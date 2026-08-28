# R6 current-bank crossed-screen pre-output contract

**Date:** 2026-08-27

**Contract ID:** `20260827-r6-current-bank-crossed-screen-v1`

**Status:** frozen design candidate; it becomes execution authority only from
its first clean tracked commit. No result may be inspected before that commit.

**Evidence class:** outcome-blind simulated analysis only.

**Promotion, decision, deployment, graph-mutation, and historical-score
authority:** none.

## Purpose

This contract is the accelerated Stage 1 promised by
`2026-08-27-foundry-crossed-arm-retest-and-simulated-scoring-plan.md`. It asks
which of the seven already-generated R6 construction profiles and eight
already-frozen retrieval laws work best together under the existing simulated
belief law.

It deliberately starts from the sealed current bank. It does not wait for the
fixed-G0 catalog recovery, the new outer-bound candidate authority, matchup
source-v2, or a newly generated independent bank because it consumes none of
them. Those products gate the next generated bank, not this read-only replay.

This contract prevents three shortcuts:

1. a larger corpus cannot win a retrieval comparison merely because it has
   more candidates;
2. the finalist cannot be chosen by a person after viewing the table; and
3. simulated findings cannot be described as historical score improvement or
   prospective promotion evidence.

## Immutable current-bank authority

The sole panel root is:

| Field | Exact value |
|---|---|
| URI | `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-freezes/20260826-foundry-v12-r6-full-union-freeze-v1/panel-freeze.json` |
| generation | `1787756181440564` |
| bytes | `89879` |
| object SHA-256 | `57844386a3da86ddf05f8b3e6b19ae19c7327afcfc1057647b210e58caec2467` |
| panel self-hash | `26d27abf5074ed20cbd401e1a93332b34449eb3ec9b3c7175330c1de10736f2d` |
| accepted slates | 54 |
| rank-80 books | 2,592 |
| frozen prefixes | 7,776 |
| simulated blocks | ordered `R0,R1,R2,R3,R4`, 10,000 worlds each |

The implementation uses one exact **direct task-surface projection** route; it
does not invoke the old seven-arm reconstruction route. A non-selector
projection process exact-generation reopens and validates the panel root,
execution manifest, fixed combined panel index, all 54 leaves, and all 54 task
results through the existing 111-object structural allowlist. It publishes
exactly 54 self-hashed slate projection bundles in source ordinal order. Each
bundle contains exactly five canonical fold projections, ordered `R0` through
`R4`; a one-fold object is not a slate projection authority. For each fold the
bundle emits only:

- source task-result identity and task-result payload hash;
- exact later-source and `R0`-`R4` world-artifact identities;
- exact `fit_candidate_view_sha256` and `selection_provenance_sha256`;
- ordered fold-stripped candidate IDs, rosters, training origin blocks,
  training source-arm sets, per-training-block occurrence counts/source arms,
  and total training occurrence count;
- candidate lineup-order, roster, and complete candidate-row hashes;
- ordered training blocks and the canonical world-column hash: canonical-JSON
  SHA-256 of the ordered 40,000 rows
  `[{"block": training_block, "index": 0..9999}, ...]`; and
- each sealed book's common expected `training_score_matrix_sha256`.

Every training score row is hashed by the exact byte law
`canonical_json({"dtype":"float64-le","shape":[40000]}) || NUL ||
contiguous-little-endian-float64-bytes`. The full ledger is the ordered array
of `{lineup_id,score_row_sha256}` rows plus its lineup, row-array, shape, and
full-matrix hashes. A sampled cell does not attest a second arbitrary matrix:
its ordered row ledger is derived as the exact sampled-ID subset of that full
ledger and binds the full ledger and full-matrix hashes.

The projection builder executes no selector and copies no existing book
metric, held-out metric, marginal trace, selected index, or selected roster.
Its audited dependency closure may include the sealed structural validator and
its transitive imports, but its own callable graph exposes no selector
dispatcher or book builder. Its output schema rejects every other task-result
field. It does not read a carrier, task-acceptance receipt, or any of the seven
arm-result bodies.

A selector worker exact-reopens that projection bundle and the later-source
player catalog, reads only the four named training world artifacts, aligns player IDs,
cross-scores the projected rosters, and requires lineup order, shape, world
columns, and the recomputed training-matrix hash to equal the sealed expected
values before selecting. This is enforced by exactly **270 logical fold
selections per phase**: one `(source_ordinal,fold_ordinal)` selection for each
of 54 slates times five folds. Each logical fold selection is an ordered
two-process `artifact-broker -> matrix-selector` chain, hence exactly **540 OS
selector processes per phase**. The broker alone owns the exact allowlist of
the bundle, later-source catalog, and four training artifacts; the fifth
artifact is not addressable and no storage/network capability reaches the
matrix-selector child. A no-world-artifact per-slate assembler combines the
five child receipts without running a selector. Its receipt embeds and hashes
five distinct child-execution evidence objects, their exact broker/matrix
commands and entrypoint hashes, four-read ledgers, process-budget identities,
fit counts, response/output byte ceilings, and immutable pre-design launch
authorization. Only after that receipt exists may a separate evaluation
process read the five fold-specific held-out artifacts and score the frozen
books. This is a process-level information boundary, not an assertion that
the full sealed task result lacks old held-out descriptive metrics.

