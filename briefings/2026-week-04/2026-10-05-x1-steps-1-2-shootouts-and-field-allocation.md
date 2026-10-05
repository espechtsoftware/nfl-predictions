# X1 steps 1–2: are shootouts predictable, and does the field over-concentrate? (2026-10-05)

Written for the operator and the reviewer. These are the first two steps of study 13 / X1 (scenario arbitrage) in the
reviewer's order: shootout calibration, then the field's allocation. Both are base-rate checks on history. No 2026
outcome and no PREREG-098 result was used. Scratch files: `curse/games.csv`, `curse/own.csv`.

## Step 1: betting totals vs realized scoring (3,214 regular-season games, 2014–2026)

- **Totals are right on average, but noisy:** realized minus total averages +0.3 (sd 13.2); corr(total, points) 0.31.
- **The share of games reaching 55+ rises with the total:** 9% (total ≤ 38), 24% (44–47), 32% (47–50), 42% (50–53),
  51% (> 53).
- **Which game shoots out is hard to call** (213 weeks with 10+ games):

  | Week's highest-scoring game | Share of weeks |
  |---|---|
  | The top-total game | 16% |
  | Total ranked 2–3 | 20% |
  | Total ranked 4–6 | 24% |
  | Total ranked 7–10 | 27% |
  | Total ranked 11+ | 13% |

  The top-total game finished in the week's top 3 by scoring only 36% of the time.

## Step 2: does the Millionaire field over-concentrate on top totals? (all 72 weeks, 2022–2025)

**Join (fixed per the reviewer):** players are mapped to games through each week's schedule, with canonical team codes
(`nfl_dfs.dashboard.teams.canon_team`). The first pass took opponents from the salary file; 2025 has none, and it
covered about 70%. After the fix, 99.99% of player rows and at least 99.9% of each week's ownership mass are joined.

The field's ownership share per game (skill players), by the game's total rank, against how often a game at that
rank was the week's top scorer in 2014–2021 (out of sample). Leverage = P(top game) ÷ field share.

| Total rank | Field share | P(week's top game), 2014–21 | P(top 3), 2014–21 | Leverage |
|---|---|---|---|---|
| 1 | 14.5% | 19.0% | 40.9% | **1.31** |
| 2 | 13.9% | 13.9% | 33.6% | 1.00 |
| 3 | 12.6% | 3.6% | 23.4% | 0.29 |
| 4 | 10.8% | 7.3% | 24.1% | 0.68 |
| 5 | 11.1% | 8.8% | 25.5% | 0.79 |
| 6 | 9.7% | 8.0% | 25.5% | 0.82 |
| 7–10 | 7.4–9.1% | 5.8–8.0% | 15–20% | 0.64–1.08 |
| 11–14 | 5.2–7.2% | 2.2–5.1% | 8–16% | 0.31–0.74 |

**Rank 3's 3.6% is noise, not a join artifact.** It is about 5 events in 137 weeks, and it holds under every tie
convention (3.9% with min-rank).

## Reading

1. **The field is FLATTER than the odds, not more concentrated.** It under-owns the top-total game (leverage 1.31) and
   over-owns low-total games (leverage 0.3–0.7). On base rates, the leverage sits in the top-total game, not in
   contrarian low-total games. Week 4's DAL–HOU (rank 3) was the 16%-of-the-time exception, not a pattern.
2. **Our error is SIZE, not direction.** Leaning on the top-total game is supported. Putting 61% of the book there
   (Week 4) is not: that game is the week's top scorer about one week in five, and in the top 3 about two in five.
3. **Consequences:**
   - Study 1 + P4 first. The arms set the per-game exposure in proportion to P(top-3 game | total rank) from 2014–21
     ONLY.
   - X1's per-slate mispricing step remains possible, but its contrarian form (under-owned low totals) has negative
     base-rate leverage. Any X1 sleeve would lean toward the top totals the field under-owns.

**Caveats:**
- Field share counts skill players only (no DST).
- The 2014–21 base rates use 8 seasons.
