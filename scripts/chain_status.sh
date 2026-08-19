#!/usr/bin/env bash
set -uo pipefail

# One-shot, operator-runnable status of every research chain: live
# processes, ACTIVE chain logs separated from finished/dead ones, cloud
# build states, whichever cell grids are currently running, and the
# outcome-lease governance state.
# Run it yourself anytime:  bash scripts/chain_status.sh
# Stream any chain live:    tail -f ~/nfl-panels/<log>
#
# Every section is queried live at run time. Nothing here is hardcoded
# to a particular experiment: the grid section derives from whichever
# execution ledgers were most recently written, so it rolls forward on
# its own as experiments change. Logs are labelled LIVE or ended with
# their age, so a finished chain can never be mistaken for a running
# one.

PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PANELS="$HOME/nfl-panels"
BOLD=$(tput bold 2>/dev/null || true); NORM=$(tput sgr0 2>/dev/null || true)
# A log counts as ACTIVE if its process is alive or it was written
# within this many seconds (watchers poll on multi-minute intervals).
ACTIVE_WINDOW=900

echo "${BOLD}== generated ==${NORM}"
echo "  $(date -u +%Y-%m-%dT%H:%M:%SZ) (utc)   $(date +%H:%M:%S%z) (local)"

echo "${BOLD}== chain processes ==${NORM}"
CHAIN_RE="watch_[a-z_]+\.sh|drive_[a-z_]+\.sh|repair_[a-z0-9_]+\.sh"
CHAIN_RE="$CHAIN_RE|tally_[a-z_]+\.sh|cloud_[a-z0-9_]+chain\.sh"
PROCS=$(ps -eo pid,etime,args --no-headers 2>/dev/null \
  | grep -aE "$CHAIN_RE" | grep -av "grep -" \
  | grep -av -- "-c source" \
  | awk '{for (i=3; i<=NF; i++) if ($i ~ /\.sh$/) {
            printf "  pid %-8s up %-11s %s\n", $1, $2, $i; break } }' \
  | sed 's|/tmp/nfl-[a-z0-9-]*/||; s|scripts/||')
[ -n "$PROCS" ] && echo "$PROCS" || echo "  (none running)"

now=$(date +%s)
# Exact liveness: a log is LIVE only if a running chain process has it
# open as stdout (/proc/<pid>/fd/1). Name matching would mark every
# superseded r2/r3/r4 log live whenever any same-family watcher runs.
LIVE_LOGS=""
for pid in $(printf '%s' "$PROCS" | awk '{print $2}'); do
  target=$(readlink "/proc/$pid/fd/1" 2>/dev/null)
  case "$target" in *.log) LIVE_LOGS="$LIVE_LOGS$target
";; esac
done

echo "${BOLD}== active chain logs (process alive) ==${NORM}"
ACTIVE=""; ENDED=""
for log in $(ls -t "$PANELS"/*.log 2>/dev/null | head -14); do
  age=$(( now - $(stat -c %Y "$log" 2>/dev/null || echo "$now") ))
  line=$(tail -1 "$log" 2>/dev/null)
  [ -z "$line" ] && line="(no output yet)"
  if printf '%s' "$LIVE_LOGS" | grep -qxF "$log"; then
    ACTIVE="$ACTIVE$(printf '  %-34s %4dm ago  %s\n' \
      "$(basename "$log")" "$((age/60))" "${line:0:96}")
"
  else
    ENDED="$ENDED$(printf '  %-34s %4dm ago  %s\n' \
      "$(basename "$log")" "$((age/60))" "${line:0:96}")
"
  fi
done
[ -n "$ACTIVE" ] && printf '%s' "$ACTIVE" \
  || echo "  (no chain process is writing a log right now)"

# Only ledgers touched inside this window describe a grid that is still
# launching or polling cells; anything older is a finished experiment
# and is labelled as such rather than presented as current.
GRID_WINDOW=$((12 * 3600))
echo "${BOLD}== cell grids ==${NORM}"
GRIDS=$(ls -t "$ROOT"/reports/*-runs/*/executions.txt 2>/dev/null | head -3)
if [ -z "$GRIDS" ]; then
  echo "  (no execution ledgers)"
else
  for ledger in $GRIDS; do
    dir=$(dirname "$ledger")
    run=$(basename "$dir")
    age=$(( now - $(stat -c %Y "$ledger" 2>/dev/null || echo "$now") ))
    cells=$(wc -l < "$ledger" 2>/dev/null | tr -d ' ')
    uri=$(awk 'NF>=5 {print $5; exit}' "$ledger" 2>/dev/null)
    prefix="${uri%/*}"
    # Aggregates land locally beside the ledger, or in GCS beside the
    # cells / one level up when the run used an attempt subdirectory.
    if [ -s "$dir/aggregate-report.json" ] \
      || { [ -n "$prefix" ] && { \
           gsutil -q stat "$prefix/aggregate-report.json" 2>/dev/null \
        || gsutil -q stat "${prefix%/*}/aggregate-report.json" 2>/dev/null; }; }
    then
      agg=PRESENT
    else
      agg=pending
    fi
    # Aggregate present means the grid is finished, however fresh its
    # ledger looks; only an unaggregated recent ledger is still running.
    if [ "$agg" = PRESENT ]; then tag="done"
    elif [ "$age" -lt "$GRID_WINDOW" ]; then tag="ACTIVE"
    else tag="stalled"; fi
    if [ -n "$uri" ]; then
      done_n=$(gsutil ls "$prefix/slate-*.json" 2>/dev/null | wc -l | tr -d ' ')
      printf '  [%-7s] %-46s %s/%s cells, aggregate %s (%dh old)\n' \
        "$tag" "${run:0:46}" "$done_n" "$cells" "$agg" "$((age/3600))"
    else
      printf '  [%-7s] %-46s %s launched, no uri in ledger (%dh old)\n' \
        "$tag" "${run:0:46}" "$cells" "$((age/3600))"
    fi
  done
fi

echo "${BOLD}== cloud builds (last 5) ==${NORM}"
gcloud builds list --project "$PROJECT" --limit 5 \
  --format="value(id,status,substitutions._IMAGE,createTime)" 2>/dev/null \
  | awk -F'\t' '{n=split($3,a,":"); printf "  %-38s %-15s %s\n", $1, $2, a[n]}'

echo "${BOLD}== outcome lease ==${NORM}"
LEASE=gs://nfl-predictions-503414-raw/research-governance/historical-outcome-active-v1.json
if gsutil -q stat "$LEASE" 2>/dev/null; then
  holder=$(gsutil cat "$LEASE" 2>/dev/null \
    | grep -ao '"run_id":"[^"]*"' | head -1 | cut -d'"' -f4)
  echo "  HELD by ${holder:-unknown}"
else
  echo "  free"
fi

echo "${BOLD}== recent handoff commits ==${NORM}"
git -C "$ROOT" log --oneline -5 2>/dev/null | sed 's/^/  /'

if [ -n "$ENDED" ]; then
  echo "${BOLD}== ended logs (history — no process attached) ==${NORM}"
  printf '%s' "$ENDED" | head -8
fi
