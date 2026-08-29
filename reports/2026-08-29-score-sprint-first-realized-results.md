# Score sprint: first realized challenger results

**Date:** 2026-08-29

**Scope:** Sunday-main slates, 2023--2025 Weeks 1--18, 54 slates

**Primary metric:** mean of the realized weekly maximum from one selected book

**Status:** historical development evidence; not yet a production promotion

## Complete-union frontier result: new K80 retrieval leader

The preregistered complete-union re-portfolio is complete across all 54
slates.  It first scored every persisted lineup in the combined population
under the already-bound modeled worlds, retained an outcome-blind top-250
frontier, and then applied four fixed selectors at nested K80/K100/K150.  The
best K80 row is the cap-4 exhaustive-prefix-then-fill ladder:

| Complete-union selector | Mean weekly max | Median | >=194 | >=200 | >=210 | >=220 | >=230 |
|---|---:|---:|---:|---:|---:|---:|---:|
| **Cap-4 prefix, then disclosed fill** | **181.361** | **178.68** | **11** | **9** | 5 | 4 | **3** |
| Cap-5 prefix, then disclosed fill | 179.193 | 174.37 | 11 | 9 | **6** | **5** | 2 |
| Strict-200 evil twin | 179.066 | 174.37 | 11 | 9 | 4 | 4 | 1 |
| Effective-independent-shots DPP | 177.283 | 175.60 | 10 | 7 | 3 | 3 | 1 |
| Frozen current R6 champion | 178.435 | -- | 8 | 6 | -- | 4 | 2 |

The frozen adoption rule was: take the highest K80 mean only if it is
nonworse than the champion's 6/4/2 counts at 200+/220+/230+.  The cap-4
prefix-then-fill row passes at 9/4/3 and improves mean weekly maximum by
**2.926 points**.  It is therefore the new historical K80 retrieval winner
under the rule.  It should be promoted only as an explicit named Foundry
retrieval preset; it does not become a universal lineup-construction law.

The exact name matters.  This is not a globally cap-4 K80 book on every
slate.  Its greedy cap-4 prefix exhausted before 80 on 34/54 slates, so those
books used the preregistered unconstrained completion tail; 20/54 K80 books
were pure cap-4 prefixes.  Prefix length ranged from 36 to 112 and averaged
73.09.  By contrast, cap-5 remained a true hard-cap prefix through K80 on all
54 slates.  The winning preset must therefore remain labeled
`overlap-cap-4-exhaustive-prefix-then-fill`, with completion receipts exposed
in the UI and experiment graph.

The same fixed nested selectors produce this entry-volume curve:

| Selector | K80 | K100 | K150 | K100 >=200/220/230 | K150 >=200/220/230 |
|---|---:|---:|---:|---:|---:|
| **Cap-4 prefix, then fill** | **181.361** | **183.690** | **185.498** | 11 / 5 / 3 | 11 / 5 / 3 |
| Cap-5 prefix, then fill | 179.193 | 182.585 | 185.237 | 12 / 5 / 2 | 12 / 5 / 3 |
| Strict-200 evil twin | 179.066 | 179.821 | 184.553 | 9 / 4 / 1 | 11 / 5 / 3 |
| DPP | 177.283 | 178.917 | 182.611 | 8 / 3 / 1 | 10 / 4 / 1 |

K100 and K150 are operational entry-volume choices, not alternate selectors
that may be cherry-picked after outcomes.  The top-250 sieve's mean realized
ceiling is 188.432; it is narrower than the complete combined population and
must not be confused with that population's 205.793 ceiling.  At K80, cap-4
converted the sieve ceiling on 23/54 slates and left 7.071 mean points of
regret.

The cap-4 K80 season means were 188.041 (2023), 179.839 (2024), and 176.202
(2025).  The cross-season decline warrants prospective monitoring, but it
does not negate the frozen all-54 decision rule.

### Calibration reinterpretation

The external lab's outcome-aware diagnostic 036 reports that its simulator
overstates lineup upper-tail rates by roughly 1.5--2x overall and 2.8x for
leverage-family rosters.  It proposed a specific mechanism check for this
result: a hard overlap cap may reduce reliance on inflated co-boom worlds, in
which case modeled `P(book max > line)` should fall while realized performance
rises.

The already-frozen production artifacts show that signature.  These are
paired K80 comparisons on the same 54 slates:

