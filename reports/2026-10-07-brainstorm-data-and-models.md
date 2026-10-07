# Brainstorm: what to add to Neo4j, what models to train, and what today's quick tests say (2026-10-07)

The operator, 10-07: *"please keep brainstorming. If there is additional data that you think we should add to neo4j or
models to train that will help us gain insights, I'm all for it."*

Outside reviewer, Wednesday of Week 5. Everything below was measured today on data we already hold: the Week 1–4 real
Millionaire fields (1.33M lineups), the T-70 frames and world draws, and 2014–2025 history. Scripts and their full output
are in `reports/2026-10-07-brainstorm/`. Aggregates only: user names are fingerprinted inside BigQuery and never
downloaded, and no per-player vendor values appear.

## 0. In plain words

**What I tested today (nine quick checks):**

1. **The cheap-player pattern holds across the whole field, not just the regulars.** Inside the same person's set of
   lineups, the ones with two or more players under $4,000 had about **twice the odds** of a top-1% finish. That held
   in **each** of the four weeks (odds ratio 1.7 to 2.5). Across all 1.33M field lineups, lineups with *no* cheap player
   reached the top 1% at 0.08–0.75%, against an average of 1%.
2. **It is not a simulator flaw.** Our simulator does not underrate cheap players' upside. The draws the build uses
   actually *overrate* the long tail of fringe cheap players. So the edge comes from using one or two good cheap
   players, and the flat cheap block is the right way to test it.
3. **Where the cheap player sits doesn't matter reliably.** Whether he is in the QB's stack or elsewhere flipped from
   week to week. Keep the block simple.
4. **A second consistent pattern: don't pay up for the defense.** Lineups with a defense under $3,000 had 2.9× the odds
   of those with a $3,500+ defense, in all four weeks. History agrees: an extra $1,000 buys about 2.5 points at DST,
   against 3.5–6 points at the other positions. **Our entered Week 2–4 books paid up for defenses far more than the
   field. The Week-5 settings already fixed that.**
5. **Game choice.** Over 207 past Sundays, the four highest-total games held the slate's best stack 55% of the time.
   **Our entered Week 1–4 books put only 13–48% of rows there** (Week 4: 13%); the field put about 50%; the top-1%
   lineups 49–76%. **The Week-5 settings put 65% there, so this is also already fixed.**
6. **Two more consistent patterns are standard practice we already follow:** always stack the QB (an unstacked QB
   halves the odds), and use your salary (leaving $1,000+ unused halves them).
7. **The betting market's touchdown prices per game add nothing beyond the Vegas total.**
8. **Late news can't be measured from our archive**, because each week's earliest saved projection is from Saturday.
   An earlier study found the closing line already absorbs the week's news.
9. **Three ideas I looked at were already tested and closed:** alternate prop ladders, late swap, and copying the
   regulars' player picks.

**What I recommend, in order:**

1. **Run a weekly real-field monitor (ready now: `scripts/field_pattern_monitor.py`, 7 tests).** Every Monday it adds
   one new, independent week of evidence on the cheap pattern and checks our game coverage against history. It is the
   only way to get more real-field weeks than the four we have.
2. **Train a cheap-boom model:** which sub-$4k players reach four times their salary. Train it on the 12 seasons of
   DraftKings salaries we already hold. If it beats the flat +2 in the same tests study 53 runs, a graded block becomes
   a Week-6+ candidate.
3. **Add game results and a few lineup-shape labels to Neo4j**, so that "did we cover the game that won?" and "which
   shapes won inside portfolios?" are one query each Monday.
4. **Train a game-environment model** (which game holds the best stack) on 207 past slates, to sharpen how rows are
   spread across games beyond the total's rank.
5. **Compile a historical winners table** from public weekly Millionaire recaps (about 100 winning lineups,
   2019–2025), to check this season's patterns on more than four weeks.

**This week:** nothing new to change. The whole-field result strengthens the case for Saturday's cheap block, and study
53 still decides it. The defense price and game coverage are already handled by the Week-5 settings.

## 1. What the tests found

### 1.1 The cheap-player pattern on the whole field (`field_within.py`, `field_pattern_monitor.py`, `cheap_mh.py`)

