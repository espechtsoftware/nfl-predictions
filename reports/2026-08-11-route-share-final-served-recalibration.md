# Route Share final-served fair-comparison protocol

Frozen on 2026-08-11 CDT before generating any new independently calibrated
control/treatment metric. The uncalibrated Route component results are already
known, so this is a retrospectively motivated new design, not independent
discovery. It cannot change the disposition of the closed component arm.

## Correction and question

The revised deep calibration audit correctly establishes that upstream
`SIM_WIDEN_DRAWS` factors are erased on TabPFN-covered rows because the
positive affine widening preserves ranks and TabPFN rank-remaps those ranks
onto its cached quantiles. Therefore this experiment must not refit or compare
the old upstream widen factors.

The new question is narrower:

> After the control and exact four-feature Route Share model are each
> calibrated on their own strictly prior **final-served** errors, does Route
> Share improve held-out 30-point tail probability on Sunday-main RB/WR/TE
> players?

“Final served” means after component simulation, fitted draw shaping, TabPFN
marginals (or the registered empirical fallback), and the 45/55 prop-market
mean shift. The calibration is the mean-invariant per-position spread
transformation already validated in the live path. It acts after every layer
that could erase it.

## Immutable data and feature arms

- Use the exact active QB/RB/WR/TE player-week population from corrected panel
  `20260810-lockfix-e80-k1-8677d21` for seasons 2022--2025: 5,115 / 5,177 /
  5,098 / 5,121 rows respectively. Primary RB/WR/TE evaluation seasons
  2023--2025 contain exactly 4,666 / 4,596 / 4,614 rows.
- Route history is only private table
  `nfl_raw.fantasy_points_route_share`, exactly 26,881 resolved rows, 1,029
  resolved players, and the four source hashes frozen in
  `reports/2026-08-11-fantasy-points-route-component-protocol.md`.
- Attach Route values with the existing `attach_strict_prior_route` function
  before training. Every non-null source week must precede its target week.
- Control uses blank `EXTRA_FEATURES`. Treatment uses exactly
  `fp_route_share_last`, `fp_route_share_l4`, `fp_route_share_jump`, and
  `fp_route_cross_season`. Missing values remain missing; no alternate window,
  threshold, interaction, transform, field, or hand coefficient is allowed.
- Both arms use K=1, 400 LightGBM rounds, the same active training rows,
  component targets, sorted feature order, seeds, 10,000 worlds, possession
  simulation, team factors, TabPFN cache, empirical fallback, market inputs,
  and model blend. No lineup is generated or scored in this diagnostic.

For every target season 2022--2025, train each arm only on seasons strictly
before the target and simulate the target from point-in-time inputs. The 2022
fold is calibration-only. Before 2022 there is no Route history from which a
model can learn a Route effect; that limitation is retained because it is the
honest information set that would have existed before 2023.

## Frozen independent calibration law

For each arm and each scored target season, fit factors using only that arm's
earlier out-of-sample folds:

| Scored season | permitted calibration folds |
|---:|---|
| 2023 | 2022 |
| 2024 | 2022, 2023 |
| 2025 | 2022, 2023, 2024 |

Fit one factor for each of QB/RB/TE/WR on the fixed grid 0.750 through 1.500
in steps of 0.005. For each position, minimize the equal-season mean of q90,
q95 and q99 pinball loss divided by that arm/season/quantile's identity loss.
Ties within `1e-12` choose the factor closest to 1.000, then the lower factor.
Apply the selected arm/target/position factors only to the corresponding
target fold after the market mean shift. Preserve every row mean within
`1e-10`.

This is walk-forward calibration, not score tuning: a 2024 factor cannot use a
2024 or 2025 outcome, and the treatment never borrows the control's errors or
factor. Factor curves, selected values, calibration-row counts and position
metrics are mandatory output. No factor may be revised after the first result.

## Mechanical validity gates

Before the scientific comparison may govern:

1. Exact source hashes, panel rows, strict-prior joins and fold populations
   must pass; control and treatment must have the same keys, positions,
   realized outcomes, market inputs and TabPFN coverage.
2. The only model difference is the exact four Route features. The only
   distribution correction difference is the independently fitted factor
   produced by the frozen law above.
3. Every target uses only the declared earlier calibration folds. TabPFN
   coverage and market coverage are reported by arm, season and position.
4. Control and treatment use identical simulation seeds. All final arrays are
   finite, 10,000 worlds wide, and mean-invariant within `1e-10` after scaling.
5. Report q90/q95/q99 exceedance and pinball, point MAE, empirical CRPS, and
   20/30-point Brier by season and position plus aggregate. Report paired
   week-clustered uncertainty and minimum detectable effect as diagnostics.

Any mechanical failure invalidates the experiment and licenses only a repair
that leaves the data, feature arms, factor law, metrics and decision law
unchanged.

## Frozen decision and consequence

The primary population is the exact 13,876 held-out RB/WR/TE rows from
2023--2025. The treatment passes only if its aggregate calibrated 30-point
Brier loss is strictly lower than the independently calibrated control. This
retains the original Route component arm's single tail-first gate. Season and
position signs, q90/q95/q99 calibration, 20-point Brier, MAE, CRPS,
uncertainty, and factor differences are mandatory diagnostics but are not
vetoes or rescue criteria.

- **Pass:** licenses exactly one separately preregistered, same-code,
  exact-80 lineup comparison using the newly adopted CE0 / direct-role12 /
  boom40 / line-194 book. The lineup protocol and both arm-specific served
  factors must be frozen before any new candidate or lineup score exists.
- **Fail:** closes this independently calibrated historical Route comparison.
  Keep only the already-frozen 2026 prospective Route shadow; do not try
  another factor objective, window, subset, model, position set, or gate.

This diagnostic cannot itself change the production registry, live position
factors, UI policy, or submitted lineups.
