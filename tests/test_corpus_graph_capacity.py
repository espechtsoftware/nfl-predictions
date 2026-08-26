"""Adversarial focused tests for the corrected Phase 5 capacity estimator."""

from __future__ import annotations

from collections import Counter
import copy

import pytest

from nfl_dfs.research import corpus_graph_capacity as capacity
from nfl_dfs.research import corpus_graph_vnext_contracts as graph
from nfl_dfs.research import corpus_graph_vnext_fixture_adapter as adapter

CREATED = "2026-08-26T00:05:00Z"
FROZEN_LAW_DIGEST = "5d20920d5c5e4a779230a966f29322c46e21a05a5c442422f0f9ad3884dc5fdc"


def _inputs(**overrides: object) -> dict[str, object]:
    packet = capacity.fixture_capacity_inputs()
    for key, value in overrides.items():
        section, _, name = key.partition(".")
        if name:
            packet[section][name] = value  # type: ignore[index]
        else:
            packet[key] = value
    return packet


def _lead_inputs(*, confirm: bool = True) -> dict[str, object]:
    packet = capacity.fixture_capacity_inputs()
    packet["authority"] = "lead-supplied-terminal"
    for name, identity in packet["identities"].items():  # type: ignore[union-attr]
        identity["uri"] = f"gs://real-bucket/releases/{name}.json"
    if confirm:
        packet["lead_confirmation_sha256"] = capacity.lead_confirmation_for(packet)
    return packet


# ---------------------------------------------------------------- law ---

def test_literal_law_digest_is_frozen() -> None:
    assert capacity.ESTIMATION_LAW_SHA256 == FROZEN_LAW_DIGEST
    assert capacity.canonical_sha256(capacity.ESTIMATION_LAW) == FROZEN_LAW_DIGEST


def test_property_schema_version_hashes_complete_rule_content() -> None:
    baseline = capacity.property_schema_version()
    assert baseline.startswith(graph.GRAPH_SCHEMA_VERSION)
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
        assert capacity.property_schema_version() != baseline, (
            "a size-only rule change must change the property schema hash"
        )
    finally:
        graph.NODE_PROPERTY_SCHEMA[kind] = original
    assert capacity.property_schema_version() == baseline


# --------------------------------------------------------- vocabulary ---

def test_every_modeled_kind_and_relationship_is_registered_and_open() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    for mode in capacity.MODES:
        estimate = receipt["estimates"][mode]
        kinds = set(estimate["node_kinds"])
        relationships = set(estimate["relationship_types"])
        assert kinds <= graph.NODE_KINDS
        assert relationships <= graph.RELATIONSHIP_TYPES
        assert not kinds & capacity.CLOSED_NODE_KINDS
        assert not relationships & capacity.CLOSED_RELATIONSHIP_TYPES
        assert "LINEAGE_COMBINED" not in relationships
    full = receipt["estimates"]["full-lineup"]
    assert set(full["node_kinds"]) == graph.NODE_KINDS - capacity.CLOSED_NODE_KINDS
    assert set(full["relationship_types"]) == (
        graph.RELATIONSHIP_TYPES - capacity.CLOSED_RELATIONSHIP_TYPES
    )


def test_realized_firewall_keeps_winner_and_outcome_vocabulary_closed() -> None:
    assert capacity.CLOSED_NODE_KINDS == {
        "WinnerRelease", "WinnerObservation", "OutcomeRelease", "OutcomeGrade",
    }
    assert capacity.CLOSED_RELATIONSHIP_TYPES == {
        "OBSERVED_IN_WINNER_RELEASE", "GRADED_IN_CONTEST", "DERIVED_FROM_OUTCOME",
    }
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    assert set(receipt["closed_vocabulary"]["node_kinds"]) == capacity.CLOSED_NODE_KINDS
    names = {item["name"] for item in capacity.required_inputs_manifest()}
    assert not any("winner" in name for name in names)
    assert not any("outcome" in name for name in names)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="unregistered counts"):
        capacity.validate_capacity_inputs(_inputs(**{"counts.winner_observation_count": 51}))


def test_omitted_snapshot_release_and_attestation_kinds_are_now_counted() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    kinds = receipt["estimates"]["full-lineup"]["node_kinds"]
    for kind in (
        "SlateSnapshot", "WorldRelease", "CorpusSnapshot", "CandidateSnapshot",
        "ScienceRelease", "VerifierRelease", "DeploymentAttestation",
    ):
        assert kind in kinds, kind
    assert kinds["DeploymentAttestation"] == 1
    assert kinds["CorpusSnapshot"] == 54 * 7


