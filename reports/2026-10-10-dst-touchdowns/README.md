# Do defensive touchdowns persist? A quick test for DST selection (2026-10-10)

**His question (the laptop's session, verbatim):** "Also, do we consider touchdowns from defenses when selecting defenses?  Can we do a
quick test of that?"

**Data:** nflverse play-by-play (`nfl_raw.pbp`), regular season 2022–2025 plus 2026 Weeks 1–4; one row per team-week. A DST touchdown =
a touchdown scored by the team while not on offense (interception / fumble returns, punt and kickoff returns, blocked-kick returns),
`dst_td.sql`. Predictors are known before the week: the team's own DST touchdowns per game in earlier weeks of the same season, the
opponent's giveaways (interceptions + lost fumbles) per game in earlier weeks, the Vegas lines (the opponent's implied total, the
spread). Rows with at least 3 earlier games: **1,824 team-weeks; 11.8% had a DST touchdown.**

| Predictor (top third minus bottom third, in the direction that should help) | Difference in the DST-TD rate | 95% bootstrap interval | Each season 2022 / 23 / 24 / 25 |
|---|---|---|---|
| The defense's own DST TDs so far | **+0.2 points** | −3.5 to +4.1 | +2.6 / −0.1 / −3.4 / +1.3 |
| The opponent's giveaways so far | +3.8 points | +0.5 to +7.9 | +3.3 / +5.3 / +4.6 / +3.3 |
| The opponent's implied total (low minus high) | +4.9 points | +0.7 to +8.1 | +2.1 / +2.8 / +8.1 / +6.8 |
| Favourite margin (big favourite minus big underdog) | +4.6 points | +1.0 to +8.4 | +4.0 / −0.1 / +6.6 / +7.3 |

**Reading.** A defense's touchdown record does not carry forward: the third with the most DST touchdowns so far scores one the next
week as often as the third with the fewest (12.2% vs 12.0%). What does predict one comes from the matchup: a weak offense (a low
implied total: 15.1% vs 10.2%), a turnover-prone offense (13.8% vs 10.0%) and being the favourite (14.5% vs 9.9%). These are the inputs
a DST projection already uses (Fantasy Points' and ours rank defenses mostly by the opponent's implied total and the spread), so **we
should not add a "DST touchdowns so far" factor**; the opponent's turnover rate is the one piece worth checking that the projections
carry. Descriptive, quick, nothing changes.

**Week 5 application:** the Texans (his hand-entered L2 and R1) face Tennessee, the slate's lowest implied total (15.75) as 7-point
favourites; Tennessee's giveaways are low (0.75 a game, 21st). Two of the three signals favour them; their own 4.8 DST points a game so
far is, by this test, not informative.
