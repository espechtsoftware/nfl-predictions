# Independent tail-scoring review: construction-first ideas for the 2026 NFL DFS season

**Date:** 2026-08-15  
**Repository state reviewed:** `main` at `ddf1e75cdd90`  
**Scope:** code, tracked reports, the `phase-s-cbwu-54` repair4 BigQuery corpus, and external research  
**Status:** independent recommendations only; no code, policy, cloud state, or historical decision was changed

## Executive conclusion

The best available opportunity is not another player model, global correlation
coefficient, or selector. It is to change the geometry of candidate
construction.

The current generator repeatedly turns a linear player-score vector into one
optimal lineup. Even the boom family chooses worlds by the sum of every
player's simulated points across the slate and then returns one MILP optimum
per world. That is a severe many-to-one compression: a rich joint simulation
is reduced to a small collection of optimizer vertices. The corrected
forensic result says this is where the points disappear. Exact P reaches 210
on 50 of 54 slates; the generated candidate pool reaches it on six. The mean
P-to-C construction gap is 68.914 points, versus only 5.007 from C to the
selected portfolio.

My highest-conviction new mechanism is **ATLAS: Attainable-Tail Lineup Array
Search**. It would replace the current 40 boom solves, at the same 40-candidate
allocation, with:

1. worlds ranked by a cheap approximation to the best *legal lineup* they can
   support, rather than by total points scored by the entire slate;
2. a small, structurally diverse set of those worlds, clustered by stack core
   and top-player identity; and
3. several distinct near-optimal lineups from each world, chosen to cover
   high-value player pairs and triples that the existing pool has not yet put
   together.

This is buildable before Week 1, requires no new outcome data, preserves the
candidate budget and incumbent selector, and is materially different from the
closed Gumbel/random-objective family. It searches the near-optimal face of a
tail world and the combinatorial interactions inside a lineup rather than
drawing another objective and taking another single MAP solution.

The rule audit also found a separate design problem: the repository sometimes
treats strategy hypotheses as if they were contest legality. Point-in-time
data, exact DraftKings roster legality, status exclusion, provenance and
outcome-blind preregistration should remain hard. QB+2 plus a bring-back in
every lineup, both RB anti-correlation bans, a universal 194 selector line,
first-N slicing and an 80-entry ceiling are not laws of the game. They are
empirical policies with context-dependent opportunity costs. The safest
change is not to remove them globally; it is to turn the unproven ones into
bounded portfolio allocations and evaluate those exceptions prospectively.

Two operational audits should precede any scientific shadow:

- The live sim-mode path appears able to recompute nonzero draws for an
  `O`/`IR` player because the stored-projection path applies inactive
  redistribution and zeroing, while `build_slate_with_draws` does not and the
  app's `allowed_ids` is only a draftable-ID filter. This is a potential
  money-lineup correctness defect, not a research arm.
- The briefing says production uses fitted Dirichlet allocation at
  `K=28.154043586960896`, but the adopted policy explicitly sets
  `GAME_SIM_USAGE=""` and no `DIRICHLET_K`. The CBWU adoption record also says
  finite-K was not licensed into that composition. The immediate action is an
  effective-policy receipt and dependence remeasurement, **not** silently
  enabling Dirichlet.

## What I reviewed and what is authoritative

I treated the code and the corrected, frozen reports as authoritative over
older narrative summaries. The important current baseline is
`classic-k1-role12-boom40-poscal-cbwu-v4`: 80 entries, a 194 coverage line,
role 12 plus boom 40, five candidate seeds, five 10,000-world scoring blocks,
the $49,000 floor, QB+2 pass catchers and one bring-back.

On the 54 comparable 2023--2025 Sunday-main slates, its weekly maxima have mean
176.063 and counts of `17/8/7/6/3/1/0` at
`187/194/200/210/220/230/240`. CBWU was rationally selected under the frozen
tail-first rule even though it lost a 194 crossing: it added the more valuable
210+ and 230 crossings.

The corrected exact-stack decomposition is:

| Layer | Meaning | Mean gap to next layer | >=210 slates |
|---|---|---:|---:|
| H | best legal hindsight roster from the full slate | H-P 4.057 | 51 |
| P | best legal hindsight roster from players used by any candidate | P-C 68.914 | 50 |
| C | best generated candidate | C-S 5.007 | 6 |
| S | best of the selected 80 | -- | 6 |

Construction is the first failure at 210 on 44 of 54 slates; selection is the
first failure on none. Exact P is also not an ordinary near miss: it averages
5.17 player swaps from the closest retained candidate.

Those facts do not license an outcome-fitted generator. Historical outcomes
are closed. They do identify the channel in which a prospective, score-free
mechanism has the largest plausible return.

## Audit of project rules and “laws”

The most useful distinction is not “strict versus loose.” It is **what kind of
rule this is**:

1. **External legality:** DraftKings salary cap, roster slots, player identity,
   slate eligibility, entry limit and locked-player rules. These must be hard.
2. **Scientific and money-safety invariants:** point-in-time inputs, common
   lock, status exclusion, immutable provenance, same-image controls,
   outcome-blind freezing and deterministic audit receipts. These must also be
   hard.
3. **Strategic hypotheses:** stacking, bring-backs, anti-correlation, minimum
   spend, overlap, target score, number and ordering of entries, and generator
   quotas. These should be versioned policies, not silently promoted to
   universal laws.
4. **Experimental controls:** fixed candidate counts, seeds, worlds and one
   changed mechanism. These should remain hard *inside a comparison*, but a
   fixed experimental budget is not evidence that the same budget is optimal
   in production forever.

The project is appropriately severe in the first two classes. The rigidity
problem is that several rules from class 3 are enforced like class 1.

