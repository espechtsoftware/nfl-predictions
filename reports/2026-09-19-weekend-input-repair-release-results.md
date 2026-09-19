# Weekend input repair: cloud release and workstation activation complete

Completed September 19, 2026 at **06:39:59 UTC / 01:39:59 CDT**, ahead of the 10:30 CDT build. The three authorized input repairs have passed the live cloud refresh and complete CLI proof. Workstation activation was subsequently verified at lab `730ed69`; the new morning refresh remains separate.

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

## Current build readiness

**Cloud release and workstation activation are complete.** Lab handoff `730ed69` verifies Erich activated all six units with explicit clean `2dc116c` source, unchanged 2,560/10,240 candidate allocation and the existing historical cache. The earlier read-only/activation-denial discussion is retained in git history; it is no longer a current blocker.

The next task is the normal **14:45 UTC / 09:45 CDT** refresh after newer raw inputs arrive. Erich assigns this to the laptop (`04c7f58`); the workstation launches none of the three jobs. He will hold both Saturday build timers after laptop readiness and recreate the reviewed transient units at fixed **15:20 UTC**, whether or not the refresh is complete (`dddce34`, `b1386c6`). A failed or delayed refresh must be reported immediately; the fixed restore is not evidence of data consistency.

The [morning refresh plan](2026-09-19-morning-refresh-plan.md) now includes a prepared runner, exact hold contract, provider/scheduler/template checks, new last-good snapshots and final validation. Its early read-only preflight passed. **No morning cloud job has launched and no timer has been held.** The live freshness check still awaits the scheduled morning captures. Source, images, selector, dose, contests and historical cache remain as already approved.

The [release/rollback plan](2026-09-19-weekend-input-repair-release-plan.md) retains exact image/source and full restore identities. All builds share the warehouse: an old source pin alone cannot restore old inputs. Morning snapshots will separately preserve the currently repaired state; the original overnight snapshots preserve the pre-repair state.

## Evidence

[Feature validation](reviews/evidence/2026-09-19-release-feature-validation.json), [cache validation](reviews/evidence/2026-09-19-release-cache-validation.json), [projection validation](reviews/evidence/2026-09-19-release-projection-validation.json), [actual host-cache proof](reviews/evidence/2026-09-19-release-live-cli-host-proof.json), [lane completion](reviews/evidence/2026-09-19-release-lane-completion.json).

The proof's 14 artifacts were published once and independently downloaded for byte verification. Manifest: `gs://nfl-2-506823-lab/research/week2-input-release-20260919/live-cli-host-proof-v1/manifest.json`, generation `1789799946211740`, SHA256 `e506da01d2c142914ed6cd75da2cc864ba9368d1da7c74f5a35650a1f06ead39`. [Publication identities](reviews/evidence/2026-09-19-release-proof-publication.json). This is a research proof bundle, not an entered book.
