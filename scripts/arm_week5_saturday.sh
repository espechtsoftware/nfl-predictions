#!/usr/bin/env bash
# Saturday 2026-10-10: the agent arms Week 5 itself (operator 10-03: arm without him, ask only if blocked). DRAFTED Tue
# 10-06 from w4_arm_saturday.sh; FINALISED Friday after his decisions -- it REFUSES to arm until SHAPE and FRIDAY_HEAD
# are set below. Run AFTER the Saturday 09:47 refresh (build-features -> tabpfn-gen -> project-slate) has succeeded.
# Stops at the first failure with "ARM STOPPED: <why>" -> ask the operator. Must finish before 10:30 CT.
#   bash scripts/arm_week5_saturday.sh [--check]   (tracked for review 10-06; Saturday runs the reviewed copy)     (--check: steps 0 and 6 only, nothing written or armed)
#
# Week-5 changes vs Week 4 (reports/2026-10-06-week5-arming-checklist.md):
#   GROUP 154468; no LineStar step (retired 10-06); Rev3 plan, Rev6 since 10-07 (supersats on rows 1-26, K 26, caps 13/6; all mean-track,
#   so no tail-sleeve settings); FP projections (UNION_PROJ_SOURCE=fp); NO ownership term (operator 10-06: "yes, remove
#   the tilt as you suggested": under FP the tilt carries no information beyond the projection -- the W1-4 regression,
#   and production's W4 fixed-book replay 0.0094 with it vs 0.0336 without); the shape: mixt (the winners' mix; his formal
#   yes 10-06, with study 35's QB cap A) -- ct (Week 4's shape) stays selectable, but only with QB_CAP_ROWS='' (the cap
#   was tested on MIXT only); both on
#   ONE pin f69598b (the reviewer 10-06); 13 timers (two Sunday FP captures and two T-70 DK pulls included), 11 when
#   armed late.
set -uo pipefail
SHAPE="mixt"             # his formal yes 2026-10-06: "yes to the winners' mix with the tilt and the quarterback cap" (the tilt removed by his 10-06 yes)
FRIDAY_HEAD="2e459a9950b7390750fcbaf8bfb50798df8fa12b"   # 10-09: his package (5eab90f4) + his test-2 row rules (e8c63263 + 58a328b6) + ONECATCH (c391fbd0 + f483644c, LIVE) + the RBMATE4 flag and wiring (4caff46d + 77bd55c5, off) + the zero-quota parser (21fa9d29); A3 cancelled by him
PLAN_SHA=5f8352eebf17860795922f8b5bca754c4ed0566c8c5ca63419e6dacd24e59470     # Rev6 (his FINAL contest order 10-07; Rev3's contests
                                    # re-ordered, the same book; installed 10-07 14:38 after the priority screen's pair (ii);
                                    # Rev3 kept as contests.json.rev3-8625de0e)
CHOSEN_LEV=0; CHOSEN_BOOM=4800                                                # FRIDAY: confirm the Week-5 dose
QB_CAP_ROWS=5; QB_CAP_K=26          # study 35's cap A (his yes 10-06): no QB in more than 5 of the 26 book rows
OWN_TILT=0                          # the ownership term (his 10-06 yes: "remove the tilt"); 0 = no term, no FP ownership on the money path
MAX_SHARED=4                        # a union row shares at most 4 players with every earlier row (his 10-06 evening yes,
                                    # "Use 4": study 41 PASS, replicated by study 42's GROUP4-GROUP5 on fresh banks, the
                                    # field audit clean; 5 was his afternoon choice; production default 7)
MAIN_CAP="0.35"                     # the per-player exposure cap share: HIS PACKAGE (his yes 10-09 in the laptop's session, "Yes, arm
                                    # the package"; HANDOFF). The flat 35% alone stays NOT armed (study 89, his rule: DO NOT ARM
                                    # 0.35 alone), so 0.35 only with OWN_CAP_DELTA=15 (the pair stop below). Empty refuses to arm
