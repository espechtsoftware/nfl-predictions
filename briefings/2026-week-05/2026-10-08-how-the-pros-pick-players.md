# How the pros pick players: Fantasy Points, the betting market, and what else they use

2026-10-08, the outside reviewer, written for you. This is descriptive research plus suggestions. It changes nothing
on Sunday. No user names or Fantasy Points player values are in this public file. "The winner you follow" is the user
you asked us to study on 10-05 (label User15 in our files); the agents give you the name in chat.

**Your question (10-08):** "try to determine, of the professionals/leaders in major tournaments, when they appear to
be relying upon Fantasy Points projections and when it seems they are using different methodology. Then do deep
analysis on the different methodologies and then write a document of suggestions of approaches that seem promising.
The analysis of different methodologies should look into the available data points for a given player or game that
might have been used."

## The short answers

1. **Most pros follow a market-style projection. We can't tell whether it is Fantasy Points' own.** Fantasy Points'
   opinion of a player beyond his salary agrees with the betting props' opinion at 0.85, so the two mostly point at the
   same players. When they disagree, the regulars side with neither. For any one pro, the lean between Fantasy Points
   and props does not repeat when the data are split in half. What does repeat is how hard each pro follows *some*
   market-style projection.
2. **They lean on the projection for running backs, tight ends, expensive players and chalk, and hardly at all for
   quarterbacks and receivers.**
   - Projections explain 26–40% of their choices among running backs, tight ends, $7,000+ players and players projected
     15%+ owned.
   - They explain 3–8% among quarterbacks and wide receivers, $4,000–5,500 players and players under 5% owned.
   - Those choices follow stacking and their own habits.
3. **Their habits beyond the projection are about avoiding the crowd's mistakes, not about better projections.** These
   habits are:
   - selling last week's big scorers and salary risers;
   - distrusting matchup stats built on one to three games;
   - buying steady route and snap volume;
   - avoiding volatile players;
   - lightly fading what the crowd over-owns.

   The crowd does the opposite: it chases last week. Three seasons of history (2023–25) say none of these habits
   predicts points beyond the betting market.
4. **Their edge is about half "follow the market better than the crowd" and half "beyond the market".**
   - **Following the market:** the regulars' players beat the field's by about 4 points per lineup a week. About 1.9 of
     those points come from picking players the market rates higher than the crowd does at the same price. That part
     shows up every week.
   - **Beyond the market:** the other 2.3 points beat the market's own expectation. That part is positive every week but
     weaker evidence (p 0.03 over four weeks), and is concentrated at tight end and quarterback.
5. **A few data points did beat the betting market over three seasons, and neither the pros nor Fantasy Points appear
   to use them:**
   - the team's implied total (higher means more points and more big games);
   - the point spread (underdogs have more big games than projected);
   - wind (fewer points and fewer big games, about −1 point per standard deviation for quarterbacks);
   - end-zone-target dependence (more busts);
   - steady route running (fewer busts).
6. **The pros differ mostly in how hard they follow the projection, and the ones who follow it harder finish better on
   average.** Across the 117 regulars, that correlation is −0.64 with average finish percentile; lower is better.
7. **What it means for us:** our Week-5 setup already copies the robust half of their edge, because it uses Fantasy
   Points' projections and the winners' shapes. The promising additions are a small game-environment calibration on top
   of Fantasy Points, tail-aware tilts (big-game and bust signals) tested in the harness, and a recency-fade test. All
   are in §8.

## 1. What was measured, and how much it can bear

- **The pros:** the same 117 regulars as the 10-05 reports. Each entered 100+ lineups in every 2026 Millionaire,
  Weeks 1–4. They were chosen by volume, not by results. For Week 4 we added every user with 20+ Millionaire lineups:
  924 users.
- **The leaders:** each week's top 1% and top 0.1% of Millionaire lineups. They are chosen by results, so what they
  played mostly shows what boomed. They are reported, but they can't tell us anyone's method.
