# Foundry crossed-arm retest and simulated-scoring plan

**Date:** 2026-08-27
**Status:** adopted lead-architect plan, as accelerated by the independent
review disposition below; no production policy change is authorized by this
document.
**Primary objective:** determine, before the 2026 regular season, which ways
of filling a legal lineup corpus and selecting an 80-entry portfolio from it
most improve historical weekly maximum score and tournament-relevant tail
coverage.

## Executive conclusion

Most pre-Foundry generation and selector experiments were well-executed
paired tests, but they answered questions **conditional on the incumbent
construction domain**. That domain required a minimum $49,000 salary, at
least two same-team WR/TE partners with the quarterback, at least one opposing
RB/WR/TE bring-back, no RB against the selected opposing DST, and no two RBs
from the same team.

Those results are not invalid. They are narrower than some of their later
interpretations. In particular, they do not establish how a generation or
selection strategy performs when it is allowed to search the broader
DraftKings-legal lineup space.

The next research program should therefore use Foundry to run **crossed
experiments**, not another sequence of one-variable tests that silently hold
the old corpus fixed:

`belief law x world scheduler x fill strategy x construction profile x selector`

The expensive artifacts should be generated once and reused. Candidate
generation, provenance, simulated score matrices, and independent evaluation
banks should be immutable. Most selector and subcorpus comparisons can then
run as cheap array operations without rebuilding or redeploying the system.

Only DraftKings legality should be universally hard. Strategic ideas such as
QB stacking, bring-backs, salary usage, RB/DST avoidance, and same-team RB
avoidance should be exposed treatments, soft preferences, or explicit
portfolio sleeves until crossed evidence supports stronger treatment.

## Important correction to the current written record

The sentence in
[`2026-08-27-scoring-improvement-suggestions.md`](2026-08-27-scoring-improvement-suggestions.md)
that says “100% of candidates QB+2+bring-back” describes the **older incumbent
corpus**, not the current v12/R6 seven-profile union. The same sentence notes
that six of seven R6 lineups scoring at least 230 were exclusive to relaxed
arms, which proves the current union is not 100% incumbent-shaped.

This plan uses the following terminology consistently:

- **Legacy incumbent corpus:** normal `lev`, `boom`, `epi`, `qbvar`, `game`,
  and `dark` generation under all five incumbent strategic rules.
- **R6 seven-profile union:** incumbent plus five one-rule relaxations and an
  all-five relaxation, generated from the same scheduled worlds and belief
  law.
- **Rule-free:** not used. Even the all-five relaxation retains DraftKings
  position, salary-cap, team, and minimum-game legality, plus the chosen world
  schedule, solver, admission, deduplication, and selection laws.

## What the evidence already proves

### The legacy support restriction was material

The winner structure census found:

| Structure | 51 Milly winners | Legacy candidates | Legacy selected books |
|---|---:|---:|---:|
| Naked QB | 22% | 0% | 0% |
| One QB partner | 41% | 0% | 0% |
| No bring-back | 61% | 0% | 0% |
| Full QB+2 and bring-back shape | 16% | 100% | 100% |

See
[`2026-08-19-winner-structure-census-results.md`](2026-08-19-winner-structure-census-results.md).
An old selector could not select a naked-QB or no-bring-back lineup if no such
lineup existed in its input corpus. This is a support limitation, not evidence
of a selector implementation defect.

### The old results retain conditional meaning

