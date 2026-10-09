# Preregistration: study 80, the underdog's QB in a top-4 game on the first 8 book rows, in the harness (DRAFT 2026-10-08)

**Status: DRAFT 2026-10-08 (22:23 CDT)** by the outside reviewer, before any scored bank. The reviewer (84) reviews, runs
the binding census and FREEZES; the laptop acks (shas, tests, census re-run, banks and seeds scanned).
- **Banks 1683–1688, seed 20261125** (assigned by the reviewer; the laptop scans the banks and the derived bases 1733–1738 /
  2383–2388).
- **Target:** tonight, after study 79 (the laptop's 02:00–07:00 window). A production option only if DOGQB8 is ENTERABLE
  and the operator chooses it in the morning.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night:** "please look at the patterns of the winners over the past few weeks and consider a
  variety of different tests we can do throughout the night."
- **What the outside reviewer measured** (the 2026 W1–4 Millionaires, weeks equally weighted; aggregates only;
  `~/private/winner-shapes-2026/scan3b.py`). The lineup's QB, by his game's total rank and his team's side:

| QB | Top 1% | Field | His W5-style book (FP) |
|---|---|---|---|
| the UNDERDOG in a top-4 game | **32%** (W1 37, W2 6, W3 60, W4 25) | 22% | 23% |
| the FAVOURITE in a top-4 game | 32% | 28% | **42%** |
| the underdog outside the top 4 | 12% | 11% | 0% |

  - The top 1% take the underdog's QB in a top-4 game about 1.5 times as often as the field (higher in 3 of 4 weeks);
    his book leans to the favourite.
  - More broadly the top 1% hold the favourite's QB 55% vs the field's 67%, and a QB from a top-5 implied total 26% vs
    36%; his book 77% and 38%.
- **What was tested before:** studies 73 (TOPG5_QB1, −3.6) and 74 (STACK4_B, −2.9) forced the FAVOURITE side's QB of the
  top games; both read NO DIFFERENCE leaning negative. No study has forced the underdog's side.
  - **Not a clean mirror of 73 / 74 (the reviewer's point):** 73 / 74 forced the favourite's QB AND his top pass catcher(s)
    (74 also the opponent's top receiver); study 80 constrains only the QB's side and leaves the stack to the cell's rules.
    The clean contrast is inside this study: FAVQB8, the same rule on the favourite's side.
- **The prior, stated first:** NO DIFFERENCE.

## 2. Arms (`experiments/s80_dogqb.py`)
**The book:** study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted through study 73 `3f76c629…`). LIVE = 48d's
41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`).
- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE GAMES:** study 73's frozen `game_order` (game_total descending, game_id ascending, over the games with a QB in the
  pool); the top 4.
- **THE SIDE:** in each of those games, the team with the LOWER (underdog) median `implied_team_total` over the pool's rows;
  a tie is neither side (a pick-em game contributes no QB). The ALLOWED set is every pool QB of those teams (backups
  included; the objective picks among them).
- **THE ROWS:** the first 8 BOOK solves in BUILD ORDER, any cell (study 75's rows). Each solve bans every pool QB outside
  the allowed set (extra bans; the cells' stacking rules are unchanged, so the lineup stacks the underdog QB as its cell
  says). A solve carries the rule while j < 8; an infeasible ruled solve is re-solved plain and recorded (not retried).
  Spares never.
- **DOGQB8 (THE DECISION):** the underdog side.
- **EXPLORATORY FAVQB8:** the mirror, the favourite side, which separates "a top-4 game's QB" from "the underdog's QB".
- **PRODUCTION'S EQUIVALENT (for §5):** `mix_rows`' peek takes extra bans (study 43's cover_games bans QBs this way); the
  sides from the T-70 frame's implied_team_total, as study 73's flag already computes it.
- **DEALING:** the smoke put the 8 ruled rows at book positions 0, 2, 3, 5, 6, 7, 9, 10, all read by big contests (Rev6:
  0–21).

## 3. Endpoint and rule (the reader `scripts/s80_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`): load, mean_contests, boot, verdict, go / no-go and trial
  identical (a test asserts it); the names, the seed, the docstring and the secondaries (underdog / favourite top-4 QB rows,
  distinct QBs) differ. The arms line prints the side rule's constants without the per-slate allowed sets.
- **THE READ: 2023–24** (36 slates). DOGQB8 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2;
  two-sided 0.95, B 20,000.
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's). One decision arm, so no multiplicity. One construction change a week.
- **EXPLORATORY:** FAVQB8 − LIVE_CB; each arm on l02; P(≥ 2); the underdog / favourite top-4 QB rows; distinct QBs; the
  QB + 2 rows; the ruled solves built plain.

## 4. What the harness can and cannot say
- **The gap transfers:** the harness's LIVE_CB takes an underdog top-4 QB in 5.0 of 26 rows (19%) and a favourite in 8.0
  (31%), the same lean as his FP book (23% / 42%); DOGQB8 takes the underdog share to 8.7 (33%), about the top 1%'s 32%.
- **Vacuity:** LIVE_CB already takes an underdog top-4 QB in 1.7 of the 8 ruled rows, so the rule changes about 6.
- **Path dependence:** the rows re-draw the rest of the book (the smoke shared 1.0 of 26 rows with LIVE_CB).
- **The week-to-week spread is large** (W2's top 1% held the underdog only 6%, W3's 60%); the harness reads 36 slates.
- **The base is our simulator's mean, not FP's. The lines are closing lines.**

## 5. What a verdict can do
- **DOGQB8 ENTERABLE:** a production option (the outside reviewer's: extra bans on the first 8 book solves in build order,
  the sides from the T-70 frame), with its format agreed first, parity-tested against this study's frozen functions, the
  laptop's review, merged before FRIDAY_HEAD only after his morning decision (default OFF), Friday's A3 ON run, his choice
  at Saturday's arming.
- **Otherwise, or if any step is not clean by Friday evening:** W6, or closed.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s80-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `8cd31890…`):
  - every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every row in the
    pool;
  - DOGQB8 and FAVQB8: 8 of 8 ruled, 0 infeasible, at 0, 2, 3, 5, 6, 7, 9, 10 (all big-read);
  - allowed QBs per slate-bank: DOG 9.0, FAV 8.7 (backups included); every ruled row's QB was his team's starter (the
    highest-base pool QB): DOG 1.000, FAV 1.000;
  - underdog / favourite top-4 QB rows: LIVE_CB 5.0 / 8.0, DOGQB8 8.7 / 7.0, FAVQB8 5.3 / 9.3; distinct QBs 8.0 / 8.0 / 8.3;
  - projection per row −0.21 (DOGQB8) / −0.14 (FAVQB8); rows shared with LIVE_CB 1.0 / 1.3; dealt identical 0.000 / 0.000.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 41 lines and 3 sections; only
  those were read.
- **The binding (support) census:** the reviewer's, on all 53 slate-banks of bank 1406, before the freeze.
- **Code:** nfl2 `production/s80-dogqb-20261008` @ `22098074` (the outside reviewer's draft; branched from study 79's; `22098074`
  added the census's starter line):
  - `experiments/s80_dogqb.py` `9a46c284…`;
  - `scripts/s80_drive.py` `bb434119…`;
  - `scripts/s80_census.py` `7f344047…`;
  - **`scripts/s80_report.py` (the reader) `815d8f68…`** (seed 20261125);
  - `tests/test_s80_dogqb.py` `5ddbf250…` (7 tests);
  - unchanged and sha-asserted: `s73_topg_qb1.py` `3f76c629…` (its game_order; its pinned `s48_winner_like.py`
    `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`), `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`;
    the plan `ac10ddf6…`.
