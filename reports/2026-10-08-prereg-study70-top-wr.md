# Preregistration: study 70, a top-receiver block for this week, in the harness (DRAFT 2026-10-08)

**Status: DRAFT 2026-10-08** by the reviewer, written after the code's smoke and before the binding census, the bank
scan and any scored bank.
- **Next:** the binding census (§6), the seed scan, the freeze, the laptop's ack and scan, the run, the confirmatory
  census before the read, the frozen reader, the laptop's re-run and the records.
- **Target:** read tonight, so an ENTERABLE arm can still be rehearsed Friday and chosen at Saturday's arming.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 about 16:25** (via the outside reviewer; study list 70): "I find this somewhat concerning. Is
  there a test we can do immediately to try to fix this for this week?"
- **The concern** (the outside reviewer's W4 analysis; in-sample and chosen after the outcome;
  `briefings/2026-week-05/2026-10-08-necessary-players-and-the-bring-back.md`):
  - The Millionaire's $500+ lineups needed Collins + Lamb: 9 of the top 10, and 92% / 86% of the top 95.
  - Today's W5 settings, rebuilt on W4, hold Lamb in 0 of 26 rows, Collins in 2, both together in 0.
  - The FP-value solve never pays for an expensive WR1: Lamb, 18.05 points at $7,800, was 24th in WR value.
  - W2 and W3 show the same pattern.
- **The prior, stated first: NOT ENTERABLE is more likely.** Studies 51, 63 and 65 found no block better than the cheap
  block, and study 65's arms were all below it.

