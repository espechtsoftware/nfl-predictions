#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-interaction-parity-v1
OUT="$ROOT/reports/atlas-interaction-parity-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-interaction-parity-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-atlas-continuous-interaction-parity-protocol.md"
PROTOCOL_SHA=0d925bc4c5fd03ca01b53ec2e2d0bdf10e48ca66f959a723aedf28ad636678a1
BUILD_REPAIR="$ROOT/reports/2026-08-16-atlas-continuous-build-path-repair.md"
BUILD_REPAIR_SHA=2a3a02f00e2a78b862647aa30da251fab27366181522b5849859b6f770acf5dc
BUILD_RECEIPT="$OUT/build-receipt.txt"
BUILD_RECEIPT_SHA=a3c7032e25bc6bcdcddcd8096d5b08436aa36bf52002298a369d025ba6b78ccf
SOURCE="$ROOT/scripts/run_atlas_interaction_parity_diagnostic.py"
SOURCE_SHA=f8b5b54ce3aab95be36d32bdb3825f2c0b34ed9552c7ebaf0085f0e5f0fb1d2d
RUNNER="$ROOT/scripts/run_atlas_matched_diversity_mvp.py"
RUNNER_SHA=0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740
OPTIMIZER="$ROOT/src/nfl_dfs/optimizer/lineup.py"
OPTIMIZER_SHA=ba5ac3a7c9eb5d436fa6b319e13104b10281fee640c64377904d56c93db65de6
IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:437641a46e1c952ec2f1628428904c89fb4f8eef3d2a2c42a52262c45817231f
CODE_SHA=06797314a0ed423b9f5783fc926b269c1fb24371
BUILD_ID=9e8347a9-7fe1-460f-a0d6-9ba379616b52
PREFLIGHT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"

for SPEC in "$PROTOCOL:$PROTOCOL_SHA" "$BUILD_REPAIR:$BUILD_REPAIR_SHA" \
  "$BUILD_RECEIPT:$BUILD_RECEIPT_SHA" "$SOURCE:$SOURCE_SHA" \
  "$RUNNER:$RUNNER_SHA" "$OPTIMIZER:$OPTIMIZER_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: ATLAS interaction-parity frozen source differs: $FILE" >&2
    exit 2
  }
done

# This launcher is the frozen fallback for a failed binary 32-GiB preflight.
# A successful or nonterminal binary preflight keeps repair5 ahead in the queue.
for FILE in completion.txt completion.sha256 execution-metadata.json \
  execution-metadata.sha256; do
  [ -s "$PREFLIGHT/$FILE" ] || {
    echo "ERROR: ATLAS interaction parity awaits strict binary preflight: $FILE" >&2
    exit 2
  }
done
(
  cd "$PREFLIGHT"
  sha256sum -c completion.sha256 >/dev/null
  sha256sum -c execution-metadata.sha256 >/dev/null
)
PREFLIGHT_STATUS=$(awk -F= '$1=="status" {print $2}' "$PREFLIGHT/completion.txt")
[ "$PREFLIGHT_STATUS" = False ] || {
  echo "ERROR: binary preflight did not fail; repair5 retains queue priority" >&2
  exit 2
}

[ ! -e "$OUT/manifest.txt" ] && [ ! -e "$OUT/execution.txt" ] && \
  [ ! -e "$OUT/completion.txt" ] || {
  echo "ERROR: immutable ATLAS interaction-parity launch/harvest exists" >&2
  exit 3
}
if gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
    2>/dev/null | head -1 | grep -q .; then
  echo "ERROR: immutable ATLAS interaction-parity cloud prefix exists" >&2
  exit 3
fi

SOURCE_B64=$(base64 -w0 "$SOURCE")
PY_COMMAND="exec(__import__('base64').b64decode('$SOURCE_B64'))"
SMOKE_COMMAND=$(cat <<PY
import base64,hashlib,pathlib
source=base64.b64decode('$SOURCE_B64')
assert hashlib.sha256(source).hexdigest()=='$SOURCE_SHA'
assert hashlib.sha256(pathlib.Path('/app/scripts/run_atlas_matched_diversity_mvp.py').read_bytes()).hexdigest()=='$RUNNER_SHA'
assert hashlib.sha256(pathlib.Path('/app/src/nfl_dfs/optimizer/lineup.py').read_bytes()).hexdigest()=='$OPTIMIZER_SHA'
compile(source,'run_atlas_interaction_parity_diagnostic.py','exec')
print('ATLAS_INTERACTION_PARITY_SMOKE_OK $SOURCE_SHA')
PY
)

