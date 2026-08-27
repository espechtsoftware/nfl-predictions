# R6 full-union fixed-job recovery amendment

**Date:** 2026-08-26  
**Run:** `20260826-foundry-v12-r6-full-union-realized-v2`  
**Scope:** one failed supply container, one already-successful fixed BigQuery
job, and the minimum recovery needed to finish the frozen eight-strategy
historical grade, including T230.

## Decision

Do not rerun the panel, compile, smoke, ordinary supply operation, or outcome
query. Recover only the already-completed fixed BigQuery job through a new
default-off executable whose BigQuery boundary can look up that exact job but
cannot submit a query. Preserve the original failed supply execution and its
evidence. Run recovery once in a distinct Cloud Run stage using one immutable
repair image; then restore the registered job to the original immutable image,
grade the frozen panel, finish the strict lease release, and run the bounded
score reporter.

This is an execution-boundary repair, not a science change. It does not alter
the 54-slate panel, lineup books, strategies, thresholds, outcome keys, SQL,
query parameters, source snapshot time, table identities, fixed job ID, or
grading laws.

## Why recovery is required

The original supply execution
`atlas-minimal-c-s2023-w1-v1-cc8xf` is terminal-failed:

- execution UID `9e1edce6-10e9-4e32-bc01-8178e8f9217f`;
- `Completed=False`, one failed task, zero succeeded/running tasks;
- exit code 1, one task, parallelism one and `maxRetries=0`;
- terminal envelope SHA-256
  `d05efa4a4f5881f35f78809d562a719c0bde4be3449de69d34f30bfd8b9727c1`;
- original reviewed code
  `16356b246817ea4777426b4e8a8b82e0737210df`;
