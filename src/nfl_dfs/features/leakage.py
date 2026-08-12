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

# Must remain identical to the value rendered into 014 by the feature builder.
# Keeping the independent recomputation explicit makes a smoothing-contract
# change fail closed rather than silently validating a different estimator.
SMOOTHING_PRIOR_K = 4


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


def team_qb_cpoe_strict_prior(
    schedule: pd.DataFrame,
    dropbacks: pd.DataFrame,
) -> pd.DataFrame:
    """Pure reference for the six-prior-team-game CPOE feature.

    ``dropbacks`` is one row per qualifying play with ``team``, ``season``,
    ``week`` and ``cpoe``. The schedule, not the observation table, defines
    the bounded six-game window, and the partition intentionally crosses
    season boundaries. This helper is used only as an independent synthetic
    contract; the warehouse implementation remains SQL.
    """
    keys = ["team", "season", "week"]
    spine = schedule[keys].drop_duplicates().sort_values(keys).copy()
    observed = dropbacks.dropna(subset=["team", "cpoe"]).groupby(
        keys, as_index=False
    ).agg(cpoe_sum=("cpoe", "sum"), cpoe_dropbacks=("cpoe", "count"))
    frame = spine.merge(observed, on=keys, how="left", validate="one_to_one")
    rows: list[dict[str, object]] = []
    for team, group in frame.groupby("team", sort=False):
        group = group.sort_values(["season", "week"]).reset_index(drop=True)
        for idx, target in group.iterrows():
            prior = group.iloc[max(0, idx - 6):idx]
            denominator = prior["cpoe_dropbacks"].sum(min_count=1)
            numerator = prior["cpoe_sum"].sum(min_count=1)
            rows.append({
                "team": team,
                "season": target["season"],
                "week": target["week"],
                "team_qb_cpoe_l6": (
                    numerator / denominator
                    if pd.notna(denominator) and denominator > 0 else np.nan
                ),
                "team_qb_cpoe_dropbacks_l6": denominator,
                "team_qb_cpoe_games_l6": int(
                    prior["cpoe_dropbacks"].notna().sum()),
            })
    return pd.DataFrame(rows).sort_values(keys).reset_index(drop=True)


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


def assert_recomputed_features_match(
    built: pd.DataFrame,
    expected: pd.DataFrame,
    feature_cols: list[str],
    key_cols: tuple[str, ...],
    atol: float = 1e-6,
    exact_cols: tuple[str, ...] = (),
) -> None:
    """Require exact keys, null support and values from an independent SQL.

    Some transforms are ratios of rolling sums or window across seasons, so
    they cannot use the simple per-column rolling-mean helper. Their reference
    query still lives independently here and this comparison fails closed on
    missing keys, changed missingness or numeric drift.
    """
    for label, frame in (("built", built), ("expected", expected)):
        if frame.duplicated(list(key_cols)).any():
            raise LeakageError(f"{label} recomputation frame has duplicate keys")
    merged = built.merge(
        expected, on=list(key_cols), how="outer", suffixes=("_built", "_expected"),
        indicator=True, validate="one_to_one",
    )
    if not merged["_merge"].eq("both").all():
        bad = merged.loc[merged["_merge"].ne("both"), [*key_cols, "_merge"]].head(5)
        raise LeakageError(
            "source recomputation keys differ from the built table. "
            f"Examples:\n{bad.to_string(index=False)}"
        )
    for feature in feature_cols:
        left = merged[f"{feature}_built"]
        right = merged[f"{feature}_expected"]
        null_mismatch = left.isna().ne(right.isna())
        numeric_mismatch = ~(np.isclose(left, right, atol=atol) | (left.isna() & right.isna()))
        mismatch = null_mismatch | numeric_mismatch
        if mismatch.any():
            cols = [*key_cols, f"{feature}_built", f"{feature}_expected"]
            bad = merged.loc[mismatch, cols].head(5)
            raise LeakageError(
                f"{feature}: {int(mismatch.sum())} source-recomputed rows "
                f"disagree. Examples:\n{bad.to_string(index=False)}"
            )
    for feature in exact_cols:
        left = merged[f"{feature}_built"]
        right = merged[f"{feature}_expected"]
        mismatch = left.isna().ne(right.isna()) | ~(
            left.eq(right) | (left.isna() & right.isna()))
        if mismatch.any():
            cols = [*key_cols, f"{feature}_built", f"{feature}_expected"]
            bad = merged.loc[mismatch, cols].head(5)
            raise LeakageError(
                f"{feature}: {int(mismatch.sum())} exact source-recomputed "
                f"rows disagree. Examples:\n{bad.to_string(index=False)}"
            )


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


