# Preregistration DRAFT: P3, the standing simple-baseline benchmark -- do our construction layers earn their place? (2026-10-07)

**Status: DRAFT** by the laptop, for the reviewer to check against his rule (10-07) and freeze BEFORE Week 5's results
load (Monday 10-12). The operator's approved-plan item P3 (`reports/2026-10-04-agent-proposed-studies.md`), his Wed
10-07 directive. No Week-5 outcome has been read.

**Units:** counts, rates and multiples only. Dollars stay in BigQuery and private files.

## 1. Why
- **The plan's prelim:** a props-only optimizer beat the entered book in mean points per row in 4 of 4 frames. That is
  a mean-points statement, and the entered book does not maximise mean points per row.
- **The reviewer's binding note:** score the benchmark on the book's own objective -- tickets, line hits and big seats
  by contest class, at each contest's own line.
- **The question, every week, on PAPER:** do OUR construction layers -- the shape portfolio, the fill order, the overlap
  limit, the QB cap, any term or block, the head layout's pins -- beat a plain capped optimizer on the same inputs?
- **What this study does and does not do:** it recommends keeping or simplifying. The operator decides. Nothing changes
  on the money path by itself.

## 2. Arms (built each week from the ENTERED T-70 union's own recorded inputs; `scripts/p3_arms.sh`)
- **ENTERED.** `union_paper_rebuild.sh <entered union> <out> same`. It must equal the entered `book.csv` byte for byte;
  otherwise the week's P3 read is VOID.
- **MEAN_MILP.** The plain capped optimizer, `--main pmo_x50`, on the week's LIVE projections (FP's from W5; ours
  before).
  - It keeps production's caps (main cap share, DST cap, salary floor, games per row) and the week's K.
  - It has NO ownership term, NO term block, NO sleeves (tail 0), NO winner order / select, NO QB cap, NO shape
    portfolio.
  - **It keeps the house stacking rules:** `pmo_rows` has no switch for them. So "no layers" means none of OUR
    construction layers, not a raw MILP.
- **PROPS_MILP** (descriptive). MEAN_MILP with the projections replaced by the market's props-implied DK points
  (`market_points`) wherever a player has props, else the live projection. Written by `scripts/props_projection_file.py`
  with the sidecar `apply_proj_source` requires (the frame's sha256 and the file's sha256).
- **M1 / M2 / M3** (descriptive): the monkeys, `scripts/moneygate_monkeys.py`. M1 is pool-random, M2 random under the
  entered book's caps and sharing, M3 random legal.
- **Determinism:** every paper arm is built twice, and its `book.csv` sha256 must match between the builds. An arm that
  fails to build, or builds differently twice, is VOID for that week; the void is recorded and the other arms stand.

## 3. Dealing
- Every arm's book is dealt into the week's REAL plan by the head layout (`enter_layout write <plan> <book.csv> <stage>
  --layout head`), with the plan's pins honoured, exactly as the entered book was dealt.
- The PLAYED book (after any R4 late swap) is reported separately, never as an arm.

## 4. Scoring (the binding scorer)
`scripts/moneygate_score.py`'s `place` puts each dealt entry among that contest's REAL entrants, with every real entry of
ours removed and DraftKings' tie split. It runs only behind the reconcile gate (its known-answer receipt).

- **PRIMARY: big seats.** By study 38's definition (the operator's utility): the number of dealt entries finishing
  inside a big contest's seats, using the plan's `big` and `seats` fields. For each week w:
  **d_w = big seats(ENTERED) − big seats(MEAN_MILP)**.
- **DESCRIPTIVE** (never decision-bearing):
  - per contest class (`moneygate_score.contest_class`): tickets (ticket contests) and line hits (cash contests: at or
    above the contest's own line), each with its multiple over the field's paid share;
  - P(≥ 1 big seat) and expected big seats on the Millionaire-field model (studies 31–37's endpoint);
  - PROPS_MILP against MEAN_MILP (the projection-source question belongs to study 38 and the weekly ours / FP / blend
    check);
  - each arm's percentile among the monkeys;
  - the R10 IC lines per arm (`book_vs_field_scoreboard.py`). The "projection IC" there is OUR projection's, even for the
    FP and props arms.

## 5. The rule (the reviewer's, 10-07)
- **Each prospective week from W5** scores +, − or 0 on d_w. A tie counts as neither. A week where ENTERED or MEAN_MILP
  is void does not count.
- **W8** (4 valid weeks): a descriptive read only.
- **W12** (8 valid weeks):
  - **"the layers are NOT earning their place"** if d_w < 0 in at least 7 of the 8 weeks (sign test, one-sided
    p ≈ 0.035);
  - **"the layers are earning their place"** if d_w > 0 in at least 7 of the 8;
  - otherwise **undetermined**.
  - If fewer than 8 valid weeks exist by W12, the read waits for the eighth.
- **The read is a recommendation to simplify or keep.** He decides.

## 6. Power, stated before any outcome
Big seats are rare: most weeks an arm wins 0–2. So many weeks will tie (d_w = 0), and the 7-of-8 rule will read
"undetermined" unless one side is systematically better. That is intended: the rule speaks only to a consistent
difference. The descriptive lines (tickets and line hits by class) carry the finer, non-binding picture.

## 7. Records
- **The season ledger:** `~/moneygate/results/p3_ledger.csv`, one row per week per arm (counts and multiples, no
  dollars). It also records the void flags and every build's book sha256.
- **Monday's report** prints P3's line beside P1's frozen record (`reports/2026-10-07-prereg-p1-contest-edge.md`).

## 8. Order
1. This prereg, frozen before W5 loads.
2. The W4 smoke: the whole pipeline on Week 4, a mechanics check. It is never counted.
3. Monday 10-12: the first counted read (W5), and every Monday after settlement from then on.
