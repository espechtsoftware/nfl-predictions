# Review of the ATLAS approach, score-free diagnostic and next MVP

**Date:** 2026-08-15  
**Brief reviewed:** `reports/2026-08-15-atlas-approach-and-status-brief.md`,
SHA-256 `8cfc3584beaa3ed42f4603cf7cd90016345a0881cbfa24c6b4e82d3a3976ad79`  
**Repository reviewed:** `main` at
`3176b894357cff899b2465cd68a7a05b032a9b44`  
**Frozen ATLAS code:** `81b5c6e97c519babb8d7bb711c915ca70a2a51ba`;
the five reviewed ATLAS files are unchanged between that commit and current
`HEAD`  
**Validation performed:** `tests/test_atlas_world_ranking.py`: 5 passed  
**Scope:** review and recommendations only; the running/frozen execution,
production policy, code and cloud state were not changed

## Bottom line

ATLAS remains one of the best available ideas for the measured construction
failure. The current code is a legitimate outcome-free test of whether a
position-aware world score retrieves higher-quality legal optima than the
incumbent whole-slate total. The use of the union of both top-40 sets, exact
MILP solves under the same lineup constraints, immutable player-world
artifacts and a create-only report is a strong design.

I would not, however, let the current binary six-condition result alone decide
whether the 8-by-5 MVP is built. Four issues need to be separated:

1. **The diagnostic worlds are not the current money-policy worlds.** They are
   the finite-K, SIS-ASOE Phase S treatment artifacts, while the production
   receipt says multinomial/K=1 with no ASOE usage allocation. World ranking is
   a joint-distribution mechanism, so this result does not automatically
   transfer.
2. **The gate conflates Part A with Part B.** Raw top-40 structural diversity
   can veto an excellent ranking proxy even though the next ATLAS stage is
   specifically designed to impose structural clustering.
3. **Forty boom solves are not necessarily 40 realized candidates.** The
   incumbent skips duplicate boom optima and does not refill the initial boom
   batch. An ATLAS treatment that contributes 40 unique rosters can gain from
   a larger realized candidate budget rather than search geometry.
4. **The gate relies on roster identities without fully canonicalizing tied
   world ranks and tied MILP optima.** Exact scores can remain correct while
   roster/core/game diversity changes due only to tie handling or solver
   choice.

These are amendments to interpretation and the next stage, not reasons to
cancel or mutate the frozen execution. The useful decision is:

- interpret the current run only for its exact Phase S world law;
- make one outcome-free current-money-law confirmation the transfer gate;
- evaluate ranking quality separately from diversity-constrained retrieval;
- build the eventual MVP on the passed order-invariant CBWU-OI admission base;
  and
- require realized post-dedup candidate-count parity and deterministic
  multiobjective solves.

## What is already well designed

Several choices in the brief and code should be preserved.

### The diagnostic asks a narrow, falsifiable question

`roster_slot_upper_bound` enforces the exact three legal RB/WR/TE count shapes
plus one QB and one DST, while explicitly relaxing salary, team, stack,
minimum-game and RB anti-correlation constraints
(`atlas_world_ranking.py:19-64`). This is mathematically a valid upper bound on
the exact legal optimum. The code then exact-solves only the union of control
and treatment worlds under the same production lineup constraints
(`atlas_world_ranking.py:183-223`). The assertion that no exact optimum exceeds
the proxy bound is an appropriate mechanical guard.

### The comparison is paired and outcome-free

Both ranks operate on the same player-by-world matrix. The runner's SQL selects
artifact identities and pre-lock player metadata, and the artifact decoder
accepts only candidate totals, player IDs and player draws. The score-free
gate refuses rows that do not explicitly declare
`uses_realized_outcomes=False`. No historical player score is needed to answer
whether one rank retrieves higher simulated legal optima.

### The first MVP preserves causal attribution

Keeping the salary floor, exact stack rules, other generator families and the
final selector fixed is correct. ATLAS should not be bundled with exact-N,
stack relaxation, a new simulator or late swap. The first implementation must
answer whether new world/near-optimal search geometry improves construction at
the same opportunity budget.

