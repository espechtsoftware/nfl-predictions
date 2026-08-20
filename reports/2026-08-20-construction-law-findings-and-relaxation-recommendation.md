# Construction mandates, the simulator's dependence defect, and what to do about relaxation

**Date:** 2026-08-20. **Audience:** an independent model/reviewer.
**Status:** findings from completed frozen experiments plus a
recommendation. Nothing here changes the money policy; no adoption is
claimed.

Self-contained: every number below comes from a committed receipt, cited
by report path. Supporting context lives in `HANDOFF.md` (current state),
`CLAUDE.md` (binding validation rules), `README.md` (architecture), and
`reports/2026-08-19-preseason-test-queue.md` (the ordered queue).

---

## 1. The program in one paragraph

DraftKings NFL Millionaire-Maker system. The optimization target is the
**weekly maximum realized score of an entered book**, not expected value.
The standing research pipeline builds an exact-80 book by generating candidate lineups
against ~50,000 simulated worlds and selecting for coverage of a
194-point line. The registered Phase-S finite-K plus SIS-ASOE baseline on
the 54-slate 2023–2025 Sunday-main
corpus: mean weekly best **176.06**; it clears 194 on 8 of 54 slates.
(`reports/current-baseline.json`.)

Production also imposes **construction mandates** on every candidate it
builds: the QB must be stacked with at least two same-team pass catchers,
plus at least one "bring-back" from the opposing team, plus a $49k salary
floor and two RB prohibitions. These are house strategy rules, not
DraftKings rules.

---

## 2. Four findings that are in tension

### 2.1 The mandates exclude most real winners

Census over 51 tracked Millionaire winners (2023–2025) versus 64,098
registered candidates and 20,320 selected lineups
(`reports/2026-08-19-winner-structure-census-results.md`):

| Shape | Winners | Our pool | Our books |
|---|---|---|---|
| Naked QB (no stack partner) | 22% | 0% | 0% |
| QB stack ≤ 1 partner | 63% | 0% | 0% |
| No bring-back | 61% | 0% | 0% |
| Full mandated shape (stack ≥2 + BB ≥1) | **16%** | **100%** | **100%** |
| ≤3 players in any one game | 69% | 0% | 0% |

43 of 51 winners violate the mandates outright. 100% of what we generate
sits in a structural region containing 16% of winners.

### 2.2 We are nowhere near the winners, and never have been

- Best overlap between any registered candidate and that week's winner:
  median **4 of 9** players; never ≥7 on any slate; and after
  exposure-preserving null calibration the proximity is **exactly
  chance** (max-minus-null median 0.00).
  (`reports/2026-08-19-winner-anatomy-results.md`.)
- Our book has beaten the actual winner on **0 of 50** paired slates;
  median shortfall **53.4** points. Winner scores median 233.2; our
  best-ever weekly max is 223.9.
  (`reports/2026-08-20-beat-the-winner-scorecard-and-week1-readiness.md`.)
- No winner is ever the *optimum* of any simulated world (0/51, median
  47.4 points below the world optimum, 4/9 overlap).
  (`reports/2026-08-19-winner-world-optima-and-field-null-results.md`.)

### 2.3 The simulator's dependence is measurably wrong, with a direction

Frozen remeasurement, 54 slates, 1,194 team-weeks, 2,000-replicate
cluster bootstrap. log(simulated/realized) co-boom rates; the
equivalence band is ±0.14 (±0.095 for multiplicity ≥2):

| Cell | Simulated | Realized | log(sim/real) | Verdict |
|---|---|---|---|---|
| multiplicity ≥2 | 1.063 | 0.821 | +0.259 | material miss |
| multiplicity ≥3 | 2.097 | 0.997 | +0.744 | material miss |
| multiplicity ≥4 | 5.654 | 1.088 | **+1.648** | material miss |
| QB–RB | 2.925 | 0.911 | +1.167 | material miss |
| RB–RB | 2.189 | 0.494 | **+1.488** | material miss |
| TE–TE | 1.609 | 0.420 | +1.343 | material miss |
| WR–WR | 1.977 | 0.991 | +0.691 | material miss |
| QB–TE | 2.353 | 1.852 | +0.239 | inconclusive |
| **QB–WR** | **2.572** | **3.339** | **−0.261** | **material miss (UNDER)** |

