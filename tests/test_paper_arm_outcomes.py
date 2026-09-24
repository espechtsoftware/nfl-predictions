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
