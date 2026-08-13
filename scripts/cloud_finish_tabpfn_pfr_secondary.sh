#!/bin/bash
# Harvest and mechanically validate all frozen PFR secondary cache arms.
# Usage: bash scripts/cloud_finish_tabpfn_pfr_secondary.sh <CODE_SHA>
set -euo pipefail

CODE_SHA=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-tabpfn-pfr-secondary-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-pfr-secondary-runs/$RUN_ID"
EXECUTIONS="$OUT/executions.txt"

[ -s "$EXECUTIONS" ] || { echo "ABORT: execution manifest missing"; exit 2; }
[ ! -e "$OUT/validation.json" ] || {
  echo "ABORT: immutable PFR validation already exists"; exit 2; }

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
  filter+='textPayload:"TABPFN_PFR_SECONDARY_JSON="'
  gcloud logging read "$filter" --project "$PROJECT" --limit 5 \
    --order asc --format='value(textPayload)' > "$OUT/${arm}_raw_log.txt"
done < "$EXECUTIONS"

"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_tabpfn_pfr_secondary.py" \
  --control-log "$OUT/control_raw_log.txt" \
  --drop-rates-log "$OUT/drop_rates_raw_log.txt" \
  --drop-top-cb-log "$OUT/drop_top_cb_raw_log.txt" \
  --drop-all-log "$OUT/drop_all_raw_log.txt" \
  --code-sha "$CODE_SHA" \
  --output "$OUT/validation.json"

echo "PFR secondary caches validated: $OUT/validation.json"
