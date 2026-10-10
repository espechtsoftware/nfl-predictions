# Preregistration: study 115, the recency rules on wide receivers and tight ends only, on his armed Week-5 book, in the harness (DRAFT 2026-10-10)

**Status: DRAFT 2026-10-10** (the times are this file's commits) by the outside reviewer; the design is the laptop's proposal
with the lab reviewer's calls. The lab reviewer reviews, runs the binding census, freezes, runs and reads; the laptop acks and
reproduces. **A pick goes to study 115b** (the fresh-draw check), whose preregistration is committed before this study's READ.
- **Banks and seed (the laptop's reservation; the full-set check: CLEAN; the text scans of both repositories: CLEAN, 10-10):** **3946–3957** (set A
  3946–3951, set B 3952–3957; sims bases 3996–4007, fields 4646–4657); the reader's bootstrap seed **20261159**.
- **Timing (the lab reviewer's order):** after study 110 (and 111 if 110 picks), before 112, so that a pick and its fresh-draw
  check can READ before his 17:55 arm.

## 1. Why
- **The operator, 10-10, in the laptop's session:** "Test today for this week" — the outside model's second page,
  `briefings/2026-week-05/2026-10-10-additional-suggestions.md` §2 (merged `735740dd`; the laptop reproduced its numbers).
- **What the page shows (his real Weeks 2–4 fields, after the fact):** within the same user, the odds of a top-1% Millionaire
  finish for a lineup with **1+ hot WR or TE** vs none: **0.37 / 0.70 / 0.40** (W2 / W3 / W4); in his own contests 0.38. For hot
  RBs the same odds were mixed (0.73 / 2.74, thin / 0.38), and for hot QBs 2.47 / — / 0.08. **These describe winners after the
  games**; the harness is the build-before-the-games test.
- **The page's argument:** a receiver's big game is touchdowns and long plays and does not persist; a running back's is usually
  volume, which does. It suggests the all-position fade (study 109) lost most of its value on RBs and QBs. **That is the page's
  argument, not a measurement:** study 109's READ did not split the cost by position.
- **The prior: NO DIFFERENCE, leaning negative.** Study 109 (READ `169cc082`) on every position: FADE2 −4.7 (A −5.7, B −3.7),
  HOT1 −1.8 (A −2.5, B −1.2), each worse on both draws. The WR / TE split is untested.
- **On his real Week-4 book (the page, under study 109's exact flag):** 1.50 hot players per lineup (24 of 26 lineups hold one,
  14 hold two), of which 1.08 are WR or TE (22 lineups hold one, **6 hold two**) and 0.42 RB. So HOT_WRTE1 would change about
  6 of his 26 lineups live; FADE2_WRTE would reprice the 22 that hold a hot WR / TE.

## 2. Arms (`experiments/s115_wrte_recency.py`)
**Study 109's frozen module exactly** (`s109_recency_fade.py` `996077e6…`, sha-asserted; it pins study 95's harness, study 65's
flag and study 97's FAVHI); `run()` = 109's `run()` with five listed edits (a test asserts it). **Every arm is his armed Week-5
book** (the package, te1 / low1, the cheap +2 block, ONECATCH and the adopted FAVHI through 96's `combo_rules`).

**The one change, a position mask on study 109's frozen flag.**
- **The flag (unchanged):** study 65's frozen `last_game()`. A skill player whose last regular-season game **this season**
  scored ≥ 2.0 × max(the mean of his up to 4 games before it, 5), with ≥ 2 such games. The games before it are this season's
  and the previous season's (the last game must be this season's), from nflverse weekly DK points, prior weeks only.
- **The mask:** only players whose position is **WR or TE** count as hot. QBs and RBs are never flagged.
- **LIVE** — his armed book; the flag is not used.
- **HOT_WRTE1** — **at most one hot WR / TE per book row**: a row rule (the hot WR / TE ids, ≤ 1) in the same tier as te1 /
  low1, study 109's HOT1 mechanics exactly (91's: an infeasible solve is re-solved without the row rules, recorded). The
  objective is unchanged. Spares never.
- **FADE2_WRTE** — **2 points off the simulated mean of each hot WR / TE**, study 109's FADE2 mechanics exactly: every row's
  objective (the live block, the cheap block's base, the spares), the cheap block's term recomputed on the faded mean. RBs and
  QBs untouched.
- **The exact id set for production** (the laptop builds the switch to match): the pool's players with position WR or TE whose
  flag above is true on the T-70 frame's slate week; HOT_WRTE1 adds `(sorted(those ids), "<=", 1)` to the row rules of every
  book solve.

## 3. The read (the reader `scripts/s115_report.py`)
- **Study 109's reader with six listed edits, relabelled** (a test asserts them); study 63's statistics; two draws (the same past
  slates, two random opponent sets) and pooled; two-sided 0.95, B 20,000.
- **Per arm − LIVE:**
  - P(≥ 1 big seat), its guards and verdict;
  - **his rule's line** (better on both draws AND the pooled expected big seats ratio ≥ 0.80);
  - the mean best real lineup points and P(best ≥ 200), printed (information).
- **THE PICK (pre-stated; study 106's tested function `floor_pick`):** among the arms passing his rule (guard 1 printed, not
  gating), the largest pooled gain. None → "keep the live book". **A pick goes to study 115b.**
- **Multiplicity:** two arms on the same 36 slates as studies 89–114; about one false pass in three to four reads of this kind.

## 4. Honest limits, the census and production
- **The harness's projections are its own simulated means;** his book uses Fantasy Points'. FP's projection may already move
  after a big game, so a fade's live effect can differ.
- **The census, per arm (outcome-blind, bank 1406):**
  - the WR / TE flagged per slate by position — **QB and RB must be 0** (the mask; flagged otherwise);
  - every position's hot players per slate (information: what the mask leaves out);
  - LIVE's book rows holding a hot WR / TE and the arm's own rows holding one; hot WR / TE per book row and rows with 2+
    (**HOT_WRTE1 wants 0**);
  - fallbacks; ONECATCH; the RB mate's slots (4 per book); rows shared with LIVE and dealt identity; LIVE == study 97's
    RBMATE4_FAVHI (`--ref97`); the per-arm rules in the census's parity.
  - Per-slate fields stay outside the blocks the reader compares.
- **Production:** HOT_WRTE1 rides the `row_rule_sets` vehicle with the WR / TE hot ids as an input (a hot-flag file is already
  part of study 38 amendment 6y's snapshot step); a default-off switch, its tests, the Week-4 check and study 38's
  classification are needed before any arming. FADE2_WRTE has no production path this week (the term-block vehicle keeps only
  positive terms).

## 5. Smoke and code
- BLAS threads pinned; PYTHONHASHSEED=0; bank 1406 only for the smoke and the census (the unit tests, the mechanics smoke 2023 W3
  / 2023 W11 / 2024 W10, the census with `--ref97`, the full path: reader exit and line count only), in the gap the lab reviewer
  names (about 08:30).
- **The smoke:** (filled in when done).
- **Code:** nfl2 `production/s115-wrte-recency-20261010` @ `197282bc` (off study 109's `65edc3c0`, whose module is the frozen
  `996077e6`):
  - `experiments/s115_wrte_recency.py` `4f195d69…` (pins s109 `996077e6…`)
  - `scripts/s115_drive.py` `6a7299d4…`
  - `scripts/s115_census.py` `54665c91…`
  - **`scripts/s115_report.py` (the reader) `0f2f9e9b…`** (seed 20261159)
  - `tests/test_s115_wrte_recency.py` `deb1121f…` (10)
