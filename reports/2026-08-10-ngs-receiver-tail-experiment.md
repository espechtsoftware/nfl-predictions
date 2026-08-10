# Lagged Next Gen Stats receiver-tail experiment

Preregistered 2026-08-10 before querying realized outcomes for this mechanism.
The source is the NFL Next Gen Stats weekly receiving feed exposed by
`nflreadpy`; acquiring it spends no Odds API quota.

## Motivation and availability

The current model already has targets, target share, PBP-derived air-yard
share/aDOT, snaps, vacancies, depth, and a same-season four-week NGS
separation average. The remaining prospective gap is narrower: the existing
NGS window resets at every season boundary, while receiver traits can carry
into Week 1; cushion and YAC above expectation are not included at all. This
experiment therefore tests career-chronological last-four NGS observations
only after explicitly controlling for the existing `separation_l4`,
`air_yards_share_l4`, and `adot_l8` inputs. It cannot claim ordinary
separation, air depth, or air share as newly discovered information.

An outcome-free inventory found 8,976 regular-season weekly receiving rows
for 2019--2025, with 198--223 distinct receivers and all 17/18 weeks per
season. On the preserved true-80 role candidate universe, a strictly prior
same-season observation covers about 81--89% of candidate-used WRs and
70--83% of candidate-used TEs by season; weighting by candidate-roster
appearances gives 88.3% coverage. Historical data are available from 2016,
so a career-chronological join can also serve returning veterans in Week 1
from prior-season observations. Rookies and other uncovered players remain
missing rather than receiving invented values.

## Frozen point-in-time construction

Use regular-season weekly NGS receiving rows with `week > 0`. For every
target player-week, retain only observations whose `(season, week)` is
strictly earlier. The join may cross a season boundary but may never use the
target week, a later week, the `week=0` season aggregate, postseason data, or
a future season.

For each field below, calculate a target-weighted mean of the most recent
four eligible weekly observations. Weekly target count is a reliability
weight only and is not added as a treatment feature. If all weights are
missing/zero, use an unweighted mean of the available finite values.

- `avg_separation`
- `avg_cushion`
- `avg_intended_air_yards`
- `percent_share_of_intended_air_yards`
- `avg_yac_above_expectation`

The evaluation universe is WR/TE player-weeks that appeared in at least one
candidate in corrected K1 control panel
`20260810-lockfix-e80-k1-8677d21`, have an authoritative actual and pre-lock
projection, and have at least one strictly prior NGS observation. Candidate
membership is point-in-time and outcome-blind. Do not evaluate partial panel
rows; the full corrected K1 control must first complete its mechanical check.

## Frozen walk-forward comparison

The 2024 fold trains on corrected source seasons 2019/2021/2022/2023. The
2025 fold trains on all of those plus 2024. No future season predicts an
earlier one. Both arms use identical rows, training-fold median imputation,
standardization, WR/TE one-hot position, models and regularization.

Control numeric inputs:

- pre-lock projection and salary;
- last target/snap share and their jumps;
- team vacated target share;
- depth rank; and
- games played before the target week; and
- the model's existing same-season `separation_l4`, PBP-derived
  `air_yards_share_l4`, and `adot_l8` fields.

The treatment adds only the five frozen lagged NGS fields. Fit
`Ridge(alpha=10)` to `actual - projection`. Separately fit L2
`LogisticRegression(C=0.1, solver=lbfgs, max_iter=2000)` for `actual >= 20`
and `actual >= 30`. Report per-fold and aggregate residual MAE, 20/30-point
Brier loss, event rates, calibration deciles, row counts, field missingness,
source age, and candidate-weighted coverage.

## Gate

The mechanism passes only if all conditions hold:

1. each held-out season has at least 1,000 eligible candidate-used WR/TE
   player-weeks and at least 70% of candidate-weighted WR/TE appearances have
   a strictly prior NGS observation;
2. aggregate 30-point Brier loss improves;
3. aggregate 20-point Brier loss does not worsen;
4. aggregate residual MAE does not worsen; and
5. held-out 30-point Brier loss does not worsen by more than 1% in either
   season.

The 30-point event is primary because it is closest to the operator's
extreme weekly portfolio objective. The 20-point and MAE guards prevent a
rare-event gain from silently destroying broader calibration. No position,
field, rolling-window, regularization, threshold, fold or missing-data retry
is allowed after a valid result.

A pass licenses feature integration and one separately preregistered
candidate-union test on the corrected live-policy source; it does not itself
change projections, generate lineups, or authorize production use. A failure
closes these five NGS receiving fields as a pre-Week-1 scoring path. It does
not negate the already-passed true-route purchase diagnostic, because NGS
separation/efficiency descriptors do not measure complete route volume or
first-read opportunity.

Primary source:

- <https://github.com/nflverse/nflreadr/releases>

## Implementation status

Guarded implementation lives in
`src/nfl_dfs/analysis/ngs_receiver_tail.py`, CLI command
`ngs-receiver-tail-diagnostic`, and
`scripts/cloud_ngs_receiver_tail.sh`. The cloud runner requires an immutable
image and a recorded passing check-only acceptance artifact for the complete
corrected K1 panel, then harvests exactly one machine-readable report.
Offline tests cover same-week/week-zero/postseason exclusion, cross-season
history, target-weighted rolling values, uncovered players, duplicate source
rows, every frozen gate, and the complete walk-forward model path. No
realized NGS-mechanism outcome has been queried and no cloud execution has
been launched.

Corrected exact-tree Cloud Build
`e8dd679c-7a40-4e98-8525-31e4ecf700eb` passed 738 tests with 2 skipped and
produced immutable diagnostic digest
`sha256:fe380648b9a146a95b8c4d942c484979b50f95762f16a277d704151106a82374`.
The runner may use only this digest and remains blocked on corrected K1
check-only acceptance.

Pre-outcome static audit correction: the first protocol draft incorrectly
described separation, air depth, and air share as absent from the model.
`sql/features/015a_player_week_advanced.sql` and the canonical feature list
show that separation is already active, while the usage/efficiency tables
already provide the other two. The implementation was corrected before any
result so both arms receive those exact existing fields. The test now asks
only whether cross-season NGS history plus cushion/YACOE adds residual value.

## Result

Execution `ngs-receiver-tail-diagnostic-nkb2h` completed successfully from
the immutable corrected diagnostic image after K1 check-only acceptance. The
mechanism had excellent candidate-weighted coverage (97.43% in 2024 and
98.25% in 2025) over 2,936 held-out player-weeks, but failed every predictive
gate. Aggregate 30-point Brier worsened `0.0230785→0.0231012`, 20-point Brier
worsened `0.0912537→0.0914343`, and residual MAE worsened
`5.65602→5.66138`; 30-point Brier also worsened in 2025. The disposition is
`ngs-receiver-tail-gate-fails`. No lineup arm is licensed, and the five NGS
fields are closed as a pre-Week-1 scoring path without a parameter retry.
This does not reverse the separate true-route-data purchase signal because
complete route volume/opportunity is not measured by these NGS descriptors.