For every scientific or task input, an identity derived from a mutable object
listing or a current-generation lookup is forbidden. Every such URI has exactly
one positive decimal generation; the same URI cannot appear with two
generations or inconsistent hashes. Exact role-derived read/write/fit budgets
are compiled from a validated bundle and the validated 275-object topology
before each process starts. Endpoint, environment, Git-ref, and input
current-generation redirection are false, not caller options. The child run
prefix is nonempty, ordinal order is explicit rather than URI-lexical, and
writes are create-once.

There is one narrow, pre-authorized host-finalization exception. After Cloud
Run reports every task terminal-success, the host finalizer may perform exactly
one current-generation metadata lookup for each ordered, deterministic,
create-once task-terminal-evidence URI declared by that exact task manifest. It
must immediately pin the returned positive generation, hash and read only that
generation, and validate the terminal body against the manifest and execution.
This exception permits no prefix or bucket listing, log read, scientific-output
resolution, alternate URI, second lookup, or unpinned body read. The pre-design
host observation budget, manifest URI ledger, execution observation source,
observed execution authority, and layer receipt all bind the exact count, URI
ledger hash, method, and false listing/log/scientific-resolution flags. The
layer receipt therefore records that current-generation resolution occurred in
this host-only scope; preparation receipts remain false because they consume
only already generation-pinned identities.

The bootstrap manifest freezes the exact topology identity, code commit,
image digest, ordered process chains, and the logical-invocation/OS-process
inventory for projection, selection, evaluation, nomination, aggregate,
finalist, and root publishers. Its `run_identity` has one precise acyclic
meaning: it is the immutable **pre-design run-authorization and launch-intent
token**. Every selector receipt, evaluator/publisher budget, and runtime
observation must use that exact identity; an arbitrary other immutable object
is rejected. The later design proves which topology and bootstrap manifest
selected that authorization. This token is not a claim that a cloud execution
occurred. A later controller request and terminal execution receipt must bind
the actual design generation, request manifest, image, job, execution, and
task metadata before execution evidence is complete.

The implementation must reject any URI or field that points to a realized
grade, outcome snapshot, outcome source, query evidence, historical lease,
attribution product, winner registry, no-rescore funnel, contest result, or
graph. Those products are neither necessary nor permitted inputs.

## Frozen construction-profile registry

The parameter registry SHA-256 is
`5de89cacdf6f836f7161b79ac889d80dafbc8a5040cbf18e06ba5cc14d9464fa`.
Order and identity are exact:

| ordinal | profile ID | profile SHA-256 | changed incumbent setting |
|---:|---|---|---|
| 0 | `incumbent` | `9083a369a9a82a462b02cba8da508654c2ecb2b36712fba0c19166e8f514dc3e` | none |
| 1 | `remove-salary-floor` | `a29865440e6f524578c4038075a4c9fe82ec8409d34ec91abc6ca2a10bbd5229` | minimum salary 49,000 to 0 |
| 2 | `remove-qb-stack` | `146e53ad0352eb3f491149a623da9803decf3bcad758ac83b4ff42d91a151fcb` | QB partners 2 to 0 |
| 3 | `remove-bring-back` | `fe5d196e362a097f21ec1875e749ec06d992b75b1f39785e1ec82beedcaabbd5` | bring-back 1 to 0 |
| 4 | `allow-rb-vs-dst` | `494378dd052610f4f4259c457368b3391599d9bf08d1f36cc60a724e00f73788` | RB-vs-DST prohibition removed |
| 5 | `allow-two-rb` | `286873ae9139d449e43d9212805f41fc520d645d8f3ec20adcb86201e808ed46` | same-team RB prohibition removed |
| 6 | `remove-all-five-shared-constraints` | `c68042831f7fe21cc0bd61c1ef59d56c84c6632fb016891766d1f131d5de8840` | all five strategic settings relaxed |

Only these seven profiles exist in this bank. Proposed pair-relaxed `F7`,
game-cap `F8`, single-partner `F9`, and overstack `F10` profiles are excluded.
They require new candidate generation and may not be inferred, filtered, or
backfilled from this union.

## Frozen selector registry

