#!/usr/bin/env bash
set -euo pipefail

# Usage: cloud_constraint_lattice_support_census.sh <image@sha256:...> <code-sha> <build-id>

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-constraint-lattice-control-support-census-v1
OUT="$ROOT/reports/constraint-lattice-support-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/constraint-lattice-support-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-constraint-lattice-control-support-census-protocol.md"
PROTOCOL_SHA=11e97d5e94a11808b4838396c6fe59ff327a65a9ae260223138657db8d2a1a17
LATTICE_PROTOCOL="$ROOT/reports/2026-08-16-constraint-lattice-scorefree-protocol.md"
LATTICE_PROTOCOL_SHA=f8591d24dd56749e5b56235f9636687fd41bd1a78991fdb60cfbb092ee65bf62
SOURCE_AMENDMENT="$ROOT/reports/2026-08-16-constraint-lattice-source-and-execution-amendment.md"
SOURCE_AMENDMENT_SHA=35ea1f0dba3be5311631d51057c7667cb624bcdc19be75e2b202c57e297e8321
CBWU="$ROOT/reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json"
CBWU_SHA=556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33
RUNNER="$ROOT/scripts/run_constraint_lattice_support_census.py"
AGGREGATOR="$ROOT/scripts/aggregate_constraint_lattice_support_census.py"
PREFLIGHT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
REPAIR5="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"
PARITY="$ROOT/reports/atlas-interaction-parity-runs/20260816-atlas-interaction-parity-v1"
HISTORICAL="$ROOT/reports/atlas-historical-score-runs/20260816-atlas-historical-score-diagnostic-v3"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || {
  echo "ERROR: immutable lattice-support image is required" >&2; exit 2; }
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ERROR: full lattice-support source commit is required" >&2; exit 2; }
[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] || {
  echo "ERROR: successful lattice-support Cloud Build ID is required" >&2; exit 2; }
git -C "$ROOT" cat-file -e "$CODE_SHA^{commit}" || {
  echo "ERROR: lattice-support source commit is unavailable" >&2; exit 2; }
for RELATIVE in \
  Dockerfile cloudbuild.yaml \
  reports/2026-08-16-constraint-lattice-scorefree-protocol.md \
  reports/2026-08-16-constraint-lattice-source-and-execution-amendment.md \
  reports/2026-08-16-constraint-lattice-control-support-census-protocol.md \
  reports/cbwu-order-invariant-runs/20260815-cbwu-order-invariant-repair-v1/report.json \
  scripts/run_constraint_lattice_scorefree.py \
  scripts/aggregate_constraint_lattice_scorefree.py \
  scripts/run_constraint_lattice_support_census.py \
  scripts/aggregate_constraint_lattice_support_census.py \
  src/nfl_dfs/analysis/constraint_lattice.py \
  src/nfl_dfs/analysis/atlas_world_ranking.py \
  src/nfl_dfs/inference/multiseed_portfolio.py \
  src/nfl_dfs/optimizer/lineup.py; do
  CURRENT=$(sha256sum "$ROOT/$RELATIVE" | awk '{print $1}')
  BUILT=$(git -C "$ROOT" show "$CODE_SHA:$RELATIVE" | sha256sum | awk '{print $1}')
  [ "$CURRENT" = "$BUILT" ] || {
    echo "ERROR: lattice-support built source differs: $RELATIVE" >&2; exit 2; }
done
git -C "$ROOT" diff --quiet -- \
  Dockerfile cloudbuild.yaml \
  src/nfl_dfs/analysis/constraint_lattice.py \
  src/nfl_dfs/analysis/atlas_world_ranking.py \
  src/nfl_dfs/inference/multiseed_portfolio.py \
  src/nfl_dfs/optimizer/lineup.py \
  scripts/run_constraint_lattice_scorefree.py \
  scripts/aggregate_constraint_lattice_scorefree.py \
  scripts/run_constraint_lattice_support_census.py \
  scripts/aggregate_constraint_lattice_support_census.py || {
  echo "ERROR: lattice-support built sources have tracked edits" >&2; exit 2; }
