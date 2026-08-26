# T230 ordinal-6 bounded platform-replacement amendment

Date frozen: 2026-08-26, after the primary ordinal-6 execution became
terminal and before any replacement execution, replacement result, bridge
verifier, realized-outcome read, or score.

Applies only to:

- run `20260825-foundry-t230-production-v2`;
- operation `run-slate`;
- source ordinal `6`, slate `2023-w07`;
- primary execution `atlas-minimal-c-s2023-w1-v1-rffts`; and
- frozen science image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:ed7da003c80ad47118c3c9242ec2e9047a24f489134bfdc0f534a6769d622fee`.

This is a mechanical execution-contract repair. It does not change the
corpus, slate, candidates, projections, worlds, rules, parameters, support
rank, K20, scoring law, or any science callable. Every Cloud Run execution
continues to use one task, one-way parallelism, and `maxRetries=0`.

## Why an amendment is required

The original launch request was durably published and consumed exactly once.
The primary execution entered the frozen runtime and published immutable
attempt-0 mechanics evidence, but Cloud Run then returned a literal platform
failure before a science result or terminal worker-stage receipt existed.

The primary attempt cannot be replayed. Its attempt-0 stage-start URI and
attempt-0 runtime-measurement URI already exist, and both are immutable.
Another execution at attempt 0 would collide with those receipts, conceal a
real execution, and violate the original `relaunch_allowed=false` law.

The only recoverable path is one explicitly separate attempt-1 computation,
followed by a bridge verifier and supplemental lane/panel receipts that retain
the exception.

## Frozen primary evidence

The replacement is eligible only if exact replay proves all of the following.

1. The original launch request is generation `1787709788000394`, SHA-256
   `6e62e8f41dbb526fcd49672c8436f2bf000933248721b4363bdb1a85af931415`,
   2,525 bytes, at the canonical ordinal-6 run-slate request URI. Its exact
   publication intent and completion are present, and the request records
   runtime attempt 0, `max_retries=0`, and `relaunch_allowed=false`.
2. The exact predecessor is ordinal-5 verifier-stage generation
   `1787709754573677`, SHA-256
   `6dd46009316b4ef6f0429d21287df329fefb926632e020e942998fc668ce5693`,
   2,063 bytes.
3. The attempt-0 stage-start is generation `1787709944159900`, SHA-256
   `744f5f944089eb01ad5a100574e69734eeb9008c2977968a67f513936c91013b`,
   3,593 bytes, with self-hash
   `c8b65e04fac81cd8834596cdba50ae45ee825865650c706049230f038d397548`.
   Its exact body binds ordinal 6, attempt 0, the primary execution, original
   request, predecessor, job, and frozen image.
4. The attempt-0 worker-runtime measurement is generation
   `1787710039301316`, SHA-256
   `80beaefc343166a3f06f9e1221f4f2126a76758114dc7c50a97838eb71623c0c`,
   13,520 bytes, with self-hash
   `163d5073ccc516ddc91612de9c5fd1f7d93b77a6dd6d4cfd3d126e3e7787622a`.
   It reports role `worker`, runtime attempt 0,
   `release_runtime_verified=true`, `uses_realized_outcomes=false`, and the
   frozen image.
5. The primary Cloud Run execution is terminal `Completed=False`, with
   `succeededCount=0`, `failedCount=1`, `cancelledCount=0`, and no Cloud task
   retry. Its completed message is exactly the ordinal-6 task failure with
   `exit code: 0` and `message: Internal error.` The sole task is terminal
   `Completed=False`; its `lastAttemptResult.status` is code `13` with message
   `Internal error.`
6. The primary execution envelope exactly retains job
   `atlas-minimal-c-s2023-w1-v1`, the frozen image, service account
   `817589974517-compute@developer.gserviceaccount.com`, 8 CPU, 32 GiB memory,
   one task, one-way parallelism, `maxRetries=0`, 21,600-second timeout, the
   in-memory evidence mount, source ordinal 6, attempt 0, original launch
   request, exact predecessor, execution authority, and compute release.
7. The canonical ordinal-6 science-result URI
   `slates/06-2023-w07/foundry-t230-slate-analysis-v1.json` is absent by an
   unambiguous exact-name 404 immediately before replacement authorization.
   The canonical ordinal-6 run-slate stage receipt is likewise absent. No
   bucket listing or latest alias may establish absence.
8. The failure evidence and absence checks use no lineup effects, support-rank
   observations, realized outcomes, or scores.

Any mismatch makes the primary terminal and ineligible. Memory-limit,
timeout, cancellation, signal, solver, nonzero-exit, ambiguous metadata,
present-result, present-stage, changed envelope, or changed-image failures are
not replacement eligible.

## One-worker replacement law

After an independently reviewed implementation validates all frozen evidence,
it may publish one create-once replacement intent in a new, ordinal-6-specific
namespace. That intent must bind:

- this amendment and the reviewed recovery implementation hashes;
- every identity and terminal fact above;
- the exact expected attempt-1 runtime and unchanged result URIs;
- runtime attempt `1`;
- the unchanged frozen execution authority and compute release;
- the unchanged job, image, service account, CPU, memory, task count,
  parallelism, timeout, and `maxRetries=0`; and
- `max_replacement_worker_executions=1` and
  `second_replacement_allowed=false`.

Only after the intent is durable may one separately named Cloud Run execution
run the frozen core `run-slate` implementation for source ordinal 6 and
runtime attempt 1. It must use the existing immutable image and write to the
existing deterministic create-once science-result URI. It may not run any
other slate or inspect any result before launch.

If the replacement fails for any reason, publishes an unequal object, changes
the envelope, or does not produce its exact result and attempt-1 runtime
measurement, ordinal 6 and the full panel are terminal-invalid. There is no
second replacement.

## Bridge-verifier law

A successful replacement result is not an acceptance. One separately named
bridge verifier is required before ordinal 7 may run.

The verifier authorization must bind the accepted attempt-1 worker receipt,
the exact replacement result, source ordinal 6, frozen D2, and a new
create-once verifier launch request. The verifier runs the frozen core
`verify-slate` implementation, publishes the canonical ordinal-6 acceptance,
and remains a distinct Cloud Run execution from both worker executions.

The bridge may expose a v1-compatible verifier stage only after the recovery
operator has replayed and validated the attempt-1 worker exception. This lets
the unchanged ordinal-7 predecessor boundary resume without pretending that
the ordinal-6 worker used attempt 0. The bridge does not erase or replace the
supplemental worker-recovery receipt.

## Required terminal receipts

The repaired panel is usable only if immutable receipts retain all of the
following:

- this frozen amendment and reviewed implementation identities;
- primary execution and task metadata;
- original launch-request publication proof;
- attempt-0 stage-start and runtime-measurement identities;
- exact pre-replacement result/stage absence evidence;
- create-once replacement intent;
- replacement execution metadata, attempt-1 runtime measurement, result, and
  amended worker-stage receipt;
- bridge-verifier launch proof, execution metadata, runtime measurement,
  acceptance, and stage receipt;
- an amended Lane-A ledger that discloses the primary and replacement worker
  identities at ordinal 6;
- the unchanged Lane-B terminal ledger; and
- an amended combined panel root that binds all 54 acceptances, both lane
  ledgers, the core panel release, and the ordinal-6 exception chain.

The original v1 Lane-A ledger or panel finalizer cannot, by itself, validate or
hide this exception. Downstream R6 or scoring may bind only the amended panel
root, never an unamended alias or partial receipt.

## Consequence boundary

This amendment grants only mechanical recovery authority for the exact failed
ordinal. It grants no realized-outcome, scoring, corpus-fill, retrieval,
selection, graph-write, promotion, deployment, decision, or production
authority. All such fields remain false until their later, separately frozen
gates.

No result may be used to decide whether to launch the replacement, choose the
attempt, alter the strategy, or omit another panel member. The attempt-1
result has the same scientific meaning as the absent attempt-0 result because
the immutable science image, inputs, parameters, and deterministic target are
unchanged; the mechanical exception remains permanently visible in the
accepted root.
