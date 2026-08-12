# TabPFN active-label final-served result

## Superseded pending PIT-clean revalidation

After this immutable run completed—and before any licensed exact-80 lineup
outcome was queried—the expanded source-recomputation audit found two common
historical feature defects: an all-history positional prior in the red-zone
smoothers and non-deduplicated injury revisions without a common-lock cutoff.
Both control and treatment used that contaminated common history. The result
below remains the accurate verdict for its named inputs, but it no longer
licenses an exact-80 launch or production change.

The only permitted continuation is to rebuild features/models, regenerate both
caches under the same respective label definitions and all other frozen laws,
and repeat this identical score-free gate with new immutable cache ids. No
lineup scores have been inspected, and the threshold, schedules, training-label
definitions and production-multinomial law may not change.

For its now-superseded inputs, the frozen final-served gate **passed**, but by a
very small aggregate 30-point Brier improvement. It originally licensed one
separately frozen paired exact-80 lineup comparison; the PIT finding above
blocks that license. It does not promote the active-only cache or change
production.

## Immutable execution

- Run: `20260811-tabpfn-active-label-final-served-v1`
- Cloud Run execution: `tabpfn-active-label-final-served-h5jpq`
- Image:
  `sha256:ce28df5bccce1a0be8966f5d86b2c53709db4d9dc83d8b1f8050043a93af6762`
- Common simulator law: production multinomial; blank `GAME_SIM_USAGE` and
  blank `DIRICHLET_K`, following the frozen fitted-K rejection
- Evaluation: 13,876 active RB/WR/TE rows, 54 slates, 2023--2025, including
  211 realized 30-point events
- Cache rows: 52,307 identical target keys in each arm

The manifest, raw log and complete machine report are under
`reports/tabpfn-active-label-runs/20260811-tabpfn-active-label-final-served-v1/`.

## Frozen gate

| aggregate metric | current-label control | active-only treatment | treatment - control |
|---|---:|---:|---:|
| 30-point Brier (primary) | 0.014021024 | 0.014010786 | **-0.000010238** |
| 20-point Brier | 0.049395663 | 0.049418692 | +0.000023030 |
| CRPS | 2.625894 | 2.597601 | -0.028293 |
| point MAE | 3.630271 | 3.637611 | +0.007340 |

The primary aggregate 30-point Brier is strictly lower and maximum
mean-preservation drift is `7.11e-15` in both arms, below the frozen `1e-10`
limit. Machine disposition is
`tabpfn-active-label-final-served-passes`.

The paired team-week clustered 95% interval for the 30-point Brier delta is
`[-0.000048884, 0.000028408]`; the observed advantage is therefore small and
uncertain. This interval was diagnostic, not a frozen veto. CRPS and all three
q90/q95/q99 pinball losses improved, while 20-point Brier and point MAE
worsened slightly.

Season 30-point Brier moved in the wrong direction in 2023 and 2024 and
improved in 2025:

| season | control | treatment | treatment - control |
|---|---:|---:|---:|
| 2023 | 0.014606038 | 0.014618244 | +0.000012206 |
| 2024 | 0.013027010 | 0.013043850 | +0.000016840 |
| 2025 | 0.014419553 | 0.014359646 | -0.000059906 |

Those season diagnostics do not override the preregistered aggregate gate.
They do make it especially important not to interpret this stage as evidence
of a durable lineup-score improvement.

## Original decision and repaired next gate

The original decision was to freeze one exact-80 control/treatment protocol
before generating or inspecting any active-label lineup outcome. Both arms
must still use the same production
multinomial usage law, exact upstream snapshots, seeds, candidate and selector
settings, market blend, and historical splice. They may differ only in the
validated TabPFN cache and their independently fitted walk-forward position
factor schedules. The operator's 240/230/220/210/200 first-nonzero weekly-
maximum rule decides that comparison.

The repaired next gate is the identical score-free final-served comparison on
PIT-clean v2 caches. Exact-80 remains blocked unless that gate passes and a
tracked mechanical addendum replaces only the prerequisite cache/report ids
and resulting independently fitted schedules.

Only a passing exact-80 comparison may promote active-only TabPFN training or
let the subsequent SCHED feature-sync arm inherit it. A reject/neutral result
keeps current-label TabPFN as the common control and closes this historical
active-label correction.
