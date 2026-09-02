# Pre-lock lineage review repairs: selective production port

**Date:** 2026-09-02

**Branch:** `codex/prelock-lineage-review-repair`

**Review commit:** `9ee67dc7deab893b52dc6d4f0579666ad8b97947`

**Integrated production base:** `origin/main`
`40aaba9846f55f6b7517aa6c5c2a4a2514c6cb75`

**Implementation commits:** `bd006ada` and source-identity hardening
`7186e878`

## Result

Every code-level concern in
`2026-09-02-prelock-lineage-phase1-production-review.md` is now either repaired
in the inactive selective port or enforced as an explicit false-authority gate.
The donor branch was not merged. The current immutable v1 candidate-lineage
contract, typed selector events, hardened graph-v2 projection, and source-set
v6 scoring files remain unchanged.

The implementation is still **default-off**. It has no CLI, route, scheduler,
deployment, graph loader, or automatic settlement caller. No cloud object,
BigQuery row, Neo4j row, model, score, lineup policy, paid entry, or deployment
was changed by this work.

## P0 disposition

1. **Immutable v1 collisions — repaired.** New detailed evidence uses
   `prelock-lineage-capture-envelope/v2`; the published sidecar is constructed
   through the unchanged `prelock_candidate_lineage_v1` builder and validator.
   No second graph-v1 packet was added. The existing graph-v2 adapter is reused.
2. **Five-seed incompatibility — repaired.** R0-R4 are normalized into one
   v1-linear `native-union` stage followed by one fixed-budget CBWU stage. The
   integration test uses real `CandidateBatch` objects, generation ledgers,
   `combine_cbwu_books`, typed `CoverageSelectorEvent` replay, and the immutable
   v1 seal. Requests, attempts, occurrences, cross-seed dedupe, pool-cap loss,
   CBWU admission, selector decisions, and final-book rows reconcile.
3. **Subsecond provider ordering — repaired.** Exact provider creation times
   retain microseconds. The whole-second graph contract receives a conservative
   ceiling of the sidecar provider time, so it can never claim to predate the
   provider object. The `.500000Z` same-second case is tested.
4. **Later-clock retry — repaired.** The first create-once capture contains the
   exact compressed selector matrix and everything needed to rebuild the v1
   sidecar and graph projection. Retries reopen before generation, resume from
   every publication boundary, and never reread salary or regenerate lineups.
   A complete root is read-only even after lock.
5. **Missing durable root — repaired.** The write set is exactly five objects:
   capture authority, raw matrix, immutable v1 sidecar, graph-v2 projection,
   and a fifth/root-last final manifest. The final manifest binds all four
   predecessors by role, fixed name, URI, generation, SHA-256, byte count, and
   trusted provider creation time. Every predecessor and the root are exact-
   reopened before completion. The former donor terminal is intentionally not
   retained: the final manifest supersedes its two-object binding and the
   production graph adapter correctly binds the immutable sidecar directly.
6. **Positional rescue join — repaired.** Settlement requires a complete
   one-to-one join on both `candidate_instance_id` and `roster_id`; duplicate,
   missing, extra, or mismatched rows fail before calculation. Input order has
   no effect. Every outcome source, winner source, and winner registry is bound
   to exact provider bytes. Force-one rescue totals remain explicitly non-joint.

## P1 and authority disposition

7. **Selector/source compatibility — preserved.** The adapter consumes current
   typed events and existing `_native_candidate_transform` / `_candidate_capture`
   seams. It does not modify engine, live-lineup, CBWU, selector, immutable v1,
   or graph-v2 sources. The exact v6 inventory remains
   `830dcfbde6cd3e2a6ac629cfbf6a7f8acd2b237f8951f9c050d40a6e1f30ad54`.
8. **Strategy/objective/preset semantics — repaired.** Selector ID and retrieval
   preset ID are separate required fields, and the existing graph-v2 total map
   is used. Admission stage IDs are never substituted for presets.
