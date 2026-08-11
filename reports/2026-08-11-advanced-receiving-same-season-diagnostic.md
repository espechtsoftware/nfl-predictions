# Frozen same-season Advanced Receiving diagnostic

Frozen 2026-08-11 CDT after the outcome-blind support/redundancy audit and
before querying any target-week outcome for this family. This is the one
historical Advanced Receiving diagnostic permitted by the post-window review.
There is no feature, support, window, model, fold or threshold retry.

## Population and point-in-time contract

- Source manifest and plan hash must match the support audit exactly.
- Positions are WR and TE only. Seasons are 2022--2025 and target weeks are
  5--18. Every source window ends at target Week W-1.
- Walk-forward evaluation folds are 2023, 2024 and 2025. Each fold trains only
  on earlier seasons beginning with 2022.
- The evaluation population is every research-eligible WR/TE with a finite
  accepted mean projection. A row is vendor-supported only when the cumulative
  export resolves to its GSIS id, has at least 20 routes, and all three frozen
  metrics below are finite. Unsupported rows remain control/fallback rows and
  are reported; they never receive a fabricated vendor value.

## Frozen feature and shrinkage law

The only treatment fields are TPRR, YPRR and XFP per route. aDOT, air-yard
share and first-read rate are excluded by the outcome-blind redundancy result.

For a supported player, each field starts at its cumulative-prior value. At
target Week 6 or later, when the matching last-four value and route count are
finite, use:

`blend = (1 - w) * cumulative + w * last_four`, where
`w = min(last_four_routes / 80, 1)`.

There is no learned blending coefficient, prior-season fallback, metric-
specific weight, alternate route floor or position-specific rule. The fixed
20-route cumulative floor preserves the support demonstrated by the audit;
the 80-route recency scale prevents four-game noise from receiving full
weight. Week 5 uses cumulative Weeks 1--4 alone.

## Frozen models and distributions

Control and treatment use the same supported training/evaluation rows. The
control numeric columns are the existing registered paid-data diagnostic
controls: mean projection, salary, target-share last/jump, snap-share
last/jump, team vacated target share, depth rank and games played prior, plus
position one-hot encoding. Treatment adds exactly the three blended fields.

For each fold and arm:

1. Fit the existing standardized median-imputed Ridge residual model with
   `alpha=10` to `actual - mean_projection`.
2. Fit the existing standardized LogisticRegression models for 20- and
   30-point events with `C=0.1`, `lbfgs`, `max_iter=2000`.
3. Build a deterministic 1,000-member predictive ensemble by adding the fitted
   residual correction to the accepted mean and the 1,000 equally spaced
   empirical quantiles of that arm's in-sample training residual errors,
   separately for WR and TE. A position cell with fewer than 200 rows falls
   back to the combined WR/TE residual distribution. Seeded random sampling is
   forbidden.

This is an auxiliary scientific diagnostic, not a production model. Both arms
must have identical fold/player keys and finite output. No candidate or lineup
score is read during this stage.

## Metrics, uncertainty and frozen gate

Report by fold, position and aggregate:

- empirical-ensemble CRPS on every supported row;
- mean absolute projection residual;
- q90/q95/q99 pinball and exceedance calibration;
- 20/30-point Brier and event counts;
- target-universe and supported-row counts; and
- paired week-clustered 95% intervals for every arm delta plus the two-sided
  alpha 0.05 / 80%-power minimum detectable effect, using the observed weekly
  paired-difference SD and `1.96 + 0.842` standard errors. Use 10,000 cluster
  bootstrap resamples with seed `20260811`. Intervals and MDE are mandatory
  reporting, not a restored significance veto under the operator's tail-first
  policy.

The diagnostic passes only if all of these hold:

1. at least 6,000 supported evaluation rows and 100 realized 30-point events;
2. aggregate treatment CRPS is at most 99.5% of control;
3. equal-fold-weighted treatment q95/q99 pinball is at most 99.5% of control;
4. aggregate q95 and q99 absolute calibration error each worsen by no more
   than 10%;
5. aggregate 30-point Brier worsens by no more than 1%, and no fold worsens by
   more than 2%; and
6. aggregate residual MAE does not worsen.

Failure closes this exact family. Passing licenses one separately frozen
exact-80 candidate/lineup consequence using the same three-field signal; it
does not directly alter production. The eventual production path would still
require a 2026 prospective shadow.
