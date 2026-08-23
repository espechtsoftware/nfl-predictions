#!/usr/bin/env bash
set -uo pipefail

# One-owner continuation watcher for LR8 later-period source construction.
# It polls Cloud Run metadata only.  The Python finisher performs every GCS
# inventory/body read, and only after strict terminal success: source first,
# then the 2023-W1 smoke, all 54 cells, and finally the 108-book aggregate.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=atlas-md-prefix-r4-smoke
ATTEMPT_ID=20260821-lr8-later-period-source-v1
OUT="$ROOT/reports/lr8-later-period-source-runs/$ATTEMPT_ID"
LAUNCHER="$ROOT/scripts/cloud_lr8_later_period_source.sh"
FINISHER="$ROOT/scripts/finish_lr8_later_period_source_transport.py"
PYTHON=${NFL_DFS_PYTHON:-"$ROOT/.venv/bin/python"}

die() {
  echo "ERROR: $*" >&2
  exit 2
}

[ "${1:-}" = "--execute" ] || die "literal --execute is required"
[ "${LR8_LATER_PERIOD_TRANSPORT_ENABLED:-}" = "1" ] || \
  die "LR8_LATER_PERIOD_TRANSPORT_ENABLED=1 is required"
[ -s "$OUT/contract.json" ] || die "later-period transport is not prepared"

stage_uri() {
  local stage=$1 index=${2:-}
  local -a index_args=()
  if [ "$stage" = "cell" ]; then
    index_args=(--cell-index "$index")
  fi
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    output-uri --stage "$stage" "${index_args[@]}"
}

stage_paths() {
  local stage=$1 index=${2:-}
  if [ "$stage" = "cell" ]; then
    INTENT_PATH=$(printf '%s/cell-launch-intents/cell-%02d.json' "$OUT" "$index")
    LEDGER_PATH=$(printf '%s/cell-execution-ledgers/cell-%02d.txt' "$OUT" "$index")
  else
    INTENT_PATH="$OUT/$stage-launch-intent.json"
    LEDGER_PATH="$OUT/$stage-execution.txt"
  fi
}

ensure_launched() {
  local stage=$1
  stage_paths "$stage"
  if [ ! -e "$INTENT_PATH" ] && [ ! -e "$LEDGER_PATH" ]; then
    bash "$LAUNCHER" "launch-$stage" --execute || exit $?
  fi
  [ -s "$INTENT_PATH" ] && [ -s "$LEDGER_PATH" ] || \
    die "$stage launch is ambiguous; no relaunch"
}

ledger_execution() {
  local ledger=$1 uri=$2
  mapfile -t LEDGER_FIELDS < <(
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      ledger-fields --ledger "$ledger" --expected-uri "$uri"
  ) || die "execution ledger validation failed"
  [ "${#LEDGER_FIELDS[@]}" -eq 3 ] && \
    [ "${LEDGER_FIELDS[0]}" = "$JOB" ] || die "execution ledger differs"
  LEDGER_EXECUTION=${LEDGER_FIELDS[1]}
}

poll_execution() {
  local execution=$1 target=$2
  local raw="$target.raw.pending"
  if [ ! -e "$target" ]; then
    [ ! -e "$raw" ] || die "execution poll raw response already exists: $raw"
    if ! gcloud run jobs executions describe "$execution" \
        --project "$PROJECT" --region "$REGION" --format=json > "$raw"; then
      die "execution poll failed; raw retained: $raw"
    fi
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      canonicalize-external-json --raw "$raw" --output "$target" || \
      die "execution poll is malformed; raw retained: $raw"
    rm -- "$raw"
  fi
  POLL_STATE=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    poll-state --metadata "$target") || die "execution state differs"
}

