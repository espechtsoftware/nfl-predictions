# Observatory Phase 3 lead acceptance

**Date:** 2026-08-25
**Workstream:** Foundry Neo4j/React observatory
**Branch:** `feature/neo4j-react-observatory`
**Reviewed branch head:** `3baf659fbaca4fbba91907891187a77a7acc5103`
**Corrective implementation:** `c1f6af83f2fd6e2cc8b5a2bb2cf7395371ac6ab0`
**Decision:** **OFFLINE PHASE 3 ACCEPTED; PRODUCTION INTEGRATION NOT YET APPROVED**

## What is accepted

The Phase 3 corrective implementation closes the P1 findings in
`reports/2026-08-25-observatory-phase3-lead-checkpoint-review.md` while
preserving the workstream's outcome-blind, read-only, offline boundary.

- The Foundry API now has a common sanitized failure boundary, an
  unconditionally unavailable production repository until a real adapter is
  supplied, repository-side pagination/deadline bounds, release/filter-bound
  cursors, bounded identifiers, typed OpenAPI response contracts,
  staleness-aware ETags, and strict finite/cross-field/provenance laws.
- The graph contract now uses positive per-kind and per-relationship property
  schemas. Unregistered properties fail closed. The `realized` namespace is
  completely closed in this offline version, and secret/outcome aliases,
  nulls, nonfinite numbers, oversized values, duplicate/conflicting sources,
  and noncanonical source order are rejected.
- Graph batches are exposed through a bounded iterator rather than retained
  as an unbounded root plan.
- The branch and its tracked handoff are clean, pushed, and exactly aligned
  with `origin/feature/neo4j-react-observatory`. Docs-only follow-up
  `3baf659f` records the exact Python 3.11 validation environment, corrects
  the API contract-failure status description, and avoids overstating input
  streaming; it does not alter the accepted implementation.

Independent review found no remaining offline Phase 3 P0 or P1 issue.
Recorded validation is:

- API contract tests: **24/24**;
- graph contract tests: **40/40**;
- compatibility UI tests: **8/8**;
- previously recorded React tests: **44/44**; and
- `git diff --check`: clean.

The detailed corrective evidence is on the branch at
`reports/2026-08-25-observatory-phase3-corrective-commit.md`.

## What this does not authorize

This acceptance does not mount the router, connect a real repository, load or
query live Neo4j, open the `realized` namespace, read governed source or
outcome artifacts, cut over the React UI, provision infrastructure, alter IAM,
or deploy. The default production API correctly remains unavailable rather
than presenting fixture data as real.

The current main-worktree Python 3.14/FastAPI/Starlette test stack has a
TestClient portal hang even for a trivial application. The API suite was
validated under a temporary Python 3.11 environment with the stable compatible
FastAPI/Starlette/httpx/anyio stack recorded by the lead. Dependency/runtime
compatibility must be pinned or deliberately updated before packaging or live
integration; this is an integration gate, not an offline Phase 3 defect.

## Next authorized work

Proceed with **Phase 4 offline only** in the isolated observatory worktree:

1. build fixture-receipt adapters into the positive graph vocabulary;
2. add versioned schema/constraint and deployment/load-manifest contracts;
3. stream deterministic idempotent batches with create-conflict rejection;
4. add the bounded allowlisted Foundry query catalog and canonical query
   fixtures;
5. prove zero-state fixture rebuild equivalence by census and query hashes;
6. keep `realized` closed and accept only injected, terminal,
   identity-bound source fixtures; and
7. stop for lead review before router mounting, live graph access, or any
   infrastructure action.

Phase 5 capacity estimation may be designed alongside Phase 4, but its mode
decision must use real terminal release counts supplied by the lead. No live
Neo4j provisioning is authorized by this acceptance.
