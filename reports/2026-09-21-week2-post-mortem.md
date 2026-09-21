# Week 2 (2026-09-20 Sunday main slate) post-mortem

Written 2026-09-20 evening by the workstation assistant for the operator and for the labs' review. Realized points are
the DraftKings FPTS carried in the 12 standings exports the operator downloaded on Sunday evening (identical across all
12 exports; raw files under `/home/erich/week2-sunday/ENTERED/standings/`, never committed). The nflverse Week-2
actuals were not loaded when this was written (`player_week_actuals` held 92 Week-2 rows), so the proper-score items
of the evidence record stay TODO for Monday. Everything here is one slate of evidence; it is descriptive under the
in-season adoption track (class R = repair, class C = candidate rule for a reversible trial, class E = execution). The
operator decides what is adopted. Shareable derived tables (no usernames, no entry ids) are on the reply branch under
`handoffs/receipts/2026-09-21-week2-post-mortem/`; the names used below are DraftKings display names.

## 0. Summary

**Result.** 97 entries, $246 in fees. Best finish: Flea Flicker rank 7,277 of 83,234 (top 8.7%, at most a minimum
cash). 7 of 97 rows finished inside the top 20% of their field, 1 inside the top 10%, 18 inside the bottom 10%; 65% of
rows scored below their field's mean. Best score 156.16; the fields' winners scored 200-235; our mean row scored 105.0
against field means of 113-120. No row came within 30 points of a ticket or a top-1% line anywhere.

**Three compounding causes, in order of size.**

1. **A top-of-board projection failure with one player at its centre, caused by a name-matching miss and a
   fallback rule.** Justin Jefferson was served at 25.3 points, the highest projection on the slate, while the props
   market said 16.4 (79 receiving yards, 6.5 receptions, 35% anytime TD at two books). Production's prop-name matcher
   on the main tip dropped him: the normalized spelling "justin jefferson" maps to two GSIS ids in the 2026 roster
   union, the matcher refuses ambiguous spellings, and the blend then silently substituted his DraftKings
   points-per-game, which after one game is his Week-1 score of 31.2, as the "market" at 55% weight:
   25.3 = 0.45 x 18.1 (the model) + 0.55 x 31.2. The model itself had him near 18, in line with the market. The same
   miss pulled DeVonta Smith the other way (model 18.3, fallback 8.3, served 12.8; he scored 30.7). The divergence
   shadow logs only prop-sourced rows, so the instrument built to show model-vs-market gaps was blind to exactly the
   two players that fell through. Confirmed two ways: re-running the main-tip market function on the Week-2 prop rows
   (447 player rows; Jefferson and Smith absent, Lamb present at 16.66) and the projection job's own log for the
   16:02Z run ("market blend source: props (388/481 rows)", "div-shadow: 211 rows logged"). He then scored 8.5 in the
   windiest game of the slate (14 mph at Chicago; MIN-CHI produced the fewest skill points of all 13 games).
2. **Concentration.** Six players sat in 25-57% of the book and all six busted: Jefferson 55 rows (8.5 pts), Bijan
   Robinson 45 (11.1), 49ers DST 39 (8.0), Javonte Williams 28 (8.0), Ladd McConkey 28 (6.5), Drake London 26 (8.9).
   Rows holding one of the six averaged 116 points; rows holding three averaged 92. The generator started it (Jefferson
   in 48.5% of the 12,555-candidate pool, the 49ers in 60.7%) and the selector amplified it (57% and 40% of the book).
   McConkey (Questionable, cracked rib, no prop lines posted, 1.2% field ownership) was the clearest case, but he was the
   fifth-largest exposure, not the first.
3. **We faded the chalk that hit and were contrarian where the market disagreed with us.** The winners were chalkier
   than the field (top-1% ownership sum 126 vs field 117 vs ours 99). Derrick Henry (37.5% owned, 17.7 pts), Christian
   McCaffrey (22.8%, 22.6), CeeDee Lamb (19%, 38.3), Dak Prescott (13%, 29.8), Brock Purdy (9.5%, 28.5) and Aaron Jones
   (21.6%, 13.5) were held at 4-10% here. Among our 44 largest exposures the served projection exceeded the market in 31;
   across the slate, players we projected 2+ points above the market (n = 17) scored 3.5 below projection on average
   (corr(proj - market, realized - proj) = -0.29 over players projected 12+).

**It was not bad luck within the pool.** 222 of the 12,555 delivered candidates scored 150+ and the best scored 197.26
(a boom row with simulated mean 116 that was never ranked). The stored `sel_mean` was inverted against reality across
the pool: corr = -0.49; the top decile by that mean (139.7) realized 69.8 on average, the bottom decile (111.5)
realized 109.3. The laptop's independent attribution (`receipts/2026-09-21-independent-review/`) shows the stored
`sel_mean` is the incumbent component's mean, not the pooled decision score: incumbent -0.488, corrected HSIM -0.087,
equal-mass pooled -0.332. The severe inversion is mostly the incumbent law; both components were poor on this slate;
no weight change follows from one slate. Ninety-seven random rows from the pool would have averaged 92 with a
best of 159; greedy-by-mean with a 25% per-player cap would have averaged 106 with a best of 184 and eight rows at 150+;
the entered book averaged 105 with a best of 156 and one row at 150+.

**What the winners did.** Every major's top ten was built on Jaxon Smith-Njigba (45.5, 10% owned), CeeDee Lamb (38.3,
19%), Dalton Schultz (29.0, 22%), Dak Prescott or Brock Purdy, Aaron Jones Sr., and the Panthers or Patriots DST, at
$49,900-50,000 salary, with 3+ players priced $7,000+ in half of the top-1% rows (field 24%, ours 13%), 4+ late-game
players (top 1% 4.07 per row; field 3.26; ours 3.36 overall, 2 in the Millionaire row, 1 in the Pylon row), 5.4
distinct games per row (ours 3.7), one same-team pass-catcher with the QB in 57% of rows and two in 30% (ours: 90% two,
10% three), and a bring-back in 41% (ours 100%). Max-entry (150) users were 17% of the Millionaire field and 32% of
its top 1% (lift 1.88); single-entry users 23% and 14% (0.63). In the Flea, 150-entry users were 44% of the field and
61% of the top 1%.

