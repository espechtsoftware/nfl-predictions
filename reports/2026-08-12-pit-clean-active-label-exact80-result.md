# PIT-clean active-label exact-80 result

The repaired comparison is valid and selects active-only TabPFN training
labels for the downstream SCHED and team-passing branches.

## Decision

Across the unchanged 107-slate book, selected weekly maxima changed as
follows:

| Threshold | Current labels | Active-only labels | Delta |
|---:|---:|---:|---:|
| 240 | 2 | 2 | 0 |
| 230 | 2 | 2 | 0 |
| 220 | 2 | 2 | 0 |
| 210 | 4 | 6 | +2 |
| 200 | 12 | 14 | +2 |
| 194 | 22 | 23 | +1 |
| 187 | 33 | 35 | +2 |

The first nonzero difference in the frozen order
`240,230,220,210,200,194,187` is therefore the two-week gain at 210. That
selects treatment without consulting lower thresholds or mean as vetoes.
Mean weekly maximum is diagnostic only and also improves
`176.3566355 -> 176.8691589` (+0.5125).

## Validity and provenance

- All six season executions and both independent exact-80 acceptance checks
  completed successfully.
- Repaired comparator execution:
  `compare-tabpfn-active-label-exact80-v2-r1-brmrp`.
- The comparator found 29,605 equal player keys per arm, zero missing or
  materially mismatched invariant rows, maximum invariant drift
  `3.5527136788e-15`, identical actuals and common levers, and material
  candidate changes.
- The treatment promotion acceptance execution
  `accept-replay-panel-rbjxg` passed.
- The selected law is `label_law=active-only`, cache table
  `tabpfn_active_label_treatment_v2`, and selected evaluation panel
  `20260812-pitclean-e80-selected-tabpfn-active-v2`.
- Full-test Cloud Build `141d2c9f-908f-4de2-a363-982d7a734490` passed 991
  tests with two expected skips and produced immutable audit digest
  `sha256:43160f9416035183794477c6003177de2e948ebc0d0597f35a28180d400a1d9b`.

The original invalid comparator and observer deviation remain disclosed in
`2026-08-12-active-label-comparator-invariant-repair.md`. That mechanical
repair changed no arm, lineup, score, threshold, or decision rule.
