# A3 post-open forensic provenance closure protocol

**Date:** 2026-08-20. **Status:** frozen recovery protocol. **Run:**
`20260819-stack-relaxation-carve-v1`. **Next owner:**
`20260820-a7-select-ladder-phase-s-incumbent-v1` (A7).

## Purpose and non-claim

The 54 A3 Cloud Run executions terminated and their scientific result bodies
and aggregate were committed in result commit
`56b09e960e5445cc7cd54c22eceef7cb5e7ec8c0` before the preregistered strict
finisher published its execution/object metadata ledgers and completion
receipt. The strict finisher correctly refuses to run over those preexisting
scientific files.

This protocol closes that provenance gap without relaunching a cell,
rewriting a scientific byte, or pretending that the results were unopened.
It licenses only operational release of the shared historical-outcome lane to
A7. It cannot improve A3's evidentiary status, license a retest, transport an
A3 result into A7, or change production.

## Frozen inputs

- Original A3 result commit:
  `56b09e960e5445cc7cd54c22eceef7cb5e7ec8c0`.
- Aggregate SHA-256:
  `2e08a551d116dc385b92ef123be3a6bb8296c71a75c822797d04c71bd669afdc`.
- Result report SHA-256:
  `b8ae2d2684baa8a236e5e0cfeb31eec27d9b1a8697702d11cb30c16724cbe7ae`.
- Original launch manifest, execution ledger, and launch receipt SHA-256:
  `6d822d6434aff3f16e00ac7e78216bcf583558abedbe93b0372683ba12edcbe7`,
  `8355974533586b549ba11bca0302b7ebc3ae792094283bb40645e7c6841ebc6f`,
  and `8f883eed18dad935459f211bcd821a8dacadde284e6c4d9170ac5e6bb399df5b`.
- Pre-open strict finisher, its tests, and its addendum SHA-256:
  `c43505f61008dd217395ba21f6f485c9a87a72fd72a581123f68c565df2addf2`,
  `13a6359b1d4165737f9b9b38755d5e6924f15d946b410a6801ee4b499204a191`,
  and `fb2ad4f3239f08ef17e35f71e10fbfa1471b48e2b18c9be77730ade3594c4860`.
- Exact population: seasons 2023–2025, weeks 1–18, 54 unique registered
  executions and 54 exact GCS result URIs.
- Recovery implementation identity is supplied by one canonical, tracked,
  operator-approved external manifest created after the recovery code/test
  commit and before any live metadata query. It pins that source commit and
  the exact recovery script, tests, and this protocol by path and SHA-256,
  while stating that the implementation manifest itself contains no realized
  outcomes and keeping all license flags false. The recovery execution does
  read the already-opened A3 result bodies for byte comparison and replay; the
  closure must say so literally. The closure embeds the full validated identity
  and manifest SHA. The recovery never binds itself
  to mutable `HEAD`; later receipt/HANDOFF commits therefore cannot invalidate
  an otherwise unchanged closure.

## Mandatory order

1. Verify all frozen local inputs and require every tracked cell and the
   aggregate to be byte-identical to the original result commit. No local
   scientific file may be created, replaced, normalized, or repaired.
2. Validate the original manifest, execution ledger, launch receipt, frozen
   protocol/runner/upload helper/chain sources, and the pre-open addendum.
3. Describe all 54 registered executions. Before reading a remote result body,
   require exact job UID/generation, immutable image/code/args/environment,
   one task, `maxRetries=0`, and strict terminal success with one succeeded and
   zero failed, cancelled, or retried tasks.
4. Require the live GCS prefix to contain exactly the 54 registered objects.
   Every generation must be positive, every metageneration exactly one, and
   every size positive.
5. Download each object at its registered generation with a generation-match
   precondition. Require its raw SHA-256 and bytes to equal the corresponding
   Git-tracked cell exactly; validate the canonical scientific schema. A
   mismatch is terminal and never licenses replacement or rerun.
6. Independently rebuild the aggregate using the frozen aggregation code and
   require exact canonical byte equality with the committed aggregate.
7. Publish create-once local operational evidence only: exact execution and
   object metadata, their checksum ledgers, a cell identity ledger, and one
   canonical post-open closure receipt/checksum. Partial publication must be
   resumable only by validating every already-created byte.
8. Probe the historical-outcome lease with a read-only, generation-aware API.
   Only a definitive NotFound is absence; authentication, transport, parsing,
   or API errors are terminal. After closure and definitive absence, publish a
   create-once canonical logical-release-v2 receipt naming A7.

## Closure and release semantics

The closure must state literally:

- `closure_mode=post-open-forensic-provenance-recovery`;
- `protocol_deviation_disclosed=true`;
- `scientific_result_opened_before_strict_harvest=true`;
- `recovery_reads_already_opened_realized_outcomes=true`;
- all 54 executions were strict terminal successes;
- the exact 54-object inventory was generation-pinned and every remote body
  byte-matched its original committed cell;
- the aggregate was independently recomputed and byte-identical;
- `strict_harvest_completed_before_read=false`;
- cell rerun, scientific retest, production change, shadow adoption, and any
  A3-to-A7 result transfer are all false.

The logical release is version
`stack-relaxation-carve-logical-release-v2`. A7 must reject the legacy v1
shape for this run and accept only the exact v2 recovery schema, including the
full original result commit, aggregate SHA, forensic closure SHA, definitive
lease-absence attestation, A7's run ID, operator approval, and all license
flags false. It embeds the exact canonical forensic closure receipt; A7
recomputes the embedded receipt SHA and validates its frozen identities, so a
syntactically valid release cannot substitute an unbound closure digest. The
release is a queue/resource handoff, not a scientific endorsement.
