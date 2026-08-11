# TabPFN stage calibration audit

Date: 2026-08-11

This is the descriptive R1-prime audit proposed by the corrected outside
deep-calibration review. It was run while the independently preregistered
served-position diagnostic was already executing; it could not alter that
diagnostic's fit, grid, gate or evaluation.

## Population and method

- Accepted panel: `20260810-lockfix-e80-k1-8677d21`.
- Seasons: 2023--2025.
- Positions: QB/RB/WR/TE.
- Rows: accepted `research_eligible` player rows joined to
  `nfl_features.player_week_training` with `was_active = TRUE` and to the
  corresponding `nfl_features.tabpfn_projections` cache row.
- A latest-row qualification was applied before joining. The result has the
  same RB/WR/TE counts as the immutable final-served audit: 3,961 RB, 6,115 WR
  and 3,800 TE rows. It additionally measures 1,520 QB rows.
- Exceedance is `actual > cached quantile`. No candidate or lineup table was
  generated or scored.

## Aggregate cache results

| position | rows | q90 | q95 | q99 |
|---|---:|---:|---:|---:|
| QB | 1,520 | 9.079% | 4.671% | 1.184% |
| RB | 3,961 | 9.392% | 4.519% | 1.439% |
| TE | 3,800 | 8.184% | 4.053% | 0.711% |
| WR | 6,115 | 10.777% | 5.953% | 1.635% |

For the positions included in the prior immutable final-served report, q99
moves by stage as follows:

| position | TabPFN cache, pre-blend | final served | change |
|---|---:|---:|---:|
| RB | 1.439% | 1.565% | +0.126 pp |
| TE | 0.711% | 0.737% | +0.026 pp |
| WR | 1.635% | 1.881% | +0.246 pp |

## Interpretation

The positional imbalance is already present in the cached TabPFN quantiles.
The 45/55 market mean shift modestly amplifies RB/WR q99 exceedance but is not
its primary cause; TE remains over-wide at both stages. This supports the
already-running post-blend per-position recalibration as the correct immediate
instrument and identifies a separate operating defect: weekly TabPFN cache
generation lacks per-position q95/q99 acceptance and drift reporting.

Before Week 1, add a fail-closed cache-quality report that emits per-position
q90/q95/q99 calibration on the available walk-forward validation rows and
alerts on material drift or missing position support. It must not use the
target week's outcome and must not silently switch the submitted policy.

The full season/fold output is reproducible with the query recorded in the
associated handoff milestone; no production policy changes are licensed by
this descriptive audit alone.
