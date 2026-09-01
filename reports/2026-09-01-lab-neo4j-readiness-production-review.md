# Lab Neo4j Handoff: Production Readiness Review

**Date:** 2026-09-01  
**Production disposition:** ready for a bounded integration/prototype load after small correctness repairs; not yet ready to describe as a production-operational knowledge graph  
**Scoring dependency:** none; this work should proceed in parallel and must not delay PREREG-078/079, E4, or other score-producing work

## Executive assessment

The lab has delivered real and useful Neo4j work, not merely a design. The
handoff provides a frozen first schema, a generated epistemic frontier,
loadable CSV artifacts, an idempotent Cypher loader, and a prototype ingester
for lineage-complete experiment runs. It is a good input to the production
research observatory.

The correct production action is **not** to run the supplied Docker command
unchanged and call Neo4j complete. The fast and trustworthy path is to absorb
the lab's epistemics and attempt-ledger work into the existing governed
production graph design, repair a few endpoint and loader gaps, perform a real
database/query smoke, and then stand up the dedicated read-only graph.

This preserves the architectural intent: immutable evidence remains
authoritative; Neo4j is a disposable, reproducible relationship index used to
understand experiments, corpus creation, retrieval, lineup traits, evidence,
and remaining knowledge gaps.

## Lab handoff reviewed

Source note:

- `../nfl2/handoffs/LAB-TO-PRODUCTION-2026-09-01-ACTION-NOTE.md`, Update 2

Lab commits:

- `2817a2c` — knowledge-graph v1 schema, ETL/export, 164-node/19-edge
  artifact, Cypher loader, and generated knowledge-frontier report.
- `adef67e` — per-run v2 ingestion prototype, Neo4j bootstrap note, 078
  mechanics example, and knowledge-frontier registry-digest test.

Important delivered files include:

- `../nfl2/docs/knowledge-graph-schema-v1.md`
- `../nfl2/scripts/build_knowledge_graph.py`
- `../nfl2/scripts/neo4j_bootstrap.md`
- `../nfl2/results/knowledge_graph_v1/`
- `../nfl2/reports/2026-09-01-knowledge-frontier.md`
- `../nfl2/tests/test_knowledge_frontier_fresh.py`

## What is genuinely ready

1. **The epistemics layer is useful now.** It represents questions, claims,
   reads, holds, experiments, contracts, and simulation-law versions. This
   directly supports the owner's request to distinguish what is known, what
   remains uncertain, which experiment supports a belief, and what currently
   blocks a decision.

2. **The high-level architecture is aligned.** World matrices stay outside
   Neo4j and are represented by immutable artifact identity/URI metadata.
   Neo4j remains derived and non-authoritative.

3. **The first real run-lineage slice exists.** The prototype ingested the
   `078m520r3-20260901T182923Z` mechanics shard into six nodes and five edges.
   Its four proposal-attempt ledger aggregates reconcile exactly, with zero
   ledger violations.

4. **The exports are deterministic enough to review and improve.** The base
   graph is represented as CSV plus Cypher rather than hidden mutable database
   state.

5. **The frontier report has a basic staleness hook.** Changes to the curated
   claims/questions/holds/reads registry require regeneration before its test
   passes.

## Corrections required before a real load

### 1. Relationship endpoint completeness

Seven of the 19 base relationships reference `Read` identifiers that are not
present in `nodes.csv`. Because the loader uses `MATCH` before creating an
edge, those relationships would be silently omitted; only 12 of the intended
19 relationships can currently load.

Required correction:

- Add the missing evidence/read nodes or remove unsupported relationships.
- Validate before publication that every edge start and end ID exists.
- Assert exact expected node and relationship counts after loading.

### 2. Per-run loading is not wired end to end

The v2 ingester emits `nodes_run_*.csv` and `edges_run_*.csv`, but
`load_v1.cypher` reads only `nodes.csv` and `edges.csv`. Bootstrap step 3 is a
comment rather than an executable loading path.

Required correction:

- Add a bounded CLI/loader for per-run slices.
- Make replay idempotent.
- Bind each load to source object identity and export checksums.
- Return a receipt containing attempted, created/matched, rejected, and final
  census counts.

### 3. The v2 scope is currently aggregate-only

The example contains `ExperimentRun`, `Slate`, and
`ProposalAttemptAggregate` data. Despite the forward schema, it does not yet
load:

- candidate lineups or canonical roster membership;
- players and lineup-player relationships;
- fill, admission, and retrieval strategy bundles;
- lineup traits, boom classifications, pairings, matchup/coverage traits, or
  correlations;
- selected-book membership;
- settlements, realized scores, Millionaire Maker winners, or winner-gap
  comparisons.

Therefore this release is the beginning of the knowledge index, not yet the
full intelligence system the owner ultimately requested.

### 4. The freshness check is narrower than the exported graph

The digest covers the curated `CLAIMS`, `QUESTIONS`, `HOLDS`, and `READS`
tables. It does not cover GCS-discovered experiment nodes, preregistration
amendment counts, the emitted CSV bytes, or source-object identities. The GCS
discovery helper also converts command failure into an empty run list.

One already-visible consequence is that the generated frontier still labels
Experiment 068 as active even though it has closed at mechanics failure.

Required correction:

- Bind the complete export manifest and every source identity into the
  release digest.
- Fail closed on discovery/read failure.
- Generate run state from authoritative terminal records rather than curated
  prose status.

### 5. A real database compatibility smoke has not occurred

The validation demonstrates Python export behavior and ledger arithmetic; it
does not yet prove Neo4j import compatibility, constraints/indexes, idempotent
replay, database census, or the advertised queries against a real server.

