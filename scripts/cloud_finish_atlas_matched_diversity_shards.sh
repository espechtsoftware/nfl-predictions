#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair2
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
ORIGINAL_EXECUTIONS="$OUT/executions.txt"
EXECUTIONS="$OUT/effective-executions.txt"
RETRY_PROTOCOL="$ROOT/reports/2026-08-16-atlas-mvp-cbc-single-shard-retry.md"
RETRY_PROTOCOL_SHA=bc55775c5a98a7027a0c117cf5371a67cc886c6da34dcdb7b1031bd6a471c455
ORIGINAL_EXECUTIONS_SHA=6794f8e608497613aec2f06f2bd13e57cf08b945d7ac20e2d4d00eb1ee3d5ea5
EFFECTIVE_EXECUTIONS_SHA=cb7d54fa9dd3dd9a61a19006477ae6cc974ca0597966eb88385723905031bbfd
FAILED_EXECUTION_SHA=28b6f509d22d1b217ccf995f80e337d14f370f97b67ee7e319886a1b7e29191f
FAILED_LOG_SHA=fe9c3d0a542c5e651b3c522b9154213d8cea47d5ac0b48650e0c5cd765e26249
REPLACEMENT_RECEIPT_SHA=f71831c7f81850493a7b418427cb5dcfac5e06c3871ba2f270222d65a6eb575d

[ -s "$MANIFEST" ] && [ -s "$ORIGINAL_EXECUTIONS" ] && \
  [ -s "$EXECUTIONS" ] && [ -s "$OUT/failed-execution.json" ] && \
  [ -s "$OUT/failed-log.json" ] && \
  [ -s "$OUT/replacement-execution.txt" ] || {
  echo "ABORT: ATLAS MVP shard launch receipt is incomplete" >&2; exit 2; }
[ "$(sha256sum "$RETRY_PROTOCOL" | awk '{print $1}')" = "$RETRY_PROTOCOL_SHA" ] && \
  [ "$(sha256sum "$ORIGINAL_EXECUTIONS" | awk '{print $1}')" = "$ORIGINAL_EXECUTIONS_SHA" ] && \
  [ "$(sha256sum "$EXECUTIONS" | awk '{print $1}')" = "$EFFECTIVE_EXECUTIONS_SHA" ] && \
  [ "$(sha256sum "$OUT/failed-execution.json" | awk '{print $1}')" = "$FAILED_EXECUTION_SHA" ] && \
  [ "$(sha256sum "$OUT/failed-log.json" | awk '{print $1}')" = "$FAILED_LOG_SHA" ] && \
  [ "$(sha256sum "$OUT/replacement-execution.txt" | awk '{print $1}')" = "$REPLACEMENT_RECEIPT_SHA" ] || {
  echo "ABORT: ATLAS MVP CBC retry receipt differs" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ABORT: ATLAS MVP shard execution grid is not 54" >&2; exit 2; }
"$ROOT/.venv/bin/python" - "$ORIGINAL_EXECUTIONS" "$EXECUTIONS" \
  "$OUT/failed-execution.json" "$OUT/failed-log.json" \
  "$OUT/replacement-execution.txt" <<'PY'
import json, sys
original=[line.split() for line in open(sys.argv[1],encoding="utf-8") if line.strip()]
effective=[line.split() for line in open(sys.argv[2],encoding="utf-8") if line.strip()]
failed=json.load(open(sys.argv[3],encoding="utf-8")); logs=json.load(open(sys.argv[4],encoding="utf-8"))
replacement=open(sys.argv[5],encoding="utf-8").read().split()
diffs=[(a,b) for a,b in zip(original,effective,strict=True) if a!=b]
if len(original)!=54 or len(effective)!=54 or len(diffs)!=1:
 raise SystemExit("ABORT: ATLAS effective execution ledger differs")
a,b=diffs[0]
if a[:3]+a[4:]!=b[:3]+b[4:] or a[:2]!=["2024","7"] or a[3]!="atlas-md-s2024-w7-r2-r9gnq" or b[3]!="atlas-md-s2024-w7-r2-6l2q2" or replacement!=b:
 raise SystemExit("ABORT: ATLAS replacement cell differs")
s=failed.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if failed.get("metadata",{}).get("name")!=a[3] or len(done)!=1 or done[0].get("status")!="False" or done[0].get("reason")!="NonZeroExitCode" or int(s.get("failedCount") or 0)!=1:
 raise SystemExit("ABORT: ATLAS original failure differs")
raw=json.dumps(logs,sort_keys=True)
if "PulpSolverError" not in raw or "ATLAS_MVP_SEED_COMPLETE" in raw or "ATLAS_MVP_SLATE_COMPLETE" in raw:
 raise SystemExit("ABORT: ATLAS original failure log differs")
PY
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution-metadata" ] && \
    [ ! -e "$OUT/shards" ] || {
  echo "ABORT: immutable ATLAS MVP shard harvest already exists" >&2; exit 3; }
mkdir -p "$OUT/execution-metadata" "$OUT/shards"

while read -r SEASON WEEK JOB EXEC URI; do
  TARGET="$OUT/execution-metadata/${EXEC}.json"
  TMP="$TARGET.pending"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$TMP"
  "$ROOT/.venv/bin/python" - "$TMP" "$MANIFEST" "$EXEC" "$SEASON" "$WEEK" "$URI" <<'PY'
import json, sys
x=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
name,season,week,uri=sys.argv[3],sys.argv[4],sys.argv[5],sys.argv[6]
if x.get("metadata",{}).get("name")!=name:
 raise SystemExit("ABORT: ATLAS MVP shard execution name differs")