# Independently reconstruct the complete usage-family transform. This covers
# the active l4/WOPR/snap/smoothing inputs and the fast-role candidate fields,
# not just one representative rolling mean. The two empirical-Bayes fields
# additionally require a position prior that is itself strictly point-in-time;
# a single all-history position average leaks future seasons even though the
# player window ends at 1 PRECEDING.
USAGE_RECOMPUTED_FEATURES = [
    "rz20_targets_l4", "rz10_targets_l4", "targets_l4",
    "target_share_l4", "air_yards_share_l4",
    "rz20_target_share_l4", "rz10_target_share_l4",
    "rz20_carries_l4", "gl3_carries_l4", "carries_l4",
    "carry_share_l4", "gl3_carry_share_l4", "snap_share_l4",
    "target_share_last", "carry_share_last", "snap_share_last",
    "rz20_targets_std", "target_share_std", "targets_std", "carries_std",
    "target_share_trend", "carry_share_trend", "games_played_prior",
    "target_share_jump", "carry_share_jump", "snap_share_jump", "wopr_l4",
    "rz20_targets_smoothed", "gl3_carries_smoothed",
]
USAGE_RECOMPUTED_BUILT_SQL = """
SELECT gsis_id, season, week, {cols}
FROM `{features}.player_week_usage`
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0
"""
USAGE_RECOMPUTED_EXPECTED_SQL = """
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
), observations AS (
  SELECT sal.gsis_id, sal.season, sal.week, sal.team, sal.position,
         COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL
           AS is_active,
         sn.snap_share,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rec.rz20_targets, 0), NULL) AS rz20_targets,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rec.rz10_targets, 0), NULL) AS rz10_targets,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rec.total_targets, 0), NULL) AS total_targets,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rec.target_share, 0), NULL) AS target_share,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rec.air_yards_share, 0), NULL) AS air_yards_share,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rec.rz20_target_share, 0), NULL) AS rz20_target_share,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rec.rz10_target_share, 0), NULL) AS rz10_target_share,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rush.rz20_carries, 0), NULL) AS rz20_carries,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rush.gl3_carries, 0), NULL) AS gl3_carries,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rush.total_carries, 0), NULL) AS total_carries,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rush.carry_share, 0), NULL) AS carry_share,
         IF(COALESCE(a.has_stat_line, FALSE) OR sn.snap_share IS NOT NULL,
            COALESCE(rush.gl3_carry_share, 0), NULL) AS gl3_carry_share
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
), upcoming AS (
  SELECT ro.gsis_id, ro.season, ro.week, ro.team, ro.position,
         FALSE AS is_active,
         CAST(NULL AS FLOAT64) AS snap_share,
         CAST(NULL AS INT64) AS rz20_targets,
         CAST(NULL AS INT64) AS rz10_targets,
         CAST(NULL AS INT64) AS total_targets,
         CAST(NULL AS FLOAT64) AS target_share,
         CAST(NULL AS FLOAT64) AS air_yards_share,
         CAST(NULL AS FLOAT64) AS rz20_target_share,
         CAST(NULL AS FLOAT64) AS rz10_target_share,
         CAST(NULL AS INT64) AS rz20_carries,
         CAST(NULL AS INT64) AS gl3_carries,
         CAST(NULL AS INT64) AS total_carries,
         CAST(NULL AS FLOAT64) AS carry_share,
         CAST(NULL AS FLOAT64) AS gl3_carry_share
  FROM `{features}.player_week_role` ro
  WHERE ro.is_upcoming
    AND NOT EXISTS (
      SELECT 1 FROM observations o
      WHERE o.gsis_id = ro.gsis_id AND o.season = ro.season
        AND o.week = ro.week
    )
), usage_all AS (
  SELECT * FROM observations
  UNION ALL
  SELECT * FROM upcoming
), rolled AS (
  SELECT gsis_id, season, week, position,
         AVG(rz20_targets) OVER w4 AS rz20_targets_l4,
         AVG(rz10_targets) OVER w4 AS rz10_targets_l4,
         AVG(total_targets) OVER w4 AS targets_l4,
         AVG(target_share) OVER w4 AS target_share_l4,
         AVG(air_yards_share) OVER w4 AS air_yards_share_l4,
         AVG(rz20_target_share) OVER w4 AS rz20_target_share_l4,
         AVG(rz10_target_share) OVER w4 AS rz10_target_share_l4,
         AVG(rz20_carries) OVER w4 AS rz20_carries_l4,
         AVG(gl3_carries) OVER w4 AS gl3_carries_l4,
         AVG(total_carries) OVER w4 AS carries_l4,
         AVG(carry_share) OVER w4 AS carry_share_l4,
         AVG(gl3_carry_share) OVER w4 AS gl3_carry_share_l4,
         AVG(snap_share) OVER w4 AS snap_share_l4,
         LAST_VALUE(target_share IGNORE NULLS) OVER w4 AS target_share_last,
         LAST_VALUE(carry_share IGNORE NULLS) OVER w4 AS carry_share_last,
         LAST_VALUE(snap_share IGNORE NULLS) OVER w4 AS snap_share_last,
         SUM(target_share) OVER w4 AS target_share_sum_l4,
         SUM(carry_share) OVER w4 AS carry_share_sum_l4,
         SUM(snap_share) OVER w4 AS snap_share_sum_l4,
         COUNT(target_share) OVER w4 AS target_share_n_l4,
         COUNT(carry_share) OVER w4 AS carry_share_n_l4,
         COUNT(snap_share) OVER w4 AS snap_share_n_l4,
         AVG(rz20_targets) OVER wprior AS rz20_targets_std,
         AVG(target_share) OVER wprior AS target_share_std,
         AVG(total_targets) OVER wprior AS targets_std,
         AVG(total_carries) OVER wprior AS carries_std,
         SUM(rz20_targets) OVER w AS rz20_targets_sum_prior,
         SUM(gl3_carries) OVER w AS gl3_carries_sum_prior,
         SAFE_DIVIDE(AVG(target_share) OVER w4,
                     AVG(target_share) OVER wprior) AS target_share_trend,
         SAFE_DIVIDE(AVG(carry_share) OVER w4,
                     AVG(carry_share) OVER wprior) AS carry_share_trend,
         COUNTIF(is_active) OVER wprior AS games_played_prior
  FROM usage_all
  WINDOW
    w4 AS (PARTITION BY gsis_id, season ORDER BY week
           ROWS BETWEEN 4 PRECEDING AND 1 PRECEDING),
    wprior AS (PARTITION BY gsis_id, season ORDER BY week
               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING),
    w AS (PARTITION BY gsis_id, season ORDER BY week
          ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
), position_week AS (
  SELECT position, season, week,
         SUM(rz20_targets) AS rz20_targets_sum,
         COUNT(rz20_targets) AS rz20_targets_n,
         SUM(gl3_carries) AS gl3_carries_sum,
         COUNT(gl3_carries) AS gl3_carries_n
  FROM observations
  GROUP BY position, season, week
), position_prior AS (
  SELECT position, season, week,
         SAFE_DIVIDE(SUM(rz20_targets_sum) OVER w,
                     SUM(rz20_targets_n) OVER w) AS prior_rz20_per_game,
         SAFE_DIVIDE(SUM(gl3_carries_sum) OVER w,
                     SUM(gl3_carries_n) OVER w) AS prior_gl3_per_game
  FROM position_week
  WINDOW w AS (PARTITION BY position ORDER BY season, week
               ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING)
)
SELECT p.gsis_id, p.season, p.week,
       p.rz20_targets_l4, p.rz10_targets_l4, p.targets_l4,
       p.target_share_l4, p.air_yards_share_l4,
       p.rz20_target_share_l4, p.rz10_target_share_l4,
       p.rz20_carries_l4, p.gl3_carries_l4, p.carries_l4,
       p.carry_share_l4, p.gl3_carry_share_l4, p.snap_share_l4,
       p.target_share_last, p.carry_share_last, p.snap_share_last,
       p.rz20_targets_std, p.target_share_std, p.targets_std, p.carries_std,
       p.target_share_trend, p.carry_share_trend, p.games_played_prior,
       CASE WHEN p.target_share_n_l4 >= 2 THEN
         p.target_share_last - SAFE_DIVIDE(
           p.target_share_sum_l4 - p.target_share_last,
           p.target_share_n_l4 - 1)
       END AS target_share_jump,
       CASE WHEN p.carry_share_n_l4 >= 2 THEN
         p.carry_share_last - SAFE_DIVIDE(
           p.carry_share_sum_l4 - p.carry_share_last,
           p.carry_share_n_l4 - 1)
       END AS carry_share_jump,
       CASE WHEN p.snap_share_n_l4 >= 2 THEN
         p.snap_share_last - SAFE_DIVIDE(
           p.snap_share_sum_l4 - p.snap_share_last,
           p.snap_share_n_l4 - 1)
       END AS snap_share_jump,
       1.5 * p.target_share_l4 + 0.7 * p.air_yards_share_l4 AS wopr_l4,
       SAFE_DIVIDE(
         p.rz20_targets_sum_prior + ({prior_k} * q.prior_rz20_per_game),
         p.games_played_prior + {prior_k}
       ) AS rz20_targets_smoothed,
       SAFE_DIVIDE(
         p.gl3_carries_sum_prior + ({prior_k} * q.prior_gl3_per_game),
         p.games_played_prior + {prior_k}
       ) AS gl3_carries_smoothed
FROM rolled p
LEFT JOIN position_prior q USING (position, season, week)
WHERE MOD(FARM_FINGERPRINT(p.gsis_id), 20) = 0
"""


