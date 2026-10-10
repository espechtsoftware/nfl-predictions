"""reports/2026-10-10-boom/boom_block_file.py (study 38 amendment 6z7's paper boom-chance block): the residual fit within
position, the bonus scale, the term-block format (every skill player once, the DST omitted, pred_own = bonus / 0.20), the join
by dk_player_id and the refusals. Offline."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "reports" / "2026-10-10-boom"))
import boom_block_file as B  # noqa: E402


def _frame(n=48, seed=5):
    rng = np.random.default_rng(seed)
    pos = ["QB", "RB", "WR", "TE"]
    rows = [{"id": f"00-{k:04d}", "dk_player_id": 1000 + k, "display_name": f"P{k}", "pos": pos[k % 4], "team": f"T{k % 8}",
             "opp": f"T{(k + 1) % 8}", "mean_projection": float(rng.uniform(2, 22))} for k in range(n)]
    rows.append({"id": "T0_DST", "dk_player_id": 9, "display_name": "D", "pos": "DST", "team": "T0", "opp": "T1",
                 "mean_projection": 6.0})
    return pd.DataFrame(rows)


def _p20(frame, seed=6, drop=(1001,)):
    rng = np.random.default_rng(seed)
    f = frame[(frame.pos != "DST") & ~frame.dk_player_id.isin(drop)]
    return pd.DataFrame({"dk_player_id": f.dk_player_id.astype(str),
                         "p20": np.clip(0.02 * f.mean_projection + rng.normal(0, 0.03, len(f)), 0, 1)})


def test_the_bonus_follows_the_design():
    fr = _frame(); p = _p20(fr)
    out = B.build(fr, p, "2026-10-04T16:04:17Z")
    assert list(out.columns) == B.COLUMNS and len(out) == 48 and "DST" not in set(out.pos)
    for pos, g in out[out.p_20_plus.notna()].groupby("pos"):                                # re-derive z and the bonus
        b = np.polyfit(g.proj, g.p_20_plus, B.FIT_DEG); r = g.p_20_plus - np.polyval(b, g.proj)
        z = (r - r.mean()) / r.std()
        assert np.allclose(g.z, z) and np.allclose(g.bonus_points, np.clip(B.SLOPE * z, 0, B.CAP))
    assert (B.SLOPE, B.CAP) == (1.0, 2.0)
    miss = out[out.dk_player_id == "1001"]
    assert miss.p_20_plus.isna().all() and (miss.bonus_points == 0).all()                    # no p_20_plus -> 0
    assert np.allclose(out.pred_own, out.bonus_points / 0.20) and (out.generated_at == "2026-10-04T16:04:17Z").all()


def test_the_refusals():
    fr = _frame()
    flat = _p20(fr).assign(p20=np.nan)                                                     # no p_20_plus anywhere -> no bonus
    with pytest.raises(ValueError, match="no player carries a bonus"):
        B.build(fr, flat, "t")
    p = _p20(fr)
    with pytest.raises(ValueError, match="repeats in the projection"):
        B.build(fr, pd.concat([p, p.head(1)]), "t")
    with pytest.raises(ValueError, match="repeats in the frame"):
        B.build(pd.concat([fr, fr.head(1)]), p, "t")


def test_the_timing_refusals():
    B.check_timing("2026-10-04T16:04:17Z", "2026-10-04T17:00:00Z", 36)
    with pytest.raises(ValueError, match="no time zone"):
        B.check_timing("2026-10-04T16:04:17Z", "2026-10-04T17:00:00", 36)
    with pytest.raises(ValueError, match="not before"):
        B.check_timing("2026-10-04T17:00:00Z", "2026-10-04T17:00:00Z", 36)
    with pytest.raises(ValueError, match="more than 36 h"):
        B.check_timing("2026-10-02T16:00:00Z", "2026-10-04T17:00:00Z", 36)


def test_the_query_never_reads_a_generation_at_or_after_as_of():
    assert "generated_at < TIMESTAMP(@as_of)" in B.P20_SQL and "player_projections`" in B.P20_SQL
    import inspect
    assert "default=36.0" in inspect.getsource(B.main)
