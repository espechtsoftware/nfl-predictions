# R6-v1 disposition — non-executable before outcome access

**Date:** 2026-08-24
**Status:** DRAFT — awaiting Gate G0 terminal v12 lane identities
**Disposition class:** protocol/implementation non-result
**Realized-outcome status:** not accessed for R6 as of handoff commit
`1e8acca5b2732586a963a1b994e4a38af9c4de8a`; this must be reverified and
replaced with terminal evidence before this document becomes final
**Decision authority:** none

**Boundary-event note (2026-08-24 22:00 UTC):** while locating existing panel-
index code, a broad local text search emitted a truncated excerpt from the
pre-existing A7 Phase-S report, which contains older realized-score rows. The
search did not resolve or read the governed v12/R6 actual-score source, did not
grade any v12 arm or book, and was stopped without using the excerpt to change
the successor design. The terminal claim must therefore be the precise one:
the governed v12/R6 realized-outcome source remained unread—not the broader,
incorrect claim that no historical score text was visible anywhere in the
repository.

## Executive disposition

The frozen R6-v1 experiment in
`reports/2026-08-22-r6-set-level-matchup-retrieval-prereg.md` cannot be
executed as registered by its frozen vehicle,
`src/nfl_dfs/research/corpus_batch_retrieval_runner.py`. This is a
**non-result**, not evidence that matchup-informed admission succeeded or
failed. The incompatibility was identified before the governed R6 realized
outcome read, so no scientific verdict may be inferred from the unexecuted
comparison.

The legacy preregistration, runner, v6-v12 amendment chain, and accepted
artifacts remain immutable evidence. They must not be edited or relabeled to
make R6-v1 appear executable. A separately versioned R6-v2 protocol and
runner may use the accepted v12 population only after their complete books
and evidence are frozen while outcome-blind.

## Frozen intent

R6-v1 registered, for every accepted slate:

- seven retrieval laws;
- two admissions: the all-seven-arm union and matchup-top-200;
- an exact 80-lineup book for every selector/admission cell;
- same-law paired comparisons;
- one later governed read of realized DraftKings scores; and
- a primary comparison using `coverage-194-v1`.

The seven registered laws were:

1. `coverage-194-v1`;
2. `strict-200-coverage-v1`;
3. `tail-ladder-200-210-220-v1`;
4. `mean-score-v1`;
5. `expected-max-v1`;
6. `block-supported-tail-ladder-v1`; and
7. `regime-robust-ladder-v1`.

## Code-verified incompatibilities

### 1. Four of seven registered selectors are omitted

The frozen runner dispatches
`frozen_retrieval_strategies_v2(80)[4:]`. That slice runs only
`expected-max-v1`, `block-supported-tail-ladder-v1`, and
`regime-robust-ladder-v1`. In particular, the registered primary law,
`coverage-194-v1`, is not executed. A three-law output cannot satisfy the
registered 14-cell lattice.

### 2. Candidate identities are not held-out-safe

The runner removes R4 score columns from discovery, but constructs its union
without candidate-origin masks. A lineup discovered only while optimizing an
R4 world can therefore enter a book selected on R0-R3 scores. Slicing score
columns does not remove identity discovery leakage.

### 3. Exact books and marginal traces are not retained

The output stores book size, admission name, strategy hash, and aggregate
coverage summaries. It does not retain the exact selected lineup IDs,
selection ordinals, marginal objective trace, tie-break values, or complete
threshold/block contribution evidence required to freeze and independently
replay the registered books.

### 4. No durable R6-v1 publication/completion path exists

The frozen vehicle is a library function without a governed CLI, create-once
publisher, full task/batch completion receipt, or independent output replay
capable of proving that every registered cell existed before outcome access.
Aggregate in-memory output cannot establish the required freeze boundary.

### 5. Matchup completeness is not a trustworthy admission denominator

The legacy lineup matchup score treats absent annotations as an implicit
zero-like ordering outcome and does not bind a complete eligible-player
denominator per lineup. It can rank a sparsely annotated lineup ahead of a
broadly supported one without exposing the missingness distinction required
for interpretation.

## Amendment-chain continuity

This disposition preserves the preregistration's outcome-blind substrate
amendments rather than erasing them:

- v6 ended after a consumed task-0 producer failure;
- v7 was replaced before scores because its lane foundations pinned a
  superseded image;
- v8a produced no accepted variant result before its finalizer refused the
  new uniqueness-certificate shape, while v8b was unused;
- v9 was replaced after the Cloud Asset quota exposed the need for the
  policy-derived access fallback;
- v10 exposed verifier attempt-ledger and lane-positional source-selection
  defects, without an R6 realized read;
- v11 retained three accepted slates as diagnostic-only evidence after CBC
  exactness defects required a new science image; and
- v12a plus v12b form the intended panel substrate, subject to Gate G0's exact
  terminal census and combined read-only index.

The final version of this disposition must bind the exact v12a and v12b batch
manifest identities, terminal batch-acceptance identities, combined panel
index identity, accepted denominator, and missing-task list.

## Evidence classification

- No R6-v1 matchup result exists.
- No primary or secondary R6-v1 bar was evaluated.
- The direction is not rejected by this disposition.
- The legacy runner's own `exploratory-pre-comparison` and
  no-adoption/no-promotion labels remain in force.
- The accepted v12 generator results remain a valid fill-ablation substrate;
  this disposition concerns only the attempted R6-v1 retrieval evaluation.

## Licensed successor boundary

A fresh R6-v2 may proceed only if, before any v12 realized-outcome access, it:

1. imports the terminal v12 panel through one exact-read compatibility
   adapter;
2. reconstructs and verifies every retained arm score hash and selected book;
3. derives provenance from every arm/visit occurrence;
4. excludes held-out-only candidate identities and all held-out-derived tie
   inputs within each fold;
5. runs all seven registered laws under both primary admissions;
6. retains exact admitted/excluded candidate evidence, selected 80 IDs,
   rosters, objectives, marginal traces, and threshold/block contributions;
7. uses explicit missing-not-zero matchup coverage with a complete skill-
   player denominator and the frozen QB depth gate;
8. freezes score-blind size/composition-matched neutral controls before the
   outcome read;
9. creates one distinct all-five-block final-fit book per registered
   selector/admission/control for realized grading; and
10. publishes and independently replays every final-fit book before acquiring
    any historical-outcome lease.

R6-v2 is a preregistered retrospective evaluation, not fresh confirmation,
because the broader 2023-2025 historical program has influenced project
development. Nothing in R6-v1 or this disposition licenses a production
default change.

## Gate G0 completion fields

The finalizer must replace this section atomically with exact evidence:

- v12a batch manifest identity: **PENDING**
- v12a terminal batch acceptance identity: **PENDING**
- v12b batch manifest identity: **PENDING**
- v12b terminal batch acceptance identity: **PENDING**
- combined v12 panel index identity: **PENDING**
- accepted slate count and missing-task list: **PENDING**
- terminal proof that R6 realized outcomes remained unread: **PENDING**

Until all fields are populated and exact-read replay passes, this document is
a draft and carries no terminal Gate G0 authority.
