#!/usr/bin/env bash
# Saturday 2026-10-10: the agent arms Week 5 itself (operator 10-03: arm without him, ask only if blocked). DRAFTED Tue
# 10-06 from w4_arm_saturday.sh; FINALISED Friday after his decisions -- it REFUSES to arm until SHAPE and FRIDAY_HEAD
# are set below. Run AFTER the Saturday 09:47 refresh (build-features -> tabpfn-gen -> project-slate) has succeeded.
# Stops at the first failure with "ARM STOPPED: <why>" -> ask the operator. Must finish before 10:30 CT.
#   bash scripts/arm_week5_saturday.sh [--check]   (tracked for review 10-06; Saturday runs the reviewed copy)     (--check: steps 0 and 6 only, nothing written or armed)
#
# Week-5 changes vs Week 4 (reports/2026-10-06-week5-arming-checklist.md):
#   GROUP 154468; no LineStar step (retired 10-06); Rev3 plan (supersats on rows 1-26, K 26, caps 13/6; all mean-track,
#   so no tail-sleeve settings); FP projections (UNION_PROJ_SOURCE=fp); NO ownership term (operator 10-06: "yes, remove
#   the tilt as you suggested": under FP the tilt carries no information beyond the projection -- the W1-4 regression,
#   and production's W4 fixed-book replay 0.0094 with it vs 0.0336 without); the shape: mixt (the winners' mix; his formal
#   yes 10-06, with study 35's QB cap A) -- ct (Week 4's shape) stays selectable, but only with QB_CAP_ROWS='' (the cap
#   was tested on MIXT only); both on
#   ONE pin f69598b (the reviewer 10-06); 11 timers (the FP projections capture included), 9 when armed late.
set -uo pipefail
SHAPE="mixt"             # his formal yes 2026-10-06: "yes to the winners' mix with the tilt and the quarterback cap" (the tilt removed by his 10-06 yes)
FRIDAY_HEAD=""           # FRIDAY: the final integration head after Friday's host rehearsal (the merges landed 10-06, 231b1ea0)
PLAN_SHA=8625de0ec37d491ce7b5cf10f7e6eef7719e3198fc118df890f1b82235fe766f     # Rev3, installed Friday
CHOSEN_LEV=0; CHOSEN_BOOM=4800                                                # FRIDAY: confirm the Week-5 dose
QB_CAP_ROWS=5; QB_CAP_K=26          # study 35's cap A (his yes 10-06): no QB in more than 5 of the 26 book rows
OWN_TILT=0                          # the ownership term (his 10-06 yes: "remove the tilt"); 0 = no term, no FP ownership on the money path
MAX_SHARED=4                        # a union row shares at most 4 players with every earlier row (his 10-06 evening yes,
                                    # "Use 4": study 41 PASS, replicated by study 42's GROUP4-GROUP5 on fresh banks, the
                                    # field audit clean; 5 was his afternoon choice; production default 7)
MIX_FILL=rr                         # the MIX fill order (study 42; his 10-06 evening yes, "Use round-robin"): the cells in
                                    # turn, a row per shape for the top QBs (the outside reviewer's arm; NO DIFFERENCE on
                                    # P(>=1 big), +9% expected seats). group = the earlier book; value is NOT to be armed
MIX_COVER=0                         # study 43's coverage rows (one A1 row in each of the top-N games by total, built
                                    # first; 0 = off). Not 0 only after study 43's READ, the W2-4 check and HIS yes
MIX_RS=0                            # study 46's half-and-half book (N of the 26 rows under the regulars' tiers; 0 =
                                    # off; 9 / 13 / 17). Not 0 only after study 46's READ, the replay and HIS yes
WINNER_ORDER=0                      # study 48b: re-order the book by study 48's winner-likeness score (most winner-like
                                    # on the big-entry ranks); 0 = off. 1 only after 48b's READ, the W2-4 check and HIS yes
WINNER_SELECT=0                     # study 48d: keep, per cell, the most winner-like of the book rows + spares (study
                                    # 48's frozen score); 0 = off. 1 only after 48d's READ, a rehearsal and HIS yes