| Prior result | What remains established | What is not established |
|---|---|---|
| All-boom population | Replacing `lev` with boom depth raised the incumbent-constrained corpus ceiling by 9.06 points at equal nominal budget. | All-boom is globally effective or ineffective in relaxed profiles or under a different selector. |
| All-boom selected book | The incumbent coverage selector converted little of that additional incumbent-domain ceiling: +1.34, statistically null. | A tail selector applied to a relaxed boom corpus would also be null. |
| A5 | The incumbent selector was within 0.134% of the optimum of its registered coverage objective. | Coverage-194 is the correct objective, or A5 is optimal on a different corpus. |
| A7 | The tested ladder was null on byte-identical incumbent candidates and worlds. | Tail ladders are null on the R6 union, profile-isolated corpora, or new belief laws. |
| B1 and older corpus-tail selectors | Their results describe the same small canonical incumbent pool. | Their ranking transfers to a larger relaxed candidate bank. |
| K1 no salary floor | That exact one-rule historical contract failed its preregistered safeguard. | Salary flexibility has no interaction with other rules or fill strategies. |
| A3 stack/bring-back carve | Relaxing both rules for 8 of 40 boom visits was nonvacuous and scored -0.98 under the then-current law and selector. | Full relaxation, a different dose, or relaxation after dependence repair is harmful. |
| Forecast-law proper scores | Calibration, marginal, variogram, or joint-tail findings measured independently of roster construction retain their stated scope. | Their downstream lineup-score effect is unchanged across feasible sets. |

The A3 result itself correctly says it is “closed at this dose” and calls for
a retest after repairing QB-to-WR dependence. It should not be promoted into a
universal construction rule.

### Current R6 establishes broader support, not a causal arm ranking

The current R6 population contains 199,244 distinct slate-lineup occurrences.
Six of the seven observed 230+ rows were exclusive to one relaxed profile:
three remove-bring-back, two remove-QB-stack, and one allow-RB-vs-DST. The
incumbent arm had only 30 exclusive rows and no exclusive 200+ row.

That validly proves that incumbent-only construction would have excluded most
of the observed R6 extreme tail. It does **not** prove that remove-bring-back
is the best policy. The profiles are nested feasible sets, can reproduce each
other's optima, use one common belief law, and generate unequal numbers of
distinct candidates despite equal nominal solve allocation. See
[`2026-08-27-r6-corpus-selection-deep-review.md`](2026-08-27-r6-corpus-selection-deep-review.md).

## Research questions

The program should answer five separate questions rather than collapse them
into one “best arm” label:

1. **Population availability:** which treatments create more distinct legal
   candidates capable of reaching useful tail levels?
2. **Belief quality:** which simulated laws assign realistic probability to
   player breakouts and correlated game environments?
3. **Search allocation:** which outcome-blind world scheduler spends solver
   work on worlds with the highest attainable legal lineup value?
4. **Retrieval conversion:** which exact-80 selector recovers the best
   available candidates without redundant modeled coverage?
5. **Interaction:** does a treatment work only when paired with a compatible
   construction profile, belief law, or selector?

## Experimental factor registry

Every run must carry immutable identifiers for all five factors below. A
result lacking any factor identity is not comparable evidence.

### Factor A — construction profile

Retain the current seven R6 profiles as the first reusable bank:

| ID | Salary floor | QB partners | Bring-back | RB vs DST | Same-team RB pair |
|---|---:|---:|---:|---|---|
| `F0-incumbent` | $49k | >=2 | >=1 | forbidden | forbidden |
| `F1-no-floor` | none | >=2 | >=1 | forbidden | forbidden |
| `F2-no-qb-min` | $49k | >=0 | >=1 | forbidden | forbidden |
| `F3-no-bringback` | $49k | >=2 | >=0 | forbidden | forbidden |
| `F4-allow-rb-dst` | $49k | >=2 | >=1 | allowed | forbidden |
| `F5-allow-two-rb` | $49k | >=2 | >=1 | forbidden | allowed |
| `F6-all-five-relaxed` | none | >=0 | >=0 | allowed | allowed |

Add one targeted profile in the next generated bank:

- `F7-qb-and-bringback-relaxed`: remove the QB and bring-back minima while
  retaining the salary floor and both RB rules. This isolates the interaction
  A3 bundled and the current seven-profile design does not isolate.

Do not add a broad arbitrary lattice merely because parameters are exposed.
Additional profiles need an explicit structural hypothesis or evidence of
missing support.

### Factor B — fill/generation strategy

The minimum useful registry is:

- legacy family mix;
- boom-heavy and all-boom allocation;
- `qbvar`-expanded allocation;
- role/epistemic allocation;
- per-world exact optimum used by current R6;
- distinct-next-best/no-good archive generation;
- quality-diversity archive generation over outcome-blind descriptors.

