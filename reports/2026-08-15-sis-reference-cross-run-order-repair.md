# SIS reference cross-run row-order repair

Date frozen: 2026-08-15 14:37 CDT

Original invalid run: `20260815-sis-receiver-copula-v1`

First grain-repair run: `20260815-sis-receiver-copula-v1-repair1`

## Newly discovered defect

The first grain-repair run passes every within-execution invariant, but it
does not satisfy the earlier frozen requirement to reproduce the original
frame, draw and score fingerprints. It is therefore preserved but remains
terminally invalid for unlocking calibration.

The cause is a reproducibility defect in the inherited G1 terminal loader.
Its accepted-panel BigQuery query had no `ORDER BY`; `_align_arm` then used
that undefined result order as both the output frame order and the player-world
row order. Two loads inside one execution usually inherit the same cached
order, so the within-execution repeat check passes, while independent Cloud Run
executions may return a different valid row permutation. The original hashes
therefore encoded an unspecified query order rather than only the terminal
data and simulation law.

No SIS treatment, calibration strength or candidate/lineup score was read in
this diagnosis. Comparing only the two preserved control scorebooks shows
exactly the same structure and all non-floating values. There are 159 floating
differences, all numerical-reduction noise with maximum absolute difference
`6.106226635438361e-16`. The original and repair1 both contain exactly 15,396
terminal rows, 7,848 score rows and 54 slates.

## Sole canonical repair

Before returning from the shared terminal loader, sort the frame by the total
player key `(season, week, gsis_id, position)` and apply the identical row
permutation to the player-world matrix. Reject duplicate keys, missing keys or
misaligned draw rows. No source, value, world, seed, model, blend, schedule,
usage law, score cell, treatment, grid, held-out gate or consequence changes.

The sole new create-only identity is
`20260815-sis-receiver-copula-v1-repair2-canonical`. It is valid only if:

1. an exact immutable descendant image passes the full suite;
2. the internal frame/draw/terminal/score repeat checks and the corrected
   15,396/7,848 grain checks all pass;
3. the emitted frame is explicitly identified as canonically player-key
   ordered;
4. the full new control scorebook is structurally identical to repair1, all
   non-floating values are exact, and every floating value is within absolute
   tolerance `1e-12`; and
5. the report still forbids retrospective exact-80 use.

The original and repair1 artifacts remain immutable and invalid under their
respective frozen contracts. Only a passing repair2 plus a strict cross-report
harvest may unlock the separately frozen 2022 calibration.
