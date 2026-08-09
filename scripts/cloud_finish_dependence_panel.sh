#!/bin/bash
# Harvest exact dependence executions and apply the frozen three-season gate.
# Usage: bash scripts/cloud_finish_dependence_panel.sh <RUN_ID>
set -euo pipefail

RUN_ID=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/dependence-runs/$RUN_ID"
EXECS="$OUT/executions.txt"

case "$RUN_ID" in ""|*[!A-Za-z0-9_-]*) echo "ABORT: invalid run id"; exit 2;; esac
[ -s "$EXECS" ] || { echo "ABORT: missing execution manifest"; exit 2; }
[ "$(wc -l < "$EXECS")" -eq 3 ] || {
  echo "ABORT: dependence manifest must contain exactly three executions"; exit 2; }

reports=()
while read -r season job execution; do
  state=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  succeeded=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.succeededCount)')
  failed=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.failedCount)')
  [ "$state" = "True" ] && [ "${succeeded:-0}" = "1" ] \
    && [ "${failed:-0}" = "0" ] || {
      echo "ABORT: $execution is not a clean success"; exit 1; }
  report="$OUT/$season-gate.txt"
  gcloud logging read \
    "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND textPayload:\"schaake-gate \"" \
    --project "$PROJECT" --limit 20 --order asc \
    --format='value(textPayload)' > "$report"
  grep -q 'schaake-gate {' "$report" || {
    echo "ABORT: dependence report absent for $execution"; exit 1; }
  gcloud logging read \
    "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND textPayload:\"candidate generation skipped\"" \
    --project "$PROJECT" --limit 5 --order asc \
    --format='value(textPayload)' > "$OUT/$season-diagnostic-exit.txt"
  grep -q 'candidate generation skipped' \
    "$OUT/$season-diagnostic-exit.txt" || {
      echo "ABORT: diagnostic-only exit absent for $execution"; exit 1; }
  reports+=("$report")
done < "$EXECS"

"$ROOT/.venv/bin/python" "$ROOT/scripts/compare_dependence_panel.py" \
  "${reports[@]}" --output "$OUT/gate.json" > "$OUT/gate.txt"
echo "Dependence gate recorded: $OUT/gate.json"
