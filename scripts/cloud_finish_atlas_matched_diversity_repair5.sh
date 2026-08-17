#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair5
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
MANIFEST="$OUT/manifest.txt"
PRIMARY_EXECUTIONS="$OUT/executions.txt"
RETRY_EXECUTIONS="$OUT/retry-executions.txt"
ACCEPTED_EXECUTIONS="$OUT/accepted-executions.txt"
ATTEMPT_RESOLUTION="$OUT/attempt-resolution.json"
ATTEMPT_CLASSIFICATION="$OUT/primary-attempt-classification.json"
AMENDMENT="$ROOT/reports/2026-08-16-atlas-repair5-bounded-platform-retry-amendment.md"
AMENDMENT_SHA=d464660b72e669d261d7f6d4800b3e59d55726b56e7003c5e3e806f38fa987a0
CANARY_AMENDMENT="$ROOT/reports/2026-08-16-atlas-repair5-real-path-canary-amendment.md"
CANARY_AMENDMENT_SHA=b2d0e32dabeb87bb1a67bee58c01f00c4c0d97e3fac9d1f7181bfcee50abc242
CANARY_VALIDATOR="$ROOT/scripts/cloud_wait_atlas_repair5_canary.sh"
CANARY_VALIDATOR_SHA=e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411
CANARY="$OUT/canary-completion.txt"
GRID_RELEASE="$OUT/grid-release.txt"
ATTEMPT_RESOLVER="$ROOT/scripts/cloud_prepare_atlas_matched_diversity_repair5_attempts.sh"
ATTEMPT_RESOLVER_SHA=705b65e5164b775361a2efe1440059f76978c3701c192179a40d85f4b0c27093
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"
PREFLIGHT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
R4="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair4"

[ -s "$AMENDMENT" ] && \
  [ "$(sha256sum "$AMENDMENT" | awk '{print $1}')" = "$AMENDMENT_SHA" ] && \
  [ -s "$CANARY_AMENDMENT" ] && \
  [ "$(sha256sum "$CANARY_AMENDMENT" | awk '{print $1}')" = "$CANARY_AMENDMENT_SHA" ] && \
  [ -s "$CANARY_VALIDATOR" ] && \
  [ "$(sha256sum "$CANARY_VALIDATOR" | awk '{print $1}')" = "$CANARY_VALIDATOR_SHA" ] && \
  [ -s "$ATTEMPT_RESOLVER" ] && \
  [ "$(sha256sum "$ATTEMPT_RESOLVER" | awk '{print $1}')" = "$ATTEMPT_RESOLVER_SHA" ] && \
  [ -s "$MANIFEST" ] && [ -s "$PRIMARY_EXECUTIONS" ] && \
  [ -e "$RETRY_EXECUTIONS" ] && [ -s "$ACCEPTED_EXECUTIONS" ] && \
  [ -s "$ATTEMPT_RESOLUTION" ] && [ -s "$ATTEMPT_CLASSIFICATION" ] && \
  [ -s "$CANARY" ] && [ -s "$OUT/canary-execution-metadata.json" ] && \
  [ -s "$OUT/canary-object-metadata.json" ] && \
  [ -s "$OUT/canary.sha256" ] && [ -s "$GRID_RELEASE" ] && \
  [ -s "$OUT/primary-execution-metadata.sha256" ] && \
  [ -s "$OUT/smoke-execution.json" ] && [ -s "$OUT/smoke-log.json" ] && \
  [ -s "$PREFLIGHT/completion.txt" ] && \
  [ -s "$PREFLIGHT/execution-metadata.json" ] && \
  [ -s "$PREFLIGHT/shard.json" ] && \
  [ -s "$R4/terminal-census.json" ] && \
  [ -s "$R4/terminal-census-completion.txt" ] || {
  echo "ABORT: ATLAS repair5 launch/attempt receipt is incomplete" >&2; exit 2; }
[ "$(wc -l < "$PRIMARY_EXECUTIONS")" = 54 ] && \
  [ "$(wc -l < "$ACCEPTED_EXECUTIONS")" = 54 ] || {
  echo "ABORT: ATLAS repair5 primary/accepted grid is not 54" >&2; exit 2; }
