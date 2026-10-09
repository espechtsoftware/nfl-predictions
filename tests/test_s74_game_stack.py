"""Study 74 (union_reselect --mix-top-game-stack G; 84's rule, production's format, 10-08): study 73's games / QB / PC plus
the opponent's top pass catcher (OPC), forced as one TRIPLE on the first G book solves of cell B; drop-and-advance, a game
missing a pass catcher on either side skipped (no backfill), spares never, never with study 73's flag; the receipt block,
printed line, the identity-based reader and checks (the union's, the audit's; vet never bound), and parity with the
harness's row choice on the lab's own term_book. Offline: a stand-in optimizer that honours 2-3-member interaction floors."""
import importlib.util
import sys
from contextlib import contextmanager
from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.inference import mix_shapes as M

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


T73 = _load("t73_helpers", ROOT / "tests" / "test_s73_top_game_qb1.py")     # frame73, the cheap file, 73's verbatim harness
T71 = T73.T71                                                                # the oracle, the fakes, the lab's term_book
frame73, pool_of, team_itt = T73.frame73, T73.pool_of, T73.team_itt


def expected_triples(fr, g):
    return M.top_game_triples(pool_of(fr), dict(T73.GT), team_itt(fr), g)


def _stand_in3(calls):
    """study 71's stand-in, for 2-3-member floors: with a floor, the first tuple (str order) whose members are all
    available plus the best non-QB others; none -> None (infeasible). Without one, the 9 best shifted by the row count."""
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 interaction_floor_weights=None, interaction_floor=None):
        calls.append({"cell": T71._cell_of(stack), "floor": interaction_floor,
                      "tuples": None if interaction_floor_weights is None else dict(interaction_floor_weights)})
        avail = [p for p in pool if not bans or p["id"] not in bans]
        order = sorted(avail, key=lambda p: (-p[objective_col], str(p["id"])))
        off = len(banned_lineups)
        if interaction_floor_weights is not None:
            assert interaction_floor == 1.0 and set(interaction_floor_weights.values()) == {1.0}
            have = {p["id"]: p for p in avail}
            for tup in sorted(interaction_floor_weights, key=str):
                if all(m in have for m in tup):
                    rest = [p for p in order if p["id"] not in tup and p["pos"] != "QB"]
                    return T71.LU([have[m] for m in tup] + [rest[(off + j) % len(rest)] for j in range(9 - len(tup))])
            return None
        return T71.LU([order[(off + j) % len(order)] for j in range(9)]) if len(order) >= 9 else None
    return optimize


def _failing(calls, every=None, oracle=None):
    inner = _stand_in3(calls)
    n = [0]

    def optimize(*args, **kw):
        floored = kw.get("interaction_floor_weights") is not None
        if oracle is not None and oracle.fails(T71._cell_of(kw["stack"]), floored):
            return None
        if every and floored:
            n[0] += 1
            if n[0] % every == 0:
                return None
        return inner(*args, **kw)
    return optimize


def _build(monkeypatch, g, fr=None, every=None, oracle=None, term_rows=0, tmp_path=None, spares=15, qb1=0):
    calls = []
    T71._install(monkeypatch, calls, _failing(calls, every, oracle))
    fr = frame73() if fr is None else fr
    kw = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=spares)
    if g:
        kw["top_game_stack"] = g
    if qb1:
        kw["top_game_qb1"] = qb1
    if term_rows:
        kw.update(term_rows=term_rows, term_bonus=T73._cheap_term(fr, tmp_path))
    rows, cells, meta, sp = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, [3, 3] + [1] * 24, **kw)
    return rows, cells, meta, sp, calls


# ---------------------------------------------------------------- the choice
def test_the_triples_extend_study_73s_pairs_with_the_opponents_top_catcher():
    fr = frame73()
    tri, pairs = expected_triples(fr, 5), T73.expected_pairs(fr, 5)
    assert [(x["game_id"], x["pair"]) for x in tri] == [(x["game_id"], x["pair"]) for x in pairs]   # 73's games, QB, PC
    for x in tri:
        opp = fr[(fr.team == x["qb"]["opp"]) & fr.pos.isin(["WR", "TE"])]
        best = opp.sort_values(["mean_projection", "salary", "id"], ascending=[False, False, True]).iloc[0]
        assert x["opc"]["id"] == best.id and x["triple"] == (x["pair"][0], x["pair"][1], best.id)
        assert x["opc"]["team"] != x["qb"]["team"]


