#!/usr/bin/env bash
set -uo pipefail

# One-owner watcher for LR8 score-free preparation plus 70 cell executions.
# Polling reads Cloud Run metadata only.  The finisher owns every GCS
# inventory/body read and performs it only after strict terminal success.

ROOT=$(cd "$(dirname "$0")/.." && pwd)
PROJECT=nfl-predictions-503414
REGION=us-central1
JOB=atlas-md-prefix-r4-smoke
ATTEMPT_ID=20260821-lr8-full-source-shards-v1
OUT="$ROOT/reports/lr8-full-source-shard-runs/$ATTEMPT_ID"
LAUNCHER="$ROOT/scripts/cloud_lr8_full_source_shards.sh"
FINISHER="$ROOT/scripts/finish_lr8_full_source_shards.py"
PYTHON=${NFL_DFS_PYTHON:-"$ROOT/.venv/bin/python"}

poll_execution() {
  local execution=$1 target=$2 raw="$2.raw.pending"
  gcloud run jobs executions describe "$execution" --project "$PROJECT" \
    --region "$REGION" --format=json > "$raw" || return 2
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    canonicalize-external-json --raw "$raw" --output "$target" || return 2
  rm -- "$raw"
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    poll-state --metadata "$target"
}

if [ ! -s "$OUT/preparation-completion.json" ]; then
  mapfile -t PREP_FIELDS < <(
    PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
      preparation-ledger-arguments \
      --ledger "$OUT/preparation-execution.txt"
  ) || exit 2
  [ "${#PREP_FIELDS[@]}" -eq 3 ] || exit 2
  LEDGER_JOB=${PREP_FIELDS[0]}
  PREP_EXECUTION=${PREP_FIELDS[1]}
  [ "$LEDGER_JOB" = "$JOB" ] || exit 2
  while true; do
    rm -f -- "$OUT/preparation-poll.json"
    STATE=$(poll_execution "$PREP_EXECUTION" "$OUT/preparation-poll.json") || exit 2
    printf '%s LR8_FULL_SOURCE_PREPARATION state=%s execution=%s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$STATE" "$PREP_EXECUTION"
    case "$STATE" in
      True) break ;;
      False) echo "ERROR: LR8 preparation failed; no retry" >&2; exit 10 ;;
      Unknown) rm -f -- "$OUT/preparation-poll.json"; sleep 30 ;;
      *) exit 2 ;;
    esac
  done
  PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
    finish-preparation --output-dir "$OUT" \
    --ledger "$OUT/preparation-execution.txt" \
    --metadata "$OUT/preparation-poll.json" || exit $?
fi

if [ ! -s "$OUT/executions.txt" ]; then
  bash "$LAUNCHER" launch-cells || exit $?
fi
PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
  validate-cell-ledger --ledger "$OUT/executions.txt" || exit $?

mkdir -p "$OUT/cell-terminal-metadata"
while true; do
  running=0
  failed=0
  index=0
  while read -r LEDGER_JOB EXECUTION _uri; do
    [ "$LEDGER_JOB" = "$JOB" ] || exit 2
    TARGET=$(printf '%s/cell-terminal-metadata/cell-%02d.json' "$OUT" "$index")
    if [ -e "$TARGET" ]; then
      STATE=$(PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" \
        poll-state --metadata "$TARGET") || exit 2
    else
      STATE=$(poll_execution "$EXECUTION" "$TARGET") || exit 2
    fi
    case "$STATE" in
      True) ;;
      False) failed=$((failed + 1)) ;;
      Unknown) running=$((running + 1)); rm -f -- "$TARGET" ;;
      *) exit 2 ;;
    esac
    index=$((index + 1))
  done < "$OUT/executions.txt"
  [ "$index" -eq 70 ] || exit 2
  printf '%s LR8_FULL_SOURCE_CELLS running=%s failed=%s total=70\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$running" "$failed"
  [ "$failed" -eq 0 ] || exit 10
  [ "$running" -eq 0 ] && break
  sleep 30
done

PYTHONPATH="$ROOT/src:$ROOT/scripts" "$PYTHON" "$FINISHER" finish-cells \
  --output-dir "$OUT" --ledger "$OUT/executions.txt" \
  --terminal-dir "$OUT/cell-terminal-metadata" || exit $?
echo "LR8_FULL_SOURCE_FINISHED cells=70"
