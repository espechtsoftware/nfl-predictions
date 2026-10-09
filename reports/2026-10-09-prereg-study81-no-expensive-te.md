# Preregistration: study 81, no expensive tight end (priced $5,000 or more) on the first 8 book rows, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (02:02 CDT)** by the outside reviewer, before any scored bank. The reviewer (84) reviews, runs the
binding census and FREEZES; the laptop acks (shas, tests, census re-run, banks and seed scanned).
- **Banks 1689–1694, seed 20261126** (assigned by the reviewer; the laptop scans the banks and the derived bases 1739–1744 /
  2389–2394).
- **Target:** tonight's second round. A production option only if NOTE5K8 is ENTERABLE and the operator chooses it in the
  morning.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night:** "try as many things as we can, and then I'll make some decisions in the morning."
- **What the outside reviewer measured** (the 2026 W1–4 Millionaires, top 1% vs the field, weeks equally weighted; aggregates
  only; `~/private/winner-shapes-2026/scan4.py`): a TE priced ≥ $5,000 per lineup:

| | W1 | W2 | W3 | W4 | Mean |
|---|---|---|---|---|---|
| Top 1% | 0.09 | 0.04 | 0.07 | 0.29 | **0.12** |
| Field | 0.18 | 0.16 | 0.21 | 0.55 | 0.28 |

  - The top 1% hold an expensive TE about half as often as the field, BELOW the field in 4 of 4 weeks.
  - His W5-style book (W4 inputs, FP): **11 of 26 rows** (0.42) — the laptop's W4 rate check, 10-09 (below).
