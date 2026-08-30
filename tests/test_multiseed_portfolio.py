from dataclasses import replace

import numpy as np
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference.multiseed_portfolio import (
    _select_tail_entries_bitpacked,
    audit_cbwu_seed_orders,
    combine_archetype_shadow_books,
    combine_cbwu_books,
    combine_cbwu_order_invariant_books,
)
from nfl_dfs.optimizer.lineup import Lineup, select_from_support, select_tail_entries


SEEDS = ("R0", "R1", "R2", "R3", "R4")


def _player(player_id):
    return {
        "id": player_id,
        "name": str(player_id),
        "pos": "WR",
        "team": "T",
        "opp": "O",
        "game_id": "G",
        "salary": 5_000,
        "proj": 20.0,
    }


def _books(*, worlds=20, counts=(10, 10, 10, 10, 10)):
    player_ids = tuple(range(20))
    player_rows = tuple(_player(player_id) for player_id in player_ids)
    books = {}
    for seed_index, (name, count) in enumerate(zip(SEEDS, counts, strict=True)):
        rng = np.random.default_rng(900 + seed_index)
        draws = rng.normal(20, 5, size=(len(player_ids), worlds)).astype(np.float32)
        candidates = []
        # R0--R4 each begin at a different rotation.  Adjacent rotations
        # overlap, later ones provide enough novelty to exercise quota/fill.
        for candidate_index in range(count):
            start = (candidate_index + 2 * seed_index) % len(player_ids)
            ids = [
                player_ids[(start + offset) % len(player_ids)]
                for offset in range(9)
            ]
            candidates.append(Lineup([player_rows[player_id] for player_id in ids],
                                     tag="lev"))
        # Remove accidental exact-roster duplicates within a native book.
        unique = []
        seen = set()
        for lineup in candidates:
            if lineup.ids not in seen:
                seen.add(lineup.ids)
                unique.append(lineup)
        candidates = unique
        id_to_row = {player_id: index for index, player_id in enumerate(player_ids)}
        totals = np.stack([
            draws[[id_to_row[player_id] for player_id in lineup.ids]].sum(axis=0)
            for lineup in candidates
        ]).astype(np.float32)
        books[name] = CandidateBatch(
            candidates=tuple(candidates),
            candidate_totals=totals,
            player_ids=player_ids,
            player_rows=player_rows,
            row_draws=draws,
            all_tags={lineup.ids: ("lev",) for lineup in candidates},
        )
    return books


def test_cbwu_preserves_r0_budget_and_uses_five_equal_world_blocks():
    books = _books()
    combined = combine_cbwu_books(
        books, SEEDS, expected_worlds_per_book=20)
    assert len(combined.candidates) == len(books["R0"].candidates)
    assert combined.candidate_totals.shape == (
        len(books["R0"].candidates), 100)
    assert combined.row_draws.shape == (20, 100)
    assert combined.metadata["worlds_per_block"] == [20] * 5
    assert sum(combined.metadata["candidate_source_counts"].values()) == len(
        books["R0"].candidates)
    assert len(combined.metadata["candidate_source_blocks"]) == len(
        combined.candidates
    )
    assert {
        label: combined.metadata["candidate_source_blocks"].count(label)
        for label in SEEDS
    } == combined.metadata["candidate_source_counts"]
    assert all(
        f"candidate_seed:{source}" in combined.all_tags[lineup.ids]
        for lineup, source in zip(
            combined.candidates,
            combined.metadata["candidate_source_blocks"],
            strict=True,
        )
    )
    assert all(len(lineup.ids) == 9 for lineup in combined.candidates)
    assert len({lineup.ids for lineup in combined.candidates}) == len(
        combined.candidates)


def test_cbwu_carries_each_native_generation_receipt():
    books = _books()
    books = {
        name: replace(batch, metadata={
            "generation_allocation": {
                "leverage_requested": 40,
                "boom_requested": 160,
                "core_requested": 200,
            },
            "generation_timing_seconds": {
                "leverage": float(index + 1),
            },
        })
        for index, (name, batch) in enumerate(books.items())
    }
    combined = combine_cbwu_books(
        books, SEEDS, expected_worlds_per_book=20,
    )
    receipts = combined.metadata["native_generation_receipts"]
    assert set(receipts) == set(SEEDS)
    assert all(receipt["core_requested"] == 200
               for receipt in receipts.values())
    assert "timing_seconds" not in receipts["R4"]


def test_cbwu_score_blind_quota_and_fixed_fill_order():
    books = _books(counts=(10, 1, 10, 10, 10))
    combined = combine_cbwu_books(
        books, SEEDS, expected_worlds_per_book=20)
    counts = combined.metadata["candidate_source_counts"]
    assert sum(counts.values()) == len(books["R0"].candidates)
    assert counts["R1"] <= 1
    # R1's shortfall is filled one-at-a-time in fixed seed order.
    assert counts["R0"] >= counts["R2"]