OWN_CAP_DELTA=15                    # his 10-09 package (HANDOFF 5380e0e7): 15 = each skill player at most his FP projected ownership
                                    # + 15 points, ONLY together with MAIN_CAP=0.35 (the tested package); 0 = off (MAIN_CAP 0.5).
                                    # Flipped to (0.35, 15) on Saturday only if the flag, the wiring, the W4 check and 6o all pass
ROW_RULES="te1_low1"                # LIVE (his answers 10-09: "Go live as my rule says" / "Go live as the rule says"); his 10-09 test 2 (HANDOFF 2ab54e30): te1_low1 = at most one TE and one skill player under 3%
                                    # FP ownership per book row, ONLY if study 91 reads it better than his package on BOTH draws
                                    # within 20% of the expected big seats; only with the package; empty = off
ONE_CATCHER_ALL=1                   # LIVE (his 10-09 decision, HANDOFF 90e8470c: "Live W5 if built in time"; every check passed:
                                    # the flag c391fbd0 + the wiring f483644c reviewed, the W4 check f9ec0239, study 38 6t acked):
                                    # 1 = study 93's ONECATCH, at most one WR / TE per team on every QB + 1 (B / C) book row, ONLY
                                    # with ROW_RULES=te1_low1 and the package; 0 = off
RB_MATE_C=0                         # his 10-09 decision (HANDOFF ad00da5c, "Try live W5 if built"): 4 = study 94's RBMATE4, the QB's
                                    # own RB in the first 4 QB + 1 (C) book rows, ONLY with ONE_CATCHER_ALL=1 (study 96 read the
                                    # two together); set to 4 only if 96 passes his rule and the flag, the wiring, the W4 check and
                                    # 6u pass; 0 = off
A1_FULL_STACK=0                     # study 102's TAIL_STACK8 (his 10-09 night "not giving up on the high scores"): 1 = the A1 rows as
                                    # QB + 2 + 2 opponents in the top-4-total games, ONLY with ONE_CATCHER_ALL=1, RB_MATE_C=0 and
                                    # MIX_QUOTAS empty, and only if study 102 picks it, 103 holds it and HE decides; 0 = off
MIX_FILL=rr                         # the MIX fill order (study 42; his 10-06 evening yes, "Use round-robin"): the cells in
                                    # turn, a row per shape for the top QBs (the outside reviewer's arm; NO DIFFERENCE on
                                    # P(>=1 big), +9% expected seats). group = the earlier book; value is NOT to be armed
MIX_COVER=0                         # study 43's coverage rows (one A1 row in each of the top-N games by total, built
                                    # first; 0 = off). Not 0 only after study 43's READ, the W2-4 check and HIS yes
MIX_QUOTAS=""                       # study 56's MIX cell quotas "A1=..,A2=..,B=..,C=.." (fewer QB + 1 rows; the operator 10-07,
                                    # his priority test this week); "" = MIX_CELLS as today. Set only after 56's READ, a
                                    # rehearsal with it and HIS yes at arming
MIX_RS=0                            # study 46's half-and-half book (N of the 26 rows under the regulars' tiers; 0 =
                                    # off; 9 / 13 / 17). Not 0 only after study 46's READ, the replay and HIS yes
BRING_BACK_TOP_WR=""                # study 71 (the operator 10-08: "Why can't we test the study 71 today ... and use it this week?"):
                                    # "A1,B" puts the opponent's top receiver in every A1 / B row's bring-back (TOPBB_AB, only if
                                    # ENTERABLE and rehearsed on Friday's A3); "" = off (the default)
BRING_BACK_TOP_WR_ROWS=""           # study 71b (the operator 10-08: "just do a very small percentage of these as a test"): "4" puts
                                    # the rule on only the first 4 A1 / B book rows (TOPBB_N4, only if ENTERABLE and rehearsed);
                                    # "" = every A1 / B row when BRING_BACK_TOP_WR is set
