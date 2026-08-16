#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair4
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb
CODE_SHA=60f296fdad769b30c0bb7334118698f156e462b9
RUNNER_SOURCE="$ROOT/scripts/run_atlas_matched_diversity_mvp.py"
RUNNER_SOURCE_SHA=0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740
RENDERER="$ROOT/scripts/render_atlas_matched_diversity_repair4_command.py"
RENDERER_SHA=69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671
PROTOCOL="$ROOT/reports/2026-08-16-atlas-matched-diversity-mvp-protocol.md"
PROTOCOL_SHA=badc0d64be69694caadd8fb2fe16a293c0cfbfe1f7813b4e80dc45e10b727abf
PAIR_REACH="$ROOT/reports/2026-08-16-atlas-mvp-pair-reach-amendment.md"
PAIR_REACH_SHA=2e3734c595159d64748ab2eeec2de61194b665d43ef6854140e5378bac464a33
PACKAGING="$ROOT/reports/2026-08-16-atlas-mvp-image-packaging-repair.md"
PACKAGING_SHA=e4293fae2dcd88b7a50179f0b4a688a23a8b1961bd7da8e437544e15a64e0e62
SHARDING="$ROOT/reports/2026-08-16-atlas-mvp-slate-sharding-repair.md"
SHARDING_SHA=a2139969e3bede2b304c0a8469bed7c7839b8ecb98da05221a005ddb2c9cbf68
RESOURCE3="$ROOT/reports/2026-08-16-atlas-mvp-resource-only-repair3.md"
RESOURCE3_SHA=95c33b8aa64aeb8e0a7740471f85b5006d3a8e34ff250375f97994ad05d33b3d
REPAIR4="$ROOT/reports/2026-08-16-atlas-mvp-output-prefix-repair4.md"
REPAIR4_SHA=5e84a6b93522fd959e798e90da307687179327b23c474fbda6b5303d0483063a
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
PREFLIGHT_RUN="$ROOT/reports/atlas-cbc-16g-preflight-runs/20260816-atlas-cbc-16g-preflight-v1"
PREFLIGHT_PROTOCOL="$ROOT/reports/2026-08-16-atlas-cbc-16g-preflight-protocol.md"
PREFLIGHT_PROTOCOL_SHA=4c09ba4065e5ac32af3873f149ca42c0dd922cadc21524fd277f404d7fdc45a7
PREFLIGHT_MANIFEST_SHA=059cf942a06de76815151e34db1ba363535c17c2069e1ce7bd19486804a8334f
PREFLIGHT_EXECUTION_SHA=00a50351f571a606e8efb47ae8eea0134c911998e64fe85e9836cf0677dd5ae3
PREFLIGHT_SUMMARY_SHA=54e659421cd4ebe59f0d0219e1dd9a9db6774e6161c681f24f39b667e964228f
PREFLIGHT_COMPLETION_SHA=07157e8e1589eaeb903ae5d7d124b677904061c11cdcc8567fab6649a1d317a9

for SPEC in \
  "$RUNNER_SOURCE:$RUNNER_SOURCE_SHA" "$RENDERER:$RENDERER_SHA" \
  "$PROTOCOL:$PROTOCOL_SHA" "$PAIR_REACH:$PAIR_REACH_SHA" \
  "$PACKAGING:$PACKAGING_SHA" "$SHARDING:$SHARDING_SHA" \
  "$RESOURCE3:$RESOURCE3_SHA" "$REPAIR4:$REPAIR4_SHA" \
  "$REPAIR3_RUN/failure-summary.json:$REPAIR3_SUMMARY_SHA" \
  "$REPAIR3_RUN/failure-completion.txt:$REPAIR3_COMPLETION_SHA" \
  "$REPAIR/validation.json:$REPAIR_VALIDATION_SHA" \
  "$REPAIR/execution.json:$REPAIR_EXECUTION_SHA" \
  "$REPAIR/completion.txt:$REPAIR_COMPLETION_SHA" \
  "$RESOURCE_RESULT:$RESOURCE_RESULT_SHA" \
  "$RESOURCE_RUN/summary.json:$RESOURCE_SUMMARY_SHA" \
  "$RESOURCE_RUN/completion.txt:$RESOURCE_COMPLETION_SHA" \
  "$PREFLIGHT_PROTOCOL:$PREFLIGHT_PROTOCOL_SHA" \
  "$PREFLIGHT_RUN/manifest.txt:$PREFLIGHT_MANIFEST_SHA" \
  "$PREFLIGHT_RUN/execution.txt:$PREFLIGHT_EXECUTION_SHA" \
  "$PREFLIGHT_RUN/summary.json:$PREFLIGHT_SUMMARY_SHA" \
  "$PREFLIGHT_RUN/completion.txt:$PREFLIGHT_COMPLETION_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: frozen ATLAS repair4 source differs: $FILE" >&2; exit 2; }