Population: every user with 20+ entries in the week's largest Millionaire: W1 6,449 users / 389,562 lineups; W2 934 /
56,162; W3 914 / 55,216; W4 924 / 56,779. The comparison is **within each user-week** (the same person, the same
slate), so skill differences between users cannot produce it.

| Within user-week, top-1% vs the same user's other lineups | Pooled [95%] | W1 | W2 | W3 | W4 |
|---|---|---|---|---|---|
| Sub-$4k non-DST players, standardized difference | +0.31 sd [+0.28, +0.34] | +0.20 | +0.54 | +0.45 | +0.52 |
| Salary used, standardized difference | +0.05 sd [+0.02, +0.08] | +0.05 | +0.02 | +0.07 | +0.08 |
| Most expensive player's salary | +0.30 sd [+0.28, +0.33] | +0.34 | +0.03 | +0.81 | −0.14 |
| **Mantel–Haenszel odds ratio, 2+ sub-$4k vs 0–1** | **1.88 [1.75, 2.01]** | 1.69 | 2.46 | 2.30 | 2.10 |
| Odds ratio, 1+ sub-$4k vs none | 1.89 [1.75, 2.06] | 1.31 | 14.32 | 2.65 | 5.22 |

The whole field (all 1.33M lineups, single-entry users included), top-1% rate by the number of sub-$4k players:

| Sub-$4k players | W1 | W2 | W3 | W4 | Share of field lineups W1–W4 |
|---|---|---|---|---|---|
| 0 | 0.75% | 0.08% | 0.31% | 0.38% | 31 / 26 / 43 / 37% |
| 1 | 0.97% | 1.15% | 1.26% | 1.34% | 53 / 55 / 44 / 49% |
| 2 | 1.61% | 1.82% | 2.45% | 1.50% | 16 / 18 / 12 / 13% |
| 3+ | 0.65% | 1.92% | 2.12% | 0.73% | about 1% |

