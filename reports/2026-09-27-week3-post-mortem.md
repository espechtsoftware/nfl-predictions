<!-- ERRATUM 2026-09-28: §0's claim that ~80% of the stake was in contests where an average 150+ lineup pays is wrong
     about the lines: the satellites paid at the 91st-99.8th percentile of their fields (see reports/2026-09-28-week3-review-and-major-changes.md §2).
     The selector finding (mean beats expected-max on the same pool) stands; what it buys at p99 lines is unmeasured. -->
<!-- Repo copy. The operator's stake and the dollar counterfactuals are in the private copy (~/week3-sunday/postmortem/REPORT.md
     on the workstation). Every points-based number here is complete. -->

# Week 3 post-mortem: why we lost, what the winners did, and what changes this week

Written 2026-09-27/28 by production, for the operator. Every number below comes from the 45 settled standings files
(loaded into the warehouse tonight), the Saturday D12800 run that was entered, the Sunday builds that were not, the
paper books, the Week-1 and Week-2 run dirs, and the 107-slate historical panel. Files: `~/week3-sunday/postmortem/`
(`players.csv` one row per player; `lineup_by_lineup.csv` one row per entered lineup; the rest are working pickles).

## 0. The result in one table

| | |
|---|---|
| Stake | private (45 contests, 204 entries) |
| Returned | one satellite ticket |
| Millionaire ($20 seat) | 127.58 points, rank 79,343 of 161,764 — the exact median. Cash line 149.5; top 100 needed 208; top 10 needed 220; winner 239.8 |
| Best lineup anywhere | 178.88 (won an 11-entry satellite) |
| Median finish over all 204 entries | 64th percentile (worse than average) |
| Our 144 distinct lineups | mean 120.5, 15 of 144 above the Millionaire cash line (10.4%) |

Two things were wrong at once, and they compound:

1. **The pool could not win the Millionaire.** The best of all 12,559 lineups we generated on Saturday scored 207. Nine
   scored 200+, and every one of the nine was a Geno Smith + Kenyon Sadiq stack. We entered none of them.
2. **Selection did worse than random inside our own pool.** 12.2% of pool lineups cleared the cash line; 10.4% of the
   144 we picked did. The order we entered them in carried no information (rank correlation with the actual score:
   −0.001).

Most of the money (about 80%) was in satellites and supersats where an *average* lineup score of 150+ pays and a
one-in-a-million tail does not. Our whole selection machinery optimises the tail of a simulation. That mismatch is the
single largest finding here, and it is the one with multi-week and historical evidence behind it (§6).

## 1. What the winners did (Millionaire, 161,764 entries)

