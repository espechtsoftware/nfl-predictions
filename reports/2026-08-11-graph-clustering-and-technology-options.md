# Technology options: graphs, clustering, and dependence structure

Date: 2026-08-11. Response to: would Neo4j help, would clustering similar
players be enlightening, and what other technologies could pay.

**No code was changed.** Proposals only.

---

## Framing: there is exactly one channel left, and it is a graph

The system now splits cleanly:

| channel | owner | status |
|---|---|---|
| per-player marginal | TabPFN cache | calibrated per-position (adopted); active-label fix in flight |
| **joint structure / copula** | possession sim + fitted Dirichlet | **the binding constraint** |
| selection | 194 coverage selector | saturated — selected == pool oracle at 220/230/240 |
| objective | score thresholds | untested alternative (dollars) |

Every technology below is judged by whether it moves the second row. That is
also why the question is well-posed: **a copula is a dependence graph.** Graph
thinking is genuinely the right lens here — the question is which graph, and
whether it needs a graph database.

---

## 1. Neo4j: no, and the repository already argued this correctly

`graph/build.py` states it plainly: "At NFL scale (~2,000 players, 32 teams) it
fits in memory; NetworkX in a job is sufficient, no graph database needed." I
agree, and would add three specifics:

- **Scale.** A season's player-team-week graph is ~10⁴ nodes and ~10⁵ edges.
  That is four to five orders of magnitude below where a graph database earns
  its indexing. NetworkX loads it in under a second.
- **Cost.** Neo4j adds a stateful service, a sync path from BigQuery, IAM
  surface, backup/restore obligations, and a second source of truth for entity
  resolution — against a system whose hardest-won discipline is *one*
  authoritative warehouse with hash-locked provenance.
- **The queries you actually run are not graph queries.** Cascade reasoning
  ("who inherits an injured player's usage") is a join plus a conditional mean.
  Cypher expresses it prettily; BigQuery computes it, and already does.

**The one condition under which to revisit:** full contest standings. A 160k-entry
Millionaire is a bipartite entry↔player graph with ~1.5M edges per contest, and
the questions you would ask of it — duplication classes, "which lineups are one
swap apart," overlap communities in the field — are genuinely graph-shaped and
genuinely large once you have several seasons. Even there BigQuery is likely
sufficient, but that is the first time the question stops being obvious. Do not
provision anything until the standings exist.

## 2. Clustering: yes — but cluster by co-movement, not by traits

This is the most promising idea in the question, with one important inversion.

`analysis/archetypes.py` clusters players by **DK-points profile** — a Gaussian
mixture over per-player feature vectors, within position, separating consistent
from boom-bust at the same scoring level. That is a **marginal** clustering: it
groups players who *look alike*. It has already paid (archetype labels feed
cascade weighting and similar-player pivots).

Given the binding constraint, the more valuable object is a clustering of the
**dependence graph**: group players who *move together*, whether or not they
look alike.

Construction, all from data in hand:

1. Build a player-player graph over a season where edge weight is the empirical
   **co-exceedance lift** — P(B exceeds his own q90 | A exceeds) ÷ P(B exceeds) —
   or the partial correlation of projection residuals, which controls for the
   shared game environment.
2. Retain edges across *both* teams in a game, not just teammates. The published
   ceiling-correlation work puts WR1↔opposing WR1 at +0.09/+0.10; the bring-back
   channel is a real edge and it crosses the team boundary.
3. Spectral-cluster (or run Louvain/Leiden community detection) on that weighted
   graph.

What this could reveal that the current work cannot:

- **Whether dependence communities coincide with teams.** The measured structure
  says they do not, cleanly: QB→TE 2.50×, QB→WR 2.34×, but **WR–WR 0.99×**. The
  natural community is *not* "the Chiefs offence" — it is "Mahomes + Kelce" and
  "Mahomes + Worthy" as overlapping star arms, with the two receivers nearly
  independent of each other. A community detector run on real co-exceedance
  would either confirm that star topology or find genuine multi-receiver
  communities the current sim cannot represent.
- **Cross-game communities.** Weather systems, referee crews, and league-wide
  scoring regimes couple players across games. Current coupling is strictly
  within-game (`game_factor_matrix`). If communities cross game boundaries, that
  is a structural gap.
- **A calibration target.** The community structure of *simulated* draws can be
  compared to the community structure of *realized* outcomes. Same spirit as the
  co-exceedance diagnostic, but it tests the whole dependence topology rather
  than a handful of pairwise statistics.

**Honest caveat:** co-exceedance edges are noisy. A 90th-percentile event on
~17 games per player-season gives ~1.7 expected exceedances per player. Edges
need pooling across seasons and across *archetype pairs* rather than player
pairs. Which is where the existing archetype clustering becomes the input to the
dependence clustering rather than a competitor to it: **cluster players into
archetypes marginally, then estimate co-exceedance lift between archetype
pairs**, where the counts are large enough to be stable. That composition is
the design I would actually build.

## 3. Factor copulas: the technology that matches the measured structure

The dependence literature has a named object for exactly what was measured. A
**factor copula is a truncated C-vine rooted at a latent variable** — the right
model when one latent variable drives dependence among the rest. The
**bi-factor / second-order** variants use a common latent factor plus
group-specific factors.

Map that onto this system:

| layer | latent | current implementation |
|---|---|---|
| slate | league scoring regime | **absent** |
| game | game environment | shared `game_factor_matrix` ✓ |
| team | pass volume / script | partial (team factors) |
| **QB** | **the hub** | **absent as an explicit factor** |
| player | idiosyncratic | Poisson + fitted Dirichlet ✓ |