`dark` and `game` remain controls until a fair crossed result determines
whether their poor legacy tail rate arose from the family or from incumbent
constraints and the old selector.

### Factor C — belief law

- current served/incumbent player-world law;
- repaired game-state/QB-to-WR and opponent-response law, if it passes
  independent calibration and joint-tail gates;
- role-jump/breakout mixture, if it passes walk-forward exceedance
  calibration;
- other independently calibrated laws that provide genuinely different
  epistemic support rather than additional seeds from the same law.

Different random blocks from one law are Monte Carlo replicates, not different
belief laws.

### Factor D — world scheduler

- incumbent total-all-player-draw ranking;
- cheap positional/legal upper bound;
- bounded feasible-core heuristic;
- exact legal attainable lineup score on a small simulated benchmark.

The exact scheduler is a benchmark, not necessarily the production algorithm.
Candidate schedulers must first be screened outcome-blind on independent
simulation banks for recall of true top feasible worlds, distinct-optimum
yield, and compute cost.

### Factor E — selector

At minimum:

- coverage at 194 control;
- coverage at 200;
- 200/210/220 tail ladder;
- expected book maximum;
- block-robust/leximin coverage;
- strict 230 as a diagnostic control, not a whole-book recommendation;
- a joint robust selector spanning genuinely different belief laws when those
  laws exist.

Future selector candidates may include a slate-conditional target, explicit
overlap caps, or anti-correlated “evil twin” pairing. They should enter only
after the reusable independent-bank contract is operational.

## Fairness requirements

### Equal work, not merely equal nominal labels

For every paired population comparison, freeze and report:

- scheduled world count;
- attempted and successful MILP solves;
- solver time/deadline law;
- nominal candidate budget;
- distinct candidate count after deduplication;
- duplicate rate and no-good retries;
- common random-number identities;
- exact source and code identities.

Report both equal-solve performance and density per 1,000 distinct candidates.
Equal solve allocation is not equal marginal contribution when one profile
repeats far more optima.

### Isolated and union views

For every construction or fill arm, report:

1. arm-isolated corpus and exact-80 selection;
2. incremental union with the incumbent sentinel;
3. leave-one-arm-out loss from the complete union;
4. order-averaged or Shapley-style marginal union contribution;
5. occurrence multiplicity and cross-block stability.

Raw “exclusive ancestry” remains descriptive and must not determine budget
allocation by itself.

### Cross selectors with populations

Every retained selector must be run on every retained corpus from the same
comparison bank. The old pattern—change generation while freezing one selector,
then change selection while freezing a different corpus—cannot identify the
interaction that matters.

The primary crossed table should contain, for each slate:

`belief x scheduler x fill x profile x selector`

with identical candidate and simulated-bank identities wherever the factor
definition allows it.

## Endpoint hierarchy

### Outcome-blind development endpoints

These may be screened aggressively without consulting historical realized
scores:

- scheduler recall against simulated exact feasible optima;
- unique high-quality candidate yield;
- simulated threshold-event density;
- simulated expected maximum and tail coverage;
- robustness across independent evaluation-bank members;
- marginal calibration, joint-tail calibration, and dependence proper scores;
- runtime, memory, and solver-failure rates.

Design choices must be made on one simulation bank and reported on a separate
bank. An adaptive design cannot select and evaluate itself on the same draws.

### Historical development endpoints

Population and retrieval must be reported separately:

| Stage | Primary metrics |
|---|---|
| Population | mean weekly corpus maximum; availability and density at 187/194/200/210/220/230; winner-score gap; distinct yield |
| Retrieval | selected weekly maximum; regret to corpus oracle; conditional conversion; exact-oracle capture; threshold hits |
| Portfolio | player/game/arm/belief exposures; lineup overlap; modeled scenario redundancy |
| Contest, when fields exist | payout, top-1%, duplication-adjusted return, winner/top-10 gap |

For conditional conversion, include the exact uniform-random-book reference
for the slate's corpus size and opportunity count. Inference is paired at the
slate level; candidate rows within a slate are not independent observations.

