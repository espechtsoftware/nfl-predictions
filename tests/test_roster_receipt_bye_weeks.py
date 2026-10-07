"""The target-week roster receipt in bye weeks (2026-10-07): Week 5 has 30 teams on the schedule and nflverse's weekly
roster holds 30, so "COUNT(DISTINCT team) = 32" refused every bye week's projections (Tuesday's scheduled project-slate,
Wednesday's pre-check). The receipt must be complete against the week's REG schedule instead. Offline: the SQL is
captured, never sent."""
import pandas as pd
import pytest

from nfl_dfs.inference import run_projections as rp


def test_the_roster_receipt_counts_the_weeks_scheduled_teams_not_32(monkeypatch):
    seen = {}

    def fake_query(sql, params=None, *a, **k):
        seen["sql"], seen["params"] = sql, params
        return pd.DataFrame()

    monkeypatch.setattr(rp, "query_df", fake_query)
    with pytest.raises(RuntimeError, match="no upcoming classic slates"):
        rp.upcoming_slate_features(2026, 5)
    sql = " ".join(seen["sql"].split())
    assert "COUNT(DISTINCT r.team) = 32" not in sql
    assert "target_week_teams AS (" in sql and "SELECT COUNT(DISTINCT t) AS n FROM ( SELECT home_team AS t" in sql
    assert "COUNT(DISTINCT r.team) >= (SELECT n FROM target_week_teams)" in sql
    assert "(SELECT n FROM target_week_teams) >= 2" in sql
    assert "game_type = 'REG'" in sql and seen["params"] == {"season": 2026, "week": 5}
