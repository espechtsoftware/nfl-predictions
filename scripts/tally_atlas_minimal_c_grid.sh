#!/usr/bin/env bash
set -euo pipefail
# Tally the attempt-1 ATLAS C grid to terminal state WITHOUT finishing:
# reports per-cell success/failure so the collision census is complete.
# Amendment-4 evidence gathering; no finisher, no outcome read.
PROJECT=nfl-predictions-503414
REGION=us-central1
ROOT=$(cd "$(dirname "$0")/.." && pwd)
RUN_ID=20260818-atlas-minimal-world-selection-c-v1
OUT="$ROOT/reports/atlas-minimal-c-runs/$RUN_ID"
while :; do
  DONE=0; FAILED=0; RUNNING=0; FAILED_CELLS=""
  while read -r SEASON WEEK JOB EXECUTION URI; do
    STATE=$(gcloud run jobs executions describe "$EXECUTION" \
      --project "$PROJECT" --region "$REGION" \
      --format='value(status.conditions[0].status)' 2>/dev/null || echo "")
    case "$STATE" in
      True) DONE=$((DONE+1)) ;;
      False) FAILED=$((FAILED+1)); FAILED_CELLS="$FAILED_CELLS $SEASON-$WEEK" ;;
      *) RUNNING=$((RUNNING+1)) ;;
    esac
  done < "$OUT/executions.txt"
  printf '%s ATLAS_C_TALLY done=%s failed=%s running=%s failed_cells:%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$DONE" "$FAILED" "$RUNNING" "$FAILED_CELLS"
  [ "$RUNNING" = 0 ] && { echo "ATLAS_C_TALLY_TERMINAL done=$DONE failed=$FAILED"; exit 0; }
  sleep 300
done
