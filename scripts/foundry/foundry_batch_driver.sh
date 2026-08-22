#!/usr/bin/env bash
# Foundry sequential task driver: runs tasks FIRST..LAST of the configured
# corpus-parametric batch through launch -> recover -> watch(producer close)
# -> verifier launch -> recover -> watch(accept), resuming from receipts.
#
# Receipt files under $CORPUS_PARAMETRIC_RUN_DIR/tasks/ are the ONLY state:
#   %03d-producer-bound.json / -closed.json, %03d-verifier-bound.json /
#   -accepted.json.  A consumed phase is NEVER reinvoked; the underlying
#   reuse-script gates stay authoritative.  Safe to rerun after any crash.
#
# Usage: foundry_batch_driver.sh FIRST LAST
# Requires the same exported CORPUS_PARAMETRIC_* environment as the reuse
# script (run dir, job, contract identity, enable flag) plus
# CORPUS_PARAMETRIC_SOURCE (repo root containing scripts/).

set -euo pipefail

FIRST="${1:?first task index required}"
LAST="${2:?last task index required}"
SOURCE="${CORPUS_PARAMETRIC_SOURCE:?repo root required}"
POLL_SECONDS="${FOUNDRY_POLL_SECONDS:-120}"
PROJECT="nfl-predictions-503414"
REGION="us-central1"
MAX_TASK_INDEX=53

[[ "$FIRST" =~ ^[0-9]+$ && "$LAST" =~ ^[0-9]+$ ]] || {
  echo "task indexes must be nonnegative integers" >&2; exit 2; }
(( FIRST <= LAST )) || { echo "FIRST must be <= LAST" >&2; exit 2; }
(( LAST <= MAX_TASK_INDEX )) || {
  echo "LAST exceeds the 54-task batch (max ${MAX_TASK_INDEX})" >&2; exit 2; }

log() { printf '%s foundry-driver %s\n' "$(date -u +%FT%TZ)" "$*"; }

receipt() {
  printf '%s/tasks/%03d-%s.json' "$CORPUS_PARAMETRIC_RUN_DIR" "$1" "$2"
}

reuse() {
  ( cd "$SOURCE" && bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute "$1" )
}

execution_completed() {
  local bound="$1"
  local execution_id
  execution_id="$(jq -er '.execution_id' "$bound")"
  gcloud run jobs executions describe "$execution_id" \
    --project "$PROJECT" --region "$REGION" --format=json 2>/dev/null | \
    jq -r '[.status.conditions[]? | select(.type=="Completed")][0].status // "Unknown"'
}

wait_terminal() {
  local bound="$1" phase="$2" task="$3"
  while true; do
    local status
    status="$(execution_completed "$bound")"
    case "$status" in
      True) log "task $task $phase execution terminal success"; return 0 ;;
      False)
        log "FATAL task $task $phase execution failed; no retry is licensed"
        return 9 ;;
      *) log "task $task $phase still running"; sleep "$POLL_SECONDS" ;;
    esac
  done
}

run_phase() {
  local task="$1" phase="$2" closed_suffix="$3"
  export CORPUS_PARAMETRIC_TASK_INDEX="$task"
  local bound closed
  bound="$(receipt "$task" "${phase}-bound")"
  closed="$(receipt "$task" "$closed_suffix")"
  if [[ -f "$closed" ]]; then
    log "task $task $phase already terminal ($closed_suffix exists)"
    return 0
  fi
  if [[ ! -f "$bound" ]]; then
    local launch_marker="$CORPUS_PARAMETRIC_RUN_DIR/timestamps/task-${task}-${phase}-launch.txt"
    if [[ -f "$launch_marker" ]]; then
      log "task $task $phase launch already consumed; recovering only"
    else
      log "task $task launching $phase"
      reuse "launch-${phase}"
    fi
    log "task $task recovering/binding $phase"
    reuse "recover-${phase}"
  fi
  [[ -f "$bound" ]] || { log "FATAL task $task $phase bind receipt absent"; return 8; }
  wait_terminal "$bound" "$phase" "$task"
  log "task $task closing $phase (watch-${phase})"
  reuse "watch-${phase}"
  [[ -f "$closed" ]] || { log "FATAL task $task $phase terminal receipt absent"; return 7; }
}

for required in CORPUS_PARAMETRIC_RUN_DIR CORPUS_PARAMETRIC_JOB \
  CORPUS_PARAMETRIC_PYTHON \
  CORPUS_PARAMETRIC_CONTRACT_URI CORPUS_PARAMETRIC_CONTRACT_GENERATION \
  CORPUS_PARAMETRIC_CONTRACT_SHA256 CORPUS_PARAMETRIC_CONTRACT_BYTES; do
  [[ -n "${!required:-}" ]] || { echo "missing $required" >&2; exit 2; }
done
[[ "${CORPUS_PARAMETRIC_RESEARCH_ENABLED:-}" == "1" ]] || {
  echo "CORPUS_PARAMETRIC_RESEARCH_ENABLED=1 required" >&2; exit 2; }

# Fan-out gate: any range beyond task 0 requires an immutable task-0
# science-equivalence PASS receipt against the accepted v4 result.
EQUIVALENCE_RECEIPT="$CORPUS_PARAMETRIC_RUN_DIR/task0-equivalence-pass.json"
if (( FIRST >= 1 )); then
  [[ -f "$EQUIVALENCE_RECEIPT" && ! -L "$EQUIVALENCE_RECEIPT" ]] || {
    echo "refused: $EQUIVALENCE_RECEIPT is absent; tasks 1..53 are gated on" \
      "the task-0 v4/v5 science-equivalence PASS" >&2; exit 5; }
  jq -e '.equivalent == true and .comparison == "science-only"' \
    "$EQUIVALENCE_RECEIPT" >/dev/null || {
    echo "refused: task-0 equivalence receipt does not record a PASS" >&2
    exit 5; }
fi

for task in $(seq "$FIRST" "$LAST"); do
  log "=== task $task begin ==="
  run_phase "$task" producer producer-closed
  run_phase "$task" verifier verifier-accepted
  accepted="$(receipt "$task" verifier-accepted)"
  jq -e '.accepted == true and .partial_result == false' "$accepted" >/dev/null || {
    log "FATAL task $task verifier acceptance flags differ"; exit 6; }
  log "=== task $task ACCEPTED ==="
done
log "tasks ${FIRST}..${LAST} complete"
