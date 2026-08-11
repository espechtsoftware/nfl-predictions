import numpy as np
import pandas as pd
import pytest
from types import SimpleNamespace

from nfl_dfs.analysis import fantasy_points_coverage_fit as diagnostic
from nfl_dfs.backtest import engine
from nfl_dfs.ingest import fantasy_points_coverage as coverage_import


def _receiver(season: int, gsis_id: str = "wr-1") -> dict:
    return {
        "season": season,
        "gsis_id": gsis_id,
        "resolution_status": "resolved",
        "overall_routes": 300,
        "overall_tprr": 0.20,
        "overall_yprr": 1.50,
        "overall_fprr": 0.30,
        "man_routes": 100,
        "man_tprr": 0.30,
        "man_yprr": 2.00,
        "man_fprr": 0.40,
        "zone_routes": 200,
        "zone_tprr": 0.10,
        "zone_yprr": 1.00,
        "zone_fprr": 0.20,
        "zone_sep": 0.10,
        **{
            f"cover{shell}_{suffix}": value
            for shell, sep in ((2, 0.20), (3, 0.10), (4, 0.00), (6, -0.10))
            for suffix, value in (("routes", 50), ("sep", sep))
        },
    }


def _defense(season: int, team: str = "BAL") -> dict:
    return {
        "season": season,
        "team": team,
        "def_man_rate": 0.25,
        "def_zone_rate": 0.75,
        "def_cover2_rate": 0.25,
        "def_cover3_rate": 0.25,
        "def_cover4_rate": 0.25,
        "def_cover6_rate": 0.25,
    }


def test_previous_season_coverage_fit_is_opponent_specific_and_leak_free():
    targets = pd.DataFrame([
        {"season": 2024, "week": 1, "gsis_id": "wr-1", "pos": "WR",
         "opp": "BAL"},
    ])
    receivers = pd.DataFrame([_receiver(2023), {
        **_receiver(2024), "overall_tprr": 0.99,
    }])
    defenses = pd.DataFrame([_defense(2023), {
        **_defense(2024), "def_man_rate": 1.0, "def_zone_rate": 0.0,
    }])
    row = diagnostic.attach_previous_season_coverage(
        targets, receivers, defenses).iloc[0]
    assert row.fp_cov_supported
    assert row.fp_cov_receiver_source_season == 2023
    assert row.fp_cov_defense_source_season == 2023
    assert row.fp_cov_matchup_tprr_edge == pytest.approx(-0.05)
    assert row.fp_cov_matchup_yprr_edge == pytest.approx(-0.25)
    assert row.fp_cov_matchup_fprr_edge == pytest.approx(-0.05)
    assert row.fp_cov_matchup_sep_edge == pytest.approx(-0.05)


def test_coverage_support_is_missing_not_zero():
    receiver = _receiver(2023)
    receiver["man_routes"] = 24
    out = diagnostic.attach_previous_season_coverage(
        pd.DataFrame([{
            "season": 2024, "week": 1, "gsis_id": "wr-1", "pos": "WR",
            "opp": "BAL",
        }]),
        pd.DataFrame([receiver]),
        pd.DataFrame([_defense(2023)]),
    )
    assert not out.iloc[0].fp_cov_supported
    assert out[list(diagnostic.COVERAGE_FEATURES)].isna().all().all()


def test_coverage_gate_is_tail_first_with_fold_and_20pt_safeguards():
    folds = [
        {"control_brier_30": 0.020, "treatment_brier_30": 0.019},
        {"control_brier_30": 0.022, "treatment_brier_30": 0.0221},
    ]
    aggregate = {
        "control_brier_30": 0.021,
        "treatment_brier_30": 0.0205,
        "control_brier_20": 0.050,
        "treatment_brier_20": 0.0504,
    }
    assert diagnostic.coverage_gate(
        folds, aggregate, {2024: 0.29, 2025: 0.28})["passes"]
    assert not diagnostic.coverage_gate(
        folds, aggregate, {2024: 0.24, 2025: 0.28})["passes"]
    aggregate["treatment_brier_20"] = 0.051
    assert not diagnostic.coverage_gate(
        folds, aggregate, {2024: 0.29, 2025: 0.28})["passes"]


