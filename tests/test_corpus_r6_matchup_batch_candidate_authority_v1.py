from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import inspect
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Mapping

import pytest

from nfl_dfs.research import (
    corpus_r6_fixed_g0_candidate_authority_release_v1 as candidate_authority,
)
from nfl_dfs.research import (
    corpus_r6_matchup_batch_candidate_authority_v1 as batch,
)
from nfl_dfs.research import corpus_r6_matchup_capture_plan_v1 as capture_v1
from nfl_dfs.research import (
    corpus_r6_matchup_capture_plan_candidate_authority_v2 as capture_v2,
)
from nfl_dfs.research import corpus_r6_matchup_source_operator_v2 as operator
from nfl_dfs.research import (
    corpus_r6_matchup_source_release_candidate_authority_v2 as release_v2,
)
from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as release_v1
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


def _digest(label: str) -> str:
    return sha256(label.encode("utf-8")).hexdigest()


def _identity(uri: str, label: str, *, generation: int = 1) -> dict[str, object]:
    raw = source.canonical_json_bytes({"fixture": label})
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _identity_for_raw(uri: str, raw: bytes, generation: int) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


class _Store:
    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], bytes] = {}
        self.latest: dict[str, dict[str, object]] = {}
        self.events: list[tuple[str, str]] = []
        self.generation = 1000

    def publish(self, uri: str, raw: bytes) -> dict[str, object]:
        self.events.append(("publish", uri))
        existing = self.latest.get(uri)
        if existing is not None:
            assert self.objects[(uri, str(existing["generation"]))] == raw
            return dict(existing)
        self.generation += 1
        identity = _identity_for_raw(uri, raw, self.generation)
        self.latest[uri] = identity
        self.objects[(uri, str(identity["generation"]))] = raw
        return dict(identity)

    def read(self, identity: Mapping[str, object]) -> bytes:
        self.events.append(("read", str(identity["uri"])))
        return self.objects[(str(identity["uri"]), str(identity["generation"]))]


class _GCSNotFound(Exception):
    code = 404


class _GCSPrecondition(Exception):
    code = 412


class _GCSBlob:
    def __init__(
        self, client: "_GCSClient", key: str, generation: int | None
    ) -> None:
        self.client = client
        self.key = key
        self.requested_generation = generation
        self.generation: int | None = None
        self.size: int | None = None

    def _resolved(self) -> int:
        generation = self.requested_generation
        if generation is None:
            generation = self.client.latest.get(self.key)
        if generation is None or (self.key, generation) not in self.client.objects:
            raise _GCSNotFound(self.key)
        return generation

    def reload(self, if_generation_match: int | None = None) -> None:
        generation = self._resolved()
        if if_generation_match is not None and generation != if_generation_match:
            raise _GCSPrecondition(self.key)
        self.generation = generation
        self.size = len(self.client.objects[(self.key, generation)])

    def download_as_bytes(
        self, if_generation_match: int | None = None
    ) -> bytes:
        generation = self._resolved()
        if if_generation_match is not None and generation != if_generation_match:
            raise _GCSPrecondition(self.key)
        self.client.download_calls += 1
        if self.client.explode_on_download:
            raise AssertionError("download must not be reached")
        return self.client.objects[(self.key, generation)]

    def upload_from_string(
        self,
        raw: bytes,
        *,
        content_type: str,
        if_generation_match: int,
    ) -> None:
        assert content_type == "application/json"
        assert if_generation_match == 0
        self.client.upload_calls += 1
        if self.client.event_sink is not None:
            self.client.event_sink.append(f"gs://{self.key}")
        if self.client.drop_uploads:
            return
        if self.key in self.client.latest:
            raise _GCSPrecondition(self.key)
        self.client.force(self.key, raw)


class _GCSBucket:
    def __init__(self, client: "_GCSClient", name: str) -> None:
        self.client = client
        self.name = name

    def blob(self, name: str, generation: int | None = None) -> _GCSBlob:
        return _GCSBlob(self.client, f"{self.name}/{name}", generation)


class _GCSClient:
    project = batch.PRODUCTION_PROJECT
    api_endpoint = batch.PRODUCTION_GCS_API_ENDPOINT
    universe_domain = batch.PRODUCTION_GCS_UNIVERSE_DOMAIN
    _is_emulator_set = False

    def __init__(self) -> None:
        self.objects: dict[tuple[str, int], bytes] = {}
        self.latest: dict[str, int] = {}
        self.next_generation = 200
        self.upload_calls = 0
        self.download_calls = 0
        self.explode_on_download = False
        self.drop_uploads = False
        self.event_sink: list[str] | None = None
        self.mirror_store: _Store | None = None

    def bucket(self, name: str) -> _GCSBucket:
        return _GCSBucket(self, name)

    def force(self, key: str, raw: bytes) -> int:
        self.next_generation += 1
        self.objects[(key, self.next_generation)] = bytes(raw)
        self.latest[key] = self.next_generation
        if self.mirror_store is not None:
            uri = f"gs://{key}"
            identity = _identity_for_raw(uri, raw, self.next_generation)
            self.mirror_store.latest[uri] = identity
            self.mirror_store.objects[(uri, str(self.next_generation))] = bytes(raw)
            self.mirror_store.generation = max(
                self.mirror_store.generation, self.next_generation
            )
        return self.next_generation


def _code(path: str, label: str = "code") -> dict[str, str]:
    return {
        "source_commit_sha": "a" * 40,
        "module_path": path,
        "module_sha256": _digest(label + path),
    }


def _code_binding(path: str, label: str) -> dict[str, object]:
    identity = _code(path, label)
    return {
        "primary_code_identity": identity,
        "repair_sha256": None,
        "effective_code_identity": identity,
    }


def _dependency_closure(commit: str = "a" * 40) -> dict[str, object]:
    labels = {
        operator.OPERATOR_MODULE_PATH: "operator",
        batch.BATCH_MODULE_PATH: "batch",
        capture_v1.SOURCE_V2_MODULE_PATH: "source",
        capture_v1.COMPONENT_PRODUCER_MODULE_PATH: "producer",
    }
    identities = []
    for path in batch.EXECUTED_DEPENDENCY_MODULE_PATHS:
        if path in labels:
            identity = _code(path, labels[path])
            identity["source_commit_sha"] = commit
        else:
            identity = {
                "source_commit_sha": commit,
                "module_path": path,
                "module_sha256": _digest(f"dependency:{path}"),
            }
        identities.append(identity)
    body: dict[str, object] = {
        "schema_version": batch.DEPENDENCY_CLOSURE_SCHEMA,
        "source_commit_sha": commit,
        "module_paths": list(batch.EXECUTED_DEPENDENCY_MODULE_PATHS),
        "module_code_identities": identities,
        "module_code_identity_manifest_sha256": source.canonical_sha256(
            identities
        ),
        "all_head_blobs_match_current_bytes": True,
        "all_scoped_paths_clean": True,
    }
    body["dependency_closure_sha256"] = source.canonical_sha256(body)
    return body


def _capture_binding(plan_sha: str) -> dict[str, object]:
    return {
        "commit_sha": "a" * 40,
        "relative_path": (
            "reports/corpus-r6-matchup-runs/20260826-r6-matchup-source-v2/"
            "capture-plan-candidate-authority-v2-lock.json"
        ),
        "sha256": _digest("capture-plan-file"),
        "bytes": 1234,
        "capture_plan_sha256": plan_sha,
    }


