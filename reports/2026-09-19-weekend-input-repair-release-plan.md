# Weekend input repairs: release candidate and complete rollback

**Prepared, not activated.** This is a concrete option for the Saturday September 19 build at **10:30 CDT / 15:30 UTC**. The usual refresh starts 09:45 CDT / 14:45 UTC. Sunday-main lock is a different deadline: September 20 at 17:00 UTC. The [workstation runtime implementation now passes independent review](2026-09-19-runtime-release-review.md): all42behavioral tests, reconstructed full arm-script hash, and default/candidate `week_env` resolution. Actual release-state checks remain required immediately before activation.

My recommendation is to prepare the three demonstrated input-contract corrections for release, keeping ordinary DUAL_EMAX, existing candidate doses and contest assignments. I do **not** recommend enabling the new target prior or WEMAX based on the completed tests. Final live adoption belongs to Erich under [CLAUDE.md](../CLAUDE.md); no live image, table, source pin or timer has been changed by this work.

## What this fixes and what the evidence establishes

1. **Salary-week resolution:** current-season raw salaries intentionally have null week, but the feature transform required non-null week. This suppressed the entire current-season salary spine and recent usage. Resolve only unique regular-season season/team/Eastern-date matches; preserve explicit weeks and historical precedence. Actual SQL fixtures, 77 targeted tests (one skip), full isolated leakage checks and exact equality of 104,847 historical salary rows pass. [Validation](2026-09-19-salary-week-repair-validation.md).
2. **TabPFN pre-week context:** once current-season rows exist, Thursday's current-week labels can enter the upcoming Sunday's context. Filter before reading labels to season/week strictly before the target week. Fourteen targeted tests, two complete isolated cloud refreshes and peer source review pass. [Validation](2026-09-19-tabpfn-preweek-context-repair.md), [cache results](2026-09-19-tabpfn-scratch-refresh-results.md).
3. **Live hsim game inputs:** the live simulator currently reads benchmark game lines instead of the current validated slate. Ten of 13 archived games have different totals and spreads. Explicit live-game inputs now reach every calibration pilot and final simulation; legacy callers retain their original path. Sixteen tests, exact archived numerical replay and full CLI rehearsals pass. [Validation](2026-09-19-live-hsim-game-input-repair-validation.md).

The complete chain passes at 160 and 1,600 candidates. At D1600 the repaired-input mixture prefers its book by 2.800 expected maximum and 3.695 percentage points P220; the old-input mixture prefers its own book by 2.534 points and 2.360 percentage points. These estimates are conditional on the models and disagree about real-world efficacy. Both co-run arms already use the shared game-input fix, so the control is not an exact operational `e7255e9` replay. Preserved books can be settled after the slate whether or not entered. [Expanded results](2026-09-19-repaired-chain-d1600-results.md).

The engineering case is the demonstrated broken input contracts and temporal correction. The simulation comparison does not prove a scoring gain. Conversely, requiring a known old-input simulator to endorse every repair is not a valid general test of input correctness. The runtime and rollback checks below are still necessary.

## Exact candidate identities

| Component | Candidate | Existing / rollback |
|---|---|---|
| `build-features` image | `nfl-dfs@sha256:8d9b3cb55865edc66c99e01b28a7a6ba0d588458ac921c1485069fac32814e03` | `nfl-dfs@sha256:cdbf96ad190925b2c96a94568f173c4bded328442441838427fa473d2fd450b2` |
| `tabpfn-gen` image | `tabpfn-gen@sha256:fdb120dc2291b7d09538987d97e8b30d0e8fe5f7e9d9d40995b6adcc4d4692d6` | `tabpfn-gen@sha256:7eeff44e7c225fed62682b3649dfa86d77f86227e3e9858c967d132deff2a10a` |
| Lab source | `2dc116ce95647a776ba9c36cf194f44d022d03a4` | `e7255e98bf87297452befb61fb508ad4b368b59f` |
| Target prior | absent / `none` | absent |

Images are under `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/`. Both candidates retain every base layer and change only the verified feature SQL or generator file. `project-slate` requires no source/template change; current tag `week1-live-193e1b44d2b4` resolves to `sha256:f630fc8c88ed1625fa7873d959e0dcc217a55bd4d95b4e0edb9c1386fb3d5f5d`. Relevant inference/model/config/feature source matches the scratch comparison base; that is a source-tag check, not a claim that we independently extracted and matched its complete installed package.

