# Preregistration: study 82, a QB from the lower-implied half of the slate on the first 4 book rows, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (02:10 CDT)** by the outside reviewer, before any scored bank. The reviewer (84) reviews, runs the
binding census and FREEZES; the laptop acks (shas, tests, census re-run, banks and seed scanned).
- **Banks 1695–1700, seed 20261127** (assigned by the reviewer; 1701–1706 skipped as old production seeds; the laptop scans the
  banks and the derived bases 1745–1750 / 2395–2400).
- **Target:** tonight's second round, after study 81. A production option only if LOWQB4 is ENTERABLE and the operator
  chooses it in the morning.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night:** "try as many things as we can, and then I'll make some decisions in the morning."
- **What the outside reviewer measured** (the 2026 W1–4 Millionaires, top 1% vs the field, weeks equally weighted; aggregates
  only; `~/private/winner-shapes-2026/scan4.py`): the lineup's QB is from a team ranked 13th or lower by median implied team
  total among the slate's QB teams:

| | W1 | W2 | W3 | W4 | Mean |
|---|---|---|---|---|---|
| Top 1% | 0.44 | 0.23 | 0.64 | 0.35 | **0.41** |
| Field | 0.28 | 0.30 | 0.27 | 0.26 | 0.28 |

  - The top 1% take a lower-half QB about 1.5 times as often as the field, higher in 3 of 4 weeks (not W2).
  - The mirror: a QB from the top-5 implied totals, top 26% vs field 36%.
  - His W5-style book (W4 inputs, FP): **25 of 26 rows take an upper-half QB** — the laptop's W4 rate check, 10-09 (§4).
- **THE PRIOR, STATED FIRST: NEGATIVE.** Every study that forced the QB choice read at or below his book (verbatim, from
  their READs):
  - study 73 (Addendum 171), TOPG5_QB1, the favourite side's QB + his top pass catcher in the top games: −0.03625
    [−0.07320, +0.00059], both seasons negative; 2022 +0.02100;
  - study 74 (Addendum 172), STACK4_B, the full game stack in the top 4 games: −0.02934 [−0.06230, +0.00353]; 2022 +0.02138;
  - study 80 (Addendum 178), DOGQB8, the underdog's QB in a top-4 game: −0.00447 [−0.04499, +0.03483], guard 1 failed,
    seats ×0.83; 2022 −0.04341, CONTRADICTED; its mirror FAVQB8 −0.03790.
  - Those forced QBs INTO the high-total games. This study forces them AWAY from the high totals — the direction none of them
    tested and the one the winners lean to. The projection cost is real (weaker offenses, §4); the read decides whether the
    top 1%'s 41% is a lean worth taking or survivorship (the winning low-total QBs are the ones that boomed).

## 2. Arms (`experiments/s82_lowqb.py`)
**The book:** study 48's harness through study 80's module (`s80_dogqb.py` `9a46c284…`, sha-asserted; study 73
`3f76c629…` underneath). LIVE = 48d's 41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6
(`plan-week5-rev6-s24.json` `ac10ddf6…`).
- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE HALVES:** the pool's QB teams with a finite median `implied_team_total` over the pool's rows, ranked by that median
  descending (ties: the team code); the UPPER half is ranks 1..ceil(n / 2), the LOWER half the rest. A team without an implied
  total is in neither half (its QBs are banned on the ruled solves). The ALLOWED set is every pool QB of a lower-half team
  (backups included; the objective picks among them).
- **O-62 does not touch it:** the rule reads `implied_team_total`, never `spread` (O-62 is the live frame's `spread` sign; the
  history frames' implied totals are consistent with their totals, and the live T-70 frame's `implied_team_total` is
  unaffected).
- **THE ROWS:** the first 4 BOOK solves in BUILD ORDER, any cell, through study 80's own `qb_side_rows` (imported, not
  copied): each solve bans every pool QB outside the allowed set (extra bans); the cells' stacking rules are unchanged, so the
  lineup stacks its lower-half QB as its cell says. A solve carries the rule while j < 4; an infeasible ruled solve is re-solved
  plain and recorded (not retried). Spares never.
- **LOWQB4 (THE DECISION):** the first 4 book solves (15% of the book; the top 1% − his book gap is about 37 points, so 4
  rows is a deliberate first dose, not the whole gap).
