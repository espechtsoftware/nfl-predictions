# Alternative ways of looking at the data

Date: 2026-08-12. Seven reframes that use data already in hand, ordered by
expected value. **No code was changed.** All are diagnostics or
evaluation-method changes, not new mechanisms.

The common thread: the system has looked at this data almost exclusively as
*per-player regression* evaluated by *threshold counting*. Both of those are
choices, and both have known weaknesses that other framings do not share.

---

## 1. Fit the weekly maximum with extreme-value theory instead of counting it

**This is the highest-value item and it fixes the problem that has broken almost
every adoption decision in this program.**

Every gate reduces to counting weeks above a line: `2/2/3/5/14/26/37`. At 240
the control count is 2 of 107. Adoptions have turned on single Bernoulli events,
and the review record is full of the consequences — Defense PROE closed on a
2.8-percentage-point equivalent, fitted-K adopted on one eval-panel week, Stage B
declared neutral where a positional effect existed underneath.

But the quantity being optimised is a **maximum over 80 entries**, and extreme
value theory is the exact mathematics of maxima. The weekly maximum of a large
sample converges to a generalised extreme value distribution; exceedances over a
high threshold converge to a generalised Pareto. You have **107 independent
observations of a maximum** — which is a perfectly ordinary sample size for
fitting a three-parameter GEV.

The reframe: stop counting `P(max ≥ 240)` and start *estimating* it.

- Fit a GEV to the 107 weekly maxima for control and treatment.
- Compare arms on fitted parameters (location, scale, **shape**) with
  bootstrap intervals, and on the model-implied `P(≥ 240)`, `P(≥ 250)`,
  `P(≥ 260)` — including thresholds never observed.
- The shape parameter ξ is the interesting one: it governs how fat the upper
  tail is, and it is estimated from *all 107 weeks*, not from the two above 240.

Consequences worth being explicit about:

- **Statistical power rises by roughly an order of magnitude.** Every week
  informs the tail estimate rather than only the exceedances.
- **You can evaluate above the observed range.** The recorded Millionaire first
  place was 246.82 and your maximum observed weekly best is 265.14. A fitted GEV
  gives a principled `P(beat 247)` rather than a count of zero.
- **It disciplines the tail-first law without weakening it.** The operator's
  objective is unchanged — you still care about the extreme — but "the fitted
  tail improved, ξ moved from a to b, with this interval" is a far stronger claim
  than "one more week crossed 240."

Caveats to preregister: the 107 maxima are not identically distributed (slate
size, scoring era, and the arm itself all vary), so fit with covariates or fit
per-season and pool; and a GEV fitted to maxima of a *selected* 80 is a
distribution of a selection outcome, not of a natural maximum — which is fine
for arm comparison but should not be over-interpreted physically.

Cost: small. This is a fit over a 107-row CSV that already exists
(`reports/2026-08-08-true80-weekly-max.csv` and its successors).

## 2. Count the effective number of independent bets in the book

The 80 entries are a portfolio, and portfolio theory's first question is not
"what is each entry worth" but "how correlated are they." The coverage selector
is a *proxy* for decorrelation — it maximises distinct covered worlds — but the
actual correlation structure of the 80 entry scores has never been computed.

Take the per-candidate score matrix from the persisted score artifacts, restrict
to the 80 selected entries, and compute the 80×80 covariance of entry scores
across the 10,000 worlds. Then look at its eigenspectrum and report the
**participation ratio** or effective rank: `(Σλ)² / Σλ²`.

The question that answers: **how many genuinely independent bets does an
80-entry book contain?** If the effective rank is 6, you are making six bets
eighty ways, and the marginal entry is nearly worthless — which would reframe
the entries-per-slate question entirely and would explain why the measured
entries curve flattens. If it is 40, diversification is working and more entries
is a live lever.

