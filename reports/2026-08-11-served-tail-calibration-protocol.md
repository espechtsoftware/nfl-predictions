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
primary population. Exact `(season, week, gsis_id, position, actual)` parity
with the accepted panel is mandatory. Report any row-count difference from
13,876 and fail closed rather than silently changing the population.

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

## Pre-result status

Protocol frozen. Implementation, exact-tree validation, Cloud Run execution
and final metrics have not started.
