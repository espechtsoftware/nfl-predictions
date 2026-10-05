# Preregistration: study 1 + P4, de-concentrating the book (FROZEN 2026-10-05 after the reviewer's first pass)

Written for the reviewer and the operator. Frozen before any arm is built or scored. Operator directive 2026-10-05: "Keep going so the system can be improved so it
actually can win."

## Why this study, and why first
- **Week-4 diagnosis (`reports/2026-10-05-path-to-winning-plan.md`):** our picks were no more over-projected relative
  to the market than the field's picks. The losses were correlated busts in a concentrated book:
  - 61% of entries held 3+ players from the top-total game;
  - one triple sat in 58% of entries;
  - Chase was in 49% of entries.
- **X1 steps 1–2 (`reports/2026-10-05-x1-steps-1-2-shootouts-and-field-allocation.md`):**
  - The top-total game is the week's top scorer about 19% of the time, and in the top 3 about 41% (2014–21).
  - The field is flatter than the odds.
  - So leaning toward the top total is supported, but not 61% of the book.
- **The money-gate replay:** a simple 30% player cap (A3) did not improve how lineups finished. A player cap alone is
  not the lever; game-level concentration and dealing are untested.

## Question
At the money path's K, dose and layout, does capping per-game concentration in proportion to each game's chance of
producing a top-3 game score, and/or dealing rows with one offset per contest (P4), improve the realized finish of
the entered rows, without hurting tickets and line hits?

## Arms (identical pools, K, dose, selector and term; co-run on the same build)
- **C (control):** the current selection, `union_reselect --main pmo_x50 --main-cap-share 0.5 --main-own-tilt 0.20`,
  plus the head layout.
- **G (game cap):** C, plus a per-game constraint in the sequential optimizer:
  - the share of main-book rows with ≥ 3 players (QB and DST count) from game g is at most
    `min(0.5, p3(rank_g))`;
  - **Exploratory secondary, never decision-bearing:** the same constraint at 0.75 × p3, labelled exploratory.
  - `p3(r)` = P(a game at total rank r is among the week's 3 highest-scoring games), from **2014–2021 outcomes
    ONLY**: 0.409,
    0.336, 0.234, 0.241, 0.255, 0.255, 0.153, 0.197, 0.182, 0.182, 0.095, 0.124, 0.161, 0.080 for ranks 1–14; 0.08
    for ranks 15+;
  - the rank is that slate's pre-lock total-line rank.
  - The constant is frozen here; there is no tuning.
- **P4 (offset dealing):** C's book, dealt with one offset per contest (the variant that cut empty weeks from 25–30% to
  11–21% in the 09-29 addendum §3). It must be BUILT and tested first; it changes dealing, not rows.
- **G+P4:** both.

## Data and harness
- **Harness:** the L-series builder (`experiments/l25_small_overlap.py`, driver `scripts/l25_drive.py`; nfl2
  `production/prereg-l26-results-20260930`).
  - It builds each slate's K = 105 main book DIRECTLY on the slate frame with the money path's sequential capped
    optimizer: `plain_mean_book` with exposure cap 52, DST cap 26, house rules and the λ = 0.20 ownership term on the
    pre-lock predictors.
  - It draws a Millionaire-sized field per slate with `sample_field`, the gated ownership-consistent sampler.
  - **Generation law and dose:** the harness has NO candidate pool and no dose. The book is the optimizer's
    sequential solves on the frame (the money path's `pmo_x50` main), not a selection from the Saturday D12800 supply
    plus the 0/4800 T-70 union.
  - Under the post-selection law, a verdict on these books may therefore not transfer to the money path's union
    selection. That is what the TRANSFER CHECK below is for.
- **Population (primary):** L13's 36 slates (2023–2024), the same slates as every L-series read, at FRESH banks.
- **The `p3` table comes from 2014–2021 OUTCOMES only.** The 2022–25 field-share step (X1 step 2) used ownership only
  (no outcomes). So no panel outcome informed the cap, and a reader can check it.
- **Excluded from every design choice:** 2022 W1 (one PREREG-098 shard was opened on 10-05, disclosed). It is not in
  the 36-slate population. The results still report the with/without sensitivity wherever 2022 data enters.
- **TRANSFER CHECK (descriptive):**
  - Run C and G through the money-gate harness (`production/moneygate-harness-20261005`) on the REAL 2026 W1–4 pools
    and contests, and require the DIRECTION to agree with the panel.
  - Week 4 is flagged as the week that motivated the study.
  - Pools are regenerated only if the panel and the transfer check disagree.
## Endpoints
- **PRIMARY (G vs C), row level:** the mean finish percentile of the main-book rows in that slate's sampled field,
  realized points vs the sampled field's realized-points distribution. It is the most powerful yardstick (P1). P4
  does not change rows, so P4 has no row-level primary.
- **PRIMARY (P4 and G+P4 vs C), entry level:** the mean finish percentile of the dealt ENTRIES, each in its own
  contest's line distribution.
  - The fixed plan is Week 4's real contest mix, the plan we run.
  - Week 3's plan is reported as a sensitivity, because the deep-supersat share changes what dealing can do.
- **Secondary:**
  - tickets and line hits at each contest's line;
  - zero-cash weeks;
  - worst-decile week;
  - one-player-bust exposure (the share of entries holding the slate's biggest projected-to-realized miss);
  - the realized ≥ 194 / 200 rates of the book's best.

## Decision rule (frozen at freezing)
- **Unit:** the slate. Season-clustered bootstrap, family level 0.975 over the three comparisons (G, P4, G+P4 vs C).
- **PASS** iff the primary interval excludes 0 in the favourable direction, AND every season is non-negative, with at
  most one negative leave-one-season-out, AND no secondary worsens beyond its stated tolerance (tickets −5%, zero-cash
  weeks +5 points).
- **Vacuity:** an arm byte-identical to C on more than 80% of slates is reported as a dead lever (the cap does not
  bind).
- **Integrity first:**
  - an outcome-blind support census (how often the cap binds; rows changed);
  - a full-path smoke at small scale;
  - the A0-style known-answer check of the scorer on the real W1–4 books (already passed in the money-gate harness,
    which is reused).
- **If PASS:** a reversible Week-N trial under adoption track v2, with the rollback trigger of the money-gate design
  Addendum 1.5, and C built every week as the paper book.

## Reviewer's rulings (first pass, 2026-10-05)
- **(a)** The L-series books are acceptable for the panel, with the generation law stated and the transfer check
  added. Pools are regenerated only on a material dose difference AND a disagreeing transfer check.
- **(b)** One primary cap form, min(0.5, p3). The 0.75 × p3 arm is exploratory only.
- **(c)** Week 4's contest mix is the fixed plan, with Week 3's plan as a sensitivity.
