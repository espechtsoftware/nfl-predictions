#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_recourse_aware_initial_scorefree.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-recourse-aware-initial-book-scorefree-v1
OUT="$ROOT/reports/recourse-aware-initial-book-runs/$RUN_ID"
PREFIX="gs://nfl-predictions-503414-raw/research/recourse-aware-initial-book-runs/$RUN_ID"
SCIENCE="$ROOT/reports/2026-08-17-recourse-aware-initial-book-scorefree-protocol.md"
SCIENCE_SHA=0085b5f77b4e859982fc4f664161cdafe2bb6ec07ea0351fb618ddf58319c077
EXECUTION="$ROOT/reports/2026-08-17-recourse-aware-initial-book-execution-protocol.md"
EXECUTION_SHA=3991fdbf36c2018b2ec11625a6be62990c100fdf1f47bde3985c2327e3248c9b
CBWU="$ROOT/reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json"
CBWU_SHA=556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33
RUNNER="$ROOT/scripts/run_recourse_aware_initial_scorefree.py"
AGGREGATOR="$ROOT/scripts/aggregate_recourse_aware_initial_scorefree.py"
CANARY_WAITER="$ROOT/scripts/cloud_wait_recourse_aware_initial_canary.sh"
CANARY_VALIDATOR="$ROOT/scripts/validate_recourse_aware_initial_canary.py"
PREFLIGHT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
REPAIR5="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"
PARITY="$ROOT/reports/atlas-interaction-parity-runs/20260816-atlas-interaction-parity-v1"
HISTORICAL="$ROOT/reports/atlas-historical-score-runs/20260816-atlas-historical-score-diagnostic-v3"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable recourse-aware image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full recourse-aware source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful recourse-aware Cloud Build ID is required" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || {
  echo "ERROR: recourse-aware source commit is unavailable" >&2; exit 2; }
for RELATIVE in \
  Dockerfile cloudbuild.yaml \
  reports/2026-08-17-recourse-aware-initial-book-scorefree-protocol.md \
  reports/2026-08-17-recourse-aware-initial-book-execution-protocol.md \
  reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json \
  src/nfl_dfs/analysis/recourse_aware_initial.py \
  scripts/run_recourse_aware_initial_scorefree.py \
  scripts/aggregate_recourse_aware_initial_scorefree.py \
  scripts/validate_recourse_aware_initial_canary.py \
  scripts/cloud_wait_recourse_aware_initial_canary.sh \
  scripts/cloud_recourse_aware_initial_scorefree.sh \
  scripts/cloud_finish_recourse_aware_initial_scorefree.sh \
  scripts/watch_recourse_aware_initial_queue.sh; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: recourse-aware built source differs: $RELATIVE" >&2; exit 2; }
done
git -C "$ROOT" diff --quiet -- \
  Dockerfile cloudbuild.yaml \
  src/nfl_dfs/analysis/recourse_aware_initial.py \
  scripts/run_recourse_aware_initial_scorefree.py \
  scripts/aggregate_recourse_aware_initial_scorefree.py \
  scripts/validate_recourse_aware_initial_canary.py \
  scripts/cloud_wait_recourse_aware_initial_canary.sh \
  scripts/cloud_recourse_aware_initial_scorefree.sh \
  scripts/cloud_finish_recourse_aware_initial_scorefree.sh \
  scripts/watch_recourse_aware_initial_queue.sh || {
  echo "ERROR: recourse-aware built sources have tracked edits" >&2; exit 2; }
for SPEC in "$SCIENCE:$SCIENCE_SHA" "$EXECUTION:$EXECUTION_SHA" "$CBWU:$CBWU_SHA"; do
  FILE=${SPEC%:*}; DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: frozen recourse-aware dependency differs: $FILE" >&2; exit 2; }
done
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable recourse-aware local run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: immutable recourse-aware cloud prefix exists" >&2; exit 3
fi

