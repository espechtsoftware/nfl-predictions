#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-cbc-16g-preflight-v1
OUT="$ROOT/reports/atlas-cbc-16g-preflight-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"
SOURCE="$ROOT/scripts/run_atlas_cbc_resource_diagnostic.py"
RENDERER="$ROOT/scripts/render_atlas_cbc_16g_preflight_command.py"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] && \
  [ "$(wc -l < "$EXECUTION")" = 1 ] || {
  echo "ABORT: ATLAS CBC 16 GiB preflight launch receipt differs" >&2; exit 2; }
[ ! -e "$OUT/completion.txt" ] && [ ! -e "$OUT/execution-metadata.json" ] && \
  [ ! -e "$OUT/artifacts" ] || {
  echo "ABORT: immutable ATLAS CBC 16 GiB preflight harvest exists" >&2; exit 3; }

read -r SEASON WEEK JOB EXEC ARTIFACT_PREFIX < "$EXECUTION"
META="$OUT/execution-metadata.pending.json"
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$META"
STATUS=$("$ROOT/.venv/bin/python" - "$META" "$MANIFEST" "$SOURCE" \
  "$RENDERER" "$SEASON" "$WEEK" "$JOB" "$EXEC" "$ARTIFACT_PREFIX" <<'PY'
import json, subprocess, sys

meta=json.load(open(sys.argv[1],encoding="utf-8"))
manifest=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
source,renderer=sys.argv[3],sys.argv[4]
season,week,job,execution,prefix=sys.argv[5:]
if season!="2024" or week!="15" or job!="atlas-cbc-16g-preflight-2024-w15-v1" or meta.get("metadata",{}).get("name")!=execution:
 raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight identity differs")
status=meta.get("status",{}); done=[r for r in status.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status") not in {"True","False"} or not status.get("completionTime"):
 raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight is not terminal")
template=meta.get("spec",{}).get("template",{}).get("spec",{}); containers=template.get("containers",[])
if meta.get("spec",{}).get("parallelism")!=1 or meta.get("spec",{}).get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight task shape differs")
command=subprocess.check_output([
 sys.executable,renderer,"--source",source,"--protocol-id",manifest["run_id"],
 "--prefix",prefix.rsplit("/season-",1)[0],
],text=True).strip()
container=containers[0]
expected_args=["-c",command,"--season","2024","--week","15","--artifact-prefix",prefix]
if container.get("image")!=manifest["repair2_image"] or container.get("command")!=["python"] or container.get("args")!=expected_args:
 raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight image/command differs")
env={r.get("name"):str(r.get("value","")) for r in container.get("env",[])}
expected_env={
 "CODE_SHA":manifest["repair2_code_sha"],
 "ANALYSIS_IMAGE":manifest["repair2_image"],
 "ATLAS_CBC_RESOURCE_PROTOCOL_SHA256":manifest["protocol_sha256"],
 "ATLAS_CBC_RESOURCE_SOURCE_SHA256":manifest["diagnostic_source_sha256"],
}
if env!=expected_env or container.get("resources",{}).get("limits")!={"cpu":"4","memory":"16Gi"}:
 raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight environment/resources differ")
if template.get("maxRetries")!=0 or str(template.get("timeoutSeconds"))!="43200" or template.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight retry/timeout/account differs")
print(done[0]["status"])
PY
)

mkdir -p "$OUT/artifacts.pending"
if [ "$STATUS" = True ]; then
  gcloud storage cp "$ARTIFACT_PREFIX/success.json" \
    "$OUT/artifacts.pending/success.json" --project "$PROJECT" >/dev/null
else
  for NAME in failure.json cbc.log problem.mps; do
    gcloud storage cp "$ARTIFACT_PREFIX/$NAME" \
      "$OUT/artifacts.pending/$NAME" --project "$PROJECT" >/dev/null
  done
fi

"$ROOT/.venv/bin/python" - "$OUT/artifacts.pending" "$MANIFEST" \
  "$EXEC" "$ARTIFACT_PREFIX" "$STATUS" > "$OUT/summary.pending.json" <<'PY'
from hashlib import sha256
import json, sys
from pathlib import Path

root=Path(sys.argv[1]); manifest=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
execution,prefix,status=sys.argv[3:]
receipt_path=root/("success.json" if status=="True" else "failure.json")
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
 raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight receipt identity differs")
evidence=receipt.get("resource_evidence",{}); last=evidence.get("last_child")
required={"child_process_count","first_cgroup_before","last_child","oom_kill_delta_total","maximum_memory_peak_bytes","maximum_memory_peak_ratio"}
if set(evidence)!=required or int(evidence.get("child_process_count",0))<1 or not isinstance(last,dict):
 raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight evidence differs")
if set(last)!={"returncode","terminating_signal","cgroup_before","cgroup_after","oom_kill_delta","memory_peak_ratio"}:
 raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight child evidence differs")
for snapshot in (last["cgroup_before"],last["cgroup_after"]):
 if not isinstance(snapshot,dict) or set(snapshot)!={"version","path","events","memory_current","memory_peak","memory_max","available"}:
  raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight cgroup snapshot differs")
if status=="True":
 if receipt.get("status")!="r0-complete" or int(last["returncode"])!=0:
  raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight success differs")
 disposition="r0-complete"
else:
 if receipt.get("status")!="cbc-failure" or receipt.get("exception_type")!="PulpSolverError" or int(last["returncode"])==0:
  raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight failure differs")
 artifacts=receipt.get("artifacts",{})
 if set(artifacts)!={"cbc.log","problem.mps"}:
  raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight artifact set differs")
 for name,value in artifacts.items():
  raw=(root/name).read_bytes()
  if value.get("uri")!=f"{prefix}/{name}" or value.get("sha256")!=sha256(raw).hexdigest() or value.get("size")!=len(raw) or not str(value.get("generation","")).isdigit():
   raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight artifact receipt differs")
 if int(evidence.get("oom_kill_delta_total") or 0)>0:
  disposition="oom-kill-confirmed-at-16g"
 else:
  disposition="16g-preflight-failure"
for forbidden in ("actual_score","actual_rank","selected_lineups","gate","tail_probability"):
 if forbidden in json.dumps(receipt,sort_keys=True).lower():
  raise SystemExit("ABORT: ATLAS CBC 16 GiB preflight crossed firewall")
print(json.dumps({
 "version":"atlas-cbc-16g-preflight-summary-v1",
 "uses_realized_outcomes":False,
 "persists_lineups":False,
 "production_change_licensed":False,
 "disposition":disposition,
 "status":receipt["status"],
 "returncode":last["returncode"],
 "terminating_signal":last["terminating_signal"],
 "oom_kill_delta_total":evidence["oom_kill_delta_total"],
 "maximum_memory_peak_bytes":evidence["maximum_memory_peak_bytes"],
 "maximum_memory_peak_ratio":evidence["maximum_memory_peak_ratio"],
},sort_keys=True,separators=(",",":")))
PY

mv "$META" "$OUT/execution-metadata.json"
mv "$OUT/artifacts.pending" "$OUT/artifacts"
mv "$OUT/summary.pending.json" "$OUT/summary.json"
sha256sum "$OUT/execution-metadata.json" > "$OUT/execution-metadata.sha256"
find "$OUT/artifacts" -type f -print0 | sort -z | xargs -0 sha256sum \
  > "$OUT/artifacts.sha256"
sha256sum "$OUT/summary.json" > "$OUT/summary.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'cell=2024-15' 'cpu=4' 'memory=16Gi' 'uses_realized_outcomes=false' \
  'persists_lineups=false' 'production_change_licensed=false' \
  > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_CBC_16G_PREFLIGHT_HARVESTED $RUN_ID"