**What to change (section 14):** repair the one-game feature windows and the divergence-shadow gaps (class R); cap
exposure per player, per injured player, and per DST, spread the top-priced players, and pull selection toward market
agreement and chalk parity (class C, as Week-3 shadow arms first); put an exposure sheet with market and status
columns in front of the operator before every upload (class E).

## 1. Results by contest

| contest | entries | field | best rank (pctile) | median pctile | best pts | mean pts | field mean | field top | field p90 |
|---|---|---|---|---|---|---|---|---|---|
| Millionaire ($20) | 1 | 172,761 | 56,403 (32.6%) | 32.6% | 126.62 | 126.6 | 115.5 | 232.38 | 151.0 |
| Flea Flicker ($5) | 23 | 83,234 | 7,277 (8.7%) | 72.0% | 156.16 | 105.0 | 118.5 | 235.48 | 154.1 |
| Huddle ($5, single) | 1 | 23,781 | 11,996 (50.4%) | 50.4% | 111.48 | 111.5 | 113.7 | 223.00 | 149.7 |
| Pylon ($3, single) | 1 | 15,854 | 5,516 (34.8%) | 34.8% | 124.32 | 124.3 | 114.9 | 215.18 | 150.7 |
| Nickel ($5, 5-max) | 5 | 9,512 | 3,521 (37.0%) | 54.1% | 128.50 | 108.2 | 119.6 | 217.26 | 155.4 |
| supersat25a | 16 | 2,378 | 337 (14.2%) | 57.3% | 143.72 | 104.7 | 115.1 | 215.06 | 150.1 |
| supersat25b | 16 | 2,378 | 255 (10.7%) | 62.5% | 148.26 | 105.5 | 114.6 | 209.26 | 149.2 |
| supersat1a | 10 | 594 | 151 (25.4%) | 70.7% | 137.44 | 106.1 | 120.0 | 200.76 | 153.2 |
| supersat1b | 10 | 594 | 171 (28.8%) | 68.2% | 133.98 | 102.7 | 117.5 | 200.76 | 153.0 |
| supersat1c | 10 | 594 | 84 (14.1%) | 74.7% | 149.52 | 102.2 | 119.0 | 200.76 | 156.5 |
| satellite ($19) | 2 | 68 | 44 (64.7%) | 70.6% | 105.88 | 102.7 | 122.5 | 182.06 | 161.7 |
| FFWC qualifier ($1) | 2 | 59 | 48 (81.4%) | 83.9% | 96.58 | 93.4 | 123.8 | 183.84 | 160.3 |

