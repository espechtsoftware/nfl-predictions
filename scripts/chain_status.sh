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
#   bash scripts/chain_status.sh -e latest  follow the newest job execution's log
#   bash scripts/chain_status.sh -e <name>  follow that execution's log
#   bash scripts/chain_status.sh --experiments   list retained experiment results
#   bash scripts/chain_status.sh --result <substr>  pretty-print one result JSON
#   bash scripts/chain_status.sh --baseline    print the canonical baseline
#
# Live-app keys: 1-6 stream a build's log; a-h stream a job execution's
# log (the experiment cells themselves); x opens the experiments browser
# over the retained result JSONs in reports/*-runs/ (every score-affecting
# run commits its aggregate there — the browser is a review tool for past
# experiments); q or Escape returns.
#
# Everything is derived at run time — nothing is hardcoded to a specific
# experiment. Local state (processes, logs, ledgers, git) is cheap and
# repaints every interval; cloud state (gcloud/gsutil) is refreshed by a
# background worker at most every CLOUD_INTERVAL seconds and rendered
# from cache with its age shown, so the UI never blocks on the network
# and the API is never hammered.

PROJECT=${NFL_DFS_PROJECT:-nfl-predictions-503414}
REGION=${NFL_DFS_REGION:-us-central1}
ROOT=$(cd "$(dirname "$0")/.." && pwd)
PANELS=${NFL_DFS_PANELS_DIR:-"$HOME/nfl-panels"}
CACHE=${NFL_DFS_CHAIN_CACHE_DIR:-"${TMPDIR:-/tmp}/chain-status-$(id -u)"}
LEASE_URI=${NFL_DFS_HISTORICAL_LEASE_URI:-gs://nfl-predictions-503414-raw/research-governance/historical-outcome-active-v1.json}
CLOUD_INTERVAL=${NFL_DFS_CHAIN_CLOUD_INTERVAL:-60}
if [ -n "${NFL_DFS_PYTHON:-}" ]; then
  PYTHON=$NFL_DFS_PYTHON
elif [ -x "$ROOT/.venv/bin/python" ]; then
  PYTHON="$ROOT/.venv/bin/python"
else
  PYTHON=python3
fi
GRID_WINDOW=$((12 * 3600))
HEARTBEAT='status=WORKING|status=QUEUED|state=Unknown|WAITS_FOR'
CHAIN_RE='watch_[a-z0-9_]+\.sh|drive_[a-z0-9_]+\.sh|repair_[a-z0-9_]+\.sh'
CHAIN_RE="$CHAIN_RE"'|tally_[a-z_]+\.sh|cloud_[a-z0-9_]+\.sh'

WATCH=0
INTERVAL=3
BUILD_LOG=""
EXEC_LOG=""
LIST_EXPERIMENTS=0
RESULT_QUERY=""
while [ $# -gt 0 ]; do
  case "$1" in
    -w|--watch) WATCH=1 ;;
    -i|--interval) INTERVAL=${2:-3}; shift ;;
    -b|--build-log) BUILD_LOG=${2:?build id or "latest"}; shift ;;
    -e|--exec-log) EXEC_LOG=${2:?execution name or "latest"}; shift ;;
    --experiments) LIST_EXPERIMENTS=1 ;;
    --baseline)
      exec "$PYTHON" -m json.tool "$ROOT/reports/current-baseline.json" ;;
    --result) RESULT_QUERY=${2:?run-id substring}; shift ;;
    -h|--help)
      sed -n '4,26p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
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
    WORKING|QUEUED|ACTIVE|pending|running)  printf '%s%-14s%s' "$Y" "$1" "$N" ;;
    FAILURE|FAILED|INTERNAL_ERROR|TIMEOUT|CANCELLED|EXPIRED|stalled|HELD)
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
  if lease_state=$("$PYTHON" - "$PROJECT" "$LEASE_URI" 2>/dev/null <<'PYL'
import json
import sys

from google.api_core.exceptions import NotFound
from google.cloud import storage

project, uri = sys.argv[1:]
bucket_name, object_name = uri[5:].split("/", 1)
blob = storage.Client(project=project).bucket(bucket_name).blob(object_name)
try:
    blob.reload()
except NotFound:
    print("free")
    raise SystemExit(0)
body = json.loads(blob.download_as_bytes(if_generation_match=blob.generation))
holder = body.get("run_id")
if not isinstance(holder, str) or not holder:
    raise SystemExit("lease run_id differs")
print(f"HELD {holder}")
PYL
  ); then
    printf '%s\n' "$lease_state" > "$CACHE/lease.$t"
    mv "$CACHE/lease.$t" "$CACHE/lease"
  else
    rm -f "$CACHE/lease.$t"
    [ -s "$CACHE/lease" ] || printf 'UNKNOWN lease-query-failed\n' > "$CACHE/lease"
  fi
  if gcloud run jobs executions list --project "$PROJECT" --region "$REGION" \
      --limit 8 --sort-by "~metadata.creationTimestamp" --format=json \
      > "$CACHE/execs-raw.$t" 2>/dev/null \
    && "$PYTHON" - "$CACHE/execs-raw.$t" > "$CACHE/execs.$t" <<'PYE'