[Machine-readable release plan](reviews/evidence/2026-09-19-release-plan.json), [live metadata inventory](reviews/evidence/2026-09-19-release-inventory.json). Inventory captured at 03:11 UTC and must be refreshed immediately before release. Private job configurations are stored locally with mode 0600; tracked evidence exposes only identities and nonsensitive fields.

The [04:33:38 UTC refresh](reviews/evidence/2026-09-19-release-inventory-refresh.json)
finds all36tables/oneview present, with **no changed table metadata or job template**
against the03:11inventory. An explicit adoption decision has been requested from
Erich; it is pending. No dependent live action is authorized by elapsed time.

## Release sequence

1. Confirm authorization for this exact option. Recheck the live job image/template identities, the prepared workstation checkout and all runtime overrides. Preserve the original clean lab checkout; activate a separate clean candidate checkout, never repoint the old one. Ensure no prior option is accidentally inherited.
2. Census provider executions and competing launchers for `build-features`, `tabpfn-gen` and `project-slate`; obtain the corresponding registry lanes for each complete update/execute/reconciliation chain. Coordinate the multi-job refresh as one writer window. Host registry locks do not prevent Cloud Scheduler or a different machine from invoking a job. The 03:32 UTC scheduler census shows no Saturday feature/projection cadence, but Sunday features run hourly at :30 from 05:30–10:30 CDT and projections at :00 from 06:00–11:00 CDT. Recheck rather than assuming that remains true.
3. **Before any live write, snapshot all 36 affected tables at one timestamp and retain the one view definition.** [Prepared snapshot SQL](reviews/evidence/2026-09-19-release-snapshot.sql) creates a distinct US backup dataset, with 14-day expiration. It deliberately refuses if the dataset already exists. Check that all snapshots completed, record their source snapshot timestamps, schemas, partitions and row counts, and retain the query/execution identities. An incomplete snapshot set is a stop condition. This is a coordinated quiet-window backup, not an atomic 36-table transaction.
4. Within the registered `build-features` launcher, update only its image to the candidate digest, verify that every other template field is unchanged, execute it with normal leakage checks and reconcile the exact provider execution. Retain logs. Verify unique salary week resolution, recovered current-season prior usage, duplicate-key refusal and historical-feature parity relative to the captured pre-write state. Investigate any historical change; do not weaken leakage checks.
5. Within the registered `tabpfn-gen` launcher, update only its image, verify template parity except image, and execute with per-execution `TABPFN_UPCOMING=2026:2`. Keep the existing full-refresh mode. Require the receipt to state strictly prior season/week context, finite ordered quantiles, unique keys, complete target-week support and no missing historical keys. Full cache regeneration can differ from a prior cache because the warehouse SELECT order was not pinned; the isolated comparison used a shared sorted order. Do not claim historical live-cache bitwise preservation from that comparison.
6. Run the unchanged `project-slate` through its registered lane. Require successful roster/identity guards, fresh production projections, the expected registered model variant and the expected props-based market blend. A freshly repaired feature table paired with an old cache or stale projection batch is not a complete release.
7. Run a small complete candidate CLI against the now-refreshed live inputs with every normal guard, retaining its receipts. Require legal and unique lineups, production centering, complete current game coverage, expected source SHA, correct current draft group and no dirty-tree/low-level override. This validates the actual refreshed state; it does not replace the retained D160/D1600 experiments.
8. Activate the reviewed workstation `CLONE`/`EXPECT_SHA` configuration for builds and watchers only after those checks pass. Verify the effective runtime resolution and code identity before the first build. Keep current doses, contest counts, ordering objective and upload workflow. Timer `RUN_TAG` strings contain the old SHA as a label; either update that metadata carefully or explicitly receipt the discrepancy. A timer re-arm is not intrinsically necessary if the wrappers resolve the new defaults at runtime.

Cloud command bodies (to be run **inside the frozen registered launchers**, not ad hoc):

