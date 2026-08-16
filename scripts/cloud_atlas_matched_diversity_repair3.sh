#!/usr/bin/env bash
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260816-atlas-matched-diversity-mvp-v1-repair3
OUT="$ROOT/reports/atlas-matched-diversity-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/$RUN_ID
IMAGE=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ce03feb739e51aabedd7cea79f46e13a06a097a7f85e9a5817f38184b67f4fcb
CODE_SHA=60f296fdad769b30c0bb7334118698f156e462b9

PROTOCOL="$ROOT/reports/2026-08-16-atlas-matched-diversity-mvp-protocol.md"
PROTOCOL_SHA=badc0d64be69694caadd8fb2fe16a293c0cfbfe1f7813b4e80dc45e10b727abf
PAIR_REACH="$ROOT/reports/2026-08-16-atlas-mvp-pair-reach-amendment.md"
PAIR_REACH_SHA=2e3734c595159d64748ab2eeec2de61194b665d43ef6854140e5378bac464a33
PACKAGING="$ROOT/reports/2026-08-16-atlas-mvp-image-packaging-repair.md"
PACKAGING_SHA=e4293fae2dcd88b7a50179f0b4a688a23a8b1961bd7da8e437544e15a64e0e62
SHARDING="$ROOT/reports/2026-08-16-atlas-mvp-slate-sharding-repair.md"
SHARDING_SHA=a2139969e3bede2b304c0a8469bed7c7839b8ecb98da05221a005ddb2c9cbf68
REPAIR3="$ROOT/reports/2026-08-16-atlas-mvp-resource-only-repair3.md"
REPAIR3_SHA=95c33b8aa64aeb8e0a7740471f85b5006d3a8e34ff250375f97994ad05d33b3d
REPAIR="$ROOT/reports/atlas-mvp-source-repair-runs/20260816-atlas-mvp-source-repair-r3-2025-v1"
REPAIR_VALIDATION_SHA=4938df8c8f7f84dea40baf2f76cd84f78cdc9e1a097c271b419e3dc8c6b5cd37
REPAIR_EXECUTION_SHA=f2bb244daf1b2d9515bee59799095fcbdd44414acb16b06e65e8298bd87c62b7
REPAIR_COMPLETION_SHA=7bbff5dd3721ba436f79cb984091e7aa5815642629ab2c5615a6f2d9aacaa592
RESOURCE_RESULT="$ROOT/reports/2026-08-16-atlas-cbc-resource-diagnostic-result.md"
RESOURCE_RESULT_SHA=241eeeb8278945ceadac78ea7ad1dcd40ea8ddb597590d4b9e3bae92d6153e05
RESOURCE_RUN="$ROOT/reports/atlas-cbc-resource-diagnostic-runs/20260816-atlas-cbc-resource-diagnostic-v1"
RESOURCE_SUMMARY_SHA=c467332d78b09589680e9354ef9454d6c3f14a0193d4db15b559dde55af1472a
RESOURCE_COMPLETION_SHA=2412fa80e01e98633ded7224f544f2b5f19ff47c04971d8fc6e99d0413777ff1
PREFLIGHT_PROTOCOL="$ROOT/reports/2026-08-16-atlas-cbc-16g-preflight-protocol.md"
PREFLIGHT_PROTOCOL_SHA=4c09ba4065e5ac32af3873f149ca42c0dd922cadc21524fd277f404d7fdc45a7
PREFLIGHT_RUN="$ROOT/reports/atlas-cbc-16g-preflight-runs/20260816-atlas-cbc-16g-preflight-v1"
PREFLIGHT_MANIFEST_SHA=059cf942a06de76815151e34db1ba363535c17c2069e1ce7bd19486804a8334f
PREFLIGHT_EXECUTION_SHA=00a50351f571a606e8efb47ae8eea0134c911998e64fe85e9836cf0677dd5ae3

for SPEC in \
  "$PROTOCOL:$PROTOCOL_SHA" "$PAIR_REACH:$PAIR_REACH_SHA" \
  "$PACKAGING:$PACKAGING_SHA" "$SHARDING:$SHARDING_SHA" \
  "$REPAIR3:$REPAIR3_SHA" \
  "$REPAIR/validation.json:$REPAIR_VALIDATION_SHA" \
  "$REPAIR/execution.json:$REPAIR_EXECUTION_SHA" \
  "$REPAIR/completion.txt:$REPAIR_COMPLETION_SHA" \
  "$RESOURCE_RESULT:$RESOURCE_RESULT_SHA" \
  "$RESOURCE_RUN/summary.json:$RESOURCE_SUMMARY_SHA" \
  "$RESOURCE_RUN/completion.txt:$RESOURCE_COMPLETION_SHA" \
  "$PREFLIGHT_PROTOCOL:$PREFLIGHT_PROTOCOL_SHA" \
  "$PREFLIGHT_RUN/manifest.txt:$PREFLIGHT_MANIFEST_SHA" \
  "$PREFLIGHT_RUN/execution.txt:$PREFLIGHT_EXECUTION_SHA"; do
  FILE=${SPEC%:*}
  DIGEST=${SPEC##*:}
  [ -s "$FILE" ] && [ "$(sha256sum "$FILE" | awk '{print $1}')" = "$DIGEST" ] || {
    echo "ERROR: frozen ATLAS repair3 source differs: $FILE" >&2; exit 2; }
done

for FILE in "$PREFLIGHT_RUN/summary.json" "$PREFLIGHT_RUN/completion.txt"; do
  [ -s "$FILE" ] || {
    echo "ERROR: strict ATLAS 16 GiB preflight harvest is missing: $FILE" >&2
    exit 2
  }
done
"$ROOT/.venv/bin/python" - "$PREFLIGHT_RUN/summary.json" \
  "$PREFLIGHT_RUN/completion.txt" "$PREFLIGHT_RUN/manifest.txt" \
  "$PREFLIGHT_RUN/execution.txt" "$IMAGE" "$CODE_SHA" <<'PY'
import json, sys

summary=json.load(open(sys.argv[1],encoding="utf-8"))
completion=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[2],encoding="utf-8") if "=" in line)
manifest=dict(line.rstrip("\n").split("=",1) for line in open(sys.argv[3],encoding="utf-8") if "=" in line)
execution=open(sys.argv[4],encoding="utf-8").read().split()
image,code_sha=sys.argv[5:]
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
if any(summary.get(k)!=v for k,v in expected.items()):
 raise SystemExit("ERROR: ATLAS 16 GiB preflight did not license grid launch")
