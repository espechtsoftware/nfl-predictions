# Remaining production-review ablations

**Date:** 2026-08-30
**Status:** implementation plan; outcome-blind audit complete; no experiment
launched and no result claimed
**Parent program:** `reports/2026-08-30-production-generation-shadow-program.md`

## Why this work remains separate

The five-arm generation-and-retrieval shadow implements the decision-bearing
incumbent-versus-boom-first test, the zero-solve retrieval crossing, cross-law
discovery, the unequal-resource boom dose, and ceiling-ordered all-boom. It
deliberately holds the incumbent construction preset and served source inputs
fixed so that those contrasts retain one interpretation.

The independent production review correctly identifies two additional
questions:

1. Does boom-first interact with the named construction preset?
2. What incremental lineup value is attributable to each paid-source consumer?

Neither question is answered by source publication, by the existing five-arm
shadow, or by Foundry v12's five-rule removal arm. They require separately
named experiments, namespaces, preregistrations, terminals, grades, and
multiplicity families. Their candidates must never be unioned into the core
primary populations after results are visible.

## A. Construction preset x candidate allocation

### Estimand

Run the complete four-cell crossing on the exact same 54-slate 2023--2025
panel:

| Construction preset | 160 leverage / 40 boom | 40 leverage / 160 boom |
|---|---:|---:|
| `classic-incumbent-gpp-v1` | required | required |
| `dk-classic-legality-only-v1` | required | required |

The primary diagnostic is the K80 difference-in-differences:

```text
(legality-only boom-first - legality-only incumbent)
- (incumbent-construction boom-first - incumbent-construction incumbent)
```

This determines whether the boom-first supply effect depends on house-style
construction rather than treating the historical construction and allocation
effects as additive.

### Frozen common law

- exact Foundry G0 54-slate panel;
- R0--R4, 10,000 generation worlds per block;
- 200 requested core solves per block;
- exact 160/40 and 40/160 allocations;
- role-12 and every auxiliary family unchanged in all cells;
- identical player, model, market, seed, retry, lock, and audit-bank inputs;
- incumbent coverage-194 retrieval and exact K80 only;
- all four cells generated on one immutable image;
- construction supplied as an exact named-preset receipt, never loose
  environment variables.

The existing incumbent and boom-first historical books may serve as
reproduction sentinels. They may not be mixed with newly generated
legality-only cells unless their complete effective input, code, exposure,
and selected-book identities reproduce exactly.

### Required reporting

- K20/K40/K80 realized weekly maximum;
- weeks at or above 194/200/210/220/230/240;
- candidate ceiling and selector regret;
- candidate and selected-book overlap;
- natural uniqueness, collisions, failures, retries, and runtime;
- per-rule incidence in each selected book;
- both construction effects, both allocation effects, and the
  difference-in-differences with slate-paired uncertainty.

This is a composite named-preset contrast. It must not be described as the
effect of only salary floor, QB stacking, bring-back, RB-vs-DST, and same-team
RB rules. Foundry's remove-five arm also leaves other preset differences,
including minimum games and overlap, and therefore is not this experiment.

### Implementation

Add a separate `corpus_r6_construction_allocation_cross_v1` release and a
construction-aware successor to
`boom_first_historical_replay_adapter_v1`. Preserve the existing adapter and
the prospective five-arm registry unchanged. Reuse per-slate/per-seed model
and world projections so the four cells repeat optimizer work, not four model
fits. Add a bounded runner, create-once pre-outcome terminal, independent
grader, season aggregate, and an outcome-free influence trace.

Historical results are descriptive because these outcomes have already been
observed. They may nominate a separately frozen 2026 shadow but cannot alter
the money policy automatically.

## B. Odds API incremental prop-override ablation

### Estimand

Do not implement one global `PAID_SOURCES=0/1` switch. For Odds API, estimate
the incremental value of the point-in-time player-prop override:

- **Odds on:** the current 45/55 blend uses eligible common-lock Odds API
  player props and otherwise follows the frozen DK-PPG fallback.
- **Odds off:** the same 45/55 blend never consumes Odds API player props and
  always follows the frozen DK-PPG fallback.

`BLEND_MODEL_WEIGHT=1.0` is not the control; it removes the complete market
blend and answers a broader question.

Generate an on and off population, then score-blind cross each population
under both selection-world states. Report the source supply effect, the
source-conditioned retrieval/calibration effect, their interaction, and the
operational on/on versus off/off effect.

### Outcome-free influence trace

- exact snapshot and common-lock identities;
- retained, excluded, missing, stale, and fallback row counts;
- changed player means, ranks, and world rows;
- candidate Jaccard and membership turnover;
- selected-book overlap and order turnover;
- solve failures, retries, and added latency.

