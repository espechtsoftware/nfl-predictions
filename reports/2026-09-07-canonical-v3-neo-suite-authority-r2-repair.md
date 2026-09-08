# Canonical v3 Neo4j suite-authority R2 repair

Date: 2026-09-07

Branch: `codex/canonical-v3-neo-authority-r2`

Exact parent: `0b9f266ea3476da3b48bfe01bc89a765be943c5e`

Status: **PASS; ready for independent review**

## Decision boundary

The policy adjudication for this repair is exact and intentionally narrow:

- only `corpus-retrieval-suite-manifest/v3-canonical-game` can grant graph
  execution authority;
- suite v1 and v2 remain available for explicit inspection and validation-only
  dry runs, but cannot contact Neo4j;
- no graph connection, graph load, deployment, cloud operation, scoring run,
  paid action, or policy activation is authorized by this work.

## Repairs implemented

1. The graph planner now names one executable suite schema. Authenticated v1
   and v2 suite objects are rejected immediately after suite-first exact-object
   authentication, before any derived completion, result, or graph evidence is
   accepted. The independent executable-plan guard repeats the exact v3 check.
2. The plan summary reports execution authority only when the typed mode,
   retained exact suite identity, and exact canonical-game v3 schema all agree.
3. A public operation-level transport guard validates every plan used by a
   governed operation before storage or graph work at that operation boundary.
   Task operations validate retrieval plus the selected extension. Whole-suite
   operations validate all 54 parametric plans up front; finish and complete
   query-smoke also validate the strategy-registry plan. Every extension must
   retain the retrieval plan's exact suite identity and schema.
4. All governed public graph operations call the guard, including the three
   previously uncovered reader/terminal boundaries:
   `query_strategy_registry`, `finish_suite`, and `query_smoke`.
5. The live transport CLI calls the same operation guard after exact manifest
   validation and release binding but before `open_bound_backend`; therefore
   the driver's constructor and `verify_connectivity()` cannot run for a
   downgraded plan.

## Adversarial coverage added

- Valid, exact suite-v1 and suite-v2 manifests rebound to a genuine retained
  terminal are authenticated and then refused as validation-only.
- Core apply and the standalone loader CLI reject a plan whose claimed suite
  schema is v1/v2 before a statement callback or driver import can occur.
- Every governed transport operation is exercised with the relevant retrieval,
  parametric, or registry plan downgraded and with storage/graph sentinels that
  raise on any contact. Both task-0 and complete-suite query-smoke modes are
  included.
- Every corresponding live CLI route is exercised and proves
  `open_bound_backend` and the operation callback remain untouched.
- The live driver adapter rejects v1/v2 schema claims before opening a session.
- Retrieval-analytics, parametric, population, and strategy-registry extensions
  retain the exact typed canonical-v3 authority. A legacy registry extension
  remains validation-only rather than acquiring authority by extension.

## Validation

Completed static checks:

- explicit-source `py_compile` for all six changed Python files: PASS;
- Ruff fatal/import checks (`E9,F63,F7,F82,I001`): PASS;
- `git diff --check`: PASS.

Two preliminary starts are explicitly excluded from evidence:

- PID `2632305` omitted the isolated `PYTHONPATH`, resolved source from the
  production worktree, and exited during collection with three import errors;
  zero tests ran.
- Corrected PID `2633239` used `PYTHONPATH=$PWD/src:$PWD`, but a higher-priority
  PREREG-074 R18 pytest process had entered the shared lane three seconds
  earlier. The coordinator terminated this process with exit 143 before a
  terminal result. It is an external lane collision, not product evidence.

After the higher-priority lane cleared, a fresh process census found no active
pytest. PID `2640761` then ran the three required modules together in one
isolated-source process with `PYTHONPATH=$PWD/src:$PWD`:

1. `tests/test_corpus_retrieval_neo4j.py`
2. `tests/test_corpus_neo4j_transport.py`
3. `tests/test_corpus_strategy_registry_release.py`

Result: **104/104 passed, exit 0** (41 retrieval, 58 transport, 5 registry
release). The serial pytest lane was released immediately afterward.

## Current disposition

**PASS for independent review.** The bounded repair and focused regression are
complete. This PASS does not authorize merge, graph connection/load,
deployment, cloud execution, scoring, paid action, or production-policy
change; those remain separate decisions.
