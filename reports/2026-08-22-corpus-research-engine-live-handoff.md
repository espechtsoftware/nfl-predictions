# Corpus research engine — live handoff

Snapshot: **2026-08-22 10:49 CDT / 15:49 UTC**

This document is the durable model/developer handoff for the active corpus
research work. `HANDOFF.md` remains authoritative; this report expands the
current entry so a replacement model can resume without conversation context.

## Executive status

- The repaired one-slate, seven-arm corpus score producer is **running now** in
  Cloud Run. It is a real scoring/solve task, not a foundation or dry run.
- The current execution is healthy, nonterminal, and unretried. Do not launch
  another producer under any circumstance.
- Repeated IAM/Cloud Asset census has been removed from the next-suite hot
  path. The bounded deployment-attestation implementation is reviewed,
  integrated, committed, and pushed.
- A complete sparse analysis of the accepted task-0 corpus has already been
  executed. It covers every one of 585 lineups across all 50,000 simulated
  worlds and 27,117 strict `>200` events.
- The existing fixed historical engine can run 54 slates × seven legal-rule
  arms after this smoke is accepted. A generalized named fill × retrieval
  scenario release and a strict phenotype-to-Neo4j/UI adapter are in isolated
  worktrees but are not yet ready to integrate.
- Realized contest outcomes are not part of the active smoke. The existing
  realized grader is ready only after a complete accepted fixed 54×7 batch.

## Repository and immutable execution identities

### Current pushed application branch

- Branch: `main`
- Local and `origin/main` tip at this snapshot:
  `ed3f7db4ef0269cbee63c78f140a415f47bb1185`
- Important integrated commits:
  - `1a1cbc8` — bounded deployment attestation
  - `0393e09` — launch-governance binding through terminalization
  - `0409c8c` — expiry renewal, legacy fallback, terminal Scheduler evidence
  - `ed3f7db` — active v4 launch receipts and handoff

### Exact source used by the active science run

