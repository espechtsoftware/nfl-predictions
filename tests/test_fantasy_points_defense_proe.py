import pandas as pd
import pytest

from nfl_dfs.ingest import fantasy_points_defense_proe as defense_proe


def test_defense_proe_attachment_is_strictly_prior_and_bye_tolerant():
    targets = pd.DataFrame([{
        "season": 2025, "week": 9, "defense": "BAL",
    }])
    weekly = pd.DataFrame([
        {"season": 2025, "week": week, "team": "BAL", "defense_proe": value}
        for week, value in ((5, 0.01), (6, 0.02), (8, 0.04), (9, 0.99))
    ])
    row = defense_proe.attach_prior_l4(targets, weekly).iloc[0]
    assert row.fp_def_proe_supported
    assert row.fp_def_proe_prior_games == 3
    assert row.fp_def_proe_l4 == pytest.approx((0.01 + 0.02 + 0.04) / 3)
    assert row.fp_def_proe_source_week_start == 5
    assert row.fp_def_proe_source_week_end == 8


def test_defense_proe_attachment_does_not_support_two_games():
    targets = pd.DataFrame([{
        "season": 2025, "week": 9, "defense": "BAL",
    }])
    weekly = pd.DataFrame([
        {"season": 2025, "week": week, "team": "BAL", "defense_proe": 0.01}
        for week in (5, 8)
    ])
    row = defense_proe.attach_prior_l4(targets, weekly).iloc[0]
    assert not row.fp_def_proe_supported


def test_defense_proe_blind_audit_has_no_outcome_contract():
    rows = []
    for season in defense_proe.SEASONS:
        for index in range(4):
            row = {
                "season": season,
                "week": index + 5,
                "defense": "BAL",
                "fp_def_proe_l4": index / 100,
                "fp_def_proe_supported": True,
            }
            row.update({
                feature: float(index)
                for feature in defense_proe.EXISTING_DEFENSE_FEATURES
            })
            rows.append(row)
    report = defense_proe.redundancy_audit(pd.DataFrame(rows))
    assert report["outcomes_read"] is False
    assert report["supported_rows"] == 16
    assert report["max_abs_spearman"] == pytest.approx(1.0)
