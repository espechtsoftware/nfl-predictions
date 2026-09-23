# The simulator's missing ceiling is not thin per-player tails (2021 diagnostic)

Production's ceiling diagnostic (`db3cec6c`): the simulator's per-world pool best tops out around 200–225, while real
winning lines reached 236 and 274, so generation cannot build a winner from worlds that never contain one. One candidate
cause is that each player's simulated upper tail is too thin. This tests that directly.

**Design (a diagnostic; outcomes are used only to score calibration).** The 18 development slates of **2021**, chosen
because they are outside L01's 2022–24 panel so this cannot peek at it. Per slate, the production-law incumbent bank
(10,000 worlds, as generation uses). For every skill player projected ≥ 5 with a realized game, the PIT is the share of his
draws ≤ his realized DK points. Calibrated tails put 1% of players above their simulated p99, 5% above p95 and 10% above p90.
Script: `reports/lab-handoffs/2026-09-22-player-tail-calibration-2021.py`.

| 2,665 player-games | > sim p99 | > p95 | > p90 | < p10 |
|---|---:|---:|---:|---:|
| **all** | **0.60%** (ideal 1%; binomial band 0.62–1.38) | 4.09% (5) | 9.01% (10) | 7.62% (10) |
| QB (444) | 0.68% | 3.60% | 7.88% | **14.64%** |
| RB (784) | 0.64% | 4.34% | 8.55% | 9.95% |
| TE (355) | 0.85% | 3.66% | 8.73% | 6.20% |
| WR (1,082) | 0.46% | 4.25% | 9.89% | **3.51%** |

Mean simulated 12.25 vs realized 12.03 (level fine in 2021).

## Reading
1. **Per-player upper tails are not too thin. If anything they are slightly too wide** (0.60% above p99 against 1%, just
   outside the band; every position at or below nominal at p95 and p90). This agrees with the lab's 036/049b finding that the
   simulator over-states lineup-level tails, and it **rules out marginal tail width** as the reason the winning lines
   never appear in the simulated worlds.
2. So the ceiling gap must come from **the joint tail** (how often several rostered players boom together, i.e.
   game/team co-movement) or from **the slate-wide level**, the one simulator defect that survived production's Addendum 2
   (W1 at world-rank 0.98). A slate whose level lands in the simulator's top 2% is exactly where a 274 can appear in
   reality and not in the worlds.
3. **Lower tails are miscalibrated by position:** QBs finish below their simulated p10 **14.6%** of the time (they bust
   more than simulated), while WRs do so only **3.5%** (they bust less than simulated). The QB result is
   consistent with the availability and early-exit failures this season fixed only partly. The WR result means WR floors
   are simulated too low. Neither affects the ceiling, but both matter for the cash shadow.

**Limits:** one season (2021, before the 2022 inactive-row change; players with a realized 0 are excluded); the incumbent
bank only (not the corrected hsim law the selector also uses).

**Suggested next measurement (for production's ceiling work):** the same PIT at the **lineup** level, split by stack structure
(QB+2 same-game versus spread) on these 2021 slates. If stacked lineups' realized PITs pile up above p99 while spread
lineups' do not, the missing ceiling is within-game co-movement.
