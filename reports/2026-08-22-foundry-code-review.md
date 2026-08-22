# Independent review of recent Foundry code changes

**Date:** 2026-08-22 12:00 CDT

**Review type:** read-only, findings first

**Base revision:** `abe06843090985bb17573918816b327c94b8e605`

**Reviewer verdict:** the deterministic 54-slate x 7-arm generation batch is a
useful fill-ablation foundation, but it is not yet the complete fill x
retrieval Foundry described in the current handoff and roadmap. It can keep
producing fixed-selector scores behind the task-0 equivalence gate. The new
uncommitted seven-retrieval draft must not be deployed in its present state.

## Scope

The review covered:

- merged deterministic parallel generation, commit `b2d8451`;
- merged named-scenario registry release, commit `04d6579`;
- Foundry naming, preplan, handoff, and roadmap descriptions through
  `0176ac2`;
- the retrieval-v2 implementation merged during review as `10bdb07` and its
  roadmap binding in `abe0684`:
  - `src/nfl_dfs/research/corpus_retrieval_engine.py`, SHA-256
    `86c47c145fcb1c483b58d25963654d969bb24949883466e4d08cb1490f796bbf`;
  - `tests/test_corpus_retrieval_engine.py`, SHA-256
    `e5cbe9897b5f65995344ac04393e7948e217f70078d5f33412d2c83c6d823ae3`;
- the local-only v5 preplan builder, runbook, and resumable batch driver; and
- separately, the unmerged Neo4j deployment-manifest draft at `4859f7e`.

Unrelated LR8 and A7 working-tree changes were not reviewed. No source code,
deployment, cloud resource, or running process was changed by this review.

## Executive assessment

There are three different systems presently being described as one Foundry:

1. the running production plan: 54 slates x 7 fill-rule arms x one fixed
   exact-80/line-194 selector;
2. the accepted task-0 retrieval pilot: one immutable corpus x four retrieval
   laws with R0-R3 discovery and R4 held out; and
3. an uncommitted draft containing three more retrieval algorithms, but no v2
   executable suite or downstream integration.

These are all useful components, but they are not yet a 54 x 7 x N factorial.
The current scores should be reported as **fill-arm diagnostics under one
fixed selector**, not as evidence that the retrieval strategies were evaluated
across the historical slate panel.

The strongest parts of the work are the outcome firewall, create-once identity
discipline, parent-only evidence writing, deterministic science ordering, and
the explicit labeling of the 54 x 7 registry results as
`all-worlds-descriptive`. I found no direct realized-outcome read in the core
parametric generator.

## Findings and suggestions

### F1 — High: the new R3/R5 names, objectives, and retained evidence need tightening

During this review, the first R5 implementation exposed a real zero-minimum
plateau: while multiple blocks remained uncovered, its total-utility tie-break
could keep selecting the already strongest block. The other model corrected
the implementation before merging `10bdb07` to maximize the sorted
post-addition block-utility
profile lexicographically
(`src/nfl_dfs/research/corpus_retrieval_engine.py:1871-1886`) and corrected an
overlapping-world test fixture. The five new
selector-focused tests then passed.

Two material issues remain:

- The R5 trace stores only total newly added utility, not the block vector or
  leximin profile that actually selected the lineup
  (`corpus_retrieval_engine.py:1887-1896`). Neither the trace nor the current
  split metrics can demonstrate the claimed block balance independently.
- The proposed R3 implementation is not a tail lower-confidence bound. It
  multiplies raw marginal event counts by the number of blocks containing at
  least one event (`corpus_retrieval_engine.py:1754-1825`). It contains no
  shrinkage prior, variance estimate, confidence level, or lower bound.
  Candidate-specific weights plus a Boolean covered-world mask are also
  order-dependent: a low-support lineup can claim a world and prevent a later
  high-support lineup from receiving any credit for upgrading that world.

Suggestion: retain per-block before/add/after vectors and the exact leximin key
in a versioned R5 trace, plus block-min/dispersion metrics. Rename R3 as a
distinct-block-weighted heuristic, or implement the preregistered shrunk
per-block tail-rate LCB. If weighted coverage is retained, track each world's
best credited weight and value weight upgrades rather than only unseen worlds.

### F2 — Blocker for retrieval v2: the new algorithms are not executable end to end

`frozen_retrieval_strategies_v2` and three dispatch branches exist, but the
actual suite path remains v1:

