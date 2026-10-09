"""The QB-alone flag (union_reselect --mix-qb-alone-rows N; study 77's NAKED rule; production's agreed format 10-08, the shape
named C0): the C0 shape in ALL_CELLS only; off identical; the first N cell-C BOOK solves in build order at C0 (C's rules
with qb_stack 0..0), an infeasible one built at C's rules and recorded, spares never; the ruled rows keep C's quota and C's
deal positions and come back as C0 (tag mix_C0) in the term path and the plain round-robin; the refusals; the shares, the
audit, the dealt-shares report and the replacement's fits; and PARITY with the lab's OWN frozen qb_alone (nfl2
experiments/s77_naked.py @ cd754b3, module d455f3dd, pasted byte for byte, its text sha-pinned) on the lab's term_book: one
shape-aware stand-in optimizer for both sides, the same (cell, j) ruled / plain, the SAME 41 lineups and the C0 rows at the
harness's ruled positions; a mutated wrapper (qb_stack_max 1) fails it."""
import ast
import dataclasses
import hashlib
import importlib.util
import sys
import types
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402
from nfl_dfs.inference import mix_shapes as M  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


T71 = _load("t71_helpers_qa", ROOT / "tests" / "test_s71_bring_back_top_wr.py")      # the lab's term_book, stand-ins, audit run
MDS = _load("mix_dealt_shares_qa", ROOT / "scripts" / "mix_dealt_shares.py")
W = [3, 3] + [1] * 24


# ---------------------------------------------------------------- the shape
def test_c0_is_c_with_no_stack_mate_and_only_in_all_cells():
    _, c_rules, c_qmax, c_pair = M.MIX_CELLS["C"]
    assert M.QB_ALONE_CELL == "C0" and M.QB_ALONE_FROM == "C"
    assert M.ALL_CELLS["C0"] == (0.0, dict(c_rules, qb_stack_min=0, qb_stack_max=0), c_qmax, c_pair)
    assert "C0" not in M.MIX_CELLS and all("C0" not in cells for cells in M.PORTFOLIOS.values())
    assert set(M.ALL_CELLS) == {"A1", "A2", "B", "C", "WS", "C0"}
    assert M.cell_of_tag("mix_C0") == "C0"


POS = {"q": "QB", "m": "WR", "t": "TE", "o": "WR", "r1": "RB", "r2": "RB", "w1": "WR", "w2": "WR", "w3": "WR", "d": "DST",
       "qr": "RB"}
TEAM = {"q": "T", "m": "T", "t": "T", "qr": "T", "o": "O", "r1": "G", "r2": "H", "w1": "G", "w2": "J", "w3": "K", "d": "J"}
OPP = {"T": "O", "O": "T", "G": "H", "H": "G", "J": "K", "K": "J"}
GAME = {k: {"T": "g1", "O": "g1", "G": "g2", "H": "g2", "J": "g3", "K": "g3"}[v] for k, v in TEAM.items()}


def viol(row, cell):
    return M.shape_violations(row, cell, POS, TEAM, {k: OPP[v] for k, v in TEAM.items()}, GAME)


def test_the_shape_check_holds_a_c0_row_to_no_mate_and_no_bring_back():
    assert viol(["q", "qr", "r1", "w1", "w2", "w3", "d"], "C0") == []                    # an RB of the QB's team is allowed
    assert any("stack mates < 1" in v for v in viol(["q", "qr", "r1", "w1", "w2", "w3", "d"], "C"))
    assert any("stack mates > 0" in v for v in viol(["q", "m", "r1", "w1", "w2", "w3", "d"], "C0"))
    assert any("bring-backs > 0" in v for v in viol(["q", "o", "r1", "w1", "w2", "w3", "d"], "C0"))


# ---------------------------------------------------------------- a 6-game fixture (12 teams: QB, RB, WR, WR, TE, DST)
def frame() -> pd.DataFrame:
    rows = []
    for t in range(12):
        team, opp, g = f"T{t}", f"T{t ^ 1}", f"g{t // 2}"
        for j, pos in enumerate(("QB", "RB", "WR", "WR", "TE", "DST")):
            pid = f"{team}.{pos}{j}"
            rows.append({"id": pid, "name": pid, "pos": pos, "team": team, "opp": opp, "game_id": g,
                         "salary": 4000 + 100 * ((7 * t + 3 * j) % 40), "mean_projection": 5.0 + ((11 * t + 5 * j) % 23)})
    return pd.DataFrame(rows)


