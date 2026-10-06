"""nfl_dfs.inference.entry_choice: study 32's R4 (joint coverage) and RND, with parity to the frozen lab rule.

The expected values below were computed 2026-10-06 by the FROZEN nfl2 experiments/s32_sorting.py @ 903a2ce (choose(), its
R4 picks and its rounded sim["R4"] / sim["RND"]) on the same seeded input; joint_coverage must reproduce them exactly,
whatever the chunk size."""
import numpy as np
import pytest

from nfl_dfs.inference import entry_choice as EC

FROZEN = {  # (N, S, m): (R4 rows, sim R4, sim RND) from s32_sorting.choose @ 903a2ce
    (634, 119, 1): ([4], 0.309815, 0.24234), (634, 119, 2): ([4, 8], 0.507086, 0.427315),
    (634, 119, 3): ([0, 3, 8], 0.649692, 0.568755), (4170, 1000, 1): ([4], 0.445781, 0.377172),
    (4170, 1000, 2): ([4, 8], 0.725921, 0.611474), (4170, 1000, 3): ([3, 4, 8], 0.843854, 0.757267),
    (634, 54, 1): ([4], 0.125134, 0.059216), (634, 54, 2): ([4, 8], 0.191678, 0.114724),
    (634, 54, 3): ([0, 4, 8], 0.248393, 0.166627),
}


def _F():
    rng = np.random.default_rng(20261006)
    return np.round(rng.beta(4, 2, size=(9, 60)), 4)


@pytest.mark.parametrize("chunk", [5, 20_000])
def test_parity_with_the_frozen_study_32_rule(chunk):
    F = _F()
    for (N, S, m), (rows, v4, vr) in FROZEN.items():
        r4, got_v4, got_vr = EC.joint_coverage(F, N, S, m, chunk=chunk)
        assert sorted(r4) == rows and round(got_v4, 6) == v4 and round(got_vr, 6) == vr, (N, S, m)
        assert EC.value_of(F, r4, N, S, m) == pytest.approx(got_v4)


def test_r4_is_at_least_every_subset_and_m_is_bounded():
    F = _F()
    r4, v4, vr = EC.joint_coverage(F, 634, 119, 2)
    assert v4 >= vr and v4 >= EC.value_of(F, [0, 1], 634, 119, 2)
    with pytest.raises(ValueError):
        EC.joint_coverage(F, 634, 119, 0)
    with pytest.raises(ValueError):
        EC.joint_coverage(F, 634, 119, EC.MAX_M + 1)


def test_worlds_thin_the_two_banks_like_study_32():
    a = np.arange(2 * 40).reshape(2, 40).astype(float); b = a + 1000
    W = EC.worlds(a, b, w_sim=8)                                # 80 columns, every 10th -> columns 0, 10, ..., 70
    assert W.shape == (2, 8) and W[0, 0] == 0 and W[0, 4] == 1000 and W[0, 7] == 1030


def test_field_cdf_counts_the_field_a_row_beats():
    W = np.array([[1.0, 5.0], [2.0, 0.0], [3.0, 1.0]])          # 3 players x 2 worlds
    field = np.array([[0], [1], [2]])                          # three one-player "lineups"
    F = EC.field_cdf(W, field, [[2], [0]])
    assert F[0].tolist() == [2 / 3, 1 / 3] and F[1].tolist() == [0.0, 2 / 3]   # ties are not beaten


def test_seats_at_or_above_the_win_line():
    ladder = [{"minPosition": 1, "maxPosition": 1, "payoutDescriptions": [{"payoutDescriptionType": "Text", "value": 1000.0}]},
              {"minPosition": 2, "maxPosition": 10, "payoutDescriptions": [{"payoutDescriptionType": "Text", "value": 500.0}]},
              {"minPosition": 11, "maxPosition": 50, "payoutDescriptions": [{"payoutDescriptionType": "Text", "value": 40.0}]}]
    assert EC.seats_at_or_above(ladder, 500) == 10 and EC.seats_at_or_above(ladder, 501) == 1
    assert EC.seats_at_or_above(ladder, 5000) == 0 and EC.seats_at_or_above([], 500) == 0
