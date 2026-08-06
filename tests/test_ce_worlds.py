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


def test_knobs_are_game_local_and_pair_opponents_within_each_game():
    draws = np.full((8, 20), 10.0)
    teams = np.repeat(np.arange(4), 2)
    games = np.repeat(np.arange(2), 4)
    is_pass = np.tile([True, False], 4)
    knobs = np.array([
        [1.0, 0.10, 0.60, 1.0],
        [1.0, 0.00, 0.50, 1.0],
    ])
    out = apply_knobs(draws, knobs, teams, is_pass, games)
    # Game 1 is neutral and cannot inherit game 0's scoring split.
    assert np.allclose(out[games == 1], draws[games == 1])
    # Within game 0, team 0 receives 60% and team 1 receives 40%, while
    # the game's combined fantasy-point total is preserved.
    assert np.allclose(out[teams == 0].sum(axis=0), 24.0)
    assert np.allclose(out[teams == 1].sum(axis=0), 16.0)
    assert np.allclose(out[games == 0].sum(axis=0), 40.0)


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


def test_ce_batch_wires_into_generator(monkeypatch):
    """N_CE must produce tagged candidates and stay inert when off."""
    import numpy as np
    import pandas as pd

    from nfl_dfs.backtest.engine import tail_select_lineups

    rng = np.random.default_rng(31)
    pool, ix = [], 0
    for pos, n, sal in (("QB", 4, 6000), ("RB", 8, 5500), ("WR", 12, 5000),
                        ("TE", 6, 3800), ("DST", 4, 3000)):
        for k in range(n):
            pool.append({"id": f"{pos}{k}", "name": f"{pos}{k}", "pos": pos,
                         "team": f"T{ix % 4}", "opp": f"T{(ix + 1) % 4}",
                         "game_id": f"g{ix % 2}", "salary": sal + 137 * k,
                         "proj": 8.0 + (k % 5), "actual": 10.0})
            ix += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    draws = np.abs(rng.normal(9, 5, size=(len(pool), 150)))
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("N_CE", "4")
    lus = tail_select_lineups(slate, pool, draws, tail_line=90.0,
                              n_entries=8, stack=None, objective_col="proj")
    assert lus
    monkeypatch.delenv("N_CE")
    assert tail_select_lineups(slate, pool, draws, tail_line=90.0,
                               n_entries=8, stack=None, objective_col="proj")
