import pandas as pd
import pytest

from nfl_dfs.ingest import fantasy_points_defense_proe as defense_proe
from nfl_dfs.analysis import fantasy_points_defense_proe as diagnostic


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


def test_defense_proe_gate_is_aggregate_tail_first():
    aggregate = {"control_brier_30": 0.02, "treatment_brier_30": 0.019}
    coverage = {2023: 0.95, 2024: 0.90, 2025: 1.0}
    assert diagnostic.defense_proe_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.89
    assert not diagnostic.defense_proe_gate(aggregate, coverage)["passes"]
    coverage[2024] = 0.90
    aggregate["treatment_brier_30"] = 0.021
    assert not diagnostic.defense_proe_gate(aggregate, coverage)["passes"]


def test_run_reads_only_the_frozen_import_so_later_weekly_appends_cannot_trip_provenance(monkeypatch):
    """O-32 amendment 3: the weekly vendor run appends 2026 rows (other run ids) to the table; the frozen diagnostic
    reads the frozen 2022-2025 import only, and its provenance checks stay unchanged."""
    import inspect

    from nfl_dfs.analysis import fantasy_points_defense_proe as A
    from nfl_dfs.ingest.fantasy_points_defense_proe import SOURCE_RUN
    src = inspect.getsource(A.run)
    assert "WHERE source_run_id = @run" in src and 'params={"run": SOURCE_RUN}' in src
    assert SOURCE_RUN == "fantasy-points-defense-proe-2022-2025-v1"
    assert "set(EXPECTED_HASHES.values()) or len(run_ids) != 1" in src          # the checks themselves unchanged
