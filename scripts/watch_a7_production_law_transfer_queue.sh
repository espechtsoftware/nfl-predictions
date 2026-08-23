#!/usr/bin/env bash
set -euo pipefail

# Serial restart-safe owner of smoke -> support -> freeze -> full.
# Polls execution metadata only. Result inventory/body reads occur exclusively
# in the Python finisher after exact strict terminal success.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260821-a7-production-law-scorefree-selector-transfer-v1
JOB=atlas-minimal-c-s2023-w1-v1
OUT="$ROOT/reports/a7-production-law-selector-transfer-runs/$RUN_ID"
LAUNCHER="$ROOT/scripts/cloud_a7_production_law_transfer.sh"
FINISHER="$ROOT/scripts/finish_a7_production_law_transfer.py"
RUNNER="$ROOT/scripts/run_a7_production_law_transfer.py"
PYTHON="$ROOT/.venv/bin/python"

gate_predecessor() {
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$RUNNER" \
    validate-predecessor >/dev/null
}

canonicalize_poll() {
  local raw=$1
  local target=$2
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    canonicalize-external-json --raw "$raw" --output "$target"
}

phase_state() {
  local path=$1
  "$PYTHON" - "$path" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
rows = [
    row for row in value.get("status", {}).get("conditions", [])
    if isinstance(row, dict) and row.get("type") == "Completed"
]
if not rows:
    print("Unknown")
elif len(rows) == 1 and rows[0].get("status") in {"Unknown", "True", "False"}:
    print(rows[0]["status"])
else:
    print("Malformed")
PY
}

run_phase() {
  local phase=$1
  local phase_out="$OUT/$phase"
  local terminal="$phase_out/terminal-receipt.json"
  local failure="$phase_out/terminal-failure.json"
  local ledger="$phase_out/executions.txt"
  local poll_raw="$phase_out/.execution-poll.raw.json"
  local poll="$phase_out/.execution-poll.json"
  local terminal_metadata="$phase_out/terminal-execution.json"
  local failed_metadata="$phase_out/failed-execution.json"

  if [ -s "$terminal" ]; then
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-phase-complete --phase "$phase" --output-dir "$OUT" >/dev/null
    return 0
  fi
  [ ! -e "$failure" ] || {
    echo "ERROR: $phase is durably terminal-failed-no-retry" >&2
    return 10
  }
  if [ -s "$terminal_metadata" ]; then
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" harvest \
      --phase "$phase" --output-dir "$OUT" \
      --execution "$terminal_metadata" >/dev/null
    return 0
  fi
  if [ -s "$failed_metadata" ]; then
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      close-terminal-failure --phase "$phase" --output-dir "$OUT" \
      --execution "$failed_metadata" >/dev/null
    echo "ERROR: $phase closed terminal-failed-no-retry" >&2
    return 10
  fi
  if [ ! -s "$ledger" ]; then
    bash "$LAUNCHER" launch "$phase"
  fi
  read -r ledger_job execution < "$ledger" || return 2
  [ "$ledger_job" = "$JOB" ] && [[ "$execution" == "$JOB-"* ]] || return 2

  if [ -e "$poll_raw" ]; then
    if [ -e "$poll" ]; then
      rm -- "$poll_raw"
    elif canonicalize_poll "$poll_raw" "$poll"; then
      rm -- "$poll_raw"
    else
      echo "ERROR: retained $phase poll is malformed; no relaunch" >&2
      return 2
    fi
  fi
  while true; do
    if [ ! -e "$poll" ]; then
      # Exact-positive validation always precedes this cloud metadata read.
      gate_predecessor || return 2
      if ! gcloud run jobs executions describe "$execution" \
          --project "$PROJECT" --region "$REGION" --format=json > "$poll_raw"; then
        echo "ERROR: $phase execution poll failed; no relaunch" >&2
        return 2
      fi
      canonicalize_poll "$poll_raw" "$poll" || return 2
      rm -- "$poll_raw"
    fi
    state=$(phase_state "$poll") || return 2
    printf '%s A7_TRANSFER phase=%s state=%s execution=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$phase" "$state" "$execution"
    case "$state" in
      True)
        [ ! -e "$terminal_metadata" ] || return 2
        mv "$poll" "$terminal_metadata"
        PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" harvest \
          --phase "$phase" --output-dir "$OUT" \
          --execution "$terminal_metadata" >/dev/null || return 2
        return 0
        ;;
      False)
        [ ! -e "$failed_metadata" ] || return 2
        mv "$poll" "$failed_metadata"
        PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
          close-terminal-failure --phase "$phase" --output-dir "$OUT" \
          --execution "$failed_metadata" >/dev/null || return 2
        echo "ERROR: $phase closed terminal-failed-no-retry" >&2
        return 10
        ;;
      Unknown)
        rm -- "$poll"
        sleep 60
        ;;
      *)
        malformed="$phase_out/malformed-execution.json"
        [ ! -e "$malformed" ] || return 2
        mv "$poll" "$malformed"
        echo "ERROR: $phase execution metadata is ambiguous; no relaunch" >&2
        return 2
        ;;
    esac
  done
}

gate_predecessor
[ -s "$OUT/deployment-receipt.json" ] || {
  echo "ERROR: prepare must complete before watcher start" >&2
  exit 2
}

run_phase smoke
run_phase support
SUPPORT_PASSED=$($PYTHON - "$OUT/support/terminal-receipt.json" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
print("true" if value["terminal"]["decision"]["support_passed"] is True else "false")
PY
) || exit 2
if [ "$SUPPORT_PASSED" != true ]; then
  echo "A7_TRANSFER_CLOSED_UNSUPPORTED shadow=false production=false"
  exit 0
fi
[ -s "$OUT/freeze-receipt.json" ] || bash "$LAUNCHER" freeze
run_phase full

DISPOSITION=$($PYTHON - "$OUT/full/terminal-receipt.json" <<'PY'
import json
import sys
value = json.load(open(sys.argv[1], encoding="utf-8"))
print(value["terminal"]["decision"]["disposition"])
PY
) || exit 2
echo "A7_TRANSFER_COMPLETE disposition=$DISPOSITION shadow_deployed=false production_mutated=false"
