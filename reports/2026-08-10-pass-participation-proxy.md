# Pass-participation proxy gate

Status: completed; frozen purchase/mechanism gate passed and supports a paid
true-route-data trial.

## Purpose

The accepted K=1/CE pool misses 36 player slots from 68 known Millionaire
winners. Twenty-three are WR/TE, and the omitted slots are disproportionately
cheap, low-owned fast-role or vacancy players. The current features have snap
share, targets and air yards but not routes run.

Before purchasing route data, test whether a closer free proxy contains
incremental signal. `nflreadpy.load_participation` currently supplies
play-level offensive personnel for 2023-2025. Joining offensive player IDs to
play-by-play dropbacks yields the fraction of team dropbacks for which a
player was on the field, including the same fraction inside the red zone.

This source is season-delayed and does not say that every on-field player ran
a route. It is therefore a diagnostic for the value of true route data, not a
production input and not permission to reconstruct a historical lineup arm.

## Frozen construction

For each regular-season team/game and player listed at WR, TE, RB or FB:

1. retain valid offensive plays with `qb_dropback == 1`;
2. count player-on-field dropbacks and team dropbacks;
3. repeat for plays with `yardline_100 <= 20`;
4. aggregate to player/team/week shares;
5. for a target slate, expose only the player's prior observed game share and
   its change from the observation before that; and
6. require the participation row's season/week to precede the prediction row.

FB maps to the RB feature family. Rows with malformed personnel vectors or
fewer/more than eleven offensive players are reported and excluded. A player
changing teams retains his own prior-game history; team denominators always
come from the team attached to that participation row.

Frozen added inputs:

- `pass_play_share_last`
- `pass_play_share_jump`
- `redzone_pass_play_share_last`
- `redzone_pass_play_share_jump`

## Frozen comparison

Universe: accepted panel `20260809-e80-k1-ce12-c616390`, skill players only,
2024 and 2025 held out. The 2023 rows are training-only. The 2024 fold trains
on 2023; the 2025 fold trains on 2023-2024. Do not use a later season to
predict an earlier one.

Two fixed regularized models are fit for each fold:

- regression target: `actual - proj`, scored by MAE, using
  `Ridge(alpha=10.0)`;
- classification target: `actual >= 20`, scored by Brier loss, using
  L2 `LogisticRegression(C=0.1, solver="lbfgs", max_iter=2000)`.

Control inputs are pre-lock `proj`, `salary`, position, `target_share_last`,
`target_share_jump`, `snap_share_last`, `snap_share_jump`, and
`team_vacated_target_share`. The treatment adds only the four frozen
participation inputs. Numeric fields use training-fold median imputation and
standardization; position uses most-frequent imputation and one-hot encoding
with unknown positions ignored. Both arms use identical rows,
preprocessing, regularization and folds. A row needs a prior participation
observation; a missing earlier observation for a jump or a week with no
red-zone dropback is handled by the training-fold imputer. Report sample
sizes, missingness, regression MAE, Brier loss, calibration by probability
decile, and WR/TE-only metrics for each season and aggregate.

## Gate and disposition

The proxy supports a paid route-data trial only if:

- aggregate treatment residual MAE is lower than control;
- aggregate treatment Brier loss is lower than control;
- neither metric worsens by more than 1% in either held-out season; and
- WR/TE-only Brier loss is lower in aggregate.

This is intentionally a purchase/mechanism gate, not a production scoring
gate. Passing does not add the proxy or a paid field to the model. It supports
acquiring true route data and running the separately frozen walk-forward
player-tail, candidate-union and fixed-budget stages in the scoring roadmap.
A valid failure lowers the priority of route-data spending; do not tune the
four inputs, thresholds, folds or model family after seeing it.

Source:

- <https://github.com/nflverse/nflreadr/releases>

## Result

Full validation build `6200e344-837e-4935-9adf-8eb062383017` passed 720 tests
with 2 skipped and produced immutable diagnostic digest
`sha256:2665a7f9a683e2d737d620519a15a431e4a5c7baa6feb43aade7f2f4084fde62`.
Cloud Run execution `pass-participation-proxy-vmxdq` completed successfully in
1m48s. Its complete machine report is tracked under
`reports/pass-participation-runs/20260810-pass-participation-v1/`.

The source audit processed 137,271 participation plays, excluded 53 malformed
personnel vectors, joined 60,805 valid dropbacks and produced 17,067
player-week rows. The accepted snapshot supplied 24,205 2023-2025 skill rows;
14,845 had a strictly prior participation observation. The two held-out folds
contained 9,887 player-weeks.

| held-out rows | control MAE | treatment MAE | control Brier | treatment Brier |
|---:|---:|---:|---:|---:|
| 2024: 4,964 | 3.80397 | 3.76658 | 0.048312 | 0.048096 |
| 2025: 4,923 | 3.61703 | 3.59184 | 0.042413 | 0.042332 |
| aggregate: 9,887 | 3.71089 | 3.67957 | 0.045375 | 0.045226 |

Aggregate WR/TE Brier also improved from `0.039258` to `0.039082`. Every
frozen gate condition passed: aggregate MAE, aggregate Brier and WR/TE Brier
improved, while neither held-out season worsened either primary metric.
Machine disposition is **`supports-paid-route-trial`**.

The improvements are small—about 0.84% in MAE and 0.33% in Brier—so this is
not evidence that route data alone will transform lineup scoring. It is clean
evidence that a closer pass-opportunity measure adds incremental held-out
signal beyond current target/snap/vacancy features. Proceed to the paid export
only after full 2022-2025 CSV availability and a checkout below $200 are
confirmed; the true-route fields must still pass their own player-tail,
candidate-union and equal-budget lineup gates.