for SPEC in "$PROTOCOL:$PROTOCOL_SHA" \
  "$LATTICE_PROTOCOL:$LATTICE_PROTOCOL_SHA" \
  "$SOURCE_AMENDMENT:$SOURCE_AMENDMENT_SHA" "$CBWU:$CBWU_SHA"; do
  FILE=${SPEC%:*}; DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: frozen lattice-support dependency differs: $FILE" >&2; exit 2; }
done
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable lattice-support local run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --project "$PROJECT" >/dev/null 2>&1; then
  echo "ERROR: immutable lattice-support cloud prefix exists" >&2; exit 3
fi

QUEUE_RELEASE=$(mktemp)
trap 'rm -f "$QUEUE_RELEASE"' EXIT
"$ROOT/.venv/bin/python" - "$PREFLIGHT" "$REPAIR5" "$PARITY" "$HISTORICAL" \
  "$QUEUE_RELEASE" <<'PY'
from hashlib import sha256
import json, pathlib, sys
preflight,repair5,parity,historical=(pathlib.Path(value) for value in sys.argv[1:5]); output=pathlib.Path(sys.argv[5])
def completion(path):
 p=path/"completion.txt"
 if not p.is_file(): return None
 return dict(line.split("=",1) for line in p.read_text().splitlines() if "=" in line)
def bind(paths):
 return {str(path):sha256(path.read_bytes()).hexdigest() for path in paths}
p=completion(preflight)
if p is None: raise SystemExit("ERROR: lattice support awaits ATLAS preflight")
files=[preflight/"completion.txt"]
if p.get("status")=="False":
 q=completion(parity)
 if q is None or q.get("status")!="True" or q.get("disposition") not in {"real-slate-parity-passes","real-slate-parity-fails"}:
  raise SystemExit("ERROR: lattice support awaits terminal continuous parity")
 files.append(parity/"completion.txt"); branch="preflight-failed-parity-closed"
elif p.get("status")=="True":
 r=completion(repair5)
 if r is not None:
  needed=[repair5/"completion.txt",repair5/"report.json",historical/"completion.txt",historical/"report.json"]
  if not all(path.is_file() for path in needed):
   raise SystemExit("ERROR: lattice support awaits repair5 historical closure")
  report=json.loads((historical/"report.json").read_text())
  if report.get("run_id")!="20260816-atlas-historical-score-diagnostic-v3" or report.get("uses_realized_outcomes") is not True:
   raise SystemExit("ERROR: lattice support historical identity differs")
  files.extend(needed); branch="repair5-valid-historical-closed"
 else:
  census=repair5/"terminal-census-completion.txt"; q=completion(parity)
  if not census.is_file() or q is None or q.get("status")!="True" or q.get("disposition") not in {"real-slate-parity-passes","real-slate-parity-fails"}:
   raise SystemExit("ERROR: lattice support awaits repair5-failure parity closure")
  files.extend([census,parity/"completion.txt"]); branch="repair5-failed-parity-closed"
else: raise SystemExit("ERROR: lattice support preflight completion differs")
output.write_text(json.dumps({"version":"constraint-lattice-support-queue-release-v1","branch":branch,"bindings":bind(files)},sort_keys=True,separators=(",",":"))+"\n")
PY

mkdir -p "$OUT"
mv "$QUEUE_RELEASE" "$OUT/queue-release.json"
trap - EXIT
gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format=json \
  > "$OUT/build-metadata.json"
