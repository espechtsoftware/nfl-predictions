"""Hermetic adversarial tests for the bounded lab Phase-B adapter."""

from __future__ import annotations

import csv
import inspect
import io
from copy import deepcopy
from dataclasses import dataclass

import pytest

from nfl_dfs.research import corpus_graph_vnext_contracts as graph
from nfl_dfs.research import lab_epistemics_phase_b as adapter

BASE_NODE_HEADERS = [
    "id:ID", ":LABEL", "text", "status", "score_channel", "note",
    "strength", "prereg", "verdict", "endpoint_era", "class", "reason",
    "releaser", "name", "file", "amendments",
]
RUN_NODE_HEADERS = [
    "id:ID", ":LABEL", "experiment", "code_sha", "image", "shards",
    "slates", "ledger_reconciles", "ledger_violations", "uri", "family",
    "attempts", "new", "dup", "reconciles", "season", "week",
]
EDGE_HEADERS = [":START_ID", ":END_ID", ":TYPE"]


@dataclass(frozen=True)
class Bundle:
    manifest: dict[str, object]
    manifest_raw: bytes
    manifest_identity: dict[str, object]
    artifacts: dict[str, bytes]


def _csv_bytes(headers: list[str], rows: list[dict[str, object]]) -> bytes:
    output = io.StringIO(newline="")
    writer = csv.DictWriter(
        output, fieldnames=headers, lineterminator="\n", extrasaction="raise"
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in headers})
    return output.getvalue().encode("utf-8")


def _base_nodes() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = [{
        "id:ID": "q:bank-breadth",
        ":LABEL": "Question",
        "text": "Do two independent generation streams beat one at fixed compute?",
        "status": "OPEN",
        "score_channel": "supply",
        "note": "exp:078 RUNNING in coordinated lane",
    }]
    rows.extend({
        "id:ID": f"q:{index:03d}",
        ":LABEL": "Question",
        "text": f"Bounded research question {index}",
        "status": "OPEN",
        "score_channel": "selection" if index % 2 else "supply",
        "note": "No source relationship is asserted",
    } for index in range(2, 14))

    rows.append({
        "id:ID": "c:compression-null",
        ":LABEL": "Claim",
        "text": "Removing 575->250 admission changes nothing (twice)",
        "strength": "CONFIRMED",
    })
    rows.extend({
        "id:ID": f"c:{index:03d}",
        ":LABEL": "Claim",
        "text": f"Outcome-free mechanics claim {index}",
        "strength": "SUPPORTED",
    } for index in range(2, 13))

    rows.append({
        "id:ID": "read:001",
        ":LABEL": "Read",
        "prereg": "PREREG-001",
        "verdict": "NULL -0.141",
        "endpoint_era": "pre-objective",
        "class": "gated-preregistered",
    })
    rows.extend({
        "id:ID": f"read:{index:03d}",
        ":LABEL": "Read",
        "prereg": f"PREREG-{index:03d}",
        "verdict": "MECHANICS PASS",
        "endpoint_era": "current-objective",
        "class": "gated-preregistered",
    } for index in range(2, 17))

    rows.extend([
        {
            "id:ID": "hold:registry-v2",
            ":LABEL": "Hold",
            "reason": "Winner-score authority disputed (11 slates, up to 30.46)",
            "releaser": "production registry v2",
        },
        {
            "id:ID": "hold:082-binding",
            ":LABEL": "Hold",
            "reason": "A fresh binding amendment is required",
            "releaser": "production review",
        },
    ])

    experiment_ids = ["exp:078"] + [
        f"exp:{index:03d}" for index in range(1, 81) if index != 78
    ]
    rows.extend({
        "id:ID": experiment_id,
        ":LABEL": "Experiment",
        "name": (
            "078_bank_breadth"
            if experiment_id == "exp:078"
            else f"experiment_{experiment_id.removeprefix('exp:')}"
        ),
    } for experiment_id in experiment_ids)
    rows.extend({
        "id:ID": f"prereg:{index:03d}",
        ":LABEL": "Preregistration",
        "file": f"PREREG-{index:03d}.md",
        "amendments": "0",
    } for index in range(1, 49))
    assert len(rows) == 171
    return rows


