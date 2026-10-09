# Preregistration: study 79, one pass catcher per team in the QB + 1 rows (no same-team WR / TE pair away from the QB), in the harness (FROZEN 2026-10-08)

**Status: FROZEN 2026-10-08 (23:17 CDT)** by the reviewer, after the outside reviewer's DRAFT (21:42 CDT), the smoke and the
binding census (§6), before any scored bank.
- The text changed at the freeze in §6 (the census) and in §4, which now carries the census's vacuity and pair-row
  figures beside the smoke's.
- The module and the reader are the DRAFT's, unchanged. The laptop acks (shas, tests, census re-run, banks and seed
  scanned, the derived seed bases too).
- **Banks 1677–1682, seed 20261124** (assigned by the reviewer; 1671–1676 skipped: the laptop found 1671 / 1672 used as seed
  bases in old lab tests; the seed scanned clean).
- **Target:** tonight, after study 78. A production option only if ONEPC8 is ENTERABLE and the operator chooses it in the
  morning.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night:** "please look at the patterns of the winners over the past few weeks and consider a
  variety of different tests we can do throughout the night."
- **What the outside reviewer measured** (the 2026 W1–4 Millionaires, weeks equally weighted; aggregates only;
  `~/private/winner-shapes-2026/scan2.py`): a lineup holding two WR / TE of ONE team that is NOT its QB's team:
  - the top 1% 11%, the field 12%: the top BELOW the field in 4 of 4 weeks (W1 11 / 15, W2 8 / 10, W3 11 / 12, W4 12 / 13);
  - his W5-style book (W4 inputs, FP): 27%.
- **Why it matters for his shapes:** a non-QB pair is a second, uncorrelated-with-the-QB stack; the winners rarely spend a
  row on it. Study 76 (two bring-backs) can ADD opponent pairs; this study removes pairs away from the QB.
- **What was tested before:** none on non-QB pairs. The nearest are studies 73 / 56 (the QB + 2 share, both NO
  DIFFERENCE).
- **The prior, stated first:** NO DIFFERENCE.

