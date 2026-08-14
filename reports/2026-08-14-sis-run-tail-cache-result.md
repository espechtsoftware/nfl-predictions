# SIS RB opponent run-tail cache result

## Disposition

`tabpfn-sis-rb-runtail-caches-valid`

The frozen control and treatment Cloud Run executions completed successfully:

- control `tabpfn-sis-rb-runtail-v1-control-7p9f7` in 9m33s;
- treatment `tabpfn-sis-rb-runtail-v1-treatment-s6p4d` in 9m56s.

Both used exact source code
`23fdbba47590af3ba7594ae22bdbf2e764d86389` and immutable GPU image digest
`sha256:848a9951f8eae2daa580e5ca43aa8f431aee2677402373c2018553d448d27593`.
The immutable validation report is
`tabpfn-sis-rb-runtail-runs/20260814-tabpfn-sis-rb-runtail-v1/validation.json`
with SHA-256
`f834ee39d403a7566767a713a43ad09b26655565514ee779f604729b777c60ff`.

## What passed

- Both write-once caches contain exactly 52,307 unique player-week rows across
  2022--2025 with identical keys, folds, source identities, training snapshot,
  hyperparameters and active-only/base laws.
- Control reproduces `tabpfn_active_label_treatment_v2` exactly: maximum
  absolute prediction delta is `0.0` across the required prediction columns.
- Treatment differs only by appending
  `sis_rb_def_boom_rate_l4` and `sis_rb_def_bust_rate_l4`; predictions changed.
- Every prediction is finite, quantiles are ordered, source and row identities
  pass, and no PIT or schema invariant failed.
- Active-RB support is 87.93% in 2023, 88.02% in 2024 and 87.84% in 2025,
  above the frozen 80% floor in every evaluation season.

## Consequence

The cache prerequisite passes and licenses the already-frozen, score-free
final-served active-RB q95/q99 normalized-pinball comparison. It does not yet
license lineup generation or scoring. A lineup comparison becomes eligible
only if that next gate also passes.
