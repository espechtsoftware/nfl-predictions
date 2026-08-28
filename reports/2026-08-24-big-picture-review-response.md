# Big-picture review response: aiming the Foundry at 230+

**Date:** 2026-08-24
**Reviewer:** Claude (Fable), high-level pass over
`reports/2026-08-24-foundry-system-big-picture-review-guide.md`
**Operator-stated objective:** among ~80 entries per slate, maximize the
probability that **at least one lineup scores 230+**, as consistently as
possible. Averages matter little. The operator explicitly asked for methods
that reach results "beyond what seems mathematically probable."
**Status:** outcome-blind commentary. Nothing here authorizes an outcome
read, a production change, or interference with the v12 lanes. Any idea
below that becomes an experiment must follow the standing preregistration,
equal-budget, and paired-control laws.

---

## 1. The single most important observation

The system's stated estimand (`S = max score in the book`) is right, but
**almost every operational surface in the guide is calibrated 35–40 points
below the operator's actual target.** The selector coverage line is 194. The
sparse tail sidecar records `>200` events. The tail ladder tops out at 220.
Historical context: mean weekly book max ≈ 179, and clearing **194** happened
in only ~25% of panel weeks. 230 is not "a bit further up the same curve" —
it is a different statistical regime, and optimizing 194-coverage is only
weakly coupled to it.

This matters because `P(max of 80 ≥ 230)` is an **extreme-value problem**,
and extreme-value problems have a well-known property: the behavior of the
maximum is governed almost entirely by the far tail of the per-lineup score
distribution and by the **dependence structure among your 80 tickets** — not
by means, not by mid-tail coverage, and not by anything a 194 line can see.

Concrete consequence: every layer should carry a 230-native instrument.

- **Selector:** add `coverage-230` and an unbounded-ladder variant
  (200/210/220/230/240 with steeply convex weights) to the registered
  catalog. `expected-max-v1` is the closest existing law but its utility is
  linear; a convex-utility expected-max (`u(s) = max(0, s - 200)^2` or an
  indicator at 230) is the literal objective.
- **Evidence:** extend the sparse sidecar and the historical scorecard to
  230/240/250 thresholds and record, per slate, **how many of the 50,000
  worlds contain any admitted lineup ≥ 230 at all**. That number is the
  ceiling on what any selector can do and nobody currently reports it.
- **Fill diagnostics:** report corpus ceiling `C` and conversion gap `C−S`
  restricted to the 230+ regime, not just overall max.

## 2. The binding-constraint hierarchy (check it in this order)

Before optimizing any single stage, establish which stage actually binds at
230. My strong prior, given the guide's own numbers, is this order:

1. **Simulator tail fidelity.** If the world model's joint tails are too
   thin, there are almost no 230-relevant worlds among the 50,000, every
   230-aware selector starves, and no fill or retrieval change can help.
   This is checkable outcome-blind and cheaply: count simulated worlds whose
   optimal-lineup ceiling reaches 230+, and separately fit an extreme-value
   (GPD/peaks-over-threshold) model to the *realized* corpus-tail scores
   already in the quarantined research tables. If realized 225+ lineups
   occur materially more often than the simulator says they should, the
   simulator's copula is the bottleneck — and fixing it is precisely the
   preregistered selector-reopening condition ("an adopted new dependence
   model," Addendum 95), so this path is ledger-legal.
2. **World supply at the tail.** Even a well-calibrated simulator wastes
   almost all of 50,000 i.i.d. worlds on the middle of the distribution. See
   §4.1 (importance sampling) — this is likely the highest ROI single change.
3. **Fill.** Does the corpus *contain* 230+ lineups in the worlds/realized
   history where 230 was achievable? The prior census (boom = 15.8% of
   corpus but 69.2% of 210+ candidates) says tail supply is concentrated and
   probably still undersized.
4. **Retrieval.** Only after 1–3 are answered does selector law matter. The
   guide's own all-boom lesson (ceiling +9, book +1.34) shows retrieval can
   fail to harvest — but it can't harvest what generation never made and the
   simulator never valued.

The guide treats fill/admission/retrieval symmetrically (the 2×2×2). That is
correct for attribution, but **resource allocation should follow the
hierarchy above**, and today the plan spends most of its sophistication on
stages 3–4 while stage 1 is unexamined.

## 3. What "beyond mathematically probable" really means (the honest version)

You cannot beat mathematics, but there are four legitimate places where
outcomes that *look* impossible under naive models become achievable. Each is
a concrete research direction:

### 3.1 Reality's joint tails are fatter than product-of-marginals intuition

A 230 lineup needs nine players averaging ~25.5 DK points. Under
independence that is astronomically unlikely — which is exactly why naive
math says 230 "shouldn't happen." It happens anyway because scoring
cascades: a shootout produces QB 40 + two pass-catchers 30+ + the opposing
QB stack simultaneously. **The entire edge is in the dependence structure.**
Whoever models joint booms best gets tail probabilities that look impossible
to everyone using thinner copulas. Directions:

- Fit the simulator's game-level dependence to *historical extreme weeks
  specifically* (a regime-mixture or heavy-tailed/t-copula component for
  "chaos games"), not to average weeks. Ordinary calibration criteria
  (CRPS, mean coverage) will barely notice tail dependence; a variogram/
  tail-dependence coefficient measured on 220+ historical games will.
- Lineup construction should be **narrative-coherent at the extreme**: every
  entry is a fully-committed bet on one specific cascade (this game goes to
  65 points and the scoring runs through these five players), never a hedge.
  Hedging within a lineup destroys exactly the joint-tail mass you need.
  `boom` (one-world optima) already embodies this; the improvement is
  conditioning the worlds themselves harder (§4.1).

### 3.2 The union trick: 80 near-independent tickets, not 80 good lineups

`P(max ≥ 230) = P(union of 80 tail events)`. With positively correlated
entries the union probability collapses toward the single best entry; with
near-disjoint tail events it approaches the *sum* of the individual tail
probabilities — up to an ~80× multiplier hiding in book construction. This
is the mathematically legitimate "multiplier beyond what seems probable."
Directions:

- Measure and report **effective number of independent tail shots** per book
  (from the score-vector correlation matrix restricted to tail events — the
  effective-rank diagnostic in §14 of the guide, but computed on 230-regime
  events, not full vectors).
- A selector variant that explicitly partitions worlds into disjoint extreme
  scenarios (scenario clustering on tail worlds) and assigns entries to
  scenarios — "scenario tickets" — is a cleaner formulation of what greedy
  coverage approximates, and at 230 the greedy approximation degrades
  because per-lineup event sets are tiny and noisy.
- Note the tension: §3.1 wants maximum correlation *within* a lineup, §3.2
  wants minimum correlation *across* lineups. That pair of properties —
  internally concentrated, externally orthogonal — is the design signature
  of a max-seeking book and could be scored directly as a book diagnostic.

### 3.3 Importance sampling: spend simulation where the objective lives

Of 50,000 i.i.d. worlds, perhaps a handful are 230-relevant, so every
tail-aware estimate has terrible variance and every tail-aware selector
overfits those few worlds. The standard fix is to **sample worlds
preferentially from the tail region and reweight** (importance sampling /
splitting), giving thousands of effective tail worlds at the same compute.
This makes P(≥230) estimable at all — the difference between "the math says
~0 with huge error bars" and "the math says 3.1% and we can optimize it."
The guide already lists "stratified world generation" as a fill experiment;
I'd promote tail-enriched world *releases* (a registered `T`-block series
alongside R0–R4) to a first-class platform feature, because it upgrades
fill, admission, retrieval, and evaluation simultaneously.

Related: the generator's visit schedule ranks worlds by **total slate
draw**. A diffuse high-total world can have a modest best-lineup ceiling,
while a concentrated medium-total world can contain a 240 lineup. Ranking
visit-worlds by **achievable optimal-lineup score** (solve the world, rank
by its optimum — or a cheap upper bound, e.g. top-9-by-position sum) targets
the actual objective. This is a registered world-schedule experiment the
guide already contemplates in general terms; it should be the first one run.

### 3.4 The field's model is the ultimate benchmark

A final honesty check: 230 is a proxy. The real event is "beat the field
max," and field max varies by slate (some weeks 218 wins the Milly, some
weeks 260). Two implications:

- A fixed 230 line mis-spends entries on slates where the winning bar is
  240+ (high-total, soft-pricing weeks) and overshoots on slates where 215
  wins. A **slate-conditional threshold** — model the field-max distribution
  from the standings captures already being collected — is strictly closer
  to the objective and is a small change to any ladder/coverage law.
- Score and field-relative rank eventually diverge via duplication: at the
  extreme, the constructions most likely to hit 230 (obvious shootout
  stacks) are also most likely to be duplicated. For *qualifiers* (score
  thresholds) this doesn't matter; for the Milly it does. Keep the two
  contest types' objectives formally separate — the guide's warning that
  4-entry books are not validated by exact-80 evidence is even more true
  when the objective is tail-seeking: a 4-entry max-seeking book is nearly
  pure scenario lottery and should be designed as such.

## 4. Specific critiques and suggestions on the current plan

