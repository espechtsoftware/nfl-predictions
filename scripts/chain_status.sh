#!/usr/bin/env bash
set -uo pipefail

# Operator dashboard for every research chain: live processes, active
# chain logs, cell grids, cloud builds, the outcome lease, and a feed of
# what changed. Two modes:
#
#   bash scripts/chain_status.sh            one-shot snapshot (scriptable)
#   bash scripts/chain_status.sh --watch    full-screen live app (q quits)
#   bash scripts/chain_status.sh -w -i 5    live app, 5s repaint
#
# Everything is derived at run time — nothing is hardcoded to a specific
# experiment. Local state (processes, logs, ledgers, git) is cheap and
# repaints every interval; cloud state (gcloud/gsutil) is refreshed by a
# background worker at most every CLOUD_INTERVAL seconds and rendered
# from cache with its age shown, so the UI never blocks on the network
# and the API is never hammered.

PROJECT=nfl-predictions-503414
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PANELS="$HOME/nfl-panels"
CACHE="${TMPDIR:-/tmp}/chain-status-$(id -u)"
LEASE_URI=gs://nfl-predictions-503414-raw/research-governance/historical-outcome-active-v1.json
CLOUD_INTERVAL=60
GRID_WINDOW=$((12 * 3600))
HEARTBEAT='status=WORKING|status=QUEUED|state=Unknown|WAITS_FOR'
CHAIN_RE='watch_[a-z_]+\.sh|drive_[a-z_]+\.sh|repair_[a-z0-9_]+\.sh'
CHAIN_RE="$CHAIN_RE"'|tally_[a-z_]+\.sh|cloud_[a-z0-9_]+chain\.sh'

WATCH=0
INTERVAL=3
while [ $# -gt 0 ]; do
  case "$1" in
    -w|--watch) WATCH=1 ;;
    -i|--interval) INTERVAL=${2:-3}; shift ;;
    -h|--help)
      sed -n '4,17p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $1 (try --help)" >&2; exit 2 ;;
  esac
  shift
done

if [ -t 1 ]; then
  B=$'\033[1m'; D=$'\033[2m'; N=$'\033[0m'
  R=$'\033[31m'; G=$'\033[32m'; Y=$'\033[33m'; C=$'\033[36m'
else
  B=""; D=""; N=""; R=""; G=""; Y=""; C=""
fi
[ "$WATCH" = 1 ] && [ ! -t 1 ] && {
  echo "--watch needs a terminal" >&2; exit 2; }

cols() { tput cols 2>/dev/null || echo 100; }
fit() {  # fit "$text" -> truncated to terminal width, ANSI-aware
  local text=$1 plain width
  width=$(( $(cols) - 2 ))
  # Colour codes must not count toward the visible width, or coloured
  # lines truncate long before the terminal edge.
  plain=$(printf '%s' "$text" | sed $'s/\033\\[[0-9;]*m//g')
  if [ "${#plain}" -le "$width" ]; then
    printf '%s' "$text"
    return
  fi
  printf '%s' "$text" | awk -v w="$width" '{
    out=""; vis=0; i=1; n=length($0)
    while (i <= n) {
      c = substr($0, i, 1)
      if (c == "\033") {                    # pass escapes through free
        j = i; while (j <= n && substr($0, j, 1) != "m") j++
        out = out substr($0, i, j - i + 1); i = j + 1; continue
      }
      if (vis >= w - 1) { out = out "…"; break }
      out = out c; vis++; i++
    }
    printf "%s\033[0m", out
  }'
}
ago() {  # ago <seconds> -> compact human age
  local s=$1
  if   [ "$s" -lt 90 ];    then printf '%ds' "$s"
  elif [ "$s" -lt 5400 ];  then printf '%dm' "$((s/60))"
  elif [ "$s" -lt 172800 ];then printf '%dh' "$((s/3600))"
  else printf '%dd' "$((s/86400))"; fi
}
paint() {  # paint <status-word> -> colored, fixed width
  case "$1" in
    SUCCESS|done|PRESENT|free|True) printf '%s%-14s%s' "$G" "$1" "$N" ;;
    WORKING|QUEUED|ACTIVE|pending)  printf '%s%-14s%s' "$Y" "$1" "$N" ;;
    FAILURE|INTERNAL_ERROR|TIMEOUT|CANCELLED|EXPIRED|stalled|HELD)
      printf '%s%-14s%s' "$R" "$1" "$N" ;;
    *) printf '%-14s' "$1" ;;
  esac
}