- **A pro's tilt on a player:** his share of the pro's lineups minus the rest of the field's share.
- **A source's "edge" on a player:** that source's projection minus what his salary implies, within position. Sources
  are Fantasy Points, the betting props and our own model. This is what the source says beyond the price.
- **The data points:** about 40 pre-lock facts per player from each week's 10:30 build frame, plus the 10-05 matchup
  panel:
  - usage, routes, red zone, aDOT and volatility;
  - Vegas totals and spreads, and wind;
  - opponent defense stats and Fantasy Points' matchup grades;
  - injuries and vacated targets;
  - salary change and last week's results.
- **Limits:**
  - Fantasy Points' projections were captured before lock only for Week 4, so the Fantasy Points questions rest on one
    week (about 140–260 players).
  - Weeks 1–4 use the betting props as "the market".
  - The three-season history uses props converted to DraftKings points (6,791 player-games). That is the best
    historical stand-in for Fantasy Points, which agrees with props at 0.85 beyond salary. It is not Fantasy Points
    itself.
  - About 40 data points were tested, so about 2 would look "significant" by chance at z ≥ 2. The strict bar is
    z ≥ 3.2.

## 2. Do the pros rely on Fantasy Points?

**Week 4: a pro's tilt per one standard deviation of each source's edge** (percentage points of lineups; fitted jointly
on the 142 prop-covered players).

| Group | Fantasy Points edge | Props edge | Our model's edge | How much the projections explain |
|---|---|---|---|---|
| The 117 regulars (pooled) | +0.68 (se 0.51) | +0.63 (0.52) | −0.05 (0.29) | 14% |
| Users with 150 lineups, not regulars (82) | +0.59 average | +0.37 | +0.01 | median 4% each |
| Users with 20–149 lineups (725) | +0.16 average | +0.33 | −0.02 | median 4% each |
| Top 1% / top 0.1% lineups (leaders) | +1.3 / +1.6 | −1.4 / −1.7 | ≈ 0 | 0–1% |

- **Fantasy Points and props weigh about equally, and our model's view is used by nobody.** Our model's edge agrees with
  Fantasy Points' at only 0.30, against 0.85 for props.
- **Individually it can't be told apart.** About half the regulars lean more on Fantasy Points' numbers and half more on
  the props. But each regular's lean has a split-half reliability of only 0.12: re-measured on another half of the
  players, it mostly flips. Only 4% significantly side with Fantasy Points and 3% with the props, about what chance
  gives.
- **Where they disagree, the regulars side with neither.** We took the third of players where Fantasy Points and props
  disagreed most (47 players). The regulars' slope toward Fantasy Points' side was −0.02 (se 0.43). On those players,
  props were slightly closer to the real result: average miss 6.62 against Fantasy Points' 6.93.
- **What is a real, stable trait is how hard a pro follows a market projection at all.** Its split-half reliability is
  0.56 in Week 4 and 0.76 across weeks (§6).
- **The leaders' lineups are not explained by projections** (R² about 0). The top 1% are the lineups that caught the
  week's booms, so this says nothing about anyone's method.

**So "relying on Fantasy Points" is best read as "relying on a market-anchored projection".** Fantasy Points, the props
and the commercial optimizers mostly agree. The pros' differences lie elsewhere.

## 3. When they rely on it, and when they don't

**Week 4, the regulars pooled: how much Fantasy Points' edge explains their tilt, by segment.** Segments are small, so
read the pattern rather than any single number.

| Segment | Players | Tilt per sd of Fantasy Points edge (pp) | Share of the tilt it explains |
|---|---|---|---|
| Quarterbacks | 24 | +0.36 | 8% |
| Running backs | 28 | +2.71 | 26% |
| Wide receivers | 68 | +0.37 | **3%** |
| Tight ends | 26 | +2.17 | 31% |
| Under $4,000 | 37 | +1.30 | 14% |
| $4,000–5,500 | 57 | +0.23 | **1%** |
| $5,500–7,000 | 40 | +1.68 | 21% |
| $7,000+ | 12 | +3.86 | **40%** |
| Projected under 5% owned | 90 | +0.18 | **3%** |
| Projected 15%+ owned | 13 | +4.66 | **36%** |
| Games in the top third by total | 52 | +1.64 | 25% |
| Games in the middle third | 38 | +0.52 | 2% |

