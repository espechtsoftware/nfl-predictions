#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair5
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb
CODE_SHA=60f296fdad769b30c0bb7334118698f156e462b9
RUNNER="$ROOT/scripts/run_atlas_matched_diversity_mvp.py"
RUNNER_SHA=0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"
RENDERER_SHA=69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671
MVP_PROTOCOL="$ROOT/reports/2026-08-16-atlas-matched-diversity-mvp-protocol.md"
MVP_PROTOCOL_SHA=badc0d64be69694caadd8fb2fe16a293c0cfbfe1f7813b4e80dc45e10b727abf
PAIR_REACH="$ROOT/reports/2026-08-16-atlas-mvp-pair-reach-amendment.md"
PAIR_REACH_SHA=2e3734c595159d64748ab2eeec2de61194b665d43ef6854140e5378bac464a33
PACKAGING="$ROOT/reports/2026-08-16-atlas-mvp-image-packaging-repair.md"
PACKAGING_SHA=e4293fae2dcd88b7a50179f0b4a688a23a8b1961bd7da8e437544e15a64e0e62
SHARDING="$ROOT/reports/2026-08-16-atlas-mvp-slate-sharding-repair.md"
SHARDING_SHA=a2139969e3bede2b304c0a8469bed7c7839b8ecb98da05221a005ddb2c9cbf68
RESOURCE3="$ROOT/reports/2026-08-16-atlas-mvp-resource-only-repair3.md"
RESOURCE3_SHA=95c33b8aa64aeb8e0a7740471f85b5006d3a8e34ff250375f97994ad05d33b3d
PREFIX4="$ROOT/reports/2026-08-16-atlas-mvp-output-prefix-repair4.md"
PREFIX4_SHA=5e84a6b93522fd959e798e90da307687179327b23c474fbda6b5303d0483063a
PROTOCOL="$ROOT/reports/2026-08-16-atlas-mvp-resource-only-repair5.md"
PROTOCOL_SHA=5acc93c2b3a59931aa17dbc67d98fca81d3a6ac047011cfe1a9a81aa1ee8550e
CANARY_AMENDMENT="$ROOT/reports/2026-08-16-atlas-repair5-real-path-canary-amendment.md"
CANARY_AMENDMENT_SHA=b2d0e32dabeb87bb1a67bee58c01f00c4c0d97e3fac9d1f7181bfcee50abc242
CANARY_VALIDATOR="$ROOT/scripts/cloud_wait_atlas_repair5_canary.sh"
CANARY_VALIDATOR_SHA=e1c82612f231976563f0df12ffbe9f5e2db1aebfae636f61b723ad8699ae1411
REPAIR3_RUN="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair3"
REPAIR3_SUMMARY_SHA=4da1f34de96f8ae9224d8c330abeae9ec3ade562c512e58f8e9ad60e6e8d4558
REPAIR3_COMPLETION_SHA=8dc630d58fae604b466792563402daff5a0801305eafde2c5e742c2d4686b149
REPAIR="$ROOT/reports/atlas-mvp-source-repair-runs/20260816-atlas-mvp-source-repair-r3-2025-v1"
REPAIR_VALIDATION_SHA=4938df8c8f7f84dea40baf2f76cd84f78cdc9e1a097c271b419e3dc8c6b5cd37
REPAIR_EXECUTION_SHA=f2bb244daf1b2d9515bee59799095fcbdd44414acb16b06e65e8298bd87c62b7
REPAIR_COMPLETION_SHA=7bbff5dd3721ba436f79cb984091e7aa5815642629ab2c5615a6f2d9aacaa592
RESOURCE_RESULT="$ROOT/reports/2026-08-16-atlas-cbc-resource-diagnostic-result.md"
RESOURCE_RESULT_SHA=241eeeb8278945ceadac78ea7ad1dcd40ea8ddb597590d4b9e3bae92d6153e05
RESOURCE_RUN="$ROOT/reports/atlas-cbc-resource-diagnostic-runs/20260816-atlas-cbc-resource-diagnostic-v1"
RESOURCE_SUMMARY_SHA=c467332d78b09589680e9354ef9454d6c3f14a0193d4db15b559dde55af1472a
RESOURCE_COMPLETION_SHA=2412fa80e01e98633ded7224f544f2b5f19ff47c04971d8fc6e99d0413777ff1
CANCEL="$ROOT/reports/2026-08-16-atlas-repair4-cost-control-cancellation.md"
CANCEL_SHA=8f2b7770a8c54f6a1faa781d8398f8102ac20d930892768de69a9b705578b528
R4="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair4"
R4_MANIFEST_SHA=083a5e158053cd03f509bfebe518516af695773c029a78a8e80aa6aa336e5df6
R4_EXECUTIONS_SHA=0ca2e0635a8cb572912aeb19156a388c9a87ba8bc0f340998a6b39eb2b28c3fd
R4_CENSUS_SHA=fae0f421a7b79225436c6361a89baaa83699245d6cafca191aa7b00804d8d4b0
R4_COMPLETION_SHA=31735ea72b5ed789974d4fff80826318222a6410fb0e1dc494081235e0dd6291
PREFLIGHT="$ROOT/reports/atlas-cbc-32g-full-cell-preflight-runs/20260816-atlas-cbc-32g-full-cell-preflight-v1"
PREFLIGHT_PROTOCOL="$ROOT/reports/2026-08-16-atlas-cbc-32g-full-cell-preflight-protocol.md"
PREFLIGHT_PROTOCOL_SHA=b848dcc4ce0cdc6c3cac07f5ffb2ad6cbaa233a2457dc0286034ff3d50840788
PREFLIGHT_MANIFEST_SHA=ad79e5cd11cf848b14255ee914c277b7ce2a56e0a59540ba0b7ea42a967869e0
PREFLIGHT_EXECUTION_SHA=a90e78b1ea1e4b261b370317eedd086a2324cc538fdbec069404c0c9a543f209
PREFLIGHT_FAILURE_META_SHA=b86e36a68600b5ced0dae7cc2c70141686fb96375c04c81d768c3a03a11fd3af
PREFLIGHT_LAUNCH_SHA=72b26bcb75566329ba127b08d5564c07da08a87df81bfa242875ac921ed21148

