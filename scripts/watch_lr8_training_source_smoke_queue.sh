#!/usr/bin/env bash
set -uo pipefail

# One-owner watcher for the LR8 real-source smoke.  It polls Cloud Run
# execution metadata only.  Result inventory/body access belongs exclusively
# to the Python finisher after strict terminal success.
#
# Recommended durable launch (chain_status.sh discovers both this process and
# its log):
#   nohup bash scripts/watch_lr8_training_source_smoke_queue.sh \
#     > "$HOME/nfl-panels/lr8-training-source-smoke.log" 2>&1 &

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
ATTEMPT_ID=20260821-lr8-training-source-smoke-v2
JOB=atlas-md-prefix-r4-smoke
OUT="$ROOT/reports/lr8-training-source-smoke-runs/$ATTEMPT_ID"
LAUNCHER="$ROOT/scripts/cloud_lr8_training_source_smoke.sh"
FINISHER="$ROOT/scripts/finish_lr8_training_source_smoke.py"
PYTHON=${NFL_DFS_PYTHON:-"$ROOT/.venv/bin/python"}

for repair_name in LR8_SMOKE_FINISHER_REPAIR_SHA256 \
  LR8_SMOKE_LAUNCHER_REPAIR_SHA256 LR8_SMOKE_WATCHER_REPAIR_SHA256; do
  repair_value=${!repair_name:-}
  [ -z "$repair_value" ] || [[ "$repair_value" =~ ^[0-9a-f]{64}$ ]] || exit 2
done

if [ -s "$OUT/finish.sha256" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" finish \
    --output-dir "$OUT" >/dev/null || exit $?
  echo "LR8_TRAINING_SOURCE_SMOKE_ALREADY_FINISHED"
  exit 0
fi
if [ -e "$OUT/failure-closure.json" ]; then
  echo "ERROR: LR8 smoke is terminal-failed-no-relaunch" >&2
  exit 10
fi

if [ ! -s "$OUT/launch.sha256" ]; then
  if [ -e "$OUT/launch-intent.json" ] || [ -e "$OUT/executions.txt" ]; then
    echo "ERROR: LR8 smoke launch is ambiguous; automatic relaunch forbidden" >&2
    exit 2
  fi
  bash "$LAUNCHER" launch || {
    if [ -e "$OUT/launch-intent.json" ]; then
      echo "ERROR: LR8 smoke launch intent exists; no relaunch" >&2
    fi
    exit 2
  }
fi

read -r LEDGER_JOB EXECUTION LEDGER_URI < "$OUT/executions.txt" || exit 2
[ "$LEDGER_JOB" = "$JOB" ] || exit 2
[[ "$EXECUTION" =~ ^${JOB}-[a-z0-9]{5}$ ]] || exit 2
[ "$LEDGER_URI" = \
  "gs://nfl-predictions-503414-raw/research/lr8-training-source/$ATTEMPT_ID/smoke-manifest.json" ] || exit 2

POLL_RAW="$OUT/.execution-poll.raw.pending"
POLL="$OUT/.execution-poll.json"
if [ -e "$POLL_RAW" ]; then
  if [ -e "$POLL" ]; then
    rm -- "$POLL_RAW"
  elif PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$POLL_RAW" --output "$POLL"; then
    rm -- "$POLL_RAW"
  else
    mv -- "$POLL_RAW" "$OUT/malformed-poll.raw.json"
    echo "ERROR: LR8 smoke retained malformed poll; no relaunch" >&2
    exit 2
  fi
fi

while true; do
  if [ ! -e "$POLL" ]; then
    if ! gcloud run jobs executions describe "$EXECUTION" \
        --project "$PROJECT" --region "$REGION" --format=json \
        > "$POLL_RAW"; then
      echo "ERROR: LR8 smoke execution poll failed; no relaunch" >&2
      exit 2
    fi
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$POLL_RAW" --output "$POLL" || {
        mv -- "$POLL_RAW" "$OUT/malformed-poll.raw.json"
        exit 2
      }
    rm -- "$POLL_RAW"
  fi
  if ! STATE=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      poll-state --output-dir "$OUT" --metadata "$POLL"); then
    mv -- "$POLL" "$OUT/malformed-execution.json"
    echo "ERROR: LR8 smoke execution metadata malformed; no result read/relaunch" >&2
    exit 2
  fi
  printf '%s LR8_TRAINING_SOURCE_SMOKE state=%s execution=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$STATE" "$EXECUTION"
  case "$STATE" in
    True)
      rm -- "$POLL"
      break
      ;;
    False)
      mv -- "$POLL" "$OUT/terminal-failure-input.json"
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        record-failure --output-dir "$OUT" \
        --metadata "$OUT/terminal-failure-input.json" || exit $?
      echo "ERROR: LR8 smoke terminal failure; no result body read/relaunch" >&2
      exit 10
      ;;
    Unknown)
      rm -- "$POLL"
      sleep 30
      ;;
    *)
      mv -- "$POLL" "$OUT/malformed-execution.json"
      echo "ERROR: LR8 smoke state differs; no result read/relaunch" >&2
      exit 2
      ;;
  esac
done

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" finish \
  --output-dir "$OUT" >/dev/null || {
    echo "ERROR: LR8 strict terminal harvest failed; no relaunch" >&2
    exit 2
  }
echo "LR8_TRAINING_SOURCE_SMOKE_FINISHED execution=$EXECUTION"