- **EXPLORATORY LOWQB8:** the first 8.
- **PRODUCTION'S EQUIVALENT (for §5):** `mix_rows`' peek takes extra bans (as study 80's); the halves from the T-70 frame's
  implied_team_total.
- **DEALING:** the first 4 book solves sit at book positions 0, 2, 3, 5 (his W4 book and the harness alike), all read by big
  contests (Rev6: 0–21).

## 3. Endpoint and rule (the reader `scripts/s82_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`): load, mean_contests, boot, verdict, go / no-go and trial
  identical (a test asserts it); the names, the seed, the docstring and the secondaries (upper / lower-half QB rows, QB
  salary, distinct QBs) differ.
- **THE READ: 2023–24** (36 slates). LOWQB4 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2; two-sided
  0.95, B 20,000.
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's). One decision arm, so no multiplicity. One construction change a week.
- **EXPLORATORY:** LOWQB8 − LIVE_CB; each arm on l02; P(≥ 2); the upper / lower-half QB rows; the QB salary; distinct QBs;
  the QB + 2 rows; the ruled solves built plain.

## 4. Binding, on his real book and in the harness (the reviewer's conditions)
- **His real book — the laptop's W4 rate check, 10-09** (read-only on the OFF book `a4ab2839`; commit index → position from
  the receipt): 4 of the first 4 committed rows take an upper-half QB — j0 → position 0 (JAX, implied 24.50), j1 → position 2
  (JAX), j2 → position 3 (CIN, 27.00), j3 → position 5 (MIN, 24.25); book-wide 25 of 26 upper-half. (The laptop split at the
  median over all 24 frame teams, 22.88; this study's definition — the pool's QB teams, rank > ceil(n / 2) — is confirmed by
  the census; these four are well above either cut.) **The rule binds on every ruled row of his book.**
- **The harness (the smoke; the binding census on 53 slate-banks is the reviewer's):**
  - VACUITY: LIVE_CB takes an UPPER-half QB in 3.33 of the 4 rows at LOWQB4's ruled positions (his book: 4 of 4) — the rule
    binds;
  - QB teams ranked per slate-bank 21.3 (upper half 10.7); lower-half pool QBs allowed 26.0; no slate-bank with a QB team
    lacking an implied total;
  - the ruled QBs' team ranks (LOWQB4, 12 rows): 11 ×2, 12, 13 ×2, 14, 16 ×2, 19, 24 ×3 — every one above its slate's
    ceil(n / 2) (asserted); each his team's starter (1.000); LOWQB8 likewise (starters 1.000);
  - upper-half QB rows per book: LIVE_CB 21.7, LOWQB4 19.0, LOWQB8 17.7 (lower-half 4.3 / 7.0 / 8.3);
  - THE PROJECTION COST, SMALL: −0.08 per row (LOWQB4) / −0.14 (LOWQB8); QB salary $6,612 → $6,527 → $6,467; distinct QBs
    8.0 → 8.7 → 9.0; QB + 2 rows 12 in every arm; dealt identical to LIVE_CB 0.000 / 0.000; rows shared with LIVE_CB 1.3 / 1.0.
- **Path dependence:** the rows re-draw the rest of the book.
- **The base is our simulator's mean, not FP's. The lines are closing lines.**

## 5. What a verdict can do
- **LOWQB4 ENTERABLE:** a production option (the outside reviewer's: extra bans on the first 4 book solves in build order, the
  halves from the T-70 frame's implied_team_total), with its format agreed first, parity-tested against this study's frozen
  functions, the laptop's review, merged before FRIDAY_HEAD only after his morning decision (default OFF), Friday's A3 ON run,
  his choice at Saturday's arming.
- **Otherwise, or if any step is not clean by Friday evening:** W6, or closed.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s82-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10): every arm is 41 rows within production's constraints (13 / 6, QB 5,
  overlap 4), with 8 term rows and every row in the pool; LOWQB4 4 of 4 ruled, 0 infeasible, at 0, 2, 3, 5 (all big-read);
  LOWQB8 8 of 8, 0 infeasible, at 0, 2, 3, 5, 6, 7, 9, 10 (all big-read); `results_bank1406.jsonl` `2282bec0…`; the rest as §4.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 41 lines and 3 sections; only those were read.
- **The binding (support) census:** the reviewer's, on all 53 slate-banks of bank 1406, before the freeze.
- **Code:** nfl2 `production/s82-lowqb-20261009` @ `83457fe5` (the outside reviewer's draft; branched from study 81's
  `9cde705f`):
  - `experiments/s82_lowqb.py` `cbf667d2…`;
  - `scripts/s82_drive.py` `bb452e40…`;
  - `scripts/s82_census.py` `334be27a…`;
  - **`scripts/s82_report.py` (the reader) `74a3914d…`** (seed 20261127);
  - `tests/test_s82_lowqb.py` `2680c37a…` (6 tests);
  - unchanged and sha-asserted: `s80_dogqb.py` `9a46c284…` (its `qb_side_rows` and `starters` imported; its
    `s73_topg_qb1.py` `3f76c629…`, and through it `s48_winner_like.py` `c22d2811…`, `s53_cheap_pref.py` `f3f9d735…`),
    `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`; the plan `ac10ddf6…`.