| Current rule or law | Evidence in this repository | Assessment | Recommended treatment |
|---|---|---|---|
| Point-in-time, walk-forward, provenance and leakage gates | Multiple prior results were invalidated by salary, identity, status and temporal defects | Essential, aligned with the goal | Keep hard; never trade validity for an apparent tail gain |
| Exact DraftKings roster legality and status | The apparent live inactive bypass could create an invalid money lineup | Essential, aligned with the goal | Keep hard and make eligibility explicit in the sim path |
| QB+2 pass catchers plus one opponent bring-back in every lineup | Corrected P falls from 260.064 under QB+1/no bring-back to 249.984 under QB+2/bring-back and loses five >=240 and four >=230 slates; a prior generic stack-free batch was nevertheless a realized-tail null | Material opportunity cost; wholesale removal is not supported, but universality is too strong | Keep the incumbent majority and test a small, conditional exception sleeve rather than another generic no-stack batch |
| No RB against opposing DST; no two RBs from one team | Hard MILP exclusions at `optimizer/lineup.py:296-313`; neither is DraftKings legality and neither has an isolated terminal test | Too rigid as an impossibility claim | Admit bounded exceptions only when held-out simulated joint-tail support clears a frozen gate |
| Minimum salary $49,000 | The actual no-floor arm added no tail crossings; corrected H/P no-floor adds only one >=230 crossing and 0.856 mean points | Current hard setting is supported, though it remains a strategy policy | Keep for production; permit only a separately frozen, narrowly targeted construction shadow—not broad relaxation |
| At most seven shared players between generated lineups | Two-player novelty can preserve the same repeated core and does not measure useful interaction coverage | Misaligned proxy rather than a safety law | Replace or supplement with stack-core, pair/triple and scenario coverage in ATLAS |
| Fixed 194 selection line for every contest profile | `tail_line_for_field` varies a contest estimate, but `contest_entry_policy` records `tail_line_changed=False`; historical 187/194/200 sweeps were flat | Too rigid across field sizes and payout shapes, but historically retuning 194 is closed | Keep the money selector until a prospectively frozen contest-relative or multi-line selector earns promotion |
| Smaller books are the first N of an 80-entry book | The forensic result explicitly says the first 20/40 lose material tail coverage and calls for purpose-built small books; production still returns `first-N-adopted-CBWU-tail-coverage-order` | Directly counter to the goal in single-entry, 3-max and 20-max contests | Solve the selector separately for the exact purchased N using the same frozen candidates/worlds |
| Production refuses more than 80 entries | Code accepts contest limits through 150 but rejects requests above 80 because 80 is the validated policy boundary | Evidence boundary, not demonstrated optimum; counterproductive when the contest permits more and bankroll policy chooses them | Preserve 80 as the validated default; prospectively construct the marginal 81--150 book instead of treating 80 as a universal ceiling |
| Fixed 52 generation slots / 40 boom attempts / candidate multiple 2 | These are valuable controls for attribution, while the final construction census shows a large missed-combination gap | Experimental constants, not laws of nature | Hold fixed for the first ATLAS A/B; revisit production allocation only after a mechanism shows higher yield per realized candidate |
| Highest-threshold-first adoption by first differing count | A fitted-K decision gained its 240/230/210 advantages from one slate while losing 3 >=200, 7 >=194 and mean score; the 240.44 treatment still trailed that week's recorded 294.38 winner | Correct utility direction, statistically brittle promotion rule | Keep high tails primary, but require an influence/replication gate before one slate can change production |
| Every downstream change invalidates every upstream verdict | This protects against non-transfer, but literal application can create an unbounded revalidation cascade | Sound principle stated too categorically | Require revalidation only when an impact map shows the treatment contrast can change; allow a machine-checkable equivalence certificate otherwise |
| Historical closures | They prevent repeated mining of the same 54/107 slates; the repository already scopes selection closure to the current simulator/static signals | Essential if scoped correctly | Close exact mechanisms and data contexts, not semantic topics; record explicit reopening conditions and expiry boundaries |
| One active historical-outcome experiment | Prevents adaptive cross-experiment leakage; repository practice already permits score-free work beside it | Keep for outcome reads, too rigid if applied to all research | Allow parallel code, data and outcome-blind diagnostics; serialize only experiments that can reveal or react to historical outcomes |
| Every CBWU block required or the build fails closed | Protects against silently serving an unvalidated partial ensemble; a labeled CE12/boom28 role-outage fallback already exists | Right default, but “no entries” is also an operational failure | Retain fail-closed validation and rehearse a complete, separately validated degraded-mode book for block/service outages |

### The stack rules should become a portfolio prior, not disappear

The exact-stack addendum supplies unusually direct evidence about the cost of
the universal stack shape. Relative to QB+1/no bring-back, exact QB+2 plus a
bring-back costs 10.080 hindsight points on average and loses
`0/1/2/0/3/4/5` threshold slates at 187/194/200/210/220/230/240. This is
outcome-viewed oracle evidence, so it cannot select a new production rule.
But it disproves the idea that the stronger rule is costless.

The earlier `N_NOSTACK=60` experiment does not justify rerunning “no stacking.”
Stack-free candidates occupied 17% of selections, produced only two of 17
weekly bests, and slightly worsened the historical tail. A better question is
conditional: **are there simulated slate states in which a specific relaxed
shape is superior enough to deserve a few portfolio slots?** Examples include
a rushing QB whose ceiling is not carried by two receivers, a concentrated
passing game without an opposing response, an RB who receives enough targets
to coexist with an opposing DST's sack/turnover ceiling, or a genuinely split
backfield with two cheap, role-distinct backs.

Freeze a **constraint-lattice shadow** with the incumbent candidate budget:

- build the control entirely under QB+2/bring-back plus both RB bans;
- reserve no more than eight of 80 treatment entries for exceptions;
- source exception candidates from four named cells: QB+1+bring-back,
  QB+2/no-bring-back, QB+1/no-bring-back, and one-RB-ban relaxation at a time;
- require an exception to beat the weakest displaced strict lineup on held-out
  multi-seed p210 and p230 support, with the margin frozen before outcomes;
