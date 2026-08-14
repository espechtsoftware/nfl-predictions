# SIS pass-tail five-seed exact-80 result

Date: 2026-08-14. Complete frozen report:
`reports/tabpfn-sis-pass-tail-runs/20260814-sis-pass-tail-exact80-v1/report.json`.
The first analyzer failed in a mechanical pandas BOOL comparison before
emitting a report. The guarded repair retry completed successfully; both
execution identities and the failure disposition are retained with the run.

## Decision

The mechanically valid tail-first decision selects **treatment** at the first
differing threshold, **220**. The treatment adds the three frozen SIS
pass-defense pass-tail fields to the active-only TabPFN marginal model and uses
the prospectively selected treatment position schedules. It inherits finite
`K=28.154043586960896` and the Phase S-selected ASOE allocation unchanged.

Aggregate selected weekly-maximum counts across the five seed books are:

| threshold | control | treatment | delta |
|---:|---:|---:|---:|
| 240 | 0 | 0 | 0 |
| 230 | 1 | 1 | 0 |
| 220 | 3 | 5 | +2 |
| 210 | 11 | 13 | +2 |
| 200 | 20 | 23 | +3 |
| 194 | 37 | 38 | +1 |
| 187 | 60 | 60 | 0 |

Mean weekly maximum changes from `173.8999` to `173.4789` (-0.4210). The
slate-clustered 95% interval for that mean delta is `[-1.5092, 0.7001]`. Mean
is diagnostic: the frozen operator-aligned rule compares the highest tail
threshold first, so the two additional >=220 seed-weeks decide the result.

## Season diagnostics

- 2023: treatment improves 220/210/200/194/187 by `+1/+2/+3/+2/+2` and mean
  by `+0.9993`.
- 2024: treatment improves 220/210/200/194 by `+1/+1/+2/+3`, loses four at
  187, and lowers mean by `1.1898`.
- 2025: 220 is tied; treatment loses `1/2/4` at 210/200/194, gains two at 187,
  and lowers mean by `1.0724`.

These mixed season diagnostics do not override the previously amended
aggregate tail-first objective. They do establish that the gain is not uniform
and should remain visible in prospective monitoring.

## Disposition

Adopt `tabpfn_sis_pass_tail_treatment_v1` and its frozen schedules as the
selected marginal state when the remaining artifact-only queue closes. Do not
refit its features or schedules. The score-free selector-resampling diagnostic
has no adoption authority; the separate frozen multi-seed candidate/world
factorial may still alter candidate/world selection. Final production wiring
must combine only mechanisms licensed by their existing protocols and record
the exact resulting state before Week 1.
