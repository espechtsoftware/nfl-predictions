"""Point-in-time leakage assertions.

The #1 way DFS backtests lie is a rolling feature that includes the current
week. These checks recompute key rolling features from the source tables
using strictly-prior weeks and assert they match what the build produced.
Any mismatch means a window definition regressed — fail the build.

`trailing_mean_excluding_current` is the pure-pandas reference
implementation; it is unit-tested on synthetic data and reused by the
SQL-vs-reference comparison.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)


class LeakageError(AssertionError):
    """A feature saw data from its own week or later."""


def assert_salary_universe_reconciled(gaps: pd.DataFrame) -> None:
    """Every played, salary-listed skill player must reach training.

    This is a universe/provenance invariant rather than a temporal leakage
    check, but it belongs in the same mandatory post-build gate: silently
    dropping a selectable player makes a replay just as misleading as seeing
    future data.
    """
    if not gaps.empty:
        cols = [c for c in (
            "gsis_id", "display_name", "season", "week", "position", "team",
            "salary",
        ) if c in gaps.columns]
        sample = gaps[cols].head(25).to_string(index=False)
        raise LeakageError(
            f"{len(gaps)} played salary-universe rows are absent from "
            f"player_week_training. Sample:\n{sample}"
        )


def assert_historical_salary_source_reconciled(gaps: pd.DataFrame) -> None:
    """Every schedule- and roster-valid historical row reaches the spine.

    The downstream universe check cannot detect a player dropped before
    ``dk_salary_week``. Independently rebuild source identity through the
    weekly roster; a valid row absent from the salary spine is an unexplained
    identity/source loss and must stop the build.
    """
    if not gaps.empty:
        cols = [c for c in (
            "gsis_id", "display_name", "season", "week", "position", "team",
            "opponent", "salary", "source_dk_points",
        ) if c in gaps.columns]
        sample = gaps[cols].head(25).to_string(index=False)
        raise LeakageError(
            f"{len(gaps)} schedule- and roster-valid historical salary "
            f"rows are absent from dk_salary_week. Sample:\n{sample}"
        )


def assert_dst_actual_universe_reconciled(gaps: pd.DataFrame) -> None:
    """Every completed regular-season team-game has a canonical DST label."""
    if not gaps.empty:
        cols = [c for c in ("season", "week", "team") if c in gaps.columns]
        sample = gaps[cols].head(25).to_string(index=False)
        raise LeakageError(
            f"{len(gaps)} completed schedule team-weeks are absent from "
            f"team_defense_week. Sample:\n{sample}"
        )


def assert_upcoming_context_rows_reconciled(gaps: pd.DataFrame) -> None:
    """Every post-game-only candidate table must emit its live target row."""
    if not gaps.empty:
        cols = [c for c in (
            "source_table", "season", "week", "team",
        ) if c in gaps.columns]
        sample = gaps[cols].head(25).to_string(index=False)
        raise LeakageError(
            f"{len(gaps)} upcoming team-context rows are absent. Exact-week "
            f"inference would serve candidate features as NULL. Sample:\n{sample}"
        )


def trailing_mean_excluding_current(
    df: pd.DataFrame,
    value_col: str,
    window: int | None = None,
    group_cols: tuple[str, ...] = ("gsis_id", "season"),
    order_col: str = "week",
) -> pd.Series:
    """Reference rolling mean over the trailing `window` rows (all prior rows
    when window is None), strictly excluding the current row. Mirrors the SQL
    `ROWS BETWEEN n PRECEDING AND 1 PRECEDING` window."""
    df = df.sort_values(list(group_cols) + [order_col])

    def _roll(s: pd.Series) -> pd.Series:
        shifted = s.shift(1)
        if window is None:
            return shifted.expanding().mean()
        return shifted.rolling(window, min_periods=1).mean()

    return df.groupby(list(group_cols), sort=False)[value_col].transform(_roll)


def trailing_std_excluding_current(
    df: pd.DataFrame,
    value_col: str,
    window: int | None = None,
    group_cols: tuple[str, ...] = ("gsis_id", "season"),
    order_col: str = "week",
) -> pd.Series:
    """Sample standard deviation over strictly-prior non-null rows.

    Pandas ``ddof=1`` matches BigQuery ``STDDEV``/``STDDEV_SAMP``: zero or
    one prior observation returns NULL, and a NULL observation occupies a row
    in a bounded ``ROWS`` frame without contributing to the statistic.
    """
    df = df.sort_values(list(group_cols) + [order_col])

    def _roll(s: pd.Series) -> pd.Series:
        shifted = s.shift(1)
        if window is None:
            return shifted.expanding().std(ddof=1)
        return shifted.rolling(window, min_periods=1).std(ddof=1)

    return df.groupby(list(group_cols), sort=False)[value_col].transform(_roll)


def assert_no_leakage(
    built: pd.DataFrame,
    source: pd.DataFrame,
    feature_col: str,
    source_col: str,
    window: int | None,
    atol: float = 1e-6,
    min_coverage: float = 0.95,
    key_col: str = "gsis_id",
    statistic: str = "mean",
    require_null_parity: bool = False,
) -> None:
    """Compare a built rolling feature against the reference recomputation.

    `built` needs [key_col, season, week, feature_col]; `source` needs
    [key_col, season, week, source_col] at per-game grain. key_col is
    gsis_id for player features, team for defense features.
    """
    ref = source[[key_col, "season", "week", source_col]].copy()
    reference = {
        "mean": trailing_mean_excluding_current,
        "std": trailing_std_excluding_current,
    }.get(statistic)
    if reference is None:
        raise ValueError(f"unsupported leakage reference statistic {statistic!r}")
    ref["expected"] = reference(
        ref, source_col, window=window, group_cols=(key_col, "season"))
    merged = built.merge(ref[[key_col, "season", "week", "expected"]],
                         on=[key_col, "season", "week"], how="inner")
    if merged.empty:
        raise LeakageError(f"No overlapping rows to check for {feature_col}")

    null_mismatch = merged[feature_col].isna().ne(merged["expected"].isna())
    if require_null_parity and null_mismatch.any():
        bad = merged[null_mismatch].head(5)[
            [key_col, "season", "week", feature_col, "expected"]]
        raise LeakageError(
            f"{feature_col}: {int(null_mismatch.sum())} rows disagree with "
            "the point-in-time reference on NULL support. This usually means "
            "the rolling spine or eligibility semantics drifted.\n"
            f"Examples:\n{bad.to_string(index=False)}"
        )

    both = merged.dropna(subset=[feature_col, "expected"])
    n_checked = len(both)
    if n_checked == 0:
        raise LeakageError(f"{feature_col}: no non-null rows to compare")
    mismatch = ~np.isclose(both[feature_col], both["expected"], atol=atol)
    rate = 1 - mismatch.mean()
    if rate < min_coverage:
        bad = both[mismatch].head(5)[[key_col, "season", "week", feature_col, "expected"]]
        raise LeakageError(
            f"{feature_col}: only {rate:.1%} of {n_checked} rows match the "
            f"point-in-time reference (need >= {min_coverage:.0%}). "
            f"A rolling window is probably including the current week.\n"
            f"Examples:\n{bad.to_string(index=False)}"
        )
    log.info("%s: %d rows checked, %.2f%% match", feature_col, n_checked, 100 * rate)


def assert_first_row_features_null(
    built: pd.DataFrame,
    feature_cols: list[str],
    group_cols: tuple[str, ...],
    order_col: str = "week",
) -> None:
    """The first row of every group has no prior data, so every strictly-prior
    rolling feature must be null there. A value means the window saw the
    current row. Grain-agnostic version of the player first-game check."""
    first = built.loc[built.groupby(list(group_cols))[order_col].idxmin()]
    for col in feature_cols:
        if col not in first.columns:
            continue
        leaked = first[first[col].notna()]
        if not leaked.empty:
            raise LeakageError(
                f"{col} is non-null on {len(leaked)} first-row groups of "
                f"{group_cols}; rolling window includes the current row."
            )


def assert_first_game_features_null(built: pd.DataFrame, feature_cols: list[str]) -> None:
    """A player's first tracked game has no prior data: every rolling feature
    must be null there. A value means the window saw the current week."""
    first = built[built["games_played_prior"] == 0]
    for col in feature_cols:
        if col not in first.columns:
            continue
        leaked = first[first[col].notna()]
        if not leaked.empty:
            raise LeakageError(
                f"{col} is non-null on {len(leaked)} first-game rows; "
                f"rolling window includes the current week."
            )


def assert_route_source_strict_prior(rows: pd.DataFrame) -> None:
    """Every attached licensed Route observation predates its target week."""
    needed = {
        "season", "week", "fp_route_source_season", "fp_route_source_week",
    }
    if missing := needed - set(rows.columns):
        raise LeakageError(f"Route source audit missing {sorted(missing)}")
    attached = rows.dropna(
        subset=["fp_route_source_season", "fp_route_source_week"]
    ).copy()
    source_order = (
        attached.fp_route_source_season.astype(int) * 100
        + attached.fp_route_source_week.astype(int)
    )
    target_order = attached.season.astype(int) * 100 + attached.week.astype(int)
    if source_order.ge(target_order).any():
        bad = attached.loc[source_order.ge(target_order)].head(25)
        raise LeakageError(
            "Fantasy Points Route Share contains same/future-week sources. "
            f"Sample:\n{bad.to_string(index=False)}"
        )


# SQL-side checks used in production against BigQuery ------------------------

CHECKED_FEATURES = [
    # (built feature col, source col, window)
    ("target_share_l4", "target_share", 4),
    ("rz20_targets_l4", "rz20_targets", 4),
    ("carry_share_l4", "carry_share", 4),
    ("target_share_std", "target_share", None),
]

SAMPLE_SQL = """
SELECT gsis_id, season, week, {cols}
FROM `{table}`
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0  -- deterministic 5% player sample
"""

# The reference must window over the same rows the build does: the historical
# DK salary universe. Active players without a receiving/rushing event receive
# a zero share; listed inactive players receive NULL. Recomputing from the
# activity tables alone would silently omit exactly the players this gate is
# intended to protect.
SOURCE_GRAIN_SQL = """
WITH snaps AS (
  SELECT i.gsis_id, CAST(n.season AS INT64) AS season,
         CAST(n.week AS INT64) AS week, n.offense_pct AS snap_share
  FROM `{raw}.snap_counts` n
  JOIN `{raw}.player_ids` i ON i.pfr_id = n.pfr_player_id
  WHERE i.gsis_id IS NOT NULL
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY i.gsis_id, CAST(n.season AS INT64), CAST(n.week AS INT64)
    ORDER BY n.offense_pct DESC
  ) = 1
)
SELECT sal.gsis_id, sal.season, sal.week,
       IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
          COALESCE(rec.rz20_targets, 0), NULL) AS rz20_targets,
       IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
          COALESCE(rec.target_share, 0), NULL) AS target_share,
       IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
          COALESCE(rush.carry_share, 0), NULL) AS carry_share
