# Data-fitted within-team usage concentration result

Date: 2026-08-11 CDT

Frozen protocol: `reports/2026-08-11-data-fitted-dirichlet-usage.md`

Cloud Run execution: `usage-dirichlet-calibration-spd5k`

Immutable image:
`sha256:2d91c90e2b64277f12909c3069f6e7ffecc2cf0436167532c0144642f63e7462`

Machine report:
`reports/usage-dirichlet-calibration-runs/20260811-data-fitted-usage-k-v1/report.json`

Report SHA-256:
`7fd2a735d22294a9f75469eda4ce5230c9e20b52620bbb0bb0d01e5a478a6996`

## Disposition

`data-fitted-usage-concentration-passes`

The single global value fitted on out-of-sample 2021--2022 target/carry
allocation is:

`K = 28.246898139750336`

The optimizer converged in 22 iterations and the solution is strictly inside
the frozen `[5, 500]` bounds. The fixed descriptive curve has its lowest
registered point at K=29, independently corroborating the outside audit's
approximately-29 estimate.

## Untouched 2023--2025 evidence

| held-out population | production mean NLL/group | fitted-K mean NLL/group | improvement |
|---|---:|---:|---:|
| aggregate | 14.207682 | 13.317778 | 0.889904 |
| targets | 17.360592 | 16.824802 | 0.535791 |
| carries | 10.970002 | 9.716463 | 1.253539 |

The fitted value improved all three held-out seasons:

| season | production | fitted K | improvement/group |
|---:|---:|---:|---:|
| 2023 | 14.693002 | 13.681634 | 1.011368 |
| 2024 | 14.013144 | 13.141598 | 0.871547 |
| 2025 | 13.910611 | 13.125780 | 0.784831 |

The paired team-week clustered 95% interval for fitted-minus-production mean
NLL is `[-0.999386, -0.790824]`, entirely favorable. Evaluation contains 2,337
groups and 68,609 observed opportunities. Every target/carry season retained
100% of otherwise eligible opportunity; no positive realized opportunity was
excluded because of a zero model mean.

## Interpretation and consequence

The historical K=8 and K=20 lineup arms tested values more dispersed than the
model-fitted value and cannot close this new question. The production
independent-Poisson allocation is the conditional `K -> infinity` reference;
the data show that a finite, moderately concentrated within-team share draw is
substantially more realistic.

This distribution result does not itself prove a scoring improvement. It
licenses exactly one separately frozen exact-80 comparison at the unrounded K
above. No alternate K, target/carry split, selector, or score-selected retry is
authorized.