wait_stage() {
  local stage=$1
  local uri execution target failure
  uri=$(stage_uri "$stage") || die "$stage output URI differs"
  stage_paths "$stage"
  ledger_execution "$LEDGER_PATH" "$uri"
  execution=$LEDGER_EXECUTION
  target="$OUT/.${stage}-poll.json"
  failure="$OUT/${stage}-terminal-failure.json"
  while true; do
    poll_execution "$execution" "$target"
    printf '%s LR8_LATER_%s state=%s execution=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
      "$(printf '%s' "$stage" | tr '[:lower:]' '[:upper:]')" \
      "$POLL_STATE" "$execution"
    case "$POLL_STATE" in
      True)
        STAGE_TERMINAL=$target
        return 0
        ;;
      Unknown)
        rm -- "$target"
        sleep 30
        ;;
      False)
        [ ! -e "$failure" ] || die "$stage terminal failure receipt exists"
        mv -- "$target" "$failure"
        echo "ERROR: $stage terminal failure; no result read/retry" >&2
        exit 10
        ;;
      *) die "$stage terminal state differs" ;;
    esac
  done
}

if [ ! -s "$OUT/source-completion.json" ]; then
  ensure_launched source
  wait_stage source
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    finish-source --output-dir "$OUT" --metadata "$STAGE_TERMINAL" || {
      echo "ERROR: source strict terminal harvest failed; no retry" >&2
      exit 2
    }
fi

if [ ! -s "$OUT/smoke-completion.json" ]; then
  ensure_launched smoke
  wait_stage smoke
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    finish-smoke --output-dir "$OUT" --metadata "$STAGE_TERMINAL" || {
      echo "ERROR: 2023-W1 smoke strict terminal harvest failed; no retry" >&2
      exit 2
    }
fi

if [ ! -s "$OUT/executions.txt" ]; then
  bash "$LAUNCHER" launch-cells --execute || {
    echo "ERROR: bounded cell continuation stopped; no execution is retried" >&2
    exit 2
  }
fi

TERMINAL_DIR="$OUT/cell-terminal-metadata"
mkdir -p "$TERMINAL_DIR"
while [ ! -s "$OUT/cell-completion.json" ]; do
  running=0
  failed=0
  for index in $(seq 0 53); do
    uri=$(stage_uri cell "$index") || die "cell $index output URI differs"
    stage_paths cell "$index"
    [ -s "$INTENT_PATH" ] && [ -s "$LEDGER_PATH" ] || \
      die "cell $index launch ledger is absent/ambiguous"
    ledger_execution "$LEDGER_PATH" "$uri"
    target=$(printf '%s/cell-%02d.json' "$TERMINAL_DIR" "$index")
    poll_execution "$LEDGER_EXECUTION" "$target"
    case "$POLL_STATE" in
      True) ;;
      Unknown)
        running=$((running + 1))
        rm -- "$target"
        ;;
      False)
        failed=$((failed + 1))
        ;;
      *) die "cell $index terminal state differs" ;;
    esac
  done
  printf '%s LR8_LATER_CELLS running=%s failed=%s terminal=%s total=54\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$running" "$failed" \
    "$((54 - running - failed))"
  if [ "$failed" -ne 0 ]; then
    echo "ERROR: one or more cells terminal-failed; no body read/retry" >&2
    exit 10
  fi
  if [ "$running" -eq 0 ]; then
    break
  fi
  sleep 30
done
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
  finish-cells --output-dir "$OUT" --terminal-dir "$TERMINAL_DIR" || {
    echo "ERROR: all-terminal cell harvest/replay failed; no retry" >&2
    exit 2
  }

if [ ! -s "$OUT/completion.json" ]; then
  ensure_launched aggregate
  wait_stage aggregate
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    finish-aggregate --output-dir "$OUT" --metadata "$STAGE_TERMINAL" || {
      echo "ERROR: 108-book aggregate strict terminal harvest failed; no retry" >&2
      exit 2
    }
fi
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
  validate-final --output-dir "$OUT" || {
    echo "ERROR: final completion replay/reopen failed; not FINISHED" >&2
    exit 2
  }

echo "LR8_LATER_PERIOD_SOURCE_FINISHED cells=54 books=108"
