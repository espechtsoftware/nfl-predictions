# Post-grade release path manifest

Status: frozen staging map amended after the d5946133 source cohort completed
54/54 and its first collector failed before either known scientific output was
published.  Commit A now carries the narrowly reviewed collector-repair path
needed to finish that frozen grade without recomputing any shard.  The purpose
of this manifest is to make the immediate release mechanical without sweeping
unrelated dirty-worktree files into it.

## Release invariant

Create one pushed Commit A containing the one-use d594 collector repair, G0,
Week-1 generation shadow, Experiment 4 and the complete executable
Experiment-5 implementation seal listed below.  The guarded cloud release
paths require `HEAD == origin/main == CODE_SHA`.  After that push, do not
advance `origin/main` again until the repaired d594 grade-reopen and the
Experiment-4 grade-reopen have sealed and every Commit-A execution that must
run before the source-v3 self-reference boundary has completed.

Commit A must not contain the generated capture-plan-v3 lock.  Normalized
source and seven-pack publication from Commit A create the immutable
identities needed to derive that lock.  Commit B then tracks the generated
lock and the associated durable `HANDOFF.md` evidence without changing any
Commit-A measured implementation.  Source-v3 code is sealed in Commit A, but
its exact-Git image and every source-v3 launch are Commit-B-only.

## G0 / current-chain record

```text
.gitignore
HANDOFF.md
reports/2026-08-30-postgrade-release-path-manifest.md
reports/2026-08-30-production-review-remaining-ablations-plan.md
scripts/finish_corpus_r6_construction_allocation_d5946133_v1.py
tests/test_finish_corpus_r6_construction_allocation_d5946133_v1.py
```

Before staging, record the d594 source completion, failed collector, exact
root cause and frozen recovery plan in `HANDOFF.md`.  Append the later repair
and realized-grade identities as soon as those phases seal; do not advance the
release commit merely to write a mid-chain chronology update.

## One-use d594 collector-repair closure

```text
Dockerfile.corpus-r6-construction-allocation-snapshot
cloudbuild.corpus-r6-construction-allocation-snapshot.yaml
scripts/cloud_corpus_r6_construction_allocation_collector_repair_v1.sh
scripts/cloud_corpus_r6_construction_allocation_snapshot_v1.sh
scripts/run_corpus_r6_construction_allocation_collector_repair_v1.py
src/nfl_dfs/research/corpus_r6_construction_allocation_collector_repair_v1.py
src/nfl_dfs/research/corpus_r6_construction_allocation_cross_operator_v1.py
tests/test_corpus_r6_construction_allocation_collector_repair_cloud_v1.py
tests/test_corpus_r6_construction_allocation_collector_repair_v1.py
tests/test_corpus_r6_construction_allocation_operator_hardening_v1.py
```

The exact d594 source execution completed 54/54 successfully, but collector
execution `atlas-cbc-32g-full-2023-w8-v1-29lvz` failed before publication
because the operator incorrectly required the independent panel-index
self-hash to equal the panel-ID suffix.  The exact fixed panel has ID suffix
`ef445e2b...7392e0` and validated self-hash
`479b65bb...69b094`; all 54 member slate IDs and their order agree.  Exact
known-name checks proved both `selection.json` and `terminal.json` absent.

This recovery admits only that failed execution name, UID and provider facts.
It exact-reuses the d594 manifest, successful 54-task execution attestation
and all 54 shards while separately attesting the new collector code, image,
build and one-task execution.  It runs one collector and one independent
reopen, preserves the existing v1 selection/terminal bytes and schemas, then
publishes and exact-reopens one create-once collector-repair sidecar.  No shard
is recomputed and no outcome surface is available.  The repair/hardening/
source-collector/cloud-release/grade focus is 46/46; the narrower root rerun is
35/35, with Python compilation, shell syntax, YAML parsing and diff checks
green.  Grade uses the original run/grade IDs under the repaired immutable
runtime; the failed d594 finisher state is not reused.

## Week-1 generation-shadow closure

