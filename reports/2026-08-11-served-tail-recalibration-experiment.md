# Served-tail recalibration experiment

Status: frozen on 2026-08-11 CDT before any recalibrated quantile, loss,
candidate, lineup or realized-score result was generated.

## Motivation and separation from the diagnostic

The separately frozen final-path diagnostic reproduced all 13,876 active
accepted 2023--2025 RB/WR/TE rows and every persisted post-shaper and
post-market mean. Its aggregate realized-score exceedance rates were
10.5794%, 5.4627% and 1.4774% at served q90, q95 and q99. All were above
nominal, and q99's week-clustered 95% interval was 1.2526%--1.7021%. That
passes the preregistered defect gate and licenses exactly one historical
mean-invariant recalibration experiment.

This document chooses the correction, fit sample, dose and gates before any
corrected output is read. The known 2023--2025 control diagnostics may not be
used to choose among factors. There is no position, salary, projection,
route-share, market-coverage or player-identity segment, and no second
correction family or retry.

## Frozen correction family

Use one global positive spread multiplier `s` for every active RB, WR and TE.
Apply it after the full fitted-widening plus TabPFN/empirical shaping and after
the 45/55 model/prop-market mean blend:

`corrected_draw = row_mean + s * (served_draw - row_mean)`

QB and DST draws remain byte-identical. Do not clip corrected skill-player
draws; clipping would move the row mean. Require maximum absolute row-mean
change below `1e-10`. Apply the same factor to baseline and alternate
role-belief skill-player worlds. This changes spread only: model inputs,
point projections, market means, correlations, simulation ranks, seeds,
candidate budgets, constraints, selector, tail line and final entry count do
not change.

The only runtime lever is `SERVED_TAIL_SCALE`. Blank, `0` and `1` are the
identity. A non-identity value outside `[1.000, 1.250]` must fail closed. The
live production policy stays at identity unless both stages below pass.

## Frozen fit sample and factor selection

Fit the single factor only on final served-path out-of-fold draws from the
accepted corrected K=1 panel for seasons 2019, 2021 and 2022. Use active
Sunday-main RB/WR/TE rows, exact accepted row keys and actuals, 10,000 worlds,
K=1, the production possession/asymmetric-team simulator, fitted widening,
TabPFN marginals with the normal empirical fallback, full shaping and the
honest common-lock 45/55 market blend. These seasons precede every evaluation
season. Fail closed on missing accepted keys, non-finite outcomes, fewer than
three calibration seasons or any replay/accepted mean difference above
`1e-4`.

Evaluate exactly 51 candidate factors `1.000, 1.005, ..., 1.250` on the
calibration rows only. For each season and each of q95 and q99, compute mean
pinball loss and divide it by that season/quantile's identity-factor loss.
The fit objective is the unweighted mean of those six ratios, so seasons and
the two upper-tail levels receive equal weight. Select the smallest factor at
the exact minimum (floating comparisons use absolute tolerance `1e-12`). No
2023--2025 outcome or corrected metric participates. If the fitted factor is
`1.000`, stop with `calibration-does-not-support-widening` and do not create a
lineup treatment.

Persist the 51-row objective curve, the selected factor, calibration row and
slate counts, coverage, control/corrected q90/q95/q99 exceedance and pinball,
CRPS, 20/30-point Brier, and maximum mean delta. The curve is an audit of this
one predeclared fit, not permission to select another factor later.

## Stage A: untouched 2023--2025 distribution gate

Apply the one fitted factor to the exact 13,876 rows and same 10,000 final
worlds used by the completed diagnostic. Report paired control/treatment
metrics by season, position and aggregate, plus week-clustered uncertainty
for row-level loss differences. The stage passes only if all mechanical
guards pass and, in aggregate:

1. absolute q99 calibration error improves by at least 25%;
2. absolute q95 calibration error strictly improves;
3. absolute q90 calibration error does not worsen by more than 0.0025;
4. the equal-weight mean of the six season/q95-q99 treatment-to-control
   pinball ratios is at most 1.000;
5. empirical CRPS worsens by no more than 0.5%;
6. 20- and 30-point Brier loss each worsen by no more than 1%; and
7. every corrected skill-player row preserves its served mean within
   `1e-10`.

Point MAE must be reported and should be identical apart from floating error,
but it is not an independent gate because the transformation preserves every
mean by construction. Position and season slices are diagnostics; they may
not choose a different factor. Failure closes this exact recalibration with
no lineup replay and no parameter retry.

## Stage B: frozen lineup test

Only a passing Stage A licenses one replay treatment on evaluation seasons
2023--2025. Its source is the accepted corrected direct-role incumbent
`20260810-lockfix-e80-k1-role12union-8677d21`. Reproduce the incumbent K=1,
12 role candidates, 40 boom candidates, line-194 greedy coverage selector,
same seeds and exactly 80 final entries, changing only the fitted
`SERVED_TAIL_SCALE` on RB/WR/TE worlds. The historical 2019/2021/2022 source
books remain unchanged; combine them with treatment 2023--2025 books only for
the complete 107-slate summary.

Mechanical validity requires all 54 evaluation slates, exactly 80 unique
selected legal lineups per slate, complete authoritative labels, identical
player keys/means/seeds/configuration apart from the declared scale, and a
live-path parity test proving that the production helper applies the same
transformation. Candidate rosters and simulated support are allowed to
change; actual scores for a roster shared by source and treatment may not.

Compare complete-book selected weekly maxima at 240, 230, 220 and 210 in that
order. At the first difference, treatment passes only if its count is higher;
it must improve at least one 210+ threshold. A tie through 210 is neutral and
does not replace the incumbent. Counts at 200/194/187, mean/median, season
slices, changed weeks, candidate-pool oracle and generator provenance are
mandatory diagnostics but not vetoes. Any loss at a higher threshold than a
gain rejects automatically; any other mixed high-threshold result requires
operator review under the standing tail-first law.

Only a treatment passing both Stage A and Stage B may update the live policy.
No result from this experiment reopens a closed Fantasy Points feature arm.