# Injury rows are legitimately same-week only when their source timestamp is
# available at the common Sunday-main lock. The raw feed occasionally contains
# multiple revisions for one player-week and a handful of post-lock updates,
# so both latest-pre-lock selection and downstream vacancy composition are
# rebuilt independently.
INJURY_FEATURES = [
    "practice_level", "practice_participation_trend", "games_missed_l4",
]
INJURY_EXACT_FIELDS = [
    "injury_status", "injury_source_modified_at", "slate_lock_at",
]
INJURY_BUILT_SQL = """
SELECT gsis_id, season, week, injury_status, practice_level,
       practice_participation_trend, games_missed_l4,
       injury_source_modified_at, slate_lock_at
FROM `{features}.player_week_injury`
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0
"""
INJURY_EXPECTED_SQL = """
WITH slate_locks AS (
  SELECT season, week,
    MIN(TIMESTAMP(
      DATETIME(PARSE_DATE('%Y-%m-%d', gameday),
               SAFE.PARSE_TIME('%H:%M', gametime)),
      'America/New_York'
    )) AS slate_lock_at
  FROM `{raw}.schedules`
  WHERE game_type = 'REG' AND weekday = 'Sunday'
    AND SAFE.PARSE_TIME('%H:%M', gametime) >= TIME '13:00:00'
    AND SAFE.PARSE_TIME('%H:%M', gametime) < TIME '19:00:00'
  GROUP BY season, week
), injury AS (
  SELECT i.gsis_id, CAST(i.season AS INT64) AS season,
         CAST(i.week AS INT64) AS week, i.report_status AS injury_status,
         CASE i.practice_status
           WHEN 'Did Not Participate In Practice' THEN 0.0
           WHEN 'Limited Participation in Practice' THEN 1.0
           WHEN 'Full Participation in Practice' THEN 2.0
         END AS practice_level,
         i.date_modified AS injury_source_modified_at, l.slate_lock_at
  FROM `{raw}.injuries` i
  JOIN slate_locks l
    ON l.season = CAST(i.season AS INT64)
   AND l.week = CAST(i.week AS INT64)
  WHERE i.gsis_id IS NOT NULL AND i.date_modified <= l.slate_lock_at
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY i.gsis_id, CAST(i.season AS INT64), CAST(i.week AS INT64)
    ORDER BY i.date_modified DESC, i.team DESC, i.practice_status DESC
  ) = 1
), missed AS (
  SELECT i.gsis_id, i.season, i.week,
         COUNTIF(prior.injury_status = 'Out') AS games_missed_l4
  FROM injury i
  LEFT JOIN injury prior
    ON prior.gsis_id = i.gsis_id AND prior.season = i.season
   AND prior.week BETWEEN i.week - 4 AND i.week - 1
  GROUP BY i.gsis_id, i.season, i.week
)
SELECT i.gsis_id, i.season, i.week, i.injury_status, i.practice_level,
       i.practice_level - LAG(i.practice_level) OVER (
         PARTITION BY i.gsis_id, i.season ORDER BY i.week
       ) AS practice_participation_trend,
       COALESCE(m.games_missed_l4, 0) AS games_missed_l4,
       i.injury_source_modified_at, i.slate_lock_at
FROM injury i LEFT JOIN missed m USING (gsis_id, season, week)
WHERE MOD(FARM_FINGERPRINT(i.gsis_id), 20) = 0
"""