The selector registry SHA-256 is
`15bafff2d7b973118565191846474e479fe76ee50053e492b66e7bcb0c7c25ba`.
Order and identity are exact:

| ordinal | selector ID | selector SHA-256 |
|---:|---|---|
| 0 | `coverage-194-v1` | `1e1e6a11149ca1c8c9babd183b85adb2ce27d0f976ca863b43768aa3dab0433f` |
| 1 | `strict-200-coverage-v1` | `9689bb11de4616e4a6295ae0a5b0ec30aa174097f1965867fdc08d7b2e7d02de` |
| 2 | `tail-ladder-200-210-220-v1` | `5561d663cdc2ec8f928ddf5a44889f16e3c23cdd264f4c8fef7925547aa527ea` |
| 3 | `mean-score-v1` | `5c880aeca7c8ec3386a9d44b111937fada857f569cb324dd2163987b333654c6` |
| 4 | `expected-max-v1` | `ad94b80a0ea61d1c58f64f825f00f0d0fea47f36158a239c29382836ff2cb780` |
| 5 | `block-supported-tail-ladder-v1` | `1ae24780c211a329e8a9867e5dec39630a7efcc640deba9e05561f6a8c98668b` |
| 6 | `regime-robust-ladder-v1` | `125610a3fda4c230bacd44f1778e43fe03905a504d55ec6fe4c424c0cbbd0e7b` |
| 7 | `strict-230-coverage-v1` | `6b1f2b3078f6cb98f8f7d74b04e18ccf6e84477de6b4c3df4cd1912d1e0260e3` |

No gamma, overlap-cap, or evil-twin selector is admitted to this first
screen. Such challengers remain desirable, but each needs a separately
committed exact algorithm, tie law, executable fingerprint, and challenger
registry entry before its first output. Omitting an undefined challenger is
not evidence against it.

## Fold law and leakage boundary

For each slate, rotate each block through the held-out role exactly once:

| fit scope | training blocks | evaluation block |
|---|---|---|
| `holdout-R0` | `R1,R2,R3,R4` | `R0` |
| `holdout-R1` | `R0,R2,R3,R4` | `R1` |
| `holdout-R2` | `R0,R1,R3,R4` | `R2` |
| `holdout-R3` | `R0,R1,R2,R4` | `R3` |
| `holdout-R4` | `R0,R1,R2,R3` | `R4` |

Candidate eligibility, profile membership, admission, selector fitting, ties,
and subsampling use the narrow projection and four training blocks only. The
selector process cannot address the held-out block. The evaluation process
cannot start without exact-reopening a selector-produced immutable book
receipt. V1 performs no all-block final fit; one requires a separately
budgeted successor contract and contributes no metric here.

No algorithm, threshold, tie law, corpus view, seed law, metric, or finalist
rule may change after any held-out result is observed. A defect correction
requires a new version, an exact supersession receipt, and complete re-emission
from the frozen predecessor inputs.

### Required per-cell source binding

Every fold/view/sample/book receipt must carry and validate all of:

- source task-result object identity and task-result payload SHA-256;
- fit-scope ID, `fit_candidate_view_sha256`, and
  `selection_provenance_sha256`;
- candidate lineup-order SHA-256 and roster SHA-256;
- corpus-view membership SHA-256 and, when sampled, rank-seed and sampled-ID
  SHA-256;
- ordered training-block IDs, exact training world-column SHA-256, the exact
  full lineup/row-hash ledger and matrix shape/hash, and an exact sampled-ID
  subset ledger whose per-lineup row hashes equal the full ledger;
- selector ID, selector SHA-256, executable fingerprint, exact selected order,
  a derived 80-row trace binding every selected ordinal to its sampled ordinal
  and exact score-row hash, and first-4/14/80 prefix hashes; and
- immutable selector-produced book-receipt identity before any held-out read.

The public selection and evaluation seams accept validated, generation-pinned
design, bootstrap-manifest, process-budget, projection-bundle, and
selection-receipt authorities, not
caller-provided eligible arrays, roster maps, block arrays, matrix hashes,
metric rows, phase grids, comparison ledgers, bootstrap rows, or finalist
identities. An evaluation publication additionally requires all five exact
held-out artifact identities, all five finite float64 candidate-by-world
matrices with exactly 10,000 worlds, and the exact generation-pinned
later-source body used to derive player-to-game mappings. It consumes the
five held-out inputs once, sequentially in exact `R0..R4` order, validates
each float64 matrix as exactly candidate-count by 10,000 finite values, reduces
and discards each fold input, derives the complete ordered population and book
metric rows for every fold/cell/prefix, and persists all row and fold hashes
internally. The result also binds the five child-execution hashes, 5 logical
fold selections, 10 broker/matrix OS processes, exact evaluator budget, and
embedded environment observation. Environment-observed job, execution, image,
and task values are not cloud attestation. Synthetic arrays and raw
finalist/bootstrap helpers remain private, non-exported unit-test fixtures.