P=$HOME/projects/nfl-predictions; W=$HOME/week5-sunday; PY=$P/.venv/bin/python; CHECK=${1:-}
say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*"; }
stop() { say "ARM STOPPED: $*"; exit 1; }
[[ "$SHAPE" == mixt || "$SHAPE" == ct ]] || stop "SHAPE is not set (Friday: mixt or ct, his choice)"
[[ "$MIX_FILL" == group || ( ( "$MIX_FILL" == value || "$MIX_FILL" == rr ) && "$SHAPE" == mixt ) ]] || stop "MIX_FILL=$MIX_FILL: group, or value / rr with SHAPE=mixt"
[[ "$MIX_COVER" =~ ^[0-8]$ && ( "$MIX_COVER" == 0 || "$SHAPE" == mixt ) ]] || stop "MIX_COVER=$MIX_COVER: 0..8, and not 0 only with SHAPE=mixt"
[[ "$MIX_RS" == 0 || ( "$MIX_RS" =~ ^(9|13|17)$ && "$SHAPE" == mixt && "$MIX_FILL" == rr && "$MIX_COVER" == 0 ) ]] || stop "MIX_RS=$MIX_RS: 0, or 9 / 13 / 17 with SHAPE=mixt, MIX_FILL=rr and MIX_COVER=0"
[[ "$WINNER_ORDER" == 0 || ( "$WINNER_ORDER" == 1 && "$SHAPE" == mixt ) ]] || stop "WINNER_ORDER=$WINNER_ORDER: 0, or 1 with SHAPE=mixt"
[[ "$WINNER_SELECT" == 0 || ( "$WINNER_SELECT" == 1 && "$SHAPE" == mixt && "$WINNER_ORDER" == 0 ) ]] || stop "WINNER_SELECT=$WINNER_SELECT: 0, or 1 with SHAPE=mixt and WINNER_ORDER=0"
[[ -n "$FRIDAY_HEAD" ]] || stop "FRIDAY_HEAD is not set (Friday: the merged integration commit)"
# the reviewer's gate (10-06): study 35 tested the QB cap on MIXT only, so ct + the cap is an untested combination
[[ "$SHAPE" == ct && -n "$QB_CAP_ROWS" ]] && stop "the QB cap was studied on MIXT only (study 35); for ct set QB_CAP_ROWS='' after an operator decision"
cd "$P" || stop "no checkout"
# 0. the checkout at the tested code, clean; fast-forward only if HANDOFF/reports/README/briefings moved
git fetch -q origin || stop "git fetch failed"
[[ -z "$(git status --porcelain)" ]] || stop "the production checkout is dirty"
CHG=$(git diff --name-only HEAD origin/production/week3-integration-20260921)
if [[ -n "$CHG" ]]; then
  echo "$CHG" | grep -vqE '^(HANDOFF\.md|README\.md|reports/|briefings/)' && stop "code changed on the branch since the tested commit: $(echo $CHG)"
  [[ "$CHECK" == --check ]] || { git pull --ff-only -q origin production/week3-integration-20260921 || stop "ff-only pull failed"; }
