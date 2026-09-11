# FP/SIS retrieval-only successor authority

Date: 2026-09-10 (America/Chicago)

Status: implementation authority ready after merge; no cloud query, build,
deployment, execution, publication, outcome read, or policy change performed
by this review

## Decision

The Experiment-5 source chain may use one newly frozen normalized FP/SIS
snapshot. This is an operational successor to the unexecuted prospective
`2026-08-31T05:25:27Z` snapshot point recorded in `HANDOFF.md`. That old
timestamp is outside the repository's documented ordinary seven-day BigQuery
time-travel window and produced no normalized terminal, seven-pack terminal,
capture-plan-v3 lock, or Experiment-5 result.

The successor changes no scientific cell, estimand, candidate population,
world population, retrieval law, admission cap, or entry budget. The sole
four-cell registry remains, in exact order:

1. `fp-on-sis-on-v1`;
2. `fp-off-sis-on-v1`;
3. `fp-on-sis-off-v1`; and
4. `fp-off-sis-off-v1`.

Every cell continues to use the same immutable candidate population and the
same immutable discovery matrix, with raw vendor slices physically removed
before component calculation in the off cells. The joint component remains
available only in the on/on cell. The experiment remains retrieval-only,
`coverage-194-v1`, A200, K80, development-only, and unable to promote policy.

## Why a fresh source freeze is scientifically admissible

The normalized producer's data domain is already fixed in code. It projects
only seasons 2022--2025 from these six relations:

- `fantasy_points_route_share`;
- `fantasy_points_alignment_player_l4`;
- `fantasy_points_receiver_coverage_prior`;
- `fantasy_points_defense_coverage_prior`;
- `sis_receiver_copula_player_game`; and
- `sis_team_run_context_game`.

The 2026-08-31 read-only preflight observed 64,715 source rows: 46,008
Fantasy Points rows and 18,707 SIS rows. Those counts are historical evidence,
not a substitute for a content identity. No immutable normalized terminal was
ever published, so there is no prior terminal whose bytes could be silently
replaced or relabelled.

A successor request must select one canonical UTC second before its first
warehouse query and retain that exact request unchanged. The producer binds
the fixed SQL, provider job, projected row bytes, relation schema/metadata,
canonical shards/manifests, and create-once generations. It rejects an empty
registered slice and rejects any relation whose exact millisecond
`last_modified_time` is later than the requested snapshot. Therefore a table
change after the request cannot be silently admitted; that namespace must
remain terminal-absent and any later attempt needs a separately named,
explicit successor request.

This establishes exact retrospective normalized content, not original-vendor
point-in-time acquisition. Every resulting authority must continue to state
`evidence_class=retrospective-prior-period-reconstruction` and
`authoritative_pit=false`.

Current-table byte equality to the never-published 2026-08-31 projection
cannot be proved from the repository alone. If byte equality to that abandoned
prospective point is required, production must perform a separate outcome-
blind comparison against a retained dated backup before publication. It is
not required by the frozen four-cell estimand; the first successful immutable
snapshot is the experiment's source-content authority.

## Exact prerequisite DAG

```text
six fixed normalized FP/SIS relations
        |
        v
normalized snapshot task0 -> publish -> independent reopen
        |
        v
candidate-authority-v2 root -> seven-pack task0/publish/reopen
                                  |
                                  v
                         capture-plan-v3 lock (Commit A bytes)
                                  |
                                  v
                        track lock in Commit B
                                  |
                                  v
                      source-v3 worker -> distinct verifier
                                  |
                                  v
                      full 54-slate publish -> reopen ----+
                                                              |
candidate-authority-v2 root -> discovery-matrix prepare       |
LR8 later-source freeze -----> task0 -> 54 tasks -> collect    |
                               -> 54 reopens -> reopen collect -+
                                                              |
                                                              v
                                      FP/SIS execution request/task0
                                      -> 54 score-free cells -> collect
                                      -> independent reopen
                                      -> separately leased grade/reopen
```

