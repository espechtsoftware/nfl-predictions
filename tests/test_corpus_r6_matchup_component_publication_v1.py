from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any, Mapping

import pytest

from nfl_dfs.research import corpus_r6_matchup_component_producer_v1 as producer
from nfl_dfs.research import corpus_r6_matchup_component_publication_v1 as publish
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


def _raw(value: object) -> bytes:
    return source.canonical_json_bytes(value)


def _identity(value: object, *, uri: str, generation: int) -> dict[str, object]:
    raw = _raw(value)
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _Store:
    def __init__(self) -> None:
        self._objects: dict[tuple[str, str], bytes] = {}
        self._heads: dict[str, dict[str, object]] = {}
        self._next_generation = 900_000
        self.events: list[tuple[str, str]] = []

    def seed(self, body: object, identity: Mapping[str, object]) -> None:
        raw = _raw(body)
        normalized = source.normalize_object_identity_v2(identity, label="seed")
        assert normalized["sha256"] == sha256(raw).hexdigest()
        assert normalized["bytes"] == len(raw)
        self._objects[(str(normalized["uri"]), str(normalized["generation"]))] = raw
        self._heads[str(normalized["uri"])] = normalized

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]:
        self.events.append(("publish", uri))
        existing = self._heads.get(uri)
        if existing is not None:
            existing_raw = self._objects[(uri, str(existing["generation"]))]
            if existing_raw != raw:
                raise ValueError("different create-once bytes")
            return existing
        self._next_generation += 1
        identity = {
            "uri": uri,
            "generation": str(self._next_generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self._heads[uri] = identity
        self._objects[(uri, str(identity["generation"]))] = raw
        return identity

    def read(self, identity: Mapping[str, object]) -> bytes:
        normalized = source.normalize_object_identity_v2(identity, label="read")
        uri = str(normalized["uri"])
        self.events.append(("read", uri))
        return self._objects[(uri, str(normalized["generation"]))]


def _fixture() -> tuple[_Store, dict[str, Any]]:
    store = _Store()
    next_generation = 1

    def seeded(body: object, uri: str) -> dict[str, object]:
        nonlocal next_generation
        identity = _identity(body, uri=uri, generation=next_generation)
        next_generation += 1
        store.seed(body, identity)
        return identity

    replay = {"schema_version": "fixture-replay"}
    replay_identity = seeded(replay, "gs://inputs/fixed-g0/replay.json")

    catalog_entries: list[dict[str, object]] = []
    catalogs: list[dict[str, object]] = []
    for ordinal in range(source.TASK_COUNT):
        body = {"fixture_catalog_ordinal": ordinal}
        identity = seeded(
            body, f"gs://inputs/catalog/tasks/{ordinal:02d}/catalog.json"
        )
        catalogs.append(body)
        catalog_entries.append({"catalog_identity": identity})
    catalog_release = {"entries": catalog_entries}
    catalog_release_identity = seeded(
        catalog_release, "gs://inputs/catalog/catalog-release.json"
    )

    candidate_entries: list[dict[str, object]] = []
    for ordinal in range(source.TASK_COUNT):
        artifact = {"fixture_candidate_ordinal": ordinal}
        artifact_identity = seeded(
            artifact,
            f"gs://inputs/candidates/tasks/{ordinal:02d}/candidates.json",
        )
        candidate_entries.append({
            "candidate_artifact": artifact,
            "candidate_artifact_identity": artifact_identity,
        })
    candidate_release = {"entries": candidate_entries}
    candidate_release_identity = seeded(
        candidate_release, "gs://inputs/candidates/candidate-release.json"
    )

    fixed_source_root = {"fixture": "fixed-source-root"}
    fixed_source_root_identity = seeded(
        fixed_source_root, "gs://inputs/upstream/fixed-source-root.json"
    )
    upstream_packs: list[dict[str, object]] = []
    upstream_rows: list[dict[str, object]] = []
    for ordinal in range(len(source.PACK_IDS)):
        rows = {"fixture_pack_rows_ordinal": ordinal}
        rows_identity = seeded(
            rows, f"gs://inputs/upstream/packs/{ordinal:02d}/rows.json"
        )
        upstream_rows.append(rows)
        provenance = {"fixture": f"provenance-{ordinal}"}
        provenance_identity = seeded(
            provenance,
            f"gs://inputs/upstream/provenance/{ordinal:02d}.json",
        )
        if ordinal < 5:
            query = provenance_identity
            manifests: list[dict[str, object]] = []
        else:
            query = None
            manifests = [provenance_identity]
        upstream_packs.append({
            "exact_rows_identity": rows_identity,
            "warehouse_query_receipt_identity": query,
            "frozen_artifact_manifest_identities": manifests,
        })
    upstream_release = {
        "fixed_source_root_identity": fixed_source_root_identity,
        "packs": upstream_packs,
    }
    upstream_release_identity = seeded(
        upstream_release, "gs://inputs/upstream/upstream-release.json"
    )

    return store, {
        "producer_id": "fixture-producer",
        "producer_release_id": "fixture-release",
        "producer_namespace": "gs://outputs/r6-matchup/",
        "fixed_g0_replay_receipt": replay,
        "fixed_g0_replay_receipt_identity": replay_identity,
        "catalog_release": catalog_release,
        "catalog_release_identity": catalog_release_identity,
        "structural_catalogs": catalogs,
        "accepted_candidate_release": candidate_release,
        "accepted_candidate_release_identity": candidate_release_identity,
        "upstream_source_release": upstream_release,
        "upstream_source_release_identity": upstream_release_identity,
        "upstream_pack_row_objects": upstream_rows,
        "producer_code_identity": {
            "source_commit_sha": "a" * 40,
            "module_path": source.PRODUCER_MODULE_PATH,
            "module_sha256": "b" * 64,
        },
    }


def _fake_panel(
    kwargs: Mapping[str, object], *, root_first: bool = False,
) -> dict[str, object]:
    materialize = kwargs["body_materializer"]
    assert callable(materialize)
    namespace = str(kwargs["producer_namespace"])
    bundles: list[dict[str, object]] = []
    bundle_ids: list[Mapping[str, object]] = []
    receipts: list[dict[str, object]] = []
    receipt_ids: list[Mapping[str, object]] = []
    release = {
        "release_id": kwargs["producer_release_id"],
        "producer_release_sha256": "c" * 64,
    }
    root_uri = f"{namespace}producer-release.json"
    root_identity: Mapping[str, object] | None = None
    if root_first:
        root_identity = materialize(root_uri, _raw(release))
    for ordinal in range(source.TASK_COUNT):
        bundle = {"source_task_ordinal": ordinal, "kind": "bundle"}
        receipt = {"source_task_ordinal": ordinal, "kind": "receipt"}
        bundle_uri = (
            f"{namespace}source-task-{ordinal:02d}-fixture/producer/"
            "component-input-bundle.json"
        )
        receipt_uri = (
            f"{namespace}source-task-{ordinal:02d}-fixture/producer/"
            "component-producer-receipt.json"
        )
        bundle_ids.append(materialize(bundle_uri, _raw(bundle)))
        receipt_ids.append(materialize(receipt_uri, _raw(receipt)))
        bundles.append(bundle)
        receipts.append(receipt)
    if root_identity is None:
        root_identity = materialize(root_uri, _raw(release))
    return {
        "producer_id": kwargs["producer_id"],
        "producer_namespace": namespace,
        "fixed_g0_replay_receipt_identity": kwargs[
            "fixed_g0_replay_receipt_identity"
        ],
        "catalog_release_identity": kwargs["catalog_release_identity"],
        "accepted_candidate_release_identity": kwargs[
            "accepted_candidate_release_identity"
        ],
        "upstream_source_release_identity": kwargs[
            "upstream_source_release_identity"
        ],
        "input_bundles": bundles,
        "input_bundle_identities": bundle_ids,
        "producer_receipts": receipts,
        "producer_receipt_identities": receipt_ids,
        "producer_release": release,
        "producer_release_identity": root_identity,
    }


def test_body_materializer_requires_and_uses_exact_reopen() -> None:
    store = _Store()
    body = {"fixture": "leaf"}
    identity = producer._identity_for_body(
        body=body,
        uri="gs://outputs/leaf.json",
        identity_lookup=None,
        body_materializer=store.publish,
        read_exact=store.read,
        label="fixture leaf",
    )
    assert store.read(identity) == _raw(body)
    assert [event[0] for event in store.events[:2]] == ["publish", "read"]
    with pytest.raises(
        producer.CorpusR6MatchupComponentProducerV1Error,
        match="requires an exact reader",
    ):
        producer._identity_for_body(
            body=body,
            uri="gs://outputs/missing-reader.json",
            identity_lookup=None,
            body_materializer=store.publish,
            label="missing reader",
        )


def test_publication_preflights_inputs_then_publishes_root_last_and_resumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, kwargs = _fixture()
    monkeypatch.setattr(
        producer,
        "produce_all_54_component_panel_v1",
        lambda **values: _fake_panel(values),
    )
    first = publish.publish_all_54_component_release_v1(
        **kwargs, publish_create_once=store.publish, read_exact=store.read
    )
    receipt = first["publication_receipt"]
    assert receipt["source_task_count"] == source.TASK_COUNT
    assert receipt["materialized_object_count"] == source.TASK_COUNT * 2 + 1
    assert receipt["materialized_object_identities"][-1] == receipt[
        "producer_release_identity"
    ]
    first_publish = next(
        offset for offset, event in enumerate(store.events) if event[0] == "publish"
    )
    assert first_publish > source.TASK_COUNT * 2
    assert publish.validate_component_publication_receipt_v1(receipt) == receipt

    store.events.clear()
    second = publish.publish_all_54_component_release_v1(
        **kwargs, publish_create_once=store.publish, read_exact=store.read
    )
    assert second["publication_receipt"] == receipt


def test_input_reopen_failure_occurs_before_first_publish(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, kwargs = _fixture()
    poisoned = deepcopy(kwargs)
    poisoned["structural_catalogs"][17]["fixture_catalog_ordinal"] = 99
    monkeypatch.setattr(
        producer,
        "produce_all_54_component_panel_v1",
        lambda **values: _fake_panel(values),
    )
    with pytest.raises(
        publish.CorpusR6MatchupComponentPublicationV1Error,
        match=r"catalog\[17\].*content identity",
    ):
        publish.publish_all_54_component_release_v1(
            **poisoned, publish_create_once=store.publish, read_exact=store.read
        )
    assert all(event[0] != "publish" for event in store.events)


def test_root_before_leaf_publication_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, kwargs = _fixture()
    monkeypatch.setattr(
        producer,
        "produce_all_54_component_panel_v1",
        lambda **values: _fake_panel(values, root_first=True),
    )
    with pytest.raises(
        publish.CorpusR6MatchupComponentPublicationV1Error,
        match="root-last",
    ):
        publish.publish_all_54_component_release_v1(
            **kwargs, publish_create_once=store.publish, read_exact=store.read
        )


def test_receipt_rejects_reordered_root_and_authority_claim() -> None:
    store, kwargs = _fixture()
    provenance = [
        kwargs["upstream_source_release"]["fixed_source_root_identity"]
    ]
    root_body = {"release": "root"}
    root_identity = _identity(
        root_body, uri="gs://outputs/root.json", generation=5000
    )
    leaf_identity = _identity(
        {"leaf": 1}, uri="gs://outputs/leaf.json", generation=5001
    )
    body = {
        "schema_version": publish.PUBLICATION_RECEIPT_SCHEMA,
        "producer_id": "fixture-producer",
        "producer_release_id": "fixture-release",
        "producer_namespace": "gs://outputs/",
        "source_task_count": source.TASK_COUNT,
        "fixed_g0_replay_receipt_identity": kwargs[
            "fixed_g0_replay_receipt_identity"
        ],
        "catalog_release_identity": kwargs["catalog_release_identity"],
        "accepted_candidate_release_identity": kwargs[
            "accepted_candidate_release_identity"
        ],
        "upstream_source_release_identity": kwargs[
            "upstream_source_release_identity"
        ],
        "upstream_provenance_identities": provenance,
        "upstream_provenance_identity_manifest_sha256": source.canonical_sha256(
            provenance
        ),
        "materialized_object_count": 2,
        "materialized_object_identities": [leaf_identity, root_identity],
        "materialized_object_identity_manifest_sha256": source.canonical_sha256(
            [leaf_identity, root_identity]
        ),
        "producer_release_identity": root_identity,
        "producer_release_object_sha256": root_identity["sha256"],
        "producer_release_sha256": "c" * 64,
        "all_inputs_exact_reopened_before_publication": True,
        "all_outputs_exact_reopened": True,
        "producer_release_published_last": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }
    body["component_publication_receipt_sha256"] = source.canonical_sha256(body)
    assert publish.validate_component_publication_receipt_v1(body) == body

    reordered = deepcopy(body)
    reordered["materialized_object_identities"] = [root_identity, leaf_identity]
    reordered["materialized_object_identity_manifest_sha256"] = (
        source.canonical_sha256(reordered["materialized_object_identities"])
    )
    reordered.pop("component_publication_receipt_sha256")
    reordered["component_publication_receipt_sha256"] = source.canonical_sha256(
        reordered
    )
    with pytest.raises(
        publish.CorpusR6MatchupComponentPublicationV1Error,
        match="root/manifest law",
    ):
        publish.validate_component_publication_receipt_v1(reordered)

    authority = deepcopy(body)
    authority["publication_authority"] = True
    authority.pop("component_publication_receipt_sha256")
    authority["component_publication_receipt_sha256"] = source.canonical_sha256(
        authority
    )
    with pytest.raises(
        publish.CorpusR6MatchupComponentPublicationV1Error,
        match="forbidden authority",
    ):
        publish.validate_component_publication_receipt_v1(authority)
