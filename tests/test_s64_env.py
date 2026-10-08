"""Study 64 (version 2, real units): the fit recovers planted per-point / per-mph effects; wind only at open-air stadiums
(home team not roofed, wind measured); demeaning within season x week x position; the application mirrors it; the line
gates on the reader's own fp and scores with the reader's own bootstrap."""
import hashlib
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]


def _mod(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec); sys.modules[name] = mod; spec.loader.exec_module(mod)
    return mod


F, A, L = _mod("s64_env_fit"), _mod("s64_env_apply"), _mod("s64_env_line")
HOMES = ("KC", "BUF", "DET", "LV", "CHI")                      # DET, LV roofed


def _synthetic(b_itt=0.3, b_wind=-0.1, n_weeks=10, per=40, seed=64):
    rng = np.random.default_rng(seed)
    rows, mk = [], []
    for s in (2023, 2024, 2025):
        for w in range(1, n_weeks + 1):
            for i in range(per):
                home = HOMES[i % len(HOMES)]
                roofed = home in F.ROOFED_HOME
                for pos in ("QB", "RB", "WR", "TE"):
                    gid = f"{s}-{w}-{i}-{pos}"
                    itt = rng.normal(23, 4); wind = abs(rng.normal(8, 5))
                    rows.append({"season": s, "week": w, "gsis_id": gid, "game_id": f"{s}_{w:02d}_XXX_{home}", "position": pos,
                                 "was_active": True, "implied_team_total": itt, "wind_mph": (np.nan if roofed else wind),
                                 "is_dome": roofed, "_itt": itt, "_wind": (0.0 if roofed else wind), "_open": not roofed})
                    mk.append({"season": s, "week": w, "gsis_id": gid, "market_points": 10.0})
    t = pd.DataFrame(rows)
    g = t.groupby(["season", "week", "position"])
    itt_d = t._itt - g._itt.transform("mean")
    wmean = t._wind.where(t._open).groupby([t.season, t.week, t.position]).transform("mean")
    wind_d = np.where(t._open, t._wind - wmean, 0.0)
    t["y_dk_points"] = 10.0 + b_itt * itt_d + b_wind * wind_d + rng.normal(0, 0.5, len(t))
    return t, pd.DataFrame(mk)


def test_the_fit_recovers_planted_real_unit_effects_in_both_models():
    t, mk = _synthetic()
    m = F.build_panel(t, mk)
    for pos in F.POSITIONS:
        d = m[m.position == pos]
        b_itt, b_wind = F.fit(d, F.MODELS["ENV"])
        assert abs(b_itt - 0.3) < 0.02 and abs(b_wind + 0.1) < 0.02, (pos, b_itt, b_wind)
        (b_only,) = F.fit(d, F.MODELS["ITT"])
        assert abs(b_only - 0.3) < 0.02, (pos, b_only)


def test_wind_only_at_open_air_stadiums_and_demeaning_within_the_week_position():
    t, mk = _synthetic()
    t.loc[t.game_id.str.endswith("_LV"), "wind_mph"] = 12.0     # a measured wind at a roofed home (international game): zeroed
    t.loc[t.index[:8], "wind_mph"] = np.nan                       # a NULL wind at an open-air stadium: missing, contributes 0
    m = F.build_panel(t, mk)
    home = m.game_id.str.split("_").str[-1]
    assert not m.open_air[home.isin(F.ROOFED_HOME)].any()
    assert (m.wind_d[~m.open_air] == 0.0).all() and m.wind_d.notna().all()
    assert not m.open_air[m.gsis_id.isin(t.gsis_id.iloc[:8])].any()
    g = m.groupby("swp")
    assert np.allclose(g.itt_d.mean(), 0.0, atol=1e-9) and np.allclose(g.resid_d.mean(), 0.0, atol=1e-9)
    assert np.allclose(m[m.open_air].groupby("swp").wind_d.mean(), 0.0, atol=1e-9)
    assert m.itt_d.std() > 3.0                                    # real units (points of team total), not z


