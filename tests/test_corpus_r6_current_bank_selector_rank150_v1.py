from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_v1 as rank150,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)


def _fixture(
    candidate_count: int = 156,
) -> tuple[list[str], np.ndarray, list[dict[str, object]], list[str], int]:
    worlds_per_block = 32
    blocks = ["R0", "R1", "R2", "R3"]
    lineup_ids = [f"lineup-{index:03d}" for index in range(candidate_count)]
    rng = np.random.default_rng(20_260_828)
    scores = np.ascontiguousarray(
        rng.normal(
            205.0,
            31.0,
            size=(candidate_count, len(blocks) * worlds_per_block),
        ),
        dtype=np.float64,
    )
    candidates: list[dict[str, object]] = []
    for index, lineup_id in enumerate(lineup_ids):
        counts = {
            block: 1 + ((index + ordinal) % 2)
            for ordinal, block in enumerate(blocks)
        }
        candidates.append({
            "lineup_id": lineup_id,
            "roster_player_ids": [
                f"p{index:03d}-{slot:02d}" for slot in range(9)
            ],
            "training_origin_blocks": list(blocks),
            "training_source_arms": ["incumbent"],
            "training_occurrence_counts_by_block": counts,
            "training_source_arms_by_block": {
                block: ["incumbent"] for block in blocks
            },
            "training_occurrence_count": sum(counts.values()),
        })
    return lineup_ids, scores, candidates, blocks, worlds_per_block


def _run(
    fixture: tuple[
        list[str], np.ndarray, list[dict[str, object]], list[str], int
    ] | None = None,
) -> dict[str, object]:
    lineup_ids, scores, candidates, blocks, worlds_per_block = (
        _fixture() if fixture is None else fixture
    )
    return rank150.run_exact_rank150_continuation_v1(
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
        preset_registry=successor.frozen_native_preset_registry_v1(),
    )


@pytest.fixture(scope="module")
def fixture_data(
) -> tuple[list[str], np.ndarray, list[dict[str, object]], list[str], int]:
    return _fixture()


@pytest.fixture(scope="module")
def result(
    fixture_data: tuple[
        list[str], np.ndarray, list[dict[str, object]], list[str], int
    ],
) -> dict[str, object]:
    return _run(fixture_data)


def test_rank150_has_exact_nested_80_100_150_books(
    result: dict[str, object],
) -> None:
    assert result["implementation_sha256"] == (
        rank150.EXPECTED_IMPLEMENTATION_SHA256
    )
    assert result["entry_budgets"] == [80, 100, 150]
    assert result["ranking_depth"] == 150
    assert result["exact_prefix_consistency_verified"] is True
    assert result["score_extrapolation_performed"] is False
    assert all(value is False for value in result["policy"].values())

    for selector in result["selectors"]:
        ranked = selector["ranked_lineup_ids"]
        assert len(ranked) == len(set(ranked)) == 150
        assert [row["prefix_size"] for row in selector["entry_books"]] == [
            80,
            100,
            150,
        ]
        for book in selector["entry_books"]:
            budget = book["prefix_size"]
            ids = book["selected_lineup_ids"]
            assert len(ids) == len(set(ids)) == budget
            assert ids == ranked[:budget]
        assert selector["entry_books"][0]["selected_lineup_ids"] == (
            selector["entry_books"][1]["selected_lineup_ids"][:80]
        )
        assert selector["entry_books"][1]["selected_lineup_ids"] == (
            selector["entry_books"][2]["selected_lineup_ids"][:100]
        )


def test_rank80_order_and_prefix_bytes_match_frozen_successor(
    fixture_data: tuple[
        list[str], np.ndarray, list[dict[str, object]], list[str], int
    ],
    result: dict[str, object],
) -> None:
    lineup_ids, scores, candidates, blocks, worlds_per_block = fixture_data
    legacy = successor.run_grouped_native_selectors_v1(
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
        preset_registry=successor.frozen_native_preset_registry_v1(),
    )
    legacy_by_preset = {
        row["preset_id"]: row for row in legacy["selectors"]
    }

    for continued in result["selectors"]:
        frozen = legacy_by_preset[continued["preset_id"]]
        exact_80 = next(
            row for row in frozen["prefixes"] if row["prefix_size"] == 80
        )
        assert continued["ranked_canonical_indices"][:80] == frozen[
            "selected_canonical_indices"
        ]
        assert continued["ranked_lineup_ids"][:80] == frozen[
            "selected_lineup_ids"
        ]
        assert successor._canonical(continued["entry_books"][0]) == (
            successor._canonical(exact_80)
        )

    scenario = next(
        row
        for row in result["selectors"]
        if row["adapter_id"]
        == "native-support-switched-scenario-ticket-v1"
    )
    assert scenario["continuation_diagnostics"]["support_gate"]["passed"] is True
    assert 0 < scenario["continuation_diagnostics"]["fallback_rank_start"] < 80


def test_rank150_replays_deterministically_and_rejects_tamper(
    fixture_data: tuple[
        list[str], np.ndarray, list[dict[str, object]], list[str], int
    ],
    result: dict[str, object],
) -> None:
    lineup_ids, scores, candidates, blocks, worlds_per_block = fixture_data
    registry = successor.frozen_native_preset_registry_v1()

    assert _run(fixture_data) == result
    assert rank150.validate_exact_rank150_continuation_v1(
        result,
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
        preset_registry=registry,
    ) == result

    tampered = deepcopy(result)
    tampered["selectors"][1]["entry_books"][1][
        "selected_lineup_ids"
    ][99] = "lineup-tampered"
    with pytest.raises(
        rank150.CorpusR6CurrentBankSelectorRank150V1Error,
        match="differs from exact pure replay",
    ):
        rank150.validate_exact_rank150_continuation_v1(
            tampered,
            sampled_lineup_ids=lineup_ids,
            training_score_matrix=scores,
            candidate_rows=candidates,
            training_blocks=blocks,
            worlds_per_block=worlds_per_block,
            preset_registry=registry,
        )


def test_rank150_rejects_any_infeasible_candidate_surface() -> None:
    fixture = _fixture(candidate_count=149)
    with pytest.raises(
        rank150.CorpusR6CurrentBankSelectorRank150V1Error,
        match="requires at least 150 sampled lineups",
    ):
        _run(fixture)
