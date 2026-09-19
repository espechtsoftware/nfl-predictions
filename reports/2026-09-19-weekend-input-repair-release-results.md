# Weekend input repair: cloud release complete, workstation activation pending

Completed September 19, 2026 at **06:39:59 UTC / 01:39:59 CDT**, ahead of the 10:30 CDT build. The three authorized input repairs have passed the live cloud refresh and complete CLI proof. The workstation code pin remains a separate step; this report does not claim it has changed.

| Stage | Actual execution / evidence | Result |
|---|---|---|
| Backup | 36 snapshots at 05:43:40.913Z, plus saved view | Schemas/counts/partition identities verified; 1,612,228 rows, 14-day retention |
| Features | `build-features-x4b8z` | Normal leakage checks pass; Week 2 has 397 prior-game and 396 snap-supported rows; unique salary/inference keys |
| TabPFN | `tabpfn-gen-zdcj2` | Strictly prior season/week context, 66,332 unique finite ordered rows, all 877 expected Week 2 keys, no missing historical keys |
| Production projections | `project-slate-x268x` | 504 rows at 06:29:00.515884Z; unchanged registered model; unique correct player/defense keys, finite ordered predictions |
| Actual CLI | Clean lab `2dc116c`, authenticated existing host cache | D160, 97 unique legal lineups, zero DK/strategy violations, 13 current games, exact projection batch; 66 seconds |
| Writer release | Three registry completions at 06:39:59Z | All exit 0, no active release receipts, recorded wrapper PIDs gone; final provider census clear |

The CLI used ordinary DUAL_EMAX, seed 2026, 10,000 worlds per component and K1 component models, with every normal guard enabled. No low-level or dirty-tree override, entry upload, new target prior, live cache replacement or selector change. The proof's small dose validates mechanics, not production-dose timing or real NFL improvement. The existing workstation historical cache remains SHA256 `8aaa5daf5a3ebd12bdb471466dabefdc55f774988ff9437710a4e54467b072b7`.

Production centering matched 397 skill players and all 26 defenses in the proof's live frame. Five low-projection fallback skill rows appeared in zero generated or selected proof lineups. The naive top-lineup projection was 161.74. Projection output covers the wider weekly pool, so its 504 rows and 32 defenses are not the entered 13-game group count. The entered draft group remains **153428**.

## Actual paid-prop consumer evidence

The exact production helper matches real prop estimates for **185/472 skill rows (39.19%)**. The execution log's `market blend source: props (384/472 rows)` includes DraftKings fallback estimates and must not be described as 81% real-prop coverage. The new div_shadow batch has exactly 185 rows at 06:28:50.672Z. The week's total 355 rows comprise the previous September 17 batch of 170 plus this new batch; it is not a competing count for this execution. The other agent independently confirmed the log branch and corrected its earlier claim that logs were absent: the earlier query used a one-day freshness window for a two-day-old execution.

## Diagnostics resolved during release

Historical feature differences were investigated before proceeding: original usage SQL plus the old salary snapshot reproduces the refreshed historical usage exactly when paired with current raw inputs. Time travel isolates one newly available player-ID mapping and three historical activity records; other observed changes are floating reduction roundoff. These are documented source-refresh effects, not an unexplained salary-patch deviation. Leakage checks were never weakened.

The initial image guard stopped on gcloud's clientVersion metadata change before any execution; the actual task template was unchanged. The resumed supervisor reverified all snapshots and source identities and skipped the already-applied image change. Later, the read-only projection validator initially mistook intentionally null DST GSIS IDs for duplicates, and another invocation stopped because the explicit local project environment was missing. The corrected identity contract and explicit project passed; failed logs remain preserved. No ambiguous cloud execution was retried.

## What remains before the build

The workstation runtime-pinning step has the operator's existing three-fix authorization, but the latest verified state remains unapplied. **Correction to this report's previous revision:** workstation `b303440` incorrectly described a read/verify rejection as a patch-apply rejection. Its follow-up `8df3fe8` supplies the full command: it read the operational tree and materialized a patch only in scratch space, with no `git apply`. The earlier read commands now pass. No host mutation, timer re-arm or activation-runner invocation was actually attempted or rejected. The reported capability blocker is therefore withdrawn, not routed around.

The laptop then asked the workstation agent to proceed under the existing explicit authorization and reviewed gates. **A subsequent real activation attempt was rejected**, documented in `d8ee83f` (commit timestamp 07:36:28Z): the command included applying the reviewed arm patch and materializing the runner, and Claude Code's automatic approval review returned `[Modify Shared Resources]`. A follow-up read-only check was rejected with `[Auto-Mode Bypass]`. The agent stopped without retrying or using another route. This is the first recorded host-mutation denial and is distinct from the withdrawn earlier account. Post-attempt state has not been independently verified; do not claim it was.

The package remains ready, but someone with permitted workstation access must verify the state and complete the reviewed steps. Operator instructions exist at `/home/erich/week2-RELEASE-STEPS.md`; their existence alone does not establish activation. The correct materialized runner path is `/home/erich/week2_runtime_pin.sh` (underscores), now corrected in the release plan. The remaining issue is the workstation's execution restriction, not a new adoption decision or missing user authorization.

The latest **verified pre-attempt** host state is clean production `78d9616b`, zero `REL_ENV` patch markers, clean lab `e7255e9`, and six active timers without explicit `CLONE`/`EXPECT_SHA` overrides, using the old runbook default. The Saturday timer specifies the chosen 2,560/10,240 allocation and fires at 10:30 CDT. Before the rejected attempt, all six services were inactive and the clean release checkout and resulting patched-script hash were verified. Exact current state must be rechecked during actual activation; no host activation is claimed here.

The **09:45 CDT refresh remains necessary** after the scheduled newer raw-data arrivals, with its own provider census and single-writer ownership. The laptop offered and accepted agent ownership after workstation `8df3fe8` confirmed no automatic producer and committed to launching none of the sequence. Follow-up `d8ee83f` surfaced standing operator text assigning him the manual commands; that expectation must be reconciled before an unattended launch. The [morning plan](2026-09-19-morning-refresh-plan.md) is prepared, but **no morning cloud job is scheduled or launched**. The laptop will not race a manual refresh or start an automatic chain without consumer coordination. Keep existing candidate doses, entries/contests, selector and historical cache.

The [release/rollback plan](2026-09-19-weekend-input-repair-release-plan.md) contains exact images, source hashes and the full restore procedure. All scheduled builds read the shared refreshed warehouse: an old source pin alone is not an old-input control. Complete rollback requires table/view restoration and image/source rollback in a quiet window.

## Evidence

[Feature validation](reviews/evidence/2026-09-19-release-feature-validation.json), [cache validation](reviews/evidence/2026-09-19-release-cache-validation.json), [projection validation](reviews/evidence/2026-09-19-release-projection-validation.json), [actual host-cache proof](reviews/evidence/2026-09-19-release-live-cli-host-proof.json), [lane completion](reviews/evidence/2026-09-19-release-lane-completion.json).

The proof's 14 artifacts were published once and independently downloaded for byte verification. Manifest: `gs://nfl-2-506823-lab/research/week2-input-release-20260919/live-cli-host-proof-v1/manifest.json`, generation `1789799946211740`, SHA256 `e506da01d2c142914ed6cd75da2cc864ba9368d1da7c74f5a35650a1f06ead39`. [Publication identities](reviews/evidence/2026-09-19-release-proof-publication.json). This is a research proof bundle, not an entered book.
