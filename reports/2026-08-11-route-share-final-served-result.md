# Route Share independently calibrated final-served result

Date: 2026-08-11 CDT

Frozen protocol:
`reports/2026-08-11-route-share-final-served-recalibration.md`

Cloud Run execution: `route-final-served-calibration-lkwk2`

Immutable image:
`sha256:4dbb7e7658225ca14f28f0d97d87d648682e7471a7e1e26362ad7b4ff9f45fee`

Durable machine report:
`reports/route-final-served-calibration-runs/20260811-route-final-served-calibration-v1/report.json`

## Disposition

`route-final-served-calibration-fails`

The treatment did not strictly improve the preregistered aggregate calibrated
30-point Brier loss. It was exactly equal to control:

| metric, 13,876 held-out RB/WR/TE rows | control | Route treatment |
|---|---:|---:|
| 30-point Brier | 0.0140250212164889 | 0.0140250212164889 |
| 20-point Brier | 0.0494691857358028 | 0.0494691857358028 |
| q90 exceedance | 10.4641106947% | 10.4641106947% |
| q95 exceedance | 5.3329489767% | 5.3329489767% |
| q99 exceedance | 1.3692706832% | 1.3692706832% |

The paired 20/30 Brier deltas are exactly zero in every week cluster. CRPS
differed by only `-2.73e-10` and point MAE by about `+2.25e-9`, numerical-scale
differences that are diagnostic-only and cannot rescue the failed primary
gate. Both arms preserved every row mean within `7.11e-15`.

## Mechanical validity

- The immutable Route source matched 26,881 resolved rows, 1,029 players and
  all four frozen hashes.
- Control and treatment aligned on every key and actual. Fold populations were
  exactly 5,115 / 5,177 / 5,098 / 5,121 for 2022--2025 and the held-out primary
  population was exactly 13,876.
- Control reproduced every accepted post-shaper and post-market mean within
  `3.55e-15`; actuals were exact.
- TabPFN coverage was 100% in both arms and every season. Market coverage was
  identical by arm.
- The strict walk-forward calibration schedule was honored and the mean
  invariant passed.

## Mechanism interpretation

The independently fitted factors were identical between arms in every target
season:

| target | calibration seasons | QB | RB | TE | WR |
|---:|---|---:|---:|---:|---:|
| 2023 | 2022 | 0.980 | 0.995 | 0.975 | 1.015 |
| 2024 | 2022--2023 | 0.915 | 0.980 | 0.975 | 1.075 |
| 2025 | 2022--2024 | 0.950 | 0.970 | 0.960 | 1.075 |

This is consistent with the corrected TabPFN audit. The component arm changes
the pre-shaping simulated values, but the shared 100%-covered TabPFN layer
rank-remaps each player's worlds onto the same cached player marginal; the
same market mean is then applied. Consequently the Route fields make no
material contribution to the served per-player marginal that the registered
Brier gate tests. They can only alter the assignment of those fixed marginal
quantiles across simulation worlds--a dependence/rank-coupling effect--and
that is not evidence of improved tail probabilities.

## Consequence

The frozen protocol licenses no exact-80 lineup comparison. Do not rerun this
historical Route treatment with another calibration objective, factor grid,
position subset, model, or marginal gate. Keep the already-frozen 2026 paired
Route shadow as prospective evidence only; it does not change the production
policy. The next independent historical diagnostic is the already-frozen,
outcome-blind data-fitted Dirichlet usage concentration test.
