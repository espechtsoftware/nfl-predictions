# A7 v1 failed-preflight logical-release protocol

**Closed run:** `20260820-a7-select-ladder-phase-s-incumbent-v1`

**Successor identity:** `20260820-a7-select-ladder-phase-s-incumbent-v2`

**Disposition:** `invalid-outcome-blind-preflight-closed-no-retry`

This is an administrative, outcome-blind closure only. It cannot repair,
retry, finish, score, or reinterpret A7 v1. Its sole purpose is to release the
shared research-job claim after proving that v1 stopped at its first
real-artifact preflight and consumed no historical look.

## Required evidence

The close-only implementation must validate all of the following before it
publishes a release:

1. The exact committed v1 source is
   `96f4487bdefa297f66d03e4aca896728581540b2`; the successful build is
   `3503c493-60d5-4fe6-a853-583679c8e33d`; and the immutable image is
   `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:9956f2b4444bc60255c29a1844c23a1f772d6b0c85ae1a532e032ece975e86ed`.
2. The retained prepared and launch ledgers, launch manifest, execution
   ledger, job claim, and first poll are byte-exact. The first poll must be
   the retained provisioning response with no `Completed` condition and no
   terminal counters.
3. A fresh read-only describe of exact execution
   `atlas-minimal-c-s2023-w1-v1-6qfpk` must show its immutable v1 contract,
   `Completed=False`, `succeeded=0`, `failed=1`, `cancelled=0`, `retried=0`,
   and `maxRetries=0`.
4. Immediately before release, the exact v1 GCS prefix must contain only the
   create-once `preflight/job-claim.json`. The closer must generation-pin and
   reopen that object, reproduce its locally retained bytes and identity, and
   separately receive definitive `NotFound` responses for every registered
   smoke, smoke-terminal, support, support-terminal, freeze, and historical
   result URI.
5. The global historical-outcome lease must return definitive `NotFound`.
   Authentication, authorization, transport, timeout, and service errors are
   failures, never evidence of absence.

The closer retains canonical terminal-execution, prefix-inventory, and
absence receipts locally before constructing the release. It may read the
job-claim body and, during idempotent verification, the release body at an
exact generation. It has no realized-score query, BigQuery client, log read,
source-artifact body read, smoke/support/freeze/result body read, or
historical-outcome lease-acquisition path.

## Release and publication

The canonical local release body is:

`reports/a7-select-ladder-preflight-runs/20260820-a7-select-ladder-phase-s-incumbent-v1/failed-preflight-logical-release.json`

It is published exactly once with an `if_generation_match=0` precondition to:

`gs://nfl-predictions-503414-raw/research/a7-select-ladder-runs/20260820-a7-select-ladder-phase-s-incumbent-v1/preflight/failed-preflight-logical-release.json`

A separate local object receipt binds the publication URI, generation,
metageneration, byte count, and SHA-256 without introducing a self-reference
inside the release body. Both local files are immutable; a repeat invocation
may only generation-pin and reproduce the already-recorded publication.

The release must state literally that the historical look was not consumed;
the lease was never acquired; v1 preflight retry, historical retest,
historical scoring, prospective shadow, production-law transfer, and
production change are all unlicensed. It releases only the shared job claim
to the exact successor ID above. It does not license reuse of the v1 prefix or
the v1 success-only finisher.