def _candidate_authority_fixture() -> (
    candidate_authority.ReopenedFixedG0CandidateAuthorityV1
):
    prefix = (
        f"gs://{candidate_authority.OUTPUT_BUCKET}/"
        f"{candidate_authority.OUTPUT_NAMESPACE}/fixture-batch-authority/"
    )
    root_identity = _identity(
        f"{prefix}{candidate_authority.ROOT_FILENAME}", "candidate-root"
    )
    release_identity = _identity(
        f"{prefix}{candidate_authority.CANDIDATE_RELEASE_FILENAME}",
        "candidate-release",
    )
    entries: list[dict[str, object]] = []
    for ordinal in range(source.TASK_COUNT):
        slate = catalog_v1.expected_slate_for_source_task(ordinal)
        task_id = catalog_v1.task_id_for_source_task(ordinal)
        slate_id = str(slate["slate_id"])
        artifact_identity = _identity(
            f"{prefix}source-task-{ordinal:02d}-{slate_id}/"
            "accepted-candidates.json",
            f"candidate-{ordinal}",
            generation=2000 + ordinal,
        )
        artifact = {
            "candidate_artifact_sha256": _digest(f"artifact-{ordinal}"),
        }
        entries.append({
            "source_task_ordinal": ordinal,
            "task_id": task_id,
            "slate": slate,
            "catalog_identity": _identity(
                f"gs://fixture-catalog/task-{ordinal:02d}.json",
                f"catalog-{ordinal}",
                generation=3000 + ordinal,
            ),
            "candidate_artifact": artifact,
            "candidate_artifact_identity": artifact_identity,
            "candidate_count": source.ENTRY_BUDGET,
            "ordered_candidate_ids_sha256": _digest(f"ordered-{ordinal}"),
        })
    release = {
        "entries": entries,
        "accepted_candidate_release_sha256": _digest("candidate-release-internal"),
    }
    root = {
        "candidate_authority_release_sha256": _digest("candidate-root-internal"),
    }
    return candidate_authority.ReopenedFixedG0CandidateAuthorityV1(
        root=root,
        root_identity=root_identity,
        authority_bundle={"fixture": True},
        candidate_release=release,
        candidate_release_identity=release_identity,
    )


def _triple(
    *, ordinal: int, prefix: str, candidate_entry: Mapping[str, object],
) -> dict[str, object]:
    export = {
        "task_id": candidate_entry["task_id"],
        "slate": candidate_entry["slate"],
        "annotation_row_count": ordinal % 3,
        "matchup_source_export_sha256": _digest(f"export-{ordinal}"),
    }
    capture = {
        "matchup_capture_receipt_sha256": _digest(f"capture-{ordinal}"),
    }
    result = {
        "matchup_operator_result_sha256": _digest(f"result-{ordinal}"),
    }
    return {
        "source_task_ordinal": ordinal,
        "task_id": candidate_entry["task_id"],
        "slate": candidate_entry["slate"],
        "source_export": export,
        "source_export_identity": _identity(
            f"{prefix}matchup-source-export.json", f"export-{ordinal}"
        ),
        "capture_receipt": capture,
        "capture_receipt_identity": _identity(
            f"{prefix}matchup-capture-receipt.json", f"capture-{ordinal}"
        ),
        "operator_result": result,
        "operator_result_identity": _identity(
            f"{prefix}matchup-operator-result.json", f"result-{ordinal}"
        ),
        "candidate_artifact_identity": candidate_entry[
            "candidate_artifact_identity"
        ],
    }


def _batch_member_fixture(ordinal: int = 0) -> dict[str, object]:
    reopened = _candidate_authority_fixture()
    candidate_entry = reopened.candidate_release["entries"][ordinal]
    slate_id = str(candidate_entry["slate"]["slate_id"])
    prefix = (
        f"{batch.output_prefix_for_run_v1('fixture-member-0001')}"
        f"source-task-{ordinal:02d}-{slate_id}/"
    )
    triple = _triple(
        ordinal=ordinal, prefix=prefix, candidate_entry=candidate_entry
    )
    component_entry = {
        "source_task_ordinal": ordinal,
        "slate": candidate_entry["slate"],
        "catalog_identity": candidate_entry["catalog_identity"],
        "input_bundle_identity": _identity(
            f"gs://fixture-component/bundle-{ordinal}.json", f"bundle-{ordinal}"
        ),
        "producer_receipt_identity": _identity(
            f"gs://fixture-component/receipt-{ordinal}.json",
            f"receipt-{ordinal}",
        ),
        "support_preflight_passed": True,
    }
    plan_task = {
        "source_task_ordinal": ordinal,
        "task_id": candidate_entry["task_id"],
        "slate": candidate_entry["slate"],
        "catalog_identity": candidate_entry["catalog_identity"],
        "candidate_artifact_identity": candidate_entry[
            "candidate_artifact_identity"
        ],
    }
    return batch._batch_member(
        ordinal=ordinal,
        candidate_root_identity=reopened.root_identity,
        candidate_root_sha256=reopened.root[
            "candidate_authority_release_sha256"
        ],
        capture_plan_task=plan_task,
        candidate_entry=candidate_entry,
        component_entry=component_entry,
        triple=triple,
    )


def _rehash_member(value: Mapping[str, object]) -> dict[str, object]:
    result = deepcopy(dict(value))
    result["batch_member_sha256"] = source.canonical_sha256({
        key: nested
        for key, nested in result.items()
        if key != "batch_member_sha256"
    })
    return result


def test_exact_read_cache_reads_once_and_rejects_identity_conflict() -> None:
    raw = b'{"fixture":"cache"}'
    identity = _identity_for_raw("gs://fixture/cache.json", raw, 7)
    reads: list[dict[str, object]] = []
    cache = batch.ExactReadCacheV1(
        lambda value: reads.append(dict(value)) or raw
    )
    assert cache.read(identity) == raw
    assert cache.read(identity) == raw
    assert len(reads) == 1
    assert cache.miss_count == 1
    assert cache.hit_count == 1
    budget = cache.budget_receipt()
    assert budget["read_operations_reserved"] == 1
    assert budget["read_bytes_reserved"] == len(raw)
    assert budget["all_payload_reads_charged_before_access"] is True
    assert budget["cross_process_durable_ledger"] is False
    conflicting = dict(identity)
    conflicting["sha256"] = _digest("different")
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="different identity",
    ):
        cache.read(conflicting)
    small_cache = batch.ExactReadCacheV1(lambda _value: raw, max_cached_bytes=4)
    assert small_cache.read(identity) == raw
    assert small_cache.cached_bytes == 0
    assert small_cache.oversize_bypass_count == 1


def test_exact_read_cache_enforces_object_and_cumulative_budget_before_reader(
) -> None:
    raw = b'{"fixture":"bounded-cache"}'
    first = _identity_for_raw("gs://fixture/cache-1.json", raw, 1)
    second = _identity_for_raw("gs://fixture/cache-2.json", raw, 1)
    reads: list[str] = []
    cache = batch.ExactReadCacheV1(
        lambda value: reads.append(str(value["uri"])) or raw,
        max_object_bytes=len(raw),
        max_invocation_read_bytes=len(raw),
        max_read_operations=1,
    )
    assert cache.read(first) == raw
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="cumulative invocation budget exhausted",
    ):
        cache.read(second)
    assert reads == [first["uri"]]

    oversize_reads: list[object] = []
    oversize = batch.ExactReadCacheV1(
        lambda value: oversize_reads.append(value) or raw,
        max_object_bytes=len(raw) - 1,
        max_invocation_read_bytes=len(raw),
    )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="object exceeds",
    ):
        oversize.read(first)
    assert oversize_reads == []


