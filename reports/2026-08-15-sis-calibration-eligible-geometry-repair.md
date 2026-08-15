# SIS calibration eligible-group geometry repair

Date: 2026-08-15 15:28 CDT

Status: infrastructure/code repair frozen before any calibration grid or
selected strength was emitted

## Failure

The first calibration execution after the passing canonical reference,
`sis-receiver-copula-calibration-repair2-canonical-5jv5v`, exited before
scoring or transporting any calibration cell. The sole error was:

`ValueError: receiver-copula eligible group geometry changed`

No calibration report, grid, strength, score or disposition was emitted or
read. The passing reference and all frozen calibration choices remain intact.

## Root cause

`build_receiver_context` defines a supported group on rows with an allowed
position and `mean_projection >= 4.0`; its QB-count check therefore ignores a
low-projection backup quarterback. `apply_receiver_copula` regrouped the full
frame and counted every QB, including those below the same support floor. A
group could consequently be declared eligible under one row predicate and
rejected under another.

This is a predicate-plumbing defect, not evidence about the treatment.

## Sole repair

When applying the treatment, resolve the QB row with the exact support
predicate already used to create eligibility:

- `position == QB`; and
- `mean_projection >= 4.0`.

Do not change eligible WR rows, source context, route-mass threshold, strength
grid, scoring, tiebreaks, calibration season/weeks, control marginals or
held-out gate. Add a regression fixture containing one supported starter and
one sub-floor backup QB; context construction and application must agree and
preserve every player marginal. A group with multiple supported QBs remains
ineligible/fail-closed.

The failed execution receipt remains immutable. A retry must use a new stage
directory, new Cloud Run execution ID, exact descendant code SHA and validated
immutable image. Held-out evaluation remains locked until the retry's complete
seven-cell report is strictly harvested and hash-pinned.
