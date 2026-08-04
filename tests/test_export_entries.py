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


def test_locked_flex_cell_fills_position_aware():
    """Regression (2026-08-04 audit): locked cell in the FLEX slot, but
    the new lineup slot_orders that player into a hard slot —
    sequential fill shifted every later cell one slot (QB cell got an
    RB, etc.). Position-aware fill must put an eligible player in every
    open slot; a genuinely un-arrangeable lock leaves the row untouched
    (the old code wrote an invalid row instead)."""
    import csv as _csv
    import io as _io

    from nfl_dfs.optimizer.export import fill_entries_csv

    # FEASIBLE: 3-RB lineup — Thu Guy (RB) locked in the FLEX cell,
    # both hard RB slots still fillable.
    names = ["Q", "R1", "R2", "Thu Guy", "W1", "W2", "W3", "T", "D"]
    pos = ["QB", "RB", "RB", "RB", "WR", "WR", "WR", "TE", "DST"]
    row = ("555,C,9,$5,X0 (1),X1 (1),X2 (1),X3 (1),X4 (1),X5 (1),X6 (1),"
           "Thu Guy (LOCKED),X8 (1)")
    out = fill_entries_csv(_entries([row]), [_lu(names, pos)])
    r = list(_csv.reader(_io.StringIO(out)))
    hdr, filled = r[0], r[1]
    by_name = dict(zip(names, pos))
    for i in range(4, 13):
        cell, slot = filled[i], hdr[i]
        if "LOCKED" in cell:
            assert slot == "FLEX"
            continue
        ppos = by_name[cell.split(" (")[0]]
        assert (ppos == slot) or (slot == "FLEX" and ppos in
                                  ("RB", "WR", "TE")), \
            f"slot {slot} got {ppos}"

    # INFEASIBLE: 2-RB lineup, one RB locked into FLEX -> no second RB
    # for the hard slot; row must be left untouched, not written invalid.
    names2 = ["Q", "R1", "Thu Guy", "W1", "W2", "W3", "T", "W4", "D"]
    pos2 = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    diff = []
    out2 = fill_entries_csv(_entries([row]), [_lu(names2, pos2)],
                            diff_out=diff)
    assert diff[0]["untouched"] is True and "X0" in out2


def test_lock_aware_assignment_prevents_stranding():
    """Regression (2026-08-04 audit): the churn assignment could give
    the only lock-compatible lineup to an unlocked entry, stranding a
    selected lineup while the locked row goes untouched."""
    from nfl_dfs.optimizer.export import fill_entries_csv

    with_lock = ["Thu Guy"] + [f"A{i}" for i in range(8)]
    without = [f"B{i}" for i in range(9)]
    # locked entry currently resembles the B lineup MORE (so naive
    # overlap would hand B to it and fail the lock check)
    locked_row = ("666,C,9,$5,Thu Guy (LOCKED)," +
                  ",".join([f"B{i} (1)" for i in range(1, 9)]))
    free_row = "777,C,9,$5," + ",".join([f"A{i} (1)" for i in range(8)]
                                        + ["Z (1)"])
    diff = []
    out = fill_entries_csv(_entries([locked_row, free_row]),
                           [_lu(with_lock), _lu(without)], diff_out=diff)
    d_locked = next(d for d in diff if d["entry_id"] == "666")
    assert d_locked["untouched"] is False, "lock-compatible lineup stranded"
    assert "B0" in out.splitlines()[2], "free row should get the B lineup"


def test_contest_id_filter_fills_only_that_contest():
    """Multi-contest DKEntries: filter fills the named contest's rows;
    other contests' rows pass through verbatim."""
    from nfl_dfs.optimizer.export import fill_entries_csv

    a = [f"A{i}" for i in range(9)]
    r1 = "111,Qual,900,$5," + ",".join([f"X{i} (1)" for i in range(9)])
    r2 = "222,Milly,901,$5," + ",".join([f"Y{i} (1)" for i in range(9)])
    out = fill_entries_csv(_entries([r1, r2]), [_lu(a)], contest_id="900")
    lines = out.strip().splitlines()
    assert "A0" in lines[1] and "Y0 (1)" in lines[2] and "A0" not in lines[2]
    import pytest

    with pytest.raises(ValueError):
        fill_entries_csv(_entries([r1]), [_lu(a)], contest_id="999")


def test_massive_lock_late_swap_stress():
    """External review 4.1: 6 of 9 cells locked (1pm games started),
    the 4pm swap must fill the remaining 3 slots position-aware."""
    from nfl_dfs.optimizer.export import fill_entries_csv

    names = ["Q", "R1", "R2", "W1", "W2", "W3", "T", "W4", "D"]
    pos = ["QB", "RB", "RB", "WR", "WR", "WR", "TE", "WR", "DST"]
    cells = ["Q (LOCKED)", "R1 (LOCKED)", "R2 (LOCKED)", "W1 (LOCKED)",
             "W2 (LOCKED)", "X5 (1)", "T (LOCKED)", "X7 (1)", "X8 (1)"]
    row = "888,C,9,$5," + ",".join(cells)
    diff = []
    out = fill_entries_csv(_entries([row]), [_lu(names, pos)], diff_out=diff)
    line = out.strip().splitlines()[1]
    assert diff[0]["untouched"] is False
    assert line.count("LOCKED") == 6
    for pn in ("W3", "W4", "D"):
        assert pn in line, f"{pn} missing from swap fill"
