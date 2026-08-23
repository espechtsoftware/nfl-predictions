#!/usr/bin/env bash
# Run the v6 task-0 independent acceptance gate from driver receipts.
# Requires foundry_v6_env.sh sourced (CORPUS_PARAMETRIC_RUN_DIR,
# CORPUS_PARAMETRIC_PYTHON, PYTHONPATH). Reads the carrier identity from
# tasks/000-producer-closed.json (.task_result) and the verifier receipt
# from tasks/000-verifier-accepted.json — nothing is retyped. Writes
# task0-acceptance-receipt.json always and task0-acceptance-pass.json
# only on PASS (the driver's fan-out gate file).

set -euo pipefail

RUN_DIR="${CORPUS_PARAMETRIC_RUN_DIR:?source foundry_v6_env.sh first}"
PYTHON_BIN="${CORPUS_PARAMETRIC_PYTHON:?source foundry_v6_env.sh first}"
# The gate script itself is operator tooling tracked on main; the law
# modules it imports resolve through PYTHONPATH, which the env file pins
# to the frozen bcf31a7 worktree src.
GATE_SCRIPT="/home/erich/projects/nfl-predictions/scripts/foundry/accept_foundry_task0.py"

CLOSED="$RUN_DIR/tasks/000-producer-closed.json"
ACCEPTED="$RUN_DIR/tasks/000-verifier-accepted.json"
[[ -f "$CLOSED" ]] || { echo "absent: $CLOSED" >&2; exit 2; }
[[ -f "$ACCEPTED" ]] || { echo "absent: $ACCEPTED" >&2; exit 2; }

carrier_field() {
  jq -er ".task_result.$1" "$CLOSED"
}

PYTHONPATH=/home/erich/projects/nfl-predictions/src exec "$PYTHON_BIN" "$GATE_SCRIPT" \
  --carrier-uri "$(carrier_field uri)" \
  --carrier-generation "$(carrier_field generation)" \
  --carrier-sha256 "$(carrier_field sha256)" \
  --carrier-bytes "$(carrier_field bytes)" \
  --verifier-accepted-receipt "$ACCEPTED" \
  --receipt-output "$RUN_DIR/task0-acceptance-receipt.json" \
  --pass-gate-output "$RUN_DIR/task0-acceptance-pass.json"
