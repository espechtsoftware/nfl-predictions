# ATLAS packaged-CBC native diagnostic result

Date harvested: 2026-08-16
Protocol: `20260816-atlas-cbc-native-diagnostic-v1`
Outcome access: none
Disposition: `native-evidence-inconclusive-abrupt-child-termination`

## Strict harvest

The strict finisher validated both immutable Cloud Run executions, their exact
image/source/protocol bindings, execution envelopes, receipts and firewall.
Completion receipt SHA-256:
`37fe3a1666d9804ecced01c75998d720dbf20dede288bf13287769fc3c79fd4c`.

| cell | execution | terminal result | solves |
|---|---|---:|---:|
| 2024 Week 15 | `atlas-cbc-diag-2024-w15-v1-qdssb` | R0 complete | 144 |
| 2024 Week 16 | `atlas-cbc-diag-2024-w16-v1-89fq4` | CBC failure | 127 |

Week 15 completed at `2026-08-16T16:08:39.769500Z`. Week 16 failed with
`NonZeroExitCode` at `2026-08-16T14:58:05.280827Z`.

## Native evidence

Week 16's retained MPS is nonempty (3,059,531 bytes; SHA-256
`c409568396bcda21379830a418fb464c130c919fd09918a8d0739f88d7a3546f`).
CBC reports that it read the model with zero errors: 9,277 rows, 3,401 columns
and 45,448 elements. Presolve and branch-and-bound then began normally.

The retained native log is exactly 4,096 bytes (SHA-256
`109b9b9c2dad02d32498b1e2eb186e4e056b15047e4bf7dd106685c0152fca88`)
and ends mid-line during a feasibility-pump pass. It contains no parser error,
infeasibility conclusion, numerical warning, normal CBC termination or final
solution record. That is evidence of abrupt child termination after a valid
model load, not evidence of a deterministic malformed-model/parser defect.

## Interpretation

The frozen native protocol specified branches for two successes, an identified
deterministic solver defect, or inconsistent/missing evidence. The observed
mixed success/failure pair does not meet either positive branch, so this result
is conservatively `inconclusive` for causal classification.

It nevertheless establishes two useful facts without post-hoc rule changes:

1. The unchanged old-binary Week 15 R0 can complete in isolation at 4 GiB, so
   repair2's Week 15 failure was not inevitable for that fixed model.
2. Week 16 dies abruptly during active branch-and-bound after a clean parse,
   which is compatible with load-sensitive resource pressure but does not prove
   OOM because this first diagnostic did not capture a return signal or cgroup
   counters.

The independent three-cell cgroup diagnostic remains authoritative for the
resource decision. No repair3 grid, ATLAS effect, score run or production change
is licensed by this native result alone.