def test_concrete_gcs_transport_pins_generation_and_resumes_equal_only() -> None:
    client = _GCSClient()
    prefix = "gs://fixture-bucket/fixed-prefix/"
    uri = f"{prefix}release.json"
    key = "fixture-bucket/fixed-prefix/release.json"
    transport = batch.GenerationPinnedGCSBatchTransportV1(
        client, expected_write_uris=(uri,)
    )
    raw = b'{"complete":true}'
    identity = transport.publish_create_once(uri, raw)
    assert transport.read_exact(identity) == raw
    recovery = batch.GenerationPinnedGCSBatchTransportV1(
        client, expected_write_uris=(uri,)
    )
    assert recovery.publish_create_once(uri, raw) == identity
    assert client.latest[key] == int(str(identity["generation"]))

    collision = batch.GenerationPinnedGCSBatchTransportV1(
        client, expected_write_uris=(uri,)
    )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="different bytes",
    ):
        collision.publish_create_once(uri, b'{"complete":false}')
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="escapes exact URI inventory",
    ):
        transport.publish_create_once(
            "gs://fixture-bucket/foreign/release.json", raw
        )

    later_generation = client.force(key, b'{"later":true}')
    assert later_generation != int(str(identity["generation"]))
    assert transport.read_exact(identity) == raw
    budget = transport.read_budget_receipt()
    assert budget["read_operations_reserved"] >= 3
    assert budget["read_bytes_reserved"] >= len(raw) * 3
    assert budget["all_payload_reads_charged_before_access"] is True
    write_budget = transport.write_budget_receipt()
    assert write_budget["write_operations_reserved"] == 1
    assert write_budget["write_bytes_reserved"] == len(raw)
    assert write_budget["completed_write_uris"] == [uri]


def test_gcs_transport_rejects_endpoint_redirects_and_precharges_read_bounds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    bad_client = _GCSClient()
    bad_client.api_endpoint = "https://attacker.invalid"
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="genuine production endpoint",
    ):
        batch.GenerationPinnedGCSBatchTransportV1(
            bad_client, expected_write_uris=()
        )

    raw = b'{"fixture":"transport-budget"}'
    client = _GCSClient()
    key = "fixture-bucket/input.json"
    generation = client.force(key, raw)
    identity = _identity_for_raw(
        "gs://fixture-bucket/input.json", raw, generation
    )
    transport = batch.GenerationPinnedGCSBatchTransportV1(
        client,
        expected_write_uris=(),
        max_object_bytes=len(raw),
        max_invocation_read_bytes=len(raw),
        max_read_operations=1,
    )
    assert transport.read_exact(identity) == raw
    downloads = client.download_calls
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="invocation budget exhausted",
    ):
        transport.read_exact(identity)
    assert client.download_calls == downloads

    # A caller can coherently sign an identity that underreports the object.
    # GCS metadata must reject that claim before the payload method—which is
    # deliberately explosive in this fake—is invoked.
    guarded_client = _GCSClient()
    guarded_generation = guarded_client.force(key, raw)
    guarded_client.explode_on_download = True
    underreported = _identity_for_raw(
        "gs://fixture-bucket/input.json", raw, guarded_generation
    )
    underreported["bytes"] = len(raw) - 1
    guarded_transport = batch.GenerationPinnedGCSBatchTransportV1(
        guarded_client,
        expected_write_uris=(),
        max_object_bytes=len(raw),
        max_invocation_read_bytes=len(raw),
        max_read_operations=1,
    )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="metadata exceeds or differs from reservation",
    ):
        guarded_transport.read_exact(underreported)
    assert guarded_client.download_calls == 0

    monkeypatch.setenv("STORAGE_EMULATOR_HOST", "http://127.0.0.1:4443")
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="endpoint override environment is forbidden",
    ):
        batch._trusted_gcs_transport_v1(expected_write_uris=())


def test_gcs_transport_enforces_exact_inventory_and_cumulative_write_precharge(
) -> None:
    first_uri = "gs://fixture-bucket/exact/first.json"
    second_uri = "gs://fixture-bucket/exact/second.json"
    raw = b'{"bounded":true}'
    client = _GCSClient()
    transport = batch.GenerationPinnedGCSBatchTransportV1(
        client,
        expected_write_uris=tuple(sorted((first_uri, second_uri))),
        max_object_bytes=len(raw),
        max_invocation_write_bytes=len(raw),
    )
    transport.publish_create_once(first_uri, raw)
    uploads = client.upload_calls
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="cumulative create-once invocation budget exhausted",
    ):
        transport.publish_create_once(second_uri, raw)
    assert client.upload_calls == uploads
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="completion state differs",
    ):
        transport.require_completed_exactly_v1(
            completed_uris=[first_uri, second_uri], pending_uris=[]
        )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="completion partition differs",
    ):
        transport.require_completed_exactly_v1(
            completed_uris=[first_uri],
            pending_uris=[
                second_uri,
                "gs://fixture-bucket/exact/unexpected.json",
            ],
        )

    retry_client = _GCSClient()
    retry_client.drop_uploads = True
    retry_transport = batch.GenerationPinnedGCSBatchTransportV1(
        retry_client, expected_write_uris=(first_uri,)
    )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="remains absent after bounded attempts",
    ):
        retry_transport.publish_create_once(first_uri, raw)
    assert retry_client.upload_calls == batch.CREATE_ONCE_ATTEMPTS
    uploads = retry_client.upload_calls
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="cumulative create-once invocation budget exhausted",
    ):
        retry_transport.publish_create_once(first_uri, raw)
    assert retry_client.upload_calls == uploads


def test_batch_member_rejects_coherent_task_and_slate_mutations() -> None:
    member = _batch_member_fixture()
    assert member["promotion_eligible"] is False
    assert member["outcome_freedom_status"] == {
        "independent_source_lineage_attested": False,
        "outcome_free_authority": False,
        "promotion_eligible": False,
        "unattested_by_this_batch_boundary": True,
    }
    wrong_task = deepcopy(member)
    wrong_task["task_id"] = "fixture-wrong-task"
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="fixed law",
    ):
        batch.validate_batch_member_v1(_rehash_member(wrong_task), expected_ordinal=0)

    wrong_slate = deepcopy(member)
    wrong_slate["slate"] = {**dict(member["slate"]), "extra": "coherent"}
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="fixed law",
    ):
        batch.validate_batch_member_v1(
            _rehash_member(wrong_slate), expected_ordinal=0
        )


def test_output_inventory_is_exact_and_covers_all_54_publication_dags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reopened = _candidate_authority_fixture()
    plan = {
        "producer_namespace": "gs://fixture-producer/exact-components/",
        "source_task_bindings": [
            {
                "source_task_ordinal": ordinal,
                "slate": entry["slate"],
            }
            for ordinal, entry in enumerate(
                reopened.candidate_release["entries"]
            )
        ],
    }
    monkeypatch.setattr(
        capture_v2, "validate_capture_plan_lock_v2", lambda value: dict(value)
    )
    inventory = batch._output_uri_inventory_v1(
        run_id="fixture-inventory-0001", plan_value=plan
    )
    # 54 * (46 role slices + support rows + bundle + producer receipt),
    # one producer root, one component receipt, 54 * (triple + member),
    # one source root, one work receipt, and one terminal root.
    assert inventory["uri_count"] == 2867
    assert inventory["uris"] == sorted(set(inventory["uris"]))
    assert inventory["broad_prefix_write_authority_allowed"] is False
    assert inventory["unexpected_uri_backend_call_possible"] is False
    phases = {entry["phase"] for entry in inventory["entries"]}
    assert phases == {
        "component-producer-object",
        "component-producer-root",
        "batch-component-receipt",
        "source-triple",
        "batch-member",
        "source-release-root",
        "preterminal-publication-work-receipt",
        "terminal-batch-root",
    }


