# Lead architect decision on the 230+ extreme-tail program

**Date:** 2026-08-24
**Status:** outcome-blind architecture decision and post-G0 test direction;
no governed outcome read, v12 mutation, production-policy change, or R6-v2
registry change is authorized by this document
**Reviewed input:** `reports/2026-08-24-big-picture-review-response.md`

## Executive decision

The review is directionally correct: **230+ must become a first-class scoring
instrument.** It is much closer to the intended large-tournament regime than
the inherited 194 coverage line. Of the 68 known Millionaire Maker winners, 45
reached 230 and 28 reached 240. The accepted task-0 simulation also contained
896 lineup-world events above 230 and 370 above 240, so the regime is not
automatically too sparse to study.

The project will not, however, replace its objective with one unqualified
fixed threshold. `P(best exact-N book >= 230)` is an aggressive raw-score proxy,
not identical to win probability or expected payout. A 225 can win a lower-
scoring slate, a 240 can lose a higher-scoring slate, and duplication can make
the same score economically different. The long-run objective remains
contest-relative first-place equity and payout; 230 is the strongest usable
near-term proxy while full-field and duplication models are incomplete.

The adopted direction is a **small separately versioned T230 research
supplement**, followed by one equal-budget tail-oriented generation treatment.
The canonical seven-law R6-v2 registry remains unchanged. This avoids turning
one promising idea into another broad selector sweep, preserves the matchup
primary protocol, and lets all intended books be frozen before one controlled
outcome read.

## What the review got right

1. The book maximum, not average lineup score, is the relevant raw-score
   estimand.
2. Far-tail performance depends on coherent outcomes within lineups and low
   redundant tail-event overlap across the book.
3. Every evidence surface should report opportunity and conversion at 230 and
   neighboring thresholds.
4. The current top-total-world visit schedule may miss concentrated worlds
   with a high achievable lineup ceiling.
5. Tail-oriented generation and tail-oriented retrieval should be tested
   jointly while preserving separate causal contrasts.
6. Exact 4-, 14-, and 80-entry books require separate validation.
7. Neo4j and visual polish do not block the Week-1 scoring work.

## Corrections to the review

### 1. Realized-tail work is not outcome-blind

A simulated 230 census is outcome-blind. Fitting a GPD, comparing the simulator
with realized 225+ lineups, or studying realized 230 traits is outcome-aware.
Previously viewed outcomes may support clearly labeled Tier-E exploration, but
opening the governed v12/R6 score source before all intended final-fit books
are immutable demotes the later panel comparison to exploratory.

The proposed naive GPD is also unsupported. The current-family realized corpus
has only 54 candidates at 200+, 13 at 210+, and four at 220+ across 54 slates.
Lineups within a slate are dependent and generated under selection. Those rows
are not an IID extreme-value sample.

### 2. A tail mismatch would not identify the copula

More realized than simulated tail events could result from marginal player-tail
calibration, slate/player-universe mismatch, salary/source drift, scoring
mapping, candidate exposure, dependence, or ordinary finite-panel variation.
The project already has variogram, co-occurrence, Schaake, possession,
production-law-dependence, and SIS copula work; dependence is not wholly
unexamined. Diagnose marginals and source identity first, then clustered joint
exceedance on held-out seasons before building a new heavy-tail mixture.

### 3. Tail-biased discovery is not automatically importance sampling

Reranking or conditioning worlds toward high ceilings is valuable for candidate
discovery. It becomes probability-preserving importance sampling only when the
proposal law `q`, target law `p`, support, likelihood ratio `p/q`, effective
sample size, maximum weight, and variance are exact and validated.

Until that machinery exists:

- tail-enriched worlds may generate candidates;
- their raw frequencies may not be reported as target-law probabilities; and
- all claims must be evaluated on independent ordinary R worlds.

True weighted T-world evaluation is deferred behind synthetic estimator and
uniform-weight parity tests.

### 4. “Independent shots” is only an intuition

Near-disjoint rare events are not the same as statistically independent
lineups, and an effective rank of ordinary score correlation is not a literal
count of independent 230 shots. The system will report event-union opportunity,
sum-of-individual-event redundancy, pair intersections/Jaccard, duplicate event
vectors, and bounded event-matrix rank as descriptive diagnostics. It will not
market an unsupported “80× multiplier.”

### 5. Sparse events do not break greedy maximum coverage

Greedy maximum coverage retains its optimization approximation property. What
can fail with sparse training events is statistical transfer to held-out worlds.
Block support, training-to-heldout gap, resampling stability, and prospective
evidence address that problem. Scenario clustering is a later hypothesis, not
an automatic improvement.

### 6. A selector-only 230 sweep has no current promotion authority

Addendum 95 closed selector tuning on the current simulator and static feature
set. A coverage-230 law on the same substrate is useful Tier-E mechanism
research, but it is not a production reopening condition by itself. A
promotable revisit requires genuinely new PIT information or an adopted new
dependence model frozen before outcomes. The corrected matchup program may
eventually supply such information; current non-PIT matchup rows cannot.

