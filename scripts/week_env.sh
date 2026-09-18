#!/usr/bin/env bash
# Shared Sunday-path environment for any regular-season week.  Source it, then call `week_env WEEK [GROUP]`.
# Everything week-specific the Sunday scripts need is derived here once; nothing else may hard-code a week.
#
#   source scripts/week_env.sh; week_env 2            # draft group auto-detected from nfl_raw.dk_salaries
#   source scripts/week_env.sh; week_env 2 153200     # explicit draft group
#   export OUT=/home/erich/week1-rehearsal; week_env 1 151307   # overrides must be EXPORTED before the call, never
#                                                             # given as a prefix (bash undoes prefix assignments after a function returns)
#
# Exports: SEASON WEEK WEEKDIR SUNDAY LOCK_UTC LATE_CUTOFF_UTC WATCH_END_UTC GROUP OUT CLONE PROD PROD_PY LAB_PY
#          TOOLS CONTESTS_JSON RUN_SUFFIX EXPECT_SHA LIVE_DIR ENTER_LAYOUT
week_env() {
  local week=${1:?week}; local group=${2:-${GROUP:-}}
  export SEASON=${SEASON:-2026}
  export WEEK=$week
  export WEEKDIR=$(printf '%s-w%02d' "$SEASON" "$WEEK")
  # Week-1 Sunday of the 2026 season is 2026-09-13; regular-season weeks are seven days apart.
  export SUNDAY=$(date -u -d "2026-09-13 + $(( (WEEK - 1) * 7 )) days" +%Y-%m-%d)
  export LOCK_UTC="$SUNDAY 17:00:00+00:00"            # 12:00 CT main-slate lock (DST in force through early November)
  export LATE_CUTOFF_UTC="$SUNDAY 18:30:00+00:00"     # games starting after this are the late-afternoon window
  export WATCH_END_UTC="$SUNDAY 20:25:00+00:00"       # late-inactives watcher exits at 15:25 CT
  export OUT=${OUT:-/home/erich/week${WEEK}-sunday}
  export CLONE=${CLONE:-/home/erich/projects/.nfl2-worktrees/week1-live-center-e7255e9}   # live_week.py, NFL2_LIVE_CENTER=production
  export EXPECT_SHA=${EXPECT_SHA:-e7255e98bf87297452befb61fb508ad4b368b59f}
  export RUN_SUFFIX=${EXPECT_SHA:0:7}
  export PROD=${PROD:-/home/erich/projects/.nfl-predictions-worktrees/week1-audit-adjust-20260912}
  export PROD_PY=${PROD_PY:-/home/erich/projects/nfl-predictions/.venv/bin/python}
  export LAB_PY=${LAB_PY:-/home/erich/projects/nfl2/.venv/bin/python}
  export TOOLS=${TOOLS:-/home/erich/week1-sunday/tools}
  export CONTESTS_JSON=${CONTESTS_JSON:-$OUT/contests.json}
  export LIVE_DIR="$CLONE/results/live/$WEEKDIR"
  # Entry layout (operator decision 2026-09-18, week 2 on): "sequential" gives every contest its OWN block of book
  # ranks, so no lineup is ever entered in two contests; "top" gave every contest ranks 1..N (the Week-1 behaviour).
  # Contest order in contests.json IS the priority order -- the first contest gets the best ranks -- so keep that file
  # sorted by value per entry.  Under "sequential" the book must hold the ENTRY TOTAL, not 90; sunday_build_host.sh
  # derives BOOK_ENTRIES from contests.json and every downstream check (verify_k90, the bundle verifier, the filler)
  # is governed by it.  Set ENTER_LAYOUT=top in the environment to fall back.
  export ENTER_LAYOUT=${ENTER_LAYOUT:-sequential}
  if [[ -z "$group" ]]; then
    group=$(PYTHONPATH="$PROD/src" "$PROD_PY" "$PROD/scripts/find_main_draft_group.py" --season "$SEASON" --sunday "$SUNDAY") || { echo "week_env: could not detect the Sunday-main draft group for $SUNDAY (set GROUP explicitly)" >&2; return 1; }
  fi
  export GROUP=$group
  mkdir -p "$OUT"
  echo "week_env: season $SEASON week $WEEK ($WEEKDIR) sunday $SUNDAY lock $LOCK_UTC group $GROUP out $OUT" >&2
}
