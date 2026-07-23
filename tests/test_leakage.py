"""Leakage checker tested on synthetic data where we control the truth."""

import numpy as np
import pandas as pd
import pytest

from nfl_dfs.features.leakage import (
    LeakageError,
    assert_first_game_features_null,
    assert_no_leakage,
    trailing_mean_excluding_current,
)


def make_source(n_players=20, n_weeks=10, seed=7):
    rng = np.random.default_rng(seed)
    rows = []
    for p in range(n_players):
        for w in range(1, n_weeks + 1):
            rows.append(
                {"gsis_id": f"00-{p:07d}", "season": 2024, "week": w,
                 "target_share": rng.uniform(0, 0.35)}
            )
    return pd.DataFrame(rows)


def build_correct(source):
    out = source.copy()
    out["target_share_l4"] = trailing_mean_excluding_current(out, "target_share", window=4)
    out["games_played_prior"] = out.groupby(["gsis_id", "season"]).cumcount()
    return out


def build_leaky(source):
    """The classic bug: rolling window includes the current week."""
    out = source.sort_values(["gsis_id", "season", "week"]).copy()
    out["target_share_l4"] = out.groupby(["gsis_id", "season"])["target_share"].transform(
        lambda s: s.rolling(4, min_periods=1).mean()  # no shift(1) — leaks
    )
    out["games_played_prior"] = out.groupby(["gsis_id", "season"]).cumcount()
    return out


def test_reference_excludes_current_week():
    source = make_source(n_players=1, n_weeks=3)
    vals = source.target_share.tolist()
    got = trailing_mean_excluding_current(source, "target_share", window=4)
    assert np.isnan(got.iloc[0])                       # week 1: nothing prior
    assert got.iloc[1] == pytest.approx(vals[0])       # week 2: only week 1
    assert got.iloc[2] == pytest.approx(np.mean(vals[:2]))


def test_expanding_window():
    source = make_source(n_players=1, n_weeks=6)
    got = trailing_mean_excluding_current(source, "target_share", window=None)
    assert got.iloc[5] == pytest.approx(source.target_share.iloc[:5].mean())


def test_correct_build_passes():
    source = make_source()
    built = build_correct(source)
    assert_no_leakage(built, source, "target_share_l4", "target_share", window=4)
    assert_first_game_features_null(built, ["target_share_l4"])


def test_leaky_build_fails():
    source = make_source()
    built = build_leaky(source)
    with pytest.raises(LeakageError):
        assert_no_leakage(built, source, "target_share_l4", "target_share", window=4)


def test_leaky_build_fails_first_game_check():
    source = make_source()
    built = build_leaky(source)
    with pytest.raises(LeakageError):
        assert_first_game_features_null(built, ["target_share_l4"])


def test_unordered_input_handled():
    source = make_source().sample(frac=1, random_state=3)  # shuffle rows
    built = build_correct(source)
    assert_no_leakage(built, source, "target_share_l4", "target_share", window=4)
