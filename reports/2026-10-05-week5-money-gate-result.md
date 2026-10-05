# Week-5 money gate: result (2026-10-05 morning)

Written for the operator, under the frozen design `reports/2026-10-04-week5-money-gate-design.md` and its Addenda 1–2,
both committed before any arm was scored. The reviewer's check is pending.
- **Harness:** `production/moneygate-harness-20261005` @ `50823e3b`; scorer sha256 `48342ae1…`.
- **Units:** multiples of fees. Dollars are private (`~/private/moneygate/`).
- **Comparison base:** every arm uses today's selection code on each week's real archived pools, dealt into that week's
  real contests and scored against the real fields and payout ladders. Every arm excludes vetting.

**Known-answer gate: PASSED exactly, run before scoring and re-run after the Addendum-2 scorer change.** Scoring the
books we actually entered through the same code reproduces DraftKings' settled results:
- 534 of 534 entries match on rank, fee and tickets;
- cashes per week are 18 / 3 / 1 / 3, as settled;
- every week's total equals the entry history exactly.

Contest 196305080 (a hand entry with no ladder captured) is excluded from every arm.

## The answers

**Q1. Would the current system have made money over Weeks 1–4? No.**
- A1 (the current selection and layout) returns **0.48× fees** (95% range 0.36–0.67). Without its single largest
  payout: 0.46× (0.34–0.64).
- By week: W1 0.85×, W2 0.65×, W3 0.00×, W4 0.17×.

**Q2. Does it beat chance (random picks from the same pools under the same caps and dealing, M2)?** Mixed: well above
in Weeks 1–2, below in Weeks 3–4.

| Week | A1's percentile among 1,000 random books (cashes) | Pool skill (projected vs realized rank corr.) |
|---|---|---|
| 1 | 100 | 0.36 |
| 2 | 99.95 | −0.32 |
| 3 | 8.9 | 0.30 |
| 4 | 16.9 | 0.03 |

Pooled per contest: above the random median in 54, below in 30. The p of 0.01 is anti-conservative, because contests
share lineups. **So the selection step does better than random overall, but the books still lose money.** That is
consistent with P1 (`reports/2026-10-05-p1-contest-type-edge.md`): our lineups sit about 8–10 DK points per lineup
below what break-even needs in these contests.

**Q3. Is any alternative arm statistically better? No.** As Addendum 2 states, four weeks cannot license any arm.
Descriptively:

| Arm | Weeks judged | Multiple | Without its largest payout | Weeks better than A1 on finish | Row-level line vs A1 (descriptive) |
|---|---|---|---|---|---|
| A1 current | W1–3 / W1–4 | 0.57× / 0.48× | 0.54× / 0.46× | — | — |
| A2 top projected mean | W1–3 | 0.59× | 0.48× | W3 only | −5.2 pct points (p 0.14) |
| **A3 tighter player cap (30%)** | W1–3 | **1.47×** | **0.91×** | W1, W2 | +1.0 (p 0.83) |
| A4 no ownership tilt | W3–4 (= A1 in W1–2) | 0.48× | 0.46× | W4 only | −4.7 (p 0.18): the tilt helps |

- **A3 is the only arm that beats A1 on money**, and it does so even without its single largest payout (0.91× vs
  0.54×). Most of its gain is one large Week-1 cash (3.09× that week). It was worse than A1 in Week 3 (0 cashes;
  finish 47.7 vs 52.8), equal in Week 4, and its row-level line is flat.
- Condition (c) cannot pass on three weeks. Here it favoured A1 in all three weeks on the contest-weighted measure.
- The permuted false-qualifier rate is 0–2%.

## What this means (evidence; the stake is the operator's)

1. **On Weeks 1–4, today's system would have returned about half of its entry fees.** That is better than what was
   actually entered (0.26× in P1), but well short of break-even. No arm tested breaks even once its single biggest
   payout is set aside.
2. **The ownership tilt helps** (A4 is worse without it). **Picking the plain top projections (A2) does not beat the
   current optimizer.**
3. **A tighter per-player cap (A3, 30% instead of 50%) is the only candidate with a money signal**, mostly from one big
   week. If the operator wants a change for Week 5, this is the one the data point to: a reversible trial with the
   written rollback trigger (Addendum 1.5), and A1 built every week as the paper comparison. It is not statistically
   established.
4. **The bigger picture (P1):** the gap to break-even is in the lineups' scoring level against these fields, not in
   which rows we pick from the pool. The levers for that are pool generation and contest choice. Pool generation means
   the stack shape and game coverage, which need regenerated pools and were not tested here.

## Disclosed deviations (reviewer-accepted)
- **Lab source:** one lab source (32cdb61) for all weeks.
- **W1 supply:** one Saturday run.
- **W2 T-70 pool:** the D800 T-70-slot run. W2's A0 entered the Saturday K97, so A0 and A1 are not like-for-like there.
- **Ownership:** no ownership file in W1–2, so A1 = A4 there.
- **Routing:** today's routing rule.
- **Vetting:** no vetting in any arm.
- **M2:** the M2 comparisons exclude the W4 Millionaire.

**Why W4's A1 (0.17×) differs from what was entered (0.42×):** the entered book added a hand-entered Millionaire seat,
which is the cash that made the difference, and was re-ordered at vetting.
