"""Study 89's ownership cap on the live MIX book (the operator 10-09: "Live W5 trial if built in time"): union_reselect's
own_cap_rows and mix_rows(own_cap=...) against the lab's OWN frozen code -- nfl2 experiments/s89_own_cap.py @ 4d0daa47 (file
sha256 92b09345...), its own_cap_rows and own_caps pasted BELOW byte for byte (each function's text sha-pinned) and run on
the lab's term_book (vendored, sha-pinned, in test_s71_bring_back_top_wr.py) with a CapBuilder stand-in that has
S24.CapBuilder's ban contract. ONE bans-aware stand-in optimizer serves both builds, so the same bans give the same rows:
the parity is the same 26 book rows, the same 15 spares and the same re-solves (cell, j), with and without infeasible ruled
solves; off is byte for byte the old call; a mutation (the cap one row looser) fails it."""
import ast
import hashlib
import importlib.util
import math
import sys
import types
from collections import Counter
from contextlib import contextmanager
from pathlib import Path

import numpy as np
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


T71 = _load("t71_helpers_own_cap", ROOT / "tests" / "test_s71_bring_back_top_wr.py")   # the lab's term_book + S18 / S24 stand-ins
S18, S24 = T71.S18, T71.S24                     # the pasted lab code below reads these names
SKILL = ("QB", "RB", "WR", "TE")
DELTA = 0.15
LAB_TEXT_SHA256 = {"own_cap_rows": "106844876271b256c4ad369b576e3056623965c3ff1f13a7100f27696e80e237",
                   "own_caps": "ff31668522c0b2626a179ba5e0fbb0e51c73e099a75d750d694b053ff9a8ff55"}


# ---- nfl2 experiments/s89_own_cap.py @ 4d0daa47, BYTE FOR BYTE (test_the_pasted_lab_text_is_the_labs) ----
def own_cap_rows(fr_pool: pd.DataFrame, pred_pct: np.ndarray, k_book: int, delta: float = DELTA) -> dict[str, int]:
    """Skill players only: id -> floor(k_book x (pred_own / 100 + delta)); DSTs absent (they keep production's DST cap)."""
    skill = fr_pool.pos.astype(str).isin(SKILL).to_numpy()
    return {str(i): int(math.floor(k_book * (float(p) / 100.0 + delta)))
            for i, p, s in zip(fr_pool.id.astype(str), pred_pct, skill) if s}


@contextmanager
def own_caps(cap_rows: dict[str, int], k_book: int):
    """Wrap the current S24.CapBuilder (inside S37.built_with): every solve with j < k_book (the book, in build order) also
    bans each player whose book rows so far reached his cap_rows; infeasible -> the same solve without those bans,
    recorded once. Spares (j >= k_book) never. Yields the class (`ruled` / `plain` lists of (cell, j); `bound`: the number
    of players banned by the rule at each book solve)."""
    orig_cls = S24.CapBuilder
    target = {id(S18.CELLS[c][1]): c for c in S18.CELLS}

    class OwnCapBuilder(orig_cls):
        ruled: list = []
        plain: list = []
        bound: list = []

        def solve_with(self, stack, qb_game_max, pair, extra_bans: set):
            j = len(self.prev)
            if j >= k_book:
                return super().solve_with(stack, qb_game_max, pair, extra_bans)
            cell = target.get(id(stack), "?")
            at = {p for p, c in self.count.items() if p in cap_rows and c >= cap_rows[p]}
            lu = super().solve_with(stack, qb_game_max, pair, set(extra_bans) | at)
            if lu is not None:
                type(self).ruled.append((cell, j)); type(self).bound.append(len(at))
                return lu
            type(self).plain.append((cell, j))
            return super().solve_with(stack, qb_game_max, pair, extra_bans)

    OwnCapBuilder.ruled, OwnCapBuilder.plain, OwnCapBuilder.bound = [], [], []
    S24.CapBuilder = OwnCapBuilder
    try:
        yield OwnCapBuilder
    finally:
        S24.CapBuilder = orig_cls


