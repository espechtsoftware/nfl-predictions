# Current-stack Route Share channel screen (I1)

**Frozen:** 2026-08-14 before the Phase S result was harvested and before any
I1 cache, score or lineup outcome existed.

This implements I1 from
`2026-08-13-experimental-design-arm-interactions-reconciliation.md`. It does
not reopen either historical Route experiment. Those experiments used an older
stack and different insertion points.

## Stage, channels and terminal context

- `C` — current control: active-only TabPFN labels, the accepted baseline
  feature contract, no Route feature.
- `M` — **player-marginal channel**: add exactly the four strictly-prior Route
  fields to the TabPFN cache and nowhere else.
- `R` — **rank/dependence channel**: add the same fields only to the component
  models, then restore every player's sorted final-served marginal exactly.

`M` estimates whether Route improves a served player's upper-tail marginal.
`R` estimates whether Route improves current-stack joint rank/dependence. The
two cells have different metrics and are not compared as one scalar effect.

The first implementation froze and prepared `C/M`. The following `R` gate was
frozen while Phase S was incomplete and before either new Route cache existed.
It may not substitute the old component arm or inherit the `M` result.

The common terminal context is:

- active-only TabPFN label law and accepted cache lineage v2;
- the historical accepted panel
  `20260811-pitclean-e80-k1-role12union-a12ab31` for keys and actuals;
- finite Dirichlet `K=28.154043586960896` selected by Phase R;
- the Phase S-selected ASOE state, applied identically to both cells;
- possession simulation, model ensemble 1, 10,000 worlds, seed 0;
- market blend weight 0.45; and
- arm-specific strictly walk-forward position-spread schedules on the fixed
  grid `0.750:0.005:1.500`.

Changing the active-label lineage, allocation law, ASOE state, market blend,
simulator, final-served schedule, Route source law or TabPFN version crosses the
transfer boundary and requires revalidation.

## Frozen source and cache generation

Both cache cells use one GPU image derived from immutable active-label base
image:

`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/tabpfn-active-label@sha256:d0830d9fb79643fd77faa0d8c80f4863c1769adb56d6d1782999d5aa0f40139b`

That preserves TabPFN 2.2.1, the baked weights and the exact numeric stack that
created the accepted v2 cache. The only image change is the I1 generator.

The frozen BigQuery source snapshot is
`nfl_features.player_week_training`:

- rows: `102927`;
- content checksum: `1904430067081090565`;
- last modified: `2026-08-12T04:06:47.502000+00:00`;
- baseline feature-file SHA-256:
  `52cc95c500bc3bd4223baacb29be73e3df4d637ce289b6431735cddd46195b83`;
- accepted active-label validation SHA-256:
  `e6b26ed7e899beb9fb5ef7bd622f644fdbefcbced121e5d15c5ff029fcf7de35`.

For both cells, targets are seasons 2022--2025, labels are active rows only,
training is strictly earlier seasons, context is capped at 28,000 with RNG 7,
and TabPFN uses four estimators and the fixed 13 quantiles q01--q99.

`M` adds exactly:

1. `fp_route_share_last`
2. `fp_route_share_l4`
3. `fp_route_share_jump`
4. `fp_route_cross_season`

The fields already encode strict-prior attachment. Source season/week and hash
remain provenance, not model features. Missing historical Route values stay
missing; no target-week value or imputation is introduced.

Write-once tables:

- `nfl_features.tabpfn_route_channel_control_v1`
- `nfl_features.tabpfn_route_channel_marginal_v1`

## Mechanical cache gate

The cache pair is invalid unless all of the following hold:

1. same immutable image/code/source snapshot/hyperparameters and target keys;
2. 52,307 unique rows per table over exactly 2022--2025;
3. active-only context in every fold;
4. `M - C` feature contract equals exactly the four registered Route fields;
5. finite ordered quantiles and non-identical treatment predictions;
6. `C` keys and every mean/quantile reproduce
   `tabpfn_active_label_treatment_v2` within `1e-10`; and
7. the accepted v2 cache source/feature identities match the frozen hashes.

Failure is mechanical and licenses no score read or follow-up.

## Frozen `M` score-free gate

After Phase S is mechanically harvested, apply its selected ASOE state as a
common law. Fit each cell's position-spread factors for target year `Y` using
only completed out-of-sample folds before `Y`: 2022 for 2023, 2022--2023 for
2024, and 2022--2024 for 2025.

Report for every evaluation season, position and aggregate:

- q90/q95/q99 pinball and exceedance/reliability;
- Brier at 20/25/30 points and reliability;
- CRPS and point MAE;
- paired whole-slate cluster intervals; and
- cache coverage, support and all fitted schedules.

The primary population is RB/WR/TE. `M` passes only if:

1. the equal-position, equal-q95/q99 treatment/control pinball ratio is
   strictly below 1;
2. at least two of RB/WR/TE have a mean q95/q99 ratio below 1; and
3. position scaling changes no player mean by more than `1e-10`.

This gate is deliberately identical in form to the already-frozen SIS
pass-tail score-free gate. Raw exceedance is diagnostic, not a discriminator.
A pass licenses the preregistered I2 five-seed exact-80 Route-marginal × ASOE
factorial. It does not itself adopt Route. A fail closes only the marginal
insertion point on this terminal stack.

## Frozen `R` rank/dependence gate

`R` uses the accepted active-label v2 marginal cache in both cells and the
accepted G0 walk-forward position schedule in both cells. The sole arm change
is adding the four registered Route fields through `EXTRA_FEATURES` while
training the component models. Finite K, the Phase S-selected ASOE state,
market blend, simulator, seeds and all marginal/position shaping are common.

After the market blend and common position schedule, every player's sorted
10,000-value served marginal in `R` must reproduce `C` within `1e-10`. This is
a mechanical gate: the arm is rank/dependence-only, not a second marginal
experiment.

Score both cells on the same 2023--2025 rows, q90 thresholds, realized flags,
walk-forward G1 archetype labels and pair book. Report complete G0 cells and
G1 broad relationships plus their clustered intervals. The five equally
weighted registered loss families are:

1. mean squared log simulated/realized gap over supported G0 multiplicity
   cells;
2. mean squared log gap over supported G0 teammate role-pair cells;
3. mean squared log gap over supported G1 primary broad relationships;
4. G1 overall joint-q90 Brier; and
5. G1 overall variogram score with exponent 0.5.

For every family, form `R / C`. `R` passes only if:

1. the equal-family mean ratio is strictly below 1;
2. at least three of five families improve;
3. the mean absolute QB-WR/QB-TE G1 broad log gap does not increase;
4. no supported primary G1 relationship's absolute log gap increases by more
   than `log(1.15)`; and
5. no primary relationship has both joint-q90 Brier and variogram worsen by
   more than 10%.

A pass licenses a separately frozen exact-80 Route-rank follow-up. It does not
adopt the arm. Failure closes only the component/rank insertion point.

## Score and sequencing firewall

- Cache generation and validation may not query lineup scores.
- The score-free evaluator may read player actuals only after Phase S has a
  complete mechanical report.
- No partial Phase S or I1 result may be read.
- `R` and the I2 exact-80 factorial remain separate experiments.
- The prior Route component, Route candidate-union and 2026 shadow results are
  disclosed context only and cannot populate a cell here.