- **They follow the projection when the decision is "which stud", "which running back or tight end", or "which chalk
  play".**
- **They leave it at quarterback and wide receiver, in the middle price band, and on low-owned players.**
  - Quarterback and receiver choices are tied together by stacking: you pick a game and a quarterback, and the receivers
    follow. The earlier reports covered that.
  - Mid-priced and low-owned choices are where the habits in §4 operate.

## 4. The other methodologies: which data points they lean on, and do they pay?

**Weeks 1–4, each data point on top of the props' edge, per one standard deviation.**
- **Regulars:** their tilt in percentage points of lineups.
- **Crowd:** the field's ownership, on a log scale.
- **Beyond props:** the player's points minus his props projection.

z is game-clustered: about 2 or more is notable, and 3.2 or more is strict.

| Data point (pre-lock) | Regulars | z | Crowd | z | Beyond props (pts) | z |
|---|---|---|---|---|---|---|
| Last week's DraftKings points | −0.72 | −3.4 | +0.57 | **+14.5** | −0.26 | −0.6 |
| Beat our projection last week | −0.90 | **−5.3** | +0.30 | +5.2 | −0.08 | −0.2 |
| Salary rise since last week | −0.84 | **−4.9** | +0.31 | +5.7 | −0.24 | −0.7 |
| Route share, last 4 games (Fantasy Points) | +0.52 | +3.2 | +0.37 | +9.2 | 0.00 | 0.0 |
| Snap share, last 4 games | +0.32 | +2.1 | +0.29 | +5.1 | −0.22 | −0.7 |
| Volatility (points sd) | −0.81 | −4.0 | +0.61 | **+14.5** | 0.00 | 0.0 |
| End-zone targets, last 4 games | −0.50 | −2.1 | +0.27 | +5.0 | +0.14 | +0.3 |
| Opponent's points allowed to the position, 2026 (1–3 games) | −0.76 | **−4.8** | +0.16 | +2.8 | −0.28 | −0.7 |
| Opponent's points allowed to the position, 2025 | +0.12 | +0.7 | +0.08 | +1.5 | +0.66 | +2.2 |
| Team implied total | −0.17 | −0.9 | +0.34 | +8.4 | +0.36 | +1.4 |
| Fantasy Points coverage grade (WR/TE) | +0.15 | +0.9 | −0.03 | −0.5 | −0.34 | −0.8 |
| Vacated team target share | +0.06 | +0.3 | −0.03 | −0.5 | −0.32 | −0.9 |
| The crowd's ownership | −0.58 | −2.6 | | | +0.38 | +0.8 |

**What it says:**
- **The crowd chases recency and volatility.** Its ownership rises sharply with last week's points and with volatile
  players: both z ≈ 14.
- **The regulars do the opposite on almost every one of those.** They sell last week's scorers and salary risers, distrust
  1–3-game matchup numbers, prefer steady route and snap volume, avoid volatile and touchdown-dependent players, and play
  a little less of what the crowd over-owns.
- **None of these habits predicted points beyond the props in 2026.** The one near 2 (last season's defense, +0.66) does
  not hold up in the three-season history (§7).
- **So the habits are leverage, not information.** They keep the regulars off players the crowd overplays for no
  scoring reason. At the same expected points, that means less shared ownership when those players hit, and a
  cheaper miss when they don't. This fits the 10-05 finding that copying the visible habits reproduces their salary
  spending but not their picking edge.
- **Week 4 alone, with Fantasy Points as the market, shows the same direction.** The regulars' tilts beyond Fantasy
  Points still sell recency (−0.29) and salary risers (−0.67), and buy route share (+0.48) and Fantasy Points' coverage
  grade (+0.65). That is one week, with no error bars.

## 5. Where the regulars' edge comes from

The 10-05 measure is points per lineup from picking: their share minus the rest's share, times each player's points
relative to his position and $1,000 salary band. Here it is split into the market's part (what the props expected,
relative to the band) and the part beyond the market. The players are the prop-covered ones (180 a week). The null
shuffles their tilts among players of the same week, position and band, 1,000 times.