def test_dependency_closure_binds_head_and_current_bytes_before_publication(
    tmp_path: Path,
) -> None:
    commit = "b" * 40
    blobs: dict[str, bytes] = {}
    for ordinal, path in enumerate(batch.EXECUTED_DEPENDENCY_MODULE_PATHS):
        raw = f"# dependency {ordinal}: {path}\n".encode("utf-8")
        target = tmp_path / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(raw)
        blobs[path] = raw
    status_calls: list[list[str]] = []

    closure = batch._replay_executed_dependency_closure(
        expected_commit_sha=commit,
        repository_root=tmp_path,
        git_head=lambda _root: commit,
        git_blob=lambda _root, _commit, path: blobs[path],
        git_status=lambda _root, paths: status_calls.append(list(paths)) or b"",
    )
    assert closure["source_commit_sha"] == commit
    assert closure["module_paths"] == list(
        batch.EXECUTED_DEPENDENCY_MODULE_PATHS
    )
    assert status_calls == [
        list(batch.EXECUTED_DEPENDENCY_MODULE_PATHS),
        list(batch.EXECUTED_DEPENDENCY_MODULE_PATHS),
    ]

    first_path = batch.EXECUTED_DEPENDENCY_MODULE_PATHS[0]
    (tmp_path / first_path).write_bytes(b"# dirty bytes\n")
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="current bytes differ",
    ):
        batch._replay_executed_dependency_closure(
            expected_commit_sha=commit,
            repository_root=tmp_path,
            git_head=lambda _root: commit,
            git_blob=lambda _root, _commit, path: blobs[path],
            git_status=lambda _root, _paths: b"",
        )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="not clean",
    ):
        batch._replay_executed_dependency_closure(
            expected_commit_sha=commit,
            repository_root=tmp_path,
            git_head=lambda _root: commit,
            git_blob=lambda _root, _commit, path: blobs[path],
            git_status=lambda _root, _paths: b" M dependency.py\n",
        )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="not clean at the fixed Git HEAD",
    ):
        batch._replay_executed_dependency_closure(
            expected_commit_sha=commit,
            repository_root=tmp_path,
            git_head=lambda _root: "c" * 40,
            git_blob=lambda _root, _commit, path: blobs[path],
            git_status=lambda _root, _paths: b"",
        )
    assert batch.CREATE_ONCE_RESUME_POLICY.startswith(
        "same_source_commit_only;restore_exact_clean_commit_before_resume;"
    )


def test_secure_repository_read_rejects_file_parent_symlink_and_hardlink(
    tmp_path: Path,
) -> None:
    safe = tmp_path / "safe" / "source.py"
    safe.parent.mkdir()
    safe.write_bytes(b"# exact source\n")
    assert batch._secure_read_repository_file_v1(
        tmp_path, "safe/source.py", label="fixture source"
    ) == b"# exact source\n"

    linked_file = tmp_path / "safe" / "linked.py"
    linked_file.symlink_to(safe)
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="secure read failed|symlink",
    ):
        batch._secure_read_repository_file_v1(
            tmp_path, "safe/linked.py", label="linked source"
        )

    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    (real_parent / "source.py").write_bytes(b"# alias\n")
    (tmp_path / "linked-parent").symlink_to(real_parent, target_is_directory=True)
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="secure read failed|symlink",
    ):
        batch._secure_read_repository_file_v1(
            tmp_path, "linked-parent/source.py", label="linked parent source"
        )

    hardlink = tmp_path / "safe" / "hardlink.py"
    os.link(safe, hardlink)
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="unaliased regular file",
    ):
        batch._secure_read_repository_file_v1(
            tmp_path, "safe/source.py", label="hardlinked source"
        )


def test_secure_repository_read_rejects_root_replacement_after_open(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "parent"
    root = parent / "root"
    replacement = parent / "replacement"
    root.mkdir(parents=True)
    replacement.mkdir()
    (root / "source.py").write_bytes(b"# original\n")
    (replacement / "source.py").write_bytes(b"# replacement\n")
    displaced = parent / "displaced"
    real_open = os.open
    replaced = False

    def racing_open(path: object, flags: int, *args: object, **kwargs: object):
        nonlocal replaced
        descriptor = real_open(path, flags, *args, **kwargs)
        if Path(path) == root and not replaced and kwargs.get("dir_fd") is None:
            root.rename(displaced)
            replacement.rename(root)
            replaced = True
        return descriptor

    monkeypatch.setattr(batch.os, "open", racing_open)
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="repository root changed during secure traversal",
    ):
        batch._secure_read_repository_file_v1(
            root, "source.py", label="raced source"
        )


def test_trusted_git_uses_allowlisted_environment_and_disables_replacements(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("GIT_REPLACE_REF_BASE", "refs/evil/")
    monkeypatch.setenv("GIT_OBJECT_DIRECTORY", "/tmp/evil-objects")
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/tmp/evil-config")
    monkeypatch.setenv("HOME", "/tmp/evil-home")
    environment = batch._clean_git_environment_v1()
    assert set(environment) == {
        "PATH",
        "LANG",
        "LC_ALL",
        "GIT_CONFIG_NOSYSTEM",
        "GIT_CONFIG_GLOBAL",
        "GIT_CONFIG_SYSTEM",
        "GIT_NO_REPLACE_OBJECTS",
        "GIT_OPTIONAL_LOCKS",
    }
    assert environment["GIT_CONFIG_GLOBAL"] == os.devnull
    assert environment["GIT_CONFIG_SYSTEM"] == os.devnull
    assert environment["GIT_NO_REPLACE_OBJECTS"] == "1"

    captured: dict[str, object] = {}

    def fake_run(command: list[str], **kwargs: object) -> SimpleNamespace:
        captured["command"] = command
        captured["environment"] = kwargs["env"]
        return SimpleNamespace(stdout=b"fixture\n")

    monkeypatch.setattr(batch, "_trusted_repository_root_v1", lambda: tmp_path)
    monkeypatch.setattr(batch.subprocess, "run", fake_run)
    assert batch._run_trusted_git_v1(tmp_path, ["fixture"]) == b"fixture\n"
    command = captured["command"]
    assert isinstance(command, list)
    assert "--no-replace-objects" in command
    assert ["-c", "core.fsmonitor=false"] == command[2:4]
    assert ["-c", "core.untrackedCache=false"] == command[4:6]
    assert captured["environment"] == environment


def test_reopen_rejects_foreign_batch_root_before_any_read() -> None:
    reads: list[object] = []
    identity = _identity(
        "gs://foreign-bucket/research/adopted/release.json", "foreign-root"
    )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="fixed source-batch namespace",
    ):
        batch._reopen_matchup_source_batch_candidate_authority_with_adapters_v1(
            batch_release_identity=identity,
            repository_root=Path("."),
            read_exact=lambda value: reads.append(value) or b"{}",
            git_head=lambda _root: "a" * 40,
            git_blob=lambda _root, _commit, _path: b"fixture",
            git_status=lambda _root, _paths: b"",
        )
    assert reads == []


def test_public_batch_api_derives_root_plan_git_and_code_without_caller_seams() -> None:
    parameters = inspect.signature(
        batch.publish_matchup_source_batch_candidate_authority_v1
    ).parameters
    for forbidden in (
        "candidate_authority_root_identity", "capture_plan",
        "capture_plan_binding", "operator_code_identity",
        "orchestrator_code_identity", "repository_root", "git_head",
        "git_blob", "git_status", "operator_repair_sha256",
        "orchestrator_repair_sha256", "publish_create_once", "read_exact",
        "accepted_candidate_release", "accepted_candidate_release_identity",
        "candidate_artifact", "candidate_artifact_identity", "candidate_rows",
        "adapter_final_release_lock_commit_sha",
        "adapter_final_release_lock_raw", "fixed_g0_replay_receipt",
        "fixed_g0_replay_receipt_identity", "catalog_release",
        "catalog_release_identity", "structural_catalogs",
        "upstream_source_release", "upstream_source_release_identity",
        "upstream_pack_row_objects", "score", "outcomes", "selector_result",
    ):
        assert forbidden not in parameters
    assert set(parameters) == {"run_id"}
    assert set(inspect.signature(
        batch.reopen_matchup_source_batch_candidate_authority_v1
    ).parameters) == {"batch_release_identity"}


