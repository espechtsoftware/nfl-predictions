# Preregistration: study 74, the full game stack (a QB, his top pass catcher and the opponent's top receiver) in each top game, in the harness (DRAFT 2026-10-08)

**Status: DRAFT 2026-10-08** by the reviewer, written after the code's smoke and before the binding census and any
scored bank. The binding census runs after study 73's scored run finishes, so the two do not compete for the machine.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night,** on studies 71 / 73: "Is it the quarterback of the highest projected team with his top
  receiver and the top receiver from the other team, or was there more to it?"
  - Study 71 forced only the opponent's top-salaried WR as the bring-back, on whatever QB the solver chose.
  - Study 73 forces a QB with his top pass catcher.
- **Asked whether to test his full form,** he chose "Test it tonight, after 73". It combines 71's and 73's mechanisms.
- **The prior, stated first: NO DIFFERENCE or leaning negative.**
  - Study 71 was neutral (read −1.9, 2022 +5.5; Addendum 169).
  - Study 71b was slightly negative (Addendum 170).
  - Study 43, stacks in the top games, was −2.8 (Addendum 147).

## 2. Arms (`experiments/s74_game_stack.py`)
**The book:** study 48's harness (LIVE = 48d's 41 rows with the cheap +2 block through study 53's `block_term` /
`term_book`; Rev6 `ac10ddf6…`). Study 73's module is imported with its sha asserted (`3f76c629…`).

- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE GAMES and THE QB:** study 73's.
  - `S73.game_order`: game_total descending, game_id ascending, over the games with a QB in the pool.
  - The side with the higher team implied total (ties: that side's top-QB projection, then the team code); that side's
    QB by projection, then id.
- **HIS TOP PASS CATCHER (PC_k)** and **THE OPPONENT'S TOP RECEIVER (OPC_k):** one definition on both sides. The team's
  highest-PROJECTED WR or TE in the pool (ties: the higher salary, then the id). "Projection" is the build's objective
  base (player_mean).
  - This is not study 70/71's highest-salaried WR. On W4 both definitions pick Lamb and Collins (the outside reviewer's
    check).
  - A game missing a WR / TE on either side is skipped before the build (no backfill).
- **THE SHAPE:** cell B as it stands. QB + exactly one pass catcher (`qb_stack_min` / `max` 1) + a bring-back
  (`bring_back_min` 1), at most 3 players from the QB's game, plus B's second-game pair.
- **THE FORCE:** the pinned optimizer's TRIPLE interaction floor {(QB_k, PC_k, OPC_k): 1.0}, floor 1.0. The pinned
  `optimize` accepts 2–3-player tuples.
  - With at most 3 from the game, the game holds exactly those three: his one pass catcher is PC_k and the bring-back is
    OPC_k.
- **THE ROWS:** the first G BOOK solves of cell B in build order (j < K_book). Each consumes the next triple from its
  attempt.
  - The harness checks the three players are in the builder's records before flooring.
  - An infeasible floored solve is re-solved plain, recorded, and the game dropped (not retried).
  - Spares never.
- **STACK4_B (the single DECISION):** G = 4.
  - **Why 4, decided at the smoke before any scored bank:** cell B's first five book rows are dealt at book positions 2,
    6, 12, 16 and 22 under Rev6.
  - Index 22 is read only by a non-big supersat (study 72's trap), so four is the most game stacks cell B can put in
    big seats.
  - The original proposal was G = 5.
- **EXPLORATORY STACK5_B:** G = 5, with its 5th stack in the supersat seat.

## 3. Endpoint and rule (the reader `scripts/s74_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`). Its load, boot, verdict, go / no-go and trial functions are
  identical, which a test asserts. The names, the seed, the docstring, the definitions line (study 73's sha twice, in the
  slots of study 48's and 53's, which study 73 pins), the secondaries and the forced-solve lines differ.
- **THE READ: 2023–24** (36 slates). STACK4_B − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2.
  - The interval is two-sided 0.95, with B 20,000.
  - **Banks 1641–1646, seed 20261119** (to be scanned by the laptop before the freeze).
- **THE GO / NO-GO: 2022** (study 51's rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's), with one decision arm and no multiplicity.
- **One construction change a week:** if more than one of tonight's studies is ENTERABLE, he picks one. The laptop's arm
  guard enforces it.

## 4. What the harness can and cannot say
- **Path dependence:** the forced rows are built early, so the rest of the book re-draws. The smoke shared 2.3 of 26 rows
  with LIVE_CB.
- **Vacuity:** LIVE_CB already holds 1.3 of the 5 top-game triples somewhere in the book (the smoke).
- **The base is our simulator's mean, not FP's.** The lines are closing lines.

## 5. What a verdict can do (the laptop's cut-off)
- **STACK4_B ENTERABLE:** the outside reviewer's production option (study 73's flag extended to a B-only triple),
  parity-tested against this harness's frozen functions; the laptop's review; merged before FRIDAY_HEAD (default OFF);
  Friday's A3 ON run; his choice at Saturday's arming.
- **Otherwise, or if any step is not clean by Friday evening:** W6.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406, never a decision bank; Rev6; `~/s74-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10;
  the arms then STACK5_B and STACK3_B):
  - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
  - 5 of 5 / 3 of 3 forced, 0 infeasible;
  - STACK5_B's forced rows were at book positions 2, 6, 12, 16, 22 (0.8 read by big contests), which set G = 4;
  - triples held: LIVE_CB 1.3 of 5, STACK5_B 5.0;
  - QB + 2 rows 12 of 26 in every arm;
  - projection cost −0.29 (STACK5) / −0.14 (STACK3) per row;
  - rows shared with LIVE_CB 2.3 / 3.0.
- **The full-path smoke** (2024 W10 and 2022 W6 scored on bank 1406, the final arms): the reader exited 0 with its 3
  sections. Only the exit code, the line count and the section count were read.
- **The binding census:** to follow, after study 73's run.
- **Code:** nfl2 `production/s74-game-stack-20261008` @ `542b422`:
  - `experiments/s74_game_stack.py` `aa3645cd…`;
  - `scripts/s74_drive.py` `fdc8ddd5…`;
  - `scripts/s74_census.py` `fe8df429…`;
  - **`scripts/s74_report.py` (the reader) `0b23e10e…`**;
  - `tests/test_s74_game_stack.py` `02030ed6…` (6 tests);
  - unchanged and sha-asserted: `s73_topg_qb1.py` `3f76c629…` (which pins s48 / s53 / s56), `term_book.py` `62c2306e…`,
    production's `enter_layout.py` `3cb051ac…`;
  - the plan: `ac10ddf6…`.
