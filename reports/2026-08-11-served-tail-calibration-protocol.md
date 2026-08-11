# Full served-path tail-calibration protocol

Frozen on 2026-08-11 CDT before any post-shaper/post-market q90/q95/q99
exceedance result was generated. The raw component-composed control result is
already known: on 13,876 held-out RB/WR/TE player-weeks, realized points
exceeded its q90/q95/q99 at 11.11%/7.10%/2.69%. This protocol does not
re-adjudicate that closed Route Share arm. It asks whether the same defect
survives the additional transformations that actually score the adopted
lineup book.

## Question

Is the adopted K=1 selection distribution still materially under-dispersed
in the upper tail after the production marginal shaper and 45/55
model/prop-market mean blend?

This is a diagnostic of the existing production belief distribution, not a
new predictive arm. It changes no model, draw, lineup, selector, registry or
UI behavior.

## Frozen path and population

Reproduce the current baseline replay path with:

- `MODEL_ENSEMBLE=1` and no `EXTRA_FEATURES`;
- the existing component models trained walk-forward on seasons strictly
  before each held-out season;
- 10,000 simulations with the possession game simulator and asymmetric team
  factors;
- fitted draw widening;
- `TABPFN_MARGINALS=1`, with the normal empirical-marginal fallback retained
  and its row coverage reported;
- full shaping (`SHAPE_MIX=1`); and
- the existing prop-market mean blend with model weight exactly 0.45.

Forbid every other model, simulation, mean, tail, route, coverage,
construction and candidate A/B lever. The blend may shift every row's draws
to its blended mean but may not independently scale their spread.

Use held-out seasons 2023, 2024 and 2025. Restrict to active Sunday-main
RB/WR/TE rows present in corrected accepted panel
`20260810-lockfix-e80-k1-8677d21`, matching the raw component diagnostic's
primary population. Exact `(season, week, gsis_id, position)` parity and
actual-score agreement within the canonical 0.11-DK-point rounding tolerance
are mandatory. Report any row-count difference from 13,876 and fail closed
rather than silently changing the population.

The recomputed post-shaper model mean and post-blend mean must match the
accepted panel's persisted `model_points_pre` and `mean_projection` within a
fixed absolute tolerance of `1e-4` for every evaluation row. This proves that
the measured draws are centered on the same beliefs that scored the adopted
historical books.

## Frozen metrics

For each held-out season, position and aggregate, report:

- observed exceedance of empirical q90, q95 and q99;
- nominal-minus-observed calibration gaps;
- ordinary binomial and week-cluster-robust standard errors for every
  exceedance rate;
- pinball loss at 0.90, 0.95 and 0.99;
- empirical CRPS;
- point MAE;
- 20- and 30-point Brier loss from the final draws;
- event counts; and
- prop-market and TabPFN-marginal row coverage.

The cluster-robust variance treats `(season, week)` as the cluster and uses
the finite-cluster correction. Report the two-sided 95% calibration interval
and the corresponding minimum detectable absolute calibration gap
`1.96 * cluster_se`. No segment, salary band, route-share band or position is
allowed to select a recalibration rule from this diagnostic.

## Frozen decision and consequence

The full served-path upper-tail defect is confirmed only if:

1. all exact row/parity/environment checks pass;
2. aggregate observed exceedance is above nominal at q90, q95 and q99; and
3. the aggregate q99 exceedance rate's cluster-robust 95% lower bound is
   above the nominal 1% rate.

If confirmed, this licenses one separately preregistered, walk-forward,
mean-invariant tail-recalibration experiment. That later experiment must
choose its correction family, fit/calibration split, shrinkage, segments and
gate before its corrected held-out metrics or lineup scores are read. If the
defect is not confirmed, historical tail recalibration is closed and no
parameter search follows.

Regardless of disposition, this diagnostic cannot reopen any closed vendor
arm or retroactively replace its registered gate. For future outcome-unseen
distribution arms, persist paired per-row metric differences, their standard
errors and a preregistered minimum detectable effect; CRPS and upper-tail
pinball/calibration may be primary where the intervention changes a full
distribution, while 20/30-point Brier remains mandatory.

## Result

Protocol was frozen and pushed at commit `16eec10`. The exact-population
alignment, production-environment guard, final-draw scorer, q90/q95/q99
calibration intervals, pinball/CRPS/Brier diagnostics, CLI and one-shot Cloud
runner were implemented and passed focused offline validation.

Exact-tree Cloud Build `98d988c4-ba7e-4dc6-b36b-73ec5842d761` from
implementation commit `f75ac08` passed 827 tests with two expected skips and
published immutable image digest
`sha256:4501adb4d4d7389feb931b4f2696eb780c18f3207d5e00732b54c5d616bdf7ff`.
The one immutable Cloud Run execution `served-tail-calibration-6fk9k`
completed successfully from that digest. It reproduced exact fold populations
of 4,666/4,596/4,614 rows with zero actual-score delta, zero post-shaper mean
delta, and maximum post-blend mean delta `3.55e-15`.

Aggregate q90/q95/q99 exceedance was 10.5794%/5.4627%/1.4774%. The q99
week-clustered 95% interval was 1.2526%--1.7021%, wholly above the nominal 1%.
The preregistered gate therefore passes with disposition
`served-upper-tail-defect-confirmed`. Fold q99 exceedance was
1.3288%/1.6971%/1.4088% in 2023/2024/2025. By position, q99 exceedance was
1.5653% RB, 1.8806% WR and 0.7368% TE; these are descriptive and may not
select position-specific corrections.

The durable report and raw execution record are under
`reports/served-tail-calibration-runs/20260811-served-tail-calibration-v1/`.
The confirmation licenses the one separately frozen experiment in
`reports/2026-08-11-served-tail-recalibration-experiment.md`; it does not by
itself change production behavior.
