# Tonight's projection-only QB trial: release plan

Authorized by the operator after the downstream limitation was explained, relayed in lab shared commit `81d809f`: **“Tonight.”** The laptop owns this release. This is a partial projection policy; the corrected host replacement step separately protects final admission. It is not a complete repair of the generator's backup-QB tails.

## Scope and current state

Only `project-slate` changes image. Preserve `GAME_SIM_MODE=possession`, `MODEL_ENSEMBLE=1`, `MODEL_REGISTRY_VARIANT=tail_k1`, `BLEND_MODEL_WEIGHT=0.45`, project configuration, the secret reference, command/args, resource limits, task count, retries, service account and timeout. Do not modify the running lab build or any schedules.

Read-only inventory at 20:20 UTC: job generation **67**, no active project-slate execution; last successful release remains `project-slate-6lzdv`. Existing image tag `week1-live-193e1b44d2b4` resolves to:

`us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:f630fc8c88ed1625fa7873d959e0dcc217a55bd4d95b4e0edb9c1386fb3d5f5d`

Sunday's projection scheduler is enabled at **06:00–11:00 CT hourly**. The host's 05:30 CT build precedes the first of those, which is why tonight's validated batch matters. Preserve the scheduler unchanged.

The candidate branch initially reviewed was `production/qb-availability-gate-20260919` at `d879beba`. The final build must use the corrected unique-primary classifier after review, with its exact SHA and passing tests recorded. Compared with existing image source `193e1b44d2b4`, that branch's projection path changes only the reviewed cascade helper and its return hook. Other source differences are ingest/ownership and a research producer; record the final diff again before building. The normal bounded live-image build performs the existing cloud checks; include the new cascade tests in release validation.

## Execution and verification

1. Review the final classifier and rerun the targeted existing and independent boundary tests. Record real input-only gate membership and prove non-gated rows are untouched by the pure post-projection transformation.
2. Build an immutable candidate image and record source SHA, Cloud Build ID, completion and registry digest. Do not deploy a mutable tag. Preserve the existing image digest above.
3. Acquire the canonical `project-slate` launcher lane through `scripts/launcher_registry.sh`. Recheck provider executions, template identity and the next scheduled invocation before mutation; retain the lane through executions and verification. Never retry an ambiguous execution request without reconciling the provider record.
4. Change only the image. Verify the installed task settings against the captured configuration. A same-image control execution with `QB_BACKUP_GATE=0` may be used to distinguish new-image/input drift from the gate itself; this override belongs only to that execution. Then execute the normal gated job. Announce each exact execution name in the shared handoff as soon as available.
5. Require provider completion and succeeded task count, exact deployed digest, fresh complete projection batch, unique identifiers, finite ordered projections, and the same model registry variant. Compare the exact gate membership against the input-only live feature capture and log, and compare non-gated values with the control under a declared tolerance. Differences caused by input changes must be identified, not attributed to the gate.
6. Production independently verifies the published batch. Record the source/batch identities in the handoff and preserve them for the next host build. Verify the final host replacement uses the corrected shared classifier and current statuses.

The input-only capture at 20:22 UTC records **473 skill rows** plus **30 DST rows** in the upcoming-feature query. The previous published batch has **505 total rows** because the DST projection path also supplies Bills/Lions; this difference is already present before release and must not be mislabeled as a gate regression. The previous batch timestamp is `2026-09-19 15:09:52.915006+00:00`.

Private raw configurations and parquet captures are under `/home/erich/projects/review-evidence/overnight-20260918/qb-projection-release-20260919/`. The final feature SELECT was restricted to identity/role/status columns while retaining the production joins, filters and structural checks. No current-week outcomes were queried or decoded.

## Rollback

Restore the recorded prior image digest under the same lane and verify other settings are preserved. An image rollback alone does not replace a newly published projection batch: execute the restored job and verify that its complete fresh batch becomes the latest one. Preserve the failed trial evidence. An explicitly recorded `QB_BACKUP_GATE=0` setting plus a new execution is an alternative emergency disable, but restoring the previous digest is the complete implementation rollback.

No Cloud Run mutation has happened as of this plan's creation. Review fixes are being completed; the existing authorization covers the necessary preparation, release and verification.
