import csv
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from dk_status_snapshot import rows_from_draftables, write_snapshot  # noqa: E402


def test_snapshot_matches_the_relayout_format(tmp_path):
    payload = {"draftables": [
        {"playerId": 7, "status": "OUT", "competition": {"startTime": "2026-10-04T20:25:00.0000000Z"}},
        {"playerId": 7, "status": "OUT", "competition": {"startTime": "2026-10-04T20:25:00.0000000Z"}},   # FLEX slot row
        {"playerId": 3, "status": "None", "competition": {"startTime": "2026-10-04T17:00:00.0000000Z"}},
        {"playerId": 5, "status": None, "competition": None}]}
    seen = rows_from_draftables(payload)
    assert seen == {"7": ("OUT", "2026-10-04T20:25:00.0000000Z"), "3": ("", "2026-10-04T17:00:00.0000000Z"), "5": ("", "")}
    out = tmp_path / "dk-status.csv"; write_snapshot(seen, out)
    rows = list(csv.DictReader(out.open()))
    assert [r["id"] for r in rows] == ["3", "5", "7"] and rows[2]["status"] == "OUT" and not (tmp_path / "dk-status.csv.tmp").exists()
