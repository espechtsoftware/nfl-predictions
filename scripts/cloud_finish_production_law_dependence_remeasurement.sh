#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260817-production-law-dependence-remeasurement-v1
OUT="$ROOT/reports/production-law-dependence-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
RUNNER="$ROOT/scripts/run_production_law_dependence_remeasurement.py"
FINISHER="$ROOT/scripts/cloud_finish_production_law_dependence_remeasurement.sh"
[ -s "$MANIFEST" ] && [ -s "$OUT/execution.txt" ] || exit 2
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution.json" ] || exit 3
read -r JOB EXEC URI < "$OUT/execution.txt"
TMP=$(mktemp -d "$OUT/.harvest.XXXXXX")
trap 'rm -rf -- "$TMP"' EXIT
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$TMP/execution.json"
gcloud storage objects describe "$URI" --project "$PROJECT" --format=json \
  > "$TMP/object-metadata.json"
gcloud storage cp "$URI" "$TMP/report.json" --project "$PROJECT" >/dev/null

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" - \
 "$TMP/execution.json" "$TMP/object-metadata.json" "$TMP/report.json" \
 "$MANIFEST" "$JOB" "$EXEC" "$URI" "$RUNNER" "$FINISHER" <<'PY'
from hashlib import sha256
import json,sys
from pathlib import Path
from nfl_dfs.analysis.production_law_dependence import aggregate_remeasurement

execution_path,object_path,report_path,manifest_path=map(Path,sys.argv[1:5])
job,execution,uri=sys.argv[5:8]; runner,finisher=map(Path,sys.argv[8:10])
m=dict(line.split("=",1) for line in manifest_path.read_text().splitlines() if "=" in line)
fixed={
 "run_id":"20260817-production-law-dependence-remeasurement-v1",
 "uses_realized_outcomes":"true","candidate_or_lineup_scores_read":"false",
 "production_change_licensed":"false","blocks":"5","worlds_per_block":"10000",
 "aggregate_worlds":"50000","candidate_rows":"68199",
 "candidate_union_rows":"10729","eligible_rows":"9469",
 "slates":"54","cpu":"8","memory":"32Gi",
 "timeout_seconds":"14400","max_retries":"0",
}
if any(m.get(k)!=v for k,v in fixed.items()) or \
 m.get("runner_sha256")!=sha256(runner.read_bytes()).hexdigest() or \
 m.get("finisher_sha256")!=sha256(finisher.read_bytes()).hexdigest():
 raise SystemExit("ABORT: production-law dependence manifest differs")
x=json.loads(execution_path.read_text()); s=x.get("status",{})
completed=[row for row in s.get("conditions",[]) if row.get("type")=="Completed"]
if x.get("metadata",{}).get("name")!=execution or len(completed)!=1 or \
 completed[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or \
 int(s.get("failedCount") or 0)!=0 or not s.get("completionTime"):
 raise SystemExit("ABORT: production-law dependence execution failed")
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if len(containers)!=1 or spec.get("parallelism")!=1 or spec.get("taskCount")!=1:
 raise SystemExit("ABORT: production-law dependence task differs")
c=containers[0]; env={row.get("name"):str(row.get("value","")) for row in c.get("env",[])}
expected_args=[
 "scripts/run_production_law_dependence_remeasurement.py",
 "--source-lock-uri",m["source_lock_uri"],
 "--source-lock-generation",m["source_lock_generation"],
 "--source-lock-sha256",m["source_lock_sha256"],"--output-uri",uri,
]
if job!="dependence-forest-2023" or c.get("image")!=m["image"] or \
 c.get("command")!=["python"] or c.get("args")!=expected_args or \
 env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]} or \
 c.get("resources",{}).get("limits")!={"cpu":"8","memory":"32Gi"} or \
 task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="14400":
 raise SystemExit("ABORT: production-law dependence execution contract differs")
raw=report_path.read_bytes(); o=json.loads(object_path.read_text()); r=json.loads(raw)
if int(o.get("size",-1))!=len(raw) or r.get("run_id")!=m["run_id"] or \
 r.get("protocol_sha256")!=m["protocol_sha256"] or r.get("code_sha")!=m["code_sha"] or \
 r.get("source_population_amendment_sha256")!=m["source_population_amendment_sha256"] or \
 r.get("analysis_image")!=m["image"] or r.get("uses_realized_outcomes") is not True or \
 r.get("candidate_or_lineup_scores_read") is not False or \
 r.get("production_change_licensed") is not False or \
 r.get("source_lock",{}).get("generation")!=m["source_lock_generation"] or \
 r.get("source_lock",{}).get("sha256")!=m["source_lock_sha256"] or \
 len(r.get("source_artifacts",[]))!=270 or r.get("outcome_population",{}).get("slates")!=54 or \
 r.get("outcome_population",{}).get("missing_eligible_outcomes")!=0 or \
 r.get("outcome_population",{}).get("duplicate_eligible_keys")!=0 or \
 r.get("outcome_query_issued_after_complete_source_preflight") is not True:
 raise SystemExit("ABORT: production-law dependence report contract differs")
expected=aggregate_remeasurement(r["blocks"],r["aggregate"])
for key,value in expected.items():
 if r.get(key)!=value:
  raise SystemExit(f"ABORT: production-law dependence aggregate differs at {key}")
if set(r.get("gate",{}).get("conditions",{}))!={
 "aggregate_qb_wr_under_coupled","qb_wr_under_coupled_in_at_least_three_blocks",
 "aggregate_multiplicity_ge3_over_coupled",
 "multiplicity_ge3_over_coupled_in_at_least_three_blocks",
}:
 raise SystemExit("ABORT: production-law dependence frozen gate differs")
print("PRODUCTION_LAW_DEPENDENCE_REMEASUREMENT_VALIDATED",r["gate"]["disposition"])
PY

mv "$TMP/execution.json" "$OUT/execution.json"
mv "$TMP/object-metadata.json" "$OUT/object-metadata.json"
mv "$TMP/report.json" "$OUT/report.json"
trap - EXIT
rmdir "$TMP"
sha256sum "$OUT/execution.json" > "$OUT/execution-metadata.sha256"
sha256sum "$OUT/object-metadata.json" > "$OUT/object-metadata.sha256"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
DISPOSITION=$($ROOT/.venv/bin/python -c \
 'import json,sys; print(json.load(open(sys.argv[1]))["gate"]["disposition"])' "$OUT/report.json")
printf '%s\n' "run_id=$RUN_ID" "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
 'uses_realized_outcomes=true' 'production_change_licensed=false' \
 'blocks=5' 'slates=54' "disposition=$DISPOSITION" > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "PRODUCTION_LAW_DEPENDENCE_REMEASUREMENT_HARVESTED $DISPOSITION"