"$ROOT/.venv/bin/python" - "$OUT/build-metadata.json" "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys
b=json.load(open(sys.argv[1],encoding="utf-8")); image=sys.argv[2]; code=sys.argv[3]
digest=image.rsplit("@",1)[1]
tag=f"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:constraint-support-{code[:7]}"
images=b.get("results",{}).get("images",[]); steps={row.get("id"):row.get("status") for row in b.get("steps",[])}
if b.get("status")!="SUCCESS" or b.get("substitutions",{}).get("_IMAGE")!=tag:
 raise SystemExit("ERROR: lattice-support build identity differs")
if not any(row.get("digest")==digest and row.get("name")==tag for row in images):
 raise SystemExit("ERROR: lattice-support image digest differs")
if steps.get("full-test-suite")!="SUCCESS" or steps.get("smoke-atlas-mvp-runner")!="SUCCESS":
 raise SystemExit("ERROR: lattice-support build steps differ")
PY

MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" "build_id=$BUILD_ID" \
  "output_prefix=$PREFIX" "protocol_sha256=$PROTOCOL_SHA" \
  "lattice_protocol_sha256=$LATTICE_PROTOCOL_SHA" \
  "source_amendment_sha256=$SOURCE_AMENDMENT_SHA" \
  "cbwu_report_sha256=$CBWU_SHA" \
  "runner_sha256=$(sha256sum "$RUNNER" | awk '{print $1}')" \
  "aggregator_sha256=$(sha256sum "$AGGREGATOR" | awk '{print $1}')" \
  "build_metadata_sha256=$(sha256sum "$OUT/build-metadata.json" | awk '{print $1}')" \
  "queue_release_sha256=$(sha256sum "$OUT/queue-release.json" | awk '{print $1}')" \
  "queue_release_branch=$("$ROOT/.venv/bin/python" -c 'import json,sys; print(json.load(open(sys.argv[1]))["branch"])' "$OUT/queue-release.json")" \
  'source_panels=20260813-sis-asoe-treatment-r0-v1,20260813-sis-asoe-treatment-r1-v1,20260813-sis-asoe-treatment-r2-v1,20260813-sis-asoe-treatment-r3-v1,20260813-sis-asoe-treatment-r4-v1' \
  'forensic_manifest_sha256=51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02' \
  'seasons=2023,2024,2025' 'weeks=1-18' 'slates=54' 'folds=270' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=7200' 'max_retries=0' \
  'aggregate_events_minimum_per_block=540' \
  'positive_slates_minimum_per_block=41' 'anchor_order=230,220,210' \
  'uses_realized_outcomes=false' 'effect_fields_inspected=false' \
  'treatment_constructed=false' 'production_change_licensed=false' \
  'historical_scoring_licensed=false' > "$MANIFEST"
: > "$EXECUTIONS"

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    JOB="constraint-support-s${SEASON}-w${WEEK}-v1"
    URI="$PREFIX/slate-${SEASON}-${WEEK}.json"
    gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --tasks 1 --parallelism 1 --cpu 4 --memory 16Gi \
      --max-retries 0 --task-timeout 2h --service-account "$SERVICE_ACCOUNT" \
      --set-env-vars "CODE_SHA=$CODE_SHA,ANALYSIS_IMAGE=$IMAGE" \
      --command python \
      --args "scripts/run_constraint_lattice_support_census.py,--season,$SEASON,--week,$WEEK,--output-uri,$URI" \
      --quiet >/dev/null
    EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" --region "$REGION" \
      --async --format='value(metadata.name)')
    [[ "$EXEC" == "$JOB-"* ]] || {
      echo "ERROR: lattice-support execution identity missing" >&2; exit 2; }
    printf '%s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" "$EXEC" "$URI" \
      >> "$EXECUTIONS"
  done
done
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ERROR: lattice-support launch grid is not 54" >&2; exit 2; }
sha256sum "$MANIFEST" > "$OUT/manifest.sha256"
sha256sum "$EXECUTIONS" > "$OUT/executions.sha256"
echo "CONSTRAINT_LATTICE_SUPPORT_LAUNCHED $RUN_ID"
