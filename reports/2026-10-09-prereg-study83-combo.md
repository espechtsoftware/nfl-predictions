# Preregistration: study 83, the three leans together (77's QB alone + 79's one catcher per team + 75's WR flex), in the harness, with his "not negative" rule (FROZEN 2026-10-09)

**Status: FROZEN 2026-10-09 (05:28 CDT)** by the reviewer, after the outside reviewer's DRAFT (05:23 CDT), the smoke and the
binding census (§6), before any scored bank.
- The text changed at the freeze in §4 (the census's figures beside the smoke's) and in §6 (the census and one disclosure).
- The module and the reader are the DRAFT's, unchanged. The laptop acks (shas, tests, the census re-run; the banks and the
  seed were scanned clean overnight).
- **Banks 1707–1712, seed 20261128** (the reviewer's; the laptop scanned 1707–1718 and their derived bases clean and unused
  overnight).
- **Target:** this morning. If his rule says USE, a combined production option for Week 5, merged before FRIDAY_HEAD.

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why — his decision
- **The operator, 10-09, in the outside reviewer's session** (recorded verbatim, HANDOFF `7473786e`, its time line
  `ee3ddd9f`): "Let's do a test now of all 3 and if it isn't negative use it in week 5."
- **What he was told first** (the plain reading): all three leaned positive on 2023–24 (75 +2.3, 77 +1.8, 79 +2.0); none is
  proven (every interval includes zero; about 35 measurements overnight); 75 was contradicted on 2022 (−1.1); 79's 8-row
  version changed nothing on his real W4 book, and the version that does is the every-B/C-row one (exploratory +2.1, 2022
  +0.8); the three were never tested together.
- **The prior, stated first:** NO DIFFERENCE. The three rules touch different parts of the book (the QB's stack, the pairs away
  from the QB, the flex) and each leaned positive alone; a combination can still interact (one solve may carry all three).

