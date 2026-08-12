#!/bin/bash
# Launch the two frozen GPU cache-generation arms without waiting for scores.
# Usage: bash scripts/cloud_tabpfn_active_label.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260811-tabpfn-active-label-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-active-label-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-active-label-protocol.md"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
[ -s "$PROTOCOL" ] || { echo "ABORT: frozen protocol missing"; exit 2; }
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable active-label executions already recorded"; exit 2; }

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" \
  "image=$IMG" \
  "code_sha=$CODE_SHA" \
  'target_seasons=2022 2023 2024 2025' \
  'context=strictly earlier seasons' \
  'context_max=28000' \
  'random_seed=7' \
  'n_estimators=4' \
  'tabpfn_version=2.2.1' \
  'control_table=nfl_features.tabpfn_active_label_control_v1' \
  'treatment_table=nfl_features.tabpfn_active_label_treatment_v1' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

launch_arm() {
  local arm=$1
  local suffix=$2
  local table=$3
  local job="tabpfn-active-${suffix}"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMG" \
    --set-env-vars "GCP_PROJECT=$PROJECT,TABPFN_ACTIVE_LABEL_ARM=$arm,TABPFN_OUTPUT_TABLE=$table,CODE_SHA=$CODE_SHA" \
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

launch_arm control ctl tabpfn_active_label_control_v1
launch_arm active_only trt tabpfn_active_label_treatment_v1

echo "TABPFN_ACTIVE_LABEL_LAUNCHED $OUT"
