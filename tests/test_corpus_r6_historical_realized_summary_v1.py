from __future__ import annotations

import inspect
from collections import Counter
from copy import deepcopy
from dataclasses import dataclass, replace
from hashlib import sha256
from pathlib import Path

import pytest

from nfl_dfs.research import corpus_r6_historical_neo4j_slice_v1 as historical
from nfl_dfs.research import corpus_r6_historical_realized_summary_v1 as subject


@dataclass(frozen=True)
class _Fixture:
    binding: subject._Binding
    receipt_raw: bytes
    funnel_raw: bytes
    funnel: dict[str, object]
    roots: dict[str, object]
    receipt: dict[str, object]
    plan: historical.HistoricalNeo4jGraphPlanV1


def _identity(uri: str, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _threshold(
    *,
    population: int = 0,
    selected: int = 0,
) -> dict[str, object]:
    return {
        "threshold_dk": 200,
        "population_lineup_count": population,
        "population_available": population > 0,
        "eligible_lineup_count": population,
        "eligible_hit": population > 0,
        "selected_lineup_count": selected,
        "selected_hit": selected > 0,
    }


def _fixture() -> _Fixture:
    strategy_ids = ("strategy-a", "strategy-b")
    arm_ids = ("arm-a", "arm-b")
    block_ids = ("B0", "B1")
    reconciliation = {
        "source_slate_count": 2,
        "candidate_count": 4,
        "visit_occurrence_count": 9,
        "player_slate_count": 0,
        "scope_membership_count": 0,
        "book_count": 4,
        "selection_count": 4,
        "final_fit_book_count": 4,
        "final_fit_selection_count": 4,
        "high_score_lineup_count": 2,
        "selected_high_score_lineup_count": 1,
        "missed_high_score_lineup_count": 1,
        "opportunity_slate_count": 1,
        "converted_slate_count": 1,
        "candidate_attribution_roster_equality": True,
        "exact_nine_player_catalog_join": True,
        "candidate_lineage_recurrence_reconciled": True,
        "full_population_denominators_retained": True,
    }

    funnel_body: dict[str, object] = {
        "slate_rows": [
            {
                "source_ordinal": 0,
                "corpus": {
                    "corpus_maximum_score_micro": 210_000_000,
                    "thresholds": [_threshold(population=2)],
                },
                "diagnostic_union": {
                    "thresholds": [_threshold(population=2, selected=1)]
                },
                "exact_80_books": [
                    {
                        "strategy_ordinal": ordinal,
                        "strategy_id": strategy_id,
                        "selected_maximum_score_micro": 205_000_000,
                        "selector_regret_micro": 5_000_000,
                        "thresholds": [_threshold(population=2, selected=1)],
                    }
                    for ordinal, strategy_id in enumerate(strategy_ids)
                ],
            },
            {
                "source_ordinal": 1,
                "corpus": {
                    "corpus_maximum_score_micro": 190_000_000,
                    "thresholds": [_threshold()],
                },
                "diagnostic_union": {"thresholds": [_threshold()]},
                "exact_80_books": [
                    {
                        "strategy_ordinal": 0,
                        "strategy_id": strategy_ids[0],
                        "selected_maximum_score_micro": 180_000_000,
                        "selector_regret_micro": 10_000_000,
                        "thresholds": [_threshold()],
                    },
                    {
                        "strategy_ordinal": 1,
                        "strategy_id": strategy_ids[1],
                        "selected_maximum_score_micro": 190_000_000,
                        "selector_regret_micro": 0,
                        "thresholds": [_threshold()],
                    },
                ],
            },
        ],
        "population_result": {
            "thresholds": [
                {
                    "threshold_dk": 200,
                    "population_lineup_count": 2,
                    "population_opportunity_slates": 1,
                }
            ]
        },
        "diagnostic_union_result": {
            "thresholds": [
                {
                    "threshold_dk": 200,
                    "selected_qualifying_lineup_count": 1,
                    "observed_hit_slates": 1,
                }
            ]
        },
        "exact_80_strategy_results": [
            {
                "strategy_ordinal": ordinal,
                "strategy_id": strategy_id,
                "strategy_sha256": character * 64,
                "source_slate_count": 2,
                "entry_count_k": 80,
                "thresholds": [
                    {
                        "threshold_dk": 200,
                        "observed_hit_slates": 1,
                        "population_opportunity_slates": 1,
                        "selected_qualifying_lineup_count": 1,
                    }
                ],
            }
            for ordinal, (strategy_id, character) in enumerate(
                zip(strategy_ids, ("a", "b"), strict=True)
            )
        ],
    }
    funnel_internal = subject.canonical_sha256(funnel_body)
    funnel_body["funnel_release_sha256"] = funnel_internal
    funnel_raw = subject.canonical_json_bytes(funnel_body)
    funnel_identity = _identity("fixture://funnel", funnel_raw)
    roots = {
        "candidate_v2": _identity("fixture://candidate", b"{}"),
        "catalog_outer": _identity("fixture://catalog", b"{}"),
        "no_rescore_funnel": funnel_identity,
    }

    nodes: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []
    slate_nodes: list[dict[str, object]] = []
    for ordinal, high_count in enumerate((2, 0)):
        row = historical._node(
            "Slate",
            f"slate-{ordinal}",
            {"source_ordinal": ordinal, "high_score_lineup_count": high_count},
        )
        slate_nodes.append(row)
        nodes.append(row)
    lineup_a = historical._node(
        "LineupCandidate",
        "lineup-a",
        {
            "source_ordinal": 0,
            "realized_score_micro": 205_000_000,
            "selected_final_book_count": 2,
        },
    )
    lineup_b = historical._node(
        "LineupCandidate",
        "lineup-b",
        {
            "source_ordinal": 0,
            "realized_score_micro": 210_000_000,
            "selected_final_book_count": 0,
        },
    )
    nodes.extend((lineup_a, lineup_b))

    books: dict[tuple[int, int], dict[str, object]] = {}
    selected_values = ((205_000_000, 205_000_000), (180_000_000, 190_000_000))
    eligible_values = (210_000_000, 190_000_000)
    for slate_ordinal in range(2):
        for strategy_ordinal, strategy_id in enumerate(strategy_ids):
            selected = selected_values[slate_ordinal][strategy_ordinal]
            eligible = eligible_values[slate_ordinal]
            threshold = _threshold(
                population=2 if slate_ordinal == 0 else 0,
                selected=1 if slate_ordinal == 0 else 0,
            )
            row = historical._node(
                "FinalFitBook",
                f"book-{slate_ordinal}-{strategy_ordinal}",
                {
                    "source_ordinal": slate_ordinal,
                    "strategy_ordinal": strategy_ordinal,
                    "strategy_id": strategy_id,
                    "eligible_maximum_score_micro": eligible,
                    "selected_maximum_score_micro": selected,
                    "selector_regret_micro": eligible - selected,
                    "threshold_capture": [threshold],
                },
            )
            books[(slate_ordinal, strategy_ordinal)] = row
            nodes.append(row)
    for strategy_ordinal in range(2):
        book = books[(0, strategy_ordinal)]
        relationships.extend(
            (
                historical._relationship(
                    book["id"],
                    lineup_a["id"],
                    "SELECTED_HIGH_SCORER",
                    {"selection_rank": 0, "realized_score_micro": 205_000_000},
                ),
                historical._relationship(
                    book["id"],
                    lineup_b["id"],
                    "MISSED_HIGH_SCORER",
                    {"reason": "not-selected-by-final-fit-book"},
                ),
            )
        )

    cell_values = {
        0: {
            ("arm-a", "B0"): (1, 2, 1, 2),
            ("arm-a", "B1"): (1, 1, 1, 1),
            ("arm-b", "B0"): (1, 1, 1, 1),
            ("arm-b", "B1"): (1, 1, 1, 1),
        },
        1: {(arm, block): (1, 1, 0, 0) for arm in arm_ids for block in block_ids},
    }
    denominator_nodes: dict[tuple[int, str, str, str], dict[str, object]] = {}
    for slate_ordinal in range(2):
        cells = cell_values[slate_ordinal]
        for kind, value, block in (
            [("arm", arm, "") for arm in arm_ids]
            + [("block", block, "") for block in block_ids]
            + [("arm-block", arm, block) for arm in arm_ids for block in block_ids]
        ):
            if kind == "arm-block":
                candidate_count, visits, high_count, high_visits = cells[(value, block)]
            elif kind == "arm":
                selected_cells = [cells[(value, item)] for item in block_ids]
                candidate_count = 1
                visits = sum(item[1] for item in selected_cells)
                high_count = max(item[2] for item in selected_cells)
                high_visits = sum(item[3] for item in selected_cells)
            else:
                selected_cells = [cells[(item, value)] for item in arm_ids]
                candidate_count = 2
                visits = sum(item[1] for item in selected_cells)
                high_count = sum(item[2] for item in selected_cells)
                high_visits = sum(item[3] for item in selected_cells)
            row = historical._node(
                "GenerationDenominator",
                f"denominator-{slate_ordinal}-{kind}-{value}-{block}",
                {
                    "source_ordinal": slate_ordinal,
                    "dimension_kind": kind,
                    "dimension_value": value,
                    "block_id": block or None,
                    "candidate_count": candidate_count,
                    "visit_count": visits,
                    "high_score_candidate_count": high_count,
                    "high_score_visit_count": high_visits,
                    "full_population_candidate_count": 2,
                },
            )
            denominator_nodes[(slate_ordinal, kind, value, block)] = row
            nodes.append(row)
    for lineup, arm, block, visits in (
        (lineup_a, "arm-a", "B0", 2),
        (lineup_a, "arm-a", "B1", 1),
        (lineup_b, "arm-b", "B0", 1),
        (lineup_b, "arm-b", "B1", 1),
    ):
        relationships.append(
            historical._relationship(
                lineup["id"],
                denominator_nodes[(0, "arm-block", arm, block)]["id"],
                "GENERATED_IN_CELL",
                {"visit_occurrence_count": visits},
            )
        )

    ordered_nodes = tuple(
        sorted(nodes, key=lambda row: (str(row["kind"]), str(row["logical_id"])))
    )
    ordered_relationships = tuple(
        sorted(
            relationships,
            key=lambda row: (
                str(row["from_id"]),
                str(row["to_id"]),
                str(row["relationship_type"]),
            ),
        )
    )
    source_manifest: list[object] = []
    row_digest_manifest: dict[str, object] = {}
    manifest: dict[str, object] = {
        "schema_version": historical.MANIFEST_SCHEMA,
        "source_root_identities": roots,
        "source_object_count": 0,
        "source_object_manifest": source_manifest,
        "source_object_manifest_sha256": subject.canonical_sha256(source_manifest),
        "source_row_digest_manifest": row_digest_manifest,
        "source_row_digest_manifest_sha256": subject.canonical_sha256(
            row_digest_manifest
        ),
        "reconciliation": reconciliation,
        "node_count": len(ordered_nodes),
        "node_rows_sha256": subject.canonical_sha256(list(ordered_nodes)),
        "relationship_count": len(ordered_relationships),
        "relationship_rows_sha256": subject.canonical_sha256(
            list(ordered_relationships)
        ),
        "persisted_realized_labels_only": True,
        "raw_outcome_query_performed": False,
        "lineup_rescore_performed": False,
        "winner_nodes_included": False,
        "official_claims_included": False,
        "neo4j_mutation_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "policy_feedback_authority": False,
        "complete": True,
    }
    manifest["manifest_sha256"] = subject.canonical_sha256(manifest)
    plan_body = {
        "schema_version": historical.PLAN_SCHEMA,
        "manifest": manifest,
        "nodes": list(ordered_nodes),
        "relationships": list(ordered_relationships),
    }
    plan = historical.HistoricalNeo4jGraphPlanV1(
        schema_version=historical.PLAN_SCHEMA,
        manifest=manifest,
        nodes=ordered_nodes,
        relationships=ordered_relationships,
        plan_sha256=subject.canonical_sha256(plan_body),
    )

    receipt: dict[str, object] = {
        "schema_version": "corpus-r6-historical-neo4j-slice-local-receipt/v1",
        "evidence_class": historical.EVIDENCE_CLASS,
        "threshold_dk": 200,
        "source_root_identities": roots,
        "source_object_count": 0,
        "source_object_manifest_sha256": manifest["source_object_manifest_sha256"],
        "source_row_digest_manifest_sha256": manifest[
            "source_row_digest_manifest_sha256"
        ],
        "reconciliation": reconciliation,
        "node_count": len(ordered_nodes),
        "node_kinds": dict(
            sorted(Counter(row["kind"] for row in ordered_nodes).items())
        ),
        "node_rows_sha256": manifest["node_rows_sha256"],
        "relationship_count": len(ordered_relationships),
        "relationship_types": dict(
            sorted(
                Counter(
                    row["relationship_type"] for row in ordered_relationships
                ).items()
            )
        ),
        "relationship_rows_sha256": manifest["relationship_rows_sha256"],
        "manifest_sha256": manifest["manifest_sha256"],
        "plan_sha256": plan.plan_sha256,
        "raw_outcome_query_performed": False,
        "lineup_rescore_performed": False,
        "winner_nodes_included": False,
        "official_claims_included": False,
        "world_matrix_bodies_included": False,
        "neo4j_mutation_performed": False,
        "network_access_performed": False,
        "promotion_authority": False,
        "decision_authority": False,
        "policy_feedback_authority": False,
        "complete": True,
    }
    receipt["receipt_sha256"] = subject.canonical_sha256(receipt)
    receipt_raw = subject.canonical_json_bytes(receipt) + b"\n"
    binding = subject._Binding(
        receipt_file_sha256=sha256(receipt_raw).hexdigest(),
        receipt_sha256=str(receipt["receipt_sha256"]),
        plan_sha256=plan.plan_sha256,
        manifest_sha256=str(manifest["manifest_sha256"]),
        funnel_internal_sha256=funnel_internal,
        funnel_identity=funnel_identity,
        source_object_count=0,
        source_object_manifest_sha256=str(manifest["source_object_manifest_sha256"]),
        source_row_digest_manifest_sha256=str(
            manifest["source_row_digest_manifest_sha256"]
        ),
        node_rows_sha256=str(manifest["node_rows_sha256"]),
        relationship_rows_sha256=str(manifest["relationship_rows_sha256"]),
        threshold_dk=200,
        slate_count=2,
        strategy_ids=strategy_ids,
        arm_ids=arm_ids,
        block_ids=block_ids,
        expected_reconciliation=reconciliation,
    )
    return _Fixture(
        binding=binding,
        receipt_raw=receipt_raw,
        funnel_raw=funnel_raw,
        funnel=funnel_body,
        roots=roots,
        receipt=receipt,
        plan=plan,
    )


def _build(fixture: _Fixture, monkeypatch: pytest.MonkeyPatch) -> dict[str, object]:
    monkeypatch.setattr(
        subject.funnel_contract,
        "validate_no_rescore_funnel_release_v1",
        lambda value: value,
    )
    return subject._build_historical_realized_summary_v1(
        accepted_e0_receipt_raw=fixture.receipt_raw,
        no_rescore_funnel_raw=fixture.funnel_raw,
        e0_plan=fixture.plan,
        binding=fixture.binding,
    )


def test_summary_is_exact_aggregate_and_deterministic(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    first = _build(fixture, monkeypatch)
    second = _build(fixture, monkeypatch)
    assert first == second
    funnel = first["outcome_funnel_summary"]
    assert funnel["eligible_high_score_lineup_count"] == 2
    assert funnel["observed_in_any_final_fit_book_count"] == 1
    assert funnel["first_observed_absence_count"] == 1
    assert funnel["selected_high_scorer_book_edge_count"] == 2
    assert funnel["book_classification_edge_count"] == 4
    assert funnel["first_observed_absence_class"] == (
        "FIRST_OBSERVED_ABSENCE_AT_FINAL_BOOK"
    )
    first_strategy = first["strategy_rescue_summary"][0]
    assert first_strategy["eligible_maximum_score_sum_micro"] == 400_000_000
    assert first_strategy["selected_maximum_score_sum_micro"] == 385_000_000
    assert first_strategy["sum_individual_rescue_deltas_micro"] == 15_000_000
    assert first_strategy["positive_rescue_slate_count"] == 2
    assert first_strategy["eligible_maximum_score_mean_micro"] == {
        "numerator": 400_000_000,
        "denominator": 2,
    }
    generation = first["generation_yield_summary"]
    assert generation["total_visit_count"] == 9
    assert generation["total_high_score_visit_count"] == 5
    arm_a_b0 = generation["by_fill_arm_world_block"][0]
    assert arm_a_b0["candidate_membership_count"] == 2
    assert arm_a_b0["visit_count"] == 3
    assert arm_a_b0["high_score_candidate_membership_count"] == 1
    assert arm_a_b0["high_score_visit_count"] == 2
    assert first["summary_sha256"] == subject.canonical_sha256(
        {key: value for key, value in first.items() if key != "summary_sha256"}
    )


@pytest.mark.parametrize("mutation", ["missing-lf", "extra-lf", "funnel-byte"])
def test_exact_receipt_and_funnel_bytes_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    fixture = _fixture()
    monkeypatch.setattr(
        subject.funnel_contract,
        "validate_no_rescore_funnel_release_v1",
        lambda value: value,
    )
    receipt_raw = fixture.receipt_raw
    funnel_raw = fixture.funnel_raw
    if mutation == "missing-lf":
        receipt_raw = receipt_raw[:-1]
    elif mutation == "extra-lf":
        receipt_raw += b"\n"
    else:
        funnel_raw += b" "
    with pytest.raises(subject.CorpusR6HistoricalRealizedSummaryV1Error):
        subject._build_historical_realized_summary_v1(
            accepted_e0_receipt_raw=receipt_raw,
            no_rescore_funnel_raw=funnel_raw,
            e0_plan=fixture.plan,
            binding=fixture.binding,
        )


def test_mutated_plan_fails_recomputed_plan_binding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    monkeypatch.setattr(
        subject.funnel_contract,
        "validate_no_rescore_funnel_release_v1",
        lambda value: value,
    )
    mutated = replace(fixture.plan, nodes=fixture.plan.nodes[:-1])
    with pytest.raises(
        subject.CorpusR6HistoricalRealizedSummaryV1Error,
        match="receipt/plan binding",
    ):
        subject._build_historical_realized_summary_v1(
            accepted_e0_receipt_raw=fixture.receipt_raw,
            no_rescore_funnel_raw=fixture.funnel_raw,
            e0_plan=mutated,
            binding=fixture.binding,
        )


def test_duplicate_book_lineup_classification_fails() -> None:
    fixture = _fixture()
    nodes = {row["id"]: row for row in fixture.plan.nodes}
    lineup_a = next(
        row for row in fixture.plan.nodes if row["logical_id"] == "lineup-a"
    )
    lineup_b = next(
        row for row in fixture.plan.nodes if row["logical_id"] == "lineup-b"
    )
    book_one = next(
        row
        for row in fixture.plan.nodes
        if row["kind"] == "FinalFitBook"
        and subject._properties(row, label="book")["strategy_ordinal"] == 1
        and subject._properties(row, label="book")["source_ordinal"] == 0
    )
    replacement_edge = historical._relationship(
        book_one["id"],
        lineup_a["id"],
        "MISSED_HIGH_SCORER",
        {"reason": "not-selected-by-final-fit-book"},
    )
    relationships = tuple(
        replacement_edge
        if row["relationship_type"] == "MISSED_HIGH_SCORER"
        and row["from_id"] == book_one["id"]
        and row["to_id"] == lineup_b["id"]
        else row
        for row in fixture.plan.relationships
    )
    assert book_one["id"] in nodes
    with pytest.raises(
        subject.CorpusR6HistoricalRealizedSummaryV1Error,
        match="classification repeats",
    ):
        subject._aggregate_bound_plan(
            plan=replace(fixture.plan, relationships=relationships),
            funnel=fixture.funnel,
            receipt=fixture.receipt,
            roots=fixture.roots,
            binding=fixture.binding,
        )


def test_generated_cell_must_target_arm_block_denominator() -> None:
    fixture = _fixture()
    generated = next(
        row
        for row in fixture.plan.relationships
        if row["relationship_type"] == "GENERATED_IN_CELL"
    )
    arm_node = next(
        row
        for row in fixture.plan.nodes
        if row["kind"] == "GenerationDenominator"
        and subject._properties(row, label="denominator")["dimension_kind"] == "arm"
    )
    properties = subject._properties(generated, label="generated")
    replacement_edge = historical._relationship(
        generated["from_id"], arm_node["id"], "GENERATED_IN_CELL", properties
    )
    relationships = tuple(
        replacement_edge if row["edge_key"] == generated["edge_key"] else row
        for row in fixture.plan.relationships
    )
    with pytest.raises(
        subject.CorpusR6HistoricalRealizedSummaryV1Error,
        match="edge target differs",
    ):
        subject._aggregate_bound_plan(
            plan=replace(fixture.plan, relationships=relationships),
            funnel=fixture.funnel,
            receipt=fixture.receipt,
            roots=fixture.roots,
            binding=fixture.binding,
        )


def test_generated_cell_cannot_cross_slates() -> None:
    fixture = _fixture()
    generated = next(
        row
        for row in fixture.plan.relationships
        if row["relationship_type"] == "GENERATED_IN_CELL"
    )
    original_target = next(
        row for row in fixture.plan.nodes if row["id"] == generated["to_id"]
    )
    original_properties = subject._properties(original_target, label="denominator")
    cross_slate_target = next(
        row
        for row in fixture.plan.nodes
        if row["kind"] == "GenerationDenominator"
        and subject._properties(row, label="denominator")["source_ordinal"] == 1
        and subject._properties(row, label="denominator")["dimension_kind"]
        == "arm-block"
        and subject._properties(row, label="denominator")["dimension_value"]
        == original_properties["dimension_value"]
        and subject._properties(row, label="denominator")["block_id"]
        == original_properties["block_id"]
    )
    properties = subject._properties(generated, label="generated")
    replacement_edge = historical._relationship(
        generated["from_id"],
        cross_slate_target["id"],
        "GENERATED_IN_CELL",
        properties,
    )
    relationships = tuple(
        replacement_edge if row["edge_key"] == generated["edge_key"] else row
        for row in fixture.plan.relationships
    )
    with pytest.raises(
        subject.CorpusR6HistoricalRealizedSummaryV1Error,
        match="edge crosses slates",
    ):
        subject._aggregate_bound_plan(
            plan=replace(fixture.plan, relationships=relationships),
            funnel=fixture.funnel,
            receipt=fixture.receipt,
            roots=fixture.roots,
            binding=fixture.binding,
        )


def test_generation_denominator_requires_exact_per_slate_grid() -> None:
    fixture = _fixture()
    target = next(
        row
        for row in fixture.plan.nodes
        if row["kind"] == "GenerationDenominator"
        and subject._properties(row, label="denominator")["source_ordinal"] == 1
        and subject._properties(row, label="denominator")["dimension_kind"] == "arm"
    )
    properties = subject._properties(target, label="denominator")
    properties["source_ordinal"] = 0
    replacement = historical._node(
        str(target["kind"]), str(target["logical_id"]), properties
    )
    nodes = tuple(
        replacement if row["id"] == target["id"] else row for row in fixture.plan.nodes
    )
    with pytest.raises(
        subject.CorpusR6HistoricalRealizedSummaryV1Error,
        match="denominator slate coordinate differs",
    ):
        subject._aggregate_bound_plan(
            plan=replace(fixture.plan, nodes=nodes),
            funnel=fixture.funnel,
            receipt=fixture.receipt,
            roots=fixture.roots,
            binding=fixture.binding,
        )


def test_funnel_strategy_result_census_is_exact() -> None:
    fixture = _fixture()
    funnel = deepcopy(fixture.funnel)
    funnel["exact_80_strategy_results"].append(
        deepcopy(funnel["exact_80_strategy_results"][0])
    )
    with pytest.raises(
        subject.CorpusR6HistoricalRealizedSummaryV1Error,
        match="strategy-result census differs",
    ):
        subject._aggregate_bound_plan(
            plan=fixture.plan,
            funnel=funnel,
            receipt=fixture.receipt,
            roots=fixture.roots,
            binding=fixture.binding,
        )


@pytest.mark.parametrize("mutation", ["float", "forbidden", "unknown", "ratio"])
def test_positive_output_schema_rejects_rehashed_mutations(
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    fixture = _fixture()
    summary = deepcopy(_build(fixture, monkeypatch))
    if mutation == "float":
        summary["generation_yield_summary"]["total_visit_count"] = 9.0
    elif mutation == "forbidden":
        summary["outcome_funnel_summary"]["lineup_id"] = "forbidden"
    elif mutation == "unknown":
        summary["source_binding"]["unreviewed"] = True
    else:
        summary["strategy_rescue_summary"][0]["selected_maximum_score_mean_micro"][
            "numerator"
        ] += 1
    summary["summary_sha256"] = subject.canonical_sha256(
        {key: value for key, value in summary.items() if key != "summary_sha256"}
    )
    with pytest.raises(subject.CorpusR6HistoricalRealizedSummaryV1Error):
        subject._validate_historical_realized_summary_v1(
            summary, binding=fixture.binding
        )


def test_public_surface_is_fixed_and_module_is_service_isolated() -> None:
    signature = inspect.signature(subject.build_historical_realized_summary_v1)
    assert set(signature.parameters) == {
        "accepted_e0_receipt_raw",
        "no_rescore_funnel_raw",
        "e0_plan",
    }
    source = Path(subject.__file__).read_text()
    for forbidden in (
        "corpus_graph_vnext_contracts",
        "google.cloud",
        "import neo4j",
        "requests.",
        "nfl_dfs.scoring",
        "FastAPI",
        "APIRouter",
    ):
        assert forbidden not in source