The seven-pack contains exactly five warehouse-derived free packs plus the
two paid packs derived from the normalized terminal. It performs five bounded
warehouse jobs and publishes seven row objects, seven provenance objects, and
the root as object 15 last. The capture-plan bridge first deep-reopens that
release and derives all seven rows and candidate-v2; callers cannot inject
loose paid-source manifests.

The discovery branch is independent of the normalized/seven-pack/source-v3
branch. It constructs 54 candidate-by-40,000 float64 R0--R3 matrices. R4 is
identity-bound and not read. The two branches converge only when the final
execution request binds both terminal identities.

## Fixed predecessor identities

Candidate-authority-v2 root:

```text
uri: gs://nfl-predictions-503414-corpus-retrieval/research/corpus-r6-fixed-g0-candidate-authorities-v2/20260830-fixed-g0-candidate-authority-v2/candidate-authority-release-v2.json
generation: 1788081739195827
sha256: ae6d0ba73ac627f652f2cfc542da3f43885f4b9090885457fa313ecb6a7faea8
bytes: 216639
```

LR8 later-source freeze:

```text
uri: gs://nfl-predictions-503414-corpus-source/research/source/20260821-corpus-artifact-source-authority-v3/source/later-source-freeze.json
generation: 1787367678830738
sha256: c63251a3dee0b455502a8e37d03c731c671457b9b17ff41dd9249edb0bae654a
bytes: 4566802
```

The existing August normalized and seven-pack image digests are build
evidence only. They are not source terminals and must not be substituted for
the fresh successor.

## Exact release sequence

Run only from a clean checkout after this repair is merged and
`HEAD == origin/main`. Use absolute paths for every payload. The identifiers
below are new namespaces, not retries into an old prefix:

```text
NORMALIZED_RUN=20260910-fp-sis-normalized-successor-v1
SEVEN_PACK_RUN=20260910-fp-sis-seven-pack-successor-v1
MATRIX_RUN=20260910-fp-sis-discovery-matrix-successor-v1
SOURCE_V3_RUN=20260910-fp-sis-source-v3-successor-v1
ABLATION_RUN=20260910-fp-sis-retrieval-cross-successor-v1
```

1. Freeze the normalized request locally before any warehouse contact:

   ```bash
   release_root=$(git rev-parse --show-toplevel)
   code_sha=$(git rev-parse HEAD)
   snapshot_at_utc=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
   PYTHONDONTWRITEBYTECODE=1 PYTHONPATH="$release_root/src:$release_root/scripts" \
     "$release_root/.venv/bin/python" \
     "$release_root/scripts/run_corpus_r6_paid_source_normalized_snapshot_v1.py" \
     build-request \
     --run-id 20260910-fp-sis-normalized-successor-v1 \
     --snapshot-at-utc "$snapshot_at_utc" \
     --repository-root "$release_root" > /ABSOLUTE/PATH/normalized-request.json
   ```

2. Build/install the normalized image, then run `task0`, collect that exact
   execution with `result`, run `publish` gated by the exact successful task0
   execution, collect the exact publication, and launch `reopen` against only
   its returned `terminal_identity`:

   ```text
   scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh build CODE_SHA
   scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh install IMAGE CODE_SHA BUILD_ID
   scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh task0 IMAGE CODE_SHA BUILD_ID /ABSOLUTE/PATH/normalized-request.json
   scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh result IMAGE CODE_SHA BUILD_ID TASK0_EXECUTION
   scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh publish IMAGE CODE_SHA BUILD_ID /ABSOLUTE/PATH/normalized-request.json TASK0_EXECUTION
   scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh result IMAGE CODE_SHA BUILD_ID PUBLISH_EXECUTION
   scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh reopen IMAGE CODE_SHA BUILD_ID /ABSOLUTE/PATH/normalized-terminal-identity.json
   scripts/cloud_corpus_r6_paid_source_normalized_snapshot_v1.sh result IMAGE CODE_SHA BUILD_ID REOPEN_EXECUTION
   ```