done

"$ROOT/.venv/bin/python" - "$REPAIR3_RUN/failure-summary.json" \
  "$PREFLIGHT_RUN/summary.json" <<'PY'
import json, sys
failure=json.load(open(sys.argv[1],encoding="utf-8"))
preflight=json.load(open(sys.argv[2],encoding="utf-8"))
if failure != {**failure,
    "version":"atlas-matched-diversity-repair3-prefix-failure-v1",
    "run_id":"20260816-atlas-matched-diversity-mvp-v1-repair3",
    "uses_realized_outcomes":False,
    "production_change_licensed":False,
    "executions":54,
    "terminal_failed":54,
    "terminal_succeeded":0,
    "output_objects":0,
    "common_reason":"NonZeroExitCode",
    "common_error":"RuntimeError: ATLAS MVP shard season/week/output identity differs",
    "failure_stage":"pre-query-output-identity-check",
    "scientific_calculation_started":False,
}:
 raise SystemExit("ERROR: ATLAS repair3 failure did not license prefix repair")
expected={
 "version":"atlas-cbc-16g-preflight-summary-v1",
 "uses_realized_outcomes":False,
 "persists_lineups":False,
 "production_change_licensed":False,
 "disposition":"r0-complete",
 "status":"r0-complete",
 "returncode":0,
 "terminating_signal":None,
 "oom_kill_delta_total":0,
}
if any(preflight.get(key)!=value for key,value in expected.items()):
 raise SystemExit("ERROR: ATLAS 16 GiB preflight did not license repair4")
PY

[ ! -e "$OUT" ] || {
  echo "ERROR: immutable ATLAS repair4 run directory exists" >&2; exit 3; }
if gcloud storage ls "$PREFIX/**" --recursive --project "$PROJECT" \
    2>/dev/null | head -1 | grep -q .; then
  echo "ERROR: immutable ATLAS repair4 cloud prefix exists" >&2; exit 3
fi

VERIFY_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX" --verify-only)
GRID_COMMAND=$("$ROOT/.venv/bin/python" "$RENDERER" \
  --replacement-prefix "$PREFIX")
VERIFY_COMMAND_SHA=$(printf '%s' "$VERIFY_COMMAND" | sha256sum | awk '{print $1}')
GRID_COMMAND_SHA=$(printf '%s' "$GRID_COMMAND" | sha256sum | awk '{print $1}')

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "output_prefix=$PREFIX" "protocol_sha256=$PROTOCOL_SHA" \
  "pair_reach_amendment_sha256=$PAIR_REACH_SHA" \
  "packaging_repair_sha256=$PACKAGING_SHA" \
  "sharding_repair_sha256=$SHARDING_SHA" \
  "resource_repair3_protocol_sha256=$RESOURCE3_SHA" \
  "output_prefix_repair4_protocol_sha256=$REPAIR4_SHA" \
  "repair3_failure_summary_sha256=$REPAIR3_SUMMARY_SHA" \
  "repair3_failure_completion_sha256=$REPAIR3_COMPLETION_SHA" \
  "repair_validation_sha256=$REPAIR_VALIDATION_SHA" \
  "repair_execution_sha256=$REPAIR_EXECUTION_SHA" \
  "repair_completion_sha256=$REPAIR_COMPLETION_SHA" \
  "resource_result_sha256=$RESOURCE_RESULT_SHA" \
  "resource_summary_sha256=$RESOURCE_SUMMARY_SHA" \
  "resource_completion_sha256=$RESOURCE_COMPLETION_SHA" \
  "preflight_protocol_sha256=$PREFLIGHT_PROTOCOL_SHA" \
  "preflight_manifest_sha256=$PREFLIGHT_MANIFEST_SHA" \
  "preflight_execution_sha256=$PREFLIGHT_EXECUTION_SHA" \
  "preflight_summary_sha256=$PREFLIGHT_SUMMARY_SHA" \
  "preflight_completion_sha256=$PREFLIGHT_COMPLETION_SHA" \
  "runner_source_sha256=$RUNNER_SOURCE_SHA" "renderer_sha256=$RENDERER_SHA" \
  "verify_command_sha256=$VERIFY_COMMAND_SHA" \
  "grid_command_sha256=$GRID_COMMAND_SHA" \
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  'seasons=2023,2024,2025' 'weeks=1-18' 'slates=54' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=43200' 'max_retries=0' \
  'repair_treatment=output-prefix-transport-only' \
  'interaction_auxiliaries=binary' > "$OUT/manifest.txt"

