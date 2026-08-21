"""Known-answer and fail-closed tests for the research evidence graph."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path

import pytest

from nfl_dfs.research.evidence_knowledge_graph import (
    EvidenceGraph,
    EvidenceGraphError,
    arm_rule_matrix,
    baseline_compatibility,
    build_graph,
    canonical_json_bytes,
    effects_for_arm,
    full_soft_removal,
    load_graph,
    validate_graph_against_registry,
    write_graph,
)


ROOT = Path(__file__).resolve().parents[1]
REGISTRY = ROOT / "reports/evidence-graph/20260821-v1/bootstrap.json"


@pytest.fixture(scope="module")
def graph() -> EvidenceGraph:
    return build_graph(ROOT, REGISTRY)


def _registry_payload() -> dict[str, object]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _write_registry(tmp_path: Path, payload: dict[str, object]) -> Path:
    path = tmp_path / "bootstrap.json"
    path.write_bytes(canonical_json_bytes(payload))
    return path


def _rule_rows_by_id(graph: EvidenceGraph, arm_id: str) -> dict[str, dict[str, object]]:
    return {row["rule_id"]: row for row in arm_rule_matrix(graph, arm_id)}


def _replace_node_property(
    graph: EvidenceGraph,
    *,
    node_id: str,
    property_name: str,
    value: object,
) -> EvidenceGraph:
    nodes = deepcopy(graph.nodes)
    node = next(row for row in nodes if row["id"] == node_id)
    node["properties"][property_name] = value
    return replace(graph, nodes=nodes)


def test_bootstrap_builds_complete_one_edge_per_arm_rule(graph: EvidenceGraph):
    assert graph.graph_id == "graph:generated-corpus-tail-20260821-v1"

    arm_ids = {node["id"] for node in graph.nodes if node["kind"] == "arm"}
    rule_ids = {node["id"] for node in graph.nodes if node["kind"] == "rule"}
    applications = [
        edge for edge in graph.edges if edge["kind"] == "RULE_APPLICATION"
    ]

    assert arm_ids
    assert rule_ids
    assert len(applications) == len(arm_ids) * len(rule_ids)
    assert {
        (edge["from"], edge["to"]) for edge in applications
    } == {(arm_id, rule_id) for arm_id in arm_ids for rule_id in rule_ids}


def test_build_rejects_retained_source_sha_poison(tmp_path: Path):
    payload = _registry_payload()
    payload["artifacts"][0]["sha256"] = "0" * 64

    with pytest.raises(EvidenceGraphError, match="artifact SHA-256 differs"):
        build_graph(ROOT, _write_registry(tmp_path, payload))


def test_build_rejects_measurement_value_that_differs_from_source(tmp_path: Path):
    payload = _registry_payload()
    measurement = next(
        node for node in payload["nodes"] if node["id"] == "measurement:b1-s"
    )
    measurement["properties"]["delta"] = -999.0

    with pytest.raises(
        EvidenceGraphError,
        match=r"measurement:b1-s property differs from source: delta",
    ):
        build_graph(ROOT, _write_registry(tmp_path, payload))


@pytest.mark.parametrize(
    "poison",
    [1, False],
    ids=["outside-domain", "wrong-type"],
)
def test_build_rejects_parameter_value_outside_typed_domain(
    tmp_path: Path,
    poison: object,
):
    payload = _registry_payload()
    arm = next(
        row for row in payload["arms"] if row["id"] == "arm:allboom-generation"
    )
    change = next(
        row
        for row in arm["parameter_changes"]
        if row["parameter_id"] == "parameter:cand-mult"
    )
    change["treatment"] = poison

    with pytest.raises(EvidenceGraphError, match="outside its frozen domain"):
        build_graph(ROOT, _write_registry(tmp_path, payload))


def test_build_rejects_in_domain_parameter_value_that_differs_from_source(
    tmp_path: Path,
):
    payload = _registry_payload()
    arm = next(
        row for row in payload["arms"] if row["id"] == "arm:allboom-generation"
    )
    change = next(
        row
        for row in arm["parameter_changes"]
        if row["parameter_id"] == "parameter:cand-mult"
    )
    change["control"] = 0

    with pytest.raises(
        EvidenceGraphError,
        match=r"parameter control differs from source: parameter:cand-mult",
    ):
        build_graph(ROOT, _write_registry(tmp_path, payload))


def test_materialized_graph_rejects_missing_rule_application(
    graph: EvidenceGraph,
    tmp_path: Path,
):
    target = next(
        edge
        for edge in graph.edges
        if edge["kind"] == "RULE_APPLICATION"
        and edge["from"] == "arm:allboom-generation"
    )
    poisoned = replace(
        graph,
        edges=tuple(edge for edge in graph.edges if edge["id"] != target["id"]),
    )

    with pytest.raises(EvidenceGraphError, match=r"rule.*coverage|RULE_APPLICATION"):
        output = tmp_path / "missing-rule"
        write_graph(poisoned, output)
        load_graph(output)


def test_materialized_graph_rejects_duplicate_arm_rule_application(
    graph: EvidenceGraph,
    tmp_path: Path,
):
    duplicate = deepcopy(
        next(
            edge
            for edge in graph.edges
            if edge["kind"] == "RULE_APPLICATION"
            and edge["from"] == "arm:allboom-generation"
        )
    )
    duplicate["id"] = f"{duplicate['id']}:duplicate"
    poisoned = replace(graph, edges=(*graph.edges, duplicate))

    with pytest.raises(
        EvidenceGraphError,
        match=r"RULE_APPLICATION|rule.*(?:cardinality|duplicate)|canonical",
    ):
        output = tmp_path / "duplicate-rule"
        write_graph(poisoned, output)
        load_graph(output)


def test_materialized_manifest_and_arm_effects_disclaim_decision_authority(
    graph: EvidenceGraph,
    tmp_path: Path,
):
    output = tmp_path / "authority-boundary"
    manifest = write_graph(graph, output)
    retained_manifest = json.loads(
        (output / "manifest.json").read_text(encoding="utf-8")
    )

    assert retained_manifest == manifest
    assert retained_manifest["decision_authority"] is False
    assert retained_manifest["property_binding_scope"] == (
        "measurement_properties_and_parameter_assignments"
    )

    effects = effects_for_arm(graph, "arm:allboom-generation")
    assert effects["decision_authority"] is False
    assert effects["parameter_binding_status"] == "source_bound"
    assert effects["parameter_changes"]


def test_a2a_is_a_diagnostic_not_a_lineup_or_selector_arm(graph: EvidenceGraph):
    arm_id = "arm:a2a-dependence-remeasurement"
    rows = arm_rule_matrix(graph, arm_id)

    assert rows
    simulation = next(
        row for row in rows if row["rule_id"] == "rule:simulation-rank-factor-law"
    )
    assert simulation["application"] == "direct"
    assert simulation["effect"] == "replaced"
    assert simulation["scope"]["unit"] == "world_blocks"
    lineup_rows = [row for row in rows if row["stage"] != "simulation"]
    assert all(row["application"] == "not_applicable" for row in lineup_rows)
    assert all(row["effect"] == "nonoperative" for row in lineup_rows)
    assert not any(
        edge["kind"] == "USES_SELECTOR" and edge["from"] == arm_id
        for edge in graph.edges
    )


def test_a7_fixed_pool_replaces_the_production_simulation_law_upstream(
    graph: EvidenceGraph,
):
    rules = _rule_rows_by_id(graph, "arm:a7-selector-ladder")
    simulation = rules["rule:simulation-rank-factor-law"]

    assert simulation["classification"] == "simulation_law"
    assert simulation["stage"] == "simulation"
    assert simulation["application"] == "upstream_inherited"
    assert simulation["effect"] == "replaced"
    assert simulation["scope"] == {
        "candidate_path": "fixed_pool",
        "denominator": 1,
        "fraction": 1,
        "numerator": 1,
        "unit": "world_law",
    }


def test_b1_directly_replaces_line194_with_the_tail_model_selector(
    graph: EvidenceGraph,
):
    arm_id = "arm:b1-tail-model"
    rules = _rule_rows_by_id(graph, arm_id)

    line194 = rules["rule:selector-line194"]
    tail_model = rules["rule:selector-tail-model"]
    assert (line194["application"], line194["effect"]) == ("direct", "removed")
    assert (tail_model["application"], tail_model["effect"]) == (
        "direct",
        "added",
    )
    for row in (line194, tail_model):
        assert row["stage"] == "selection"
        assert row["scope"] == {
            "candidate_path": "selected_book",
            "denominator": 1,
            "fraction": 1,
            "numerator": 1,
            "unit": "books",
        }
    assert [
        edge["to"]
        for edge in graph.edges
        if edge["kind"] == "USES_SELECTOR" and edge["from"] == arm_id
    ] == ["rule:selector-tail-model"]


def test_allboom_retained_every_feasibility_rule(graph: EvidenceGraph):
    rules = _rule_rows_by_id(graph, "arm:allboom-generation")
    feasibility_rules = {
        "rule:salary-floor-49000",
        "rule:qb-stack-min-two",
        "rule:bring-back-min-one",
        "rule:forbid-rb-vs-dst",
        "rule:forbid-two-rb-same-team",
    }

    assert {rule_id: rules[rule_id]["effect"] for rule_id in feasibility_rules} == {
        rule_id: "retained" for rule_id in feasibility_rules
    }
    assert rules["rule:leverage-family"]["effect"] == "removed"
    assert rules["rule:candidate-budget-truncation"]["effect"] == "added"


def test_a3_relaxation_dose_and_equal_count_truncation_are_explicit(
    graph: EvidenceGraph,
):
    rules = _rule_rows_by_id(graph, "arm:a3-partial-stack-carve")

    for rule_id in ("rule:qb-stack-min-two", "rule:bring-back-min-one"):
        row = rules[rule_id]
        assert row["application"] == "direct"
        assert row["effect"] == "relaxed"
        assert row["scope"] == {
            "candidate_path": "boom",
            "denominator": 40,
            "fraction": 0.2,
            "numerator": 8,
            "unit": "solve_attempts_per_seed",
        }

    truncation = rules["rule:candidate-budget-truncation"]
    assert truncation["application"] == "direct"
    assert truncation["effect"] == "added"
    assert truncation["scope"] == {
        "candidate_path": "all",
        "denominator": 1,
        "fraction": 1,
        "numerator": 1,
        "unit": "candidate_paths",
    }
    for retained in (
        "rule:salary-floor-49000",
        "rule:forbid-rb-vs-dst",
        "rule:forbid-two-rb-same-team",
    ):
        assert rules[retained]["effect"] == "retained"


def test_exact_winner_and_b1_values_are_retained(graph: EvidenceGraph):
    nodes = graph.node_map()

    assert nodes["measurement:winner-production-valid"]["properties"] == {
        "denominator": 51,
        "numerator": 8,
        "value": 0.1568627450980392,
    }
    assert nodes["measurement:winner-p99"]["properties"] == {
        "denominator": 51,
        "numerator": 50,
        "value": 0.9803921568627451,
    }
    assert nodes["measurement:winner-qb-stack"]["properties"]["value"] == (
        1.2156862745098038
    )
    assert nodes["measurement:winner-games"]["properties"]["value"] == (
        5.666666666666667
    )

    assert nodes["measurement:b1-s"]["properties"] == {
        "control_value": 173.6555555555556,
        "delta": -2.287037037037095,
        "entry_count": 80,
        "prospective_shadow_licensed": False,
        "slate_count": 54,
        "treatment_value": 171.3685185185185,
    }


def test_full_soft_removal_is_hard_false_without_independent_inventory(
    graph: EvidenceGraph,
):
    result = full_soft_removal(graph, "arm:allboom-generation")

    assert result["coverage_complete"] is True
    assert result["independent_policy_rule_inventory_bound"] is False
    assert result["full_soft_removal"] is False
    assert any(
        blocker["reason"] == "v1 has no independent effective-policy rule inventory"
        for blocker in result["blockers"]
    )


def test_baseline_compatibility_distinguishes_shared_and_different_controls(
    graph: EvidenceGraph,
):
    shared = baseline_compatibility(
        graph,
        "measurement:allboom-s",
        "measurement:a3-s",
    )
    different = baseline_compatibility(
        graph,
        "measurement:b1-s",
        "measurement:a7-s",
    )

    assert shared["compatible"] is True
    assert shared["differences"] == {}
    assert different["compatible"] is False
    assert different["differences"]


def test_source_replay_rejects_a_self_receipted_measurement_tamper(
    graph: EvidenceGraph,
    tmp_path: Path,
):
    validate_graph_against_registry(ROOT, REGISTRY, graph)

    poisoned = _replace_node_property(
        graph,
        node_id="measurement:b1-s",
        property_name="delta",
        value=-999.0,
    )
    output = tmp_path / "self-receipted-tamper"
    write_graph(poisoned, output)
    loaded = load_graph(output)

    with pytest.raises(EvidenceGraphError, match="registry|source|replay|differs"):
        validate_graph_against_registry(ROOT, REGISTRY, loaded)


def test_source_replay_rejects_boolean_numeric_type_alias(
    graph: EvidenceGraph,
    tmp_path: Path,
):
    poisoned = _replace_node_property(
        graph,
        node_id="measurement:pool-full-shape",
        property_name="value",
        value=True,
    )
    output = tmp_path / "boolean-numeric-alias"
    write_graph(poisoned, output)
    loaded = load_graph(output)

    with pytest.raises(EvidenceGraphError, match="registry|source|replay|differs"):
        validate_graph_against_registry(ROOT, REGISTRY, loaded)
