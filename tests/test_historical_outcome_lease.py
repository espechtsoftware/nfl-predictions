from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import importlib.util
import json
from pathlib import Path
import sys

import pytest

from nfl_dfs.research import corpus_core_v1_outcome_supply as core
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as r6_outcome
from nfl_dfs.research import corpus_r6_full_union_outcome_supply_v1 as r6_supply
from nfl_dfs.research import corpus_r6_full_union_grade_release_v1 as grade_release
from nfl_dfs.research import corpus_r6_full_union_realized_grading_v1 as grading


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
        self.time_created = None

    def reload(self, *, if_generation_match: int | None = None) -> None:
        key = (self._bucket, self._name)
        generation = self.generation
        if generation is None:
            try:
                generation = self._client.current[key]
            except KeyError as exc:
                raise lease_tool.NotFound("object absent") from exc
            self.generation = generation
            self._client.current_resolutions.append(key)
        if if_generation_match is not None and generation != if_generation_match:
            raise RuntimeError("generation precondition failed")
        if generation not in self._client.objects[key]:
            raise lease_tool.NotFound("object generation absent")
        self.time_created = self._client.created_at[(key, generation)]

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
        self.created_at: dict[
            tuple[tuple[str, str], int], datetime
        ] = {}

    def bucket(self, name: str) -> _FakeBucket:
        return _FakeBucket(self, name)

    def put(
        self, uri: str, generation: int, raw: bytes,
        *, created_at: datetime | None = None,
    ) -> None:
        key = _parts(uri)
        self.objects.setdefault(key, {})[generation] = raw
        self.current[key] = generation
        self.created_at[(key, generation)] = created_at or datetime(
            2026, 8, 26, 12, 0, tzinfo=timezone.utc
        )


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


def _r6_strict_rows(
    lease_body: dict[str, object], lease_identity: dict[str, object],
) -> dict[str, str]:
    def values(prefix: str, marker: str) -> dict[str, str]:
        return {
            f"{prefix}_uri": f"gs://fixture/{prefix}.json",
            f"{prefix}_generation": "9",
            f"{prefix}_sha256": marker * 64,
            f"{prefix}_bytes": "10",
        }

    rows = {
        "schema_version": lease_tool.R6_STRICT_COMPLETION_SCHEMA,
        "run_id": str(lease_body["run_id"]),
        "job": str(lease_body["job"]),
        "execution": f"{lease_body['job']}-execution-00001",
        "code_sha": str(lease_body["code_sha"]),
        "image": str(lease_body["image"]),
        "service_account": lease_tool.R6_DEFAULT_COMPUTE_SERVICE_ACCOUNT,
        "grade_stage_token": "a" * 64,
        "uses_realized_outcomes": "true",
        "disposition": lease_tool.R6_STRICT_DISPOSITION,
        "supply_completion_self_sha256": "1" * 64,
        "grade_completion_self_sha256": "2" * 64,
        "persisted_grade_root_self_sha256": "3" * 64,
        "one_historical_outcome_read": "true",
        "one_exact_query_job": "true",
        "canonical_persisted_grade_replay_complete": "true",
        "terminal_execution_envelope_validation_required": "true",
        "historical_outcome_lease_release_required": "true",
        **values("supply_completion", "4"),
        **values("attempt", "5"),
        **values("query_evidence", "6"),
        **values("grade_completion", "7"),
        **values("persisted_grade_root", "8"),
        **values("panel_freeze", "9"),
        **values("actual_root_smoke_receipt", "a"),
        **values("outcome_key_projection", "b"),
        **values("realized_source", "c"),
        **values("outcome_snapshot", "d"),
        "snapshot_module_sha256": "e" * 64,
        "snapshot_cli_sha256": "f" * 64,
        "snapshot_test_sha256": "0" * 64,
        "snapshot_cli_test_sha256": "1" * 64,
        "historical_outcome_lease_uri": str(lease_identity["uri"]),
        "historical_outcome_lease_generation": str(
            lease_identity["generation"]
        ),
        "historical_outcome_lease_sha256": str(lease_identity["sha256"]),
        "historical_outcome_lease_bytes": str(lease_identity["bytes"]),
    }
    assert set(rows) == lease_tool._R6_STRICT_COMPLETION_KEYS  # noqa: SLF001
    return rows


def _r6_recovery_strict_rows(
    lease_body: dict[str, object], lease_identity: dict[str, object],
) -> dict[str, str]:
    rows = _r6_strict_rows(lease_body, lease_identity)
    recovery_root = (
        f"{lease_tool.R6_OUTCOME_PREFIX}/{lease_body['run_id']}"
        "/recoveries/supply-attempt-02"
    )
    rows.update({
        "schema_version": lease_tool.R6_RECOVERY_STRICT_COMPLETION_SCHEMA,
        "disposition": lease_tool.R6_RECOVERY_STRICT_DISPOSITION,
        "recovery_intent_uri": f"{recovery_root}/recovery-intent.json",
        "recovery_intent_generation": "10",
        "recovery_intent_sha256": "2" * 64,
        "recovery_intent_bytes": "11",
        "recovery_intent_self_sha256": "3" * 64,
        "recovery_receipt_uri": f"{recovery_root}/recovery-receipt.json",
        "recovery_receipt_generation": "12",
        "recovery_receipt_sha256": "4" * 64,
        "recovery_receipt_bytes": "13",
        "recovery_receipt_self_sha256": "5" * 64,
        "recovery_ordinal": "2",
        "recovery_receipt_required": "true",
        "distinct_query_job_count": "1",
        "total_query_submission_count": "1",
        "recovery_query_submission_count": "0",
        "new_job_count": "0",
        "physical_fixed_job_result_retrieval_count": "2",
        "failed_result_validation_count": "1",
        "successful_result_validation_count": "1",
        "distinct_outcome_snapshot_count": "1",
        "one_historical_outcome_read_definition": (
            lease_tool.R6_LOGICAL_OUTCOME_READ_DEFINITION
        ),
    })
    assert set(rows) == (  # noqa: SLF001
        lease_tool._R6_RECOVERY_STRICT_COMPLETION_KEYS
    )
    return rows


