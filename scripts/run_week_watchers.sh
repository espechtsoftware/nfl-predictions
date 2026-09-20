#!/usr/bin/env bash
# Persistent watcher supervisor.  The old host wrapper launched detached children and then exited, so systemd killed
# their cgroup before the first log line.  This process owns the three watchers and waits for them, keeping the timer
# service alive; it also writes a heartbeat that the operator can check while away from the machine.
set -Eeuo pipefail
SCRIPT_DIR=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
if [[ -z "${WEEK:-}" ]]; then
  WEEK=${1:?usage: run_week_watchers.sh WEEK}
  shift
fi
# shellcheck disable=SC1091
source "$SCRIPT_DIR/week_env.sh"
week_env "$WEEK" "${GROUP:-}"
[[ -f "$CONTESTS_JSON" ]] || { echo "watchers: contests file missing: $CONTESTS_JSON" >&2; exit 2; }
"$PROD_PY" "$SCRIPT_DIR/check_week_runtime.py" --role watchers
if [[ "${1:-}" == "--check" ]]; then exit 0; fi

WATCH_DIR="$OUT/watchers"
mkdir -p "$WATCH_DIR"
HEARTBEAT="$WATCH_DIR/heartbeat"
touch "$HEARTBEAT"
PIDS=()
NAMES=()
FAILED=0

start_watcher() {
  local name=$1; shift
  echo "$(date -u +%FT%TZ) starting $name: $*" | tee -a "$WATCH_DIR/supervisor.log"
  "$@" >"$WATCH_DIR/$name.log" 2>&1 &
  PIDS+=("$!")
  NAMES+=("$name")
}

cleanup() {
  local status=$?
  trap - EXIT INT TERM
  for pid in "${PIDS[@]:-}"; do kill "$pid" 2>/dev/null || true; done
  for pid in "${PIDS[@]:-}"; do wait "$pid" 2>/dev/null || true; done
  echo "$(date -u +%FT%TZ) supervisor exit status=$status" | tee -a "$WATCH_DIR/supervisor.log"
  exit "$status"
}
trap cleanup EXIT INT TERM

start_watcher after-build "$SCRIPT_DIR/sunday_after_build.sh"
start_watcher dk-entries "$SCRIPT_DIR/sunday_watch_dk_entries.sh"
start_watcher late-inactives "$PROD_PY" "$SCRIPT_DIR/sunday_watch_late_inactives.py"

while ((${#PIDS[@]})); do
  touch "$HEARTBEAT"
  next_pids=(); next_names=()
  for i in "${!PIDS[@]}"; do
    pid=${PIDS[$i]}; name=${NAMES[$i]}
    if kill -0 "$pid" 2>/dev/null; then
      next_pids+=("$pid"); next_names+=("$name")
    else
      if wait "$pid"; then
        echo "$(date -u +%FT%TZ) $name exited successfully" | tee -a "$WATCH_DIR/supervisor.log"
      else
        FAILED=1
        echo "$(date -u +%FT%TZ) $name exited with failure; see $WATCH_DIR/$name.log" | tee -a "$WATCH_DIR/supervisor.log" >&2
      fi
    fi
  done
  PIDS=("${next_pids[@]}"); NAMES=("${next_names[@]}")
  ((${#PIDS[@]})) && sleep 60
done
exit "$FAILED"
