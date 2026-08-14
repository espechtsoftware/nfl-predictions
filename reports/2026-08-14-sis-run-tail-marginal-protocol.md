# Adaptive SIS RB opponent run-tail marginal protocol

Status: frozen 2026-08-14 after the outcome-blind prerequisite audit and
before generating either cache or reading a new model/lineup outcome. This is
an explicitly adaptive retrospective arm. It is queued behind the terminal
TD-ledger branch and may not compete with that execution.

## Rationale and prior boundary

The prior SIS RB Points-Saved arm failed its score-free Brier-30 gate and its
protocol prohibited adding Boom%/Bust% after that result. This protocol does
not reinterpret that failure. A later pre-forensic review identified opponent
run-defense tail frequency as a different two-field mechanism, and the
outcome-blind audit in `2026-08-14-sis-run-tail-prerequisite-audit.md` found
86.79% exact-panel RB support plus low redundancy with the nearest existing
fantasy-points-allowed field. The new evidence therefore remains
`adaptive_retrospective=true`, never confirmatory.

SIS pass-defense Boom%/Bust% and pressure are already tested and selected under
the separate pass-tail arm. They are not repeated here.

## Only treatment difference

Inherit the accepted active-only TabPFN cache law exactly: shared-33 base
features, TabPFN 2.2.1, strictly-earlier-season context, 28,000-row cap, four
estimators, seed 7, identical folds/keys/quantiles, and no SCHED, team-QB,
pass-tail, route, or prior SIS RB feature. The control must reproduce
`tabpfn_active_label_treatment_v2` on every key and numeric prediction within
`1e-10`.

The treatment appends exactly two RB-only columns:

1. `sis_rb_def_boom_rate_l4`;
2. `sis_rb_def_bust_rate_l4`.

Every non-RB value is null. No Points Saved, YAC, EPA, positive rate, offense
tail field, hand coefficient, interaction, imputation, window, threshold,
hyperparameter, or sampling change is permitted.

## Point-in-time feature law

Use only write-once source `nfl_raw.sis_team_run_context_game`, source run
`sis-team-run-context-tranche-2-v1`. Pin its row count, schema, source-run
identity, full checksum and original/recovery state identities.

For target `(season, week, opponent)`, select the opponent's rows in the same
season. Reconstruct Boom/Bust event counts as rate times `rdef_attempts`; sum
each numerator and attempts across the last four completed rows after
`shift(1)`, requiring at least two prior games; divide by summed attempts.
Zero denominators remain null. Join only by season/target week/opponent and
expose only to RB. Every supported source week must be below target week.

Tests must prove target-week mutation invariance, unique source and output
keys, volume weighting, opponent direction, unchanged panel row count, null
non-RB values, no current/future/cross-season fallback, and rates in `[0,1]`.

## Mechanical and score-free gate

- Control table: `nfl_features.tabpfn_sis_rb_runtail_control_v1`.
- Treatment table: `nfl_features.tabpfn_sis_rb_runtail_treatment_v1`.
- Calibration fold: 2022; evaluation folds: 2023--2025.
- Quantiles: 0.01, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.60, 0.70,
  0.80, 0.90, 0.95, 0.99.
- New research tables use `WRITE_EMPTY`.

Mechanical validation requires exact source/law/key/hyperparameter equality,
ordered finite quantiles, exact feature contracts, changed treatment
predictions, exact control reproduction, at least 80% supported salary-listed
RB rows in each evaluation season, and strict PIT provenance. Failure stops
before scientific scoring.

Reconstruct each arm with the unchanged terminal simulator, finite Dirichlet
`K=28.154043586960896`, 10,000 worlds, seed 0, accepted position widening and
45/55 model/market blend. Fit each arm's final-served position scale only from
strictly earlier out-of-sample folds (2022 for 2023, 2022--2023 for 2024,
2022--2024 for 2025). Preserve every player mean within `1e-10`.

The sole primary population is active RBs in 2023--2025. The score-free gate
passes if and only if the equal-weight mean of q95 and q99 normalized pinball
loss is strictly lower for treatment than control and every mechanical/mean
invariant passes. Brier-20/25/30, CRPS, MAE, q90, season folds, support and
slate-cluster uncertainty are diagnostics without a season veto. The tail
pinball gate matches the already successful SIS pass-tail mechanism and avoids
using the earlier Points-Saved arm's central Brier-30 question for a tail-shape
feature family.

## Consequences

A pass licenses exactly one separately frozen paired exact-80 comparison under
the terminal weekly-maximum order `240,230,220,210,200,194,187`; first differing
count decides and mean weekly maximum breaks a complete threshold tie. It does
not license production, feature composition, K=1 transfer, refitting, or a new
window. A failure closes this exact run-tail block historically without a
lineup-score read. An invalid result may receive infrastructure-only repair but
no scientific change.

Regardless of result, retain the adaptive label and require a prospective 2026
shadow before production use. Record the terminal disposition before the final
forensic freeze.
