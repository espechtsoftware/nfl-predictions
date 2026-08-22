# Offseason roadmap: learn how to fill the corpus, then learn how to select from it

**Date:** 2026-08-22
**Objective:** improve the probability that a fixed-size large-field tournament
portfolio contains an exceptional lineup, with the first operational target being
Week 1.
**Scope:** only candidate-corpus population and selection from that corpus. Cloud
deployment, IAM, Neo4j transport, and general application work are deliberately
outside this report.

## Executive recommendation

The project should not build a single “Millionaire-winner model” and use its top
80 predictions. It should build a two-stage, portfolio-aware research system:

1. **Population:** generate a broad but deliberately structured candidate
   super-pool using several soft sleeves: simulated-tail/boom, realized-tail,
   winner-support, and novelty. Do not impose a new universal winner template.
2. **Retrieval:** admit lineups using cross-fitted tail evidence, then choose the
   final book by each lineup's *marginal contribution to the portfolio*, not by
   its individual rank alone. A lineup that is excellent in the same worlds as
   20 already-selected lineups is less valuable than a slightly weaker lineup
   that wins in different worlds.

The most important scientific question is not “which historical trait is best?”
It is why the two strongest evidence sources currently disagree:

- In 51 realized Millionaire winners, the modal construction is a single QB
  teammate, no bring-back, and broad game dispersion.
- In the accepted 2023 Week 1 simulated `>200` analysis, the strongest supported
  topology is QB stack 3 + bring-back 1 + five players from one game.

That disagreement can reflect slate context, generator-selection bias, a known
simulation dependence defect, or a real difference between “wins a simulated
world” and “wins a 150,000-entry contest.” Copying either side before resolving
the disagreement would be premature. The Week-1 candidate should therefore be a
**hybrid, set-level strategy with explicit support for both evidence regimes**,
tested against the incumbent under identical budgets and worlds.

The immediate priority is to expand the complete `>200` phenotype analysis from
one slate to the historical slate set, join it to realized candidate outcomes and
the governed winner cohort, and produce one cross-fitted fill × retrieval
challenger. The current one-slate findings are valuable hypothesis generators,
not sufficient Week-1 policy evidence.

## 1. What success means

The repository's construction objective is the weekly maximum of a tournament
book, not average lineup score. The operator's mean weekly-max target near 194 is
useful for comparing mechanisms, but it is not a historical winning line. The 51
tracked 2023–2025 winners have a median winning score of 233.2; the larger set of
68 known winner lines from 2019 and 2023–2025 has a median of 237.29. A 194 lineup
can be valuable, but it should not be described as Millionaire-winning scale.
Among those 68 first-place lines, 63 exceeded 200, 61 reached 210, 55 reached
220, 45 reached 230, and 28 reached 240.

For this roadmap, success has four nested meanings:

1. **Fill success:** at the same generation budget, the corpus contains more
   genuinely high-tail and structurally useful lineups.
2. **Retrieval success:** at the same entry budget, the selected book captures
   more of the corpus ceiling and covers more distinct tail scenarios.
3. **Historical transfer:** improvements survive slate- and season-held-out
   realized scoring rather than appearing only in the worlds used to select.
4. **Prospective transfer:** the frozen Week-1 strategy behaves as designed on
   pre-lock data and is graded against the actual contest afterward.

The ultimate tournament goal is served by all four. None alone proves future
wins.

## 2. Evidence inventory: what the project actually has

| Evidence surface | Exact usable evidence | What it can answer | What it cannot answer |
|---|---|---|---|
| Known Milly first-place lines | 68 weeks across 2019 and 2023–2025 | Winner score distribution and raw roster anatomy | Full-field rank curve, duplication, payout, or matched non-winner shapes |
| Governed winner cohort | 51 winners, 17 in each of 2023–2025 | Feature-complete structure, ownership, pool overlap, constructibility, and world-forensic analyses | A well-calibrated probability of winning; 51 positives are too few for a high-dimensional winner classifier |
| Current-family realized corpus census | 67,951 candidate appearances over 54 slates; 54 realized candidates at `>=200`, 13 at `>=210`, 4 at `>=220` | Which generator families have actually produced tails | A portable selector by itself; events are extremely sparse |
| Generated-union realized corpus | 127,778 distinct legal rosters from 51 panels over 54 slates | Broad generated ceiling, actual tail labels, source recurrence | An unbiased field sample; panels and their outcomes have already been studied |
| Accepted simulated phenotype task | 585 unique 2023 Week 1 lineups × 50,000 worlds = 29.25 million scores; 27,117 strict `>200` events | Event rates, block stability, topology, pairs, generator tags, selector membership, event-set redundancy | Realized contest performance, causal effects, easy coverage, ownership, or cross-slate generalization |
| Accepted retrieval pilot | Four exact-80 retrieval laws on task 0, fitted on R0–R3 and descriptively read on R4 | Whether different simulated set utilities change one frozen corpus | A historical or production winner; only one slate has been run |

Primary internal sources are
[`2026-08-19-winner-anatomy-results.md`](./2026-08-19-winner-anatomy-results.md),
[`2026-08-19-winner-structure-census-results.md`](./2026-08-19-winner-structure-census-results.md),
[`2026-08-20-b1-winner-relative-census-result.md`](./2026-08-20-b1-winner-relative-census-result.md),
[`2026-08-21-corpus-population-review.md`](./2026-08-21-corpus-population-review.md),
[`2026-08-21-corpus-retrieval-engine-v1.md`](./2026-08-21-corpus-retrieval-engine-v1.md),
and the exact task-0 receipt at
[`receipt.json`](./corpus-gt200-runs/20260822-task0-simulated-gt200-phenotype-v1/receipt.json).