## 2. Arms (`experiments/s70_topwr.py`)
**The book:** on each slate-bank, study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted), with LIVE = 48d's
41 rows: mix_fill rr, QB cap 5, caps 13 / 6, overlap limit 4. It is dealt on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`), as in studies 54–65. Every block is study 53's `block_term` through `term_book`'s 8 rows at ranks 2, 5, 9,
12, 15, 18, 22, 25.

- **The TOP RECEIVER:** each team's highest-salaried WR in the pool. Ties go to the higher projection, then the id.
  - The pool is the optimizer's: skill players projected at least the minimum, and every DST. The live writer picks
    among the T-70 frame's buildable players, the same population.
  - Exactly one per team; the census asserts it.
- **LIVE_CB (the reference):** his live book with the cheap +2 block (study 53's CHEAP2_BLOCK8; the Week-5 trial).
- **TOPWR2_B8 (DECISION):** +2 to every top receiver, cap 2, as the 8-row block INSTEAD of the cheap block.
- **CHEAPTOPWR2_B8 (DECISION):** one block giving +2 to a top receiver OR to any non-DST player under $4,000 (the cheap
  rule), cap 2. This is the combined form he would enter.
- **CHEAPEXPWR2_B8 (DECISION; added at the smoke, before any scored bank):** one block giving +2 to a top receiver
  priced at $7,000 or more OR to a cheap player, cap 2. This is his concern itself: the expensive WR1.
  - **Why it was added:** the smoke (§6) showed that a flat +2 moves the block TOWARD the cheaper top receivers.
    Expensive top WRs per row went 0.83 → 0.72 under TOPWR2_B8, while all top WRs went 1.72 → 2.33.
  - Under the salary cap, +2 buys more on a $5,000 WR1 than on a $7,800 one.
  - The $7,000 floor holds about a third of the slate's top receivers (7.0 of 21.3 on the smoke slates). With it, expensive
    top WRs per row went 0.83 → 1.12.
- **EXPLORATORY TOPWR3_B8:** TOPWR2_B8 at +3, cap 3.
- **A block with no qualifying player** falls back to LIVE_CB's book there, recorded. The smoke found none.

## 3. Endpoint and rule (the reader `scripts/s70_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`). Its load, boot, verdict, go / no-go and trial functions are
  identical, which a test asserts. Only the names, the seed, the docstring, the decision count and the secondaries
  differ.
- **THE READ: 2023–24** (36 slates). For each of the three decision arms, the arm − LIVE_CB on P(≥ 1 big seat), per
  slate, on the calibrated field v2.
  - The interval is two-sided 0.95, with B 20,000.
  - **Banks 1611–1616** (scanned clean by the laptop; the reviewer re-scans with the seed), seed **20261114**. Each
    slate's value is the mean over its six banks.
- **THE GO / NO-GO: 2022** (study 51's frozen rule): the point estimate of P(≥ 1 big) ARM − LIVE_CB on 2022, with its
  two-sided 0.95 interval. CONTRADICTED if the point estimate is < 0.
- **Guards** as in studies 54–65. They gate a PASS only: the mean entry percentile (one-sided 0.95 lower bound above
  −0.015) and the expected-big-seats ratio (≥ 0.80).
- **Verdict per arm:** DEAD LEVER (the dealt book identical to LIVE_CB's on more than 80% of slate-banks) / WORSE / PASS
  / FAIL (guard) / NO DIFFERENCE.
- **THE TRIAL RULE** (study 51's), per arm:
  - NOT ENTERED if WORSE, if CONTRADICTED, or if the expected-big-seats ratio is below 0.80;
  - MOOT on a dead lever;
  - otherwise ENTERABLE, his decision.
- **Multiplicity, disclosed:** three decision arms, each its own read, with no adjustment. Under no effect, a false PASS
  somewhere among the three has roughly a 7% chance.
- **EXPLORATORY:** TOPWR3_B8 − LIVE_CB; each arm on the l02 field; P(≥ 2 big seats); top receivers, expensive top
  receivers and cheap players per book row.

## 4. What the harness can and cannot say (disclosed before the census)
- **The transfer caveat is sharper than study 65's.**
  - The concern is FP's value solve specifically: FP's projection per dollar never reaches the expensive WR1.
  - The harness base is our simulator's mean, not FP's. So the harness answers "does a top-receiver block help on our
    base?", not "does it fix FP's undervaluation?".
- **The descriptive complement** is the outside reviewer's W2–4 real-field replay with FP (review/outside-fill-order-20261006
  @ `1ed24fa5`, `reports/2026-10-08-topwr/`; in-sample, with W4 chosen after the outcome; descriptive only). P(≥ 1 big)
  for W2 / W3 / W4:
  - live: .010 / .002 / .297;
  - cheap +2: .112 / .018 / .660;
  - top-WR +2: .453 / .018 / .455;
  - cheap OR top-WR: .452 / .019 / .421.
  - W2 jumps (Lamb boomed; more WR1 exposure), while W4 falls below the cheap block.
- **The block cannot produce W4's pairing** (the outside reviewer's mechanics probe on W4, outcome-chosen).
  - Top-WR +2, +3 and +4 all leave Lamb in 0 of 26 rows, and Collins + Lamb together in 0.
  - The solver puts Stroud in cells with no bring-back, or takes the cheapest bring-back. A per-player bonus on 8 rows
    does not steer which bring-back a QB row takes.
  - So a PASS here would come from WR1 exposure in general, not from producing W4's stack. The tool for the pairing
    itself is study 71 (the bring-back = the opponent's top-salaried receiver), a W6 candidate.
- **The harness's lines are closing lines,** as in every harness study; salaries are DK's.

## 5. What a verdict can do
- **An arm ENTERABLE:** his choice at Saturday's arming, between `cheap2-w5.csv` and that arm's file.
  - The W5 writer is the outside reviewer's `scripts/top_wr_block_file.py` (the laptop reviews it).
    - `--base cheap2-w5.csv` keeps the live cheap rows unchanged and adds the top-WR flags.
    - `--min-salary 7000` gives CHEAPEXPWR2's floor.
  - The writer must be merged with tests before FRIDAY_HEAD. Friday's A3 rehearses the file. The arm keeps TERM_FILE /
    TERM_SHA and cap 2.0.
  - The live file uses the group-based cheap rows; the harness uses the frame's cheap mask. Both are the cheap rule.
- **Otherwise:** the live book stands.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406, never a decision bank; Rev6; `~/s70-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10):
  - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
  - one top receiver per team;
  - every block applied.
  - Per book row (26 rows), LIVE_CB vs TOPWR2 / CHEAPTOPWR2 / CHEAPEXPWR2 / TOPWR3:
    - top receivers 1.72 vs 2.33 / 2.13 / 1.92 / 2.37;
    - expensive top receivers ($7,000+) 0.83 vs 0.72 / 0.92 / 1.12 / 0.73;
    - cheap players 1.78 vs 1.18 / 1.55 / 1.74 / 1.15.
  - Rows shared with LIVE_CB: 18.0–18.7.
  - **That smoke added CHEAPEXPWR2_B8 (§2).** The first pass ran without it. The second pass, with it, is the one above.
- **The full-path smoke** (2024 W10 and 2022 W6 scored on bank 1406):
  - the reader exited 0 and printed its five sections;
  - only the exit code, the line count and the section count were read. No number or verdict word was seen.
- **The binding census:** to follow (all 53 slate-banks of 2022–24, bank 1406, mechanics only).
- **Code:** nfl2 `production/s70-topwr-20261008` @ `2698ed2`:
  - `experiments/s70_topwr.py` `d622a211…`;
  - `scripts/s70_drive.py` `9c82f0db…`;
  - `scripts/s70_census.py` `cca92be7…`;
  - **`scripts/s70_report.py` (the reader) `26409685…`**;
  - `tests/test_s70_topwr.py` `d2441164…` (6 tests);
  - unchanged and sha-asserted: `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`, `term_book.py`
    `62c2306e…`, production's `enter_layout.py` `3cb051ac…`;
  - the plan: `plan-week5-rev6-s24.json` `ac10ddf6…`.

## 7. Order
1. The code and the smoke. Done.
2. This DRAFT.
3. The binding census.
4. The seed and bank scan.
5. The freeze.
6. The laptop's ack and scan.
7. The run.
8. The confirmatory census before the read.
9. The read.
10. The laptop's re-run.
11. The records: the Addendum and the lab LEDGER row.
