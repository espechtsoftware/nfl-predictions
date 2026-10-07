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


def test_the_walk_forward_slope_recovers_a_planted_effect_and_the_file_meets_the_arm_format():
    fr, al = _frame(200), _allowed()
    z = P.matchup_z(fr, al, 4)
    fp = pd.DataFrame({"dk_draftable_id": fr.dk_draftable_id, "fp": 12.0})
    actual = pd.Series(12.0 + 2.0 * z, index=z.index)                     # residual = 2 x z exactly
    slope, n = P.walk_forward_slope([(4, fr, fp, actual)], al)
    assert abs(slope - 2.0) < 1e-9 and n == len(z.dropna())
    fp5 = fp.assign(fp=lambda d: np.where(d.dk_draftable_id == 5000, 0.0, 12.0))
    out = P.build(pd.concat([fr, fr.head(3)]), fp5, al, 5, slope)          # a duplicated frame row counts once
    assert list(out.columns) == ["dk_player_id", "gsis_id", "pos", "opp", "z", "slope", "fp", "adj_points"]
    assert len(out) == 200 and out.dk_player_id.is_unique and set(out.pos) == {"QB", "RB", "WR", "TE"}
    assert out.slope.nunique() == 1 and np.isfinite(out[["z", "slope", "fp", "adj_points"]].to_numpy()).all()
    zero = out.gsis_id == "00-0000"
    assert (out[zero].adj_points == 0.0).all()                              # FP's 0 stays 0
    assert np.allclose(out[~zero].adj_points, out[~zero].fp + 2.0 * out[~zero].z, atol=1e-9)


def test_refuses_rather_than_write_outside_the_format():
    fr, al = _frame(), _allowed()
    fp = pd.DataFrame({"dk_draftable_id": fr.dk_draftable_id, "fp": 12.0})
    with pytest.raises(ValueError, match="not unique"):
        P.build(fr.assign(dk_player_id=lambda d: d.dk_player_id.where(d.index != 1, 1000)), fp, al, 4, 1.0)
    with pytest.raises(ValueError, match="not finite"):
        P.build(fr, fp, al, 4, float("nan"))
    out = P.build(fr.assign(opp=lambda d: d.opp.where(d.index != 0, "T99")), fp, al, 4, 1.0)
    assert "00-0000" not in set(out.gsis_id)                                # no z: absent (the arm gives it 0)


def test_too_few_prior_rows_gives_no_slope():
    fr, al = _frame(8), _allowed()
    fp = pd.DataFrame({"dk_draftable_id": fr.dk_draftable_id, "fp": 12.0})
    slope, n = P.walk_forward_slope([(4, fr, fp, pd.Series(12.0, index=fr["id"]))], al)
    assert slope is None and n < 30
