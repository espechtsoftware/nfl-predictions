#!/bin/bash
# Report status of the immutable Phase R execution set without reading scores.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
LIST="$ROOT/reports/game-team-usage-runs/20260813-game-team-usage-phase-r-v1/executions.txt"
[ -s "$LIST" ] || { echo "ABORT: Phase R execution list missing"; exit 2; }

while read -r arm rep season panel job execution; do
  state=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  printf '%s %s %s %s %s\n' "$arm" "$rep" "$season" "$state" "$execution"
done < "$LIST"