printf '%s\n' \
  "run_id=$RUN_ID" "protocol_sha256=$PROTOCOL_SHA" \
  "build_repair_sha256=$BUILD_REPAIR_SHA" \
  "build_receipt_sha256=$BUILD_RECEIPT_SHA" "build_id=$BUILD_ID" \
  "diagnostic_source_sha256=$SOURCE_SHA" "runner_sha256=$RUNNER_SHA" \
  "optimizer_sha256=$OPTIMIZER_SHA" "code_sha=$CODE_SHA" \
  "image=$IMAGE" "output_prefix=$PREFIX" \
  "preflight_completion_sha256=$(sha256sum "$PREFLIGHT/completion.txt" | awk '{print $1}')" \
  "preflight_execution_metadata_sha256=$(sha256sum "$PREFLIGHT/execution-metadata.json" | awk '{print $1}')" \
  "command_sha256=$(printf '%s' "$PY_COMMAND" | sha256sum | awk '{print $1}')" \
  'queue_trigger=binary-32g-preflight-failed' 'cell=2024-15-R0' \
  'cpu=8' 'memory=32Gi' 'max_retries=0' 'timeout_seconds=43200' \
  'uses_realized_outcomes=false' 'persists_lineups=false' \
  'production_change_licensed=false' > "$OUT/manifest.txt"

SMOKE_JOB=atlas-interaction-parity-smoke-v1
gcloud run jobs deploy "$SMOKE_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python --args=-c,"$SMOKE_COMMAND" \
  --service-account "$SERVICE_ACCOUNT" --cpu 1 --memory 1Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 10m --quiet
SMOKE_EXEC=$(gcloud run jobs execute "$SMOKE_JOB" --project "$PROJECT" \
  --region "$REGION" --wait --format='value(metadata.name)')
[ -n "$SMOKE_EXEC" ] || {
  echo "ERROR: ATLAS interaction-parity smoke execution missing" >&2; exit 2; }
gcloud run jobs executions describe "$SMOKE_EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$OUT/smoke-execution.json"
"$ROOT/.venv/bin/python" - "$OUT/smoke-execution.json" "$SMOKE_EXEC" \
  "$SMOKE_COMMAND" "$IMAGE" "$SERVICE_ACCOUNT" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding="utf-8"))
execution,command,image,account=sys.argv[2:]
s=x.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if x.get("metadata",{}).get("name")!=execution or len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or not s.get("completionTime"):
 raise SystemExit("ERROR: ATLAS interaction-parity smoke did not complete")
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ERROR: ATLAS interaction-parity smoke task shape differs")
container=containers[0]
if container.get("image")!=image or container.get("command")!=["python"] or container.get("args")!=["-c",command] or container.get("env",[]) or container.get("resources",{}).get("limits")!={"cpu":"1","memory":"1Gi"}:
 raise SystemExit("ERROR: ATLAS interaction-parity smoke container differs")
if task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="600" or task.get("serviceAccountName")!=account:
 raise SystemExit("ERROR: ATLAS interaction-parity smoke retry/timeout/account differs")
PY
gcloud logging read \
  "resource.type=cloud_run_job AND labels.\"run.googleapis.com/execution_name\"=\"$SMOKE_EXEC\" AND textPayload:\"ATLAS_INTERACTION_PARITY_SMOKE_OK\"" \
  --project "$PROJECT" --limit 20 --format='value(textPayload)' \
  > "$OUT/smoke.log"
grep -Fq "ATLAS_INTERACTION_PARITY_SMOKE_OK $SOURCE_SHA" "$OUT/smoke.log" || {
  echo "ERROR: ATLAS interaction-parity smoke marker differs" >&2; exit 2; }

URI="$PREFIX/parity.json"
JOB=atlas-interaction-parity-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python \
  --args=-c,"$PY_COMMAND",--season,2024,--week,15,--output-uri,"$URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE",ATLAS_INTERACTION_PARITY_PROTOCOL_SHA256="$PROTOCOL_SHA",ATLAS_INTERACTION_PARITY_SOURCE_SHA256="$SOURCE_SHA" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 12h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: ATLAS interaction-parity execution identity missing" >&2; exit 2; }
printf '2024 15 R0 %s %s %s\n' "$JOB" "$EXEC" "$URI" \
  | tee "$OUT/execution.txt"
sha256sum "$OUT/manifest.txt" "$OUT/execution.txt" \
  "$OUT/smoke-execution.json" "$OUT/smoke.log" > "$OUT/launch.sha256"
echo "ATLAS_INTERACTION_PARITY_LAUNCHED $RUN_ID"
