# Corpus research Neo4j projection foundation

Date: 2026-08-21

Status: offline foundation focused-green. No Neo4j instance, connection,
secret, graph write, corpus mutation, policy change, or deployment occurred.

## Boundary and namespaces

Canonical create-once GCS objects remain authoritative. Neo4j is a dedicated,
append-only, rebuildable research projection. Every node sourced from a
retained object carries the exact immutable `source_uri`,
`source_generation`, `source_sha256`, and `source_bytes`. The graph holds
compact receipts, measurements, relationships, and JSON properties. The
50,000-world matrices, strict-event NPZ bodies, solver shards, and raw outcomes
remain in GCS as exact object pointers.

The namespaces are intentionally non-interchangeable:

- `corpus-retrieval-research` contains accepted retrieval task-0 evidence and
  compact retrieval analytics.
- `corpus-parametric-research` contains the seven-arm legal-feasibility and
  selection-parameter suite.
- `corpus-population-research` is reserved for a future, independently
  governed corpus-filling workstream. This loader creates no node or
  relationship in that namespace.

All policy, decision, fill, corpus-population mutation, and automatic-feedback
authority flags remain false. No result is fed back into production policy.

## Complete 54-task parametric projection

One parametric task may be appended only when all four exact canonical bodies
validate together:

1. a create-once batch completion with exactly 54 ordered task rows, seven
   arms, 378 cells, and `complete=true`;
2. the task result selected by its exact index in `0..53`;
3. its strict successful zero-retry terminal receipt; and
4. its independent verification receipt.

The loader binds the selected completion row to the task result object using
URI, generation, SHA-256, and bytes. It also binds the task SHA, artifact-source
task SHA, world-receipt-set SHA, terminal object identity, terminal semantic
SHA, verification semantic SHA, exact task index, exact slate ID, and the
verification season/week parsed from that slate. Duplicate task indexes,
reordered completion rows, reused task/result identities, cross-task retained
object aliases, and mismatched task/terminal/verification fields fail closed.

Every task-grain node, relationship, and measurement carries `task_index` and
`slate_id`. IDs use the exact zero-padded key (`task-0000` through
`task-0053`) plus the exact slate. Suite-scoped workstream, completion, and
rule nodes use `task_index_present=false`; they are deduplicated across
repeated task loads. Consequently, an operator may invoke the CLI once per
accepted task. Repeating the same task produces the same plan and immutable
MERGEs; loading task 53 cannot collide with task 0.

There is exactly one suite-level `DERIVED_FROM_RETRIEVAL_TASK0` relationship
to the accepted retrieval graph projection. It records
`lineage_scope=suite-root-only` and `same_slate_derivation_claim=false`.
Non-parent parametric slates therefore do not claim same-slate derivation from
retrieval task 0.

## Files

- `src/nfl_dfs/research/corpus_retrieval_neo4j.py`: receipt-bound base plan,
  immutable parameterized Cypher, exact source-byte binding, plan combiner,
  and canonical load-result receipt.
- `src/nfl_dfs/research/corpus_neo4j_extensions.py`: compact retrieval-sidecar
  measurements and complete-suite-validated 54-task parametric projection.
- `scripts/load_corpus_retrieval_neo4j.py`: offline `validate`/`dry-run`, plus a
  doubly gated optional live execution command with create-exclusive receipt
  output.
- `cypher/corpus_retrieval_neo4j_schema.cypher`: dedicated label constraint and
  indexes, including task index and slate ID.
- `cypher/corpus_retrieval_analysis_queries.cypher`: read-only analysis catalog.
- `tests/test_corpus_retrieval_neo4j.py`: offline adversarial contract tests.

Focused validation:

```bash
.venv/bin/python -m py_compile \
  src/nfl_dfs/research/corpus_retrieval_neo4j.py \
  src/nfl_dfs/research/corpus_neo4j_extensions.py \
  scripts/load_corpus_retrieval_neo4j.py \
  tests/test_corpus_retrieval_neo4j.py
.venv/bin/python -m pytest -q tests/test_corpus_retrieval_neo4j.py
```

Result at this milestone: 16/16 passed. The suite proves task 0 and task 53,
repeat idempotence, nonzero task IDs, task/slate/season/week/completion mismatch
rejection, cross-task alias rejection, source-byte binding, parameterized
Cypher, immutable conflicts, execute gates, and exclusive receipt conflicts.

## Offline validation and per-task extension

The retrieval terminal identity input is canonical JSON with exact GCS
`uri`, `generation`, `sha256`, and `bytes`. Completion, task result, graph, and
optional sidecar identities are chained from accepted receipts and checked
against the supplied bytes.

