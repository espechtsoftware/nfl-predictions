import importlib.util
from pathlib import Path

import pandas as pd
import pytest

_P = Path(__file__).resolve().parents[1] / "scripts" / "ownership_sets.py"
_spec = importlib.util.spec_from_file_location("ownership_sets", _P)
osets = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(osets)


def _pred():
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "DST", "WR", "RB"]
    return pd.DataFrame({"pos": pos, "pred_own": [30, 25, 2, 18, 1, 9, 0.5, 15, 3, 4.0]})


def test_sets_are_rank_defined_and_sized_by_the_shares():
    s = osets.assign_sets(_pred(), chalk_share=0.2, low_share=0.5)
    assert sorted(s.loc[s.set == "CHALK", "pred_own"]) == [25, 30]          # top 2 of 10
    low = s[s.set == "LOW"]
    assert len(low) == round(0.5 * 9)                                        # 9 skill players
    assert set(low.pos) <= set(osets.SKILL)                                  # DST never LOW
    assert low.pred_own.max() <= s[(s.set == "MID") & s.pos.isin(osets.SKILL)].pred_own.min()


def test_chalk_is_never_empty_even_with_compressed_predictions():
    p = _pred().assign(pred_own=lambda d: d.pred_own / 10)                   # nobody predicted >= 20%
    s = osets.assign_sets(p, chalk_share=0.01, low_share=0.3)
    assert (s.set == "CHALK").sum() == 1


def test_set_shares_counts_chalk_over_all_and_low_over_skill_only():
    h = pd.DataFrame({"season": 2024, "week": 1,
                      "pos": ["QB", "WR", "WR", "DST"], "own": [25.0, 3.0, 10.0, 1.0]})
    chalk, low = osets.set_shares(h)
    assert chalk == pytest.approx(1 / 4)
    assert low == pytest.approx(1 / 3)
