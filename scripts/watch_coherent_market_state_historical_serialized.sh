#!/usr/bin/env bash
set -uo pipefail

# Operational wrapper: acquire the shared outcome lease only after score-free
# readiness, then run the unchanged frozen coherent historical watcher.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
BUILD_ID=${1:-}
CODE_SHA=${2:-}
TAG=${3:-}
UPSTREAM="$ROOT/reports/coherent-market-state-runs/20260816-coherent-market-state-scorefree-v1"
OUT="$ROOT/reports/coherent-market-state-historical-score-runs/20260817-coherent-market-state-historical-score-v1"
LEASE_DIR="$ROOT/reports/historical-outcome-leases"
LEASE="$LEASE_DIR/20260817-coherent-market-state-historical-score-v1.json"

while [ ! -s "$UPSTREAM/completion.txt" ]; do
  printf '%s COHERENT_HISTORICAL_SERIALIZER_WAITS_FOR_SCOREFREE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
while true; do
  STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --format='value(status)') || exit $?
  case "$STATUS" in SUCCESS) break;; QUEUED|PENDING|WORKING) sleep 60;; *) exit 2;; esac
done
DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
  --format='value(results.images[0].digest)') || exit $?
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
IMAGE="${TAG%:*}@$DIGEST"
mkdir -p "$LEASE_DIR"
while true; do
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/historical_outcome_lease.py" acquire \
    --run-id 20260817-coherent-market-state-historical-score-v1 \
    --job coherent-market-historical-v1 --code-sha "$CODE_SHA" --image "$IMAGE" \
    --receipt "$LEASE" && break
  [ ! -e "$LEASE" ] || exit 2
  printf '%s COHERENT_HISTORICAL_SERIALIZER_WAITS_FOR_LEASE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
bash "$ROOT/scripts/watch_coherent_market_state_historical_score_queue.sh" \
  "$BUILD_ID" "$CODE_SHA" "$TAG"
RC=$?
if [ "$RC" -eq 0 ] && [ -s "$OUT/execution.json" ] && \
    [ -s "$OUT/completion.txt" ]; then
  {
    printf '%s\n' 'run_id=20260817-coherent-market-state-historical-score-v1'
    cat "$OUT/completion.txt"
  } > "$OUT/lease-completion.txt"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/historical_outcome_lease.py" release \
    --receipt "$LEASE" --execution "$OUT/execution.json" \
    --completion "$OUT/lease-completion.txt" || exit $?
fi
exit "$RC"
