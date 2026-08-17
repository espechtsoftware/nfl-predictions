#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_stack_core_shell_support_census.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-stack-core-shell-control-support-census-v1
OUT="$ROOT/reports/stack-core-shell-support-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/stack-core-shell-support-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-stack-core-shell-scorefree-protocol.md"
PROTOCOL_SHA=edd13697fd3d7fc787d159c74d6e8280bf1b51517dcdbacc8337011a01cd5d46
EXECUTION_PROTOCOL="$ROOT/reports/2026-08-16-stack-core-shell-support-execution-protocol.md"
EXECUTION_PROTOCOL_SHA=d2e902611e070ef67c191dffd35d86fd0c81365126eb86dcae7b9640aede1cc3
TRANSFER="$ROOT/reports/atlas-money-transfer-runs/20260815-atlas-current-money-transfer-v1/report.json"
TRANSFER_SHA=8e568f8e5e343319ab4e4f48421b41f3266e56ecb592abce77f3ed6d246cd446
CBWU="$ROOT/reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json"
CBWU_SHA=556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33
RUNNER="$ROOT/scripts/run_stack_core_shell_support_census.py"
AGGREGATOR="$ROOT/scripts/aggregate_stack_core_shell_support_census.py"
SOURCES="$ROOT/scripts/stack_core_shell_sources.py"
CANARY="$ROOT/scripts/cloud_wait_stack_core_shell_support_canary.sh"
ATTEMPTS="$ROOT/scripts/manage_stack_core_shell_support_attempts.py"
PREFLIGHT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
REPAIR5="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"
PARITY="$ROOT/reports/atlas-interaction-parity-runs/20260816-atlas-interaction-parity-v1"
HISTORICAL="$ROOT/reports/atlas-historical-score-runs/20260816-atlas-historical-score-diagnostic-v3"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable stack-core/shell support image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full stack-core/shell source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful stack-core/shell Cloud Build ID is required" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || {
  echo "ERROR: stack-core/shell source commit is unavailable" >&2; exit 2; }
for RELATIVE in \
  Dockerfile.stack-support cloudbuild.stack-support.yaml \
  reports/2026-08-16-stack-core-shell-scorefree-protocol.md \
  reports/2026-08-16-stack-core-shell-support-execution-protocol.md \
  reports/atlas-money-transfer-runs/20260815-atlas-current-money-transfer-v1/report.json \
  reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json \
  reports/atlas-mvp-source-repair-runs/20260816-atlas-mvp-source-repair-r3-2025-v1/validation.json \
  reports/atlas-mvp-source-repair-runs/20260816-atlas-mvp-source-repair-r3-2025-v1/execution.json \
  reports/atlas-mvp-source-repair-runs/20260816-atlas-mvp-source-repair-r3-2025-v1/completion.txt \
  scripts/stack_core_shell_sources.py \
  scripts/run_stack_core_shell_support_census.py \
  scripts/aggregate_stack_core_shell_support_census.py \
  scripts/cloud_wait_stack_core_shell_support_canary.sh \
  scripts/manage_stack_core_shell_support_attempts.py \
  src/nfl_dfs/analysis/stack_core_shell.py \
  src/nfl_dfs/analysis/constraint_lattice.py \
  src/nfl_dfs/analysis/atlas_matched_diversity.py \
  src/nfl_dfs/inference/multiseed_portfolio.py \
  src/nfl_dfs/optimizer/lineup.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: stack-core/shell built source differs: $RELATIVE" >&2; exit 2; }
done
git -C "$ROOT" diff --quiet -- \
  Dockerfile.stack-support cloudbuild.stack-support.yaml \
  reports/2026-08-16-stack-core-shell-scorefree-protocol.md \
  reports/2026-08-16-stack-core-shell-support-execution-protocol.md \
  scripts/stack_core_shell_sources.py \
  scripts/run_stack_core_shell_support_census.py \
  scripts/aggregate_stack_core_shell_support_census.py \
  scripts/cloud_wait_stack_core_shell_support_canary.sh \
  scripts/manage_stack_core_shell_support_attempts.py \
  src/nfl_dfs/analysis/stack_core_shell.py || {
  echo "ERROR: stack-core/shell built sources have tracked edits" >&2; exit 2; }
