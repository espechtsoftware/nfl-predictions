#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_stack_core_shell_production_locks.sh <image@sha256:...> <code-sha> <build-id> <scorefree-report-sha256> <scorefree-completion-sha256>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-stack-core-shell-production-lock-v1
OUT="$ROOT/reports/stack-core-shell-lock-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/stack-core-shell-lock-runs/$RUN_ID
SCOREFREE_ID=20260816-stack-core-shell-scorefree-v1
SCOREFREE="$ROOT/reports/stack-core-shell-runs/$SCOREFREE_ID"
SCOREFREE_REPORT_URI=gs://nfl-predictions-503414-raw/research/stack-core-shell-runs/$SCOREFREE_ID/report.json
SCOREFREE_COMPLETION_URI=gs://nfl-predictions-503414-raw/research/stack-core-shell-runs/$SCOREFREE_ID/completion.txt
HISTORICAL_PROTOCOL="$ROOT/reports/2026-08-16-stack-core-shell-historical-score-protocol.md"
HISTORICAL_PROTOCOL_SHA=f562ce6e9a7e0458a1fd3382692f6761f1d9de56edb06ab4350403584cd702fc
EXECUTION_PROTOCOL="$ROOT/reports/2026-08-16-stack-core-shell-lock-execution-protocol.md"
EXECUTION_PROTOCOL_SHA=71063a42c21a1f6bff4d881af6e60bb10b1860d87d72c62332beb2ec83b27e7f
RUNNER="$ROOT/scripts/run_stack_core_shell_production_lock.py"
AGGREGATOR="$ROOT/scripts/aggregate_stack_core_shell_production_locks.py"
SOURCES="$ROOT/scripts/stack_core_shell_sources.py"
CANARY="$ROOT/scripts/cloud_wait_stack_core_shell_lock_canary.sh"
CANARY_VALIDATOR="$ROOT/scripts/validate_stack_core_shell_lock_canary.py"
ATTEMPTS="$ROOT/scripts/manage_stack_core_shell_lock_attempts.py"
FINISHER="$ROOT/scripts/finish_stack_core_shell_production_locks.py"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}
SCOREFREE_REPORT_SHA=${4:-}
SCOREFREE_COMPLETION_SHA=${5:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable production-lock image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full production-lock source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful production-lock build ID is required" >&2; exit 2; }
[[ "$SCOREFREE_REPORT_SHA" =~ ^[0-9a-f]{64}$ ]] && \
  [[ "$SCOREFREE_COMPLETION_SHA" =~ ^[0-9a-f]{64}$ ]] || {
  echo "ERROR: strict score-free hashes are required" >&2; exit 2; }
[ "$(sha256sum "$HISTORICAL_PROTOCOL" | awk '{print $1}')" = "$HISTORICAL_PROTOCOL_SHA" ] && \
  [ "$(sha256sum "$EXECUTION_PROTOCOL" | awk '{print $1}')" = "$EXECUTION_PROTOCOL_SHA" ] || {
  echo "ERROR: frozen production-lock protocol differs" >&2; exit 2; }
for REQUIRED in "$SCOREFREE/report.json" "$SCOREFREE/completion.txt" \
  "$SCOREFREE/report-upload.json" "$SCOREFREE/completion-upload.json" \
  "$SCOREFREE/accepted-executions.txt" "$SCOREFREE/attempt-resolution.json"; do
  [ -s "$REQUIRED" ] || {
    echo "ERROR: strict score-free harvest is incomplete: $REQUIRED" >&2; exit 2; }
done
[ "$(sha256sum "$SCOREFREE/report.json" | awk '{print $1}')" = "$SCOREFREE_REPORT_SHA" ] && \
  [ "$(sha256sum "$SCOREFREE/completion.txt" | awk '{print $1}')" = "$SCOREFREE_COMPLETION_SHA" ] || {
  echo "ERROR: strict score-free hash differs" >&2; exit 2; }

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$SCOREFREE" "$SCOREFREE_REPORT_URI" "$SCOREFREE_COMPLETION_URI" \
  "$SCOREFREE_REPORT_SHA" "$SCOREFREE_COMPLETION_SHA" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

root = Path(sys.argv[1])
report_uri, completion_uri, report_sha, completion_sha = sys.argv[2:]
report = json.loads((root / "report.json").read_text(encoding="utf-8"))
completion = dict(
    line.split("=", 1)
    for line in (root / "completion.txt").read_text(encoding="utf-8").splitlines()
    if "=" in line
)
report_upload = json.loads((root / "report-upload.json").read_text(encoding="utf-8"))
completion_upload = json.loads(
    (root / "completion-upload.json").read_text(encoding="utf-8")
)
resolution = json.loads(
    (root / "attempt-resolution.json").read_text(encoding="utf-8")
)
if report.get("version") != "stack-core-shell-scorefree-report-v1" or \
        report.get("run_id") != "20260816-stack-core-shell-scorefree-v1" or \
        report.get("uses_realized_outcomes") is not False or \
        report.get("production_change_licensed") is not False or \
        report.get("historical_scoring_licensed") is not True or \
        report.get("disposition") != "stack-core-shell-shadow-licensed" or \
        report.get("gate", {}).get("passes_scorefree_gate") is not True or \
        report.get("mechanical") != {
            "seasons": [2023, 2024, 2025], "slates": 54,
            "heldout_folds": 270, "worlds_per_fold": 10000,
            "source_artifacts": 270, "all_valid": True,
        }:
    raise SystemExit("ERROR: score-free production-lock license differs")
accepted_sha = sha256((root / "accepted-executions.txt").read_bytes()).hexdigest()
expected_completion = {
    "run_id": "20260816-stack-core-shell-scorefree-v1",
    "report_sha256": report_sha,
    "accepted_execution_ledger_sha256": accepted_sha,
    "disposition": "stack-core-shell-shadow-licensed",
    "uses_realized_outcomes": "false",
    "production_change_licensed": "false",
    "historical_scoring_licensed": "true",
}
if any(completion.get(key) != value for key, value in expected_completion.items()) or \
        sha256((root / "completion.txt").read_bytes()).hexdigest() != completion_sha:
    raise SystemExit("ERROR: score-free completion differs")
if resolution.get("disposition") not in {
    "accepted-primary-population", "accepted-population-with-platform-replacements",
} or resolution.get("accepted_execution_ledger_sha256") != accepted_sha:
    raise SystemExit("ERROR: score-free accepted execution population differs")
for receipt, uri, digest in (
    (report_upload, report_uri, report_sha),
    (completion_upload, completion_uri, completion_sha),
):
    if receipt.get("uri") != uri or receipt.get("sha256") != digest or \
            not str(receipt.get("generation", "")).isdigit() or \
            int(receipt.get("bytes", 0)) <= 0:
        raise SystemExit("ERROR: score-free upload receipt differs")
print("STACK_CORE_SHELL_LOCK_LICENSE_VALIDATED")
PY

git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}"
for RELATIVE in Dockerfile.stack-treatment cloudbuild.stack-treatment.yaml \
  reports/2026-08-16-stack-core-shell-historical-score-protocol.md \
  scripts/stack_core_shell_sources.py \
  scripts/run_stack_core_shell_production_lock.py \
  scripts/aggregate_stack_core_shell_production_locks.py \
  src/nfl_dfs/analysis/stack_core_shell.py \
  src/nfl_dfs/analysis/stack_core_shell_historical.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: production-lock built source differs: $RELATIVE" >&2; exit 2; }
