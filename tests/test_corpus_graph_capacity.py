"""Adversarial focused tests for the corrected Phase 5 capacity estimator."""

from __future__ import annotations

from collections import Counter
import copy
from types import MappingProxyType

import pytest

from nfl_dfs.research import corpus_graph_capacity as capacity
from nfl_dfs.research import corpus_graph_vnext_contracts as graph
from nfl_dfs.research import corpus_graph_vnext_fixture_adapter as adapter

CREATED = "2026-08-26T00:05:00Z"
FROZEN_LAW_DIGEST = "5d20920d5c5e4a779230a966f29322c46e21a05a5c442422f0f9ad3884dc5fdc"
FROZEN_CONTRACT_DIGEST = "18a0ddb1cb97fa674ed3cd7ce8a2491d16e373d9e49ef172a39b266916183bee"


def _altered_contract(**changes) -> MappingProxyType:
    """A substituted contract object with targeted semantic edits."""

    body = capacity._plain(capacity.SEMANTIC_CONTRACT)
    for path, value in changes.items():
        cursor = body
        parts = path.split("/")
        for part in parts[:-1]:
            cursor = cursor[int(part)] if isinstance(cursor, list) else cursor[part]
        last = parts[-1]
        if isinstance(cursor, list):
            cursor[int(last)] = value
        else:
            cursor[last] = value
    return capacity._freeze(body)  # type: ignore[return-value]


def _inputs(**overrides: object) -> dict[str, object]:
    packet = capacity.fixture_capacity_inputs()
    for key, value in overrides.items():
        section, _, name = key.partition(".")
        if name:
            packet[section][name] = value  # type: ignore[index]
        else:
            packet[key] = value
    return packet


def _lead_inputs(*, assert_digest: bool = True) -> dict[str, object]:
    packet = capacity.fixture_capacity_inputs()
    packet["authority"] = "lead-supplied-terminal"
    for name, identity in packet["identities"].items():  # type: ignore[union-attr]
        identity["uri"] = f"gs://real-bucket/releases/{name}.json"
    for name, entries in packet["release_manifests"].items():  # type: ignore[union-attr]
        for index, entry in enumerate(entries):
            entry["identity"]["uri"] = f"gs://real-bucket/releases/{name}-{index}.json"
    if assert_digest:
        packet["inputs_assertion_sha256"] = capacity.inputs_assertion_digest(packet)
    return packet


# ------------------------------------------------------------- law ---

def test_literal_law_digest_is_frozen_and_recomputed_live() -> None:
    assert capacity.ESTIMATION_LAW_SHA256 == FROZEN_LAW_DIGEST
    assert capacity.law_digest_now() == FROZEN_LAW_DIGEST
    assert capacity.canonical_sha256(dict(capacity.ESTIMATION_LAW)) == FROZEN_LAW_DIGEST


def test_law_is_immutable_at_runtime() -> None:
    with pytest.raises(TypeError):
        capacity.ESTIMATION_LAW["bytes_per_node"] = 1  # type: ignore[index]
    assert isinstance(capacity.ESTIMATION_LAW, MappingProxyType)


def test_substituted_law_cannot_emit_or_validate_receipts(monkeypatch: pytest.MonkeyPatch) -> None:
    genuine = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    altered = dict(capacity.ESTIMATION_LAW)
    altered["bytes_per_node"] = 99
    monkeypatch.setattr(capacity, "ESTIMATION_LAW", MappingProxyType(altered))
    assert capacity.law_digest_now() != FROZEN_LAW_DIGEST
    with pytest.raises(capacity.CorpusGraphCapacityError, match="drifted"):
        capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="drifted|different estimation law"):
        capacity.validate_capacity_receipt(genuine)
    monkeypatch.undo()
    assert capacity.validate_capacity_receipt(genuine)["receipt_sha256"] == genuine["receipt_sha256"]


def test_receipt_with_altered_embedded_law_under_frozen_hash_is_rejected() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    forged = copy.deepcopy(receipt)
    forged["estimation_law"]["bytes_per_node"] = 99  # keep the frozen digest string
    forged["receipt_sha256"] = capacity.canonical_sha256(
        {k: v for k, v in forged.items() if k != "receipt_sha256"}
    )
    with pytest.raises(capacity.CorpusGraphCapacityError, match="different estimation law"):
        capacity.validate_capacity_receipt(forged)


def test_property_schema_version_hashes_complete_rule_content() -> None:
    baseline = capacity.property_schema_version()
    kind = "Lineup"
    original = graph.NODE_PROPERTY_SCHEMA[kind]
    prop = sorted(original)[0]
    rule = original[prop]
    try:
        tightened = graph.PropertyRule(
            rule.value_type,
            max_string_bytes=max(1, rule.max_string_bytes - 1),
            max_list_items=rule.max_list_items,
            allowed_strings=rule.allowed_strings,
        )
        graph.NODE_PROPERTY_SCHEMA[kind] = {**original, prop: tightened}
        assert capacity.property_schema_version() != baseline
    finally:
        graph.NODE_PROPERTY_SCHEMA[kind] = original
    assert capacity.property_schema_version() == baseline


# ------------------------------------------------ semantic contract ---