def cheap_term(fr):
    return {i: 2.0 for i, s, p in zip(fr.id, fr.salary, fr.pos) if s < 5500 and p != "DST"}


def pick(pool, obj, n_prev, bans, naked):
    """THE shared stand-in solve: the objective order (ties: id) rotated by the rows committed so far; naked: the first QB in
    that order and the next 8 non-QB players that are not a WR / TE of his team; else the first 9."""
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj]), str(p["id"])))
    off = n_prev % len(order)
    rot = order[off:] + order[:off]
    if not naked:
        return rot[:9]
    q = next(p for p in rot if p["pos"] == "QB")
    return [q] + [p for p in rot if p["pos"] != "QB" and not (p["pos"] in ("WR", "TE") and p["team"] == q["team"])][:8]


class Fail:
    """Which QB-alone solves report infeasible: every `every`-th (None = never)."""
    def __init__(self, every=None):
        self.every, self.n = every, 0

    def __call__(self) -> bool:
        self.n += 1
        return bool(self.every) and self.n % self.every == 0


def production_opt(calls, fail):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 interaction_floor_weights=None, interaction_floor=None):
        naked = stack.qb_stack_max == 0
        calls.append({"naked": naked, "qb_stack_min": stack.qb_stack_min, "bring_back_max": stack.bring_back_max,
                      "qb_game_max": qb_game_max, "j": len(banned_lineups)})
        if naked and fail():
            return None
        return T71.LU(pick(pool, objective_col, len(banned_lineups), bans, naked))
    return optimize


def build(monkeypatch, n, fail_every=None, term=True, caps=True, spares=15, **extra):
    calls = []
    T71._install(monkeypatch, calls, production_opt(calls, Fail(fail_every)))
    fr = frame()
    kw = dict(exposure_cap=13 if caps else None, dst_cap=6 if caps else None, fill="rr", spares=spares, qb_alone_rows=n)
    if term:
        kw.update(term_rows=8, term_bonus=cheap_term(fr))
    kw.update(extra)
    rows, cells, meta, sp = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, W, **kw)
    return rows, cells, meta, sp, calls


def qb_mates(row, fr):
    pos, team = dict(zip(fr.id, fr.pos)), dict(zip(fr.id, fr.team))
    q = next(i for i in row if pos[i] == "QB")
    return sum(1 for i in row if pos[i] in ("WR", "TE") and team[i] == team[q])


# ---------------------------------------------------------------- production behaviour
@pytest.mark.parametrize("term", [True, False])
def test_off_is_the_old_call_exactly(monkeypatch, term):
    """The known-answer gate (84 / production): N = 0 is the call without the argument, byte for byte (rows, cells, meta,
    spares and every optimizer call)."""
    a = build(monkeypatch, 0, term=term)
    calls = []
    T71._install(monkeypatch, calls, production_opt(calls, Fail()))
    fr = frame()
    kw = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=15)
    if term:
        kw.update(term_rows=8, term_bonus=cheap_term(fr))
    b = ur.mix_rows(fr, set(), 26, 4, 4, 49_000, W, **kw)
    assert a[:4] == b and a[4] == calls and "qb_alone" not in a[2] and not any(c["naked"] for c in calls)
    assert "C0" not in a[1] and set(a[2]["entry_shares_before_overlap_limit"]) == set(M.MIX_CELLS)


