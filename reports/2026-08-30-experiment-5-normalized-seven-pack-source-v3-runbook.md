# Experiment 5 normalized-source to source-v3 release runbook

Date: 2026-08-30
Status: implementation-complete locally; no cloud action, staging, commit, or
publication performed by this work

## Outcome

The shortest exact Experiment-5 source chain is now explicit:

1. publish and independently reopen one normalized paid-source terminal;
2. freeze one seven-pack request containing only that terminal identity and
   the already-published candidate-authority-v2 root identity;
3. task-0, publish, and independently reopen the seven-pack release;
4. from that reopened release, derive candidate-v2 and all seven row objects,
   then create the capture-plan-v3 lock;
5. track that lock in a second commit; and
6. let the existing component-v3/source-release-v3/source-batch-v3 chain
   derive every downstream input from the tracked lock.

No request or public bridge accepts caller-selected Fantasy Points or SIS
manifest identities. The two identities are derived only after
`reopen_normalized_snapshot_v1(...)` validates the normalized terminal and all
of its manifest/shard predecessors.

## Exact seven source packs

The five free-source warehouse packs remain fixed and ordered:

| Ordinal | Pack ID | Frozen slice(s) | Bounded warehouse relation(s) |
|---:|---|---|---|
| 0 | `nfl-schedules-2022-2025` | `schedule-games` | `schedules` |
| 1 | `nfl-weekly-stats-2022-2025` | `weekly-player-stats` | `weekly_stats` |
| 2 | `nfl-legacy-depth-2022-2024` | `legacy-depth` | `depth_charts` |
| 3 | `nfl-snapshot-depth-2025` | `snapshot-depth` | `depth_charts_snapshots` |
| 4 | `nfl-pfr-defense-and-snaps-2022-2025` | `pfr-pass-rush`, `pfr-secondary`, `pfr-snap-positions` | `pfr_advstats_def`, `snap_counts` |

The two paid-source artifact packs remain fixed and ordered:

| Ordinal | Canonical pack ID | Sole identity authority |
|---:|---|---|
| 5 | `fantasy-points-normalized-2022-2025` | Deep-reopened normalized terminal |
| 6 | `sis-normalized-2022-2025` | Deep-reopened normalized terminal |

The seven-pack capture performs exactly five bounded BigQuery jobs, produces
seven canonical row objects and seven provenance objects, and creates the
terminal upstream release as object 15, last. Synthetic fallback, listing,
overwrite, realized outcomes, world matrices, scoring and policy promotion
remain absent.

## Implemented release surfaces

- `corpus_r6_matchup_seven_pack_capture_operator_v1.py`
  - request schema is now `...capture-request/v2`;
  - accepts only `candidate_authority_v2_root_identity` and
    `normalized_snapshot_terminal_identity`;
  - task-0 and publish independently deep-reopen the normalized terminal and
    derive both canonical long manifest identities;
  - task-0 receives no publication callback, has an empty write inventory,
    and performs no query or publication; ambient service-account write
    capability is truthfully recorded as `not_evaluated`, not claimed absent.
- `corpus_r6_matchup_seven_pack_input_freezer_v1.py`
  - freezes only the two terminal identities into the request;
  - no longer reconstructs or accepts paid-source shards/manifests.
- `cloud_corpus_r6_matchup_seven_pack_capture_v1.sh`, its dedicated
  Dockerfile and Cloud Build file
  - build from an exact requested/resolved Git source;
  - embed a provider-source implementation authority and remeasure it in the
    Git-free runtime;
  - reuse the exact existing Cloud Run job, one task, zero retries;
  - expose only `task0`, `publish` and `reopen` container modes;
  - require a successful matching task-0 execution before publish;
  - remain host-default-off and were not executed here.
- `corpus_r6_matchup_capture_plan_from_seven_pack_v1.py`
  - first runs the full independent seven-pack reopen;
  - only after success reads the terminal and seven exact row objects;
  - derives candidate-v2 from the release rather than accepting another
    caller-selected candidate identity;
  - reads the fixed adapter final lock from Commit A;
  - builds and byte-revalidates capture-plan-v3;
  - has no publication callback.
