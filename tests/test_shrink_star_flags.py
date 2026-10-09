"""Study 92's S1 (shrink) and S2 (one star) on the live MIX book (the operator 10-09: "Test both tonight for live"):
union_reselect's proj_shrink / star_ids and mix_rows(shrink=..., row_bounds=[..., (stars, 1, 9)]) against the lab's OWN code
-- nfl2 experiments/s92_shrink_star.py @ 7913aefc: its shrink and star_set pasted BELOW byte for byte (text sha-pinned),
built through study 38 6p's row_rules inside study 89's own_caps (pasted in test_row_rules_flag.py / test_own_cap_flag.py) on
the lab's term_book, with ONE stand-in optimizer reading the lab's set_constraints (<= and >=) and production's member_bounds
(lo, hi) alike: identical shrunk values, star sets, 26 book rows, 15 spares and re-solves; off is the old call; the frame's
proj is never rewritten."""
import ast
import hashlib
import importlib.util
import sys
import types
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


RR = _load("row_rules_helpers_s92", ROOT / "tests" / "test_row_rules_flag.py")   # 6p's row_rules, 89's own_caps, the fixture
OC, T71 = RR.OC, RR.T71
S24 = T71.S24
SKILL = ("QB", "RB", "WR", "TE")                # the lab module's names, read by the pasted text
K_SHRINK, WINDOW, STAR_SALARY, STAR_POS = 0.7, 500.0, 8000.0, ("RB", "WR", "TE")
LAB_TEXT_SHA256 = {"shrink": "367ea775c8647cd9f707ffb3a692c415e21e5d5209f77c1ee5eb76e23228bc8d",
                   "star_set": "76af6e8c5c3f1ca8d8db7bac4cc8cc207359e868e6a201ca02b2401dbed123fb"}


# ---- nfl2 experiments/s92_shrink_star.py @ 7913aefc, BYTE FOR BYTE (test_the_pasted_lab_text_is_the_labs) ----
def shrink(fr_pool: pd.DataFrame, proj: np.ndarray, k: float = K_SHRINK, window: float = WINDOW) -> np.ndarray:
    """S1: per skill position, typical_i = the median of proj over the pool's players of that position whose salary is within
    +-window of salary_i (inclusive, i included); proj'_i = typical_i + k x (proj_i - typical_i). DSTs (and any other position)
    unchanged."""
    pos = fr_pool.pos.astype(str).to_numpy()
    sal = pd.to_numeric(fr_pool.salary, errors="coerce").fillna(0.0).to_numpy(float)
    p = np.asarray(proj, dtype=float)
    out = p.copy()
    for P in SKILL:
        idx = np.where(pos == P)[0]
        for i in idx:
            nb = idx[np.abs(sal[idx] - sal[i]) <= window]
            typ = float(np.median(p[nb]))
            out[i] = typ + k * (float(p[i]) - typ)
    return out


def star_set(fr_pool: pd.DataFrame, salary: float = STAR_SALARY) -> set[str]:
    """S2: the pool's RB / WR / TE priced >= salary."""
    sal = pd.to_numeric(fr_pool.salary, errors="coerce").fillna(0.0).to_numpy(float)
    return {str(i) for i, p, s in zip(fr_pool.id.astype(str), fr_pool.pos.astype(str), sal) if p in STAR_POS and s >= salary}


# ---- one stand-in optimizer (lower and upper bounds) ----
FORCE_NONE_AT = {6, 15}


