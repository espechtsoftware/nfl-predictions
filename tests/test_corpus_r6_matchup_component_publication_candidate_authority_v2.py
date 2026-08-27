from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
from pathlib import Path
from typing import Any, Mapping

import pytest

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v1 as candidate_authority,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_candidate_authority_v2 as publish_v2,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_v1 as publish_v1,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


def _digest(label: str) -> str:
    return sha256(label.encode()).hexdigest()


def canonical_sha256(value: object) -> str:
    return source.canonical_sha256(value)


def _identity(uri: str, label: str) -> dict[str, object]:
    raw = source.canonical_json_bytes({"fixture": label})
    return {
        "uri": uri,
        "generation": str(int(_digest(label)[:10], 16)),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _identity_for_body(
    body: object, *, uri: str, generation: str,
) -> dict[str, object]:
    raw = source.canonical_json_bytes(body)
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _v1_receipt(
    *,
    catalog_replay_identity: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    candidate_release_identity: Mapping[str, object],
) -> dict[str, object]:
    upstream_identity = _identity(
        "gs://fixture-upstream/upstream-release.json", "upstream"
    )
    producer_identity = _identity(
        "gs://fixture-producer/output/producer-release.json", "producer-root"
    )
    body: dict[str, object] = {
        "schema_version": publish_v1.PUBLICATION_RECEIPT_SCHEMA,
        "producer_id": "fixture-producer",
        "producer_release_id": "fixture-release",
        "producer_namespace": "gs://fixture-producer/output/",
        "source_task_count": source.TASK_COUNT,
        "fixed_g0_replay_receipt_identity": dict(catalog_replay_identity),
        "catalog_release_identity": dict(catalog_release_identity),
        "accepted_candidate_release_identity": dict(candidate_release_identity),
        "upstream_source_release_identity": upstream_identity,
        "upstream_provenance_identities": [],
        "upstream_provenance_identity_manifest_sha256": source.canonical_sha256(
            []
        ),
        "materialized_object_count": 1,
        "materialized_object_identities": [producer_identity],
        "materialized_object_identity_manifest_sha256": source.canonical_sha256(
            [producer_identity]
        ),
        "producer_release_identity": producer_identity,
        "producer_release_object_sha256": producer_identity["sha256"],
        "producer_release_sha256": _digest("producer-release-internal"),
        "all_inputs_exact_reopened_before_publication": True,
        "all_outputs_exact_reopened": True,
        "producer_release_published_last": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    body["component_publication_receipt_sha256"] = source.canonical_sha256(body)
    return publish_v1.validate_component_publication_receipt_v1(body)


def _fixture(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    prefix = (
        f"gs://{candidate_authority.OUTPUT_BUCKET}/"
        f"{candidate_authority.OUTPUT_NAMESPACE}/fixture-run-5678/"
    )
    root_identity = _identity(
        f"{prefix}{candidate_authority.ROOT_FILENAME}", "candidate-root"
    )
    candidate_identity = _identity(
        f"{prefix}{candidate_authority.CANDIDATE_RELEASE_FILENAME}",
        "candidate-release",
    )
    catalog_replay_identity = _identity(
        "gs://fixture-catalog/fixed-g0-replay-receipt.json", "catalog-replay"
    )
    catalog_release_identity = _identity(
        "gs://fixture-catalog/catalog-release.json", "catalog-release"
    )
    catalog_replay_sha = _digest("catalog-replay-internal")
    catalog_release_sha = _digest("catalog-release-internal")
    candidate_release_sha = _digest("candidate-release-internal")
    root_sha = _digest("candidate-root-internal")
    candidate_release = {
        "accepted_candidate_release_sha256": candidate_release_sha,
        "entries": [{"fixture": ordinal} for ordinal in range(source.TASK_COUNT)],
    }
    root = {
        "target_uri": root_identity["uri"],
        "candidate_authority_release_sha256": root_sha,
        "candidate_release_identity": candidate_identity,
        "candidate_release_sha256": candidate_release_sha,
        "catalog_replay_receipt_identity": catalog_replay_identity,
        "catalog_replay_receipt_sha256": catalog_replay_sha,
        "candidate_population_authority": True,
        "exact_occurrence_provenance_authority": True,
        "authoritative_reopen_required": True,
        "structure_only_validation_authority": False,
        "complete": True,
    }
    reopened = candidate_authority.ReopenedFixedG0CandidateAuthorityV1(
        root=root,
        root_identity=root_identity,
        authority_bundle={
            "panel_derivation_receipt": {
                "catalog_replay_receipt_identity": catalog_replay_identity,
                "catalog_replay_receipt_sha256": catalog_replay_sha,
                "catalog_release_identity": catalog_release_identity,
                "catalog_release_sha256": catalog_release_sha,
                "candidate_release_sha256": candidate_release_sha,
            },
        },
        candidate_release=candidate_release,
        candidate_release_identity=candidate_identity,
    )
    reopen_calls: list[dict[str, object]] = []
    v1_calls: list[dict[str, object]] = []

    def reopen(root_value: Mapping[str, object], **_kwargs: object):
        reopen_calls.append(dict(root_value))
        return reopened

    def publish_v1_fake(**kwargs: object) -> dict[str, object]:
        v1_calls.append(dict(kwargs))
        receipt = _v1_receipt(
            catalog_replay_identity=kwargs["fixed_g0_replay_receipt_identity"],
            catalog_release_identity=kwargs["catalog_release_identity"],
            candidate_release_identity=kwargs[
                "accepted_candidate_release_identity"
            ],
        )
        return {
            "publication_receipt": receipt,
            "offline_panel": {
                "fixed_g0_replay_receipt_identity": kwargs[
                    "fixed_g0_replay_receipt_identity"
                ],
                "catalog_release_identity": kwargs["catalog_release_identity"],
                "accepted_candidate_release": kwargs[
                    "accepted_candidate_release"
                ],
                "accepted_candidate_release_identity": kwargs[
                    "accepted_candidate_release_identity"
                ],
            },
        }

    monkeypatch.setattr(
        candidate_authority,
        "reopen_fixed_g0_candidate_authority_release_v1",
        reopen,
    )
    monkeypatch.setattr(
        publish_v1, "publish_all_54_component_release_v1", publish_v1_fake
    )
    return {
        "root_identity": root_identity,
        "candidate_identity": candidate_identity,
        "candidate_release": candidate_release,
        "catalog_replay_identity": catalog_replay_identity,
        "catalog_replay_sha": catalog_replay_sha,
        "catalog_release_identity": catalog_release_identity,
        "catalog_release_sha": catalog_release_sha,
        "root": root,
        "reopened": reopened,
        "reopen_calls": reopen_calls,
        "v1_calls": v1_calls,
    }


def _publish(fixture: Mapping[str, Any]) -> dict[str, object]:
    return publish_v2.publish_all_54_component_release_candidate_authority_v2(
        producer_id="fixture-producer",
        producer_release_id="fixture-release",
        producer_namespace="gs://fixture-producer/output/",
        fixed_g0_replay_receipt={
            "replay_receipt_sha256": fixture["catalog_replay_sha"]
        },
        fixed_g0_replay_receipt_identity=fixture["catalog_replay_identity"],
        catalog_release={
            "release_sha256": fixture["catalog_release_sha"],
            "fixture": True,
        },
        catalog_release_identity=fixture["catalog_release_identity"],
        structural_catalogs=[],
        candidate_authority_root_identity=fixture["root_identity"],
        repository_root=Path("/fixture"),
        git_head=lambda _root: "1" * 40,
        git_blob=lambda _root, _commit, _path: b"fixture",
        git_status=lambda _root, _paths: b"",
        upstream_source_release={"fixture": True},
        upstream_source_release_identity=_identity(
            "gs://fixture-upstream/upstream-release.json", "upstream-input"
        ),
        upstream_pack_row_objects=[],
        producer_code_identity={"fixture": True},
        publish_create_once=lambda _uri, _raw: {},
        read_exact=lambda _identity: b"fixture",
    )


def _validate_exact(
    result: Mapping[str, object],
    *,
    read_exact: Any | None = None,
) -> dict[str, object]:
    return publish_v2.validate_component_publication_against_candidate_authority_v2(
        result,
        repository_root=Path("/fixture"),
        read_exact=read_exact or (lambda _identity: b"fixture"),
        git_head=lambda _root: "1" * 40,
        git_blob=lambda _root, _commit, _path: b"fixture",
        git_status=lambda _root, _paths: b"",
    )


def _rehash_v1(receipt: dict[str, object]) -> None:
    receipt["component_publication_receipt_sha256"] = source.canonical_sha256({
        key: value
        for key, value in receipt.items()
        if key != "component_publication_receipt_sha256"
    })


def _rehash_v2(receipt: dict[str, object]) -> None:
    receipt["candidate_authority_component_publication_receipt_sha256"] = (
        source.canonical_sha256({
            key: value
            for key, value in receipt.items()
            if key
            != "candidate_authority_component_publication_receipt_sha256"
        })
    )


def _durable_result(
    monkeypatch: pytest.MonkeyPatch,
) -> dict[str, Any]:
    objects: dict[tuple[str, str], bytes] = {}
    generation = 10_000

    def put(body: object, uri: str) -> dict[str, object]:
        nonlocal generation
        generation += 1
        identity = _identity_for_body(
            body, uri=uri, generation=str(generation)
        )
        objects[(uri, str(identity["generation"]))] = source.canonical_json_bytes(
            body
        )
        return identity

    catalog_rows: list[dict[str, object]] = []
    candidate_rows: list[dict[str, object]] = []
    for ordinal in range(source.TASK_COUNT):
        catalog = {"fixture_catalog_ordinal": ordinal}
        catalog_identity = put(
            catalog, f"gs://durable/catalogs/{ordinal:02d}.json"
        )
        artifact = {"fixture_candidate_ordinal": ordinal}
        artifact_identity = put(
            artifact, f"gs://durable/candidates/{ordinal:02d}.json"
        )
        catalog_rows.append({"catalog_identity": catalog_identity})
        candidate_rows.append({
            "candidate_artifact": artifact,
            "candidate_artifact_identity": artifact_identity,
        })
    catalog_release_sha = _digest("durable-catalog-release")
    catalog_release = {
        "entries": catalog_rows,
        "release_sha256": catalog_release_sha,
    }
    catalog_release_identity = put(
        catalog_release, "gs://durable/catalog/catalog-release.json"
    )
    replay_sha = _digest("durable-replay")
    replay = {"replay_receipt_sha256": replay_sha}
    replay_identity = put(replay, "gs://durable/catalog/replay.json")

    prefix = (
        f"gs://{candidate_authority.OUTPUT_BUCKET}/"
        f"{candidate_authority.OUTPUT_NAMESPACE}/durable-run-01/"
    )
    candidate_sha = _digest("durable-candidate-release")
    candidate_release = {
        "entries": candidate_rows,
        "accepted_candidate_release_sha256": candidate_sha,
    }
    candidate_identity = put(
        candidate_release,
        f"{prefix}{candidate_authority.CANDIDATE_RELEASE_FILENAME}",
    )
    root_identity = _identity(
        f"{prefix}{candidate_authority.ROOT_FILENAME}", "durable-root"
    )
    root_sha = _digest("durable-root-internal")
    root = {
        "target_uri": root_identity["uri"],
        "candidate_authority_release_sha256": root_sha,
        "candidate_release_identity": candidate_identity,
        "candidate_release_sha256": candidate_sha,
        "catalog_replay_receipt_identity": replay_identity,
        "catalog_replay_receipt_sha256": replay_sha,
        "candidate_population_authority": True,
        "exact_occurrence_provenance_authority": True,
        "authoritative_reopen_required": True,
        "structure_only_validation_authority": False,
        "complete": True,
    }
    reopened = candidate_authority.ReopenedFixedG0CandidateAuthorityV1(
        root=root,
        root_identity=root_identity,
        authority_bundle={
            "panel_derivation_receipt": {
                "catalog_replay_receipt_identity": replay_identity,
                "catalog_replay_receipt_sha256": replay_sha,
                "catalog_release_identity": catalog_release_identity,
                "catalog_release_sha256": catalog_release_sha,
                "candidate_release_sha256": candidate_sha,
            },
        },
        candidate_release=candidate_release,
        candidate_release_identity=candidate_identity,
    )
    monkeypatch.setattr(
        candidate_authority,
        "reopen_fixed_g0_candidate_authority_release_v1",
        lambda *_args, **_kwargs: reopened,
    )

    fixed_source = {"fixture": "fixed-source"}
    fixed_source_identity = put(
        fixed_source, "gs://durable/upstream/fixed-source.json"
    )
    provenance = [fixed_source_identity]
    packs: list[dict[str, object]] = []
    for ordinal in range(len(source.PACK_IDS)):
        rows = {"fixture_pack_ordinal": ordinal}
        rows_identity = put(
            rows, f"gs://durable/upstream/pack-{ordinal}/rows.json"
        )
        evidence = {"fixture_provenance_ordinal": ordinal}
        evidence_identity = put(
            evidence, f"gs://durable/upstream/pack-{ordinal}/evidence.json"
        )
        provenance.append(evidence_identity)
        packs.append({
            "exact_rows_identity": rows_identity,
            "warehouse_query_receipt_identity": evidence_identity,
            "frozen_artifact_manifest_identities": [],
        })
    upstream_release = {
        "fixed_source_root_identity": fixed_source_identity,
        "packs": packs,
    }
    upstream_identity = put(
        upstream_release, "gs://durable/upstream/upstream-release.json"
    )

    bundle_bodies: list[dict[str, object]] = []
    bundle_ids: list[dict[str, object]] = []
    receipt_bodies: list[dict[str, object]] = []
    receipt_ids: list[dict[str, object]] = []
    task_materialized: list[dict[str, object]] = []
    panel_entries: list[dict[str, object]] = []
    release_entries: list[dict[str, object]] = []
    family_registry = source.frozen_family_registry_v1()
    for ordinal in range(source.TASK_COUNT):
        schedule_rows = [{"fixture_schedule_ordinal": ordinal}]
        schedule_identity = put(
            schedule_rows,
            f"gs://durable/producer/{ordinal:02d}/schedule.json",
        )
        period_rows = [{"fixture_period_ordinal": ordinal}]
        period_identity = put(
            period_rows,
            f"gs://durable/producer/{ordinal:02d}/period.json",
        )
        support_rows = {
            "rows": [{"fixture_support_ordinal": ordinal}],
            "candidate_support_rows_sha256": _digest(f"support-{ordinal}"),
        }
        support_identity = put(
            support_rows,
            f"gs://durable/producer/{ordinal:02d}/candidate-support.json",
        )
        bundle = {
            "source_task_ordinal": ordinal,
            "fixture": "bundle",
            "target_spine": {
                "schedule_slice_identity": schedule_identity,
                "games": schedule_rows,
            },
            "source_slices": [{
                "exact_slice_identity": period_identity,
                "rows": period_rows,
            }],
            "family_registry": family_registry,
            "family_registry_sha256": family_registry[
                "family_registry_sha256"
            ],
        }
        bundle_identity = put(
            bundle, f"gs://durable/producer/{ordinal:02d}/bundle.json"
        )
        producer_receipt = {
            "source_task_ordinal": ordinal,
            "fixture": "producer-receipt",
            "slate": {"slate_id": f"durable-{ordinal:02d}"},
            "catalog_identity": catalog_rows[ordinal]["catalog_identity"],
            "support_preflight_passed": True,
            "family_registry": family_registry,
            "family_registry_sha256": family_registry[
                "family_registry_sha256"
            ],
            "target_or_later_deletion_proof": {
                "deletion_proof_sha256": _digest(f"deletion-{ordinal}")
            },
            "admission_support_census": {
                "candidate_support_rows_identity": support_identity,
                "candidate_support_rows": support_rows,
                "qualifying_candidate_count": 200,
            },
        }
        producer_receipt_identity = put(
            producer_receipt,
            f"gs://durable/producer/{ordinal:02d}/receipt.json",
        )
        bundle_bodies.append(bundle)
        bundle_ids.append(bundle_identity)
        receipt_bodies.append(producer_receipt)
        receipt_ids.append(producer_receipt_identity)
        release_entry = {
            "source_task_ordinal": ordinal,
            "slate": producer_receipt["slate"],
            "catalog_identity": producer_receipt["catalog_identity"],
            "input_bundle_identity": bundle_identity,
            "producer_receipt_identity": producer_receipt_identity,
            "support_preflight_passed": True,
            "qualifying_candidate_count": 200,
        }
        panel_entries.append({
            **release_entry,
            "deletion_proof_sha256": producer_receipt[
                "target_or_later_deletion_proof"
            ]["deletion_proof_sha256"],
        })
        release_entries.append(release_entry)
        task_materialized.extend([
            schedule_identity, period_identity, support_identity,
            bundle_identity, producer_receipt_identity,
        ])
    producer_release_sha = _digest("durable-producer-release")
    producer_release = {
        "entries": release_entries,
        "producer_release_sha256": producer_release_sha,
        "all_54_support_census": {"fixture": "support-census"},
        "all_54_support_census_sha256": _digest("all-54-support"),
        "family_registry": family_registry,
        "family_registry_sha256": family_registry[
            "family_registry_sha256"
        ],
    }
    producer_identity = put(
        producer_release, "gs://durable/producer/producer-release.json"
    )
    materialized = [*task_materialized, producer_identity]
    v1_receipt_body: dict[str, object] = {
        "schema_version": publish_v1.PUBLICATION_RECEIPT_SCHEMA,
        "producer_id": "durable-producer",
        "producer_release_id": "durable-release",
        "producer_namespace": "gs://durable/producer/",
        "source_task_count": source.TASK_COUNT,
        "fixed_g0_replay_receipt_identity": replay_identity,
        "catalog_release_identity": catalog_release_identity,
        "accepted_candidate_release_identity": candidate_identity,
        "upstream_source_release_identity": upstream_identity,
        "upstream_provenance_identities": provenance,
        "upstream_provenance_identity_manifest_sha256": canonical_sha256(
            provenance
        ),
        "materialized_object_count": len(materialized),
        "materialized_object_identities": materialized,
        "materialized_object_identity_manifest_sha256": canonical_sha256(
            materialized
        ),
        "producer_release_identity": producer_identity,
        "producer_release_object_sha256": producer_identity["sha256"],
        "producer_release_sha256": producer_release_sha,
        "all_inputs_exact_reopened_before_publication": True,
        "all_outputs_exact_reopened": True,
        "producer_release_published_last": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    v1_receipt_body["component_publication_receipt_sha256"] = canonical_sha256(
        v1_receipt_body
    )
    v1_receipt = publish_v1.validate_component_publication_receipt_v1(
        v1_receipt_body
    )
    panel_body: dict[str, object] = {
        "schema_version": publish_v2.producer.OFFLINE_PANEL_RESULT_SCHEMA,
        "producer_id": "durable-producer",
        "producer_namespace": "gs://durable/producer/",
        "fixed_g0_replay_receipt": replay,
        "fixed_g0_replay_receipt_identity": replay_identity,
        "catalog_release_identity": catalog_release_identity,
        "accepted_candidate_release": candidate_release,
        "accepted_candidate_release_identity": candidate_identity,
        "upstream_source_release_identity": upstream_identity,
        "producer_code_identity": {"fixture": "code"},
        "family_registry": family_registry,
        "family_registry_sha256": family_registry[
            "family_registry_sha256"
        ],
        "task_count": source.TASK_COUNT,
        "entries": panel_entries,
        "entry_manifest_sha256": canonical_sha256(panel_entries),
        "input_bundles": bundle_bodies,
        "input_bundle_identities": bundle_ids,
        "input_bundle_identity_manifest_sha256": canonical_sha256(bundle_ids),
        "producer_receipts": receipt_bodies,
        "producer_receipt_identities": receipt_ids,
        "producer_receipt_identity_manifest_sha256": canonical_sha256(
            receipt_ids
        ),
        "all_54_support_census": producer_release["all_54_support_census"],
        "all_54_support_census_sha256": producer_release[
            "all_54_support_census_sha256"
        ],
        "producer_release": producer_release,
        "producer_release_identity": producer_identity,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    panel_body["offline_panel_result_sha256"] = canonical_sha256(panel_body)
    binding = {
        "candidate_authority_root_identity": root_identity,
        "candidate_authority_root_sha256": root_sha,
        "accepted_candidate_release_identity": candidate_identity,
        "accepted_candidate_release_sha256": candidate_sha,
        "catalog_replay_receipt_identity": replay_identity,
        "catalog_replay_receipt_sha256": replay_sha,
        "catalog_release_identity": catalog_release_identity,
        "catalog_release_sha256": catalog_release_sha,
    }
    wrapper = publish_v2._build_receipt(
        binding=binding, v1_receipt=v1_receipt
    )
    result = {
        "publication_receipt": wrapper,
        "component_publication_result": {
            "publication_receipt": deepcopy(v1_receipt),
            "offline_panel": panel_body,
        },
    }

    def read_exact(identity: Mapping[str, object]) -> bytes:
        return objects[(str(identity["uri"]), str(identity["generation"]))]

    deep_replay_calls: list[object] = []

    def record_deep_replay(value: object, **_kwargs: object) -> object:
        deep_replay_calls.append(value)
        return value

    monkeypatch.setattr(source, "validate_producer_release_v1", record_deep_replay)
    return {
        "result": result,
        "objects": objects,
        "read_exact": read_exact,
        "reopened": reopened,
        "deep_replay_calls": deep_replay_calls,
    }


def test_public_api_accepts_only_candidate_root_and_delegates_derived_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    result = _publish(fixture)
    receipt = result["publication_receipt"]
    parameters = inspect.signature(
        publish_v2.publish_all_54_component_release_candidate_authority_v2
    ).parameters
    assert "candidate_authority_root_identity" in parameters
    assert "accepted_candidate_release" not in parameters
    assert "accepted_candidate_release_identity" not in parameters
    assert fixture["reopen_calls"] == [fixture["root_identity"]]
    assert fixture["v1_calls"][0]["accepted_candidate_release"] == fixture[
        "candidate_release"
    ]
    assert fixture["v1_calls"][0][
        "accepted_candidate_release_identity"
    ] == fixture["candidate_identity"]
    assert receipt["candidate_authority_root_identity"] == fixture[
        "root_identity"
    ]
    assert receipt["candidate_authority_exact_reopened"] is True
    assert receipt["exact_occurrence_provenance_binding_verified"] is True
    assert receipt["candidate_authority_structure_only_authority"] is False
    assert receipt["legacy_v1_publication_path_authoritative"] is False
    assert receipt["authoritative_consumer_requires_full_v2_result"] is True
    assert (
        publish_v2.validate_component_publication_candidate_authority_receipt_v2(
            receipt
        )
        == receipt
    )
    monkeypatch.setattr(
        publish_v2,
        "_durable_validate_full_result",
        lambda **_kwargs: result["component_publication_result"][
            "offline_panel"
        ],
    )
    assert _validate_exact(result) == result
    assert fixture["reopen_calls"] == [
        fixture["root_identity"],
        fixture["root_identity"],
    ]


@pytest.mark.parametrize("mutation", ["identity", "sha256"])
def test_catalog_replay_mismatch_fails_before_v1_publication(
    monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    fixture = _fixture(monkeypatch)
    if mutation == "identity":
        changed_identity = _identity(
            "gs://fixture-catalog/alternate-replay.json", "alternate-replay"
        )
        fixture["root"]["catalog_replay_receipt_identity"] = changed_identity
        fixture["reopened"].authority_bundle["panel_derivation_receipt"][
            "catalog_replay_receipt_identity"
        ] = changed_identity
    else:
        changed_sha = _digest(
            "alternate-replay-internal"
        )
        fixture["root"]["catalog_replay_receipt_sha256"] = changed_sha
        fixture["reopened"].authority_bundle["panel_derivation_receipt"][
            "catalog_replay_receipt_sha256"
        ] = changed_sha
    mismatch_field = "identity" if mutation == "identity" else "SHA"
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match=rf"catalog replay receipt {mismatch_field} differs",
    ):
        _publish(fixture)
    assert fixture["v1_calls"] == []


def test_reopen_failure_never_calls_v1_publication(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)

    def fail_reopen(*_args: object, **_kwargs: object) -> object:
        raise ValueError("missing generation")

    monkeypatch.setattr(
        candidate_authority,
        "reopen_fixed_g0_candidate_authority_release_v1",
        fail_reopen,
    )
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match="exact reopen failed",
    ):
        _publish(fixture)
    assert fixture["v1_calls"] == []


def test_authoritative_validator_rejects_receipt_only_and_one_object_panel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    result = _publish(fixture)
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match="result fields differ",
    ):
        _validate_exact(result["publication_receipt"])
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match="offline panel fields differ",
    ):
        _validate_exact(result)


def test_v1_result_cannot_substitute_another_candidate_release(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    original = publish_v1.publish_all_54_component_release_v1

    def substitute(**kwargs: object) -> dict[str, object]:
        result = original(**kwargs)
        alternate = _identity(
            "gs://attacker/candidate-release.json", "alternate-candidate"
        )
        receipt = result["publication_receipt"]
        receipt["accepted_candidate_release_identity"] = alternate
        _rehash_v1(receipt)
        result["offline_panel"]["accepted_candidate_release_identity"] = alternate
        return result

    monkeypatch.setattr(
        publish_v1, "publish_all_54_component_release_v1", substitute
    )
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match="differs from candidate authority",
    ):
        _publish(fixture)


def test_coherent_structure_only_root_substitution_fails_exact_validation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture(monkeypatch)
    result = deepcopy(_publish(fixture))
    receipt = result["publication_receipt"]
    alternate_prefix = (
        f"gs://{candidate_authority.OUTPUT_BUCKET}/"
        f"{candidate_authority.OUTPUT_NAMESPACE}/alternate-run-88/"
    )
    alternate_root = _identity(
        f"{alternate_prefix}{candidate_authority.ROOT_FILENAME}",
        "alternate-root",
    )
    alternate_candidate = _identity(
        f"{alternate_prefix}{candidate_authority.CANDIDATE_RELEASE_FILENAME}",
        "alternate-candidate",
    )
    receipt["candidate_authority_root_identity"] = alternate_root
    receipt["accepted_candidate_release_identity"] = alternate_candidate
    v1_receipt = receipt["component_publication_receipt"]
    v1_receipt["accepted_candidate_release_identity"] = alternate_candidate
    _rehash_v1(v1_receipt)
    receipt["component_publication_receipt_sha256"] = v1_receipt[
        "component_publication_receipt_sha256"
    ]
    _rehash_v2(receipt)
    assert (
        publish_v2.validate_component_publication_candidate_authority_receipt_v2(
            receipt
        )
        == receipt
    )
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match="root binding differs",
    ):
        _validate_exact(result)


def test_full_durable_result_exact_reopens_complete_v1_manifest(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _durable_result(monkeypatch)
    assert _validate_exact(
        fixture["result"], read_exact=fixture["read_exact"]
    ) == fixture["result"]
    assert fixture["deep_replay_calls"] == [
        fixture["result"]["component_publication_result"]["offline_panel"][
            "producer_release"
        ]
    ]


def test_full_durable_result_rejects_coherent_materialized_manifest_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _durable_result(monkeypatch)
    result = deepcopy(fixture["result"])
    alternate = {"fixture": "attacker-materialized-object"}
    alternate_identity = _identity_for_body(
        alternate,
        uri="gs://durable/producer/attacker.json",
        generation="999999",
    )
    fixture["objects"][(
        str(alternate_identity["uri"]),
        str(alternate_identity["generation"]),
    )] = source.canonical_json_bytes(alternate)
    nested = result["component_publication_result"]["publication_receipt"]
    nested["materialized_object_identities"][0] = alternate_identity
    nested["materialized_object_identity_manifest_sha256"] = canonical_sha256(
        nested["materialized_object_identities"]
    )
    _rehash_v1(nested)
    wrapper = result["publication_receipt"]
    wrapper["component_publication_receipt"] = deepcopy(nested)
    wrapper["component_publication_receipt_sha256"] = nested[
        "component_publication_receipt_sha256"
    ]
    _rehash_v2(wrapper)
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match="complete nested leaf manifest|absent from materialized manifest",
    ):
        _validate_exact(result, read_exact=fixture["read_exact"])


def test_full_durable_result_rejects_coherent_producer_root_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _durable_result(monkeypatch)
    result = deepcopy(fixture["result"])
    alternate = {
        "entries": [],
        "producer_release_sha256": _digest("alternate-producer-release"),
    }
    alternate_identity = _identity_for_body(
        alternate,
        uri="gs://durable/producer/alternate-release.json",
        generation="999998",
    )
    fixture["objects"][(
        str(alternate_identity["uri"]),
        str(alternate_identity["generation"]),
    )] = source.canonical_json_bytes(alternate)
    nested = result["component_publication_result"]["publication_receipt"]
    nested["materialized_object_identities"][-1] = alternate_identity
    nested["materialized_object_identity_manifest_sha256"] = canonical_sha256(
        nested["materialized_object_identities"]
    )
    nested["producer_release_identity"] = alternate_identity
    nested["producer_release_object_sha256"] = alternate_identity["sha256"]
    nested["producer_release_sha256"] = alternate["producer_release_sha256"]
    _rehash_v1(nested)
    wrapper = result["publication_receipt"]
    wrapper["component_publication_receipt"] = deepcopy(nested)
    wrapper["component_publication_receipt_sha256"] = nested[
        "component_publication_receipt_sha256"
    ]
    wrapper["producer_release_identity"] = alternate_identity
    wrapper["producer_release_sha256"] = alternate["producer_release_sha256"]
    _rehash_v2(wrapper)
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match="complete nested leaf manifest|producer root differs",
    ):
        _validate_exact(result, read_exact=fixture["read_exact"])


