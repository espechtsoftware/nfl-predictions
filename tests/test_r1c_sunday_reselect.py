"""R1(c) paper Sunday re-selection: the drop rule and the re-selection on the T-70 banks."""
import importlib.util
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

_P = Path(__file__).resolve().parents[1] / "scripts" / "r1c_sunday_reselect.py"
_spec = importlib.util.spec_from_file_location("r1c", _P)
r1c = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(r1c)


def _t70():
    return pd.DataFrame({"id": ["a", "b", "c", "d", "e"], "pos": ["QB", "WR", "WR", "RB", "DST"],
                         "status": ["None", "OUT", "Q", "None", "None"], "roster_status": ["ACT"] * 5,
                         "dk_player_id": [1, 2, 3, 4, 5]})


def test_drop_rule_covers_missing_out_and_the_dk_snapshot():
    cands = pd.DataFrame({"players": ["a,c,e", "a,b,e", "a,z,e", "a,d,e"], "book_rank": [1, None, 2, None]})
    inc = np.arange(50, dtype=float).reshape(5, 10); hs = inc + 1
    top = lambda mat, k: list(np.argsort(-mat.mean(axis=1))[:k])
    book, rec = r1c.reselect(cands, _t70(), inc, hs, 2, top)
    assert rec["dropped_missing_from_t70"] == 1 and rec["dropped_unavailable"] == 1 and rec["survivors"] == 2
    assert set(book.players) == {"a,c,e", "a,d,e"}                        # Questionable c stays; OUT b and unknown z go
    snap = pd.DataFrame({"id": ["4"], "status": ["O"]})                  # d ruled out on the post-10:30 DK pull
    with pytest.raises(SystemExit, match="only 1"):
        r1c.reselect(cands, _t70(), inc, hs, 2, top, snap)


def test_inactive_roster_status_drops_a_skill_player_but_not_a_dst():
    t = _t70(); t.loc[t.id == "d", "roster_status"] = "INA"; t.loc[t.id == "e", "roster_status"] = None
    assert r1c.unavailable_ids(t) == {"b", "d"}
