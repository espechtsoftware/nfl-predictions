"""ownership_tabpfn: the pure parts (L23's lag definition, the spread convention, the capture picker, the features, the
transfer checks, the context, the prediction checks, the fit with a stub regressor) on synthetic data; tabpfn and a GPU
are not needed. The live run on the laptop GPU is the integration test (HANDOFF)."""
import hashlib
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import ownership_tabpfn as ot  # noqa: E402

NOW = datetime(2026, 10, 4, 15, 55, tzinfo=timezone.utc)


def _nm(i):
    """a letter-only name (the name key drops digits, as L15/L23's does)"""
    a = "abcdefghijklmnopqrstuvwxyz"
    return "Player " + a[i // 26].upper() + a[i % 26]


def _frame(n=40, flip=False):
    rng = np.random.default_rng(1)
    pos = (["QB", "RB", "WR", "TE"] * n)[:n] + ["DST"]
    tot = rng.uniform(38, 52, n + 1).round(1)
    sp_hist = rng.uniform(-9, 9, n + 1).round(1)                       # L23's convention: a favourite is negative
    imp = (tot - sp_hist) / 2.0
    live_spread = -sp_hist if not flip else sp_hist                    # the live frame's convention is the opposite
    return pd.DataFrame({"id": [str(1000 + i) for i in range(n + 1)], "dk_player_id": [9000 + i for i in range(n + 1)],
                         "gsis_id": [f"00-{i:07d}" for i in range(n + 1)], "name": [_nm(i) + " Jr." for i in range(n + 1)],
                         "pos": pos, "salary": rng.integers(3000, 8500, n + 1), "mean_projection": rng.uniform(2, 22, n + 1),
                         "implied_team_total": imp, "game_total": tot, "spread": live_spread,
                         "salary_delta_wow": rng.choice([-300, 0, 200, 500], n + 1)})


def _history(fr):
    """History rows in L23's conventions, drawn from the same ranges."""
    f = fr[fr.pos != "DST"].copy()
    h = pd.DataFrame({"season": 2024, "week": 5, "salary": f.salary, "mean_projection": f.mean_projection,
                      "implied_team_total": f.implied_team_total, "game_total": f.game_total, "spread": -pd.to_numeric(f.spread),
                      "salary_delta_wow": f.salary_delta_wow, "linestar_own": np.linspace(0.5, 30, len(f))})
    h["value"] = h.mean_projection / (h.salary / 1000.0)
    return pd.concat([h, h.assign(week=6)], ignore_index=True)


def _linestar(fr, cover=1.0):
    f = fr[fr.pos != "DST"]
    f = f.head(int(len(f) * cover))
    return pd.DataFrame({"name": f.name.str.replace(" Jr.", "", regex=False), "pos": f.pos, "own_proj": np.linspace(0.6, 29, len(f))})


def test_lags_follow_l23_definition():
    weeks = {1: {"a": 10.0, "b": 2.0}, 2: {"a": 20.0}, 3: {"b": 6.0, "c": 1.0}}
    d = ot.lags_from_weeks(weeks, 4).set_index("key")
    assert d.loc["a", "own_l1"] == 0.0 and d.loc["a", "own_l3"] == pytest.approx(10.0)       # absent from W3: 0, as L23
    assert d.loc["b", "own_l1"] == 6.0 and d.loc["b", "own_l3"] == pytest.approx(8.0 / 3)
    assert np.isnan(ot.lags_from_weeks({1: {"a": 5.0}}, 3).set_index("key").loc["a", "own_l1"])  # no W2 file: NaN


def test_spread_is_rebuilt_in_l23s_convention_and_a_changed_convention_refuses():
    fr = _frame()
    got = ot.spread_historical(fr)
    assert np.allclose(got, -fr.spread)                                   # favourite negative, as the history
    with pytest.raises(SystemExit, match="spread convention"):
        ot.spread_historical(_frame(flip=True))                           # a frame already in L23's sign is a change: refuse


def _capture(tmp_path, fr, label="t70", at=NOW - timedelta(hours=1), season=2026, week=4, cover=1.0, bad_sha=False):
    d = tmp_path / "linestar"; d.mkdir(exist_ok=True)
    stamp = at.strftime("%Y%m%dT%H%M%SZ")
    c = d / f"linestar-own-{label}-{stamp}.csv"
    _linestar(fr, cover).to_csv(c, index=False)
    sha = hashlib.sha256(c.read_bytes()).hexdigest() if not bad_sha else "0" * 64
    (d / f"linestar-own-{label}-{stamp}.receipt.json").write_text(json.dumps(
        {"season": season, "week": week, "captured_at_utc": at.isoformat(), "csv_sha256": sha}))
    return d, c


def test_newest_capture_refuses_stale_wrong_week_and_tampered(tmp_path):
    fr = _frame()
    d, c = _capture(tmp_path, fr)
    got, meta = ot.newest_capture(d, 2026, 4, 30.0, NOW)
    assert got == c and meta["age_hours"] == pytest.approx(1.0)
    for kw, msg in (({"at": NOW - timedelta(hours=40), "label": "old"}, "h old"), ({"week": 3, "label": "w3"}, "not 2026 week 4"),
                    ({"bad_sha": True, "label": "bad"}, "does not match its receipt")):
        sub = tmp_path / kw.get("label", "x"); sub.mkdir()
        dd, _ = _capture(sub, fr, **kw)
        with pytest.raises(SystemExit, match=msg):
            ot.newest_capture(dd, 2026, 4, 30.0, NOW)


def test_features_and_transfer_checks(tmp_path):
    fr = _frame(); hist = _history(fr)
    lags = pd.DataFrame({"key": [ot.norm(_nm(1)), ot.norm(_nm(2))], "own_l1": [12.0, 0.0], "own_l3": [9.0, 3.0]})
    feats = ot.build_features(fr, lags, _linestar(fr))
    assert list(feats.columns[-len(ot.FEATURES):]) == ot.FEATURES and "DST" not in set(feats.pos)
    assert feats.set_index("display_name").loc[_nm(1) + " Jr.", "own_l1"] == 12.0
    assert (feats.own_l1.fillna(-1) >= 0).all() and feats.linestar_own.notna().all()   # suffix-insensitive name key
    checks = ot.transfer_checks(feats, hist)
    assert checks["linestar"]["coverage_projected_5"] == 1.0
    with pytest.raises(SystemExit, match="LineStar covers"):
        ot.transfer_checks(ot.build_features(fr, lags, _linestar(fr, cover=0.2)), hist)
    shifted = feats.assign(salary=feats.salary * 1000)                                   # a unit change
    with pytest.raises(SystemExit, match="feature salary"):
        ot.transfer_checks(shifted, hist)
    scaled = feats.assign(linestar_own=feats.linestar_own / 100 * 3)                    # fractions ×3: not percentages
    with pytest.raises(SystemExit, match="LineStar"):
        ot.transfer_checks(scaled, hist)


def test_context_keeps_the_newest_rows_and_predictions_are_checked():
    cols = ["season", "week"] + ot.FEATURES + ["target_own"]
    a = pd.DataFrame(np.ones((5, len(cols))), columns=cols).assign(season=2024, week=[1, 2, 3, 4, 5])
    b = pd.DataFrame(np.ones((2, len(cols))), columns=cols).assign(season=2026, week=[1, 2])
    ctx = ot.context_rows(a, b, ctx_max=3)
    assert list(zip(ctx.season, ctx.week)) == [(2024, 5), (2026, 1), (2026, 2)]
    assert ot.check_predictions(np.full(100, 3.0))["sum"] == 300.0
    with pytest.raises(SystemExit, match="scale"):
        ot.check_predictions(np.full(100, 0.5))                                         # a collapsed week
    with pytest.raises(SystemExit, match="non-finite"):
        ot.check_predictions(np.array([1.0, np.nan]))


def test_fit_predict_with_a_stub_regressor_clips_negatives():
    class Stub:
        def fit(self, X, y): self.n = X.shape[1]
        def predict(self, X): return np.linspace(-1, 10, len(X))
    cols = ot.FEATURES + ["target_own"]
    ctx = pd.DataFrame(np.ones((4, len(cols))), columns=cols)
    feats = pd.DataFrame(np.ones((6, len(ot.FEATURES))), columns=ot.FEATURES)
    p = ot.fit_predict(ctx, feats, regressor=Stub())
    assert p.min() == 0.0 and len(p) == 6


def test_features_command_end_to_end(tmp_path):
    fr = _frame(); fp = tmp_path / "frame.parquet"; fr.to_parquet(fp)
    hp = tmp_path / "rows.parquet"; _history(fr).to_parquet(hp)
    lp = tmp_path / "lags.csv"; pd.DataFrame({"key": [ot.norm(_nm(1))], "own_l1": [5.0], "own_l3": [4.0]}).to_csv(lp, index=False)
    d, _ = _capture(tmp_path, fr)
    out = tmp_path / "feats.parquet"
    assert ot.main(["features", "--season", "2026", "--week", "4", "--frame", str(fp), "--lags", str(lp), "--linestar-dir", str(d),
                    "--history", str(hp), "--out", str(out), "--now", NOW.isoformat()]) == 0
    rec = json.loads(Path(str(out) + ".receipt.json").read_text())
    assert rec["checks"]["spread"]["live_in_band"] >= 0.95 and "rebuilt" in rec["spread"]
    with pytest.raises(SystemExit, match="OWNERSHIP TABPFN REFUSED"):
        ot.main(["features", "--season", "2026", "--week", "4", "--frame", str(fp), "--lags", str(lp), "--linestar-dir",
                 str(tmp_path / "none"), "--history", str(hp), "--out", str(out), "--now", NOW.isoformat()])
