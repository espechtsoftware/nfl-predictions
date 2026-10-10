# The qualifiers' history, where the 30-point games come from, and what this week's matchups say (2026-10-10, afternoon)

**For:** Erich, and the laptop and reviewers. Written by the outside model for three questions asked this afternoon: how much
history we hold on the 4444 / 555 / 333 qualifiers and whether the same people win them; what else could improve scores this
week; and how this week's matchups suggest plays. All numbers are from our own tables (the real standings in BigQuery, the
Week-5 feature table the model builds from, Fantasy Points' Week-5 captures summed by team). Aggregates only; no player names,
no per-player vendor values; the field's ownership is Fantasy Points' projection as of its 12:55 capture today.

## 1. The qualifiers: how much data, and do the same people win?

**How much.** Our standings table holds only 2026, Weeks 1–4 (86 contests, 1.66 million entries). Of the limited-entry kind you
ask about there are **12 contests in Weeks 2–4, 2,229 entries, 517 users**: four $4,444 contests (380–402 entries each, 12 per
user allowed), three $555 (68–72 entries, 2 per user), two $333 (79 entries, 2 per user) and three small FFWC satellites
(59–148 entries, 2–4 per user). Separately there are the two large FFWC qualifiers (Weeks 1 and 3, about 5,000 entries each,
150 per user), where the Millionaire regulars hold 53–56% of the entries. There is no earlier season to look at; DraftKings
publishes no per-user history we can read.

**Do the same people win?** On this data, no more than chance would give:

| Measure (limited-entry contests, Weeks 2–4) | Result |
|---|---|
| Users who played in 2+ of the three weeks / all three | 103 of 517 / 22 |
| Per-entry top-10% rate in a later week, for users who had a top-10% entry earlier vs not | 11.3% vs 10.1% |
| The same, chance benchmark (results shuffled among users with the same entry count) | 10.2% (95% range 7.5–13.2%) |
| Rank correlation of a user's mean finish across weeks | 0.04 (p 0.6) |
| Top-3 finishes: total / users / users with 2+ / across two different weeks | 37 / 29 / 6 / **1** |
| The top-3 finishers' other entries in these contests (307): mean finish, top-10% share | 49.7th percentile, 8.5% (the field: 50.3rd, 9.7%) |
| Entries per user in the contest for the 37 top-3 finishes | 1 entry: 34%, 2 entries: 33%, 12 entries: 35% (the $4,444 maximum) |
| The 117 Millionaire regulars: share of entries in your priority contests / share of top-3 finishes | 49% (mostly the two big qualifiers) / 21% |

**Reading.** Three weeks and 147 user-week pairs cannot rule out a small edge (anything up to about 1.3× would hide in this
sample), but the point estimate is chance: the people who finished top 3 did not finish better elsewhere, and only one person
has a top 3 in two different weeks. In the two big 150-max qualifiers the regulars' share of top-3s (21%) is below their share
of entries (49%). For you this means the one-seat contests are not a shark tank you must out-pick; they are a lottery among
reasonable lineups, which puts the weight on how many distinct, reasonable shots you hold and on duplication (rare there), not
on beating particular people. (A separate pooled look that included the 150-entry users showed "repeaters" at twice the rate;
that was volume, not skill: a user with 150 entries in both weeks has a top-10% entry in both by arithmetic.)

## 2. Where the 30-point games come from, against where the book's slots are

A big win needs about three players over 30 (the winning-score research). On the Week 1–4 main slates, among skill players
projected 5 or more:

| Price tier | Player-weeks | 30+ games | Rate | Share of all 30+ games | The Sunday book's skill slots |
|---|---|---|---|---|---|
| under $4,000 | 124 | **0** | 0.0% | 0% | **17%** |
| $4,000–5,999 | 379 | 7 | 1.8% | 25% | 27% |
| $6,000–7,999 | 145 | 16 | 11.0% | **57%** | 46% |
| $8,000+ | 13 | 5 | **38.5%** | 18% | 10% |

By other cuts: position QB 5.1%, RB 6.0%, WR 4.1%, **TE 1.0%** (1 of 105); realized ownership under 5%: 1.8%, 5–10%: 8.2%,
10–20%: 10.3%, 20%+: 14.3%; **projection rank within position: top 3 16.7%, 4–8 8.8%, 9–15 6.2%, 16+ 1.4%**; the player's game
by total rank: **rank 1: 1 of 52 (1.9%)**, ranks 2–3: 8 of 109 (7.3%), 4–5: 5.6%, 6+: 3.3%.