## Corpus views

Let `A(c)` be the mathematical set of candidate `c`'s training-block
source-profile IDs after held-out provenance has been stripped. It is
serialized as a unique lexicographically sorted array, matching the sealed
candidate view; profile-registry order is not substituted. Membership is
defined only by frozen candidate provenance. A roster's shape may not be used
to impute an origin profile.

The following full-size views are emitted for every slate and fold:

- `U`: every fold-eligible candidate;
- `I[a]`: every eligible candidate for which profile `a` is in `A(c)`, for
  each of the seven profiles;
- `L[a]`: every eligible candidate for which `A(c)` contains at least one
  profile other than `a`, the leave-one-profile-out union;
- `P[a]`: every eligible candidate supplied by either `incumbent` or relaxed
  profile `a`, for each `a` from ordinal 1 through 6; and
- `E[a]`: candidates whose training source-profile set is exactly `{a}`.

All 28 full-size views receive population diagnostics. Only `U` and the seven
`I[a]` views are selected in v1. `L`, `P`, and `E` receive no new selector fit,
regardless of whether they contain 80 candidates. Existing sealed `U` books
may be reported as separately labeled operational context but cannot replace
the equal-count screen.

A `U` or `I` view with fewer than 80 candidates is marked
`structurally-infeasible-exact-80`; it is not padded, borrowed from another
view, or silently omitted. `I[a]` means origin-membership support, not a causal
arm-isolated population: a roster generated by multiple profiles belongs to
multiple `I` views. Conclusions must use that label.

## Equal-candidate-count design

The equal-count exploratory screen is `U` versus the seven `I[a]` views. It is
adaptive reuse of a bank whose prior `U` held-out metrics are already known;
it is not fresh inference. Independent-bank re-emission remains mandatory.

For each slate and fold, define `M` as the minimum eligible candidate count
among `U,I[0],...,I[6]`. If `M < 80`, the entire slate-fold screen fails
closed. Otherwise execution has two bounded phases:

1. **Broad screen:** one common-`M` sample for all eight views and all eight
   selectors, exactly 64 cells per slate-fold. It deterministically nominates
   the three fixed controls and no more than three challengers.
2. **Confirmation sensitivity:** 32 new common-`M` samples for only those
   three-to-six nominated cells. These samples use a separate seed domain and
   cannot add a cell omitted by the broad screen.

A view already of size `M` is retained byte-identically in every replicate and
is reported as having one distinct membership, not 32 independent samples.

There is no mutable PRNG. Candidate `lineup_id` values are ordered by the
ascending tuple

`(SHA256(seed_material || 0x00 || lineup_id), lineup_id)`

and the first `M` are retained. `seed_material` is canonical JSON containing
only:

- contract ID;
- panel object SHA-256 and panel self-hash;
- slate ID;
- fit-scope ID;
- phase domain, exactly `broad-screen` or `confirmation-sensitivity`; and
- exact replicate ordinal: `0` for the broad screen and `0..31` for
  confirmation.

The corpus-view ID is retained in the sample receipt but is deliberately
absent from the candidate-rank seed. Thus a candidate shared by nested views
receives the same hash rank within the same slate/fold/phase/replicate. The
canonical seed-material schema and its SHA-256 are persisted. Confirmation
metrics are averaged over all 32 replicates and their sample standard
deviation (`ddof=1`), minimum, maximum, and distinct-membership count are
reported. These overlapping hash samples are sensitivity replicates, not
independent standard-error units. One failed replicate fails the whole
slate-fold-view-selector confirmation cell.

This common-`M` design makes profile retrieval comparable without crediting a
larger arm for candidate volume. Full-size results remain useful operational
descriptions and population-size evidence, but never replace the equal-size
comparison.

### Fixed-panel serialization and memory bounds

The accepted 54-slate panel contains at most 250 fold-eligible candidates;
this is a fixed-bank execution contract, not an open-ended future-slate
schema. Every projection therefore contains 80 through 250 candidates, every
equal-count sample contains at most 250, and every roster contains exactly
nine sorted unique player IDs. Lineup IDs are safe ASCII tokens of at most 71
UTF-8 bytes; player IDs are safe ASCII tokens of at most 32 bytes. Occurrence
counts, object URIs, generations, and object byte identities have explicit
finite scalar bounds. A 251st candidate or any oversized/non-token identifier
fails before sampling, matrix selection, or receipt construction.