if completion.get("cell")!="2024-15" or completion.get("cpu")!="4" or completion.get("memory")!="16Gi" or completion.get("uses_realized_outcomes")!="false" or completion.get("persists_lineups")!="false" or completion.get("production_change_licensed")!="false":
 raise SystemExit("ERROR: ATLAS 16 GiB preflight completion differs")
if manifest.get("repair2_image")!=image or manifest.get("repair2_code_sha")!=code_sha or manifest.get("cpu")!="4" or manifest.get("memory")!="16Gi" or manifest.get("max_retries")!="0":
 raise SystemExit("ERROR: ATLAS 16 GiB preflight manifest differs")
if len(execution)!=5 or execution[:3]!=["2024","15","atlas-cbc-16g-preflight-2024-w15-v1"] or execution[3]!="atlas-cbc-16g-preflight-2024-w15-v1-ckjlj":
 raise SystemExit("ERROR: ATLAS 16 GiB preflight execution differs")
PY
PREFLIGHT_SUMMARY_SHA=$(sha256sum "$PREFLIGHT_RUN/summary.json" | awk '{print $1}')
PREFLIGHT_COMPLETION_SHA=$(sha256sum "$PREFLIGHT_RUN/completion.txt" | awk '{print $1}')

[ ! -e "$OUT" ] || {
  echo "ERROR: immutable ATLAS repair3 run directory exists" >&2; exit 3; }
for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    if gcloud storage objects describe "$PREFIX/slate-${SEASON}-${WEEK}.json" \
        --project "$PROJECT" >/dev/null 2>&1; then
      echo "ERROR: frozen ATLAS repair3 output exists: $SEASON/$WEEK" >&2
      exit 3
    fi
  done
done
for NAME in season-2023.json season-2024.json season-2025.json report.json; do
  if gcloud storage objects describe "$PREFIX/$NAME" \
      --project "$PROJECT" >/dev/null 2>&1; then
    echo "ERROR: frozen ATLAS repair3 aggregate exists: $NAME" >&2
    exit 3
  fi
done

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMAGE" "code_sha=$CODE_SHA" \
  "output_prefix=$PREFIX" "protocol_sha256=$PROTOCOL_SHA" \
  "pair_reach_amendment_sha256=$PAIR_REACH_SHA" \
  "packaging_repair_sha256=$PACKAGING_SHA" \
  "sharding_repair_sha256=$SHARDING_SHA" \
  "resource_repair3_protocol_sha256=$REPAIR3_SHA" \
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
  'uses_realized_outcomes=false' 'production_change_licensed=false' \
  'seasons=2023,2024,2025' 'weeks=1-18' 'slates=54' \
  'cpu=4' 'memory=16Gi' 'timeout_seconds=43200' 'max_retries=0' \
  'repair_treatment=cloud-run-resource-envelope-only' \
  'interaction_auxiliaries=binary' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

for SEASON in 2023 2024 2025; do
  for WEEK in $(seq 1 18); do
    JOB="atlas-md-s${SEASON}-w${WEEK}-r3"
    URI="$PREFIX/slate-${SEASON}-${WEEK}.json"
    gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
      --image "$IMAGE" --command python \
      --args scripts/run_atlas_matched_diversity_mvp.py,--season,"$SEASON",--week,"$WEEK",--output-uri,"$URI" \
      --set-env-vars CODE_SHA="$CODE_SHA",ANALYSIS_IMAGE="$IMAGE" \
      --service-account "$SERVICE_ACCOUNT" --cpu 4 --memory 16Gi \
      --tasks 1 --parallelism 1 --max-retries 0 --task-timeout 12h --quiet
    EXEC=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
      --region "$REGION" --async --format='value(metadata.name)')
    [ -n "$EXEC" ] || {
      echo "ERROR: ATLAS repair3 execution identity is missing" >&2; exit 1; }
    printf '%s %s %s %s %s\n' "$SEASON" "$WEEK" "$JOB" "$EXEC" "$URI" \
      | tee -a "$OUT/executions.txt"
  done
done
sha256sum "$OUT/manifest.txt" "$OUT/executions.txt" > "$OUT/launch.sha256"
echo "ATLAS_MATCHED_DIVERSITY_REPAIR3_LAUNCHED $RUN_ID"

