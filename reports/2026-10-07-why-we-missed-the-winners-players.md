# Why we did not get the winners' players: matchups, injuries, the market (2026-10-07)

The operator (10-07): "Have you looked at all the other factors for each of those players … Were the matchups
favorable? Were there injuries that made them get more plays?" and "run any experiment that comes out of these
findings." By the outside reviewing agent. Code: `reports/2026-10-07-winners-strategy-study/player_factors.py`;
per-player table `run/player_factors.csv`; full log `run/player_factors.log`.

**Pre-lock facts** (what a Saturday/T−70 build could have known): the projection played (ours W1–3, Fantasy Points
W4), the props-implied projection (`market_points`), the anytime-TD probability (last prop snapshot before lock),
a **matchup measure** (the opponent's DraftKings points allowed to the player's position: 2025 as a six-game prior
plus the 2026 weeks before the slate; percentile among the slate's opponents, 100 = softest), teammates ruled Out or
Doubtful on the injury report and the vacated target/carry share, depth-chart moves. **Outcome facts** (explain only):
that game's snaps, targets, carries, red-zone and goal-line touches, touchdowns, 20-yard plays, and teammates whose
snaps collapsed in the game (an in-game exit, checked against the next week's injury report).

## 1. Player by player (the winner's players we did not have)

| Week | Player | Pre-lock: matchup pct · injuries in his favour · market vs projection | What happened |
|---|---|---|---|
| 1 | Jalen Coker WR CAR | soft (84) · — · market 1.4 below | 9 targets, 2 TDs, two 20-yard plays (36.8) |
| 1 | Christian Watson WR GB | hard (3) · — · 1.7 below | 8 targets, 2 TDs (35.7) |
| 1 | DJ Moore WR BUF | hard (10) · — · 1.9 below | 8 targets, 1 TD (24.0) |
| 1 | Dallas Goedert TE PHI | soft (84) · rookie TE Stowers Out · even | 5 targets, 2 TDs (23.7) |
| 2 | CeeDee Lamb WR DAL | soft (82) · — · even | 9 targets (his norm), 2 TDs, four 20-yard plays (38.3) |
| 2 | Tre Tucker WR LV | hard (15) · **Brock Bowers (TE1) Doubtful** · even | 7 targets vs 4, 1 TD (25.9) |
| 2 | Purdy / McCaffrey / Kittle SF | soft (80 / 93 / 85) · Stribling Out; **D. Robinson left the game** (31% of snaps, Out the next week) · CMC +1.7 | the slate's top total (29), favourite by 13.5 |
| 3 | Jaylen Warren RB PIT | **soft (90) · Rico Dowdle Out (38% of the carries) · market +3.7 above our projection** | snaps 54% → 90%, 17 touches, three 20-yard plays (23.6) |
| 3 | Jaxon Smith-Njigba WR SEA | soft (84) · — · +0.8 | 14 targets vs 11, 2 TDs (38.4) |
| 4 | Kyren Williams RB LA | neutral (47) · **Mumpfield left the game** · 1.4 below (FP) | 16 touches vs 13, 2 TDs (36.7) |
| 4 | Javonte Williams RB DAL | hard (3) · — · 1.0 below | 19 carries, 8 inside the 20, 5 inside the 5, 3 TDs (31.3) |
| 4 | Zay Flowers WR BAL | soft (90) · Questionable himself; **Bateman left the game** · 2.0 below | snaps 31% → 73%, 10 targets, 1 TD (28.8) |

And the winners' players we did have, for contrast: Dalton Schultz W2 (Nico Collins Out, 27% of the targets
vacated → 14 targets), the NYJ stack W3 (matchup 95–96, the softest on the slate; Mason Taylor Out → Sadiq's snaps
39% → 58%, Wilson 13 targets vs 7), Hockenson W4 (Justin Jefferson Out, 37% of the targets → 13 targets vs 4).

**Reading.** Of the twelve missed explosions, six had a soft matchup, four had a pre-lock injury in their favour
(Warren, Tucker, Goedert, the 49ers' Stribling), four were helped by a teammate leaving during the game (not
knowable), and almost all were decided by touchdowns and long plays. Three had a hard matchup and nothing else
(Watson, Moore, Javonte Williams). So the answer to the operator's question is: yes, for about half of them the
matchup or an injury pointed their way before lock, and the projection we played did not move enough; for the rest
it was the game.

## 2. Across the whole slate: which pre-lock facts predict an explosion?

545 skill player-weeks projected ≥ 5 (W1–4); an explosion = actual ≥ projection + 10 and ≥ 1.8× the projection
(base rate 9.7%). Explosion rate by tercile within each week (low / mid / high), and the high − low gap per week:

| Pre-lock fact | low | mid | high | high − low by week (W1, W2, W3, W4) |
|---|---|---|---|---|
| **matchup: the opponent's points allowed to the position** | 7.7% | 7.2% | **14.3%** | **+.11, +.04, +.05, +.07 (all four)** |
| anytime-TD probability | 6.1% | 11.2% | 12.2% | +.11, +.04, +.05, +.05 (mostly the projection itself) |
| props-implied projection − projection played | 8.0% | 9.4% | 13.5% | +.08, +.09, +.15, **−.09 (W4, FP played)** |
| the projection played (reference) | 4.4% | 12.8% | 12.1% | +.17, +.04, +.02, +.07 |
| team implied total | 8.7% | 10.6% | 9.9% | +.07, +.02, −.07, +.02 |
| teammates Out vacate ≥ 10% of the own-type share | no 9.2% (n 487) | | yes 13.8% (n 58) | yes-rate .13, .14, .14 (W2–4) |
| market ≥ projection + 1.5 | no 9.4% | | yes 25.0% (n 12) | W1 .50, W2 .00, W3 .25 |

**The matchup measure is the one pre-lock fact that doubles the explosion rate in all four weeks.** And the
projection model does not have it: `src/nfl_dfs/models/featureset.py` carries coverage and pressure features
(`cb_ypt_allowed_l6`, `db_ypt_allowed_l6`, `top_cb_out`, `opp_pressure_rate_l6`, …) but not the opponent's points
allowed to the position; the warehouse's own `qb/rb/wr/te_fp_allowed_adj_l6` and `rz_td_rate_allowed_l6` exist but
are windowed within the season (`sql/features/017_defense_week_allowed.sql`, `PARTITION BY … season`), so they were
**empty for every player in the Weeks 1–3 frames** and first appear in Week 4. Our own projection in Weeks 1–3
therefore had no matchup information of this kind. The market's disagreement with our projection predicted explosions
while our projection was played (W1–3) and stopped doing so under Fantasy Points (W4), which agrees with the earlier
finding that FP is market-quality. Vacated opportunity carries a small, consistent lift.

## 3. Experiments run on these findings

[EXPERIMENTS]
