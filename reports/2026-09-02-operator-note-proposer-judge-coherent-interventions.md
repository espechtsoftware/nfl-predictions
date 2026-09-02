# Operator-side note: five more ways to widen the joint tail on both sides of the pipeline at once

**Date:** 2026-09-02
**Author:** operator-side assistant (outside review; neither a production nor a lab document; no queue
authority)
**Audience:** operator, lab experiment team, production implementation team
**Parent:** extends §2.4 ("the audio-exact version") of
`reports/2026-09-02-operator-note-midside-extremes-and-score-ideas.md`, and accepts the production-lead
routing recorded inline there (088 is the immediate lab execution; the ECC-versus-tilting dependence repair
is LAB NEXT; ECC and tilting stay distinct interventions; no co-boom target may be tuned on the evaluation
fold). Nothing here adds an arm to frozen 088 or proposes any outcome spend before its read.

**The operator's question this answers:** the preferred idea from the parent note keeps each player's
individual score distribution as it is but widens how the extremes move together — valuable because it
changes *what gets generated and how it is judged simultaneously*. What other interventions have that same
dual-action property?

---

## Production-lead review: lab work selected from this note

**Overall verdict:** the lab should work on this intervention class, but not as five simultaneous efficacy
arms. The note contains two high-value near-term tests, two contingent successors, and one enabling substrate.
The fastest honest program is a staged ladder that keeps one score-bearing read at a time while implementation
and outcome-disabled mechanics proceed in parallel.

The lab has already acted on the parent review at commit `5806bbf`: it drafted PREREG-058 / experiment 089
for ECC versus minimum-KL and added the point-in-time participation contract to PREREG-054 / experiment 085.
Those are useful starts. For speed, the first efficacy question should stay simple: **does one coherent,
equal-budget proposer-plus-judge treatment beat the incumbent end to end?** Run control versus the combined
repair, with the normal mechanics and leakage checks, and stop if it is flat or harmful. Only after a promising
screen should the lab spend on separating proposer-only from judge-only effects. That later decomposition is
for understanding and safe composition; it is not a prerequisite to trying the idea. One interpretation
boundary remains: **ECC versus minimum-KL is not a proposer/judge decomposition** because they are different
transformations.

### What the lab should work on

| Rank | Candidate | Lab disposition | Timing |
|---|---|---|---|
| 1 | Frozen 088 | Execute/read unchanged. | Immediate; no new arms. |
| 2 | **2.2 measured additive regime overlay** | Port the already-working mechanism to the current D800/K80/DEMAX stack and freeze one low-dose coherent treatment-versus-control screen. Investigate components only if it is promising. | Build/mechanics now; first available score slot after 088 unless 089 is already execution-ready. |
| 3 | **089 ECC and minimum-KL** | Finish the already-drafted instrument and mechanics work. Keep the two estimands separate; add a declared same-transformation decomposition only for a finalist, not by treating ECC and KL as the two sides of one factorial. | Build in parallel; score after 088/current-stack readiness ordering. |
| 4 | **085 participation mixture** | Run the frozen same-supply judge-only experiment. Prepare—but do not conflate with 085—a successor in which role-state worlds also drive generation and coherent opportunity transfer. | Existing parallel lane; successor conditional on engagement/result. |
| 5 | **2.3 joint-event sleeve plus tilt** | Implement support/mechanics now, but score only if the minimum-KL judge in 089 engages. Start with one combined equal-budget screen; decompose only if promising. | Contingent. |
| 6 | **2.1 elite-world allocation** | Treat as a proposal-efficiency experiment, not a law repair. Build only the synthetic/reproduction and ESS mechanics now; no historical efficacy spend until a repaired law passes. | Conditional/lower priority. |
| 7 | **2.5 calibration and tracking substrate** | Build the walk-forward measurement harness and point-in-time feature audit now. It may fit on prior outcomes, so it is not “outcome-free”; target-fold evaluation remains sealed. | Background enabling work. |