Adversarial maximum-shape serialization at 250 candidates measures below
29 MB for the complete five-fold broad receipt and about 85 MB for the
maximum six-nominee confirmation receipt. The immutable publication ceilings
are consequently 32,000,000 and 96,000,000 bytes respectively. The assembler
stdout remains a compact identity/evidence envelope capped at 4,000,000 bytes;
it never carries the published receipt body. Dispatcher verification streams
each generation-pinned opaque publication through a bounded SHA-256 sink and
retains no body. These dimensions, one-body-at-a-time aggregation, and an
explicit RSS algebra must remain below the 512 MiB dispatcher ceiling.

## Prefixes and entry count

Every selected order must freeze exactly the existing nested prefixes
`k={4,14,80}`. The prefix is always the first `k` entries of one exact
selector order; it is never refit independently.

Prefixes 100 and 150 are disabled in v1. They may be added only after a new
contract proves an exact deterministic continuation of the selector beyond
80 and freezes the resulting algorithm/code identities. An extrapolated
`a+b*ln(k)` curve may be shown as a labeled sensitivity analysis, never as an
observed 100- or 150-entry result and never as ROI.

## Population metrics

For every slate, fold, and corpus view, emit before book metrics. Given a
candidate-by-held-out-world matrix `S` and `N` candidates:

- full and equal-size candidate counts;
- total training occurrence count and true occurrence-dedup loss, exactly
  `sum(training_occurrence_count)-candidate_row_count`;
- unique roster count and the separately named surviving roster-alias count,
  exactly `candidate_row_count-unique_canonical_roster_count`; this diagnostic
  is not called dedup loss;
- occurrence multiplicity by profile and training block;
- exclusive and shared-profile counts;
- the vector `O_w=max_c S[c,w]`; report its mean and its q50/q90/q95/q99 using
  `numpy.quantile(method="linear")`, plus `max_w O_w`; this is the simulated
  corpus oracle and no other quantity is called an oracle;
- at each registered threshold, the number of lineups with at least one event,
  the total lineup-world event count, `1000 * tail_lineup_count / N`, and
  `tail_event_count / (N * 10000)`; and
- leave-one-out loss of candidate count, held-out tail availability, and
  mean simulated corpus oracle, all as `U-L[a]` paired differences.

Held-out population metrics are descriptive evaluation outputs. They cannot
change admission, selection, or the finalist function.

## Book metrics

For every selected selector/view/prefix/slate/fold/sample, compute on the
held-out 10,000-world matrix. Let `B_w` be the maximum selected-lineup score in
world `w`:

- `mean(B)`, `max(B)`, and q50/q90/q95/q99 of `B` using
  `numpy.quantile(method="linear")`;
- the exact event count and probability for `B>=194` and for strict
  `B>T`, `T={200,210,220,230,240}`;
- mean and maximum shared-player count over all unordered distinct lineup
  pairs on the 0-to-9 scale; unique-player count; and unique `game_id` count
  derived from the generation-pinned later-source player catalog;
- selected-lineup provenance exposure by profile and training block, derived
  only from fold-stripped occurrence/source-arm fields;
- selected-lineup pairwise tail-event correlation summaries; and
- effective independent tail shots at `>200`, `>210`, `>220`, and `>230`.

Repeat the following independently at each of `>200`, `>210`, `>220`, and
`>230`. Create a selected-lineup by held-out-world Boolean tail matrix. Rows
with zero variance are excluded from correlation decomposition and counted
separately. For the remaining standardized row correlation matrix, compute
eigenvalues with a symmetric eigensolver, clip only numerical negative values
in `[-1e-12,0)` to zero, and fail on a smaller eigenvalue. Report:

- active tail-lineup count;
- zero-event and all-event row counts;
- participation ratio `(sum(lambda)^2 / sum(lambda^2))`; and
- entropy effective rank `exp(-sum(p_i*log(p_i)))`, where
  `p_i=lambda_i/sum(lambda)` and zero terms contribute zero; and
- active-row pairwise correlation count, mean, minimum, and maximum; with
  null extrema and mean when fewer than two active rows exist.

If no nonconstant row remains, both effective-shot measures are exactly zero.
If one remains, both are exactly one. Full eigenspectra are not persisted.

Matrix calculations remain float64. At the result boundary each finite scalar is
serialized as a signed integer micro-unit using `numpy.rint(value * 1e6)`
(IEEE-754 ties-to-even) followed by exact int64 range validation. Counts remain
integers. Probabilities additionally retain exact event numerator and
denominator. Finalist metrics retain exact integer numerators and denominators
greater than or equal to one. Both broad and confirmation phase grids require
one common denominator per metric; a zero or mixed denominator fails closed.
Comparisons use rational cross-products before display rounding; display
values never drive a tie.

## Aggregation and uncertainty