s=x.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0 or not s.get("completionTime"):
 raise SystemExit("ABORT: ATLAS MVP shard execution is not terminal successful")
spec=x.get("spec",{}); t=spec.get("template",{}).get("spec",{}); cs=t.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(cs)!=1:
 raise SystemExit("ABORT: ATLAS MVP shard task shape differs")
c=cs[0]
if c.get("image")!=m["image"] or c.get("command")!=["python"] or c.get("args")!=["scripts/run_atlas_matched_diversity_mvp.py","--season",season,"--week",week,"--output-uri",uri]:
 raise SystemExit("ABORT: ATLAS MVP shard image/command differs")
env={r.get("name"):str(r.get("value","")) for r in c.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]}:
 raise SystemExit("ABORT: ATLAS MVP shard environment differs")
if c.get("resources",{}).get("limits")!={"cpu":"1","memory":"4Gi"} or t.get("maxRetries")!=0 or str(t.get("timeoutSeconds"))!="43200" or t.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS MVP shard resources/account differ")
PY
  mv "$TMP" "$TARGET"
  sha256sum "$TARGET" > "$TARGET.sha256"
  SHARD="$OUT/shards/slate-${SEASON}-${WEEK}.json"
  gcloud storage cp "$URI" "$SHARD.pending" --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - "$SHARD.pending" "$MANIFEST" "$SEASON" "$WEEK" <<'PY'
import json, sys
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line); season=int(sys.argv[3]); week=int(sys.argv[4])
if r.get("version")!="atlas-matched-diversity-mvp-v1" or r.get("uses_realized_outcomes") is not False or r.get("season")!=season or r.get("shard_week")!=week or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"] or len(r.get("slates",[]))!=1:
 raise SystemExit("ABORT: ATLAS MVP shard report identity differs")
row=r["slates"][0]
if row.get("season")!=season or row.get("week")!=week or row.get("mechanical_valid") is not True or row.get("uses_realized_outcomes") is not False or row.get("global_atlas_additions")!=200 or set(row.get("native_boom_counts",{}).values())!={40}:
 raise SystemExit("ABORT: ATLAS MVP shard mechanics differ")
hashes=r.get("source_hashes",{})
expected={"2026-08-16-atlas-matched-diversity-mvp-protocol.md":m["protocol_sha256"],"2026-08-16-atlas-mvp-pair-reach-amendment.md":m["pair_reach_amendment_sha256"],"2026-08-16-atlas-mvp-image-packaging-repair.md":m["packaging_repair_sha256"],"2026-08-16-atlas-mvp-slate-sharding-repair.md":m["sharding_repair_sha256"],"validation.json":m["repair_validation_sha256"],"execution.json":m["repair_execution_sha256"],"completion.txt":m["repair_completion_sha256"]}
for name,value in expected.items():
 if [digest for path,digest in hashes.items() if path.endswith("/"+name) or path=="reports/"+name] != [value]:
  raise SystemExit("ABORT: ATLAS MVP shard frozen-source binding differs")
PY
  mv "$SHARD.pending" "$SHARD"
  sha256sum "$SHARD" > "$SHARD.sha256"
done < "$EXECUTIONS"

ARGS=()
for SHARD in "$OUT"/shards/slate-*.json; do
  ARGS+=(--shard-report "$SHARD")
done
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/aggregate_atlas_matched_diversity_shards.py" \
  "${ARGS[@]}" --output-dir "$OUT" \
  --output-prefix "$(awk -F= '$1=="output_prefix" {print $2}' "$MANIFEST")"

"$ROOT/.venv/bin/python" - "$OUT/report.json" "$MANIFEST" <<'PY'
import json, math, sys
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
if r.get("version")!="atlas-matched-diversity-mvp-v1" or r.get("uses_realized_outcomes") is not False or r.get("production_change_licensed") is not False or r.get("historical_arm_licensed") is not False or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"]:
 raise SystemExit("ABORT: ATLAS MVP shard aggregate identity/license differs")
mech=r.get("mechanical",{}); gate=r.get("gate",{}); conditions=gate.get("conditions",{})
expected={"conditional_pair_weight_strictly_higher","candidate_pair_reach_retains_100pct","conditional_stack_core_retains_90pct","candidate_pool_p210_strictly_higher_aggregate","candidate_pool_p210_higher_at_least_three_blocks","candidate_pool_p230_retains_95pct","exact80_p194_retains_90pct","exact80_p230_retains_90pct"}
if mech!={"seasons":[2023,2024,2025],"slates":54,"all_valid":True,"all_global_atlas_additions_200":True,"all_native_boom_counts_40":True} or set(conditions)!=expected or gate.get("passes_scorefree_gate") is not all(conditions.values()) or len(r.get("slates",[]))!=54:
 raise SystemExit("ABORT: ATLAS MVP shard aggregate mechanics/gate differs")
if any(row.get("uses_realized_outcomes") is not False for row in r["slates"]):
 raise SystemExit("ABORT: ATLAS MVP shard aggregate contains outcomes")
print("ATLAS_MVP_SHARD_AGGREGATE_VALIDATED",gate["passes_scorefree_gate"])
PY

sha256sum "$OUT"/season-*.json > "$OUT/season-reports.sha256"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
sha256sum "$OUT"/execution-metadata/*.json | sort > "$OUT/execution-metadata.sha256"
sha256sum "$OUT"/shards/*.json | sort > "$OUT/shards.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=54' 'seasons=2023,2024,2025' 'slates=54' \
  'single_shard_replacement=2024-7' \
  'replacement_execution=atlas-md-s2024-w7-r2-6l2q2' \
  'uses_realized_outcomes=false' > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_MATCHED_DIVERSITY_SHARDS_HARVESTED $RUN_ID"