### A crucial denominator warning

“27,117 `>200` events” sounds like a large independent sample. It is not. Those
events come from 585 overlapping lineups on one slate evaluated under 50,000
draws from one model family. Lineups share players, worlds share a law, and many
events occur in the same extreme worlds. The independent units for claims that
must transfer are primarily **slates and seasons**, not lineup-world rows.

The task-0 event population is still extremely valuable. It supplies much more
information about *how* each lineup reaches the tail than a single realized
score does. It must be modeled with clustered/hierarchical uncertainty and then
replicated across slates.

There is also a subtle task-0 scope difference that must be preserved. The
phenotype description covers all 585 union lineups, while the retrieval pilot
admits only 524 R0–R3-origin identities and excludes 61 identities first seen in
R4. An all-585 phenotype association is therefore not automatically a property
of the selectable discovery population.

### Winner-source integrity must be fixed before modeling

The canonical 68 count is produced by
[`real_winner_overlap.py`](../src/nfl_dfs/research/real_winner_overlap.py),
which removes a duplicated 2024 Week 9 row and yields 17 winners in each of
2019, 2023, 2024, and 2025. The underlying files are not yet one clean source
of truth:

- `milly-winners-2019-2023-2024.csv` contains 52 nine-player blocks because
  2024 Week 9 duplicates Week 7; it also has one missing salary and five raw
  salary totals above $50,000.
- `milly_rosters_2023_2024.csv` contains 31 overlapping article-derived
  winners. Among 30 shared slate keys, only 18 winning scores agree with the
  canonical user-supplied file.
- The 2025 roster file has 17 complete nine-player winners, while its summary
  companion lacks `salary_used` in three weeks.
- Other older consumers do not all remove the duplicate and can expose 69
  keys; a README statement still cites 65. Those are stale scopes, not new
  winner evidence.

The canonical loader is the current analytical authority, but source URLs,
contest IDs, capture times and immutable source receipts are missing. Phase 0
must reconcile and receipt these inputs rather than allowing different model
paths to learn from different winner populations.

## 3. What the winner evidence says

### 3.1 Winner structure differs radically from the generated corpus

The complete structure census is unusually sharp:

| Structure | 51 winners | Registered pool (64,098) | Selected books (20,320) |
|---|---:|---:|---:|
| Naked QB | 11 (21.6%) | 0 | 0 |
| Exactly one QB teammate | 21 (41.2%) | 0 | 0 |
| QB stack 2 | 16 (31.4%) | 62,540 (97.6%) | 19,473 (95.8%) |
| QB stack 3+ | 3 (5.9%) | 1,558 (2.4%) | 847 (4.2%) |
| No bring-back | 31 (60.8%) | 0 | 0 |
| Full stack-2 + bring-back shape | 8 (15.7%) | 100% | 100% |
| Maximum game concentration `<=3` | 35 (68.6%) | 0 | 0 |
| Mean games represented | 5.67 | 4.87 | 4.65 |

All 51 winners were DraftKings-legal in the reconstructed snapshots. Thirty-two
violated the stack-2 mandate, 31 violated the bring-back mandate, and 43 violated
at least one. No winner violated the $49,000 salary floor or the two RB-related
house bans. This makes relaxed structure a legitimate *support* question, but
not an automatic performance rule.

### 3.2 Winner ownership is a mixed shape, not “be contrarian everywhere”

All 51 winners had ownership profiles; 40 matched all nine players. Median
cumulative ownership was 104.49%, with interquartile range 79.37%–135.01%, and
the median winner used four players below 10% ownership. The useful abstraction
is **chalk core plus three to five leverage pieces**. It is not a fixed total-
ownership target and should be normalized to each slate's ownership distribution.

The contest-aware Milly ownership model itself predicted ownership well, but its
downstream fade arm did not improve tails. That result warns against treating a
descriptive winner characteristic as a standalone selection rule.

An earlier exploratory 2025 review found a QB below 10% ownership in 11/17
winners and a sub-$4,000 player scoring at least 15 in 16/17. A broader curated
but conflicting 2023–2025 article set put a cheap-boom player in 41/48 rosters.
These are sensible punt/ceiling hypotheses, but winner-only numerators without
same-slate prevalence are not measured lift. They belong in the compact winner-
support feature set and matched-control audit, not in a hard fill rule.

### 3.3 The current pool has no winner-combination signal

Across roughly 1,242 registered candidates per winner slate, the median best
winner overlap was 4 of 9; none reached 7 of 9 and none reproduced a winner.
After preserving player exposures, overlap was at chance. Even the eight fully
constructible winners had only 4.5 median best overlap. Twelve winner-player
occurrences were absent from their slate's corpus.

This is evidence for learning **relationship and structural patterns**, not for
memorizing historical players. It also says that relaxing a rule is insufficient
if the generator and selector still prefer the wrong combinations.

### 3.4 Winner score extremity is not a simulator-calibration target

The winner-law follow-up showed that a contest winner is expected to sit at an
extreme percentile of its own score distribution simply because it is selected
as the maximum of a huge field. Winner score percentiles therefore do not prove
that the simulation tail is too thin. No tracked winner was the legal optimum of
its best archived world; median gap to the optimum was 47.4 points with 4/9
median overlap. Winner identities are a diagnostic ceiling and structural
support signal, not direct labels for retuning world scores.

