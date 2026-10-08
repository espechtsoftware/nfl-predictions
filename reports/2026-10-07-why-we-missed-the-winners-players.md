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

**The matchup measure is the one pre-lock fact that doubles the explosion rate in all four 2026 weeks (but see §3.0:
out of sample the effect is about a fifth of that, and nothing in Weeks 1–4).** And the
projection model does not have it: `src/nfl_dfs/models/featureset.py` carries coverage and pressure features
(`cb_ypt_allowed_l6`, `db_ypt_allowed_l6`, `top_cb_out`, `opp_pressure_rate_l6`, …) but not the opponent's points
allowed to the position; the warehouse's own `qb/rb/wr/te_fp_allowed_adj_l6` and `rz_td_rate_allowed_l6` exist but
are windowed within the season (`sql/features/017_defense_week_allowed.sql`, `PARTITION BY … season`), so they were
**empty for every player in the Weeks 1–3 frames** and first appear in Week 4. Our own projection in Weeks 1–3
therefore had no matchup information of this kind. The market's disagreement with our projection predicted explosions
while our projection was played (W1–3) and stopped doing so under Fantasy Points (W4), which agrees with the earlier
finding that FP is market-quality. Vacated opportunity carries a small, consistent lift.

## 3. Experiments run on these findings

### 3.0 Correction first: the matchup signal out of sample (2023–2025)

`matchup_oos.py`: the same matchup measure on 2023–2025 (10,742 player-weeks expected ≥ 5 points; none of today's work
touched these seasons), with each player's own pre-week scoring (prior season as a six-game prior plus the season so
far) standing in for the projection, because no archived projections exist before 2026.

| | hard | mid | soft |
|---|---|---|---|
| explosion rate, all positions | 8.8% | 10.7% | 10.3% |
| RB | 8.2% | 9.8% | 11.4% |
| TE | 5.9% | 10.4% | 9.2% |

Logistic, explosion on the player's expected points and the matchup: odds ratio **1.07 per standard deviation**
(z 2.1 pooled; 2023 1.10, 2024 1.07, 2025 1.05). **In Weeks 1–4, when the measure leans on the prior season, 1.01
(z 0.2): nothing.** So the matchup effect is real but small, and the doubling seen in the 2026 weeks was mostly those
four weeks. It is worth a feature in the projection (RB and TE most), not a construction rule.

### 3.1 Experiment A — the live Week-5 book with pre-lock factor bonuses (Weeks 2–4 real fields)

The fixed-book replay harness (the one that decided the tilt and the overlap limit), the live Week-5 settings
(overlap 4, round-robin, QB cap 5, no ownership term), each arm adding a pre-lock bonus through the union's existing
term vehicle, weights fixed before the run: MATCHUP up to +2 (one point per standard deviation of softness),
VACATED up to +3 (10 × the own-type share vacated by teammates ruled Out), MARKET up to +2 (half the props-implied
excess over the projection played), COMBINED their sum capped at +3. `run/experiments/` holds the files and log.

| Arm | P(≥1 big) W2 / W3 / W4 | mean entry percentile W2 / W3 / W4 | best row W2 / W3 / W4 |
|---|---|---|---|
| live | .041 / .002 / .434 | .424 / .516 / .502 | 163.0 / 164.6 / 181.1 |
| matchup | .001 / .296 / .503 | .417 / .606 / .661 | 143.2 / 189.6 / 183.5 |
| vacated | .000 / .025 / .056 | .449 / .692 / .494 | 155.3 / 175.1 / 161.5 |
| market | .134 / .028 / .434 (= live: no bonus under FP) | .419 / .525 / .502 | 162.0 / 160.6 / 181.1 |
| combined | .007 / **.921** / .308 | **.482 / .694 / .571** | 165.0 / 190.1 / 174.8 |

The combined bonus improves the average finish in all three weeks (+6, +18, +7 percentile points) and is ahead on
P(≥1 big) in one; the matchup bonus is ahead in two of three on both. **These are in-sample:** the factors were chosen
from these same weeks, and §3.0 shows the matchup effect is about a fifth of its 2026 size out of sample. The vacated
bonus alone, at ten times the share, promotes fringe backups and is harmful in every week.

### 3.2 Experiment C — lineups built from the simulator's sampled worlds inside each week's winning environment

One lineup per simulated world (the archived worlds of that week's T−70 run, in production's order), under the same
rules as the ladder's best layer; 500 worlds per week.

| Week | Sampled worlds: first top 1% / first top 100 / best | Projection order (same rules, 1,000 builds) |
|---|---|---|
| 1 | 165 / never / 244.1 | 1 / 108 / 248.7 |
| 2 | **6** / never / **192.8** | never / never / 169.7 |
| 3 | **5 / 82** / 210.8 | 21 / 240 / 215.6 |
| 4 | 248 / 251 / 212.3 | 35 / 262 / 219.2 |

The sampled worlds reach the winners' region faster in the two weeks where the projection was furthest from the
winners (Week 2: a top-1% lineup at the 6th build where projection order never got one in 4,000; Week 3: the top 100
at the 82nd), and slower in Weeks 1 and 4. Neither search came within 10 of a winner in any week.

