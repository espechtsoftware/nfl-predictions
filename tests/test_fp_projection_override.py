"""Fantasy Points' projections as the projection source (operator 2026-10-05): the override file's gates
(scripts/fp_projection_override.py) and union_reselect's --proj-source. Offline: synthetic frames and captures.
Reference, W4 2026 (real; not run here): coverage 1.0, 24 DSTs, r(FP, ours) 0.966, capture 15:38Z after the 15:30Z inactives."""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("fp_projection_override", ROOT / "scripts" / "fp_projection_override.py")
FPO = importlib.util.module_from_spec(spec); spec.loader.exec_module(FPO)
sys.path.insert(0, str(ROOT / "scripts"))
import union_reselect as ur  # noqa: E402


def _frame(n=40):
    rows = []
    for k in range(n):
        rows.append({"id": f"p{k}", "name": f"P{k}", "pos": ["QB", "RB", "WR", "TE"][k % 4], "salary": 4000 + 100 * k,
                     "dk_draftable_id": float(1000 + k), "mean_projection": 3.0 + 0.5 * k})
    for t in range(4):
        rows.append({"id": f"d{t}", "name": f"D{t}", "pos": "DST", "salary": 3000, "dk_draftable_id": float(2000 + t), "mean_projection": 6.0})
    return pd.DataFrame(rows)


def _capture(fr, noise=0.0, drop=(), salary_shift=None):
    rng = np.random.default_rng(3)
    fp = pd.DataFrame({"slate_player_id": fr.dk_draftable_id.astype(int).astype(str), "salary": fr.salary,
                       "fantasy_points": fr.mean_projection * 1.05 + noise * rng.normal(size=len(fr))})
    fp = fp[~fp.slate_player_id.isin([str(int(x)) for x in drop])]
    if salary_shift:
        fp.loc[fp.index[0], "salary"] += salary_shift
    return fp


def test_a_clean_capture_maps_every_player_exactly():
    fr = _frame(); out, g = FPO.build(fr, _capture(fr))
    assert len(out) == len(fr) and g["coverage_skill_ge5"] == 1.0 and g["dst_covered"] == 4 and g["kept_ours"] == 0
    assert g["pearson_r"] > 0.99 and len(g["top15_abs_diff"]) == 15
    assert set(out.columns) == {"id", "dk_draftable_id", "name", "pos", "ours", "fp"}


def test_each_gate_refuses():
    fr = _frame()
    with pytest.raises(FPO.Refused, match="coverage"):
        FPO.build(fr, _capture(fr, drop=[1000 + k for k in range(10, 20)]))          # 10 skill players >= 5 missing
    with pytest.raises(FPO.Refused, match="DSTs without an FP projection"):
        FPO.build(fr, _capture(fr, drop=[2001]))
    with pytest.raises(FPO.Refused, match="salary differs"):
        FPO.build(fr, _capture(fr, salary_shift=200))
    with pytest.raises(FPO.Refused, match="disagree"):
        FPO.build(fr, _capture(fr, noise=40.0))
    two = pd.concat([_capture(fr), _capture(fr).head(1)])
    with pytest.raises(FPO.Refused, match="repeats"):
        FPO.build(fr, two)


def test_a_player_fp_lacks_keeps_ours():
    fr = _frame(); out, g = FPO.build(fr, _capture(fr, drop=[1000]))                 # p0 projects 3.0 (< 5): no gate
    assert g["kept_ours"] == 1 and "p0" not in set(out.id)


def _write_override(tmp_path, fr, frame_file):
    out, g = FPO.build(fr, _capture(fr))
    csv = tmp_path / "proj_fp.csv"; out.to_csv(csv, index=False)
    meta = {"frame_sha256": hashlib.sha256(frame_file.read_bytes()).hexdigest(), "csv_sha256": hashlib.sha256(csv.read_bytes()).hexdigest(),
            "gates": g, "capture": {"retrieved_at": "2026-10-11T15:41:00+00:00"}, "before_inactives": False}
    Path(str(csv) + ".json").write_text(json.dumps(meta))
    return csv


def test_union_replaces_ours_for_the_files_players_and_keeps_ours_beside_it(tmp_path):
    fr = _frame(); ff = tmp_path / "frame.parquet"; fr.to_parquet(ff)
    csv = _write_override(tmp_path, fr, ff)
    new, meta = ur.apply_proj_source(fr, csv, ff)
    assert np.allclose(new.mean_projection, fr.mean_projection * 1.05) and np.allclose(new.mean_projection_ours, fr.mean_projection)
    assert meta["replaced"] == len(fr) and meta["kept_ours"] == 0 and "top15_abs_diff" not in meta["gates"]


def test_union_refuses_a_file_built_for_another_frame_or_edited(tmp_path):
    fr = _frame(); ff = tmp_path / "frame.parquet"; fr.to_parquet(ff)
    csv = _write_override(tmp_path, fr, ff)
    other = tmp_path / "other.parquet"; _frame(41).to_parquet(other)
    with pytest.raises(SystemExit, match="built for another frame"):
        ur.apply_proj_source(fr, csv, other)
    csv.write_text(csv.read_text().replace("P1,", "P1x,", 1))
    with pytest.raises(SystemExit, match="does not match its sidecar"):
        ur.apply_proj_source(fr, csv, ff)