## 4. What the high-scoring corpus says

### 4.1 Boom is the strongest replicated family signal—but not a complete policy

In task 0, boom-tagged lineups are 200/585 (34.2%) of the corpus but create
15,161/27,117 (55.9%) of all simulated `>200` events. Their share rises as the
threshold becomes more extreme:

| Strict simulated threshold | All events | Boom events | Boom share |
|---:|---:|---:|---:|
| `>200` | 27,117 | 15,161 | 55.9% |
| `>210` | 9,255 | 5,660 | 61.2% |
| `>220` | 2,814 | 1,916 | 68.1% |
| `>230` | 896 | 685 | 76.5% |
| `>240` | 370 | 319 | 86.2% |

This agrees directionally with the 54-slate realized family census: boom was
15.8% of the current-family corpus but produced 69.2% of the 13 realized
`>=210` candidates. It is the strongest signal that appears in both simulated
and realized evidence.

The accepted selectors already exploit much of the obvious boom signal:
coverage-194 chose 64/80 boom-tagged lineups, strict-200 and the tail ladder
each chose 66/80, and mean-score chose 59/80. More boom enrichment therefore
has diminishing room unless it produces different scenario support rather than
more versions of the same stacks.

It still does not justify all-boom population. The exact-budget all-boom arm
raised mean pool ceiling from 187.58 to 196.64 (+9.06), but the unchanged
line-194 selector moved the selected book only 178.57 to 179.91 (+1.34,
`p=0.49`). Half of the book changed and the result was null. Boom is a valuable
source of candidates; the unsolved problem is converting that source into a
portfolio.

### 4.2 Supported task-0 phenotypes

The frozen R0–R3 discovery view retained the following headline findings, with
R4 used only as a descriptive holdout:

| Phenotype | Lineup support | R0–R3 `>200` events | Discovery lift | R4 descriptive lift |
|---|---:|---:|---:|---:|
| Boom generator tag | 200 | 12,089 | 1.624x | 1.682x |
| QB stack 3 + bring-back 1 + max game 5 | 92 | 7,607 | 2.221x | 2.283x |
| Same topology + boom | 55 | 5,494 | 2.684x | 2.773x |
| Raheem Mostert + Tyreek Hill | 10 | 1,586 | 4.261x | 4.763x |
| MIA four-player stack | 10 | 1,585 | 4.258x | 4.697x |

The identity-specific MIA findings are evidence about that slate, not portable
rules. Their transferable representation is something like “correlated elite
pair in a concentrated high-ceiling team/game environment,” with player names
removed and slate context retained. The artifact contains 5,733 player-pair
associations with no family-wide multiplicity correction or uncertainty
intervals; supports of 5–15 lineups must be shrunk heavily even when R4 points
in the same direction.

Task-0 projection sum has useful but incomplete information: it correlates
about 0.57 with discovery event count. Salary is essentially uncorrelated
(`~-0.01`) because almost all generated lineups already spend near the cap.
This supports keeping projection context in the phenotype model while rejecting
salary-used as a meaningful tail ranker inside this narrow range.

### 4.3 The event signal is broad across blocks but clustered within worlds

Only four of 585 lineups had zero `>200` events; 531 had at least one event in
all five blocks. Per-lineup total event-count quartiles were 20, 30, and 55;
the 95th percentile was 130 and maximum 491. That stability argues that the
lineup rankings are not solely one-block accidents under this law.

At the same time, only 1,891–1,921 of 10,000 worlds in each block had any
`>200` lineup, and the top ten event worlds held 13.0%–14.3% of each block's
events. Across all five blocks, 9,534/50,000 worlds (19.1%) had any `>200`
lineup. This is exactly why a book must be selected as a set: many individually
strong lineups can be redundant because they all depend on the same small set
of extreme scenarios.

The existing phenotype artifact computes `>200` event-set overlap for 2,000
high-roster-overlap pairs, but it intentionally did not read the full score
matrix and therefore did not compute global score correlations. A separate
accepted top-overlap diagnostic did reopen the relevant scores: median Pearson
correlation among those 2,000 prefiltered pairs was 0.915, 1,120 were at least
0.90, and eight-player-overlap pairs had median 0.953. It also found one exact
duplicate score-vector pair, differing only at DST. This is strong redundancy
evidence, but it is not a global correlation search. Full-corpus correlation or
scenario-cluster summaries remain required before a correlation-aware selector
is promoted.

### 4.4 One-slate retrieval results are close and not decisive

All four accepted laws chose exactly 80 lineups using R0–R3. Their unchanged
R4 results were:

| Retrieval preset | R4 worlds `>200` | `>210` | `>220` | R4 mean world-best |
|---|---:|---:|---:|---:|
| Coverage at 194 | 1,216 | 532 | 180 | 176.645 |
| Strict-200 coverage | 1,211 | 532 | 182 | 176.638 |
| Tail ladder 200/210/220 | 1,197 | 521 | 181 | 176.336 |
| Individual mean score | 1,017 | 439 | 152 | 174.026 |

Coverage-194 and strict-200 shared 72 of 80 lineups; coverage and the ladder
shared 67. Strict-200 produced two more R4 worlds above 220 but five fewer
above 200. The differences are too small and the slate count too low to choose
a winner. The clear negative is individual mean ranking, which lost substantial
portfolio tail coverage.