The seven observed 230+ rows are a diagnostic case series. Powered decisions
must also use denser thresholds, weekly maximum/regret, season sensitivity,
and uncertainty intervals.

## Data separation and decision authority

- `CAL19`, `WF21`, and `HOLD22` are walk-forward calibration/development
  partitions for belief-law work.
- The 2023-2025 54-slate panel is a spent retrospective development panel.
  It can compare a small frozen set and diagnose interactions, but it cannot
  become fresh confirmation through another freeze.
- Broad searches belong on outcome-free simulated banks. Only a small frozen
  finalist set should consume historical development labels.
- A genuinely unseen prospective 2026 panel is the confirmation layer.
- No historical result automatically changes the served policy. Preserve an
  incumbent sentinel until a bounded challenger clears the declared evidence
  path.

## Efficient execution architecture

The Foundry should make the crossed design fast by separating expensive and
cheap work:

1. **Generate once:** freeze player catalogs, belief worlds, scheduler visits,
   candidate rosters, profile/fill provenance, and exact simulated score
   matrices.
2. **Materialize reusable subcorpora:** construct profile-isolated, fill-
   isolated, incremental-union, and leave-one-out candidate indices without
   re-solving lineups.
3. **Select repeatedly:** run selectors as pure deterministic consumers of an
   immutable candidate matrix and an independent simulated bank.
4. **Grade once:** attach a governed historical score vector only after all
   selections and comparison rules are frozen.
5. **Analyze without rescoring:** publish population/retrieval funnels,
   interaction tables, uncertainty, and attribution from immutable grade
   artifacts.

Neo4j and the web UI should project these authorities for exploration, not
become the evidence source. Each displayed result must link to the immutable
experiment, source, candidate-bank, selector, and grade identities.

## Required experiment record

Each experiment cell must persist:

- `experiment_id` and parent design identity;
- `belief_law_id`;
- `scheduler_id`;
- `fill_strategy_id`;
- `constraint_profile_id`;
- `selector_id`;
- source/catalog/world/candidate/bank/score identities;
- code and image identities;
- solve, candidate, distinct-count, and final-entry budgets;
- seed and common-random-number design;
- all population and retrieval metrics;
- uncertainty method and stopping law;
- outcome-viewed/outcome-blind classification;
- promotion eligibility, which defaults to false.

Lineup-level provenance must retain every producing arm rather than only the
first producer. A lineup repeated by multiple profiles carries information
about robustness and redundancy.

## Execution sequence from the current state

### Stage 0 — finish the outcome-blind authority chain

Current status:

- the 54-slate Gate-G0 combined panel is sealed;
- the full-union attribution release and deterministic no-rescore funnel are
  published and independently reopened;
- the real fixed-G0 player-catalog authority is still missing;
- catalog recovery, legal scheduler, source-v2 batch, and independent-bank
  code are locally prepared but not yet integrated into a terminal simulated
  comparison.

Finish and independently reopen:

1. outer fixed-G0 catalog recovery authority;
2. fixed-G0 candidate authority bound to that outer root;
3. seven immutable matchup/source packs across all 54 slates;
4. terminal source-v2 batch root;
5. independent selection and audit banks.

No realized outcome source is needed for this stage.

### Stage 1 — current-bank crossed baseline

Using the already-generated R6 candidates and independent simulated bank:

1. reconstruct all seven profile-isolated corpora and the complete union;
2. apply every retained selector to every corpus at exact 80 entries;
3. publish population size, unique yield, overlap, simulated tail support,
   expected maximum, and cross-bank stability;
4. add incremental-union and leave-one-out views;
5. publish the outcome-blind crossed baseline before opening any historical
   grade comparison.

This is the fastest way to learn whether old selector rankings were artifacts
of the incumbent corpus.

### Stage 2 — legal-aware scheduler treatment

Hold the current belief law, seven profiles, and solver budget fixed. Replace
only total-slate-draw scheduling with the best one or two outcome-blind legal-
aware schedulers. Generate and freeze candidate banks, then apply the full
selector matrix.

