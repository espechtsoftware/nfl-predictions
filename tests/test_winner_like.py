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


# ------------------------------------------------ study 48d: SEL_CELL (lab s48d_winner_select.py d746010, verbatim reference)
def _lab_selections(score, cells, k_book, names):
    from collections import Counter
    n = len(score)
    key = lambda i: (-score[i], i >= k_book, i)                                     # noqa: E731
    book_count = Counter(cells[:k_book])
    cell_sel = {c: sorted([i for i in range(n) if cells[i] == c], key=key)[:book_count.get(c, 0)] for c in names}
    return {c: sorted(v) for c, v in cell_sel.items()}


def _lab_interleaved(by_cell, weights, names, quotas):
    from nfl_dfs.inference.mix_shapes import interleave
    got = [len(by_cell.get(c, [])) for c in names]
    seq = interleave(got, quotas, weights)
    ptr = [0] * len(names); order = []
    for j in seq:
        order.append(by_cell[names[j]][ptr[j]]); ptr[j] += 1
    return order


def test_winner_select_equals_the_labs_sel_cell(monkeypatch):
    """Production's winner_select picks and orders exactly as the lab's selections + interleaved (SEL_CELL), on random
    scores and cells; the chosen book keeps the caps; the rest become the spares."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import union_reselect as ur
    from nfl_dfs.inference.mix_shapes import MIX_CELLS
    names = list(MIX_CELLS); quotas = [MIX_CELLS[c][0] for c in names]
    rng = np.random.default_rng(5)
    weights = [10, 9, 3, 3, 2, 2] + [1] * 20
    for trial in range(20):
        k, n = 26, 41
        cells = list(rng.choice(names, size=n, p=[0.3, 0.14, 0.28, 0.28]))
        while any(cells[:k].count(c) == 0 for c in names):
            cells = list(rng.choice(names, size=n, p=[0.3, 0.14, 0.28, 0.28]))
        scores = rng.normal(size=n).round(2)                                      # rounding makes ties happen
        rows = [[f"r{i}_{j}" for j in range(9)] for i in range(n)]
        monkeypatch.setattr(W, "score_book", lambda rws, players, model=None, _s=scores: (np.asarray(_s[:len(rws)]), None))
        fr = pd.DataFrame({"id": [p for r in rows for p in r], "pos": (["QB"] + ["WR"] * 7 + ["DST"]) * n, "team": "T",
                           "opp": "O", "game_id": "g", "salary": 5000.0, "game_total": 44.0,
                           **{c: 0.0 for c in W.FRAME_FACTS if c != "game_total"}})
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "inp.csv"
            pd.DataFrame({"id": fr.id, "own_proj": 1.0, "td_l4": 0, "td_l8": 0, "pass_td_l4": 0, "att_l4": 0}).to_csv(f, index=False)
            chosen, ccells, spares, meta = ur.winner_select(rows[:k], cells[:k], [(rows[i], cells[i]) for i in range(k, n)], fr, f,
                                                           weights, (13, 6, 5, 9))
        want = _lab_interleaved(_lab_selections(scores, cells, k, names), weights, names, quotas)
        assert meta["chosen_built_index_in_book_order"] == want, trial
        assert chosen == [rows[i] for i in want] and ccells == [cells[i] for i in want]
        assert [ids for ids, _ in spares] == [rows[i] for i in range(n) if i not in set(want)]
        assert sorted(cells[:k]) == sorted(ccells)                               # the shape quotas hold


def test_winner_select_falls_back_without_spares_and_refuses_with_the_order():
    sys.path.insert(0, str(ROOT / "scripts"))
    import union_reselect as ur
    rows, cells, spares, meta = ur.winner_select_or_fallback([["a"] * 9], ["A1"], [], pd.DataFrame(), Path("x"), [1], (13, 6, 5, 4))
    assert "no spares" in meta["not_applied"] and rows == [["a"] * 9]


def test_selected_shares_use_the_chosen_cells_and_the_as_built_ones_are_kept_apart():
    """The reviewer's NOTE 1 (10-07): after a selection the book-level shares describe the book as chosen."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import union_reselect as ur
    sh = ur.selected_entry_shares(["A1", "B", "A1", "C"], [3, 1, 1, 0, 0])
    assert sh["A1"] == 0.8 and sh["B"] == 0.2 and sh["C"] == 0.0 and sh["A2"] == 0.0
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert 'mix_meta["pre_selection"]' in src and '"commit_order", "entry_shares_before_overlap_limit"' in src