## 5. Previous experiments define what not to repeat

The new program must be materially different from four closed mechanisms:

1. **Population-only all-boom:** higher ceiling, null selected-book result.
2. **Simple winner-shape relaxation:** replacing eight of 40 boom solves with
   open stack/bring-back solves admitted 530 open lineups across 53 slates but
   moved mean selected max 178.57 to 177.59 and regressed 200+ weeks 7 to 6.
3. **Shoulder-heavy A7 ladder:** exact-80 mean delta +0.05; 200/210/220 weeks
   each fell by one. Its utility placed 68% of value at or below 194.
4. **B1 individual tail classifier:** an L2 logistic model using 27 pre-lock
   summaries modestly improved average precision over `p_line`, but worsened
   Brier calibration and selected-book mean (173.66 to 171.37), with no gain in
   200+ or 210+ weeks.

The B1 feature list already included salary, simulated mean/SD/q50/q90/q99,
`p_line`, source appearances, games/teams represented, largest team/game
blocks, stack and bring-back counts, positional salaries, and FLEX position.
Training another linear classifier on those fields and the same 250-lineup
weekly pools would be a retry in substance even if it had a new name.

The new work earns a fresh question only by adding all of the following:

- complete lineup-by-world event fingerprints rather than marginal q99 alone;
- relationship, boom, coverage, ownership, and slate-context phenotypes;
- candidate support outside the incumbent structural region;
- hierarchical/cross-fitted uncertainty across slates; and
- set-level marginal selection rather than top individual model scores.

## 6. The synthesis: a concordance matrix

Every proposed trait should be classified before it can affect a preset:

| Evidence relationship | Interpretation | Permitted use |
|---|---|---|
| Winner and realized/simulated tail agree | Most credible portable signal | Larger soft weight or fill sleeve after cross-slate validation |
| Winner-only | Possible simulator blind spot or field/duplication effect | Small exploration sleeve; require realized validation |
| Simulated-tail-only | Possible model artifact or slate-specific relationship | Simulation-coverage sleeve; never a universal hard rule |
| Realized corpus only | Potential portable tail signal that the world law misses | Cross-fitted realized-tail feature and prospective challenger |
| Neither / negative | Control or ablation | Retain only if it contributes unique set coverage |

Current examples:

- **Boom:** concordant across task-0 simulations and the 54-slate realized
  family census, but population-only deployment failed because retrieval could
  not harvest it.
- **Concentrated triple stack:** strong task-0 simulated signal, sharply
  discordant with realized winner structure. Treat it as one regime, not the
  default.
- **Winner-dispersed structure:** strong winner-support signal, but the direct
  k=8 relaxed sleeve was negative under the current scoring law. Preserve a
  bounded hedge, not a wholesale relaxation.
- **QB-variant family:** 2.37x realized tail efficiency at 210 in the 54-slate
  census, but only 0.44x task-0 simulated `>200` lift. This disagreement is a
  high-value diagnostic for cross-slate work.
- **Coverage fit:** the prior FantasyPoints player model produced a very small
  valid 30-point Brier improvement, but adding 432 coverage candidates changed
  33 selected slots and changed zero weekly maxima over 107 slates. Coverage
  should return as an interaction/phenotype annotation, not as a repeat of the
  same twelve-candidate construction arm.

## 7. Build one canonical research table

The foundational deliverable should be a versioned `lineup_slate_evidence`
dataset at one row per `(slate_snapshot, lineup_id)`. Large score matrices stay
as immutable artifacts; the table stores their identities and bounded
summaries.

### 7.1 Keys and provenance

- slate, contest, lock time, salary-slate identity;
- canonical nine-player lineup ID;
- fill preset, generator family/tags, source panels, appearances;
- exact player/world/candidate artifact identities;
- point-in-time feature version and missingness receipt;
- selection preset membership and rank;
- realized-outcome authority/version kept separate from pre-lock features.

### 7.2 Pre-lock lineup features

1. **Construction:** salary used/left, positions, team count, game count,
   QB-teammate count, bring-backs, team/game concentration, secondary stacks,
   relation-typed player pairs.
2. **Projection/tail:** projection sum and slate percentiles, player ceilings,
   boom probabilities/tags, uncertainty, leverage, world-optimum source rank.
3. **Ownership:** sum, log product, chalk anchors, counts below slate-relative
   ownership cutoffs, duplication proxy. Use walk-forward predicted ownership
   live; realized ownership is evaluation only.
4. **Context:** slate size, ownership entropy, pricing tightness, game totals,
   team implied totals, game-environment rank, injury/opportunity concentration.
5. **Coverage/SIS:** supported-player count, easy-coverage count and weighted
   score, missingness, receiver alignment/coverage interaction, opponent prior-
   window Wide/Slot information. Every value must be point-in-time.
6. **Relationship graph:** teammate/opponent relation types, projected joint
   ceiling, pair overlap with other candidates, and scenario-cluster membership.

All continuous features should have both raw and within-slate normalized forms.
Winner likeness must not learn that a $7,000 player or a 20% player means the
same thing on every slate.

### 7.3 Simulated phenotype summaries

For each threshold `t in {194, 200, 210, 220, 230, 240}` and each world block:

- exposure count, event count and event rate;
- posterior mean and lower credible bound;
- number of world regimes reached;
- event-world IDs or a pointer to the sparse bitmap;
- marginal uniqueness versus incumbent selections;
- best, mean and quantiles of scores;
- stability across R0–R4.