Every generic teammate pairing is **over**-coupled — five-fold at
four-plus simultaneous booms. The single pairing that actually wins
tournaments, **QB→WR, is under-coupled.** This is the only law defect we
have with a measured direction.
(`reports/2026-08-19-all-boom-and-dependence-results.md`.)

### 2.4 Relaxing the mandates made our book WORSE

Frozen arm `20260819-stack-relaxation-carve-v1`, 54/54 terminal cells and
53 paired S endpoints (the 2025-W1 recovery cell has no S endpoint), one lever
(`OPEN_BOOM_SOLVES=8`): 8 of 40 boom solves per seed dropped the QB-stack
and bring-back minima; everything else — salary bounds, RB prohibitions,
worlds, candidate budget, selector, seeds — held identical.

| Endpoint | Control | Treatment |
|---|---|---|
| Mean selected score | 178.57 | **177.59 (−0.98)** |
| Slates better / worse / tied | — | **6 / 11 / 36** |
| ≥194 slates | 9 | 8 |
| ≥200 slates | 7 | 6 |
| Winner overlap vs chance null | +0.242 | +0.189 |

p_mean 0.367 — not significant, but directionally consistent and
regressive at exactly the thresholds that matter.

**The mechanism gate makes this a real negative estimate rather than a
vacuous arm, but it does not make the causal explanation decisive.** The
arm was not vacuous: 2,152 open candidates were generated and the
*unchanged* production selector admitted **530 of them into the books, on
all 53 slates**. The selector admitted un-mandated candidates in quantity
and the whole treatment books got slightly worse. Whole-book winner overlap
moved *away* from the winners; the retained receipt does not identify the
structures of the selected open-tagged subset. The estimate is still noisy
(`p_mean=0.367`) and the
single treatment relaxed both same-team stacking and cross-team bring-back
requirements together.
(`reports/2026-08-20-stack-relaxation-carve-results.md`.)

---

## 3. The reconciliation

The intuitive inference from 2.1 — "the mandates exclude the winning
shapes, so relax them" — is **falsified at this dose** by 2.4. Both
statements are simultaneously true:

1. The mandates exclude 84% of real winners' structures.
2. This bundled k=8 relaxation did not improve our books under the current
   law and selector.

The leading mechanism that could reconcile them is 2.3. Our simulator
under-couples QB→WR by −0.26 log units while over-coupling every generic
teammate pairing. Inside that law, a stack can be worth *less* than it is
in reality, so an unconstrained solver can under-build stacks and
over-build generic same-team pile-ups (which the law overvalues by up to
five-fold).

**The same-team stack mandate may be functioning as a hand-applied
correction for a known law defect.** That is a plausible, testable
explanation—not an identified causal result. The cited dependence table
does not identify the bring-back mechanism: bring-backs are cross-team,
and the current simulator's nearly independent team factors remove much
of the game-level dependence that could price them. A3 bundled the two
relaxations, so it cannot tell us whether its negative estimate came from
the stack change, the bring-back change, their interaction, portfolio
variance, duplication control, or sampling noise.

A supporting observation points the same way: deep simulated world optima
carry roughly **three times** the never-realized player-score mass of
actual winning rosters in the same worlds (median +19.3 points versus
+5.8). The law's extreme worlds are composed unrealistically, so shapes
selected to exploit them are selected on mispricing.
(`reports/2026-08-19-winner-anatomy-results.md`.)

---

## 4. Recommendation on relaxing the laws

**Do not relax the construction mandates now. Repair the dependence
law first, then re-test relaxation on the repaired law.**

Rationale: if the mandates are a correction for a mis-specified law, then
(a) relaxing them before the repair predictably costs points — now
observed; and (b) after a successful repair they should become
*unnecessary*, and relaxation should either help or be neutral. That
makes the sequence a genuine test of the reconciliation rather than a
preference.

### Proposed order

**Step 1 — repair the law (A2a dependence factor split).** Reduce the
shared/generic same-team factor and add a sparse QB→WR allocation factor,
targeting the nine measured cells above. Do not apply one common factor to
all pass catchers: WR–WR is already high and QB–TE is inconclusive. Preserve
each player's marginal draw distribution exactly and change dependence only.
Stages must stay separate:

1. *Score-free mechanism census:* verify on simulated worlds only that
   the intended split is active, marginals are preserved, budgets match,
   and the treatment is non-vacuous.
2. *Frozen one-shot remeasurement:* do the material-miss cells move
   inside their equivalence bands without regressing protected cells?
   Guard metrics that must not degrade: book-tail exceedance calibration
   (currently realized 6 versus expected 2.76 at 210) and the
   optimum-realism metric.