@pytest.mark.parametrize("term", [True, False])
@pytest.mark.parametrize("n", [3, 6, 7])
def test_the_first_n_c_book_solves_are_qb_alone_in_cs_slots(monkeypatch, n, term):
    rows, cells, meta, spares, calls = build(monkeypatch, n, term=term)
    off_rows, off_cells, off_meta, _, _ = build(monkeypatch, 0, term=term)
    qa = meta["qb_alone"]
    assert qa["rows_cap"] == n and qa["plain"] == [] and qa["from_cell"] == "C" and qa["shape"] == "C0"
    c_solves = [j for j, c in enumerate(meta["commit_order"]) if c.split(":")[-1] == "C"]
    assert qa["ruled"] == [["C", j] for j in c_solves[:n]]                                  # the first n C solves, build order
    assert sum(1 for c in calls if c["naked"]) == n and all(c["j"] < 26 for c in calls if c["naked"])
    assert all(c["qb_stack_min"] == 0 and c["bring_back_max"] == 0 and c["qb_game_max"] == 3 for c in calls if c["naked"])
    assert cells.count("C0") == n == qa["book_rows_tagged"]
    assert [("C" if c == "C0" else c) for c in cells] == off_cells                          # C's quota and C's deal positions
    fr = frame()
    assert all(qb_mates(r, fr) == 0 for r, c in zip(rows, cells) if c == "C0")
    assert all(c != "C0" for _, c in spares)                                                # spares never
    sh = meta["entry_shares_before_overlap_limit"]
    assert set(sh) == set(M.MIX_CELLS) | {"C0"}
    assert sh["C"] + sh["C0"] == pytest.approx(off_meta["entry_shares_before_overlap_limit"]["C"], abs=2e-4)
    assert ur.qb_alone_line(qa) == f"QB ALONE: {n} rows; ruled {n}, plain 0"


def test_an_infeasible_ruled_solve_is_built_at_cs_rules_and_the_slot_counts(monkeypatch):
    rows, cells, meta, spares, calls = build(monkeypatch, 6, fail_every=2)
    qa = meta["qb_alone"]
    c_solves = [j for j, c in enumerate(meta["commit_order"]) if c.split(":")[-1] == "C"]
    assert [j for _, j in qa["plain"]] == [c_solves[1], c_solves[3], c_solves[5]]          # the 2nd, 4th, 6th attempts failed
    assert sorted(j for _, j in qa["ruled"] + qa["plain"]) == c_solves[:6]                  # the slot is used either way
    assert sum(1 for c in calls if c["naked"]) == 6 and cells.count("C0") == 3              # one attempt per slot, never retried
    assert ur.qb_alone_line(qa) == "QB ALONE: 6 rows; ruled 3, plain 3"


@pytest.mark.parametrize("kw, msg", [(dict(qb_alone_rows=-1), "0 <= N"), (dict(qb_alone_rows=8), r"C's book rows \(7\)"),
                                     (dict(qb_alone_rows=3, fill="group"), "fill rr"),
                                     (dict(qb_alone_rows=3, cover_games=2), "no cover")])
def test_mix_rows_refusals(monkeypatch, kw, msg):
    T71._install(monkeypatch, [])
    args = dict(exposure_cap=13, dst_cap=6, fill="rr", spares=0); args.update(kw)
    with pytest.raises(ValueError, match=msg):
        ur.mix_rows(frame(), set(), 26, 4, 4, 49_000, [1] * 26, **args)


def test_qb_alone_max_is_cs_book_rows():
    q = [c[0] for c in M.MIX_CELLS.values()]
    assert ur.qb_alone_max(q, 26) == 7 == ur.qb_alone_max(q, 26, 8)
    assert ur.qb_alone_max([0.30, 0.14, 0.40, 0.16], 26) == M.allocate([0.30, 0.14, 0.40, 0.16], 26)[3]


Q = [c[0] for c in M.MIX_CELLS.values()]


@pytest.mark.parametrize("args, ok", [((0, "pmo_x50", None, "group", 0, 0, 26, None, Q, 0), True),
                                      ((3, "mix", "mix", "rr", 0, 0, 26, None, Q, 8), True),
                                      ((7, "mix", "mix", "rr", 0, 0, 26, None, Q, 8), True),
                                      ((8, "mix", "mix", "rr", 0, 0, 26, None, Q, 8), False),
                                      ((-1, "mix", "mix", "rr", 0, 0, 26, None, Q, 8), False),
                                      ((3, "pmo_x50", None, "rr", 0, 0, 26, None, Q, 0), False),
                                      ((3, "mix", "ws", "rr", 0, 0, 26, None, Q, 0), False),
                                      ((3, "mix", "mix", "value", 0, 0, 26, None, Q, 0), False),
                                      ((3, "mix", "mix", "rr", 3, 0, 26, None, Q, 0), False),
                                      ((3, "mix", "mix", "rr", 0, 9, 26, None, Q, 0), False),
                                      ((3, "mix", "mix", "rr", 0, 0, 26, Path("inputs.csv"), Q, 0), False)])
