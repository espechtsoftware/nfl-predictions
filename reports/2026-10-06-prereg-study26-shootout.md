# Preregistration: study 26, ceiling by correlation (a one-game shootout build) against the house shape, on the operator's goal (DRAFT 2026-10-06)

**Status: DRAFT.** It is frozen, with the reader's sha256 recorded here, after the one-slate smoke (§2a) and before the
binding census and any scored bank. The reviewer freezes it and reads first. The laptop acks the census and re-runs the
frozen reader before the LEDGER row.

**The operator (10-06, verbatim):** "I would rather see around the clock efforts to try different strategies of
selecting boom players, sorting, testing usage of route share data etc with the intent to use the best system available
this week".

## 1. Why this, and not the other "boom" ideas
The ledger sweep (10-06) found the player-upside routes tested and closed at deep lines:
- a p90 lineup objective was REJECTED (system study Addendum 2);
- q97 and q98.75 objectives were HARMFUL (PREREG-006 / 010);
- the finish objective was NEGATIVE, decisively (PREREG-098);
- simulated P(≥ line) selection was negative (L14);
- the P(30+) ceiling model was negative (09-22);
- sorting by simulated tail never beat random (09-22 sort-key study; Addendum 62/65).

Our simulations overstate the far tail (studies 24 / 18b: simulated P(≥ 1 big) ≈ 0.50 vs realized ≈ 0.26), which
explains why tail-sorted selection fails.

Never tested at deep lines: building MORE correlation.
- **Studies 24 and 18b both pointed this way:** spreading the QB games lowered the ceiling, and the house shape kept the
  higher ceiling against WS.
- **L10** (CAP5, QB+3 buildable) was read only at the p89 ticket line: −1.6%, no gain.
- **The field data:** in the 2026 W1–3 Millionaires, QB+3 and 5-from-one-game lineups reached the top 10% more often
  than QB+2 / 4-per-game ones (the laptop's 09-27 critique, §3d).

## 2. Arms (one co-run per slate-bank)
Study 18b's harness unchanged:
- the plain simulated mean over the dual-law worlds (unless an arm says otherwise); no ownership term;
- ≤ 7 shared with every earlier row; a $49k floor; skill players with simulated mean < 1.0 dropped;
- production's main caps for the head layout's K = 20 (player 10 rows, DST 5);
- build depth 40; the head layout; the small-contest overlap limit M 5 / ceiling 10.

The arms:
- **C (reference):** `PRODUCTION_STACK` (QB + 2 WR/TE, ≥ 1 bring-back), MAX_PER_GAME 4. Today's main construction.
- **SH (DECISION, vs C): the shootout.** QB + ≥ 3 WR/TE, ≥ 1 bring-back, MAX_PER_GAME 5: five from the QB's game.
- **C5 (EXPLORATORY, vs C):** the house rules with MAX_PER_GAME 5 (L10's CAP5: the shootout allowed, not required).
- **P90 (EXPLORATORY, vs C):** the house shape with each player's simulated 90th percentile as the objective. This is
  the operator's "boom players", tested because he asked; **the prior is negative** (§1).

## 2a. Smoke observations before the freeze
(To be filled from `~/s26-panel/smoke/`: 2023 W9, throwaway bank 1406, mechanics only; the reader exit-checked with
its output unread.)

## 3. Panel and plan
- **Slates:** the 53 `k1` slates of 2022–24 with Millionaire ownership.
- **Banks:** **fresh 1421/1422** (no use in either repository's branch scan, 10-06). The smoke and the binding census
  are on 1406.
- **Plan:** the operator's Rev1 Week-5 plan (`~/s24-panel/plan-week5-rev1-s24.json`, sha256 `f34f3a00…`; 19 contests,
  24 entries, 23 in 18 big contests).
- **Field caveat (as in studies 24 / 18b):** the opponents are modelled Millionaire-style draws, so absolute
  probabilities are optimistic. The differences decide.

## 4. Endpoints and decision rule (study 18b's, unchanged)
- **PRIMARY:** P(≥ 1 big seat) per slate, SH − C, paired. Season-clustered bootstrap, B 20,000, seed 20261008.
  **Two-sided 0.95.**
- **GUARD 1:** mean entry finish; the one-sided 0.95 lower bound > −0.015.
- **GUARD 2:** expected big seats ratio ≥ 0.80 (the operator's tolerance).
- **Verdicts:**
  - **PASS** = lower bound > 0, at most one season mean < 0, and both guards hold;
  - **WORSE** = upper bound < 0;
  - **FAIL (guard)** = the primary would pass but a guard fails;
  - **DEAD LEVER** = identical to C on > 80% of slate-banks;
  - **NO DIFFERENCE** otherwise.
- **Secondaries:** as study 18b's, plus the share of dealt entries with five from one game and with QB+3.

## 5. What a verdict can do
- **SH PASS:** a reason to offer the shootout for the deepest contests this week. The production port is a stack-rule
  and MAX_PER_GAME change for the main book (a reviewed, tested build change); the operator decides.
- **NO DIFFERENCE:** today's shape stands. Stated plainly.
- **WORSE:** the shootout is not offered.

## 6. Integrity
- **Code:** nfl2 `production/s26-boom-objective-20261006`:
  - `experiments/s26_shootout.py`;
  - `scripts/s26_drive.py`;
  - **`scripts/s26_report.py` (the reader: study 18b's with study 26's arms, its seed and the shootout shape
    columns)**;
  - `scripts/s26_census.py`;
  - `tests/test_s26_shootout.py` (6 tests; green with studies 18b and 24).

  The shas are recorded at the freeze.
- **Order:** this freeze → the binding census on 1406 (the laptop's ack) → the scored run on **1421/1422** → a
  confirmatory census before the reader → the reviewer's read → the laptop's byte-identical re-run → LEDGER and
  Addendum.
