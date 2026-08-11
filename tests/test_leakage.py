"""Leakage checker tested on synthetic data where we control the truth."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.features.leakage import (
    assert_dst_actual_universe_reconciled,
    HISTORICAL_ROSTER_GAP_SQL,
    LeakageError,
    assert_first_game_features_null,
    assert_historical_salary_source_reconciled,
    assert_no_leakage,
    assert_route_source_strict_prior,
    assert_salary_universe_reconciled,
    trailing_mean_excluding_current,
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