def test_cbwu_selected_book_is_exact_and_cross_scored():
    combined = combine_cbwu_books(
        _books(), SEEDS, expected_worlds_per_book=20)
    clears = combined.candidate_totals >= 194.0
    picked = select_from_support(
        clears, clears.mean(axis=1), combined.candidate_totals.mean(axis=1), 8)
    assert len(picked) == 8
    assert len(set(picked)) == 8
    # Every destination block differs; native totals were not reused five times.
    blocks = np.split(combined.candidate_totals, 5, axis=1)
    assert any(not np.array_equal(blocks[0], block) for block in blocks[1:])


def test_cbwu_fails_closed_on_missing_or_misaligned_book():
    books = _books()
    missing = dict(books)
    missing.pop("R4")
    with pytest.raises(ValueError, match="seed books differ"):
        combine_cbwu_books(missing, SEEDS, expected_worlds_per_book=20)

    bad = dict(books)
    source = books["R4"]
    bad["R4"] = CandidateBatch(
        candidates=source.candidates,
        candidate_totals=source.candidate_totals,
        player_ids=source.player_ids[:-1] + (999,),
        player_rows=source.player_rows,
        row_draws=source.row_draws,
        all_tags=source.all_tags,
    )
    with pytest.raises(ValueError, match="player universe|universes differ"):
        combine_cbwu_books(bad, SEEDS, expected_worlds_per_book=20)


def test_cbwu_fails_closed_when_native_totals_do_not_reconstruct():
    books = _books()
    source = books["R2"]
    corrupted = source.candidate_totals.copy()
    corrupted[0, 0] += 0.5
    books["R2"] = CandidateBatch(
        candidates=source.candidates,
        candidate_totals=corrupted,
        player_ids=source.player_ids,
        player_rows=source.player_rows,
        row_draws=source.row_draws,
        all_tags=source.all_tags,
    )
    with pytest.raises(ValueError, match="do not reconstruct"):
        combine_cbwu_books(books, SEEDS, expected_worlds_per_book=20)


def test_cbwu_seed_order_audit_is_score_free_and_budget_fixed():
    books = _books(counts=(10, 9, 8, 10, 9))
    report = audit_cbwu_seed_orders(
        books,
        SEEDS,
        n_entries=8,
        tail_line=194.0,
        expected_worlds_per_book=20,
    )
    assert report["uses_realized_outcomes"] is False
    assert report["canonical_seed_order"] == list(SEEDS)
    assert len(report["rotations"]) == 5
    assert {row["candidate_budget"] for row in report["rotations"]} == {10}
    canonical = report["rotations"][0]
    assert canonical["candidate_identity_jaccard_vs_canonical"] == 1.0
    assert canonical["selected_identity_jaccard_vs_canonical"] == 1.0
    assert all(row["candidate_pair_coverage"] > 0 for row in report["rotations"])
    assert all(row["selected_world_coverage"] >= 0 for row in report["rotations"])


def test_cbwu_oi_is_exact_budget_score_free_and_order_invariant():
    books = _books(counts=(10, 9, 8, 10, 9))
    first = combine_cbwu_order_invariant_books(
        books, SEEDS, expected_worlds_per_book=20
    )
    rotated = combine_cbwu_order_invariant_books(
        dict(reversed(list(books.items()))),
        SEEDS[2:] + SEEDS[:2],
        expected_worlds_per_book=20,
    )
    assert first.metadata["portfolio"] == "CBWU_OI_V1"
    assert first.metadata["production_enabled"] is False
    assert first.metadata["uses_realized_outcomes"] is False
    assert len(first.candidates) == len(books["R0"].candidates)
    assert [lineup.ids for lineup in first.candidates] == [
        lineup.ids for lineup in rotated.candidates
    ]
    assert np.array_equal(first.candidate_totals, rotated.candidate_totals)
    assert np.array_equal(first.row_draws, rotated.row_draws)
    assert all(
        "candidate_admission:cbwu-oi-v1" in tags
        for tags in first.all_tags.values()
    )


def test_cbwu_oi_bitpacked_selector_exactly_matches_incumbent_law():
    rng = np.random.default_rng(810_215)
    totals = rng.normal(190.0, 22.0, size=(137, 1003)).astype(np.float32)
    # Force both coverage saturation and exact tie cells.
    totals[3] = totals[2]
    totals[5:8] = 120.0
    for count in (1, 3, 20, 80, 137):
        assert _select_tail_entries_bitpacked(totals, count, 194.0) == (
            select_tail_entries(
                totals, count, 194.0, env={"SELECT_LSE": "0"}
            )
        )


def test_cbwu_oi_fails_closed_without_r0_or_complete_union():
    books = _books(counts=(10, 1, 1, 1, 1))
    with pytest.raises(ValueError, match="exact registered seeds"):
        combine_cbwu_order_invariant_books(
            {name: book for name, book in books.items() if name != "R4"}
            | {"R5": books["R4"]},
            ("R0", "R1", "R2", "R3", "R5"),
            expected_worlds_per_book=20,
        )

    identical = {name: books["R0"] for name in SEEDS}
    # The repeated book has enough union rows for this fixture, so reducing R0
    # below the unique-union size proves the fixed-budget guard separately.
    source = books["R0"]
    too_large = CandidateBatch(
        candidates=source.candidates + source.candidates,
        candidate_totals=np.concatenate(
            [source.candidate_totals, source.candidate_totals], axis=0
        ),
        player_ids=source.player_ids,
        player_rows=source.player_rows,
        row_draws=source.row_draws,
        all_tags=source.all_tags,
    )
    identical["R0"] = too_large
    with pytest.raises(ValueError, match="duplicate rosters"):
        combine_cbwu_order_invariant_books(
            identical, SEEDS, expected_worlds_per_book=20
        )