for SPEC in \
  "$RUNNER:$RUNNER_SHA" "$RENDERER:$RENDERER_SHA" \
  "$MVP_PROTOCOL:$MVP_PROTOCOL_SHA" "$PAIR_REACH:$PAIR_REACH_SHA" \
  "$PACKAGING:$PACKAGING_SHA" "$SHARDING:$SHARDING_SHA" \
  "$RESOURCE3:$RESOURCE3_SHA" "$PREFIX4:$PREFIX4_SHA" \
  "$PROTOCOL:$PROTOCOL_SHA" \
  "$CANARY_AMENDMENT:$CANARY_AMENDMENT_SHA" \
  "$CANARY_VALIDATOR:$CANARY_VALIDATOR_SHA" \
  "$CANCEL:$CANCEL_SHA" \
  "$REPAIR3_RUN/failure-summary.json:$REPAIR3_SUMMARY_SHA" \
  "$REPAIR3_RUN/failure-completion.txt:$REPAIR3_COMPLETION_SHA" \
  "$REPAIR/validation.json:$REPAIR_VALIDATION_SHA" \
  "$REPAIR/execution.json:$REPAIR_EXECUTION_SHA" \
  "$REPAIR/completion.txt:$REPAIR_COMPLETION_SHA" \
  "$RESOURCE_RESULT:$RESOURCE_RESULT_SHA" \
  "$RESOURCE_RUN/summary.json:$RESOURCE_SUMMARY_SHA" \
  "$RESOURCE_RUN/completion.txt:$RESOURCE_COMPLETION_SHA" \
  "$R4/manifest.txt:$R4_MANIFEST_SHA" \
  "$R4/executions.txt:$R4_EXECUTIONS_SHA" \
  "$R4/terminal-census.json:$R4_CENSUS_SHA" \
  "$R4/terminal-census-completion.txt:$R4_COMPLETION_SHA" \
  "$PREFLIGHT_PROTOCOL:$PREFLIGHT_PROTOCOL_SHA" \
  "$PREFLIGHT/manifest.txt:$PREFLIGHT_MANIFEST_SHA" \
  "$PREFLIGHT/execution.txt:$PREFLIGHT_EXECUTION_SHA" \
  "$PREFLIGHT/repair4-failure-execution.json:$PREFLIGHT_FAILURE_META_SHA" \
  "$PREFLIGHT/launch.sha256:$PREFLIGHT_LAUNCH_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: frozen ATLAS repair5 dependency differs: $FILE" >&2; exit 2; }
