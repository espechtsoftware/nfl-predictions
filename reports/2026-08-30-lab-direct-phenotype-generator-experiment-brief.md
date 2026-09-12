# Lab brief: direct phenotype and learned legal-lineup generation

**Date:** 2026-08-30  
**Requested owner:** lab for rapid exploratory discovery; production for
independent transport, confirmation, and integration  
**Status:** proposed new exploratory project; not a production-policy change  
**Requested timing:** first deterministic comparison within approximately 24
hours of acceptance; first complete walk-forward learned comparison within
approximately 2--3 days. These are aggressive operating targets, not a claim
that a positive result is likely.

## The request

Please test whether a generator that learns directly from historical
high-scoring-lineup phenotypes can produce a stronger pre-lock candidate pool
than the current pattern of drawing simulated worlds and retaining one
optimizer winner from each world.

This is intentionally a **generation** experiment first. It asks whether we
can construct legal lineups directly from pre-lock player and lineup
characteristics associated with Millionaire Maker winners and realized
200+/220+/230+ corpus lineups. It must not assume that quarterback stacking,
bring-backs, salary floors, game-count requirements, overlap limits, or other
house rules are universally correct. Those properties may be learned features
or separately named policies; only DraftKings Classic legality is universal.

The lab is the preferred initial owner because it can iterate quickly and
already separates candidate supply, retrieval, regret, and tail calibration.
Production will retain responsibility for reproducing any nominated method on
its exact frozen panel and integrating it into Foundry.

## Important evidence boundary

The lab's 2025 holdout has been spent and its prior historical program was
declared closed. This request therefore opens a **new exploratory project**;
it does not restore a holdout. All historical results from this work must be
described as development evidence, even when the arms are fixed before a run.
Fresh random banks test computational stability, not outcome generalization.

No historical result from this project may automatically alter production or
money policy. Confirmation belongs to an independently reproduced production
test and ultimately to the 2026 prospective season.

## Exact distinction from the current generator

For this brief, a direct or non-Monte-Carlo generator means:

- it does not draw player-score worlds to propose candidates;
- it does not retain the per-world MILP argmax as its proposal mechanism;
- it uses only information that would have existed before the tested slate's
  lock;
- it may use deterministic constrained search, beam search, integer
  optimization, top-M/no-good-cut enumeration, or another reproducible search
  procedure to produce DraftKings-legal lineups from a phenotype score;
- every generated roster and its ordered proposal score are reproducible from
  a frozen feature manifest, model/parameter artifact, and seed, if any.

Using untouched simulated worlds later to apply the same production selector
to every frozen pool is allowed and useful: that isolates the effect of
generation. It must be labeled **evaluation/retrieval**, never part of the
direct generator. A secondary completely deterministic phenotype selector may
also be tested, but only as a separately crossed retrieval arm.

## Scientific questions

1. At the same delivered unique-candidate count, does direct phenotype
   generation raise the realized candidate-pool ceiling relative to the
   incumbent per-world-optimum generator?
2. Does a learned walk-forward phenotype generator outperform a transparent,
   deterministic phenotype-score generator?
3. Can the fixed incumbent selector or cap-4 selector convert any additional
   supply into better K20/K40/K80/K100 books?
4. If supply improves but selection does not, does a separately trained
   phenotype retrieval score recover it without using same-slate outcomes?
5. Which pre-lock characteristics drive proposals, and do those
   characteristics transport across seasons rather than merely memorize
   winner archetypes?

## Required arms

Use the same DraftKings-legal universe, slate inputs, delivered candidate
count, and downstream evaluation for every primary arm.

| Arm | Candidate proposal mechanism | Status |
|---|---|---|
| G0 incumbent | Current per-world-optimum Monte Carlo generator | Required control |
| G1 transparent direct | Frozen deterministic phenotype score plus reproducible top-M/diverse legal search | Required first treatment |
| G2 learned direct | Walk-forward learned phenotype score/generator plus the same legal search budget | Required second treatment |

