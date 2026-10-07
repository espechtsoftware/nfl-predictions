"""scripts/paper_factor_file.py (study 38 amendment 6d, the paper factor-bonus arms): make_factor_files.py's formulas for
one week in the reviewer's file format -- the points-allowed blend, the matchup z over ALL the frame's skill players, the
own-type vacated share, the market against FP, the combined clip, FP's 0 and the refusals. Offline."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import paper_factor_file as P  # noqa: E402

TEAMS = [f"T{k}" for k in range(8)]


def _allowed():
    rows = []
    for t, team in enumerate(TEAMS):
        for p, pos in enumerate(("QB", "RB", "WR", "TE")):
            for w in range(1, 7):
                if not (team == "T7" and pos == "RB"):                     # T7 has no prior-season RB rows
                    rows.append({"season": 2025, "week": w, "def": team, "position": pos, "pts": 10.0 + t + p + w % 2})
            for w in range(1, 5):
                rows.append({"season": 2026, "week": w, "def": team, "position": pos, "pts": 20.0 + 3 * t - p})
    return pd.DataFrame(rows)


def _frame():
    rows, k = [], 0
    for j in range(8):
        for pos in ("QB", "RB", "WR", "TE"):
            rows.append({"id": f"00-{k:04d}", "dk_player_id": 1000 + k, "dk_draftable_id": 5000 + k, "pos": pos,
                         "team": TEAMS[j], "opp": TEAMS[(j + 3) % 8], "team_vacated_carry_share": 0.05 * (j % 3),
                         "team_vacated_target_share": 0.04 * (j % 4), "market_points": 14.0 + (k % 5) if k % 7 else np.nan,
                         "display_name": f"P{k}"})
            k += 1
    rows.append({"id": "T0_DST", "dk_player_id": 9, "dk_draftable_id": 9, "pos": "DST", "team": "T0", "opp": "T3",
                 "team_vacated_carry_share": 0.0, "team_vacated_target_share": 0.0, "market_points": np.nan, "display_name": "D"})
    return pd.DataFrame(rows)


def _fp(frame):
    fp = 12.0 + (frame.index % 6).to_numpy(float)
    d = pd.DataFrame({"dk_draftable_id": frame.dk_draftable_id, "fp": fp})
    d.loc[d.dk_draftable_id == 5001, "fp"] = 0.0                            # FP projects player 1 at 0
    return d[d.dk_draftable_id != 5002]                                    # player 2 has no FP value


def test_points_allowed_blend_prior_season_and_weeks_before_only():
    al = _allowed()
    apg = P.allowed_per_game(al, 2026, 3)
    prior = al[(al.season == 2025) & (al["def"] == "T2") & (al.position == "WR")].pts.mean()
    cur = al[(al.season == 2026) & (al.week < 3) & (al["def"] == "T2") & (al.position == "WR")].pts
    assert apg[("T2", "WR")] == pytest.approx((6 * prior + cur.sum()) / (6 + len(cur)))
    pos_mean = al[(al.season == 2025) & (al.position == "RB")].groupby("def").pts.mean().mean()
    cur7 = al[(al.season == 2026) & (al.week < 3) & (al["def"] == "T7") & (al.position == "RB")].pts
    assert apg[("T7", "RB")] == pytest.approx((6 * pos_mean + cur7.sum()) / (6 + len(cur7)))   # the position-mean fill
    al_future = al.copy(); al_future.loc[(al_future.season == 2026) & (al_future.week >= 3), "pts"] += 99
    assert P.allowed_per_game(al_future, 2026, 3) == pytest.approx(apg)    # weeks >= w never enter


def test_the_file_follows_make_factor_files_formulas_in_the_reviewers_format():
    fr, al = _frame(), _allowed()
    out, unmatched = P.build(fr, _fp(fr), al, 2026, 3)
    assert list(out.columns) == P.COLUMNS and unmatched == 0
    assert out.dk_player_id.is_unique and set(out.pos) == {"QB", "RB", "WR", "TE"} and "1002" not in set(out.dk_player_id)
    # the matchup z runs over ALL the frame's skill players (player 2 has no FP value but enters every z)
    apg = P.allowed_per_game(al, 2026, 3)
    sk = fr[fr.pos != "DST"].assign(raw=lambda d: [apg[(o, p)] for o, p in zip(d.opp, d.pos)])
    z = sk.groupby("pos").raw.transform(lambda s: (s - s.mean()) / (s.std() + 1e-9))
    want_m = dict(zip(sk.dk_player_id.astype(str), np.clip(z, 0, 2)))
    o = out.set_index("dk_player_id")
    live = o[o.fp > 0]
    assert np.allclose(live.b_matchup, [want_m[i] for i in live.index])
    src = fr.set_index(fr.dk_player_id.astype(str)).loc[live.index]
    share = np.where(src.pos == "RB", src.team_vacated_carry_share,
                     np.where(src.pos.isin(["WR", "TE"]), src.team_vacated_target_share, 0.0))
    assert np.allclose(live.b_vacated, np.clip(10 * share, 0, 3))
    assert np.allclose(live.b_market, np.clip(0.5 * (src.market_points - live.fp).fillna(0), 0, 2))
    assert np.allclose(live.b_combined, np.clip(live.b_matchup + live.b_vacated + live.b_market, 0, 3), atol=1e-6)
    assert (o.loc["1001", ["b_matchup", "b_vacated", "b_market", "b_combined"]] == 0).all()   # FP's 0: no bonus
    for k, (lo, hi) in P.CLIPS.items():
        assert out[f"b_{k}"].between(lo, hi).all()


def test_refuses_a_missing_id_and_an_empty_week():
    fr, al = _frame(), _allowed()
    with pytest.raises(ValueError, match="not unique / missing"):
        P.build(fr.assign(dk_player_id=fr.dk_player_id.where(fr.index != 4)), _fp(fr), al, 2026, 3)
    with pytest.raises(ValueError, match="no skill player"):
        P.build(fr, pd.DataFrame({"dk_draftable_id": [9], "fp": [5.0]}), al, 2026, 3)
    out, unmatched = P.build(fr.assign(opp=fr.opp.where(fr.index != 0, "T99")), _fp(fr), al, 2026, 3)
    assert unmatched == 1 and out.set_index("dk_player_id").loc["1000", "b_matchup"] == 0.0   # no allowed value: z 0