## Exact outcome-blind metrics

Use `score >= threshold` for the T230 supplement because the operator's target
is “230 or more.” Preserve the existing strict/non-strict semantics of older
strategy IDs; do not silently alter them.

For slate `s`, fold `f`, threshold `t`, fold-eligible admitted universe `U`,
exact-N book `B`, and held-out ordinary worlds `W_f`:

```text
A_t(U) = mean_w 1[max(lineup in U) score(lineup,w) >= t]
H_t(B) = mean_w 1[max(lineup in B) score(lineup,w) >= t]
miss_t = A_t - H_t
conversion_t = H_t / A_t, when A_t > 0
conditional_regret_t = mean_w[(max_U score - max_B score)
                              * 1[max_U score >= t]]
```

`A_t` is the admitted-pool opportunity upper bound. It is not proof that an
80-entry book can cover every opportunity world. Where tractable, compare
greedy `H_t` with an exact or bounded-MIP maximum-coverage oracle and report the
gap.

The first census retains, for `t in {220, 230, 240, 250}`:

- candidate and lineup-world event count;
- opportunity-world count and `A_t` by block;
- source-arm, source-block, and visit support;
- candidates supported in 1/2/3/4/5 blocks;
- book `H_t`, `miss_t`, `conversion_t`, and conditional regret;
- worst-block hit rate, block range, and training-to-heldout gap;
- event-union divided by summed individual event rates;
- event intersection/Jaccard and duplicate event-vector groups;
- roster/topology concentration and book membership stability;
- runtime, peak memory, matrix dimensions, and exact admitted/selected counts.

Full 80×80 spectra/effective-rank calculations run only on nominated/final
books. Cheap event-union and summed-entry redundancy run on every book.

Slates—not lineups or worlds—are the inferential unit for historical transfer.
Report equal-weight per-slate vectors, season-stratified intervals, and
leave-one-slate/season influence. Five R folds are not 270 independent NFL
contests.

## Phase 0 — support census before selector effects

After Gate G0 and the required real-artifact one-slate smoke:

1. Reconstruct one accepted v12 slate without outcomes.
2. Compute the T230 census over each arm, the cross-arm fold-eligible union,
   and the all-block union.
3. Validate streaming memory/runtime and exact matrix hashes.
4. Scale to 54 slates only if the benchmark meets the frozen compute ceiling.

Before inspecting T230 selector comparisons, freeze a support branch. The
initial proposed law is:

- literal 230 coverage remains nomination-eligible for a slate/fold only when
  every training block has nonzero 230 opportunity and the four training
  blocks contain at least 100 total opportunity worlds;
- otherwise literal coverage-230 remains a diagnostic and the bounded ladder
  is the deterministic tail fallback.

The aggressive policy used in later generation tests is fixed now as a
**support-switched law**, not selected from observed selector performance:

- in a four-training-block fold, use literal coverage-230 only when every
  training block has nonzero opportunity and total opportunity is at least
  100 worlds; otherwise use the block-robust bounded 210..250 ladder;
- in an all-block final fit, use literal coverage-230 only when every block has
  nonzero opportunity and total opportunity is at least 125 worlds; otherwise
  use the same block-robust bounded ladder; and
- pure literal coverage-230 is nomination-eligible as a generally supported
  mechanism only if at least 80% of the 270 panel folds and at least 80% of the
  54 all-block fits pass their respective support gates. It remains diagnostic
  otherwise.

These thresholds and the 80% panel fraction are frozen before the census is
opened. They may not be selected after seeing which law wins.

## Phase 1 — separate T230 retrieval supplement

Do not edit or reorder R6-v2's seven canonical laws. Register a new
`extreme-tail-retrieval-suite/v1` over the fold-eligible/all-block full union
only. Do not mix in the currently non-PIT matchup admission.

The small new catalog is:

| ID | Law | Role |
|---|---|---|
| `coverage-ge-230-v1` | Greedy distinct-world coverage at `score >= 230` | Literal aggressive target |
| `bounded-tail-ladder-ge-210-250-v1` | Greedy finite ladder at 210/220/230/240/250 | Less brittle aggressive target |
| `block-robust-bounded-tail-ge-210-250-v1` | Leximin/worst-block version of the finite ladder | Robust fallback |
| `individual-ge-230-rank-v1` | Top individual training `p(score>=230)` without marginal set coverage | Mechanism ablation, not a negative control |

Use existing `coverage-194-v1`, `expected-max-v1`, and `mean-score-v1` as
comparators. Preserve mean score or a stable-hash book as the true negative
control.

The finite ladder uses a hard final cap. One simple preregisterable incremental
weight law is 1/2/4/8/16 at 210/220/230/240/250; a world above 250 therefore has
finite utility 31. Do not use an unbounded squared score transform. Final
weights must be frozen before selector effects are viewed.

