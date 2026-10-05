# Studies 15 and 16: the QB stack rule and the thesis portfolio (2026-10-05)

Written for the operator. Two of your ideas were tested today, the same way as the player cap: on 36 practice slates
(2023–24), with the rules frozen before any result was read. The reviewer re-ran both independently and got identical
output.

## Study 15: should a lineup need only the QB, 1 teammate and a bring-back?
**Answer: no measurable difference. It is your call, and keeping today's rule is the better-supported choice.**

| version | average finish vs today | cashes on 36 slates |
|---|---|---|
| today: QB + 2 + bring-back | – | 325.5 |
| QB + 1 everywhere | +0.7 points (could be −1.6 to +3.0) | 283 (about 13% fewer; not significant) |
| QB + 1 only in the two highest-total games | −0.4 points (could be −2.9 to +2.3) | 327 (the same) |

- **"Everywhere":** a 194+ point lineup on 18% of slates instead of 32%.
- **"Shootout games only":** indistinguishable from today.
- **If you want to switch anyway:** it would be a reversible trial with a rollback. The live system first needs a new
  version of the lab code that holds the per-game rule, reviewed before any entry.
- **One honest note:** my results reader printed slightly narrower ranges than the plan said. That cannot change a
  "no difference" result, and recomputing at the planned width gave the same answer. It is recorded.

## Study 16: your thesis: core lineups on the expected high-scoring games, plus some "a game goes differently"
**Answer: it did not hold up, either as a whole book or as a 25% sleeve. It is not offered.**

| version | cashes | average finish vs today | slates with no cash at all |
|---|---|---|---|
| today's book | 326 | – | 31% |
| the thesis as the whole book | 260 (about 20% fewer; the test cannot call it significant) | 4.3 points worse | 17% |
| the thesis as a 25% sleeve | about 1.2 fewer per slate | 1.3 points worse | 29% |

- **The formal verdict is "no difference" on cashes:** the test could only detect a swing of about 40%. But the
  average-finish limit you set (1.5 points) failed by a wide margin.
- **Why it lost:**
  - today's book already puts 75% of entries on the four highest-total games;
  - the thesis version pushed that to 89% and cut the mid-total games from 24% to 7%;
  - it picked "the games expected to score high" from the betting totals, the same information our optimizer already
    uses.
  - So, as tested, it was a heavier bet on the market's expected shootouts, not a different view, and that cost average
    finish.
- **The sleeve made it worse, not better:** the thesis lineups are mostly the same popular games we already hold, so a
  sleeve of them added more of the same exposure instead of spreading it.
- **The bright spot:** fewer slates with no cash at all (31% → 17%), the same pattern as the capping studies. But it
  came with fewer cashes overall and a lower average finish.

## The honest limit
What was tested is the *betting-market* version of the thesis: games A–D = the four highest totals. Your own picks
cannot be tested on history, and you have said you do not want to supply picks, so that version is not pursued. The
sleeve follow-up (16b) is tabled: thesis lineups built this way are worse per entry, and cashes add up per entry.

## The pattern from today's four studies
- **Spreading the book out** (by game, by player entry cap, or by scenario) lowered the average finish every time.
  Several versions reduced the weeks with no cash at all, but none raised expected cashes measurably.
- **Loosening the stack rule** changed nothing measurable.
- **The biggest remaining lever** is the projections themselves: the data-leak fix (O-22) is reviewed and ready, and
  the retrain runs Thursday–Friday.

## For the record
- Preregistrations: `reports/2026-10-05-prereg-study15-qb-stack.md` and
  `reports/2026-10-05-prereg-study16-thesis-portfolio.md`.
- Full numbers: system study Addenda 124 and 125.