def test_loaded_runtime_attestation_rejects_monkeypatched_authority_callable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    commit = "a" * 40
    identities = [
        {
            "source_commit_sha": commit,
            "module_path": path,
            "module_sha256": sha256(
                (batch.REPOSITORY_ROOT / path).read_bytes()
            ).hexdigest(),
        }
        for path in batch.EXECUTED_DEPENDENCY_MODULE_PATHS
    ]
    closure = {
        "schema_version": batch.DEPENDENCY_CLOSURE_SCHEMA,
        "source_commit_sha": commit,
        "module_paths": list(batch.EXECUTED_DEPENDENCY_MODULE_PATHS),
        "module_code_identities": identities,
        "module_code_identity_manifest_sha256": source.canonical_sha256(
            identities
        ),
        "all_head_blobs_match_current_bytes": True,
        "all_scoped_paths_clean": True,
    }
    closure["dependency_closure_sha256"] = source.canonical_sha256(closure)
    digest = f"sha256:{_digest('runtime-image')}"
    monkeypatch.setenv(batch.IMAGE_DIGEST_ENV, digest)
    monkeypatch.setenv(batch.IMAGE_REFERENCE_ENV, f"fixture/image@{digest}")
    monkeypatch.setenv(batch.IMAGE_SOURCE_COMMIT_ENV, commit)
    attestation = batch._build_loaded_runtime_attestation_v1(
        dependency_closure=closure
    )
    assert len(attestation["loaded_modules"]) == len(
        batch.EXECUTED_DEPENDENCY_MODULE_PATHS
    )
    assert attestation["image_digest"] == digest
    assert attestation[
        "all_critical_callables_bound_to_measured_modules"
    ] is True
    revalidation = batch._revalidate_publisher_runtime_with_current_v1(
        publisher_attestation=attestation,
        current_attestation=attestation,
        dependency_closure=closure,
    )
    assert revalidation["critical_callable_code_identities_equal"] is True
    substituted = deepcopy(attestation)
    substituted["critical_callables"][0]["code_sha256"] = _digest(
        "substituted-code"
    )
    substituted["critical_callable_manifest_sha256"] = source.canonical_sha256(
        substituted["critical_callables"]
    )
    substituted["runtime_attestation_sha256"] = source.canonical_sha256({
        key: value
        for key, value in substituted.items()
        if key != "runtime_attestation_sha256"
    })
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="differs from committed measured source",
    ):
        batch._revalidate_publisher_runtime_with_current_v1(
            publisher_attestation=substituted,
            current_attestation=attestation,
            dependency_closure=closure,
        )
    with monkeypatch.context() as scoped:
        scoped.setattr(
            release_v1,
            "build_matchup_source_export_v2",
            lambda **_kwargs: {},
        )
        with pytest.raises(
            batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
            match="critical loaded callable differs",
        ):
            batch._build_loaded_runtime_attestation_v1(
                dependency_closure=closure
            )
    monkeypatch.setattr(
        operator,
        "publish_matchup_source_triple_v2",
        lambda **_kwargs: {},
    )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="critical loaded callable differs",
    ):
        batch._build_loaded_runtime_attestation_v1(
            dependency_closure=closure
        )