# ---- the fixture and the one stand-in optimizer ----
def frame(n_skill: int = 90, n_dst: int = 12) -> pd.DataFrame:
    rows = []
    for k in range(n_skill):
        rows.append({"id": f"p{k}", "name": f"P{k}", "pos": SKILL[k % 4], "team": f"T{k % 12}", "opp": f"T{(k % 12) ^ 1}",
                     "salary": 4000 + 61 * k, "game_id": f"g{(k % 12) // 2}", "dk_player_id": str(1000 + k),
                     "mean_projection": 30.0 - 0.25 * k + 0.01 * (k % 7)})
    for t in range(n_dst):
        rows.append({"id": f"d{t}", "name": f"D{t}", "pos": "DST", "team": f"T{t}", "opp": f"T{t ^ 1}", "salary": 3000,
                     "game_id": f"g{t // 2}", "dk_player_id": str(5000 + t), "mean_projection": 6.0 + 0.1 * t})
    return pd.DataFrame(rows)


def fp_file(tmp_path, fr: pd.DataFrame, missing=("p7",), scale=1.0) -> Path:
    """Fantasy Points' ownership export: fp_own_raw % for the skill players (minus `missing`), 0..~32, DSTs too."""
    out = []
    for i, pos, dk in zip(fr.id, fr.pos, fr.dk_player_id):
        if i in missing:
            continue
        k = int(i[1:])
        own = ((32.0 * math.exp(-k / 18.0) + (k % 5) * 0.37) if pos != "DST" else 8.0) * scale
        out.append({"dk_player_id": dk, "id": i, "pos": pos, "pred_own": own / 2, "fp_own_raw": own, "filled_from": "fp"})
    p = tmp_path / "ownership_fp-test.csv"
    pd.DataFrame(out).to_csv(p, index=False)
    return p


TRIGGER = {"p7", "p12", "p15"}                   # each reaches his cap in the fixture: a solve banning >= 2 is infeasible


def pick(pool, obj_col, prev, bans, fail_on_trigger):
    if fail_on_trigger and len(TRIGGER & set(bans or ())) >= 2:
        return None
    avail = [p for p in pool if not bans or p["id"] not in bans]
    order = sorted(avail, key=lambda p: (-float(p[obj_col]), str(p["id"])))
    if len(order) < 9:
        return None
    off = len(prev) % len(order)
    return [order[(off + j) % len(order)] for j in range(9)]


class _PLU:
    def __init__(self, players):
        self.players = players


def install_production(monkeypatch, fail_on_trigger):
    def optimize(pool, stack, objective_col, banned_lineups, max_overlap, bans, env, second_game_pair=None, qb_game_max=None,
                 interaction_floor_weights=None, interaction_floor=None):
        got = pick(pool, objective_col, banned_lineups, bans, fail_on_trigger)
        return _PLU(got) if got is not None else None
    lineup = types.ModuleType("nfl2.core.lineup"); lineup.optimize = optimize; lineup.StackRules = T71.StackRules
    for name, mod in (("nfl2", types.ModuleType("nfl2")), ("nfl2.core", types.ModuleType("nfl2.core")), ("nfl2.core.lineup", lineup)):
        monkeypatch.setitem(sys.modules, name, mod)


class _LU:
    def __init__(self, ids):
        self.ids = ids


class _BCapBuilder:
    """S24.CapBuilder's contract (nfl2 experiments/s24_qb_game_cap.py CapBuilder.solve_with): ban players at main_cap rows and
    DSTs at dst_cap rows plus the extra bans; solve; COMMIT a solved row (prev / count). Its optimize is the shared stand-in."""
    fail_on_trigger = False

    def __init__(self, fr, base, lam, main_cap, dst_cap):
        self.recs = [{"id": str(i), "obj": 0.0} for i in fr["id"]]
        self.dst = {str(i) for i, p in zip(fr["id"], fr["pos"]) if p == "DST"}
        self.main_cap, self.dst_cap = int(main_cap), int(dst_cap)
        self.prev, self.count = [], Counter()

    def solve_with(self, stack, qb_game_max, pair, extra_bans):
        bans = {p for p, c in self.count.items() if c >= self.main_cap} | {p for p, c in self.count.items() if p in self.dst and c >= self.dst_cap}
        got = pick(self.recs, "obj", self.prev, bans | set(extra_bans), _BCapBuilder.fail_on_trigger)
        if got is None:
            return None
        lu = _LU(tuple(p["id"] for p in got))
        self.prev.append(lu.ids); self.count.update(lu.ids)
        return lu


