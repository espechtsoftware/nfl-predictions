#!/usr/bin/env bash
set -uo pipefail

# Serial, restart-safe owner of the one frozen A2a historical execution.
# It polls metadata only.  The Python finisher alone may inventory/open the
# result, and lease closure occurs only after strict harvest.
#
# Usage: watch_a2a_production_law_dependence_queue.sh IMAGE CODE_SHA BUILD_ID

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260820-a2a-production-law-dependence-remeasurement-v1
JOB=atlas-minimal-c-s2023-w1-v1
OUT="$ROOT/reports/a2a-production-law-dependence-runs/$RUN_ID"
RESULT_URI="gs://nfl-predictions-503414-raw/research/a2a-production-law-dependence-runs/$RUN_ID/report.json"
LAUNCHER="$ROOT/scripts/cloud_a2a_production_law_dependence_remeasurement.sh"
FINISHER="$ROOT/scripts/finish_a2a_production_law_dependence_remeasurement.py"
LEASE_TOOL="$ROOT/scripts/historical_outcome_lease.py"
PYTHON="$ROOT/.venv/bin/python"
IMAGE=${1:-}
CODE_SHA=${2:-}
BUILD_ID=${3:-}

[[ "$IMAGE" =~ ^us-central1-docker\.pkg\.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:[0-9a-f]{64}$ ]] || exit 2
[[ "$CODE_SHA" =~ ^[0-9a-f]{40}$ ]] || exit 2
[[ "$BUILD_ID" =~ ^[0-9A-Za-z-]{8,80}$ ]] || exit 2

