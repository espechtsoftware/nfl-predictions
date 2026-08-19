#!/usr/bin/env bash
set -euo pipefail

# Generalized single-cell repair for the ATLAS C attempt-2 grid: wait out
# an amendment build, redeploy the shared job to it, rerun ONE cell,
# update the ledger/manifest with disclosure, poll all 54 objects, then
# run the attempt-aware strict finisher. Passed cells keep their
# receipts: the fill lever fires only on duplicate optima, which failed
# the pre-amendment parity check, so every passed cell is provably a
# no-op under the amendment (recorded in the freeze doc).
#
# Usage: repair_atlas_c2_cell.sh <season> <week> <build-id> <code-sha> <amendment-label>

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260818-atlas-minimal-world-selection-c-v1
OUT="$ROOT/reports/atlas-minimal-c-runs/$RUN_ID-attempt-2"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-minimal-world-selection-c-runs/$RUN_ID/attempt-2
REUSED_JOB=atlas-minimal-c-s2023-w1-v1

SEASON=${1:?season}
WEEK=${2:?week}
BUILD_ID=${3:?build id}
CODE_SHA=${4:?code sha}
LABEL=${5:?amendment label}

while :; do
  STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --format='value(status)' 2>/dev/null || echo "")
  printf '%s ATLAS_C2C_BUILD status=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${STATUS:-Unknown}"
  case "$STATUS" in
    SUCCESS) break ;;
    FAILURE|CANCELLED|TIMEOUT|EXPIRED)
      echo "ERROR: cell-repair build terminal $STATUS" >&2; exit 2 ;;
    *) sleep 120 ;;
  esac
done
DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
  --format='value(results.images[0].digest)')
IMAGE="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@${DIGEST}"
URI="$PREFIX/slate-${SEASON}-${WEEK}.json"
gsutil -q stat "$URI" && {
  echo "ERROR: cell object already exists" >&2; exit 2; }

gcloud run jobs deploy "$REUSED_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
  --max-retries 0 --task-timeout 2h \
  --service-account 817589974517-compute@developer.gserviceaccount.com \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
  --command python \
  --args "scripts/run_atlas_minimal_world_selection_c.py,--season,$SEASON,--week,$WEEK,--output-uri,$URI" \
  --quiet >/dev/null
EXECUTION=$(gcloud run jobs execute "$REUSED_JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
echo "ATLAS_C2C_CELL_RELAUNCHED $SEASON $WEEK $EXECUTION"
printf '%s_repair_execution=%s\n%s_image=%s\n%s_code_sha=%s\n' \
  "$LABEL" "$EXECUTION" "$LABEL" "$IMAGE" "$LABEL" "$CODE_SHA" \
  >> "$OUT/manifest.txt"
python3 - "$OUT/executions.txt" "$SEASON" "$WEEK" "$REUSED_JOB" \
  "$EXECUTION" "$URI" <<'PY'
import sys
path, season, week, job, execution, uri = sys.argv[1:]
lines = open(path).read().splitlines()
out = []
for line in lines:
    parts = line.split()
    if parts[0] == season and parts[1] == week:
        out.append(f"{season} {week} {job} {execution} {uri}")
    else:
        out.append(line)
open(path, "w").write("\n".join(out) + "\n")
PY
sha256sum "$OUT/manifest.txt" "$OUT/executions.txt" > "$OUT/launch.sha256"

while :; do
  OBJECTS=$(gsutil ls "$PREFIX/slate-*.json" 2>/dev/null | wc -l)
  printf '%s ATLAS_C2C_GRID objects=%s/54\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$OBJECTS"
  [ "$OBJECTS" -ge 54 ] && break
  STATE=$(gcloud run jobs executions describe "$EXECUTION" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
  if [ "$STATE" = "False" ]; then
    printf '%s ATLAS_C2C_CELL_FAILED %s %s %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SEASON" "$WEEK" "$EXECUTION"
    exit 2
  fi
  sleep 180
done
ATLAS_C_OUT_DIR="$OUT" ATLAS_C_PREFIX="$PREFIX" \
  bash "$ROOT/scripts/cloud_finish_atlas_minimal_c.sh"
