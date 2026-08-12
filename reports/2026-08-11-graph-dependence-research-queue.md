# Graph and dependence research queue

Date: 2026-08-11. This tracked queue reconciles the operator-supplied
`reports/2026-08-11-graph-clustering-and-technology-options.md` with the live
repository. The supplied review remains unmodified and untracked.

## Corrections and constraints

- Joint dependence is an important open channel, but it is not literally the
  only one left. The fitted-K exact-80 decision and the active-label, SCHED-sync
  and team-QB-quality TabPFN marginal sequence are still open. Do not displace
  or combine those frozen questions.
- The existing `player_archetypes` table is not safe as a historical label for
  this diagnostic: its normal job fits a trailing window ending at the latest
  completed season. Historical evaluation must refit archetypes separately for
  each target season using only prior seasons.
- Standard play-by-play rows do not identify all eleven players on the field.
  Any co-occurrence embedding must use the audited nflverse participation feed
  (or another provenance-locked participation source), joined to PBP, rather
  than claiming ordinary PBP alone supplies on-field co-occurrence.
- Full contest-entry lineups are already preserved prospectively by
  `import-ownership` in `nfl_raw.contest_entries`. The field-graph item is data-
  gated until 2026 large-field standings and payout ladders are captured; it
  does not require a new importer or a graph database.
- Neo4j is not queued. The player graph fits in memory, BigQuery remains the
  source of truth, and sparse arrays/NetworkX are enough for the proposed
  diagnostics. Reconsider storage technology only after measured query or
  memory limits appear on several seasons of full contest entries.

## G0 — final-served dependence premise kill test

Priority: first dependence execution, only after the marginal cache queue
drains. This inexpensive diagnostic decides whether G1/G2 have a premise.

Pin the manifest to the exact accepted cache table identity/hash, immutable
CPU image digest, common simulator law, source panel and final-served position
schedule. On same-key 2023--2025 active main-slate rows, recompute nine
registered metrics from that cache's own point-in-time q90 thresholds:

- team-week multiplicity at >=2, >=3 and >=4 exceeders;
- conditional QB→WR, QB→TE and QB→RB exceedance lift; and
- same-team WR↔WR, RB↔RB and TE↔TE lift.

For each team-week, calculate the independence count distribution from its
heterogeneous per-player exceedance probabilities with an exact
Poisson-binomial recursion/DFT. The pooled-binomial null is reported only for
comparison with the outside review; it is not the scientific baseline. The
protocol must freeze support rules, equivalence/materiality bands and clustered
uncertainty before one execution. It must also record the directional premise
that production overstates same-team WR lift, understates QB→WR lift and
understates >=4 multiplicity relative to realized final-served events.

If production reproduces every registered cell within the frozen equivalence
rule, G1 and G2 close without a clustering build. A material miss licenses G1.
If the accepted cache or served calibration changes before G2 launches, G0 and
any dependent G1 topology must be recomputed against the new immutable identity.

## G1 — walk-forward archetype-pair dependence topology

Priority: score-free follow-on only if G0 confirms a material dependence miss.
It runs after the fitted-K and marginal cache queue fixes the common simulator
and served-cache identities; it may not run concurrently against a cache that
could be superseded by an in-flight marginal arm.

Build one target-season diagnostic for 2023, 2024 and 2025:

1. Fit position-specific marginal archetypes from seasons strictly before the
   target. Freeze component count, seed, minimum games and feature definitions
   before reading target outcomes.
2. On accepted active main-slate rows, define player exceedance against that
   player's point-in-time final-served q90. Do not estimate a realized-season
   q90 with the target outcomes.
3. Aggregate edges by walk-forward archetype pair plus relationship class:
   same-team QB→WR/TE/RB, same-team WR↔WR, opposing pass-game pairs and other
   justified bring-backs. Report cross-game same-slate cells separately; do
   not assume a slate factor unless those cells show stable residual lift.
4. Estimate realized and simulated co-exceedance lift with minimum-support
   rules and shrinkage. Cluster the resulting small relationship/archetype
   graph with a deterministic spectral or Leiden/Louvain implementation.
5. Compare realized versus simulated adjacency/topology, role-pair variogram,
   joint-q90 Brier, >=2/>=3/>=4 exceedance multiplicity, and the named QB-hub
   and WR-competition cells. Multiplicity uses the exact team-week
   Poisson-binomial null from G0; pooled-binomial results are diagnostic only.
   Use slate-clustered or team-week-clustered uncertainty.

This is a calibration instrument, not an adoption arm. Individual player-pair
edges are explicitly excluded because roughly 1.7 q90 events per player-season
cannot support them. No lineup outcomes or score thresholds are read.
The outside review's 8.53% marginal rate and QB/receiver lift values were
computed from widened-summary `proj_p90`, not the final served draws. They are
motivation for the preregistered relationship cells only. G1 must recompute all
thresholds, marginal rates, lifts and absolute gaps from its final-served folds;
none of the prior numerical levels is an input, baseline or gate target.

## G2 — upper-tail QB bi-factor copula

Priority: highest-upside new mechanism, conditional on G1 confirming a stable
QB-hub residual that the accepted simulator misses.

