# Week-2 supplier scorecard: which projection source was closest to what happened

Written 2026-09-21 by the workstation assistant. Realized points are the DraftKings FPTS from the Week-2 standings
exports; the comparison covers the 287 non-DST players priced at $3,000 or more who scored. Every source is the
value that existed before lock (the served batch of 16:02Z, the run frame, the cache tables, the archived simulator
banks). One slate; descriptive; not an adoption decision.

| source | players scored | correlation | Spearman | mean abs error | mean bias (realized minus source) | players projected 15+: source mean -> realized mean | top-20 by source that were top-20 realized |
|---|---|---|---|---|---|---|---|
| lab corrected-HSIM marginal (bank mean) | 287 | 0.647 | 0.702 | 4.25 | -0.93 | 18.4 -> 15.2 (n = 51) | 5 |
| production served projection | 287 | 0.603 | 0.637 | 4.55 | -1.33 | 18.3 -> 14.9 (n = 41) | 6 |
| lab incumbent marginal (bank mean) | 287 | 0.603 | 0.637 | 4.55 | -1.33 | identical to the served projection (it re-centres on it) | 6 |
| salary / 400 | 287 | 0.588 | 0.584 | 6.66 | -4.52 | 16.7 -> 15.3 (n = 42) | 6 |
| props market (frame market_points) | 171 | 0.570 | 0.607 | 4.77 | -0.44 | 17.8 -> 17.3 (n = 30) | 7 |
| TabPFN base cache (`tabpfn_projections`) | 287 | 0.559 | 0.625 | 4.50 | -0.62 | 16.4 -> 18.8 (n = 8) | 5 |
| 2025 season mean | 245 | 0.535 | 0.547 | 4.84 | +0.20 | 19.3 -> 15.8 (n = 20) | 5 |
| DraftKings one-game PPG (Week-1 score) | 251 | 0.464 | 0.531 | 6.08 | -1.13 | 23.2 -> 13.9 (n = 50) | 4 |

By position (correlation with realized):

| source | QB (38) | RB (85) | WR (134) | TE (30) |
|---|---|---|---|---|
| corrected-HSIM marginal | 0.79 | 0.66 | 0.60 | 0.28 |
| served projection / incumbent | 0.65 | 0.67 | 0.58 | 0.22 |
| props market | 0.17 (26) | 0.68 (48) | 0.65 (70) | 0.34 (27) |
| TabPFN base cache | 0.55 | 0.62 | 0.59 | 0.00 |
| 2025 season mean | 0.32 (35) | 0.64 (73) | 0.59 (109) | 0.43 (28) |

## Read

- The corrected-HSIM marginal was the best single source on this slate, and much the best on quarterbacks. This is
  the same component whose lineup-level correlation the laptop measured at -0.087 against the incumbent's -0.488: the
  bank that was least wrong at the player level was also least inverted at the lineup level. The Week-3 arm design
  (component attribution before any weight change) stands.
- The served projection (and the incumbent bank, which re-centres on it) beat salary alone only marginally and lost
  to the props market on receivers and tight ends; it beat the market clearly on quarterbacks, where the market's
  quarterback lines were poor (0.17).
- The props market was the only source that was not biased low at the top of the board (players projected 15+ scored
  within half a point of their market mean); every other source over-projected its top group by 3-9 points, the
  one-game DK PPG by 9.
- The one-game DK PPG is the worst source in the table and was the stand-in that served Jefferson at 25.3; it is gone
  from the live path on the market repair branch.
- No paid source can be scored: the SIS pass-tail, route-channel and schedule TabPFN variants have no Week-2 rows (their
  schedulers are paused), the Fantasy Points and SIS captures feed nothing live, and ETR never landed. "Which supplier
  is better" therefore has one answer this week: among what actually ran, the corrected-HSIM marginal; among external
  suppliers, the props feed, and only for receivers.

## What follows from it (proposals, not adoptions)

1. Keep the paired component attribution in the Week-3 shadow; the market-pull arm targets exactly the receivers where
   the market beat us.
2. The paid-source shadows cannot be judged until they run in-season; resuming them is the operator's gate decision,
   not a scorecard result.
3. Re-run this scorecard every Monday from the standings exports (it needs no nflverse load) and keep it beside the
   evidence record; the proper-score reader (CRPS, coverage) adds the distributional read when the nflverse actuals
   land.

Files: `handoffs/receipts/2026-09-21-week2-post-mortem/supplier-scorecard-week2.csv` (reply branch).