W = [3, 3] + [1] * 24
TERM = {f"p{k}": 2.0 for k in range(90) if (4000 + 61 * k) < 5500}     # a cheap-style block term (production: id -> points)


def production_book(monkeypatch, own_cap, fail_on_trigger=False, k=26, spares=15):
    install_production(monkeypatch, fail_on_trigger)
    rows, cells, meta, sp = ur.mix_rows(frame(), set(), k, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="rr",
                                        spares=spares, term_rows=8, term_bonus=TERM, own_cap=own_cap)
    return [list(r) for r in rows], [list(r) for r, _ in sp], meta


def lab_book(cap_rows, fail_on_trigger=False, k_book=26, k=41):
    fr = frame()
    base = fr.mean_projection.to_numpy(float)
    term = np.array([TERM.get(i, 0.0) for i in fr.id])
    S24.CapBuilder = _BCapBuilder; _BCapBuilder.fail_on_trigger = fail_on_trigger
    try:
        with own_caps(cap_rows, k_book) as T:
            book, cells, mt = T71.term_book(fr, base, term, (13, 6), W, k_book, 8, k=k)
            plain = list(T.plain)
    finally:
        S24.CapBuilder = T71._HCapBuilder
    rows = [list(lu.ids) for lu in book]
    return rows[:k_book], rows[k_book:], plain


# ---- the tests ----
def test_the_pasted_lab_text_is_the_labs():
    src = (ROOT / "tests" / "test_own_cap_flag.py").read_text()
    lines = src.splitlines(keepends=True)
    seen = set()
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in LAB_TEXT_SHA256:
            start = min([node.lineno] + [d.lineno for d in node.decorator_list])
            text = "".join(lines[start - 1:node.end_lineno])
            assert hashlib.sha256(text.encode()).hexdigest() == LAB_TEXT_SHA256[node.name], node.name
            seen.add(node.name)
    assert seen == set(LAB_TEXT_SHA256)


def lab_caps(fr: pd.DataFrame, fp_path: Path) -> dict:
    """The lab's input: pred_blend's form on the file (skill players, negatives clipped, the frame's skill sum -> 800%)."""
    f = pd.read_csv(fp_path, dtype={"id": str})
    raw = dict(zip(f.id, pd.to_numeric(f.fp_own_raw)))
    skill = fr.pos.astype(str).isin(SKILL).to_numpy()
    p = np.clip(np.array([raw.get(i, 0.0) for i in fr.id], dtype=float), 0.0, None) * skill
    p = p * (800.0 / p.sum())
    return own_cap_rows(fr, p, 26)


def test_cap_rows_equal_the_labs(tmp_path):
    fr = frame()
    caps, meta = ur.own_cap_rows(fp_file(tmp_path, fr), fr, set(), 15.0, 26, 0.9)
    assert caps == lab_caps(fr, fp_file(tmp_path, fr))
    assert caps["p7"] == math.floor(26 * 0.15) == 3 and meta["unnamed_skill_players_at_0"] == 1     # unnamed -> 0%
    assert not any(i.startswith("d") for i in caps) and meta["factor"] > 0 and meta["rescale_to"] == 800.0
    assert max(caps.values()) > 9 and meta["min_cap_rows"] == 3                                     # some above the 35% cap


@pytest.mark.parametrize("fail", [False, True])
def test_the_book_equals_the_labs_own_caps_on_term_book(monkeypatch, tmp_path, fail):
    fr = frame()
    caps, _ = ur.own_cap_rows(fp_file(tmp_path, fr), fr, set(), 15.0, 26, 0.9)
    book_p, spares_p, meta = production_book(monkeypatch, caps, fail)
    book_l, spares_l, plain_l = lab_book(caps, fail)
    assert book_p == book_l and spares_p == spares_l
    assert [tuple(x) for x in meta["own_cap"]["resolved_without"]] == [tuple(x) for x in plain_l]
    assert (len(plain_l) > 0) == fail                                   # the fallback path is exercised only when asked
    held = Counter(i for r in book_p for i in r)
    assert all(held[i] <= caps[i] for i in caps) or fail                 # the book never exceeds a cap without a fallback


