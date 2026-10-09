"""Study 73 (union_reselect --mix-top-game-qb1 G; 84's rule, production's agreed format, 10-08): the games / QB / pass
catcher choice, mix_rows' forced rows (the first G book solves of B / C in build order, drop-and-advance, spares never,
W5's term block), the receipt block and printed line, the refusals, the identity-based reader and checks (the union's,
the audit's; vet never bound), and parity with the harness's row choice on the lab's own term_book (study 71's sha-pinned
copy) and 84's OWN study-73 functions (game_order, game_pairs, top_game_qb1 of nfl2 experiments/s73_topg_qb1.py @
b402cdd, pasted byte for byte, each function's text sha-pinned). Offline: the stand-in optimizer of study 71's tests.""" 
import importlib.util
import json
import sys
import types
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


T71 = _load("t71_helpers", ROOT / "tests" / "test_s71_bring_back_top_wr.py")     # the stand-in, the oracle, term_book
V = _load("vet_replace_v4_s73", ROOT / "scripts" / "vet_replace_v4.py")

# ---------------------------------------------------------------- a 6-game slate (12 teams): QB, RB, WR, WR, TE, DST each
GT = {"g0": 50.0, "g1": 48.5, "g2": 48.5, "g3": 47.0, "g4": 45.0, "g5": 41.0}          # g1 / g2 tie: game id order
ITT = {"T0": 26.0, "T1": 24.0, "T2": 23.0, "T3": 25.5, "T4": 24.0, "T5": 24.0,          # T4 / T5 tie: the QB projection
       "T6": 22.0, "T7": 25.0, "T8": 23.0, "T9": 22.0, "T10": 20.0, "T11": 21.0}
POSITIONS = ("QB", "RB", "WR", "WR", "TE", "DST")