VACATED_FEATURES = [
    "team_vacated_target_share", "team_vacated_carry_share",
]
VACATED_BUILT_SQL = """
SELECT gsis_id, season, week,
       team_vacated_target_share, team_vacated_carry_share
FROM `{features}.player_week_training`
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0
"""
VACATED_EXPECTED_SQL = """
WITH outs AS (
  SELECT gsis_id, season, week
  FROM `{features}.player_week_injury`
  WHERE injury_status = 'Out'
), asof AS (
  SELECT o.gsis_id, o.season, o.week, u.team,
         u.target_share_l4, u.carry_share_l4
  FROM outs o
  JOIN `{features}.player_week_usage` u
    ON u.gsis_id = o.gsis_id AND u.season = o.season AND u.week <= o.week
  QUALIFY ROW_NUMBER() OVER (
    PARTITION BY o.gsis_id, o.season, o.week ORDER BY u.week DESC
  ) = 1
), vacated AS (
  SELECT team, season, week,
         SUM(COALESCE(target_share_l4, 0)) AS vacated_target_share,
         SUM(COALESCE(carry_share_l4, 0)) AS vacated_carry_share
  FROM asof GROUP BY team, season, week
)
SELECT t.gsis_id, t.season, t.week,
       GREATEST(
         COALESCE(v.vacated_target_share, 0)
           - IF(i.injury_status = 'Out',
                COALESCE(u.target_share_l4, 0), 0),
         0
       ) AS team_vacated_target_share,
       GREATEST(
         COALESCE(v.vacated_carry_share, 0)
           - IF(i.injury_status = 'Out',
                COALESCE(u.carry_share_l4, 0), 0),
         0
       ) AS team_vacated_carry_share
FROM `{features}.player_week_training` t
LEFT JOIN `{features}.player_week_usage` u
  USING (gsis_id, season, week)
LEFT JOIN `{features}.player_week_injury` i
  USING (gsis_id, season, week)
LEFT JOIN vacated v
  ON v.team = t.team AND v.season = t.season AND v.week = t.week
WHERE MOD(FARM_FINGERPRINT(t.gsis_id), 20) = 0
"""


