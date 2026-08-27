from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
from typing import Any, Mapping

import pytest

from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as release
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


TERMINAL_NAMESPACE = "gs://fixture-bucket/r6-matchup-source-v1/"
PRODUCER_NAMESPACE = "gs://fixture-bucket/r6-matchup-producer-v1/"


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _raw(value: object) -> bytes:
    return source.canonical_json_bytes(value)


def _identity(
    value: object, *, uri: str, generation: int,
) -> dict[str, object]:
    raw = _raw(value)
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _opaque_identity(label: str, *, generation: int) -> dict[str, object]:
    return _identity(
        {"fixture": label},
        uri=f"gs://fixture-bucket/predecessors/{label}.json",
        generation=generation,
    )


def _policy(true_fields: frozenset[str] = frozenset()) -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{
            field: field in true_fields for field in source.FALSE_AUTHORITY_FIELDS
        },
    }


def _rehash(value: Mapping[str, object], field: str) -> dict[str, object]:
    result = deepcopy(dict(value))
    result.pop(field, None)
    result[field] = source.canonical_sha256(result)
    return result


class _Store:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.heads: dict[str, dict[str, object]] = {}
        self.events: list[tuple[str, str]] = []
        self.next_generation = 700_000

    def seed(self, body: object, identity: Mapping[str, object]) -> None:
        normalized = source.normalize_object_identity_v2(identity, label="seed")
        raw = _raw(body)
        assert normalized["sha256"] == sha256(raw).hexdigest()
        assert normalized["bytes"] == len(raw)
        key = (str(normalized["uri"]), str(normalized["generation"]))
        self.objects[key] = raw
        self.heads[str(normalized["uri"])] = normalized

    def read(self, identity: Mapping[str, object]) -> bytes:
        normalized = source.normalize_object_identity_v2(identity, label="read")
        uri = str(normalized["uri"])
        self.events.append(("read", uri))
        return self.objects[(uri, str(normalized["generation"]))]

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]:
        self.events.append(("publish", uri))
        retained = self.heads.get(uri)
        if retained is not None:
            retained_raw = self.objects[(uri, str(retained["generation"]))]
            if retained_raw != raw:
                raise ValueError("different create-once bytes")
            return retained
        self.next_generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.next_generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.objects[(uri, str(identity["generation"]))] = raw
        self.heads[uri] = identity
        return identity


def _capture_plan() -> dict[str, object]:
    return {
        "commit_sha": "a" * 40,
        "relative_path": (
            "reports/corpus-r6-matchup-runs/fixture/capture-plan-lock.json"
        ),
        "sha256": "b" * 64,
        "bytes": 1234,
        "capture_plan_sha256": "c" * 64,
    }


def _operator_code() -> dict[str, str]:
    return {
        "source_commit_sha": "d" * 40,
        "module_path": release.OPERATOR_MODULE_PATH,
        "module_sha256": "e" * 64,
    }


