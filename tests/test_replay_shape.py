

def test_tabpfn_marginals_maps_and_preserves_ranks(monkeypatch):
    """TABPFN_MARGINALS: draws remap onto the cached per-player quantile
    curve; rank order (the correlation carrier) is preserved; uncached
    rows keep their original draws."""
    import numpy as np
    import pandas as pd

    from nfl_dfs.backtest import replay

    rng = np.random.default_rng(3)
    draws = rng.gamma(2.0, 5.0, size=(2, 500)).astype(np.float32)
    keys = pd.DataFrame({"season": [2025, 2025], "week": [1, 1],
                         "gsis_id": ["A", "MISSING"]})
    cache = pd.DataFrame([{
        "season": 2025, "week": 1, "gsis_id": "A", "mean": 12.0,
        "q01": 0.5, "q05": 2.0, "q10": 4.0, "q50": 11.0,
        "q90": 24.0, "q95": 29.0, "q99": 38.0}])
    monkeypatch.setattr(replay, "query_df", None, raising=False)
    import nfl_dfs.bq as bqmod
    monkeypatch.setattr(bqmod, "query_df", lambda sql, **kw: cache)
    out = replay._tabpfn_marginals(draws, keys)
    r0, o0 = draws[0], out[0]
    assert (np.argsort(r0) == np.argsort(o0)).all(), "rank order preserved"
    assert abs(np.quantile(o0, 0.5) - 11.0) < 1.5
    assert abs(np.quantile(o0, 0.9) - 24.0) < 2.5
    assert (out[1] == draws[1]).all(), "uncached row untouched"
    assert (out >= 0).all()


def test_tabpfn_research_cache_table_is_exactly_licensed(monkeypatch):
    import numpy as np
    import pandas as pd
    import pytest

    from nfl_dfs.backtest import replay
    import nfl_dfs.bq as bqmod

    queries = []
    cache = pd.DataFrame([{
        "season": 2025, "week": 1, "gsis_id": "A", "mean": 12.0,
        "q01": 0.5, "q05": 2.0, "q10": 4.0, "q50": 11.0,
        "q90": 24.0, "q95": 29.0, "q99": 38.0,
    }])

    def fake_query(sql, **_kwargs):
        queries.append(sql)
        return cache

    monkeypatch.setattr(bqmod, "query_df", fake_query)
    draws = np.arange(100, dtype=float).reshape(1, -1)
    keys = pd.DataFrame({
        "season": [2025], "week": [1], "gsis_id": ["A"],
    })
    replay._tabpfn_marginals(
        draws, keys,
        env={"TABPFN_MARGINAL_TABLE": "tabpfn_active_label_treatment_v1"},
    )
    assert "tabpfn_active_label_treatment_v1" in queries[0]
    with pytest.raises(ValueError, match="unlicensed TABPFN_MARGINAL_TABLE"):
        replay._tabpfn_marginals(
            draws, keys,
            env={"TABPFN_MARGINAL_TABLE": "tabpfn_projections; DROP TABLE x"},
        )


def test_marginal_rank_ties_use_world_index_as_stable_tiebreaker():
    """Equal outcomes cannot acquire CPU-dependent marginal ranks."""
    import numpy as np

    from nfl_dfs.backtest.replay import _stable_ordinal_ranks

    draws = np.array([2.0, 1.0, 1.0, 2.0, 1.0])
    # Values sort as world indices [1, 2, 4, 0, 3]. Equal values retain
    # their original simulation-column order.
    np.testing.assert_array_equal(
        _stable_ordinal_ranks(draws), np.array([3, 0, 1, 4, 2]))


def test_rookie_widen_scales_only_rookie_rows(monkeypatch):
    import numpy as np
    import pandas as pd

    from nfl_dfs.backtest.replay import apply_draw_shape

    monkeypatch.setenv("ROOKIE_WIDEN", "1")
    monkeypatch.setenv("TABPFN_MARGINALS", "0")
    monkeypatch.setenv("EMP_MARGINALS", "0")
    monkeypatch.setenv("SIM_WIDEN_DRAWS", "off")
    rng = np.random.default_rng(4)
    draws = rng.gamma(3, 4, (2, 800)).astype(np.float32)
    keys = pd.DataFrame({"season": [2026, 2026], "week": [1, 1],
                         "gsis_id": ["R", "V"], "is_rookie": [True, False]})
    out = apply_draw_shape(draws.copy(), pd.Series(["WR", "WR"]), 0, keys=keys)
    assert np.allclose(out[1], draws[1]), "veteran untouched"
    assert out[0].std() > draws[0].std() * 1.05, "rookie spread widened"
    assert abs(out[0].mean() - draws[0].mean()) < 0.15, "mean preserved"


def test_audit_smoke_limits_weeks_without_changing_default():
    import pandas as pd
    import pytest

    from nfl_dfs.backtest import replay

    slates = [pd.DataFrame({"week": [w]}) for w in range(1, 5)]
    assert replay._limit_replay_slates(slates, None) is slates
    limited = replay._limit_replay_slates(slates, 1)
    assert [int(x.week.iloc[0]) for x in limited] == [1]
    with pytest.raises(ValueError, match="at least 1"):
        replay._limit_replay_slates(slates, 0)


