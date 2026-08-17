#!/usr/bin/env bash
set -uo pipefail

# Operational wrapper: acquire the shared outcome lease only after immutable
# stack-core/shell production locks license historical scoring.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
LOCK="$ROOT/reports/stack-core-shell-lock-runs/20260816-stack-core-shell-production-lock-v1"
OUT="$ROOT/reports/stack-core-shell-historical-runs/20260816-stack-core-shell-historical-score-v1"
LEASE_DIR="$ROOT/reports/historical-outcome-leases"
LEASE="$LEASE_DIR/20260816-stack-core-shell-historical-score-v1.json"

while [ ! -s "$LOCK/completion.txt" ]; do
  printf '%s STACK_HISTORICAL_SERIALIZER_WAITS_FOR_LOCKS\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
LICENSE=$($ROOT/.venv/bin/python -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["historical_scoring_licensed"])' \
  "$LOCK/completion.txt") || exit $?
if [ "$LICENSE" != true ]; then
  bash "$ROOT/scripts/watch_stack_core_shell_historical_score_queue.sh"
  exit $?
fi
IMAGE=$($ROOT/.venv/bin/python -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["image"])' \
  "$LOCK/manifest.txt") || exit $?
CODE_SHA=$($ROOT/.venv/bin/python -c \
  'import sys; print(dict(line.split("=",1) for line in open(sys.argv[1]) if "=" in line)["code_sha"])' \
  "$LOCK/manifest.txt") || exit $?
mkdir -p "$LEASE_DIR"
while true; do
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/historical_outcome_lease.py" acquire \
    --run-id 20260816-stack-core-shell-historical-score-v1 \
    --job stack-shell-historical-score-v1 --code-sha "$CODE_SHA" --image "$IMAGE" \
    --receipt "$LEASE" && break
  [ ! -e "$LEASE" ] || exit 2
  printf '%s STACK_HISTORICAL_SERIALIZER_WAITS_FOR_LEASE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 300
done
bash "$ROOT/scripts/watch_stack_core_shell_historical_score_queue.sh"
RC=$?
if [ "$RC" -eq 0 ] && [ -s "$OUT/execution.json" ] && \
    [ -s "$OUT/completion.txt" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$ROOT/.venv/bin/python" \
    "$ROOT/scripts/historical_outcome_lease.py" release \
    --receipt "$LEASE" --execution "$OUT/execution.json" \
    --completion "$OUT/completion.txt" || exit $?
fi
exit "$RC"