FROM `{features}.dk_salary_week` sal
LEFT JOIN `{features}.rz_receiving` rec
  ON rec.gsis_id = sal.gsis_id AND rec.season = sal.season
 AND rec.week = sal.week
 AND CASE rec.team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE rec.team END = sal.team
LEFT JOIN `{features}.rz_rushing` rush
  ON rush.gsis_id = sal.gsis_id AND rush.season = sal.season
 AND rush.week = sal.week
 AND CASE rush.team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                    WHEN 'STL' THEN 'LA' ELSE rush.team END = sal.team
LEFT JOIN `{features}.player_week_actuals` a
  ON a.gsis_id = sal.gsis_id AND a.season = sal.season AND a.week = sal.week
LEFT JOIN snaps sn
  ON sn.gsis_id = sal.gsis_id AND sn.season = sal.season AND sn.week = sal.week
WHERE sal.position IN ('QB', 'RB', 'WR', 'TE')
  AND MOD(FARM_FINGERPRINT(sal.gsis_id), 20) = 0
"""


# Independent source-family reconstruction of 015's active production trail.
# That transform excludes salary-listed inactive zero labels from rolling
# production, so the reference uses has_stat_line instead of treating every
# replay-retained zero as a played game.
EFFICIENCY_CHECKS = [
    # (built feature, source column, window, statistic)
    ("dk_points_l4", "dk_points", 4, "mean"),
    ("dk_points_std", "dk_points", None, "mean"),
    ("dk_points_vol", "dk_points", None, "std"),
]

EFFICIENCY_SAMPLE_SQL = """
SELECT gsis_id, season, week, {cols}
FROM `{features}.player_week_efficiency`
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0
"""

EFFICIENCY_SOURCE_SQL = """
SELECT gsis_id, season, week,
       IF(has_stat_line, dk_points, NULL) AS dk_points
