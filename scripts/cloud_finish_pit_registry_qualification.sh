#!/bin/bash
# Harvest and validate the three isolated PIT-clean registry jobs.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260811-pit-clean-registry-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/pit-tier1-runs/$RUN_ID"
[ -s "$OUT/executions.txt" ] || { echo "ABORT: execution manifest missing"; exit 2; }
[ ! -e "$OUT/validation.json" ] || { echo "ABORT: validation exists"; exit 2; }

while read -r variant _ensemble _job execution; do
  state=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  [ "$state" = True ] || {
    echo "ABORT: $variant execution $execution is incomplete ($state)"; exit 1; }
done < "$OUT/executions.txt"
ISO_WEEK=$(awk -F= '$1=="iso_week" {print $2}' "$OUT/manifest.txt")
"$ROOT/.venv/bin/python" "$ROOT/scripts/validate_pit_registry_qualification.py" \
  --project "$PROJECT" --prefix models_pit_v2 --iso-week "$ISO_WEEK" \
  --output "$OUT/validation.json"
