from __future__ import annotations

from copy import deepcopy
from hashlib import sha256
import importlib.util
from pathlib import Path
import re
import shlex
from types import ModuleType
from typing import Any

import pytest

from nfl_dfs.research import corpus_expansion_build as expansion_build
from nfl_dfs.research import corpus_neo4j_transport as transport
from nfl_dfs.research import corpus_retrieval_neo4j as projection
from scripts import run_corpus_neo4j_transport as run_cli


ROOT = Path(__file__).resolve().parents[1]
BUILD_ID = "12345678-1234-1234-1234-123456789abc"
JOB_NAME = "corpus-graph-job"
JOB_UID = "corpus-graph-job-uid"
SERVICE_ACCOUNT = "corpus-graph@nfl-predictions-503414.iam.gserviceaccount.com"


def _fixture_module() -> ModuleType:
    path = ROOT / "tests/test_corpus_retrieval_neo4j.py"
    spec = importlib.util.spec_from_file_location("_corpus_graph_fixture_source", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIXTURES = _fixture_module()


def _registry_fixture_module() -> ModuleType:
    path = ROOT / "tests/test_corpus_strategy_registry.py"
    spec = importlib.util.spec_from_file_location(
        "_corpus_strategy_registry_fixture_source", path
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


REGISTRY_FIXTURES = _registry_fixture_module()


class FakeStorage:
    def __init__(self) -> None:
        self.exact: dict[tuple[str, str], bytes] = {}
        self.current: dict[str, transport.ObjectIdentity] = {}
        self.next_generation = 900_000
        self.list_calls = 0

    def add(self, identity_value: object, raw: bytes) -> transport.ObjectIdentity:
        identity = transport.object_identity(identity_value, label="fake object")
        assert len(raw) == identity.bytes
        assert sha256(raw).hexdigest() == identity.sha256
        self.exact[(identity.uri, identity.generation)] = raw
        self.current[identity.uri] = identity
        return identity

    def read_exact(self, identity: transport.ObjectIdentity) -> bytes:
        return self.exact[(identity.uri, identity.generation)]

    def resolve_optional(
        self, uri: str,
    ) -> tuple[transport.ObjectIdentity, bytes] | None:
        identity = self.current.get(uri)
        if identity is None:
            return None
        return identity, self.read_exact(identity)

    def publish_create_once(
        self, uri: str, raw: bytes,
    ) -> transport.ObjectIdentity:
        existing = self.resolve_optional(uri)
        if existing is not None:
            if existing[1] != raw:
                raise transport.CorpusNeo4jTransportError("fake create conflict")
            return existing[0]
        self.next_generation += 1
        identity = transport.ObjectIdentity(
            uri=uri,
            generation=str(self.next_generation),
            sha256=sha256(raw).hexdigest(),
            bytes=len(raw),
        )
        self.exact[(identity.uri, identity.generation)] = raw
        self.current[uri] = identity
        return identity

    def remove_current(self, uri: str) -> None:
        identity = self.current.pop(uri)
        del self.exact[(identity.uri, identity.generation)]

    def list_blobs(self, *_args: object, **_kwargs: object) -> None:
        self.list_calls += 1
        raise AssertionError("worker LIST is forbidden")


class FakeGraph:
    def __init__(self, deployment: dict[str, object]) -> None:
        self.database = str(deployment["database"])
        self.deployment = deployment
        self.nodes: dict[str, dict[str, object]] = {}
        self.relationships: dict[str, dict[str, object]] = {}
        self.schema_bootstrapped = False

    def component(self) -> dict[str, object]:
        return dict(self.deployment["server"])

    def census(self) -> dict[str, object]:
        namespaces = sorted({
            str(row["workstream_namespace"]) for row in self.nodes.values()
        })
        return {
            "node_count": len(self.nodes),
            "relationship_count": len(self.relationships),
            "node_labels": [] if not self.nodes else ["CorpusRetrievalEntity"],
            "relationship_types": (
                [] if not self.relationships else ["CORPUS_RELATION"]
            ),
            "workstream_namespaces": namespaces,
        }

    def bootstrap_schema(self, statements: list[str] | tuple[str, ...]) -> None:
        assert tuple(statements) == projection.SCHEMA_STATEMENTS
        assert not self.nodes and not self.relationships
        self.schema_bootstrapped = True

    def apply(self, plan: projection.Neo4jLoadPlan) -> dict[str, object]:
        assert self.schema_bootstrapped
        for raw in plan.nodes:
            row = dict(raw)
            prior = self.nodes.get(str(row["id"]))
            if prior is not None and prior != row:
                raise transport.CorpusNeo4jTransportError("fake node conflict")
            self.nodes[str(row["id"])] = row
        for raw in plan.relationships:
            row = dict(raw)
            prior = self.relationships.get(str(row["edge_key"]))
            if prior is not None and prior != row:
                raise transport.CorpusNeo4jTransportError("fake edge conflict")
            self.relationships[str(row["edge_key"])] = row
        return projection.build_load_result_receipt(
            plan,
            database=self.database,
            node_count=len(plan.nodes),
            relationship_count=len(plan.relationships),
        )

    def verify(self, plan: projection.Neo4jLoadPlan) -> dict[str, object]:
        exact = all(
            self.nodes.get(str(row["id"])) == dict(row) for row in plan.nodes
        ) and all(
            self.relationships.get(str(row["edge_key"])) == dict(row)
            for row in plan.relationships
        )
        if not exact:
            raise transport.CorpusNeo4jTransportError("fake graph replay differs")
        return {
            "plan_sha256": plan.plan_sha256,
            "verified_node_count": len(plan.nodes),
            "verified_relationship_count": len(plan.relationships),
            "exact": True,
        }

    def suite_census(
        self, *, batch_id: str, registry_id: str,
    ) -> dict[str, object]:
        tasks = sorted(
            (
                int(row["task_index"]),
                str(row["slate_id"]),
            )
            for row in self.nodes.values()
            if row["kind"] == "CorpusParametricTask"
            and row["run_id"] == batch_id
        )
        arms = [
            row for row in self.nodes.values()
            if row["kind"] == "CorpusParametricArm" and row["run_id"] == batch_id
        ]
        namespaces = sorted({
            str(row["workstream_namespace"]) for row in self.nodes.values()
        })
        registry_nodes = [
            row for row in self.nodes.values()
            if row["workstream_namespace"] == transport.STRATEGY_REGISTRY_NAMESPACE
            and row["run_id"] == registry_id
        ]
        registry_node_ids = {str(row["id"]) for row in registry_nodes}
        registry_kind_counts = {
            kind: sum(row["kind"] == kind for row in registry_nodes)
            for kind in sorted({str(row["kind"]) for row in registry_nodes})
        }
        return {
            "batch_id": batch_id,
            "task_count": len(tasks),
            "arm_count": len(arms),
            "task_indexes": [row[0] for row in tasks],
            "slate_ids": [row[1] for row in tasks],
            "registry_id": registry_id,
            "registry_node_count": len(registry_nodes),
            "registry_relationship_count": sum(
                str(row["from_id"]) in registry_node_ids
                or str(row["to_id"]) in registry_node_ids
                for row in self.relationships.values()
            ),
            "registry_kind_counts": registry_kind_counts,
            "workstream_namespaces": namespaces,
            "reserved_population_node_count": sum(
                row["workstream_namespace"] == "corpus-population-research"
                for row in self.nodes.values()
            ),
            "reserved_realized_outcome_node_count": sum(
                row["workstream_namespace"]
                == transport.REALIZED_OUTCOME_NAMESPACE
                for row in self.nodes.values()
            ),
        }

    def run_read_only_query(
        self, database: str, cypher: str, parameters: dict[str, object],
    ) -> list[dict[str, object]]:
        assert database == self.database
        assert parameters["namespace"] == transport.STRATEGY_REGISTRY_NAMESPACE
        assert "CREATE" not in cypher and "MERGE" not in cypher
        return [{"query_sha256": sha256(cypher.encode("utf-8")).hexdigest()}]

    def query_smoke(self, *, run_id: str, task_id: str) -> dict[str, object]:
        kinds = (
            "LineupCandidate", "CorpusAssociationMeasurement",
            "CorpusCorrelationMeasurement", "CorpusStrategySplitMeasurement",
            "CorpusArtifactPointer",
        )
        return {
            "retrieval_kind_counts": {
                kind: sum(
                    row["kind"] == kind
                    and row["run_id"] == run_id
                    and row["task_id"] == task_id
                    for row in self.nodes.values()
                )
                for kind in kinds
            },
            "reserved_population_node_count": sum(
                row["workstream_namespace"] == "corpus-population-research"
                for row in self.nodes.values()
            ),
            "reserved_realized_outcome_node_count": sum(
                row["workstream_namespace"] == "corpus-realized-outcomes"
                for row in self.nodes.values()
            ),
            "read_only": True,
        }


def _execution_row(name: str, *, state: str = "True") -> dict[str, object]:
    status: dict[str, object] = {
        "conditions": [{"type": "Completed", "status": state}],
    }
    if state == "True":
        status["succeededCount"] = 1
    return {"metadata": {"name": name}, "status": status}


def _parked_contract(
    deployment: dict[str, object], *, role: str, image: str, code_sha: str,
) -> dict[str, str]:
    principal = deployment["principal_secret_versions"][role]
    return {
        "image": image,
        "code_sha": code_sha,
        "build_id": BUILD_ID,
        "service_account": SERVICE_ACCOUNT,
        "uri": "neo4j+s://corpus.graph.example",
        "database": str(deployment["database"]),
        "provider_resource_id": str(deployment["provider_resource_id"]),
        "username_secret_version": principal["username"],
        "password_secret_version": principal["password"],
    }


def _parked_job(
    deployment: dict[str, object], *, role: str, image: str, code_sha: str,
) -> dict[str, object]:
    contract = _parked_contract(
        deployment, role=role, image=image, code_sha=code_sha
    )

    def secret_row(name: str, identity: str) -> dict[str, object]:
        prefix, version = identity.rsplit("/versions/", 1)
        return {
            "name": name,
            "valueSource": {
                "secretKeyRef": {"name": prefix, "key": version}
            },
        }

    literals = {
        transport.TRANSPORT_ENABLE_ENV: "1",
        "CORPUS_NEO4J_CONFIGURED_ROLE": role,
        transport.URI_ENV: contract["uri"],
        transport.DATABASE_ENV: contract["database"],
        transport.PROVIDER_RESOURCE_ENV: contract["provider_resource_id"],
        transport.USERNAME_SECRET_VERSION_ENV: contract[
            "username_secret_version"
        ],
        transport.PASSWORD_SECRET_VERSION_ENV: contract[
            "password_secret_version"
        ],
        "CORPUS_NEO4J_IMAGE": image,
        "CORPUS_NEO4J_BUILD_ID": BUILD_ID,
        "CODE_SHA": code_sha,
    }
    container = {
        "image": image,
        "command": ["python"],
        "args": ["scripts/run_corpus_neo4j_transport.py", "parked"],
        "env": [
            *({"name": key, "value": value} for key, value in literals.items()),
            secret_row(
                transport.USERNAME_ENV, contract["username_secret_version"]
            ),
            secret_row(
                transport.PASSWORD_ENV, contract["password_secret_version"]
            ),
        ],
        "resources": {"limits": {"cpu": "2000m", "memory": "4Gi"}},
    }
    return {
        "metadata": {
            "name": JOB_NAME,
            "uid": JOB_UID,
            "generation": 7,
            "resourceVersion": "resource-version-7",
        },
        "spec": {"template": {
            "metadata": {
                "annotations": {
                    "run.googleapis.com/client-name": (
                        "corpus-neo4j-governed-rest"
                    ),
                    "run.googleapis.com/client-version": "1.0.0",
                    "run.googleapis.com/execution-environment": "gen2",
                },
                "labels": {"client.knative.dev/nonce": BUILD_ID},
            },
            "spec": {
                "taskCount": 1,
                "parallelism": 1,
                "template": {"spec": {
                    "containers": [container],
                    "maxRetries": 0,
                    "timeoutSeconds": "86400s",
                    "serviceAccountName": SERVICE_ACCOUNT,
                }},
            },
        }},
        "status": {
            "observedGeneration": 7,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
    }


def _identity(uri: str, generation: int, raw: bytes) -> dict[str, object]:
    return {
        "uri": uri,
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _deployment(storage: FakeStorage) -> tuple[dict[str, object], dict[str, object]]:
    secrets = {
        role: {
            "username": (
                f"projects/graph-proj/secrets/{role}-username/versions/1"
            ),
            "password": (
                f"projects/graph-proj/secrets/{role}-password/versions/1"
            ),
        }
        for role in ("bootstrap", "writer", "reader")
    }
    deployment = transport.build_deployment_manifest(
        deployment_id="corpus-research-dedicated-v1",
        provider="dedicated-managed-neo4j",
        provider_resource_id="provider-instance-123",
        endpoint_host="corpus.graph.example",
        database="corpus-research",
        server_version="2026.08.0",
        server_edition="enterprise",
        principal_secret_versions=secrets,
        created_at_utc="2026-08-21T21:00:00Z",
    )
    raw = projection.canonical_json_bytes(deployment)
    identity = _identity(
        "gs://dedicated-research/graph/governance/deployment.json", 800, raw
    )
    storage.add(identity, raw)
    return deployment, identity


def _retrieval(storage: FakeStorage) -> dict[str, Any]:
    bundle = FIXTURES._bundle(analytics=True)
    terminal = projection.parse_canonical_json_bytes(
        bundle["terminal_receipt_raw"], label="fixture terminal"
    )
    result = projection.parse_canonical_json_bytes(
        bundle["task_result_raw"], label="fixture result"
    )
    assert isinstance(terminal, dict) and isinstance(result, dict)
    storage.add(bundle["terminal_receipt_identity"], bundle["terminal_receipt_raw"])
    storage.add(terminal["batch_completion"], bundle["batch_completion_raw"])
    storage.add(terminal["result_object"], bundle["task_result_raw"])
    storage.add(result["graph_projection_object"], bundle["graph_projection_raw"])
    bodies = bundle["sidecar_bodies"]
    for sidecar in result["sidecars"]:
        key = (sidecar["role"], sidecar["strategy_id"])
        if key in bodies:
            storage.add(sidecar["object_identity"], bodies[key])
    return bundle


def _strategy_registry(storage: FakeStorage) -> dict[str, object]:
    fixture_storage, release_identity, _ = REGISTRY_FIXTURES._build_fixture()
    for (uri, generation), raw in fixture_storage.exact.items():
        identity = {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        storage.add(identity, raw)
    return release_identity


def _prepare_task0(
    storage: FakeStorage,
) -> tuple[dict[str, object], transport.ValidatedLoadBundle, dict[str, object]]:
    deployment, deployment_identity = _deployment(storage)
    retrieval = _retrieval(storage)
    strategy_registry_release = _strategy_registry(storage)
    manifest, _ = transport.prepare_load_manifest(
        storage=storage,
        deployment_manifest_identity=deployment_identity,
        retrieval_terminal_identity=retrieval["terminal_receipt_identity"],
        parametric_batch_acceptance_identity=None,
        strategy_registry_release_identity=strategy_registry_release,
        output_prefix="gs://dedicated-research/graph/load-v1/",
        code_commit="a" * 40,
        image=(
            "us-central1-docker.pkg.dev/graph-proj/repo/image@sha256:"
            + "b" * 64
        ),
        created_at_utc="2026-08-21T21:05:00Z",
    )
    manifest_raw = projection.canonical_json_bytes(manifest)
    manifest_identity = storage.publish_create_once(
        "gs://dedicated-research/graph/load-v1/governance/load-manifest.json",
        manifest_raw,
    )
    bundle = transport.validate_load_manifest(
        storage=storage, manifest_identity=manifest_identity.as_dict()
    )
    return deployment, bundle, retrieval


def _accepted_parametric(storage: FakeStorage) -> dict[str, object]:
    task_acceptance_identities: list[dict[str, object]] = []
    completion_identity: dict[str, object] | None = None
    completion_raw: bytes | None = None
    for task_index in range(54):
        parametric = FIXTURES._parametric_bundle(task_index)
        if completion_identity is None:
            completion_identity = parametric["batch_completion_identity"]
            completion_raw = parametric["batch_completion_raw"]
            storage.add(completion_identity, completion_raw)
        else:
            assert parametric["batch_completion_identity"] == completion_identity
            assert parametric["batch_completion_raw"] == completion_raw
        storage.add(parametric["task_result_identity"], parametric["task_result_raw"])
        storage.add(
            parametric["terminal_receipt_identity"],
            parametric["terminal_receipt_raw"],
        )
        storage.add(
            parametric["independent_verification_identity"],
            parametric["independent_verification_raw"],
        )
        task = projection.parse_canonical_json_bytes(
            parametric["task_result_raw"], label="fixture parametric task"
        )
        verification = projection.parse_canonical_json_bytes(
            parametric["independent_verification_raw"],
            label="fixture parametric verification",
        )
        assert isinstance(task, dict) and isinstance(verification, dict)
        body = {
            "schema_version": "corpus-parametric-task-acceptance/v1",
            "task_index": task_index,
            "task_sha256": task["task_sha256"],
            "science_terminal": parametric["terminal_receipt_identity"],
            "task_result": parametric["task_result_identity"],
            "independent_verification": parametric[
                "independent_verification_identity"
            ],
            "independent_verification_sha256": verification[
                "verification_sha256"
            ],
            "evidence_object_count": 140,
            "complete_evidence_receipt": True,
            "independent_verification_complete": True,
            "strict_verifier_terminal_success": True,
            "accepted": True,
            "partial_result": False,
            "automatic_retry_licensed": False,
            "uses_realized_outcomes": False,
            "historical_scoring_licensed": False,
            "corpus_fill_licensed": False,
            "graph_mutation_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        }
        acceptance = deepcopy(body)
        acceptance["task_acceptance_sha256"] = projection.canonical_sha256(body)
        raw = projection.canonical_json_bytes(acceptance)
        identity = _identity(
            (
                "gs://dedicated-research/parametric/"
                f"task-{task_index:04d}/acceptance.json"
            ),
            800_000 + task_index,
            raw,
        )
        storage.add(identity, raw)
        task_acceptance_identities.append(identity)
    assert completion_identity is not None
    body = {
        "schema_version": "corpus-parametric-batch-acceptance/v1",
        "batch_mode": "complete-54-task",
        "batch_completion": completion_identity,
        "task_acceptances": task_acceptance_identities,
        "task_count": 54,
        "parameter_set_count": 7,
        "matrix_cell_count": 378,
        "complete": True,
        "accepted": True,
        "partial_result": False,
        "independent_verification_complete_for_every_task": True,
        "automatic_retry_licensed": False,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "corpus_fill_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    acceptance = deepcopy(body)
    acceptance["batch_acceptance_sha256"] = projection.canonical_sha256(body)
    raw = projection.canonical_json_bytes(acceptance)
    identity = _identity(
        "gs://dedicated-research/parametric/batch-acceptance.json", 899_999, raw
    )
    storage.add(identity, raw)
    return identity


def test_deployment_binding_requires_tls_exact_instance_and_principal() -> None:
    storage = FakeStorage()
    deployment, _ = _deployment(storage)
    assert deployment["schema_version"] == transport.DEPLOYMENT_SCHEMA
    assert deployment["allowed_schema"] == {
        "node_labels": ["CorpusRetrievalEntity"],
        "relationship_types": ["CORPUS_RELATION"],
        "workstream_namespaces": [
            "corpus-parametric-research",
            "corpus-retrieval-research",
            "corpus-strategy-registry",
        ],
        "reserved_empty_namespaces": [
            "corpus-population-research",
            "corpus-realized-outcomes",
        ],
    }
    principal = deployment["principal_secret_versions"]["writer"]
    environ = {
        transport.URI_ENV: "neo4j+s://corpus.graph.example",
        transport.DATABASE_ENV: "corpus-research",
        transport.USERNAME_ENV: "writer",
        transport.PASSWORD_ENV: "secret-value",
        transport.PROVIDER_RESOURCE_ENV: "provider-instance-123",
        transport.USERNAME_SECRET_VERSION_ENV: principal["username"],
        transport.PASSWORD_SECRET_VERSION_ENV: principal["password"],
    }
    values = transport.validate_connection_binding(
        deployment, role="writer", environ=environ
    )
    assert values["database"] == "corpus-research"
    changed = dict(environ)
    changed[transport.URI_ENV] = "bolt://corpus.graph.example"
    with pytest.raises(transport.CorpusNeo4jTransportError, match="TLS"):
        transport.validate_connection_binding(
            deployment, role="writer", environ=changed
        )
    changed = dict(environ)
    changed[transport.PROVIDER_RESOURCE_ENV] = "shared-application-instance"
    with pytest.raises(transport.CorpusNeo4jTransportError, match="binding"):
        transport.validate_connection_binding(
            deployment, role="writer", environ=changed
        )
    poisoned = deepcopy(deployment)
    poisoned.pop("deployment_manifest_sha256")
    poisoned["allowed_schema"]["workstream_namespaces"].append(
        "application-production"
    )
    poisoned["deployment_manifest_sha256"] = projection.canonical_sha256(poisoned)
    with pytest.raises(
        transport.CorpusNeo4jTransportError, match="allowed schema differs"
    ):
        transport.validate_deployment_manifest(poisoned)


def test_task0_manifest_requires_all_compact_analytics_and_never_lists() -> None:
    storage = FakeStorage()
    _, bundle, retrieval = _prepare_task0(storage)
    assert bundle.manifest["worker_object_access_mode"] == (
        "generation-pinned-exact-get-no-list"
    )
    assert len(bundle.manifest["retrieval"]["mandatory_analytics"]) == 7
    assert storage.list_calls == 0

    result = projection.parse_canonical_json_bytes(
        retrieval["task_result_raw"], label="fixture result"
    )
    assert isinstance(result, dict)
    missing = next(
        row for row in result["sidecars"]
        if row["role"] == "redundancy-topk"
    )["object_identity"]
    identity = transport.object_identity(missing, label="missing analytic")
    del storage.exact[(identity.uri, identity.generation)]
    with pytest.raises(KeyError):
        transport.prepare_load_manifest(
            storage=storage,
            deployment_manifest_identity=bundle.deployment_identity.as_dict(),
            retrieval_terminal_identity=retrieval["terminal_receipt_identity"],
            parametric_batch_acceptance_identity=None,
            strategy_registry_release_identity=bundle.manifest[
                "strategy_registry"
            ]["registry_release"],
            output_prefix="gs://dedicated-research/graph/second/",
            code_commit="a" * 40,
            image="example.invalid/repo/image@sha256:" + "b" * 64,
            created_at_utc="2026-08-21T21:06:00Z",
        )


@pytest.mark.parametrize(
    "field,value,match",
    [
        ("plan_sha256", "0" * 64, "does not rebuild exactly"),
        ("registry_node_count", 1, "kind census differs"),
        ("winner_imported", True, "strategy registry manifest differs"),
        ("query_catalog_sha256", "0" * 64, "query catalog differs"),
        ("uses_realized_outcomes", True, "strategy registry manifest differs"),
    ],
)
def test_manifest_v2_rejects_tampered_registry_authority(
    field: str, value: object, match: str,
) -> None:
    storage = FakeStorage()
    _, bundle, _ = _prepare_task0(storage)
    changed = deepcopy(bundle.manifest)
    changed.pop("load_manifest_sha256")
    changed["strategy_registry"][field] = value
    changed["load_manifest_sha256"] = projection.canonical_sha256(changed)
    raw = projection.canonical_json_bytes(changed)
    identity = storage.publish_create_once(
        f"gs://dedicated-research/graph/tampered-{field}/load-manifest.json",
        raw,
    )
    with pytest.raises(transport.CorpusNeo4jTransportError, match=match):
        transport.validate_load_manifest(
            storage=storage, manifest_identity=identity.as_dict()
        )


def test_bootstrap_task0_load_recovery_and_query_smoke_are_idempotent() -> None:
    storage = FakeStorage()
    deployment, bundle, _ = _prepare_task0(storage)
    graph = FakeGraph(deployment)
    bootstrap = transport.bootstrap_schema(
        storage=storage, graph=graph, bundle=bundle
    )
    assert bootstrap["routine_writer_schema_mutation_forbidden"] is True
    first = transport.load_plan(
        storage=storage, graph=graph, bundle=bundle, task_index=None
    )
    second = transport.load_plan(
        storage=storage, graph=graph, bundle=bundle, task_index=None
    )
    assert first == second
    receipt_uri = bundle.manifest["receipt_uris"]["retrieval"]
    storage.remove_current(receipt_uri)
    recovered = transport.recover_plan_receipt(
        storage=storage, graph=graph, bundle=bundle, task_index=None
    )
    assert recovered["plan_sha256"] == bundle.retrieval_plan.plan_sha256
    smoke = transport.query_smoke(
        storage=storage,
        graph=graph,
        bundle=bundle,
        require_complete_suite=False,
    )
    assert smoke["graph_mutation"] is False
    assert storage.list_calls == 0


def test_strategy_registry_load_recovery_query_chain_is_exact_and_read_only() -> None:
    storage = FakeStorage()
    deployment, bundle, _ = _prepare_task0(storage)
    graph = FakeGraph(deployment)
    transport.bootstrap_schema(storage=storage, graph=graph, bundle=bundle)
    transport.load_plan(storage=storage, graph=graph, bundle=bundle, task_index=None)
    loaded = transport.load_strategy_registry(
        storage=storage, graph=graph, bundle=bundle
    )
    assert loaded["registry_release"] == bundle.manifest[
        "strategy_registry"
    ]["registry_release"]
    assert loaded["uses_realized_outcomes"] is False
    receipts = bundle.manifest["receipt_uris"]
    assert storage.resolve_optional(receipts["strategy_registry_projection"])

    storage.remove_current(receipts["strategy_registry_load"])
    storage.remove_current(receipts["strategy_registry_projection"])
    recovered = transport.recover_strategy_registry_receipt(
        storage=storage, graph=graph, bundle=bundle
    )
    assert recovered["plan_sha256"] == bundle.manifest[
        "strategy_registry"
    ]["plan_sha256"]
    queried = transport.query_strategy_registry(
        storage=storage, graph=graph, bundle=bundle
    )
    assert queried["read_only"] is True
    assert queried["graph_mutation"] is False
    assert queried["outcome_namespace_read"] is False
    assert queried["governed_load_manifest"] == bundle.manifest_identity.as_dict()
    assert storage.list_calls == 0

    assert transport._ROLE_BY_OPERATION["load-strategy-registry"] == "writer"
    assert (
        transport._ROLE_BY_OPERATION["recover-strategy-registry-receipt"]
        == "reader"
    )
    assert transport._ROLE_BY_OPERATION["query-strategy-registry"] == "reader"
    manifest_args = [
        "--manifest-uri", bundle.manifest_identity.uri,
        "--manifest-generation", bundle.manifest_identity.generation,
        "--manifest-sha256", bundle.manifest_identity.sha256,
        "--manifest-bytes", str(bundle.manifest_identity.bytes),
    ]
    for command in (
        "load-strategy-registry",
        "recover-strategy-registry-receipt",
        "query-strategy-registry",
    ):
        assert run_cli._parser().parse_args([command, *manifest_args]).command == command


def test_complete_54_task_load_finishes_only_after_exact_graph_census() -> None:
    storage = FakeStorage()
    deployment, deployment_identity = _deployment(storage)
    retrieval = _retrieval(storage)
    batch_acceptance = _accepted_parametric(storage)
    strategy_registry_release = _strategy_registry(storage)
    manifest, prepared = transport.prepare_load_manifest(
        storage=storage,
        deployment_manifest_identity=deployment_identity,
        retrieval_terminal_identity=retrieval["terminal_receipt_identity"],
        parametric_batch_acceptance_identity=batch_acceptance,
        strategy_registry_release_identity=strategy_registry_release,
        output_prefix="gs://dedicated-research/graph/full-v1/",
        code_commit="c" * 40,
        image="example.invalid/repo/image@sha256:" + "d" * 64,
        created_at_utc="2026-08-21T21:10:00Z",
    )
    assert len(prepared.parametric_plans) == 54
    raw = projection.canonical_json_bytes(manifest)
    manifest_identity = storage.publish_create_once(
        "gs://dedicated-research/graph/full-v1/governance/load-manifest.json",
        raw,
    )
    bundle = transport.validate_load_manifest(
        storage=storage, manifest_identity=manifest_identity.as_dict()
    )
    graph = FakeGraph(deployment)
    transport.bootstrap_schema(storage=storage, graph=graph, bundle=bundle)
    transport.load_plan(storage=storage, graph=graph, bundle=bundle, task_index=None)
    registry_load = transport.load_strategy_registry(
        storage=storage, graph=graph, bundle=bundle
    )
    assert registry_load["task_kind"] == "strategy-registry"
    registry_query = transport.query_strategy_registry(
        storage=storage, graph=graph, bundle=bundle
    )
    assert registry_query["uses_realized_outcomes"] is False
    pass_result = transport.load_parametric_suite(
        storage=storage, graph=graph, bundle=bundle
    )
    assert pass_result["task_indexes"] == list(range(54))
    terminal = transport.finish_suite(storage=storage, graph=graph, bundle=bundle)
    assert terminal["complete"] is True
    assert terminal["suite_census"]["arm_count"] == 378
    assert terminal["suite_census"]["registry_node_count"] == (
        bundle.manifest["strategy_registry"]["registry_node_count"]
    )
    assert terminal["suite_census"]["reserved_realized_outcome_node_count"] == 0
    smoke = transport.query_smoke(
        storage=storage,
        graph=graph,
        bundle=bundle,
        require_complete_suite=True,
    )
    assert smoke["require_complete_suite"] is True
    assert storage.list_calls == 0


def test_partial_or_unsafe_batch_acceptance_is_rejected() -> None:
    storage = FakeStorage()
    _, deployment_identity = _deployment(storage)
    retrieval = _retrieval(storage)
    acceptance_identity = _accepted_parametric(storage)
    strategy_registry_release = _strategy_registry(storage)
    identity = transport.object_identity(acceptance_identity, label="batch acceptance")
    raw = storage.read_exact(identity)
    acceptance = projection.parse_canonical_json_bytes(raw, label="batch acceptance")
    assert isinstance(acceptance, dict)
    acceptance.pop("batch_acceptance_sha256")
    acceptance["graph_mutation_licensed"] = True
    acceptance["batch_acceptance_sha256"] = projection.canonical_sha256(acceptance)
    changed_raw = projection.canonical_json_bytes(acceptance)
    changed_identity = _identity(
        "gs://dedicated-research/parametric/unsafe-batch-acceptance.json",
        900_001,
        changed_raw,
    )
    storage.add(changed_identity, changed_raw)
    with pytest.raises(transport.CorpusNeo4jTransportError, match="not final"):
        transport.prepare_load_manifest(
            storage=storage,
            deployment_manifest_identity=deployment_identity,
            retrieval_terminal_identity=retrieval["terminal_receipt_identity"],
            parametric_batch_acceptance_identity=changed_identity,
            strategy_registry_release_identity=strategy_registry_release,
            output_prefix="gs://dedicated-research/graph/unsafe/",
            code_commit="e" * 40,
            image="example.invalid/repo/image@sha256:" + "f" * 64,
            created_at_utc="2026-08-21T21:11:00Z",
        )


def test_build_and_frozen_job_preflights_reject_missing_authority_surface() -> None:
    image = "example.invalid/repo/image@sha256:" + "4" * 64
    image_tag = "example.invalid/repo/image:graph-fixture"
    code_sha = "3" * 40
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
                "-t", image_tag, ".",
            ]
        else:
            commands = tuple(
                tuple(image_tag if token == "${_IMAGE}" else token for token in row)
                for row in command_sets[step_id]
            )
            args = ["-ceu", "\n".join(shlex.join(row) for row in commands)]
        step: dict[str, object] = {
            "id": step_id, "name": name, "args": args,
            "status": "SUCCESS", "exitCode": 0,
        }
        if entrypoint:
            step["entrypoint"] = entrypoint
        steps.append(step)
    build = {
        "id": BUILD_ID,
        "status": "SUCCESS",
        "source": {"gitSource": {
            "revision": code_sha,
            "url": transport.EXPECTED_CODE_REPOSITORY,
        }},
        "sourceProvenance": {"resolvedGitSource": {
            "revision": code_sha,
            "url": transport.EXPECTED_CODE_REPOSITORY,
        }},
        "substitutions": {"_IMAGE": image_tag},
        "images": [image_tag],
        "artifacts": {"images": [image_tag]},
        "timeout": "10800s",
        "options": {
            "logging": "LEGACY", "machineType": "E2_HIGHCPU_8", "pool": {},
        },
        "results": {"images": [{
            "name": image_tag, "digest": image.rsplit("@", 1)[1],
        }]},
        "steps": steps,
    }
    accepted = transport.validate_build_metadata(
        build, build_id=BUILD_ID, code_sha=code_sha, image=image
    )
    assert accepted["code_sha"] == code_sha
    missing = deepcopy(build)
    missing["steps"] = missing["steps"][:-1]
    with pytest.raises(
        transport.CorpusNeo4jTransportError, match="step census/order"
    ):
        transport.validate_build_metadata(
            missing, build_id=BUILD_ID, code_sha=code_sha, image=image
        )

    storage = FakeStorage()
    deployment, _ = _deployment(storage)
    job = _parked_job(
        deployment, role="writer", image=image, code_sha=code_sha
    )
    preflight = transport.validate_reuse_preflight(
        job=job,
        executions=[_execution_row("corpus-graph-job-old01")],
        schedulers=[],
        expected_job_name=JOB_NAME,
        expected_job_uid=JOB_UID,
        all_regions_complete=True,
    )
    assert preflight["inherited_attachment_surface_empty"] is True
    parked = transport.validate_parked_job(
        job=job,
        expected_job_name=JOB_NAME,
        expected_job_uid=JOB_UID,
        role="writer",
        **_parked_contract(
            deployment, role="writer", image=image, code_sha=code_sha
        ),
    )
    assert parked["exact_parked_spec"] is True

    poisoned = deepcopy(job)
    poisoned["spec"]["template"]["spec"]["template"]["spec"][
        "containers"
    ][0]["startupProbe"] = {"tcpSocket": {"port": 7687}}
    with pytest.raises(
        transport.CorpusNeo4jTransportError, match="container attachments"
    ):
        transport.validate_reuse_preflight(
            job=poisoned,
            executions=[],
            schedulers=[],
            expected_job_name=JOB_NAME,
            expected_job_uid=JOB_UID,
            all_regions_complete=True,
        )
    with pytest.raises(
        transport.CorpusNeo4jTransportError, match="frozen Ready name/UID"
    ):
        transport.validate_reuse_preflight(
            job=job,
            executions=[],
            schedulers=[],
            expected_job_name=JOB_NAME,
            expected_job_uid="different-uid",
            all_regions_complete=True,
        )


def test_job_identity_normalizes_only_positive_json_integer_generations() -> None:
    job = {
        "metadata": {
            "name": JOB_NAME,
            "uid": JOB_UID,
            "generation": 7,
            "resourceVersion": "resource-version-7",
        },
        "status": {
            "observedGeneration": 7,
            "conditions": [{"type": "Ready", "status": "True"}],
        },
        "spec": {},
    }
    identity = transport._job_identity(
        job, expected_name=JOB_NAME, expected_uid=JOB_UID
    )
    assert identity["generation"] == "7"
    assert identity["observed_generation"] == "7"

    for parent, field in (
        ("metadata", "generation"),
        ("status", "observedGeneration"),
    ):
        for invalid in ("7", 7.0, True, 0, -1, None):
            poisoned = deepcopy(job)
            poisoned[parent][field] = invalid
            with pytest.raises(
                transport.CorpusNeo4jTransportError,
                match="must be a positive JSON integer",
            ):
                transport._job_identity(
                    poisoned,
                    expected_name=JOB_NAME,
                    expected_uid=JOB_UID,
                )

    unreconciled = deepcopy(job)
    unreconciled["status"]["observedGeneration"] = 6
    with pytest.raises(
        transport.CorpusNeo4jTransportError,
        match="externally frozen Ready name/UID",
    ):
        transport._job_identity(
            unreconciled,
            expected_name=JOB_NAME,
            expected_uid=JOB_UID,
        )


def test_create_once_launch_binding_and_terminal_recovery_prevent_relaunch() -> None:
    storage = FakeStorage()
    deployment, bundle, _ = _prepare_task0(storage)
    image = str(bundle.manifest["release"]["image"])
    code_sha = str(bundle.manifest["release"]["code_commit"])
    job = _parked_job(
        deployment, role="writer", image=image, code_sha=code_sha
    )
    contract = _parked_contract(
        deployment, role="writer", image=image, code_sha=code_sha
    )
    before = [_execution_row("corpus-graph-job-old01")]
    first = transport.consume_launch_intent(
        storage=storage,
        bundle=bundle,
        operation="load-task0",
        task_index=None,
        require_complete_suite=False,
        project="graph-proj",
        job=job,
        executions=before,
        schedulers=[],
        expected_job_name=JOB_NAME,
        expected_job_uid=JOB_UID,
        all_regions_complete=True,
        parked_job_contract={**contract, "role": "writer"},
        created_at_utc="2026-08-21T21:20:00Z",
    )
    assert first["launch_permitted"] is True
    second = transport.consume_launch_intent(
        storage=storage,
        bundle=bundle,
        operation="load-task0",
        task_index=None,
        require_complete_suite=False,
        project="graph-proj",
        job=job,
        executions=before,
        schedulers=[],
        expected_job_name=JOB_NAME,
        expected_job_uid=JOB_UID,
        all_regions_complete=True,
        parked_job_contract={**contract, "role": "writer"},
        created_at_utc="2026-08-21T21:21:00Z",
    )
    assert second["launch_permitted"] is False

    after = [*before, _execution_row("corpus-graph-job-new01", state="Unknown")]
    binding = transport.bind_launch_execution(
        storage=storage,
        bundle=bundle,
        operation="load-task0",
        task_index=None,
        require_complete_suite=False,
        job=job,
        executions=after,
        schedulers=[],
        expected_job_name=JOB_NAME,
        expected_job_uid=JOB_UID,
        all_regions_complete=True,
        created_at_utc="2026-08-21T21:22:00Z",
    )
    assert binding["sole_new_execution"] is True
    with pytest.raises(
        transport.CorpusNeo4jTransportError, match="exactly one attributable"
    ):
        different_storage = FakeStorage()
        different_storage.exact = dict(storage.exact)
        different_storage.current = {
            key: value for key, value in storage.current.items()
            if not key.endswith("execution-binding.json")
        }
        transport.bind_launch_execution(
            storage=different_storage,
            bundle=bundle,
            operation="load-task0",
            task_index=None,
            require_complete_suite=False,
            job=job,
            executions=[
                *before,
                _execution_row("corpus-graph-job-new01", state="Unknown"),
                _execution_row("corpus-graph-job-new02", state="Unknown"),
            ],
            schedulers=[],
            expected_job_name=JOB_NAME,
            expected_job_uid=JOB_UID,
            all_regions_complete=True,
            created_at_utc="2026-08-21T21:22:00Z",
        )

    graph = FakeGraph(deployment)
    transport.bootstrap_schema(storage=storage, graph=graph, bundle=bundle)
    transport.load_plan(storage=storage, graph=graph, bundle=bundle, task_index=None)
    terminal_execution = _execution_row("corpus-graph-job-new01")
    terminal = transport.finish_launch_execution(
        storage=storage,
        bundle=bundle,
        operation="load-task0",
        task_index=None,
        require_complete_suite=False,
        execution=terminal_execution,
        created_at_utc="2026-08-21T21:23:00Z",
    )
    assert terminal["strict_terminal_success"] is True
    assert len(terminal["operation_receipts"]) == 1
    assert storage.list_calls == 0


def test_parked_cli_constructs_no_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("parked mode constructed a client")

    monkeypatch.setattr(run_cli, "GoogleCloudObjectStore", forbidden)
    assert run_cli.main(["parked"]) == 0


def test_reuse_wrapper_has_no_job_creation_or_deployment_command() -> None:
    source = (ROOT / "scripts/cloud_corpus_neo4j_v1_reuse.sh").read_text()
    assert "resourceVersion" in source
    assert "--request PUT" in source
    assert "rollback_existing_job" in source
    assert not re.search(r"gcloud\s+run\s+jobs\s+(?:create|deploy)\b", source)
    assert source.count("gcloud run jobs execute") == 1
    assert "consume-launch" in source
    assert "recover-launch" in source
    assert "finish-execution" in source
    assert "load-strategy-registry" in source
    assert "recover-strategy-registry-receipt" in source
    assert "query-strategy-registry" in source
    assert "capture_all_region_schedulers" in source
