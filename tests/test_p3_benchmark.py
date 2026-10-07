"""P3 (the frozen prereg reports/2026-10-07-prereg-p3-simple-baseline.md): the props projection file's rows and sidecar,
and the scorer's big-seat count and per-class lines on a synthetic week. Offline."""
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    m = importlib.util.module_from_spec(spec); sys.modules[name] = m; spec.loader.exec_module(m)
    return m


PP = _load("props_projection_file")


def _frame():
    return pd.DataFrame({"id": ["a", "b", "c", "d"], "display_name": ["A", "B", "C", "D"], "pos": ["QB", "RB", "WR", "DST"],
                         "market_points": [20.0, 11.0, np.nan, 7.0], "dk_ppg": [18.0, 11.0, 9.0, 7.0]})


def test_props_rows_take_real_props_only_and_the_base_for_the_rest():
    r = PP.props_rows(_frame())
    assert dict(zip(r["id"], r["fp"])) == {"a": 20.0} and set(r.source) == {"props"}     # b and d are the dk_ppg fallback
    base = pd.DataFrame({"id": ["a", "b", "c"], "fp": [19.0, 12.5, 8.0]})
    r = PP.props_rows(_frame(), base)
    assert dict(zip(r["id"], r["fp"])) == {"a": 20.0, "b": 12.5, "c": 8.0}                  # props win where real
    assert dict(zip(r["id"], r["source"])) == {"a": "props", "b": "base", "c": "base"}


def test_the_sidecar_matches_what_apply_proj_source_checks(tmp_path):
    f = tmp_path / "frame.parquet"; _frame().to_parquet(f)
    out = tmp_path / "proj_props.csv"
    assert PP.main(["--frame", str(f), "--out", str(out)]) == 0
    meta = json.loads(Path(str(out) + ".json").read_text())
    assert meta["frame_sha256"] == PP.sha256_file(f) and meta["csv_sha256"] == PP.sha256_file(out)
    assert PP.main(["--frame", str(f), "--out", str(out)]) == 3                              # never overwrites


def test_a_frame_without_real_props_and_no_base_is_refused(tmp_path):
    f = tmp_path / "frame.parquet"; _frame().assign(market_points=np.nan).to_parquet(f)
    assert PP.main(["--frame", str(f), "--out", str(tmp_path / "x.csv")]) == 3


def test_big_seats_count_entries_inside_a_big_contests_seats_and_classes_carry_multiples(monkeypatch):
    MS = _load("moneygate_score"); P3 = _load("p3_score")
    det = {"1": {"name": "NFL Millionaire SUPERSat [5x]", "payoutSummary": [{"minPosition": 1, "maxPosition": 2,
                 "tierPayoutDescriptions": {"Ticket": "t"}, "payoutDescriptions": [{"value": 20.0}]}]},
           "2": {"name": "NFL $9K Cash Game", "payoutSummary": [{"minPosition": 1, "maxPosition": 3,
                 "tierPayoutDescriptions": {"Cash": "$"}, "payoutDescriptions": [{"value": 5.0}]}]}}
    others = {"1": np.array([1000, 2000, 3000, 4000], np.int64), "2": np.array([500, 1500, 2500, 3500, 4500], np.int64)}
    W = SimpleNamespace(contests=[{"contest_id": "1"}, {"contest_id": "2"}], details=det,
                        name_of={"10": "x", "11": "y", "12": "z"}, fpts={"x": 2500, "y": 2000, "z": 900},
                        others_sorted=lambda cid: others[cid])
    layout = {"1": {"lineups": [["10", "11"], ["12"]]}, "2": {"lineups": [["10", "11"]]}}
    # contest 1 entries: 4500 (rank 1) and 900 (rank 6 of 6); contest 2 entry: 4500 (rank 2 of 6)
    r = P3.score_arm(MS, W, layout, {"1": (True, 2), "2": (False, 0)})
    assert r["big_seats"] == 1 and r["entries"] == 3 and r["missing_names"] == 0
    assert r["contests"]["1"]["hits"] == 1 and r["contests"]["2"]["hits"] == 1 and r["contests"]["2"]["big_seats"] == 0
    sat = r["by_class"]["SuperSat 5x"]
    assert sat["entries"] == 2 and sat["hits"] == 1 and sat["paid_share"] == round(2 / 6, 6) and sat["multiple"] == round(0.5 / (2 / 6), 4)
