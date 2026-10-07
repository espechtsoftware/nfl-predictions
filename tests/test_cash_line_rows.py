"""Study 60's ladder rows (the format agreed with the reviewer 2026-10-07): roles from his big-win rule, the lines from
the ladder, written once and only under ~/private."""
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import cash_line_rows as C  # noqa: E402

PLAN = [
    {"contest_id": "1", "name": "milly", "entries": 2, "seats": 3, "big": True, "prize": "$500+ finish", "fee": 20.0},
    {"contest_id": "2", "name": "sat", "entries": 1, "seats": 1, "big": True, "prize": "NFL $4,444 ... Ticket", "fee": 13.0},
    {"contest_id": "3", "name": "supersat", "entries": 5, "seats": 25, "big": False, "prize": "$20 Millionaire Ticket", "fee": 1.0},
    {"contest_id": "4", "name": "mega", "entries": 1, "seats": 9, "big": True, "prize": "$500+ finish", "fee": 4444.0},
    {"contest_id": "5", "name": "ticketed", "entries": 1, "seats": 1, "big": True, "prize": "seat", "fee": 5.0, "ticket": True},
]


def _tiers():
    t = [("1", 100, 1, 1, 1000.0, 0.0), ("1", 100, 2, 3, 500.0, 0.0), ("1", 100, 4, 20, 40.0, 0.0),
         ("2", 400, 1, 1, 0.0, 4444.0),
         ("3", 594, 1, 25, 0.0, 20.0),
         ("4", 50, 1, 9, 600.0, 0.0), ("4", 50, 10, 12, 100.0, 0.0),
         ("5", 30, 1, 1, 0.0, 333.0)]
    df = pd.DataFrame(t, columns=["contest_id", "max_entries", "min_position", "max_position", "cash_value", "ticket_value"])
    df["source_sha256"] = "ab" * 32
    return df


def test_roles_follow_his_big_rule_with_precedence():
    assert [C.role_of(c) for c in PLAN] == ["gpp", "sat", None, "big", "big"]


def test_rows_carry_each_line_and_leave_non_big_out():
    out, warn = C.rows(PLAN, _tiers(), 5)
    assert [r["contest_id"] for r in out] == ["1", "2", "4", "5"]
    milly = out[0]
    assert (milly["role"], milly["entries"], milly["size"], milly["paid_places"], milly["cash500_last_position"],
            milly["seat_last_position"]) == ("gpp", 2, 100, 20, 3, 0)
    sat = out[1]
    assert (sat["role"], sat["paid_places"], sat["cash500_last_position"], sat["seat_last_position"]) == ("sat", 1, 0, 1)
    assert out[2]["cash500_last_position"] == 9 and out[2]["paid_places"] == 12
    assert warn == []


def test_a_line_that_disagrees_with_the_plan_warns():
    plan = [dict(PLAN[0], seats=5)]
    _, warn = C.rows(plan, _tiers(), 5)
    assert warn and "the ladder's line 3 != the plan's seats 5" in warn[0]


def test_a_big_contest_without_a_ladder_refuses_the_week():
    with pytest.raises(ValueError, match="has no ladder"):
        C.rows(PLAN, _tiers()[_tiers().contest_id != "2"], 5)


def test_two_captures_for_one_contest_refuse():
    t = _tiers()
    t.loc[t.index[0], "source_sha256"] = "cd" * 32
    with pytest.raises(ValueError, match="2 ladder captures"):
        C.rows(PLAN, t, 5)


def test_written_once_only_under_private(tmp_path, monkeypatch):
    monkeypatch.setattr(C, "PRIVATE", tmp_path / "private")
    out, _ = C.rows(PLAN, _tiers(), 5)
    p = C.write_once(out, tmp_path / "private" / "cash-line", 5)
    assert p.name == "cash-lines-w05.csv"
    assert p.read_text().splitlines()[0] == ",".join(C.COLUMNS)
    assert (p.parent / "cash-lines-w05.csv.sha256").read_text().split()[1] == "cash-lines-w05.csv"
    with pytest.raises(FileExistsError):
        C.write_once(out, tmp_path / "private" / "cash-line", 5)
    with pytest.raises(ValueError, match="not under"):
        C.write_once(out, tmp_path / "elsewhere", 5)
    assert "$" not in p.read_text()
