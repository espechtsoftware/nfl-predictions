# Fantasy Points same-season route-shape protocol

Preregistered on 2026-08-11 CDT after the complete Fantasy Points catalog and
outcome-blind redundancy/support audit, and before any exact-window Route
Break value was joined to a target-week outcome.

## Question and immutable collection

Does a receiver's broad route-shape mix over exactly the last four completed
weeks improve 30-point WR/TE tail forecasts beyond the corrected pre-lock
projection and point-in-time controls?

Use only
`automation/fantasy_points/plans/same-season-route-shape-last-four-v1.json`.
It contains 56 grouped-header Player exports of Receiving Separation by Route
Breaks: seasons 2022--2025, target Weeks 5--18, and source Weeks W-4 through
W-1. Same/future-week data, cumulative windows, postseason, vendor opponent,
individual named routes and files outside the final manifest are forbidden.
Every artifact must pass the downloader's exact response-payload, rendered
Season/G and downloaded hash/shape/scope checks.

## Outcome-blind support evidence

In exact 2025 Weeks 1--4 and 5--8 samples, Horizontal, Vertical, Static,
Shallow/Underneath and Backfield route counts summed exactly to Overall routes
for all 392/404 rows. Among accepted WR/TE target rows with prior snap data,
an Overall floor of 30 routes covered 58.2% and 52.2%. The five shares were
not duplicates of the existing strictly-prior receiver inputs: their largest
absolute Spearman correlations were 0.20--0.61, with Horizontal and Static
the most distinct and Vertical/Shallow moderately related to aDOT or NGS
separation. No realized target-week score or residual selected this family.

Individual-route and conditional-efficiency cells are excluded. Most named
route types had only 1--7 median routes over four weeks; even broad conditional
YPRR/TPRR/separation cells would require outcome-sensitive support choices.
This protocol uses only count-based composition, for which a zero category is
a legitimate zero after the exact partition check.

## Frozen population, support and features

Evaluate WR and TE rows from corrected accepted panel
`20260810-lockfix-e80-k1-8677d21`. Resolve identities without outcomes using
normalized name, position and team. A source row is supported only when
Overall routes are at least 30 and the five component counts are finite,
nonnegative and sum exactly to Overall routes.

Treatment adds exactly four independent composition coordinates:

1. Horizontal routes / Overall routes;
2. Vertical routes / Overall routes;
3. Static routes / Overall routes; and
4. Shallow/Underneath routes / Overall routes.

Backfield share is the omitted reference category and is mechanically
`1 - sum(the four coordinates)`. Exclude every SEP SCORE, YPRR, TPRR and WIN
RATE field, Overall performance field, individual route type, alignment,
coverage shell and unlisted interaction. Do not change the support floor,
categories, transforms or reference group after outcomes are read.

## Frozen walk-forward evaluation

Use target Weeks 5--18 and held-out seasons 2023, 2024 and 2025:

- held-out 2023 trains on target-season 2022;
- held-out 2024 trains on target-seasons 2022--2023; and
- held-out 2025 trains on target-seasons 2022--2024.

The control inputs, imputation, standardization and fixed models match the
completed receiver diagnostics: residual `Ridge(alpha=10.0)` plus 20- and
30-point `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)` over
`mean_projection`, salary, target/snap last and jump, team vacated target
share, depth rank, games played prior and position one-hot encoding.

Report fold and aggregate 20/30-point Brier loss, residual MAE, calibration
deciles, event counts, identity/support coverage, component-sum validation,
and each share's descriptive residual/tail correlation. Correlations cannot
select or remove a coordinate.

## Frozen gate and consequence

The mechanism passes only if:

1. supported coverage is at least 30% in every held-out fold; and
2. aggregate 30-point Brier loss is strictly lower for treatment.

Season-specific 30-point Brier, aggregate 20-point Brier and residual MAE are
mandatory diagnostics but not vetoes. A pass licenses one separately
preregistered candidate-union test; it does not directly change production.
A valid failure closes this exact mechanism. No threshold, coordinate, window,
model, regularization, fold or gate retry is licensed on its outcomes.

## Pre-outcome status

The plan and protocol were frozen and pushed at commit `99f665d` before
implementation. The manifest-locked importer, strict-prior attachment,
walk-forward diagnostic, CLI and explicit backup member are now implemented;
the complete 812-test offline suite passes with one expected skip, with
compilation, CLI discovery and whitespace checks clean. Immutable collection
`20260811T073453Z__same-season-route-shape-last-four-v1` completed all 56
exports with zero failures. The outcome-blind audit normalized 16,482 receiver
windows (16,119 resolved, 363 unresolved and zero ambiguous), suppressed three
duplicate groups, validated the exact component partition for all 16,485
source rows, and marked 9,489 rows supported. The private table was created
and the mandatory repeat returned `already-identical`. The one-shot cloud
wrapper is frozen to these counts and provenance. Backup execution
`backup-tables-p8ckj` completed successfully and snapshot
`fantasy_points_route_shape_l4_20260811` has exactly 16,482 rows. Exact-tree
Cloud Build `1dfbb3a2-9ab5-410a-933c-0913af4f17f1` from commit `3039af9`
passed 811 tests with two expected skips and published immutable digest
`sha256:35283c02d0be0bfb1be32fd4c9f8a3d9ee81da15ff20e6dc6d471772a11f3d76`.
At that pre-outcome milestone, evaluation and lineup generation had not
started. The already known
same-season coverage and Advanced Passing failures do not contain any Route
Break treatment value and did not select these count-only coordinates.

## Frozen result

The one permitted execution
`fantasy-points-same-season-route-shape-fsrdg` completed successfully with
disposition `same-season-route-shape-player-tail-fails`. Supported accepted
WR/TE coverage passed at 34.32%/33.60%/34.20% in held-out 2023/2024/2025, but
aggregate 30-point Brier worsened `0.02080521→0.02094089`. It worsened in
every fold: `0.02399321→0.02413170`, `0.02069936→0.02086009`, and
`0.01775559→0.01786374`. Aggregate 20-point Brier also worsened
`0.07253747→0.07256688`, as did residual MAE `4.92840→4.93420`. All four
registered descriptive correlations were small.

The exact route-shape mechanism is closed. It receives no candidate-union
test, support-floor retry, coordinate subset or model retry. No lineup or
production policy changed.
