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


def test_game_weather_uses_only_snapshots_pulled_before_lock():
    # O-22 (d): a completed game's weather must be what serving could see:
    # the latest snapshot at/before the earlier of kickoff and the slate lock.
    sql = (SQL_DIR / "features" / "020_game_weather.sql").read_text()
    assert "WHERE w.pulled_at <= g.lock_at" in sql
    assert "LEAST(g.kickoff_at, COALESCE(l.slate_lock_at, g.kickoff_at))" in sql


def test_top_cb_out_reads_the_point_in_time_injury_table_only():
    """O-22 (2026-10-05): 017a runs before 018, so it must not read raw injuries
    (that bypassed 018's common Sunday-main lock). 018a fills top_cb_out from
    player_week_injury after 018 and before the training/inference joins."""
    names = [p.name for p in FEATURE_SQL]
    fill = names.index("018a_defense_week_cb_out.sql")
    assert names.index("017a_defense_week_coverage.sql") < names.index("018_player_week_injury.sql") < fill
    assert fill < names.index("021_player_week_training.sql")
    assert fill < names.index("023_player_week_inference.sql")
    cov = (SQL_DIR / "features" / "017a_defense_week_coverage.sql").read_text()
    out = (SQL_DIR / "features" / "018a_defense_week_cb_out.sql").read_text()
    assert "${raw}.injuries" not in cov and "${features}.player_week_injury" not in cov
    assert "top_cb_pfr_id" in cov and "CAST(NULL AS BOOL) AS top_cb_out" in cov
    assert "${raw}.injuries" not in out
    assert "${features}.player_week_injury" in out
    assert "WHERE c.top_cb_pfr_id IS NOT NULL" in out            # week-1 rows stay NULL
    assert "IFNULL(LOGICAL_OR(inj.injury_status = 'Out'), FALSE)" in out
    # A season-week the point-in-time table does not cover (all of 2025: NULL
    # date_modified) stays NULL: the FALSE default applies only inside covered
    # weeks, so "no source" never reads as "the corner played".
    assert "SELECT DISTINCT season, week FROM `${features}.player_week_injury`" in out
    assert "JOIN pit_weeks pw ON pw.season = c.season AND pw.week = c.week" in out
    assert "LEFT JOIN pit_weeks" not in out


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
    assert "h.team = g.team" in dst
    assert "h.opponent = g.opponent" in dst
    assert "h.sole_authoritative_dst_dk_points" in dst
    assert "n.reconstructed_dst_dk_points" in dst
    assert "schedules_normalized AS" in dst
    assert dst.count("FROM schedules_normalized s") == 2
    assert "FROM schedules_normalized" in dst
    assert dst.index("schedules_normalized AS") < dst.index("points_allowed AS")


def test_referee_tiebreak_uses_live_officials_schema():
    sql = (SQL_DIR / "features" / "017b_referee_tendency.sql").read_text()
    assert "ORDER BY official_name, official_id" in sql
    assert "ORDER BY g.season, g.week, g.game_id" in sql
    assert "ORDER BY name" not in sql


def test_target_concentration_tiebreak_uses_weekly_stats_schema():
    sql = (SQL_DIR / "features" / "017g_target_concentration.sql").read_text()
    assert "ORDER BY t DESC, player_id" in sql
    assert "ORDER BY t DESC, gsis_id" not in sql


def test_adopted_context_features_are_as_of_over_the_usage_spine():
    # O-22 (2026-10-05): the old tables had a row only for event weeks (a
    # neutral-situation play, an NGS passing record, a target or carry) plus
    # one synthetic upcoming row, and 021 joined them by exact week, so a
    # training NULL meant "no event in the game being predicted". Each table
    # now has a row for every player_week_usage key (upcoming week included)
    # holding the mean of the most recent observations strictly before it.
    for name, strictly_prior, window in (
        ("017c_team_neutral_pass.sql",
         "(t.season < s.season OR (t.season = s.season AND t.week < s.week))", "pr.k <= 6"),
        ("017h_qb_ngs.sql",
         "(o.season < s.season OR (o.season = s.season AND o.week < s.week))", "pr.k <= 6"),
        ("017j_xfp_schedule.sql",
         "w.season = s.season AND w.week < s.week", "pr.k <= 4"),
    ):
        sql = (SQL_DIR / "features" / name).read_text()
        assert "FROM `${features}.player_week_usage`" in sql, name
        assert strictly_prior in sql, name
        assert window in sql, name
        assert "1 PRECEDING" not in sql.split("spine AS")[1], name
        assert "is_upcoming" not in sql, name
    infer = (SQL_DIR / "features" / "023_player_week_inference.sql").read_text()
    assert "xfp_asof" not in infer.replace("-- xfp", "")
    assert "LEFT JOIN `${features}.player_week_xfp` xf\n  ON xf.gsis_id = u.gsis_id " \
        "AND xf.season = u.season AND xf.week = u.week" in infer


def test_candidate_team_context_features_emit_upcoming_inference_rows():
    for name in (
        "017e_team_pace.sql",
        "017f_opp_blitz.sql",
        "017g_target_concentration.sql",
        "017i_ftn_offense.sql",
    ):
        sql = (SQL_DIR / "features" / name).read_text()
        assert "`${features}.player_week_role`" in sql
        assert "is_upcoming" in sql
        assert "NOT EXISTS" in sql
        assert "UNION ALL" in sql