done
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable production-lock run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: immutable production-lock cloud prefix exists" >&2; exit 3
fi

BUILD_TMP=$(mktemp)
trap 'rm -f "$BUILD_TMP"' EXIT
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --region "$REGION" \
  --format=json > "$BUILD_TMP"
"$ROOT/.venv/bin/python" - "$BUILD_TMP" "$IMAGE" "$CODE_SHA" <<'PY'
import json
import sys
b = json.load(open(sys.argv[1], encoding="utf-8"))
image, code = sys.argv[2:]
tag = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:"
    f"stack-shell-treatment-{code[:7]}"
)
digest = image.rsplit("@", 1)[1]
steps = {row.get("id"): row.get("status") for row in b.get("steps", [])}
required = {
    "full-test-suite", "build-image", "smoke-stack-core-shell-source-loader",
    "smoke-stack-core-shell-lock-runner",
    "smoke-stack-core-shell-lock-aggregator",
}
if b.get("status") != "SUCCESS" or b.get("substitutions", {}).get("_IMAGE") != tag or \
        any(steps.get(name) != "SUCCESS" for name in required) or not any(
            row.get("name") == tag and row.get("digest") == digest
            for row in b.get("results", {}).get("images", [])
        ):
    raise SystemExit("ERROR: production-lock build identity differs")
