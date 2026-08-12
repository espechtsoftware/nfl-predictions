# TabPFN team-QB-quality broadcast protocol

Status: frozen before implementing the feature, generating a cache, or
inspecting any team-QB-quality prediction, calibration metric, candidate, or
lineup score.

## Question

Current `qb_cpoe_l6` is player-level NGS data, reaches no pass-catcher, and is
populated on only about 29% of QB training rows. The warehouse already contains
play-by-play CPOE for a much broader set of team dropbacks. This experiment asks
whether a strictly-prior team passing-quality signal, broadcast to that team's
RB/WR/TE rows, improves their served 30-point probabilities and final
portfolio tail.

The feature targets the marginal channel. It is distinct from dependence
modelling and does not alter the possession simulator, stack rules, or existing
QB-only NGS feature.

## Sequencing and inherited baseline

This experiment starts only after the active-label and SCHED-sync sequences
reach terminal historical decisions. Both arms inherit every cache change that
passed its complete staged decision and omit every rejected change. The arms
differ only by the new team-QB-quality column.

## Frozen feature definition

Create `team_qb_cpoe_l6` as follows:

1. From `nfl_raw.pbp`, retain rows with `qb_dropback = 1`, non-null `posteam`,
   and non-null `cpoe`.
2. For each `(team, season, week)`, retain the sum of CPOE and contributing
   dropback count.
3. On the complete team schedule spine, compute
   `SUM(prior cpoe) / SUM(prior dropbacks)` over the six strictly previous team
   games, ordered by `(season, week)` and allowed to cross seasons. The target
   week's dropbacks are excluded. A live scheduled row therefore carries only
   completed-game information.
4. Join by the player's point-in-time team, season, and week. Populate the new
   feature only for RB/WR/TE; leave QB rows null so the experiment isolates the
   proposed broadcast and does not duplicate `qb_cpoe_l6` on quarterbacks.

The implementation must include leakage tests proving no same/future game can
contribute, historical parity tests when an upcoming null row is appended, and
coverage reporting by season and position. Do not use depth-chart hindsight or
choose a primary QB for the target week; the signal is deliberately team-level.

The cache report must also stratify the existing QB-only `qb_cpoe_l6` support
and treatment behavior by active status and feature presence. The generator
passes NaNs directly to TabPFN and performs no imputation, so this is a sparse-
support/proxy diagnostic only; it does not authorize filling, dropping or
broadcasting the existing field.

## Frozen cache arms

Both arms use the same immutable GPU image/code, inherited label and feature
law, warehouse snapshot, strictly-earlier-season TabPFN context, target seasons
2022--2025, position encoding, `tabpfn==2.2.1`, four estimators, seed 7,
context cap 28,000, target keys, quantiles, and research-only write path.

- Control: the inherited accepted TabPFN feature contract.
- Treatment: that exact ordered contract plus only `team_qb_cpoe_l6`.

No NGS time-to-throw field, interaction, second QB metric, hyperparameter,
context sampling, or model-version change is permitted in this arm.

## Staged decision

1. Mechanical validation must prove the point-in-time feature contract, same
   source/label law, exact target-key equality, unique keys, finite ordered
   quantiles, full 2022--2025 coverage, and changed predictions.
2. Reconstruct same-seed final-served worlds under the accepted common
   simulator law and 45/55 market blend. Independently fit each arm's exact
   walk-forward position-scale schedule using 2022 for 2023, 2022--2023 for
   2024, and 2022--2024 for 2025.
3. Primary gate: treatment aggregate active RB/WR/TE 30-point Brier on
   2023--2025 must be strictly lower than control. Position/season slices,
   CRPS, MAE, Brier20, quantile calibration, and clustered uncertainty are
   diagnostics rather than vetoes.
4. Only a passing gate licenses one separately frozen paired exact-80 test.
   The 240/230/220/210/200 first-nonzero weekly-maximum decision governs, with
   no mean-score veto.

Failure closes this exact broadcast historically. Do not change the window,
weight weeks equally instead of dropbacks, add another QB field, or tune on
known lineup outcomes after viewing a result.

## Production safety

The new SQL column and research cache remain inactive until every licensed gate
passes. Production continues to force the canonical cache, and any eventual
promotion requires a validated feature rebuild, cache promotion, policy
update, and deployment verification.
