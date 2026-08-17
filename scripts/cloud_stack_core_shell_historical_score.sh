#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_stack_core_shell_historical_score.sh <image@sha256:...> <code-sha> <build-id> <lock-report-sha256> <lock-completion-sha256>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-stack-core-shell-historical-score-v1
OUT="$ROOT/reports/stack-core-shell-historical-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/stack-core-shell-historical-runs/$RUN_ID
REPORT_URI=$PREFIX/report.json
LOCK_ID=20260816-stack-core-shell-production-lock-v1
LOCK="$ROOT/reports/stack-core-shell-lock-runs/$LOCK_ID"
LOCK_REPORT_URI=gs://nfl-predictions-503414-raw/research/stack-core-shell-lock-runs/$LOCK_ID/report.json
LOCK_COMPLETION_URI=gs://nfl-predictions-503414-raw/research/stack-core-shell-lock-runs/$LOCK_ID/completion.txt
PROTOCOL="$ROOT/reports/2026-08-16-stack-core-shell-historical-score-protocol.md"
PROTOCOL_SHA=f562ce6e9a7e0458a1fd3382692f6761f1d9de56edb06ab4350403584cd702fc
EXECUTION_PROTOCOL="$ROOT/reports/2026-08-16-stack-core-shell-historical-score-execution-protocol.md"
EXECUTION_PROTOCOL_SHA=ad3fe7e1045b61d4f64e21fee72c9f5d829fb7b2b4fb3854586e11641b458597
RUNNER="$ROOT/scripts/run_stack_core_shell_historical_score.py"
ATTEMPTS="$ROOT/scripts/manage_stack_core_shell_historical_score_attempt.py"
FINISHER="$ROOT/scripts/finish_stack_core_shell_historical_score.py"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}
LOCK_REPORT_SHA=${4:-}
LOCK_COMPLETION_SHA=${5:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable historical-score image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full historical-score source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful historical-score build ID is required" >&2; exit 2; }
[[ "$LOCK_REPORT_SHA" =~ ^[0-9a-f]{64}$ ]] && \
  [[ "$LOCK_COMPLETION_SHA" =~ ^[0-9a-f]{64}$ ]] || {
  echo "ERROR: strict production-lock hashes are required" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] && \
  [ "$(sha256sum "$EXECUTION_PROTOCOL" | awk '{print $1}')" = "$EXECUTION_PROTOCOL_SHA" ] || {
  echo "ERROR: frozen historical-score protocol differs" >&2; exit 2; }
for REQUIRED in "$LOCK/report.json" "$LOCK/completion.txt" \
  "$LOCK/report-upload.json" "$LOCK/completion-upload.json" \
  "$LOCK/accepted-executions.txt" "$LOCK/attempt-resolution.json"; do
  [ -s "$REQUIRED" ] || {
    echo "ERROR: strict production-lock harvest is incomplete: $REQUIRED" >&2; exit 2; }
done
[ "$(sha256sum "$LOCK/report.json" | awk '{print $1}')" = "$LOCK_REPORT_SHA" ] && \
  [ "$(sha256sum "$LOCK/completion.txt" | awk '{print $1}')" = "$LOCK_COMPLETION_SHA" ] || {
  echo "ERROR: strict production-lock hash differs" >&2; exit 2; }

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
  "$LOCK" "$LOCK_REPORT_URI" "$LOCK_COMPLETION_URI" \
  "$LOCK_REPORT_SHA" "$LOCK_COMPLETION_SHA" <<'PY'
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
resolution = json.loads((root / "attempt-resolution.json").read_text(encoding="utf-8"))
report_upload = json.loads((root / "report-upload.json").read_text(encoding="utf-8"))
completion_upload = json.loads(
    (root / "completion-upload.json").read_text(encoding="utf-8")
)
accepted_sha = sha256((root / "accepted-executions.txt").read_bytes()).hexdigest()
if report.get("version") != "stack-core-shell-production-lock-report-v1" or \
        report.get("run_id") != "20260816-stack-core-shell-production-lock-v1" or \
        report.get("uses_realized_outcomes") is not False or \
        report.get("actual_scores_queried") is not False or \
        report.get("production_change_licensed") is not False or \
        report.get("historical_scoring_licensed") is not True or \
        report.get("mechanical") != {
            "seasons": [2023, 2024, 2025], "slates": 54,
            "source_artifacts": 270, "all_valid": True,
            "rosters_locked_before_actual_query": True,
        } or len(report.get("locks", [])) != 54 or \
        len(report.get("artifact_receipts", [])) != 270:
    raise SystemExit("ERROR: historical-score production-lock license differs")
expected = {
    "run_id": "20260816-stack-core-shell-production-lock-v1",
    "report_sha256": report_sha,
    "accepted_execution_ledger_sha256": accepted_sha,
    "uses_realized_outcomes": "false", "actual_scores_queried": "false",
    "production_change_licensed": "false", "historical_scoring_licensed": "true",
    "rosters_locked_before_actual_query": "true",
}
if any(completion.get(key) != value for key, value in expected.items()) or \
        sha256((root / "completion.txt").read_bytes()).hexdigest() != completion_sha:
    raise SystemExit("ERROR: production-lock completion differs")
if resolution.get("disposition") not in {
    "accepted-primary-population", "accepted-population-with-platform-replacements",
} or resolution.get("accepted_execution_ledger_sha256") != accepted_sha:
    raise SystemExit("ERROR: production-lock accepted population differs")
for receipt, uri, digest in (
    (report_upload, report_uri, report_sha),
    (completion_upload, completion_uri, completion_sha),
):
    if receipt.get("uri") != uri or receipt.get("sha256") != digest or \
            not str(receipt.get("generation", "")).isdigit() or \
            int(receipt.get("bytes", 0)) <= 0:
        raise SystemExit("ERROR: production-lock upload receipt differs")
print("STACK_CORE_SHELL_HISTORICAL_LOCK_LICENSE_VALIDATED")
PY

git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}"
for RELATIVE in Dockerfile.stack-treatment cloudbuild.stack-treatment.yaml \
  reports/2026-08-16-stack-core-shell-historical-score-protocol.md \
  scripts/stack_core_shell_sources.py \
  scripts/run_stack_core_shell_historical_score.py \
  scripts/aggregate_stack_core_shell_production_locks.py \
  src/nfl_dfs/analysis/stack_core_shell_historical.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: historical-score built source differs: $RELATIVE" >&2; exit 2; }