The QB layer is the measured hub and it has no explicit representation. A
bi-factor construction — game factor common to all ten players, plus a
QB/passing-game factor loading only on that team's pass-catchers, plus the
Dirichlet allocation you have now fitted — reproduces all three measured facts
simultaneously: strong QB→receiver lift, near-zero WR–WR (volume loading
cancelled by allocation competition), and excess ≥4-way multiplicity from the
factor's own tail.

Two design notes:

- **Choose the factor's copula family for upper-tail dependence.** Gaussian
  factors have zero tail dependence by construction — they cannot produce the
  2.17× four-way multiplicity no matter how the correlation is tuned. Gumbel or
  Student factor links carry upper-tail dependence. **This is not the closed
  Gumbel arm** — that was a *candidate generator* (`N_GUMBEL`), a completely
  different object from a Gumbel *dependence function*. Say so explicitly in any
  preregistration, because the name collision will otherwise read as a retry.
- **Gate it on the dependence statistics, not on lineups.** The variogram +
  joint-q90 Brier gate the forest failed, plus the co-exceedance grid
  (≥2/≥3/≥4 multiplicity, QB→WR/TE/RB lifts, WR–WR) against realized values.
  Marginals must stay invariant — which they will, since this changes only ranks
  before the TabPFN remap.

## 4. Self-supervised player embeddings: the way around label scarcity

The recurring reason to refuse flexible models here is 107 slates. That argument
applies to models trained on *slate outcomes*. It does not apply to models
trained on *plays*.

Recent sports-ML work trains player representations by treating a match as a
sentence and a player as a token — masked-player prediction, action-co-occurrence
embeddings in the word2vec style, TabTransformer event encoders. The training
signal is every play, not every slate: nflverse PBP gives ~50k plays per season,
roughly 350k across the panel.

Concrete, cheap version for this system: learn player embeddings from **on-field
co-occurrence and target co-occurrence** in PBP (the participation data already
audited for the pass-participation proxy), using a skip-gram objective. Then use
embedding geometry for the things that are currently hand-specified:

- **the Dirichlet's concentration**, per team, from the dispersion of its
  receivers' embeddings — a spread-out receiving corps should allocate more
  evenly than one dominated by a single alpha;
- **archetype similarity** for cascade weighting, replacing hand-built
  `COMPETES_WITH` edges with a learned metric;
- **cold-start players**, where embedding-nearest-neighbours give a prior that
  trailing-usage features cannot.

This is a **copula-channel** tool. Judge it on dependence statistics and cascade
accuracy, not on 30-point Brier.

## 5. Where graph tooling genuinely earns its keep: the field

The strongest graph application in this system is not the player graph — it is
the **opponent field**, and it is currently unbuilt.

Entries and players form a bipartite graph. The questions that determine dollars
are natively graph questions: duplication classes (identical rosters),
near-duplicate neighbourhoods (one-swap and two-swap balls around our entries),
connected components of the field's stack choices, and the overlap between our
80 and the field's mass. Computing "how many of the field's 160k lineups are
within one swap of ours" is a neighbourhood query, and it is the quantity that
decides whether a 200-point week pays $50 or $50,000.

This is the same item as the field/payout objective from the strategy review,
now with a clearer implementation story. It also remains blocked on the same
input: full contest standings.

---

## What I would skip

- **Neo4j / any graph database.** §1.
- **Graph neural networks over the player graph.** A GNN trained on slate
  outcomes has the same label-scarcity problem that gated out GFlowNet, plus more
  parameters. The embedding approach in §4 gets most of the representational
  benefit with a training signal three orders of magnitude larger. Revisit only
  if §4 embeddings prove useful as inputs.
- **LLMs anywhere near projections.** `graph/news.py` already has the right
  boundary — extraction into structured claims, never generation of numbers.
  Keep it there.
- **Another marginal-accuracy model.** The marginal is TabPFN's and is now
  calibrated. Accuracy work belongs in `features.txt`, not in a new model.

---

## Ranked

1. **Archetype-pair co-exceedance clustering** (§2, composed with §2's caveat).
   Uses existing data and the existing archetype labels, produces a calibration
   target for the copula, and is a diagnostic rather than an arm — so it is
   cheap and cannot fail expensively. **Start here.**
2. **Bi-factor copula with a QB layer and an upper-tail-dependent link** (§3).
   The technology matches the measured structure exactly, it preserves marginals
   by construction, and it is gated on dependence statistics. This is the most
   likely source of a genuine 210+ movement.
3. **Self-supervised PBP player embeddings** (§4), first as the estimator for
   per-team Dirichlet concentration — which you now have a fitted global value
   for, so per-team is the natural next refinement.
4. **Field graph + expected-payout objective** (§5), when standings exist.
5. Neo4j: no, unless and until §5 is running at multi-season scale.

---

## Sources

- [Factor copula models for multivariate data — Krupskii & Joe](https://www.sciencedirect.com/science/article/pii/S0047259X13000870)
- [Factor tree copula models / bi-factor and second-order structures](https://pmc.ncbi.nlm.nih.gov/articles/PMC10444667/)
- [Vine copula approximation for conditional dependence](https://link.springer.com/article/10.1007/s11222-017-9727-9)
- [Dependence Modeling with Copulas — Joe](https://www.routledge.com/Dependence-Modeling-with-Copulas/Joe/p/book/9781466583221)
- [RisingBALLER: a player is a token, a match is a sentence](https://arxiv.org/pdf/2410.00943)
- [A Foundation Model for Soccer (play-by-play sequence modelling)](https://arxiv.org/html/2407.14558v1)
- [Learning football player features using graph embeddings](https://dl.acm.org/doi/10.1145/3477314.3507257)
- [Correlation at ceiling outcomes between teammates and opponents — Underdog](https://underdognetwork.com/football/best-ball-research/correlation-at-ceiling-outcomes-between-teammates-and-their-opponents)
