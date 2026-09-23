"""MARKET_BONUS_AWARE: the +3 yardage bonuses priced from the line's own normal; default off is byte-identical."""
import numpy as np
import pandas as pd
import pytest
from scipy import stats

from nfl_dfs.models import prop_market
from nfl_dfs.models.blend import american_to_prob, devig_two_way, prop_line_to_mean

LAMB = "00-0036358"


def test_hand_computed_bonus_values():
    # receiving 85.5 at an even price: mean 85.5, sigma 0.30*85.5 = 25.65, z = 14.5/25.65 = 0.5653 -> P = 0.28593
    assert prop_market.yardage_bonus_points("player_reception_yds", 85.5, 85.5) == pytest.approx(3 * 0.285931, abs=1e-4)
    # passing is deliberately NOT bonused (QB conversion already unbiased; no INT market to offset it)
    assert prop_market.yardage_bonus_points("player_pass_yds", 265.5, 265.5) == 0.0
    # rushing uses the 100-yard threshold too; far below it the bonus is ~0
    assert prop_market.yardage_bonus_points("player_rush_yds", 20.5, 20.5) < 1e-6
    # 160.5: sigma 48.15, z = -60.5/48.15 = -1.2565 -> P = 0.89553 (a wide line keeps real miss risk)
    assert prop_market.yardage_bonus_points("player_rush_yds", 160.5, 160.5) == pytest.approx(3 * 0.895531, abs=1e-4)
    # no bonus on non-yardage markets
    for m in ("player_receptions", "player_pass_tds", "player_anytime_td"):
        assert prop_market.yardage_bonus_points(m, 6.5, 6.5) == 0.0


def test_flag_parsing_fails_closed(monkeypatch):
    monkeypatch.delenv("MARKET_BONUS_AWARE", raising=False)
    assert prop_market.bonus_aware() is False
    monkeypatch.setenv("MARKET_BONUS_AWARE", "1")
    assert prop_market.bonus_aware() is True
    monkeypatch.setenv("MARKET_BONUS_AWARE", "yes")
    with pytest.raises(ValueError):
        prop_market.bonus_aware()


def _props(line=85.5):
    rows = []
    for book in ("draftkings", "fanduel"):
        for market, point, over, under in (("player_reception_yds", line, -112, -112), ("player_receptions", 6.5, -115, -105)):
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


def test_market_points_add_exactly_the_bonus_and_default_is_unchanged(warehouse, monkeypatch):
    monkeypatch.delenv("MARKET_BONUS_AWARE", raising=False)
    off = float(prop_market.market_points((2026,), minimum_markets=2).market_points.iloc[0])
    monkeypatch.setenv("MARKET_BONUS_AWARE", "0")
    assert float(prop_market.market_points((2026,), minimum_markets=2).market_points.iloc[0]) == off
    monkeypatch.setenv("MARKET_BONUS_AWARE", "1")
    on = float(prop_market.market_points((2026,), minimum_markets=2).market_points.iloc[0])
    p_over, _ = devig_two_way(american_to_prob(-112), american_to_prob(-112))
    mean = prop_line_to_mean(85.5, p_over, "normal")
    want = 3.0 * stats.norm.sf(100.0, loc=mean, scale=0.30 * 85.5)
    assert on - off == pytest.approx(want, abs=1e-9)
