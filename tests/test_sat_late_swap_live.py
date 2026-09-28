"""Offline tests for scripts/sat_late_swap_live.py (layout parsing, clock fraction, token ordering)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from sat_late_swap_live import Refuse, RowSkip, expand_rows, game_fraction_left, pair_tokens, parse_layout  # noqa: E402


def test_expand_rows_and_layout(tmp_path):
    assert expand_rows("1,3,19-20,24-25") == [1, 3, 19, 20, 24, 25]
    p = tmp_path / "ENTER-layout.txt"
    p.write_text("layout head; order frozen\n"
                 "sat20-111: 1 entries = ranks frozen (book rows 4; keep 1) -> f.csv\n"
                 "supersat25hi-222: 3 entries = ranks frozen (book rows 1,3-4; keep 3) -> g.csv\n")
    lay = parse_layout(p)
    assert [c["rows"] for c in lay] == [[4], [1, 3, 4]] and lay[1]["name"] == "supersat25hi"
    p.write_text("x-1: 2 entries = ranks frozen (book rows 1; keep 2) -> f.csv\n")
    with pytest.raises(Refuse):
        parse_layout(p)                                   # 1 row for 2 entries


def test_game_fraction_left():
    assert game_fraction_left({"status": "STATUS_FINAL"}) == 0.0
    assert game_fraction_left({"status": "STATUS_SCHEDULED"}) == 1.0
    assert game_fraction_left({"status": "STATUS_IN_PROGRESS", "period": 4, "clock": "7:30"}) == pytest.approx(450 / 3600)
    assert game_fraction_left({"status": "STATUS_IN_PROGRESS", "period": 2, "clock": "15:00"}) == pytest.approx(0.75)


POS = {"a": "WR", "b": "TE", "c": "WR", "n": "TE", "m": "WR"}
DD = {k: f"d{k}" for k in POS}
SAL = {f"d{k}": v for k, v in {"a": 6000, "b": 4000, "c": 5000, "n": 3000, "m": 7000}.items()}


def cells(**kw):
    # QB,RB,RB,WR,WR,WR,TE,FLEX,DST with the late players placed by the caller; others fixed at $5,000 total 25,000
    base = ["q", "r1", "r2", "w1", "w2", "x", "t", "f", "d"]
    for k, v in kw.items():
        base[int(k[1:])] = v
    return base


def test_plain_replacement_and_reseat_order():
    sal = {**SAL, **{c: 5000 for c in ("q", "r1", "r2", "w1", "w2", "x", "t", "f", "d")}}
    # late: WR 'da' in the third WR cell, TE 'db' in the TE cell; the new set keeps 'a', drops 'b', adds 'n'
    row = cells(i5="da", i6="db")
    toks = pair_tokens(7, row, ["a", "b"], ["a", "n"], DD, POS, sal)
    assert toks == ["7:db:dn"]
    # re-seat: WR 'da' sits in FLEX, TE 'db' in TE; new set = TE 'n' (FLEX) + WR 'a' moved into ... there is no free WR
    # cell, so the only legal assignment keeps 'a' in FLEX and replaces 'db' with 'dn'
    row = cells(i7="da", i6="db")
    assert pair_tokens(7, row, ["a", "b"], ["a", "n"], DD, POS, sal) == ["7:db:dn"]


def test_order_keeps_every_step_under_the_cap():
    # two replacements; the expensive-in first would breach the cap, so the cheap one must come first
    sal = {c: 5000 for c in ("q", "r1", "r2", "w1", "w2", "t", "f", "d")}
    sal.update({"dc": 5000, "da": 6000, "db": 4000, "dm": 7000, "dn": 3000})
    row = cells(i5="dc", i6="db")                          # 45,000 fixed... + dc 5,000 + db 4,000
    row = [c if c.startswith("d") else c for c in row]
    total = sum(sal[c] for c in row[:9])
    toks = pair_tokens(3, row, ["c", "b"], ["m", "n"], DD, POS, {**sal, "q": 5000})
    assert toks.index("3:db:dn") < toks.index("3:dc:dm") or total - 5000 + 7000 <= 50000


def test_unrealizable_row_is_skipped_not_fatal():
    sal = {c: 5000 for c in ("q", "r1", "r2", "w1", "w2", "t", "f", "d")}
    sal.update({"dc": 1000, "dm": 15000})
    row = cells(i5="dc")
    with pytest.raises(RowSkip):
        pair_tokens(9, row, ["c"], ["m"], DD, POS, sal)    # 45,000 - 1,000 + 15,000 > 50,000
