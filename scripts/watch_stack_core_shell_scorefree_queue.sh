#!/usr/bin/env bash
set -uo pipefail

# Usage: watch_stack_core_shell_scorefree_queue.sh <build-id> <code-sha> <tag>

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
BUILD_ID=${1:-}
CODE_SHA=${2:-}
TAG=${3:-}
RUN_ID=20260816-stack-core-shell-scorefree-v1
OUT="$ROOT/reports/stack-core-shell-runs/$RUN_ID"
SUPPORT="$ROOT/reports/stack-core-shell-support-runs/20260816-stack-core-shell-control-support-census-v1"

[[ "$BUILD_ID" =~ ^[0-9a-f-]{36}$ ]] && \
  [[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] && \
  [[ "$TAG" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs:stack-shell-treatment-[0-9a-f]{7}$ ]] || {
  echo "Usage: $0 <build-id> <code-sha> <canonical-tag>" >&2
  exit 2
}

while true; do
  BUILD_STATUS=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
    --region "$REGION" --format='value(status)') || exit $?
  printf '%s STACK_CORE_SHELL_TREATMENT_BUILD status=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$BUILD_STATUS"
  case "$BUILD_STATUS" in
    SUCCESS) break ;;
    QUEUED|PENDING|WORKING) sleep 60 ;;
    *) exit 2 ;;
  esac
done
DIGEST=$(gcloud builds describe "$BUILD_ID" --project "$PROJECT" \
  --region "$REGION" --format='value(results.images[0].digest)') || exit $?
[[ "$DIGEST" =~ ^sha256:[0-9a-f]{64}$ ]] || exit 2
IMAGE="${TAG%:*}@$DIGEST"

while [ ! -s "$SUPPORT/completion.txt" ]; do
  printf '%s STACK_CORE_SHELL_TREATMENT_WAITS_FOR_SUPPORT\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["disposition"])' \
  "$SUPPORT/completion.txt") || exit $?
case "$DISPOSITION" in
  p230-supported-stack-core-shell-treatment-licensed|\
  p220-supported-stack-core-shell-treatment-licensed|\
  p210-supported-stack-core-shell-treatment-licensed) ;;
  *)
    echo "STACK_CORE_SHELL_TREATMENT_CLOSED_BY_SUPPORT $DISPOSITION"
    exit 10
    ;;
esac
SUPPORT_REPORT_SHA=$(sha256sum "$SUPPORT/report.json" | awk '{print $1}')
SUPPORT_COMPLETION_SHA=$(sha256sum "$SUPPORT/completion.txt" | awk '{print $1}')

bash "$ROOT/scripts/cloud_stack_core_shell_scorefree.sh" \
  "$IMAGE" "$CODE_SHA" "$BUILD_ID" \
  "$SUPPORT_REPORT_SHA" "$SUPPORT_COMPLETION_SHA" || exit $?

while true; do
  running=0
  while read -r _season _week _job execution _uri; do
    state=$(gcloud run jobs executions describe "$execution" --project "$PROJECT" \
      --region "$REGION" --format='value(status.conditions[0].status)') || exit $?
    [ "$state" = Unknown ] && running=$((running + 1))
  done < "$OUT/executions.txt"
  printf '%s STACK_CORE_SHELL_TREATMENT_PRIMARY_STATUS running=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$running"
  [ "$running" -eq 0 ] && break
  sleep 300
done

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/manage_stack_core_shell_scorefree_attempts.py" prepare \
  --output-dir "$OUT" || exit $?
DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
  "$OUT/attempt-resolution.json") || exit $?
case "$DISPOSITION" in
  accepted-primary-population|accepted-population-with-platform-replacements) ;;
  *)
    echo "STACK_CORE_SHELL_TREATMENT_STOPS_AFTER_ATTEMPTS $DISPOSITION"
    exit 10
    ;;
esac
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/finish_stack_core_shell_scorefree.py" --output-dir "$OUT"
