#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair1
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] || {
  echo "ABORT: ATLAS MVP launch receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 3 ] || {
  echo "ABORT: ATLAS MVP requires three season executions" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution-metadata" ] || {
  echo "ABORT: immutable ATLAS MVP harvest already exists" >&2; exit 3; }
mkdir -p "$OUT/execution-metadata"

while read -r SEASON JOB EXEC URI; do
  TARGET="$OUT/execution-metadata/${EXEC}.json"
  TMP="$TARGET.pending"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$TMP"
  "$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" "$EXEC" "$SEASON" "$URI" <<'PY'
import json, sys
x=json.load(open(sys.argv[1], encoding="utf-8"))
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
name, season, uri=sys.argv[3],sys.argv[4],sys.argv[5]
if x.get("metadata",{}).get("name") != name:
 raise SystemExit("ABORT: ATLAS MVP execution name differs")
status=x.get("status",{}); completed=[r for r in status.get("conditions",[]) if r.get("type")=="Completed"]
if len(completed)!=1 or completed[0].get("status")!="True" or int(status.get("succeededCount") or 0)!=1 or int(status.get("failedCount") or 0)!=0 or not status.get("completionTime"):
 raise SystemExit("ABORT: ATLAS MVP execution is not terminal successful")
spec=x.get("spec",{}); template=spec.get("template",{}).get("spec",{}); containers=template.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ABORT: ATLAS MVP execution task shape differs")
c=containers[0]
if c.get("image")!=m["image"] or c.get("command")!=["python"] or c.get("args")!=["scripts/run_atlas_matched_diversity_mvp.py","--season",season,"--output-uri",uri]:
 raise SystemExit("ABORT: ATLAS MVP image/command differs")
env={r.get("name"):str(r.get("value","")) for r in c.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]}:
 raise SystemExit("ABORT: ATLAS MVP execution environment differs")
if c.get("resources",{}).get("limits")!={"cpu":"8","memory":"32Gi"} or template.get("maxRetries")!=0 or str(template.get("timeoutSeconds"))!="28800" or template.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS MVP resources/account differ")
print("ATLAS_MVP_EXECUTION_VALIDATED",name)
PY
  mv "$TMP" "$TARGET"
  sha256sum "$TARGET" > "$TARGET.sha256"
  REPORT_TMP="$OUT/season-${SEASON}.pending.json"
  gcloud storage cp "$URI" "$REPORT_TMP" --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - "$REPORT_TMP" "$MANIFEST" "$SEASON" <<'PY'
import json, sys
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line); season=int(sys.argv[3])
if r.get("version")!="atlas-matched-diversity-mvp-v1" or r.get("uses_realized_outcomes") is not False or r.get("season")!=season or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"] or len(r.get("slates",[]))!=18:
 raise SystemExit("ABORT: ATLAS MVP season report identity differs")
hashes=r.get("source_hashes",{})
expected={"2026-08-16-atlas-matched-diversity-mvp-protocol.md":m["protocol_sha256"],"2026-08-16-atlas-mvp-pair-reach-amendment.md":m["pair_reach_amendment_sha256"],"2026-08-16-atlas-mvp-image-packaging-repair.md":m["packaging_repair_sha256"],"validation.json":m["repair_validation_sha256"],"execution.json":m["repair_execution_sha256"],"completion.txt":m["repair_completion_sha256"]}
for name,value in expected.items():
 if [digest for path,digest in hashes.items() if path.endswith("/"+name) or path=="reports/"+name] != [value]:
  raise SystemExit("ABORT: ATLAS MVP frozen-source binding differs")
if any(row.get("mechanical_valid") is not True or row.get("uses_realized_outcomes") is not False or int(row.get("global_atlas_additions",0))!=200 or set(row.get("native_boom_counts",{}).values())!={40} for row in r["slates"]):
 raise SystemExit("ABORT: ATLAS MVP season mechanics differ")
print("ATLAS_MVP_SEASON_VALIDATED",season)
PY
  mv "$REPORT_TMP" "$OUT/season-${SEASON}.json"
  sha256sum "$OUT/season-${SEASON}.json" > "$OUT/season-${SEASON}.sha256"
done < "$EXECUTIONS"

REPORT_TMP="$OUT/report.pending.json"
PREFIX=$(awk -F= '$1=="output_prefix" {print $2}' "$MANIFEST")
"$ROOT/.venv/bin/python" "$ROOT/scripts/aggregate_atlas_matched_diversity_mvp.py" \
  --season-report "$OUT/season-2023.json" \
  --season-report "$OUT/season-2024.json" \
  --season-report "$OUT/season-2025.json" \
  --output "$REPORT_TMP" --output-uri "$PREFIX/report.json"
"$ROOT/.venv/bin/python" - "$REPORT_TMP" "$MANIFEST" <<'PY'
import json, math, sys
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
if r.get("version")!="atlas-matched-diversity-mvp-v1" or r.get("uses_realized_outcomes") is not False or r.get("production_change_licensed") is not False or r.get("historical_arm_licensed") is not False or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"]:
 raise SystemExit("ABORT: ATLAS MVP aggregate identity/license differs")
mechanical=r.get("mechanical",{}); gate=r.get("gate",{}); conditions=gate.get("conditions",{})
expected={"conditional_pair_weight_strictly_higher","candidate_pair_reach_retains_100pct","conditional_stack_core_retains_90pct","candidate_pool_p210_strictly_higher_aggregate","candidate_pool_p210_higher_at_least_three_blocks","candidate_pool_p230_retains_95pct","exact80_p194_retains_90pct","exact80_p230_retains_90pct"}
if mechanical!={"seasons":[2023,2024,2025],"slates":54,"all_valid":True,"all_global_atlas_additions_200":True,"all_native_boom_counts_40":True} or set(conditions)!=expected or gate.get("passes_scorefree_gate") is not all(conditions.values()) or len(r.get("slates",[]))!=54:
 raise SystemExit("ABORT: ATLAS MVP aggregate mechanics/gate differs")
reach=gate.get("candidate_pair_reach",{})
if set(reach)!={"P1_mean_unique_pairs","P2_mean_unique_pairs","P2_over_P1"} or not all(math.isfinite(float(value)) for value in reach.values()):
 raise SystemExit("ABORT: ATLAS MVP pair-reach gate receipt differs")
if any(row.get("uses_realized_outcomes") is not False for row in r["slates"]):
 raise SystemExit("ABORT: ATLAS MVP aggregate contains outcome-facing row")
print("ATLAS_MVP_AGGREGATE_VALIDATED",f"passes={gate['passes_scorefree_gate']}")
PY
mv "$REPORT_TMP" "$OUT/report.json"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
sha256sum "$OUT"/execution-metadata/*.json | sort > "$OUT/execution-metadata.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=3' 'seasons=2023,2024,2025' 'slates=54' \
  'uses_realized_outcomes=false' > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_MATCHED_DIVERSITY_MVP_HARVESTED $RUN_ID"
