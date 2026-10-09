# Preregistration: study 84, the no-expensive-TE rule (study 81's every-row version) with study 83's rules, with each of them, and alone, in the harness, with his "not negative" rule (DRAFT 2026-10-09)

**Status: DRAFT 2026-10-09 (05:39 CDT)** by the outside reviewer — **THE DESIGN IS COMMITTED BEFORE STUDY 83'S READ** (study
83's run is on the same slates; the reviewer holds 83's reader until this draft is on origin). The code shas follow in the
next commit; the reviewer reviews, runs the binding census and FREEZES; the laptop acks.
- **Banks 1713–1718, seed 20261129** (the reviewer's; the laptop's scanned-clean block).
- **Target:** this morning, after study 83's run.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his instructions, in order
- **Decision 1** (HANDOFF `7473786e`): "Let's do a test now of all 3 and if it isn't negative use it in week 5." → study 83.
- **Decision 2** (HANDOFF `b6df3671`, 05:36 CDT): "It also appears that 81 was positive. So following the current test, we need
  to try a version including 81." Told first: study 81's decision arm was flat; its +4.7 was the side measurement NOTE5K_ALL
  (one of about 35); on his real W4 book NOTE5K_ALL changes 24 of 26 rows at −0.76 FP per row. Asked the dose, he chose "No $5k+
  TE in any lineup", with the same rule.
- **Decision 3** (in the outside reviewer's session, after decision 2, before 83's read; the laptop records it verbatim):
  "If 83 comes back negative, but 84 beats 83, then let's try versions where the 5000+ TE rule is active along with each portion
  of what we tried in 83 separately."
- **Decision 4** (same session, right after): "And the final test of the week after that is just the 5000+ TE rule with the
  current book."
- All four are tested in ONE run, designed here before study 83 is read (our rule since studies 50 / 51).

## 2. Arms (`experiments/s84_combo81.py`)
**The book:** study 48's harness through study 80's module; studies 81 (`s81_note5k.py` `b37dbbc9…`) and 83 (`s83_combo.py`
`19d9a77c…`, and through it 75 / 77 / 79) sha-asserted. LIVE = 48d's 41 rows with the cheap +2 block through study 53's
`block_term` / `term_book`, on Rev6 (`plan-week5-rev6-s24.json` `ac10ddf6…`).
- **THE RULES** (on BOOK solves only, j < 26, in build order; spares never):
  - **C0 (77):** the first 3 cell-C solves at C's rules with qb_stack 0..0;
  - **ONEPC (79):** every B / C solve holds at most one WR / TE of every team;
  - **FLEX (75):** the first 3 solves hold exactly 4 WRs;
  - **TE5K (81, NOTE5K_ALL):** every solve bans every pool TE priced ≥ $5,000.
  - The rules that apply to a solve are ONE solve (the C0 stack, the union of the constraints, the bans); an infeasible one is
    re-solved at the cell's own rules with no constraint and no ban and recorded once (study 81's and 83's own fallback).
- **ONE WRAPPER (`combo81`):** study 83's `combo` with study 81's ban set added. The frozen wrappers cannot be stacked (both keep
  their records on `type(self)`, the same class in a stacked builder). With no ban set `combo81` IS study 83's `combo`, and with
  no combo rule it IS study 81's `banned_rows` over every book solve, call for call (tests).
- **THE ARMS:**
  - **LIVE_CB** — the reference (his live book with the cheap +2 block);
  - **COMBO81 (decision 2)** — C0 + ONEPC + FLEX + TE5K;
  - **COMBO** — C0 + ONEPC + FLEX (study 83's arm, rebuilt on these banks: COMBO81 − COMBO isolates the ban);
  - **TE_C0, TE_ONEPC, TE_FLEX (decision 3)** — TE5K with each of 83's rules alone;
  - **TE_ONLY (decision 4)** — TE5K alone on his current book (study 81's NOTE5K_ALL on these banks).

## 3. The reads and HIS RULE (the reader `scripts/s84_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`) for its statistics (load, mean_contests, boot, verdict, go / no-go,
  trial identical; a test asserts it), with study 83's `his_rule`.
- **For every arm X ≠ LIVE_CB:** X − LIVE_CB on P(≥ 1 big seat) per slate on the calibrated field v2 — the 2023–24 read (36
  slates, two-sided 0.95, B 20,000) and the 2022 check — and **HIS RULE: NOT NEGATIVE iff the 2023–24 point ≥ 0 AND the 2022
  point ≥ 0 AND the expected-big-seats ratio ≥ 0.80.** Also printed: **COMBO81 − COMBO** (the 2023–24 point and interval,
  "84 beats 83" = that point > 0).
- **WHAT HE ENTERS IN WEEK 5 — our reading of his four decisions** (the laptop confirms it with him before any merge):
  1. If study 83's COMBO is NOT NEGATIVE (83's READ): **COMBO81** if NOT NEGATIVE here, else **COMBO**.
  2. If 83's COMBO is negative AND COMBO81 − COMBO > 0 here ("84 beats 83"): the NOT-NEGATIVE arm among **TE_C0 / TE_ONEPC /
     TE_FLEX** with the highest 2023–24 point; if none, step 3.
  3. Otherwise: **TE_ONLY** if NOT NEGATIVE; else **nothing new** (the live book stands).
