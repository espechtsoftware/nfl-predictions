import numpy as np
import pandas as pd

from nfl_dfs.research.schaake import (apply_schaake, apply_schaake_game,
                                      build_game_bank)
from nfl_dfs.research import schaake_diag
from nfl_dfs.research.schaake_diag import realized_dependence_scores


def test_game_shuffle_is_an_exact_marginal_permutation():
    n = 1000
    draws = np.vstack([np.arange(n, dtype=float),
                       np.arange(n, dtype=float) + 10_000])
    templates = pd.DataFrame({
        "QB_a": [0.1, 0.2, 0.3, 0.4],
        "WR1_a": [0.2, 0.3, 0.4, 0.5],
    })
    out = apply_schaake_game(
        draws, pd.Series(["QB", "WR1"]), np.array(["A", "A"]),
        templates, seed=1,
    )
    for before, after in zip(draws, out):
        assert np.array_equal(np.sort(before), np.sort(after))
        assert len(np.unique(after)) == n


def test_legacy_shuffle_is_an_exact_marginal_permutation():
    rng = np.random.default_rng(2)
    draws = rng.normal(size=(2, 401))
    templates = pd.DataFrame({"QB": [0.1, 0.5, 0.9],
                              "WR1": [0.2, 0.6, 0.8]})
    out = apply_schaake(draws, pd.Series(["QB", "WR1"]),
                        pd.Series(["A", "A"]), templates, seed=3)
    assert all(np.array_equal(np.sort(x), np.sort(y))
               for x, y in zip(draws, out))


def test_realized_scores_prefer_matching_dependence():
    rng = np.random.default_rng(4)
    n = 5000
    common = rng.normal(size=n)
    matched = np.vstack([common, common + rng.normal(0, 0.1, n)])
    independent = rng.normal(size=(2, n))
    meta = pd.DataFrame({"game_id": ["g", "g"], "team": ["A", "A"],
                         "role": ["QB", "WR1"]})
    # A jointly high realization should receive a better tail forecast from
    # the positively dependent arm.
    actual = np.array([2.0, 2.0])
    good = realized_dependence_scores(matched, actual, meta)
    bad = realized_dependence_scores(independent, actual, meta)
    assert good["tail_brier"] < bad["tail_brier"]


def test_game_bank_orients_sides_by_implied_total():
    rows = []
    for team, implied, qb in (("ZZZ", 27.0, 30.0), ("AAA", 20.0, 12.0)):
        rows.append({"season": 2024, "week": 1, "game_id": "g",
                     "team": team, "role": "QB", "dk_points": qb,
                     "implied_team_total": implied})
    bank = build_game_bank(pd.DataFrame(rows))
    # ZZZ is alphabetically last but is still the semantic favorite side.
    assert bank.QB_fav.iloc[0] > bank.QB_dog.iloc[0]


def test_whole_season_gate_emits_each_week_and_uses_all_role_pairs(
        monkeypatch, caplog):
    rows = []
    for week in (1, 2):
        for team in ("A", "B"):
            for pos, salary, actual in (("QB", 7000, 20.0),
                                        ("WR", 6500, 16.0),
                                        ("WR", 5200, 11.0)):
                rows.append({"season": 2025, "week": week,
                             "game_id": f"g{week}", "team": team,
                             "position": pos, "salary": salary,
                             "y_dk_points": actual,
                             "game_total": 47.0, "spread": 3.0,
                             "implied_team_total": (25.0 if team == "A"
                                                    else 22.0)})
    frame = pd.DataFrame(rows)
    rng = np.random.default_rng(9)
    draws = rng.normal(15, 5, size=(len(frame), 500))
    bank = pd.DataFrame({
        "season": [2024] * 4, "week": [1, 2, 3, 4],
        "game_id": ["h1", "h2", "h3", "h4"],
        "game_total": [44.0, 46.0, 48.0, 50.0],
        "spread_abs": [2.0, 3.0, 4.0, 5.0],
        "QB_fav": [0.2, 0.4, 0.6, 0.8],
        "WR1_fav": [0.3, 0.5, 0.7, 0.9],
        "WR2_fav": [0.1, 0.4, 0.6, 0.9],
        "QB_dog": [0.1, 0.3, 0.7, 0.9],
        "WR1_dog": [0.2, 0.4, 0.8, 0.9],
        "WR2_dog": [0.1, 0.5, 0.7, 0.8],
    })
    monkeypatch.setattr(schaake_diag, "_BANK", bank)
    monkeypatch.setenv("SCHAAKE_DIAG_STRICT", "1")
    caplog.set_level("INFO")
    report = schaake_diag.log_dependence_ab(frame, draws)
    assert report["weeks"] == 2
    assert report["required_pairs_complete"]
    assert report["marginal_exact"]
    assert all(report["production"]["by_pair"][key]["n"] > 0
               for key in schaake_diag.REQUIRED_PAIR_KEYS)
    assert sum("schaake-week " in r.message for r in caplog.records) == 2


def test_game_seeds_are_distinct_and_image_smoke_passes():
    assert (schaake_diag._stable_game_seed(2025, 1, "g1")
            != schaake_diag._stable_game_seed(2025, 1, "g2"))
    assert schaake_diag.cloud_smoke()["status"] == "PASS"
