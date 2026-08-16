#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair4
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
EXECUTIONS="$OUT/executions.txt"
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"

[ -s "$MANIFEST" ] && [ -s "$EXECUTIONS" ] && \
  [ -s "$OUT/smoke-execution.json" ] && [ -s "$OUT/smoke-log.json" ] || {
  echo "ABORT: ATLAS repair4 launch/smoke receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$EXECUTIONS")" = 54 ] || {
  echo "ABORT: ATLAS repair4 execution grid is not 54" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution-metadata" ] && \
  [ ! -e "$OUT/shards" ] || {
  echo "ABORT: immutable ATLAS repair4 harvest already exists" >&2; exit 3; }

PREFIX=$(awk -F= '$1=="output_prefix" {print $2}' "$MANIFEST")
VERIFY_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX" --verify-only)
GRID_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX")

"$ROOT/.venv/bin/python" - "$MANIFEST" "$EXECUTIONS" \
  "$OUT/smoke-execution.json" "$OUT/smoke-log.json" \
  "$VERIFY_COMMAND" "$GRID_COMMAND" <<'PY'
from hashlib import sha256
import json, re, sys

manifest=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[1],encoding="utf-8") if "=" in line)
rows=[line.split() for line in open(sys.argv[2],encoding="utf-8") if line.strip()]
smoke=json.load(open(sys.argv[3],encoding="utf-8")); logs=json.load(open(sys.argv[4],encoding="utf-8"))
verify_command,grid_command=sys.argv[5:]
expected_fixed={
 "run_id":"20260816-atlas-matched-diversity-mvp-v1-repair4",
 "image":"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb",
 "code_sha":"60f296fdad769b30c0bb7334118698f156e462b9",
 "output_prefix":"gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair4",
 "protocol_sha256":"badc0d64be69694caadd8fb2fe16a293c0cfbfe1f7813b4e80dc45e10b727abf",
 "pair_reach_amendment_sha256":"2e3734c595159d64748ab2eeec2de61194b665d43ef6854140e5378bac464a33",
 "packaging_repair_sha256":"e4293fae2dcd88b7a50179f0b4a688a23a8b1961bd7da8e437544e15a64e0e62",
 "sharding_repair_sha256":"a2139969e3bede2b304c0a8469bed7c7839b8ecb98da05221a005ddb2c9cbf68",
 "resource_repair3_protocol_sha256":"95c33b8aa64aeb8e0a7740471f85b5006d3a8e34ff250375f97994ad05d33b3d",
 "output_prefix_repair4_protocol_sha256":"5e84a6b93522fd959e798e90da307687179327b23c474fbda6b5303d0483063a",
 "repair3_failure_summary_sha256":"4da1f34de96f8ae9224d8c330abeae9ec3ade562c512e58f8e9ad60e6e8d4558",
 "repair3_failure_completion_sha256":"8dc630d58fae604b466792563402daff5a0801305eafde2c5e742c2d4686b149",
 "repair_validation_sha256":"4938df8c8f7f84dea40baf2f76cd84f78cdc9e1a097c271b419e3dc8c6b5cd37",
 "repair_execution_sha256":"f2bb244daf1b2d9515bee59799095fcbdd44414acb16b06e65e8298bd87c62b7",
 "repair_completion_sha256":"7bbff5dd3721ba436f79cb984091e7aa5815642629ab2c5615a6f2d9aacaa592",
 "resource_result_sha256":"241eeeb8278945ceadac78ea7ad1dcd40ea8ddb597590d4b9e3bae92d6153e05",
 "resource_summary_sha256":"c467332d78b09589680e9354ef9454d6c3f14a0193d4db15b559dde55af1472a",
 "resource_completion_sha256":"2412fa80e01e98633ded7224f544f2b5f19ff47c04971d8fc6e99d0413777ff1",
 "preflight_protocol_sha256":"4c09ba4065e5ac32af3873f149ca42c0dd922cadc21524fd277f404d7fdc45a7",
 "preflight_manifest_sha256":"059cf942a06de76815151e34db1ba363535c17c2069e1ce7bd19486804a8334f",
 "preflight_execution_sha256":"00a50351f571a606e8efb47ae8eea0134c911998e64fe85e9836cf0677dd5ae3",
 "preflight_summary_sha256":"54e659421cd4ebe59f0d0219e1dd9a9db6774e6161c681f24f39b667e964228f",
 "preflight_completion_sha256":"07157e8e1589eaeb903ae5d7d124b677904061c11cdcc8567fab6649a1d317a9",
 "runner_source_sha256":"0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740",
 "renderer_sha256":"69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671",
 "uses_realized_outcomes":"false", "production_change_licensed":"false",
 "seasons":"2023,2024,2025", "weeks":"1-18", "slates":"54",
 "cpu":"4", "memory":"16Gi", "timeout_seconds":"43200",
 "max_retries":"0", "repair_treatment":"output-prefix-transport-only",
 "interaction_auxiliaries":"binary",
}
for key,value in expected_fixed.items():
 if manifest.get(key)!=value:
  raise SystemExit(f"ABORT: ATLAS repair4 manifest differs: {key}")