Historical live-parity execution is a NO-GO unless an exact point-in-time
DK-PPG fallback authority exists for every tested slate. If it does not, retain
the older broad market/model result as prior evidence and run this incremental
override ablation prospectively in 2026. Game-line snapshots currently support
monitoring/UI rather than this scoring estimand and remain a different test.

## C. Fantasy Points x SIS matchup-source ablation

### Estimand

Fantasy Points Route and SIS ASOE are currently off in core generation, so a
global source switch would be vacuous there. Their immediate consumer is R6
matchup annotation, admission, and retrieval. On one exact frozen candidate
population, run:

| Fantasy Points | SIS | Interpretation |
|---|---|---|
| on | on | complete seven-pack mechanism |
| off | on | conditional Fantasy Points value |
| on | off | conditional SIS value |
| off | off | free-source fallback |

This is retrieval-only. Candidate IDs and world matrices must be byte-identical
in every cell, so candidate turnover is zero by construction. Recompute raw
annotations, component eligibility/support, percentiles, edge scores,
admission, and fixed coverage-194 K80 retrieval independently in each cell.
The exact selector bank is the incumbent retrieval engine's discovery bank:
R0--R3 in that order, 10,000 worlds per block (40,000 columns total); R4 is
held out and must not enter the selector.  Every per-slate matrix authority
must bind the exact candidate artifact and candidate order, the four
generation-pinned R0--R3 source artifacts, block order and worlds-per-block in
addition to the matrix bytes.  An opaque matrix identity or an R0-only/all-five
shortcut does not execute the frozen `coverage-194-v1` law.  Matrix construction
must also reproduce the production crossed scorer's numerical law exactly:
sum each nine-player roster with `dtype=float64` and persist the candidate by
40,000-world matrix as C-contiguous float64.  The float32 source-player draws
do not license float32 lineup accumulation or storage.

Remove each vendor's raw slices before component calculation and exercise the
real missing-source fallback. Never zero already-ranked values or drop columns
after full-on ranking. Components that jointly require Fantasy Points and SIS
become unavailable when either predecessor is absent. Report both conditional
effects and their interaction; never add the two vendor effects.

### Pre-freeze support gate

Run an outcome-blind four-cell census before any result freeze. For every
slate and cell record:

- raw and stable-identity source support;
- staleness and missing-observation status;
- available component count and joint-component loss;
- eligible candidate count before retrieval;
- whether exact K80 remains feasible.

The existing matchup runner fails below 80 eligible candidates. If any cell
lacks K80 support, redesign and freeze the fallback before outcomes. Never
weaken support after seeing scores.

Reuse the existing matchup source, component producer, candidate consumer,
retrieval runner, and R6 analysis/controller machinery. Add a distinct
ablation-derived source view and release; do not weaken the immutable full
seven-pack validator to accept missing packs.

Historical Fantasy Points/SIS source periods lack authoritative observation
timestamps and are labelled retrospective prior-period reconstructions.
Historical grades therefore remain descriptive mechanism evidence. True
source-value confirmation requires 2026 prelock manifests. The weekly process
also needs a bounded recurring SIS capture plan; current default behavior only
preflights the SIS session and makes zero SIS data queries.

## D. Broad-corpus admission tournament

### Corrected estimand and ownership

Production owns this experiment because the exact current R6 candidate corpus
and its source memberships are not available in the lab frame. The target is
**retention from one fixed corpus at one fixed admission budget**, not recovery
of the 17.361-point gap between the 205.793 hindsight-union oracle and the
188.432 top-250 oracle. The full-corpus number is a maximum over a larger,
multi-run union and rises partly through multiplicity. It is the denominator
and diagnostic ceiling, never a promise or a training target.

Use the exact immutable 54-slate combined R6 population already graded in the
score sprint. No arm may add a candidate, regenerate a world, change a source
population, or receive a different candidate count. Run both exact admission
budgets A250 and A500 and retain every loser.

### Three fixed admissions

1. **Modeled-tail reference.** Extend the existing strict
   230/220/210/200/mean lexicographic sieve from its exact A250 implementation
   to both A250 and A500 without changing the ordering law.
2. **Quota/disagreement union.** Reserve deterministic source-population and
   source-exclusive slots, multi-source consensus slots, and distinct
   source/detail disagreement slots. Fill unused quota only by the frozen
   modeled-tail reference order. The quota law must census availability and
   freeze its apportionment before any outcome label is opened; it may not use
   source historical success to size a quota.
3. **Direct admission ranker.** Fit one small, regularized and inspectable
   grouped ranker on prior seasons only. Inputs may include frozen modeled
   threshold counts/ranks, mean and dispersion, source membership and
   occurrence counts, law/source disagreement, and score-free construction
   descriptors. Training uses same-slate hard negatives. It may not use a
   held-out slate's outcome, winner membership, corpus-oracle membership, or
   post-lock feature.

The first production implementation should be a regularized linear pairwise
or listwise ranker rather than a new service or large model. Complexity earns
a follow-up only if this fixed-corpus test demonstrates admission lift.