### The project correctly distinguishes a premise gate from adoption

Even a clean score-free pass does not establish realized C, S or ROI. Requiring
pre-lock 2026 books and fixed checkpoints before a money promotion is the right
boundary. The brief is also right not to treat CBWU-OI's 194--210 construction
gain as evidence that ATLAS will improve 220+.

## Finding 1 — the running result has a simulator-law transfer boundary

This is the most important omission in the brief.

The runner hard-codes source panels
`20260813-sis-asoe-treatment-r0-v1` through `r4-v1`
(`scripts/run_atlas_world_ranking.py:34-35`). Those Phase S treatment worlds
inherit fitted `K=28.154043586960896` and SIS ASOE. ASOE deliberately preserves
each player's marginal draw multiset while changing joint rank order; finite K
changes within-team opportunity concentration. Those are precisely the kinds
of changes that can alter:

- which worlds have a high whole-slate total;
- which worlds concentrate points in a legal nine-player roster;
- how many top worlds share a QB core or game; and
- whether a position-only proxy is tight or loose.

The current money receipt instead pins `GAME_SIM_USAGE=""`, no Dirichlet K and
`usage_allocation="production-multinomial"`
(`inference/production_policy.py:151-164,355-361`). The CBWU adoption record is
also explicit that the generic multi-seed mechanism retained K=1 money-policy
marginals and did not transfer the finite-K research composition.

Therefore:

| Current score-free result | Valid inference |
|---|---|
| Passes on Phase S finite-K + ASOE | The proxy is worth pursuing under that joint world law; current-money transfer remains untested |
| Fails on Phase S finite-K + ASOE | This proxy fails under that law; it does not kill the production-multinomial version |
| Passes again on current money worlds | Part A has a robust production-relevant premise |
| Passes only under one law | Treat world ranking as simulator-conditional; do not use it in the other policy |

### Concrete amendment

Do not change or rerun the active artifact. After harvest, generate five
outcome-free R0--R4 player-world blocks from the exact public money-policy
receipt and run the same frozen control/treatment comparison on those blocks.
This can be a smaller transfer confirmation if compute is constrained, but it
must preserve all 54 slates or use posted 2026 slates without outcomes. Record
both simulator-law receipts next to the result.

No historical actual is required, and no ATLAS parameter changes between
laws. If current-law artifacts cannot be produced before Week 1, the Phase S
result may license engineering the offline solver, but not a production-law
ATLAS shadow claim.

The brief should explicitly name the source law instead of calling the five
inputs merely “R0--R4 simulation panels.”

## Finding 2 — ranking quality and structural diversity should not be one conjunctive veto

The frozen gate requires all three quality conditions and all three diversity
ratios to pass. That is understandable as a collapse guard, but it does not
faithfully decompose ATLAS:

- Part A ranks worlds by attainable quality.
- Part B deliberately selects eight structurally different worlds.
- Part C searches several solutions within each world.

The current diagnostic applies no Part-B clusterer. It takes the raw top 40 by
each rank. A treatment can therefore retrieve much better legal optima but
fail because those top 40 concentrate on one game. That would establish the
need for Part B, not falsify Part A.

The reverse problem is also possible. The diversity metrics are counts of
unique rosters, variable-length QB stack cores and one dominant-game label.
They do not measure evenness. Thirty-three worlds can resolve to one game and
the remaining seven to seven different games, producing the same unique-game
count as a much more balanced set. A tied dominant-game count is reduced to
the lexicographically first game (`atlas_world_ranking.py:128-140`), which
also discards part of the structure.

Finally, the gate averages per-row ratios without capping them
(`atlas_world_ranking.py:245-250,273-280`). Diversity gains on some
seed/slates can compensate for severe collapse on others. For example, equal
numbers of rows at 50% and 110% of control average 80% and pass even though
half the books lose half their diversity.

### Concrete amendment

