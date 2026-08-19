"""Offline tests for the field-max null calibration (N1d)."""
from __future__ import annotations

import math

import numpy as np
import pytest

from nfl_dfs.analysis.field_max_null import (
    FieldMaxNullError,
    combine_block_nulls,
    field_max_null_report,
    implied_field_size,
    null_field_max_percentiles,
    subsample_field_null,
)


def _totals(seed: int = 7, n_cand: int = 5, n_worlds: int = 240
            ) -> np.ndarray:
    rng = np.random.default_rng(seed)
    return rng.normal(150.0, 20.0, size=(n_cand, n_worlds))


def test_combine_pools_contests_across_differing_blocks():
    first = null_field_max_percentiles(_totals(seed=1, n_cand=4))
    second = null_field_max_percentiles(_totals(seed=2, n_cand=7))
    pooled = combine_block_nulls([first, second])
    assert pooled["block_candidates"] == [4, 7]
    assert pooled["n_worlds"] == first["n_worlds"] + second["n_worlds"]
    assert len(pooled["percentiles"]) == pooled["n_worlds"]
    assert np.array_equal(
        pooled["percentiles"][: first["n_worlds"]], first["percentiles"])
    with pytest.raises(FieldMaxNullError, match="block null result"):
        combine_block_nulls([{"percentiles": np.ones(3)}])


def test_null_percentiles_match_brute_force():
    totals = _totals()
    null = null_field_max_percentiles(totals)
    n_worlds = totals.shape[1]
    for world in range(0, n_worlds, 17):
        winner = int(np.argmax(totals[:, world]))
        value = totals[winner, world]
        row = totals[winner]
        less = int((row < value).sum())
        equal_excl = int((row == value).sum()) - 1
        expected = (less + 0.5 * equal_excl) / (n_worlds - 1)
        assert null["percentiles"][world] == pytest.approx(expected)
        expected_ge = ((row >= value).sum() - 1) / (n_worlds - 1)
        assert null["pr_ge"][world] == pytest.approx(expected_ge)


def test_strict_row_maximum_has_pr_ge_zero():
    totals = _totals()
    winner = int(np.argmax(totals[:, 0]))
    totals[winner, 0] = totals.max() + 100.0
    null = null_field_max_percentiles(totals)
    assert null["pr_ge"][0] == 0.0
    assert null["percentiles"][0] == 1.0


def test_subsample_is_seed_deterministic_and_bounded():
    totals = _totals(n_cand=8)
    a = subsample_field_null(totals, 3, seed=11, reps=4)
    b = subsample_field_null(totals, 3, seed=11, reps=4)
    assert np.array_equal(a, b)
    assert len(a) == 4 * totals.shape[1]
    assert (a >= 0.0).all() and (a <= 1.0).all()
    with pytest.raises(FieldMaxNullError, match="outside"):
        subsample_field_null(totals, 9, seed=11, reps=1)


def test_implied_field_size_inverts_the_exceedance_relation():
    n = 1000.0
    p = 1.0 - 0.999 ** n
    assert implied_field_size(p) == pytest.approx(n, rel=1e-9)
    assert implied_field_size(0.0) is None
    assert implied_field_size(1.0) is None


def _slate(p999: float, n_candidates: int = 64) -> dict:
    return {
        "season": 2023, "week": 1,
        "n_candidates": n_candidates, "n_worlds": 50_000,
        "p_beyond": {0.95: 0.9, 0.99: 0.5, 0.999: p999},
        "p_zero": 0.1,
        "subsample": {},
    }


def test_report_verdict_selection_effect_explains():
    per_slate = [_slate(0.9) for _ in range(4)]
    report = field_max_null_report(
        per_slate, {0.95: 4, 0.99: 4, 0.999: 3}, 4, ())
    assert report["verdict"] == "selection_effect_explains_n1_at_pool_size"
    tail = report["exceedance"]["p999"]["null_prob_count_ge_observed"]
    brute = sum(
        math.comb(4, k) * 0.9 ** k * 0.1 ** (4 - k) for k in (3, 4))
    assert tail == pytest.approx(brute)


def test_report_verdict_nondiagnostic_within_plausible_field():
    frac = 1.0 - 0.999 ** 64
    per_slate = [_slate(frac, n_candidates=64) for _ in range(4)]
    report = field_max_null_report(
        per_slate, {0.95: 4, 0.99: 4, 0.999: 3}, 4, ())
    assert report["verdict"] == "n1_nondiagnostic_within_plausible_field"
    assert report["required_raw_field_size"] == pytest.approx(
        math.log(0.25) / math.log(0.999), rel=1e-6)


def test_report_verdict_missing_mass_when_field_cannot_explain():
    frac = 1.0 - 0.999 ** 64
    per_slate = [_slate(frac, n_candidates=1_000_000) for _ in range(4)]
    report = field_max_null_report(
        per_slate, {0.95: 4, 0.99: 4, 0.999: 3}, 4, ())
    assert report["verdict"] == "missing_mass_confirmed_at_winner_scale"
    assert report["uses_realized_outcomes"] is False
    assert report["gate_decision"] is None
    with pytest.raises(FieldMaxNullError, match="winner count"):
        field_max_null_report(
            per_slate, {0.95: 4, 0.99: 4, 0.999: 3}, 5, ())
