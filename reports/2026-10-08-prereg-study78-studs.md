# Preregistration: study 78, stars and scrubs -- two $8,000+ players on the first 8 book rows, in the harness (DRAFT 2026-10-08)

**Status: DRAFT 2026-10-08 (21:36 CDT)** by the outside reviewer, before any scored bank. The reviewer (84) reviews, runs
the binding census and FREEZES; the laptop acks (shas, tests, census re-run, banks and seed scanned).
- **Banks 1665–1670, seed 20261123** (assigned by the reviewer; the laptop scans).
- **Target:** tonight, after study 77 (about 01:30–02:00). A production option only if STUDS2_8 is ENTERABLE and the
  operator chooses it in the morning.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night:** "please look at the patterns of the winners over the past few weeks and consider a
  variety of different tests we can do throughout the night."
- **What the outside reviewer measured** (the 2026 W1–4 Millionaires, top 1% vs the field, weeks equally weighted;
  aggregates only; `~/private/winner-shapes-2026/scan2.py`):
  - players priced ≥ $8,000: 0.88 vs 0.66 per lineup (higher at the top in 3 of 4 weeks);
  - players under $4,000: 1.16 vs 0.82 (4 of 4);
  - salary left: $111 vs $128 (the top spends more, 4 of 4);
  - his W5-style book (W4 inputs, FP): 0.54 players at $8,000+, 1.00 under $4,000, $35 left.
- **What was tested before:** neither ledger has a studs test. Addendum 91 (the salary floor is not load-bearing) is about
  total spend. The nearest is **study 70's CHEAPEXPWR2_B8 (Addendum 168)**: +2 projected points to a team's top WR priced
  $7,000+ OR to a cheap player, in an 8-row block; −3.4 on 2023–24, +3.2 on 2022, ENTERABLE only at the edge, not
  recommended. **Study 78 differs:** any position, a hard constraint (≥ 2 such players in the row), not a bonus, and on
  the first-built rows rather than the term block.
- **The scrubs side is already live:** the cheap +2 block is kept in every arm; this study adds the stars.
- **The prior, stated first:** NO DIFFERENCE.

## 2. Arms (`experiments/s78_studs.py`)
**The book:** study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted through study 73 `3f76c629…`). LIVE = 48d's
41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`).
- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE STUD SET:** every pool player of ANY position priced ≥ $8,000. A DST would count; none is ever priced there.
- **THE ROWS:** the first 8 BOOK solves in BUILD ORDER, any cell (study 75's rows). A solve carries the rule while j < 8;
  an infeasible ruled solve is re-solved plain and recorded (not retried). Spares never.
- **STUDS2_8 (THE DECISION):** those 8 solves hold at least TWO stud-set players: the lab optimizer's `set_constraints`
  [(stud ids, ">=", 2)].
- **EXPLORATORY STUDS1_8:** at least ONE.
  - **Why it is not the decision (outcome-blind, before any scored bank, as the reviewer asked):** the smoke found
    LIVE_CB already holding a $8,000+ player in 6 of the 8 rows at the ruled positions; STUDS1_8 left the studs per row
    unchanged (0.92 → 0.91) and was dealt identically to LIVE_CB on 1 of 3 slate-banks.
- **PRODUCTION'S EQUIVALENT (for §5):** production's pinned optimize (nfl2 `f69598b`) takes `member_bounds`: (the same ids,
  2, 9). A member_bounds vs set_constraints parity test on fixtures is a condition of live use (study 75's §5).
- **DEALING:** the smoke put the 8 ruled rows at book positions 0, 2, 3, 5, 6, 7, 9, 10, all read by big contests (Rev6:
  0–21).

## 3. Endpoint and rule (the reader `scripts/s78_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`): load, mean_contests, boot, verdict, go / no-go and trial
  identical (a test asserts it); the names, the seed, the docstring and the secondaries (studs and cheap players per row,
  salary left) differ.
- **THE READ: 2023–24** (36 slates). STUDS2_8 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2;
  two-sided 0.95, B 20,000. **Banks 1665–1670, seed 20261123.**
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's). One decision arm, so no multiplicity. One construction change a week.
- **EXPLORATORY:** STUDS1_8 − LIVE_CB; each arm on l02; P(≥ 2); studs and cheap players per row; studs by position; salary
  left; the QB + 2 rows; the ruled solves built plain.

## 4. What the harness can and cannot say
- **THE TRANSFER CAVEAT (the most important line here).** The harness's base is our simulator's mean, not FP's, and its
  LIVE_CB already plays 0.92 $8,000+ players per row and 1.78 under $4,000 (the smoke), about the top 1%'s 0.88 and above
  its 1.16. His real FP book plays 0.54 and 1.00. So in the harness STUDS2_8 tests going ABOVE the top-1% level (1.12 per
  row); the production gap (0.54 → about 0.9) is not reproduced. A read here does not transfer directly to his FP book.
- **Path dependence:** the ruled rows re-draw the rest of the book (the smoke shared 1.3 of 26 rows with LIVE_CB).
- **The lines are closing lines.**

## 5. What a verdict can do
- **STUDS2_8 ENTERABLE:** given §4, the outside reviewer would first measure what the rule does to his FP book (a W4 replay
  of the studs per row) before any production option; then, if he chooses it, the option (member_bounds on the first 8
  book solves, study 73's machinery) with its format agreed first and the parity condition, the laptop's review, merged
  before FRIDAY_HEAD only after his decision (default OFF), Friday's A3 ON run, his choice at Saturday's arming.
- **Otherwise, or if any step is not clean by Friday evening:** W6, or closed.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s78-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `032c7b89…`):
  - every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every row in the
    pool;
  - STUDS2_8 and STUDS1_8: 8 of 8 ruled, 0 infeasible, at 0, 2, 3, 5, 6, 7, 9, 10 (all big-read);
  - VACUITY: LIVE_CB holds a $8,000+ player in 6.0 of the 8 rows at the ruled positions;
  - $8,000+ per row 0.92 / 1.12 / 0.91 (LIVE_CB / STUDS2_8 / STUDS1_8); under $4,000 per row 1.78 / 1.90 / 1.77; salary left
    $28 / $46 / $27; studs by position (book) RB 12.3 / 13.7 / 13.0, WR 9.3 / 13.7 / 9.0, QB 2.3 / 1.7 / 1.7, TE and DST 0;
  - projection per row −0.26 (STUDS2_8) / +0.05 (STUDS1_8); rows shared with LIVE_CB 1.3 / 10.3; dealt identical 0.000 /
    0.333.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 41 lines and 3 sections; only
  those were read.
- **The binding (support) census:** the reviewer's, on all 53 slate-banks of bank 1406, before the freeze.
- **Code:** nfl2 `production/s78-studs-20261008` @ `0f33bbf0` (the outside reviewer's draft; branched from study 77's):
  - `experiments/s78_studs.py` `5af7c50f…`;
  - `scripts/s78_drive.py` `40ff4a13…`;
  - `scripts/s78_census.py` `188a23fb…`;
  - **`scripts/s78_report.py` (the reader) `b7287931…`**;
  - `tests/test_s78_studs.py` `c68da560…` (5 tests);
  - unchanged and sha-asserted: `s73_topg_qb1.py` `3f76c629…` (its pinned `s48_winner_like.py` `c22d2811…`,
    `s53_cheap_pref.py` `f3f9d735…`), `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`; the plan
    `ac10ddf6…`.
