# Morning refresh completed and validated

The authorized Saturday refresh passed all three cloud stages and the actual D160/K97 lineup-builder proof. Validation completed at**15:11:33UTC /10:11:33CDT**; all three canonical writer lanes exited successfully and released at15:11:34UTC. The workstation independently confirmed the three provider executions and exact projection batch in handoff `9e1b0a5`.

At this15:14UTC report update, the operator's fixed15:20timer recreation and15:30/15:35build starts remain future observations. Refresh completion does not claim those later actions have already happened.

## Executions and exact output

| Stage | Exact execution | Provider completion UTC |
|---|---|---|
| Features | `build-features-cx2px` | 14:52:34.484430 |
| TabPFN cache | `tabpfn-gen-29lsc` | 15:06:31.932609 |
| Projections | `project-slate-6lzdv` | 15:10:00.062252 |

The exact new projection batch is **2026-09-19 15:09:52.915006+00:00**:505rows, comprising473skill players and32DSTs. Model version remains `pooled/components__tail_k1/2026-W32`. Player identifiers are unique and non-null where required; quantiles are finite and ordered.

The cache has66,332unique finite ordered forecast rows, all877expected upcoming player keys and no missing historical forecast keys. Its logged context is strictly before2026Week2, with full refresh mode and the planned per-execution upcoming target. One training-source key disappeared in2026Week1; the [keys-only comparison](reviews/evidence/2026-09-19-morning-training-key-delta.json) found no historical key changes and opened no outcome values. The separate+1skill projection row is not attributed to that training change.

## Fresh data reached the consumer

Readiness passed14:36:19UTC after the scheduled props collection completed. Today's injury, weather, odds and props captures passed freshness checks; weather, odds and props each cover all13Sunday-main games.

The whole-capture injury comparison confirms246unique players and99designations in the rebuilt injury table, with no missing rows or status/timestamp mismatches. All23designated players matching the inference population now have their current status; previously that input field had0designated rows. See the [source and injury review](2026-09-19-availability-law-source-review.md).

The exact projection consumer has **202/473real-prop rows (42.706%)**, corroborated by202new real-prop divergence records. Overnight coverage was185/472(39.19%). The logged385/473blend count includes fallbacks and must not be presented as pure paid-Odds coverage.

## Builder and ownership verification

The unchanged normal CLI on clean lab `2dc116ce95647a776ba9c36cf194f44d022d03a4` consumed that exact batch and all13validated games. It generated160candidates and wrote97unique legal lineups, with zero DK or strategy violations. It used the existing workstation training cache SHA256 `8aaa5daf5a3ebd12bdb471466dabefdc55f774988ff9437710a4e54467b072b7`.

The proof run is `20260919T151024628419Z-2dc116c`. This is a small engineering proof, not full-dose efficacy or an entered book. Generation doses, selector, model, host cache and contest entries were not changed by this refresh.

Before rebuilding, the runner created and verified36same-time snapshots in `nfl-predictions-503414.nfl_release_20260919_morning`, with14-day retention. These preserve the repaired last-good state separately from the original pre-repair snapshots. No job submission was retried and no rollback was needed. All deployed templates remained unchanged.

## Reviewable evidence

- [Validated completion](reviews/evidence/2026-09-19-morning-refresh-validated.json) and [terminal lane release](reviews/evidence/2026-09-19-morning-refresh-released.json).
- [Actual CLI proof](reviews/evidence/2026-09-19-morning-refresh-live-cli-proof.json), [cache validation](reviews/evidence/2026-09-19-morning-refresh-cache-validation.json), [projection validation](reviews/evidence/2026-09-19-morning-refresh-projection-validation.json) and [feature support](reviews/evidence/2026-09-19-morning-refresh-feature-support.json).
- [All36backup validations](reviews/evidence/2026-09-19-morning-refresh-backup-validation.json) and [publication identities](reviews/evidence/2026-09-19-morning-refresh-publication.json).

All nine published JSON receipts are create-once objects under `gs://nfl-2-506823-lab/research/week2-input-release-20260919/morning-refresh-v1/`, with generations, byte counts and SHA256identities recorded and downloads verified. Private deployed job configurations and credentials are excluded.

The [Saturday scoring recommendation](2026-09-19-saturday-scoring-recommendation.md) still requires current-status/full-corpus review before choosing Sunday's final selection and ordering. This refresh establishes a validated fresh-input build path; it is not a new actual-NFL scoring result.
