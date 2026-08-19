#!/usr/bin/env bash
set -euo pipefail

# Poll the ATLAS C grid to terminal state, then run the strict finisher.
# Fails closed on the first failed cell (halt-and-disposition). Rerunnable
# after a crash; the finisher's create-only guard prevents double-finish.

PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260818-atlas-minimal-world-selection-c-v1
OUT="$ROOT/reports/atlas-minimal-c-runs/$RUN_ID"
PREFIX=gs://nfl-predictions-503414-raw/research/atlas-minimal-world-selection-c-runs/$RUN_ID

while :; do
  OBJECTS=$(gsutil ls "$PREFIX/slate-*.json" 2>/dev/null | wc -l)
  printf '%s ATLAS_C_GRID objects=%s/54\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$OBJECTS"
  [ "$OBJECTS" -ge 54 ] && break
  while read -r SEASON WEEK JOB EXECUTION URI; do
    gsutil -q stat "$URI" 2>/dev/null && continue
    STATE=$(gcloud run jobs executions describe "$EXECUTION" \
      --project "$PROJECT" --region "$REGION" \
      --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
    if [ "$STATE" = "False" ]; then
      printf '%s ATLAS_C_CELL_FAILED %s %s %s\n' \
        "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$SEASON" "$WEEK" "$EXECUTION"
      exit 2
    fi
  done < "$OUT/executions.txt"
  sleep 300
done
bash "$ROOT/scripts/cloud_finish_atlas_minimal_c.sh"
