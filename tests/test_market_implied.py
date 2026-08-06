"""De-vig / implied-curve mechanics (Addendum 45)."""
import numpy as np
import pandas as pd

from nfl_dfs.inference.market_implied import (
    american_implied, curve_quantile, implied_curve, market_quantiles)


def _ladder():
    # A realistic DK alt ladder: P(over) falls as the line rises.
    rows = []
    for pt, over, under in [(29.5, -650, 475), (39.5, -270, 210),
                            (46.5, -165, 130), (59.5, 135, -165),
                            (67.5, 210, -265), (85.5, 500, -700)]:
        rows.append({"point": pt, "outcome_name": "Over", "price": over})
        rows.append({"point": pt, "outcome_name": "Under", "price": under})
    return pd.DataFrame(rows)


def test_american_implied_symmetry():
    assert abs(american_implied(100) - 0.5) < 1e-9
    assert abs(american_implied(-110) + american_implied(110) - 1.0) < 0.03


def test_curve_monotone_and_devigged():
    x, y = implied_curve(_ladder())
    assert (np.diff(x) > 0).all() and (np.diff(y) <= 1e-12).all()
    assert 0.8 < y[0] < 1.0 and 0.0 < y[-1] < 0.25


def test_quantiles_ordered_and_in_range():
    x, y = implied_curve(_ladder())
    med, q90 = curve_quantile(x, y, 0.5), curve_quantile(x, y, 0.9)
    assert med < q90
    assert 39.5 <= med <= 67.5 and q90 >= 67.5


def test_market_quantiles_frame():
    d = _ladder()
    d["season"], d["week"], d["market"], d["player"] = 2025, 1, "m", "A B"
    out = market_quantiles(d)
    assert len(out) == 1 and out.q50.iloc[0] < out.q90.iloc[0]


def test_prop_market_accepts_td_only_snapshot(monkeypatch):
    """A season with no two-way prices must not suppress its TD market."""
    from nfl_dfs.models import prop_market

    props = pd.DataFrame([{
        "season": 2019, "week": 1, "bookmaker": "book",
        "market": "player_anytime_td", "outcome_name": "Yes",
        "player": "A Player", "price": 150, "point": np.nan,
    }])
    names = pd.DataFrame([{"gsis_id": "p1", "display_name": "A Player"}])
    replies = iter([props, names])
    monkeypatch.setattr(prop_market, "query_df", lambda _sql: next(replies))

    out = prop_market.market_points((2019,))
    assert len(out) == 1
    assert out.gsis_id.iloc[0] == "p1"
    assert out.market_points.iloc[0] > 0