PY

mkdir -p "$OUT"
mv "$BUILD_TMP" "$OUT/build-metadata.json"
trap - EXIT
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" "historical_protocol_sha256=$HISTORICAL_PROTOCOL_SHA" \
  "execution_protocol_sha256=$EXECUTION_PROTOCOL_SHA" \
  "scorefree_report_uri=$SCOREFREE_REPORT_URI" \
  "scorefree_completion_uri=$SCOREFREE_COMPLETION_URI" \
  "scorefree_report_sha256=$SCOREFREE_REPORT_SHA" \
  "scorefree_completion_sha256=$SCOREFREE_COMPLETION_SHA" \
  "scorefree_report_generation=$($ROOT/.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' "$SCOREFREE/report-upload.json")" \
  "scorefree_completion_generation=$($ROOT/.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' "$SCOREFREE/completion-upload.json")" \
  "scorefree_accepted_execution_ledger_sha256=$(sha256sum "$SCOREFREE/accepted-executions.txt" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "aggregator_sha256=$(sha256sum "$AGGREGATOR" | awk '{print $1}')" \
  "source_loader_sha256=$(sha256sum "$SOURCES" | awk '{print $1}')" \
  "canary_sha256=$(sha256sum "$CANARY" | awk '{print $1}')" \
  "canary_validator_sha256=$(sha256sum "$CANARY_VALIDATOR" | awk '{print $1}')" \
  "attempt_manager_sha256=$(sha256sum "$ATTEMPTS" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$FINISHER" | awk '{print $1}')" \
  'seasons=2023,2024,2025' 'weeks=1-18' 'slates=54' 'source_artifacts=270' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=7200' 'max_retries=0' \
  'uses_realized_outcomes=false' 'effect_fields_inspected=false' \
  'actual_scores_queried=false' 'treatment_constructed=true' \
  'production_change_licensed=false' 'historical_scoring_licensed=true' > "$MANIFEST"
: > "$EXECUTIONS"

launch_cell() {
  local season=$1 week=$2
  local job="stack-shell-lock-s${season}-w${week}-v1"
  local uri="$PREFIX/slate-${season}-${week}.json"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
    --max-retries 0 --task-timeout 2h --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" --command python \
    --args "scripts/run_stack_core_shell_production_lock.py,--season,$season,--week,$week,--output-uri,$uri,--scorefree-report-sha256,$SCOREFREE_REPORT_SHA,--scorefree-completion-sha256,$SCOREFREE_COMPLETION_SHA" \
    --quiet >/dev/null
  local execution
  execution=$(gcloud run jobs execute "$job" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [[ "$execution" == "$job-"* ]] || return 2
  printf '%s %s %s %s %s\n' "$season" "$week" "$job" "$execution" "$uri" \
    >> "$EXECUTIONS"
}

launch_cell 2023 1
bash "$CANARY"
for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    [ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && continue
    launch_cell "$SEASON" "$WEEK"
  done
done
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: production-lock launch grid is not 54" >&2; exit 2; }
printf '%s\n' \
  "released_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'primary_executions=54' 'released_after_canary=53' \
  "canary_completion_sha256=$(sha256sum "$OUT/canary-completion.txt" | awk '{print $1}')" \
  'object_content_inspected=false' 'actual_scores_queried=false' \
  'treatment_constructed=true' > "$OUT/grid-release.txt"
sha256sum "$MANIFEST" > "$OUT/manifest.sha256"
sha256sum "$EXECUTIONS" > "$OUT/executions.sha256"
echo "STACK_CORE_SHELL_PRODUCTION_LOCKS_LAUNCHED $RUN_ID"
