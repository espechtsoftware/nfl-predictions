# Foundry v5 production runbook — SUPERSEDED by foundry-v6-runbook.md

**SUPERSEDED 2026-08-22.** The v4 producer failed terminally (CBC
integer-infeasibility solution headers classified ERROR — fixed in
`bcf31a7`) and the v5 image carries the same defect, so v5 was never
launched and its namespaces are burned. All operation now follows
`foundry-v6-runbook.md`. Retained verbatim below as the design record.

# Foundry v5 production runbook — 54-slate × 7-arm historical scores

"The Foundry" = the fill × retrieval corpus experiment engine. THIS BATCH is
its fill axis only: **54 slates × 7 fill-rule arms under one fixed
exact-80/line-194 selector** — report its results as fixed-selector
fill-ablation diagnostics, never as a fill × retrieval factorial. The
retrieval axis (the 4 accepted laws + the 3 v2 laws) runs later against
per-slate snapshots via the parametric-snapshot adapter, per
`reports/2026-08-22-foundry-roadmap-adaptation.md` and review F3 in
`reports/2026-08-22-foundry-code-review.md`.

## Frozen v5 identities (do not retype hashes — copy from here or recompute)

- Code SHA: `04d6579394af70df7120e81c0196837d29b5ffcf` (pushed `main`)
- Cloud Build: `b2832a18-666d-4260-9d4b-619ad94aa5ae` (SUCCESS 16:34:20Z)
- Immutable image:
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:232c1087471f91a62e1f3a7d7036e7a344dab1c826eedc004cb027d86a2cdadd`
- Engine: deterministic 7-worker parallel generation (commit `b2d8451`),
  ~6-7x wall-clock per task vs the serial v4 shape.
- Reused job: `atlas-minimal-c-s2023-w1-v1`, expected UID
  `d6e4b8c1-5950-46b7-8869-7e34dbf29ad2` (job UPDATE only; never create).
- Service account: `corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com`
- Source publication (REUSED from accepted source-v3):
  `gs://nfl-predictions-503414-corpus-source/research/source/20260821-corpus-artifact-source-authority-v3/governance/publication-completion.json`
  generation `1787367916927834`
- Retrieval terminal (REUSED accepted task-0):
  generation `1787354391156959`

## Hard preconditions (in order)

1. v4 producer `atlas-minimal-c-s2023-w1-v1-l6dll` terminal.
2. v4 chain closed with the exact c60 procedure in
   `reports/2026-08-22-corpus-research-engine-live-handoff.md`
   (watch-producer → launch-verifier → recover-verifier → watch-verifier →
   finish-batch). The job must have NO active executions before v5 configure.
3. v4 accepted result retained — it is the equivalence baseline.

## v5 sequence

1. Clean worktree: `git worktree add /tmp/nfl-predictions-corpus-04d6579 04d6579394af70df7120e81c0196837d29b5ffcf`
   (recreate after any reboot; verify `git status --porcelain` empty).
2. Build the production preplan from the v4 preplan as template
   (Python 3.11, PYTHONPATH=<worktree>/src): load
   `reports/corpus-parametric-runs/20260822-corpus-parametric-task0-smoke-v4/foundation-live/preplan.json`,
   override: new `batch_id`/`foundation_id`/prefixes (v5 production names),
   `mode="production"`, `source_task_indexes=list(range(54))`, fresh
   timestamps, and a `code_source` recomputed against the worktree files +
   the v5 build/image identities above; call
   `prepare_corpus_parametric_batch_v1.build_preplan(**values)`.
3. Gate: `prepare_corpus_parametric_batch_v1.py validate --preplan ...` then
   `dry-run` (expect 54 tasks, 7 arms, zero writes). Fail-closed on any
   surprise — do not hand-edit around a validator.
4. Move the two narrow corpus-parametric runtime IAM conditions from the v4
   foundation/batch prefixes to the v5 prefixes on bucket
   `nfl-predictions-503414-corpus-parametric` (inspect current policy first;
   replicate the v4 condition shape exactly). Single bounded census comes
   next — never repeat per task.
5. Execute the foundation once (non-TTY): `execute --preplan ... --execute`.
   It must reopen/verify all 270 Atlas artifacts and publish the batch
   manifest carrying all 54 task definitions. Task-request OBJECTS are
   deliberately not published (`publish_task_requests:false` is the v5 law):
   the transport deterministically synthesizes and rebinds each task request
   from the exact manifest and contract at launch time. Never relaunch the
   create-once foundation because zero task-request objects exist.
   Record foundation/manifest/evidence-contract/retrieval-prerequisite
   identities from its completion output.
   DONE 2026-08-22: status=created, 270/270 exact GETs, 54 tasks; identities
   frozen in `foundry_v5_env.sh` and HANDOFF.md.
6. `cloud_corpus_parametric_v1_reuse.sh --execute configure` (initial
   configure: updates the job to the v5 image, one IAM capture + one
   all-region Scheduler census, creates the 6h deployment attestation).
   Run dir: `reports/corpus-parametric-runs/20260822-foundry-production-v5/transport-live-v5`.
7. EQUIVALENCE GATE — task 0 only (same slate 2023-w01 as v4):
   `foundry_batch_driver.sh 0 0`. After acceptance, compare task-0 science
   against accepted v4: per-arm visit rosters, unique-lineup unions,
   score-matrix SHAs, exact-80 selections, arm metrics. Law/binding hashes
   differ by construction — compare science only. Write the comparator
   against the real v4 artifact, then freeze it beside this runbook.
8. On equivalence PASS: `foundry_batch_driver.sh 1 53` (sequential tasks;
   each = launch → recover → poll → close → verify → accept). Each accepted
   task is one slate's 7-arm scores — results accumulate incrementally.
9. `finish-batch` after task 53. Then the one-read realized grader on the
   complete accepted batch.

## Timeline reality (assumes v4 measures ~2s/visit serial)

- Parallel producer per task ≈ 35-50 min + verifier ≈ 10-15 min.
- 54 tasks sequential on the single job ≈ 45-60 hours end-to-end.
- First slates' accepted scores land within ~2-3 hours of v5 configure.
- A second lane on another REUSED existing job could halve wall-clock but
  needs its own contract/attestation design review — operator decision,
  not an improvisation.

## Never

- Never relaunch v2/v3/v4 anything; never mix current-main code into c60.
- Never create a Cloud Run job (JobsPerProject quota is at the limit).
- Never repeat IAM/Scheduler census per task (attestation hot path only).
- Never report a task's scores before its verifier acceptance.
