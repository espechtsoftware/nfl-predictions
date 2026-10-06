# The fill order (study 42's question) on real fields, and the shapes the winners actually used (2026-10-06, 16:50 CT)

By the outside reviewing agent, answering the operator's question of 10-06 ("are we putting our best strategy first
for a given QB?") and his suggestion to look at the winners' lineups rather than ours. Two pieces of evidence, both
on the real Millionaire fields of Weeks 2–4, aggregates only. Neither is a frozen study; study 42 (the reviewer's) is
the frozen court. This file is for that court's authors and the operator, before the read.

## 1. The shapes the winners used, by week and by QB (real fields)

Every Millionaire lineup classified by its QB's stack: A1 = QB + 2 teammates + a bring-back, A2 = QB + 2 teammates, no
bring-back, B = QB + 1 + bring-back, C = QB + 1, no bring-back, N = no teammate (bring-back = a skill player from the
opponent in the QB's game; teammates = WR/TE/RB). Positions and games from each week's T−70 frame.

| Week | Group | A1 | A2 | B | C | N |
|---|---|---|---|---|---|---|
| 2 (172,692) | field | 20.1 | 18.7 | 20.3 | 28.2 | 12.5 |
| | top 1% (1,729) | 20.3 | 23.5 | 18.4 | 29.8 | 8.0 |
| | top 100 | 14.0 | 28.0 | 18.0 | 35.0 | 5.0 |
| 3 (161,682) | field | 20.8 | 20.6 | 16.9 | 28.6 | 13.0 |
| | top 1% (1,620) | **54.0** | 20.2 | 10.8 | 12.8 | 2.3 |
| | top 100 | **63.0** | 17.0 | 12.0 | 8.0 | 0.0 |
| 4 (161,764) | field | 21.8 | 20.7 | 19.4 | 25.6 | 12.5 |
| | top 1% (1,614) | 23.2 | 10.9 | **40.4** | 18.6 | 6.8 |
| | top 100 | 16.0 | 4.0 | **58.0** | 17.0 | 5.0 |

Per QB (QBs with ≥ 150 top-1% lineups), the share of his top-1% lineups by shape against his field share:

| Week | QB | top 1% A1 / A2 / B / C / N | field A1 / A2 / B / C / N | QB+2 lift |
|---|---|---|---|---|
| 2 | Prescott (811) | 26 / 28 / 19 / 26 / 2 | 26 / 24 / 17 / 27 / 6 | 1.07 |
| 2 | Purdy (226) | 7 / 31 / 4 / 34 / 24 | 11 / 29 / 8 / 35 / 18 | 0.95 |
| 3 | G. Smith (885) | **81** / 8 / 10 / 2 / 0 | 45 / 9 / 26 / 15 / 4 | 1.63 |
| 3 | Shough (253) | 12 / **58** / 2 / 25 / 4 | 16 / 21 / 15 / 36 / 12 | 1.85 |
| 3 | Purdy (191) | 31 / 19 / 18 / 25 / 6 | 15 / 23 / 11 / 32 / 19 | 1.31 |
| 4 | Stroud (639) | 17 / 1 / **67** / 13 / 2 | 19 / 10 / 33 / 28 / 11 | 0.62 |
| 4 | Prescott (332) | **46** / 8 / 29 / 15 / 1 | 21 / 19 / 20 / 31 / 9 | 1.34 |

Reading: **a QB's best shape is not knowable before kickoff.** The winning shape follows the game script: Week 3's
top 100 was 63% full game stacks (Geno Smith's lineups: 81% A1); Week 4's was 58% QB + 1 + bring-back (Stroud: 67% B,
and his QB + 2 lineups finished *below* his field rate); Week 2's leaned to QB + 1 and QB + 2 without a bring-back.
The same QB swings between weeks (Prescott: no shape edge in Week 2, A1 at 2.2× his field rate in Week 4). Our own
replay books say the same: the best row was a C row in Weeks 2 and 4 and an A1 / B row in Week 3.

So the right rule for a capped QB's slots is **coverage across shapes**, not "his best shape first". A fill that
concentrates a QB's five rows in one shape (today's group order: Lawrence A1 A1 A1 A1 B, Shough A1 A1 A1 A1 B,
Herbert A1 A1 A1 A1 B in the replay books) bets his week on one script, and when that script fails the rows die
together (our Week-2 A1 rows: projected 142.6, realized 79.7). Round-robin (one row per shape in turn) is the order
that gives each top QB a row in each shape.

## 2. Group vs value fill on real fields (the production switch `a7fafd38`, `--mix-fill`)

The lever-screen harness (`reports/2026-10-06-fixed-book-lever-screen-w2-w4.md`), both arms at the live Week-5
settings (overlap 5, QB cap 5, no term; W4 under FP, W2–3 under our projections), differing only in the fill order.

| Week | Arm | P(≥1 big) | E[big] | mean entry pct | projected sum / row | best row | top-3 rows | QBs | top QBs' shapes |
|---|---|---|---|---|---|---|---|---|---|
| 2 | group (live) | **.908** | 1.657 | .400 | 137.25 | **185.2** | 185.2 C, 174.3 C, 174.1 C | 8 | Herbert A1A1A1A1B; Williams A1A2A2BB; Prescott CCCCC |
| 2 | value | .045 | .045 | .411 | 137.16 | 162.9 | 162.9 A1, 149.6 A2, 147.2 A1 | 8 | Herbert BBCCC; Williams A1A1A2BB; Prescott A1A1A2A2C |
| 3 | group (live) | **.310** | .318 | .526 | 133.03 | **170.0** | 170.0 A1, 169.5 B, 157.5 B | 10 | Shough A1A1A1A1B; Allen BBCCC; Goff A1A1A2A2A2 |
| 3 | value | .0002 | .0002 | .472 | 133.15 | 161.0 | 161.0 C, 160.0 A2, 155.7 C | 8 | Goff A1A1A1A2A2; Shough A2CCCC; Mahomes A1A2BBB |
| 4 | group (live) | **.343** | .374 | .565 | 143.99 | **176.1** | 176.1 C, 175.5 C, 151.4 B | 10 | Lawrence A1A1A1A1B; Burrow A1BBCC; Brissett A1BBCC |
| 4 | value | .0046 | .0046 | .452 | 143.79 | 150.2 | 150.2 C, 144.1 C, 139.9 B | 8 | Brissett A1A1A1BC; Lawrence A2BBBC; Burrow BBCCC |

Reading:
1. **The value fill does not raise the book's projection.** The projected sum per row is identical to a tenth of a
   point in every week (the caps bind the same players either way). Its premise, that committing the best-projected
   row first keeps options open, buys nothing even on its own terms; it only changes which QB gets which shapes.
2. **On real fields it is far worse in all three weeks**: best row 163 vs 185, 161 vs 170, 150 vs 176; P(≥1 big)
   .05 vs .91, .0002 vs .31, .005 vs .34; mean entry percentile worse in two of three. With identical projections,
   the realized gap is largely the luck of single rows, but it is three for three with wide margins, and it is the
   direction the mechanism predicts: by projected value, the top QB's first rows are his least-constrained shapes
   (Herbert B B C C C, Burrow B B C C C), the shapes with the lowest ceiling, and the book covers fewer QBs (8 vs 10).
3. **What is left of the original observation.** The group order's real defect is not that a QB's rows go to the
   "wrong" shape; it is that they go to ONE shape (four of five in A1) and that the last cell (A2) is built from
   leftovers. Round-robin addresses both without choosing a favourite shape.

## 3. Suggestions for study 42 and for Week 5

- Do not arm `--mix-fill value` for Week 5 on this evidence; the frozen read will say what it says, but a PASS on
  36 slates against three real weeks this far apart would need an explanation before it was entered.
- Make round-robin (MIXT_RR) decision-bearing, or add a second decision pair; it is the arm the winners' shapes argue
  for. Add to the census, per arm, the shape coverage of the top three QBs (distinct shapes among their rows).
- A per-QB shape-coverage rule is the direct form of the same idea (a QB with ≥ 3 rows holds ≥ 2 shapes), one line
  in `mix_rows`, Week 6 at the earliest.
- The operator's own version ("try several strategies per lineup, keep the best projected") is the value fill, and
  the test says no. The version his instinct points at is: for each QB in turn, build his best row under EACH shape
  and keep all that fit the quotas, which is round-robin.

Reproduction: `reports/2026-10-06-fill-order-replay/` (`screen_fill.sh`, `score.json`); scratch
`~/rehearsals/screenfill-20261006T214640Z`. Section 1's classification script is in the session scratch and is
reproducible from `moneygate_score.load_week` and each week's T−70 frame; it will be added here if the reviewer wants
it as a Monday line.