- **WHAT THE RULE CAN AND CANNOT SAY, PLAINLY:**
  - Under no true effect an arm passes about **one time in four** (two independent point estimates ≥ 0). The rule screens out a
    version that looks harmful; it does **not** show a gain.
  - **The TE5K part is re-tested on the SAME 53 slates and the SAME real outcomes on which study 81's NOTE5K_ALL read +4.7**
    (new banks change only the field draws and the simulated means). So the TE arms are LIKELY to pass, and a pass is **not
    new evidence** that the ban helps: it says only that adding the ban to these rules does not look harmful on slates already
    seen.
  - Choosing the best of three arms in step 2 favours a lucky arm; the size of its lead is not a measured gain.

## 4. What the harness can and cannot say — the transfer caveat, first
- **On his real W4 book the TE5K piece is far bigger than in the harness:** it changes 24 of 26 rows at **−0.76 FP per row**
  (the harness −0.33); flex 1 / 14 / 11 → 4 / 7 / 15; QB + TE stacks 12 → 10 (the laptop's W4 check, `reports/2026-10-09-
  option-w4-checks/`, Addendum 179). **The harness may flatter it.** The laptop's W4 check of the four rules together follows
  after 83's run.
- Every piece binds on his real book (83's §4: C0 3 / 7 / 13; one catcher pairs 7 → 1; flex 1 / 14 / 11 → 4 / 11 / 11).
- Path dependence: the rules re-draw most of the book. The base is our simulator's mean, not FP's. The lines are closing lines.

## 5. Production
- If an arm with TE5K is entered: a fourth piece in the combined production option (review/combo-flag-20261009): every pool TE
  priced ≥ $5,000 banned on every book solve, in the same ONE combined solve, with the same fallback; parity against this
  study's frozen `combo81`; its new argument classified in the reviewer's s38 6l before any merge; the laptop's wiring and
  FRIDAY_HEAD as for 83. If COMBO or nothing is entered, no new production piece.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s84-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `66c27164…`):
  - every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every row in the pool;
  - **0 infeasible combined solves in every arm**; $5k+ TE rows in every TE arm's book **0** (LIVE_CB 10.0);
  - VACUITY at the ruled positions: TE5K 0.385 of LIVE_CB's rows there hold a $5k+ TE; C0 1.000; ONEPC 0.310; FLEX 1.000;
  - per book (QB-alone / non-QB-pair / $5k+ TE / QB + TE rows; flex WR / TE / RB; projection per row, cost):
    - LIVE_CB 0 / 6.3 / 10.0 / 15.0; 4.3 / 15.7 / 6.0; 127.86;
    - COMBO81 3 / 2.7 / 0 / 11.3; 7.0 / 11.0 / 8.0; −0.52;
    - COMBO 3 / 1.7 / 10.3 / 12.3; 5.3 / 14.0 / 6.7; −0.12;
    - TE_C0 3 / 6.3 / 0 / 10.3; 5.0 / 13.3 / 7.7; −0.44;
    - TE_ONEPC 0 / 2.3 / 0 / 11.7; 6.0 / 11.7 / 8.3; −0.60;
    - TE_FLEX 0 / 5.3 / 0 / 11.3; 7.7 / 11.3 / 7.0; −0.65;
    - TE_ONLY 0 / 5.3 / 0 / 12.7; 6.3 / 12.7 / 7.0; −0.57 (dealt identical to LIVE_CB 0.333: one slate-bank's book held no
      $5k+ TE).
  - On his real W4 book (the laptop's check, 10-09, OFF `a4ab2839`): COMBO81 bans 11 → 0 $5k+ TE rows, pairs 7 → 1, flex
    1 / 14 / 11 → 6 / 5 / 15, QB + own-TE 12 → 9, **FP −0.53 per row**; the TE ban alone −0.76 per row (§4).
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 128 lines and 10 sections; only
  those were read.
- **The binding (support) census:** the reviewer's, on all 53 slate-banks of bank 1406, before the freeze.
- **Code:** nfl2 `production/s84-combo81-20261009` @ `37365127` (the outside reviewer's draft; branched from study 83's
  `45cd1a76`):
  - `experiments/s84_combo81.py` `40201328…` (the wrapper `combo81`, text `c38f27a7…`);
  - `scripts/s84_drive.py` `52c7bc0a…`;
  - `scripts/s84_census.py` `a053d015…`;
  - **`scripts/s84_report.py` (the reader) `293d263a…`** (seed 20261129);
  - `tests/test_s84_combo81.py` `72512271…` (16 tests);
  - unchanged and sha-asserted: `s81_note5k.py` `b37dbbc9…`, `s83_combo.py` `19d9a77c…` (its `s75` `e9948fd9…`, `s77`
    `d455f3dd…`, `s79` `d48790cf…`, `s80` `9a46c284…`, `s73_topg_qb1.py` `3f76c629…`), `term_book.py` `62c2306e…`,
    production's `enter_layout.py` `3cb051ac…`; the plan `ac10ddf6…`.
- **Study 83's READ (after this design was on origin):** COMBO −0.01893 (2024 −0.040), 2022 +0.01832, HIS RULE DO NOT USE.
  So step 1 of §3's entry order does not apply; steps 2–3 decide.
