"""Offline guards on the feature SQL files themselves.

The BigQuery build can't run in tests, but two invariants are checkable from
the files alone: every file renders with no unresolved ${placeholders}, and
every rolling window in a model-input table ends strictly before the current
row (the point-in-time rule; see CLAUDE.md and features/leakage.py).
"""

import re

import pytest

from nfl_dfs.bq import SQL_DIR, render_sql

FEATURE_SQL = sorted((SQL_DIR / "features").glob("*.sql"))

# Dashboard-only tables (README: "never a model input") may legitimately
# window through CURRENT ROW. Everything else must not.
CURRENT_ROW_OK = {"022_defense_points_against.sql"}


def test_feature_sql_discovered():
    assert len(FEATURE_SQL) >= 17


def test_coverage_table_present_and_ordered_before_training():
    """build.py executes in sorted order; the coverage table must be built
    before the training/inference tables that join it."""
    names = [p.name for p in FEATURE_SQL]
    cov = names.index("017a_defense_week_coverage.sql")
    assert cov < names.index("021_player_week_training.sql")
    assert cov < names.index("023_player_week_inference.sql")


def test_route_shadow_table_is_strict_prior_and_joined_symmetrically():
    names = [p.name for p in FEATURE_SQL]
    route_path = SQL_DIR / "features" / "017k_fantasy_points_route.sql"
    route = route_path.read_text()
    assert names.index(route_path.name) < names.index("021_player_week_training.sql")
    assert names.index(route_path.name) < names.index("023_player_week_inference.sql")
    assert "h.season * 100 + h.week < t.season * 100 + t.week" in route
    assert "source_rank <= 4" in route
    assert "route-share-unavailable-fallback" in route
    for consumer in ("021_player_week_training.sql", "023_player_week_inference.sql"):
        sql = (SQL_DIR / "features" / consumer).read_text()
        assert "player_week_fp_route" in sql
        for column in (
            "fp_route_source_season", "fp_route_source_week",
            "fp_route_source_sha256",
            "fp_route_share_last", "fp_route_share_l4",
            "fp_route_share_jump", "fp_route_cross_season",
            "fp_route_fallback",
        ):
            assert f"fr.{column}" in sql


def test_salary_spine_built_before_actuals_and_usage():
    """Historical player membership starts at the selectable DK universe."""
    names = [p.name for p in FEATURE_SQL]
    salary = names.index("001a_dk_salary_week.sql")
    assert "019_dk_salary_week.sql" not in names
    assert salary < names.index("013_player_week_actuals.sql")
    assert salary < names.index("014_player_week_usage.sql")
    assert salary < names.index("021_player_week_training.sql")


def test_historical_salary_identity_and_usage_spine_are_guarded():
    salary = (SQL_DIR / "features" / "001a_dk_salary_week.sql").read_text()
    usage = (SQL_DIR / "features" / "014_player_week_usage.sql").read_text()
    training = (SQL_DIR / "features" / "021_player_week_training.sql").read_text()
    assert "JR|SR|II|III|IV|V" in salary
    assert "source_priority" in salary
    assert "norm_rosters AS" in salary
    assert "FROM `${raw}.rosters_weekly`" in salary
    assert "UNNEST([name, merge_name]) AS id_name" in salary
    assert "CONCAT(football_name, ' ', last_name)" in salary
    assert "historical_name_aliases AS" in salary
    assert "('KENNY GAINWELL', 'KENNETH GAINWELL')" in salary
    assert "('NICK WESTBROOK', 'NICK WESTBROOKIKHINE')" in salary
    assert "('PHILLY BROWN', 'COREY BROWN')" in salary
    for old, new in (("ARZ", "ARI"), ("BLT", "BAL"), ("CLV", "CLE"),
                     ("HST", "HOU"), ("SL", "LA")):
        assert f"WHEN '{old}' THEN '{new}'" in salary
    assert "h.season <= 2021" not in salary
    assert "r.season = h.season AND r.week = h.week" in salary
    assert "r.team = h.team AND r.clean_name = h.clean_name" in salary
    assert "COUNT(DISTINCT IF(r.position = h.position" in salary
    assert "ir.team = h.team AND ir.gsis_id = i.gsis_id" in salary
    assert "COUNT(DISTINCT IF(ir.position = h.position" in salary
    assert "r' +', ' '" in salary
    assert "schedule_games AS" in salary
    assert salary.count("WHERE game_type = 'REG'") >= 2
    assert "g.team = h.team" in salary
    assert "g.opponent = h.opponent" in salary
    assert "h.season = 2025 AND h.opponent IS NULL" in salary
    assert "h.season = 2017 AND h.week = 11 AND h.opponent = '-'" in salary
    assert "CASE UPPER(opponent)" in salary
    assert salary.count("WHEN 'SDG' THEN 'LAC'") >= 3
    assert "clean_name = 'MIKE WILLIAMS'" in salary
    assert "team = 'PIT' THEN 4100" in salary
    assert "clean_name = 'JONATHAN MINGO'" in salary
    assert "team = 'DAL' THEN 3200" in salary
    assert "FROM historical_corrected h" in salary
    assert "MAX(CAST(salary AS INT64))" not in salary
    assert "FROM `${features}.dk_salary_week` sal" in usage
    assert "COALESCE(a.has_stat_line, FALSE)" in usage
    assert "is_active AS was_active" in usage
    assert "games_played_prior >= 1" not in training