PRIORITY_ORDER=0                    # priority-first dealing (the operator 10-07: "Let's try to do this one this week"; the
                                    # outside reviewer's class-E proposal): the 18 non-block rows re-ordered among their own
                                    # positions by the frozen score (nfl_dfs.inference.priority_deal), the live block kept at
                                    # its ranks; on Rev5 (his order 10-07) the priority contests read ranks 1-22. 0 = the book's own order. 1 only
                                    # after the W2-4 harm screen (reports/2026-10-07-priority-deal-harm-screen.md), study 59's
                                    # read if he sets that bar, Friday's A3 with it on, and HIS yes at arming
WINNER_ORDER=0                      # study 48b: re-order the book by study 48's winner-likeness score (most winner-like
                                    # on the big-entry ranks); 0 = off. 1 only after 48b's READ, the W2-4 check and HIS yes
WINNER_SELECT=0                     # study 48d: keep, per cell, the most winner-like of the book rows + spares (study
                                    # 48's frozen score); 0 = off. 1 only after 48d's READ, a rehearsal and HIS yes
TERM_ROWS=""                        # SATURDAY sets it (the outside review 10-07, M2: a forcing step): 8 = his cheap +2 trial
                                    # (his 10-07 decision), 0 = none (only by a recorded decision); empty REFUSES to arm.
                                    # The live term block (Saturday's one slot: the matchup block, the cheap block or none;
                                    # his decision at arming, each only if its frozen Saturday rule says ENTERABLE -- study
                                    # 51 for matchup, study 53 amendment 1 for cheap). Was the prior-top block: 8 of the
                                    # 26 rows on projection + min(0.20 x pred_own, 2.0); 0 until the replay, study 49 and
                                    # the rehearsal are recorded; a book built WITHOUT it is not published (his decision)
TERM_FILE=reports/2026-10-08-live-block/cheap2-w5.csv    # in the FRIDAY_HEAD checkout ($P): his cheap trial's file (Thursday,
                                    # cheap_block_file.py --group 154468); the prior-top file is paper only and the check refuses it
TERM_SHA=""                         # its sha256, pinned (the arm refuses a mismatch)
TERM_CAP=2.0                        # the block's cap in projected points = its dose (matchup and cheap +2: 2.0; cheap +4:
                                    # 4.0); the arm refuses a bonus file whose largest bonus exceeds it (the union would clip
                                    # a +4 file to +2 silently: a different rule from the one tested) and a cap outside (0, 5]
CLASS_SHA=92cec73388193a107c235ff3d8e8dafeea9a2d5d0121b481814b2e4fe0802f13   # O-42 (10-07): the class sleeve's model
                                    # (week_env's CLASS_SLEEVE_EVERY=2 makes every build's preflight need $W/class_model.json
                                    # + .sha256): W4's class_model_w4_w1w3 (W1 + W3), installed 10-07, unless the reviewer's
                                    # Friday decision replaces it
P=$HOME/projects/nfl-predictions; W=$HOME/week5-sunday; PY=$P/.venv/bin/python; CHECK=${1:-}
say() { printf '%s %s\n' "$(date +%H:%M:%S)" "$*"; }
stop() { say "ARM STOPPED: $*"; exit 1; }
[[ "$SHAPE" == mixt || "$SHAPE" == ct ]] || stop "SHAPE is not set (Friday: mixt or ct, his choice)"
[[ -n "$TERM_ROWS" ]] || stop "TERM_ROWS is not set (Saturday: 8 for his cheap +2 trial, or 0 by a recorded decision)"
[[ ( "$MAIN_CAP" == 0.5 && "$OWN_CAP_DELTA" == 0 ) || ( "$MAIN_CAP" == 0.35 && "$OWN_CAP_DELTA" == 15 && "$SHAPE" == mixt ) ]] \
  || stop "MAIN_CAP=$MAIN_CAP with OWN_CAP_DELTA=$OWN_CAP_DELTA: (0.5, 0) = the book as before, or (0.35, 15) = his package with SHAPE=mixt; the flat 35% never runs alone"