The supersats award 25 tickets each; the best rank was 84. Fees $246.00 (entries export). Winnings need the DraftKings
contest-history export (Monday); the standings exports carry no payout column. The promoted Millionaire row (candidate
2123, the book's highest simulated mean at 139.5) scored 126.62; the delivered rank-1 row it displaced (candidate 12413)
scored 83.84, so the class-E promotion gained 42.8 points on the one row that carried the $20.

## 2. Study 1: the winners, their entry counts, and their construction

Top of each major (points, user's entry count in that contest, lineup):

- Millionaire #1, 232.38, 150 entries (49th of 150): Purdy, McCaffrey, J.K. Dobbins, Smith-Njigba, Lamb, Tre Tucker,
  Schultz, Kittle (FLEX), Patriots. $50,000; seven late-game players; QB + one pass catcher + the RB; three $7k+
  players; ownership sum 97.
- Millionaire #2, 226.66, 150 entries: Dak, McCaffrey, Aaron Jones, Smith-Njigba, Lamb, Diggs, Schultz, Ferguson (FLEX),
  Jets. Dak + Lamb + Ferguson with Diggs as the bring-back; six late players.
- Millionaire #3-#10: 150-entry users in six of eight (one 13-entry, one 3-entry). All hold Smith-Njigba and Lamb;
  nine of ten hold Schultz; Dak in six, Purdy in two, Drew Lock and Tyler Shough one each.
- Flea #1, 235.48 (100th of 150): Purdy, McCaffrey, Aaron Jones, Smith-Njigba, Chase, Tre Tucker, Schultz, Kittle,
  Panthers. Flea #2 231.26 (7th of 150): Dak + Lamb + Diggs + Matthew Golden, Henry, Aaron Jones, Schultz, Panthers.
- Huddle (single entry) #1, 223.00: Lock, McCaffrey, Aaron Jones, Smith-Njigba, Chase, Bateman, Schultz, Garrett Wilson,
  Panthers. Pylon #1, 215.18: Malik Willis, Henry, Aaron Jones, Lamb, McMillan, Coker, Schultz, Smith-Njigba, Panthers.
- Nickel #1, 217.26: Dak + Lamb + Ferguson + Diggs bring-back, Henry, Bucky Irving, Chase, Schultz, Patriots.
- supersat25a/b #1 (same user, 10 entries in each): Dak + Lamb + Pickens, Henry, Aaron Jones, Smith-Njigba, Schultz,
  Mayer, Panthers (215.06); and Dak + Lamb, Bijan, Tuten, Smith-Njigba, Schultz, Vele, Kalif Raymond, Patriots (209.26).
- supersat1a/b/c #1 (same user, 17 entries in each): Dak + Lamb + Golden, McCaffrey, Henry, Garrett Wilson, Andrews,
  Schultz (FLEX), Panthers (200.76).

Entry counts. In the Millionaire, users with 150 entries were 17% of the field and 32% of the top 1%; 21-149 entries
14% and 16%; 4-20 entries 29% and 26%; 2-3 entries 17% and 13%; single entries 23% and 14%. In the Flea, 150-entry users
were 44% of the field and 61% of the top 1%. In the 5-max Nickel and the 20-max supersats the per-entry rate is flat
across entry counts. So volume players beat the field per entry in the large fields, which says their process is
better, not only larger; our 23 Flea rows were one user with a below-field mean.

Construction, Millionaire field sample (20,000 rows) vs its top 1% (1,727 rows) vs our 97:

| feature | field | top 1% | ours |
|---|---|---|---|
| points | 115.5 | 189.0 | 105.0 |
| salary used | 49,866 | 49,878 | 49,814 |
| late-game players (4:05/4:25 ET) | 3.26 | 4.07 | 3.36 |
| QB + same-team WR/TE count | 1.13 | 1.21 | 2.12 |
| rows with 2+ same-team pass catchers | 27.7% | 31.6% | 100% |
| rows with 3+ same-team skill players (incl. RB) | 4.9% | 5.2% | 52.6% |
| rows with a bring-back | 44.1% | 40.7% | 100% |
| rows with no QB stack | 16.6% | 11.7% | 0% |
| ownership sum (Millionaire %) | 117.2 | 126.2 | 99.0 |
| highest-owned player in the row | 36.4 | 32.5 | 33.6 |
| players priced $7,000+ | 1.91 | 2.52 | 1.62 |
| rows with 3+ players priced $7,000+ | 24.2% | 52.2% | 13.4% |
| players priced $3,500 or less (non-DST) | 0.47 | 0.99 | 0.70 |
| distinct games per row | 5.35 | 5.40 | 3.70 |

Stack depth (definition: QB plus same-team WR/TE in any slot including FLEX; our book counts 87 rows at two, 8 at three,
2 at four, matching the labs' frozen-delivery review; with same-team RBs included it is 46 / 45 / 4 / 2). In the field:
0 stack 16.6% of the field, 11.7% of the top 1% (lift 0.71); one
55.8% / 56.7% (1.02); two 26.0% / 30.0% (1.16); three 1.7% / 1.6% (0.91). Mean points by depth 112.9 / 115.5 / 117.0 /
117.9. Expensive players: rows with three $7k+ players had lift 2.21 into the top 1% and the highest mean (123.2); rows
with one had lift 0.16. Late-game players: rows with 4-6 late players had lifts 1.3-1.8, rows with 0-2 had 0.09-0.55.

Read: the winners spent up on the two most expensive WRs and a $8,000 RB, took a cheap TE and DST that popped, played
mostly one-deep stacks, and leaned on the late games. We built two-deep stacks with a bring-back in every row (which
forces 3-4 players from one game and drops distinct games to 3.7), used fewer $7k+ players, and put the Millionaire and
Pylon rows almost entirely in the early window.

## 3. Study 2: high scorers we did not hold, and whether they were predictable

Players scoring 20+ that we held in under 15% of rows (served projection / frame market / Millionaire ownership / our
exposure / points):

| player | pos | salary | proj | market | own | ours | pts | what was visible |
|---|---|---|---|---|---|---|---|---|
| Jaxon Smith-Njigba | WR | 8,100 | 17.3 | 17.6 | 10.1% | 5.2% | 45.5 | #4 WR by our projection, highest-priced WR, 2025 mean 22.8, Week-1 29.2; nothing saw 45 |
| CeeDee Lamb | WR | 7,300 | 16.6 | 16.4 | 19.0% | 9.3% | 38.3 | #6 WR by projection; game total 50.5 (slate high); field held him 2x us |
| DeVonta Smith | WR | 6,800 | 12.8 | 12.8 | 3.7% | 3.1% | 30.7 | #18 WR; A.J. Brown out (not in the draft group); no source saw it |
| Dak Prescott | QB | 6,400 | 21.6 | 18.4 | 13.0% | 5.2% | 29.8 | #3 QB by projection, highest team total; we held Herbert (total 43.5) at 10% instead |
| Brock Purdy | QB | 6,200 | 21.3 | 18.7 | 9.5% | 4.1% | 28.5 | #5 QB; SF favoured by 13.5; we held the 49ers DST at 40% but their QB at 4% |
| Ja'Marr Chase | WR | 7,600 | 17.8 | 17.3 | 14.1% | 12.4% | 26.5 | held near field; fine |
| Panthers DST | DST | 2,700 | 7.0 | - | 4.9% | 1.0% | 26.0 | #9 DST by projection; not predictable |
| Tre Tucker | WR | 4,500 | 6.7 | 8.4 | 0.7% | 0% | 25.9 | market above us but both under 9; not predictable |
| Jaylen Waddle | WR | 6,500 | 14.3 | 12.0 | 3.3% | 3.1% | 24.8 | Week-1 1.2; ours above market; not predictable |
| Bryce Young | QB | 5,400 | 18.6 | 17.2 | 5.6% | 8.2% | 24.1 | held above field; fine |
| Chris Olave | WR | 7,200 | 16.0 | 14.6 | 4.5% | 7.2% | 22.6 | Questionable, limited practice; held above field |
| Christian McCaffrey | RB | 8,000 | 18.9 | 20.6 | 22.8% | 9.3% | 22.6 | market above us; we faded a 23%-owned player the market liked |
| Tyler Shough | QB | 5,300 | 17.2 | 17.6 | 3.1% | 5.2% | 22.4 | fine |
| Rashod Bateman | WR | 4,400 | 8.2 | 8.8 | 7.9% | 1.0% | 21.8 | Flowers out; field went 8x us; operator asked about him pre-lock (we kept 1 row) |
| Stefon Diggs | WR | 5,300 | 12.1 | 11.3 | 9.2% | 11.3% | 21.7 | fine |
| Drew Lock | QB | 4,900 | 15.3 | 15.8 | 1.2% | 1.0% | 21.4 | fine |
| Kirk Cousins | QB | 5,000 | 14.5 | 12.5 | 0.2% | 1.0% | 21.2 | not predictable |
| Denzel Boston | WR | 4,200 | 7.9 | 7.1 | 0.5% | 1.0% | 20.5 | not predictable |
| Jake Ferguson | TE | 3,800 | 8.1 | 7.8 | 4.6% | 4.1% | 20.3 | Dak stack piece; not predictable on its own |
| C.J. Stroud | QB | 5,500 | 19.4 | 16.5 | 2.1% | 7.2% | 20.0 | held above field; fine |
| Cam Ward | QB | 4,900 | 14.7 | 13.1 | 0.1% | 0% | 20.0 | not predictable |

Verdict: the magnitude of the two slate-defining scores (45.5, 38.3) was invisible to every source, ours and the market
alike. What was predictable is the allocation: we held the slate's three most expensive WRs at 5% (JSN, $8,100), 9%
(Lamb, $7,300) and 57% (Jefferson, $7,800), and the two QBs of the highest-total game plus the 13.5-point favourite's
QB at 5%/4% while holding Herbert at 10%. A salary-tier spread rule (section 14) would have put JSN and Lamb near 20%
each without any foresight. The $2,700-4,500 pops (Panthers, Tucker, Bateman, Boston, Ferguson) are where the winners'
salary went after spending up; no source we hold forecast them individually (our projection, the props, DK PPG and
ownership all sat within a point of each other), and the field found them at 0.5-8%.

## 4. Study 3: our underperformers, one by one

Served projection / frame market / implied production model mean (from the 0.45 blend weight) / Week-1 points / 2025
mean / our exposure / field ownership / points:

- **Justin Jefferson** 25.3 / no matched market (DK-PPG fallback 31.2) / 18.1 / 31.2 / 12.4 / 56.7% / 18.9% / 8.5.
  Highest projection on the slate because the name matcher dropped his prop lines and the blend used his one-game
  DraftKings PPG as the market (section 0); the model had him at 18.1 and the books at 16.4. His 2025 mean was 12.4
  over 17 games; wind 14.1 mph (slate high) in the game that scored least. The projection was unchanged from Thursday
  (24.5) to Sunday (25.3) because the miss was present in every batch. Available and unused: the prop lines
  themselves, the wind, the 2025 baseline.
- **Bijan Robinson** 21.7 / 22.7 / 20.5 / 31.3 / 23.2 / 46.4% / 47.2% / 11.1. The market agreed with us and the field
  held him at our level; this one is variance. But 46% exposure at 47% ownership is pure chalk with no leverage: had he
  hit, the field would have hit with us.
- **49ers DST** 10.0 / - / - / - / - / 40.2% / 9.9% / 8.0. Highest DST projection (13.5-point favourite). DST
  projection correlated 0.11 with outcomes this week; 40% of the book on one DST at 10% ownership is a leverage bet with
  no skill behind it.
- **Javonte Williams** 17.7 / 16.4 / 19.3 / 24.2 / 14.8 / 28.9% / 17.2% / 8.0. Model above market; Week-1 riser.
- **Ladd McConkey** 17.2 / none / - / 19.2 / 11.0 / 28.9% / 1.2% / 6.5. Questionable, limited practice, cracked rib;
  the books posted no lines (the only $6k+ skill player without props); the projection did not move from Thursday.
  The absence of a prop line is itself an availability signal and was not used.
- **Drake London** 16.5 / 12.4 / 21.5 / 5.5 / 12.8 / 26.8% / 3.4% / 8.9. Second-largest model-vs-market gap among our
  core; Week-1 5.5; the field held him at 3%.
- **Justin Herbert** 20.4 / 17.9 / 23.6 / 14.3 / 18.5 / 10.3% / 2.8% / 9.9. Model above market; 43.5 total (third
  lowest); the field held him at 3%.
- **Caleb Williams** 22.0 / 19.1 / 25.6 / 37.3 / 19.4 / 8.2% / 9.2% / 8.7. Week-1 riser (37.3), wind game.
- **David Montgomery** 15.2 / 13.5 / 17.3 / 28.9 / 10.1 / 13.4% / 10.3% / 4.4. Week-1 riser (28.9 vs 10.1 in 2025).
- **Colston Loveland** 13.3 / 11.8 / 14.4 / 0.0 / 9.9 / 10.3% / 10.9% / 1.3. Wind game, Week-1 zero.
- **Rhamondre Stevenson** 14.4 / 12.9 / 16.5 / 14.5 / 10.9 / 12.4% / 3.9% / 4.6. Model above market; field 4%.
- **Terry McLaurin** 12.5 / 11.6 / 13.7 / 3.4 / 6.7 / 12.4% / 14.1% / 7.0. Near field; fine.
- **Ashton Jeanty** 16.3 / 17.4 / 14.8 / 35.7 / 14.8 / 14.4% / 15.1% / 10.3. Near field; variance.

The pattern is one thing, not eleven: of our 44 exposures of 7+ rows, the served projection exceeded the market in 31,
by 1.4 points on an exposure-weighted basis; the players we projected 2+ above the market (17 on the slate) fell 3.5
short of projection on average; corr(proj - market, realized - proj) = -0.29 among players projected 12+. The market's
disagreement was the best available predictor of our misses, and the book was built on the side of that disagreement.
By position the market beat our projection for WRs (corr with points 0.65 vs 0.58) and tied for RBs (0.68 vs 0.68);
our projection beat the market for QBs (0.65 vs 0.17).

## 5. Study 4: were the heavy exposures justified?

Pool exposure vs book exposure vs field ownership vs points:

| player | pool | book | field | proj | market | pts |
|---|---|---|---|---|---|---|
| Justin Jefferson | 48.5% | 56.7% | 18.9% | 25.3 | 16.6 | 8.5 |
| Bijan Robinson | 37.2% | 46.4% | 47.2% | 21.7 | 22.7 | 11.1 |
| 49ers | 60.7% | 40.2% | 9.9% | 10.0 | - | 8.0 |
| Javonte Williams | 15.2% | 28.9% | 17.2% | 17.7 | 16.4 | 8.0 |
| Ladd McConkey | 11.2% | 28.9% | 1.2% | 17.2 | none | 6.5 |
| Drake London | 7.8% | 26.8% | 3.4% | 16.5 | 12.4 | 8.9 |
| Patriots | 9.1% | 24.7% | 5.3% | 8.3 | - | 21.0 |
| Dalton Schultz | 8.2% | 21.6% | 22.4% | 10.4 | 10.4 | 29.0 |
| Ashton Jeanty | 13.0% | 14.4% | 15.1% | 16.3 | 17.4 | 10.3 |
| David Montgomery | 9.2% | 13.4% | 10.3% | 15.2 | 13.5 | 4.4 |

A heavy exposure is justified when (a) our edge over the market is real and (b) the field is not already there. None
of the six 25%+ exposures met both: Jefferson, London, McConkey and Javonte were model-over-market plays (a), with the
market saying no; Bijan was pure chalk (b); the 49ers were a DST leverage play with no edge. The two heavy exposures
that paid, the Patriots (25% vs 5%, 21 pts) and Schultz (22% vs 22%, 29 pts), were not model-over-market plays. The
selector multiplied the generator's tilt: from pool to book, Jefferson +8 points of exposure, Bijan +9, Javonte +14,
McConkey +18, London +19, Patriots +16, Schultz +13. That is the expected-max selector rewarding the simulator's
highest-variance players (their p90s: Bijan 41.1, Javonte 39.1, London 39.1, Jefferson 34.5), which is exactly the
memory finding that simulated-tail objectives lose when the simulator's tail is 2.8x the realized tail.

## 6. Study 5: McConkey, and an exposure policy so it does not recur

28 rows (28.9%): supersat25b 9, supersat1b 5, supersat1c 5, supersat25a 4, supersat1a 3, Nickel 2; none in the
Millionaire, Flea, Huddle or Pylon (the promotion, replacement and ordering kept him out of the first 26 rows). He
played through the rib injury and scored 6.5; his rows averaged 98.8 with a best of 148.26. The labs' pre-lock
reconciliation and the operator both saw the count before lock; the tool that could have bounded it
(`tools/exposure_cap_book.py`) existed but was not in the chain.

Proposal (class C; the operator decides; the labs implement as a selection arm on the fixed Week-3 pool first):

1. Any player carrying Questionable or Doubtful at build time: at most 10% of the book; at most 5% if no book has
   posted a prop line for him by Saturday morning (McConkey's case); Doubtful players and any player with no
   depth-chart starter status: 0% unless the operator overrides.
2. Any single player: at most 30% of the book and at most 20% of the majors' rows (Millionaire, Flea, Huddle, Pylon,
   Nickel), unless field ownership is projected at 30%+ (chalk parity; Bijan would have been allowed).
3. Any DST: at most 20%.
4. The cap is enforced by re-selection from the pool (greedy by the selector's own score with the cap as a constraint),
   not by post-hoc swapping, so the book stays inside the delivered candidate set. On this slate that rule (25% cap,
   greedy by simulated mean) gives 106.3 mean, 183.6 best, eight rows at 150+, against the entered 105.0 / 156.2 / 1.
5. The exposure sheet with market points, status, props-present and field-ownership columns is shown before upload
   (class E), and every player over 20% is listed with the reason he is allowed.

Some exposure to an injured impact player is right when the market prices him (Olave: Questionable, props posted,
7% here, 22.6 points). The rule targets the combination of injury, no market and concentration.

## 7. Study 6: did our data see the high scorers; which sources were unused

- Accuracy over 287 salaried skill players: corr with points, served projection 0.60; frame market 0.57 (n = 171);
  implied pre-blend model 0.46; DK PPG 0.46; 2025 mean 0.54; salary 0.59. The served projection is the best single
  ranker, but only marginally better than salary, and at the top of the board it inverted: the 41 players projected
  15+ averaged 18.3 projected and 14.9 scored, 32% reached projection; top-10 QBs 21.1 -> 16.9; top-10 RBs 16.8 ->
  11.8; top-10 WRs 17.8 -> 18.4 (carried by JSN and Lamb, whom we barely held).
- Nothing saw the magnitude of JSN, Lamb, DeVonta Smith, Tre Tucker, the Panthers DST or Bateman: the market's numbers
  were within a point of ours for all of them except Tucker (8.4 vs 6.7).
- Existed and unused or broken:
  1. **Model-vs-market divergence.** The frame carries `market_points` for 346 players; the selection never sees the
     gap. The divergence shadow (`nfl_predictions.div_shadow`, 211 rows in the last pre-lock batch) has no row for
     Jefferson, DeVonta Smith or Zay Flowers although both books posted lines all week; the writer needs a look.
  2. **The DK-PPG fallback and the one-game window.** A slate player whose prop lines fail to match gets DraftKings'
     points-per-game as his market at 55% weight; in Week 2 that figure is one game (Jefferson 31.2, DeVonta Smith
     8.3). Every `_l4` feature also restarts each season, so the model's own Week-2 inputs were one game for everyone;
     the model's implied means for Week-1 risers sat above the market (London 21.5, Caleb Williams 25.6, Montgomery
     17.3) though not by Jefferson's margin. Fix order: suppress the fallback when it rests on fewer than four games
     (model-only for that row) and resolve ambiguous prop names against the slate; then cross-season windows with a
     season-change shrinkage.
  3. **Wind.** `wind_mph` is in the frame (14.1 for MIN-CHI, the next highest 7.9); that game got the most exposure of
     any game (1.15 player-slots per row, field 1.04, top-100 0.66) and produced the fewest points (104 skill points
     vs 204 for WAS-DAL).
  4. **Prop absence for a Questionable player** (McConkey): a signal, unused.
  5. **Ownership.** `nfl_predictions.own_shadow` has zero Week-2 rows: the ownership model did not run for this
     slate. The naive fade inside the lab generator pushed the book to a 99 ownership sum against a top-1% of 126.
  6. **DFS-platform lines** (`prop_lines_us_dfs`, 32,675 rows): never consumed.
  7. **ETR projections:** never landed.
  8. **Line movement:** none this week (every total moved 2 points or less between Wednesday and Sunday); no signal
     to have used.
  9. **Practice status** cut both ways (Schultz DNP Wednesday, 29 points; McConkey limited, 6.5); not a projection
     input on its own.
- Sources that would not have helped this week: line movement, weather beyond wind, depth charts (no starter change
  mattered after Tua/Flowers were handled).

## 8. Study 7: lineup variety, late games, games per row

- Late-game players per row: Millionaire row 2, Pylon 1, Huddle 8, Flea 3.2 (0-8), Nickel 2.4, supersats 3.3-3.9;
  field 3.26; the top 1% of every major 4.0-4.3; the Millionaire winner 7. The 4:25 ET games were the slate's best
  (WAS-DAL 204 skill points, MIA-SF 167, SEA-ARI 152). The late games also carry the late-swap option the chain now
  has; a row with one or two late players cannot use it.
- Distinct games per row: ours 3.70, field 5.35, top 1% 5.40. Two-deep stack + bring-back + a DST from a third game
  leaves four games; the winners spread over five or six.
- Within-contest variety was not the problem: mean pairwise shared players on canonical nine-player sets, ours Flea
  1.60 (23 rows, 12 QBs, 7 DSTs; max 6 shared, 4 of 253 pairs share 5+),
  supersats 1.07-1.58, Nickel 2.10; the winning multi-entry users were less diverse (2.1-3.7 shared) but around the
  right core (the supersat winner's ten rows: 3.1 shared, 4 QBs, mean 160). We varied widely around a wrong core; they
  varied narrowly around a right one. Variety cannot substitute for the core being right, but the core should not be
  one player at 57%.
- Game concentration, our player-slots per row vs the field vs the Millionaire top 100: MIN-CHI 1.15 / 1.04 / 0.66
  (104 points); CAR-ATL 1.12 / 0.85 / 0.48 (151); WAS-DAL 0.98 / 1.13 / 2.15 (204); LV-LAC 0.87 / 0.48 / 0.15 (143);
  CIN-HOU 0.77 / 0.72 / 1.24 (169); GB-NYJ 0.75 / 0.62 / 0.28 (146); NO-BAL 0.43 / 0.89 / 0.77 (165); MIA-SF 0.42 /
  0.66 / 0.69 (167); SEA-ARI 0.20 / 0.27 / 0.97 (152).

## 9. Study 8: recency (one week overweighted against history)

- Structural: the rolling windows partition by season, so every Week-2 usage and points feature was one game. That is
  a repair, not a tuning question.
- Measured on the 245 slate players with 6+ games in 2025 and a Week-1 score: our projection moved with the Week-1
  surprise (Week-1 minus 2025 mean) with correlation 0.55; reality moved with it at 0.26. Regressing points on the
  2025 mean and Week-1: reality weights 0.53 / 0.22; our projection 0.52 / 0.29. At the projection level the
  over-weight is modest.
- The selection was not modest. The 43 players whose Week 1 beat their 2025 mean by 8+ (Jefferson, Bijan, Javonte,
  McConkey, Jeanty, Montgomery, Caleb Williams, Bryce Young, Swift, Coker, Christian Watson, ...) received 378 of our
  873 player-slots (43%); they projected 14.4 and scored 11.6. The 99 players near their 2025 mean received 135 slots.
  The p90s of the risers (the selector's fuel) were the highest on the board.
- Recommendation: cross-season windows with shrinkage (class R), and until then a Week-1-riser guard in selection:
  a player whose only 2026 game exceeds his prior-season mean by 8+ cannot exceed 20% of the book.

## 10. Study 9: which games to go heavy in; were the odds used properly

- Closing totals and realized skill points: WAS-DAL 50.5 -> 204; MIN-CHI 48.5 -> 104; NO-BAL 46.5 -> 165; CIN-HOU 45.5
  -> 169; JAX-DEN 45.5 -> 147; GB-NYJ 44.5 -> 146; MIA-SF 44.5 -> 167; CAR-ATL 43.5 -> 151; LV-LAC 43.5 -> 143; CLE-TB
  41.5 -> 151; PIT-NE 41.5 -> 115; SEA-ARI 40.5 -> 152; PHI-TEN 39.5 -> 162. The total ranked the games weakly; the
  best game was the highest total, the worst game was the second highest. Totals did not move (max 2 points), so there
  was no movement signal.
- We used the odds the way the field did (our slots per row track the totals; MIN-CHI and CAR-ATL heaviest), which is
  to say properly but without edge. The winners' edge was player-level inside WAS-DAL (Lamb, Dak, Diggs, Ferguson) and
  SEA-ARI (JSN at a 40.5 total), not game-level.
- Recommendation: keep implied totals as the game prior; do not add game-level concentration rules beyond "5+ distinct
  games per row"; put wind into the game prior explicitly (a 14-mph game at a 48.5 total should not be the book's
  heaviest game).

## 11. Study 10: the perfect lineup and its signals

Optimal on realized DK points under the roster and $50,000 rules: Panthers DST ($2,700, 26.0), Dak Prescott ($6,400,
29.8), Jonah Coleman ($4,200, 14.8), Omarion Hampton ($6,600, 18.5), Dalton Schultz ($3,200, 29.0), CeeDee Lamb
($7,300, 38.3), DeVonta Smith ($6,800, 30.7), Jaxon Smith-Njigba ($8,100, 45.5), Tre Tucker ($4,500, 25.9): 258.46 at
$49,800. Our best row 156.16; the Millionaire winner 232.38.

Signals by piece: Dak was our #3 QB, JSN our #4 WR, Schultz our #5 TE, Lamb our #6 WR, Hampton our #14 RB, DeVonta
Smith our #18 WR; Coleman (projected 0.5), Tucker (6.7) and the Panthers (#9 DST) were unforecastable. Our exposure to
the nine: Schultz 22%, Lamb 9%, JSN 5%, Dak 5%, Smith 3%, Hampton 1%, Panthers 1%, Tucker 0%, Coleman 0%; pool
exposure 0-11% each. The best lineup with none of the nine still scores 201.48 (Purdy, McCaffrey, Rachaad White,
Ferguson, Chase, Waddle, Bateman, Diggs, Patriots).

Read: a perfect lineup always has three or four unforecastable pieces; the reachable part is the five or six
top-of-board players, and reaching them requires holding the expensive projected leaders broadly (JSN, Lamb, Dak,
Purdy, McCaffrey at 15-25% each) rather than one of them at 57%. The winners did exactly that and let the cheap pops
fall where they fell.

## 12. Study 11: where ownership worked for and against us

- The field-level picture: chalk hit. Among players 1%+ owned, ownership correlated +0.26 with points. The 20%+ owned
  players: Bijan 47% (11.1), Henry 37.5% (17.7), McCaffrey 22.8% (22.6), Schultz 22.4% (29.0), Aaron Jones 21.6%
  (13.5); three of five paid.
- Against us (our exposure vs Millionaire ownership, points): Henry 10% vs 37.5% (17.7); Lamb 9% vs 19% (38.3);
  McCaffrey 9% vs 23% (22.6); Dak 5% vs 13% (29.8); Aaron Jones 8% vs 22% (13.5); Purdy 4% vs 9.5% (28.5); Bateman
  1% vs 8% (21.8); Pickens 7% vs 19% (10.0, the one fade that helped). Over-weights that failed: Jefferson +38 points
  of exposure (8.5), 49ers +30 (8.0), McConkey +28 (6.5), London +24 (8.9), Javonte +12 (8.0), Stevenson +9 (4.6),
  Herbert +8 (9.9).
- For us: Patriots DST 25% vs 5% (21.0) is the one clean leverage win; Stroud 7% vs 2% (20.0), Bryce Young 8% vs 6%
  (24.1), Shough 5% vs 3% (22.4) were small ones.
- Per-contest decomposition of our mean against the field mean (exact: sum over players of (our share - field share)
  x points): Flea -13.5, of which under-holding Henry -5.0, McCaffrey -4.8, Chase -3.1, Lamb -2.8, Schultz -2.7, Purdy
  -1.7, Andrews -1.5; supersat1c -16.8 (McCaffrey -5.6, JSN -5.1, Schultz -3.5, Aaron Jones -3.1, Purdy -2.8);
  Nickel -11.4 (Lamb -8.8, Bijan -5.6, Dak -4.5, JSN -4.3). The Millionaire (+11.1) and Pylon (+9.4) rows beat their
  field means through Chase, Schultz and Stroud.
- Read: the naive fade lowered our ownership sum to 99 against the winners' 126; this week that cost ~10-15 points per
  row in every multi-entry contest. The fade is a proven +2 on the six-season panel; the problem is the size of the
  fade on a week when the model disagreed with the market, because the fade and the model-over-market tilt pushed the
  same way. Chalk parity (rule 2 of section 6) bounds that without removing the fade.

## 13. Selection audit: the pool versus the book

- Pool: 12,555 delivered candidates (2,560 lev, 9,995 boom). Realized: mean 98.0 (boom) / 76.7 (lev); 222 rows at 150+
  (all boom); best 197.26 (boom, simulated mean 116.0, never ranked); second 186.86, third 186.42.
- corr(sel_mean, realized) = -0.49 over the pool; -0.20 over the 97 entered rows. Realized mean by simulated-mean
  decile: 109.3, 108.5, 103.3, 100.1, 96.0, 93.1, 91.4, 88.4, 76.8, 69.8 (lowest to highest simulated mean). The
  simulator's top decile is the Jefferson-Bijan-49ers-Javonte-McConkey core; its bottom decile is where JSN, Lamb and
  Dak lived. Attribution by component (laptop, independent recomputation from the archived banks): the stored
  `sel_mean` equals the incumbent bank's mean (-0.488); the corrected-HSIM bank is -0.087 and the equal-mass pooled
  mean -0.332 (max difference from the stored mean 10.87 points). Within boom rows: -0.359 / -0.037 / -0.196.
- Counterfactual selections from the same pool, 97 rows (EXPLORATORY: these change the selection law to a mean sort,
  so they are not an isolated cap effect; the fair comparison is the cap arm on the delivered selector in the Week-3
  runner): entered book 105.0 mean / 156.2 best / 1 row at 150+; greedy by simulated mean, no cap 71.0 / 109.7 / 0;
  cap 35% 101.2 / 183.6 / 10; cap 25% 106.3 / 183.6 / 8; cap 15% 108.6 / 183.6 / 7; greedy by simulated P(194+), no
  cap 70.1 / 107.5 / 0, cap 25% 106.4 / 168.5 / 5; 97 random rows 92.1 / 158.7 / 1.3 (20 draws); 97 random boom rows
  97.6 / 164.7 / 2.1.
- Read: the entered book beat a random draw on mean (the dual expected-max selector with its coverage terms did work as
  a mean selector), but every simulated score was inverted at the top, and a per-player cap alone recovers the tail
  (best 184 vs 156) by forcing the selection out of the core. The 220+ supply question is unchanged: nothing in the pool
  reached 200 on a week when the field's winners scored 232-235 with rows built from players the pool held at 8-11%
  (JSN 11.0%, Lamb 10.0%, Schultz 8.2%, Dak 3.7%).

## 14. Proposals for Week 3 (for the labs' review; the operator decides)

Class R (repairs; no protocol question):
1. Prop-name ambiguity and the DK-PPG fallback (the Jefferson mechanism): resolve a normalized spelling shared by
   several GSIS ids by preferring the one id on the current slate; suppress the DK-PPG market fallback for any row
   whose PPG rests on fewer than four games of the season (model-only for that row) and log the suppressed rows; write
   fallback rows to the divergence shadow with their source so the instrument is no longer blind to them. Branch
   `production/prop-name-ambiguity-and-fallback-guard-20260921` (tests), for the laptop's merge before Saturday.
1b. Cross-season rolling windows with a season-change shrinkage for the `_l4` / `_last` / `_jump` features, so Week
   2-4 projections are not one-to-three-game windows (production feature SQL; leakage checks must stay as they are;
   needs a retrain cycle, so it is a reviewed branch, not a Saturday change).
2. Divergence shadow completeness: every slate player with prop lines must have a row; Jefferson and DeVonta Smith were
   missing because the matcher dropped them (item 1); Flowers had a TD-only line.
3. Ownership model: `own_shadow` wrote nothing for Week 2; find out why before Saturday.
4. Standings capture validator: entries-based tolerances (command sheet section 2a); until then the Millionaire and
   Flea exports cannot be loaded, and the field-calibration work has no Week-2 rows.

Class C (candidate rules; selection-only arms on the fixed Week-3 pool first, then the operator decides):
5. Exposure caps: per player 30% of the book and 20% of the majors' rows unless projected field ownership is 30%+; DST
   20%; Questionable/Doubtful 10% (5% with no prop line).
6. Market-agreement pull: for selection only, replace the served mean by a 0.25/0.75 model/market blend for players
   whose served projection exceeds the market by 15%+ (Jefferson would have entered selection at 19, London at 13).
7. Top-salary spread: each of the three highest-priced WRs and the two highest-priced RBs held at 10-25% of the book,
   none above 30%.
8. Row shape: 5+ distinct games per row; 3+ late-game players in the majors' rows; two-deep stacks in at most 40% of
   rows and a bring-back in at most 50% (the field's top 1%: 30% and 41%).
9. Week-1-riser guard until repair 1 lands: a player whose only 2026 game exceeds his prior-season mean by 8+ is capped
   at 20%.
10. The projection-floor question the operator raised (12-point floor) is not supported by this week either: the
    perfect lineup's TE, DST, RB2 and WR3 were all projected under 12, and the winners' rows carried 0.99 minimum-price
    players each. Keep it as the falsifier arm in the shadow.

Class E (execution, this week):
11. Exposure sheet before upload with market points, implied model mean, status, props-present, field ownership and
    the cap reason for every player over 15%.
12. Late-swap plan for rows with 3+ late players (the chain has the applier).

Questions for the labs: (a) can arms 5-9 run as selection-only arms in the Week-3 shadow runner on the same fixed pool
(the runner already takes cap_prefix, floor and depth arms)? (b) is there a cheap way to score the incumbent and hsim
halves separately on this pool so the -0.49 can be attributed? (c) does the boom generator's p90 valuation need a
market-agreement term, given that the exposure tilt starts in the pool (Jefferson 48.5%, 49ers 60.7%)?

## 15. Corrections, data-quality items and method notes

- Corrections made while this was being prepared. The first draft said the props blend had missed Jefferson (a join
  error on my side); the second said the model itself carried him near 36 (inferred from the lab frame's market column,
  which the lab computes with older matching code). Both were wrong. The main-tip production code, re-run on the
  Week-2 prop rows, has no market row for Jefferson or DeVonta Smith; the projection job's log confirms props reached
  388 of 481 rows; the served 25.3 is the 0.45/0.55 blend of the model (18.1) with his one-game DK PPG (31.2). The
  sections above now say that.
- Realized points are DK FPTS from the standings exports; they matched our 97 entries' DK scores to 0.00001. The
  nflverse-based outcomes builder and proper-score reader run Monday and may differ by DK stat corrections.
- The `nfl-dfs` CLI in the operational worktree runs pre-2026-09-14 capture code; the main-tip code validates 6 of 12
  exports; the failures are DK ownership-summary tolerances, not entry data (command sheet section 2a).
- Two aggregate reads of Week-2 `player_week_actuals` (row counts and a max) happened before the operator's release
  and were disclosed to the labs on 2026-09-20; no lineup score was read before the release.
- Field ownership used here is the Millionaire's %Drafted summed over roster slots; the Flea and the other contests'
  ownership are in the shared table and differ by a few points.
- Status of the section-14 items as of 2026-09-20 late evening: R1 built and pushed as
  `production/prop-name-ambiguity-and-fallback-guard-20260921` (props-or-nothing live market, per-row source log,
  inventory v8, exposure sheet); R4 built and pushed as `production/standings-capture-tolerances-20260921` (twelve of
  twelve exports validate); C5-C9 built as selection-only arms in `production/week3-shadow-arms-20260920` (cap30,
  cap20, marketpull, cap20pull, games5, late3). The introduced commit of the name-ambiguity drop is 5878c841
  (2026-09-04, "Resolve live Week 1 prop player identities"), on main since; Week 1 did not trip it because the
  colliding roster rows were not yet in the 2026 roster union.
- Files: `handoffs/receipts/2026-09-21-week2-post-mortem/` on the reply branch: `contest-field-summary.csv`,
  `our-97-results.csv`, `player-signals-week2.csv`, `pool-realized-12555.csv`, `standings-player-ownership-fpts.csv`,
  `top100-lineups-by-contest.csv`, `top10-features-by-contest.csv`, `games-week2.csv`,
  `regeneration-1048-changed-rows.csv`, `capture-validate-main-tip.log`.
