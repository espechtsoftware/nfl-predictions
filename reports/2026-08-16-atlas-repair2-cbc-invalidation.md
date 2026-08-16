# ATLAS repair2 CBC invalidation

Date: 2026-08-16
Run: `20260816-atlas-matched-diversity-mvp-v1-repair2`
Disposition: terminally invalid; no score-free effect and no historical score
is licensed from this execution grid.

## What happened

The frozen 54-slate grid initially lost 2024 Week 7 to
`pulp.apis.core.PulpSolverError` before a seed or slate completion marker. The
single exact retry permitted by the pre-launch retry amendment was running when
two additional effective cells failed:

- 2024 Week 15: `atlas-md-s2024-w15-r2-vnl5z`, terminal at
  `2026-08-16T13:40:38.549957Z`;
- 2024 Week 16: `atlas-md-s2024-w16-r2-dkvln`, terminal at
  `2026-08-16T13:40:36.499026Z`.

Both ended in the same packaged-CBC `PulpSolverError` from the stage-two ATLAS
interaction solve. Neither emitted a seed-completion marker or created its
slate object. At discovery the grid had only 26 non-metric seed markers and no
slate-completion marker or slate object. No candidate, selection, effect or
score result was opened.

The all-54-success rule therefore became impossible. The remaining 52
nonterminal effective executions were cancelled for compute safety. The final
effective terminal census is 52 `Cancelled` and two `NonZeroExitCode`; the
earlier superseded Week 7 failure remains separately preserved by the retry
receipt.

## Mechanical evidence

The invalidation receipt manifest is
`reports/atlas-matched-diversity-runs/20260816-atlas-matched-diversity-mvp-v1-repair2/invalidated-receipts.sha256`.
Its terminal snapshot SHA-256 is
`bb44ceec5e30a99cee2d7469f0c6a8db6af12d7e370c1353c7acba2734a1c7b6`.
The Week 15/16 execution receipt hashes are
`a0829d1e8fcd3fe999391c59fce85138ad1728894975e3d3b5465abf49fa8c04`
and
`e74b05fce8add90edb28bf87eced6b82828399ff13ae0b368dc6c11eb07b5b9b`;
their log hashes are
`cbce1b8eb090455893c4094c0d0937075390f1bf7407cfa8e5b24d00207e68d4`
and
`dfc00db5e177a545a0ebeee4c3851370134f5144a1d698da48f4ed9b96177f72`.

Cloud Monitoring is inconclusive about OOM. One-minute p99 memory utilization
for the failed Week 15 and Week 16 jobs peaked at approximately 0.660 and 0.740
of the 4 GiB allocation; their CPU utilization reached one full core. The
original Week 7 failure was near 0.240 memory utilization. Those sampled
percentiles can miss a sub-minute branch-and-bound allocation spike, and a
cgroup OOM killer can terminate the larger CBC child while leaving the Python
parent alive to report its nonzero exit. Repair2 was also the first
interaction-heavy ATLAS grid reduced from the 16--32 GiB used by completed
ATLAS jobs to 4 GiB. Memory pressure is therefore the leading unproven
hypothesis, not a ruled-out explanation. PuLP suppressed the native CBC stream
and did not expose the child return code, cgroup OOM counter or true high-water
mark, so the exact child-process cause is not observable from this run.

## Licensed next action

Before another effect-bearing grid, complete the already-launched score-free
native-log diagnostic on Weeks 15 and 16, then the separately frozen resource
diagnostic on Weeks 7, 15 and 16. The latter retains the same 4 GiB repair2
calculation while recording the CBC child return code/signal,
`memory.events`, `memory.peak` and `memory.max` around every child. Both discard
the returned slate payload, prohibit normal ATLAS output URIs and report only
mechanical, outcome-free evidence. The resource protocol is
`reports/2026-08-16-atlas-cbc-resource-diagnostic-protocol.md`.

Choose and freeze repair3 only after that evidence is terminal. Any repair3
must use new jobs/output identities and rerun the complete 54-slate grid; no
repair2 output may be reused. The scoring law remains frozen, but its upstream
receipt must later bind repair3, so every scorer image built for repair2 is
mechanically ineligible for the future grid.