### Do not create new work from

- another middle-candidate pruning arm;
- a replacement-form copula, Schaake replacement, CE-style self-elite refit, or a generic diversity arm;
- multiple hand-picked regime-overlay doses on the same score panel;
- same-season tracking or coverage traits that were not available before that slate's lock;
- arithmetic stacking of historical gains. Only a final crossed book can establish compatibility.

The lab should therefore attempt **2.2, 2.4/085, and 089**, prepare **2.3** conditionally, and restrict
**2.1/2.5** to enabling work until their gates are earned. This covers every credible mechanism in the note
without spending the remaining pre-season window on variants that cannot answer a distinct question.

### Conceptual correction before implementation

Not every item below literally widens dependence on both sides:

- Base ECC with the simulator's own rank ordering **preserves the incumbent copula** while changing marginal
  calibration. Only its optional pair-recoupling step changes rank dependence. If those are combined, the lab
  must at least report marginal-only versus marginal-plus-recoupling mechanics; otherwise a co-exceedance gain
  at an absolute threshold may be entirely a marginal-level effect.
- Correctly weighted elite-world sampling preserves the incumbent probability measure. It reallocates proposal
  compute and may lower estimator variance; it does not repair the law merely because the same samples are used
  by a judge.
- Minimum-KL tilting changes the judge's effective distribution but not proposal unless generation is also
  driven from the tilted/conditioned measure.
- The additive regime overlay and a fully specified role-state model are the clearest true shared-substrate
  interventions in this note.

This does not disqualify ECC, tilting, or elite sampling. It determines the claims their experiments are
allowed to make and prevents a successful combined score from being given the wrong mechanism label.

---

## 1. Why this intervention class, restated with the newest receipts

The simulation worlds are the pipeline's shared substrate: the generator solves per-world optima on them,
and the selector judges candidates by their distribution across them. An intervention at the world level
therefore moves proposal and judgment coherently; an intervention anywhere downstream moves only one side of
a miscalibrated instrument. Three recent, mutually consistent receipts say the downstream side is inert:

- **087 sealed FLAT** (production review in the parent note): WEMAX − DEMAX proxy `+0.00022
  [-0.00307, +0.00507]`, 25 ties, `p=.91`, despite **34% book turnover**. A different utility over the same
  worlds reshuffled the book and bought nothing.
- **PREREG-052** (scheduler confirmation): the treatment *provably ordered worlds better by its own bound*
  (visit-value corr 0.378 vs 0.251) and reshaped books hard (book-J 0.130, 11.6 new players) — raw −0.354,
  proxy +0.001. Better search over the same law bought nothing.
- **More precision on the same law is negative**: 30k worlds scored −0.61; 32 residual columns were null
  after a +0.83 same-law screen (lab synthesis §0).

Meanwhile the one thing the law provably gets wrong is joint: realized QB+WR1 ≥70 co-exceedance ~.020–.026
vs the incumbent's .011–.014 (≥50/≥60 realized .125/.047 vs far less; both-top-3 ≥60 realized .176), and
realized cross-team correlation .065–.125 vs ~.056–.068 (exp 003/003-recal). All five ideas below are ways
to spend that one measured fact on both sides of the pipeline at once. ECC marginal repair (untried-ideas
1.1) and min-KL world tilting (1.2) are the two already routed; these are their siblings, each with the
changed dimension that keeps it outside an existing closure.

## 2. The five candidates

### 2.1 Erase the middle *worlds*, not the middle lineups — elite-world reallocation with importance weights

**What.** Adaptive multilevel splitting / subset simulation on the latent game state, with the level
function = *that world's best legal lineup value* (cheap bound first, exact MILP above a threshold), so
surviving worlds are, by construction, worlds whose optima clear the line. Keep importance weights so judged
probabilities remain calibrated.