Honor the frozen six-condition result, but interpret it by condition:

- **quality fails:** investigate proxy looseness/current-law transfer before
  building Part A;
- **quality passes and only diversity fails:** do not kill the rank; run the
  already-fixed structural clusterer on a larger top-M treatment set and
  compare diversity-constrained control versus treatment;
- **quality and diversity pass:** proceed to the Part-B/C engineering MVP,
  subject to the other findings here.

For the next score-free stage, report:

- capped preservation, `mean(min(treatment/control, 1))`, so gains cannot hide
  collapses;
- the q10/median/minimum per-slate preservation ratio;
- entropy or Simpson effective counts for QB, stack core and game;
- pairwise roster overlap and top-player-set Jaccard;
- the full maximum-game-count signature, including tied games; and
- quality *after* applying the same frozen eight-cluster selection rule to
  both arms.

The decisive Part-B test is not “does the raw top 40 happen to be diverse?” It
is “at a fixed structural-diversity requirement, does the attainable rank
retain higher exact legal quality?”

## Finding 3 — the position-only bound is a good first probe, but a poor final falsifier

The current bound can be very loose when the highest-scoring players in a
world are jointly unaffordable or cannot form the required stack. A loose
upper bound is still mathematically correct, but it can rank worlds by
infeasible concentration. A failure would then reject the approximation, not
the attainable-world idea.

Solving 10,000 legal MILPs per seed/slate is unnecessary. A substantially
tighter salary-aware upper bound can remain vectorized through Lagrangian
relaxation. For any nonnegative salary price `lambda`:

```text
legal optimum
    <= lambda * 50,000
       + best roster-shape sum of (world_score_i - lambda * salary_i)
```

Taking the minimum across a small, frozen grid of nonnegative `lambda` values
remains an upper bound. It reuses the current top-k-by-position machinery,
adds no outcome data and costs only several vectorized passes over the 10,000
worlds. The `lambda=0` cell exactly reproduces the current position-only bound,
so the new bound can only tighten it.

A second option is a cascade:

1. position/Lagrangian bound over all 10,000 worlds;
2. LP relaxation or stack-core relaxation only for the top 100--200;
3. exact MILP for the final control/treatment union.

### Missing diagnostic needed to choose

The current report stores world IDs and exact union results, but not the proxy
value or proxy-minus-exact slack for those worlds. Consequently a pass/fail
cannot show whether the bound was informative or merely lucky. The source
artifacts make this reconstructable without outcomes. Before killing Part A or
choosing an LP implementation, report:

- bound-minus-exact slack by arm, seed and slate;
- rank correlation between proxy and exact optimum inside the solved union;
- exact-quality win/tie/loss counts by seed/slate;
- overlap at the top-8, top-20 and top-40 cutoffs; and
- tie counts at and near the top-40 cutoff.

Do not tune a salary-price grid against realized fantasy scores. It can be
fixed from slate salary geometry or generic dimensional coverage and judged
only on exact simulated legal optima.

## Finding 4 — “40 boom candidates” needs a realized-budget contract

The brief says 8 clusters by 5 solutions “produces exactly 40 boom candidates,
matching the incumbent allocation.” The incumbent code actually takes 40
worlds as solve attempts. When an exact optimum duplicates a roster already in
`seen`, it is skipped (`backtest/engine.py:1067-1092`). The initial boom batch
has no refill. Thus control can contribute fewer than 40 unique candidates.

ATLAS is specifically designed to generate several different rosters and is
more likely to contribute 40 unique additions. If treatment is allowed 40
realized rosters while control contributes, for example, 34, part of any C
gain is an added-budget effect.

### Concrete amendment

Freeze the causal unit as **realized post-dedup candidate count**, not solve
attempts:

1. Build all unchanged non-boom families first and freeze their `seen` set.
2. Record the number of unique boom candidates the incumbent actually adds
   for each native R0--R4 seed/slate.
3. Generate ATLAS proposals while banning every pre-existing non-boom roster
   and every earlier ATLAS roster.