The paired reporting unit is one `(slate_id, heldout_block)` **statistical
evaluation cell**. Aggregate each metric as an unweighted mean across all 270
cells; this 270-cell count is distinct from the 270 logical fold selections
and 540 selector OS processes in each phase. Do not pool worlds across slates
as though they were one contest. Confirmation metrics first
average the 32 sensitivity replicates within a cell, then average the 270 cell
values.

Report:

- all 270 paired cell values;
- mean and median paired delta versus the named baseline;
- five held-out-block-family means;
- season means as diagnostics only;
- a deterministic 10,000-resample paired **slate-cluster** bootstrap interval:
  sample 54 slates with replacement and retain all five block deltas for every
  sampled slate; and
- missing/failure census. Any missing cell prevents a terminal panel claim.

The bootstrap seed is canonical-JSON SHA-256 of exact tracked contract and
code SHA-256 values, pinned panel identity/self-hash, and the exact
source-ordinal-0-through-53 array of 54 `{slate_id,sha256}` confirmation
evaluation identities. URI or slate lexicographic sorting is forbidden. The
aggregate authority internally derives and binds, for every nominated
challenger and metric, the ordered 270-row `source_ordinal then R0..R4`
paired-delta ledger and its hash. No caller may supply a comparison or
bootstrap row. For replicate `r`, draw `d`,
and nonce `n`, hash
`seed_bytes || uint32be(r) || uint16be(d) || uint32be(n)`, reject integers at
or above `2^256-(2^256 mod 54)`, and take modulo 54; increment the nonce only
on rejection. Each of 10,000 replicates draws 54 whole slates and retains all
five folds. The 95% interval uses exact linear interpolation at 1/40 and 39/40
over sorted integer micro-unit replicate means with ties-to-even endpoint
rounding. It excludes GCS generations, aggregate bytes, finalist bytes, and
the terminal root, so the dependency is not circular.

The bootstrap describes simulated-bank stability. It does not create an
independent bank, historical confidence interval, or promotion probability.

## Baselines and deterministic finalist function

The primary equal-`M` baseline is
`U / coverage-194-v1 / k=80`. All three controls below are equal-`M` cells and
are nominated regardless of the broad screen:

1. `U / coverage-194-v1 / k=80` — current-union incumbent selector;
2. `U / tail-ladder-200-210-220-v1 / k=80` — registered tail control; and
3. `I[incumbent] / coverage-194-v1 / k=80` — legacy-profile sentinel.

Only equal-`M` `I[a]` cells from relaxed profiles 1 through 6 may nominate a
challenger. For the broad-screen nomination and again for confirmation, a cell
passes the simulated book-level 200-point non-inferiority guard when

`challenger P(book world-wise max > 200) >= baseline P(book world-wise max > 200) - max(0.001, 0.02 * baseline P(book world-wise max > 200))`.

The broad-screen probability is the exact 270-cell mean from its single
sample. The confirmation probability is the exact 270-cell mean after the
32-replicate within-cell average. Both use strict `>` and `k=80`.

The broad screen nominates challengers as follows. Sorting is explicitly
ascending on these tuples using exact rational numerator/denominator metrics;
`_micro` denotes the unit, not a rounded comparison value:

1. **Performance nominee:** minimize
   `(-mean_expected_book_max_micro, -p220_micro, -effective_shots_220_micro,
   profile_ordinal, selector_ordinal)`.
2. **Diversity nominee:** among other passing cells no more than 500,000 score
   micro-units below the performance nominee, minimize
   `(-effective_shots_220_micro, -p230_micro, profile_ordinal,
   selector_ordinal)`.
3. **Structural-contrast nominee:** among the remaining passing cells from
   `remove-qb-stack`, `remove-bring-back`, or
   `remove-all-five-shared-constraints`, minimize the performance tuple. This
   preserves one direct test of the winner-census support
   mismatch without hand-picking whichever profile looks best afterward.

Duplicate cells are emitted once. An empty slot is not backfilled. The three
to six nominated cells alone enter the 32-replicate confirmation. Mandatory
controls remain final controls. A challenger becomes a confirmed finalist
only if it passes the same P200 guard on confirmation; a failure is removed,
not replaced or re-ranked. `strict-230-coverage-v1` may be nominated, but one
sparse threshold never overrides the guard or performance tuple.

Full-size, leave-one-out, pair-union, exclusive-view, in-sample, 4-entry, and
14-entry results cannot nominate a v1 finalist. They
are mechanism and entry-count diagnostics only.

