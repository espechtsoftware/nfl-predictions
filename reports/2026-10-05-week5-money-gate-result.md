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

## Bottom line

**On Weeks 1–4 the current system would have returned about 0.48× of fees (range 0.36–0.67): it would have lost
money.** None of the tested selection changes does better in a way the data can support, and the current selection is
the best of them. **So the Week-5 question is how much to stake, not which version to run.** The staking evidence is P1
(`reports/2026-10-05-p1-contest-type-edge.md`, robustness section verified 10-05).

## The answers

**Q1. Would the current system have made money over Weeks 1–4? No.**
- A1 (the current selection and layout) returns **0.48× fees** (95% range 0.36–0.67). Without its single largest
  payout: 0.46× (0.34–0.64).
- By week: W1 0.85×, W2 0.65×, W3 0.00×, W4 0.17×.

**Q2. Does it beat chance (random picks from the same pools under the same caps and dealing, M2)?** Week by week:
**far above chance in Weeks 1–2, below in Weeks 3–4.**

| Week | A1's percentile among 1,000 random books (cashes) | Pool skill (projected vs realized rank corr.) |
|---|---|---|
| 1 | 100 | 0.36 |
| 2 | 99.95 | −0.32 |
| 3 | 8.9 | 0.30 |
| 4 | 16.9 | 0.03 |

Over all four weeks it is above the random median in 54 of 84 contests (contests share lineups, so they are not
independent). The selection beats random overall, but the books still lose money. That is consistent with P1: our
lineups sit about 8–10 DK points per lineup below what break-even needs in these fields.

**Q3. Is any alternative better? No.** Four weeks cannot license an arm (Addendum 2), and the evidence points the other
way:

| Arm | Weeks judged | Multiple | Without its largest payout | Row-level vs A1 (descriptive) | Reading |
|---|---|---|---|---|---|
| A1 current | W1–3 / W1–4 | 0.57× / 0.48× | 0.54× / 0.46× | — | the best of those tested |
| A2 top projected mean | W1–3 | 0.59× | 0.48× | **−5.2** pct points (p 0.14) | worse lineups than A1 |
| A3 tighter player cap (30%) | W1–3 | 1.47× | 0.91× | +1.0 (p 0.83): nothing | **one lucky cash**: a single W1 hit in a 3-contest week. On how its lineups actually finished it was **worse than A1 in all 3 weeks** |
| A4 no ownership tilt | W3–4 | 0.48× | 0.46× | **−4.7** (p 0.18) | worse: **the ownership term helps** |

- A3's money edge holds even without its largest payout only because Week 1 is so small. A3 is an option only as a
  risk preference (spreading exposure), not on evidence.
- The permuted false-qualifier rate is 0–2%.

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