import json
import sys

rows = json.load(open(sys.argv[1], encoding="utf-8"))
for row in rows:
    conditions = [
        item for item in row.get("status", {}).get("conditions", [])
        if item.get("type") == "Completed"
    ]
    state = conditions[0].get("status", "Unknown") if len(conditions) == 1 else "Unknown"
    metadata = row.get("metadata", {})
    status = row.get("status", {})
    print("\t".join((
        str(metadata.get("name", "")), str(state),
        str(metadata.get("creationTimestamp", "")),
        str(status.get("completionTime", "")),
    )))
PYE
  then
    mv "$CACHE/execs.$t" "$CACHE/execs"
  fi
  rm -f "$CACHE/execs.$t" "$CACHE/execs-raw.$t"
  : > "$CACHE/grids.$t"
  : > "$CACHE/exec-labels.$t"
  while IFS= read -r ledger; do
    [ -n "$ledger" ] || continue
    dir=$(dirname "$ledger"); run=$(basename "$dir")
    case "$run" in
      smoke|support) run="$(basename "$(dirname "$dir")")/$run" ;;
    esac
    age=$(( $(date +%s) - $(stat -c %Y "$ledger" 2>/dev/null || date +%s) ))
    cells=$(wc -l < "$ledger" 2>/dev/null | tr -d ' ')
    uri=$(awk 'NF>=5 {print $5; exit} NF==3 {print $3; exit}' "$ledger" 2>/dev/null)
    execution=$(awk 'NF==3 {print $2; exit}' "$ledger" 2>/dev/null)
    case "$uri" in
      */preflight/real-artifact-smoke.json) phase="A7 smoke" ;;
      */preflight/support-census.json) phase="A7 support" ;;
      */a7-select-ladder-runs/*/result.json) phase="A7 historical" ;;
      *) phase="" ;;
    esac
    [ -z "$execution" ] || [ -z "$phase" ] || \
      printf '%s\t%s\n' "$execution" "$phase" >> "$CACHE/exec-labels.$t"
    prefix="${uri%/*}"
    # Aggregates land locally beside the ledger, or in GCS beside the
    # cells / one level up when the run used an attempt subdirectory.
    if { [ -s "$dir/finish.sha256" ] && [ -s "$dir/completion.txt" ]; } \
      || [ -s "$dir/aggregate-report.json" ] \
      || { [ -n "$prefix" ] && { \
           gsutil -q stat "$prefix/aggregate-report.json" 2>/dev/null \
        || gsutil -q stat "${prefix%/*}/aggregate-report.json" 2>/dev/null; }; }
    then agg=PRESENT; else agg=pending; fi
    execution_state=""
    if [ -n "$execution" ] && [ -s "$CACHE/execs" ]; then
      execution_state=$(awk -F '\t' -v target="$execution" \
        '$1 == target {print $2; exit}' "$CACHE/execs")
    fi
    # A terminal cloud failure takes precedence over ledger age. Aggregate
    # present means finished however fresh the ledger looks; only a recent,
    # nonterminal ledger is still active.
    if [ "$execution_state" = False ]; then tag=FAILED
    elif [ "$agg" = PRESENT ]; then tag=done
    elif [ "$age" -lt "$GRID_WINDOW" ]; then tag=ACTIVE
    else tag=stalled; fi
    done_n="?"
    if [ "$(awk 'NR==1 {print NF}' "$ledger" 2>/dev/null)" = 3 ]; then
      if [ "$agg" = PRESENT ]; then done_n=1
      elif [ -n "$uri" ] && gsutil -q stat "$uri" 2>/dev/null; then done_n=1
      elif [ "$execution_state" = False ]; then done_n=0
      fi
    elif [ -n "$prefix" ]; then
      done_n=$(gsutil ls "$prefix/slate-*.json" 2>/dev/null | wc -l | tr -d ' ')
    fi
    printf '%s\t%s\t%s\t%s\t%s\t%s\n' \
      "$tag" "$run" "$done_n" "$cells" "$agg" "$age" >> "$CACHE/grids.$t"
  done < <(
    find "$ROOT/reports" -type f -name executions.txt -path '*-runs/*' \
      -printf '%T@\t%p\n' 2>/dev/null | sort -nr | head -3 | cut -f2-
  )
  mv "$CACHE/grids.$t" "$CACHE/grids"
  mv "$CACHE/exec-labels.$t" "$CACHE/exec-labels"
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

stream_gcloud_log() {  # follow one Cloud Logging filter until q/Escape
  local title=$1 label=$2 filter=$3
  [ -z "$filter" ] && return
  # Declared separately: bash expands every argument of a single `local`
  # before assigning any of them, so "$label" would be unbound here.
  local out="$CACHE/viewlog.$label" stop="$CACHE/viewlog.$label.stop"
  local pid key rows
  : > "$out"; rm -f "$stop"
  # Sweep snapshots orphaned by an earlier kill; anything an hour old
  # cannot belong to a live viewer.
  find "$CACHE" -maxdepth 1 -name 'viewlog.*' -mmin +60 -delete 2>/dev/null
  (
    # Both Cloud Build steps and Cloud Run job cells stream to Cloud
    # Logging; poll it and rewrite a full snapshot each time (no cursor
    # state, never out of order).
    while [ ! -e "$stop" ]; do
      if gcloud logging read "$filter" \
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
    printf '\033[H'
    fit "${B}${title}${N} ${C}${label}${N}  ${D}$(wc -l < "$out" 2>/dev/null | tr -d ' ') lines · polling Cloud Logging every ${BUILD_POLL}s · [q] back${N}"
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

stream_build() {
  stream_gcloud_log "BUILD LOG" "${1:0:8}" \
    "resource.type=build AND resource.labels.build_id=$1"
}

stream_execution() {
  stream_gcloud_log "EXECUTION LOG" "$1" \
    "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$1\""
}

build_id_at() {  # map a 1-based menu index to its cached build id
  [ -s "$CACHE/builds" ] || return 1
  sed -n "${1}p" "$CACHE/builds" | cut -f1
}

exec_at() {  # map a letter a-h to its cached execution name
  [ -s "$CACHE/execs" ] || return 1
  local idx
  idx=$(( $(printf '%d' "'$1") - 96 ))   # a=1 … h=8
  sed -n "${idx}p" "$CACHE/execs" | cut -f1
}

# ---------------------------------------------------- experiments browser
EXPERIMENTS_HELPER='
import json, sys, time
from pathlib import Path
root = Path(sys.argv[1]) / "reports"
rows = []
for path in root.glob("*-runs/**/*.json"):
    name = path.name
    if not (name in ("aggregate-report.json", "report.json")
            or name.endswith("-report.json") or name.endswith("-census.json")):
        continue
    try:
        r = json.loads(path.read_text())
    except Exception:
        continue
    if not isinstance(r, dict):
        continue
    label = r.get("run_id") or r.get("protocol_id") or path.parent.name
    # Some aggregates nest their headline numbers one level down.
    nested = r.get("aggregate")
    if isinstance(nested, dict):
        r = {**nested, **r}
    bits = []
    for key, fmt in (
        ("mean_paired_delta_s", "dS={:+.2f}"), ("mean_paired_delta_c", "dC={:+.2f}"),
        ("treatment_better_s", "S better={}"), ("treatment_better", "better={}"),
        ("verdict", "{}"), ("median_percentile", "median pct={}"),
        ("n_exact_legal_optimum", "exact optima={}"),
        ("required_raw_field_size", "req field={:.0f}"),
        ("fraction_draws_changed_mean", "draws changed={:.4f}"),
        ("n_winner_production_valid", "prod-legal winners={}"),
    ):
        v = r.get(key)
        if v is not None:
            try: bits.append(fmt.format(v))
            except Exception: bits.append(f"{key}={v}")
    gate = r.get("gate") or {}
    if isinstance(gate, dict) and gate.get("disposition"):
        bits.append(str(gate["disposition"]))
    if r.get("uses_realized_outcomes"): bits.append("outcome-aware")
    rows.append((path.stat().st_mtime, str(label)[:52],
                 " ".join(bits)[:90] or "(no headline keys)",
                 str(path.relative_to(root.parent))))
