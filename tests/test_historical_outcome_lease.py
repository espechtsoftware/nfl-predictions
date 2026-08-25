from __future__ import annotations

from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from nfl_dfs.research import corpus_core_v1_outcome_supply as core
from nfl_dfs.research import corpus_parametric_batch as batch


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "historical_outcome_lease_test", SCRIPTS / "historical_outcome_lease.py"
)
assert SPEC is not None and SPEC.loader is not None
lease_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(lease_tool)


RUN_ID = "core-outcome-fixture"
JOB = "atlas-minimal-c-s2023-w1-v1"
CODE_SHA = "a" * 40
IMAGE = "us-central1-docker.pkg.dev/fixture/image@sha256:" + "b" * 64
COMPLETION_URI = f"{lease_tool.CORE_OUTCOME_PREFIX}/{RUN_ID}/completion.json"
ATTEMPT_URI = f"{lease_tool.CORE_OUTCOME_PREFIX}/{RUN_ID}/read-attempt.json"


def _parts(uri: str) -> tuple[str, str]:
    return tuple(uri.removeprefix("gs://").split("/", 1))  # type: ignore[return-value]


class _FakeBlob:
    def __init__(
        self, client: "_FakeStorage", bucket: str, name: str,
        generation: int | None,
    ) -> None:
        self._client = client
        self._bucket = bucket
        self._name = name
        self.generation = generation

    def reload(self, *, if_generation_match: int | None = None) -> None:
        key = (self._bucket, self._name)
        generation = self.generation
        if generation is None:
            generation = self._client.current[key]
            self.generation = generation
            self._client.current_resolutions.append(key)
        if if_generation_match is not None and generation != if_generation_match:
            raise RuntimeError("generation precondition failed")
        if generation not in self._client.objects[key]:
            raise RuntimeError("object generation absent")

    def download_as_bytes(
        self, *, if_generation_match: int | None = None,
    ) -> bytes:
        key = (self._bucket, self._name)
        generation = self.generation
        if generation is None:
            generation = self._client.current[key]
        if if_generation_match is not None and generation != if_generation_match:
            raise RuntimeError("generation precondition failed")
        self._client.pinned_downloads.append((key, generation))
        return self._client.objects[key][generation]

    def delete(self, *, if_generation_match: int) -> None:
        key = (self._bucket, self._name)
        if self.generation != if_generation_match:
            raise RuntimeError("delete generation precondition failed")
        del self._client.objects[key][if_generation_match]
        if self._client.current.get(key) == if_generation_match:
            del self._client.current[key]
        self._client.deleted.append((key, if_generation_match))


class _FakeBucket:
    def __init__(self, client: "_FakeStorage", name: str) -> None:
        self._client = client
        self._name = name

    def blob(self, name: str, generation: int | None = None) -> _FakeBlob:
        return _FakeBlob(self._client, self._name, name, generation)


class _FakeStorage:
    """Known-name fake deliberately has no object-listing interface."""

    def __init__(self) -> None:
        self.objects: dict[tuple[str, str], dict[int, bytes]] = {}
        self.current: dict[tuple[str, str], int] = {}
        self.current_resolutions: list[tuple[str, str]] = []
        self.pinned_downloads: list[tuple[tuple[str, str], int]] = []
        self.deleted: list[tuple[tuple[str, str], int]] = []

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self, name)

    def put(self, uri: str, generation: int, raw: bytes) -> None:
        key = _parts(uri)
        self.objects.setdefault(key, {})[generation] = raw
        self.current[key] = generation


def _identity(uri: str, generation: int, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _placeholder(uri: str, marker: str) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": "1",
        "sha256": marker * 64,
        "bytes": 1,
    }


def _execution(path: Path, *, completed: str = "True") -> None:
    path.write_text(json.dumps({
        "metadata": {"name": (
            "projects/fixture/locations/us-central1/jobs/fixture/executions/"
            f"{JOB}-execution-00001"
        )},
        "status": {
            "conditions": [{"type": "Completed", "status": completed}],
            "completionTime": "2026-08-25T17:00:00Z",
        },
    }), encoding="utf-8")


