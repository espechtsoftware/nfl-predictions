# Observatory Phase 3 lead checkpoint review

**Decision date:** 2026-08-25

**Reviewed worktree:** `/home/erich/projects/nfl-predictions-observatory`

**Reviewed branch:** `feature/neo4j-react-observatory`

**Reviewed head:** `ff04bd67`

**Decision:** **APPROVE ONE CORRECTIVE COMMIT; INTEGRATION NOT APPROVED**

The Phase 3 packet is clean, pushed, isolated from the active scoring chain,
and useful. It did not wire a route, contact Neo4j, read governed artifacts or
outcomes, change IAM, or deploy anything. There is no P0 while these modules
remain offline and unmounted.

The architecture should be retained: a GET-only API over a repository seam,
fixture-backed contract tests, versioned graph vocabulary, exact source
identities, and a rebuildable graph projection are the right direction. The
implementation nevertheless has P1 gaps that make a router cutover or graph
load unsafe and, in several places, make the Phase 3 claims stronger than the
code proves. The delegated assistant is authorized to make one bounded
corrective Phase 3 commit. Router integration, a live graph, governed source
reads, realized data, deployment, and UI cutover remain withheld until the
correction is reviewed.

## Accepted work

- `76d9577a` adds only new, GET-only API/read-model modules and focused tests.
  The router is deliberately absent from `main.py`.
- `19c5cc33` adds only pure offline graph-contract code and tests. It creates
  no driver, connection, cloud operation, or graph write.
- Successful API envelopes carry release and staleness metadata; receipts are
  projected through an allowlisted metadata model rather than returning raw
  bodies.
- Page-size and serialized-response caps, an ETag mechanism, and a synthetic
  fixture repository provide a good test foundation.
- The graph vocabulary keeps `FillPreset`, `AdmissionPreset`, and
  `RetrievalPreset` distinct, forbids factual `COVERED_BY`, requires inferred
  defender exposure to remain qualified, validates four-part GCS source
  identities, fails on conflicting node/edge identities, and produces batch
  hashes plus a terminal-census concept.
- The preceding Phase 2 corrective commit is represented accurately in the
  branch handoff. No new Phase 2 blocker was found in this checkpoint.

## P1 corrections required before API integration

### 1. Make degradation apply to the entire read surface

Only `/status` catches a repository exception, at
`src/nfl_dfs/app/foundry_api.py:185`. Even there, `_respond()` subsequently
calls `release_identity()`, `staleness()`, response canonicalization, and the
byte-budget check outside that guard (`foundry_api.py:76`). Every other route
calls repository methods directly (`foundry_api.py:202-402`). A missing graph,
malformed adapter row, non-finite value, or oversized endpoint therefore
becomes an unhandled 500 despite the stated “healthy degraded” contract.
The degraded response also reflects raw `str(exc)` text
(`foundry_api.py:192-193`), which can disclose backend details.

Required correction:

- put repository access, model conversion, release/staleness lookup,
  canonicalization, and response-budget enforcement behind one common read
  boundary for every endpoint;
- return a stable, sanitized reason code and safe message, while logging the
  internal exception server-side;
- distinguish unavailable backend (503), invalid client cursor/filter (422),
  absent entity (404), and server-side response-budget/contract failure;
- test a failing non-status repository method, failing release/staleness
  methods, malformed/non-finite repository data, and a genuinely oversized
  route response—not only the budget helper.

### 2. Never make the synthetic fixture the production default

`default_foundry_repository()` returns `FixtureFoundryRepository()`
unconditionally (`foundry_api.py:49-54`). That fixture reports 54 accepted
slates (`foundry_read_models.py:325-345`) and uses winner-like governed labels.
If the router were mounted as written, an absent graph would return synthetic
research state with HTTP 200. The envelope evidence note is also permanently
hard-coded as fixture-backed (`foundry_api.py:70-73`), so a future real adapter
would be mislabeled.

Required correction:

- production default must be an explicitly unavailable repository that yields
  a sanitized degraded response until a release-bound adapter is configured;
- retain the fixture only through test dependency overrides or an explicit,
  unmistakable local-development setting;
- make authority/evidence notes repository- and release-derived;
- rename fixture identities so none implies that governed evidence was read.

### 3. Enforce query-side bounds, not only response-side pagination

The repository protocol returns complete `Sequence` objects
(`foundry_read_models.py:234-253`). Routes materialize every model through
`_rows()` before slicing a page (`foundry_api.py:154-182`). Thus a page size of
50 can still execute and allocate an unbounded graph query. There is no
query-side row limit or deadline, and cursors are bare offsets that are not
bound to endpoint, filters, or release (`foundry_read_models.py:256-269`).

Required correction:

- make pageable repository methods accept a validated page request and return
  a bounded page plus total/next-cursor information;
- require catalogued queries to carry a hard row cap and adapter timeout;
- bind opaque cursors to API version, endpoint/query, canonical filters, and
  immutable release identity, and reject cross-query/release reuse;
- cap any non-pageable collection in the model and adapter contracts;
- add adversarial tests proving the repository is never asked for more than
  the licensed page/cap.

### 4. Bound path parameters and freeze response schemas

Query IDs use a bounded annotation, but `experiment_id`, `book_id`,
`slate_id`, `lineup_id`, and `receipt_id` path parameters remain plain `str`
(`foundry_api.py:254-256`, `296-299`, `343-347`, `388-391`). The OpenAPI test
freezes only paths/methods, while `Envelope.payload` is `object`; it does not
freeze each endpoint's response contract.

Required correction:

- use a `Path`-appropriate canonical ID type with length and character bounds
  on every path ID;