done
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable historical-score run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: immutable historical-score cloud prefix exists" >&2; exit 3
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
required = {"full-test-suite", "build-image", "smoke-stack-core-shell-historical-scorer"}
if b.get("status") != "SUCCESS" or b.get("substitutions", {}).get("_IMAGE") != tag or \
        any(steps.get(name) != "SUCCESS" for name in required) or not any(
            row.get("name") == tag and row.get("digest") == digest
            for row in b.get("results", {}).get("images", [])
        ):
    raise SystemExit("ERROR: historical-score build identity differs")
PY

mkdir -p "$OUT"
mv "$BUILD_TMP" "$OUT/build-metadata.json"
trap - EXIT
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" "output_uri=$REPORT_URI" \
  "protocol_sha256=$PROTOCOL_SHA" \
  "execution_protocol_sha256=$EXECUTION_PROTOCOL_SHA" \
  "lock_report_uri=$LOCK_REPORT_URI" "lock_completion_uri=$LOCK_COMPLETION_URI" \
  "lock_report_sha256=$LOCK_REPORT_SHA" \
  "lock_completion_sha256=$LOCK_COMPLETION_SHA" \
  "lock_report_generation=$($ROOT/.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' "$LOCK/report-upload.json")" \
  "lock_completion_generation=$($ROOT/.venv/bin/python -c 'import json,sys; print(json.load(open(sys.argv[1]))["generation"])' "$LOCK/completion-upload.json")" \
  "lock_accepted_execution_ledger_sha256=$(sha256sum "$LOCK/accepted-executions.txt" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "attempt_manager_sha256=$(sha256sum "$ATTEMPTS" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$FINISHER" | awk '{print $1}')" \
  'tasks=1' 'parallelism=1' 'cpu=4' 'memory=16Gi' \
  'timeout_seconds=7200' 'max_retries=0' \
  'uses_realized_outcomes=true' 'actual_scores_queried=true' \
  'production_change_licensed=false' > "$MANIFEST"

JOB=stack-shell-historical-score-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
  --max-retries 0 --task-timeout 2h --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" --command python \
  --args "scripts/run_stack_core_shell_historical_score.py,--output-uri,$REPORT_URI,--lock-report-sha256,$LOCK_REPORT_SHA,--lock-completion-sha256,$LOCK_COMPLETION_SHA" \
  --quiet >/dev/null
EXECUTION=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[[ "$EXECUTION" == "$JOB-"* ]] || exit 2
printf '%s %s %s\n' "$JOB" "$EXECUTION" "$REPORT_URI" > "$EXECUTIONS"
sha256sum "$MANIFEST" > "$OUT/manifest.sha256"
sha256sum "$EXECUTIONS" > "$OUT/executions.sha256"
echo "STACK_CORE_SHELL_HISTORICAL_SCORE_LAUNCHED $EXECUTION"