sha256sum -c "$OUT/primary-execution-metadata.sha256" >/dev/null || {
  echo "ABORT: ATLAS repair5 primary metadata differs" >&2; exit 2; }
[ ! -e "$OUT/report.json" ] && [ ! -e "$OUT/execution-metadata" ] && \
  [ ! -e "$OUT/shards" ] || {
  echo "ABORT: immutable ATLAS repair5 harvest already exists" >&2; exit 3; }

PREFIX=$(awk -F= '$1=="output_prefix" {print $2}' "$MANIFEST")
VERIFY_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX" --verify-only)
GRID_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX")

"$ROOT/.venv/bin/python" - "$MANIFEST" "$PRIMARY_EXECUTIONS" \
  "$RETRY_EXECUTIONS" "$ACCEPTED_EXECUTIONS" "$ATTEMPT_RESOLUTION" \
  "$ATTEMPT_CLASSIFICATION" "$AMENDMENT" "$ATTEMPT_RESOLVER" \
  "$OUT/smoke-execution.json" "$OUT/smoke-log.json" \
  "$VERIFY_COMMAND" "$GRID_COMMAND" "$PREFLIGHT" "$R4" \
  "$CANARY_AMENDMENT" "$CANARY_VALIDATOR" "$CANARY" "$GRID_RELEASE" <<'PY'
from hashlib import sha256
import json, pathlib, sys

