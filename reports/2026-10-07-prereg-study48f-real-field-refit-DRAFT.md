# Study 48f (DRAFT, not frozen): the winner-likeness score refit on REAL 2026 fields, graded prospectively from Week 5

Drafted 2026-10-07 by the laptop agent for the reviewer's review. Study list item 44. **Nothing here is frozen.** The
reviewer reviews the design before any Week-5 outcome is read. The freeze happens before the Week-5 lock (Sun 10-11
12:00 CT).

**Revision 1 (2026-10-07, the reviewer's review):**
- The decision's unit is the WEEK, not the lineup. Lineups within a week share the few players whose games decide the top
  1%, so a lineup bootstrap understates the uncertainty several-fold: the frozen 48 score's band AUC moved .492 / .538 /
  .391 across W2–W4.
- Also added: the 5% band as a descriptive line, a W9 replacement rule, OWN kept with SE-without-OWN as a descriptive
  line, the walk-forward refit as a descriptive line, the monkeys pool definition, the seeds, the dropped-lineup count,
  and the freeze contents.

## 1. Why (the evidence so far)

- Study 48 (PASS in the harness) fitted its score on top-1% rows of SAMPLED 2022–24 fields, scored on real points. The
  outside reviewer's critique (10-07): the structure coefficients partly encode the field sampler's habits, and the only
  real-field check was negative.
- The laptop's whole-field check (10-07, descriptive, every real Millionaire entrant W2–W4, 160–172k a week). The
  frozen score at equal projection had AUC .548 / .546 / .590 for the top 1% on the whole field, but **.492 / .538 / .391
  within the top 20% by projection**, where our candidates live. In W4 the most winner-like fifth of that band was the
  worst.
- The outside reviewer's attribution (W1–W4 real top 1%): no lagged player fact clears t 1.5. The environment facts (the
  QB's game-total rank, favourite / underdog, players from the top-total game) separate winners with lifts of 2–3× in
  every week.
- Study 48e's prereg §5: a harness PASS is necessary, not sufficient. Arming any winner-likeness use needs real-field
  support among top-projection lineups. 48f decides that.

## 2. The question

Among lineups a builder like ours would make (the top 20% of each real field by pre-lock projection), does a score
learned from the REAL 2026 top 1% rank this week's top-1% lineups above the rest, before lock? And does the player-fact
part add anything over structure and environment?

## 3. Data (all real 2026, all pre-lock features)

- **Rows:** every non-ours entrant of the week's Millionaire (W1–W4: 831k / 173k / 162k / 162k). Lineups with a player
  not in the T-70 frame are dropped and counted.
- **Features:** pre-lock only, from the week's T-70 frame, FP's projected ownership (W4 on; W3 the sets file; W1–2 none,
  so that block is absent), and prior-game lags (`winner_like_inputs.LAG_SQL`).
  - STRUCT: mates, bring-back, RB mate, players in the QB's game, top-total-game players, salary used.
  - ENV (new, the outside reviewer's point 3): the QB's game-total RANK (1 / 2–3 / 4+), QB favourite or underdog, the QB's
    implied total and spread, the count of players from the top-total game (0 / 1–2 / 3+), DST price class.
  - OWN: the mean projected-ownership percentile of the 8 skill players (where a source exists).
  - FACTS: study 48's player facts (red-zone / end-zone targets, goal-line carries, shares, WOPR, route share, vacated,
    touchdowns and attempts over the prior 4 / 8 games).
- **The band (the outside reviewer's point 1):** the top 20% of the week's field by the lineup's pre-lock projection sum
  (the projection we played: ours W1–3, FP W4 on).
- **Label:** finished in the real top 1% of that week's field.

## 4. Models (fixed before any fit is seen)

- Two logistic regressions, L2, C = 1.0, features standardized on the training rows:
  - **SE** = STRUCT + ENV + OWN;
  - **FULL** = SE + FACTS.
- Trained on the top-1% rows against the band's other rows (not the whole field).
- Weeks without an ownership source enter OWN as the training mean (0 after standardizing). OWN stays in SE: ownership is
  the largest coefficient in study 48, and FP's projected ownership exists from W5 on. Disclosed: OWN's coefficient is
  learned from W3–W4 only, from two sources (the sets file, then FP).
- **Development (allowed, not graded):** walk-forward fits W1→W2, W1–2→W3, W1–3→W4, used only to check that the code runs
  and the features are point-in-time. These weeks' outcomes are already known, so they grade nothing.
- **The frozen model for grading (decision-bearing):** SE and FULL fit on W1–W4. The freeze commit carries the fit's
  coefficients, standardization, the exact feature list and the sha256, before the Week-5 lock.
- **Descriptive only:** the walk-forward refit with the same frozen recipe (W1..W(w−1)) for each graded week w, and
  SE-without-OWN, so a failure can be attributed.

## 5. Grading: prospective only, Weeks 5–8 (the reviewer: "fitting walk-forward on W1–W4 is fine; grading on them is not")

**The unit is the week.** Lineups within a week are not independent: when one player booms, thousands of lineups carrying
him enter the top 1% together.

- **PRIMARY:** SE's band AUC for the top-1% label, computed separately in each graded week (the 20% band).
  - **PASS:** AUC > 0.50 in ALL FOUR graded weeks (1 in 16 under a coin-flip null).
  - **WORSE:** AUC < 0.50 in all four.
  - **NO PASS:** anything else.
  - Printed with it: the mean AUC across the weeks and the across-week SD.
  - Four weeks can detect only a large, consistent effect. A NO PASS is not evidence of no effect.
- **SECONDARY:** FULL − SE, per week. "The player facts add nothing" is supported unless the difference is positive in
  all four weeks.
- **Descriptive only, never decision-bearing:**
  - each week's lineup-bootstrap interval (B = 20,000, seed 20261048), labelled as assuming independent lineups;
  - the 5% band's AUC per week (closer to our rows, few labels);
  - the walk-forward refit and SE-without-OWN (§4).
- **The monkeys test (the outside reviewer's point 3, the score's actual use), descriptive:**
  - The pool is the union's own candidate pool as the union selected from it that week (its `candidates.parquet`),
    plus the book and the spares. The weekly line records the pool's size and sha256.
  - SE's top 26 is compared with 10,000 random 26-row draws from the same pool (seed 20261049), all scored on the real
    field.
  - Reported: the percentile of SE's 26 on P(≥ 1 top-1% row) and on mean finish.
  - The random 26s ignore the caps, so the comparison is descriptive.
- **Horizon:** W5–W8. The reader takes the first four VALID weeks of W5–W9 and prints which. W9 can only replace an
  invalid week; there is never a W10. With fewer than four valid weeks the study is INCOMPLETE.
- **A valid week** (`week_validity`, frozen in the code):
  - the T-70 frame and its FP projection file were read;
  - a pre-lock ownership file existed;
  - at least 90% of the field's non-ours entries resolved to the frame;
  - the 20% band holds at least 50 top-1% labels.

  An invalid week prints its reasons and is not counted.
- **The frozen fit** carries three models: SE and FULL (decision-bearing) and SE_NOOWN (descriptive).
- **The monkeys pool** for week w is the union dir named `union_dir_48f` in the money gate's per-week config.
- **Weekly line:** each graded week's AUCs and the monkeys percentile go into the Monday evidence record. No interim
  decision.

## 6. Support census (outcome-blind, before freezing)

For W1–W4 (outcomes already known; counts only):
- band size and top-1% labels per week (the whole-field check: W2 344 of 34,466; W3 541 of 32,302; W4 151 of 32,008);
- the share of band lineups with every feature defined;
- the band lineups dropped because a player is missing from the T-70 frame.

For W5–W8, the band and label counts are computed when each week settles.

## 7. Power and point-in-time

- **Power:** each week is one draw. The across-week SD of a band AUC looks like ~0.08 (the frozen 48 score W2–W4), so
  only a consistent effect passes in all four weeks. The per-lineup SE (0.012–0.025) is not the relevant uncertainty.
- **Point in time:** the T-70 frame and the lags come strictly before the lock. The top-total game is the frame's
  pre-lock total rank. FP's projected ownership is the newest capture before the lock.

## 8. What a result would do

- **PASS on SE:** a candidate for a real use (48e's gate at the soft threshold, or a selection), each still needing its
  own test.
- **NO DIFFERENCE or WORSE:** closes the winner-likeness line for construction. The graph stays a looking tool.

## 9. Resolved with the reviewer (revision 1)

- (a) The primary stays on the 20% band; the 5% band is descriptive.
- (b) W5–W8, with W9 as the only replacement.
- (c) OWN is kept in SE and disclosed; SE-without-OWN is descriptive.
- (d) The pool is the union's candidates.parquet plus the book and the spares, size and sha recorded.
