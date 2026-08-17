# ATLAS historical-score v4 hybrid protocol

Frozen: 2026-08-17, before any repair6 shard body, treatment effect or realized
ATLAS score was opened and while 52 repair5 primaries were still nonterminal.

Protocol ID: `20260817-atlas-historical-score-diagnostic-v4`.

This is an outcome-facing diagnostic, not a production promotion. It may begin
only after the repair6 transport has sealed the score-free disposition
`valid-complete-repair6-hybrid-population` for exactly 54 slates.

## Immutable source population

The scorer consumes one create-only hybrid-population receipt. For every
2023-2025 regular-season Week 1-18 cell, that receipt must bind exactly one
successful execution and immutable object generation, size and SHA-256:

- the repair5 object for every terminal-success repair5 cell; and
- the repair6 object for every failure classified under the frozen repair6
  identity-tiebreak extension.

It must also prove the Week 1 repair5/repair6 no-change canary byte-identical,
include the Week 7 defect canary as its accepted repair6 cell, bind the complete
repair5 terminal census and exact repair6 execution census, and contain no
extra, missing or duplicate cell. The scorer downloads each declared object at
its exact generation and rejects any byte/hash mismatch before parsing it.

Each shard must be a single mechanically valid score-free ATLAS slate with 200
global additions (40 per registered R0-R4 book), the exact native and treatment
candidate budgets, and exact-80 identities. The source-specific code/image may
differ only as already certified by repair6; no scorer-side reconstruction may
choose which implementation supplied a cell.

## Frozen comparison

For every slate, reconstruct the same five native 10,000-world books from the
same immutable score-artifact URIs and hashes used by ATLAS. Reproduce:

- P1: incumbent order-invariant native candidate union and exact-80 selector;
- P2: the same books with each seed's native 40-lineup boom book replaced by
  that seed's 40 ATLAS additions, followed by the same union and selector.

The reconstructed candidate counts, exact-80 indices and exact-80 identities
must equal the source shard before any score comparison is accepted. Actual
player fantasy points come only from the frozen historical player table. The
runner must repeat the existing 68,199-roster native actual-score parity check
at absolute tolerance `1e-9`. It may query no ownership, payout, contest rank
or realized leaderboard-selection field.

## Frozen result and diagnostic targets

Score the complete P1 and P2 candidate books and exact-80 books at thresholds
187, 194, 200, 210, 220, 230 and 240. Report weekly maxima, paired deltas,
season summaries and treatment-only threshold crossings. Separately report:

- the realized maximum among all 200 generated ATLAS additions;
- how many additions enter P2's candidate book and exact-80 book;
- their candidate and selected maxima and threshold counts; and
- whether a treatment-only winning candidate survives exact-80 selection.

The already implemented `aggregate_diagnostic` law is frozen unchanged. Its
descriptive signal is positive only if selected `>=200` has a net improvement
of at least two weeks, selected `>=210`, `>=220`, `>=230` and `>=240` each have
no net decline, and candidate `>=200` has no net decline. Regardless of that
label, retain and report all tail-first counts and maxima; the result remains a
diagnostic and cannot silently change production.

## Execution and outcome lease

Package the exact committed runner, source validator, finisher and protocol in
one fully tested immutable image. Run one Cloud Run task with 8 CPU, 32 GiB,
zero retries and an eight-hour timeout. The output URI is create-only. Acquire
the shared historical-outcome lease immediately before execution and release
it only after a terminal execution and strict immutable harvest. A failed or
partial run cannot be interpreted, retried or replaced without a prospective
amendment based only on mechanical evidence.
