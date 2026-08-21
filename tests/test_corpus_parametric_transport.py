from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
from types import SimpleNamespace
import subprocess
import sys

import pytest

from nfl_dfs.research import corpus_batch_evidence_contract as evidence
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
SERVICE_ACCOUNT = (
    "corpus-parametric@nfl-predictions-503414.iam.gserviceaccount.com"
)
JOB_NAME = "atlas-minimal-c-s2023-w1-v1"
JOB_UID = "fixture-job-uid"
NOW = "2026-08-21T18:00:00Z"
ENABLED = {transport.ENABLE_ENV: "1"}
PLACEHOLDER_RAW: dict[tuple[str, str], bytes] = {}


class FakeStore:
    def __init__(self) -> None:
        self.values: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, str] = {}
        self.next_generation = 1
        self.inventory_calls = 0

    def seed(self, uri: str, raw: bytes, generation: str) -> dict[str, object]:
        assert uri not in self.current
        self.values[(uri, generation)] = raw
        self.current[uri] = generation
        return _identity(uri, raw, generation)

    def read(self, identity: dict[str, object]) -> bytes:
        raw = self.values[(str(identity["uri"]), str(identity["generation"]))]
        if len(raw) != identity["bytes"] or sha256(raw).hexdigest() != identity["sha256"]:
            raise ValueError("identity mismatch")
        return raw

    def read_generation(self, *, uri: str, generation: str) -> bytes:
        return self.values[(uri, generation)]

    def publish(
        self, uri: str, raw: bytes, media_type: str = "application/json"
    ) -> dict[str, object]:
        del media_type
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


