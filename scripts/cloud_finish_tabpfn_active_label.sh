#!/bin/bash
# Harvest and mechanically validate the two frozen GPU cache-generation arms.
# Usage: bash scripts/cloud_finish_tabpfn_active_label.sh <CODE_SHA>
set -euo pipefail

CODE_SHA=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-tabpfn-active-label-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-active-label-runs/$RUN_ID"
EXECUTIONS="$OUT/executions.txt"

[ -s "$EXECUTIONS" ] || { echo "ABORT: execution manifest missing"; exit 2; }
[ ! -e "$OUT/validation.json" ] || {
  echo "ABORT: immutable active-label validation already exists"; exit 2; }

while read -r arm _job execution _table; do
  state=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  [ "$state" = True ] || {
    echo "ABORT: $arm execution $execution is not cleanly complete ($state)"
    exit 1
  }
  filter="resource.type=\"cloud_run_job\" AND "
  filter+="labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND "
  filter+='textPayload:"TABPFN_ACTIVE_LABEL_JSON="'
  gcloud logging read "$filter" --project "$PROJECT" --limit 5 \
    --order asc --format='value(textPayload)' > "$OUT/${arm}_raw_log.txt"
done < "$EXECUTIONS"

"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_tabpfn_active_label.py" \
  --control-log "$OUT/control_raw_log.txt" \
  --treatment-log "$OUT/active_only_raw_log.txt" \
  --code-sha "$CODE_SHA" \
  --output "$OUT/validation.json"

echo "TabPFN active-label caches validated: $OUT/validation.json"