# ---------------------------------------------------------------- cloud
refresh_cloud() {  # writes atomically into $CACHE; safe to run twice
  mkdir -p "$CACHE"
  # Temp names are per-process: a foreground cold-start fetch and a
  # background refresh must never mv each other's half-written file.
  local t="$$"
  gcloud builds list --project "$PROJECT" --limit 6 \
    --format="value(id,status,substitutions._IMAGE,createTime)" \
    > "$CACHE/builds.$t" 2>/dev/null && mv "$CACHE/builds.$t" "$CACHE/builds"
  rm -f "$CACHE/builds.$t"
  if gsutil -q stat "$LEASE_URI" 2>/dev/null; then
    holder=$(gsutil cat "$LEASE_URI" 2>/dev/null \
      | grep -ao '"run_id":"[^"]*"' | head -1 | cut -d'"' -f4)
    printf 'HELD %s\n' "${holder:-unknown}" > "$CACHE/lease.$t"
  else
    printf 'free\n' > "$CACHE/lease.$t"
  fi
  mv "$CACHE/lease.$t" "$CACHE/lease"
  : > "$CACHE/grids.$t"
  for ledger in $(ls -t "$ROOT"/reports/*-runs/*/executions.txt 2>/dev/null \
                  | head -3); do
    dir=$(dirname "$ledger"); run=$(basename "$dir")
    age=$(( $(date +%s) - $(stat -c %Y "$ledger" 2>/dev/null || date +%s) ))
    cells=$(wc -l < "$ledger" 2>/dev/null | tr -d ' ')
    uri=$(awk 'NF>=5 {print $5; exit}' "$ledger" 2>/dev/null)
    prefix="${uri%/*}"
    # Aggregates land locally beside the ledger, or in GCS beside the
    # cells / one level up when the run used an attempt subdirectory.
    if [ -s "$dir/aggregate-report.json" ] \
      || { [ -n "$prefix" ] && { \
           gsutil -q stat "$prefix/aggregate-report.json" 2>/dev/null \
        || gsutil -q stat "${prefix%/*}/aggregate-report.json" 2>/dev/null; }; }
    then agg=PRESENT; else agg=pending; fi
    # Aggregate present means finished however fresh the ledger looks;
    # only an unaggregated recent ledger is still running.
    if [ "$agg" = PRESENT ]; then tag=done
    elif [ "$age" -lt "$GRID_WINDOW" ]; then tag=ACTIVE
    else tag=stalled; fi
    done_n="?"
    [ -n "$prefix" ] && done_n=$(gsutil ls "$prefix/slate-*.json" 2>/dev/null \
      | wc -l | tr -d ' ')
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$tag" "$run" "$done_n" "$cells" "$agg" "$age" >> "$CACHE/grids.$t"
  done
  mv "$CACHE/grids.$t" "$CACHE/grids"
  date +%s > "$CACHE/stamp"
}

