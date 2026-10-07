## 1. Week by week

Each week: the field, the winner and the cluster within 10 points; the attributes that were distinctive (cluster share
against field share, with the lift); the ladder (which rules were added, whether the rules can reach the winner at all,
and how deep the projection-ordered search went before its first top-1%, top-100 and within-10 lineup); the best lineup
the search built; and the reading. The full attribute tables and ladders are in Appendix A.

### Week 1 (winner 273.98 in a field of 831,028; two lineups within 10; top 100 at 244.8; top 1% at 209.0)

An outlier week: the winning score was 40 points above any other week's, and the 100th place would have won Weeks 2,
3 and 4. The two lineups within 10 were read together with the top 100.

**What won.** A *favourite* QB (79% of the top 100 against 34% of the field, 2.3×), from the *second- or third-highest
total* on the slate (89% vs 45%, 2.0×), *cheaply priced* (82% vs 49%, 1.7×); *nobody from the top-total game* (83% vs
38%, 2.2×); a running back in the flex (63% vs 43%); one bring-back (51% vs 36%). Stack size, salary left and the number
of cheap players were not distinctive.

**The ladder.** The unconstrained search built 1,000 lineups in projection order and never entered the top 1% (best
200.0). The shape rules alone added little (204.9). The environment rules (QB from the 2nd–3rd total, a favourite,
zero players from the top-total game) changed everything: the **first** lineup built was inside the real top 1%, the
108th scored 248.7, roughly 50th of 831,000, and nothing better followed in 1,000. The salary rule (cheap QB) was
already satisfied and changed nothing. The rules' oracle is 290.2, sixteen points above the winner, so the rules can
describe a winner; projection order reaches 248.7 and no further. No lineup came within 10 of 274.

**Best lineup built (248.7):** Bryce Young (CAR, $5,200, 35.4) with no Panthers teammate; Gibbs, Henry and Swift at
running back; Olave and Vele; a cheap tight end and defense.

**Reading.** Week 1's "strategy" is an environment call, not a stacking call: the cheap favourite's passing game in a
second-tier total, and fading the top-total game outright. It was reachable with the projection we played in one
build. Whether it is a strategy or a Week-1 accident is answered in §3: on Weeks 2 and 3 the same rules produced
nothing inside the top 1% in 500 builds, and on Week 4 one such lineup at build 259.

### Week 2 (winner 232.38 in 172,692; seven within 10; top 100 at 203.5; top 1% at 179.8)

**What won.** A tight end in the flex (86% of the cluster against 17% of the field, 5.1×, the largest lift in the
study) and a cheap tight end (100% vs 36%); the QB from the *top-total* game as the *underdog* (57% vs 22%, and 100% vs
68% underdog), mid-priced (86% vs 35%); no bring-back (71% vs 56%); no second stacked game; six or more games; a cheap
defense; one or two players from the top-total game. This is the regular-we-model's week (he won it), and the pattern
reads like his book: wide, two tight ends, the QB alone with one receiver, no bring-back.

**The ladder.** Nothing. Unconstrained 148.7; shape 164.1; environment 169.7; the salary layer identical; no pre-lock
ownership file for Week 2. Not one of 4,000 builds across the layers reached the top 1% (179.8), although the rules'
oracle is 255.0, twenty-three points above the winner.

**Best lineup built (169.7):** Prescott with two running backs who scored 8.0 and 4.6, two tight ends (5.3 and 29.0),
Smith-Njigba (45.5) and Jefferson (8.5), a Panthers defense that scored 26.

