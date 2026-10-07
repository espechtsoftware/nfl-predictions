# The winner-likeness check (study list 44): what the Milly graph holds, and the per-player facts it needs (2026-10-06, 21:30 CT)

By the outside reviewing agent, at the operator's request: "make sure that all the inputs for Neo4j … has all the data
points that could help it look like a winner … for each player selected in a lineup, what their red zone … attempts
are, the number of touchdowns, the number of attempts, things like that; if it's not there that should be part of
the plan."

## 1. What the graph holds today (`src/nfl_dfs/dashboard/milly_graph.py`, loader `scripts/load_milly_neo4j.py`)

Week; Contest (entries, winning score, top-1% / top-0.1% / cash lines); Game (home, away only); Team; Player (DK id,
name, position, team); Lineup (rank, points, dupes, stack label, stack size, bring-back, salary, ownership sum,
top-1% flags, source); User → Lineup; Lineup → Player (slot); Player → Contest (realized ownership, that week's DK
points); Player ↔ Player same-game pair counts; and, opt-in, Player → Week (FP projection, FP ownership).

**No per-player football facts** of any kind: no red-zone targets or carries, no goal-line carries, no touchdowns,
no targets, carries or attempts, no snap or route shares, no injury or depth status, no projections other than
FP's; and the Game nodes carry no total, spread, kickoff window or final score. The graph can say *which* players
the winners used and how they were shaped; it cannot say *what those players looked like before lock*.

The plan in study-list item 44 scores a lineup on shape, stack size and bring-back, salary used, ownership sum and
the players' past top-1% frequency. Those are lineup facts and field facts. The operator's intent, player facts, is
not in the plan yet. It should be.

## 2. The facts already exist in the warehouse, point-in-time

The T−70 frame the build consumes (archived per week, e.g. `~/moneygate/inputs/runs/<run>/frame.parquet`, 141
columns) already carries, for every slate player, exactly the lagged facts the operator names, as the build saw
them before lock:

- **Red zone and goal line:** `rz20_targets_l4`, `rz10_targets_l4`, `rz20_target_share_l4`, `rz10_target_share_l4`,
  `rz20_targets_smoothed`, `ez_targets_l4`, `gl3_carries_l4`, `gl3_carry_share_l4`, `gl3_carries_smoothed`,
  `rz_td_rate_allowed_l6` (the opponent).
- **Volume:** `targets_l4`, `target_share_l4`, `carries_l4`, `carry_share_l4`, `snap_share_l4`, `deep_targets_l4`,
  `air_yards_share_l4`, `wopr_l4`, the `_last` / `_jump` / `_trend` / `_std` forms, `team_vacated_target_share`,
  `team_vacated_carry_share`, `fp_route_share_last` / `_l4` / `_jump` (Fantasy Points), `xfp_l4`.
- **Efficiency and matchup:** `yards_per_target_l8`, `yards_per_reception_l8`, `yards_per_carry_l8`,
  `yards_per_attempt_l8`, `qb_cpoe_l6`, `qb/rb/wr/te_fp_allowed_adj_l6`, `team_top2_target_share_l6`.
- **Market and environment:** `total_line`, `spread_line`, `game_total`, `implied_team_total`, `pace_l4`,
  `proe_l4`, `pace_env_l6`, `market_points` (the props-implied projection).
- **Status and role:** `status` (DK), `injury_status`, `practice_level`, `practice_participation_trend`,
  `depth_rank`, `depth_rank_delta`, `report_status`, `practice_status`, `roster_status`.
- **Projection:** `mean_projection` / `proj` (ours), `dk_ppg`; FP is in the graph already.

The same-week **outcomes** exist too, from nflverse weekly stats and play-by-play (`sql/features/015a_player_week_advanced.sql`,
`011_rz_rushing.sql`, `sql/raw/001_pbp.sql`): targets, receptions, receiving yards and TDs, carries, rushing yards
and TDs, pass attempts, passing yards and TDs, interceptions, red-zone targets and carries, goal-line carries,
end-zone targets, snaps and routes.