- Source SHA: `c60b7e7992b5c6367edb14a17c6edd13a30539f2`
- Clean exact worktree: `/tmp/nfl-predictions-corpus-c60b7e7`
- Python 3.11: `/tmp/nfl-corpus-py311/bin/python`
- Build ID: `485ecb3f-ef3e-4bf4-81b7-408adae96362`
- Immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:93623cffccdd67688499e20ef9904504749d270184158f181b90af5d3d4b6c5b`
- Reused Cloud Run job: `atlas-minimal-c-s2023-w1-v1`
- Expected job UID: `d6e4b8c1-5950-46b7-8869-7e34dbf29ad2`
- Runtime service account:
  `corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com`

Do not run the active c60 contract with current-main operator/worker code. The
current execution must finish with the c60 scripts in the exact worktree.

## Active score execution

- Execution name: `atlas-minimal-c-s2023-w1-v1-l6dll`
- Execution UID: `64e1275f-ee3f-4efe-a63a-6fc6becfac84`
- Created: `2026-08-22T14:56:04.602828Z`
- Execution start: `2026-08-22T14:56:38.322669Z`
- Container task start: `2026-08-22T14:58:01.153094Z`
- Status at `2026-08-22T15:49:15Z`:
  - `Completed=Unknown`
  - `runningCount=1`
  - `succeededCount=0`
  - `failedCount=0`
  - `retriedCount=0`
  - message: `Waiting for execution to complete.`
- Job law: one task, `maxRetries=0`, no automatic retry authority.
- The producer launch was consumed exactly once and is bound in:
  `reports/corpus-parametric-runs/20260822-corpus-parametric-task0-smoke-v4/transport-live-v4/tasks/000-producer-bound.json`
- At the snapshot, the task prefix contains exactly the three expected
  transport objects: producer intent, launch ledger, and execution-name
  binding. No provisional science object has been inferred as a result.

### Runtime diagnosis

Cloud Monitoring shows a stable CPU-utilization mean of approximately
`0.125` on the 8-vCPU worker. This is exactly one saturated core. The run is
not hung; the current implementation executes deterministic CBC work
sequentially with `CBC_THREADS=1`.

The smoke dose is substantial:

- seven parameter arms;
- five world blocks;
- 200 scheduled lineup visits per block and arm;
- 7,000 visits total;
- two exact CBC proof stages per normal visit, up to roughly 14,000 CBC stages;
- all selected candidates are then cross-scored on the common 50,000-world
  matrix.

The larger engine should parallelize independent arm/block visits
deterministically while retaining one CBC thread per solve. It should also
publish bounded progress telemetry. Do not change or cancel the current run to
apply that optimization.

## Exact resume procedure for the active execution

### 1. Poll only; do not call `launch-producer`

```bash
gcloud run jobs executions describe atlas-minimal-c-s2023-w1-v1-l6dll \
  --project nfl-predictions-503414 \
  --region us-central1 \
  --format=json | jq '{
    name:.metadata.name,
    uid:.metadata.uid,
    startTime:.status.startTime,
    completionTime:(.status.completionTime // null),
    completed:([.status.conditions[]? | select(.type=="Completed")][0].status // "Unknown"),
    reason:([.status.conditions[]? | select(.type=="Completed")][0].reason // null),
    message:([.status.conditions[]? | select(.type=="Completed")][0].message // null),
    runningCount:(.status.runningCount // 0),
    succeededCount:(.status.succeededCount // 0),
    failedCount:(.status.failedCount // 0),
    retriedCount:(.status.retriedCount // 0)
  }'
```

If `Completed=Unknown`, wait and poll again. Do not create new launch or bind
attempts. If `Completed=False`, retain the execution metadata and logs, update
`HANDOFF.md`, and stop permanently; no retry is licensed.

### 2. Export the exact c60 close/verification environment

Use a non-TTY shell:

```bash
set -euo pipefail

export CORPUS_EXACT_SOURCE=/tmp/nfl-predictions-corpus-c60b7e7
export CORPUS_PARAMETRIC_PYTHON=/tmp/nfl-corpus-py311/bin/python
export PYTHONPATH="$CORPUS_EXACT_SOURCE/src"
export CORPUS_PARAMETRIC_RESEARCH_ENABLED=1
export CORPUS_PARAMETRIC_RUN_DIR=/home/erich/projects/nfl-predictions/reports/corpus-parametric-runs/20260822-corpus-parametric-task0-smoke-v4/transport-live-v4
export CORPUS_PARAMETRIC_JOB=atlas-minimal-c-s2023-w1-v1
export CORPUS_PARAMETRIC_TASK_INDEX=0
export CORPUS_PARAMETRIC_CONTRACT_URI='gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260822-corpus-parametric-task0-smoke-batch-v4/governance/parametric-transport-contract.json'
export CORPUS_PARAMETRIC_CONTRACT_GENERATION=1787410071435177
export CORPUS_PARAMETRIC_CONTRACT_SHA256=269f7ddd18d661adc5cc5458e6f08021f71ebfbda0667ea9838a27eecc272f33
export CORPUS_PARAMETRIC_CONTRACT_BYTES=7383

test "$(git -C "$CORPUS_EXACT_SOURCE" rev-parse HEAD)" = \
  c60b7e7992b5c6367edb14a17c6edd13a30539f2
test -z "$(git -C "$CORPUS_EXACT_SOURCE" status --porcelain)"
cd "$CORPUS_EXACT_SOURCE"
```

### 3. On `Completed=True`, close the producer once

```bash
bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute watch-producer
```

This terminal c60 action performs exact job/execution checks, one Scheduler
census, and independent reopening before publishing the producer close and
task result. It performs no IAM or Cloud Asset census. It may take several
minutes because c60 reopens the task inputs again. Do not invoke it twice after
`tasks/000-producer-closed.json` exists.

Expected producer result URI:

`gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260822-corpus-parametric-task0-smoke-batch-v4/tasks/task-0000-2023-w01/result/task-result.json`

Do not report that result as accepted until the independent verifier completes.

### 4. Launch the verifier exactly once

Separate invocations only:

```bash
bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute launch-verifier
```

Whether the command succeeds, fails, times out, or returns ambiguously, never
call `launch-verifier` again. The only next action is recovery:

```bash
bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute recover-verifier
```

After `tasks/000-verifier-bound.json` exists, monitor that exact execution with
`gcloud run jobs executions describe`. On terminal success:

```bash
bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute watch-verifier
bash scripts/cloud_corpus_parametric_v1_reuse.sh --execute finish-batch
```

Acceptance requires both:

- `tasks/000-verifier-accepted.json` with `accepted=true` and
  `partial_result=false`;
- `batch-accepted.json` with `complete=true` and `accepted=true`.

The accepted terminal URI is:

`gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/batches/20260822-corpus-parametric-task0-smoke-batch-v4/tasks/task-0000-2023-w01/variants/transport/accepted-terminal.json`

Only then summarize the seven arm metrics and paired deltas.

## V4 foundation and transport evidence

### Foundation

- Foundation ID:
  `20260822-corpus-parametric-task0-smoke-foundation-v4`
- Batch ID: `20260822-corpus-parametric-task0-smoke-batch-v4`
- The one foundation run succeeded after reopening all 270 exact-generation
  Atlas artifacts: 54 slates × five blocks, 6,630,513,953 retained bytes.
- Publication completion:
  - URI:
    `gs://nfl-predictions-503414-corpus-parametric/research/corpus-parametric-research/foundations/20260822-corpus-parametric-task0-smoke-foundation-v4/governance/publication-completion.json`
  - generation `1787409646860065`
  - SHA-256
    `afccf08cdc0e643fc9363c9d012b7fb9f876728f8af19aaf04ff3218d73a37e3`
  - 7,570 bytes
- Batch manifest:
  - generation `1787409646007422`
  - SHA-256
    `8fac4aedabb3628c0506dd1ab1565e1c690ff7902e770b9b0df21d28cc792150`
  - 12,646 bytes
- Evidence contract:
  - generation `1787409646519070`
  - SHA-256
    `c9642e155cee7b2b2f34c832dd0f31dc18419c73849640ea10bcfd76007f59c1`
  - 38,493 bytes
- Retrieval prerequisite:
  - generation `1787409640765683`
  - SHA-256
    `1e2090aaf88085c5fb99ad1b07e480b0d0db5cb0606b5edd464703b3a7f89c85`
  - 1,925 bytes

### Transport

- Transport contract:
  - generation `1787410071435177`
  - SHA-256
    `269f7ddd18d661adc5cc5458e6f08021f71ebfbda0667ea9838a27eecc272f33`
  - 7,383 bytes
- Outcome-blind `validate-only` reopened 19 exact inputs for `2023-w01`,
  reported `solve_invoked=false`, and read no realized outcomes.
- The exact task prefix was proven empty immediately before the producer launch.

### Failed build/run identities that must never be reused

- Build `e6fb9995-a89d-4765-bc89-7292ce5a551a` used a mistyped nonexistent
  revision and failed before any configured build step. It produced no image.
- V3 producer execution `atlas-minimal-c-s2023-w1-v1-jx6wt` is terminal failed
  from the import-path packaging defect. Its launch is consumed. Never retry or
  cite it as a score.
- Earlier v2 execution `atlas-minimal-c-s2023-w1-v1-24bkl` is also terminal
  failed and consumed. Never retry.

## IAM-census removal

The new implementation is on current `main`; it is not mixed into the active
c60 run.

### Behavior

1. Initial configuration makes one bounded, self-hashed deployment attestation
   from:
   - the retained immutable IAM capture;
   - exact build/image/code;
   - service account;
   - exact parked job UID, generation and spec;
   - `maxRetries=0` and no active executions;
   - one complete Scheduler census.
2. `configure-attested`, launch, attested recovery and attested watch avoid IAM
   and Cloud Asset calls and avoid all-region Scheduler scans while the proof is
   valid.
3. A phase launched before expiry remains recoverable/terminalizable after
   expiry because launch-time governance is bound into its receipts.
4. If a long producer outlives the default six-hour proof, the verifier launch
   may make one bounded renewal from the byte-identical retained IAM capture
   plus fresh job, execution and Scheduler evidence. Renewal makes no IAM or
   Cloud Asset call.
5. Legacy governance-free receipts still require their former fresh Scheduler
   evidence.
6. Launch-governance and terminal-Scheduler fingerprints are stored separately.

### Validation

- Independent final rereview: no blockers.
- Focused Python 3.11 transport suite: 43 passed.
- Shell syntax, bytecode compilation and diff checks passed.
- Residual intentional tradeoff: a no-census bounded proof cannot detect an
  out-of-band IAM mutation during its lifetime. A new initial configure or
  expiry refreshes the trust boundary.

### V4 IAM capture

- Local tracked file:
  `reports/corpus-parametric-runs/20260822-corpus-parametric-task0-smoke-v4/governance-live-v4/runtime-iam-policy-capture.json`
- 23,569 bytes
- raw SHA-256
  `476bfdd06634058449c4afc43511fd37a614f7f38b80e68a8ed012f166e2776d`
- embedded capture SHA-256
  `9cfa4b86726591f3f915e4ecf8882ccb70cb8cb135c2ec413581dc76d2d57c32`

Do not repeat IAM/Cloud Asset census per task or phase.

## Accepted corpus `>200` phenotype intelligence

The sparse analyzer has already run and its output is durable.

### Scope

- 585 unique lineups
- all 50,000 simulated worlds
- 29,250,000 lineup-world scores represented by the accepted source task
- 27,117 strict `>200` events
- 581 of 585 lineups with at least one event
- 5,997 retained phenotype associations
- all 170,820 lineup-pair roster overlaps examined
- 2,000 high-overlap/correlation pairs retained
- Neo4j projection: 16,899 nodes and 82,917 edges
- Discovery R0–R3 is structurally separate from descriptive held-out R4.

### Strong supported observations

| Phenotype | Lineup support | R0–R3 `>200` events | Discovery lift | R4 descriptive lift |
|---|---:|---:|---:|---:|
| Boom generator tag | 200 | 12,089 | 1.624× | 1.682× |
| QB stack 3 + bring-back 1 + max game stack 5 | 92 | 7,607 | 2.221× | 2.283× |
| Same stack + boom | 55 | 5,494 | 2.684× | 2.773× |
| Raheem Mostert + Tyreek Hill | 10 | 1,586 | 4.261× | 4.763× |
| Four-player MIA stack | 10 | 1,585 | 4.258× | 4.697× |

These are simulated associations, not causal conclusions and not automatic
production-promotion authority.

### Durable artifact

- Compressed analysis URI:
  `gs://nfl-predictions-503414-corpus-parametric/research/corpus-phenotype-analysis/20260822-task0-simulated-gt200-phenotype-v1/analysis.json.gz`
- generation `1787408082871309`
- compressed SHA-256
  `83d7bfe6d635530ce7983df0bf875031a7b0370837e285e573a4c7bd32d28ed5`
- 6,336,408 bytes
- internal analysis SHA-256
  `98b21c536660a9d012be178632914ff0f0a36fbd951445177180401915ba5e19`
- uncompressed SHA-256
  `ef65d7a24e78088ab740fabc5e02217ace6649e181f570a41cb89fed0cbe0bbb`
- uncompressed size 62,124,979 bytes
- tracked receipt:
  `reports/corpus-gt200-runs/20260822-task0-simulated-gt200-phenotype-v1/receipt.json`

### What is not present

- no realized contest rank, payout, ROI or milly-winner label;
- no easy-coverage annotation;
- no FantasyPoints or SIS scoring input in the accepted matrices;
- no ownership/leverage phenotype in this artifact;
- no causal promotion decision;
- no full 170,820-pair score-correlation matrix (only 2,000 high-overlap pairs
  retain full correlation/event-overlap data).

## Population and retrieval strategy direction

Keep two experimental axes separate:

1. **Population/fill preset**: how the corpus is generated and admitted.
2. **Retrieval preset**: how an exact-80 portfolio is selected from one frozen
   corpus snapshot.

This creates a factorial surface:

`FillPreset → CorpusSnapshot → ExperimentRun ← RetrievalPreset`

Each run produces a versioned `MetricSet`; paired comparisons produce a
`PromotionDecision`; an `ActiveStrategyPointer` records any adopted strategy.

### Existing ready surface

- Fixed fill engine: 54 historical slates × seven legal-rule arms.
- Fixed parameters cover salary, stack, bring-back, RB-v-DST and two-RB rules.
- Existing task-0 retrieval laws:
  - `coverage-194-v1`
  - `strict-200-coverage-v1`
  - `tail-ladder-200-210-220-v1`
  - `mean-score-v1`
- Existing realized grader can grade a complete accepted fixed 54×7 batch.

### Comparison law

- Fill effect: different fill/snapshot, same retrieval and worlds.
- Retrieval effect: same fill/snapshot, different retrieval.
- A cell where both differ is useful descriptively but is not an isolated main
  effect. Interaction estimation needs an explicit 2×2 comparison law.
- R4 must never influence selection or promotion; it is held-out descriptive
  evidence only.

### Boom direction

The evidence supports a prospective boom-enriched population experiment, but
does not yet authorize silently replacing the baseline. Register it as a named
challenger fill preset, score its snapshot once, apply all retrieval presets to
the same snapshot, and compare against a baseline retained on every slate.

## Neo4j and web UI status

### Already implemented and reusable

- Generic, versioned strategy registry types:
  `FillPreset`, `RetrievalPreset`, `CorpusSnapshot`, `ExperimentRun`,
  `MetricSet`, `PromotionDecision`, `ActiveStrategyPointer`.
- Dedicated append-only Neo4j transport, receipts, recovery and read-only query
  model for current namespaces.
- Web page and APIs for:
  - fill × retrieval heatmap;
  - paired delta chart;
  - scatter view;
  - promotion history;
  - lineup/player/team/game network.

### Remaining blockers

1. The production registry publisher is hard-wired to seven fixed fills, one
   exact-80 retrieval preset, and 378 fixed experiments.
2. Arbitrary boom/fill scenarios are not yet runnable by the fixed parametric
   engine.
3. The accepted phenotype projection has no strict Neo4j adapter/load receipt.
4. `corpus-population-research` and `corpus-realized-outcomes` are reserved
   empty in the current transport contract.
5. There is no durable proof yet of a live dedicated Neo4j endpoint/database,
   network route or secret binding.
6. The app reads only `CORPUS_RESEARCH_UI_PROJECTION_PATH`; production does not
   yet deliver a generation-pinned GCS projection to that path.
7. The 62-MB uncompressed phenotype artifact exceeds the UI 32-MB cap. Neo4j
   should retain sparse events and a generation-pinned GCS pointer; the UI
   should receive bounded aggregate association views.
8. Easy-coverage data is absent and cannot be created by graph ingestion.

### Desired bounded phenotype views

- phenotype support, event rate and lift;
- discovery R0–R3 beside descriptive R4;
- boom prevalence among `>200`, `>210`, `>220` cohorts;
- future point-in-time easy-coverage prevalence once a governed join exists;
- selected maximum and threshold-hit deltas for simulated and later realized
  results.

## FantasyPoints, SIS and coverage data

FantasyPoints and SIS datasets exist elsewhere in the repository, but neither
was bound to the accepted task-0 score matrices or the active v4 Atlas run.
Do not describe them as inputs to these scores.

A future coverage arm needs a separate immutable point-in-time namespace:

- `VendorCapture`
- `PrelockCoverageObservation`
- `CoverageProfile`

Every observation should bind vendor/source family, metric/value, support,
season/week/window, available-at timestamp, lock cutoff, immutable object
identity and player/team identity-mapping provenance.

## Work currently isolated and not on `main`

### Named scenario registry/release

- Worktree: `/tmp/nfl-scenario-registry-ed3f7db`
- Branch: `codex/scenario-registry`
- Base: `ed3f7db`
- Modified:
  - `src/nfl_dfs/research/corpus_strategy_registry.py`
  - `src/nfl_dfs/research/corpus_strategy_registry_release.py`
  - `scripts/prepare_corpus_strategy_registry_release.py`
  - `tests/test_corpus_strategy_registry_release.py`
- Intended additive behavior:
  - strict named-scenario manifest/CLI path;
  - old no-option release behavior remains byte-compatible;
  - four accepted task-0 retrieval laws share a neutral
    `accepted-task0-existing-corpus-v1` fill;
  - no fabricated boom-fill outcome;
  - R4 descriptive only.
- Status at handoff: the agent was interrupted after the documentation snapshot
  to freeze the worktree. The current diff is 2,159 lines across the four files
  and remains uncommitted. New v3 code compiled; existing registry/release tests
  passed 17 tests before the new fixture; old release/publication hashes
  remained unchanged. The subsequently added end-to-end test changes have not
  been run to a reported green terminal, so this work must not be cherry-picked
  yet.

### Phenotype Neo4j/UI adapter

- Worktree: `/tmp/nfl-predictions-phenotype-ed3f7db`
- Branch: `codex/phenotype-graph-ui-adapter`
- Base: `ed3f7db`
- Partial modification only:
  `src/nfl_dfs/research/corpus_neo4j_transport.py`
- Draft size: 109 changed lines (104 additions, five changes).
- The draft adds a population-only successor schema while preserving v2 and
  keeping realized outcomes reserved.
- It byte-compiles and passes `git diff --check`, but has no behavioral tests
  and is incomplete without receipt/hash validation, graph planning/loading,
  UI views and focused tests. It is deliberately uncommitted.

## Immediate post-score rollout

1. Accept the current producer through the independent verifier and report the
   seven arm results.
2. Add deterministic arm/block parallelism and progress telemetry; validate
   equivalence against the accepted one-slate result before using it broadly.
3. Build a new immutable image from the integrated no-IAM-census code.
4. Use one initial deployment attestation, then `configure-attested` for the
   fixed complete 54×7 historical batch.
5. Run tasks with safe bounded concurrency only after deterministic
   equivalence and job-quota checks; do not blindly repeat the current serial
   one-core shape 54 times.
6. Run the existing one-read realized grader on the complete accepted batch.
7. Finish and integrate the named-scenario release path.
8. Finish the strict phenotype graph adapter, then provision/load the dedicated
   graph and materialize a bounded UI projection.
9. Add the boom-enriched fill challenger and cross it with the four retrieval
   presets while preserving baseline and R4 isolation.
10. Add separately governed point-in-time coverage annotations when source
    identities and lock-time provenance are ready.

## Safety/no-go list

- Never retry or relaunch v2, v3 or the active v4 producer.
- Never treat a Cloud Run `Completed=True` condition alone as accepted science.
- Never report the v4 producer result before independent verifier acceptance.
- Never mix current-main transport code into the already-launched c60 contract.
- Never mutate the application’s existing graph for this research; use a
  dedicated Neo4j/database and an append-only manifest.
- Never let R4 held-out evidence influence selection.
- Never imply FantasyPoints/SIS/easy coverage produced the accepted Atlas
  scores.
- Never promote boom or another phenotype causally from one simulated slate.
- Never run another IAM/Cloud Asset census per task/phase. Refresh only at the
  bounded deployment trust boundary.
- Preserve unrelated dirty root-worktree files; they belong to the user.

## Root-worktree preservation note

At this snapshot the root worktree still contains unrelated user modifications
to `Dockerfile`, `cloudbuild.yaml`,
`src/nfl_dfs/research/lr8_exact_solvers.py`, and
`tests/test_lr8_exact_solvers.py`, plus many untracked reports/run artifacts.
Do not reset, overwrite, stage or clean them indiscriminately.

## Focused validation already completed

- Expansion build contract: 9 passed.
- Effective-policy inventory: 16 passed.
- c60 parametric transport before attestation series: 37 passed.
- Final deployment-attestation transport suite: 43 passed.
- Sparse phenotype analyzer: 3 passed before execution.
- Build `485ecb3f-ef3e-4bf4-81b7-408adae96362`: all mandatory focused build,
  source-resolution, image and Neo4j/UI stages passed.

Do not rerun the broad suite merely for handoff. Run only focused tests for new
code, then rely on the immutable build gate before cloud execution.
