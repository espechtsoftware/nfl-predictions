from __future__ import annotations

import pandas as pd

from nfl_dfs.research.final_forensic_diagnostics import (
    aggregate_candidate_diagnostics,
    between_arm_variance_diagnostic,
    candidate_slate_diagnostics,
    evt_diagnostic,
    feature_missingness_diagnostics,
    paired_scope_diagnostics,
    player_calibration_diagnostics,
    regime_and_drift_diagnostics,
    route_pool_admission_diagnostics,
    winner_benchmark,
)


def _players() -> pd.DataFrame:
    positions = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    return pd.DataFrame([
        {
            "id": f"p{index}",
            "name": f"Player {index}",
            "pos": positions[index % 9],
            "team": "A" if index % 9 < 7 else "B",
            "opp": "B" if index % 9 < 7 else "A",
            "game_id": "B@A",
            "kickoff_time": "13:00",
            "salary": 5000 + index % 5 * 100,
            "actual": 8.0 + index,
            "mean_projection": 9.0 + index * 0.8,
            "proj_p10": 3.0 + index * 0.8,
            "proj_p90": 18.0 + index * 0.8,
            "proj_std": 5.0,
            "feature_missing": "[]",
            "game_total": 47.0,
            "actual_ownership": 10.0,
        }
        for index in range(89)
    ])


def _candidates() -> pd.DataFrame:
    return pd.DataFrame([
        {
            "players": ",".join(f"p{i}" for i in range(rank, rank + 9)),
            "actual_score": 100.0 + rank,
            "selected": True,
            "selected_rank": rank,
            "cand_ix": rank,
            "p_line": rank / 100,
            "sim_mean": 110 + rank,
            "sim_q90": 140 + rank,
            "sim_q99": 170 + rank,
            "sim_rank_p_line": 80 - rank,
            "salary": 45_000,
            "tag": "base" if rank % 2 else "boom",
        }
        for rank in range(80)
    ] + [{
        "players": ",".join(f"p{i}" for i in range(80, 89)),
        "actual_score": 250.0,
        "selected": False,
        "selected_rank": None,
        "cand_ix": 80,
        "p_line": 0.99,
        "sim_mean": 210,
        "sim_q90": 240,
        "sim_q99": 270,
        "sim_rank_p_line": 0,
        "salary": 45_000,
        "tag": "late",
    }])


def _slate(season: int, week: int, selected: float) -> dict:
    return {
        "season": season,
        "week": week,
        "H": {"actual_score": selected + 20},
        "P": {"actual_score": selected + 15},
        "C": {"actual_score": selected + 5},
        "S": {"actual_score": selected},
        "gaps": {"player_support": 5, "construction": 10, "selection": 5},
    }


def test_candidate_diagnostics_find_unselected_oracle_and_shapes():
    report = candidate_slate_diagnostics(_players(), _candidates())
    assert report["near_miss_frontier"]["candidate_oracle_score"] == 250.0
    assert report["near_miss_frontier"]["roster_changes"] == 1
    assert report["construction_shapes"]["salary"]["rows"] == 80
    assert report["historical_ownership"]["complete_entries"] == 80
    assert report["rank_skill"]["p_line"]["brier_ge194"] is not None
    aggregate = aggregate_candidate_diagnostics([
        {"season": 2025, "week": 1, "diagnostic": report}
    ])
    assert aggregate["candidate_oracle_omitted_slates"] == 1
    assert aggregate["generator_tag_yield"]


def test_player_calibration_has_fixed_strata_and_rank_metrics():
    players = _players()
    players["season"] = 2025
    players["week"] = 1
    report = player_calibration_diagnostics(players)
    assert report["overall"]["rows"] == 89
    assert report["overall"]["normal_crps_from_mean_std"] is not None
    assert "WR" in report["by_position"]
    assert report["slate_relative_rank"][0]["actual_ndcg"] is not None
    missing = feature_missingness_diagnostics(players)
    assert missing["duplicate_player_week_keys"] == 0
    assert any(row["feature"] == "salary" for row in missing["features"])


