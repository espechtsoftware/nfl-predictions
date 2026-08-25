# R6-v1 disposition — non-executable before outcome access

**Date:** 2026-08-24
**Status:** FINAL — Gate G0 complete; R6-v1 remains non-executable
**Disposition class:** protocol/implementation non-result
**Realized-outcome status:** the governed v12/R6 realized-outcome source
remained unread through terminal Gate G0. The terminal panel publication and
G0 authority lock both record `uses_realized_outcomes=false`; this is the
qualified claim defined by the boundary-event note below
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

The terminal, exact-read-replayed Gate G0 evidence is:

- v12a batch manifest identity: URI
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12a/governance/batch-manifest.json`,
  generation `1787516651848534`, SHA-256
  `cdcdc77b66ad01e77e97419ba596cd87d65eba1f3b3b36313c6af89d388f9aa3`,
  68,958 bytes.
- v12a terminal batch acceptance identity: URI
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12a/governance/batch-acceptance.json`,
  generation `1787656756640443`, SHA-256
  `a0ed809dc6480c93c301e3022c4adcc173ef285b8673e76174cf81f43b5c4397`,
  1,316,197 bytes. It is complete and accepted for all 28 lane tasks.
- v12b batch manifest identity: URI
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12b/governance/batch-manifest.json`,
  generation `1787517978301938`, SHA-256
  `90d60d62e5045c1a5b82486d4ee2bddaa24200f8ee0ce4c26a3dea7a51d17b92`,
  64,834 bytes.
- v12b terminal batch acceptance identity: URI
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260823-corpus-parametric-production-batch-v12b/governance/batch-acceptance.json`,
  generation `1787663188263409`, SHA-256
  `9823eaa9a51062a6a437af22d1f6a5e0444f080191dd7ab6aad37b46f32f1e53`,
  1,222,287 bytes. It is complete and accepted for all 26 lane tasks.
- combined v12 panel index identity: URI
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/panels/20260823-foundry-production-v12/foundry-v12-combined-panel-index-v1.json`,
  generation `1787663639938214`, SHA-256
  `4d41acd9277e525cd8521071b62390281c442d6324db1e3f5812bf59920c16f9`,
  209,279 bytes. Its panel ID is
  `v12:ef445e2b31a7756609b458753dc064318b58ea2912e9277071c08fd0d07392e0`.
- accepted slate count: 54/54—v12a 28/28 plus v12b 26/26. Missing-task
  list: `[]`.
- outcome boundary: validate-only replay passed with exact input replay; the
  create-once publication receipt and frozen G0 authority lock both record
  `uses_realized_outcomes=false`, `historical_scoring_licensed=false`, and
  no analytical or decision authority. The terminal handoff records that the
  governed v12/R6 actual-score source remained unread and no v12/R6 grade was
  performed. This does not retract the older-score-text boundary event above
  and grants no R6-v2 freeze, scoring, promotion, or production authority.

These identities finalize only the Gate G0 substrate census. They do not
create an R6-v1 result or alter its non-executable disposition.
