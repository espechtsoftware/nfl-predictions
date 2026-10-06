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
  SATURDAY=$(date -u -d "$SUNDAY - 1 day" +%Y-%m-%d) || return
  export FIRST_SUNDAY WEEKDIR SUNDAY SATURDAY
  # The week's publication window (sweep 2026-09-29 items 6/7): a run dir built before Saturday 00:00 CT (Wednesday's smoke, a
  # Thursday paper build) is never published and never the union's supply. ISO UTC; consumers compare it by parsed content.
  export WEEK_WINDOW_START_UTC=${WEEK_WINDOW_START_UTC:-$(date -u -d "@$(TZ=America/Chicago date -d "$SATURDAY 00:00" +%s)" +%Y-%m-%dT%H:%M:%S)}
  local name spec epoch
  # ENTRIES_END (Week 4): the DK-entries watcher now runs to 15:20 CT so the afternoon swaps (R4 ~13:55, the satellite
  # late swap ~14:40) get a refilled export like the morning ones; it used to stop at 11:58 CT (a hard-coded 16:58Z).
  for spec in 'LOCK_UTC 12:00' 'LATE_CUTOFF_UTC 13:30' 'WATCH_END_UTC 15:25' 'AFTER_BUILD_END_UTC 11:50' "ENTRIES_END_UTC ${ENTRIES_END_CT:-15:20}"; do
    read -r name spec <<< "$spec"
    epoch=$(TZ=America/Chicago date -d "$SUNDAY $spec" +%s) || return
    printf -v "$name" '%s' "$(date -u -d "@$epoch" '+%Y-%m-%d %H:%M:%S+00:00')"
    export "$name"
  done
  export OUT=${OUT:-$HOME/week${WEEK}-sunday}
  # The live revision is a reviewed weekly choice, never inferred from an arbitrary checkout HEAD.
  export CLONE=${CLONE:-${NFL2_LIVE_CLONE:-/home/erich/projects/.nfl2-worktrees/week4-live-center}}
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
  # 2026-09-25 (operator: "why can't it be this week"): moved 9b341d77 -> 65305f5a (nfl2 laptop/flex-latest-kickoff-20260924,
  # parent 9b341d77, one commit): LIVE_FLEX_LATEST=1 puts each lineup's latest-starting surplus RB/WR/TE in FLEX for late
  # swaps. Default off = byte-identical to 9b341d77; lineups unchanged, only slot labels move.
  # 2026-09-29 (Week 4, the laptop host): moved 65305f5a -> 826d8de6 (nfl2 laptop/two-track-selector-20260927): the mean
  # selector and mean tail sleeve, the class sleeve, --min-proj, the DST cap, the late-swap policy (54dd512), plus the DK->
  # nflverse team alias (LAR->LA; Week 4's LA@PHI refused every build at 54dd512). Descends from 65305f5a and 2dc116ce
  # (merge-base --is-ancestor); the clone .nfl2-worktrees/week4-live-center is checked out at it.
  export EXPECT_SHA=${EXPECT_SHA:-${NFL2_EXPECT_SHA:-32cdb6112beb68ce5171423a8e12bf684256bbf2}}
  # Week 3 on (operator, 2026-09-25): the FLEX slot holds the latest starter. LIVE_FLEX_LATEST=0 is the rollback.
  export LIVE_FLEX_LATEST=${LIVE_FLEX_LATEST:-1}
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
  export ENTER_LAYOUT=${ENTER_LAYOUT:-head}        # reviewer 2026-09-28: the head layout deals the deep-line contests first (set_contest_tracks --rule line)
  # 2026-09-24: "head" (operator, Week 3) opens every contest with the book's best rows and fills the rest with lineups
  # used nowhere else; the rule is src/nfl_dfs/inference/enter_layout.py. ENTER_ORDER=fewest-low orders the rows by
  # predicted LOW-owned count (external review 2026-09-24 §5.3) from OWNERSHIP_SETS, the Saturday sets file
  # (scripts/ownership_sets.py sets). Defaults keep the pre-2026-09-24 behaviour.
  export ENTER_ORDER=${ENTER_ORDER:-greedy}
  export OWNERSHIP_SETS=${OWNERSHIP_SETS:-$OUT/ownership_sets.csv}
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
    # The book must hold every distinct row the layout reads (sequential: the entry total; top: the widest contest;
    # head: the four head rows plus every unique row), and never fewer than 90.
    # Two tracks (operator 2026-09-27): BOOK_ENTRIES is the MEAN-track row count the builder receives as --entries; the
    # tail sleeve (Millionaire seats, "track": "tail") is TAIL_SLEEVE rows appended after them (--tail-sleeve).
    BOOK_ENTRIES=$(PYTHONPATH="$PROD/src" "$PROD_PY" -c "import json,sys; from nfl_dfs.inference.enter_layout import rows_needed, sleeve_size; c=json.load(open(sys.argv[1])); print(max(1, rows_needed(c, sys.argv[2]) - sleeve_size(c, sys.argv[2])))" "$CONTESTS_JSON" "${ENTER_LAYOUT:-sequential}") || return 1
  fi
  export BOOK_ENTRIES
  if [[ -z "${TAIL_SLEEVE:-}" ]]; then
    TAIL_SLEEVE=$(PYTHONPATH="$PROD/src" "$PROD_PY" -c "import json,sys; from nfl_dfs.inference.enter_layout import sleeve_size; print(sleeve_size(json.load(open(sys.argv[1])), sys.argv[2]))" "$CONTESTS_JSON" "${ENTER_LAYOUT:-sequential}") || return 1
  fi
  export TAIL_SLEEVE
  # The live selector. dual_emax is the incumbent (byte-identical default); "mean" is the two-track satellite selector,
  # which the pinned lab commit must support (the arming preflight and the build audit check the receipt).
  export LIVE_SELECTOR=${LIVE_SELECTOR:-mean} TAIL_LINE=${TAIL_LINE:-210}   # reviewer 2026-09-28 10:30: the mean selector for every contest (dual_emax retired; class withdrawn)
  # Q4b (operator 2026-09-27, fail loudly / no fallbacks): players projected below LIVE_MIN_PROJ leave the universe before
  # generation, so no candidate holds a non-player and none is valued at his upside; the build audit refuses the pool
  # otherwise. Empty = flag omitted (the pre-Q4b lab pin does not know it; the arming preflight checks support).
  export LIVE_MIN_PROJ=${LIVE_MIN_PROJ-1.0}
  # Operator decisions 2026-09-28 for the mean track: ownership tilt (0.1 x summed pre-lock predicted ownership from the
  # Saturday sets file) and a 25% cap on any one DST. Empty = flag omitted. MEAN_OWN_SOURCE defaults to OWNERSHIP_SETS.
  export MEAN_OWN_TILT=${MEAN_OWN_TILT-0} MEAN_DST_CAP=${MEAN_DST_CAP-0.25}   # tilt OFF (2026-09-28 05:40): the 156.8 used realized ownership; pre-lock sets lose 3.3/row
  export MEAN_OWN_SOURCE=${MEAN_OWN_SOURCE:-${OWNERSHIP_SETS:-}}
  # T-70 rules (operator decision 2, 2026-09-28). The layout half runs on this host (ENTER_FLAG_LATE_Q_ONLY: a
  # Questionable player flags a row only if his game starts after the lock). The projection half (T70_ACTIVE_Q,
  # T70_VACATED_BUMP) runs in the project-slate job executed after the 10:30 inactives with these values.
  export ENTER_FLAG_LATE_Q_ONLY=${ENTER_FLAG_LATE_Q_ONLY-1} T70_ACTIVE_Q=${T70_ACTIVE_Q-1} T70_VACATED_BUMP=${T70_VACATED_BUMP-1}
  # Tail-track selector (operator decision 1, 2026-09-28): the field-fitted class model (JSON + .sha256, refit each
  # Monday by the laptop's fit_field_class_model.py). With TAIL_SLEEVE > 0 the chain passes
  # --tail-sleeve-selector "$TAIL_SLEEVE_SELECTOR" and, for class, --class-model "$CLASS_MODEL" (must exist: no fallback here;
  # the lab falls back to EMAX only when the class path fails its own checks, and prints it).
  export TAIL_SLEEVE_SELECTOR=${TAIL_SLEEVE_SELECTOR-mean} CLASS_MODEL=${CLASS_MODEL:-$OUT/class_model.json}   # class withdrawn 10:30; mean = the only sleeve selector allowed if a week declares tail contests
  # Class sleeve (reviewer item 2, 2026-09-28): every Nth boom visit is solved under the field's 193+ shape
  # (--class-sleeve-every N; lab dd0ce98, needs CLASS_MODEL). 0 = flag omitted. The Wednesday cutover sets 2.
  export CLASS_SLEEVE_EVERY=${CLASS_SLEEVE_EVERY-2}
  # The T-70 union (operator 2026-09-28: authorized; repairs the lev-0 supply regression). UNION_SATURDAY_RUN = a Saturday
  # run dir, or auto (the newest UNION_SAT_DOSE run in LIVE_DIR built before the T-70 run); empty = no union. UNION_PMO = N
  # plain-mean-optimizer rows solved on the T-70 frame into the same union (0 = none; set only if L13 supports R5).
  # UNION_SAT_DOSE is an ORDERED list (operator 2026-10-01, cracks audit B): the Saturday D12800 supply, else the Saturday
  # D6400 (which must therefore run: SKIP_UNITS must not hold d6400sat). The union says so loudly when it falls back.
  export UNION_SATURDAY_RUN=${UNION_SATURDAY_RUN-} UNION_SAT_DOSE=${UNION_SAT_DOSE:-2560/10240,1280/5120} UNION_PMO=${UNION_PMO-0} UNION_PMO_CAP=${UNION_PMO_CAP:-0.5}
  # The main-track book's form (operator 2026-09-28 14:05, L13 R5): pmo_x50 = K capped plain-mean-optimizer rows solved on
  # the build's frame (ENTERS Week 4); mean = the union pool's top-K by projected sum (the Monday paper arm). The sleeve is
  # the union's mean selection either way. Needs UNION_SATURDAY_RUN (the union step runs the main).
  export UNION_MAIN=${UNION_MAIN:-pmo_x50}   # Week 4 arms UNION_SATURDAY_RUN=auto; UNION_PMO > 0 only if L13's R5 supports it
  # Fantasy Points' projections in the union's selection (operator 2026-10-05); empty = ours. `fp` needs the union
  # (UNION_SATURDAY_RUN). Armed only with the operator's yes.
  export UNION_PROJ_SOURCE=${UNION_PROJ_SOURCE:-}
  # With UNION_MAIN=mix, which study-18 portfolio: mix (four cells) or ws (the whole-book WS shape that PASSED). NO
  # default (reviewer 10-05): a missed line must never silently arm the other arm; check_week_runtime requires it.
  export UNION_MIX_PORTFOLIO=${UNION_MIX_PORTFOLIO-}
  # With UNION_MAIN=mix: spare rows solved after the book (same running caps, caps from the book's entries), added to the
  # candidate corpus as the Sunday replacement step's in-shape supply -- no house candidate fits WS (reviewer 2026-10-06,
  # blocking). 15 = study 24's sizing (deepest spare drawn 9). Never book rows.
  export UNION_MIX_SPARES=${UNION_MIX_SPARES-15}
  # Operator 2026-09-28 14:3x: the 25% DST cap on the pmo_x50 main book, and the deep-line sleeve may draw from its rows.
  export UNION_MAIN_DST_CAP=${UNION_MAIN_DST_CAP-0.25} UNION_SLEEVE_INCLUDES_MAIN=${UNION_SLEEVE_INCLUDES_MAIN-1}
  # The main book's per-player exposure cap as a share of K (0.5 = L13's PMO_X50, as entered; L17 09-29: looser is HARMFUL).
  # UNION_PMO_CAP is NOT this lever: it caps the extra --pmo pool rows, which are off (UNION_PMO=0).
  export UNION_MAIN_CAP=${UNION_MAIN_CAP:-0.5}
  # The tail sleeve's per-player exposure cap as a share of T; empty = none (as entered). PREREG-L19 tests it (operator 09-29).
  export UNION_SLEEVE_CAP=${UNION_SLEEVE_CAP-0.5}   # operator 2026-09-30 after L19 (S50 SUPPORTED): Week 4; UNION_SLEEVE_CAP= turns it off
  # The winner-shaped tail sleeve (operator 2026-10-02): mean = the projection sleeve; field = scripts/field_sleeve.py
  export UNION_SLEEVE_SOURCE=${UNION_SLEEVE_SOURCE:-mean} UNION_SLEEVE_FIELD_MODE=${UNION_SLEEVE_FIELD_MODE:-top} UNION_SLEEVE_MAX_PER_GAME=${UNION_SLEEVE_MAX_PER_GAME:-5}
  export UNION_SLEEVE_FIELD_ROWS=${UNION_SLEEVE_FIELD_ROWS-}   # the split: N field rows first, the projection sleeve after (unset = all field)
  # The ownership term in the main book's objective (operator 2026-09-29, reviewer 16c293b7): mean + tilt x predicted
  # ownership % (skill players), from the lag + LineStar blend built right before each union. 0 = off (the book as armed
  # before 09-29); 0.20 = the reviewer's specification. OWNERSHIP_LAG = Saturday's lag-model file (ownership_sets.py sets
  # --lag-features; never rebuilt later: a past week's rebuild collapses), LINESTAR_DIR = the captures.
  export UNION_MAIN_OWN_TILT=${UNION_MAIN_OWN_TILT:-0}
  # the term's last fallback before none (operator 2026-10-01, cracks audit A): Saturday's lag file at this tilt (L20 LAG_010)
  export UNION_MAIN_OWN_LAG_TILT=${UNION_MAIN_OWN_LAG_TILT:-0.10}
  export OWNERSHIP_LAG=${OWNERSHIP_LAG:-$OUT/ownership_lag.csv} LINESTAR_DIR=${LINESTAR_DIR:-$OUT/linestar}
  # The predictor inside the term (operator 2026-09-30): blend (default) or tabpfn (PREREG-L23b's form on the laptop GPU,
  # the blend file as its LOUD fallback). OWNERSHIP_LAGS = Saturday's `ownership_tabpfn.py lags`; OWN_TABPFN_ROWS = L23's
  # rows file (private, sha pinned in the script); OWN_TABPFN_ROWS_2026 = the 2026 W1-3 context rows (optional).
  export UNION_MAIN_OWN_PREDICTOR=${UNION_MAIN_OWN_PREDICTOR:-blend} TABPFN_PY=${TABPFN_PY:-$HOME/.local/tabpfn311-gpu/bin/python}
  export OWNERSHIP_LAGS=${OWNERSHIP_LAGS:-$OUT/ownership_lags.csv} OWN_TABPFN_ROWS=${OWN_TABPFN_ROWS:-$OUT/private/l23_rows.parquet}
  # The small-contest overlap limit (PREREG-L25 SUPPORTED; operator 09-30: Week 4, M picked at the Thursday freeze): each
  # 2-5-entry main-track contest's rows share <= M players pairwise; unset = off. enter_layout.py reads it (with its
  # loud fallback to M+1..7, then head rows, per contest).
  # Week 4 (operator 2026-09-30 14:2x, "in effect this week"): 5 by DEFAULT, so every shell that sources week_env -- the
  # timers, the after-build chain, a hand-run sunday_swap.sh -- writes and checks with the same value (enter_layout's
  # check fails closed on a mismatch). ENTER_SMALL_MAX_SHARED= (explicitly empty) turns it off.
  # CBC threads for the lev batch (operator 2026-10-01; nfl2 1c8eff1): unset/1 = the exact single-thread call. Set on the
  # arm line (8) only after the full-batch exact-match acceptance passes on the workstation AND on this laptop.
  export LEV_CBC_THREADS=${LEV_CBC_THREADS-}
  export ENTER_SMALL_MAX_SHARED=${ENTER_SMALL_MAX_SHARED-5}
  # The limit's contest-size ceiling (PREREG-L26 SUPPORTED; operator 09-30 17:05: Week 4 IF Thursday's smoke covers it):
  # unset/empty = 5 (L25's 2-5-entry cells); 10 adds the 10-entry contests (default since the 2026-10-01 smoke passed).
  export ENTER_SMALL_OVERLAP_MAX_ENTRIES=${ENTER_SMALL_OVERLAP_MAX_ENTRIES-10}   # Week 4: L26 SUPPORTED + the 10-01 smoke published/swapped through it; = (empty) -> 5
  export OWN_TABPFN_ROWS_2026=${OWN_TABPFN_ROWS_2026-$OUT/private/rows_2026_w1w3.parquet}   # production 04fa1257, sha 214f67c2
  # Cash/double-up PAPER shadows (operator 2026-09-22; never built in Week 3 by omission): arms A and B are built by the
  # chain from the final run dir before lock, entered nowhere, scored Monday. 1 = build them; 0 = off (explicit).
  export CASH_SHADOW=${CASH_SHADOW-1} CASH_SHADOW_N=${CASH_SHADOW_N:-20}
  if [[ -z "$group" ]]; then
    group=$(PYTHONPATH="$PROD/src" "$PROD_PY" "$PROD/scripts/find_main_draft_group.py" --season "$SEASON" --sunday "$SUNDAY") || { echo "week_env: could not detect the Sunday-main draft group for $SUNDAY (set GROUP explicitly)" >&2; return 1; }
  fi
  export GROUP=$group
  mkdir -p "$OUT"
  echo "week_env: season $SEASON week $WEEK ($WEEKDIR) sunday $SUNDAY lock $LOCK_UTC group $GROUP out $OUT" >&2
}