**Why dual-action.** The sample concentrates on the joint tail — generation gets tail-consistent solve
targets — while the weights preserve the measure — judging stays honest. This is the operator's original
"erase the middle" instinct applied one level up: the middle is removed from the *sample*, not from the
*probability measure*. Pruning mid-scoring candidates was falsified (033/035) precisely because the measure
never changed; here it is the sampling that changes and the measure that is preserved.

**Nearest closures / changed dimension.** 117 closed raw *candidate*-budget scaling; 026 showed selection-
bank world-count precision is not binding; both added unconditioned volume. This conditions *which worlds
exist for generation*, a different dimension (world allocation), with an explicitly weighted estimator.
Already specced as proposal §4.2 / plan B-12 / untried-ideas Tier 2.7, incl. its moderate-threshold
reproduction gate; v0.14's density-known latents make it implementable now.

**First gate (outcome-blind).** Reproduction of known conditional frequencies at moderate thresholds;
effective-sample-size floor on the weights; U3 search-amplification curve attached to any generated sleeve.

**Honest risk.** Elite-according-to-a-miscalibrated-law amplifies law error (the CE failure mode). Run only
after a marginal-level repair passes the instruments, and judge under untouched banks and both laws.

> **Production review — CONDITIONAL LAB WORK, not a current law-repair arm.** With correct importance
> weights, the judge estimates the incumbent measure more efficiently; it does not change the target law.
> The intervention primarily changes proposal allocation. Moreover, candidates chosen from the same weighted
> worlds on which they are judged can overfit a few enormous weights. Require an independent untouched judge
> bank, an ESS floor, a maximum normalized-weight cap, repeated moderate-threshold recovery, fixed exact solve
> and delivered-unique budgets, and comparison against ordinary stratified/antithetic sampling. Proceed to a
> score read only after a repaired law has passed and only if elite sampling improves proposal recall per solve.

### 2.2 Regime-amplified dependence with a *measured* dose — finish the 004d overlay

**What.** State-dependent widening: correlations that rise in extreme regimes rather than uniformly. The lab
already measured the primitive — the **additive regime overlay** at low dose (λ_hi 0.7, λ_team 0.5) scored
**+1.86 ± 0.26 across four seeds** (all four positive on mean and ≥200; ≥200 weeks 12.0→14.8, ≥210 4.0→6.5),
with the high dose (+0.53 ± 0.52; ≥210 4.2→7.2) as a deep-tail specialist (experiments 004d, 2026-08-28).
What was never done: (a) set λ/dose by *measurement* — walk-forward, to reproduce the realized co-exceedance
ladder at several thresholds — instead of by hand; (b) read it under the current proxy objective and modern
D800/K80 stack; (c) later, condition the regime weights on pre-lock signals (market totals, alternate-ladder
tail shape, weather) so the widening is slate-specific.

**Why dual-action.** The overlay changes the worlds themselves; per-world boom solves then propose
regime-consistent rosters and the selector prices them under the same widened joint — one substrate, both
stages.

**Nearest closures / changed dimension.** Replacement-form analog copula lost (−1.9) and the composed
replacement (012) was null/negative — this stays additive, keeping z0, the only form that has won (010 vs
010a). The hierarchical game/team/player Gumbel arm (closed, 23 vs 27 on the production panel) relocated
shock variance at *equal* magnitude, uncalibrated to any realized target; this *adds* tail-state dependence
calibrated to realized co-exceedance. Learned conditional templates (Addendum 115) imposed template ranks
and failed the joint-tail gate; this touches no rank template.

**First gate (outcome-blind).** The frozen Schaake instruments: realized variogram score, co-exceedance
Brier at the 003-recal targets, lineup-tail reliability — must beat the incumbent *and* the recorded 004d
hand-dose before one equal-budget screen.

