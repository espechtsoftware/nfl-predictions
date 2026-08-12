#!/bin/bash
# Harvest and validate the two frozen TabPFN SCHED GPU cache executions.
# Usage: cloud_finish_tabpfn_sched.sh <CODE_SHA>
set -euo pipefail

CODE_SHA=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260812-tabpfn-sched-v1-pit-clean
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-sched-runs/$RUN_ID"
EXECUTIONS="$OUT/executions.txt"
MANIFEST="$OUT/manifest.txt"

[ -s "$EXECUTIONS" ] || { echo "ABORT: execution manifest missing"; exit 2; }
[ -s "$MANIFEST" ] || { echo "ABORT: run manifest missing"; exit 2; }
[ ! -e "$OUT/validation.json" ] || {
  echo "ABORT: immutable SCHED validation already exists"; exit 2; }
LABEL_LAW=$(awk -F= '$1=="label_law" {print $2}' "$MANIFEST")
INHERITED_TABLE=$(awk -F= '$1=="inherited_cache_table" {print $2}' "$MANIFEST")
case "$LABEL_LAW" in current|active_only) ;; *) echo "ABORT: invalid label law"; exit 2;; esac

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
  filter+='textPayload:"TABPFN_SCHED_JSON="'
  gcloud logging read "$filter" --project "$PROJECT" --limit 5 \
    --order asc --format='value(textPayload)' > "$OUT/${arm}_raw_log.txt"
done < "$EXECUTIONS"

"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_tabpfn_sched.py" \
  --control-log "$OUT/control_raw_log.txt" \
  --treatment-log "$OUT/treatment_raw_log.txt" \
  --features "$ROOT/scripts/tabpfn_sched/features_control.txt" \
  --code-sha "$CODE_SHA" --label-law "$LABEL_LAW" \
  --inherited-table "$INHERITED_TABLE" \
  --output "$OUT/validation.json"
echo "TabPFN SCHED caches validated: $OUT/validation.json"
