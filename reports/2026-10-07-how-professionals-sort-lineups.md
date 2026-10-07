# How professionals sort lineups, what this project has already tested, and sort ideas to try (2026-10-07)

The operator (10-07): "do some research on how professionals sort lineups. I just asked production to design a test
that sorts based on projected touchdowns, but I'd like other ideas." By the outside reviewing agent. The screen's code:
`reports/2026-10-07-winners-strategy-study/sort_screen.py`; results `run/experiments/sort_screen.csv`.

## 1. How the professionals do it

The commercial tools that most high-volume players use share one pipeline:

1. **A large pool**, built by an optimizer and by sampled worlds (thousands of lineups).
2. **Contest simulation.** The slate is simulated thousands of times; a field of opponents is simulated from projected
   ownership; every pool lineup is played against that field in every simulation.
3. **One sort number per lineup, from the simulation.** Stokastic's default is **simulated ROI** ("generally the best
   single number for choosing what to play"; win %, top-10 % and cash % are shown beside it). SaberSim recommends
   **RAROI**, a risk-adjusted ROI, for tournaments, and asks the user to set the contest's percent-to-first first
   ("push it to 20 percent or higher for a top-heavy Milly Maker").
4. **Uniqueness, then filters.** A minimum number of differing players between chosen lineups ("at four uniques, each
   favorited lineup has to differ by at least four players"), then filters on stack type, specific combinations,
   ownership sum, **ownership product or its geometric mean** (the standard duplication filter: the product of the nine
   ownerships predicts how many copies a lineup will have far better than the sum), and salary left.
5. **An exposure check against the field.** "Leverage" is the portfolio's exposure to a player minus the field's
   projected ownership; tools show a player's **optimal %** (how often he is in a simulated world's best lineup) beside
   his ownership, and the gap is the raw material of tournament equity.
6. **For big portfolios, greedy selection on marginal portfolio value** rather than the top N by score, the method the
   academic papers prove is near-optimal (the objective "at least one entry wins" is submodular: Hunter, Vielma and
   Zaman; Haugh and Singal).

The one constant: **every professional sort is a simulation's verdict against a simulated field**, so its value is the
value of the projections and the simulation behind it. Establish The Run publishes calibration of its sims' cash rate
(lineups the sims gave 30%+ cashed 31.1% of the time); nobody publishes calibration of top-1% or win rates.

## 2. What this project has already tested (both ledgers)

| Professional method | Tested here? | Result |
|---|---|---|
| Sort by simulated finish against a modelled field (P(top-N), sim ROI) | Yes: PREREG-098; the 09-xx sim-ROI theory | Lost to expected-max (−0.030, 9 wins / 44 losses); "does not survive its own test" |
| Greedy marginal portfolio value (E[max], coverage of sampled worlds) | Yes, extensively (the lab's 2026-08 programme; study 32) | The old incumbent selector; joint choice helps only at 2–3 entries |
| Ceiling / p90 / quantile sorts | Yes, five times | Closed: negative each time |
| One-number ranking of single rows | Yes: study 32 | Every one-row ranking rule trailed random |
| A learned "looks like a winner" score | Yes: studies 48–48e | No support among high-projection lineups on real fields |
| Ownership product / geometric mean (duplication) | Mentioned, never as a sort | — |
| Optimal % and leverage (optimal % − ownership) | No | — |
| Touchdown-based sorts | No (production designing one now) | — |
| Salary left, stack score as sort keys | No (only as construction rules) | — |

So the simulation-against-a-field family, which is what the professionals use, has been tried here and lost, because
our simulator's tails have not been good enough. What was never tried are the simple, transparent keys the professionals
use as filters and tie-breakers.

## 3. A screen of eight sort keys on the real 2026 fields

For each week, the pool is every lineup our builds kept before lock (1,447 in Week 1; 13,000–17,000 in Weeks 2–4, mostly
sampled-world rows). Each key ranks the pool; the book is the top 26 with at most seven players shared between rows (the
professionals' "uniques"); it is scored on the real Millionaire field and placed among 2,000 random 26-row books from the
same pool (0.5 = no better than random picks). All keys are pre-lock. The pool itself held few top-1% lineups: 0.55%,
0.08%, 0.37% and 0.71% of its rows, so a random 26-row book holds 0.02–0.20 of them on average.

| Key | What it ranks by | Best row vs random books (W1 / W2 / W3 / W4 → mean) | Average finish vs random (mean) | Top-1% rows (four weeks) |
|---|---|---|---|---|
| STACK | pass-catchers with the QB + bring-backs | .87 / .16 / .90 / .54 → **.62** | .70 | 1 |
| PROJ | our projection | .56 / .37 / .90 / .54 → .59 | .73 | 0 |
| SALARY_LEFT | most salary left (above-median projection) | .76 / .09 / .61 / .77 → .56 | .72 | 0 |
| OPTIMAL | how often its players are in a sampled world's best lineup | .43 / .16 / .92 / .70 → .55 | .64 | 1 |
| **TD** | **sum of anytime-touchdown probabilities (production's test)** | .43 / .75 / .82 / .04 → **.51** | **.80** | 0 |
| MARKET | sum of props-implied projections | .56 / .00 / .90 / .08 → .39 | .51 | 0 |
| TD_VALUE | cheap players whose TD odds beat their salary | .43 / .23 / .00 / .65 → .33 | .70 | 0 |
| UNIQUE | lowest ownership product (W3–4) | .08 / .22 → .15 | .82 | 0 |
| LEVERAGE | optimal % minus projected ownership (W3–4) | .05 / .13 → .09 | .47 | 0 |

**No key reliably beats random picks from our pool at the top end** (best row, top-1% rows); the best is level with
noise (0.62), the worst two are the ownership keys. Several keys improve the **average** finish (touchdowns most, 0.80),
which is not the operator's goal. This is the project's standing result seen from the professionals' side: the pool
holds very few top-1% lineups, and no ranking finds them more often than chance. In Week 4, the one Fantasy Points
week, the touchdown key was worse than random at the top (0.04).

## 4. Recommendations

1. **Production's touchdown sort:** worth running, but set its success criterion on the big-win chance, not the average
   finish; this screen predicts it will improve the average and be level at the top. If it is tested, also test the
   per-game version (the QB stack's implied team touchdowns) beside the per-player sum.
2. **The professionals' core method, a simulated ROI against a simulated field, has already lost here** (PREREG-098)
   because it can only be as good as our simulator's tails. It becomes worth retrying only after the simulation or the
   projections improve, not as a sorting change.
3. **The one sort with a clear mechanism is duplication, used for dealing rather than ranking:** send the rows with the
   fewest expected copies (the ownership product) to the one-seat satellites, where a tie halves or loses the seat.
   That is a small, checkable change (the copies are observable every Monday), not a bet on finding winners.
4. **The lever stays upstream of sorting:** the pool held 0.08–0.71% top-1% rows. A sort can only choose among what the
   pool contains; today's experiments say the pool improves when the environment is right and when the player inputs
   carry information (the market's touchdown price against salary in the field data; Fantasy Points' projections).