def _stack_player(player_id):
    if player_id == 0:
        pos, team, opp = "QB", "T0", "O0"
    elif player_id == 1:
        pos, team, opp = "WR", "T0", "O0"
    elif player_id == 2:
        pos, team, opp = "TE", "T0", "O0"
    elif player_id == 3:
        pos, team, opp = "WR", "O0", "T0"
    else:
        pos, team, opp = "RB", f"T{player_id}", f"O{player_id}"
    return {
        "id": player_id,
        "name": str(player_id),
        "pos": pos,
        "team": team,
        "opp": opp,
        "game_id": "G0" if player_id <= 3 else f"G{player_id}",
        "salary": 5_000,
        "proj": 20.0,
    }


def _stack_books(*, worlds=40, candidates_per_book=15):
    player_ids = tuple(range(40))
    player_rows = tuple(_stack_player(player_id) for player_id in player_ids)
    books = {}
    for seed_index, name in enumerate(SEEDS):
        rng = np.random.default_rng(1900 + seed_index)
        draws = rng.normal(
            20 + seed_index / 10, 5, size=(len(player_ids), worlds)
        ).astype(np.float32)
        candidates = []
        for candidate_index in range(candidates_per_book):
            start = (candidate_index + 3 * seed_index) % 36
            ids = [0, 1, 2, 3] + [4 + (start + offset) % 36 for offset in range(5)]
            candidates.append(Lineup(
                [player_rows[player_id] for player_id in ids], tag="lev"
            ))
        id_to_row = {player_id: index for index, player_id in enumerate(player_ids)}
        totals = np.stack([
            draws[[id_to_row[player_id] for player_id in lineup.ids]].sum(axis=0)
            for lineup in candidates
        ]).astype(np.float32)
        books[name] = CandidateBatch(
            candidates=tuple(candidates),
            candidate_totals=totals,
            player_ids=player_ids,
            player_rows=player_rows,
            row_draws=draws,
            all_tags={lineup.ids: ("lev",) for lineup in candidates},
        )
    return books


def test_archetype_shadow_is_exact_budget_balanced_and_not_production():
    shadow = combine_archetype_shadow_books(
        _stack_books(), SEEDS, expected_worlds_per_book=40
    )
    assert len(shadow.candidates) == 15
    assert shadow.candidate_totals.shape == (15, 200)
    assert shadow.row_draws.shape == (40, 200)
    assert shadow.metadata["portfolio"] == "CBWU_ARCHETYPE_SHADOW"
    assert shadow.metadata["production_enabled"] is False
    assert shadow.metadata["candidate_source_counts"] == {
        "R0": 3,
        "R1": 3,
        "R2": 3,
        "R3": 3,
        "R4": 3,
    }
    receipt = shadow.metadata["allocation_receipt"]
    assert receipt["candidate_budget"] == 15
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["source_quota_relaxed"] is False
    assert all(
        any(tag.startswith("candidate_archetype:") for tag in tags)
        for tags in shadow.all_tags.values()
    )


def test_archetype_shadow_is_deterministic_and_leaves_cbwu_unchanged():
    books = _stack_books()
    control_before = combine_cbwu_books(
        books, SEEDS, expected_worlds_per_book=40
    )
    first = combine_archetype_shadow_books(
        books, SEEDS, expected_worlds_per_book=40
    )
    second = combine_archetype_shadow_books(
        dict(reversed(list(books.items()))),
        SEEDS,
        expected_worlds_per_book=40,
    )
    control_after = combine_cbwu_books(
        books, SEEDS, expected_worlds_per_book=40
    )
    assert [lineup.ids for lineup in first.candidates] == [
        lineup.ids for lineup in second.candidates
    ]
    assert np.array_equal(first.candidate_totals, second.candidate_totals)
    assert [lineup.ids for lineup in control_before.candidates] == [
        lineup.ids for lineup in control_after.candidates
    ]
    assert np.array_equal(
        control_before.candidate_totals, control_after.candidate_totals
    )
    assert len(
        {lineup.ids for lineup in first.candidates}
        & {lineup.ids for lineup in control_before.candidates}
    ) < len(first.candidates)


def test_archetype_shadow_fails_closed_on_invalid_structure_or_tail_line():
    books = _books()
    with pytest.raises(ValueError, match="one quarterback"):
        combine_archetype_shadow_books(
            books, SEEDS, expected_worlds_per_book=20
        )
    with pytest.raises(ValueError, match="finite"):
        combine_archetype_shadow_books(
            _stack_books(), SEEDS, tail_line=np.nan, expected_worlds_per_book=40
        )