# ---------------------------------------------- Phase 4 endpoint parity ---

def _phase4_census() -> tuple[Counter[str], Counter[str]]:
    manifest, source = adapter.canonical_fixture_projection()
    terminal = adapter.read_terminal_fixtures(manifest, source)
    nodes, edges = adapter.project_fixture_rows(terminal)
    return (
        Counter(str(row["kind"]) for row in nodes),
        Counter(str(row["relationship"]) for row in edges),
    )


def test_derived_cardinalities_match_phase4_endpoint_semantics() -> None:
    kinds, relationships = _phase4_census()
    bundles = kinds["StrategyBundle"]
    books = kinds["SelectedBook"]
    assert bundles > 0 and books > 0
    assert relationships["ADMITTED_BY"] == bundles
    assert relationships["SELECTED_BY"] == bundles + books
    assert relationships["GENERATED_BY"] >= books
    assert relationships["MEMBER_OF_BOOK"] >= books
    assert set(relationships) <= graph.RELATIONSHIP_TYPES
    assert not set(relationships) & capacity.CLOSED_RELATIONSHIP_TYPES
    assert not set(kinds) & capacity.CLOSED_NODE_KINDS

    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    est = receipt["estimates"]["full-lineup"]["relationship_types"]
    counts = receipt["inputs"]["counts"]
    assert est["ADMITTED_BY"] == counts["strategy_bundle_count"]
    assert est["SELECTED_BY"] == counts["strategy_bundle_count"] + counts["selected_book_count"]
    assert est["MEMBER_OF_BOOK"] == counts["selected_book_membership_count"]
    assert est["CONTAINS_PLAYER"] == 9 * counts["unique_lineup_count"]
    assert set(receipt["estimates"]["full-lineup"]["derived_relationship_types"]) == {
        "ADMITTED_BY", "SELECTED_BY", "MEMBER_OF_BOOK", "CONTAINS_PLAYER",
    }


def test_summary_mode_keeps_bundle_and_book_structure_but_drops_corpus_scale() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    full = receipt["estimates"]["full-lineup"]
    summary = receipt["estimates"]["summary-only"]
    assert summary["relationship_types"]["ADMITTED_BY"] == full["relationship_types"]["ADMITTED_BY"]
    assert summary["relationship_types"]["SELECTED_BY"] == full["relationship_types"]["SELECTED_BY"]
    assert summary["relationship_types"]["MEMBER_OF_BOOK"] == full["relationship_types"]["MEMBER_OF_BOOK"]
    assert summary["node_kinds"]["Lineup"] == 4_320
    assert full["node_kinds"]["Lineup"] == 60_000
    assert summary["relationship_types"]["CONTAINS_PLAYER"] == 9 * 4_320
    assert summary["estimated_store_bytes"] < full["estimated_store_bytes"]
    assert summary["full_corpus_traversal_available"] is False
    assert "never labeled full" in receipt["labels_law"]


# ------------------------------------------------------ identities/hash ---

def test_r6_full_union_identity_replaces_standalone_t230() -> None:
    names = {item["name"] for item in capacity.required_inputs_manifest()}
    assert "r6_full_union_panel_freeze_identity" in names
    assert "r6_full_union_panel_self_sha256" in names
    assert "t230_panel_release_identity" not in names
    packet = _inputs()
    packet["identities"]["t230_panel_release_identity"] = packet["identities"]["world_release_identity"]  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="identities must carry exactly"):
        capacity.validate_capacity_inputs(packet)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="hashes.r6_full_union_panel_self_sha256 is not 64-hex"):
        capacity.validate_capacity_inputs(_inputs(**{"hashes.r6_full_union_panel_self_sha256": "nope"}))


