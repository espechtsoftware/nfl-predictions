#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_coherent_market_state_scorefree.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-coherent-market-state-scorefree-v1
OUT="$ROOT/reports/coherent-market-state-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/coherent-market-state-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-coherent-market-state-scorefree-protocol.md"
PROTOCOL_SHA=ddf40d804614aa3011604cda49c1c599309418fd7d0298a56529e87de4ef1208
SUPPORT="$ROOT/reports/2026-08-16-coherent-market-state-support-census.md"
SUPPORT_SHA=677171a16e339083b2eb1272926e9024ecab63b531ecc861d5237f94e61c0e63
EXECUTION_PROTOCOL="$ROOT/reports/2026-08-17-coherent-market-state-execution-protocol.md"
EXECUTION_PROTOCOL_SHA=0dd8175e88c9e01c29971663e0455f83b3d693c97b34f8bf8de2b2d054fafcbd
RUNNER="$ROOT/scripts/run_coherent_market_state_scorefree.py"
SOURCES="$ROOT/scripts/coherent_market_state_sources.py"
AGGREGATOR="$ROOT/scripts/aggregate_coherent_market_state_scorefree.py"
ATTEMPT_RESOLVER="$ROOT/scripts/cloud_prepare_coherent_market_state_attempts.sh"
ATTEMPT_VALIDATOR="$ROOT/scripts/validate_coherent_market_state_attempts.py"
CANARY_VALIDATOR="$ROOT/scripts/cloud_wait_coherent_market_state_canary.sh"
FINISHER="$ROOT/scripts/cloud_finish_coherent_market_state_scorefree.sh"
LAUNCHER="$ROOT/scripts/cloud_coherent_market_state_scorefree.sh"
WATCHER="$ROOT/scripts/watch_coherent_market_state_queue.sh"
PREFLIGHT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
REPAIR5="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"
PARITY="$ROOT/reports/atlas-interaction-parity-runs/20260816-atlas-interaction-parity-v1"
HISTORICAL="$ROOT/reports/atlas-historical-score-runs/20260816-atlas-historical-score-diagnostic-v3"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable coherent-state image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full coherent-state source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful coherent-state Cloud Build ID is required" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || {
  echo "ERROR: coherent-state source commit is unavailable" >&2; exit 2; }
for RELATIVE in \
  Dockerfile cloudbuild.yaml \
  reports/2026-08-16-coherent-market-state-scorefree-protocol.md \
  reports/2026-08-16-coherent-market-state-support-census.md \
  reports/2026-08-17-coherent-market-state-execution-protocol.md \
  scripts/coherent_market_state_sources.py \
  scripts/run_coherent_market_state_scorefree.py \
  scripts/aggregate_coherent_market_state_scorefree.py \
  scripts/cloud_coherent_market_state_scorefree.sh \
  scripts/cloud_prepare_coherent_market_state_attempts.sh \
  scripts/validate_coherent_market_state_attempts.py \
  scripts/cloud_wait_coherent_market_state_canary.sh \
  scripts/cloud_finish_coherent_market_state_scorefree.sh \
  scripts/watch_coherent_market_state_queue.sh \
  src/nfl_dfs/analysis/coherent_market_state.py \
  src/nfl_dfs/analysis/constraint_lattice.py \
  src/nfl_dfs/analysis/stack_core_shell.py \
  src/nfl_dfs/optimizer/lineup.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: coherent-state built source differs: $RELATIVE" >&2; exit 2; }
done
for SPEC in "$PROTOCOL:$PROTOCOL_SHA" "$SUPPORT:$SUPPORT_SHA" \
  "$EXECUTION_PROTOCOL:$EXECUTION_PROTOCOL_SHA"; do
  FILE=${SPEC%:*}; DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: frozen coherent-state dependency differs: $FILE" >&2; exit 2; }
done
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable coherent-state local run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: immutable coherent-state cloud prefix exists" >&2; exit 3
fi