def _producer_release() -> tuple[dict[str, object], dict[str, object]]:
    entries: list[dict[str, object]] = []
    census_receipts: list[dict[str, object]] = []
    generation = 10_000
    for ordinal in range(source.TASK_COUNT):
        slate = catalog_v1.expected_slate_for_source_task(ordinal)
        lane = catalog_v1.expected_lane_for_source_task(ordinal)
        catalog_identity = _opaque_identity(
            f"catalog-{ordinal:02d}", generation=generation
        )
        receipt_identity = _opaque_identity(
            f"producer-receipt-{ordinal:02d}", generation=generation + 1
        )
        bundle_identity = _opaque_identity(
            f"input-bundle-{ordinal:02d}", generation=generation + 2
        )
        candidate_identity = _opaque_identity(
            f"candidate-{ordinal:02d}", generation=generation + 3
        )
        generation += 4
        task_binding = {
            "source_task_ordinal": ordinal,
            "task_id": catalog_v1.task_id_for_source_task(ordinal),
            "slate": slate,
            "lane_id": lane["lane_id"],
            "lane_ordinal": lane["lane_ordinal"],
            "task_ordinal": lane["task_ordinal"],
            "accepted_slate_membership_sha256": _digest(
                f"membership-{ordinal}"
            ),
            "source_task_authority_sha256": _digest(
                f"task-authority-{ordinal}"
            ),
            "catalog_identity": catalog_identity,
            "source_catalog_sha256": _digest(f"catalog-rows-{ordinal}"),
            "player_count": 9,
            "ordered_player_ids_sha256": _digest(f"players-{ordinal}"),
        }
        entries.append({
            "source_task_ordinal": ordinal,
            "task_binding": task_binding,
            "slate": slate,
            "lock_time_utc": "2023-09-10T17:00:00Z",
            "catalog_identity": catalog_identity,
            "producer_receipt_identity": receipt_identity,
            "input_bundle_identity": bundle_identity,
            "candidate_artifact_identity": candidate_identity,
            "ordered_candidate_ids_sha256": _digest(
                f"ordered-candidates-{ordinal}"
            ),
            "qualifying_candidate_count": source.ENTRY_BUDGET,
            "qualifying_candidate_ids_sha256": _digest(
                f"qualifying-candidates-{ordinal}"
            ),
            "role_entry_manifest_sha256": _digest(f"roles-{ordinal}"),
            "support_census_sha256": _digest(f"support-{ordinal}"),
            "capture_output_prefix": (
                f"{PRODUCER_NAMESPACE}source-task-{ordinal:02d}-"
                f"{slate['slate_id']}/"
            ),
            "support_preflight_passed": True,
        })
        census_receipts.append({
            "source_task_ordinal": ordinal,
            "slate": slate,
            "qb_depth_census": {"fixture": ordinal},
            "component_support_census": [],
            "admission_support_census": {"fixture": ordinal},
            "target_or_later_deletion_proof": {
                "target_or_later_deletion_invariant": True,
            },
            "support_preflight_passed": True,
        })
    census = source.build_all_54_support_census_v1(census_receipts)
    body: dict[str, object] = {
        "schema_version": source.PRODUCER_RELEASE_SCHEMA,
        "release_id": "fixture-producer-release",
        "producer_id": "fixture-producer",
        "publication_mode": source.PUBLICATION_MODE,
        "authority_boundary": source.AUTHORITY_BOUNDARY,
        "namespace": PRODUCER_NAMESPACE,
        "catalog_release_identity": _opaque_identity(
            "catalog-release", generation=20_001
        ),
        "catalog_replay_receipt_identity": _opaque_identity(
            "catalog-replay", generation=20_002
        ),
        "accepted_candidate_release_identity": _opaque_identity(
            "candidate-release", generation=20_003
        ),
        "upstream_source_release_identity": _opaque_identity(
            "upstream-release", generation=20_004
        ),
        "upstream_pack_manifest_sha256": _digest("upstream-pack-manifest"),
        "family_registry": source.frozen_family_registry_v1(),
        "family_registry_sha256": source.frozen_family_registry_v1()[
            "family_registry_sha256"
        ],
        "role_registry": source.frozen_role_registry_v2(),
        "role_registry_sha256": source.frozen_role_registry_v2()[
            "role_registry_sha256"
        ],
        "semantic_registry": source.frozen_semantic_registry_v2(),
        "semantic_registry_sha256": source.frozen_semantic_registry_v2()[
            "semantic_registry_sha256"
        ],
        "producer_code_identity": {
            "source_commit_sha": "f" * 40,
            "module_path": source.PRODUCER_MODULE_PATH,
            "module_sha256": "1" * 64,
        },
        "task_count": source.TASK_COUNT,
        "entries": entries,
        "entry_manifest_sha256": source.canonical_sha256(entries),
        "all_54_support_census": census,
        "all_54_support_census_sha256": census[
            "all_54_support_census_sha256"
        ],
        **_policy(),
    }
    body = _rehash(body, "producer_release_sha256")
    identity = _identity(
        body,
        uri=f"{PRODUCER_NAMESPACE}producer-release.json",
        generation=20_005,
    )
    return body, identity


