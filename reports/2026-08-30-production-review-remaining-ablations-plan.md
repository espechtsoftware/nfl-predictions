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

## Sequencing and acceptance

1. Keep the core five-arm generation/retrieval release unchanged.
2. Implement the construction x allocation four-cell runner immediately; it
   is independent of the matchup seven-pack.
3. Implement the common source-influence trace and run the outcome-blind
   Fantasy Points/SIS four-state support census in parallel.
4. Execute the Fantasy Points/SIS retrieval ablation only after the real
   candidate-v2 root, seven-pack source root, component v3 publication, and
   canonical R6 source-release v3 exist.
5. Execute the historical Odds override test only if exact historical DK-PPG
   fallback authority passes; otherwise preregister the prospective test.
6. For each lane require create-once roots, exact input identities,
   independent reopening, no outcome read before terminal freeze, complete
   loser reporting, diagnostic-only decision status, and no automatic policy
   promotion.

Completion means all executable cells and influence traces exist, their
support gates pass, one real outcome-blind artifact smoke succeeds, and their
historical/prospective evidence limitations are explicit. Source availability
or immutable publication alone never counts as evidence of scoring value.