| | Total | Market part | Beyond the market |
|---|---|---|---|
| Weeks 1–4, summed | **+16.6** (p 0.003) | **+7.4** (p < 0.001) | +9.2 (p 0.03) |
| Week 1 / 2 / 3 / 4 | +3.8 / +5.5 / +3.0 / +4.4 | +1.6 / +2.5 / +1.6 / +1.8 (each p ≤ 0.017) | +2.2 / +3.0 / +1.4 / +2.6 (each p 0.14–0.27) |
| Week 4 with Fantasy Points as the market | +4.1 | +1.5 (p 0.03) | +2.6 (p 0.19) |
| Quarterbacks, Weeks 1–4 | +2.0 | +0.2 | +1.8 (p 0.07) |
| Running backs | +5.3 | **+3.0** (p 0.001) | +2.3 (p 0.22) |
| Wide receivers | +1.9 | **+1.5** (p 0.007) | +0.4 (p 0.45) |
| Tight ends | **+7.5** (p 0.005) | **+2.8** (p < 0.001) | **+4.7** (p 0.02) |

- **The solid part is market-following.** It is positive and beyond chance every single week. At running back and wide
  receiver it is essentially the whole edge.
- **The beyond-market part is concentrated at tight end, with a lean at quarterback.** It is positive every week, but
  only the four-week total clears chance.
  - Tight end is also where the regulars' cheap-TE habit lives (10-05 report).
  - It is where our own model's opinion and the market's differ most.
- **Fantasy Points as the market gives the same split in Week 4** (market +1.5, beyond +2.6).

## 6. Different pro styles

Each regular's profile is his tilt on nine dimensions, fitted on Weeks 1–4, with props as the market. A dimension
counts as a person trait only if it repeats between Weeks 1–2 and Weeks 3–4.

| Dimension | Repeats (r) | Average regular | Regulars on the same side |
|---|---|---|---|
| **How hard he follows the market projection** | **0.76** | +1.63 pp per sd | 91% follow it |
| Plays against the crowd's ownership | 0.53 | −0.77 | 86% fade it |
| Prefers high or low team totals | 0.46 | +0.04 | split 60 / 40 |
| Avoids volatile players | 0.42 | −1.16 | 94% avoid |
| Pays up (salary level beyond the projection) | 0.32 | +0.88 | 95% |
| Route and snap volume | 0.29 | +0.49 | 91% (shared habit, weak trait) |
| Salary-change and recency fades | 0.22–0.25 | | shared habits, not individual traits |
| 2026 matchup numbers | 0.09 | −0.71 | everyone ignores them alike |

Four styles fall out of the stable dimensions (k-means). Results are four weeks, so they are suggestive only. Lower
finish is better; the field's average is 0.50.

| Style | Regulars | What defines it | Top-1% rate | Average finish |
|---|---|---|---|---|
| Disciplined market + leverage | 23 | strongest market following, strongest crowd fade, pays up | 1.66% | **0.426** |
| Steady volume, high totals | 46 | very low volatility, leans to high-total games | 1.41% | 0.438 |
| Moderate | 38 | middle on everything | 1.51% | 0.445 |
| With the crowd | 10 | weaker market following, plays the crowd's players | **2.20%** | 0.440 |

- **Market following is the trait most tied to results.** Its correlation with average finish is −0.64 across the 117
  (better finishes), and +0.27 with the top-1% rate. Following the projection harder raises the average lineup. The
  tail depends more on which booms you held.