QUEUE_RELEASE=$(mktemp)
trap 'rm -f "$QUEUE_RELEASE"' EXIT
"$ROOT/.venv/bin/python" - "$PREFLIGHT" "$REPAIR5" "$PARITY" \
  "$HISTORICAL" "$QUEUE_RELEASE" <<'PY'
from hashlib import sha256
import json, pathlib, sys
preflight,repair5,parity,historical=(pathlib.Path(value) for value in sys.argv[1:5])
output=pathlib.Path(sys.argv[5])
def completion(path):
 p=path/"completion.txt"
 if not p.is_file(): return None
 return dict(line.split("=",1) for line in p.read_text().splitlines() if "=" in line)
def bind(paths):
 return {str(path):sha256(path.read_bytes()).hexdigest() for path in paths}
p=completion(preflight); files=[preflight/"completion.txt"]; branch=None
if p is None: raise SystemExit("ERROR: recourse-aware queue awaits ATLAS preflight")
if p.get("status")=="False":
 q=completion(parity)
 if q is None or q.get("status")!="True" or q.get("disposition") not in {"real-slate-parity-passes","real-slate-parity-fails"}:
  raise SystemExit("ERROR: recourse-aware queue awaits terminal ATLAS parity")
 files.append(parity/"completion.txt"); branch="preflight-failed-parity-closed"
elif p.get("status")=="True":
 r=completion(repair5)
 if r is not None:
  needed=[repair5/"completion.txt",repair5/"report.json",historical/"completion.txt",historical/"report.json"]
  if not all(path.is_file() for path in needed):
   raise SystemExit("ERROR: recourse-aware queue awaits ATLAS historical closure")
  report=json.loads((historical/"report.json").read_text())
  if report.get("run_id")!="20260816-atlas-historical-score-diagnostic-v3" or report.get("uses_realized_outcomes") is not True:
   raise SystemExit("ERROR: recourse-aware ATLAS historical identity differs")
  files.extend(needed); branch="repair5-valid-historical-closed"
 else:
  census=repair5/"terminal-census-completion.txt"; q=completion(parity)
  if not census.is_file() or q is None or q.get("status")!="True" or q.get("disposition") not in {"real-slate-parity-passes","real-slate-parity-fails"}:
   raise SystemExit("ERROR: recourse-aware queue awaits repair5 failure closure")
  files.extend([census,parity/"completion.txt"]); branch="repair5-failed-parity-closed"
else: raise SystemExit("ERROR: recourse-aware ATLAS preflight completion differs")
output.write_text(json.dumps({"version":"recourse-aware-queue-release-v1","branch":branch,"bindings":bind(files)},sort_keys=True,separators=(",",":"))+"\n")
PY

mkdir -p "$OUT"
mv "$QUEUE_RELEASE" "$OUT/queue-release.json"
trap - EXIT
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json \
  > "$OUT/build-metadata.json"
"$ROOT/.venv/bin/python" - "$OUT/build-metadata.json" "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys
b=json.load(open(sys.argv[1])); image=sys.argv[2]; code=sys.argv[3]
digest=image.rsplit("@",1)[1]
tag=f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:recourse-initial-{code[:7]}"
images=b.get("results",{}).get("images",[]); steps={row.get("id"):row.get("status") for row in b.get("steps",[])}
if b.get("status")!="SUCCESS" or b.get("substitutions",{}).get("_IMAGE")!=tag or not any(row.get("digest")==digest and row.get("name")==tag for row in images) or steps.get("full-test-suite")!="SUCCESS" or steps.get("smoke-atlas-mvp-runner")!="SUCCESS":
 raise SystemExit("ERROR: recourse-aware validation build identity differs")
PY

MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "build_id=$BUILD_ID" "output_prefix=$PREFIX" \
  "science_protocol_sha256=$SCIENCE_SHA" \
  "execution_protocol_sha256=$EXECUTION_SHA" \
  "cbwu_report_sha256=$CBWU_SHA" \
  'forensic_manifest_sha256=51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02' \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "aggregator_sha256=$(sha256sum "$AGGREGATOR" | awk '{print $1}')" \
  "canary_waiter_sha256=$(sha256sum "$CANARY_WAITER" | awk '{print $1}')" \
  "canary_validator_sha256=$(sha256sum "$CANARY_VALIDATOR" | awk '{print $1}')" \
  "launcher_sha256=$(sha256sum "$ROOT/scripts/cloud_recourse_aware_initial_scorefree.sh" | awk '{print $1}')" \
  "finisher_sha256=$(sha256sum "$ROOT/scripts/cloud_finish_recourse_aware_initial_scorefree.sh" | awk '{print $1}')" \
  "watcher_sha256=$(sha256sum "$ROOT/scripts/watch_recourse_aware_initial_queue.sh" | awk '{print $1}')" \
  "build_metadata_sha256=$(sha256sum "$OUT/build-metadata.json" | awk '{print $1}')" \
  "queue_release_sha256=$(sha256sum "$OUT/queue-release.json" | awk '{print $1}')" \
  "queue_release_branch=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["branch"])' "$OUT/queue-release.json")" \
  'source_panels=20260813-sis-asoe-treatment-r0-v1,20260813-sis-asoe-treatment-r1-v1,20260813-sis-asoe-treatment-r2-v1,20260813-sis-asoe-treatment-r3-v1,20260813-sis-asoe-treatment-r4-v1' \
  'seasons=2023,2024,2025' 'weeks=1-18' 'slates=54' 'folds=270' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=14400' 'max_retries=0' \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  'historical_scoring_licensed=false' > "$MANIFEST"
: > "$EXECUTIONS"

deploy_and_run() {
  local season=$1 week=$2
  local job="recourse-initial-s${season}-w${week}-v1"
  local uri="$PREFIX/slate-${season}-${week}.json"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
    --max-retries 0 --task-timeout 4h --service-account "$SERVICE_ACCOUNT" \
    --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
    --command python \
    --args "scripts/run_recourse_aware_initial_scorefree.py,--season,$season,--week,$week,--output-uri,$uri" \
    --quiet >/dev/null
  local execution
  execution=$(gcloud run jobs execute "$job" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [[ "$execution" == "$job-"* ]] || {
    echo "ERROR: recourse-aware execution identity missing" >&2; exit 2; }
  printf '%s %s %s %s %s\n' "$season" "$week" "$job" "$execution" "$uri" \
    >> "$EXECUTIONS"
}

deploy_and_run 2023 1
"$CANARY_WAITER"
"$ROOT/.venv/bin/python" - "$OUT/canary-completion.json" <<'PY'
import json,sys
r=json.load(open(sys.argv[1]))
if r.get("status") is not True or r.get("disposition")!="actual-final-path-canary-passes" or r.get("remaining_cells_released") is not False:
 raise SystemExit("ERROR: recourse-aware canary did not license release")
PY
for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    [ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && continue
    deploy_and_run "$SEASON" "$WEEK"
  done
done
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: recourse-aware launch grid is not 54" >&2; exit 2; }
printf '%s\n' \
  "released_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'primary_executions=54' 'released_after_canary=53' \
  "canary_completion_sha256=$(sha256sum "$OUT/canary-completion.json" | awk '{print $1}')" \
  "canary_object_sha256=$(sha256sum "$OUT/canary-shard.json" | awk '{print $1}')" \
  'outcome_fields_inspected=false' 'effect_fields_inspected=false' \
  > "$OUT/grid-release.txt"
sha256sum "$MANIFEST" > "$OUT/manifest.sha256"
sha256sum "$EXECUTIONS" > "$OUT/executions.sha256"
echo "RECOURSE_INITIAL_LAUNCHED $RUN_ID"