def frame73(n_games: int = 6) -> pd.DataFrame:
    rows, gt, itt = [], dict(GT), dict(ITT)                     # a wider slate adds its own games locally
    for t in range(2 * n_games):
        team, opp, g = f"T{t}", f"T{t ^ 1}", f"g{t // 2:02d}" if n_games > 6 else f"g{t // 2}"
        gt.setdefault(g, 40.0 - t // 2 * 0.5); itt.setdefault(team, 20.0 + t % 5)
        for j, pos in enumerate(POSITIONS):
            pid = f"{team}.{pos}{j}"
            rows.append({"id": pid, "name": pid, "pos": pos, "team": team, "opp": opp, "game_id": g,
                         "salary": 4000 + 100 * ((7 * t + 3 * j) % 40), "mean_projection": 5.0 + ((11 * t + 5 * j) % 23),
                         "game_total": gt[g], "implied_team_total": itt[team]})
    return pd.DataFrame(rows)


def pool_of(fr):
    return list(ur.frame_players(fr).values())


def team_itt(fr):
    return pd.to_numeric(fr.implied_team_total, errors="coerce").groupby(fr.team.astype(str)).median().to_dict()


def expected_pairs(fr, g):
    return M.top_game_pairs(pool_of(fr), dict(GT), team_itt(fr), g)


# ---------------------------------------------------------------- the choice (84's rule)
def test_the_games_qb_and_pass_catcher():
    fr = frame73()
    pr = expected_pairs(fr, 5)
    assert [x["game_id"] for x in pr] == ["g0", "g1", "g2", "g3", "g4"]                 # total desc; the 48.5 tie by game id
    assert [x["qb"]["team"] for x in pr][:2] == ["T0", "T3"]                            # the higher implied team total
    g2 = pr[2]                                                                           # T4 / T5 tie at 24.0
    q4, q5 = (fr[(fr.team == t) & (fr.pos == "QB")].mean_projection.iloc[0] for t in ("T4", "T5"))
    assert g2["qb"]["team"] == ("T4" if q4 >= q5 else "T5")                             # the top QB projection, then team
    fr2 = fr.copy(); fr2.loc[fr2.id == "T5.QB0", "mean_projection"] = q4                 # a full tie: the TEAM code decides
    assert expected_pairs(fr2, 3)[2]["qb"]["team"] == "T4"
    for x in pr:                                                                         # his team's best WR / TE by projection
        team = fr[(fr.team == x["qb"]["team"]) & fr.pos.isin(["WR", "TE"])]
        best = team.sort_values(["mean_projection", "salary", "id"], ascending=[False, False, True]).iloc[0]
        assert x["pc"]["id"] == best.id and x["pair"] == (x["qb"]["id"], best.id)


def test_ties_fall_to_salary_then_id_and_two_qbs_on_a_side():
    fr = frame73()
    i = fr.index[fr.id == "T0.WR3"][0]
    fr.loc[fr.team == "T0", "mean_projection"] = 10.0                                    # every T0 player ties on projection
    fr.loc[fr.id == "T0.WR2", "salary"] = 6000; fr.loc[i, "salary"] = 6000; fr.loc[fr.id == "T0.TE4", "salary"] = 6000
    assert expected_pairs(fr, 1)[0]["pc"]["id"] == "T0.TE4"                              # salary tie -> the id ("TE" < "WR")
    fr.loc[fr.id == "T0.TE4", "salary"] = 5900
    assert expected_pairs(fr, 1)[0]["pc"]["id"] == "T0.WR2"                              # the higher salary first
    backup = fr[fr.id == "T0.QB0"].assign(id="T0.QBb", name="T0.QBb", mean_projection=12.0)
    fr2 = pd.concat([fr, backup], ignore_index=True)
    assert expected_pairs(fr2, 1)[0]["qb"]["id"] == "T0.QBb"                             # same side: the higher projection


def test_a_team_without_pass_catchers_and_the_errors():
    fr = frame73()
    no_pc = fr[~((fr.team == "T0") & fr.pos.isin(["WR", "TE"]))]
    assert expected_pairs(no_pc, 1)[0]["pc"] is None and expected_pairs(no_pc, 1)[0]["pair"] is None
    with pytest.raises(ValueError, match="game g0 has no game_total"):
        M.top_game_pairs(pool_of(fr), {k: v for k, v in GT.items() if k != "g0"}, team_itt(fr), 2)
    with pytest.raises(ValueError, match="team T0 has no implied_team_total"):
        M.top_game_pairs(pool_of(fr), dict(GT), {}, 2)


# ---------------------------------------------------------------- mix_rows
def _build(monkeypatch, g, fr=None, optimize=None, term_rows=0, tmp_path=None, spares=15, calls=None):
    calls = [] if calls is None else calls
    T71._install(monkeypatch, calls, optimize(calls) if optimize else None)
    kw = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=spares)
    if g:
        kw["top_game_qb1"] = g
    if term_rows:
        kw.update(term_rows=term_rows, term_bonus=_cheap_term(fr if fr is not None else frame73(), tmp_path))
    rows, cells, meta, sp = ur.mix_rows(frame73() if fr is None else fr, set(), 26, 4, 4, 49_000, [4, 3, 3, 3] + [2] * 18 + [1] * 4, **kw)
    return rows, cells, meta, sp, calls


def _cheap_term(fr, tmp_path, points=2.0):
    """A cheap-block FILE for the fixture (cheap_block_file.py's columns), read through production's own_bonus and capped."""
    sk = fr[fr.pos != "DST"]
    b = np.where(sk.salary < 5500, points, 0.0)
    f = tmp_path / "cheap2.csv"
    pd.DataFrame({"dk_player_id": range(1, len(sk) + 1), "id": sk.id, "display_name": sk.name, "pos": sk.pos, "team": sk.team,
                  "opp": sk.opp, "pred_own": np.round(b / 0.20, 4), "bonus_points": b}).to_csv(f, index=False)
    raw, _ = ur.own_bonus(f, fr, set(), 0.20, 0.5)
    return {i: min(v, points) for i, v in raw.items()}