def test_semantic_contract_digest_is_pinned_frozen_and_live_rederived() -> None:
    assert capacity.SEMANTIC_CONTRACT_SHA256 == FROZEN_CONTRACT_DIGEST
    assert capacity.contract_digest_now() == FROZEN_CONTRACT_DIGEST
    assert isinstance(capacity.SEMANTIC_CONTRACT, MappingProxyType)
    assert capacity.SEMANTIC_CONTRACT["version"] == capacity.SEMANTIC_CONTRACT_VERSION
    for key in (
        "node_count_inputs", "exact_relationship_inputs", "derived_relationship_types",
        "relationship_endpoints", "release_manifests", "identity_inputs",
        "version_inputs", "hash_inputs", "parameter_inputs", "closed_node_kinds",
        "closed_relationship_types", "modes", "roster_slots", "graph_binding",
        "excluded_from_graph",
    ):
        assert key in capacity.SEMANTIC_CONTRACT, key
    assert capacity._plain(capacity.SEMANTIC_CONTRACT["graph_binding"]) == capacity.graph_binding_now()


def test_semantic_registries_are_deep_frozen() -> None:
    with pytest.raises(TypeError):
        capacity.RELATIONSHIP_ENDPOINTS["CONTAINS_PLAYER"]["targets"] = ("Slate",)  # type: ignore[index]
    with pytest.raises(TypeError):
        capacity.RELATIONSHIP_ENDPOINTS["CONTAINS_PLAYER"] = {"sources": (), "targets": ()}  # type: ignore[index]
    with pytest.raises(TypeError):
        capacity.RELEASE_MANIFESTS[0]["count_input"] = "science_release_count"  # type: ignore[index]
    with pytest.raises(TypeError):
        capacity.SEMANTIC_CONTRACT["roster_slots"] = 1  # type: ignore[index]
    with pytest.raises(AttributeError):
        capacity.SEMANTIC_CONTRACT["modes"].append("realized")  # type: ignore[union-attr]


def test_endpoint_map_substitution_cannot_emit_or_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    genuine = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    altered = _altered_contract(**{"relationship_endpoints/CONTAINS_PLAYER/targets": ["Slate"]})
    monkeypatch.setattr(capacity, "SEMANTIC_CONTRACT", altered)
    assert capacity.contract_digest_now() != FROZEN_CONTRACT_DIGEST
    with pytest.raises(capacity.CorpusGraphCapacityError, match="semantic contract content drifted"):
        capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="drifted|different semantic contract"):
        capacity.validate_capacity_receipt(genuine)
    monkeypatch.undo()
    assert capacity.validate_capacity_receipt(genuine)["receipt_sha256"] == genuine["receipt_sha256"]


def test_release_manifest_rebinding_cannot_emit_or_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    genuine = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    altered = _altered_contract(**{"release_manifests/0/count_input": "science_release_count"})
    monkeypatch.setattr(capacity, "SEMANTIC_CONTRACT", altered)
    rebound = _inputs(**{"counts.world_release_count": 2})
    with pytest.raises(capacity.CorpusGraphCapacityError, match="semantic contract content drifted"):
        capacity.validate_capacity_inputs(rebound)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="drifted|different semantic contract"):
        capacity.validate_capacity_receipt(genuine)
    monkeypatch.undo()
    with pytest.raises(capacity.CorpusGraphCapacityError, match="carries 1 entries but its count input is 2"):
        capacity.validate_capacity_inputs(rebound)


def test_receipt_with_altered_embedded_contract_under_pinned_digest_is_rejected() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    forged = copy.deepcopy(receipt)
    forged["semantic_contract"]["relationship_endpoints"]["CONTAINS_PLAYER"]["targets"] = ["Slate"]
    forged["receipt_sha256"] = capacity.canonical_sha256(
        {k: v for k, v in forged.items() if k != "receipt_sha256"}
    )
    with pytest.raises(capacity.CorpusGraphCapacityError, match="different semantic contract"):
        capacity.validate_capacity_receipt(forged)
    stripped = copy.deepcopy(receipt)
    del stripped["semantic_contract"]
    stripped["receipt_sha256"] = capacity.canonical_sha256(
        {k: v for k, v in stripped.items() if k != "receipt_sha256"}
    )
    with pytest.raises(capacity.CorpusGraphCapacityError, match="lacks a semantic contract"):
        capacity.validate_capacity_receipt(stripped)


def test_receipt_embeds_contract_body_and_digest() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    embedded = receipt["semantic_contract"]
    assert embedded["semantic_contract_sha256"] == FROZEN_CONTRACT_DIGEST
    body = {k: v for k, v in embedded.items() if k != "semantic_contract_sha256"}
    assert capacity.canonical_sha256(body) == FROZEN_CONTRACT_DIGEST
    assert body == capacity._plain(capacity.SEMANTIC_CONTRACT)
    assert receipt["excluded_from_graph"] == list(embedded["excluded_from_graph"])
    assert receipt["closed_vocabulary"]["node_kinds"] == list(embedded["closed_node_kinds"])
    assert set(receipt["estimates"]) == set(embedded["modes"])


# ------------------------------------ contract is the sole use-time authority ---

def test_rebinding_cached_registries_cannot_relax_required_fields(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(capacity, "REQUIRED_IDENTITIES", ())
    monkeypatch.setattr(capacity, "REQUIRED_HASHES", ())
    monkeypatch.setattr(capacity, "REQUIRED_COUNTS", ())
    stripped = _inputs()
    stripped["identities"] = {}
    stripped["hashes"] = {}
    with pytest.raises(capacity.CorpusGraphCapacityError, match="identities must carry exactly"):
        capacity.validate_capacity_inputs(stripped)
    stripped = _inputs()
    stripped["hashes"] = {}
    with pytest.raises(capacity.CorpusGraphCapacityError, match="hashes must carry exactly"):
        capacity.validate_capacity_inputs(stripped)
    stripped = _inputs()
    del stripped["counts"]["fold_count"]  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="fold_count"):
        capacity.validate_capacity_inputs(stripped)


