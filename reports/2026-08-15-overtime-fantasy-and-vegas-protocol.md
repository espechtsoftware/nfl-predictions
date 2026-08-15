# Overtime fantasy uplift and pregame-odds protocol

Date frozen: 2026-08-15 12:29 CDT  
Status: pre-result mechanism and predictability study; no production license

## Question

Under the overtime rules relevant to the 2026 NFL regular season:

1. how many DraftKings points does overtime add, where do those points land,
   and does the extra period materially increase useful player/game tails; and
2. can information available from pregame Vegas lines identify overtime risk
   well enough to support an outcome-blind shared-duration mixture in the game
   simulator?

No overtime frequency, fantasy-point uplift, model coefficient, validation
metric or selected-lineup result was queried before this protocol was fixed.

## Rule regimes and permitted seasons

The regimes may not be pooled for the fantasy-uplift estimate:

- In 2022 the NFL guaranteed both teams a possession only in the postseason.
- Beginning in 2025, the guaranteed-possession rule also applies to the
  regular season, subject to its single 10-minute overtime period.
- Postseason overtime uses successive 15-minute periods as necessary and is
  structurally different from the Sunday-main regular-season target.

Accordingly:

- **primary current-rule uplift:** 2025 regular season only;
- **secondary current-rule mechanism description:** 2022--2025 postseason,
  reported separately and never used to estimate the regular-season effect;
- **OT-occurrence model training:** 2022--2024 regular season;
- **OT-occurrence model heldout evaluation:** 2025 regular season; and
- seasons before 2022 are excluded from every analysis.

The occurrence model may use 2022--2024 because its label is whether the score
is tied at the end of regulation, an event fixed before the overtime procedure
begins. Those seasons may not contribute overtime fantasy points to the
current-rule uplift estimate.

Official rule references:

- <https://operations.nfl.com/gameday/analytics/stats-articles/using-data-and-analytics-to-evaluate-the-2022-club-proposals-on-overtime-in-the-postseason/>
- <https://operations.nfl.com/rules-officiating/featured-rules>
- <https://operations.nfl.com/media/ntif5hxb/2025-nfl-rulebook-final.pdf>

## Frozen sources and identities

- Game identity, game type, overtime flag and closing market fields:
  `nfl_raw.schedules`, unique by `game_id`.
- Play identity and period: `nfl_raw.pbp`, unique by `(game_id, play_id)`.
- Authoritative full-game skill score parity:
  `nfl_features.player_week_actuals` plus the already reconciled
  `research.recourse_scoring` scorer.
- Authoritative DST score parity:
  `nfl_features.team_defense_week` plus the same reconciled scorer.

Schedule closing fields are a retrospective feasibility source with no local
snapshot timestamp. They may answer whether spread/total contain signal, but
they cannot by themselves license production. If the heldout predictability
gate passes, a separate create-only acquisition must reproduce the result from
The Odds API snapshots pulled no later than the applicable slate lock before
any live hook is permitted.

Every query must emit source row counts, distinct game counts, missing-line
counts, duplicate counts, season/game-type extrema and a deterministic hash of
the ordered input frame.

## A. Current-rule fantasy uplift

For every 2025 regular-season overtime game, score the identical PBP twice:

1. **regulation state:** only plays with `qtr <= 4`; and
2. **full state:** all plays, including `qtr > 4`.

Use the already reconciled DraftKings skill and DST scorers, so threshold
bonuses and points-allowed tiers are recomputed in both states. Full-state
scores must reconcile to the authoritative full-game tables before any delta
is accepted. Report both player-level and game-level `full - regulation`:

- total skill-player DK points and total DST points;
- QB, RB, WR and TE point deltas;
- maximum individual delta and the number of players gaining at least
  3, 6 and 10 points;
- change in the game's top-one and top-three skill-player scores;
- bonus crossings at 300 passing and 100 rushing/receiving yards;
- OT offensive drives, plays, elapsed seconds and possessions by team; and
- score deltas for the fixed historical production selections, where a
  checksum-bound 2025 selected-lineup book is available.

The last item is descriptive only and may not change a historical selection.
All regular-season games are included for the mechanism estimate; a Sunday
13:00--16:30 ET subset is separately reported as the deployment-relevant view.

Also report full-game OT versus non-OT differences for game skill total,
top-one, top-three and counts of players at or above 20/25/30 DK points. Show
both the raw difference and a fixed linear adjustment using `abs(spread_line)`
and `total_line`. The within-OT regulation/full delta, not this observational
comparison, is the primary causal description of points added by overtime.

## B. Pregame prediction of reaching overtime

The binary label is `schedules.overtime = 1` in a regular-season game. Drop a
game only when either spread or total is missing; report every exclusion.

Fit on 2022--2024 and evaluate once on untouched 2025:

- `M0`: the Laplace-smoothed training OT base rate;
- `M1`: L2 logistic regression on standardized `abs(spread_line)`; and
- `M2`: L2 logistic regression on standardized `abs(spread_line)` and
  `total_line`.

For M1/M2 use `C=1.0`, an intercept, no class weighting, training-set means and
standard deviations, and clip probabilities only for log loss at
`[1e-6, 1-1e-6]`. No polynomial, interaction, team, quarterback, weather,
season, line-movement or in-game feature may be added after results are read.

Report 2025 Brier score, log loss, ROC-AUC, average precision, calibration by
predicted-risk quartile, observed/base lift in the highest quartile, and the
number of OT events in every quartile. Bootstrap 2025 games by week, seed
`20260815`, 10,000 replicates, for paired M2-minus-M0 Brier and log-loss
intervals. M2 is the primary candidate; M1 is an attribution diagnostic.

## Frozen disposition

The result is **predictive** only if all of the following hold on 2025:

1. M2 Brier score is strictly lower than M0;
2. M2 log loss is strictly lower than M0;
3. both paired 90% week-bootstrap intervals exclude zero in the improving
   direction;
4. the highest-risk quartile has observed OT lift greater than 1.0 versus the
   full 2025 rate and contains at least two OT games; and
5. all source, scorer-parity and deterministic-repeat checks pass.

Anything else is non-predictive or inconclusive. No threshold may be relaxed
after results are visible.

Even a predictive result does **not** license adding expected points. Sportsbook
game totals and player markets already settle with overtime and therefore
already embed average OT value. The only licensed next step is a separately
frozen, prospective simulator arm that:

- uses a pre-lock Odds API snapshot;
- samples an odds-conditioned shared game-duration/possession state;
- preserves each player's unconditional served mean and marginal distribution;
- changes only within-game joint allocation/tail dependence;
- uses current-rule 2025 OT possessions as the treatment distribution; and
- must beat the unchanged 80-lineup control under the project's tail-first
  heldout gate before any production adoption.

The postseason result remains descriptive and cannot license the regular-season
simulator arm.