def test_batch_publish_materializes_54_in_order_and_requests_root_last(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()
    reopened = _candidate_authority_fixture()
    prefix = batch.output_prefix_for_run_v1("fixture-batch-0001")
    plan_sha = _digest("plan")
    fixed_replay_identity = _identity(
        "gs://fixture-catalog/replay.json", "replay"
    )
    catalog_release_identity = _identity(
        "gs://fixture-catalog/catalog-release.json", "catalog-release"
    )
    plan = {
        "capture_plan_sha256": plan_sha,
        "fixed_g0_candidate_authority_root_identity": reopened.root_identity,
        "fixed_g0_replay_receipt_identity": fixed_replay_identity,
        "catalog_release_identity": catalog_release_identity,
        "accepted_candidate_release_identity": reopened.candidate_release_identity,
        "producer_id": "fixture-producer",
        "producer_release_id": "fixture-producer-release",
        "producer_namespace": "gs://fixture-producer/components/",
        "component_producer_code_identity": _code(
            capture_v1.COMPONENT_PRODUCER_MODULE_PATH, "producer"
        ),
        "source_v2_code_identity": _code(
            capture_v1.SOURCE_V2_MODULE_PATH, "source"
        ),
        "upstream_source_release_identity": _identity(
            "gs://fixture-upstream/upstream-release.json", "upstream"
        ),
        "upstream_source_release_sha256": _digest("upstream-internal"),
        "source_task_bindings": [
            {
                "source_task_ordinal": ordinal,
                "task_id": entry["task_id"],
                "slate": entry["slate"],
                "catalog_identity": entry["catalog_identity"],
                "candidate_artifact_identity": entry[
                    "candidate_artifact_identity"
                ],
            }
            for ordinal, entry in enumerate(
                reopened.candidate_release["entries"]
            )
        ],
    }
    capture_binding = _capture_binding(plan_sha)
    producer_release_identity = _identity(
        "gs://fixture-producer/components/producer-release.json", "producer"
    )
    component_entries = []
    bundles = []
    bundle_ids = []
    receipts = []
    receipt_ids = []
    catalogs = []
    for ordinal, candidate_entry in enumerate(
        reopened.candidate_release["entries"]
    ):
        component_entries.append({
            "source_task_ordinal": ordinal,
            "slate": candidate_entry["slate"],
            "catalog_identity": candidate_entry["catalog_identity"],
            "input_bundle_identity": _identity(
                f"gs://fixture-producer/bundle-{ordinal}.json", f"bundle-{ordinal}"
            ),
            "producer_receipt_identity": _identity(
                f"gs://fixture-producer/receipt-{ordinal}.json", f"receipt-{ordinal}"
            ),
            "support_preflight_passed": True,
        })
        bundles.append({"fixture": f"bundle-{ordinal}"})
        bundle_ids.append(component_entries[-1]["input_bundle_identity"])
        receipts.append({"fixture": f"receipt-{ordinal}"})
        receipt_ids.append(component_entries[-1]["producer_receipt_identity"])
        catalogs.append({"fixture": f"catalog-{ordinal}"})
    component_result = {
        "publication_receipt": {
            "catalog_release_identity": catalog_release_identity,
            "catalog_release_sha256": _digest("catalog-release-internal"),
            "candidate_authority_component_publication_receipt_sha256": _digest(
                "component-receipt"
            ),
            "producer_release_identity": producer_release_identity,
            "producer_release_sha256": _digest("producer-release-internal"),
        },
        "component_publication_result": {
            "offline_panel": {
                "entries": component_entries,
                "input_bundles": bundles,
                "input_bundle_identities": bundle_ids,
                "producer_receipts": receipts,
                "producer_receipt_identities": receipt_ids,
                "producer_release": {
                    "producer_release_sha256": _digest("producer-release-internal")
                },
                "producer_release_identity": producer_release_identity,
            }
        },
    }
    source_release: dict[str, object] = {}
    source_identity: dict[str, object] = {}
    published_triples: list[dict[str, object]] = []
    events: list[str] = []
    authority_calls = 0

    def reopen_authority(*_args: object, **_kwargs: object):
        nonlocal authority_calls
        authority_calls += 1
        return reopened

    monkeypatch.setattr(
        candidate_authority,
        "reopen_fixed_g0_candidate_authority_release_v1",
        reopen_authority,
    )
    monkeypatch.setattr(
        batch, "_validate_plan_with_cached_authority",
        lambda value, **_kwargs: dict(value),
    )
    monkeypatch.setattr(
        batch, "_validate_capture_plan_binding",
        lambda **_kwargs: dict(capture_binding),
    )

    def fake_code(
        identity: Mapping[str, object], *, expected_path: str, **_kwargs: object
    ):
        effective = dict(identity)
        binding = {
            "primary_code_identity": effective,
            "repair_sha256": None,
            "effective_code_identity": effective,
        }
        assert effective["module_path"] == expected_path
        return effective, binding

    monkeypatch.setattr(batch, "_validate_code_identity", fake_code)
    dependency_closure = _dependency_closure()

    def replay_dependencies(**_kwargs: object) -> dict[str, object]:
        events.append("dependency-closure")
        return dependency_closure

    monkeypatch.setattr(
        batch,
        "_replay_executed_dependency_closure",
        replay_dependencies,
    )

    def publish_component(**_kwargs: object) -> dict[str, object]:
        events.append("component-publication")
        return component_result

    monkeypatch.setattr(
        batch, "_publish_component_with_cached_authority",
        publish_component,
    )
    monkeypatch.setattr(
        batch,
        "_validate_component_receipt_with_cached_authority",
        lambda value, **_kwargs: dict(value),
    )

    def fake_operator(**kwargs: Any) -> dict[str, object]:
        ordinal = int(kwargs["source_task_ordinal"])
        events.append(f"triple-{ordinal:02d}")
        return _triple(
            ordinal=ordinal,
            prefix=str(kwargs["output_prefix"]),
            candidate_entry=reopened.candidate_release["entries"][ordinal],
        )

    monkeypatch.setattr(operator, "publish_matchup_source_triple_v2", fake_operator)

    def fake_source_root(**kwargs: Any) -> dict[str, object]:
        nonlocal source_release, source_identity, published_triples
        published_triples = [dict(value) for value in kwargs["triples"]]
        source_members = []
        for ordinal, triple in enumerate(published_triples):
            component_entry = component_entries[ordinal]
            source_members.append({
                "source_task_ordinal": ordinal,
                "task_id": triple["task_id"],
                "slate": triple["slate"],
                "catalog_identity": reopened.candidate_release["entries"][ordinal][
                    "catalog_identity"
                ],
                "candidate_artifact_identity": triple[
                    "candidate_artifact_identity"
                ],
                "producer_receipt_identity": component_entry[
                    "producer_receipt_identity"
                ],
                "input_bundle_identity": component_entry["input_bundle_identity"],
                "source_export_identity": triple["source_export_identity"],
                "capture_receipt_identity": triple["capture_receipt_identity"],
                "operator_result_identity": triple["operator_result_identity"],
            })
        source_release = {
            "release_id": "fixture-batch-0001",
            "namespace": prefix,
            "capture_plan_binding": capture_binding,
            "candidate_authority_root_identity": reopened.root_identity,
            "accepted_candidate_release_identity": reopened.candidate_release_identity,
            "catalog_release_identity": component_result["publication_receipt"][
                "catalog_release_identity"
            ],
            "upstream_source_release_identity": plan[
                "upstream_source_release_identity"
            ],
            "operator_code_identity": _code(
                operator.OPERATOR_MODULE_PATH, "operator"
            ),
            "producer_release_identity": producer_release_identity,
            "producer_release_sha256": component_result[
                "component_publication_result"
            ]["offline_panel"]["producer_release"]["producer_release_sha256"],
            "entries": source_members,
            "matchup_source_release_candidate_authority_sha256": _digest(
                "source-release-internal"
            ),
        }
        raw = source.canonical_json_bytes(source_release)
        source_identity = dict(kwargs["publish_create_once"](
            f"{prefix}{release_v2.ROOT_FILENAME}", raw
        ))
        assert kwargs["read_exact"](source_identity) == raw
        return {"release": source_release, "release_identity": source_identity}

    monkeypatch.setattr(
        batch, "_publish_terminal_source_release_with_cached_authority",
        fake_source_root,
    )
    inventory_entries = []

    def add_inventory(uri: str, phase: str) -> None:
        inventory_entries.append({"uri": uri, "phase": phase})

    add_inventory(
        f"{prefix}{batch.COMPONENT_RECEIPT_FILENAME}",
        "batch-component-receipt",
    )
    for ordinal, entry in enumerate(reopened.candidate_release["entries"]):
        slate_id = str(entry["slate"]["slate_id"])
        add_inventory(
            f"{prefix}source-task-{ordinal:02d}-{slate_id}/batch-member.json",
            "batch-member",
        )
    add_inventory(
        f"{prefix}{release_v2.ROOT_FILENAME}", "source-release-root"
    )
    add_inventory(
        f"{prefix}{batch.PUBLICATION_WORK_RECEIPT_FILENAME}",
        "preterminal-publication-work-receipt",
    )
    add_inventory(f"{prefix}{batch.ROOT_FILENAME}", "terminal-batch-root")
    inventory_entries.sort(key=lambda value: str(value["uri"]))
    inventory_uris = [str(value["uri"]) for value in inventory_entries]
    inventory = {
        "schema_version": batch.OUTPUT_URI_INVENTORY_SCHEMA,
        "run_id": "fixture-batch-0001",
        "namespace": prefix,
        "producer_namespace": plan["producer_namespace"],
        "entries": inventory_entries,
        "uris": inventory_uris,
        "uri_count": len(inventory_uris),
        "uri_manifest_sha256": source.canonical_sha256(inventory_uris),
        "entry_manifest_sha256": source.canonical_sha256(inventory_entries),
        "publication_work_receipt_uri": (
            f"{prefix}{batch.PUBLICATION_WORK_RECEIPT_FILENAME}"
        ),
        "terminal_root_uri": f"{prefix}{batch.ROOT_FILENAME}",
        "inventory_derived_before_write_client_construction": True,
        "broad_prefix_write_authority_allowed": False,
        "unexpected_uri_backend_call_possible": False,
    }
    inventory["output_uri_inventory_sha256"] = source.canonical_sha256(
        inventory
    )
    gcs_client = _GCSClient()
    gcs_client.event_sink = events
    gcs_client.mirror_store = store
    publication_transport = batch.GenerationPinnedGCSBatchTransportV1(
        gcs_client, expected_write_uris=inventory_uris
    )
    capture_replay = {
        "capture_plan_git_replay_sha256": _digest("capture-git-replay")
    }
    runtime_attestation = {
        "source_commit_sha": "a" * 40,
        "runtime_attestation_sha256": _digest("runtime-attestation"),
    }
    monkeypatch.setattr(
        batch,
        "_output_uri_inventory_v1",
        lambda **_kwargs: dict(inventory),
    )
    monkeypatch.setattr(
        batch,
        "_normalize_capture_plan_git_replay_v1",
        lambda value, **_kwargs: dict(value),
    )
    monkeypatch.setattr(
        batch,
        "_normalize_runtime_attestation_v1",
        lambda value, **_kwargs: dict(value),
    )

    result = batch._publish_matchup_source_batch_candidate_authority_with_adapters_v1(
        run_id="fixture-batch-0001",
        candidate_authority_root_identity=reopened.root_identity,
        capture_plan=plan,
        capture_plan_binding=capture_binding,
        capture_plan_git_replay=capture_replay,
        adapter_final_release_lock_commit_sha="b" * 40,
        adapter_final_release_lock_raw=b"fixture\n",
        fixed_g0_replay_receipt={"fixture": True},
        fixed_g0_replay_receipt_identity=fixed_replay_identity,
        catalog_release={"fixture": True},
        catalog_release_identity=component_result["publication_receipt"][
            "catalog_release_identity"
        ],
        structural_catalogs=catalogs,
        upstream_source_release={"fixture": True},
        upstream_source_release_identity=plan[
            "upstream_source_release_identity"
        ],
        upstream_pack_row_objects=[],
        operator_code_identity=_code(operator.OPERATOR_MODULE_PATH, "operator"),
        orchestrator_code_identity=_code(batch.BATCH_MODULE_PATH, "batch"),
        repository_root=Path("."),
        git_head=lambda _root: "a" * 40,
        git_blob=lambda _root, _commit, _path: b"fixture",
        git_status=lambda _root, _paths: b"",
        publish_create_once=publication_transport.publish_create_once,
        read_exact=publication_transport.read_exact,
        output_uri_inventory=inventory,
        publication_transport=publication_transport,
        runtime_attestation=runtime_attestation,
    )
    assert authority_calls == 1
    first_slate_id = str(
        reopened.candidate_release["entries"][0]["slate"]["slate_id"]
    )
    assert events[:5] == [
        "dependency-closure",
        "component-publication",
        f"{prefix}{batch.COMPONENT_RECEIPT_FILENAME}",
        "triple-00",
        f"{prefix}source-task-00-{first_slate_id}/batch-member.json",
    ]
    assert events[-5:] == [
        "dependency-closure",
        f"{prefix}{release_v2.ROOT_FILENAME}",
        f"{prefix}{batch.PUBLICATION_WORK_RECEIPT_FILENAME}",
        "dependency-closure",
        f"{prefix}{batch.ROOT_FILENAME}",
    ]
    assert events.count("dependency-closure") == 3
    assert result["batch_release"]["task_count"] == source.TASK_COUNT
    assert len(result["batch_release"]["members"]) == source.TASK_COUNT
    assert result["result_panel"]["candidate_authority_full_replay_count"] == 1
    assert result["batch_release_identity"]["uri"] == (
        f"{prefix}{batch.ROOT_FILENAME}"
    )
    component_receipt_identity = result["batch_release"][
        "component_publication_receipt_identity"
    ]
    assert component_receipt_identity["uri"] == (
        f"{prefix}{batch.COMPONENT_RECEIPT_FILENAME}"
    )
    assert json.loads(store.read(component_receipt_identity)) == component_result[
        "publication_receipt"
    ]
    missing = deepcopy(result["batch_release"])
    missing["members"].pop()
    missing["member_descriptor_manifest_sha256"] = source.canonical_sha256(
        missing["members"]
    )
    missing["batch_release_sha256"] = source.canonical_sha256({
        key: value
        for key, value in missing.items()
        if key != "batch_release_sha256"
    })
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="exactly 54",
    ):
        batch.validate_batch_release_structure_v1(missing)

    reordered = deepcopy(result["batch_release"])
    reordered["members"][0], reordered["members"][1] = (
        reordered["members"][1], reordered["members"][0]
    )
    reordered["member_descriptor_manifest_sha256"] = source.canonical_sha256(
        reordered["members"]
    )
    reordered["member_identity_manifest_sha256"] = source.canonical_sha256([
        descriptor["batch_member_identity"] for descriptor in reordered["members"]
    ])
    reordered["batch_release_sha256"] = source.canonical_sha256({
        key: value
        for key, value in reordered.items()
        if key != "batch_release_sha256"
    })
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="order/identity",
    ):
        batch.validate_batch_release_structure_v1(reordered)

    producer_body = {
        "producer_release_sha256": _digest("producer-release-internal"),
        "catalog_release_identity": component_result["publication_receipt"][
            "catalog_release_identity"
        ],
        "accepted_candidate_release_identity": reopened.candidate_release_identity,
        "upstream_source_release_identity": plan[
            "upstream_source_release_identity"
        ],
        "producer_code_identity": plan["component_producer_code_identity"],
    }
    monkeypatch.setattr(
        capture_v2, "validate_capture_plan_lock_v2", lambda _value: plan
    )
    monkeypatch.setattr(
        release_v2,
        "validate_matchup_source_release_candidate_authority_v2",
        lambda value: dict(value),
    )
    monkeypatch.setattr(release_v2, "_project_release_v1", lambda value: value)
    monkeypatch.setattr(
        release_v1, "_parse_exact", lambda *_args, **_kwargs: producer_body
    )
    monkeypatch.setattr(
        release_v1,
        "_producer_release_shape",
        lambda value, **_kwargs: dict(value),
    )

    def fake_deep(*, ordinal: int, **_kwargs: object) -> dict[str, object]:
        triple = published_triples[ordinal]
        return {
            "candidate_artifact": reopened.candidate_release["entries"][ordinal][
                "candidate_artifact"
            ],
            "producer_receipt": {"support_preflight_passed": True},
            "source_export": triple["source_export"],
            "capture_receipt": triple["capture_receipt"],
            "operator_result": triple["operator_result"],
        }

    monkeypatch.setattr(
        release_v1,
        "_reopen_validated_matchup_source_release_ordinal_v1",
        fake_deep,
    )
    monkeypatch.setattr(
        release_v2, "_selected_candidate_binding", lambda **_kwargs: {}
    )
    monkeypatch.setattr(
        batch,
        "_durable_reopen_component_receipt",
        lambda value, **_kwargs: dict(value),
    )

    plan_raw = source.canonical_json_bytes(plan) + b"\n"

    def reopen_git_blob(_root: Path, _commit: str, path: str) -> bytes:
        if path == capture_binding["relative_path"]:
            return plan_raw
        return Path(path).read_bytes()

    reopened_result = (
        batch._reopen_matchup_source_batch_candidate_authority_with_adapters_v1(
            batch_release_identity=result["batch_release_identity"],
            repository_root=Path("."),
            read_exact=store.read,
            git_head=lambda _root: "a" * 40,
            git_blob=reopen_git_blob,
            git_status=lambda _root, _paths: b"",
        )
    )
    assert reopened_result["batch_release"] == result["batch_release"]
    assert reopened_result["candidate_authority_full_replay_count"] == 1
    assert authority_calls == 2

    def retain_mutated_object(
        body: Mapping[str, object], *, uri: str,
    ) -> dict[str, object]:
        store.generation += 1
        raw = source.canonical_json_bytes(body)
        identity = _identity_for_raw(uri, raw, store.generation)
        store.objects[(uri, str(identity["generation"]))] = raw
        return identity

    mutated_member = deepcopy(
        result["batch_release"]["members"][0]
    )
    member_identity = mutated_member["batch_member_identity"]
    original_member_raw = store.read(member_identity)
    original_member = deepcopy(json.loads(original_member_raw.decode("utf-8")))
    original_member["candidate_count"] += 1
    original_member["batch_member_sha256"] = source.canonical_sha256({
        key: value
        for key, value in original_member.items()
        if key != "batch_member_sha256"
    })
    mutated_member_identity = retain_mutated_object(
        original_member, uri=str(member_identity["uri"])
    )
    mutated_member["candidate_count"] += 1
    mutated_member["batch_member_identity"] = mutated_member_identity
    mutated_member["batch_member_sha256"] = original_member[
        "batch_member_sha256"
    ]
    mutated_root = deepcopy(result["batch_release"])
    mutated_root["members"][0] = mutated_member
    mutated_root["total_candidate_count"] += 1
    mutated_root["member_identity_manifest_sha256"] = source.canonical_sha256([
        descriptor["batch_member_identity"]
        for descriptor in mutated_root["members"]
    ])
    mutated_root["member_descriptor_manifest_sha256"] = source.canonical_sha256(
        mutated_root["members"]
    )
    mutated_root["batch_release_sha256"] = source.canonical_sha256({
        key: value
        for key, value in mutated_root.items()
        if key != "batch_release_sha256"
    })
    mutated_root_identity = retain_mutated_object(
        mutated_root,
        uri=f"{prefix}{batch.ROOT_FILENAME}",
    )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="exact reconstruction differs",
    ):
        batch._reopen_matchup_source_batch_candidate_authority_with_adapters_v1(
            batch_release_identity=mutated_root_identity,
            repository_root=Path("."),
            read_exact=store.read,
            git_head=lambda _root: "a" * 40,
            git_blob=reopen_git_blob,
            git_status=lambda _root, _paths: b"",
        )

    mutated_metadata_root = deepcopy(result["batch_release"])
    mutated_metadata_root["upstream_source_release_sha256"] = _digest(
        "coherent-false-upstream-sha"
    )
    mutated_metadata_root["batch_release_sha256"] = source.canonical_sha256({
        key: value
        for key, value in mutated_metadata_root.items()
        if key != "batch_release_sha256"
    })
    mutated_metadata_identity = retain_mutated_object(
        mutated_metadata_root,
        uri=f"{prefix}{batch.ROOT_FILENAME}",
    )
    with pytest.raises(
        batch.CorpusR6MatchupBatchCandidateAuthorityV1Error,
        match="exact reconstruction differs",
    ):
        batch._reopen_matchup_source_batch_candidate_authority_with_adapters_v1(
            batch_release_identity=mutated_metadata_identity,
            repository_root=Path("."),
            read_exact=store.read,
            git_head=lambda _root: "a" * 40,
            git_blob=reopen_git_blob,
            git_status=lambda _root, _paths: b"",
        )


