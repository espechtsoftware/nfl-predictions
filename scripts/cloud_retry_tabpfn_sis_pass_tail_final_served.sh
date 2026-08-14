#!/bin/bash
# One infrastructure-only retry after the original evaluator was blocked by
# its missing research-table license.  Caches, panel and frozen gate are reused.
# Usage: cloud_retry_tabpfn_sis_pass_tail_final_served.sh <IMAGE@sha256:...> <CODE_SHA>
set -euo pipefail

IMG=${1:-}
CODE_SHA=${2:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-pass-tail-runs/20260813-tabpfn-sis-pass-tail-final-served-v1"
ORIGINAL=$(tr -d '[:space:]' < "$OUT/execution.txt")
RETRY_FILE="$OUT/execution_retry.txt"

case "$IMG" in *@sha256:*) ;; *) echo "ABORT: immutable audit image required"; exit 2;; esac
case "$CODE_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]*) ;;
  *) echo "ABORT: immutable code SHA required"; exit 2;;
esac
[ ! -e "$RETRY_FILE" ] && [ ! -e "$OUT/report.json" ] || {
  echo "ABORT: SIS pass-tail retry already recorded"; exit 2; }
state=$(gcloud run jobs executions describe "$ORIGINAL" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$state" = False ] || { echo "ABORT: original execution did not fail"; exit 2; }
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
[ "$deployed" = "$IMG" ] || { echo "ABORT: retry image differs"; exit 1; }
execution=$(gcloud run jobs execute "$JOB" --project "$PROJECT" \
  --region "$REGION" --async --format='value(metadata.name)')
[ -n "$execution" ] || { echo "ABORT: retry execution missing"; exit 1; }
printf '%s\n' "$execution" > "$RETRY_FILE"
printf '%s\n' "retry_image=$IMG" "retry_code_sha=$CODE_SHA" \
  "retry_reason=research_table_allowlist_omission" \
  > "$OUT/retry_manifest.txt"
echo "TABPFN_SIS_PASS_TAIL_FINAL_SERVED_RETRIED $execution"
