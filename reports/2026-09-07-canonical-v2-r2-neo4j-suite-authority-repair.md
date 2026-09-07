# Canonical-v2 R2 Neo4j suite-authority repair

Date: 2026-09-07

Disposition: **review candidate only**

Parent commit:
`3c51fd3fb5cf6f3c52dfc9f1762661b94e1a67c9`

Branch: `codex/canonical-v3-neo-repair`

This narrow repair closes the unauthenticated Neo4j downgrade described in
`reports/2026-09-07-canonical-v2-r2-independent-review.md`. It does not change
lineup generation, scoring, admission, selection, production defaults, paid
entries, or the default-off Neo4j boundary.

## Repaired contract

- Load-plan construction now requires one explicit typed evidence authority:
  `authenticated-suite` or `legacy-validation-only`.
- An authenticated plan can be constructed only with a non-null exact-object
  reader. The suite is reopened first and determines the permitted completion,
  result, graph, and canonical paths before caller-supplied evidence is
  accepted.
- The authenticated suite identity and schema are bound into the plan SHA and
  survive every supported plan-extension path.
- Legacy v1 evidence remains inspectable only through separately named
  `validate-legacy` and `dry-run-legacy` CLI commands. Such a plan cannot be
  applied.
- Ordinary `validate`, `dry-run`, and `execute` require `--exact-object`
  bodies. Missing downstream objects and content that disagrees with the exact
  identity fail during suite-first authentication.
- Core apply, standalone execute, governed schema bootstrap, governed
  load/recovery, registry load/recovery, and the live driver apply boundary all
  reject a validation-only or altered authenticated plan before their write
  callback can run.

## Adversarial coverage

The added tests:

1. start from a genuine suite-v3 evidence chain;
2. coherently repackage its completion, result, graph, dependent identities,
   self-hashes, inventory, and terminal as registered legacy v1 evidence;
3. omit the reader and construct only the explicitly labeled validation plan;
4. prove neither core apply nor standalone execute can invoke graph contact;
5. prove an authenticated plan whose suite generation is changed cannot invoke
   its statement callback;
6. prove CLI execute rejects no exact objects, an incomplete exact-object set,
   and suite bytes that mismatch the retained identity before `_execute`; and
7. prove governed transport rejects a downgraded plan before accessing even an
   injected graph backend.

The governed-transport fixture was also corrected to use one genuine
canonical-v3 exact-object chain. The prior placeholder v1 fixture could not
authenticate under the already-existing suite-first transport caller. Its
immutable evidence and validated plan are cached once per module; each test
still receives fresh copied object-store state, so receipt mutations remain
isolated.

## Validation

The focused governed transport module ran with the isolated worktree first on
the import path:

```text
PYTHONPATH=$PWD/src:$PWD \
  /home/erich/projects/nfl-predictions/.venv/bin/python -m pytest \
  -q -p no:cacheprovider tests/test_corpus_neo4j_transport.py

33 passed, 0 failed
```

The process reached 100% and exited zero with no competing pytest observed
during the run. Two earlier starts were terminated when a lab pytest
unexpectedly reacquired the shared serial lane; they are discarded and are not
counted as evidence.

Static checks also pass:

- compilation of all six changed Python source/test files with the isolated
  source tree first on `PYTHONPATH`;
- Ruff fatal/import checks `E9,F63,F7,F82,I001` on those files; and
- `git diff --check`.

The retrieval and strategy-registry full-module regressions remain unrun by
explicit coordinator direction while higher-priority score-path reviews own
the serial pytest lane. That remaining validation must be considered during
independent review; this report does not turn the focused pass into a broader
release claim.

## State and authority

No Neo4j, cloud, paid-entry, deployment, scoring, or production-policy state
was read or mutated. This candidate grants no merge, build, deployment, graph
load, paid-entry, or release authorization.