def test_team_qb_quality_is_strict_prior_dropback_weighted_side_table():
    """The frozen broadcast signal must not mutate the production table."""
    path = SQL_DIR / "features" / "017l_team_qb_quality.sql"
    sql = path.read_text()
    names = [p.name for p in FEATURE_SQL]
    assert names.index(path.name) < names.index("021_player_week_training.sql")
    assert "CREATE OR REPLACE TABLE `${features}.team_week_qb_quality`" in sql
    assert "FROM `${raw}.schedules`" in sql
    assert "home_score IS NOT NULL AND away_score IS NOT NULL" in sql
    assert "FROM `${features}.player_week_role`" in sql
    assert "is_upcoming AND team IS NOT NULL" in sql
    assert "qb_dropback = 1" in sql
    assert "posteam IS NOT NULL" in sql
    assert "cpoe IS NOT NULL" in sql
    assert "SUM(CAST(cpoe AS FLOAT64))" in sql
    assert "COUNT(cpoe)" in sql
    assert "PARTITION BY team" in sql
    assert "ORDER BY season, week" in sql
    assert "ROWS BETWEEN 6 PRECEDING AND 1 PRECEDING" in sql
    assert "SAFE_DIVIDE(" in sql
    assert "team_qb_cpoe_cross_season" in sql
    assert "team_qb_cpoe_min_source_season_l6 < season" in sql
    for consumer in ("021_player_week_training.sql", "023_player_week_inference.sql"):
        # The experiment reads this side table itself. Merely implementing the
        # candidate must not alter production model/cache source identity.
        assert "team_week_qb_quality" not in (
            SQL_DIR / "features" / consumer
        ).read_text()


def test_modeled_defense_position_is_exact_player_week():
    modeled = (
        SQL_DIR / "features" / "017_defense_week_allowed.sql"
    ).read_text()
    assert "position_week AS" in modeled
    assert "pm.week = a.week" in modeled
    assert "ANY_VALUE(position HAVING MAX week)" not in modeled


def test_usage_smoothing_position_prior_is_strictly_prior():
    usage = (SQL_DIR / "features" / "014_player_week_usage.sql").read_text()
    assert "position_week AS" in usage
    assert "position_priors AS" in usage
    assert "ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING" in usage
    assert "pp.season = r.season AND pp.week = r.week" in usage
    # A single all-history AVG by position lets early rows borrow later
    # seasons even when the player-level window is correctly lagged.
    assert "AVG(u.rz20_targets) AS prior_rz20_per_game" not in usage
    assert "ANY_VALUE(position HAVING MAX week)" not in usage
    assert "COALESCE(r.position" not in usage


def test_efficiency_does_not_reintroduce_unused_same_week_team_cpoe():
    efficiency = (
        SQL_DIR / "features" / "015_player_week_efficiency.sql"
    ).read_text()
    assert "qb_quality AS" not in efficiency
    assert "team_cpoe" not in efficiency


def test_injury_rows_are_latest_revision_available_at_slate_lock():
    injury = (
        SQL_DIR / "features" / "018_player_week_injury.sql"
    ).read_text()
    assert "slate_locks AS" in injury
    assert "i.date_modified <= l.slate_lock_at" in injury
    assert "`${raw}.injury_snapshots`" in injury
    assert "i.pulled_at <= l.slate_lock_at" in injury
    assert "i.date_modified <= i.pulled_at" in injury
    assert "PARTITION BY gsis_id, season, week" in injury
    assert "ORDER BY injury_information_at DESC" in injury
    assert "injury_source_modified_at" in injury
    assert "injury_snapshot_pulled_at" in injury
    assert "injury_source_kind" in injury


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


def test_own_salary_null_weeks_resolved_before_week_filter():
    """O-12/O-26: dk_job leaves raw salary week NULL on purpose (1.4M 2026 rows).

    The unrepaired SQL filtered ``s.week IS NOT NULL`` straight off the raw
    table, which silently emptied the 2026 salary spine and every prior-usage
    feature downstream. The week must be resolved from the schedule first, and
    the only NULL-week filter must read the resolved relation.
    """
    salary = (SQL_DIR / "features" / "001a_dk_salary_week.sql").read_text()
    source = salary.split("own_source AS (", 1)[1].split("own_resolved AS (", 1)[0]
    resolved = salary.split("own_resolved AS (", 1)[1].split("own_log AS (", 1)[0]
    log = salary.split("own_log AS (", 1)[1].split("norm_ids AS (", 1)[0]
    assert "week IS NOT NULL" not in source
    assert "COALESCE(CAST(s.week AS INT64), g.week) AS week" in resolved
    assert "ON s.week IS NULL" in resolved
    assert "DATE(s.game_start, 'America/New_York')" in resolved
    assert "FROM own_resolved s" in log
    assert "FROM `${raw}.dk_salaries`" not in log
    # A team-date that maps to more than one game or week stays unresolved.
    assert "HAVING COUNT(DISTINCT g.game_id) = 1 AND COUNT(DISTINCT g.week) = 1" in salary
