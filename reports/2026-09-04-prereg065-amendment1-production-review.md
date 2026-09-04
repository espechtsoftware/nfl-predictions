# Production review — PREREG-065 amendment 1

Date: 2026-09-04 UTC

Reviewed lab commit: `eb708717fb3f8508d603ac7d2ae6b05f94bf7def`

Outcome boundary: production did not run the efficacy reader, inspect a book,
or compute any score, proxy, oracle, or settlement value during this review.

## Disposition

**Conditional co-sign after one narrow validation correction.** The amendment's
scientific intent is accepted: allow a finite negative
`points_unallocated` value when the frozen runner encounters a designated
player whose aggregate removed value is non-positive, while retaining
nonnegative transferred value and the frozen conservation tolerance. The
runner, image, estimands, arms, endpoints, family level, and routing remain
unchanged.

The current implementation relaxes one rule beyond the amendment text. Before
the amendment, the reader required all three numeric receipt values to be
nonnegative. The text says only `points_unallocated` may become negative and
that every other receipt rule stands, but the amended comprehension removes
the nonnegative check from `points_zeroed` as well. As written, the reader
would accept a finite negative `points_zeroed` value whenever the other fields
satisfy the conservation equation. The mechanics gate still requires
`points_zeroed > 0`, so the two validators would also encode different ranges.

Required repair before production co-signs and before the first read:

1. Keep the amended finite checks for all three fields.
2. Require `points_zeroed >= 0` (or the stronger existing engaged-row
   equivalent) in the efficacy reader.
3. Require `points_transferred >= 0` as the amendment already does.
4. Permit `points_unallocated` to be negative.
5. Preserve the existing conservation tolerance and every other receipt rule.
6. Add a behavioral regression proving that negative unallocated is accepted,
   negative zeroed is rejected, negative transferred is rejected, and broken
   conservation is rejected. The current source-string test proves the edit is
   present but does not exercise the validator.

For precise disclosure, describe the corner as a **designated player's
aggregate removed value across its sampled-off worlds being non-positive**.
The frozen runner branches on `removed.sum() <= 0`; it does not independently
discard every negative per-world draw.

Once that bounded correction lands, production's co-sign is automatic subject
to the focused reader/gate/contract tests remaining green. No rerun, rebuild,
new arm, or scientific redesign is requested. The 54/54 clean cohort remains
valid and sealed.

## Checks performed

- Reviewed the complete two-commit diff from production launch binding
  `cb2d394433b45e004d28007f9f80363ec3b691c4` through lab Update 48.
- Confirmed the frozen runner and immutable image are unchanged.
- Confirmed the failure occurred inside receipt validation before result
  computation, as represented by the lab's pre-open record.
- Re-ran the amended focused suite from detached lab commit `eb708717`:
  **27/27 passed** across the PREREG-065 reader, mechanics gate, and experiment
  contract tests.
- Confirmed the mechanics gate retains positive `points_zeroed` and
  `points_transferred` requirements while allowing finite negative
  `points_unallocated`.

