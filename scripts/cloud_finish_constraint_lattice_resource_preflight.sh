#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-constraint-lattice-resource-preflight-v1
OUT="$ROOT/reports/constraint-lattice-resource-preflight-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"
PROTOCOL="$ROOT/reports/2026-08-16-constraint-lattice-resource-preflight-protocol.md"
PROTOCOL_SHA=9e04ebcbcb2def607e28c5f8fa046ba4456f40e2e8a654182f654318ca579d7b
RUNNER="$ROOT/scripts/run_constraint_lattice_resource_preflight.py"
SUPPORT="$ROOT/reports/constraint-lattice-support-runs/20260816-constraint-lattice-control-support-census-v1"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] && [ -s "$PROTOCOL" ] && \
  [ -s "$RUNNER" ] && [ -s "$SUPPORT/completion.txt" ] && \
  [ -s "$SUPPORT/report.json" ] || {
  echo "ABORT: lattice-resource launch/dependency receipt is incomplete" >&2; exit 2; }
[ "$(sha256sum "$PROTOCOL" | awk '{print $1}')" = "$PROTOCOL_SHA" ] || {
  echo "ABORT: lattice-resource protocol differs" >&2; exit 2; }
[ ! -e "$OUT/completion.txt" ] && [ ! -e "$OUT/execution-metadata.json" ] && \
  [ ! -e "$OUT/object-metadata.json" ] && [ ! -e "$OUT/logs.json" ] || {
  echo "ABORT: immutable lattice-resource harvest exists" >&2; exit 3; }

read -r JOB EXEC URI < "$EXECUTION"
LISTED=$(gcloud run jobs executions list --job "$JOB" --project "$PROJECT" \
  --region "$REGION" --format='value(metadata.name)')
[ "$LISTED" = "$EXEC" ] || {
  echo "ABORT: lattice-resource job has replacement/extra execution" >&2; exit 2; }
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$OUT/execution-metadata.pending.json"
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC\"" \
  --project "$PROJECT" --limit=300 --order=asc --format=json \
  > "$OUT/logs.pending.json"
gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
  > "$OUT/object-metadata.pending.json"

"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTION" \
  "$OUT/execution-metadata.pending.json" "$OUT/logs.pending.json" \
  "$OUT/object-metadata.pending.json" "$RUNNER" "$SUPPORT" <<'PY'
from hashlib import sha256
import json, pathlib, re, sys
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[1],encoding="utf-8") if "=" in line)
job,execution,uri=open(sys.argv[2],encoding="utf-8").read().split()
x=json.load(open(sys.argv[3],encoding="utf-8")); logs=json.load(open(sys.argv[4],encoding="utf-8")); obj=json.load(open(sys.argv[5],encoding="utf-8")); runner=pathlib.Path(sys.argv[6]); support=pathlib.Path(sys.argv[7])
fixed={
 "run_id":"20260816-constraint-lattice-resource-preflight-v1",
 "output_prefix":"gs://nfl-predictions-503414-raw/research/constraint-lattice-resource-preflight-runs/20260816-constraint-lattice-resource-preflight-v1",
 "output_uri":"gs://nfl-predictions-503414-raw/research/constraint-lattice-resource-preflight-runs/20260816-constraint-lattice-resource-preflight-v1/slate-2023-1.json",
 "protocol_sha256":"9e04ebcbcb2def607e28c5f8fa046ba4456f40e2e8a654182f654318ca579d7b",
 "cell":"2023-1", "source_artifact_bytes":"163064634",
 "cpu":"4", "memory":"16Gi", "timeout_seconds":"43200", "max_retries":"0",
 "uses_realized_outcomes":"false", "effect_fields_inspected":"false",
 "production_change_licensed":"false",
}
for key,value in fixed.items():
 if m.get(key)!=value: raise SystemExit(f"ABORT: lattice-resource manifest differs: {key}")
if not re.fullmatch(r"[0-9a-f]{40}",m.get("code_sha","")) or not re.fullmatch(r".+@sha256:[0-9a-f]{64}",m.get("image","")) or m.get("runner_sha256")!=sha256(runner.read_bytes()).hexdigest():
 raise SystemExit("ABORT: lattice-resource code/image/runner differs")
if m.get("support_completion_sha256")!=sha256((support/"completion.txt").read_bytes()).hexdigest() or m.get("support_report_sha256")!=sha256((support/"report.json").read_bytes()).hexdigest():
 raise SystemExit("ABORT: lattice-resource support binding differs")
if job!="constraint-lattice-resource-2023-w1-v1" or not execution.startswith(job+"-") or uri!=m["output_uri"] or x.get("metadata",{}).get("name")!=execution:
 raise SystemExit("ABORT: lattice-resource execution identity differs")
s=x.get("status",{}); done=[row for row in s.get("conditions",[]) if row.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0 or not s.get("completionTime"):
 raise SystemExit("ABORT: lattice-resource execution is not terminal successful")
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ABORT: lattice-resource task shape differs")
c=containers[0]; expected=["scripts/run_constraint_lattice_resource_preflight.py","--output-uri",uri]
if c.get("image")!=m["image"] or c.get("command")!=["python"] or c.get("args")!=expected:
 raise SystemExit("ABORT: lattice-resource image/command differs")
env={row.get("name"):str(row.get("value","")) for row in c.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]} or c.get("resources",{}).get("limits")!={"cpu":"4","memory":"16Gi"} or task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="43200" or task.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: lattice-resource execution contract differs")
messages=[str(row.get("textPayload","")) for row in logs]
markers=[]
for block in ("R0","R1","R2","R3","R4"):
 expected_marker=f"CONSTRAINT_LATTICE_FOLD_COMPLETE 2023 1 {block}"
 matches=[message for message in messages if expected_marker in message]
 if len(matches)!=1: raise SystemExit("ABORT: lattice-resource fold markers differ")
 markers.append(block)
protocol_marker=f"CONSTRAINT_LATTICE_RESOURCE_PROTOCOL_SHA256 {m['protocol_sha256']}"
if sum(protocol_marker in message for message in messages)!=1:
 raise SystemExit("ABORT: lattice-resource protocol marker differs")
if not str(obj.get("generation","")).isdigit() or int(obj.get("size",0))<=0:
 raise SystemExit("ABORT: lattice-resource object metadata differs")
print("CONSTRAINT_LATTICE_RESOURCE_MECHANICS_VALIDATED",execution)
PY

mv "$OUT/execution-metadata.pending.json" "$OUT/execution-metadata.json"
mv "$OUT/logs.pending.json" "$OUT/logs.json"
mv "$OUT/object-metadata.pending.json" "$OUT/object-metadata.json"
sha256sum "$OUT/execution-metadata.json" "$OUT/logs.json" \
  "$OUT/object-metadata.json" > "$OUT/evidence.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'status=True' 'disposition=full-cell-complete-at-16g' 'cell=2023-1' \
  'fold_markers=5' 'object_present=true' 'object_content_inspected=false' \
  'cpu=4' 'memory=16Gi' 'task_max_retries=0' \
  'uses_realized_outcomes=false' 'effect_fields_inspected=false' \
  'production_change_licensed=false' > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "CONSTRAINT_LATTICE_RESOURCE_PREFLIGHT_HARVESTED $EXEC"
