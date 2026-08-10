from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.analysis import fantasy_points_route_share as diagnostic
from nfl_dfs.backtest import engine
from nfl_dfs.ingest import fantasy_points_route as ingest


def _frame(season: int, rows: list[dict]) -> pd.DataFrame:
    values = []
    for rank, supplied in enumerate(rows, start=1):
        row = {
            "Rank": rank,
            "Name": supplied.get("Name", "Test Player"),
            "Team": supplied.get("Team", "BLT"),
            "POS": supplied.get("POS", "WR"),
            "G": supplied.get("G", 1),
            "Season": season,
            **{column: "" for column in ingest.WEEK_COLUMNS},
            "TM RTE %": supplied.get("TM RTE %", 50.0),
        }
        row.update(supplied)
        values.append(row)
    return pd.DataFrame(values, columns=ingest.EXPECTED_COLUMNS)


def _snapshots() -> pd.DataFrame:
    return pd.DataFrame([
        {"season": season, "gsis_id": "00-1", "name": "Test Player",
         "pos": "WR", "team": "BAL"}
        for season in range(2022, 2026)
    ])


def test_route_normalization_is_hash_provenance_and_identity_safe(monkeypatch):
    monkeypatch.setattr(ingest, "EXPECTED_ROWS", {
        season: 1 for season in range(2022, 2026)})
    frames = {
        season: _frame(season, [{"W1": 50.0 + season - 2022}])
        for season in range(2022, 2026)
    }
    hashes = {season: f"hash-{season}" for season in frames}
    rows, audit = ingest.normalize_exports(frames, _snapshots(), hashes)
    assert len(rows) == 4
    assert rows.gsis_id.eq("00-1").all()
    assert rows.canonical_teams.eq("BAL").all()
    assert rows.route_share.tolist() == [0.50, 0.51, 0.52, 0.53]
    assert rows.source_sha256.tolist() == [
        "hash-2022", "hash-2023", "hash-2024", "hash-2025"]
    assert audit["resolved_source_rows"] == 4
    assert audit["ambiguous_source_rows"] == 0


def test_route_normalization_rejects_conflicting_player_week(monkeypatch):
    expected = {season: 1 for season in range(2022, 2026)}
    expected[2022] = 2
    monkeypatch.setattr(ingest, "EXPECTED_ROWS", expected)
    frames = {
        2022: _frame(2022, [{"W1": 50.0}, {"W1": 51.0}]),
        **{
            season: _frame(season, [{"W1": 50.0}])
            for season in range(2023, 2026)
        },
    }
    with pytest.raises(ValueError, match="conflicting Route Share"):
        ingest.normalize_exports(
            frames, _snapshots(), {season: "hash" for season in frames})


def test_strict_prior_route_excludes_same_week_and_marks_cross_season():
    route = pd.DataFrame([
        {"season": 2022, "week": 18, "gsis_id": "p1",
         "route_share": 0.50},
        {"season": 2023, "week": 1, "gsis_id": "p1",
         "route_share": 0.60},
        {"season": 2023, "week": 2, "gsis_id": "p1",
         "route_share": 0.70},
    ])
    targets = pd.DataFrame([
        {"season": 2022, "week": 18, "gsis_id": "p1"},
        {"season": 2023, "week": 1, "gsis_id": "p1"},
        {"season": 2023, "week": 2, "gsis_id": "p1"},
    ])
    out = diagnostic.attach_strict_prior_route(targets, route)
    assert pd.isna(out.loc[0, "fp_route_share_last"])
    assert out.loc[1, "fp_route_share_last"] == pytest.approx(0.50)
    assert out.loc[1, "fp_route_cross_season"] == 1
    assert out.loc[2, "fp_route_share_last"] == pytest.approx(0.60)
    assert out.loc[2, "fp_route_share_l4"] == pytest.approx(0.55)
    assert out.loc[2, "fp_route_share_jump"] == pytest.approx(0.10)
    assert out.loc[2, "fp_route_cross_season"] == 0


def test_route_gate_is_30_point_tail_first_with_coverage_safeguard():
    folds = [
        {"control_brier_30": 0.020, "treatment_brier_30": 0.019},
        {"control_brier_30": 0.022, "treatment_brier_30": 0.0221},
    ]
    aggregate = {
        "control_brier_30": 0.021,
        "treatment_brier_30": 0.0205,
        "control_wr_te_brier_30": 0.018,
        "treatment_wr_te_brier_30": 0.0178,
    }
    gate = diagnostic.route_gate(folds, aggregate, {2024: 0.82, 2025: 0.83})
    assert gate["passes"]
    assert not diagnostic.route_gate(
        folds, aggregate, {2024: 0.79, 2025: 0.83})["passes"]


def test_route_tail_delta_uses_frozen_models_without_target_outcome(
        monkeypatch):
    rows = []
    for season, actual in ((2022, 10.0), (2023, 35.0), (2024, np.nan)):
        rows.append({
            "season": season,
            "week": 2,
            "gsis_id": f"p-{season}",
            "pos": "WR",
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
            "fp_route_source_season": season,
            "fp_route_source_week": 1,
            "fp_route_share_last": 0.75,
            "fp_route_share_l4": 0.70,
            "fp_route_share_jump": 0.05,
            "fp_route_cross_season": 0,
        })

    calls = []

    def fake_fit(train, test, numeric):
        assert train.season.tolist() == [2022, 2023]
        assert test.season.tolist() == [2024]
        assert test.actual.isna().all()
        calls.append(numeric)
        p30 = 0.12 if len(numeric) == len(diagnostic.CONTROL_NUMERIC) else 0.17
        return np.zeros(len(test)), np.full(len(test), 0.2), np.full(len(test), p30)

    monkeypatch.setattr(diagnostic, "_fit_predict", fake_fit)
    out = diagnostic.route_tail_deltas(pd.DataFrame(rows), 2024)
    assert len(calls) == 2
    assert out.route_delta_30.tolist() == pytest.approx([0.05])
    assert out.fp_route_source_week.tolist() == [1]


def test_route_tail_candidates_are_exact_novel_added_budget(monkeypatch):
    pool = [
        {"id": f"p{i}", "proj_tourney": 10.0 + i,
         "route_delta_30": 0.01 * i}
        for i in range(20)
    ]
    source = [SimpleNamespace(ids=frozenset({"source"}))]
    calls = []

    def fake_optimize(scored, **kwargs):
        calls.append(kwargs)
        assert scored[1]["proj_route_tail"] == pytest.approx(11.3)
        assert kwargs["objective_col"] == "proj_route_tail"
        assert kwargs["max_overlap"] == 8
        index = len(calls)
        return SimpleNamespace(
            ids=frozenset({f"route-{index}"}), tag=None)

    monkeypatch.setattr(engine, "optimize", fake_optimize)
    added = engine.route_tail_candidates(
        pool, source, stack=None, locks=set(), env={})
    assert len(added) == 12
    assert all(lineup.tag == "route_tail" for lineup in added)
    assert [len(call["banned_lineups"]) for call in calls] == list(
        range(1, 13))
