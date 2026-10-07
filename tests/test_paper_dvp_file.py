"""scripts/paper_dvp_file.py (study 38 amendment 6c, the paper FP-means DvP arm): the point-in-time matchup z, the
walk-forward pooled slope of FP's residual, the adjusted points, and the refusals. Offline."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import paper_dvp_file as P  # noqa: E402


def _frame(n=40):
    teams = [f"T{k}" for k in range(8)]
    rows = []
    for k in range(n):
        j = k // 4                                                          # every position meets every opponent
        rows.append({"id": f"00-{k:04d}", "dk_player_id": 1000 + k, "dk_draftable_id": 5000 + k,
                     "pos": ["QB", "RB", "WR", "TE"][k % 4], "team": teams[j % 8], "opp": teams[(j + 1) % 8]})
    rows.append({"id": "T0_DST", "dk_player_id": 9, "dk_draftable_id": 9, "pos": "DST", "team": "T0", "opp": "T1"})
    return pd.DataFrame(rows)


def _allowed(weeks=(1, 2, 3), seed=1):
    rng = np.random.default_rng(seed)
    return pd.DataFrame([{"def_team": f"T{t}", "week": w, "position": p, "fp_allowed": float(rng.uniform(10, 40))}
                         for t in range(8) for w in weeks for p in ("QB", "RB", "WR", "TE")])


def test_z_uses_only_prior_weeks_and_is_within_position():
    fr, al = _frame(), _allowed(weeks=(1, 2, 3, 4))
    z3 = P.matchup_z(fr, al, 3); z4 = P.matchup_z(fr, al, 4)
    assert "T0_DST" not in z3.index                                    # no DST adjustment
    assert not np.allclose(z3.to_numpy(float), z4.to_numpy(float))    # week 3's own rows enter only week 4's z
    al_future = al.copy(); al_future.loc[al_future.week == 3, "fp_allowed"] += 100
    assert np.allclose(P.matchup_z(fr, al_future, 3).to_numpy(float), z3.to_numpy(float))
    pos = fr.set_index("id").loc[z3.index, "pos"]
    for p in ("QB", "RB", "WR", "TE"):
        assert abs(z3[pos == p].mean()) < 1e-9


def test_the_walk_forward_slope_recovers_a_planted_effect_and_the_adjustment():
    fr, al = _frame(200), _allowed()
    z = P.matchup_z(fr, al, 4)
    fp = pd.DataFrame({"dk_draftable_id": fr.dk_draftable_id, "fp": 12.0})
    actual = pd.Series(12.0 + 2.0 * z, index=z.index)                     # residual = 2 x z exactly
    slope, n = P.walk_forward_slope([(4, fr, fp, actual)], al)
    assert abs(slope - 2.0) < 1e-9 and n == len(z.dropna())
    out = P.build(fr, fp.assign(fp=lambda d: np.where(d.dk_draftable_id == 5000, 0.0, 12.0)), al, 5, slope)
    zero = out[out.gsis_id == "00-0000"]
    assert (zero.adj_points == 0.0).all()                                   # FP's 0 stays 0
    rest = out[out.gsis_id != "00-0000"]
    assert np.allclose(rest.adj_points, rest.fp + 2.0 * rest.z) and "DST" not in set(out.pos)


def test_too_few_prior_rows_gives_no_slope():
    fr, al = _frame(8), _allowed()
    fp = pd.DataFrame({"dk_draftable_id": fr.dk_draftable_id, "fp": 12.0})
    slope, n = P.walk_forward_slope([(4, fr, fp, pd.Series(12.0, index=fr["id"]))], al)
    assert slope is None and n < 30
