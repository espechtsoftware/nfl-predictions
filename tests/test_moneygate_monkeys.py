"""The monkey benchmark's building blocks (synthetic; the scoring itself is moneygate_score's validated path)."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("moneygate_monkeys", ROOT / "scripts" / "moneygate_monkeys.py")
M = importlib.util.module_from_spec(spec); spec.loader.exec_module(M)


def test_percentile_is_mid_rank_and_reading_thresholds():
    d = np.array([1, 2, 2, 3])
    assert M.percentile(2, d) == pytest.approx(50.0) and M.percentile(0, d) == 0.0 and M.percentile(9, d) == 100.0
    assert M.reading(50.1) == "beats the monkey" and M.reading(50.0) == "no better than the monkey"
    assert M.reading(24.9) == "WORSE THAN RANDOM" and M.reading(25.0) == "no better than the monkey"


def test_empirical_caps_measure_the_entered_lineups():
    pos = {"a": "QB", "b": "WR", "c": "WR", "D": "DST", "e": "RB"}
    game = {"a": "g1", "b": "g1", "c": "g2", "D": "g2", "e": "g1"}
    caps = M.empirical_caps([["a", "b", "D"], ["a", "c", "D"], ["e", "c", "D"]], pos, game)
    assert caps == {"max_exp": 2, "max_dst": 3, "max_shared": 2, "max_per_game": 2}


def test_m2_rows_respect_every_cap_and_fail_closed():
    pos = {f"p{i}": "WR" for i in range(30)}; game = {f"p{i}": f"g{i % 6}" for i in range(30)}
    pool = [[f"p{(i + j) % 30}" for j in range(3)] for i in range(30)]
    caps = {"max_exp": 2, "max_dst": 1, "max_shared": 1, "max_per_game": 3}
    rows = M.m2_rows(np.random.default_rng(0), pool, 8, caps, pos, game)
    assert len(set(rows)) == 8
    ex = pd.Series([n for r in rows for n in pool[r]]).value_counts()
    assert ex.max() <= 2
    assert all(len(set(pool[a]) & set(pool[b])) <= 1 for i, a in enumerate(rows) for b in rows[i + 1:])
    with pytest.raises(SystemExit):
        M.m2_rows(np.random.default_rng(0), pool, 29, caps, pos, game)


def test_m3_bank_is_legal():
    rng = np.random.default_rng(1)
    rows = []
    for p, n, sal in (("QB", 4, 7000), ("RB", 8, 6000), ("WR", 10, 5500), ("TE", 4, 4500), ("DST", 4, 3000)):
        rows += [{"pos": p, "salary": sal + 100 * i, "game_code": i % 3} for i in range(n)]
    fr = pd.DataFrame(rows)
    bank = M.m3_bank(rng, fr, 200, batch=20000)
    assert bank.shape == (200, 9)
    s = fr.salary.to_numpy()[bank].sum(1)
    assert ((s >= M.SALARY_MIN) & (s <= M.SALARY_MAX)).all()
    assert (np.diff(np.sort(bank, 1), axis=1) != 0).all()
    pos = fr.pos.to_numpy()[bank]
    assert (pos[:, 0] == "QB").all() and (pos[:, 8] == "DST").all()