def _base_edges() -> list[dict[str, object]]:
    claim_ids = ["c:compression-null"] + [
        f"c:{index:03d}" for index in range(2, 13)
    ]
    rows = [
        {
            ":START_ID": claim_id,
            ":END_ID": f"read:{ordinal:03d}",
            ":TYPE": "EVIDENCED_BY",
        }
        for ordinal, claim_id in enumerate(claim_ids, start=1)
    ]
    rows.extend({
        ":START_ID": claim_ids[index - 1],
        ":END_ID": f"read:{index + 12:03d}",
        ":TYPE": "EVIDENCED_BY",
    } for index in range(1, 4))
    rows.extend([
        {":START_ID": "exp:078", ":END_ID": "hold:registry-v2", ":TYPE": "BLOCKED_BY"},
        {":START_ID": "exp:001", ":END_ID": "hold:registry-v2", ":TYPE": "BLOCKED_BY"},
        {":START_ID": "exp:002", ":END_ID": "hold:082-binding", ":TYPE": "BLOCKED_BY"},
        {":START_ID": "exp:003", ":END_ID": "hold:082-binding", ":TYPE": "BLOCKED_BY"},
    ])
    assert len(rows) == 19
    return rows


def _run_nodes() -> list[dict[str, object]]:
    run_id = "078m520r3-20260901T182923Z"
    rows: list[dict[str, object]] = [{
        "id:ID": f"run:{run_id}",
        ":LABEL": "ExperimentRun",
        "experiment": "078_bank_breadth",
        "code_sha": "165d9e8c1c7d1e47ac4e4f1931a66de718b6934e",
        "image": "sha256:a336af925f04e4fe3db90205bf1fc208c1e91f20cc5f0f50cff5e7deed29c17b",
        "shards": "1",
        "slates": "1",
        "ledger_reconciles": "4",
        "ledger_violations": "0",
        "uri": f"gs://fixture-lab/results/078_bank_breadth/{run_id}/",
    }]
    ledger = [
        ("single", 400, 400, 0),
        ("split", 400, 400, 0),
        ("split_stream1", 240, 240, 0),
        ("split_stream2", 160, 160, 0),
    ]
    rows.extend({
        "id:ID": f"attempts:{run_id}:2021w01:{family}",
        ":LABEL": "ProposalAttemptAggregate",
        "family": family,
        "attempts": str(attempts),
        "new": str(new),
        "dup": str(duplicate),
        "reconciles": "true",
    } for family, attempts, new, duplicate in ledger)
    rows.append({
        "id:ID": "slate:2021-w01",
        ":LABEL": "Slate",
        "season": "2021",
        "week": "1",
    })
    return rows


def _run_edges() -> list[dict[str, object]]:
    run_id = "078m520r3-20260901T182923Z"
    families = ("single", "split", "split_stream1", "split_stream2")
    rows = [{
        ":START_ID": f"attempts:{run_id}:2021w01:{family}",
        ":END_ID": "slate:2021-w01",
        ":TYPE": "PROPOSED_IN",
    } for family in families]
    rows.append({
        ":START_ID": f"run:{run_id}",
        ":END_ID": "exp:078",
        ":TYPE": "PROPOSED_IN",
    })
    return rows