### Stage 3 — fill/profile interactions

Cross the finalist fill allocations with `F0`, `F2`, `F3`, `F6`, and the new
`F7` pair-relaxed profile. Retain other one-rule profiles as sentinels and
diagnostics. This stage answers whether all-boom, `qbvar`, role-state, or
quality-diverse filling behaves differently when structural support is open.

### Stage 4 — belief-law interactions

Only belief laws that pass independent walk-forward calibration enter this
stage. Reuse the scheduler/fill/profile/selector machinery and compare with
common random-number designs where mathematically valid. Do not describe five
seeds from one law as five epistemic models.

### Stage 5 — sparse historical development comparison

Freeze a small finalist set from Stages 1-4 and evaluate it on the spent
historical development panel. Report paired deltas, uncertainty, population
availability, retrieval conversion, and interactions. Do not promote a policy
from seven 230+ rows or from ancestry counts.

### Stage 6 — prospective 2026 confirmation

Freeze the leading portfolio and incumbent sentinel before each slate locks,
capture all inputs, and grade only after outcomes arrive. Week 1 is a testing
deadline, not a reason to preserve the old lineup law unchallenged until then.

## Decisions this plan makes now

1. Previous experiments are retained and relabeled with their exact feasible-
   set scope; they are not discarded.
2. Old nulls do not bury treatments whose mechanism interacts with corpus
   support.
3. The R6 union becomes the immediate reusable baseline.
4. Only DraftKings legality remains universally hard.
5. The incumbent strategic profile remains a sentinel, not the whole search
   space.
6. Population and selection are always evaluated separately and jointly.
7. A candidate strategy is judged at equal work and exact-80 portfolio size.
8. Graph/UI views are downstream observability, not scientific authority.
9. Broad experimentation occurs on independent simulated banks; historical
   reads are sparse and frozen.
10. Interaction effects are first-class results, not inconvenient residuals.

## Questions for the reviewing model

The independent reviewer should explicitly answer:

1. Is the distinction between internally valid conditional tests and broader
   strategy claims correct for every named prior result?
2. Does `F7` adequately isolate the QB-stack/bring-back interaction, or is a
   different minimal profile needed?
3. Which factor crossings are scientifically essential, and which can be
   screened out outcome-blind without risking a major interaction miss?
4. Are equal solver work, distinct-candidate density, isolated corpora,
   incremental unions, leave-one-out loss, and order-averaged contribution
   sufficient to compare nested feasible sets fairly?
5. Should any strategic construction rule remain universally hard based on
   evidence currently in the repository?
6. Are the independent design/evaluation-bank and historical-panel boundaries
   strong enough to prevent adaptive overfitting?
7. Which endpoint should be primary for the first crossed historical read:
   mean weekly maximum, regret, a dense threshold, or a composite?
8. Is there a faster design that preserves the ability to identify
   generation-by-profile-by-selector interactions?
9. What failure or null result would genuinely justify retiring an arm rather
   than merely changing its partner factor?
10. What part of this plan is unnecessarily cautious, and what part is not
    cautious enough?

The requested review should distinguish correctness findings from differences
of scientific judgment and should propose concrete replacement language or
experiment cells for every material objection.

## Lead disposition on the independent review

The review in
[`2026-08-27-crossed-arm-retest-plan-review.md`](2026-08-27-crossed-arm-retest-plan-review.md)
is accepted on its central sequencing point. The original Stage 0 through
Stage 6 ordering was too serial. The sealed current R6 bank can answer the
first profile-by-selector questions without waiting for the catalog recovery,
matchup packs, source-v2 batch, or a newly generated independent bank. Those
provenance items remain mandatory for the **next generated bank** and for any
claim that consumes them, but they no longer block current-bank analysis.

This section is the controlling implementation order when it differs from the
earlier stage order. It accelerates reusable, outcome-blind work; it does not
weaken artifact identity, point-in-time, historical-outcome, or prospective
activation boundaries.

### Findings adopted