manifest=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[1],encoding="utf-8") if "=" in line)
primary=[line.split() for line in open(sys.argv[2],encoding="utf-8") if line.strip()]
retries=[line.split() for line in open(sys.argv[3],encoding="utf-8") if line.strip()]
rows=[line.split() for line in open(sys.argv[4],encoding="utf-8") if line.strip()]
resolution=json.load(open(sys.argv[5],encoding="utf-8")); classification=json.load(open(sys.argv[6],encoding="utf-8"))
amendment=pathlib.Path(sys.argv[7]); resolver=pathlib.Path(sys.argv[8])
smoke=json.load(open(sys.argv[9],encoding="utf-8")); logs=json.load(open(sys.argv[10],encoding="utf-8"))
verify_command,grid_command=sys.argv[11:13]
preflight=pathlib.Path(sys.argv[13]); r4=pathlib.Path(sys.argv[14])
canary_amendment=pathlib.Path(sys.argv[15]); canary_validator=pathlib.Path(sys.argv[16])
canary_path=pathlib.Path(sys.argv[17]); grid_release_path=pathlib.Path(sys.argv[18])
expected_fixed={
 "run_id":"20260816-atlas-matched-diversity-mvp-v1-repair5",
 "image":"us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb",
 "code_sha":"60f296fdad769b30c0bb7334118698f156e462b9",
 "output_prefix":"gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5",
 "protocol_sha256":"badc0d64be69694caadd8fb2fe16a293c0cfbfe1f7813b4e80dc45e10b727abf",
 "pair_reach_amendment_sha256":"2e3734c595159d64748ab2eeec2de61194b665d43ef6854140e5378bac464a33",
 "packaging_repair_sha256":"e4293fae2dcd88b7a50179f0b4a688a23a8b1961bd7da8e437544e15a64e0e62",
 "sharding_repair_sha256":"a2139969e3bede2b304c0a8469bed7c7839b8ecb98da05221a005ddb2c9cbf68",
 "resource_repair3_protocol_sha256":"95c33b8aa64aeb8e0a7740471f85b5006d3a8e34ff250375f97994ad05d33b3d",
 "output_prefix_repair4_protocol_sha256":"5e84a6b93522fd959e798e90da307687179327b23c474fbda6b5303d0483063a",
 "resource_repair5_protocol_sha256":"5acc93c2b3a59931aa17dbc67d98fca81d3a6ac047011cfe1a9a81aa1ee8550e",
 "canary_amendment_sha256":"b2d0e32dabeb87bb1a67bee58c01f00c4c0d97e3fac9d1f7181bfcee50abc242",
 "canary_validator_sha256":"e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411",
 "cost_control_cancellation_sha256":"8f2b7770a8c54f6a1faa781d8398f8102ac20d930892768de69a9b705578b528",
 "repair4_manifest_sha256":"083a5e158053cd03f509bfebe518516af695773c029a78a8e80aa6aa336e5df6",
 "repair4_execution_ledger_sha256":"0ca2e0635a8cb572912aeb19156a388c9a87ba8bc0f340998a6b39eb2b28c3fd",
 "repair4_terminal_census_sha256":"fae0f421a7b79225436c6361a89baaa83699245d6cafca191aa7b00804d8d4b0",
 "repair4_terminal_completion_sha256":"31735ea72b5ed789974d4fff80826318222a6410fb0e1dc494081235e0dd6291",
 "repair3_failure_summary_sha256":"4da1f34de96f8ae9224d8c330abeae9ec3ade562c512e58f8e9ad60e6e8d4558",
 "repair3_failure_completion_sha256":"8dc630d58fae604b466792563402daff5a0801305eafde2c5e742c2d4686b149",
 "repair_validation_sha256":"4938df8c8f7f84dea40baf2f76cd84f78cdc9e1a097c271b419e3dc8c6b5cd37",
 "repair_execution_sha256":"f2bb244daf1b2d9515bee59799095fcbdd44414acb16b06e65e8298bd87c62b7",
 "repair_completion_sha256":"7bbff5dd3721ba436f79cb984091e7aa5815642629ab2c5615a6f2d9aacaa592",
 "resource_result_sha256":"241eeeb8278945ceadac78ea7ad1dcd40ea8ddb597590d4b9e3bae92d6153e05",
 "resource_summary_sha256":"c467332d78b09589680e9354ef9454d6c3f14a0193d4db15b559dde55af1472a",
 "resource_completion_sha256":"2412fa80e01e98633ded7224f544f2b5f19ff47c04971d8fc6e99d0413777ff1",
 "preflight_protocol_sha256":"b848dcc4ce0cdc6c3cac07f5ffb2ad6cbaa233a2457dc0286034ff3d50840788",
 "preflight_manifest_sha256":"ad79e5cd11cf848b14255ee914c277b7ce2a56e0a59540ba0b7ea42a967869e0",
 "preflight_execution_sha256":"a90e78b1ea1e4b261b370317eedd086a2324cc538fdbec069404c0c9a543f209",
 "preflight_failure_metadata_sha256":"b86e36a68600b5ced0dae7cc2c70141686fb96375c04c81d768c3a03a11fd3af",
 "preflight_launch_sha256":"72b26bcb75566329ba127b08d5564c07da08a87df81bfa242875ac921ed21148",
 "runner_source_sha256":"0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740",
 "renderer_sha256":"69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671",
 "uses_realized_outcomes":"false", "production_change_licensed":"false",
 "seasons":"2023,2024,2025", "weeks":"1-18", "slates":"54",
 "cpu":"8", "memory":"32Gi", "timeout_seconds":"43200",
 "max_retries":"0", "repair_treatment":"resource-envelope-only",
 "interaction_auxiliaries":"binary",
}
for key,value in expected_fixed.items():
 if manifest.get(key)!=value:
  raise SystemExit(f"ABORT: ATLAS repair5 manifest differs: {key}")
dynamic={
 "preflight_completion_sha256":preflight/"completion.txt",
 "preflight_execution_metadata_sha256":preflight/"execution-metadata.json",
 "preflight_shard_sha256":preflight/"shard.json",
}
for key,path in dynamic.items():
 if manifest.get(key)!=sha256(path.read_bytes()).hexdigest():
  raise SystemExit(f"ABORT: ATLAS repair5 preflight binding differs: {key}")
if sha256((r4/"terminal-census.json").read_bytes()).hexdigest()!=manifest["repair4_terminal_census_sha256"] or sha256((r4/"terminal-census-completion.txt").read_bytes()).hexdigest()!=manifest["repair4_terminal_completion_sha256"]:
 raise SystemExit("ABORT: ATLAS repair5 repair4 census binding differs")