def test_off_is_the_old_call_exactly(monkeypatch):
    a = _build(monkeypatch, 0)
    calls = []
    T71._install(monkeypatch, calls)
    b = ur.mix_rows(frame73(), set(), 26, 4, 4, 49_000, [4, 3, 3, 3] + [2] * 18 + [1] * 4, exposure_cap=13, dst_cap=6,
                    fill="rr", spares=15)
    assert a[:4] == b and a[4] == calls and "top_game_qb1" not in a[2]
    assert all(c["floor"] is None for c in calls)


@pytest.mark.parametrize("g", [5, 3])
def test_the_first_g_bc_book_solves_carry_the_pairs(monkeypatch, g):
    rows, cells, meta, spares, calls = _build(monkeypatch, g)
    tg = meta["top_game_qb1"]
    order = meta["commit_order"]
    bc = [j for j, c in enumerate(order) if c in ("B", "C")]
    assert [f["commit_index"] for f in tg["forced"]] == bc[:g] and tg["dropped"] == []
    assert [f["k"] for f in tg["forced"]] == list(range(1, g + 1))
    pairs = {x["k"]: x["pair"] for x in expected_pairs(frame73(), g)}
    for f in tg["forced"]:
        assert set(pairs[f["k"]]) <= set(f["row"]) and f["cell"] == order[f["commit_index"]]
        assert rows[f["dealt_index"]] and frozenset(rows[f["dealt_index"]]) == frozenset(f["row"])   # where it is dealt
    floored = [c for c in calls if c["floor"] is not None]
    assert len(floored) == g and all(len(c["pairs"]) == 1 for c in floored)
    assert [list(c["pairs"])[0] for c in floored] == [pairs[k] for k in range(1, g + 1)]
    assert [x["game_id"] for x in tg["games"]] == [x["game_id"] for x in expected_pairs(frame73(), g)]
    line = ur.top_game_qb1_line(tg)
    assert line.startswith(f"TOP-GAME QB1 (study 73): G {g}; {g} forced on the first {g} B/C book solves (build ")
    assert f"; 0 dropped" in line.splitlines()[0] and len(line.splitlines()) == 1 + g and "!!!" not in line
    assert M.top_game_qb1_rows({"config": {"union": {"mix": {"mix": meta}}}}) == {frozenset(f["row"]): pairs[f["k"]] for f in tg["forced"]}


def test_w5_term_block_every_forced_row_is_a_live_row(monkeypatch, tmp_path):
    """Production's note: with W5's term_rows 8 the first 5 B / C solves all fall in the LIVE block (rr: A1, B, C, A2, ...)."""
    for g in (5, 3):
        rows, cells, meta, spares, _ = _build(monkeypatch, g, term_rows=8, tmp_path=tmp_path)
        term = meta["term"]
        order = meta["commit_order"]
        n_live = sum(1 for c in order if c.startswith("L:"))
        forced = meta["top_game_qb1"]["forced"]
        assert len(forced) == g and all(order[f["commit_index"]].startswith("L:") and f["commit_index"] < n_live for f in forced)
        assert not {f["dealt_index"] for f in forced} & set(term["term_positions"])       # none is dealt in a term slot


