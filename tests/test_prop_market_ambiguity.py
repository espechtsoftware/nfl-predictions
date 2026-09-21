"""Ambiguous prop-name spellings are resolved against the slate, never arbitrarily (Week-2 2026 post-mortem).

Week 2 2026: "justin jefferson" normalized to two GSIS ids in the roster union (the WR and a roster-only rookie), the
matcher dropped the spelling, and the blend substituted the WR's one-game DK PPG (31.2) as the market at 55% weight.
"""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.models import prop_market


WR, ROOKIE, LAMB = "00-0036322", "00-0041075", "00-0036358"


def _props():
    rows = []
    for player in ("Justin Jefferson", "CeeDee Lamb"):
        for book in ("draftkings", "fanduel"):
            rows += [
                dict(market="player_reception_yds", outcome_name="Over", point=79.5, price=-112),
                dict(market="player_reception_yds", outcome_name="Under", point=79.5, price=-112),
                dict(market="player_receptions", outcome_name="Over", point=6.5, price=-115),
                dict(market="player_receptions", outcome_name="Under", point=6.5, price=-105),
                dict(market="player_anytime_td", outcome_name="Yes", point=np.nan, price=200),
            ]
            for r in rows[-5:]:
                r.update(season=2026, week=2, bookmaker=book, player=player, snapshot_ts="2026-09-20T14:00:00Z")
    return pd.DataFrame(rows)


def _schedules():
    return pd.DataFrame([dict(season=2026, week=2, gameday="2026-09-20", gametime="13:00", game_type="REG", weekday="Sunday")])


def _names():
    return pd.DataFrame([
        dict(gsis_id=WR, display_name="Justin Jefferson"),
        dict(gsis_id=ROOKIE, display_name="Justin Jefferson"),
        dict(gsis_id=LAMB, display_name="CeeDee Lamb"),
    ])


@pytest.fixture
def fake_warehouse(monkeypatch):
    def query_df(sql, *args, **kwargs):
        if "prop_lines" in sql:
            return _props()
        if "schedules" in sql:
            return _schedules()
        return _names()
    monkeypatch.setattr(prop_market, "query_df", query_df)


def _points(df, gsis):
    sub = df[(df.week == 2) & (df.gsis_id == gsis)]
    return None if sub.empty else float(sub.market_points.iloc[0])


def test_ambiguous_spelling_is_dropped_without_slate_ids(fake_warehouse):
    out = prop_market.market_points((2026,), minimum_markets=2)
    assert _points(out, LAMB) is not None and _points(out, LAMB) > 10
    assert _points(out, WR) is None and _points(out, ROOKIE) is None


def test_slate_resolves_the_spelling_to_the_one_id_on_the_slate(fake_warehouse):
    plain = prop_market.market_points((2026,), minimum_markets=2)
    out = prop_market.market_points((2026,), minimum_markets=2, prefer_ids={WR, LAMB})
    assert _points(out, WR) is not None and _points(out, WR) > 10 and _points(out, ROOKIE) is None
    # the identical inputs for Jefferson and Lamb must price identically; Lamb is unchanged by the option
    assert _points(out, WR) == pytest.approx(_points(out, LAMB))
    assert _points(out, LAMB) == pytest.approx(_points(plain, LAMB))
    assert len(out) == len(plain) + 1


def test_two_colliding_ids_on_the_slate_stay_ambiguous(fake_warehouse):
    out = prop_market.market_points((2026,), minimum_markets=2, prefer_ids={WR, ROOKIE, LAMB})
    assert _points(out, WR) is None and _points(out, ROOKIE) is None and _points(out, LAMB) is not None


def test_prefer_ids_with_no_ambiguity_is_a_no_op(fake_warehouse):
    out = prop_market.market_points((2026,), minimum_markets=2, prefer_ids={"00-0000000"})
    plain = prop_market.market_points((2026,), minimum_markets=2)
    pd.testing.assert_frame_equal(out.reset_index(drop=True), plain.reset_index(drop=True))