def test_rebinding_cached_metadata_cannot_change_receipts(monkeypatch: pytest.MonkeyPatch) -> None:
    genuine = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    monkeypatch.setattr(capacity, "MODES", ("full-lineup",))
    monkeypatch.setattr(capacity, "CLOSED_NODE_KINDS", frozenset())
    monkeypatch.setattr(capacity, "CLOSED_RELATIONSHIP_TYPES", frozenset())
    monkeypatch.setattr(capacity, "DERIVED_RELATIONSHIP_TYPES", frozenset({"CONTAINS_PLAYER"}))
    monkeypatch.setattr(capacity, "RELATIONSHIP_ENDPOINTS", MappingProxyType({}))
    monkeypatch.setattr(capacity, "RELEASE_MANIFESTS", ())
    rebuilt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    assert rebuilt["receipt_sha256"] == genuine["receipt_sha256"]
    assert set(rebuilt["estimates"]) == {"full-lineup", "summary-only"}
    assert rebuilt["closed_vocabulary"]["node_kinds"] == sorted({"WinnerRelease", "WinnerObservation", "OutcomeRelease", "OutcomeGrade"})
    assert len(rebuilt["excluded_from_graph"]) == 8
    assert capacity.required_inputs_manifest() == genuine["required_inputs_manifest"]
    assert capacity.validate_capacity_receipt(genuine)["receipt_sha256"] == genuine["receipt_sha256"]


# ------------------------------------------ live graph contract cross-binding ---

def test_live_graph_vocabulary_drift_cannot_emit_or_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    genuine = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    monkeypatch.setattr(graph, "RELATIONSHIP_TYPES", graph.RELATIONSHIP_TYPES | {"UNBOUND_NEW_EDGE"})
    assert capacity.graph_binding_now() != capacity._plain(capacity.SEMANTIC_CONTRACT["graph_binding"])
    with pytest.raises(capacity.CorpusGraphCapacityError, match="live graph contract differs"):
        capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="live graph contract differs"):
        capacity.validate_capacity_receipt(genuine)
    monkeypatch.undo()
    assert capacity.validate_capacity_receipt(genuine)["receipt_sha256"] == genuine["receipt_sha256"]


def test_live_graph_schema_version_drift_cannot_emit_or_replay(monkeypatch: pytest.MonkeyPatch) -> None:
    genuine = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    monkeypatch.setattr(graph, "GRAPH_SCHEMA_VERSION", "corpus-graph-vnext/v2")
    v2_packet = _inputs(**{"versions.graph_schema_version": "corpus-graph-vnext/v2"})
    with pytest.raises(capacity.CorpusGraphCapacityError, match="live graph contract differs"):
        capacity.validate_capacity_inputs(v2_packet)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="live graph contract differs"):
        capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="live graph contract differs"):
        capacity.validate_capacity_receipt(genuine)


@pytest.mark.parametrize(
    "attribute, mutate",
    [
        ("NODE_KINDS", lambda value: value | {"UnboundKind"}),
        ("RELATIONSHIP_NAMESPACE_SCHEMA", lambda value: {**value, "PLAYS_FOR": frozenset({"realized"})}),
        ("NODE_NAMESPACE_SCHEMA", lambda value: {**value, "Lineup": frozenset({"realized"})}),
        ("OFFLINE_ALLOWED_NAMESPACES", lambda value: value | {"realized"}),
        ("FORBIDDEN_RELATIONSHIP_TYPES", lambda value: frozenset()),
        ("QUALIFIED_INFERRED_TYPES", lambda value: frozenset()),
    ],
)
def test_live_graph_semantic_drift_is_detected(monkeypatch: pytest.MonkeyPatch, attribute: str, mutate) -> None:
    genuine = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    monkeypatch.setattr(graph, attribute, mutate(getattr(graph, attribute)))
    with pytest.raises(capacity.CorpusGraphCapacityError, match="live graph contract differs"):
        capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="live graph contract differs"):
        capacity.validate_capacity_receipt(genuine)


def test_live_property_rule_drift_is_detected(monkeypatch: pytest.MonkeyPatch) -> None:
    genuine = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    original = graph.NODE_PROPERTY_SCHEMA["Lineup"]
    prop = sorted(original)[0]
    rule = original[prop]
    loosened = graph.PropertyRule(rule.value_type, max_string_bytes=rule.max_string_bytes + 1,
                                  max_list_items=rule.max_list_items, allowed_strings=rule.allowed_strings)
    monkeypatch.setitem(graph.NODE_PROPERTY_SCHEMA, "Lineup", {**original, prop: loosened})
    with pytest.raises(capacity.CorpusGraphCapacityError, match="live graph contract differs"):
        capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="live graph contract differs"):
        capacity.validate_capacity_receipt(genuine)


# --------------------------------------------- assertion digest canonical order ---

