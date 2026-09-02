#!/usr/bin/env bash
# Host-only single-writer registry for queue/launcher processes.
#
# Usage:
#   scripts/launcher_registry.sh run \
#     --root /absolute/repository/root \
#     --state-root /absolute/canonical/host/state \
#     --lane cloud-run-job-name \
#     --owner production \
#     --target-prefixes run-prefix-a,run-prefix-b \
#     -- /absolute/path/to/launcher [args ...]
#
# The wrapper owns one lane-wide flock while the child is alive and publishes
# a human-readable receipt under .tmp/launchers.  Lock files are deliberately
# persistent coordination inodes: cleanup releases the flock and removes only
# this process's receipt.  Unlinking a flock inode on exit would let a racing
# process create a second inode and defeat mutual exclusion.

set -euo pipefail

die() {
  printf 'ERROR: %s\n' "$*" >&2
  exit 2
}

usage() {
  sed -n '2,13p' "$0" >&2
  exit 2
}

ROOT=""
STATE_ROOT=""
STATE_ROOT_EXPLICIT=0
LANE=""
OWNER=""
TARGET_PREFIXES=""
REGISTRY_DIR=""
COMPLETION_DIR=""
LOCK_DIR=""
LOG_PATH=""
REGISTRATION=""
REGISTRATION_SHA256=""
COMPLETION_PATH=""
ACQUIRED_AT=""
SCRIPT_PATH=""
LOCK_FD=""
CHILD_PID=""
CHILD_PGID=""
CHILD_GROUP_FILE=""
WRAPPER_PGID=""
PROCESS_START_TICKS=""

log_event() {
  local action=$1 detail=$2 timestamp line
  timestamp=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
  line="$timestamp action=$action lane=$LANE pid=$$ detail=$detail"
  printf '%s\n' "$line" >&2
  if [[ -n "$LOG_PATH" ]]; then
    printf '%s\n' "$line" >>"$LOG_PATH"
  fi
}

publish_terminal_record() {
  local exit_status=$1 completed_at temp
  [[ -n "$COMPLETION_PATH" ]] || return 0
  [[ "$exit_status" =~ ^[0-9]+$ && "$exit_status" -le 255 ]] || return 1
  completed_at=$(date -u +'%Y-%m-%dT%H:%M:%SZ') || return 1
  temp=$(mktemp "$COMPLETION_DIR/.completion.XXXXXX") || return 1
  if ! jq -cnS \
      --arg schema shared-launcher-completion/v1 \
      --arg acquired "$ACQUIRED_AT" \
      --arg completed "$completed_at" \
      --arg lane "$LANE" \
      --arg owner "$OWNER" \
      --arg script "$SCRIPT_PATH" \
      --arg receipt_sha "$REGISTRATION_SHA256" \
      --arg prefixes "$TARGET_PREFIXES" \
      --argjson pid "$$" \
      --argjson ticks "$PROCESS_START_TICKS" \
      --argjson status "$exit_status" '{
        schema_version:$schema,acquired_at_utc:$acquired,
        completed_at_utc:$completed,lane:$lane,owner:$owner,
        script_path:$script,pid:$pid,process_start_ticks:$ticks,
        receipt_sha256:$receipt_sha,
        target_run_id_prefixes:($prefixes | split(",")),exit_status:$status
      }' >"$temp"; then
    rm -f -- "$temp"
    return 1
  fi
  chmod 0600 "$temp" || { rm -f -- "$temp"; return 1; }
  sync -d "$temp" || { rm -f -- "$temp"; return 1; }
  if ! ln "$temp" "$COMPLETION_PATH" 2>/dev/null; then
    if [[ ! -f "$COMPLETION_PATH" || -L "$COMPLETION_PATH" ]] ||
       ! cmp -s "$temp" "$COMPLETION_PATH"; then
      rm -f -- "$temp"
      return 1
    fi
  fi
  rm -f -- "$temp"
  if ! sync -f "$COMPLETION_DIR"; then
    rm -f -- "$COMPLETION_PATH"
    return 1
  fi
  log_event completed "receipt_sha256=$REGISTRATION_SHA256,exit_status=$exit_status,record=$COMPLETION_PATH"
}