- original immutable image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:8be07290476cb88a584eb20adacc020598255855c9f305102bf3fe8f5f089de8`.

The execution published its create-once read attempt and submitted the sole
fixed-ID query. BigQuery completed the job successfully. The container then
failed before calling `job.result()` because the SDK reconstructed the frozen
TIMESTAMP parameter as a timezone-aware `datetime`/space-formatted API value,
while the runner compared that API representation directly with the frozen
ISO string containing `T`. This was a representation mismatch at the SDK
boundary. It was not a query, data, panel, or strategy failure.

The repair converts registered TIMESTAMP values to timezone-aware UTC
`datetime` objects only when constructing SDK query parameters. The immutable
registered `QuerySpec`, canonical parameter payload and
`parameters_sha256` remain unchanged. Full offline
`QueryJob.from_api_repr` tests cover fractional seconds and reject a
one-microsecond substitution, malformed strings, naive timestamps and wrong
types.

## Immutable recovery inputs

### Existing read attempt

- URI:
  `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-full-union-realized/20260826-foundry-v12-r6-full-union-realized-v2/read-attempt.json`
- generation: `1787788728079549`
- bytes: `4804`
- object SHA-256:
  `a5da1cb1000d1f4c4084e02598127724c77342a235e691f8ef13954fac9db2c4`
- body `attempt_sha256`:
  `ee6438c401fc62f3821ea3509b24be23e36f2aaf47898c123626f04f65a010ce`
- body `query_contract_sha256`:
  `bac121a31c1a0e8a29ebb16432f83dd73ac97b006f6c40aacc38d0ba1a7b066c`
- parameter payload SHA-256:
  `159e72d718e387f77c858aefc83a044bab1305a481b453da8949dafc5c7e78d7`
- table-receipt-set SHA-256:
  `f6fac5ad40ae71438f13207fec10c850a0e8e9e9555d789b92a18b83ac1cf245`
- source snapshot:
  `2026-08-26T23:58:47.451523+00:00`

The object SHA and the body's self-hash are deliberately separate identities
and must not be interchanged.

### Existing fixed query job

- project: `nfl-predictions-503414`
- location: `US`
- ID:
  `r6_full_union_realized_20260826_foundry_v12_r6_full_union_realized_v2_57844386a3da86ddf05f8b3e6b19ae19c7327afcfc1057647b210e58caec2467`
- state: `DONE`
- error result: null
- cache hit: false
- legacy SQL: false
- query cache requested: false
- creation/start/end milliseconds:
  `1787788729086` / `1787788729423` / `1787788730727`
- total bytes processed: `8689314`
- SQL SHA-256:
  `03b5028dadbe4d92621103e2ccd6dcfe91e8e36fc351cf671f37e309951752cb`

These are metadata-only observations. No result row was opened while
diagnosing the failure or authoring this amendment.

### Original frozen authorities

- panel generation `1787756181440564`, bytes `89879`, SHA-256
  `57844386a3da86ddf05f8b3e6b19ae19c7327afcfc1057647b210e58caec2467`;
- actual-root smoke generation `1787780169874584`, bytes `67127`, SHA-256
  `7e2db3d420d1e5027a566455a8614b11e941a478215ce34909b959758db9ac4a`;
- live lease generation `1787782649649091`, bytes `388`, SHA-256
  `c85694a96ece0923ed470820cb704f6f9e1b4f38cdb2bf1598b8cf276600e867`;
- compile receipt generation `1787776558889920` and the unchanged SQL hash
  above.

The lease stays live through recovery and grading. Recovery resolves it using
the original run/job/code/image tuple and can never acquire or replace it.

## Recovery executable law

The recovery implementation is a separate executable, not a mode or fallback
inside the ordinary supply runner. Its source and tested execution path must
contain no query-submission operation. In particular:

1. It is default-off and requires an explicit recovery gate plus the exact
   single-task Cloud Run envelope (`TASK_INDEX=0`, `TASK_COUNT=1`,
   `TASK_ATTEMPT=0`).
2. It distinguishes the original code/image used by the frozen smoke,
   read-attempt and lease from the repair code/image currently executing.
3. Before constructing BigQuery, it generation-reopens the exact read attempt,
   proves the expected identity/self-hash/query contract, proves the four
   downstream supply objects are absent, and publishes or exactly reopens one
   create-only recovery intent.
4. Its sole query callback calls `get_job` for the exact fixed ID and location.
   If the job is absent, nonterminal, failed, cached, or differs in SQL or any
   parameter, it fails closed. It never calls `client.query`,
   `query_and_wait`, or a create helper, and never substitutes a new job ID.
5. After exact job validation it may call `job.result(job_retry=None)` once.
   The existing pure supplier then validates rows against the frozen outcome
   keys and publishes the standard query-evidence, realized-source,
   outcome-snapshot and completion objects create-once.
6. Standard output contains only a compact receipt. It never prints score or
   source rows.
7. It publishes a create-only recovery receipt binding the failed execution,
   recovery intent/runtime/execution, exact job receipt, zero submissions and
   all five standard supply artifact identities.

An absent or drifting fixed job is a terminal recovery failure; it never falls
back to ordinary supply. A failed recovery execution is not automatically
retried and would require a separate reviewed amendment.

## Controller and continuation law

The chain exposes `recover-supply` only as an explicit operator command. The
normal `run` sequence remains compile, smoke, ordinary supply, grade and
finish, so an unrelated future run cannot enter this repair path.

Before launch the controller must verify the exact original terminal-failure
envelope, exact local launch intent, live original lease, read-attempt
identity, fixed-job terminal metadata and absence of all downstream supply
objects. It writes recovery state beneath `stages/supply-recovery-01/` and
never changes `stages/supply/`. The one registered Cloud Run job is updated to
the immutable repair image, cleared to the same isolated one-task shape,
launched once with an exact token/argv/env binding, and monitored to a
terminal-success envelope. Ambiguous launch recovery may claim only the one
execution matching that exact binding; it cannot blind-launch again.

After recovery, the controller resolves the five standard supply objects and
recovery receipt, restores the registered job to the original immutable image,
and validates that restoration. `grade` accepts a prior supply only if either
the original supply terminal is genuinely successful or the distinct recovery
terminal and recovery receipt are both exact and successful. Mere presence of
the known failed terminal file is insufficient.

## Acceptance and score path

Before building or running recovery:

- focused recovery, ordinary-supply, pure-supply, timestamp, chain and build
  contract tests pass serially;
- source/static tests prove the recovery executable has no submission path;
- all changed Python and shell files compile/parse;
- `git diff --check` is clean;
- the exact commit is pushed and Cloud Build tests that detached commit before
  producing an immutable digest.

After the single recovery execution succeeds:

1. resolve and validate query evidence, realized source, outcome snapshot and
   supply completion;
2. restore the original image and run `grade` once across all 54 frozen
   slates and all eight frozen strategies, including T230;
3. resolve the grade root/completion, materialize strict evidence and release
   the exact lease generation;
4. invoke the read-only bounded score reporter against the exact grade
   completion and report its authoritative historical score table;
5. update `HANDOFF.md` with the repair commit/image/build/execution, artifact
   generations, grade execution, lease-release receipt and reported score
   artifact.

No recovery result licenses production selection changes by itself. The first
read is comparative historical evidence for the already-frozen strategies and
the starting point for the faster Foundry experiment loop.