def test_assertion_digest_is_manifest_order_independent_and_validation_agrees() -> None:
    lead = _lead_inputs(assert_digest=False)
    lead["counts"]["science_release_count"] = 2  # type: ignore[index]
    lead["release_manifests"]["science_releases"].append({  # type: ignore[index]
        "release_id": "science-release-fixture-000",
        "identity": {
            "uri": "gs://real-bucket/releases/science-0.json",
            "generation": "1788000000000099",
            "sha256": "cd" * 32,
            "bytes": 5_000,
        },
    })
    forward = copy.deepcopy(lead)
    reversed_order = copy.deepcopy(lead)
    reversed_order["release_manifests"]["science_releases"].reverse()  # type: ignore[index]
    assert capacity.inputs_assertion_digest(forward) == capacity.inputs_assertion_digest(reversed_order)
    forward["inputs_assertion_sha256"] = capacity.inputs_assertion_digest(forward)
    reversed_order["inputs_assertion_sha256"] = forward["inputs_assertion_sha256"]
    a = capacity.validate_capacity_inputs(forward)
    b = capacity.validate_capacity_inputs(reversed_order)
    assert a["inputs_sha256"] == b["inputs_sha256"]
    assert [e["release_id"] for e in a["release_manifests"]["science_releases"]] == sorted(
        e["release_id"] for e in a["release_manifests"]["science_releases"]
    )


# ----------------------------------------------------- vocabulary ---

def test_every_modeled_kind_and_relationship_is_registered_and_open() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    for mode in capacity.MODES:
        estimate = receipt["estimates"][mode]
        assert set(estimate["node_kinds"]) <= graph.NODE_KINDS
        assert set(estimate["relationship_types"]) <= graph.RELATIONSHIP_TYPES
        assert not set(estimate["node_kinds"]) & capacity.CLOSED_NODE_KINDS
        assert not set(estimate["relationship_types"]) & capacity.CLOSED_RELATIONSHIP_TYPES
        assert "LINEAGE_COMBINED" not in estimate["relationship_types"]
    full = receipt["estimates"]["full-lineup"]
    assert set(full["node_kinds"]) == graph.NODE_KINDS - capacity.CLOSED_NODE_KINDS
    assert set(full["relationship_types"]) == graph.RELATIONSHIP_TYPES - capacity.CLOSED_RELATIONSHIP_TYPES
    assert set(capacity.RELATIONSHIP_ENDPOINTS) == graph.RELATIONSHIP_TYPES - capacity.CLOSED_RELATIONSHIP_TYPES
    for spec in capacity.RELATIONSHIP_ENDPOINTS.values():
        assert set(spec["sources"]) | set(spec["targets"]) <= graph.NODE_KINDS - capacity.CLOSED_NODE_KINDS


def test_realized_firewall_keeps_winner_and_outcome_vocabulary_closed() -> None:
    assert capacity.CLOSED_NODE_KINDS == {"WinnerRelease", "WinnerObservation", "OutcomeRelease", "OutcomeGrade"}
    assert capacity.CLOSED_RELATIONSHIP_TYPES == {"OBSERVED_IN_WINNER_RELEASE", "GRADED_IN_CONTEST", "DERIVED_FROM_OUTCOME"}
    names = {item["name"] for item in capacity.required_inputs_manifest()}
    assert not any("winner" in name or "outcome" in name for name in names)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="unregistered counts"):
        capacity.validate_capacity_inputs(_inputs(**{"counts.winner_observation_count": 51}))


def test_unknown_direct_mode_is_rejected() -> None:
    packet = capacity.validate_capacity_inputs(_inputs())
    with pytest.raises(capacity.CorpusGraphCapacityError, match="not registered"):
        capacity.estimate_mode(packet["counts"], packet["parameters"], "full")
    with pytest.raises(capacity.CorpusGraphCapacityError, match="not registered"):
        capacity.estimate_mode(packet["counts"], packet["parameters"], "realized")


# ------------------------------------------ Phase 4 endpoint parity ---

def _phase4_rows():
    manifest, source = adapter.canonical_fixture_projection()
    terminal = adapter.read_terminal_fixtures(manifest, source)
    return adapter.project_fixture_rows(terminal)


def test_phase4_bundle_book_cardinalities_and_endpoint_pairs_hold() -> None:
    """Phase 4 parity, stated truthfully: bundle/book laws and endpoint
    pairs are checked against the adapter's own synthetic rows. The fixture
    carries ONE CONTAINS_PLAYER edge per lineup; nine per lineup is the
    separate production Phase 5 law and is NOT asserted here."""

    nodes, edges = _phase4_rows()
    kind_by_id = {str(row["node_id"]): str(row["kind"]) for row in nodes}
    kinds = Counter(kind_by_id.values())
    relationships = Counter(str(row["relationship"]) for row in edges)
    assert relationships["ADMITTED_BY"] == kinds["StrategyBundle"]
    assert relationships["SELECTED_BY"] == kinds["StrategyBundle"] + kinds["SelectedBook"]
    assert relationships["GENERATED_BY"] >= kinds["SelectedBook"]
    assert relationships["CONTAINS_PLAYER"] == kinds["Lineup"], "fixture: one player edge per lineup"
    for row in edges:
        relationship = str(row["relationship"])
        spec = capacity.RELATIONSHIP_ENDPOINTS[relationship]
        assert kind_by_id[str(row["source_id"])] in spec["sources"], relationship
        assert kind_by_id[str(row["target_id"])] in spec["targets"], relationship
    assert not set(kinds) & capacity.CLOSED_NODE_KINDS