for key,command in (("verify_command_sha256",verify_command),("grid_command_sha256",grid_command)):
 if manifest.get(key)!=sha256(command.encode()).hexdigest():
  raise SystemExit(f"ABORT: ATLAS repair4 rendered command differs: {key}")
expected_cells={(str(s),str(w)) for s in (2023,2024,2025) for w in range(1,19)}
if len(rows)!=54 or {(r[0],r[1]) for r in rows}!=expected_cells or any(len(r)!=5 for r in rows):
 raise SystemExit("ABORT: ATLAS repair4 cell ledger differs")
for season,week,job,execution,uri in rows:
 if job!=f"atlas-md-s{season}-w{week}-r4" or not execution.startswith(job+"-") or uri!=f"{manifest['output_prefix']}/slate-{season}-{week}.json":
  raise SystemExit("ABORT: ATLAS repair4 execution identity differs")
s=smoke.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0:
 raise SystemExit("ABORT: ATLAS repair4 smoke status differs")
marker="ATLAS_REPAIR4_PREFIX_PATCH_VERIFIED"
matches=[row.get("textPayload","") for row in logs if marker in row.get("textPayload","")]
if len(matches)!=1 or manifest["runner_source_sha256"] not in matches[0] or manifest["output_prefix"] not in matches[0]:
 raise SystemExit("ABORT: ATLAS repair4 smoke marker differs")
PY

mkdir -p "$OUT/execution-metadata.pending" "$OUT/shards.pending"
while read -r SEASON WEEK JOB EXEC URI; do
  TARGET="$OUT/execution-metadata.pending/${EXEC}.json"
  gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
    --region "$REGION" --format=json > "$TARGET"
  "$ROOT/.venv/bin/python" - "$TARGET" "$MANIFEST" "$GRID_COMMAND" \
    "$EXEC" "$SEASON" "$WEEK" "$URI" <<'PY'
import json, sys
x=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
command,name,season,week,uri=sys.argv[3:]
if x.get("metadata",{}).get("name")!=name:
 raise SystemExit("ABORT: ATLAS repair4 execution name differs")
s=x.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0 or not s.get("completionTime"):
 raise SystemExit("ABORT: ATLAS repair4 execution is not terminal successful")
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ABORT: ATLAS repair4 task shape differs")
container=containers[0]
expected_args=["-c",command,"--season",season,"--week",week,"--output-uri",uri]
if container.get("image")!=m["image"] or container.get("command")!=["python"] or container.get("args")!=expected_args:
 raise SystemExit("ABORT: ATLAS repair4 image/command differs")
env={r.get("name"):str(r.get("value","")) for r in container.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]}:
 raise SystemExit("ABORT: ATLAS repair4 environment differs")
if container.get("resources",{}).get("limits")!={"cpu":"4","memory":"16Gi"} or task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="43200" or task.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS repair4 resources/account differ")
PY
  SHARD="$OUT/shards.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage cp "$URI" "$SHARD" --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - "$SHARD" "$MANIFEST" "$SEASON" "$WEEK" <<'PY'
import json, sys
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line); season=int(sys.argv[3]); week=int(sys.argv[4])
if r.get("version")!="atlas-matched-diversity-mvp-v1" or r.get("uses_realized_outcomes") is not False or r.get("season")!=season or r.get("shard_week")!=week or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"] or len(r.get("slates",[]))!=1:
 raise SystemExit("ABORT: ATLAS repair4 shard identity differs")