for SPEC in "$PROTOCOL:$PROTOCOL_SHA" \
  "$EXECUTION_PROTOCOL:$EXECUTION_PROTOCOL_SHA" \
  "$TRANSFER:$TRANSFER_SHA" "$CBWU:$CBWU_SHA"; do
  FILE=${SPEC%:*}; DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: frozen stack-core/shell dependency differs: $FILE" >&2; exit 2; }
done
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable stack-core/shell support run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: immutable stack-core/shell cloud prefix exists" >&2; exit 3
fi

QUEUE_RELEASE=$(mktemp)
trap 'rm -f "$QUEUE_RELEASE"' EXIT
"$ROOT/.venv/bin/python" - "$PREFLIGHT" "$REPAIR5" "$PARITY" "$HISTORICAL" \
  "$QUEUE_RELEASE" <<'PY'
from hashlib import sha256
import json
from pathlib import Path
import sys

preflight, repair5, parity, historical = (Path(value) for value in sys.argv[1:5])
output = Path(sys.argv[5])
def completion(path):
    target = path / "completion.txt"
    if not target.is_file():
        return None
    return dict(
        line.split("=", 1) for line in target.read_text().splitlines() if "=" in line
    )
def bind(paths):
    return {str(path): sha256(path.read_bytes()).hexdigest() for path in paths}
p = completion(preflight)
if p is None:
    raise SystemExit("ERROR: stack-core/shell support awaits ATLAS preflight")
files = [preflight / "completion.txt"]
if p.get("status") == "False":
    q = completion(parity)
    if q is None or q.get("status") != "True" or q.get("disposition") not in {
        "real-slate-parity-passes", "real-slate-parity-fails",
    }:
        raise SystemExit("ERROR: stack-core/shell support awaits terminal parity")
    files.append(parity / "completion.txt")
    branch = "preflight-failed-parity-closed"
elif p.get("status") == "True":
    r = completion(repair5)
    if r is not None:
        needed = [
            repair5 / "completion.txt", repair5 / "report.json",
            historical / "completion.txt", historical / "report.json",
        ]
        if not all(path.is_file() for path in needed):
            raise SystemExit("ERROR: stack-core/shell support awaits ATLAS history")
        report = json.loads((historical / "report.json").read_text())
        if report.get("run_id") != "20260816-atlas-historical-score-diagnostic-v3" or \
                report.get("uses_realized_outcomes") is not True:
            raise SystemExit("ERROR: stack-core/shell historical identity differs")
        files.extend(needed)
        branch = "repair5-valid-historical-closed"
    else:
        census = repair5 / "terminal-census-completion.txt"
        q = completion(parity)
        if not census.is_file() or q is None or q.get("status") != "True" or \
                q.get("disposition") not in {
                    "real-slate-parity-passes", "real-slate-parity-fails",
                }:
            raise SystemExit("ERROR: stack-core/shell awaits ATLAS failure closure")
        files.extend([census, parity / "completion.txt"])
        branch = "repair5-failed-parity-closed"
else:
    raise SystemExit("ERROR: stack-core/shell preflight completion differs")
output.write_text(json.dumps({
    "version": "stack-core-shell-support-queue-release-v1",
    "branch": branch,
    "bindings": bind(files),
}, sort_keys=True, separators=(",", ":")) + "\n")
PY

mkdir -p "$OUT"
mv "$QUEUE_RELEASE" "$OUT/queue-release.json"
trap - EXIT
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --region "$REGION" \
  --format=json \
  > "$OUT/build-metadata.json"
"$ROOT/.venv/bin/python" - "$OUT/build-metadata.json" "$IMAGE" "$CODE_SHA" <<'PY'
import json
import sys
b = json.load(open(sys.argv[1], encoding="utf-8"))
image, code = sys.argv[2:]
digest = image.rsplit("@", 1)[1]
tag = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:"
    f"stack-shell-support-{code[:7]}"
)
images = b.get("results", {}).get("images", [])
steps = {row.get("id"): row.get("status") for row in b.get("steps", [])}
if b.get("status") != "SUCCESS" or b.get("substitutions", {}).get("_IMAGE") != tag:
    raise SystemExit("ERROR: stack-core/shell build identity differs")
if not any(row.get("digest") == digest and row.get("name") == tag for row in images):
    raise SystemExit("ERROR: stack-core/shell image digest differs")
