# Canonical TabPFN PIT-clean cache addendum

Frozen 2026-08-11 before generating the repaired canonical cache and before
any repaired lineup score was generated or queried.

## Purpose

The K3/K1 and direct-role production lineage uses TabPFN per-player marginals
by default. Rebuilding the common feature table and LightGBM models while
continuing to read the old `tabpfn_projections` table would splice repaired
component predictions with stale marginal predictions. The Tier-1 scope
therefore requires a fresh canonical cache before either control can run.

## Immutable identity and unchanged law

- destination: `nfl_features.tabpfn_projections_pit_v2`;
- write disposition: `WRITE_EMPTY`;
- targets: the existing six replay seasons 2019, 2021, 2022, 2023, 2024 and
  2025;
- context for target season S: every training row from seasons `< S` with a
  non-null DK label, including the existing inactive-zero rows;
- context cap 28,000, NumPy sampling seed 7, four TabPFN estimators with
  TabPFN 2.2.1 and the unchanged canonical `features.txt` contract;
- the existing 13 quantiles q01/q05/q10/q20/q30/q40/q50/q60/q70/q80/q90/
  q95/q99 plus mean; and
- no upcoming row, component mode, alternate season subset or append mode.

This is a repair-only regeneration of the production current-label law. The
separate active-only experiment retains its own v2 control/treatment tables
and target-season scope. No active-only conclusion is imported here.

## Required gate

Generation must record the immutable code SHA, feature-contract hash, complete
training-table schema hash/checksum/modified time, row/activity counts,
hyperparameters, target seasons, output row count and unique keys. Predictions
must be finite, quantiles ordered and keys unique. Both repaired K3/K1 controls
must explicitly set the same `TABPFN_MARGINAL_TABLE` to this table; silent
fallback to the old canonical table or empirical marginals invalidates the
panel.

The old `tabpfn_projections` table is neither overwritten nor promoted by this
test. Production may switch only after the repaired Tier-1 lineage, refitted
served-position calibration and complete deployment/fallback verification are
terminal.

## Execution and validation controls

`scripts/cloud_tabpfn_canonical_pit.sh` requires an immutable GPU image and
code SHA, proves that the write-once destination does not already exist,
records the frozen protocol hash and launches the sole registered execution.
`scripts/cloud_finish_tabpfn_canonical_pit.sh` harvests that execution only
after a clean Cloud Run completion. The independent validator then requires:

- the exact code, feature-contract, training-table schema, modification time,
  content checksum and active/inactive counts recorded by the generator;
- exact equality between every target key in the repaired training table and
  every cache key for the six frozen target seasons;
- finite means and quantiles, monotonically ordered quantiles, unique keys and
  the frozen hyperparameters/context law; and
- `WRITE_EMPTY` into exactly `tabpfn_projections_pit_v2`.

The validator reads no realized lineup score. Any source-table mutation after
generation invalidates the cache rather than accepting mixed lineage.