FROM `{features}.player_week_actuals`
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0
"""


# Independent source reconstruction of 015a on its exact usage spine. Rows
# with no PBP/NGS observation must remain present and NULL because bounded SQL
# ROWS windows count calendar/player-spine rows, not only observed values.
ADVANCED_CHECKS = [
    ("ez_targets_l4", "ez_targets", 4),
    ("deep_targets_l4", "deep_targets", 4),
    ("separation_l4", "avg_separation", 4),
    ("stacked_box_l4", "stacked_box_pct", 4),
]

ADVANCED_SOURCE_SQL = """
WITH target_quality AS (
  SELECT receiver_player_id AS gsis_id, season, week,
         COUNTIF(air_yards >= yardline_100) AS ez_targets,
         COUNTIF(air_yards >= 20) AS deep_targets
  FROM `{raw}.pbp`
  WHERE pass_attempt = 1 AND receiver_player_id IS NOT NULL
    AND air_yards IS NOT NULL AND season_type = 'REG'
  GROUP BY 1, 2, 3
), ngs_rec AS (
  SELECT player_gsis_id AS gsis_id, season, week, avg_separation
  FROM `{raw}.ngs_receiving`
  WHERE week > 0
), ngs_rush AS (
  SELECT player_gsis_id AS gsis_id, season, week,
         percent_attempts_gte_eight_defenders AS stacked_box_pct
  FROM `{raw}.ngs_rushing`
  WHERE week > 0
)
SELECT u.gsis_id, u.season, u.week,
       t.ez_targets, t.deep_targets, nr.avg_separation, nu.stacked_box_pct
