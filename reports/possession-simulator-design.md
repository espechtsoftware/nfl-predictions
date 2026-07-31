# Possession-level game simulator — design doc

Issue #13 item 6 (flagship). Status: **core engine landed, offline-tested,
env-gated off**. Not yet wired to replace the production game factor —
that requires fitting real transition probabilities from `nfl_raw.pbp`,
which needs BigQuery access this worker doesn't have. This doc records the
design so the next session (with GCP creds) can finish the integration.

## Why

`models/simulate.py` currently correlates players within a game with a
single shared lognormal multiplier (`GAME_FACTOR_SIGMA`) applied to every
player's opportunity counts. It's mean-preserving and cheap, and it's why
shootout lineups price correctly at all (Addendum on correlated sim,
README §6.2) — but it's one dial. It can't produce:

- **Game script correlation with DST**: a team leading big should run
  more / pass less, and the trailing team's garbage-time volume should
  show up as a distinct DST/RB or WR skew, not just "both teams randomly
  scaled up or down together."
- **Emergent joint tails**: the current factor makes shootouts likely by
  construction (both teams scaled up together); it can't produce a
  one-sided blowout boosting one team's pass volume while suppressing the
  other's, which is a distinct and common source of Milly-winning stacks
  (Addendum 4/5/6 in `2026-07-25-system-study.md`).
- **Possession-count variance**: two 11-drive games and one team getting
  14 possessions to the other's 9 (garbage time, short fields off
  turnovers) changes usage independent of any scoring-rate factor.

A drive-state Markov simulator generates score and possession-count
variance from first principles (how drives actually end) instead of
imposing a distributional shape on top of point projections.

## State space (drives, not plays)

Full play-by-play state (yardline x down x distance x personnel) is the
"eventually" version of this model but isn't needed for DFS-relevant
outputs (team points, possession count, pace, red zone trips). The v1
engine models **drives** as the unit, with a small discrete state space:

- `start_zone`: `deep_own` (own 1-10), `own` (11-40), `midfield` (41-59),
  `fringe` (60-79, opp side), `redzone` (80-99, i.e. opp 1-20). Yardline
  expressed 1-99 from the simulating team's own end zone.
- Terminal outcomes per drive: `td`, `fg_make`, `fg_miss`, `punt`,
  `turnover`, `turnover_on_downs`, `safety`, `end_of_half`.

This keeps the transition table small enough to fit from a few seasons
of `nfl_raw.pbp` (~15 rows: start_zone -> terminal outcome probabilities,
plus a start-zone transition for the *next* drive conditioned on how the
previous one ended — a turnover in `redzone` starts the opponent's next
drive in `redzone` from the other side, a punt starts it around
`own`/`midfield` depending on punt distance, etc). That fit is future
work requiring BigQuery (see "Next steps").

## What ships in this increment (offline, no GCP)

`src/nfl_dfs/models/game_sim.py`:

- `DEFAULT_TRANSITIONS`: a hardcoded starting transition table (terminal
  outcome probabilities per start zone, next-drive start-zone
  distribution per terminal outcome), calibrated to roughly plausible
  NFL aggregates (~11-12 drives/team/game, ~2.0-2.2 points/drive) purely
  so the engine is runnable and testable without pbp data. **Placeholder,
  not fit from real plays** — flagged in the docstring and in the
  deficiency log below.
- `simulate_drives(...)`: draws a sequence of terminal outcomes and
  next-drive start zones for one team across a game, bounded to avoid
  runaway loops.
- `simulate_game_points(...)`: alternates possessions between two teams
  for `n_sims` draws, returns per-team total points per sim — this is
  the analog of today's lognormal `game_mult`, but derived from summed
  discrete drive outcomes instead of a smooth multiplicative factor.
- `game_environment_factor(...)`: converts `simulate_game_points` output
  into a mean-preserving multiplier per team per sim (team points / that
  team's expected points), shaped so it can be substituted for the
  `game_mult` array in `simulate.simulate()`.
- `allocate_drive_usage(...)`: Dirichlet-draw split of a drive's plays
  across a team's players given prior usage shares (`target_share_l4`,
  `carry_share_l4` — the columns `models/featureset.py` already carries).
  This is the "usage draws" piece flagged in Addendum 22 as a candidate
  consumer of `market_ceilings()` and team usage features.

All of it is pure numpy/pandas, seeded, and covered by
`tests/test_game_sim.py` — no BigQuery, no network.

## Env gate

`GAME_SIM_MODE` (default unset / `"lognormal"`): current behavior,
unchanged. `GAME_SIM_MODE=possession` switches `models/simulate.py` to
build `game_mult` from `game_environment_factor()` instead of the
lognormal draw. Off by default — this is a placeholder-calibrated engine,
not something to run in production until it's validated.

## Next steps (need GCP + Cloud Run; NOT done by this worker)

1. Fit `DEFAULT_TRANSITIONS` for real from `nfl_raw.pbp`: group plays by
   drive (`drive` column), bucket start yardline into the four zones,
   read off `fixed_drive_result` as the terminal outcome, and the next
   drive's start yardline as the next-drive start zone. Write as a new
   `sql/features/` transform or a one-off notebook query — this is a
   fitting step, not a point-in-time feature, so it doesn't need to go
   through the leakage-checked feature pipeline; it's closer to
   `models/scoring.py`'s DK-rules constants than to a per-week feature.
2. Wire `GAME_SIM_MODE=possession` into `backtest/replay.py` behind the
   same kind of A/B flag as `N_DARKGAME`/`ALT_CEIL`, and run
   `nfl-dfs replay --season 2025` with it on vs. off.
3. Validate against the current baseline (correlated lognormal sim + all
   adopted A/Bs): mean best-of-40 184.2, 6/17 weeks >= the min Milly
   line (194), median finish 12.3% (`Addendum 21`). Adopt only if the
   possession sim matches or beats that on 2025 replay — this is a
   structural change to every simulated draw, so hold it to the same bar
   as the A/B tests that came before it, not a lower one just because
   it's more "realistic."
4. If adopted, `allocate_drive_usage` becomes the place to fold in
   `market_ceilings()` (Addendum 22) as a per-player ceiling nudge on top
   of the Dirichlet draw, and to fold in the DK pricing-lag residual
   (issue #13 item 3, already landed) as a usage-share adjustment for
   players whose salary lags their trailing production.
