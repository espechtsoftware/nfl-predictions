#!/usr/bin/env bash
set -uo pipefail

# Usage: watch_coherent_market_state_queue.sh <build-id> <code-sha> <tag>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
BUILD_ID=${1:-}
CODE_SHA=${2:-}
TAG=${3:-}
RUN_ID=20260816-coherent-market-state-scorefree-v1
OUT="$ROOT/reports/coherent-market-state-runs/$RUN_ID"

[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] && \
  [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] && \
  [[ "$TAG" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:coherent-market-state-[0-9a-f]{7}$ ]] || {
  echo "Usage: $0 <build-id> <code-sha> <canonical-tag>" >&2
  exit 2
}

execution_status() {
  gcloud run jobs executions describe "$1" --project "$PROJECT" \
    --region "$REGION" --format=json | "$ROOT/.venv/bin/python" -c '
import json, sys
value = json.load(sys.stdin)
completed = [
    row for row in value.get("status", {}).get("conditions", [])
    if row.get("type") == "Completed"
]
print(completed[0].get("status", "Unknown") if len(completed) == 1 else "Unknown")
'
}

while true; do
  BUILD_STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --format='value(status)') || exit $?
  printf '%s COHERENT_MARKET_STATE_BUILD status=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$BUILD_STATUS"
  case "$BUILD_STATUS" in
    SUCCESS) break ;;
    QUEUED|PENDING|WORKING) sleep 60 ;;
    *) exit 2 ;;
  esac
done
DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
  --format='value(results.images[0].digest)') || exit $?
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
IMAGE="${TAG%:*}@${DIGEST}"

while [ ! -e "$OUT" ]; do
  bash "$ROOT/scripts/cloud_coherent_market_state_scorefree.sh" \
    "$IMAGE" "$CODE_SHA" "$BUILD_ID"
  RC=$?
  if [ "$RC" -eq 0 ]; then
    break
  fi
  [ ! -e "$OUT" ] || exit "$RC"
  printf '%s COHERENT_MARKET_STATE_QUEUE_NOT_RELEASED rc=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RC"
  sleep 300
done

while true; do
  unknown=0
  while read -r _season _week _job execution _uri; do
    state=$(execution_status "$execution") || exit $?
    [ "$state" = Unknown ] && unknown=$((unknown + 1))
  done < "$OUT/executions.txt"
  printf '%s COHERENT_MARKET_STATE_PRIMARY_STATUS running=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown"
  [ "$unknown" -eq 0 ] && break
  sleep 300
done

bash "$ROOT/scripts/cloud_prepare_coherent_market_state_attempts.sh"
ATTEMPT_RC=$?
if [ "$ATTEMPT_RC" -ne 0 ]; then
  if [ "$ATTEMPT_RC" -eq 10 ]; then
    echo COHERENT_MARKET_STATE_TERMINAL_INVALID_PRIMARY
  fi
  exit "$ATTEMPT_RC"
fi

while true; do
  unknown=0
  succeeded=0
  failed=0
  while read -r _season _week _job execution _uri; do
    state=$(execution_status "$execution") || exit $?
    case "$state" in
      Unknown) unknown=$((unknown + 1)) ;;
      True) succeeded=$((succeeded + 1)) ;;
      *) failed=$((failed + 1)) ;;
    esac
  done < "$OUT/accepted-executions.txt"
  printf '%s COHERENT_MARKET_STATE_ACCEPTED_STATUS running=%s succeeded=%s failed=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown" "$succeeded" "$failed"
  [ "$unknown" -eq 0 ] && break
  sleep 300
done
[ "$failed" -eq 0 ] || exit 10
bash "$ROOT/scripts/cloud_finish_coherent_market_state_scorefree.sh"
