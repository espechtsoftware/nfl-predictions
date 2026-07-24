import numpy as np
import pandas as pd

from nfl_dfs.trends.changepoint import (
    changepoint_probabilities,
    cusum_flags,
    detect_panel,
    two_window_pvalue,
)


def promoted_series(rng, n_before=8, n_after=6, lo=0.08, hi=0.26, noise=0.02):
    """WR3 usage for n_before weeks, then a promotion to WR1 usage."""
    return np.concatenate([
        rng.normal(lo, noise, n_before),
        rng.normal(hi, noise, n_after),
    ])


def test_bocpd_spikes_at_the_break():
    rng = np.random.default_rng(21)
    series = promoted_series(rng)
    cp = changepoint_probabilities(series)
    break_idx = 8
    window = cp[break_idx : break_idx + 3]
    assert window.max() > 0.5, f"no spike at the break: {np.round(cp, 2)}"
    # Post-warmup stretch before the break must stay quiet
    assert cp[5:break_idx].max() < 0.5


def test_bocpd_quiet_on_stable_series():
    rng = np.random.default_rng(22)
    series = rng.normal(0.2, 0.02, 14)
    cp = changepoint_probabilities(series)
    assert cp.max() < 0.5


def test_bocpd_operating_point_across_seeds():
    """~3% FP / ~98% hit at the shipped defaults; assert loose bounds so the
    test survives numeric drift."""
    fp = hits = 0
    n = 60
    for seed in range(n):
        rng = np.random.default_rng(seed)
        if changepoint_probabilities(rng.normal(0.2, 0.02, 14)).max() > 0.5:
            fp += 1
        rng = np.random.default_rng(10_000 + seed)
        cp = changepoint_probabilities(promoted_series(rng))
        if cp[8:11].max() > 0.5:
            hits += 1
    assert fp / n < 0.15, f"false-positive rate {fp / n:.1%}"
    assert hits / n > 0.85, f"hit rate {hits / n:.1%}"


def test_bocpd_handles_empty_and_short():
    assert changepoint_probabilities([]).shape == (0,)
    assert len(changepoint_probabilities([0.2])) == 1


def test_cusum_catches_shift():
    rng = np.random.default_rng(23)
    series = promoted_series(rng, n_before=10, n_after=8)
    flags = cusum_flags(series)
    assert flags[10:].any()
    assert not flags[:8].any()


def test_two_window_pvalue():
    rng = np.random.default_rng(24)
    shifted = promoted_series(rng, n_before=6, n_after=2)
    stable = rng.normal(0.2, 0.02, 8)
    assert two_window_pvalue(shifted) < 0.05
    assert two_window_pvalue(stable) > 0.05


def test_detect_panel_weeks_since_change():
    rng = np.random.default_rng(25)
    rows = []
    for w, v in enumerate(promoted_series(rng), start=1):
        rows.append({"gsis_id": "00-1", "season": 2024, "week": w, "target_share": v})
    # A stable control player
    for w, v in enumerate(rng.normal(0.15, 0.015, 14), start=1):
        rows.append({"gsis_id": "00-2", "season": 2024, "week": w, "target_share": v})
    out = detect_panel(pd.DataFrame(rows))

    p1 = out[out.gsis_id == "00-1"].sort_values("week")
    # weeks_since_change resets shortly after the week-9 break
    post = p1[p1.week.between(9, 11)]
    assert (post.weeks_since_change <= 2).any()

    p2 = out[out.gsis_id == "00-2"].sort_values("week")
    assert p2.weeks_since_change.iloc[-1] >= 10
