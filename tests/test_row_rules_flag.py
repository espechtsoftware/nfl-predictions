"""Study 91's row rules on the live MIX book (the operator 10-09: "use it in week 5" if better on both draws): union_reselect's
row_rule_sets and mix_rows(row_bounds=...) against the lab's OWN code -- study 38 amendment 6p (nfl2 experiments/
s38_paper_corun.py @ b03ddaac): its _dk, low_owned and row_rules pasted BELOW byte for byte (each function's text sha-pinned),
row_rules entered before study 89's own_caps (pasted in test_own_cap_flag.py) on the lab's term_book (vendored in
test_s71_bring_back_top_wr.py), with ONE stand-in optimizer that reads the lab's set_constraints and production's member_bounds
alike: the same TE / low-owned sets, the same 26 book rows, 15 spares and re-solves (some forced); off is the old call."""
import ast
import hashlib
import importlib.util
import sys
import types
from collections import Counter
from contextlib import contextmanager
from functools import partial
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


OC = _load("own_cap_helpers_rr", ROOT / "tests" / "test_own_cap_flag.py")     # 89's own_caps (pasted), the fixture, T71
T71 = OC.T71
S18, S24 = T71.S18, T71.S24                     # the pasted lab code below reads these names
LOW_OWN_PCT = 3.0                               # s38's constant (the pasted low_owned's default)
LAB_TEXT_SHA256 = {"_dk": "e99395d5612500379ceb12ec66eae161de83e102c8b1e46558640170e9151845",
                   "low_owned": "df8a59279f9ffa958dffc8fef36cc8532f5f5b503262f8d838a05aaea1b03f6f",
                   "row_rules": "47727594a2fd8ea68199f7d9d738057b03ba8dce95b0b67bc6bd96ef9fafcfde"}


def sha256(p: Path) -> str:                     # s38's helper of the same name (read by the pasted low_owned)
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ---- nfl2 experiments/s38_paper_corun.py @ b03ddaac, BYTE FOR BYTE (test_the_pasted_lab_text_is_the_labs) ----
def _dk(x) -> str | None:
    """A DK player id as text ('123', never '123.0'); None when missing."""
    if x is None or (isinstance(x, float) and not np.isfinite(x)) or str(x).strip() in ("", "nan", "None"):
        return None
    try:
        return str(int(float(x)))
    except ValueError:
        return str(x).strip()


def low_owned(path: Path, pool: pd.DataFrame, pct: float = LOW_OWN_PCT) -> tuple[set[str], dict]:
    """Amendment 6p: the pool's SKILL players whose FP projected ownership -- the ownership_fp file's fp_own_raw, FP's raw % --
    is below `pct`, matched by the frame id, then the DK id (production's own_cap_rows order); a blank fp_own_raw (lag-filled)
    or a player the file does not name counts as 0% (low). A non-number or a missing column refuses (ValueError)."""
    d = pd.read_csv(path, dtype=str)
    if "fp_own_raw" not in d.columns or "id" not in d.columns:
        raise ValueError(f"{Path(path).name} lacks id / fp_own_raw")
    raw = d["fp_own_raw"].fillna("").astype(str).str.strip()
    num = pd.to_numeric(raw.where(raw != ""), errors="coerce")
    if bool((num.isna() & (raw != "")).any()):
        raise ValueError(f"{Path(path).name}: a non-number fp_own_raw")
    by_id = {str(i): float(v) for i, v in zip(d["id"], num) if pd.notna(v)}
    by_dk = ({k: float(v) for i, v in zip(d["dk_player_id"], num) if pd.notna(v) and (k := _dk(i)) is not None}
             if "dk_player_id" in d.columns else {})
    dks = pool["dk_player_id"] if "dk_player_id" in pool.columns else pd.Series([None] * len(pool))
    low, named, n_skill = set(), 0, 0
    for i, dk, pos in zip(pool.id.astype(str), dks, pool.pos.astype(str)):
        if pos not in ("QB", "RB", "WR", "TE"):
            continue
        n_skill += 1
        v = by_id.get(i)
        if v is None and _dk(dk) is not None:
            v = by_dk.get(_dk(dk))
        named += v is not None
        if v is None or v < pct:
            low.add(i)
    return low, {"source": Path(path).name, "source_sha256": sha256(Path(path)), "low_own_pct": pct, "pool_skill_players": n_skill,
                 "named": named, "low_owned": len(low)}


