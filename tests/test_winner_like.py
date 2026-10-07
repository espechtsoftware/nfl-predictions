"""Study 48's winner-likeness score in production and study 48b's order (operator 10-07: "Test tonight, aim for Week 5"):
the frozen model, the lab's features reproduced exactly, the order (descending, ties keep the book order), the inputs
step's point-in-time lags, and the union's hook. The parity fixture is PRIVATE (it carries FP's licensed route share), so
that test runs where the fixture exists and is skipped elsewhere (CI)."""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.inference import winner_like as W

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = Path.home() / "private" / "s48-port" / "PARITY_fixture_2024w10.json"


def test_the_model_is_the_frozen_all53_and_the_features_are_the_labs():
    mu, sd, beta = W.load_model()
    assert len(mu) == len(sd) == 24 and len(beta) == 25
    assert W.FEATURES[6] == "own_rank" and W.FEATURES[-1] == "qb_att_l4"


@pytest.mark.skipif(not FIXTURE.is_file(), reason="the private parity fixture is not on this host")
def test_parity_with_the_labs_fixture_to_1e9():
    j = json.loads(FIXTURE.read_text())
    P = pd.DataFrame.from_dict(j["players"], orient="index")
    A = W.slate_arrays(P.reset_index(drop=True), j["slate"]["top_game_id"])
    at = {p: i for i, p in enumerate(P.index)}
    L = np.array([[at[p] for p in r] for r in j["lineups"]])
    own = np.array([np.nan if v is None else float(v) for v in P["own_rank"]])
    hist = np.array([0.0 if v is None else float(v) for v in P["hist"]])
    F = W.features(L, A, own, hist)
    for c in W.FEATURES:
        assert np.max(np.abs(F[c].to_numpy(float) - np.asarray(j["features"][c], float))) <= 1e-9, c
    assert np.max(np.abs(W.score(F.to_numpy(float), W.load_model()) - np.asarray(j["scores_all53"]))) <= 1e-9


def test_order_is_descending_and_ties_keep_the_book_order():
    assert W.order_by_score([0.1, 0.5, 0.5, -1.0, 0.3]) == [1, 2, 4, 0, 3]


def _players():
    rows = []
    for i, (team, opp, game) in enumerate((("A", "B", "g1"), ("B", "A", "g1"), ("C", "D", "g2"), ("D", "C", "g2"))):
        for pos in ("QB", "RB", "RB", "WR", "WR", "WR", "TE", "DST"):
            k = len(rows)
            rows.append({"id": f"p{k}", "pos": pos, "team": team, "opp": opp, "game_id": game, "salary": 5000 + 100 * k,
                         "game_total": 50.0 if game == "g1" else 44.0, "implied_team_total": 25.0, "spread": -3.0,
                         "rz20_targets_l4": 1.0, "own_proj": float(k), "td_l4": 1.0, "td_l8": 2.0, "pass_td_l4": 6.0,
                         "att_l4": 120.0})
    return pd.DataFrame(rows).set_index("id")


def test_score_book_reads_projected_ownership_ranks_and_refuses_unknown_players():
    P = _players()
    rows = [["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p9", "p7"], ["p16", "p17", "p18", "p19", "p20", "p21", "p22", "p25", "p23"]]
    s, F = W.score_book(rows, P)
    assert len(s) == 2 and F.loc[0, "top_game"] == 8 and F.loc[1, "top_game"] == 0     # g1 is the top-total game
    assert F.loc[1, "own_rank"] > F.loc[0, "own_rank"]                                  # later ids carry more ownership
    assert F.loc[0, "qb_att_l4"] == 120.0 and F.loc[0, "hist"] == 0.0                  # hist is 0 live
    with pytest.raises(ValueError, match="without inputs"):
        W.score_book([["zz"] + rows[0][1:]], P)


def test_inputs_step_maps_fp_ownership_and_prior_game_lags():
    sys.path.insert(0, str(ROOT / "scripts"))
    import winner_like_inputs as WI
    frame = pd.DataFrame({"id": ["a", "b", "c"], "pos": ["QB", "WR", "DST"]})
    own = pd.DataFrame({"id": ["a", "b", "c"], "pred_own": [10.0, 5.0, 1.0]})
    lags = pd.DataFrame({"gsis_id": ["a"], "td_l4": [1], "td_l8": [2], "pass_td_l4": [7], "att_l4": [140]})
    out = WI.build(frame, own, lags).set_index("id")
    assert out.loc["a", "own_proj"] == 10.0 and out.loc["a", "att_l4"] == 140 and out.loc["b", "td_l8"] == 0.0
    assert "week < @week" in WI.LAG_SQL and "week <= 18" in WI.LAG_SQL and "SUM(IF(rn <= 4, att, 0))" in WI.LAG_SQL


def test_the_union_hook_reorders_the_main_book_only(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import union_reselect as ur
    P = _players().reset_index()
    rosters = [["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p9", "p7"], ["p16", "p17", "p18", "p19", "p20", "p21", "p22", "p25", "p23"],
               ["p8", "p9", "p10", "p11", "p12", "p13", "p14", "p1", "p15"]]
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "inp.csv"
        P[["id", "own_proj", "td_l4", "td_l8", "pass_td_l4", "att_l4"]].to_csv(f, index=False)
        fr = P.drop(columns=["own_proj", "td_l4", "td_l8", "pass_td_l4", "att_l4"])
        for c in W.FRAME_FACTS:
            if c not in fr.columns:
                fr[c] = 0.0
        book, meta = ur.apply_winner_order([0, 1], rosters, fr, f)
    assert sorted(book) == [0, 1] and meta["order"] in ([0, 1], [1, 0]) and len(meta["scores_in_book_order"]) == 2
    assert meta["model_sha256"].startswith(W.MODEL_SHA256) and meta["hist"].startswith("0")


def test_a_frame_missing_a_model_column_keeps_the_book_order_and_says_why():
    """The reviewer (10-07): never score with a model column silently zeroed -- refuse, and the union keeps its order."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import tempfile
    import union_reselect as ur
    P = _players().reset_index()
    rosters = [["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p9", "p7"], ["p16", "p17", "p18", "p19", "p20", "p21", "p22", "p25", "p23"]]
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "inp.csv"
        P[["id", "own_proj", "td_l4", "td_l8", "pass_td_l4", "att_l4"]].to_csv(f, index=False)
        fr = P.drop(columns=["own_proj", "td_l4", "td_l8", "pass_td_l4", "att_l4"])
        for c in W.FRAME_FACTS:                                   # a frame with every model column ...
            if c not in fr.columns:
                fr[c] = 0.0
        book, meta = ur.winner_order_or_fallback([0, 1], rosters, fr, f)
        assert "not_applied" not in meta
        book, meta = ur.winner_order_or_fallback([0, 1], rosters, fr.drop(columns=["wopr_l4"]), f)   # ... and one without wopr
    assert book == [0, 1] and "wopr_l4" in meta["not_applied"]