def _fixture() -> dict[str, Any]:
    producer_root, producer_root_identity = _producer_release()
    entries = producer_root["entries"]
    assert isinstance(entries, list)
    exports: list[dict[str, object]] = []
    export_ids: list[dict[str, object]] = []
    captures: list[dict[str, object]] = []
    capture_ids: list[dict[str, object]] = []
    results: list[dict[str, object]] = []
    result_ids: list[dict[str, object]] = []
    for ordinal, entry_value in enumerate(entries):
        entry = dict(entry_value)
        slate = entry["slate"]
        assert isinstance(slate, Mapping)
        prefix = (
            f"{TERMINAL_NAMESPACE}source-task-{ordinal:02d}-"
            f"{slate['slate_id']}/"
        )
        export = _rehash({
            "schema_version": release.MATCHUP_SOURCE_EXPORT_SCHEMA,
            "source_task_ordinal": ordinal,
            "task_id": catalog_v1.task_id_for_source_task(ordinal),
            "slate": slate,
            "lock_time_utc": entry["lock_time_utc"],
            "evidence_class": source.EVIDENCE_CLASS,
            "authoritative_pit": False,
            "producer_release_identity": producer_root_identity,
            "producer_receipt_identity": entry["producer_receipt_identity"],
            "input_bundle_identity": entry["input_bundle_identity"],
            "catalog_identity": entry["catalog_identity"],
            "candidate_artifact_identity": entry[
                "candidate_artifact_identity"
            ],
            **_policy(frozenset({"authoritative_for_mechanics"})),
        }, "matchup_source_export_sha256")
        export_identity = _identity(
            export,
            uri=f"{prefix}matchup-source-export.json",
            generation=30_000 + ordinal,
        )
        capture = _rehash({
            "schema_version": release.MATCHUP_CAPTURE_RECEIPT_SCHEMA,
            "source_task_ordinal": ordinal,
            "task_id": catalog_v1.task_id_for_source_task(ordinal),
            "slate": slate,
            "lock_time_utc": entry["lock_time_utc"],
            "source_export_identity": export_identity,
            "source_export_sha256": export["matchup_source_export_sha256"],
            "producer_release_identity": producer_root_identity,
            "producer_receipt_identity": entry["producer_receipt_identity"],
            "input_bundle_identity": entry["input_bundle_identity"],
            "catalog_identity": entry["catalog_identity"],
            "candidate_artifact_identity": entry[
                "candidate_artifact_identity"
            ],
            "producer_receipt_exact_reopened": True,
            "input_bundle_exact_reopened": True,
            "catalog_exact_reopened": True,
            "source_export_exact_reopened": True,
            **_policy(frozenset({
                "authoritative_for_mechanics",
                "capture_mechanics_authority",
            })),
        }, "matchup_capture_receipt_sha256")
        capture_identity = _identity(
            capture,
            uri=f"{prefix}matchup-capture-receipt.json",
            generation=31_000 + ordinal,
        )
        result = _rehash({
            "schema_version": release.MATCHUP_OPERATOR_RESULT_SCHEMA,
            "source_task_ordinal": ordinal,
            "task_id": catalog_v1.task_id_for_source_task(ordinal),
            "slate": slate,
            "lock_time_utc": entry["lock_time_utc"],
            "capture_plan_binding": _capture_plan(),
            "operator_code_identity": _operator_code(),
            "output_prefix": prefix,
            "source_export_identity": export_identity,
            "capture_receipt_identity": capture_identity,
            "producer_release_identity": producer_root_identity,
            "producer_receipt_identity": entry["producer_receipt_identity"],
            "input_bundle_identity": entry["input_bundle_identity"],
            "catalog_identity": entry["catalog_identity"],
            "candidate_artifact_identity": entry[
                "candidate_artifact_identity"
            ],
            "publication_mode": source.PUBLICATION_MODE,
            "source_export_exact_reopened": True,
            "capture_receipt_exact_reopened": True,
            "operator_result_exact_reopened": True,
            **_policy(frozenset({
                "authoritative_for_mechanics",
                "capture_mechanics_authority",
                "source_execution_authority",
                "source_publication_authority",
            })),
        }, "matchup_operator_result_sha256")
        result_identity = _identity(
            result,
            uri=f"{prefix}matchup-operator-result.json",
            generation=32_000 + ordinal,
        )
        exports.append(export)
        export_ids.append(export_identity)
        captures.append(capture)
        capture_ids.append(capture_identity)
        results.append(result)
        result_ids.append(result_identity)
    return {
        "release_id": "fixture-terminal-release",
        "namespace": TERMINAL_NAMESPACE,
        "capture_plan_binding": _capture_plan(),
        "producer_release": producer_root,
        "producer_release_identity": producer_root_identity,
        "source_exports": exports,
        "source_export_identities": export_ids,
        "capture_receipts": captures,
        "capture_receipt_identities": capture_ids,
        "operator_results": results,
        "operator_result_identities": result_ids,
    }


