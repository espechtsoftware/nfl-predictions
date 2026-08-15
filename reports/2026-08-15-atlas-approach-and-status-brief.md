# ATLAS approach and current status

**Prepared:** 2026-08-15 18:45 CDT  
**Purpose:** shareable technical brief for review by the model that originally
proposed ATLAS  
**Current production impact:** none

## Executive summary

ATLAS (Attainable-Tail Lineup Array Search) is a proposed replacement for the
current 40 “boom-world” candidate solves. Its premise is that the generator is
looking at the wrong simulated worlds and then compressing each chosen world
into only one optimizer solution.

The incumbent ranks a simulated world by the sum of every player's fantasy
points across the entire slate. A world can rank highly that way without
supporting an exceptional legal nine-player DraftKings lineup. ATLAS instead
aims to:

1. rank worlds by the best legal-lineup score they appear capable of
   supporting;
2. choose structurally different high-value worlds; and
3. enumerate several near-optimal, interaction-diverse lineups from each
   chosen world rather than taking one optimizer vertex.

Only the first premise is running now as a score-free diagnostic. It does not
read actual fantasy scores, choose a historical winner, score an exact-80
book, or change production. If that premise survives its frozen falsifier, the
next step is the fixed 8-cluster by 5-lineup ATLAS MVP and then a pre-lock 2026
shadow.

## Why the project prioritized it

The corrected forensic decomposition on 54 comparable 2023--2025 Sunday-main
slates found:

| Layer | Meaning | Mean gap to next layer | Weeks >=210 |
|---|---|---:|---:|
| H | Best legal hindsight lineup from the full slate | H-P: 4.057 | 51 |
| P | Best legal hindsight lineup from players used by any candidate | P-C: 68.914 | 50 |
| C | Best generated candidate | C-S: 5.007 | 6 |
| S | Best of the selected 80 | -- | 6 |

The player universe was usually adequate, while the generator failed to
assemble the useful combinations. Selection lost much less than construction.
That made a genuinely different construction search more compelling than
another marginal player model, global correlation coefficient, selector
threshold, random objective, or raw candidate-count sweep.

A separate order-invariant candidate-union repair has since strengthened this
diagnosis. At the same roughly 241--265 candidate budget, CBWU-OI improved mean
C from 181.07 to 186.73 and improved C crossings at 194/200/210 from 11/8/6 to
18/14/10. It did not improve 220/230/240. That result is not ATLAS evidence,
but it confirms that better combination breadth can materially improve C
without adding candidate budget.

## Full ATLAS concept

The intended mechanism has three linked parts:

### A. Attainable-world ranking

Rank simulated worlds by a roster-sized estimate of the best legal lineup
they could support, not by the sum of all players. This directs scarce exact
optimizer calls toward worlds relevant to a nine-player DFS roster.

### B. Structural world diversity

Choose eight worlds/clusters that differ in their top-player set, QB stack
core, and dominant game. This avoids using 40 solves on near-duplicate global
scoring regimes.

### C. Near-optimal interaction coverage

For each of eight worlds, generate five unique legal lineups:

- lineup 1 is the exact legal optimum;
- lineups 2--5 retain at least 98% of that world's positive optimum;
- within that near-optimal face, a secondary objective covers high-value,
  currently underrepresented player pairs and stack-core triples; and
- exact prior rosters are banned before each subsequent solve.

This produces exactly 40 boom candidates, matching the incumbent allocation.
All non-boom families, production legality, salary floor, stacking rules,
candidate budget and final selector remain fixed for the first comparison.
The point is new search geometry, not more candidates or looser rules.

## What the running score-free stage does

The current diagnostic is a deliberately cheaper falsification of Part A.
For each of five simulation panels (R0--R4) on each of 54 slates, it reads the
immutable 10,000-world player-draw artifact: 270 seed/slate artifacts total.

For every world it computes two rankings:

- **Control:** sum of all player draws on the slate, matching the current boom
  world's ranking concept.
- **Treatment:** a fast Classic roster-slot upper bound consisting of exactly
  one QB, one DST, and the best legal position-count shape among
  `(2 RB, 4 WR, 1 TE)`, `(2 RB, 3 WR, 2 TE)`, and
  `(3 RB, 3 WR, 1 TE)`.

The treatment bound intentionally relaxes salary, team/game, stacking,
minimum-game, and RB anti-correlation restrictions, so it is not claimed to be
a legal lineup. It is only a cheap ranking proxy and a mathematical upper
bound on the exact legal optimum.

The diagnostic takes the top 40 control worlds and top 40 treatment worlds,
forms their union (40--80 worlds), and exact-MILP-solves every union world
under the current production constraints:

- $50,000 salary cap and $49,000 salary floor;
- exact DraftKings Classic roster slots;
- players from at least two games;
- QB plus at least two same-team WR/TE;
- at least one opposing RB/WR/TE bring-back;
- no RB against opposing DST; and
- no two RBs from the same team.