rows.sort(reverse=True)
for m, label, headline, rel in rows[:40]:
    stamp = time.strftime("%m-%d %H:%M", time.localtime(m))
    print(f"{stamp}\t{label}\t{headline}\t{rel}")
'

list_experiments() {
  "$PYTHON" -c "$EXPERIMENTS_HELPER" "$ROOT" 2>/dev/null
}

view_json() {  # pretty-print one result through a pager, TUI-safely
  local file=$1
  [ -f "$file" ] || return
  if [ "$WATCH" = 1 ]; then tput rmcup 2>/dev/null; tput cnorm 2>/dev/null; fi
  "$PYTHON" -m json.tool "$file" | less -R
  if [ "$WATCH" = 1 ]; then tput smcup 2>/dev/null; tput civis 2>/dev/null; fi
  printf '\033[2J'
}

experiments_browser() {  # interactive list -> pager on the chosen result
  local table key n line file
  table=$(list_experiments)
  [ -z "$table" ] && { printf '\033[2J\033[H  no retained results found\n'; sleep 2; return; }
  while :; do
    printf '\033[H'
    fit "${B}EXPERIMENTS${N} ${D}retained result JSONs in reports/*-runs — newest first · [1-9] view · [q] back${N}"
    printf '\033[K\n\033[K\n'
    n=0
    while IFS=$'\t' read -r stamp label headline rel; do
      n=$((n + 1)); [ "$n" -gt 9 ] && break
      fit "  ${D}[$n]${N} ${D}$stamp${N} $(printf '%-52s' "$label") ${G}$headline${N}"
      printf '\033[K\n'
      fit "        ${D}$rel${N}"
      printf '\033[K\n'
    done <<< "$table"
    printf '\033[J'
    read -r -N 1 -t 30 key || continue
    case "$key" in
      q|Q|$'\033') printf '\033[2J'; return ;;
      [1-9])
        line=$(sed -n "${key}p" <<< "$table")
        file="$ROOT/$(printf '%s' "$line" | cut -f4)"
        view_json "$file"
        ;;
    esac
  done
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
    local active_build="" active_execution=""
    if [ -s "$CACHE/builds" ]; then
      active_build=$(awk -F '\t' '$2 == "WORKING" || $2 == "QUEUED" {
        image=$3; sub(/^.*:/, "", image)
        printf "%s (%s)", image, substr($1, 1, 8); exit
      }' "$CACHE/builds")
    fi
    if [ -n "$active_build" ]; then
      fit "  ${Y}●${N} cloud build active: $active_build ${D}— see CLOUD BUILDS below${N}"
      echo
    elif [ -s "$CACHE/execs" ]; then
      active_execution=$(awk -F '\t' '$2 != "True" && $2 != "False" {
        print $1; exit
      }' "$CACHE/execs")
      if [ -n "$active_execution" ]; then
        fit "  ${Y}●${N} cloud execution active: $active_execution ${D}— see JOB EXECUTIONS below${N}"
        echo
      else
        echo "  ${D}no local chain process or active cloud work${N}"
      fi
    else
      echo "  ${D}no local chain process or active cloud work${N}"
    fi
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

  # ---- baseline --------------------------------------------------------
  echo
  echo "${B}BASELINE${N} ${D}(reports/current-baseline.json)${N}"
  if [ -f "$ROOT/reports/current-baseline.json" ]; then
    "$PYTHON" - "$ROOT/reports/current-baseline.json" <<'PYB' 2>/dev/null | while read -r line; do fit "  $line"; echo; done
