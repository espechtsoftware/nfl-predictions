# Prospective reader v4: independent review accepted

Reviewed production `1c95dd68` on September 19, before Week 2 Sunday-main outcomes.
The 52 targeted synthetic tests pass on the laptop. The changes address the empirical
CRPS estimator, real-clock settlement gate, exact slate identity, cross-arm metadata,
book integrity and player-to-own-game binding defects raised in earlier reviews.
No additional blocking defect was found in this review; this is not a claim that all
possible input defects have been exhausted.

The [forecast-only smoke](reviews/evidence/2026-09-19-prospective-v4-forecast-smoke.py)
and its [result](reviews/evidence/2026-09-19-prospective-v4-forecast-smoke.json) use the
actual saved portable bundle. All required fields in the workstation's manifest
match exactly. The reader loads both frames and all four banks, verifies both
97-lineup books, and finds every roster player and every player's own game. There
are 428 shared players, one additional repaired-frame player, 13 games, and 27
prior-eligible players. Shared metadata is identical. Neither actual outcomes nor
synthetic outcomes attached to the real frame were opened. The real CLI refuses
before reading deliberately nonexistent actuals files at the present clock.

The create-once bundle is published at
`gs://nfl-2-506823-lab/research/week2-prospective-d1600/20260919-prelock-v1/`.
[Transfer receipt](reviews/evidence/2026-09-19-prospective-bundle.json) records each
object's generation, hash, byte count and CRC32C. Manifest SHA256:
`839f4b887a45a8c89a60c3c021063c4d9f7a16d70a3dad205e6eb2a51fc46bd8`.
Reader SHA256:
`99d43b7e90b1e9f1bee4d9642e03467dfdb7f745a2940e5c935f3d5281130b13`.

These are paired prospective shadow books, with no entered-book claim. Both arms
use the game-input repair; the control uses old usage/cache inputs and is not an
exact replay of the operational `e7255e9` chain. The workstation owns the protocol
and first settled-outcome read; the laptop will independently repeat that same
reader afterward. Neither this acceptance nor one future slate establishes
efficacy or authorizes a release. Runtime-guard review remains a separate open item.
