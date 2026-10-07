"""Priority-first dealing (the operator 10-07): the one pure function the lab copies verbatim, and the union's use of it."""
import ast
import sys
from pathlib import Path

import pandas as pd
import pytest

from nfl_dfs.inference import priority_deal as PD

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402

# a slate: game A @ B and game C @ D; 8 skill players a side plus a DST
INFO = {}
for t, o in (("A", "B"), ("B", "A"), ("C", "D"), ("D", "C")):
    INFO[f"{t}qb"] = ("QB", t, o, 6000)
    for k in range(1, 7):
        INFO[f"{t}{k}"] = (["RB", "WR", "TE"][k % 3], t, o, 3500 if k >= 5 else 6000)   # {t}5 and {t}6 are under 4,000
    INFO[f"{t}dst"] = ("DST", t, o, 2500)
POS, TEAM, OPP, SAL = ({k: v[i] for k, v in INFO.items()} for i in range(4))


def _order(rows, fixed=(), scores=False):
    return PD.priority_order(rows, POS, TEAM, OPP, SAL, fixed, return_scores=scores)


def _score(row):
    return _order([row], scores=True)[1][0]


def test_the_score_parts_follow_the_monitor_definitions():
    assert _score(["Aqb", "A1", "A2", "B1", "A5", "A6", "C1", "C2", "Cdst"]) == 4      # QB+4, bring-back, 2 cheap (A5 A6)
    assert _score(["Aqb", "A1", "C1", "C2", "C3", "C4", "D1", "D2", "Ddst"]) == 0      # QB+1, nothing else
    assert _score(["Aqb", "A1", "A2", "C1", "C2", "C3", "C4", "D1", "Ddst"]) == 2      # QB+2 exactly
    assert _score(["Aqb", "A1", "B1", "C1", "C2", "C3", "C4", "D1", "Ddst"]) == 1      # QB+1 + a bring-back
    assert _score(["Aqb", "A1", "C5", "C6", "C1", "C2", "C3", "D1", "Ddst"]) == 1      # QB+1 + 2 cheap (another game)


def test_dsts_never_count_and_4000_is_not_cheap():
    assert _score(["Aqb", "A1", "C1", "C2", "C3", "C4", "D1", "D2", "Adst"]) == 0      # his own DST is not a teammate
    assert _score(["Aqb", "A1", "C1", "C2", "C3", "C4", "D1", "D2", "Bdst"]) == 0      # the opponent's DST is not a bring-back
    sal = dict(SAL, C5=4000, C6=3999)
    row = ["Aqb", "A1", "C5", "C6", "C1", "C2", "C3", "D1", "Ddst"]
    assert PD.priority_order([row], POS, TEAM, OPP, sal, return_scores=True)[1] == [0]  # 4,000 is not under 4,000
    sal["C5"] = 3999
    assert PD.priority_order([row], POS, TEAM, OPP, sal, return_scores=True)[1] == [1]


def test_the_order_is_stable_and_highest_first():
    q1 = ["Aqb", "A1", "C1", "C2", "C3", "C4", "D1", "D2", "Ddst"]                  # 0
    q2 = ["Aqb", "A1", "A2", "C1", "C2", "C3", "C4", "D1", "Ddst"]                  # 2
    q4 = ["Aqb", "A1", "A2", "B1", "A5", "A6", "C1", "C2", "Cdst"]                  # 4
    assert _order([q1, q2, q1, q4, q2]) == [3, 1, 4, 0, 2]                          # ties keep the book order


def test_block_positions_keep_their_rows_and_the_rest_sort_among_theirs():
    q0 = ["Aqb", "A1", "C1", "C2", "C3", "C4", "D1", "D2", "Ddst"]
    q4 = ["Aqb", "A1", "A2", "B1", "A5", "A6", "C1", "C2", "Cdst"]
    rows = [q0, q0, q4, q0, q4, q0]
    p, s = _order(rows, fixed=[1, 4], scores=True)
    assert s == [0, 0, 4, 0, 4, 0]
    assert p[1] == 1 and p[4] == 4                                                   # the block rows stay
    assert p == [2, 1, 0, 3, 4, 5]                                                   # the free 4 sort over free slots


