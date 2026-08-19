#!/usr/bin/env bash
set -euo pipefail

# Resume the ATLAS C grid after the JobsPerProject=1000 quota stop.
#
# The original launcher created one Cloud Run job per cell (the house
# pattern) and hit the project's 1000-job cap at cell #17; the canary
# PASSED and 16 cells are executing. This resume launches every missing
# cell as a per-execution `--args` override on the EXISTING canary job —
# zero new job definitions — appends to the same ledger, and writes the
# manifest the interrupted launcher never reached, with the quota event
# disclosed. The finisher binds execution ids + create-only output
# objects, so reused job names change nothing scientific.
#
# Usage: resume_atlas_minimal_c_grid.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260818-atlas-minimal-world-selection-c-v1
OUT="$ROOT/reports/atlas-minimal-c-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-minimal-world-selection-c-runs/$RUN_ID
EXECUTIONS="$OUT/executions.txt"
REUSED_JOB=atlas-minimal-c-s2023-w1-v1

IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/.+@sha256:[0-9a-f]{64}$ ]] && \
  [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] && \
  [[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: resume needs <image@digest> <code-sha> <build-id>" >&2; exit 2; }

[ -f "$EXECUTIONS" ] || {
  echo "ERROR: no interrupted ledger to resume" >&2; exit 2; }
[ -e "$OUT/manifest.txt" ] && {
  echo "ERROR: manifest exists; this run already completed its launch" >&2
  exit 2; }

# Same in-image pin checks the launcher ran.
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

# The reused job's template must carry the exact frozen image and env.
TEMPLATE=$(gcloud run jobs describe "$REUSED_JOB" --project "$PROJECT" \
  --region "$REGION" --format=json)
"$ROOT/.venv/bin/python" - "$IMAGE" "$CODE_SHA" <<PY
import json, sys
template = json.loads('''$TEMPLATE''')
image, code = sys.argv[1], sys.argv[2]
container = template["spec"]["template"]["spec"]["template"]["spec"]["containers"][0]
env = {row["name"]: row.get("value", "") for row in container.get("env", [])}
if container["image"] != image or env.get("CODE_SHA") != code or \
        env.get("ANALYSIS_IMAGE") != image:
    raise SystemExit("ERROR: reused job template differs from the frozen launch")
print("ATLAS_C_REUSED_JOB_TEMPLATE_OK")
PY

launch_missing() {
  local season=$1 week=$2
  local uri="$PREFIX/slate-${season}-${week}.json"
  local execution
  execution=$(gcloud run jobs execute "$REUSED_JOB" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)' \
    --args "scripts/run_atlas_minimal_world_selection_c.py,--season,$season,--week,$week,--output-uri,$uri")
  [[ "$execution" == "$REUSED_JOB-"* ]] || {
    echo "ERROR: ATLAS C resumed execution identity missing" >&2; exit 2; }
  printf '%s %s %s %s %s\n' "$season" "$week" "$REUSED_JOB" "$execution" "$uri" \
    >> "$EXECUTIONS"
  echo "ATLAS_C_RESUMED_CELL $season $week $execution"
}

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    grep -q "^$SEASON $WEEK " "$EXECUTIONS" && continue
    launch_missing "$SEASON" "$WEEK"
    sleep 2
  done
done
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: ATLAS C resumed population is not 54" >&2; exit 2; }

printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" \
  "freeze_doc_sha256=$(sha256sum "$ROOT/reports/2026-08-18-atlas-minimal-c-implementation-freeze.md" | awk '{print $1}')" \
  "source_grid_sha256=$(sha256sum "$ROOT/reports/atlas-money-world-runs/20260815-atlas-current-money-worlds-v1/source-grid.json" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$ROOT/scripts/run_atlas_minimal_world_selection_c.py" | awk '{print $1}')" \
  "launcher_sha256=$(sha256sum "$ROOT/scripts/cloud_atlas_minimal_c_launcher.sh" | awk '{print $1}')" \
  "resume_sha256=$(sha256sum "$ROOT/scripts/resume_atlas_minimal_c_grid.sh" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$ROOT/scripts/cloud_finish_atlas_minimal_c.sh" | awk '{print $1}')" \
  "queue_gate=coherent-historical-report-object" \
  "resume_note=JobsPerProject-quota-1000-stop-after-16-cells; remaining cells are per-execution --args overrides on $REUSED_JOB (zero new jobs); ledger job column records the reused job" \
  'uses_realized_outcomes=true' 'production_change_licensed=false' \
  'predeclared_prior=negative' 'cells=54' 'canary=2023-1 (PASSED)' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=7200' 'max_retries=0' \
  > "$OUT/manifest.txt"
sha256sum "$OUT/manifest.txt" "$EXECUTIONS" > "$OUT/launch.sha256"
echo "ATLAS_C_GRID_RESUMED_AND_LAUNCHED $RUN_ID"
