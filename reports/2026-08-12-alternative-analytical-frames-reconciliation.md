# Alternative analytical frames reconciliation

Date: 2026-08-12 CDT. This reconciles the operator-supplied
`reports/2026-08-12-alternative-analytical-frames.md` with the terminal
research program and the mandatory final-preseason forensic closure protocol.
The source review is retained unchanged.

## Bottom line

All seven frames are useful, but none may retroactively change a frozen arm
verdict. The strongest immediate additions are model-implied portfolio
effective rank/tail overlap and slate-relative ranking diagnostics. A paired
extreme-value analysis is also worth adding to future exact-80 reports, but as
a mandatory risk diagnostic rather than a replacement promotion gate. The
remaining frames belong in the outcome-aware final forensic program or the
prospective 2026 charter.

## Disposition by frame

| frame | disposition | required correction |
|---|---|---|
| Extreme-value model of weekly maxima | Add to future exact-80 reports and final forensics as a diagnostic | The 107 maxima are paired across arms, non-identically distributed across seasons/slates, and arise from correlated selected books. Do not claim an order-of-magnitude power gain or promote from an extrapolated return probability. |
| Effective independent bets | High-priority diagnostic | Compute per slate from the exact selected candidate-by-world score artifact. Report covariance- and correlation-based participation ratios plus tail-event overlap; label every result model-implied because G0/G1 show the current simulator misses QB-receiver tail dependence. |
| Variance components | Final forensic diagnostic | Freeze an identifiable hierarchy and distinguish central variance from upper-tail dependence. A team-week random effect is not itself proof of the QB-hub mechanism. |
| Belief distance to winners | Final forensic diagnostic | Define the norm, feasible roster universe, objective and candidate-versus-legal comparator before outcomes. Separate a player-support miss, construction miss and selection miss rather than calling every gap a projection perturbation. |
| Ownership as consensus | Start with a historical diagnostic; use prospectively when pre-lock projections exist | Actual ownership is observed only after lock and repeated contest rows are not independent forecasts. Aggregate to player-slate with contest/field weights, evaluate walk-forward, and never substitute realized ownership for a live pre-lock input. Fantasy Points projected ownership is the intended 2026 live signal. |
| Ranking rather than regression | High-priority diagnostic; a model arm only if the diagnostic licenses it | Use within-slate and within-position/salary-relevant ranks, top-tail relevance and slate-clustered uncertainty. Raw player NDCG does not reproduce salary, position and stacking constraints. Closed arms remain closed unless a standing downstream-change rule independently licenses revalidation. |
| Slate winnability | Low-power prospective lead | Freeze only pre-lock predictors and leave-one-season-out evaluation. A realized `pool >= 240` label is outcome-aware, positives are rare, and the operator normally chooses entry volume for one Sunday-main slate rather than among many simultaneous classic slates. |

## A1 — paired extreme-value diagnostic

The empirical `240/230/220/210/200/194/187` grid remains the registered
tail-first decision unless a future protocol changes it before either arm is
generated. For every future exact-80 comparison, add a separately labelled
EVT diagnostic with these safeguards:

1. fit and resample control/treatment as paired slate observations;
2. include a fixed season/slate-location treatment or standardized benchmark
   so one stationary GEV is not asserted over six different eras;
3. report location, scale and shape with paired slate-bootstrap intervals,
   leave-one-season-out fits and influential-week sensitivity;
4. report fitted probabilities only over a preregistered, modest threshold
   range and show empirical estimates beside them; and
5. fail visibly on non-convergence, boundary shape estimates or material
   sensitivity to one season/week.

The current active-label usage revalidation was frozen and launched before
this review. EVT may be reported afterward as an explicitly retrospective
diagnostic, but it cannot select that comparison.

## A2 — portfolio effective rank and tail overlap

The required data are genuinely present: every accepted slate has a
checksummed compressed score artifact containing the candidate-by-10,000-world
total matrix. For each exact selected 80-entry book, reconstruct the selected
artifact rows and report:

- covariance participation ratio `(sum(lambda))^2 / sum(lambda^2)`;
- the same measure on the correlation matrix so unequal lineup variances do
  not dominate the answer;
- variance share of the first five eigenvectors and their identifiable
  player/game/stack loadings;
- pairwise joint exceedance and overlap of covered worlds at the frozen tail
  lines; and
- marginal effective-rank/tail-coverage gain in nested 20, 40 and 80 books.

Run this first on the final incumbent and then on any passing G2 book. It is
descriptive under the current dependence law, not evidence that the real-world
book contains the same number of independent bets.

## A3/A4 — variance and inverse-belief forensics

Freeze the variance hierarchy before fitting. At minimum, distinguish stable
player, offensive team/game, game environment, opponent-defense and residual
components by position, with season/era sensitivity and bootstrap uncertainty.
Report ordinary variance and registered upper-tail event dependence
separately; their relationship is a cross-check, not an identity.

For inverse belief distance, use the corrected `H/P/C/S` opportunity layers
already fixed in the closure protocol. Only after identifying the first failed
layer should an inverse optimization report the minimum normalized L1 and L2
change in pre-lock player utilities needed to make the known winner optimal
within (a) the generated candidate set and, where tractable, (b) the full legal
roster universe. Preserve salary, position and stack constraints and expose
non-unique solutions. This is outcome-aware sizing, never a historical arm.

## A5/A6 — ownership consensus and rank skill

Historical actual ownership can answer whether the crowd's player-slate rank
contains information absent from the terminal pre-lock model. Collapse repeated
contest rows to a preregistered field-size-weighted player-slate estimate,
cluster uncertainty by slate, and compare model, ownership and their
disagreement walk-forward by position, salary band and active/support state.
Also compare the submitted book's ownership sum/product and empirical
duplicate classes where complete standings exist. Live use requires a
timestamped pre-lock ownership projection; actual ownership is never available
to the lineup decision at lock.

Add slate-relative player diagnostics to the final model census: Spearman,
top-tail average precision and NDCG with a preregistered relevance function,
reported within position and salary-relevant candidate strata. Also report
whether a marginal treatment changed the exact ordering consumed by candidate
construction. A future listwise arm is licensed only if these diagnostics show
a stable rank deficiency not already explained by the dependence stage.

## A7 — pre-lock opportunity regime

This is a restricted extension of the closure protocol's regime section. Use
only features available at the common lock: game count, market totals/spreads,
their dispersion, forecast weather, salary structure and projected ownership
concentration. The target may include full-universe, candidate-pool and
selected-book tail availability, but all models are exploratory, use frozen
bins or a tiny fixed specification, report leave-one-season-out behavior, and
cannot set 2026 entry volume until a prospective falsification rule is frozen.

## Execution order

1. Do not alter the running active-label usage comparison.
2. Add paired EVT as a diagnostic to the next not-yet-frozen exact-80 protocol.
3. After the final dependence law is known, run effective-rank/tail-overlap on
   the incumbent and any G2 treatment before interpreting entry-count value.
4. Add the corrected ranking and ownership-consensus analyses to the frozen
   final-preseason forensic run.
5. Run variance components and winner belief distance after the corrected
   `H/P/C/S` decomposition identifies the dominant layer.
6. Route only stable pre-lock slate-regime findings into a prospective 2026
   entry-allocation rule.

