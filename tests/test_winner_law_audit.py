"""Winner-law audit (N1): block alignment, roster totals, percentile
placement, aggregation, and fail-closed validation."""
import numpy as np
import pytest

from nfl_dfs.analysis.winner_law_audit import (
    WinnerLawAuditError,
    align_world_blocks,
    audit_roster_under_law,
    winner_law_report,
    winner_roster_world_totals,
)


def _ids(n=12):
    return np.array([f"p{i}" for i in range(n)], dtype=str)


def test_align_reindexes_permuted_blocks_exactly():
    ids = _ids()
    rng = np.random.default_rng(7)
    draws_a = rng.normal(10, 3, size=(12, 50))
    perm = rng.permutation(12)
    # Block B carries the same universe in a different row order.
    draws_b = rng.normal(10, 3, size=(12, 40))
    aligned_ids, combined = align_world_blocks(
        [(ids, draws_a), (ids[perm], draws_b[perm][np.argsort(perm)][perm])])
    assert list(aligned_ids) == list(ids)
    assert combined.shape == (12, 90)
    np.testing.assert_array_equal(combined[:, :50], draws_a)
    # Row for p3 in the combined tail must equal block B's p3 row.
    b_ids = ids[perm]
    b_draws = draws_b[perm][np.argsort(perm)][perm]
    row_in_b = int(np.flatnonzero(b_ids == "p3")[0])
    np.testing.assert_array_equal(combined[3, 50:], b_draws[row_in_b])


def test_align_rejects_universe_mismatch():
    ids = _ids()
    other = ids.copy()
    other[0] = "intruder"
    with pytest.raises(WinnerLawAuditError):
        align_world_blocks([
            (ids, np.zeros((12, 10))), (other, np.zeros((12, 10)))])


def test_roster_totals_are_exact_sums():
    ids = _ids()
    draws = np.arange(12 * 5, dtype=float).reshape(12, 5)
    roster = [f"p{i}" for i in range(9)]
    totals = winner_roster_world_totals(roster, ids, draws)
    np.testing.assert_array_equal(totals, draws[:9].sum(axis=0))


def test_roster_totals_fail_closed():
    ids = _ids()
    draws = np.zeros((12, 5))
    with pytest.raises(WinnerLawAuditError):
        winner_roster_world_totals([f"p{i}" for i in range(8)], ids, draws)
    with pytest.raises(WinnerLawAuditError):
        winner_roster_world_totals(
            ["p0"] * 2 + [f"p{i}" for i in range(1, 8)], ids, draws)
    with pytest.raises(WinnerLawAuditError):
        winner_roster_world_totals(
            [f"p{i}" for i in range(8)] + ["ghost"], ids, draws)


def test_percentile_placement_is_mid_rank_exact():
    totals = np.concatenate([np.full(900, 100.0), np.full(100, 200.0)])
    audit = audit_roster_under_law(150.0, totals)
    assert audit["percentile_mid_rank"] == pytest.approx(0.9)
    assert audit["pr_sim_ge_realized"] == pytest.approx(0.1)
    at_mass = audit_roster_under_law(200.0, totals)
    assert at_mass["percentile_mid_rank"] == pytest.approx(0.95)
    beyond = audit_roster_under_law(500.0, totals)
    assert beyond["percentile_mid_rank"] == pytest.approx(1.0)
    assert beyond["pr_sim_ge_realized"] == pytest.approx(0.0)


def test_audit_rejects_thin_or_nonfinite_worlds():
    with pytest.raises(WinnerLawAuditError):
        audit_roster_under_law(100.0, np.ones(50))
    bad = np.ones(200)
    bad[3] = np.nan
    with pytest.raises(WinnerLawAuditError):
        audit_roster_under_law(100.0, bad)


def _entry(season, week, percentile, n=1000):
    totals = np.linspace(100.0, 250.0, n)
    realized = float(np.quantile(totals, percentile))
    return {
        "season": season, "week": week,
        "roster_ids": [f"p{i}" for i in range(9)],
        "realized_snapshot_total": realized,
        "audit": audit_roster_under_law(realized, totals),
    }


def test_report_aggregates_exceedance_and_seasons():
    entries = [
        _entry(2023, 1, 0.90), _entry(2023, 2, 0.995),
        _entry(2024, 1, 0.9995), _entry(2025, 3, 0.50),
    ]
    report = winner_law_report(entries)
    assert report["n_winners"] == 4
    assert report["exceedance"]["at_or_beyond_p99"]["observed"] == 2
    assert report["exceedance"]["at_or_beyond_p999"]["observed"] == 1
    assert report["by_season"]["2023"]["n"] == 2
    assert report["uses_realized_outcomes"] is True
    assert report["gate_decision"] is None


def test_report_rejects_duplicate_slates():
    entries = [_entry(2023, 1, 0.5), _entry(2023, 1, 0.6)]
    with pytest.raises(WinnerLawAuditError):
        winner_law_report(entries)
