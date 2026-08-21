#!/usr/bin/env bash
set -euo pipefail

# Sole watcher.  Polling reads only Cloud Run execution metadata.  Result
# inventory/bodies are opened only after a strict terminal-success receipt.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
FINISHER="$ROOT/scripts/finish_lr8_historical_score_transport.py"
LEASE_TOOL="$ROOT/scripts/historical_outcome_lease.py"
PYTHON=${NFL_DFS_PYTHON:-"$ROOT/.venv/bin/python"}
MODE=${1:-}

mapfile -t MODE_VALUES < <(
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    mode-values --mode "$MODE"
) || exit 2
[ "${#MODE_VALUES[@]}" -eq 4 ] || exit 2
RUN_ID=${MODE_VALUES[0]}
OUT=${MODE_VALUES[2]}
LEASE="$OUT/historical-outcome-lease.json"

[ -s "$OUT/contract.json" ] || exit 2
if [ -s "$OUT/queue-completion.txt" ] && [ -s "$OUT/queue-completion.sha256" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    validate-queue-completion --mode "$MODE" --output-dir "$OUT" || exit 2
  echo "LR8_HISTORICAL_SCORE_ALREADY_COMPLETE mode=$MODE"
  exit 0
fi
if [ -s "$OUT/failure.json" ] && [ -s "$OUT/completion.txt" ] && \
    [ ! -e "$LEASE" ]; then
  echo "LR8_HISTORICAL_SCORE_ALREADY_CLOSED mode=$MODE no_retry=true"
  exit 10
fi
if [ ! -s "$OUT/execution.txt" ]; then
  bash "$ROOT/scripts/cloud_lr8_historical_score_transport.sh" launch "$MODE" || exit $?
fi
mapfile -t LEDGER < <(
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    ledger-values --mode "$MODE" --ledger "$OUT/execution.txt"
) || exit 2
[ "${#LEDGER[@]}" -eq 3 ] || exit 2
EXECUTION=${LEDGER[1]}

if [ -s "$OUT/execution-terminal.json" ]; then
  STATE=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    poll-state --metadata "$OUT/execution-terminal.json") || exit 2
  case "$STATE" in True|False) ;; *) exit 2 ;; esac
else
  while true; do
    RAW="$OUT/.execution-poll.raw.pending"
    POLL="$OUT/.execution-poll.json.pending"
    rm -f -- "$RAW" "$POLL"
    gcloud run jobs executions describe "$EXECUTION" --project "$PROJECT" \
      --region "$REGION" --format=json > "$RAW" || exit 2
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$RAW" --output "$POLL" || exit 2
    rm -- "$RAW"
    STATE=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      poll-state --metadata "$POLL") || exit 2
    printf '%s LR8_HISTORICAL_SCORE mode=%s execution=%s state=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$MODE" "$EXECUTION" "$STATE"
    case "$STATE" in
      Unknown) rm -- "$POLL"; sleep 30 ;;
      True|False) mv -- "$POLL" "$OUT/execution-terminal.json"; break ;;
      *) exit 2 ;;
    esac
  done
fi

if [ "$STATE" = "False" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    close-failure --mode "$MODE" --output-dir "$OUT" --state False \
    --disposition terminal-failed-no-retry || exit $?
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$LEASE_TOOL" abandon \
    --receipt "$LEASE" --reason terminal-failed-no-retry \
    --preserve-dir "$OUT/failed-execution" || exit $?
  echo "LR8_HISTORICAL_SCORE_CLOSED_FAILED mode=$MODE no_retry=true"
  exit 10
fi

if ! PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    finish-success --mode "$MODE" --output-dir "$OUT"; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    close-failure --mode "$MODE" --output-dir "$OUT" --state True \
    --disposition harvest-validation-failed || exit $?
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$LEASE_TOOL" abandon \
    --receipt "$LEASE" --reason harvest-validation-failed \
    --preserve-dir "$OUT/failed-harvest" || exit $?
  echo "LR8_HISTORICAL_SCORE_CLOSED_INVALID mode=$MODE no_retry=true" >&2
  exit 11
fi
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
  release-success --mode "$MODE" --output-dir "$OUT" || exit $?
echo "LR8_HISTORICAL_SCORE_COMPLETE mode=$MODE lease_released=true"
