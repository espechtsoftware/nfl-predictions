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

## 4. Which cheap players (added 10-07, 10:30 CT; `graph/cheap_tier.py`)

All 546 sub-$4,000 RB/WR/TE player-weeks of W1–4, scored with the real contest points; boom = 15+ DK points (20 booms, 3.7%).
- **The regulars pick better cheap players than the field:** ownership-weighted points 12.2 vs 9.9 (three weeks of four),
  boom share 31% vs 23%.
- **Their lean tracks the betting market:** Spearman with the props-implied projection +0.82, the anytime-TD odds +0.47,
  our projection +0.44, target share +0.44, snap share +0.41, Fantasy Points route share +0.33; vacated opportunity +0.07.
- **What separates the booms (tercile within week, low / high, positive in all four weeks):** props-implied points
  3.2% / 18.5%; anytime-TD odds 0.6% / 10.7%; route share 0.6% / 9.3%; our projection 0.6% / 9.8%. Not: vacated
  opportunity, depth-chart moves, route-share jump, team total.

**Refined preference, same replay:** +4 only for the top third of each week's cheap players by props-implied points
(cheapmkt4) or by TD odds (cheaptd4).

| Arm | P(≥1 big) W2 / W3 / W4 | mean entry percentile W2 / W3 / W4 |
|---|---|---|
| live | .041 / .002 / .434 | .424 / .516 / .502 |
| +4 all cheap | .655 / .127 / .160 | .471 / .569 / .665 |
| +4 market-rated cheap | .083 / .008 / .160 | .480 / .523 / .665 |
| +4 TD-rated cheap | .646 / .127 / .160 | .481 / .569 / .665 |

The refinement does not beat the plain preference; the market-rated set is mostly cheap tight ends. Every cheap
variant improves the average finish in all three weeks and trails live on the big-win chance in Week 4; the laptop's
reading (10-07) is right that the replay is dose-unstable (+2 trails in W2, +4 in W4), which is why the harness study
(study list 51) decides.

## 5. The cheap preference as Saturday's 8-row block (added 10-07, 10:45 CT) — the form that could enter Week 5

The laptop's own block harness (`bonus_blocks_replay.sh`, copied as `run/experiments/cblocks_replay.sh`; production at
the integration head, the live W5 settings, Rev3, head layout), 8 of 26 rows built on projection + min(0.20 × pred_own,
cap) from the cheap file, the other 18 as live. W2–4 real fields.

| P(≥ 1 big) | W2 | W3 | W4 | weeks below live | expected big seats vs live | mean entry percentile W2 / W3 / W4 |
|---|---|---|---|---|---|---|
| live | .041 | .002 | .434 | — | 1.00 | .424 / .516 / .502 |
| **cheap block, +2** | **.058** | **.018** | **.535** | **0** | **1.46** | .449 / .500 / .570 |
| **cheap block, +4** | **.084** | **.018** | **.529** | **0** | **1.52** | .437 / .495 / .563 |
| matchup block (the laptop's run, 10-07) | .031 | .018 | .530 | 1 | 1.40 | — |

The block form is ahead of live in **all three weeks at both doses** (the whole-book form was dose-unstable); it passes
the frozen block screen production applied to the matchup and TD blocks (not entered if below live in 2+ weeks or the
pooled expected-seats ratio is under 0.80). In-sample: the cheap idea came from W1–4; the block form and doses were not
tuned on these numbers. Study 53's CHEAP4_BLOCK8 arm (Thursday) is the out-of-sample read.

**Sort-key deals (`sortdeal_replay.sh`), the same live books re-dealt:** cheap count (below live in 2 of 3 weeks,
expected-seats ratio 0.79) and props-minus-projection (2 of 3, 1.04) do not help; projection order (control) 1 of 3,
1.02. Sorting stays at chance.

**Writer:** `scripts/cheap_block_file.py` (`--season --week --frame --points --out`; the matchup writer's columns and
refusals; public salaries only), test `tests/test_cheap_block_file.py` (7 pass); it reproduces the six replay files exactly.
