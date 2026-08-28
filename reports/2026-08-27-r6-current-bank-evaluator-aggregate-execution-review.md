# R6 current-bank evaluator and aggregate execution review

Date: 2026-08-27 (America/Chicago)

Status: preparatory read-only review; implementation is not yet authorized to
open simulated output. This document records the minimum execution surface and
the contract defects that must be closed before executables C and D are built.

## Purpose

Executable A projects the fixed panel into five fold-safe views per slate.
Executable B selects lineups in isolated four-block processes. The remaining
path must evaluate those immutable selections on the fifth block, aggregate
all 54 slates without accepting caller-created metrics, nominate challengers,
and reconstruct a root from exact published predecessors. This review keeps
that path small, deterministic, generation-exact, and reusable for the broad
and confirmation screens.

## Required contract repairs

1. **Materialize broad authority at ordinal 163.** The present topology has no
   standalone broad-authority object, while confirmation accepts a supplied
   broad-authority body. Make ordinal 163 a nomination-publication wrapper
   containing both the exact broad authority rebuilt from 54 broad evaluation
   publications and the nomination deterministically derived from it.
   Confirmation must exact-reopen this one object; it must not accept a
   separately supplied broad body plus matching hash. The topology remains
   275 objects.
2. **Compile budgets for every publisher.** Add process roles and exact
   cumulative read/write budgets for the broad nomination aggregator, the
   aggregate/finalist publisher, and the terminal-root publisher. Include the
   design, topology, process-budget and runtime/bootstrap authorities in the
   read precharge rather than counting only scientific inputs.
3. **Bind runtime and bootstrap authority.** The topology-bearing design must
   bind an immutable bootstrap manifest containing the run identity, code
   commit, image digest, expected commands and entrypoint hashes, process
   budget inventory, and exact topology identity. Runtime values observed from
   a process environment are observations, not independent cloud attestation;
   the outer launch and terminal execution receipts must bind the actual
   Cloud Run image/job/execution to those expected and observed values.
   Evaluation results must bind their exact process budget and observed
   runtime evidence.
4. **Make terminal reconstruction streaming.** Do not list-materialize all 274
   predecessor bodies. Exact-read them in topology ordinal order and retain
   every identity. Discard projections and selection receipts after
   validation; validate each evaluation body, immediately reduce it to the
   compact phase-grid/comparison inputs required for deterministic aggregate
   replay, and then discard that body too. Do not retain all 108 evaluation
   bodies—their ceilings alone are tens of gigabytes. Frozen predecessor byte
   ceilings sum to roughly 105.7 GB, so the list API is not a valid memory
   contract even if normal objects are smaller.
5. **Evaluate held-out matrices sequentially.** Factor a contract-owned
   single-fold evaluator and exact-five-fold assembler. Validate, derive and
   release one `N x 10,000` matrix before opening the next rather than retaining
   all five matrices together.

## Executable C: held-out evaluator

Proposed files:

- `src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_evaluation_v1.py`
- `scripts/run_corpus_r6_current_bank_crossed_screen_evaluation_v1.py`
- `tests/test_corpus_r6_current_bank_crossed_screen_evaluation_execution_v1.py`

The sole mode is `evaluate-slate`. One process handles one
`(phase, source_ordinal)` and all five folds sequentially. It produces 108
topology objects:

- broad evaluation ordinals 109–162; and
- confirmation evaluation ordinals 218–271.

The request may contain only phase/source and exact identities for design,
topology, projection, immutable selection receipt, evaluator process budget,
runtime/bootstrap authority, and—during confirmation—the ordinal-163
nomination publication. It must not accept artifact identities, matrices,
player maps, metric rows, cells, output URIs, selector commands, selected
lineups, comparisons, or bootstraps.

The process exact-reopens and validates its receipt (and confirmation
nomination) before any held-out artifact read. Its allowlisted scientific
reader then exposes only the later source and five held-out artifacts derived
from the validated projection/budget. It must not import the selector,
selection worker/assembler, strategy dispatcher, book builder, graph code, or
outcome source.

Each result must contain exactly five folds in R0–R4 order, 140 population
metric rows (28 per fold), and:

- broad: 960 book rows (`5 folds x 64 cells x 3 prefixes`); or
- confirmation: `480 x nominee_count` book rows, or 1,440–2,880 for 3–6
  nominees.

Candidate order and each finite float64 held-out matrix must be rebound to the
frozen shape/hash before metrics are derived.

## Executable D: deterministic publication

Proposed files:

- `src/nfl_dfs/research/corpus_r6_current_bank_crossed_screen_aggregate_v1.py`
- `scripts/run_corpus_r6_current_bank_crossed_screen_aggregate_v1.py`
- `tests/test_corpus_r6_current_bank_crossed_screen_aggregate_execution_v1.py`

It has three separate-process modes:

### `publish-nomination`

Exact-read design/topology/runtime authorities and all 54 broad evaluation
publications in source order. Rebuild the 64-row broad grid and broad-phase
authority, deterministically derive 3–6 nominees, and publish only the
ordinal-163 wrapper containing both authorities.

