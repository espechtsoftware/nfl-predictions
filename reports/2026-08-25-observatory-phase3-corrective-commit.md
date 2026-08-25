# Observatory workstream — Phase 3 corrective commit evidence

**Workstream:** Neo4j/React observatory (delegated lane)
**Date:** 2026-08-25
**Responds to:**
`reports/2026-08-25-observatory-phase3-lead-checkpoint-review.md`
(APPROVE ONE CORRECTIVE COMMIT; INTEGRATION NOT APPROVED)
**Branch:** `feature/neo4j-react-observatory`

## Authorship and coordination note (recorded for the operator)

While this session was implementing the correction, a concurrent session
was implementing the same correction in the same worktree; its rewrites of
`foundry_read_models.py`, `foundry_api.py`,
`corpus_graph_vnext_contracts.py`, and both test modules superseded this
session's drafts on disk (last-writer-wins, uncommitted). This session
detected the collision, stopped writing, waited for quiescence (~10 min
with no further writes), validated the surviving set, repaired one test
defect (a bad-route fixture shorter than the model's min-length, so the
wrong validator fired first), and produced this single authorized
corrective commit. Recommendation: point exactly one session at a
worktree at a time.

## P1 coverage (verified in the committed set)

API (review items 1–6):

- one common read boundary covers repository access, model conversion,
  release/staleness lookup, canonicalization, and the byte budget on
  every endpoint; backend internals are logged, never reflected —
  sanitized stable reason codes with a four-way taxonomy
  (503 degraded / 422 invalid-request / 404 not-found / 500
  response-contract-failure);
- `default_foundry_repository()` returns `UnavailableFoundryRepository`
  unconditionally — the synthetic fixture is reachable only by explicit
  test injection, and authority/evidence context is repository-derived
  (`AuthorityContext`, fixture forbidden from claiming outcome
  authority); fixture identities are fixture-named throughout;
- pagination is query-side: repository methods take a validated page
  request with a hard cap and deadline budget; cursors are bound to API
  version, catalogued query, canonical filters, and release identity,
  with offset caps; adversarial tests prove the repository is never
  asked for more than the licensed page;
- every path/query identifier is length/pattern-bound; per-endpoint
  typed envelope/page response models are asserted in the OpenAPI
  contract tests (parameters and response schemas, not just paths);
- ETags no longer hide staleness truth: the fresh→stale transition is
  part of the ETag basis while continuously-changing age is conveyed via
  an `X-Foundry-Age-Seconds` header;
- strict model laws: `extra="forbid"`, finite numerics
  (`allow_inf_nan=False`), `missing <= total`,
  `accepted_task_count <= task_count`, ordered
  generation/verification timestamps, real-UTC validation, receipt
  route/id binding, scope/outcome-release coherence.

Graph (review items 7–10):

- a versioned POSITIVE property schema per node kind and relationship is
  the primary firewall (unregistered properties never load); normalized
  secret-token rejection is defense in depth; alternate spellings are
  tested (`actual_points`, `dk_points`, `access_token`, `client_secret`,
  `private_key`, `apiKey`, …);
- outcome node kinds, relationships, and properties are namespace-bound
  to `realized`, and `realized` is ENTIRELY CLOSED offline
  (`OFFLINE_ALLOWED_NAMESPACES` excludes it); no manifest field can open
  it — a later opening requires a separately reviewed exact accepted
  OutcomeRelease contract;
- the root plan holds only per-batch identities and the exact terminal
  census; rows stream through `iter_load_batches`; property counts, key
  lengths, string/list aggregate bytes, numeric magnitudes, source
  counts, and total elements are capped; NaN/Inf are rejected;
- `None` properties are rejected (Neo4j null removes a property);
  source identities are canonically ordered with duplicate/conflict
  rejection so input order cannot change a manifest hash; node/edge/
  manifest rows enforce exact key sets.

## Validation (serial, exact results)

1. `pytest tests/test_foundry_api_v1.py` — **24 passed** (after the
   one-line bad-route fixture repair; the model behavior was already
   fail-closed, only the expected message was wrong).
2. `pytest tests/test_corpus_graph_vnext_contracts.py` — **40 passed**.
3. `pytest tests/test_corpus_research_ui.py` — **8 passed**.
4. Frontend unchanged by this correction (no API type consumed by the
   React slice changed), so no frontend re-run was required by the
   review; the last recorded frontend state remains 44/44.
5. `git diff --check` — clean.

No new dependency; no cloud, graph, source, outcome, IAM, deployment, or
live-main action. Router integration remains withheld pending re-review.