FROM `{features}.player_week_usage` u
LEFT JOIN target_quality t USING (gsis_id, season, week)
LEFT JOIN ngs_rec nr USING (gsis_id, season, week)
LEFT JOIN ngs_rush nu USING (gsis_id, season, week)
WHERE MOD(FARM_FINGERPRINT(u.gsis_id), 20) = 0
"""


UNIVERSE_GAP_SQL = """
SELECT s.gsis_id, s.display_name, s.season, s.week, s.position, s.team, s.salary
FROM `{features}.dk_salary_week` s
JOIN `{features}.schedule_long` g
  ON g.season = s.season AND g.week = s.week AND g.team = s.team
LEFT JOIN `{features}.player_week_training` t
  ON t.gsis_id = s.gsis_id AND t.season = s.season AND t.week = s.week
WHERE s.position IN ('QB', 'RB', 'WR', 'TE')
  AND DATE(g.gameday) < CURRENT_DATE()
  AND t.gsis_id IS NULL
ORDER BY s.season, s.week, s.position, s.salary DESC
"""


# Independent raw-source-to-spine contract for every historical source.
# raw.schedules avoids making identity validation depend on betting-line
# availability. This deliberately repeats the identity bridge: a regression
# in the transform must not redefine its own acceptance condition.
HISTORICAL_ROSTER_GAP_SQL = r"""
WITH norm_ids AS (
  SELECT DISTINCT gsis_id, UPPER(position) AS position,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(id_name)),
                       r'\s+(JR|SR|II|III|IV|V)\.?$', ''),
        r'[^A-Z ]', ''), r' +', ' ') AS clean_name
  FROM `{raw}.player_ids`, UNNEST([name, merge_name]) AS id_name
  WHERE gsis_id IS NOT NULL AND id_name IS NOT NULL
), norm_rosters AS (
  SELECT DISTINCT
    gsis_id, CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
    CASE UPPER(team)
      WHEN 'ARZ' THEN 'ARI' WHEN 'BLT' THEN 'BAL' WHEN 'CLV' THEN 'CLE'
      WHEN 'HST' THEN 'HOU' WHEN 'SL' THEN 'LA'
      WHEN 'GNB' THEN 'GB' WHEN 'KAN' THEN 'KC' WHEN 'JAC' THEN 'JAX'
      WHEN 'LAR' THEN 'LA' WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'NOR' THEN 'NO' WHEN 'NWE' THEN 'NE' WHEN 'SFO' THEN 'SF'
      WHEN 'TAM' THEN 'TB' WHEN 'SD' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
      WHEN 'STL' THEN 'LA' ELSE UPPER(team)
    END AS team,
    UPPER(position) AS position,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(roster_name)),
                       r'\s+(JR|SR|II|III|IV|V)\.?$', ''),
        r'[^A-Z ]', ''), r' +', ' ') AS clean_name
  FROM `{raw}.rosters_weekly`,
       UNNEST([full_name, CONCAT(football_name, ' ', last_name)]) AS roster_name
  WHERE gsis_id IS NOT NULL AND full_name IS NOT NULL
    AND roster_name IS NOT NULL AND game_type = 'REG'
), games AS (
  SELECT season, week,
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END AS team,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END AS opponent
  FROM `{raw}.schedules`
  WHERE game_type = 'REG'
  UNION ALL
  SELECT season, week,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END,
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END
  FROM `{raw}.schedules`
  WHERE game_type = 'REG'
), aliases AS (
  SELECT * FROM UNNEST([
    STRUCT('BISI JOHNSON' AS source_name, 'OLABISI JOHNSON' AS roster_name),
    ('CHIG OKONKWO', 'CHIGOZIEM OKONKWO'),
    ('ELI MITCHELL', 'ELIJAH MITCHELL'),
    ('HOLLYWOOD BROWN', 'MARQUISE BROWN'),
    ('KENNY GAINWELL', 'KENNETH GAINWELL'),
    ('MITCH TRUBISKY', 'MITCHELL TRUBISKY'),
    ('NICK WESTBROOK', 'NICK WESTBROOKIKHINE'),
    ('PHILLY BROWN', 'COREY BROWN'),
    ('PJ WALKER', 'PHILLIP WALKER'),
    ('ROBBIE ANDERSON', 'ROBBY ANDERSON'),
    ('RODNEY WILLIAMS', 'ROD WILLIAMS'),
    ('SHAQ DAVIS', 'SHAQUAN DAVIS'),
    ('TYRON BILLY JOHNSON', 'TYRON JOHNSON')
  ])
), source_base AS (
  SELECT
    CAST(season AS INT64) AS season, CAST(week AS INT64) AS week,
    display_name, UPPER(position) AS position,
    CASE UPPER(team_abbr)
      WHEN 'GNB' THEN 'GB' WHEN 'KAN' THEN 'KC' WHEN 'JAC' THEN 'JAX'
      WHEN 'LAR' THEN 'LA' WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'NOR' THEN 'NO' WHEN 'NWE' THEN 'NE' WHEN 'SFO' THEN 'SF'
      WHEN 'TAM' THEN 'TB' WHEN 'SD' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
      WHEN 'STL' THEN 'LA' ELSE UPPER(team_abbr)
    END AS team,
    CASE UPPER(opponent)
      WHEN 'GNB' THEN 'GB' WHEN 'KAN' THEN 'KC' WHEN 'JAC' THEN 'JAX'
      WHEN 'LAR' THEN 'LA' WHEN 'LVR' THEN 'LV' WHEN 'OAK' THEN 'LV'
      WHEN 'NOR' THEN 'NO' WHEN 'NWE' THEN 'NE' WHEN 'SFO' THEN 'SF'
      WHEN 'TAM' THEN 'TB' WHEN 'SD' THEN 'LAC' WHEN 'SDG' THEN 'LAC'
      WHEN 'STL' THEN 'LA' ELSE UPPER(opponent)
    END AS opponent,
    CAST(salary AS INT64) AS salary,
    CAST(dk_points AS FLOAT64) AS source_dk_points,
    REGEXP_REPLACE(
      REGEXP_REPLACE(
        REGEXP_REPLACE(UPPER(TRIM(display_name)),
                       r'\s+(JR|SR|II|III|IV|V)\.?$', ''),
        r'[^A-Z ]', ''), r' +', ' ') AS clean_name
  FROM `{raw}.dk_salaries_historical`
  WHERE salary > 0 AND UPPER(position) IN ('QB', 'RB', 'WR', 'TE')
), source AS (
  SELECT s.* REPLACE(COALESCE(a.roster_name, s.clean_name) AS clean_name)
  FROM source_base s
  LEFT JOIN aliases a ON a.source_name = s.clean_name
), valid AS (
  SELECT DISTINCT s.*
  FROM source s
  JOIN games g
   ON g.season = s.season AND g.week = s.week AND g.team = s.team
   AND (g.opponent = s.opponent
        OR (s.season = 2025 AND s.opponent IS NULL)
        OR (s.season = 2017 AND s.week = 11 AND s.opponent = '-'
            AND ((s.team = 'MIA' AND g.opponent = 'TB')
                 OR (s.team = 'TB' AND g.opponent = 'MIA'))))
), matched AS (
  SELECT v.*,
    COALESCE(
      IF(COUNT(DISTINCT IF(r.position = v.position, r.gsis_id, NULL)) = 1,
         MAX(IF(r.position = v.position, r.gsis_id, NULL)), NULL),
      IF(COUNT(DISTINCT r.gsis_id) = 1, MAX(r.gsis_id), NULL),
      IF(COUNT(DISTINCT IF(ir.position = v.position, ir.gsis_id, NULL)) = 1,
         MAX(IF(ir.position = v.position, ir.gsis_id, NULL)), NULL),
      IF(COUNT(DISTINCT ir.gsis_id) = 1, MAX(ir.gsis_id), NULL)
    ) AS gsis_id
  FROM valid v
  LEFT JOIN norm_rosters r
    ON r.season = v.season AND r.week = v.week
   AND r.team = v.team AND r.clean_name = v.clean_name
  LEFT JOIN norm_ids i ON i.clean_name = v.clean_name
  LEFT JOIN norm_rosters ir
    ON ir.season = v.season AND ir.week = v.week
   AND ir.team = v.team AND ir.gsis_id = i.gsis_id
  GROUP BY v.season, v.week, v.display_name, v.position, v.team,
           v.opponent, v.salary, v.source_dk_points, v.clean_name
), expected AS (
  SELECT DISTINCT gsis_id, season, week, display_name, position, team,
                  opponent, salary, source_dk_points
  FROM matched WHERE gsis_id IS NOT NULL
)
SELECT e.*
FROM expected e
LEFT JOIN `{features}.dk_salary_week` d
  ON d.gsis_id = e.gsis_id AND d.season = e.season AND d.week = e.week
 AND d.team = e.team AND UPPER(d.position) = e.position
