#!/bin/bash
# One transport-only rerun after the successful evaluator report exceeded
# Cloud Logging's per-entry limit.  The new image emits the same report as
# compressed, numbered chunks; model/gate inputs remain frozen.
# Usage: cloud_retry_tabpfn_sis_pass_tail_harvest.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-pass-tail-runs/20260813-tabpfn-sis-pass-tail-final-served-v1"
PRIOR=$(tr -d '[:space:]' < "$OUT/execution_retry.txt")
EXEC_FILE="$OUT/execution_harvest_retry.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
[ ! -e "$EXEC_FILE" ] && [ ! -e "$OUT/report.json" ] || {
  echo "ABORT: SIS pass-tail harvest retry already recorded"; exit 2; }
state=$(gcloud run jobs executions describe "$PRIOR" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$state" = True ] || { echo "ABORT: prior evaluator was not successful"; exit 2; }
grep -q '^TABPFN_SIS_PASS_TAIL_FINAL_SERVED_JSON=' "$OUT/raw_log.txt" || {
  echo "ABORT: truncated prior report evidence missing"; exit 2; }
PANEL=$(awk -F= '$1=="panel" {print $2}' "$OUT/manifest.txt")
DIRICHLET_K=$(awk -F= '$1=="dirichlet_k" {print $2}' "$OUT/manifest.txt")
[ "$PANEL" = 20260811-pitclean-e80-k1-role12union-a12ab31 ] || {
  echo "ABORT: historical panel differs"; exit 2; }
[ "$DIRICHLET_K" = 28.154043586960896 ] || {
  echo "ABORT: finite K differs"; exit 2; }

ENVS="GCP_PROJECT=$PROJECT,MODEL_ENSEMBLE=1,TABPFN_SIS_PASS_TAIL_PANEL_ID=$PANEL"
ENVS="$ENVS,TABPFN_ACCEPTED_USAGE_LAW=dirichlet"
ENVS="$ENVS,TABPFN_ACCEPTED_DIRICHLET_K=$DIRICHLET_K"
ENVS="$ENVS,GAME_SIM_USAGE=dirichlet,DIRICHLET_K=$DIRICHLET_K"
JOB=tabpfn-sis-pass-tail-final-served-v1
gcloud run jobs deploy "$JOB" --project "$PROJECT" --region "$REGION" \
  --image "$IMG" --command nfl-dfs \
  --args "tabpfn-sis-pass-tail-final-served,--panel,$PANEL" \
  --set-env-vars "$ENVS" --memory 16Gi --cpu 8 \
  --max-retries 0 --task-timeout 10800 >/dev/null
deployed=$(gcloud run jobs describe "$JOB" --project "$PROJECT" \
  --region "$REGION" \
  --format='value(spec.template.spec.template.spec.containers[0].image)')
[ "$deployed" = "$IMG" ] || { echo "ABORT: harvest retry image differs"; exit 1; }
execution=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$execution" ] || { echo "ABORT: harvest retry execution missing"; exit 1; }
printf '%s\n' "$execution" > "$EXEC_FILE"
printf '%s\n' "harvest_retry_image=$IMG" "harvest_retry_code_sha=$CODE_SHA" \
  "harvest_retry_reason=cloud_logging_text_entry_truncation" \
  > "$OUT/harvest_retry_manifest.txt"
echo "TABPFN_SIS_PASS_TAIL_HARVEST_RETRIED $execution"
