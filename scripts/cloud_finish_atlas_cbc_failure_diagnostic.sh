#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-cbc-native-diagnostic-v1
OUT="$ROOT/reports/atlas-cbc-native-diagnostic-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
SOURCE="$ROOT/scripts/run_atlas_cbc_failure_diagnostic.py"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: ATLAS CBC diagnostic launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 2 ] || {
  echo "ABORT: ATLAS CBC diagnostic execution count differs" >&2; exit 2; }
[ ! -e "$OUT/completion.txt" ] && [ ! -e "$OUT/execution-metadata" ] && \
  [ ! -e "$OUT/artifacts" ] || {
  echo "ABORT: immutable ATLAS CBC diagnostic harvest exists" >&2; exit 3; }

mkdir -p "$OUT/execution-metadata.pending" "$OUT/artifacts.pending"
while read -r SEASON WEEK JOB EXEC ARTIFACT_PREFIX; do
  META="$OUT/execution-metadata.pending/season-${SEASON}-week-${WEEK}.json"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$META"
  "$ROOT/.venv/bin/python" - "$META" "$MANIFEST" "$SOURCE" \
    "$SEASON" "$WEEK" "$JOB" "$EXEC" "$ARTIFACT_PREFIX" <<'PY'
import base64, json, sys
from pathlib import Path

meta=json.load(open(sys.argv[1],encoding="utf-8"))
manifest=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
source=Path(sys.argv[3]).read_bytes()
season,week,job,execution,prefix=sys.argv[4:]
if season!="2024" or week not in {"15","16"} or meta.get("metadata",{}).get("name")!=execution:
 raise SystemExit("ABORT: ATLAS CBC diagnostic cell/execution differs")
status=meta.get("status",{}); done=[r for r in status.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status") not in {"True","False"} or not status.get("completionTime"):
 raise SystemExit("ABORT: ATLAS CBC diagnostic is not terminal")
spec=meta.get("spec",{}); template=spec.get("template",{}).get("spec",{}); containers=template.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ABORT: ATLAS CBC diagnostic task shape differs")
container=containers[0]
command="exec(__import__('base64').b64decode('"+base64.b64encode(source).decode()+"'))"
expected_args=["-c",command,"--season","2024","--week",week,"--artifact-prefix",prefix]
if container.get("image")!=manifest["repair2_image"] or container.get("command")!=["python"] or container.get("args")!=expected_args:
 raise SystemExit("ABORT: ATLAS CBC diagnostic image/command differs")
env={r.get("name"):str(r.get("value","")) for r in container.get("env",[])}
expected_env={
 "CODE_SHA":manifest["repair2_code_sha"],
 "ANALYSIS_IMAGE":manifest["repair2_image"],
 "ATLAS_CBC_DIAGNOSTIC_PROTOCOL_SHA256":manifest["protocol_sha256"],
 "ATLAS_CBC_DIAGNOSTIC_SOURCE_SHA256":manifest["diagnostic_source_sha256"],
}
if env!=expected_env or container.get("resources",{}).get("limits")!={"cpu":"1","memory":"4Gi"}:
 raise SystemExit("ABORT: ATLAS CBC diagnostic environment/resources differ")
if template.get("maxRetries")!=0 or str(template.get("timeoutSeconds"))!="43200" or template.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS CBC diagnostic retry/timeout/account differs")
print(done[0]["status"])
PY
  STATUS=$("$ROOT/.venv/bin/python" - "$META" <<'PY'
import json,sys
x=json.load(open(sys.argv[1],encoding="utf-8"))
print([r for r in x["status"]["conditions"] if r.get("type")=="Completed"][0]["status"])
PY
)
  CELL="$OUT/artifacts.pending/season-${SEASON}-week-${WEEK}"
  mkdir -p "$CELL"
  if [ "$STATUS" = True ]; then
    gcloud storage cp "$ARTIFACT_PREFIX/success.json" "$CELL/success.json" \
      --project "$PROJECT" >/dev/null
  else
    for NAME in failure.json cbc.log problem.mps; do
      gcloud storage cp "$ARTIFACT_PREFIX/$NAME" "$CELL/$NAME" \
        --project "$PROJECT" >/dev/null
    done
  fi
  "$ROOT/.venv/bin/python" - "$CELL" "$META" "$MANIFEST" \
    "$SEASON" "$WEEK" "$EXEC" "$ARTIFACT_PREFIX" "$STATUS" <<'PY'
from hashlib import sha256
import json,sys
from pathlib import Path

cell=Path(sys.argv[1]); meta=json.load(open(sys.argv[2],encoding="utf-8"))
manifest=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[3],encoding="utf-8") if "=" in line)
season,week,execution,prefix,status=sys.argv[4:]
receipt_path=cell/("success.json" if status=="True" else "failure.json")
receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
expected={
 "version":"atlas-cbc-native-diagnostic-v1",
 "uses_realized_outcomes":False,
 "persists_lineups":False,
 "protocol_id":manifest["run_id"],
 "protocol_sha256":manifest["protocol_sha256"],
 "diagnostic_source_sha256":manifest["diagnostic_source_sha256"],
 "repair2_code_sha":manifest["repair2_code_sha"],
 "repair2_image":manifest["repair2_image"],
 "execution":execution,
}
if any(receipt.get(k)!=v for k,v in expected.items()) or int(receipt.get("solve_count",0))<1:
 raise SystemExit("ABORT: ATLAS CBC diagnostic receipt identity differs")
if status=="True":
 if receipt.get("status")!="r0-complete" or set(receipt)!=(set(expected)|{"status","task_index","solve_count"}):
  raise SystemExit("ABORT: ATLAS CBC diagnostic success receipt differs")
else:
 if receipt.get("status")!="cbc-failure" or receipt.get("exception_type")!="PulpSolverError":
  raise SystemExit("ABORT: ATLAS CBC diagnostic failure disposition differs")
 artifacts=receipt.get("artifacts",{})
 if set(artifacts)!={"cbc.log","problem.mps"}:
  raise SystemExit("ABORT: ATLAS CBC diagnostic artifact set differs")
 for name,value in artifacts.items():
  raw=(cell/name).read_bytes()
  if value.get("uri")!=f"{prefix}/{name}" or value.get("sha256")!=sha256(raw).hexdigest() or value.get("size")!=len(raw) or not str(value.get("generation","")).isdigit():
   raise SystemExit("ABORT: ATLAS CBC diagnostic artifact receipt differs")
 if not (cell/"problem.mps").stat().st_size:
  raise SystemExit("ABORT: ATLAS CBC diagnostic MPS is empty")
for forbidden in ("actual_score","actual_rank","selected_lineups","gate","tail_probability"):
 if forbidden in json.dumps(receipt,sort_keys=True).lower():
  raise SystemExit("ABORT: ATLAS CBC diagnostic receipt crossed firewall")
print("ATLAS_CBC_DIAGNOSTIC_RECEIPT_VALIDATED",season,week,receipt["status"])
PY
done < "$EXECUTIONS"

mv "$OUT/execution-metadata.pending" "$OUT/execution-metadata"
mv "$OUT/artifacts.pending" "$OUT/artifacts"
sha256sum "$OUT"/execution-metadata/*.json | sort > "$OUT/execution-metadata.sha256"
find "$OUT/artifacts" -type f -print0 | sort -z | xargs -0 sha256sum \
  > "$OUT/artifacts.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'cells=2024-15,2024-16' 'uses_realized_outcomes=false' \
  'persists_lineups=false' 'production_change_licensed=false' \
  > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_CBC_NATIVE_DIAGNOSTIC_HARVESTED $RUN_ID"