import json, sys
b = json.load(open(sys.argv[1]))
mb, ac, pc = b["money_book"], b["arm_comparator_book"], b["pool_ceiling"]
t = lambda d: "/".join(str(d[k]) for k in ("187","194","200","210","220","230","240"))
print(f"money book  {mb['mean_weekly_best']:.2f} mean weekly best "
      f"({mb['slates']} slates) · {t(mb['at_or_above'])} at 187-240 "
      f"· target {b['target']['value']:.0f}")
print(f"comparator  {ac['mean_weekly_best']:.2f} ({ac['slates']}) · "
      f"pool C {pc['control_mean']:.2f} (boom-deep {pc['boom_deep_treatment_mean']:.2f}) · "
      f"C-S gap {b['gaps']['C_minus_S']:.2f} · as of {b['as_of']}")
PYB
  else
    echo "  ${D}reports/current-baseline.json missing${N}"
  fi

  # ---- job executions --------------------------------------------------
  echo
  local ehint=""
  [ "$WATCH" = 1 ] && ehint=" ${D}— press a-h to stream that execution's log${N}"
  echo "${B}JOB EXECUTIONS${N} ${D}(cached, $cloud_age)${N}$ehint"
  if [ -s "$CACHE/execs" ]; then
    local letter_ix=0 letters="abcdefgh"
    while IFS=$'\t' read -r name state created completed; do
      [ -z "$name" ] && continue
      local word phase_label="" display_name
      case "$state" in
        True) word=done ;;
        False) word=FAILED ;;
        *) word=running ;;
      esac
      [ ! -s "$CACHE/exec-labels" ] || \
        phase_label=$(awk -F '\t' -v execution="$name" \
          '$1 == execution {print $2; exit}' "$CACHE/exec-labels")
      display_name=$name
      [ -z "$phase_label" ] || display_name="$phase_label · $name"
      local lt="${letters:$letter_ix:1}"; letter_ix=$((letter_ix + 1))
      fit "  ${D}[$lt]${N} $(paint "$word") $(printf '%-46s' "${display_name:0:46}") ${D}${created:5:11}${N}"
      echo
    done < <(head -8 "$CACHE/execs")
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
    elif [ "$state" = UNKNOWN ]; then
      fit "  $(paint UNKNOWN) ${R}${holder:-lease-query-failed}; last state unavailable${N}"
    else
      fit "  $(paint free) ${D}no historical-outcome experiment holds it${N}"
    fi
    echo
  else
    echo "  ${D}fetching…${N}"
  fi

  # ---- change feed ---------------------------------------------------
  echo
  echo "${B}EVENTS — LOCAL CHAIN LOGS${N} ${D}(newest non-heartbeat line per local watcher)${N}"
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
  if [ "$live_shown" = 0 ]; then
    if { [ -s "$CACHE/builds" ] && awk -F '\t' \
          '$2 == "WORKING" || $2 == "QUEUED" {found=1} END {exit !found}' \
          "$CACHE/builds"; } || { [ -s "$CACHE/execs" ] && awk -F '\t' \
          '$2 != "True" && $2 != "False" {found=1} END {exit !found}' \
          "$CACHE/execs"; }; then
      echo "  ${D}no local watcher yet; active cloud progress is shown above${N}"
    else
      echo "  ${D}no local watcher has emitted an event yet${N}"
    fi
  fi
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
if [ "$LIST_EXPERIMENTS" = 1 ]; then
  list_experiments | while IFS=$'\t' read -r stamp label headline rel; do
    printf '%s  %-52s %s\n        %s\n' "$stamp" "$label" "$headline" "$rel"
  done
  exit 0