def test_an_infeasible_floor_drops_its_game_and_the_next_solve_takes_the_next(monkeypatch):
    rows, cells, meta, spares, calls = _build(monkeypatch, 5, optimize=lambda c: T71._failing_floor(c, every=2))
    tg = meta["top_game_qb1"]
    order = meta["commit_order"]
    bc = [j for j, c in enumerate(order) if c in ("B", "C")]
    assert [d["k"] for d in tg["dropped"]] == [2, 4] and all(d["reason"] == "infeasible with the floor" for d in tg["dropped"])
    assert [f["k"] for f in tg["forced"]] == [1, 3, 5]
    assert sorted([f["commit_index"] for f in tg["forced"]] + [d["commit_index"] for d in tg["dropped"]]) == bc[:5]
    assert all(d["row"] and d["row_sha256"] for d in tg["dropped"])                     # the plain row, by identity
    assert sum(1 for c in calls if c["floor"] is not None) == 5                           # never retried
    line = ur.top_game_qb1_line(tg)
    assert "; 2 dropped" in line and "!!! 2 STUDY-73 GAME(S) DROPPED: g2 g1 (infeasible with the floor); g4 g3" in line
    assert set(M.top_game_qb1_rows({"config": {"union": {"mix": {"mix": meta}}}})) == {frozenset(f["row"]) for f in tg["forced"]}


def test_a_game_without_a_pass_catcher_is_skipped_and_never_takes_a_solve(monkeypatch):
    fr = frame73()
    fr = fr[~((fr.team == "T3") & fr.pos.isin(["WR", "TE"]))].reset_index(drop=True)      # g1's side (T3) has none
    rows, cells, meta, spares, calls = _build(monkeypatch, 3, fr=fr)
    tg = meta["top_game_qb1"]
    bc = [j for j, c in enumerate(meta["commit_order"]) if c in ("B", "C")]
    assert tg["dropped"] == [] and tg["games"][1]["skipped"] and tg["games"][1]["pc"] is None
    assert [f["k"] for f in tg["forced"]] == [1, 3] and [f["commit_index"] for f in tg["forced"]] == bc[:2]   # no backfill
    assert sum(1 for c in calls if c["floor"] is not None) == 2
    line = ur.top_game_qb1_line(tg)
    assert "; 0 dropped; 1 skipped (no pass catcher)" in line and "g2 g1 total 48.5:" in line and "(SKIPPED)" in line


def test_spares_are_never_forced(monkeypatch):
    rows, cells, meta, spares, calls = _build(monkeypatch, 40)                          # G larger than the slate: 6 games
    tg = meta["top_game_qb1"]
    assert len(tg["games"]) == 6 and len(tg["forced"]) == 6
    assert all(f["commit_index"] < 26 for f in tg["forced"])


@pytest.mark.parametrize("kw, msg", [
    (dict(bring_back_top_wr=("A1", "B")), "no bring_back_top_wr"),
    (dict(fill="group"), "fill rr"),
    (dict(cover_games=2), "no cover"),
    (dict(top_game_qb1=-1), "integer >= 1"),
])
def test_mix_rows_refusals(monkeypatch, kw, msg):
    T71._install(monkeypatch, [])
    args = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=0, top_game_qb1=2)
    args.update(kw)
    with pytest.raises(ValueError, match=msg):
        ur.mix_rows(frame73(), set(), 26, 4, 4, 49_000, [1] * 26, **args)


@pytest.mark.parametrize("drop, conflict, msg", [
    ("implied_team_total", False, "the T-70 frame has no implied_team_total"),
    ("game_total", False, "the T-70 frame has no game_total"),
    (None, True, r"game g0 has game_total \[48.0, 50.0\]"),
])
def test_frame_refusals(monkeypatch, drop, conflict, msg):
    T71._install(monkeypatch, [])
    fr = frame73()
    if drop:
        fr = fr.drop(columns=[drop])
    if conflict:
        fr.loc[fr.id == "T1.DST5", "game_total"] = 48.0
    with pytest.raises(SystemExit, match=f"TOP-GAME QB1 REFUSED: {msg}"):
        ur.mix_rows(fr, set(), 26, 4, 4, 49_000, [1] * 26, exposure_cap=13, dst_cap=6, fill="rr", top_game_qb1=2)