def test_a_side_without_a_catcher_skips_the_game():
    fr = frame73()
    qb_team = expected_triples(fr, 1)[0]["qb"]["team"]
    opp_team = expected_triples(fr, 1)[0]["qb"]["opp"]
    no_opp = fr[~((fr.team == opp_team) & fr.pos.isin(["WR", "TE"]))].reset_index(drop=True)
    assert expected_triples(no_opp, 1)[0]["triple"] is None and expected_triples(no_opp, 1)[0]["pair"] is not None
    no_own = fr[~((fr.team == qb_team) & fr.pos.isin(["WR", "TE"]))].reset_index(drop=True)
    t = expected_triples(no_own, 1)[0]
    assert t["triple"] is None and t["pair"] is None


# ---------------------------------------------------------------- mix_rows
def test_off_is_the_old_call_exactly(monkeypatch):
    a = _build(monkeypatch, 0)
    calls = []
    T71._install(monkeypatch, calls, _stand_in3(calls))
    b = ur.mix_rows(frame73(), set(), 26, 4, 4, 49_000, [3, 3] + [1] * 24, exposure_cap=13, dst_cap=6, fill="rr", spares=15)
    assert a[:4] == b and a[4] == calls and "top_game_stack" not in a[2] and "top_game_qb1" not in a[2]


@pytest.mark.parametrize("g", [5, 3])
def test_the_first_g_b_book_solves_carry_the_triples(monkeypatch, g):
    rows, cells, meta, spares, calls = _build(monkeypatch, g)
    ts = meta["top_game_stack"]
    order = meta["commit_order"]
    b = [j for j, c in enumerate(order) if c == "B"]
    assert [f["commit_index"] for f in ts["forced"]] == b[:g] and all(f["cell"] == "B" for f in ts["forced"])
    assert ts["dropped"] == [] and ts["cells"] == ["B"] and [f["k"] for f in ts["forced"]] == list(range(1, g + 1))
    tri = {x["k"]: x["triple"] for x in expected_triples(frame73(), g)}
    for f in ts["forced"]:
        assert set(tri[f["k"]]) <= set(f["row"]) and frozenset(rows[f["dealt_index"]]) == frozenset(f["row"])
    floored = [c for c in calls if c["floor"] is not None]
    assert len(floored) == g and all(c["cell"] == "B" for c in floored)                  # never a C solve
    assert [list(c["tuples"])[0] for c in floored] == [tri[k] for k in range(1, g + 1)]
    assert all(x.get("opc") for x in ts["games"])
    assert M.top_game_stack_rows({"config": {"union": {"mix": {"mix": meta}}}}) == {frozenset(f["row"]): tri[f["k"]] for f in ts["forced"]}
    line = ur.top_game_stack_line(ts)
    assert line.startswith(f"TOP-GAME STACK (study 74): G {g}; {g} forced on the first {g} B book solves (build ")
    assert "; 0 dropped; 0 skipped (a side without a pass catcher)" in line and len(line.splitlines()) == 1 + g
    assert line.splitlines()[1].count(" + ") == 2


def test_w5_term_block_every_forced_row_is_a_live_row(monkeypatch, tmp_path):
    for g in (5, 3):
        rows, cells, meta, spares, _ = _build(monkeypatch, g, term_rows=8, tmp_path=tmp_path)
        order = meta["commit_order"]
        n_live = sum(1 for c in order if c.startswith("L:"))
        forced = meta["top_game_stack"]["forced"]
        assert len(forced) == g and all(order[f["commit_index"]] == "L:B" and f["commit_index"] < n_live for f in forced)
        assert not {f["dealt_index"] for f in forced} & set(meta["term"]["term_positions"])


