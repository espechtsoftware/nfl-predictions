"""Monday paper-arm outcome line (reports/lab-handoffs/paper_arm_outcomes.py): endpoint arithmetic and book specs."""
import importlib.util
from pathlib import Path

import numpy as np

_P = Path(__file__).resolve().parents[1] / "reports" / "lab-handoffs" / "paper_arm_outcomes.py"
_spec = importlib.util.spec_from_file_location("paper_arm_outcomes", _P)
pao = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pao)


def test_finish_share_counts_field_entries_strictly_above_the_book_best():
    field = np.array([150.0, 190.0, 200.0, 200.0, 230.0])
    out = pao.outcomes(np.array([120.0, 200.0, 195.0]), field)
    assert out["finish_share_above_best"] == 0.2          # only 230 is strictly above 200
    assert out["book_best"] == 200.0 and out["clears_194"] == 2 and out["clears_220"] == 0 and out["n"] == 3


def test_book_spec_defaults_to_the_run_dir_book(tmp_path):
    label, run, book = pao.parse_book(f"c_low2={tmp_path}")
    assert (label, run, book) == ("c_low2", tmp_path, tmp_path / "book.csv")
    assert pao.parse_book(f"entered={tmp_path}@{tmp_path}/e.csv")[2] == tmp_path / "e.csv"


def test_sizes_spec_expands_in_contest_order():
    c = pao.parse_sizes("wildcat:2x2,ffwc:4")
    assert [(x["name"], x["entries"]) for x in c] == [("wildcat", 2), ("wildcat", 2), ("ffwc", 4)]


def test_snake_deals_unique_rows_and_reverses_each_round():
    c = pao.parse_sizes("a:2,b:2,c:3")
    assert pao.snake_ranks(c) == [[0, 5], [1, 4], [2, 3, 6]]


def test_layout_line_scores_each_contest_through_the_order():
    import pytest
    pytest.importorskip("nfl_dfs.inference.enter_layout")
    ids = [["p1"], ["p2"], ["p3"], ["p4"]]                   # p1, p2 are LOW: fewest-low puts rows 3, 4 first
    pts = np.array([100.0, 90.0, 80.0, 200.0])
    rows = {r["layout"]: r for r in pao.layout_lines(ids, pts, pao.parse_sizes("a:2,b:2"), {"p1", "p2"})}
    assert rows["sequential/greedy"]["contest_best"] == 150.0      # contests hold rows {1,2} and {3,4}: bests 100, 200
    assert rows["top/fewest-low"]["contest_best"] == 200.0 and rows["top/fewest-low"]["contest_mean"] == 140.0
    assert rows["snake/fewest-low"]["distinct_rows"] == 4 and rows["top/fewest-low"]["distinct_rows"] == 2


def test_sizes_spec_carries_rank_pins():
    c = pao.parse_sizes("milly20:1@1,sat13:1@2,wildcat:2x2")
    assert c[0]["ranks"] == [1] and c[1]["ranks"] == [2] and "ranks" not in c[2] and len(c) == 4
