"""Pre-upload exposure sheet: shares, majors shares, market source, and the flags that need a stated reason."""
import pandas as pd
import pytest

from nfl_dfs.inference.exposure_sheet import build_sheet, contest_blocks, majors_row_mask, sheet_markdown


def _players():
    return pd.DataFrame({
        "id": ["jj", "bijan", "sf", "ladd", "lamb", "qb", "rb2", "te", "dst2", "wr9"],
        "name": ["Justin Jefferson", "Bijan Robinson", "49ers", "Ladd McConkey", "CeeDee Lamb", "QB", "RB2", "TE", "DST2", "WR9"],
        "pos": ["WR", "RB", "DST", "WR", "WR", "QB", "RB", "TE", "DST", "WR"],
        "team": ["MIN", "ATL", "SF", "LAC", "DAL", "T", "T", "T", "U", "V"],
        "salary": [7800, 8200, 3800, 6200, 7300, 6000, 5000, 3200, 3000, 4000],
        "proj": [25.3, 21.7, 10.0, 17.2, 16.6, 20.0, 12.0, 9.0, 7.0, 8.0],
    })


def _book():
    base = ["qb", "bijan", "rb2", "jj", "lamb", "wr9", "te", "ladd", "sf"]
    alt = ["qb", "bijan", "rb2", "jj", "lamb", "wr9", "te", "ladd", "dst2"]
    return [base] * 6 + [alt] * 4          # 10 rows: jj/bijan/ladd in 100%, sf 60%, dst2 40%


def _contests():
    return [{"name": "milly", "entries": 1}, {"name": "flea", "entries": 4}, {"name": "supersat1a", "entries": 5}]


def test_blocks_and_majors_mask():
    assert contest_blocks(_contests()) == [{"name": "milly", "rows": [1, 1]}, {"name": "flea", "rows": [2, 5]}, {"name": "supersat1a", "rows": [6, 10]}]
    assert majors_row_mask(_contests(), 10).tolist() == [True] * 5 + [False] * 5


def test_sheet_flags_the_week2_patterns():
    ms = pd.DataFrame({"id": ["jj", "bijan", "lamb", "ladd", "qb"], "source": ["props", "props", "props", "model_only_no_line", "props"], "market_points": [16.4, 22.7, 16.7, None, 18.0]})
    sheet = build_sheet(_book(), _players(), _contests(), market_source=ms, status={"ladd": "Q"}, field_own={"bijan": 0.47})
    by = sheet.set_index("id")
    assert by.loc["jj", "rows"] == 10 and by.loc["jj", "share"] == 1.0 and by.loc["jj", "majors_share"] == 1.0
    assert "over_30" in by.loc["jj", "flags"] and "majors_over_20" in by.loc["jj", "flags"] and "market_gap" in by.loc["jj", "flags"]
    assert by.loc["bijan", "flags"] == ""                          # chalk parity: field ownership 47% licenses the share
    assert by.loc["sf", "flags"].split(",") == ["over_30", "majors_over_20", "dst_over_20"]
    assert "injured_over_10" in by.loc["ladd", "flags"] and "no_line_over_5" in by.loc["ladd", "flags"] and by.loc["ladd", "market_source"] == "model_only_no_line"
    assert by.loc["lamb", "market_source"] == "props" and "market_gap" not in by.loc["lamb", "flags"]
    assert by.loc["dst2", "share"] == pytest.approx(0.4) and by.loc["dst2", "majors_share"] == 0.0 and by.loc["dst2", "flags"] == "over_30,dst_over_20"
    md = sheet_markdown(sheet)
    assert md.startswith("10 players held; ") and "| Justin Jefferson |" in md and "over_30" in md


def test_sheet_rejects_layout_mismatch_and_short_rows():
    with pytest.raises(ValueError, match="covers"):
        build_sheet(_book(), _players(), [{"name": "milly", "entries": 3}])
    with pytest.raises(ValueError, match="nine"):
        build_sheet([["qb"] * 8], _players(), [{"name": "milly", "entries": 1}])