def test_estimator_applies_bundle_book_laws_and_production_roster_law() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    est = receipt["estimates"]["full-lineup"]["relationship_types"]
    counts = receipt["inputs"]["counts"]
    assert est["ADMITTED_BY"] == counts["strategy_bundle_count"]
    assert est["SELECTED_BY"] == counts["strategy_bundle_count"] + counts["selected_book_count"]
    assert est["MEMBER_OF_BOOK"] == counts["selected_book_membership_count"]
    assert est["CONTAINS_PLAYER"] == 9 * counts["unique_lineup_count"]
    assert set(receipt["estimates"]["full-lineup"]["derived_relationship_types"]) == {
        "ADMITTED_BY", "SELECTED_BY", "CONTAINS_PLAYER",
    }
    assert "MEMBER_OF_BOOK" not in capacity.DERIVED_RELATIONSHIP_TYPES


# ----------------------------------------------- endpoint coherence ---

@pytest.mark.parametrize(
    "relationship_input, empty_kind_input, empty_kind",
    [
        ("plays_for_edge_count", "player_slate_count", "PlayerSlate"),
        ("in_game_edge_count", "game_count", "Game"),
        ("trait_membership_count", "trait_definition_count", "Trait"),
        ("has_metric_edge_count", "metric_set_count", "MetricSet"),
        ("decides_on_bundle_edge_count", "promotion_decision_count", "PromotionDecision"),
        ("uses_world_release_edge_count", "world_release_count", "WorldRelease"),
    ],
)
def test_positive_relationships_need_populated_endpoints(
    relationship_input: str, empty_kind_input: str, empty_kind: str,
) -> None:
    """An emptied endpoint population must fail closed, naming that kind —
    whichever positive relationship touching it is checked first."""

    packet = _inputs(**{f"counts.{relationship_input}": 5, f"counts.{empty_kind_input}": 0})
    if empty_kind_input == "world_release_count":
        packet["release_manifests"]["world_releases"] = []  # type: ignore[index]
    if empty_kind_input == "trait_definition_count":
        packet["counts"]["selected_trait_membership_count"] = 5  # type: ignore[index]
    with pytest.raises(
        capacity.CorpusGraphCapacityError,
        match=rf"has \d+ relationships in [a-z-]+ but no populated (source|target) kind among \[.*'{empty_kind}'",
    ):
        capacity.build_capacity_receipt(packet, created_at_utc=CREATED)


def test_endpoint_failure_names_the_specific_relationship() -> None:
    packet = _inputs(**{"counts.decides_on_bundle_edge_count": 5, "counts.promotion_decision_count": 0})
    with pytest.raises(capacity.CorpusGraphCapacityError, match="DECIDES_ON_BUNDLE has 5 relationships in full-lineup"):
        capacity.build_capacity_receipt(packet, created_at_utc=CREATED)


def test_endpoint_law_is_mode_specific_for_lineups() -> None:
    packet = _inputs(**{
        "counts.selected_unique_lineup_count": 0,
        "counts.selected_lineup_occurrence_count": 0,
        "counts.selected_lineup_arm_supply_count": 0,
        "counts.selected_trait_membership_count": 0,
        "counts.selected_cohort_membership_count": 0,
        "counts.selected_book_count": 0,
        "counts.selected_book_membership_count": 0,
        "counts.generated_by_edge_count": 0,
    })
    receipt = capacity.build_capacity_receipt(packet, created_at_utc=CREATED)
    assert receipt["estimates"]["full-lineup"]["relationship_types"]["MEMBER_OF_CORPUS"] > 0
    assert receipt["estimates"]["summary-only"]["node_kinds"]["Lineup"] == 0
    assert receipt["estimates"]["summary-only"]["relationship_types"]["CONTAINS_PLAYER"] == 0


# --------------------------------------------- identities and counts ---

def test_release_counts_are_bound_to_count_matched_manifests() -> None:
    packet = _inputs(**{"counts.science_release_count": 2})
    with pytest.raises(capacity.CorpusGraphCapacityError, match="carries 1 entries but its count input is 2"):
        capacity.validate_capacity_inputs(packet)
    packet = _inputs()
    packet["release_manifests"]["verifier_releases"].append(  # type: ignore[index]
        copy.deepcopy(packet["release_manifests"]["verifier_releases"][0])  # type: ignore[index]
    )
    with pytest.raises(capacity.CorpusGraphCapacityError, match="carries 2 entries but its count input is 1"):
        capacity.validate_capacity_inputs(packet)
    packet = _inputs(**{"counts.verifier_release_count": 2})
    duplicate = copy.deepcopy(packet["release_manifests"]["verifier_releases"][0])  # type: ignore[index]
    packet["release_manifests"]["verifier_releases"].append(duplicate)  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="repeats a release id or object identity"):
        capacity.validate_capacity_inputs(packet)
    packet = _inputs()
    packet["release_manifests"]["deployment_attestations"][0]["identity"]["sha256"] = "zz" * 32  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="deployment_attestations\\[0\\].identity.sha256"):
        capacity.validate_capacity_inputs(packet)
    packet = _inputs()
    del packet["release_manifests"]["world_releases"]  # type: ignore[union-attr]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="release_manifests must carry exactly"):
        capacity.validate_capacity_inputs(packet)
    assert {item["name"] for item in capacity.required_inputs_manifest() if item["kind"] == "release_manifest"} == {
        "world_releases", "science_releases", "verifier_releases", "deployment_attestations",
    }


def test_r6_full_union_identity_replaces_standalone_t230() -> None:
    names = {item["name"] for item in capacity.required_inputs_manifest()}
    assert {"r6_full_union_panel_freeze_identity", "r6_full_union_panel_self_sha256"} <= names
    assert "t230_panel_release_identity" not in names
    packet = _inputs()
    packet["identities"]["t230_panel_release_identity"] = packet["identities"]["source_universe_release_identity"]  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="identities must carry exactly"):
        capacity.validate_capacity_inputs(packet)