def test_an_infeasible_floor_drops_its_game_and_the_next_b_solve_takes_the_next(monkeypatch):
    rows, cells, meta, spares, calls = _build(monkeypatch, 5, every=2)
    ts = meta["top_game_stack"]
    b = [j for j, c in enumerate(meta["commit_order"]) if c == "B"]
    assert [d["k"] for d in ts["dropped"]] == [2, 4] and [f["k"] for f in ts["forced"]] == [1, 3, 5]
    assert sorted([f["commit_index"] for f in ts["forced"]] + [d["commit_index"] for d in ts["dropped"]]) == b[:5]
    line = ur.top_game_stack_line(ts)
    assert "; 2 dropped;" in line and "!!! 2 STUDY-74 GAME(S) DROPPED: g2 g1 (infeasible with the floor); g4 g3" in line


def test_a_skipped_game_never_takes_a_solve(monkeypatch):
    fr = frame73()
    opp_team = expected_triples(fr, 2)[1]["qb"]["opp"]                                    # game 2's opponent side
    fr = fr[~((fr.team == opp_team) & fr.pos.isin(["WR", "TE"]))].reset_index(drop=True)
    rows, cells, meta, spares, calls = _build(monkeypatch, 3, fr=fr)
    ts = meta["top_game_stack"]
    b = [j for j, c in enumerate(meta["commit_order"]) if c == "B"]
    assert ts["games"][1]["skipped"] and ts["dropped"] == [] and [f["k"] for f in ts["forced"]] == [1, 3]
    assert [f["commit_index"] for f in ts["forced"]] == b[:2]                             # no backfill
    assert "; 1 skipped (a side without a pass catcher)" in ur.top_game_stack_line(ts)


def test_spares_are_never_forced(monkeypatch):
    rows, cells, meta, spares, calls = _build(monkeypatch, 15, fr=frame73(15))
    ts = meta["top_game_stack"]
    n_b_book = sum(1 for c in meta["commit_order"] if c == "B")
    assert len(ts["forced"]) == n_b_book < 15 and all(f["commit_index"] < 26 for f in ts["forced"])


def test_never_with_study_73_and_the_other_refusals(monkeypatch):
    T71._install(monkeypatch, [])
    with pytest.raises(ValueError, match="top_game_qb1 3 and top_game_stack 5 together"):
        ur.mix_rows(frame73(), set(), 26, 4, 4, 49_000, [1] * 26, exposure_cap=13, dst_cap=6, fill="rr", top_game_qb1=3, top_game_stack=5)
    for kw, msg in ((dict(fill="group"), "fill rr"), (dict(bring_back_top_wr=("A1",)), "no bring_back_top_wr"),
                    (dict(cover_games=2), "no cover")):
        args = dict(exposure_cap=13, dst_cap=6, fill="rr", top_game_stack=2); args.update(kw)
        with pytest.raises(ValueError, match=f"top_game_stack 2 needs .*{msg}" if msg != "fill rr" else "fill rr"):
            ur.mix_rows(frame73(), set(), 26, 4, 4, 49_000, [1] * 26, **args)
    with pytest.raises(SystemExit, match="TOP-GAME STACK REFUSED: the T-70 frame has no implied_team_total"):
        ur.mix_rows(frame73().drop(columns=["implied_team_total"]), set(), 26, 4, 4, 49_000, [1] * 26, exposure_cap=13,
                    dst_cap=6, fill="rr", top_game_stack=2)
    assert ur.parse_top_game_stack(0, "mix", "mix", "rr", 0, 0, (), 0) == 0
    assert ur.parse_top_game_stack(5, "mix", "mix", "rr", 0, 0, (), 0) == 5
    with pytest.raises(SystemExit, match="--mix-top-game-stack 5 with --mix-top-game-qb1 3"):
        ur.parse_top_game_stack(5, "mix", "mix", "rr", 0, 0, (), 3)
    with pytest.raises(SystemExit, match=r"--mix-top-game-stack 5: .*\(study 74;"):
        ur.parse_top_game_stack(5, "mix", "mix", "group", 0, 0, (), 0)


