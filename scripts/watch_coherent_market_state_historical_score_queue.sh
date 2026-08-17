#!/usr/bin/env bash
set -uo pipefail

# Usage: watch_coherent_market_state_historical_score_queue.sh <build-id> <code-sha> <tag>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
BUILD_ID=${1:-}
CODE_SHA=${2:-}
TAG=${3:-}
UPSTREAM="$ROOT/reports/coherent-market-state-runs/20260816-coherent-market-state-scorefree-v1"
OUT="$ROOT/reports/coherent-market-state-historical-score-runs/20260817-coherent-market-state-historical-score-v1"

[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] && \
  [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] && \
  [[ "$TAG" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:coherent-market-historical-[0-9a-f]{7}$ ]] || {
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
  printf '%s COHERENT_MARKET_STATE_HISTORICAL_BUILD status=%s\n' \
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

while [ ! -s "$UPSTREAM/completion.txt" ]; do
  printf '%s COHERENT_MARKET_STATE_HISTORICAL_WAITS_FOR_SCOREFREE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done

bash "$ROOT/scripts/cloud_coherent_market_state_historical_score.sh" \
  "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?
read -r _job execution _uri < "$OUT/execution.txt"
while true; do
  state=$(execution_status "$execution") || exit $?
  printf '%s COHERENT_MARKET_STATE_HISTORICAL_STATUS state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
  [ "$state" != Unknown ] && break
  sleep 300
done
bash "$ROOT/scripts/cloud_finish_coherent_market_state_historical_score.sh"
