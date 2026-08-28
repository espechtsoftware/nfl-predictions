from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_extreme_tail_preweek_additions as convex_source,
)
from nfl_dfs.research import (
    corpus_extreme_tail_roadmap_retrieval as roadmap_source,
)
from nfl_dfs.research import (
    corpus_extreme_tail_scenario_ticket as scenario_source,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)


EXPECTED_IMPLEMENTATION_SHA256 = (
    "f32c07afd2a75d56a119b23135e5e8f3300575158bf3be0d731bd4ea7ed0fef4"
)
EXPECTED_REGISTRY_SHA256 = (
    "c73065043d5381967957526074adfc046bf19f9208441f1552f6f9d2aaaf66b4"
)
EXPECTED_FIXTURE_RESULT_SHA256 = (
    "52b8f0bb2b7e382493e62be852ed94bd414ca6d828997063d35359d540d180c7"
)


def _fixture() -> tuple[
    list[str], np.ndarray, list[dict[str, object]], list[str], int
]:
    candidate_count = 84
    worlds_per_block = 32
    blocks = ["R0", "R1", "R2", "R3"]
    lineup_ids = [f"lineup-{index:03d}" for index in range(candidate_count)]
    rng = np.random.default_rng(20_260_828)
    scores = np.ascontiguousarray(
        rng.normal(
            205.0,
            30.0,
            size=(candidate_count, len(blocks) * worlds_per_block),
        ),
        dtype=np.float64,
    )
    candidates: list[dict[str, object]] = []
    for index, lineup_id in enumerate(lineup_ids):
        # Preserve varied but internally exact source provenance.  It is
        # descriptive input only; V1 has no independent-calibration adapter.
        counts = {
            block: (0 if index >= 82 and block != "R3" else 1)
            for block in blocks
        }
        arms_by_block = {
            block: ([] if count == 0 else ["incumbent"])
            for block, count in counts.items()
        }
        candidates.append({
            "lineup_id": lineup_id,
            "roster_player_ids": sorted(
                f"p{index:03d}-{slot:02d}" for slot in range(9)
            ),
            "training_origin_blocks": [
                block for block in blocks if counts[block] > 0
            ],
            "training_source_arms": ["incumbent"],
            "training_occurrence_counts_by_block": counts,
            "training_source_arms_by_block": arms_by_block,
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
    return successor.run_grouped_native_selectors_v1(
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
        preset_registry=successor.frozen_native_preset_registry_v1(),
    )


def _tie_fixture(
    *, candidate_count: int, heldout_block: str, worlds_per_block: int = 8
) -> tuple[list[str], np.ndarray, list[dict[str, object]], list[str], int]:
    blocks = [block for block in successor.WORLD_BLOCKS if block != heldout_block]
    lineup_ids = [f"lineup-{index:03d}" for index in range(candidate_count)]
    scores = np.full(
        (candidate_count, len(blocks) * worlds_per_block),
        200.0,
        dtype=np.float64,
        order="C",
    )
    candidates = []
    for index, lineup_id in enumerate(lineup_ids):
        counts = {block: 1 for block in blocks}
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
            "training_occurrence_count": len(blocks),
        })
    return lineup_ids, scores, candidates, blocks, worlds_per_block


@pytest.fixture(scope="module")
def grouped_result() -> dict[str, object]:
    return _run()


def test_frozen_registry_and_implementation_are_exact() -> None:
    implementation = successor.frozen_successor_implementation_v1()
    registry = successor.frozen_native_preset_registry_v1()

    assert implementation["implementation_id"] == successor.IMPLEMENTATION_ID
    assert implementation["implementation_sha256"] == EXPECTED_IMPLEMENTATION_SHA256
    assert successor._sha(registry) == EXPECTED_REGISTRY_SHA256
    assert [row["preset_id"] for row in registry] == [
        "convex-excess-expected-max-ge-200-v1",
        "correlation-aware-expected-max-ge-230-v1",
        "support-switched-event-component-tickets-ge-230-v1",
    ]
    assert implementation["deferred_adapters"] == [{
        "source_strategy_id": "tail-lcb-ge-230-v1",
        "reason": (
            "rank-only-view-and-equal-count-sample-authority-required-"
            "before-independent-calibration"
        ),
    }]


