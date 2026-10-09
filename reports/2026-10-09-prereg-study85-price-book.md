# Preregistration: study 85, his whole-book price rules (TE ≤ $5,000, DST ≤ $3,000, exactly one WR ≤ $4,500, no TE in the flex), in the harness (FROZEN 2026-10-09)

**Status: FROZEN 2026-10-09 (07:18 CDT)** by the reviewer, after the outside reviewer's DRAFT. THE DESIGN (`159907fc`, 06:24) was
committed BEFORE study 84's READ, on 84's slates. Then the code shas, the smoke and the binding census (§6), all before any
scored bank.
- The text changed at the freeze in §6 only (the census).
- The module and the reader are the DRAFT's, unchanged. The laptop acks.
- **Banks 1719–1724, seed 20261130** (the reviewer's). The laptop scanned them, the derived bases 1769–1774 / 2419–2424 and the
  seed clean; the only hits were self-references.
- **Target:** after study 84's run.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request
- **The operator, 10-09, in the outside reviewer's session (before study 84's read; the laptop records it verbatim):** "As an
  experiment lets try an entire book like this: TE <= 5000 / D <= 3000 / 1 WR <= 4500 / WR or RB in Flex."
- **His two clarifications (asked the same minute):** "1 WR <= 4500" means **exactly one** WR priced ≤ $4,500 per lineup; the
  result is **information for his decision** ("Let me decide") — no automatic Week-5 rule.
- **What it extends:** study 81's NOTE5K_ALL (no TE ≥ $5,000 on any row; the side measurement +4.7, re-tested in study 84), the
  brainstorm's cheap-DST finding (10-07; the W5 settings already lean that way), study 75's WR flex (no TE in the flex here,
  RB allowed), and the cheap-player lean (study 53, the live cheap block). **The TE rule differs from study 81's by one price
  point:** a TE at exactly $5,000 is allowed here.
- **The prior, stated first:** NO DIFFERENCE. Each piece is a price restriction on a book already solved on projection; the
  pieces cost projection.

## 2. Arms (`experiments/s85_price_book.py`)
**The book:** study 48's harness through study 80's module (sha-asserted; study 73 underneath), the same as studies 81–84.
LIVE = 48d's 41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6
(`plan-week5-rev6-s24.json` `ac10ddf6…`).
- **THE RULES, on EVERY BOOK solve (j < 26; spares never), whatever the cell:**
  - **TE5000:** every pool TE priced > $5,000 banned;
  - **DST3000:** every pool DST priced > $3,000 banned;
  - **WR1CHEAP:** exactly one WR priced ≤ $4,500 (the lab optimizer's set_constraints [(those WRs, ">=", 1), (those WRs, "<=",
    1)]);
  - **FLEXNOTE:** at most one TE (set_constraints [(the TEs, "<=", 1)]), so the flex is a WR or an RB.
  - The rules that apply are ONE solve (the bans and the union of the constraints); an infeasible one is re-solved at the
    cell's own rules with no ban and no constraint and recorded once (studies 81 / 83 / 84's fallback). The cells, their
    quotas and stacking rules, the cheap +2 block, the caps and the dealing are his live book's.
- **THE ARMS:**
  - **LIVE_CB** — the reference;
  - **BOOK85 (his book)** — all four rules;
  - **EXPLORATORY, each rule alone:** TE5000, DST3000, WR1CHEAP, FLEXNOTE (which piece drives the result).

## 3. The read (the reader `scripts/s85_report.py`)
- **Study 63's frozen reader** for its statistics (load, mean_contests, boot, verdict, go / no-go, trial identical; a test
  asserts it), with study 83's `his_rule` printed beside each arm for his reference.
- **For every arm X ≠ LIVE_CB:** X − LIVE_CB on P(≥ 1 big seat) per slate on the calibrated field v2 — the 2023–24 read (36
  slates, two-sided 0.95, B 20,000) and the 2022 check; the guards; expected big seats; P(≥ 2); l02.
- **NO AUTOMATIC DECISION:** the read is information for his decision, as he asked. The lines he sees first: BOOK85 − LIVE_CB
  on 2023–24 and 2022, the expected big seats, and the projection cost.