if sha256(amendment.read_bytes()).hexdigest()!="d464660b72e669d261d7f6d4800b3e59d55726b56e7003c5e3e806f38fa987a0" or sha256(resolver.read_bytes()).hexdigest()!="705b65e5164b775361a2efe1440059f76978c3701c192179a40d85f4b0c27093" or sha256(canary_amendment.read_bytes()).hexdigest()!=manifest["canary_amendment_sha256"] or sha256(canary_validator.read_bytes()).hexdigest()!=manifest["canary_validator_sha256"]:
 raise SystemExit("ABORT: ATLAS repair5 attempt source differs")
canary=dict(line.rstrip("\n").split("=",1) for line in canary_path.read_text(encoding="utf-8").splitlines() if "=" in line)
grid_release=dict(line.rstrip("\n").split("=",1) for line in grid_release_path.read_text(encoding="utf-8").splitlines() if "=" in line)
canary_sha=sha256(canary_path.read_bytes()).hexdigest(); grid_release_sha=sha256(grid_release_path.read_bytes()).hexdigest()
if canary.get("status")!="True" or canary.get("disposition")!="real-path-canary-passes" or canary.get("cell")!="2023-1" or canary.get("remaining_cells_released")!="false" or canary.get("object_content_inspected")!="false" or grid_release.get("primary_executions")!="54" or grid_release.get("released_after_canary")!="53" or grid_release.get("canary_completion_sha256")!=canary_sha:
 raise SystemExit("ABORT: ATLAS repair5 canary/grid release differs")
for key,command in (("verify_command_sha256",verify_command),("grid_command_sha256",grid_command)):
 if manifest.get(key)!=sha256(command.encode()).hexdigest():
  raise SystemExit(f"ABORT: ATLAS repair5 rendered command differs: {key}")
expected_cells={(str(s),str(w)) for s in (2023,2024,2025) for w in range(1,19)}
if len(primary)!=54 or {(r[0],r[1]) for r in primary}!=expected_cells or any(len(r)!=5 for r in primary) or len({r[3] for r in primary})!=54:
 raise SystemExit("ABORT: ATLAS repair5 primary ledger differs")
if len(rows)!=54 or {(r[0],r[1]) for r in rows}!=expected_cells or any(len(r)!=5 for r in rows) or len({r[3] for r in rows})!=54:
 raise SystemExit("ABORT: ATLAS repair5 accepted ledger differs")
if any(len(r)!=6 for r in retries) or len({(r[0],r[1]) for r in retries})!=len(retries) or len({r[4] for r in retries})!=len(retries):
 raise SystemExit("ABORT: ATLAS repair5 retry ledger differs")
primary_by_cell={(r[0],r[1]):r for r in primary}; retry_by_cell={(r[0],r[1]):r for r in retries}
for cell,row in primary_by_cell.items():
 accepted=[r for r in rows if (r[0],r[1])==cell]
 if len(accepted)!=1:
  raise SystemExit("ABORT: ATLAS repair5 accepted cell differs")
 retry=retry_by_cell.get(cell)
 expected_execution=row[3] if retry is None else retry[4]
 if retry is not None and (retry[:4]!=row[:4] or retry[5]!=row[4]):
  raise SystemExit("ABORT: ATLAS repair5 retry-primary binding differs")
 if accepted[0][:3]!=row[:3] or accepted[0][3]!=expected_execution or accepted[0][4]!=row[4]:
  raise SystemExit("ABORT: ATLAS repair5 accepted attempt differs")
if resolution.get("version")!="atlas-repair5-attempt-resolution-v1" or resolution.get("disposition") not in {"accepted-primary-population","accepted-population-with-platform-replacements"} or resolution.get("uses_realized_outcomes") is not False or resolution.get("effect_fields_inspected") is not False or resolution.get("task_max_retries")!=0 or resolution.get("max_replacement_executions_per_cell")!=1 or resolution.get("primary_executions")!=54 or resolution.get("retry_executions")!=len(retries) or resolution.get("accepted_executions")!=54:
 raise SystemExit("ABORT: ATLAS repair5 attempt resolution differs")