- cap each cell and each game so the selector cannot fill the sleeve with one
  narrative; and
- freeze control and treatment membership before lock, reporting candidate-
  layer and selected-book results separately.

Eight slots are a risk budget, not a fitted optimum. If the score-free gate
admits zero exceptions, that is a valid result. If exceptions are admitted,
2026 prospective slates decide whether any cell graduates. ATLAS's first A/B
should still retain the exact incumbent constraints so search geometry and
constraint relaxation are not confounded.

### Fixed 194, first-N and 80 entries confuse one validated book with a contest policy

The current contest layer changes leverage by entry cap but deliberately
keeps the 194 target and selects the first N entries from the 80-entry CBWU
order (`inference/production_policy.py:16-75`). That conflicts with the final
forensic conclusion. On the 54-slate panel, the first 20, first 40 and all 80
have mean weekly maxima of 165.916, 172.729 and 176.063. Their registered tail
counts differ materially; the report explicitly concludes that lower-entry
contests need contest-size-aware selection.

This has an immediate preseason fix that does not need a new model or outcome:
for a requested N in `{1,3,20,40,80}`, rerun the incumbent greedy selector to
choose exactly N from the full candidate pool rather than truncate a book
optimized to have 80 complementary entries. Validate that `N=80` reproduces
the incumbent exactly, then shadow the smaller books. A single-entry lineup
should maximize robust individual tail value; it should not be “the roster
that happened to be selected first while constructing an 80-way cover.”

Likewise, 80 is the end of the validated evidence, not a proof that entry 81
has zero marginal value. The code permits contest caps through 150 but rejects
more than 80. If the operator actually intends to buy more than 80 entries in
an eligible major contest, generate entries 81--150 by optimizing their
*marginal* world and interaction coverage conditional on the first 80. Do not
simply repeat the first-N idea at a larger N. Keep that expansion prospective
until its incremental overlap, effective rank, tail support and realized
return are observed.

The fixed 194 selector has a related scope problem. It is the minimum recorded
2025 Milly-winning score used as a confidence anchor, while the app separately
contains a provisional field-size line. Major-tournament winning conditions
vary with slate scoring, field size and payout shape. Historical selector
sweeps were already null, so the answer is not another retrospective threshold
search. Freeze a 2026 shadow that either covers several fixed lines jointly
(for example 194/210/230) or uses a pre-lock field-relative target produced by
a validated opponent simulator. Keep raw-score and ROI shadows separate until
ownership, duplication and standings inputs can support the latter.

### The tail-first adoption law needs robustness, not a return to averages

Prioritizing rare scores is aligned with the stated objective. The brittle
part is letting the first nonzero cell in a nested threshold grid decide.
Nested counts are not independent evidence, and one slate can create apparent
advantages at several thresholds. The fitted-K result is the clearest warning:
one 2023 slate supplied all of its new >=240, >=230 and >=210 events, while the
arm lost seven >=194 slates, three >=200 slates and 0.590 mean points. Its
240.44 still did not approach that week's recorded winner score of 294.38.

For future mechanisms, retain the frozen high-tail ordering as the **utility
signal**, but add a second **robustness gate**:

1. disclose which distinct slates generate every nested crossing;
2. compute a leave-one-slate-out decision and cap the influence of any one
   slate in a secondary weighted tail-utility diagnostic;
3. if the adoption direction disappears after removing one slate, classify
   it as a discovery and require a prospectively frozen replication rather
   than immediate money promotion; and
4. disclose lower-threshold, mean, median and season costs as mandatory risk
   diagnostics, without allowing them to be tuned into a post hoc veto.

This change would not reverse any historical decision and would not optimize
the mean. It would stop a single rare observation from being mistaken for a
stable increase in the probability of winning future tournaments.

### Keep scientific discipline, but make transfer and closure mechanism-specific

The point-in-time, audit-before-verdict and outcome-free freeze rules are among
the project's strongest assets. Weakening them would increase reported scores
by increasing leakage and researcher degrees of freedom, not by increasing
real tail probability.

The post-selection rule can be made less costly without weakening it. Build a
dependency map from each adopted mechanism to the quantities a downstream
change can alter: player marginals, candidate membership, candidate order,
world masks and selected identities. A prior verdict transfers only if a
machine-checkable equivalence certificate proves the relevant treatment-
control contrast unchanged. Otherwise revalidate. This replaces “rerun
everything after anything changes” with “rerun every comparison that can
actually change,” while retaining the burden of proof.

Closures should use the same semantics. “Gumbel/noisy MAP under the current
simulator and fixed budget” can be closed; “diverse search” should not be,
because near-optimal interaction coverage is a different mechanism. “Selector
changes under the static feature set” can be closed historically; a selector
using genuinely new prospective field or dependence information can reopen
under a frozen protocol. Every closure should record mechanism, input law,
downstream context, data window and explicit reopening condition.

Finally, the one-active-outcome firewall should serialize only work that can
read or adapt to historical scores. Code implementation, acquisition, schema
validation, score-free simulator diagnostics and already-frozen prospective
shadows can proceed concurrently without creating another historical outcome
look. That interpretation preserves the firewall while avoiding unnecessary
preseason queueing.

## New BigQuery interaction proxy: the pool has players, but not their combinations

I queried only the isolated repair4 forensic tables, filtered throughout to
`scope='phase-s-cbwu-54'`. There is an important limitation: the write-once
BigQuery oracle table contains the originally published QB+1/no-bring-back P
roster. The later exact-stack addendum recomputed corrected P but did not and
could not overwrite that table, and its immutable result exposes corrected
scores and aggregate frequency diagnostics rather than corrected roster IDs.
The pair/triple census below is therefore a **loose-P interaction proxy**, not
a corrected exact-P statistic.