| Cap-4 comparison | Modeled book-max mean delta | Modeled P(max >200) delta | Realized weekly-max delta | Realized W/L/T |
|---|---:|---:|---:|---:|
| Versus cap-5 prefix-then-fill | **-0.450** | **-0.70 percentage points** | **+2.168** | 19 / 10 / 25 |
| Versus strict-200 evil twin | **-0.663** | **-1.08 percentage points** | **+2.295** | 20 / 11 / 23 |
| Versus DPP | +1.272 | +1.07 percentage points | +4.078 | 25 / 8 / 21 |

Cap-4 was modeled below cap-5 on 49/54 slates and below the evil twin on all
54, yet realized higher against both.  Its mean modeled probabilities for
`max > 200/210/220/230` were 26.825%/15.224%/7.793%/3.549%.  The final value,
3.549%, was the **lowest modeled >230 probability of the four challengers**,
while cap-4 produced the **most realized 230+ weeks** (three).

This is evidence for a calibration-correction mechanism, not proof that
diversity is irrelevant.  Cap-4 still has lower average pairwise roster
overlap, and its completion path means it is not a pure cap experiment on
34/54 slates.  The correct conclusion is that the winning law may be choosing
a better point on a diversity-versus-model-overconfidence frontier.  The
frozen adoption result stands, but the preset and UI must expose both modeled
tail probability and realized calibration rather than labeling the gain as
diversity alone.

The lab has frozen PREREG-016 to replicate the exact selector law over a
different boom-first K1 population, with cov194, ladder, cap-4 ladder, cap-5
ladder and cap-4 coverage arms across banks 210/211/212.  It explicitly tests
whether simulated exceedance falls while realized performance rises.  No
PREREG-016 result exists yet; its independent read will determine whether the
law generalizes or is a population-by-selector interaction.

## Boom-first external result: review and production disposition

The external production brief is a high-priority generation test, not a
drop-in production promotion.  On 89 development slates and three independent
banks, moving the same 200 solves from `lev160/boom40` to
`lev40/boom160` improved K100 mean weekly maximum by **6.563** with a
season-clustered 95% interval of **[4.905, 8.101]**, won 66/89 slates, and
remained positive in every leave-one-season-out read.  K80 improved by
**4.819 [3.444, 6.032]** with 60/29 wins/losses.  This is unusually strong,
stable directional evidence.

The receiving test must still isolate exactly that allocation change.  Both
arms must use the same production simulator, centering, source snapshots,
role candidates, construction preset, CBWU selector, worlds and exact K80;
natural deduplication is reported rather than padded away.  The lab omitted
important production components, so its effect size cannot be assumed here.
The current production-shaped implementation has passed its scientific core
tests, but independent review found launch-trust gaps: no provider-bound
exact-54/54 collector, no no-publish real-artifact smoke gate, incomplete
build/job attestation, shallow result-to-manifest validation, and an improper
abort on role/boom roster collisions.  Those are being repaired before the
single historical execution.  No broader construction-preset rewrite will be
mixed into this causal pair.

The optional `lev40/boom360` arm should follow only after the 200-solve pair;
its measured incremental gain was much smaller (+0.68 at K100) and it changes
the total solve budget.

## Full-54 update: combined corpus and L2b selector surface

Two additional score-producing lanes are now complete.

The combined incumbent + F7/F8/F9 + hard-230 population has a realized
full-corpus ceiling of **205.793** average weekly maximum. Its best tested
exact-K80 book is the strict-230 selector at **178.661**, with
10/8/4/4/2 weeks at >=194/200/210/220/230. That is +1.199 against the same
selector on the old population, but only +0.226 against the actual frozen
178.435 tail-ladder champion. The combined population contains 451 realized
200+ lineups on 33 slates and 18 realized 230+ lineups on seven slates, while
the strict-230 book retrieves 200+ on eight slates and 230+ on two. The large
27.131-point mean gap from selected book to population ceiling makes retrieval
the primary measured bottleneck.

The L2b run scored all **300** predeclared cells across 54 slates. Its
post-outcome descriptive leaders are:

| Population / selector | K | Mean weekly max | >=194 | >=200 | >=220 | >=230 |
|---|---:|---:|---:|---:|---:|---:|
| L2b native R3 + effective-independent-shots DPP | 80 | **180.434** | 14 | 10 | 1 | 0 |
| L2b native R3 + effective-independent-shots DPP | 100 | **181.345** | 14 | 10 | 1 | 0 |
| L2b native R1 + correlation-aware | 150 | **184.349** | 18 | 13 | 1 | 0 |

These rows improve mean and 194/200 frequency, but they are **not** a
large-field-tournament improvement over the current K80 book: the frozen book
has four 220+ and two 230+ weeks, whereas every displayed L2b leader has one
220+ and zero 230+. The best L2b K80 tail cell also reached only two 220+
weeks and one 230+ week at a 177.640 mean. The next high-value experiment is
therefore to cross DPP, gamma-4/gamma-5 overlap diversity, and the strict-200
evil-twin selector onto the combined high-ceiling population, rather than
promote the L2b post-outcome mean winner.

