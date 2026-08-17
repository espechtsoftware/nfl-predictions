#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_stack_core_shell_scorefree.sh <image@sha256:...> <code-sha> <build-id> <support-report-sha256> <support-completion-sha256>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-stack-core-shell-scorefree-v1
OUT="$ROOT/reports/stack-core-shell-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/stack-core-shell-runs/$RUN_ID
SUPPORT_ID=20260816-stack-core-shell-control-support-census-v1
SUPPORT="$ROOT/reports/stack-core-shell-support-runs/$SUPPORT_ID"
SUPPORT_URI=gs://nfl-predictions-503414-raw/research/stack-core-shell-support-runs/$SUPPORT_ID/report.json
PROTOCOL="$ROOT/reports/2026-08-16-stack-core-shell-scorefree-protocol.md"
PROTOCOL_SHA=edd13697fd3d7fc787d159c74d6e8280bf1b51517dcdbacc8337011a01cd5d46
EXECUTION_PROTOCOL="$ROOT/reports/2026-08-16-stack-core-shell-treatment-execution-protocol.md"
EXECUTION_PROTOCOL_SHA=e786783334d994caf4378beffaef6a048e6ba9fb13541382b7e491bf412dc78d
RUNNER="$ROOT/scripts/run_stack_core_shell_scorefree.py"
AGGREGATOR="$ROOT/scripts/aggregate_stack_core_shell_scorefree.py"
SOURCES="$ROOT/scripts/stack_core_shell_sources.py"
CANARY="$ROOT/scripts/cloud_wait_stack_core_shell_scorefree_canary.sh"
CANARY_VALIDATOR="$ROOT/scripts/validate_stack_core_shell_scorefree_canary.py"
ATTEMPTS="$ROOT/scripts/manage_stack_core_shell_scorefree_attempts.py"
FINISHER="$ROOT/scripts/finish_stack_core_shell_scorefree.py"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}
SUPPORT_REPORT_SHA=${4:-}
SUPPORT_COMPLETION_SHA=${5:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable score-free image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full score-free source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful score-free build ID is required" >&2; exit 2; }
[[ "$SUPPORT_REPORT_SHA" =~ ^[0-9a-f]{64}$ ]] && \
  [[ "$SUPPORT_COMPLETION_SHA" =~ ^[0-9a-f]{64}$ ]] || {
  echo "ERROR: strict support hashes are required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] && \
  [ "$(sha256sum "$EXECUTION_PROTOCOL" | awk '{print $1}')" = "$EXECUTION_PROTOCOL_SHA" ] || {
  echo "ERROR: frozen score-free protocol differs" >&2; exit 2; }
for REQUIRED in "$SUPPORT/report.json" "$SUPPORT/completion.txt" \
  "$SUPPORT/report-upload.json" "$SUPPORT/accepted-executions.txt" \
  "$SUPPORT/attempt-resolution.json"; do
  [ -s "$REQUIRED" ] || {
    echo "ERROR: strict support harvest is incomplete: $REQUIRED" >&2; exit 2; }
done
[ "$(sha256sum "$SUPPORT/report.json" | awk '{print $1}')" = "$SUPPORT_REPORT_SHA" ] && \
  [ "$(sha256sum "$SUPPORT/completion.txt" | awk '{print $1}')" = "$SUPPORT_COMPLETION_SHA" ] || {
  echo "ERROR: strict support hash differs" >&2; exit 2; }

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$SUPPORT" "$SUPPORT_URI" "$SUPPORT_REPORT_SHA" \
  "$SUPPORT_COMPLETION_SHA" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
uri, report_sha, completion_sha = sys.argv[2:]
report = json.loads((root / "report.json").read_text(encoding="utf-8"))
completion = dict(
    line.split("=", 1)
    for line in (root / "completion.txt").read_text(encoding="utf-8").splitlines()
    if "=" in line
)
upload = json.loads((root / "report-upload.json").read_text(encoding="utf-8"))
resolution = json.loads((root / "attempt-resolution.json").read_text(encoding="utf-8"))
anchor = report.get("selected_anchor")
expected = {
    230: "p230-supported-stack-core-shell-treatment-licensed",
    220: "p220-supported-stack-core-shell-treatment-licensed",
    210: "p210-supported-stack-core-shell-treatment-licensed",
}
adequate = report.get("adequate_by_threshold", {})
first = next((value for value in (230, 220, 210) if adequate.get(str(value)) is True), None)
if report.get("version") != "stack-core-shell-control-support-report-v1" or \
        report.get("uses_realized_outcomes") is not False or \
        report.get("treatment_constructed") is not False or \
        report.get("production_change_licensed") is not False or \
        anchor not in expected or anchor != first or \
        report.get("disposition") != expected[anchor] or \
        report.get("mechanical") != {
            "seasons": [2023, 2024, 2025], "slates": 54,
            "heldout_folds": 270, "worlds_per_fold": 10000,
            "source_artifacts": 270, "all_valid": True,
        }:
    raise SystemExit("ERROR: support license differs")
if completion.get("disposition") != expected[anchor] or \
        completion.get("selected_anchor") != str(anchor) or \
        completion.get("uses_realized_outcomes") != "false" or \
        completion.get("treatment_constructed") != "false" or \
        completion.get("accepted_executions_sha256") != sha256(
            (root / "accepted-executions.txt").read_bytes()
        ).hexdigest() or sha256((root / "report.json").read_bytes()).hexdigest() != report_sha or \
        sha256((root / "completion.txt").read_bytes()).hexdigest() != completion_sha:
    raise SystemExit("ERROR: support completion differs")
if resolution.get("disposition") not in {
    "accepted-primary-population", "accepted-population-with-platform-replacements",
} or resolution.get("accepted_execution_ledger_sha256") != completion.get(
    "accepted_executions_sha256"
):
    raise SystemExit("ERROR: support accepted execution population differs")
if upload.get("uri") != uri or upload.get("sha256") != report_sha or \
        not str(upload.get("generation", "")).isdigit() or int(upload.get("bytes", 0)) <= 0:
    raise SystemExit("ERROR: support upload receipt differs")
print("STACK_CORE_SHELL_SUPPORT_LICENSE_VALIDATED", anchor)
PY

git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}"
for RELATIVE in Dockerfile.stack-treatment cloudbuild.stack-treatment.yaml \
  reports/2026-08-16-stack-core-shell-scorefree-protocol.md \
  reports/2026-08-16-stack-core-shell-treatment-execution-protocol.md \
  scripts/stack_core_shell_sources.py scripts/run_stack_core_shell_scorefree.py \
  scripts/aggregate_stack_core_shell_scorefree.py \
  scripts/cloud_wait_stack_core_shell_scorefree_canary.sh \
  scripts/validate_stack_core_shell_scorefree_canary.py \
  scripts/manage_stack_core_shell_scorefree_attempts.py \
  src/nfl_dfs/analysis/stack_core_shell.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: score-free built source differs: $RELATIVE" >&2; exit 2; }