def _expected_census() -> dict[str, object]:
    return {
        "artifact_row_counts": {
            "base_nodes": 171,
            "base_edges": 19,
            "run_nodes": 6,
            "run_edges": 5,
        },
        "node_kind_counts": {
            "Question": 13,
            "Claim": 12,
            "Read": 16,
            "Hold": 2,
            "Experiment": 80,
            "Preregistration": 48,
            "ExperimentRun": 1,
            "ProposalAttemptAggregate": 4,
            "Slate": 1,
        },
        "relationship_type_counts": {
            "EVIDENCED_BY": 15,
            "BLOCKED_BY": 4,
            "PROPOSED_IN": 5,
        },
        "isolated_node_kind_counts": {
            "Question": 13,
            "Read": 1,
            "Experiment": 76,
            "Preregistration": 48,
        },
        "ledger_totals": {
            "reported_attempts": 1_200,
            "reported_new": 1_200,
            "reported_duplicate": 0,
            "reported_reconciles": 4,
            "reported_violations": 0,
            "verified_reconciliations": 0,
        },
    }


def _source(role: str, ordinal: int) -> dict[str, object]:
    raw = f"hermetic source identity for {role}".encode()
    return {
        "role": role,
        "identity": adapter.object_identity(
            f"gs://fixture-lab/source/{role}.json", str(10_000 + ordinal), raw
        ),
        "evidence_class": adapter.SOURCE_ROLE_EVIDENCE_CLASS[role],
        "contains_realized_evidence": False,
        "contains_winner_evidence": False,
        "contains_settlement_evidence": False,
    }


def _build_bundle(
    *,
    artifacts: dict[str, bytes] | None = None,
    expected: dict[str, object] | None = None,
    sources: list[dict[str, object]] | None = None,
) -> Bundle:
    artifact_bodies = artifacts or {
        "base_nodes": _csv_bytes(BASE_NODE_HEADERS, _base_nodes()),
        "base_edges": _csv_bytes(EDGE_HEADERS, _base_edges()),
        "run_nodes": _csv_bytes(RUN_NODE_HEADERS, _run_nodes()),
        "run_edges": _csv_bytes(EDGE_HEADERS, _run_edges()),
    }
    source_rows = sources or [
        _source(role, ordinal)
        for ordinal, role in enumerate(sorted(adapter.REQUIRED_SOURCE_ROLES), start=1)
    ]
    artifact_rows = [{
        "role": role,
        "row_kind": "nodes" if role.endswith("nodes") else "edges",
        "format": adapter.ARTIFACT_FORMAT,
        "identity": adapter.object_identity(
            f"gs://fixture-lab/export/{role}.csv",
            str(20_000 + ordinal),
            artifact_bodies[role],
        ),
        "source_roles": sorted(adapter.ARTIFACT_SOURCE_ROLES[role]),
    } for ordinal, role in enumerate(sorted(artifact_bodies), start=1)]
    manifest = adapter.build_release_manifest(
        graph_release_id="graph-release:lab-phase-b-fixture",
        created_at_utc="2026-09-01T20:00:00Z",
        artifacts=artifact_rows,
        sources=source_rows,
        expected_census=expected or _expected_census(),
    )
    manifest_raw = adapter.canonical_json_bytes(manifest)
    manifest_identity = adapter.object_identity(
        "gs://fixture-lab/release/manifest.json", "30001", manifest_raw
    )
    return Bundle(manifest, manifest_raw, manifest_identity, artifact_bodies)


def _project(bundle: Bundle) -> adapter.LabEpistemicsProjection:
    return adapter.project_lab_packet(
        manifest_raw=bundle.manifest_raw,
        manifest_identity=bundle.manifest_identity,
        artifact_bodies=bundle.artifacts,
    )


def _replace_csv_value(
    raw: bytes, *, row_index: int, key: str, value: str
) -> bytes:
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8"), newline=""))
    assert reader.fieldnames is not None
    rows = [dict(row) for row in reader]
    rows[row_index][key] = value
    return _csv_bytes(list(reader.fieldnames), rows)


