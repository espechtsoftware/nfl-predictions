# Saturday morning refresh: prepared runner and fixed operator window

**Completed:** the [refresh results](2026-09-19-morning-refresh-results.md) record validated completion15:11:33UTC and release of all three lanes15:11:34UTC. The preparation and observed readiness history below are retained. Fixed15:20timer recreation and later build starts were still pending when this completion note was added.

The overnight three-fix release and workstation activation are complete. This is the normal fresh-input feature → TabPFN → projection refresh for the **15:30UTC / 10:30CDT** build. It uses the same deployed images, ordinary selector, chosen doses, contests and historical cache.

Erich assigns the refresh to the laptop (lab `04c7f58`). All six host units are verified on clean `2dc116c` (`730ed69`). The operator will hold **both** Saturday build timers after laptop readiness, then recreate the reviewed transient units at fixed **15:20UTC**, whether or not the refresh has completed (`dddce34`, `b1386c6`). Stopped transient units can disappear; restoration means running the reviewed recreation command, not `systemctl start`.

## Clock and ownership

- **14:33–14:38UTC:** laptop acquires all three canonical registry lanes and completes read-only freshness, scheduler, template, source and provider checks. Post explicit readiness around14:35.
- **Around14:40:** operator holds D12800/15:30 and D6400/15:35 timers. The workstation supplies a committed fresh receipt that both timers and services are inactive or absent, source/cache pins remain correct, and no competing manual build/refresh will launch.
- **14:45:** laptop starts only after validating that receipt. No readiness by14:45 means no hold and no refresh. The runner refuses a start after14:46.
- **15:20:** operator recreates the reviewed units at the fixed time. Laptop reports completion or any failure immediately; it does not request extending the hold after starting.
- **15:30 / 15:35:** scheduled consumers. A partially completed or ambiguous refresh must never be described as certified just because the timers are restored.

Previous provider durations were5m07s features,13m55s cache and4m16s projections, plus checks and the roughly1minute CLI proof. This makes the35minute window plausible, not guaranteed. There is no automatic mutation retry or failure rollback. Any nonzero/ambiguous execution is reconciled against its exact provider identity before further action.

## Fixed sequence

The [runner](reviews/evidence/2026-09-19-morning-refresh.py) and [nested registry launcher](reviews/evidence/2026-09-19-morning-refresh-launch.sh) acquired the three lanes at14:35:50UTC and passed readiness at14:36:19.608528UTC. The [readiness receipt](reviews/evidence/2026-09-19-morning-refresh-readiness.json) preserves the actual checks. At that point the runner was waiting for the actual operator hold and fixed14:45 start; no shared-table refresh had begun. The [manifest](reviews/evidence/2026-09-19-morning-refresh-manifest.json) pins dependencies, private template identities and the existing host cache by content. Its producer hash identifies the preparation version and deliberately is not a self-hash validation gate.

1. Verify all deployed templates, resolve the mutable projection image tag to its approved digest, and repeat the provider census. Confirm the exact scheduler set has no Saturday writer. Verify all36 source schemas, original snapshot identities and the view definition. Require today's injury/weather/odds/props captures, including complete13-game support for the latter three and the14:30 props arrival.
2. Validate a fresh operator hold receipt. Create a new36-table same-timestamp snapshot set in `nfl_release_20260919_morning`, with14-day retention. Verify source etags, row/schema/partition/clustering identity and one snapshot timestamp. These preserve the already repaired last-good state; the original pre-repair snapshots remain untouched.
3. Execute unchanged `build-features`; require normal leakage checks, unique keys, current Week2 usage support and no Week1 future support.
4. Execute unchanged strict-prior `tabpfn-gen`, with only per-execution `TABPFN_UPCOMING=2026:2`. Require exact logged temporal context, full-refresh mode, finite ordered unique quantiles, all upcoming keys and no missing historical keys.
5. Execute unchanged `project-slate`; bind one exact batch to its provider execution, validate player/DST identity and ordered finite values, unchanged model and the real-prop consumer evidence. Fallback-inclusive counts are not pure Odds coverage.
6. Run the same complete D160/K97 CLI proof using clean `2dc116c` and the authenticated existing host cache. Require the new exact projection batch, current game inputs and97unique legal rows. This is an engineering proof, not production-dose efficacy.
7. Publish the validated receipt once, exit all writer wrappers, reconcile terminal lane receipts, and send exact execution IDs, batch, proof and released-lane confirmation to the workstation.

Each job rechecks lane ancestry, provider census, template identity, STOP flag and build deadline. No image or template update occurs. The morning sequence does not replace the historical cache and cannot change entry files.

## Validation and pending actions

Early read-only preflight at12:21UTC passes deployed template/digest checks, scheduler census, all36source schemas, original rollback identities, view definition and clear provider execution census. It deliberately cannot establish freshness for inputs due later. Fourteen offline tests exercise hold refusal and actual nested registry acquisition, ancestry and terminal release using isolated test lanes. The first test run used the wrong completion-directory name in its assertion; correcting the test to the registry's actual `launcher-completions` path resolves it without changing the registry.

The exact hold contract is documented in the accompanying workstation handoff. Laptop materializes the local receipt only from committed evidence of a real operator hold; a template is never accepted as a completed hold. The scheduled props job `ingest-props-qsg4x` completed at14:35:08.636050 after a slower container start. Readiness then confirmed today's injury/weather/odds/props timestamps and complete13-game weather/odds/props support. READY was published in lab handoff `cbba2f9`. Actual hold, refresh execution and completion remain pending in this14:40 status update.
