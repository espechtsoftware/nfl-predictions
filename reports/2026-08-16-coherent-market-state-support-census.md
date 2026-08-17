# Coherent model/market-state construction: outcome-blind support census

Date: 2026-08-16

This census is limited to identity, source lineage, feature availability and
candidate-count support. It did **not** read `actual`, `actual_score`, payout,
contest rank, ownership, or any treatment effect. It precedes both the frozen
mechanism protocol and implementation.

## Frozen source panel

- Candidate table: `nfl_predictions.replay_candidates_staging`
- Player table: `nfl_predictions.slate_player_features`
- Native blocks: `20260815-atlas-money-worlds-r0-v1` through
  `20260815-atlas-money-worlds-r4-v1`
- Required repaired source: `20260816-atlas-mvp-repair-r3-2025-v1` for
  R3/2025 Week 1
- Scope: 2023--2025, Weeks 1--18 (54 slates)

The panel is the exact production-multinomial, five-block money source already
bound by the current-money transfer and downstream score-free construction
protocols. The player catalog is the matching R0 catalog. Its quarantined
`research_eligible=false` value is expected: these rows are consumed only
through the exact immutable research receipts, never as live production rows.

## Candidate-universe identity census

BigQuery job
`bqjob_r263b2f71bba5e61e_000001a00e055e74_1` split the R0 candidate roster
strings into distinct `(season, week, player_id)` keys and joined them to the
matching R0 player catalog.

| measure | count |
|---|---:|
| candidate-universe player keys | 8,577 |
| DST keys | 923 |
| missing catalog keys | 0 |
| non-unique catalog keys | 0 |

This is the relevant player universe. An earlier exploratory count over all
catalog rows, rather than players actually appearing in the registered
candidate universe, is superseded and must not be cited.

## Team-state eligibility census

A player is feature-covered only when all three of `market_points`,
`model_points_pre`, and `mean_projection` are non-null. A team is eligible
only when the candidate universe contains at least one covered QB and at least
two covered WR/TE players for that team. BigQuery job
`bqjob_r28d711a054e6602_000001a00e0530d9_1` produced:

| season | slates | eligible teams min / median / max | covered skill players min / median / max |
|---|---:|---:|---:|
| 2023 | 18 | 8 / 12 / 18 | 52 / 82 / 115 |
| 2024 | 18 | 8 / 13 / 22 | 69 / 85 / 155 |
| 2025 | 18 | 4 / 13 / 21 | 37 / 92 / 142 |

Every slate therefore supports the prospectively fixed top-three eligible-team
design. No post-treatment eligibility relaxation is permitted.

## Fixed-budget source census

BigQuery job `bqjob_r4e2918e63175d9b0_000001a00e05af20_1` verified that every
available native block/slate contains exactly 160 `lev` candidates. R0, R1,
R2 and R4 each contain all 54 slates; the original R3 panel contains the 53
intact slates. Candidate totals vary only with the already-registered source
generation and fall between 242 and 265 per slate.

BigQuery job `bqjob_r6ee21046dc632461_000001a00e05d0df_1` independently
verified that every one of the 18 repaired R3/2025 slates contains exactly 160
`lev` candidates; repaired Week 1 has 248 total candidates. The protocol uses
the repaired panel only for R3/2025 Week 1 and the original R3 panel elsewhere.

The treatment replaces exactly 12 candidates inside each train-four admitted
control pool and never increases the candidate budget. The source census also
shows ample tagged leverage supply for lineage diagnostics, but the frozen
removal rule ranks all admitted candidates on training worlds and does not
require a mutable minimum number of admitted `lev` rows.

## Support disposition

`support-complete`

The exact top-three-team, two-state, two-lineup design is supported on all 54
slates. This receipt licenses freezing and implementing an outcome-free
construction experiment only. It is not evidence of a scoring gain and does
not license production or UI changes.
