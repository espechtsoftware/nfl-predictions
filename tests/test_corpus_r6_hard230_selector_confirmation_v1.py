from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as bridge
from nfl_dfs.research import corpus_r6_hard230_selector_confirmation_v1 as confirmation
from nfl_dfs.research import corpus_r6_current_bank_selector_successor_v1 as successor


def _lineups(prefix: str) -> list[dict[str, object]]:
    return [
        {
            "lineup_id": f"{prefix}-{index:03d}",
            "roster_player_ids": [f"p-{index:03d}-{slot}" for slot in range(9)],
            "roster_sha256": f"{index + 1:064x}",
        }
        for index in range(150)
    ]


def _source_book(
    *, role: str, population_id: str, selector: str, budget: int,
    sampled: list[str],
) -> dict[str, object]:
    return {
        "coordinate": {
            "adapter_id": bridge.ADAPTER_ID,
            "metric_kind": "selected-book",
            "population_role": role,
            "population_id": population_id,
            "selector_family": "fixture-family",
            "selector_id": selector,
            "entry_budget": budget,
        },
        "selected_lineup_ids": sampled[:budget],
    }


def _fixture() -> tuple[dict[str, object], dict[str, np.ndarray]]:
    populations = []
    matrices = {}
    for pop_ordinal, spec in enumerate(bridge.POPULATION_SPECS):
        role, population_id, *_ = spec
        lineups = _lineups(f"l{pop_ordinal}")
        sampled = [str(row["lineup_id"]) for row in lineups]
        matrix = np.ascontiguousarray(
            np.arange(150 * 40, dtype=np.float64).reshape(150, 40)
            + pop_ordinal
        )
        matrices[role] = matrix
        books = [
            _source_book(
                role=role,
                population_id=population_id,
                selector=f"base-{selector}",
                budget=budget,
                sampled=sampled,
            )
            for selector in range(4)
            for budget in confirmation.ENTRY_BUDGETS
        ]
        populations.append({
            "population_role": role,
            "population_id": population_id,
            "full_population_lineups": lineups,
            "sampled_lineup_ids": sampled,
            "selector_fit_score_shape": [150, 40],
            "selector_fit_score_matrix_sha256": successor._matrix_sha(matrix),
            "books": books,
        })
    return ({
        "source_ordinal": 0,
        "slate_id": "2023-w01",
        "slate_result_sha256": "a" * 64,
        "generator_origin_block": "R0",
        "selector_fit_blocks": ["R1", "R2", "R3", "R4"],
        "worlds_per_block": 10,
        "population_results": populations,
    }, matrices)


def _patch(monkeypatch: pytest.MonkeyPatch, slate: dict[str, object]) -> None:
    monkeypatch.setattr(
        confirmation.bridge,
        "validate_hard230_selector_slate_v1",
        lambda *_args, **_kwargs: slate,
    )


