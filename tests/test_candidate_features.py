"""Candidate aggregates (scoring plan §5.3): deterministic derivation
from the immutable player snapshot, with explicit unavailability."""
import numpy as np
import pandas as pd

from nfl_dfs.research.candidate_features import (FEATURE_DEF_VERSION,
                                                 candidate_aggregates,
                                                 candidate_feature_frame)


def _players():
    return pd.DataFrame([
        # QB + two mates + a bring-back + filler
        dict(id="QB1", pos="QB", team="KC", opp="BUF", game_id="g1",
             salary=7000, proj=20.0, own_est=0.25, consensus_div=1.2,
             market_points=18.8, proj_p10=10.0, proj_p90=32.0),
        dict(id="WR1", pos="WR", team="KC", opp="BUF", game_id="g1",
             salary=8000, proj=18.0, own_est=0.30, consensus_div=-0.8,
             market_points=18.8, proj_p10=6.0, proj_p90=30.0),
        dict(id="TE1", pos="TE", team="KC", opp="BUF", game_id="g1",
             salary=6000, proj=13.0, own_est=0.04, consensus_div=2.0,
             market_points=11.0, proj_p10=4.0, proj_p90=24.0),
        dict(id="WR2", pos="WR", team="BUF", opp="KC", game_id="g1",
             salary=7500, proj=16.0, own_est=0.02, consensus_div=-1.0,
             market_points=17.0, proj_p10=5.0, proj_p90=28.0),
        dict(id="RB1", pos="RB", team="DAL", opp="PHI", game_id="g2",
             salary=6500, proj=14.0, own_est=0.18, consensus_div=0.4,
             market_points=13.6, proj_p10=4.0, proj_p90=26.0),
    ])


def test_aggregates_are_deterministic_and_structural():
    p = _players()
    f = candidate_aggregates(p, ["QB1", "WR1", "TE1", "WR2", "RB1"])
    assert f["feature_def_version"] == FEATURE_DEF_VERSION
    assert f["proj_sum"] == 81.0
    assert f["salary_sum"] == 35000 and f["salary_left"] == 15000
    assert f["stack_mates"] == 2          # WR1 + TE1 with the QB
    assert f["bring_back"] == 1           # WR2 from the opponent
    assert f["max_from_game"] == 4 and f["n_games"] == 2
    assert f["own_n_low"] == 2 and f["own_n_high"] == 2
    assert f["div_abs_sum"] == 5.4
    assert f["div_qb"] == 1.2
    assert f["q_width_sum"] == 111.0   # 22+24+20+23+22
    # recomputation is exact
    assert candidate_aggregates(p, ["QB1", "WR1", "TE1", "WR2", "RB1"]) == f


def test_missing_feature_family_is_nan_not_zero():
    p = _players().drop(columns=["consensus_div", "market_points",
                                 "proj_p10", "proj_p90"])
    f = candidate_aggregates(p, ["QB1", "WR1"])
    for k in ("div_abs_sum", "div_qb", "q_width_sum", "market_covered"):
        assert np.isnan(f[k]), f"{k} silently became {f[k]}"
    assert f["proj_sum"] == 38.0  # available features still computed


def test_feature_frame_keys_candidates():
    p = _players()
    cands = pd.DataFrame([
        dict(slate_run_id="s1", cand_ix=0, players="QB1,WR1,TE1"),
        dict(slate_run_id="s1", cand_ix=1, players="RB1,WR2"),
    ])
    out = candidate_feature_frame(cands, p)
    assert list(out.cand_ix) == [0, 1]
    assert out.n_players.tolist() == [3, 2]
    assert (out.slate_run_id == "s1").all()