- **THE TENSION, STATED FIRST (the reviewer's condition).** On 10-07 the operator asked for MORE QB + TE stacking ("perhaps
  consider a percentage of our lineups to have a QB tight end stack" and "a bonus to the tight end"). This rule fades the
  expensive TE, which is often the stack TE. What was tested on his ask:
  - study 63 (Addendum 166): TE bonus blocks (TE2_B8, TETOUGH2_B8, CHEAPTE2_B8) all NO DIFFERENCE leaning slightly positive;
    the forced QB + TE share (QBTE_SHARE) leaned against;
  - study 38 amendment 6k: the three TE blocks as PAPER arms on the real field (being read).
  - None restricted the TE's PRICE. This study does; the census reports the QB + TE stack rows in every arm (§4).
- **The prior, stated first:** NO DIFFERENCE.

## 2. Arms (`experiments/s81_note5k.py`)
**The book:** study 48's harness through study 80's module (`s80_dogqb.py` `9a46c284…`, sha-asserted; study 73
`3f76c629…` underneath). LIVE = 48d's 41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6
(`plan-week5-rev6-s24.json` `ac10ddf6…`).
- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE BANNED SET:** every pool TE priced ≥ $5,000 (`salary`; a missing salary counts as 0, never expensive).
- **THE ROWS:** the first 8 BOOK solves in BUILD ORDER, any cell (study 75's / 80's rows). Each adds the banned set to its
  extra bans (study 80's machinery with a fixed set). A solve carries the rule while j < 8; an infeasible ruled solve is
  re-solved plain and recorded (not retried). Spares never.
- **NOTE5K8 (THE DECISION):** the first 8 book solves.
- **EXPLORATORY NOTE5K_ALL:** every book solve (26); 4 of them are dealt at non-big indices.
- **PRODUCTION'S EQUIVALENT (for §5):** `mix_rows`' peek takes extra bans (study 43's cover_games bans QBs this way); the set
  from the T-70 frame's salary.
- **DEALING:** the smoke put the 8 ruled rows at book positions 0, 2, 3, 5, 6, 7, 9, 10, all read by big contests (Rev6:
  0–21). His W4 book's first 8 commits sit at the same positions.

## 3. Endpoint and rule (the reader `scripts/s81_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`): load, mean_contests, boot, verdict, go / no-go and trial
  identical (a test asserts it); the names, the seed, the docstring and the secondaries ($5k+ TE rows, QB + TE stack rows)
  differ.
- **THE READ: 2023–24** (36 slates). NOTE5K8 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2;
  two-sided 0.95, B 20,000.
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's). One decision arm, so no multiplicity. One construction change a week.
- **EXPLORATORY:** NOTE5K_ALL − LIVE_CB; each arm on l02; P(≥ 2); the $5k+ TE rows; the QB + TE stack rows; the QB + 2
  rows; the ruled solves built plain.

## 4. Binding, on his real book and in the harness (the reviewer's conditions)
- **His real book — the laptop's W4 rate check, 10-09** (read-only on the OFF book `a4ab2839`; commit index → position from
  the receipt): 3 of the first 8 committed rows hold a TE ≥ $5,000 — j2 → position 3 (C, $5,100), j3 → position 5 (A2,
  $6,500), j4 → position 9 (A1, $6,500); the other five at positions 0 / 2 / 6 / 7 / 10. Book-wide 11 of 26. **The rule binds
  on his book.**
- **The harness (the smoke, 3 slate-banks; the binding census on 53 is the reviewer's):**
  - VACUITY: LIVE_CB holds a $5k+ TE in 3.67 of the 8 rows at NOTE5K8's ruled positions (his book: 3 of 8) — the dose
    transfers;
  - pool TEs per slate-bank 48.7, of them ≥ $5,000 3.7 (banned); no slate-bank without one;
  - $5k+ TE rows per book: LIVE_CB 10.0, NOTE5K8 8.67, NOTE5K_ALL 0.0. **NOTE5K8 mostly MOVES the expensive TEs out of the
    first 8 rows into later rows** (book-wide −1.3) rather than out of the book; NOTE5K_ALL removes them;
  - QB + TE stack rows: 15.0 / 14.0 / 12.7; flex (WR / TE / RB) 4.3 / 15.7 / 6.0 → 4.3 / 15.3 / 6.3 → 6.3 / 12.7 / 7.0;
  - projection per row −0.01 (NOTE5K8) / −0.57 (NOTE5K_ALL); dealt identical to LIVE_CB 0.333 / 0.333 (on one of the three
    slate-banks the first 8 rows held no expensive TE).
- **Path dependence:** the rows re-draw the rest of the book (the smoke shared 8.7 of 26 rows with LIVE_CB).
- **The base is our simulator's mean, not FP's. The lines are closing lines.**

## 5. What a verdict can do
- **NOTE5K8 ENTERABLE:** a production option (the outside reviewer's: extra bans on the first 8 book solves in build order,
  the set from the T-70 frame's salary), with its format agreed first, parity-tested against this study's frozen functions,
  the laptop's review, merged before FRIDAY_HEAD only after his morning decision (default OFF), Friday's A3 ON run, his choice
  at Saturday's arming. Given §1's tension, the morning sheet says plainly what it does to his QB + TE stacks.
- **Otherwise, or if any step is not clean by Friday evening:** W6, or closed.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s81-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `f41df9c3…`): every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every
  row in the pool; NOTE5K8 8 of 8 ruled, 0 infeasible, at 0, 2, 3, 5, 6, 7, 9, 10 (all big-read); NOTE5K_ALL 26 of 26, 0
  infeasible, 0.846 big-read; the rest as §4.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 41 lines and 3 sections; only
  those were read.
- **The binding (support) census:** the reviewer's, on all 53 slate-banks of bank 1406, before the freeze.
- **Code:** nfl2 `production/s81-note5k-20261009` @ `9cde705f` (the outside reviewer's draft; branched from study 80's
  `9a9ee47b`, which carries every LEDGER row through 80 and 79's correction):
  - `experiments/s81_note5k.py` `b37dbbc9…`;
  - `scripts/s81_drive.py` `d02fdd6a…`;
  - `scripts/s81_census.py` `6fc407ac…`;
  - **`scripts/s81_report.py` (the reader) `bfa1b23b…`** (seed 20261126);
  - `tests/test_s81_note5k.py` `4aec215f…` (8 tests);
  - unchanged and sha-asserted: `s80_dogqb.py` `9a46c284…` (its `s73_topg_qb1.py` `3f76c629…`, and through it
    `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`), `term_book.py` `62c2306e…`, production's
    `enter_layout.py` `3cb051ac…`; the plan `ac10ddf6…`.