done
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable score-free run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: immutable score-free cloud prefix exists" >&2; exit 3
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
    "smoke-stack-core-shell-scorefree-runner",
    "smoke-stack-core-shell-scorefree-aggregator",
}
if b.get("status") != "SUCCESS" or b.get("substitutions", {}).get("_IMAGE") != tag or \
        any(steps.get(name) != "SUCCESS" for name in required) or not any(
            row.get("name") == tag and row.get("digest") == digest
            for row in b.get("results", {}).get("images", [])
        ):
    raise SystemExit("ERROR: score-free build identity differs")
PY

mkdir -p "$OUT"
mv "$BUILD_TMP" "$OUT/build-metadata.json"
trap - EXIT
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" "protocol_sha256=$PROTOCOL_SHA" \
  "execution_protocol_sha256=$EXECUTION_PROTOCOL_SHA" \
  "support_report_uri=$SUPPORT_URI" "support_report_sha256=$SUPPORT_REPORT_SHA" \
  "support_completion_sha256=$SUPPORT_COMPLETION_SHA" \
  "support_report_generation=$($ROOT/.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' "$SUPPORT/report-upload.json")" \
  "support_report_bytes=$($ROOT/.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["bytes"])' "$SUPPORT/report-upload.json")" \
  "support_accepted_execution_ledger_sha256=$(sha256sum "$SUPPORT/accepted-executions.txt" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "aggregator_sha256=$(sha256sum "$AGGREGATOR" | awk '{print $1}')" \
  "source_loader_sha256=$(sha256sum "$SOURCES" | awk '{print $1}')" \
  "canary_sha256=$(sha256sum "$CANARY" | awk '{print $1}')" \
  "canary_validator_sha256=$(sha256sum "$CANARY_VALIDATOR" | awk '{print $1}')" \
  "attempt_manager_sha256=$(sha256sum "$ATTEMPTS" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$FINISHER" | awk '{print $1}')" \
  'seasons=2023,2024,2025' 'weeks=1-18' 'slates=54' 'folds=270' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=14400' 'max_retries=0' \
  'uses_realized_outcomes=false' 'effect_fields_inspected=false' \
  'treatment_constructed=true' 'production_change_licensed=false' \
  'historical_scoring_licensed=false' > "$MANIFEST"
: > "$EXECUTIONS"

launch_cell() {
  local season=$1 week=$2
  local job="stack-shell-scorefree-s${season}-w${week}-v1"
  local uri="$PREFIX/slate-${season}-${week}.json"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
    --max-retries 0 --task-timeout 4h --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" --command python \
    --args "scripts/run_stack_core_shell_scorefree.py,--season,$season,--week,$week,--output-uri,$uri,--support-uri,$SUPPORT_URI,--support-sha256,$SUPPORT_REPORT_SHA" \
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
  echo "ERROR: score-free launch grid is not 54" >&2; exit 2; }
printf '%s\n' \
  "released_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'primary_executions=54' 'released_after_canary=53' \
  "canary_completion_sha256=$(sha256sum "$OUT/canary-completion.txt" | awk '{print $1}')" \
  'object_content_inspected=false' 'effect_fields_inspected=false' \
  'treatment_constructed=true' > "$OUT/grid-release.txt"
sha256sum "$MANIFEST" > "$OUT/manifest.sha256"
sha256sum "$EXECUTIONS" > "$OUT/executions.sha256"
echo "STACK_CORE_SHELL_SCOREFREE_LAUNCHED $RUN_ID"
