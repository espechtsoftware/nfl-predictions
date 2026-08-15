# Models and structures for *understanding* the corpus

Date: 2026-08-14. On what to train or build to understand correlations, missed
opportunities and trends in the forensic corpus — as distinct from improving
scores. **No code was changed.**

---

## 0. The framing matters, because it changes what is appropriate

Everything the project has built so far has been **predictive**: does this input
improve a forecast, does this mechanism improve a book. The question here is
**descriptive**: what is actually in this corpus, what did we leave in it, and
what patterns exist.

That distinction licenses tools that would be inappropriate as predictors. A
model with no deployment path can be arbitrarily flexible, because it is never
asked to generalise — it is asked to *summarise*. Overfitting is a
disqualifying flaw in a forecaster and an acceptable one in a descriptive
instrument, provided nothing downstream consumes its output as belief.

**The standing constraint holds throughout:** every one of these reads realized
outcomes, so all of it is hypothesis-generating. None of it may promote,
retune or reopen anything, and any lead must be confirmed prospectively.

---

## 1. Interpretability over a deliberately weak model — best first move

Train a gradient-boosted classifier on the candidate corpus to predict a binary
outcome — `actual_score >= 200`, or `is slate oracle` — from pre-lock features
only: `p_line`, `sim_mean`, `sim_sd`, `sim_q50/q90/q99`, `sim_rank_p_line`,
`salary`, `tag`, plus derived roster structure (games represented, largest team
block, stack shape, salary distribution, aggregate `own_est`).

**Do not deploy it. Read it.** Compute SHAP values over all ~300,000 candidates
and examine:

- which features carry any signal at all, and their direction;
- **feature interactions**, which is the part the existing rank-correlation
  census structurally cannot see. That census found `corr(sim-rank, regret)` at
  `+0.030` and concluded no gradient exists — but a marginal correlation of zero
  is entirely consistent with a strong interaction. "High `sim_q99` matters only
  when the slate total is high" would appear as zero marginal correlation and as
  a clear interaction in SHAP;
- where the model is *confidently wrong*, which localises the corpus regions
  where pre-lock belief and outcome diverge most.

Expect a weak model — AUC in the 0.55–0.62 range would be unsurprising given
what is already known. **That is fine and it is the point.** A weak model whose
weak signal is *legible* tells you where to look; the existing census told you
only that the marginal gradient is flat.

## 2. Subgroup discovery — the closest fit to "what should have been selected"

This is the technique most directly aimed at the question and it is
underused generally.

Rather than fitting a global model, subgroup discovery searches for
**conjunctive conditions under which the outcome deviates most from base rate**.
Beam search over feature conjunctions, scored by something like weighted
relative accuracy.

Applied to unselected candidates it answers, in plain language:

> *In what specific conditions did we leave value in the pool?*

with outputs of the form "`tag = lev` **and** salary < $47,000 **and** ≥ 5 games
represented **and** `sim_q99` in the top tercile — 4.1× the base rate of scoring
≥ 200, covering 3.2% of unselected candidates."

That is directly actionable in a way a global feature-importance ranking is not,
and it naturally surfaces the *conditional* structure the rank census missed.
It also fits the operator's stated question exactly: not "what predicts score"
but "what did we leave behind, and under what conditions."

Run it three ways: over all unselected candidates; restricted to unselected
candidates that outscored the selected best; and over the 33 winning
player-slots absent from the pool entirely.

## 3. Graph structure — descriptive, and this is where a graph genuinely helps

My earlier position stands: no graph database is warranted, and at ~2,000
players NetworkX in a job is sufficient. But for *understanding the corpus*,
graph structure earns its place in a way it does not for prediction.

**3.1 Player co-selection graph.** Build two weighted graphs over players:
edges weighted by co-occurrence across *all* candidates, and by co-occurrence
across *high-scoring* candidates. Then compare their community structure.

The interesting object is the **difference**: pairs that co-occur far more often
in high scorers than in the pool at large are combinations the generator
under-explores. That is a direct, interpretable answer to "what was in the
corpus that should have been selected," and it is a property of *combinations*
rather than players, which nothing in the current diagnostic set measures.

**3.2 Bipartite candidate↔player graph.** With candidates carrying
`actual_score`, compute player-level centrality restricted to high-scoring
candidates. Players who are structural *bridges* — present across many distinct
high-scoring constructions rather than concentrated in one — are the ones whose
absence costs most, and they are distinguishable from players who merely
appeared in one enormous lineup.

Both are cheap: sparse arrays or NetworkX, no new data, no database.

## 4. Low-dimensional embedding of lineup space — the picture

Represent each candidate as a sparse player-incidence vector (plus structural
features), reduce with UMAP, and colour by `actual_score`.

The question it answers is binary and important: **do high-scoring lineups
cluster, or are they scattered?**

- If they **cluster**, there is a region of lineup space the selector
  systematically under-visits, and that region is characterisable — which would
  be the single most actionable finding available from the corpus.
- If they are **scattered**, no selector or generator targeting helps, and that
  closes a family of ideas permanently with a picture rather than another arm.

Either answer is worth having, and unlike most items here the output is
inspectable by eye, which matters for a question about understanding.

Pair it with the existing effective-rank work: the eigenspectrum says how many
independent bets the book contains; the embedding says whether they are aimed
anywhere near where the winners live.

## 5. Trends over time — changepoints rather than regressions

`regime_and_drift_diagnostics` already covers regime cuts. The addition worth
making is **changepoint detection** on the weekly series — weekly max, weekly
regret, pool-oracle gap, calibration exceedance.

A regression on season tests whether drift exists; a changepoint test asks
*when* it happened and whether it coincides with a known code or data event. The
project's own history makes this valuable: the `(game, team)` allocation-unit
repair, the per-position calibration adoption and the active-label cache change
all have dates, and aligning detected changepoints against them separates
"the football changed" from "we changed."

---

## 6. What will not help

- **A large model to predict `actual_score` from features.** The signal is
  known to be near-zero at the margin, and 107 slates cannot support a flexible
  forecaster. §1 is different because it is read, not deployed.
- **A graph database.** Still unwarranted at this scale; §3 needs sparse arrays,
  not Cypher.
- **An LLM over the corpus.** Nothing here needs language, and the failure mode
  — confident, fluent, uncalibrated summary — is the worst possible one for a
  project whose whole discipline is calibration.
- **Deep generative models of lineups.** GFlowNet was gated out on its own
  cheap-diversity baselines; nothing since has changed that.

---

## 7. Suggested order

| # | item | cost | why |
|---|---|---|---|
| 1 | **Subgroup discovery** (§2) | low | most directly answers the question asked; outputs are sentences, not coefficients |
| 2 | **SHAP over a weak model** (§1) | low | exposes interactions the rank census cannot see |
| 3 | **UMAP of lineup space** (§4) | low | one picture that either opens or closes a whole family |
| 4 | **Co-selection graphs** (§3) | low | combinations, not players — the only diagnostic aimed at that unit |
| 5 | **Changepoint detection** (§5) | low | separates football drift from our own changes |

All five are local or single-job computations over data already in the
warehouse. None requires a new execution, a new panel, or an acquisition.

**And all five are outcome-viewed.** Their proper destination is the opportunity
register and the 2026 charter as *hypotheses*, never as adoptions — with the
same rule the forensic program already operates under.