done
for FILE in completion.txt execution-metadata.json shard.json; do
  [ -s "$PREFLIGHT/$FILE" ] || {
    echo "ERROR: ATLAS repair5 awaits strict 32-GiB preflight: $FILE" >&2; exit 2; }
done

"$ROOT/.venv/bin/python" - "$R4/terminal-census.json" \
  "$PREFLIGHT/completion.txt" "$PREFLIGHT/execution-metadata.json" \
  "$PREFLIGHT/shard.json" <<'PY'
import json, sys
census=json.load(open(sys.argv[1],encoding="utf-8"))
completion=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
meta=json.load(open(sys.argv[3],encoding="utf-8"))
shard=json.load(open(sys.argv[4],encoding="utf-8"))
if census.get("version")!="atlas-matched-diversity-repair4-terminal-census-v1" or census.get("executions")!=54 or census.get("terminal_failed",0)<1 or census.get("effect_fields_inspected") is not False or census.get("historical_scoring_licensed") is not False:
 raise SystemExit("ERROR: ATLAS repair4 census does not license repair5")
week8=[r for r in census.get("terminal",[]) if r.get("season")==2023 and r.get("week")==8]
if len(week8)!=1 or "configured memory limit was reached" not in week8[0].get("message",""):
 raise SystemExit("ERROR: ATLAS repair4 memory failure differs")
if completion.get("status")!="True" or completion.get("disposition")!="full-cell-r0-complete-at-32g" or completion.get("cell")!="2023-8" or completion.get("cpu")!="8" or completion.get("memory")!="32Gi":
 raise SystemExit("ERROR: ATLAS 32-GiB preflight did not license repair5")
s=meta.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if meta.get("metadata",{}).get("name")!="atlas-cbc-32g-full-2023-w8-v1-lbzjd" or len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1:
 raise SystemExit("ERROR: ATLAS 32-GiB preflight metadata differs")
if shard.get("version")!="atlas-matched-diversity-mvp-v1" or shard.get("uses_realized_outcomes") is not False or shard.get("season")!=2023 or shard.get("shard_week")!=8 or len(shard.get("slates",[]))!=1:
 raise SystemExit("ERROR: ATLAS 32-GiB preflight shard identity differs")
row=shard["slates"][0]
if row.get("season")!=2023 or row.get("week")!=8 or row.get("mechanical_valid") is not True or row.get("uses_realized_outcomes") is not False or row.get("global_atlas_additions")!=200 or set(row.get("native_boom_counts",{}).values())!={40}:
 raise SystemExit("ERROR: ATLAS 32-GiB preflight shard mechanics differ")
PY

