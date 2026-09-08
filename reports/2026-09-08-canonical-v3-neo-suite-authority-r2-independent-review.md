# Canonical-v3 Neo4j suite-authority R2 independent review

Date: 2026-09-08

Reviewed commit: `9ec524344f47483e59ad15adbca6aec824e506d8`

Required parent: `0b9f266ea3476da3b48bfe01bc89a765be943c5e`

Reviewed branch: `origin/codex/canonical-v3-neo-authority-r2`

Independent-review branch:
`codex/canonical-v3-neo-authority-r2-independent`

Disposition: **PASS**

## Decision

The exact candidate closes the assigned Neo4j execution-authority gap. I found
no P0 or P1 defect in the reviewed boundary.

Only an exact-object-authenticated
`corpus-retrieval-suite-manifest/v3-canonical-game` plan can reach a governed
Neo4j backend. Suite v1/v2 and explicitly legacy evidence remain usable for
compatibility validation, but cannot acquire execution authority. The repair
does not change lineup generation, admission, scoring, selection, production
defaults, experiment policy, or paid-entry behavior.

This is a code-review PASS only. It does not itself authorize a graph
connection, graph load, deployment, cloud action, scoring run, policy change,
or paid action.

## Independent findings

### 1. Exact canonical-v3 authority is enforced twice

`corpus_retrieval_neo4j.py` now defines one executable suite schema:

```text
corpus-retrieval-suite-manifest/v3-canonical-game
```

The load-plan builder first reopens and authenticates the suite through the
generation-pinned exact-object reader. Immediately after that authentication,
it rejects suite v1 or v2 before accepting the completion, task-result, graph,
or extension evidence. This ordering prevents a caller-supplied downstream
schema from selecting a weaker evidence law.

The independent `require_executable_plan` boundary repeats the exact-v3 check,
then recomputes the complete plan hash and verifies that the retained task
authority names the same exact suite identity. A caller therefore cannot turn
a legacy or altered plan into an executable plan merely by changing the enum,
schema string, or summary fields.

### 2. Legacy compatibility remains non-executable

The typed `LEGACY_VALIDATION_ONLY` mode remains available to the explicitly
named `validate-legacy` and `dry-run-legacy` paths. It cannot pass
`require_executable_plan`, `apply_load_plan`, the standalone loader's execute
path, the live driver adapter, or the governed transport operations.

The plan summary now reports `execution_authorized=true` only when all three
surface facts agree: authenticated-suite mode, a retained suite identity, and
the exact canonical-game v3 schema. That field is descriptive; the stronger
content and task-authority checks still run at execution.

### 3. Every governed operation is covered before graph contact

The shared `require_executable_operation_bundle` guard validates the relevant
plan set for all eleven registered operation names:

- schema bootstrap;
- task-0 load and receipt recovery;
- one parametric-task load and receipt recovery;
- full parametric-suite load;
- strategy-registry load, receipt recovery, and query;
- suite finish; and
- task-0 or complete-suite query smoke.

Task-scoped operations authenticate the retrieval plan and the selected
extension when one is used. `load-suite` authenticates retrieval plus all 54
parametric plans before task 0 can contact the graph. `finish-suite` and the
complete-suite query smoke authenticate retrieval, all 54 parametric plans,
and the strategy-registry plan before any receipt or backend work. All
extensions must retain the retrieval plan's exact suite identity and schema.

The direct operation functions call this guard before their first storage or
graph access. The live transport CLI validates the exact GCS manifest and
release binding, then runs the same operation guard before
`open_bound_backend`; consequently driver construction and
`verify_connectivity()` cannot occur for a downgraded plan. The separate
standalone loader calls `require_executable_plan` before importing the Neo4j
driver, and `Neo4jDriverBackend.apply` repeats the plan guard before opening a
session.

The raw adapter remains intentionally lower-level and must continue to be
reached only through these governed entry points. Any future live entry point
must use the same pre-open operation guard; the two current live entry points
are covered.

### 4. Full-suite and extension behavior is fail-closed

The complete-suite preflight happens before the list comprehension that loads
individual tasks, so a downgraded late task cannot create a partially loaded
suite. Retrieval analytics, parametric, population, and strategy-registry
appenders preserve the parent plan's typed mode, exact suite identity, schema,
and recomputed plan hash. A registry built on legacy validation evidence stays
legacy and is rejected rather than being upgraded by the extension.

### 5. Scope is clean

The candidate is a direct child of the required parent. Its executable changes
are confined to the Neo4j projection/transport modules and the live transport
CLI; the remaining changes are focused tests and documentation. The diff
contains no generation, admission, selector, score, money-policy, or default
change.

## Independent validation

A process census immediately before the test found no active `python -m
pytest` process. One isolated-source process then ran:

```text
PYTHONPATH=$PWD/src:$PWD \
  /home/erich/projects/nfl-predictions/.venv/bin/python -m pytest -q \
  tests/test_corpus_retrieval_neo4j.py \
  tests/test_corpus_neo4j_transport.py \
  tests/test_corpus_strategy_registry_release.py
```

Result: **104/104 passed, exit 0**. No competing pytest appeared during this
run.

Independent static validation also passed:

- `py_compile` for all six changed Python source/test files;
- exact parent relationship and changed-path inspection; and
- `git diff --check` for the reviewed commit.

Ruff is not installed in the independent review environment, so I did not
count the author's Ruff result as independent evidence. The missing optional
lint executable is not a release blocker given the successful compilation,
focused regression, and clean diff.

## Safety and state

This review made no graph connection, Neo4j mutation, GCS read or write,
cloud-provider call, deployment, scoring run, simulation, paid action, or
production-policy change. No outcome was opened.

## Release recommendation

**PASS for selective integration of exact commit
`9ec524344f47483e59ad15adbca6aec824e506d8`.** Preserve the default-off graph
boundary. Any later graph load still requires its own exact manifest, launch
gate, independent state census, and explicit release decision.
