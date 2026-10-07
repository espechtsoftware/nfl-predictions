# Preregistration: study 56, fewer QB+1 rows in his live book, in the harness, with a 2022 go / no-go (DRAFT 2026-10-07)

**Status: DRAFT 2026-10-07.** The reviewer committed it BEFORE reading study 54. Study 54's PLAIN arm (the house shape on
every row: QB + 2 + one bring-back) is close to this study's arms, so its read would bear on this design.
- The code, the smoke, the binding census, the bank scan and the freeze follow.
- The laptop acks the census, scans the banks and re-runs the frozen reader.

## 1. Why
- **The source:** study list item 56, the operator 10-07 ~12:00: "I agree with your recommendations if they pass the
  necessary tests". It is approved for testing as a Week-6 candidate; the reviewer designs it.
- **The outside reviewer's evidence** (`d9494619` §2; every W1–4 satellite and qualifier contest in contest_entries: 76
  contests, 42,309 lineups; Mantel–Haenszel odds of a top-10% finish in the lineup's own contest):
  - QB+1 vs QB+2: 0.83 [0.74, 0.93];
  - QB+3 vs QB+2: 1.02. The Millionaire's QB+3 edge does not carry to the satellites.
  - So the question is framed as **fewer QB+1 rows in favour of QB+2**, judged at the satellite lines, not as more QB+3.
- **His live book:** about 56% of its dealt entries are QB+1 (cells B and C). The field is about 52% QB+1.
- **After-the-fact evidence:** a top-10% lineup is conditioned on its outcome. The test here is the before-the-fact
  version on study 48's harness, at the installed plan's lines.
- **The prior, stated before any outcome:** QB+2 rows correlate more. That can raise P(≥ 1 big seat) and lower expected
  big seats. Study 18's WS arm (QB + ≥ 1, most rows QB+1) PASSED on tickets at draft-A lines, which points the other way.
  NO DIFFERENCE is the likeliest reading.

## 2. Arms (`experiments/s56_fewer_qb1.py`)
**The build:** on each slate-bank, his live Week-5 book and production's 15 spares, 41 rows through one state, on study
48's harness (`s48_winner_like.py` `c22d2811…`, sha-asserted). Everything is held as live: the winners' mix cells,
mix_fill's round-robin, overlap limit 4, QB cap 5, caps 13 / 6, player_mean. Only the cell QUOTAS change (the dealt-entry
shares the fill allocates and interleaves to):

| arm | A1 (QB+2, bring-back) | A2 (QB+2, none) | B (QB+1, bring-back, pair) | C (QB+1, none) | QB+1 share |
|---|---|---|---|---|---|
| **LIVE** (reference; study 48d's) | 0.30 | 0.14 | 0.28 | 0.28 | 0.56 |
| **QB2HALF** (THE DECISION) | 0.44 | 0.28 | 0.14 | 0.14 | 0.28 |
| **QB2ALL** (exploratory) | 0.58 | 0.42 | 0 | 0 | 0 |

- **QB2HALF** moves half of each QB+1 cell's quota to its QB+2 counterpart with the same bring-back rule: B to A1, C to A2.
- **The mechanism:** a context manager sets `s28_winners_mix.QUOTAS` (which mix_fill reads at call time) for that arm's
  build and restores it afterwards. The cells' StackRules are unchanged.
- **Production's constraints** are asserted on every arm's 41 rows. Each arm is dealt by the head layout.
- **Production's vehicle for a Week-6 adoption:** a new named portfolio in `mix_shapes.PORTFOLIOS` (union_reselect
  `--mix-portfolio`), with the same cells and these quotas.

## 3. Endpoint and rule (the reader `scripts/s56_report.py`)
- **THE READ: 2023–24** (36 slates).
  - QB2HALF − LIVE, P(≥ 1 big seat) per slate on the calibrated field v2.
  - Two-sided 0.95. B 20,000, seed 20261107; slates resampled within season.
  - Banks 1581–1586. The unique-blob scan precedes the freeze.
- **Guards** (v2): guard 1, mean entry pct, one-sided 0.95 lower > −0.015; guard 2, expected big seats ratio ≥ 0.80.
  **The guards gate a PASS only.**
- **Verdict:** DEAD LEVER / WORSE / PASS (lower > 0, at most one season mean < 0, both guards) / FAIL (guard) / NO
  DIFFERENCE.
- **THE GO / NO-GO: 2022** (17 k1 slates with real Millionaire ownership, the same banks): CONTRADICTED if the point
  estimate is < 0.
- **STUDY:** ADOPTABLE (a Week-6 candidate, his decision) only on a PASS that is not contradicted.
- **THE TRIAL RULE** (adoption track v2: the operator may run a reversible trial before a scientific PASS). This is study
  51's frozen rule, for QB2HALF:
  - NOT ENTERED if WORSE on the read, CONTRADICTED on 2022, or the read's expected big seats ratio < 0.80 (his
    tolerance);
  - MOOT on a dead lever;
  - otherwise ENTERABLE, his decision.
- **EXPLORATORY** (two-sided 0.95):
  - QB2ALL − LIVE, on the read and on 2022;
  - the decision on l02;
  - P(≥ 1 big seat) over the plan's SATELLITES only (the plan's contests less the Millionaire), QB2HALF − LIVE, on the
    read and on 2022 (the outside reviewer's "judged at the satellite lines");
  - levels, projection, dealt QB+1 / QB+2 / QB+3 shares and distinct QBs.

## 4. What a verdict can do
- **ADOPTABLE or ENTERABLE:** a Week-6 candidate for his decision, through a named portfolio. Study 38 would gain a paired
  paper arm (his live construction at QB2HALF's quotas) from the week it is proposed.
- **Otherwise:** the quotas stay as they are.

## 5. Production parity
- The quotas are production's MIX quotas (`mix_shapes.CELLS`, the same four cells). Only the shares change.
- The fill, the caps and the QB cap are study 48d's emulation of his live book (the reference for studies 48–55).

## 6. Smoke and integrity
(Added at the freeze: the smoke, the binding census, the bank scan, the code shas.)

## 7. Order
1. This DRAFT.
2. The code, the smoke, then the binding census.
3. The freeze.
4. The laptop's ack and bank scan.
5. The scored run.
6. The confirmatory census, committed before the read.
7. The read.
8. The laptop's re-run.
9. The LEDGER row (after merging study 54's branch) and an Addendum.