For a lineup and threshold, model the aggregate as
`k[lineup, slate, block, t] ~ beta-binomial(10,000, p)`, or an equivalent
hierarchical binomial model. This prevents 10,000 correlated draws from
masquerading as 10,000 independent slates and shrinks small-support pair lifts.

### 7.4 Realized labels

- actual lineup score and threshold indicators;
- weekly corpus rank and distance to corpus ceiling;
- winner score and winner gap;
- winner/top-N/full-field rank, duplication and payout when available.

Realized fields must never be materialized into the live feature view.

## 8. Learn three distinct quantities, not one overloaded score

### 8.1 Simulated tail phenotype

Estimate a cross-fitted posterior distribution for `P(score > t)` and for
scenario breadth. The model should use structure, generator family, boom,
pair-relation, context, and optional PIT annotations. Fit on designated slates
and R blocks; predict a different slate/season and unopened world block.

The output is not “probability of winning.” It is a portable estimate of how
often and how robustly a lineup reaches simulated tails.

### 8.2 Realized corpus tail

Fit `P(actual score >= t)` using only pre-lock features, with outer folds by
season and clusters by slate. Because actual 200+ prevalence is tiny, report
calibration, average precision, lift at fixed admission budgets, and book-level
utility. The model must beat the frozen B1 comparator out of fold and must show
new information from the richer features; a ranking-only AP gain is
insufficient.

### 8.3 Winner-support density

With 51 feature-complete positives, estimate a low-dimensional, strongly
regularized **density ratio** between winner rosters and matched same-slate
controls. It answers “is this shape represented among historical winners more
than among the lineups we generate?” It does not estimate a lineup's literal
win probability.

Use a preregistered small feature set: stack topology, game dispersion, salary
use, slate-relative ownership shape, projection/ceiling percentiles, and broad
relation classes. Exclude player IDs, team IDs, season/week IDs, and specific
historical pairs. Match controls within slate and report leave-one-season-out
stability. As full standings arrive, expand positives to top-10/top-0.1% and
use field entries as the correct denominator.

### 8.4 Portfolio marginal utility

The final selector must optimize a set. For a candidate book `S`, a useful
family is:

`J(S) = sum_world q(world) * u(max_score_in_S(world))`

where `u` is frozen before evaluation. Candidate choices use marginal gain
`J(S union {l}) - J(S)`. Viable utilities are:

- identity `u(x)=x` for expected maximum;
- a genuinely tail-weighted ladder above 200;
- contest-relative thresholds when historical rank curves become available.

Winner-support, realized-tail posterior and uncertainty should control
admission, sleeves, or frozen tie-breaks. They should not replace the set
objective with another top-80 individual ranking.

## 9. Corpus population roadmap

### 9.1 Generate a neutral super-pool once, then compare fixed admissions

For rapid experimentation, generate a broad, mechanically fixed super-pool
under identical world and solve budgets, retaining every legal unique roster.
Different fill presets should be reproducible admission/generation policies
over that source. This allows many retrieval experiments without rebuilding
the simulation law and permits exact attribution of whether a missing lineup
was never generated or merely not admitted.

Pure reweighting cannot create naked/single-stack or other absent support.
Therefore the super-pool also needs bounded conditional-generation sleeves.

### 9.2 Initial fill presets

| Preset | Purpose | Proposed construction |
|---|---|---|
| `F0-incumbent` | Paired control | Current six-family mixture and rules |
| `F1-tail-family` | Replicate concordant generator evidence | Same total solves, more boom plus a bounded qbvar/role allocation; preserve an incumbent component |
| `F2-winner-support` | Cover shapes excluded by the incumbent | Bounded topology sleeves across QB stack 0/1/2/3+, bring-back 0/1, and max-game 2/3/4/5; soft ownership-shape targets |
| `F3-phenotype-conditional` | Generate toward portable high-tail traits | Soft objective bonuses from cross-fitted phenotype scores; no player/team identity coefficients |
| `F4-hybrid` | Hedge simulation/model misspecification | Fixed mixture of F1 simulated-tail, F2 winner-support, and novelty/residual-scenario candidates |
| `F-negatives` | Identify what is causal versus correlated | Equal-budget ablations removing one phenotype sleeve at a time on development folds |

The dose for each sleeve must be learned inside development folds or fixed from
score-free support—not adjusted after the outer realized read. Start with soft
bonuses/quotas. A 51-winner sample is not enough to justify universal hard
constraints.

### 9.3 Fill metrics

For every slate and fill preset retain:

- unique legal lineups and duplicate-generation rate;
- phenotype support and novelty relative to F0;
- simulated threshold counts, scenario breadth and block robustness;
- realized corpus ceiling `C` and threshold grid;
- source attribution of each slate maximum;
- generation time and fixed-budget compliance.

The 127,778-roster historical union already reaches mean realized ceiling
198.10, with 24/54 slate maxima at 200+, but matched-volume analysis found only
about +0.4 points from heterogeneous arm diversity over independent same-law
volume. More raw volume is not the main discovery. The fill objective is to
produce **more admissible, distinguishable tail support per fixed budget**.

## 10. Retrieval roadmap

### 10.1 Separate admission from final portfolio construction

1. **Admission:** remove dominated/redundant candidates and form a bounded
   shortlist using simulated-tail lower bounds, cross-fitted realized-tail
   scores, winner-support sleeves, and novelty.
2. **Portfolio construction:** greedily or exactly maximize frozen marginal
   set utility over that shortlist, subject to exact book size and legality.

