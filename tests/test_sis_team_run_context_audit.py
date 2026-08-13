import pandas as pd
import pytest

from nfl_dfs.analysis.sis_team_run_context import (
    FEATURES,
    attach_run_context,
    build_strict_prior_run_context,
)


def _source():
    rows = []
    for week in range(1, 6):
        for team, scale in (("A", 1.0), ("B", 2.0)):
            attempts = 20.0
            rows.append({
                "season": 2025, "week": week, "team": team,
                "rush_attempts": attempts,
                "rush_yards_after_contact": scale * week * 10,
                "rush_broken_tackles": scale * week,
                "rush_missed_tackles": scale * week / 2,
                "rush_hit_at_line": week,
                "rush_stuffs": week / 2,
                "rush_value_attempts": attempts,
                "rush_points_earned": scale * week,
                "rush_epa": scale * week / 2,
                "rush_positive_rate": 0.5,
                "rush_boom_rate": 0.1,
                "rush_bust_rate": 0.2,
                "rdef_attempts": attempts,
                "rdef_yards": scale * week * 20,
                "rdef_yards_after_contact": scale * week * 8,
                "rdef_stuffs": week,
                "rdef_tackles_for_loss": week / 2,
                "rdef_points_saved": scale * week,
                "rdef_epa_per_attempt": scale * week / attempts,
                "rdef_positive_rate": 0.4,
                "rdef_boom_rate": 0.15,
                "rdef_bust_rate": 0.25,
            })
    return pd.DataFrame(rows)


def test_run_context_is_strict_prior_and_volume_weighted():
    source = _source()
    before = build_strict_prior_run_context(source)
    source.loc[(source.team == "A") & (source.week == 3),
               "rush_yards_after_contact"] = 99999
    after = build_strict_prior_run_context(source)
    key = lambda frame: frame[(frame.team == "A") & (frame.week == 3)].iloc[0]
    assert key(before).sis_run_source_week_end == 2
    assert key(before).sis_run_prior_games == 2
    assert key(before).sis_rb_off_yac_per_att_l4 == pytest.approx(0.75)
    assert key(before).sis_rb_off_yac_per_att_l4 == key(after).sis_rb_off_yac_per_att_l4
    assert set(FEATURES).issubset(before.columns)


def test_attach_run_context_uses_offense_and_opponent():
    context = build_strict_prior_run_context(_source())
    panel = pd.DataFrame([{
        "season": 2025, "week": 3, "gsis_id": "rb", "position": "RB",
        "team": "A", "opp": "B", "actual": 30.0, "mean_projection": 15.0,
        "was_active": True, "epa_per_rush_allowed_l6": 0.1,
        "yards_per_carry_l8": 4.5, "stacked_box_l4": 0.2,
        "carry_share_l4": 0.7,
    }])
    got = attach_run_context(panel, context).iloc[0]
    assert got.sis_run_supported
    assert got.sis_rb_off_yac_per_att_l4 == pytest.approx(0.75)
    assert got.sis_rb_def_yards_per_att_l4 == pytest.approx(3.0)
    assert got.residual == 15.0


def test_run_context_rejects_target_duplicates():
    source = _source()
    with pytest.raises(ValueError, match="repeats team-week"):
        build_strict_prior_run_context(pd.concat([source, source.iloc[[0]]]))