def test_annotation_rows_retain_presence_and_nullable_observed_counts() -> None:
    components = source.family_components_v1()["receiver"]
    supported = set(components[:2])
    row = {
        "gsis_id": "p01",
        "family": "receiver",
        "position": "WR",
        "qb_depth1": None,
        "qb_depth_evidence_class": None,
        "raw_component_values": {
            component: 1.0 if component in supported else None
            for component in components
        },
        "component_observed_game_counts": {
            component: 4 if component in supported else None
            for component in components
        },
        "component_values": {
            component: 0.5 if component in supported else None
            for component in components
        },
        "component_support": {
            component: component in supported for component in components
        },
        "component_missingness_reasons": {
            component: None if component in supported else "source_unavailable"
            for component in components
        },
        "matchup_component_count": 2,
        "matchup_edge_score": 0.5,
        "annotation_row_present": True,
        "component_source_bounds": {component: [] for component in components},
    }
    assert release._normalize_annotations([row]) == [row]
    poisoned = deepcopy(row)
    poisoned["annotation_row_present"] = False
    with pytest.raises(
        release.CorpusR6MatchupSourceReleaseV1Error,
        match="edge support",
    ):
        release._normalize_annotations([poisoned])


def test_terminal_root_is_exact_54_ordinal_only_and_binds_producer_root() -> None:
    fixture = _fixture()
    root = release.build_matchup_source_release_v1(**fixture)
    assert release.validate_matchup_source_release_v1(root) == root
    assert root["task_count"] == source.TASK_COUNT
    assert [entry["source_task_ordinal"] for entry in root["entries"]] == list(
        range(source.TASK_COUNT)
    )
    assert all(
        entry["producer_release_identity"]
        == fixture["producer_release_identity"]
        for entry in root["entries"]
    )

    poisoned = deepcopy(root)
    poisoned["entries"][0]["producer_release_identity"] = _opaque_identity(
        "alternate-producer-release", generation=99_999
    )
    poisoned["entries"][0] = _rehash(
        poisoned["entries"][0], "matchup_source_member_sha256"
    )
    poisoned["entry_manifest_sha256"] = source.canonical_sha256(
        poisoned["entries"]
    )
    poisoned = _rehash(poisoned, "matchup_source_release_sha256")
    with pytest.raises(
        release.CorpusR6MatchupSourceReleaseV1Error,
        match="producer release differs from root",
    ):
        release.validate_matchup_source_release_v1(poisoned)


def test_terminal_root_rejects_operator_prefix_outside_release_namespace() -> None:
    fixture = _fixture()
    result = deepcopy(fixture["operator_results"][0])
    result["output_prefix"] = result["output_prefix"].replace(
        TERMINAL_NAMESPACE, "gs://fixture-bucket/alternate-source/"
    )
    result = _rehash(result, "matchup_operator_result_sha256")
    fixture["operator_results"][0] = result
    fixture["operator_result_identities"][0] = _identity(
        result,
        uri=fixture["operator_result_identities"][0]["uri"],
        generation=88_888,
    )
    with pytest.raises(
        release.CorpusR6MatchupSourceReleaseV1Error,
        match="fixed namespace law",
    ):
        release.build_matchup_source_release_v1(**fixture)


def test_selected_candidate_rosters_must_belong_to_selected_catalog() -> None:
    slate = catalog_v1.expected_slate_for_source_task(0)
    catalog = {
        "source_task_ordinal": 0,
        "task_id": catalog_v1.task_id_for_source_task(0),
        "slate": slate,
        "players": [{"id": f"p{ordinal:02d}"} for ordinal in range(1, 10)],
    }
    member = {"task_id": catalog["task_id"], "slate": slate}
    artifact = {
        "source_task_ordinal": 0,
        "rows": [{"player_ids": [f"p{ordinal:02d}" for ordinal in range(1, 10)]}],
    }
    release._validate_selected_candidate_catalog_binding(
        candidate_artifact=artifact,
        structural_catalog=catalog,
        member=member,
        ordinal=0,
    )
    artifact["rows"][0]["player_ids"][-1] = "outside-catalog"
    with pytest.raises(
        release.CorpusR6MatchupSourceReleaseV1Error,
        match="catalog task/universe",
    ):
        release._validate_selected_candidate_catalog_binding(
            candidate_artifact=artifact,
            structural_catalog=catalog,
            member=member,
            ordinal=0,
        )


