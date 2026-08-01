import numpy as np
import pandas as pd

import pytest

from nfl_dfs.backtest.showdown_replay import (
    build_pools, naive_trailing, replay_showdown_season, showdown_draws)


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


def test_sim_mode_entries_and_gate(monkeypatch):
    """SHOWDOWN_SIM=1 routes through correlated-draw construction and
    still produces valid, scored entries; unset leaves the MILP path
    untouched (proven by identical results)."""
    slates = _slates(weeks=(5,))
    proj = _proj(slates)

    monkeypatch.delenv("SHOWDOWN_SIM", raising=False)
    base = replay_showdown_season(slates, proj, n_entries=4, days=("mon",))
    base2 = replay_showdown_season(slates, proj, n_entries=4, days=("mon",))
    pd.testing.assert_frame_equal(base, base2)  # deterministic without gate

    monkeypatch.setenv("SHOWDOWN_SIM", "1")
    monkeypatch.setenv("SHOWDOWN_TAIL_LINE", "80")
    sim = replay_showdown_season(slates, proj, n_entries=4, days=("mon",))
    assert not sim.empty
    assert (sim.best > 0).all()
    assert (sim.capture <= 1.001).all()


def test_showdown_draws_mean_preserving_and_nonnegative():
    pool = [
        {"id": 1, "proj": 15.0, "proj_sd": 8.0},
        {"id": 2, "proj": 5.0, "proj_sd": 4.0},
        {"id": 3, "proj": 0.0, "proj_sd": 0.0},
    ]
    draws = showdown_draws(pool, n_sims=30_000, seed=1)
    assert draws[1].mean() == pytest.approx(15.0, rel=0.05)
    assert draws[2].mean() == pytest.approx(5.0, rel=0.05)
    assert (draws[1] >= 0).all()
    assert (draws[3] == 0).all()


def test_lineup_draw_totals_captain_weighting():
    from nfl_dfs.optimizer.showdown import ShowdownLineup, lineup_draw_totals
    cpt = {"id": 1, "salary": 5000, "proj": 10.0}
    flex = [{"id": i, "salary": 3000, "proj": 5.0} for i in range(2, 7)]
    lu = ShowdownLineup(cpt, flex)
    draws = {i: np.full(4, 10.0) for i in range(1, 7)}
    totals = lineup_draw_totals([lu], draws)
    assert totals.shape == (1, 4)
    np.testing.assert_allclose(totals[0], 1.5 * 10 + 5 * 10)
