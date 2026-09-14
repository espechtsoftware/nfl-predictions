# Week 1 settled against the real field (2026-09-14)

Sources: DraftKings full-standings exports for the three contests (832,342 / 158,541 / 5,000 entries), the operator's
contest-entry-history export, and every Week-1 book and shadow scored on DraftKings' official per-player points.
Data: `results/2026-09-13/` (local, untracked: entry keys), `reports/week1-duds/week1_settlement_official.csv`,
`reports/week1-duds/milly_top100_players.csv`.

## 1. The fields

| contest | entries | winner | top-10 cut | top-100 | top-1,000 | cash line | median | p99 | p99.9 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Millionaire | 832,342 | 273.98 | 257.8 | 244.8 | 228.2 | 165.5 (place 173,275) | 141.7 | 209.0 | 229.6 |
| Play-Action | 158,541 | 263.84 | 247.4 | 232.2 | 213.4 | 168.1 (place 34,890) | 141.7 | 209.2 | 228.2 |
| FFWC Qualifier 7 | 5,000 | 260.00 | 229.2 | 205.3 | 171.1 (260 paid) | – | 147.1 | 212.2 | 232.2 |

Ours (entered v6b): Millionaire best 192.08, rank 34,838 (top 4.2%), 61% of our entries above the field median, 25%
above the cash line; Play-Action best 196.24, rank 4,872 (top 3.1%); qualifier best 153.72. Fees $399, winnings $140.

## 2. Every book, settled on official points

| book | n | best | best of first 30 | mean | cashing (≥165.5) | ≥200 |
|---|---:|---:|---:|---:|---:|---:|
| **entered v6b (proven-scorer rule)** | 80 | **196.24** | 182.00 | 144.9 | 18 | 0 |
| counterfactual v4b (scratch swaps only) | 80 | 224.54 | 203.84 | 146.0 | 19 | 2 |
| **paid K90 vetted order, 09:10 build** | 90 | **226.64** | 226.64 | 145.8 | 20 | 2 |
| paid K90 vetted order, 10:50 build | 90 | 226.64 | 226.64 | 145.9 | 22 | 2 |
| hybrid15 (09:10) | 30 | 226.64 | 226.64 | 151.0 | 11 | 1 |
| learned-book re-sort (09:10) | 90 | 226.64 | 226.64 | 145.8 | 20 | 2 |
| union (09:10) | 90 | 226.64 | 226.64 | 156.1 | 32 | 3 |
| learned-div5 (09:10 / final) | 90 | 228.76 / 228.50 | 194.6 / 228.5 | 152 | 24 / 31 | 2 / 5 |
| blend-div5 (09:10 / final) | 90 | 228.76 / 228.50 | 228.76 / 216.2 | 152 / 157 | 27 / 32 | 3 / 6 |
| blend-q99 (09:10 / final) | 90 | 214.50 / 216.20 | 214.5 / 191.4 | 165 / 161 | 46 / 38 | 3 / 1 |
| learned-pool (09:10 / final) | 90 | 214.50 / 204.50 | 191.6 / 196.4 | 160 | 36 / 39 | 1 / 1 |
| today-30 (learned rule, final) | 30 | 196.40 | 196.40 | 143.9 | 12 | 0 |

Reading:
- **The machine's own book held a 226.64 in the first 30 of the vetted order, in both builds.** In the Millionaire that
  is about rank 1,100 of 832,342 (top-1,000 cut 228.2). Its lineup: the Bryce Young / Coker / McMillan Carolina side of
  the 59–37 game with Gibbs and Swift. The entered book did not contain it because the proven-scorer rule removed Coker.
- The learned-family shadows had their best week: 228.5–228.8 (learned-div5, blend-div5), with 3–6 lineups over 200 and
  book means 152–165 against the paid book's 146. One week; hypothesis-level; it goes into the prospective ledger.
- Nothing reached the Millionaire's top 100 (244.8). The winner's 273.98 was Steelers DST, Swift, Love, Gibbs, Henry,
  Goedert, Watson, DJ Moore, Coker: 4 top-quartile studs at 30+ and Coker, exactly the perfect-lineup anatomy.

## 3. The winners' profile (Millionaire top 100) versus our book

| | top 100 | our entered book |
|---|---:|---:|
| mean ownership of skill slots | 12.9% | 9.5% |
| slots under 10% owned, per lineup | 5.8 | 5.0 |
| slots under 5% owned, per lineup | 1.5 | 2.5 |
| highest-owned slot, per lineup | 35.8% | 23.8% |
| projection percentile within position | 0.89 (96% top-quartile) | 0.88 (91%) |
| salary per skill slot | $5,856 | $5,814 |
| QB-stack mates per lineup | 1.65 | – |
| practice-DNP players per lineup | 0.00 | 0.28 (Chase) |
| players' points vs projection | 29.6 vs 14.7 | 16.7 |

The winners were **more chalky** than we were, not less: they held Gibbs (39% owned) and Olave (24%) and added three or
four low-owned booms (Coker 7%, Swift 8%, Bryce Young 3%, Goedert 8%, Henry 8%). Most common players in the top 100:
Coker 92, Gibbs 87, Olave 71, Swift 53, Young 45, Goedert 44, Henry 40, Shough 31, Flowers 30, Jeanty 29. Their
players' history in our pool: big-game rate 0.22, no "unproven" players. Structurally they look like our book with the
right two or three names.

## 4. What this settles

1. The filter cost the week's result: 196 entered against 226 available in the machine's own top 30. Rule recorded.
2. Practice-status exposure: the winners held zero did-not-practice players; we held Chase in 22 lineups. The cap goes in.
3. The field's cash line (165.5, top 20.8%) sits 24 points above its median (141.7). Our entered book's mean (144.9)
   beat the median but only 25% of entries cashed: the Millionaire's payout curve punishes the mean-optimal lineup;
   a double-up field (paid above the median) would have cashed 61% of these same entries.
4. Contrarianism per se was not the edge today: the winners were chalkier than us. The edge was the right game
   (Chicago–Carolina, 96 points) and the right cheap receiver in it. Our book had that side of the game in the vetted
   top 30 (226.64) and in 13 lineups of the plain book; the entered book had it filtered out.
