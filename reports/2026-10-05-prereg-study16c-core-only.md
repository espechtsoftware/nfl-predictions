# Preregistration: study 16c, the thesis portfolio with no contrarian element (FROZEN 2026-10-05)

Frozen before the outcome-blind census and before any scored bank. Later changes are dated deviation notes at the end.
The reviewer froze it and reads it first; the laptop re-runs the frozen reader before the LEDGER row.

**The operator's request (10-05, verbatim), after study 16's read:** "please describe how the thesis study was
implemented.  Did it include contrarian players?   I can accept that that idea isn't good, so if that was included, try
again without any contrarian element"

## What study 16 contained
- **No player-level contrarian.** The prereg excluded it ("Excluded: player-level contrarian"). Both books carry the same
  +0.10 × LAG predicted-ownership term, a tilt TOWARD the field's popular players.
- **A game-level contrarian element:** the alternative-scenario share, 15% of rows ("a game goes differently than
  predicted"), split between mid-total shootouts (total rank 5–8, full stack) and favourite blowouts (the lead RB and the
  DST of a team favoured by ≥ 6, at most 1 opponent).
- Study 16 read NO DIFFERENCE on tickets (−1.833 per slate, [−5.347, +1.431]); the descriptive mean-finish guard was far
  below its margin (Addendum 125).

## The arm
- **C:** the current book, study 16's C, unchanged.
- **TP0, the thesis portfolio with the alternative share set to 0:** every one of K = 105 rows has its QB from a game at
  pre-lock total rank ≤ 4, with the share per game ∝ P3(rank), study 1's frozen 2014–21 table renormalised over ranks 1–4.
  - Rows per game by largest remainder; the same sequential optimizer, objective (mean + 0.10 × LAG), caps (player 52,
    DST 26, ≤ 7 shared), stack rule, MAX_PER_GAME 4 and $49k floor.
  - Cells filled in descending size, the caps shared; a failed solve passes to the core game with the highest P3.
  - The book's rank order interleaves the four games by D'Hondt (study 16 deviation note 1).
- **The code:** study 16's experiment, byte-identical (`experiments/s16_thesis_portfolio.py`, sha256 `8d3414a3…6930`,
  frozen in study 16's deviation note 3), run through a wrapper that swaps its arm set to `{"TP0": 0.0}` for the call.
  With a zero alternative share, study 16's `cells()` gives the core cells all of the share and the mid and blow cells
  zero rows. There are no exploratory arms.

## Fixed (as study 16)
K 105; LAG 0.10; the Week-4 mean-track plan (22 contests, 147 entries); L13's 36 slates (2023–24); the gated field sampler;
dealing by study 1b's `deal()` (M 5, ceiling 10); **fresh banks 1411/1412** (unused as bank labels in both repositories'
branch scans, reserved with the laptop 10-05); smokes on throwaway bank 1406.

## Endpoints and decision rule (study 16's, unchanged)
- **PRIMARY = TICKETS:** dealt entries at or above each contest's line, summed per slate, TP0 − C, paired.
  Season-clustered bootstrap, B 20,000, seed 20261005, two-sided 0.975.
- **PASS** = lower bound > 0, both season means ≥ 0, and the GUARD holds: mean entry finish, one-sided 0.975 lower bound
  > −0.015 (the operator's 1.5-point margin, as study 16).
- **FAIL (guard):** tickets would pass but the guard fails. **WORSE:** the tickets upper bound < 0. **DEAD LEVER:** dealt
  identically to C on more than 80% of slate-banks. **NO DIFFERENCE** otherwise.
- **Secondaries:** zero-ticket slates, best ≥ 200, the worst-decile slate, the maximum entry exposure, the realized core
  share, and the simulated line-crossing share (in-sample: the books were optimized on the same draws, which favours the
  mean-max C; never decision-bearing).
- **The guard is read and REPORTED in every branch** beside the frozen verdict (the reader reaches it only on a tickets
  PASS), as Addendum 125 did for study 16.

## Power and the prior, stated before the read
- Power is study 16's: TP0 re-allocates the whole book, so on 36 slates the tickets primary resolves only about +40–45%
  more tickets. **A smaller effect reads NO DIFFERENCE.**
- **The prior points against TP0.** In study 16's exploratory arms, shrinking the alternative share did not help: TP20
  −1.472, TP −1.833, TP10 −1.694 tickets per slate, with the guard at −0.038, −0.043 and −0.045. Study 16's loss came with
  the CONCENTRATION on the top-4 totals (C deals about 75% of entries there, TP 89%); TP0 concentrates further (100% of
  rows). The test is built to come out either way, and a read in either direction answers the operator's question.

## Integrity
- **Reader:** `scripts/s16c_report.py`, sha256 `ceb90a64af6179bb0dbe30c285fbdd47c3729125c507cdf7664971385468c766`.
  It is study 16's frozen reader (04ed4fda) with the arm set changed to (C, TP0); a test asserts that outside the docstring
  and the arm names the two are identical, and that the printed levels match this text.
- **Wrapper** `experiments/s16c_core_only.py` sha256 `548e7fb6…b6`; **driver** `scripts/s16c_drive.py` sha256
  `390dd406…a6` (study 16's driver with the 16c module).
- **Tests** (nfl2 `production/s16c-core-only-20261005`, `tests/test_s16c_core_only.py`, 5, plus study 16's 10): the
  arm swap reaches study 16's `run()` and is restored after it; study 16's experiment is byte-identical; every row is in a
  core cell with P3 shares; the reader's rules and levels.
- **Full-path smoke** on throwaway bank 1406 (2024 W6), before this freeze: rc 0; TP0 105 rows, all core (35/29/20/21),
  0 passes; only mechanics printed; the output was deleted unread.
- **Next, in order:** the outcome-blind census on 1411/1412 (realized core share, passes, entries changed vs C, short
  books), recorded as deviation note 1; then the scored run; then the reviewer's read; then the laptop's byte-identical
  re-run; then the LEDGER row and an Addendum.

---

## Deviation note 1 (2026-10-05, before any scored bank): the outcome-blind census is in
- **Census** (banks 1411/1412, mechanics only, 72 slate-banks, no errors; nfl2 `production/s16c-core-only-20261005`
  `results/s16c/CENSUS_s16c.txt`, script `scripts/s16c_census.py` = study 16's with the arm set (TP0,)):
  - TP0 target and realized share core/mid/blow 1.000 / 0.000 / 0.000, in rows and in dealt entries;
  - shortfall passes 0 (max 0); short books 0;
  - **entries changed vs C 0.965**: not a dead lever.
- "Slate-banks with a blowout cell 70/72" in the census counts cells that exist with a ZERO share (study 16's `cells()`
  still lists them); none receives a row. Nothing changes in the design.
- Next: the scored run on 1411/1412, then the reviewer's read with the frozen reader (sha `ceb90a64…`).
