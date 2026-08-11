# Data-fitted within-team usage concentration protocol

Frozen on 2026-08-11 CDT before generating any new model-fitted concentration
estimate or held-out likelihood. This diagnostic uses player opportunity
counts only. It cannot query, generate, join, or score lineups.

## Question

The production simulator independently Poisson-draws each player's targets and
carries. Conditional on a team's realized total, that is a multinomial
allocation centered on the component model's predicted player shares--the
`K -> infinity` member of the same family as the optional within-team
Dirichlet allocation. Historical lineup tests used `K=20` and `K=8`, but
neither value was fitted from the component model's conditional usage errors.

The new question is:

> Does one global Dirichlet concentration fitted only from early out-of-sample
> target/carry allocation improve untouched conditional usage likelihood over
> the production multinomial allocation?

Known lineup scores from `K=8`, `K=20`, or any other panel are forbidden from
the estimator, gate, and implementation.

## Point-in-time prediction folds

- Use the canonical `player_week_training` data and the unchanged production
  component model with blank `EXTRA_FEATURES`, K=1 ensemble, 400 LightGBM
  rounds, and active-player filtering.
- Generate target/carry means separately for target seasons 2021--2025. For
  every target, train only on seasons strictly before that target using
  `components.train`; fill target-season cold-start fields with the existing
  production function before prediction. No target-season outcome may enter
  its component model.
- Seasons 2021 and 2022 are calibration-only. Fit the one global concentration
  from their out-of-sample predictions and observed opportunities.
- Seasons 2023, 2024, and 2025 are untouched evaluation folds. Their outcomes
  may be read only after the estimator and gate implementation are frozen in a
  committed, exact-tree-validated image.
- Restrict target-season rows to the canonical Sunday-main replay universe,
  `was_active = TRUE`, positions QB/RB/WR/TE, finite nonnegative component
  predictions, and finite nonnegative integer opportunity outcomes.

## Conditional allocation population

Construct independent `(season, week, team, kind)` groups for `targets` and
`carries`.

- Targets use non-QB rows and `y_targets`; carries use all four positions and
  `y_carries`.
- A group is eligible only when it has at least two players with strictly
  positive predicted opportunity and at least 15 observed opportunities among
  those players.
- If any active player excluded by a nonpositive prediction has positive
  realized opportunity of that kind, exclude the entire group and report it;
  do not silently move that player's count to another player or add an
  unregistered epsilon mean.
- Normalize strictly positive model means within each group to `p_i`. Preserve
  the complete ordered vector of player probabilities and observed counts.
- Report total and retained teams, players, opportunities, excluded-zero-mean
  groups, and minimum/maximum group sizes by kind and season. Mechanical
  validity requires at least 95% of otherwise eligible observed opportunities
  to remain after the zero-mean exclusion in every kind/season.

Conditioning removes team total and shared game-factor variation. Under the
production independent-Poisson allocation, the exact conditional reference is
`Multinomial(n, p)`. Under a finite concentration, it is the
Dirichlet-multinomial induced by the simulator's exact concentration law:

`alpha_i(K) = max(K * p_i, 0.05)`.

The `0.05` floor is retained because it is part of
`game_sim.allocate_drive_usage`; the diagnostic must not fit a cleaner but
different family.

## Frozen estimator

Fit one shared value of `K` to all retained 2021--2022 target and carry groups
by minimizing the sum of exact Dirichlet-multinomial negative log likelihoods.
Use deterministic bounded scalar minimization over `5 <= K <= 500` with
absolute `x` tolerance `1e-6`; then evaluate the two exact endpoints and keep
the lowest objective. A tie within `1e-10` chooses the larger K, closer to the
production reference. The value is rounded to six decimals only for display;
all scoring uses the unrounded value.

Mandatory output includes the fitted K, convergence/boundary status,
calibration objective curve on the fixed descriptive grid
`[5, 8, 12, 16, 20, 24, 29, 35, 40, 50, 65, 80, 100, 150, 200, 300, 500]`,
and calibration likelihood by season and opportunity kind. The descriptive
grid cannot replace or revise the frozen estimator.

## Untouched evaluation and gate

On exact retained 2023--2025 groups, compare the fitted finite-K conditional
negative log likelihood with the production multinomial reference. Report
paired differences by group, opportunity, kind, season, and aggregate, plus a
team-week-clustered bootstrap confidence interval as a diagnostic. The
bootstrap is fixed at 2,000 resamples with seed 8112026 and is not a veto or
rescue criterion.

The diagnostic passes only if all mechanical checks pass and:

1. the selected K is finite and strictly inside `(5, 500)`;
2. fitted-K aggregate mean NLL per group is strictly lower than production;
3. fitted-K aggregate mean NLL is strictly lower separately for targets and
   carries; and
4. fitted-K aggregate mean NLL is lower in at least two of the three untouched
   seasons.

No effect-size threshold, lineup score, mean fantasy-point metric, or prior
`K=8`/`K=20` result may veto or rescue the decision.

## Consequence

- **Pass:** licenses one separately preregistered exact-80 lineup comparison
  at the single unrounded fitted K, using the adopted CE0 / direct-role12 /
  boom40 / line-194 book and final-served position calibration. That lineup
  protocol must be committed before a finite-K candidate or lineup score is
  generated.
- **Fail:** closes the historical data-fitted allocation retry. Do not choose
  a new K, split K by target/carry/team/position, change the minimum total,
  relax the likelihood gate, or use lineup outcomes to reinterpret it.

Any pre-report mechanical or packaging failure licenses only a repair that
leaves this population, estimator, folds, family, and gate unchanged.