- **The winner you follow is in the "moderate" style.**
  - He follows the market less than two thirds of the regulars (34th percentile).
  - He fades the crowd harder than three quarters of them.
  - He leans away from high-total games.
  - In Week 4 he leaned on the props more than on Fantasy Points, but individually that lean is unreliable (§2).

## 7. What beat the betting market over three seasons (2023–25)

These are 6,791 player-games of quarterbacks, running backs, receivers and tight ends with a 2+-market props projection.
Each data point was fitted alone, within season, week and position. z comes from resampling whole weeks. "3/3" means the
same sign in 2023, 2024 and 2025.

**Average points beyond the market, per one standard deviation:**

| Data point | Points | z | 3/3 |
|---|---|---|---|
| **Team implied total** | **+0.33** | **+3.4** (passes the strict bar) | yes |
| **Wind** | **−0.35** (quarterbacks −0.97) | −3.0 | yes |
| Route-share jump (last game vs 4-game) | +0.18 | +2.5 | no (2 of 3) |
| Spread (+ = favoured) | −0.22 | −2.4 | yes |
| Expected plays | +0.23 | +2.1 | yes |
| Game total | +0.24 | +2.1 | yes |
| Last game's points / beat the market last game | +0.10 / −0.07 | +1.0 / −0.6 | no |
| Salary change | +0.09 | +0.9 | no |
| Matchup stats from 1–3 games | +0.04 | +0.2 | no |
| Last season's defense vs the position | +0.04 | +0.4 | no |

**Big games and busts beyond the market.** Each is relative to the player's own projection: a big game is 1.6× or more,
a bust 0.5× or less. Base rates are 21% and 22%. The figures control for the projection's level.

| Data point | Big-game chance (pp per sd) | z | Bust chance (pp per sd) | z |
|---|---|---|---|---|
| Team implied total | **+1.9** | +2.9 (3/3) | −1.1 | −1.4 |
| Spread (+ = favoured) | **−1.8** (underdogs boom more) | −2.8 (3/3) | +1.1 | +1.5 |
| Wind | **−1.8** | −2.0 (3/3); −4.0 on the absolute definition | | |
| Top opposing cornerback out | +2.2 | +2.3 (3/3) | | |
| End-zone targets (touchdown dependence) | | | **+2.0** | +3.4 (3/3) |
| Expected fantasy points from opportunity (xFP) | | | +3.0 | +2.4 (3/3) |
| Fantasy Points route share | | | **−1.8** (steady routes bust less) | −2.2 (3/3) |
| Beat the market last game | −1.8 | −1.6 (3/3) | +1.8 | +2.2 (3/3) |

- **The game environment is under-priced by the player props.** Higher team totals, more expected plays and trailing
  scripts (underdogs) add points and big games. Wind takes them away.
  - Our own model uses the Vegas lines, but Fantasy Points' numbers replace ours from Week 5.
  - In Week 4, Fantasy Points' numbers minus the props showed no relation to team total (−0.01), game total (−0.07),
    spread (+0.04) or wind (−0.04). So Fantasy Points does not appear to add this adjustment either.
- **Recency matters only in the tails, and only a little.** A player who just beat his projection busts a bit more and
  booms a bit less next week. This is the one place the regulars' anti-recency habit has some support. On average
  points it is zero.
- **Touchdown-dependent receivers bust more than their projection says; steady route runners bust less.** This matches
  the regulars' preference for route volume over end-zone targets.
- **Two cautions:**
  - The history's "market" is props converted to DraftKings points. Part of the team-total effect could come from that
    conversion.
  - Only the team-total mean effect passes the strict multiple-testing bar. Wind passes on the absolute big-game
    definition (z −4.0).

## 8. Suggestions: approaches that seem promising

Each is a test first, under the adoption track. Nothing changes Sunday.

**S1. A game-environment calibration on top of Fantasy Points (class C; promising; small).**
- **What:** add to each player's Fantasy Points projection a fixed amount per standard deviation of team implied total
  (+0.33), game total and expected plays, and subtract for wind (about −1 per sd for quarterbacks).
