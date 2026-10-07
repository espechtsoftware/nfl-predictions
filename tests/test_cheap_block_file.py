"""scripts/cheap_block_file.py: the cheap-player term-block file (offline, synthetic frame)."""
import importlib.util
from pathlib import Path

import pandas as pd
import pytest

spec = importlib.util.spec_from_file_location("cheap_block_file", Path(__file__).resolve().parents[1] / "scripts" / "cheap_block_file.py")
CB = importlib.util.module_from_spec(spec); spec.loader.exec_module(CB)


def frame():
    return pd.DataFrame({"dk_player_id": [1, 2, 3, 4, 5, 6], "id": ["a", "b", "c", "d", "e", "BUF_DST"],
                         "display_name": list("ABCDEF"), "pos": ["QB", "RB", "WR", "TE", "WR", "DST"],
                         "team": ["X"] * 6, "opp": ["Y"] * 6, "salary": [6000, 3900, 4000, 3000, 3999, 2500]})


def test_bonus_only_under_4000_and_no_dst():
    out = CB.build(frame(), 2.0)
    assert list(out.columns) == CB.COLUMNS
    assert dict(zip(out.display_name, out.bonus_points)) == {"A": 0.0, "B": 2.0, "C": 0.0, "D": 2.0, "E": 2.0}
    assert "F" not in set(out.display_name)                            # the DST is omitted
    assert (out.pred_own * CB.TILT).round(6).tolist() == out.bonus_points.tolist()   # tilt 0.20 x pred_own = the bonus


def test_points_scale_the_bonus():
    assert CB.build(frame(), 4.0).bonus_points.max() == 4.0


@pytest.mark.parametrize("mutate, msg", [
    (lambda f: f.assign(pos="DST"), "no skill players"),
    (lambda f: f.assign(dk_player_id=[1, 1, 3, 4, 5, 6]), "duplicated"),
    (lambda f: f.assign(dk_player_id=[None, 2, 3, 4, 5, 6]), "no dk_player_id"),
    (lambda f: f.assign(salary=5000), "no player carries"),
])
def test_refusals(mutate, msg):
    with pytest.raises(ValueError, match=msg):
        CB.build(mutate(frame()), 2.0)


def test_non_positive_points_refused():
    with pytest.raises(ValueError, match="positive"):
        CB.build(frame(), 0.0)
