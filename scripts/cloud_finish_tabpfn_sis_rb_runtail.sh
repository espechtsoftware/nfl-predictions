#!/bin/bash
# Harvest and validate the adaptive SIS RB run-tail caches.
set -euo pipefail

CODE_SHA=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260814-tabpfn-sis-rb-runtail-v1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sis-rb-runtail-runs/$RUN_ID"
EXECUTIONS="$OUT/executions.txt"

[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || {
  echo "ABORT: full immutable run-tail code SHA required"; exit 2; }
[ -s "$EXECUTIONS" ] || { echo "ABORT: run-tail execution manifest missing"; exit 2; }
[ ! -e "$OUT/validation.json" ] || {
  echo "ABORT: immutable run-tail validation exists"; exit 2; }
while read -r arm _job execution _table; do
  state=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  [ "$state" = True ] || {
    echo "ABORT: $arm run-tail execution $execution is not complete ($state)"; exit 1; }
  filter="resource.type=\"cloud_run_job\" AND "
  filter+="labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND "
  filter+='textPayload:"TABPFN_SIS_RB_RUNTAIL_JSON="'
  gcloud logging read "$filter" --project "$PROJECT" --limit 5 \
    --order asc --format='value(textPayload)' > "$OUT/${arm}_raw_log.txt"
done < "$EXECUTIONS"

"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_tabpfn_sis_rb_runtail.py" \
  --control-log "$OUT/control_raw_log.txt" \
  --treatment-log "$OUT/treatment_raw_log.txt" \
  --features "$ROOT/scripts/tabpfn_gen/features.txt" \
  --code-sha "$CODE_SHA" --output "$OUT/validation.json"
echo "TABPFN_SIS_RB_RUNTAIL_VALIDATED $OUT/validation.json"
