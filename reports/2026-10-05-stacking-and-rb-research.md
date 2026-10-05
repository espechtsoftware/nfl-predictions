# How winners stack, and how they use running backs (2026-10-05)

Written for the operator and the reviewer. Descriptive research for the operator's questions (10-05):
- "I think we should be doing more like what the winners do. Also, have we tried dual stacks…?"
- "we need to study how they use running backs in those stacks. I'm guessing that sometimes they have an RB from the same
  team thinking that if they are ahead, the RB will get more carries plus there will be more goal line opportunities."

Aggregates only. The scripts are private (`~/private/week4-monday/stack_shapes.py`, `rb_shapes.py`); the queries are
reproduced below.

**Caveat:** "what the winners do" is measured on OUTCOMES. The top 1% each week reflects which games happened to hit,
so these shapes inspire test arms. They are not rules. Every number below compares winners with the FIELD as well as
with us, which separates "winners do this" from "everyone does this".

## 1. Stack shapes (2026 Weeks 1–4 Millionaires; mean of the four weeks)

| | top 0.1% | top 1% | field | OUR entries |
|---|---|---|---|---|
| QB + 1 teammate only | 52% | 48% | 53% | 6% |
| QB + 2 or more teammates | 43% | 44% | 30% | 94% |
| Bring-back | 63% | 59% | 43% | 97% |
| Players from the QB's game | 3.3 | 3.2 | 2.8 | 4.2 |
| A second game with players from BOTH teams (a "dual stack") | 49% | 46% | 46% | 15% |
| Games used per lineup | 4.8 | 4.9 | 5.3 | 4.1 |

- **Winners stack more than the field,** but far less rigidly than our rule (QB + 2 + bring-back) combined with our
  mean-max optimizer, which puts 4+ players into one game.
- **QB + 2 among the top 1% swings by week:** 71% in Week 3, 26% in Week 4. The Week-4 statement that "winners don't use
  QB + 2" was one week, corrected.
- **Dual stacks are field-normal; our book is the outlier.** Never tested as an arm. That is now study 18 (designed;
  frozen after study 17's read).

## 2. Running backs in lineups (2026 Weeks 1–4 Millionaires; mean of the four weeks)

| | top 0.1% | top 1% | field | OUR entries |
|---|---|---|---|---|
| An RB from the QB's own team | 10% | 12% | 18% | 24% |
| …when that team was favored | 7% | 10% | 13% | 13% |
| An RB as the BRING-BACK (the QB's opponent) | 33% | 28% | 16% | 37% |
| An RB with his own team's DST | 14% | 14% | 16% | 7% |
| An RB against the opposing DST | 3% | 3% | 2% | 0% (house rule) |
| Two RBs from the same team | 0% | 0% | 0% | 0% (house rule) |
| An RB in the FLEX | 29% | 33% | 39% | 30% |

- **Winners paired the QB with his own RB LESS often than the field,** even when the team was favored.
- **What winners did more:** use an RB as the bring-back, about twice the field's rate, though it swings from 8% to 52%
  by week.

## 3. Does a favored team's RB get more carries and goal-line work? (2014–2025, 6,126 team-games; the team's lead RB by carries)

| Pre-game spread | Carries | Targets | TDs | Team goal-line carries (inside the 5) | PPR points | Final margin |
|---|---|---|---|---|---|---|
| favored by 7+ | 15.7 | 3.1 | 0.76 | 1.6 | 16.3 | +10.5 |
| favored by 3–6.5 | 15.8 | 3.4 | 0.67 | 1.5 | 15.6 | +4.4 |
| pick-em (< 3) | 15.5 | 3.3 | 0.57 | 1.33 | 14.4 | 0.0 |
| underdog by 3–6.5 | 15.1 | 3.4 | 0.53 | 1.25 | 13.8 | −4.2 |
| underdog by 7+ | 14.3 | 3.3 | 0.42 | 1.07 | 12.5 | −10.4 |

**The operator's theory is right in direction:** a big favorite's lead RB scores about 3.8 more points than a big
underdog's. That comes mostly through TOUCHDOWNS (+0.34) and goal-line chances (+50%), not carries (+1.4). The spread and
the implied total are already model inputs, and the market props (55% of each projection) reflect them, so this is
probably already priced. A residual check (our RB projection error by spread bucket) is a possible follow-up.

## 4. How strongly do players' scores move together? (2014–2025, PPR, per team-game)

| Pair | Correlation |
|---|---|
| QB – own WR1 | 0.45 |
| QB – own TE1 | 0.30 |
| QB – opposing WR1 (a WR bring-back) | 0.11 |
| QB – own RB1 | 0.09 |
| QB – opposing RB1 (an RB bring-back) | 0.04 |
| RB1 – own WR1 | 0.03 |
| RB1 – opposing RB1 | −0.05 |

- **Pairing the QB with his own RB adds little correlation (0.09):** an RB's points come from script and touchdowns, not
  the passing game. The QB–pass-catcher stack is the strong one.
- **An RB bring-back is nearly uncorrelated with the QB (0.04).** Winners' extra RB bring-backs are therefore not about
  correlation: more likely value or leverage at RB, in the weeks the script broke that way.

## 5. What it changes
- **Study 18** (designed with the reviewer; runs after study 17) tests the operator's dual stack and a field-normal shape
  (QB + ≥ 1 teammate, an optional bring-back, ≤ 3 from the QB's game, plus a second-game pair).
- **No separate RB arm:** the data does not favor a QB + own-RB rule, and the favorite-RB effect is probably already
  priced. The RB bring-back pattern is outcome-measured and swings by week.
- **To find patterns like these without waiting for the right question:** a weekly automatic "how are we different"
  scorecard. Our book vs the field vs the top 1% on stack shape, RB use, players per game, salary spread, cheap players,
  ownership and duplication, with the biggest gaps ranked. It is to be built as a permanent Monday step beside the monkey
  benchmark.

## Queries (BigQuery, `nfl-predictions-503414`)
- **Section 3:** `nfl_raw.schedules` (spread_line, result; REG 2014–2025), joined to `nfl_raw.weekly_stats` (the lead RB
  by carries per team-game) and `nfl_raw.pbp` (rushes at yardline_100 ≤ 5).
- **Section 4:** `CORR()` of `fantasy_points_ppr` between position leaders (QB by PPR; RB by carries; WR and TE by
  targets) within a team-game, or across the two teams of a game.