Add one explicit team passing/QB latent factor inside each game, loading on the
QB and that team's pass-catchers, while retaining the accepted game factor and
within-team allocation law. Use one preregistered upper-tail-dependent link;
the name “Gumbel” here would describe a copula link, not the closed
`N_GUMBEL` candidate generator. A slate factor is omitted unless G1 first finds
stable cross-game residual dependence.

Fit all link/load parameters on the available early calibration seasons 2019,
2021 and 2022 without lineup scores. Evaluate the complete G0/G1 grid,
variogram and joint-q90 metrics only on held-out 2023--2025. The mechanism must
reorder ranks while preserving every player's exact marginal draw multiset
after TabPFN shaping. Its frozen scientific gate must require
aggregate improvement in role-weighted variogram and joint-q90 Brier, reduced
error in the G1 co-exceedance/multiplicity grid, exact marginal preservation,
and evidence that the QB factor is active. Per-season declines are reported but
are not an automatic veto under the operator's aggregate-tail objective.

Only a passing dependence gate licenses one separately frozen exact-80 panel
under the then-current production book and the 240/230/220/210/200 first-
nonzero weekly-maximum law. Parameters, link family and graph cells may not be
tuned on that lineup result.

Cross-game same-slate dependence is retained in G0/G1, but it does not license
a slate latent inside the lineup copula by itself. Its practical target is the
distribution of the slate's winning line. Stable cross-game evidence is routed
to a separately frozen winning-line/target-threshold model; it is not credited
as stack-construction value in G2.

## G3 — self-supervised participation embeddings for allocation hierarchy

Priority: exploratory follow-on after G1/G2, not a near-term lineup arm.

Train walk-forward player embeddings with a fixed skip-gram-style objective on
strictly-prior nflverse participation plus PBP target/action co-occurrence.
First use them only to inform a shrinkage model for team target/carry
concentration around the globally fitted K; embeddings do not directly choose
lineups or replace the simulator. True pre-debut rookies remain cold because
they have no NFL participation history, so do not claim this solves Week-1
rookie cold starts without a separately sourced college bridge.

The fitted-K exact-80 branch is fixed now, before that result is known:

- If fitted K `28.246898139750336` passes and is adopted, G3 control is that
  accepted global law and treatment is an embedding-conditioned hierarchy
  regularized around the same exact K. This isolates conditional heterogeneity.
- If fitted K is neutral or rejected, production K→infinity remains the lineup
  control. G3 may first run only a score-free heterogeneity diagnostic. Its
  embedding-conditioned law may still use the already frozen, outcome-free
  `28.246898139750336` as a regularization center, but it must improve held-out
  allocation likelihood and the G1 dependence scorecard against **both** the
  production K→infinity reference and the fixed global-K reference. Failure
  against either closes the allocation use of embeddings. A dual-reference
  pass licenses one separately frozen exact-80 comparison of production
  K→infinity versus the conditional law; the rejected global-K book is not a
  lineup arm or selector input.

No choice between these branches may be made after viewing the fitted-K score;
the comparator disposition selects it mechanically.

The first gate is held-out 2023--2025 conditional target/carry allocation
likelihood under the branch above, followed by the G1 dependence metrics. Only
a pass licenses a fixed mechanism and later exact-80 protocol.
Embedding dimension, window, negative sampling, context definition and K
mapping must be frozen before held-out evaluation; no GNN is included.

## G4 — field neighbourhood graph and payout objective

Priority: prospective 2026 data-gated work.

After several complete large-field standings exports exist, represent entries
as compact player bitsets or a sparse entry×player matrix. Measure exact
duplicate classes, one-/two-swap neighbourhood mass, stack communities and the
distance from each submitted lineup to concentrated field mass. Use BigQuery
for durable rows and local sparse/MinHash/LSH tooling only if exact pairwise
work becomes too expensive. NetworkX may visualize aggregated communities;
Neo4j is unnecessary.

Before optimizing dollars, also preserve each contest's entry fee, field size
and payout ladder. Calibrate the existing conditional field sampler against
real duplication, salary-leftover and neighbourhood distributions, then compare
the current tail selector with a preregistered expected-payout/portfolio-win
objective. Historical winner-only files cannot substitute for the missing
field distribution.

## Not queued

- Neo4j or another graph database without a measured scale failure.
- A player-graph GNN trained on 107 slate outcomes.
- LLM-generated projections or numerical adjustments.
- Individual player-pair community detection from 17-game seasons.
- A new generic marginal model outside the TabPFN feature/cache sequence.

## Execution order

1. Finish fitted-K exact-80 and the already-frozen TabPFN marginal queue.
2. Run G0 once against the resulting immutable final-served identity.
3. Run G1 only if G0 confirms a material dependence miss.
4. If G1 supports the mechanism, preregister and run G2.
5. Develop G3 only after the fitted-K branch and G0/G1 evidence define it.
6. Begin G4 when complete 2026 standings plus payout ladders accumulate.

Every stage must update `HANDOFF.md` with its protocol, immutable code/image,
data identities, execution IDs, validation, result and exact next action.
