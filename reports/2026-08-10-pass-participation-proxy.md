# Pass-participation proxy gate

Status: preregistered; implementation and cloud diagnostic pending.

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
