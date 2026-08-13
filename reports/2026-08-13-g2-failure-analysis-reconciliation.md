# Reconciliation of the G2 failure analysis and ledger proposal

Date: 2026-08-13. This reviews
`reports/2026-08-13-g2-failure-analysis-and-next-mechanism.md` against the
validated G2 report, current simulator code and historical arm ledger. No
scientific result is produced here.

## Decision

Accept the proposed TD-ledger mechanism for one new **score-free** evaluation
against the current final-served finite-K incumbent, after the already-running
effective-rank diagnostic. This is not a G2 theta retune and it does not revive
the old TDLEDGER2 lineup result. A score-free pass would only license a newly
frozen exact-80 comparison; it would not promote the ledger directly.

The valid old TDLEDGER2 result (19 versus 27 >=194 weeks) remains material
negative prior evidence. Its lineup verdict does not answer the new question,
because it predates the active-only TabPFN cache, walk-forward served-position
calibration, accepted finite `K=28.154043586960896`, and G0/G1 scorecard. The
old isolation tests proved coupling and mean preservation but never measured
the current final-served QB-WR/WR-WR dependence error.

## Findings accepted

- G2 was informative rather than vacuous. It moved joint-q90 Brier and
  variogram with paired-slate intervals wholly below zero and cut held-out
  QB-TE absolute log error from `0.787420` to `0.307184`.
- `theta_WR=1.0` means the selected G2 treatment did exactly nothing to WR
  ranks. The held-out QB-WR lift/error therefore remained exactly unchanged.
- A monotone shared QB-root factor creates a real structural tension: loading
  multiple WRs toward the same QB root also tends to couple those WRs to one
  another. That is poorly aligned with the observed combination of very large
  QB-WR lift and near-neutral WR-WR lift.
- The existing TD ledger is a distinct mechanism class. It draws one
  `(game, team)` passing-TD count and allocates the identical event total to
  passers and catchers while preserving player marginal means. Its ranks
  survive the current TabPFN marginal remap, so the mechanism can reach the
  final-served copula.
- A TD-only repair is deliberately partial because shared passing yards and
  receptions remain uncoupled. Any yardage/reception ledger would be a later,
  separately frozen mechanism—not an automatic continuation selected after
  viewing this test.

## Corrections

### The impossibility claim is directional, not absolute

The simple one-factor proof assumes independent residuals. G2 does not:
receiver innovations inherit the incumbent finite-K allocation dependence.
In principle, negative/competitive residual dependence can offset a positive
shared factor. The calibration grid shows that this particular context-free
Gumbel overlay could not activate WR on the registered objective; it does not
prove that every factor model or every per-player loading is mathematically
incapable. We still decline those variants because the held-out result gives
no outcome-independent way to choose their extra flexibility.

### Multinomial competition does not remain negative after Poisson thinning

In `_td_event_ledger`, the team TD total is Poisson and fixed-share receiver
allocation is multinomial. Conditional on a fixed total, receiver counts are
negatively related; after marginalizing a Poisson total, Poisson thinning makes
the receiver counts independent conditional on the game multiplier. The
shared random game multiplier then adds positive covariance. The ledger's
falsifiable advantage is therefore narrower: it can add exact QB-catcher
same-event dependence without the direct all-WR shared-root coupling used by
G2. It is not guaranteed to create negative WR-WR dependence.

### Effective rank is not a formal upper bound

The unresolved QB-receiver miss makes optimistic simulator-implied effective
rank plausible, but other covariance and lineup-overlap effects prevent a
mathematical upper-bound claim. Retain the registered wording: **likely
optimistic; not a formal bound**. If a later dependence mechanism is adopted,
rerun effective rank and report the direction empirically rather than requiring
it to fall by definition.

## Frozen design requirements for the ledger test

Before execution, a dedicated protocol must pin the accepted cache, position
schedule, finite K, seeds, control reproduction and exact TD-ledger code path.
The treatment changes only `TD_LEDGER=1`; its TD allocation remains the code's
existing fixed-share multinomial (`td_alloc_k=None`). Do not tune TD allocation
K, game-factor sigma, usage K or any marginal schedule.

The primary score-free gate must require:

1. exact player marginal draw multisets after final-served shaping, finite
   deterministic output, unchanged non-TD simulator configuration and exact
   G0/G1 control reproduction;
2. improved aggregate joint-q90 Brier and variogram p=0.5;
3. improved QB-WR absolute log error and improved registered G0/G1 aggregate
   errors;
4. WR-WR absolute log error not worsened beyond a predeclared numerical
   tolerance;
5. no material regression in QB-TE, RB-RB, multiplicity >=2 or multiplicity
   >=3; and
6. season and paired-slate bootstrap disclosures, with no lineup score query.

Because the mechanism was selected after examining G0/G1/G2 on 2023--2025,
label this evidence adaptive/retrospective even though the metric gate is
frozen before its treatment result. A pass licenses one exact-80 historical
comparison under the current incumbent, but production adoption should still
carry explicit overfitting disclosure and a 2026 prospective shadow.

Test the ledger alone first. Do not automatically compose it with G2's
`theta_TE=1.05`. If the ledger passes but leaves a specific QB-TE residual, a
separate composition protocol must be frozen before generating that treatment;
the failed G2 arm is not silently imported into the ledger.

## Sequence

1. Finish and harvest incumbent effective rank.
2. Freeze and implement the current-incumbent score-free TD-ledger evaluator.
3. Run exactly one immutable ledger treatment and apply the gate above.
4. On failure, close this mechanism without parameter or yardage variants.
5. On pass, freeze one exact-80 comparison before querying lineup outcomes.
6. Continue G3 participation-conditioned allocation work independently of the
   ledger disposition.
