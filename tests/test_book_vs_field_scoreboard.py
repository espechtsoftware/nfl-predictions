import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_P = Path(__file__).resolve().parents[1] / "scripts" / "book_vs_field_scoreboard.py"
_spec = importlib.util.spec_from_file_location("book_vs_field_scoreboard", _P)
sb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sb)


def _frame():
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST", "QB"]
    return pd.DataFrame({
        "display_name": [f"p{i}" for i in range(10)], "position": pos,
        "gsis_id": [f"g{i}" for i in range(10)], "proj": [20, 15, 12, 14, 10, 8, 7, 6, 5, 9.0],
        "dk_player_id": list(range(100, 110)), "dk_draftable_id": list(range(900, 910)),
    })


def test_dead_slot_and_played_gap():
    fr = _frame()
    played = {f"g{i}" for i in range(10)} - {"g1"}          # p1 (RB) did not play
    real = {"p0": 30.0, "p2": 12.0, "p8": 5.0}               # others realized 0
    a = sb.player_arrays(fr, played, real, "proj")
    s = sb.summarize(a, np.array([list(range(9))]))
    assert s["dnp_slots"] == 1.0
    assert s["proj"] == pytest.approx(97.0)
    assert s["realized"] == pytest.approx(47.0)
    # played skill players: p0 +10, p2 0, p3..p7 -(14+10+8+7+6); DST and the dead RB excluded
    assert s["gap_played"] == pytest.approx(10 - 45)


def test_book_rows_detects_id_column_and_fails_closed():
    fr = _frame()
    book = pd.DataFrame([list(range(100, 109))])
    assert sb.book_rows(fr, book).tolist() == [list(range(9))]
    with pytest.raises(SystemExit):
        sb.book_rows(fr, pd.DataFrame([list(range(100, 108)) + [999]]))


def test_name_rows_drops_unmatched_lineups():
    fr = _frame()
    keys = pd.Series(["|".join(f"p{i}" for i in range(9)), "|".join(["zz"] + [f"p{i}" for i in range(1, 9)])])
    rows, ok = sb.name_rows(fr, keys)
    assert ok.tolist() == [True, False] and rows.shape == (1, 9)
