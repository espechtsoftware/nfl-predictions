# Market-tail disagreement candidate experiment

Status: preregistered before querying player outcomes or current-policy lineup
scores for this experiment.

## Question and scope

Can the shape of DraftKings alternate-yardage prop ladders identify rare
player outcomes that the production marginal distribution prices differently,
and can that disagreement create a better 80-entry extreme-tail portfolio?

This is not a retry of `ALT_CEIL`. That arm added raw market ceiling room to
every optimizer objective and was validly rejected on the ensemble baseline.
The present mechanism uses the **signed, position-relative disagreement**
between the production and market tail spreads, only to generate twelve
additional candidate lineups. Every candidate is still scored and selected
with the incumbent production worlds. The earlier `DIV_TILT` mean-market arm
and generic q99 wildcard also remain closed.

The experiment uses only alternate prop rows already present in
`nfl_raw.prop_lines`; it spends no Odds API quota.

## Frozen point-in-time construction

The player diagnostic uses the mechanically accepted source snapshot
`20260809-e80-k1-ce12-c616390`. Its player features are invariant to the live
role-union panel and retain `research_eligible=true`. Only 2024 and 2025 are
eligible: all 18 corrected Sunday-main slates in each season have useful
alternate-ladder coverage. The four covered 2023 slates are reported but are
neither training nor evaluation data; 2019, 2021 and 2022 have no coverage.

For each season/week:

1. normalize prop and snapshot player names with the repository's canonical
   `norm_name`; drop an ambiguous normalized snapshot identity;
2. infer the common Sunday-main lock as the earliest `commence_time` among
   alternate-prop events containing a player in that accepted slate;
3. retain only DraftKings rows with `snapshot_ts < common_slate_lock`;
4. retain the latest such row for each player, market, point and outcome;
5. de-vig and monotonize the ladder with
   `inference.market_implied.implied_curve`, requiring at least three distinct
   points; and
6. use exactly one primary market per position: pass yards for QB, rush yards
   for RB, and receiving yards for WR/TE. This avoids summing independent
   rushing and receiving tails for dual-role players.

The common lock is deliberately stricter than each player's kickoff. A 4 p.m.
player may not use a prop snapshot collected after the 1 p.m. main slate
locked.

Convert market yardage quantiles to their monotone DraftKings component score:

- passing: `0.04 * yards + 3 * I(yards >= 300)`;
- rushing/receiving: `0.10 * yards + 3 * I(yards >= 100)`.

Frozen quantities are:

```text
production_upside = max(proj_p90 - proj_p50, 0)
market_upside     = component_points(q90) - component_points(q50)
raw_tail_edge     = production_upside - market_upside
tail_edge         = raw_tail_edge - median(raw_tail_edge within slate/position)
```

Position centering removes the known structural bias from comparing a total
fantasy-score distribution with one primary yardage component. It is done
once, without an outcome-fitted scale, clip, threshold or salary band.

The already-inspected availability-only audit found 1,576 covered player
rows in 2024 and 1,700 in 2025, with 35--128 and 41--118 per slate,
respectively. No `actual` value or candidate score was selected or summarized
to set this protocol.

## Frozen player-level mechanism gate

All models use identical covered rows. The target residual is
`actual - mean_projection`; tail targets are `actual >= 20` and
`actual >= 30`. The control numeric inputs are `mean_projection`, `salary`
and `production_upside`, plus one-hot position. The treatment adds only
`tail_edge`.

Fit on 2024 and evaluate once on 2025:

- residual regression: `Ridge(alpha=10.0)`;
- both tail classifiers:
  `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)`;
- training-fold median imputation and standardization for numeric fields;
  most-frequent imputation and unknown-safe one-hot encoding for position.

Also report, without fitting, the mean residual difference between the top
and bottom `tail_edge` quintiles within each season/position, aggregated by
rows. Report coverage, missingness, residual MAE, 20/30-point Brier loss,
calibration deciles and QB/RB/WR/TE plus WR/TE-only slices.

The mechanism passes only if all conditions hold:

1. both seasons contain all 18 slates, at least 1,500 covered rows, and at
   least 30 covered rows on every slate;
2. top-minus-bottom residual separation is positive in 2024, 2025 and their
   aggregate;
3. treatment strictly improves held-out 2025 30-point Brier loss;
4. treatment does not worsen held-out 2025 residual MAE or 20-point Brier by
   more than 1%; and
5. treatment does not worsen held-out 2025 WR/TE 30-point Brier by more than
   1%.

Failure closes this use of alternate-ladder disagreement. Do not tune the
market mapping, centering, model regularization, quintile, season set or gate
after seeing the result.

## Frozen candidate union if the mechanism passes

Only a passing player-level gate licenses one lineup experiment against live
policy `classic-k1-ce12-role12-boom28-v2`, panel
`20260810-e80-k1-ce12-roleunion-c616390`.

For each 2024--2025 slate, missing/invalid market edges are zero and covered
players receive the exact centered `tail_edge` above. Add twelve candidates:

- four sequentially banned optimizer solves using
  `proj_tourney + tail_edge`; and
- eight solves using the incumbent baseline draw worlds with the largest
  slate totals, adding the same player `tail_edge` to each world's optimizer
  values.

This is an added-budget union: preserve every source candidate and its
support/score, add exactly twelve `market_tail` candidates per covered slate,
then run the unchanged 194-world-coverage selector to return exactly 80
unique final lineups. Candidate scoring, support masks and selection all use
the incumbent K=1 production draws, not a market-adjusted scoring matrix.
The 2019, 2021, 2022 and 2023 books must reproduce the source exactly.

The mechanism audit must prove source containment, exact shared-candidate and
feature invariance, the frozen prop cutoff/mapping, exactly twelve realized
market candidates on every 2024--2025 slate, changed candidate support, and
exactly 80 legal unique selected entries per slate. A failure is invalid, not
a score verdict.

After mechanical validity, apply the current operator law in
`reports/2026-08-10-tail-first-adoption-review.md`: compare selected weekly
maximum counts at 240, 230, 220 and 210 from highest to lowest. The arm is a
promotion candidate only if at least one 210+ count improves and no higher
threshold worsens. Counts at 200/194/187, pool oracles, means, season signs,
runtime and paired weekly gains/losses are reported diagnostics. No alternate
dose, scale, selector line, market combination or seed may follow a valid
rejection on these outcomes.