def test_the_gate_scores_a_row_as_score_book_does_and_refuses_unknown_players():
    """Study 48e (DRAFT): the gate's one-row score equals score_book on the same frame and inputs."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import tempfile
    import union_reselect as ur
    P = _players().reset_index()
    rows = [["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p9", "p7"], ["p16", "p17", "p18", "p19", "p20", "p21", "p22", "p25", "p23"]]
    with tempfile.TemporaryDirectory() as d:
        f = Path(d) / "inp.csv"
        P[["id", "own_proj", "td_l4", "td_l8", "pass_td_l4", "att_l4"]].to_csv(f, index=False)
        fr = P.drop(columns=["own_proj", "td_l4", "td_l8", "pass_td_l4", "att_l4"])
        for c in W.FRAME_FACTS:
            if c not in fr.columns:
                fr[c] = 0.0
        g = ur.WinnerGate(fr, f, tau=0.0, tries=5)
        inp = pd.read_csv(f, dtype={"id": str}).set_index("id")
        players = fr.set_index("id").join(inp, how="left")
        ref, _ = W.score_book(rows, players)
        assert [round(g.score(r), 12) for r in rows] == [round(float(x), 12) for x in ref]
        with pytest.raises(ValueError, match="without inputs"):
            g.score(["zz"] + rows[0][1:])
        with pytest.raises(ValueError, match="model's columns"):
            ur.WinnerGate(fr.drop(columns=["wopr_l4"]), f, tau=0.0)
        m = g.meta([{"passed": True, "tries": 3}, {"passed": False, "tries": 5}])
    assert m["passed"] == 1 and m["solves"] == 8 and m["tau"] == 0.0 and m["model_sha256"].startswith(W.MODEL_SHA256)


class _FakeGate:
    """Scores a row by a lookup; tau 1: only rows containing 'good' pass."""
    tau, tries, fallback = 1.0, 3, "best"

    def __init__(self):
        self.calls = 0

    def score(self, ids):
        self.calls += 1
        return 1.0 if "good" in ids else -float(self.calls)

    def meta(self, log):
        return {"rows": log}


def test_the_gate_re_solves_with_the_rejected_lineup_banned_and_falls_back_to_the_best_try(monkeypatch):
    sys.path.insert(0, str(ROOT / "scripts"))
    import union_reselect as ur
    seen = []

    class _LU:
        def __init__(self, ids):
            self.players = [{"id": i, "proj": 10.0} for i in ids]

    def fake_optimize(pool, banned_lineups=None, **kw):
        seen.append(len(banned_lineups))
        return _LU([f"x{len(banned_lineups)}"] + [f"y{j}" for j in range(8)])

    import types
    fake = types.ModuleType("nfl2.core.lineup")
    fake.StackRules = lambda **kw: None
    fake.optimize = fake_optimize
    monkeypatch.setitem(sys.modules, "nfl2", types.ModuleType("nfl2"))
    monkeypatch.setitem(sys.modules, "nfl2.core", types.ModuleType("nfl2.core"))
    monkeypatch.setitem(sys.modules, "nfl2.core.lineup", fake)
    monkeypatch.setattr(ur, "frame_players", lambda fr: {f"p{i}": {"id": f"p{i}", "pos": "WR", "proj": 1.0, "game_id": "g"}
                                                          for i in range(3)})
    g = _FakeGate()
    book, cells, meta, spares = ur.mix_rows(pd.DataFrame(), set(), 1, 4, None, 0, [1], portfolio="ws", fill="rr", gate=g)
    assert seen == [0, 1, 2]                                    # each try bans the rejected lineups so far (none passed)
    assert meta["gate"]["rows"][0]["tries"] == 3 and meta["gate"]["rows"][0]["solves"] == 3 and meta["gate"]["rows"][0]["passed"] is False
    assert book[0][0] == "x0" and meta["gate"]["rows"][0]["score"] == -1.0      # the best-scoring try: the first
    with pytest.raises(ValueError, match="fill rr"):
        ur.mix_rows(pd.DataFrame(), set(), 1, 4, None, 0, [1], portfolio="ws", fill="group", gate=g)
