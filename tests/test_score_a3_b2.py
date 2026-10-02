"""PREREG-A3 / B2 readers: the pure parts on synthetic data (no BigQuery)."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import score_article_mentions as a3  # noqa: E402
import score_projection_blend as b2  # noqa: E402


def test_counted_titles_follow_the_frozen_patterns():
    assert a3.counted("2026 Week 4 DraftKings/FanDuel DFS Main Slate Early Look", a3.M_TITLES)
    assert a3.counted("Ryan Heath's 2026 Week 4 Fantasy Football Advanced Matchups", a3.M_TITLES)
    assert a3.counted("2026 Week 4 WR/CB Fantasy Football Matchups", a3.M_TITLES)
    assert not a3.counted("Guru's Best Bets: 2026 NFL Week 4", a3.M_TITLES)
    assert not a3.counted("Ryan Heath's 2026 Week 4 Fantasy Football Advanced Matchups", a3.M_DFS_TITLES)
    assert a3.counted("Barfield's DFS Slate Breakdown: Week 4", a3.M_DFS_TITLES)


def test_mentions_count_articles_with_suffix_insensitive_full_names_and_dst_nicknames():
    arts = pd.DataFrame({"title": ["DFS Main Slate Early Look", "Advanced Matchups", "Guru's Best Bets"],
                         "text": ["Kenneth Walker III is chalk. Walker again. The Bears DST is cheap.",
                                  "Kenneth Walker faces a soft front. Jalen Coker too.", "Kenneth Walker over 80.5"]})
    players = pd.DataFrame({"key": ["kenneth walker", "jalen coker", "bears", "aj brown"], "pos": ["RB", "WR", "DST", "WR"],
                            "nickname": [None, None, "Bears", None]})
    m = a3.mention_counts(arts, players, a3.M_TITLES)
    assert m["kenneth walker"] == 2 and m["jalen coker"] == 1 and m["bears"] == 1 and m["aj brown"] == 0   # betting not counted
    assert a3.mention_counts(arts, players, a3.M_DFS_TITLES)["kenneth walker"] == 1


def test_arms_are_the_frozen_forms_and_lift_a_near_zero_player_only_additively():
    base = pd.Series({"a": 20.0, "b": 0.0}); C = {"M": pd.Series({"b": 3.0})}
    out = a3.arms(base, C, "LAG")
    assert out["LAG_mult_M"]["b"] == 0.0 and out["LAG_add_M"]["b"] == 6.0 and out["LAG_mult_M"]["a"] == 20.0


def test_spearman_counts_a_player_absent_from_the_field_as_zero():
    pred = pd.Series({"a": 3.0, "b": 2.0, "c": 1.0}); real = pd.Series({"a": 30.0, "b": 10.0})
    assert a3.spearman(pred, real) == pytest.approx(1.0)


def test_blend_renormalises_over_the_sources_present():
    model = pd.Series({"x": 10.0, "y": 10.0, "z": 10.0}); market = pd.Series({"x": 13.0, "y": np.nan, "z": np.nan})
    fp = pd.Series({"x": 16.0, "y": 16.0, "z": np.nan})
    eq = b2.blend(model, market, fp, (1 / 3, 1 / 3, 1 / 3))
    assert eq["x"] == pytest.approx(13.0) and eq["y"] == pytest.approx(13.0) and eq["z"] == pytest.approx(10.0)
    w45 = b2.blend(model, market, fp, (0.45, 0.275, 0.275))
    assert w45["y"] == pytest.approx((0.45 * 10 + 0.275 * 16) / 0.725)


def test_score_is_mae_and_bias_overall_and_by_position():
    pred = pd.Series({"a": 10.0, "b": 20.0}); act = pd.Series({"a": 12.0, "b": 15.0}); pos = pd.Series({"a": "WR", "b": "QB"})
    s = b2.score(pred, act, pos)
    assert s["MAE"] == 3.5 and s["bias"] == 1.5 and s["MAE_WR"] == 2.0 and s["MAE_QB"] == 5.0


def test_gate_carries_the_served_projection_into_our_components():
    ours = pd.DataFrame({"proj_points": [18.2, 12.0, 10.0], "model_points_pre": [17.0, 11.0, 9.0], "market_points": [19.0, np.nan, 11.0]},
                        index=["caleb williams", "x", "y"])
    served = pd.Series({"caleb williams": 0.0, "x": 6.0, "y": 10.0})                       # out; halved; unchanged
    g = b2.gate(ours, served)
    assert g.loc["caleb williams", ["proj_points", "model_points_pre", "market_points"]].tolist() == [0.0, 0.0, 0.0]
    assert g.loc["x", "model_points_pre"] == pytest.approx(5.5) and np.isnan(g.loc["x", "market_points"])
    assert g.loc["y", "model_points_pre"] == 9.0 and g.loc["y", "proj_points"] == 10.0