def test_exact_full_packet_projection_and_reported_reconciliation() -> None:
    projection = _project(_build_bundle())
    receipt = projection.receipt

    assert graph.GRAPH_SCHEMA_VERSION == "corpus-graph-vnext/v2"
    assert receipt["node_count"] == 177
    assert receipt["relationship_count"] == 24
    assert receipt["artifact_row_counts"] == {
        "base_nodes": 171,
        "base_edges": 19,
        "run_nodes": 6,
        "run_edges": 5,
    }
    assert receipt["source_node_kind_counts"] == dict(sorted(
        _expected_census()["node_kind_counts"].items()
    ))
    assert receipt["source_relationship_type_counts"] == {
        "BLOCKED_BY": 4,
        "EVIDENCED_BY": 15,
        "PROPOSED_IN": 5,
    }
    assert receipt["production_relationship_type_counts"] == {
        "BLOCKED_BY": 4,
        "EVIDENCED_BY": 15,
        "FOR_SLATE": 4,
        "RUN_OF": 1,
    }
    assert receipt["isolated_node_count"] == 138
    assert receipt["isolated_node_kind_counts"] == {
        "Experiment": 76,
        "Preregistration": 48,
        "Question": 13,
        "Read": 1,
    }
    assert receipt["dangling_endpoint_count"] == 0
    assert receipt["claims_without_evidence_count"] == 0
    assert receipt["unresolved_preregistration_reference_count"] == 0
    assert receipt["reported_proposal_ledger_totals"] == {
        "reported_attempts": 1_200,
        "reported_new": 1_200,
        "reported_duplicate": 0,
        "reported_reconciles": 4,
        "reported_violations": 0,
        "verified_reconciliations": 0,
    }
    assert receipt["verified_proposal_reconciliation_count"] == 0
    assert receipt["artifact_bodies_content_verified"] is True
    assert receipt["source_bodies_content_verified"] is False
    assert receipt["artifact_source_derivation_verified"] is False
    assert receipt["database_load_performed"] is False
    assert receipt["declared_source_outcome_evidence_flags_all_false"] is True
    assert receipt["governed_non_hold_outcome_token_scan_passed"] is True
    assert receipt["hold_text_class"] == "governance_blocker_not_evidence"
    assert receipt["authority_flags"] == adapter.AUTHORITY_FLAGS
    assert receipt["receipt_sha256"] == adapter.canonical_sha256({
        key: value for key, value in receipt.items() if key != "receipt_sha256"
    })

    assert projection.load_plan["terminal_census"]["node_count"] == 177
    assert projection.load_plan["terminal_census"]["edge_count"] == 24
    assert projection.load_plan["terminal_census"]["namespaces"] == [
        "epistemic", "identity", "lineage"
    ]
    assert len({node["node_id"] for node in projection.nodes}) == 177
    assert len({edge["edge_key"] for edge in projection.relationships}) == 24
    assert all("id:ID" not in node["properties"] for node in projection.nodes)
    assert all(":LABEL" not in node["properties"] for node in projection.nodes)

    run = next(node for node in projection.nodes if node["kind"] == "RunObservation")
    assert run["namespace"] == "lineage"
    assert run["properties"]["shard_count"] == 1
    assert run["properties"]["verification_status"] == "reported_unverified"
    assert run["properties"]["source_prefix_uri"].endswith("/")
    aggregates = [
        node for node in projection.nodes
        if node["kind"] == "ProposalAttemptAggregate"
    ]
    assert len(aggregates) == 4
    assert all(
        node["properties"]["reconciliation_verified"] is False
        for node in aggregates
    )