WHERE d.gsis_id IS NULL
ORDER BY e.season, e.week, e.position, e.salary DESC
"""


DST_ACTUAL_GAP_SQL = """
WITH expected AS (
  SELECT season, week,
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END AS team
  FROM `{raw}.schedules`
  WHERE game_type = 'REG' AND season >= {first_season}
    AND home_score IS NOT NULL AND away_score IS NOT NULL
  UNION ALL
  SELECT season, week,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END
  FROM `{raw}.schedules`
  WHERE game_type = 'REG' AND season >= {first_season}
    AND home_score IS NOT NULL AND away_score IS NOT NULL
)
SELECT DISTINCT e.season, e.week, e.team
FROM expected e
LEFT JOIN `{features}.team_defense_week` d
  USING (season, week, team)
WHERE d.team IS NULL
ORDER BY e.season, e.week, e.team
"""


UPCOMING_CONTEXT_GAP_SQL = """
WITH spine AS (
  SELECT DISTINCT team, season, week
  FROM `{features}.player_week_role`
  WHERE is_upcoming
), gaps AS (
  SELECT 'team_week_pace' AS source_table, s.*
  FROM spine s LEFT JOIN `{features}.team_week_pace` t
    USING (team, season, week)
  WHERE t.team IS NULL
  UNION ALL
  SELECT 'defense_week_blitz', s.*
  FROM spine s LEFT JOIN `{features}.defense_week_blitz` t
    USING (team, season, week)
  WHERE t.team IS NULL
  UNION ALL
  SELECT 'team_week_target_concentration', s.*
  FROM spine s LEFT JOIN `{features}.team_week_target_concentration` t
    USING (team, season, week)
  WHERE t.team IS NULL
  UNION ALL
  SELECT 'team_week_ftn_offense', s.*
  FROM spine s LEFT JOIN `{features}.team_week_ftn_offense` t
    USING (team, season, week)
  WHERE t.team IS NULL
)
SELECT * FROM gaps ORDER BY source_table, season, week, team
"""


DEFENSE_L6_FEATURES = ["epa_per_dropback_allowed_l6", "epa_per_rush_allowed_l6"]
DEFENSE_SOURCE_COLS = ["epa_per_dropback_allowed", "epa_per_rush_allowed"]
DEFENSE_ADJ_FEATURES = [
    "qb_fp_allowed_adj_l6", "rb_fp_allowed_adj_l6",
    "wr_fp_allowed_adj_l6", "te_fp_allowed_adj_l6",
]

DEFENSE_SAMPLE_SQL = """
SELECT team, season, week, {cols}
FROM `{table}`
WHERE MOD(FARM_FINGERPRINT(team), 4) = 0  -- deterministic 8-team sample
"""

# Mirrors 017's def_games CTE exactly; sampled by team, not player.
DEFENSE_SOURCE_SQL = """
SELECT defteam AS team, season, week,
       AVG(IF(qb_dropback = 1, epa, NULL)) AS epa_per_dropback_allowed,
       AVG(IF(rush_attempt = 1, epa, NULL)) AS epa_per_rush_allowed
