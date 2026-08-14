# SIS pass-tail current-stack marginal protocol

Frozen 2026-08-13 after the outcome-free support/redundancy screen and before
any treatment cache, model outcome, candidate score or lineup score is read.

## Stage, channel and question

- stage: player marginal forecast;
- channel: TabPFN feature/cache only;
- estimand: whether lagged proprietary opponent tail/pressure context improves
  the served upper-tail distribution for active QB/WR/TE players;
- terminal control: active-only-label shared-33 TabPFN cache law;
- transfer boundary: any exact-80 follow-on must use the Phase-S-selected
  allocation law and rerun under that terminal context;
- interaction status: standalone marginal screen. It is not the SIS ASOE
  allocation mechanism and does not test their interaction.

## Frozen treatment

Build one control/treatment cache pair on the same immutable training snapshot,
active-only historical labels, walk-forward seasons 2022--2025, TabPFN seed,
context cap, estimator count and quantile grid used by the accepted cache.
Control must reproduce `tabpfn_active_label_treatment_v2` within `1e-10` on
every key and prediction field.

Treatment appends exactly these three fields to the shared-33 feature list:

1. `sis_pass_def_boom_rate_l4`;
2. `sis_pass_def_bust_rate_l4`; and
3. `sis_pass_rush_pressure_rate_l4`.

For a target player week, join the opponent's SIS team/game rows, aggregate
only the last four completed same-season games and require at least two prior
games. Boom/Bust must be volume-weighted by Pass Defense Value attempts;
pressure must be total pressures divided by pass-defense attempts plus sacks.
Expose all three only for QB/WR/TE; leave RB and all unsupported early weeks
null. No hand coefficient, imputation, cross-season fallback, feature subset,
position subset or alternate window is permitted after cache output.

## Mechanical gate

Require identical source fingerprints, target keys and inherited
hyperparameters; exact 52,307 rows per cache; ordered finite quantiles; changed
treatment predictions; no inactive training labels; at least 80% supported
active QB/WR/TE rows in each evaluation season; and exact control reproduction.
Any failure invalidates the arm without model or lineup interpretation.

## Frozen score-free final-served gate

Fit each arm's position schedule independently using the existing 2022
calibration construction, then score all active QB/WR/TE rows in 2023--2025.
For q95 and q99 separately compute pinball loss by position. Normalize every
treatment loss by its matching control position/quantile loss, then average
the six ratios equally.

The treatment passes only if:

1. the equal-position/equal-quantile mean normalized pinball ratio is strictly
   below `1.0`;
2. at least two of QB, WR and TE improve their mean q95/q99 normalized
   pinball ratio; and
3. each arm preserves served player means within `1e-10`.

Report q90, q95 and q99 pinball/exceedance, Brier at 20/25/30, reliability,
CRPS, MAE, all position and season folds, and paired slate-cluster uncertainty.
They are diagnostics without a season veto. This gate deliberately prioritizes
proper tail scores over average error while preventing one populous position
from deciding the result alone.

## Conditional exact-80 follow-on

A pass licenses one separately frozen five-seed exact-80 control/treatment
panel using the Phase-S-selected allocation law and otherwise identical
candidate/world/selector contracts. Decide by the operator's terminal
`240,230,220,210,200,194,187`, then mean weekly-maximum order with no average
or season veto. A failure closes only this three-feature bundle. It does not
close SIS Receiving, player-grain filtered allocation or passing charting.
