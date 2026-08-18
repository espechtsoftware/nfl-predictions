"""Selector optimality-gap audit (A3): greedy vs exact CBC max coverage
on constructed instances with and without a real greedy gap."""
import numpy as np

from nfl_dfs.research.selector_optimality_gap import (
    exact_coverage_optimum,
    greedy_coverage,
    optimality_gap_report,
)


def _totals_from_sets(sets, n_worlds):
    """Binary coverage instance: candidate c scores 200 in its worlds."""
    totals = np.full((len(sets), n_worlds), 100.0)
    for c, worlds in enumerate(sets):
        totals[c, list(worlds)] = 200.0
    return totals


def test_classic_greedy_gap_instance():
    # A={0,1,2,3}, B={0,1,4}, C={2,3,5}; k=2. Greedy takes A (4 worlds)
    # then adds one more world (5 total); exact B+C covers all 6.
    totals = _totals_from_sets(
        [{0, 1, 2, 3}, {0, 1, 4}, {2, 3, 5}], 6)
    report = optimality_gap_report(totals, 2, 194.0)
    assert report["greedy"]["covered_worlds"] == 5
    assert report["exact"]["status"] == "Optimal"
    assert report["exact"]["covered_worlds"] == 6
    assert report["gap_worlds"] == 1
    assert report["gap_citable"] is True


def test_no_gap_instance():
    totals = _totals_from_sets([{0, 1}, {2, 3}, {1, 2}], 4)
    report = optimality_gap_report(totals, 2, 194.0)
    assert report["greedy"]["covered_worlds"] == 4
    assert report["exact"]["covered_worlds"] == 4
    assert report["gap_worlds"] == 0


def test_random_instances_never_show_negative_gap():
    rng = np.random.default_rng(4)
    for _ in range(3):
        totals = rng.normal(180, 20, size=(15, 60))
        report = optimality_gap_report(totals, 5, 194.0)
        assert report["exact"]["status"] == "Optimal"
        assert report["gap_worlds"] >= 0


def test_greedy_helper_matches_production_selector_shape():
    totals = _totals_from_sets([{0}, {1}, {0, 1}], 3)
    greedy = greedy_coverage(totals, 1, 194.0)
    assert greedy["covered_worlds"] == 2
    exact = exact_coverage_optimum(totals, 1, 194.0)
    assert exact["covered_worlds"] == 2
