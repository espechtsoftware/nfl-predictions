#!/usr/bin/env bash
set -uo pipefail

# Usage: watch_stack_core_shell_support_queue.sh <build-id> <code-sha> <tag>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
BUILD_ID=${1:-}
CODE_SHA=${2:-}
TAG=${3:-}
OUT="$ROOT/reports/stack-core-shell-support-runs/20260816-stack-core-shell-control-support-census-v1"

[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] && \
  [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] && \
  [[ "$TAG" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:stack-shell-support-[0-9a-f]{7}$ ]] || {
  echo "Usage: $0 <build-id> <code-sha> <canonical-tag>" >&2
  exit 2
}

execution_status() {
  gcloud run jobs executions describe "$1" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)'
}

while true; do
  BUILD_STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --format='value(status)') || exit $?
  printf '%s STACK_CORE_SHELL_BUILD_STATUS status=%s\n' \
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
  bash "$ROOT/scripts/cloud_stack_core_shell_support_census.sh" \
    "$IMAGE" "$CODE_SHA" "$BUILD_ID"
  RC=$?
  if [ "$RC" -eq 0 ]; then
    break
  fi
  [ ! -e "$OUT" ] || exit "$RC"
  printf '%s STACK_CORE_SHELL_QUEUE_NOT_RELEASED rc=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$RC"
  sleep 300
done

while true; do
  unknown=0
  while read -r _season _week _job execution _uri; do
    state=$(execution_status "$execution") || exit $?
    [ "$state" = Unknown ] && unknown=$((unknown + 1))
  done < "$OUT/executions.txt"
  printf '%s STACK_CORE_SHELL_PRIMARY_STATUS running=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$unknown"
  [ "$unknown" -eq 0 ] && break
  sleep 300
done

PYTHONPATH="$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/manage_stack_core_shell_support_attempts.py" prepare \
  --output-dir "$OUT"
ATTEMPT_RC=$?
[ "$ATTEMPT_RC" -eq 0 ] || exit "$ATTEMPT_RC"
DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
  "$OUT/attempt-resolution.json") || exit $?
case "$DISPOSITION" in
  accepted-primary-population|accepted-population-with-platform-replacements) ;;
  *)
    echo "STACK_CORE_SHELL_SUPPORT_STOPS_AFTER_ATTEMPTS $DISPOSITION"
    exit 10
    ;;
esac

bash "$ROOT/scripts/cloud_finish_stack_core_shell_support_census.sh"