- `run_corpus_r6_matchup_seven_pack_capture_v1.py freeze-capture-plan`
  - is separately default-off;
  - writes only the exact canonical capture-plan-v3 lock path, create-once;
  - cannot run before a generation-pinned seven-pack release exists.
- `corpus_r6_matchup_component_producer_v1.py`
  - exposes one bounded ordinal reducer for the launch gate;
  - validates the same complete 54-slate candidate/catalog predecessor
    lattice, but executes the production semantic/deletion reducer only for
    ordinal zero;
  - uses the same component leaf, bundle and producer-receipt builders as the
    full 54-slate publisher.
- `corpus_r6_matchup_source_task0_v3.py` and its CLI
  - are separately default-off for worker and verifier;
  - enumerate every possible ordinal-zero component leaf, source triple and
    task-0 result URI before constructing the write transport;
  - publish the task-0 worker result as the final create-once request;
  - independently reopen the exact generation-pinned worker result,
    candidate-v2/capture-v3 predecessors, one component ordinal and one source
    triple in a later verifier process;
  - expose no publication callback to the verifier and give it an empty write
    inventory; ambient principal capability remains `not_evaluated`.
- `cloud_corpus_r6_matchup_source_task0_v3.sh`, the Commit-B Dockerfile and
  Cloud Build file
  - build an immutable image containing an exact clean Git checkout of Commit
    B, which is required by the tracked capture-plan-v3 lock;
  - launch one-task/zero-retry worker, verifier and full-publication
    executions and retain the provider-returned exact execution names;
  - accept the verifier receipt only from exact provider-bound terminal
    success stdout/spec, require worker and verifier execution names to be
    distinct, and inject those exact names into the full-publication gate;
  - refuse full 54-slate publication unless the receipt binds the same
    run ID, Commit-B plan, dependency closure, immutable runtime, worker
    execution and verifier execution.

## Why two commits are unavoidable

This is a real self-reference boundary, not process preference.

### Commit A: executable implementation seal

Commit A must contain every implementation file measured by the seven-pack
capture and capture-plan-v3 builder. It is pushed before the normalized and
seven-pack releases are produced. Both releases and the capture-plan builder
therefore bind executable, clean, durable code.

The capture-plan file cannot be in Commit A: its bytes contain Commit-A
implementation measurements and generation-pinned identities that do not
exist until the seven-pack has published and independently reopened.

### Commit B: tracked plan lock

After seven-pack reopen, the default-off bridge creates exactly:

`reports/corpus-r6-matchup-runs/20260830-r6-matchup-source-v2/capture-plan-outer-candidate-authority-v3-lock.json`

Commit B tracks that generated file without changing the Commit-A measured
implementation. Existing component-v3 and source-v3 code then secure-reads
the lock from Git and proves its current bytes equal its Commit-B blob. Trying
to put this lock into Commit A would require the lock to contain the hash of a
commit that already contains the lock itself.

## Exact execution sequence

All placeholders below must be replaced with canonical absolute files or
provider identities. Do not launch a later step unless the preceding
independent reopen is complete.

1. **Commit A and push.** Include normalized-snapshot, seven-pack capture,
   bridge, cloud seam and tests. Keep the capture-plan-v3 lock absent.
2. **Normalized snapshot.** Run its guarded task-0, publish and reopen chain.
   Preserve the terminal identity, not loose manifest identities.
3. **Freeze seven-pack request.** The spec contains exactly:
   `schema_version`, `run_id`, `candidate_authority_v2_root_identity`, and
   `normalized_snapshot_terminal_identity`. The canonical candidate-v2 root
   presently recorded by the project is generation `1788081739195827`, SHA
   `ae6d0ba73ac627f652f2cfc542da3f43885f4b9090885457fa313ecb6a7faea8`.
4. **Build seven-pack image from Commit A.** Use
   `cloud_corpus_r6_matchup_seven_pack_capture_v1.sh build COMMIT_A` with its
   explicit host enable value. Retain build ID and immutable image digest.
5. **Seven-pack task-0.** Launch the request in the one-task image. Confirm its
   receipt has publication count zero and binds the normalized terminal plus
   derived canonical FP/SIS manifests.
