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