[ ! -e "$OUT" ] || {
  echo "ERROR: immutable ATLAS repair5 local run exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
    2>/dev/null | head -1 | grep -q .; then
  echo "ERROR: immutable ATLAS repair5 cloud prefix exists" >&2; exit 3
fi

VERIFY_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX" --verify-only)
GRID_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX")
mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "output_prefix=$PREFIX" "protocol_sha256=$MVP_PROTOCOL_SHA" \
  "pair_reach_amendment_sha256=$PAIR_REACH_SHA" \
  "packaging_repair_sha256=$PACKAGING_SHA" \
  "sharding_repair_sha256=$SHARDING_SHA" \
  "resource_repair3_protocol_sha256=$RESOURCE3_SHA" \
  "output_prefix_repair4_protocol_sha256=$PREFIX4_SHA" \
  "resource_repair5_protocol_sha256=$PROTOCOL_SHA" \
  "canary_amendment_sha256=$CANARY_AMENDMENT_SHA" \
  "canary_validator_sha256=$CANARY_VALIDATOR_SHA" \
  "repair3_failure_summary_sha256=$REPAIR3_SUMMARY_SHA" \
  "repair3_failure_completion_sha256=$REPAIR3_COMPLETION_SHA" \
  "repair_validation_sha256=$REPAIR_VALIDATION_SHA" \
  "repair_execution_sha256=$REPAIR_EXECUTION_SHA" \
  "repair_completion_sha256=$REPAIR_COMPLETION_SHA" \
  "resource_result_sha256=$RESOURCE_RESULT_SHA" \
  "resource_summary_sha256=$RESOURCE_SUMMARY_SHA" \
  "resource_completion_sha256=$RESOURCE_COMPLETION_SHA" \
  "cost_control_cancellation_sha256=$CANCEL_SHA" \
  "repair4_manifest_sha256=$R4_MANIFEST_SHA" \
  "repair4_execution_ledger_sha256=$R4_EXECUTIONS_SHA" \
  "repair4_terminal_census_sha256=$R4_CENSUS_SHA" \
  "repair4_terminal_completion_sha256=$R4_COMPLETION_SHA" \
  "preflight_protocol_sha256=$PREFLIGHT_PROTOCOL_SHA" \
  "preflight_manifest_sha256=$PREFLIGHT_MANIFEST_SHA" \
  "preflight_execution_sha256=$PREFLIGHT_EXECUTION_SHA" \
  "preflight_failure_metadata_sha256=$PREFLIGHT_FAILURE_META_SHA" \
  "preflight_launch_sha256=$PREFLIGHT_LAUNCH_SHA" \
  "preflight_completion_sha256=$(sha256sum "$PREFLIGHT/completion.txt" | awk '{print $1}')" \
  "preflight_execution_metadata_sha256=$(sha256sum "$PREFLIGHT/execution-metadata.json" | awk '{print $1}')" \
  "preflight_shard_sha256=$(sha256sum "$PREFLIGHT/shard.json" | awk '{print $1}')" \
  "runner_source_sha256=$RUNNER_SHA" "renderer_sha256=$RENDERER_SHA" \
  "verify_command_sha256=$(printf '%s' "$VERIFY_COMMAND" | sha256sum | awk '{print $1}')" \
  "grid_command_sha256=$(printf '%s' "$GRID_COMMAND" | sha256sum | awk '{print $1}')" \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  'seasons=2023,2024,2025' 'weeks=1-18' 'slates=54' \
  'cpu=8' 'memory=32Gi' 'timeout_seconds=43200' 'max_retries=0' \
  'repair_treatment=resource-envelope-only' \
  'interaction_auxiliaries=binary' > "$OUT/manifest.txt"

SMOKE_JOB=atlas-md-prefix-r5-smoke
gcloud run jobs deploy "$SMOKE_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python --args=-c,"$VERIFY_COMMAND" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 1 --memory 4Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 5m --quiet
SMOKE_EXEC=$(gcloud run jobs execute "$SMOKE_JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$SMOKE_EXEC" ] || {
  echo "ERROR: ATLAS repair5 smoke identity missing" >&2; exit 2; }
printf '%s %s\n' "$SMOKE_JOB" "$SMOKE_EXEC" > "$OUT/smoke-execution.txt"
while true; do
  STATE=$(gcloud run jobs executions describe "$SMOKE_EXEC" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)')
  [ "$STATE" = Unknown ] || break
  sleep 5
done
gcloud run jobs executions describe "$SMOKE_EXEC" --project "$PROJECT" \
  --region "$REGION" --format=json > "$OUT/smoke-execution.json"
gcloud logging read \
  "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$SMOKE_EXEC\"" \
  --project "$PROJECT" --limit=30 --order=asc --format=json > "$OUT/smoke-log.json"
"$ROOT/.venv/bin/python" - "$OUT/smoke-execution.json" \
  "$OUT/smoke-log.json" "$OUT/manifest.txt" "$SMOKE_EXEC" <<'PY'
import json, sys
x=json.load(open(sys.argv[1],encoding="utf-8")); logs=json.load(open(sys.argv[2],encoding="utf-8")); m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[3],encoding="utf-8") if "=" in line); name=sys.argv[4]
s=x.get("status",{}); done=[r for r in s.get("conditions",[]) if r.get("type")=="Completed"]
if x.get("metadata",{}).get("name")!=name or len(done)!=1 or done[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1:
 raise SystemExit("ERROR: ATLAS repair5 prefix smoke failed")
marker="ATLAS_REPAIR4_PREFIX_PATCH_VERIFIED"
matches=[r.get("textPayload","") for r in logs if marker in r.get("textPayload","")]
if len(matches)!=1 or m["runner_source_sha256"] not in matches[0] or m["output_prefix"] not in matches[0]:
 raise SystemExit("ERROR: ATLAS repair5 smoke marker differs")
PY
sha256sum "$OUT/smoke-execution.txt" "$OUT/smoke-execution.json" \
  "$OUT/smoke-log.json" > "$OUT/smoke.sha256"

: > "$OUT/executions.txt"
SEASON=2023
WEEK=1
JOB="atlas-md-s${SEASON}-w${WEEK}-r5"
URI="$PREFIX/slate-${SEASON}-${WEEK}.json"
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python \
  --args=-c,"$GRID_COMMAND",--season,"$SEASON",--week,"$WEEK",--output-uri,"$URI" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 12h --quiet
EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$EXEC" ] || {
  echo "ERROR: ATLAS repair5 canary execution identity missing" >&2; exit 2; }
