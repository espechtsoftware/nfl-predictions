# Pre-result amendment: ATLAS MVP pair-reach floor

**Frozen:** 2026-08-16T01:28:23-05:00, before the matched-diversity MVP was
launched and before any P0/P1/P2 MVP effect result existed. The only active
execution was the mechanically separate R3/2025 Week 1 source-identity repair.
No MVP treatment or control result was queried.

The source protocol remains
`reports/2026-08-16-atlas-matched-diversity-mvp-protocol.md`, with SHA-256
`badc0d64be69694caadd8fb2fe16a293c0cfbfe1f7813b4e80dc45e10b727abf`.
This amendment adds one prospective disposition condition and changes no
source panel, candidate budget, cluster, interaction price, solve, admission,
selector, tail threshold or realized-outcome firewall.

## Evidence-based prior

The current-money ATLAS premise pass improves exact attainable-world quality
while reducing mean player-pair reach to `0.9520` of control and dominant-game
reach to `0.9080`. CBWU-OI's realized candidate-C improvement, by contrast,
coincides with approximately `+41%` player-pair reach and `+52%` stack-core
reach. These endpoints are not directly comparable, but the observed signs
support this preregistered prior:

> A matched-diversity ATLAS candidate book that still reduces combination
> breadth is expected to underperform one that preserves breadth at candidate
> C, even if ATLAS continues to identify higher-quality attainable worlds.

Accordingly, an MVP failure caused by lost pair reach is confirmatory mechanism
evidence, not a surprise or permission for post-result tuning.

## Added frozen condition

For each of the 54 season/slate cells, count the distinct unordered player
pairs in the complete fixed-budget candidate pool for P1 and P2. Let
`R1(s)` and `R2(s)` be those counts. The additional condition is:

`mean_s R2(s) >= mean_s R1(s)`.

Equivalently, because both arms contain the same number of slate cells, the
aggregate distinct-pair count across cells must not decline. This is an
absolute breadth floor, not the conditional pair-*weight* condition already
in the protocol. Both must pass. It is aggregate rather than every-slate to
avoid treating ordinary slate-size variation as a hard feasibility failure.

The executable gate must report both arm means, the P2/P1 ratio and the Boolean
condition named `candidate_pair_reach_retains_100pct`. The strict finisher must
require that condition by name. Any mismatch is a mechanical failure.

## Unchanged consequence

All original conditions remain necessary. A complete score-free pass still
licenses only a separately labeled 2026 pre-lock P0/P1/P2 shadow. It does not
license production adoption, a historical realized-score arm, or an ROI claim.
