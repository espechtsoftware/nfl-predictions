"""Equivalence harness for restoring the chalk fade into nfl2.

The fade's proven +2 depends on the EXACT naive_ownership weights. nfl2 has no
runtime dependency on nfl_dfs (all three `nfl_dfs` greps in nfl2 are prose inside
docstrings), so restoring the fade means porting this function or passing the
vector in as data. Either way the weights must match bit for bit, and a silent
drift would be indistinguishable from the lever not working.

Run from the PRODUCTION repo, where the reference lives:

    PYTHONPATH=<worktree>/src <venv>/python -m pytest \
        reports/lab-handoffs/test_naive_ownership_port_equivalence.py

`ported` below is the candidate nfl2 copy. Measured 2026-09-22: bitwise identical
to the reference on 300 randomised frames (worst abs diff 0.0), including
non-default indexes, zero-variance salaries, identical projections and zero
projections.

It also pins the ONE case where the reference is not finite -- see
test_single_player_position_is_nan_in_BOTH.
"""
import numpy as np
import pandas as pd
import pytest

from nfl_dfs.backtest.field import naive_ownership as reference


def ported(players: pd.DataFrame) -> np.ndarray:
    """Candidate standalone copy for nfl2. No nfl_dfs import."""
    df = players.copy()
    value = df["proj"] / (df["salary"] / 1000.0)
    weights = np.zeros(len(df))
    for _pos, idx in df.groupby("pos").groups.items():
        loc = df.index.get_indexer(idx)
        v = value.iloc[loc]
        z = (v - v.mean()) / (v.std() + 1e-9)
        s = df["salary"].iloc[loc]
        zs = (s - s.mean()) / (s.std() + 1e-9)
        w = np.exp(1.2 * z + 0.3 * zs)
        weights[loc] = w / w.sum()
    return weights


POS = ["QB", "RB", "WR", "TE", "DST"]


def _frame(rng, n, shuffle_index=False):
    df = pd.DataFrame({
        "pos": rng.choice(POS, n),
        "salary": rng.integers(2000, 9000, n).astype(float),
        "proj": np.round(rng.uniform(0, 30, n), 2),
    })
    if shuffle_index:
        df.index = rng.permutation(n) + 1000
    return df


def test_port_is_bitwise_identical_on_randomised_slates():
    rng = np.random.default_rng(20260922)
    for t in range(300):
        df = _frame(rng, int(rng.integers(20, 700)), shuffle_index=(t % 5 == 0))
        a, b = reference(df), ported(df)
        assert np.array_equal(a, b, equal_nan=True), f"drift on trial {t}"


@pytest.mark.parametrize("name,df", [
    ("zero-variance salary", pd.DataFrame(
        {"pos": ["WR"] * 4, "salary": [4000.0] * 4, "proj": [9.0, 10.0, 11.0, 12.0]})),
    ("identical projections", pd.DataFrame(
        {"pos": ["RB"] * 4, "salary": [3000.0, 4000.0, 5000.0, 6000.0], "proj": [8.0] * 4})),
    ("zero projection", pd.DataFrame(
        {"pos": ["TE"] * 3, "salary": [3000.0, 4000.0, 5000.0], "proj": [0.0, 0.0, 5.0]})),
])
def test_edge_cases_match_and_stay_finite(name, df):
    a, b = reference(df), ported(df)
    assert np.array_equal(a, b), name
    assert np.isfinite(a).all(), name
    assert a.sum() == pytest.approx(1.0), name


def test_single_player_position_is_nan_in_BOTH():
    """A position group of exactly ONE player yields NaN -- in the reference too.

    pandas `.std()` is ddof=1, so a one-element group gives NaN, which flows
    through the z-score into exp() and out as NaN. It is CONTAINED to that
    position (other groups still sum to 1), and proj_tourney_production guards it
    with `np.nan_to_num(..., nan=0.0)` -- so that player silently receives NO
    fade rather than crashing the run.

    Pinned here because the guard lives in the CONSUMER, not the producer: any
    other caller of naive_ownership inherits the NaN. Not a blocker for a classic
    slate (633 players, no position near 1), but it is a real property of the
    function being restored into the money path.
    """
    df = pd.DataFrame({
        "pos": ["QB"] * 3 + ["RB"] * 4 + ["TE"] * 1,
        "salary": [7000.0, 6500.0, 6000.0, 8000.0, 5000.0, 4000.0, 3000.0, 4200.0][:8],
        "proj": [20.0, 18.0, 16.0, 19.0, 12.0, 9.0, 6.0, 10.5][:8],
    })
    a, b = reference(df), ported(df)
    assert np.array_equal(a, b, equal_nan=True)
    te = df.index[df.pos == "TE"][0]
    assert np.isnan(a[df.index.get_indexer([te])[0]]), "expected NaN for the lone TE"
    assert np.isfinite(a[df.index.get_indexer(df.index[df.pos == 'QB'])]).all(), "QB must be unaffected"
    guarded = np.nan_to_num(a, nan=0.0)
    assert np.isfinite(guarded).all() and guarded[df.index.get_indexer([te])[0]] == 0.0