fi
git merge-base --is-ancestor "$FRIDAY_HEAD" HEAD || stop "HEAD $(git rev-parse --short HEAD) is not at or after $FRIDAY_HEAD"
[[ "$(sha256sum $W/contests.json | cut -d' ' -f1)" == "$PLAN_SHA" ]] || stop "$W/contests.json is not Rev3 ($PLAN_SHA)"
K=$(PYTHONPATH=src $PY -m nfl_dfs.inference.enter_layout rows-needed $W/contests.json --layout head) || stop "rows-needed failed on the plan"
[[ "$K" == 26 ]] || stop "rows-needed on the installed plan is $K, not 26 (Rev3 under head)"
[[ -z "$QB_CAP_ROWS" || "$K" == "$QB_CAP_K" ]] || stop "the QB cap was calibrated at K $QB_CAP_K, but the plan needs $K rows (study 35: re-calibrate)"
# the local Milly graph must not run through the build windows (reviewer 10-04, binding: a CHECK, not a habit -- the O-24
# lesson): its heap and page cache (up to 18 GB) could starve the Sunday builds. ss/ps only, never pgrep -f.
NEO_PID=$HOME/.local/share/neo4j-milly/run/neo4j.pid
if [[ -s $NEO_PID ]] && ps -p "$(cat "$NEO_PID")" >/dev/null 2>&1; then stop "the local Neo4j is running (pid $(cat "$NEO_PID")): neo4j-milly stop, then re-run"; fi
[[ -z "$(ss -ltnH '( sport = :7474 or sport = :7687 )' 2>/dev/null)" ]] || stop "a process listens on 7474/7687 (the local Neo4j?): stop it, then re-run"
say "step 0 OK: checkout $(git rev-parse --short HEAD) clean; Rev3 installed; K $K; shape $SHAPE; Neo4j not running"
if [[ "$CHECK" != --check ]]; then
  # 1-4. Saturday inputs (no LineStar step: retired 10-06)
  PYTHONPATH=src $PY scripts/ownership_sets.py sets --week 5 --group 154468 --out $W/ownership_sets.csv 2>&1 | tail -1 || stop "ownership_sets.py sets failed"
  [[ -s $W/ownership_sets.csv ]] || stop "ownership_sets.csv not written"
  # the lag file and the TabPFN lags feed only the ownership term; at OWN_TILT 0 nothing on the money path reads them
  # (the reviewer 10-06, R1): a failure WARNS and arming continues; only a non-zero tilt makes them stops
  own_input() { if [[ "$OWN_TILT" != 0 ]]; then stop "$1"; else say "WARN: $1 (tilt 0: only study 38's exploratory MIXT_QA paper arm may be missing this week; the money path is unaffected)"; fi; }
  PYTHONPATH=src $PY scripts/ownership_sets.py sets --season 2026 --week 5 --group 154468 --lag-features --out $W/ownership_lag.csv 2>&1 | tail -1 || own_input "ownership_sets.py --lag-features failed"
  # the lag file is still produced: study 38's no-term snapshot scales FP's ownership export with it (ownership_fp.py --lag)
  $PY scripts/check_ownership_lag.py $W/ownership_lag.csv || own_input "the lag file fails its gate (sum >= 280)"
  PYTHONPATH=src $PY scripts/ownership_tabpfn.py lags --season 2026 --week 5 --out $W/ownership_lags.csv 2>&1 | tail -1 || own_input "ownership_tabpfn.py lags failed"
  [[ -s $W/ownership_lags.csv ]] || own_input "ownership_lags.csv not written"
  # 5. the dose file
  if [[ -f $W/chosen-dose.env ]]; then
    grep -qx "CHOSEN_LEV=$CHOSEN_LEV" $W/chosen-dose.env && grep -qx "CHOSEN_BOOM=$CHOSEN_BOOM" $W/chosen-dose.env || stop "chosen-dose.env exists with other values: $(tr '\n' ' ' < $W/chosen-dose.env)"
  else
    printf 'CHOSEN_LEV=%s\nCHOSEN_BOOM=%s\n' "$CHOSEN_LEV" "$CHOSEN_BOOM" > $W/chosen-dose.env; chmod 600 $W/chosen-dose.env
  fi
  say "inputs: sets OK; lag and lags as printed above (WARN lines = study 38 only); chosen-dose $CHOSEN_LEV/$CHOSEN_BOOM; ownership tilt $OWN_TILT"