[[ -z "$ROW_RULES" || ( "$ROW_RULES" == te1_low1 && "$OWN_CAP_DELTA" == 15 ) ]] || stop "ROW_RULES=$ROW_RULES: empty, or te1_low1 with his package (OWN_CAP_DELTA=15)"
[[ "$ONE_CATCHER_ALL" == 0 || ( "$ONE_CATCHER_ALL" == 1 && "$ROW_RULES" == te1_low1 && "$OWN_CAP_DELTA" == 15 && "$SHAPE" == mixt && "$MIX_FILL" == rr \
      && "$MIX_COVER" == 0 && "$MIX_RS" == 0 && -z "$BRING_BACK_TOP_WR" && "$WINNER_SELECT" == 0 ) ]] \
  || stop "ONE_CATCHER_ALL=$ONE_CATCHER_ALL: 0, or 1 with ROW_RULES=te1_low1, his package (OWN_CAP_DELTA=15), SHAPE=mixt, MIX_FILL=rr, MIX_COVER=0, MIX_RS=0, no BRING_BACK_TOP_WR and WINNER_SELECT=0 (the union refuses the rest)"
[[ "$RB_MATE_C" == 0 || ( "$RB_MATE_C" == 4 && "$ONE_CATCHER_ALL" == 1 ) ]] || stop "RB_MATE_C=$RB_MATE_C: 0, or 4 with ONE_CATCHER_ALL=1 (study 96)"
[[ "$A1_FULL_STACK" == 0 || ( "$A1_FULL_STACK" == 1 && "$ONE_CATCHER_ALL" == 1 && "$RB_MATE_C" == 0 && -z "$MIX_QUOTAS" ) ]] || stop "A1_FULL_STACK=$A1_FULL_STACK: 0, or 1 with ONE_CATCHER_ALL=1, RB_MATE_C=0 and MIX_QUOTAS empty (study 102)"
[[ "$MIX_FILL" == group || ( ( "$MIX_FILL" == value || "$MIX_FILL" == rr ) && "$SHAPE" == mixt ) ]] || stop "MIX_FILL=$MIX_FILL: group, or value / rr with SHAPE=mixt"
[[ "$MIX_COVER" =~ ^[0-8]$ && ( "$MIX_COVER" == 0 || "$SHAPE" == mixt ) ]] || stop "MIX_COVER=$MIX_COVER: 0..8, and not 0 only with SHAPE=mixt"
[[ "$MIX_RS" == 0 || ( "$MIX_RS" =~ ^(9|13|17)$ && "$SHAPE" == mixt && "$MIX_FILL" == rr && "$MIX_COVER" == 0 ) ]] || stop "MIX_RS=$MIX_RS: 0, or 9 / 13 / 17 with SHAPE=mixt, MIX_FILL=rr and MIX_COVER=0"
[[ "$WINNER_ORDER" == 0 || ( "$WINNER_ORDER" == 1 && "$SHAPE" == mixt ) ]] || stop "WINNER_ORDER=$WINNER_ORDER: 0, or 1 with SHAPE=mixt"
[[ -z "$BRING_BACK_TOP_WR" || ( "$BRING_BACK_TOP_WR" == "A1,B" && "$SHAPE" == mixt && "$MIX_FILL" == rr && "$MIX_RS" == 0 && "$MIX_COVER" == 0 && "$WINNER_ORDER" == 0 && "$WINNER_SELECT" == 0 && "$PRIORITY_ORDER" == 0 ) ]] || stop "BRING_BACK_TOP_WR=$BRING_BACK_TOP_WR: empty, or A1,B with SHAPE=mixt, MIX_FILL=rr and no half / cover / winner order or select / priority order (study 71's tested arm)"
[[ -z "$BRING_BACK_TOP_WR_ROWS" || ( "$BRING_BACK_TOP_WR_ROWS" == 4 && "$BRING_BACK_TOP_WR" == "A1,B" ) ]] || stop "BRING_BACK_TOP_WR_ROWS=$BRING_BACK_TOP_WR_ROWS: empty, or 4 with BRING_BACK_TOP_WR=A1,B (study 71b's tested dose)"
[[ "$PRIORITY_ORDER" == 0 || ( "$PRIORITY_ORDER" == 1 && "$SHAPE" == mixt && "$MIX_RS" == 0 && "$MIX_COVER" == 0 && "$WINNER_ORDER" == 0 && "$WINNER_SELECT" == 0 ) ]] || stop "PRIORITY_ORDER=$PRIORITY_ORDER: 0, or 1 with SHAPE=mixt and no half / cover / winner order or select"
[[ "$WINNER_SELECT" == 0 || ( "$WINNER_SELECT" == 1 && "$SHAPE" == mixt && "$WINNER_ORDER" == 0 ) ]] || stop "WINNER_SELECT=$WINNER_SELECT: 0, or 1 with SHAPE=mixt and WINNER_ORDER=0"
[[ -z "$MIX_QUOTAS" || ( "$SHAPE" == mixt && "$MIX_QUOTAS" =~ ^A1=[0-9.]+,A2=[0-9.]+,B=[0-9.]+,C=[0-9.]+$ ) ]] || stop "MIX_QUOTAS='$MIX_QUOTAS': empty, or A1=..,A2=..,B=..,C=.. with SHAPE=mixt (study 56)"
[[ "$TERM_ROWS" == 0 || ( "$TERM_ROWS" =~ ^[1-9][0-9]?$ && "$SHAPE" == mixt && "$MIX_FILL" == rr && "$MIX_RS" == 0 && "$MIX_COVER" == 0 && "$WINNER_ORDER" == 0 && "$WINNER_SELECT" == 0 && "$TERM_SHA" =~ ^[0-9a-f]{64}$ ) ]] || stop "TERM_ROWS=$TERM_ROWS: 0, or N with SHAPE=mixt, MIX_FILL=rr, no half / cover / winner order or select, and a pinned TERM_SHA"
[[ -n "$FRIDAY_HEAD" ]] || stop "FRIDAY_HEAD is not set (Friday: the merged integration commit)"
[[ "$TERM_ROWS" == 0 || "$(sha256sum "$P/$TERM_FILE" 2>/dev/null | cut -c1-64)" == "$TERM_SHA" ]] || stop "TERM_FILE $P/$TERM_FILE is missing or its sha is not the pinned TERM_SHA"
[[ "$TERM_ROWS" == 0 ]] || "$PY" "$P/scripts/check_term_block_file.py" "$P/$TERM_FILE" --cap "$TERM_CAP" --require-bonus || stop "TERM_FILE does not fit TERM_CAP=$TERM_CAP or is not the bonus form (above)"
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
# M3 (the outside review 10-07): the armed code is the code Friday rehearsed -- only docs and this arm script may differ
CODECHG=$(git diff --name-only "$FRIDAY_HEAD" HEAD | grep -vE '^(HANDOFF\.md|README\.md|scripts/arm_week5_saturday\.sh)$|^(reports|briefings)/' || true)
[[ -z "$CODECHG" ]] || stop "code changed between FRIDAY_HEAD ${FRIDAY_HEAD:0:12} and HEAD: $(echo $CODECHG)"
[[ "$(sha256sum $W/contests.json | cut -d' ' -f1)" == "$PLAN_SHA" ]] || stop "$W/contests.json is not Rev6 ($PLAN_SHA)"
# O-42 (10-07): the class sleeve's model, checked here (also under --check) rather than at the 10:30 build's preflight
[[ -s $W/class_model.json && -s $W/class_model.json.sha256 ]] || stop "$W/class_model.json or its .sha256 is missing (the class sleeve's model, CLASS_SLEEVE_EVERY=2; O-42)"
[[ "$(sha256sum $W/class_model.json | cut -c1-64)" == "$CLASS_SHA" && "$(cut -c1-64 $W/class_model.json.sha256)" == "$CLASS_SHA" ]] || stop "$W/class_model.json is not the pinned CLASS_SHA ${CLASS_SHA:0:8} (or its .sha256 disagrees)"
K=$(PYTHONPATH=src $PY -m nfl_dfs.inference.enter_layout rows-needed $W/contests.json --layout head) || stop "rows-needed failed on the plan"
[[ "$K" == 26 ]] || stop "rows-needed on the installed plan is $K, not 26 (Rev6 under head)"
[[ -z "$QB_CAP_ROWS" || "$K" == "$QB_CAP_K" ]] || stop "the QB cap was calibrated at K $QB_CAP_K, but the plan needs $K rows (study 35: re-calibrate)"
# the local Milly graph must not run through the build windows (reviewer 10-04, binding: a CHECK, not a habit -- the O-24
# lesson): its heap and page cache (up to 18 GB) could starve the Sunday builds. ss/ps only, never pgrep -f.
NEO_PID=$HOME/.local/share/neo4j-milly/run/neo4j.pid
if [[ -s $NEO_PID ]] && ps -p "$(cat "$NEO_PID")" >/dev/null 2>&1; then stop "the local Neo4j is running (pid $(cat "$NEO_PID")): neo4j-milly stop, then re-run"; fi
[[ -z "$(ss -ltnH '( sport = :7474 or sport = :7687 )' 2>/dev/null)" ]] || stop "a process listens on 7474/7687 (the local Neo4j?): stop it, then re-run"
say "step 0 OK: checkout $(git rev-parse --short HEAD) clean; Rev6 installed; class model ${CLASS_SHA:0:8}; K $K; shape $SHAPE; Neo4j not running"
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
  if [[ "$SHAPE" == mixt ]]; then e+=(UNION_MAIN=mix UNION_MIX_PORTFOLIO=mix UNION_MIX_FILL=$MIX_FILL UNION_MIX_COVER_GAMES=$MIX_COVER UNION_MIX_RS_ROWS=$MIX_RS UNION_WINNER_ORDER=$WINNER_ORDER UNION_WINNER_SELECT=$WINNER_SELECT UNION_PRIORITY_ORDER=$PRIORITY_ORDER UNION_MIX_BRING_BACK_TOP_WR=$BRING_BACK_TOP_WR UNION_MIX_BRING_BACK_TOP_WR_ROWS=$BRING_BACK_TOP_WR_ROWS UNION_TERM_BLOCK_ROWS=$TERM_ROWS UNION_TERM_BLOCK_SOURCE=$P/$TERM_FILE UNION_TERM_BLOCK_TILT=0.20 UNION_TERM_BLOCK_CAP=$TERM_CAP UNION_TERM_BLOCK_SHA256=$TERM_SHA); [[ -n "$MIX_QUOTAS" ]] && e+=(UNION_MIX_CELL_QUOTAS=$MIX_QUOTAS) || u+=(-u UNION_MIX_CELL_QUOTAS); else u+=(-u UNION_MIX_CELL_QUOTAS -u UNION_PRIORITY_ORDER -u UNION_MIX_PORTFOLIO -u UNION_MIX_FILL -u UNION_MIX_COVER_GAMES -u UNION_MIX_RS_ROWS -u UNION_WINNER_ORDER -u UNION_WINNER_SELECT -u UNION_TERM_BLOCK_ROWS -u UNION_TERM_BLOCK_SOURCE -u UNION_TERM_BLOCK_TILT -u UNION_TERM_BLOCK_CAP -u UNION_TERM_BLOCK_SHA256); e+=(UNION_MAIN=pmo_x50); fi
  if [[ -n "$QB_CAP_ROWS" ]]; then e+=(UNION_MAIN_QB_CAP_ROWS=$QB_CAP_ROWS UNION_MAIN_QB_CAP_K=$QB_CAP_K); else u+=(-u UNION_MAIN_QB_CAP_ROWS -u UNION_MAIN_QB_CAP_K); fi
  env "${u[@]}" "${e[@]}" GROUP=154468 EXPECT_SHA=$PIN CLONE=$CLONE_DIR ENTER_LAYOUT=head PROD_ARMED_HEAD=$(git -C "$P" rev-parse HEAD) \
    D3200_LEV=$CHOSEN_LEV D3200_BOOM=$CHOSEN_BOOM D800_LEV=$CHOSEN_LEV D800_BOOM=$CHOSEN_BOOM SKIP_UNITS="$skip" \
    LEV_CBC_THREADS=8 EARLY_PROPS_CT=04:30 EARLY_PROJECT_CT=04:45 EARLY_SUPPLY_CT=05:00 \
    UNION_PROJ_SOURCE=fp UNION_MAIN_OWN_TILT=$OWN_TILT UNION_MEAN_MAX_SHARED=$MAX_SHARED UNION_MAIN_CAP=$MAIN_CAP UNION_MAIN_OWN_CAP_DELTA=$OWN_CAP_DELTA UNION_MIX_ROW_RULES=$ROW_RULES UNION_MIX_ONE_CATCHER_ALL=$ONE_CATCHER_ALL UNION_MIX_RB_MATE_C=$RB_MATE_C UNION_MIX_A1_FULL_STACK=$A1_FULL_STACK \
    T70_MIN_PROJ_CT=10:30 T70_PROJECT=1 UNION_SATURDAY_RUN=auto UNION_PMO=0 "$@"
}
# 6. not too late: the Saturday D12800 is 10:30
SKIP="d6400"; EXPECT_N=13                  # 11 + the second Sunday FP capture (10:46; the outside review 10-06) + the 10:47 DK pull (O-59, 10-08)
if [[ "${ARM_LATE:-0}" == 1 ]]; then SKIP="d6400 d12800sat d6400sat"; EXPECT_N=11; say "ARM_LATE=1: Saturday supply units skipped (operator decision)"; fi
[[ "${ARM_LATE:-0}" == 1 ]] || (( 10#$(date +%H%M) < 1028 )) || stop "it is $(date +%H:%M); the 10:30 Saturday D12800 would be in the past. Operator decision: ARM_LATE=1 (no Saturday supply builds, $((EXPECT_N - 2)) timers)"
if [[ "$CHECK" == --check ]]; then
  say "the timers' dose: D3200 and D800 LEV $CHOSEN_LEV / BOOM $CHOSEN_BOOM (chosen-dose.env must say the same); QB cap ${QB_CAP_ROWS:-off} rows at K $QB_CAP_K; overlap limit $MAX_SHARED shared players; player cap $MAIN_CAP of the book; ownership cap ${OWN_CAP_DELTA} points; row rules ${ROW_RULES:-off}; one catcher per team $ONE_CATCHER_ALL; RB mate in C rows $RB_MATE_C; A1 full stack $A1_FULL_STACK; MIX fill $MIX_FILL; cover $MIX_COVER; half $MIX_RS; winner order $WINNER_ORDER; winner select $WINNER_SELECT; priority order $PRIORITY_ORDER; bring-back top WR ${BRING_BACK_TOP_WR:-off}${BRING_BACK_TOP_WR_ROWS:+ on $BRING_BACK_TOP_WR_ROWS rows}; term block $TERM_ROWS${TERM_SHA:+ (file ${TERM_SHA:0:12})}"
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
say "ARMED ($SHAPE): $N timers; checkout $(git rev-parse --short HEAD) clean; term block $TERM_ROWS rows$( [[ "$TERM_ROWS" != 0 ]] && echo " from $TERM_FILE (sha ${TERM_SHA:0:12}, cap $TERM_CAP)")"
