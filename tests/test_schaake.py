import numpy as np
import pandas as pd

from nfl_dfs.research.schaake import apply_schaake, apply_schaake_game
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

