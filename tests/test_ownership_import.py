import pandas as pd
import pytest

from nfl_dfs.ingest.ownership_import import parse_lineup_slots, parse_standings_csv


def _write_export(path, with_summary=True):
    """Mimic a DK contest-standings export: entry columns on the left,
    per-player summary block on the right (sparser than entries)."""
    df = pd.DataFrame({
        "Rank": [1, 2, 3, 4],
        "EntryId": [11, 12, 13, 14],
        "EntryName": ["a", "b", "c", "d"],
        "Points": [180.1, 176.2, 150.0, 149.5],
        "Lineup": ["QB X RB Y", "QB X RB Z", "QB W RB Y", "QB W RB Z"],
        "Player": ["Josh Allen", "Bijan Robinson", None, None],
        "Roster Position": ["QB", "RB", None, None],
        "%Drafted": ["24.31%", "18.20%", None, None],
        "FPTS": [31.2, 22.4, None, None],
    })
    if not with_summary:
        df = df.drop(columns=["Player", "Roster Position", "%Drafted", "FPTS"])
    df.to_csv(path, index=False)
    return path


def test_parse_standings(tmp_path):
    out = parse_standings_csv(_write_export(tmp_path / "standings.csv"))
    assert len(out) == 2
    assert out.display_name.tolist() == ["Josh Allen", "Bijan Robinson"]
    assert out.pct_drafted.tolist() == pytest.approx([24.31, 18.20])
    assert out.roster_position.tolist() == ["QB", "RB"]


def test_parse_rejects_wrong_file(tmp_path):
    path = _write_export(tmp_path / "not_standings.csv", with_summary=False)
    with pytest.raises(ValueError, match="missing columns"):
        parse_standings_csv(path)


def test_slot_parser_preserves_names_and_order():
    slots = parse_lineup_slots(
        "QB Patrick Mahomes II RB James Cook III RB A Player "
        "WR A.J. Brown WR B Player WR C Player TE Travis Kelce "
        "FLEX D Player DST Chiefs"
    )
    assert len(slots) == 9
    assert slots[0] == {"slot": "QB", "player": "Patrick Mahomes II"}
    assert slots[1] == {"slot": "RB", "player": "James Cook III"}
    assert slots[-1] == {"slot": "DST", "player": "Chiefs"}