def _recovery_evidence_fixture(
    client: _FakeStorage,
    lease_body: dict[str, object],
    lease_identity: dict[str, object],
) -> tuple[str, dict[str, object], dict[str, object]]:
    recovery_root = (
        f"{lease_tool.R6_OUTCOME_PREFIX}/{lease_body['run_id']}"
        "/recoveries/supply-attempt-02"
    )
    intent_uri = f"{recovery_root}/recovery-intent.json"
    receipt_uri = f"{recovery_root}/recovery-receipt.json"
    supply_replay: dict[str, object] = {
        "attempt_identity": _placeholder(
            f"{lease_tool.R6_OUTCOME_PREFIX}/{lease_body['run_id']}"
            "/read-attempt.json",
            "1",
        ),
        "query_evidence_identity": _placeholder(
            f"{lease_tool.R6_OUTCOME_PREFIX}/{lease_body['run_id']}"
            "/query-evidence.json",
            "2",
        ),
        "realized_source_identity": _placeholder(
            f"{lease_tool.R6_OUTCOME_PREFIX}/{lease_body['run_id']}"
            "/realized-source.json",
            "3",
        ),
        "outcome_snapshot_identity": _placeholder(
            f"{lease_tool.R6_OUTCOME_PREFIX}/{lease_body['run_id']}"
            "/outcome-snapshot.json",
            "4",
        ),
        "completion_identity": _placeholder(
            f"{lease_tool.R6_OUTCOME_PREFIX}/{lease_body['run_id']}"
            "/completion.json",
            "5",
        ),
        "query_evidence": {
            "query_job_receipt": {"job_id": "fixed-job"},
            "query_job_disposition": "recovered",
        },
    }
    retained_lease_identity = {
        key: lease_identity[key]
        for key in ("uri", "generation", "sha256", "bytes")
    }
    intent: dict[str, object] = {
        "recovery_intent_sha256": "6" * 64,
        "recovery_ordinal": 2,
        "run_id": lease_body["run_id"],
        "cloud_run_job": lease_body["job"],
        "original_runtime": {
            "code_sha": lease_body["code_sha"],
            "image": lease_body["image"],
            "service_account": lease_tool.R6_DEFAULT_COMPUTE_SERVICE_ACCOUNT,
        },
        "historical_outcome_lease_identity": retained_lease_identity,
    }
    intent_raw = batch.canonical_json_bytes(intent)
    client.put(intent_uri, 101, intent_raw)
    intent_identity = _identity(intent_uri, 101, intent_raw)
    standard = {
        label: supply_replay[f"{label}_identity"]
        for label in (
            "attempt", "query_evidence", "realized_source",
            "outcome_snapshot", "completion",
        )
    }
    receipt: dict[str, object] = {
        "recovery_receipt_sha256": "7" * 64,
        "recovery_intent_identity": intent_identity,
        "standard_artifact_identities": standard,
        "fixed_query_job": {"job_id": "fixed-job"},
        "distinct_query_job_count": 1,
        "total_query_submission_count": 1,
        "job_submission_count": 0,
        "new_job_count": 0,
        "cumulative_fixed_job_result_retrieval_count": 2,
        "failed_result_validation_count": 1,
        "successful_result_validation_count": 1,
        "distinct_outcome_snapshot_count": 1,
        "recovery_closed": True,
        "automatic_retry_licensed": False,
        "additional_recovery_licensed": False,
    }
    client.put(receipt_uri, 102, batch.canonical_json_bytes(receipt))
    return receipt_uri, supply_replay, receipt


@pytest.mark.parametrize(
    ("service_account", "accepted"),
    [
        ("817589974517-compute@developer.gserviceaccount.com", True),
        (
            "r6-score-runtime@"
            "nfl-predictions-503414.iam.gserviceaccount.com",
            True,
        ),
        ("817589974517-compute@other-project.iam.gserviceaccount.com", False),
        ("-invalid@nfl-predictions-503414.iam.gserviceaccount.com", False),
    ],
)
def test_r6_service_account_contract_accepts_only_explicit_project_forms(
    service_account: str, accepted: bool,
) -> None:
    assert lease_tool._valid_r6_service_account(service_account) is accepted


def test_r6_recovery_release_evidence_exact_reopens_and_binds_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import recover_corpus_r6_full_union_outcome_supply_v1 as recovery

    client, receipt_path, _, _ = _fixture(tmp_path)
    lease_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    lease_body = lease_receipt["lease"]
    lease_identity = lease_receipt["object"]
    receipt_uri, supply_replay, _ = _recovery_evidence_fixture(
        client, lease_body, lease_identity
    )
    validations: list[str] = []

    def validate_intent(value: object) -> dict[str, object]:
        validations.append("intent")
        return dict(value)  # type: ignore[arg-type]

    def validate_receipt(
        value: object, **_: object,
    ) -> dict[str, object]:
        validations.append("receipt")
        return dict(value)  # type: ignore[arg-type]

    monkeypatch.setattr(recovery, "validate_recovery_intent_v1", validate_intent)
    monkeypatch.setattr(
        recovery, "validate_recovery_receipt_v1", validate_receipt
    )
    replay = lease_tool._validate_r6_recovery_evidence(  # noqa: SLF001
        client=client,
        required_recovery_receipt_uri=receipt_uri,
        supply_replay=supply_replay,
        lease=lease_body,
        lease_object=lease_identity,
        expected_service_account=lease_tool.R6_DEFAULT_COMPUTE_SERVICE_ACCOUNT,
    )

    assert validations == ["intent", "receipt"]
    assert replay["intent_identity"]["generation"] == "101"
    assert replay["receipt_identity"]["generation"] == "102"
    assert _parts(receipt_uri) in client.current_resolutions
    assert _parts(receipt_uri.replace(
        "recovery-receipt.json", "recovery-intent.json"
    )) in client.current_resolutions
    assert (
        (_parts(receipt_uri), 102) in client.pinned_downloads
    )


@pytest.mark.parametrize(
    ("field", "wrong"),
    [
        ("distinct_query_job_count", 2),
        ("total_query_submission_count", 2),
        ("job_submission_count", 1),
        ("new_job_count", 1),
        ("cumulative_fixed_job_result_retrieval_count", 1),
        ("failed_result_validation_count", 0),
        ("successful_result_validation_count", 0),
        ("distinct_outcome_snapshot_count", 2),
    ],
)
def test_r6_recovery_release_evidence_rejects_false_accounting(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    field: str, wrong: int,
) -> None:
    import recover_corpus_r6_full_union_outcome_supply_v1 as recovery

    client, receipt_path, _, _ = _fixture(tmp_path)
    lease_receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_uri, supply_replay, receipt = _recovery_evidence_fixture(
        client, lease_receipt["lease"], lease_receipt["object"]
    )
    receipt[field] = wrong
    client.put(receipt_uri, 103, batch.canonical_json_bytes(receipt))
    monkeypatch.setattr(
        recovery, "validate_recovery_intent_v1", lambda value: dict(value)
    )
    monkeypatch.setattr(
        recovery,
        "validate_recovery_receipt_v1",
        lambda value, **_: dict(value),
    )

    with pytest.raises(RuntimeError, match="release binding differs"):
        lease_tool._validate_r6_recovery_evidence(  # noqa: SLF001
            client=client,
            required_recovery_receipt_uri=receipt_uri,
            supply_replay=supply_replay,
            lease=lease_receipt["lease"],
            lease_object=lease_receipt["object"],
            expected_service_account=(
                lease_tool.R6_DEFAULT_COMPUTE_SERVICE_ACCOUNT
            ),
        )


def _write_rows(path: Path, rows: dict[str, str]) -> None:
    path.write_text(
        "".join(f"{key}={rows[key]}\n" for key in sorted(rows)),
        encoding="utf-8",
    )


