# TabPFN active-label correction protocol

Status: frozen before generating a corrected TabPFN cache or evaluating its
predictions, final-served worlds, candidates, or lineup scores.

## Why this test exists

The historical player universe was expanded beginning in 2022 to retain
listed inactive players for replay scoring. Those rows have `was_active=false`
and a synthetic `y_dk_points=0`; they must not be treated as played outcomes
when fitting player-production models. The LightGBM component path already
enforces that rule through `featureset.active_training_rows`.

The production TabPFN generator does not. It currently trains on every row
with non-null `y_dk_points`. Warehouse counts confirm that this admits
6,202/6,041/6,130/6,021 inactive zero labels in 2022/2023/2024/2025, versus
7,044/7,043/7,002/6,824 active labels. The existing cache contains the
expanded 2022--2025 key universe and was last written before the active-row
training safeguard was added to the component path.

This protocol asks one causal implementation question: does applying the same
active-label rule to TabPFN improve the final distributions served for players
who actually played? It is not a feature sweep or a lineup-outcome tune.

## Frozen arms

Both arms must run from the same immutable GPU image, current warehouse
snapshot, feature list, season list, context sampler, TabPFN version, seed,
estimator count, target rows, and write path implementation.

- Control: the current generator law, training on all strictly earlier rows
  with non-null `y_dk_points`.
- Treatment: the identical law plus exactly
  `was_active IS TRUE` on training/context rows.

Target rows are not filtered by activity; each cache must contain the same
unique `(season, week, gsis_id)` keys so replay coverage cannot differ.
Evaluation later filters to accepted, active main-slate QB/RB/WR/TE rows.

The generator must emit a manifest containing the immutable image/code
identity, arm, exact feature contract, target seasons, context counts by
season, target counts by season, seed, estimators, context cap, output table,
row count, and key uniqueness. Research tables must be separate from
`features.tabpfn_projections`; this stage must not overwrite production.

## Frozen data generation

- Target seasons: 2022, 2023, 2024, 2025.
- Context: strictly earlier seasons only.
- Outcome: `y_dk_points`.
- Baseline features: exact tracked `scripts/tabpfn_gen/features.txt` plus the
  existing encoded position column; no `EXTRA_FEATURES`.
- Quantiles: 0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70, 0.80,
  0.90, 0.95, 0.99, plus the TabPFN mean.
- `tabpfn==2.2.1`, four estimators, seed 7, maximum context 28,000.
- The same deterministic sampled context indices must be used by both arms
  before the treatment's activity filter changes eligible row count. Each arm
  samples from its own frozen eligible population using the same seeded law;
  no retry with another seed or context cap is allowed.

## Frozen staged decision

No lineup score may be inspected during cache generation.

1. Mechanical cache validation must pass: exact target-key equality, unique
   keys, expected columns, finite ordered quantiles, complete 2022--2025
   coverage, exact arm manifests, and treatment contexts containing zero
   inactive labels.
2. The current fitted-K exact-80 test completes first. The accepted simulator
   law after that frozen decision becomes the common law for both TabPFN arms.
3. Reconstruct final-served control and treatment worlds with their respective
   caches, the same simulation seeds and market blend, and independently fit
   each arm's position scale schedule using only strictly earlier out-of-sample
   folds (2022 calibrates 2023; 2022--2023 calibrate 2024; and
   2022--2024 calibrate 2025).
4. Primary scientific gate: aggregate active RB/WR/TE 30-point Brier score on
   2023--2025 must be strictly lower for treatment. Mean score, MAE, CRPS,
   20-point Brier, q90/q95/q99 pinball/calibration, position slices, season
   slices, and paired team-week uncertainty are diagnostics, not vetoes.
   Individual-season declines do not veto an aggregate tail improvement.
5. Only a passing final-served gate licenses one paired exact-80 comparison
   under the then-accepted production candidate book. That comparison must be
   frozen separately before producing any corrected-cache lineup score. The
   operator's 240/230/220/210/200 first-nonzero weekly-maximum rule governs.

Failure at a stage closes this exact active-label arm historically. Do not
alter the activity definition, seasons, features, seed, estimator count,
context cap, position-factor grid, market weight, or primary metric after
viewing a result.

## Production safety

The research cache tables may not be selected by production implicitly.
Alternate-table access must use a validated research-only table identifier,
must be persisted in experiment provenance, and the adopted production policy
must explicitly overwrite it with the canonical default. No corrected cache
can replace `features.tabpfn_projections` until every licensed gate passes and
a separate code-reviewed promotion/deployment is validated.