def test_mapping_is_deterministic_and_does_not_infer_missing_links() -> None:
    first = _project(_build_bundle())
    second = _project(_build_bundle())
    assert first.load_plan["plan_sha256"] == second.load_plan["plan_sha256"]
    assert first.receipt == second.receipt
    assert not any(
        edge["source_id"].startswith("lab:q:")
        or edge["source_id"].startswith("lab:prereg:")
        for edge in first.relationships
    )
    assert {edge["relationship"] for edge in first.relationships} == {
        "EVIDENCED_BY", "BLOCKED_BY", "RUN_OF", "FOR_SLATE"
    }
    assert "HAS_ATTEMPT_AGGREGATE" not in {
        edge["relationship"] for edge in first.relationships
    }
    assert adapter.MAPPING_CONTRACT_SHA256 == adapter.canonical_sha256(
        adapter.MAPPING_CONTRACT
    )
    assert adapter.MAPPING_CONTRACT["node_property_transforms"][
        "ExperimentRun"
    ]["experiment_name"] == "rename:experiment"
    assert adapter.MAPPING_CONTRACT["semantic_reconciliation"] == [
        "all_claims_have_explicit_evidence_endpoint",
        "all_read_preregistration_references_resolve_without_derived_edges",
        "one_run_one_slate",
        "one_run_of_endpoint_matching_experiment_name",
        "one_for_slate_endpoint_per_aggregate",
        "exact_proposal_family_coverage",
        "run_shard_count_equals_one_manifested_mechanics_shard",
        "run_slate_count_equals_explicit_slate_count",
        "reported_run_ledger_count_equals_aggregate_count",
        "exact_manifest_census_and_isolated_node_census",
    ]


def test_missing_extra_and_content_drifted_artifacts_fail_closed() -> None:
    bundle = _build_bundle()
    missing = dict(bundle.artifacts)
    del missing["run_nodes"]
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="body roles"):
        adapter.project_lab_packet(
            manifest_raw=bundle.manifest_raw,
            manifest_identity=bundle.manifest_identity,
            artifact_bodies=missing,
        )
    extra = {**bundle.artifacts, "unexpected": b"x"}
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="body roles"):
        adapter.project_lab_packet(
            manifest_raw=bundle.manifest_raw,
            manifest_identity=bundle.manifest_identity,
            artifact_bodies=extra,
        )
    drifted = {**bundle.artifacts, "run_edges": bundle.artifacts["run_edges"] + b"\n"}
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="content identity"):
        adapter.project_lab_packet(
            manifest_raw=bundle.manifest_raw,
            manifest_identity=bundle.manifest_identity,
            artifact_bodies=drifted,
        )


def test_manifest_identity_canonicality_and_self_hash_fail_closed() -> None:
    bundle = _build_bundle()
    wrong_identity = {**bundle.manifest_identity, "sha256": "0" * 64}
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="manifest content"):
        adapter.project_lab_packet(
            manifest_raw=bundle.manifest_raw,
            manifest_identity=wrong_identity,
            artifact_bodies=bundle.artifacts,
        )
    noncanonical = b'{"schema_version": "x"}'
    identity = adapter.object_identity(
        "gs://fixture-lab/release/noncanonical.json", "30002", noncanonical
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="not canonical"):
        adapter.project_lab_packet(
            manifest_raw=noncanonical,
            manifest_identity=identity,
            artifact_bodies=bundle.artifacts,
        )
    tampered = {**bundle.manifest, "mapping_contract_sha256": "0" * 64}
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="mapping contract"):
        adapter.validate_release_manifest(tampered)
    missing_self_hash = deepcopy(bundle.manifest)
    missing_self_hash.pop("manifest_sha256")
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="keys differ"):
        adapter.validate_release_manifest(missing_self_hash)
    nonboolean_authority = deepcopy(bundle.manifest)
    nonboolean_authority["authority_flags"]["database_load_authority"] = 0
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="authority flags"):
        adapter.validate_release_manifest(nonboolean_authority)


def test_incomplete_or_conflicting_source_manifest_fails_closed() -> None:
    sources = [
        _source(role, ordinal)
        for ordinal, role in enumerate(sorted(adapter.REQUIRED_SOURCE_ROLES), start=1)
    ]
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="source role coverage"):
        _build_bundle(sources=sources[:-1])
    conflicting = deepcopy(sources)
    conflicting[1]["identity"] = {
        **conflicting[0]["identity"],
        "sha256": "f" * 64,
    }
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="identity conflicts"):
        _build_bundle(sources=conflicting)

    bundle = _build_bundle()
    base_identity = next(
        row["identity"]
        for row in bundle.manifest["artifacts"]
        if row["role"] == "base_nodes"
    )
    colliding_manifest_identity = {
        **bundle.manifest_identity,
        "uri": base_identity["uri"],
        "generation": base_identity["generation"],
    }
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="identity conflicts"):
        adapter.project_lab_packet(
            manifest_raw=bundle.manifest_raw,
            manifest_identity=colliding_manifest_identity,
            artifact_bodies=bundle.artifacts,
        )