process_start_ticks() {
  local pid=$1 stat rest
  [[ "$pid" =~ ^[1-9][0-9]*$ && -r "/proc/$pid/stat" ]] || return 1
  IFS= read -r stat <"/proc/$pid/stat" || return 1
  # Everything after the final ')' begins at proc(5) field 3 (state).
  # starttime is field 22, therefore the twentieth token in this suffix.
  rest=${stat##*) }
  set -- $rest
  [[ $# -ge 20 && "${20}" =~ ^[1-9][0-9]*$ ]] || return 1
  printf '%s\n' "${20}"
}

release_registry() {
  local cleanup_status=0 actual_sha
  # The durable completion is already published when this runs. Clean up
  # scratch state and release the flock before removing the receipt. If either
  # earlier step fails, retain the receipt so the monitor reports a
  # terminalized orphan instead of accepting a receiptless exit-status split.
  if [[ -n "$CHILD_GROUP_FILE" ]]; then
    if rm -f -- "$CHILD_GROUP_FILE"; then
      CHILD_GROUP_FILE=""
    else
      cleanup_status=1
    fi
  fi
  if [[ -n "$LOCK_FD" ]]; then
    flock -u "$LOCK_FD" 2>/dev/null || cleanup_status=1
    exec {LOCK_FD}>&-
    LOCK_FD=""
  fi
  if [[ -n "$REGISTRATION" && -e "$REGISTRATION" ]]; then
    if (( cleanup_status != 0 )); then
      log_event cleanup_refused "prerequisite_cleanup_failed:$REGISTRATION"
    elif [[ -f "$REGISTRATION" && ! -L "$REGISTRATION" ]]; then
      actual_sha=$(sha256sum "$REGISTRATION" | awk '{print $1}') || cleanup_status=1
      if [[ "$actual_sha" == "$REGISTRATION_SHA256" ]]; then
        rm -f -- "$REGISTRATION" || cleanup_status=1
      else
        log_event cleanup_refused "receipt_changed:$REGISTRATION"
        cleanup_status=1
      fi
    else
      log_event cleanup_refused "receipt_unsafe:$REGISTRATION"
      cleanup_status=1
    fi
  fi
  if (( cleanup_status == 0 )); then
    REGISTRATION=""
  fi
  return "$cleanup_status"
}

exit_trap() {
  local status=$1 cleanup_failed=0
  trap - EXIT INT TERM HUP
  if ! publish_terminal_record "$status"; then
    log_event completion_failed "receipt_sha256=$REGISTRATION_SHA256,exit_status=$status"
    [[ "$status" -ne 0 ]] || status=2
    # Keep the receipt until process death. The persistent orphan prevents a
    # contender from acquiring the lane without manual adjudication.
  else
    release_registry || cleanup_failed=1
    if (( cleanup_failed )) && [[ "$status" -eq 0 ]]; then status=2; fi
  fi
  exit "$status"
}

safe_child_group() {
  [[ "$CHILD_PGID" =~ ^[1-9][0-9]*$ ]] || return 1
  [[ "$CHILD_PGID" != "$$" ]] || return 1
  [[ -z "$WRAPPER_PGID" || "$CHILD_PGID" != "$WRAPPER_PGID" ]] || return 1
}

load_child_group() {
  local candidate=""
  [[ -n "$CHILD_GROUP_FILE" && -s "$CHILD_GROUP_FILE" ]] || return 1
  IFS= read -r candidate <"$CHILD_GROUP_FILE" || return 1
  [[ "$candidate" =~ ^[1-9][0-9]*$ ]] || return 1
  CHILD_PGID="$candidate"
  safe_child_group
}

child_group_alive() {
  safe_child_group || return 1
  kill -0 -- "-$CHILD_PGID" 2>/dev/null
}

wait_for_child_group() {
  while child_group_alive; do
    sleep 0.05
  done
}

terminate_child_group() {
  local requested_signal=$1 deadline

  if [[ -z "$CHILD_PGID" ]]; then
    load_child_group || true
  fi
  if child_group_alive; then
    kill -s "$requested_signal" -- "-$CHILD_PGID" 2>/dev/null || true
    deadline=$((SECONDS + 10))
    while child_group_alive && (( SECONDS < deadline )); do
      sleep 0.05
    done
    if child_group_alive; then
      log_event child_group_kill_escalation \
        "pgid=$CHILD_PGID,signal=$requested_signal"
      kill -KILL -- "-$CHILD_PGID" 2>/dev/null || true
    fi
  elif [[ -n "$CHILD_PID" ]]; then
    # Only reachable during the short session bootstrap window.
    kill -s "$requested_signal" "$CHILD_PID" 2>/dev/null || true
  fi
}

signal_trap() {
  local signal=$1 status=$2
  trap - EXIT INT TERM HUP
  terminate_child_group "$signal"
  [[ -z "$CHILD_PID" ]] || wait "$CHILD_PID" 2>/dev/null || true
  wait_for_child_group
  CHILD_PID=""
  CHILD_PGID=""
  if ! publish_terminal_record "$status"; then
    log_event completion_failed "receipt_sha256=$REGISTRATION_SHA256,exit_status=$status"
  else
    release_registry || true
  fi
  exit "$status"
}

validate_receipt_shape() {
  local receipt=$1
  [[ -f "$receipt" && ! -L "$receipt" ]] || return 1
  jq -e '
    (keys | sort) == ([
      "acquired_at_utc", "lane", "owner", "pid", "process_start_ticks",
      "schema_version", "script_path", "target_run_id_prefixes"
    ] | sort) and
    .schema_version == "shared-launcher-registry/v1" and
    (.script_path | type == "string" and length > 0) and
    (.pid | type == "number" and . > 0 and floor == .) and
    (.process_start_ticks | type == "number" and . > 0 and floor == .) and
    (.owner == "lab" or .owner == "production") and
    (.lane | type == "string" and length > 0) and
    (.target_run_id_prefixes | type == "array" and length > 0 and
      all(.[]; type == "string" and length > 0)) and
    (.acquired_at_utc | type == "string" and
      test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$"))
  ' "$receipt" >/dev/null
}

clean_stale_same_lane_receipts() {
  local receipt receipt_lane receipt_pid receipt_ticks live_ticks
  for receipt in "$REGISTRY_DIR"/*; do
    [[ -e "$receipt" || -L "$receipt" ]] || continue
    validate_receipt_shape "$receipt" || \
      die "launcher receipt is malformed or unsafe; manual review required: $receipt"
    receipt_lane=$(jq -er '.lane' "$receipt")
    [[ "$receipt_lane" == "$LANE" ]] || continue
    receipt_pid=$(jq -er '.pid | tostring' "$receipt")
    receipt_ticks=$(jq -er '.process_start_ticks | tostring' "$receipt")
    if live_ticks=$(process_start_ticks "$receipt_pid"); then
      if [[ "$live_ticks" == "$receipt_ticks" ]]; then
        die "live launcher already owns lane $LANE: $receipt (pid $receipt_pid)"
      fi
      die "launcher receipt owner identity changed; manual adjudication required: $receipt"
    elif kill -0 "$receipt_pid" 2>/dev/null; then
      die "launcher owner cannot be proven stale for lane $LANE: $receipt (pid $receipt_pid)"
    else
      die "launcher receipt owner is absent; surviving child work cannot be excluded; manual adjudication required: $receipt"
    fi
  done
}

describe_lock_owner() {
  local receipt receipt_lane receipt_pid receipt_ticks live_ticks
  for receipt in "$REGISTRY_DIR"/*; do
    [[ -e "$receipt" || -L "$receipt" ]] || continue
    validate_receipt_shape "$receipt" || continue
    receipt_lane=$(jq -er '.lane' "$receipt")
    [[ "$receipt_lane" == "$LANE" ]] || continue
    receipt_pid=$(jq -er '.pid | tostring' "$receipt")
    receipt_ticks=$(jq -er '.process_start_ticks | tostring' "$receipt")
    if live_ticks=$(process_start_ticks "$receipt_pid") && \
       [[ "$live_ticks" == "$receipt_ticks" ]]; then
      printf '%s (pid %s)' "$receipt" "$receipt_pid"
      return 0
    fi
  done
  printf '%s' 'unidentified live lock owner'
}

acquire_registry() {
  local lane_hash lock_path script_name temp receipt_owner
  lane_hash=$(printf '%s' "$LANE" | sha256sum | awk '{print $1}')
  lock_path="$LOCK_DIR/$lane_hash.lock"
  [[ ! -L "$lock_path" ]] || die "launcher lane lock cannot be a symlink: $lock_path"
  exec {LOCK_FD}<>"$lock_path"
  if ! flock -n "$LOCK_FD"; then
    receipt_owner=$(describe_lock_owner)
    exec {LOCK_FD}>&-
    LOCK_FD=""
    die "launcher lane is already owned: $LANE ($receipt_owner)"
  fi

  clean_stale_same_lane_receipts

  SCRIPT_PATH=$(command -v -- "$1" 2>/dev/null || true)
  [[ -n "$SCRIPT_PATH" ]] || die "launcher command is not executable: $1"
  SCRIPT_PATH=$(readlink -f -- "$SCRIPT_PATH")
  [[ -f "$SCRIPT_PATH" && -x "$SCRIPT_PATH" ]] || \
    die "launcher command path differs: $SCRIPT_PATH"
  script_name=${SCRIPT_PATH##*/}
  [[ "$script_name" =~ ^[A-Za-z0-9._-]+$ ]] || die "launcher script name differs"
  REGISTRATION="$REGISTRY_DIR/$script_name-$$.json"
  [[ ! -e "$REGISTRATION" && ! -L "$REGISTRATION" ]] || \
    die "launcher registration already exists: $REGISTRATION"
  ACQUIRED_AT=$(date -u +'%Y-%m-%dT%H:%M:%SZ')
  temp=$(mktemp "$REGISTRY_DIR/.registration.XXXXXX")
  jq -cnS \
    --arg schema shared-launcher-registry/v1 \
    --arg script "$SCRIPT_PATH" \
    --argjson pid "$$" \
    --argjson ticks "$PROCESS_START_TICKS" \
    --arg owner "$OWNER" \
    --arg lane "$LANE" \
    --arg prefixes "$TARGET_PREFIXES" \
    --arg acquired "$ACQUIRED_AT" '{
      schema_version:$schema,script_path:$script,pid:$pid,
      process_start_ticks:$ticks,owner:$owner,lane:$lane,
      target_run_id_prefixes:($prefixes | split(",")),
      acquired_at_utc:$acquired
    }' >"$temp"
  chmod 0600 "$temp"
  if ! ln "$temp" "$REGISTRATION" 2>/dev/null; then
    rm -f -- "$temp"
    die "launcher registration create race: $REGISTRATION"
  fi
  rm -f -- "$temp"
  REGISTRATION_SHA256=$(sha256sum "$REGISTRATION" | awk '{print $1}')
  [[ "$REGISTRATION_SHA256" =~ ^[0-9a-f]{64}$ ]] || die "launcher receipt hash differs"
  COMPLETION_PATH="$COMPLETION_DIR/$REGISTRATION_SHA256.json"
  [[ ! -e "$COMPLETION_PATH" && ! -L "$COMPLETION_PATH" ]] ||
    die "launcher completion already exists: $COMPLETION_PATH"
  log_event acquired "receipt=$REGISTRATION,script=$SCRIPT_PATH,prefixes=$TARGET_PREFIXES"
}

parse_run() {
  [[ "${1:-}" == run ]] || usage
  shift
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --root)
        [[ $# -ge 2 ]] || usage
        ROOT=$2
        shift 2
        ;;
      --state-root)
        [[ $# -ge 2 ]] || usage
        STATE_ROOT=$2
        STATE_ROOT_EXPLICIT=1
        shift 2
        ;;
      --lane)
        [[ $# -ge 2 ]] || usage
        LANE=$2
        shift 2
        ;;
      --owner)
        [[ $# -ge 2 ]] || usage
        OWNER=$2
        shift 2
        ;;
      --target-prefixes)
        [[ $# -ge 2 ]] || usage
        TARGET_PREFIXES=$2
        shift 2
        ;;
      --)
        shift
        break
        ;;
      *) usage ;;
    esac
  done
  [[ $# -gt 0 ]] || die "launcher command is absent"
  [[ "$ROOT" == /* && -d "$ROOT" && ! -L "$ROOT" ]] || \
    die "repository root must be one absolute real directory"
  ROOT=$(cd "$ROOT" && pwd -P)
  [[ ! -L "$ROOT/.tmp" ]] || die "repository scratch root cannot be a symlink"
  mkdir -p "$ROOT/.tmp"
  [[ -d "$ROOT/.tmp" ]] || die "repository scratch root differs"
  if [[ -z "$STATE_ROOT" ]]; then
    STATE_ROOT="$ROOT/.tmp"
  fi
  [[ "$STATE_ROOT" == /* && ! -L "$STATE_ROOT" ]] ||
    die "launcher state root must be one absolute real directory"
  mkdir -p "$STATE_ROOT"
  STATE_ROOT=$(cd "$STATE_ROOT" && pwd -P)
  [[ "$LANE" =~ ^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$ ]] || \
    die "launcher lane differs"
  if [[ "$LANE" == nfl2-lab-jobs && (
        "$STATE_ROOT_EXPLICIT" -ne 1 ||
        "$STATE_ROOT" != /home/erich/.local/state/nfl-dfs/lab-launcher-registry
      ) ]]; then
    die "lane nfl2-lab-jobs requires canonical --state-root /home/erich/.local/state/nfl-dfs/lab-launcher-registry"
  fi
  [[ "$OWNER" == production || "$OWNER" == lab ]] || die "launcher owner differs"
  [[ "$TARGET_PREFIXES" =~ ^[A-Za-z0-9][A-Za-z0-9._:-]*(,[A-Za-z0-9][A-Za-z0-9._:-]*)*$ ]] || \
    die "target run-id prefixes differ"
  for tool in awk cmp date flock jq mktemp ps readlink setsid sha256sum sync tr; do
    command -v "$tool" >/dev/null 2>&1 || die "required host tool is absent: $tool"
  done

  REGISTRY_DIR="$STATE_ROOT/launchers"
  COMPLETION_DIR="$STATE_ROOT/launcher-completions"
  LOCK_DIR="$STATE_ROOT/launcher-locks"
  LOG_PATH="$STATE_ROOT/launcher-registry.log"
  [[ ! -L "$REGISTRY_DIR" && ! -L "$COMPLETION_DIR" && ! -L "$LOCK_DIR" && ! -L "$LOG_PATH" ]] || \
    die "launcher registry paths cannot be symlinks"
  mkdir -p "$REGISTRY_DIR" "$COMPLETION_DIR" "$LOCK_DIR"
  chmod 0700 "$COMPLETION_DIR"
  [[ -d "$REGISTRY_DIR" && -d "$COMPLETION_DIR" && -d "$LOCK_DIR" ]] ||
    die "launcher registry directories differ"
  PROCESS_START_TICKS=$(process_start_ticks "$$") || die "launcher process identity unavailable"

  trap 'exit_trap "$?"' EXIT
  trap 'signal_trap INT 130' INT
  trap 'signal_trap TERM 143' TERM
  trap 'signal_trap HUP 129' HUP
  acquire_registry "$1"

  WRAPPER_PGID=$(ps -o pgid= -p "$$" | tr -d '[:space:]')
  [[ "$WRAPPER_PGID" =~ ^[1-9][0-9]*$ ]] || die "wrapper process group unavailable"

  cd "$ROOT"
  CHILD_GROUP_FILE=$(mktemp "$ROOT/.tmp/.launcher-group.XXXXXX")
  chmod 0600 "$CHILD_GROUP_FILE"
  # The child must not inherit the lane flock. The wrapper remains its sole
  # owner. The dedicated session keeps ordinary launcher descendants in a
  # group that cannot be confused with (or signal) the wrapper's own group.
  (
    exec {LOCK_FD}>&-
    export NFL_LAUNCHER_REGISTRY_RECEIPT="$REGISTRATION"
    export NFL_LAUNCHER_REGISTRY_RECEIPT_SHA256="$REGISTRATION_SHA256"
    export NFL_LAUNCHER_REGISTRY_STATE_ROOT="$STATE_ROOT"
    export NFL_LAUNCHER_REGISTRY_LANE="$LANE"
    export NFL_LAUNCHER_REGISTRY_WRAPPER_PID="$$"
    export NFL_LAUNCHER_REGISTRY_WRAPPER_START_TICKS="$PROCESS_START_TICKS"
    exec setsid --wait /bin/bash -c '
      group_file=$1
      shift
      printf "%s\n" "$$" >"$group_file"
      exec "$@"
    ' launcher-registry-session "$CHILD_GROUP_FILE" "$@"
  ) &
  CHILD_PID=$!

  local status bootstrap_deadline observed_pgid
  bootstrap_deadline=$((SECONDS + 5))
  while ! load_child_group && kill -0 "$CHILD_PID" 2>/dev/null && \
      (( SECONDS < bootstrap_deadline )); do
    sleep 0.01
  done
  if ! load_child_group; then
    wait "$CHILD_PID" 2>/dev/null || true
    CHILD_PID=""
    die "launcher failed before publishing its isolated process group"
  fi
  if kill -0 "$CHILD_PGID" 2>/dev/null; then
    observed_pgid=$(ps -o pgid= -p "$CHILD_PGID" | tr -d '[:space:]')
    if [[ "$observed_pgid" != "$CHILD_PGID" ]]; then
      terminate_child_group TERM
      wait "$CHILD_PID" 2>/dev/null || true
      CHILD_PID=""
      die "launcher process group verification failed"
    fi
  fi

  if wait "$CHILD_PID"; then
    status=0
  else
    status=$?
  fi
  CHILD_PID=""
  # A launcher can return after starting provider-launching work. Retain the
  # lane until every ordinary descendant in its isolated group is gone.
  wait_for_child_group
  CHILD_PGID=""
  return "$status"
}

parse_run "$@"
