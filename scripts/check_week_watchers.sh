#!/usr/bin/env bash
# Check the persistent supervisor's heartbeat and child logs. This is read-only and safe to run from a second shell.
set -Eeuo pipefail
OUT=${OUT:?set OUT to the week's output directory}
MAX_AGE=${MAX_AGE:-90}
W="$OUT/watchers"
H="$W/heartbeat"
[[ -f "$H" ]] || { echo "WATCHERS NOT HEALTHY: no heartbeat at $H" >&2; exit 2; }
age=$(( $(date +%s) - $(stat -c %Y "$H") ))
(( age <= MAX_AGE )) || { echo "WATCHERS NOT HEALTHY: heartbeat age ${age}s > ${MAX_AGE}s" >&2; exit 2; }
for name in after-build dk-entries late-inactives; do
  [[ -f "$W/$name.log" ]] || { echo "WATCHERS NOT HEALTHY: missing $W/$name.log" >&2; exit 2; }
done
echo "watchers healthy: heartbeat_age=${age}s directory=$W"
