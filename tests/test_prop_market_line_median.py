"""MARKET_LINE_MEDIAN: rushing/receiving lines priced as the median of a gamma; default off is byte-identical."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from nfl_dfs.models import prop_market
from nfl_dfs.models.blend import american_to_prob, devig_two_way

LAMB = "00-0036358"


def test_gamma_honours_the_line_and_price():
    for market in ("player_reception_yds", "player_rush_yds"):
        for line, p in ((10.5, 0.5), (55.5, 0.47), (85.5, 0.55)):
            k, theta = prop_market.median_line_gamma(market, line, p)
            assert stats.gamma.sf(line, k, scale=theta) == pytest.approx(p, abs=1e-9)
            a, b = prop_market.MEDIAN_LINE_GAMMA[market]
            assert k == pytest.approx(np.exp(a + b * np.log(line)))
    # right skew: at an even price the mean sits above the line, by more yards than zero and less than the line
    k, theta = prop_market.median_line_gamma("player_reception_yds", 30.5, 0.5)
    assert 30.5 < k * theta < 40.0


def test_flag_parsing_fails_closed(monkeypatch):
    monkeypatch.delenv("MARKET_LINE_MEDIAN", raising=False)
    assert prop_market.line_median() is False
    monkeypatch.setenv("MARKET_LINE_MEDIAN", "1")
    assert prop_market.line_median() is True
    monkeypatch.setenv("MARKET_LINE_MEDIAN", "true")
    with pytest.raises(ValueError):
        prop_market.line_median()


def _props():
    rows = []
    for book in ("draftkings", "fanduel"):
        for market, point, over, under in (("player_reception_yds", 85.5, -112, -112), ("player_receptions", 6.5, -115, -105)):
            for outcome, price in (("Over", over), ("Under", under)):
                rows.append(dict(season=2026, week=2, bookmaker=book, market=market, outcome_name=outcome,
                                 player="CeeDee Lamb", price=price, point=point, snapshot_ts="2026-09-20T14:00:00Z"))
    return pd.DataFrame(rows)


@pytest.fixture
def warehouse(monkeypatch):
    def query_df(sql, *a, **k):
        if "prop_lines" in sql:
            return _props()
        if "schedules" in sql:
            return pd.DataFrame([dict(season=2026, week=2, gameday="2026-09-20", gametime="13:00", game_type="REG", weekday="Sunday")])
        return pd.DataFrame([dict(gsis_id=LAMB, display_name="CeeDee Lamb")])
    monkeypatch.setattr(prop_market, "query_df", query_df)


def _pts(monkeypatch, median, bonus):
    for name, v in (("MARKET_LINE_MEDIAN", median), ("MARKET_BONUS_AWARE", bonus)):
        if v is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, v)
    return float(prop_market.market_points((2026,), minimum_markets=2).market_points.iloc[0])


def test_market_points_move_exactly_the_yardage_leg(warehouse, monkeypatch):
    plain = _pts(monkeypatch, None, None)
    assert _pts(monkeypatch, "0", None) == plain
    p_over, _ = devig_two_way(american_to_prob(-112), american_to_prob(-112))
    k, theta = prop_market.median_line_gamma("player_reception_yds", 85.5, p_over)
    median = _pts(monkeypatch, "1", None)
    assert median - plain == pytest.approx(0.1 * (k * theta - 85.5), abs=1e-9)   # the even-price normal returns 85.5
    both = _pts(monkeypatch, "1", "1")
    assert both - median == pytest.approx(3.0 * stats.gamma.sf(100.0, k, scale=theta), abs=1e-9)
    # the bonus comes from the gamma, not the normal
    assert both - median != pytest.approx(3.0 * stats.norm.sf(100.0, 85.5, 0.30 * 85.5), abs=1e-3)
