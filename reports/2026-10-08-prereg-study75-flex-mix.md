# Preregistration: study 75, a WR in the flex on the first 8 book rows (the winners' flex mix), in the harness (FROZEN 2026-10-08)

**Status: FROZEN 2026-10-08 (21:19 CDT)** by the reviewer, after the outside reviewer's DRAFT (`9e84c7f5`), the smoke and the binding
census (§6), before any scored bank. The laptop acks (shas, tests, census re-run, banks and seed scanned).
- **Changed at the freeze (text only):** §2 states the rule as a feasible-set rule; §4 carries the census's base flex
  mix; §5 makes production parity a condition of live use; §6 records the census. The module and the reader are the
  DRAFT's, unchanged.
- **Banks 1647–1652, seed 20261120** (assigned by the reviewer; pre-scanned clean by the laptop).
- **Target:** read tonight, after study 74. A production option only if WR_FLEX8 is ENTERABLE and the operator chooses it
  in the morning (code can be ready, not merged).

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 night:** "please look at the patterns of the winners over the past few weeks and consider a
  variety of different tests we can do throughout the night."
- **What the outside reviewer measured** (the 2026 W1–4 Millionaires, the money gate's real fields; aggregates only;
  `~/private/winner-shapes-2026/shapes.py`). The FLEX position (WR = 4 WRs, TE = 2 TEs, RB = 3 RBs):

| Flex | Top 0.1% | Top 1% | Field | His W5-style book (W4 inputs, FP) |
|---|---|---|---|---|
| WR | 27% | 30% | 33% | about 4% |
| TE | 44% | 37% | 28% | 54% |
| RB | 29% | 33% | 39% | 42% |

  - The four winners: TE flex in 3, RB in 1, WR in none.
  - The shape mix otherwise already matches the top 1% (QB+1 54% vs 48%, QB+2 46% vs 44%, a QB from a top-4 game 65% vs
    64%, a bring-back 58% vs 59%). The flex is the largest structural gap left: his book almost never plays a WR there.
- **What was tested before:** study 39 (Addendum 143) forced an RB INTO the flex of every row: −0.014 [−0.065, +0.039],
  NO DIFFERENCE; on 2 rows of 5, +0.007. This study goes the other way (a WR in the flex), on 8 rows.
- **The prior, stated first:** NO DIFFERENCE. The WR flex rate is about the same at the top as in the field (30% vs 33%);
  this tests whether his near-zero WR flex costs him anything.

## 2. Arms (`experiments/s75_flex_mix.py`)
**The book:** study 48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted through study 73 `3f76c629…`). LIVE = 48d's
41 rows with the cheap +2 block through study 53's `block_term` / `term_book`, on Rev6 (`plan-week5-rev6-s24.json`
`ac10ddf6…`).
- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE ROWS:** the first 8 BOOK solves in BUILD ORDER, any cell (studies 73 / 74's choice: the first-built rows take each
  cell's earliest dealt positions; the term block's rows are avoided, so the change is not confounded with the cheap
  term). A solve carries the rule while j (the rows committed before it) < 8. An infeasible ruled solve is re-solved
  plain and recorded (not retried). Spares never.
- **WR_FLEX8 (THE DECISION):** those 8 solves hold 4 WRs, i.e. a WR in the flex: the lab optimizer's `set_constraints`
  [(pool WRs, ">=", 4)] (its own WR ≤ 4 makes it exactly 4).
- **EXPLORATORY NORB_FLEX8:** those 8 solves hold exactly 2 RBs (no RB in the flex; the WR or TE the objective prefers):
  `set_constraints` [(pool RBs, "<=", 2)] with the optimizer's own RB ≥ 2.
  - **Why it is not the decision (outcome-blind, before any scored bank):** the mechanics smoke dealt it identically to
    LIVE_CB on 2 of 3 slate-banks. The harness's first 8 rows rarely flex an RB (§4), so it is close to a dead lever.
- **THE RULE, as a feasible-set rule (either mechanism implements it):** on the ruled solves, a lineup holds EXACTLY 4
  WRs (WR_FLEX8: the flex is a WR) or EXACTLY 2 RBs (NORB_FLEX8: the flex is a WR or a TE).
  - The harness implements it with the lab optimizer's `set_constraints` (the research optimize has no `member_bounds`).
  - Production's pinned optimize (nfl2 `f69598b`) would use `member_bounds` (WRs, 4, 4) / (RBs, 2, 2).
  - Under the DK slot counts (RB 2–3, WR 3–4) the two give the same feasible set.
- **Disclosed:** the module's docstring cites study 39 as "Addendum 141"; the correct citation is Addendum 143, as §1
  says. The docstring was left unchanged so the census ran on the frozen code.
- **DEALING:** the mechanics smoke put the 8 ruled rows at book positions 0, 2, 3, 5, 6, 7, 9, 10, all read by big
  contests (Rev6: 0–21). The census reports them on every slate-bank; the reviewer stops the freeze if any lands outside
  0–21.

## 3. Endpoint and rule (the reader `scripts/s75_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`). Its load, mean_contests, boot, verdict, go / no-go and trial
  functions are identical, which a test asserts. The names, the seed, the docstring, the secondaries (the book's flex
  WR / TE / RB) and the ruled-solve lines differ.
- **THE READ: 2023–24** (36 slates). WR_FLEX8 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2.
  The interval is two-sided 0.95, with B 20,000. **Banks 1647–1652, seed 20261120.**
