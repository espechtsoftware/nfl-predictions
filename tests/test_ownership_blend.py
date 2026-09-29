"""ownership_blend: the BLEND_PCT rule, the join, and the refusals, on synthetic files (no network, no warehouse)."""
import hashlib
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ownership_blend as ob  # noqa: E402


def _sets():
    return pd.DataFrame({"gsis_id": ["g1", "g2", "g3", "g4"], "dk_player_id": [11, 12, 13, 14],
                         "display_name": ["A.J. Brown", "Kenneth Walker III", "Tre Tucker", "Jaguars"], "pos": ["WR", "RB", "WR", "DST"],
                         "team": ["PHI", "KC", "LV", "JAX"], "salary": [8200, 7400, 4000, 3400], "proj": [17.3, 20.2, 10.3, 9.0],
                         "pred_own": [10.0, 28.0, 4.0, -0.1], "pred_rank": [2, 1, 3, 4], "set": ["", "CHALK", "", ""]})


def _linestar():
    return pd.DataFrame({"name": ["AJ Brown", "Kenneth Walker", "Somebody Else"], "pos": ["wr", "RB", "TE"], "team": ["PHI", "KC", "X"],
                         "opp": ["Y", "Y", "Y"], "salary": [8200, 7400, 3000], "own_proj": [20.0, 50.0, 9.0]})


def test_norm_is_l15s_key():
    assert ob.norm("A.J. Brown") == ob.norm("AJ Brown") == "aj brown"
    assert ob.norm("Kenneth Walker III") == ob.norm("Kenneth Walker") == "kenneth walker"
    assert ob.norm("Marvin Harrison Jr.") == "marvin harrison"


def test_blend_is_the_mean_where_covered_and_the_model_elsewhere():
    out, meta = ob.blend(_sets(), _linestar())
    got = out.set_index("display_name")
    assert got.loc["A.J. Brown", "pred_own"] == pytest.approx(15.0) and got.loc["Kenneth Walker III", "pred_own"] == pytest.approx(39.0)
    assert got.loc["Tre Tucker", "pred_own"] == pytest.approx(4.0) and not got.loc["Tre Tucker", "blended"]
    assert got.loc["Jaguars", "pred_own"] == 0.0                     # the model's negative is clipped
    assert list(out.display_name) == ["Kenneth Walker III", "A.J. Brown", "Tre Tucker", "Jaguars"] and list(out.pred_rank) == [1, 2, 3, 4]
    assert {"gsis_id", "dk_player_id", "model_own", "linestar_own"} <= set(out.columns)
    assert meta["joined"] == 2 and meta["linestar_rows_not_joined"] == 1 and meta["largest_not_joined"][0]["name"] == "Somebody Else"


def test_blend_refuses_values_that_are_not_percentages():
    with pytest.raises(SystemExit, match="not percentages"):
        ob.blend(_sets().assign(pred_own=[0.1, 0.28, 0.04, 0.0]), _linestar())
    with pytest.raises(SystemExit, match="not numbers"):
        ob.blend(_sets(), _linestar().assign(own_proj=[20.0, None, 9.0]))


def _capture(d, label, taken, season=2026, week=4, rows=None):
    d.mkdir(exist_ok=True)
    c = d / f"linestar-own-{label}-{taken.replace(':', '').replace('-', '')}.csv"
    (rows if rows is not None else _linestar()).to_csv(c, index=False)
    (c.with_name(c.name[:-4] + ".receipt.json")).write_text(json.dumps(
        {"season": season, "week": week, "label": label, "captured_at_utc": taken, "csv_sha256": hashlib.sha256(c.read_bytes()).hexdigest()}))
    return c


def test_main_takes_the_newest_capture_and_writes_the_receipt(tmp_path):
    sets = tmp_path / "ownership_sets.csv"; _sets().to_csv(sets, index=False)
    d = tmp_path / "linestar"
    _capture(d, "saturday", "2026-10-03T15:20:00+00:00", rows=_linestar().assign(own_proj=[18.0, 40.0, 9.0]))
    t70 = _capture(d, "t70", "2026-10-04T15:36:00+00:00")
    (d / "linestar-own-late-unfinished.csv").write_text("name,pos,own_proj\n")     # no receipt: never chosen
    out = tmp_path / "ownership_blend.csv"
    args = ["--sets", str(sets), "--linestar-dir", str(d), "--season", "2026", "--week", "4", "--out", str(out), "--min-joined", "2"]
    assert ob.main(args + ["--now", "2026-10-04T15:40:00+00:00"]) == 0
    rec = json.loads((tmp_path / "ownership_blend.csv.receipt.json").read_text())
    assert rec["linestar_capture"] == str(t70) and rec["linestar_label"] == "t70" and rec["joined"] == 2
    assert rec["out_sha256"] == hashlib.sha256(out.read_bytes()).hexdigest() and rec["sets_sha256"] == hashlib.sha256(sets.read_bytes()).hexdigest()
    assert pd.read_csv(out).set_index("display_name").loc["Kenneth Walker III", "pred_own"] == pytest.approx(39.0)


def test_main_refuses_by_name(tmp_path):
    sets = tmp_path / "ownership_sets.csv"; _sets().to_csv(sets, index=False)
    d = tmp_path / "linestar"
    cap = _capture(d, "t70", "2026-10-04T15:36:00+00:00")
    base = ["--sets", str(sets), "--season", "2026", "--week", "4", "--out", str(tmp_path / "o.csv")]
    now = ["--now", "2026-10-04T15:40:00+00:00"]
    with pytest.raises(SystemExit, match="exactly one"):
        ob.main(base + now)
    with pytest.raises(SystemExit, match="need >= 100"):
        ob.main(base + ["--linestar", str(cap)] + now)
    with pytest.raises(SystemExit, match="taken 168.1 h ago"):
        ob.main(base + ["--linestar", str(cap), "--min-joined", "2", "--now", "2026-10-11T15:40:00+00:00"])      # last week's capture
    with pytest.raises(SystemExit, match="not 2026 week 5"):
        ob.main(["--sets", str(sets), "--season", "2026", "--week", "5", "--out", str(tmp_path / "o.csv"), "--linestar", str(cap), "--min-joined", "2"] + now)
    cap.write_text(cap.read_text() + "Late Edit,WR,X,Y,3000,1.0\n")
    with pytest.raises(SystemExit, match="does not match its receipt"):
        ob.main(base + ["--linestar", str(cap), "--min-joined", "2"] + now)
    with pytest.raises(SystemExit, match="no LineStar capture with a receipt"):
        ob.main(base + ["--linestar-dir", str(tmp_path)] + now)
    assert not (tmp_path / "o.csv").exists()