@contextmanager
def row_rules(cons: list, k_book: int):
    """Amendment 6p: wrap the current S24.CapBuilder (inside S37.built_with): every BOOK solve (j < k_book) carries `cons` as
    set_constraints, ONE solve; infeasible -> the same solve without them, recorded (cell, j). Spares never. Entered BEFORE
    own_caps (the ownership cap wraps it), so an infeasible solve drops the row rules first and keeps the ownership cap
    (study 87's qb_price_rules pattern, set_constraints only)."""
    orig_cls, orig_opt = S24.CapBuilder, S24.optimize
    target = {id(S18.CELLS[c][1]): c for c in S18.CELLS}

    class RowRuleBuilder(orig_cls):
        ruled: list = []
        plain: list = []

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            j = len(self.prev)
            if j >= k_book or not cons:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            cell = target.get(id(stack), "?")
            S24.optimize = partial(orig_opt, set_constraints=list(cons))
            try:
                lu = super().solve_with(stack, qb_game_max, pair, extra_bans)
            finally:
                S24.optimize = orig_opt
            if lu is not None:                           # recorded on THIS class by name: own_caps subclasses it with
                RowRuleBuilder.ruled.append((cell, j))   # its own `ruled` / `plain`, so type(self) would write into those
                return lu
            RowRuleBuilder.plain.append((cell, j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    RowRuleBuilder.ruled, RowRuleBuilder.plain = [], []
    S24.CapBuilder = RowRuleBuilder
    try:
        yield RowRuleBuilder
    finally:
        S24.CapBuilder, S24.optimize = orig_cls, orig_opt


# ---- one stand-in optimizer for both builds ----
FORCE_NONE_AT = {5, 12, 20}                     # a ruled solve at these row indices is infeasible (the fallback path)


def pick(pool, obj_col, prev, bans, bounds):
    """The objective order (ties: id) rotated by the rows so far, skipping banned players and any player that would push a
    bounded set over its upper bound; 9 players or None. bounds: [(ids, hi)]."""
    if bounds and len(prev) in FORCE_NONE_AT:
        return None
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj_col]), str(p["id"])))
    if len(order) < 9:
        return None
    off = len(prev) % len(order)
    rot = order[off:] + order[:off]
    sets = [(set(ids), hi) for ids, hi in (bounds or [])]
    held = [0] * len(sets)
    out = []
    for p in rot:
        hit = [k for k, (ids, _) in enumerate(sets) if p["id"] in ids]
        if any(held[k] >= sets[k][1] for k in hit):
            continue
        out.append(p)
        for k in hit:
            held[k] += 1
        if len(out) == 9:
            return out
    return None


class _PLU:
    def __init__(self, players):
        self.players = players


def install_production(monkeypatch):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 interaction_floor_weights=None, interaction_floor=None, member_bounds=None):
        assert all(lo == 0 for _, lo, _ in (member_bounds or ()))
        got = pick(pool, objective_col, banned_lineups, bans, [(ids, hi) for ids, _, hi in (member_bounds or ())])
        return _PLU(got) if got is not None else None
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = optimize; lineup.StackRules = T71.StackRules
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")), ("nfl2.core.lineup", lineup)):
        monkeypatch.setitem(sys.modules, name, mod)


class _LU:
    def __init__(self, ids):
        self.ids = ids


def _lab_optimize(recs, stack, objective_col, banned_lineups, bans, set_constraints=None):
    assert all(op == "<=" for _, op, _ in (set_constraints or ()))
    got = pick(recs, objective_col, banned_lineups, bans, [(ids, hi) for ids, _, hi in (set_constraints or ())])
    return _LU(tuple(p["id"] for p in got)) if got is not None else None


class _SCapBuilder:
    """S24.CapBuilder's contract (main / DST caps + extra bans; COMMIT a solved row) calling the MODULE's S24.optimize, so the
    pasted row_rules' set_constraints (a partial on S24.optimize) reach the stand-in."""

    def __init__(self, fr, base, lam, main_cap, dst_cap):
        self.recs = [{"id": str(i), "obj": 0.0} for i in fr["id"]]
        self.dst = {str(i) for i, p in zip(fr["id"], fr["pos"]) if p == "DST"}
        self.main_cap, self.dst_cap = int(main_cap), int(dst_cap)
        self.prev, self.count = [], Counter()

    def solve_with(self, stack, qb_game_max, pair, extra_bans):
        bans = {p for p, c in self.count.items() if c >= self.main_cap} | {p for p, c in self.count.items() if p in self.dst and c >= self.dst_cap}
        lu = S24.optimize(self.recs, stack=stack, objective_col="obj", banned_lineups=self.prev, bans=bans | set(extra_bans))
        if lu is not None:
            self.prev.append(lu.ids); self.count.update(lu.ids)
        return lu


W = OC.W
TERM = OC.TERM


def sets_of(tmp_path):
    fr = OC.frame()
    p = OC.fp_file(tmp_path, fr)
    d = pd.read_csv(p, dtype=str)
    d.loc[d.id.isin(["p40", "p41"]), "fp_own_raw"] = None                       # lag-filled rows: 0% (low)
    d.loc[d.id == "p50", "id"] = "x50"                                            # named only by the DK id
    d.to_csv(p, index=False)
    return fr, p


def production_book(monkeypatch, own_cap, bounds, k=26, spares=15):
    install_production(monkeypatch)
    rows, cells, meta, sp = ur.mix_rows(OC.frame(), set(), k, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="rr",
                                        spares=spares, term_rows=8, term_bonus=TERM, own_cap=own_cap, row_bounds=bounds)
    return [list(r) for r in rows], [list(r) for r, _ in sp], meta