4. Admit exactly the incumbent realized count, round-robin across the eight
   clusters so truncation cannot favor cluster 1.
5. Report solve attempts, feasible near-optimal solutions, duplicate proposals
   and unique additions as an efficiency diagnostic.
6. Preserve exact total native-book and final CBWU-OI admission counts.

If the project prefers a clean 40-versus-40 comparison, it must also create a
deterministically refilled incumbent control. That is a different control from
production and should be labeled as such. The primary promotion comparison
should retain production's realized opportunity budget.

At 98%, a world may not contain five distinct legal solutions after global
deduplication. Do not relax the tolerance after seeing outcomes. Use a frozen
refill hierarchy: next qualifying world within the same cluster, then next
structurally eligible cluster, all at the same 98% rule. If the fixed hierarchy
cannot reach count parity, the treatment fails mechanically.

## Finding 5 — ATLAS should be incremental to CBWU-OI, not entangled with canonical admission

CBWU-OI has now passed its score-free order-invariance gate and, in the
separate fixed-budget construction diagnostic, changed C materially. The
canonical CBWU admission is order-sensitive. An ATLAS test built on canonical
admission would inherit that nuisance, while an ATLAS-versus-canonical result
could mix better boom generation with first-source quota/fill behavior.

Use the same passed order-invariant admission and the same five scoring blocks
for both generation arms:

| Book | Boom generation | Admission | Purpose |
|---|---|---|---|
| P0 | incumbent | canonical production CBWU | money-policy context only |
| P1 | incumbent | CBWU-OI | clean construction base |
| P2 | ATLAS | CBWU-OI | incremental ATLAS effect |

The scientific ATLAS contrast is P2 versus P1. P2 versus P0 is the composite
prospective opportunity, not attribution to ATLAS alone. Freeze all three
before lock and do not use the already-viewed historical CBWU-OI C result to
alter ATLAS's clusters, tolerance or weights.

This design also lets the project answer a useful question: does ATLAS add new
combination geometry after order-invariant complete-union admission has
already captured the easier construction gain?

## Finding 6 — measure novelty conditional on the rest of the candidate pool

The current structural metrics are internal to the 40 selected worlds. They do
not ask whether an exact world optimum is already present in role, game,
dark-game or other non-boom candidates. Forty unique ATLAS rosters can still
add zero marginal candidate identities or pairs to the full pool.

Before the outcome-facing MVP, add score-free marginal receipts:

- unique ATLAS additions after global deduplication;
- roster overlap with each non-boom family and incumbent boom candidates;
- new player pairs and stack-core triples conditional on the frozen non-boom
  pool;
- weighted pair coverage gained per admitted candidate; and
- held-out p194/p210/p230 of each novel candidate across blocks not used to
  generate its pair weights.

This is also the right response to the CBWU-OI finding that better C came from
combination breadth despite worse player coverage. Generic unique-roster
counts are not enough; the relevant quantity is *marginal interaction reach in
the complete candidate pool*.

## Finding 7 — canonicalize both world ties and MILP ties before using identities as a gate

`rank_worlds` deliberately breaks value ties by lower world ID
(`atlas_world_ranking.py:67-76`). The incumbent engine uses
`np.argsort(rd.sum(axis=0))[::-1]` (`backtest/engine.py:1067`), which has a
different tie convention and uses the default sort kind. The diagnostic thus
matches the incumbent concept but has not proven exact top-40 identity parity
when whole-slate totals tie.

The exact optimizer also maximizes only the floating primary score. It has no
canonical secondary objective. Two equally optimal legal rosters can return
the same exact score but different roster, QB-core and dominant-game
identities. Because three gate conditions depend on those identities, solver
tie behavior can affect the disposition without affecting quality.

### Concrete amendment

- Add a score-free tie audit for whole-slate totals, especially at the top-40
  boundary. If ties exist, extract one shared ranking helper and use it in both
  production control and diagnostic.
