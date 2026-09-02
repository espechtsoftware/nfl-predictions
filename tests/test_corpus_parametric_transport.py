from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
import os
from pathlib import Path
from types import SimpleNamespace
import shlex
import subprocess
import sys

import pytest

from nfl_dfs.research import corpus_batch_evidence_contract as evidence
from nfl_dfs.research import corpus_expansion_build as expansion_build
from nfl_dfs.research import corpus_parametric_batch as batch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "run_corpus_parametric_transport",
    ROOT / "scripts" / "run_corpus_parametric_transport.py",
)
assert SPEC and SPEC.loader
transport = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = transport
SPEC.loader.exec_module(transport)

CODE_SHA = "a" * 40
BUILD_ID = "12345678-abcd-abcd-abcd-123456789abc"
IMAGE = (
    "us-central1-docker.pkg.dev/nfl-predictions-503414/"
    "nfl-dfs/nfl-dfs@sha256:" + "b" * 64
)
IMAGE_TAG = IMAGE.split("@", 1)[0] + ":cloud-validated"
SERVICE_ACCOUNT = (
    "corpus-parametric@nfl-predictions-503414.iam.gserviceaccount.com"
)
JOB_NAME = "atlas-minimal-c-s2023-w1-v1"
JOB_UID = "fixture-job-uid"
NOW = "2026-08-21T18:00:00Z"
ENABLED = {transport.ENABLE_ENV: "1"}
PLACEHOLDER_RAW: dict[tuple[str, str], bytes] = {}
FOUNDATION_PREFIX = "gs://foundation/corpus-parametric-research/test-v1/"
SOURCE_PREFIX = (
    "gs://source-authority/corpus-artifact-source/source-test-v1/"
)
RETRIEVAL_PREFIX = "gs://retrieval/task0/"


class FakeStore:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, str] = {}
        self.next_generation = 1
        self.inventory_calls = 0
        self.publish_calls = 0
        self.read_calls = 0
        self.read_generation_calls = 0
        self.resolve_calls = 0

    def seed(self, uri: str, raw: bytes, generation: str) -> dict[str, object]:
        assert uri not in self.current
        self.values[(uri, generation)] = raw
        self.current[uri] = generation
        return _identity(uri, raw, generation)

    def read(self, identity: dict[str, object]) -> bytes:
        self.read_calls += 1
        raw = self.values[(str(identity["uri"]), str(identity["generation"]))]
        if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
            raise ValueError("identity mismatch")
        return raw

    def read_generation(self, *, uri: str, generation: str) -> bytes:
        self.read_generation_calls += 1
        return self.values[(uri, generation)]

    def publish(
        self, uri: str, raw: bytes, media_type: str = "application/json"
    ) -> dict[str, object]:
        del media_type
        self.publish_calls += 1
        if uri in self.current:
            raise ValueError("create-once collision")
        generation = str(self.next_generation)
        self.next_generation += 1
        return self.seed(uri, raw, generation)

    def publish_or_reopen(
        self, uri: str, raw: bytes, media_type: str = "application/json"
    ) -> dict[str, object]:
        try:
            return self.publish(uri, raw, media_type)
        except ValueError:
            identity, reopened = self.resolve_current(uri)
            if reopened != raw:
                raise
            return identity

    def resolve_current(self, uri: str) -> tuple[dict[str, object], bytes]:
        self.resolve_calls += 1
        generation = self.current[uri]
        raw = self.values[(uri, generation)]
        return _identity(uri, raw, generation), raw

    def inventory(self, prefix: str) -> list[dict[str, object]]:
        self.inventory_calls += 1
        rows = []
        for uri, generation in self.values:
            if uri.startswith(prefix):
                raw = self.values[(uri, generation)]
                rows.append({
                    "uri": uri,
                    "generation": generation,
                    "bytes": len(raw),
                })
        return sorted(rows, key=lambda row: (row["uri"], row["generation"]))


class _FakeGCSBlob:
    def __init__(self, *, generation: object) -> None:
        self.name = "prefix/object.json"
        self.generation = generation
        self.raw = b"retained"
        self.size = len(self.raw)

    def upload_from_string(
        self, raw: bytes, *, content_type: str, if_generation_match: int,
    ) -> None:
        assert content_type == "application/json"
        assert if_generation_match == 0
        self.raw = raw
        self.size = len(raw)

    def reload(self) -> None:
        return None

    def download_as_bytes(self, *, if_generation_match: int) -> bytes:
        assert type(self.generation) is int
        assert if_generation_match == self.generation
        return self.raw


class _FakeGCSClient:
    def __init__(self, blob: _FakeGCSBlob) -> None:
        self.blob_value = blob

    def bucket(self, name: str) -> "_FakeGCSClient":
        assert name == "test-bucket"
        return self

    def blob(
        self, name: str, generation: int | None = None,
    ) -> _FakeGCSBlob:
        assert name == self.blob_value.name
        if generation is not None:
            assert type(self.blob_value.generation) is int
            assert generation == self.blob_value.generation
        return self.blob_value

    def list_blobs(
        self, bucket: str, *, prefix: str, versions: bool,
    ) -> list[_FakeGCSBlob]:
        assert bucket == "test-bucket"
        assert prefix == "prefix/"
        assert versions is True
        return [self.blob_value]


def _generation_boundary_storage(
    generation: object,
) -> tuple[object, _FakeGCSBlob]:
    storage = object.__new__(transport.GenerationPinnedStorage)
    blob = _FakeGCSBlob(generation=generation)
    storage._client = _FakeGCSClient(blob)
    return storage, blob


def test_gcs_blob_positive_integer_generation_is_normalized() -> None:
    storage, _blob = _generation_boundary_storage(7)
    uri = "gs://test-bucket/prefix/object.json"
    published = storage.publish(uri, b"published")
    assert published["generation"] == "7"
    current, reopened = storage.resolve_current(uri)
    assert current["generation"] == "7"
    assert reopened == b"published"
    assert storage.inventory("gs://test-bucket/prefix/") == [{
        "uri": uri, "generation": "7", "bytes": len(b"published"),
    }]


@pytest.mark.parametrize("generation", ["7", 7.0, True, 0, -1, None])
@pytest.mark.parametrize("operation", ["publish", "resolve", "inventory"])
def test_gcs_blob_generation_rejects_non_positive_json_integers(
    generation: object, operation: str,
) -> None:
    storage, _blob = _generation_boundary_storage(generation)
    uri = "gs://test-bucket/prefix/object.json"
    with pytest.raises(transport.CorpusParametricTransportError, match="generation"):
        if operation == "publish":
            storage.publish(uri, b"published")
        elif operation == "resolve":
            storage.resolve_current(uri)
        else:
            storage.inventory("gs://test-bucket/prefix/")


def _identity(uri: str, raw: bytes, generation: str = "1") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _placeholder(
    name: str, ordinal: int, *, prefix: str = FOUNDATION_PREFIX
) -> dict[str, object]:
    raw = f"placeholder-{name}-{ordinal}".encode()
    identity = _identity(
        f"{prefix}{name}.json", raw, str(ordinal + 1)
    )
    PLACEHOLDER_RAW[(identity["uri"], identity["generation"])] = raw
    return identity


def _code_source() -> tuple[dict[str, object], bytes]:
    value = {
        "schema": "corpus-legal-feasibility-code-source/v1",
        "source_commit_sha": CODE_SHA,
        "cloud_build_id": BUILD_ID,
        "implementation_sha256": {},
        "build_definition_sha256": {},
        "immutable_image": {
            "uri": IMAGE,
            "digest": IMAGE.rsplit("@", 1)[1],
        },
        "terminal_verification": {
            "authority": "external-terminal-execution-receipt",
            "required": True,
            "verifies": [
                "cloud_build_id",
                "immutable_image",
                "source_commit_sha",
            ],
        },
    }
    raw = batch.canonical_json_bytes(value)
    return _identity(f"{FOUNDATION_PREFIX}code-source.json", raw, "2"), raw


def _common_law(
    code_identity: dict[str, object], *, evidence_v2: bool = False
) -> dict[str, object]:
    source_receipts = {
        "later_source_freeze": _placeholder(
            "later-source-freeze", 10, prefix=f"{SOURCE_PREFIX}source/"
        )
    }
    result: dict[str, object] = {
        "code_source": code_identity,
        "immutable_image": {
            "uri": IMAGE,
            "digest": IMAGE.rsplit("@", 1)[1],
        },
        "source_receipts": source_receipts,
        "source_receipt_set_sha256": batch.canonical_sha256(source_receipts),
        "later_source_freeze_manifest_sha256": "9" * 64,
        "artifact_source_authority_completion": _placeholder(
            "artifact-source-authority-completion",
            11,
            prefix=f"{SOURCE_PREFIX}source/",
        ),
        "artifact_source_authority_completion_sha256": "2" * 64,
        "effective_policy_inventory_identity": _placeholder("inventory", 12),
        "effective_policy_inventory_sha256": evidence.EXPECTED_INVENTORY_SHA256,
        "effective_policy_rule_universe_sha256": (
            evidence.EXPECTED_RULE_UNIVERSE_SHA256
        ),
        "effective_policy_inventory_source_set_sha256": (
            evidence.EXPECTED_INVENTORY_SOURCE_SET_SHA256
        ),
        "effective_policy_classified_input_projection_sha256": (
            evidence.EXPECTED_CLASSIFIED_INPUT_PROJECTION_SHA256
        ),
        "world_schedule": _placeholder("world-schedule", 13),
        "world_seed": 7331,
        "objective": _placeholder("objective", 14),
        "solve_budget": {
            "solve_attempts_per_seed": 200,
            "worlds_per_block": 10_000,
            "solver_timeout_seconds": 600,
            "candidate_entry_budget": 1_000,
            "selected_entry_budget": 80,
        },
        "generator_families": _placeholder("generator-families", 15),
        "unique_fill": _placeholder("unique-fill", 16),
        "deduplication": _placeholder("deduplication", 17),
        "admission": _placeholder("admission", 18),
        "cbwu": _placeholder("cbwu", 19),
        "selector": _placeholder("selector", 20),
        "line_194": _placeholder("line-194", 21),
        "exact_80": _placeholder("exact-80", 22),
        "solver": {
            "name": "cbc",
            "version": "2.10.3",
            "binary_sha256": "b" * 64,
            "options_sha256": "c" * 64,
            "exact_mode": True,
        },
        "retry_law": {"max_attempts_per_task": 1, "max_retries": 0},
        "fresh_model_state_per_parameter_set": True,
        "worker_environment_inheritance": False,
        "worker_graph_mutation": False,
    }
    if evidence_v2:
        result.update({
            "effective_policy_inventory_sha256": (
                evidence.V2_EXPECTED_INVENTORY_SHA256
            ),
            "effective_policy_rule_universe_sha256": (
                evidence.V2_EXPECTED_RULE_UNIVERSE_SHA256
            ),
            "effective_policy_inventory_source_set_sha256": (
                evidence.V2_EXPECTED_INVENTORY_SOURCE_SET_SHA256
            ),
            "effective_policy_classified_input_projection_sha256": (
                evidence.V2_EXPECTED_CLASSIFIED_INPUT_PROJECTION_SHA256
            ),
        })
    return result


def _task(task_index: int, *, batch_id: str) -> dict[str, object]:
    artifacts = {
        role: _placeholder(
            f"task-{task_index}-{role}",
            100 + task_index * 5 + ordinal,
            prefix=SOURCE_PREFIX,
        )
        for ordinal, role in enumerate(batch.TASK_WORLD_SOURCE_ROLES)
    }
    return {
        "task_index": task_index,
        "slate_id": f"2023-w{task_index + 1}-main",
        "season": 2023,
        "week": task_index + 1,
        "result_receipt_uri": (
            f"gs://dedicated/batches/{batch_id}/tasks/{task_index:03d}.json"
        ),
        "variant_output_prefix": (
            f"gs://dedicated/batches/{batch_id}/variants/task-{task_index:03d}/"
        ),
        "world_artifact_receipts": artifacts,
        "world_artifact_receipt_set_sha256": batch.canonical_sha256(artifacts),
        "artifact_source_authority_task_sha256": f"{(task_index % 9) + 1}" * 64,
    }


def _manifest(
    task_count: int = 1, *, evidence_v2: bool = False
) -> tuple[dict[str, object], bytes, bytes]:
    code_identity, code_raw = _code_source()
    batch_id = "corpus-transport-test-v1"
    manifest = batch.build_batch_manifest(
        batch_id=batch_id,
        created_at_utc=NOW,
        output_prefix=f"gs://dedicated/batches/{batch_id}/",
        common_law=_common_law(code_identity, evidence_v2=evidence_v2),
        tasks=[_task(index, batch_id=batch_id) for index in range(task_count)],
    )
    return manifest, batch.canonical_json_bytes(manifest), code_raw