The frozen quota allocation is 4% exclusive per source, then 4% inclusive per
source, 10% multi-source consensus, 10% greedy novel `(source, detail)`
coverage and modeled-tail fill. Each stratum records requested, eligible,
available after prior strata, delivered and shortfall counts. These percentages
are fixed from the admission budget and never from realized source success.

For endpoint 3, freeze an exact-total-budget blend before outcomes: take the
first A/2 reference candidates, then scan the challenger's frozen order until
A/2 candidates not already selected have been added. Both budgets are even,
so the result is exact A250 or A500; overlap merely makes the challenger scan
deeper and never expands the candidate count. Compare that blend's realized
maximum with the same-budget reference. Do not report the unconstrained union
of two A-sized admissions as a fixed-budget result.

### Time split, endpoints and interpretation

Use strict walk-forward outer seasons. The learned arm has no efficacy claim
on the 2023 cold start; 2024 may fit 2023 only, and 2025 may fit 2023--2024
with any threshold or hyperparameter choice made inside that past-only
boundary. The quota and modeled-tail arms run unchanged on all 54 slates.
Freeze the complete outcome-blind feature/admission inputs before fitting or
grading.

The v1 direct ranker gives every training slate the same aggregate sample
weight, assigns tied realized scores the same within-slate percentile, binds
an ordered ledger of score-free freeze and outcome identities, and includes
the normalized modeled-tail reference rank. This prevents larger candidate
corpora from silently receiving more training authority and makes input-order
replay exact.

The three primary endpoints, reported separately at A250 and A500, are:

1. mean and slate-paired distribution of the admitted realized maximum,
   together with retention relative to that same slate's fixed-corpus maximum;
2. retained 194/200/210/220/230/240 candidates and slate coverage; and
3. incremental union maximum when each challenger is added to the reference
   at the same total admission budget.

K80 selection is secondary and runs only after the admission read, on every
frozen admission using the same selector. Do not tune the selector to rescue
an admission arm. Report corpus size, source multiplicity and the full-corpus
oracle beside every result so a larger-union ceiling cannot be mistaken for
recoverable selection loss. Historical results are descriptive and can
nominate a 2026 shadow; they cannot automatically alter the Week-1 book.

### Minimal release boundary

Implement one pure scientific module plus one bounded adapter to the already
frozen combined-population artifacts, one boundary-slate smoke, and one full
read. Reuse the existing catalog outcome snapshot for grading after all
admissions are frozen. No new database, service, dashboard, corpus build, or
outcome query is needed. A validity defect gets one correction pass; optional
provenance refinements are non-blocking follow-up work.

## E. Upstream paid-source consumers

Production also owns the full-history plan's paid-source Experiment 5. The
lab has neither the point-in-time Fantasy Points/SIS/Odds columns nor the R6
consumer graph, so lab proxy fields are not evidence about vendor value.
After the retrieval-only FP x SIS factorial, test only one upstream consumer
at a time: Odds ladder/dispersion tail shape where immutable historical support
exists; Fantasy Points route/alignment/coverage role states; SIS receiver/QB
dependence; then a small frozen external-disagreement anchor dose. Every arm
must trace changes through marginals or states, candidates, admission and the
selected book. A null closes only that exact source-consumer pair.

The historical Odds prop-override arm is currently NO-GO because the required
point-in-time DraftKings-PPG fallback exists on 0/54 slates. That is a data-
support disposition, not a negative result for Odds tail ladders. Capture the
fallback and vendor snapshots prospectively rather than fabricating history.

## Sequencing and acceptance

1. Keep the core five-arm generation/retrieval release unchanged.
2. Implement the construction x allocation four-cell runner immediately; it
   is independent of the matchup seven-pack.
3. Implement the broad-corpus admission scientific core and run its one
   boundary-slate outcome-blind smoke while the construction crossing grades.
4. Implement the common source-influence trace and run the outcome-blind
   Fantasy Points/SIS four-state support census in parallel.
5. Execute the Fantasy Points/SIS retrieval ablation only after the real
   candidate-v2 root, seven-pack source root, component v3 publication, and
   canonical R6 source-release v3 exist.
6. Execute the historical Odds override test only if exact historical DK-PPG
   fallback authority passes; otherwise preregister the prospective test.
7. Start one upstream paid-source consumer only after its immutable support
   census passes; do not bundle vendors or consumers.
8. For each lane require create-once roots, exact input identities,
   independent reopening, no outcome read before terminal freeze, complete
   loser reporting, diagnostic-only decision status, and no automatic policy
   promotion.

Completion means all executable cells and influence traces exist, their
support gates pass, one real outcome-blind artifact smoke succeeds, and their
historical/prospective evidence limitations are explicit. Source availability
or immutable publication alone never counts as evidence of scoring value.