1. **Season clock vs. platform build.** Week 1 is ~12 days away. The
   sequence in §18 (seal v12 → R6-v2 panel → Foundry Next → Neo4j → React)
   is architecturally right, but the graph/UI/product tail of it changes no
   Week-1 book. The subset that changes Week-1 outcomes is: v12 seal, the
   one-slate R6-v2 smoke, the 54-slate simulated panel, the controlled
   grade, and a nominated strategy bundle. I'd explicitly time-box
   everything after step 13 as post-Week-1 work.
2. **Seven selectors, none aimed at the target.** As §1 above: add
   230-native laws before the R6-v2 protocol freezes, because after the
   freeze, adding one is a new preregistered family and the retrospective
   panel is spent. The tail-ladder weights (1/4/12 at 200/210/220) encode a
   convexity guess; extending the ladder to 230/240 with steeper weights
   costs nothing now and is expensive to add later.
3. **The `mean-score-v1` negative control is good; add a second negative
   control at the other end** — e.g., "80 highest single-world scores
   regardless of overlap" (max-seeking with zero diversification). The gap
   between it and the coverage laws isolates the value of the union trick
   specifically, which is the mechanism claim in §3.2.
4. **The 200-event sidecar will be nearly empty exactly where it matters.**
   With i.i.d. worlds, 230+ events will be so sparse that trait analysis at
   the operator's threshold is impossible. This is another argument for
   tail-enriched world blocks (§3.3) — they make the sidecar dense in the
   region the operator cares about.
5. **Winner cohort: mine it at 230+, not just first place.** The
   reconciliation plan (§11.2 of the guide) is right. One addition: the
   portable question isn't "what did winners look like" but "what did
   *230+ scorers* look like versus same-slate 190–210 scorers" — that
   contrast isolates the last 30 points, which is the operator's regime.
   Prospective capture of top-0.1% (not only top-10) supports this.
6. **Mean sacrifice should be an explicit registered lever.** The system's
   history (punt-boost deletion cost tails; salary floor and stack mandates
   kept because deletion cost tails) shows the operator already pays mean
   for tail. Since averages are explicitly not the objective, a fill preset
   that *hard-commits* to tail (e.g., all entries required to clear 230 in
   at least one training world) is a legitimate arm — with the caveat that
   qualifier contests may still have a min-cash consideration the operator
   should confirm is irrelevant.
7. **Guard against 230-overfitting.** Everything above sharpens the
   instrument at a threshold where events are rare; rare-event optimization
   is exactly where panel mining bites hardest. The mitigations are the
   ones already in the ledger — preregistered bounded families, block
   breadth requirements (a 230 signal supported in one world block is an
   accident), cross-fit, and prospective 2026 as the only real
   confirmation. The block-supported and regime-robust selectors already in
   the catalog are the right template; they just need 230-native versions.

## 5. Ledger-consistency check (pressure test, per operator practice)

- **"Selection is closed" (Addendum 95)** was scoped to *the current
  simulator and static feature set*. Everything in §2–§3 above routes
  through a changed dependence model, new world releases, or new pre-lock
  signals — all inside the preregistered reopening conditions. No proposal
  here re-tunes a selector on the spent 107/54-slate panels outside a
  frozen family.
- **Equal-budget law:** tail-enriched world blocks and ceiling-ranked visit
  schedules are world-schedule treatments and must be run as same-image,
  equal-visit-budget arms, exactly as the guide's §10.1 contemplates.
- **Audit-before-verdict:** the simulator tail-calibration census (§2, item
  1) is an instrument audit, not an outcome read — it uses realized corpus
  tails already quarantined for research, under the existing research
  eligibility gates. It should still be written up as a preregistered
  census with the read scope declared before looking.
- **No interference with v12/R6-v2 in flight:** every suggestion here lands
  either in the R6-v2 pre-freeze window (selector/ladder additions), in
  Foundry Next presets, or in new world releases. None touches the running
  lanes.

## 6. If only three things get done before the season

1. **Tail census + simulator tail audit** (outcome-blind, cheap): how many
   simulated worlds and realized corpus lineups reach 230, and does the
   simulator's extreme-tail frequency match reality's? This decides where
   every subsequent dollar goes.
2. **230-native instruments everywhere**: extended ladders, 230-coverage
   selector, 230-regime `C`/`S`/`C−S`, effective-independent-tail-shots
   book diagnostic — all added before the R6-v2 freeze.
3. **One tail-enriched world block release** (importance-sampled or
   ceiling-ranked), run as a registered paired arm. It is the single change
   that upgrades generation, admission, selection, and evaluation at once,
   and it is the most plausible source of results that look "beyond what
   the math allows" — because the math most people run can't even see the
   region this makes visible.
