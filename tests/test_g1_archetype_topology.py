from pathlib import Path

import numpy as np
import pandas as pd

from nfl_dfs.analysis import g1_archetype_topology as g1


ROOT = Path(__file__).parents[1]


def _history() -> pd.DataFrame:
    rows = []
    for season in (2019, 2021, 2022, 2023, 2024):
        for position in g1.POSITIONS:
            for player in range(24):
                for week in range(1, 7):
                    rows.append({
                        "gsis_id": f"{position}-{player}",
                        "position": position,
                        "season": season,
                        "week": week,
                        "dk_points": float(player + week),
                        "was_active": True,
                    })
    rows.append({
        "gsis_id": "future-only", "position": "WR", "season": 2024,
        "week": 18, "dk_points": 99.0, "was_active": True,
    })
    return pd.DataFrame(rows)


def test_walk_forward_archetypes_are_strictly_prior_and_active_only():
    history = _history()
    result = g1.fit_walk_forward_archetypes(history, 2023)
    assert result.source_first_season.unique().tolist() == [2019]
    assert result.source_last_season.unique().tolist() == [2022]
    assert "future-only" not in set(result.gsis_id)
    future_changed = history.copy()
    future_changed.loc[future_changed.season.ge(2023), "dk_points"] = 9999.0
    unchanged = g1.fit_walk_forward_archetypes(future_changed, 2023)
    pd.testing.assert_frame_equal(result, unchanged)
    inactive = history.copy()
    inactive.loc[
        (inactive.gsis_id == "WR-0") & inactive.season.lt(2023), "was_active"
    ] = False
    result = g1.fit_walk_forward_archetypes(inactive, 2023)
    assert "WR-0" not in set(result.gsis_id)


def _pair_frame() -> pd.DataFrame:
    rows = []
    games = (("A", "B"), ("C", "D"))
    positions = ("QB", "RB", "RB", "WR", "WR", "TE", "TE")
    for game_number, (left, right) in enumerate(games):
        game_id = f"2023_01_{left}_{right}"
        for team, opponent in ((left, right), (right, left)):
            for slot, position in enumerate(positions):
                rows.append({
                    "season": 2023, "week": 1,
                    "gsis_id": f"{team}-{slot}", "position": position,
                    "team": team, "opp": opponent, "game_id": game_id,
                    "archetype": f"{position}-tier{slot % 2 + 1}-stable",
                })
    return pd.DataFrame(rows)


def test_pair_book_contains_exact_frozen_classes_and_is_deterministic():
    frame = _pair_frame()
    first = g1.build_pair_book(frame)
    second = g1.build_pair_book(frame)
    pd.testing.assert_frame_equal(first, second)
    assert set(first.relationship) == set(g1.ALL_RELATIONSHIPS)
    assert not first.duplicated([
        "relationship", "source_index", "target_index"]).any()
    cross = first[first.relationship.str.contains("XGAME")]
    for row in cross.itertuples():
        assert frame.iloc[row.source_index].game_id != frame.iloc[row.target_index].game_id


def test_pair_counts_use_equal_effective_simulation_pair_weight():
    pairs = pd.DataFrame({"source_index": [0, 1], "target_index": [1, 2]})
    actual = np.array([True, True, False])
    simulated = np.array([
        [True, False, True, False],
        [True, True, False, False],
        [False, True, False, True],
    ])
    got = g1._counts_for_pairs(pairs, actual, simulated)
    assert got["pairs"] == 2
    assert got["actual_n11"] == 1
    assert got["actual_n10"] == 1
    assert sum(got[name] for name in g1.COUNT_COLUMNS[:4]) == 2
    assert sum(got[name] for name in g1.COUNT_COLUMNS[4:]) == 2


def _relationship(log_gap=-0.5, high=-0.1, supported=True):
    return {
        "supported": supported,
        "log_simulated_to_realized": log_gap,
        "cluster_ci95_low": -0.8,
        "cluster_ci95_high": high,
        "classification": "material-miss",
        "by_season": {
            str(season): {
                "supported": True,
                "log_simulated_to_realized": -0.2,
                "cluster_ci95_low": -0.5,
                "cluster_ci95_high": -0.01,
                "classification": "material-miss",
            }
            for season in g1.EVALUATION_SEASONS
        },
    }


def test_stable_qb_hub_decision_requires_both_relationships_and_edges():
    broad = {"QB_WR": _relationship(), "QB_TE": _relationship()}
    cells = {
        "wr": {
            "relationship": "QB_WR", "supported": True,
            "classification": "material-miss", "log_simulated_to_realized": -0.4,
        },
        "te": {
            "relationship": "QB_TE", "supported": True,
            "classification": "material-miss", "log_simulated_to_realized": -0.4,
        },
    }
    result = g1.stable_qb_hub_decision(cells, broad, True)
    assert result["disposition"] == "stable-qb-hub-confirmed"
    assert result["g2_licensed"]
    cells.pop("te")
    result = g1.stable_qb_hub_decision(cells, broad, True)
    assert result["disposition"] == "dependence-miss-not-stable-qb-hub"
    assert not result["g2_licensed"]


def test_topology_diagnostic_is_deterministic():
    cells = {}
    for index, (source, target) in enumerate((
        ("QB-a", "WR-a"), ("QB-a", "TE-a"),
        ("QB-b", "WR-b"), ("QB-b", "TE-b"),
    )):
        cells[str(index)] = {
            "supported": True,
            "relationship": "QB_WR" if "WR" in target else "QB_TE",
            "source_archetype": source,
            "target_archetype": target,
            "pairs": 200,
            "realized_lift": 2.0 + index,
            "simulated_lift": 1.2 + index / 10,
        }
    assert g1.topology_diagnostics(cells) == g1.topology_diagnostics(cells)


def test_g1_cli_is_registered():
    cli = (ROOT / "src/nfl_dfs/cli.py").read_text(encoding="utf-8")
    launch = (
        ROOT / "scripts/cloud_g1_archetype_topology.sh"
    ).read_text(encoding="utf-8")
    finish = (
        ROOT / "scripts/cloud_finish_g1_archetype_topology.sh"
    ).read_text(encoding="utf-8")
    assert "g1-archetype-topology" in cli
    assert "g0-dependence-runs/20260812-g0-final-served-dependence-v2" in launch
    assert "selected_team_qb.txt" in launch
    assert "selected_active_label.txt" in launch
    assert "selected_sched.txt" in launch
    assert "selected_usage.txt" in launch
    assert "WRITE_" not in launch
    assert "G1_ARCHETYPE_TOPOLOGY_JSON=" in finish
    assert "archetype_labels.csv.gz" in finish
    assert "immutable G1 report already exists" in finish