required = {
    "full-test-suite", "smoke-stack-core-shell-source-loader",
    "smoke-stack-core-shell-support-runner",
    "smoke-stack-core-shell-support-aggregator",
}
if any(steps.get(name) != "SUCCESS" for name in required):
    raise SystemExit("ERROR: stack-core/shell build steps differ")
PY

MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" "protocol_sha256=$PROTOCOL_SHA" \
  "execution_protocol_sha256=$EXECUTION_PROTOCOL_SHA" \
  "transfer_report_sha256=$TRANSFER_SHA" "cbwu_report_sha256=$CBWU_SHA" \
  "source_loader_sha256=$(sha256sum "$SOURCES" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "aggregator_sha256=$(sha256sum "$AGGREGATOR" | awk '{print $1}')" \
  "canary_validator_sha256=$(sha256sum "$CANARY" | awk '{print $1}')" \
  "attempt_manager_sha256=$(sha256sum "$ATTEMPTS" | awk '{print $1}')" \
  "build_metadata_sha256=$(sha256sum "$OUT/build-metadata.json" | awk '{print $1}')" \
  "queue_release_sha256=$(sha256sum "$OUT/queue-release.json" | awk '{print $1}')" \
  "queue_release_branch=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["branch"])' "$OUT/queue-release.json")" \
  'source_panels=20260815-atlas-money-worlds-r0-v1,20260815-atlas-money-worlds-r1-v1,20260815-atlas-money-worlds-r2-v1,20260815-atlas-money-worlds-r3-v1,20260815-atlas-money-worlds-r4-v1' \
  'seasons=2023,2024,2025' 'weeks=1-18' 'slates=54' 'folds=270' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=7200' 'max_retries=0' \
  'aggregate_events_minimum_per_block=540' \
  'positive_slates_minimum_per_block=41' 'anchor_order=230,220,210' \
  'support_layers=candidate,selected' \
  'uses_realized_outcomes=false' 'effect_fields_inspected=false' \
  'treatment_constructed=false' 'production_change_licensed=false' \
  'historical_scoring_licensed=false' > "$MANIFEST"
: > "$EXECUTIONS"

SEASON=2023
WEEK=1
JOB="stack-shell-support-s${SEASON}-w${WEEK}-v1"
URI="$PREFIX/slate-${SEASON}-${WEEK}.json"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
  --max-retries 0 --task-timeout 2h --service-account "$SERVICE_ACCOUNT" \
  --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
  --command python \
  --args "scripts/run_stack_core_shell_support_census.py,--season,$SEASON,--week,$WEEK,--output-uri,$URI" \
  --quiet >/dev/null
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
  --async --format='value(metadata.name)')
[[ "$EXEC" == "$JOB-"* ]] || {
  echo "ERROR: stack-core/shell canary execution identity missing" >&2; exit 2; }
printf '%s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" "$EXEC" "$URI" \
  >> "$EXECUTIONS"
bash "$CANARY"

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    [ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && continue
    JOB="stack-shell-support-s${SEASON}-w${WEEK}-v1"
    URI="$PREFIX/slate-${SEASON}-${WEEK}.json"
    gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
      --max-retries 0 --task-timeout 2h --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
      --command python \
      --args "scripts/run_stack_core_shell_support_census.py,--season,$SEASON,--week,$WEEK,--output-uri,$URI" \
      --quiet >/dev/null
    EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
      --async --format='value(metadata.name)')
    [[ "$EXEC" == "$JOB-"* ]] || {
      echo "ERROR: stack-core/shell execution identity missing" >&2; exit 2; }
    printf '%s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" "$EXEC" "$URI" \
      >> "$EXECUTIONS"
  done
done
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: stack-core/shell support launch grid is not 54" >&2; exit 2; }
printf '%s\n' \
  "released_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'primary_executions=54' 'released_after_canary=53' \
  "canary_completion_sha256=$(sha256sum "$OUT/canary-completion.txt" | awk '{print $1}')" \
  'object_content_inspected=false' 'effect_fields_inspected=false' \
  'treatment_constructed=false' > "$OUT/grid-release.txt"
sha256sum "$MANIFEST" > "$OUT/manifest.sha256"
sha256sum "$EXECUTIONS" > "$OUT/executions.sha256"
echo "STACK_CORE_SHELL_SUPPORT_LAUNCHED $RUN_ID"