@pytest.mark.parametrize(
    "field, value, message",
    [
        ("uri", "https://not-gcs/x.json", "gs://"),
        ("uri", "gs://synthetic-fixture.invalid", "real gs://bucket/object"),
        ("uri", "gs://synthetic-fixture.invalid/", "real gs://bucket/object"),
        ("uri", "gs://synthetic-fixture.invalid/dir/", "real gs://bucket/object"),
        ("uri", "gs://synthetic-fixture.invalid/a//b.json", "real gs://bucket/object"),
        ("uri", "gs://192.168.5.4/x.json", "real gs://bucket/object"),
        ("uri", "gs://goog-bucket/x.json", "real gs://bucket/object"),
        ("uri", "gs://my-google-bucket/x.json", "real gs://bucket/object"),
        ("uri", "gs://my..bucket/x.json", "real gs://bucket/object"),
        ("uri", "gs://my.-bucket/x.json", "real gs://bucket/object"),
        ("generation", "007", "positive digits"),
        ("sha256", "zz" * 32, "64-hex"),
        ("bytes", 0, "within"),
        ("bytes", 256 * 1024**2 + 1, "within"),
    ],
)
def test_identity_malformations_fail_closed(field: str, value: object, message: str) -> None:
    packet = _inputs()
    packet["identities"]["r6_full_union_panel_freeze_identity"][field] = value  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match=message):
        capacity.validate_capacity_inputs(packet)


def test_real_bucket_names_are_enforced_for_lead_identities() -> None:
    lead = _lead_inputs(assert_digest=False)
    lead["identities"]["source_universe_release_identity"]["uri"] = "gs://Bad_Bucket/x.json"  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="real gs://bucket/object"):
        capacity.validate_capacity_inputs(lead)


def test_bucket_grammar_accepts_legal_long_dotted_names_and_rejects_misspellings() -> None:
    long_dotted = ".".join(["a" * 63] * 3 + ["b" * 20])  # 212 chars, each component <= 63
    assert len(long_dotted) > 63
    assert capacity._valid_gcs_bucket(long_dotted)
    assert capacity._valid_gcs_bucket("nfl-predictions-503414-corpus-retrieval")
    assert capacity._valid_gcs_bucket("synthetic-fixture.invalid")
    for bad in (
        "a" * 64, ".".join(["a" * 64, "b"]), "g00gle-bucket", "my-g0ogle-data", "go0g1e",
        "goog-le", "192.168.5.4", "my..bucket", "my.-bucket", "ab", "-abc", "abc-",
    ):
        assert not capacity._valid_gcs_bucket(bad), bad


def test_identity_class_separation() -> None:
    lead = _lead_inputs()
    lead["identities"]["source_universe_release_identity"]["uri"] = f"{capacity.SYNTHETIC_URI_PREFIX}w.json"  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="synthetic identity"):
        capacity.validate_capacity_inputs(lead)
    fixture = _inputs()
    fixture["release_manifests"]["world_releases"][0]["identity"]["uri"] = "gs://real-bucket/world.json"  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="non-synthetic"):
        capacity.validate_capacity_inputs(fixture)


# ----------------------------------------------- authority labeling ---

def test_assertion_digest_binds_content_but_never_approves() -> None:
    assert not hasattr(capacity, "lead_confirmation_for")
    unasserted = capacity.build_capacity_receipt(_lead_inputs(assert_digest=False), created_at_utc=CREATED)
    assert unasserted["decision"]["state"] == "pending-lead-inputs"
    asserted = capacity.build_capacity_receipt(_lead_inputs(), created_at_utc=CREATED)
    assert asserted["decision"]["state"] == "estimated-pending-approval"
    assert asserted["decision"]["recommended_mode"] == "full-lineup"
    assert asserted["decision"]["approval"]["status"] == "not-authenticated"
    assert asserted["decision"]["approval"]["receipt_identity"] is None
    assert asserted["decision"]["requires_lead_approval"] is True
    assert asserted["decision"]["self_activating"] is False
    assert "decidable" not in asserted["decision"]["state"]
    forged = _lead_inputs()
    forged["inputs_assertion_sha256"] = "ab" * 32
    with pytest.raises(capacity.CorpusGraphCapacityError, match="does not bind the canonical inputs subject"):
        capacity.validate_capacity_inputs(forged)
    moved = _lead_inputs()
    moved["counts"]["unique_lineup_count"] = 70_000  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="does not bind"):
        capacity.validate_capacity_inputs(moved)
    fixture = _inputs()
    fixture["inputs_assertion_sha256"] = capacity.inputs_assertion_digest(fixture)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="assertion digest"):
        capacity.validate_capacity_inputs(fixture)


def test_approval_receipt_slot_is_reserved_and_rejected_offline() -> None:
    lead = _lead_inputs()
    lead["lead_approval_receipt_identity"] = lead["identities"]["source_universe_release_identity"]  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="reserved"):
        capacity.validate_capacity_inputs(lead)
    retained = capacity.validate_capacity_inputs(_lead_inputs())
    assert retained["lead_approval_receipt_identity"] is None


# ---------------------------------------------------- coherence ---