Do not union the treatment pools with the control before measuring each one.
A union or hybrid arm is permitted only after the three primary pools are
frozen and must be labeled exploratory.

### Retrieval crossing

Apply at least these same fixed selectors independently to every frozen pool:

- incumbent coverage-194 ordering;
- production `overlap-cap-4-exhaustive-prefix-then-fill` ordering.

Report nested K20/K40/K80/K100. If the lab's standard primary is K100, retain
it, but do not omit production K80 or pretend that a prefix is an independently
optimized smaller book.

A learned or deterministic phenotype selector is a useful secondary arm. It
must be trained walk-forward independently of the target slate and crossed
over **all** generator pools, so a generation effect is not confounded with a
new selector.

## Fair resource comparisons

The primary comparison is **equal delivered unique legal candidates**. Start
with 200 per slate to match the lab ceiling diagnostic. If an arm cannot
deliver 200 naturally, report the shortfall; never pad with duplicates or
silently relax its policy.

Also report:

- requested proposals and delivered unique candidates;
- duplicate, infeasible, collision, and rejected counts;
- CPU time, wall time, peak memory, and search/model-fit time separately;
- an equal-wall-time sensitivity;
- an optional 400-candidate dose after the 200-candidate comparison is sealed.

Do not call equal candidate counts equal compute. Present both estimands.

## Point-in-time and leakage rules

For every evaluated slate, all generator and selector fitting must be
walk-forward. The target slate's outcomes, actual ownership, contest lineups,
winning lineup, and post-lock role/injury information are forbidden until the
candidate pools and selected books are frozen.

Allowed feature families, when genuinely available before lock, include:

- salary, position, team, opponent, game, and slate structure;
- served projection, ceiling/boom probability, ownership forecast, and
  pre-lock market data;
- pre-lock injury, expected role, routes/coverage, Fantasy Points, SIS, and
  other matchup information with explicit observation-time authority;
- derived lineup properties such as salary used, aggregate ownership,
  concentration, correlation, stacks, bring-backs, game counts, team counts,
  boom counts, coverage ease, and player/pair phenotype scores.

Historical labels may include Milly winners and realized corpus lineups at
200+, 220+, and 230+, but only labels from training slates strictly prior to
the target fit boundary. Same-slate labels cannot influence features,
parameters, thresholds, proposal counts, diversity penalties, or search
termination.

Post-lock coverage grades, actual defender assignments learned after lock,
actual role/route shares, actual contest ownership, realized fantasy points,
and contest-field membership are outcome-side data. They are grading or
diagnostic inputs only unless an independently proven pre-lock snapshot
exists.

Freeze and publish an outcome-free influence trace before each realized read:

- training-slate IDs and maximum training timestamp;
- feature names, source identities, missingness, and observation-time rules;
- model class, hyperparameters, fit seed, and artifact hash;
- search algorithm, constraints, tie-breaks, proposal budget, and seed;
- exact candidate IDs and ordered selector IDs;
- confirmation that only DraftKings legality was universal;
- confirmation that target-slate outcomes were inaccessible.

## Suggested model structure

The lab may choose the implementation, but the first two versions should be
easy to audit.

### G1: transparent deterministic phenotype generator

Build a shrinkage-weighted score from pre-lock player and lineup
characteristics enriched among prior Milly winners and prior 200+/220+/230+
corpus lineups. Use deterministic legal search to emit the top candidates,
with a frozen diversity/no-good-cut schedule so the pool is not 200 minor
variants of one lineup.

Stacks, bring-backs, ownership, salary usage, boom classification, matchup
ease, and pair/correlation characteristics belong in the score as evidence,
not as mandatory laws. Publish every coefficient and contribution.

### G2: walk-forward learned phenotype generator

Fit a regularized, interpretable baseline first (for example, a calibrated
logistic/ranking or gradient-boosted model) that estimates a pre-lock lineup
tail/phenotype score. Severe class imbalance and slate identity must be
handled explicitly. Training/validation splitting must occur by slate and
time, never by random lineup rows.