@pytest.mark.parametrize("args, ok", [((0, "pmo_x50", None, "group", 0, 0, ()), True), ((5, "mix", "mix", "rr", 0, 0, ()), True),
                                      ((5, "mix", "mix", "group", 0, 0, ()), False), ((5, "mix", "mix", "rr", 2, 0, ()), False),
                                      ((5, "mix", "mix", "rr", 0, 6, ()), False), ((5, "mix", "mix", "rr", 0, 0, ("A1",)), False),
                                      ((-2, "mix", "mix", "rr", 0, 0, ()), False), ((5, "pmo_x50", None, "rr", 0, 0, ()), False)])
def test_the_switch_parses_and_refuses(args, ok):
    if ok:
        assert ur.parse_top_game_qb1(*args) == args[0]
    else:
        with pytest.raises(SystemExit, match="--mix-top-game-qb1"):
            ur.parse_top_game_qb1(*args)


# ---------------------------------------------------------------- the identity checks: union, audit; vet never bound
def test_the_identity_check_binds_forced_rows_only():
    forced = {frozenset(["q", "w", "a", "b", "c", "d", "e", "f", "g"]): ("q", "w")}
    assert M.top_game_violations(["q", "w", "a", "b", "c", "d", "e", "f", "g"], forced) == []
    assert M.top_game_violations(["q", "x", "a", "b", "c", "d", "e", "f", "g"], forced) == []      # a replacement: not bound
    bad = {frozenset(["q", "x", "a", "b", "c", "d", "e", "f", "g"]): ("q", "w")}                   # a receipt that lies
    assert M.top_game_violations(["q", "x", "a", "b", "c", "d", "e", "f", "g"], bad) == ["top-game pair missing: w (the forced pair q + w)"]
    assert M.top_game_qb1_rows({}) == {}


def test_vet_is_never_bound_by_study_73():
    text = (ROOT / "scripts" / "vet_replace_v4.py").read_text()
    assert "top_game" not in text                       # a replacement is a new identity: the reader never names it
    assert V.cell_violations(T71.ROW_WITHOUT, "A1", T71.POS, T71.TEAM, T71.OPP, T71.GAME) == \
        M.shape_violations(T71.ROW_WITHOUT, "A1", T71.POS, T71.TEAM, T71.OPP, T71.GAME)


def test_the_audit_fails_a_forced_row_without_its_pair_and_passes_the_rest(tmp_path):
    b_row = ["AQB", "AWR1", "BRB1", "CRB0", "DWR0", "CWR2", "DTE", "EWR1", "G_DST"]

    def rec(pair):
        blk = {"g": 1, "games": [{"k": 1, "game_id": "x", "game_total": 50.0, "qb": {"id": pair[0]}, "pc": {"id": pair[1]}}],
               "forced": [{"k": 1, "cell": "B", "commit_index": 1, "row": sorted(b_row)}], "dropped": []}
        return {"config": {"union": {"mix": {"mix": {"top_game_qb1": blk}}}}}
    assert "stack_rules" not in T71._audit_run(tmp_path / "ok", b_row, "mix_B", rec(("AQB", "AWR1")))["failed"]
    assert "stack_rules" in T71._audit_run(tmp_path / "lie", b_row, "mix_B", rec(("AQB", "ZWR9")))["failed"]


def test_the_union_checks_and_prints_through_the_one_reader():
    text = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert text.count('ms_tg_rows({"config": {"union": {"mix": {"mix": mix_meta}}}})') == 2      # spares + the book check
    assert "v += ms_tg_violations(ids, _tg)" in text and "v_cell += ms_tg_violations(rosters[i], _tg)" in text
    assert text.count("top_game_qb1=tg_g)") == 2 and text.count("top_game_qb1_line(") == 3