- `build_suite_manifest` requires exactly four strategies and invokes only
  `validate_retrieval_strategy`
  (`src/nfl_dfs/research/corpus_retrieval_engine.py:982-1010`);
- `validate_suite_manifest` again requires exactly four
  (`corpus_retrieval_engine.py:1044-1074`);
- task-result replay hard-codes `strategy_count == 4`
  (`corpus_retrieval_engine.py:3165-3175`);
- Neo4j projection/transport and registry release also retain v1 counts and
  contracts (`corpus_retrieval_neo4j.py:423`,
  `corpus_neo4j_transport.py:955`, and
  `corpus_strategy_registry_release.py:1051`); and
- the v2 builder/validator are absent from `__all__`
  (`corpus_retrieval_engine.py:3665-3698`).

Suggestion: introduce an explicit versioned suite schema, select the matching
strategy registry in build/validate/replay, update every downstream count and
identity contract, and add one end-to-end seven-strategy
publish/reopen/replay/Neo4j/UI test. Do not work around the existing v1 schema
by merely changing `4` to `7`; accepted v1 artifacts must remain replayable.

Also reject negative `expected_ordinal` explicitly; the v1/v2 validators use
Python indexing and `-1` can select the last registered strategy.

### F3 — High: the production batch is 54 x 7 x 1, not fill x retrieval

The parametric contract freezes seven generation assignments
(`src/nfl_dfs/research/corpus_parametric_batch.py:9-14,47-62`). Each arm is
deduplicated, scored, and independently passed to the same `select_exact80`
law (`src/nfl_dfs/research/corpus_legal_feasibility.py:6341-6383`). The registry
accordingly creates one retrieval preset and binds it to every arm
(`src/nfl_dfs/research/corpus_strategy_registry_release.py:1478-1503,1698-1708`).

The four accepted retrieval laws are only a separate task-0 pilot. Named
scenario evidence is locked to task 0
(`src/nfl_dfs/research/corpus_strategy_registry.py:498-516,662-668`). The
running batch does not execute those laws across the seven fills or 54 slates.

Suggestion: immediately describe the current run as the **54 x 7 fill-ablation
foundation under fixed exact80/line194 retrieval**. Build a generation-pinned
adapter that reconstructs or publishes a common source-attributed lineup/score
snapshot per accepted slate, then applies each retrieval law to that same
snapshot. A minimal causal expansion can use the roadmap's A/B/C/D cells rather
than blindly paying for every 7 x N combination:

- incumbent fill / incumbent retrieval;
- incumbent fill / challenger retrieval;
- challenger fill / incumbent retrieval; and
- challenger fill / challenger retrieval.

### F4 — High: fill-axis named comparisons are logically impossible

For every paired scenario, the validator requires the baseline and challenger
to have the same source snapshot manifest
(`src/nfl_dfs/research/corpus_strategy_registry.py:2153-2168`). The fill-axis
branch then requires those snapshot manifests to differ
(`corpus_strategy_registry.py:2195-2203`). Both conditions cannot be true.

Suggestion: define retrieval comparisons as same snapshot/fill/worlds with a
different retrieval preset; define fill comparisons as different
fill-produced snapshots with the same retrieval preset and worlds. Remove the
contradictory common equality and add end-to-end tests for both axes before
using the registry for A/B/C/D cells.

### F5 — High: named scenario evidence is not visible in the web UI

The release creates `NamedScenarioDefinition` and
`AcceptedScenarioExperimentEvidence` nodes with direct `HAS_METRIC` and
`PAIRED_AGAINST_*` edges
(`src/nfl_dfs/research/corpus_strategy_registry.py:2873-3116`). The functional
read-only query catalog still matches only legacy `ExperimentRun` and
`ExperimentMetricSet` shapes; named nodes appear only in the generic census
(`corpus_strategy_registry.py:3694-3846`). The UI bridge is bound to that
catalog.

Suggestion: version the query and browser projection schemas and add a bounded
named-scenario comparison view carrying definition, baseline, comparison axis,
fill preset, retrieval preset, split, value, and
`heldout_descriptive_only`. Add graph-query -> bridge -> API -> browser tests.

### F6 — High for strategy promotion: current 54 x 7 evidence is descriptive, not held out