```bash
.venv/bin/python scripts/load_corpus_retrieval_neo4j.py validate \
  --terminal-receipt /durable/retrieval-task0/terminal-receipt.json \
  --terminal-receipt-identity /durable/retrieval-task0/terminal-identity.json \
  --batch-completion /durable/retrieval-task0/completion.json \
  --task-result /durable/retrieval-task0/result.json \
  --graph-projection /durable/retrieval-task0/graph-projection.json
```

Only compact canonical JSON analytical sidecars are accepted. NPZ and world
bodies are deliberately unsupported. The parametric extension is all-or-none;
for one selected task, add all eight flags below. Repeat the command with the
same complete completion and each task's own exact result/terminal/verification
inputs to append more of the 54 tasks:

```text
--parametric-batch-completion PATH
--parametric-batch-completion-identity PATH
--parametric-task-result PATH
--parametric-task-result-identity PATH
--parametric-terminal-receipt PATH
--parametric-terminal-receipt-identity PATH
--parametric-independent-verification PATH
--parametric-independent-verification-identity PATH
```

`validate` and `dry-run` only print canonical summaries and never import the
Neo4j driver or contact an endpoint.

## Operational load-result receipt

A successful transaction produces
`corpus-retrieval-neo4j-load-result/v2`, a deterministic self-hashed canonical
receipt containing:

- the exact plan SHA, schema-statement hashes, and parameterized load-query
  hashes;
- database name, exact node/relationship counts, kind/type counts, namespace
  counts, task indexes, and slate IDs;
- `idempotent=true`, pointer-only storage assertions, and all authority flags
  false; and
- `publication_mode=create_once` plus a requirement that any later GCS
  publication be generation pinned.

It never contains a connection endpoint, username, or password. Live CLI
execution requires `--receipt-output NEW_PATH`. That local path is opened in
exclusive-create mode and is never overwritten. If the graph transaction
succeeds but local receipt creation is ambiguous or conflicts, the loader does
not attempt a destructive rollback. The operator should retain/inspect the
path, rerun offline validation, and may safely repeat the identical immutable
graph MERGEs with a new receipt path before create-once GCS publication.

## Read-only analysis catalog

The catalog includes task- and slate-bound queries for:

- high-tail lineups and generation-pinned strict-event/world pointers;
- player, player-pair, team, team-pair, game, and stack enrichment;
- retained lineup-pair score correlations and overlap/event diagnostics;
- per-task parameter-arm measurements and retained/removed rule states;
- discovery R0--R3 versus held-out R4 strategy comparisons;
- uncertainty, support, denominators, coverage, and exact source identities;
- loaded task/arm coverage across the 54-task suite;
- paired challenger-minus-incumbent effects and cross-slate arm rankings with
  task counts, dispersion, extrema, improvement/tie counts, and regressed
  slate identities;
- the suite-only retrieval-task-0 lineage and no-feedback firewall; and
- an audit count for the reserved, unpopulated corpus-population namespace.

The graph does not store full matrices or raw outcomes. Analyses needing those
bodies must resolve the returned URI/generation/SHA/bytes pointer in GCS and
independently bind the fetched bytes.

## Live provisioning blockers and runbook

There is currently no Neo4j endpoint and no Neo4j-named Secret Manager entry.
The repository now pins the official Python driver as the dedicated
`graph` optional dependency (`neo4j==6.2.0`), the local research environment
imports it successfully, and the expansion image integration is pending with
the rest of the transport files. No immutable expansion image or live instance
should yet be assumed.

Before live execution:

1. Provision a dedicated Neo4j instance/logical database not shared with the
   application's operational datastore.
2. Establish the endpoint/network path and dedicated least-privilege secret.
   Do not place values in the repo, CLI flags, logs, or receipts.
3. Build and verify the immutable expansion image containing the pinned
   `graph` dependency and this loader.
4. Run `validate`, then `dry-run`; review exact identities, task/slate keys,
   namespaces, counts, and query hashes.
5. Inject `CORPUS_RETRIEVAL_NEO4J_URI`,
   `CORPUS_RETRIEVAL_NEO4J_DATABASE`,
   `CORPUS_RETRIEVAL_NEO4J_USERNAME`, and
   `CORPUS_RETRIEVAL_NEO4J_PASSWORD` at runtime. Also set
   `CORPUS_RETRIEVAL_NEO4J_DEDICATED=1`.
6. Live loading additionally requires literal `execute --execute`,
   `CORPUS_RETRIEVAL_NEO4J_ENABLED=1`, and
   `--receipt-output /new/exclusive/load-result.json`. Missing any gate fails.
7. Publish the reviewed canonical load receipt to a create-once GCS object and
   retain its generation-pinned identity alongside the execution evidence.
8. Run only read-only catalog queries. Any corpus-population experiment remains
   a separate workstream and may not be inferred from parametric evidence.

Repeated identical loads are idempotent. An existing node or relationship with
the same immutable key but different content, source bytes, task index, or
slate fails the transaction rather than overwriting retained evidence.