# ---------------------------------------------------------------- parity with the harness: 84's OWN code
# nfl2 experiments/s73_topg_qb1.py @ b402cdd = the FROZEN ffb5bd0 for these three (prereg 5488bd5e): game_order, game_pairs and top_game_qb1 are
# pasted below BYTE FOR BYTE (test_the_vendored_s73_text_is_the_labs pins each function's text; 84: "pin the function
# texts, not the file" -- the frozen module adds an arm, these three stay byte-identical). They run on the lab's own
# term_book (study 71's sha-pinned copy, T71.term_book) through T71's stand-ins and the shared outcome oracle. A difference
# is a parity failure to report to production and 84, never to fix here by editing the vendored text.
S24, S18 = T71.S24, T71.S18
QB1_CELLS = ("B", "C")
S73_TEXT_SHA256 = {"game_order": "78f30ce0ede1edda75929cb341bf204670fcf0ba372e61cb95c602ddaca4f69a",
                   "game_pairs": "1d8626f41ee48fc79408c211665554142301434f5c75fac894a004a1b3782175",
                   "top_game_qb1": "e15b7aec13f8e5178b498b0ff40d3b74fdb4ba2131373881ae526a99969d1f54"}


def game_order(fr_pool: pd.DataFrame) -> list[str]:
    """game_ids by game_total desc, game_id asc, over the games with a QB in the pool."""
    q = fr_pool[fr_pool.pos.astype(str) == "QB"]
    g = (fr_pool[fr_pool.game_id.astype(str).isin(set(q.game_id.astype(str)))]
         .assign(_t=lambda d: pd.to_numeric(d.game_total, errors="coerce"), _g=lambda d: d.game_id.astype(str))
         .groupby("_g")._t.median().reset_index().sort_values(["_t", "_g"], ascending=[False, True]))
    return list(g._g)


def game_pairs(fr_pool: pd.DataFrame, base: np.ndarray, n_games: int) -> list[tuple[str, str, str]]:
    """[(game_id, QB id, top pass catcher id)] for the top n_games games (a game with no pass catcher on the QB's side is
    skipped, recorded by its absence)."""
    d = fr_pool.assign(_p=np.asarray(base, float), _id=fr_pool["id"].astype(str), _pos=fr_pool.pos.astype(str),
                       _team=fr_pool.team.astype(str), _g=fr_pool.game_id.astype(str),
                       _itt=pd.to_numeric(fr_pool.implied_team_total, errors="coerce"),
                       _sal=pd.to_numeric(fr_pool.salary, errors="coerce").fillna(0.0))
    out = []
    for gid in game_order(fr_pool)[:n_games]:
        q = d[(d._g == gid) & (d._pos == "QB")].sort_values(["_p", "_id"], ascending=[False, True])
        sides = []
        for team, qq in q.groupby("_team"):
            sides.append((-float(d[d._team == team]._itt.median()), -float(qq._p.iloc[0]), team, str(qq._id.iloc[0])))
        if not sides:
            continue
        _, _, team, qb = sorted(sides)[0]
        pc = d[(d._team == team) & d._pos.isin(["WR", "TE"])].sort_values(["_p", "_sal", "_id"], ascending=[False, False, True])
        if len(pc):
            out.append((gid, qb, str(pc._id.iloc[0])))
    return out


