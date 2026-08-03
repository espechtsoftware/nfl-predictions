"""Min-churn entries fill: assignment, locked handling, diff."""

import numpy as np

from nfl_dfs.optimizer.lineup import Lineup


def _lu(names, pos=None):
    pos = pos or ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    players = [{"id": i, "name": n, "pos": p, "salary": 5000, "proj": 10.0}
               for i, (n, p) in enumerate(zip(names, pos))]
    return Lineup(players=players)


HDR = "Entry ID,Contest Name,Contest ID,Entry Fee,QB,RB,RB,WR,WR,WR,TE,FLEX,DST"


def _entries(rows):
    return HDR + "\n" + "\n".join(rows) + "\n"


def test_min_churn_assignment_and_diff():
    from nfl_dfs.optimizer.export import fill_entries_csv

    a = [f"A{i}" for i in range(9)]
    b = [f"B{i}" for i in range(9)]
    # entry 1 currently holds mostly-B, entry 2 mostly-A -> assignment
    # must give entry 1 the B lineup and entry 2 the A lineup.
    e1 = "111,C,9,$5," + ",".join([f"B{i} (1)" for i in range(8)] + ["A8 (1)"])
    e2 = "222,C,9,$5," + ",".join([f"A{i} (1)" for i in range(8)] + ["B8 (1)"])
    diff = []
    out = fill_entries_csv(_entries([e1, e2]), [_lu(a), _lu(b)], diff_out=diff)
    lines = out.strip().splitlines()
    assert "B0" in lines[1] and "A0" in lines[2]
    d1 = next(d for d in diff if d["entry_id"] == "111")
    assert d1["out"] == ["A8"] and d1["in"] == ["B8"]


def test_locked_row_kept_when_lineup_lacks_locked_player():
    from nfl_dfs.optimizer.export import fill_entries_csv

    locked_row = "333,C,9,$5,Thu Guy (LOCKED)," + ",".join(
        [f"X{i} (1)" for i in range(8)])
    diff = []
    out = fill_entries_csv(_entries([locked_row]),
                           [_lu([f"A{i}" for i in range(9)])], diff_out=diff)
    assert "Thu Guy (LOCKED)" in out and "A0" not in out
    assert diff[0]["untouched"] is True


def test_locked_cell_preserved_when_lineup_contains_player():
    from nfl_dfs.optimizer.export import fill_entries_csv

    names = ["Thu Guy"] + [f"A{i}" for i in range(8)]
    locked_row = "444,C,9,$5,Thu Guy (LOCKED)," + ",".join(
        [f"X{i} (1)" for i in range(8)])
    out = fill_entries_csv(_entries([locked_row]), [_lu(names)])
    line = out.strip().splitlines()[1]
    assert "Thu Guy (LOCKED)" in line and "A0" in line
