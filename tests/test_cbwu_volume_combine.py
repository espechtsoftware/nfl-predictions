"""Offline tests for the volume-OI admission combine (B1 shadow core)."""
import numpy as np
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference.multiseed_portfolio import (
    combine_cbwu_order_invariant_books,
    combine_cbwu_volume_books,
)
from nfl_dfs.optimizer.lineup import Lineup

from tests.test_multiseed_portfolio import _books, _player


def _volume_books(k=8, worlds=20):
    books = dict(_books(worlds=worlds))
    player_ids = books["R0"].player_ids
    player_rows = books["R0"].player_rows
    id_to_row = {pid: i for i, pid in enumerate(player_ids)}
    for seed_index in range(5, k):
        rng = np.random.default_rng(900 + seed_index)
        draws = rng.normal(20, 5, size=(len(player_ids), worlds)).astype(
            np.float32)
        candidates = []
        for candidate_index in range(10):
            start = (candidate_index + 3 * seed_index) % len(player_ids)
            ids = [player_ids[(start + o) % len(player_ids)]
                   for o in range(9)]
            lineup = Lineup(
                [player_rows[id_to_row[p]] for p in ids], tag="lev")
            if lineup.ids not in {c.ids for c in candidates}:
                candidates.append(lineup)
        totals = np.stack([
            draws[[id_to_row[p] for p in lineup.ids]].sum(axis=0)
            for lineup in candidates
        ]).astype(np.float32)
        books[f"R{seed_index}"] = CandidateBatch(
            candidates=tuple(candidates),
            candidate_totals=totals,
            player_ids=player_ids,
            player_rows=player_rows,
            row_draws=draws,
            all_tags={c.ids: ("lev",) for c in candidates},
        )
    return books


def test_volume_keeps_r0_budget_and_canonical_world_blocks():
    books = _volume_books(k=8)
    combined = combine_cbwu_volume_books(
        books, tuple(books), expected_worlds_per_book=20)
    assert len(combined.candidates) == len(books["R0"].candidates)
    # Worlds stay the five canonical blocks even with eight books.
    assert combined.candidate_totals.shape[1] == 100
    assert combined.metadata["candidate_books"] == 8
    assert combined.metadata["world_blocks"] == 5
    assert combined.metadata["complete_union_candidates"] > len(
        books["R0"].candidates)
    for tags in combined.all_tags.values():
        assert "candidate_admission:cbwu-volume-v1" in tags


def test_volume_is_order_invariant():
    books = _volume_books(k=7)
    forward = combine_cbwu_volume_books(
        books, tuple(sorted(books)), expected_worlds_per_book=20)
    backward = combine_cbwu_volume_books(
        books, tuple(reversed(sorted(books))), expected_worlds_per_book=20)
    assert [c.ids for c in forward.candidates] == \
        [c.ids for c in backward.candidates]
    assert np.array_equal(forward.candidate_totals, backward.candidate_totals)


def test_volume_at_five_books_matches_oi_admission():
    books = _volume_books(k=5)
    volume = combine_cbwu_volume_books(
        books, tuple(books), expected_worlds_per_book=20)
    oi = combine_cbwu_order_invariant_books(
        books, tuple(books), expected_worlds_per_book=20)
    assert {c.ids for c in volume.candidates} == \
        {c.ids for c in oi.candidates}


def test_volume_fails_closed_on_bad_contracts():
    books = _volume_books(k=6)
    with pytest.raises(ValueError, match="contiguous registered"):
        combine_cbwu_volume_books(
            {k: v for k, v in books.items() if k != "R3"},
            tuple(k for k in books if k != "R3"),
            expected_worlds_per_book=20)
    with pytest.raises(ValueError, match="at least five"):
        combine_cbwu_volume_books(
            {k: books[k] for k in ("R0", "R1", "R2", "R3")},
            ("R0", "R1", "R2", "R3"), expected_worlds_per_book=20)
