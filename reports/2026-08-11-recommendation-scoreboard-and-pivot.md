# Recommendation scoreboard and revised direction

Date: 2026-08-11. An honest accounting of the outside recommendations made on
2026-08-10/11, what the repository did with them, what the results were, and
what should change as a result.

**No code was changed.**

---

## Read this first

> **PARTIALLY SUPERSEDED 2026-08-11 by
> `2026-08-11-deep-analysis-calibration-and-data-audit.md`. Read that file
> first.** It found that the simulator's per-position dispersion constants
> (`calibration.DEFAULT_WIDEN`) were fit on 2019+2021 and never refit across
> seven material simulator changes, that `fit_widen_factors` is dead code, and
> that served q99 exceedance is imbalanced by position (WR 1.88% / RB 1.57% /
> TE 0.74% vs 1% nominal). Consequences for this file:
>
> - **§4.1 is retracted** — within-team Dirichlet allocation exists
>   (`GAME_SIM_USAGE=dirichlet`) and was tested at K=20 and K=8. It was not
>   untested. The residue is that neither test was at a data-consistent
>   concentration (empirical α₀ ≈ 29; production default is the K→∞ limit).
> - **§4.3 "stop" is deferred**, not withdrawn. Stopping is premature until the
>   calibration refit that the code's own docstring mandates has been run.
> - **§8.1 is demoted** below R1/R2 of the newer file. It remains a valid
>   diagnostic; it is no longer the first thing to run.
> - **§3.2's reading of the Stage B null is too strong.** Stage B tested a
>   single global scalar, which cannot fix a positional imbalance. It showed
>   that *global* marginal widening is not the 210+ lever, not that marginal
>   dispersion is irrelevant.
> - §1–§2 (the scoreboard and the corrections to my own claims) stand
>   unchanged, as does §7's measurement of the co-boom structure.

This file is written for the agent continuing this work. Four points, in
priority order:

1. **The "2.7× too thin tail" claim in the earlier outside review was wrong** —
   it was a pre-shaper artifact. The served path is 1.48% q99 exceedance
   against 1% nominal. The repository's qualification of that claim was correct
   on every point. Do not carry the 2.7× figure forward.
2. **The Stage B null is the most informative result of the sequence.**
   Inflating every marginal tail by 2.5% moved the 200 count `11→13` and moved
   *nothing* at 210/220/230/240. The remaining ceiling is **joint, not
   marginal**. Let this govern what is attempted next. See §3.2.
3. **The marginal-projection layer is close to exhausted.** Six vendor
   families, tail recalibration, TabPFN, ensemble variants, member-sampled
   worlds and Chronos have all been tried against it. Do not retry a closed
   family under a different window, support floor, field subset or model. See
   §5 for the explicit do-not list.
4. **Recommended ranking going forward, revised downward from two days ago:**
   *stopping historical experimentation* (§4.3) ranks **above** the field/payout
   model (§4.2) and roughly **level with** within-team allocation variance
   (§4.1). Continued historical arms have demonstrably near-zero marginal
   information; the prospective 2026 infrastructure is already built and frozen.
5. **Run §8.1 first, whatever else is decided.** §7 measured the realized
   co-boom structure and found it is **star-shaped through the QB** (QB→TE
   2.50×, QB→WR 2.34×) while same-position teammates are **independent**
   (WR–WR 0.99×) — a pattern the current single shared game multiplier
   structurally cannot produce. §8.1 tests that against the simulator's own
   draws for the cost of one execution, with a falsifiable prediction stated in
   advance, and it is decisive either way: it either indicates §4.1 or it
   makes §4.3 the clear answer.

### Companion documents

These four files are currently **untracked** in git. They are operator-supplied
outside reviews, superseded in the order listed — later files correct earlier
ones.

| File | Contents | Status |
|---|---|---|
| `2026-08-10-scoring-strategy-recommendations.md` | System-wide review; §3.1 field/payout model and §3.4 allocation variance originate here | §3.3 tail claim **superseded** by this file |
| `2026-08-11-fantasy-points-data-utilization.md` | Fantasy Points inventory, route-share measurements, coverage-shell effect-size arithmetic | Route-share centre findings confirmed by the component run; Defense PROE redundancy claim **retracted** |
| `2026-08-11-post-window-program-review.md` | Gate-power critique, served-tail recommendation | Gate critique adopted; tail magnitude **superseded** by this file |
| `2026-08-11-recommendation-scoreboard-and-pivot.md` | *(this file)* — scoreboard, corrections, §7 co-boom measurements, §8 new suggestions | Current |