### `publish-aggregate-finalists`

Exact-read design/topology/runtime authorities, all 54 broad evaluations,
ordinal 163, and all 54 confirmation evaluations. Rebuild the aggregate, then
publish ordinal 272. Exact-reopen its returned generation, derive finalists
from that exact identity, and publish ordinal 273. Precharge both writes before
the first write. The aggregate must contain 64 broad rows, 3–6 confirmation
rows, and 10–25 paired comparison/bootstrap authorities (five folds for each
non-incumbent nominee), each derived from exactly 270 ordered rows.

### `publish-terminal-root`

Run in a fresh process. Exact-read all 274 predecessor identities in topology
ordinal order through the streaming interface, byte-rebuild aggregate and
finalists, and publish only ordinal 274.

Executable D may read published JSON authorities only. It must have no world
artifact, NPZ, later-source, matrix, selector, graph, or realized-outcome
capability.

## Create-once and resume law

All C/D modes reuse executable A's strict transport semantics:

- fixed project and public storage endpoint;
- semantic, execution-gate, command and redirect validation before client
  construction;
- no list, current-generation metadata, reload, or optional resolution;
- create with generation precondition zero;
- exact-generation reopen after every successful creation;
- collision resume only with a supplied prior exact identity whose URI,
  generation, size, object hash and canonical body equal the would-be body;
- no platform retry and no implicit resume; and
- strict ordinal layer publication, so all 54 selections precede evaluation
  publication and all 54 broad evaluations precede ordinal 163.

## Initial resource envelopes

| Mode | CPU | Memory | Timeout | Tasks / retries |
|---|---:|---:|---:|---:|
| evaluator | 4 | 16 GiB | 7,200 s | 1 / 0 |
| nomination | 2 | 8 GiB | 1,800 s | 1 / 0 |
| aggregate/finalists | 4 | 16 GiB | 7,200 s | 1 / 0 |
| terminal root | 4 | 16 GiB | 7,200 s | 1 / 0 |

These are starting ceilings, not performance claims. Representative largest
slate smoke evidence must confirm them before the full screen.

## Minimum acceptance tests

The focused suites must include:

- golden broad and confirmation evaluation construction;
- receipt/nomination generation, phase, source and body rejection before any
  held-out read;
- missing, duplicate, reordered and wrong-block artifact rejection;
- candidate-order, dtype, nonfinite, row-count and 10,000-world rejection;
- static dependency rejection for selector/worker/assembler imports in C and
  any scientific artifact imports in D;
- exact 54-record nomination and exact 54+54 aggregate known answers;
- rejection of caller grids, nominee arrays, comparisons and bootstraps;
- pinned bootstrap seed, input/draw hash and endpoints;
- deterministic finalists bound to the exact aggregate generation;
- streaming root acceptance of exactly 274 ordered predecessors and rejection
  of omission, duplication, reorder, URI/generation/body change and 273/275
  counts;
- new-create, exact-resume, missing-authority collision, wrong-generation and
  changed-body cases for every publication mode;
- invalid invocation and redirect rejection before client construction; and
- one authorized real-slate outcome-blind smoke that proves full-matrix and
  row-ledger equality without publishing the full result prefix.

## Implementation order

1. Repair the ordinal-163 wrapper and confirmation validation.
2. Add complete bootstrap/runtime and publisher-budget authority.
3. Add sequential fold evaluation and streaming terminal reconstruction.
4. Implement and adversarially test executable C.
5. Implement and adversarially test the three executable-D modes.
6. Commit the complete pre-output authority.
7. Run the one-slate real-artifact smoke, benchmark the largest representative
   slate, and only then launch the bounded 17,280-fit broad screen.

## Reusable cloud orchestration requirement

The stdin entrypoints are sufficient for focused tests and a controlled local
smoke, but stdin is not the full Cloud Run task-array contract. Before the
broad screen, add one immutable layer controller and task dispatcher. For each
54-slate layer it must:

- publish an exact request manifest mapping `CLOUD_RUN_TASK_INDEX` 0–53 to a
  generation-pinned canonical request;
- bind the manifest, image, command, process budgets and task count in a
  create-once launch intent before job mutation/execution;
- reuse one reviewed Cloud Run job/image and run the layer as a bounded task
  array—never deploy per strategy, profile, fold or slate;
- let each task exact-read only its manifest entry, then invoke the canonical
  B or C entrypoint without accepting an arbitrary command;
- retain the exact execution metadata and task terminal states in a terminal
  execution receipt that attests the environment observations embedded in
  output receipts; and
- enforce layer barriers globally: all 54 projections before broad selection,
  all 54 broad selections before broad evaluation, all 54 broad evaluations
  before ordinal 163, and the analogous confirmation/root ordering.

Resume must derive solely from the recorded request/output identities in the
manifest and receipts. It must not list an output prefix or resolve current
generations. This controller is what turns the parameterized engine into the
intended rapid experiment harness: build/deploy once, vary frozen request
manifests across runs, and retain complete comparable lineage.

No cloud object, sealed result, realized outcome, graph, deployment, IAM
policy, or Git ref was read or changed during this review.
