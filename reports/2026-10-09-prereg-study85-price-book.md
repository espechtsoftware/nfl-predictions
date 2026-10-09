# Preregistration: study 85, his whole-book price rules (TE ≤ $5,000, DST ≤ $3,000, exactly one WR ≤ $4,500, no TE in the flex), in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (06:24 CDT)** by the outside reviewer — **THE DESIGN IS COMMITTED BEFORE STUDY 84'S READ** (study 84
is running on the same slates). The code and its shas follow; the reviewer reviews, runs the binding census and FREEZES; the
laptop acks.
- **Banks and seed:** the reviewer assigns them (proposed 1719–1724, seed 20261130; the laptop scans them and the derived bases
  1769–1774 / 2419–2424 first).
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
- Bank 1406 only, after study 84's run frees the machine: the mechanics smoke (2022 W9, 2023 W3, 2024 W10), the binding
  census, the full-path smoke (reader exit and line count only). Shas in the next commit.
- **Code:** nfl2 `production/s85-price-book-20261009` (to branch from study 84's `37365127`).