Thus the proxy chooses the world set, but only exact legal optimizer results
are compared.

Conceptually:

```text
same player draws
       |
       +--> all-slate total rank --> top 40 --+
       |                                     |
       +--> roster upper-bound rank -> top 40+--> union --> exact legal MILPs
                                                        --> quality/diversity
```

## Frozen score-free falsifier

Across all 270 diagnostics, the attainable-world premise survives only if all
six conditions hold:

1. aggregate mean exact legal optimum improves;
2. mean exact legal optimum improves in at least three of five seeds;
3. aggregate q25 exact legal optimum does not decline;
4. mean unique-roster diversity is at least 80% of control;
5. mean unique-QB-stack-core diversity is at least 80% of control; and
6. mean dominant-game diversity is at least 80% of control.

The report also preserves medians, world-set overlap/Jaccard, exact roster
identities, stack cores, and dominant games. The proxy is mechanically checked
so no exact legal optimum may exceed its bound.

This gate is a premise falsifier, not an adoption gate. Passing would justify
building the already-specified ATLAS MVP. It would not prove that ATLAS raises
realized C or S, and it cannot promote a money lineup. Failing would reject
this cheap ranking primitive as currently specified; it would not prove that
all diverse near-optimal construction is useless.

## Outcome and leakage firewall

The runner's SQL and input frames exclude actual scores, actual ownership,
selected rank, contest rank, payout, and winnings. Inputs are pre-lock player
metadata plus immutable simulated-world artifacts. It requires exact code SHA,
immutable image digest, forensic-manifest identity, the five named panels,
270 source receipts, 54 slates, object checksums/generations, and a create-only
output. A strict finisher refuses partial or identity-mismatched results.

No realized 2023--2025 result may choose the later ATLAS clustering, 98%
tolerance, interaction universe, weights, or quota. Those are fixed before an
outcome-facing test. The descriptive prior for that later test is a broad
improvement in candidate C concentrated around 194--210, with no assumed 220+
gain; the complete 240/230/220/210/200/194/187 grid and standing tail-first
law remain unchanged.

## Current implementation and cloud status

- Core diagnostic: `src/nfl_dfs/analysis/atlas_world_ranking.py`
- Immutable runner: `scripts/run_atlas_world_ranking.py`
- Create-only launcher: `scripts/cloud_atlas_world_ranking.sh`
- Strict harvester: `scripts/cloud_finish_atlas_world_ranking.sh`
- Source-only repair record:
  `reports/2026-08-15-atlas-source-query-repair.md`
- Frozen repair code:
  `81b5c6e97c519babb8d7bb711c915ca70a2a51ba`
- Validated immutable image:
  `sha256:ac5d31bba3fa300301bf5a08d694f384f1cc16c2f232109f61f200b0c7768549`
- Validation: 1,531 tests passed, 2 skipped, 5 warnings in Cloud Build.

The first Cloud Run attempt, `atlas-world-ranking-scorefree-v1-8p92l`, failed
before science because BigQuery resolved an unqualified aggregate alias in a
source-receipt query. It loaded no source artifact, ran no diagnostic, wrote
no output, and queried no outcome. The only repair was to qualify the source
fields; population, metrics and gate were unchanged.

The repaired execution is:

`atlas-world-ranking-scorefree-v1-l59bt`

It started at `2026-08-15T23:18:39Z` in `us-central1` with 8 vCPU, 32 GiB RAM,
one task, no retries, and a six-hour timeout. At the preparation time above it
was still running normally with one active task. No ATLAS scientific result
exists yet, and ATLAS has produced no scoring or production improvement yet.
Only a terminal successful execution will be harvested and interpreted.

## Planned next steps if the premise survives

1. Strictly harvest and independently verify the score-free report.
2. Implement the fixed 8-by-5 near-optimal pair-coverage MVP; do not sweep
   clustering counts, tolerance, weights, or quotas against outcomes.
3. Validate exact candidate-count parity, legal rosters, uniqueness, pair/
   triple and stack-core coverage, effective rank, overlap, and held-out
   simulated p194/p210/p230 across R0--R4.
4. If mechanically sound, generate separate control/treatment books before
   2026 locks and grade candidate C and selected S prospectively at fixed
   checkpoints.
5. Keep production unchanged until prospective tail evidence licenses a
   promotion.

## Most useful reviewer questions

The highest-value critique would address:

- whether the position-only upper bound is an adequate cheap falsifier or an
  LP relaxation should be required before killing the ranking premise;
- whether the six score-free conditions preserve the intended mechanism
  without letting a weak proxy pass;
- whether the fixed eight structural clusters and five 98%-near-optimal
  lineups express the original idea faithfully;
- whether pair weights and stack-core triples can be defined entirely from
  pre-lock, multi-seed-robust evidence without reintroducing generic Hamming
  diversity; and
- whether any critical receipt, feasibility, or leakage guard is missing
  before the outcome-facing MVP.