def _job(*, generation: int | str = 7) -> dict[str, object]:
    task_spec = {
        "maxRetries": 0,
        "timeoutSeconds": transport.EXPECTED_TIMEOUT_SECONDS,
        "serviceAccountName": SERVICE_ACCOUNT,
        "volumes": [],
        "containers": [{
            "image": IMAGE,
            "command": ["python"],
            "args": [transport.TRANSPORT_SCRIPT if hasattr(transport, "TRANSPORT_SCRIPT") else "scripts/run_corpus_parametric_transport.py", "parked"],
            "env": [
                {"name": transport.ENABLE_ENV, "value": "1"},
                {"name": transport.IMAGE_ENV, "value": IMAGE},
                {"name": transport.BUILD_ENV, "value": BUILD_ID},
                {"name": transport.CODE_ENV, "value": CODE_SHA},
            ],
            "resources": {"limits": dict(transport.EXPECTED_RESOURCES)},
            "volumeMounts": [],
        }],
    }
    return {
        "metadata": {"name": JOB_NAME, "uid": JOB_UID, "generation": generation},
        "spec": {"template": {"spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": task_spec},
        }}},
        "status": {
            "observedGeneration": generation,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _build_metadata() -> dict[str, object]:
    source = {"revision": CODE_SHA, "url": transport.EXPECTED_CODE_REPOSITORY}
    command_sets = {
        "focused-corpus-research-tests": expansion_build.FOCUSED_TEST_COMMANDS,
        "smoke-corpus-artifact-source": expansion_build.SOURCE_SMOKE_COMMANDS,
        "smoke-corpus-parametric-expansion": (
            expansion_build.PARAMETRIC_SMOKE_COMMANDS
        ),
        "smoke-corpus-neo4j-transport": expansion_build.NEO4J_SMOKE_COMMANDS,
    }
    steps: list[dict[str, object]] = []
    for step_id, name, entrypoint in expansion_build.EXPECTED_STEP_SPECS:
        if step_id == "build-image":
            args = [
                "build", "-f", expansion_build.EXPANSION_DOCKERFILE,
                "-t", IMAGE_TAG, ".",
            ]
        else:
            rendered = [
                shlex.join(tuple(
                    IMAGE_TAG if token == "${_IMAGE}" else token
                    for token in command
                ))
                for command in command_sets[step_id]
            ]
            args = ["-ceu", "\n".join(rendered)]
        row: dict[str, object] = {
            "id": step_id,
            "name": name,
            "status": "SUCCESS",
            "exitCode": 0,
            "args": args,
        }
        if entrypoint:
            row["entrypoint"] = entrypoint
        steps.append(row)
    return {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": source},
        "sourceProvenance": {"resolvedGitSource": source},
        "substitutions": {"_IMAGE": IMAGE_TAG},
        "images": [IMAGE_TAG],
        "artifacts": {"images": [IMAGE_TAG]},
        "timeout": "10800s",
        "options": {
            "logging": "LEGACY", "machineType": "E2_HIGHCPU_8", "pool": {},
        },
        "results": {"images": [{
            "name": IMAGE_TAG,
            "digest": IMAGE.rsplit("@", 1)[1],
        }]},
        "steps": steps,
    }


def _core_self_hash(body: dict[str, object], field: str) -> dict[str, object]:
    return {**body, field: batch.canonical_sha256(body)}


class FakeRetrievalCore:
    canonical_json_bytes = staticmethod(batch.canonical_json_bytes)
    canonical_sha256 = staticmethod(batch.canonical_sha256)
    parse_canonical_json_bytes = staticmethod(batch.parse_canonical_json_bytes)

    @staticmethod
    def _validate_self(value: object, *, schema: str, field: str) -> dict[str, object]:
        item = dict(value)
        retained = item.pop(field)
        if item["schema_version"] != schema or retained != batch.canonical_sha256(item):
            raise ValueError("fake retrieval self hash differs")
        return {**item, field: retained}

    @classmethod
    def validate_suite_manifest(cls, value: object) -> dict[str, object]:
        return cls._validate_self(value, schema="fake-retrieval-suite/v1", field="suite_manifest_sha256")

    @classmethod
    def validate_snapshot_manifest(cls, value: object) -> dict[str, object]:
        return cls._validate_self(value, schema="fake-retrieval-snapshot/v1", field="snapshot_manifest_sha256")

    @staticmethod
    def validate_retrieval_task_result(**kwargs: object) -> dict[str, object]:
        assert kwargs["replay"] is True
        published = kwargs["published_result"]
        authority = dict(published["authority"])
        body = dict(authority)
        retained = body.pop("task_result_sha256")
        if retained != batch.canonical_sha256(body):
            raise ValueError("fake retrieval result hash differs")
        reader = kwargs["read_object"]
        if reader(authority["sidecar_object"]) != b"task0-sidecar":
            raise ValueError("fake retrieval result replay differs")
        if published["object_identity"]["uri"] != kwargs["suite_manifest"]["tasks"][0]["result_uri"]:
            raise ValueError("fake retrieval result URI differs")
        return authority

    @staticmethod
    def validate_retrieval_batch_completion(value: object, **kwargs: object) -> dict[str, object]:
        item = dict(value)
        retained = item.pop("batch_completion_sha256")
        if retained != batch.canonical_sha256(item):
            raise ValueError("fake retrieval completion hash differs")
        result = kwargs["published_results"][0]
        if (
            len(kwargs["published_results"]) != 1
            or item["task_results"][0]["task_result_object"]
            != result["object_identity"]
        ):
            raise ValueError("fake retrieval completion result differs")
        return {**item, "batch_completion_sha256": retained}


@pytest.fixture(autouse=True)
def _use_fake_retrieval_core(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        transport, "_retrieval_module", lambda: FakeRetrievalCore
    )


def _prerequisite(store: FakeStore) -> tuple[dict[str, object], bytes]:
    snapshot = _core_self_hash({
        "schema_version": "fake-retrieval-snapshot/v1",
        "tasks": [{"task_index": 0, "task_id": "task-0"}],
    }, "snapshot_manifest_sha256")
    snapshot_raw = batch.canonical_json_bytes(snapshot)
    snapshot_identity = store.seed(
        f"{RETRIEVAL_PREFIX}snapshot.json", snapshot_raw, "20"
    )
    suite = _core_self_hash({
        "schema_version": "fake-retrieval-suite/v1",
        "snapshot_manifest_identity": snapshot_identity,
        "tasks": [{
            "task_index": 0,
            "task_id": "task-0",
            "result_uri": f"{RETRIEVAL_PREFIX}result.json",
        }],
    }, "suite_manifest_sha256")
    suite_raw = batch.canonical_json_bytes(suite)
    suite_identity = store.seed(
        f"{RETRIEVAL_PREFIX}suite.json", suite_raw, "21"
    )
    sidecar_identity = store.seed(
        f"{RETRIEVAL_PREFIX}sidecar.bin", b"task0-sidecar", "22"
    )
    result = _core_self_hash({
        "schema_version": "fake-retrieval-task-result/v1",
        "task_index": 0,
        "sidecar_object": sidecar_identity,
        "coverage": {
            "unique_lineup_count": 3,
            "world_count": 50_000,
            "lineup_world_score_count": 150_000,
            "every_unique_lineup_scored_in_every_world": True,
        },
        "licenses": {"corpus_fill_authority": False},
    }, "task_result_sha256")
    result_raw = batch.canonical_json_bytes(result)
    result_identity = store.seed(
        f"{RETRIEVAL_PREFIX}result.json", result_raw, "23"
    )
    completion = _core_self_hash({
        "schema_version": "fake-retrieval-completion/v1",
        "coverage": {"task_count": 1, "all_tasks_complete": True},
        "task_results": [{
            "task_index": 0,
            "task_result_object": result_identity,
        }],
    }, "batch_completion_sha256")
    completion_raw = batch.canonical_json_bytes(completion)
    completion_identity = store.seed(
        f"{RETRIEVAL_PREFIX}completion.json", completion_raw, "24"
    )
    governance: dict[str, dict[str, object]] = {}
    for ordinal, field in enumerate((
        value for value in transport._RETRIEVAL_TERMINAL_GOVERNANCE_FIELDS
        if value != "prefix_claim"
    ), start=25):
        governance[field] = store.seed(
            f"{RETRIEVAL_PREFIX}{field}.json",
            batch.canonical_json_bytes({"field": field}),
            str(ordinal),
        )
    runtime_iam = governance["runtime_iam_evidence"]
    prefix_claim = _core_self_hash({
        "schema_version": transport.RETRIEVAL_PREFIX_CLAIM_SCHEMA,
        "published_at_utc": NOW,
        "preflight_sha256": "3" * 64,
        "suite_manifest_identity": suite_identity,
        "snapshot_manifest_identity": snapshot_identity,
        "task_index": 0,
        "task_id": "task-0",
        "output_prefix": RETRIEVAL_PREFIX,
        "result_uri": result_identity["uri"],
        "job": "retrieval-job",
        "job_uid": "retrieval-job-uid",
        "job_prior_generation": "2",
        "runtime_iam_evidence_uri": runtime_iam["uri"],
        "runtime_iam_evidence_sha256": runtime_iam["sha256"],
        "runtime_iam_evidence_bytes": runtime_iam["bytes"],
        "create_once": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }, field="claim_sha256")
    governance["prefix_claim"] = store.seed(
        f"{RETRIEVAL_PREFIX}prefix-claim.json",
        batch.canonical_json_bytes(prefix_claim),
        "30",
    )
    terminal_inventory = transport._inventory_rows([
        suite_identity,
        sidecar_identity,
        result_identity,
        completion_identity,
        *governance.values(),
    ])
    terminal_body = {
        "schema_version": "corpus-retrieval-transport-terminal/v1",
        "finished_at_utc": NOW,
        **governance,
        "execution": {
            "execution_id": "retrieval-task0",
            "execution_name": "retrieval-task0",
            "execution_uid": "retrieval-task0-uid",
            "job": "retrieval-job",
            "job_uid": "retrieval-job-uid",
            "job_generation": "3",
            "job_spec_sha256": "1" * 64,
            "task_count": 1,
            "attempt": 0,
            "retry_count": 0,
            "state": "True",
            "counters": {
                "succeeded": 1,
                "failed": 0,
                "cancelled": 0,
                "retried": 0,
            },
            "metadata_sha256": "2" * 64,
        },
        "suite_manifest_identity": suite_identity,
        "snapshot_manifest_identity": snapshot_identity,
        "task_index": 0,
        "task_id": "task-0",
        "result_object": result_identity,
        "task_result_sha256": result["task_result_sha256"],
        "batch_completion": completion_identity,
        "batch_completion_sha256": completion["batch_completion_sha256"],
        "post_terminal_job": {
            "name": "retrieval-job",
            "uid": "retrieval-job-uid",
            "generation": "3",
            "observed_generation": "3",
            "spec_sha256": "1" * 64,
        },
        "output_inventory_before_terminal": terminal_inventory,
        "output_inventory_before_terminal_sha256": batch.canonical_sha256(
            terminal_inventory
        ),
        "one_execution": True,
        "attempt_zero": True,
        "retry_count": 0,
        "generation_pinned_replay": True,
        "successful_deployment_remains_parked": True,
        "uses_realized_outcomes": False,
        "bigquery_access_licensed": False,
        "corpus_fill_licensed": False,
        "live_policy_access_licensed": False,
        "production_change_licensed": False,
    }
    terminal = {
        **terminal_body,
        "terminal_receipt_sha256": batch.canonical_sha256(terminal_body),
    }
    terminal_raw = batch.canonical_json_bytes(terminal)
    terminal_identity = store.seed(
        f"{RETRIEVAL_PREFIX}terminal.json", terminal_raw, "31"
    )
    body = {
        "schema_version": transport.RETRIEVAL_PREREQUISITE_SCHEMA,
        "accepted_at_utc": NOW,
        "task_index": 0,
        "suite_manifest_identity": suite_identity,
        "snapshot_manifest_identity": snapshot_identity,
        "task_result_object": result_identity,
        "terminal_receipt": terminal_identity,
        "completion_receipt": completion_identity,
        "accepted": True,
        "complete_result": True,
        "partial_result": False,
        "partial_object_count": 0,
        "every_unique_lineup_scored_in_every_world": True,
        "generation_pinned_replay": True,
        "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
    }
    accepted = transport._self_hash(body, field="acceptance_sha256")
    raw = transport.canonical_json_bytes(accepted)
    identity = store.seed(
        f"{FOUNDATION_PREFIX}governance/retrieval-task0-accepted-prerequisite.json",
        raw,
        "32",
    )
    return identity, raw


def _no_newline_hashed(
    body: dict[str, object], *, field: str
) -> tuple[dict[str, object], bytes]:
    value = {
        **body,
        field: sha256(transport.canonical_json_bytes(body)[:-1]).hexdigest(),
    }
    return value, transport.canonical_json_bytes(value)[:-1]


def _seed_foundation_publication(
    *,
    store: FakeStore,
    manifest: dict[str, object],
    manifest_identity: dict[str, object],
    evidence_identity: dict[str, object],
    prerequisite_identity: dict[str, object],
) -> dict[str, object]:
    common = manifest["common_law"]

    def seed_source(name: str, raw: bytes, generation: str) -> dict[str, object]:
        return store.seed(f"{SOURCE_PREFIX}{name}", raw, generation)

    registration = seed_source(
        "governance/source-registration.json", b"registration", "700"
    )
    salary = seed_source(
        "source/salary-diagnostic.json", b"salary", "701"
    )
    base_lock = seed_source("base-source-lock.json", b"base-lock", "702")
    capture_identities = {
        "r0_candidates": seed_source(
            "queries/r0-candidates.json", b"r0", "708"
        ),
        "artifact_catalog": seed_source(
            "queries/artifact-catalog.json", b"catalog", "709"
        ),
        "salary_player_ids": seed_source(
            "queries/salary-player-ids.json", b"salary-ids", "710"
        ),
    }
    inventory = []
    source_publication_uri = (
        f"{SOURCE_PREFIX}governance/publication-completion.json"
    )
    source_claim_uri = f"{SOURCE_PREFIX}governance/prefix-claim.json"
    source_claim_body = {
        "schema": transport.SOURCE_PREFIX_CLAIM_SCHEMA,
        "run_id": "source-test-v1",
        "plan_sha256": "4" * 64,
        "output_prefix": SOURCE_PREFIX,
        "publication_uris": {
            "prefix_claim": source_claim_uri,
            "registration": registration["uri"],
            "r0_candidates": capture_identities["r0_candidates"]["uri"],
            "artifact_catalog": capture_identities["artifact_catalog"]["uri"],
            "salary_player_ids": capture_identities["salary_player_ids"]["uri"],
            "later_source_freeze": common["source_receipts"][
                "later_source_freeze"
            ]["uri"],
            "salary_diagnostic": salary["uri"],
            "publication_completion": source_publication_uri,
            "source_authority_completion": common[
                "artifact_source_authority_completion"
            ]["uri"],
        },
        "base_source_lock_object": base_lock,
        "source_snapshot_at": NOW,
        "registration_sha256": "5" * 64,
        "create_once": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    _, source_claim_raw = _no_newline_hashed(
        source_claim_body, field="claim_sha256"
    )
    source_claim_identity = store.seed(source_claim_uri, source_claim_raw, "703")
    producer_get_trace, _ = _no_newline_hashed({
        "schema": "corpus-artifact-source-producer-get-trace/v1",
        "delivered_plan_object": base_lock,
        "delivered_intent_object": base_lock,
        "events": [],
        "event_count": 0,
        "events_sha256": sha256(
            transport.canonical_json_bytes([])[:-1]
        ).hexdigest(),
        "absence_check_uris": [],
        "object_list_used": False,
        "complete": True,
    }, field="trace_sha256")
    producer_query_trace, _ = _no_newline_hashed({
        "schema": "corpus-artifact-source-producer-query-trace/v1",
        "events": [],
        "event_count": 0,
        "events_sha256": sha256(
            transport.canonical_json_bytes([])[:-1]
        ).hexdigest(),
        "complete": True,
    }, field="trace_sha256")
    source_publication_body = {
        "schema": transport.SOURCE_PUBLICATION_SCHEMA,
        "run_id": "source-test-v1",
        "plan_sha256": "4" * 64,
        "output_prefix": SOURCE_PREFIX,
        "prefix_claim": source_claim_identity,
        "registration_object": registration,
        "registration_sha256": "5" * 64,
        "query_captures": {
            role: {
                "object": identity,
                "job_id": f"source-test-v1-{role}",
                "row_count": 54,
                "rows_sha256": "8" * 64,
                "capture_sha256": "9" * 64,
            }
            for role, identity in capture_identities.items()
        },
        "later_source_freeze_object": common["source_receipts"][
            "later_source_freeze"
        ],
        "later_source_freeze_manifest_sha256": common[
            "later_source_freeze_manifest_sha256"
        ],
        "salary_diagnostic_object": salary,
        "salary_diagnostic_sha256": "6" * 64,
        "source_authority_completion_object": common[
            "artifact_source_authority_completion"
        ],
        "source_authority_completion_sha256": common[
            "artifact_source_authority_completion_sha256"
        ],
        "base_source_lock_object": base_lock,
        "task_count": 54,
        "artifact_count": 270,
        "artifact_reads": "exact-generation-get-only-one-at-a-time",
        "artifact_list_used": False,
        "producer_get_trace": producer_get_trace,
        "producer_query_trace": producer_query_trace,
        "producer_trace_complete_before_terminal_publication": True,
        "inventory_before_publication": inventory,
        "inventory_before_publication_sha256": sha256(
            transport.canonical_json_bytes(inventory)[:-1]
        ).hexdigest(),
        "create_once": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "live_strategy_authority": False,
    }
    _, source_publication_raw = _no_newline_hashed(
        source_publication_body, field="publication_completion_sha256"
    )
    source_publication_identity = store.seed(
        source_publication_uri, source_publication_raw, "704"
    )

    foundation_id = "test-v1"
    claim_uri = f"{FOUNDATION_PREFIX}governance/prefix-claim.json"
    publication_uri = f"{FOUNDATION_PREFIX}governance/publication-completion.json"
    preplan = store.seed(
        f"{FOUNDATION_PREFIX}governance/preplan.json", b"preplan", "705"
    )
    common_identities = {
        role: common[role] for role in transport.COMMON_LAW_BODY_ROLES
    }
    planned_uris = [
        claim_uri,
        preplan["uri"],
        prerequisite_identity["uri"],
        common["effective_policy_inventory_identity"]["uri"],
        *(identity["uri"] for identity in common_identities.values()),
        manifest_identity["uri"],
        evidence_identity["uri"],
        publication_uri,
    ]
    claim_body = {
        "schema_version": transport.FOUNDATION_PREFIX_CLAIM_SCHEMA,
        "foundation_id": foundation_id,
        "workstream": "corpus-parametric-research",
        "mode": "production" if len(manifest["tasks"]) == 54 else "smoke",
        "foundation_prefix": FOUNDATION_PREFIX,
        "batch_output_prefix": manifest["output_prefix"],
        "preplan_sha256": "7" * 64,
        "planned_object_uris": planned_uris,
        "planned_object_uri_set_sha256": sha256(
            transport.canonical_json_bytes(planned_uris)[:-1]
        ).hexdigest(),
        "pre_outcome_registration": True,
        "create_once": True,
        "resume_licensed": False,
        "replace_licensed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "corpus_fill_licensed": False,
        "production_change_licensed": False,
    }
    _, claim_raw = _no_newline_hashed(
        claim_body, field="prefix_claim_sha256"
    )
    claim_identity = store.seed(claim_uri, claim_raw, "706")
    publication_body = {
        "schema_version": transport.FOUNDATION_PUBLICATION_SCHEMA,
        "foundation_id": foundation_id,
        "batch_id": manifest["batch_id"],
        "mode": claim_body["mode"],
        "workstream": "corpus-parametric-research",
        "reserved_independent_workstream": "corpus-population-research",
        "created_at_utc": NOW,
        "preplan_sha256": "7" * 64,
        "prefix_claim": claim_identity,
        "preplan_object": preplan,
        "full_manifest": manifest_identity,
        "full_evidence_contract": evidence_identity,
        "accepted_retrieval_prerequisite": prerequisite_identity,
        "source_publication_authority": source_publication_identity,
        "source_authority_completion": common[
            "artifact_source_authority_completion"
        ],
        "source_freeze": common["source_receipts"]["later_source_freeze"],
        "common_law_objects": common_identities,
        "effective_policy_inventory": common[
            "effective_policy_inventory_identity"
        ],
        "task_requests": [],
        "task_count": len(manifest["tasks"]),
        "parameter_arm_count": 7,
        "source_task_count": 54,
        "source_artifact_count": 270,
        "source_artifact_exact_get_count": 270,
        "idempotent": True,
        "create_once": True,
        "runtime_iam_authority": False,
        "launch_authority": False,
        "outcome_read_authority": False,
        "historical_scoring_authority": False,
        "corpus_fill_authority": False,
        "corpus_population_authority": False,
        "live_strategy_authority": False,
        "graph_mutation_authority": False,
        "production_change_authority": False,
        "production_policy_change_authority": False,
        "automatic_policy_feedback": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    _, publication_raw = _no_newline_hashed(
        publication_body, field="publication_sha256"
    )
    return store.seed(publication_uri, publication_raw, "707")


def _runtime_iam_capture_raw(
    manifest: dict[str, object],
    *,
    exact_identities: tuple[dict[str, object], ...] = (),
) -> bytes:
    read_role = (
        f"projects/{transport.PROJECT}/roles/corpusParametricObjectGetV2"
    )
    create_role = (
        f"projects/{transport.PROJECT}/roles/corpusParametricObjectCreateV2"
    )
    member = f"serviceAccount:{SERVICE_ACCOUNT}"
    prefixes = sorted([
        manifest["output_prefix"],
        FOUNDATION_PREFIX,
        RETRIEVAL_PREFIX,
        SOURCE_PREFIX,
    ])

    def expression(
        rows: list[str],
        exact_rows: list[dict[str, object]] | tuple[dict[str, object], ...] = (),
    ) -> str:
        clauses = [
            f'resource.name.startsWith("{transport._resource_prefix(prefix)}")'
            for prefix in rows
        ]
        clauses.extend(
            f'resource.name == "{transport._resource_name(str(row["uri"]))}"'
            for row in exact_rows
        )
        return " || ".join(clauses)

    bucket_names = sorted({
        prefix.removeprefix("gs://").split("/", 1)[0]
        for prefix in prefixes
    } | {
        str(identity["uri"]).removeprefix("gs://").split("/", 1)[0]
        for identity in exact_identities
    })
    bucket_policies = []
    effective_results = []
    for bucket_name in bucket_names:
        bucket_prefixes = [
            prefix for prefix in prefixes
            if prefix.startswith(f"gs://{bucket_name}/")
        ]
        bucket_exact = [
            identity for identity in exact_identities
            if str(identity["uri"]).startswith(f"gs://{bucket_name}/")
        ]
        bindings: list[dict[str, object]] = [{
            "role": read_role,
            "members": [member],
            "condition": {
                "title": transport.RUNTIME_READ_CONDITION_TITLE,
                "expression": expression(bucket_prefixes, bucket_exact),
            },
        }]
        if manifest["output_prefix"].startswith(f"gs://{bucket_name}/"):
            bindings.append({
                "role": create_role,
                "members": [member],
                "condition": {
                    "title": transport.RUNTIME_CREATE_CONDITION_TITLE,
                    "expression": expression([manifest["output_prefix"]]),
                },
            })
        bucket_policies.append({
            "bucket": bucket_name,
            "policy": {
                "version": 3,
                "etag": f"etag-{bucket_name}",
                "bindings": bindings,
            },
        })
        attached = f"//storage.googleapis.com/{bucket_name}"

        def effective_grant(
            *, role: str, title: str, grant_expression: str, permission: str
        ) -> dict[str, object]:
            return {
                "fullyExplored": True,
                "nonCriticalErrors": [],
                "iamBinding": {
                    "role": role,
                    "members": [member],
                    "condition": {
                        "title": title,
                        "expression": grant_expression,
                    },
                },
                "attachedResourceFullName": attached,
                "identityList": {
                    "identities": [{"name": member}],
                    "groupEdges": [],
                },
                "accessControlLists": [{
                    "resources": [{"fullResourceName": attached}],
                    "accesses": [
                        {"role": role}, {"permission": permission},
                    ],
                    "conditionEvaluation": {
                        "evaluationValue": "CONDITIONAL"
                    },
                }],
            }

        effective_results.append(effective_grant(
            role=read_role,
            title=transport.RUNTIME_READ_CONDITION_TITLE,
            grant_expression=expression(bucket_prefixes, bucket_exact),
            permission=transport.STORAGE_GET_PERMISSION,
        ))
        if manifest["output_prefix"].startswith(f"gs://{bucket_name}/"):
            effective_results.append(effective_grant(
                role=create_role,
                title=transport.RUNTIME_CREATE_CONDITION_TITLE,
                grant_expression=expression([manifest["output_prefix"]]),
                permission=transport.STORAGE_CREATE_PERMISSION,
            ))

    def analysis(identity: str, results: list[dict[str, object]]) -> dict[str, object]:
        query = {
            "identitySelector": {"identity": identity},
            "options": transport._CLOUD_ASSET_OPTIONS,
            "scope": f"projects/{transport.PROJECT}",
        }
        return {
            "fullyExplored": True,
            "nonCriticalErrors": [],
            "mainAnalysis": {
                "fullyExplored": True,
                "nonCriticalErrors": [],
                "analysisQuery": query,
                "analysisResults": results,
            },
        }
    body = {
        "schema_version": transport.RUNTIME_IAM_CAPTURE_SCHEMA,
        "captured_at_utc": NOW,
        "project": transport.PROJECT,
        "project_policy": {"version": 1, "etag": "project-etag", "bindings": []},
        "custom_role_definitions": sorted([
            {
                "name": read_role,
                "stage": "GA",
                "deleted": False,
                "includedPermissions": [transport.STORAGE_GET_PERMISSION],
            },
            {
                "name": create_role,
                "stage": "GA",
                "deleted": False,
                "includedPermissions": [transport.STORAGE_CREATE_PERMISSION],
            },
        ], key=lambda row: row["name"]),
        "bucket_policies": bucket_policies,
        "bucket_metadata": [
            {
                "bucket": bucket_name,
                "metadata": {
                    "name": bucket_name,
                    "iamConfiguration": {
                        "uniformBucketLevelAccess": {"enabled": True},
                        "publicAccessPrevention": "enforced",
                    },
                },
            }
            for bucket_name in bucket_names
        ],
        "effective_access_analyses": {
            "runtime_identity": analysis(member, effective_results),
            "all_users": analysis("allUsers", []),
            "all_authenticated_users": analysis(
                "allAuthenticatedUsers", []
            ),
        },
    }
    return transport.canonical_json_bytes(
        transport._self_hash(body, field="capture_sha256")
    )


def _deployment_attestation(
    manifest: dict[str, object],
) -> dict[str, object]:
    return transport.build_deployment_attestation(
        runtime_iam_policy_capture=transport.strict_json_bytes(
            _runtime_iam_capture_raw(manifest), label="fixture IAM capture"
        ),
        build_metadata=_build_metadata(),
        build_id=BUILD_ID,
        code_sha=CODE_SHA,
        image=IMAGE,
        service_account=SERVICE_ACCOUNT,
        parked_job=_job(),
        expected_job_name=JOB_NAME,
        expected_job_uid=JOB_UID,
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        expires_at_utc="2026-08-22T18:00:00Z",
    )


def _configuration_fixture(
    *, task_count: int = 1, evidence_v2: bool = False
) -> tuple[
    FakeStore, dict[str, object], dict[str, object], dict[str, object],
    dict[str, object], dict[str, object],
]:
    store = FakeStore()
    manifest, manifest_raw, code_raw = _manifest(
        task_count, evidence_v2=evidence_v2
    )
    manifest_identity = store.seed(manifest["manifest_uri"], manifest_raw, "100")
    evidence_builder = (
        evidence.build_corpus_batch_evidence_contract_v2
        if evidence_v2
        else evidence.build_corpus_batch_evidence_contract
    )
    evidence_contract = evidence_builder(
        batch_manifest=manifest,
        batch_manifest_identity=manifest_identity,
    )
    evidence_raw = batch.canonical_json_bytes(evidence_contract)
    evidence_identity = store.seed(
        evidence_contract["contract_uri"], evidence_raw, "101"
    )
    store.seed(
        manifest["common_law"]["code_source"]["uri"],
        code_raw,
        manifest["common_law"]["code_source"]["generation"],
    )
    for identity in transport._manifest_input_identities(manifest):
        key = (identity["uri"], identity["generation"])
        if identity["uri"] not in store.current:
            store.seed(identity["uri"], PLACEHOLDER_RAW[key], identity["generation"])
    prerequisite_identity, _ = _prerequisite(store)
    foundation_publication_identity = _seed_foundation_publication(
        store=store,
        manifest=manifest,
        manifest_identity=manifest_identity,
        evidence_identity=evidence_identity,
        prerequisite_identity=prerequisite_identity,
    )
    return (
        store, manifest, manifest_identity, evidence_identity,
        prerequisite_identity, foundation_publication_identity,
    )


def _configured(
    *, task_count: int = 1, evidence_v2: bool = False
) -> tuple[FakeStore, dict[str, object], dict[str, object], dict[str, object]]:
    (
        store, manifest, manifest_identity, evidence_identity,
        prerequisite_identity, foundation_publication_identity,
    ) = _configuration_fixture(
        task_count=task_count, evidence_v2=evidence_v2
    )
    configured = transport.configure_transport(
        storage=store,
        batch_manifest_identity=manifest_identity,
        evidence_contract_identity=evidence_identity,
        retrieval_prerequisite_identity=prerequisite_identity,
        foundation_publication_identity=foundation_publication_identity,
        runtime_iam_evidence_raw=_runtime_iam_capture_raw(manifest),
        build_metadata=_build_metadata(),
        build_id=BUILD_ID,
        code_sha=CODE_SHA,
        image=IMAGE,
        service_account=SERVICE_ACCOUNT,
        parked_job=_job(),
        expected_job_name=JOB_NAME,
        expected_job_uid=JOB_UID,
        executions=[],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    _, contract_raw = store.resolve_current(
        configured["transport_contract"]["uri"]
    )
    contract = transport.validate_transport_contract(
        transport.strict_json_bytes(contract_raw, label="contract")
    )
    return store, manifest, contract, configured


def test_transport_configure_accepts_strict_v2_evidence_contract() -> None:
    _, manifest, contract, configured = _configured(evidence_v2=True)
    assert contract["batch_manifest_sha256"] == manifest[
        "batch_manifest_sha256"
    ]
    assert configured["launch_permitted"] is False


def _execution(
    *,
    contract: dict[str, object],
    contract_identity: dict[str, object],
    task_index: int,
    phase: str,
    execution_id: str,
    execution_uid: str,
    terminal: bool,
) -> dict[str, object]:
    build = contract["build"]
    task_spec = {
        "maxRetries": 0,
        "timeoutSeconds": transport.EXPECTED_TIMEOUT_SECONDS,
        "serviceAccountName": SERVICE_ACCOUNT,
        "volumes": [],
        "containers": [{
            "image": IMAGE,
            "command": ["python"],
            "args": transport.cloud_worker_args(
                phase=phase,
                contract_identity=contract_identity,
                task_index=task_index,
            ),
            "env": [
                {"name": transport.ENABLE_ENV, "value": "1"},
                {"name": transport.IMAGE_ENV, "value": build["image"]},
                {"name": transport.BUILD_ENV, "value": build["build_id"]},
                {"name": transport.CODE_ENV, "value": build["code_sha"]},
            ],
            "resources": {"limits": dict(transport.EXPECTED_RESOURCES)},
            "volumeMounts": [],
        }],
    }
    status: dict[str, object] = {"conditions": []}
    if terminal:
        status = {
            "conditions": [{"type": "Completed", "status": "True"}],
            "succeededCount": 1,
            "failedCount": 0,
            "cancelledCount": 0,
            "retriedCount": 0,
        }
    return {
        "metadata": {
            "name": execution_id,
            "uid": execution_uid,
            "labels": {
                "run.googleapis.com/job": JOB_NAME,
                "run.googleapis.com/jobUid": JOB_UID,
                "run.googleapis.com/jobGeneration": "7",
            },
        },
        "spec": {
            "taskCount": 1,
            "parallelism": 1,
            "template": {"spec": task_spec},
        },
        "status": status,
    }


def _runtime_environ(execution_id: str, execution_uid: str) -> dict[str, str]:
    del execution_uid  # Cloud Run exposes the UID through the bound metadata, not env.
    return {
        transport.ENABLE_ENV: "1",
        transport.IMAGE_ENV: IMAGE,
        transport.BUILD_ENV: BUILD_ID,
        transport.CODE_ENV: CODE_SHA,
        "CLOUD_RUN_EXECUTION": execution_id,
        "CLOUD_RUN_JOB": JOB_NAME,
        "CLOUD_RUN_TASK_INDEX": "0",
        "CLOUD_RUN_TASK_ATTEMPT": "0",
        "CLOUD_RUN_TASK_COUNT": "1",
    }


def _fake_producer(**kwargs: object) -> SimpleNamespace:
    evidence_directory = Path(kwargs["evidence_directory"])
    manifest = batch.parse_canonical_json_bytes(
        kwargs["batch_manifest_bytes"], label="fake producer manifest"
    )
    task_index = kwargs["task_request"]["task_index"]
    task = manifest["tasks"][task_index]
    profiles = manifest["parameter_sets"]
    shards = []
    for ordinal in range(70):
        compressed = evidence_directory / f"shard-{ordinal:03d}.zlib"
        index = evidence_directory / f"shard-{ordinal:03d}.index.json"
        compressed.write_bytes(f"zlib-{ordinal}".encode())
        index.write_bytes(batch.canonical_json_bytes({"ordinal": ordinal}))
        shards.append(SimpleNamespace(
            global_shard_ordinal=ordinal,
            compressed_path=compressed,
            index_path=index,
        ))
    def payload(body: dict[str, object], field: str) -> bytes:
        return batch.canonical_json_bytes(_core_self_hash(body, field))

    source_raw = payload({
        "schema": "corpus-authoritative-task-source/v1",
        "task_index": task_index,
        "task_sha256": task["task_sha256"],
    }, "binding_sha256")
    law_raw = payload({
        "schema": "corpus-authoritative-registered-law/v1",
        "task_sha256": task["task_sha256"],
    }, "binding_sha256")
    attempts = []
    for variant, profile in enumerate(profiles):
        for visit in range(1_000):
            attempts.append({
                "variant_ordinal": variant,
                "visit_ordinal": visit,
                "parameter_set_id": profile["parameter_set_id"],
                "status": "optimal",
                "primary_optimum_micro": visit + variant,
                "world": {"block": "R0", "index": visit},
            })
    attempt_raw = payload({
        "schema": "corpus-legal-feasibility-attempt-ledger/v1",
        "attempts": attempts,
    }, "attempt_ledger_sha256")
    matrix_raw = payload({
        "schema": "corpus-legal-feasibility-matrix-authority/v1",
        "task_index": task_index,
    }, "matrix_authority_sha256")
    content_root_raw = payload({
        "schema": "corpus-cbc-evidence-task-root/v1",
        "shard_count": 70,
    }, "task_evidence_root_sha256")
    variant_raws = []
    for variant, profile in enumerate(profiles):
        variant_raws.append(payload({
            "schema": "corpus-legal-feasibility-variant-result/v2",
            "profile": profile,
            "coverage": {
                "unique_candidates": 100 + variant,
                "selected_entries": 80,
            },
            "candidate_score_sha256": f"{variant + 1}" * 64,
            "selected_score_sha256": f"{variant + 2}" * 64,
        }, "result_sha256"))
    parsed_variants = [
        batch.parse_canonical_json_bytes(raw, label="fake variant")
        for raw in variant_raws
    ]
    batch_raw = payload({
        "schema": "corpus-legal-feasibility-batch-result/v1",
        "variant_results": [{
            "ordinal": variant,
            "parameter_set_id": profile["parameter_set_id"],
            "result_sha256": parsed_variants[variant]["result_sha256"],
        } for variant, profile in enumerate(profiles)],
    }, "result_sha256")
    draft_raw = payload({
        "schema": "corpus-legal-feasibility-draft-authority-bundle/v1",
        "task_index": task_index,
    }, "draft_sha256")
    return SimpleNamespace(
        solver_evidence_shards=tuple(shards),
        source_binding_payload=source_raw,
        registered_law_payload=law_raw,
        attempt_ledger_payload=attempt_raw,
        matrix_authority_payload=matrix_raw,
        solver_evidence_task_root_payload=content_root_raw,
        canonical_draft_payload=draft_raw,
        batch_result_payload=batch_raw,
        runtime_policy_payloads=tuple(
            batch.canonical_json_bytes({"payload": f"policy-{i}"})
            for i in range(7)
        ),
        variant_result_payloads=tuple(variant_raws),
    )


def _fake_finalizer(draft: object, **kwargs: object) -> SimpleNamespace:
    assert len(kwargs["solver_evidence_object_identities"]) == 70
    draft_value = batch.parse_canonical_json_bytes(
        draft.canonical_draft_payload, label="fake draft"
    )
    published = _core_self_hash({
        "schema": "corpus-cbc-published-task-evidence-root/v1",
        "shard_count": 70,
    }, "published_task_evidence_root_sha256")
    batch_value = batch.parse_canonical_json_bytes(
        draft.batch_result_payload, label="fake batch result"
    )
    bundle = _core_self_hash({
        "schema": "corpus-legal-feasibility-authority-bundle/v1",
        "draft_sha256": draft_value["draft_sha256"],
        "batch_result_sha256": batch_value["result_sha256"],
    }, "bundle_sha256")
    return SimpleNamespace(
        published_task_evidence_root_payload=batch.canonical_json_bytes(published),
        canonical_bundle_payload=batch.canonical_json_bytes(bundle),
    )


def test_default_off_gate_and_parked_command_do_not_construct_cloud_client() -> None:
    with pytest.raises(transport.CorpusParametricTransportError, match="literal"):
        transport.require_execute_gate(execute=False, environ=ENABLED)
    with pytest.raises(transport.CorpusParametricTransportError, match="=1"):
        transport.require_execute_gate(execute=True, environ={})
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts/run_corpus_parametric_transport.py"), "parked"],
        check=True,
        capture_output=True,
        text=True,
    )
    assert '"enabled":false' in completed.stdout
    assert '"cloud_client_constructed":false' in completed.stdout


def _runtime_iam_validation_kwargs(
    manifest: dict[str, object], iam: dict[str, object]
) -> dict[str, object]:
    retrieval_inputs = [
        identity for identity in iam["required_input_identities"]
        if identity["uri"].startswith(RETRIEVAL_PREFIX)
        or identity == iam["retrieval_prerequisite_identity"]
    ]
    return {
        "service_account": SERVICE_ACCOUNT,
        "foundation_publication_identity": iam[
            "foundation_publication_identity"
        ],
        "batch_manifest_identity": iam["batch_manifest_identity"],
        "evidence_contract_identity": iam["evidence_contract_identity"],
        "retrieval_prerequisite_identity": iam[
            "retrieval_prerequisite_identity"
        ],
        "required_input_identities": iam["required_input_identities"],
        "manifest_input_identities": transport._manifest_input_identities(
            manifest
        ),
        "retrieval_replay_identities": retrieval_inputs,
        "read_prefix_authorities": iam["read_prefix_authorities"],
        "output_prefix": manifest["output_prefix"],
    }


def _rehash_runtime_iam(value: dict[str, object]) -> dict[str, object]:
    changed = deepcopy(value)
    changed.pop("iam_evidence_sha256", None)
    return transport._self_hash(changed, field="iam_evidence_sha256")


def test_runtime_iam_v2_derives_exact_transitive_get_and_create_authority() -> None:
    store, manifest, _, configured = _configured()
    raw = store.read(configured["runtime_iam_evidence"])
    iam = transport.strict_json_bytes(raw, label="runtime IAM")
    assert iam["schema_version"] == transport.RUNTIME_IAM_EVIDENCE_SCHEMA
    assert iam["principal_scope"] == transport.RUNTIME_PRINCIPAL_SCOPE
    assert any(
        identity["uri"] == "gs://retrieval/task0/sidecar.bin"
        for identity in iam["required_input_identities"]
    )
    permissions = {
        tuple(role["includedPermissions"])
        for role in iam["custom_role_definitions"]
    }
    assert permissions == {
        (transport.STORAGE_GET_PERMISSION,),
        (transport.STORAGE_CREATE_PERMISSION,),
    }
    assert transport.validate_runtime_iam_evidence(
        iam, **_runtime_iam_validation_kwargs(manifest, iam)
    )["iam_evidence_sha256"] == iam["iam_evidence_sha256"]

    observed = list(iam["required_input_identities"])
    transport._validate_observed_runtime_gets(
        iam_evidence=iam, observed_identities=observed
    )
    unknown_raw = b"not-retained"
    unknown = _identity(
        "gs://retrieval/task0/unretained.json", unknown_raw, "909"
    )
    with pytest.raises(
        transport.CorpusParametricTransportError,
        match="absent from retained IAM evidence",
    ):
        transport._validate_observed_runtime_gets(
            iam_evidence=iam, observed_identities=[unknown]
        )


def test_guarded_worker_store_blocks_rogue_get_generation_and_current_before_io() -> None:
    store, _, _, configured = _configured()
    iam = transport.strict_json_bytes(
        store.read(configured["runtime_iam_evidence"]), label="runtime IAM"
    )
    guard = transport._TracingReadStore(store)
    guard.authorize(iam)
    rogue_raw = b"rogue"
    rogue = store.seed(
        f"{RETRIEVAL_PREFIX}rogue.bin", rogue_raw, "9999"
    )

    reads_before = store.read_calls
    with pytest.raises(
        transport.CorpusParametricTransportError, match="exact retained inputs"
    ):
        guard.read(rogue)
    assert store.read_calls == reads_before

    generation_reads_before = store.read_generation_calls
    with pytest.raises(
        transport.CorpusParametricTransportError, match="retained inputs"
    ):
        guard.read_generation(
            uri=str(rogue["uri"]), generation=str(rogue["generation"])
        )
    assert store.read_generation_calls == generation_reads_before

    known = next(
        row for row in iam["required_input_identities"]
        if not row["uri"].startswith(iam["output_prefix"])
    )
    resolves_before = store.resolve_calls
    with pytest.raises(
        transport.CorpusParametricTransportError, match="outside output prefix"
    ):
        guard.resolve_current(str(known["uri"]))
    assert store.resolve_calls == resolves_before

    assert guard.read_generation(
        uri=str(known["uri"]), generation=str(known["generation"])
    ) == store.values[(str(known["uri"]), str(known["generation"]))]


def test_runtime_iam_uses_exact_object_equality_without_frozen_prefix_claim() -> None:
    store, manifest, _, configured = _configured()
    retained = transport.strict_json_bytes(
        store.read(configured["runtime_iam_evidence"]), label="runtime IAM"
    )
    exact = store.seed(
        "gs://one-exact-object/authority.json", b"exact", "9001"
    )
    kwargs = _runtime_iam_validation_kwargs(manifest, retained)
    required = [*retained["required_input_identities"], exact]
    capture = transport.strict_json_bytes(
        _runtime_iam_capture_raw(manifest, exact_identities=(exact,)),
        label="IAM capture with exact object",
    )
    rebuilt = transport.build_runtime_iam_evidence(
        policy_capture=capture,
        service_account=SERVICE_ACCOUNT,
        foundation_publication_identity=kwargs[
            "foundation_publication_identity"
        ],
        batch_manifest_identity=kwargs["batch_manifest_identity"],
        evidence_contract_identity=kwargs["evidence_contract_identity"],
        retrieval_prerequisite_identity=kwargs[
            "retrieval_prerequisite_identity"
        ],
        required_input_identities=required,
        manifest_input_identities=kwargs["manifest_input_identities"],
        retrieval_replay_identities=kwargs["retrieval_replay_identities"],
        read_prefix_authorities=kwargs["read_prefix_authorities"],
        output_prefix=manifest["output_prefix"],
    )
    assert rebuilt["read_exact_identities"] == [exact]
    policy = next(
        row["policy"] for row in rebuilt["bucket_policies"]
        if row["bucket"] == "one-exact-object"
    )
    assert (
        f'resource.name == "{transport._resource_name(str(exact["uri"]))}"'
        in policy["bindings"][0]["condition"]["expression"]
    )


def test_preflight_configure_is_read_only_and_freezes_reused_job_name_uid() -> None:
    (
        store, manifest, manifest_identity, evidence_identity,
        prerequisite_identity, foundation_publication_identity,
    ) = _configuration_fixture()
    kwargs = {
        "storage": store,
        "batch_manifest_identity": manifest_identity,
        "evidence_contract_identity": evidence_identity,
        "retrieval_prerequisite_identity": prerequisite_identity,
        "foundation_publication_identity": foundation_publication_identity,
        "runtime_iam_evidence_raw": _runtime_iam_capture_raw(manifest),
        "build_metadata": _build_metadata(),
        "build_id": BUILD_ID,
        "code_sha": CODE_SHA,
        "image": IMAGE,
        "service_account": SERVICE_ACCOUNT,
        "observed_job": _job(),
        "expected_job_name": JOB_NAME,
        "expected_job_uid": JOB_UID,
        "executions": [],
        "schedulers": [],
        "all_regions_complete": True,
        "execute": True,
        "environ": ENABLED,
    }
    before = store.publish_calls
    result = transport.preflight_configure(**kwargs)
    assert result["valid"] is True
    assert result["read_only"] is True
    assert store.publish_calls == before

    changed = {**kwargs, "expected_job_uid": "different-frozen-uid"}
    with pytest.raises(
        transport.CorpusParametricTransportError, match="name/UID"
    ):
        transport.preflight_configure(**changed)
    assert store.publish_calls == before


def test_deployment_attestation_is_bounded_self_hashed_and_drift_closed() -> None:
    manifest, _, _ = _manifest()
    attestation = _deployment_attestation(manifest)
    build = transport.validate_build_metadata(
        _build_metadata(), build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
    )
    validated = transport.validate_deployment_attestation(
        attestation,
        observed_at_utc="2026-08-22T17:59:59Z",
        current_job=_job(),
        expected_build=build,
        expected_service_account=SERVICE_ACCOUNT,
    )
    assert validated["runtime_iam_policy_capture_sha256"] == (
        transport.canonical_sha256(validated["runtime_iam_policy_capture"])
    )
    assert validated["scheduler_census_sha256"] == transport.canonical_sha256([])
    assert validated["max_retries"] == 0
    assert validated["automatic_retry_licensed"] is False

    with pytest.raises(
        transport.CorpusParametricTransportError, match="expired"
    ):
        transport.validate_deployment_attestation(
            attestation,
            observed_at_utc="2026-08-22T18:00:00Z",
            current_job=_job(),
            expected_build=build,
            expected_service_account=SERVICE_ACCOUNT,
        )
    with pytest.raises(transport.CorpusParametricTransportError):
        transport.validate_deployment_attestation(
            attestation,
            observed_at_utc="2026-08-22T12:00:00Z",
            current_job=_job(generation=8),
            expected_build=build,
            expected_service_account=SERVICE_ACCOUNT,
        )
    tampered = deepcopy(attestation)
    tampered["no_scheduler_targets_job"] = False
    with pytest.raises(
        transport.CorpusParametricTransportError, match="self-hash"
    ):
        transport.validate_deployment_attestation(
            tampered,
            observed_at_utc="2026-08-22T12:00:00Z",
            current_job=_job(),
            expected_build=build,
            expected_service_account=SERVICE_ACCOUNT,
        )


def test_attested_configure_and_launch_need_only_current_job_and_executions() -> None:
    (
        store, manifest, manifest_identity, evidence_identity,
        prerequisite_identity, foundation_publication_identity,
    ) = _configuration_fixture()
    attestation = _deployment_attestation(manifest)
    configured = transport.configure_transport(
        storage=store,
        batch_manifest_identity=manifest_identity,
        evidence_contract_identity=evidence_identity,
        retrieval_prerequisite_identity=prerequisite_identity,
        foundation_publication_identity=foundation_publication_identity,
        runtime_iam_evidence_raw=b"",
        build_metadata=_build_metadata(),
        build_id=BUILD_ID,
        code_sha=CODE_SHA,
        image=IMAGE,
        service_account=SERVICE_ACCOUNT,
        parked_job=_job(),
        expected_job_name=JOB_NAME,
        expected_job_uid=JOB_UID,
        executions=[],
        schedulers=None,
        all_regions_complete=False,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
        deployment_attestation=attestation,
        observed_at_utc="2026-08-22T12:00:00Z",
    )
    ready = transport.consume_phase_launch(
        storage=store,
        contract_identity=configured["transport_contract"],
        task_index=0,
        phase="producer",
        parked_job=_job(),
        executions=[],
        schedulers=None,
        all_regions_complete=False,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
        deployment_attestation=attestation,
        observed_at_utc="2026-08-22T12:01:00Z",
    )
    assert ready["launch_permitted"] is True
    assert ready["automatic_retry_licensed"] is False
    configured_governance = configured["governance_authorization"]
    assert configured_governance["governance_mode"] == (
        "bounded-deployment-attestation"
    )
    assert configured_governance["deployment_attestation_sha256"] == (
        attestation["attestation_sha256"]
    )
    assert ready["governance_authorization"] == configured_governance | {
        "governance_observed_at_utc": "2026-08-22T12:01:00Z"
    }


def test_consumed_attestation_can_bind_and_terminalize_after_expiry(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    (
        store, manifest, manifest_identity, evidence_identity,
        prerequisite_identity, foundation_publication_identity,
    ) = _configuration_fixture()
    attestation = _deployment_attestation(manifest)
    configured = transport.configure_transport(
        storage=store,
        batch_manifest_identity=manifest_identity,
        evidence_contract_identity=evidence_identity,
        retrieval_prerequisite_identity=prerequisite_identity,
        foundation_publication_identity=foundation_publication_identity,
        runtime_iam_evidence_raw=b"",
        build_metadata=_build_metadata(),
        build_id=BUILD_ID,
        code_sha=CODE_SHA,
        image=IMAGE,
        service_account=SERVICE_ACCOUNT,
        parked_job=_job(),
        expected_job_name=JOB_NAME,
        expected_job_uid=JOB_UID,
        executions=[],
        schedulers=None,
        all_regions_complete=False,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
        deployment_attestation=attestation,
        observed_at_utc="2026-08-22T17:58:00Z",
    )
    contract_identity = configured["transport_contract"]
    _, contract_raw = store.resolve_current(contract_identity["uri"])
    contract = transport.validate_transport_contract(
        transport.strict_json_bytes(contract_raw, label="contract")
    )
    ready = transport.consume_phase_launch(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        parked_job=_job(),
        executions=[],
        schedulers=None,
        all_regions_complete=False,
        created_at_utc="2026-08-22T17:59:00Z",
        execute=True,
        environ=ENABLED,
        deployment_attestation=attestation,
        observed_at_utc="2026-08-22T17:59:00Z",
    )
    task = contract["tasks"][0]
    for uri_key in ("producer_launch_intent_uri", "producer_launch_ledger_uri"):
        _, raw = store.resolve_current(task[uri_key])
        retained = transport.strict_json_bytes(raw, label=uri_key)
        assert retained["governance_authorization"] == ready[
            "governance_authorization"
        ]
    running = _execution(
        contract=contract,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        execution_id="producer-expiry",
        execution_uid="producer-expiry-uid",
        terminal=False,
    )
    recovered = transport.recover_phase_execution_name(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        executions=[running],
        execute=True,
        environ=ENABLED,
    )
    assert recovered["execution_id"] == "producer-expiry"
    bound = transport.bind_phase_execution(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        execution_metadata=running,
        parked_job=_job(),
        executions=[running],
        schedulers=None,
        all_regions_complete=False,
        created_at_utc="2026-08-22T19:00:00Z",
        execute=True,
        environ=ENABLED,
    )
    assert bound["governance_authorization"] == ready[
        "governance_authorization"
    ]
    _, bound_raw = store.resolve_current(task["producer_execution_name_uri"])
    assert transport.strict_json_bytes(
        bound_raw, label="execution-name ledger"
    )["governance_authorization"] == ready["governance_authorization"]
    terminal = _execution(
        contract=contract,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        execution_id="producer-expiry",
        execution_uid="producer-expiry-uid",
        terminal=True,
    )
    terminal_receipt = transport._validate_terminal_governance_census(
        storage=store,
        contract=contract,
        contract_identity=transport.object_identity(
            contract_identity, label="contract identity"
        ),
        task_index=0,
        phase="producer",
        terminal=transport._validate_execution_spec(
            terminal,
            contract=contract,
            contract_identity=transport.object_identity(
                contract_identity, label="contract identity"
            ),
            task_index=0,
            phase="producer",
            require_terminal_success=True,
        ),
        parked_job=_job(),
        executions=[terminal],
        schedulers=None,
        all_regions_complete=False,
        observed_at_utc="2026-08-22T19:01:00Z",
    )
    assert terminal_receipt["governance_authorization"] == ready[
        "governance_authorization"
    ]

    with pytest.raises(
        transport.CorpusParametricTransportError, match="expired"
    ):
        transport.consume_phase_launch(
            storage=store,
            contract_identity=contract_identity,
            task_index=0,
            phase="verifier",
            parked_job=_job(),
            executions=[terminal],
            schedulers=None,
            all_regions_complete=False,
            created_at_utc="2026-08-22T19:02:00Z",
            execute=True,
            environ=ENABLED,
            deployment_attestation=attestation,
            observed_at_utc="2026-08-22T19:02:00Z",
        )

    renewed = transport.renew_deployment_attestation(
        existing_attestation=attestation,
        current_job=_job(),
        executions=[terminal],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc="2026-08-22T19:03:00Z",
        expires_at_utc="2026-08-23T01:03:00Z",
    )
    assert renewed["renewed_from_attestation_sha256"] == attestation[
        "attestation_sha256"
    ]
    assert renewed["runtime_iam_policy_capture"] == attestation[
        "runtime_iam_policy_capture"
    ]
    assert renewed["runtime_iam_policy_capture_sha256"] == attestation[
        "runtime_iam_policy_capture_sha256"
    ]
    with pytest.raises(
        transport.CorpusParametricTransportError, match="renewal chain"
    ):
        transport.renew_deployment_attestation(
            existing_attestation=renewed,
            current_job=_job(),
            executions=[terminal],
            schedulers=[],
            all_regions_complete=True,
            created_at_utc="2026-08-23T01:04:00Z",
            expires_at_utc="2026-08-23T07:04:00Z",
        )
    monkeypatch.setattr(
        transport,
        "_reopen_producer_close",
        lambda **kwargs: ({"uri": "fixture"}, {"closed": True}),
    )
    verifier_ready = transport.consume_phase_launch(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="verifier",
        parked_job=_job(),
        executions=[terminal],
        schedulers=None,
        all_regions_complete=False,
        created_at_utc="2026-08-22T19:04:00Z",
        execute=True,
        environ=ENABLED,
        deployment_attestation=renewed,
        observed_at_utc="2026-08-22T19:04:00Z",
    )
    assert verifier_ready["launch_permitted"] is True
    assert verifier_ready["governance_authorization"][
        "deployment_attestation_sha256"
    ] == renewed["attestation_sha256"]

def test_runtime_iam_v2_rejects_self_attestation_and_policy_escalations() -> None:
    store, manifest, _, configured = _configured()
    iam = transport.strict_json_bytes(
        store.read(configured["runtime_iam_evidence"]), label="runtime IAM"
    )
    kwargs = _runtime_iam_validation_kwargs(manifest, iam)

    old_v1 = {
        "schema_version": "corpus-parametric-runtime-iam-evidence/v1",
        "captured_at_utc": NOW,
        "project": transport.PROJECT,
        "service_account": SERVICE_ACCOUNT,
        "all_input_gets_conditionally_authorized": True,
    }
    with pytest.raises(
        transport.CorpusParametricTransportError, match="fields differ"
    ):
        transport.validate_runtime_iam_evidence(old_v1, **kwargs)

    def rejected(value: dict[str, object], pattern: str) -> None:
        with pytest.raises(transport.CorpusParametricTransportError, match=pattern):
            transport.validate_runtime_iam_evidence(
                _rehash_runtime_iam(value), **kwargs
            )

    project_role = deepcopy(iam)
    project_role["project_policy"]["bindings"] = [{
        "role": "roles/viewer",
        "members": [f"serviceAccount:{SERVICE_ACCOUNT}"],
    }]
    rejected(project_role, "project-level role")

    public = deepcopy(iam)
    public["bucket_policies"][0]["policy"]["bindings"].append({
        "role": "roles/storage.objectViewer", "members": ["allUsers"]
    })
    rejected(public, "public access")

    object_viewer = deepcopy(iam)
    object_viewer["bucket_policies"][0]["policy"]["bindings"][0]["role"] = (
        "roles/storage.objectViewer"
    )
    rejected(object_viewer, "predefined")

    grants_list = deepcopy(iam)
    read_role = next(
        row for row in grants_list["custom_role_definitions"]
        if row["includedPermissions"] == [transport.STORAGE_GET_PERMISSION]
    )
    read_role["includedPermissions"].append("storage.objects.list")
    rejected(grants_list, "overbroad")

    grants_delete = deepcopy(iam)
    create_role = next(
        row for row in grants_delete["custom_role_definitions"]
        if row["includedPermissions"] == [transport.STORAGE_CREATE_PERMISSION]
    )
    create_role["includedPermissions"].append("storage.objects.delete")
    rejected(grants_delete, "overbroad")

    no_ubla = deepcopy(iam)
    no_ubla["bucket_metadata"][0]["metadata"]["iamConfiguration"][
        "uniformBucketLevelAccess"
    ]["enabled"] = False
    rejected(no_ubla, "UBLA/PAP")

    no_pap = deepcopy(iam)
    no_pap["bucket_metadata"][0]["metadata"]["iamConfiguration"][
        "publicAccessPrevention"
    ] = "inherited"
    rejected(no_pap, "UBLA/PAP")

    missing_bucket = deepcopy(iam)
    missing_bucket["bucket_policies"].pop()
    rejected(missing_bucket, "policy census")

    wrong_condition = deepcopy(iam)
    wrong_condition["bucket_policies"][0]["policy"]["bindings"][0][
        "condition"
    ]["title"] = "unbound-read"
    rejected(wrong_condition, "condition title")

    overlapping = deepcopy(iam)
    overlapping["read_prefixes"].append(
        f'{manifest["output_prefix"]}nested/'
    )
    overlapping["read_prefixes"].sort()
    rejected(overlapping, "overlap")

    operator_broadening = deepcopy(iam)
    operator_broadening["read_prefix_authorities"][0]["prefixes"][0] = (
        "gs://foundation/"
    )
    rejected(operator_broadening, "identity graph differs")

    credential = deepcopy(iam)
    credential["project_policy"]["password"] = "must-never-be-retained"
    rejected(credential, "credential material")

    camel_credential = deepcopy(iam)
    camel_credential["project_policy"]["privateKeyData"] = "forbidden"
    rejected(camel_credential, "credential material")

    incomplete_asset = deepcopy(iam)
    incomplete_asset["effective_access_analyses"]["runtime_identity"][
        "fullyExplored"
    ] = False
    rejected(incomplete_asset, "incomplete or differs")

    asset_error = deepcopy(iam)
    asset_error["effective_access_analyses"]["runtime_identity"][
        "nonCriticalErrors"
    ] = [{"code": "PARTIAL"}]
    rejected(asset_error, "incomplete or differs")

    group_inheritance = deepcopy(iam)
    group_inheritance["effective_access_analyses"]["runtime_identity"][
        "mainAnalysis"
    ]["analysisResults"][0]["identityList"]["groupEdges"] = [{
        "sourceNode": "group:unsafe@example.com",
        "targetNode": f"serviceAccount:{SERVICE_ACCOUNT}",
    }]
    rejected(group_inheritance, "inherited")

    effective_list = deepcopy(iam)
    effective_list["effective_access_analyses"]["runtime_identity"][
        "mainAnalysis"
    ]["analysisResults"][0]["accessControlLists"][0]["accesses"].append({
        "permission": "storage.objects.list"
    })
    rejected(effective_list, "effective runtime access")

    public_effective = deepcopy(iam)
    public_effective["effective_access_analyses"]["all_users"][
        "mainAnalysis"
    ]["analysisResults"] = [{"unexpected": "public grant"}]
    rejected(public_effective, "public access")


def test_build_gate_requires_every_expansion_test_cli_import_and_shell_smoke() -> None:
    assert transport.validate_build_metadata(
        _build_metadata(), build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
    )["image"] == IMAGE
    for step_index in (0, 2, 3, 4):
        changed = _build_metadata()
        retained = list(changed["steps"][step_index]["args"])
        retained[1] = "\n".join(retained[1].splitlines()[:-1])
        changed["steps"][step_index]["args"] = retained
        with pytest.raises(
            transport.CorpusParametricTransportError, match="not exact"
        ):
            transport.validate_build_metadata(
                changed, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
            )

    commented = _build_metadata()
    commented["steps"][3]["args"][1] = "\n".join(
        f"# {row}" for row in commented["steps"][3]["args"][1].splitlines()
    )
    with pytest.raises(
        transport.CorpusParametricTransportError, match="not exact"
    ):
        transport.validate_build_metadata(
            commented, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
        )

    masked = _build_metadata()
    masked["steps"][0]["args"][1] += " || true"
    with pytest.raises(
        transport.CorpusParametricTransportError, match="mask or branch"
    ):
        transport.validate_build_metadata(
            masked, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
        )

    shell_state_masked = _build_metadata()
    shell_state_masked["steps"][0]["args"][1] = (
        "set +e\n" + shell_state_masked["steps"][0]["args"][1]
    )
    with pytest.raises(
        transport.CorpusParametricTransportError, match="not exact"
    ):
        transport.validate_build_metadata(
            shell_state_masked, build_id=BUILD_ID, code_sha=CODE_SHA,
            image=IMAGE,
        )

    extra_smoke = _build_metadata()
    extra_smoke["steps"][3]["args"][1] += "\necho not-a-bound-smoke"
    with pytest.raises(
        transport.CorpusParametricTransportError, match="not exact"
    ):
        transport.validate_build_metadata(
            extra_smoke, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
        )

    unbound_step_environment = _build_metadata()
    unbound_step_environment["steps"][0]["env"] = [
        "PYTEST_ADDOPTS=--ignore=tests/test_corpus_parametric_transport.py"
    ]
    with pytest.raises(
        transport.CorpusParametricTransportError, match="unbound execution fields"
    ):
        transport.validate_build_metadata(
            unbound_step_environment, build_id=BUILD_ID, code_sha=CODE_SHA,
            image=IMAGE,
        )

    injected_step = _build_metadata()
    injected_step["steps"].insert(2, {
        "id": "unbound-successful-step",
        "name": "gcr.io/cloud-builders/docker",
        "status": "SUCCESS",
        "exitCode": 0,
        "args": ["build", "-t", IMAGE_TAG, "."],
    })
    with pytest.raises(
        transport.CorpusParametricTransportError, match="step census/order"
    ):
        transport.validate_build_metadata(
            injected_step, build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE,
        )


def test_parked_job_rejects_inherited_secrets_volumes_and_mounts() -> None:
    build = transport.validate_build_metadata(
        _build_metadata(), build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
    )
    for mutate in (
        lambda value: value["spec"]["template"]["spec"]["template"]["spec"]
        ["containers"][0]["env"].append({
            "name": "INHERITED_SECRET",
            "valueSource": {"secretKeyRef": {"secret": "unsafe", "version": "1"}},
        }),
        lambda value: value["spec"]["template"]["spec"]["template"]["spec"]
        ["volumes"].append({"name": "inherited"}),
        lambda value: value["spec"]["template"]["spec"]["template"]["spec"]
        ["containers"][0]["volumeMounts"].append({
            "name": "inherited", "mountPath": "/unsafe"
        }),
        lambda value: value["spec"]["template"]["spec"]["template"]["spec"].update({
            "vpcAccess": {"connector": "unsafe"}
        }),
        lambda value: value["spec"]["template"]["spec"]["template"]["spec"].update({
            "cloudSqlInstances": ["unsafe"]
        }),
        lambda value: value["spec"]["template"]["spec"]["template"]["spec"].update({
            "tags": ["unsafe"]
        }),
        lambda value: value["spec"]["template"]["spec"]["template"]["spec"]
        ["containers"][0].update({"startupProbe": {"tcpSocket": {"port": 9}}}),
        lambda value: value["spec"]["template"]["spec"]["template"]["spec"]
        ["containers"][0].update({"workingDir": "/unsafe"}),
        lambda value: value["spec"]["template"]["spec"]["template"]["spec"]
        ["containers"][0].update({"ports": [{"containerPort": 9999}]}),
        lambda value: value["spec"]["template"].update({
            "metadata": {"annotations": {"unsafe.example/attachment": "1"}}
        }),
    ):
        job = _job()
        mutate(job)
        with pytest.raises(transport.CorpusParametricTransportError):
            transport.validate_parked_job(
                job,
                job_name=JOB_NAME,
                expected_uid=JOB_UID,
                build=build,
                service_account=SERVICE_ACCOUNT,
            )


def test_parked_job_accepts_only_exact_empty_cloudsql_clear_marker() -> None:
    build = transport.validate_build_metadata(
        _build_metadata(), build_id=BUILD_ID, code_sha=CODE_SHA, image=IMAGE
    )
    cleared = _job()
    cleared["spec"]["template"]["metadata"] = {
        "annotations": {
            "run.googleapis.com/client-name": "gcloud",
            "run.googleapis.com/client-version": "579.0.0",
            "run.googleapis.com/execution-environment": "gen2",
            "run.googleapis.com/cloudsql-instances": "",
        }
    }
    assert transport.validate_parked_job(
        cleared,
        job_name=JOB_NAME,
        expected_uid=JOB_UID,
        build=build,
        service_account=SERVICE_ACCOUNT,
    )["generation"] == "7"

    for inherited in ("project:region:instance", " ", None, [], {}):
        poisoned = deepcopy(cleared)
        poisoned["spec"]["template"]["metadata"]["annotations"][
            "run.googleapis.com/cloudsql-instances"
        ] = inherited
        with pytest.raises(
            transport.CorpusParametricTransportError,
            match="inherited Cloud SQL instances are forbidden",
        ):
            transport.validate_parked_job(
                poisoned,
                job_name=JOB_NAME,
                expected_uid=JOB_UID,
                build=build,
                service_account=SERVICE_ACCOUNT,
            )


def test_retrieval_task0_prerequisite_is_transitively_reopened_and_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store = FakeStore()
    identity, raw = _prerequisite(store)
    accepted, reopened = transport.reopen_retrieval_task0_prerequisite(
        storage=store, prerequisite_identity=identity
    )
    assert reopened == raw
    assert accepted["task_index"] == 0
    assert accepted["every_unique_lineup_scored_in_every_world"] is True

    class RejectingRetrievalCore(FakeRetrievalCore):
        @staticmethod
        def validate_retrieval_task_result(**kwargs: object) -> dict[str, object]:
            del kwargs
            raise ValueError("semantic replay rejected")

    monkeypatch.setattr(
        transport, "_retrieval_module", lambda: RejectingRetrievalCore
    )
    with pytest.raises(
        transport.CorpusParametricTransportError, match="semantic replay"
    ):
        transport.reopen_retrieval_task0_prerequisite(
            storage=store, prerequisite_identity=identity
        )
    monkeypatch.setattr(
        transport, "_retrieval_module", lambda: FakeRetrievalCore
    )

    for key, bad_value in (
        ("accepted", False),
        ("task_index", 1),
        ("complete_result", False),
        ("partial_result", True),
        ("partial_object_count", 1),
        ("every_unique_lineup_scored_in_every_world", False),
    ):
        changed = deepcopy(accepted)
        changed[key] = bad_value
        changed.pop("acceptance_sha256")
        changed = transport._self_hash(changed, field="acceptance_sha256")
        with pytest.raises(transport.CorpusParametricTransportError):
            transport.validate_retrieval_task0_prerequisite(changed)

    missing = accepted["task_result_object"]
    del store.values[(missing["uri"], missing["generation"])]
    with pytest.raises(Exception):
        transport.reopen_retrieval_task0_prerequisite(
            storage=store, prerequisite_identity=identity
        )


def test_configure_accepts_only_one_task_smoke_or_complete_54_task_batch() -> None:
    _, _, smoke_contract, configured = _configured(task_count=1)
    assert smoke_contract["batch_mode"] == "one-task-smoke"
    assert smoke_contract["matrix_cell_count"] == 7
    assert configured["launch_permitted"] is False

    _, _, full_contract, _ = _configured(task_count=54)
    assert full_contract["batch_mode"] == "complete-54-task"
    assert full_contract["task_count"] == 54
    assert full_contract["matrix_cell_count"] == 378
    assert len(full_contract["tasks"]) == 54

    # The two enumerated v7 half-batch lanes are the only other shapes.
    _, _, lane_a, _ = _configured(task_count=28)
    assert lane_a["batch_mode"] == "lane-a-28-task"
    assert lane_a["matrix_cell_count"] == 196
    _, _, lane_b, _ = _configured(task_count=26)
    assert lane_b["batch_mode"] == "lane-b-26-task"
    assert lane_b["matrix_cell_count"] == 182

    manifest, raw, _ = _manifest(2)
    identity = transport.object_identity(
        batch.object_identity_for_json(
            manifest, uri=manifest["manifest_uri"], generation="100"
        ),
        label="manifest",
    )
    with pytest.raises(
        transport.CorpusParametricTransportError, match="one-task smoke"
    ):
        transport.build_transport_contract(
            created_at_utc=NOW,
            manifest=manifest,
            manifest_identity=identity,
            evidence_contract_identity=transport.identity_for_bytes(
                uri=manifest["output_prefix"] + "governance/evidence.json",
                generation="1",
                raw=raw,
            ),
            retrieval_prerequisite_identity=transport.identity_for_bytes(
                uri="gs://retrieval/task0/accepted.json", generation="1", raw=raw
            ),
            foundation_publication_identity=transport.identity_for_bytes(
                uri=f"{FOUNDATION_PREFIX}governance/publication-completion.json",
                generation="1",
                raw=raw,
            ),
            runtime_iam_identity=transport.identity_for_bytes(
                uri=manifest["output_prefix"] + "governance/iam.json",
                generation="1",
                raw=raw,
            ),
            prefix_claim_identity=transport.identity_for_bytes(
                uri=manifest["create_once_prefix_claim_uri"],
                generation="1",
                raw=raw,
            ),
            build={
                "build_id": BUILD_ID,
                "code_repository": transport.EXPECTED_CODE_REPOSITORY,
                "code_sha": CODE_SHA,
                "image": IMAGE,
            },
            job=transport.job_identity(_job()),
            service_account=SERVICE_ACCOUNT,
        )


def test_one_shot_launch_is_recover_only_and_requires_all_region_census() -> None:
    store, _, contract, configured = _configured()
    contract_identity = configured["transport_contract"]
    with pytest.raises(
        transport.CorpusParametricTransportError, match="all-region"
    ):
        transport.consume_phase_launch(
            storage=store,
            contract_identity=contract_identity,
            task_index=0,
            phase="producer",
            parked_job=_job(),
            executions=[],
            schedulers=[],
            all_regions_complete=False,
            created_at_utc=NOW,
            execute=True,
            environ=ENABLED,
        )
    ready = transport.consume_phase_launch(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        parked_job=_job(),
        executions=[],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert ready["launch_permitted"] is True
    assert ready["worker_args"][1] == "execute-task"
    recovered = transport.consume_phase_launch(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        parked_job=_job(),
        executions=[],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert recovered["launch_permitted"] is False
    assert recovered["worker_args"] == []
    assert recovered["recovery_action"] == "census-only-never-relaunch"


def test_validate_only_reports_loaded_source_without_solving(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    store, manifest, _, configured = _configured()
    task = manifest["tasks"][0]
    _, _, core, _ = transport._modules()
    loaded = SimpleNamespace(source=SimpleNamespace(
        prepared=SimpleNamespace(slate_id=task["slate_id"]),
        binding=SimpleNamespace(
            artifact_source_authority_task_sha256=task[
                "artifact_source_authority_task_sha256"
            ]
        ),
    ))
    monkeypatch.setattr(
        core, "_load_authoritative_inputs", lambda **kwargs: loaded
    )

    result = transport.validate_task_inputs(
        storage=store,
        contract_identity=configured["transport_contract"],
        task_index=0,
        repository_root=ROOT,
    )

    assert result["slate_id"] == task["slate_id"]
    assert result["artifact_source_authority_task_sha256"] == task[
        "artifact_source_authority_task_sha256"
    ]
    assert result["solve_invoked"] is False
    assert result["uses_realized_outcomes"] is False


@pytest.mark.parametrize("domain_failure", [False, True])
def test_producer_failure_discloses_only_controlled_domain_detail(
    domain_failure: bool,
) -> None:
    store, _, contract, configured = _configured()
    contract_identity = configured["transport_contract"]
    transport.consume_phase_launch(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        parked_job=_job(),
        executions=[],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    producer_running = _execution(
        contract=contract,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        execution_id="producer-failure",
        execution_uid="producer-failure-uid",
        terminal=False,
    )
    transport.bind_phase_execution(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        execution_metadata=producer_running,
        parked_job=_job(),
        executions=[producer_running],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )

    _, _, core, _ = transport._modules()
    failure = (
        core.CorpusLegalFeasibilityError("runtime source file is absent")
        if domain_failure
        else RuntimeError("sensitive sentinel")
    )

    def fail_with_context(**kwargs: object) -> object:
        del kwargs
        raise failure

    with pytest.raises(transport.CorpusParametricTransportError) as captured:
        transport.execute_producer_task(
            storage=store,
            contract_identity=contract_identity,
            task_index=0,
            repository_root=ROOT,
            execute=True,
            environ=_runtime_environ(
                "producer-failure", "producer-failure-uid"
            ),
            wait_seconds=0,
            producer=fail_with_context,
            finalizer=_fake_finalizer,
        )
    expected = "authoritative producer failed"
    if domain_failure:
        expected += ": runtime source file is absent"
    assert str(captured.value) == expected
    assert captured.value.__cause__ is failure
    assert domain_failure or "sensitive sentinel" not in str(captured.value)


def test_complete_two_execution_flow_accepts_only_after_independent_verifier() -> None:
    store, manifest, contract, configured = _configured()
    contract_identity = configured["transport_contract"]
    producer_ready = transport.consume_phase_launch(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        parked_job=_job(),
        executions=[],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert producer_ready["launch_permitted"] is True
    producer_running = _execution(
        contract=contract,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        execution_id="producer-1",
        execution_uid="producer-uid",
        terminal=False,
    )
    transport.bind_phase_execution(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        execution_metadata=producer_running,
        parked_job=_job(),
        executions=[producer_running],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    inventory_before_worker = store.inventory_calls
    transport.execute_producer_task(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        repository_root=ROOT,
        execute=True,
        environ=_runtime_environ("producer-1", "producer-uid"),
        wait_seconds=0,
        producer=_fake_producer,
        finalizer=_fake_finalizer,
    )
    # Worker uses exact GET/create seams and never lists the bucket.
    assert store.inventory_calls == inventory_before_worker

    producer_terminal = _execution(
        contract=contract,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        execution_id="producer-1",
        execution_uid="producer-uid",
        terminal=True,
    )
    rogue_terminal = _execution(
        contract=contract,
        contract_identity=contract_identity,
        task_index=0,
        phase="producer",
        execution_id="producer-rogue",
        execution_uid="producer-rogue-uid",
        terminal=True,
    )
    with pytest.raises(
        transport.CorpusParametricTransportError, match="exactly one"
    ):
        transport.close_producer_task(
            storage=store,
            contract_identity=contract_identity,
            task_index=0,
            terminal_execution_metadata=producer_terminal,
            parked_job=_job(),
            executions=[producer_terminal, rogue_terminal],
            schedulers=[],
            all_regions_complete=True,
            created_at_utc=NOW,
            execute=True,
            environ=ENABLED,
        )
    assert contract["tasks"][0]["science_terminal_uri"] not in store.current
    fresh_terminal_schedulers = [{
        "name": "projects/fixture/locations/us-central1/jobs/unrelated",
        "httpTarget": {"uri": "https://example.test/unrelated:run"},
    }]
    closed = transport.close_producer_task(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        terminal_execution_metadata=producer_terminal,
        parked_job=_job(),
        executions=[producer_terminal],
        schedulers=fresh_terminal_schedulers,
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert closed["terminal_acceptance"] is False
    assert closed["independent_verification_complete"] is False
    task_paths = contract["tasks"][0]
    producer_close_raw = store.resolve_current(task_paths["producer_close_uri"])[1]
    producer_close = transport.strict_json_bytes(
        producer_close_raw, label="producer close"
    )
    producer_governance = producer_close["terminal_governance_census"][
        "governance_authorization"
    ]
    assert producer_governance["governance_mode"] == "live-all-region-census"
    assert producer_governance["governance_observed_at_utc"] == NOW
    terminal_census = producer_close["terminal_governance_census"]
    assert producer_governance["scheduler_census_sha256"] == (
        transport.canonical_sha256([])
    )
    assert terminal_census["terminal_scheduler_census_sha256"] == (
        transport.canonical_sha256(fresh_terminal_schedulers)
    )
    assert terminal_census["launch_governance_authorization_sha256"] == (
        transport.canonical_sha256(producer_governance)
    )
    assert terminal_census["launch_governance_authorization_sha256"] != (
        terminal_census["terminal_scheduler_census_sha256"]
    )
    assert terminal_census["scheduler_census_sha256"] == terminal_census[
        "terminal_scheduler_census_sha256"
    ]
    legacy_terminal_census = deepcopy(terminal_census)
    legacy_terminal_census.pop("launch_governance_authorization_sha256")
    legacy_terminal_census.pop("terminal_scheduler_census_sha256")
    legacy_terminal_census["scheduler_census_sha256"] = producer_governance[
        "scheduler_census_sha256"
    ]
    validated_producer_terminal = transport._validate_execution_spec(
        producer_terminal,
        contract=contract,
        contract_identity=transport.object_identity(
            contract_identity, label="contract identity"
        ),
        task_index=0,
        phase="producer",
        require_terminal_success=True,
    )
    assert transport._validate_terminal_census_receipt(
        legacy_terminal_census,
        contract=contract,
        task_index=0,
        phase="producer",
        terminal=validated_producer_terminal,
    )["scheduler_census_sha256"] == producer_governance[
        "scheduler_census_sha256"
    ]
    assert task_paths["accepted_terminal_uri"] not in store.current

    verifier_ready = transport.consume_phase_launch(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="verifier",
        parked_job=_job(),
        executions=[producer_terminal],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert verifier_ready["worker_args"][1] == "verify-task"
    verifier_running = _execution(
        contract=contract,
        contract_identity=contract_identity,
        task_index=0,
        phase="verifier",
        execution_id="verifier-1",
        execution_uid="verifier-uid",
        terminal=False,
    )
    transport.bind_phase_execution(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        phase="verifier",
        execution_metadata=verifier_running,
        parked_job=_job(),
        executions=[producer_terminal, verifier_running],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )

    def fake_verifier(**kwargs: object) -> SimpleNamespace:
        reader = kwargs["object_reader"]

        def exact_read(identity: dict[str, object]) -> bytes:
            return reader.read_generation(
                uri=str(identity["uri"]),
                generation=str(identity["generation"]),
            )

        result_raw = exact_read(kwargs["task_result_identity"])
        result = batch.parse_canonical_json_bytes(result_raw, label="result")
        terminal_identity = result["execution"]["terminal_receipt"]
        terminal_raw = exact_read(terminal_identity)
        terminal = batch.parse_canonical_json_bytes(terminal_raw, label="terminal")
        authorities = terminal["authorities"]

        def authority(role: str) -> dict[str, object]:
            return batch.parse_canonical_json_bytes(
                exact_read(authorities[role]), label=f"fake {role}"
            )

        source = authority("source_binding")
        law = authority("registered_law")
        attempts = authority("attempt_ledger")
        matrix = authority("matrix_authority")
        content_root = authority("content_task_evidence_root")
        published_root = authority("published_task_evidence_root")
        draft = authority("draft_authority_bundle")
        bundle = authority("authority_bundle")
        batch_result = authority("batch_result")
        variants = [
            batch.parse_canonical_json_bytes(
                exact_read(row["object_identity"]), label=f"fake variant {ordinal}"
            )
            for ordinal, row in enumerate(terminal["variant_result_objects"])
        ]
        coverage_summaries = []
        endpoint_summaries = []
        outside_summaries = []
        for ordinal, (profile, variant) in enumerate(zip(
            manifest["parameter_sets"], variants, strict=True
        )):
            parameter_id = profile["parameter_set_id"]
            unique_count = variant["coverage"]["unique_candidates"]
            lattice = {
                "block_order": ["R0", "R1", "R2", "R3", "R4"],
                "worlds_per_block": 10_000,
                "order": "block-major-then-world-index-ascending",
            }
            coverage = _core_self_hash({
                "schema": "corpus-score-matrix-coverage/v1",
                "parameter_set_id": parameter_id,
                "dtype": "float64-le",
                "generated_unique_roster_count": unique_count,
                "candidate_score_row_count": unique_count,
                "selected_roster_count": 80,
                "selected_score_row_count": 80,
                "world_count": 50_000,
                "ordered_world_lattice": lattice,
                "ordered_world_lattice_sha256": batch.canonical_sha256(lattice),
                "generated_unique_roster_identity_sha256": f"{ordinal + 1}" * 64,
                "selected_roster_identity_sha256": f"{ordinal + 2}" * 64,
                "candidate_score_sha256": variant["candidate_score_sha256"],
                "selected_score_sha256": variant["selected_score_sha256"],
                "complete_generated_unique_roster_row_coverage": True,
                "complete_selected_roster_row_coverage": True,
                "selected_rows_are_exact_candidate_subset": True,
            }, "coverage_sha256")
            endpoint = _core_self_hash({
                "schema": "corpus-score-free-endpoint-summary/v1",
                "parameter_set_id": parameter_id,
                "world_count": 50_000,
                "simulated_candidate_ceiling_c": 210.0 + ordinal,
                "simulated_exact80_maximum_s": 209.0 + ordinal,
                "simulated_conversion_gap_c_minus_s": 1.0,
                "candidate_world_max_sha256": f"{ordinal + 2}" * 64,
                "selected_world_max_sha256": f"{ordinal + 3}" * 64,
                "score_matrix_coverage_sha256": coverage["coverage_sha256"],
            }, "endpoint_summary_sha256")
            outside = _core_self_hash({
                "schema": "corpus-outside-incumbent-law-nonvacuity/v1",
                "variant_ordinal": ordinal,
                "parameter_set_id": parameter_id,
                "predicate": "fixture",
                "removed_rule": None,
                "generated_unique_count": unique_count,
                "outside_incumbent_law_unique_count": ordinal,
                "required_witness_count": 0 if ordinal == 0 else 1,
                "qualifying_witness_count": ordinal,
                "independent_five_rule_violation_counts": {},
                "generated_unique_roster_identity_sha256": f"{ordinal + 3}" * 64,
                "outside_roster_violation_rows_sha256": f"{ordinal + 4}" * 64,
                "passed": True,
            }, "outside_law_nonvacuity_sha256")
            coverage_summaries.append(coverage)
            endpoint_summaries.append(endpoint)
            outside_summaries.append(outside)
        from nfl_dfs.research import corpus_legal_feasibility_verifier as verifier

        paired = verifier._paired_primary_optimum_summary(attempts["attempts"])
        common = manifest["common_law"]
        manifest_task = manifest["tasks"][0]
        body = {
            "schema": "corpus-legal-feasibility-independent-verification/v2",
            "task_index": 0,
            "season": manifest_task["season"],
            "week": manifest_task["week"],
            "slate_id": manifest_task["slate_id"],
            "source_binding_sha256": source["binding_sha256"],
            "registered_law_sha256": law["binding_sha256"],
            "attempt_ledger_sha256": attempts["attempt_ledger_sha256"],
            "matrix_authority_sha256": matrix["matrix_authority_sha256"],
            "solver_evidence_task_root_sha256": content_root[
                "task_evidence_root_sha256"
            ],
            "published_task_evidence_root_sha256": published_root[
                "published_task_evidence_root_sha256"
            ],
            "draft_sha256": draft["draft_sha256"],
            "authority_bundle_sha256": bundle["bundle_sha256"],
            "artifact_source_authority_completion_object_sha256": common[
                "artifact_source_authority_completion"
            ]["sha256"],
            "artifact_source_authority_completion_sha256": common[
                "artifact_source_authority_completion_sha256"
            ],
            "artifact_source_authority_task_sha256": manifest_task[
                "artifact_source_authority_task_sha256"
            ],
            "evidence_contract_sha256": terminal["evidence_contract_sha256"],
            "task_result_sha256": result["task_result_sha256"],
            "terminal_receipt_sha256": terminal["terminal_receipt_sha256"],
            "variant_result_sha256s": [
                value["result_sha256"] for value in variants
            ],
            "batch_result_sha256": batch_result["result_sha256"],
            "candidate_score_sha256s": [
                value["candidate_score_sha256"] for value in variants
            ],
            "selected_score_sha256s": [
                value["selected_score_sha256"] for value in variants
            ],
            "paired_primary_optimum_summary": paired,
            "outside_incumbent_law_summaries": outside_summaries,
            "score_free_endpoint_summaries": endpoint_summaries,
            "score_matrix_coverage_summaries": coverage_summaries,
            "verified_cell_count": 7_000,
            "verified_solver_stage_count": 14_000,
            "verified_unique_candidate_count": sum(
                value["coverage"]["unique_candidates"] for value in variants
            ),
            "verified_selected_entry_count": 560,
            "verified_gate_ids": list(transport._VERIFIER_GATE_IDS),
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
            "historical_scoring_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        }
        payload = batch.canonical_json_bytes({
            **body, "verification_sha256": batch.canonical_sha256(body)
        })
        return SimpleNamespace(canonical_payload=payload)

    def partial_verifier(**kwargs: object) -> SimpleNamespace:
        result_raw = store.read(kwargs["task_result_identity"])
        result = batch.parse_canonical_json_bytes(result_raw, label="result")
        body = {
            "schema": "corpus-legal-feasibility-independent-verification/v2",
            "task_index": 0,
            "task_result_sha256": result["task_result_sha256"],
        }
        return SimpleNamespace(canonical_payload=batch.canonical_json_bytes({
            **body,
            "verification_sha256": batch.canonical_sha256(body),
        }))

    inventory_before_verifier = store.inventory_calls
    with pytest.raises(
        transport.CorpusParametricTransportError,
        match="independent verification fields differ",
    ):
        transport.execute_verifier_task(
            storage=store,
            contract_identity=contract_identity,
            task_index=0,
            repository_root=ROOT,
            execute=True,
            environ=_runtime_environ("verifier-1", "verifier-uid"),
            wait_seconds=0,
            verifier_call=partial_verifier,
        )
    assert task_paths["independent_verification_uri"] not in store.current
    transport.execute_verifier_task(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        repository_root=ROOT,
        execute=True,
        environ=_runtime_environ("verifier-1", "verifier-uid"),
        wait_seconds=0,
        verifier_call=fake_verifier,
    )
    assert store.inventory_calls == inventory_before_verifier
    assert task_paths["accepted_terminal_uri"] not in store.current

    verifier_terminal = _execution(
        contract=contract,
        contract_identity=contract_identity,
        task_index=0,
        phase="verifier",
        execution_id="verifier-1",
        execution_uid="verifier-uid",
        terminal=True,
    )
    accepted = transport.accept_verified_task(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        terminal_execution_metadata=verifier_terminal,
        parked_job=_job(),
        executions=[producer_terminal, verifier_terminal],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert accepted["accepted"] is True
    acceptance_raw = store.resolve_current(task_paths["accepted_terminal_uri"])[1]
    acceptance = transport.strict_json_bytes(acceptance_raw, label="acceptance")
    assert acceptance["complete_evidence_receipt"] is True
    assert acceptance["independent_verification_complete"] is True
    assert acceptance["partial_result"] is False
    verifier_governance = acceptance["terminal_governance_census"][
        "governance_authorization"
    ]
    assert verifier_governance["governance_mode"] == "live-all-region-census"
    assert verifier_governance["governance_observed_at_utc"] == NOW

    rogue_uri = manifest["output_prefix"] + "rogue-extra.json"
    store.seed(rogue_uri, b"rogue", "999")
    with pytest.raises(
        transport.CorpusParametricTransportError, match="inventory differs"
    ):
        transport.finish_batch(
            storage=store,
            contract_identity=contract_identity,
            created_at_utc=NOW,
            execute=True,
            environ=ENABLED,
        )
    assert (
        manifest["output_prefix"] + "governance/batch-completion.json"
        not in store.current
    )
    del store.current[rogue_uri]
    del store.values[(rogue_uri, "999")]
    finished = transport.finish_batch(
        storage=store,
        contract_identity=contract_identity,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert finished["accepted"] is True
    assert finished["task_count"] == 1
    assert finished["matrix_cell_count"] == 7
    batch_acceptance_raw = store.resolve_current(
        manifest["output_prefix"] + "governance/batch-acceptance.json"
    )[1]
    batch_acceptance = transport.strict_json_bytes(
        batch_acceptance_raw, label="batch acceptance"
    )
    assert batch_acceptance["complete"] is True
    assert batch_acceptance["partial_result"] is False


def test_partial_or_identity_mismatched_verification_never_accepts() -> None:
    store, _, contract, configured = _configured()
    contract_identity = configured["transport_contract"]
    with pytest.raises(transport.CorpusParametricTransportError):
        transport.accept_verified_task(
            storage=store,
            contract_identity=contract_identity,
            task_index=0,
            terminal_execution_metadata={},
            parked_job=_job(),
            executions=[],
            schedulers=[],
            all_regions_complete=True,
            created_at_utc=NOW,
            execute=True,
            environ=ENABLED,
        )
    assert contract["tasks"][0]["accepted_terminal_uri"] not in store.current


def test_bad_attestation_ttl_fails_before_any_cloud_mutation(
    tmp_path: Path,
) -> None:
    marker = tmp_path / "gcloud-called"
    for name, body in {
        "gcloud": f"#!/bin/sh\ntouch '{marker}'\nexit 99\n",
        "jq": "#!/bin/sh\nexit 99\n",
    }.items():
        executable = tmp_path / name
        executable.write_text(body, encoding="utf-8")
        executable.chmod(0o755)
    run_dir = tmp_path / "run"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "CORPUS_PARAMETRIC_RESEARCH_ENABLED": "1",
        "CORPUS_PARAMETRIC_PYTHON": sys.executable,
        "CORPUS_PARAMETRIC_RUN_DIR": str(run_dir),
        "CORPUS_PARAMETRIC_JOB": JOB_NAME,
        "CORPUS_PARAMETRIC_IMAGE": IMAGE,
        "CORPUS_PARAMETRIC_BUILD_ID": BUILD_ID,
        "CORPUS_PARAMETRIC_CODE_SHA": CODE_SHA,
        "CORPUS_PARAMETRIC_SERVICE_ACCOUNT": SERVICE_ACCOUNT,
        "CORPUS_PARAMETRIC_EXPECTED_JOB_UID": JOB_UID,
        "CORPUS_PARAMETRIC_RUNTIME_IAM_FILE": str(tmp_path / "iam.json"),
        "CORPUS_PARAMETRIC_BUILD_METADATA_FILE": str(
            run_dir / "build.json"
        ),
        "CORPUS_PARAMETRIC_DEPLOYMENT_ATTESTATION_TTL_SECONDS": "86401",
    }
    for stem in (
        "FOUNDATION_PUBLICATION", "MANIFEST", "EVIDENCE_CONTRACT",
        "RETRIEVAL_PREREQUISITE",
    ):
        env[f"CORPUS_PARAMETRIC_{stem}_URI"] = f"gs://fixture/{stem}.json"
        env[f"CORPUS_PARAMETRIC_{stem}_GENERATION"] = "1"
        env[f"CORPUS_PARAMETRIC_{stem}_SHA256"] = "a" * 64
        env[f"CORPUS_PARAMETRIC_{stem}_BYTES"] = "1"
    completed = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/cloud_corpus_parametric_v1_reuse.sh"),
            "--execute",
            "configure",
        ],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
    )
    assert completed.returncode == 2
    assert "TTL exceeds 86400" in completed.stderr
    assert not marker.exists()
    assert not (run_dir / "job-before.json").exists()


def test_operator_legacy_postlaunch_seam_captures_fresh_scheduler_census(
    tmp_path: Path,
) -> None:
    attempt = tmp_path / "attempt"
    attempt.mkdir()
    shell = ROOT / "scripts/cloud_corpus_parametric_v1_reuse.sh"
    command = r'''
source "$SHELL_UNDER_TEST"
capture_all_region_schedulers() {
  printf '%s\n' '[]' >"$1"
}
postlaunch_governance_args legacy-governance-free "$ATTEMPT_DIR"
'''
    completed = subprocess.run(
        ["bash", "-c", command],
        cwd=ROOT,
        env={
            **os.environ,
            "SHELL_UNDER_TEST": str(shell),
            "ATTEMPT_DIR": str(attempt),
        },
        check=True,
        capture_output=True,
        text=True,
    )
    scheduler_file = attempt / "terminal-schedulers.json"
    assert scheduler_file.read_text(encoding="utf-8") == "[]\n"
    assert completed.stdout.splitlines() == [
        "--schedulers-file",
        str(scheduler_file),
        "--all-regions-complete",
    ]


def test_operator_recovers_governance_free_launch_with_live_census(
    tmp_path: Path,
) -> None:
    scheduler_marker = tmp_path / "scheduler-called"
    fake_gcloud = tmp_path / "gcloud"
    fake_gcloud.write_text(
        """#!/bin/sh
case "$*" in
  *"scheduler locations list"*)
    printf '%s\n' '[{"locationId":"us-central1"}]'
    ;;
  *"scheduler jobs list"*)
    touch "$SCHEDULER_MARKER"
    printf '%s\n' '[]'
    ;;
  *"run jobs executions list"*)
    printf '%s\n' '[{"metadata":{"name":"old-execution"}}]'
    ;;
  *"run jobs executions describe"*|*"run jobs describe"*)
    printf '%s\n' '{}'
    ;;
  *)
    exit 91
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_gcloud.chmod(0o755)
    fake_python = tmp_path / "transport-python"
    fake_python.write_text(
        """#!/bin/sh
case "$2" in
  recover-name)
    printf '%s\n' '{"execution_id":"old-execution","governance_mode":"legacy-governance-free"}'
    ;;
  bind-execution)
    printf '%s\n' '{"execution_id":"old-execution","governance_authorization":null}'
    ;;
  *)
    exit 92
    ;;
esac
""",
        encoding="utf-8",
    )
    fake_python.chmod(0o755)
    run_dir = tmp_path / "operator-run"
    env = {
        **os.environ,
        "PATH": f"{tmp_path}:/usr/bin:/bin",
        "SCHEDULER_MARKER": str(scheduler_marker),
        "CORPUS_PARAMETRIC_RESEARCH_ENABLED": "1",
        "CORPUS_PARAMETRIC_PYTHON": str(fake_python),
        "CORPUS_PARAMETRIC_RUN_DIR": str(run_dir),
        "CORPUS_PARAMETRIC_JOB": JOB_NAME,
        "CORPUS_PARAMETRIC_TASK_INDEX": "0",
        "CORPUS_PARAMETRIC_CONTRACT_URI": "gs://fixture/contract.json",
        "CORPUS_PARAMETRIC_CONTRACT_GENERATION": "1",
        "CORPUS_PARAMETRIC_CONTRACT_SHA256": "a" * 64,
        "CORPUS_PARAMETRIC_CONTRACT_BYTES": "1",
    }
    completed = subprocess.run(
        [
            "bash",
            str(ROOT / "scripts/cloud_corpus_parametric_v1_reuse.sh"),
            "--execute",
            "recover-producer",
        ],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "execution bound" in completed.stdout
    assert scheduler_marker.exists()
    assert (
        run_dir / "tasks/000-producer-bound.json"
    ).is_file()
    attempts = list(
        (run_dir / "tasks").glob("000-producer-recover-attempt-*/terminal-schedulers.json")
    )
    assert len(attempts) == 1
    assert attempts[0].read_text(encoding="utf-8") == "[]\n"


def test_shell_keeps_configure_launch_recover_watch_and_finish_separate() -> None:
    shell = ROOT / "scripts/cloud_corpus_parametric_v1_reuse.sh"
    subprocess.run(["bash", "-n", str(shell)], check=True)
    source = shell.read_text(encoding="utf-8")
    for mode in (
        "configure",
        "launch-producer",
        "recover-producer",
        "watch-producer",
        "launch-verifier",
        "recover-verifier",
        "watch-verifier",
        "finish-batch",
    ):
        assert mode in source
    assert "--max-retries 0" in source
    assert "--clear-secrets --clear-volumes --clear-volume-mounts" in source
    for fragment in (
        "preflight-configure",
        "CORPUS_PARAMETRIC_EXPECTED_JOB_UID",
        "--foundation-publication-uri",
        "--clear-vpc-connector",
        "--clear-cloudsql-instances",
        "--clear-network",
        "--startup-probe=\"\"",
        "--workdir=\"\"",
        "status=97",
    ):
        assert fragment in source
    assert "--clear-network-tags" not in source
    assert "--async" in source
    assert "never relaunch" in source
    assert "set -o noclobber" in source
    assert "CORPUS_PARAMETRIC_RESEARCH_ENABLED=1 is required" in source
    assert "gcloud run jobs create" not in source
    assert "sleep " not in source
    assert "timestamp_once" not in source
    for event_key in (
        "timestamp_for configured",
        "-${phase}-launch",
        "-${phase}-bound",
        "-producer-closed",
        "-verifier-accepted",
        "timestamp_for batch-accepted",
    ):
        assert event_key in source
    assert "transport-created-at.txt" not in source
    assert source.index("validate-build") < source.index("gcloud run jobs update")
    assert source.index("preflight-configure") < source.index(
        "gcloud run jobs update"
    )
    assert "--region \"$REGION\" --quiet >/dev/null || true" not in source
    assert "configure-attested" in source
    assert "create-deployment-attestation" in source
    hot_path = source[source.index("launch_mode()") : source.index("finish_batch_mode()")]
    assert "capture_all_region_schedulers" not in hot_path
    assert "--deployment-attestation-file" in source
    assert "--observed-at-utc" in source
    assert "TTL exceeds 86400 seconds" in source
    assert "path must be absolute and canonical" in source
    configure_source = source[
        source.index("configure_mode()") : source.index("configure_attested_mode()")
    ]
    assert configure_source.index(
        "validate_new_deployment_attestation_settings"
    ) < configure_source.index('capture_job "$before_json"')
    assert configure_source.index(
        "create-deployment-attestation"
    ) < configure_source.index('"$PYTHON_BIN" "$TRANSPORT_SCRIPT" configure')
    assert configure_source.index(
        'capture_all_region_schedulers "$schedulers_after"'
    ) < configure_source.index("created_at=\"$(date -u")
    assert configure_source.index("created_at=\"$(date -u") < (
        configure_source.index("create-deployment-attestation")
    )
    assert "renew-deployment-attestation" in source
    renewal_source = source[
        source.index("current_or_renew_deployment_attestation()") :
        source.index("postlaunch_governance_args()")
    ]
    assert "CORPUS_PARAMETRIC_RUNTIME_IAM_FILE" not in renewal_source
    assert "build-runtime-iam-evidence" not in renewal_source
    assert renewal_source.index(
        'capture_all_region_schedulers "$schedulers"'
    ) < renewal_source.index("created_at=\"$(date -u")


def test_policy_derived_effective_access_recomputes_and_fails_closed() -> None:
    # Analyzer-quota fallback: each record must declare policy_derived
    # with an explicit analyzer-unavailable reason, and the validator
    # recomputes every grant from the capture's own version-3 bucket
    # policies, refusing any divergence, unregistered role, or public
    # member. The analyzer path remains preferred and untouched.
    store, manifest, _, configured = _configured()
    iam = transport.strict_json_bytes(
        store.read(configured["runtime_iam_evidence"]), label="runtime IAM"
    )
    kwargs = _runtime_iam_validation_kwargs(manifest, iam)
    member = f"serviceAccount:{SERVICE_ACCOUNT}"
    role_permissions = {
        str(row["name"]): str(row["includedPermissions"][0])
        for row in iam["custom_role_definitions"]
    }
    unavailable = {
        "reason": "cloudasset analyze_iam_policy daily quota exhausted",
        "observed_at_utc": NOW,
    }
    grants = transport._policy_derived_grants(
        iam["bucket_policies"],
        member=member,
        role_permissions=role_permissions,
    )
    derived = deepcopy(iam)
    derived["effective_access_analyses"] = {
        "runtime_identity": {
            "policy_derived": True,
            "analyzer_unavailable": dict(unavailable),
            "derived_grants": [
                {
                    "role": role,
                    "resource": resource,
                    "condition_title": title,
                    "prefixes": sorted(prefixes),
                    "exact_objects": sorted(exact_objects),
                    "permissions": sorted(permissions),
                }
                for (
                    role, resource, title, prefixes, exact_objects,
                    permissions,
                ) in grants
            ],
        },
        "all_users": {
            "policy_derived": True,
            "analyzer_unavailable": dict(unavailable),
            "public_bindings_found": 0,
        },
        "all_authenticated_users": {
            "policy_derived": True,
            "analyzer_unavailable": dict(unavailable),
            "public_bindings_found": 0,
        },
    }
    accepted = transport.validate_runtime_iam_evidence(
        _rehash_runtime_iam(derived), **kwargs
    )
    assert accepted["effective_access_analyses"]["runtime_identity"][
        "policy_derived"
    ] is True

    def rejected(value: dict[str, object], pattern: str) -> None:
        with pytest.raises(
            transport.CorpusParametricTransportError, match=pattern
        ):
            transport.validate_runtime_iam_evidence(
                _rehash_runtime_iam(value), **kwargs
            )

    tampered = deepcopy(derived)
    tampered["effective_access_analyses"]["runtime_identity"][
        "derived_grants"
    ] = tampered["effective_access_analyses"]["runtime_identity"][
        "derived_grants"
    ][:-1]
    rejected(tampered, "differ from the captured policies")

    unreasoned = deepcopy(derived)
    del unreasoned["effective_access_analyses"]["all_users"][
        "analyzer_unavailable"
    ]
    rejected(unreasoned, "analyzer-unavailable record")

    public = deepcopy(derived)
    public["bucket_policies"][0]["policy"]["bindings"].append({
        "role": "roles/storage.objectViewer", "members": ["allUsers"]
    })
    rejected(public, "public")