maybe_refresh_cloud() {
  mkdir -p "$CACHE"
  local last=0 pid_file="$CACHE/worker.pid"
  [ -s "$CACHE/stamp" ] && last=$(cat "$CACHE/stamp" 2>/dev/null || echo 0)
  [ -s "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null && return
  if [ $(( $(date +%s) - last )) -ge "$CLOUD_INTERVAL" ]; then
    ( refresh_cloud ) & echo $! > "$pid_file"
  fi
}

# --------------------------------------------------------------- render
render() {
  local now; now=$(date +%s)
  local stamp=0; [ -s "$CACHE/stamp" ] && stamp=$(cat "$CACHE/stamp")
  local cloud_age="never"
  [ "$stamp" -gt 0 ] && cloud_age="$(ago $((now - stamp))) ago"

  # ---- processes (and the exact log each one owns) -------------------
  local procs live_logs="" pid script
  procs=$(ps -eo pid,etime,args --no-headers 2>/dev/null \
    | grep -aE "$CHAIN_RE" | grep -av 'grep -' | grep -av -- '-c source')
  fit "${B}NFL-DFS CHAIN MONITOR${N}  ${D}$(date -u +%H:%M:%SZ) utc · $(date +%H:%M:%S) local · cloud data $cloud_age${N}"
  echo
  echo "${B}CHAINS${N}"
  if [ -z "$procs" ]; then
    echo "  ${D}no chain process running${N}"
  else
    while read -r pid etime rest; do
      script=$(printf '%s' "$rest" | tr ' ' '\n' | grep -m1 '\.sh$')
      [ -z "$script" ] && continue
      local log; log=$(readlink "/proc/$pid/fd/1" 2>/dev/null)
      case "$log" in *.log) live_logs="$live_logs$log
";; *) log="" ;; esac
      local last="" lage=""
      if [ -n "$log" ] && [ -s "$log" ]; then
        last=$(tail -1 "$log" 2>/dev/null)
        lage=$(ago $(( now - $(stat -c %Y "$log") )))
      elif [ -n "$log" ]; then
        last="(no output yet)"
        lage=$(ago $(( now - $(stat -c %Y "$log") )))
      fi
      fit "  ${G}●${N} $(printf '%-38s' "$(basename "$script")") ${D}pid $pid  up $etime${N}"
      echo
      [ -n "$log" ] && { fit "      ${C}$(basename "$log")${N} ${D}[$lage]${N} $last"; echo; }
    done <<< "$procs"
  fi

  # ---- cloud builds --------------------------------------------------
  echo
  echo "${B}CLOUD BUILDS${N} ${D}(cached, $cloud_age)${N}"
  if [ -s "$CACHE/builds" ]; then
    while IFS=$'\t' read -r id status image created; do
      [ -z "$id" ] && continue
      local tag="${image##*:}"
      fit "  $(paint "$status") $(printf '%-34s' "${tag:0:34}") ${D}${id:0:8}${N}"
      echo
    done < <(head -6 "$CACHE/builds")
  else
    echo "  ${D}fetching…${N}"
  fi

  # ---- cell grids ----------------------------------------------------
  echo
  echo "${B}CELL GRIDS${N}"
  if [ -s "$CACHE/grids" ]; then
    while IFS=$'\t' read -r tag run dn cells agg age; do
      [ -z "$tag" ] && continue
      # Run ids share a long prefix and differ at the tail (…-attempt-2),
      # so trim from the left to keep the distinguishing part.
      [ ${#run} -gt 44 ] && run="…${run: -43}"
      fit "  $(paint "$tag") $(printf '%-44s' "$run") ${dn}/${cells} cells  ${D}aggregate $agg · $(ago "$age") old${N}"
      echo
    done < "$CACHE/grids"
  else
    echo "  ${D}fetching…${N}"
  fi

  # ---- lease ---------------------------------------------------------
  echo
  echo "${B}OUTCOME LEASE${N}"
  if [ -s "$CACHE/lease" ]; then
    read -r state holder < "$CACHE/lease"
    if [ "$state" = HELD ]; then
      fit "  $(paint HELD) ${holder}"
    else
      fit "  $(paint free) ${D}no historical-outcome experiment holds it${N}"
    fi
    echo
  else
    echo "  ${D}fetching…${N}"
  fi

  # ---- change feed ---------------------------------------------------
  echo
  echo "${B}RECENT EVENTS${N} ${D}(non-heartbeat lines, newest first)${N}"
  local shown=0 log line age
  for log in $(ls -t "$PANELS"/*.log 2>/dev/null | head -12); do
    [ "$shown" -ge 7 ] && break
    line=$(grep -avE "$HEARTBEAT" "$log" 2>/dev/null | tail -1)
    [ -z "$line" ] && continue
    age=$(( now - $(stat -c %Y "$log" 2>/dev/null || echo "$now") ))
    local mark="${D}·${N}"
    printf '%s' "$live_logs" | grep -qxF "$log" && mark="${G}●${N}"
    case "$line" in
      *ERROR*|*FAILED*|*failed*) line="${R}${line}${N}" ;;
      *COMPLETE*|*FINISHED*|*ACQUIRED*|*SUCCESS*) line="${G}${line}${N}" ;;
    esac
    fit "  $mark $(printf '%-30s' "$(basename "$log")") ${D}$(ago $age)${N}  $line"
    echo
    shown=$((shown + 1))
  done
  [ "$shown" = 0 ] && echo "  ${D}nothing yet${N}"

  # ---- commits -------------------------------------------------------
  echo
  echo "${B}RECENT COMMITS${N}"
  git -C "$ROOT" log --oneline -4 2>/dev/null | while read -r line; do
    fit "  ${D}$line${N}"; echo
  done
}

# ----------------------------------------------------------------- run
if [ "$WATCH" = 0 ]; then
  # One-shot fetches in the foreground when the cache is cold or stale:
  # it must never print an empty or misleadingly old dashboard.
  stale=0; [ -s "$CACHE/stamp" ] \
    && stale=$(( $(date +%s) - $(cat "$CACHE/stamp") )) || stale=$CLOUD_INTERVAL
  [ "$stale" -ge "$CLOUD_INTERVAL" ] && refresh_cloud
  render
  exit 0
fi

cleanup() { tput rmcup 2>/dev/null; tput cnorm 2>/dev/null; echo; exit 0; }
trap cleanup INT TERM
tput smcup 2>/dev/null; tput civis 2>/dev/null
[ -s "$CACHE/builds" ] || { clear; echo "  loading cloud state…"; refresh_cloud; }
while :; do
  maybe_refresh_cloud
  frame=$(render)
  # Repaint from home, clearing each line, then wipe the tail: no flicker
  # and no clear-screen blank between frames.
  printf '\033[H'
  # ANSI-C quoting: sed's replacement must carry a literal ESC, not the
  # four characters \033.
  printf '%s\n' "$frame" | sed $'s/$/\033[K/'
  printf '\033[J'
  printf '%s' "${D}  [q] quit · [r] refresh cloud now · repaint ${INTERVAL}s${N}"
  read -r -N 1 -t "$INTERVAL" key && case "$key" in
    q|Q) cleanup ;;
    r|R) rm -f "$CACHE/stamp" ;;
  esac
done
