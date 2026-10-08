# Preregistration: study 71b, the top-receiver bring-back on a few rows only, in the harness (FROZEN 2026-10-08)

**Status: FROZEN 2026-10-08 (18:50 CDT)** by the reviewer, after the smoke and the binding census (§6), before any scored bank.
- The DRAFT was `f121c044`. Nothing in §2–§5 changed at the census; §6 records it.
- **Next:** the laptop's ack (the banks and seed already scanned clean), the run, the confirmatory census before the
  read, the frozen reader, the laptop's re-run and the records.
- **Target:** read tonight. If TOPBB_N4 is ENTERABLE, the production row cap can be reviewed, merged before
  FRIDAY_HEAD and rehearsed on Friday's A3, for his choice at Saturday's arming (default OFF).

**Units:** probabilities, counts and rates only. Dollars stay in BigQuery and private files.

## 1. Why
- **The operator, 10-08 about 18:40,** on study 71: "For your test, were you doing that in every single lineup? I think
  it would be good to just do a very small percentage of these as a test."
  - This matches his standing preference (10-05): a portfolio of shapes, never one rule for the whole book.
- **Study 71** (Addendum 169) put the rule on all 15 A1 / B rows. It was NO DIFFERENCE, not contradicted, and neutral:
  read −1.9 points, 2022 +5.5.
- **A dose change needs its own test** before entry.
- **The prior, stated first: NO DIFFERENCE.** A smaller dose moves less. A "not harmful" small dose is what he would
  trial.

## 2. Arms (`experiments/s71b_topbb_n.py`)
**The book:** study 71's (study 48's harness; LIVE = 48d's 41 rows with the cheap +2 block through study 53's
`block_term` / `term_book`; Rev6 `ac10ddf6…`). Study 71's module is imported with its sha asserted (`2d287cf4…`), with
its `qb_top_wr` and study 70's `top_wr`.

