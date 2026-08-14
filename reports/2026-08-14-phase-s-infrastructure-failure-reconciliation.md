# Phase S infrastructure failure review reconciliation

Date: 2026-08-14. This reconciles
`reports/2026-08-13-phase-s-infrastructure-failure-review.md` against the
actual launcher, analyzer, Cloud Run execution specifications and live retry
state. No outcome was read and no scientific arm, seed, feature, allocation
law or decision rule was changed.

## Accepted findings

- The observed failures are infrastructure failures. Each retry remains
  byte-identical and is permitted only after candidate rows, feature rows and
  candidate-world artifacts are all confirmed absent.
- A launch delay is not an in-flight concurrency bound. Thirty 8-CPU/32-GiB
  cells released in fifteen minutes requested 240 vCPU and 960 GiB. The last
  recorded `us-central1` quota is 200 vCPU and 400 GiB, so the original burst
  exceeded the memory quota by 2.4x before allowing for any other work.
- Retry provenance should not depend on a human placing an execution ID in the
  correct ledger row. An execution-owned specification check is appropriate.
- BigQuery transient-read retry and replay checkpointing are useful before a
  future multi-cell panel. They cannot repair the already-frozen Phase S image
  without changing that image, so they are not being introduced into this
  experiment.

## Important qualifications

The review's single-root-cause claim is stronger than the evidence. The Phase
S image is already co-regional in `us-central1` and is approximately 330.5 MB.
Quota/capacity contention is directly demonstrated by requested resources;
registry pressure and the two BigQuery Storage 500s may be secondary effects,
but are not established as one common cause.

The claimed silent ledger-cell relabeling path is also narrower than stated.
The analyzer does not load candidates under ledger-assigned arm labels. It
queries the ten immutable `panel_run_id`s directly and hard-checks the complete
season/slate set, stored seed pair, lever environment, code identity, exact-80
contract, artifact identity and same-image Phase R reproduction. A swapped
ledger execution ID would ordinarily leave a missing/incomplete panel and fail
closed rather than relabeling its rows. Nevertheless, execution-spec
verification is now added as independent defense in depth.

## Implemented response

1. `verify_sis_asoe_phase_s_execution.py` validates each execution's own Cloud
   Run specification against its registered arm, replicate, season, panel,
   job, image digest, code SHA, seed pair, position scales, finite-K or
   multinomial law, ASOE flag/beta, output destinations and resource/terminal
   contract. `cloud_finish_sis_asoe_phase_s.sh` requires all 30 checks before
   launching the analyzer.
2. The Phase S launcher now holds a hard maximum of ten in-flight cells rather
   than merely sleeping between launches.
3. `cloud_release_sis_asoe_phase_s_retry.sh` releases at most one pending retry,
   only below that cap, only after rechecking zero output in BigQuery and GCS,
   and only after validating the new execution-owned spec. Its ledger update
   helper requires exactly 30 unique factorial cells and execution IDs and
   substitutes the matching cell in all retry records as one controlled step.
4. Focused tests cover all 60 control-law/arm/seed/season execution-spec
   combinations, wrong-cell/seed/flag rejection, terminal-status enforcement,
   successful ledger substitution and wrong/duplicate substitution rejection.
   The complete 1,181-test repository suite also passes.

## Live recovery consequence

No new retry is released while the live count exceeds ten. The first bounded
release check detected treatment R2/2023 replacement
`replay-sisasoet2-2023-lf7l8` had newly failed with the same approximately
30-minute Cloud Run internal-error/exit-0 signature. It had zero application
logs beyond the platform error, zero candidate rows, zero feature rows and
zero candidate-world artifacts, so it was returned to the pending queue. The
releaser launched nothing and edited no ledger before this classification.
Two other replacements from the same overloaded wave subsequently terminated
with the identical signature: control R0/2025
`replay-sisasoec0-2025-v6jfr` and treatment R4/2023
`replay-sisasoet4-2023-hqskx`. Each also has zero candidate rows, feature rows
and artifacts and is queued without a new launch.

This response preserves Phase S's scientific validity while removing the two
actionable operational hazards: resource over-release and trust in manual
execution-to-cell substitution.

After the bounded controller reduced the live count to ten, control R3/2025
`replay-sisasoec3-2025-lgczd` terminated with the same Cloud Run internal
error/exit-0 status, but unlike the earlier failures it had already persisted
15 of 18 weeks. Before permitting a retry, recovery removed exactly the
partial cell's 3,820 candidate rows, 8,312 feature rows and 15 candidate-world
artifacts. The dedicated replay-lineups table had not yet been created. All
three candidate stores were then verified empty, the cleanup was recorded in
`partial_infrastructure_recoveries.txt`, and the cell was added to the bounded
retry queue. No outcome was used in making that classification or recovery
decision.