3. *Only if the law-shape gate passes:* fixed-budget C/S candidate arm,
   then a 2026 prospective shadow if favorable.

Design notes: prefer the factor split over TD-allocation coupling first —
parametric TD coupling was validly buried once (19 vs 27 in the old
universe/selector), and while that verdict does not transfer across the
changed stack, expectations should stay modest and the old failure mode
(season pooling) must be designed out.

**Cross-team diagnosis before Step 2.** Preregister supported
QB–opponent-WR/TE/RB and joint-team upper-tail cells. Prefer parameters fit on
pre-2023 data and evaluated on 2023–2025, or season-walk-forward fitting. Only
if this census identifies a cross-team miss should a separate A2b hybrid
game/opponent factor be tested; do not bundle it into A2a's first scored arm.

**Step 2 — re-freeze the relaxation question on the repaired law.** Keep
the prior k=8 bundled result closed; do not tune its dose. Before another
outcome-bearing run, use score-free mechanism checks to separate the
same-team stack relaxation from the cross-team bring-back relaxation. A
single-stack `qb_stack_min: 2→1` arm while holding bring-back fixed is the
best first construction test because one partner is the winners' modal
shape and A3's generated open population overproduced naked QBs. Test
`bring_back_min: 1→0` separately while holding stack fixed. A newly frozen
protocol may then test one prespecified contrast (or a
multiplicity-controlled factorial if justified before outcomes). The
preregistered reading becomes sharper than before:

- Relaxation now helps → the mandates were a law-defect correction and
  can be retired or reduced (via a 2026 prospective shadow, never by
  direct adoption).
- Relaxation still hurts → the mandates encode something real beyond the
  measured dependence defect, and they should be kept deliberately rather
  than by inertia.
- Either outcome is informative; today's negative result alone cannot
  distinguish them.

**Step 3 — add a winner-realism gate to newly designed construction arms
after A7.**
Score alone was nearly uninformative here (p 0.37); the *mechanism*
readings (530 admitted, overlap moving the wrong way) carried the
finding. Every such future construction arm should report the
winner-overlap-versus-chance instrument and a never-realized-mass check
alongside the score.

### What NOT to do

- **No dose sweep on this corpus.** Do not retry k=4, 16, 20 against the
  same 54 slates; that is panel mining and the protocol forbids it. The
  next dose is a new frozen arm on a changed law or a prospective shadow.
- **No wholesale mandate deletion.** Already rejected historically, and
  now with a bounded-carve companion result.
- **Do not chase winner-nearness directly** as an optimization target;
  proximity is chance-level and no winner is a world optimum.
- **Do not sequence selection-objective work (e.g. a tail ladder) ahead
  of the law repair without a realism guard.** A utility that rewards
  extreme simulated worlds more heavily will reward the region where the
  law is least trustworthy. If such an arm runs first, cap its top rungs
  where calibration support exists (210 is defensible; 230/240 are ~1 and
  ~0 events in 54 slates) and add a realism check to its mechanism gate.

---

## 5. Open questions for the reviewer

1. Is the "mandates as law-defect correction" reconciliation the most
   parsimonious explanation of the 2.1 / 2.4 tension, or is there a
   better one? (Alternative worth testing: the mandates act as a variance
   or duplication control that has nothing to do with dependence.)
2. Is the factor split the right first repair, given the measured cells,
   or does the pattern (all generic pairs over, QB–WR under) point to a
   different parameterization?
3. What is the minimum evidence that should license retiring a mandate,
   given that any historical positive still requires a prospective 2026
   shadow before it touches money lineups?
4. Should the salary floor and RB prohibitions be treated as part of the
   same question? Both were measured to exclude **zero** winners, so they
   were deliberately left untouched by the carve.

---

## 6. Independent implementation review and disposition

The recommendation to **leave production construction unchanged now is
accepted**, but for the narrower reason supported by the evidence: the
registered k=8 bundled relaxation did not prove higher scoring. It does
not prove that the existing mandates improve scores, and it does not
identify the dependence defect as the cause of the negative estimate.

The four reviewer questions are disposed as follows:

1. The law-defect-correction story is the best current hypothesis for the
   same-team stack requirement, not a conclusion. Variance, duplication,
   selector interaction, and sampling noise remain live alternatives.