### External sources cited in §7

- [Correlation at ceiling outcomes between teammates and their opponents — Underdog Network](https://underdognetwork.com/football/best-ball-research/correlation-at-ceiling-outcomes-between-teammates-and-their-opponents)
- [How to Play Fantasy Sports Strategically (and Win) — Haugh & Singal](http://www.columbia.edu/~mh2078/DFS_Revision_1_May2019.pdf) — Dirichlet-multinomial allocation precedent
- [Competing in daily fantasy sports using generative models — Mlčoch & Hubáček (2024)](https://onlinelibrary.wiley.com/doi/full/10.1111/itor.13344)
- [NFL DFS stacking correlation — Stokastic](https://www.stokastic.com/articles/nfl-dfs/nfl-dfs-stacking)
- [The most undervalued NFL DFS correlations — FantasyLabs](https://www.fantasylabs.com/articles/undervalued-nfl-dfs-correlations/)

---

## 1. Scoreboard

| Recommendation | Status | Result |
|---|---|---|
| §4.2 measure served-path tail exceedance | executed | **Defect confirmed, but far smaller than claimed** — served q99 exceedance 1.4774% (95% CI 1.2526–1.7021) vs my quoted 2.69% |
| §4.2 recalibrate the tail | executed (Stage A + B) | Stage A passed, factor 1.025; **Stage B lineup replay NEUTRAL** — 240/230/220/210 tied at 2/3/5/7 |
| §4.1 all-row gate (CRPS/pinball/MDE/paired CI) | adopted | Working as designed — and it made the next rejection *cleaner*, not softer |
| §4.3 route share → 2026 prospective shadow | implemented | Pending 2026 outcomes |
| §4.5 prospective matchup capture | implemented | Fail-closed schedule gate; stale offseason samples correctly rejected |
| §4.4 Advanced Receiving as the one remaining family | executed | **Decisive failure** — CRPS +0.17%, MAE +0.29%, both worse in all three folds with clustered CIs wholly unfavorable |

Roughly four immutable Cloud Builds and twenty-plus tracked Cloud Run
executions in two days. Zero production changes. The operator's read that this
has not been successful is correct.

---

## 2. What I got wrong

**The headline number was an artifact and I over-weighted it.** I reported the
production tail as "≈2.7× too thin at q99, z≈20" and called it "the largest
well-powered defect in the system." That measurement was taken on the
component-composed path. I flagged the caveat that the shaper and market blend
sit downstream — and then led with the uncorrected number anyway.

The served path, measured properly, is q90/q95/q99 exceedance of
10.5794%/5.4627%/1.4774%. The defect is real and statistically distinguishable
from nominal, but it is roughly **1.5×** at q99, not 2.7×. In quantile terms
that is a 2.5% widening. A 2.5% intervention was never going to move a
240-point threshold, and I should have said so before the Stage B replay was
launched rather than after. The reconciliation's qualification was correct on
every point it raised.

**I also implied a better gate would rescue real effects.** It did the
opposite. Advanced Receiving under the new all-row gate failed with tight
confidence intervals (CRPS +0.004926, CI +0.001829 to +0.008059; MAE +0.011640,
CI +0.005517 to +0.017644) where the old 30-point Brier would have reported
"effectively unchanged" (0.01407425 → 0.01407660). The better gate was worth
adopting, but its effect was to convert ambiguous nulls into confident nulls.
That is genuinely useful and it is not what I was hoping for.

---

## 3. What was actually learned — and it is not nothing

**3.1 The served distribution is close to correctly calibrated.** After the
shaper and the 45/55 blend, q90/q95/q99 land at 10.58/5.46/1.48 against
10/5/1. That is a good result for the system and it definitively closes
"our tails are too thin" as an explanation for the scoring gap. Before this
diagnostic that was an open hypothesis carried in two separate review
documents. It is now closed for the cost of one execution.

**3.2 The Stage B null is mechanistically informative, and this is the most
valuable thing in the whole sequence.** Widening every player's tail by 2.5%:

| threshold | 240 | 230 | 220 | 210 | 200 | 194 | 187 |
|---|---:|---:|---:|---:|---:|---:|---:|
| incumbent | 2 | 3 | 5 | 7 | 11 | 22 | 34 |
| factor 1.025 | 2 | 3 | 5 | **7** | **13** | 23 | 33 |

It moved the 200 count (+2) and moved **nothing at all** at 210 and above —
not by one week, in either direction, across 54 slates.

If the 210+ ceiling were limited by per-player marginal tail probability,
inflating every marginal tail would move it. It did not budge. **The binding
constraint at 210+ is not marginal — it is joint.** Combined with the standing
fact that selection already equals the pool oracle at 220/230/240, the
remaining problem is which players the simulator believes will boom
*together*.

**3.3 The marginal-projection layer is now close to exhausted.** Counting only
what has been tried against it: six vendor field families (route components,
same-season coverage, advanced passing, route shape, defense PROE, advanced
receiving), tail recalibration, TabPFN, ensemble variants, coherent
member-sampled worlds, Chronos. The single robust positive is that route share
improves the projection's *centre* (composed MAE and CRPS better in every fold)
— and even that did not improve the tail.

Meanwhile every dependence mechanism tried — Schaake, forest-learned
conditional templates, the entire Gumbel family — shares one property: they
**permute or shock ranks over marginals that are already fixed**. None of them
can create the event "one receiver absorbed 14 targets this week."

---

## 4. Revised direction

Priors should be lower across the board now. I am not going to present these
with the confidence of the earlier documents.

### 4.1 The one structurally untested mechanism: within-team allocation variance

This was §3.4 of the first strategy review and it has never been run. It is the
only dependence mechanism in the class the failures do *not* cover: it is
**allocative** (it changes how a drawn team total is divided among teammates)
rather than **permutational** (it rearranges fixed values).

Concretely: draw per-world team target-share vectors from a Dirichlet centred
on the projected share vector with concentration fit from historical
week-to-week share dispersion; draw TD allocation multinomially over
red-zone-weighted shares conditioned on the already-drawn team touchdown count;
carry rush-attempt share similarly. The Dirichlet mean equals the projected
share vector, so **team-level marginals are preserved by construction** — the
same invariance property that made Schaake and the forest scientifically clean.

Gate it on the metrics the forest failed (pair-weighted variogram, joint-q90
tail Brier) plus one the prior gates lacked and which is the direct target:
**the realized frequency of "≥2 players from one team simultaneously above
their own q90," against the historical rate.** Section 3.2 predicts the current
simulator under-produces that statistic; if it does not, the mechanism is dead
before any lineup work and the check is cheap.

Honest prior: moderate, and lower than I would have assigned two days ago. But
it is the one remaining item with a mechanism that matches the diagnosis, and
the diagnostic is a distribution check, not a lineup panel.

### 4.2 The objective, not the beliefs

Also from the first review (§3.1), also untested. Every arm for two days has
tried to improve *beliefs*. Nothing has tried to change *what is being
optimized*. The selector maximizes world coverage at a fixed 194 in contests
whose min-cash is ~169 and first place ~247; there is no field model, no
duplication model, and no payout curve anywhere in the objective.

The calibrated contest-aware ownership model already passed its gate (MAE 2.87,
Spearman 0.79) and is used only as a fade coefficient. Its natural use is as
the marginal of an opponent-lineup generator, validated against co-ownership
and the 68 known winner rosters — a gate that never touches the 107 slates.

This is the largest build in either document and I am no longer confident it
pays. But it is the only proposal that is not another belief experiment.

### 4.3 The option that deserves explicit consideration: stop

After this many well-run nulls, "the historical panel is exhausted" is a
legitimate conclusion rather than a failure to find the right lever. The
prospective infrastructure is now built and frozen: the 2026 route shadow with
a proper gate, the weekly append path, the fail-closed matchup collector, the
eleven-book selector policy, and the standings-collection workflow.

A defensible plan is to bank `classic-k1-ce12-role12-boom28-v2`, spend nothing
further on historical arms, and let Week 1 through Week 4 of 2026 generate
genuinely independent evidence — particularly the full contest standings, which
are the one input the system has never had and which unlock 4.2. The cloud
spend saved is real, and the marginal information from a twelfth historical
arm is demonstrably near zero.

I would rank this **above** 4.2 and roughly level with 4.1.

---

## 5. What should not happen

- No retry of any closed family under a different window, support floor, field
  subset or model. Six have closed; the pattern is not "wrong hyperparameters."
- No second recalibration factor. Stage B's null was a clean answer to a
  well-posed question.
- No further historical vendor collection. The redundancy audit already showed
  the remainder is 0.5–0.99 correlated with existing inputs, and the two
  least-redundant families have now both failed.
- No treating the Stage B 200-point gain (11→13) as a lever. It tied everywhere
  that governs and declined at 187 and on the mean.

---

## 6. Summary

The recommendations were executed faithfully and competently. Two produced
clean negative answers that genuinely closed open questions, one produced a
better measurement standard that immediately proved its worth by making a
rejection unambiguous, and one — the tail defect — rested on a number I should
have qualified before it was acted on rather than after.

The most useful output of the two days is the Stage B null: **inflating
marginal tails moves the 200 count and does not touch 210+, which says the
remaining ceiling is joint rather than marginal.** That is the first direct
evidence for a claim both earlier reviews asserted without proof, and it should
govern whatever is attempted next — or whether anything is.

---

## 7. New measurement: the shape of the co-boom structure

> **Outcome-viewed.** Everything in this section queried realized 2019–2025
> outcomes on the corrected panel `20260810-lockfix-e80-k1-8677d21`. It is
> hypothesis-generating and target-setting only. No threshold, position slice
> or dose below may be adopted without prospective preregistration.

Section 3.2 established that the constraint is joint. This section measures
*what shape* the joint structure actually has, because "add more dependence" is
not an actionable instruction.

Method: flag each player-week where `actual > proj_p90` — i.e. exceedance of
the model's own 90th percentile — over QB/RB/WR/TE rows with
`mean_projection >= 4`. 18,092 player rows, 2,405 team-weeks with ≥3 qualifying
players. Marginal exceedance rate 8.53%.

### 7.1 Team-level multiplicity versus independence

| event | observed team-weeks | independent expectation | ratio | z |
|---|---:|---:|---:|---:|
| ≥2 teammates exceed | 316 | 316.0 | **1.00** | 0.0 |
| ≥3 teammates exceed | 66 | 54.5 | 1.21 | 1.6 |
| ≥4 teammates exceed | **14** | 6.5 | **2.17** | **3.0** |

Reality has essentially **no** pairwise excess over independent marginals, but a
genuine fat tail at four-plus simultaneous exceedances. The 240-point weeks live
in that last row.

### 7.2 The dependence is star-shaped through the QB

Conditional on the team's QB exceeding his own p90:

| teammate | exceed rate given QB boom | given QB no-boom | lift |
|---|---:|---:|---:|
| TE | 26.72% (n=116) | 10.69% | **2.50×** |
| WR | 22.12% (n=330) | 9.47% | **2.34×** |
| RB | 9.82% (n=224) | 7.52% | 1.31× |

### 7.3 …but same-position teammates are independent or mildly negative

| pair | pairs | P(B exceeds \| A exceeds) | P(B \| not A) | lift |
|---|---:|---:|---:|---:|
| WR–WR | 8,391 | 10.67% | 10.76% | **0.99×** |
| RB–RB | 3,401 | 7.66% | 7.26% | 1.05× |
| TE–TE | 614 | 7.81% | 9.82% | 0.80× |

Independent corroboration from published ceiling-correlation work, which
computes correlations rather than exceedance lifts but agrees on sign and
ordering: WR1–WR2 +0.16, WR1–RB1 +0.01, TE1–WR1 +0.02, TE1–WR2 −0.04,
RB1–WR2 −0.11 at ceiling outcomes; bring-back WR1 to opposing WR1/WR2 +0.09 /
+0.10.

### 7.4 Why this matters mechanically

The production simulator couples players through **one shared mean-preserving
multiplier per game** (possession sim → `game_factor_matrix`). That
construction can only produce **uniform positive pairwise correlation among all
players in the game.** It structurally cannot produce §7.2 together with §7.3.

The observed pattern has a clean two-force explanation:

- **Shared volume (+):** when a team throws more and better, everyone's
  opportunity rises. This is the force the current multiplier models.
- **Competitive allocation (−):** conditional on team passing volume, receivers
  split a fixed pie. One receiver's 14-target game is another's 3-target game.
  This force is **entirely absent** from the current simulator.

WR–WR at 0.99× is the signature of those two forces cancelling. A model with
only the first force must over-correlate WR–WR, and — because it spends its
dependence budget on uniform pairwise coupling — under-produce the extreme
multiplicity in §7.1 that actually generates 240-point lineups.

**This is now a mechanistic derivation of the allocation-variance proposal
(§4.1) rather than an assertion.** The Dirichlet allocation layer supplies
exactly the missing negative force, and it does so while preserving team-level
marginals by construction.

---

## 8. Additional suggestions

### 8.1 Run the co-exceedance diagnostic on simulated draws — cheapest next test

§7 gives target numbers measured from reality. The matching statistics have
never been computed on the simulator's own output. Compute, on simulated draws
for the same 2,405 team-weeks:

1. the ≥2 / ≥3 / ≥4 team-week multiplicity ratios against independence;
2. the QB→WR / QB→TE / QB→RB conditional exceedance lifts; and
3. the WR–WR / RB–RB / TE–TE same-position lifts.

Predicted failure mode, stated **before** running it so it is falsifiable: the
simulator will show WR–WR materially above 1.0 (reality: 0.99), QB→WR below
2.34, and ≥4 multiplicity below 2.17.

If that prediction holds, the dependence graph is mis-shaped and §4.1 is the
indicated repair. If the simulator already reproduces all six statistics, then
the joint hypothesis is wrong too, the constraint is somewhere neither review
has identified, and §4.3 (stop) becomes the clear answer. **Either outcome is
decisive and it costs one execution with no new data and no lineup panel.**

This should run before anything else in this document.

### 8.2 Make co-exceedance a standing panel diagnostic

Whatever the answer, these six statistics should be emitted by every future
panel alongside the leakage checks. They are cheap, they are the direct
signature of the mechanism that governs the 210+ threshold, and their absence
is why a mis-shaped dependence graph could persist through 120 addenda.

### 8.3 The right use of the Fantasy Points data is as the allocation denominator

Route share has now failed twice as a **marginal** feature — the component test
(tail gate) and Advanced Receiving (CRPS/MAE/pinball). But an allocative model
needs exactly what it supplies: **who was on the field running a route, and how
often.** Route share is the natural denominator for the eligible-receiver set,
and target share among that set is the Dirichlet quantity.

That reframes the purchase. The data was tested where it does not help (as
another predictor of one player's mean) and has not been tested where it is
structurally the right input (as the participation weight in a joint
allocation). This is a genuinely different mechanism, not a retry of either
closed arm, and it should be stated that way in any preregistration.

Concretely, the concentration parameter for the Dirichlet can be fitted from
observed week-to-week dispersion of target shares **within the route-running
set**, which requires route share weekly — the one vendor series that exists.

### 8.4 Fit the allocation concentration per team, not globally

Offenses differ persistently in how concentrated their target distribution is.
A single global concentration parameter would reproduce league-average
dispersion and miss both the hyper-concentrated offense (where one receiver's
ceiling is enormous) and the committee offense (where nobody's is). Fit
concentration walk-forward per team with shrinkage to the league mean, using
the same support-aware pattern the project already applies elsewhere.

### 8.5 Two construction observations — prospective only

- **TE lift (2.50×) exceeds WR lift (2.34×)** conditional on a QB boom. If real,
  QB+TE stacks are mildly underrated relative to QB+WR. But n=116 TE instances,
  the difference is well inside noise, and this is outcome-viewed. It is a
  prospective shadow question at most, not a construction change.
- **Bring-back is supported but weak** (+0.09/+0.10 published, WR to opposing
  WR). The incumbent QB+2+bring-back rule is consistent with the evidence. No
  change indicated.

### 8.6 What §7 does *not* license

- No stacking-rule change, position quota, or salary rule derived from these
  numbers on the 107 historical slates.
- No claim that fixing the dependence shape will produce 240-point weeks. §7.1
  says the event is 14 team-weeks in 2,405; correctly modelling its frequency
  raises the probability that generation finds one, and nothing more.
- No reopening of any closed marginal arm. §8.3 is a joint-model input, and it
  must be gated on joint statistics, not on another 30-point Brier test.
