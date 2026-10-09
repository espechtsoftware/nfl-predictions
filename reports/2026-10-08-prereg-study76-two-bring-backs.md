# Preregistration: study 76, QB + 1 with two bring-backs on the first 4 B rows (the W4 winner's shape), in the harness (DRAFT 2026-10-08)

**Status: DRAFT 2026-10-08 (21:18 CDT)** by the outside reviewer, before any scored bank. The reviewer (84) reviews, runs
the binding census and FREEZES; the laptop acks (shas, tests, census re-run, banks and seed scanned).
- **Banks 1653–1658, seed 20261121** (assigned by the reviewer; pre-scanned clean by the laptop).
- **Target:** read tonight, after study 75. A production option only if B2BB4 is ENTERABLE and the operator chooses it in
  the morning (code can be ready, not merged).

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night:** "please look at the patterns of the winners over the past few weeks and consider a
  variety of different tests we can do throughout the night", after "the two pass catchers from the same team that we're
  doing in so many of our lineups seems like too much".
- **What the outside reviewer measured** (the 2026 W1–4 Millionaires; aggregates only; `~/private/winner-shapes-2026/`):
  - 4+ players from ONE game: 41% of the top 1% against 29% of the field (W1 49 / 30, W2 27 / 28, W3 58 / 28, W4 31 / 31).
  - The W4 winner was QB + 1 with 4+ from one game; three of the four winners were QB + 1.
  - His book reaches 4 in the QB's game only through A1 (QB + 2 + a bring-back), the QB + 2 shape he doubts.
- **This study keeps the concentration and drops the second QB-side catcher:** QB + 1 + two opponents.
- **What was tested before:** study 73's QB1HALF (fewer QB + 2 rows) and study 56's QB2HALF (more) both read NO
  DIFFERENCE; study 74 (a QB + his top catcher + the opponent's top receiver on the first 4 B rows) is running. No study
  has put two bring-backs in a row.
- **The prior, stated first:** NO DIFFERENCE.

## 2. Arms (`experiments/s76_b2bb.py`)
**The book:** study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted through study 73 `3f76c629…`). LIVE = 48d's
41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`).
- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE ROWS:** the first 4 BOOK solves of cell B (by StackRules identity), in BUILD ORDER. Each is solved at B's rules
  (QB + exactly 1 pass catcher, B's second-game pair) with `bring_back_min` 2 and the QB's-game cap (`qb_game_max`) raised
  from 3 to 4: QB + 1 + at least 2 opponents, so 4 in the QB's game (MAX_PER_GAME 4 still holds). The slot is used whether
  the solve is feasible or not; an infeasible one is solved at B's own rules and recorded. Spares never. B itself is never
  mutated (a copy of its StackRules, `dataclasses.replace`).
- **B2BB4 (THE DECISION):** the first 4. Study 74's lesson: B's 5th book row is dealt at index 22, a non-big seat; 4 is
  the most B rows that sit in big seats.
- **EXPLORATORY B2BB_ALL:** every B book solve (7 at K 26).
- **PRODUCTION'S EQUIVALENT (for §5):** study 73's machinery in `mix_rows` with B's StackRules copied at
  `bring_back_min` 2 and `qb_game_max` 4 on the first 4 B book solves; the pinned optimize takes both.
- **DEALING:** the smoke put the 4 ruled rows at book positions 2, 6, 12 and 16, all read by big contests (Rev6: 0–21).

## 3. Endpoint and rule (the reader `scripts/s76_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`): load, mean_contests, boot, verdict, go / no-go and trial
  identical (a test asserts it); the names, the seed, the docstring and the secondaries (the rows with 4+ from the QB's
  game, the B rows with 2+ bring-backs) differ.
- **THE READ: 2023–24** (36 slates). B2BB4 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2; two-sided
  0.95, B 20,000. **Banks 1653–1658, seed 20261121.**
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's). One decision arm, so no multiplicity. One construction change a week.
- **EXPLORATORY:** B2BB_ALL − LIVE_CB; each arm on l02; P(≥ 2); the concentration rows; the QB + 2 rows; the ruled solves
  built plain.

## 4. What the harness can and cannot say
- **Path dependence:** the ruled rows are built early, so the rest of the book re-draws (the smoke shared 4.7 of 26 rows
  with LIVE_CB). The effect is measured on the whole book.
- **The concentration is real in the book:** rows with 4+ from the QB's game go 8.3 → 12.3 of 26 (B2BB4) and 15.3
  (B2BB_ALL); QB + 2 rows stay 12.
- **The base is our simulator's mean, not FP's. The lines are closing lines.**

## 5. What a verdict can do
- **B2BB4 ENTERABLE:** a production option (the outside reviewer's, e.g. `--mix-b-two-bring-backs 4`, study 73's
  machinery) with its format agreed first, parity-tested against this study's frozen functions, the laptop's review,
  merged before FRIDAY_HEAD only after his morning decision (default OFF), Friday's A3 ON run, his choice at Saturday's
  arming.
- **Otherwise, or if any step is not clean by Friday evening:** W6, or closed.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s76-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `5d554125…`):
  - every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every row in the
    pool;
  - B2BB4: 4 of 4 ruled, 0 infeasible, at 2, 6, 12, 16 (all big-read); B2BB_ALL: 7 of 7, at 2, 4, 6, 12, 14, 16, 22 (0.857
    big-read);
  - rows with 4+ from the QB's game: LIVE_CB 8.3, B2BB4 12.3, B2BB_ALL 15.3; B rows with 2+ bring-backs 0 / 4 / 7;
  - projection per row −0.08 / −0.14; rows shared with LIVE_CB 4.7 / 3.7; dealt identical 0.000 / 0.000.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 41 lines and 3 sections; only
  those were read.
- **The binding (support) census:** the reviewer's, on all 53 slate-banks of bank 1406, before the freeze.
- **Code:** nfl2 `production/s76-b2bb-20261008` @ `63b39df` (the outside reviewer's draft; branched from study 75's):
  - `experiments/s76_b2bb.py` `64509afa…`;
  - `scripts/s76_drive.py` `13772673…`;
  - `scripts/s76_census.py` `6114487a…`;
  - **`scripts/s76_report.py` (the reader) `0e436117…`**;
  - `tests/test_s76_b2bb.py` `9b121e5b…` (6 tests);
  - unchanged and sha-asserted: `s73_topg_qb1.py` `3f76c629…` (its pinned `s48_winner_like.py` `c22d2811…`,
    `s53_cheap_pref.py` `f3f9d735…`), `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`; the plan
    `ac10ddf6…`.