if classification.get("version")!="atlas-repair5-primary-attempt-classification-v1" or classification.get("uses_realized_outcomes") is not False or classification.get("effect_fields_inspected") is not False or classification.get("ineligible_failures")!=0 or classification.get("eligible_replacements")!=len(retries) or classification.get("canary_completion_sha256")!=canary_sha or classification.get("grid_release_sha256")!=grid_release_sha or resolution.get("canary_completion_sha256")!=canary_sha or resolution.get("grid_release_sha256")!=grid_release_sha:
 raise SystemExit("ABORT: ATLAS repair5 primary classification differs")
for key,path in (("primary_execution_ledger_sha256",sys.argv[2]),("retry_execution_ledger_sha256",sys.argv[3]),("accepted_execution_ledger_sha256",sys.argv[4]),("classification_sha256",sys.argv[6])):
 if resolution.get(key)!=sha256(pathlib.Path(path).read_bytes()).hexdigest():
  raise SystemExit(f"ABORT: ATLAS repair5 attempt hash differs: {key}")
for season,week,job,execution,uri in rows:
 if job!=f"atlas-md-s{season}-w{week}-r5" or not execution.startswith(job+"-") or uri!=f"{manifest['output_prefix']}/slate-{season}-{week}.json":
  raise SystemExit("ABORT: ATLAS repair5 execution identity differs")
s=smoke.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0:
 raise SystemExit("ABORT: ATLAS repair5 smoke status differs")
marker="ATLAS_REPAIR4_PREFIX_PATCH_VERIFIED"
matches=[row.get("textPayload","") for row in logs if marker in row.get("textPayload","")]
if len(matches)!=1 or manifest["runner_source_sha256"] not in matches[0] or manifest["output_prefix"] not in matches[0]:
 raise SystemExit("ABORT: ATLAS repair5 smoke marker differs")
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
 raise SystemExit("ABORT: ATLAS repair5 execution name differs")
s=x.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0 or not s.get("completionTime"):
 raise SystemExit("ABORT: ATLAS repair5 execution is not terminal successful")
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ABORT: ATLAS repair5 task shape differs")
container=containers[0]
expected_args=["-c",command,"--season",season,"--week",week,"--output-uri",uri]
if container.get("image")!=m["image"] or container.get("command")!=["python"] or container.get("args")!=expected_args:
 raise SystemExit("ABORT: ATLAS repair5 image/command differs")
env={r.get("name"):str(r.get("value","")) for r in container.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]}:
 raise SystemExit("ABORT: ATLAS repair5 environment differs")
if container.get("resources",{}).get("limits")!={"cpu":"8","memory":"32Gi"} or task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="43200" or task.get("serviceAccountName")!="817589974517-compute@developer.gserviceaccount.com":
 raise SystemExit("ABORT: ATLAS repair5 resources/account differ")
PY
  SHARD="$OUT/shards.pending/slate-${SEASON}-${WEEK}.json"
  gcloud storage cp "$URI" "$SHARD" --project "$PROJECT" >/dev/null
  "$ROOT/.venv/bin/python" - "$SHARD" "$MANIFEST" "$SEASON" "$WEEK" <<'PY'