@pytest.mark.parametrize(
    "mutation, message",
    [
        ({"counts.selected_unique_lineup_count": 10**9}, "exceeds unique_lineup_count"),
        ({"counts.lineup_occurrence_count": 1}, "below unique_lineup_count"),
        ({"counts.lineup_arm_supply_count": 1}, "lineup_arm_supply_count is below unique_lineup_count"),
        ({"counts.selected_lineup_occurrence_count": 10**9}, "exceeds lineup_occurrence_count"),
        ({"counts.selected_lineup_occurrence_count": 1}, "selected_lineup_occurrence_count is below selected_unique"),
        ({"counts.selected_lineup_arm_supply_count": 1}, "selected_lineup_arm_supply_count is below selected_unique"),
        ({"counts.selected_trait_membership_count": 10**9}, "exceeds trait_membership_count"),
        ({"counts.selected_book_membership_count": 100}, "selected_book_membership_count is below selected_book_count"),
        ({"counts.selected_book_membership_count": 0}, "jointly zero or jointly positive"),
        ({"counts.generated_by_edge_count": 0}, "generated_by_edge_count is below selected_book_count"),
        ({"counts.strategy_bundle_count": 0}, "without any strategy bundle"),
        ({"counts.mean_string_property_bytes": 0}, "must be positive"),
        ({"counts.unique_lineup_count": -1}, "outside"),
        ({"counts.unique_lineup_count": 1.5}, "exact integer"),
        ({"counts.unique_lineup_count": True}, "exact integer"),
        ({"parameters.provisioned_disk_bytes": 0}, "must be positive"),
        ({"versions.graph_schema_version": "corpus-graph-vnext/v0"}, "graph_schema_version differs"),
        ({"versions.property_schema_version": "corpus-graph-vnext/v1+properties-0000000000000000"}, "property_schema_version differs"),
        ({"created_at_utc": "2026-08-26 00:00"}, "second-precision UTC"),
        ({"created_at_utc": "2026-02-30T00:00:00Z"}, "calendar-valid"),
        ({"created_at_utc": "2026-08-26T24:00:00Z"}, "calendar-valid"),
        ({"authority": "operator"}, "authority is not registered"),
        ({"hashes.r6_full_union_panel_self_sha256": "nope"}, "not 64-hex"),
    ],
)
def test_malformed_or_incoherent_inputs_fail_closed(mutation: dict[str, object], message: str) -> None:
    with pytest.raises(capacity.CorpusGraphCapacityError, match=message):
        capacity.validate_capacity_inputs(_inputs(**mutation))


def test_receipt_created_at_must_be_calendar_valid() -> None:
    with pytest.raises(capacity.CorpusGraphCapacityError, match="second-precision UTC|calendar-valid"):
        capacity.build_capacity_receipt(_inputs(), created_at_utc="2026-13-01T00:00:00Z")


def test_missing_extra_and_malformed_sections_are_named() -> None:
    packet = _inputs()
    del packet["counts"]["fold_count"]  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="fold_count"):
        capacity.validate_capacity_inputs(packet)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="unregistered counts"):
        capacity.validate_capacity_inputs(_inputs(**{"counts.lineage_edge_count": 1}))
    with pytest.raises(capacity.CorpusGraphCapacityError, match="registered packet keys"):
        capacity.validate_capacity_inputs(_inputs(extra_field=1))
    with pytest.raises(capacity.CorpusGraphCapacityError, match="registered packet keys"):
        capacity.validate_capacity_inputs(_inputs(lead_confirmation_sha256="ab" * 32))
    packet = _inputs()
    del packet["release_manifests"]  # type: ignore[arg-type]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="registered packet keys"):
        capacity.validate_capacity_inputs(packet)


# ---------------------------------------------------- estimation ---

def test_receipt_is_deterministic_and_order_independent() -> None:
    first = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    shuffled = _inputs()
    shuffled["counts"] = dict(reversed(list(shuffled["counts"].items())))  # type: ignore[union-attr]
    shuffled["identities"] = dict(reversed(list(shuffled["identities"].items())))  # type: ignore[union-attr]
    second = capacity.build_capacity_receipt(shuffled, created_at_utc=CREATED)
    assert first["receipt_sha256"] == second["receipt_sha256"]


def test_summary_mode_is_smaller_and_never_labeled_full() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    full = receipt["estimates"]["full-lineup"]
    summary = receipt["estimates"]["summary-only"]
    assert summary["node_kinds"]["Lineup"] == 4_320 and full["node_kinds"]["Lineup"] == 60_000
    assert summary["relationship_types"]["CONTAINS_PLAYER"] == 9 * 4_320
    assert summary["estimated_store_bytes"] < full["estimated_store_bytes"]
    assert summary["full_corpus_traversal_available"] is False
    assert "never labeled full" in receipt["labels_law"]


def test_forcing_to_summary_and_none_feasible() -> None:
    packet = _inputs(**{"parameters.provisioned_disk_bytes": 200 * 1024**2})
    receipt = capacity.build_capacity_receipt(packet, created_at_utc=CREATED)
    assert receipt["estimates"]["full-lineup"]["feasible"] is False
    assert receipt["forced_mode"] == "summary-only"
    lead = _lead_inputs(assert_digest=False)
    lead["parameters"]["provisioned_disk_bytes"] = 200 * 1024**2  # type: ignore[index]
    lead["inputs_assertion_sha256"] = capacity.inputs_assertion_digest(lead)
    assert capacity.build_capacity_receipt(lead, created_at_utc=CREATED)["decision"]["recommended_mode"] == "summary-only"
    lead["parameters"]["provisioned_disk_bytes"] = 1  # type: ignore[index]
    lead["inputs_assertion_sha256"] = capacity.inputs_assertion_digest(lead)
    none = capacity.build_capacity_receipt(lead, created_at_utc=CREATED)
    assert none["forced_mode"] == "none-feasible"
    assert none["decision"]["recommended_mode"] is None


