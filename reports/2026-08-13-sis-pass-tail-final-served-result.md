# SIS opponent pass-tail final-served result

Date: 2026-08-13  
Frozen protocol: `reports/2026-08-13-sis-pass-tail-marginal-protocol.md`  
Machine report: `reports/tabpfn-sis-pass-tail-runs/20260813-tabpfn-sis-pass-tail-final-served-v1/report.json`

## Disposition

**Pass.** The three-feature SIS opponent pass-tail marginal arm passed every
registered final-served calibration gate:

- Equal-position/equal-q95/q99 treatment-to-control pinball ratio:
  `0.9950319868` (must be below `1.0`).
- Improving positions: QB and TE (must be at least two of QB/WR/TE).
- Maximum absolute row-mean change: `7.11e-15` (must be at most `1e-10`).

Position mean q95/q99 ratios were QB `0.9859404`, TE `0.9991500`, and WR
`1.0000056`. The result is therefore driven primarily by QB tail calibration;
TE contributes a very small pass and WR is effectively neutral.

Diagnostics are directionally supportive but were not promotion gates. CRPS
improved from `2.7322923` to `2.7233727` (paired mean delta `-0.0089196`,
slate-cluster 95% interval `[-0.0117390, -0.0061002]`). Brier loss improved at
20 and 25 points and worsened slightly at 30; those intervals include zero.

## Licensed next action

This pass licenses **one** exact-80 lineup comparison that adds these three
strict-prior features to the accepted active-label cache law under the
allocation/dependence law selected by Phase S. It does not license direct
production adoption, a different feature bundle, threshold changes, or a
second exploratory lineup test. Launch only after Phase S is harvested so the
allocation law cannot be selected post hoc.

## Execution and transport notes

The original evaluator failed before scoring because its two cache tables were
missing from the fail-closed research allowlist. The repaired evaluator then
completed, but Cloud Logging truncated its single report line at 102,400
bytes. Final execution `tabpfn-sis-pass-tail-final-served-v1-c7dsz` used the
same frozen caches/panel/gate and emitted the report as verified compressed,
numbered chunks. These were infrastructure and result-transport repairs only;
the arm, simulations, calibration schedule, population, and decision rule did
not change.