Across all scientifically paired fraction cells, quarter-world mixture minus
native averaged -0.010 DK at K80, +0.127 at K100, and -0.095 at K150. There
is no broad fraction winner; the large local top-cell contrasts must not be
generalized to the complete surface.

## Executive result

The replenishing hard-230 population is the first new population mechanism in
this sprint to show a material matched K=80 improvement. Its best paired cell
was the effective-independent-tail-shots DPP selector:

| Population / selector | K | Mean weekly max | >=194 | >=200 | >=220 | >=230 |
|---|---:|---:|---:|---:|---:|---:|
| Hard-230 + DPP | 80 | **179.549** | 13/54 | 11/54 | 3/54 | 1/54 |
| Matched P0 + DPP | 80 | 177.298 | 14/54 | 9/54 | 1/54 | 1/54 |
| Difference | 80 | **+2.251** | -1 | +2 | +2 | 0 |

The result is promising under a fixed R1--R4 out-of-origin selector fit: R0 is
the hard-230 population's generation block and is intentionally excluded from
selection. The next production evidence is therefore a same-law crossing with
the diversity selectors and a combined-corpus comparison, not an R0--R4 fit
that would reuse the generator-origin block.

The targeted isolated structure profiles F7/F8/F9 did not establish an K=80
improvement over the current all-block R6 benchmark. Their strongest displayed
cell was 178.791, but that is one of five held-out-block coordinates and cannot
be selected after the realized read. Under the canonical R0 view, their best
K=80 rows were 176.169 for F7, 177.387 for F8, and 176.991 for F9. These arms
should not become standalone production defaults. Their retained value is as
potentially complementary contributors to a combined corpus, which is a
distinct test.

## Frozen references

| Reference | K | Mean weekly max | >=194 | >=200 | >=220 | >=230 |
|---|---:|---:|---:|---:|---:|---:|
| Legacy A7 ladder | 80 | 176.113 | 8/54 | 6/54 | 2/54 | 1/54 |
| Current R6 tail ladder / supported ladder | 80 | **178.435** | 8/54 | 6/54 | 4/54 | 2/54 |

The current R6 row is the decision-bearing all-block final-fit benchmark. The
hard-230 and crossed-profile rows below are deliberately labeled diagnostics
because their fit scopes differ.

## Hard-230 matched K=80 comparison

| Selector | P0 control | Hard-230 | Hard minus P0 | Hard >=200 | Hard >=220 | Hard >=230 |
|---|---:|---:|---:|---:|---:|---:|
| Convex excess | 178.594 | 179.358 | +0.764 | 10/54 | 3/54 | 1/54 |
| Correlation aware | 179.456 | 178.603 | -0.853 | 8/54 | 3/54 | 1/54 |
| Support switched | 178.221 | 179.523 | +1.301 | 8/54 | 4/54 | **3/54** |
| Effective independent shots / DPP | 177.298 | **179.549** | **+2.251** | **11/54** | 3/54 | 1/54 |

This interaction matters. Hard-230 is not uniformly better under every
selector, so the production test must cross the population with the selector
rather than promote the population in isolation.

The population ceilings were nearly equal in this particular 250-lineup
score-blind bridge: 196.134 for hard-230 and 196.079 for P0. The improvement
therefore came primarily from placing more of the available realized tail in
the selected book, not from a large increase in this bridge's oracle ceiling.

## Entry-count curve already visible

Hard-230's best observed weekly-max rows increased materially with book size:

| K | Best hard-230 mean weekly max | >=194 | >=200 | >=220 | >=230 |
|---:|---:|---:|---:|---:|---:|
| 80 | 179.549 (DPP) | 13/54 | 11/54 | 3/54 | 1/54 |
| 100 | 182.177 (support switched) | 17/54 | 10/54 | 4/54 | 3/54 |
| 150 | **185.517** (support switched) | **20/54** | **15/54** | 4/54 | 3/54 |

The non-monotone selector identities across K are diagnostic choices, not one
nested production book. Even so, the magnitude confirms that testing and
supporting 150-entry operation is one of the largest available scoring levers.

## F7/F8/F9 crossed-profile result

The immutable grade contains 315 cells: three profiles, five held-out world
blocks, seven selector coordinates, and the relevant 4/14/80/100/150 budgets.
No isolated profile produced a realized 230+ selected lineup in any K=80 cell.

