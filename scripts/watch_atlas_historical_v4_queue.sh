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

repair6_closure_is_valid() {
  closure="$UPSTREAM/queue-closure.txt"
  receipt="$UPSTREAM/queue-closure.sha256"
  [ -s "$closure" ] && [ -s "$receipt" ] && \
    sha256sum -c "$receipt" >/dev/null 2>&1 && \
    [ "$(wc -l < "$closure")" = 6 ] && \
    [ "$(grep -c '^reason=' "$closure")" = 1 ] && \
    grep -qx 'disposition=repair6-closed-no-scoreable-population' "$closure" && \
    grep -qx 'uses_realized_outcomes=false' "$closure" && \
    grep -qx 'candidate_or_lineup_scores_read=false' "$closure" && \
    grep -qx 'production_change_licensed=false' "$closure" && \
    grep -Eq '^recorded_at=[0-9]{4}-[0-9]{2}-[0-9]{2}T' "$closure" || return 1
  reason=$(awk -F= '$1=="reason" {print substr($0,8)}' "$closure")
  case "$reason" in
    failure-classification-closed|dual-canary-execution-failed|\
repair6-grid-execution-failed|hybrid-population-invalid) return 0 ;;
    *) return 1 ;;
  esac
}

while [ ! -s "$UPSTREAM/hybrid-completion.txt" ]; do
  if [ -s "$UPSTREAM/queue-closure.txt" ]; then
    if repair6_closure_is_valid; then
      echo "ATLAS_HISTORICAL_V4_NOT_LICENSED_REPAIR6_CLOSED"
      exit 0
    fi
    echo "ERROR: ATLAS repair6 queue closure receipt differs" >&2
    exit 2
  fi
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
