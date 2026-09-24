"""Monday per-contest-type bundle scoring (reports/lab-handoffs/paper_bundle_outcomes.py)."""
import importlib.util
from pathlib import Path

import numpy as np
import pytest

_P = Path(__file__).resolve().parents[1] / "reports" / "lab-handoffs" / "paper_bundle_outcomes.py"
_spec = importlib.util.spec_from_file_location("paper_bundle_outcomes", _P)
pbo = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pbo)
HDR = "QB,RB,RB,WR,WR,WR,TE,FLEX,DST\n"


def _file(d, name, cid, rows, k=None):
    (d / f"ENTER-{name}-{cid}-{len(rows)}-entries-KEEP-first-{k if k is not None else len(rows)}.csv").write_text(
        HDR + "".join(",".join(r) + "\n" for r in rows))


def test_bundle_scores_per_contest_and_groups_by_type(tmp_path):
    _file(tmp_path, "sat20", 11, [["a"] * 9]); _file(tmp_path, "sat20", 12, [["b"] * 9])
    _file(tmp_path, "supersat2", 21, [["a"] * 9, ["b"] * 9])
    (tmp_path / "ENTER-all-rows-1-to-3-are-the-KEEPERS.csv").write_text(HDR)       # ignored
    contests = pbo.read_bundle(tmp_path)
    per = pbo.score_bundle(contests, {"a": 22.0, "b": 10.0}, np.array([100.0, 150.0, 250.0]))
    t = pbo.by_type(per)
    assert t.loc["sat20", "contests"] == 2 and t.loc["sat20", "contest_best"] == (198.0 + 90.0) / 2
    assert t.loc["supersat2", "contest_best"] == 198.0 and t.loc["supersat2", "ge194"] == 1
    assert t.loc["supersat2", "field_above_best"] == pytest.approx(1 / 3)


def test_a_file_whose_rows_disagree_with_its_name_is_refused(tmp_path):
    (tmp_path / "ENTER-ffwc-31-4-entries-KEEP-first-4.csv").write_text(HDR + ",".join(["a"] * 9) + "\n")
    with pytest.raises(SystemExit, match="declares 4"):
        pbo.read_bundle(tmp_path)
