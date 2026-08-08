import os

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest import payout, replay


@pytest.fixture(scope="module")
def proj(small_panel):
    return replay.replay_projections(
        small_panel, season=2022, n_sims=2000, num_boost_round=80, seed=1
    )


def test_replay_is_point_in_time(proj, small_panel):
    # Projections must come from a model that never saw 2022: they can't
    # equal actuals, and they must exist for every 2022 panel row.
    assert len(proj) == (small_panel.season == 2022).sum()
    assert not np.allclose(proj.proj_points, proj.actual)
    assert proj.proj_p10.le(proj.proj_p90 + 1e-9).all()


def test_role_snapshot_fields_survive_projection_and_slate_build(small_panel):
    """The snapshot writer cannot audit a feature dropped by replay plumbing."""
    panel = small_panel.copy()
    panel["target_share_last"] = 0.22
    panel["target_share_jump"] = 0.06
    panel["is_cold_start"] = False
    projected = replay.replay_projections(
        panel, season=2022, n_sims=40, num_boost_round=5, seed=17,
    )
    assert projected.target_share_last.eq(0.22).all()
    assert projected.target_share_jump.eq(0.06).all()
    assert not projected.is_cold_start.astype(bool).any()

    one_week = projected[projected.week == projected.week.min()].copy()
    slates = replay.build_slates(one_week, dst=None)
    assert len(slates) == 1
    slate = slates[0]
    assert slate.target_share_last.eq(0.22).all()
    assert slate.target_share_jump.eq(0.06).all()
    assert not slate.is_cold_start.astype(bool).any()


def test_role_belief_projection_is_exact_and_restores_baseline_env(
        small_panel, monkeypatch):
    features = ",".join(replay.ROLE_BELIEF_FEATURES)
    monkeypatch.setenv("ROLE_BELIEF_FEATURES", features)
    monkeypatch.setenv("ROLE_BELIEF_SEED", "73")
    alternate, draws = replay.role_belief_projections(
        small_panel, season=2022, n_sims=20, num_boost_round=5)
    assert len(alternate) == (small_panel.season == 2022).sum()
    assert draws.shape == (len(alternate), 20)
    assert "EXTRA_FEATURES" not in os.environ

    monkeypatch.setenv("ROLE_BELIEF_FEATURES", "target_share_last")
    with pytest.raises(ValueError, match="must be exactly"):
        replay.role_belief_projections(
            small_panel, season=2022, n_sims=10, num_boost_round=2)


def test_replay_metrics(proj):
    overall, by_pos = replay.replay_metrics(proj)
    assert overall["mae"] < 7.65  # learned signal (sigma 6; small margin
    # for correlated-game-factor simulation variance at low n_sims)
    # Synthetic component labels are drawn independently of y_dk_points, so
    # tight calibration isn't achievable here by construction — directional
    # bounds only. Real calibration is judged on warehouse replays.
    assert overall["coverage_p10"] < 0.35
    assert overall["coverage_p90"] > 0.50
    assert overall["coverage_p10"] < overall["coverage_p90"]
    assert set(by_pos.index) == {"QB", "RB", "WR", "TE"}
    # conftest's QB passing labels are constants (no usage link), so QB rank
    # correlation is structurally ~0 on synthetic data; judge the positions
    # whose labels actually carry signal.
    assert (by_pos.drop("QB").rank_corr > 0.2).all()
    assert np.isfinite(by_pos.rank_corr).all()


def _dst(seed=3):
    rng = np.random.default_rng(seed)
    rows = []
    for t in range(8):
        for wk in range(1, 18):
            rows.append({"season": 2022, "week": wk, "team": f"T{t}",
                         "opp": f"T{(t + 1) % 8}", "salary": 2900,
                         "actual": max(0.0, rng.normal(7, 5))})
    return pd.DataFrame(rows)


def test_dst_projection_is_strictly_prior():
    d = replay.dst_slate_rows(_dst())
    wk1 = d[d.week == 1]
    assert (wk1.proj == replay.DST_FALLBACK_PROJ).all()
    one = d[d.team == "T0"].sort_values("week")
    expected_wk3 = one[one.week <= 2].actual.mean()
    assert one[one.week == 3].proj.iloc[0] == pytest.approx(expected_wk3)


def test_contest_replay_runs(proj):
    weeks = proj[proj.week <= 2].copy()  # two weeks keeps this fast
    result = replay.run_contest_replay(
        weeks, _dst(), payout.double_up(entry_fee=5, field_size=1000),
        n_entries=3, field_size=200, seed=1,
    )
    assert len(result.weeks) == 2
    assert all(len(w.winnings) == 3 for w in result.weeks)
    assert np.isfinite(result.total_roi)



def test_contest_replay_tail_selection(proj, small_panel):
    # Full issue-#5 path: correlated draws -> candidate pool (leverage batch
    # + boom-draw solves) -> greedy coverage selection. A low line keeps
    # coverage non-degenerate on the tiny synthetic slate.
    p, draws = replay.replay_projections(
        small_panel, season=2022, n_sims=200, num_boost_round=40, seed=1,
        return_draws=True,
    )
    weeks = p[p.week <= 1].copy()
    result = replay.run_contest_replay(
        weeks, _dst(), payout.double_up(entry_fee=5, field_size=1000),
        n_entries=3, field_size=200, seed=1,
        draws=draws, tail_line=60.0, n_boom_solves=3,
    )
    assert len(result.weeks) == 1
    assert len(result.weeks[0].winnings) == 3
    ids = [frozenset(pl["id"] for pl in lu.players)
           for lu in result.weeks[0].lineups]
    assert len(set(ids)) == 3  # selected entries are distinct lineups


def test_dst_qb_experience_adjustment():
    from nfl_dfs.inference.qb_experience import adjustment

    starts = pd.Series([0, 3, 4, 10, 11, 30, 31, 200, np.nan])
    adj = adjustment(starts)
    assert list(adj[:2]) == [2.2, 2.2]          # rookie tier
    assert list(adj[2:4]) == [1.5, 1.5]         # early career
    assert list(adj[4:6]) == [-0.5, -0.5]       # established
    assert list(adj[6:8]) == [-0.7, -0.7]       # veteran
    assert adj.iloc[8] == 0.0                    # unknown starter

    d = _dst()
    qb = pd.DataFrame({"season": 2022, "week": d.week, "team": d.opp,
                       "prior_starts": 0}).drop_duplicates()
    plain = replay.dst_slate_rows(_dst())
    adj_rows = replay.dst_slate_rows(_dst(), qb)
    merged = plain.merge(adj_rows, on=["team", "week"], suffixes=("_p", "_a"))
    assert np.allclose(merged.proj_a - merged.proj_p, 2.2)  # all rookies