> **Production review — YES, HIGHEST-PRIORITY NEW LAB SCREEN.** This is cheap, implemented, and supported by
> the strongest prior signal in this note, but that signal came from the older lab pipeline and partially
> reused development outcomes. It also weakened at deeper boom supply in the limited 004b160 evidence, so
> transport to boom-first D800 is the actual question. Freeze **one** dose before the new read; the low dose
> (`lambda_hi=0.7`, `lambda_team=0.5`) has the cleanest four-seed mean/200+ precedent and avoids another
> dose search. Compare coherent R/R with C/C on the current D800/K80/DEMAX stack at exact equal solve and
> delivered-candidate budgets. If it is promising, then run the smallest useful mechanism follow-up before
> claiming which side caused the gain.
> Variogram, Brier, and reliability use realized data and are walk-forward score gates—not outcome-blind
> gates. Verify that the additive transform preserves intended marginal means/quantiles and uses pre-lock
> role identities when defining QB/WR pair families.

### 2.3 Joint-event-conditioned solve sleeves, with the judge tilted to the same event rates

**What.** Take the measured deficit events themselves — QB+WR1 ≥70, both-top-3 ≥60 by total band, cross-game
double spikes — and use one external target set on *both* sides: a fixed sleeve of solves runs only in
worlds where the event occurs (cheap first pass: subset the existing 10k-world banks, no resimulation),
while min-KL tilting (1.2) sets the judge's event frequencies to the same walk-forward realized rates.

**Why dual-action.** The symmetry is the mechanism. Conditioning the generator without correcting the judge
is error mining; correcting the judge without feeding the generator leaves the new mass unproposed. Pairing
them from one external target set makes the two stages coherent by construction — this is the generation
half that 1.2 currently lacks.

**Nearest closures / changed dimension.** Anchors (055) locked a *single player* in the world where his own
draw peaked — marginal conditioning, closed as implemented; this conditions on *joint events*, the exact
thing the law under-produces. CE refit an adaptive elite distribution against the sim's own scores; these
targets are fixed, external, realized, and prior-fold only.

**First gate (outcome-blind).** Event-frequency reproduction receipts; ESS floor and ≥15% book-turnover gate
inherited from 1.2 (if books barely change, stop without a read — the PREREG-014 lesson); U3 curve on the
sleeve; exact count-matching against the displaced boom solves.

> **Production review — LAB CONTINGENT ON 089 E2.** If the minimum-KL treatment engages, first try this as one
> coherent combined sleeve-plus-judge arm against control at fixed budget. That directly answers whether the
> package helps and is faster than a full factorial. Only a promising result earns a follow-up separating
> generation from judgment. Use independent generation and judge banks, freeze the event taxonomy and role
> assignment from pre-lock information, expose per-event support, and hold total solves/admission capacity
> constant. A subset of existing worlds is a mechanics shortcut, not independent evidence.

### 2.4 Role/participation-state worlds — score it as a dependence repair, not just an availability fix

**What.** A discrete latent state (starter inactive → backup inherits share; game flips run-heavy) flips
several players *coherently*: the backup's boom, the stars' funneled targets, and the freed salary are one
joint event, not three marginals. A walk-forward `P(active)`/role mixture in the worlds makes generation
propose state-consistent rosters (cheap-replacement + stars combinations the incumbent never proposes) and
makes judging price them.

**Status.** Already queued (exp 073 redesign awaiting the latent-role port) and the participation lane is
already LAB IN PARALLEL in production's routing, with its rules fixed (later-inactive labels are outcomes;
`was_active` is a prior-fold target, never a same-slate feature). The only addition here is evaluative:
report its effect on the co-exceedance/variogram instruments alongside book endpoints, because its real
identity is joint-structure repair from a genuinely new information dimension — the strongest legal reopening
class the rules recognize.