9. **Execution and model identity — repaired.** The capture binds the exact v6
   policy inventory, a separately hashed lineage-adapter manifest, immutable
   image digest, exact clean source commit, CBC binary hash/size, PuLP version,
   Python/NumPy/OS/architecture/CPU/memory envelope, and exact model-registry
   artifacts. Model generations are frozen before generation and exact-reopened
   after generation; a changed latest week, object census, generation, bytes,
   hash, or creation time fails before the first capture can publish.
10. **Read/write boundary — repaired.** GCS publication is fixed to
    `settings.gcs_bucket`, one deterministic run prefix, five fixed names, and
    create-only `if_generation_match=0`. A scoped BigQuery proxy permits only
    SELECT/WITH reads from the seven frozen pre-lock tables and exposes no write
    methods. Rejected reads remain fatal even if legacy fallback code catches
    the first exception. Ownership shadow, candidate log, distribution artifact,
    and graph writes are disabled. There is no runtime entry point.
11. **Double salary read — repaired.** One exact latest-pull dataframe supplies
    lock time, allowed player IDs, draftable bridge, salary catalog, and salary
    overrides. A test store raises on a second read; all retries complete with
    exactly one read.
12. **Outcome exclusion and feature intelligence — repaired.** Effective player
    fields use a positive, versioned allowlist, so aliases such as
    `actual_rank` fail rather than escaping a denylist. The exact typed feature
    values and player order—not merely a hash—live in the create-once capture,
    including projection distribution, component means, market blend, salary,
    matchup, ownership-derived pre-lock tilt, and route fields when present.
    Detailed rows remain outside Neo4j; only the bounded graph-v2 aggregate is
    produced.
13. **Settlement authority — preserved false.** Descriptive settlement binds
    candidate scores, opportunity rosters, complete standings, entries/field
    bridge, access receipt, winner score, and winner-registry-v2 identities, but
    it deliberately sets official-adapter, settlement, decision, promotion,
    and graph-mutation authority to false. It cannot support adoption until
    reviewed official source adapters exact-reopen those sources.

The donor's useful paid-preparation seam is also retained as an optional
callback on the existing paid-v2 exporter. Its test proves ordinary and traced
CSV bytes and export receipts are identical. Nothing calls the seam yet.

## Validation

- **150/150 focused compatibility and review-gate tests passed** across
  immutable v1 lineage, typed selector instrumentation, graph-v2, real live
  multiseed/CBWU behavior, policy-v6 identity, generation exposure, paid-v2,
  and all new authority/publication/settlement tests.
- The new/modified 45-test slice passed independently.
- Adversarial coverage includes subsecond provider time, create-only GCS race,
  later-clock retry after each of five write boundaries, complete post-lock
  read-only reopen, arbitrary bucket rejection, salary second-read rejection,
  model-generation drift, dirty/wrong source commit, rejected BigQuery reads
  swallowed by caller code, feature alias rejection, matrix tamper, keyed score
  permutation, and missing/duplicate score rows.
- Ruff passes on every changed Python file; all new modules compile; and
  `git diff --check` passes.
- A repository-wide suite was started but intentionally interrupted near 1%
  because this repository includes long-running experiment tests; no failure
  had appeared. It is not counted as validation.

## Remaining operational sequence

These are activation controls, not unresolved implementation defects:

1. Independently review this selective branch and merge it without importing
   the rejected donor contracts.
2. Build one clean immutable image from the merged commit and construct its
   execution receipt.
3. Well before lock, run exactly one candidate-only shadow with the read-only
   model authority and closed GCS store. The clean-checkout gate will reject a
   dirty tree or mismatched commit.
4. Exact-reopen the final manifest and all five provider generations, verify
   returned-book parity, and inspect the graph projection offline.
5. Only after that smoke may production choose to load the bounded packet into
   a dedicated shadow graph. Settlement remains descriptive until the official
   standings/entry/winner adapters are separately reviewed.

The branch should not be presented as a deployed Neo4j experience or an active
lineup change. It is the repaired evidence path needed to learn where scoring
opportunities are lost without changing how the book is built.