row=r["slates"][0]
if row.get("season")!=season or row.get("week")!=week or row.get("mechanical_valid") is not True or row.get("uses_realized_outcomes") is not False or row.get("global_atlas_additions")!=200 or set(row.get("native_boom_counts",{}).values())!={40}:
 raise SystemExit("ABORT: ATLAS repair4 shard mechanics differ")
hashes=r.get("source_hashes",{})
expected={"2026-08-16-atlas-matched-diversity-mvp-protocol.md":m["protocol_sha256"],"2026-08-16-atlas-mvp-pair-reach-amendment.md":m["pair_reach_amendment_sha256"],"2026-08-16-atlas-mvp-image-packaging-repair.md":m["packaging_repair_sha256"],"2026-08-16-atlas-mvp-slate-sharding-repair.md":m["sharding_repair_sha256"],"validation.json":m["repair_validation_sha256"],"execution.json":m["repair_execution_sha256"],"completion.txt":m["repair_completion_sha256"]}
for source_name,value in expected.items():
 if [digest for path,digest in hashes.items() if path.endswith("/"+source_name) or path=="reports/"+source_name] != [value]:
  raise SystemExit("ABORT: ATLAS repair4 frozen-source binding differs")
PY
done < "$EXECUTIONS"

mv "$OUT/execution-metadata.pending" "$OUT/execution-metadata"
mv "$OUT/shards.pending" "$OUT/shards"
ARGS=()
for SHARD in "$OUT"/shards/slate-*.json; do ARGS+=(--shard-report "$SHARD"); done
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/aggregate_atlas_matched_diversity_shards.py" \
  "${ARGS[@]}" --output-dir "$OUT" --output-prefix="$PREFIX"

"$ROOT/.venv/bin/python" - "$OUT/report.json" "$MANIFEST" <<'PY'
import json, sys
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
if r.get("version")!="atlas-matched-diversity-mvp-v1" or r.get("uses_realized_outcomes") is not False or r.get("production_change_licensed") is not False or r.get("historical_arm_licensed") is not False or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"]:
 raise SystemExit("ABORT: ATLAS repair4 aggregate identity/license differs")
mechanical=r.get("mechanical",{}); gate=r.get("gate",{}); conditions=gate.get("conditions",{})
expected={"conditional_pair_weight_strictly_higher","candidate_pair_reach_retains_100pct","conditional_stack_core_retains_90pct","candidate_pool_p210_strictly_higher_aggregate","candidate_pool_p210_higher_at_least_three_blocks","candidate_pool_p230_retains_95pct","exact80_p194_retains_90pct","exact80_p230_retains_90pct"}
if mechanical!={"seasons":[2023,2024,2025],"slates":54,"all_valid":True,"all_global_atlas_additions_200":True,"all_native_boom_counts_40":True} or set(conditions)!=expected or gate.get("passes_scorefree_gate") is not all(conditions.values()) or len(r.get("slates",[]))!=54:
 raise SystemExit("ABORT: ATLAS repair4 aggregate mechanics/gate differs")
if any(row.get("uses_realized_outcomes") is not False for row in r["slates"]):
 raise SystemExit("ABORT: ATLAS repair4 aggregate contains outcomes")
print("ATLAS_REPAIR4_AGGREGATE_VALIDATED",gate["passes_scorefree_gate"])
PY

sha256sum "$OUT"/season-*.json > "$OUT/season-reports.sha256"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
sha256sum "$OUT"/execution-metadata/*.json | sort > "$OUT/execution-metadata.sha256"
sha256sum "$OUT"/shards/*.json | sort > "$OUT/shards.sha256"
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'executions=54' 'seasons=2023,2024,2025' 'slates=54' \
  'cpu=4' 'memory=16Gi' 'max_retries=0' \
  'repair_treatment=output-prefix-transport-only' \
  'interaction_auxiliaries=binary' 'uses_realized_outcomes=false' \
  'production_change_licensed=false' > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_MATCHED_DIVERSITY_REPAIR4_HARVESTED $RUN_ID"
