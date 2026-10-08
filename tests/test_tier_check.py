"""scripts/tier_check.py (study row 67): input gates, the tier join and the reader-pinned metrics (offline, synthetic)."""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("tier_check", ROOT / "scripts" / "tier_check.py")
TC = importlib.util.module_from_spec(spec); spec.loader.exec_module(TC)


def acc_rows(n=24):
    rng = np.random.default_rng(0)
    d = pd.DataFrame({"id": [f"P{i:02d}" for i in range(n)], "name": [f"Player {i}" for i in range(n)],
                      "pos": ["QB", "RB", "WR", "TE"] * (n // 4), "game": [f"G{i % 6}" for i in range(n)],
                      "gsis_id": [f"00-{i:07d}" for i in range(n)], "season": 2026, "week": 5,
                      "ours": rng.uniform(8, 20, n), "fp": rng.uniform(8, 20, n), "actual": rng.uniform(0, 30, n)})
    d["blend"] = 0.5 * d.ours + 0.5 * d.fp
    return d


def frame(acc):
    sal = [5000 + 250 * i for i in range(len(acc))]                 # 5,000 ... 10,750: the tier holds 6,000-7,900
    return pd.DataFrame({"id": acc.id, "salary": sal})


def fpp_rows(acc):
    d = acc[["id", "name", "pos", "game", "gsis_id", "season", "week", "fp", "actual"]].iloc[::2].copy()
    d["props"] = d.fp + 0.5
    d["blend"] = 0.5 * d.fp + 0.5 * d.props
    return d


def test_tier_rows_keep_the_salary_band_and_join_props():
    acc = acc_rows(); d, audit = TC.tier_rows(acc, fpp_rows(acc), frame(acc))
    assert d.salary.between(6000, 7900).all() and len(d) == audit["tier_rows"] == 8
    assert list(d.columns) == TC.COLS
    assert d.props.notna().sum() == audit["with_props"] == 4      # every other id carries props


def test_fp_identity_gate_refuses_a_different_capture():
    acc = acc_rows(); f = fpp_rows(acc); f.loc[f.index[2], "fp"] += 0.01
    with pytest.raises(SystemExit, match="different fp"):
        TC.tier_rows(acc, f, frame(acc))


def test_input_checks(tmp_path):
    side = {"frame": str(tmp_path / "frame.parquet"), "capture": {"retrieved_at": "x"}, "capture_before": "c", "lock_utc": "l", "contest": "1"}
    TC.check_inputs(side, dict(side), tmp_path / "frame.parquet")
    with pytest.raises(SystemExit, match="not the accuracy reader's frame"):
        TC.check_inputs(side, dict(side), tmp_path / "other.parquet")
    with pytest.raises(SystemExit, match="disagree on capture"):
        TC.check_inputs(side, {**side, "capture": {"retrieved_at": "y"}}, tmp_path / "frame.parquet")


def test_rows_sha_must_match_the_sidecar(tmp_path):
    p = tmp_path / "accuracy-2026-w05.csv"; acc_rows().to_csv(p, index=False)
    p.with_suffix(".json").write_text(json.dumps({"rows_sha256": "0" * 64}))
    with pytest.raises(SystemExit, match="its sidecar says"):
        TC.read_rows(p)


def test_reader_is_sha_pinned(monkeypatch):
    monkeypatch.setattr(TC, "READER_SHA256", "f" * 64)
    with pytest.raises(SystemExit, match="not the pinned"):
        TC.reader()


def test_block_uses_the_readers_sign_and_names_the_props_slot():
    R = TC.reader()
    acc = acc_rows(); d, _ = TC.tier_rows(acc, fpp_rows(acc), frame(acc))
    text = TC.block(d, "2026 W5", R)
    m = R.metrics(d)
    assert f"bias {m['fp']['bias']:+.2f}" in text                    # bias = source - actual, the reader's own
    assert "props_vs_fp" in text and "fp+props_vs_fp" in text and "descriptive, gates nothing" in text


def _write(df, path, side):
    df.to_csv(path, index=False)
    path.with_suffix(".json").write_text(json.dumps({**side, "rows_sha256": hashlib.sha256(path.read_bytes()).hexdigest()}))


def test_week_and_pool_end_to_end(tmp_path, capsys):
    acc = acc_rows(); fr = tmp_path / "frame.parquet"; frame(acc).to_parquet(fr)
    side = {"frame": str(fr), "capture": {"retrieved_at": "x"}, "capture_before": "c", "lock_utc": "l", "contest": "1"}
    _write(acc, tmp_path / "accuracy-2026-w05.csv", side); _write(fpp_rows(acc), tmp_path / "fp-props-2026-w05.csv", side)
    out = tmp_path / "out"; summ = tmp_path / "summary.txt"
    assert TC.main(["week", "--season", "2026", "--week", "5", "--accuracy", str(tmp_path / "accuracy-2026-w05.csv"),
                    "--fp-props", str(tmp_path / "fp-props-2026-w05.csv"), "--frame", str(fr), "--out-dir", str(out),
                    "--summary", str(summ)]) == 0
    assert (out / "tier-2026-w05.csv").is_file() and "TIER CHECK" in summ.read_text()
    assert "Player" not in summ.read_text()                         # the tracked summary carries no player rows
    assert TC.main(["pool", "--out-dir", str(out)]) == 0
    assert "POOLED weeks >= 5" in capsys.readouterr().out
