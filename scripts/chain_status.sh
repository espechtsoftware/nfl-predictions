#!/usr/bin/env bash
set -uo pipefail

# Operator dashboard for every research chain: live processes, active
# chain logs, cell grids, cloud builds, the outcome lease, and a feed of
# what changed. Two modes:
#
#   bash scripts/chain_status.sh            one-shot snapshot (scriptable)
#   bash scripts/chain_status.sh --watch    full-screen live app (q quits)
#   bash scripts/chain_status.sh -w -i 5    live app, 5s repaint
#   bash scripts/chain_status.sh -b latest  follow the newest build's log
#   bash scripts/chain_status.sh -b <id>    follow that build's log
#
# In the live app, keys 1-6 stream the matching build's log in place; q or
# Escape returns to the dashboard.
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
BUILD_LOG=""
while [ $# -gt 0 ]; do
  case "$1" in
    -w|--watch) WATCH=1 ;;
    -i|--interval) INTERVAL=${2:-3}; shift ;;
    -b|--build-log) BUILD_LOG=${2:?build id or "latest"}; shift ;;
    -h|--help)
      sed -n '4,19p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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

# ----------------------------------------------------------- build logs
BUILD_TAIL=400   # log entries kept in view; a full build log is far longer
BUILD_POLL=5     # seconds between Cloud Logging reads while viewing

stream_build() {  # follow one Cloud Build's log until the operator returns
  local id=$1
  [ -z "$id" ] && return
  # Declared separately: bash expands every argument of a single `local`
  # before assigning any of them, so "$id" would be unbound here.
  local out="$CACHE/buildlog.$id" stop="$CACHE/buildlog.$id.stop"
  local pid key rows
  : > "$out"; rm -f "$stop"
  # Sweep snapshots orphaned by an earlier kill; anything an hour old
  # cannot belong to a live viewer.
  find "$CACHE" -maxdepth 1 -name 'buildlog.*' -mmin +60 -delete 2>/dev/null
  (
    # Cloud Build streams step output to Cloud Logging; `builds log
    # --stream` reads only the Cloud Storage copy, which stays empty
    # until the build finishes — so poll Logging directly and rewrite a
    # full snapshot each time (no cursor state, never out of order).
    while [ ! -e "$stop" ]; do
      if gcloud logging read \
          "resource.type=build AND resource.labels.build_id=$id" \
          --project "$PROJECT" --limit "$BUILD_TAIL" --order desc \
          --format='value(textPayload)' 2>/dev/null | tac > "$out.tmp"; then
        mv "$out.tmp" "$out"
      fi
      sleep "$BUILD_POLL"
    done
    rm -f "$out.tmp"
  ) &
  pid=$!
  # A kill during viewing must still stop the poller and drop its files.
  trap 'touch "$stop" 2>/dev/null; kill "$pid" 2>/dev/null;
        rm -f "$out" "$out.tmp" "$stop"; exit 0' INT TERM
  while :; do
    rows=$(( $(tput lines 2>/dev/null || echo 40) - 4 ))
    local state
    state=$(grep -m1 -F "$id" "$CACHE/builds" 2>/dev/null | cut -f2)
    printf '\033[H'
    fit "${B}BUILD LOG${N} ${C}${id:0:8}${N} $(paint "${state:-?}")${D}$(wc -l < "$out" 2>/dev/null | tr -d ' ') lines · polling Cloud Logging every ${BUILD_POLL}s · [q] back${N}"
    printf '\033[K\n\033[K\n'
    tail -n "$rows" "$out" 2>/dev/null | sed $'s/$/\033[K/'
    printf '\033[J'
    read -r -N 1 -t 2 key && case "$key" in
      q|Q|$'\033') break ;;
    esac
  done
  touch "$stop"
  kill "$pid" 2>/dev/null
  wait "$pid" 2>/dev/null
  rm -f "$out" "$out.tmp" "$stop"
  trap - INT TERM
  [ "$WATCH" = 1 ] && trap cleanup INT TERM
  printf '\033[2J'
}