- Use a two-pass lexicographic MILP for ATLAS diagnostics and MVP: maximize
  primary score; constrain score to the exact optimum within a declared
  numerical tolerance; then minimize a stable roster-identity rank or hash.
- For near-optimal lineups, use explicit three-stage optimization: satisfy the
  98% floor, maximize uncovered interaction weight, then apply a deterministic
  tertiary tie-break.
- Add repeated-run and player-row-permutation fixtures proving identical world
  IDs, rosters, cores and games.

Do not add tiny ID coefficients to the primary objective in one pass; their
scale can accidentally trade real score for deterministic identity.

## Finding 8 — harden the aggregate gate and strict finisher before the outcome-facing MVP

The current focused tests cover the happy path, one deliberate ranking
disagreement, deterministic rank ties and a basic outcome flag. They do not
exercise the individual gate failure modes, real optimizer legality, row-order
invariance or strict source-key coverage.

The finisher also trusts `status.conditions[0].status` as the completion state
and compares the report's self-declared image/code to the local manifest
(`cloud_finish_atlas_world_ranking.sh:15-19,33-44`). It does not independently
bind the retained report to the Cloud Run execution's actual image, command,
arguments, environment, resources or service account. Nor does it verify that
the 270 source receipts and diagnostics have exactly one common key set of 54
slates per seed.

The launch script itself passes the same image string to deployment and the
`ANALYSIS_IMAGE` environment, so accidental mismatch is unlikely. A “strict”
harvester should nevertheless verify independent execution metadata rather
than only a self-report.

### Concrete amendment

Before the historical engineering MVP or any outcome-facing shadow:

- locate the Cloud Run condition by `type=Completed`, require success,
  `succeededCount=1`, `failedCount=0`, and terminal completion;
- verify the execution-owned image digest, command/args, env identity,
  task/retry/timeout/resources and service account against the manifest;
- require unique `(panel, season, week)` keys, exactly 54 identical slate keys
  in every seed, and equality of source-receipt and diagnostic keys;
- verify exact proxy name, 10,000 worlds, 40 selected worlds, relaxed-
  constraint list and production-constraint receipt;
- add tests where each of the six gate conditions fails alone;
- add a real-optimizer property test over random small slate/world fixtures
  asserting `exact <= bound`, exact legality and row-order invariance; and
- reject nonfinite aggregate metrics before gate construction rather than
  relying on JSON serialization to fail later.

These changes need not mutate the already-running execution. Apply them to the
next finisher/protocol version, or perform an independent metadata verification
alongside the frozen harvest without altering its artifact.

## Suggested definition of the Part-C interaction objective

The brief correctly refuses outcome-derived exact-P pairs. The interaction
objective can be fully pre-lock and still be more meaningful than generic
Hamming distance.

For candidate seed `Rk`:

1. Define eligible pairs only from players that pass the frozen tail-
   plausibility rule and are jointly feasible under the exact production
   constraints. For the shortlist, prove feasibility once with both players
   locked.
2. Estimate pair support using the other four world blocks, not `Rk`. A useful
   primitive is the lower quartile across blocks of the probability that both
   players exceed their own pre-lock high quantile in the same world.
3. Multiply by a bounded lineup-value term so two low-output players with high
   relative quantiles do not dominate.
4. Multiply by a capped novelty factor such as
   `1 / sqrt(1 + existing_pair_count)`. Do not use an unbounded inverse count.
5. Normalize weights within pair classes—QB/catcher, bring-back, same-game
   nonstack and cross-game—so one populous class cannot consume every solve.
6. Limit triples to the exact QB/catcher/bring-back core and require robust
   multi-block support.
7. After each accepted roster, decay covered weights deterministically.

The primary outcome-free evidence should be marginal weighted coverage over
the complete non-boom pool and held-out multi-block tail support. Realized
2026 C and S remain the promotion evidence.

## The 98% near-optimal rule

Keeping 98% frozen for the first MVP is defensible, but it should be described
as a search-width constant rather than a universal near-optimal definition.
It has two limitations:

- the allowed point regret scales with the world's optimum; and
- a multiplicative percentage is not invariant to adding the same constant to
  every player's score, even though every legal roster has nine players and
  the lineup ordering would be unchanged.

For the frozen MVP, report both percent and absolute regret, number of feasible
unique solutions at 98%, and refill frequency. Do not relax 98% after a world
fails to produce five lineups. A later prospective version could use a
score-free normalized regret based on the world's legal-solution spread, but
that should be a separately frozen mechanism, not a rescue of the first test.

## Recommended decision tree after the frozen score-free report

1. **Harvest mechanically first.** Do not interpret a partial run or change
   the current six conditions.
2. **Attach the simulator-law qualifier.** The result describes finite-K +
   ASOE Phase S worlds.
3. **Read quality and diversity conditions separately.** Preserve the official
   all-six disposition, but do not confuse a raw-diversity failure with a
   ranking-quality failure.
4. **If quality passes:** run the unchanged proxy on exact current-money worlds.
5. **If position-proxy quality fails:** inspect proxy slack. Test one frozen
   salary-Lagrangian bound before abandoning attainable ranking.
6. **If quality passes but diversity fails:** apply the fixed structural
   clusterer to both arms and compare quality at matched diversity.
7. **If both proxy versions fail under the money law:** close attainable-world
   ranking. Near-optimal interaction enumeration can still be tested on
   incumbent worlds because that is a separate part of ATLAS.
8. **If current-law quality survives:** implement the deterministic, matched-
   realized-budget 8-by-5 MVP on the CBWU-OI base and freeze P0/P1/P2 books
   before 2026 locks.

## Priority summary

| Priority | Recommendation | Why it matters |
|---|---|---|
| P0 | State and test the Phase S-to-money simulator-law transfer boundary | ATLAS ranks joint worlds; the current artifact law is not the money law |
| P0 | Match realized post-dedup candidate counts | Otherwise treatment can win by adding candidates rather than searching better |
| P0 | Use CBWU-OI identically in control and ATLAS arms | Removes known admission-order confounding and tests incremental value |
| P1 | Separate ranking-quality disposition from structural-diversity diagnosis | Part B exists to add diversity; raw top-40 diversity should not incorrectly kill Part A |
| P1 | Add a vectorized salary-Lagrangian proxy and proxy-slack report if needed | Provides a much tighter attainable upper bound without 10,000 MILPs |
| P1 | Canonicalize world and MILP ties | Identity-based diversity gates require deterministic identities, not merely deterministic scores |
| P1 | Measure novelty conditional on all non-boom candidates | Internal uniqueness is not marginal construction value |
| P1 | Bind the report to actual Cloud Run execution metadata | Self-declared image/code is weaker than an execution-owned receipt |
| P2 | Use leave-one-seed-out, class-normalized, capped pair weights | Covers tail-plausible interactions without exact-P leakage or generic Hamming diversity |
| P2 | Predeclare same-tolerance refill and report absolute regret | Preserves candidate parity without post-result relaxation |

## Final assessment

The central ATLAS thesis survives this review. The system loses far more in
candidate construction than selection, CBWU-OI shows that combination breadth
can move C at fixed budget, and the incumbent boom path really does compress
each selected world to one vertex. Attainable-world ranking plus diverse
near-optimal enumeration is a coherent response.

The biggest risk is not that ATLAS is too unconventional. It is that the first
test can answer a narrower question than the project believes: ranking quality
under a finite-K/ASOE world law, with raw rather than imposed diversity, and
with solve-attempt rather than realized-candidate parity. Tightening those
boundaries would make a positive result substantially more credible and a
negative result much more informative.

My recommended path is therefore to let the frozen diagnostic finish, preserve
its official result, and use it as the first cell—not the final verdict. A
current-money-law confirmation, matched realized candidate budget,
order-invariant admission, deterministic identities and conditional
interaction coverage would turn ATLAS from a promising search idea into a
clean prospective experiment.