The broad grid is first sealed in a broad-phase authority that exact-reopens
all 54 broad evaluation publication bodies and generation-pinned identities
in source-ordinal/topology order, validates their complete metric transcripts,
and derives the grid and ordered projection/selection/evaluation layers. It
also binds the exact design, validated topology bytes and identity, and run
authorization. Topology ordinal 163 is one self-contained nomination
publication that embeds that exact rebuilt broad authority and the
deterministic nomination derived from it, plus both hashes. Confirmation
accepts only the exact generation-pinned ordinal-163 publication, replays the
nomination function against its embedded broad authority, and proves its URI
is the unique topology `nomination` URI. It cannot accept separate
caller-supplied broad or nomination bodies. A caller-created body plus
matching caller-created hash is not authority.

The finalist function is executable code, not prose interpreted after the
table. It accepts the combined aggregate-mechanics authority, never two raw
metric arrays. Its output binds the combined aggregate hash and nomination
hash; its source hash, tests, inputs, and exact output must be frozen in the
terminal result.

## Result topology

Publication, if authorized separately, uses one new create-once prefix. It
must be root-last and contain exactly:

1. one design object binding this tracked contract, phase lattice, compute
   ceiling, URI inventory, bootstrap process specifications, code/image
   identity, and pre-design run authorization (not later observed execution
   metadata);
2. 54 self-hashed selection-input projection bundles, each containing exactly
   five canonical fold projections from the non-selector process;
3. 54 immutable broad-screen selection receipts, written before any broad
   held-out read;
4. 54 broad evaluation results exact-binding those receipts;
5. one deterministic nomination object;
6. 54 immutable confirmation selection receipts, written before any
   confirmation held-out read;
7. 54 confirmation evaluation results exact-binding those receipts;
8. one aggregate mechanics object;
9. one deterministic confirmed-finalist object; and
10. one terminal root that exact-binds every predecessor.

This is exactly 275 objects. Each selection-receipt layer precedes its
evaluation layer in explicit topology ordinal order; URI lexical order is not
an authority. Evaluation without the exact receipt identity fails closed.

The one aggregate-mechanics object sequentially exact-reopens all 54 broad and
all 54 confirmation evaluation publication bodies and generation-pinned
identities in source-ordinal/topology order, validates and immediately reduces
each full body to its frozen compact record, and retains at most one full body
at a time. From those compact records it derives both phase
grids; exact ordered 54-entry projection, broad-selection, broad-evaluation,
confirmation-selection, and confirmation-evaluation layer arrays and hashes;
and every keyed comparison ledger, summary, and nonconstant slate-cluster
bootstrap result. It also binds the design/topology/run identities, the
reconstructed broad authority, and the exact nomination. These are
materialized object identities, not fictional caller-named layer roots or
caller-supplied metric arrays. All five arrays use explicit source ordinal
`0..53`, never URI lexical order, and their slate order must be identical. The
broad layers and grid must equal the nomination's broad authority; the
confirmation grid must equal the exact nominee lattice; every comparison row
must have complete 54-slate by five-fold coverage; and the bootstrap source
evaluation layer must equal the aggregate's confirmation evaluation layer.

Each phase additionally derives an ordered 270-entry
child-execution-evidence hash ledger in the same source/fold order, exactly
270 logical fold selections, and exactly 540 broker/matrix OS processes. The
aggregate and terminal root bind both phase ledgers and counts; a missing,
repeated, reordered, or fabricated evaluation/evidence identity fails closed.

The prefix must be a child of
`gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-current-bank-crossed-screens/`;
generic privileged and production namespaces are forbidden. The expected URI
inventory and per-invocation cumulative read/write budgets are compiled
before the first write. Every upload is precharged. Resume accepts an existing
object only when generation-exact bytes equal the would-be bytes. A root is
terminal only after a fresh process exact-reopens every identity and rebuilds
the aggregate and finalist bytes exactly.

Bootstrap authority covers every executable publisher role, including the
111-read/54-write projection publisher, both fold selector chains, both slate
assemblers, both evaluators, the ordinal-163 nomination publisher, the
aggregate/finalist publisher, and the terminal-root publisher. Publisher
budgets precharge their exact generation-pinned scientific read identities,
create-once topology writes, and byte ceilings before invocation. The
terminal-root API accepts an exact-ordinal opener, never a caller-materialized
274-body list. It validates each predecessor, immediately reduces each of the
108 full evaluation bodies to compact aggregate inputs plus exact identity and
body hashes, discards the full body, and retains zero full evaluation bodies
while rebuilding aggregate and finalist authority.

Every object makes the following code-path/allowlist claims. They are not an
external attestation about unknown systems:

- `uses_realized_outcomes=false`;
- `historical_scoring_performed=false`;
- `historical_scoring_licensed=false`;
- `corpus_regeneration_performed=false`;
- `matchup_source_read=false`;
- `graph_mutation_performed=false`;
- `production_change_performed=false`;
- `promotion_authority=false`; and
- `decision_authority=false`.

## Implementation and acceptance gates

No simulated output may be inspected until all of the following pass from a
clean tracked checkout:

1. this contract has a clean commit identity and exact file SHA-256;
2. the pure module validates authoritative five-fold projection bundles,
   immutable selection receipts, broad-phase/nomination authority, exact
   54-layer aggregate mechanics, and generation-pinned aggregate publication;
   it reproduces registries, canonical world columns, fold-safe views,
   common-seed subsamples, exact-rational finalist laws, strict 10,000-world
   tail metrics, input-bound deterministic bootstrap, 275-object topology,
   and role-derived URI/read/write/fit budgets;
3. adversarial tests reject reordered folds/layers, held-out provenance,
   current- or multi-generation reads, outcome/grade/funnel URIs, fewer than
   80 candidates, arbitrary sampled row ledgers, mixed/zero denominators,
   missing cells, mutable seeds, independent prefix refits, non-finite or
   non-10,000-world held-out matrices, changed tie laws, caller-created
   nominations, human-supplied finalists, forged child-execution evidence,
   mismatched launch authorization, and list-materialized terminal roots;
   known-answer tests pin the score-row byte hash, bootstrap
   seed/hash/endpoints, 270-logical/540-OS phase counts, and topology endpoint;
4. the projection process derives the exact 111-object structural allowlist,
   emits only the narrow schema, and tests prove old held-out/book fields
   cannot reach the selector worker;
5. one-slate smokes separately prove the five logical four-block selectors as
   ten ordered broker/matrix OS processes, the no-world-artifact assembler,
   then five sequential fifth-block evaluations, including
   sealed full-matrix and exact sampled-row-ledger equality, from immutable
   runtimes without writing the full prefix;
6. an independent review has no unresolved P0, P1, or P2 finding about
   leakage, deterministic selection, candidate-count fairness, runtime/code
   identity, transport bounds, or root-last publication; and
7. the design freezes no all-block fit and at most 17,280 broad selector fits and 51,840
   confirmation fits (69,120 total), excluding failed cells; exact compute and
   output byte ceilings are durably tracked; and
8. the exact full-run attempt and runtime identities are durably tracked
   before the first backend mutation.

A passing Stage 1 result licenses only the next preregistered research step:
re-emission on the independent common-random-number bank and nomination into
a separately authorized sparse historical comparison. It cannot change the
served lineup engine, schedule a shadow, enter a contest, or establish that a
strategy improves realized scoring.

## 2026-08-27 implementation disposition

This document is the required design, not evidence that every acceptance gate
has passed.  The current implementation now separates the contract/schema
module from the selector runtime: the contract owns canonical literal copies
of the seven profiles and eight strategies and imports no selector module or
callable. A sibling broker/matrix selector chain alone verifies the live registries,
accepts a generation-pinned projection bundle/topology/process budget and the
finite float64 training matrix, verifies the sealed matrix hash, derives the
full and sampled row ledgers, executes and replays every frozen selector cell,
and exposes no caller parameter for cells, selected IDs, traces, or ledgers.
The five-fold assembler also requires exact phase, source, process ordinal,
per-fold cell cardinality, bootstrap process chain, pre-design run
authorization, process-budget identities, exact four-read ledgers, and five
distinct child-execution transcripts, closing broad-to-confirmation receipt
splicing and the prior single-process accounting gap.

The implementation now contains the authoritative evaluation, phase, and
aggregate construction paths described above. Evaluation derives its complete
metric transcript from exact held-out inputs; broad and aggregate construction
exact-reopen the ordered 54-publication phase sets; aggregate construction
derives the canonical phase grids, paired comparison ledgers, summaries, and
bootstrap results without caller metric input; and finalist/root construction
consumes those derived authorities. Ordinal 163 is now the sole public
nomination wrapper containing the exact rebuilt broad authority. Both phase
aggregates prove 270 logical fold selections and 540 selector OS processes.
This remains a design-time, no-output slice until the focused contract and
selector suites, static checks, and a fresh adversarial final review all pass.
No production or cloud output is authorized by the presence of code alone.

The durable-authority implementation also has a topology-bearing design
whose exact budget enumerates all 275 ordinal URIs with positive byte ceilings
and create-once semantics, a bootstrap manifest covering every publisher and
both broker/matrix selector components, evaluator and publisher precharge
builders, an aggregate-identity-bound finalist function and finalist
publication authority, and a streaming terminal root. That root opens exactly
the 274 ordinal predecessors, immediately reduces and discards full evaluation
bodies, rebinds every supplied body to its generation-pinned identity, rejects
missing/reordered/tampered predecessors, reconstructs aggregate/finalist bytes,
and binds the sole topology root URI. Fold and slate receipts additionally
retain the complete projection-derived view-registry hashes. These closures do
not waive the remaining focused-test, static-check, or final-review gates.