NEUTRAL_PASS_FEATURES = ["neutral_pass_rate_l6"]
NEUTRAL_PASS_BUILT_SQL = """
SELECT team, season, week, neutral_pass_rate_l6
FROM `{features}.team_week_neutral_pass`
WHERE MOD(FARM_FINGERPRINT(team), 4) = 0
"""
NEUTRAL_PASS_EXPECTED_SQL = """
WITH plays AS (
  SELECT posteam AS team, season, week, CAST(pass AS INT64) AS is_pass
  FROM `{raw}.pbp`
  WHERE posteam IS NOT NULL AND (pass = 1 OR rush = 1)
    AND ABS(COALESCE(score_differential, 0)) <= 3
    AND half_seconds_remaining > 120 AND qtr <= 4
), tw AS (
  SELECT team, season, week, SUM(is_pass) AS p, COUNT(*) AS n
  FROM plays GROUP BY team, season, week
), spine AS (
  SELECT * FROM tw
  UNION ALL
  SELECT DISTINCT ro.team, ro.season, ro.week,
         CAST(NULL AS INT64) AS p, CAST(NULL AS INT64) AS n
  FROM `{features}.player_week_role` ro
  WHERE ro.is_upcoming AND ro.team IS NOT NULL
    AND NOT EXISTS (
      SELECT 1 FROM tw prior
      WHERE prior.team = ro.team AND prior.season = ro.season
        AND prior.week = ro.week
    )
)
SELECT team, season, week,
       SAFE_DIVIDE(SUM(p) OVER w, SUM(n) OVER w) AS neutral_pass_rate_l6
FROM spine
WHERE MOD(FARM_FINGERPRINT(team), 4) = 0
WINDOW w AS (PARTITION BY team ORDER BY season, week
             ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)
"""

