from __future__ import annotations

from copy import deepcopy

import numpy as np
import pytest

from nfl_dfs.research import corpus_extreme_tail_retrieval_suite as suite
from nfl_dfs.research import corpus_extreme_tail_scenario_ticket as tickets
from nfl_dfs.research import corpus_extreme_tail_support_switch as support_switch
from nfl_dfs.research.corpus_legal_feasibility import canonical_sha256


BLOCK_REGISTRY = ["R0", "R1", "R2", "R3", "R4"]
FIT_BLOCKS = BLOCK_REGISTRY[:-1]
WIDTH = 30


def _ids(prefix: str = "lineup", count: int = 80) -> list[str]:
    return [f"{prefix}-{index:03d}" for index in range(count)]


def _two_component_case() -> tuple[list[str], np.ndarray]:
    lineup_ids = [
        *[f"a-lineup-{index:03d}" for index in range(40)],
        *[f"b-lineup-{index:03d}" for index in range(40)],
    ]
    scores = np.full((80, len(FIT_BLOCKS) * WIDTH), 100.0, dtype=np.float64)
    component_a: list[int] = []
    component_b: list[int] = []
    for block in range(len(FIT_BLOCKS)):
        start = block * WIDTH
        a_width = 18 if block < 3 else 16
        component_a.extend(range(start, start + a_width))
        component_b.extend(range(start + a_width, start + WIDTH))
    for offset, worlds in ((0, component_a), (40, component_b)):
        anchor = worlds[0]
        for candidate in range(40):
            scores[offset + candidate, anchor] = 230.0
        for ordinal, world in enumerate(worlds[1:]):
            scores[offset + (ordinal % 40), world] = 230.0
    scores[0, scores[0] < 230.0] = 150.0
    return lineup_ids, np.ascontiguousarray(scores)


def _build(
    lineup_ids: list[str],
    scores: np.ndarray,
    *,
    world_block_registry: list[str] = BLOCK_REGISTRY,
    width: int = WIDTH,
    scope_kind: str = "cross-fit",
    heldout_block: str | None = "R4",
) -> dict[str, object]:
    return tickets.build_scenario_ticket_selection_v1(
        lineup_ids=lineup_ids,
        fit_scores=scores,
        world_block_registry=world_block_registry,
        worlds_per_block=width,
        scope_kind=scope_kind,
        heldout_block=heldout_block,
    )


def _rehash(value: dict[str, object]) -> None:
    value["scenario_ticket_sha256"] = canonical_sha256({
        key: item
        for key, item in value.items()
        if key != "scenario_ticket_sha256"
    })


def test_contract_literal_freezes_inputs_fallback_and_false_authority() -> None:
    contract = tickets.frozen_scenario_ticket_contract_v1()
    assert contract["strategy_id"] == (
        "support-switched-event-component-tickets-ge-230-v1"
    )
    assert contract["entry_budgets"] == [4, 14, 80]
    assert contract["ranking_depth"] == 80
    assert contract["world_block_registry"] == BLOCK_REGISTRY
    assert contract["event_law"] == {
        "threshold": 230.0,
        "operator": ">=",
        "world_identity": ["fit-block-ordinal", "zero-based-world-column"],
        "retained_world_law": "at-least-one-eligible-candidate-event",
        "retained_candidate_law": "at-least-one-retained-world-event",
    }
    assert contract["fallback"]["strategy_sha256"] == (
        tickets.FALLBACK_STRATEGY_SHA256
    )
    assert "held-out-scores" in contract["forbidden_inputs"]
    assert contract["uses_realized_outcomes"] is False
    assert contract["promotion_authority"] is False