Every law uses five candidate-identity-safe folds plus a distinct all-block
final fit, exact IDs, and marginal traces. The one-slate benchmark decides
whether all four new laws can run over the panel within budget. If not, retain
literal coverage, one bounded ladder, and the individual-tail ablation; do not
choose which law to drop based on its result.

This supplement is Tier-E on the current simulator. If complete before the
governed grade, freeze its intended final-fit books alongside R6-v2 so one
outcome access grades the whole predeclared catalog.

## Phase 2 — fastest legitimate new-generation treatment

Use the existing Atlas upper-bound world-ranking capability rather than
building true importance sampling first.

Run one compact 2×2. Freeze the complete factorial before inspecting Phase-1
selector effects; choosing a retrieval arm after those effects are visible
would reuse the same R evidence and bias the generation interaction.

| | Incumbent retrieval | Frozen support-switched aggressive law |
|---|---|---|
| `F0` current top-total schedule | control | retrieval-only |
| `F1` 50/50 current + Atlas high-ceiling-proxy schedule | fill-only | joint/intersection |

Rules:

- identical total visit and exact-solve budget;
- the aggressive retrieval column is the Phase-0 support-switched law above,
  never the best-performing Phase-1 selector chosen after inspection;
- account for screening CPU/memory in compute reporting;
- use a deterministic roster-slot/legal upper bound rather than exact-solving
  all 50,000 worlds merely to rank 200;
- use training/T worlds for generation only;
- cross-score every unique candidate on the unchanged ordinary R release;
- evaluate only on held-out ordinary R blocks;
- retain all candidate occurrences and F→admission→selection conversion; and
- change no dependence model in this family, so the world-schedule effect
  remains identifiable.

This is the fastest safe test of the review's main world-supply hypothesis.

## Phase 3 — dependence and true rare-event sampling

These are separate later workstreams, not a combined first arm.

For dependence:

1. exact-read PIT player/game outcome sources;
2. audit marginal quantiles and tail rates before joint dependence;
3. reuse existing variogram/co-occurrence/possession/SIS instruments at
   higher-tail definitions;
4. compare at most one preregistered alternative on held-out seasons;
5. require marginal preservation plus joint-tail and proper-score improvement;
   and
6. only then create a new world release and candidates.

For weighted rare-event sampling:

1. prove the estimator on synthetic targets;
2. prove exact parity when proposal equals target;
3. bind `p`, `q`, `p/q`, support, weights, ESS and variance;
4. add weighted objective, trace and independent-verifier schemas; and
5. smoke one slate before any panel use.

Until those gates pass, tail-biased worlds are stress/discovery worlds only.

## Phase 4 — grading and Week-1 use

Before governed historical outcomes are opened, freeze:

1. the incumbent book;
2. at most one aggressive T230 nominee; and
3. one materially distinct robust fallback/ablation.

The retrospective T230 primary is the paired per-slate indicator/count
`1[max(book) >= 230]`. Weekly-max delta, transitions at 220/240, conditional
conversion, season effects, and influence are required support because 230
counts will be underpowered. This is retrospective nomination, never fresh
confirmation.

Reconstruct and evaluate exact 4-, 14-, and 80-entry books separately. An
exact-80 result does not validate four Milly entries or fourteen qualifier
entries. Unless a valid reopening signal/dependence release and Tier-P gate
exist, the new T230 policy remains shadow/research only for Week 1. Prospective
2026 pre-lock books provide the real confirmation.

## Adopt now, defer now

### Adopt now

- 230 as a first-class but not exclusive objective;
- 220/230/240/250 opportunity, hit, miss, conversion and regret metrics;
- one outcome-blind v12 support census;
- one small versioned T230 retrieval supplement;
- tail-event redundancy rather than ordinary correlation alone;
- one Atlas upper-bound generation schedule treatment;
- independent ordinary-R evaluation; and
- exact 4/14/80 budget separation.

### Defer

- naive GPD on realized corpus candidates;
- claims that a copula defect is already identified;
- raw tail-world counts as probabilities;
- true importance sampling before weights/verifier support;
- a new t-copula/regime simulator before the instrument audit;
- scenario-ticket clustering before literal/robust coverage baselines;
- universal five-player narrative stacks;
- hard “every lineup clears 230 once” admission before a support census;
- learned field-max, duplication and payout objectives before full-field data;
  and
- Neo4j/React work as a blocker for the first T230 scores.

## Immediate next action

Do not alter the active v12 lanes or the first real-artifact R6-v2 smoke. Seal
Gate G0, then add the standalone T230 support-census contract to the accepted
one-slate analysis path. Its first output should answer one question before any
new selector is credited:

> On how many ordinary held-out worlds does the eligible v12 corpus make 230
> achievable, and how much of that opportunity can an exact-size book capture?