2. A factor split is the right first same-team repair because it targets
   the only directional defect measured with useful precision. The repair
   must not be represented as a bring-back repair. Cross-team/game-level
   dependence needs its own score-free measurement and protected cells.
3. A mandate can be reduced only after: a frozen score-free mechanism
   gate; a fixed-budget historical arm under the repaired law; and an
   unseen 2026 shadow with a prespecified positive score endpoint and no
   protected-tail regression. A historical positive alone cannot alter
   money lineups.
4. Salary floor and RB prohibitions remain out of scope. The current census
   found no winner exclusion from them, so relaxing them would add a new
   causal question without measured upside.

No validation, point-in-time, fixed-budget, one-shot, provenance, or
prospective-adoption rule should be relaxed in pursuit of a higher score.
Those rules protect the score claim from hindsight. The only permissible
relaxations are lineup-construction treatments that are default-off,
preregistered, mechanically isolated, and promoted only after proving the
registered endpoint. A7 already satisfies the document's warning: it caps
reward at 210, treats 220/230/240 as report-only, and carries a score-free
simultaneous-extremes realism guard. It may proceed without changing the
production construction law. Its frozen scope intentionally excludes the
winner-overlap and never-realized-mass diagnostics above, so those diagnostics
must not be retrofitted into A7 after its science was registered.

---

## 7. Minimal winner-like implementation now prepared

The recent winner census does not justify copying historical winner shares
into hard quotas. It does justify correcting the specific mismatch in A3's
treatment population. Across 51 winners, the number of same-team QB WR/TE
partners was 0/1/2/3+ in approximately 22%/41%/31%/6% of lineups. A3's open
candidates were approximately 58% naked and only 30% exact-single-stack, so
that arm did not actually test the modal winner structure.

A separate default-off seam, `SINGLE_STACK_BOOM_SOLVES`, is therefore prepared
with the narrowest causal contrast:

- replace exactly the registered number of deterministic boom visits; never
  add solve slots or candidates;
- require exactly one same-team QB WR/TE partner on those visits;
- retain the incumbent bring-back, salary, RB/DST, and game rules unchanged;
- retain the incumbent worlds, seeds, objective, candidate budget, and
  selector;
- reject coexistence with `OPEN_BOOM_SOLVES`, malformed or over-budget doses,
  solver/infeasibility failures, and any duplicate-replacement shortfall;
- tag the treatment `single_stack` while retaining its primary `boom` family;
- force both OPEN and SINGLE to zero in the money policy and reject either in
  deployed application configuration.

The seam is locally covered by 59 focused tests, including absent/zero parity,
exact-one structure, preserved bring-back and protected constraints,
deterministic budget use, duplicate shortfalls, runtime visibility, and
production/deployment isolation. This is implementation readiness only. It is
not frozen, outcome-tested, shadow-licensed, or adopted.

To avoid repeating an over-broad arm, its execution order is fixed: first pass
the separate A2a same-team dependence repair; then freeze this one exact
single-stack dose under that repaired law. Bring-back removal, max-game spread,
ownership, and residual-world pricing remain separate experiments. This keeps
the redesign focused on producing more winner-like roster composition without
claiming that descriptive winner frequencies are an oracle.

---

## 8. Execution update: the winner-law path is now the active queue

A7 v1 subsequently failed its one-slate outcome-blind smoke while hashing the
player-source query. The frozen player table contains 439 SQL NULL projections
among 30,044 rows; the receipt rejected their pandas NaN representation before
any outcome query or scientific output. This is neither an A7 score result nor
evidence against its utility. V1 is closed with no retry, and a fresh A7
protocol is deferred rather than allowed to displace the higher-priority law
work. Exact evidence is recorded in
`reports/2026-08-20-a7-outcome-blind-smoke-failure-and-queue-disposition.md`.

The queued tests now align with the winner evidence in the following limited,
scientific sense:

1. A2a first tests whether the simulator can reduce generic teammate
   over-coupling while increasing the specifically under-coupled QB–WR cell,
   without changing player marginals.
2. The prepared exact-one arm then tests the winners' modal QB construction
   shape without copying winner frequencies into a fitted quota and without
   simultaneously removing bring-backs.
3. Only a later, separate cross-team dependence census can justify a
   bring-back relaxation.

What is *not* in the active queue is equally important: no wholesale rule
removal, no naked-QB redo, no ownership template, no 230/240 world chase, and
no production change. The tests are designed to discover whether a narrow
winner-like construction improves the exact-80 book—not to force historical
winners to appear in-sample.