def test_route_pool_admission_bound_uses_frozen_prior_rule():
    players = _players().iloc[:18].copy()
    players["season"] = 2025
    players["week"] = 1
    players["salary"] = 3_400
    players["fp_route_share_last"] = 0.30
    players.loc[players.id.eq("p9"), ["pos", "fp_route_share_last"]] = ["WR", 0.70]
    candidates = pd.DataFrame([{
        "season": 2025,
        "week": 1,
        "players": ",".join(f"p{i}" for i in range(9)),
    }])
    winners = pd.DataFrame([
        {"season": 2025, "week": 1, "id": "p9", "pos": "WR"},
        {"season": 2025, "week": 1, "id": "p10", "pos": "RB"},
    ])

    report = route_pool_admission_diagnostics(players, candidates, winners)

    assert report["omitted_winner_slots"] == 2
    assert report["omitted_winner_slots_recovered"] == 1
    assert report["frozen_rule"]["route_share_floor"] == 0.60
    assert report["total_absent_players_admitted"] == 1
    assert report["status"] == "outcome_viewed_forensic_bound_only"


def test_regime_and_evt_diagnostics_use_fixed_cuts():
    rows = [_slate(2024, week, 180 + week) for week in range(1, 9)]
    features = []
    for _ in rows:
        frame = _players().iloc[:18].copy()
        frame["game_id"] = [f"g{index % 9}" for index in range(len(frame))]
        features.append(frame)
    regimes = regime_and_drift_diagnostics(rows, features)
    assert regimes["fixed_bins"]["week"][0][2] == "weeks_1_6"
    assert regimes["season_drift"]["2024"]["slates"] == 8
    evt = evt_diagnostic(rows)
    assert evt["slates"] == 8
    assert evt["paired_slate_bootstrap_mean"]["repetitions"] == 4000
    paired = paired_scope_diagnostics({
        "component-107": rows,
        "position-54": [
            _slate(2024, week, 181 + week) for week in range(1, 9)
        ],
        "phase-s-cbwu-54": [
            _slate(2024, week, 183 + week) for week in range(1, 9)
        ],
    })
    assert paired["paired_predeclared_comparisons"][0]["mean_delta"] == 1.0
    assert paired["paired_predeclared_comparisons"][1]["mean_delta"] == 2.0


def test_between_arm_variance_removes_common_slate_effects():
    panels = [
        "20260807-livefaithful-b2-91d596e",
        "20260807-trusted-b0-ef6d31c",
        "20260808-deterministic-baseline-c616390",
        "20260808-e80-k1-c616390",
        "20260808-e80-k3-c616390",
        "20260808-e80-msctl-d99b125",
        "20260808-livefaithful-b3-ee6f433",
        "20260809-e80-k1-ce12-c616390",
        "20260810-lockfix-e80-k1-8677d21",
        "20260810-lockfix-e80-k1-role12union-8677d21",
        "20260810-lockfix-e80-k3-8677d21",
        "20260811-pitclean-e80-k1-a12ab31",
        "20260811-pitclean-e80-k1-role12union-a12ab31",
        "20260811-pitclean-e80-k3-a12ab31",
    ]
    weekly = pd.DataFrame([
        {
            "panel_run_id": panel,
            "season": 2025,
            "week": week,
            "weekly_max": 180.0 + week + panel_index,
            "entries": 80,
        }
        for panel_index, panel in enumerate(panels)
        for week in range(1, 9)
    ])
    report = between_arm_variance_diagnostic(weekly, panel_ids=panels)
    assert report["panel_count"] == 14
    assert report["common_slate_count"] == 8
    assert report["models"]["weekly_max"]["arm_effect_sd"] > 0
    assert len(report["named_historical_panel_contrasts"]) == 6


def test_winner_benchmark_reports_only_identifiable_fields(tmp_path):
    reports = tmp_path / "reports"
    reports.mkdir()
    older = pd.DataFrame([
        {
            "season": 2024, "week": 1, "position": pos, "salary": 5000,
            "ownership_pct": "10%", "fantasy_points": 20,
        }
        for pos in ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"]
    ])
    older.to_csv(reports / "milly-winners-2019-2023-2024.csv", index=False)
    current = pd.DataFrame([
        {
            "week": 1, "player": f"p{i}", "position": pos, "salary": 5000,
            "own_pct": 10, "pts": 20,
        }
        for i, pos in enumerate(["QB", "RB", "RB", "WR", "WR", "WR", "TE", "FLEX", "DST"])
    ])
    current.to_csv(reports / "2025-milly-rosters.csv", index=False)

    report = winner_benchmark(tmp_path)

    assert report["slates"] == 2
    assert report["salary"]["mean"] == 45_000
    assert "places 2-5" in report["limitations"]