def test_the_switch_parses_and_refuses(args, ok):
    if ok:
        assert ur.parse_qb_alone_rows(*args) == args[0]
    else:
        with pytest.raises(SystemExit, match="--mix-qb-alone-rows"):
            ur.parse_qb_alone_rows(*args)


def test_the_cli_carries_the_flag_and_the_help_names_the_house_fallback():
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert src.count("qb_alone_rows=qa_g") == 2                                             # the book and the ownership-term book
    assert "takes the flagged house fallback (an A1 row)" in src


def test_selected_entry_shares_puts_c0_beside_c_and_is_unchanged_off():
    off = ur.selected_entry_shares(["A1", "C", "B", "C"], [2, 1, 1, 0])
    assert set(off) == set(M.MIX_CELLS) and off["C"] == 0.25
    on = ur.selected_entry_shares(["A1", "C0", "B", "C"], [2, 1, 1, 0])
    assert set(on) == set(M.MIX_CELLS) | {"C0"} and on["C0"] == 0.25 and on["C"] == 0.0


# ---------------------------------------------------------------- the audit, the dealt shares, the replacement's fits
C0_ROW = ["AQB", "ERB0", "CRB1", "CWR0", "DWR0", "CWR2", "GTE", "EWR1", "G_DST"]      # A's QB alone: no A WR / TE, no B player
B_ROW = ["AQB", "AWR1", "BRB1", "CRB0", "DWR0", "CWR2", "DTE", "EWR1", "G_DST"]       # a QB + 1 row with a bring-back


def test_the_audit_holds_a_c0_row_to_the_c0_shape(tmp_path):
    assert "stack_rules" not in T71._audit_run(tmp_path / "a", C0_ROW, "mix_C0", {})["failed"]
    bad = T71._audit_run(tmp_path / "b", B_ROW, "mix_C0", {})
    assert "stack_rules" in bad["failed"]
    assert "stack mates > 0" in next(c["detail"] for c in bad["checks"] if c["check"] == "stack_rules")
    assert "stack_rules" in T71._audit_run(tmp_path / "c", C0_ROW, "mix_C", {})["failed"]   # tagged C: 0 mates < 1


def test_the_audit_counts_the_c0_main_rows_against_the_receipt(tmp_path):
    TA = _load("tabl_qa", ROOT / "tests" / "test_audit_build_levers.py")
    lus = [TA._lineup("A", "B", "C"), TA._lineup("C", "D", "E"), TA._lineup("E", "F", "G"), TA._lineup("G", "H", "A"),
           TA._lineup("B", "A", "D"), TA._lineup("D", "C", "F")]
    tail = TA.CONTESTS + [{"name": "milly", "contest_id": "9", "entries": 1, "keep": 1, "track": "tail"}]
    base = {"selector": "mean", "operational_k": 5, "tail_sleeve": {"rows": 1, "selector_used": "mean"}}

    def run(tmp, qa, tags):
        mix_meta = {"exposure_cap": 3, "max_exposure_used": 3, "dst_cap": 2, "max_dst_rows_used": 2,
                    "mix": {"cells": {"A1": {"rows": 5}}, **({"qb_alone": qa} if qa else {})}}
        r = TA._run_dir(tmp, lineups=lus, book=lus[:6], receipt={"written": 6, "config": {**base, "union": {"main": "mix", "mix": mix_meta}}})
        c = pd.read_parquet(r / "candidates.parquet"); c["source_run"] = ["mix"] * 5 + ["saturday"]; c["tag"] = tags
        c["book_rank"] = [1, 2, 3, 4, 5, None]
        c.to_parquet(r / "candidates.parquet")
        res = TA._audit(r, contests=tail, expect_selector="mean")
        return res, next(x for x in res["checks"] if x["check"] == "qb_alone")

    blk = {"rows_cap": 2, "ruled": [["C", 3], ["C", 7]], "plain": [["C", 11]]}
    res, c = run(tmp_path / "a", blk, ["mix_A1"] * 3 + ["mix_C0"] * 2 + ["mix_C0"])        # the 6th row is not a main row
    assert c["ok"] and c["tagged"] == 2 and c["ruled"] == 2 and c["plain"] == 1 and "--mix-qb-alone-rows 2" in c["detail"]
    res, c = run(tmp_path / "b", blk, ["mix_A1"] * 4 + ["mix_C0"] + ["lev"])
    assert not c["ok"] and "qb_alone" in res["failed"]                                    # 1 tagged, 2 ruled
    res, c = run(tmp_path / "c", None, ["mix_A1"] * 5 + ["lev"])
    assert c["ok"] and c["tagged"] == 0 and c["detail"] == "--mix-qb-alone-rows off; 0 main rows tagged mix_C0"
    res, c = run(tmp_path / "d", None, ["mix_A1"] * 4 + ["mix_C0"] + ["lev"])
    assert not c["ok"]                                                                     # a C0 row the receipt never built


