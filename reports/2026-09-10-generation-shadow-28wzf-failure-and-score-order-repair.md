# Generation-shadow `28wzf` failure and deterministic score-order repair

Date: 2026-09-10
Status: implementation repaired and validated; replacement run active

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
authority. Repair commit `ee87e7d39e68634cd50411f6c3763798ecc7c7fc`
produced passing Cloud Build `701ee02e-c63f-4a81-a978-7873ef39c2ca` and
digest-pinned image `sha256:56613633cb5e49067455b921b54c465c62e15b82e4b4f147cc45ca95724029bd`.
The existing dedicated job launched fresh zero-retry execution
`generation-shadow-suite-8mz64`, UID
`bcf7e194-bfb8-4373-96b0-c0dfc8f21cb6`. Monitor it to provider terminality
and collect only on success. Preserve `28wzf`, `j5qzl`, and `vx76b` as failed
evidence.
