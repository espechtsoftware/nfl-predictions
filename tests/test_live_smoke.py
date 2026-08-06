"""End-to-end OFFLINE smoke of the live sim build chain (2026-08-04
readiness check): synthetic slate through the REAL build_sim_lineups —
cold-start fill, ensemble component models, correlated sims, draw
shaping (TabPFN cache empty -> empirical fallback), fade (booster
unavailable -> naive fallback), tilts, candidate generation, and
tail-coverage selection. This is the week-1 'first click' path with
every BigQuery/registry touchpoint mocked."""
import numpy as np
import pandas as pd
import pytest


@pytest.fixture()
def live_slate(panel):
    season = int(panel.season.max())
    rows = panel[(panel.season == season) & (panel.week == 3)].head(60).copy()
    rows = rows.reset_index(drop=True)
    rows["dk_player_id"] = np.arange(100, 100 + len(rows))
    rows["display_name"] = ["P" + str(i) for i in range(len(rows))]
    rows["dk_position"] = rows.position
    rows["salary"] = np.clip(3000 + (np.arange(len(rows)) % 40) * 130,
                             3000, 8100)
    teams = [f"T{i % 8}" for i in range(len(rows))]
    rows["team"] = teams
    rows["opponent"] = [f"T{(i + 1) % 8}" for i in range(len(rows))]
    rows["game_id"] = [f"g{min(i % 8, (i + 1) % 8)}" for i in range(len(rows))]
    rows["game_total"] = 45.0
    return rows


def test_live_build_chain_offline(monkeypatch, panel, live_slate):
    from nfl_dfs.inference import live_lineups
    from nfl_dfs.models import components
    from nfl_dfs.optimizer.lineup import StackRules

    season = int(panel.season.max())
    monkeypatch.setenv("MODEL_ENSEMBLE", "2")  # exercise ensemble path, fast
    cm = components.train(panel, target_season=season, num_boost_round=15)
    monkeypatch.setattr(
        "nfl_dfs.models.train_job.load_latest_component_models",
        lambda: (cm, "test/components/w1"))
    monkeypatch.setattr(
        "nfl_dfs.inference.run_projections.upcoming_slate_features",
        lambda s, w: live_slate)
    # BQ touchpoints -> empty (tabpfn cache missing, notes absent)
    import nfl_dfs.bq as bqmod
    monkeypatch.setattr(bqmod, "query_df",
                        lambda sql, **k: pd.DataFrame())
    # market blend -> no market rows; dst -> none; booster -> unavailable
    monkeypatch.setattr("nfl_dfs.models.blend.market_projection_frame",
                        lambda df: pd.Series(np.nan, index=df.index))
    from nfl_dfs.backtest import replay as rp
    monkeypatch.setattr(rp, "_ownership_booster", lambda s: None)
    monkeypatch.setattr(rp, "punt_boom_flags_live",
                        lambda s, w: set(), raising=False)
    import nfl_dfs.inference.dst_projections as dstm
    dst = pd.DataFrame({
        "dk_player_id": [900, 901, 902, 903],
        "display_name": ["D0", "D1", "D2", "D3"],
        "team": ["T0", "T2", "T4", "T6"],
        "opponent": ["T1", "T3", "T5", "T7"],
        "salary": [2800, 3000, 3200, 3400],
        "proj_points": [6.0, 5.5, 7.0, 6.5]})
    monkeypatch.setattr(dstm, "project_dst",
                        lambda s, w, model_version=None: dst,
                        raising=False)

    lineups = live_lineups.build_sim_lineups(
        season, 3, n_entries=4, stack=None, tail_line=150.0,
        n_sims=300, seed=7)
    assert len(lineups) == 4
    for lu in lineups:
        assert len(lu.players) == 9
        assert lu.salary <= 50_000
        ids = [p["id"] for p in lu.players]
        assert len(ids) == len(set(ids))

    # A selected classic draft group can price an overlapping player
    # differently from the largest-group row used to source live features.
    # The exact chosen snapshot must win before salary-sensitive tilts.
    slate, _ = live_lineups.build_slate_with_draws(
        season, 3, n_sims=20, seed=7, salary_overrides={100: 4321})
    assert int(slate.loc[slate.id == 100, "salary"].iloc[0]) == 4321