def test_leaf_operator_publishes_dependency_order_and_exact_reopens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()
    prefix = "gs://fixture-terminal/source-task-00-s00/"
    export = {
        "task_id": "task-00",
        "slate": {"season": 2023, "week": 1, "slate_id": "s00"},
        "matchup_source_export_sha256": _digest("export-internal"),
    }
    capture = {"matchup_capture_receipt_sha256": _digest("capture-internal")}
    result_body = {"matchup_operator_result_sha256": _digest("result-internal")}
    calls: list[str] = []

    monkeypatch.setattr(
        release_v1,
        "build_matchup_source_export_v2",
        lambda **_kwargs: calls.append("build-export") or export,
    )

    def build_capture(**kwargs: object) -> dict[str, object]:
        assert kwargs["source_export"] == export
        assert kwargs["source_export_identity"]["uri"] == (
            f"{prefix}matchup-source-export.json"
        )
        calls.append("build-capture")
        return capture

    monkeypatch.setattr(release_v1, "build_matchup_capture_receipt_v2", build_capture)

    def build_result(**kwargs: object) -> dict[str, object]:
        assert kwargs["capture_receipt"] == capture
        assert kwargs["capture_receipt_identity"]["uri"] == (
            f"{prefix}matchup-capture-receipt.json"
        )
        calls.append("build-result")
        return result_body

    monkeypatch.setattr(release_v1, "build_matchup_operator_result_v2", build_result)
    operator_kwargs = {
        "source_task_ordinal": 0,
        "output_prefix": prefix,
        "capture_plan_binding": _capture_binding(_digest("plan")),
        "operator_code_identity": _code(
            operator.OPERATOR_MODULE_PATH, "operator"
        ),
        "producer_release_identity": _identity(
            "gs://fixture/producer.json", "producer"
        ),
        "producer_receipt": {"fixture": "receipt"},
        "producer_receipt_identity": _identity(
            "gs://fixture/receipt.json", "receipt"
        ),
        "input_bundle": {"fixture": "bundle"},
        "input_bundle_identity": _identity(
            "gs://fixture/bundle.json", "bundle"
        ),
        "structural_catalog": {"fixture": "catalog"},
        "catalog_identity": _identity(
            "gs://fixture/catalog.json", "catalog"
        ),
        "candidate_artifact_identity": _identity(
            "gs://fixture/candidate.json", "candidate"
        ),
        "publish_create_once": store.publish,
        "read_exact": store.read,
    }
    triple = operator.publish_matchup_source_triple_v2(**operator_kwargs)
    assert calls == ["build-export", "build-capture", "build-result"]
    assert [uri for event, uri in store.events if event == "publish"] == [
        f"{prefix}matchup-source-export.json",
        f"{prefix}matchup-capture-receipt.json",
        f"{prefix}matchup-operator-result.json",
    ]
    assert triple["all_three_exact_reopened"] is True
    assert triple["promotion_eligible"] is False
    assert triple["outcome_freedom_status"][
        "independent_source_lineage_attested"
    ] is False
    assert triple["create_once_resume_policy"] == (
        operator.CREATE_ONCE_RESUME_POLICY
    )
    generations = {
        key: triple[key]
        for key in (
            "source_export_identity",
            "capture_receipt_identity",
            "operator_result_identity",
        )
    }
    resumed = operator.publish_matchup_source_triple_v2(**operator_kwargs)
    assert {
        key: resumed[key] for key in generations
    } == generations
    assert resumed["partial_triple_exact_equal_resume_allowed"] is True
    assert store.generation == 1003