def test_lead_confirmation_must_bind_the_canonical_subject() -> None:
    unconfirmed = _lead_inputs(confirm=False)
    assert capacity.build_capacity_receipt(unconfirmed, created_at_utc=CREATED)["decision"]["state"] == "pending-lead-inputs"
    confirmed = _lead_inputs()
    receipt = capacity.build_capacity_receipt(confirmed, created_at_utc=CREATED)
    assert receipt["decision"]["state"] == "decidable"
    assert receipt["decision"]["recommended_mode"] == "full-lineup"
    assert receipt["decision"]["requires_lead_approval"] is True
    assert receipt["decision"]["self_activating"] is False
    # Any well-formed but unbound hash is rejected.
    forged = _lead_inputs()
    forged["lead_confirmation_sha256"] = "ab" * 32
    with pytest.raises(capacity.CorpusGraphCapacityError, match="does not bind the canonical inputs subject"):
        capacity.validate_capacity_inputs(forged)
    # A confirmation over different counts does not transfer.
    moved = _lead_inputs()
    moved["counts"]["unique_lineup_count"] = 70_000  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="does not bind"):
        capacity.validate_capacity_inputs(moved)
    # The subject is the inputs digest, not the receipt.
    expected = capacity.canonical_sha256({
        "subject": capacity.LEAD_CONFIRMATION_SUBJECT,
        "inputs_sha256": capacity.canonical_sha256({
            key: confirmed[key]
            for key in (
                "schema_version", "authority", "counts", "identities",
                "versions", "hashes", "parameters", "created_at_utc",
            )
        }),
    })
    assert confirmed["lead_confirmation_sha256"] == expected


def test_fixture_authority_never_decides_and_rejects_confirmation() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    assert receipt["decision"]["state"] == "pending-lead-inputs"
    assert receipt["decision"]["recommended_mode"] is None
    assert receipt["forced_mode"] is None
    packet = _inputs()
    packet["lead_confirmation_sha256"] = capacity.lead_confirmation_for(packet)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="lead confirmation"):
        capacity.validate_capacity_inputs(packet)


def test_identity_class_separation() -> None:
    lead = _lead_inputs()
    lead["identities"]["world_release_identity"]["uri"] = f"{capacity.SYNTHETIC_URI_PREFIX}w.json"  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="synthetic identity"):
        capacity.validate_capacity_inputs(lead)
    fixture = _inputs()
    fixture["identities"]["world_release_identity"]["uri"] = "gs://real/world.json"  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="non-synthetic"):
        capacity.validate_capacity_inputs(fixture)


# --------------------------------------------------------- coherence ---

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
        ({"authority": "operator"}, "authority is not registered"),
    ],
)
def test_malformed_or_incoherent_inputs_fail_closed(mutation: dict[str, object], message: str) -> None:
    with pytest.raises(capacity.CorpusGraphCapacityError, match=message):
        capacity.validate_capacity_inputs(_inputs(**mutation))


def test_selected_lineups_zero_requires_no_books() -> None:
    packet = _inputs(**{
        "counts.selected_unique_lineup_count": 0,
        "counts.selected_lineup_occurrence_count": 0,
        "counts.selected_lineup_arm_supply_count": 0,
        "counts.selected_trait_membership_count": 0,
        "counts.selected_cohort_membership_count": 0,
    })
    with pytest.raises(capacity.CorpusGraphCapacityError, match="selected_unique_lineup_count is zero"):
        capacity.validate_capacity_inputs(packet)


def test_missing_extra_and_malformed_sections_are_named() -> None:
    packet = _inputs()
    del packet["counts"]["fold_count"]  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="fold_count"):
        capacity.validate_capacity_inputs(packet)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="unregistered counts"):
        capacity.validate_capacity_inputs(_inputs(**{"counts.lineage_edge_count": 1}))
    with pytest.raises(capacity.CorpusGraphCapacityError, match="registered packet keys"):
        capacity.validate_capacity_inputs(_inputs(extra_field=1))
    packet = _inputs()
    del packet["hashes"]  # type: ignore[arg-type]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="registered packet keys"):
        capacity.validate_capacity_inputs(packet)
    for field, value, message in (
        ("uri", "https://not-gcs/x.json", "gs://"),
        ("generation", "007", "positive digits"),
        ("sha256", "zz" * 32, "64-hex"),
        ("bytes", 0, "positive"),
    ):
        packet = _inputs()
        packet["identities"]["r6_full_union_panel_freeze_identity"][field] = value  # type: ignore[index]
        with pytest.raises(capacity.CorpusGraphCapacityError, match=message):
            capacity.validate_capacity_inputs(packet)


# --------------------------------------------------------- estimation ---

def test_receipt_is_deterministic_and_order_independent() -> None:
    first = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    shuffled = _inputs()
    shuffled["counts"] = dict(reversed(list(shuffled["counts"].items())))  # type: ignore[union-attr]
    shuffled["identities"] = dict(reversed(list(shuffled["identities"].items())))  # type: ignore[union-attr]
    second = capacity.build_capacity_receipt(shuffled, created_at_utc=CREATED)
    assert first["receipt_sha256"] == second["receipt_sha256"]


