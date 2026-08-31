from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import json

import pytest

from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as capture
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


class _MemoryStore:
    def __init__(self) -> None:
        self._by_uri: dict[str, tuple[dict[str, object], bytes]] = {}
        self._generation = 100
        self.write_events: list[str] = []
        self.read_events: list[str] = []

    def add(self, uri: str, raw: bytes) -> dict[str, object]:
        self._generation += 1
        identity = {
            "uri": uri,
            "generation": str(self._generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self._by_uri[uri] = (identity, raw)
        return dict(identity)

    def add_json(self, uri: str, value: object) -> dict[str, object]:
        return self.add(uri, source.canonical_json_bytes(value))

    def read(self, identity: dict[str, object]) -> bytes:
        self.read_events.append(str(identity["uri"]))
        retained, raw = self._by_uri[str(identity["uri"])]
        assert retained == dict(identity)
        return raw

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        self.write_events.append(uri)
        prior = self._by_uri.get(uri)
        if prior is not None:
            identity, existing = prior
            if existing != raw:
                raise RuntimeError("create-once collision")
            return dict(identity)
        return self.add(uri, raw)

    def remove(self, uri: str) -> None:
        del self._by_uri[uri]


@pytest.fixture
def store() -> _MemoryStore:
    return _MemoryStore()


def _value(field: str, *, suffix: str) -> object:
    if field in {"season"}:
        return 2022
    if field in {"week", "target_week", "pos_rank"}:
        return 5
    if field in {"alignment_supported", "split_duplicate"}:
        return False
    if field == "source_sha256":
        return sha256(suffix.encode()).hexdigest()
    if field in {
        "route_share", "player_wide_share", "man_fprr", "zone_fprr",
        "def_man_rate", "completions", "coverage_snaps", "targets",
        "touchdowns", "yards", "rdef_attempts", "rdef_boom_rate",
        "rdef_bust_rate", "rdef_epa_per_attempt", "rdef_stuffs",
        "rdef_yards_after_contact", "air_yards_share", "carries",
        "fumbles_lost_total", "passing_interceptions", "passing_tds",
        "passing_yards", "receiving_tds", "receiving_yards", "receptions",
        "rushing_tds", "rushing_yards", "target_share", "def_pressures",
        "def_sacks", "def_times_blitzed", "def_times_hurried",
        "def_completions_allowed", "def_targets", "def_yards_allowed",
        "defense_snaps", "jersey_number",
    }:
        return 1
    if field == "gameday":
        return "2022-09-11"
    if field == "gametime":
        return "13:00"
    if field == "kickoff_time_utc":
        return "2022-09-11T17:00:00Z"
    if field == "dt":
        return "2025-09-11T17:00:00Z"
    if field == "game_type":
        return "REG"
    if field == "position":
        return "WR"
    if field == "alignment":
        return "Wide"
    return f"{field}-{suffix}"


def _row(pack_id: str, slice_kind: str, *, suffix: str) -> dict[str, object]:
    registry = source.frozen_upstream_pack_registry_v1()
    for pack in registry["packs"]:
        if pack["pack_id"] != pack_id:
            continue
        for schema in pack["positive_row_schemas"]:
            if schema["slice_kind"] == slice_kind:
                return {
                    str(field): _value(str(field), suffix=suffix)
                    for field in schema["row_fields"]
                }
    raise AssertionError("missing fixture schema")


def _identity_fields_for_relation(relation: str) -> set[str]:
    return set(capture._REQUIRED_RELATION_COLUMNS[relation])


def _relation_metadata(relation: str) -> dict[str, object]:
    columns = [
        {
            "name": name,
            "data_type": "STRING",
            "is_nullable": "YES",
            "ordinal_position": ordinal,
        }
        for ordinal, name in enumerate(
            sorted(_identity_fields_for_relation(relation)), start=1
        )
    ]
    return {
        "project_id": capture.PRODUCTION_PROJECT,
        "dataset_id": capture.WAREHOUSE_DATASET,
        "relation_id": relation,
        "row_count": 100,
        "size_bytes": 1000,
        "modified_time_utc": "2026-08-30T12:00:00Z",
        "columns": columns,
    }


def _query_result(spec: dict[str, object]) -> dict[str, object]:
    result_rows: list[dict[str, object]] = []
    for slice_kind in spec["slice_kinds"]:
        positive = _row(str(spec["pack_id"]), str(slice_kind), suffix="positive")
        result_rows.append({
            "record_kind": "row",
            "slice_kind": slice_kind,
            "row_json": json.dumps(positive),
        })
        if slice_kind == "snapshot-depth":
            unresolved = _row(
                str(spec["pack_id"]), str(slice_kind), suffix="unresolved"
            )
            unresolved["gsis_id"] = None
            result_rows.append({
                "record_kind": "row",
                "slice_kind": slice_kind,
                "row_json": json.dumps(unresolved),
            })
    for relation in spec["input_relations"]:
        result_rows.append({
            "record_kind": "relation-metadata",
            "slice_kind": relation,
            "row_json": json.dumps(_relation_metadata(str(relation))),
        })
    return {
        "job_metadata": {
            "project_id": capture.PRODUCTION_PROJECT,
            "location": capture.WAREHOUSE_LOCATION,
            "job_id": spec["job_id"],
            "query_sha256": spec["query_sha256"],
            "state": "DONE",
            "error_result": None,
            "cache_hit": False,
            "total_bytes_processed": 1234,
            "created_utc": "2026-08-30T12:00:00Z",
            "started_utc": "2026-08-30T12:00:01Z",
            "ended_utc": "2026-08-30T12:00:02Z",
        },
        "result_rows": result_rows,
    }


def _implementation() -> dict[str, object]:
    return capture.build_implementation_authority_v1(
        source_commit_sha="a" * 40,
        measurements=[
            {
                "relative_path": path,
                "sha256": sha256(path.encode()).hexdigest(),
                "bytes": len(path.encode()),
            }
            for path in capture.IMPLEMENTATION_PATHS
        ],
    )


def _artifact_manifest(
    store: _MemoryStore, *, pack_id: str,
) -> dict[str, object]:
    registry = source.frozen_upstream_pack_registry_v1()
    pack = next(value for value in registry["packs"] if value["pack_id"] == pack_id)
    shard_pairs: list[tuple[dict[str, object], dict[str, object]]] = []
    for schema in pack["positive_row_schemas"]:
        slice_kind = str(schema["slice_kind"])
        rows = [_row(pack_id, slice_kind, suffix="resolved")]
        if slice_kind in {"fp-route-share", "sis-defender-alignment"}:
            unresolved = _row(pack_id, slice_kind, suffix="unresolved")
            missing_field = (
                "gsis_id" if slice_kind == "fp-route-share"
                else "defender_player_id"
            )
            unresolved[missing_field] = None
            rows.append(unresolved)
        shard = capture.build_artifact_row_shard_v1(
            pack_id=pack_id, slice_kind=slice_kind, rows=rows
        )
        uri = f"gs://fixture-input/{pack_id}/shards/{slice_kind}.json"
        shard_pairs.append((shard, store.add_json(uri, shard)))
    shard_pairs.sort(key=lambda value: str(value[1]["uri"]))
    source_manifest = store.add(
        f"gs://fixture-input/{pack_id}/source-manifest.txt",
        f"frozen-manifest:{pack_id}".encode(),
    )
    source_artifact = store.add(
        f"gs://fixture-input/{pack_id}/source-artifact.bin",
        f"frozen-artifact:{pack_id}".encode(),
    )
    manifest = capture.build_artifact_pack_manifest_v1(
        manifest_id=f"artifact-{pack_id}",
        pack_id=pack_id,
        shard_objects=[value[0] for value in shard_pairs],
        shard_identities=[value[1] for value in shard_pairs],
        source_manifest_identities=[source_manifest],
        source_artifact_identities=[source_artifact],
        projection_code_identity={
            "source_commit_sha": "b" * 40,
            "module_path": f"src/nfl_dfs/research/{pack_id}.py",
            "module_sha256": "c" * 64,
        },
    )
    return store.add_json(
        f"gs://fixture-input/{pack_id}/normalized-manifest.json", manifest
    )


def _inputs(store: _MemoryStore) -> dict[str, object]:
    fixed = store.add("gs://fixture-input/fixed-root.json", b"fixed-root")
    manifests = {
        pack_id: _artifact_manifest(store, pack_id=pack_id)
        for pack_id in capture.ARTIFACT_PACK_IDS
    }
    return {"fixed": fixed, "manifests": manifests}


def test_fixed_query_registry_has_exact_five_non_outcome_extracts() -> None:
    specs = capture.frozen_warehouse_query_specs_v1("sevenpack-test-run")
    assert [value["pack_id"] for value in specs] == list(
        capture.WAREHOUSE_PACK_IDS
    )
    assert len(specs) == 5
    assert all(value["use_legacy_sql"] is False for value in specs)
    assert all(value["use_query_cache"] is False for value in specs)
    assert all(value["named_parameters"] == [] for value in specs)
    assert all("contest" not in value["canonical_query"].lower() for value in specs)
    assert all("realized" not in value["canonical_query"].lower() for value in specs)


def test_artifact_manifest_filters_and_accounts_for_missing_ids(
    store: _MemoryStore,
) -> None:
    inputs = _inputs(store)
    for pack_id in capture.ARTIFACT_PACK_IDS:
        manifest = json.loads(store.read(inputs["manifests"][pack_id]))
        accounting = manifest["missing_id_accounting"]
        assert accounting["missing_id_count"] == 1
        assert accounting["source_row_count"] == (
            accounting["retained_row_count"] + 1
        )
        assert accounting["retention_rule"] == capture.MISSING_ID_RETENTION_RULE
    receipt = capture.preflight_seven_pack_inputs_v1(
        fixed_source_root_identity=inputs["fixed"],
        artifact_manifest_identities=inputs["manifests"],
        read_exact=store.read,
    )
    assert receipt["generation_exact_predecessor_replay_complete"] is True
    assert receipt["warehouse_query_count"] == 0
    assert receipt["publication_count"] == 0
    assert receipt["uses_realized_outcomes"] is False


def test_publish_is_seven_rows_seven_provenance_then_root_and_retry_invariant(
    store: _MemoryStore,
) -> None:
    inputs = _inputs(store)

    def query(spec: dict[str, object]) -> dict[str, object]:
        return _query_result(spec)

    first = capture.publish_seven_pack_capture_v1(
        run_id="sevenpack-test-run",
        fixed_source_root_identity=inputs["fixed"],
        artifact_manifest_identities=inputs["manifests"],
        implementation_authority=_implementation(),
        query_warehouse=query,
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    assert first["write_count"] == 15
    assert first["terminal_release_root_last"] is True
    assert store.write_events[-1].endswith("/upstream-release.json")
    assert first["all_seven_rows_and_provenance_reopened_before_root"] is True
    assert first["same_process_full_reopen_complete"] is True
    assert first["independent_process_reopen_required"] is True
    assert all(first[field] is False for field in source.FALSE_AUTHORITY_FIELDS)
    root_identity = deepcopy(first["terminal_release_identity"])

    store.write_events.clear()
    second = capture.publish_seven_pack_capture_v1(
        run_id="sevenpack-test-run",
        fixed_source_root_identity=inputs["fixed"],
        artifact_manifest_identities=inputs["manifests"],
        implementation_authority=_implementation(),
        query_warehouse=query,
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    assert second["terminal_release_identity"] == root_identity
    assert second["retry_invariant_root_sha256"] == first[
        "retry_invariant_root_sha256"
    ]
    assert store.write_events[-1].endswith("/upstream-release.json")


def test_bad_query_job_fails_before_any_publication(store: _MemoryStore) -> None:
    inputs = _inputs(store)
    store.write_events.clear()

    def query(spec: dict[str, object]) -> dict[str, object]:
        result = _query_result(spec)
        if spec["ordinal"] == 2:
            result["job_metadata"]["job_id"] = "substituted-job"
        return result

    with pytest.raises(
        capture.CorpusR6MatchupSevenPackCaptureV1Error,
        match="job result differs",
    ):
        capture.publish_seven_pack_capture_v1(
            run_id="sevenpack-test-run",
            fixed_source_root_identity=inputs["fixed"],
            artifact_manifest_identities=inputs["manifests"],
            implementation_authority=_implementation(),
            query_warehouse=query,
            read_exact=store.read,
            publish_create_once=store.publish,
        )
    assert store.write_events == []


def test_missing_required_relation_column_fails_before_publication(
    store: _MemoryStore,
) -> None:
    inputs = _inputs(store)
    store.write_events.clear()

    def query(spec: dict[str, object]) -> dict[str, object]:
        result = _query_result(spec)
        if spec["ordinal"] == 0:
            metadata = json.loads(result["result_rows"][-1]["row_json"])
            metadata["columns"] = [
                value for value in metadata["columns"]
                if value["name"] != "game_id"
            ]
            for ordinal, value in enumerate(metadata["columns"], start=1):
                value["ordinal_position"] = ordinal
            result["result_rows"][-1]["row_json"] = json.dumps(metadata)
        return result

    with pytest.raises(
        capture.CorpusR6MatchupSevenPackCaptureV1Error,
        match="required direct column",
    ):
        capture.publish_seven_pack_capture_v1(
            run_id="sevenpack-test-run",
            fixed_source_root_identity=inputs["fixed"],
            artifact_manifest_identities=inputs["manifests"],
            implementation_authority=_implementation(),
            query_warehouse=query,
            read_exact=store.read,
            publish_create_once=store.publish,
        )
    assert store.write_events == []


def test_integer_run_id_fails_before_query_or_publication(store: _MemoryStore) -> None:
    calls: list[str] = []
    with pytest.raises(capture.CorpusR6MatchupSevenPackCaptureV1Error):
        capture.publish_seven_pack_capture_v1(
            run_id=12345678,  # type: ignore[arg-type]
            fixed_source_root_identity={},
            artifact_manifest_identities={},
            implementation_authority={},
            query_warehouse=lambda _: calls.append("query") or {},
            read_exact=lambda _: calls.append("read") or b"",
            publish_create_once=lambda _uri, _raw: calls.append("write") or {},
        )
    assert calls == []


def test_reopen_fails_when_one_frozen_shard_is_missing(store: _MemoryStore) -> None:
    inputs = _inputs(store)
    published = capture.publish_seven_pack_capture_v1(
        run_id="sevenpack-test-run",
        fixed_source_root_identity=inputs["fixed"],
        artifact_manifest_identities=inputs["manifests"],
        implementation_authority=_implementation(),
        query_warehouse=_query_result,
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    fp_manifest_raw = store.read(inputs["manifests"][source.FANTASY_POINTS_PACK])
    fp_manifest = json.loads(fp_manifest_raw)
    store.remove(fp_manifest["shards"][0]["identity"]["uri"])
    with pytest.raises(
        capture.CorpusR6MatchupSevenPackCaptureV1Error,
        match="generation-exact read failed",
    ):
        capture.reopen_seven_pack_capture_v1(
            release_identity=published["terminal_release_identity"],
            read_exact=store.read,
        )


def test_reopen_fails_when_original_artifact_predecessor_is_missing(
    store: _MemoryStore,
) -> None:
    inputs = _inputs(store)
    published = capture.publish_seven_pack_capture_v1(
        run_id="sevenpack-test-run",
        fixed_source_root_identity=inputs["fixed"],
        artifact_manifest_identities=inputs["manifests"],
        implementation_authority=_implementation(),
        query_warehouse=_query_result,
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    sis_manifest = json.loads(
        store.read(inputs["manifests"][source.SIS_PACK])
    )
    store.remove(sis_manifest["source_artifact_identities"][0]["uri"])
    with pytest.raises(
        capture.CorpusR6MatchupSevenPackCaptureV1Error,
        match="generation-exact read failed",
    ):
        capture.reopen_seven_pack_capture_v1(
            release_identity=published["terminal_release_identity"],
            read_exact=store.read,
        )


def test_query_receipt_is_exactly_bound_to_namespace_run_id(
    store: _MemoryStore,
) -> None:
    inputs = _inputs(store)
    published = capture.publish_seven_pack_capture_v1(
        run_id="sevenpack-test-run",
        fixed_source_root_identity=inputs["fixed"],
        artifact_manifest_identities=inputs["manifests"],
        implementation_authority=_implementation(),
        query_warehouse=_query_result,
        read_exact=store.read,
        publish_create_once=store.publish,
    )
    root = json.loads(store.read(published["terminal_release_identity"]))
    pack = root["packs"][0]
    rows = json.loads(store.read(pack["exact_rows_identity"]))
    provenance = json.loads(store.read(pack["warehouse_query_receipt_identity"]))
    with pytest.raises(
        capture.CorpusR6MatchupSevenPackCaptureV1Error,
        match="frozen query registry",
    ):
        capture.validate_warehouse_query_receipt_v1(
            provenance,
            expected_run_id="different-test-run",
            expected_pack_id=pack["pack_id"],
            expected_rows=rows,
            expected_rows_identity=pack["exact_rows_identity"],
        )
