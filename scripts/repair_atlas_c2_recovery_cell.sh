#!/usr/bin/env bash
set -euo pipefail
# Amendment-5 surgical repair: wait out the fe81fbe build, redeploy the
# shared job to it, rerun ONLY the four-seed recovery cell (2025 W1),
# append the mixed-image disclosure to the attempt-2 manifest, poll all
# 54 objects, then run the attempt-aware strict finisher. The 53
# five-seed cells stay on the Amendment-4 image (the Amendment-5 branch
# is unreachable at five seeds; freeze doc records the argument).
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260818-atlas-minimal-world-selection-c-v1
OUT="$ROOT/reports/atlas-minimal-c-runs/$RUN_ID-attempt-2"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-minimal-world-selection-c-runs/$RUN_ID/attempt-2
REUSED_JOB=atlas-minimal-c-s2023-w1-v1
BUILD_ID=${1:?build id}
CODE_SHA=${2:?code sha}

while :; do
  STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --format='value(status)' 2>/dev/null || echo "")
  printf '%s ATLAS_C2R_BUILD status=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${STATUS:-Unknown}"
  case "$STATUS" in
    SUCCESS) break ;;
    FAILURE|CANCELLED|TIMEOUT|EXPIRED)
      echo "ERROR: repair build terminal $STATUS" >&2; exit 2 ;;
    *) sleep 120 ;;
  esac
done
DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
  --format='value(results.images[0].digest)')
IMAGE="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@${DIGEST}"
URI="$PREFIX/slate-2025-1.json"
gsutil -q stat "$URI" && {
  echo "ERROR: recovery cell object already exists" >&2; exit 2; }

gcloud run jobs deploy "$REUSED_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
  --max-retries 0 --task-timeout 2h \
  --service-account 817589974517-compute@developer.gserviceaccount.com \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
  --command python \
  --args "scripts/run_atlas_minimal_world_selection_c.py,--season,2025,--week,1,--output-uri,$URI" \
  --quiet >/dev/null
EXECUTION=$(gcloud run jobs execute "$REUSED_JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
echo "ATLAS_C2R_RECOVERY_LAUNCHED $EXECUTION"
printf 'amendment5_recovery_execution=%s\namendment5_image=%s\namendment5_code_sha=%s\namendment5_note=only the four-seed recovery cell runs this image; the Amendment-5 branch is unreachable at five seeds\n' \
  "$EXECUTION" "$IMAGE" "$CODE_SHA" >> "$OUT/manifest.txt"
sed -i "s|^2025 1 .*|2025 1 $REUSED_JOB $EXECUTION $URI|" "$OUT/executions.txt"
sha256sum "$OUT/manifest.txt" "$OUT/executions.txt" > "$OUT/launch.sha256"

while :; do
  OBJECTS=$(gsutil ls "$PREFIX/slate-*.json" 2>/dev/null | wc -l)
  printf '%s ATLAS_C2R_GRID objects=%s/54\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$OBJECTS"
  [ "$OBJECTS" -ge 54 ] && break
  while read -r SEASON WEEK JOB EXEC CELL_URI; do
    gsutil -q stat "$CELL_URI" 2>/dev/null && continue
    STATE=$(gcloud run jobs executions describe "$EXEC" \
      --project "$PROJECT" --region "$REGION" \
      --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
    if [ "$STATE" = "False" ]; then
      printf '%s ATLAS_C2R_CELL_FAILED %s %s %s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SEASON" "$WEEK" "$EXEC"
      exit 2
    fi
  done < "$OUT/executions.txt"
  sleep 300
done
ATLAS_C_OUT_DIR="$OUT" ATLAS_C_PREFIX="$PREFIX" \
  bash "$ROOT/scripts/cloud_finish_atlas_minimal_c.sh"