For each slate I split that published loose P and every retained candidate
into player IDs, formed the 36 pairs and 84 triples in loose P, and asked
whether each tuple occurred together in at least one candidate.

| Loose-P interaction covered by any candidate | Covered | Possible | Rate | Median per slate | Range per slate |
|---|---:|---:|---:|---:|---:|
| player pair | 793 | 1,944 | 40.79% | 15 of 36 | 7--33 |
| player triple | 302 | 4,536 | 6.66% | 3 of 84 | 0--62 |

This is a directional rendering of the construction problem, not a new gap
estimate. Most of the combinations in the original player-support oracle do
not coexist in one generated roster. Some of those tuples may disappear under
the corrected production stack, so the exact rates must not be used as an
acceptance target.

The loose-P player's frequency in the retained pool is also thin:

| Position | Loose-P slots | Mean candidate frequency | Median | Slots appearing in only 1--4 candidates |
|---|---:|---:|---:|---:|
| QB | 54 | 19.44 | 6 | 24 |
| RB | 124 | 28.15 | 9 | 25 |
| WR | 188 | 17.05 | 9 | 47 |
| TE | 66 | 16.82 | 8 | 19 |
| DST | 54 | 23.50 | 15 | 11 |
| **All** | **486** | -- | -- | **126** |

In this proxy, missing interactions are not confined to one obvious position pair.
Coverage is 45.7% for QB-WR, 39.6% for WR-WR, 37.1% for TE-WR, 34.9% for
RB-RB, 29.6% for DST-QB and 28.8% for QB-TE. None of the 12 loose-P TE-TE
pairs appears in the pool. That last cell is small, loose-stack and
outcome-viewed, so it is emphatically not a case for forcing two tight ends.

The 126 loose-P slots with frequency below five averaged only 2.60 candidate
appearances, $4,769 salary, 9.93 projected mean and 22.08 served p90. The other
360 averaged 27.22 appearances, $5,779 salary, 13.26 mean and 27.53 p90. The
thin group ultimately scored 27.61 and exceeded served p90 by 5.53 on average,
versus 29.35 and 1.81 for the represented group.

The corrected exact-stack addendum independently reports 124 of its 486 P
slots below five candidate appearances, only two fewer than this loose-P
proxy, and a 5.17-swap mean distance to the nearest candidate. That supports
the direction of the diagnosis while leaving corrected exact-P pair/triple
coverage unmeasured.

The score and projection comparison is explicitly outcome-viewed. It must **not** become a
rule to prefer cheap players or to inflate a historical p90 until the miss
disappears. Its legitimate use is narrower: candidate construction needs an
outcome-free way to give a few additional combinations to tail-plausible,
low-frequency players rather than letting one linear optimum determine nearly
all of their combinatorial neighborhood.

The retained pool itself averages 253.81 lineups per slate (241--265). Thus
this is not a claim that 254 legal rosters are intrinsically too few. It is a
claim that their allocation across lineup space is poorly matched to the
observed failure.

## Code-level diagnosis

### 1. Each objective usually contributes one vertex

The base generator calls `optimize_many`, which repeatedly solves the same
linear objective and only requires a new lineup to differ from every previous
one by at least two players (`max_overlap=7`):
`src/nfl_dfs/optimizer/lineup.py:316-364`. Role, game, dark-game and boom
families similarly use one optimum for a scenario or lock, with overlap bans
providing most of the diversity.

Two-player Hamming novelty is not interaction coverage. Two lineups can meet
that rule while repeatedly using the same core and leaving most valid
QB-WR-RB, WR-WR-TE, or stack-core-plus-DST combinations untouched.

### 2. “Top boom world” is ranked by the wrong proxy

At `src/nfl_dfs/backtest/engine.py:1067`, boom worlds are ordered by
`rd.sum(axis=0)`: the total simulated points of every player on the slate.
The solver then finds the one best legal lineup in each of the first 40
worlds (`engine.py:1070-1092`).

Total slate scoring is not attainable lineup scoring. A world where 100
players are mildly high can outrank a world where one legal nine-player
combination is extraordinary. Salary, position, stacking and mutual
competition are all absent from the ranking proxy. This is testable without
opening an actual score: compare the current top-40 order with a stack-aware
LP relaxation or cheap legal-lineup heuristic over the same simulated worlds.

There is a second leak in the fixed allocation: if a boom optimum duplicates
an existing candidate, it is not appended, and the initial `_add_boom` call
does not refill the missing unique slot. “Boom 40” is therefore 40 solve
attempts, not a guarantee of 40 unique boom candidates.

### 3. CBWU adds useful search noise but does not repair within-book geometry

`combine_cbwu_books` assigns a duplicate roster to the first seed that
supplied it, admits equal source quotas, fills deficits round-robin, and caps
the combined candidate book at the R0 native count
(`src/nfl_dfs/inference/multiseed_portfolio.py:71-146`). It then cross-scores
the retained book on all five world blocks. This was a successful fixed-budget
improvement, but every native book is still produced by the same one-vertex
generator geometry.

There is a worthwhile score-free order audit. Retained candidates are almost
balanced by source seed (`2,765/2,754/2,738/2,729/2,720` across R0--R4), while
selected counts are `226/692/1,037/1,125/1,240`. That does not prove a bias;
later-seed candidates may be valuable precisely because they cover worlds
made redundant by R0. It does show a strong interaction between first-source
deduplication, novelty and greedy coverage. Rotate the five seed orders and
measure retained identities, tuple coverage and cross-world coverage before
assuming the registered ordering is operationally neutral.

### 4. The selector is doing what it was designed to do

The selector greedily covers simulated worlds in which a candidate clears 194
and only falls back to individual `p_line` and mean after coverage saturates
(`src/nfl_dfs/optimizer/lineup.py:367-430`). The corrected C-S gap and zero
first-failure count at 210 support leaving this alone while construction is
tested.

## Priority recommendations