def test_terminal_publication_deep_replays_all_members_then_publishes_only_root(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    store = _Store()
    store.seed(
        fixture["producer_release"], fixture["producer_release_identity"]
    )
    for ordinal, entry in enumerate(fixture["producer_release"]["entries"]):
        store.seed(
            {"fixture": f"catalog-{ordinal:02d}"},
            entry["catalog_identity"],
        )
    replayed: list[int] = []

    def deep_reopen(**values: object) -> dict[str, object]:
        ordinal = int(values["ordinal"])
        root = values["release"]
        reader = values["read_exact"]
        assert isinstance(root, Mapping)
        assert callable(reader)
        member = root["entries"][ordinal]
        release._parse_exact(
            member["catalog_identity"],
            read_exact=reader,
            label=f"deep catalog[{ordinal}]",
        )
        replayed.append(ordinal)
        return {}

    monkeypatch.setattr(
        release,
        "_reopen_validated_matchup_source_release_ordinal_v1",
        deep_reopen,
    )

    first = release.publish_matchup_source_release_root_last_v1(
        **fixture, publish_create_once=store.publish, read_exact=store.read
    )
    root_uri = f"{TERMINAL_NAMESPACE}matchup-source-release.json"
    publish_events = [event for event in store.events if event[0] == "publish"]
    assert publish_events == [("publish", root_uri)]
    publish_offset = store.events.index(("publish", root_uri))
    assert replayed == list(range(source.TASK_COUNT))
    assert publish_offset >= source.TASK_COUNT + 1
    assert store.events[-1] == ("read", root_uri)

    store.events.clear()
    replayed.clear()
    second = release.publish_matchup_source_release_root_last_v1(
        **fixture, publish_create_once=store.publish, read_exact=store.read
    )
    assert second == first
    assert replayed == list(range(source.TASK_COUNT))
    assert [event for event in store.events if event[0] == "publish"] == [
        ("publish", root_uri)
    ]


def test_late_missing_deep_dependency_prevents_root_create(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixture = _fixture()
    store = _Store()
    store.seed(
        fixture["producer_release"], fixture["producer_release_identity"]
    )
    entries = fixture["producer_release"]["entries"]
    for ordinal, entry in enumerate(entries[:-1]):
        store.seed(
            {"fixture": f"catalog-{ordinal:02d}"},
            entry["catalog_identity"],
        )
    attempted: list[int] = []

    def deep_reopen(**values: object) -> dict[str, object]:
        ordinal = int(values["ordinal"])
        root = values["release"]
        reader = values["read_exact"]
        assert isinstance(root, Mapping)
        assert callable(reader)
        attempted.append(ordinal)
        member = root["entries"][ordinal]
        release._parse_exact(
            member["catalog_identity"],
            read_exact=reader,
            label=f"deep catalog[{ordinal}]",
        )
        return {}

    monkeypatch.setattr(
        release,
        "_reopen_validated_matchup_source_release_ordinal_v1",
        deep_reopen,
    )
    with pytest.raises(
        release.CorpusR6MatchupSourceReleaseV1Error,
        match=r"deep catalog\[53\] exact reopen failed",
    ):
        release.publish_matchup_source_release_root_last_v1(
            **fixture,
            publish_create_once=store.publish,
            read_exact=store.read,
        )
    assert attempted == list(range(source.TASK_COUNT))
    assert all(event[0] != "publish" for event in store.events)


def test_ordinal_outside_fixed_lattice_fails_before_any_read() -> None:
    reads: list[Mapping[str, object]] = []

    def reader(identity: Mapping[str, object]) -> bytes:
        reads.append(identity)
        raise AssertionError("reader must not be called")

    with pytest.raises(
        release.CorpusR6MatchupSourceReleaseV1Error,
        match="must be in 0..53",
    ):
        release.reopen_matchup_source_release_ordinal_v1(
            release_identity=_opaque_identity("terminal-root", generation=77),
            source_task_ordinal=source.TASK_COUNT,
            read_exact=reader,
        )
    assert reads == []