def test_full_durable_result_rejects_nested_leaf_body_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _durable_result(monkeypatch)
    result = deepcopy(fixture["result"])
    panel = result["component_publication_result"]["offline_panel"]
    panel["input_bundles"][0]["target_spine"]["games"] = [
        {"fixture_schedule_ordinal": "attacker"}
    ]
    panel["offline_panel_result_sha256"] = canonical_sha256({
        key: value
        for key, value in panel.items()
        if key != "offline_panel_result_sha256"
    })
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match=r"input bundle\[0\] bytes differ|nested materialized leaf bytes differ",
    ):
        _validate_exact(result, read_exact=fixture["read_exact"])


def test_full_durable_result_rejects_panel_upstream_root_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _durable_result(monkeypatch)
    result = deepcopy(fixture["result"])
    panel = result["component_publication_result"]["offline_panel"]
    panel["upstream_source_release_identity"] = _identity(
        "gs://durable/upstream/alternate-release.json", "alternate-upstream"
    )
    panel["offline_panel_result_sha256"] = canonical_sha256({
        key: value
        for key, value in panel.items()
        if key != "offline_panel_result_sha256"
    })
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match="upstream source root differs",
    ):
        _validate_exact(result, read_exact=fixture["read_exact"])


def test_full_durable_result_rejects_v1_catalog_root_swap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _durable_result(monkeypatch)
    result = deepcopy(fixture["result"])
    alternate = _identity(
        "gs://durable/catalog/alternate-release.json", "alternate-catalog"
    )
    nested = result["component_publication_result"]["publication_receipt"]
    nested["catalog_release_identity"] = alternate
    _rehash_v1(nested)
    wrapper = result["publication_receipt"]
    wrapper["component_publication_receipt"] = deepcopy(nested)
    wrapper["component_publication_receipt_sha256"] = nested[
        "component_publication_receipt_sha256"
    ]
    _rehash_v2(wrapper)
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error,
        match="fixed law differs|catalog release differs",
    ):
        _validate_exact(result, read_exact=fixture["read_exact"])