def test_off_is_the_old_call_exactly(monkeypatch):
    a = production_book(monkeypatch, None)
    b = production_book(monkeypatch, {})
    install_production(monkeypatch, False)
    rows, cells, meta, sp = ur.mix_rows(frame(), set(), 26, 9, None, 0, W, exposure_cap=13, dst_cap=6, fill="rr", spares=15,
                                        term_rows=8, term_bonus=TERM)
    assert a[0] == b[0] == [list(r) for r in rows] and "own_cap" not in meta and "own_cap" not in a[2]


def test_a_looser_cap_is_caught(monkeypatch, tmp_path):
    fr = frame()
    caps, _ = ur.own_cap_rows(fp_file(tmp_path, fr), fr, set(), 15.0, 26, 0.9)
    loose = {i: c + 1 for i, c in caps.items()}                          # the mutation: one row looser in production only
    book_p, _, _ = production_book(monkeypatch, loose)
    book_l, _, _ = lab_book(caps)
    assert book_p != book_l


@pytest.mark.parametrize("bad, why", [("missing", "does not exist"), ("fractions", "fractions"), ("coverage", "names"),
                                      ("nocol", "needs fp_own_raw")])
def test_refusals(tmp_path, bad, why):
    fr = frame()
    if bad == "missing":
        p = tmp_path / "nope.csv"
    elif bad == "fractions":
        p = fp_file(tmp_path, fr, scale=0.02)
    elif bad == "coverage":
        p = fp_file(tmp_path, fr, missing=tuple(f"p{k}" for k in range(0, 90, 3)))
    else:
        p = fp_file(tmp_path, fr); pd.read_csv(p).drop(columns=["fp_own_raw"]).to_csv(p, index=False)
    with pytest.raises(SystemExit, match=f"OWN CAP REFUSED: .*{why}"):
        ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)


def test_the_cli_wiring_and_the_fallback_share():
    src = (ROOT / "scripts" / "union_reselect.py").read_text()
    assert src.count("own_cap=own_cap") == 2                            # the plain mix build and the ownership-term build
    assert 'own_cap_meta["fallback_cap_share"] = cap_share_used' in src and "!!! OWN CAP NOT APPLIED" in src
    assert '"exposure_cap_share": cap_share_used' in src
    assert '--main-own-cap-delta is defined for --main mix' in src
    assert "--main-own-cap-delta with --main-cap-share != 0.5 needs --main-own-cap-fallback-share" in src


def test_lag_filled_rows_count_as_unnamed_and_junk_is_refused(tmp_path):
    """ownership_fp.py writes fp_own_raw empty for the players FP does not price (filled_from lag): those players are
    unnamed (0% -> floor(k x delta) rows, the lab's form), never a refusal; a non-number that is not empty still refuses."""
    fr = frame()
    p = fp_file(tmp_path, fr)
    d = pd.read_csv(p, dtype=str)
    d.loc[d.id.isin(["p40", "p41"]), "fp_own_raw"] = None
    d.loc[d.id.isin(["p40", "p41"]), "filled_from"] = "lag"
    d.to_csv(p, index=False)
    caps, meta = ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)
    assert caps["p40"] == caps["p41"] == 3 and meta["rows_without_fp_own_raw"] == 2 and meta["unnamed_skill_players_at_0"] == 3
    d.loc[d.id == "p42", "fp_own_raw"] = "abc"                                # ("n/a" reads as empty, like pandas' other NA strings)
    d.to_csv(p, index=False)
    with pytest.raises(SystemExit, match="OWN CAP REFUSED: .*not numbers"):
        ur.own_cap_rows(p, fr, set(), 15.0, 26, 0.9)


def test_a_refused_cap_can_never_leave_the_flat_35_alone():
    base = ["--saturday-run", "x", "--t70-run", "y", "--live-dir", "z", "--entries", "26", "--main", "mix",
            "--main-cap-share", "0.35", "--main-own-cap-delta", "15"]
    with pytest.raises(SystemExit, match="needs --main-own-cap-fallback-share"):
        ur.main(base)
    with pytest.raises(SystemExit, match="--mix-plan"):                    # with the fallback share: the next check, not ours
        ur.main(base + ["--main-own-cap-fallback-share", "0.5"])
    with pytest.raises(SystemExit, match="--mix-plan"):                    # at 0.5 a refused cap builds today's book anyway
        ur.main(base[:-4] + ["--main-cap-share", "0.5", "--main-own-cap-delta", "15"])
