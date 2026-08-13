# SIS warehouse and join audit

Date: 2026-08-13. Audit of `nfl_raw.sis_team_context_game`,
`nfl_raw.sis_team_run_context_game`, and how they are consumed.
**No code was changed.** All checks are outcome-free structural queries.

---

## Verified clean

This is the cleanest data intake in the project. Every integrity check passed.

**Row counts are exactly right, including the one that looks wrong.**

| season | rows | weeks | expected |
|---|---:|---:|---|
| 2019 | 512 | 17 | 32 × 16 ✓ |
| 2021 | 544 | 18 | 32 × 17 ✓ |
| **2022** | **542** | 18 | **correct** — the cancelled Bills–Bengals game leaves two teams at 16 |
| 2023–2025 | 544 each | 18 | ✓ |

2020 is absent, matching the six-season replay panel. Both tables have identical
counts.

**Keys and joins.**

| check | result |
|---|---|
| duplicate `(season, week, team)` keys | **0** in both tables |
| NULL `team` / `opp` / `game_key` | **0** in every season |
| non-reciprocal rows (A vs B without B vs A) | **0** |
| game-set mismatch between the two tables | **0** |
| distinct `team` / `opp` values | 32 / 32 |
| **rows joining `schedule_long` on (season, week, team)** | **3,230 / 3,230** |
| **…with `opponent` also matching** | **3,230 / 3,230** |
| SIS teams absent from the schedule | none |

A perfect opponent-validated join across every row. This is the failure mode
that broke the Fantasy Points matchup exports and cost the LineStar DST work
real time; it does not exist here.

**Metric completeness.** Zero NULLs in every column checked — `block_snaps`,
`pass_block_blown_blocks`, `block_points_earned_per_play`, `pdef_epa_per_play`,
`prush_pressures`, `rdef_points_saved_per_play`, `rdef_attempts`,
`rush_points_earned_per_play`, `rush_boom_rate`, `pass_dropbacks` — across all
six seasons. Both `source_sha256_*_value` provenance columns are fully
populated, so no Totals-without-Value partial join exists.

**Lag construction is correct**, and better than I expected:

- `groupby(["season","team"]).shift(1).rolling(4, min_periods=2)` — strictly
  prior, current row excluded.
- The window is over **team games, not calendar weeks**, so byes are handled
  correctly by construction.
- **Rates are reconstructed from lagged numerators and denominators**, not
  averaged from weekly rates. That is the right method — averaging weekly rates
  over-weights low-volume games — and it matches what `017l_team_qb_quality.sql`
  does with `SUM(cpoe_sum)/SUM(cpoe_dropbacks)`.
- `sis_run_source_week_end` persists the source week for leakage audit.

**Operational coverage.** `ops/backup.py` includes `("raw", "sis_")` in
`DISCOVER_PREFIXES`, so both tables are picked up automatically. `leakage.py`
carries substantial SIS-specific checking.

---

## Issues

### 1. Feature coverage was never reported for either SIS arm

Every Fantasy Points arm reported feature coverage and gated on it:

| arm | reported coverage | gate |
|---|---|---|
| FP coverage-fit | 28.83% / 29.14% | passed a 25% floor |
| FP same-season coverage | 21.79 / 22.74 / 21.79% | **failed** a 30% floor |
| FP QB shell | 99.3–100% | passed a 70% floor |

**Neither the SIS QB-line nor the SIS RB run-defense result reports a coverage
figure or a support gate at all.**

This matters because the support rule is `prior_games >= 2` inside a
`(season, team)` group. That structurally leaves **weeks 1 and 2 of every season
unsupported** — 2 of 18 weeks, roughly **11% of the evaluation panel**, by
construction rather than by data gap.

For arms whose conclusion is "no effect," an unreported 11% structural
missingness is a material omission: it is a plausible partial explanation for a
null, and it should have been stated alongside the Brier deltas. The handling
may well be correct — median imputation on the training fold is the standard
treatment and is used elsewhere — but it is not documented in either result.

**Recommended:** add coverage reporting to the SIS result documents
retrospectively (it is a query, not a rerun), and make a support figure a
mandatory reported field for any future SIS arm, matching the Fantasy Points
convention.

### 2. Season-boundary handling is now inconsistent across the codebase

| construct | grouping | Week 1 behaviour |
|---|---|---|
| SIS run/team context | `(season, team)` | **no value** — restarts each season |
| `017h_qb_ngs.sql` | `PARTITION BY gsis_id ORDER BY season, week` | **carries prior season** |
| `017l_team_qb_quality.sql` | `PARTITION BY team ORDER BY season, week` | **carries prior season** |
| `fp_route_share_*` | cross-season with an explicit indicator | carries, and flags it |

All four choices are defensible in isolation, but the codebase now does three
different things with no stated rationale in any of them. The route-share family
has the best pattern — carry the value *and* emit a `cross_season` indicator so
the model can learn the difference.

**Recommended:** one comment line in each file stating the choice and why. This
is cheap and it prevents a future session from "fixing" one to match another.

### 3. The two table names actively mislead

The split is by acquisition tranche, not by football concept:

- **`sis_team_context_game`** holds **pass defense**, **pass rush** and
  **blocking** — i.e. defense and line.
- **`sis_team_run_context_game`** holds **team passing offense**
  (`pass_dropbacks`, `pass_attempts`, `pass_air_yards`, `pass_pressures`),
  **rushing offense**, and **run defense**.

So the *passing offense* columns live in the table named "run context," and the
*pass defense* columns live in the one named "team context." A future consumer
looking for team pass-offense metrics will naturally query
`sis_team_context_game`, find `pdef_*` and `prush_*`, and reasonably conclude
the data is not there.

This is not a correctness defect today — the analysis modules reference the
right tables — but it is a live trap. **Recommended:** either rename to reflect
content (`sis_team_defense_line_game` / `sis_team_offense_rundef_game`) or add
an explicit table-to-content map in the intake report and in each ingest
module's docstring. Renaming a raw table has provenance cost, so the documented
map is probably the right call.

### 4. There is no production path for SIS features

SIS has no `sql/features/*.sql` and no `nfl_features.sis_*` table. It is
consumed directly by `analysis/` modules for diagnostics.

That is entirely appropriate for the diagnostic stage. But it means SIS features
bypass `build-features` and its leakage-check invocation, and there is currently
**no route by which a passing SIS arm could reach production.** Every other
source family — nflverse, NGS, FTN, PFR, Fantasy Points route share — goes
through the feature SQL layer, `player_week_training` / `player_week_inference`,
and the upcoming-row spine.

No SIS arm has passed, so nothing is blocked. But if one ever does, the work to
productionise it is larger than it looks, and it should include the
upcoming-week spine requirement from the earlier PIT audit — SIS is built from
completed games only, so an exact-week join would return NULL on every live
slate. That is exactly the class the `xfp_asof` audit fixed.

**Recommended:** note this as a known prerequisite in the SIS acquisition plan
so that a passing arm is not mistaken for a shippable one.

---

## Summary

Nothing here is broken. Row counts, keys, reciprocity, NULLs, and the
schedule-validated opponent join are all clean, and the lag construction is
correct in the two places that usually go wrong — team-games rather than
calendar weeks, and rates rebuilt from lagged numerators and denominators.

The four items above are a reporting omission (coverage), an undocumented
inconsistency (season boundaries), a naming trap (table contents), and a missing
downstream path (productionisation). The first is the only one that affects how
a completed result should be read.
