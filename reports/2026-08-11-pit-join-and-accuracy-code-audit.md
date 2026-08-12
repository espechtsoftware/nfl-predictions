# Point-in-time, join, and accuracy code audit

Date: 2026-08-11. Requested scope: bad joins, features that would not be
available in a live week, and anything that reduces accuracy.

**No code was changed.** All findings are static code/SQL audits plus
outcome-free warehouse counts.

---

## What is clean (verified, not assumed)

Worth stating first, because the fragile parts of this system are not where I
expected them.

- **Training and inference compute the same features.** Diffing the column
  expressions of `021_player_week_training.sql` against
  `023_player_week_inference.sql` yields only three differences, all correct:
  `u.was_active`, `a.pass_attempts AS y_pass_attempts`, and
  `a.interceptions AS y_interceptions` — labels and provenance, not features.
  The join lists are otherwise identical table-for-table.
- **Every window frame in the model path ends at `1 PRECEDING`.** The only
  frames including `CURRENT ROW` are in `022_defense_points_against.sql`, which
  documents itself as a rear-view UI table ("never a model input") and is
  consumed only by `app/main.py`, `app/store.py` and `app/chat.py`. Correct
  as written; keep the comment.
- **All *active* model features have a live path.** Each source table either
  carries an explicit upcoming-week spine or is as-of joined in inference:

| source | mechanism | feeds (active) |
|---|---|---|
| `player_week_efficiency` | `UNION ALL` synthetic upcoming rows from `player_week_role` | `dk_points_l4/_std/_vol` |
| `player_week_advanced` | driven by the `player_week_usage` spine | `ez_targets_l4`, `deep_targets_l4`, `separation_l4`, `stacked_box_l4` |
| `qb_week_ngs` | appends a live QB target row | `qb_cpoe_l6` |
| `team_week_neutral_pass` | upcoming spine | `neutral_pass_rate_l6` |
| `team_week_context` | schedule-driven | pace/PROE context |
| `defense_week_allowed` | `def_asof` in inference | `cb_*`, `db_*`, `top_cb_out` |
| `player_week_xfp` | `xfp_asof` in inference | `xfp_l4` (candidate) |

The `xfp_asof` comment shows the bug class was recognised and fixed once. The
findings below are the places the same sweep did not reach.

---

## Finding 1 — four candidate features would be NULL on every live slate

**Severity: no production impact today; a live trap the moment any of them is
promoted — including one I recommended testing.**

These tables are built purely from post-game sources, have **no upcoming-week
spine**, and are joined **exact-week** in `023_player_week_inference.sql`:

| table | built from | feeds | live behaviour |
|---|---|---|---|
| `team_week_pace` | `pbp` only | `pace_env_l6` | NULL |
| `defense_week_blitz` | `ftn_charting` + `pbp` | `opp_blitz_rate_l6` | NULL |
| `team_week_target_concentration` | `weekly_stats` | **`team_top2_target_share_l6`** | NULL |
| `team_week_ftn_offense` | `ftn_charting` + `pbp` | `pa_rate_l6`, `opp_pressure_rate_l6` | NULL |

For an upcoming week W no game has been played, so no row exists at
`(team, season, W)`, and `LEFT JOIN ... AND pc.week = u.week` returns NULL.
Replays, which run on completed weeks, see real values. That is exactly the
train/serve skew the `xfp_asof` audit fixed — an arm would look fine
historically and then serve nulls on Sunday.

None of the four is in `NUMERIC_FEATURES`, so nothing is broken in production
right now. But `team_top2_target_share_l6` is the feature I recommended testing
as the team-concentration input, and it is in this set. **Any promotion of these
must be preceded by either an upcoming spine (the `qb_week_ngs` pattern) or an
as-of join (the `xfp_asof` pattern).**

Recommended check to make this class impossible to reintroduce: assert, for the
current season's maximum scheduled week, that every table joined by
`player_week_inference` returns a non-null row for the spine's upcoming rows.
That is a single query and it would have caught all four.

## Finding 2 — leakage checks cover 7 of 54 features

**Severity: process gap, not a known defect.**

`CHECKED_FEATURES` covers `target_share_l4`, `rz20_targets_l4`,
`carry_share_l4`, `target_share_std`; `COVERAGE_CHECKS` adds
`cb_ypt_allowed_l6`, `cb_comp_rate_allowed_l6`, `db_ypt_allowed_l6`. Seven
total, against 35 active plus 19 candidate features.

Many of the uncovered ones cannot leak by construction — `is_home`, `is_dome`,
`spread`, `game_total`, `salary`, `net_rest_diff`, `body_clock_hour` are all
pre-game facts. But roughly sixteen genuinely rolling features have no
automated check, including `dk_points_l4/_std/_vol`, `separation_l4`,
`snap_share_l4`, `wopr_l4`, `deep_targets_l4`, `ez_targets_l4`,
`stacked_box_l4`, `gl3_carries_smoothed`, `rz20_targets_smoothed`,
`neutral_pass_rate_l6`, `qb_cpoe_l6`, and both `team_vacated_*` columns.

The checker is generic — `assert_no_leakage(built, source, feature_col,
source_col, window)` — so extending coverage is mostly a matter of adding rows
to the list and naming each feature's source grain. Given that "point-in-time
is sacred" is the project's first rule and `build-features` already runs these
on every build, the marginal cost is low and the coverage gap is the largest
process risk in the audit.

## Finding 3 — `team_cpoe` is computed and thrown away

**Severity: low effort, and it corroborates a standing recommendation.**

`015_player_week_efficiency.sql:34-41` defines:

```sql
qb_quality AS (
  -- CPOE of the team's primary passer, trailing; a receiver feature.
  SELECT posteam AS team, season, week, AVG(cpoe) AS team_cpoe
  FROM `${raw}.pbp` WHERE qb_dropback = 1 AND cpoe IS NOT NULL
  GROUP BY 1, 2, 3
),
```

`team_cpoe` appears nowhere in the final `SELECT`, in
`021_player_week_training.sql`, in `023_player_week_inference.sql`, or in
`featureset.py`. The CTE is evaluated and discarded.

This independently confirms the correlation gap flagged earlier: **QB quality
does not reach pass-catchers.** `qb_cpoe_l6` is populated on 0.0% of RB/WR/TE
rows by design (`017h_qb_ngs.sql` filters `ro.position = 'QB'`). Someone
started the receiver-side version — the comment says "a receiver feature" — and
never wired it up. The plumbing is half-built, which lowers the cost of the
recommendation.

Note it needs the strictly-prior treatment before use: as written the CTE is a
same-week aggregate, so it must be given a trailing window ending at
`1 PRECEDING` and an upcoming spine, exactly like `qb_week_ngs`.

## Finding 4 — `position` is taken from the end of the season in training

**Severity: low, but it is a genuine PIT violation and a skew.**

`014_player_week_usage.sql:7`, `017_defense_week_allowed.sql:31,47` and
`022_defense_points_against.sql:10` all use:

```sql
SELECT gsis_id, season, ANY_VALUE(position HAVING MAX week) AS position
FROM `${raw}.rosters_weekly` ... GROUP BY gsis_id, season
```

For a historical season this resolves to the player's **week-18** position and
attaches it to his week-3 row. `position` is a model feature
(`FEATURES = NUMERIC_FEATURES + ["position"]`), so future information enters
the model directly. It also creates skew: a live week can only know the
as-of position, so training rows are cleaner than anything production sees.

Measured incidence — player-seasons with more than one distinct roster position:

| season | player-seasons | with change | % |
|---|---:|---:|---:|
| 2019 | 3,112 | 42 | 1.35 |
| 2020 | 3,067 | 56 | 1.83 |
| 2021 | 2,960 | 25 | 0.84 |
| 2022 | 3,133 | 16 | 0.51 |
| 2023 | 3,089 | 31 | 1.00 |
| 2024 | 3,215 | 19 | 0.59 |
| 2025 | 3,134 | 24 | 0.77 |

So ~1% of player-seasons are affected. Small, and the affected players are
disproportionately the ambiguous FB/RB and TE/WR designations where the model
is least confident anyway. The fix is a strictly-prior `LAST_VALUE(... ROWS
BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)` with a first-week fallback to the
preseason roster. Worth doing on the next feature rebuild rather than urgently.

## Finding 5 — `qb_cpoe_l6` is present on 29.4% of QB rows

**Severity: accuracy consideration, not a defect.**

Coverage in `player_week_training`, 2022+:

| position | rows | % `qb_cpoe_l6` populated |
|---|---:|---:|
| QB | 7,171 | **29.4%** |
| RB / WR / TE | 45,136 | 0.0% |

NGS only publishes qualifying passers, and the training universe includes every
salary-listed backup, so a low rate is expected. Two consequences worth
recording:

- LightGBM handles NaN natively and splits on missingness, so this is benign
  there. **TabPFN's handling of a 70%-missing column is not obviously the
  same**, and `qb_cpoe_l6` is in `scripts/tabpfn_gen/features.txt`. Worth one
  check during the next cache regeneration: whether the imputation path used by
  the generator turns a 70%-missing column into a near-constant.
- A feature that passed a six-season panel while present on under a third of
  its own position's rows is either very strong where it exists or is partly
  proxying "is a qualifying starter." Both are worth knowing before extending
  it to receivers per Finding 3.

---

## Non-findings, checked and dismissed

- **`QUALIFY ROW_NUMBER() ... ORDER BY season DESC` on `draft_picks`**
  (`003_player_week_role.sql:133`) looks like a cross-season lookahead but is
  deduplication of an immutable attribute — a player's draft round does not
  change. Fine.
- **`def_asof` / `xfp_asof` "latest week" joins** are not skew: for a live week
  W the latest built row is W−1, whose window already ends at `1 PRECEDING`,
  which is the same information the exact-week row would carry.
- **Name-based joins.** The Fantasy Points importers resolve through the audited
  name/position/team → GSIS bridge with explicit unresolved/ambiguous reporting
  and hard failure on conflicts, and `017k_fantasy_points_route.sql` dedupes with
  `QUALIFY ROW_NUMBER()`. The route source additionally has its own
  `assert_route_source_strict_prior` check. This is handled better than most of
  the pipeline.

---

## Recommended order

1. **Finding 1** — add the upcoming-row assertion for every table joined by
   `player_week_inference`. One query, prevents a whole bug class, and it must
   land before `team_top2_target_share_l6` or any FTN candidate is promoted.
2. **Finding 2** — extend `CHECKED_FEATURES` to the ~16 uncovered rolling
   features. Mechanical, uses the existing generic checker, and closes the
   largest gap against the project's own first rule.
3. **Finding 3** — wire `team_cpoe` properly (trailing window + upcoming spine)
   as the QB-quality-to-receivers feature. This is the correlation gap already
   queued as `tabpfn-team-qb-quality`; the CTE existing means less new SQL.
4. **Finding 4** — strictly-prior `position` on the next feature rebuild.
5. **Finding 5** — one check on TabPFN's treatment of sparse columns during the
   next cache regeneration.

Nothing here invalidates a completed arm. Findings 1 and 4 would have made
some historical results look slightly better than live behaviour would deliver,
but Finding 1 affects only unused candidates and Finding 4 affects ~1% of rows.
