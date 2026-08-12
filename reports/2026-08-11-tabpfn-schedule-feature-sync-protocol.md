# TabPFN SCHED feature-sync protocol

Status: frozen before generating either cache or inspecting any SCHED-sync
TabPFN prediction, calibration metric, candidate, or lineup score.

## Question

The adopted LightGBM feature contract contains `net_rest_diff` and
`body_clock_hour`, but the TabPFN cache's tracked feature list predates that
adoption. Because TabPFN owns every covered player's final marginal, this
experiment asks whether adding that exact already-adopted pair to the TabPFN
input improves served player tails and, if so, the final 80-lineup weekly
maximum. It is not a feature sweep and it does not retest the component-path
SCHED result.

## Sequencing and baseline

This experiment may start only after the frozen TabPFN active-label sequence
reaches its terminal historical decision:

- If active-only labels pass both their final-served gate and their separately
  frozen exact-80 comparison, both SCHED arms use active-only context labels.
- Otherwise both SCHED arms use the current-label context law.

The branch is determined solely by the earlier active-label result. The two
SCHED arms must always share the same label law. This prevents the label repair
and feature-list sync from being combined in one treatment.

## Frozen cache arms

Both arms use the same immutable GPU image and code, current frozen warehouse
snapshot, strictly-earlier-season context, target seasons 2022--2025,
`tabpfn==2.2.1`, position encoding, four estimators, seed 7, context cap 28,000,
target keys, quantiles, and research-only write implementation.

- Control: the exact 33-column tracked feature list represented by commit
  `bff6f7d`.
- Treatment: those exact 33 columns in the same order followed only by
  `net_rest_diff` and `body_clock_hour`, matching `NUMERIC_FEATURES` exactly.

No candidate feature, interaction, hyperparameter, imputation change, context
resampling change, or model-version change is permitted. Each cache must be
written to a new licensed research table; production
`features.tabpfn_projections` must not be overwritten.

Mechanical identities fixed before cache generation: the write-once research
tables are `nfl_features.tabpfn_sched_control_v1` and
`nfl_features.tabpfn_sched_treatment_v1`; the durable run id is
`20260812-tabpfn-sched-v1-pit-clean`. The terminal active-label selection maps
`label_law=current` to all-prior non-null context and
`label_law=active-only` to strictly active context. Both SCHED arms must carry
the same mapped law in every report and table row. The effective control
matrix retains the existing generator's sorted 33-column order; treatment
appends `net_rest_diff`, then `body_clock_hour`, without reordering the shared
columns.

## Staged decision

1. Mechanical validation must prove same source/label law, exact target-key
   equality, exact feature contracts, unique keys, finite ordered quantiles,
   complete 2022--2025 coverage, and changed predictions.
2. Reconstruct same-seed final-served worlds under the then-accepted common
   simulator law and 45/55 market blend. Independently fit each arm's frozen
   walk-forward position-scale schedule: 2022 calibrates 2023, 2022--2023
   calibrate 2024, and 2022--2024 calibrate 2025.
3. Primary scientific gate: treatment aggregate active RB/WR/TE 30-point Brier
   on 2023--2025 must be strictly below control. All other marginal metrics,
   season/position slices, and clustered uncertainty are diagnostics.
4. Only a passing final-served gate licenses one separately frozen paired
   exact-80 comparison. The operator's 240/230/220/210/200 first-nonzero
   weekly-maximum decision governs, with no mean-score veto.

Failure closes this exact pair historically. Do not split the pair, reorder it,
add other features, alter TabPFN settings, or tune the calibration grid after
viewing a result. Any later single-feature question requires a new prospective
protocol.

## Production safety

Research cache selectors must be explicit, validated, and persisted in
experiment provenance. Production policy continues to force the canonical
cache until every licensed gate passes and a separate validated promotion and
deployment is complete.
