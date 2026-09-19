import importlib.util
from pathlib import Path

import numpy as np
import pytest

spec = importlib.util.spec_from_file_location('frontier', Path(__file__).with_name('2026-09-19-selection-loss-frontier.py'))
frontier = importlib.util.module_from_spec(spec)
spec.loader.exec_module(frontier)


def test_measures_cost_instead_of_vetoing_all_loss():
    # First check equal coverage, then introduce one extra covered world at cost0.25.
    t = np.array([[220, 219, 221, 221], [219, 220, 220, 221]], np.float32)
    r = frontier.proposals(t, [0], np.ones(2, bool))
    assert r['decisions'][0]['book'] == 'control'
    # Both rows clear three worlds, so there is no P220 gain.
    assert all(x['book'] == 'control' for x in r['decisions'])
    t[1] = [220, 220, 220, 220]
    r = frontier.proposals(t, [0], np.ones(2, bool))
    assert r['decisions'][0]['book'] == 'control'
    assert r['decisions'][1]['delta_emax'] == -.25
    assert r['decisions'][1]['delta_p220'] == .25


def test_every_exchange_matches_direct_full_book_recomputation():
    rng = np.random.default_rng(19)
    t = rng.integers(180, 250, (12, 20)).astype(np.float32)
    book = [4, 1, 7]
    r = frontier.proposals(t, book, np.ones(12, bool))
    baseline = t[book].max(axis=0)
    for row in r['evaluated_exchanges']:
        alt = book.copy()
        alt[row['position']] = row['incoming']
        score = t[alt].max(axis=0)
        assert row['delta_emax'] == pytest.approx(score.mean(dtype=np.float64) - baseline.mean(dtype=np.float64))
        assert row['delta_p220'] == pytest.approx((score >= 220).mean() - (baseline >= 220).mean())


def test_ineligible_candidates_cannot_enter_and_unaffected_ranks_stay_fixed():
    t = np.array([[219, 219], [218, 218], [300, 300], [220, 220]], np.float32)
    r = frontier.proposals(t, [0, 1], np.array([True, True, False, True]))
    assert 2 not in r['shortlist']
    for b in r['books'].values():
        assert 2 not in b and sum(x != y for x, y in zip(b, [0, 1])) <= 1


def test_invalid_control_and_nonfinite_worlds_refuse():
    with pytest.raises(AssertionError, match='admission'):
        frontier.proposals(np.ones((2, 3)), [0], np.array([False, True]))
    with pytest.raises(AssertionError):
        frontier.proposals(np.array([[np.nan], [220.]]), [0], np.ones(2, bool))


def test_equal_scores_choose_stable_candidate_and_position():
    t = np.array([[219, 219], [219, 219], [220, 220], [220, 220]], np.float32)
    r = frontier.proposals(t, [1, 0], np.ones(4, bool))
    assert all(d['incoming'] == 2 and d['position'] == 0 for d in r['decisions'])
