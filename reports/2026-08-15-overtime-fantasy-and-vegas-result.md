# Overtime fantasy uplift and Vegas result

Date: 2026-08-15 12:48 CDT  
Protocol: `reports/2026-08-15-overtime-fantasy-and-vegas-protocol.md`  
Machine result: `reports/2026-08-15-overtime-fantasy-and-vegas-result.json`  
Disposition: **overtime materially increases fantasy tails, but ordinary
spread/total did not predict overtime out of sample**

## Current-rule fantasy effect

The direct regulation-versus-full-game comparison covered all 14 overtime
games in the 2025 regular season. The reconciled DraftKings scorer passed for
every skill player and defense, and both the uplift and prediction results
reproduced bit-exactly.

- Overtime added **23.77 skill-player DK points per OT game** on average
  (median 20.27; total 332.82).
- The top player in the game gained 4.98 points on average and the top three
  gained **10.12 points** on average.
- The largest individual OT gain was 14.70 points.
- Across the 14 games, 46 player-games gained at least 3 points, 13 gained at
  least 6 and 6 gained at least 10.
- Four quarterbacks crossed the 300-yard bonus and three runners crossed the
  100-yard bonus during overtime.
- Added skill points by position were QB 78.92, RB 83.90, WR 120.10 and TE
  49.90.
- DST scoring fell by 0.29 points per game on average because extra scoring can
  worsen the points-allowed tier.

OT games were already unusually productive before considering only their
extra period. Across all 272 games, full-game OT contests contained 43.77 more
skill-player DK points than non-OT games; the fixed spread/total-adjusted OT
coefficient was 40.45. OT games averaged 3.71 players at 20+ DK versus 2.07 in
non-OT games, 2.14 versus 1.03 at 25+, and 1.36 versus 0.45 at 30+.

This makes overtime a real high-score mechanism. It does **not** mean 23.77
points can be added to projections: game totals and player markets settle with
overtime and already embed its average value.

## Pregame Vegas prediction

The frozen predictor trained on 815 regular-season games from 2022--2024 (49
OT) and evaluated once on all 272 games from 2025 (14 OT). No pre-2022 season
was used.

| Model | 2025 Brier | 2025 log loss | ROC-AUC | Average precision |
|---|---:|---:|---:|---:|
| Training base rate | 0.048916 | 0.203691 | 0.500 | 0.0515 |
| Absolute spread | 0.048991 | 0.204318 | 0.433 | 0.0519 |
| Absolute spread + total | 0.048939 | 0.203776 | 0.507 | 0.1232 |

The spread-plus-total model was slightly worse than the base rate on both
primary proper scores. Its highest predicted-risk quartile contained four OT
games, the same count as its lowest quartile, and only 1.14x the overall OT
rate. The paired week-bootstrap intervals crossed zero for both scores. The
frozen predictability gate therefore failed cleanly.

## Consequence and next opportunity

No production or prospective duration treatment is licensed from ordinary
spread and total. The production baseline remains unchanged.

The Odds API documents an additional `h2h_3_way` market whose Draw outcome,
when offered for an NFL regulation market, would be a direct sportsbook price
for the event that produces overtime. NFL availability has not been verified,
and the vendor's ordinary NFL market list does not advertise a dedicated
overtime prop. During the first live 2026 market window, perform one bounded,
quota-audited schema/availability check for:

1. a full-game regulation `h2h_3_way` Draw price;
2. any explicitly named game-goes-to-overtime market; and
3. the number of books and timestamps supporting either price.

If a direct pre-lock price exists, freeze a prospective 2026 collection and
calibration protocol before reading outcomes. If it does not, do not infer OT
risk from spread/total in production. Richer consensus disagreement or line
movement can remain a research lead, but 2025 is no longer an untouched
holdout for post-hoc feature additions.

Official rule sources:

- <https://operations.nfl.com/gameday/analytics/stats-articles/using-data-and-analytics-to-evaluate-the-2022-club-proposals-on-overtime-in-the-postseason/>
- <https://operations.nfl.com/rules-officiating/featured-rules>
- <https://operations.nfl.com/media/ntif5hxb/2025-nfl-rulebook-final.pdf>

Odds-market references:

- <https://the-odds-api.com/sports-odds-data/betting-markets.html>
- <https://the-odds-api.com/sports-odds-data/nfl-odds.html>