def test_disjoint_components_use_breadth_then_exact_dhondt() -> None:
    lineup_ids, scores = _two_component_case()
    result = _build(lineup_ids, scores)
    diagnostics = result["component_diagnostics"]
    assert diagnostics["component_count"] == 2
    assert diagnostics["one_giant_component"] is False
    assert diagnostics["opportunity_world_count"] == 120
    components = {
        row["opportunity_world_count"]: row
        for row in diagnostics["components"]
    }
    assert set(components) == {50, 70}
    assert all(row["distinct_fit_block_count"] == 4 for row in components.values())
    trace = result["selection_trace"]
    assert [row["allocation_phase"] for row in trace[:4]] == [
        "breadth",
        "breadth",
        "dhondt",
        "dhondt",
    ]
    assert [row["component_opportunity_world_count"] for row in trace[:4]] == [
        70,
        50,
        70,
        50,
    ]
    assert trace[2]["dhondt_quotient"] == {"numerator": 70, "denominator": 2}
    assert trace[3]["dhondt_quotient"] == {"numerator": 50, "denominator": 2}
    assert trace[0]["lineup_id"] == "a-lineup-000"
    assert result["fallback_rank_start"] is None
    assert result["selection_mode"] == "scenario-tickets"


def test_equal_component_quotients_use_canonical_component_key() -> None:
    lineup_ids = [
        *[f"left-{index:03d}" for index in range(40)],
        *[f"right-{index:03d}" for index in range(40)],
    ]
    scores = np.full((80, 120), 100.0, dtype=np.float64)
    left = [block * 30 + column for block in range(4) for column in range(15)]
    right = [block * 30 + column for block in range(4) for column in range(15, 30)]
    for offset, worlds in ((0, left), (40, right)):
        for candidate in range(40):
            scores[offset + candidate, worlds[0]] = 230.0
        for ordinal, world in enumerate(worlds[1:]):
            scores[offset + ordinal % 40, world] = 230.0
    result = _build(lineup_ids, np.ascontiguousarray(scores))
    trace = result["selection_trace"]
    component_keys = sorted({row["component_key"] for row in trace})
    assert trace[0]["component_key"] == component_keys[0]
    assert trace[1]["component_key"] == component_keys[1]
    assert trace[2]["component_key"] == component_keys[0]
    assert trace[2]["dhondt_quotient"] == {"numerator": 60, "denominator": 2}


def test_one_giant_component_is_reported_without_reclustering() -> None:
    lineup_ids = _ids("giant")
    scores = np.full((80, 120), 100.0, dtype=np.float64)
    scores[:, 0] = 230.0
    for world in range(1, 120):
        scores[(world - 1) % 80, world] = 230.0
    result = _build(lineup_ids, np.ascontiguousarray(scores))
    diagnostics = result["component_diagnostics"]
    assert diagnostics["component_count"] == 1
    assert diagnostics["one_giant_component"] is True
    assert diagnostics["largest_component_opportunity_share"] == {
        "numerator": 120,
        "denominator": 120,
    }
    assert {row["component_key"] for row in result["selection_trace"]} == {
        diagnostics["components"][0]["component_key"]
    }


def test_sparse_support_uses_complete_robust_fallback_verbatim() -> None:
    lineup_ids = _ids("sparse")
    scores = np.full((80, 120), 210.0, dtype=np.float64)
    for block in range(4):
        scores[block, block * WIDTH] = 230.0
    result = _build(lineup_ids, np.ascontiguousarray(scores))
    assert result["support_gate"]["passed"] is False
    assert result["support_gate"]["opportunity_world_count"] == 4
    assert result["fallback_rank_start"] == 0
    assert result["selection_mode"] == (
        "block-robust-fallback-support-failure"
    )
    assert all(
        row["selection_source"] == "block-robust-fallback"
        for row in result["selection_trace"]
    )
    assert result["selected_lineup_ids"] == result[
        "fallback_rank_considered_lineup_ids"
    ][:80]


def test_supported_components_exhaust_then_append_robust_relative_order() -> None:
    lineup_ids = _ids("exhaust", 90)
    scores = np.full((90, 120), 100.0, dtype=np.float64)
    scores[:5, 0] = 230.0
    for world in range(1, 120):
        scores[(world - 1) % 5, world] = 230.0
    result = _build(lineup_ids, np.ascontiguousarray(scores))
    assert result["support_gate"]["passed"] is True
    assert result["fallback_rank_start"] == 5
    assert result["selection_mode"] == (
        "scenario-tickets-with-block-robust-exhaustion-suffix"
    )
    assert len(result["fallback_rank_considered_lineup_ids"]) == 80
    scenario_ids = result["selected_lineup_ids"][:5]
    expected_suffix = [
        lineup_id
        for lineup_id in result["fallback_rank_considered_lineup_ids"]
        if lineup_id not in scenario_ids
    ][:75]
    assert result["selected_lineup_ids"][5:] == expected_suffix
    fallback_rows = result["selection_trace"][5:]
    assert max(row["source_fallback_rank"] for row in fallback_rows) <= 79


