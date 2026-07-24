import numpy as np
import pandas as pd

from nfl_dfs.graph.build import build_graph, qb_of, team_of, teammates
from nfl_dfs.graph.cascade import project_vacated_usage


def rosters():
    return pd.DataFrame([
        {"gsis_id": "QB1", "name": "Quinn Back", "position": "QB", "team": "MIN"},
        {"gsis_id": "WR1", "name": "Alpha Receiver", "position": "WR", "team": "MIN"},
        {"gsis_id": "WR2", "name": "Beta Receiver", "position": "WR", "team": "MIN"},
        {"gsis_id": "WR3", "name": "Gamma Receiver", "position": "WR", "team": "MIN"},
        {"gsis_id": "TE1", "name": "Tight End", "position": "TE", "team": "MIN"},
        {"gsis_id": "WRX", "name": "Other Team", "position": "WR", "team": "GB"},
    ])


def qb_conn():
    return pd.DataFrame([
        {"qb": "QB1", "wr": "WR1", "team": "MIN", "targets": 60,
         "rz_targets": 12, "air_yards": 700, "tds": 6},
        {"qb": "QB1", "wr": "WR2", "team": "MIN", "targets": 40,
         "rz_targets": 5, "air_yards": 380, "tds": 2},
    ])


def usage_panel(seed=61):
    """WR2's share jumps in the weeks WR1 sat out (weeks 5, 9, 13)."""
    rng = np.random.default_rng(seed)
    rows = []
    out_weeks = {5, 9, 13}
    for week in range(1, 15):
        wr1_out = week in out_weeks
        if not wr1_out:
            rows.append({"gsis_id": "WR1", "season": 2024, "week": week,
                         "total_targets": 9, "rz20_targets": 2,
                         "target_share": rng.normal(0.27, 0.02)})
        rows.append({"gsis_id": "WR2", "season": 2024, "week": week,
                     "total_targets": 6, "rz20_targets": 1,
                     "target_share": rng.normal(0.32 if wr1_out else 0.17, 0.02)})
        rows.append({"gsis_id": "WR3", "season": 2024, "week": week,
                     "total_targets": 3, "rz20_targets": 0,
                     "target_share": rng.normal(0.14 if wr1_out else 0.09, 0.02)})
        rows.append({"gsis_id": "TE1", "season": 2024, "week": week,
                     "total_targets": 4, "rz20_targets": 1,
                     "target_share": rng.normal(0.12, 0.02)})
    return pd.DataFrame(rows)


def injuries():
    return pd.DataFrame(
        [{"gsis_id": "WR1", "season": 2024, "week": w, "game_status": "Out"}
         for w in (5, 9, 13)]
    )


def test_graph_structure():
    G = build_graph(rosters(), qb_conn())
    assert team_of(G, "WR1") == "MIN"
    assert set(teammates(G, "WR1")) == {"WR2", "WR3"}   # same position group only
    assert qb_of(G, "WR1") == "QB1"
    assert "WRX" not in teammates(G, "WR1")             # other team excluded


def test_cascade_uses_absence_history():
    G = build_graph(rosters(), qb_conn())
    out = project_vacated_usage(G, usage_panel(), injuries(), "WR1")
    assert (out.method == "history").all()
    top = out.iloc[0]
    assert top.gsis_id == "WR2"
    # WR2 gained ~15 share points when WR1 sat
    assert top.delta > 0.10
    # WR3 also gains, but less
    wr3 = out[out.gsis_id == "WR3"].iloc[0]
    assert 0.0 < wr3.delta < top.delta


def test_cascade_falls_back_without_history():
    G = build_graph(rosters(), qb_conn())
    thin_injuries = injuries().head(1)  # only one absence: below threshold
    out = project_vacated_usage(G, usage_panel(), thin_injuries, "WR1")
    assert (out.method == "depth_chart").all()
    # Fallback still ranks the higher-usage teammate first
    assert out.iloc[0].gsis_id == "WR2"
    assert (out.delta > 0).all()


def test_cascade_no_candidates():
    lone = pd.DataFrame([{"gsis_id": "K1", "name": "Kicker", "position": "K",
                          "team": "MIN"}])
    G = build_graph(lone, qb_conn().head(0))
    out = project_vacated_usage(G, usage_panel(), injuries(), "K1")
    assert out.empty