1. **C1 is adopted.** Begin the current-bank crossed baseline directly from
   the sealed R6 full-union freeze, `panel-freeze.json` generation
   `1787756181440564`, and its five R0-R4 world blocks. Catalog and source-v2
   completion proceeds in parallel for the next generation.
2. **C2 is adopted with a bounded scope.** Pure, predeclared selector
   operations may be screened now with rotated-block fit/holdout. The tables
   must later be re-emitted on the independent common-random-number bank.
   Rotated holdout does not authorize an adaptive, open-ended selector search.
3. **C3 is adopted.** Every portfolio report will include effective
   independent tail shots at each registered threshold, alongside overlap,
   exposure, and tail-event dependence. Both an effective-rank measure and a
   participation-ratio measure will be recorded when well-defined.
4. **C4 is adopted.** Unequal-corpus retrieval comparisons will include the
   full-corpus result and equal-distinct-candidate comparisons from 32
   deterministic subsamples of the larger corpus. The seed derivation and
   sample count must be frozen before output is viewed.
5. **C5 is adopted.** A deterministic finalist function—metrics, thresholds,
   safeguards, ordering, and tie-breaks—must be committed before Stage 1
   outputs are published. Humans may reject a malformed experiment, but may
   not hand-pick finalists after seeing the table.
6. **J5, J6, and J7 are adopted.** The sparse historical primary endpoint is
   paired mean weekly maximum, guarded by non-inferiority in 200-plus hit
   weeks. The design is fractional rather than a full five-factor product:
   profile-by-selector first; law-by-profile and law-by-selector after law
   qualification; scheduler as a main-effect screen; and fill crossed only
   after outcome-blind screening. An arm is retired only after equal-work
   failure under at least two qualified laws plus approximately zero
   leave-one-arm-out union loss, with no more than two resurrection retests.

### Corrections and qualifications to the review

The following details are corrected before its schedule is implemented:

- The paired R6 comparison is tail ladder **178.435** versus coverage-194
  **176.882**, a paired gain of **1.553** mean weekly maximum. The roughly
  176.1 benchmark came from a different panel and cannot support the review's
  stated paired comparison.
- The sealed release presently freezes nested prefixes at `k={4,14,80}`.
  Prefixes 100 and 150 are desirable, but are not called "free" or reported
  until an exact deterministic continuation of the frozen selection order is
  proven and frozen. Entry-count curves measure scoring potential; they do not
  by themselves establish entry-fee-adjusted value or ROI.
- Historical/public player co-exceedance rates and breakout base rates are
  realized player outcomes. Calibration of shootout or role-jump laws is a
  separate walk-forward historical calibration activity, not outcome-blind
  work. No such outcome is read under the current no-outcome chain without
  its own frozen authority and access boundary.
- Score-free recourse construction and testing can begin immediately. A
  historical 3:55 p.m. policy grade consumes early-game realized outcomes and
  must run under a separate, preregistered historical evaluation boundary.
- `F8-game-cap-3`, `F9-single-partner`, and `F10-overstack-5` are accepted as
  hypotheses for the next candidate generation, not silently projected onto
  the existing bank. Their exact QB-partner and bring-back settings must be
  specified so the cells isolate one interpretable mechanism. `F10` waits for
  a qualified correlated-game belief law.
- `S1` and `S2` are shadow candidates, not deployment-ready jobs. The R6 bank
  is not evidence that the live `nostk` sleeve reproduces the same population.
  Each shadow needs an outcome-blind production-path smoke, immutable inputs,
  an activation clock, and an incumbent comparison before scheduling.

## Accelerated parallel execution schedule

The work now runs in five lanes. Lane A is the shortest path to new evidence;
the other lanes must not serialize it.

