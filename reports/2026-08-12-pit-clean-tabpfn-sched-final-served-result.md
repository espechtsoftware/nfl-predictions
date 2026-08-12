# PIT-clean TabPFN SCHED final-served result

## Decision

The frozen final-served prerequisite **fails**, so the SCHED treatment is
closed without any score-bearing exact-80 lineup replay. The terminal lineage
retains the incumbent 33-feature active-only TabPFN cache
`tabpfn_active_label_treatment_v2`.

The SCHED treatment appended only `net_rest_diff` and `body_clock_hour` to the
shared 33-feature contract. Its aggregate calibrated 30-point Brier was
slightly worse:

| Metric | Control | SCHED treatment | Treatment - control |
|---|---:|---:|---:|
| 30-point Brier (primary) | 0.0140065605 | 0.0140111906 | +0.0000046301 |
| 20-point Brier | 0.0494353120 | 0.0494374614 | +0.0000021494 |
| CRPS | 2.6041234883 | 2.6026754059 | -0.0014480825 |
| Point MAE | 3.6328205058 | 3.6292280363 | -0.0035924694 |

Lower is better for every metric. CRPS and point MAE improved slightly, but
the frozen prerequisite required the aggregate 30-point Brier to improve
strictly. It did not. Its slate-clustered 95% interval for the 30-point loss
difference was `[-0.0000066048, 0.0000158650]`, also consistent with a nearly
neutral arm rather than a dependable tail improvement.

By evaluation season, 30-point Brier improved minutely in 2023
(`0.0146108827 -> 0.0146069666`) and worsened in both 2024
(`0.0130305180 -> 0.0130320809`) and 2025
(`0.0143676624 -> 0.0143839902`). All cache, point-in-time, coverage and mean
invariants passed; maximum mean drift was `7.11e-15` in each arm. This is a
valid negative model result, not an execution or data-quality failure.

## Durable evidence

- Cloud Run execution: `tabpfn-sched-final-served-v1-fn9bv`
- Frozen source code: `23da1dd`
- Immutable audit image: `sha256:aec3c368dd493b166f99b444f06dc87b892d2220e4b0e544aa7314b9f03bd9a6`
- Machine report:
  `reports/tabpfn-sched-runs/20260812-tabpfn-sched-final-served-v1-pit-clean/report.json`
- Terminal selection:
  `reports/tabpfn-sched-runs/20260812-tabpfn-sched-exact80-v1-pit-clean/selected_sched.txt`

The predesignated fallback selected `sched_selected=false`,
`feature_contract=shared33`, `label_law=active-only`, fitted
`K=28.154043586960896`, and the existing role-union evaluation panel. The
next independent scoring branch is the amended team-passing-efficiency bundle;
it must inherit this no-SCHED terminal context and use only the already-built
post-review team-passing images recorded in `HANDOFF.md`.