def _identity(uri: str, raw: bytes, generation: str = "1") -> dict[str, object]:
    return {
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _placeholder(name: str, ordinal: int) -> dict[str, object]:
    raw = f"placeholder-{name}-{ordinal}".encode()
    identity = _identity(
        f"gs://inputs/contracts/{name}.json", raw, str(ordinal + 1)
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
    return _identity("gs://inputs/contracts/code-source.json", raw, "2"), raw


def _common_law(code_identity: dict[str, object]) -> dict[str, object]:
    source_receipts = {"later_source_freeze": _placeholder("later-freeze", 10)}
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
            "source-authority-completion", 11
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
            "solver_timeout_seconds": 120,
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
    return result


def _task(task_index: int, *, batch_id: str) -> dict[str, object]:
    artifacts = {
        role: _placeholder(f"task-{task_index}-{role}", 100 + task_index * 5 + ordinal)
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


def _manifest(task_count: int = 1) -> tuple[dict[str, object], bytes, bytes]:
    code_identity, code_raw = _code_source()
    batch_id = "corpus-transport-test-v1"
    manifest = batch.build_batch_manifest(
        batch_id=batch_id,
        created_at_utc=NOW,
        output_prefix=f"gs://dedicated/batches/{batch_id}/",
        common_law=_common_law(code_identity),
        tasks=[_task(index, batch_id=batch_id) for index in range(task_count)],
    )
    return manifest, batch.canonical_json_bytes(manifest), code_raw


def _job(*, generation: str = "7") -> dict[str, object]:
    task_spec = {
        "maxRetries": 0,
        "timeoutSeconds": "86400s",
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
            "resources": {"limits": {"cpu": "8000m", "memory": "32Gi"}},
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
    return {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": source},
        "sourceProvenance": {"resolvedGitSource": source},
        "results": {"images": [{"digest": IMAGE.rsplit("@", 1)[1]}]},
        "steps": [{"status": "SUCCESS", "exitCode": 0}],
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
        "gs://retrieval/source/snapshot.json", snapshot_raw, "20"
    )
    suite = _core_self_hash({
        "schema_version": "fake-retrieval-suite/v1",
        "snapshot_manifest_identity": snapshot_identity,
        "tasks": [{
            "task_index": 0,
            "task_id": "task-0",
            "result_uri": "gs://retrieval/task0/result.json",
        }],
    }, "suite_manifest_sha256")
    suite_raw = batch.canonical_json_bytes(suite)
    suite_identity = store.seed(
        "gs://retrieval/task0/suite.json", suite_raw, "21"
    )
    sidecar_identity = store.seed(
        "gs://retrieval/task0/sidecar.bin", b"task0-sidecar", "22"
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
        "gs://retrieval/task0/result.json", result_raw, "23"
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
        "gs://retrieval/task0/completion.json", completion_raw, "24"
    )
    governance: dict[str, dict[str, object]] = {}
    for ordinal, field in enumerate(
        transport._RETRIEVAL_TERMINAL_GOVERNANCE_FIELDS, start=25
    ):
        governance[field] = store.seed(
            f"gs://retrieval/task0/{field}.json",
            batch.canonical_json_bytes({"field": field}),
            str(ordinal),
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
        "gs://retrieval/task0/terminal.json", terminal_raw, "31"
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
    identity = store.seed("gs://retrieval/task0/accepted.json", raw, "32")
    return identity, raw


def _runtime_iam_raw(manifest: dict[str, object]) -> bytes:
    inputs = transport._manifest_input_identities(manifest)
    body = {
        "schema_version": "corpus-parametric-runtime-iam-evidence/v1",
        "captured_at_utc": NOW,
        "project": transport.PROJECT,
        "service_account": SERVICE_ACCOUNT,
        "input_object_identity_set_sha256": transport.canonical_sha256(inputs),
        "output_prefix": manifest["output_prefix"],
        "all_input_gets_conditionally_authorized": True,
        "output_get_create_conditionally_authorized": True,
        "project_level_roles_absent": True,
        "object_list_granted": False,
        "object_delete_granted": False,
        "bucket_uniform_access": True,
        "public_access_prevention": True,
    }
    return transport.canonical_json_bytes(
        transport._self_hash(body, field="iam_evidence_sha256")
    )


def _configured(
    *, task_count: int = 1
) -> tuple[FakeStore, dict[str, object], dict[str, object], dict[str, object]]:
    store = FakeStore()
    manifest, manifest_raw, code_raw = _manifest(task_count)
    manifest_identity = store.seed(manifest["manifest_uri"], manifest_raw, "100")
    evidence_contract = evidence.build_corpus_batch_evidence_contract(
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
    configured = transport.configure_transport(
        storage=store,
        batch_manifest_identity=manifest_identity,
        evidence_contract_identity=evidence_identity,
        retrieval_prerequisite_identity=prerequisite_identity,
        runtime_iam_evidence_raw=_runtime_iam_raw(manifest),
        build_metadata=_build_metadata(),
        build_id=BUILD_ID,
        code_sha=CODE_SHA,
        image=IMAGE,
        service_account=SERVICE_ACCOUNT,
        parked_job=_job(),
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
        "timeoutSeconds": "86400s",
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
            "resources": {"limits": {"cpu": "8000m", "memory": "32Gi"}},
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
    closed = transport.close_producer_task(
        storage=store,
        contract_identity=contract_identity,
        task_index=0,
        terminal_execution_metadata=producer_terminal,
        parked_job=_job(),
        executions=[producer_terminal],
        schedulers=[],
        all_regions_complete=True,
        created_at_utc=NOW,
        execute=True,
        environ=ENABLED,
    )
    assert closed["terminal_acceptance"] is False
    assert closed["independent_verification_complete"] is False
    task_paths = contract["tasks"][0]
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
        result_raw = store.read(kwargs["task_result_identity"])
        result = batch.parse_canonical_json_bytes(result_raw, label="result")
        terminal_identity = result["execution"]["terminal_receipt"]
        terminal_raw = store.read(terminal_identity)
        terminal = batch.parse_canonical_json_bytes(terminal_raw, label="terminal")
        authorities = terminal["authorities"]

        def authority(role: str) -> dict[str, object]:
            return batch.parse_canonical_json_bytes(
                store.read(authorities[role]), label=f"fake {role}"
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
                store.read(row["object_identity"]), label=f"fake variant {ordinal}"
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
    assert "--async" in source
    assert "never relaunch" in source
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
