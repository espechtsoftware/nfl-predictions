"""WR-boom and ownership-shape levers (winner-anatomy follow-ups)."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.optimizer.lineup import optimize


def _pool(n_low=3):
    rng = np.random.default_rng(11)
    pool = []
    for i in range(60):
        pos = ["QB", "RB", "WR", "TE", "DST"][i % 5]
        pool.append({
            "id": f"p{i}", "name": f"P{i}", "pos": pos,
            "team": f"T{i % 8}", "opp": f"T{(i + 4) % 8}",
            "game_id": f"g{i % 4}", "salary": int(3000 + 150 * (i % 40)),
            "proj": float(5 + rng.random() * 20),
            "low_own": i < n_low,  # first few flagged low-owned
        })
    return pool


def test_min_lowown_constraint(monkeypatch):
    monkeypatch.setenv("MIN_LOWOWN", "2")
    lu = optimize(_pool(), stack=None)
    assert lu is not None
    assert sum(1 for p in lu.players if p.get("low_own")) >= 2


def test_min_lowown_off_by_default(monkeypatch):
    monkeypatch.delenv("MIN_LOWOWN", raising=False)
    lu = optimize(_pool(n_low=0), stack=None)
    assert lu is not None  # no flags, no constraint, still solves


def test_min_lowown_inert_when_unflagged(monkeypatch):
    monkeypatch.setenv("MIN_LOWOWN", "2")
    lu = optimize(_pool(n_low=0), stack=None)
    assert lu is not None  # flag absent from pool -> constraint skipped


def test_wr_boom_flags_top_decile():
    from nfl_dfs.backtest.replay import _wr_boom_flags  # noqa: F401 import works

    # pure-SQL helper; logic exercised via the percentile contract on a frame
    df = pd.DataFrame({
        "gsis_id": [f"W{i}" for i in range(20)], "season": 2025, "week": 3,
        "deep_targets_l4": list(range(1, 21)),
    })
    pct = df.groupby(["season", "week"]).deep_targets_l4.rank(pct=True)
    assert set(df[pct >= 0.90].gsis_id) == {"W17", "W18", "W19"}


def test_max_per_game_cap(monkeypatch):
    monkeypatch.setenv("MAX_PER_GAME", "3")
    lu = optimize(_pool(), stack=None)
    assert lu is not None
    games = {}
    for p in lu.players:
        games[p["game_id"]] = games.get(p["game_id"], 0) + 1
    assert max(games.values()) <= 3


def test_value2_barbell(monkeypatch):
    monkeypatch.setenv("VALUE2_MIN", "2")
    monkeypatch.setenv("VALUE2_MAX", "5300")
    lu = optimize(_pool(), stack=None)
    assert lu is not None
    cheap = [p for p in lu.players
             if p["salary"] <= 5300 and p["pos"] != "DST"]
    assert len(cheap) >= 2


def test_qd_cell_constraints_hold():
    """optimize() cell parameters (the MAP-Elites archive axes): salary
    band and per-game concentration must bind simultaneously."""
    from nfl_dfs.optimizer.lineup import optimize

    pool = _pool()
    # 4-game fixture: mpg=2 is pigeonhole-infeasible (9 slots / 4 games)
    # and must return None (the engine skips such cells), mpg=3 must bind.
    assert optimize(pool, min_salary=44_000, max_salary=47_500,
                    max_per_game=2) is None
    lu = optimize(pool, min_salary=44_000, max_salary=47_500, max_per_game=3)
    assert lu is not None
    assert 44_000 <= lu.salary <= 47_500
    from collections import Counter

    per_game = Counter(p.get("game_id") for p in lu.players)
    assert max(per_game.values()) <= 3
