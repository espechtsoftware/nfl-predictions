# What the Milly graph shows about sorting: the regulars' winning lineups carried more sub-$4,000 players (2026-10-07)

The operator (10-07): "have we given up on the use of neo4j for sorting? are there any insights that we can gain from the
neo4j data now that it includes more data on players?" By the outside reviewing agent. Scripts:
`reports/2026-10-07-winners-strategy-study/graph/within_portfolio.py`, `cheap_count_check.py`; aggregates only (no user
names, no vendor values).

## 1. The test only the graph can run: inside a good portfolio, do the winning lineups look different before lock?

For every regular (users with 20+ lineups in a week; 351 user-weeks, 51,729 lineups, 1,075 in the real top 1%), each
pre-lock lineup fact was standardized within that user's week, and the top-1% lineups were compared with the same
user's other lineups. This removes skill and information: it asks only whether one of a good player's lineups can be
told from his others before kickoff.

| Pre-lock fact (within the user's week) | Top-1% lineups vs his other lineups (sd) | 95% interval | W1 / W2 / W3 / W4 |
|---|---|---|---|
| **sub-$4,000 non-DST players** | **+0.43** | +0.36 to +0.49 | +0.34 / +0.52 / +0.34 / +0.61 |
| mean prior snap share of the skill players | −0.35 | −0.43 to −0.27 | — / −0.30 / −0.37 / −0.31 |
| tight end's salary | −0.29 | −0.35 to −0.22 | −0.23 / −0.35 / −0.09 / −0.33 |
| props-implied minus our projection | +0.18 | +0.10 to +0.25 | +0.34 / +0.19 / +0.26 / +0.04 |
| prior target share (WR/TE) | −0.15 | −0.22 to −0.07 | — / −0.15 / −0.12 / −0.02 |
| our projection | 0.00 | −0.07 to +0.08 | +0.34 / −0.21 / +0.02 / −0.34 |
| (every other fact: QB environment, stack, touchdowns, red zone, prior top-1% share, …) | | | signs change by week |

Top-1% rate of the regulars' lineups by the number of sub-$4,000 non-DST players:

| | none | one | two |
|---|---|---|---|
| W1 / W2 / W3 / W4 | .74 / .16 / .79 / .22% | 1.34 / 2.02 / 1.68 / 1.62% | 2.99 / 3.82 / 2.73 / 2.36% |

The same gradient holds in **the whole real field** (none .75 / .08 / .31 / .38%; one .97 / 1.15 / 1.26 / 1.34%; two
1.61 / 1.82 / 2.45 / 1.50%), and only weakly in **our own candidate pool**. **Our books carry few such lineups**: the
live Week-5 settings replayed on Weeks 3 and 4 put two sub-$4,000 players in 1 of 26 rows and none in 9–13.

## 2. The construction test: a preference for sub-$4,000 players (not a mandate)

The live Week-5 book (overlap 4, round-robin, QB cap 5, no term) with a bonus of +2 or +4 projected points for every
non-DST player under $4,000, Weeks 2–4 real fields (`run/experiments/replay_cheap.sh`).

| Arm | P(≥1 big) W2 / W3 / W4 | mean entry percentile W2 / W3 / W4 | sub-$4k per row |
|---|---|---|---|
| live | .041 / .002 / .434 | .424 / .516 / .502 | 1.35 / 0.54 / 0.69 |
| +2 | .000 / .319 / .641 | .419 / .506 / .573 | 2.12 / 2.15 / 1.35 |
| **+4** | **.655 / .127 / .160** | **.471 / .569 / .665** | 2.58 / 3.12 / 2.19 |

The +4 preference improves the average finish in all three weeks (+5, +5, +16 percentile points) and the big-win chance
in two of three; +2 is ahead on the big-win chance in two of three. **In-sample** (the pattern was found on these
weeks), but the population that found it (the regulars' own portfolios, the whole field) is independent of our build.
The project removed a hard "at least one sub-$4,000 player" rule in August (Addendum 77) on the old historical panel; the
live book now solves on Fantasy Points' means and has neither that rule nor the old ceiling valuation of cheap players.

## 3. Status of the graph for sorting

Not given up. The winner-likeness score (study 48, built on the graph's facts) passed its mechanism test, then read no
difference as a deal order (48b), a selection (48d) and a generation gate (48e); on real fields it had no support among
high-projection lineups. Its real-field refit (48f) is frozen and grades Weeks 5–8 prospectively. The finding above is
the first pre-lock fact that sorts lineups inside good portfolios in every week, and the natural next step is a
preregistered harness study of the +2/+4 preference with the 2022 go/no-go, the process every live lever has followed.
