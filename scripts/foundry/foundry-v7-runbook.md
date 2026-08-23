# Foundry v7 runbook — two concurrent lanes over the 54 historical slates

SUPERSEDES `foundry-v6-runbook.md`. v6's single 54-task batch died with
its task-0 producer: exactly one cell of 7,000 (arm 0, visit 573) has a
correct branch-and-bound collision proof needing ~91 s locally, which
crossed the 120 s per-visit budget under 7-worker cloud contention; the
all-optimal law fails a task for one timed-out cell, and finish-batch
demands every task of a batch, so the batch could not survive. Local
reproduction of the full visit range proved all 100 cells optimal given
time (no classifier defect). Repair `0c7d8cc`: deadline raised to 600 s
(execution bound, not a selection input — no science change), tests
derive from the constant.

v7 additionally splits the same 54 source slates into TWO half-batches
on two REUSED jobs so lanes run concurrently (~halving wall-clock) and a
single-task failure burns one lane, not both:

- Lane A: source tasks 0–27, job `atlas-minimal-c-s2023-w1-v1`
  (UID `d6e4b8c1-5950-46b7-8869-7e34dbf29ad2`)
- Lane B: source tasks 28–53, job `atlas-cbc-32g-full-2023-w8-v1`
  (UID `1f4bcf0a-2300-4afa-9fc1-9981844c8275`, idle since 2026-08-17,
  same 8-CPU/32Gi shape; job UPDATE only — never create)

The R6 preregistration's panel is the union of both lanes' accepted
tasks — the same 54 source slates; the split was fixed before any lane
score existed and its manifests bind into the prereg's identity-only
Bindings section.

## Frozen v7 identities

- Code SHA: `2aba4aefdc98b71e874195c85944c72f4b707c58` (pushed `main`;
  carries the 600 s deadline, the lane lattices, the lattice-derived
  execute-path count laws, AND the second-best uniqueness certificate —
  the collision stage now maximizes the witness-excluded combined
  objective and proves the runner-up strictly below the optimum by
  exact integers, replacing the pinned-equality infeasibility proof
  whose tree-closure ran a real cell past 39 unbounded CPU-minutes; all
  seven v6-failed cells now certify in 0.8-1.38 s). Superseded unused images:
  `1d27f45f` at `0c7d8cc` (the preparer's strict HEAD-equality law
  forbids lane preplans from a worktree not at the image commit, and
  the lattices landed after that commit) and `1a017a13` at `6b05db2`
  (three execute-path count laws were still pinned to the 54-task
  production constant, so both lane foundation executes refused
  fail-closed pre-write with "preflight task count differs" — nothing
  was published and the v7a/v7b namespaces stayed virgin).
- Cloud Build: `b75297ee-f161-4c10-ba2d-5333efb0bde4` (corpus config;
  superseded unused: `4ea157a4`@`b7f9c98` — its image predates the
  second-best certificate and a hard cell would time out its lane)
- Worktree: `/tmp/nfl-predictions-corpus-2aba4ae` (recreate after reboot)
- Namespaces: `20260823-corpus-parametric-production-{foundation,batch}-v7a`
  and `-v7b`. v6 namespaces are BURNED (task-0 launch consumed + failed;
  never retry, never reuse the names; terminal evidence retained under
  `reports/corpus-parametric-runs/20260822-foundry-production-v6/`).

## Per-lane sequence (lane = a then b; independent after step 2)

1. v7 build SUCCESS → per lane: capture
   `governance-live-v7<lane>/build-metadata.json`
   (gcloud builds describe b75297ee… --format=json).
2. `foundry_v7_iam_move.sh` (dry-run, inspect, `--execute`) — ONCE for
   both lanes (moves both conditions to cover v7a+v7b prefixes).
3. `python scripts/foundry/build_foundry_lane_preplan.py --lane <lane>
   --image-commit 2aba4aefdc98b71e874195c85944c72f4b707c58
   --worktree /tmp/nfl-predictions-corpus-2aba4ae`
   → validate → dry-run → `execute --preplan … --execute` once
   (CORPUS_PARAMETRIC_BATCH_PREPARER_ENABLED=1), all FROM the image
   worktree — the image commit contains the lane lattices, so preparer
   worktree and image commit are the same and the builder's byte-identity
   cross-check is trivially exact.
4. `python scripts/foundry/append_foundry_lane_identities.py --lane
   <lane> --append`.
5. `python scripts/foundry/capture_foundry_lane_iam.py --lane <lane>`
   (py311; runs AFTER the IAM move so conditions show v7 prefixes).
6. Source `foundry_v7<lane>_env.sh` → `cloud_corpus_parametric_v1_reuse.sh
   --execute configure` from the worktree → append the contract block to
   the lane env from `configured.json`.
7. `foundry_batch_driver.sh 0 0` → `run_foundry_task0_gate.sh` (each
   lane self-gates on ITS first task: exact-identity reopen + per-arm
   all-optimal census + verifier acceptance) → `foundry_batch_driver.sh
   1 <last>` (lane a: 27, lane b: 25).
8. `finish-batch` per lane; realized grader only after BOTH lanes'
   complete acceptance (one read, per the frozen R6 preregistration).

## Timeline reality

- ~70–110 min per task (producer) + ~10–15 min verifier, per lane.
- Two lanes ≈ 27–28 tasks each ≈ 24–30 h to full acceptance.
- Under the second-best certificate the worst observed real cell is
  1.38 s; the 600 s deadline carries ~430× margin.

## Never

- Never relaunch anything v2–v6; never create a Cloud Run job; never
  repeat IAM/Scheduler census per task; never report scores before
  verifier acceptance; never read realized outcomes before both lanes
  finish and the single grader read.
- Never build corpus images from the main cloudbuild.yaml or a dirty
  local config — only the tracked
  `cloudbuild.corpus-research-expansion.yaml`.
