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


def _run_main(tmp_path, monkeypatch, retrieved_at, require):
    fr = _frame(); fpath = tmp_path / "frame.parquet"; fr.to_parquet(fpath)
    cap = {"retrieved_at": retrieved_at, "slate_id": "s1", "source_sha256": "x", "rows": len(fr)}
    monkeypatch.setattr(FPO, "load_capture", lambda season, week, before: (_capture(fr), cap))
    args = ["--frame", str(fpath), "--season", "2026", "--week", "5", "--before", "2026-10-11T15:57:00Z",
            "--inactives-utc", "2026-10-11T15:30:00Z", "--out", str(tmp_path / "proj_fp-T.csv")]
    return FPO.main(args + (["--require-after-inactives"] if require else []))


def test_the_t70_build_refuses_a_capture_from_before_the_inactives(tmp_path, monkeypatch, capsys):
    """Operator 10-06 ("Our post-inactives numbers"): the T-70 build REFUSES a pre-inactives capture (exit 2, no file), so
    the host falls back to OUR post-inactives projections; earlier builds keep it with a banner. Every run prints the
    capture timing line the upload sheet shows."""
    assert _run_main(tmp_path, monkeypatch, "2026-10-11T15:10:00Z", require=True) == 2
    err = capsys.readouterr().err
    assert "FP CAPTURE TIMING: 2026-10-11T15:10:00Z BEFORE the 10:30 CT inactives" in err
    assert "FP PROJECTIONS REFUSED: the newest capture" in err and not (tmp_path / "proj_fp-T.csv").exists()
    assert _run_main(tmp_path, monkeypatch, "2026-10-11T15:10:00Z", require=False) == 0      # the 09:10 build: banner only
    err = capsys.readouterr().err
    assert "BEFORE THE 10:30 CT INACTIVES" in err and (tmp_path / "proj_fp-T.csv").exists()
    (tmp_path / "proj_fp-T.csv").unlink()
    assert _run_main(tmp_path, monkeypatch, "2026-10-11T15:46:30Z", require=True) == 0       # the 10:46 capture: accepted
    assert "FP CAPTURE TIMING: 2026-10-11T15:46:30Z AFTER the 10:30 CT inactives" in capsys.readouterr().err
