# Preregistration: study 86, no player priced over $7,900 anywhere in the book, in the harness (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (06:49 CDT)** by the outside reviewer — **THE DESIGN IS COMMITTED BEFORE STUDY 84'S AND STUDY 85'S
READS** (both on the same slates). The code and its shas follow; the reviewer reviews, runs the binding census and FREEZES;
the laptop acks.
- **Banks and seed:** the reviewer assigns them (proposed 1725–1730, seed 20261131; the laptop scans them and the derived bases
  1775–1780 / 2425–2430 first).
- **Target:** after study 85's run.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his request
- **The operator, 10-09, in the outside reviewer's session (before study 84's read; the laptop records it verbatim):** "After
  that, let's do one additional study where the only rule is no player over $8100 for the entire book."
- **AMENDED by the operator before any code, smoke or read (same session, minutes later):** "Let's change that to no player
  over 7,900." **The cap is $7,900** (a player at exactly $7,900 is allowed); every "$8,100" below now reads "$7,900", and the
  arm is CAP7900.
- **Use:** like study 85, the result is **information for his decision** (the outside reviewer's reading of "an additional
  study"; he can change it before the read). No automatic Week-5 rule.
- **What it relates to:** study 78 forced the OPPOSITE — two players priced $8,000 or more on the first 8 rows (STUDS2_8, mixed:
  2023 −0.8, 2024 +4.5, 2022 +2.2, a guard failed; Addendum 176). The top 1% of the 2026 W1–4 Millionaires hold 0.88 players
  priced ≥ $8,000 per lineup, the field 0.66, his W5-style book 0.54 (the reviewer's scan2). This study removes them.
- **The prior, stated first:** NO DIFFERENCE or negative (the top 1% hold MORE stars than the field).

## 2. Arms (`experiments/s86_price_cap.py`)
**The book:** study 48's harness through study 81's module (`s81_note5k.py` `b37dbbc9…`, sha-asserted; study 80 / 73
underneath), the same as studies 81–85. LIVE = 48d's 41 rows with the cheap +2 block through study 53's `block_term` /
`term_book`, on Rev6 (`plan-week5-rev6-s24.json` `ac10ddf6…`).
- **THE RULE, on EVERY BOOK solve (j < 26; spares never), whatever the cell:** every pool player of ANY position priced
  **> $7,900** is banned (a player at exactly $7,900 is allowed, his wording). Through study 81's frozen `banned_rows` (the ban
  set, every book solve), imported, never copied; an infeasible solve is re-solved at the cell's own rules with no ban and
  recorded.
- **THE ARMS:** **LIVE_CB** (the reference) and **CAP7900** (the rule).

## 3. The read (the reader `scripts/s86_report.py`)
- **Study 63's frozen reader** for its statistics (identical functions; a test asserts it), with study 83's `his_rule` printed
  for reference only.
- **CAP7900 − LIVE_CB** on P(≥ 1 big seat) per slate on the calibrated field v2 — the 2023–24 read (36 slates, two-sided 0.95,
  B 20,000) and the 2022 check; the guards; expected big seats; P(≥ 2); l02; the projection cost; the players priced > $7,900
  per row in LIVE_CB.
- **NO AUTOMATIC DECISION:** information for his decision.
- **Plainly:** the slates are the ones studies 78–85 read; under no true effect a version is "not negative" on both 2023–24 and
  2022 about one time in four.

- **THE NOISE FINDING (study 84, disclosed as a fact; the rules here are unchanged):** the same rule read +0.047 on banks 1689–1694 and −0.012 on 1713–1718 (study 81's NOTE5K_ALL = study 84's TE_ONLY, call for call), and study 83's COMBO −0.019 vs +0.010 in 84. The intervals resample slates and do not include the bank-to-bank variation of the simulations and the field draws, so they understate the uncertainty; a lean of a few points is within that variation.

## 4. What the harness can and cannot say
- **The real-book check first** (the laptop's, outcome-blind, W4, OFF `a4ab2839`): how many of his rows hold a player priced
  > $7,900, and the rule's FP cost per row (the dk-status route marks those players OUT: it emulates this rule exactly, up to the
  spares and the T-70 pool).
- **The transfer caveat (study 78's):** the harness's LIVE_CB plays about 0.92 players priced ≥ $8,000 per row against his FP
  book's 0.54, so the rule removes more in the harness than in his book.
- Path dependence; the simulator's mean; closing lines.

## 5. Production
- None unless he decides to use it. The rule maps to the dk-status route's bans for the book only; a production flag (every
  pool player priced > SALARY banned on every book solve) would be a fresh build with parity against this study's frozen
  wrapper, its format agreed with the laptop first, his decision recorded first.

- **BEFORE HE ACTS ON ANY ARM (the reviewer's forward rule, 10-09):** it is first re-read on a second, disjoint bank set (the same code and reader, new banks and seed), and both reads and their difference are reported before any option is built.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s86-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `7d5fba40…`):
  - both arms are 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every row in the pool;
  - **0 infeasible solves** (78 of 78 ruled); the ruled rows read by big contests 0.846 (all 26 book rows);
  - the pool per slate-bank: 6.33 players priced > $7,900 (min 6; over the three: QB 3, RB 5, WR 11); 1.0 at exactly $7,900
    (allowed);
  - VACUITY: LIVE_CB holds a player > $7,900 in 17.3 of 26 rows; CAP7900 in 0;
  - $7k+ per row 2.31 → 1.95; $8k+ per row 0.92 → 0; flex WR / TE / RB 4.3 / 15.7 / 6.0 → 3.3 / 12.7 / 10.0; QB + TE rows 15.0 →
    12.3; **projection per row −0.90**; rows shared with LIVE_CB 0.7.
  - **His real W4 book** (the laptop, 10-09, the dk-status route, exact up to the spares): 4 slate players above $7,900 (WR
    $9,100, RB $8,400, RB $8,200, WR $8,100), in 11 of his 26 rows; 17 of 26 rows change; **FP −0.18 per row**; flex 1 / 14 / 11
    → 1 / 13 / 12; pairs 7 → 4. The harness's base plays far more $8k+ players (0.92 per row vs his 0.54), so the harness cost
    (−0.90) overstates his (−0.18): the transfer caveat in §4.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 36 lines and 4 sections; only those
  were read.
- **The binding (support) census:** the reviewer's, on all 53 slate-banks of bank 1406, before the freeze.
- **Code:** nfl2 `production/s86-price-cap-20261009` @ `4fdad305` (committed 07:26:04, before study 85's READ; unchanged by the
  smoke; branched from study 85's `658dd352`):
  - `experiments/s86_price_cap.py` `b7d741c9…`; `scripts/s86_drive.py` `9d184971…`; `scripts/s86_census.py` `b13d809d…`;
  - **`scripts/s86_report.py` (the reader) `76df628d…`** (seed 20261131); `tests/test_s86_price_cap.py` `d7608e3a…` (6 tests);
  - unchanged and sha-asserted: `s81_note5k.py` `b37dbbc9…` (its `s80` / `s73` and their pins), `term_book.py` `62c2306e…`,
    production's `enter_layout.py` `3cb051ac…`; the plan `ac10ddf6…`.
