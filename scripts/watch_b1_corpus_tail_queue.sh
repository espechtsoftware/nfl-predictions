#!/usr/bin/env bash
set -uo pipefail

# Serial, restart-safe owner of the one frozen B1 historical execution.
# Metadata is polled without opening result bodies.  The Python finisher alone
# inventories and generation-opens results after strict terminal success.
#
# Usage: watch_b1_corpus_tail_queue.sh IMAGE CODE_SHA BUILD_ID

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
RUN_ID=20260820-b1-corpus-tail-model-v1
JOB=atlas-minimal-c-s2023-w1-v1
OUT="$ROOT/reports/b1-corpus-tail-runs/$RUN_ID"
LAUNCHER="$ROOT/scripts/cloud_b1_corpus_tail_model.sh"
FINISHER="$ROOT/scripts/finish_b1_corpus_tail_model.py"
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
  echo "B1_CORPUS_TAIL_ALREADY_FINISHED_AND_LEASE_CLOSED"
  exit 0
fi

# B1 may not update the shared reused job or compete for the outcome lease
# until A2a has durably closed its exact generation and that closure is in the
# source commit which will be built.
while true; do
  if PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      validate-a2a-terminal --code-sha "$CODE_SHA" >/dev/null 2>&1; then
    break
  fi
  printf '%s B1_CORPUS_TAIL_WAITS_FOR_PUSHED_A2A_TERMINAL\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 60
done

if [ ! -s "$OUT/prepared.sha256" ]; then
  bash "$LAUNCHER" prepare "$IMAGE" "$CODE_SHA" "$BUILD_ID" || exit $?
fi
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
  validate-prepared --output-dir "$OUT" --code-sha "$CODE_SHA" \
  --image "$IMAGE" --build-id "$BUILD_ID" || exit $?

# Preparation deliberately pauses at the human-auditable boundary.  Launch
# cannot proceed until the exact generated manifest and A2a terminal closure
# are both byte-identical on origin/main.
while true; do
  git -C "$ROOT" fetch --quiet origin main >/dev/null 2>&1 || true
  if PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      verify-pushed-manifest --output-dir "$OUT" --remote-ref origin/main \
      >/dev/null 2>&1; then
    break
  fi
  printf '%s B1_CORPUS_TAIL_WAITS_FOR_PUSHED_MANIFEST\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 60
done

if [ -e "$OUT/failed-execution.json" ] || \
    [ -e "$OUT/failure-closure.sha256" ]; then
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    close-failed-execution --output-dir "$OUT" || {
      echo "ERROR: B1 terminal-failure closure could not resume" >&2
      exit 2
    }
  echo "ERROR: B1 execution is durably closed terminal-failed-no-retry" >&2
  exit 10
fi

LEASE="$OUT/lease-receipt.json"
while true; do
  if [ -e "$LEASE" ]; then
    if PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        recover-lease --manifest "$OUT/manifest.json" --receipt "$LEASE" \
        >/dev/null 2>&1; then
      echo "B1_CORPUS_TAIL_VALIDATED_OR_RECOVERED_OWN_LIVE_LEASE"
      break
    fi
    echo "ERROR: B1 local/live lease state differs; launch forbidden" >&2
    exit 2
  fi
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$LEASE_TOOL" acquire \
    --run-id "$RUN_ID" --job "$JOB" --code-sha "$CODE_SHA" --image "$IMAGE" \
    --receipt "$LEASE"
  RC=$?
  if [ "$RC" -eq 0 ]; then
    break
  fi
  if PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      recover-lease --manifest "$OUT/manifest.json" --receipt "$LEASE" \
      >/dev/null 2>&1; then
    echo "B1_CORPUS_TAIL_RESUMED_OWN_LIVE_LEASE"
    break
  fi
  printf '%s B1_CORPUS_TAIL_WAITS_FOR_HISTORICAL_OUTCOME_LEASE\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  sleep 60
done

if [ ! -s "$OUT/executions.txt" ]; then
  if [ -e "$OUT/launch-intent.json" ]; then
    echo "ERROR: B1 launch is ambiguous; no retry and lease remains held for forensic recovery" >&2
    exit 2
  fi
  bash "$LAUNCHER" launch
  RC=$?
  if [ "$RC" -ne 0 ]; then
    if [ -e "$OUT/launch-intent.json" ]; then
      echo "ERROR: B1 launch is ambiguous; no retry and lease remains held" >&2
    else
      PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$LEASE_TOOL" abandon \
        --receipt "$LEASE" --reason b1-corpus-tail-prelaunch-failed \
        --preserve-dir "$OUT/failed-prelaunch" || exit $?
      echo "ERROR: B1 prelaunch failed; own lease safely abandoned" >&2
    fi
    exit "$RC"
  fi
fi

read -r LEDGER_JOB EXECUTION ATTEMPT_URI REPORT_URI MODEL_URI INTENT_GENERATION \
  < "$OUT/executions.txt" || exit 2
[ "$LEDGER_JOB" = "$JOB" ] && [[ "$EXECUTION" == "$JOB-"* ]] && \
  [[ "$INTENT_GENERATION" =~ ^[1-9][0-9]*$ ]] || exit 2

POLL_RAW="$OUT/.execution-poll.raw.json"
POLL="$OUT/.execution-poll.json"
if [ -e "$POLL_RAW" ]; then
  if [ -e "$POLL" ]; then
    rm -- "$POLL_RAW"
  elif PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$POLL_RAW" --output "$POLL"; then
    rm -- "$POLL_RAW"
  else
    rm -- "$POLL_RAW"
  fi
fi

while true; do
  if [ ! -e "$POLL" ]; then
    if ! gcloud run jobs executions describe "$EXECUTION" --project "$PROJECT" \
        --region "$REGION" --format=json > "$POLL_RAW"; then
      echo "ERROR: B1 execution poll failed; lease held" >&2
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
  printf '%s B1_CORPUS_TAIL_OUTCOME state=%s execution=%s\n' \
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
          echo "ERROR: B1 terminal-failure closure incomplete; lease held" >&2
          exit 2
        }
      echo "ERROR: B1 execution failed terminally; durable no-retry closure complete" >&2
      exit 10
      ;;
    Unknown)
      rm -- "$POLL"
      sleep 60
      ;;
    *)
      mv "$POLL" "$OUT/malformed-execution.json"
      echo "ERROR: B1 execution metadata malformed; lease held" >&2
      exit 2
      ;;
  esac
done

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" finish \
  --output-dir "$OUT" || {
    echo "ERROR: B1 strict harvest failed; lease held" >&2
    exit 2
  }
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" close-lease \
  --output-dir "$OUT" || {
    echo "ERROR: B1 release-intent close incomplete; rerun watcher to resume" >&2
    exit 2
  }
echo "B1_CORPUS_TAIL_FINISHED_AND_LEASE_CLOSED $EXECUTION $REPORT_URI"