@pytest.mark.parametrize(
    "field",
    ["fixed_g0", "catalog", "candidate", "producer", "entry", "support"],
)
def test_full_durable_result_rejects_offline_panel_field_substitution(
    monkeypatch: pytest.MonkeyPatch, field: str,
) -> None:
    fixture = _durable_result(monkeypatch)
    result = deepcopy(fixture["result"])
    panel = result["component_publication_result"]["offline_panel"]
    alternate = _identity(
        f"gs://durable/attacker/{field}.json", f"attacker-{field}"
    )
    if field == "fixed_g0":
        panel["fixed_g0_replay_receipt_identity"] = alternate
    elif field == "catalog":
        panel["catalog_release_identity"] = alternate
    elif field == "candidate":
        panel["accepted_candidate_release_identity"] = alternate
    elif field == "producer":
        panel["producer_id"] = "attacker-producer"
    elif field == "entry":
        panel["entries"][0]["input_bundle_identity"] = alternate
        panel["entry_manifest_sha256"] = canonical_sha256(panel["entries"])
    else:
        panel["all_54_support_census"] = {"fixture": "attacker-support"}
    panel["offline_panel_result_sha256"] = canonical_sha256({
        key: value
        for key, value in panel.items()
        if key != "offline_panel_result_sha256"
    })
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error
    ):
        _validate_exact(result, read_exact=fixture["read_exact"])


