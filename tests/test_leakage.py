"""Leakage checker tested on synthetic data where we control the truth."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.features.leakage import (
    assert_dst_actual_universe_reconciled,
    assert_upcoming_context_rows_reconciled,
    HISTORICAL_ROSTER_GAP_SQL,
    LeakageError,
    assert_first_game_features_null,
    assert_injury_slate_lock_coverage,
    assert_historical_salary_source_reconciled,
    assert_no_leakage,
    assert_recomputed_features_match,
    assert_route_source_strict_prior,
    assert_salary_universe_reconciled,
    trailing_mean_excluding_current,
    trailing_std_excluding_current,
    team_qb_cpoe_strict_prior,
    USAGE_RECOMPUTED_EXPECTED_SQL,
    USAGE_RECOMPUTED_FEATURES,
    SMOOTHING_PRIOR_K,
    INJURY_EXPECTED_SQL,
    INJURY_LOCK_COVERAGE_SQL,
    VACATED_EXPECTED_SQL,
)


def make_source(n_players=20, n_weeks=10, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        for w in range(1, n_weeks + 1):
            rows.append(
                {"gsis_id": f"00-{p:07d}", "season": 2024, "week": w,
                 "target_share": rng.uniform(0, 0.35)}
            )
    return pd.DataFrame(rows)


def build_correct(source):
    out = source.copy()
    out["target_share_l4"] = trailing_mean_excluding_current(out, "target_share", window=4)
    out["games_played_prior"] = out.groupby(["gsis_id", "season"]).cumcount()
    return out


def build_leaky(source):
    """The classic bug: rolling window includes the current week."""
    out = source.sort_values(["gsis_id", "season", "week"]).copy()
    out["target_share_l4"] = out.groupby(["gsis_id", "season"])["target_share"].transform(
        lambda s: s.rolling(4, min_periods=1).mean()  # no shift(1) — leaks
    )
    out["games_played_prior"] = out.groupby(["gsis_id", "season"]).cumcount()
    return out


def test_reference_excludes_current_week():
    source = make_source(n_players=1, n_weeks=3)
    vals = source.target_share.tolist()
    got = trailing_mean_excluding_current(source, "target_share", window=4)
    assert np.isnan(got.iloc[0])                       # week 1: nothing prior
    assert got.iloc[1] == pytest.approx(vals[0])       # week 2: only week 1
    assert got.iloc[2] == pytest.approx(np.mean(vals[:2]))


def test_team_qb_quality_excludes_current_and_crosses_seasons():
    schedule = pd.DataFrame({
        "team": ["DET"] * 8,
        "season": [2024] * 6 + [2025] * 2,
        "week": [13, 14, 15, 16, 17, 18, 1, 2],
    })
    dropbacks = schedule.copy()
    dropbacks["cpoe"] = [1.0, 2.0, 3.0, 4.0, 5.0, 60.0, 700.0, 8000.0]
    got = team_qb_cpoe_strict_prior(schedule, dropbacks)

    # 2025 Week 1 uses the six 2024 games, including Week 18, but never its
    # own deliberately huge current value.
    week1 = got[(got.season == 2025) & (got.week == 1)].iloc[0]
    assert week1.team_qb_cpoe_l6 == pytest.approx(12.5)
    assert week1.team_qb_cpoe_dropbacks_l6 == 6
    assert week1.team_qb_cpoe_games_l6 == 6
    assert week1.team_qb_cpoe_cross_season == 1

    # Week 2 drops the oldest game and may use Week 1 only because it is now
    # strictly prior. Its own 8000 value remains excluded.
    week2 = got[(got.season == 2025) & (got.week == 2)].iloc[0]
    assert week2.team_qb_cpoe_l6 == pytest.approx((2 + 3 + 4 + 5 + 60 + 700) / 6)
    assert week2.team_qb_cpoe_cross_season == 1


def test_team_qb_quality_future_null_row_preserves_history():
    schedule = pd.DataFrame({
        "team": ["GB"] * 3,
        "season": [2025] * 3,
        "week": [1, 2, 3],
    })
    dropbacks = schedule.copy()
    dropbacks["cpoe"] = [1.0, 2.0, 3.0]
    before = team_qb_cpoe_strict_prior(schedule, dropbacks)
    upcoming = pd.concat([
        schedule,
        pd.DataFrame({"team": ["GB"], "season": [2025], "week": [4]}),
    ], ignore_index=True)
    after = team_qb_cpoe_strict_prior(upcoming, dropbacks)
    pd.testing.assert_frame_equal(before, after.iloc[:len(before)].reset_index(drop=True))
    future = after.iloc[-1]
    assert future.team_qb_cpoe_l6 == pytest.approx(2.0)
    assert future.team_qb_cpoe_dropbacks_l6 == 3
    assert future.team_qb_cpoe_games_l6 == 3
    assert future.team_qb_cpoe_cross_season == 0


def test_route_source_must_be_strictly_prior_across_seasons():
    good = pd.DataFrame([
        {"season": 2026, "week": 2,
         "fp_route_source_season": 2026, "fp_route_source_week": 1},
        {"season": 2026, "week": 1,
         "fp_route_source_season": 2025, "fp_route_source_week": 18},
    ])
    assert_route_source_strict_prior(good)
    bad = good.copy()
    bad.loc[0, "fp_route_source_week"] = 2
    with pytest.raises(LeakageError, match="same/future-week"):
        assert_route_source_strict_prior(bad)


def test_expanding_window():
    source = make_source(n_players=1, n_weeks=6)
    got = trailing_mean_excluding_current(source, "target_share", window=None)
    assert got.iloc[5] == pytest.approx(source.target_share.iloc[:5].mean())


def test_expanding_std_excludes_current_and_matches_sample_std():
    source = pd.DataFrame({
        "gsis_id": ["a"] * 5,
        "season": [2025] * 5,
        "week": [1, 2, 3, 4, 5],
        "dk_points": [10.0, np.nan, 14.0, 18.0, 22.0],
    })
    got = trailing_std_excluding_current(source, "dk_points", window=None)
    assert np.isnan(got.iloc[0])
    assert np.isnan(got.iloc[1])
    assert np.isnan(got.iloc[2])
    assert got.iloc[3] == pytest.approx(np.std([10.0, 14.0], ddof=1))
    assert got.iloc[4] == pytest.approx(np.std([10.0, 14.0, 18.0], ddof=1))


def test_std_leakage_check_rejects_current_week_window():
    source = pd.DataFrame({
        "gsis_id": ["a"] * 5,
        "season": [2025] * 5,
        "week": [1, 2, 3, 4, 5],
        "dk_points": [10.0, 12.0, 14.0, 18.0, 22.0],
    })
    built = source[["gsis_id", "season", "week"]].copy()
    built["dk_points_vol"] = source["dk_points"].expanding().std(ddof=1)
    with pytest.raises(LeakageError, match="rolling window"):
        assert_no_leakage(
            built, source, "dk_points_vol", "dk_points", window=None,
            statistic="std", min_coverage=1.0,
        )


def test_exact_spine_check_rejects_null_support_drift():
    source = pd.DataFrame({
        "gsis_id": ["a"] * 6,
        "season": [2025] * 6,
        "week": [1, 2, 3, 4, 5, 6],
        "separation": [1.0, np.nan, np.nan, np.nan, np.nan, 2.0],
    })
    built = source[["gsis_id", "season", "week"]].copy()
    built["separation_l4"] = trailing_mean_excluding_current(
        source, "separation", window=4)
    # Simulate a transform that incorrectly compresses out the four missing
    # spine rows and carries the stale week-1 observation into week 6.
    built.loc[built.week.eq(6), "separation_l4"] = 1.0
    with pytest.raises(LeakageError, match="NULL support"):
        assert_no_leakage(
            built, source, "separation_l4", "separation", window=4,
            require_null_parity=True,
        )


def test_independent_recomputation_requires_keys_nulls_and_values():
    expected = pd.DataFrame({
        "team": ["DET", "GB"], "season": [2025, 2025], "week": [1, 1],
        "neutral_pass_rate_l6": [0.55, np.nan],
    })
    assert_recomputed_features_match(
        expected.copy(), expected, ["neutral_pass_rate_l6"],
        ("team", "season", "week"),
    )
    wrong_value = expected.copy()
    wrong_value.loc[0, "neutral_pass_rate_l6"] = 0.65
    with pytest.raises(LeakageError, match="source-recomputed rows"):
        assert_recomputed_features_match(
            wrong_value, expected, ["neutral_pass_rate_l6"],
            ("team", "season", "week"),
        )
    missing_key = expected.iloc[:1].copy()
    with pytest.raises(LeakageError, match="keys differ"):
        assert_recomputed_features_match(
            missing_key, expected, ["neutral_pass_rate_l6"],
            ("team", "season", "week"),
        )
    exact_expected = expected.assign(status=["Out", None])
    exact_wrong = exact_expected.copy()
    exact_wrong.loc[0, "status"] = "Questionable"
    with pytest.raises(LeakageError, match="exact source-recomputed"):
        assert_recomputed_features_match(
            exact_wrong, exact_expected, ["neutral_pass_rate_l6"],
            ("team", "season", "week"), exact_cols=("status",),
        )


def test_smoothed_usage_reference_has_two_strictly_prior_levels():
    assert SMOOTHING_PRIOR_K == 4
    assert "PARTITION BY gsis_id, season ORDER BY week" in \
        USAGE_RECOMPUTED_EXPECTED_SQL
    assert "PARTITION BY position ORDER BY season, week" in \
        USAGE_RECOMPUTED_EXPECTED_SQL
    assert USAGE_RECOMPUTED_EXPECTED_SQL.count(
        "ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING") >= 2


def test_usage_reference_covers_active_and_fast_role_fields():
    for field in (
        "target_share_l4", "carry_share_l4", "snap_share_l4", "wopr_l4",
        "rz20_targets_smoothed", "gl3_carries_smoothed",
        "target_share_last", "carry_share_last", "snap_share_last",
        "target_share_jump", "carry_share_jump", "snap_share_jump",
        "target_share_trend", "carry_share_trend",
    ):
        assert field in USAGE_RECOMPUTED_FEATURES
        assert field in USAGE_RECOMPUTED_EXPECTED_SQL


def test_injury_and_vacancy_references_enforce_prelock_sources():
    assert "i.date_modified <= l.slate_lock_at" in INJURY_EXPECTED_SQL
    assert "FROM `{raw}.injury_snapshots`" in INJURY_EXPECTED_SQL
    assert "i.pulled_at <= l.slate_lock_at" in INJURY_EXPECTED_SQL
    assert "i.date_modified <= i.pulled_at" in INJURY_EXPECTED_SQL
    assert "ROW_NUMBER() OVER" in INJURY_EXPECTED_SQL
    assert "ORDER BY injury_information_at DESC" in INJURY_EXPECTED_SQL
    assert "prior.week BETWEEN i.week - 4 AND i.week - 1" in \
        INJURY_EXPECTED_SQL
    assert "u.week <= o.week" in VACATED_EXPECTED_SQL
    assert "i.injury_status = 'Out'" in VACATED_EXPECTED_SQL
    assert "FROM `{features}.player_week_training`" in \
        INJURY_LOCK_COVERAGE_SQL
    assert "i.date_modified <= l.slate_lock_at" in \
        INJURY_LOCK_COVERAGE_SQL
    assert "JOIN `{raw}.injury_snapshots`" in \
        INJURY_LOCK_COVERAGE_SQL
    assert "i.pulled_at <= l.slate_lock_at" in \
        INJURY_LOCK_COVERAGE_SQL


def test_injury_slate_lock_coverage_fails_closed_without_erasing_no_feed_weeks():
    coverage = pd.DataFrame({
        "season": [2024, 2025],
        "week": [18, 1],
        "slate_lock_at": pd.to_datetime([
            "2025-01-05T18:00:00Z", "2025-09-07T17:00:00Z"]),
        "eligible_source_rows": [20, 0],
        "built_rows": [10, 0],
    })
    assert_injury_slate_lock_coverage(coverage)

    missing_lock = coverage.copy()
    missing_lock.loc[0, "slate_lock_at"] = pd.NaT
    with pytest.raises(LeakageError, match="lock coverage"):
        assert_injury_slate_lock_coverage(missing_lock)

    silently_dropped = coverage.copy()
    silently_dropped.loc[0, "built_rows"] = 0
    with pytest.raises(LeakageError, match="lock coverage"):
        assert_injury_slate_lock_coverage(silently_dropped)


def test_correct_build_passes():
    source = make_source()
    built = build_correct(source)
    assert_no_leakage(built, source, "target_share_l4", "target_share", window=4)
    assert_first_game_features_null(built, ["target_share_l4"])


def test_leaky_build_fails():
    source = make_source()
    built = build_leaky(source)
    with pytest.raises(LeakageError):
        assert_no_leakage(built, source, "target_share_l4", "target_share", window=4)


def test_leaky_build_fails_first_game_check():
    source = make_source()
    built = build_leaky(source)
    with pytest.raises(LeakageError):
        assert_first_game_features_null(built, ["target_share_l4"])


def test_unordered_input_handled():
    source = make_source().sample(frac=1, random_state=3)  # shuffle rows
    built = build_correct(source)
    assert_no_leakage(built, source, "target_share_l4", "target_share", window=4)


def test_team_grain_key_col():
    """Defense-style checks: team key instead of gsis_id."""
    source = make_source(n_players=6, n_weeks=10).rename(
        columns={"gsis_id": "team", "target_share": "epa_allowed"}
    )
    built = source.copy()
    built["epa_allowed_l6"] = trailing_mean_excluding_current(
        built, "epa_allowed", window=6, group_cols=("team", "season")
    )
    assert_no_leakage(built, source, "epa_allowed_l6", "epa_allowed",
                      window=6, key_col="team")

    leaky = source.sort_values(["team", "season", "week"]).copy()
    leaky["epa_allowed_l6"] = leaky.groupby(["team", "season"])["epa_allowed"].transform(
        lambda s: s.rolling(6, min_periods=1).mean()
    )
    with pytest.raises(LeakageError):
        assert_no_leakage(leaky, source, "epa_allowed_l6", "epa_allowed",
                          window=6, key_col="team")


def test_first_row_null_generic():
    from nfl_dfs.features.leakage import assert_first_row_features_null

    source = make_source(n_players=3, n_weeks=5).rename(columns={"gsis_id": "team"})
    ok = source.copy()
    ok["f_l6"] = trailing_mean_excluding_current(
        ok, "target_share", window=6, group_cols=("team", "season")
    )
    assert_first_row_features_null(ok, ["f_l6"], ("team", "season"))

    bad = ok.copy()
    bad["f_l6"] = bad["f_l6"].fillna(0.1)
    with pytest.raises(LeakageError):
        assert_first_row_features_null(bad, ["f_l6"], ("team", "season"))


def test_dst_actual_universe_gate_rejects_missing_team_weeks():
    assert_dst_actual_universe_reconciled(pd.DataFrame())
    gaps = pd.DataFrame([
        {"season": 2019, "week": 1, "team": "LV"},
        {"season": 2019, "week": 1, "team": "LAC"},
    ])
    with pytest.raises(LeakageError, match="team_defense_week"):
        assert_dst_actual_universe_reconciled(gaps)


def test_upcoming_context_gate_rejects_missing_exact_week_rows():
    assert_upcoming_context_rows_reconciled(pd.DataFrame())
    gaps = pd.DataFrame([{
        "source_table": "team_week_target_concentration",
        "season": 2026, "week": 1, "team": "DET",
    }])
    with pytest.raises(LeakageError, match="serve candidate features as NULL"):
        assert_upcoming_context_rows_reconciled(gaps)


def test_salary_universe_reconciliation():
    assert_salary_universe_reconciled(pd.DataFrame())
    gap = pd.DataFrame([{
        "gsis_id": "00-0000001", "display_name": "Missing Player",
        "season": 2025, "week": 7, "position": "QB", "team": "DET",
        "salary": 6100,
    }])
    with pytest.raises(LeakageError, match="salary-universe"):
        assert_salary_universe_reconciled(gap)


def test_historical_salary_source_reconciliation():
    assert_historical_salary_source_reconciled(pd.DataFrame())
    gap = pd.DataFrame([{
        "display_name": "Dropped Player", "season": 2015, "week": 3,
        "position": "WR", "team": "BAL", "opponent": "CIN",
        "salary": 4200, "source_dk_points": 18.4,
    }])
    with pytest.raises(LeakageError, match="roster-valid historical"):
        assert_historical_salary_source_reconciled(gap)


def test_historical_source_gate_independently_requires_weekly_roster():
    assert "`{raw}.rosters_weekly`" in HISTORICAL_ROSTER_GAP_SQL
    assert "ir.team = v.team AND ir.gsis_id = i.gsis_id" in HISTORICAL_ROSTER_GAP_SQL
    assert "WHEN 'BLT' THEN 'BAL'" in HISTORICAL_ROSTER_GAP_SQL
    assert "('PHILLY BROWN', 'COREY BROWN')" in HISTORICAL_ROSTER_GAP_SQL
    assert "LEFT JOIN `{features}.dk_salary_week`" in HISTORICAL_ROSTER_GAP_SQL
    assert "season <= 2021" not in HISTORICAL_ROSTER_GAP_SQL