```text
Dockerfile
cloudbuild.yaml
cloudbuild.generation-shadow-suite.yaml
config/2026-week1-generation-shadow-seed-crossing-design.json
reports/2026-08-30-generation-shadow-operator-runbook.md
reports/2026-08-30-production-generation-shadow-program.md
scripts/build_generation_shadow_suite_image.sh
scripts/cloud_generation_shadow_suite.sh
scripts/publish_week1_operating_book.py
src/nfl_dfs/app/main.py
src/nfl_dfs/app/week1_operating_book_api.py
src/nfl_dfs/inference/live_lineups.py
src/nfl_dfs/inference/production_policy.py
src/nfl_dfs/inference/prospective_generation_shadow_operator.py
src/nfl_dfs/inference/prospective_generation_shadow_registry.py
src/nfl_dfs/inference/prospective_latent_role.py
src/nfl_dfs/inference/prospective_shadow.py
src/nfl_dfs/inference/run_projections.py
src/nfl_dfs/inference/week1_operating_book.py
src/nfl_dfs/inference/week1_operating_book_export.py
src/nfl_dfs/inference/week1_operating_book_operator.py
src/nfl_dfs/inference/week1_operating_book_suite_adapter.py
src/nfl_dfs/inference/week1_operating_roster_materializer.py
src/nfl_dfs/research/effective_policy_rule_inventory.py
tests/test_app.py
tests/test_effective_policy_rule_inventory.py
tests/test_generation_shadow_clean_build.py
tests/test_generation_shadow_suite_deployment.py
tests/test_live_smoke.py
tests/test_production_policy.py
tests/test_prospective_generation_shadow_operator.py
tests/test_prospective_generation_shadow_registry.py
tests/test_publish_week1_operating_book_script.py
tests/test_week1_operating_book.py
tests/test_week1_operating_book_api.py
tests/test_week1_operating_book_export.py
tests/test_week1_operating_book_operator.py
tests/test_week1_operating_book_suite_adapter.py
tests/test_week1_operating_roster_materializer.py
```

The new API and Week-1 modules are required by imports and by the effective
policy inventory's content hashes.  Partial staging is invalid.

## Experiment-4 fixed-budget admission closure

```text
Dockerfile.corpus-r6-broad-admission
Dockerfile.corpus-r6-broad-admission.dockerignore
cloudbuild.corpus-r6-broad-admission.yaml
scripts/cloud_corpus_r6_broad_admission_tournament_v1.sh
scripts/finish_corpus_r6_broad_admission_tournament_v1.py
scripts/run_corpus_r6_broad_admission_tournament_v1.py
src/nfl_dfs/research/corpus_r6_broad_admission_tournament_v1.py
src/nfl_dfs/research/corpus_r6_broad_admission_program_v1.py
tests/test_cloud_corpus_r6_broad_admission_tournament_v1.py
tests/test_corpus_r6_broad_admission_tournament_v1.py
tests/test_corpus_r6_broad_admission_program_v1.py
tests/test_finish_corpus_r6_broad_admission_tournament_v1.py
tests/test_run_corpus_r6_broad_admission_tournament_v1.py
```

The host finisher and its tests passed independent review on 2026-08-30:
the finisher/cloud-launcher focus is 26/26, its CLI is default-off, every
mutating phase writes a create-once intent before launch, and ambiguous
launch recovery requires an explicitly supplied exact execution name.

Exact fixed parents:

- Combined terminal: `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-combined-population-all-block/20260829-score-sprint-170b7b4e-v2/full54/full-54/descriptive-terminal-v2.json`, generation `1787999967997744`, SHA-256 `f6f2679f44032246508ac5905b51d53d4a3f1f178d15103a203d488017a796d1`, 35,870 bytes.
- Frontier manifest: `gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-combined-frontier-reportfolio/20260829-score-sprint-28db339e-v1/full54/manifest.json`, generation `1788029467812121`, SHA-256 `206a4dde7203bbd62b1ff6c6beee10ece26580c51650732132a0a7f8df08f114`, 55,096 bytes.

## Experiment-5 Commit-A implementation seal

The following groups are executable implementation, cloud seams and focused
tests.  They join Commit A even where their runtime is chronologically gated
on Commit B.  Stage the exact paths explicitly; do not use `git add -A`.

### Normalized paid-source snapshot

```text
Dockerfile.corpus-r6-paid-source-normalized-snapshot
Dockerfile.corpus-r6-paid-source-normalized-snapshot.dockerignore
cloudbuild.corpus-r6-paid-source-normalized-snapshot.yaml
scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh
scripts/run_corpus_r6_paid_source_normalized_snapshot_v1.py
src/nfl_dfs/research/corpus_r6_paid_source_normalized_snapshot_v1.py
tests/test_corpus_r6_paid_source_normalized_snapshot_v1.py
tests/test_run_corpus_r6_paid_source_normalized_snapshot_v1.py
tests/test_cloud_corpus_r6_paid_source_normalized_snapshot_v1.py
```

### Seven-pack capture, request freezer and capture-plan bridge

