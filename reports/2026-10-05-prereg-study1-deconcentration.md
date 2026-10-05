# Preregistration: study 1 + P4, de-concentrating the book (FROZEN 2026-10-05 after the reviewer's first pass)

Written for the reviewer and the operator. Frozen before any arm is built or scored. Operator directive 2026-10-05: "Keep going so the system can be improved so it
actually can win."

## Why this study, and why first
- **Week-4 diagnosis (`briefings/2026-week-04/2026-10-05-path-to-winning-plan.md`):** our picks were no more over-projected relative
  to the market than the field's picks. The losses were correlated busts in a concentrated book:
  - 61% of entries held 3+ players from the top-total game;
  - one triple sat in 58% of entries;
  - Chase was in 49% of entries.
- **X1 steps 1–2 (`briefings/2026-week-04/2026-10-05-x1-steps-1-2-shootouts-and-field-allocation.md`):**
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

## Deviation note (2026-10-05, before any bank runs; reviewer ruling)

1. **The ownership term is the LAG-only predictor at λ = 0.10** (L20's LAG_010, SUPPORTED, provably pre-lock;
   `results/l20_sets/lag`, manifest-checked), identical across arms. Two alternatives were set aside:
   - **L25's primary (TABPFN_LS):** its pinned predictions file is not on this host, and it depends on LineStar.
   - **The LAG + LineStar blend:** every LineStar value we hold was fetched AFTER lock. Until Tuesday's revision check,
     a blend built on it may carry post-lock information.

   A first census launched with the blend term was stopped before it wrote any result (its directory was renamed
   `census-VOID-blend-term`).
2. **Banks 1400 and 1401: verified unused.** Every bank-labelled number in every lab branch's PREREG*, LEDGER and
   launch scripts was collected (291 distinct numbers). In the 1300–1999 range the highest used is 1341, and no 14xx
   number is labelled as a bank. Earlier plain-number matches for 1400/1401 were data values, not banks.
3. **Builder:** nfl2 `production/s1-deconcentration-20261005` (experiments/s1_deconcentration.py; driver
   scripts/s1_drive.py). Mechanics smoke 2023 W1 on throwaway bank 1398: caps bind, the arms differ from C, about 100
   seconds per slate.

4. **Reader frozen 2026-10-05, before any scored bank:** nfl2 `production/s1-deconcentration-20261005` @ `7bb4c5e`,
   `scripts/s1_report.py` sha256 `21f364d36fb21989ce8e2ff7f7aa7c5e06fd2d591c7fd5e1ebbc16b2257bcc59`. The bootstrap seed (20261005) and resample count (20,000) are fixed in the
   code. Direction: `pct` = the share of the field a row BEATS (higher = better), and every contrast is ARM − C
   (positive favours the arm). A full-path smoke on the throwaway bank 1398 (2 slates) follows; its numbers are
   discarded, and the reader sha must not change after it.

5. **DST counting fix, stopped run, bank change (2026-10-05, before any result was read; reviewer ruling).**
   - **The deviation found.** The panel frame gives each DST a side id ('ARI@WAS') with no total. So in the first
     builder a DST never counted toward its game's ≥ 3, contrary to this preregistration's "QB and DST count".
     Skill rows carry one id per game with a total. No real game was ever ranked wrong or capped wrongly.
   - **The fix** (lab `3b52858`, test plus mutation): `game_key_map` maps a DST to the game its team plays in, for
     the CAP ONLY. The optimizer's `game_id` is untouched, so C is still exactly L25's builder. Production frames
     are unaffected: the W4 T-70 frame's DSTs carry the real game id, with 0 null totals.
   - **The stopped run.** The scored run on banks 1400/1401 was stopped after 2 slate-banks; those 2 result rows
     were DELETED UNREAD. **Banks change to FRESH 1402/1403** (verified unused by the same all-branch bank-label
     scan as item 2). The mechanics census on 1400 is re-run with the fixed builder.
   - **The reader is unchanged:** sha256 `21f364d36fb21989ce8e2ff7f7aa7c5e06fd2d591c7fd5e1ebbc16b2257bcc59`.