def test_the_dealt_shares_count_c0_beside_c_and_fit_a_replacement_only_when_on():
    pos = {k: POS[k] for k in POS}; team = TEAM
    opp = {k: OPP[v] for k, v in TEAM.items()}
    alone = ["q", "qr", "r1", "w1", "w2", "w3", "d"]
    stacked = ["q", "m", "r1", "w1", "w2", "w3", "d"]
    upload = [alone, stacked, list(reversed(alone))]
    tagged = {frozenset(alone): "C0", frozenset(stacked): "C"}
    out = MDS.dealt_shares({"x": [0, 1]}, upload, tagged, pos, team, opp, GAME, M.MIX_CELLS, 2)
    assert out["cells"]["C0"] == 1 and out["cells"]["C"] == 1 and "C0" not in out["quotas"]
    untagged = {frozenset(stacked): "C"}                                                   # row 0: an untagged replacement
    off = MDS.dealt_shares({"x": [0, 1]}, upload, untagged, pos, team, opp, GAME, M.MIX_CELLS, 2)
    on = MDS.dealt_shares({"x": [0, 1]}, upload, untagged, pos, team, opp, GAME, M.MIX_CELLS, 2,
                          extra_fit={"C0": M.ALL_CELLS["C0"]})
    assert off["untagged_main_entries_by_shape"] == {"house": 1} and on["untagged_main_entries_by_shape"] == {"C0": 1}


def test_the_replacement_offers_c0_only_when_the_union_built_c0_rows():
    src = (ROOT / "scripts" / "vet_replace_v4.py").read_text()
    assert '_qa_on = bool(_mixm.get("qb_alone") or (_mixm.get("with_term") or {}).get("qb_alone"))' in src
    assert "_fit_cells = [c for c in ALL_CELLS if c != QB_ALONE_CELL or _qa_on]" in src
    assert "fits = {c for c in _fit_cells if not mix_violations(toks, c)}" in src
    assert "fits = {c for c in ALL_CELLS" not in src
    V = T71.V
    j, fb = V.pick_replacement(__import__("numpy").array([1.0, 2.0]), [{"C0"}, {"A1"}], "C0")
    assert (j, fb) == (0, None)                                                            # a C0 candidate fills a C0 row
    j, fb = V.pick_replacement(__import__("numpy").array([1.0, 2.0]), [{"C"}, {"A1"}], "C0")
    assert (j, fb) == (1, "A1")                                                            # none fits: the flagged house fallback


# ---------------------------------------------------------------- parity with the lab's OWN frozen qb_alone
QB_ALONE_TEXT_SHA256 = "a4911b4b085d45e1950a9bb4e7e53737bf18fb51c443481a838c656c352fab26"   # nfl2 cd754b3 s77_naked.py (d455f3dd)


@dataclasses.dataclass
class _QStack:                                     # one dataclass per cell: s77's wrapper finds C by identity and replaces it
    cell: str
    qb_stack_min: int = 1
    bring_back_min: int = 0
    qb_stack_max: int | None = None
    bring_back_max: int | None = None


