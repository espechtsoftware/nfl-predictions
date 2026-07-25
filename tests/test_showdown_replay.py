import numpy as np
import pandas as pd

from nfl_dfs.backtest.showdown_replay import (
    build_pools, naive_trailing, replay_showdown_season)


def _slates(weeks=(5, 6), seed=8):
    rng = np.random.default_rng(seed)
    rows = []
    for wk in weeks:
        for slate in (f"S{wk}",):
            pid = 0
            for team in ("AAA", "BBB"):
                for pos, n in (("QB", 1), ("RB", 2), ("WR", 3), ("TE", 1),
                               ("K", 1), ("Def", 1)):
                    for i in range(n):
                        rows.append({
                            "season": 2025, "week": wk,
                            "operator_slate_id": slate,
                            "operator_day": "Monday",
                            "game_teams": "AAA@BBB",
                            "sdio_player_id": 1000 + pid,
                            "display_name": f"{pos}{chr(65 + i)} {team}",
                            "position": pos, "team_abbr": team,
                            "salary": int(rng.integers(20, 110)) * 100,
                            "dk_points_actual": float(max(0, rng.normal(10, 6))),
                        })
                        pid += 1
    return pd.DataFrame(rows)


def _proj(slates):
    rows = []
    for r in slates[slates.position.isin(["QB", "RB", "WR", "TE"])].itertuples():
        rows.append({"week": r.week, "name": r.display_name,
                     "position": r.position,
                     "proj_points": r.dk_points_actual + 2.0})
    return pd.DataFrame(rows)


def test_build_pools_sources():
    slates = _slates()
    pools = build_pools(slates, _proj(slates))
    wk6 = pools[pools.week == 6]
    assert (wk6[wk6.position.isin(["QB", "RB", "WR", "TE"])].proj_source == "model").all()
    # K/Def in week 6 fall back to trailing actuals... only 1 prior game
    # (min 2) -> dropped; week-5 K/Def have no prior at all -> dropped
    assert set(pools.proj_source) == {"model"}
    assert (pools[pools.week == 5].position.isin(["QB", "RB", "WR", "TE"])).all()


def test_naive_trailing_strictly_prior():
    df = pd.DataFrame({
        "sdio_player_id": [1, 1, 1], "week": [1, 2, 3],
        "dk_points_actual": [10.0, 20.0, 30.0]})
    t = naive_trailing(df)
    assert t.isna().iloc[0] and t.isna().iloc[1]  # min 2 prior games
    assert t.iloc[2] == 15.0  # mean of weeks 1-2, current week excluded


def test_replay_scores_and_capture():
    slates = _slates(weeks=(5,))
    res = replay_showdown_season(slates, _proj(slates), n_entries=4, days=("mon",))
    assert len(res) == 1
    row = res.iloc[0]
    assert row.optimal >= row.best >= row.median_entry > 0
    assert 0 < row.capture <= 1.0
    # Projections = actuals + constant -> optimizer should capture nearly
    # everything (cap constraints can force small gaps)
    assert row.capture > 0.85