def lab_book(cap_rows, cons, k_book=26, k=41):
    fr = OC.frame()
    base = fr.mean_projection.to_numpy(float)
    term = np.array([TERM.get(i, 0.0) for i in fr.id])
    S24.CapBuilder, S24.optimize = _SCapBuilder, _lab_optimize
    try:
        with row_rules(cons, k_book) as R, OC.own_caps(cap_rows, k_book) as T:
            book, cells, mt = T71.term_book(fr, base, term, (13, 6), W, k_book, 8, k=k)
            rplain, oplain = list(R.plain), list(T.plain)
    finally:
        S24.CapBuilder, S24.optimize = T71._HCapBuilder, None
    rows = [list(lu.ids) for lu in book]
    return rows[:k_book], rows[k_book:], rplain, oplain


# ---- the tests ----
def test_the_pasted_lab_text_is_the_labs():
    src = (ROOT / "tests" / "test_row_rules_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    seen = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in LAB_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            assert hashlib.sha256("".join(lines[start - 1:node.end_lineno]).encode()).hexdigest() == LAB_TEXT_SHA256[node.name], node.name
            seen.add(node.name)
    assert seen == set(LAB_TEXT_SHA256)


def test_the_sets_equal_6ps_low_owned(tmp_path):
    fr, p = sets_of(tmp_path)
    te, low, meta = ur.row_rule_sets(p, fr, set(), 3.0)
    low_lab, meta_lab = low_owned(p, fr, 3.0)
    assert low == low_lab and {"p40", "p41"} <= low and "p50" not in low or "p50" in low_lab
    assert te == {i for i, q in zip(fr.id, fr.pos) if q == "TE"} and meta["low_owned"] == meta_lab["low_owned"]
    assert meta["named"] == meta_lab["named"] and not any(i.startswith("d") for i in low)


@pytest.mark.parametrize("which", ["te", "both"])
def test_the_book_equals_6ps_row_rules_inside_89s_own_caps(monkeypatch, tmp_path, which):
    fr, p = sets_of(tmp_path)
    caps, _ = ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)
    te, low, _ = ur.row_rule_sets(p, fr, set(), 3.0)
    bounds = [(te, 0, 1)] + ([(low, 0, 1)] if which == "both" else [])
    cons = [(sorted(te), "<=", 1)] + ([(sorted(low), "<=", 1)] if which == "both" else [])
    book_p, spares_p, meta = production_book(monkeypatch, caps, bounds)
    book_l, spares_l, rplain, oplain = lab_book(caps, cons)
    assert book_p == book_l and spares_p == spares_l
    assert [tuple(x) for x in meta["row_rules"]["resolved_without"]] == [tuple(x) for x in rplain] and len(rplain) == len(FORCE_NONE_AT)
    assert [tuple(x) for x in meta["own_cap"]["resolved_without"]] == [tuple(x) for x in oplain]
    bad = sum(1 for r in book_p if sum(i in te for i in r) > 1 or (which == "both" and sum(i in low for i in r) > 1))
    assert bad <= len(rplain)                                            # only a re-solved (forced) row may break a rule
    held = [sum(i in te for i in r) for r in spares_p]                    # spares never carry the rule (it binds in the book)


def test_off_is_the_old_call_exactly(monkeypatch, tmp_path):
    fr, p = sets_of(tmp_path)
    caps, _ = ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)
    a = production_book(monkeypatch, caps, None)
    b = production_book(monkeypatch, caps, [])
    assert a[0] == b[0] and a[1] == b[1] and "row_rules" not in a[2] and "row_rules" not in b[2]


def test_a_looser_bound_is_caught(monkeypatch, tmp_path):
    fr, p = sets_of(tmp_path)
    caps, _ = ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)
    te, low, _ = ur.row_rule_sets(p, fr, set(), 3.0)
    book_p, _, _ = production_book(monkeypatch, caps, [(te, 0, 2)])                 # the mutation: two TEs allowed
    book_l, _, _, _ = lab_book(caps, [(sorted(te), "<=", 1)])
    assert book_p != book_l


def test_refusals_and_the_cli(tmp_path):
    fr, p = sets_of(tmp_path)
    with pytest.raises(SystemExit, match="ROW RULES REFUSED: .*does not exist"):
        ur.row_rule_sets(tmp_path / "nope.csv", fr, set(), 3.0)
    d = pd.read_csv(p, dtype=str); d.loc[d.id == "p3", "fp_own_raw"] = "abc"; d.to_csv(p, index=False)
    with pytest.raises(SystemExit, match="ROW RULES REFUSED: .*non-number"):
        ur.row_rule_sets(p, fr, set(), 3.0)
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix"]
    with pytest.raises(SystemExit, match="defined for --main mix with the ownership cap"):
        ur.main(base + ["--mix-max-te", "1"])
    with pytest.raises(SystemExit, match="take 1"):
        ur.main(base + ["--main-own-cap-delta", "15", "--main-own-cap-source", "f.csv", "--main-own-cap-fallback-share", "0.5",
                        "--mix-max-te", "2"])
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert src.count("row_bounds=row_bounds") == 2 and "!!! ROW RULES NOT APPLIED" in src and '"the ownership cap is not applied"' in src
