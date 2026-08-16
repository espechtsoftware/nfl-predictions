#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-historical-score-diagnostic-v1
OUT="$ROOT/reports/atlas-historical-score-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTION="$OUT/execution.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTION" ] && [ -s "$OUT/upstream-receipt.json" ] || {
  echo "ABORT: ATLAS historical launch receipt is incomplete" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution.json" ] || {
  echo "ABORT: immutable ATLAS historical harvest already exists" >&2; exit 3; }
read -r JOB EXEC URI < "$EXECUTION"
TMP="$OUT/execution.pending.json"
gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$TMP"
"$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" "$EXEC" "$URI" <<'PY'
import json, sys
x=json.load(open(sys.argv[1],encoding="utf-8"))
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
name,uri=sys.argv[3],sys.argv[4]
if x.get("metadata",{}).get("name")!=name:
 raise SystemExit("ABORT: ATLAS historical execution name differs")
s=x.get("status",{}); c=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if len(c)!=1 or c[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0 or not s.get("completionTime"):
 raise SystemExit("ABORT: ATLAS historical execution is not terminal successful")
spec=x.get("spec",{}); t=spec.get("template",{}).get("spec",{}); cs=t.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(cs)!=1:
 raise SystemExit("ABORT: ATLAS historical task shape differs")
v=cs[0]
if v.get("image")!=m["image"] or v.get("command")!=["python"] or v.get("args")!=["scripts/run_atlas_historical_score_diagnostic.py","--upstream-receipt-uri",m["output_prefix"]+"/upstream-receipt.json","--output-uri",uri]:
 raise SystemExit("ABORT: ATLAS historical image/command differs")
env={r.get("name"):str(r.get("value","")) for r in v.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]}:
 raise SystemExit("ABORT: ATLAS historical execution environment differs")
if v.get("resources",{}).get("limits")!={"cpu":"8","memory":"32Gi"} or t.get("maxRetries")!=0 or str(t.get("timeoutSeconds"))!="28800" or t.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS historical resources/account differ")
print("ATLAS_HISTORICAL_EXECUTION_VALIDATED",name)
PY
mv "$TMP" "$OUT/execution.json"
sha256sum "$OUT/execution.json" > "$OUT/execution.sha256"

REPORT_TMP="$OUT/report.pending.json"
gcloud storage cp "$URI" "$REPORT_TMP" --project "$PROJECT" >/dev/null
PYTHONPATH="$ROOT/src" "$ROOT/.venv/bin/python" - "$REPORT_TMP" "$MANIFEST" <<'PY'
import json, sys
from nfl_dfs.analysis.atlas_historical_score import aggregate_diagnostic
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
if r.get("version")!="atlas-historical-score-diagnostic-v1" or r.get("uses_realized_outcomes") is not True or r.get("production_change_licensed") is not False or r.get("scorer_code_sha")!=m["code_sha"] or r.get("scorer_image")!=m["image"] or r.get("protocol_sha256")!=m["protocol_sha256"] or r.get("source_parity_amendment_sha256")!=m["source_parity_amendment_sha256"] or r.get("sharded_upstream_amendment_sha256")!=m["sharded_upstream_amendment_sha256"] or r.get("cbc_retry_protocol_sha256")!=m["cbc_retry_protocol_sha256"] or r.get("high_tail_guard_amendment_sha256")!=m["high_tail_guard_amendment_sha256"]:
 raise SystemExit("ABORT: ATLAS historical report identity/license differs")
if r.get("population")!={"seasons":[2023,2024,2025],"slates":54} or len(r.get("rows",[]))!=54:
 raise SystemExit("ABORT: ATLAS historical population differs")
u=r.get("upstream",{}); receipt=u.get("receipt_object",{})
expected_executions={f"{season}-{week}" for season in (2023,2024,2025) for week in range(1,19)}
if receipt.get("uri")!=m["output_prefix"]+"/upstream-receipt.json" or receipt.get("sha256")!=m["upstream_receipt_sha256"] or not str(receipt.get("generation","")).isdigit() or u.get("code_sha")!=m["upstream_code_sha"] or u.get("image")!=m["upstream_image"] or set(u.get("executions",{}))!=expected_executions:
 raise SystemExit("ABORT: ATLAS historical upstream receipt binding differs")
p=r.get("native_actual_score_parity",{})
if p.get("registered_candidate_rows")!=68199 or p.get("compared_rows")!=68199 or p.get("slots_per_roster")!=9 or p.get("malformed_rosters")!=0 or p.get("missing_player_outcomes")!=0 or float(p.get("maximum_absolute_error",1))>1e-9 or float(p.get("absolute_tolerance",-1))!=1e-9 or float(p.get("relative_tolerance",-1))!=0.0 or p.get("source_storage_type")!="FLOAT":
 raise SystemExit("ABORT: ATLAS historical actual-score parity differs")
if r.get("source_artifacts",{}).get("count")!=270:
 raise SystemExit("ABORT: ATLAS historical source artifact count differs")
expected=aggregate_diagnostic(r["rows"])
for key,value in expected.items():
 if r.get(key)!=value:
  raise SystemExit(f"ABORT: ATLAS historical aggregate differs at {key}")
gate=r.get("gate",{})
if set(gate)!={"selected_200_net","selected_210_net","selected_220_net","selected_230_net","selected_240_net","candidate_200_net","historical_tail_signal_positive","disposition"}:
 raise SystemExit("ABORT: ATLAS historical gate receipt differs")
print("ATLAS_HISTORICAL_REPORT_VALIDATED",gate["disposition"])
PY
mv "$REPORT_TMP" "$OUT/report.json"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=1' 'seasons=2023,2024,2025' 'slates=54' \
  'uses_realized_outcomes=true' 'production_change_licensed=false' \
  > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_HISTORICAL_SCORE_DIAGNOSTIC_HARVESTED $RUN_ID"
