# T230 Production Transport Amendment

Date: 2026-08-25
Status: implementation candidate; no production launch authority

## Purpose

This amendment adds the production transport seam for the already frozen,
outcome-blind T230 panel. It does not change prospective k20, the G0 panel,
the 54 accepted source members, the four retrieval laws, the 270/54 support
gates, or any realized-outcome boundary.

The production prefix is now literal:

`gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/t230/20260825-foundry-t230-production-v1/`

The only licensed execution layout is two concurrent lanes, sequential within
each lane: source ordinals 0–27 on
`atlas-minimal-c-s2023-w1-v1` and ordinals 28–53 on
`atlas-cbc-32g-full-2023-w8-v1`. Every worker and independent verifier is a
fresh one-task Cloud Run execution; the finalizer is a third, distinct role.
All jobs retain `maxRetries=0`.

Here, worker/verifier/finalizer distinctness is proved by role-specific core
receipts and globally unique Cloud execution/process identities. The launcher
does not claim separate IAM principals: it accepts one explicitly supplied
service account and performs no IAM census or policy mutation.

## Superseded evidence

Any earlier T230 code-source hash, image digest, image-evidence object,
synthetic test clearance, or deployment clearance produced before this
amendment is superseded for production launch. The worker and verifier
*declarative* implementation hashes remain unchanged, but their measured file
and critical-callable evidence must be regenerated because the execution file
changed. The new structural finalizer implementation hash is:

`70f546436f7df6b5733689926fbcbd8d9bfaea08750f062931b6b6410a313cf0`

The G0 lock schema is now the portable v2 form. Live reads still enforce an
absolute no-follow regular file, current-owner control, safe mode, link count,
and stable metadata/content. The reviewed lock retains the stable repository-
relative path plus exact SHA-256 and byte count, not a host checkout root, UID,
or mode. Thus the same reviewed bytes can replay in the operator checkout,
Cloud Build checkout, and root-owned image without weakening the live secure-
file gate. A production source commit must contain that reviewed lock, while
the three exact raw G0 receipts must be materialized at their corresponding
relative paths and replay against it.

## Production release sequence

1. Finish, publish, review, and commit the real G0 panel/authority lock. Until
   that upstream seal exists, this transport is only an implementation
   candidate.
2. Finalize the candidate implementation and reviewed G0 lock before starting
   the two-phase build. The `candidate` phase builds and pushes one uniquely
   tagged image from the exact detached commit, resolves immutable digest D,
   and never publishes image evidence or the transport contract.
3. Run D once as the fixed ordinal-zero Rule-1 smoke on the fixed 8-CPU/32-GiB
   Cloud Run job with retry zero. It executes exact member reconstruction, the
   support census, all four T230 suite laws, and the support-switch path through
   the same no-knob helper used by the production worker. The existing Gate-5
   census alone is insufficient. Its compact receipt, strict complete GNU
   `time -v` bytes, and successful terminal Cloud execution projection are
   separate create-once, generation-pinned mechanics objects. They bind the
   exact G0 panel identity, source commit, D, task 0/attempt 0/count 1, process
   identity, service account, 8/32 resource envelope, timeout, and runtime
   binding hash while retaining no science payload or selector effect.
   These objects and their journals live only below the frozen, noncanonical
   `.../t230-prefreeze/20260825-foundry-t230-production-v1/` namespace; the
   canonical T230 production prefix remains untouched until release gate pass.
   Before `gcloud` execution, candidate mode journals one fixed launch claim
   binding D, G0, commit, service account and the retry-zero envelope. Only the
   caller whose create returned `target_created=true` may launch; a retained
   claim without a complete smoke is terminal and cannot be relaunched.
4. If reality contact requires any byte change, freeze a new source commit and
   start a new candidate run. Never rebuild or substitute D after a passing
   smoke. An incomplete smoke receipt/time transaction is terminal for this run
   and cannot license a science relaunch.
5. Build from an exact detached checkout containing a real `.git` database and
   the three exact raw G0 receipts at their literal paths. Before any image
   push, run the tracked-lock preflight that semantically replays those raw
   bytes, both lane terminals, and the published panel through the committed
   G0 authority lock. A mere file-presence or file-hash check is insufficient.
6. Invoke the separate `release` phase with that exact D. This phase contains
   no Docker build or push. Before generating evidence, it exact-reopens the
   launch claim, smoke receipt, raw timing, execution projection, and each
   publication intent/completion; reconstructs the prefreeze release gate;
   compares the source commit, D and G0 identity; and requires the frozen
   numeric envelope.
7. Only after that gate passes, run D to generate image evidence E, publish E
   create-once, retain its exact URI/generation/SHA-256/byte identity, and
   exact-reopen E's intent/target/completion journal before contract
   publication.
8. Build and publish the transport contract binding the exact source snapshot,
   D, E, prefreeze release gate, prefix, lanes, mount law, and numeric gate.
   Contract publication and every later bootstrap exact-reopen all four Rule-1
   mechanics objects and require byte-identical gate reconstruction.
9. Bootstrap the controller by resolving only the fixed contract URI, pinning
   its generation, structurally validating it, and deriving E's exact identity
   from that contract. The stronger baked-snapshot comparison occurs only
   inside D, where the real checkout and `/opt` snapshot exist.
   Each execution generation-pins E, materializes it as a root-owned regular
   `0400` file at the literal `/etc/nfl-dfs` path, and runs the core process as
   root so no ownership relaxation or symlink projection is needed.