6. **Seven-pack publish.** Supply the exact successful task-0 execution to the
   host gate. Confirm five warehouse queries, 15 create-once writes, and the
   upstream release root last.
7. **Seven-pack independent reopen.** Reopen the returned terminal identity in
   a later execution. Require all seven rows, all seven provenance objects and
   all paid-source manifest/shard predecessors reopened exactly.
8. **Create capture-plan-v3.** Return to a clean Commit-A worktree. With
   `CORPUS_R6_MATCHUP_CAPTURE_PLAN_V3_FREEZE=1`, run the seven-pack CLI's
   `freeze-capture-plan` mode against the exact reopened release identity and
   `--confirm-freeze`. The command writes only the canonical lock path.
9. **Commit B and push.** Track the generated lock plus its durable identity
   evidence/HANDOFF update. Do not alter measured Commit-A implementation in
   this commit.
10. **Build source-v3 Commit-B image.** Submit
    `cloudbuild.corpus-r6-matchup-source-v3.yaml` with `_CODE_SHA=COMMIT_B` and
    an image tag ending `matchup-source-v3-COMMIT_B`. Retain the provider build
    ID and immutable digest. The image must contain the exact clean Commit-B
    Git checkout; a source-only image is insufficient because the runtime
    reopens the tracked plan blob.
11. **Real ordinal-zero worker.** With the controller's explicit host enable,
    run `cloud_corpus_r6_matchup_source_task0_v3.sh worker` against the
    immutable image. Retain the provider-returned execution name and terminal
    stdout. Require the complete bounded inventory and task-0 result root
    last.
12. **Distinct ordinal-zero verifier.** Run the controller's `verify` action
    with the exact worker execution name. It extracts only that successful
    execution's generation-pinned worker-result identity, launches a distinct
    execution, and write-disabled reopens the complete one-ordinal chain.
13. **Full source-v3 publication.** Run the controller's `publish` action with
    the exact successful verifier execution. The controller verifies provider
    stdout/spec, while the in-image CLI checks the same exact worker/verifier
    names and Commit-B plan/closure/runtime before invoking the existing full
    component-v3 -> 54 source triples -> source-v3 root -> batch-v3 root
    publisher.
14. **Independent full reopen.** Launch the existing write-disabled full-batch
    reopener in a later exact-named execution and retain that receipt before
    treating source-v3 as released.

## Current downstream status and external launch gates

The existing capture-v3, component-v3, source-release-v3 and source-batch-v3
focused suites all pass against their current contracts. The batch public
publish API accepts only a run ID and derives candidate, plan, adapter,
upstream packs and component inputs from the tracked capture-plan-v3 lock.

The real worker/distinct-verifier/controller mechanics gap is closed in local
code. The older source-batch `task0` remains truthfully prerequisite-only and
is not relabelled; the new task-0 module is the real bounded worker/verifier.

Cloud launch remains **NO-GO** only because the chronological release inputs
do not yet exist: Commit A is not settled/pushed, the normalized and
seven-pack terminals are not published and independently reopened, the
capture-plan-v3 bytes therefore cannot yet exist, Commit B is not tracked and
pushed, and no provider Commit-B image/execution exists. Those are required
external release steps, not remaining source-v3 implementation gaps.

## Validation performed

- seven-pack core: 9 passed;
- seven-pack operator/CLI: 17 passed;
- seven-pack request freezer: 4 passed;
- normalized snapshot compatibility: 4 passed;
- seven-pack-to-capture-plan bridge: 3 passed;
- cloud seam: 5 passed;
- capture-plan-v3: 9 passed;
- component-v3: 9 passed;
- source-release-v3: 9 passed;
- source-batch-v3: 16 passed;
- source-batch-v3 CLI: 3 passed;
- one-task production component reducer: 1 passed;
- source-v3 task-0 worker/verifier contracts: 4 passed;
- source-v3 task-0 CLI: 3 passed;
- source-v3 exact-name controller/Commit-B build seam: 3 passed;
- edited Python compilation and shell syntax: passed.

No cloud command, outcome read, staging action, commit or publication occurred
during this implementation and validation.
