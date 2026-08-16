#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-cbc-32g-full-cell-preflight-v1
OUT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-cbc-32g-full-cell-preflight-runs/$RUN_ID
PROTOCOL="$ROOT/reports/2026-08-16-atlas-cbc-32g-full-cell-preflight-protocol.md"
PROTOCOL_SHA=b848dcc4ce0cdc6c3cac07f5ffb2ad6cbaa233a2457dc0286034ff3d50840788
RUNNER="$ROOT/scripts/run_atlas_matched_diversity_mvp.py"
RUNNER_SHA=0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"
RENDERER_SHA=69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671
IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb
CODE_SHA=60f296fdad769b30c0bb7334118698f156e462b9
REPAIR4_EXEC=atlas-md-s2023-w8-r4-6rn7r
REPAIR4_PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair4

for SPEC in "$PROTOCOL:$PROTOCOL_SHA" "$RUNNER:$RUNNER_SHA" \
  "$RENDERER:$RENDERER_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: ATLAS 32-GiB full-cell preflight source differs: $FILE" >&2
    exit 2
  }
done
[ ! -e "$OUT" ] || {
  echo "ERROR: immutable ATLAS 32-GiB preflight local run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
    2>/dev/null | head -1 | grep -q .; then
  echo "ERROR: immutable ATLAS 32-GiB preflight cloud prefix exists" >&2
  exit 3
fi

REPAIR4_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$REPAIR4_PREFIX")
PREFLIGHT_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX")
URI="$PREFIX/slate-2023-8.json"
mkdir -p "$OUT"
gcloud run jobs executions describe "$REPAIR4_EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$OUT/repair4-failure-execution.json"
"$ROOT/.venv/bin/python" - "$OUT/repair4-failure-execution.json" \
  "$REPAIR4_EXEC" "$REPAIR4_COMMAND" "$REPAIR4_PREFIX" "$IMAGE" \
  "$CODE_SHA" <<'PY'
import json, sys
x=json.load(open(sys.argv[1],encoding="utf-8"))
name,command,prefix,image,code_sha=sys.argv[2:]
if x.get("metadata",{}).get("name")!=name:
 raise SystemExit("ERROR: ATLAS repair4 failure execution name differs")
s=x.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="False" or int(s.get("failedCount") or 0)!=1 or not s.get("completionTime") or "configured memory limit was reached" not in done[0].get("message",""):
 raise SystemExit("ERROR: ATLAS repair4 memory failure evidence differs")
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ERROR: ATLAS repair4 failure task shape differs")
container=containers[0]
expected_uri=f"{prefix}/slate-2023-8.json"
expected_args=["-c",command,"--season","2023","--week","8","--output-uri",expected_uri]
if container.get("image")!=image or container.get("command")!=["python"] or container.get("args")!=expected_args:
 raise SystemExit("ERROR: ATLAS repair4 failure command differs")
env={r.get("name"):str(r.get("value","")) for r in container.get("env",[])}
if env!={"CODE_SHA":code_sha,"ANALYSIS_IMAGE":image} or container.get("resources",{}).get("limits")!={"cpu":"4","memory":"16Gi"}:
 raise SystemExit("ERROR: ATLAS repair4 failure environment/resources differ")
if task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="43200" or task.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ERROR: ATLAS repair4 failure retry/timeout/account differs")
PY

printf '%s\n' \
  "run_id=$RUN_ID" "protocol_sha256=$PROTOCOL_SHA" \
  "runner_sha256=$RUNNER_SHA" "renderer_sha256=$RENDERER_SHA" \
  "code_sha=$CODE_SHA" "image=$IMAGE" "output_prefix=$PREFIX" \
  "repair4_failure_execution=$REPAIR4_EXEC" \
  "repair4_failure_execution_sha256=$(sha256sum "$OUT/repair4-failure-execution.json" | awk '{print $1}')" \
  "command_sha256=$(printf '%s' "$PREFLIGHT_COMMAND" | sha256sum | awk '{print $1}')" \
  'cell=2023-8' 'cpu=8' 'memory=32Gi' 'max_retries=0' \
  'timeout_seconds=43200' 'interaction_auxiliaries=binary' \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  > "$OUT/manifest.txt"

JOB=atlas-cbc-32g-full-2023-w8-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python \
  --args=-c,"$PREFLIGHT_COMMAND",--season,2023,--week,8,--output-uri,"$URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 12h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: ATLAS 32-GiB full-cell execution identity missing" >&2; exit 2; }
printf '2023 8 %s %s %s\n' "$JOB" "$EXEC" "$URI" \
  | tee "$OUT/execution.txt"
sha256sum "$OUT/manifest.txt" "$OUT/execution.txt" \
  "$OUT/repair4-failure-execution.json" > "$OUT/launch.sha256"
echo "ATLAS_CBC_32G_FULL_CELL_PREFLIGHT_LAUNCHED $RUN_ID"