The fixed selector uses all R0-R4 worlds and its summaries reuse those worlds.
The registry correctly records `heldout_split_registered=false` and
`selection_informed_by_evaluation_worlds=true`
(`src/nfl_dfs/research/corpus_strategy_registry_release.py:1419-1427`) and
forbids promotion. The realized grader can report scores/ceilings but explicitly
rejects contest rank/ROI inputs and ends with `decision_authority=false`
(`src/nfl_dfs/research/corpus_realized_grading.py:572-595,895-910`).

Suggestion: use this batch to learn corpus support and nominate hypotheses, not
to promote a production strategy. Use R-block cross-fitting or season-level
nested walk-forward evaluation, then an untouched season/prospective gate.
Integrate the preregistered paired statistics and multiplicity correction
before emitting any promotion receipt.

### F7 — Medium-high: named release validation can fail after thousands of create-once writes

Definitions, intent, and presets are published before cross-definition
experiment ordering, source/metric binding, and full graph replay
(`src/nfl_dfs/research/corpus_strategy_registry_release.py:1336-1544,1921-1984`).
Duplicate experiment IDs, pairing cycles, invalid fill comparisons, or missing
source shapes can therefore strand an immutable partial prefix.

Suggestion: construct and replay the entire prospective release in memory
before the first object write. Add negative tests asserting the exact object
store remains empty for duplicate IDs, cycles, invalid fill pairs, missing
source nodes, and metric mismatches.

### F8 — Medium-high: named-source validation and assembly disagree

Validation accepts a selection source represented by either
`CorpusArtifactPointer` or `CorpusStrategySplitMeasurement`
(`src/nfl_dfs/research/corpus_strategy_registry.py:2007-2019`), while assembly
unconditionally indexes a `CorpusArtifactPointer` and also assumes a
`RetrievalStrategyResult` exists
(`corpus_strategy_registry.py:2927-3023`). Validated parent shapes can therefore
end in raw `KeyError` rather than a governed registry error.

Suggestion: preflight every exact node kind and key consumed by assembly, then
raise `CorpusStrategyRegistryError` with the missing source identity. Add
negative tests for absent strategy result and split-measurement-only selection.

Named metric declarations also accept free-form name, unit, direction, and
source metric while publication always derives `sample_count` from
`world_count` (`corpus_strategy_registry_release.py:1240-1271`). That is wrong
for lineup-world or lineup-count denominators. Define a canonical source-metric
catalog binding name, unit, direction, value field, and denominator field.

### F9 — Medium: the documented data product is richer than the retained batch product

The roadmap says each task yields a cross-arm union and full 50,000-world score
matrices. The current variant payload retains per-arm rosters and score hashes,
not the score-matrix bodies
(`src/nfl_dfs/research/corpus_legal_feasibility.py:6042-6064,6256-6264`). The
strategy registry stores only the first three selected lineups per arm
(`src/nfl_dfs/research/corpus_strategy_registry_release.py:58,1581-1592`).

Suggestion: either publish governed sparse/full score sidecars, or specify and
verify deterministic reconstruction from the pinned world matrices before
retrieval and phenotype work. Keep full data in object storage and bounded
aggregates/pointers in Neo4j; label the current graph lineup traversal as a
three-lineup sample, not a complete corpus view.

### F10 — Medium: production orchestration contracts are inconsistent and local-only

The frozen preplan has `publish_task_requests:false`. The builder inherits this
from the smoke template and never overrides it, while the runbook says the
foundation must publish 54 task-request objects. The foundation correctly
publishes zero under that preplan. This is **not an execution blocker** because
the transport deterministically synthesizes and rebinds each task request from
the exact manifest and contract
(`scripts/run_corpus_parametric_transport.py:5710-5730,6051-6056`). Do not
relaunch the create-once foundation merely to satisfy the prose.

The builder, runbook, and driver live only under `/home/erich/nfl-panels`.
The driver can run any numeric range and does not require a task-0 equivalence
PASS receipt before task 1. This leaves the most important fanout gate as an
operator convention.

Suggestion: accept deterministic runtime request synthesis as the v5 law and
correct the runbook. Track the builder, driver, and runbook in Git. Require an
immutable equivalence receipt before any range beginning above zero; validate
integer bounds `0..53` and `FIRST <= LAST`; test crash/resume and ambiguous
launch states. This should be done before unattended tasks 1-53, but it need not
delay the current foundation or task 0.

### F11 — Medium: deterministic parallelism has head-of-line and failure-teardown risks

