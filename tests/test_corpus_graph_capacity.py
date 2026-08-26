"""Adversarial focused tests for the Phase 5 graph capacity estimator."""

from __future__ import annotations

import copy

import pytest

from nfl_dfs.research import corpus_graph_capacity as capacity
from nfl_dfs.research import corpus_graph_vnext_contracts as graph

CREATED = "2026-08-26T00:05:00Z"


def _inputs(**overrides: object) -> dict[str, object]:
    packet = capacity.fixture_capacity_inputs()
    for key, value in overrides.items():
        section, _, name = key.partition(".")
        if name:
            packet[section][name] = value  # type: ignore[index]
        else:
            packet[key] = value
    return packet


def _lead_inputs() -> dict[str, object]:
    packet = capacity.fixture_capacity_inputs()
    packet["authority"] = "lead-supplied-terminal"
    for name, identity in packet["identities"].items():  # type: ignore[union-attr]
        identity["uri"] = f"gs://real-bucket/releases/{name}.json"
    packet["lead_confirmation_sha256"] = "ab" * 32
    return packet


def test_receipt_is_deterministic_and_order_independent() -> None:
    first = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    shuffled = _inputs()
    shuffled["counts"] = dict(reversed(list(shuffled["counts"].items())))  # type: ignore[union-attr]
    shuffled["identities"] = dict(reversed(list(shuffled["identities"].items())))  # type: ignore[union-attr]
    second = capacity.build_capacity_receipt(shuffled, created_at_utc=CREATED)
    assert first["receipt_sha256"] == second["receipt_sha256"]
    assert first["inputs"]["inputs_sha256"] == second["inputs"]["inputs_sha256"]


def test_fixture_authority_never_decides_a_mode() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    assert receipt["decision"]["state"] == "pending-lead-inputs"
    assert receipt["decision"]["recommended_mode"] is None
    assert receipt["decision"]["requires_lead_approval"] is True
    assert receipt["decision"]["self_activating"] is False
    assert receipt["forced_mode"] is None
    assert receipt["estimates"]["full-lineup"]["feasible"] is True
    assert receipt["estimates"]["summary-only"]["feasible"] is True


def test_lead_inputs_require_a_confirmation_before_recommending() -> None:
    packet = _lead_inputs()
    del packet["lead_confirmation_sha256"]
    receipt = capacity.build_capacity_receipt(packet, created_at_utc=CREATED)
    assert receipt["decision"]["state"] == "pending-lead-inputs"
    confirmed = capacity.build_capacity_receipt(_lead_inputs(), created_at_utc=CREATED)
    assert confirmed["decision"]["state"] == "decidable"
    assert confirmed["decision"]["recommended_mode"] == "full-lineup"
    assert confirmed["decision"]["requires_lead_approval"] is True
    assert confirmed["decision"]["self_activating"] is False


def test_lead_inputs_reject_synthetic_identities_and_fixture_rejects_real_ones() -> None:
    packet = _lead_inputs()
    packet["identities"]["world_release_identity"]["uri"] = (  # type: ignore[index]
        f"{capacity.SYNTHETIC_URI_PREFIX}world.json"
    )
    with pytest.raises(capacity.CorpusGraphCapacityError, match="synthetic identity"):
        capacity.validate_capacity_inputs(packet)
    fixture = _inputs()
    fixture["identities"]["world_release_identity"]["uri"] = "gs://real/world.json"  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="non-synthetic"):
        capacity.validate_capacity_inputs(fixture)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="lead confirmation"):
        capacity.validate_capacity_inputs(_inputs(lead_confirmation_sha256="cd" * 32))


