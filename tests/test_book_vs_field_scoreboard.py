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


def test_corpus_shape_counts_low_and_chalk_by_slot_summed_ownership():
    fr = _frame()
    own = {"p0": 25.0, "p1": 3.0, "p2": 4.0, "p3": 2.0, "p4": 30.0, "p5": 10.0, "p6": 1.0, "p7": 8.0, "p8": 50.0}
    a = sb.player_arrays(fr, {f"g{i}" for i in range(10)}, {}, "proj", own)
    s = sb.summarize(a, np.array([list(range(9))]))
    # skill players under 5%: p1, p2, p3, p6 -> 4 (DST p8 never counts as low)
    assert s["pct_3plus_low"] == 100.0 and s["pct_0to1_low"] == 0.0
    assert s["pct_no_chalk"] == 0.0


def test_heavy_user_mask_reads_the_declared_entry_count():
    names = pd.Series(["a (3/150)", "b (1/20)", "c", "d (51/51)", "e (2/151)"])
    assert sb.heavy_user_mask(names).tolist() == [True, False, False, True, False]


def test_information_lines_identity_and_signs():
    # 12 players; the field owns 9 slots per lineup in total, like the book
    rng = np.random.default_rng(0)
    proj = rng.uniform(5, 20, 12); real = proj + rng.normal(0, 4, 12)
    own = np.full(12, 9 / 12)                                         # field: every player at 75% of a slot
    salary = np.linspace(3000, 8000, 12)
    a = {"proj": proj, "real": real, "own": own, "salary": salary}
    best = np.argsort(-(real - proj))[:9]                             # a book holding the 9 best residuals in every lineup
    idx = np.tile(best, (4, 1))
    out = sb.information_lines(a, idx)
    assert out["sum_a_p"] == pytest.approx(out["book_mean_minus_own_field_mean"])   # the identity
    assert out["IC"] > 0.5 and out["players"] == 12
    assert 0 < out["active_share"] <= 1
