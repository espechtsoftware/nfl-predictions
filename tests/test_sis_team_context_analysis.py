import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import sis_team_context as sis


def _source():
    rows = []
    for week in range(1, 6):
        for team in ("ARI", "ATL"):
            rows.append({
                "season": 2025, "week": week, "team": team,
                "pdef_attempts": 30, "prush_combined_sacks": 2,
                "prush_pressures": week + 2,
                "pdef_epa_per_play": week / 10,
                "pdef_points_saved_per_play": week / 20,
                "prush_points_saved_per_play": week / 30,
                "pass_block_blown_blocks": week,
                "pass_block_snaps": 40,
                "run_block_blown_blocks": week + 1,
                "run_block_snaps": 20,
                "block_points_earned_per_play": week / 40,
            })
    return pd.DataFrame(rows)


def test_strict_prior_context_never_uses_target_week():
    context = sis.build_strict_prior_context(_source())
    row = context[(context.team == "ARI") & (context.week == 3)].iloc[0]
    assert row.sis_source_week_end == 2
    assert row.sis_prior_games == 2
    assert row.sis_def_pdef_epa_l4 == pytest.approx(0.15)
    assert row.sis_off_pass_bb_l4 == pytest.approx((1 / 40 + 2 / 40) / 2)


def test_target_week_mutation_does_not_change_attached_feature():
    source = _source()
    before = sis.build_strict_prior_context(source)
    source.loc[(source.team == "ARI") & (source.week == 3), "pdef_epa_per_play"] = 999
    after = sis.build_strict_prior_context(source)
    key = lambda frame: frame[(frame.team == "ARI") & (frame.week == 3)].iloc[0]
    assert key(before).sis_def_pdef_epa_l4 == key(after).sis_def_pdef_epa_l4


def test_attach_context_requires_both_strict_prior_sides():
    context = sis.build_strict_prior_context(_source())
    panel = pd.DataFrame([{
        "season": 2025, "week": 3, "gsis_id": "p1", "position": "QB",
        "team": "ARI", "opp": "ATL", "actual": 25.0,
        "mean_projection": 18.0, "was_active": True,
    }])
    attached = sis.attach_context(panel, context)
    assert attached.sis_supported.iloc[0]
    assert attached.sis_off_source_week_end.iloc[0] == 2
    assert attached.sis_def_source_week_end.iloc[0] == 2


def test_duplicate_source_key_fails():
    source = pd.concat([_source(), _source().iloc[[0]]], ignore_index=True)
    with pytest.raises(ValueError, match="repeats team-week"):
        sis.build_strict_prior_context(source)


def test_outcome_audit_excludes_inactive_zero_rows():
    rows = pd.DataFrame({
        "sis_supported": [True, True, True],
        "was_active": [True, True, False],
        "position": ["QB", "QB", "QB"],
        "season": [2025, 2025, 2025],
        "week": [3, 4, 4],
        "residual": [1.0, 2.0, -20.0],
        "beat_10": [0.0, 1.0, 0.0],
        "actual_20": [0.0, 1.0, 0.0],
        "actual_30": [0.0, 1.0, 0.0],
        **{
            feature: [1.0, 2.0, 100.0]
            for feature in sis.FEATURES
        },
    })
    report = sis.outcome_audit(rows)
    assert report["rows"] == 2
    assert all(row["rows"] == 2 for row in report["aggregate"][:7])
