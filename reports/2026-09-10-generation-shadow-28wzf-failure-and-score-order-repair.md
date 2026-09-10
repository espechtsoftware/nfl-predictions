# Generation-shadow `28wzf` failure and deterministic score-order repair

Date: 2026-09-10
Status: implementation repaired and validated; replacement image/run pending

## Provider-terminal finding

Cloud Run execution `generation-shadow-suite-28wzf`, UID
`edba950d-3629-47ae-8d9c-1762badda9fa`, failed terminally at
`2026-09-10T16:07:27.350800Z` with one failed task and zero retries. The
execution completed every treatment-arm candidate block, then stopped before
publishing a prelock manifest or terminal. It must not be collected, retried
into the same namespace, or treated as a completed experiment.

The terminal exception was
`ProspectiveGenerationRetrievalCrossingError: retrieval candidate score row
differs from common bank` in `_validate_base_scoring`.

## Root cause

The candidate producer creates each float32 score row by summing the nine
players in `Lineup.players` order. The crossing validator recomputed the same
row by iterating `Lineup.ids`, which is a `frozenset`. Hash-dependent summation
order can change a float32 result by one ULP even when the same nine source
rows are present. Exact array equality therefore rejected an authentic common
bank. The test fixture repeated the validator's unordered summation and hid
the defect.

## Repair

Both base-bank validation and independent-audit scoring now use the producer's
ordered `Lineup.players` sequence. Roster identity and uniqueness checks remain
separate and unchanged. The fixture now constructs candidate totals in that
same stable order, and a regression proves that the ordered score is exact,
the legacy unordered score differs, and the repaired validator accepts the
authentic batch.

Validation:

- `git diff --check` passes.
- The focused crossing suite passes 8/8.
- The generation suite, evaluation, crossing, live-multiseed, portfolio,
  boom-first, and deployment cohort passes 96/96.

## Operating disposition

This is a mechanics repair only. It does not change candidate membership,
selection policy, adopted scoring, paid-entry behavior, or experimental
authority. Build a new immutable image from the pushed repair commit, update
the dedicated unscheduled job, and launch one fresh zero-retry Week-1 suite.
Preserve `28wzf`, `j5qzl`, and `vx76b` as failed evidence.