# ---------------------------------------------------------------- identity checks: union, audit; vet never bound
def test_the_identity_check_binds_forced_stacks_only():
    row = ["q", "w", "o", "a", "b", "c", "d", "e", "f"]
    assert M.top_game_violations(row, {frozenset(row): ("q", "w", "o")}) == []
    lie = {frozenset(row): ("q", "w", "z")}
    assert M.top_game_violations(row, lie) == ["top-game stack missing: z (the forced stack q + w + z)"]
    assert M.top_game_violations(["q", "w", "x", "a", "b", "c", "d", "e", "f"], {frozenset(row): ("q", "w", "o")}) == []
    assert M.top_game_stack_rows({}) == {}


def test_the_audit_and_union_read_both_studies(tmp_path):
    b_row = ["AQB", "AWR1", "BRB1", "CRB0", "DWR0", "CWR2", "DTE", "EWR1", "G_DST"]

    def rec(tri):
        blk = {"g": 1, "games": [{"k": 1, "game_id": "x", "game_total": 50.0, "qb": {"id": tri[0]}, "pc": {"id": tri[1]},
                                  "opc": {"id": tri[2]}}],
               "forced": [{"k": 1, "cell": "B", "commit_index": 1, "row": sorted(b_row)}], "dropped": []}
        return {"config": {"union": {"mix": {"mix": {"top_game_stack": blk}}}}}
    assert "stack_rules" not in T71._audit_run(tmp_path / "ok", b_row, "mix_B", rec(("AQB", "AWR1", "DWR0")))["failed"]
    assert "stack_rules" in T71._audit_run(tmp_path / "lie", b_row, "mix_B", rec(("AQB", "AWR1", "ZWR9")))["failed"]
    text = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert text.count('_tg.update(ms_ts_rows({"config": {"union": {"mix": {"mix": mix_meta}}}}))') == 2
    assert text.count("top_game_stack=tgs_g,") == 2 and text.count("top_game_stack_line(") == 3
    assert "top_game" not in (ROOT / "scripts" / "vet_replace_v4.py").read_text()


# ---------------------------------------------------------------- parity with the harness's row choice
# TEMPORARY (a merge blocker, production 10-08): game_triples_TEMPORARY / game_stack_TEMPORARY TRANSCRIBE 84's rule; they
# are replaced by 84's VERBATIM game_triples, _top_catcher and game_stack (nfl2 experiments/s74_game_stack.py), sha-pinned,
# as soon as the lab pushes them. Study 73's game_order / game_pairs below are 84's VERBATIM frozen text (T73's pins).
def game_triples_TEMPORARY(fr_pool, base, n_games):
    d = fr_pool.assign(_p=np.asarray(base, float), _id=fr_pool["id"].astype(str), _pos=fr_pool.pos.astype(str),
                       _team=fr_pool.team.astype(str), _g=fr_pool.game_id.astype(str),
                       _sal=pd.to_numeric(fr_pool.salary, errors="coerce").fillna(0.0))
    out = []
    for gid, qb, pc in T73.game_pairs(fr_pool, base, n_games):
        team = d.loc[d._id == qb, "_team"].iloc[0]
        opp = sorted(set(d.loc[d._g == gid, "_team"]) - {team})[0]
        oc = d[(d._team == opp) & d._pos.isin(["WR", "TE"])].sort_values(["_p", "_sal", "_id"], ascending=[False, False, True])
        if len(oc):
            out.append((gid, qb, pc, str(oc._id.iloc[0])))
    return out


