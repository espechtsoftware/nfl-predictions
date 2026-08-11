# Fantasy Points Route Share component-model protocol

Frozen on 2026-08-11 CDT before any control-versus-treatment component-model
prediction, simulation draw, component score or lineup score was generated.
The Route Share family and its auxiliary Ridge/logistic outcomes have already
been viewed, so this is a retrospectively motivated model-layer test rather
than independent discovery. Any historical pass must be labeled accordingly
and confirmed in the 2026 prospective shadow.

## Question and immutable source

Does strictly lagged true Route Share improve the K=1 LightGBM component
model's composed 30-point tail probabilities for DraftKings Sunday-main
RB/WR/TE players?

Use only private table `nfl_raw.fantasy_points_route_share`, previously
created by the hash-locked importer from the four registered 2022--2025
exports. Require exactly 26,881 resolved player-week rows, 1,029 resolved
players and this complete hash set:

- 2022 `68c92bcb01a97e9e603807496b44515c599bf6dd091ac7a47ec2c2802f9b4637`;
- 2023 `c4940b8d7163b2baf0734b0b70d5c5c9bee456c1c004c61341ebcc5aa97a81d0`;
- 2024 `45b68bb3fef0cd74c96ad88943141f37865647ef699f1e41553fca895f5408f7`;
- 2025 `305b5ff5523e09645ef41bd7f3c1f290b035e3d97b5f1d0c942815feebc43717`.

Every non-null source `(season, week)` must be strictly earlier than its
target `(season, week)`. Same-week values, season `TM RTE %`, ranks, games and
Fantasy Points Scored are forbidden.

## Frozen treatment

The control uses the current canonical component feature set with
`MODEL_ENSEMBLE=1`. The treatment changes only the feature matrix by adding
the four fields already registered in the first Route protocol:

- `fp_route_share_last`;
- `fp_route_share_l4`, the unweighted mean of up to four prior observations;
- `fp_route_share_jump`, latest minus the preceding observation; and
- `fp_route_cross_season`.

Use the existing `attach_strict_prior_route` implementation for both training
and evaluation data. Missing Route Share stays missing for LightGBM; it is
never zero-filled. Do not add a route threshold, projection band, position
interaction, hand coefficient, support transformation, alternate window,
trend, rank, route count, target share, or another Fantasy Points field.
Control and treatment use the same sorted feature order, training rows,
sample weights, component targets, LightGBM parameters, 400 boosting rounds,
simulation configuration and seeds.

## Frozen walk-forward population

Load the canonical `nfl_features.player_week_training` panel from season 2015
forward, restricted to active QB/RB/WR/TE outcomes exactly as production
training does. Attach Route features before training. Use three walk-forward
folds:

- target 2023 trains on seasons before 2023;
- target 2024 trains on seasons before 2024; and
- target 2025 trains on seasons before 2025.

Train all eleven existing component models in both arms. Component diagnostics
use the exact common set of active QB/RB/WR/TE player-weeks present on the
corrected accepted Sunday-main panel `20260810-lockfix-e80-k1-8677d21` in the
target season. The primary composed metrics and gate use its active RB/WR/TE
subset, because those are the positions to which Route Share applies. Salary,
identity and slate membership come only from that accepted panel; actual
component labels and point-in-time model inputs come from the canonical
training table. Duplicate or missing key matches fail closed.

The treatment is evaluated on every common row, including rows whose Route
features are missing. Report strictly-prior Route coverage separately and
require at least 80% coverage in each held-out fold.

## Frozen model and simulation evaluation

For each fold and aggregate, report:

- component MAE for all eleven predicted means, with rate components scored
  only where their observed denominator is positive;
- composed DraftKings point MAE;
- empirical CRPS from 10,000 common-seed component simulations;
- 20- and 30-point Brier loss from those simulations;
- q90/q95/q99 exceedance rates; and
- the same composed metrics by position as mandatory diagnostics only.

Use the repository's current component composition and clips. The diagnostic
must set and validate `MODEL_ENSEMBLE=1`, use the adopted possession simulator
with team-asymmetric factors (`GAME_SIM_MODE=possession`,
`GAME_SIM_TEAM_FACTORS=1`), unset every other model/replay A/B lever, and use
identical fixed simulation seeds per fold and arm. It must not read, generate
or select lineups.

## Frozen gate and consequence

The component mechanism passes only if:

1. strictly-prior Route coverage is at least 80% in each held-out fold; and
2. aggregate 30-point Brier is strictly lower for treatment on the exact
   common RB/WR/TE evaluation rows.

Fold and position stability, component errors, composed point MAE, CRPS,
20-point Brier and quantile exceedance are mandatory diagnostics but are not
vetoes under the operator's tail-first objective. No significance or
four-positive-season rule is restored.

A valid failure closes this exact full-component mechanism with no feature,
window, threshold, subset, model, round-count or gate retry. A pass licenses
one separately preregistered same-code Route-component lineup comparison; it
does not itself alter the adopted 80-entry policy or production registry.
Regardless of the historical result, the exact feature contract must be
collected and graded prospectively in 2026 before its evidence is described
as independent confirmation.

## Pre-outcome status

The strict-prior full-panel attachment, K=1 control/treatment component
harness, supported component metrics, efficient empirical CRPS, common-seed
10,000-draw possession simulation, frozen gate, CLI and one-shot Cloud runner
are implemented. The four fields are registered as opt-in candidate features;
with `EXTRA_FEATURES` unset, the production feature matrix is unchanged. The
live private-table source contract was verified at 26,881 resolved rows, four
exact hashes and 1,029 resolved players. Thirty-four focused Route,
component, feature-set and status tests pass, with compilation, CLI discovery,
shell parsing and whitespace checks clean. No new component control/treatment
has been trained or scored, and no lineup outcome has been queried under this
intervention.