fi

if [ -n "$RESULT_QUERY" ]; then
  match=$(list_experiments | awk -F'\t' -v q="$RESULT_QUERY" \
    'index($2, q) || index($4, q) {print $4; exit}')
  [ -z "$match" ] && { echo "no retained result matches: $RESULT_QUERY" >&2; exit 2; }
  exec "$PYTHON" -m json.tool "$ROOT/$match"
fi

if [ -n "$EXEC_LOG" ]; then
  if [ "$EXEC_LOG" = latest ]; then
    EXEC_LOG=$(gcloud run jobs executions list --project "$PROJECT" \
      --region "$REGION" --limit 1 --sort-by "~metadata.creationTimestamp" \
      --format='value(metadata.name)' 2>/dev/null)
    [ -z "$EXEC_LOG" ] && { echo "no executions found" >&2; exit 2; }
  fi
  if [ -t 1 ]; then
    mkdir -p "$CACHE"
    trap 'printf "\033[?25h\n"; exit 0' INT TERM
    printf '\033[2J'
    stream_execution "$EXEC_LOG"
    exit 0
  fi
  gcloud logging read \
    "resource.type=\"cloud_run_job\" AND labels.\"run.googleapis.com/execution_name\"=\"$EXEC_LOG\"" \
    --project "$PROJECT" --limit "${BUILD_TAIL:-400}" --order desc \
    --format='value(textPayload)' | tac
  exit 0
