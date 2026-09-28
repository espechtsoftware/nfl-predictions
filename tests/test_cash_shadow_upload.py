"""cash_shadow_upload: the pure parts (cash_shadow.csv ids -> lineups against the frame; player dicts). The pinned lab's
dk_csv and the fail-closed upload writer are exercised by the chain smoke, not here."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cash_shadow_upload as cu  # noqa: E402

FRAME = pd.DataFrame({"id": [f"p{i}" for i in range(9)] + ["X_DST"], "name": [f"P{i}" for i in range(9)] + ["X"],
                      "pos": ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "RB", "DST"], "salary": [5000] * 10})


def test_ids_are_split_checked_and_ordered(tmp_path):
    f = tmp_path / "cash_shadow.csv"
    f.write_text("rank,players,ids,salary,proj\n1,a,p0|p1|p2|p3|p4|p5|p6|p7|X_DST,45000,120\n2,b,p0|p1|p2|p3|p4|p5|p6|p8|X_DST,45000,118\n")
    lus = cu.lineups_from_cash_csv(f, FRAME)
    assert lus[0] == ["p0", "p1", "p2", "p3", "p4", "p5", "p6", "p7", "X_DST"] and lus[1][7] == "p8"


def test_unknown_id_and_short_lineup_refuse(tmp_path):
    f = tmp_path / "cash_shadow.csv"
    f.write_text("rank,players,ids,salary,proj\n1,a,p0|p1|p2|p3|p4|p5|p6|zz|X_DST,45000,120\n")
    with pytest.raises(SystemExit, match="does not carry"):
        cu.lineups_from_cash_csv(f, FRAME)
    f.write_text("rank,players,ids,salary,proj\n1,a,p0|p1|p2,45000,120\n")
    with pytest.raises(SystemExit, match="not 9"):
        cu.lineups_from_cash_csv(f, FRAME)
    f.write_text("rank,players,salary\n1,a,45000\n")
    with pytest.raises(SystemExit, match="no ids column"):
        cu.lineups_from_cash_csv(f, FRAME)


def test_player_dicts_carry_what_dk_csv_needs():
    p = cu.player_dicts(FRAME)
    assert p["X_DST"] == {"id": "X_DST", "name": "X", "pos": "DST", "salary": 5000}
    assert cu._LU([p["p0"]]).players[0]["pos"] == "QB"