@contextmanager
def top_game_qb1(pairs: list[tuple[str, str, str]], k_book: int):
    """Wrap the current S24.CapBuilder (inside S37.built_with): each solve of a QB + 1 cell (B or C, by StackRules identity)
    with j < k_book, while pairs remain, takes the next pair as the interaction floor; infeasible -> the plain solve,
    recorded, the game dropped. Yields the class (`forced` / `plain` lists of (game, cell, j); `forced_ids` lineups)."""
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    target = {id(S18.CELLS[c][1]): c for c in QB1_CELLS}

    class TopGameBuilder(orig_cls):
        forced: list = []
        plain: list = []
        forced_ids: list = []
        used: list = []

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            cell = target.get(id(stack))
            j = len(self.prev)
            k = len(type(self).used)
            if cell is None or j >= k_book or k >= len(pairs):
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            gid, qb, pc = pairs[k]
            type(self).used.append(gid)
            ids = {str(p["id"]) for p in self.recs}
            lu = None
            if qb in ids and pc in ids:
                S24.optimize = partial(orig_opt, interaction_floor_weights={(qb, pc): 1.0}, interaction_floor=1.0)
                try:
                    lu = super().solve_with(stack, qb_game_max, pair, extra_bans)
                finally:
                    S24.optimize = orig_opt
            if lu is not None:
                type(self).forced.append((gid, cell, j)); type(self).forced_ids.append(sorted(str(x) for x in lu.ids))
                return lu
            type(self).plain.append((gid, cell, j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    TopGameBuilder.forced, TopGameBuilder.plain, TopGameBuilder.forced_ids, TopGameBuilder.used = [], [], [], []
    S24.CapBuilder = TopGameBuilder
    try:
        yield TopGameBuilder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt


def test_the_vendored_s73_text_is_the_labs():
    import ast
    import hashlib
    src = (ROOT / "tests" / "test_s73_top_game_qb1.py").read_text()
    lines = src.splitlines(keepends=True)
    seen = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in S73_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            assert hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest() == S73_TEXT_SHA256[node.name], node.name
            seen.add(node.name)
    assert seen == set(S73_TEXT_SHA256)


def _pool_frame(fr):
    """The harness's fr_pool for the fixture: every row of the union's pool (the stand-in pool = the whole fixture)."""
    return fr.reset_index(drop=True)


@pytest.mark.parametrize("variant", ["plain", "itt_tie", "full_tie", "full_tie_ids", "no_pc", "backup_qb", "pc_ties"])
def test_the_pairs_are_the_harness_game_pairs(monkeypatch, variant):
    fr = frame73()
    if variant == "itt_tie":
        fr.loc[fr.team == "T1", "implied_team_total"] = 26.0                             # g0's sides tie on the implied total
    elif variant == "full_tie":
        fr.loc[fr.team == "T1", "implied_team_total"] = 26.0
        fr.loc[fr.id == "T1.QB0", "mean_projection"] = float(fr.loc[fr.id == "T0.QB0", "mean_projection"].iloc[0])
    elif variant == "full_tie_ids":                                                      # team order != QB id order
        fr.loc[fr.team == "T1", "implied_team_total"] = 26.0
        fr.loc[fr.id == "T1.QB0", "mean_projection"] = float(fr.loc[fr.id == "T0.QB0", "mean_projection"].iloc[0])
        fr.loc[fr.id == "T1.QB0", ["id", "name"]] = "A.T1QB"
    elif variant == "no_pc":
        fr = fr[~((fr.team == "T3") & fr.pos.isin(["WR", "TE"]))].reset_index(drop=True)
    elif variant == "backup_qb":
        fr = pd.concat([fr, fr[fr.id == "T0.QB0"].assign(id="T0.QBb", name="T0.QBb", mean_projection=99.0)], ignore_index=True)
    elif variant == "pc_ties":
        fr.loc[fr.team == "T0", "mean_projection"] = 10.0
        fr.loc[fr.team == "T0", "salary"] = 6000
    fp = _pool_frame(fr)
    harness = game_pairs(fp, fp.mean_projection.to_numpy(float), 5)
    rows, cells, meta, spares, calls = _build(monkeypatch, 5, fr=fr)
    prod = [(g["game_id"], g["qb"]["id"], g["pc"]["id"]) for g in meta["top_game_qb1"]["games"] if not g["skipped"]]
    assert prod == harness
    assert [g["game_id"] for g in meta["top_game_qb1"]["games"]] == game_order(fp)[:5]


def no_pc_frame():
    fr = frame73()
    return fr[~((fr.team == "T3") & fr.pos.isin(["WR", "TE"]))].reset_index(drop=True)      # g1's side has no pass catcher


def _harness(g, n_term, oracle, k_book=26, k=41, fr=None):
    fr = frame73() if fr is None else fr
    fp = _pool_frame(fr)
    pairs = game_pairs(fp, fp.mean_projection.to_numpy(float), g)
    T71.S24.optimize = T71._h_optimize(oracle)
    with top_game_qb1(pairs, k_book) as TB:
        book, cells, meta = T71.term_book(fr, [0.0] * len(fr), [0.0] * len(fr), (13, 6), [3, 3] + [1] * (k_book - 2), k_book, n_term, k)
        log = list(T71._HCapBuilder.last.log)
    n_live, n_t = sum(meta["live_block"]["cell_rows"].values()), sum(meta["term_block"]["cell_rows"].values())
    tags = ["L"] * n_live + ["T"] * n_t + ["S"] * (len(log) - n_live - n_t)
    return [(t, c, j) for t, (c, j) in zip(tags, log)], list(TB.forced), list(TB.plain), list(TB.used)


def _production(monkeypatch, tmp_path, g, n_term, oracle, fr=None):
    fr = frame73() if fr is None else fr
    calls = []

    def optimize(*args, **kw):
        if oracle.fails(T71._cell_of(kw["stack"]), kw.get("interaction_floor_weights") is not None):
            return None
        return inner(*args, **kw)
    inner = T71._stand_in(calls)
    T71._install(monkeypatch, calls, optimize)
    kw = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=15, top_game_qb1=g)
    if n_term:
        kw.update(term_rows=n_term, term_bonus=_cheap_term(fr, tmp_path))
    rows, cells, meta, spares = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, [3, 3] + [1] * 24, **kw)
    order = [tuple(c.split(":")) if ":" in c else ("L", c) for c in meta["commit_order"]]
    built = [(t, c, j) for j, (t, c) in enumerate(order)] + [("S", c, len(order) + s) for s, (_, c) in enumerate(spares)]
    tg = meta["top_game_qb1"]
    return (built, [(f["game_id"], f["cell"], f["commit_index"]) for f in tg["forced"]],
            [(d["game_id"], d["cell"], d["commit_index"]) for d in tg["dropped"]], len(rows))