def test_grouped_result_is_exact_deterministic_and_outcome_blind(
    grouped_result: dict[str, object],
) -> None:
    replay = _run()

    assert grouped_result == replay
    assert grouped_result["result_sha256"] == EXPECTED_FIXTURE_RESULT_SHA256
    assert grouped_result["selector_count"] == 3
    assert grouped_result["entry_budget"] == 80
    assert grouped_result["prefix_sizes"] == [4, 14, 80]
    assert all(value is False for value in grouped_result["policy"].values())
    assert grouped_result["input_binding"]["caller_supplied_inputs_only"] is True
    assert grouped_result["input_binding"]["production_authority_validated"] is False

    for selector in grouped_result["selectors"]:
        selected = selector["selected_lineup_ids"]
        assert len(selected) == len(set(selected)) == 80
        assert [row["prefix_size"] for row in selector["prefixes"]] == [
            4, 14, 80
        ]
        for prefix in selector["prefixes"]:
            assert prefix["selected_lineup_ids"] == selected[
                : prefix["prefix_size"]
            ]


def test_three_unchanged_native_adapters_match_their_frozen_kernels(
    grouped_result: dict[str, object],
) -> None:
    lineup_ids, scores, _candidates, blocks, worlds_per_block = _fixture()
    shared = successor._build_shared_preprocessing_v1(
        scores=scores,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
    )
    source_rows = np.arange(len(lineup_ids), dtype=np.int64)

    convex_selected, _ = convex_source._select_convex_expected_max(
        scores=scores,
        canonical_source_rows=source_rows,
        lineup_ids=lineup_ids,
        means=shared.means,
        primary_counts=shared.strict_gt_200_counts,
    )
    correlation_selected, _ = (
        roadmap_source._select_correlation_aware_expected_max(
            scores=scores,
            canonical_source_rows=source_rows,
            packed_by_block=shared.packed_by_threshold[230.0],
            training_blocks=blocks,
            worlds_per_block=worlds_per_block,
            lineup_ids=lineup_ids,
            means=shared.means,
        )
    )
    scenario_receipt = scenario_source.build_scenario_ticket_selection_v1(
        lineup_ids=lineup_ids,
        fit_scores=scores,
        world_block_registry=successor.WORLD_BLOCKS,
        worlds_per_block=worlds_per_block,
        scope_kind="cross-fit",
        heldout_block="R4",
    )
    by_id = {
        selector["preset_id"]: selector for selector in grouped_result["selectors"]
    }

    assert by_id["convex-excess-expected-max-ge-200-v1"][
        "selected_canonical_indices"
    ] == convex_selected
    assert by_id["correlation-aware-expected-max-ge-230-v1"][
        "selected_canonical_indices"
    ] == correlation_selected
    assert by_id["support-switched-event-component-tickets-ge-230-v1"][
        "selected_canonical_indices"
    ] == scenario_receipt["selected_canonical_indices"]


