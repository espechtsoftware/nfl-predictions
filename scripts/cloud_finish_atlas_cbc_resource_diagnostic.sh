#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-cbc-resource-diagnostic-v1
OUT="$ROOT/reports/atlas-cbc-resource-diagnostic-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
SOURCE="$ROOT/scripts/run_atlas_cbc_resource_diagnostic.py"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: ATLAS CBC resource launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 3 ] || {
  echo "ABORT: ATLAS CBC resource execution count differs" >&2; exit 2; }
[ ! -e "$OUT/completion.txt" ] && [ ! -e "$OUT/execution-metadata" ] && \
  [ ! -e "$OUT/artifacts" ] || {
  echo "ABORT: immutable ATLAS CBC resource harvest exists" >&2; exit 3; }

mkdir -p "$OUT/execution-metadata.pending" "$OUT/artifacts.pending"
while read -r SEASON WEEK JOB EXEC ARTIFACT_PREFIX; do
  META="$OUT/execution-metadata.pending/season-${SEASON}-week-${WEEK}.json"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$META"
  STATUS=$("$ROOT/.venv/bin/python" - "$META" "$MANIFEST" "$SOURCE" \
    "$SEASON" "$WEEK" "$JOB" "$EXEC" "$ARTIFACT_PREFIX" <<'PY'
import base64, json, sys
from pathlib import Path

meta=json.load(open(sys.argv[1],encoding="utf-8"))
manifest=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
source=Path(sys.argv[3]).read_bytes()
season,week,job,execution,prefix=sys.argv[4:]
if season!="2024" or week not in {"7","15","16"} or meta.get("metadata",{}).get("name")!=execution:
 raise SystemExit("ABORT: ATLAS CBC resource cell/execution differs")
status=meta.get("status",{}); done=[r for r in status.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status") not in {"True","False"} or not status.get("completionTime"):
 raise SystemExit("ABORT: ATLAS CBC resource diagnostic is not terminal")
spec=meta.get("spec",{}); template=spec.get("template",{}).get("spec",{}); containers=template.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ABORT: ATLAS CBC resource task shape differs")
container=containers[0]
command="exec(__import__('base64').b64decode('"+base64.b64encode(source).decode()+"'))"
expected_args=["-c",command,"--season","2024","--week",week,"--artifact-prefix",prefix]
if container.get("image")!=manifest["repair2_image"] or container.get("command")!=["python"]:
 raise SystemExit("ABORT: ATLAS CBC resource image/command differs")
if container.get("args")!=expected_args:
 raise SystemExit("ABORT: ATLAS CBC resource args differ")
env={r.get("name"):str(r.get("value","")) for r in container.get("env",[])}
expected_env={
 "CODE_SHA":manifest["repair2_code_sha"],
 "ANALYSIS_IMAGE":manifest["repair2_image"],
 "ATLAS_CBC_RESOURCE_PROTOCOL_SHA256":manifest["protocol_sha256"],
 "ATLAS_CBC_RESOURCE_SOURCE_SHA256":manifest["diagnostic_source_sha256"],
}
if env!=expected_env or container.get("resources",{}).get("limits")!={"cpu":"1","memory":"4Gi"}:
 raise SystemExit("ABORT: ATLAS CBC resource environment/resources differ")
if template.get("maxRetries")!=0 or str(template.get("timeoutSeconds"))!="43200" or template.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS CBC resource retry/timeout/account differs")
print(done[0]["status"])
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
  "$ROOT/.venv/bin/python" - "$CELL" "$MANIFEST" "$SEASON" "$WEEK" \
    "$EXEC" "$ARTIFACT_PREFIX" "$STATUS" <<'PY'
from hashlib import sha256
import json, math, sys
from pathlib import Path

cell=Path(sys.argv[1]); manifest=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
season,week,execution,prefix,status=sys.argv[3:]
receipt_path=cell/("success.json" if status=="True" else "failure.json")
receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
expected={
 "version":"atlas-cbc-resource-diagnostic-v1",
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
 raise SystemExit("ABORT: ATLAS CBC resource receipt identity differs")
evidence=receipt.get("resource_evidence",{})
required={"child_process_count","first_cgroup_before","last_child","oom_kill_delta_total","maximum_memory_peak_bytes","maximum_memory_peak_ratio"}
if set(evidence)!=required or int(evidence.get("child_process_count",0))<1 or not isinstance(evidence.get("last_child"),dict):
 raise SystemExit("ABORT: ATLAS CBC resource evidence differs")
last=evidence["last_child"]
if set(last)!={"returncode","terminating_signal","cgroup_before","cgroup_after","oom_kill_delta","memory_peak_ratio"}:
 raise SystemExit("ABORT: ATLAS CBC child receipt differs")
for snapshot in (last["cgroup_before"],last["cgroup_after"]):
 if not isinstance(snapshot,dict) or set(snapshot)!={"version","path","events","memory_current","memory_peak","memory_max","available"}:
  raise SystemExit("ABORT: ATLAS CBC cgroup snapshot differs")
if status=="True":
 if receipt.get("status")!="r0-complete" or int(last["returncode"])!=0:
  raise SystemExit("ABORT: ATLAS CBC resource success differs")
else:
 if receipt.get("status")!="cbc-failure" or receipt.get("exception_type")!="PulpSolverError" or int(last["returncode"])==0:
  raise SystemExit("ABORT: ATLAS CBC resource failure differs")
 artifacts=receipt.get("artifacts",{})
 if set(artifacts)!={"cbc.log","problem.mps"}:
  raise SystemExit("ABORT: ATLAS CBC resource artifact set differs")
 for name,value in artifacts.items():
  raw=(cell/name).read_bytes()
  if value.get("uri")!=f"{prefix}/{name}" or value.get("sha256")!=sha256(raw).hexdigest() or value.get("size")!=len(raw) or not str(value.get("generation","")).isdigit():
   raise SystemExit("ABORT: ATLAS CBC resource artifact receipt differs")
 if not (cell/"problem.mps").stat().st_size:
  raise SystemExit("ABORT: ATLAS CBC resource MPS is empty")
for forbidden in ("actual_score","actual_rank","selected_lineups","gate","tail_probability"):
 if forbidden in json.dumps(receipt,sort_keys=True).lower():
  raise SystemExit("ABORT: ATLAS CBC resource receipt crossed firewall")
print("ATLAS_CBC_RESOURCE_RECEIPT_VALIDATED",season,week,receipt["status"])
PY
done < "$EXECUTIONS"

"$ROOT/.venv/bin/python" - "$OUT/artifacts.pending" > "$OUT/summary.pending.json" <<'PY'
import json, sys
from pathlib import Path

root=Path(sys.argv[1]); rows=[]
for cell in sorted(root.iterdir()):
 receipt_path=cell/("success.json" if (cell/"success.json").is_file() else "failure.json")
 receipt=json.loads(receipt_path.read_text(encoding="utf-8"))
 evidence=receipt["resource_evidence"]; last=evidence["last_child"]
 rows.append({
  "cell":cell.name,
  "status":receipt["status"],
  "returncode":last["returncode"],
  "terminating_signal":last["terminating_signal"],
  "oom_kill_delta_total":evidence["oom_kill_delta_total"],
  "maximum_memory_peak_bytes":evidence["maximum_memory_peak_bytes"],
  "maximum_memory_peak_ratio":evidence["maximum_memory_peak_ratio"],
  "cgroup_available":bool(last["cgroup_before"].get("available") and last["cgroup_after"].get("available")),
 })
all_success=all(r["status"]=="r0-complete" for r in rows)
all_cgroup=all(r["cgroup_available"] for r in rows)
any_oom=any(int(r["oom_kill_delta_total"])>0 for r in rows)
ratios=[r["maximum_memory_peak_ratio"] for r in rows if isinstance(r["maximum_memory_peak_ratio"],(int,float))]
any_pressure=any(r>=0.80 for r in ratios)
any_sigkill=any(r["returncode"]==-9 for r in rows)
if any_oom:
 disposition="oom-kill-confirmed"
elif any_sigkill:
 disposition="sigkill-without-cgroup-oom-confirmation"
elif all_success and all_cgroup and len(ratios)==len(rows) and not any_pressure:
 disposition="isolated-r0-success-memory-clear"
elif all_success and all_cgroup and any_pressure:
 disposition="isolated-r0-success-memory-pressure"
else:
 disposition="resource-diagnostic-inconclusive"
print(json.dumps({
 "version":"atlas-cbc-resource-diagnostic-summary-v1",
 "uses_realized_outcomes":False,
 "persists_lineups":False,
 "pressure_ratio_boundary":0.80,
 "disposition":disposition,
 "production_change_licensed":False,
 "rows":rows,
},sort_keys=True,separators=(",",":")))
PY

mv "$OUT/execution-metadata.pending" "$OUT/execution-metadata"
mv "$OUT/artifacts.pending" "$OUT/artifacts"
mv "$OUT/summary.pending.json" "$OUT/summary.json"
sha256sum "$OUT"/execution-metadata/*.json | sort > "$OUT/execution-metadata.sha256"
find "$OUT/artifacts" -type f -print0 | sort -z | xargs -0 sha256sum \
  > "$OUT/artifacts.sha256"
sha256sum "$OUT/summary.json" > "$OUT/summary.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'cells=2024-7,2024-15,2024-16' 'uses_realized_outcomes=false' \
  'persists_lineups=false' 'production_change_licensed=false' \
  > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_CBC_RESOURCE_DIAGNOSTIC_HARVESTED $RUN_ID"
