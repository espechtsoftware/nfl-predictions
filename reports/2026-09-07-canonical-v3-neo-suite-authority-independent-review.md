# Canonical-v3 Neo4j suite-authority independent review

Date: 2026-09-07

Reviewed commit: `0b9f266ea3476da3b48bfe01bc89a765be943c5e`

Required parent: `3c51fd3fb5cf6f3c52dfc9f1762661b94e1a67c9`

Disposition: **HOLD**

This was an exact-commit, static-first review. It did not run pytest because
PREREG-074 and experiment-081 recovery reviews own the shared serial test
lane. It did not connect to or mutate Neo4j, GCS, Cloud Run, Cloud Build,
paid-entry state, lineup generation, scoring, selection, or production
policy.

## What the candidate fixes correctly

The repair closes the original unauthenticated write path at the core and
standalone-loader boundaries:

- `build_load_plan` now requires an exact `Neo4jEvidenceMode` value. An
  `authenticated-suite` plan requires a non-null exact-object reader, while a
  `legacy-validation-only` plan rejects one.
- Suite-first authentication selects the completion, task-result, and graph
  schemas and paths before caller-supplied derived evidence is accepted.
- Authenticated suite identity and suite schema are included in the plan-hash
  body and copied by `append_load_plan`, so the existing retrieval-analytics,
  parametric, phenotype, and strategy-registry extension paths retain them.
- Core `apply_load_plan`, standalone `_execute`, governed schema bootstrap,
  governed load/recovery, strategy-registry load/recovery, and
  `Neo4jDriverBackend.apply` invoke the executable-plan guard before their own
  statement or graph callbacks.
- The standalone CLI exposes legacy validation through separately named
  `validate-legacy` and `dry-run-legacy` commands, and ordinary `validate`,
  `dry-run`, and `execute` require exact-object inputs.
- Authenticated identity/schema changes invalidate the recomputed plan hash.
  The legacy plan-hash byte shape is deliberately retained for validation
  compatibility.

No lineup generation, scoring, candidate admission, selection, or live-money
source is changed by this commit.

## P0 release blocker: not every governed graph-contact path checks authority

The candidate's own contract says only a suite-first authenticated plan may
contact Neo4j. That invariant is not yet enforced across the whole governed
transport:

1. `query_strategy_registry` in
   `src/nfl_dfs/research/corpus_neo4j_transport.py:2511` has no executable-plan
   guard. When a query receipt is absent it reaches
   `graph.run_read_only_query` through `run_read_only_traversal_receipt` at
   line 2556.
2. `finish_suite` at line 2723 has no executable-plan guard and reaches
   `graph.component`, `graph.suite_census`, and `graph.census` beginning at
   line 2801.
3. `query_smoke` at line 2845 has no executable-plan guard and reaches
   `graph.query_smoke` at line 2858.
4. The live CLI helper `_live` in
   `scripts/run_corpus_neo4j_transport.py:280` validates the manifest but then
   calls `open_bound_backend` at line 287 before the action-level guard runs.
   `Neo4jDriverBackend.__init__` constructs the driver and calls
   `verify_connectivity`, so even the newly guarded mutation operations make a
   real graph contact before their authority check.

This is independently visible without executing code: replacing a validated
bundle's retrieval plan with a `LEGACY_VALIDATION_ONLY` plan leaves each of
the three unguarded functions able to invoke its graph backend. The added
adversarial test checks only `bootstrap_schema` and `load_plan`, so it cannot
detect these paths.

### Narrow repair

- Add one operation-aware, fail-closed bundle-plan authority check that runs
  in `_live` after exact manifest validation and before `open_bound_backend`.
  It should cover the retrieval plan, the requested parametric plan or all 54
  plans for suite operations, and the derived strategy-registry plan where
  applicable.
- Also guard `query_strategy_registry`, `finish_suite`, and `query_smoke` at
  their public function boundaries. Defense in depth matters because tests
  and future callers can inject a backend without using `_live`.
- Add `NoGraphContact` coverage for every governed operation and monkeypatch
  `open_bound_backend` in a live-CLI test to prove it is never called for a
  validation-only or authority-altered plan.

No graph connection, schema statement, read query, census, or write callback
should occur before this check passes.

## P1 specification ambiguity: exact suite-v1/v2 remain executable

`_AUTHENTICATED_SUITE_SCHEMAS` includes suite-manifest v1, v2, and v3. An
exact-object-authenticated suite-v1 or suite-v2 chain can therefore receive
`AUTHENTICATED_SUITE` mode and pass `require_executable_plan`. This conflicts
with an ordinary reading of the candidate report's statement that “legacy v1
evidence remains inspectable only” through validation-only commands.

The release contract must make one of these two meanings explicit before the
HOLD clears:

- If **legacy means any suite-v1/v2 schema**, executable authority must be
  limited to `corpus-retrieval-suite-manifest/v3-canonical-game`; add exact
  authenticated-v1 and authenticated-v2 negative tests.
- If **legacy means only the explicitly unauthenticated
  `LEGACY_VALIDATION_ONLY` mode**, retain the three registered suite schemas
  but amend the report and CLI help so it says exact-object-authenticated
  suite-v1/v2 remain executable. Add positive tests for those two cases so
  the compatibility decision cannot drift silently.

The current code chooses the second behavior but the written release claim
sounds like the first. This review does not choose policy by inference.

## Additional test coverage required after repair

Once the shared pytest lane is available, the repair should run serially with
the isolated worktree first on `PYTHONPATH`:

1. `tests/test_corpus_retrieval_neo4j.py`;
2. `tests/test_corpus_neo4j_transport.py`; and
3. `tests/test_corpus_strategy_registry_release.py`.

In addition to the graph-contact negatives above, assertions should prove
that suite identity, suite schema, evidence mode, and the resulting plan hash
survive each supported extension and that changing any one of them fails
before graph contact.

## Static validation

- Python bytecode compilation passed for the three changed source files and
  three changed test files with the isolated source tree first on
  `PYTHONPATH`.
- Ruff fatal/import checks passed using the available lab Ruff installation.
- `git diff --check 3c51fd3f..0b9f266e` passed.
- Call-site census found no unmodified production constructor of
  `Neo4jLoadPlan`; supported extensions route through `append_load_plan`.

Pytest was intentionally not run and no author test result was elevated into
independent evidence.

## Clearance condition

Keep merge, graph load, deployment, and release on HOLD until the P0 paths are
guarded before any backend connection/contact, the suite-v1/v2 meaning is
explicitly adjudicated, the adversarial coverage is expanded, and the three
focused modules pass serially from the repaired exact commit.
