"""2026 contest_ownership rows are one per player per roster SLOT (a WR has a WR row and a FLEX row); 2022-2025 rows are
one per player. Every per-player aggregation must dedupe import retries per slot and then SUM the slots -- MAX drops the
FLEX share and AVG roughly halves a flex player (found 2026-09-22; README data-deficiency row of that date)."""
import re

import pandas as pd
import pytest


def _norm(sql: str) -> str:
    return re.sub(r"\s+", " ", sql)


def test_ownership_model_target_dedupes_per_slot_then_sums(monkeypatch):
    import nfl_dfs.models.ownership as own
    seen = {}
    monkeypatch.setattr("nfl_dfs.bq.query_df", lambda sql, *a, **k: seen.setdefault("sql", sql) and pd.DataFrame())
    with pytest.raises(RuntimeError):
        own.training_frame()
    sql = _norm(seen["sql"])
    assert "PARTITION BY season, week, contest_id, display_name, roster_position" in sql, "dedupe must keep every slot"
    assert "SUM(pct_drafted) AS pct_drafted FROM own_rows GROUP BY season, week, contest_id, display_name" in sql, \
        "slots must be summed into a per-contest ownership before averaging across contests"
    assert "AVG(pct_drafted) AS pct_drafted FROM per_contest" in sql


def test_leaderboard_ownership_sums_slots_after_deduping_retries(monkeypatch):
    import nfl_dfs.analysis.leaderboard as lb
    calls = []

    def fake(sql, *a, **k):
        calls.append(_norm(sql))
        if "contest_entries" in sql:
            return pd.DataFrame({"entry_id": ["e1"]})       # non-empty so run() proceeds to the ownership query
        raise RuntimeError("stop after the ownership query")
    monkeypatch.setattr("nfl_dfs.bq.query_df", fake)
    with pytest.raises(RuntimeError, match="stop after"):
        lb.run(2026, 2, "195648007")
    own_sql = next(c for c in calls if "contest_ownership" in c)
    assert "SUM(pct_drafted) AS pct_drafted" in own_sql and "AVG(pct_drafted)" not in own_sql
    assert "PARTITION BY contest_id, display_name, roster_position ORDER BY imported_at DESC" in own_sql