if [ -s "$OUT/finish.sha256" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    close-lease --output-dir "$OUT" || exit $?
  echo "A2A_REMEASUREMENT_ALREADY_FINISHED_AND_LEASE_CLOSED"
  exit 0
fi

if [ ! -s "$OUT/prepared.sha256" ]; then
  bash "$LAUNCHER" prepare "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?
fi
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
  validate-prepared --output-dir "$OUT" --code-sha "$CODE_SHA" \
  --image "$IMAGE" --build-id "$BUILD_ID" || exit $?

# Preparation deliberately stops short of the lease.  The exact generated
# manifest must be reviewed, committed, and pushed before this loop advances.
while true; do
  git -C "$ROOT" fetch --quiet origin main >/dev/null 2>&1 || true
  if PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      verify-pushed-manifest --output-dir "$OUT" --remote-ref origin/main \
      >/dev/null 2>&1; then
    break
  fi
  printf '%s A2A_REMEASUREMENT_WAITS_FOR_PUSHED_MANIFEST\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 60
done

if [ -e "$OUT/failed-execution.json" ] || \
    [ -e "$OUT/failure-closure.sha256" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    close-failed-execution --output-dir "$OUT" || {
      echo "ERROR: A2a terminal-failure closure could not resume" >&2
      exit 2
    }
  echo "ERROR: A2a execution is durably closed terminal-failed-no-retry" >&2
  exit 10
fi

LEASE="$OUT/lease-receipt.json"
while true; do
  if [ -e "$LEASE" ]; then
    # This also reconstructs a non-empty truncated receipt, but only after the
    # exact live run/job/code/image lease body has been generation-read.
    if PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        recover-lease --manifest "$OUT/manifest.json" --receipt "$LEASE" \
        >/dev/null 2>&1; then
      echo "A2A_REMEASUREMENT_VALIDATED_OR_RECOVERED_OWN_LIVE_LEASE"
      break
    fi
    echo "ERROR: A2a local/live lease state differs; launch forbidden" >&2
    exit 2
  fi
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$LEASE_TOOL" acquire \
    --run-id "$RUN_ID" --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" \
    --receipt "$LEASE"
  RC=$?
  if [ "$RC" -eq 0 ]; then
    break
  fi
  # Crash after the remote create but before local receipt publication is
  # recoverable only for this exact run/job/code/image identity.
  if PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      recover-lease --manifest "$OUT/manifest.json" --receipt "$LEASE" \
      >/dev/null 2>&1; then
    echo "A2A_REMEASUREMENT_RESUMED_OWN_LIVE_LEASE"
    break
  fi
  printf '%s A2A_REMEASUREMENT_WAITS_FOR_HISTORICAL_OUTCOME_LEASE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 60
done

if [ ! -s "$OUT/executions.txt" ]; then
  if [ -e "$OUT/launch-intent.json" ]; then
    echo "ERROR: A2a launch is ambiguous; lease held, relaunch forbidden" >&2
    exit 2
  fi
  bash "$LAUNCHER" launch
  RC=$?
  if [ "$RC" -ne 0 ]; then
    if [ -e "$OUT/launch-intent.json" ]; then
      echo "ERROR: A2a launch is ambiguous; lease held, relaunch forbidden" >&2
    else
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$LEASE_TOOL" abandon \
        --receipt "$LEASE" --reason a2a-remeasurement-prelaunch-failed \
        --preserve-dir "$OUT/failed-prelaunch" || exit $?
      echo "ERROR: A2a prelaunch failed; own lease safely abandoned" >&2
    fi
    exit "$RC"
  fi
fi

read -r LEDGER_JOB EXECUTION LEDGER_URI < "$OUT/executions.txt" || exit 2
[ "$LEDGER_JOB" = "$JOB" ] && [[ "$EXECUTION" == "$JOB-"* ]] && \
  [ "$LEDGER_URI" = "$RESULT_URI" ] || exit 2

POLL_RAW="$OUT/.execution-poll.raw.json"
POLL="$OUT/.execution-poll.json"
if [ -e "$POLL_RAW" ]; then
  if [ -e "$POLL" ]; then
    rm -- "$POLL_RAW"
  elif PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$POLL_RAW" --output "$POLL"; then
    rm -- "$POLL_RAW"
  else
    # A process may have stopped midway through the metadata-only write.
    # That transient file carries no unique evidence; repoll the same execution.
    rm -- "$POLL_RAW"
  fi
fi

while true; do
  if [ ! -e "$POLL" ]; then
    if ! gcloud run jobs executions describe "$EXECUTION" --project "$PROJECT" \
        --region "$REGION" --format=json > "$POLL_RAW"; then
      echo "ERROR: A2a execution poll failed; lease held" >&2
      exit 2
    fi
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$POLL_RAW" --output "$POLL" || exit $?
    rm -- "$POLL_RAW"
  fi
  STATE=$("$PYTHON" - "$POLL" <<'PY'
import json
import sys

value = json.load(open(sys.argv[1], encoding="utf-8"))
rows = [
    row for row in value.get("status", {}).get("conditions", [])
    if row.get("type") == "Completed"
]
if not rows:
    print("Unknown")
elif len(rows) == 1 and rows[0].get("status") in {"Unknown", "True", "False"}:
    print(rows[0]["status"])
else:
    print("Malformed")
PY
  ) || exit $?
  printf '%s A2A_REMEASUREMENT_OUTCOME state=%s execution=%s\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$STATE" "$EXECUTION"
  case "$STATE" in
    True)
      rm -- "$POLL"
      break
      ;;
    False)
      [ ! -e "$OUT/failed-execution.json" ] || exit 2
      mv "$POLL" "$OUT/failed-execution.json"
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        close-failed-execution --output-dir "$OUT" || {
          echo "ERROR: A2a terminal-failure closure incomplete; lease held" >&2
          exit 2
        }
      echo "ERROR: A2a execution failed terminally; durable no-retry closure complete" >&2
      exit 10
      ;;
    Unknown)
      rm -- "$POLL"
      sleep 60
      ;;
    *)
      mv "$POLL" "$OUT/malformed-execution.json"
      echo "ERROR: A2a execution metadata malformed; lease held" >&2
      exit 2
      ;;
  esac
done

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" finish \
  --output-dir "$OUT" || {
    echo "ERROR: A2a strict harvest failed; lease held" >&2
    exit 2
  }
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" close-lease \
  --output-dir "$OUT" || {
    echo "ERROR: A2a release-intent close incomplete; rerun watcher to resume" >&2
    exit 2
  }
echo "A2A_REMEASUREMENT_FINISHED_AND_LEASE_CLOSED $EXECUTION $LEDGER_URI"