> **Production review — YES, BUT THIS IS NOT THE CURRENT 085 ESTIMAND.** PREREG-054/085 deliberately keeps
> generated supply identical and applies `P(active)` only while judging/selecting. Run that clean judge-only
> comparison first. A true role-state-world successor must additionally model opportunity transfer—backup
> share, teammate funneling, play-volume or pass/run response—and feed those worlds to both generation and
> judgment. Binary zeroing alone is not coherent role redistribution. If 085 engages, reduces contamination,
> or reveals candidate-rescue potential, the lab should first run one coherent role-generation-plus-judgment
> treatment against control at an equal generation budget. Decompose it only if promising. Production owns
> the timestamped live input contract; later inactive status remains reader-only.

### 2.5 Substrate: measured width knobs, and structural co-boom priors from tracking data

Two supports that make 2.1–2.4 statistically honest rather than new outcome spends:

- **Walk-forward dependence-knob calibration.** hsim v0.9→v0.13 hand-tuned ~4 joint-dependence knobs against
  gate-4 lineup-tail reliability; make that a bounded walk-forward optimization (≤5 knobs, prior seasons
  only, loss = lineup-tail reliability + variogram + co-exceedance Brier) for both laws. Set the width by
  meter, not by ear. Instrument-only work; no outcome opened.
- **Structural priors for the targets.** Every idea above calibrates to realized co-exceedance rates
  estimated from ~89 slates of rare events (the .02-level targets are noisy). Regularize them with
  structure: route-tree overlap, air-yards concentration, funnel-defense and coverage-role traits from the
  already-shipped tracking table (1,384 players, 96.3% high-confidence gsis crosswalk) plus free in-season
  NGS aggregates. Shrink pair-level targets toward these structural predictions; fit shrinkage on prior
  folds. This is a legitimate new-information add and it de-noises the whole family.

> **Production review — LAB ENABLING WORK NOW, with corrected evidence labels.** Calibration on prior-season
> realized outcomes is model fitting, not “instrument-only” or “no outcome.” Use nested walk-forward folds:
> inner prior folds choose at most five knobs or shrinkage strength; the next season evaluates once. Preserve
> an untouched incumbent and report parameter stability because rare `.02` events can produce unstable
> optima. Tracking, coverage, funnel, and NGS features are admissible only at their actual historical
> publication time; season-final tables must be lagged to the following season unless an in-season snapshot
> proves availability. Treat incomplete crosswalks and missing seasons as explicit states. This substrate can
> be built immediately, but it should not block 088, 085, or the first current-stack overlay screen.

## 3. Summary table

| Idea | Acts on | Nearest closure | Changed dimension | First gate before efficacy | Cost |
|---|---|---|---|---|---|
| 2.1 Elite-world reallocation | world sampling (weighted) | 117 candidate scaling; 026 world count | conditional world allocation w/ importance weights | freq reproduction, ESS, U3 | medium (needs v0.14 latents) |
| 2.2 Regime overlay, measured dose | dependence in tail states | analog-copula replacement; hier. Gumbel; Add.115 templates | additive + calibrated to realized ladder | variogram / co-exc. Brier / tail reliability | low (mechanism exists, 004d) |
| 2.3 Event-conditioned sleeves + tilt | generation targets + judge weights | anchors (055); CE | joint events, external fixed targets, paired judge | event receipts, ESS, turnover ≥15%, U3 | low (subset existing banks) |
| 2.4 Role-state worlds | joint structure from new info | — (queued 073/participation lane) | availability/role latent state | P(active) calibration; instruments co-reported | in queue already |
| 2.5 Knobs + tracking priors | calibration substrate | — | measurement infra, no outcome | n/a (instrument-only) | low |

## 4. Sequencing and discipline (one ladder, not five arms)

1. **Nothing before the 088 read.** Frozen; no added arms.
2. These enter as members of the *same* preregistered dependence-repair ladder production routed as LAB NEXT
   — one intervention per read, instruments first, targets fit on prior seasons only, evaluation on
   untouched banks under both laws, ECC and tilting kept distinct per the routing boundary. Suggested order
   inside the ladder: 2.2 (cheapest, has a measured four-seed precedent) alongside the already-routed
   ECC/tilting instruments; 2.3 once tilting's judge half exists; 2.1 only after a marginal-level repair
   passes the instruments; 2.4 on its own queued lane; 2.5 anytime (no outcome).
