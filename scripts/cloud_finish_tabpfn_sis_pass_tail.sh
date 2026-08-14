#!/bin/bash
# Harvest and validate the frozen SIS opponent pass-tail cache executions.
# Usage: cloud_finish_tabpfn_sis_pass_tail.sh <CODE_SHA>
set -euo pipefail

CODE_SHA=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260813-tabpfn-sis-pass-tail-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-pass-tail-runs/$RUN_ID"
EXECUTIONS="$OUT/executions.txt"

[ -s "$EXECUTIONS" ] || { echo "ABORT: execution manifest missing"; exit 2; }
[ ! -e "$OUT/validation.json" ] || {
  echo "ABORT: immutable SIS pass-tail validation already exists"; exit 2; }
while read -r arm _job execution _table; do
  state=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  [ "$state" = True ] || {
    echo "ABORT: $arm execution $execution is not complete ($state)"; exit 1; }
  filter="resource.type=\"cloud_run_job\" AND "
  filter+="labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND "
  filter+='textPayload:"TABPFN_SIS_PASS_TAIL_JSON="'
  gcloud logging read "$filter" --project "$PROJECT" --limit 5 \
    --order asc --format='value(textPayload)' > "$OUT/${arm}_raw_log.txt"
done < "$EXECUTIONS"

"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_tabpfn_sis_pass_tail.py" \
  --control-log "$OUT/control_raw_log.txt" \
  --treatment-log "$OUT/treatment_raw_log.txt" \
  --features "$ROOT/scripts/tabpfn_gen/features.txt" \
  --code-sha "$CODE_SHA" \
  --inherited-table tabpfn_active_label_treatment_v2 \
  --output "$OUT/validation.json"
echo "TabPFN SIS pass-tail caches validated: $OUT/validation.json"