build_id_at() {  # map a 1-based menu index to its cached build id
  [ -s "$CACHE/builds" ] || return 1
  sed -n "${1}p" "$CACHE/builds" | cut -f1
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
  local hint=""
  [ "$WATCH" = 1 ] && hint=" ${D}— press 1-6 to stream a build's log${N}"
  echo "${B}CLOUD BUILDS${N} ${D}(cached, $cloud_age)${N}$hint"
  if [ -s "$CACHE/builds" ]; then
    local idx=0
    while IFS=$'\t' read -r id status image created; do
      [ -z "$id" ] && continue
      idx=$((idx + 1))
      local tag="${image##*:}"
      fit "  ${D}[$idx]${N} $(paint "$status") $(printf '%-34s' "${tag:0:34}") ${D}${id:0:8}${N}"
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
  echo "${B}EVENTS — LIVE CHAINS${N} ${D}(newest non-heartbeat line per running chain)${N}"
  local log line age live_shown=0 past=""
  for log in $(ls -t "$PANELS"/*.log 2>/dev/null | head -12); do
    line=$(grep -avE "$HEARTBEAT" "$log" 2>/dev/null | tail -1)
    [ -z "$line" ] && continue
    age=$(( now - $(stat -c %Y "$log" 2>/dev/null || echo "$now") ))
    case "$line" in
      *ERROR*|*FAILED*|*failed*) line="${R}${line}${N}" ;;
      *COMPLETE*|*FINISHED*|*ACQUIRED*|*SUCCESS*) line="${G}${line}${N}" ;;
    esac
    if printf '%s' "$live_logs" | grep -qxF "$log"; then
      fit "  ${G}●${N} $(printf '%-30s' "$(basename "$log")") ${D}$(ago $age)${N}  $line"
      echo
      live_shown=$((live_shown + 1))
    elif [ ${#past} -lt 1200 ]; then
      # Superseded runs keep their last error forever; they must never be
      # mistaken for something happening now.
      past="$past$(fit "  ${D}·${N} $(printf '%-30s' "$(basename "$log")") ${D}$(ago $age)${N}  ${D}$line${N}")
"
    fi
  done
  [ "$live_shown" = 0 ] \
    && echo "  ${D}no running chain has emitted an event yet${N}"
  if [ -n "$past" ]; then
    echo
    echo "${D}  ── history: finished or superseded runs, not current ──${N}"
    printf '%s' "$past" | head -6
  fi

  # ---- commits -------------------------------------------------------
  echo
  echo "${B}RECENT COMMITS${N}"
  git -C "$ROOT" log --oneline -4 2>/dev/null | while read -r line; do
    fit "  ${D}$line${N}"; echo
  done
}

# ----------------------------------------------------------------- run
if [ -n "$BUILD_LOG" ]; then
  # Direct log follow, no dashboard: usable over a plain pipe or ssh.
  if [ "$BUILD_LOG" = latest ]; then
    BUILD_LOG=$(gcloud builds list --project "$PROJECT" --limit 1 \
      --format='value(id)' 2>/dev/null)
    [ -z "$BUILD_LOG" ] && { echo "no builds found" >&2; exit 2; }
  fi
  if [ -t 1 ]; then
    mkdir -p "$CACHE"
    trap 'printf "\033[?25h\n"; exit 0' INT TERM
    printf '\033[2J'
    stream_build "$BUILD_LOG"
    exit 0
  fi
  # Non-tty: emit the log body once (Cloud Logging holds the step output).
  exec gcloud logging read \
    "resource.type=build AND resource.labels.build_id=$BUILD_LOG" \
    --project "$PROJECT" --limit "${BUILD_TAIL:-400}" --order desc \
    --format='value(textPayload)'
fi

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
  printf '%s' "${D}  [q] quit · [r] refresh cloud · [1-6] stream that build's log · repaint ${INTERVAL}s${N}"
  read -r -N 1 -t "$INTERVAL" key && case "$key" in
    q|Q) cleanup ;;
    r|R) rm -f "$CACHE/stamp" ;;
    [1-6])
      build=$(build_id_at "$key") && [ -n "$build" ] && {
        printf '\033[2J'; stream_build "$build"; }
      ;;
  esac
done
