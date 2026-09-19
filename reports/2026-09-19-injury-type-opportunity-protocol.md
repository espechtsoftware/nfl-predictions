# Injury-type incremental opportunity screen

This is one new exploratory development test of information, not a lineup
selection change. Freeze the implementation and complete its synthetic checks
before opening target labels for this study. Root owns the first read; the
workstation independently reruns the frozen reader before a ledger entry.

## Question and input support

Does the reported injury type add information about **target counts conditional
on playing**, beyond the existing model inputs, designation, practice and recent
role? This tests one part of active-but-limited opportunity forecasting. It does
not equate low targets with a medically limited player or infer a causal injury
effect. It does not estimate a full opportunity distribution or a 220+ lineup gain.

The outcome-blind census finds 33,802 Sunday-daytime RB/WR/TE player-weeks with
prior snap share at least .20 and at least one prior game in 2014–2024. Of 7,104
admissible injury reports, 7,102 have a primary injury type; 1,887 of 1,888
Questionable rows have one. No joined designation disagrees with the frozen
feature table. [Census and hashes](reviews/evidence/2026-09-19-injury-type-support.json).
This follows the finding that daily historical practice trajectories are absent;
it does not reconstruct such trajectories from final weekly reports.

Safe covariate extract SHA256
`842fa31c6f20e635593d59772cf0aafd9b1e81ff56c97e3261580da4e0874393`.
The historical feature/label panel is the already authenticated control panel,
SHA256 `445de23a683c17437723c98f4619296f742d13f5843bcb90a77b97af88308419`.
The support census did not open `was_active` or `y_targets` for this test.

## Fixed comparison

Both arms predict the same target mean with a Poisson-loss histogram gradient
boosting regressor: 100 iterations, learning rate .05, 7 leaves, minimum leaf size 30, L2=10,
no early stopping, max features 1.0 (all features), seed 20260919. No hyperparameter search.

The control uses the 41 numeric fields recorded in the support receipt: every
current standard numeric model input plus prior targets, practice/trend, missed
games and recent target/snap shares. It also uses position, designation and
report-presence indicators. Native missing-value handling is retained. These are
fresh matched research regressors, not an exact replay of the served component
model; an incremental gain here would still need a served-model ablation.

Treatment adds only fixed multi-hot flags from the primary report injury, falling
back to primary practice injury when absent: knee, ankle, hamstring, shoulder, foot,
hip, concussion, illness, groin, back, calf, quadricep, thigh, toe, rib, neck, wrist, hand,
non-injury-related, plus other named type and missing type on a reported injury.
Substring matching permits multiple named sites. No severity or medical-effect
weights are supplied. These categories are selected from input vocabulary only.

## Temporal and cohort contract

Evaluate 2019, 2021, 2022, 2023, 2024. Each fit uses only earlier seasons from 2014
onward, including 2020 when it is prior. Neither 2025 nor 2026 enters this study.
Use regular-season Sunday games with Eastern kickoff from 13:00 through before 19:00.
Every admitted injury was source-modified before the common Sunday-main lock.
Thursday/Monday players are excluded from fitting and evaluation, preventing a
post-Thursday report from masquerading as a pregame predictor.

Eligibility is RB/WR/TE, prior snap share >= .20, prior games >= 1; it does not depend
on that week's outcome. Fit on eligible earlier rows with `was_active==True` and
known nonnegative targets. Predict **all** eligible target-year rows before loading
their labels. Score the conditional-on-playing estimand on active rows only;
count all missing activity/target labels explicitly, never impute zeros. This is
not a new P(active) estimate or an assumption that a questionable player will play.

## Primary, safeguards and routing

Primary is treatment minus control **mean Poisson deviance among active
Questionable players**, averaged within slate, then equally across the five
evaluation seasons. Lower is better. Require at least 30 scored Questionable
rows and at least two supported slates per year; otherwise stop as insufficient
support without redefining the cohort.

Report a 10,000-replicate paired slate bootstrap within each year, seed 20260919,
holding the fitted models fixed. Report all yearly differences, row/slate support,
position/practice summaries, target-mean bias and mean absolute error. Secondary
is identically balanced deviance across all active eligible players, including
those without a designation. No injury-type subgroup is a separate efficacy hunt.

Nominate only for a separately frozen served-model/opportunity-law follow-up if
the primary 95% upper bound is below zero **and** all-active pooled deviance does
not worsen. Report season instability candidly; do not silently add a different
season veto or change the operator's aggregate-utility preference. If the gate
fails, close this fixed method with no injury-category/model-capacity search on
these outcomes. Passing does not authorize entering different lineups.

Synthetic verification covers the complete forecast/read path, known informative
injury signal, the exact deviance formula, missing outcomes and refusal of
target-season training labels. Forecasts and receipts must be published/authenticated
before the evaluation read. Use one CPU in Cloud Build, smoke before full run,
timeout 30 minutes; no shared Cloud Run job or warehouse writes. The historical
panel has already been studied, including target labels in the prior-support test:
this is development evidence with one new primary, not independent confirmation.