| Lane | Starts | Work | First durable output | What it blocks |
|---|---|---|---|---|
| A — current-bank crossed screen | immediately | frozen design; profile-isolated and union corpora; retained and bounded new selectors; rotated R0-R4 holdout; equal-size retrieval; effective tail shots | outcome-blind Stage 1 table and finalist-rule output | only the first simulated comparison |
| B — next-bank provenance | already active | fixed-G0 catalog recovery; outer candidate authority; seven immutable matchup packs; source-v2 root; immutable consumer smoke | reopenable root-last source authority | next generation and matchup-informed arms, not Lane A |
| C — belief laws | immediately in parallel | implement `L1-shootout-regime` and `L2-breakout-mixture`; freeze calibration statistics and folds before any historical read | score-free law implementations, then separately authorized walk-forward calibration | law-by-profile and law-by-selector generation |
| D — recourse | immediately in parallel | validate frozen recourse-aware initial-book primitives and package score-free policy variants | deterministic score-free recourse receipt | historical recourse grade and `S2` |
| E — prospective shadows | after each candidate passes its own gate | specify and smoke `S0` incumbent, `S1` relaxed union plus tail ladder, and `S2` recourse-aware variant | immutable shadow manifests with activation clocks | prospective use only |

### Lane A pre-output contract

Before any Stage 1 metric is inspected, commit one exact experiment contract
that includes:

1. the sealed freeze and generation identities;
2. the available current-bank profile cells; `U` and seven origin-membership
   `I` views are selected, while incremental, leave-one-out, exclusive, and
   order-averaged views remain population diagnostics in the first screen;
3. the retained selector registry plus exact definitions of any gamma cap,
   overlap cap, or anti-correlated pairing candidate;
4. `k={4,14,80}` as the immediate prefixes, with 100 and 150 disabled unless
   the exact-order extension gate passes;
5. one deterministic common-count broad sample, followed by 32 new
   common-count sensitivity samples for only three fixed controls and at most
   three deterministic nominees, using a candidate-rank seed shared across
   nested views;
6. rotated-block fit/holdout roles and a prohibition on changing a selector
   after seeing its held-out metric;
7. tail thresholds, effective-tail-shot estimators, overlap and stability
   diagnostics, and failure handling;
8. the deterministic finalist and tie-break function; and
9. explicit assertions that the run reads no raw realized outcome, performs
   no historical rescore, changes no production policy, and cannot promote a
   strategy.

The current bank contains only the profiles actually generated and frozen in
R6. New `F7`-`F10` profiles require a new candidate bank; they are not
synthetically inferred from the existing union.

### Ten-day implementation target

This is a target sequence, not permission to skip a failed gate or a promise
that external compute will finish on a particular wall-clock hour.

- **Day 0-1:** freeze Lane A's design and finalist rule; implement/reuse the
  current-bank projection and selector matrix; start score-free law and
  recourse work; continue catalog recovery independently.
- **Day 1-2:** finish the projection/selection/evaluation process-boundary
  smokes, benchmark representative selector cells, and begin the bounded
  17,280-fit broad profile-by-selector screen. Publish the broad table only if
  the measured runtime and immutable execution complete; do not turn the date
  into permission to skip a shard or inspect a partial ranking.
- **Day 0-3:** finish and independently reopen the catalog/candidate/source-v2
  chain for the next generated bank. This is concurrent with, not prior to,
  the first two bullets.
- **Day 2-4:** deterministically nominate at most three challengers and run no
  more than 51,840 confirmation-sensitivity fits; in parallel complete
  score-free `L1`/`L2` and recourse implementation, preregister their separate
  calibration/evaluation boundaries, and prove or reject exact 100/150 prefix
  continuation.
- **Day 3-6:** after terminal current-bank confirmation, re-emit the bounded
  nominee set on the independent bank;
  compare stability with rotated holdout; freeze next-bank `F7`-`F9` profiles
  and finalist fill allocation.
- **Day 5-8:** generate the qualified fractional-factor next bank, including
  matchup arms only if source-v2 is terminal and reopenable. Add `F10` only if
  the correlated-game law passes its preregistered calibration gates.
- **Day 7-10:** execute one sparse historical finalist comparison under a new
  frozen historical authority; prepare—but do not silently activate—the
  validated `S0`/`S1`/`S2` prospective shadows.

The operational target is to have shadow manifests frozen by 2026-09-04.
Missing evidence removes a challenger from that freeze; it does not weaken
the gate or delay the incumbent sentinel. Historical strategies remain
research results until their prospective activation clocks begin.