FROM `{raw}.pbp`
WHERE defteam IS NOT NULL AND season_type = 'REG'
  AND MOD(FARM_FINGERPRINT(defteam), 4) = 0
GROUP BY 1, 2, 3
"""


COVERAGE_CHECKS = [
    # (built l6 col, per-game source col)
    ("cb_ypt_allowed_l6", "cb_ypt_allowed"),
    ("cb_comp_rate_allowed_l6", "cb_comp_rate_allowed"),
    ("db_ypt_allowed_l6", "db_ypt_allowed"),
]

# Mirrors 017a's cov_games CTE exactly; sampled by team. PFR advstats start
# in 2018, so pre-2018 built rows simply have nothing to compare against
# (they're NULL and drop out of the merge).
COVERAGE_SOURCE_SQL = """
WITH def_pos AS (
  SELECT pfr_player_id, season, week, position
  FROM `{raw}.snap_counts`
  WHERE defense_snaps > 0 AND pfr_player_id IS NOT NULL
)
SELECT
  a.team, a.season, a.week,
  SAFE_DIVIDE(
    SUM(IF(p.position = 'CB', a.def_yards_allowed, NULL)),
    NULLIF(SUM(IF(p.position = 'CB', a.def_targets, NULL)), 0)
  ) AS cb_ypt_allowed,
  SAFE_DIVIDE(
    SUM(IF(p.position = 'CB', a.def_completions_allowed, NULL)),
    NULLIF(SUM(IF(p.position = 'CB', a.def_targets, NULL)), 0)
  ) AS cb_comp_rate_allowed,
  SAFE_DIVIDE(
    SUM(IF(p.position IN ('CB', 'DB', 'S', 'FS', 'SS'), a.def_yards_allowed, NULL)),
    NULLIF(SUM(IF(p.position IN ('CB', 'DB', 'S', 'FS', 'SS'), a.def_targets, NULL)), 0)
  ) AS db_ypt_allowed
