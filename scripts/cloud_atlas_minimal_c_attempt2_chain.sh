#!/usr/bin/env bash
set -euo pipefail

# Attempt-2 chain for the ATLAS C grid (freeze Amendment 4): wait for the
# amendment build, verify it, redeploy the single reused job to the new
# image (JobsPerProject quota: zero new jobs), run the 2023 W1 real-path
# canary, release the 53 remaining cells as per-execution --args
# overrides, then poll to terminal and run the strict finisher against
# the attempt-2 prefix. Attempt-1 objects and ledger are preserved
# untouched; the queue gate (historical report object) is already
# satisfied and re-checked once.
#
# Usage: cloud_atlas_minimal_c_attempt2_chain.sh <build-id> <code-sha>

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260818-atlas-minimal-world-selection-c-v1
OUT="$ROOT/reports/atlas-minimal-c-runs/$RUN_ID-attempt-2"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-minimal-world-selection-c-runs/$RUN_ID/attempt-2
HISTORICAL_REPORT=gs://nfl-predictions-503414-raw/research/coherent-market-state-historical-score-runs/20260817-coherent-market-state-historical-score-v1/report.json
REUSED_JOB=atlas-minimal-c-s2023-w1-v1
EXECUTIONS="$OUT/executions.txt"

BUILD_ID=${1:-}
CODE_SHA=${2:-}
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] && [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: attempt-2 chain needs <build-id> <code-sha>" >&2; exit 2; }

[ -e "$EXECUTIONS" ] && {
  echo "ERROR: attempt-2 ledger already exists" >&2; exit 2; }

while :; do
  STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --format='value(status)' 2>/dev/null || echo "")
  printf '%s ATLAS_C2_BUILD status=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${STATUS:-Unknown}"
  case "$STATUS" in
    SUCCESS) break ;;
    FAILURE|CANCELLED|TIMEOUT|EXPIRED)
      echo "ERROR: attempt-2 build terminal $STATUS" >&2; exit 2 ;;
    *) sleep 120 ;;
  esac
done
DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
  --format='value(results.images[0].digest)')
TAG="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:atlas-minimal-c-${CODE_SHA:0:7}"
IMAGE="us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@${DIGEST}"

gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json \
  > /tmp/atlas-c2-build.json
"$ROOT/.venv/bin/python" - /tmp/atlas-c2-build.json "$IMAGE" "$CODE_SHA" "$TAG" <<'PY'
import json, sys
b = json.load(open(sys.argv[1], encoding="utf-8"))
image, code, tag = sys.argv[2:]
digest = image.rsplit("@", 1)[1]
images = b.get("results", {}).get("images", [])
steps = {row.get("id"): row.get("status") for row in b.get("steps", [])}
if b.get("substitutions", {}).get("_IMAGE") != tag or \
        not any(r.get("digest") == digest and r.get("name") == tag for r in images) or \
        steps.get("full-test-suite") != "SUCCESS" or \
        steps.get("smoke-atlas-mvp-runner") != "SUCCESS":
    raise SystemExit("ERROR: attempt-2 validation build differs")
print("ATLAS_C2_BUILD_OK")
PY

for RELATIVE in \
  Dockerfile cloudbuild.yaml \
  scripts/run_atlas_minimal_world_selection_c.py \
  reports/2026-08-18-atlas-minimal-c-implementation-freeze.md \
  reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/source-grid.json; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: attempt-2 built source differs: $RELATIVE" >&2; exit 2; }
done
gsutil -q stat "$HISTORICAL_REPORT" || {
  echo "ERROR: attempt-2 queue gate regressed" >&2; exit 2; }
if gsutil -q stat "$PREFIX/slate-*.json" 2>/dev/null; then
  echo "ERROR: attempt-2 prefix already holds objects" >&2; exit 2
fi
mkdir -p "$OUT"

gcloud run jobs deploy "$REUSED_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
  --max-retries 0 --task-timeout 2h \
  --service-account 817589974517-compute@developer.gserviceaccount.com \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
  --command python \
  --args "scripts/run_atlas_minimal_world_selection_c.py,--season,2023,--week,1,--output-uri,$PREFIX/slate-2023-1.json" \
  --quiet >/dev/null