def test_historical_dst_exact_labels_preserve_rescheduled_game_exception():
    dst = (SQL_DIR / "features" / "024_team_defense_week.sql").read_text()
    assert "h.season = 2017 AND h.week = 11 AND h.opponent = '-'" in dst
    assert "h.team = 'MIA' AND g.opponent = 'TB'" in dst
    assert "h.team = 'TB' AND g.opponent = 'MIA'" in dst


def test_dst_actuals_credit_event_team_and_exclude_offense_points():
    dst = (SQL_DIR / "features" / "024_team_defense_week.sql").read_text()
    assert "fumble_recovery_1_team != fumbled_1_team" in dst
    assert "fumble_recovery_2_team != fumbled_2_team" in dst
    assert "return_touchdown = 1 AND td_team = defteam" in dst
    assert "play_type IN ('kickoff', 'punt', 'field_goal')" in dst
    assert "defensive_two_point_conv" in dst
    assert "offense_points_not_allowed" in dst
    assert "defensive_td_points" in dst
    assert "safety_points" in dst
    assert "historical_exact_raw" in dst
    assert "g.team = h.team" in dst
    assert "g.opponent = h.opponent" in dst
    assert "COALESCE(h.exact_dk_points, n.dst_dk_points)" in dst
    assert "schedules_normalized AS" in dst
    assert dst.count("FROM schedules_normalized s") == 2
    assert "FROM schedules_normalized" in dst
    assert dst.index("schedules_normalized AS") < dst.index("points_allowed AS")


def test_referee_tiebreak_uses_live_officials_schema():
    sql = (SQL_DIR / "features" / "017b_referee_tendency.sql").read_text()
    assert "ORDER BY official_name, official_id" in sql
    assert "ORDER BY name" not in sql


def test_target_concentration_tiebreak_uses_weekly_stats_schema():
    sql = (SQL_DIR / "features" / "017g_target_concentration.sql").read_text()
    assert "ORDER BY t DESC, player_id" in sql
    assert "ORDER BY t DESC, gsis_id" not in sql


@pytest.mark.parametrize("path", FEATURE_SQL, ids=lambda p: p.name)
def test_renders_without_unresolved_placeholders(path):
    sql = render_sql(path, prior_k=4)
    assert "${" not in sql


@pytest.mark.parametrize("path", FEATURE_SQL, ids=lambda p: p.name)
def test_model_input_windows_exclude_current_row(path):
    if path.name in CURRENT_ROW_OK:
        pytest.skip("dashboard table, windows through CURRENT ROW by design")
    for clause in re.findall(r"ROWS BETWEEN[^)]+", path.read_text()):
        assert clause.rstrip().endswith("1 PRECEDING"), (
            f"{path.name}: rolling window does not end at 1 PRECEDING: {clause!r}"
        )