Top 10 finishers, entries each: 10, 4, 150, 150, 150, 150, 1, 4 (same user as #2), 150, 5. The field: 55,340 users;
36,206 entered once; 17% of entries came from 150-entry users.

Structure of the top 100 versus the field versus us:

| | Milly top 10 | top 100 | top 1000 | field | OUR 144 |
|---|---:|---:|---:|---:|---:|
| Points | 225.6 | 213.5 | 199.7 | 128.5 | 120.5 |
| QB salary | $4,900 | $5,109 | $5,185 | $5,980 | $5,948 |
| QB under $5,500 | 100% | 93% | 88% | 40% | 38% |
| QB+2 stack | 100% | 79% | 74% | 32% | 100% |
| Bring-back | 90% | 75% | 69% | 41% | 100% |
| Max players from one game | 4.4 | 3.9 | 3.8 | 3.0 | 4.0 |
| Ownership sum (chalkiness) | 121 | 117 | 119 | 105 | 86 |
| TE salary | $3,500 | $3,860 | $3,935 | $4,266 | $4,325 |
| TE in FLEX | 100% | 70% | 57% | 38% | 52% |
| RB salary (2 slots) | $14,870 | $15,144 | $15,089 | $13,957 | $14,456 |
| WR salary (3 slots) | $19,620 | $18,472 | $17,921 | $17,437 | $17,155 |

The pattern is consistent from the winner down to the 1,000th place: **cheap QB in a stack, cheap TE plus a second TE at
FLEX, the savings spent on stud RB/WR, four players from one game, and chalkier than the field.** We matched them on
stacking and game concentration (our construction rules already force QB+2 and a bring-back) and were on the wrong side
of everything else.

**QBs in the top 100:** Geno Smith 66, Tyler Shough 13, Sam Darnold 8, Brock Purdy 7, Jacoby Brissett 4, Deshaun Watson 2.
Ours across 144 rows: Goff 12, Shough 12, Allen 12, Prescott 10, Lawrence 9, Daniel Jones 9, Lamar 9, Herbert 8, Geno 7.

**Kenyon Sadiq** ($3,500 Jets TE, 26.5 points) was in 21 of the top 25. He became the Jets' starting TE when Mason
Taylor was ruled out — news that existed Sunday morning, not Saturday. We had Sadiq in 4 rows, all from Sunday's
scratch swap (§4).

**The 150-entry winners** (User18 #3, User03 #4, User34/User26 #5, User24 #9) are not diversified: they put
60–73% of their 150 lineups on the same three or four players (Gibbs, Garrett Wilson, Jaylen Warren, Titans DST) and
varied the rest. Their portfolios averaged 138–152 points with 32–47% of lineups above the cash line; ours averaged
120.5 with 10%. That gap is not variance; it is which players and which shapes.

**The small-entry winners** did exactly what you proposed: User14 (2nd and 8th) entered 4 lineups that shared Kittle,
Jeremiyah Love and Garrett Wilson, with 3 of 4 also sharing Geno + Sadiq + Chase, varying only two or three slots; the
four averaged 214.7. User01 (the winner, 10 entries) had Gibbs in 9 of 10 and Wilson in 8 of 10.

## 2. Every lineup, one at a time

`lineup_by_lineup.csv` has all 144 rows: score, QB and price, stack points, bring-back, DST, 20+ scorers, sub-8 players,
ownership sum, the contests it was entered in, and the problems flagged. The problem classes and what they cost:

| Problem (rows affected) | Mean score of those rows | Mean of the others |
|---|---:|---:|
| ≥50% of skill slots in the seven low-scoring games (85 rows) | 112.1 | 132.4 |
| Stack (QB + same-team partners) under 35 points (54 rows) | 106.8 | 128.6 |
| Three or more players under 8 points (56 rows) | 105.5 | 130.0 |
| DST scored 5 or less (73 rows) | 117.7 | 123.3 |
| Expensive QB, $6,500+ (38 rows) | 114.1 | 122.7 |
| Contrarian build, ownership sum under 70 (18 rows) | 108.6 | 122.1 |
| Boom-world filler that never hit (11 rows) | 87.4 | 123.2 |
| No problem flagged (17 rows) | 136.2 | — |

Row 1 (the Millionaire seat, 127.58): Lawrence–Parker Washington–Strange stack (19 stack points), Bengals DST (3),
Hunter Henry (2), 75% of its skill slots in NE@JAX, HOU@IND and KC@MIA. It was the highest projected mean in the book.

Row 2 (84.6): Prescott ($6,700) + Lamb + Flournoy, Bengals, Achane (2), Schultz (6), Andrews (5). Four players under 8.

The Jets-heavy row 93 (176.0) you noticed: Geno + Garrett Wilson + Sadiq was the deliberate part. Jonathan Taylor,
Xavier Worthy and Devaughn Vele were not a strategy — that row is a "boom-world" build, which solves for the best lineup
inside ONE simulated world; the filler slots are whoever spiked in that world. Eleven such rows never hit anything and
averaged 87. The stack carried this one.

## 3. Every player we took who scored under 15

64% of our 1,296 player-slots (832) went to players who scored under 15. The heaviest, with what the data said before lock:

| Player | Rows | Price | Our proj | Market | Actual | Field own | What we can say |
|---|---:|---:|---:|---:|---:|---:|---|
| Titans DST | 51 | 2,400 | 6.9 | — | 7.0 | 26.9% | Scored its projection; the chalk DST. |
| Bengals DST | 47 | 2,900 | 8.2 | — | 3.0 | 12.4% | Our 2nd-highest DST projection; PIT offense ranked 30th by DK. The game went 57 points against a 42.5 total. Nothing pre-lock in our data, the props or Kalshi flagged it. |
| Amon-Ra St. Brown | 31 | 7,900 | 20.6 | 19.2 | 11.9 | 15.5% | Model above market by 1.4. |
| Jonathan Taylor | 31 | 7,600 | 18.6 | 17.1 | 9.2 | 6.4% | Model above market by 1.5; **DraftKings ranked HOU the 2nd-toughest run defence** and we took him 5× the field's rate. |
| Parker Washington | 30 | 6,000 | 14.8 | 13.2 | 13.0 | 17.0% | Model above market by 1.6. Near his projection anyway. |
| Ashton Jeanty | 25 | 7,100 | 17.5 | 16.6 | 12.3 | 15.7% | Favourable matchup (27th). Just missed. |
| Travis Kelce | 24 | 4,500 | 11.7 | 12.6 | 13.9 | 13.8% | Not really a bust. |
| De'Von Achane | 23 | 6,500 | 15.7 | 15.5 | 1.7 | 5.8% | KC 24–10 game script. No pre-lock signal. |
| Jameson Williams | 22 | 5,400 | 13.9 | 11.6 | 8.9 | 8.9% | **Model highest of every source** (market 11.6, Kalshi 10.4). |
| Dalton Schultz | 22 | 4,200 | 12.3 | 12.4 | 6.0 | 27.0% | **Did not practise**; the chalk TE. |
| Tetairoa McMillan | 21 | 6,000 | 13.5 | 13.0 | 3.7 | 9.9% | Bryce Young 14.6. |
| Hunter Henry | 20 | 3,900 | 9.7 | 9.6 | 1.5 | 3.2% | NE scored 6 points; Maye 6.8. |
| Seahawks DST | 17 | 3,800 | 9.4 | — | 2.0 | 5.8% | Our highest DST projection; the 39.5 total became 64. |

**Did the model's disagreements with the market predict the busts?** Weakly, and in one direction only. Where our
projection was at least 1 point *below* the market, players beat our projection by +3.5 (Week 3, n=15) and +7.1 (Week 1,
n=9): Jaylen Warren (we 12.2, market 15.1, actual 23.6) is the Week-3 example. Where we were above the market there
was no effect. The projection is as accurate as the market on average (MAE 5.93 vs 5.79) — it is not a bad projection;
it is a projection with no edge over what everyone can see, and a habit of undercutting the market on players it
discounts for injury or usage.

**DraftKings' opponent rank (OPRK):** on this slate its correlation with the residual was −0.05 to −0.14 by position:
Taylor (2nd, bust) and Chase (2nd, 24.8) cancel. It is not ingested anywhere in our features; our own matchup features
(`*_fp_allowed_adj_l6`) are. Neither carried information this week. Not a lever.

## 4. What happened Sunday, and the swap rule

At 10:44 Adonai Mitchell was OUT (5 rows, all Jets stacks). The same-team, same-slot swap put Sadiq in the one row
where Mitchell sat at FLEX and Isaiah Williams ($3,300, 3.1 points) in the four rows where he sat at WR, because a TE
cannot fill a WR slot. Sadiq scored 26.5. The rule was correct as written and wrong in effect: it never considers moving
the existing TE to FLEX to open the slot. Two rows also ended below our own $49k floor. This is a small fix (two-cell
swap) but the bigger fix is §6.2: a Sunday build already had Sadiq in the right places.

## 5. Games: which we missed, and what the market said

| Game | Market total | Actual total | Skill fantasy points | Share of our slots |
|---|---:|---:|---:|---:|
| NYJ @ DET | 48.5 | 55 | 229.7 | 15.7% |
| ARI @ SF | 47.5 | 66 | 227.6 | 7.2% |
| LV @ NO | 43.5 | 62 | 224.5 | 7.0% |
| **SEA @ WAS** | 39.5 | 64 | 211.1 | **1.1%** |
| **CIN @ PIT** | 42.5 | 57 | 209.3 | **5.0%** |
| BAL @ DAL | 53.5 | 65 | 198.7 | 11.5% |
| CAR @ CLE | 42.5 | 39 | 158.9 | 7.9% |
| **KC @ MIA** | 45.5 | 34 | 153.5 | **11.5%** |
| NE @ JAX | 46.5 | 41 | 148.8 | 8.5% |
| LAC @ BUF | 50.5 | 40 | 145.4 | 8.3% |
| **HOU @ IND** | 42.5 | 36 | 135.2 | **10.8%** |
| MIN @ TB | 42.5 | 39 | 122.5 | 5.3% |
| TEN @ NYG | 37.5 | 19 | 108.8 | 0.1% |

We were 2nd-heaviest in KC@MIA and 4th-heaviest in HOU@IND, the two worst offensive games, and nearly absent from
SEA@WAS (JSN 38.4, Darnold 32.7, Mariota 20.4) and light in CIN@PIT (Warren 23.6, Chase 24.8, Rodgers 23.7, Metcalf 12.1).

**Did anything foresee SEA@WAS?** No. The market total was the second-lowest on the slate (39.5). Darnold was 2.2%
owned, Mariota 0.3%. The field still had JSN at 18.9% because he is a stud WR1; we had him in 6.2% because at $8,600
our value ranking disliked him and the chalk fade cut him further. That is the general lesson of the studs: Gibbs 41.4,
JSN 38.4, Chase 24.8, CMC 21.6 — the two most expensive RBs and WRs beat their projections by 9–20 points, and
historically (107 slates) the $7,500+ tiers return the *most* points per dollar at RB and WR, not the least.

**Was the Bengals defence foreseeable?** Not from anything we hold. Our projection (8.2) was the 2nd-highest DST on the
slate; DraftKings ranked the Steelers offence 30th; the market total was 42.5. What we can control is concentration:
98 of 144 rows sat on two defences that scored 7 and 3. A 25% cap on any one DST costs about 0.3 points of simulated
expected max and removes that single point of failure.

**Shootouts and game stacks:** our construction already forces QB + two same-team pass-catchers + a bring-back, and
caps a game at four players, so a high-total game is stacked when the projections like it. What we do not do is weight
games by *their* upside once the projections are fixed; the winners' extra concentration (4.4 per game in the top 10)
came from the simulation-free habit of stacking the game you believe in. This is the core of your "3–5 cores with
variations" idea, and §7 Q4 turns it into a test.

## 6. Sorting and selection — the part that is not one week's luck

### 6.1 The selector
Our book is chosen by "expected maximum": the 144 lineups that together maximise the simulated best-of-144. That objective
deliberately sacrifices average score for coverage of simulated worlds. Measured against the simplest alternative —
take the 144 highest projected means from the *same* pool — on the two live weeks with clean projections and on the
107-slate historical panel:

| | Entered (expected-max) | Top-N by projected mean, same pool |
|---|---:|---:|
| Week 1 (K=80): mean / share above cash line / best | 146.6 / 30% / 207.1 | 169.7 / 55% / 214.5 |
| Week 3 (K=144): mean / share above cash line / best | 120.5 / 10% / 178.9 | 151.2 / 50% / 202.4 |
| Week 3 in dollars, same contests, same layout | [private copy] | [private copy] |
| Historical 107 slates (N=40 each): mean score per lineup | 118 | 125 (better in all six seasons, +4 to +10) |
| Historical: best-of-40 | 173.4 | 170.5 (expected-max better in 5 of 6 seasons, by 2–8) |

Week 2 is excluded from the live comparison because its projections carried the backup-QB availability defect (fixed
the following week); on that pool the top-mean lineups were full of players who did not play.

So the research verdict that adopted expected-max was right about what it measured (the tail of a 40-lineup book) and
costs 4–10 points of average score per lineup for it historically, and 23–31 points on the two clean live weeks. Our
money is not in the tail. The Millionaire is one $20 seat; the other [dollars: private copy] is in contests that pay an average lineup.

### 6.2 Saturday versus Sunday
Both weeks with a Sunday rebuild, the Sunday book beat the Saturday book we entered:

| | Saturday D12800 (entered) | Sunday 09:10 D3200 | Sunday 10:50 T-70 D800 |
|---|---:|---:|---:|
| Week 2: mean / row 1 / best / above cash | 98.4 / 82.6 / 158.0 / 6 | 106.1 / 102.3 / 171.5 / 11 | 105.9 / 97.3 / 166.7 / 9 |
| Week 3: mean / row 1 / best / above cash | 120.5 / 127.6 / 178.9 / 15 | 120.6 / 127.6 / 183.6 / 12 | 120.5 / 142.1 / 203.3 / 12 |

Sunday morning knew Mason Taylor and Mitchell were out; Saturday did not. The dose (12,800 vs 800) mattered less than
the freshness. But pool size does matter once selection is by mean: the Saturday pool's 2,560 leverage lineups are where
the high-mean candidates live (their mean was 137 vs 116 for boom lineups), and the Saturday pool re-selected on Sunday's
projections by mean scored 148.3 / [dollars: private copy]. The Week-4 speed-up of the leverage batch is what makes a large Sunday build
possible.

### 6.3 The entry order
The fewest-LOW order moved rows 98 (121.6) and 24 (128.9) into the shared top four and pushed row 4 (178.9) out to a
single satellite. The same 144 lineups in the book's own order would have returned [dollars: private copy]. Among the 25
pre-registered orderings scored tonight, ranking by the incumbent simulator's P(200+) would have put a 151-point row
first and averaged 137 over the top 30 (versus 121 for the order used).

### 6.4 Chalk: the fade never fired; the selector and the punt rule made us contrarian
Winners were chalkier than the field in both weeks we can measure (ownership sum 117 vs 105 this week; 123 vs 117 in
Week 2). Inside our own pools, lineups with ownership sum ≥100 averaged 133 vs 118 this week and 149 vs 136 in Week 1.
Our book averaged 86, the least chalky group in the table. Our exposure versus the field on the field's chalk: Walker
33% vs 44%, Garrett Wilson 13% vs 28%, JSN 6% vs 19%, Warren 2% vs 13%, Shough 8% vs 13%, Cook 6% vs 12%; our
over-weights were Bengals DST 33% vs 12%, Taylor 22% vs 6%, Achane 16% vs 6%, Hunter Henry 14% vs 3%, Jameson Williams
15% vs 9%.

I first wrote this up as the chalk fade costing us. It is not: the laptop showed on 09-22 that the fade never fired in
the Week-1 and Week-2 money runs (ownership was never passed, penalty 0.0), and the Week-3 frame shows the same — the
tournament objective equals the plain projection for every player above $4,000, including the most-owned (Walker,
Wilson, Schultz, Titans, Gibbs). Two other things made us contrarian:

1. **The expected-max selector** spends lineups on covering different simulated worlds, so it drifts away from the
   lineups everyone else builds; top-mean selection from the same pool is naturally chalkier (its 144 averaged an
   ownership sum near the field's winners).
2. **The punt valuation.** Every skill player at $4,000 or under is valued at roughly his 90th percentile in the
   leverage objective: average tournament value 8.9 against a 2.3 projection and a 2.3 actual (244 players; 7.4% of them
   scored 10+). The 2,560 leverage lineups therefore carry 3.7 such players each. It is a deliberate lottery rule from
   the research panels ("true-deletion tests cost tails"), and this week it bought Hunter Henry (valued 18.5, scored 1.5)
   and Ryan Flournoy (18.2 → 4.2) as readily as Juwan Johnson (17.5 → 24.3) and Fannin (17.5 → 24.1). It also values
   Jameis Winston at 24.4 and seven $4,000 backups who did not play at 10–11 (projection 0.0): 109 boom lineups hold
   Winston, and 399 boom lineups hold a sub-1-point player. None reached the entered book, but they waste pool.

### 6.5 What the winners' chalk actually was
The field's chalk was not blind: Walker 44% (21.3), Gibbs 27% (41.4), Garrett Wilson 28% (29.7), JSN 19% (38.4),
Warren 13% (23.6), Shough 13% (26.8), Cook 12% (23.4). The chalk that busted — Schultz 27% (6.0), Titans 27% (7.0),
Jeanty 16% (12.3) — we held too. So the field's collective read of the studs was better than ours, and the winners
leaned into it rather than away from it. Two of the three 2026 weeks say the same thing (Week 2 could not be scored
cleanly). The right experiment is not "fade off" (there is nothing to turn off) but whether a mild *tilt toward* field
ownership in selection helps (§10 Q4).

## 7. Positions and prices

Where our salary went versus the top 100: QB +$840, TE +$465, DST +$160; WR −$1,317, RB −$688. So yes, we overpay at
QB, TE and DST and underpay at WR and RB relative to what wins. But be careful with "cheaper QBs": historically
(107 slates) points per $1k at QB rise with price (2.44 → 2.87 → 2.89 → 2.91 from the $4.5–5.5k tier upward) and were flat
in Week 1; this week's cheap-QB sweep (Geno 30.0, Darnold 32.7, Brissett 25.6, Shough 26.8 against Allen 20.5 at $8,000)
was those players booming, not a law. What *is* systematic is the other side: RB and WR points per dollar rise with
price too (RB 1.78 → 2.29, WR 2.02 → 2.22), so salary saved at QB/TE/DST and spent on stud RB/WR loses nothing in
expectation and buys the ceiling the studs delivered (Gibbs 41.4, JSN 38.4). Our 6–7k RB tier (98 rows: Achane,
Javonte, Jeanty, Hubbard, Chase Brown, Hall) scored 11.4 against an 14.5 projection this week.

**RB:** the field paired Gibbs with Walker (305 of 875 top-1000 Gibbs lineups) or **Jaylen Warren** (293, $5,700, 23.6)
or Cook (136). We paired him with Walker 12×, Javonte 6×, Taylor 5×, Achane 5×, Jeanty 4× — and Warren 3× in the whole
book, because he was Questionable (flag rule) and our projection (12.2) sat below the market (15.1).

## 8. Data sources: Fantasy Points, SIS, Kalshi, Neo4j

**Kalshi** (captured Saturday and at T-70): its fantasy-point markets imply a median for 104 slate players. Those medians
were slightly *less* accurate than our projection (MAE 5.87 vs 5.76) and their disagreement with us had no relation to
what happened (correlation with the residual −0.03). No usable signal this week. The R5 capture continues; it is graded
from Week 6 as planned.

**Fantasy Points / SIS (§8a, the warehouse audit; full report `vendor_signals_report.md` beside this file).**
"Hardly used" is an understatement. The served projection uses none of the vendor data: the only vendor-derived
columns that reach the feature tables are Fantasy Points route shares, and they are candidate features that enter the
model only when a research job names them — the production jobs do not. No SIS table appears in the feature or
prediction SQL at all. Fourteen of the 22 vendor tables have no 2026 rows (last written mid-August); the seven with
2026 rows were all captured before lock (no leakage), but the three matchup tables are built on the vendor's 2025
full-season numbers. On this slate, against 161 skill players: the vendor signals showed a borderline excess of weak
correlations with our error (14 nominal hits from 110 tests, none surviving multiplicity), concentrated in one
cluster — 2025 per-route efficiency for WR/TE, a route-share jump with a *negative* sign, and SIS opponent pass-defence
bust rate. On the specific players: the data read favourably on St. Brown (8 green flags, 1 warning) and Jameson
Williams (6/1), no verdict on Taylor, warned against Addison (20.0, we had none) and Jeremiyah Love (21.9), and did
carry real warnings on Achane (SIS 2026: Miami's blocking worst on the slate) and Breece Hall. Refitting with
hindsight moves our heavy picks by a handful of ranks and leaves St. Brown first. The market was the better pointer:
props had Darnold 2 points above us and Bowers 3 above us. The only honest next step it supports is a preregistered
prospective shadow of the prior-season per-route efficiency prior and the route-share jump — never tuning on this slate.

**Neo4j (§8b).** It could not have found these patterns, because it has never contained the field. The graph on this
workstation is an index of *our own generated lineups*: a 54-slate historical slice (only the 279 lineups at 200+ loaded
as nodes), a 36-slate lab corpus, and the experiment registry. Every shard records contest results as "unavailable";
there are no winner, contest or settlement nodes. The 2026-08-11 review said the one thing that would justify a graph
was full-field standings — and those now exist in BigQuery (`contest_entries`: 994k Week-1 rows, 312k Week-2, and
Week 3 loaded tonight) and are read by nothing on the money path. Everything in §1 above was computed from that table
with plain pandas in minutes; the winners' structure does not need a graph, it needs to be looked at every Monday. What
the graph did contribute — that 220+ lineups are "broad" and our selectors pick "concentrated" ones — led to the
4-per-game cap; its one learned reranker (PREREG-096) reverted on real pools. The 09-10 review's own verdict stands:
use it as a lineage index, do not build more graph infrastructure.

**DraftKings' opponent rank (OPRK).** Not ingested anywhere: the DraftKings client keeps attribute 90 (points per game)
and discards −2 (OPRK). The Sunday 10:51 snapshot on disk carries OPRK for all 1,230 draftables, so it can be captured
from now on, but there is no history to backtest and on this slate it carried no signal (§3). Our own opponent-adjusted
"fantasy points allowed by position" is computed every week and has never been a model input; the ablation that
removed all defense features cost 0.008 points of error, so it is not a lever either.

**Shootouts, from the ledger.** Real shootouts do concentrate in high totals: both teams' top-3 scorers reach 60+ in
29% of games with a total of 48+ against 9% below 44. This week's exceptions (SEA@WAS at 39.5, CIN@PIT at 42.5) are
what makes them exceptions. Two simulator gaps matter here: the generation simulator's opposing-team factors are nearly
independent (realized cross-team fantasy correlation +0.21), and drive counts ignore the Vegas total because
`GAME_SIM_PACE=vegas` is not set. Both are cheap to test.

## 9. Small fields: why volume did not help

Nineteen $2 satellites of 11 entries each: our ranks were 1, 2, 5, 5, 6, 6, 6, 6, 7, 7, 7, 8, 8, 9, 9, 9, 11, 11, 11 —
average 7.1 of 11, worse than a coin flip. The winning scores ran 160–206 (median 166). The top-mean book would have
won 17 of the 19 (its rows scored 167–187 where ours scored 84–179). Volume multiplies whatever the average lineup is
worth; at 120 it multiplies a loss.

## 10. Two tracks from one pool (operator, 2026-09-27 evening)

You will again be mostly in satellites with a couple of Millionaire shots, and you do not want to be forced into one
objective. The data says that is right: the satellites pay the average lineup, the Millionaire pays the tail, and one
selector cannot serve both. Design:

- **`contests.json` gains `"track": "mean" | "tail"`** per contest (default `mean`). Satellites, supersats, wildcards
  and qualifiers are `mean`; the Millionaire seats (and any other large-field GPP you choose) are `tail`.
- **One pool, two selections.** The Sunday build's pool is selected twice: the mean track takes the K highest
  projected means with the existing overlap cap (≤7 shared players), ordered by mean; the tail track takes T rows by
  simulated probability of clearing a Millionaire line (210 as the working line — the top 100 needed 208 this week),
  from the whole pool, duplicates with the mean track allowed. The book is rows 1..K (mean) then K+1..K+T (tail).
- **Layout.** Head-layout contests draw from the mean rows as today (shared top four, unique rows for the rest);
  `tail` contests draw only from the sleeve rows, with explicit `ranks` pins allowed inside it. The injury protection
  (clean rows in the protected ranks) stays; the fewest-LOW reorder goes (row order = mean order).
- **What each track gets.** Mean track: this week's counterfactual is the top-mean book (mean 151, 50% above cash,
  17 of 19 small satellites won). Tail track: no honest claim of an edge — the pool's best was 207 and the seats are
  lottery tickets — but the selection at least aims at the right target, and the two Millionaire seats no longer
  dictate the other 200 entries.
- **Timing.** Sunday 09:10 build at the largest dose the leverage speed-up allows; fallback: the Saturday D12800 pool
  re-projected at T-70 and re-selected by both tracks (this week that gave mean 148).

## 10a. Quick experiments, most already read

Each item is a small, reversible change with a same-day read on the three live pools and, where possible, the 107-slate
panel. None needs a new model. The first three are already read above; they need your yes/no, not another week.

| # | Change | Evidence so far | Read needed before entry | Owner |
|---|---|---|---|---|
| Q1 | **Mean track:** select the satellite book by projected mean (top-K from the pool, overlap ≤7 as today); **tail track:** T Millionaire rows by simulated P(≥210) | W1 +23, W3 +31 points per lineup; [dollars: private copy]; historical +4–10 mean, −2..−8 on the tail | A `mean` selector and a `--tail-sleeve` in the lab builder; `track` in contests.json and the layout; a rehearsal | laptop (lab), production (layout) |
| Q2 | **Order rows by mean** (row 1 = highest); drop the fewest-LOW reorder; keep flags only for OUT/IR/D | [dollars: private copy] this week; the order used had zero rank correlation with results | None | laptop |
| Q3 | **Enter a Sunday build**, not Saturday's: 09:10 D3200 (or larger with the lazy-cuts speed-up); Saturday's pool kept only as a fallback re-selected by mean at T-70 | Sunday beat Saturday on both weeks measured | A timing rehearsal (build + select + fill inside 09:10–11:15) | laptop |
| Q4 | **Ownership tilt in selection:** rank the pool by projected mean + λ × ownership sum, λ small (the field's Millionaire ownership is known Saturday from the sets file; the live projected ownership from `own_shadow` is the pre-lock source) | Winners chalkier than the field both weeks; chalky pool lineups +15 (W3) and +14 (W1); the fade itself never fired, so there is nothing to switch off | Score top-144 books at λ ∈ {0, 0.1, 0.2, 0.3} on the W1 and W3 pools; adopt the smallest λ that is not worse on both | laptop, Mon |
| Q4b | **Punt valuation, availability-aware:** value a sub-$4,000 player at his upside only if his projection is above 1 point (non-players at 0), and test the p90 valuation against the plain mean for the leverage batch | 3.7 punts per leverage lineup; 399 boom lineups hold a non-player; Winston valued 24.4 | Two leverage batches (640) on the W3 frame — p90 vs mean valuation — scored as mean-selected books; ~20 min each with lazy cuts | laptop, Tue |
| Q5 | **DST cap 25% of rows**; no other caps | 98 rows on two DSTs scoring 3 and 7; the cap costs 0.3 simulated points | None | laptop |
| Q6 | **Market floor:** where the market is ≥1 point above our projection, use the midpoint | +3.5 (W3) and +7.1 (W1) residual in that group; MAE no worse | Score the top-mean book under both projections on W1/W3 pools | laptop, Mon |
| Q7 | **Two-cell swaps** (move TE to FLEX to open a WR slot for a starting TE) | Sadiq 26.5 in 1 of 5 Mitchell rows | Unit test + rehearsal | laptop |
| Q8 | **Core + variations generator:** 3–5 cores (QB stack + 2 studs) × variations over TE/DST/cheap flex, selected by mean | The small-entry winners' shape; our pool's 200+ lineups were all one core. Prior evidence is mixed: "core + one-player swaps" around the expected-max book's core was far weaker than the book's own top ranks (7.7% vs 24.6% at 180 over 65 slates), and the Week-2 study's verdict was "we varied widely around a wrong core; they varied narrowly around a right one" — the core must come from the mean/market, not from the tail selector | Prototype as a selection filter on the W3 pool first (cluster top-mean rows by shared 6-player core; keep the best 3–5 cores × up to 10 variations) | laptop, Wed–Thu |
| Q10 | **Simulator pace from the Vegas total** (`GAME_SIM_PACE=vegas`) and a cross-team correlation check | Drive counts currently ignore the total; realized cross-team fantasy correlation +0.21 vs ~0 simulated | Same-image A/B on one live frame, boom-pool composition and mean-selected book | laptop, Wed |
| Q11 | **Millionaire winners' portfolio anatomy and emulation** (§12): measure every ≥20-entry top-100 user's portfolio shape over Weeks 1–3, test persistence, then build a 150-lineup portfolio from our pool that matches the shape and score it on each week | The top-10 150-entry users: 60–73% on the same 3–4 players, chalkier than the field, mean 138–152, cash 32–47%; the tail-track sleeve from our simulator picked 110–137-point rows | A report by Wed; the emulation read by Thu; the tail track for Sat 10-03 follows what it finds | laptop, Mon–Thu |
| S1 | **Fail-loud build audit** (`scripts/audit_build_levers.py`, wired after the receipt check): every declared lever must leave its trace, no undeclared lever may, no candidate may hold a non-player, declared sources must be present, selector/tracks/book must agree | Run on the Week-3 D12800 run dir tonight: FAILS on 438 non-player candidates and 87 non-players valued at upside, passes the other eight checks | The laptop rehearses it on the Week-4 smoke; it must fail until Q4b lands and pass after | production (built), laptop (rehearse) |
| Q9 | **Contest mix:** stake concentrated where a 150-average book pays (satellites/supersats), Millionaire seat kept at one | The Millionaire top 100 was unreachable from any pool we built | Your call | operator |

## 11. Dress rehearsal (operator ask, 2026-09-27 evening): the Week-4 process replayed on Weeks 2 and 3

The exact Week-4 process — one pool, the mean track selected by projected mean (overlap ≤7), the tail track by
simulated P(≥210), the head layout with the week's contests, placed into the real fields — replayed on this week's
Saturday pool (K=147 mean rows, 3 sleeve rows for the Millionaire seat and the $18 qualifier):

| Process | Mean track: avg / row 1 / best / above cash | Tail rows | Return |
|---|---|---|---|
| What we did (entered) | 120.5 / 127.6 / 178.9 / 15 of 144 | — | [private copy] |
| A. Two tracks: plain mean + P(≥210) sleeve | 151.4 / 127.6 / 202.4 / 74 of 147 | 128, 110, 137 | [dollars: private copy] |
| B. Same, mean + 0.1 × ownership sum | 156.8 / 171.8 / 202.4 / 92 of 147 | same | **[dollars: private copy]** |
| B at 0.2 / 0.3 | 154.7 / 153.9 | same | [dollars: private copy] |
| C. Cores anchored in the top-3-total games, 3 cores × 20 variations, mean fill | 148.8 / 108.3 / 203.4 / 68 of 147 | same | [dollars: private copy] |

The exact rule behind A (for the laptop's reproduction): rank the pool by the frame's projected sum over the lineup's
nine players (`sel_mean` in `candidates.parquet` is that sum exactly, correlation 1.000), take the top K greedily with
pairwise shared players ≤ 7 (the cap changed one pair this week: 151.2 → 151.4), order rows by the same sum; the tail
sleeve is the top T by P(total ≥ 210) over the two persisted score banks (`incumbent_player_scores.npy` +
`corrected_hsim_player_scores.npy`, equal mass), duplicates with the mean rows allowed. Week 1 under the same rule:
169.7 average vs 146.6 entered (55% vs 30% above the cash line).

The tail sleeve chose 128/110/137-point lineups: no lineup in the pool could reach the Millionaire's top 100, so the
sleeve did what it could, which was nothing (§12 is the answer to that). The core-of-top-games form lost to the plain
mean this week: the market's highest totals included a dud (LAC@BUF 50.5 → 40 points) and every core it built carried
the Bengals DST. It gets one more form in Q8 (DST outside the core; mean ordering inside).

**Week 2** cannot be rehearsed cleanly on its Saturday pool: 19 quarterbacks projected 10+ points scored zero (the
backup contract defect, fixed the following week), so a mean selection from that pool picks non-players (mean 70). On
the Sunday 09:10 pool, which had two such quarterbacks, the two-track mean book scores 102.3 average against the 98.4
entered — a wash. Week 2 was the week the pool held nothing (its post-mortem said so; the field's cash line was 138);
the process change would not have rescued it, and the Sunday build was the only thing that helped there.

## 12. The Millionaire: reverse-engineering the winners' pools (operator directive, 2026-09-27)

"It not being possible is not an option." Agreed, and the data to do this properly now exists on our side: every lineup
from three Millionaires (Weeks 1–3, ~1.1 million entries) with the user behind each one, so the multi-entry winners'
whole portfolios are measurable, week after week. Tonight's first look (§1) already says: the 150-entry users who
finished top-10 are not diversified — 60–73% of their lineups share the same three or four players — they are chalkier
than the field, they run 10–25 quarterbacks, and their portfolios average 138–152 with 32–47% above the cash line; the
small-entry winners build 3–5 lineups around one core and vary two slots. That is the behaviour of a simulation-driven
builder with exposure targets and no fade, not of a coverage selector.

The study (laptop, this week; a report, then an emulation test):
1. **Portfolio anatomy** for every user with ≥20 entries who finished top-100 in any of the three Millionaires, and
   for a matched sample who finished mid-field: exposure concentration (share on the top 1/3/5 players), ownership
   profile versus the field, quarterback count, stack and bring-back rates, game concentration, salary allocation by
   position, pairwise overlap distribution (how many "cores", how the variations are made — which slots vary), share
   of lineups that are unique in the field, and the portfolio's mean / cash share / best.
2. **Persistence:** the same usernames across the three weeks — is a good portfolio shape a stable trait (a process)
   or a one-week draw?
3. **Emulation:** build a 150-lineup portfolio from OUR pool that matches the winners' shape statistics (exposure
   targets, chalk level, core count, variation pattern) and score it against theirs on each week. If we can land in
   their class of average score and cash share from our own projections, the remaining gap to the top 10 is the
   projection edge, which is then the next study; if we cannot, the shape is not the explanation and we say so.

This is Q11 in §10a.

What I would **not** change on this evidence: the projection model itself (as accurate as the market), the stack rules,
OPRK (no signal), cheap-QB-as-a-rule (one week), Kalshi (no incremental information).

Rules that are in the way and should be relaxed for these: the six-season-panel gate for *permanent* adoption stays,
but Q1–Q3 and Q5 are reversible entry-path switches with two-week live evidence and a historical read, and the
in-season adoption track (2026-09-19) allows exactly that.
