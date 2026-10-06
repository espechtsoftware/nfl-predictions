# Preregistration: study 28, the winners' shape mix against the house shape, on the operator's goal and final plan (DRAFT 2026-10-06)

**Status: DRAFT.** It is frozen, with the reader's sha256 recorded here, after the one-slate smoke (§2a) and before the
binding census and any scored bank. The reviewer freezes it and reads first. The laptop acks the census and re-runs the
frozen reader before the LEDGER row.

**The operator (10-06, verbatim):** "In my opinion, that is too big of a stack and it doesn't match what the winners
do.  However, it's alternative is the same shape for every lineup.  I like what we discussed previously of mirroring how
the winners play - with a mix of stacks, double stacks, etc.  Is there a reason that we aren't trying to play the way the
winners play?" He dropped the shootout sleeve (study 27, not run).

## 1. What is known
- **Study 18 (Addendum 129):** MIX at draft A's SHALLOW lines with the lab's loose caps: +16% tickets, NO DIFFERENCE.
  It was never read on his goal or plan.
- **Studies 24 / 18b / 26 on his goal:**
  - every shape change so far reads NO DIFFERENCE;
  - WS ties the house shape;
  - the shootout shows a ceiling signal but is off the table by his choice.
- **The winners' and regulars' rates** (study 18 §1; 2026 W1–4 Millionaire top 1%):
  - QB + 2+ 44% (range 26–71%);
  - bring-back 59%;
  - dual 46%;
  - players in the QB's game 3.2;
  - depth 3+ about 2% of 69 historical winners.

  The MIX quotas were fixed from those rates on 10-05.

## 2. Arms (one co-run per slate-bank)
Study 18b's harness:
- the plain simulated mean; no ownership term;
- ≤ 7 shared with every earlier row; MAX_PER_GAME 4; a $49k floor; skill players with simulated mean < 1.0 dropped;
- production's main caps for the head K = 22 (player 11 rows, DST 5);
- the head layout with his pins; the overlap limit M 5 / ceiling 10.

The arms:
- **C (reference):** `PRODUCTION_STACK` on every row.
- **MIX (DECISION, vs C):** study 18's cells by DEALT ENTRIES, built as production's `mix_rows`:
  - **the cells:**
    - A1 30%: QB + 2+, a bring-back;
    - A2 14%: QB + 2+, no bring-back;
    - B 28%: QB + 1, a bring-back, a second-game pair, ≤ 3 from the QB's game;
    - C 28%: QB + 1, no bring-back, ≤ 3 from the QB's game;
  - the 22 book rows are allocated by quota, and the cells are solved largest first through ONE shared state (caps,
    overlap). A row a cell cannot solve passes to A1 (counted);
  - then the entry-weighted interleave. Its weights come from enter_layout's head deal of the plan WITH his pins
    (rank 1 = 10 entries, then 8, 7, 6, 5; ranks 6–22 one each), so the quotas hold by entries as dealt;
  - spares by quota after the book, to depth 40.
- **MIXNP (EXPLORATORY, vs C):** the same, with production's CURRENT `mix_shapes.plan_weights`, which strips the pins
  (O-35). It shows what MIX would deal if armed before O-35 is fixed.

## 2a. Smoke observations before the freeze
(To be filled from `~/s28-panel/smoke/`: 2023 W9, throwaway bank 1406, mechanics only; the reader checked by its exit
code and its count of "== " headers only.)

## 3. Panel and plan
- **Slates:** the 53 `k1` slates of 2022–24 with Millionaire ownership.
- **Banks:** **fresh 1425/1426** (scanned 10-06). The census is on 1406.
- **Plan:** his FINAL Rev2 plan (`~/s24-panel/plan-week5-rev2-s24.json`, sha256 `00c66004…`; pins as in study 26).
- **Field caveat:** as in studies 24 / 18b / 26.

## 4. Endpoints and decision rule (study 18b's, unchanged)
- **PRIMARY:** P(≥ 1 big seat) per slate, MIX − C. Season-clustered bootstrap, B 20,000, seed 20261010. Two-sided
  0.95.
- **GUARD 1:** mean finish; the one-sided 0.95 lower bound > −0.015.
- **GUARD 2:** expected big seats ratio ≥ 0.80.
- **Verdicts:** PASS / WORSE / FAIL (guard) / DEAD LEVER / NO DIFFERENCE, as in 18b.
- **Binding-census checks before the scored run:**
  - MIX's dealt-entry cell shares within 10 points of the quotas on average;
  - passes to A1 reported;
  - no short books;
  - MIX never identical to C;
  - MIXNP's dealt shares reported beside MIX's.

## 5. What a verdict can do
- **MIX PASS:** a reason to arm `--main mix --mix-portfolio mix` this week.
  - FIRST fix O-35 (`plan_weights` keeps the pins), with a parity test against this study's weights.
  - The MIX Sunday spares already exist (`ddd470ed`).
  - The operator decides.
- **NO DIFFERENCE with both guards intact:** a legitimate reason to choose MIX as his stated preference ("mirroring how
  the winners play"), said plainly as a preference, not a tested gain. It is still armed only with O-35 fixed.
- **WORSE / FAIL (guard):** not offered.

## 6. Integrity
- **Code:** nfl2 `production/s28-winners-mix-20261006`:
  - `experiments/s28_winners_mix.py`;
  - `scripts/s28_drive.py`;
  - **`scripts/s28_report.py` (the reader)**;
  - `scripts/s28_census.py`;
  - `tests/test_s28_winners_mix.py` (6 tests).

  The shas are recorded at the freeze.
- **Order:** this freeze → the binding census on 1406 (the laptop's ack) → the scored run on 1425/1426 → a confirmatory
  census → the reviewer's read → the laptop's byte-identical re-run → LEDGER and Addendum 133.
- **Transfer:** our projections; no ownership term; no FP.