| Priority | Proposal | Channel | New data? | Available before Week 1? | Main falsifier |
|---|---|---|---|---|---|
| P0 | Reproduce and close the apparent live inactive bypass | correctness / live inference | no | yes | an O/IR fixture receives any nonzero draw or remains optimizer-eligible |
| P0 | Emit and verify the exact effective simulator/policy receipt | correctness / dependence | no | yes | API, candidate log and deployed env disagree, or claimed dependence book used another law |
| P1 | ATLAS: attainable-world ranking + diverse near-optimal tuple coverage | construction | no | yes | no fixed-budget gain in score-free tuple coverage or robust simulated tail support; prospective treatment never adds candidate-layer tails |
| P1 | CBWU seed-order invariance audit | candidate admission | no | yes | cyclic order materially changes score-free coverage; if invariant, close the concern |
| P1 | Exact-N selectors for 1/3/20/40-entry contests | contest-specific selection | no | yes | exact-N books do not improve score-free coverage over first-N prefixes; prospective tails remain no better |
| P2 | Stack-core × shell beam recombination | construction | no | yes | produces no unique, tail-viable combinations beyond ATLAS/current pool |
| P2 | Eight-entry constraint-lattice exception sleeve | strategic constraints | no | yes | no exception clears a frozen held-out multi-seed tail gate, or prospective exception cells do not add tails |
| P2 | Add robustness and equivalence certificates to research governance | decision validity / throughput | no | yes | decisions remain single-slate fragile, or a purported transfer certificate fails identity/mask parity |
| P2 | Option-valued initial entries for late swap | decision shape / recourse | no | yes | reachable conditional-completion value does not improve prospectively over static initial books and naive mean swap |
| P2 | Sparse drive/pass-event ledger, conditional on current-law remeasurement | dependence | existing PBP/SIS is sufficient | prototype yes | joint proper scores or QB-hub/multiplicity shape fail prospectively |
| P3 | Conditional entries 81--150, only for contests actually entered above 80 | portfolio breadth | no | yes | marginal books add no effective rank or robust world coverage after conditioning on the first 80 |
| P3 | Coherent market-disagreement scenario worlds | construction / epistemic | live props or preseason market snapshots | mostly | treatment candidates are not novel or robust under incumbent scoring worlds |

## P0: live correctness and policy identity

### Apparent inactive-player bypass

The scheduled stored-projection job does the right conceptual work:
`run_projections.project` applies `_cascade_adjuster` and then
`zero_out_projections` for out players
(`src/nfl_dfs/inference/run_projections.py:99-211,214-242`). The sim-mode money
path does not use those stored distributions. It calls
`build_slate_with_draws`, predicts components again from
`upcoming_slate_features`, and builds fresh draws
(`src/nfl_dfs/inference/live_lineups.py:98-247`). That function does not call
the inactive adjuster and does not carry `status` into its optimizer frame.

The app's `_classic_projections` intersects projections with all salary-list
IDs but does not filter the salary `status`; `_build_classic` passes those IDs
as `allowed_ids` (`src/nfl_dfs/app/main.py:2345-2425`). Consequently, an O/IR
player that remains in the DraftKings draftable list can apparently survive
the ID restriction and receive newly recomputed nonzero draws.

This should be settled with one isolated integration fixture before any
research work:

1. put a skill player with DK status `O` in the chosen draft group and in
   `player_week_inference`;
2. confirm the player is present in `_classic_projections`;
3. run the actual sim-mode call with no manual ban;
4. assert the player is absent from the player universe or has exactly zero
   draws and can never enter a lineup; and
5. assert vacated usage is redistributed once, not lost and not double-counted.

If DraftKings always removes the draftable ID first, the fixture will show the
path is currently protected by an external invariant. That invariant should
still be explicit and fail closed, because salary-feed behavior is not a safe
substitute for a lineup eligibility rule.

### The production Dirichlet contradiction

The briefing's current-state list says fitted Dirichlet
`K=28.154043586960896` is live. The code reviewed does not:
`ClassicProductionPolicy.engine_environment` pins
`GAME_SIM_USAGE=""` (`src/nfl_dfs/inference/production_policy.py:132-144`),
and `simulate.py` activates the within-team Dirichlet only when that value is
exactly `dirichlet` (`src/nfl_dfs/models/simulate.py:331-344`). The CBWU result
and adoption record explicitly say finite-K was a separate result not licensed
into the K=1 money composition.

Therefore the reported “current” QB-to-WR and high-multiplicity dependence
figures cannot be assumed to describe the deployed path until their receipt is
checked. The right preseason action is:

- serialize the complete effective `policy_env` used by each money build;
- include simulator law, exact model/cache identity and hashes in the API/CSV
  policy receipt and candidate log;
- have one test assert that the UI description is generated from that receipt;
- rerun the score-free/held-out dependence diagnostic under that exact receipt;
  and
- do not turn on finite-K merely to make the document and code agree.

This could prevent the team from spending preseason effort correcting a
dependence shape that belongs to a different simulator composition.

## P1: ATLAS — Attainable-Tail Lineup Array Search

ATLAS is one combined mechanism, not a menu of unrelated knobs.

### Step A: rank worlds by attainable tail

For each simulated world, compute a cheap score that respects more of the
lineup problem than total slate points. Three implementation levels are
possible:

1. **Immediate heuristic:** top feasible score by position with one QB, one
   DST and seven eligible skill slots, ignoring only salary and stack. This is
   still a much tighter proxy than summing the slate.
2. **Preferred:** solve the LP relaxation of the actual lineup MILP for every
   world. LPs should be far cheaper than 10,000 integer solves and provide an
   upper bound on attainable legal score.
3. **Fallback:** a stack-core enumeration plus greedy salary-feasible fill.

Select high-bound worlds with a diversity constraint on their top-player set,
QB stack core and dominant game. This avoids spending 40 solves on essentially
the same all-slate scoring regime.