QB_NGS_FEATURES = ["qb_cpoe_l6", "qb_time_to_throw_l6"]
QB_NGS_BUILT_SQL = """
SELECT gsis_id, season, week, qb_cpoe_l6, qb_time_to_throw_l6
FROM `{features}.qb_week_ngs`
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0
"""
QB_NGS_EXPECTED_SQL = """
WITH observations AS (
  SELECT player_gsis_id AS gsis_id, season, week,
         completion_percentage_above_expectation AS cpoe,
         avg_time_to_throw AS time_to_throw
  FROM `{raw}.ngs_passing`
  WHERE week > 0
), spine AS (
  SELECT * FROM observations
  UNION ALL
  SELECT DISTINCT ro.gsis_id, ro.season, ro.week,
         CAST(NULL AS FLOAT64) AS cpoe,
         CAST(NULL AS FLOAT64) AS time_to_throw
  FROM `{features}.player_week_role` ro
  WHERE ro.is_upcoming AND ro.position = 'QB'
    AND NOT EXISTS (
      SELECT 1 FROM observations prior
      WHERE prior.gsis_id = ro.gsis_id AND prior.season = ro.season
        AND prior.week = ro.week
    )
)
SELECT gsis_id, season, week,
       AVG(cpoe) OVER w AS qb_cpoe_l6,
       AVG(time_to_throw) OVER w AS qb_time_to_throw_l6
FROM spine
WHERE MOD(FARM_FINGERPRINT(gsis_id), 20) = 0
WINDOW w AS (PARTITION BY gsis_id ORDER BY season, week
             ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING)
"""


