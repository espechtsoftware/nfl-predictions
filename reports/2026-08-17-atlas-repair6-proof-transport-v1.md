# ATLAS repair6 proof transport and provenance-equivalence amendment

Date frozen: 2026-08-17, after proof execution
`atlas-md-s2023-w1-r6-proof-m6ctm` terminal-failed at the runner's initial
output-identity check, while defect execution
`atlas-md-s2023-w7-r6-9pxdt` was still nonterminal, before either repair6
object body, any candidate/effect field, or any realized outcome was opened.

Protocol ID: `20260817-atlas-repair6-proof-transport-v1`.

Evidence class: score-free transport and provenance-equivalence repair.

Production impact: none. Historical scoring remains forbidden until a new
versioned effective-canary receipt and complete repair5/repair6 hybrid receipt
are strictly sealed under this amendment and a separately rebound historical
transport.

## Frozen source evidence and exact defect

This amendment binds these already-created, immutable local sources:

- repair6 manifest SHA-256
  `5727c09b0cec60e8d99dc5755e18449d4a8d7904f454930aa4fe7a82e4baec6f`;
- original dual-canary ledger SHA-256
  `d35e9249eb02ac1804400662b7f89ed8b4a83220d8a60f3f6a8e9e0e033e55ee`;
- eligibility-classification SHA-256
  `d76e5a3a56e7b654e446bd104c525c219aaf88acc0d1dfc38733533a0757b787`;
- eligible-cell ledger SHA-256
  `932a3adb7c8e84544d5bcb809c5c3405444ca8fc59d42b9248c0cb979403bd0a`;
- code-diff proof SHA-256
  `7c59e5327dbed363ef00f7dece26c794a44a03e54ad59c49938d8b9de1199727`;
- original repair6 protocol SHA-256
  `b4a98543b1dcd776d50ae00e380fbc695346debb0de6452131fdfd0ba7c2820a`;
- original launcher SHA-256
  `eab78cd50c6f620fbd48bf3bc8284b54cd2049cac10337177c3e231400b7132a`;
- original finisher SHA-256
  `6599daf8ce25d6b1027a68c47b5395570d4f6d4344def20dc43b8451ede948b3`;
- pinned renderer SHA-256
  `69d0ed1187bf59176a857e0bc822f65bd9aea2ffd211ffc247312796bfaeb671`;
  and
- pinned runner SHA-256
  `0548e26e26d7e81b20c6837adcc8925bc2317f9b7c8586fba084787581cac740`.

The original launcher rendered exactly one command with the main repair6
prefix and used that command for both canaries. The proof row instead supplied
an output URI under the dedicated `-proof` prefix. The pinned renderer therefore
set `SHARDED_OUTPUT_PREFIX` to the main repair6 prefix, after which the pinned
runner compared the proof URI with that different prefix and raised exactly:

`RuntimeError: ATLAS MVP shard season/week/output identity differs`

That comparison precedes local-source validation, BigQuery/GCS client
construction, every query, every solver, payload construction and upload. The
failure is consequently a transport preflight failure with no scientific
object. It is not evidence about the repair6 tolerance extension.

The original finisher has the same transport defect: it reconstructs
`render(main_repair6_prefix)` once and requires both execution commands to
match it. A corrected proof command cannot be submitted to that finisher. The
original manifest, ledger, finisher and their hash receipts remain immutable
and cannot be edited, replaced or reinterpreted as successful.

## Prospective defect-canary rule

The target defect execution was nonterminal when this rule was frozen. Its
disposition is therefore fixed without knowing its result:

1. If `atlas-md-s2023-w7-r6-9pxdt` terminates successful under its exact
   original image, code, command, environment, resources, service account and
   main-prefix URI, with exactly one positive create-only object and no extra
   job execution, it is the only permitted repair6 Week 7 object and must be
   reused. It cannot be rerun.
2. If it fails, is cancelled, has missing/extra execution or object identity,
   or differs from that contract, this repair closes without launching a
   replacement proof.
3. Its object may be downloaded only after terminal success to compute an
   opaque whole-object hash; it may not be parsed and no slate, candidate,
   effect, score or tolerance value may be inspected or reported.

This rule is mechanical and symmetric: target success permits only proof
transport repair; target failure closes it. No target result can choose a
parameter, URI, proof law or consequence.

## Unique replacement proof

Only the failed no-change proof may be replaced. Its frozen identity is:

- job: `atlas-md-s2023-w1-r6-proof-r1`;
- prefix:
  `gs://nfl-predictions-503414-raw/research/atlas-matched-diversity-runs/20260817-atlas-matched-diversity-mvp-v1-repair6-proof-transport-v1`;
- URI: that prefix plus `/slate-2023-1.json`;
- command: the pinned renderer applied to that exact new prefix;
- exact original repair6 image
  `us-central1-docker.pkg.dev/nfl-predictions-503414/nfl-dfs/nfl-dfs@sha256:86b852e838f1ac685f40d8f0aed136337cdc5e230f38335076e45aaf24727487`;
- exact scientific code SHA
  `061767492628fccf0c9058fa8e1d41acb5fd55dc`;
- one task, parallelism one, 8 CPU, 32 GiB, zero retries, 43,200-second
  timeout, and the original service account.

