#!/bin/bash
# Harvest and mechanically validate the frozen canonical PIT-clean cache.
# Usage: bash scripts/cloud_finish_tabpfn_canonical_pit.sh <CODE_SHA>
set -euo pipefail

CODE_SHA=${1:-}
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-tabpfn-canonical-pit-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/tabpfn-canonical-runs/$RUN_ID"
EXECUTION_FILE="$OUT/execution.txt"

[ -s "$EXECUTION_FILE" ] || { echo "ABORT: execution manifest missing"; exit 2; }
[ ! -e "$OUT/validation.json" ] || {
  echo "ABORT: immutable canonical validation already exists"; exit 2; }
read -r _job execution _table < "$EXECUTION_FILE"
state=$(gcloud run jobs executions describe "$execution" \
  --project "$PROJECT" --region "$REGION" \
  --format='value(status.conditions[0].status)')
[ "$state" = True ] || {
  echo "ABORT: execution $execution is not cleanly complete ($state)"
  exit 1
}
filter="resource.type=\"cloud_run_job\" AND "
filter+="labels.\"run.googleapis.com/execution_name\"=\"$execution\" AND "
filter+='textPayload:"TABPFN_GEN_JSON="'
gcloud logging read "$filter" --project "$PROJECT" --limit 5 \
  --order asc --format='value(textPayload)' > "$OUT/raw_log.txt"

"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_tabpfn_canonical_pit.py" \
  --log "$OUT/raw_log.txt" \
  --code-sha "$CODE_SHA" \
  --output "$OUT/validation.json"

echo "Canonical PIT-clean TabPFN cache validated: $OUT/validation.json"