- **WHAT IT CAN AND CANNOT SAY, PLAINLY:**
  - five comparisons on slates already read by studies 81–84 (the TE piece's +4.7 among them): any one leaning positive is
    weak evidence;
  - under no true effect an arm is "not negative" on both 2023–24 and 2022 about one time in four.

- **THE NOISE FINDING (study 84, disclosed as a fact; the rules here are unchanged):** the same rule read +0.047 on banks 1689–1694 and −0.012 on 1713–1718 (study 81's NOTE5K_ALL = study 84's TE_ONLY, call for call), and study 83's COMBO −0.019 vs +0.010 in 84. The intervals resample slates and do not include the bank-to-bank variation of the simulations and the field draws, so they understate the uncertainty; a lean of a few points is within that variation.

## 4. What the harness can and cannot say
- **The real-book check first** (the laptop's, outcome-blind, W4, OFF `a4ab2839`): how many of his rows break each rule today
  (TE > $5,000; DST > $3,000; not exactly one WR ≤ $4,500; a TE in the flex), and what the four rules together cost in FP
  points per row. The TE piece alone cost −0.76 per row there (study 84 §4).
- The harness's census reports the same counts for LIVE_CB (the vacuity of each rule) and the projection cost per arm.
- Path dependence: the rules re-draw most of the book. The base is our simulator's mean, not FP's. The lines are closing lines.

## 5. Production
- None unless he decides to use it. The pieces would map to: the TE price (`--mix-no-te-above`, at $5,001); new flags for the DST
  price, the one cheap WR and the TE count, each with parity against this study's frozen wrapper; his decision recorded first.

- **BEFORE HE ACTS ON ANY ARM (the reviewer's forward rule, 10-09):** it is first re-read on a second, disjoint bank set (the same code and reader, new banks and seed), and both reads and their difference are reported before any option is built.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s85-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `7485a26b…`):
  - every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every row in the pool;
  - **0 infeasible solves in every arm** (78 of 78 ruled each); the ruled rows read by big contests 0.846 (all 26 book rows);
  - the pool per slate-bank (mean / min): DSTs ≤ $3,000 12.0 / 10; TEs ≤ $5,000 45.7 / 45 (at exactly $5,000: 0.7); WRs ≤ $4,500
    69.3 / 57;
  - VACUITY over LIVE_CB's 26 rows (rows breaking each rule): a TE > $5,000 10.0; a DST > $3,000 8.0; cheap WRs ≠ 1 11.3; a TE in
    the flex 15.7 (his W4 FP book: 11 / 7 / 12 / 14; all four met by 5 of 26);
  - BOOK85 breaks no rule in any row; its flex WR / TE / RB 11.0 / 0 / 15.0 (LIVE_CB 4.3 / 15.7 / 6.0); QB + TE rows 10.0 (15.0);
  - **projection per row:** BOOK85 −0.94; TE5000 −0.57; DST3000 −0.14; WR1CHEAP +0.03; FLEXNOTE −0.67;
  - his real W4 book (the laptop, 10-09): the two bans alone change 24 of 26 rows at −0.73 FP per row (the WR and flex rules
    come on top).
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 108 lines and 8 sections; only those
  were read.
- **The binding (support) census** (the reviewer's; outcome-blind; bank 1406; all 53 slate-banks of 2022–24; code
  `658dd352` clean; 10 tests pass; lab `results/s85/CENSUS_s85_binding.txt` `227b4748…`, the raw mechanics rows
  `census_mechanics_bank1406.jsonl` `38580f81…` with no outcome field, committed at `4a2318ee`):
  - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
  - pool per slate-bank (mean / min): DSTs ≤ $3,000 12.6 / 8; TEs ≤ $5,000 50.9 / 36, of which at exactly $5,000 0.4 / 0
    (allowed by his wording; studies 81 / 84 banned them); WRs ≤ $4,500 70.8 / 40;
  - 0 infeasible ruled solves in every arm (0 of 1,378 each);
  - vacuity over LIVE_CB's 26 rows (rows breaking each rule): TE > $5k 7.5, DST > $3k 10.1, cheap WRs ≠ 1 12.3, a TE flex
    15.2. His W4 FP book breaks them in 11 / 7 / 12 / 14 rows; all four are met by 5 of 26;
  - BOOK85 meets all four on every row (flex WR 14.8 / TE 0 / RB 11.2); QB + TE rows 12.2 → 8.6; projection −0.80 per row
    (his real book: the two bans alone −0.73); rows shared with LIVE_CB 0.7; dealt identical 0.000;
  - each rule alone, projection: TE5000 −0.30, DST3000 −0.23, WR1CHEAP −0.22, FLEXNOTE −0.32.
- **Code:** nfl2 `production/s85-price-book-20261009` @ `658dd352` (branched from study 84's `37365127`):
  - `experiments/s85_price_book.py` `4f752f8e…`;
  - `scripts/s85_drive.py` `f19857c8…`;
  - `scripts/s85_census.py` `f8090037…`;
  - **`scripts/s85_report.py` (the reader) `865c4f1e…`** (seed 20261130);
  - `tests/test_s85_price_book.py` `31a52814…` (10 tests);
  - unchanged and sha-asserted: `s84_combo81.py` `40201328…` (its `s81_note5k.py` `b37dbbc9…`, `s83_combo.py` `19d9a77c…` and
    their pins), `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`; the plan `ac10ddf6…`.
