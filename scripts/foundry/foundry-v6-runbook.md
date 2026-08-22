# Foundry v6 production runbook — 54-slate × 7-arm historical scores

SUPERSEDES `foundry-v5-runbook.md`. v5 was never launched: its image
(232c1087, commit 04d6579) carries the CBC classification defect that
terminally failed the v4 producer on 2026-08-22 (exit 2 after 6h34m,
6,363/7,000 cells ERROR). Root cause: CBC reports branch-and-bound
infeasibility with the solution header `Integer infeasible - objective
value X`; the classifier accepted only the presolve header `Infeasible -
...`, so nearly every CORRECT collision-uniqueness proof on the real
773-player slate was classified ERROR. Small/synthetic models die in
presolve, which is why every local test and the 24-player 700-solve probe
passed. Fixed and regression-pinned in commit `bcf31a7`
(`tests/test_corpus_legal_feasibility.py::
test_classifier_accepts_both_exact_infeasibility_solution_headers`), and
re-verified against the real v5 task-0 pinned inputs: 9/9 probe cells
optimal at 0.8–3.5 s/solve. Terminal evidence:
`reports/corpus-parametric-runs/20260822-corpus-parametric-task0-smoke-v4/terminal-failure-evidence/`.

The scientific framing is unchanged from v5: this batch is the fill axis
only — **54 slates × 7 fill-rule arms under one fixed exact-80/line-194
selector** — fixed-selector fill-ablation diagnostics, never a
fill × retrieval factorial. The retrieval axis runs later against
per-slate snapshots via the parametric-snapshot adapter.

## Frozen v6 identities (copy from receipts — never retype)

- Code SHA: `bcf31a75087a48d7207389fe6a69bf9244f73aeb` (pushed `main`)
- Cloud Build: `b0bfb7b6-cfb4-4016-8e20-9ebee67b5857` (submitted 23:34Z
  from the PRISTINE tracked `cloudbuild.corpus-research-expansion.yaml`
  at bcf31a7 — the dedicated corpus config the preplan's
  build_definition_sha256 pins; it installs jq and runs the complete
  corpus workstream suites). Superseded attempt `588a2b97` FAILED because
  it used the MAIN cloudbuild.yaml: its python:3.11-slim step lacks jq,
  so the two operator-shell tests fail there (3,607 others passed; both
  pass wherever jq exists). Never build corpus images from the main
  config, and never from the dirty local cloudbuild.yaml (its step arg
  exceeds Cloud Build's 10,000-char limit).
- Immutable image: from `governance-live-v6/build-metadata.json` after
  SUCCESS (results.images[0].digest)
- Engine: same deterministic 7-worker parallel generation as v5, plus the
  classifier fix.
- Reused job: `atlas-minimal-c-s2023-w1-v1`, expected UID
  `d6e4b8c1-5950-46b7-8869-7e34dbf29ad2` (job UPDATE only; never create).
- Service account: `corpus-parametric-research@nfl-predictions-503414.iam.gserviceaccount.com`
- Source publication (REUSED accepted source-v3): generation
  `1787367916927834`; retrieval terminal (REUSED accepted task-0):
  generation `1787354391156959`.
- Namespaces: `20260822-corpus-parametric-production-{foundation,batch}-v6`.
  The v5 namespaces are BURNED (bound to the defective image; foundation
  governance objects exist but the batch was never configured/launched —
  leave the objects in place, never reuse the names).

## v4/v5 closure law

- v4: producer terminally FAILED; launch authority consumed; only 3
  transport objects exist under its prefixes; NO close/verify/finish is
  possible or licensed; NO retry ever. The accepted-v4 equivalence
  baseline therefore does not exist.
- v5: never launched; no executions; nothing to close.

## v6 sequence

1. Build 588a2b97 SUCCESS → capture
   `governance-live-v6/build-metadata.json` (gcloud builds describe,
   JSON). The preplan builder refuses anything but SUCCESS at bcf31a7.
2. Clean worktree `/tmp/nfl-predictions-corpus-bcf31a7` (exists; recreate
   after any reboot: `git worktree add --detach ... bcf31a7...`; verify
   porcelain-clean).
3. `python scripts/foundry/build_foundry_v6_preplan.py` (py311,
   PYTHONPATH=worktree src) → validate → dry-run (expect 54 tasks, 7
   arms, zero writes) → `execute --preplan ... --execute` once.
   Task-request objects are deliberately not published
   (`publish_task_requests:false`); never relaunch the create-once
   foundation. Append the four publication identities to
   `scripts/foundry/foundry_v6_env.sh` from `execute-result.json`.
4. IAM: `scripts/foundry/foundry_v6_iam_move.sh` (dry-run, inspect diff,
   then `--execute`) — moves the two narrow runtime conditions v4 → v6.
   Then capture the fresh policy to
   `governance-live-v6/runtime-iam-policy-capture.json` via the
   transport's canonicalize-external-json + build-runtime-iam-evidence
   flow.
5. `cloud_corpus_parametric_v1_reuse.sh --execute configure` with
   `scripts/foundry/foundry_v6_env.sh` sourced. Run dir:
   `reports/corpus-parametric-runs/20260822-foundry-production-v6/transport-live-v6`.
6. TASK-0 GATE (redesigned): `foundry_batch_driver.sh 0 0` (launch →
   recover → poll → close → verify → accept), then
   `bash scripts/foundry/run_foundry_task0_gate.sh` (composes
   `accept_foundry_task0.py` from the closed-task carrier identity in
   `tasks/000-producer-closed.json` and the driver's
   `tasks/000-verifier-accepted.json` — nothing retyped).
   The gate reopens all seven variant results by exact identity and
   requires scheduled=attempted=optimal=1000 on every arm plus verifier
   acceptance — the exact invariant v4 violated. It writes
   `task0-acceptance-pass.json` only on PASS; the driver refuses tasks
   1..53 without it. (The old science-equivalence gate is impossible —
   there is no accepted baseline task anywhere.)
7. On PASS: `foundry_batch_driver.sh 1 53`, then `finish-batch`, then the
   one-read realized grader on the complete accepted batch.

## Timeline reality (measured 0.8–3.5 s/solve on the real slate)

- Parallel producer per task ≈ 35–50 min + verifier ≈ 10–15 min.
- 54 tasks sequential on the single job ≈ 45–60 hours end-to-end.
- First slate's accepted scores land within ~2–3 hours of v6 configure.

## Never

- Never relaunch v2/v3/v4/v5 anything; never mix current-main code into
  the c60 worktree flows.
- Never create a Cloud Run job (JobsPerProject quota is at the limit).
- Never repeat IAM/Scheduler census per task (attestation hot path only).
- Never report a task's scores before its verifier acceptance.
- Never build from the dirty local cloudbuild.yaml (10k step-arg limit).