For comparison, our entered T-70 books (the laptop's count): 0.79 / 1.13 / 0.85 / 0.91 sub-$4k players per row, rows with
2+ .12 / .28 / .17 / .16. That is about the field's level. The cheap block moves us above it.

**Caveat (the laptop's, agreed):** this is an association with the realized top 1% on four slates. Within a portfolio,
the lineups that boomed are the top-1% ones, and cheap players add variance. Extra variance is part of the mechanism we
want, since the target is the top-1% rate rather than the mean. Whether the pattern holds on other slates *beforehand*
is study 53's question (2023–24 sampled fields, the 2022 go/no-go). The weekly monitor (§2, D1) adds real-field weeks.

### 1.2 Is it a simulator calibration error? No (`tail_calibration.py`)

For each player in the W1–4 T-70 frames (QB/RB/WR/TE, sim mean ≥ 1), the summed probability of a boom from the 10,000
draws was compared with the realized count. Each cell shows observed / expected, with z = (observed − expected) / sd.

| Tier | Draws | 4× salary | 5× salary | 2× own sim mean | 25+ points |
|---|---|---|---|---|---|
| Sub-$4k (529) | incumbent (the build's) | 27 / 46.0 (z −3.0) | 14 / 27.1 (z −2.6) | 70 / 109.7 (z −4.3) | 4 / 3.2 |
| Sub-$4k (302) | corrected_hsim | 24 / 25.6 (z −0.4) | 14 / 13.5 | 40 / 41.6 | 4 / 2.5 |
| $6–7.9k WR (55) | incumbent | 12 / 5.1 (z +3.3) | 2 / 2.0 | 8 / 3.2 | 14 / 6.7 (z +3.1) |
| $6–7.9k WR (55) | corrected_hsim | 12 / 8.0 | 2 / 3.3 | 3 / 3.4 | 14 / 9.9 |

The build's draws **over-state** booms for the long tail of fringe cheap players. That matters only where worlds build
rows (the boom pool and tail sleeve), and it is an open item (§3, M3). The corrected draws are calibrated. So the field's
cheap edge is not something the simulator misses at the tier level. It is about using one or two *good* cheap players,
and about mean-maximizing MILPs not valuing the salary they free.

### 1.3 Where the winning cheap players sit (`cheap_where.py`)

| Within user-week odds ratio | Pooled [95%] | W1 | W2 | W3 | W4 |
|---|---|---|---|---|---|
| Cheap player in the QB's stack vs cheap players elsewhere only | 1.60 [1.50, 1.73] | 1.94 | 1.03 | 3.45 | 0.33 |
| Cheap bring-back only vs elsewhere only | 0.51 [0.44, 0.59] | 0.58 | 0.20 | 0.09 | 0.96 |
| Cheap stack piece vs no cheap player | 2.51 [2.27, 2.80] | 1.99 | 15.38 | 4.63 | 2.46 |
| Cheap players elsewhere only vs none | 1.75 [1.61, 1.93] | 1.15 | 15.84 | 1.55 | 6.95 |

Any cheap player beats none in every week. *Where* he sits flips with the week, because it depends on which game booms.
So targeting the bonus to stack pieces is not supported. A cheap bring-back was the weakest place in three weeks of
four. It is noted here, but it is not a rule.

### 1.4 A structural screen of the whole field (`structure_screen.py`, `dst_value.py`)

The same within-user odds ratio, for lineup shapes on the four real fields (multi-entry users, lineups with all nine
players matched):

| Structure (vs reference) | OR [95%] | W1 | W2 | W3 | W4 | Weeks |
|---|---|---|---|---|---|---|
| **DST < $3,000 vs ≥ $3,500** | **2.86 [2.51, 3.33]** | 4.21 | 4.92 | 3.04 | 1.28 | all > 1 |
| Naked QB vs QB + 2 | 0.54 [0.46, 0.63] | 0.54 | 0.89 | 0.09 | 0.73 | all < 1 |
| Salary left ≥ $1,000 vs ≤ $200 (2.5% of lineups) | 0.56 [0.41, 0.73] | 0.51 | 0.84 | 0.35 | 0.83 | all < 1 |
| Salary left $300–900 vs ≤ $200 | 0.95 [0.88, 1.01] | 1.00 | 0.89 | 0.82 | 0.79 | all ≤ 1 |
| QB + 1 vs QB + 2 | 0.80 | 0.69 | 0.90 | 0.59 | 1.98 | mixed |
| QB + 3+ vs QB + 2 | 1.32 | 1.50 | 0.99 | 1.08 | 0.72 | mixed |
| Bring-back 1+ vs none | 1.77 | 2.32 | 0.58 | 1.42 | 1.65 | mixed |
| FLEX RB vs FLEX WR | 1.25 | 1.56 | 0.24 | 1.17 | 0.85 | mixed |
| FLEX TE vs FLEX WR | 1.04 | 0.76 | 1.55 | 1.78 | 1.42 | mixed |
| ≤ 4 games used vs 6+ | 2.10 | 2.74 | 0.61 | 1.81 | 0.92 | mixed |
| 5+ players from one game vs ≤ 3 | 2.43 | 3.42 | 0.43 | 2.37 | 0.53 | mixed |
| QB ≥ $7,000 vs < $6,000 | 1.06 | 2.46 | 0.52 | 0.01 | 0.43 | mixed |
| RB with his own DST vs not | 0.86 | 0.86 | 0.83 | 0.61 | 1.14 | mixed |
| A player facing his own DST vs not | 0.87 | 0.76 | 1.49 | 0.55 | 1.09 | mixed |

Fourteen shapes were screened, so one or two "all four weeks" results could appear by luck (about 1 in 8 per shape
under no effect). The cheap-DST result is large in three weeks and agrees with history.

**History (2014–2021, the `dk_salaries_historical` rows that carry DK points):** an extra $1,000 of salary buys **+2.5
points at DST** (2014–17 +2.60, 2018–21 +2.54), against WR +3.5, TE +3.6, RB +4.0 and QB +6.1 (2018–21). Expensive
defenses do boom more often (20+ points: 1.7% under $2.5k vs 10.5% at $4k+), but each dollar buys the fewest points
there.

**Our books:** share of rows with a DST ≥ $3,500, our book vs the field:

| | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| Entered T-70 book | .01 | **.57** | **.33** | **.65** |
| W2–4 replays at Week-5 settings (live) | — | .31 | .04 | .04 |
| The real field | .06 | .34 | .13 | .27 |

The entered W2–W4 books paid up for defenses far more than the field. The Week-5 settings use cheaper defenses than the
field. Nothing to change; the monitor can watch it. Side note: the cheap +2 block moves a little salary back into DST
(W2 .31 → .42; W3 .04 → .08).

### 1.5 Game coverage (`game_leverage.py`, `book_game_ranks.py`, `field_pattern_monitor.py`)

**History, 207 Sunday main slates 2014–2025** (13:00–16:30 ET kickoffs, ≥ 6 games): how often the game with the k-th
highest closing total held the slate's best stack (QB + 2 teammates + 1 opponent, DK points):

| Total rank | 1 | 2 | 3 | 4 | 5 | 6 | 7th+ (per game) |
|---|---|---|---|---|---|---|---|
| P(best stack game) | 21.7% | 14.0% | 10.6% | 8.7% | 6.8% | 9.7% | 5.3% |
| 2020–2025 only | 24.5% | 16.0% | 14.2% | — | — | — | 5.6% (4th+) |

The top four games together: 55% (about 60% in 2020–25). A random game would be 8.8%.

**2026, share of lineups by the QB's game total rank (W1–4 means):**

| Total rank | 1 | 2 | 3 | 4 | 5 | 6 | 7th+ (summed) |
|---|---|---|---|---|---|---|---|
| Field | .181 | .149 | .087 | .082 | .085 | .072 | .344 |
| Top-1% lineups | .157 | .109 | .212 | .166 | .099 | .038 | .220 |
| Entered T-70 books | .130 | .104 | .068 | .066 | .061 | .186 | .384 |

| Top-4 games' share | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| Field | .54 | .51 | .46 | .50 |
| Top-1% lineups | .49 | .60 | .73 | .76 |
| Entered T-70 books | .46 | .41 | .48 | **.13** |
| W2–4 replays at Week-5 settings (live / cheap +2) | — | .73 / .73 | .58 / .54 | .65 / .65 |

The entered books under-covered the games most likely to hold the best stack. Week 4's (with the ownership term) put 87%
of its rows in games ranked 6th or lower. The Week-5 settings put 65% in the top four, slightly above the historical
base rate. This supports the decision to drop the term. The monitor reports this every week.

### 1.6 Market touchdowns per game (`news_and_games.py`, part 2)

The sum of every player's anytime-TD probability per game (last pre-lock snapshot), compared with the Vegas total, as a
predictor of the game's realized skill DK points (Spearman, 50 games): total +0.52, TD sum +0.49, and **TD sum beyond
the total −0.07**. In every week the top game by total and by TD sum was the same game. Nothing to add.

### 1.7 Late news (`news_and_games.py`, part 1)

The earliest archived build frame for each week is from Saturday afternoon (W4: Sunday morning). Only 9 / 2 / 3 players
moved 1.5+ projected points before T-70 in W2–W4. Week 1's 215 movers reflect a model change, not news. So our archive
cannot measure late news. Addendum 17 (54 weeks of DraftKings opening vs closing lines) already found that the close
absorbs the week's news. Collecting Wednesday projections would only matter for *ownership* (does the field anchor to
early-week values?), which is low priority while the ownership term is off.

### 1.8 Already tested and closed (checked against both ledgers before proposing)

- **Alternate prop ladders:** Addendum 45 found the market's implied q90 calibrated (2023–25 ladders). The ladder lever
  was closed when its mechanism gate failed (09-02 review; `reports/2026-10-04-different-approaches.md`). The 2026
  collector pulls no alternate markets, so the lab's "parked until 2026 ladders accumulate" row can never resume as
  written. It should be closed in the lab ledger too.
- **Late swap:** lab cohorts 023 (−1.23) and 024 (−0.42), both with valid information sets. Closed.
- **Copying the regulars' player picks:** the habit model predicts their picks (ρ .51–.58) but not their edge (failed
  pre-test, HANDOFF 10-06).
- **Pace / Vegas-pace drive counts in the simulator:** null (the system study's lever table, `GAME_SIM_PACE=vegas`).
- **Line movement:** Addendum 17, null.

## 2. Data to add (Neo4j and BigQuery), ranked

**D1. The weekly real-field monitor: no new data, ready now.** `scripts/field_pattern_monitor.py` (BigQuery only, no
Neo4j; about 3 minutes for four weeks). For every week with a real field, it prints:
- the within-user odds ratios for the cheap pattern (2+ vs 0–1, 1+ vs none), per week and pooled with a 95% interval;
- the whole-field top-1% rate by cheap count;
- the share of field, top-1% and book lineups by the QB's game total rank, next to the historical base rates.

It writes a CSV. Run on W1–4 it reproduces §1.1 and §1.5 exactly (`field_pattern_monitor_w1-4.txt`).

*Proposed reading, for the reviewer to freeze before Monday's W5 field loads:* the pattern holds prospectively if the
2+ vs 0–1 odds ratio is above 1 in at least 3 of W5–W8 and the pooled W5–W8 lower bound is above 1. It is descriptive
and gates nothing on its own. Each new week is an independent outcome that study 53's history cannot supply.

**D2. Game result facts in Neo4j.** Add to each `Game` node:
- `total_rank` (the tie rule as in the monitor: ties broken by game id);
- `best_stack_pts`, and `is_best_stack_game` for the week's top one;
- `field_qb_share` and `top1_qb_share`.

Give our own lineups (the `PoolLineup` / book rows) the QB's game rank too. Then "did we cover the game that won?" is
one Cypher line each Monday. Small: the loader already builds Game and TeamWeek facts (production's
`milly_graph_facts.py`; a production change, their call).

**D3. A few more shape labels on every `Lineup`.** The graph already carries `lbl_cheap_players`, `lbl_salary_left`,
`lbl_dst_salary`, `lbl_games`, `lbl_dual_stack` and `lbl_qb_game_rank`. Add:
- `lbl_stack_n` (QB teammates);
- `lbl_bring_n`;
- `lbl_flex_pos`;
- `lbl_max_game` (players from the most-used game).

With those, §1.4's screen runs in the graph every week, and the "mixed" shapes can be tracked for a pattern that firms
up.

**D4. Points for the 2022–2025 salary rows.** `dk_salaries_historical` carries DK points through 2021. Of the
2022–2025 rows, 58,139 have salaries without points (all of 2022–24, and all but 528 in 2025); the salary gap is already in the README's deficiency log. A
derived view joining those rows to `player_week_actuals` (name + team + week) gives 12 seasons of salary and points.
The models in §3 need it.

**D5. A historical winners table.** There is no central database. Winning Millionaire lineups are published weekly by
public recaps (4for4, Stokastic, Footballguys, RotoGrinders). About 100 winning lineups from 2019–2025, joined to the
historical salaries, would show how often past winners had 2+ cheap players, a cheap DST, or a QB from the top-4 total
games. That checks this season's patterns on more than four weeks. Compile by hand or with a careful collector that
respects the sites' terms. Keep only derived counts in tracked files.

**D6. Practice-report trajectories and defensive injuries as facts.** Wed/Thu/Fri practice status per player (a
`PlayerWeek` fact), and per defense the starters out (CB/S/edge; a `TeamWeek` fact linked to the opposing offense).
These are inputs for the cheap-boom and game models (§3). `nfl_raw.injuries` has report status; whether it carries the
daily practice lines needs a check.

**D7. Weather into Game nodes.** `nfl_raw.weather` (199 rows, 2026: wind, precipitation, dome). Small; mainly for the
game model.

**Not recommended:** alternate ladders (closed), `odds_movement` (the table is empty, and the close absorbs news),
per-game market TD sums (redundant with the total).

## 3. Models to train, ranked

**M1. A cheap-boom model.** P(a sub-$4k WR/TE, or a near-minimum RB, scores 4× salary).
- **Data:** 2014–2025 salaries (D4 for 2022–25 points), role (`player_week_role` depth rank, rookie, depth change), lagged
  usage (the feature tables' snap/target/route shares), team implied total, the matchup term (O-40), and from 2023 the
  market lines.
- **Validation:** walk-forward by season. Baselines: salary alone, our projection, props-implied points.
- **Use:** a graded block (tilt × P(boom)) in place of the flat +2, tested exactly as study 53 tests the flat one.
- **Honest prior:** my market-rated refinement did not beat the flat block in the W2–4 replay, and the regulars' cheap
  picks already track props-implied points (ρ .82). The model has to beat the market to matter. It would also give the
  incumbent draws' fringe-cheap over-statement (§1.2) a calibration target.

**M2. A game-environment model.** P(game holds the slate's best stack).
- **Data:** closing total, spread, implied team totals, pace / PROE / expected plays (already frame columns: `pace_l4`,
  `proe_l4`, `expected_plays`), weather (D7), and defensive injuries (D6). 207 slates from 2014–2025.
- **Baseline:** the rank table in §1.5.
- **Use:** allocate QB rows across games by P(best) rather than by rank alone.
- **Honest prior:** market TD sums added nothing beyond the total (§1.6), and the Week-5 settings are already near the
  base rates. Worth it only if it beats the rank table out of sample.

**M3. Repair the incumbent draws' fringe-cheap tail** (§1.2; z −3.0 at 4× salary). A per-tier/role calibration of the
draws for low-role cheap players. It matters where worlds build rows (the boom pool and tail sleeve), not for the
FP-mean MILPs.

**M4. A weekly $6–7.9k tier check** (aggregate only). That tier is where our W1–4 picks lost most (−6.0 points per
lineup), and where our projection ran +0.6 above the market. Now that FP's means drive the build, check FP vs market
there each week. Also note the incumbent draws under-state $6–7.9k WR booms (25+ points: 14 observed vs 6.7 expected).

**M5. Production's field-behaviour model (study 10 / R17, about 1.49M captured lineups).** Give it the consistent
shapes found here as features: cheap count, DST price, stacked QB, and salary used.

**Not recommended:** a regulars'-picks model (failed pre-test), late swap (closed), alternate ladders (closed).

## 4. This week and next

- **Week 5:** no new change. The whole-field result strengthens Saturday's cheap-block option, and study 53's frozen
  rule decides it. The defense price and game coverage are already right under the Week-5 settings.
- **Monday 10-12:** run `field_pattern_monitor.py` on W5's real field (its first prospective week). The laptop's weekly
  graph refresh is the natural place for it.
- **Week 6+ candidates:** the graded cheap block (M1) if it beats flat; a game-allocation rule (M2) if it beats the rank
  base rates. Each takes the usual path: preregistered test, operational proof, rollback, and the operator's decision.

## 5. Reproduction

All outputs are in `reports/2026-10-07-brainstorm/` (`*.txt`), produced by the scripts beside them on 2026-10-07
(BigQuery reads only; the `nfl-predictions` venv).

| Script | Output | Measures |
|---|---|---|
| `scripts/field_pattern_monitor.py` | `field_pattern_monitor_w1-4.txt` / `.csv` | weekly cheap-pattern odds ratios, whole-field rates, game coverage (tests: `tests/test_field_pattern_monitor.py`, 7 pass) |
| `field_within.py` | `field_within.txt` | within-user standardized differences (§1.1) |
| `cheap_mh.py` | — (superseded by the monitor; kept for the record) | the first odds-ratio run |
| `tail_calibration.py` | `tail_calibration.txt` | §1.2 |
| `cheap_where.py` | `cheap_where.txt` | §1.3 |
| `structure_screen.py`, `dst_value.py` | `structure_screen.txt`, `dst_value.txt` | §1.4 |
| `game_leverage.py`, `book_game_ranks.py` | `game_leverage.txt`, `book_game_ranks.txt` | §1.5 (the replay books are `~/rehearsals/outside-cblocks-20261007T153309Z/w{2,3,4}-*/book.csv`) |
| `news_and_games.py` (argument: production's `scripts/weekly_picks_vs_field.py`, sha256 `02e8d3432e73…`) | `news_and_games.txt` | §1.6, §1.7 |

Inputs: `~/moneygate/weeks.json` (the T-70 runs), `nfl_raw.contest_entries` / `contest_ownership` (the largest
Millionaire per week), `nfl_raw.schedules`, `nfl_features.player_week_actuals` / `player_week_role`,
`nfl_raw.dk_salaries_historical`, `nfl_raw.prop_lines`.