```text
Dockerfile.corpus-r6-matchup-seven-pack-capture
Dockerfile.corpus-r6-matchup-seven-pack-capture.dockerignore
cloudbuild.corpus-r6-matchup-seven-pack-capture.yaml
scripts/cloud_corpus_r6_matchup_seven_pack_capture_v1.sh
scripts/freeze_corpus_r6_matchup_seven_pack_inputs_v1.py
scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py
src/nfl_dfs/research/corpus_r6_matchup_seven_pack_capture_v1.py
src/nfl_dfs/research/corpus_r6_matchup_seven_pack_capture_operator_v1.py
src/nfl_dfs/research/corpus_r6_matchup_seven_pack_input_freezer_v1.py
src/nfl_dfs/research/corpus_r6_matchup_capture_plan_from_seven_pack_v1.py
tests/test_corpus_r6_matchup_seven_pack_capture_v1.py
tests/test_corpus_r6_matchup_seven_pack_capture_operator_v1.py
tests/test_corpus_r6_matchup_seven_pack_input_freezer_v1.py
tests/test_corpus_r6_matchup_capture_plan_from_seven_pack_v1.py
tests/test_cloud_corpus_r6_matchup_seven_pack_capture_v1.py
```

The normalized snapshot must not be partially staged without this seven-pack
closure.  Its runtime and measured implementation authority import the
seven-pack CLI/core/operator and the bridge.  The additional source-v2 and
player-catalog dependencies are already tracked and unchanged.

### Source-v3 executable seam

```text
Dockerfile.corpus-r6-matchup-source-v3
Dockerfile.corpus-r6-matchup-source-v3.dockerignore
cloudbuild.corpus-r6-matchup-source-v3.yaml
scripts/cloud_corpus_r6_matchup_source_task0_v3.sh
scripts/run_corpus_r6_matchup_source_task0_v3.py
scripts/run_corpus_r6_matchup_source_batch_v3.py
src/nfl_dfs/research/corpus_r6_matchup_source_task0_v3.py
src/nfl_dfs/research/corpus_r6_matchup_component_producer_v1.py
src/nfl_dfs/research/corpus_r6_matchup_source_batch_outer_candidate_authority_v3.py
src/nfl_dfs/research/corpus_r6_matchup_batch_candidate_authority_v1.py
src/nfl_dfs/research/corpus_r6_matchup_source_operator_v2.py
tests/test_cloud_corpus_r6_matchup_source_task0_v3.py
tests/test_corpus_r6_matchup_source_task0_v3.py
tests/test_run_corpus_r6_matchup_source_task0_v3.py
tests/test_corpus_r6_matchup_component_producer_v1.py
tests/test_corpus_r6_matchup_source_batch_outer_candidate_authority_v3.py
tests/test_run_corpus_r6_matchup_source_batch_v3.py
tests/test_corpus_r6_matchup_batch_candidate_authority_v1.py
```

These files are sealed in Commit A so Commit B can remain a generated-lock
commit.  Do not build or run the source-v3 image from Commit A.  Its Dockerfile
and Cloud Build contract require an exact clean Commit-B checkout containing
the tracked capture-plan-v3 blob.

### Discovery-matrix freezer

```text
Dockerfile.corpus-r6-paid-source-discovery-matrix
Dockerfile.corpus-r6-paid-source-discovery-matrix.dockerignore
cloudbuild.corpus-r6-paid-source-discovery-matrix.yaml
scripts/cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.sh
scripts/run_corpus_r6_paid_source_discovery_matrix_freeze_v1.py
src/nfl_dfs/research/corpus_r6_paid_source_discovery_matrix_freeze_v1.py
tests/test_corpus_r6_paid_source_discovery_matrix_freeze_v1.py
tests/test_run_corpus_r6_paid_source_discovery_matrix_freeze_v1.py
tests/test_cloud_corpus_r6_paid_source_discovery_matrix_freeze_v1.py
```

### Fantasy Points x SIS downstream ablation

```text
Dockerfile.corpus-r6-paid-source-fp-sis
Dockerfile.corpus-r6-paid-source-fp-sis.dockerignore
cloudbuild.corpus-r6-paid-source-fp-sis.yaml
scripts/cloud_corpus_r6_paid_source_fp_sis_v1.sh
scripts/run_corpus_r6_paid_source_fp_sis_v1.py
src/nfl_dfs/research/corpus_r6_paid_source_ablation_v1.py
src/nfl_dfs/research/paid_source_ablation_execution_v1.py
src/nfl_dfs/research/paid_source_ablation_grade_v1.py
src/nfl_dfs/research/paid_source_ablation_operator_v1.py
src/nfl_dfs/research/paid_source_ablation_registry_v1.py
tests/test_paid_source_ablation_execution_v1.py
tests/test_run_corpus_r6_paid_source_fp_sis_v1.py
tests/test_cloud_corpus_r6_paid_source_fp_sis_v1.py
tests/test_paid_source_ablations_v1.py
tests/test_paid_source_ablation_operator_grade_v1.py
```

The FP/SIS runner also imports the source-v3 batch-candidate and source
operator modules listed in the source-v3 group.  Its current operator imports
the following Odds implementation unconditionally, so these files are
dependency-only members of Commit A:

```text
src/nfl_dfs/research/odds_prop_override_ablation_v1.py
src/nfl_dfs/research/paid_source_odds_execution_adapter_v1.py
tests/test_paid_source_odds_execution_adapter_v1.py
```