This makes diagnostics clean. If a high-realized-score lineup is absent from
the shortlist, admission failed. If admitted but not selected, portfolio
utility or redundancy pricing failed. If selected but does not transfer, the
pre-lock signal failed.

### 10.2 Retrieval presets to implement

| Preset | Role |
|---|---|
| `R0-coverage-194` | Incumbent control |
| `R1-strict-200-coverage` | Existing tail control |
| `R2-expected-max` | Marginal gain in `E[max score]`; directly aligned with the stated weekly-max objective |
| `R3-tail-lcb` | Marginal 200/210/220 utility using shrunk cross-block lower bounds, not raw event counts |
| `R4-hybrid-support` | R2 or R3 with fixed winner-support and realized-tail admission sleeves |
| `R5-regime-robust` | Equalizes marginal utility across world blocks/scenario clusters so one rare world family cannot dominate |

`mean-score-v1` remains a negative control. The one-slate result already shows
why a marginal individual rank is not enough.

### 10.3 Redundancy should be measured in outcome space

Use, in priority order:

1. overlap of tail-event worlds and scenario clusters;
2. full score-vector correlation across held-out blocks;
3. roster/player overlap;
4. generator/source overlap.

Roster overlap is only a proxy. Two lineups sharing six players can still hedge
different game outcomes; two lineups sharing four can be nearly identical in
world behavior. The selector should retain the event bitmap or a compressed
scenario signature for every candidate.

## 11. The experiment design that isolates fill from retrieval

Every candidate hypothesis should enter a paired 2 × 2 before a joint policy is
credited:

| | Incumbent retrieval `R0` | Challenger retrieval `R*` |
|---|---|---|
| Incumbent fill `F0` | **A: baseline** | **B: retrieval-only effect** on the exact same snapshot |
| Challenger fill `F*` | **C: fill-only effect** with retrieval fixed | **D: joint strategy** and interaction |

- `B - A` isolates retrieval.
- `C - A` isolates fill.
- `D - C` asks whether the new retrieval can harvest the new pool.
- `D - B` asks whether the new fill adds value under the new retrieval.
- `D - C - B + A` is the fill × retrieval interaction.

This directly answers the unresolved all-boom result: C improved dramatically,
but the old retrieval could not convert it. The untested target is not another
population-only or selector-only arm; it is a jointly designed strategy whose
component effects remain observable.

### 11.1 Fixed comparison law

All four cells must share:

- exact slate/player snapshot and point-in-time features;
- exact world matrices, block order and random seeds;
- equal generator/solver budget for fill comparisons;
- identical candidate snapshot for retrieval comparisons;
- exact final entry budget and legality law;
- frozen tie-breaks, thresholds and missing-data behavior;
- complete lineup identities and score vectors.

The existing strategy registry already validates the key causal separation:
retrieval comparisons share one corpus snapshot and fill preset; fill
comparisons use different snapshots but the same retrieval preset and world
identities. That contract should remain the backbone of the research suite.

### 11.2 Discovery and evaluation tiers

1. **Exploratory historical development:** use already-viewed outcomes openly,
   but label them exploratory and allow them only to nominate a frozen policy.
2. **Inner cross-fitting:** select model form and preset dose within training
   seasons/slates. No outer-fold outcomes may choose features or weights.
3. **Outer season/slate evaluation:** generate predictions without that
   season's labels. Rotate R blocks or use fresh world panels so R4 does not
   become a repeatedly tuned development set.
4. **Prospective 2026 confirmation:** freeze before lock, then grade after the
   contest. This is the only genuinely unseen outcome tier remaining after
   extensive 2019–2025 research.

### 11.3 Unit of inference and statistics

- Primary paired unit: slate; season is the outer dependency block.
- Report weekly vectors, not only aggregate means.
- Use paired slate bootstrap or randomization intervals with season
  stratification.
- Report leave-one-slate and leave-one-season influence.
- Correct across a registered family of challengers or use nested selection;
  do not nominate the best of dozens against one untouched p-value.
- Use empirical-Bayes shrinkage/minimum slate support for high-cardinality
  pairs. A pair appearing in ten lineups on one slate is not ten-slate support.

### 11.4 Primary and secondary metrics

**Primary historical metric:** paired weekly maximum of the exact-size selected
book, plus 200/210/220 threshold counts. Keep the 194 target as a comparison
marker, not the only utility.

**Required diagnostics:**

- corpus ceiling `C`, selected maximum `S`, and conversion gap `C-S`;
- held-out simulated worlds above 200/210/220 and `E[max]`;
- portfolio event-world breadth and correlation;
- realized winner gap and field-relative rank when available;
- source/phenotype composition and exact book overlap;
- first 4/14/80 prefix maxima if those cuts match intended entry use;
- calibration/AP for individual models, never as a substitute for book results.

## 12. Expand the two knowledge sources deliberately

### 12.1 Millionaire data

P0 work:

1. Reconcile the raw winner CSVs into one canonical 68-contest registry with
   contest ID, slate universe, nine canonical player IDs, score, salary and
   ownership provenance. Preserve the 51-row governed 2023–2025 cohort as a
   versioned subset rather than silently mixing definitions.
   Replace outcome-aware name-resolution tie-breaks with durable player/source
   identities where possible, and explicitly flag the 11/51 recent winners
   whose ownership match is not complete for all nine slots.
2. Build matched controls per slate: incumbent corpus, broad generated union,
   legal random/optimized lineups, and—when available—actual field entries.
