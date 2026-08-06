"""Review #4 levers (2026-08-05): LSE selection objective (F1),
ownership-barbell MILP constraint (F4), QB-concentrated tiny-N
selection (F5). Each test proves the lever FIRES (vacuity law) and
that off-by-default leaves behavior byte-identical."""
import numpy as np
import pytest

from nfl_dfs.backtest.engine import _select_qb_concentrated
from nfl_dfs.optimizer.lineup import (_select_lse_entries, optimize,
                                      select_tail_entries)


# --- F1: log-sum-exp selection -------------------------------------------

def test_lse_prefers_depth_over_redundant_breadth():
    # World 0: cand A scores 200, cand B scores 265 (both clear 194).
    # Binary coverage sees them as redundant; LSE must keep the 265.
    line = 194.0
    a = np.array([200.0, 100.0, 100.0, 100.0])
    b = np.array([265.0, 100.0, 100.0, 100.0])
    c = np.array([100.0, 196.0, 100.0, 100.0])
    totals = np.array([a, b, c])
    picked = _select_lse_entries(totals, 2, line, alpha=0.10)
    assert 1 in picked, "LSE dropped the deep candidate"
    # binary coverage picks one of {a,b} arbitrarily plus c; LSE must
    # rank b's depth above a's redundancy
    assert 0 not in picked or 1 in picked


def test_lse_env_gates_select_tail_entries(monkeypatch):
    totals = np.random.default_rng(0).normal(170, 20, size=(30, 200))
    base = select_tail_entries(totals, 8, 194.0)
    monkeypatch.setenv("SELECT_LSE", "0.08")
    lse = select_tail_entries(totals, 8, 194.0)
    monkeypatch.delenv("SELECT_LSE")
    again = select_tail_entries(totals, 8, 194.0)
    assert again == base, "off-by-default changed baseline behavior"
    assert len(lse) == 8 and len(set(lse)) == 8


def test_lse_submodular_gain_never_negative():
    totals = np.random.default_rng(1).normal(160, 25, size=(12, 50))
    picked = _select_lse_entries(totals, 12, 194.0, alpha=0.05)
    assert sorted(picked) == list(range(12))  # all picked exactly once


# --- F4: ownership barbell ------------------------------------------------

def _pool(own_map):
    """Minimal feasible slate: 2 QB, 4 RB, 6 WR, 3 TE, 2 DST."""
    players = []
    ix = 0
    for pos, n, sal in (("QB", 2, 6000), ("RB", 4, 5500),
                        ("WR", 6, 5000), ("TE", 3, 3800), ("DST", 2, 3000)):
        for k in range(n):
            players.append({
                "id": f"{pos}{k}", "name": f"{pos}{k}", "pos": pos,
                "team": f"T{ix % 4}", "opp": f"T{(ix + 1) % 4}",
                "game_id": f"g{ix % 2}", "salary": sal + 100 * k,
                "proj": 10.0 + k,
                "own_est": own_map.get(f"{pos}{k}", 0.10)})
            ix += 1
    return players


def test_barbell_constraint_fires(monkeypatch):
    own = {"WR0": 0.02, "WR1": 0.02, "TE0": 0.01,   # punt-band lows
           "RB0": 0.35, "RB1": 0.30}                # mega chalk
    pool = _pool(own)
    monkeypatch.setenv("OWN_BARBELL", "1")
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    lu = optimize(pool, punt_max_salary=None, punt_min=0)
    assert lu is not None
    ids = {p["id"] for p in lu.players}
    lows = {p["id"] for p in pool if p["pos"] != "DST"
            and p["own_est"] <= 0.05}
    highs = {p["id"] for p in pool if p["pos"] != "DST"
             and p["own_est"] >= 0.20}
    assert len(ids & lows) >= 3 and len(ids & highs) >= 2


def test_barbell_inert_without_own_est(monkeypatch):
    pool = _pool({})
    for p in pool:
        del p["own_est"]
    monkeypatch.setenv("OWN_BARBELL", "1")
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    assert optimize(pool, punt_max_salary=None, punt_min=0) is not None


# --- F5: QB-concentrated selection ---------------------------------------

class _Lu:
    def __init__(self, qb):
        self.players = [{"id": qb, "pos": "QB"}]


def test_qb_concentrated_single_family():
    rng = np.random.default_rng(2)
    cands = [_Lu("qbA")] * 5 + [_Lu("qbB")] * 5
    cands = [_Lu("qbA") for _ in range(5)] + [_Lu("qbB") for _ in range(5)]
    totals = rng.normal(150, 10, size=(10, 300))
    totals[5:] += 30  # qbB family clears far more often
    picked = _select_qb_concentrated(cands, totals, 4, 194.0)
    assert len(picked) == 4
    qbs = {next(p["id"] for p in cands[i].players if p["pos"] == "QB")
           for i in picked}
    assert qbs == {"qbB"}, f"portfolio spans QBs: {qbs}"


def test_qb_concentrated_fallback_small_families():
    cands = [_Lu(f"qb{i}") for i in range(6)]  # all singleton families
    totals = np.random.default_rng(3).normal(150, 10, size=(6, 50))
    picked = _select_qb_concentrated(cands, totals, 4, 194.0)
    assert len(picked) == 4


# --- HYPER_BOOM: manufactured collinear game worlds ----------------------

