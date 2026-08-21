# Corpus artifact-supported source authority v1

Date: 2026-08-21
Status: contract and pure verifier implemented; no production receipt exists
Authority: research source evidence only

## Decision

The later-period source freeze does not establish a complete DraftKings salary
universe.  It establishes the exact player universe represented in each
slate's five retained R0--R4 world artifacts.  This lane therefore uses the
only truthful positive scope label:

`exact-artifact-supported-r0-r4-player-universe`

The completion always states all of the following:

- `artifact_supported_universe_complete=true` means that all five retained
  artifacts were reopened and proved to carry the same IDs as the freeze's
  structural catalog for every one of the 54 slates;
- `complete_dk_salary_universe_claimed=false`;
- `salary_coverage_is_predeclared_query_relative=true`;
- `salary_query_result_independently_verified=false` and
  `complete_dk_salary_coverage_claimed=false`;
- `salary_only_players_have_world_draws=false`;
- `outcome_columns_read=[]` and `uses_realized_outcomes=false`;
- historical scoring, production change, and live-strategy authority are all
  false.

No missing salary player is padded, imputed, assigned a zero, or otherwise
given a synthetic world draw.

## Closed inputs

The pure verifier accepts six retained common inputs plus one closed stream:

1. canonical later-source freeze bytes and their generation-pinned object
   identity;
2. canonical pre-query registration bytes and their generation-pinned object
   identity;
3. canonical salary-ID coverage diagnostic bytes and their generation-pinned
   object identity;
4. an iterator containing exactly 270 `RetainedArtifactBody` values in
   task-index-major, R0, R1, R2, R3, R4 order.

The registration predeclares the exact source snapshot, source run, candidate
query, structural-catalog query, and salary-ID diagnostic query.  The source
queries are replayed against the already validated later-source schema and its
fixed SQL, parameter, table, column, job, and location identities.  The salary
query is restricted to the predeclared `id`, `season`, and `week` projection;
the production publisher remains responsible for approving the registered
SQL identity and authorized snapshot table before execution.  The current
query receipt has no result-body hash, so this lane does not independently
prove that the retained diagnostic IDs are the query job's rows.  Its coverage
is relative only to the retained diagnostic and predeclared query identity; it
cannot establish complete DraftKings salary coverage.

The production-facing verifier takes already reopened retained bytes.  It has
no storage callback, cloud client, environment read, runner, or implicit
lookup.  Transport must reopen each object at the exact retained generation
and yield it once in the closed order.

## Schemas

Three canonical, exact-key, self-hashed schemas are introduced:

- `corpus-artifact-source-registration/v1`;
- `corpus-salary-universe-coverage-diagnostic/v1`, whose mandatory scope is
  `predeclared-query-relative-salary-player-id-coverage-diagnostic`;
- `corpus-artifact-supported-source-authority-completion/v1`.

For registration, source freeze, and salary diagnostic, the retained object
SHA/byte length is kept separately from the document's internal manifest SHA.
Equality between an object SHA and its internal self-hash is rejected as hash
conflation.  The completion binds both layers.  Each of its 54 self-hashed task
rows also binds the registration internal SHA, later-source internal freeze
SHA, salary-diagnostic internal SHA, slate/catalog/incumbent identities, and
the exact five world-artifact object identities.

## Streaming proof

For each of the exact 270 positions, the verifier:

1. requires the next record's exact task, role, URI, generation, SHA, and byte
   length to equal the corresponding later-source receipt;
2. rejects repeated or common-artifact-overlapping object URIs;
3. hashes and sizes the reopened raw bytes before decoding;
4. opens only that NPZ and reuses the existing later-source artifact validator;
5. requires the exact NPZ member set `cand_ix`, `totals`, `tail_line`,
   `player_ids`, and `player_draws`;
6. requires finite float32 player draws of shape
   `(artifact_player_count, 10000)` and the existing 10,000-world totals law;
7. proves the artifact's unique player-ID set equals that slate's catalog ID
   set; and
8. emits an ordinal/role/object/schema/dtype/shape/player-set validation row,
   then drops the decoded artifact before requesting the next record.

The iterator must end immediately after ordinal 269.  Receipt, validation, and
task manifests are independently hashed into the canonical completion.  The
strict completion replay checks the 54-by-5 topology, ordinal order, unique
URIs, task hashes, common-source bindings, per-task set hashes, salary counts,
and all three manifest roots.

## Salary coverage diagnostic

The diagnostic is mandatory and covers exactly the same 54 slate identities.
For every slate it retains a sorted, unique salary player-ID list and its hash.
All artifact-supported catalog IDs must be present in that list.  The receipt
reports exact artifact-supported, salary-only, and impossible artifact-only
counts and hashes.

Salary-only IDs are a boundary diagnostic.  They do not expand the experiment
matrix and do not acquire draws.  A zero salary-only count permits an equality
diagnostic for that slate but still does not turn this lane into an
independent complete-salary-universe authority.  Until an approved salary
source and exact SQL/parameter law are pinned and the query result is bound to
the retained row body, every reported salary count remains explicitly
predeclared-query-relative.

## Focused poison coverage

The isolated focused module covers:

- successful 54-task, 270-body streamed completion;
- exact scope wording and all negative authority/license flags;
- retained-object versus internal-manifest hash separation;
- missing, non-iterator, and wrong-order streams with fail-fast behavior;
- generation/identity drift and retained-byte mismatch;
- unknown NPZ outcome members, float64 draws, 9,999-world shapes, and an
  R0--R4/catalog player-set mismatch;
- predeclared source-query drift;
- a salary diagnostic missing an artifact-supported player;
- attempted salary-draw and realized-outcome claims;
- completion hash conflation, common-to-task binding drift, bool-as-int, and
  noncanonical JSON.

The fixture uses the existing later-source freeze validator.  It temporarily
substitutes a deterministic synthetic repaired-artifact digest solely because
the real retained NPZ bodies are deliberately absent from the repository; the
production path has no such substitution seam.

## Production boundary and blockers

The shortest safe production sequence is:

1. create-once publish and retain the reviewed pre-query registration before
   any registered query starts;
2. run the existing outcome-blind later-source freeze query path at the exact
   registered snapshot and retain its generation-pinned canonical bytes;
3. run the separately approved salary-ID diagnostic query at that same
   snapshot and create-once publish its 54-slate canonical result;
4. reopen registration, source freeze, and salary diagnostic at their exact
   generations;
5. reopen each of the 270 source-receipted NPZ objects one at a time at its
   exact generation and feed the closed iterator to the pure verifier;
6. create-once publish the returned canonical completion and give its retained
   object identity plus internal SHA to the corpus batch authority.

Remaining blockers before production execution:

- no transport/runner currently constructs the registration and salary
  diagnostic or feeds the exact generation-reopened iterator;
- the salary query SQL/table identity needs explicit review as a point-in-time
  structural player-ID authority;
- create-once claims and generation-match reopening must be implemented by the
  transport layer;
- the focused test module must be run after orchestration clearance;
- this source authority does not itself license outcome access, score the
  experiment, deploy a job, or change live strategy.

## Validation checkpoint

Only static compilation and isolated diff/whitespace checks are authorized at
this checkpoint.  No pytest, CBC, cloud action, outcome access, deployment,
handoff edit, commit, or push is part of this lane.
