#!/bin/bash
set -euo pipefail
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
LIST="$ROOT/reports/sis-asoe-phase-s-runs/20260813-sis-asoe-phase-s-v1/executions.txt"
[ -s "$LIST" ] || { echo "ABORT: Phase S execution list missing"; exit 2; }
while read -r rep season panel job execution; do
  state=$(gcloud run jobs executions describe "$execution" \
    --project "$PROJECT" --region "$REGION" \
    --format='value(status.conditions[0].status)')
  printf 'R%s %s %s %s\n' "$rep" "$season" "$state" "$execution"
done < "$LIST"