The target should not be only `score >= 200`. Prefer a preregistered multitask
or ordinal target that retains information at 194/200/210/220/230/240 and does
not teach the model to improve the 200-point shoulder while sacrificing the
true tournament tail. Winner labels may receive a separate head but must not
dominate merely because the sample is tiny.

Hyperparameters must be selected inside the walk-forward training boundary.
Do not tune them on the full historical panel and then call the resulting
target-slate predictions out of sample.

## Evaluation and required report

For every generator × selector cell, report:

- mean and median realized weekly maximum at K20/K40/K80/K100;
- slate counts at or above 194/200/210/220/230/240;
- candidate-pool oracle and threshold supply at the same lines;
- selector regret and ceiling-conversion count;
- per-season results and paired slate deltas;
- slate-bootstrap interval and W/L/T counts versus G0;
- candidate and selected-book Jaccard/overlap;
- unique players, pair coverage, effective independent shots, maximum overlap,
  ownership, salary, game/team concentration, and phenotype distributions;
- known-winner and high-scorer characteristic recovery as descriptive
  diagnostics, not training-validity proof;
- runtime and natural failure/collision/duplicate receipts.

Publish a stagewise reachability funnel:

```text
generated legal pool
  -> any admission/frontier filter
  -> selector-eligible pool
  -> K20 / K40 / K80 / K100 book
  -> realized oracle / selected maximum / regret
```

If a wider legal-universe oracle is available, show it separately. Never
describe an outcome-aware hindsight oracle as attainable pre-lock performance.

The primary read is the paired difference in mean K80 weekly maximum and the
paired difference in the equal-200-candidate pool oracle. A method may be
nominated for production replication only if:

- its input and outcome-blind freeze pass completely;
- its pool-ceiling and selected-book effects are reported separately;
- gains are not produced solely by one season or one Monte Carlo bank;
- 220/230/240 supply and selected hits are not concealed by a higher mean;
- all attempted arms, variants, and deviations are disclosed.

Because no lab holdout remains, a positive interval is nomination evidence,
not confirmation or adoption authority.

## Deliverables to production

Please return:

1. A short preregistration naming arms, counts, features, selectors, metrics,
   and stopping rules before the realized read.
2. Exact code commit and environment/dependency manifest.
3. Feature dictionary and point-in-time source manifest.
4. Frozen training partitions and model/parameter artifact identities.
5. Per-slate ordered candidate pools for G0/G1/G2 with proposal receipts.
6. Per-selector ordered books and the outcome-free freeze receipt.
7. Complete realized grade and paired comparison report.
8. Machine-readable per-slate metrics and a concise disclosure of every look,
   failed arm, deviation, and reused outcome.
9. A production handoff explaining the smallest reusable generator API,
   required inputs, runtime, and known limitations.

Production should be able to reproduce candidate IDs without copying a lab
result file or reading realized outcomes.

## Ownership and handoff

### Lab owns

- rapid G1 and G2 prototyping;
- the exploratory historical screen and complete disclosure ledger;
- candidate/model/feature artifacts needed for reproduction;
- explaining why the direct proposal mechanism differs from per-world argmax.

### Production owns

- independent code and artifact review;
- reproduction on the exact production 54-slate panel;
- crossing the nominated generator with production admission and retrieval;
- point-in-time source enforcement and live-input availability;
- Foundry preset/API/UI integration;
- prospective 2026 confirmation and every production or money decision.

The lab should not pause or modify the production construction × allocation
crossing. That execution is already active and answers a separate question.
The two teams can work concurrently and exchange only frozen, explicitly
identified artifacts.

## Immediate requested response from the lab

Please confirm:

1. whether the lab accepts this as a new exploratory project despite its
   previously closed historical program;
2. which historical panel and pre-lock feature snapshots it can support
   without reconstruction leakage;
3. whether it can produce G1 within roughly 24 hours and G2 within roughly
   2--3 days;
4. any feature or search limitation that would prevent an equal-200-candidate
   comparison;
5. the exact preregistration path and commit before opening realized results.