3. **Shared risks, stated once:** (a) any law-referential conditioning can amplify law error — external
   realized targets only, U3 attached to every generated sleeve; (b) sparse targets — use multi-threshold
   ladders and the 2.5 priors, never a single tuned point; (c) replacement-form hazard — additive /
   ordering-preserving forms only; (d) ±1-scale effects die to bank luck — use the stratified/antithetic
   bank designs (untried-ideas 1.6) for these screens.
4. Anything that passes a screen ships as a frozen 2026 prospective shadow; the historical panel remains
   screening data only.

> **Production review — simplify the first pass.** Do not begin with a four-cell factorial or a large dose
> grid. For each genuinely new shared-substrate idea, first run one frozen end-to-end treatment against the
> incumbent at equal compute. A flat/harmful result closes that implementation. A promising result earns the
> smallest follow-up needed to distinguish generation from judgment and to test compatibility with other
> winners. This is the fastest route through the ideas while preserving interpretable promotion evidence.

## 5. Aggressive pre-season execution plan

The exact dates may move with Cloud Run completion, but the work order should not:

1. **Now:** execute/read frozen 088. In parallel, complete outcome-disabled mechanics for 085, the single-dose
   additive regime overlay, and 089's ECC/minimum-KL instruments. Keep no more than the provider-safe number
   of cloud executions active and serialize historical-outcome reads under the existing lease.
2. **First new end-to-end screen:** low-dose additive regime overlay versus incumbent on the current
   D800/K80/DEMAX stack. It is the fastest credible dual-action idea and has the strongest prior evidence.
3. **Existing participation screen:** run 085 unchanged. It is judge-only by design; if it materially reduces
   contamination or improves the endpoint, immediately prepare one coherent role-state generation successor.
4. **Dependence repair:** run 089's gated ECC and minimum-KL work without adding the other ideas to that family.
   If the instrument stage selects a viable repair, give it one equal-budget efficacy screen.
5. **Only on a promising precursor:** try the joint-event generation-plus-tilt package after minimum-KL, or
   the coherent role-state generator after 085. Pick the one whose precursor produced the stronger engagement;
   do not run both merely to exhaust a checklist.
6. **Late-window crossing:** combine only surviving components in one frozen generation × judgment × retrieval
   book comparison, then freeze prospective Week-1 shadows by September 12. No historical result alone changes
   the entered policy.

Elite-world allocation receives a mechanics/support screen during this window but an efficacy slot only if a
law repair first succeeds. Tracking-prior work continues as background infrastructure and must not displace
the short end-to-end screens above.

## 6. Sources

- Parent note + production-lead routing/087 seal:
  `reports/2026-09-02-operator-note-midside-extremes-and-score-ideas.md`
- `nfl2/reports/2026-08-31-untried-ideas-corpus-and-selection-deep-research.md` (1.1/1.2/1.6, Tier 2.7,
  Tier 4.4, §0 diagnosis)
- `nfl2/LEDGER.md` rows 004d/010/010a/012 (overlay family), PREREG-047/052/055; lab reads 003/003-recal,
  026, 033/035, 036, 049b, 055, 117-analog candidate scaling
- `nfl2/reports/2026-08-31-where-the-score-is-lost-synthesis.md` (search-only failures; §9 crossed funnel)
- `nfl-predictions/reports/2026-07-25-system-study.md` Addenda 99 (Schaake), 115 (conditional templates),
  and the hierarchical-Gumbel closure
- Tracking substrate: production tracking v0 (1,384-player traits, gsis crosswalk), nflverse NGS weekly
  aggregates