def test_rank_requires_canonical_order_replays_and_has_exact_prefix_books() -> None:
    lineup_ids, scores = _two_component_case()
    result = _build(lineup_ids, scores)
    reverse = list(reversed(range(80)))
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError,
        match="ascending canonical order",
    ):
        _build(
            [lineup_ids[index] for index in reverse],
            np.ascontiguousarray(scores[np.asarray(reverse, dtype=np.int64)]),
        )
    assert [book["entry_budget"] for book in result["books"]] == [4, 14, 80]
    for book in result["books"]:
        budget = book["entry_budget"]
        assert book["entry_count"] == budget
        assert book["selected_lineup_ids"] == result["selected_lineup_ids"][:budget]
        assert len(set(book["selected_lineup_ids"])) == budget
    assert tickets.validate_scenario_ticket_selection_v1(
        result,
        lineup_ids=lineup_ids,
        fit_scores=scores,
        world_block_registry=BLOCK_REGISTRY,
        worlds_per_block=WIDTH,
        scope_kind="cross-fit",
        heldout_block="R4",
    ) == result


def test_final_fit_exact_125_gate_boundary() -> None:
    lineup_ids = _ids("final")
    blocks = ["R0", "R1", "R2", "R3", "R4"]
    scores = np.full((80, 125), 230.0, dtype=np.float64)
    passed = _build(
        lineup_ids,
        np.ascontiguousarray(scores),
        world_block_registry=blocks,
        width=25,
        scope_kind="final-fit",
        heldout_block=None,
    )
    assert passed["support_gate"]["opportunity_world_count"] == 125
    assert passed["support_gate"]["passed"] is True
    below = scores.copy()
    below[:, 0] = 229.0
    failed = _build(
        lineup_ids,
        np.ascontiguousarray(below),
        world_block_registry=blocks,
        width=25,
        scope_kind="final-fit",
        heldout_block=None,
    )
    assert failed["support_gate"]["opportunity_world_count"] == 124
    assert failed["support_gate"]["passed"] is False


def test_scope_identity_derives_exact_fit_blocks_from_canonical_registry() -> None:
    lineup_ids, scores = _two_component_case()
    result = _build(lineup_ids, scores)
    assert result["heldout_block"] == "R4"
    assert result["input_binding"]["world_block_registry"] == BLOCK_REGISTRY
    assert result["input_binding"]["fit_block_ids"] == FIT_BLOCKS
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError,
        match="registry differs",
    ):
        _build(
            lineup_ids,
            scores,
            world_block_registry=["R1", "R0", "R2", "R3", "R4"],
        )
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError,
        match="requires one exact canonical heldout block",
    ):
        _build(lineup_ids, scores, heldout_block=None)
    final_scores = np.full((80, 5 * WIDTH), 230.0, dtype=np.float64)
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError,
        match="requires null heldout block",
    ):
        _build(
            lineup_ids,
            np.ascontiguousarray(final_scores),
            scope_kind="final-fit",
            heldout_block="R4",
        )


def test_nonfinite_shape_and_insufficient_candidate_inputs_fail_closed() -> None:
    lineup_ids, scores = _two_component_case()
    nonfinite = scores.copy()
    nonfinite[0, 0] = np.nan
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError, match="non-finite"
    ):
        _build(lineup_ids, np.ascontiguousarray(nonfinite))
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError, match="exact shape"
    ):
        _build(lineup_ids, np.ascontiguousarray(scores[:, :-1]))
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError, match="at least 80"
    ):
        _build(lineup_ids[:79], np.ascontiguousarray(scores[:79]))


