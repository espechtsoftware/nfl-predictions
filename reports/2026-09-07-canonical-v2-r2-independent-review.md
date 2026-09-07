# Canonical-v2 R2 independent review

Date: 2026-09-07

Reviewed commit: `a6007f2fd6cc5aca662489994a5f1d590b26f164`

Required parent: `a5e39f7362114430278e9473d7096a16ee3da061`

Disposition: **HOLD**

This was a static-first, exact-commit review. It did not modify source code,
cloud state, Neo4j, paid-entry state, or deployment state.

## Release blocker: unauthenticated Neo4j downgrade

`build_load_plan` authenticates the suite only when the caller supplies a
non-null exact-object reader. When the reader is absent, the caller-provided
completion schema selects the task and graph artifact law. The resulting v1
branch never authenticates the suite named by the terminal, never reopens the
transport-governance chain, and never reaches canonical graph-v2 replay.

The relevant seams are:

- `src/nfl_dfs/research/corpus_retrieval_neo4j.py:1289`: suite authentication
  is conditional on `read_object is not None`;
- `src/nfl_dfs/research/corpus_retrieval_neo4j.py:1327`: an unauthenticated
  completion selects the remaining evidence schemas, and only a completion
  already declaring v2 is rejected;
- `src/nfl_dfs/research/corpus_retrieval_neo4j.py:1377`: transport-governance
  authentication is conditional on the optional authenticated-suite result;
- `src/nfl_dfs/research/corpus_retrieval_neo4j.py:1387`: genuine semantic
  replay runs only after graph-v2 was selected; and
- `scripts/load_corpus_retrieval_neo4j.py:192`: the standalone loader supplies
  the reader only when at least one `--exact-object` argument was supplied.
  This applies to `validate`, `dry-run`, and `execute` alike.

The execute command can therefore construct and apply an unauthenticated
legacy plan even when its terminal names a suite-v3 authority.

### Independent reproduction

At the reviewed commit, I built and independently validated a genuine
`corpus-retrieval-suite-manifest/v3-canonical-game`. I then constructed a
coherent terminal/completion/result/graph chain under the legacy registered
schemas, rebound every dependent identity and self-hash, retained the genuine
suite-v3 and snapshot identities in the chain, and called
`build_load_plan(..., read_object=None)`.

The exact result was:

```text
ACCEPTED_DOWNGRADE
authenticated_suite_schema=corpus-retrieval-suite-manifest/v3-canonical-game
accepted_completion_schema=corpus-retrieval-batch-completion/v1
accepted_task_schema=corpus-retrieval-task-result/v1
accepted_graph_schema=corpus-retrieval-graph-projection/v1
plan_nodes=105 plan_relationships=106
```

The existing downgrade test keeps the suite reader present while changing
only the completion schema. It therefore proves the authenticated branch but
does not cover a coherently repackaged chain that omits the reader.

### Narrow repair contract

1. Make legacy evidence handling an explicit typed mode or authority rather
   than inferring it from the caller-provided completion object.
2. Prohibit any unauthenticated plan from execute/apply. The safest boundary
   is for execute to require exact suite/snapshot objects and suite-first
   authentication unconditionally.
3. Derive the completion/result/graph laws and their canonical paths only from
   the reopened suite for every canonical execution.
4. Add an adversarial full-repackage-without-reader test and a CLI execute test
   proving Neo4j contact cannot occur on that path.
5. If historical replay compatibility requires legacy validate/dry-run,
   expose it as a separately named, non-executable mode.

## Other reviewed surfaces

No additional release blocker was found in the assigned surfaces:

- The paid catalog accepts `proj_p50`, `proj_p90`, and `proj_std` only as a
  complete set, requires finite values and positive sigma, requires p50 not to
  exceed p90, and binds the distribution values into the projection-batch
  identity.
- Paid generation rejects a missing or nonpositive sigma before confidence
  ranking. It rejects simulation requests using p50/p90 before generation,
  while deterministic MILP genuinely consumes the requested certified point,
  p50, or p90 objective.
- When canonical graph-v2 is selected with authenticated evidence, the loader
  calls the public retrieval validator with `replay=True` and compares the
  reconstructed authority byte-for-byte.
- Retrieval compatibility tests passed.
- Canonical-game v7 inventory regeneration exactly reproduced:
  - inventory SHA-256
    `de290be1ef2f65014919bc57b775e4de13d1a4153d8bd9221bc88847e9e44c25`;
  - source-set SHA-256
    `93da1da1473772733a5eff3cf1d30d6fcd83eba3e533f58c2e9390b5ddb64b37`;
  - rule-universe SHA-256
    `0de128a919dff6d39283ba1ee5390110fbf3eb5d11a6d0348dc43307b58289b4`;
  - classified-input SHA-256
    `28173788062fdbad85cf77d33ee35cea06ecc391b31fb3ddf7c49f12a18af3f7`;
  - 65 rules, 134 classified inputs, 290 direct input-read sites, and 21
    frozen sources.

## Validation

After explicit clearance of the shared serial-test lane, one pytest process
ran the focused suites for paid-v3, live multiseed, effective-policy inventory,
retrieval engine, and Neo4j retrieval. Result: **153 passed, zero failed**.
The lane was released immediately afterward. `git diff --check` passed and the
review worktree was otherwise clean.

A delegated semantic reviewer independently identified the same downgrade
boundary, but its final response was suppressed by an automated content
filter. The reproduction and disposition above are independently established
by this reviewer and do not depend on that response.
