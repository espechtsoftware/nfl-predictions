"""Integrity 5.3: the anytime-TD conversion prices only the "Yes" side; a "No" row is dropped, never read as a Yes price."""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import prop_market

LAMB = "00-0036358"


def _props(with_no: bool):
    rows = []
    for book in ("draftkings", "fanduel"):
        rows += [dict(market="player_reception_yds", outcome_name="Over", point=79.5, price=-112),
                 dict(market="player_reception_yds", outcome_name="Under", point=79.5, price=-112),
                 dict(market="player_anytime_td", outcome_name="Yes", point=np.nan, price=200)]
        if with_no:
            rows.append(dict(market="player_anytime_td", outcome_name="No", point=np.nan, price=-250))
    for r in rows:
        r.update(season=2026, week=2, bookmaker=r.get("bookmaker", "draftkings"), player="CeeDee Lamb",
                 snapshot_ts="2026-09-20T14:00:00Z")
    return pd.DataFrame(rows)


@pytest.fixture
def warehouse(monkeypatch):
    state = {"no": False}

    def query_df(sql, *a, **k):
        if "prop_lines" in sql:
            return _props(state["no"])
        if "schedules" in sql:
            return pd.DataFrame([dict(season=2026, week=2, gameday="2026-09-20", gametime="13:00", game_type="REG",
                                      weekday="Sunday")])
        return pd.DataFrame([dict(gsis_id=LAMB, display_name="CeeDee Lamb")])
    monkeypatch.setattr(prop_market, "query_df", query_df)
    return state


def test_a_no_side_row_does_not_change_the_price(warehouse):
    base = prop_market.market_points((2026,), minimum_markets=2)
    warehouse["no"] = True
    with_no = prop_market.market_points((2026,), minimum_markets=2)
    assert float(with_no.market_points.iloc[0]) == pytest.approx(float(base.market_points.iloc[0]))