3. Create a schema-v2 seven-pack freeze spec containing only
   `run_id`, the fixed candidate-v2 root identity, and the returned normalized
   terminal identity. Run `freeze_corpus_r6_matchup_seven_pack_inputs_v1.py`,
   then the seven-pack `build`, `task0`, `publish`, and `reopen` actions in
   order. Retain the exact successful terminal identity and reopen receipt.

4. In the same clean Commit-A checkout, run `freeze-capture-plan` against that
   exact seven-pack identity. It must create only:

   ```text
   reports/corpus-r6-matchup-runs/20260830-r6-matchup-source-v2/capture-plan-outer-candidate-authority-v3-lock.json
   ```

   Commit and push that generated lock as Commit B without changing any
   measured Commit-A implementation.

5. Build the Git-capable source-v3 image from Commit B using
   `cloudbuild.corpus-r6-matchup-source-v3.yaml`. Run the exact-name controller
   phases `worker SOURCE_V3_RUN`, `verify WORKER_EXECUTION`,
   `publish SOURCE_V3_RUN VERIFIER_EXECUTION`, and
   `reopen SOURCE_V3_RUN PUBLISH_EXECUTION`. The final source identity is
   usable only after the distinct write-disabled reopen succeeds.

6. The discovery-matrix branch may proceed independently after its own clean
   build. Its prepare input contains exactly the fixed candidate root, fixed
   LR8 later-source freeze, and its code/image/build-attestation identities.
   Run `prepare`, `task0`, `task`, `collect`, `reopen-task`, and
   `reopen-collect` in that order, always naming the exact preceding execution.

7. Build the FP/SIS image only from the settled execution commit. Its prepare
   input must contain exactly the independently reopened source-v3 release,
   independently reopened discovery-matrix terminal, runtime build
   attestation, `ABLATION_RUN`, and one explicit UTC `frozen_at`. Run task0
   before the 54 score-free tasks. No grade may read outcomes until the
   score-free terminal independently reopens and the recognized historical
   outcome lease is confirmed live.

## Residual gates

- merge this precision repair and ensure the settled release commit is durable
  `origin/main`;
- choose and freeze the exact successor `snapshot_at_utc` before first query;
- obtain fresh normalized build/image/attestation and exact task0, publication,
  terminal, and independent-reopen identities;
- obtain the seven-pack terminal/reopen identity;
- generate and track the absent capture-plan-v3 lock in the required second
  commit;
- obtain the Commit-B source-v3 build, worker, verifier, publication, and
  independent-reopen identities;
- obtain the discovery-matrix build/attestation, terminal, and independent
  reopen terminal;
- build the final FP/SIS runtime and bind both converged terminals; and
- keep the shared Cloud Run job serialized and idle before every installation
  or launch.

Any missing identity, relation newer than the frozen snapshot, nonempty-slice
failure, task0 mismatch, partial namespace, failed deep reopen, moving Git
head, nonterminal shared job, or outcome access before the grade lease is a
hard stop. No fallback source, old source-v3 release, loose manifest, current
object resolution, or relabelled failed prefix is authorized.

## Follow-up validation closure

An independent rerun exposed a test-environment contamination hazard. The
shared virtual environment is editable-installed against the primary checkout;
bare `pytest` from an isolated worktree therefore loaded the primary module
while collecting the isolated worktree's tests. The production query was not
missing its cutoff: both isolated-worktree query specs contain the exact
millisecond predicate. `pyproject.toml` now prepends this checkout's `src`
directory ahead of any reused editable installation and retains `.` for the
repository-level `scripts` namespace.

The focused regression also models a source relation modified at
`12:00:00.001Z` against a snapshot frozen at `12:00:00.000Z`. It confirms that
the native-millisecond SQL predicate filters the otherwise same-rounded-second
metadata row and that the producer fails for incomplete relation metadata
before any create-once write.

Validation using the formerly contaminated bare-pytest path is green:

- the independent reproducer's exact normalized/seven-pack subset: **18/18**;
- normalized core, CLI, and cloud contract: **20/20**;
- seven-pack operator, freezer, bridge, and cloud compatibility: **33/33**;
- edited Python compilation and `git diff --check`: passed.