S18 = types.SimpleNamespace(CELLS={n: (q, _QStack(n, **r), qmax, which) for n, (q, r, qmax, which) in M.MIX_CELLS.items()},
                            allocate=M.allocate, interleave=M.interleave, pair_games=lambda fr, which: None)
S24 = T71.S24


@contextmanager
def qb_alone(n_rows: int, k_book: int):
    """Wrap the current S24.CapBuilder (inside S37.built_with): the first n_rows solves of cell C (by StackRules identity)
    with j < k_book are solved at C's rules with qb_stack_min 0 and qb_stack_max 0 (C's qb_game_max kept); infeasible ->
    C's own rules, recorded (the slot is used either way). Yields the class (`ruled` / `plain` lists of (cell, j);
    `ruled_ids` lineups)."""
    orig_cls = S24.CapBuilder
    c_stack = S18.CELLS["C"][1]
    naked = dataclasses.replace(c_stack, qb_stack_min=0, qb_stack_max=0)

    class NakedBuilder(orig_cls):
        ruled: list = []
        plain: list = []
        ruled_ids: list = []
        used: list = []

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            j = len(self.prev)
            if stack is not c_stack or j >= k_book or len(type(self).used) >= n_rows:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            type(self).used.append(j)
            lu = super().solve_with(naked, qb_game_max, pair, extra_bans)
            if lu is not None:
                type(self).ruled.append(("C", j)); type(self).ruled_ids.append(sorted(str(x) for x in lu.ids))
                return lu
            type(self).plain.append(("C", j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    NakedBuilder.ruled, NakedBuilder.plain, NakedBuilder.ruled_ids, NakedBuilder.used = [], [], [], []
    S24.CapBuilder = NakedBuilder
    try:
        yield NakedBuilder
    finally:
        S24.CapBuilder = orig_cls


def _text_of(name: str) -> str:
    src = (ROOT / "tests" / "test_qb_alone_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.FunctionDef) and n.name == name)
    start = min([node.lineno] + [d.lineno for d in node.decorator_list])
    return "".join(lines[start - 1:node.end_lineno])


def test_the_vendored_qb_alone_text_is_the_labs():
    assert hashlib.sha256(_text_of("qb_alone").encode()).hexdigest() == QB_ALONE_TEXT_SHA256


class _HLU:
    def __init__(self, ids):
        self.ids = ids


class _QHCap:
    """S24.CapBuilder's contract (solve_with commits a solved row) with the frame's records, so the stand-in can read each
    player's pos / team; no caps (production's run below has its caps off too)."""
    def __init__(self, fr, base, lam, main_cap, dst_cap):
        self.recs = fr.assign(obj=0.0).to_dict("records")
        self.prev, self.count, self.log = [], Counter(), []

    def solve_with(self, stack, qb_game_max, pair, extra_bans):
        lu = S24.optimize(self.recs, stack=stack, banned_lineups=self.prev)
        if lu is not None:
            self.prev.append(lu.ids); self.count.update(lu.ids); self.log.append((stack.cell, len(self.prev) - 1))
        return lu


def harness_opt(fail):
    def optimize(recs, stack, banned_lineups):
        naked = stack.qb_stack_max == 0
        if naked and fail():
            return None
        return _HLU(tuple(str(p["id"]) for p in pick(recs, "obj", len(banned_lineups), None, naked)))
    return optimize


def harness(monkeypatch, n, n_term=8, fail_every=None, wrapper=None):
    fr = frame()
    term = cheap_term(fr)
    monkeypatch.setattr(T71, "S18", S18)
    monkeypatch.setattr(S24, "CapBuilder", _QHCap)
    monkeypatch.setattr(S24, "optimize", harness_opt(Fail(fail_every)))
    base = fr.mean_projection.astype(float).tolist()
    with (wrapper or qb_alone)(n, 26) as T:
        book, cells, meta = T71.term_book(fr, base, [term.get(i, 0.0) for i in fr.id], (13, 6), W, 26, n_term, 41)
    lineups = [sorted(lu.ids) for lu in book]
    at = [next(k for k in range(26) if lineups[k] == r) for r in T.ruled_ids]
    return lineups, cells, list(T.ruled), list(T.plain), at


def production(monkeypatch, n, term=True, fail_every=None):
    rows, cells, meta, spares, _ = build(monkeypatch, n, fail_every=fail_every, term=term, caps=False)
    qa = meta["qb_alone"]
    return ([sorted(r) for r in rows] + [sorted(ids) for ids, _ in spares], cells,
            [tuple(x) for x in qa["ruled"]], [tuple(x) for x in qa["plain"]])


@pytest.mark.parametrize("n, term, fail_every", [(3, True, None), (6, True, None), (7, True, None), (6, True, 2),
                                                 (3, True, 3), (3, False, None), (6, False, 2)])
def test_parity_same_rows_ruled_the_same_lineups_and_positions(monkeypatch, n, term, fail_every):
    lineups_h, cells_h, ruled_h, plain_h, at_h = harness(monkeypatch, n, n_term=8 if term else 0, fail_every=fail_every)
    lineups_p, cells_p, ruled_p, plain_p = production(monkeypatch, n, term=term, fail_every=fail_every)
    assert ruled_p == ruled_h and plain_p == plain_h                                        # the same (cell, j)
    assert lineups_p == lineups_h and len(lineups_p) == 41                                  # the same 26 book rows + 15 spares
    assert [("C" if c == "C0" else c) for c in cells_p] == cells_h[:26]                     # C's deal positions
    assert [k for k, c in enumerate(cells_p) if c == "C0"] == sorted(at_h)                  # C0 exactly at the ruled rows


def test_parity_detects_a_wrong_stack_bound(monkeypatch):
    """The mutation check (production's request): the lab's wrapper with qb_stack_max 1 (C's own rule) gives other lineups."""
    text = _text_of("qb_alone")
    assert text.count("qb_stack_max=0") == 1
    ns = dict(globals())
    exec(compile(text.replace("qb_stack_max=0", "qb_stack_max=1"), "mutated", "exec"), ns)
    lineups_h, _, ruled_h, _, _ = harness(monkeypatch, 3, wrapper=ns["qb_alone"])
    lineups_p, _, ruled_p, _ = production(monkeypatch, 3)
    assert ruled_p == ruled_h and lineups_p != lineups_h


# ---------------------------------------------------------------- the build fails closed on a broken record (84, 10-09)
def _state(ruled, plain=(), used=None, pending=None):
    return {"used": len(ruled) + len(plain) if used is None else used, "pending": pending, "ruled": [list(x) for x in ruled],
            "plain": [list(x) for x in plain], "rows": {frozenset({f"r{j}"}) for _, j in ruled}}


def test_a_clean_record_passes():
    ur.qb_alone_close(_state([("C", 2), ("C", 6)], [("C", 9)]), ["A1", "C0", "B", "C0", "C"], [(["s"], "C")],
                      ["A1", "B", "C", "A2", "A1", "B", "C", "A1", "B", "C"])


@pytest.mark.parametrize("state, cells, order, msg", [
    (_state([("C", 2)], pending=5), ["C0"], ["A1", "B", "C"], "never committed"),               # a peek with no commit
    (_state([("C", 2)], used=3), ["C0"], ["A1", "B", "C"], "3 attempts but 1 ruled"),
    (_state([("C", 2), ("C", 3)]), ["C0", "B"], ["A1", "B", "C", "A1"], "1 rows labelled C0 for 2 ruled"),
    (_state([("C", 2), ("C", 3)]), ["C0", "C0"], ["A1", "B", "C", "A1"], r"ruled rows at j \[3\] are not C solves"),
])
def test_a_leaked_or_broken_record_raises(state, cells, order, msg):
    """84's leak: a C0 peek left uncommitted marks the NEXT committed row (another cell's, here A1 at j 3) as ruled; the
    build raises instead of returning a book whose record is wrong."""
    with pytest.raises(ValueError, match="QB ALONE RECORD BROKEN: .*" + msg):
        ur.qb_alone_close(state, cells, [], order)


def test_mix_rows_runs_the_record_check(monkeypatch):
    called = []
    real = ur.qb_alone_close
    monkeypatch.setattr(ur, "qb_alone_close", lambda *a: (called.append(a), real(*a)))
    build(monkeypatch, 3)
    assert len(called) == 1
    called.clear(); build(monkeypatch, 0)
    assert called == []                                                                     # off: never called