@pytest.mark.parametrize("g, n_term, oracle_kw, frame", [
    (5, 8, {}, None),                               # W5: the cheap +2 block on 8 rows, TOPG5_QB1 (the decision)
    (3, 8, {}, None),                               # TOPG3_QB1 (exploratory)
    (5, 8, {"floor_every": 2}, None),               # infeasible floors: dropped, the next solve takes the next pair
    (5, 8, {"floor_every": 3, "c_ok": 2}, None),    # and C failing: its quota passes to A1
    (5, 0, {"c_ok": 3}, None),                      # no block: the plain round-robin fill
    (5, 8, {}, "no_pc"),                            # a game without a pass catcher: skipped, never a solve
    (15, 8, {}, "wide"),                            # more pairs than book B / C solves: the spares never take one
])
def test_parity_with_the_harness_row_choice(monkeypatch, tmp_path, g, n_term, oracle_kw, frame):
    fr = {None: None, "no_pc": no_pc_frame(), "wide": frame73(15)}[frame]
    built_h, forced_h, plain_h, used_h = _harness(g, n_term, T71._Oracle(**oracle_kw), fr=fr)
    built_p, forced_p, dropped_p, n_book = _production(monkeypatch, tmp_path, g, n_term, T71._Oracle(**oracle_kw), fr=fr)
    assert n_book == 26 and built_p == built_h                                           # the same build order, 41 rows
    assert forced_p == forced_h and dropped_p == plain_h                                  # the same (game, cell, j)
    assert len(forced_p) + len(dropped_p) == len(used_h)
    assert all(j < 26 for _, _, j in forced_p + dropped_p)                               # BOOK solves only
    if frame == "wide":
        assert len(used_h) == sum(1 for t, c, j in built_h if j < 26 and c in ("B", "C")) < g   # pairs left over