**Reading.**
- **The 30-point games come from the top-projected, owned, mid-to-high-priced players, in the second- and third-total games.**
  The slate's top-total game produced one 30-point game in four weeks; the next two games produced eight.
- **The cheap players produced none.** Their job is salary relief, and the field pattern behind the cheap block ("2+ sub-$4k
  players win more") is about the stars those slots pay for, not about the cheap players booming. The Sunday book spends 17%
  of its skill slots there, 10% on $8,000+ players; at the tiers' average boom rates that mix expects 0.74 30-point games per
  lineup. Three are needed. Lineups with two $8,000+ players and six mid-tier players would expect about 1.4.
- **Tight ends almost never reach 30** (Hockenson's 27.9 was the position's best game): the one-TE rule is consistent with this;
  a TE in the flex spends a slot where a boom is rarest.
- **This is why the stars rule and the game hedge are the two levers with a mechanism.** Both sit on paper this week (S2) or
  are available as one setting (QB cap 3). The harness read the stars rule worse on 2023–24 and Week 4 was a stars-bust week;
  Weeks 1–3 were the opposite. Nothing here changes what is armed; it tells you what Monday's paper arms are measuring.

## 3. This week's matchups, read with the signals that beat the market

The three-season history (the pros briefing §7) found four pre-lock facts that beat the betting market: the team's implied
total (+0.33 points per sd, the one that passes the strict bar), the spread (underdogs boom more, +1.8 points of big-game
chance per sd), wind (−0.35 per sd; −1 for QBs) and a top opposing cornerback out (+2.2 points of big-game chance, 3 of 3
seasons). Matchup statistics from one to three games (points allowed to a position, EPA allowed) carried nothing beyond the
market out of sample (odds 1.07 per sd), and the regulars ignore them. So the read below weighs the first four and treats the
defensive numbers as second-order.

**The Week-5 main slate (11 games; Philadelphia–Jacksonville is in London and off the slate), by game total, with the field's
Week-5 ownership as Fantasy Points projects it:**

| Game (total) | Implied totals, spread | Wind | The field's ownership (FP, share of the slate) | What the signals say |
|---|---|---|---|---|
| DET–ARI (54.5, late window) | DET 30.0 (−5.5), ARI 24.5 | 23 mph forecast, but Arizona's roof is usually closed; treat as nil unless open | **23% of all ownership on these two teams** (DET RB 35%, ARI WR 31%, ARI TE 35%, ARI QB 19%, DET QB 14%) | The highest implied total on the board by 4.7 points, the one strict-bar signal. Inside the game the field is on the DET running back; Arizona's defense allows the slate's worst pass efficiency (0.44 EPA per dropback) and a good run efficiency (−0.17), so the matchup favours the Detroit passing game over the back. Arizona as a 5.5-point underdog is the trailing-script side (its pass catchers are already 31–35% owned) |
| CIN–MIA (43.5) | CIN 25.3 (−7.0), MIA 18.3 | 9 | CIN receivers under 8%, CIN QB 3% | **The second-highest implied total, against the slate's worst pass defense by EPA (0.52 per dropback), with the receivers nearly unowned after last week's bust.** The clearest "environment plus low ownership" spot on the slate |
| LV–NE (45.5) | NE 24.5 (−3.5), LV 21.0 | 10 | LV RB 32%; NE QB 7%, NE RB 4%, NE WR 12% | New England is the under-owned favourite in a top-third total (FAVHI pairs its RB with its QB); Las Vegas's defense is sound both ways (−0.11 pass, −0.18 rush). The field's 32% on the Raiders' back runs into New England's −0.18 run defense |
| SF–SEA (45.5, late) | SEA 24.3 (−3.0), SF 21.3 | 9 | SEA WR 17%, SEA RB 14%; SF RB 10%, SF TE 10% | Seattle is the favourite (FAVHI's second RB); San Francisco's run defense is the slate's second-best (−0.28), so that pairing meets a strong run defense. San Francisco as the 3-point underdog is the trailing side at 10% ownership |
| CHI–GB (45.5) | CHI 23.5 (−1.5), GB 22.0 | 14 (Green Bay, outdoors) | CHI RB 28%, CHI WR 13%, GB WR 11% | Neither side is a 3-point favourite, so FAVHI does not apply. Green Bay's pass defense is sound (−0.11); Chicago's allows 0.18. Wind at 14 trims passing a little |
| IND–PIT (43.5) | PIT 23.3 (−3.0), IND 20.3 | 9 | PIT WR 11%, IND RB 14% | Indianapolis allows 0.23 per dropback; Pittsburgh's receivers are under-owned relative to projection |
| NYG–WAS (41.5) | WAS 22.5 (−3.5), NYG 19.0 | 13 | WAS WR 5%, WAS QB 3%, NYG TE 9%, NYG QB 1% | Both pass defenses are poor by the within-season numbers (0.23 and 0.26 per dropback) and both passing games are nearly unowned. The market's 41.5 says it does not believe it; second-order evidence only |
| MIN–NO (41.5, dome) | MIN 22.0 (−2.5), NO 19.5 | — | MIN RB 17% | New Orleans allows tight ends (+16 points above average by the within-season measure) |
| DEN–LAC (41.5, dome) | DEN 22.5 (−3.5), LAC 19.0 | — | LAC WR 15%, DEN WR 6%, DEN QB 4% | **Denver's top cornerback is out, the only such flag on the slate**: the Chargers' receivers get the one signal with a +2.2-point big-game lift in all three seasons. Denver's passing game is the under-owned favourite's side in a dome |
| CLE–NYJ (39.5) | NYJ 21.0 (−2.5), CLE 18.5 | 10 | NYJ RB 22% (the back behind 59% of vacated carries) | The field already knows the vacated carries |
| HOU–TEN (38.5) | HOU 22.8 (−7.0), TEN 15.8 | 10 | HOU WR 11%, HOU QB 3% | Houston's passing game is under-owned relative to projection; the game total is the slate's lowest |

**Three things this says about the armed book, as information for Monday rather than changes for today:**
1. **Fantasy Points' projections are flat against the implied totals.** FP projects 3.5–3.6 points per implied point for the two
   highest-implied teams (Detroit, Cincinnati) and 4.1–4.5 for low-implied teams; the market's team total is the one signal that
   beat the market in all three seasons, and FP's numbers do not carry it (the W4 check in the pros briefing found the same).
   The book will therefore hold less Detroit and Cincinnati passing than the market implies, and more of the low-implied
   teams' players at good prices. The frozen fix is study 64's environment calibration, on its weekly line from Monday and not
   usable before Week 8 by its rule.
2. **FAVHI's three pairs this week (Detroit, New England, Seattle) all meet good run defenses** (−0.17, −0.18, −0.28 EPA per
   rush). The rule passed twice in the harness on game script, not on the opponent's run defense; this week is a fair first
   real test of it, and the paper arm without it (NORBMATE) scores beside the book.
3. **Where the environment signals and the field disagree most:** Cincinnati's passing game (second-highest implied total,
   worst opposing pass defense, receivers under 8% owned), Denver and Houston's passing games (under-owned favourites), and
   the Chargers' receivers (the cornerback flag). Where they agree: the field's 23% on Detroit–Arizona, with the field heaviest
   on the one Detroit position the matchup favours least. None of this is a pick: the book takes players by Fantasy Points'
   projection per dollar under the rules, and the only lever that moves rows between games today is the QB cap (3 vs 5).

## 4. Limits

The qualifier history is three weeks and twelve contests. The 30-point table is four weeks and 661 player-weeks with 28 such
games; the $8,000+ tier is 13 player-weeks. Fantasy Points' Week-5 ownership is a Saturday-midday projection and will move with
the inactives; its projections here are the 10-08 capture. The within-season defensive numbers are four games old and read as
second-order evidence by the project's own history. The Arizona wind figure is the outdoor forecast; the stadium's roof decides
whether it applies.

## 5. Sources

`nfl_raw.contest_entries` (2026 W1–4) with the private contest typing file (types only); `nfl_features.player_week_inference`
(season 2026, week 5: lines, implied totals, wind, defensive EPA and points allowed, cornerback and line injuries, vacated
shares); `nfl_raw.fantasy_points_projected_ownership` (week 5, the 12:55 capture) and `nfl_raw.fantasy_points_dfs_projections`
(week 5, the 10-08 capture), summed by team; the Week 1–4 T-70 frames with the Millionaire's realized points; the pros briefing
§7 for the signals; `reports/2026-10-07-why-we-missed-the-winners-players.md` §3.0 for the out-of-sample matchup result.
