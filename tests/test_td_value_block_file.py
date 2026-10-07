"""scripts/td_value_block_file.py (the operator's under-$7,000 idea as a live block, 10-07): the outside reviewer's replay
formula (make_tdup_files.py) for every frame skill player, the combined option, the unmatched-name report and the
refusals. Offline."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import td_value_block_file as T  # noqa: E402


def _frame(n=60, seed=3):
    rng = np.random.default_rng(seed)
    pos = ["QB", "RB", "WR", "TE"]
    rows = [{"id": f"00-{k:04d}", "dk_player_id": 1000 + k, "display_name": f"P{k}", "pos": pos[k % 4], "team": f"T{k % 8}",
             "opp": f"T{(k + 1) % 8}", "salary": int(rng.integers(3000, 9500))} for k in range(n)]
    rows.append({"id": "T0_DST", "dk_player_id": 9, "display_name": "D", "pos": "DST", "team": "T0", "opp": "T1", "salary": 3000})
    return pd.DataFrame(rows)


def _td(frame, seed=4, drop=("P5",)):
    rng = np.random.default_rng(seed)
    f = frame[frame.pos.isin(["RB", "WR", "TE"]) & ~frame.display_name.isin(drop)]
    return pd.DataFrame({"player": f.display_name, "td": 0.1 + 0.00003 * f.salary + rng.normal(0, 0.05, len(f))})


def _reviewer_formula(fr, td):
    """make_tdup_files.py's loop body, verbatim in substance (the outside reviewer, 0ad813b2 / tdupside run)."""
    fr = fr.drop_duplicates("dk_player_id").copy()
    tdm = dict(zip(td.player.astype(str), td.td)); fr["td"] = fr.display_name.astype(str).map(tdm); fr["res"] = np.nan
    for pos in ("RB", "WR", "TE"):
        g = fr[(fr.pos == pos) & fr.td.notna()]
        b = np.polyfit(g.salary, g.td, 1); fr.loc[g.index, "res"] = g.td - np.polyval(b, g.salary)
    fr["z"] = fr.groupby("pos").res.transform(lambda v: (v - v.mean()) / v.std())
    fr["bonus"] = np.where(fr.pos.isin(["RB", "WR", "TE"]) & (fr.salary < 7000), np.clip(fr.z.fillna(0), 0, 2), 0.0)
    return dict(zip(fr.dk_player_id.astype(str), fr.bonus))


def test_the_bonus_is_the_reviewers_replay_formula_and_pred_own_carries_it_at_tilt_020():
    fr = _frame(); td = _td(fr)
    out, unmatched = T.build(fr, td, "2026-10-03T14:34:00Z")
    assert list(out.columns) == T.COLUMNS and len(out) == 60 and "DST" not in set(out.pos) and out.dk_player_id.is_unique
    want = _reviewer_formula(fr, td)
    assert np.allclose(out.b_td, [want[i] for i in out.dk_player_id])
    assert np.allclose(out.pred_own * T.TILT, out.bonus_points) and (out.b_matchup == 0).all()
    assert (out[out.pos == "QB"].b_td == 0).all() and (out[out.salary >= 7000].b_td == 0).all()
    assert out.b_td.between(0, 2).all() and (out.snapshot_ts == "2026-10-03T14:34:00Z").all()
    p5 = fr[fr.display_name == "P5"].iloc[0]                                 # P5 has no price: no bonus, named if cheap
    assert out.set_index("display_name").loc["P5", "b_td"] == 0.0 and (("P5" in unmatched) == (p5.salary < 7000))


def test_the_combined_option_sums_the_two_bonuses_before_the_blocks_cap():
    fr = _frame(); td = _td(fr)
    mu = pd.DataFrame({"dk_player_id": fr.dk_player_id.astype(str), "bonus_points": np.where(fr.index % 3 == 0, 1.5, 0.0)})
    out, _ = T.build(fr, td, "ts", mu)
    m = dict(zip(mu.dk_player_id, mu.bonus_points))
    assert np.allclose(out.b_matchup, [m[i] for i in out.dk_player_id])
    assert np.allclose(out.bonus_points, out.b_td + out.b_matchup) and np.allclose(out.pred_own, out.bonus_points / T.TILT)
    assert (out.bonus_points > 2.0).any()                                   # the sum can exceed 2; the union's cap binds there


def test_refusals():
    fr = _frame()
    with pytest.raises(ValueError, match="no skill players"):
        T.build(fr[fr.pos == "DST"], _td(fr), "ts")
    with pytest.raises(ValueError, match="no dk_player_id"):
        T.build(fr.assign(dk_player_id=fr.dk_player_id.where(fr.index != 1)), _td(fr), "ts")
    with pytest.raises(ValueError, match="no player carries a bonus"):
        T.build(fr, pd.DataFrame({"player": ["nobody"], "td": [0.3]}), "ts")


def test_timing_guards_refuse_a_naive_as_of_a_late_or_a_stale_snapshot():
    """The reviewer 10-07: a missed Saturday pull must not hand Friday's prices to the live file (max age 3 h by default),
    and an --as-of without a time zone is refused by name."""
    T.check_timing("2026-10-10T14:33:10Z", "2026-10-10T15:00:00Z", 3.0)                 # the Saturday pull: accepted
    with pytest.raises(ValueError, match="no time zone"):
        T.check_timing("2026-10-10T14:33:10Z", "2026-10-10T15:00:00", 3.0)
    with pytest.raises(ValueError, match="not before"):
        T.check_timing("2026-10-10T15:00:00Z", "2026-10-10T15:00:00Z", 3.0)
    with pytest.raises(ValueError, match="more than 3 h"):
        T.check_timing("2026-10-09T14:33:10Z", "2026-10-10T15:00:00Z", 3.0)             # Friday's pull: refused
