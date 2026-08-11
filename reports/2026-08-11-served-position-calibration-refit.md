# Served-position calibration refit protocol

Date frozen: 2026-08-11, before any new calibration replay or factor was
generated.

## Question and mechanism correction

The operator-supplied deep calibration audit correctly identified that
`calibration.fit_widen_factors` has no call site and that the documented
`DEFAULT_WIDEN` maintenance step was not repeated after material simulator
changes. It also identified a real held-out positional imbalance in the final
served q99 exceedance rates.

Those are two different questions in the current pipeline. `DEFAULT_WIDEN` is
applied before the TabPFN marginal mapper. The mapper uses only each row's
ordinal ranks and replaces its values with cached TabPFN quantiles. Any
positive mean-centred widening preserves those ranks and is therefore erased
for a TabPFN-covered row. The accepted 2023--2025 served-tail audit reported
100% TabPFN coverage on all 13,876 evaluated RB/WR/TE rows. Consequently a
stale `DEFAULT_WIDEN` can affect summary projections and uncovered fallback
rows, but cannot explain those final served-tail results.

This protocol answers both questions without changing production:

1. run the existing refit function on the current simulator's summary layer,
   as its docstring requires; and
2. fit a separate position-specific, mean-invariant scale at the **final
   served-draw layer**, after marginal shaping and market blending, where it
   can actually alter the distributions used by lineup generation.

Neither step is a lineup arm. No candidate or selected-lineup outcome may be
queried by this execution.

## Frozen source and split

- Accepted panel: `20260810-lockfix-e80-k1-8677d21`.
- Calibration seasons: 2019, 2021, 2022.
- Untouched evaluation seasons: 2023, 2024, 2025.
- Positions: QB, RB, WR and TE.
- Rows: all accepted `research_eligible` rows that the replay marks active.
- Simulation: 10,000 worlds, seed 0, model ensemble 1, possession simulation,
  asymmetric team factors, fitted upstream widening, TabPFN marginals with
  the production empirical fallback, shape mix 1, and 45/55 model/market
  blending.
- Each season trains only on strictly earlier seasons. Existing point-in-time
  feature and accepted-row parity checks remain mandatory.

## R1: documented summary-layer refit

Pool the calibration-season active rows and call the existing
`fit_widen_factors` unchanged on `position`, `actual`, `proj_p10`,
`proj_p50` and `proj_p90`. Its unchanged default grid is 1.00 through 2.60 in
steps of 0.05 and its unchanged loss is absolute lower/upper coverage error.
Report:

- the incremental factor by position;
- the implied absolute factor (`DEFAULT_WIDEN * incremental factor`);
- calibration and evaluation p10/p90 coverage before and after the refit; and
- final-path TabPFN coverage by season and position.

These factors are diagnostic only. They may not replace `DEFAULT_WIDEN`
because the summary layer is not the final lineup distribution and because
TabPFN-covered rows erase the upstream scale.

## R2: final-served per-position refit

For each position independently, scale every final served row around its own
simulation mean. The candidate factor grid is 0.750 through 1.500 in steps of
0.005, permitting both narrowing and widening. Means must remain invariant to
`1e-10`.

For each candidate factor, calculate q90/q95/q99 pinball loss in every
calibration season. Normalize each season/quantile cell to the identity
factor's loss and minimize their equally weighted mean. Ties within `1e-12`
are resolved by the factor closest to 1.000 and then by the smaller factor.
The four selected factors are frozen before evaluation is reduced.

Report control and treatment by calibration season, evaluation season,
aggregate and position for:

- q90/q95/q99 exceedance, calibration gap and pinball;
- CRPS and point MAE;
- 20- and 30-point Brier loss and event counts;
- paired week-clustered uncertainty for every loss; and
- row count, slate count, market coverage and TabPFN coverage.

The outside review's directional prediction is frozen as WR factor greater
than 1.000 and TE factor less than 1.000. No requirement is imposed on the QB
or RB direction.

## R2 gate and consequence

The final-served refit passes only if all of these hold on untouched
2023--2025 rows:

1. WR widens and TE narrows as predicted.
2. The equally weighted mean absolute q90/q95/q99 calibration gap across the
   four positions improves by at least 10%.
3. WR and TE each strictly improve their absolute q99 calibration gap.
4. The equally weighted position/season/q90/q95/q99 pinball ratio is at most
   1.000, and no position's corresponding ratio exceeds 1.010.
5. Aggregate CRPS worsens by no more than 0.5%; 20- and 30-point Brier each
   worsen by no more than 1%.
6. The maximum row-mean change is at most `1e-10` and all parity checks pass.

A pass licenses exactly one separately preregistered, same-image, exact-80
lineup comparison using these four frozen factors. A failure closes this
position-specific calibration hypothesis. This diagnostic itself never
changes the adopted policy, live jobs, UI, registries or accepted tables.

## Prohibitions

- Do not choose a second grid, objective, factor, position subset or season
  split after seeing the result.
- Do not infer a scoring gain from calibration alone.
- Do not retroactively reclassify a closed feature arm.
- Do not stage or modify the operator-supplied outside-review documents.

## Result

Exact-tree Cloud Build `fa8677da-1d00-4639-86fc-67622df925d5` passed 880
tests with two expected skips from preregistration/implementation commit
`fcbaf0f` and published immutable digest
`sha256:0c03d5f31eb2f786a02779502bc4ec6ef3dd03708a43d1ced381c83d033f9c00`.
The one guarded execution `served-position-calibration-47r24` completed
successfully. Its immutable report is under
`reports/served-position-calibration-runs/20260811-served-position-calibration-v1/`.

R1's unchanged summary-layer refit selected incremental factors QB 1.00,
RB 1.00, TE 1.10 and WR 1.05, implying absolute legacy summary factors
1.50/1.45/1.155/1.155. This does not alter final fully covered TabPFN worlds.
The separately recorded R1-prime SQL audit confirms that the q99 imbalance is
already present in the TabPFN cache and is only modestly amplified by the
market mean shift.

R2 selected the following factors using only 2019/2021/2022:

| Position | Final-served factor |
|---|---:|
| QB | 0.970 |
| RB | 1.005 |
| TE | 0.940 |
| WR | 1.070 |

On untouched 2023--2025 rows, position-averaged absolute q90/q95/q99
calibration gap fell `0.006113 -> 0.003149` (48.5%). The equal-weight
position/season/quantile pinball ratio was `0.996151`; every position was at
or below 1.000. Aggregate q90/q95/q99 exceedance moved
`10.496%/5.365%/1.448% -> 10.366%/5.242%/1.357%`. WR q99 moved
`1.881% -> 1.439%`, while TE moved `0.737% -> 1.079%`. Both Brier losses
improved slightly; CRPS worsened 0.3005%, inside the frozen 0.5% limit; and
maximum row-mean drift was `7.11e-15`.

Every frozen gate passed. This licenses exactly one separately frozen
exact-80 lineup comparison using these four factors. It does not itself
change production or retroactively reopen a feature arm.