def test_a_null_fp_projection_keeps_ours_and_is_named():
    """The outside review 10-07, M1: a null fantasyPoints was set to 0 and dropped by the union's 1.0 floor."""
    fr = _frame(); cap = _capture(fr)
    cap.loc[cap.slate_player_id == "1003", "fantasy_points"] = np.nan                  # p3 (TE, ours 4.5)
    out, g = FPO.build(fr, cap)
    assert "p3" not in set(out.id) and g["fp_null_kept_ours"] == 1 and g["kept_ours"] == 1
    assert g["fp_null_players"] == [{"name": "P3", "pos": "TE", "ours": 4.5}]
    assert not (out.fp == 0).any()


def test_null_fp_projections_are_not_coverage():
    fr = _frame(); cap = _capture(fr)
    cap.loc[cap.slate_player_id.isin([str(1000 + k) for k in range(10, 20)]), "fantasy_points"] = np.nan
    with pytest.raises(FPO.Refused, match="coverage"):
        FPO.build(fr, cap)


def test_the_content_floor_is_six_am_central_on_the_inactives_date():
    assert FPO.content_floor("2026-10-11T15:30:00Z") == pd.Timestamp("2026-10-11T11:00:00Z")
    assert FPO.content_floor("2026-12-06T16:30:00Z") == pd.Timestamp("2026-12-06T12:00:00Z")      # CST
    assert FPO.content_floor("2026-10-11T15:30:00Z", "2026-10-11T09:00:00Z") == pd.Timestamp("2026-10-11T09:00:00Z")


def _run_main(tmp_path, monkeypatch, fp_last_updated, retrieved_at="2026-10-11T15:38:35+00:00", extra=()):
    fr = _frame(); ff = tmp_path / "frame.parquet"; fr.to_parquet(ff)
    cap = _capture(fr)
    meta = {"retrieved_at": retrieved_at, "slate_id": "154468", "source_sha256": "x" * 64, "rows": len(cap),
            "fp_last_updated": fp_last_updated}
    monkeypatch.setattr(FPO, "load_capture", lambda s, w, b: (cap, meta))
    out = tmp_path / "proj_fp.csv"
    rc = FPO.main(["--frame", str(ff), "--season", "2026", "--week", "5", "--before", "2026-10-11T15:50:00Z",
                   "--inactives-utc", "2026-10-11T15:30:00Z", "--out", str(out), *extra])
    return rc, out


def test_the_t70_gate_uses_fp_numbers_updated_before_the_inactives_and_says_so(tmp_path, monkeypatch, capsys):
    """The operator 10-07 ("FP anyway, label it honestly"): W4's pattern -- captured 10:38 CT, FP last updated 08:58 CT."""
    rc, out = _run_main(tmp_path, monkeypatch, "2026-10-11T13:58:38+00:00", extra=["--require-after-inactives"])
    err = capsys.readouterr().err
    assert rc == 0 and out.is_file()
    assert "captured 2026-10-11T15:38:35+00:00 AFTER" in err and "FP last updated 2026-10-11T13:58:38+00:00 BEFORE them" in err
    assert "LAST UPDATED BEFORE THE 10:30 CT INACTIVES" in err
    meta = json.loads(Path(str(out) + ".json").read_text())
    assert meta["before_inactives"] is True and meta["captured_before_inactives"] is False
    assert meta["content_floor_utc"] == "2026-10-11T11:00:00+00:00"


def test_the_t70_gate_refuses_fp_numbers_from_before_sunday_morning(tmp_path, monkeypatch, capsys):
    rc, out = _run_main(tmp_path, monkeypatch, "2026-10-10T21:00:00+00:00", extra=["--require-after-inactives"])
    assert rc == 2 and not out.exists()
    assert "before Sunday morning" in capsys.readouterr().err
    rc, _ = _run_main(tmp_path, monkeypatch, None, extra=["--require-after-inactives"])                # unknown: refuse
    assert rc == 2


def test_without_the_t70_flag_old_fp_numbers_are_used_with_the_banner(tmp_path, monkeypatch, capsys):
    rc, out = _run_main(tmp_path, monkeypatch, "2026-10-10T21:00:00+00:00")
    assert rc == 0 and "LAST UPDATED BEFORE" in capsys.readouterr().err


def test_the_timing_line_names_both_our_capture_time_and_fps_update_time(tmp_path, monkeypatch, capsys):
    """Replaces the 10-06 rule's test (refuse a capture taken before the inactives): the operator 10-07 keys the gate to FP's
    own update time. An early capture of fresh numbers is used; a late capture of numbers updated after 10:30 says AFTER."""
    rc, _ = _run_main(tmp_path, monkeypatch, "2026-10-11T15:05:00+00:00", retrieved_at="2026-10-11T15:10:00+00:00",
                      extra=["--require-after-inactives"])
    err = capsys.readouterr().err
    assert rc == 0 and "captured 2026-10-11T15:10:00+00:00 BEFORE the 10:30 CT inactives" in err
    assert "FP last updated 2026-10-11T15:05:00+00:00 BEFORE them" in err
    (tmp_path / "proj_fp.csv").unlink(); Path(str(tmp_path / "proj_fp.csv") + ".json").unlink()
    rc, _ = _run_main(tmp_path, monkeypatch, "2026-10-11T15:44:00+00:00", retrieved_at="2026-10-11T15:46:30+00:00",
                      extra=["--require-after-inactives"])
    err = capsys.readouterr().err
    assert rc == 0 and "FP last updated 2026-10-11T15:44:00+00:00 AFTER them" in err and "LAST UPDATED BEFORE" not in err
