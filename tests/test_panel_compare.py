import json

import pandas as pd

from nfl_dfs.research.panel_compare import (
    candidate_mean_parity, directional_gate, high_tail_gate, metrics,
    slate_scores, tail_first_gate)


def _panel(improved_seasons=()):
    rows = []
    for season_ix, season in enumerate((2019, 2021, 2022, 2023, 2024, 2025)):
        weeks = 17 if season == 2019 else 18
        for week in range(1, weeks + 1):
            score = 195.0 if week == 1 else 180.0
            if season in improved_seasons and week == 2:
                score = 195.0
            rows.extend([
                {"season": season, "week": week, "selected": True,
                 "actual_score": score},
                {"season": season, "week": week, "selected": False,
                 "actual_score": score + 1},
            ])
    return pd.DataFrame(rows)


def test_directional_gate_requires_strictly_positive_four_seasons():
    base = slate_scores(_panel())
    good = slate_scores(_panel((2019, 2021, 2022, 2023)))
    gate, seasons = directional_gate(base, good)
    assert gate["passes"]
    assert int((seasons.lift > 0).sum()) == 4
    neutral_gate, _ = directional_gate(base, base.copy())
    assert not neutral_gate["passes"]


def test_high_tail_gate_uses_declared_threshold_and_season_law():
    base = slate_scores(_panel())
    challenger = base.copy()
    for season in (2019, 2021, 2022, 2023):
        row = challenger.season.eq(season) & challenger.week.eq(2)
        challenger.loc[row, "selected_best"] = 205.0
        challenger.loc[row, "oracle"] = 206.0
    gate, seasons = high_tail_gate(base, challenger, threshold=200.0)
    assert gate["passes"]
    assert int((seasons.lift > 0).sum()) == 4
    assert int((seasons.lift < 0).sum()) == 0

    unstable = challenger.copy()
    for season in (2024, 2025):
        row = unstable.season.eq(season) & unstable.week.eq(1)
        unstable.loc[row, "selected_best"] = 170.0
    unstable_gate, unstable_seasons = high_tail_gate(
        base, unstable, threshold=194.0)
    assert int((unstable_seasons.lift < 0).sum()) == 2
    assert not unstable_gate["passes"]


def test_tail_first_gate_uses_aggregate_tail_without_season_veto():
    base = slate_scores(_panel())
    for season in (2021, 2023):
        row = base.season.eq(season) & base.week.eq(1)
        base.loc[row, ["selected_best", "oracle"]] = [205.0, 206.0]
    challenger = base.copy()
    # Three gained seasons and two losing seasons: the old stability law
    # fails, while the newly frozen aggregate-tail utility passes.
    for season in (2019, 2022, 2025):
        row = challenger.season.eq(season) & challenger.week.isin((2, 3))
        challenger.loc[row, ["selected_best", "oracle"]] = [215.0, 216.0]
    for season in (2021, 2023):
        row = challenger.season.eq(season) & challenger.week.eq(1)
        challenger.loc[row, "selected_best"] = 180.0

    old_gate, seasons = high_tail_gate(base, challenger, threshold=200.0)
    new_gate = tail_first_gate(base, challenger)

    assert int((seasons.lift > 0).sum()) == 3
    assert int((seasons.lift < 0).sum()) == 2
    assert not old_gate["passes"]
    assert new_gate["passes"]


def test_tail_first_gate_preserves_210_and_pool_oracle_safeguards():
    base = slate_scores(_panel())
    high = base.season.eq(2024) & base.week.eq(1)
    base.loc[high, ["selected_best", "oracle"]] = [215.0, 216.0]
    challenger = base.copy()
    for season in (2019, 2021):
        row = challenger.season.eq(season) & challenger.week.eq(2)
        challenger.loc[row, ["selected_best", "oracle"]] = [205.0, 206.0]
    challenger.loc[high, "selected_best"] = 205.0
    gate = tail_first_gate(base, challenger)
    assert gate["clear_200_lift_at_least_2"]
    assert not gate["clear_210_not_worse"]
    assert gate["oracle_200_not_worse"]
    assert not gate["passes"]


def test_score_gate_reports_are_json_serializable():
    base = slate_scores(_panel())
    directional, _ = directional_gate(base, base.copy())
    high_tail, _ = high_tail_gate(base, base.copy())
    # Pandas comparisons can return numpy.bool_, which json.dumps rejects.
    # These reports cross a persisted JSON boundary and need native booleans.
    json.dumps({"directional": directional, "high_tail": high_tail})


def test_metrics_reports_all_frozen_thresholds():
    summary = slate_scores(_panel())
    out = metrics(summary)
    assert out["clear_194"] == 6
    assert out["clear_187"] == 6
    assert out["clear_200"] == 0
    assert out["oracle_194"] == 6
    assert out["oracle_187"] == 6
    for threshold in (187, 194, 200, 210, 220, 230, 240):
        assert f"clear_{threshold}" in out
        assert f"oracle_{threshold}" in out


def test_candidate_mean_parity_uses_blended_offense_and_static_dst():
    features = pd.DataFrame([
        {"season": 2025, "week": 1, "id": "qb", "pos": "QB",
         "proj": 10.0, "model_points_pre": 12.0, "market_points": 8.0,
         "mean_projection": 9.8},
        {"season": 2025, "week": 1, "id": "wr", "pos": "WR",
         "proj": 7.0, "model_points_pre": 7.0, "market_points": None,
         "mean_projection": 7.0},
        {"season": 2025, "week": 1, "id": "DST_X", "pos": "DST",
         "proj": 6.0, "model_points_pre": None, "market_points": None,
         "mean_projection": 0.0},
    ])
    candidates = pd.DataFrame([
        {"season": 2025, "week": 1, "players": "qb,wr,DST_X",
         "sim_mean": 22.8},
    ])
    report, failures = candidate_mean_parity(candidates, features)
    assert failures == []
    assert report["passes"]
    assert report["candidate_mean_max_abs_error"] < 1e-9


def test_candidate_mean_parity_fails_unshifted_candidate_worlds():
    features = pd.DataFrame([
        {"season": 2025, "week": 1, "id": "qb", "pos": "QB",
         "proj": 10.0, "model_points_pre": 12.0, "market_points": 8.0,
         "mean_projection": 9.8},
    ])
    candidates = pd.DataFrame([
        {"season": 2025, "week": 1, "players": "qb",
         "sim_mean": 12.0},
    ])
    report, failures = candidate_mean_parity(candidates, features)
    assert not report["passes"]
    assert any("candidate simulated means" in failure
               for failure in failures)