fi
# The one arm line (the reviewer 10-06): ONE pin for both shapes (f69598b = 32cdb61 + the optimize() params, inert for
# the house shape; Friday rehearses the chosen shape on it); the dose from CHOSEN_* (never literals: the dose file and the
# timers must agree); UNION_MIX_PORTFOLIO only for mixt and unset otherwise.
PIN=f69598ba559202969cc91d9fbdee7f64996e97af; CLONE_DIR=$HOME/projects/.nfl2-worktrees/week5-live-center
arm_env() {
  local skip=$1; shift
  # env takes every -u before any NAME=VALUE: build the two lists apart. The QB cap rides only when set (and ct + cap
  # never reaches here: the preamble stops it); unset otherwise, so check_week_runtime never sees a K without a cap.
  local u=() e=()
  if [[ "$SHAPE" == mixt ]]; then e+=(UNION_MAIN=mix UNION_MIX_PORTFOLIO=mix UNION_MIX_FILL=$MIX_FILL UNION_MIX_COVER_GAMES=$MIX_COVER UNION_MIX_RS_ROWS=$MIX_RS UNION_WINNER_ORDER=$WINNER_ORDER UNION_WINNER_SELECT=$WINNER_SELECT); else u+=(-u UNION_MIX_PORTFOLIO -u UNION_MIX_FILL -u UNION_MIX_COVER_GAMES -u UNION_MIX_RS_ROWS -u UNION_WINNER_ORDER -u UNION_WINNER_SELECT); e+=(UNION_MAIN=pmo_x50); fi
  if [[ -n "$QB_CAP_ROWS" ]]; then e+=(UNION_MAIN_QB_CAP_ROWS=$QB_CAP_ROWS UNION_MAIN_QB_CAP_K=$QB_CAP_K); else u+=(-u UNION_MAIN_QB_CAP_ROWS -u UNION_MAIN_QB_CAP_K); fi
  env "${u[@]}" "${e[@]}" GROUP=154468 EXPECT_SHA=$PIN CLONE=$CLONE_DIR ENTER_LAYOUT=head \
    D3200_LEV=$CHOSEN_LEV D3200_BOOM=$CHOSEN_BOOM D800_LEV=$CHOSEN_LEV D800_BOOM=$CHOSEN_BOOM SKIP_UNITS="$skip" \
    LEV_CBC_THREADS=8 EARLY_PROPS_CT=04:30 EARLY_PROJECT_CT=04:45 EARLY_SUPPLY_CT=05:00 \
    UNION_PROJ_SOURCE=fp UNION_MAIN_OWN_TILT=$OWN_TILT UNION_MEAN_MAX_SHARED=$MAX_SHARED \
    T70_MIN_PROJ_CT=10:30 T70_PROJECT=1 UNION_SATURDAY_RUN=auto UNION_PMO=0 "$@"
}
# 6. not too late: the Saturday D12800 is 10:30
SKIP="d6400"; EXPECT_N=12                  # 11 + the second Sunday FP capture (10:46; the outside review 10-06)
if [[ "${ARM_LATE:-0}" == 1 ]]; then SKIP="d6400 d12800sat d6400sat"; EXPECT_N=10; say "ARM_LATE=1: Saturday supply units skipped (operator decision)"; fi
[[ "${ARM_LATE:-0}" == 1 ]] || (( 10#$(date +%H%M) < 1028 )) || stop "it is $(date +%H:%M); the 10:30 Saturday D12800 would be in the past. Operator decision: ARM_LATE=1 (no Saturday supply builds, $((EXPECT_N - 2)) timers)"
if [[ "$CHECK" == --check ]]; then
  say "the timers' dose: D3200 and D800 LEV $CHOSEN_LEV / BOOM $CHOSEN_BOOM (chosen-dose.env must say the same); QB cap ${QB_CAP_ROWS:-off} rows at K $QB_CAP_K; overlap limit $MAX_SHARED shared players; MIX fill $MIX_FILL; cover $MIX_COVER; half $MIX_RS; winner order $WINNER_ORDER; winner select $WINNER_SELECT"
  UNITS=$(arm_env "$SKIP" bash scripts/arm_week_timers.sh 5 2>&1 | grep -oE 'nfl-week5-[a-z0-9-]+' | sort -u)
  for s in $SKIP; do UNITS=$(echo "$UNITS" | grep -vx "nfl-week5-$(echo $s | sed -E 's/^(d[0-9]+)sat$/\1-sat/')-build"); done
  echo "$UNITS" | sed 's/^/  planned: /'
  NU=$(echo "$UNITS" | grep -c .)
  (( NU == EXPECT_N )) || stop "the print-only arm lists $NU units after SKIP ($SKIP), not $EXPECT_N: a merge changed the unit list"
  say "CHECK DONE (nothing armed): shape $SHAPE, pin ${PIN:0:7}, $NU units"; exit 0
fi
# 7. arm: the shape's pin and main, the rest common
arm_env "$SKIP" scripts/arm_week_timers.sh 5 --run || stop "arm_week_timers.sh --run exited $?"
# 8. verify the timer count
N=$(systemctl --user list-timers --all --no-pager | grep -c 'nfl-week5-')
systemctl --user list-timers --all --no-pager | grep 'nfl-week5-'
(( N == EXPECT_N )) || stop "expected $EXPECT_N nfl-week5 timers, found $N"
[[ -z "$(git status --porcelain)" ]] || stop "the checkout became dirty during arming"
say "ARMED ($SHAPE): $N timers; checkout $(git rev-parse --short HEAD) clean"
