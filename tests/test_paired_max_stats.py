"""Paired weekly-max co-primary (N7): exact small-sample values,
determinism, threshold discordance, and fail-closed validation."""
import numpy as np
import pytest

from nfl_dfs.research.paired_max_stats import (
    _mcnemar_exact_p,
    _signed_rank_ranks,
    paired_weekly_max_report,
)


def test_exact_enumeration_matches_hand_computed_case():
    # diffs = [1, 2, 3]: 8 sign patterns; |sum| >= 6 for exactly {+++,---},
    # and |W+ - 3| >= 3 for exactly the same two patterns -> p = 0.25 both.
    control = np.array([100.0, 100.0, 100.0])
    treatment = np.array([101.0, 102.0, 103.0])
    report = paired_weekly_max_report(control, treatment)
    assert report["inference"]["method"] == "exact_enumeration"
    assert report["inference"]["p_mean_two_sided"] == pytest.approx(0.25)
    assert report["inference"]["p_signed_rank_two_sided"] == pytest.approx(0.25)
    assert report["mean_diff"] == pytest.approx(2.0)
    assert report["n_treatment_better"] == 3


def test_zero_differences_are_tied_not_evidence():
    control = np.array([180.0, 190.0, 170.0, 165.0])
    treatment = np.array([180.0, 190.0, 171.0, 165.0])
    report = paired_weekly_max_report(control, treatment)
    assert report["n_tied"] == 3
    assert report["inference"]["n_nonzero"] == 1
    # One nonzero difference: sign flip gives p = 1.0 two-sided.
    assert report["inference"]["p_mean_two_sided"] == pytest.approx(1.0)


def test_monte_carlo_path_is_deterministic():
    rng = np.random.default_rng(3)
    control = rng.normal(175, 12, size=40)
    treatment = control + rng.normal(1.5, 4, size=40)
    first = paired_weekly_max_report(control, treatment)
    second = paired_weekly_max_report(control, treatment)
    assert first == second
    assert first["inference"]["method"] == "monte_carlo"
    assert 0.0 < first["inference"]["p_mean_two_sided"] <= 1.0


def test_threshold_grid_counts_discordant_pairs():
    control = np.array([196.0, 180.0, 210.0, 150.0])
    treatment = np.array([190.0, 195.0, 211.0, 149.0])
    report = paired_weekly_max_report(control, treatment)
    row = {r["threshold"]: r for r in report["threshold_grid"]}[194]
    assert row["control"] == 2 and row["treatment"] == 2
    assert row["discordant_control_only"] == 1
    assert row["discordant_treatment_only"] == 1
    assert row["mcnemar_exact_p_two_sided"] == pytest.approx(1.0)
    row240 = {r["threshold"]: r for r in report["threshold_grid"]}[240]
    assert row240["mcnemar_exact_p_two_sided"] is None


def test_mcnemar_exact_binomial_values():
    # b=0, c=5: 2 * P(X <= 0 | n=5) = 2/32
    assert _mcnemar_exact_p(0, 5) == pytest.approx(2 / 32)
    assert _mcnemar_exact_p(0, 0) is None
    assert _mcnemar_exact_p(3, 3) == pytest.approx(1.0)


def test_tied_magnitudes_share_average_ranks():
    ranks = _signed_rank_ranks(np.array([2.0, -2.0, 5.0]))
    assert ranks[0] == pytest.approx(1.5)
    assert ranks[1] == pytest.approx(1.5)
    assert ranks[2] == pytest.approx(3.0)


def test_validation_fails_closed():
    with pytest.raises(ValueError):
        paired_weekly_max_report([1.0], [2.0])
    with pytest.raises(ValueError):
        paired_weekly_max_report([1.0, 2.0], [2.0])
    with pytest.raises(ValueError):
        paired_weekly_max_report([1.0, np.nan], [2.0, 3.0])
    with pytest.raises(ValueError):
        paired_weekly_max_report(
            [1.0, 2.0], [2.0, 3.0], slate_keys=["a", "a"])
