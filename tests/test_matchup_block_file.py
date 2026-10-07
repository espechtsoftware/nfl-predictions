"""scripts/matchup_block_file.py (the live matchup term block, the operator 10-07): the same b_matchup as the paper arm's
writer for every FP-projected player, pred_own = bonus / 0.20 in the format own_bonus reads, every skill player once,
and the refusals. Offline."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import matchup_block_file as M  # noqa: E402
import paper_factor_file as PF  # noqa: E402
from test_paper_factor_file import _allowed, _fp, _frame  # noqa: E402


def test_the_block_bonus_is_the_paper_arms_b_matchup_and_pred_own_carries_it_at_tilt_020():
    fr, al = _frame(), _allowed()
    out, unmatched = M.build(fr, al, 2026, 3)
    assert list(out.columns) == M.COLUMNS and unmatched == 0
    assert len(out) == int((fr.pos != "DST").sum()) and out.dk_player_id.is_unique and "DST" not in set(out.pos)
    assert np.allclose(out.pred_own * M.TILT, out.bonus_points) and out.bonus_points.between(0, 2).all()
    paper, _ = PF.build(fr, _fp(fr), al, 2026, 3)                          # the paper arm's writer, same frame
    live = paper[paper.fp > 0].set_index("dk_player_id").b_matchup
    assert np.allclose(out.set_index("dk_player_id").loc[live.index, "bonus_points"], live)
    assert out.set_index("dk_player_id").loc["1002", "bonus_points"] >= 0   # no FP value: still in the block file


def test_refusals():
    fr, al = _frame(), _allowed()
    with pytest.raises(ValueError, match="no skill players"):
        M.build(fr[fr.pos == "DST"], al, 2026, 3)
    with pytest.raises(ValueError, match="no dk_player_id"):
        M.build(fr.assign(dk_player_id=fr.dk_player_id.where(fr.index != 2)), al, 2026, 3)
    flat = al.assign(pts=10.0)                                             # every defence alike: no z above 0
    with pytest.raises(ValueError, match="no player carries a matchup bonus"):
        M.build(fr, flat, 2026, 3)