def _fixture(
    tmp_path: Path,
) -> tuple[_FakeStorage, Path, dict[str, object], bytes]:
    client = _FakeStorage()
    lease_body = {
        "version": "historical-outcome-active-v1",
        "run_id": RUN_ID,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": "2026-08-25T16:00:00+00:00",
    }
    lease_raw = (
        json.dumps(lease_body, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    lease_identity = {
        **_identity(lease_tool.LEASE_URI, 71, lease_raw),
        "create_only": True,
    }
    client.put(lease_tool.LEASE_URI, 71, lease_raw)
    receipt_path = tmp_path / "lease-receipt.json"
    receipt_path.write_text(
        json.dumps(
            {"lease": lease_body, "object": lease_identity},
            sort_keys=True,
            separators=(",", ":"),
        ) + "\n",
        encoding="utf-8",
    )

    catalog_identity = _placeholder("gs://fixture/catalog.json", "c")
    catalog_sha256 = "d" * 64
    source_freeze_identity = _placeholder("gs://fixture/freeze.json", "1")
    outcome_keys = [{"player_id": "fixture-player"}]
    query_contract = {"job_id": "fixture-job"}
    table_receipts = [{"table_id": "fixture.table"}]
    attempt = {
        "schema_version": core.ATTEMPT_SCHEMA,
        "run_id": RUN_ID,
        "catalog_identity": catalog_identity,
        "catalog_sha256": catalog_sha256,
        "later_source_freeze_identity": source_freeze_identity,
        "later_source_freeze_sha256": "2" * 64,
        "outcome_key_count": 9,
        "outcome_keys": outcome_keys,
        "outcome_keys_sha256": core.canonical_sha256(outcome_keys),
        "query_contract": query_contract,
        "query_contract_sha256": core.canonical_sha256(query_contract),
        "table_receipts_before_query": table_receipts,
        "table_receipt_set_sha256": core.canonical_sha256(table_receipts),
        "historical_outcome_lease": {
            "body": lease_body,
            "object_receipt": lease_identity,
        },
        "started_at": "2026-08-25T16:01:00+00:00",
        "uses_realized_outcomes_at_creation": False,
        "attempt_precedes_query": True,
        "historical_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    assert set(attempt) == core._ATTEMPT_KEYS - {"attempt_sha256"}  # noqa: SLF001
    attempt["attempt_sha256"] = core.canonical_sha256(attempt)
    attempt_raw = batch.canonical_json_bytes(attempt)
    client.put(ATTEMPT_URI, 72, attempt_raw)
    attempt_identity = _identity(ATTEMPT_URI, 72, attempt_raw)

    completion: dict[str, object] = {
        "schema_version": core.COMPLETION_SCHEMA,
        "run_id": RUN_ID,
        "catalog_identity": catalog_identity,
        "catalog_sha256": catalog_sha256,
        "attempt_identity": attempt_identity,
        "player_source_identity": _placeholder("gs://fixture/source.json", "e"),
        "outcome_snapshot_identity": _placeholder(
            "gs://fixture/snapshot.json", "f"
        ),
        "outcome_key_count": 9,
        "one_historical_outcome_read": True,
        "independent_source_snapshot_replay_complete": True,
        "rank_available": False,
        "roi_available": False,
        "rank_roi_unavailable_reason": (
            "full_field_standings_and_payout_ladder_not_supplied"
        ),
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": core.LEASE_RELEASE_OWNER,
        "historical_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    completion["completion_sha256"] = core.canonical_sha256(completion)
    completion_raw = batch.canonical_json_bytes(completion)
    client.put(COMPLETION_URI, 73, completion_raw)
    return client, receipt_path, completion, completion_raw


def test_core_completion_materializes_and_releases_from_exact_known_objects(
    tmp_path: Path,
) -> None:
    client, receipt_path, completion, _ = _fixture(tmp_path)
    strict_path = tmp_path / "strict-completion.txt"

    rows = lease_tool.materialize_core_v1_completion(
        receipt_path=receipt_path,
        completion_uri=COMPLETION_URI,
        output_path=strict_path,
        storage_client=client,
    )
    assert rows["schema_version"] == lease_tool.CORE_STRICT_COMPLETION_SCHEMA
    assert rows["completion_generation"] == "73"
    assert rows["completion_self_sha256"] == completion["completion_sha256"]
    assert rows["attempt_generation"] == "72"
    assert rows["historical_outcome_lease_generation"] == "71"
    before = strict_path.read_bytes()
    lease_tool.materialize_core_v1_completion(
        receipt_path=receipt_path,
        completion_uri=COMPLETION_URI,
        output_path=strict_path,
        storage_client=client,
    )
    assert strict_path.read_bytes() == before
    assert _parts(COMPLETION_URI) in client.current_resolutions
    assert _parts(ATTEMPT_URI) in client.current_resolutions

    execution_path = tmp_path / "execution.json"
    _execution(execution_path)
    lease_tool.release(
        receipt_path=receipt_path,
        execution_path=execution_path,
        completion_path=strict_path,
        storage_client=client,
    )
    assert client.deleted == [(_parts(lease_tool.LEASE_URI), 71)]


def test_materializer_rejects_rehashed_false_release_flag(
    tmp_path: Path,
) -> None:
    client, receipt_path, completion, _ = _fixture(tmp_path)
    completion["one_historical_outcome_read"] = False
    completion.pop("completion_sha256")
    completion["completion_sha256"] = core.canonical_sha256(completion)
    client.put(COMPLETION_URI, 74, batch.canonical_json_bytes(completion))
    strict_path = tmp_path / "strict-completion.txt"

    with pytest.raises(RuntimeError, match="completion release law differs"):
        lease_tool.materialize_core_v1_completion(
            receipt_path=receipt_path,
            completion_uri=COMPLETION_URI,
            output_path=strict_path,
            storage_client=client,
        )
    assert not strict_path.exists()
    assert _parts(lease_tool.LEASE_URI) in client.current


def test_core_release_rejects_replaced_completion_generation(
    tmp_path: Path,
) -> None:
    client, receipt_path, _, completion_raw = _fixture(tmp_path)
    strict_path = tmp_path / "strict-completion.txt"
    lease_tool.materialize_core_v1_completion(
        receipt_path=receipt_path,
        completion_uri=COMPLETION_URI,
        output_path=strict_path,
        storage_client=client,
    )
    client.put(COMPLETION_URI, 74, completion_raw)
    execution_path = tmp_path / "execution.json"
    _execution(execution_path)

    with pytest.raises(RuntimeError, match="completion object changed"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution_path,
            completion_path=strict_path,
            storage_client=client,
        )
    assert _parts(lease_tool.LEASE_URI) in client.current


def test_core_artifact_cannot_downgrade_to_legacy_when_schema_is_removed(
    tmp_path: Path,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    strict_path = tmp_path / "strict-completion.txt"
    lease_tool.materialize_core_v1_completion(
        receipt_path=receipt_path,
        completion_uri=COMPLETION_URI,
        output_path=strict_path,
        storage_client=client,
    )
    strict_path.write_text(
        "\n".join(
            line for line in strict_path.read_text(encoding="utf-8").splitlines()
            if not line.startswith("schema_version=")
        ) + "\n",
        encoding="utf-8",
    )
    execution_path = tmp_path / "execution.json"
    _execution(execution_path)

    with pytest.raises(RuntimeError, match="strict completion keys differ"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution_path,
            completion_path=strict_path,
            storage_client=client,
        )
    assert _parts(lease_tool.LEASE_URI) in client.current


def test_materializer_rejects_noncanonical_attempt_uri_and_forged_lease_size(
    tmp_path: Path,
) -> None:
    client, receipt_path, completion, _ = _fixture(tmp_path)
    attempt_raw = client.objects[_parts(ATTEMPT_URI)][72]
    alternate_attempt_uri = (
        f"{lease_tool.CORE_OUTCOME_PREFIX}/{RUN_ID}/alternate-attempt.json"
    )
    client.put(alternate_attempt_uri, 75, attempt_raw)
    completion["attempt_identity"] = _identity(
        alternate_attempt_uri, 75, attempt_raw
    )
    completion.pop("completion_sha256")
    completion["completion_sha256"] = core.canonical_sha256(completion)
    client.put(COMPLETION_URI, 74, batch.canonical_json_bytes(completion))

    with pytest.raises(RuntimeError, match="read attempt URI differs"):
        lease_tool.materialize_core_v1_completion(
            receipt_path=receipt_path,
            completion_uri=COMPLETION_URI,
            output_path=tmp_path / "wrong-attempt.txt",
            storage_client=client,
        )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt["object"]["bytes"] += 1
    receipt_path.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="active lease changed"):
        lease_tool.materialize_core_v1_completion(
            receipt_path=receipt_path,
            completion_uri=COMPLETION_URI,
            output_path=tmp_path / "wrong-lease-size.txt",
            storage_client=client,
        )
    assert _parts(lease_tool.LEASE_URI) in client.current


def test_release_requires_success_and_preserves_legacy_completion(
    tmp_path: Path,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    legacy = tmp_path / "legacy-completion.txt"
    legacy.write_text(
        f"run_id={RUN_ID}\nuses_realized_outcomes=true\ndisposition=complete\n",
        encoding="utf-8",
    )
    execution_path = tmp_path / "execution.json"
    _execution(execution_path, completed="False")
    with pytest.raises(RuntimeError, match="execution is not terminal"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution_path,
            completion_path=legacy,
            storage_client=client,
        )
    assert _parts(lease_tool.LEASE_URI) in client.current

    _execution(execution_path, completed="True")
    lease_tool.release(
        receipt_path=receipt_path,
        execution_path=execution_path,
        completion_path=legacy,
        storage_client=client,
    )
    assert client.deleted == [(_parts(lease_tool.LEASE_URI), 71)]