At K=80, averaging each selector/profile result over the five block-specific
fits (a stability diagnostic, not a deployable consensus), the strongest rows
were:

| Profile / selector | Mean over five block fits | Block range |
|---|---:|---:|
| F7 QB/bring-back relaxed + correlation aware | 176.426 | 174.263--178.791 |
| F8 game cap 3 + correlation aware | 176.360 | 174.968--177.865 |
| F9 single QB partner + convex excess | 175.453 | 173.659--176.991 |

The result argues against any of these profiles as a standalone default under
the current belief law. It does not answer whether their union adds unique
tail lineups to the incumbent/hard-230 corpus, nor whether a different belief
law would make the structures valuable.

## Exact immutable evidence

- Catalog-wide outcome snapshot: generation `1787987566557209`, byte SHA-256
  `96c88d27cfa356794e250431dbcaa638fe7df2ec8dc1a9ead8538f0608c32f88`,
  3,547,704 bytes.
- Hard-230 grade: generation `1787987773846917`, byte SHA-256
  `a0fd3dc7b2ffae28b7dec97048da4fe99fedaf717b481b239c52c65819f01ef5`,
  15,126,123 bytes; internal grade SHA-256
  `fa6fe6f87b70736221d0696f781f5fc5e331ddefeb690e2f0fc281f146ccdea5`.
- F7/F8/F9 grade: generation `1787988278722136`, byte SHA-256
  `f62d4250773957cb8a7d8274d9cbb1030d3339adc970a0f234232d34a7cde438`,
  58,937,259 bytes; internal grade SHA-256
  `1cf54b0b86efac123ae4c3a45c209517601547c3fe39f4e4ea16b71034977fab`.
- Both challenger terminals existed before the first outcome read, and both
  grades cover all 54 slates.
- Combined descriptive grade: generation `1788000433892086`, byte SHA-256
  `8458337715af482d27664463fb2ed5adba7e0cf5151d6d3e9e10697c7886b139`,
  63,755,290 bytes; internal grade SHA-256
  `1454abc41aa839ff4dd31aaedd752b705a6e66d2e6966b1486ab305bd2e8dee1`.
- L2b provisional provider grade: generation `1788002384329100`, byte SHA-256
  `e862b5d1bb49abb8367d68bfb592b0d45854015669db6aa34921104bbc0ebc5a`,
  44,748,199 bytes; internal grade SHA-256
  `10c610d9c12c179993bc5718282250c207efbb213641781ac89c906599f48c69`.
  It is complete descriptive evidence, not promotion authority; the canonical
  exact replay remains an asynchronous audit.
- Complete-union frontier score-free terminal: generation
  `1788029872513108`, byte SHA-256
  `ec49ee14e2af9364c38931355f8a8bde51b2f3800a230b9a589934cc5062bdc1`,
  39,380 bytes; internal terminal SHA-256
  `9d973eb8b0da3da497db66e5cec431ffa43d74cb35b2665392f57a18bd4916f2`.
  Sole provider execution `atlas-minimal-c-s2023-w3-v1-ssk9n` completed exact
  54/54 before collection.  The reused job was restored after collection.
- Complete-union frontier grade: generation `1788029992254691`, byte SHA-256
  `cbeca6b84f1e78cd4dfa92913d2ee96d24bbabf0a0fb04965b6290fd0456a590`,
  4,104,786 bytes; internal grade SHA-256
  `67942399f1f0be7c3e000c9496337b3e3ce88fc5d8bb773f1f9c405b00e98e0a`.
  It contains all 648 fixed book/slate cells.

## Immediate decision schedule

1. **Completed:** run and rank the 300-cell L2b/diversity panel at
   4/14/80/100/150.
2. **Completed:** score DPP, cap-4, cap-5 and strict-200 evil-twin selectors
   over the complete combined union at nested K80/K100/K150.
3. **Decision recorded:** cap-4 exhaustive-prefix-then-fill is the new K80
   historical retrieval leader at 181.361 and passes the frozen 200/220/230
   guard.  Wire it as an explicit named preset with its completion receipt.
4. **In progress:** finish the bounded launch hardening and run the external
   boom-first allocation pair, `lev160/boom40` versus `lev40/boom160`, under
   identical incumbent construction and K80 retrieval.
5. If boom-first passes, cross the winning generation preset with the winning
   retrieval preset.  Test the 400-solve dose and legality-only construction
   separately; do not add independently measured gains.
6. Finalize the exact K80 Week 1 configuration by September 4.  Keep K100/150
   as explicit entry-volume choices, then allow only rehearsal and critical
   correctness fixes from September 5 onward.