```bash
gcloud run jobs update build-features --project=nfl-predictions-503414 --region=us-central1 --image=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:8d9b3cb55865edc66c99e01b28a7a6ba0d588458ac921c1485069fac32814e03
gcloud run jobs execute build-features --project=nfl-predictions-503414 --region=us-central1 --wait
gcloud run jobs update tabpfn-gen --project=nfl-predictions-503414 --region=us-central1 --image=us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/tabpfn-gen@sha256:fdb120dc2291b7d09538987d97e8b30d0e8fe5f7e9d9d40995b6adcc4d4692d6
gcloud run jobs execute tabpfn-gen --project=nfl-predictions-503414 --region=us-central1 --update-env-vars=TABPFN_UPCOMING=2026:2 --wait
gcloud run jobs execute project-slate --project=nfl-predictions-503414 --region=us-central1 --wait
```

The expected refresh is about 35 minutes in the existing operator checklist, not a hard guarantee. The two isolated cache runs took roughly 14–15 minutes each. D1600 CLI runs took 7–8 minutes on one CPU; do not extrapolate those measurements into a production-dose completion promise. If the refresh/proof cannot finish before a build starts, coordinate an explicit build hold or remain on the complete old state; do not let a timer read a half-refreshed chain.

## Complete rollback

A source/image rollback alone is insufficient: the feature build replaces tables, TabPFN replaces its mutable cache, and projection execution writes new predictions. First stop or reconcile all affected writers and hold builders. Retain the failed candidate receipts and table metadata. Then:

1. Return `build-features` and `tabpfn-gen` to the **recorded pre-release image digests**, verifying all other template fields against the private captured configuration. No source tag guessing.
2. Require all 36 snapshots to exist and match the release manifest. Execute [prepared restore SQL](reviews/evidence/2026-09-19-release-restore.sql), restoring features, mutable cache, `player_projections` and `div_shadow`, and the saved view definition. It uses `CREATE OR REPLACE TABLE ... CLONE snapshot`. Restoration is not atomic; builders stay held until every table is verified. Do not merely rerun old feature code against newer raw inputs and call that a rollback.
3. Restore the workstation's old `CLONE`/`EXPECT_SHA` configuration, leaving both checkouts intact. Restore only scheduler/timer states actually changed during this release, using their captured prior state. Recheck effective runtime identity, table schemas/partitions/row support, cache/projection alignment and normal build guards before resuming.

The actual snapshot, clone and replacement primitives passed a scratch-only rehearsal on salary and projection tables: **18 BigQuery jobs, exact bidirectional row matches, row-count/checksum matches, schema/partition/clustering matches, and unchanged source metadata**. Probe tables expire in three days. This proves the primitive on those two scratch table shapes, not the unexecuted 36-table live restore. [Probe source and result](reviews/evidence/2026-09-19-release-rollback-probe.json).

Google documents [snapshot creation](https://docs.cloud.google.com/bigquery/docs/table-snapshots-create), [restoration](https://docs.cloud.google.com/bigquery/docs/table-snapshots-restore?hl=en), [job image updates](https://docs.cloud.google.com/sdk/gcloud/reference/run/jobs/update) and [per-execution overrides](https://docs.cloud.google.com/run/docs/execute/jobs). The release still requires fresh state checks and applying the reviewed workstation patch; these documents are not an assertion that activation has happened.

## Reviewed workstation commands (after the successful cloud refresh and CLI proof)

Materialize the pinned runner from lab `d7abe2c` to `/home/erich/week2-runtime-pin.sh`,
verify its SHA256 above, and apply the existing arm patch only after checking the
operational source is the reviewed version. Its full resulting SHA256 must match
the value below. Preserve both clean lab checkouts. Then the exact guarded calls are:

```bash
bash /home/erich/week2-runtime-pin.sh release /home/erich/projects/.nfl2-worktrees/week2-release-2dc116c 2dc116ce95647a776ba9c36cf194f44d022d03a4 c1cf827099bfe4b8d73b5a7d55a8533ce45f7c16a52f9c456b6d4bc10bd94424
bash /home/erich/week2-runtime-pin.sh rollback c1cf827099bfe4b8d73b5a7d55a8533ce45f7c16a52f9c456b6d4bc10bd94424
```

Use the second command only as the host portion of the complete rollback above.
The source test seams must be unset in operational use. A nonzero result can mean
partial arming; reconcile the runner's actual per-unit report before retrying.
