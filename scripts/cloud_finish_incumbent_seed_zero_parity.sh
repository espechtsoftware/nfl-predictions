#!/bin/bash
# Finish the frozen explicit-seed-zero smoke and launch its exact one-slate
# comparison against the accepted incumbent.
set -euo pipefail

PROJECT=nfl-predictions-503414
REGION=us-central1
PANEL=20260813-incumbent-seed-zero-parity-v1
REFERENCE=20260812-pitclean-e80-selected-tabpfn-active-v2
ROOT=$(cd "$(dirname "$0")/.." && pwd)
OUT="$ROOT/reports/panel-runs/$PANEL"
EXEC=$(cat "$OUT/execution.txt")
IMG=$(awk -F= '$1=="image" {print $2}' "$OUT/manifest.txt")
[ -n "$EXEC" ] && [ -n "$IMG" ] || {
  echo "ABORT: seed-zero manifest/execution incomplete"; exit 2; }
STATE=$(gcloud run jobs executions describe "$EXEC" --project "$PROJECT" \
  --region "$REGION" --format='value(status.conditions[0].status)')
[ "$STATE" = True ] || {
  echo "ABORT: seed-zero execution $EXEC is not complete ($STATE)"; exit 1; }
bash "$ROOT/scripts/cloud_compare_exact_replay.sh" \
  "$IMG" "$REFERENCE" "$PANEL" promoted slate-only