def test_the_week5_shape_sends_the_three_lowest_free_rows_to_23_24_26():
    hi = ["Aqb", "A1", "A2", "B1", "A5", "A6", "C1", "C2", "Cdst"]                   # 4
    lo = ["Aqb", "A1", "C1", "C2", "C3", "C4", "D1", "D2", "Ddst"]                   # 0
    block = [1, 4, 8, 11, 14, 17, 21, 24]
    rows = [lo if i in (0, 2, 3) else hi for i in range(26)]                         # the three low rows sit at 1, 3, 4
    p = _order(rows, fixed=block)
    assert [p[i] for i in block] == block
    assert sorted(p) == list(range(26))
    assert {p[22], p[23], p[25]} == {0, 2, 3}                                        # 1-based 23, 24, 26


def test_bad_inputs_fail_closed():
    two_qbs = ["Aqb", "Bqb", "C1", "C2", "C3", "C4", "D1", "D2", "Ddst"]
    with pytest.raises(ValueError, match="exactly one QB"):
        _order([two_qbs])
    row = ["Aqb", "A1", "C1", "C2", "C3", "C4", "D1", "D2", "Ddst"]
    for bad in ([1], [-1], [True], ["0"]):
        with pytest.raises(ValueError, match="block positions"):
            _order([row], fixed=bad)
    with pytest.raises(KeyError):
        _order([row[:-1] + ["nobody"]])


def test_the_module_is_stdlib_only_with_one_function_for_the_lab_copy():
    tree = ast.parse(Path(PD.__file__).read_text())
    imports = [n for n in ast.walk(tree) if isinstance(n, (ast.Import, ast.ImportFrom))]
    assert [(getattr(n, "module", None)) for n in imports] == ["__future__"]
    assert [n.name for n in tree.body if isinstance(n, ast.FunctionDef)] == ["priority_order"]


def _union_inputs():
    fr = pd.DataFrame([{"id": k, "pos": v[0], "team": v[1], "opp": v[2], "salary": v[3]} for k, v in INFO.items()])
    hi = ["Aqb", "A1", "A2", "B1", "A5", "A6", "C1", "C2", "Cdst"]
    lo = ["Aqb", "A1", "C1", "C2", "C3", "C4", "D1", "D2", "Ddst"]
    rosters = [["x"]] * 3 + [lo, hi, lo, hi]                                         # the book is rosters 3..6
    return fr, rosters, [3, 4, 5, 6]


def test_the_union_keeps_a_live_blocks_rows_and_records_the_order():
    fr, rosters, book = _union_inputs()
    new, meta = ur.apply_priority_order(book, rosters, fr, {"blocks": ["L", "T", "L", "L"]}, ["C", "A1", "C", "A1"], [3, 2, 1, 1])
    assert new == [6, 4, 3, 5]                                                       # position 1 (the block) stays; 6 (hi) leads
    assert meta["fixed_positions"] == [1] and meta["scores_in_book_order"] == [0, 4, 0, 4] and meta["moved"] == 3
    assert meta["entry_shares_after"] == {"A1": round(5 / 7, 4), "A2": 0.0, "B": 0.0, "C": round(2 / 7, 4)}
    assert len(meta["module_sha256"]) == 64
    new, meta = ur.apply_priority_order(book, rosters, fr, None)                     # no block: every row sorts
    assert new == [4, 6, 3, 5] and meta["fixed_positions"] == []


def test_the_union_falls_back_loudly_and_keeps_the_book():
    fr, rosters, book = _union_inputs()
    new, meta = ur.priority_order_or_fallback(book, rosters, fr.drop(columns=["opp"]), None)
    assert new == book and "lacks ['opp']" in meta["not_applied"]
    new, meta = ur.priority_order_or_fallback(book, rosters, fr, {"blocks": ["L", "T"]})
    assert new == book and "position list" in meta["not_applied"]


@pytest.mark.parametrize("extra", [["--main", "pmo_x50"], ["--winner-order", "x.csv"], ["--main-own-tilt", "0.2"],
                                   ["--mix-rs-rows", "9"], ["--mix-cover-games", "2"]])
def test_the_union_refuses_untested_combinations(tmp_path, extra):
    base = ["--saturday-run", "auto", "--t70-run", str(tmp_path), "--live-dir", str(tmp_path), "--entries", "26",
            "--main", "mix", "--mix-portfolio", "mix", "--mix-plan", str(tmp_path / "c.json"), "--priority-order"]
    if extra[0] == "--main":
        base[base.index("--main") + 1] = extra[1]
        extra = []
    with pytest.raises(SystemExit, match="--priority-order needs"):
        ur.main(base + extra)