def test_dangling_duplicate_and_invalid_endpoint_kinds_fail_closed() -> None:
    bundle = _build_bundle()
    dangling_edges = _replace_csv_value(
        bundle.artifacts["run_edges"],
        row_index=4,
        key=":END_ID",
        value="exp:missing",
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="dangling endpoint"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_edges": dangling_edges
        }))

    invalid_pair = _replace_csv_value(
        bundle.artifacts["run_edges"],
        row_index=0,
        key=":END_ID",
        value="exp:078",
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="endpoint kinds"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_edges": invalid_pair
        }))

    duplicate_rows = _run_nodes() + [dict(_run_nodes()[0])]
    duplicate_nodes = _csv_bytes(RUN_NODE_HEADERS, duplicate_rows)
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="repeats"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_nodes": duplicate_nodes
        }))

    mismatched_experiment = _replace_csv_value(
        bundle.artifacts["run_nodes"],
        row_index=0,
        key="experiment",
        value="experiment_001",
    )
    mismatched_experiment = _replace_csv_value(
        mismatched_experiment,
        row_index=0,
        key="uri",
        value=(
            "gs://fixture-lab/results/experiment_001/"
            "078m520r3-20260901T182923Z/"
        ),
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="does not reconcile"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_nodes": mismatched_experiment
        }))

    unresolved_preregistration = _replace_csv_value(
        bundle.artifacts["base_nodes"],
        row_index=25,
        key="prereg",
        value="PREREG-999",
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="unresolved"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "base_nodes": unresolved_preregistration
        }))


def test_reported_ledger_drift_fails_without_claiming_verification() -> None:
    bundle = _build_bundle()
    inconsistent = _replace_csv_value(
        bundle.artifacts["run_nodes"], row_index=1, key="new", value="399"
    )
    with pytest.raises(
        adapter.LabEpistemicsPhaseBError, match="reported consistency"
    ):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_nodes": inconsistent
        }))
    expected = _expected_census()
    expected["ledger_totals"]["verified_reconciliations"] = 4
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="may not claim"):
        _build_bundle(expected=expected)

    duplicate_family = _replace_csv_value(
        bundle.artifacts["run_nodes"], row_index=2, key="family", value="single"
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="family coverage"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_nodes": duplicate_family
        }))

    unbounded_counts = _replace_csv_value(
        bundle.artifacts["run_nodes"], row_index=0, key="shards", value="999"
    )
    unbounded_counts = _replace_csv_value(
        unbounded_counts, row_index=0, key="slates", value="999"
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="does not reconcile"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_nodes": unbounded_counts
        }))


def test_exact_census_drift_fails_closed() -> None:
    bundle = _build_bundle()
    rows = _base_nodes()
    rows.pop()
    shorter = _csv_bytes(BASE_NODE_HEADERS, rows)
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="artifact row census"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "base_nodes": shorter
        }))


