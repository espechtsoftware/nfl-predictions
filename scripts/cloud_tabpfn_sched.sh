#!/bin/bash
# Launch the frozen SCHED feature-contract cache pair after active-label selection.
# Usage: cloud_tabpfn_sched.sh <GPU_IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
SERVICE_ACCOUNT=817589974517-compute@developer.gserviceaccount.com
RUN_ID=20260812-tabpfn-sched-v1-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sched-runs/$RUN_ID"
PROTOCOL="$ROOT/reports/2026-08-11-tabpfn-schedule-feature-sync-protocol.md"
ACTIVE_SELECTION="$ROOT/reports/tabpfn-active-label-runs/20260812-active-label-exact80-v2-pit-clean/selected_active_label.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable GPU image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
for path in "$PROTOCOL" "$ACTIVE_SELECTION"; do
  [ -s "$path" ] || { echo "ABORT: prerequisite missing: $path"; exit 2; }
done
[ ! -e "$OUT/executions.txt" ] || {
  echo "ABORT: immutable SCHED executions already recorded"; exit 2; }

ACTIVE_LAW=$(awk -F= '$1=="label_law" {print $2}' "$ACTIVE_SELECTION")
INHERITED_TABLE=$(awk -F= '$1=="cache_table" {print $2}' "$ACTIVE_SELECTION")
case "$ACTIVE_LAW" in
  current)
    LABEL_LAW=current
    [ "$INHERITED_TABLE" = tabpfn_projections_pit_v2 ] || {
      echo "ABORT: current-label branch does not select canonical v2 cache"; exit 2; }
    ;;
  active-only)
    LABEL_LAW=active_only
    [ "$INHERITED_TABLE" = tabpfn_active_label_treatment_v2 ] || {
      echo "ABORT: active-only branch does not select v2 treatment cache"; exit 2; }
    ;;
  *) echo "ABORT: active-label terminal law is invalid"; exit 2;;
esac
for table in tabpfn_sched_control_v1 tabpfn_sched_treatment_v1; do
  if bq show --project_id "$PROJECT" "$PROJECT:nfl_features.$table" \
      >/dev/null 2>&1; then
    echo "ABORT: write-once SCHED table already exists: $table"
    exit 2
  fi
done

mkdir -p "$OUT"
printf '%s\n' \
  "run_id=$RUN_ID" "image=$IMG" "code_sha=$CODE_SHA" \
  "protocol_sha256=$(sha256sum "$PROTOCOL" | awk '{print $1}')" \
  "active_selection=$ACTIVE_SELECTION" \
  "active_selection_sha256=$(sha256sum "$ACTIVE_SELECTION" | awk '{print $1}')" \
  "label_law=$LABEL_LAW" \
  "inherited_cache_table=$INHERITED_TABLE" \
  'target_seasons=2022 2023 2024 2025' \
  'context=strictly earlier seasons' 'context_max=28000' \
  'random_seed=7' 'n_estimators=4' 'tabpfn_version=2.2.1' \
  'control_table=nfl_features.tabpfn_sched_control_v1' \
  'treatment_table=nfl_features.tabpfn_sched_treatment_v1' \
  > "$OUT/manifest.txt"
: > "$OUT/executions.txt"

launch_arm() {
  local arm=$1
  local table=$2
  local job="tabpfn-sched-v1-$arm"
  gcloud run jobs deploy "$job" --project "$PROJECT" --region "$REGION" \
    --image "$IMG" \
    --set-env-vars "GCP_PROJECT=$PROJECT,TABPFN_SCHED_ARM=$arm,TABPFN_SCHED_LABEL_LAW=$LABEL_LAW,TABPFN_OUTPUT_TABLE=$table,CODE_SHA=$CODE_SHA" \
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

launch_arm control tabpfn_sched_control_v1
launch_arm treatment tabpfn_sched_treatment_v1
echo "TABPFN_SCHED_LAUNCHED $OUT"