QUEUE_RELEASE=$(mktemp)
trap 'rm -f "$QUEUE_RELEASE"' EXIT
"$ROOT/.venv/bin/python" - "$PREFLIGHT" "$REPAIR5" "$PARITY" "$HISTORICAL" \
  "$QUEUE_RELEASE" <<'PY'
from hashlib import sha256
import json, pathlib, sys
preflight, repair5, parity, historical = (pathlib.Path(value) for value in sys.argv[1:5])
output = pathlib.Path(sys.argv[5])
def completion(path):
    target = path / "completion.txt"
    if not target.is_file():
        return None
    return dict(line.split("=", 1) for line in target.read_text().splitlines() if "=" in line)
def bind(paths):
    return {str(path): sha256(path.read_bytes()).hexdigest() for path in paths}
p = completion(preflight)
if p is None:
    raise SystemExit("ERROR: coherent-state queue awaits ATLAS preflight")
files = [preflight / "completion.txt"]
if p.get("status") == "False":
    q = completion(parity)
    if q is None or q.get("status") != "True":
        raise SystemExit("ERROR: coherent-state queue awaits continuous parity closure")
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
            raise SystemExit("ERROR: coherent-state queue awaits repair5 historical closure")
        report = json.loads((historical / "report.json").read_text())
        if report.get("run_id") != "20260816-atlas-historical-score-diagnostic-v3" or \
                report.get("uses_realized_outcomes") is not True:
            raise SystemExit("ERROR: coherent-state historical closure identity differs")
        files.extend(needed)
        branch = "repair5-valid-historical-closed"
    else:
        census = repair5 / "terminal-census-completion.txt"
        q = completion(parity)
        if not census.is_file() or q is None or q.get("status") != "True":
            raise SystemExit("ERROR: coherent-state queue awaits repair5-failure parity closure")
        files.extend([census, parity / "completion.txt"])
        branch = "repair5-failed-parity-closed"
else:
    raise SystemExit("ERROR: coherent-state preflight completion differs")
output.write_text(json.dumps({
    "version": "coherent-market-state-queue-release-v1",
    "branch": branch, "bindings": bind(files),
}, sort_keys=True, separators=(",", ":")) + "\n")
PY

mkdir -p "$OUT"
mv "$QUEUE_RELEASE" "$OUT/queue-release.json"
trap - EXIT
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json \
  > "$OUT/build-metadata.json"
"$ROOT/.venv/bin/python" - "$OUT/build-metadata.json" "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys
b = json.load(open(sys.argv[1], encoding="utf-8"))
image, code = sys.argv[2:]
digest = image.rsplit("@", 1)[1]
tag = f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:coherent-market-state-{code[:7]}"
images = b.get("results", {}).get("images", [])
steps = {row.get("id"): row.get("status") for row in b.get("steps", [])}
if b.get("status") != "SUCCESS" or b.get("substitutions", {}).get("_IMAGE") != tag:
    raise SystemExit("ERROR: coherent-state validation build identity differs")
if not any(row.get("digest") == digest and row.get("name") == tag for row in images):
    raise SystemExit("ERROR: coherent-state validation image digest differs")
if steps.get("full-test-suite") != "SUCCESS" or \
        steps.get("smoke-atlas-mvp-runner") != "SUCCESS":
    raise SystemExit("ERROR: coherent-state validation steps differ")
PY

MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "build_id=$BUILD_ID" "output_prefix=$PREFIX" \
  "protocol_sha256=$PROTOCOL_SHA" "support_sha256=$SUPPORT_SHA" \
  "execution_protocol_sha256=$EXECUTION_PROTOCOL_SHA" \
  "source_loader_sha256=$(sha256sum "$SOURCES" | awk '{print $1}')" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "aggregator_sha256=$(sha256sum "$AGGREGATOR" | awk '{print $1}')" \
  "attempt_resolver_sha256=$(sha256sum "$ATTEMPT_RESOLVER" | awk '{print $1}')" \
  "attempt_validator_sha256=$(sha256sum "$ATTEMPT_VALIDATOR" | awk '{print $1}')" \
  "canary_validator_sha256=$(sha256sum "$CANARY_VALIDATOR" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$FINISHER" | awk '{print $1}')" \
  "launcher_sha256=$(sha256sum "$LAUNCHER" | awk '{print $1}')" \
  "watcher_sha256=$(sha256sum "$WATCHER" | awk '{print $1}')" \
  "build_metadata_sha256=$(sha256sum "$OUT/build-metadata.json" | awk '{print $1}')" \
  "queue_release_sha256=$(sha256sum "$OUT/queue-release.json" | awk '{print $1}')" \
  'source_panels=20260815-atlas-money-worlds-r0-v1,20260815-atlas-money-worlds-r1-v1,20260815-atlas-money-worlds-r2-v1,20260815-atlas-money-worlds-r3-v1,20260815-atlas-money-worlds-r4-v1' \
  'repair_panel=20260816-atlas-mvp-repair-r3-2025-v1' \
  'seasons=2023,2024,2025' 'weeks=1-18' 'slates=54' 'folds=270' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=14400' 'max_retries=0' \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  'historical_scoring_licensed=false' > "$MANIFEST"
: > "$EXECUTIONS"

deploy_cell() {
  local season=$1 week=$2
  local job="coherent-state-s${season}-w${week}-v1"
  local uri="$PREFIX/slate-${season}-${week}.json"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
    --max-retries 0 --task-timeout 4h --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
    --command python \
    --args "scripts/run_coherent_market_state_scorefree.py,--season,$season,--week,$week,--output-uri,$uri" \
    --quiet >/dev/null
  local execution
  execution=$(gcloud run jobs execute "$job" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [[ "$execution" == "$job-"* ]] || {
    echo "ERROR: coherent-state execution identity missing" >&2; exit 2; }
  printf '%s %s %s %s %s\n' "$season" "$week" "$job" "$execution" "$uri" \
    >> "$EXECUTIONS"
}

deploy_cell 2023 1
bash "$CANARY_VALIDATOR"
"$ROOT/.venv/bin/python" - "$OUT/canary-completion.txt" \
  "$OUT/canary-execution-metadata.json" "$OUT/canary-object-metadata.json" \
  "$OUT/grid-release.pending.txt" <<'PY'
from hashlib import sha256
from pathlib import Path
import sys
completion, execution, object_meta, target = map(Path, sys.argv[1:])
c = dict(line.split("=", 1) for line in completion.read_text().splitlines() if "=" in line)
if c.get("status") != "True" or c.get("disposition") != "real-path-canary-passes" or \
        c.get("cell") != "2023-1" or c.get("object_content_inspected") != "false":
    raise SystemExit("ERROR: coherent-state canary does not license grid")
target.write_text("\n".join([
    "primary_executions=54", "released_after_canary=53",
    f"canary_completion_sha256={sha256(completion.read_bytes()).hexdigest()}",
    f"canary_execution_metadata_sha256={sha256(execution.read_bytes()).hexdigest()}",
    f"canary_object_metadata_sha256={sha256(object_meta.read_bytes()).hexdigest()}",
    "object_content_inspected=false", "effect_fields_inspected=false",
]) + "\n")
PY
mv "$OUT/grid-release.pending.txt" "$OUT/grid-release.txt"

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    [ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && continue
    deploy_cell "$SEASON" "$WEEK"
  done
done
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: coherent-state execution population is incomplete" >&2; exit 2; }
sha256sum "$MANIFEST" "$EXECUTIONS" "$OUT/grid-release.txt" \
  > "$OUT/launch.sha256"
echo "COHERENT_MARKET_STATE_GRID_LAUNCHED $RUN_ID"