printf '%s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" "$EXEC" "$URI" \
  | tee -a "$OUT/executions.txt"
bash "$CANARY_VALIDATOR"

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    [ "$SEASON" = 2023 ] && [ "$WEEK" = 1 ] && continue
    JOB="atlas-md-s${SEASON}-w${WEEK}-r5"
    URI="$PREFIX/slate-${SEASON}-${WEEK}.json"
    gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --command python \
      --args=-c,"$GRID_COMMAND",--season,"$SEASON",--week,"$WEEK",--output-uri,"$URI" \
      --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
      --service-account "$SERVICE_ACCOUNT" --cpu 8 --memory 32Gi \
      --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 12h --quiet
    EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --format='value(metadata.name)')
    [ -n "$EXEC" ] || {
      echo "ERROR: ATLAS repair5 execution identity missing" >&2; exit 2; }
    printf '%s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" "$EXEC" "$URI" \
      | tee -a "$OUT/executions.txt"
  done
done
[ "$(wc -l < "$OUT/executions.txt")" = 54 ] || {
  echo "ERROR: ATLAS repair5 primary grid is not 54" >&2; exit 2; }
printf '%s\n' \
  "released_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'primary_executions=54' 'released_after_canary=53' \
  "canary_completion_sha256=$(sha256sum "$OUT/canary-completion.txt" | awk '{print $1}')" \
  'object_content_inspected=false' 'effect_fields_inspected=false' \
  > "$OUT/grid-release.txt"
sha256sum "$OUT/manifest.txt" "$OUT/executions.txt" > "$OUT/launch.sha256"
echo "ATLAS_MATCHED_DIVERSITY_REPAIR5_LAUNCHED $RUN_ID"
