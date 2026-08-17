#!/usr/bin/env bash
set -uo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
SCOREFREE="$ROOT/reports/stack-core-shell-runs/20260816-stack-core-shell-scorefree-v1"
RUN_ID=20260816-stack-core-shell-production-lock-v1
OUT="$ROOT/reports/stack-core-shell-lock-runs/$RUN_ID"

while [ ! -s "$SCOREFREE/completion.txt" ]; do
  printf '%s STACK_CORE_SHELL_LOCK_WAITS_FOR_SCOREFREE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["disposition"])' \
  "$SCOREFREE/completion.txt") || exit $?
LICENSE=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["historical_scoring_licensed"])' \
  "$SCOREFREE/completion.txt") || exit $?
if [ "$DISPOSITION" != stack-core-shell-shadow-licensed ] || \
    [ "$LICENSE" != true ]; then
  echo "STACK_CORE_SHELL_LOCK_CLOSED_BY_SCOREFREE $DISPOSITION"
  exit 10
fi

IMAGE=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["image"])' \
  "$SCOREFREE/manifest.txt") || exit $?
CODE_SHA=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["code_sha"])' \
  "$SCOREFREE/manifest.txt") || exit $?
BUILD_ID=$("$ROOT/.venv/bin/python" -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["build_id"])' \
  "$SCOREFREE/manifest.txt") || exit $?
SCOREFREE_REPORT_SHA=$(sha256sum "$SCOREFREE/report.json" | awk '{print $1}')
SCOREFREE_COMPLETION_SHA=$(sha256sum "$SCOREFREE/completion.txt" | awk '{print $1}')

bash "$ROOT/scripts/cloud_stack_core_shell_production_locks.sh" \
  "$IMAGE" "$CODE_SHA" "$BUILD_ID" \
  "$SCOREFREE_REPORT_SHA" "$SCOREFREE_COMPLETION_SHA" || exit $?

while true; do
  running=0
  while read -r _season _week _job execution _uri; do
    state=$(gcloud run jobs executions describe "$execution" --project "$PROJECT" \
      --region "$REGION" --format='value(status.conditions[0].status)') || exit $?
    [ "$state" = Unknown ] && running=$((running + 1))
  done < "$OUT/executions.txt"
  printf '%s STACK_CORE_SHELL_LOCK_PRIMARY_STATUS running=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$running"
  [ "$running" -eq 0 ] && break
  sleep 300
done

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/manage_stack_core_shell_lock_attempts.py" prepare \
  --output-dir "$OUT" || exit $?
DISPOSITION=$("$ROOT/.venv/bin/python" -c \
  'import json,sys; print(json.load(open(sys.argv[1]))["disposition"])' \
  "$OUT/attempt-resolution.json") || exit $?
case "$DISPOSITION" in
  accepted-primary-population|accepted-population-with-platform-replacements) ;;
  *)
    echo "STACK_CORE_SHELL_LOCK_STOPS_AFTER_ATTEMPTS $DISPOSITION"
    exit 10
    ;;
esac
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
  "$ROOT/scripts/finish_stack_core_shell_production_locks.py" \
  --output-dir "$OUT"
