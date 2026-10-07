# Study 48f (DRAFT, not frozen): the winner-likeness score refit on REAL 2026 fields, graded prospectively from Week 5

Drafted 2026-10-07 by the laptop agent for the reviewer's review. Study list item 44. **Nothing here is frozen.** The
reviewer reviews the design before any Week-5 outcome is read. The freeze happens before the Week-5 lock (Sun 10-11
12:00 CT).

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
- Weeks without an ownership source enter OWN as the training mean (0 after standardizing).
- **Development (allowed, not graded):** walk-forward fits W1→W2, W1–2→W3, W1–3→W4, used only to check that the code runs
  and the features are point-in-time. These weeks' outcomes are already known, so they grade nothing.
- **The frozen model for grading:** SE and FULL fit on W1–W4. Coefficients, standardization and sha256 committed before the
  Week-5 lock.

## 5. Grading: prospective only, Weeks 5–8 (the reviewer: "fitting walk-forward on W1–W4 is fine; grading on them is not")

- **PRIMARY:** the pooled AUC of SE for the top-1% label within each graded week's band, with the weeks' AUCs averaged
  with equal weight.
  - 95% interval by a bootstrap over lineups, stratified by week, B = 20,000, seed fixed at freezing.
  - **PASS** if the lower bound > 0.50 after Week 8.
  - **NO DIFFERENCE** if the interval covers 0.50.
  - **WORSE** if the upper bound < 0.50.
- **SECONDARY:** FULL − SE pooled AUC, with the same bootstrap. "The player facts add nothing" is supported if the
  interval covers 0 or is negative.
- **SECONDARY, the monkeys test (the outside reviewer's point 3, the score's actual use):**
  - Each week, our union's candidate pool is scored (the week's T-70 candidates, the book and the spares).
  - SE's top 26 is compared with 10,000 random 26-row draws from the same pool, all scored on the real field.
  - Reported: the percentile of SE's 26 on P(≥ 1 top-1% row) and on mean finish. Descriptive; not decision-bearing.
- **Weekly line:** each graded week's AUCs and the monkeys percentile go into the weekly evidence record on Monday. No
  interim decision.

## 6. Support census (outcome-blind, before freezing)

For W1–W4 (outcomes already known; counts only):
- band size and top-1% labels per week (the whole-field check: W2 344 of 34,466; W3 541 of 32,302; W4 151 of 32,008);
- the share of band lineups with every feature defined.

For W5–W8, the band and label counts are computed when each week settles.

## 7. Power (rough, for the reviewer)

Per week the band holds about 32k lineups and 150–540 top-1% labels. With a per-week AUC SE of about 0.012–0.025, four
graded weeks give an interval half-width of about 0.015–0.02 on the averaged AUC. So the design can detect an AUC of
0.53–0.54 and above.

## 8. What a result would do

- **PASS on SE:** a candidate for a real use (48e's gate at the soft threshold, or a selection), each still needing its
  own test.
- **NO DIFFERENCE or WORSE:** closes the winner-likeness line for construction. The graph stays a looking tool.

## 9. Open for the reviewer

- (a) Band at 20%, or the top 5%? The 5% band holds only 12–94 labels a week.
- (b) Is a 4-week horizon (W5–W8) right, given 2 seasons of practice weeks are not usable here?
- (c) Should OWN be dropped entirely for symmetry (W1–2 lack it), or kept as W4-on only?
- (d) For the monkeys pool: the T-70 candidates plus the book and spares, or also the Saturday supply?