def test_element_ceiling_and_deadlines_are_enforced() -> None:
    packet = _inputs(**{
        "counts.unique_lineup_count": 6_000_000,
        "counts.lineup_occurrence_count": 12_000_000,
        "counts.lineup_arm_supply_count": 12_000_000,
        "counts.trait_membership_count": 18_000_000,
        "counts.cohort_membership_count": 6_000_000,
        "parameters.load_deadline_seconds": 10,
    })
    violations = capacity.build_capacity_receipt(packet, created_at_utc=CREATED)["estimates"]["full-lineup"]["violations"]
    assert any("max_graph_elements" in item for item in violations)
    assert any("load_deadline_seconds" in item for item in violations)


def test_estimates_replay_from_law_and_positive_schema() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    full = receipt["estimates"]["full-lineup"]
    law = capacity.ESTIMATION_LAW
    chunk = int(law["string_chunk_bytes"])
    chunks = -(-48 // chunk)
    raw = (
        full["node_count"] * int(law["bytes_per_node"])
        + full["relationship_count"] * int(law["bytes_per_relationship"])
        + full["property_count"] * int(law["bytes_per_property"])
        + full["string_property_count"] * chunks * chunk
    )
    assert full["estimated_raw_bytes"] == raw
    assert full["estimated_store_bytes"] == -(-raw * 1_500 // 1_000)
    expected = sum(len(graph.NODE_PROPERTY_SCHEMA.get(k, {})) * n for k, n in full["node_kinds"].items())
    expected += sum(len(graph.RELATIONSHIP_PROPERTY_SCHEMA.get(r, {})) * n for r, n in full["relationship_types"].items())
    assert full["property_count"] == expected
    assert full["observed"]["store_bytes"] is None


def test_receipt_replays_and_rejects_tamper_and_forge() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    assert capacity.validate_capacity_receipt(receipt)["receipt_sha256"] == receipt["receipt_sha256"]
    tampered = copy.deepcopy(receipt)
    tampered["estimates"]["full-lineup"]["feasible"] = False
    with pytest.raises(capacity.CorpusGraphCapacityError, match="receipt_sha256 differs"):
        capacity.validate_capacity_receipt(tampered)
    forged = copy.deepcopy(receipt)
    forged["inputs"]["counts"]["unique_lineup_count"] = 70_000
    forged["inputs"]["inputs_sha256"] = capacity.canonical_sha256(
        {k: v for k, v in forged["inputs"].items() if k not in ("inputs_sha256", "lead_approval_receipt_identity")}
    )
    forged["receipt_sha256"] = capacity.canonical_sha256({k: v for k, v in forged.items() if k != "receipt_sha256"})
    with pytest.raises(capacity.CorpusGraphCapacityError, match="does not replay"):
        capacity.validate_capacity_receipt(forged)


def test_required_inputs_manifest_covers_every_consumed_input() -> None:
    manifest = capacity.required_inputs_manifest()
    names = {item["name"] for item in manifest}
    fixture = capacity.fixture_capacity_inputs()
    consumed: set[str] = set()
    for section in ("counts", "identities", "release_manifests", "versions", "hashes", "parameters"):
        consumed |= set(fixture[section])  # type: ignore[arg-type]
    assert consumed == names
    assert {item["kind"] for item in manifest} == {"count", "identity", "release_manifest", "version", "hash", "parameter"}
    open_relationships = graph.RELATIONSHIP_TYPES - capacity.CLOSED_RELATIONSHIP_TYPES
    exact_inputs = {str(e["relationship"]) for e in capacity.EXACT_RELATIONSHIP_INPUTS}
    assert exact_inputs | capacity.DERIVED_RELATIONSHIP_TYPES == open_relationships
    assert not exact_inputs & capacity.DERIVED_RELATIONSHIP_TYPES
    counted_kinds = {str(e["kind"]) for e in capacity.NODE_COUNT_INPUTS}
    assert counted_kinds == graph.NODE_KINDS - capacity.CLOSED_NODE_KINDS
    assert set(capacity.SEMANTIC_CONTRACT["closed_node_kinds"]) == capacity.CLOSED_NODE_KINDS
    assert set(capacity.SEMANTIC_CONTRACT["closed_relationship_types"]) == capacity.CLOSED_RELATIONSHIP_TYPES


def test_fixture_scale_is_bounded_and_coherent() -> None:
    for bad in (0, -1, capacity.MAX_FIXTURE_SCALE + 1, True):
        with pytest.raises(capacity.CorpusGraphCapacityError, match="fixture scale"):
            capacity.fixture_capacity_inputs(scale=bad)  # type: ignore[arg-type]
    scaled = capacity.fixture_capacity_inputs(scale=3)
    assert scaled["counts"]["unique_lineup_count"] == 180_000  # type: ignore[index]
    assert scaled["counts"]["selected_unique_lineup_count"] == 4_320  # type: ignore[index]
    assert scaled["counts"]["selected_book_membership_count"] == 54 * 12 * 98  # type: ignore[index]
    for scale in (1, 7, capacity.MAX_FIXTURE_SCALE):
        capacity.validate_capacity_inputs(capacity.fixture_capacity_inputs(scale=scale))