def test_correlation_report_has_frozen_features_and_complete_bands():
    n = 20
    frame = pd.DataFrame({
        "actual": np.linspace(10, 40, n),
        "mean_projection": np.full(n, 20.0),
        **{
            feature: np.linspace(-1, 1, n)
            for feature in diagnostic.COVERAGE_FEATURES
        },
    })
    rows = diagnostic._correlations(frame, 2024)
    assert {row["feature"] for row in rows} == set(
        diagnostic.COVERAGE_FEATURES)
    assert all(sum(band["rows"] for band in row["quintile_bands"]) == n
               for row in rows)


def test_receiver_idempotency_query_avoids_reserved_hash_alias():
    sql = coverage_import._receiver_identity_query("project.dataset.table")
    assert "AS source_hash" in sql
    assert "DISTINCT source_hash" in sql
    assert ") AS hash\n" not in sql


def test_coverage_tail_delta_uses_frozen_models_without_target_outcome(
        monkeypatch):
    rows = []
    for season, actual in ((2023, 35.0), (2024, np.nan)):
        rows.append({
            "season": season,
            "week": 2,
            "gsis_id": f"p-{season}",
            "pos": "WR",
            "opp": "BAL",
            "actual": actual,
            "mean_projection": 15.0,
            "salary": 5000,
            "target_share_last": 0.20,
            "target_share_jump": 0.01,
            "snap_share_last": 0.80,
            "snap_share_jump": 0.02,
            "team_vacated_target_share": 0.10,
            "depth_rank": 1,
            "games_played_prior": 1,
            "fp_cov_supported": True,
            "fp_cov_receiver_source_season": season - 1,
            "fp_cov_defense_source_season": season - 1,
            **{feature: 0.01 for feature in diagnostic.COVERAGE_FEATURES},
        })

    calls = []

    def fake_fit(train, test, numeric):
        assert train.season.tolist() == [2023]
        assert test.season.tolist() == [2024]
        assert test.actual.isna().all()
        calls.append(numeric)
        p30 = 0.12 if len(numeric) == len(diagnostic.CONTROL_NUMERIC) else 0.17
        return np.zeros(len(test)), np.full(len(test), 0.2), np.full(len(test), p30)

    monkeypatch.setattr(diagnostic, "_fit_predict", fake_fit)
    out = diagnostic.coverage_tail_deltas(pd.DataFrame(rows), 2024)
    assert len(calls) == 2
    assert out.coverage_delta_30.tolist() == pytest.approx([0.05])
    assert out.fp_cov_receiver_source_season.tolist() == [2023]
    assert out.fp_cov_defense_source_season.tolist() == [2023]


def test_coverage_tail_candidates_are_exact_novel_added_budget(monkeypatch):
    pool = [
        {"id": f"p{i}", "proj_tourney": 10.0 + i,
         "coverage_delta_30": 0.01 * i}
        for i in range(20)
    ]
    source = [SimpleNamespace(ids=frozenset({"source"}))]
    calls = []

    def fake_optimize(scored, **kwargs):
        calls.append(kwargs)
        assert scored[1]["proj_coverage_tail"] == pytest.approx(11.3)
        assert kwargs["objective_col"] == "proj_coverage_tail"
        assert kwargs["max_overlap"] == 8
        index = len(calls)
        return SimpleNamespace(
            ids=frozenset({f"coverage-{index}"}), tag=None)

    monkeypatch.setattr(engine, "optimize", fake_optimize)
    added = engine.coverage_tail_candidates(
        pool, source, stack=None, locks=set(), env={})
    assert len(added) == 12
    assert all(lineup.tag == "coverage_tail" for lineup in added)
    assert [len(call["banned_lineups"]) for call in calls] == list(
        range(1, 13))