fi

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
# The alternate screen has NO terminal scrollback by design, so the app
# scrolls its own frame: OFFSET is the first visible line of the render.
OFFSET=0
while :; do
  maybe_refresh_cloud
  frame=$(render)
  total=$(printf '%s\n' "$frame" | wc -l)
  view_rows=$(( $(tput lines 2>/dev/null || echo 40) - 1 ))
  max_offset=$(( total > view_rows ? total - view_rows : 0 ))
  [ "$OFFSET" -gt "$max_offset" ] && OFFSET=$max_offset
  [ "$OFFSET" -lt 0 ] && OFFSET=0
  # Repaint from home, clearing each line, then wipe the tail: no flicker
  # and no clear-screen blank between frames.
  printf '\033[H'
  # ANSI-C quoting: sed's replacement must carry a literal ESC, not the
  # four characters \033.
  printf '%s\n' "$frame" \
    | sed -n "$((OFFSET + 1)),$((OFFSET + view_rows))p" \
    | sed $'s/$/\033[K/'
  printf '\033[J'
  scroll_note=""
  [ "$max_offset" -gt 0 ] && scroll_note="↑↓/jk scroll · [0]top · $((OFFSET + 1))-$((OFFSET + view_rows > total ? total : OFFSET + view_rows))/${total} · "
  printf '%s' "${D}  [q]uit · [r]efresh · ${scroll_note}[1-6] build · [a-h] execution · [x] experiments · ${INTERVAL}s${N}"
  if read -r -N 1 -t "$INTERVAL" key; then
    # Arrow keys arrive as ESC [ A/B; consume the tail so a bare Escape
    # (no sequence) still falls through harmlessly.
    if [ "$key" = $'\033' ]; then
      read -r -N 2 -t 0.02 seq || seq=""
      case "$seq" in
        '[A') key=__up ;;
        '[B') key=__dn ;;
        '[5') read -r -N 1 -t 0.02 _; key=__pgu ;;   # PgUp: ESC [ 5 ~
        '[6') read -r -N 1 -t 0.02 _; key=__pgd ;;   # PgDn: ESC [ 6 ~
        *) key="" ;;
      esac
    fi
    # j/k mirror the arrows; d-h stay reserved for execution selection.
    case "$key" in
      q|Q) cleanup ;;
      r|R) rm -f "$CACHE/stamp" ;;
      j|__dn) OFFSET=$((OFFSET + 2)) ;;
      k|__up) OFFSET=$((OFFSET - 2)) ;;
      __pgd|' ') OFFSET=$((OFFSET + view_rows / 2)) ;;
      __pgu) OFFSET=$((OFFSET - view_rows / 2)) ;;
      G) OFFSET=$max_offset ;;
      0) OFFSET=0 ;;
      x|X) printf '\033[2J'; experiments_browser ;;
      [1-6])
        build=$(build_id_at "$key") && [ -n "$build" ] && {
          printf '\033[2J'; stream_build "$build"; }
        ;;
      [a-h])
        execution=$(exec_at "$key") && [ -n "$execution" ] && {
          printf '\033[2J'; stream_execution "$execution"; }
        ;;
    esac
  fi
done
