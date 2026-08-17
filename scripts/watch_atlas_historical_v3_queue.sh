#!/usr/bin/env bash
set -uo pipefail

# Usage: watch_atlas_historical_v3_queue.sh <image@sha256:...> <code-sha> <build-id>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
UPSTREAM="$ROOT/reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair5"
OUT="$ROOT/reports/atlas-historical-score-runs/20260816-atlas-historical-score-diagnostic-v3"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

while [ ! -s "$UPSTREAM/completion.txt" ]; do
  if [ -s "$UPSTREAM/terminal-census-completion.txt" ]; then
    echo "ATLAS_HISTORICAL_V3_NOT_LICENSED_REPAIR5_TERMINALLY_INVALID"
    exit 0
  fi
  printf '%s ATLAS_HISTORICAL_V3_WAITING_FOR_REPAIR5\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done

if [ ! -s "$OUT/upstream-receipt.json" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/prepare_atlas_historical_v3_source_receipt.py" || exit $?
fi

if [ ! -s "$OUT/execution.txt" ]; then
  "$ROOT/scripts/cloud_atlas_historical_score_diagnostic_v3.sh" \
    "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?
fi
read -r _job execution _uri < "$OUT/execution.txt"
while true; do
  state=$(gcloud run jobs executions describe "$execution" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)') || exit $?
  printf '%s ATLAS_HISTORICAL_V3_STATUS state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
  [ "$state" != Unknown ] && break
  sleep 300
done

finish_rc=0
if [ ! -s "$OUT/completion.txt" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/finish_atlas_historical_score_diagnostic_v3.py" || finish_rc=$?
fi
if [ ! -s "$OUT/completion.txt" ] || [ ! -s "$OUT/execution.json" ]; then
  exit "${finish_rc:-1}"
fi
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/historical_outcome_lease.py" release \
  --receipt "$OUT/historical-outcome-lease.json" \
  --execution "$OUT/execution.json" \
  --completion "$OUT/completion.txt" || exit $?
echo "ATLAS_HISTORICAL_V3_QUEUE_COMPLETE"
exit "$finish_rc"