def _execution(
    path: Path, *, completed: str = "True",
    r6_rows: dict[str, str] | None = None,
) -> None:
    args = (
        lease_tool._r6_grade_cli_args(r6_rows)  # noqa: SLF001
        if r6_rows is not None
        else ["--run-id", RUN_ID, "--code-sha", CODE_SHA, "--image", IMAGE]
    )
    env = [] if r6_rows is None else [
        {"name": "R6_CHAIN_STAGE_TOKEN", "value": r6_rows["grade_stage_token"]},
        {"name": "R6_FULL_UNION_REALIZED_GRADE_ENABLED", "value": "1"},
        {"name": "R6_FULL_UNION_REVIEWED_CODE_SHA", "value": CODE_SHA},
        {"name": "R6_FULL_UNION_RUNTIME_IMAGE", "value": IMAGE},
    ]
    path.write_text(json.dumps({
        "metadata": {"name": (
            "projects/fixture/locations/us-central1/jobs/fixture/executions/"
            f"{JOB}-execution-00001"
        ), "labels": {"run.googleapis.com/job": JOB}},
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": {
                "maxRetries": 0,
                "timeoutSeconds": "28800",
                "serviceAccountName": (
                    r6_rows["service_account"] if r6_rows is not None
                    else "fixture@nfl-predictions-503414.iam.gserviceaccount.com"
                ),
                "volumes": [],
                "containers": [{
                    "image": IMAGE,
                    "command": ["python"],
                    "args": args,
                    "env": env,
                    "volumeMounts": [],
                    "resources": {"limits": {"cpu": "8", "memory": "32Gi"}},
                }],
            }},
        },
        "status": {
            "conditions": [{"type": "Completed", "status": completed}],
            "completionTime": "2026-08-25T17:00:00Z",
            "succeededCount": 1 if completed == "True" else 0,
            "failedCount": 0 if completed == "True" else 1,
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


def test_resolve_generation_pins_exact_owner_and_is_create_or_equal(
    tmp_path: Path,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    expected = json.loads(receipt_path.read_text(encoding="utf-8"))
    receipt_path.unlink()

    resolved = lease_tool.resolve(
        run_id=RUN_ID,
        job=JOB,
        code_sha=CODE_SHA,
        image=IMAGE,
        receipt_path=receipt_path,
        storage_client=client,
    )
    assert resolved == expected
    before = receipt_path.read_bytes()
    assert lease_tool.resolve(
        run_id=RUN_ID,
        job=JOB,
        code_sha=CODE_SHA,
        image=IMAGE,
        receipt_path=receipt_path,
        storage_client=client,
    ) == expected
    assert receipt_path.read_bytes() == before
    assert _parts(lease_tool.LEASE_URI) in client.current_resolutions
    assert (_parts(lease_tool.LEASE_URI), 71) in client.pinned_downloads


@pytest.mark.parametrize("field", ["run_id", "job", "code_sha", "image"])
def test_resolve_rejects_every_nonowner_coordinate(
    tmp_path: Path, field: str,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    receipt_path.unlink()
    values = {
        "run_id": RUN_ID,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
    }
    values[field] = {
        "run_id": "other-outcome-fixture",
        "job": "different-existing-job",
        "code_sha": "c" * 40,
        "image": "us-central1-docker.pkg.dev/fixture/other@sha256:" + "d" * 64,
    }[field]

    with pytest.raises(RuntimeError, match="not the exact requested owner"):
        lease_tool.resolve(
            **values,
            receipt_path=receipt_path,
            storage_client=client,
        )
    assert not receipt_path.exists()


def test_resolve_rejects_different_existing_local_receipt(tmp_path: Path) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    receipt_path.write_text("not-the-receipt\n", encoding="utf-8")
    with pytest.raises(RuntimeError, match="local evidence differs"):
        lease_tool.resolve(
            run_id=RUN_ID,
            job=JOB,
            code_sha=CODE_SHA,
            image=IMAGE,
            receipt_path=receipt_path,
            storage_client=client,
        )


def test_acquire_crash_before_atomic_local_receipt_is_exactly_resolvable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client = _FakeStorage()
    receipt_path = tmp_path / "lease.json"
    original_write = lease_tool._write_create_or_equal  # noqa: SLF001

    monkeypatch.setattr(lease_tool.storage, "Client", lambda **_: client)

    def upload_create_only(
        retained_client: _FakeStorage, uri: str, raw: bytes,
    ) -> dict[str, object]:
        assert retained_client is client
        client.put(uri, 90, raw)
        return {**_identity(uri, 90, raw), "create_only": True}

    monkeypatch.setattr(lease_tool, "_upload_create_only", upload_create_only)
    monkeypatch.setattr(
        lease_tool,
        "_write_create_or_equal",
        lambda path, raw: (_ for _ in ()).throw(
            RuntimeError("simulated local receipt crash")
        ),
    )
    with pytest.raises(RuntimeError, match="simulated local receipt crash"):
        lease_tool.acquire(
            run_id=RUN_ID,
            job=JOB,
            code_sha=CODE_SHA,
            image=IMAGE,
            receipt_path=receipt_path,
        )
    assert not receipt_path.exists()
    assert client.current[_parts(lease_tool.LEASE_URI)] == 90

    monkeypatch.setattr(lease_tool, "_write_create_or_equal", original_write)
    resolved = lease_tool.resolve(
        run_id=RUN_ID,
        job=JOB,
        code_sha=CODE_SHA,
        image=IMAGE,
        receipt_path=receipt_path,
        storage_client=client,
    )
    assert resolved["object"]["generation"] == "90"  # type: ignore[index]
    assert receipt_path.is_file()


def test_referenced_object_retains_generation_pinned_creation_time(
    tmp_path: Path,
) -> None:
    del tmp_path
    client = _FakeStorage()
    uri = "gs://fixture/durable-attempt.json"
    raw = batch.canonical_json_bytes({"value": "attempt"})
    published = datetime(2026, 8, 26, 12, 10, tzinfo=timezone.utc)
    client.put(uri, 8, raw, created_at=published)

    identity, body, retained_raw, created_at = (
        lease_tool._resolve_referenced_current(  # noqa: SLF001
            client,
            _identity(uri, 8, raw),
            expected_uri=uri,
            label="durable attempt",
        )
    )
    assert identity == _identity(uri, 8, raw)
    assert body == {"value": "attempt"}
    assert retained_raw == raw
    assert created_at == published
    assert (_parts(uri), 8) in client.pinned_downloads


def test_r6_query_ending_before_durable_attempt_publication_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    run_id = RUN_ID
    prefix = f"{lease_tool.R6_OUTCOME_PREFIX}/{run_id}"
    uris = {
        "projection": f"{prefix}/outcome-key-projection.json",
        "smoke": f"{prefix}/actual-root-smoke-receipt.json",
        "attempt": f"{prefix}/read-attempt.json",
        "query_evidence": f"{prefix}/query-evidence.json",
        "source": f"{prefix}/realized-source.json",
        "snapshot": f"{prefix}/outcome-snapshot.json",
    }
    identities = {
        label: _placeholder(uri, str(index))
        for index, (label, uri) in enumerate(uris.items(), start=1)
    }
    lease = {
        "version": "historical-outcome-active-v1",
        "run_id": run_id,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": "2026-08-26T11:50:00+00:00",
    }
    lease_object = {
        **_placeholder(lease_tool.LEASE_URI, "a"),
        "create_only": True,
    }
    expected_lease = {"body": lease, "object_receipt": lease_object}
    durable_publication = datetime(
        2026, 8, 26, 12, 10, tzinfo=timezone.utc
    )
    objects: dict[str, dict[str, object]] = {
        "projection": {},
        "smoke": {
            "snapshot_module_sha256": "2" * 64,
            "snapshot_cli_sha256": "3" * 64,
            "snapshot_test_sha256": "4" * 64,
            "snapshot_cli_test_sha256": "5" * 64,
        },
        "attempt": {
            "historical_outcome_lease": expected_lease,
            "started_at": "2026-08-26T12:00:00+00:00",
            "table_receipts_before_query": [],
            "query_contract": {},
        },
        "query_evidence": {
            "query_job_receipt": {
                "ended_at": "2026-08-26T12:05:00+00:00"
            }
        },
        "source": {},
        "snapshot": {},
    }
    completion = {
        "run_id": run_id,
        "panel_freeze_identity": _placeholder("gs://fixture/panel.json", "b"),
        "panel_freeze_object_sha256": "c" * 64,
        **{
            {
                "projection": "outcome_key_projection_identity",
                "smoke": "actual_root_smoke_receipt_identity",
                "attempt": "attempt_identity",
                "query_evidence": "query_evidence_identity",
                "source": "realized_source_identity",
                "snapshot": "outcome_snapshot_identity",
            }[label]: identity
            for label, identity in identities.items()
        },
    }
    completion_uri = f"{prefix}/completion.json"
    completion_raw = batch.canonical_json_bytes(completion)
    completion_identity = _identity(completion_uri, 99, completion_raw)
    independent_pins = {
        "snapshot_module_sha256": "e" * 64,
        "snapshot_cli_sha256": "f" * 64,
        "snapshot_test_sha256": "0" * 64,
        "snapshot_cli_test_sha256": "1" * 64,
    }
    observed: dict[str, object] = {}

    def resolve_reference(
        client: object, value: object, *, expected_uri: str, label: str,
    ) -> tuple[dict[str, object], dict[str, object], bytes, datetime]:
        del client, label
        retained = dict(value)  # type: ignore[arg-type]
        object_label = next(key for key, uri in uris.items() if uri == expected_uri)
        created_at = (
            durable_publication
            if object_label == "attempt"
            else datetime(2026, 8, 26, 12, 0, tzinfo=timezone.utc)
        )
        return retained, objects[object_label], b"{}", created_at

    def validate_smoke(*args: object, **kwargs: object):
        del args
        observed["smoke_snapshot_pins"] = {
            key: kwargs[f"expected_{key}"] for key in independent_pins
        }
        return objects["smoke"], identities["smoke"]

    def reject_early_query(*args: object, **kwargs: object):
        del args
        observed["attempt_created_at"] = kwargs["attempt_created_at"]
        ended_at = datetime.fromisoformat(
            str(objects["query_evidence"]["query_job_receipt"]["ended_at"])
        )
        assert ended_at < kwargs["attempt_created_at"]
        raise ValueError("query ended before durable attempt publication")

    monkeypatch.setattr(
        lease_tool, "_resolve_referenced_current", resolve_reference
    )
    monkeypatch.setattr(
        r6_outcome,
        "validate_outcome_key_projection_v1",
        lambda *args, **kwargs: ({}, identities["projection"], []),
    )
    monkeypatch.setattr(
        r6_outcome, "validate_actual_root_smoke_receipt_v1", validate_smoke
    )
    monkeypatch.setattr(r6_supply, "_legacy_config", lambda *args, **kwargs: object())
    monkeypatch.setattr(r6_supply, "_table_receipts", lambda *args, **kwargs: [])
    monkeypatch.setattr(
        r6_supply,
        "_query_spec_from_contract",
        lambda *args, **kwargs: (object(), object()),
    )
    monkeypatch.setattr(
        r6_supply,
        "validate_outcome_attempt_v1",
        lambda *args, **kwargs: objects["attempt"],
    )
    monkeypatch.setattr(
        r6_supply, "validate_query_evidence_v1", reject_early_query
    )

    with pytest.raises(RuntimeError, match="supply canonical replay failed") as exc:
        lease_tool._validate_r6_supply_evidence(  # noqa: SLF001
            client=object(),
            raw=completion_raw,
            identity=completion_identity,
            lease=lease,
            lease_object=lease_object,
            expected_snapshot_code_identities=independent_pins,
        )
    assert "query ended before durable attempt publication" in str(
        exc.value.__cause__
    )
    assert observed["attempt_created_at"] == durable_publication
    assert observed["smoke_snapshot_pins"] == independent_pins


def test_r6_materializer_emits_opt_in_recovery_v2_and_preserves_v1(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path = tmp_path / "lease.json"
    receipt_path.write_text("{}\n", encoding="utf-8")
    lease = {
        "version": "historical-outcome-active-v1",
        "run_id": RUN_ID,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": "2026-08-26T12:00:00+00:00",
    }
    lease_identity = {
        **_placeholder(lease_tool.LEASE_URI, "a"),
        "create_only": True,
    }
    expected_code = {
        "snapshot_module_sha256": "e" * 64,
        "snapshot_cli_sha256": "f" * 64,
        "snapshot_test_sha256": "0" * 64,
        "snapshot_cli_test_sha256": "1" * 64,
    }
    supply_uri = f"{lease_tool.R6_OUTCOME_PREFIX}/{RUN_ID}/completion.json"
    grade_uri = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized-grades/{RUN_ID}/grade-completion.json"
    )
    recovery_uri = lease_tool._r6_recovery_receipt_uri(RUN_ID)  # noqa: SLF001
    grade_shallow = {
        "expected_supply_run_id": RUN_ID,
        "expected_supply_job": JOB,
        "expected_supply_code_sha": CODE_SHA,
        "expected_supply_image": IMAGE,
        **expected_code,
    }
    grade_raw = batch.canonical_json_bytes(grade_shallow)
    supply_raw = batch.canonical_json_bytes({"fixture": "supply"})
    supply_identity = _identity(supply_uri, 201, supply_raw)
    grade_identity = _identity(grade_uri, 202, grade_raw)
    supply_replay: dict[str, object] = {
        "completion": {"completion_sha256": "1" * 64},
        "query_evidence": {"query_job_disposition": "created"},
        "attempt_identity": _placeholder("gs://fixture/attempt.json", "2"),
        "query_evidence_identity": _placeholder(
            "gs://fixture/query-evidence.json", "3"
        ),
        "panel_freeze_identity": _placeholder(
            "gs://fixture/panel-freeze.json", "4"
        ),
        "smoke_identity": _placeholder("gs://fixture/smoke.json", "5"),
        "projection_identity": _placeholder(
            "gs://fixture/projection.json", "6"
        ),
        "realized_source_identity": _placeholder(
            "gs://fixture/realized-source.json", "7"
        ),
        "outcome_snapshot_identity": _placeholder(
            "gs://fixture/outcome-snapshot.json", "8"
        ),
        "completion_identity": supply_identity,
        "snapshot_code_identities": expected_code,
    }
    grade_replay: dict[str, object] = {
        "completion": {
            "execution": f"{JOB}-execution-00001",
            "grade_completion_sha256": "9" * 64,
        },
        "persisted_root": {"persisted_grade_root_sha256": "a" * 64},
        "persisted_root_identity": _placeholder(
            "gs://fixture/persisted-grade-root.json", "b"
        ),
    }
    recovery_root = recovery_uri.rsplit("/", 1)[0]
    recovery_replay: dict[str, object] = {
        "intent": {"recovery_intent_sha256": "c" * 64},
        "intent_identity": _placeholder(
            f"{recovery_root}/recovery-intent.json", "d"
        ),
        "receipt": {"recovery_receipt_sha256": "e" * 64},
        "receipt_identity": _placeholder(recovery_uri, "f"),
    }
    recovery_calls: list[str] = []
    materializer_client = _FakeStorage()

    monkeypatch.setattr(
        lease_tool,
        "_verified_lease_blob",
        lambda *args, **kwargs: (
            materializer_client, lease, lease_identity, object(), b"lease"
        ),
    )

    def resolve(_client: object, uri: str, **_: object):
        if uri == grade_uri:
            return grade_identity, grade_raw
        if uri == supply_uri:
            return supply_identity, supply_raw
        raise AssertionError(f"unexpected URI {uri}")

    monkeypatch.setattr(lease_tool, "_resolve_current_exact", resolve)
    monkeypatch.setattr(
        lease_tool, "_validate_r6_supply_evidence",
        lambda **_: supply_replay,
    )
    monkeypatch.setattr(
        lease_tool, "_validate_r6_grade_evidence",
        lambda **_: grade_replay,
    )

    def validate_recovery(**kwargs: object) -> dict[str, object]:
        recovery_calls.append(str(kwargs["required_recovery_receipt_uri"]))
        return recovery_replay

    monkeypatch.setattr(
        lease_tool, "_validate_r6_recovery_evidence", validate_recovery
    )
    common = {
        "receipt_path": receipt_path,
        "supply_completion_uri": supply_uri,
        "grade_completion_uri": grade_uri,
        "expected_service_account": lease_tool.R6_DEFAULT_COMPUTE_SERVICE_ACCOUNT,
        "expected_grade_stage_token": "7" * 64,
        "expected_snapshot_module_sha256": expected_code[
            "snapshot_module_sha256"
        ],
        "expected_snapshot_cli_sha256": expected_code["snapshot_cli_sha256"],
        "expected_snapshot_test_sha256": expected_code[
            "snapshot_test_sha256"
        ],
        "expected_snapshot_cli_test_sha256": expected_code[
            "snapshot_cli_test_sha256"
        ],
    }
    v1 = lease_tool.materialize_r6_full_union_completion(
        **common, output_path=tmp_path / "strict-v1.txt"
    )
    supply_replay["query_evidence"] = {
        "query_job_disposition": "recovered"
    }
    recovered_v1 = lease_tool.materialize_r6_full_union_completion(
        **common, output_path=tmp_path / "recovered-v1.txt"
    )
    supply_replay["query_evidence"] = {"query_job_disposition": "created"}
    with pytest.raises(RuntimeError, match="cannot bind ordinal-2"):
        lease_tool.materialize_r6_full_union_completion(
            **common,
            required_recovery_receipt_uri=recovery_uri,
            output_path=tmp_path / "created-as-v2.txt",
        )
    supply_replay["query_evidence"] = {
        "query_job_disposition": "recovered"
    }
    with pytest.raises(RuntimeError, match="required.*receipt is absent"):
        lease_tool.materialize_r6_full_union_completion(
            **common,
            required_recovery_receipt_uri=recovery_uri,
            output_path=tmp_path / "absent-recovery-v2.txt",
        )
    materializer_client.put(
        recovery_uri, 203, batch.canonical_json_bytes({"receipt": "present"})
    )
    with pytest.raises(RuntimeError, match="cannot downgrade to v1"):
        lease_tool.materialize_r6_full_union_completion(
            **common, output_path=tmp_path / "recovery-downgrade.txt"
        )
    v2 = lease_tool.materialize_r6_full_union_completion(
        **common,
        required_recovery_receipt_uri=recovery_uri,
        output_path=tmp_path / "strict-v2.txt",
    )

    assert set(v1) == lease_tool._R6_STRICT_COMPLETION_KEYS  # noqa: SLF001
    assert v1["schema_version"] == lease_tool.R6_STRICT_COMPLETION_SCHEMA
    assert recovered_v1 == v1
    assert set(v2) == (  # noqa: SLF001
        lease_tool._R6_RECOVERY_STRICT_COMPLETION_KEYS
    )
    assert v2["schema_version"] == (
        lease_tool.R6_RECOVERY_STRICT_COMPLETION_SCHEMA
    )
    assert v2["one_historical_outcome_read"] == "true"
    assert v2["one_historical_outcome_read_definition"] == (
        lease_tool.R6_LOGICAL_OUTCOME_READ_DEFINITION
    )
    assert v2["physical_fixed_job_result_retrieval_count"] == "2"
    assert v2["recovery_query_submission_count"] == "0"
    assert recovery_calls == [recovery_uri]


def test_r6_materializer_rejects_grade_snapshot_hash_self_expectation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    receipt_path = tmp_path / "lease.json"
    receipt_path.write_text("{}\n", encoding="utf-8")
    lease = {
        "version": "historical-outcome-active-v1",
        "run_id": RUN_ID,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "acquired_at": "2026-08-26T12:00:00+00:00",
    }
    lease_identity = {
        **_placeholder(lease_tool.LEASE_URI, "a"),
        "create_only": True,
    }
    grade_uri = (
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized-grades/{RUN_ID}/grade-completion.json"
    )
    grade = {
        "expected_supply_run_id": RUN_ID,
        "expected_supply_job": JOB,
        "expected_supply_code_sha": CODE_SHA,
        "expected_supply_image": IMAGE,
        "snapshot_module_sha256": "9" * 64,
        "snapshot_cli_sha256": "f" * 64,
        "snapshot_test_sha256": "0" * 64,
        "snapshot_cli_test_sha256": "1" * 64,
    }
    grade_raw = batch.canonical_json_bytes(grade)
    grade_identity = _identity(grade_uri, 4, grade_raw)
    monkeypatch.setattr(
        lease_tool,
        "_verified_lease_blob",
        lambda *args, **kwargs: (
            object(), lease, lease_identity, object(), b"lease"
        ),
    )
    monkeypatch.setattr(
        lease_tool,
        "_resolve_current_exact",
        lambda *args, **kwargs: (grade_identity, grade_raw),
    )

    with pytest.raises(RuntimeError, match="independent supply/runtime/code pins"):
        lease_tool.materialize_r6_full_union_completion(
            receipt_path=receipt_path,
            supply_completion_uri=(
                f"{lease_tool.R6_OUTCOME_PREFIX}/{RUN_ID}/completion.json"
            ),
            grade_completion_uri=grade_uri,
            output_path=tmp_path / "strict.txt",
            expected_service_account=(
                "r6-score-runtime@"
                "nfl-predictions-503414.iam.gserviceaccount.com"
            ),
            expected_grade_stage_token="7" * 64,
            expected_snapshot_module_sha256="e" * 64,
            expected_snapshot_cli_sha256="f" * 64,
            expected_snapshot_test_sha256="0" * 64,
            expected_snapshot_cli_test_sha256="1" * 64,
        )


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


def test_r6_release_never_falls_through_legacy_and_checks_terminal_envelope(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = _r6_strict_rows(receipt["lease"], receipt["object"])
    strict = tmp_path / "r6-strict.txt"
    _write_rows(strict, rows)
    execution = tmp_path / "grade-execution.json"
    _execution(execution, r6_rows=rows)
    replay_calls: list[dict[str, str]] = []

    def replay(**_: object) -> dict[str, str]:
        replay_calls.append(rows)
        return rows

    monkeypatch.setattr(
        lease_tool, "materialize_r6_full_union_completion", replay
    )
    release_intent = tmp_path / "release-intent.json"
    release_receipt = tmp_path / "release-receipt.json"
    lease_tool.release(
        receipt_path=receipt_path,
        execution_path=execution,
        completion_path=strict,
        storage_client=client,
        required_contract="r6-full-union",
        release_intent_path=release_intent,
        release_receipt_path=release_receipt,
    )
    assert replay_calls == [rows]
    assert client.deleted == [(_parts(lease_tool.LEASE_URI), 71)]
    intent = json.loads(release_intent.read_text(encoding="utf-8"))
    deletion = json.loads(release_receipt.read_text(encoding="utf-8"))
    assert lease_tool.validate_release_receipt_local(
        lease_receipt_path=receipt_path,
        execution_path=execution,
        completion_path=strict,
        release_intent_path=release_intent,
        release_receipt_path=release_receipt,
    ) == deletion
    assert intent["delete_if_generation_match"] == "71"
    assert intent["strict_completion_file"]["sha256"] == sha256(
        strict.read_bytes()
    ).hexdigest()
    assert intent["terminal_execution_file"]["sha256"] == sha256(
        execution.read_bytes()
    ).hexdigest()
    assert deletion["release_intent_sha256"] == intent["release_intent_sha256"]
    assert deletion["generation_delete_complete"] is True
    assert deletion["recovered_after_delete"] is False
    release_receipt_raw = release_receipt.read_bytes()
    tampered = dict(deletion)
    tampered["release_receipt_sha256"] = "0" * 64
    release_receipt.write_bytes(lease_tool._canonical_local_json(tampered))  # noqa: SLF001
    with pytest.raises(RuntimeError, match="release receipt differs"):
        lease_tool.validate_release_receipt_local(
            lease_receipt_path=receipt_path,
            execution_path=execution,
            completion_path=strict,
            release_intent_path=release_intent,
            release_receipt_path=release_receipt,
        )
    release_receipt.write_bytes(release_receipt_raw)

    # Exact-own recovery is idempotent and never reruns strict/cloud replay.
    lease_tool.release(
        receipt_path=receipt_path,
        execution_path=execution,
        completion_path=strict,
        storage_client=client,
        required_contract="r6-full-union",
        release_intent_path=release_intent,
        release_receipt_path=release_receipt,
    )
    assert replay_calls == [rows]
    assert client.deleted == [(_parts(lease_tool.LEASE_URI), 71)]


def test_r6_recovery_v2_is_required_replayed_and_durably_bound(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    v1_rows = _r6_strict_rows(receipt["lease"], receipt["object"])
    v2_rows = _r6_recovery_strict_rows(
        receipt["lease"], receipt["object"]
    )
    recovery_uri = v2_rows["recovery_receipt_uri"]
    strict = tmp_path / "r6-strict.txt"
    execution = tmp_path / "grade-execution.json"
    release_intent = tmp_path / "release-intent.json"
    release_receipt = tmp_path / "release-receipt.json"
    _write_rows(strict, v1_rows)
    _execution(execution, r6_rows=v1_rows)

    with pytest.raises(RuntimeError, match="required recovery strict"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=strict,
            storage_client=client,
            required_contract="r6-full-union",
            release_intent_path=release_intent,
            release_receipt_path=release_receipt,
            required_recovery_receipt_uri=recovery_uri,
        )
    assert not release_intent.exists()
    assert not client.deleted

    client.put(
        recovery_uri, 80, batch.canonical_json_bytes({"receipt": "present"})
    )
    monkeypatch.setattr(
        lease_tool,
        "materialize_r6_full_union_completion",
        lambda **_: v1_rows,
    )
    with pytest.raises(RuntimeError, match="cannot release through v1"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=strict,
            storage_client=client,
            required_contract="r6-full-union",
            release_intent_path=release_intent,
            release_receipt_path=release_receipt,
        )
    assert not release_intent.exists()
    assert not client.deleted

    wrong_rows = dict(v2_rows)
    wrong_rows["physical_fixed_job_result_retrieval_count"] = "1"
    _write_rows(strict, wrong_rows)
    _execution(execution, r6_rows=wrong_rows)
    with pytest.raises(RuntimeError, match="recovery strict completion law"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=strict,
            storage_client=client,
            required_contract="r6-full-union",
            release_intent_path=release_intent,
            release_receipt_path=release_receipt,
            required_recovery_receipt_uri=recovery_uri,
        )
    assert not release_intent.exists()
    assert not client.deleted

    _write_rows(strict, v2_rows)
    _execution(execution, r6_rows=v2_rows)
    replay_uris: list[object] = []

    def replay(**kwargs: object) -> dict[str, str]:
        replay_uris.append(kwargs.get("required_recovery_receipt_uri"))
        return v2_rows

    monkeypatch.setattr(
        lease_tool, "materialize_r6_full_union_completion", replay
    )
    lease_tool.release(
        receipt_path=receipt_path,
        execution_path=execution,
        completion_path=strict,
        storage_client=client,
        required_contract="r6-full-union",
        release_intent_path=release_intent,
        release_receipt_path=release_receipt,
        required_recovery_receipt_uri=recovery_uri,
    )

    assert replay_uris == [recovery_uri]
    assert client.deleted == [(_parts(lease_tool.LEASE_URI), 71)]
    intent = json.loads(release_intent.read_text(encoding="utf-8"))
    assert intent["recovery_accounting_required"] is True
    assert intent["required_recovery_receipt"] == {
        "uri": recovery_uri,
        "generation": v2_rows["recovery_receipt_generation"],
        "sha256": v2_rows["recovery_receipt_sha256"],
        "bytes": int(v2_rows["recovery_receipt_bytes"]),
    }
    assert lease_tool.validate_release_receipt_local(
        lease_receipt_path=receipt_path,
        execution_path=execution,
        completion_path=strict,
        release_intent_path=release_intent,
        release_receipt_path=release_receipt,
        required_recovery_receipt_uri=recovery_uri,
    )["generation_delete_complete"] is True


def test_required_r6_contract_rejects_legacy_and_downgraded_r6(
    tmp_path: Path,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    execution = tmp_path / "grade-execution.json"
    _execution(execution)
    legacy = tmp_path / "legacy.txt"
    legacy.write_text(
        f"run_id={RUN_ID}\nuses_realized_outcomes=true\ndisposition=complete\n",
        encoding="utf-8",
    )
    with pytest.raises(RuntimeError, match="required strict contract differs"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=legacy,
            storage_client=client,
            required_contract="r6-full-union",
        )

    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = _r6_strict_rows(receipt["lease"], receipt["object"])
    rows.pop("schema_version")
    downgraded = tmp_path / "downgraded-r6.txt"
    _write_rows(downgraded, rows)
    with pytest.raises(RuntimeError, match="R6 full-union strict completion keys"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=downgraded,
            storage_client=client,
            required_contract="r6-full-union",
        )
    assert _parts(lease_tool.LEASE_URI) in client.current


def test_r6_release_requires_durable_intent_and_receipt_paths(
    tmp_path: Path,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    strict = tmp_path / "r6-strict.txt"
    execution = tmp_path / "grade-execution.json"
    rows = _r6_strict_rows(receipt["lease"], receipt["object"])
    _write_rows(strict, rows)
    _execution(execution, r6_rows=rows)

    with pytest.raises(RuntimeError, match="durable release paths"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=strict,
            storage_client=client,
            required_contract="r6-full-union",
        )
    assert _parts(lease_tool.LEASE_URI) in client.current


@pytest.mark.parametrize(
    ("schema", "disposition", "message"),
    [
        (
            lease_tool.CORE_STRICT_COMPLETION_SCHEMA,
            lease_tool.CORE_STRICT_DISPOSITION,
            "Core v1 strict completion keys differ",
        ),
        (
            lease_tool.R6_STRICT_COMPLETION_SCHEMA,
            lease_tool.R6_STRICT_DISPOSITION,
            "R6 full-union strict completion keys differ",
        ),
    ],
)
def test_auto_detection_rejects_strict_family_truncated_to_shared_keys(
    tmp_path: Path, schema: str, disposition: str, message: str,
) -> None:
    truncated = tmp_path / "truncated-strict.txt"
    _write_rows(truncated, {
        "schema_version": schema,
        "run_id": RUN_ID,
        "uses_realized_outcomes": "true",
        "disposition": disposition,
    })
    with pytest.raises(RuntimeError, match=message):
        lease_tool._completion_rows(truncated)  # noqa: SLF001
    client, receipt_path, _, _ = _fixture(tmp_path)
    execution = tmp_path / "execution.json"
    _execution(execution)
    family = (
        "core-v1"
        if schema == lease_tool.CORE_STRICT_COMPLETION_SCHEMA
        else "r6-full-union"
    )
    for required_contract in ("auto", family):
        with pytest.raises(RuntimeError, match=message):
            lease_tool.release(
                receipt_path=receipt_path,
                execution_path=execution,
                completion_path=truncated,
                storage_client=client,
                required_contract=required_contract,
            )
    assert _parts(lease_tool.LEASE_URI) in client.current


def test_r6_release_rejects_wrong_terminal_image_before_delete(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = _r6_strict_rows(receipt["lease"], receipt["object"])
    strict = tmp_path / "r6-strict.txt"
    _write_rows(strict, rows)
    execution = tmp_path / "grade-execution.json"
    _execution(execution, r6_rows=rows)
    payload = json.loads(execution.read_text(encoding="utf-8"))
    payload["spec"]["template"]["spec"]["containers"][0]["image"] = (
        "us-central1-docker.pkg.dev/fixture/wrong@sha256:" + "9" * 64
    )
    execution.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        lease_tool,
        "materialize_r6_full_union_completion",
        lambda **_: rows,
    )
    with pytest.raises(RuntimeError, match="terminal execution envelope differs"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=strict,
            storage_client=client,
            required_contract="r6-full-union",
            release_intent_path=tmp_path / "release-intent.json",
            release_receipt_path=tmp_path / "release-receipt.json",
        )
    assert _parts(lease_tool.LEASE_URI) in client.current


@pytest.mark.parametrize(
    "mutation",
    [
        "runner",
        "execute-flag",
        "panel-pin",
        "gate",
        "stage-token",
        "service-account",
        "volume",
    ],
)
def test_r6_release_rejects_nonexact_grade_command_and_isolation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mutation: str,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = _r6_strict_rows(receipt["lease"], receipt["object"])
    strict = tmp_path / "r6-strict.txt"
    execution = tmp_path / "grade-execution.json"
    _write_rows(strict, rows)
    _execution(execution, r6_rows=rows)
    payload = json.loads(execution.read_text(encoding="utf-8"))
    task = payload["spec"]["template"]["spec"]
    container = task["containers"][0]
    if mutation == "runner":
        container["args"][0] = "/opt/nfl-predictions/scripts/other.py"
    elif mutation == "execute-flag":
        container["args"].remove("--execute")
    elif mutation == "panel-pin":
        ordinal = next(
            index for index, value in enumerate(container["args"])
            if value.startswith("--panel-freeze-generation=")
        )
        container["args"][ordinal] = "--panel-freeze-generation=999"
    elif mutation == "gate":
        next(
            item for item in container["env"]
            if item["name"] == "R6_FULL_UNION_REALIZED_GRADE_ENABLED"
        )["value"] = "0"
    elif mutation == "stage-token":
        next(
            item for item in container["env"]
            if item["name"] == "R6_CHAIN_STAGE_TOKEN"
        )["value"] = "b" * 64
    elif mutation == "service-account":
        task["serviceAccountName"] = (
            "other-runtime@nfl-predictions-503414.iam.gserviceaccount.com"
        )
    else:
        task["volumes"] = [{"name": "inherited-secret"}]
    execution.write_text(json.dumps(payload), encoding="utf-8")
    monkeypatch.setattr(
        lease_tool,
        "materialize_r6_full_union_completion",
        lambda **_: rows,
    )

    with pytest.raises(RuntimeError, match="terminal execution envelope differs"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=strict,
            storage_client=client,
            required_contract="r6-full-union",
            release_intent_path=tmp_path / "release-intent.json",
            release_receipt_path=tmp_path / "release-receipt.json",
        )
    assert not (tmp_path / "release-intent.json").exists()
    assert _parts(lease_tool.LEASE_URI) in client.current


def test_r6_release_recovers_after_delete_without_touching_new_generation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, receipt_path, _, _ = _fixture(tmp_path)
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    rows = _r6_strict_rows(receipt["lease"], receipt["object"])
    strict = tmp_path / "r6-strict.txt"
    execution = tmp_path / "grade-execution.json"
    release_intent = tmp_path / "release-intent.json"
    release_receipt = tmp_path / "release-receipt.json"
    _write_rows(strict, rows)
    _execution(execution, r6_rows=rows)
    monkeypatch.setattr(
        lease_tool,
        "materialize_r6_full_union_completion",
        lambda **_: rows,
    )
    original_write = lease_tool._write_create_or_equal  # noqa: SLF001

    def crash_before_receipt(path: Path, raw: bytes) -> None:
        if path == release_receipt:
            raise RuntimeError("simulated crash after generation delete")
        original_write(path, raw)

    monkeypatch.setattr(
        lease_tool, "_write_create_or_equal", crash_before_receipt
    )
    with pytest.raises(RuntimeError, match="simulated crash"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=strict,
            storage_client=client,
            required_contract="r6-full-union",
            release_intent_path=release_intent,
            release_receipt_path=release_receipt,
        )
    assert release_intent.is_file()
    assert not release_receipt.exists()
    assert client.deleted == [(_parts(lease_tool.LEASE_URI), 71)]

    # A later owner may acquire the known lease name. Recovery must inspect
    # only the old generation from the durable intent and preserve the new one.
    new_lease = {
        **receipt["lease"],
        "run_id": "later-historical-owner",
        "acquired_at": "2026-08-26T19:00:00+00:00",
    }
    new_raw = (
        json.dumps(new_lease, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    client.put(lease_tool.LEASE_URI, 72, new_raw)
    monkeypatch.setattr(lease_tool, "_write_create_or_equal", original_write)
    original_execution = execution.read_bytes()
    changed_execution = json.loads(original_execution)
    changed_execution["status"]["completionTime"] = "2026-08-26T20:00:00Z"
    execution.write_text(json.dumps(changed_execution), encoding="utf-8")
    with pytest.raises(RuntimeError, match="release intent differs"):
        lease_tool.release(
            receipt_path=receipt_path,
            execution_path=execution,
            completion_path=strict,
            storage_client=client,
            required_contract="r6-full-union",
            release_intent_path=release_intent,
            release_receipt_path=release_receipt,
        )
    execution.write_bytes(original_execution)
    lease_tool.release(
        receipt_path=receipt_path,
        execution_path=execution,
        completion_path=strict,
        storage_client=client,
        required_contract="r6-full-union",
        release_intent_path=release_intent,
        release_receipt_path=release_receipt,
    )
    recovered = json.loads(release_receipt.read_text(encoding="utf-8"))
    assert recovered["recovered_after_delete"] is True
    assert client.current[_parts(lease_tool.LEASE_URI)] == 72
    assert client.objects[_parts(lease_tool.LEASE_URI)][72] == new_raw
    assert client.deleted == [(_parts(lease_tool.LEASE_URI), 71)]


def test_r6_grade_evidence_invokes_full_54_shard_canonical_replay(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    root_identity = _placeholder(
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized-grades/{RUN_ID}/"
        "realized-grade-root.json",
        "8",
    )
    grade_identity = _placeholder(
        "gs://nfl-predictions-503414-corpus-retrieval/research/"
        f"corpus-r6-full-union-realized-grades/{RUN_ID}/grade-completion.json",
        "7",
    )
    completion = {
        "execution": f"{JOB}-execution-00001",
        "persisted_grade_root_identity": root_identity,
        "source_slate_count": 54,
        "slate_grade_object_count": 54,
        "rank_80_book_count": 2592,
        "prefix_grade_count": 7776,
        "aggregate_cell_count": 144,
        "aggregate_slate_row_count": 7776,
        "every_unique_final_union_roster_scored_once": True,
        "roster_sum_operation_ceiling_equals_final_union_count": True,
        "every_book_projected_from_union_score_lookup": True,
        "all_4_14_80_prefixes_projected_from_rank_80": True,
        "actual_player_outcome_keys_exact": True,
        "canonical_persisted_grade_replay_complete": True,
        "complete": True,
        "uses_realized_outcomes": True,
        "historical_outcome_lease_release_required": True,
        "terminal_execution_envelope_validated": False,
        "terminal_execution_envelope_validation_owner": (
            grade_release.LEASE_RELEASE_OWNER
        ),
    }
    persisted = {"persisted_grade_root_sha256": "9" * 64}
    logical = {"coverage": {
        "roster_sum_operation_count": 123,
        "unique_final_union_roster_count": 123,
        "roster_sum_operation_ceiling": 123,
    }}
    calls: list[str] = []

    monkeypatch.setattr(
        lease_tool,
        "_resolve_referenced_current",
        lambda *args, **kwargs: (
            root_identity,
            persisted,
            b"{}",
            lease_tool.datetime.fromisoformat("2026-08-26T12:00:00+00:00"),
        ),
    )

    def replay(*args: object, **kwargs: object):
        calls.append("persisted-54-shard-replay")
        return persisted, root_identity, logical, [{} for _ in range(54)]

    monkeypatch.setattr(grading, "validate_persisted_realized_grade_v1", replay)
    monkeypatch.setattr(
        grade_release,
        "validate_grade_completion_v1",
        lambda *args, **kwargs: (completion, grade_identity),
    )
    supply_replay = {
        "read_exact": lambda identity: b"{}",
        "panel_freeze_identity": _placeholder("gs://fixture/panel.json", "1"),
        "completion": {},
        "completion_identity": _placeholder("gs://fixture/supply.json", "2"),
        "smoke_receipt": {},
        "smoke_identity": _placeholder("gs://fixture/smoke.json", "6"),
        "attempt": {"historical_outcome_lease": {}},
        "projection": {},
        "projection_identity": _placeholder("gs://fixture/projection.json", "3"),
        "realized_source": {},
        "realized_source_identity": _placeholder("gs://fixture/source.json", "4"),
        "outcome_snapshot": {},
        "outcome_snapshot_identity": _placeholder("gs://fixture/snapshot.json", "5"),
        "snapshot_code_identities": {
            "snapshot_module_sha256": "a" * 64,
            "snapshot_cli_sha256": "b" * 64,
            "snapshot_test_sha256": "c" * 64,
            "snapshot_cli_test_sha256": "d" * 64,
        },
    }
    lease = {
        "run_id": RUN_ID,
        "job": JOB,
        "code_sha": CODE_SHA,
        "image": IMAGE,
    }
    result = lease_tool._validate_r6_grade_evidence(  # noqa: SLF001
        client=object(),
        supply_replay=supply_replay,
        grade_completion_raw=batch.canonical_json_bytes(completion),
        grade_completion_identity=grade_identity,
        lease=lease,
    )
    assert calls == ["persisted-54-shard-replay"]
    assert result["persisted_root_identity"] == root_identity