@pytest.mark.parametrize(
    "field",
    [
        "slate", "catalog_identity", "support_preflight_passed",
        "qualifying_candidate_count", "deletion_proof_sha256",
    ],
)
def test_full_durable_result_rejects_each_panel_entry_field_substitution(
    monkeypatch: pytest.MonkeyPatch, field: str,
) -> None:
    fixture = _durable_result(monkeypatch)
    result = deepcopy(fixture["result"])
    panel = result["component_publication_result"]["offline_panel"]
    entry = panel["entries"][0]
    mutations = {
        "slate": {"slate_id": "attacker-slate"},
        "catalog_identity": _identity(
            "gs://durable/attacker/catalog.json", "entry-catalog"
        ),
        "support_preflight_passed": False,
        "qualifying_candidate_count": 199,
        "deletion_proof_sha256": _digest("attacker-deletion"),
    }
    entry[field] = mutations[field]
    panel["entry_manifest_sha256"] = canonical_sha256(panel["entries"])
    panel["offline_panel_result_sha256"] = canonical_sha256({
        key: value
        for key, value in panel.items()
        if key != "offline_panel_result_sha256"
    })
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error
    ):
        _validate_exact(result, read_exact=fixture["read_exact"])


def test_full_durable_result_rejects_family_registry_substitution(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _durable_result(monkeypatch)
    result = deepcopy(fixture["result"])
    panel = result["component_publication_result"]["offline_panel"]
    panel["family_registry"] = deepcopy(panel["family_registry"])
    panel["family_registry"]["fixture_attacker"] = True
    panel["family_registry_sha256"] = canonical_sha256(
        panel["family_registry"]
    )
    panel["offline_panel_result_sha256"] = canonical_sha256({
        key: value
        for key, value in panel.items()
        if key != "offline_panel_result_sha256"
    })
    with pytest.raises(
        publish_v2.CorpusR6MatchupComponentPublicationCandidateAuthorityV2Error
    ):
        _validate_exact(result, read_exact=fixture["read_exact"])