- **Why:** this is the one effect that beat the betting market in all three seasons and passes the strict bar.
  Fantasy Points shows no sign of carrying it, and the regulars don't use it either. So it would be information the
  field's projections lack, not a copy of the field.
- **Size:** small. About a third of a point per standard deviation, larger for quarterbacks in wind.
- **Test:**
  - Freeze the adjustment from 2023–25 now.
  - Score it every Monday beside the frozen weekly Fantasy Points accuracy reader (Fantasy Points vs Fantasy Points +
    environment).
  - Run a paper book with it from Week 6.
  - A reversible trial once the pooled weekly check favours it.
- **Rollback:** drop the adjustment.

**S2. Tail-aware tilts for the big contests (class S; promising; harness first).**
- **What:** a bonus block in the same file format as the cheap +2 block (the term-block vehicle already in production).
  - Small bonuses for higher team totals, underdogs and a missing top opposing cornerback.
  - Penalties for wind, and for touchdown-dependent receivers whose projection rests on end-zone targets.
- **Why:** your goal is one big win, which is decided by big games. These signals moved big-game chances by about 2
  points in 21 at the same projection, consistently across three seasons.
- **Test:** a study-63-style harness study (2023–24 decides, 2022 go/no-go), frozen before any bank is read, against
  the live cheap block. Then a paper arm on live weeks.

**S3. Fade the crowd's recency picks, not chalk in general (class S; worth one test).**
- **What:** among players with near-equal Fantasy Points projections, prefer the one who did not just have a big game or
  a salary rise.
- **Why:** this is the regulars' most consistent habit. The crowd's ownership rises sharply with last week's points, and
  history says those points carry no information beyond the market on average, with a little extra bust risk. That
  makes recency-driven ownership ownership without value, and avoiding it makes a hit lineup more unique. This differs
  from the general ownership term that failed under Fantasy Points: it targets only the recency-driven part.
- **Test:** the same harness format as S2, as a separate arm. In the history, "last game beat the market" stands in for
  "beat our projection".

**S4. Keep Fantasy Points as the base; keep the props check running (no change).**
- The pros' main method is a market-anchored projection, and Fantasy Points is one. Our own model's view is the one
  nobody uses (weight about 0).
- On the 47 players where Fantasy Points and props disagreed in Week 4, the props were slightly closer. The frozen
  weekly Fantasy Points vs 50/50 Fantasy Points + props check from Week 5 is the right decision tool.

**S5. Spend our differentiation where the pros spend theirs (descriptive guidance for future shapes).**
- The pros follow the projection at RB, TE, studs and chalk. They differ through stacking (QB/WR) and the mid-priced,
  low-owned players. Our shapes already handle QB/WR through the winners' mix.
- Tight end is where the regulars' beyond-market edge is largest. Their cheap-TE habit, together with the
  pass-catching-TE screen from 10-07, is the natural place for a TE test if one is wanted. Study 63's TE arms leaned
  positive without a shown gain.

**What not to pursue:**
- Chasing or fading recency as a projection change (zero beyond the market on average).
- 1–3-game matchup numbers, and last season's defense vs position (zero in history).
- Our own model's opinion as a separate signal.
- Copying the habits wholesale (10-05: it reproduces their spending, not their edge).

## 9. Proposed next steps

1. **S1:** freeze the environment calibration from 2023–25 before any Week-5 result is seen, and add its line to Monday's
   accuracy read.
2. **S2 and S3:** one harness preregistration with both arms against the live cheap block, frozen and run this week if
   the lab's lanes are free, and read before the Week-6 decisions.
3. **Monday (10-12):** the first Week-5 rows are:
   - Fantasy Points vs props on disagreement players;
   - the regulars' tilts beyond Fantasy Points with a second Fantasy Points week;
   - whether any Sunday game had strong wind (compare Fantasy Points' numbers for it).

Scripts and the aggregate tables are in `reports/2026-10-08-pro-methods/`. They read private inputs; per-user outputs
stay private (`~/private/pro-methods/`).
