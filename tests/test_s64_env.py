"""Study 64: the fit recovers a planted joint effect; dome wind is 0 before z-scoring; z within season x week x position."""
import importlib.util
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("s64_env_fit", ROOT / "scripts" / "s64_env_fit.py")
F = importlib.util.module_from_spec(spec); sys.modules["s64_env_fit"] = F; spec.loader.exec_module(F)


def _synthetic(b_itt=0.5, b_wind=-1.0, n_weeks=30, per=40, seed=64):
    rng = np.random.default_rng(seed)
    rows, mk = [], []
    for s in (2023, 2024, 2025):
        for w in range(1, n_weeks // 3 + 1):
            for i in range(per):
                for pos in ("QB", "RB", "WR", "TE"):
                    gid = f"{s}-{w}-{i}-{pos}"
                    itt = rng.normal(23, 4); dome = i % 4 == 0; wind = 0.0 if dome else abs(rng.normal(8, 5))
                    rows.append({"season": s, "week": w, "gsis_id": gid, "position": pos, "was_active": True,
                                 "implied_team_total": itt, "wind_mph": (np.nan if dome else wind), "is_dome": dome, "_itt": itt, "_wind": wind})
                    mk.append({"season": s, "week": w, "gsis_id": gid, "market_points": 10.0})
    t = pd.DataFrame(rows)
    # the planted outcome: per-sd effects within each season x week x position
    t["_z_itt"] = t.groupby(["season", "week", "position"])._itt.transform(lambda x: (x - x.mean()) / x.std())
    t["_z_wind"] = t.groupby(["season", "week", "position"])._wind.transform(lambda x: (x - x.mean()) / x.std())
    t["y_dk_points"] = 10.0 + b_itt * t._z_itt + b_wind * t._z_wind + rng.normal(0, 0.5, len(t))
    return t, pd.DataFrame(mk)


def test_the_fit_recovers_a_planted_joint_effect():
    t, mk = _synthetic()
    m = F.build_panel(t, mk)
    for pos in F.POSITIONS:
        b_itt, b_wind = F.fit(m[m.position == pos])
        assert abs(b_itt - 0.5) < 0.05 and abs(b_wind + 1.0) < 0.05, (pos, b_itt, b_wind)


def test_dome_wind_is_zero_and_z_is_within_the_week_position():
    t, mk = _synthetic()
    m = F.build_panel(t, mk)
    assert (m.loc[m.is_dome.astype(bool), "wind_eff"] == 0.0).all() and m.wind_eff.notna().all()
    g = m.groupby("swp")
    assert np.allclose(g.z_itt.mean(), 0.0, atol=1e-9) and np.allclose(g.z_itt.std(), 1.0, atol=1e-9)
    assert np.allclose(g.resid_d.mean(), 0.0, atol=1e-9)


def test_inactive_players_and_missing_markets_are_left_out():
    t, mk = _synthetic()
    t.loc[t.index[:10], "was_active"] = False
    m = F.build_panel(t, mk.iloc[20:])
    assert not m.gsis_id.isin(t.gsis_id.iloc[:10]).any() and not m.gsis_id.isin(mk.gsis_id.iloc[:20]).any()


spec2 = importlib.util.spec_from_file_location("s64_env_apply", ROOT / "scripts" / "s64_env_apply.py")
A = importlib.util.module_from_spec(spec2); sys.modules["s64_env_apply"] = A; spec2.loader.exec_module(A)
COEFFS = {"positions": {"QB": {"b_itt": 0.5, "b_wind": -1.0}, "RB": {"b_itt": 0.5, "b_wind": 0.2},
                        "WR": {"b_itt": 0.4, "b_wind": -0.4}, "TE": {"b_itt": 0.0, "b_wind": 0.0}},
          "apply": {"cap_points": 2.0}}


def test_the_application_z_scores_within_position_zeroes_dome_wind_caps_and_floors():
    fr = pd.DataFrame({"id": ["q1", "q2", "q3", "q4", "w1", "w2", "d1"], "dk_draftable_id": range(7),
                       "pos": ["QB", "QB", "QB", "QB", "WR", "WR", "DST"],
                       "implied_team_total": [30.0, 20.0, 20.0, 18.0, 25.0, np.nan, 20.0],
                       "wind_mph": [20.0, 5.0, 5.0, 5.0, 10.0, 10.0, 10.0], "is_dome": [False, False, True, False, False, False, False]})
    proj = pd.DataFrame({"id": ["q1", "q2", "q3", "q4", "w1", "w2", "d1"], "fp": [20.0, 18.0, 0.5, 15.0, 10.0, 9.0, 6.0]})
    out = A.apply(fr, proj, COEFFS).set_index("id")
    assert "d1" not in out.index                                                   # skill players only
    q = fr[fr.pos == "QB"]
    z_itt = (q.implied_team_total - q.implied_team_total.mean()) / q.implied_team_total.std()
    w = pd.Series([20.0, 5.0, 0.0, 5.0], index=q.index)                           # q3 under a roof: wind 0
    z_wind = (w - w.mean()) / w.std()
    want = (0.5 * z_itt - 1.0 * z_wind).clip(-2, 2).round(4)
    assert np.allclose(out.loc[["q1", "q2", "q3", "q4"], "env_adj"].to_numpy(), want.to_numpy(), atol=1e-4)
    assert out.loc["q1", "env_adj"] == -2.0 or abs(out.loc["q1", "env_adj"]) <= 2.0   # capped at 2 points
    assert out.loc["q3", "fp_env"] >= 0.0                                          # never below 0
    assert out.loc["w1", "env_adj"] == 0.0 and out.loc["w2", "env_adj"] == 0.0     # 2 WRs < 3: z is 0