FROM `{raw}.pfr_advstats_def` a
JOIN def_pos p
  ON p.pfr_player_id = a.pfr_player_id
 AND p.season = a.season AND p.week = a.week
WHERE MOD(FARM_FINGERPRINT(a.team), 4) = 0
GROUP BY 1, 2, 3
"""


def run_leakage_checks() -> None:
    from ..bq import query_df
    from ..config import settings

    built_cols = sorted({f for f, *_ in CHECKED_FEATURES} | {"games_played_prior"})
    built = query_df(
        SAMPLE_SQL.format(cols=", ".join(built_cols),
                          table=f"{settings.features}.player_week_usage")
    )
    source = query_df(SOURCE_GRAIN_SQL.format(
        features=settings.features, raw=settings.raw))
    for feature_col, source_col, window in CHECKED_FEATURES:
        assert_no_leakage(built, source, feature_col, source_col, window)
    assert_first_game_features_null(built, [f for f, *_ in CHECKED_FEATURES])

    # Production trail (015): independently rebuild both trailing means and
    # sample volatility from authoritative actual rows. This catches an
    # include-current regression that a first-row-null assertion alone cannot.
    eff_built = query_df(EFFICIENCY_SAMPLE_SQL.format(
        features=settings.features,
        cols=", ".join(f for f, *_ in EFFICIENCY_CHECKS),
    ))
    eff_source = query_df(EFFICIENCY_SOURCE_SQL.format(
        features=settings.features))
    for feature_col, source_col, window, statistic in EFFICIENCY_CHECKS:
        assert_no_leakage(
            eff_built, eff_source, feature_col, source_col, window,
            statistic=statistic, require_null_parity=True,
        )
    assert_first_row_features_null(
        eff_built, [f for f, *_ in EFFICIENCY_CHECKS], ("gsis_id", "season")
    )

    # Advanced opportunity and NGS context (015a): retain the complete usage
    # spine so bounded ROWS windows and missing observations match exactly.
    adv_built = query_df(SAMPLE_SQL.format(
        cols=", ".join(f for f, *_ in ADVANCED_CHECKS),
        table=f"{settings.features}.player_week_advanced",
    ))
    adv_source = query_df(ADVANCED_SOURCE_SQL.format(
        features=settings.features, raw=settings.raw))
    for feature_col, source_col, window in ADVANCED_CHECKS:
        assert_no_leakage(
            adv_built, adv_source, feature_col, source_col, window,
            require_null_parity=True,
        )
    assert_first_row_features_null(
        adv_built, [f for f, *_ in ADVANCED_CHECKS], ("gsis_id", "season")
    )

    # Exact replay-universe contract. This catches identity, source-spine,
    # actual-label, and cold-start filtering regressions before a new build can
    # be used by replay or training.
    gaps = query_df(UNIVERSE_GAP_SQL.format(features=settings.features))
    assert_salary_universe_reconciled(gaps)
    source_gaps = query_df(HISTORICAL_ROSTER_GAP_SQL.format(
        features=settings.features, raw=settings.raw))
    assert_historical_salary_source_reconciled(source_gaps)
    dst_gaps = query_df(DST_ACTUAL_GAP_SQL.format(
        features=settings.features, raw=settings.raw,
        first_season=settings.first_season))
    assert_dst_actual_universe_reconciled(dst_gaps)
    upcoming_gaps = query_df(UPCOMING_CONTEXT_GAP_SQL.format(
        features=settings.features))
    assert_upcoming_context_rows_reconciled(upcoming_gaps)

    # Defense features: same discipline, team grain. EPA-allowed is
    # recomputed per-week from raw pbp on a deterministic team sample and
    # compared against the built l6 window; the adjusted-FP columns can't be
    # cheaply recomputed here, so they get the first-row-null invariant
    # (which is what catches an include-current-week regression).
    def_built = query_df(
        DEFENSE_SAMPLE_SQL.format(
            cols=", ".join(DEFENSE_L6_FEATURES + DEFENSE_ADJ_FEATURES),
            table=f"{settings.features}.defense_week_allowed",
        )
    )
    def_source = query_df(DEFENSE_SOURCE_SQL.format(raw=settings.raw))
    for feature_col, source_col in zip(DEFENSE_L6_FEATURES, DEFENSE_SOURCE_COLS):
        assert_no_leakage(def_built, def_source, feature_col, source_col,
                          window=6, key_col="team")
    assert_first_row_features_null(
        def_built, DEFENSE_L6_FEATURES + DEFENSE_ADJ_FEATURES, ("team", "season")
    )

    # Coverage features (017a): per-game CB-group concessions recomputed from
    # raw PFR advstats on the same team sample. The built table's window
    # slides over schedule-spine rows, so a played game absent from advstats
    # occupies a slot the reference doesn't — min_coverage absorbs that rare
    # drift. Upcoming-week spine rows have no source row and drop out of the
    # merge. top_cb_out isn't a rolling mean, but it is strictly-prior on the
    # snaps side, so the week-1-null invariant applies to it too.
    cov_built = query_df(
        DEFENSE_SAMPLE_SQL.format(
            cols=", ".join([f for f, _ in COVERAGE_CHECKS] + ["top_cb_out"]),
            table=f"{settings.features}.defense_week_coverage",
        )
    )
    cov_source = query_df(COVERAGE_SOURCE_SQL.format(raw=settings.raw))
    for feature_col, source_col in COVERAGE_CHECKS:
        assert_no_leakage(cov_built, cov_source, feature_col, source_col,
                          window=6, key_col="team")
    assert_first_row_features_null(
        cov_built, [f for f, _ in COVERAGE_CHECKS] + ["top_cb_out"],
        ("team", "season"),
    )

    route_sources = query_df(f"""
        SELECT season, week, fp_route_source_season, fp_route_source_week
        FROM `{settings.features}.player_week_fp_route`
        WHERE fp_route_source_season IS NOT NULL
        """)
    assert_route_source_strict_prior(route_sources)

    # Training-table sanity: labels exist, features don't correlate perfectly
    # with same-week labels (a 1.0 correlation is a copied column).
    tr = query_df(
        f"""SELECT target_share_l4, y_targets, dk_points_l4, y_dk_points
            FROM `{settings.features}.player_week_training`
            WHERE RAND() < 0.05"""
    )
    for feat, label in (("target_share_l4", "y_targets"), ("dk_points_l4", "y_dk_points")):
        sub = tr[[feat, label]].dropna()
        if len(sub) > 100 and abs(sub[feat].corr(sub[label])) > 0.98:
            raise LeakageError(f"{feat} correlates {sub[feat].corr(sub[label]):.3f} "
                               f"with same-week {label}; that's a leak, not a feature.")
    log.info("All leakage checks passed")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_leakage_checks()
