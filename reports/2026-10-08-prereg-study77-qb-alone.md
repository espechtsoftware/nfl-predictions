# Preregistration: study 77, the QB alone on the first 3 C rows (the shape his book never plays), in the harness (DRAFT 2026-10-08)

**Status: DRAFT 2026-10-08 (21:25 CDT)** by the outside reviewer, before any scored bank. The reviewer (84) reviews, runs
the binding census and FREEZES; the laptop acks (shas, tests, census re-run, banks and seed scanned).
- **Banks 1659–1664, seed 20261122** (assigned by the reviewer; pre-scanned clean by the laptop).
- **Target:** read tonight, after study 76, if time allows (the reviewer's triage: last). A production option only if NAKED3
  is ENTERABLE and the operator chooses it in the morning.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night:** "please look at the patterns of the winners over the past few weeks and consider a
  variety of different tests we can do throughout the night."
- **What the records and the outside reviewer's measurement show** (aggregates only):
  - The winner-structure census (08-19; 51 historical Millionaire winners): the QB alone (no WR / TE from his team) in
    22%, QB + 1 in 41%, QB + 2 or more in 37%.
  - The 2026 W1–4 Millionaires: the QB alone in 5% of the top 0.1%, 8% of the top 1%, 17% of the field; none of the four
    winners. **The definition, as the reviewer asked:** "QB alone" = NO WR / TE of the QB's team (an RB teammate allowed),
    counted whatever the opponents. This study's shape also has NO opponent (C's no bring-back); counted that way the
    2026 figures are 3% of the top 0.1%, 6% of the top 1% and 12% of the field (the same script,
    `~/private/winner-shapes-2026/shapes_naked.py`).
  - His book: 0% (every MIX cell requires a QB-side pass catcher).
- **The prior, stated first: NO DIFFERENCE or leaning negative.** In 2026 the QB alone is under-represented at the top
  (8% against the field's 17%; with no opponent, 6% against 12%). It is tested because it is the one winners' shape the book cannot play.

## 2. Arms (`experiments/s77_naked.py`)
**The book:** study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted through study 73 `3f76c629…`). LIVE = 48d's
41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`).
- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE ROWS (the reviewer asked which quota they take): cell C's.** The first 3 BOOK solves of cell C (QB + exactly 1
  pass catcher, no bring-back, ≤ 3 from the QB's game), by StackRules identity, in BUILD ORDER, are solved at C's rules
  with `qb_stack_min` 0 and `qb_stack_max` 0: the QB with NO WR / TE of his team (an RB of his team is allowed, as in any
  cell) and, as C, no bring-back. C's quota is unchanged (7 book rows); 3 of them become QB-alone, so C keeps 4 QB + 1
  rows; A1 / A2 / B are unchanged. The slot is used whether the solve is feasible or not; an infeasible one is solved at
  C's own rules and recorded. Spares never. C itself is never mutated (`dataclasses.replace`).
- **NAKED3 (THE DECISION):** 3 rows, 12% of the book (the 2026 top 1% 8%; historical winners 22%).
- **EXPLORATORY NAKED6:** the first 6 C solves, 23% (the historical rate); its 6th row is dealt at index 23 (non-big).
- **PRODUCTION'S EQUIVALENT (for §5):** study 73's machinery with C's StackRules copied at `qb_stack_min` / `qb_stack_max` 0
  on the first 3 C book solves; the shape check would treat those rows by identity.
- **DEALING:** the smoke put the 3 rows at book positions 3, 7 and 13, all read by big contests (Rev6: 0–21).

## 3. Endpoint and rule (the reader `scripts/s77_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`): load, mean_contests, boot, verdict, go / no-go and trial
  identical (a test asserts it); the names, the seed, the docstring and the secondaries (the QB-alone rows) differ.
- **THE READ: 2023–24** (36 slates). NAKED3 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2;
  two-sided 0.95, B 20,000. **Banks 1659–1664, seed 20261122.**
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's). One decision arm, so no multiplicity. One construction change a week.
- **EXPLORATORY:** NAKED6 − LIVE_CB; each arm on l02; P(≥ 2); the QB-alone rows; the QB + 2 rows; the ruled solves built
  plain.

## 4. What the harness can and cannot say
- **Path dependence:** the rows re-draw the rest of the book (the smoke shared 4.7 of 26 rows with LIVE_CB).
- **The QB-alone rows project slightly HIGHER** (+0.04 per row in the smoke): the stack requirement costs projection, so
  the test is whether the stack's correlation is worth its projection in these 3 rows.
- **The base is our simulator's mean, not FP's. The lines are closing lines.**

## 5. What a verdict can do
- **NAKED3 ENTERABLE:** a production option (the outside reviewer's, study 73's machinery) with its format agreed first,
  parity-tested against this study's frozen functions, the laptop's review, merged before FRIDAY_HEAD only after his
  morning decision (default OFF), Friday's A3 ON run, his choice at Saturday's arming.
- **Otherwise, or if any step is not clean by Friday evening:** W6, or closed.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s77-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `f4e8aa6f…`):
  - every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every row in the
    pool;
  - NAKED3: 3 of 3 ruled, 0 infeasible, at 3, 7, 13 (all big-read); NAKED6: 6 of 6, at 3, 7, 8, 13, 18, 23 (0.833);
  - QB-alone rows: LIVE_CB 0, NAKED3 3, NAKED6 6; QB + 2 rows 12 in every arm;
  - projection per row +0.04 / +0.15; rows shared with LIVE_CB 4.7 / 4.0; dealt identical 0.000 / 0.000.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 41 lines and 3 sections; only
  those were read.
- **The binding (support) census:** the reviewer's, on all 53 slate-banks of bank 1406, before the freeze.
- **Code:** nfl2 `production/s77-naked-20261008` @ `cd754b3` (the outside reviewer's draft; branched from study 76's
  `4cf9e29`, which carries study 75's census merge):
  - `experiments/s77_naked.py` `d455f3dd…`;
  - `scripts/s77_drive.py` `2bb3cd70…`;
  - `scripts/s77_census.py` `051973f5…`;
  - **`scripts/s77_report.py` (the reader) `246a2147…`**;
  - `tests/test_s77_naked.py` `3116fb3e…` (6 tests);
  - unchanged and sha-asserted: `s73_topg_qb1.py` `3f76c629…` (its pinned `s48_winner_like.py` `c22d2811…`,
    `s53_cheap_pref.py` `f3f9d735…`), `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`; the plan
    `ac10ddf6…`.