@contextmanager
def game_stack_TEMPORARY(triples, k_book):
    S24, S18 = T71.S24, T71.S18
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    target = {id(S18.CELLS["B"][1]): "B"}

    class GameStackBuilder(orig_cls):
        forced: list = []
        plain: list = []
        used: list = []

        def solve_with(self, stack, qb_game_max, pair, extra_bans):
            cell = target.get(id(stack))
            j = len(self.prev)
            k = len(type(self).used)
            if cell is None or j >= k_book or k >= len(triples):
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            gid, qb, pc, opc = triples[k]
            type(self).used.append(gid)
            ids = {str(p["id"]) for p in self.recs}
            lu = None
            if qb in ids and pc in ids and opc in ids:
                S24.optimize = partial(orig_opt, interaction_floor_weights={(qb, pc, opc): 1.0}, interaction_floor=1.0)
                try:
                    lu = super().solve_with(stack, qb_game_max, pair, extra_bans)
                finally:
                    S24.optimize = orig_opt
            if lu is not None:
                type(self).forced.append((gid, cell, j))
                return lu
            type(self).plain.append((gid, cell, j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    GameStackBuilder.forced, GameStackBuilder.plain, GameStackBuilder.used = [], [], []
    S24.CapBuilder = GameStackBuilder
    try:
        yield GameStackBuilder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt


def _harness(g, n_term, oracle, fr, k_book=26, k=41):
    triples = game_triples_TEMPORARY(fr, fr.mean_projection.to_numpy(float), g)
    T71.S24.optimize = T71._h_optimize(oracle)
    with game_stack_TEMPORARY(triples, k_book) as TB:
        book, cells, meta = T71.term_book(fr, [0.0] * len(fr), [0.0] * len(fr), (13, 6), [3, 3] + [1] * (k_book - 2), k_book, n_term, k)
        log = list(T71._HCapBuilder.last.log)
    n_live, n_t = sum(meta["live_block"]["cell_rows"].values()), sum(meta["term_block"]["cell_rows"].values())
    tags = ["L"] * n_live + ["T"] * n_t + ["S"] * (len(log) - n_live - n_t)
    return [(t, c, j) for t, (c, j) in zip(tags, log)], list(TB.forced), list(TB.plain), list(TB.used), triples


def _production(monkeypatch, tmp_path, g, n_term, oracle, fr):
    rows, cells, meta, spares, _ = _build(monkeypatch, g, fr=fr, oracle=oracle, term_rows=n_term, tmp_path=tmp_path)
    order = [tuple(c.split(":")) if ":" in c else ("L", c) for c in meta["commit_order"]]
    built = [(t, c, j) for j, (t, c) in enumerate(order)] + [("S", c, len(order) + s) for s, (_, c) in enumerate(spares)]
    ts = meta["top_game_stack"]
    tri = [(x["game_id"], x["qb"]["id"], x["pc"]["id"], x["opc"]["id"]) for x in ts["games"] if not x["skipped"]]
    return (built, [(f["game_id"], f["cell"], f["commit_index"]) for f in ts["forced"]],
            [(d["game_id"], d["cell"], d["commit_index"]) for d in ts["dropped"]], len(rows), tri)


def _opp_no_pc():
    fr = frame73()
    opp = expected_triples(fr, 2)[1]["qb"]["opp"]
    return fr[~((fr.team == opp) & fr.pos.isin(["WR", "TE"]))].reset_index(drop=True)


@pytest.mark.parametrize("g, n_term, oracle_kw, frame", [
    (5, 8, {}, None),                               # W5: the cheap +2 block on 8 rows, the decision's G
    (3, 8, {}, None),
    (5, 8, {"floor_every": 2}, None),               # infeasible floors: dropped, the next B solve takes the next triple
    (5, 8, {"floor_every": 3, "c_ok": 2}, None),    # and C failing: its quota passes to A1
    (5, 0, {"c_ok": 3}, None),                      # no block: the plain round-robin fill
    (5, 8, {}, "opp_no_pc"),                        # an opponent side without a pass catcher: skipped, never a solve
    (15, 8, {}, "wide"),                            # more triples than book B solves: the spares never take one
])
def test_parity_with_the_harness_row_choice(monkeypatch, tmp_path, g, n_term, oracle_kw, frame):
    fr = {None: frame73(), "opp_no_pc": _opp_no_pc(), "wide": frame73(15)}[frame]
    built_h, forced_h, plain_h, used_h, triples_h = _harness(g, n_term, T71._Oracle(**oracle_kw), fr)
    built_p, forced_p, dropped_p, n_book, triples_p = _production(monkeypatch, tmp_path, g, n_term, T71._Oracle(**oracle_kw), fr)
    assert triples_p == triples_h                                                        # the same games and triples
    assert n_book == 26 and built_p == built_h                                           # the same build order, 41 rows
    assert forced_p == forced_h and dropped_p == plain_h                                  # the same (game, cell, j)
    assert all(c == "B" and j < 26 for _, c, j in forced_p + dropped_p)
    if frame == "wide":
        assert len(used_h) == sum(1 for t, c, j in built_h if j < 26 and c == "B") < g