def pick(pool, obj_col, prev, bans, bounds):
    """bounds: [(ids, lo, hi)]. First the best (objective order, rotated by the rows so far) members of every set with lo > 0
    up to lo, then the rest in order without exceeding any hi; 9 players or None."""
    if bounds and len(prev) in FORCE_NONE_AT:
        return None
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj_col]), str(p["id"])))
    if len(order) < 9:
        return None
    off = len(prev) % len(order)
    rot = order[off:] + order[:off]
    sets = [(set(ids), lo, hi) for ids, lo, hi in (bounds or [])]
    out, held = [], [0] * len(sets)

    def ok(p):
        return all(not (p["id"] in ids and held[k] >= hi) for k, (ids, lo, hi) in enumerate(sets)) and p not in out

    def take(p):
        out.append(p)
        for k, (ids, _, _) in enumerate(sets):
            held[k] += p["id"] in ids
    for k, (ids, lo, hi) in enumerate(sets):
        for p in rot:
            if held[k] >= lo:
                break
            if p["id"] in ids and ok(p):
                take(p)
        if held[k] < lo:
            return None
    for p in rot:
        if len(out) == 9:
            break
        if ok(p):
            take(p)
    return out if len(out) == 9 else None


class _PLU:
    def __init__(self, players):
        self.players = players


def install_production(monkeypatch):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 interaction_floor_weights=None, interaction_floor=None, member_bounds=None):
        got = pick(pool, objective_col, banned_lineups, bans, list(member_bounds or ()))
        return _PLU(got) if got is not None else None
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = optimize; lineup.StackRules = T71.StackRules
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")), ("nfl2.core.lineup", lineup)):
        monkeypatch.setitem(sys.modules, name, mod)


class _LU:
    def __init__(self, ids):
        self.ids = ids


def _lab_optimize(recs, stack, objective_col, banned_lineups, bans, set_constraints=None):
    b = [(ids, 0, n) if op == "<=" else (ids, n, 99) for ids, op, n in (set_constraints or ())]
    got = pick(recs, objective_col, banned_lineups, bans, b)
    return _LU(tuple(p["id"] for p in got)) if got is not None else None


def frame_with_stars():
    fr = OC.frame()
    fr.loc[fr.id.isin(["p1", "p2", "p5", "p9", "p14", "p22"]), "salary"] = [8000, 8400, 9100, 8200, 7999, 8800]
    return fr


def fp_path(tmp_path, fr):
    return OC.fp_file(tmp_path, fr)


def production_book(monkeypatch, fr, own_cap, bounds, shrink, k=26, spares=15):
    install_production(monkeypatch)
    rows, cells, meta, sp = ur.mix_rows(fr, set(), k, 9, None, 0, OC.W, exposure_cap=13, dst_cap=6, fill="rr", spares=spares,
                                        term_rows=8, term_bonus=OC.TERM, own_cap=own_cap, row_bounds=bounds, shrink=shrink)
    return [list(r) for r in rows], [list(r) for r, _ in sp], meta


def lab_book(fr, cap_rows, cons, base, k_book=26, k=41):
    term = np.array([OC.TERM.get(i, 0.0) for i in fr.id])
    orig = (S24.CapBuilder, S24.optimize)
    S24.CapBuilder, S24.optimize = RR._SCapBuilder, _lab_optimize
    try:
        with RR.row_rules(cons, k_book) as R, OC.own_caps(cap_rows, k_book) as T:
            book, cells, mt = T71.term_book(fr, base, term, (13, 6), OC.W, k_book, 8, k=k)
            rplain, oplain = list(R.plain), list(T.plain)
    finally:
        S24.CapBuilder, S24.optimize = orig
    rows = [list(lu.ids) for lu in book]
    return rows[:k_book], rows[k_book:], rplain, oplain


# ---- the tests ----
def test_the_pasted_lab_text_is_the_labs():
    src = (ROOT / "tests" / "test_shrink_star_flags.py").read_text()
    lines = src.splitlines(keepends=True)
    seen = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in LAB_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            assert hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest() == LAB_TEXT_SHA256[node.name], node.name
            seen.add(node.name)
    assert seen == set(LAB_TEXT_SHA256)