def test_inactive_players_and_missing_markets_are_left_out():
    t, mk = _synthetic()
    t.loc[t.index[:10], "was_active"] = False
    m = F.build_panel(t, mk.iloc[20:])
    assert not m.gsis_id.isin(t.gsis_id.iloc[:10]).any() and not m.gsis_id.isin(mk.gsis_id.iloc[:20]).any()


def test_fit_all_writes_both_models_per_position_with_bootstrap_and_seasons():
    t, mk = _synthetic(n_weeks=4, per=12)
    out = F.fit_all(F.build_panel(t, mk))
    assert set(out) == {"ITT", "ENV"}
    for pos in F.POSITIONS:
        assert {"b_itt", "se_itt", "n", "n_open_air", "by_season"} <= set(out["ITT"][pos]) and "b_wind" not in out["ITT"][pos]
        assert {"b_itt", "b_wind", "se_itt", "se_wind"} <= set(out["ENV"][pos])
        assert set(out["ENV"][pos]["by_season"]) == {2023, 2024, 2025}


COEFFS = {"version": 2, "apply": {"cap_points": 2.0, "roofed_home": list(F.ROOFED_HOME)},
          "models": {"ITT": {p: {"b_itt": b} for p, b in (("QB", 0.3), ("RB", 0.2), ("WR", 0.1), ("TE", 0.0))},
                     "ENV": {p: {"b_itt": b, "b_wind": w} for p, b, w in (("QB", 0.25, -0.2), ("RB", 0.2, 0.0), ("WR", 0.1, -0.05),
                                                                           ("TE", 0.0, 0.0))}}}


def _frame():
    fr = pd.DataFrame({"id": ["q1", "q2", "q3", "q4", "w1", "w2", "d1"], "dk_draftable_id": range(7),
                       "pos": ["QB", "QB", "QB", "QB", "WR", "WR", "DST"],
                       "game_id": ["2026_05_A_KC", "2026_05_B_BUF", "2026_05_C_DET", "2026_05_D_CHI", "2026_05_A_KC",
                                   "2026_05_B_BUF", "2026_05_A_KC"],
                       "implied_team_total": [40.0, 20.0, 20.0, 16.0, 25.0, np.nan, 20.0],
                       "wind_mph": [20.0, 5.0, 9.0, 8.0, 10.0, 10.0, 10.0], "is_dome": [False] * 7})   # q3: DET, roofed, is_dome wrong
    proj = pd.DataFrame({"id": ["q1", "q2", "q3", "q4", "w1", "w2", "d1"], "fp": [20.0, 18.0, 0.5, 15.0, 10.0, 9.0, 6.0]})
    return fr, proj


def test_the_application_is_real_units_with_the_stadium_rule_caps_and_floors():
    fr, proj = _frame()
    out = A.apply(fr, proj, COEFFS).set_index("id")
    assert "d1" not in out.index                                                    # skill players only
    itt_d = pd.Series([40.0, 20.0, 20.0, 16.0], index=["q1", "q2", "q3", "q4"]) - 24.0
    assert np.allclose(out.loc[itt_d.index, "itt_adj"], (0.3 * itt_d).clip(-2, 2).round(4))
    assert out.loc["q1", "itt_adj"] == 2.0                                          # capped at 2 points
    assert not out.loc["q3", "open_air"] and out.loc[["q1", "q2", "q4"], "open_air"].all()   # the stadium rule, not is_dome
    wind_d = pd.Series([20.0, 5.0, 8.0], index=["q1", "q2", "q4"]) - 11.0           # open-air mean over q1, q2, q4
    env = (0.25 * itt_d.loc[wind_d.index] - 0.2 * wind_d).clip(-2, 2).round(4)
    assert np.allclose(out.loc[wind_d.index, "env_adj"], env)
    assert out.loc["q3", "env_adj"] == round(0.25 * -4.0, 4)                        # roofed: ITT part only
    assert (out.fp_itt >= 0).all() and out.loc["q3", "fp_itt"] == 0.0               # floored at 0 (0.5 - 1.2)
    assert (out.loc[["w1", "w2"], ["itt_adj", "env_adj"]] == 0.0).all().all()       # 2 WRs < 3: 0