10. Configure each reused job to D and immediately exact-describe it. A fixed,
   create-once job-config receipt binds image, service account, 8 CPU, 32 GiB,
   one task, parallelism one, retry zero, six-hour timeout, and the in-memory
   `/etc/nfl-dfs` mount. Every launch re-describes the live job and must replay
   that same receipt before it can consume launch permission.
11. Run the ordinal-zero mechanics benchmark through the sole timed command,
   `bash scripts/run_t230_benchmark_worker_v1.sh`. Scale-out remains forbidden
   until the complete whitelisted GNU `time -v` object, contract, D, E,
   source-zero launch request and stage start,
   worker stage receipt, result/runtime identities, parser, benchmark, and
   compute release replay exactly.
12. Raw-ready and terminal-abort compete for one shared create-once benchmark
   disposition URI. Raw-ready publishes that decision first, binding the
   expected time-v URI/content hash/byte count and retaining the already
   strict-parsed mechanics bytes, and only then may publish the raw `time -v`
   object. A crash in that narrow window deterministically republishes the
   exact retained bytes without science. It can resume benchmark/compute
   publications structurally without relaunching science. If raw time is
   absent, first exact-describe the bound Cloud execution and require a
   terminal Completed condition. A strict mechanics-only create-once terminal
   execution projection binds that condition, D, resources, retry law,
   service account, task envelope, evidence volume, worker stage, and job-
   config receipt; only its exact identity can authorize `terminal-abort`.
   The two outcomes cannot coexist. The run cannot relaunch
   source zero; an aborted run requires a newly frozen run ID and prefix.
13. Run one worker plus one independent verifier per source member. The
   finalizer structurally replays the 54 verifier acceptances and does not run
   a third science computation.

The prior CLI performed approximately 270 complete one-slate computations:
54 worker computations, 108 verifier computations, and 108 finalizer/post-write
computations. This amendment performs 108: 54 workers plus 54 independent
verifiers. Post-publication checks and the final join are structural exact
replays.

## Recovery and disclosure law

Every create-once transition has a hash-addressed intent and completion under
the fixed journal prefix. Recovery resolves only the exact target name,
immediately pins the returned generation, derives the exact content-addressed
journal names, and verifies bytes. Bucket listing and `latest` aliases are
absent. Before `gcloud` is called, a deterministic remote launch request is
published create-once. Runtime recovery must reopen the target *and* its exact
intent/completion journal; directly creating canonical-looking target bytes is
not launch authority. Only the caller that created that request may launch;
an ambiguous response consumes it globally and is never relaunched. Its exact
target, intent, and completion identities are passed into the runtime,
exact-replayed before core work, and bound into the stage start. Every
predecessor, lane, benchmark, and final replay reopens those request/journal
bytes plus the retained job-config receipt. A later invocation first resolves the fixed stage
receipt. If the original process created its core terminal before exiting, a
controller-only recovery command structurally reopens that terminal and
publishes the missing transport stage receipt with no Cloud relaunch and no
science computation. If neither stage nor core terminal exists, the consumed
request is terminal.

The production launcher fixes runtime attempt ordinal zero. Each stage start
attests the Cloud Run job, execution, task index zero, task attempt zero, task
count one, and exact digest D from runtime environment. It also binds the
exact predecessor identity: worker-to-verifier, prior-verifier-to-next-worker,
prepare-to-each-lane-head, and both lane ledgers-to-finalizer. The lane-ledger
replay verifies those chains. Finalization additionally proves all 108 worker
and verifier execution names are globally unique and that the finalizer name
is not among them.

The two background lane controllers are always joined, even when the first
wait reports failure. Their two exit statuses are written to a deterministic
state-named local mechanics carrier before the controller reports failure;
later structural recovery can retain a distinct success carrier without
overwriting the earlier failure. Neither carrier can license a stage or
science relaunch.

Durable recovery of a completed panel release reopens the finalizer runtime
from the release's exact published binding. It never fresh-measures the exited
finalizer process and never recomputes the 54 science suites. The live builder
retains its stricter fresh-current-process requirement.

Transport receipts expose mechanics and generation-pinned identities only.
They do not expose support observations, ranks, books, or comparative effects
before the complete panel release. The raw timing parser requires the complete
fixed GNU `time -v` label set under `LC_ALL=C` and rejects unknown lines, so
arbitrary support/rank/book/effect text cannot ride inside benchmark evidence.

The numeric gate also discloses both outer-versus-worker coherence limits used
by benchmark acceptance. GNU-time wall duration may exceed the bound worker
measurement by at most 120,000 milliseconds, and GNU-time peak RSS may exceed
it by at most 2,097,152 KiB. These are named, self-hashed compute-gate fields;
there is no hidden auxiliary numeric threshold.

As of this amendment's implementation, the 54-member G0 panel and generated
portable lock have passed independent byte/semantic review and the reviewed
lock is committed at Git HEAD. Every candidate and release invocation still
must rebuild and byte-match that tracked lock before doing any release work;
the committed fact alone is not substituted for the live preflight. The
disposable Rule-1 real-artifact four-law smoke is a second explicit
pre-contract blocker and has not yet run. Candidate mode may begin only after
the tracked G0 preflight succeeds; release mode cannot publish E or the
contract without the exact smoke/time/execution conjunction.

All outcome, historical-scoring, corpus-fill, graph-mutation, live-policy,
production-change, analytical, R6-freeze, promotion, and decision authorities
remain false. The implementation and this document grant no cloud launch or
outcome-read authority.
