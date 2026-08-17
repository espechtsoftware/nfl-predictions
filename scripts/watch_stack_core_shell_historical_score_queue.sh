#!/usr/bin/env bash
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
LOCK="$ROOT/reports/stack-core-shell-lock-runs/20260816-stack-core-shell-production-lock-v1"
RUN_ID=20260816-stack-core-shell-historical-score-v1
OUT="$ROOT/reports/stack-core-shell-historical-runs/$RUN_ID"

while [ ! -s "$LOCK/completion.txt" ]; do
  printf '%s STACK_CORE_SHELL_HISTORICAL_WAITS_FOR_LOCKS\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
LICENSE=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["historical_scoring_licensed"])' \
  "$LOCK/completion.txt") || exit $?
if [ "$LICENSE" != true ]; then
  echo "STACK_CORE_SHELL_HISTORICAL_CLOSED_BY_LOCKS"
  exit 10
fi

IMAGE=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["image"])' \
  "$LOCK/manifest.txt") || exit $?
CODE_SHA=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["code_sha"])' \
  "$LOCK/manifest.txt") || exit $?
BUILD_ID=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["build_id"])' \
  "$LOCK/manifest.txt") || exit $?
LOCK_REPORT_SHA=$(sha256sum "$LOCK/report.json" | awk '{print $1}')
LOCK_COMPLETION_SHA=$(sha256sum "$LOCK/completion.txt" | awk '{print $1}')

bash "$ROOT/scripts/cloud_stack_core_shell_historical_score.sh" \
  "$IMAGE" "$CODE_SHA" "$BUILD_ID" \
  "$LOCK_REPORT_SHA" "$LOCK_COMPLETION_SHA" || exit $?

read -r _job execution _uri < "$OUT/executions.txt"
while true; do
  state=$(gcloud run jobs executions describe "$execution" --project "$PROJECT" \
    --region "$REGION" --format='value(status.conditions[0].status)') || exit $?
  printf '%s STACK_CORE_SHELL_HISTORICAL_PRIMARY state=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$state"
  [ "$state" != Unknown ] && break
  sleep 300
done

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/manage_stack_core_shell_historical_score_attempt.py" prepare \
  --output-dir "$OUT" || exit $?
DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
  "$OUT/attempt-resolution.json") || exit $?
case "$DISPOSITION" in
  accepted-primary|accepted-platform-replacement) ;;
  *)
    echo "STACK_CORE_SHELL_HISTORICAL_STOPS_AFTER_ATTEMPTS $DISPOSITION"
    exit 10
    ;;
esac
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/finish_stack_core_shell_historical_score.py" \
  --output-dir "$OUT"