def test_leaf_operator_stops_before_dependents_when_exact_reopen_differs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = _Store()
    prefix = "gs://fixture-terminal/source-task-00-s00/"
    export = {
        "task_id": "task-00",
        "slate": {"season": 2023, "week": 1, "slate_id": "s00"},
        "matchup_source_export_sha256": _digest("export-internal"),
    }
    monkeypatch.setattr(
        release_v1, "build_matchup_source_export_v2", lambda **_kwargs: export
    )
    capture_calls: list[object] = []
    monkeypatch.setattr(
        release_v1,
        "build_matchup_capture_receipt_v2",
        lambda **kwargs: capture_calls.append(kwargs) or {},
    )

    def corrupt_read(identity: Mapping[str, object]) -> bytes:
        return store.read(identity) + b"x"

    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV2Error,
        match="content identity differs",
    ):
        operator.publish_matchup_source_triple_v2(
            source_task_ordinal=0,
            output_prefix=prefix,
            capture_plan_binding=_capture_binding(_digest("plan")),
            operator_code_identity=_code(operator.OPERATOR_MODULE_PATH, "operator"),
            producer_release_identity=_identity(
                "gs://fixture/producer.json", "producer"
            ),
            producer_receipt={},
            producer_receipt_identity=_identity(
                "gs://fixture/receipt.json", "receipt"
            ),
            input_bundle={},
            input_bundle_identity=_identity(
                "gs://fixture/bundle.json", "bundle"
            ),
            structural_catalog={},
            catalog_identity=_identity("gs://fixture/catalog.json", "catalog"),
            candidate_artifact_identity=_identity(
                "gs://fixture/candidate.json", "candidate"
            ),
            publish_create_once=store.publish,
            read_exact=corrupt_read,
        )
    assert capture_calls == []
    assert len([event for event in store.events if event[0] == "publish"]) == 1


def test_leaf_operator_rejects_different_bytes_create_once_collision() -> None:
    store = _Store()
    uri = "gs://fixture-terminal/source-task-00-s00/matchup-source-export.json"
    store.publish(uri, source.canonical_json_bytes({"foreign": True}))
    store.events.clear()
    with pytest.raises(
        operator.CorpusR6MatchupSourceOperatorV2Error,
        match="create-once publication failed",
    ):
        operator._publish_json(
            {"expected": True},
            uri=uri,
            publish_create_once=store.publish,
            read_exact=store.read,
            label="matchup source export",
        )
    assert store.latest[uri]["generation"] == "1001"
    assert [event for event, _uri in store.events] == ["publish"]
