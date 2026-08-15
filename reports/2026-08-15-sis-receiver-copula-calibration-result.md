# SIS receiver-copula calibration result

Date: 2026-08-15 16:08 CDT

Run: `20260815-sis-receiver-copula-v1-repair2-canonical`

Calibration stage: `calibration-geometry1`

## Disposition

**Procedurally closed: untestable under this calibration design. The mechanism
was not shown to be adverse; its disclosed non-decisional direction was
favorable and is preserved only as motivation for a separately designed
prospective protocol.**

The repaired execution `sis-receiver-copula-calibration-geometry1-fwvrp`
completed successfully in 8m13s and its strict checksum harvest passed. The
terminal scientific disposition is
`sis-receiver-copula-calibration-invalid-or-inconclusive`.

Every strength cell passed the finite, exact-marginal, unchanged-ineligible-row
and mean-drift invariants. The calibration population and strictly-prior
Fantasy Points/SIS context also passed their frozen identity checks. However,
the 2022 Weeks 5--18 calibration book did not support either registered G0
multiplicity cell (`multiplicity_ge2` and `multiplicity_ge3`). Consequently
all seven cells had `required_support=false`, the proper-score tiebreak fields
were unavailable, and the selector correctly returned no selected strength.

This result is not a treatment failure estimate and must not be repaired by
choosing the visually best row after seeing the grid. It means the frozen
calibration design cannot identify a licensed treatment from the available
2022 support.

This is a third result category: **untestable under this calibration design**.
It is neither a valid pass nor a tested-and-rejected treatment. The exact
historical protocol permits no scientific change after this result, so this
distinction does not reopen the run; it prevents a future session from
mistaking a support failure for evidence that the receiver-copula mechanism
was harmful.

## Non-decisional direction of the completed cells

The following G0 estimates are disclosed from the already-produced artifact.
They did not participate in a valid selection and cannot be used to choose a
strength, launch held-out evaluation or promote an arm. The realized 2022
comparators are constant across the grid:

- QB-WR `2.608`; WR-WR `1.265`;
- multiplicity >=2 `0.841`, >=3 `0.806`, and >=4 `1.856`; and
- QB-TE `3.658`, versus a simulated `2.472` at every strength because this
  WR-only treatment does not modify TE ranks.

| lambda | QB-WR simulated | WR-WR simulated | mult >=2 | mult >=3 | mult >=4 |
|---:|---:|---:|---:|---:|---:|
| 0.00 | 2.665 | 2.139 | 1.118 | 2.430 | 7.561 |
| 0.25 | 2.464 | 1.778 | 1.111 | 2.361 | 7.095 |
| 0.50 | 2.556 | 1.369 | 1.099 | 2.286 | 6.693 |
| 0.75 | 2.812 | 1.268 | 1.089 | 2.274 | 6.734 |
| 1.00 | 3.038 | 1.260 | 1.084 | 2.284 | 6.825 |
| 1.50 | 3.430 | 1.299 | 1.078 | 2.311 | 7.033 |
| 2.00 | 3.760 | 1.353 | 1.075 | 2.336 | 7.235 |

The G1 broad-relationship book has the same qualitative direction. In the
2022 calibration season, lambda 0 already fit QB-WR closely, so strengths
>=0.75 improve the WR-WR miss while worsening that season's QB-WR error.
Against the separate 2023--2025 reference shape, however, the useful direction
is clear: that control under-couples QB-WR (`2.418` simulated versus `3.323`
realized), over-couples WR-WR (`1.583` versus `1.137`) and over-produces high
multiplicity (>=4 `6.175` versus `2.333`). Strengths 0.75--1.00 move QB-WR up,
WR-WR down and every multiplicity estimate down simultaneously. They therefore
provide a **promising qualitative clue**, not a merits-based rejection. The
remaining multiplicity miss is still large, QB-TE is untouched, and no
held-out treatment value was queried, so the mechanism remains unadjudicated.

## Consequence

- `heldout_evaluation_licensed=false`; do not launch the 2023--2025 held-out
  execution.
- `retrospective_exact80_licensed=false`; do not generate or score lineups.
- No production simulation, candidate or selector setting changes.
- Preserve the passing canonical reference and complete calibration grid for
  forensic use.
- This exact historical protocol is closed to scientific repair. Future SIS
  work must be a separately specified mechanism or a prospectively frozen
  2026 shadow; it may use the qualitative direction above only as motivation,
  never retroactively lower this gate or select a strength from these values.
- Future protocols with cell-dependent eligibility must first run an
  outcome-blind support census that reads only eligibility/event counts, not
  gate metrics or treatment values.

Machine report SHA-256:
`c552694c4bbd5ac361d57ec6bf616b65f156b4068fedb874571e6a6b3abe6110`.

Manifest SHA-256:
`fbb4b81b05401e2df6c3a5433fbd43ed66cdfad607d198700563a4ef1dc9583f`.