### 3.3 Experiment B — the factor bonus inside the winners' exercise (each week's own winning rules)

Projection-ordered enumeration on projection + the combined pre-lock bonus (the weights of experiment A), under the
same rules as the ladder's best layer, 500 builds per week.

| Week | Within-10 line | Bonus: first top 1% / first top 100 / best | Projection only (1,000 builds): first top 1% / top 100 / best |
|---|---|---|---|
| 1 | 264.0 | 3 / **11** / **263.3** | 1 / 108 / 248.7 |
| 2 | 222.4 | never / never / 168.6 | never / never / 169.7 |
| 3 | 229.8 | 1 / **13** / **227.4** | 21 / 240 / 215.6 |
| 4 | 224.2 | 2 / **14** / 219.2 | 35 / 262 / 219.2 |

With the bonus the search reached the real top 100 within the first 11–14 builds in three weeks (against 108–262), and
came within 0.7 points (Week 1) and 2.4 points (Week 3) of the within-10 line; Week 2 is untouched. The winner's exact
lineup did not become more selectable (its gap to the best lineup under the rules is unchanged or wider: 9.7→12.4,
24.7→27.6, 9.8→10.9, 17.2→17.2): the bonus makes the top-100 region dense, not the winner's nine. **Two hindsights
remain:** the rules are each week's own winning rules, and the factors were chosen on these weeks.

### 3.4 The no-hindsight test — four generic environment forms, the same every week

`environment_forms.py`: sampled-world lineups under four forms fixed in advance (the QB's game is the top total or
ranks 2nd–3rd, × favourite or underdog), 125 per form, no stack or salary rule; a 32-row coverage book of the first
eight of each form.

| Week | Best per form (F1 top-fav / F2 top-dog / F3 2nd–3rd-fav / F4 2nd–3rd-dog) | Coverage book (32): top-1% rows / best | Projection order (32): best |
|---|---|---|---|
| 1 | 188.7 / 196.6 / 201.8 / 205.8 | 0 / 196.7 | 183.1 |
| 2 | 168.0 / 182.1 / 187.5 / 173.4 | 0 / 162.4 | 140.6 |
| 3 | 167.7 / 167.1 / 185.1 / 164.2 | 0 / 168.3 | 160.8 |
| 4 | 189.4 / 195.6 / 204.5 / 202.4 | 0 / 172.6 | 160.1 |

**Without knowing the week's environment, no 32-row book reached the top 1% in any week.** The coverage book's best
row beats projection order's in all four weeks, but by too little to matter at book size. The version with the factor
bonus inside the generic forms was stopped at 07:25 to yield the machine to another agent's twelve-worker job and will
be rerun when it is free.

## 4. What this means for choosing lineups

- **Nothing here changes the Week-5 book.** The factor bonuses are in-sample and weak out of sample; under Fantasy
  Points the market part is zero and the matchup and injury parts are largely inside the projection already. The
  things that address the pre-lock cases (Warren, Hockenson, Schultz) are armed: FP's projections with the 10:46
  post-inactives capture.
- **The binding problem is unchanged:** finding the winners' region needs the week's environment, and the environment
  is not knowable in advance; given it, a better player score (experiment B) makes the top 100 easy to reach. Given only
  the generic forms, 32 rows do not reach the top 1%.
- **For the projection (Week 6 onward):** add the position-level matchup with a prior-season fallback to the planned
  retrain (small, real, mostly RB and TE).



## 5. The operator's salary idea (10-07): "a preference to a lower-priced player that has high upside", not ruling out the expensive ones

Field check on the four real Millionaire fields (`cheap_upside_field.py`, BigQuery, results `run/experiments/cheap_upside_field.csv`):
the top-1% rate of real lineups by how many of three kinds of player they carried.

| Real field lineups, top-1% rate W1 / W2 / W3 / W4 | 0 | 1 | 2 | 3+ |
|---|---|---|---|---|
| cheap players (< $7,000) whose anytime-TD odds beat what their salary implies (top sixth) | .24 / .08 / 2.8 / .26% | .61 / .69 / 1.8 / .53% | 1.1 / 1.2 / 1.0 / .87% | 1.3 / 1.3 / .47 / 1.2% |
| cheap players our simulator rates high-upside (p90 − mean, top sixth) | 1.2 / 2.6 / .57 / 1.6% | 1.3 / 1.3 / 1.2 / 1.5% | .99 / .65 / 1.1 / 1.2% | .56 / .18 / .78 / .36% |
| $8,000+ players | .45 / .51 / .06 / 1.7% | 1.8 / 1.0 / 1.3 / .63% | — / 2.1 / 3.2 / .18% | |

The idea holds in three of four weeks when upside is the market's touchdown price relative to salary, and fails in all
four when upside is our simulator's ceiling (the reason the August "punt boost" was removed). The expensive players
helped in Weeks 1–3 and hurt in Week 4, so ruling them out would be wrong. This is a field pattern, not a construction
test: the replay of the live Week-5 book with a preference of up to +2 projected points for sub-$7,000 players whose
touchdown odds beat their price (`tdupside-…/replay_tdup.sh`) is armed to run when the machine is free.