The new job must have no prior execution and the new URI must be absent before
launch. The original proof job, execution, URI, ledger and empty object prefix
remain evidence and cannot be deleted, overwritten, redeployed or appended.
The new launcher writes a create-once manifest and one-row replacement ledger
under a new local evidence directory. It binds separate hashes for the
original target command, failed proof command and corrected proof command.

## Opaque provenance-normalized byte equivalence

The original complete-byte equality gate is structurally impossible for a
truthfully receipted repair5-versus-repair6 comparison. The pinned shard writer
serializes `analysis_image` and `code_sha` in the payload, while the immutable
repair5 and repair6 executions necessarily have different exact values for
both. Falsifying either environment value to manufacture raw byte equality is
forbidden.

Source inspection proves those are the only forced provenance differences.
The shard payload contains top-level `analysis_image`, `code_sha`, `season`,
`shard_week`, `slates`, `source_hashes`, `uses_realized_outcomes`, and
`version`. The output URI, prefix, job, execution, build ID, generation and
timestamp are not serialized. `source_hashes` is the unchanged static mapping
returned by the same pinned runner and is scientific-equivalence evidence, not
a field to normalize.

The repaired gate therefore operates on opaque bytes and removes exactly the
two forced leading provenance fields:

1. Independently validate the repair5 execution/object provenance against the
   frozen repair5 manifest, execution and object generation, and the repaired
   proof provenance against its exact execution metadata and new manifest.
2. Without decoding JSON, require each raw object to begin at byte zero with
   the exact canonical byte sequence
   `{"analysis_image":<expected JSON string>,"code_sha":<expected JSON string>,`.
   The repair5 prefix must contain the exact repair5 image/code; the new proof
   prefix must contain the exact repair6 image/code.
3. Remove only those exact leading sequences. Require each remaining byte
   sequence to begin with the exact public identity
   `"season":2023,"shard_week":1,`, end in one newline, and be completely
   byte-for-byte identical.
4. Do not call a JSON decoder, traverse `slates`, extract a scientific field,
   or persist/print either suffix. Retain only whole-object metadata/hashes,
   each normalized-suffix SHA-256, equality booleans and explicit
   `json_parsed=false`, `slate_fields_inspected=false` receipts.
5. Require the raw full-object bytes to differ, the normalized suffixes to be
   equal, and every non-normalized byte—including the complete
   `source_hashes` and `slates` encodings—to match. Any other difference closes
   the repair; no third run, normalization or tolerance is allowed.

This evidence-layer correction was frozen from source before the replacement
proof existed. It changes no simulation, optimizer, tolerance, candidate,
selector, score-free effect or historical gate.

## Effective population and immutable evidence

A successful strict finisher must bind exactly three execution roles:

- the original successful defect execution with command rendered for the main
  repair6 prefix;
- the original failed proof execution with that same incorrect command and
  its original `-proof` URI; and
- the single successful replacement proof execution with command rendered for
  the new proof-transport prefix and its new URI.

It must require the original proof prefix to contain zero objects, the new
proof prefix exactly one declared object, and the main repair6 prefix exactly
the accepted Week 7 object. It writes only versioned transport completion and
hash receipts. It cannot create the legacy `canary-completion.txt` or alter a
legacy closure receipt.

The frozen eligibility classification contains exactly one repair6 cell,
2023 Week 7. Consequently a successful effective execution ledger contains
the reused target only; no additional repair6 scientific grid job is needed.
A new hybrid-receipt version must accept exactly 53 repair5 objects plus that
one repair6 object, bind both proof attempts and both proof-prefix inventories,
and treat neither proof object as a population cell. The existing legacy
finisher and historical-v4 source validator cannot be reused because they
require the failed legacy proof job/prefix to be successful. Any historical
run requires a new versioned upstream receipt and job/URI.

## Queue and closure serialization

If the legacy repair6 closure receipt is absent when a tested replacement
watcher takes control, this amendment narrowly supersedes automatic closure
only for the exact bound pre-model proof transport failure above. The watcher
must first wait for the defect execution. Target failure closes repair6 and
releases the already-frozen continuous parity chain. Target success permits
the one replacement proof. Replacement execution failure, byte-equivalence
failure, or any validator ambiguity records one create-once amended closure
and releases parity exactly once. Successful proof/hybrid/historical closure
retains the original order: historical first, parity after strict harvest.

The replacement watcher must parse the complete execution metadata, find at
most one `Completed` condition by type, treat an absent condition or literal
`Unknown` as nonterminal, accept only exact terminal `True`/`False` states,
and reject duplicates or other values. It may not classify an empty formatted
status through a wildcard failure branch.

If the legacy watcher writes `queue-closure.txt` or starts parity before the
replacement watcher takes control, that receipt and queue action are final.
They cannot be deleted, amended or bypassed. Continuous parity must reach its
strict terminal completion and release the one-heavy slot before this protocol
may launch its replacement proof as a distinct chain. The new chain must bind
the legacy closure and parity completion; historical-v4 remains nonlicensed,
and only a new historical version may consume a later valid hybrid receipt.

Stopping or replacing a local watcher never authorizes cancelling, updating or
duplicating a Cloud Run execution. This amendment itself launches nothing,
opens no object, licenses no historical score and changes no production policy.
