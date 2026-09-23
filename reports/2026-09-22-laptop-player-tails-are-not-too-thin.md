> **CORRECTED 2026-09-22 (late) after a second season (2019). Read this box; the 2021-only text below is superseded where
> it says tails are "wide".**
>
> | | 2021 | 2019 | ideal |
> |---|---:|---:|---:|
> | player-games above sim p99 | 0.60% | **1.75%** (WR 2.19, RB 1.87) | 1% |
> | lineups above independent-bank p99 | 0.35% | **1.79%** | 1% |
> | game-heavy (5+ from one game) lineups above p99 | 0.20% | 1.41% | 1% |
> | slate-level rank: outer-10% share / KS p | 0.06 / 0.18 | 0.12 / 0.46 | 0.10 / — |
> | realized vs simulated level sd across slates | 8.9 vs 11.2 | 11.2 vs 11.3 | equal |
> | WR below sim p10 | 3.5% | 4.5% | 10% |
>
> **Corrected conclusion.** Upper-tail calibration **varies by season** (thin in 2019, wide in 2021; pooled ≈ 1.2% above p99,
> close to nominal), so "the tails are not too thin" was a one-season result. What holds in **both** seasons:
> (1) the **slate level is calibrated**, spread correctly across 35 slates; (2) **co-booms are not under-simulated**:
> game-heavy lineups exceed their tails no more than 4-from-one-game lineups do; (3) the 2019 lineup-tail excess is
> **concentrated on the highest-level slates** (W5 10.8%, W1 5.8%, W4 4.2% above p99; level ranks 0.987, 0.961, 0.862).
> Lineups break their simulated ceilings **when the whole slate scores high**, and high slates arrive at the calibrated
> rate. So the missing ceiling is still best read as the level draw (W1-2026 at rank 0.98) plus field size, not a structural
> tail or co-movement defect. The confidence is lower than the 2021-only text claimed.
> **Replicates in both seasons:** WRs bust **less** often than simulated (3.5% and 4.5% below p10), so WR floors are
> simulated too low. The QB bust result (14.6%) **does not** replicate (10.8% in 2019).
> Scripts (season as the first argument): `reports/lab-handoffs/2026-09-22-{tail_calibration,lineup_tail,level_rank}-by-season.py`.

# The simulator's missing ceiling is not a tail defect: players, lineups and slate level are all calibrated or wide (2021)

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

## Follow-up (same evening): the joint tail and the slate level, same 2021 slates

**Joint tail** (`reports/lab-handoffs/2026-09-22-lineup-tail-calibration-2021.py`): a 240-lineup boom pool per slate (production
stack), each lineup's realized score placed in its own distribution on an **independent** bank. 4,320 lineups:

| | > sim p99 | > p95 | > p90 | mean PIT |
|---|---:|---:|---:|---:|
| all | **0.35%** (1%) | 2.38% (5%) | 5.51% (10%) | 0.451 |
| 4 players from one game | 0.43% | 2.34% | 5.93% | 0.446 |
| 5+ from one game | 0.20% | 2.46% | 4.72% | 0.460 |

The simulator **over-states** the lineup tail (as the lab's 036 found), and game-heavy lineups are no exception. By slate, the
share above p99 is 0–2.1%. **Co-booms are not under-simulated.**

**Slate level** (`reports/lab-handoffs/2026-09-22-slate-level-calibration-2021.py`): the realized mean of a 120-lineup pool,
ranked among the 10,000 per-world means on an independent bank. Ranks across the 18 slates run 0.044–0.749; **6%** fall in the
outer 10% (calibrated 10%); KS against uniform p = 0.175. The simulated level sd **11.2** is wider than the realized
across-slate sd **8.9**. The simulator runs **slightly high** on average (12 of 18 ranks below 0.5; pool mean 121 vs 116).

## Conclusion
On the 2021 replay, **none of the three candidate mechanisms is too narrow:** per-player tails, joint (co-boom) tails and
slate-level dispersion are calibrated or conservative. The Week-1 2026 winning line sitting outside the simulated worlds
(world-rank 0.98) is what a **rare high-scoring slate** looks like under a calibrated level, about 1 week in 50, not a
structural simulator defect. That strengthens production's structural reading (`2026-09-22-production-what-winning-requires.md`):
the large-field winning line is out of reach because the field is large, not because generation cannot see it. Ceiling
work should target construction and field-relative position, not simulator dispersion.

Limits: one season; the lab replay centring (`NFL2_CENTER=mean`), not the live production-centred path; boom-only pools.
Running the same three scripts on 2025 would need the sealed season's unseal, which is the operator's call.