@pytest.mark.parametrize(
    "mutation, message",
    [
        ({"counts.unique_lineup_count": -1}, "outside"),
        ({"counts.unique_lineup_count": 1.5}, "exact integer"),
        ({"counts.unique_lineup_count": True}, "exact integer"),
        ({"counts.unique_lineup_count": 10**13}, "outside"),
        ({"counts.mean_string_property_bytes": 0}, "must be positive"),
        ({"counts.selected_unique_lineup_count": 10**9}, "exceeds unique_lineup_count"),
        ({"counts.lineup_occurrence_count": 1}, "below unique_lineup_count"),
        ({"counts.selected_trait_membership_count": 10**9}, "exceeds trait_membership_count"),
        ({"parameters.provisioned_disk_bytes": 0}, "must be positive"),
        ({"versions.graph_schema_version": "corpus-graph-vnext/v0"}, "graph_schema_version differs"),
        ({"versions.property_schema_version": "wrong"}, "property_schema_version differs"),
        ({"versions.science_release_id": "bad id!"}, "canonical id"),
        ({"created_at_utc": "2026-08-26 00:00"}, "second-precision UTC"),
        ({"authority": "operator"}, "authority is not registered"),
    ],
)
def test_malformed_inputs_fail_closed(mutation: dict[str, object], message: str) -> None:
    with pytest.raises(capacity.CorpusGraphCapacityError, match=message):
        capacity.validate_capacity_inputs(_inputs(**mutation))


def test_missing_or_extra_counts_are_named() -> None:
    packet = _inputs()
    del packet["counts"]["fold_count"]  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="fold_count"):
        capacity.validate_capacity_inputs(packet)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="unregistered counts"):
        capacity.validate_capacity_inputs(_inputs(**{"counts.invented": 1}))
    packet = _inputs()
    del packet["identities"]["winner_release_identity"]  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="identities must carry exactly"):
        capacity.validate_capacity_inputs(packet)
    with pytest.raises(capacity.CorpusGraphCapacityError, match="registered packet keys"):
        capacity.validate_capacity_inputs(_inputs(extra_field=1))


def test_malformed_identities_fail_closed() -> None:
    for field, value, message in (
        ("uri", "https://not-gcs/x.json", "gs://"),
        ("generation", "0", "positive digits"),
        ("generation", "007", "positive digits"),
        ("sha256", "zz" * 32, "64-hex"),
        ("bytes", 0, "positive"),
    ):
        packet = _inputs()
        packet["identities"]["t230_panel_release_identity"][field] = value  # type: ignore[index]
        with pytest.raises(capacity.CorpusGraphCapacityError, match=message):
            capacity.validate_capacity_inputs(packet)
    packet = _inputs()
    packet["identities"]["t230_panel_release_identity"]["extra"] = 1  # type: ignore[index]
    with pytest.raises(capacity.CorpusGraphCapacityError, match="exactly uri/generation"):
        capacity.validate_capacity_inputs(packet)


def test_summary_only_is_smaller_and_never_labeled_full() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    full = receipt["estimates"]["full-lineup"]
    summary = receipt["estimates"]["summary-only"]
    assert summary["node_count"] < full["node_count"]
    assert summary["relationship_count"] < full["relationship_count"]
    assert summary["estimated_store_bytes"] < full["estimated_store_bytes"]
    assert summary["full_corpus_traversal_available"] is False
    assert full["full_corpus_traversal_available"] is True
    assert summary["relationship_types"]["ADMITTED_BY"] == 0
    assert summary["node_kinds"]["Lineup"] == 4_320
    assert full["node_kinds"]["Lineup"] == 60_000
    assert full["relationship_types"]["CONTAINS_PLAYER"] == 9 * 60_000
    assert "never labeled full" in receipt["labels_law"]


def test_full_mode_is_forced_to_summary_when_it_breaches_a_ceiling() -> None:
    packet = _inputs(**{"parameters.provisioned_disk_bytes": 200 * 1024**2})
    receipt = capacity.build_capacity_receipt(packet, created_at_utc=CREATED)
    full = receipt["estimates"]["full-lineup"]
    assert full["feasible"] is False
    assert any("disk safety ceiling" in item for item in full["violations"])
    assert receipt["estimates"]["summary-only"]["feasible"] is True
    assert receipt["forced_mode"] == "summary-only"
    lead = _lead_inputs()
    lead["parameters"]["provisioned_disk_bytes"] = 200 * 1024**2  # type: ignore[index]
    decided = capacity.build_capacity_receipt(lead, created_at_utc=CREATED)
    assert decided["decision"]["recommended_mode"] == "summary-only"