The parallel generator submits a bounded window but waits for futures in plan
order (`src/nfl_dfs/research/corpus_legal_feasibility.py:5085-5121`). A slow
early unit can leave workers idle even when later work has completed. On a
future exception, cancellation plus the executor context can wait for running
units to finish.

Suggestion: consume completions into a bounded indexed buffer, emit progress
when futures finish, and assemble canonical evidence in plan order. Add delayed
first-unit, worker-death, exception, cancellation, heartbeat, and retained
partial-evidence tests. The current parent-writer/spawn-worker design otherwise
looks sound, and the task-0 v4/v5 science-equivalence gate is the correct
production protection.

### F12 — Separate unmerged Neo4j v3 draft: predecessor identity is not content-bound

Commit `4859f7e` accepts both a base deployment manifest and a claimed base
identity, validates them independently, and copies the manifest into a v3
successor. It never proves that the supplied identity SHA/byte count is the
canonical identity of the supplied base manifest
(`corpus_neo4j_transport.py` in that commit, lines 767-821). The v3 validator
only normalizes the `supersedes_deployment_manifest` identity. The commit adds
no tests.

Suggestion before merging: exact-read the predecessor from its object store or
compare canonical bytes, SHA-256, and length to the supplied identity. Test a
mismatched-but-valid predecessor identity, exact allowed-schema delta, v2
compatibility, outcome-namespace exclusion, and create-once idempotency.

## Interpretation cautions for the planned phenotype research

These are not reasons to discard the batch, but they limit claims made from it:

- The source authority does not claim a complete DraftKings salary universe;
  relaxed arms cannot discover lineups containing absent players. Label results
  conditional on the exact artifact-supported player universe.
- Optional coverage/ownership/leverage annotations in the >200 analyzer are
  not yet generation-pinned or point-in-time enforced. Require immutable
  source/query identities, observation timestamps, slate lock, row allowlists,
  and an outcome-column denial before using them in a reusable phenotype.
- `qb_stack_teammates` includes RB in the retrieval phenotype code, while the
  optimizer and winner census use WR/TE. Version a common
  `qb_pass_catcher_count` definition before comparing corpus and winners.
- Treat slate/season as the evidence unit. Lineup-world events share players,
  worlds, and slates; raw >200 event counts are not independent observations.

## Recommended release sequence

1. **Keep current scoring moving:** allow the v5 foundation/task-0 path to
   continue under its exact preplan. Do not stop it because zero task-request
   objects were published.
2. **Before tasks 1-53:** require a machine-readable task-0 v4/v5 science
   equivalence PASS and put the resumable driver under version control.
3. **Correct the name of the evidence:** publish current results as 54 x 7
   fixed-selector fill diagnostics, not the complete Foundry factorial.
4. **Complete retrieval v2:** retain the corrected leximin R5 law, resolve the
   R3 name/objective mismatch, version the suite, integrate all downstream
   validators, add full replay tests, and benchmark chunked memory/runtime on
   realistic corpus sizes.
5. **Build the parametric-to-retrieval adapter:** one immutable per-slate
   source-attributed snapshot with score/event sidecars or verified
   reconstruction; then run A/B/C/D cells with true heldout/cross-fit evidence.
6. **Repair registry and UI:** make fill comparisons satisfiable, preflight
   releases before writes, close source-shape gaps, and expose named comparisons
   in the web UI.
7. **Only then consider promotion:** grade realized outcomes once, use
   slate/season paired statistics and multiplicity control, and reserve an
   untouched confirmation gate.

## Focused validation performed

- `tests/test_corpus_legal_feasibility.py`: 31 passed.
- `tests/test_corpus_strategy_registry_release.py`: 4 passed.
- `tests/test_corpus_strategy_registry.py`: 15 passed.
- `tests/test_corpus_research_ui_bridge.py`: 6 passed.
- `tests/test_corpus_research_ui.py`: 6 passed, one unrelated deprecation
  warning.
- The full retrieval module was loaded while `10bdb07` was being prepared and
  initially exposed two failures: the R5 zero-minimum plateau and an overlapping
  test fixture. Both were corrected in the SHA-identified snapshot above. A
  fresh focused rerun of the five new v2 selector tests then passed in 2.8s.
  This does not close F2 because no end-to-end v2 suite test exists.

No full suite or heavy local simulation was run.