- **THE GO / NO-GO: 2022** (study 51's frozen rule). Guards as before; they gate a PASS only.
- **THE TRIAL RULE** (study 51's). One decision arm, so no multiplicity.
- **One construction change a week:** if ENTERABLE alongside another lever, he picks one.
- **EXPLORATORY:** NORB_FLEX8 − LIVE_CB; each arm on l02; P(≥ 2); the book's flex mix; the QB + 2 rows; the ruled solves
  built plain.

## 4. What the harness can and cannot say
- **The base is our simulator's mean, not FP's, and the flex differs with it.** The harness's LIVE_CB flexes WR 6.2 / TE
  15.2 / RB 4.6 of 26 (the binding census; the smoke said 4.3 / 15.7 / 6.0; study 39's QA0 had an RB flex in 23% of
  rows). His real W5-style book on FP flexes
  about WR 1 / TE 14 / RB 11. So the harness tests "a WR flex on 8 rows" from a TE-heavy base; production's base is
  RB-heavier. WR_FLEX8 replaces mostly TE flexes in the harness (the census: TE 15.2 → 11.6, RB 4.6 → 3.4, WR 6.2 → 11.0). Live, it
  would mostly replace RB flexes, so the harness answers "a WR flex instead of a TE flex" more than "instead of an RB
  flex" (the laptop's point).
- **Path dependence:** the ruled rows are built first, so the rest of the book re-draws (the smoke shared 1.3 of 26 rows
  with LIVE_CB). The effect is measured on the whole book.
- **The lines are closing lines.**

## 5. What a verdict can do
- **WR_FLEX8 ENTERABLE:** a production option (the outside reviewer's; e.g. `--mix-flex-wr-rows 8`: member_bounds (WRs, 4,
  4) on the first 8 book solves in build order, study 73's machinery), with its format agreed first. A CONDITION of any
  live use: a parity test showing the same ruled rows and books under production's `member_bounds` as under this
  harness's frozen `set_constraints` rule, on fixtures. Then the laptop's review, merged before FRIDAY_HEAD only after his morning decision (default
  OFF), Friday's A3 ON run, his choice at Saturday's arming.
- **Otherwise, or if any step is not clean by Friday evening:** W6, or closed.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406, never a decision bank; Rev6; `~/s75-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10;
  `results_bank1406.jsonl` `91373a5c…`):
  - every arm is 41 rows within production's constraints (13 / 6, QB 5, overlap 4), with 8 term rows and every row in the
    pool;
  - WR_FLEX8 and NORB_FLEX8: 8 of 8 ruled, 0 infeasible, at book positions 0, 2, 3, 5, 6, 7, 9, 10 (all big-read);
  - flex of 26 (WR / TE / RB): LIVE_CB 4.3 / 15.7 / 6.0; WR_FLEX8 10.3 / 12.3 / 3.3; NORB_FLEX8 6.0 / 16.3 / 3.7;
  - projection per row: WR_FLEX8 −0.24, NORB_FLEX8 −0.03; rows shared with LIVE_CB 1.3 / 17.7; dealt identical 0.000 /
    0.667.
- **The full-path smoke** (2024 W10, 2022 W6 scored on bank 1406; `~/s75-panel/smoke-full/`): the reader exited 0 with 41
  lines and 3 sections. Only the exit code, the line count and the section count were read.
- **The binding (support) census** (the reviewer's; outcome-blind; bank 1406; all 53 slate-banks of 2022–24; code
  `bb66c2e` clean; lab `results/s75/CENSUS_s75_binding.txt` `bb8d21ae…`, the raw mechanics rows `census_mechanics_bank1406.jsonl`
  `65ded1fb…` with no outcome field, committed at `f3c6d0d`):
  - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
  - WR_FLEX8 and NORB_FLEX8: 8 of 8 ruled on every slate-bank, 0 infeasible, all at book positions 0, 2, 3, 5, 6, 7, 9,
    10 (read by big contests: 1.000);
  - flex of 26 (WR / TE / RB): LIVE_CB 6.2 / 15.2 / 4.6; WR_FLEX8 11.0 / 11.6 / 3.4; NORB_FLEX8 7.2 / 15.2 / 3.7;
  - QB + 2 rows 12 of 26 in every arm;
  - projection cost −0.12 / −0.03 per row;
  - rows shared with LIVE_CB 2.0 / 12.9; dealt identical 0.000 / 0.377 (no dead lever; NORB_FLEX8 is exploratory).
  - Disclosed: the laptop's study 74 census re-run was running at the same time (the build time, 105 s per slate-bank,
    reflects that; the mechanics are seeded).
- **Code:** nfl2 `production/s75-flex-mix-20261008` @ `bb66c2e` (the outside reviewer's draft):
  - `experiments/s75_flex_mix.py` `e9948fd9…`;
  - `scripts/s75_drive.py` `ad24227c…`;
  - `scripts/s75_census.py` `0c8e45e5…`;
  - **`scripts/s75_report.py` (the reader) `dfc6c9a2…`**;
  - `tests/test_s75_flex_mix.py` `cb34210f…` (6 tests; with study 74's 6, 12 pass);
  - unchanged and sha-asserted: `s73_topg_qb1.py` `3f76c629…` (with its pinned `s48_winner_like.py` `c22d2811…`,
    `s53_cheap_pref.py` `f3f9d735…`), `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`;
  - the plan: `ac10ddf6…`.
