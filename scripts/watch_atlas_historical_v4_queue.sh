#!/usr/bin/env bash
set -uo pipefail

# Usage: watch_atlas_historical_v4_queue.sh <image@sha256:...> <code-sha> <build-id>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
UPSTREAM="$ROOT/reports/atlas-matched-diversity-runs/20260817-atlas-matched-diversity-mvp-v1-repair6"
OUT="$ROOT/reports/atlas-historical-score-runs/20260817-atlas-historical-score-diagnostic-v4"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

while [ ! -s "$UPSTREAM/hybrid-completion.txt" ]; do
  if [ -s "$UPSTREAM/canary-completion.txt" ] && \
      ! grep -qx 'disposition=repair6-dual-canary-passes' \
        "$UPSTREAM/canary-completion.txt"; then
    echo "ATLAS_HISTORICAL_V4_NOT_LICENSED_REPAIR6_CANARY_FAILED"
    exit 0
  fi
  printf '%s ATLAS_HISTORICAL_V4_WAITING_FOR_REPAIR6_HYBRID\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
if ! grep -qx 'disposition=valid-complete-repair6-hybrid-population' \
    "$UPSTREAM/hybrid-completion.txt"; then
  echo "ATLAS_HISTORICAL_V4_NOT_LICENSED_HYBRID_INVALID"
  exit 0
fi
if [ ! -s "$OUT/upstream-receipt.json" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/prepare_atlas_historical_v4_source_receipt.py" || exit $?
fi
if [ ! -s "$OUT/execution.txt" ]; then
  "$ROOT/scripts/cloud_atlas_historical_score_diagnostic_v4.sh" \
    "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?
fi
read -r _job execution _uri < "$OUT/execution.txt"
while true; do
  state=$(gcloud run jobs executions describe "$execution" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)') || exit $?
  printf '%s ATLAS_HISTORICAL_V4_STATUS state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
  [ "$state" != Unknown ] && break
  sleep 300
done
finish_rc=0
if [ ! -s "$OUT/completion.txt" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/finish_atlas_historical_score_diagnostic_v4.py" || finish_rc=$?
fi
if [ ! -s "$OUT/completion.txt" ] || [ ! -s "$OUT/execution.json" ]; then
  exit "${finish_rc:-1}"
fi
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/historical_outcome_lease.py" release \
  --receipt "$OUT/historical-outcome-lease.json" \
  --execution "$OUT/execution.json" \
  --completion "$OUT/completion.txt" || exit $?
printf '%s\n' \
  "completed_at=$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  'outcome_lease_released=true' \
  "completion_sha256=$(sha256sum "$OUT/completion.txt" | awk '{print $1}')" \
  > "$OUT/queue-completion.txt"
sha256sum "$OUT/queue-completion.txt" > "$OUT/queue-completion.sha256"
echo "ATLAS_HISTORICAL_V4_QUEUE_COMPLETE"
exit "$finish_rc"
