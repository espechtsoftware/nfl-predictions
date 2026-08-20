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
Production builds an exact-80 book by generating candidate lineups
against ~50,000 simulated worlds and selecting for coverage of a
194-point line. Verified baseline on the 54-slate 2023–2025 Sunday-main
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

Frozen arm `20260819-stack-relaxation-carve-v1`, 54/54 cells, one lever
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

**The mechanism gate makes this decisive rather than a shrug.** The arm
was not vacuous: 2,152 open candidates were generated and the *unchanged*
production selector admitted **530 of them into the books, on all 53
slates**. The selector wanted the un-mandated shapes, took them in
quantity, and the books got slightly worse. Winner overlap moved *away*
from the winners.
(`reports/2026-08-20-stack-relaxation-carve-results.md`.)

---

## 3. The reconciliation

The intuitive inference from 2.1 — "the mandates exclude the winning
shapes, so relax them" — is **falsified at this dose** by 2.4. Both
statements are simultaneously true:

1. The mandates exclude 84% of real winners' structures.
2. The mandates are, right now, *helping* our books score.

The mechanism that reconciles them is 2.3. Our simulator under-couples
QB→WR by −0.26 log units while over-coupling every generic teammate
pairing. Inside that law, a stack is worth *less* than it is in reality,
so an unconstrained solver will under-build stacks and over-build generic
same-team pile-ups (which the law overvalues by up to five-fold).

**The mandates have been functioning as a hand-applied correction for a
known law defect.** They force the correlation the simulator fails to
value. Relaxing them while the law remains mis-specified removes the
correction and exposes the defect — which is exactly the negative result
observed, and exactly why the freed shapes drifted *away* from winners
rather than toward them.

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

**Step 1 — repair the law (A2 dependence factor split).** Reduce the
shared/generic team factor and add an explicit QB→pass-catcher factor,
targeting the nine measured cells above. Stages must stay separate:

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

**Step 2 — re-freeze the relaxation carve on the repaired law.** Same
single lever, same k=8 dose, same mechanism gates, newly frozen protocol.
The preregistered reading becomes sharper than before:

- Relaxation now helps → the mandates were a law-defect correction and
  can be retired or reduced (via a 2026 prospective shadow, never by
  direct adoption).
- Relaxation still hurts → the mandates encode something real beyond the
  measured dependence defect, and they should be kept deliberately rather
  than by inertia.
- Either outcome is informative; today's negative result alone cannot
  distinguish them.

**Step 3 — add a winner-realism gate to any future construction arm.**
Score alone was nearly uninformative here (p 0.37); the *mechanism*
readings (530 admitted, overlap moving the wrong way) carried the
finding. Every future construction/selection arm should report the
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
