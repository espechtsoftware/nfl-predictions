# Preregistration: study 56, fewer QB+1 rows in his live book, in the harness, with a 2022 go / no-go (FROZEN 2026-10-07)

**Status: FROZEN 2026-10-07** by the reviewer, after the smoke and the binding (support) census (§6), before any scored
bank.
- The DRAFT (`895cb346`) was committed BEFORE study 54's read, whose PLAIN arm (the house shape on every row) is close to
  this study's arms.
- Two additions were made before that read: the exploratory cheap-block arms (`ebb17277`), and the code (lab `ff66338` /
  `103516c`).
- Added after study 54's read, before the freeze: the operator's Week-5 line (`3cf242a0`, his words of 10-07) and §6.
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
- **Added to the DRAFT at about 13:37, still before study 54's read:** two EXPLORATORY arms with Week 5's live block. The
  operator's 10-07 trial puts the cheap +2 block in the 8-row slot, and if this tilt is adopted the two would run together.
  - **LIVE_CB:** LIVE plus study 53's CHEAP2_BLOCK8 block (`s53_cheap_pref.py` `f3f9d735…`, `term_book.py` `62c2306e…`):
    the +2 term on every non-DST player under $4,000, cap 2.0, at ranks 2, 5, 9, 12, 15, 18, 22, 25.
  - **QB2HALF_CB:** the same block at QB2HALF's quotas. The block's own rows allocate by the arm's quotas, as production's
    `--mix-cell-quotas` would make them.
  - Read only as QB2HALF_CB − LIVE_CB, the tilt beside his live block, on the read and on 2022.
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
- **THE WEEK-5 LINE** (the operator, 10-07, relayed verbatim by the laptop, added before the freeze): "If it doesn't seem
  like it will improve things, I don't want to do it this week. But I do think it's worth a test to find out as planned."
  - QB2HALF goes live in Week 5 ONLY on a PASS on the 2023–24 read that is not contradicted on 2022. Anything else stays
    on paper in Week 5 (study 38's paper arm MIXT_QA0_QB2HALF, amendment 6j).
  - The TRIAL rule's ENTERABLE stays a Week-6 trial option, his decision then.
- **EXPLORATORY** (two-sided 0.95):
  - QB2ALL − LIVE, on the read and on 2022;
  - QB2HALF_CB − LIVE_CB (the tilt beside the cheap +2 block), on the read and on 2022;
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
- **The smoke** (`~/s56-panel/smoke.sh`; code as committed at lab `103516c`, clean; bank 1406; 2024 W10 SCORED, 2022 W6
  MECHANICS ONLY):
  - every arm built 41 rows within production's constraints;
  - LIVE equals study 53's LIVE (= study 48d's), and LIVE_CB equals study 53's CHEAP2_BLOCK8, in rows and ranks on both
    slates (against study 53's amendment-1 smoke);
  - the quotas are reached: book rows per cell LIVE 8 / 4 / 7 / 7, QB2HALF 11 / 7 / 4 / 4, QB2ALL 15 / 11 / 0 / 0,
    QB2HALF_CB 12 / 7 / 4 / 3 (its block and its live part each allocate by the quotas);
  - the census and the reader exited 0.
  - **Disclosed:** the reader ran on a FAKE file (the 2024 row relabelled 2022 as well) to exercise the code. Its STUDY
    line, truncated at 40 characters, printed a verdict word for the single 2024 W10 slate-bank of bank 1406 ("not
    adoptable: QB2HALF FAIL (g"). That is one mechanics-test slate-bank, not a study bank.
  - The smoke's last check first named study 53's pre-amendment smoke, which has no CHEAP2_BLOCK8; it was re-run against
    the amendment-1 smoke (recorded in the log).
  - The log: lab `results/s56/SMOKE_s56.log`.
- **The binding (support) census** (outcome-blind; bank 1406; 53/53 (2022: 17; 2023–24: 36); code `f3c7549` clean;
  `results/s56/CENSUS_s56_binding.txt` `cc5f27b0…`, raw `84c07dc6…`; lab `08afaa9`). The first run (code `103516c`)
  printed a stale "three arms" in its header. The label was fixed (`f3c7549`) and the census re-run before the freeze.

  | 2023–24 | LIVE | QB2HALF | QB2ALL | LIVE_CB | QB2HALF_CB |
  |---|---|---|---|---|---|
  | dealt entries QB+1 / QB+2 / QB+3+ | .480 / .474 / .047 | .261 / .671 / .068 | 0 / .896 / .104 | .462 / .492 / .046 | .241 / .690 / .069 |
  | projection per row (change vs its reference) | 128.04 | −0.26 | −0.64 | −0.42 | −0.26 (vs LIVE_CB) |
  | predicted ownership per row | 78.56% | 78.14% | 77.70% | 76.74% | 76.64% |
  | book rows shared with the reference (of 26) | — | 3.9 | 2.3 | 16.3 | 4.1 |
  | identical to the reference | — | 0.000 | 0.000 | 0.000 | 0.000 |

  - **2022 is alike:** QB+1 .464 / .250 / 0 / .452 / .233; projection −0.20 / −0.51 / −0.42 / −0.27.
  - **Support holds:** every arm reaches its quotas on every slate-bank (passes 0, dropped 0). The cheap block applies on
    every slate-bank. The tilt costs about a quarter of a projected point per row.
- **Banks:** 1581–1586 and seed 20261107. The reviewer's unique-blob scan of both repositories (every blob up to 5 MB:
  17,670 in production, 7,996 in the lab; the 8 larger blobs per repository were not searched) found them only in study
  56's own records: this prereg's DRAFTs, `s56_drive.py` and `s56_report.py`. No result file for these banks exists on
  disk.
- **Code:** nfl2 `production/s56-fewer-qb1-20261007` @ `f3c7549` (the census at `08afaa9`):
  - `experiments/s56_fewer_qb1.py`, sha256 `1a1bbe0b14c36356a825071db7a23ff7a56bd5f1e3e774b41195effd5bbe7ad3`;
  - `scripts/s56_drive.py`, `f70b9bd56514c2b6eff5fb1215e67720d0c8bcbfeccc09f3e1d189aabdaafabb`;
  - **`scripts/s56_report.py` (the reader), sha256 `38fb00d768012390c4d08597706e1ff7affbc8da745c6c7174cbebc1185c6d1f`**;
  - `scripts/s56_census.py`, `767f3ed6585a24de87b2d3e599d8f1d6ee745ddaa3948c1255fff1d470b02030`;
  - `tests/test_s56_fewer_qb1.py`, `4330c3f1f183d528ad1f0e6d4cb3f827248fdede03aaf136fdb8754e08d51400` (7 tests);
  - unchanged, sha-asserted: study 48's `s48_winner_like.py` `c22d2811…`; study 53's `s53_cheap_pref.py` `f3f9d735…`;
    `term_book.py` `62c2306e…`; production's `enter_layout.py` `3cb051ac…` (pins-extend-review).
- **Production's vehicle:** integration `48946cd0`, `union_reselect --mix-cell-quotas` (default off, byte-identical).
  - Its tests check that the targets at K 26 are [11, 7, 4, 4] for QB2HALF (LIVE [8, 4, 7, 7]) and the 15 spares
    [7, 4, 2, 2]. The harness's allocation gives the same.

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