- **LIVE_CB (the reference):** his live book with the cheap +2 block.
- **THE RULE:** study 71's. The lineup must hold its QB's opponent's top receiver. It is the pinned optimizer's
  interaction floor of 1 over the (QB, his opponent's top receiver) pairs, on solves of the cells that require a
  bring-back (A1, B).
- **THE ROW CHOICE (the production flag `--mix-bring-back-top-wr-rows N` mirrors it exactly):**
  - The floor goes on a solve of a designated cell (A1 or B) only while fewer than N BOOK rows have been committed under
    the rule.
  - "Book" means the solve's row index j (the rows committed before it) is below K_book (26). Spares never get the rule.
  - BUILD ORDER: term_book's fill, the live block first, then the term block.
  - A floored solve that is infeasible is re-solved plain, recorded, and does not count toward N.
  - No positions are named. In the round-robin fill each cell's first-built rows are dealt to that cell's earliest
    positions, so the ruled rows land near the head. The census reports where they sit.
- **TOPBB_N4 (the single DECISION):** the rule on 4 book rows, about 15% of the book.
- **EXPLORATORY TOPBB_N2:** on 2 rows.

## 3. Endpoint and rule (the reader `scripts/s71b_report.py`)
- **The reader is study 63's frozen reader** (`5c24b8b9…`). Its load, boot, verdict, go / no-go and trial functions are
  identical, which a test asserts. The names, the seed, the docstring, the definitions line (it shows study 71's sha
  twice in the slots of study 48's and study 53's, which study 71 pins), the secondaries and the infeasible-solve lines
  differ.
- **THE READ: 2023–24** (36 slates). TOPBB_N4 − LIVE_CB on P(≥ 1 big seat), per slate, on the calibrated field v2.
  - The interval is two-sided 0.95, with B 20,000.
  - **Banks 1623–1628, seed 20261116** (scanned clean by the laptop: 18,074 production and 8,117 lab blobs; three hex
    false positives; no result file).
- **THE GO / NO-GO: 2022** (study 51's frozen rule): the point estimate; CONTRADICTED if < 0.
- **Guards** as before. They gate a PASS only.
- **Verdict / THE TRIAL RULE:** as in studies 63–71. One decision arm, so no multiplicity.
- **EXPLORATORY:** TOPBB_N2 − LIVE_CB; each arm on l02; P(≥ 2); the rows with the top bring-back; the QB games; the
  infeasible solves.

## 4. What the harness can and cannot say (disclosed before the census)
- **The dose is smaller than N.** The live book already brings back the top receiver in about 3.7 of 26 rows. With the
  rule on 4 rows, the book carries about 5.0 (the smoke), because some ruled rows would have had it anyway.
- **The other rows change too.** The build is path-dependent: changing the first-built rows changes the caps and the
  overlap state for every later solve.
  - The smoke shared 0.3 of 26 rows with LIVE_CB.
  - Those rows follow the same rules as LIVE_CB's, so they are a re-draw of the same construction, not a different one.
  - The downside is therefore not capped row by row. It is measured on the whole book, which is what the endpoint reads.
- **The base is our simulator's mean, not FP's.** The lines are closing lines, as in every harness study.

## 5. What a verdict can do (the laptop's cut-off)
- **TOPBB_N4 ENTERABLE:**
  - the outside reviewer's row cap on the merged flag, with its parity test against this harness;
  - the laptop's review;
  - merged before FRIDAY_HEAD, default OFF;
  - Friday's A3 ON run (the receipt lists the ruled rows);
  - his choice at Saturday's arming.
- **Otherwise, or if any step is not clean by Friday evening:** it waits for W6.

## 6. Smoke, census and integrity
- **The mechanics smoke** (bank 1406, never a decision bank; Rev6; `~/s71b-panel/smoke/`; 2022 W9, 2023 W3, 2024 W10):
  - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
  - exactly N ruled book rows per slate-bank (asserted);
  - 0 infeasible.
  - The book positions of TOPBB_N4's top-bring-back rows, per slate-bank: 2.3 in positions 0–4, 2.0 in 5–9, 0.7 in 20–25.
  - Rows with the top bring-back: LIVE_CB 3.7, TOPBB_N4 5.0, TOPBB_N2 4.3.
  - Projection cost −0.05 / −0.02 per row.
  - Rows shared with LIVE_CB: 0.3 / 1.0.
- **The full-path smoke** (2024 W10 and 2022 W6 scored on bank 1406): the reader exited 0 with its 3 sections. Only the
  exit code, the line count and the section count were read.
- **The binding (support) census** (outcome-blind; bank 1406; all 53 slate-banks of 2022–24; code `c2f5638` clean; lab
  `results/s71b/CENSUS_s71b_binding.txt` `76d4f617…`, the raw mechanics rows `census_mechanics_bank1406.jsonl` `a05b581d…` with no
  outcome field, committed at `1b0d221`):
  - every arm is 41 rows within production's constraints, with 8 term rows and every row in the pool;
  - exactly 4 / 2 ruled book rows per slate-bank (asserted), with 0 of 212 / 106 floored solves infeasible;
  - every QB had an opponent's top receiver (52.5 of 52.5).
  - Rows with the top bring-back: LIVE_CB 3.43, TOPBB_N4 5.43, TOPBB_N2 4.21 of 26.
  - TOPBB_N4's top-bring-back rows sit at book positions 0–4 (2.47 per slate-bank), 5–9 (2.00), 10–14 (0.23),
    15–19 (0.25) and 20–25 (0.49): the head, as designed.
  - Projection per row: 128.98 / 128.92 / 128.94 (cost −0.06 / −0.04).
  - QB games 6.4 / 6.6 / 6.5.
  - Rows shared with LIVE_CB: 2.6 / 3.6; dealt identical 0.019 / 0.038 (no dead lever).
- **Code:** nfl2 `production/s71b-topbb-n-20261008` @ `c2f5638`:
  - `experiments/s71b_topbb_n.py` `1592a9c8…`;
  - `scripts/s71b_drive.py` `5aa365a2…`;
  - `scripts/s71b_census.py` `00699753…`;
  - **`scripts/s71b_report.py` (the reader) `256827bc…`**;
  - `tests/test_s71b_topbb_n.py` `17d3b50e…` (5 tests);
  - unchanged and sha-asserted: `s71_topbb.py` `2d287cf4…` (which pins s48 `c22d2811…`, s53 `f3f9d735…`, s70
    `d622a211…`), `term_book.py` `62c2306e…`, production's `enter_layout.py` `3cb051ac…`;
  - the plan: `ac10ddf6…`.

## 7. Order
1. The code and the smoke. Done.
2. The DRAFT (`f121c044`). Done.
3. The binding census. Done (§6).
4. The freeze. Done (this text).
5. The laptop's ack.
6. The run.
7. The confirmatory census before the read.
8. The read.
9. The laptop's re-run.
10. The records.