Follow-ons that fall straight out: which eigenvector dominates (usually "the
slate was high-scoring"), how much of book variance is that single common
factor, and whether the residual eigenvectors correspond to identifiable game
or stack theses.

Cost: small; the artifacts exist. Strikingly informative for its price.

## 3. Decompose outcome variance into player, team-game, opponent, and noise

Everything is modelled at the player-week level, which implicitly assumes player
identity is the right unit. The econometric framing asks how much of realized DK
variance is *attributable* to each level:

```
dk_points ~ player effect + team-week effect + opponent effect + residual
```

Fit as a crossed random-effects / variance-components model over 2019–2025.
Report the variance share of each component, by position.

This **bounds the whole enterprise**. If team-week effects carry, say, 40% of
the variance in WR outcomes, then which *games* you are in matters comparably to
which players, and game-level modelling deserves resources equal to player-level
modelling. If the residual is 70%, that is the irreducible ceiling and it should
be stated plainly in every future protocol as the denominator against which
"improved MAE by 0.03" is judged.

It also connects directly to G0: a large team-week variance component is the
statistical shadow of the QB-hub dependence G0 measured, and the two numbers
should be consistent. If they are not, one of them is wrong.

## 4. Invert the problem: distance-to-winner in belief space

Every miss analysis so far asks *whether* a winning player or roster was in the
pool. The more informative question is **by how much the beliefs were wrong**.

For each of the 68 known Millionaire winning rosters, solve: what is the minimal
perturbation to our pre-lock projections that would have made this roster the
optimizer's choice? A small LP or a direct computation of the gap to the
optimizer's objective at that roster.

Output per winner: a scalar "belief distance" in projection points, plus its
decomposition across the nine slots.

Why this is better than the existing audits:

- It converts "we missed him" into **"we were 4.2 points short on one player"**
  versus **"we were 1.1 points short on each of seven"** — two completely
  different failure modes requiring different fixes, currently indistinguishable.
- It gives a **continuous, well-powered** target across all 68 winners instead of
  a binary hit rate, so trends over seasons and positions become visible.
- It sizes the marginal-improvement path honestly: if the median belief distance
  is 15 points spread over six players, no realistic feature closes it, and that
  is decisive evidence for the dependence/objective path over the feature path.

## 5. Use ownership as a consensus forecast, not as an opponent

You hold 103,556 actual ownership rows over 1,258 contests and have used them in
exactly one way — as a fade coefficient, rejected twice.

Different lens: **the field's aggregate ownership is a crowd projection.** It
embeds thousands of independent forecasts plus the market's own information.
Treating it as a competing *estimator* rather than as an opponent gives:

- **A calibration instrument.** Where our projection rank and the ownership rank
  disagree, who is right, conditional on position, salary band and week? If the
  field systematically beats us in an identifiable cell, that is a directly
  actionable model deficiency — and it is measurable on 2022–2025 without any
  new data.
- **A free consensus baseline.** The acquisition doc has repeatedly weighed
  buying an independent projection source. Ownership *is* one, already paid for,
  for four seasons.
- **A leverage measurement that is not a fade.** Compute the realized ownership
  profile of the submitted book against the winners'. That tests the leverage
  premise the construction assumes, which has never been checked.

Note this is distinct from the rejected arms: those changed the *objective* with
a fade term. This changes nothing in production — it is a measurement of who
forecasts better.

## 6. Train and evaluate as ranking, not regression

The models are fitted with squared/quantile losses and judged by MAE, CRPS and
Brier. The decision they serve is **rank the slate, then select a subset**.
Those are different objectives, and the mismatch is a plausible contributor to
the six-arm pattern: a feature can improve MAE while leaving the within-slate
*ordering* unchanged, and ordering is what the optimizer consumes.

Two cheap steps before any modelling change:

- **Report within-slate rank metrics on every existing arm**: Spearman against
  realized, and NDCG restricted to the top-k that lineups actually draw from.
  These can be computed from artifacts already saved. It is entirely possible
  that some closed arm improved ranking while failing MAE, and nobody looked.
- If ranking metrics diverge from the loss metrics, a **listwise objective**
  (LambdaRank-style, slate as the query group) becomes a well-motivated
  experiment rather than a speculative one.

## 7. Ask what makes a *slate* winnable

All 107 slates are treated as exchangeable. Flip the unit: label each slate by
whether a 240+ lineup was *available in the pool at all*, and model that label
from pre-lock slate features — game count, implied totals, total dispersion,
weather, salary structure.

If winnable slates are predictable, the lever is **entry allocation across
slates and contests**, which no belief improvement can provide and which is
free to act on. Enter more where the ceiling exists, fewer where it does not.

Small n (roughly five to ten winnable slates), so this is hypothesis-generating
and belongs in the forensic program with an explicit power caveat — but it is
the only frame here whose payoff is operational rather than modelling.

---

## Suggested order

| # | frame | cost | why now |
|---|---|---|---|
| 1 | GEV on weekly maxima | small | fixes the decision-power problem blocking every gate |
| 2 | Effective independent bets | small | reframes entries-per-slate; artifacts exist |
| 6 | Rank metrics on existing arms | small | may re-read six closed arms at no experimental cost |
| 3 | Variance decomposition | small | bounds the enterprise; cross-checks G0 |
| 4 | Belief-distance to winners | medium | sizes the marginal path honestly |
| 5 | Ownership as consensus | medium | uses 103k unused rows a new way |
| 7 | Slate winnability | medium | operational lever, weakest power |

Items 1, 2, 3 and 6 are all small enough to run inside the end-of-program
forensic plan rather than as separate arms, and **item 1 should arguably be
adopted as a standing reporting requirement before the next gate**, since it
changes how every subsequent result is read.
