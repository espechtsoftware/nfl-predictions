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
#          TOOLS CONTESTS_JSON RUN_SUFFIX EXPECT_SHA LIVE_DIR ENTER_LAYOUT BOOK_ENTRIES
WEEK_ENV_REPO=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)

# Resolve paths and dates without querying providers or reading contest reservations. Used when printing timers.
week_settings() {
  local week=${1:?week}
  [[ "$week" =~ ^([1-9]|1[0-8])$ ]] || { echo 'week_env: week must be 1..18' >&2; return 2; }
  export SEASON=${SEASON:-2026}
  export WEEK=$week
  [[ "$SEASON" =~ ^[0-9]{4}$ ]] || { echo 'week_env: season must be a four-digit year' >&2; return 2; }
  if [[ -z "${FIRST_SUNDAY:-}" ]]; then
    [[ "$SEASON" == 2026 ]] || { echo 'week_env: set FIRST_SUNDAY for seasons other than 2026' >&2; return 2; }
    FIRST_SUNDAY=2026-09-13
  fi
  WEEKDIR=$(printf '%s-w%02d' "$SEASON" "$WEEK")
  SUNDAY=$(date -u -d "$FIRST_SUNDAY + $(( (WEEK - 1) * 7 )) days" +%Y-%m-%d) || return
  export FIRST_SUNDAY WEEKDIR SUNDAY
  local name spec epoch
  for spec in 'LOCK_UTC 12:00' 'LATE_CUTOFF_UTC 13:30' 'WATCH_END_UTC 15:25' 'AFTER_BUILD_END_UTC 11:50' 'ENTRIES_END_UTC 11:58'; do
    read -r name spec <<< "$spec"
    epoch=$(TZ=America/Chicago date -d "$SUNDAY $spec" +%s) || return
    printf -v "$name" '%s' "$(date -u -d "@$epoch" '+%Y-%m-%d %H:%M:%S+00:00')"
    export "$name"
  done
  export OUT=${OUT:-$HOME/week${WEEK}-sunday}
  # The live revision is a reviewed weekly choice, never inferred from an arbitrary checkout HEAD.
  export CLONE=${CLONE:-${NFL2_LIVE_CLONE:-/home/erich/projects/.nfl2-worktrees/week3-live-center}}
  # Week 3 must retain the reviewed live-game-input repair that Week 2 used.
  # Keep this explicit so an unattended arm cannot silently fall back to the
  # older pre-repair revision; advance it deliberately at the next weekly
  # review.
  # 2026-09-22: moved from 2dc116ce (the Week-2 release) to 69f98a75, which adds "D"
  # to DK_INACTIVE_STATUSES so a Doubtful player is removed before any solve. Week 2
  # entered a Doubtful player in 48 of 97 rows including the Millionaire seat for 0.0.
  # The clone .nfl2-worktrees/week3-live-center is checked out at this commit; if the
  # two ever disagree the runtime check fails closed, which is the point.
  # 2026-09-22 (operator): moved 69f98a75 -> 9b341d77 (nfl2 laptop/max-per-game-sidecars-20260922), which
  # lets --max-per-game ride the paid --emit-a5-sidecars path (every other shadow flag still refused;
  # a cap below 4 is refused). Parent is 69f98a75, so the Doubtful inactive set is unchanged.
  export EXPECT_SHA=${EXPECT_SHA:-${NFL2_EXPECT_SHA:-9b341d77dd34c7e9ba6e82610ba06ccdf6a588ee}}
  # Week-3 construction cap (operator, 2026-09-22): max 4 players per game in every lev and boom
  # solve, QB and DST included. MAX_PER_GAME=0 removes the flag (rollback, no code change).
  export MAX_PER_GAME=${MAX_PER_GAME:-4}
  export CLONE EXPECT_SHA
  export RUN_SUFFIX=${RUN_SUFFIX:-${EXPECT_SHA:0:7}}
  export PROD=${PROD:-$WEEK_ENV_REPO}
  export PROD_PY=${PROD_PY:-/home/erich/projects/nfl-predictions/.venv/bin/python}
  export LAB_PY=${LAB_PY:-/home/erich/projects/nfl2/.venv/bin/python}
  # TOOLS may point to the independently reviewed host bundle until all its helpers are in scripts/. Preflight
  # refuses missing helpers; it never substitutes the old week1_vet_book.py for the current QB-aware vetter.
  export TOOLS=${TOOLS:-$PROD/scripts}
  export CONTESTS_JSON=${CONTESTS_JSON:-$OUT/contests.json}
  export LIVE_DIR="$CLONE/results/live/$WEEKDIR"
  export CHOSEN_FILE=${CHOSEN_FILE:-$OUT/chosen-dose.env}
  export DOSE_FILE=${DOSE_FILE:-$OUT/dose.env}
  # Entry layout (operator decision 2026-09-18, week 2 on): "sequential" gives every contest its OWN block of book
  # ranks, so no lineup is ever entered in two contests; "top" gave every contest ranks 1..N (the Week-1 behaviour).
  # Contest order in contests.json IS the priority order -- the first contest gets the best ranks -- so keep that file
  # sorted by value per entry.  Under "sequential" the book must hold the ENTRY TOTAL, not 90; sunday_build_host.sh
  # derives BOOK_ENTRIES from contests.json and every downstream check (verify_k90, the bundle verifier, the filler)
  # is governed by it.  Set ENTER_LAYOUT=top in the environment to fall back.
  export ENTER_LAYOUT=${ENTER_LAYOUT:-sequential}
}

week_env() {
  local week=${1:?week}; local group=${2:-${GROUP:-}}
  week_settings "$week" || return
  # Book size.  Derived HERE, not in the build script, so the build, the after-build chain, the watchers and the bundle
  # verifier all agree: under "sequential" every entry needs its own lineup, so the book must hold the entry total;
  # under "top" every contest reuses ranks 1..N and 90 is enough.  Never let a consumer fall back to a bare 90 under
  # "sequential" -- that would let a short book past the gate and fail later, confusingly, at the bundle verifier.
  if [[ -z "${BOOK_ENTRIES:-}" ]]; then
    [[ -f "$CONTESTS_JSON" ]] || { echo "week_env: contests file missing: $CONTESTS_JSON (create the reviewed Week-${WEEK} contests.json before arming)" >&2; return 1; }
    BOOK_ENTRIES=$("$PROD_PY" -c "import json,os,sys; c=json.load(open(sys.argv[1])); tot=sum(int(x['entries']) for x in c); print(max(90, tot) if os.environ.get('ENTER_LAYOUT','top')=='sequential' else 90)" "$CONTESTS_JSON") || return
  fi
  export BOOK_ENTRIES
  if [[ -z "$group" ]]; then
    group=$(PYTHONPATH="$PROD/src" "$PROD_PY" "$PROD/scripts/find_main_draft_group.py" --season "$SEASON" --sunday "$SUNDAY") || { echo "week_env: could not detect the Sunday-main draft group for $SUNDAY (set GROUP explicitly)" >&2; return 1; }
  fi
  export GROUP=$group
  mkdir -p "$OUT"
  echo "week_env: season $SEASON week $WEEK ($WEEKDIR) sunday $SUNDAY lock $LOCK_UTC group $GROUP out $OUT" >&2
}
