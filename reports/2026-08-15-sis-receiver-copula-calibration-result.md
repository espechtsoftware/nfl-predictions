# SIS receiver-copula calibration result

Date: 2026-08-15 16:08 CDT

Run: `20260815-sis-receiver-copula-v1-repair2-canonical`

Calibration stage: `calibration-geometry1`

## Disposition

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

## Consequence

- `heldout_evaluation_licensed=false`; do not launch the 2023--2025 held-out
  execution.
- `retrospective_exact80_licensed=false`; do not generate or score lineups.
- No production simulation, candidate or selector setting changes.
- Preserve the passing canonical reference and complete calibration grid for
  forensic use.
- Future SIS work must be a separately specified mechanism or prospective
  2026 shadow. It may not retroactively lower this gate or select a strength
  from these values.

Machine report SHA-256:
`c552694c4bbd5ac361d57ec6bf616b65f156b4068fedb874571e6a6b3abe6110`.

Manifest SHA-256:
`fbb4b81b05401e2df6c3a5433fbd43ed66cdfad607d198700563a4ef1dc9583f`.
