from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as capture
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_paid_source_normalized_snapshot_v1 as snapshot
from tests import test_corpus_r6_matchup_seven_pack_capture_v1 as fixture


CODE = {
    "source_commit_sha": "a" * 40,
    "module_path": (
        "src/nfl_dfs/research/corpus_r6_paid_source_normalized_snapshot_v1.py"
    ),
    "module_sha256": "b" * 64,
}


class Store:
    def __init__(self) -> None:
        self.data: dict[str, tuple[dict[str, object], bytes]] = {}
        self.writes: list[str] = []
        self.generation = 100

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        self.writes.append(uri)
        prior = self.data.get(uri)
        if prior is not None:
            identity, existing = prior
            if existing != raw:
                raise RuntimeError("collision")
            return dict(identity)
        self.generation += 1
        identity = {
            "uri": uri,
            "generation": str(self.generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self.data[uri] = (identity, raw)
        return dict(identity)

    def read(self, identity: dict[str, object]) -> bytes:
        retained, raw = self.data[str(identity["uri"])]
        assert retained == dict(identity)
        return raw


def _metadata(relation: str) -> dict[str, object]:
    columns = [
        {
            "name": name,
            "data_type": "STRING",
            "is_nullable": "YES",
            "ordinal_position": ordinal,
        }
        for ordinal, name in enumerate(
            sorted(snapshot._REQUIRED_COLUMNS[relation]), start=1
        )
    ]
    return {
        "project_id": snapshot.PROJECT,
        "dataset_id": snapshot.DATASET,
        "relation_id": relation,
        "row_count": 100,
        "size_bytes": 1000,
        "modified_time_utc": "2026-08-30T12:00:00Z",
        "columns": columns,
    }


def _query_result(spec: dict[str, object]) -> dict[str, object]:
    records = [
        {
            "record_kind": "row",
            "slice_kind": slice_kind,
            "row_json": json.dumps(
                fixture._row(str(spec["pack_id"]), str(slice_kind), suffix=str(slice_kind)),
                sort_keys=True,
                separators=(",", ":"),
            ),
        }
        for slice_kind in spec["slice_kinds"]
    ]
    records.extend({
        "record_kind": "relation-metadata",
        "slice_kind": relation,
        "row_json": json.dumps(
            _metadata(str(relation)), sort_keys=True, separators=(",", ":")
        ),
    } for relation in spec["input_relations"])
    return {
        "job_metadata": {
            "project_id": spec["project_id"],
            "location": spec["location"],
            "job_id": spec["job_id"],
            "query_sha256": spec["query_sha256"],
            "state": "DONE",
            "error_result": None,
            "cache_hit": False,
            "total_bytes_processed": 1234,
            "created_utc": "2026-08-30T12:00:01Z",
            "started_utc": "2026-08-30T12:00:02Z",
            "ended_utc": "2026-08-30T12:00:03Z",
        },
        "result_rows": records,
    }


def _request() -> dict[str, object]:
    return snapshot.build_snapshot_request_v1(
        run_id="paid-source-snapshot-fixture-v1",
        snapshot_at_utc="2026-08-30T12:00:00Z",
        projection_code_identity=CODE,
    )


def _task0(request: dict[str, object]) -> dict[str, object]:
    return snapshot.run_normalized_snapshot_task0_v1(
        request, query_warehouse=lambda spec: _query_result(dict(spec))
    )


def test_request_freezes_two_time_travel_queries_and_exact_inventory() -> None:
    request = _request()
    assert snapshot.validate_snapshot_request_v1(request) == request
    assert request["query_count"] == 2
    assert request["output_object_count"] == 13
    assert request["evidence_class"] == "retrospective-prior-period-reconstruction"
    assert request["authoritative_pit"] is False
    assert request["uses_realized_outcomes"] is False
    assert request["automatic_policy_promotion"] is False
    assert len(request["output_inventory"]["nonterminal_uris"]) == 12
    for spec in request["query_specs"]:
        assert "FOR SYSTEM_TIME AS OF" in spec["canonical_query"]
        assert "2026-08-30T12:00:00Z" in spec["canonical_query"]
        assert spec["use_query_cache"] is False
        assert "realized" not in spec["canonical_query"].lower()
        assert "contest" not in spec["canonical_query"].lower()


def test_publish_creates_compatible_manifests_and_root_last() -> None:
    request = _request()
    task0 = _task0(request)
    assert snapshot.validate_normalized_snapshot_task0_v1(
        task0, request_value=request
    ) == task0
    assert task0["publication_count"] == 0
    store = Store()
    seen_specs: list[str] = []

    def query(spec: dict[str, object]) -> dict[str, object]:
        seen_specs.append(str(spec["pack_id"]))
        return _query_result(spec)

    result = snapshot.publish_normalized_snapshot_v1(
        request,
        task0_receipt_value=task0,
        query_warehouse=query,
        publish_create_once=store.publish,
        read_exact=store.read,
    )
    assert seen_specs == list(capture.ARTIFACT_PACK_IDS)
    assert len(store.writes) == 13
    assert store.writes[-1] == request["output_inventory"]["terminal_uri"]
    assert result["complete"] is True
    assert result["uses_realized_outcomes"] is False
    assert result["independent_reopen"][
        "both_manifests_and_all_exact_predecessors_reopened"
    ] is True
    for pack_id, identity in result["artifact_manifest_identities"].items():
        manifest = json.loads(store.read(identity))
        assert capture.validate_artifact_pack_manifest_structure_v1(
            manifest, expected_pack_id=pack_id
        ) == manifest
        assert manifest["source_kind"] == "frozen-artifact-projection"
        assert len(manifest["source_manifest_identities"]) == 1
        assert len(manifest["source_artifact_identities"]) == 1


def test_provider_job_and_relation_metadata_fail_closed_before_writes() -> None:
    request = _request()
    task0 = _task0(request)
    store = Store()

    def bad_job(spec: dict[str, object]) -> dict[str, object]:
        result = _query_result(spec)
        result["job_metadata"]["cache_hit"] = True
        return result

    with pytest.raises(
        snapshot.CorpusR6PaidSourceNormalizedSnapshotV1Error,
        match="BigQuery job differs",
    ):
        snapshot.publish_normalized_snapshot_v1(
            request,
            task0_receipt_value=task0,
            query_warehouse=bad_job,
            publish_create_once=store.publish,
            read_exact=store.read,
        )
    assert store.writes == []

    def changed_fp_rerun(spec: dict[str, object]) -> dict[str, object]:
        result = _query_result(spec)
        if spec["ordinal"] == 0:
            first = next(
                row for row in result["result_rows"]
                if row["record_kind"] == "row"
                and row["slice_kind"] == "fp-route-share"
            )
            body = json.loads(first["row_json"])
            body["route_share"] = float(body["route_share"]) + 0.125
            first["row_json"] = json.dumps(
                body, sort_keys=True, separators=(",", ":")
            )
        return result

    with pytest.raises(
        snapshot.CorpusR6PaidSourceNormalizedSnapshotV1Error,
        match="FP rerun differs from its task0 gate",
    ):
        snapshot.publish_normalized_snapshot_v1(
            request,
            task0_receipt_value=task0,
            query_warehouse=changed_fp_rerun,
            publish_create_once=store.publish,
            read_exact=store.read,
        )
    assert store.writes == []

    def future_metadata(spec: dict[str, object]) -> dict[str, object]:
        result = _query_result(spec)
        relation_record = next(
            row for row in result["result_rows"]
            if row["record_kind"] == "relation-metadata"
        )
        body = json.loads(relation_record["row_json"])
        body["modified_time_utc"] = "2026-08-30T12:00:01Z"
        relation_record["row_json"] = json.dumps(
            body, sort_keys=True, separators=(",", ":")
        )
        return result

    with pytest.raises(
        snapshot.CorpusR6PaidSourceNormalizedSnapshotV1Error,
        match="metadata is newer than its rows",
    ):
        snapshot.publish_normalized_snapshot_v1(
            request,
            task0_receipt_value=task0,
            query_warehouse=future_metadata,
            publish_create_once=store.publish,
            read_exact=store.read,
        )
    assert store.writes == []

    def missing_column(spec: dict[str, object]) -> dict[str, object]:
        result = _query_result(spec)
        relation_record = next(
            row for row in result["result_rows"]
            if row["record_kind"] == "relation-metadata"
        )
        body = json.loads(relation_record["row_json"])
        body["columns"] = body["columns"][1:]
        for ordinal, column in enumerate(body["columns"], start=1):
            column["ordinal_position"] = ordinal
        relation_record["row_json"] = json.dumps(
            body, sort_keys=True, separators=(",", ":")
        )
        return result

    with pytest.raises(
        snapshot.CorpusR6PaidSourceNormalizedSnapshotV1Error,
        match="predecessor metadata differs",
    ):
        snapshot.publish_normalized_snapshot_v1(
            request,
            task0_receipt_value=task0,
            query_warehouse=missing_column,
            publish_create_once=store.publish,
            read_exact=store.read,
        )
    assert store.writes == []


def test_request_rejects_query_or_code_substitution() -> None:
    request = _request()
    poisoned = deepcopy(request)
    poisoned["query_specs"][0]["canonical_query"] += "\nSELECT 1"
    poisoned.pop("snapshot_request_sha256")
    poisoned["snapshot_request_sha256"] = source.canonical_sha256(poisoned)
    with pytest.raises(
        snapshot.CorpusR6PaidSourceNormalizedSnapshotV1Error,
        match="canonical replay differs",
    ):
        snapshot.validate_snapshot_request_v1(poisoned)
