# G1 walk-forward archetype topology protocol

Frozen 2026-08-12 after the valid G0 disposition
`dependence-premise-miss`, but before any G1 target-season archetype label,
edge, realized/simulated metric, graph, community or disposition is computed.
This implements G1 from
`reports/2026-08-11-graph-dependence-research-queue.md` against the exact G0
terminal identity. G1 is score-free: it does not generate, select or score a
lineup.

## Immutable identity and invalidation

The G1 manifest must bind the G0 v2 report, protocol, cache preflight and
manifest hashes; terminal active-label, SCHED, team-QB and fitted-K selection
hashes; selected cache metadata/checksum; selected control served schedule;
historical panel; exact code and image digest; and the G0 simulator, blend,
draw-count and seed law. The selected cache is
`tabpfn_active_label_treatment_v2`, fitted K is
`28.154043586960896`, and the evaluation seasons are 2023--2025.

If any terminal cache, panel, usage law or served position schedule changes
before G2 launches, this G1 result is stale and G0/G1 must both be rerun. G1
may not run against a mutable/latest image or warehouse archetype table.

## Walk-forward archetypes

For target season `t`, compute each player's scoring-consistency profile only
from complete player-week training rows with `season < t`, excluding the
repository-wide omitted 2020 season. Inputs are player ID, QB/RB/WR/TE
position and authoritative DK points. Target-season outcomes never enter the
profile or label.

Reuse `analysis/archetypes.py` exactly: features `avg_pts`, `cv`, `pct_20_plus`,
`pct_10_plus`, and `skew`; minimum 16 prior games; within-position Gaussian
mixture; requested four components; seed 0; `n_init=3`; per-fold z-scoring and
deterministic tier/stability names. A player without 16 strictly-prior games is
labeled `<POS>-history-lt16`; do not assign it from target outcomes or from a
future fitted centroid. Persist the target-season label rows and source-season
range/checksum so the warehouse's ordinary trailing `player_archetypes` table
cannot be substituted.

## Terminal served population

Recreate the identical 10,000-draw, seed-0 terminal final-served book used by
G0: active/research-eligible QB/RB/WR/TE rows, selected TabPFN cache, 45/55
model/market blend, fitted-K usage law, and selected walk-forward position
factors. Apply each row's own final-served q90; `actual > q90` and
`draw > q90` use strict inequalities. Primary support remains final-served
mean at least 4.0 DK points. G1 must reproduce all 7,848 G0 supported keys,
54 slates, broad-cell point estimates within `1e-12`, 100% cache coverage and
mean drift at most `1e-10` before any G1 disposition is valid.

Each row must have point-in-time team, opponent and game identity. Fail on an
unresolved/ambiguous game, multiple supported QBs for one team-week, duplicate
player-week, actual disagreement or archetype position disagreement.

## Frozen pair classes

Use all eligible directed pairs for these primary within-game classes:

1. same-team `QB_WR`, `QB_TE`, `QB_RB`;
2. same-team `WR_WR`, `RB_RB`, `TE_TE`, using both orientations of every
   unordered teammate pair;
3. opponent `QB_OPP_QB` (both orientations), `QB_OPP_WR`, `QB_OPP_TE`, and
   `WR_OPP_WR` (both orientations).

Report three cross-game same-slate controls separately:
`QB_XGAME_WR`, `QB_XGAME_TE`, and `WR_XGAME_WR`. For each source row choose
exactly one eligible target in another game on that slate by the smallest
lexical SHA-256 of
`season|week|class|source_gsis_id|target_gsis_id`. A target may be reused.
These controls cannot license a QB factor; stable residuals instead route to a
future winning-line/slate-regime model.

Every cell is `relationship | source_archetype | target_archetype`. Preserve
direction even if the two archetype strings match. No individual player-pair
cell is estimated or reported.

## Estimand, shrinkage and support

For every relationship/archetype cell, accumulate the realized 2x2 table for
source q90 exceedance A and target exceedance B. For simulation, sum the same
four cells over all worlds and divide by 10,000, producing expected counts on
the identical directed-pair-teamweek scale. Apply Jeffreys shrinkage by adding
`0.5` to each of the four cells for both realized and simulated tables. The
estimand is
`P(B=1 | A=1) / P(B=1 | A=0)`, and the comparison is
`log(simulated lift / realized lift)`.

An archetype cell is supported with at least 100 directed pair-teamweeks and
at least ten realized source booms. A broad relationship cell uses the G0
minimum of 500 pair-teamweeks and 30 realized source booms. Unsupported cells
remain visible but cannot establish a stable topology or G2 license.

Use 2,000 paired bootstrap resamples of whole `(season, week)` slates, seed
1702. A supported archetype cell is a material miss when its point gap is
outside `log(1.25)` and its complete 95% interval is on one side of zero. It
is equivalent only when its entire interval lies inside `±log(1.15)`.
Everything else is inconclusive. Broad relationship cells use the same bands.

## Frozen topology diagnostics

Build separate realized and simulated positive-lift graphs over supported
archetype nodes for the six same-team and four opponent classes. Edge weight
is support-weighted `max(log(lift), 0)`; symmetrize directed weights by their
mean. Cross-game controls are excluded. Report signed cell gaps separately so
competition is not erased by the positive-community view.

For each graph report weighted-adjacency relative Frobenius distance and the
L1 distance between sorted normalized-Laplacian eigenvalues. On non-isolated
shared nodes, run normalized spectral clustering with four clusters (or the
number of nodes when fewer), NumPy symmetric eigendecomposition, k-means seed
0 and `n_init=20`; report adjusted Rand agreement. Communities and topology
distances are calibration descriptions, never G2 gate inputs.

Also report, by relationship and overall, the `p=0.5` variogram error and
pair-level joint-q90 Brier score using the simulator's pair co-exceedance
probability and realized joint indicator. Reproduce G0's exact
Poisson-binomial `>=2`, `>=3`, `>=4` multiplicity cells. These form the frozen
target scorecard for a possible G2 mechanism but are not retrospectively
combined into a G1 win statistic.

## Stable QB-hub decision

G2 is licensed only if all of the following hold:

1. broad `QB_WR` and `QB_TE` are supported and each has aggregate
   `log(simulated/realized) < -log(1.25)` with its entire slate-bootstrap 95%
   interval below zero;
2. for each of `QB_WR` and `QB_TE`, simulated lift is below realized lift in
   at least two of the three separately reported target seasons, and no season
   is a supported material miss in the opposite direction;
3. at least one supported `QB_WR` archetype cell and at least one supported
   `QB_TE` archetype cell are material underpredictions; and
4. every terminal/G0 reproduction invariant passes.

If all four hold, disposition is `stable-qb-hub-confirmed` and G2 is licensed.
If valid supported evidence contradicts one of the first three rules,
disposition is `dependence-miss-not-stable-qb-hub` and G2 closes. If a rule
cannot be evaluated because its required cell lacks support or a bootstrap
interval, disposition is `g1-inconclusive` and G2 is not licensed.

No threshold, cluster count, fallback label, pair class, cross-game matching
rule, pseudocount, support minimum, bootstrap setting, band or G2 decision may
change after the first G1 target-season metric is visible. Any later
sensitivity is exploratory and cannot license G2.