def test_shrink_and_stars_equal_the_labs():
    fr = frame_with_stars()
    pool = list(ur.frame_players(fr).values())
    prod = ur.proj_shrink(pool, 0.7, 500.0)
    lab = shrink(fr, fr.mean_projection.to_numpy(float))
    assert [prod[i] for i in fr.id.astype(str)] == [float(x) for x in lab]          # exact, value for value
    assert any(abs(prod[i] - p) > 1e-9 for i, p in zip(fr.id, fr.mean_projection))     # it moves something
    assert all(prod[i] == p for i, p, q in zip(fr.id, fr.mean_projection, fr.pos) if q == "DST")
    stars = ur.star_ids(fr, set(), 8000.0)
    assert stars == star_set(fr) and "p14" not in stars                                # $7,999 is not a star
    assert stars and all(q in ("RB", "WR", "TE") for i, q in zip(fr.id, fr.pos) if i in stars)


@pytest.mark.parametrize("arm", ["shrink", "star", "both"])
def test_the_book_equals_the_labs(monkeypatch, tmp_path, arm):
    fr = frame_with_stars()
    p = fp_path(tmp_path, fr)
    caps, _ = ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)
    te, low, _ = ur.row_rule_sets(p, fr, set(), 3.0)
    stars = ur.star_ids(fr, set(), 8000.0)
    with_star = arm in ("star", "both")
    bounds = [(te, 0, 1), (low, 0, 1)] + ([(stars, 1, 9)] if with_star else [])
    cons = [(sorted(te), "<=", 1), (sorted(low), "<=", 1)] + ([(sorted(stars), ">=", 1)] if with_star else [])
    sh = (0.7, 500.0) if arm in ("shrink", "both") else None
    base = shrink(fr, fr.mean_projection.to_numpy(float)) if sh else fr.mean_projection.to_numpy(float)
    book_p, spares_p, meta = production_book(monkeypatch, fr, caps, bounds, sh)
    book_l, spares_l, rplain, oplain = lab_book(fr, caps, cons, base)
    assert book_p == book_l and spares_p == spares_l
    assert [tuple(x) for x in meta["row_rules"]["resolved_without"]] == [tuple(x) for x in rplain]
    assert [tuple(x) for x in meta["own_cap"]["resolved_without"]] == [tuple(x) for x in oplain]
    if with_star:
        assert sum(1 for r in book_p if not any(i in stars for i in r)) <= len(rplain)    # every ruled row holds a star
    assert ("shrink" in meta) == (sh is not None)


def test_off_is_the_old_call_and_the_frame_is_untouched(monkeypatch, tmp_path):
    fr = frame_with_stars()
    before = fr.copy()
    p = fp_path(tmp_path, fr)
    caps, _ = ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)
    a = production_book(monkeypatch, fr, caps, None, None)
    b = production_book(monkeypatch, fr, caps, None, (0.7, 500.0))
    install_production(monkeypatch)
    rows, cells, meta, sp = ur.mix_rows(fr, set(), 26, 9, None, 0, OC.W, exposure_cap=13, dst_cap=6, fill="rr", spares=15,
                                        term_rows=8, term_bonus=OC.TERM, own_cap=caps)
    assert a[0] == [list(r) for r in rows] and "shrink" not in a[2] and b[0] != a[0]
    pd.testing.assert_frame_equal(fr, before)                                         # proj / mean_projection never rewritten


def test_the_cli():
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix",
            "--main-own-cap-delta", "15", "--main-own-cap-source", "f.csv", "--main-own-cap-fallback-share", "0.5"]
    with pytest.raises(SystemExit, match="rides with the row rules"):
        ur.main(base + ["--mix-min-star", "1"])
    with pytest.raises(SystemExit, match="takes \\[0.5, 1.0\\)"):
        ur.main(base + ["--proj-shrink-k", "0.4"])
    with pytest.raises(SystemExit, match="--mix-plan"):                               # valid: the next check, not ours
        ur.main(base + ["--mix-max-te", "1", "--mix-max-low-own", "1", "--mix-min-star", "1", "--proj-shrink-k", "0.7"])
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert "shrink=(a.proj_shrink_k, a.proj_shrink_window) if a.proj_shrink_k != 1.0 else None" in src
    assert 'row_bounds.append((stars, a.mix_min_star, 9))' in src