## 2. Arms (`experiments/s79_nopairs.py`)
**The book:** study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted through study 73 `3f76c629…`). LIVE = 48d's
41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`).
- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE ROWS:** the first 8 BOOK solves of the QB + 1 cells (B and C, by StackRules identity), in BUILD ORDER. Each carries
  the lab optimizer's `set_constraints` [(team T's pool WR / TE, "<=", 1) for EVERY team T]. In a QB + 1 row the QB's
  team holds exactly one WR / TE anyway, so the rule bans exactly the same-team WR / TE pairs away from the QB (an
  opponent pair included; bring-backs stay possible: one opponent WR / TE and any RBs). The slot is used whether the
  solve is feasible or not; an infeasible one is solved plain and recorded. Spares never. A1 / A2 are untouched (their
  QB pairs are the point of those cells).
  - **What counts as a pair:** any two of one non-QB team's WR / TE, so a TE and a WR of the same team count; RBs never
    count, and a DST never counts (it is not a WR / TE).
  - **A consequence in cell B (disclosed):** B allows several bring-backs today; under the rule a B row's bring-back holds
    at most ONE opposing WR / TE (an opposing RB can still be a second bring-back).
- **ONEPC8 (THE DECISION):** the first 8 B / C book solves.
- **EXPLORATORY ONEPC_ALL:** every B / C book solve (14 at K 26; 2 of them dealt at 22–23, non-big).
- **PRODUCTION'S EQUIVALENT (for §5):** production's pinned optimize (nfl2 `f69598b`) takes `member_bounds`: (team T's
  WR / TE, 0, 1) for every team; a member_bounds vs set_constraints parity test on fixtures is a condition of live use
  (study 75's §5).
- **DEALING:** the smoke put the 8 ruled rows at book positions 2, 3, 6, 7, 12, 13, 16, 18, all read by big contests
  (Rev6: 0–21).

## 3. Endpoint and rule (the reader `scripts/s79_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`): load, mean_contests, boot, verdict, go / no-go and trial
  identical (a test asserts it); the names, the seed, the docstring and the secondaries (the non-QB pair rows) differ.
- **THE READ: 2023–24** (36 slates). ONEPC8 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2;
  two-sided 0.95, B 20,000.
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's). One decision arm, so no multiplicity. One construction change a week.
- **EXPLORATORY:** ONEPC_ALL − LIVE_CB; each arm on l02; P(≥ 2); the non-QB pair rows; the QB + 2 rows; the ruled solves
  built plain.

## 4. What the harness can and cannot say
- **THE GAP TRANSFERS (unlike studies 75 and 78), which is why this study is worth its slot.**
  - The smoke: the harness's LIVE_CB holds a non-QB pair in 6.3 of 26 rows (24%), close to his FP book's 27%; ONEPC8 takes
    it to 3.0 (12%), about the top 1%'s 11%.
  - The binding census (53 slate-banks, §6): 5.02 of 26 (19%) → 3.26 (13%).
- **Vacuity, the smoke:** LIVE_CB holds a pair in 4.0 of the 8 rows at the ruled positions.
- **Vacuity, the binding census (§6):** 2.38 of 8. So the rule changes directly about 2.4 of the 8 ruled rows on average,
  and the rest of its effect comes through the re-drawn book. It was dealt identical to LIVE_CB on 17% of slate-banks.
  - A small dose, disclosed before any scored bank. It is not a dead lever (study 51's MOOT threshold is 80%), and the
    decision is unchanged.
- **Path dependence:** the rows re-draw the rest of the book (the smoke shared 7.3 of 26 rows with LIVE_CB).
- **The base is our simulator's mean, not FP's. The lines are closing lines.**

## 5. What a verdict can do
- **ONEPC8 ENTERABLE:** a production option (the outside reviewer's, study 73's machinery: member_bounds per team on the
  first 8 B / C book solves) with its format agreed first and the parity condition, the laptop's review, merged before
  FRIDAY_HEAD only after his morning decision (default OFF), Friday's A3 ON run, his choice at Saturday's arming.
- **Otherwise, or if any step is not clean by Friday evening:** W6, or closed.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s79-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `3abb01ad…`):
  - every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every row in the
    pool;
  - ONEPC8: 8 of 8 ruled, 0 infeasible, at 2, 3, 6, 7, 12, 13, 16, 18 (all big-read); ONEPC_ALL: 14 of 14, 0.857 big-read;
  - rows with a non-QB pair: LIVE_CB 6.3 (4.3 in B / C), ONEPC8 3.0 (0.7), ONEPC_ALL 2.3 (0.0);
  - projection per row +0.01 / −0.00; rows shared with LIVE_CB 7.3 / 7.3; dealt identical 0.000 / 0.000.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 41 lines and 3 sections; only
  those were read.
- **The binding (support) census** (the reviewer's; outcome-blind; bank 1406; all 53 slate-banks of 2022–24; code
  `a51d4238` clean; 6 tests pass; lab `results/s79/CENSUS_s79_binding.txt` `5bed1d5d…`, the raw mechanics rows
  `census_mechanics_bank1406.jsonl` `70a9f054…` with no outcome field, committed at `01a4969f`):
  - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
  - ONEPC8: 8 of 8 ruled on every slate-bank, 0 infeasible, at book positions 2, 3, 6, 7, 12, 13, 16, 18 (read by big
    contests: 1.000);
  - ONEPC_ALL: 14 of 14, 0 infeasible, two at book positions 22 and 23 (non-big; 0.857 big-read), by design exploratory;
  - vacuity: LIVE_CB holds a non-QB pair in 2.38 of the 8 rows at ONEPC8's ruled positions;
  - rows with a non-QB pair: LIVE_CB 5.02 of 26 (3.43 in B / C), ONEPC8 3.26 (1.30), ONEPC_ALL 2.15 (0.00);
  - QB + 2 rows 12 in every arm;
  - projection cost −0.02 / −0.04 per row;
  - rows shared with LIVE_CB 11.1 / 10.7; dealt identical 0.170 / 0.075 (no dead lever).
- **Code:** nfl2 `production/s79-nopairs-20261008` @ `a51d4238` (the outside reviewer's draft; branched from study 78's;
  `a51d4238` corrected the module's meta `rows` text to name B / C, the laptop's catch, no behaviour change):
  - `experiments/s79_nopairs.py` `d48790cf…`;
  - `scripts/s79_drive.py` `b789d931…`;
  - `scripts/s79_census.py` `b50f5d91…`;
  - **`scripts/s79_report.py` (the reader) `fb34eb4d…`** (seed 20261124);
  - `tests/test_s79_nopairs.py` `f792be92…` (6 tests);
  - unchanged and sha-asserted: `s73_topg_qb1.py` `3f76c629…` (its pinned `s48_winner_like.py` `c22d2811…`,
    `s53_cheap_pref.py` `f3f9d735…`), `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`; the plan
    `ac10ddf6…`.
