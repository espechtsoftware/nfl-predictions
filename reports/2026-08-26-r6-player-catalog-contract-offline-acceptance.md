# R6 Player-Catalog Contract Offline Acceptance

Date: 2026-08-26

## Decision

**APPROVE** the reviewed player-catalog spine as an offline, outcome-blind,
explicitly non-authoritative catalog contract only.

This acceptance does not authorize a cloud execution, an R6 source freeze,
production integration, deployment, graph mutation, corpus fill or retrieval,
historical scoring, outcome access, promotion, or any T230 action. The
separate adapter gates in this report remain blocking for every authoritative
or production use.

## Exact reviewed artifacts

| Artifact | SHA-256 |
|---|---|
| `src/nfl_dfs/research/corpus_r6_player_catalog_v1.py` | `5da7905f3caa620597f22bfb348a12d099709feb26a409ecec8c5578c03d99b7` |
| `tests/test_corpus_r6_player_catalog_v1.py` | `41d976095d3052f3c4d1f96a89c98fe12baeee6a37be4d75c54217f4fe8493e2` |

The disposition applies only to these exact bytes. Any change requires a new
hash-pinned review.

## Validation record

- The author reports **51/51 passing** in the corrected project environment.
- An earlier invocation used system Python, where `pytest` was unavailable.
  It stopped before collection and therefore was an environment/precollection
  failure, not a failed catalog-contract test.
- The final independent disposition was static and hash-pinned. It did not
  rerun pytest, access cloud resources or outcomes, or inspect or alter T230.

## Severity disposition

| Severity | Open findings |
|---|---:|
| P0 | 0 |
| P1 | 0 |
| P2 | 0 |

The earlier stale duplicate-lane test expectation is absent from the accepted
test artifact. The remaining coherent 54-way lane permutation adversary
expects the earlier, correct exact source-to-lane rejection.

## Accepted contract behavior

The accepted module provides a strict structural projection seam:

1. Derivation receipts, per-task player catalogs, and the 54-task release use
   exact schemas, self-hashes, and canonical replay checks.
2. The player population is exactly the six structural fields `id`, `pos`,
   `team`, `opp`, `game_id`, and `salary`, with nonempty, unique players in
   strict ascending player-ID order. Names, projections, and outcome fields
   are excluded.
3. The frozen task lattice contains exactly 54 ordered source members. The
   source ordinal fixes the slate, task ID, and exact lane projection:
   `v12a` tasks 0-27 followed by `v12b` tasks 0-25. Member and release-entry
   validators reject valid-looking substitutions, reorderings, duplicates,
   and coherent 54-way permutations.
4. Each exact catalog reopen cross-binds the externally expected tracked root,
   accepted member, later-source catalog, artifact-source completion, and
   derivation code identity. Release construction applies one normalized
   expected code identity across all 54 reopens.
5. Catalog and derivation child URIs are deterministic children of one fixed
   catalog namespace. Release validation and exact replay reject relocated,
   reordered, reused, or substituted identities.
6. The injected create-once seam supports identical-byte resume, rejects a
   different-byte collision, exact-reopens the returned generation, and
   performs semantic preflight before the corresponding write boundary.

## Projection-only authority boundary

Every built object fixes `authority_boundary` to
`projection-only-pending-fixed-g0-replay`. All outcome, scoring, fill,
retrieval, graph, promotion, decision, production, publication, and
`r6_source_authority` fields are required to be exactly false.

The catalog-pair and release publication entry points hard-fail an
authoritative-publication request before writing. A complete internally
coherent alternate-root chain may be represented only as a non-authoritative
projection: it fails an exact reopen against the externally expected root and
cannot use these entry points to claim publication or R6 source authority.

## Blocking adapter gates

All five gates below are mandatory before any authoritative or production use:

1. **Repository-pinned G0 replay.** Implement a trusted outer adapter that
   exact-replays the repository-pinned G0 lock and derives every tracked-root,
   accepted-member, later-source, and completion projection from the exact
   retained source bodies. Caller-supplied coherent projections are not
   sufficient authority.
2. **Atomic create-once transport.** Implement the real storage publisher with
   an atomic create-if-absent precondition. On collision, it may resume only
   after exact-reading the retained generation and proving byte identity; it
   must never overwrite the existing object.
3. **Generation-specific exact reads.** Implement the real reader so it fetches
   the requested generation, never an unpinned latest object, and verifies the
   URI, generation, byte count, and SHA-256 before parsing.
4. **Resolved code and final namespace identity.** Resolve the code identity
   from the committed module bytes rather than a caller assertion, then pin
   the catalog namespace and final release object identity in a separate
   fixed-G0 replay manifest.
5. **Adapter-level integration evidence.** Add focused integration evidence
   proving the real adapter's fixed-root derivation, transport preconditions,
   collision behavior, generation-pinned reads, and fail-closed authority
   boundary before designing or enabling any separate authoritative
   publication path.

Until all five gates are implemented and independently reviewed, the accepted
artifacts remain projection-only and execute-blocked.