def test_outcome_winner_and_settlement_evidence_stay_closed() -> None:
    bundle = _build_bundle()
    winner_text = _replace_csv_value(
        bundle.artifacts["base_nodes"],
        row_index=0,
        key="text",
        value="The lineup finished first with 250 fantasy points.",
    )
    with pytest.raises(
        adapter.LabEpistemicsPhaseBError,
        match="authorized evidence contract",
    ):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "base_nodes": winner_text
        }))

    experiment_name = _replace_csv_value(
        bundle.artifacts["base_nodes"],
        row_index=43,
        key="name",
        value="winner_score_250",
    )
    with pytest.raises(
        adapter.LabEpistemicsPhaseBError,
        match="authorized evidence contract",
    ):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "base_nodes": experiment_name
        }))

    camel_case_evidence = _replace_csv_value(
        bundle.artifacts["base_nodes"],
        row_index=43,
        key="name",
        value="winnerScore250",
    )
    with pytest.raises(
        adapter.LabEpistemicsPhaseBError,
        match="authorized evidence contract",
    ):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "base_nodes": camel_case_evidence
        }))

    source_flag = deepcopy(bundle.manifest)
    source_flag["sources"][0]["contains_settlement_evidence"] = True
    with pytest.raises(
        adapter.LabEpistemicsPhaseBError,
        match="authorized evidence contract",
    ):
        adapter.validate_release_manifest(source_flag)

    fake_authorization = deepcopy(bundle.manifest)
    fake_authorization["authorized_evidence_identity"] = (
        bundle.manifest["sources"][0]["identity"]
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="cannot open"):
        adapter.validate_release_manifest(fake_authorization)


def test_unknown_outcome_column_and_noncanonical_types_fail_closed() -> None:
    bundle = _build_bundle()
    reader = csv.DictReader(
        io.StringIO(bundle.artifacts["run_nodes"].decode("utf-8"), newline="")
    )
    assert reader.fieldnames is not None
    rows = [dict(row) for row in reader]
    rows[0]["actual_points"] = "200"
    with_outcome_column = _csv_bytes(
        [*reader.fieldnames, "actual_points"], rows
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="ungoverned"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_nodes": with_outcome_column
        }))

    noncanonical_bool = _replace_csv_value(
        bundle.artifacts["run_nodes"], row_index=1, key="reconciles", value="True"
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="true/false"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_nodes": noncanonical_bool
        }))
    noncanonical_int = _replace_csv_value(
        bundle.artifacts["run_nodes"], row_index=1, key="attempts", value="0400"
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="nonnegative integer"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_nodes": noncanonical_int
        }))

    invalid_prefix = _replace_csv_value(
        bundle.artifacts["base_nodes"], row_index=0, key="id:ID", value="bad:q"
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="ID prefix"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "base_nodes": invalid_prefix
        }))

    whitespace_only = _replace_csv_value(
        bundle.artifacts["base_nodes"], row_index=13, key="strength", value="   "
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="whitespace"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "base_nodes": whitespace_only
        }))

    too_long = _replace_csv_value(
        bundle.artifacts["base_nodes"], row_index=13, key="text", value="x" * 513
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="governed node"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "base_nodes": too_long
        }))

    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="gs:// location"):
        adapter.object_identity("gs:///x", "1", b"x")
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="positive digits"):
        adapter.object_identity("gs://fixture/x", "0001", b"x")

    invalid_run_uri = _replace_csv_value(
        bundle.artifacts["run_nodes"], row_index=0, key="uri", value="gs:///"
    )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="gs:// location"):
        _project(_build_bundle(artifacts={
            **bundle.artifacts, "run_nodes": invalid_run_uri
        }))

    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="not bytes"):
        adapter.project_lab_packet(
            manifest_raw=None,
            manifest_identity=bundle.manifest_identity,
            artifact_bodies=bundle.artifacts,
        )
    with pytest.raises(adapter.LabEpistemicsPhaseBError, match="role-to-bytes"):
        adapter.project_lab_packet(
            manifest_raw=bundle.manifest_raw,
            manifest_identity=bundle.manifest_identity,
            artifact_bodies=None,
        )


def test_adapter_has_no_live_or_external_io_surface() -> None:
    source = "\n".join((inspect.getsource(adapter), inspect.getsource(graph)))
    for forbidden in (
        "import neo4j", "from neo4j", "google.cloud", "subprocess",
        "requests", "urlopen", "Path(", "open(",
    ):
        assert forbidden not in source
    assert "load_v1.cypher" not in source
    assert "database_load_performed\": False" in source
