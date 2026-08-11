# Fantasy Points weekly reports — short project summary

Fantasy Points supplied six weekly report families for the 2022--2025
seasons.  For any prediction of Week N, only observations from weeks before
Week N may be used; Week N results are not available until those games have
been played.

| Report | What it measures | Current project assessment |
|---|---|---|
| **Weekly Fantasy Points Scored** | Each player's fantasy production for the completed week. | Useful mainly for player-identity and scoring-reconciliation checks. The project already has authoritative DraftKings scoring labels, so this should not replace them. |
| **Weekly Snap Share** | Percentage of the team's offensive snaps on which the player was on the field. | General playing-time/role signal. It substantially overlaps the existing nflverse-derived snap-share features, but a source-agreement and missingness audit should be completed before declaring it fully redundant. |
| **Weekly Route Share** | Percentage of team passing plays/dropbacks on which the player ran a route. | The clearest incremental asset in the purchase. It distinguishes actual receiving participation from merely being on the field, especially for tight ends who may stay in to block. It has slightly improved held-out 20- and 30-point tail calibration and is undergoing lineup-level testing. |
| **Weekly Target Share** | Percentage of the team's targets received by the player. | Direct receiving-volume signal. It substantially overlaps the project's play-by-play target-share features, but should receive the same outcome-blind agreement/completeness audit as Snap Share before being closed. |
| **Weekly PROE — Offense** | How pass-heavy an offense was relative to expectation in the completed week. | Mostly overlaps the project's existing strictly lagged offensive `proe_l4` feature. It is low priority unless a source comparison shows better coverage or a materially different definition. |
| **Weekly PROE — Defense** | How pass-heavy opposing offenses played relative to expectation against a defense. | Distinct opponent-context data; the current feature SQL does not already contain this exact defensive series. It remains a plausible secondary feature and should not be dismissed as redundant without an incremental test. |

## Practical priority

1. **Route Share** is the primary weekly download and research input.
2. **Defense PROE** is the main remaining team-context question.
3. **Target Share and Snap Share** should be retained until their agreement
   with existing sources is measured without looking at outcomes.
4. **Offense PROE and Fantasy Points Scored** are primarily reconciliation or
   fallback sources rather than clearly new predictive information.

The current evidence supports Route Share more clearly as a player-tail signal
than as a mean-projection correction: the frozen Route diagnostic slightly
improved 20/30-point Brier scores but slightly worsened residual MAE.  A future
full component-model test is therefore reasonable, but the data do not yet
justify claiming that Route Share improves the production mean projection.
