#!/bin/bash
# Launch the frozen current-stack Route C/M GPU cache pair.
# Usage: cloud_tabpfn_route_channel_i1.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260814-tabpfn-route-channel-i1-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-route-channel-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-14-route-channel-i1-protocol.md"
PRIOR="$ROOT/reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-v2-pit-clean/validation.json"
PHASE_S="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1/report.json"
EXPECTED_PRIOR_SHA=e6b26ed7e899beb9fb5ef7bd622f644fdbefcbced121e5d15c5ff029fcf7de35

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable GPU image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$PRIOR" "$PHASE_S"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ "$(sha256sum "$PRIOR" | awk '{print $1}')" = "$EXPECTED_PRIOR_SHA" ] || {
  echo "ABORT: accepted active-label validation changed"; exit 2; }
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable Route-channel executions already recorded"; exit 2; }

"$ROOT/.venv/bin/python" - "$PHASE_S" "$PRIOR" <<'PY'
import json
import sys
phase = json.load(open(sys.argv[1], encoding="utf-8"))
prior = json.load(open(sys.argv[2], encoding="utf-8"))
if not phase.get("mechanical_passes") or phase.get("failures") or \
        phase.get("result", {}).get("decision", {}).get("selected_arm") \
        not in {"control", "treatment"}:
    raise SystemExit("ABORT: Phase S does not have a valid frozen decision")
if prior.get("version") != "v2" or not prior.get("passes") or \
        prior.get("disposition") != "tabpfn-active-label-caches-valid":
    raise SystemExit("ABORT: accepted active-label cache validation differs")
PY

for table in tabpfn_route_channel_control_v1 tabpfn_route_channel_marginal_v1; do
  if bq show --project_id="$PROJECT" "nfl_features.$table" >/dev/null 2>&1; then
    echo "ABORT: write-once Route-channel table already exists: $table"
    exit 2
  fi
done

SOURCE=$(
  bq query --project_id="$PROJECT" --use_legacy_sql=false --format=csv \
    'SELECT COUNT(*) AS n, BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum FROM `nfl-predictions-503414.nfl_features.player_week_training` t' \
    | tail -1 | tr -d '[:space:]'
)
[ "$SOURCE" = "102927,1904430067081090565" ] || {
  echo "ABORT: Route-channel source snapshot differs: $SOURCE"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "incumbent_validation=$PRIOR" \
  "incumbent_validation_sha256=$EXPECTED_PRIOR_SHA" \
  "phase_s_report=$PHASE_S" \
  "phase_s_report_sha256=$(sha256sum "$PHASE_S" | awk '{print $1}')" \
  'source_rows=102927' 'source_checksum=1904430067081090565' \
  'target_seasons=2022 2023 2024 2025' \
  'label_law=active_only' 'context=strictly earlier seasons' \
  'context_max=28000' 'random_seed=7' 'n_estimators=4' \
  'tabpfn_version=2.2.1' \
  'control_table=nfl_features.tabpfn_route_channel_control_v1' \
  'marginal_table=nfl_features.tabpfn_route_channel_marginal_v1' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

launch_arm() {
  local arm=$1
  local suffix=$2
  local table=$3
  local job="tabpfn-route-i1-$suffix"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMG" \
    --set-env-vars "GCP_PROJECT=$PROJECT,TABPFN_ROUTE_CHANNEL_ARM=$arm,TABPFN_OUTPUT_TABLE=$table,CODE_SHA=$CODE_SHA" \
    --memory 16Gi --cpu 4 --gpu 1 --gpu-type nvidia-l4 \
    --no-gpu-zonal-redundancy --max-retries 0 --task-timeout 3600 \
    --service-account "$SERVICE_ACCOUNT" >/dev/null
  local deployed
  deployed=$(gcloud run jobs describe "$job" --project "$PROJECT" \
    --region "$REGION" \
    --format='value(spec.template.spec.template.spec.containers[0].image)')
  [ "$deployed" = "$IMG" ] || {
    echo "ABORT: $job deployed $deployed, expected $IMG"; exit 1; }
  local execution
  execution=$(gcloud run jobs execute "$job" --project "$PROJECT" \
    --region "$REGION" --async --format='value(metadata.name)')
  [ -n "$execution" ] || { echo "ABORT: $arm execution id missing"; exit 1; }
  printf '%s %s %s %s\n' "$arm" "$job" "$execution" "$table" \
    | tee -a "$OUT/executions.txt"
}

launch_arm control control tabpfn_route_channel_control_v1
launch_arm marginal marginal tabpfn_route_channel_marginal_v1
echo "TABPFN_ROUTE_CHANNEL_LAUNCHED $OUT"