def test_shared_preprocessing_runs_once_and_native_repackers_are_not_used(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    original_scores = fixture[1].copy()
    original_builder = successor._build_shared_preprocessing_v1
    calls = 0

    def counted_builder(**kwargs: object):
        nonlocal calls
        calls += 1
        assert kwargs["scores"] is fixture[1]
        return original_builder(**kwargs)

    def forbidden(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("native adapter rebuilt a shared >=230 mask")

    monkeypatch.setattr(successor, "_build_shared_preprocessing_v1", counted_builder)
    monkeypatch.setattr(roadmap_source, "_pack_ge230_by_block", forbidden)
    monkeypatch.setattr(scenario_source, "_pack_threshold", forbidden)

    result = _run(fixture)
    preprocessing = result["shared_preprocessing"]

    assert calls == 1
    assert preprocessing["no_persistent_full_float64_matrix_clone"] is True
    assert preprocessing["shared_preprocessing_build_count"] == 1
    assert preprocessing["full_fit_mean_pass_count"] == 1
    assert preprocessing["strict_gt_200_count_pass_count"] == 1
    assert preprocessing["block_partition_build_count"] == 1
    assert preprocessing["inclusive_mask_build_count_by_threshold"] == {
        "210": 1,
        "220": 1,
        "230": 1,
        "240": 1,
        "250": 1,
    }
    assert result["input_binding"]["input_score_matrix_object_reused"] is True
    assert result["input_binding"][
        "no_persistent_full_float64_matrix_clone"
    ] is True
    assert np.array_equal(fixture[1], original_scores)


def test_result_validator_replays_exactly_and_rejects_tamper(
    grouped_result: dict[str, object],
) -> None:
    lineup_ids, scores, candidates, blocks, worlds_per_block = _fixture()
    registry = successor.frozen_native_preset_registry_v1()

    assert successor.validate_grouped_native_selector_result_v1(
        grouped_result,
        sampled_lineup_ids=lineup_ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
        preset_registry=registry,
    ) == grouped_result

    tampered = deepcopy(grouped_result)
    tampered["selectors"][0]["selected_lineup_ids"][0] = "lineup-tampered"
    with pytest.raises(
        successor.CorpusR6CurrentBankSelectorSuccessorV1Error,
        match="differs from exact pure replay",
    ):
        successor.validate_grouped_native_selector_result_v1(
            tampered,
            sampled_lineup_ids=lineup_ids,
            training_score_matrix=scores,
            candidate_rows=candidates,
            training_blocks=blocks,
            worlds_per_block=worlds_per_block,
            preset_registry=registry,
        )


@pytest.mark.parametrize("heldout_block", successor.WORLD_BLOCKS)
def test_exact80_ties_are_deterministic_across_every_heldout_rotation(
    heldout_block: str,
) -> None:
    fixture = _tie_fixture(candidate_count=80, heldout_block=heldout_block)
    result = _run(fixture)
    expected_ids = fixture[0]

    assert result["input_binding"]["heldout_block_label_only"] == heldout_block
    assert all(
        selector["selected_lineup_ids"] == expected_ids
        for selector in result["selectors"]
    )
    assert result == _run(fixture)


def test_maximum_250_candidate_tie_boundary_and_support_fallback() -> None:
    fixture = _tie_fixture(candidate_count=250, heldout_block="R4")
    result = _run(fixture)
    expected_ids = fixture[0][:80]

    assert all(
        selector["selected_lineup_ids"] == expected_ids
        for selector in result["selectors"]
    )
    scenario = result["selectors"][2]
    assert scenario["compact_diagnostics"]["selection_mode"] == (
        "block-robust-fallback-support-failure"
    )


def test_strict_200_and_inclusive_230_threshold_boundaries() -> None:
    _ids, scores, _candidates, blocks, worlds_per_block = _tie_fixture(
        candidate_count=80, heldout_block="R4"
    )
    scores[0, 0] = 230.0
    shared = successor._build_shared_preprocessing_v1(
        scores=scores,
        training_blocks=blocks,
        worlds_per_block=worlds_per_block,
    )

    assert shared.strict_gt_200_counts[:2].tolist() == [1, 0]
    assert shared.inclusive_ge_230_counts[:2].tolist() == [1, 0]
    assert int(successor._POPCOUNT[
        shared.packed_by_threshold[230.0][0][0]
    ].sum()) == 1
    assert int(successor._POPCOUNT[
        shared.packed_by_threshold[240.0][0][0]
    ].sum()) == 0


def test_fails_closed_on_registry_or_candidate_provenance_drift() -> None:
    lineup_ids, scores, candidates, blocks, worlds_per_block = _fixture()
    registry = successor.frozen_native_preset_registry_v1()
    registry[0]["parameters"]["pivot"] = 199.0
    with pytest.raises(
        successor.CorpusR6CurrentBankSelectorSuccessorV1Error,
        match="preset registry differs",
    ):
        successor.run_grouped_native_selectors_v1(
            sampled_lineup_ids=lineup_ids,
            training_score_matrix=scores,
            candidate_rows=candidates,
            training_blocks=blocks,
            worlds_per_block=worlds_per_block,
            preset_registry=registry,
        )

    bad_candidates = deepcopy(candidates)
    bad_candidates[0]["training_occurrence_count"] = 999
    with pytest.raises(
        successor.CorpusR6CurrentBankSelectorSuccessorV1Error,
        match=r"candidate\[0\] identity/provenance differs",
    ):
        successor.run_grouped_native_selectors_v1(
            sampled_lineup_ids=lineup_ids,
            training_score_matrix=scores,
            candidate_rows=bad_candidates,
            training_blocks=blocks,
            worlds_per_block=worlds_per_block,
            preset_registry=successor.frozen_native_preset_registry_v1(),
        )


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda matrix: matrix.astype(np.float32), "C-contiguous float64"),
        (
            lambda matrix: np.ascontiguousarray(matrix[:, :-1]),
            "C-contiguous float64",
        ),
        (
            lambda matrix: np.where(
                np.arange(matrix.size).reshape(matrix.shape) == 0,
                np.nan,
                matrix,
            ),
            "non-finite",
        ),
    ],
)
def test_fails_closed_on_score_matrix_drift(
    mutation: object, message: str
) -> None:
    lineup_ids, scores, candidates, blocks, worlds_per_block = _fixture()
    bad = mutation(scores)
    with pytest.raises(
        successor.CorpusR6CurrentBankSelectorSuccessorV1Error,
        match=message,
    ):
        successor.run_grouped_native_selectors_v1(
            sampled_lineup_ids=lineup_ids,
            training_score_matrix=bad,
            candidate_rows=candidates,
            training_blocks=blocks,
            worlds_per_block=worlds_per_block,
            preset_registry=successor.frozen_native_preset_registry_v1(),
        )