3. Compute the same point-in-time normalized feature vector for winners and
   controls. Without the denominator, “X% of winners have a trait” is not an
   enrichment estimate.
4. Prospectively collect full 2026 standings immediately after every contest:
   top 10/top 100/top 0.1%, field scores, complete rosters, duplication, rank,
   payout and ownership. One winner per slate is too sparse; top-finish bands
   turn winner anatomy into a learnable ranking problem.

The current project has no historical `contest_entries` population. It must
not infer top-five lineups, duplication, rank curves, or ROI from first-place
files.

### 12.2 High-scoring corpus data

P0 work:

1. Run complete scoring and sparse phenotype production for every historical
   slate/fill snapshot, not only 2023 Week 1.
2. Retain thresholds 194/200/210/220/230/240, all five block counts, event
   bitmaps, selector membership, generator/source lineage and full score-matrix
   pointers.
3. Join realized scores after selections and pre-lock features are frozen.
4. Produce cross-slate association tables with support in **lineups, slates,
   seasons and world blocks**. Rank by shrunk held-out effect, not raw lift.
5. Separate player-identity findings from portable relation findings.
6. Cluster tail worlds into scenario regimes so the selector can buy breadth
   across game environments rather than raw event count.

### 12.3 Coverage, FantasyPoints and SIS

The accepted task-0 matrices contain no FantasyPoints or SIS scoring input and
its easy-coverage availability is explicitly false. The annotation schema
already provides point-in-time join keys for player, game and world features.

For each lineup, add only audit-safe aggregates:

- supported receiver count and coverage completeness;
- count/share of players with favorable prior-window coverage fit;
- projection- or target-share-weighted coverage-fit score;
- interaction between coverage fit, alignment, ownership and boom probability;
- opponent prior-window Wide/Slot attempt environment from SIS where valid.

Then ask two separate questions:

1. Are these traits enriched among simulated and realized high-tail lineups
   after controlling for projection, ownership, role and slate?
2. Do they add *marginal portfolio value* beyond the existing candidate set?

Do not rerun the closed twelve-candidate FantasyPoints coverage arm. The new
question is whether coverage explains phenotype differences and improves a
joint admission/set selector.

## 13. Offseason implementation sequence

### Phase 0 — canonicalize and freeze the evidence contract (1–2 focused days)

- Publish the lineup-level schema and feature dictionary.
- Reconcile 68 known winners versus the 51 governed feature-complete cohort.
- Define the cross-validation folds and reserve prospective 2026 outcomes.
- Register exact fill/retrieval preset schemas, budgets and metrics.
- Establish one immutable baseline result per slate.

**Exit:** every reported number maps to one exact lineup/slate/world identity;
outcomes cannot enter the live feature view.

### Phase 1 — expand phenotype extraction (2–4 focused days plus compute)

- Execute all-slate complete scoring for available fill snapshots.
- Produce threshold/event/block summaries and event bitmaps.
- Attach structure, generator tags, ownership and available PIT context.
- Add coverage/SIS annotations with explicit missingness.
- Build cross-slate support/lift and discordance reports.

**Exit:** no Week-1 decision rests on a one-slate association; every nominated
trait has multi-slate support or is explicitly an exploration hedge.

### Phase 2 — implement the population and retrieval candidates (3–5 focused days)

- Add bounded topology and phenotype conditional-generation sleeves.
- Fit cross-fitted simulated-tail, realized-tail and winner-support models.
- Implement expected-max, tail-LCB and regime-robust marginal selectors.
- Retain exact selection traces explaining every admission and marginal pick.

**Exit:** exact budgets and deterministic replay pass; B1's old feature-only
individual ranking is reproduced as a negative control.

### Phase 3 — paired factorial evaluation (2–3 focused days plus compute)

- Run A/B/C/D cells on identical historical snapshots/worlds.
- Open realized outcomes only after all books are frozen.
- Compute C, S, C-S, threshold, robustness, overlap and influence reports.
- Nominate at most one joint strategy and one materially distinct fallback.

**Exit:** the nominee improves a book, not merely a classifier or corpus
ceiling, and the effect is not a single-slate accident.

### Phase 4 — Week-1 freeze and rehearsal (complete by T-3 days)

- Freeze exact fill/retrieval preset IDs, model artifacts, feature source
  versions, missing-data fallback, entry budget and tie laws.
- Rehearse on a stored slate from candidate generation through legal DK CSV.
- Prove every intended lineup is unique, legal, available and exportable.
- Produce incumbent and challenger books from the same Week-1 snapshot.
- Prohibit outcome-driven changes after the freeze.

**Exit:** a failed optional annotation falls back deterministically; it cannot
stop lineup export or silently change strategy.

### Phase 5 — Week 1 and onward

- Run the frozen incumbent and phenotype challenger in parallel.
- If the new strategy has not earned a money-policy gate, keep it shadowed or
  cap operator-authorized exposure while retaining an interpretable control.
- Download the full target-contest standings and payout curve immediately
  after settlement.
- Grade fill, admission and retrieval separately; append the evidence before
  proposing Week-2 changes.

## 14. Prioritized action plan

