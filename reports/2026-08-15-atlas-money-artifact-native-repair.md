# ATLAS current-money acquisition artifact-native receipt repair

**Frozen:** 2026-08-15 20:25 CDT, while all acquisition executions were
nonterminal and before any acquired player-world value or transfer effect was
read  
**Outcome use:** prohibited  
**Changes to the simulation, seeds, player worlds, ranking method, exact solve,
or Part-A thresholds:** none

## Trigger

The registered R3/2025 acquisition uploaded its immutable Week 1 NPZ player-
world object and then received BigQuery `429 rateLimitExceeded` responses for
the separate candidate-row and player-feature `WRITE_APPEND` operations. The
replay continued to Week 2 because those metadata writes run in daemon threads.
At freeze time this was the only observed acquisition error, all 16 research
executions remained nonterminal, and 42 of the expected 270 GCS objects were
present. No scientific payload was opened.

This means the original finisher's BigQuery-only source-grid condition may be
incomplete even when the exact score-free scientific payload is complete. It
does not license treating a missing object, failed execution, ambiguous object,
or malformed payload as valid.

## Repair boundary

The acquisition's scientific source is the NPZ object containing aligned
`player_ids` and `player_draws`; candidate-table rows provide its URI, digest,
lever receipt and row count but are not used to construct or rank ATLAS worlds.
The point-in-time player catalog comes from the separately frozen forensic
source, not from the acquisition's ancillary player-feature append.

The strict finisher will therefore build one hybrid source grid:

1. Verify all 15 Cloud Run executions are terminal successes and match their
   immutable image, full code SHA, command, resources, account and complete
   environment receipts.
2. List the exact five registered GCS panel prefixes and require exactly one
   object for every common `(panel, season, week)` cell: 270 objects, 54 slates
   per panel and seasons 2023--2025.
3. Bind each object generation, creation time and size to the registered
   execution for its panel/season. Objects outside that execution's start and
   completion interval are invalid.
4. Where a unique candidate-table cell exists, require its URI to equal the
   listed object and retain its recorded SHA-256, source-row count, code SHA and
   logged lever environment.
5. Where candidate metadata is absent, download only that exact object, compute
   SHA-256, and require the registered NPZ arrays, aligned candidate/world axes,
   10,000 finite worlds, unique player IDs and a positive candidate count. Bind
   its code and complete scientific environment to the independently verified
   execution/environment receipt. Label the cell
   `gcs_artifact_recovery`; do not fabricate a candidate-table row.
6. Reject any ambiguous BigQuery identity, orphan/missing/duplicate GCS object,
   digest mismatch, malformed payload, unexpected cell or nonterminal/failed
   execution. The analyzer must redownload every source object and verify the
   frozen SHA-256 before use, regardless of its metadata source.

The source grid and completion receipt must report counts by binding type. A
mechanically valid transfer may proceed only when all 270 exact scientific
objects pass this contract. Missing ancillary BigQuery rows remain disclosed as
an infrastructure defect; they are not silently described as successful table
persistence.

## Interpretation

This repair changes source receipt plumbing only. It cannot change which worlds
were generated, which ATLAS method is evaluated, or any pass/fail threshold. If
the GCS grid is incomplete or an execution fails, this acquisition remains
invalid/inconclusive and requires a separately frozen rerun. If the grid is
complete, object-native verification is stronger for the payload actually used
by the transfer than trusting a URI/digest copied through an ancillary table.
