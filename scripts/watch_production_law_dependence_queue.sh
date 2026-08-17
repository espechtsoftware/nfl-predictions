#!/usr/bin/env bash
set -uo pipefail

# Usage: watch_production_law_dependence_queue.sh <build-id> <code-sha> <tag>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
BUILD_ID=${1:-}
CODE_SHA=${2:-}
TAG=${3:-}
LOCK="$ROOT/reports/production-law-dependence-runs/20260817-production-law-dependence-source-lock-v1"
COHERENT="$ROOT/reports/coherent-market-state-historical-score-runs/20260817-coherent-market-state-historical-score-v1"
OUT="$ROOT/reports/production-law-dependence-runs/20260817-production-law-dependence-remeasurement-v1"
JOB=production-law-dependence-v1

[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] && [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] && \
 [[ "$TAG" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:production-law-dependence-[0-9a-f]{7}$ ]] || exit 2
while true; do
  STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format='value(status)') || exit $?
  case "$STATUS" in SUCCESS) break;; QUEUED|PENDING|WORKING) sleep 60;; *) exit 2;; esac
done
DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" --format='value(results.images[0].digest)') || exit $?
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
IMAGE="${TAG%:*}@$DIGEST"

if [ ! -s "$LOCK/completion.txt" ]; then
  bash "$ROOT/scripts/cloud_production_law_dependence_source_lock.sh" \
    "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?
  read -r _job execution _uri < "$LOCK/execution.txt"
  while true; do
    state=$(gcloud run jobs executions describe "$execution" --project "$PROJECT" \
      --region "$REGION" --format='value(status.conditions[0].status)') || exit $?
    printf '%s PRODUCTION_LAW_DEPENDENCE_SOURCE_LOCK state=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
    [ "$state" != Unknown ] && break
    sleep 300
  done
  [ "$state" = True ] || exit 10
  bash "$ROOT/scripts/cloud_finish_production_law_dependence_source_lock.sh" || exit $?
fi

while [ ! -s "$COHERENT/completion.txt" ]; do
  printf '%s PRODUCTION_LAW_DEPENDENCE_WAITS_FOR_COHERENT_HISTORICAL\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
mkdir -p "$OUT"
while true; do
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/historical_outcome_lease.py" acquire \
    --run-id 20260817-production-law-dependence-remeasurement-v1 \
    --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" \
    --receipt "$OUT/lease-receipt.json" && break
  [ ! -e "$OUT/lease-receipt.json" ] || exit 2
  printf '%s PRODUCTION_LAW_DEPENDENCE_WAITS_FOR_OUTCOME_LEASE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
LEASE_SHA=$(sha256sum "$OUT/lease-receipt.json" | awk '{print $1}')
bash "$ROOT/scripts/cloud_production_law_dependence_remeasurement.sh" \
  "$IMAGE" "$CODE_SHA" "$BUILD_ID" "$LEASE_SHA" || exit $?
read -r _job execution _uri < "$OUT/execution.txt"
while true; do
  state=$(gcloud run jobs executions describe "$execution" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)') || exit $?
  printf '%s PRODUCTION_LAW_DEPENDENCE_OUTCOME state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
  [ "$state" != Unknown ] && break
  sleep 300
done
[ "$state" = True ] || exit 10
bash "$ROOT/scripts/cloud_finish_production_law_dependence_remeasurement.sh" || exit $?
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/historical_outcome_lease.py" release \
  --receipt "$OUT/lease-receipt.json" --execution "$OUT/execution.json" \
  --completion "$OUT/completion.txt"