Required correction:

- Load into a disposable but persistent local/test instance.
- Run exact count, duplicate, missing-endpoint, idempotent-reload, and query
  smokes.
- Destroy and rebuild from the same release to prove reproducibility.

### 6. The bootstrap note is development-grade

The example uses a mutable `neo4j:5` tag, a placeholder password, broadly
bound ports, no persistent `/data` volume, and no explicit health, TLS,
backup, restart, or least-privilege configuration. It is useful as a sketch,
not as the production deployment recipe.

## Existing production observatory state

The production repository already has a substantial isolated observatory
workstream:

- Branch: `feature/neo4j-react-observatory`
- Current pushed commit at review: `832e4360`
- State: clean, 17 commits ahead of its original base but approximately 392
  commits behind current production `main`; it should be selectively ported,
  not blindly merged.

That branch already contains stricter graph contracts, a deterministic
fixture adapter, capacity estimation and load ceilings, a bounded read API,
and React application work. Recorded focused validation includes 109/109
capacity tests, 40/40 graph-contract tests, and 33/33 fixture-adapter tests.

It remains intentionally offline: no live Neo4j endpoint has been
provisioned, no governed source release has been loaded, no router or React
cutover has occurred, and no production graph pointer exists.

The two workstreams are complementary:

- Production supplies the governed schema, release identity, capacity,
  transport, API, and UI discipline.
- The lab supplies a useful epistemics registry and the beginning of real
  proposal-attempt/run lineage.

The schemas are not directly interchangeable. The lab introduces entities
such as `CandidateLineup`, `ProposalAttemptAggregate`, `Question`, `Claim`,
`Read`, and `Hold`, while the production contract currently uses its own
versioned `Lineup`, `Attempt`, experiment, evaluation, and release vocabulary.
Loading the lab CSVs unchanged would bypass the production contract.

## Production integration decision

Adopt the lab work as an **additive epistemics and run-lineage layer** inside
the governed production research observatory.

The resulting graph remains:

- dedicated to corpus and experiment research;
- read-only from the application;
- rebuildable from exact immutable releases;
- unable to launch experiments or change an active strategy;
- prohibited from storing world matrices, raw licensed vendor rows, secrets,
  or mutable production policy; and
- independent of all scoring gates.

## Fast implementation sequence

### A. Repair and freeze the lab packet

1. Add or resolve the seven missing evidence nodes.
2. Add endpoint-completeness validation.
3. Add an executable per-run loader and exact post-load census.
4. Bind all input/export bytes and authoritative run states into a release
   manifest.
5. Correct the stale Experiment 068 frontier status.

### B. Integrate from current production main

1. Create a new isolated integration worktree from current `main`.
2. Selectively port the accepted observatory contracts and adapters rather
   than merging the stale branch wholesale.
3. Version a schema extension for `Question`, `Claim`, `Read`, `Hold`, and
   proposal-attempt aggregates.
4. Define explicit mappings between lab and production identifiers.
5. Preserve fill, admission, and retrieval as distinct strategy entities.

### C. Run a real Neo4j compatibility gate

1. Use an immutable Neo4j image/version and persistent test data volume.
2. Create uniqueness constraints and required indexes.
3. Load v1 and the 078 run slice twice; the second load must make no logical
   change.
4. Assert exact node/relationship counts and zero dangling endpoints.
5. Exercise the initial questions, evidence, holds, experiment lineage, and
   reconciliation queries.
6. Rebuild from zero and compare the terminal release census.

### D. Provision the dedicated service

1. Use a dedicated database/instance rather than the application's primary
   operational graph.
2. Configure persistent storage, TLS/private access as appropriate, health
   checks, backups, and separate loader/read-only principals.
3. Store credentials only in the approved secret system.
4. Publish a content-bound graph release and activate the read-only pointer
   only after load/query acceptance.

### E. Extend toward lineup and winner intelligence

As authoritative artifacts become available, add:

1. every canonical corpus lineup and its source/fill provenance;
2. admission and retrieval decisions, ranks, reasons, and selected books;
3. players, pairs, stack/game structure, salary and ownership traits;
4. boom, matchup, coverage, correlation, and source-completeness traits;
5. realized scores and threshold cohorts such as `>=194`, `>=200`, `>=210`,
   and `>=230` only through governed settlement releases;
6. Millionaire Maker winner observations and comparable cohort definitions;
7. gap views showing where strong/winning traits were absent from supply,
   removed at admission, or missed by retrieval; and
8. React visualizations for strategy comparisons, evidence lineage, trait
   enrichment, missingness, and unresolved questions.

## Acceptance definition

Neo4j may be described as production-operational only when all of the
following are true:

- every graph release has exact immutable source and export identities;
- every relationship endpoint resolves;
- the loader is bounded, idempotent, receipted, and count-verified;
- a real-server load/query/rebuild smoke passes;
- the dedicated persistent deployment and least-privilege principals exist;
- the API exposes only release-bound read models and degrades safely;
- the UI truthfully distinguishes unavailable, partial, stale, exploratory,
  and confirmed evidence; and
- scoring and strategy activation remain independent of graph availability.

## Bottom line

The lab has supplied a valuable, integration-ready **knowledge and lineage
packet**. It has not yet supplied the complete live knowledge graph. The
remaining work is bounded and can proceed immediately in parallel with
scoring. The right route is a quick correction plus governed integration,
followed by a real Neo4j load smoke and dedicated deployment—not a restart of
the design and not an unreviewed one-command bootstrap.