def test_schema_authority_and_coherently_rehashed_receipt_drift_fail_replay() -> None:
    lineup_ids, scores = _two_component_case()
    result = _build(lineup_ids, scores)
    for mutation in ("schema", "authority", "extra"):
        changed = deepcopy(result)
        if mutation == "schema":
            changed["schema_version"] = "extreme-tail-scenario-ticket-selection/v2"
        elif mutation == "authority":
            changed["promotion_authority"] = True
        else:
            changed["post_result_selector_choice"] = "winner"
        _rehash(changed)
        with pytest.raises(
            tickets.CorpusExtremeTailScenarioTicketError,
            match="canonical replay differs",
        ):
            tickets.validate_scenario_ticket_selection_v1(
                changed,
                lineup_ids=lineup_ids,
                fit_scores=scores,
                world_block_registry=BLOCK_REGISTRY,
                worlds_per_block=WIDTH,
                scope_kind="cross-fit",
                heldout_block="R4",
            )


def test_coherent_neighboring_suite_constant_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lineup_ids, scores = _two_component_case()
    monkeypatch.setattr(suite, "RANKING_DEPTH", 81)
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError,
        match="suite constants differ",
    ):
        _build(lineup_ids, scores)


@pytest.mark.parametrize(
    ("field", "drifted"),
    [
        ("STRATEGY_ID", "support-switched-event-component-tickets-ge-230-v2"),
        ("IMPLEMENTATION_ID", "packed-exact-event-components-dhondt-v2"),
        ("CANONICAL_WORLD_BLOCKS", ("R0", "R1", "R2", "R3", "RX")),
        ("ENTRY_BUDGETS", (4, 15, 80)),
        ("RANKING_DEPTH", 81),
        ("EVENT_THRESHOLD", 230.01),
        ("EVENT_OPERATOR", ">"),
        ("FOLD_MINIMUM_OPPORTUNITY_WORLDS", 101),
        ("FINAL_MINIMUM_OPPORTUNITY_WORLDS", 126),
        ("FALLBACK_STRATEGY_ID", "changed-fallback"),
        ("FALLBACK_STRATEGY_SHA256", "1" * 64),
        ("FALLBACK_IMPLEMENTATION_SHA256", "2" * 64),
        ("LITERAL_COVERAGE_STRATEGY_ID", "changed-literal"),
        ("LITERAL_COVERAGE_STRATEGY_SHA256", "3" * 64),
        ("FALLBACK_RUNGS", ((210.0, ">=", 1),)),
    ],
)
def test_every_local_literal_drift_fails_before_selection(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    drifted: object,
) -> None:
    lineup_ids, scores = _two_component_case()
    monkeypatch.setattr(tickets, field, drifted)
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError,
        match="literal constants differ",
    ):
        _build(lineup_ids, scores)


def test_coherently_rehashed_fallback_registry_drift_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lineup_ids, scores = _two_component_case()
    registry = deepcopy(suite.frozen_extreme_tail_strategies_v1())
    registry[2]["description"] = "coherently changed fallback"
    registry[2]["strategy_sha256"] = canonical_sha256({
        key: value
        for key, value in registry[2].items()
        if key != "strategy_sha256"
    })
    monkeypatch.setattr(
        suite, "frozen_extreme_tail_strategies_v1", lambda: registry
    )
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError,
        match="fallback strategy differs",
    ):
        _build(lineup_ids, scores)


def test_coherently_changed_neighbor_support_policy_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    lineup_ids, scores = _two_component_case()
    changed_gate = support_switch._gate_law()
    changed_gate["fold_minimum_opportunity_world_count"] = 101
    monkeypatch.setattr(
        support_switch, "FOLD_MINIMUM_OPPORTUNITY_WORLDS", 101
    )
    monkeypatch.setattr(support_switch, "_gate_law", lambda: changed_gate)
    with pytest.raises(
        tickets.CorpusExtremeTailScenarioTicketError,
        match="neighboring support-switch policy differs",
    ):
        _build(lineup_ids, scores)