def test_confirmation_emits_exact_42_cell_lattice_without_regeneration(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slate, matrices = _fixture()
    _patch(monkeypatch, slate)
    result = confirmation.build_hard230_selector_confirmation_v1(
        bridge_slate=slate,
        bridge_replay_inputs={},
        training_score_matrices=matrices,
    )
    assert result["book_count"] == 42
    assert len(result["books"]) == 42
    assert result["selector_fit_blocks"] == ["R1", "R2", "R3", "R4"]
    assert result["generator_origin_block"] == "R0"
    assert result["corpus_regeneration_performed"] is False
    assert result["uses_realized_outcomes"] is False
    coordinates = [book["coordinate"] for book in result["books"]]
    assert {row["entry_budget"] for row in coordinates} == {80, 100, 150}
    assert len({
        (row["population_role"], row["selector_id"], row["entry_budget"])
        for row in coordinates
    }) == 42
    assert not any("cap-3" in row["selector_id"] for row in coordinates)


def test_confirmation_rejects_matrix_binding_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slate, matrices = _fixture()
    _patch(monkeypatch, slate)
    role = bridge.POPULATION_SPECS[0][0]
    matrices[role] = matrices[role].copy()
    matrices[role][0, 0] += 1.0
    with pytest.raises(
        confirmation.CorpusR6Hard230SelectorConfirmationV1Error,
        match="matrix binding",
    ):
        confirmation.build_hard230_selector_confirmation_v1(
            bridge_slate=slate,
            bridge_replay_inputs={},
            training_score_matrices=matrices,
        )


def test_confirmation_validation_replays_and_rejects_tamper(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slate, matrices = _fixture()
    _patch(monkeypatch, slate)
    inputs = {
        "bridge_slate": slate,
        "bridge_replay_inputs": {},
        "training_score_matrices": matrices,
    }
    result = confirmation.build_hard230_selector_confirmation_v1(**inputs)
    assert confirmation.validate_hard230_selector_confirmation_v1(
        result, **inputs
    ) == result
    tampered = deepcopy(result)
    tampered["books"][0]["selected_lineup_ids"][0] = "forged"
    with pytest.raises(
        confirmation.CorpusR6Hard230SelectorConfirmationV1Error,
        match="differs from exact replay",
    ):
        confirmation.validate_hard230_selector_confirmation_v1(
            tampered, **inputs
        )


def test_confirmation_completes_partial_hard_cap_after_exact_k100(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slate, matrices = _fixture()
    role = bridge.POPULATION_SPECS[0][0]
    population = slate["population_results"][0]
    by_id = {
        str(row["lineup_id"]): row
        for row in population["full_population_lineups"]
    }
    candidates = [by_id[value] for value in population["sampled_lineup_ids"]]
    original = confirmation.diversity._run_overlap_cap_order
    retained_prefix: list[int] = []

    def partial(*, gamma: int, **kwargs: object):
        selected, trace, summary = original(gamma=gamma, **kwargs)
        if gamma == 4:
            retained_prefix[:] = selected[:100]
            selected = selected[:100]
            trace = trace[:100]
            summary = {
                **summary,
                "greedy_prefix_count": 100,
                "ranking_depth_reached": False,
                "unselected_feasible_candidate_count_at_stop": 0,
            }
        return selected, trace, summary

    monkeypatch.setattr(
        confirmation.diversity, "_run_overlap_cap_order", partial
    )
    selectors, _contract_sha = confirmation._hard230_diversity_orders(
        scores=matrices[role], candidates=candidates
    )
    completed = selectors[0]
    prefix_ids = [
        candidates[index]["lineup_id"] for index in retained_prefix
    ]
    completion_ids = completed["ranked_lineup_ids"][100:]
    assert completed["strategy_id"] == confirmation.DIVERSITY_IDS[0]
    assert completed["greedy_prefix_count"] == 150
    assert completed["entry_budgets_available"] == [80, 100, 150]
    assert completed["ranked_canonical_indices"][:100] == retained_prefix
    assert len(set(completed["ranked_lineup_ids"])) == 150
    assert completed["selector_summary"] == {
        "overlap_cap": 4,
        "hard_cap_greedy_prefix_count": 100,
        "hard_cap_prefix_lineup_ids": prefix_ids,
        "hard_cap_prefix_lineup_ids_sha256": confirmation._hash(prefix_ids),
        "hard_cap_ranking_depth_reached": False,
        "hard_cap_unselected_feasible_candidate_count_at_stop": 0,
        "hard_cap_global_maximum_feasible_cardinality_claimed": False,
        "hard_cap_relaxed_within_prefix": False,
        "completion_law_id": confirmation.OVERLAP_COMPLETION_LAW_ID,
        "completion_performed": True,
        "completion_start_rank": 100,
        "completion_count": 50,
        "completion_lineup_ids": completion_ids,
        "completion_lineup_ids_sha256": confirmation._hash(completion_ids),
        "completion_overlap_cap_enforced": False,
        "completion_global_cap_compliance_claimed": False,
        "final_ranking_depth_reached": True,
    }


def test_confirmation_rejects_truncated_diversity_result_after_completion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slate, matrices = _fixture()
    _patch(monkeypatch, slate)

    original = confirmation._hard230_diversity_orders

    def partial(**kwargs):
        selectors, contract_sha = original(**kwargs)
        selectors[0]["ranked_lineup_ids"] = selectors[0]["ranked_lineup_ids"][:100]
        selectors[0]["entry_budgets_available"] = [80, 100]
        return selectors, contract_sha

    monkeypatch.setattr(
        confirmation, "_hard230_diversity_orders", partial
    )
    with pytest.raises(
        confirmation.CorpusR6Hard230SelectorConfirmationV1Error,
        match="lacks exact K150",
    ):
        confirmation.build_hard230_selector_confirmation_v1(
            bridge_slate=slate,
            bridge_replay_inputs={},
            training_score_matrices=matrices,
        )


def test_sealed_bridge_replay_matches_full_bridge_replay_byte_exactly(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slate, matrices = _fixture()
    _patch(monkeypatch, slate)
    monkeypatch.setattr(
        confirmation.bridge,
        "normalized_slate_for_grader_v1",
        lambda value: {"source_ordinal": value["source_ordinal"]},
    )
    full = confirmation.build_hard230_selector_confirmation_v1(
        bridge_slate=slate,
        bridge_replay_inputs={},
        training_score_matrices=matrices,
    )
    sealed = confirmation.build_from_sealed_hard230_bridge_v1(
        bridge_slate=slate,
        training_score_matrices=matrices,
    )
    assert confirmation._canonical(sealed) == confirmation._canonical(full)
