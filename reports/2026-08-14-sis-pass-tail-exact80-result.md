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

## Non-nested crossing breadth

The grid above is nested: one seed/slate can contribute at several lower
thresholds. A post-decision descriptive retrofit therefore reports both gross
crossings and distinct NFL slates; it does not change the frozen decision.

| threshold | improving seed/slates | worsening seed/slates | net | distinct improving slates | distinct worsening slates |
|---:|---:|---:|---:|---:|---:|
| 240 | 0 | 0 | 0 | 0 | 0 |
| 230 | 0 | 0 | 0 | 0 | 0 |
| 220 | 3 | 1 | +2 | 2 | 1 |
| 210 | 5 | 3 | +2 | 4 | 3 |
| 200 | 7 | 4 | +3 | 6 | 3 |
| 194 | 6 | 5 | +1 | 6 | 4 |
| 187 | 10 | 10 | 0 | 8 | 10 |

The deciding 220 gain is concentrated in two calendar slates. Treatment gains
R0 and R1 on `2023-W03` and R2 on `2024-W03`, while it loses R4 on
`2023-W03`. Across all thresholds, after counting a seed/slate only once,
there are 19 improving and 15 worsening seed/slate observations. Those span
14 distinct improving slates, 14 distinct worsening slates, and 23 distinct
changed slates in total. This is a real but modest-breadth tail result, not
eight independent gains implied by summing the nested deltas.

## Season diagnostics

- 2023: treatment improves 220/210/200/194/187 by `+1/+2/+3/+2/+2` and mean
  by `+0.9993`.
- 2024: treatment improves 220/210/200/194 by `+1/+1/+2/+3`, loses four at
  187, and lowers mean by `1.1898`.
- 2025: 220 is tied; treatment loses `1/2/4` at 210/200/194, gains two at 187,
  and lowers mean by `1.0724`.

These mixed season diagnostics do not override the previously amended
aggregate tail-first objective. They do establish that the gain is not uniform
and should remain visible in prospective monitoring. The 2026 finite-K shadow
will predeclare checkpoints after Weeks 4, 8, 13 and 18 and report the
treatment-control 220/210/200/194 crossings, distinct slates and mean weekly
maximum. In particular it will state whether 2025's negative below-220 pattern
persists; intermediate checkpoints cannot promote the treatment into the K=1
money policy.

## Disposition

Record `tabpfn_sis_pass_tail_treatment_v1` and its frozen schedules as the
selected **finite-K historical research baseline**. Do not refit its features
or schedules. This result licenses a later explicit live/UI integration
decision under the addendum, but it does not license silently combining the
cache/schedules with the distinct K=1 money-lineup policy; that transfer cell
was not tested here. The score-free selector-resampling diagnostic has no
adoption authority. The separate multi-seed candidate/world factorial has now
selected the `CBWU` generation/selection mechanism under its own protocol;
that generic mechanism verdict does not transfer the pass-tail cache or
schedules. Final production wiring must respect those boundaries and record
the exact resulting state before Week 1.