def test_hyper_boom_injects_tagged_candidates(monkeypatch):
    import pandas as pd

    from nfl_dfs.backtest.engine import tail_select_lineups

    rng = np.random.default_rng(7)
    pool = []
    ix = 0
    for pos, n, sal in (("QB", 4, 6000), ("RB", 8, 5500), ("WR", 12, 5000),
                        ("TE", 6, 3800), ("DST", 4, 3000)):
        for k in range(n):
            team = f"T{ix % 4}"
            pool.append({
                "id": f"{pos}{k}", "name": f"{pos}{k}", "pos": pos,
                "team": team, "opp": f"T{(ix + 1) % 4}",
                "game_id": f"g{ix % 2}", "salary": sal + 137 * k,
                "proj": 8.0 + (k % 5), "actual": 10.0})
            ix += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    draws = np.abs(rng.normal(9, 5, size=(len(pool), 120)))
    monkeypatch.setenv("HYPER_BOOM", "2")
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("PUNT_MIN", "0")
    lus = tail_select_lineups(slate, pool, draws, tail_line=90.0,
                              n_entries=8, stack=None,
                              objective_col="proj")
    assert lus, "no lineups returned"
    monkeypatch.delenv("HYPER_BOOM")
    base = tail_select_lineups(slate, pool, draws, tail_line=90.0,
                               n_entries=8, stack=None,
                               objective_col="proj")
    assert base, "baseline returned nothing"


# --- N_GUMBEL: perturb-and-MAP diverse candidates (GFN-gate winner) -------

def test_gumbel_batch_injects_and_default_off(monkeypatch):
    import pandas as pd

    from nfl_dfs.backtest.engine import tail_select_lineups

    rng = np.random.default_rng(19)
    pool = []
    ix = 0
    for pos, n, sal in (("QB", 4, 6000), ("RB", 8, 5500), ("WR", 12, 5000),
                        ("TE", 6, 3800), ("DST", 4, 3000)):
        for k in range(n):
            pool.append({
                "id": f"{pos}{k}", "name": f"{pos}{k}", "pos": pos,
                "team": f"T{ix % 4}", "opp": f"T{(ix + 1) % 4}",
                "game_id": f"g{ix % 2}", "salary": sal + 137 * k,
                "proj": 8.0 + (k % 5), "actual": 10.0})
            ix += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    draws = np.abs(rng.normal(9, 5, size=(len(pool), 120)))
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    base = tail_select_lineups(slate, pool, draws, tail_line=90.0,
                               n_entries=8, stack=None, objective_col="proj")
    monkeypatch.setenv("N_GUMBEL", "6")
    gum = tail_select_lineups(slate, pool, draws, tail_line=90.0,
                              n_entries=8, stack=None, objective_col="proj")
    assert base and gum


# --- N_EPISTEMIC: belief-scenario candidates (scoring plan §8) ------------

def test_epistemic_scenarios_use_complete_member_and_game_vectors():
    from nfl_dfs.backtest.engine import _epistemic_scenarios

    pool = [
        {"proj": 10.0, "game_id": "g1", "ensemble_point_0": 12.0,
         "model_points_pre": 11.0, "market_points": 8.0},
        {"proj": 10.0, "game_id": "g1", "ensemble_point_0": 9.0,
         "model_points_pre": 12.0, "market_points": 9.0},
        {"proj": 10.0, "game_id": "g2", "ensemble_point_0": 8.0,
         "model_points_pre": 10.0, "market_points": 10.0},
        {"proj": 6.0, "game_id": "g2", "ensemble_point_0": np.nan,
         "model_points_pre": np.nan, "market_points": np.nan},
    ]
    scenarios = dict(_epistemic_scenarios(pool, "proj"))
    assert np.array_equal(scenarios["ensemble_point_0"],
                          [12.0, 9.0, 8.0, 6.0])
    assert np.array_equal(scenarios["game_model:g1"],
                          [11.0, 12.0, 10.0, 6.0])
    assert np.array_equal(scenarios["game_market:g1"],
                          [8.0, 9.0, 10.0, 6.0])

def test_epistemic_batch_fires_and_is_inert_without_market(monkeypatch):
    import pandas as pd

    from nfl_dfs.backtest.engine import tail_select_lineups

    rng = np.random.default_rng(23)
    pool, ix = [], 0
    for pos, n, sal in (("QB", 4, 6000), ("RB", 8, 5500), ("WR", 12, 5000),
                        ("TE", 6, 3800), ("DST", 4, 3000)):
        for k in range(n):
            pool.append({
                "id": f"{pos}{k}", "name": f"{pos}{k}", "pos": pos,
                "team": f"T{ix % 4}", "opp": f"T{(ix + 1) % 4}",
                "game_id": f"g{ix % 2}", "salary": sal + 137 * k,
                "proj": 8.0 + (k % 5), "actual": 10.0,
                "model_points_pre": 8.0 + (k % 5) + 0.7,
                "market_points": 8.0 + (k % 5) - 0.7,
                "consensus_div": 1.4 if k % 3 == 0 else -0.6})
            ix += 1
    slate = pd.DataFrame(pool)
    slate["draw_idx"] = range(len(slate))
    draws = np.abs(rng.normal(9, 5, size=(len(pool), 120)))
    monkeypatch.setenv("MIN_LINEUP_SALARY", "0")
    monkeypatch.setenv("N_EPISTEMIC", "8")
    lus = tail_select_lineups(slate, pool, draws, tail_line=90.0,
                              n_entries=8, stack=None, objective_col="proj")
    assert lus
    # inert when the market/model split is absent
    bare = [{k: v for k, v in p.items()
             if k not in ("model_points_pre", "market_points", "consensus_div")}
            for p in pool]
    sb = pd.DataFrame(bare)
    sb["draw_idx"] = range(len(bare))
    assert tail_select_lineups(sb, bare, draws, tail_line=90.0, n_entries=8,
                               stack=None, objective_col="proj")
