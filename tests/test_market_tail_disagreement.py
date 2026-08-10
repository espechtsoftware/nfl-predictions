import numpy as np
import pandas as pd

from nfl_dfs.analysis.market_tail_disagreement import (
    attach_market_tail_edges,
    component_points,
    evaluate_disagreement,
)


def test_component_points_includes_position_bonus():
    got = component_points(
        np.array(["QB", "QB", "RB", "WR"]),
        np.array([299.0, 300.0, 99.0, 100.0]),
    )
    assert np.allclose(got, [11.96, 15.0, 9.9, 13.0])


def _ladder_rows(player, market, commence, snapshot, prices):
    rows = []
    for point, over, under in prices:
        for outcome, price in (("Over", over), ("Under", under)):
            rows.append({
                "season": 2024,
                "week": 1,
                "event_id": player,
                "commence_time": commence,
                "snapshot_ts": snapshot,
                "market": market,
                "player": player,
                "point": point,
                "outcome_name": outcome,
                "price": price,
            })
    return rows


def test_market_edges_use_common_slate_lock_and_primary_market():
    features = pd.DataFrame([
        {
            "season": 2024, "week": 1, "gsis_id": "qb", "name": "A Qb",
            "pos": "QB", "salary": 6000, "mean_projection": 20,
            "proj_p50": 18, "proj_p90": 30, "actual": 25,
        },
        {
            "season": 2024, "week": 1, "gsis_id": "wr", "name": "B Wr",
            "pos": "WR", "salary": 5000, "mean_projection": 14,
            "proj_p50": 12, "proj_p90": 24, "actual": 18,
        },
    ])
    ordinary = [(40.5, -300, 230), (60.5, -110, -110), (80.5, 230, -300)]
    late_changed = [(90.5, -300, 230), (110.5, -110, -110),
                    (130.5, 230, -300)]
    props = pd.DataFrame(
        _ladder_rows(
            "A Qb", "player_pass_yds_alternate", "2024-09-08T17:00:00Z",
            "2024-09-08T15:00:00Z", ordinary,
        )
        + _ladder_rows(
            "B Wr", "player_reception_yds_alternate",
            "2024-09-08T20:00:00Z", "2024-09-03T18:00:00Z", ordinary,
        )
        + _ladder_rows(
            "B Wr", "player_reception_yds_alternate",
            "2024-09-08T20:00:00Z", "2024-09-08T18:00:00Z", late_changed,
        )
        + _ladder_rows(
            "B Wr", "player_rush_yds_alternate",
            "2024-09-08T20:00:00Z", "2024-09-03T18:00:00Z", ordinary,
        )
    )
    out, audit = attach_market_tail_edges(features, props)
    assert len(out) == 2
    assert out.tail_edge.notna().all()
    assert out.loc[out.gsis_id.eq("wr"), "market"].item() == (
        "player_reception_yds_alternate"
    )
    assert audit["cutoffs"][0]["common_slate_lock"] == (
        "2024-09-08T17:00:00+00:00"
    )
    # The post-lock late-game ladder has 90.5 as its minimum. It must not
    # replace the Tuesday ladder whose q50 remains below that value.
    assert out.loc[out.gsis_id.eq("wr"), "q50"].item() < 90.5


def test_evaluation_is_walk_forward_and_fails_small_coverage_only():
    rng = np.random.default_rng(17)
    rows = []
    for season in (2024, 2025):
        for i in range(240):
            edge = rng.normal()
            mean = 14 + rng.normal(0, 2)
            actual = mean + 1.5 * edge + rng.normal(0, 3)
            rows.append({
                "season": season,
                "week": 1 + i % 18,
                "gsis_id": f"{season}-{i}",
                "pos": ("WR", "TE", "RB", "QB")[i % 4],
                "salary": 3000 + 100 * (i % 50),
                "mean_projection": mean,
                "production_upside": 8 + abs(rng.normal()),
                "tail_edge": edge,
                "actual": actual,
            })
    audit = {
        "seasons": [
            {
                "season": season, "slates": 18, "covered_slates": 18,
                "covered_rows": 240, "minimum_covered_rows_per_slate": 10,
            }
            for season in (2024, 2025)
        ]
    }
    report = evaluate_disagreement(pd.DataFrame(rows), audit)
    assert report["train_season"] == 2024
    assert report["test_season"] == 2025
    assert report["training_rows"] == report["heldout_rows"] == 240
    assert not report["gate"]["coverage_passes"]
    assert report["gate"]["positive_separation_aggregate"]
    assert report["disposition"] == "market-tail-mechanism-gate-fails"