| Priority | Deliverable | Concrete completion criterion |
|---|---|---|
| P0.1 | Canonical lineup evidence schema | One row per snapshot/lineup, exact artifact pointers, PIT/outcome firewall tests |
| P0.2 | Canonical winner/control dataset | 68 winners reconciled; 51 governed cohort reproduced; same-slate controls and feature completeness report |
| P0.3 | All-slate `>200` phenotype expansion | Every available lineup scored in every retained world; 194–240 event/block summaries and sparse bitmaps |
| P0.4 | Cross-slate phenotype report | Shrunk effects with lineup/slate/season/block support; identity and relation findings separated |
| P0.5 | Fill presets F0–F4 | Equal budget, deterministic candidates, explicit topology/phenotype support and ablations |
| P0.6 | Retrieval presets R0–R5 | Exact-size deterministic books, complete marginal traces, block-held-out metrics |
| P0.7 | Factorial evaluator | A/B/C/D paired cells and fill × retrieval interaction with C/S/C-S vectors |
| P0.8 | Week-1 release packet | Frozen IDs/hashes, legality/export rehearsal, fallback, scorecard and no-tuning boundary |
| P1.1 | PIT coverage/SIS annotation | Completeness and source-season proofs; no missing-as-zero behavior |
| P1.2 | Scenario/redundancy model | Tail-event clusters and global score correlation or bounded signatures |
| P1.3 | Full contest collector | Complete standings, duplication, payouts and rank curve captured after every 2026 slate |

## 15. Week-1 decision gates

A Week-1 challenger is ready only if all of these are true:

1. It is generated entirely from pre-lock, point-in-time inputs.
2. It has exact budget parity and all lineup identities/legality are retained.
3. Its retrieval policy is evaluated on the exact same candidate snapshot as
   its retrieval control.
4. Its fill policy is evaluated with the same worlds, solve budget and
   retrieval policy as its fill control.
5. It improves held-out simulated set utility and does not depend on one R
   block.
6. It improves or credibly protects realized weekly-max/tail metrics in outer
   folds, not merely AP, Brier, winner likeness, or corpus ceiling.
7. It has a deterministic fallback to the incumbent when a paid/context
   feature is absent.
8. Its preset, models, feature sources and tie laws are frozen before Week-1
   outcomes exist.

If those gates are not complete, the system should still produce the
challenger as a shadow. The worst response to time pressure would be to convert
one-slate simulated lifts into 80 live entries without cross-slate validation.

## 16. Explicit no-go list

- Do not train on winner player/team identities.
- Do not call 27,117 world events 27,117 independent observations.
- Do not hard-code the task-0 MIA pair or stack as a general rule.
- Do not convert winner structure percentages into universal quotas without
  same-slate denominators.
- Do not rerun all-boom with the incumbent selector or the closed k=8 open-
  stack carve and call it a new test.
- Do not rerun B1's linear individual ranking on the same feature set/pool.
- Do not optimize the 194 shoulder and claim it targets tournament wins.
- Do not use R4 repeatedly for feature selection and still call it held out.
- Do not select the 80 highest individual probabilities without portfolio
  marginal gain and redundancy.
- Do not mix realized ownership, scores, ranks or winners into the live
  feature view.
- Do not judge a fill policy only by C or a retrieval policy only by simulated
  utility; retain the complete A/B/C/D chain.

## 17. External methods checkpoint

The portfolio direction is also consistent with the most relevant primary
operations-research literature, without relying on that literature as evidence
that this NFL implementation will transfer:

- Hunter, Vielma and Zaman formulate fixed-cardinality winner-take-all entry
  selection as a submodular portfolio problem. Their central result is the same
  principle the task-0 event sets expose here: individual strength is
  insufficient because the joint distribution and marginal coverage of each
  added entry matter. Their practical construction balances expected score,
  variance and correlation. See
  [*Picking Winners in Daily Fantasy Sports Using Integer Programming*](https://arxiv.org/abs/1604.01455).
- Haugh and Singal model expected reward in both top-heavy and flatter DFS
  contests, explicitly model opponent roster behavior, and extend the decision
  to multiple entries. This supports collecting full fields, ownership,
  duplication and payout curves rather than treating a fixed fantasy-point
  threshold as the final contest objective. See
  [*How to Play Fantasy Sports Strategically (and Win)*](https://doi.org/10.1287/mnsc.2019.3528).
- Bergman, Cardonha, Imbrogno and Lozano study expected-maximum optimization and
  include an NFL DFS application. That makes `R2-expected-max` a principled
  comparator to threshold coverage, while the project's own historical folds
  must decide whether it works here. See
  [*Optimizing the Expected Maximum of Two Linear Functions Defined on a Multivariate Gaussian Distribution*](https://doi.org/10.1287/ijoc.2022.1259).

These papers reinforce the set-level objective and the need to model the field;
they do not validate the project's boom, winner-shape or task-0 phenotype
findings. Those remain hypotheses until the paired all-slate program succeeds.

## Bottom line

The project has already learned three things that materially narrow the path:

1. There is substantial high-score support in the generated universe: the
   broad union's mean realized ceiling is 198.10.
2. Tail-heavy generation can raise that ceiling dramatically, but the tested
   selectors have not converted it.
3. Real winners occupy structural regions the incumbent never generates, yet
   naive relaxation toward those regions was negative under the current law.

The opportunity is therefore not “more corpus” or “copy the winners.” It is a
joint policy that generates **both** model-favored and model-challenging tail
support, learns portable phenotypes across slates, and buys the final 80 by
marginal scenario value. The all-slate phenotype expansion and the paired
fill × retrieval evaluator are the two pieces that turn the existing harness
into that system. They are the critical offseason work for a defensible
Week-1 challenger.