TEAM_QB_QUALITY_FEATURES = [
    "team_qb_cpoe_l6",
    "team_qb_cpoe_dropbacks_l6",
    "team_qb_cpoe_games_l6",
]
TEAM_QB_QUALITY_BUILT_SQL = """
SELECT team, season, week,
       team_qb_cpoe_l6, team_qb_cpoe_dropbacks_l6,
       team_qb_cpoe_games_l6
FROM `{features}.team_week_qb_quality`
WHERE MOD(FARM_FINGERPRINT(team), 4) = 0
"""
TEAM_QB_QUALITY_EXPECTED_SQL = """
WITH spine AS (
  SELECT season, week,
    CASE home_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE home_team END AS team
  FROM `{raw}.schedules`
  WHERE game_type = 'REG' AND home_score IS NOT NULL AND away_score IS NOT NULL
  UNION DISTINCT
  SELECT season, week,
    CASE away_team WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                   WHEN 'STL' THEN 'LA' ELSE away_team END AS team
  FROM `{raw}.schedules`
  WHERE game_type = 'REG' AND home_score IS NOT NULL AND away_score IS NOT NULL
  UNION DISTINCT
  SELECT season, week, team
  FROM `{features}.player_week_role`
  WHERE is_upcoming AND team IS NOT NULL
), weekly AS (
  SELECT
    CASE posteam WHEN 'OAK' THEN 'LV' WHEN 'SD' THEN 'LAC'
                 WHEN 'STL' THEN 'LA' ELSE posteam END AS team,
    season, week,
    SUM(CAST(cpoe AS FLOAT64)) AS cpoe_sum,
    COUNT(cpoe) AS cpoe_dropbacks
  FROM `{raw}.pbp`
  WHERE qb_dropback = 1 AND posteam IS NOT NULL AND cpoe IS NOT NULL
    AND season_type = 'REG'
  GROUP BY 1, 2, 3
), prior_schedule AS (
  SELECT
    target.team, target.season, target.week,
    prior.season AS prior_season, prior.week AS prior_week,
    ROW_NUMBER() OVER (
      PARTITION BY target.team, target.season, target.week
      ORDER BY prior.season DESC, prior.week DESC
    ) AS prior_rank
  FROM spine target
  LEFT JOIN spine prior
    ON prior.team = target.team
   AND (prior.season < target.season
        OR (prior.season = target.season AND prior.week < target.week))
  WHERE MOD(FARM_FINGERPRINT(target.team), 4) = 0
), expected AS (
  SELECT
    p.team, p.season, p.week,
    SAFE_DIVIDE(SUM(w.cpoe_sum), SUM(w.cpoe_dropbacks)) AS team_qb_cpoe_l6,
    SUM(w.cpoe_dropbacks) AS team_qb_cpoe_dropbacks_l6,
    COUNTIF(w.cpoe_dropbacks IS NOT NULL) AS team_qb_cpoe_games_l6
  FROM prior_schedule p
  LEFT JOIN weekly w
    ON w.team = p.team AND w.season = p.prior_season
   AND w.week = p.prior_week
  WHERE p.prior_rank <= 6
  GROUP BY 1, 2, 3
)
SELECT * FROM expected
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


def run_team_qb_quality_checks() -> None:
    """Validate only the isolated strict-prior team-QB-quality side table."""
    from ..bq import query_df
    from ..config import settings

    team_qb_built = query_df(TEAM_QB_QUALITY_BUILT_SQL.format(
        features=settings.features))
    team_qb_expected = query_df(TEAM_QB_QUALITY_EXPECTED_SQL.format(
        features=settings.features, raw=settings.raw))
    assert_recomputed_features_match(
        team_qb_built, team_qb_expected, TEAM_QB_QUALITY_FEATURES,
        ("team", "season", "week"),
    )


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

    # Reconstruct every usage-family model/candidate field from raw source
    # observations. This catches bounded-window, last-value, jump, ratio and
    # empirical-Bayes position-prior regressions with exact key/null parity.
    usage_built = query_df(USAGE_RECOMPUTED_BUILT_SQL.format(
        features=settings.features,
        cols=", ".join(USAGE_RECOMPUTED_FEATURES),
    ))
    usage_expected = query_df(USAGE_RECOMPUTED_EXPECTED_SQL.format(
        features=settings.features, raw=settings.raw,
        prior_k=SMOOTHING_PRIOR_K,
    ))
    assert_recomputed_features_match(
        usage_built, usage_expected, USAGE_RECOMPUTED_FEATURES,
        ("gsis_id", "season", "week"),
    )

    injury_built = query_df(INJURY_BUILT_SQL.format(
        features=settings.features))
    injury_expected = query_df(INJURY_EXPECTED_SQL.format(
        raw=settings.raw))
    assert_recomputed_features_match(
        injury_built, injury_expected, INJURY_FEATURES,
        ("gsis_id", "season", "week"),
        exact_cols=tuple(INJURY_EXACT_FIELDS),
    )
    vacated_built = query_df(VACATED_BUILT_SQL.format(
        features=settings.features))
    vacated_expected = query_df(VACATED_EXPECTED_SQL.format(
        features=settings.features))
    assert_recomputed_features_match(
        vacated_built, vacated_expected, VACATED_FEATURES,
        ("gsis_id", "season", "week"),
    )

    # Adopted neutral-pass context is a ratio of rolling sums, while NGS QB
    # windows deliberately cross season boundaries. Independent SQL references
    # preserve those exact semantics and fail on any key/null/value drift.
    neutral_built = query_df(NEUTRAL_PASS_BUILT_SQL.format(
        features=settings.features))
    neutral_expected = query_df(NEUTRAL_PASS_EXPECTED_SQL.format(
        features=settings.features, raw=settings.raw))
    assert_recomputed_features_match(
        neutral_built, neutral_expected, NEUTRAL_PASS_FEATURES,
        ("team", "season", "week"),
    )
    qb_built = query_df(QB_NGS_BUILT_SQL.format(features=settings.features))
    qb_expected = query_df(QB_NGS_EXPECTED_SQL.format(
        features=settings.features, raw=settings.raw))
    assert_recomputed_features_match(
        qb_built, qb_expected, QB_NGS_FEATURES,
        ("gsis_id", "season", "week"),
    )
    run_team_qb_quality_checks()

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