def test_neither_mode_feasible_recommends_nothing() -> None:
    lead = _lead_inputs()
    lead["parameters"]["provisioned_disk_bytes"] = 1  # type: ignore[index]
    receipt = capacity.build_capacity_receipt(lead, created_at_utc=CREATED)
    assert receipt["forced_mode"] == "none-feasible"
    assert receipt["decision"]["state"] == "decidable"
    assert receipt["decision"]["recommended_mode"] is None


def test_element_ceiling_and_deadlines_are_enforced() -> None:
    packet = _inputs(**{
        "counts.unique_lineup_count": 6_000_000,
        "counts.lineup_occurrence_count": 12_000_000,
        "counts.lineup_arm_supply_count": 12_000_000,
        "counts.admitted_membership_count": 6_000_000,
        "counts.trait_membership_count": 18_000_000,
        "counts.cohort_membership_count": 6_000_000,
        "parameters.load_deadline_seconds": 10,
    })
    receipt = capacity.build_capacity_receipt(packet, created_at_utc=CREATED)
    violations = receipt["estimates"]["full-lineup"]["violations"]
    assert any("max_graph_elements" in item for item in violations)
    assert any("load_deadline_seconds" in item for item in violations)


def test_estimates_are_exact_integer_arithmetic_from_the_law() -> None:
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
    assert full["batch_count"] == (
        -(-full["node_count"] // graph.BATCH_SIZE)
        + -(-full["relationship_count"] // graph.BATCH_SIZE)
    )
    assert full["observed"]["store_bytes"] is None
    assert full["observed"]["query_p95_ms"] is None


def test_property_counts_derive_from_the_positive_schema() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    full = receipt["estimates"]["full-lineup"]
    expected = 0
    for kind, count in full["node_kinds"].items():
        expected += len(graph.NODE_PROPERTY_SCHEMA.get(kind, {})) * count
    for relationship, count in full["relationship_types"].items():
        expected += len(graph.RELATIONSHIP_PROPERTY_SCHEMA.get(relationship, {})) * count
    assert full["property_count"] == expected
    assert set(full["node_kinds"]) <= graph.NODE_KINDS


def test_law_hash_is_frozen_and_receipt_replays_or_fails() -> None:
    assert capacity.ESTIMATION_LAW_SHA256 == capacity.canonical_sha256(capacity.ESTIMATION_LAW)
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    replayed = capacity.validate_capacity_receipt(receipt)
    assert replayed["receipt_sha256"] == receipt["receipt_sha256"]
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


def test_required_inputs_manifest_covers_every_consumed_count() -> None:
    manifest = capacity.required_inputs_manifest()
    names = {item["name"] for item in manifest}
    fixture = capacity.fixture_capacity_inputs()
    consumed = set(fixture["counts"]) | set(fixture["identities"]) | set(fixture["versions"]) | set(fixture["parameters"])  # type: ignore[arg-type]
    assert consumed == names
    kinds = {item["kind"] for item in manifest}
    assert kinds == {"count", "identity", "version", "parameter"}
    summary_only = {
        item["name"] for item in manifest if item["modes"] == ["summary-only"]
    }
    assert "selected_lineup_occurrence_count" in summary_only
    full_only = {item["name"] for item in manifest if item["modes"] == ["full-lineup"]}
    assert "unique_lineup_count" in full_only


def test_receipt_records_exclusions_and_property_schema_binding() -> None:
    receipt = capacity.build_capacity_receipt(_inputs(), created_at_utc=CREATED)
    excluded = receipt["excluded_from_graph"]
    assert "world score matrices" in excluded
    assert "realized namespace (closed offline)" in excluded
    assert receipt["inputs"]["versions"]["property_schema_version"] == capacity.property_schema_version()
    assert receipt["inputs"]["versions"]["property_schema_version"].startswith(graph.GRAPH_SCHEMA_VERSION)


def test_fixture_scale_is_bounded() -> None:
    with pytest.raises(capacity.CorpusGraphCapacityError, match="positive integer"):
        capacity.fixture_capacity_inputs(scale=0)
    bigger = capacity.fixture_capacity_inputs(scale=3)
    assert bigger["counts"]["unique_lineup_count"] == 180_000  # type: ignore[index]
