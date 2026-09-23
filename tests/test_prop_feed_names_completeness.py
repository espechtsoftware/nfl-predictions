"""2026-09-23: the name-match guard must use the same completeness boundary as market_points.

A slate player priced only by an anytime-TD market has no market_points row (minimum_markets=2); counting him
as "in the feed" stopped project-slate on Wednesday of Week 3 (236 TD-only players)."""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs import bq
from nfl_dfs.inference.market_source import MarketMatchError, resolve_live_market
from nfl_dfs.models import prop_market


def test_feed_names_require_two_markets_by_default(monkeypatch):
    seen = {}
    def fake(sql, params=None):
        seen["sql"] = sql
        return pd.DataFrame({"player": ["Full Player"]})
    monkeypatch.setattr(bq, "query_df", fake)
    assert prop_market.prop_feed_player_names(2026, 3) == {"Full Player"}
    assert "HAVING COUNT(DISTINCT market) >= 2" in seen["sql"]
    prop_market.prop_feed_player_names(2026, 3, minimum_markets=1)
    assert ">= 1" in seen["sql"]
    with pytest.raises(ValueError):
        prop_market.prop_feed_player_names(2026, 3, minimum_markets=0)


def _feats():
    return pd.DataFrame({"gsis_id": ["A", "B", "C"], "display_name": ["Full Player", "Td Only", "Name Miss"],
                         "position": ["WR", "TE", "WR"]})


def test_td_only_player_is_model_only_but_a_real_name_miss_still_stops_the_run():
    market = pd.DataFrame({"gsis_id": ["A"], "market_points": [14.0]})
    # the feed list now holds only players with >= 2 markets: the TD-only TE is absent from it
    m, src = resolve_live_market(_feats(), market, {"Full Player"}, min_coverage=0.0)
    assert list(src.source) == ["props", "model_only_no_line", "model_only_no_line"]
    assert m[0] == 14.0 and np.isnan(m[1])
    # a fully priced player whose id failed to resolve is still caught (the Jefferson case)
    with pytest.raises(MarketMatchError):
        resolve_live_market(_feats(), market, {"Full Player", "Name Miss"}, min_coverage=0.0)
