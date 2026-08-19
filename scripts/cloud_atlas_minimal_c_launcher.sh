#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_atlas_minimal_c_launcher.sh <image@sha256:...> <code-sha> <build-id>
#
# Launches the frozen minimal ATLAS world-selection C test
# (20260818-atlas-minimal-world-selection-c-v1): real-path canary on
# 2023 W1 (the reality-tested smoke slate) with its reproduction gate,
# then the 53 remaining create-only cells. Queued strictly behind the
# coherent historical stage: exits 3 (QUEUE_NOT_RELEASED) until the
# historical report object exists, so the watcher can loop.
#
# Pin design (frozen-chain lessons, CLAUDE.md): files that run INSIDE the
# image are pinned against the image's CODE_SHA; this launcher, the
# finisher and the watcher run locally and are RECORDED by sha256 in the
# manifest without being pinned to the image commit — an orchestration
# fix must never cost a rebuild cycle again.

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260818-atlas-minimal-world-selection-c-v1
OUT="$ROOT/reports/atlas-minimal-c-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-minimal-world-selection-c-runs/$RUN_ID
HISTORICAL_REPORT=gs://nfl-predictions-503414-raw/research/coherent-market-state-historical-score-runs/20260817-coherent-market-state-historical-score-v1/report.json
RUNNER="$ROOT/scripts/run_atlas_minimal_world_selection_c.py"
LAUNCHER="$ROOT/scripts/cloud_atlas_minimal_c_launcher.sh"
FINISHER="$ROOT/scripts/cloud_finish_atlas_minimal_c.sh"
WATCHER="$ROOT/scripts/watch_atlas_minimal_c_queue.sh"
FREEZE_DOC="$ROOT/reports/2026-08-18-atlas-minimal-c-implementation-freeze.md"
SOURCE_GRID="$ROOT/reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/source-grid.json"
EXECUTIONS="$OUT/executions.txt"

IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: ATLAS C immutable image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: ATLAS C full source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: ATLAS C successful build ID is required" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || {
  echo "ERROR: ATLAS C source commit is unavailable" >&2; exit 2; }

# In-image sources must match the image's commit exactly.
for RELATIVE in \
  Dockerfile cloudbuild.yaml \
  scripts/run_atlas_minimal_world_selection_c.py \
  reports/2026-08-18-atlas-minimal-c-implementation-freeze.md \
  reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/source-grid.json; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: ATLAS C built source differs: $RELATIVE" >&2; exit 2; }
done

# Runner-side frozen-input pins (freeze doc + source grid SHA constants).
"$ROOT/.venv/bin/python" - <<'PY'
import sys
sys.path.insert(0, "src"); sys.path.insert(0, "scripts")
import run_atlas_minimal_world_selection_c as runner
runner.validate_frozen_inputs()
print("ATLAS_C_FROZEN_INPUTS_OK")
PY

# The validation build must be SUCCESS, tagged for this commit, carrying
# this digest, with the full suite and runner smoke green.
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json \
  > /tmp/atlas-c-build-metadata.json
"$ROOT/.venv/bin/python" - /tmp/atlas-c-build-metadata.json "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys
b = json.load(open(sys.argv[1], encoding="utf-8"))
image, code = sys.argv[2:]
digest = image.rsplit("@", 1)[1]
tag = f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:atlas-minimal-c-{code[:7]}"
images = b.get("results", {}).get("images", [])
steps = {row.get("id"): row.get("status") for row in b.get("steps", [])}
if b.get("status") != "SUCCESS" or b.get("substitutions", {}).get("_IMAGE") != tag or \
        not any(row.get("digest") == digest and row.get("name") == tag for row in images) or \
        steps.get("full-test-suite") != "SUCCESS" or \
        steps.get("smoke-atlas-mvp-runner") != "SUCCESS":
    raise SystemExit("ERROR: ATLAS C validation build differs")
print("ATLAS_C_BUILD_OK")
PY

# Queue gate: strictly behind the coherent historical stage.
if [ "${ATLAS_C_QUEUE_OVERRIDE:-}" != "1" ]; then
  gsutil -q stat "$HISTORICAL_REPORT" || {
    echo "ATLAS_C_QUEUE_NOT_RELEASED waiting_for=$HISTORICAL_REPORT"; exit 3; }
fi

# Create-only: a prior launch of this run id must never be overwritten.
[ -e "$EXECUTIONS" ] && {
  echo "ERROR: ATLAS C executions ledger already exists" >&2; exit 2; }
if gsutil -q stat "$PREFIX/slate-*.json" 2>/dev/null; then
  echo "ERROR: ATLAS C output prefix already holds cell objects" >&2; exit 2
fi
mkdir -p "$OUT"

deploy_cell() {
  local season=$1 week=$2
  local job="atlas-minimal-c-s${season}-w${week}-v1"
  local uri="$PREFIX/slate-${season}-${week}.json"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
    --max-retries 0 --task-timeout 2h --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
    --command python \
    --args "scripts/run_atlas_minimal_world_selection_c.py,--season,$season,--week,$week,--output-uri,$uri" \
    --quiet >/dev/null
  local execution
  execution=$(gcloud run jobs execute "$job" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [[ "$execution" == "$job-"* ]] || {
    echo "ERROR: ATLAS C execution identity missing" >&2; exit 2; }
  printf '%s %s %s %s %s\n' "$season" "$week" "$job" "$execution" "$uri" \
    >> "$EXECUTIONS"
}

# Real-path canary: the reality-tested smoke slate, full outcome path.
deploy_cell 2023 1
CANARY_EXEC=$(awk '{print $4}' "$EXECUTIONS")
echo "ATLAS_C_CANARY_LAUNCHED $CANARY_EXEC"
DEADLINE=$(( $(date +%s) + 6000 ))
while :; do
  STATE=$(gcloud run jobs executions describe "$CANARY_EXEC" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
  echo "$(date -u +%Y-%m-%dT%H:%M:%SZ) ATLAS_C_CANARY state=${STATE:-Unknown}"
  [ "$STATE" = "True" ] && break
  [ "$STATE" = "False" ] && {
    echo "ERROR: ATLAS C canary execution failed; halt and disposition" >&2
    exit 2; }
  [ "$(date +%s)" -ge "$DEADLINE" ] && {
    echo "ERROR: ATLAS C canary did not terminate in 100 minutes" >&2
    exit 2; }
  sleep 60
done
gsutil -q stat "$PREFIX/slate-2023-1.json" || {
  echo "ERROR: ATLAS C canary produced no output object" >&2; exit 2; }
echo "ATLAS_C_CANARY_PASSED"

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    [ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && continue
    deploy_cell "$SEASON" "$WEEK"
  done
done
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: ATLAS C execution population is incomplete" >&2; exit 2; }

printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" \
  "freeze_doc_sha256=$(sha256sum "$FREEZE_DOC" | awk '{print $1}')" \
  "source_grid_sha256=$(sha256sum "$SOURCE_GRID" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "launcher_sha256=$(sha256sum "$LAUNCHER" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$FINISHER" | awk '{print $1}')" \
  "watcher_sha256=$(sha256sum "$WATCHER" | awk '{print $1}')" \
  "queue_gate=coherent-historical-report-object" \
  'uses_realized_outcomes=true' 'production_change_licensed=false' \
  'predeclared_prior=negative' 'cells=54' 'canary=2023-1' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=7200' 'max_retries=0' \
  > "$OUT/manifest.txt"
sha256sum "$OUT/manifest.txt" "$EXECUTIONS" > "$OUT/launch.sha256"
echo "ATLAS_C_GRID_LAUNCHED $RUN_ID"