def test_dst_salary_query_validates_weekly_opponent(monkeypatch):
    """Adjacent-Thursday rows share the prior source week.  The replay must
    join both team and opponent to schedule_long before choosing a salary."""
    import pandas as pd

    from nfl_dfs.backtest import replay
    import nfl_dfs.bq as bq

    queries = []

    def fake_query(sql, **_kwargs):
        queries.append(sql)
        return pd.DataFrame()

    monkeypatch.setattr(bq, "query_df", fake_query)
    replay.load_panel_and_dst(2024)
    dst_sql = queries[1]
    assert "schedule_long" in dst_sql
    assert "s.team = h.team AND s.opponent = h.opp" in dst_sql
    assert dst_sql.index("schedule_long") < dst_sql.index("computed AS")
    assert "team_defense_week" in dst_sql
    assert "fumble_lost = 1" not in dst_sql
    assert "ORDER BY sal.season, sal.week, sal.team, sal.opp" in dst_sql


def test_replay_player_name_join_cannot_duplicate_training_rows(monkeypatch):
    """player_ids has legacy duplicate GSIS ids; name lookup is one-to-one."""
    import pandas as pd

    from nfl_dfs.backtest import replay
    import nfl_dfs.bq as bq

    queries = []

    def fake_query(sql, **_kwargs):
        queries.append(sql)
        return pd.DataFrame()

    monkeypatch.setattr(bq, "query_df", fake_query)
    replay.load_panel_and_dst(2024)
    panel_sql = queries[0]
    assert "ARRAY_AGG(name IGNORE NULLS ORDER BY name LIMIT 1)" in panel_sql
    assert "GROUP BY gsis_id" in panel_sql
    assert "LEFT JOIN `nfl-dfs-prod.nfl_raw.player_ids` i USING" not in panel_sql


def test_dst_salary_query_normalizes_all_historical_team_aliases(monkeypatch):
    """RotoGuru aliases must not disappear against modern schedule codes."""
    import pandas as pd

    from nfl_dfs.backtest import replay
    import nfl_dfs.bq as bq

    queries = []

    def fake_query(sql, **_kwargs):
        queries.append(sql)
        return pd.DataFrame()

    monkeypatch.setattr(bq, "query_df", fake_query)
    replay.load_panel_and_dst(2019)
    dst_sql = queries[1]

    for old, new in {
        "GNB": "GB", "JAC": "JAX", "KAN": "KC", "LAR": "LA",
        "LVR": "LV", "NOR": "NO", "NWE": "NE", "OAK": "LV",
        "SD": "LAC", "SDG": "LAC", "SFO": "SF", "STL": "LA",
        "TAM": "TB",
    }.items():
        mapping = f"WHEN '{old}' THEN '{new}'"
        # Once in the team expression and once in the opponent expression.
        assert dst_sql.count(mapping) == 2
    assert "CASE team_abbr" in dst_sql
    assert "CASE opponent" in dst_sql


def test_replay_target_and_dst_are_restricted_to_sunday_main_slate(
        monkeypatch):
    """NFL-week salary feeds must never become an all-games DFS slate."""
    import pandas as pd

    from nfl_dfs.backtest import replay
    import nfl_dfs.bq as bq

    queries = []

    def fake_query(sql, **_kwargs):
        queries.append(sql)
        return pd.DataFrame()

    monkeypatch.setattr(bq, "query_df", fake_query)
    replay.load_panel_and_dst(2024)
    panel_sql, dst_sql = queries
    predicate_parts = (
        "sc.game_type = 'REG'",
        "sc.weekday = 'Sunday'",
        "SAFE.PARSE_TIME('%H:%M', sc.gametime) >= TIME '13:00:00'",
        "SAFE.PARSE_TIME('%H:%M', sc.gametime) < TIME '19:00:00'",
    )
    for part in predicate_parts:
        assert part in panel_sql
        assert part in dst_sql
    assert "t.season < 2024 OR" in panel_sql
    assert ".nfl_raw.schedules` sc USING (game_id)" in dst_sql


def test_dst_salary_query_rejects_duplicate_valid_team_weeks(monkeypatch):
    import pandas as pd
    import pytest

    from nfl_dfs.backtest import replay
    import nfl_dfs.bq as bq

    calls = 0

    def fake_query(_sql, **_kwargs):
        nonlocal calls
        calls += 1
        if calls == 1:
            return pd.DataFrame()
        return pd.DataFrame([
            {"season": 2024, "week": 1, "team": "BUF", "opp": "ARI",
             "salary": 3200, "actual": 8},
            {"season": 2024, "week": 1, "team": "BUF", "opp": "ARI",
             "salary": 3100, "actual": 8},
        ])

    monkeypatch.setattr(bq, "query_df", fake_query)
    with pytest.raises(ValueError, match="one row per team-week"):
        replay.load_panel_and_dst(2024)