SMOKE_JOB=atlas-md-prefix-r4-smoke
gcloud run jobs deploy "$SMOKE_JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMAGE" --command python --args=-c,"$VERIFY_COMMAND" \
  --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
  --service-account "$SERVICE_ACCOUNT" --cpu 1 --memory 4Gi \
  --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 5m --quiet
SMOKE_EXEC=$(gcloud run jobs execute "$SMOKE_JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$SMOKE_EXEC" ] || {
  echo "ERROR: ATLAS repair4 smoke execution identity missing" >&2; exit 2; }
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
  "$OUT/smoke-log.json" "$OUT/manifest.txt" "$SMOKE_EXEC" \
  "$VERIFY_COMMAND" <<'PY'
import json, sys
x=json.load(open(sys.argv[1],encoding="utf-8"))
logs=json.load(open(sys.argv[2],encoding="utf-8"))
m=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[3],encoding="utf-8") if "=" in line)
name,command=sys.argv[4:]
s=x.get("status",{}); c=[row for row in s.get("conditions",[]) if row.get("type")=="Completed"]
if x.get("metadata",{}).get("name")!=name or len(c)!=1 or c[0].get("status")!="True" or int(s.get("succeededCount") or 0)!=1 or int(s.get("failedCount") or 0)!=0:
 raise SystemExit("ERROR: ATLAS repair4 prefix smoke failed")
spec=x.get("spec",{}); task=spec.get("template",{}).get("spec",{}); containers=task.get("containers",[])
if spec.get("parallelism")!=1 or spec.get("taskCount")!=1 or len(containers)!=1:
 raise SystemExit("ERROR: ATLAS repair4 smoke task shape differs")
container=containers[0]
if container.get("image")!=m["image"] or container.get("command")!=["python"] or container.get("args")!=["-c",command]:
 raise SystemExit("ERROR: ATLAS repair4 smoke command differs")
env={row.get("name"):str(row.get("value","")) for row in container.get("env",[])}
if env!={"CODE_SHA":m["code_sha"],"ANALYSIS_IMAGE":m["image"]}:
 raise SystemExit("ERROR: ATLAS repair4 smoke environment differs")
if container.get("resources",{}).get("limits")!={"cpu":"1","memory":"4Gi"} or task.get("maxRetries")!=0 or str(task.get("timeoutSeconds"))!="300":
 raise SystemExit("ERROR: ATLAS repair4 smoke resources differ")
marker="ATLAS_REPAIR4_PREFIX_PATCH_VERIFIED"
matches=[row.get("textPayload","") for row in logs if marker in row.get("textPayload","")]
if len(matches)!=1 or m["runner_source_sha256"] not in matches[0] or m["output_prefix"] not in matches[0]:
 raise SystemExit("ERROR: ATLAS repair4 smoke marker differs")
PY
sha256sum "$OUT/smoke-execution.txt" "$OUT/smoke-execution.json" \
  "$OUT/smoke-log.json" > "$OUT/smoke.sha256"

: > "$OUT/executions.txt"
for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    JOB="atlas-md-s${SEASON}-w${WEEK}-r4"
    URI="$PREFIX/slate-${SEASON}-${WEEK}.json"
    gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --command python \
      --args=-c,"$GRID_COMMAND",--season,"$SEASON",--week,"$WEEK",--output-uri,"$URI" \
      --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
      --service-account "$SERVICE_ACCOUNT" --cpu 4 --memory 16Gi \
      --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 12h --quiet
    EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --format='value(metadata.name)')
    [ -n "$EXEC" ] || {
      echo "ERROR: ATLAS repair4 execution identity missing" >&2; exit 2; }
    printf '%s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" "$EXEC" "$URI" \
      | tee -a "$OUT/executions.txt"
  done
done
sha256sum "$OUT/manifest.txt" "$OUT/executions.txt" > "$OUT/launch.sha256"
echo "ATLAS_MATCHED_DIVERSITY_REPAIR4_LAUNCHED $RUN_ID"