## 2. Arms (`experiments/s83_combo.py`)
**The book:** study 48's harness through study 80's module (`s80_dogqb.py` `9a46c284…`); studies 75 / 77 / 79's frozen modules
sha-asserted (`s75_flex_mix.py` `e9948fd9…`, `s77_naked.py` `d455f3dd…`, `s79_nopairs.py` `d48790cf…`; study 73 `3f76c629…`
underneath). LIVE = 48d's 41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6
(`plan-week5-rev6-s24.json` `ac10ddf6…`).
- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **COMBO (THE DECISION):** on the BOOK solves (j = len(prev) < 26; spares never), in BUILD ORDER:
  - **C0 (77):** the first 3 cell-C solves at C's rules with `qb_stack_min` / `qb_stack_max` 0 (the QB alone, no bring-back);
    the slot is used either way (study 77's count);
  - **ONEPC (79):** EVERY B / C solve holds at most one WR / TE of every team (study 79's `set_constraints`
    [(team T's WR / TE, "<=", 1)] for every team T; its ONEPC_ALL — the version that binds on his real book);
  - **FLEX (75):** the first 3 solves, any cell, hold ≥ 4 WRs, i.e. exactly 4 (study 75's `set_constraints` [(WRs, ">=", 4)];
    **3 rows, his "small amount", not the tested 8**).
  - **ONE solve:** the rules that apply to a solve are applied together — the C0 stack and the union of the constraints —
    in one optimizer call. An infeasible combined solve is re-solved at the cell's own rules with no extra constraint and
    recorded once (not retried).
  - **Why one wrapper:** the frozen wrappers cannot be nested (each sets `S24.optimize = partial(orig, set_constraints=…)`
    inside its own solve, so an inner patch replaces the outer one). The combined wrapper's parts ALONE reproduce studies
    75 / 77 / 79's frozen wrappers call for call, with and without infeasible solves (tests).
- **EXPLORATORY C0_ONEPC:** C0 and ONEPC, no FLEX.
- **PRODUCTION'S EQUIVALENT (for §5):** one combined peek in `mix_rows` — the C0 StackRules + member_bounds (team T's WR / TE,
  0, 1) for every team + member_bounds (WRs, 4, 4) in one optimize call — the three existing flags allowed together only at
  exactly this combination; parity against this study's frozen combined wrapper.
- **DEALING (the smoke):** position 0 FLEX; 2 ONEPC + FLEX; **3 C0 + ONEPC + FLEX (all three)**; 7 and 13 C0 + ONEPC; 4, 6,
  8, 12, 14, 16, 17, 18, 22, 23 ONEPC. Positions 22 / 23 are non-big (ONEPC on every B / C row).

## 3. Endpoint and rules (the reader `scripts/s83_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`): load, mean_contests, boot, verdict, go / no-go and trial
  identical (a test asserts it); the names, the seed, the docstring, the secondaries (QB-alone / non-QB-pair / WR-flex rows)
  and HIS RULE's line differ.
- **THE READ: 2023–24** (36 slates). COMBO − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2; two-sided
  0.95, B 20,000. **THE 2022 CHECK** as before.
- **HIS RULE — THE DECISION FOR WEEK 5** (printed as its own line): **USE IN W5 iff the 2023–24 point estimate ≥ 0 AND the
  2022 point estimate ≥ 0 AND the expected-big-seats ratio ≥ 0.80** (his tolerance). The guards and study 63's verdict /
  trial lines are printed as usual and do not gate his rule.
- **WHAT THE RULE CAN AND CANNOT SAY (the reviewer's condition, plainly):** the read and the 2022 check use different slates,
  so under no true effect "both point estimates ≥ 0" happens **about one time in four**. The rule screens out a combination
  that looks harmful; it does **not** show a gain.
- **EXPLORATORY:** C0_ONEPC − LIVE_CB; each arm on l02; P(≥ 2); the rows by shape; the ruled solves built plain.

## 4. Binding, on his real book and in the harness
- **His real book — the laptop's W4 rate checks, 10-09** (read-only on the OFF book `a4ab2839`): every piece binds.
  - C0-3: 3 QB-alone rows at positions 3 / 7 / 13 (each in big contests), FP +0.11 per row.
  - One catcher, every B / C row (14 at K 26): non-QB-pair rows 7 → 1, 8 rows changed, FP +0.03 per row.
  - WR flex on 3 rows: flex 1 / 14 / 11 → 4 / 11 / 11 (WR / TE / RB), FP −0.31 per row; every row changes through path
    dependence.
  - The three together on his real book: the laptop's check after the read, if his rule says USE.
- **The harness (the smoke, 3 slate-banks; the binding census on 53 is the reviewer's):**
  - combined solves per slate-bank: C0+ONEPC 2, C0+ONEPC+FLEX 1, FLEX 1, ONEPC 10, ONEPC+FLEX 1; **0 of 45 infeasible**;
  - VACUITY at the ruled positions (LIVE_CB's rows there that the rule changes): C0 1.000 (all had a QB-team catcher),
    ONEPC 0.310 (had a non-QB pair), FLEX 1.000 (had a non-WR flex);
  - per book (LIVE_CB / COMBO / C0_ONEPC): QB-alone rows 0 / 3 / 3; non-QB-pair rows 6.3 / 1.7 / 2.0; flex WR 4.3 / 5.3 / 3.3,
    TE 15.7 / 14.0 / 16.0, RB 6.0 / 6.7 / 6.7; QB + 2 rows 12 in every arm;
  - projection per row −0.12 (COMBO) / −0.01 (C0_ONEPC); rows shared with LIVE_CB 1.3 / 3.0; dealt identical 0.000 / 0.000.
- **The binding census (53 slate-banks, §6):**
  - The combined solves per slate-bank are as the smoke: c0+onepc 2, all three 1, flex 1, onepc 10, onepc+flex 1.
  - **0 of 795 ruled solves infeasible**, including position 3's QB-alone row with four WRs, each from a different team.
  - VACUITY at the ruled positions: c0 1.000, onepc 0.245, flex 0.792.
  - Non-QB-pair rows 5.02 → 1.74 (C0_ONEPC 1.94); flex WR 6.2 → 7.4; QB-alone rows 0 → 3.
  - Projection −0.01 per row (C0_ONEPC +0.02); rows shared with LIVE_CB 2.3 / 4.6; dealt identical 0.000 / 0.000.
  - Ruled rows read by a big contest 0.867: the one-catcher rows at positions 22 / 23 are non-big, by design.
- **Path dependence:** the rules re-draw most of the book. **The base is our simulator's mean, not FP's. The lines are closing
  lines.**

## 5. What the read does
- **USE IN W5:** the combined production option (the outside reviewer's; format agreed with the laptop: the three flags at
  3 / 14 / 3 together, one combined peek), parity-tested against this study's frozen combined wrapper, the laptop's review
  and wiring (SECOND_CHANGE_DECISION = his recorded decision), the laptop's W4 real-book check of the combination, merged
  before FRIDAY_HEAD; Friday's A3 ON run and its check; the reviewer's s38 6m (MIXT_QA0 follows the combination); the
  laptop confirms with him before the money-path merge (HANDOFF `7473786e`).
- **DO NOT USE IN W5:** nothing changes this week; the exploratory lines go to his sheet.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406; Rev6; `~/s83-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10; `results_bank1406.jsonl`
  `b2732b46…`): every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every
  row in the pool; the rest as §2 / §4.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406): the reader exited 0 with 43 lines and 4 sections (his
  rule's line added); only those were read.
- **The binding (support) census** (the reviewer's; outcome-blind; bank 1406; all 53 slate-banks of 2022–24; code
  `a7a1f60c` clean; 13 tests pass; lab `results/s83/CENSUS_s83_binding.txt` `971d33c0…`, the raw mechanics rows
  `census_mechanics_bank1406.jsonl` `cbaba5d6…` with no outcome field, committed at `45cd1a76`):
  - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
  - COMBO: 0 of 795 ruled solves infeasible (the 5% condition is not reached); the ruled positions by rule: 0 flex,
    2 onepc+flex, 3 c0+onepc+flex, 7 and 13 c0+onepc, the rest onepc (4, 6, 8, 12, 14, 16, 17, 18, 22, 23);
  - C0_ONEPC: 0 of 742 infeasible;
  - the rest as §4.
- **Disclosed:** the module's docstring dates his decision "10-09 05:20 CDT", the relay's estimate. The record is HANDOFF
  `7473786e` (its time line `ee3ddd9f`, 05:16). The docstring was left unchanged so the census ran on the frozen code.
- **Code:** nfl2 `production/s83-combo-20261009` @ `a7a1f60c` (the outside reviewer's draft; branched from study 82's
  `bba5687d`):
  - `experiments/s83_combo.py` `19d9a77c…`;
  - `scripts/s83_drive.py` `a2644acb…`;
  - `scripts/s83_census.py` `867ba356…`;
  - **`scripts/s83_report.py` (the reader) `465c9910…`** (seed 20261128);
  - `tests/test_s83_combo.py` `af5f3476…` (13 tests);
  - unchanged and sha-asserted: `s75_flex_mix.py` `e9948fd9…`, `s77_naked.py` `d455f3dd…`, `s79_nopairs.py` `d48790cf…`,
    `s80_dogqb.py` `9a46c284…` (its `s73_topg_qb1.py` `3f76c629…`, and through it `s48_winner_like.py` `c22d2811…`,
    `s53_cheap_pref.py` `f3f9d735…`), `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`; the plan
    `ac10ddf6…`.