## 3. What to add to the plan (the loader, one new batch each; sized for a local instance)

**A. A player-week fact layer.** `(:Player)-[:IN_WEEK {…}]->(:Week)` (or a `:PlayerWeek` node), with every property
tagged by group so a query can never mix them:
- `pre.*` — the pre-lock facts above, taken from the **archived T−70 frame of that week** (what the build saw) when
  one exists, else the feature tables as of the Saturday build; plus salary, the props-implied projection and the
  anytime-TD probability from `prop_lines`, and FP's projection and ownership (fold the existing `FP_PROJECTED` in).
  Add two lagged facts the frame lacks: touchdowns over the last 4 and 8 games (rush, receiving, passing) and QB
  pass attempts over the last 4, from the weekly stats.
- `out.*` — that week's outcomes: DK points (already on `OWNED_IN`), targets, receptions, receiving yards and TDs,
  carries, rushing yards and TDs, attempts, passing yards and TDs, interceptions, red-zone targets and carries,
  goal-line carries, end-zone targets, snaps, routes, the 100-yard bonuses, realized ownership.

**B. Game and team facts.** Game: `pre.total`, `pre.spread`, `pre.implied_home`, `pre.implied_away`, `pre.kickoff`
(early / late / night), `pre.weather` if captured; `out.home_pts`, `out.away_pts`, `out.total`, `out.plays`,
`out.pass_attempts`, `out.top_game_rank` (the slate's scoring rank). Team-week: `pre.implied_total`, `pre.favourite`,
`pre.pace_l4`, `pre.proe_l4`, `pre.starters_out` (from the inactives), `pre.vacated_target_share`,
`pre.vacated_carry_share`.

**C. Lineup labels precomputed** (so "looks like a winner" is a property query, not a nine-join Cypher): the shape
attributes used in `reports/2026-10-07-winners-strategy-study.md` (teammates, bring-backs, dual stack, games,
flex position, QB's game-total rank, favourite/underdog, players from the top-total game, cheap-player count,
salary left, QB price tier, TE and DST price) and pre-lock ownership facts (sum, max, count under 5%), plus the
outcome tiers (winner, within 10, top 100, top 1%, top 0.1%, cashed).

**D. Our side.** Our book rows per week (cell / shape, dealt contests, projected sum, realized points, the field
copies) and the union's candidate pool, loaded as Lineups with `source = 'ours'` / `'pool'`, so the same questions
can be asked of what we built and what we could have built.

**E. Users.** The cohort flag (regular / not), entries per week, and per player the past top-1% frequency relative
to ownership (the plan's "players' past top-1% frequency" is a per-player lift: appearances in prior weeks' top 1%
divided by prior ownership).

**F. Provenance on every pre-lock property**: the source (frame run id or table) and its as-of time. The loader
should refuse to write a same-week outcome under a `pre.` name. This is what makes the winner-likeness score
auditable as point-in-time, which item 44 rightly requires before any use.

Sizing: four weeks × ~450 slate players × ~80 properties is a few hundred thousand property values; the full
fields (~1.5M lineups, ~14M CONTAINS edges) were the 10-04 plan's own scope and fit the local instance.

## 4. Two cautions, and one thing the graph cannot do

- Lagged facts (last 4 weeks' red-zone targets) are pre-lock and may enter a winner-likeness score. The same week's
  red-zone targets and touchdowns are outcomes: they explain *why* a lineup won and must never enter the score.
  The property groups above exist to keep that line visible in every query.
- The score's test is already the right one (item 44: does a higher score predict a better finish than a lineup of
  equal projection, on real fields, preregistered). With player facts added, the same test applies; the richer the
  inputs, the easier it is to fit the four weeks we have, so the walk-forward read matters more, not less.
- The graph is for looking (the plan says so). The facts above are the same columns the projection model and the
  features SQL already use; if a player fact predicts top-1% membership beyond projection, the place it pays is the
  projection or the builder, and the graph is where that is first seen.