echo "ATLAS_C2_JOB_UPDATED $IMAGE"

run_cell() {
  local season=$1 week=$2
  local uri="$PREFIX/slate-${season}-${week}.json"
  local execution
  execution=$(gcloud run jobs execute "$REUSED_JOB" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)' \
    --args "scripts/run_atlas_minimal_world_selection_c.py,--season,$season,--week,$week,--output-uri,$uri")
  [[ "$execution" == "$REUSED_JOB-"* ]] || {
    echo "ERROR: attempt-2 execution identity missing" >&2; exit 2; }
  printf '%s %s %s %s %s\n' "$season" "$week" "$REUSED_JOB" "$execution" "$uri" \
    >> "$EXECUTIONS"
}

run_cell 2023 1
CANARY_EXEC=$(awk '{print $4}' "$EXECUTIONS")
echo "ATLAS_C2_CANARY_LAUNCHED $CANARY_EXEC"
DEADLINE=$(( $(date +%s) + 6000 ))
while :; do
  STATE=$(gcloud run jobs executions describe "$CANARY_EXEC" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
  printf '%s ATLAS_C2_CANARY state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${STATE:-Unknown}"
  [ "$STATE" = "True" ] && break
  [ "$STATE" = "False" ] && {
    echo "ERROR: attempt-2 canary failed; halt and disposition" >&2; exit 2; }
  [ "$(date +%s)" -ge "$DEADLINE" ] && {
    echo "ERROR: attempt-2 canary did not terminate in 100 minutes" >&2
    exit 2; }
  sleep 60
done
gsutil -q stat "$PREFIX/slate-2023-1.json" || {
  echo "ERROR: attempt-2 canary produced no output object" >&2; exit 2; }
echo "ATLAS_C2_CANARY_PASSED"

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    [ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && continue
    run_cell "$SEASON" "$WEEK"
    sleep 2
  done
done
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: attempt-2 population is not 54" >&2; exit 2; }

printf '%s\n' \
  "run_id=$RUN_ID" "attempt=2" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "build_id=$BUILD_ID" "output_prefix=$PREFIX" \
  "freeze_doc_sha256=$(sha256sum "$ROOT/reports/2026-08-18-atlas-minimal-c-implementation-freeze.md" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$ROOT/scripts/run_atlas_minimal_world_selection_c.py" | awk '{print $1}')" \
  "chain_sha256=$(sha256sum "$ROOT/scripts/cloud_atlas_minimal_c_attempt2_chain.sh" | awk '{print $1}')" \
  "attempt1_note=superseded-by-freeze-amendment-4 (preseeded role dedup); attempt-1 ledger/objects preserved untouched" \
  "quota_note=single reused job, per-execution --args overrides (JobsPerProject=1000)" \
  'uses_realized_outcomes=true' 'production_change_licensed=false' \
  'predeclared_prior=negative' 'cells=54' 'canary=2023-1' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=7200' 'max_retries=0' \
  > "$OUT/manifest.txt"
sha256sum "$OUT/manifest.txt" "$EXECUTIONS" > "$OUT/launch.sha256"
echo "ATLAS_C2_GRID_LAUNCHED"

while :; do
  OBJECTS=$(gsutil ls "$PREFIX/slate-*.json" 2>/dev/null | wc -l)
  printf '%s ATLAS_C2_GRID objects=%s/54\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$OBJECTS"
  [ "$OBJECTS" -ge 54 ] && break
  while read -r SEASON WEEK JOB EXECUTION URI; do
    gsutil -q stat "$URI" 2>/dev/null && continue
    STATE=$(gcloud run jobs executions describe "$EXECUTION" \
      --project "$PROJECT" --region "$REGION" \
      --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
    if [ "$STATE" = "False" ]; then
      printf '%s ATLAS_C2_CELL_FAILED %s %s %s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SEASON" "$WEEK" "$EXECUTION"
      exit 2
    fi
  done < "$EXECUTIONS"
  sleep 300
done
ATLAS_C_OUT_DIR="$OUT" ATLAS_C_PREFIX="$PREFIX" \
  bash "$ROOT/scripts/cloud_finish_atlas_minimal_c.sh"
