"""Cross-entropy rare-world sampler (scoring plan §10)."""
import numpy as np

from nfl_dfs.research.ce_worlds import (KNOBS, apply_knobs, ce_iterate,
                                        sample_knobs)


def test_knobs_respect_bounds():
    rng = np.random.default_rng(0)
    X = sample_knobs(rng, 500)
    for j, (_, lo, hi, _, _) in enumerate(KNOBS):
        assert X[:, j].min() >= lo and X[:, j].max() <= hi


def test_apply_knobs_is_coherent_at_team_level():
    draws = np.full((6, 50), 10.0)
    teams = np.array([0, 0, 0, 1, 1, 1])
    is_pass = np.array([True, True, False, True, True, False])
    out = apply_knobs(draws, np.array([1.2, 0.1, 0.6, 1.0]), teams, is_pass)
    # a whole team moves together, not player-by-player noise
    assert np.allclose(out[0], out[1])
    assert out[0].mean() > out[2].mean()      # pass tilt favours pass game
    assert out[0].mean() > out[3].mean()      # score split favours team 0


def test_ce_finds_a_known_elite_region():
    """Synthetic: worlds score best at high pace. CE must move the
    proposal mean toward it while keeping ESS finite."""
    rng = np.random.default_rng(3)

    def score(k):
        return -abs(k[0] - 1.25) * 100.0

    elites, w, hist = ce_iterate(score, rng, n_per_round=40, rounds=4)
    assert hist[-1]["elite_mean_score"] > hist[0]["all_mean_score"]
    assert hist[-1]["mu"][0] > hist[0]["mu"][0]        # moved toward 1.25
    assert np.isfinite(w).all() and hist[-1]["ess"] > 0