def test_forcing_to_summary_and_none_feasible() -> None:
    packet = _inputs(**{"parameters.provisioned_disk_bytes": 200 * 1024**2})
    receipt = capacity.build_capacity_receipt(packet, created_at_utc=CREATED)
    assert receipt["estimates"]["full-lineup"]["feasible"] is False
    assert receipt["forced_mode"] == "summary-only"
    lead = _lead_inputs(confirm=False)
    lead["parameters"]["provisioned_disk_bytes"] = 200 * 1024**2  # type: ignore[index]
    lead["lead_confirmation_sha256"] = capacity.lead_confirmation_for(lead)
    assert capacity.build_capacity_receipt(lead, created_at_utc=CREATED)["decision"]["recommended_mode"] == "summary-only"
    lead["parameters"]["provisioned_disk_bytes"] = 1  # type: ignore[index]
    lead["lead_confirmation_sha256"] = capacity.lead_confirmation_for(lead)
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
    expected = 0
    for kind, count in full["node_kinds"].items():
        expected += len(graph.NODE_PROPERTY_SCHEMA.get(kind, {})) * count
    for relationship, count in full["relationship_types"].items():
        expected += len(graph.RELATIONSHIP_PROPERTY_SCHEMA.get(relationship, {})) * count
    assert full["property_count"] == expected
    assert full["observed"]["store_bytes"] is None


def test_receipt_replays_and_rejects_tamper_forge_and_relaw() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    assert capacity.validate_capacity_receipt(receipt)["receipt_sha256"] == receipt["receipt_sha256"]
    tampered = copy.deepcopy(receipt)
    tampered["estimates"]["full-lineup"]["feasible"] = False
    with pytest.raises(capacity.CorpusGraphCapacityError, match="receipt_sha256 differs"):
        capacity.validate_capacity_receipt(tampered)
    forged = copy.deepcopy(receipt)
    forged["inputs"]["counts"]["unique_lineup_count"] = 70_000
    forged["inputs"]["inputs_sha256"] = capacity.canonical_sha256(
        {k: v for k, v in forged["inputs"].items() if k != "inputs_sha256"}
    )
    forged["receipt_sha256"] = capacity.canonical_sha256(
        {k: v for k, v in forged.items() if k != "receipt_sha256"}
    )
    with pytest.raises(capacity.CorpusGraphCapacityError, match="does not replay"):
        capacity.validate_capacity_receipt(forged)
    relawed = copy.deepcopy(receipt)
    relawed["estimation_law"]["estimation_law_sha256"] = "0" * 64
    relawed["receipt_sha256"] = capacity.canonical_sha256(
        {k: v for k, v in relawed.items() if k != "receipt_sha256"}
    )
    with pytest.raises(capacity.CorpusGraphCapacityError, match="different estimation law"):
        capacity.validate_capacity_receipt(relawed)


def test_required_inputs_manifest_covers_every_consumed_input() -> None:
    manifest = capacity.required_inputs_manifest()
    names = {item["name"] for item in manifest}
    fixture = capacity.fixture_capacity_inputs()
    consumed: set[str] = set()
    for section in ("counts", "identities", "versions", "hashes", "parameters"):
        consumed |= set(fixture[section])  # type: ignore[arg-type]
    assert consumed == names
    assert {item["kind"] for item in manifest} == {"count", "identity", "version", "hash", "parameter"}
    open_relationships = graph.RELATIONSHIP_TYPES - capacity.CLOSED_RELATIONSHIP_TYPES
    exact_inputs = {relationship for _, relationship, _, _ in capacity._EXACT_RELATIONSHIP_INPUTS}
    assert exact_inputs | capacity.DERIVED_RELATIONSHIP_TYPES == open_relationships
    assert "MEMBER_OF_BOOK" in exact_inputs and "MEMBER_OF_BOOK" in capacity.DERIVED_RELATIONSHIP_TYPES
    counted_kinds = {kind for _, kind, _, _ in capacity._NODE_COUNT_INPUTS}
    assert counted_kinds == graph.NODE_KINDS - capacity.CLOSED_NODE_KINDS


def test_fixture_scale_is_bounded() -> None:
    with pytest.raises(capacity.CorpusGraphCapacityError, match="positive integer"):
        capacity.fixture_capacity_inputs(scale=0)
    assert capacity.fixture_capacity_inputs(scale=3)["counts"]["unique_lineup_count"] == 180_000  # type: ignore[index]
