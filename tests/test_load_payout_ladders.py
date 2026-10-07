"""scripts/load_payout_ladders.py (P1): DraftKings contest-details captures become one row per payout tier; refusals
before any write; the per-contest structure in fee multiples. Offline (synthetic captures)."""
import importlib.util
import json
from pathlib import Path

import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("load_payout_ladders", ROOT / "scripts" / "load_payout_ladders.py")
L = importlib.util.module_from_spec(spec); spec.loader.exec_module(L)


def _tier(lo, hi, value, kind="Cash"):
    return {"minPosition": lo, "maxPosition": hi, "tierPayoutDescriptions": {kind: "x"},
            "payoutDescriptions": [{"payoutDescriptionType": "Text", "order": 1, "value": value}]}


def _capture():
    return {
        "1": {"name": "GPP", "entryFee": 20, "maximumEntries": 100, "entries": 100, "maximumEntriesPerUser": 150,
              "draftGroupId": 9, "contestStartTime": "2026-10-11T17:00:00.0000000Z", "totalPayouts": 1690.0,
              "payoutSummary": [_tier(2, 2, 300.0), _tier(1, 1, 1000.0), _tier(3, 15, 30.0)]},
        "2": {"name": "Sat", "entryFee": None, "fee": 10, "max": 20, "entries": 7, "draftGroupId": 9, "totalPayouts": 170.0,
              "payoutSummary": [_tier(1, 2, 85.0, "Ticket")]},
    }


def test_tiers_sorted_numbered_and_valued_per_position():
    rows = L.ladder_rows(_capture(), 2026, 5, "f.json", "abc", "2026-10-06T10:00:00+00:00")
    g = [r for r in rows if r["contest_id"] == "1"]
    assert [(r["tier"], r["min_position"], r["max_position"], r["cash_value"]) for r in g] == [(1, 1, 1, 1000.0), (2, 2, 2, 300.0), (3, 3, 15, 30.0)]
    s = [r for r in rows if r["contest_id"] == "2"]
    assert s[0]["entry_fee"] == 10.0 and s[0]["max_entries"] == 20 and s[0]["ticket_value"] == 85.0 and s[0]["cash_value"] == 0.0
    assert set(rows[0]) | {"loaded_at"} == set(L.COLUMNS)


def test_structure_in_fee_multiples_and_the_flat_ladder_break_even():
    st = L.structure(L.ladder_rows(_capture(), 2026, 5, "f.json", "abc", "t")).set_index("contest_id")
    assert st.loc["1", "kind"] == "cash" and st.loc["1", "paid"] == 15 and st.loc["1", "pool_ratio"] == 0.845
    assert st.loc["1", "first_x"] == 50.0 and st.loc["1", "min_cash_x"] == 1.5 and pd.isna(st.loc["1", "break_even_x_field_rate"])
    assert st.loc["2", "kind"] == "ticket" and st.loc["2", "pool_ratio"] == 0.85 and st.loc["2", "break_even_x_field_rate"] == round(1 / 0.85, 3)


@pytest.mark.parametrize("mutate, msg", [
    (lambda c: c["1"]["payoutSummary"].append(_tier(17, 20, 1.0)), "expected it to start at 16"),            # a gap
    (lambda c: c["1"]["payoutSummary"].append(_tier(15, 20, 1.0)), "expected it to start at 16"),            # an overlap
    (lambda c: c["2"].update(fee=0), "no positive entry fee"),
    (lambda c: c["1"].update(payoutSummary=[]), "no payoutSummary"),
    (lambda c: c["1"]["payoutSummary"][0]["payoutDescriptions"][0].update(value=None), "has no value"),
    (lambda c: c["1"]["payoutSummary"][0]["tierPayoutDescriptions"].update(Ticket="t"), "both cash and a ticket"),
    (lambda c: c["1"].update(totalPayouts=2000.0), "DK's totalPayouts"),
])
def test_refusals(mutate, msg):
    c = _capture(); mutate(c)
    with pytest.raises(ValueError, match=msg):
        L.ladder_rows(c, 2026, 5, "f.json", "abc", "t")


def test_a_refused_file_exits_3_and_a_dry_run_writes_nothing(tmp_path, capsys):
    good = tmp_path / "good.json"; good.write_text(json.dumps(_capture()))
    assert L.main(["--season", "2026", "--week", "5", "--file", str(good)]) == 0
    out = capsys.readouterr().out
    assert "dry run: nothing written" in out and "$" not in out                       # multiples only, never dollars
    c = _capture(); c["1"]["totalPayouts"] = 9.0; bad = tmp_path / "bad.json"; bad.write_text(json.dumps(c))
    assert L.main(["--season", "2026", "--week", "5", "--file", str(bad)]) == 3


def test_the_ddl_declares_the_table_and_the_three_views():
    ddl = (ROOT / "sql" / "raw" / "011_dk_payout_ladders.sql").read_text()
    assert "CREATE TABLE IF NOT EXISTS `${raw}.dk_payout_ladders`" in ddl
    for v in ("v_dk_payout_ladder_latest", "v_dk_payout_structure", "v_dk_entry_tier"):
        assert f"CREATE OR REPLACE VIEW `${{raw}}.{v}`" in ddl
    cols = ddl[ddl.index("dk_payout_ladders` ("):ddl.index("PARTITION BY")]
    assert all(f"  {c} " in cols for c in L.COLUMNS)