The score-free diagnostic is simple: among the current top-total 40 and the
new top-attainable 40, compare the distribution of exact MILP optimum scores
after solving both small sets. If total-slate ordering is a good proxy, the
proposal dies cheaply.

### Step B: enumerate the near-optimal face, not just its highest vertex

Choose eight structurally distinct worlds. For each, produce five unique
lineups, for exactly 40 boom candidates:

1. solve the world optimum `z*`;
2. constrain subsequent lineups to simulated world score at least
   `z* - delta` (start with a frozen, scale-free tolerance such as 98% of
   `z*`, not an outcome-tuned point value);
3. among that near-optimal set, maximize a secondary uncovered-interaction
   objective; and
4. ban the exact prior roster and refill until five unique lineups exist or
   the near-optimal region is proven exhausted.

This can be implemented with the existing repeated MILP approach; a new
commercial solver is not required. If infrastructure permits it, Gurobi's
[official solution-pool mechanism](https://docs.gurobi.com/projects/optimizer/en/current/features/solutionpool.html)
can retrieve multiple high-quality solutions, while Google OR-Tools documents
[CP-SAT solution enumeration](https://developers.google.com/optimization/cp/cp_solver).
The optimization literature also directly supports searching for diverse
near-optima rather than only a single optimum; see
[DiversiTree](https://pubsonline.informs.org/doi/10.1287/ijoc.2022.0164).

### Step C: price valid player interactions

Define an outcome-free eligible interaction universe from the current slate:

- a player must occur in at least one native R0--R4 candidate or meet a frozen
  multi-seed tail-plausibility rule;
- a pair/triple must be jointly feasible under salary, position and the exact
  production stack rules;
- stack-core interactions receive their joint simulated tail probability;
- non-stack interactions receive a trimmed mean or minimum across R0--R4
  blocks so one lucky seed cannot dominate; and
- an inverse-frequency factor gives a moderate bonus to a plausible tuple
  that has little existing candidate coverage.

For a pair `(i,j)`, add a binary `y_ij` with the usual linearization
`y_ij <= x_i`, `y_ij <= x_j`, and `y_ij >= x_i+x_j-1`. The secondary pricing
objective is the sum of weights for currently uncovered `y` variables. After
each accepted lineup, covered weights decay or are removed. Start with pairs;
triples can be limited to stack cores and the highest-weight cross-game
interactions to control model size.

This is an adaptation of constrained t-way coverage. NIST's
[combinatorial coverage framework](https://www.nist.gov/publications/combinatorial-coverage-measurement)
formalizes the measurement of how much of a t-way state space a finite suite
covers. It is not evidence that player-pair coverage causes DFS wins; the
BigQuery result supplies the project-specific reason to test the adaptation.

### Why this differs from prior failed families

- It is not a selector change: the incumbent 194 world-coverage selector sees
  the final pool unchanged in size.
- It is not more candidates: 40 candidates replace the 40 boom allocation.
- It is not Gumbel/noisy MAP: the primary tail world is fixed, solution quality
  is bounded, and diversity is optimized inside its near-optimal region.
- It is not retrospective archetype fitting: weights use only pre-lock draws,
  feasibility and existing candidate frequency.
- It is not generic Hamming diversity: it covers named, valid interactions
  that can be audited before outcomes.

### Frozen MVP and falsification

I would freeze one treatment, not sweep a grid:

- current 160 leverage candidates and all non-boom families unchanged;
- current five CBWU seeds and five scoring blocks unchanged;
- exactly eight attainable-world clusters × five near-optimal rosters;
- pairs as the primary coverage objective, with only stack-core triples;
- exact realized candidate count matched to control through deterministic
  refill; and
- incumbent selector and exact-80 export unchanged.

Before an outcome is visible, reject the build if it fails exact player/world
parity, fixed candidate count, legality, or unique-roster checks. Record:
weighted eligible pair/triple coverage, player-frequency distribution, stack
core coverage, simulated p194/p210/p230 on each held-out seed block, effective
rank and overlap with control.

The real falsifier is prospective candidate-layer performance. Freeze both
candidate books before lock and, after each slate, compare the best treatment
candidate with the best control candidate and the exact selected 80 at the
registered thresholds. Do not tune eligibility, tolerance or weights after a
bad week. Predeclare checkpoints (for example Weeks 4/8/13/18) and require the
same tail-first ordering used by the project, while disclosing distinct slate
crossings rather than treating nested counts as independent.

## P2: stack-core × shell recombination

This is a complementary construction method if ATLAS's pair-variable MILP is
too slow.

Represent a legal lineup as:

- a **core**: QB, two same-team pass catchers and one opponent bring-back; and
- a **shell**: the remaining RB/WR/TE/FLEX/DST choices.

Enumerate a moderate number of multi-seed tail-plausible cores, then build a
beam of salary-feasible shells. Recombine core and shell columns using an
upper bound on robust joint tail and retain combinations that add uncovered
core-shell pairs. The current generator varies a whole nine-player linear
optimum at once; this method explicitly crosses useful partial solutions that
may never be adjacent under a single objective.

It needs no new data. It should be tested at a fixed candidate budget and is
falsified if its candidates are mostly duplicates, have inferior robust
simulated tail, or fail to expand valid interaction coverage. If it works, it
can be the pricing oracle inside ATLAS rather than a separate production arm.

## P2: value late-swap options before the first lock

The rejected 3:55 PM tail-aware reoptimizer does not close the recourse
channel. It tested a static initial book and reacted once, after exact-P misses
were already 4.5 players locked on average. A different question is whether
the *initial* 80 should be constructed as a portfolio of contingent policies.

At 12:55 PM, each entry commits its early players but retains a set of legal
late completions. The value of an entry is then not only its static p194; it is
the distribution of the best reachable completion after early scores and
late news are observed. A two-stage MVP would:

1. group simulation worlds into a small number of early-score information
   states;
2. construct an early core shared across worlds that are indistinguishable at
   lock;
3. optimize a legal late completion separately within each state;
4. value the root entry by its state-weighted probability of reaching the
   tail; and
5. select 80 roots to cover both early worlds and late completion branches.

The nonanticipativity rule is essential: a swap policy may use only information
available at that time. This is exactly the “decide-observe-decide” structure
of multistage recourse described in the INFORMS tutorial
[Stochastic Programming: Optimization When Uncertainty Matters](https://pubsonline.informs.org/doi/10.1287/educ.1053.0016).
Problem-driven scenario-tree reduction is preferable to arbitrary score bins;
see [Keutchayan, Munger and Gendreau](https://pubsonline.informs.org/doi/10.1287/moor.2019.1043).

This uses existing simulations and kickoff times and can be shadowed from Week
1. Compare four prospective cells: static/no-swap, static/naive-mean swap,
option-valued/no-swap and option-valued/naive-mean swap. That separates value
created at initial construction from value created by the later action.

Useful pre-lock diagnostics are the number of legal late completions, their
effective diversity, salary/FLEX reachability and conditional tail value. The
falsifier is not the hindsight ceiling; it is failure to improve frozen
prospective portfolios over the static-plus-naive comparator.

## P2: dependence as a sparse event ledger, after policy reconciliation

If an exact deployed-environment rerun confirms an under-coupled QB hub and
over-coupled high multiplicity, another global copula strength is unlikely to
work. The desired shape is selective: a QB boom should strongly carry one or
two receivers, not make three or four teammates exceed together.

A plausible mechanism is a **sparse pass-event ledger**:

1. simulate team drives, plays and pass attempts;
2. draw a shared QB efficiency/volume state;
3. activate one or two primary receiving paths in each high-pass world;
4. allocate targets, completions, yards and TDs through those conserved team
   events; and
5. derive QB and receiver fantasy points from the same events.

This is not the rejected TD-only ledger. Conservation applies to attempts,
completions, yards and scores together, so the same latent event creates the
QB hub while competition for a finite event pool limits receiver multiplicity.
Play/drive simulation from historical PBP is a practical, published approach;
the [NFLSimulatoR paper](https://ideas.repec.org/a/spr/annopr/v325y2023i1d10.1007_s10479-022-04524-7.html)
is one relevant reference.

The project already has PBP and SIS inputs, so no new in-season collection is
required for a prototype. To respect historical closure, freeze parameters on
a predeclared pre-2026 training window and evaluate lineup consequences only
prospectively. Gate first on marginal preservation and joint proper scores,
then QB-WR, WR-WR and multiplicity shape. If the current production-law audit
does not reproduce the briefing's dependence error, this proposal should be
reframed or dropped.

## P3: preserve model/market disagreement as coherent generator worlds

The 45/55 blend is reasonable for a served mean but can erase tail-relevant
disagreement. When the model says a receiver is a 9-point player and a market
or role source says 16, the 12.9-point average describes neither coherent
state. Use disagreement in candidate generation rather than changing the
money marginal:

- model-dominant and market-dominant team states;
- alternate-prop-ladder ceiling states;
- coherent injury/role states across a depth chart; and
- line-movement states captured at fixed pre-lock timestamps.

Each state must move an entire team/game story, not independently boost the
largest player disagreements. Candidate lineups can still be scored and
selected on the incumbent five CBWU world blocks, making this a discovery
mechanism rather than a silent marginal promotion. Existing `prop_lines`,
market-tail and injury/depth infrastructure covers much of this; best-ball ADP
or another preseason market can be added as a role-belief source now, with no
need to wait for 2026 outcomes.

This is lower priority than ATLAS because the forensic bottleneck is combining
supported players, not admitting beliefs. Its falsifier is straightforward:
if coherent disagreement worlds do not add novel, robustly tail-viable
candidates at a fixed allocation, close them.

## A separate ROI extension, not the first raw-score experiment

The current 194 objective targets a raw score event. Winning a major GPP also
depends on the field maximum and duplication. Academic DFS work explicitly
models fixed-cardinality portfolios in top-heavy contests; see
[Hunter, Vielma and Zaman](https://arxiv.org/abs/1604.01455) and
[Haugh and Singal](https://pubsonline.informs.org/doi/10.1287/mnsc.2019.3528).

Eventually, candidate value should be tested against a simulated field and
payout surface rather than only `score >= 194`. However, ownership is disabled
in the adopted policy and prior chalk/selector arms are closed. Field-aware EV
should therefore be a separately frozen prospective ROI shadow after candidate
construction improves—not a reason to replace the raw-score selector now.

## Recommended preseason sequence

### First 48 hours

1. Reproduce the inactive-player path with a real sim-mode fixture.
2. Capture the exact deployed effective-policy receipt and reconcile the
   Dirichlet/dependence statements.
3. Run the score-free boom-world diagnostic: total-slate rank versus attainable
   legal-lineup rank on existing simulations.
4. Rotate CBWU seed order score-free and quantify retained/selected identity,
   tuple coverage and cross-world coverage sensitivity.
5. Re-select the incumbent candidate pool at exact N=`1/3/20/40/80`; require
   exact reproduction at 80 and compare score-free world coverage against each
   current first-N prefix.

### Next five days

1. Build an offline ATLAS prototype with pairs only.
2. Compare current 40 boom attempts against 8×5 attainable/near-optimal
   candidates under identical worlds and fixed realized candidate count.
3. If repeated CBC solves are too slow, prototype stack-core × shell pricing.
4. Freeze one Week-1 ATLAS shadow, including eligibility, tolerance, weights,
   seed blocks, metrics and checkpoint rule.
5. Build the constraint-lattice candidates score-free, but do not combine that
   treatment with ATLAS; freeze a separate eight-entry exception shadow only
   if candidates clear the registered multi-seed admission gate.
6. Add the distinct-slate and leave-one-slate-out robustness report to the
   next adoption protocol, plus an explicit dependency/equivalence map.

### Before the first regular-season lock

1. Exercise both control and treatment on a posted DraftKings slate.
2. Verify exact draftable IDs, status exclusion, salaries, stack legality,
   80-entry export and candidate persistence.
3. Freeze control and treatment books before kickoff.
4. Start the option-valued late-swap shadow only if its information timestamps
   and nonanticipativity checks are mechanically enforced.
5. If small-contest books pass score-free gates, freeze purpose-built 1/3/20
   books before lock. If more than 80 entries will actually be purchased,
   separately freeze the conditional 81--150 book; otherwise do not spend
   preseason compute on it.

## What I would not spend the remaining preseason on

- another sweep of the 194 selector;
- another global correlation or temperature scalar;
- a direct switch to finite Dirichlet solely because the briefing says it is
  current;
- expanding the candidate or entry budget without optimizing its marginal
  allocation;
- more noisy-objective/Gumbel MAP solves;
- loosening the salary floor broadly;
- fitting exact-P player, salary or positional contrasts back to the 54 viewed
  outcomes; or
- treating nested threshold deltas as independent evidence.

## Final assessment

The system is much closer to having the right players than to building the
right lineups. Its simulation work is sophisticated, but the final conversion
from worlds to candidates is still largely “one score vector, one optimizer
vertex.” The BigQuery loose-P proxy makes that compression visible: 59% of its
pairs and 93% of its triples never appear together in a candidate. The
corrected exact-stack result separately confirms 124 thin-frequency P slots
and a 5.17-swap distance, but corrected exact-P tuple coverage remains
unmeasured and should not be implied by the proxy.

ATLAS is the most direct, preseason-ready response. It changes the boom family
from 40 loosely chosen point optima into a fixed-size array of legal,
attainable, near-optimal and interaction-diverse lineups. It is cheap to kill
with score-free diagnostics if the premise is wrong, and it can be evaluated
honestly on frozen 2026 books if the premise survives. That combination—large
measured opportunity, genuinely different search geometry, no new outcome
dependency and clear falsification—is stronger than any additional marginal
or selector refinement I found.

The rule review changes the framing around that recommendation. The project
should remain uncompromising about legality, point-in-time correctness,
provenance and outcome blindness. It should be less categorical about
strategic geometry. The clearest immediate correction is purpose-built exact-N
selection instead of first-N slicing. The highest-upside controlled question
is whether a small conditional sleeve can relax stack/anti-correlation rules
without weakening the strict majority book. The adoption law itself should
continue to value extreme scores, but a one-slate high-tail event should earn
a prospective replication—not automatic authority over future money lineups.

## Reproducibility notes and external sources

BigQuery calculations used these write-once tables and always filtered the
candidate, oracle and player data to `phase-s-cbwu-54`:

- `nfl_forensic_review.final_forensic_20260814_candidate_corpus_repair4`
- `nfl_forensic_review.final_forensic_20260814_oracle_rosters_repair4`
- `nfl_forensic_review.final_forensic_20260814_player_corpus_repair4`

The BigQuery interaction comparison uses the published loose-stack P roster
and is descriptive and outcome-viewed. Corrected exact-P aggregate statements
come only from the immutable exact-stack addendum. No realized score was used
in the proposed ATLAS eligibility or weighting design.

Primary local evidence for the rule audit:

- `CLAUDE.md:43-50,108-139` for point-in-time, validation, transfer and
  mechanism-scoped closure rules;
- `src/nfl_dfs/optimizer/lineup.py:270-313` for stack, bring-back and both RB
  anti-correlation constraints;
- `src/nfl_dfs/inference/production_policy.py:16-75` for the 80-entry ceiling,
  first-N slicing and unchanged tail line across contest profiles;
- `reports/2026-08-15-post-forensic-exact-stack-addendum-result.md` for the
  stack-shape and salary-floor opportunity costs;
- `reports/2026-08-14-final-preseason-forensic-result.md` for the 20/40/80
  prefix results and explicit need for contest-size-aware selection; and
- `reports/2026-08-12-marginal-arm-pattern-adoption-risk-reconciliation.md`
  for the single-slate concentration and lower-threshold cost of the fitted-K
  tail-first adoption.

External sources used for method transfer:

- D. Kuhn, R. Kacker and Y. Lei,
  [Combinatorial Coverage Measurement, NISTIR 7878](https://www.nist.gov/publications/combinatorial-coverage-measurement).
- I. Ahanor, H. Medal and A. Trapp,
  [DiversiTree: diverse near-optimal MIP solutions](https://pubsonline.informs.org/doi/10.1287/ijoc.2022.0164).
- Gurobi,
  [Solution Pool reference](https://docs.gurobi.com/projects/optimizer/en/current/features/solutionpool.html).
- Google OR-Tools,
  [CP-SAT solution enumeration](https://developers.google.com/optimization/cp/cp_solver).
- D. Hunter, J. Vielma and T. Zaman,
  [Picking Winners in Daily Fantasy Sports Using Integer Programming](https://arxiv.org/abs/1604.01455).
- M. Haugh and R. Singal,
  [How to Play Fantasy Sports Strategically (and Win)](https://pubsonline.informs.org/doi/abs/10.1287/mnsc.2019.3528).
- J. Higle,
  [Stochastic Programming: Optimization When Uncertainty Matters](https://pubsonline.informs.org/doi/10.1287/educ.1053.0016).
- J. Keutchayan, D. Munger and M. Gendreau,
  [On the Scenario-Tree Optimal-Value Error for Stochastic Programming Problems](https://pubsonline.informs.org/doi/10.1287/moor.2019.1043).
- B. Williams, W. Palmquist and R. Elmore,
  [Simulation-based decision making in the NFL using NFLSimulatoR](https://ideas.repec.org/a/spr/annopr/v325y2023i1d10.1007_s10479-022-04524-7.html).
