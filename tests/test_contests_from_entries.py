"""contests_from_entries: the export's four header columns -> contests.json rows; non-main draft groups split out; refusals."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import contests_from_entries as ce  # noqa: E402

HEAD = "Entry ID,Contest Name,Contest ID,Entry Fee,QB,RB,RB,WR,WR,WR,TE,FLEX,DST,,Instructions\n"


def _export(tmp_path, rows):
    f = tmp_path / "DKEntries.csv"
    f.write_text(HEAD + "".join(f"{i},{n},{c},${fee},,,,,,,,,,,\n" for i, (n, c, fee) in enumerate(rows, 1)))
    return f


def test_labels_are_derived_from_dk_names():
    assert ce.short_label("NFL $2.75M Fantasy Football Millionaire [$1M to 1st]") == "milly"
    assert ce.short_label("NFL $4,444 Fantasy Football Millionaire Satellite") == "sat"
    assert ce.short_label("NFL Fantasy Football Millionaire Super Satellite [25 Tickets]") == "supersat"
    assert ce.short_label("$14M 2026 Fantasy Football World Championship Qualifier") == "ffwc"
    assert ce.short_label("NFL $6K Huddle [Single Entry] (Thu-Mon)") == "huddle"
    assert ce.short_label("NFL $333 Wild Card Satellite") == "wildcat"
    assert ce.short_label("NFL SUPERSat to $20 NFL Fantasy Football Millionaire [25x]") == "supersat"
    assert ce.short_label("NFL $490 2026 FFWC Qualifier Satellite") == "ffwc"


def test_export_rows_count_entries_per_contest_and_refuse_two_names(tmp_path):
    f = _export(tmp_path, [("A [20 Entry Max]", "1", "20"), ("A [20 Entry Max]", "1", "20"), ("B", "2", "5")])
    ex = ce.read_export(f)
    assert ex["1"] == {"dk_name": "A [20 Entry Max]", "fee": 20.0, "entries": 2} and ex["2"]["entries"] == 1
    g = _export(tmp_path / "g", []) if False else None
    bad = tmp_path / "bad.csv"; bad.write_text(HEAD + "1,A,1,$20,,,,,,,,,,,\n2,A renamed,1,$20,,,,,,,,,,,\n")
    with pytest.raises(SystemExit, match="two names"):
        ce.read_export(bad)


def test_build_splits_the_main_draft_group_from_the_others_and_refuses_missing_details(tmp_path):
    f = _export(tmp_path, [("NFL Millionaire", "10", "20"), ("Sat 1", "11", "13"), ("Sat 2", "12", "13"), ("Huddle (Thu-Mon)", "20", "5")])
    ex = ce.read_export(f)
    details = {"10": {"draftGroupId": 500}, "11": {"draftGroupId": 500}, "12": {"draftGroupId": 500}, "20": {"draftGroupId": 501}}
    main, other, group = ce.build(ex, details, None, set())
    assert group == "500" and [r["name"] for r in main] == ["milly", "sat1", "sat2"] and [r["name"] for r in other] == ["huddle"]
    assert main[0]["keep"] == main[0]["entries"] == 1 and other[0]["draft_group"] == "501"
    main2, other2, _ = ce.build(ex, details, "501", set())
    assert [r["name"] for r in main2] == ["huddle"] and len(other2) == 3
    with pytest.raises(SystemExit, match="lacks a contest"):
        ce.build(ex, {k: v for k, v in details.items() if k != "12"}, None, set())


def test_cli_writes_main_and_other_files(tmp_path, capsys):
    f = _export(tmp_path, [("NFL Millionaire", "10", "20"), ("Huddle (Thu-Mon)", "20", "5")])
    d = tmp_path / "details.json"; d.write_text(json.dumps({"10": {"draftGroupId": 500}, "20": {"draftGroupId": 501}}))
    out = tmp_path / "contests.json"
    assert ce.main(["--entries", str(f), "--details", str(d), "--out", str(out), "--group", "500"]) == 0
    assert json.loads(out.read_text())[0]["contest_id"] == "10"
    assert json.loads(out.with_suffix(".other.json").read_text())[0]["contest_id"] == "20"
    assert "NOT on the main slate" in capsys.readouterr().out
