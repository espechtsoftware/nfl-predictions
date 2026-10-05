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

## Step 2: does the Millionaire field over-concentrate on top totals? (54 weeks, 2022–2025)

The field's ownership share per game (skill players), by the game's total rank, against how often a game at that
rank was the week's top scorer in 2014–2021 (out of sample):

| Total rank | Field share | P(week's top game), 2014–21 | P(top 3), 2014–21 |
|---|---|---|---|
| 1 | 14.4% | 19.0% | 40.9% |
| 2 | 13.1% | 13.9% | 33.6% |
| 3 | 11.2% | 3.6% | 23.4% |
| 4 | 10.3% | 7.3% | 24.1% |
| 5 | 10.5% | 8.8% | 25.5% |
| 6 | 9.6% | 8.0% | 25.5% |
| 7–9 | 7.8–8.8% | 5.8–6.6% | 15–20% |
| 10–12 | 6.7–7.0% | 2.2–8.0% | 10–18% |

## Reading

1. **The field spreads across games roughly in proportion to the real odds.** If anything it slightly under-owns the
   top-total game. On base rates there is no systematic game-level mispricing for a contrarian sleeve to exploit.
2. **The concentration problem is ours, not the field's.** Week 4: 61% of our entries held 3+ players from JAX–CIN
   (the top total). The field spread out. A game that is the week's top scorer only about 16–20% of the time cannot
   carry 61% of a book.
3. **Consequences:**
   - X1's remaining step (per-slate mispricing: the market scenario probability vs the field's allocation, slate by
     slate) can still be preregistered. The aggregate gives it no tailwind.
   - The stronger, evidence-backed lever is de-concentrating our own book toward the odds-proportional spread the
     field already has: study 1 + P4. That is now the first study to preregister.

**Caveats:**
- About 70% of game-weeks joined between the ownership and schedule data (team-code matching). Unjoined games are
  missing at random with respect to rank, as far as checked.
- Field share counts skill players only (no DST).
- The 2014–21 base rates use 8 seasons.
