"""linestar_ownership_capture: the period lookup, the Main-slate projected-ownership parse, the refusals, and a full run on a
saved payload (no network)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import linestar_ownership_capture as lc  # noqa: E402

PAYLOAD = {"Ownership": {"Slates": [{"Id": 77, "SlateName": "Main", "Mode": 0}, {"Id": 78, "SlateName": "Showdown", "Mode": 1}],
                         "Projected": {"77": [{"SalaryId": 1, "Owned": 22.5}, {"SalaryId": 2, "Owned": 3.1}]}},
           "SalaryContainerJson": json.dumps({"Salaries": [{"Id": 1, "Name": "A. Player", "POS": "wr", "PTEAM": "X", "OTEAM": "Y", "SAL": 7000, "PID": 11},
                                                           {"Id": 2, "Name": "B. Player", "POS": "RB", "PTEAM": "Y", "OTEAM": "X", "SAL": 5000, "PID": 12},
                                                           {"Id": 3, "Name": "C. Player", "POS": "TE", "PTEAM": "X", "OTEAM": "Y", "SAL": 3000, "PID": 13}]})}


def test_period_lookup():
    periods = [{"Id": 500, "Name": "Week 3, 2026"}, {"Id": 501, "Name": "Week 4, 2026"}, {"Id": 9, "Name": "Showdown"}]
    assert lc.period_id(periods, 2026, 4) == 501
    with pytest.raises(SystemExit, match="no period"):
        lc.period_id(periods, 2026, 5)


def test_projected_rows_parse_and_refusals():
    rows, meta = lc.projected_rows(PAYLOAD)
    assert [r["name"] for r in rows] == ["A. Player", "B. Player"] and rows[0]["pos"] == "WR" and rows[0]["own_proj"] == 22.5
    assert meta == {"slate_id": 77, "projected_rows": 2, "salary_rows": 3}
    with pytest.raises(SystemExit, match="no Main slate"):
        lc.projected_rows({"Ownership": {"Slates": []}, "SalaryContainerJson": "{}"})
    with pytest.raises(SystemExit, match="no projected ownership"):
        lc.projected_rows({"Ownership": {"Slates": [{"Id": 77, "SlateName": "Main", "Mode": 0}], "Projected": {}}, "SalaryContainerJson": "{}"})


def test_main_writes_csv_payload_and_receipt(tmp_path):
    pl = tmp_path / "payload.json"; pl.write_text(json.dumps(PAYLOAD))
    out = tmp_path / "out"
    with pytest.raises(SystemExit, match="not filled"):
        lc.main(["--season", "2026", "--week", "4", "--out", str(out), "--label", "test", "--payload", str(pl)])   # 2 rows < 100
    assert lc.main(["--season", "2026", "--week", "4", "--out", str(out), "--label", "test", "--payload", str(pl), "--min-rows", "2"]) == 0
    files = sorted(p.name for p in out.iterdir())
    assert any(f.endswith(".csv") for f in files) and any(f.endswith(".receipt.json") for f in files) and any(f.endswith(".payload.json") for f in files)
    rec = json.loads(next(out.glob("*.receipt.json")).read_text())
    assert rec["rows"] == 2 and rec["label"] == "test" and rec["captured_at_utc"].endswith("+00:00") and len(rec["csv_sha256"]) == 64