**Reading.** The rules describe the Week-2 winners exactly, and the projection cannot find them. The players who made
those lineups (a cheap tight end who scored, an underdog QB's lone receiver, six games wide) were not the projection's
picks under those constraints. Week 2 is the week where the gap is information, not shape. §3 adds that the full
Week-2 rule set does not even exist on the other three slates (no QB is at once the top-total underdog and mid-priced),
and that the environment rules alone found one top-1% lineup in 500 on Week 4 and none on Weeks 1 and 3.

### Week 3 (winner 239.80 in 161,682; two within 10; top 100 at 208.3; top 1% at 188.2)

**What won.** A *favourite* QB (72% of the top 100 vs 26%, 2.8×), *cheap* (93% vs 56%), from the *second- or
third-highest total* (77% vs 35%, 2.2×); *QB plus two teammates* (65% vs 36%) with *one bring-back* (57% vs 34%); a
tight end in the flex (70% vs 38%) and a *cheap tight end* (79% vs 32%, 2.5×); *nobody from the top-total game* (82% vs
50%); pre-lock ownership capped at 15–30% per player (98% vs 81%). The real top 100 of this week was 63% full game stacks,
and 81% of Geno Smith's top-1% lineups were the full stack with a bring-back.

**The ladder.** The one week where every rule layer moved the search closer. Unconstrained: nothing in the top 1%
(176.8). Shape (QB+2, one bring-back, TE flex): first top-1% lineup at build 812, best 193.2. Environment (QB from the
2nd–3rd total, favourite, no top-total players): first top-1% at build **44**, first top-100 at 459, best 211.3.
Salary (cheap QB, cheap TE): first top-1% at build **21**, first top-100 at **240**, best **215.6**, seven points above
the 100th place. The ownership rule changed nothing. No lineup came within 10 of 239.8; the rules' oracle is 256.8.

**Best lineup built (215.6):** Geno Smith (NYJ, $4,900, 30.0) with Sadiq (26.5) and Garrett Wilson (29.7), the bring-back
Parker Washington (JAX); Gibbs (41.4), Walker and Cook; Juwan Johnson (24.3) in the flex; a $2,500 defense. That is the
exact shape the week's winners used, with the right QB and the right game, found inside the first 21 builds.

**Reading.** Week 3 is the week the operator's picture holds: the winning pattern is pre-lock expressible, the rules
find the winning game stack early, and the remaining 24 points are the specific pass-catchers that went off against
the projection's choices. §3 shows it is also the rule set that transferred most strongly: on Week 1 it put a top-1%
lineup at build 3 and reached 236.8.

### Week 4 (winner 234.20 in 161,516; ten within 10; top 100 at 209.2; top 1% at 182.8; Fantasy Points projections)

**What won.** The QB from the *second- or third-highest total* (80% of the cluster vs 27%, 2.9×, the strongest single
rule of any week), a *favourite* (50% vs 38%); *QB plus one* (80% vs 45%) with *one bring-back* (70% vs 37%); a second
stacked game (100% vs 64%); five games (50% vs 27%); a tight end in the flex (60% vs 35%) and a *cheap tight end* (80%
vs 47%); one or two players from the top-total game (70% vs 46%); a cheap defense; pre-lock ownership sum under 80
(100% vs 83%). The real top 100 was 58% QB+1 with a bring-back, and 67% of Stroud's top-1% lineups were that shape.

**The ladder.** Unconstrained: first top-1% lineup at build 395, best 185.8. Shape (QB+1, one bring-back,
TE flex, five games, a second stack): first top-1% at 698, best 185.0, no better. Environment (QB from the 2nd–3rd total,
favourite, one or two players from the top-total game, cheap DST): first top-1% at **140**, best 199.5. Salary (cheap TE):
first top-1% at 122, best 199.5, the same lineups. Ownership (pre-lock ownership sum under 80, from Fantasy Points'
projected ownership): first top-1% at **35**, first top-100 at **262**, best **219.2**, five points short of the within-10
line (224.2) and ten above the 100th place. The rules' oracle is 249.0. This is the only week where the ownership rule
did anything, and it did the most of any rule in the week: it lifted the best build from 199.5 to 219.2 and the first
top-100 from never to build 262.

**Best lineup built (219.2):** Dak Prescott (DAL, $6,400, 21.1) with CeeDee Lamb (44.3) and the bring-back Nico Collins
(HOU, 33.8), the game the Week-4 post-mortem named as the one that decided the slate and that our entered book held no
slot in; a second stack from Minnesota (Jones, Hockenson 27.9 in the flex); Nacua (30.7); Brenton Strange as the cheap TE;
a $2,500 defense.

**Reading.** Week 4 is the operator's post-mortem rerun by rules: the pattern says "the favourite in the second- or
third-ranked total, one receiver and a bring-back, keep the whole book's ownership low", and under Fantasy Points'
projections those rules find the Dallas–Houston game stack inside the first 35 builds and a top-100 lineup by 262. It
is also the week where pre-lock ownership mattered: with the ownership-sum rule the search reached 219.2; without it,
199.5. That is the one place in this study where the ownership data the project now captures changed the answer.

## 2. The four strategies, as rules a Saturday builder could follow

| Week | The strategy (every rule is pre-lock) | In its own week | On the other weeks (§3) |
|---|---|---|---|
| 1 | The cheap favourite QB from the 2nd–3rd highest total; one bring-back; RB in the flex; no player from the top-total game | Top 1% at build 1; ~50th place (248.7) at build 108; never within 10 of 274 | W2 none, W3 none, W4 one top-1% at 259 |
| 2 | The underdog QB of the top-total game, mid-priced, alone with one receiver, no bring-back; two tight ends with a cheap one in the flex; six or more games; no second stack; cheap DST | Never inside the top 1% in 4,000 builds; the rules' oracle 255 | The full set is infeasible elsewhere; the environment set: W1 none, W3 none, W4 one top-1% at 371 |
| 3 | The cheap favourite QB from the 2nd–3rd total with two teammates and one bring-back; a cheap TE and a TE in the flex; no player from the top-total game; pre-lock ownership ≤ 30% per player | Top 1% at build 21; top 100 at build 240 (215.6); never within 10 of 239.8 | **W1: top 1% at build 3, 236.8**; W2 none; W4 none |
| 4 | The favourite QB from the 2nd–3rd highest total, alone with one receiver and one bring-back; a second stacked game; five games; a TE in the flex and a cheap TE; one or two players from the top-total game; cheap DST; pre-lock ownership sum under 80 | Top 1% at build 35; top 100 at build 262 (219.2); never within 10 of 234.2 | Environment rules: **W1: top 1% at build 185, 224.8**; W2 none; **W3: top 1% at build 41, 202.8** (line 208.3). Final rules (adding the cheap TE and, on W3, the ownership ceiling): W1 the same 224.8; W2 none (154.5); W3 top 1% at build 19, 203.4 |

## 3. Each strategy on the other weeks

[CROSS-TABLE]

Three things stand out. First, no rule set reached within 10 points of any other week's winner, and none reached the
top 100 of another week; the closest were Week 3's rules on Week 1 (236.8 against a 244.8 line) and Week 4's on Week 3
(202.8 against 208.3). Second, every transfer that did happen is among Weeks 1, 3 and 4, the three weeks won by a
*favourite in a second- or third-ranked total*: Week 3's rules found Week 1's top 1% at build 3, Week 4's found Week 1's at
build 185 and Week 3's at build 41, Week 1's found Week 4's at build 259. Third, Week 2, won by the *top-total underdog*
alone with one receiver, is reached by nothing built for the other weeks, and its own rules reach nothing elsewhere
(the full set is infeasible on the other slates; the environment set found one top-1% lineup in 500 on Week 4). The
winning environment is the lever, and it has at least two forms that no other week's rules anticipate.

## 4. What this says, and what it does not

1. **The winners' patterns are pre-lock expressible, and they change every week.** All four winning patterns were
   written as rules a Saturday builder could follow. Three of the four rule sets found the real top 1% of their own
   week within 150 builds once the environment rules were in (Week 1 at build 1, Week 3 at 44, Week 4 at 140); the
   fourth (Week 2) never did in 4,000. But the rules
   that won each week are different rules: top-total underdog in Week 2, second-tier favourite in Weeks 1, 3 and 4;
   QB+2 in Week 3, QB+1 in Week 4, no stack rule in Weeks 1 and 2; RB flex in Week 1, TE flex in Weeks 2 to 4.
2. **"Within 10 points of the winner" was not reached in any week by projection-ordered search, in-week or cross-week.**
   The rules' oracles (the best lineup the rules allow, built on actual points) exceeded every winner by 2 to 23 points,
   so the rules can describe a winner; the projection we played could not rank its way to one within 1,000 builds. The
   closest were Week 4 (219.2 against the line of 224.2, with the ownership rule), Week 3 (215.6 against 229.8) and
   Week 1 (248.7 against 264.0); Week 2 never came near (169.7 against 222.4).
3. **The one lever that transferred is the environment, and only between weeks that shared one.** Every cross-week
   success is among Weeks 1, 3 and 4, the second-tier-favourite weeks, and the strongest is Week 3's rules on Week 1
   (top 1% at build 3, 236.8). The environment rule (which total, favourite or underdog, how many players from the
   top-total game) is the pre-lock fact that most separates winners from the field in every week (lifts of 2 to 3×),
   and it is the one the build does not use today.
4. **What is usable now, as paper arms and not as a verdict:** (a) an environment-coverage rule in the builder, since
   the winning environment is unknowable in advance but has only a few forms (the top-total underdog; the second-tier
   favourite; the top-total favourite), so a book should hold rows built for each; (b) the cheap tight end in the flex,
   distinctive in three of four weeks; (c) a cap of two players from the top-total game (the winners held none of it in
   Weeks 1 and 3 and one or two in Weeks 2 and 4, never more); (d) in the FP weeks, a pre-lock ownership-sum ceiling on
   some rows, the rule that moved Week 4's search most. Each is a context column for study 38's harness and a Week-6
   question for the operator, not a Week-5 change.
5. **What it does not say.** Four weeks, patterns extracted from outcomes, 1,000 builds per layer: this is a map of
   what happened, not a forecast. The honest tests are the cross-week rows, and they say the winning environment of a
   given week is not predicted by any other week's.

## 5. The player-data question: what, before lock, separated the winners' players from the projection's picks?

The operator's question after the ladders: "exactly what kind of additional player data is needed to better select?"
The answer is testable on the data in hand, so it was tested (`attribution.py`, results in `run/attribution_*.csv`).
For each week, every slate player's share of the real top-1% lineups was compared with his share of the whole field
(the lift; 150–158 players per week with at least 0.2% field ownership), and his actual points with the projection we
played. Every pre-lock fact in the T−70 frame was then tested two ways: the difference between the winners' players
and the field's players on that fact, and the fact's slope on log lift after controlling for projection, salary and
projected ownership (pooled over the four weeks, with the sign counted per week). The same slope on the residual
(actual minus projection) says whether the fact predicted beating the projection.

| pre-lock fact (z-scored within week and position) | weeks | winners' players minus the field's (z) | slope of log lift, beyond projection, salary and ownership | mean t | weeks with the same sign | slope on actual − projection (points) | mean t |
|---|---|---|---|---|---|---|---|
| salary | 4 | +0.000 | -0.261 | -1.47 | 0 of 4 positive | +2.23 | +1.70 |
| proj | 4 | +0.045 | +0.171 | +0.91 | 4 of 4 positive | -1.91 | -1.27 |
| market_points | 4 | +0.066 | +0.113 | +0.86 | 2 of 4 positive | +0.92 | +0.84 |
| value | 4 | +0.106 | +0.200 | +0.82 | 3 of 4 positive | +1.76 | +0.94 |
| total_line | 4 | +0.147 | +0.060 | +0.86 | 3 of 4 positive | +0.44 | +0.64 |
| rz20_targets_l4 | 3 | +0.013 | +0.008 | +0.10 | 2 of 3 positive | +0.02 | +0.03 |
| rz10_targets_l4 | 3 | -0.005 | +0.028 | +0.33 | 2 of 3 positive | +0.45 | +0.67 |
| ez_targets_l4 | 3 | +0.035 | -0.001 | -0.01 | 1 of 3 positive | +0.21 | +0.31 |
| gl3_carries_l4 | 3 | +0.012 | -0.046 | -0.64 | 1 of 3 positive | -0.37 | -0.42 |
| gl3_carry_share_l4 | 3 | +0.012 | -0.070 | -0.83 | 1 of 3 positive | -0.38 | -0.44 |
| targets_l4 | 3 | +0.038 | +0.078 | +0.78 | 3 of 3 positive | +0.06 | +0.11 |
| target_share_l4 | 3 | -0.000 | +0.038 | +0.38 | 2 of 3 positive | +0.09 | +0.10 |
| target_share_jump | 2 | -0.127 | -0.088 | -1.14 | 0 of 2 positive | -0.91 | -1.30 |
| target_share_trend | 3 | +0.000 | +0.000 | +0.00 | 0 of 3 positive | +0.00 | +0.00 |
| snap_share_l4 | 3 | -0.020 | +0.053 | +0.67 | 2 of 3 positive | +0.05 | +0.09 |
| snap_share_jump | 2 | -0.046 | -0.100 | -1.25 | 0 of 2 positive | -0.97 | -1.58 |
| fp_route_share_l4 | 4 | +0.024 | +0.027 | +0.31 | 3 of 4 positive | +0.17 | +0.24 |
| fp_route_share_jump | 4 | +0.043 | -0.001 | -0.07 | 3 of 4 positive | -0.04 | -0.08 |
| team_vacated_target_share | 4 | +0.073 | +0.001 | -0.01 | 2 of 4 positive | -0.17 | -0.19 |
| team_vacated_carry_share | 4 | +0.001 | -0.046 | -0.71 | 1 of 4 positive | -0.07 | -0.01 |
| air_yards_share_l4 | 3 | +0.082 | +0.021 | +0.28 | 2 of 3 positive | +0.33 | +0.49 |
| wopr_l4 | 3 | +0.003 | +0.038 | +0.36 | 2 of 3 positive | +0.22 | +0.22 |
| depth_rank | 4 | -0.080 | -0.043 | -0.50 | 1 of 4 positive | -0.41 | -0.54 |
| xfp_l4 | 2 | +0.008 | +0.080 | +0.76 | 2 of 2 positive | +0.24 | +0.27 |
| pown | 2 | -0.045 | +0.046 | +0.20 | 1 of 2 positive | -0.29 | -0.20 |
| implied_team_total | 4 | +0.013 | -0.017 | -0.13 | 2 of 4 positive | +0.10 | +0.11 |
| pace_l4 | 3 | -0.035 | +0.063 | +0.86 | 3 of 3 positive | +0.25 | +0.41 |

Reading: **nothing in the lagged usage data separates the winners' players from the field's picks.** No fact clears a
pooled t of 1.5, and almost none keeps its sign across the four weeks. Red-zone targets inside the 20 and the 10,
end-zone targets, goal-line carries and share, route share and its jump, target-share trend and jump, snap share,
vacated opportunity, air-yards share, depth rank: each is within noise of zero, on both the lift and the residual.
The two faint signals are salary (cheaper players within a position slightly over-represented among the winners
beyond projection, and higher-priced players slightly beating our projection) and the game total (players in
higher-total games slightly over-represented), which is the environment finding again. The red-zone and touchdown
history the operator hoped would select the winners' players is already inside the projection, and the winners'
players did not differ on it.

**The one tail input not in the frame: the anytime-touchdown market** (`attribution_td.py`; the last prop snapshot
before each Sunday's lock, the price-implied probability averaged over books, 119–124 skill players per week). This is
the market's direct price on this week's touchdown, not last month's usage. Its slope on log lift beyond projection,
salary and ownership: Week 1 +0.24 (t 1.4), Week 2 +0.23 (t 1.8, and +2.4 points on the residual, t 2.1), Week 3 −0.16
(t −0.8), Week 4 −0.05 (t −0.3); pooled t 0.5. The touchdown-dependence ratio (TD probability per projected point)
showed nothing. So the market's touchdown price carried something our own projection lacked in the two early weeks,
when the projection was ours alone, and nothing beyond it in the two later weeks (Week 4 under Fantasy Points). It is
the best of the inputs tested and still not a consistent signal; it earns a weekly line, not a rule.

**A player's past top-1% frequency from the prior weeks' real fields** (`attribution_history.py`; the one player-level
input the winner-likeness score carries, there zeroed live because its history came from sampled fields): the mean of a
player's prior-week shares of the real top-1% lineups, tested on Weeks 2–4 (105–132 players with history). Raw, it
tells nothing about the current week's lift (correlation 0.01) because it is mostly a proxy for projection and
ownership (correlations 0.47 and 0.46). Beyond projection, salary and ownership it is weakly positive in all three
weeks: +0.11 on log lift (t 1.5 / 1.0 / 0.9, pooled 1.1) and about +1.0 point per standard deviation on beating the
projection (t 1.7 / 2.1 / 0.2, pooled 1.3). That is the best-supported player-level input in this study, and the
operator asked that it be tried in Week 5; the fixed-book replay and the Week-5 input file are in
`reports/2026-10-07-prior-top-term-replay.md`.

What this means for the gap: given the right game and the right shape, the winners' players looked, before lock, like
the players the projection chose instead. Their extra fifteen to twenty-five points were that week's variance, not a
usage fact the build failed to read. The levers that remain are the ones §4 names: cover the environments, add the
three structural rules, cap ownership in the FP weeks, and spread more rows under each form.