Their inclusion is not Odds adoption.  Historical Odds prop override remains
NO-GO and is not an FP/SIS cell.  The files are present solely so the exact-Git
FP/SIS image can import its operator and validate the dependency.

### Experiment-5 release record

```text
reports/2026-08-30-experiment-5-normalized-seven-pack-source-v3-runbook.md
```

The ordinary build dependencies `README.md`, `pyproject.toml`, source-v2,
player-catalog, source-release and capture/component support modules are
already tracked and unchanged.  They are available to exact-Git or source
copy builds but do not need staging in Commit A.

## Commit-B-only generated boundary

The following path must be absent from Commit A and is created only after the
Commit-A normalized terminal and seven-pack terminal both publish and pass
independent reopen:

```text
reports/corpus-r6-matchup-runs/20260830-r6-matchup-source-v2/capture-plan-outer-candidate-authority-v3-lock.json
```

Commit B tracks that create-once local lock, the post-publication
`HANDOFF.md` update and only specifically named durable identity evidence.
It must not modify any normalized, seven-pack, bridge, source-v3, matrix or
FP/SIS implementation sealed in Commit A.

## Explicit exclusions

Do not sweep in the modified Foundry evidence trees, T230 run artifacts,
foundation execute result, core-v1 score-chain wrapper, Foundry environment
scripts, recourse single-job transport, or the untracked fair-fill,
recourse-aware, supported232, legal-scheduler, selector-audit,
independent-bank and boom-first-replay families.  Do not sweep normalized,
seven-pack, source-v3, matrix or paid-source runtime artifacts into either
commit; only the exact implementation paths above and the one generated
Commit-B lock are authorized.

## Immediate post-push sequence

1. Assert `HEAD == origin/main == COMMIT_A`.  Build the repaired construction
   image, generation-shadow suite and broad-admission image in parallel; builds
   do not mutate the shared research job.  The generation-shadow suite uses
   its own `generation-shadow-suite` job and may be installed dormant, frozen
   and published independently.
2. Treat `atlas-cbc-32g-full-2023-w8-v1` as one serialized execution lane.
   First run the exact one-use d594 repair sequence: repair collect from the
   admitted failed execution, independent repair reopen, create-once sidecar
   seal, repaired-image install, original-ID grade-prepare, grade and
   independent grade-reopen.  Preserve every exact launch/provider/result
   receipt.  Never relaunch the failed collect and never regenerate a shard.
3. Still on Commit A, run broad admission: install dormant, prepare from the
   exact parents above, pass its nonpublishing task-0, run the 54 tasks,
   collect, independently reopen, grade and independently grade-reopen.  Never
   install another image on this job while any phase is active.
4. Still on exact Commit A, install the normalized snapshot image and carry
   its task-0 -> publish -> independent-reopen chain to a terminal identity.
5. Freeze the seven-pack request from that normalized terminal and the exact
   candidate-v2 root.  Install the seven-pack image only after the normalized
   execution is terminal, then run task-0 -> publish -> independent reopen.
6. On a clean Commit-A worktree, derive the canonical capture-plan-v3 lock
   from the reopened seven-pack.  Commit and push only that generated lock,
   the durable handoff/evidence update and no measured implementation as
   Commit B.
7. Assert `HEAD == origin/main == COMMIT_B`.  Build the exact-Git source-v3,
   discovery-matrix and FP/SIS images from Commit B; those builds may run in
   parallel.  The FP/SIS public build must verify both requested and provider-
   resolved Git SHA, retain the provider build ID and immutable image digest,
   publish its runtime-build attestation create-once, and exact-reopen that
   attestation before reporting build success.
8. Resume the single shared-job lane with source-v3.  Install its Commit-B
   image, run the real ordinal-zero worker, run the distinct write-disabled
   verifier, publish all 54 source tasks only through that exact-name gate,
   and independently reopen the full source-v3 terminal.
9. After source-v3 is terminal, install the discovery-matrix image and carry
   task-0, 54-task construction, collection, 54-task streamed reopen and
   reopen collection to the exact terminal registry.  Do not install FP/SIS
   until this chain is terminal.
10. Build the FP/SIS prepare input only from the exact source-v3 terminal, the
   exact discovery-matrix terminal and the exact-reopened runtime-build
   attestation.  `prepare` must bind the immutable image, full Commit-B SHA
   and provider build ID.  Install the image dormant, launch one provider
   task-0 execution, retrieve that exact execution result, and validate the
   provider task-0 gate including execution name/UID, completion, provider
   spec, request, image, code and build bindings.  Only then may the 54-task
   FP x SIS execution launch.  Continue with exact-publication collection,
   independent reopen, realized grade and grade-reopen without mutating the
   shared job between phases.