import json, sys
r=json.load(open(sys.argv[1],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line); season=int(sys.argv[3]); week=int(sys.argv[4])
if r.get("version")!="atlas-matched-diversity-mvp-v1" or r.get("uses_realized_outcomes") is not False or r.get("season")!=season or r.get("shard_week")!=week or r.get("code_sha")!=m["code_sha"] or r.get("analysis_image")!=m["image"] or len(r.get("slates",[]))!=1:
 raise SystemExit("ABORT: ATLAS repair5 shard identity differs")
row=r["slates"][0]
if row.get("season")!=season or row.get("week")!=week or row.get("mechanical_valid") is not True or row.get("uses_realized_outcomes") is not False or row.get("global_atlas_additions")!=200 or set(row.get("native_boom_counts",{}).values())!={40}:
 raise SystemExit("ABORT: ATLAS repair5 shard mechanics differ")
hashes=r.get("source_hashes",{})
expected={"2026-08-16-atlas-matched-diversity-mvp-protocol.md":m["protocol_sha256"],"2026-08-16-atlas-mvp-pair-reach-amendment.md":m["pair_reach_amendment_sha256"],"2026-08-16-atlas-mvp-image-packaging-repair.md":m["packaging_repair_sha256"],"2026-08-16-atlas-mvp-slate-sharding-repair.md":m["sharding_repair_sha256"],"validation.json":m["repair_validation_sha256"],"execution.json":m["repair_execution_sha256"],"completion.txt":m["repair_completion_sha256"]}
for source_name,value in expected.items():
 if [digest for path,digest in hashes.items() if path.endswith("/"+source_name) or path=="reports/"+source_name] != [value]:
  raise SystemExit("ABORT: ATLAS repair5 frozen-source binding differs")
PY
done < "$ACCEPTED_EXECUTIONS"

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
 raise SystemExit("ABORT: ATLAS repair5 aggregate identity/license differs")
mechanical=r.get("mechanical",{}); gate=r.get("gate",{}); conditions=gate.get("conditions",{})
expected={"conditional_pair_weight_strictly_higher","candidate_pair_reach_retains_100pct","conditional_stack_core_retains_90pct","candidate_pool_p210_strictly_higher_aggregate","candidate_pool_p210_higher_at_least_three_blocks","candidate_pool_p230_retains_95pct","exact80_p194_retains_90pct","exact80_p230_retains_90pct"}
if mechanical!={"seasons":[2023,2024,2025],"slates":54,"all_valid":True,"all_global_atlas_additions_200":True,"all_native_boom_counts_40":True} or set(conditions)!=expected or gate.get("passes_scorefree_gate") is not all(conditions.values()) or len(r.get("slates",[]))!=54:
 raise SystemExit("ABORT: ATLAS repair5 aggregate mechanics/gate differs")
if any(row.get("uses_realized_outcomes") is not False for row in r["slates"]):
 raise SystemExit("ABORT: ATLAS repair5 aggregate contains outcomes")
print("ATLAS_REPAIR5_AGGREGATE_VALIDATED",gate["passes_scorefree_gate"])
PY

sha256sum "$OUT"/season-*.json > "$OUT/season-reports.sha256"
sha256sum "$OUT/report.json" > "$OUT/report.sha256"
sha256sum "$OUT"/execution-metadata/*.json | sort > "$OUT/execution-metadata.sha256"
sha256sum "$OUT"/shards/*.json | sort > "$OUT/shards.sha256"
sha256sum "$OUT/executions.txt" "$OUT/retry-executions.txt" \
  "$OUT/accepted-executions.txt" "$OUT/attempt-resolution.json" \
  "$OUT/primary-attempt-classification.json" \
  "$OUT/primary-execution-metadata.sha256" "$OUT/canary-completion.txt" \
  "$OUT/canary-execution-metadata.json" \
  "$OUT/canary-object-metadata.json" "$OUT/grid-release.txt" \
  > "$OUT/attempt-artifacts.sha256"
RETRY_COUNT=$(wc -l < "$RETRY_EXECUTIONS")
printf '%s\n' "validated_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'primary_executions=54' "retry_executions=$RETRY_COUNT" \
  'accepted_executions=54' 'seasons=2023,2024,2025' 'slates=54' \
  'cpu=8' 'memory=32Gi' 'task_max_retries=0' \
  'max_replacement_executions_per_cell=1' \
  'real_path_canary=passed' 'released_after_canary=53' \
  'repair_treatment=resource-envelope-only' \
  'interaction_auxiliaries=binary' 'uses_realized_outcomes=false' \
  'production_change_licensed=false' > "$OUT/completion.txt"
sha256sum "$OUT/completion.txt" > "$OUT/completion.sha256"
echo "ATLAS_MATCHED_DIVERSITY_REPAIR5_HARVESTED $RUN_ID"