- add explicit typed payload/page envelope models or discriminated response
  models per endpoint;
- assert request parameters and response schemas in the OpenAPI/contract
  tests, not just route names.

### 5. Preserve staleness truth across ETag revalidation

The ETag deliberately replaces the entire staleness object with `None`
(`foundry_api.py:97`). A client can therefore receive 304 and keep a formerly
fresh body after it has crossed the stale threshold.

Required correction: bind the ETag at least to generated/verified identity and
the stale-state transition. It may omit continuously changing `age_seconds`
if age is separately conveyed, but it may not hide a fresh-to-stale change.

### 6. Add cross-field and finite-value model laws

The current Pydantic models allow `missing > total`, accepted tasks greater
than total tasks, NaN/infinite metrics, unbounded identifiers/text/tuples, and
silently ignored extra fields (`foundry_read_models.py:41-231`). These can
make an apparently valid response scientifically false or exhaust resources
before the serialized byte check.

Required correction:

- require `missing <= total` and `accepted_task_count <= task_count`;
- require finite numeric metrics and exact SHA/timestamp/ID forms where those
  fields make authority claims;
- set bounded lengths/counts and `extra="forbid"` on adapter-facing models;
- add cross-field tests for status/disposition/scope/outcome-release coherence.

## P1 corrections required before any graph load

### 7. Replace name denylists with a positive graph property schema

The graph firewall recognizes only eight exact outcome names and five exact
secret names (`corpus_graph_vnext_contracts.py:58-67`). Fields such as
`actual_points`, `dk_points`, `lineup_score`, `tournament_rank`,
`access_token`, `client_secret`, `private_key`, or `apiKey` pass. Outcome node
kinds and relationships such as `OutcomeGrade`, `GRADED_IN_CONTEST`, and
`DERIVED_FROM_OUTCOME` can also be placed outside the realized namespace.

Required correction:

- define a versioned positive property allowlist, with type/size rules, per
  node kind and relationship (or a comparably strict schema registry);
- require all outcome entities, relationships, and properties to use the
  realized namespace;
- reject secret-like keys after canonical normalization/tokenization as a
  defense in depth, while relying on the positive schema as the primary law;
- test alternate spellings and representative score/rank/winner/payout and
  credential/key/token fields.

### 8. Bind realized authorization to exact accepted evidence

`authorized_outcome_release_id` is only a caller-supplied canonical string
(`corpus_graph_vnext_contracts.py:240-250`). It does not bind an exact release
object, receipt, generation, SHA-256, bytes, acceptance state, or authorized
scope. It therefore asserts authorization rather than proving it.

Required correction: keep `realized` entirely closed in this offline phase,
or require a separately reviewed exact accepted OutcomeRelease identity and
scope contract. A name alone must never open the namespace.

### 9. Make the graph plan genuinely bounded and streamable

Batch rows are capped at 500, but property counts, property-key lengths,
string bytes inside lists, source-release count, total node/edge input, and
the returned plan size are unbounded. Floats admit NaN/Inf. `build_load_plan()`
collects every row and then embeds every row in the returned plan
(`corpus_graph_vnext_contracts.py:275-383`), contrary to the Phase 4
requirement to stream transactions instead of constructing a full in-memory
load plan.

Required correction:

- cap property count/key length, list aggregate bytes and item strings,
  source identities, and all numeric values;
- reject NaN/Inf explicitly as `CorpusGraphVNextError`;
- separate a small deterministic plan/index from a streaming batch iterator
  or exact shard identities; do not retain all graph rows in a root plan;
- define total/shard bounds and checkpoint identities before any adapter can
  load data.

### 10. Close deterministic and Neo4j-semantic gaps

- `None` is counted as a property, but Neo4j null assignment removes a
  property. Reject it or represent missingness explicitly so the terminal
  property census matches persisted state.
- Canonicalize/sort source identities and reject duplicate/conflicting source
  identities; source ordering currently changes the manifest hash even though
  the module advertises order independence.
- Require exact top-level node, edge, and manifest key sets rather than
  silently discarding extra content.
- Bind outcome-bearing relationship types and endpoint node kinds to the
  authorized namespace and release.

## Required focused validation

The corrective commit must add adversarial tests for every P1 above, then run
serially when the lead confirms the local test lane is free:

1. `pytest -q tests/test_foundry_api_v1.py`
2. `pytest -q tests/test_corpus_graph_vnext_contracts.py`
3. the existing focused Corpus Research UI test
4. frontend typecheck and unit tests if any API contract/type changes touch
   the React slice
5. `git diff --check`

The Phase 3 handoff reports 15/15 API tests and 11/11 graph tests. This lead
checkpoint was a static review plus clean-branch/diff inspection; those tests
were not repeated while the live T230 panel occupied the active execution
window.

## Authorization and next checkpoint

Authorized now:

- one isolated corrective Phase 3 commit limited to the new API/read-model,
  graph-contract, focused-test, report, and branch-local handoff files;
- no new dependency; and
- no cloud, graph, source, outcome, IAM, deployment, or live-main action.

Still withheld:

- adding `foundry_api` to `main.py`;
- a fixture or real graph adapter that reads governed artifacts;
- any Neo4j provision/load/write;
- any realized namespace or outcome release;
- React route cutover, compatibility-page removal, packaging release, or
  deployment; and
- any change to the active T230/Core/R6 paths.

After the corrective commit is clean and pushed, the lead will re-review it.
Only then should a separate reversible router-seam commit and fixture-receipt
adapter be considered. This checkpoint does not slow or alter the live T230
panel or the route to historical scoring.
