# Review of the Milly graph facts layer and the winner-likeness follow-ups (2026-10-07, 05:20 CT)

By the outside reviewing agent, against its own checklist in `reports/2026-10-06-neo4j-winner-likeness-inputs.md` §3.
Commits read: 736f2bb2 (the facts layer), 862de670 (`--facts-only`), 4d69912c (the reviewer's finding), dc875c8f (study
list 44 after the critique); `src/nfl_dfs/dashboard/milly_graph_facts.py` at integration `dc875c8f`.

## Done, and done the right way

- **A. Player-week facts:** `(:PlayerWeek)` with 62 `pre_` columns taken from the archived T−70 frame (every red-zone,
  goal-line, end-zone, volume, trend, vacated, efficiency, matchup, market, status, role, projection and price fact the
  frame holds), plus the six lagged facts the frame lacked (touchdowns and pass attempts over the prior 4 and 8 games,
  games played), plus 18 `out_` columns from the weekly actuals and play-by-play. Vendor columns opt-in. Exactly the plan.
- **B. Game and team facts:** Game `pre_total / pre_spread_home / pre_implied_home / pre_implied_away / pre_kickoff` and
  `out_home_pts / out_away_pts / out_total / out_top_game_rank`; TeamWeek implied total, favourite, pace, PROE, vacated
  shares. Done, with one omission below.
- **C. Lineup labels:** `lbl_qb_game_rank`, `lbl_qb_favourite`, `lbl_top_game_players`, `lbl_dual_stack`, `lbl_flex_pos`,
  `lbl_games`, `lbl_cheap_players`, `lbl_salary_left`, `lbl_qb_salary`, `lbl_te_salary`, `lbl_dst_salary`, `lbl_own`
  (pre-lock), with the stack facts already on the base Lineup; outcome tiers `out_tier_winner / within10 / top100 /
  top1pct / top01pct`. These are the attributes the winners' study used; the environment ones are the ones that mattered.
- **F. Provenance and the guard:** `pre_source` (run id + sha), `pre_as_of`, `out_source`; `assert_point_in_time` refuses
  any outcome name under `pre_` and any realized fact under `lbl_`; the reviewer caught realized ownership under a
  pre-lock label and moved it to `out_own_*_realized`. This is the discipline the plan asked for.

## Not yet in the graph (from the same checklist)

- **D. Our rows and the candidate pool.** Our entered rows are present only through the users file; the union's pool
  (the thousands of rows we could have entered) is not. Without it the graph cannot answer the question that matters
  most for a selector: among OUR candidates, which looked like winners. Load each week's pool rows as Lineups with
  `source = 'pool'` and the same `lbl_` labels (no `out_tier`; score them by finish against the field instead).
- **E. The user side.** No cohort flag on `(:User)` and no entries-per-week; the per-player past top-1% frequency is
  derivable in Cypher from `out_tier_top1pct` across prior weeks but is not materialised as a `pre_` fact for the next
  week (it is the one player-level input with any support: `reports/2026-10-07-winners-strategy-study.md` §5).
- **The anytime-touchdown probability** from `nfl_raw.prop_lines` (the last pre-lock snapshot), the market's price on
  this week's touchdown; `market_points` (the props-implied mean) is loaded, the tail price is not.
- **TeamWeek `pre_starters_out`** from the 10:30 inactives (the early-game information the regulars act on).

## On the follow-ups (studies 48–48f)

- The laptop's whole-field check answers the critique's first point directly: the frozen score separates the field's
  bottom from its top (AUC .55–.59) and does nothing within the top 20% by projection, where our candidates live (AUC
  .49 / .54 / .39, and in Week 4 the most winner-like fifth was the worst). A score that only tells bad lineups from
  good ones adds nothing to a builder that never makes bad ones.
- **48f (the real-field refit) is the right next test.** Three suggestions for its design: (1) train on the top 1% against
  the top-20%-by-projection band, not against the whole field, so the model learns the distinction that exists among
  candidates; (2) keep the structure + environment model and the full model side by side, and expect the full model to
  add nothing (the attribution's result); (3) grade it weekly by the monkeys test, the model's top 26 of our pool
  against random 26s on the real field, which is the use it would have. The graph now holds everything (1)–(3) need
  except the pool rows (item D above).