def test_the_application_refuses_version_1_coefficients():
    fr, proj = _frame()
    with pytest.raises(SystemExit, match="version"):
        A.apply(fr, proj, {**COEFFS, "version": None})


def _rows(n=120, seed=1):
    rng = np.random.default_rng(seed)
    rows = pd.DataFrame({"id": [f"p{i}" for i in range(n)], "pos": ["WR"] * n, "game": [f"g{i % 12}" for i in range(n)],
                         "gsis_id": [f"p{i}" for i in range(n)], "season": 2026, "week": 5, "fp": rng.uniform(5, 20, n)})
    rows["actual"] = rows.fp + rng.normal(0, 5, n)
    env = pd.DataFrame({"id": rows.id, "fp": rows.fp, "itt_adj": np.where(np.arange(n) % 2 == 0, 0.5, -0.5),
                        "env_adj": np.where(np.arange(n) % 3 == 0, 0.7, -0.3)})
    return rows, env


def test_the_line_pins_the_reader_and_scores_both_comparisons_with_its_own_bootstrap():
    assert hashlib.sha256((ROOT / "scripts" / "weekly_projection_accuracy.py").read_bytes()).hexdigest() == L.READER_SHA256
    R = L.reader()
    rows, env = _rows()
    d, audit = L.week_rows(rows, env.iloc[:-3])                                       # 3 rows outside apply's population
    assert audit["rows"] == 120 and audit["joined"] == 117 and audit["without_env"] == 3
    assert (d[["itt_adj", "env_adj"]].iloc[-3:] == 0).all().all()
    p = L.score(R, d, "fp_itt", "fp")
    assert abs(p["incumbent"]["MAE"] - (d.fp - d.actual).abs().mean()) < 1e-12
    assert abs(p["challenger"]["MAE"] - (d.fp_itt - d.actual).abs().mean()) < 1e-12
    assert p["improvement"] == R.bootstrap(d.assign(ours=d.fp_itt, blend=d.fp))["ours_vs_fp"]
    w = L.score(R, d, "fp_env", "fp_itt")                                             # the wind increment: ENV vs ITT
    assert abs(w["incumbent"]["MAE"] - (d.fp_itt - d.actual).abs().mean()) < 1e-12
    assert w["improvement"] == R.bootstrap(d.assign(ours=d.fp_env, fp=d.fp_itt, blend=d.fp_itt))["ours_vs_fp"]


def test_the_identity_gate_refuses_different_fp_numbers():
    rows, env = _rows()
    env.loc[5, "fp"] += 0.25
    with pytest.raises(SystemExit, match="differs from the reader's fp"):
        L.week_rows(rows, env)


def test_the_pooled_rule():
    good = {"incumbent": {"MAE": 5.0}, "challenger": {"MAE": 4.9}, "improvement": {"share_better": 0.97}}
    weak = {"incumbent": {"MAE": 5.0}, "challenger": {"MAE": 4.9}, "improvement": {"share_better": 0.90}}
    assert L.reading(good, [5, 6, 7, 8]).startswith("FP + ITT beats FP") and "TRIAL-ELIGIBLE" in L.reading(good, [5, 6, 7, 8])
    assert L.reading(weak, [5, 6, 7, 8]).startswith("FP + ITT does not beat FP")
    assert L.reading(good, [5, 6, 7]).startswith("descriptive only")               # before W8
    assert L.reading(good, [5, 6, 8]).startswith("descriptive only")               # fewer than 4 weeks


def test_the_pool_leaves_out_pre_w5_smoke_rows(tmp_path, capsys):
    rows, env = _rows()
    d, _ = L.week_rows(rows, env)
    d.assign(week=4).to_csv(tmp_path / "s64-2026-w04.csv", index=False)
    with pytest.raises(SystemExit, match="no weekly s64 rows from W5"):
        L.main(["pool", "--out-dir", str(tmp_path)])
    d.to_csv(tmp_path / "s64-2026-w05.csv", index=False)
    assert L.main(["pool", "--out-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "left out of the pool: weeks [4]" in out and "POOLED weeks [5] PRIMARY" in out and "descriptive only" in out
