"""Bounded task-0 worker and write-disabled verifier for source-v3.

The worker is an explicit, default-off launch gate.  It resolves every input
from the future tracked capture-plan-v3 lock, replays the complete candidate
and source-authority predecessors, executes the production component reducer
for source-task ordinal zero, and invokes the production leaf source
operator.  Its seven possible output URIs are enumerated before a write-
capable transport is constructed.  The task-0 result is the final create-once
request.

The verifier is a separate, default-off, read-only invocation.  It accepts
only the generation-pinned task-0 result identity, independently reopens the
same tracked plan and every task-0 object, and emits a verifier receipt on
stdout.  It receives no publication callback and has an empty write
inventory.  Ambient service-account capability is reported as not evaluated,
not falsely claimed absent.

Neither path reads outcomes or grants source-release, scoring, selection,
promotion, graph, deployment, or production-policy authority.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from hashlib import sha256
import json
import os
import re
from typing import Final

from nfl_dfs.research import (
    corpus_r6_matchup_batch_candidate_authority_v1 as batch_mechanics,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_producer_v1 as producer_v1,
)
from nfl_dfs.research import (
    corpus_r6_matchup_component_publication_outer_candidate_authority_v3
    as component_v3,
)
from nfl_dfs.research import corpus_r6_matchup_source_operator_v2 as operator_v2
from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as release_v1
from nfl_dfs.research import (
    corpus_r6_matchup_source_batch_outer_candidate_authority_v3 as batch_v3,
)
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


SOURCE_TASK_ORDINAL: Final = 0
TASK0_COMPONENT_RELEASE_SCHEMA: Final = (
    "corpus-r6-matchup-source-task0-component-release/v3"
)
TASK0_WORKER_RESULT_SCHEMA: Final = (
    "corpus-r6-matchup-source-task0-worker-result/v3"
)
TASK0_VERIFIER_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-source-task0-verifier-receipt/v3"
)
TASK0_PROVIDER_EXECUTION_SPEC_SCHEMA: Final = (
    "corpus-r6-matchup-source-task0-provider-execution-spec/v3"
)
TASK0_PROVIDER_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-source-task0-provider-receipt/v3"
)
PROVIDER_PUBLICATION_STDOUT_SCHEMA: Final = (
    "corpus-r6-matchup-source-provider-publication-stdout/v3"
)
TASK0_FULL_AUTHORIZATION_SCHEMA: Final = (
    "corpus-r6-matchup-source-task0-full-authorization/v3"
)
INDEPENDENT_REOPEN_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-source-independent-reopen-receipt/v3"
)
OUTPUT_INVENTORY_SCHEMA: Final = (
    "corpus-r6-matchup-source-task0-output-inventory/v3"
)
TASK0_NAMESPACE: Final = "research/corpus-r6-matchup-source-task0-v3"
TASK0_RESULT_FILENAME: Final = "task0-worker-result.json"
TASK0_COMPONENT_ROOT_FILENAME: Final = "task0-component-release.json"
WORKER_ENABLE_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER"
WORKER_ENABLE_VALUE: Final = "I_UNDERSTAND_SOURCE_V3_TASK0_WORKER"
VERIFIER_ENABLE_ENV: Final = "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFY"
VERIFIER_ENABLE_VALUE: Final = "I_UNDERSTAND_SOURCE_V3_TASK0_VERIFY"
EXECUTION_NAME_ENV: Final = "CLOUD_RUN_EXECUTION"
BOUND_WORKER_EXECUTION_ENV: Final = (
    "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_WORKER_EXECUTION"
)
BOUND_VERIFIER_EXECUTION_ENV: Final = (
    "CORPUS_R6_MATCHUP_SOURCE_V3_TASK0_VERIFIER_EXECUTION"
)
BOUND_PUBLISHER_EXECUTION_ENV: Final = (
    "CORPUS_R6_MATCHUP_SOURCE_V3_PUBLISHER_EXECUTION"
)
TASK0_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_matchup_source_task0_v3.py"
)
TASK0_CLI_PATH: Final = "scripts/run_corpus_r6_matchup_source_task0_v3.py"

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,80}$")
_EXECUTION = re.compile(r"^[a-z][a-z0-9-]{1,56}-[a-z0-9]{5}$")
_HEX_40 = re.compile(r"^[0-9a-f]{40}$")
_HEX_64 = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[1-5][0-9a-f]{3}-"
    r"[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_RFC3339_UTC = re.compile(
    r"^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:"
    r"[0-9]{2}(?:\.[0-9]+)?Z$"
)
PROVIDER_PROJECT: Final = "nfl-predictions-503414"
PROVIDER_REGION: Final = "us-central1"
PROVIDER_JOB: Final = "atlas-cbc-32g-full-2023-w8-v1"
PROVIDER_JOB_UID: Final = "1f4bcf0a-2300-4afa-9fc1-9981844c8275"
PROVIDER_SERVICE_ACCOUNT: Final = (
    "817589974517-compute@developer.gserviceaccount.com"
)
PROVIDER_CONTROLLER_PATH: Final = (
    "/app/scripts/cloud_corpus_r6_matchup_source_task0_v3.sh"
)


class CorpusR6MatchupSourceTask0V3Error(ValueError):
    """The bounded source-v3 task-0 gate differs from its frozen law."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupSourceTask0V3Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSourceTask0V3Error(str(exc)) from exc


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _read_budget_summary(value: object, *, label: str) -> dict[str, object]:
    receipt = _mapping(value, label=label)
    required = (
        "schema_version",
        "ledger_kind",
        "max_object_bytes",
        "max_invocation_read_bytes",
        "max_read_operations",
        "read_bytes_reserved",
        "read_operations_reserved",
        "read_charge_manifest_sha256",
        "all_payload_reads_charged_before_access",
        "failed_reads_remain_charged",
        "per_invocation_only",
        "cross_process_durable_ledger",
        "exact_read_budget_sha256",
    )
    if any(field not in receipt for field in required):
        _fail(f"{label} summary fields differ")
    return {field: receipt[field] for field in required}


def _validate_read_budget_summary(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    normalized = _read_budget_summary(item, label=label)
    if item != normalized or "read_charges" in item:
        _fail(f"{label} must be the bounded charge-manifest summary")
    return normalized


def _run_id(value: object) -> str:
    if type(value) is not str or _RUN_ID.fullmatch(value) is None:
        _fail("task0 run ID differs")
    return value


def _execution_name(value: object, *, label: str) -> str:
    if type(value) is not str or _EXECUTION.fullmatch(value) is None:
        _fail(f"{label} differs")
    return value


def _hex_digest(value: object, *, label: str) -> str:
    if type(value) is not str or _HEX_64.fullmatch(value) is None:
        _fail(f"{label} differs")
    return value


def _environment_execution_name() -> str:
    return _execution_name(
        os.environ.get(EXECUTION_NAME_ENV), label="Cloud Run execution name"
    )


def output_prefix_for_run_v3(run_id: str) -> str:
    retained = _run_id(run_id)
    return (
        f"gs://{batch_v3.OUTPUT_BUCKET}/{TASK0_NAMESPACE}/{retained}/"
    )


def _task_prefix(*, run_id: str, slate_id: str) -> str:
    return (
        f"{output_prefix_for_run_v3(run_id)}source-task-00-{slate_id}/"
    )


def _output_inventory(
    *, run_id: str, slate: Mapping[str, object]
) -> dict[str, object]:
    slate_id = str(slate.get("slate_id"))
    prefix = _task_prefix(run_id=run_id, slate_id=slate_id)
    producer_prefix = f"{prefix}producer/"
    component_uris: set[str] = {
        f"{producer_prefix}slices/00-00-schedule-games.json",
        f"{producer_prefix}candidate-support-rows.json",
        f"{producer_prefix}component-input-bundle.json",
        f"{producer_prefix}component-producer-receipt.json",
        f"{producer_prefix}{TASK0_COMPONENT_ROOT_FILENAME}",
    }
    for role_value in source.frozen_role_registry_v2()["roles"]:
        role = _mapping(role_value, label="frozen task0 role")
        for period_ordinal, requirement_value in enumerate(
            _sequence(
                role["period_requirements"],
                label="frozen task0 role requirements",
            )
        ):
            requirement = _mapping(
                requirement_value, label="frozen task0 role requirement"
            )
            component_uris.add(
                f"{producer_prefix}slices/{int(role['ordinal']):02d}-"
                f"{period_ordinal:02d}-{requirement['slice_kind']}.json"
            )
    uris = sorted([
        *sorted(component_uris),
        f"{prefix}matchup-source-export.json",
        f"{prefix}matchup-capture-receipt.json",
        f"{prefix}matchup-operator-result.json",
        f"{output_prefix_for_run_v3(run_id)}{TASK0_RESULT_FILENAME}",
    ])
    body: dict[str, object] = {
        "schema_version": OUTPUT_INVENTORY_SCHEMA,
        "run_id": _run_id(run_id),
        "source_task_ordinal": SOURCE_TASK_ORDINAL,
        "slate": dict(slate),
        "uris": uris,
        "uri_count": len(uris),
        "result_root_uri": f"{output_prefix_for_run_v3(run_id)}{TASK0_RESULT_FILENAME}",
        "result_root_is_last": True,
    }
    body["output_uri_inventory_sha256"] = batch_v3.canonical_sha256(body)
    return body


def _validate_output_inventory(value: object) -> dict[str, object]:
    item = _mapping(value, label="task0 output inventory")
    retained = item.get("output_uri_inventory_sha256")
    body = dict(item)
    body.pop("output_uri_inventory_sha256", None)
    expected = _output_inventory(
        run_id=str(item.get("run_id")),
        slate=_mapping(item.get("slate"), label="task0 inventory slate"),
    )
    if (
        retained != batch_v3.canonical_sha256(body)
        or batch_v3.canonical_json_bytes(expected)
        != batch_v3.canonical_json_bytes(item)
        or len(set(_sequence(item.get("uris"), label="task0 output URIs")))
        != item.get("uri_count")
    ):
        _fail("task0 output inventory differs")
    return expected


def _component_root(
    *,
    run_id: str,
    execution_name: str,
    capture_plan_binding: Mapping[str, object],
    candidate_authority_root_identity: Mapping[str, object],
    component: Mapping[str, object],
    output_inventory: Mapping[str, object],
    component_object_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    row = _mapping(component, label="one-task component result")
    normalized_component_identities = _normalize_component_object_identities(
        component_object_identities,
        run_id=run_id,
        slate=_mapping(row.get("slate"), label="one-task component slate"),
    )
    body: dict[str, object] = {
        "schema_version": TASK0_COMPONENT_RELEASE_SCHEMA,
        "run_id": _run_id(run_id),
        "worker_execution_name": _execution_name(
            execution_name, label="worker execution name"
        ),
        "source_task_ordinal": SOURCE_TASK_ORDINAL,
        "task_id": row["task_id"],
        "slate": row["slate"],
        "capture_plan_v3_binding": dict(capture_plan_binding),
        "candidate_authority_v2_root_identity": _identity(
            candidate_authority_root_identity,
            label="candidate-authority v2 root",
        ),
        "fixed_g0_replay_receipt_identity": row[
            "fixed_g0_replay_receipt_identity"
        ],
        "catalog_release_identity": row["catalog_release_identity"],
        "catalog_identity": row["catalog_identity"],
        "accepted_candidate_release_identity": row[
            "accepted_candidate_release_identity"
        ],
        "upstream_source_release_identity": row[
            "upstream_source_release_identity"
        ],
        "producer_code_identity": row["producer_code_identity"],
        "input_bundle_identity": row["input_bundle_identity"],
        "producer_receipt_identity": row["producer_receipt_identity"],
        "component_object_identities": normalized_component_identities,
        "component_object_identity_count": len(normalized_component_identities),
        "component_object_identity_manifest_sha256": batch_v3.canonical_sha256(
            normalized_component_identities
        ),
        "one_task_result_sha256": row["one_task_result_sha256"],
        "output_uri_inventory_sha256": output_inventory[
            "output_uri_inventory_sha256"
        ],
        "component_task_count": 1,
        "complete": True,
        "full_producer_release_authority": False,
        **_policy(),
    }
    body["task0_component_release_sha256"] = batch_v3.canonical_sha256(body)
    return body


def _normalize_component_object_identities(
    value: object,
    *,
    run_id: str,
    slate: Mapping[str, object],
) -> list[dict[str, object]]:
    identities = [
        _identity(item, label=f"component object identity[{ordinal}]")
        for ordinal, item in enumerate(
            _sequence(value, label="component object identities")
        )
    ]
    identities.sort(key=lambda item: str(item["uri"]))
    actual_uris = [str(item["uri"]) for item in identities]
    inventory = _output_inventory(run_id=_run_id(run_id), slate=slate)
    expected_uris = sorted(
        uri
        for uri in inventory["uris"]
        if "/producer/" in str(uri)
        and not str(uri).endswith(TASK0_COMPONENT_ROOT_FILENAME)
    )
    if actual_uris != expected_uris or len(actual_uris) != len(set(actual_uris)):
        _fail("task0 component object identity inventory differs")
    return identities


def _validate_component_root(value: object) -> dict[str, object]:
    item = _mapping(value, label="task0 component release")
    retained = item.get("task0_component_release_sha256")
    body = dict(item)
    body.pop("task0_component_release_sha256", None)
    run_id = _run_id(item.get("run_id"))
    slate = _mapping(item.get("slate"), label="component root slate")
    identities = _normalize_component_object_identities(
        item.get("component_object_identities"), run_id=run_id, slate=slate
    )
    if (
        item.get("schema_version") != TASK0_COMPONENT_RELEASE_SCHEMA
        or item.get("source_task_ordinal") != SOURCE_TASK_ORDINAL
        or item.get("component_task_count") != 1
        or item.get("complete") is not True
        or item.get("full_producer_release_authority") is not False
        or item.get("component_object_identity_count") != len(identities)
        or item.get("component_object_identity_manifest_sha256")
        != batch_v3.canonical_sha256(identities)
        or retained != batch_v3.canonical_sha256(body)
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
        or any(item.get(field) is not False for field in source.FALSE_AUTHORITY_FIELDS)
    ):
        _fail("task0 component release differs")
    _execution_name(item.get("worker_execution_name"), label="worker execution")
    for field in (
        "candidate_authority_v2_root_identity",
        "fixed_g0_replay_receipt_identity",
        "catalog_release_identity",
        "catalog_identity",
        "accepted_candidate_release_identity",
        "upstream_source_release_identity",
        "input_bundle_identity",
        "producer_receipt_identity",
    ):
        _identity(item.get(field), label=field)
    return item


def _worker_result(
    *,
    run_id: str,
    execution_name: str,
    closure: Mapping[str, object],
    runtime: Mapping[str, object],
    capture_plan_binding: Mapping[str, object],
    candidate_root_identity: Mapping[str, object],
    inventory: Mapping[str, object],
    component_root_identity: Mapping[str, object],
    triple: Mapping[str, object],
    write_budget_receipt: Mapping[str, object],
) -> dict[str, object]:
    row = _mapping(triple, label="task0 source triple")
    budget = _mapping(write_budget_receipt, label="task0 pre-root write budget")
    expected_uris = _sequence(
        inventory.get("uris"), label="task0 pre-root expected URIs"
    )
    result_root_uri = str(inventory["result_root_uri"])
    if (
        budget.get("expected_write_uris") != expected_uris
        or budget.get("completed_write_uris")
        != sorted(uri for uri in expected_uris if uri != result_root_uri)
        or budget.get("pending_write_uris") != [result_root_uri]
    ):
        _fail("task0 pre-root write completion partition differs")
    body: dict[str, object] = {
        "schema_version": TASK0_WORKER_RESULT_SCHEMA,
        "run_id": _run_id(run_id),
        "worker_execution_name": _execution_name(
            execution_name, label="worker execution name"
        ),
        "source_task_ordinal": SOURCE_TASK_ORDINAL,
        "task_id": row["task_id"],
        "slate": row["slate"],
        "capture_plan_v3_binding": dict(capture_plan_binding),
        "candidate_authority_v2_root_identity": _identity(
            candidate_root_identity, label="candidate authority root"
        ),
        "executed_dependency_closure_sha256": closure[
            "dependency_closure_sha256"
        ],
        "runtime_binding_sha256": runtime["runtime_binding_sha256"],
        "output_uri_inventory": dict(inventory),
        "component_task_release_identity": _identity(
            component_root_identity, label="task0 component release"
        ),
        "source_export_identity": row["source_export_identity"],
        "capture_receipt_identity": row["capture_receipt_identity"],
        "operator_result_identity": row["operator_result_identity"],
        "write_budget_receipt_before_result_root": budget,
        "component_task_count": 1,
        "source_triple_count": 1,
        "all_component_objects_exact_reopened": True,
        "all_source_objects_exact_reopened": True,
        "task0_result_root_is_final_create_once_request": True,
        "full_source_publication_authority": False,
        "complete": True,
        **_policy(),
    }
    body["task0_worker_result_sha256"] = batch_v3.canonical_sha256(body)
    return body


def validate_task0_worker_result_structure_v3(value: object) -> dict[str, object]:
    item = _mapping(value, label="task0 worker result")
    retained = item.get("task0_worker_result_sha256")
    body = dict(item)
    body.pop("task0_worker_result_sha256", None)
    inventory = _validate_output_inventory(item.get("output_uri_inventory"))
    budget = _mapping(
        item.get("write_budget_receipt_before_result_root"),
        label="task0 pre-root write budget",
    )
    expected_uris = inventory["uris"]
    result_root_uri = inventory["result_root_uri"]
    if (
        item.get("schema_version") != TASK0_WORKER_RESULT_SCHEMA
        or item.get("source_task_ordinal") != SOURCE_TASK_ORDINAL
        or item.get("component_task_count") != 1
        or item.get("source_triple_count") != 1
        or item.get("all_component_objects_exact_reopened") is not True
        or item.get("all_source_objects_exact_reopened") is not True
        or item.get("task0_result_root_is_final_create_once_request") is not True
        or item.get("full_source_publication_authority") is not False
        or item.get("complete") is not True
        or retained != batch_v3.canonical_sha256(body)
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
        or any(item.get(field) is not False for field in source.FALSE_AUTHORITY_FIELDS)
        or budget.get("expected_write_uris") != expected_uris
        or budget.get("completed_write_uris")
        != sorted(uri for uri in expected_uris if uri != result_root_uri)
        or budget.get("pending_write_uris") != [result_root_uri]
    ):
        _fail("task0 worker result differs")
    run_id = _run_id(item.get("run_id"))
    _execution_name(item.get("worker_execution_name"), label="worker execution")
    for field in (
        "candidate_authority_v2_root_identity",
        "component_task_release_identity",
        "source_export_identity",
        "capture_receipt_identity",
        "operator_result_identity",
    ):
        _identity(item.get(field), label=field)
    if inventory["run_id"] != run_id:
        _fail("task0 worker result inventory run differs")
    slate_id = str(_mapping(item.get("slate"), label="worker slate").get("slate_id"))
    task_prefix = _task_prefix(run_id=run_id, slate_id=slate_id)
    expected_identity_uris = {
        "component_task_release_identity": (
            f"{task_prefix}producer/{TASK0_COMPONENT_ROOT_FILENAME}"
        ),
        "source_export_identity": f"{task_prefix}matchup-source-export.json",
        "capture_receipt_identity": f"{task_prefix}matchup-capture-receipt.json",
        "operator_result_identity": f"{task_prefix}matchup-operator-result.json",
    }
    if any(
        _identity(item[field], label=field)["uri"] != uri
        for field, uri in expected_identity_uris.items()
    ):
        _fail("task0 worker result object URI binding differs")
    return item


def publish_task0_worker_v3(*, run_id: str) -> dict[str, object]:
    """Run and publish the real ordinal-zero source gate, result root last."""

    retained_run_id = _run_id(run_id)
    if os.environ.get(WORKER_ENABLE_ENV) != WORKER_ENABLE_VALUE:
        _fail(f"task0 worker requires {WORKER_ENABLE_ENV}={WORKER_ENABLE_VALUE}")
    execution_name = _environment_execution_name()
    closure, runtime, plan, binding, _ = batch_v3._validate_local_context_v3()
    plan_tasks = _sequence(plan.get("source_task_bindings"), label="plan tasks")
    first_task = _mapping(plan_tasks[SOURCE_TASK_ORDINAL], label="plan task0")
    inventory = _output_inventory(
        run_id=retained_run_id,
        slate=_mapping(first_task.get("slate"), label="plan task0 slate"),
    )
    try:
        transport = batch_mechanics._trusted_gcs_transport_v1(
            expected_write_uris=inventory["uris"]
        )
        cache = batch_mechanics.ExactReadCacheV1(transport.read_exact)
        prerequisites = batch_v3._trusted_remote_prerequisites_v3(
            plan=plan, read_exact=cache.read
        )
        batch_v3._deep_validate_capture_plan_v3(
            plan=plan, prerequisites=prerequisites, read_exact=cache.read
        )
        reopened, candidate_binding = component_v3._open_candidate(
            root_identity=plan["fixed_g0_candidate_authority_root_identity"],
            repository_root=batch_v3.REPOSITORY_ROOT,
            read_exact=cache.read,
            git_head=batch_mechanics._trusted_git_head_v1,
            git_blob=batch_mechanics._trusted_git_blob_v1,
            git_status=batch_mechanics._trusted_git_status_v1,
        )
        component_v3._require_plan_candidate_equality(
            plan=plan, binding=candidate_binding
        )
        inner = component_v3._derive_inner_inputs(
            binding=candidate_binding, reopened=reopened, read_exact=cache.read
        )
        refreshed_closure = batch_v3._trusted_dependency_closure_v3()
        refreshed_runtime = batch_v3._build_runtime_binding_v3(refreshed_closure)
        if refreshed_closure != closure or refreshed_runtime != runtime:
            _fail("task0 clean runtime changed before first publication")
        seen_raw: dict[str, bytes] = {}
        seen_identity: dict[str, dict[str, object]] = {}

        def materialize_once(uri: str, raw: bytes) -> Mapping[str, object]:
            prior = seen_raw.get(uri)
            if prior is not None:
                if prior != raw:
                    _fail("task0 component requested one URI with different bytes")
                return seen_identity[uri]
            identity = _identity(
                transport.publish_create_once(uri, raw),
                label="task0 component materialization",
            )
            seen_raw[uri] = raw
            seen_identity[uri] = identity
            return identity

        component = producer_v1.produce_one_component_task_v1(
            source_task_ordinal=SOURCE_TASK_ORDINAL,
            producer_id=str(plan["producer_id"]),
            producer_namespace=output_prefix_for_run_v3(retained_run_id),
            fixed_g0_replay_receipt=inner["receipt"],
            fixed_g0_replay_receipt_identity=inner["receipt_identity"],
            catalog_release=inner["catalog_release"],
            catalog_release_identity=inner["catalog_release_identity"],
            structural_catalogs=inner["structural_catalogs"],
            accepted_candidate_release=inner["candidate_release"],
            accepted_candidate_release_identity=inner[
                "candidate_release_identity"
            ],
            upstream_source_release=prerequisites["upstream_source_release"],
            upstream_source_release_identity=prerequisites[
                "upstream_source_release_identity"
            ],
            upstream_pack_row_objects=prerequisites["upstream_pack_row_objects"],
            producer_code_identity=plan["component_producer_code_identity"],
            body_materializer=materialize_once,
            read_exact=cache.read,
        )
        component_root = _component_root(
            run_id=retained_run_id,
            execution_name=execution_name,
            capture_plan_binding=binding,
            candidate_authority_root_identity=plan[
                "fixed_g0_candidate_authority_root_identity"
            ],
            component=component,
            output_inventory=inventory,
            component_object_identities=list(seen_identity.values()),
        )
        task_prefix = _task_prefix(
            run_id=retained_run_id,
            slate_id=str(component["slate"]["slate_id"]),
        )
        component_root, component_root_identity = batch_v3._publish_json(
            component_root,
            uri=f"{task_prefix}producer/{TASK0_COMPONENT_ROOT_FILENAME}",
            publish_create_once=transport.publish_create_once,
            read_exact=cache.read,
            label="task0 component release",
        )
        triple = operator_v2.publish_matchup_source_triple_v2(
            source_task_ordinal=SOURCE_TASK_ORDINAL,
            output_prefix=task_prefix,
            capture_plan_binding=binding,
            operator_code_identity=batch_v3._operator_code_identity(closure),
            producer_release_identity=component_root_identity,
            producer_receipt=component["producer_receipt"],
            producer_receipt_identity=component["producer_receipt_identity"],
            input_bundle=component["input_bundle"],
            input_bundle_identity=component["input_bundle_identity"],
            structural_catalog=inner["structural_catalogs"][SOURCE_TASK_ORDINAL],
            catalog_identity=component["catalog_identity"],
            candidate_artifact_identity=_mapping(
                inner["candidate_release"]["entries"][SOURCE_TASK_ORDINAL],
                label="candidate entry0",
            )["candidate_artifact_identity"],
            publish_create_once=transport.publish_create_once,
            read_exact=cache.read,
        )
        if batch_v3._trusted_dependency_closure_v3() != closure:
            _fail("task0 clean closure changed before result root")
        root = _worker_result(
            run_id=retained_run_id,
            execution_name=execution_name,
            closure=closure,
            runtime=runtime,
            capture_plan_binding=binding,
            candidate_root_identity=plan[
                "fixed_g0_candidate_authority_root_identity"
            ],
            inventory=inventory,
            component_root_identity=component_root_identity,
            triple=triple,
            write_budget_receipt=transport.write_budget_receipt(),
        )
        root, root_identity = batch_v3._publish_json(
            root,
            uri=inventory["result_root_uri"],
            publish_create_once=transport.publish_create_once,
            read_exact=cache.read,
            label="task0 worker result root",
        )
        transport.require_completed_exactly_v1(
            completed_uris=inventory["uris"], pending_uris=()
        )
        final_write_budget_receipt = transport.write_budget_receipt()
    except CorpusR6MatchupSourceTask0V3Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupSourceTask0V3Error(
            f"task0 worker failed closed: {exc}"
        ) from exc
    return {
        "schema_version": "corpus-r6-matchup-source-task0-worker-publication/v3",
        "run_id": retained_run_id,
        "worker_result": root,
        "worker_result_identity": root_identity,
        "worker_execution_name": execution_name,
        "final_write_budget_receipt": final_write_budget_receipt,
        "task0_result_root_was_final_create_once_request": True,
        "complete": True,
        **_policy(),
    }


def _exact_object(
    identity_value: object,
    *,
    cache: batch_mechanics.ExactReadCacheV1,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        return batch_v3._parse_exact_json(
            _identity(identity_value, label=f"{label} identity"),
            read_exact=cache.read,
            label=label,
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceTask0V3Error(
            f"task0 {label} exact reopen failed: {exc}"
        ) from exc


def verify_task0_worker_v3(
    *, worker_result_identity: Mapping[str, object]
) -> dict[str, object]:
    """Independently deep-reopen one real ordinal with no write callback."""

    if os.environ.get(VERIFIER_ENABLE_ENV) != VERIFIER_ENABLE_VALUE:
        _fail(f"task0 verifier requires {VERIFIER_ENABLE_ENV}={VERIFIER_ENABLE_VALUE}")
    verifier_execution = _environment_execution_name()
    closure, runtime, plan, binding, _ = batch_v3._validate_local_context_v3()
    try:
        transport = batch_mechanics._trusted_gcs_transport_v1(
            expected_write_uris=()
        )
        cache = batch_mechanics.ExactReadCacheV1(transport.read_exact)
        root, root_identity = _exact_object(
            worker_result_identity, cache=cache, label="worker result root"
        )
        root = validate_task0_worker_result_structure_v3(root)
        worker_execution = _execution_name(
            root["worker_execution_name"], label="worker execution"
        )
        if verifier_execution == worker_execution:
            _fail("task0 verifier must run in a distinct execution")
        if (
            root_identity["uri"]
            != root["output_uri_inventory"]["result_root_uri"]
            or
            root["capture_plan_v3_binding"] != binding
            or root["candidate_authority_v2_root_identity"]
            != plan["fixed_g0_candidate_authority_root_identity"]
            or root["executed_dependency_closure_sha256"]
            != closure["dependency_closure_sha256"]
            or root["runtime_binding_sha256"] != runtime["runtime_binding_sha256"]
        ):
            _fail("task0 worker root differs from verifier runtime/plan")
        prerequisites = batch_v3._trusted_remote_prerequisites_v3(
            plan=plan, read_exact=cache.read
        )
        batch_v3._deep_validate_capture_plan_v3(
            plan=plan, prerequisites=prerequisites, read_exact=cache.read
        )
        reopened, candidate_binding = component_v3._open_candidate(
            root_identity=plan["fixed_g0_candidate_authority_root_identity"],
            repository_root=batch_v3.REPOSITORY_ROOT,
            read_exact=cache.read,
            git_head=batch_mechanics._trusted_git_head_v1,
            git_blob=batch_mechanics._trusted_git_blob_v1,
            git_status=batch_mechanics._trusted_git_status_v1,
        )
        component_v3._require_plan_candidate_equality(
            plan=plan, binding=candidate_binding
        )
        inner = component_v3._derive_inner_inputs(
            binding=candidate_binding, reopened=reopened, read_exact=cache.read
        )
        component_root, component_root_identity = _exact_object(
            root["component_task_release_identity"],
            cache=cache,
            label="component task release",
        )
        component_root = _validate_component_root(component_root)
        if (
            component_root["run_id"] != root["run_id"]
            or component_root["worker_execution_name"] != worker_execution
            or component_root["task_id"] != root["task_id"]
            or component_root["slate"] != root["slate"]
            or component_root["capture_plan_v3_binding"] != binding
            or component_root["candidate_authority_v2_root_identity"]
            != root["candidate_authority_v2_root_identity"]
            or component_root["output_uri_inventory_sha256"]
            != root["output_uri_inventory"]["output_uri_inventory_sha256"]
        ):
            _fail("task0 component root differs from worker root")
        component_leaf_identities = _normalize_component_object_identities(
            component_root["component_object_identities"],
            run_id=str(root["run_id"]),
            slate=_mapping(root["slate"], label="worker root slate"),
        )
        # Every URI declared by the worker before transport construction is
        # reopened generation-exact in the independent verifier.  Semantic
        # validators below additionally replay the bundle and receipt; this
        # loop closes the remaining slice/support-leaf existence seam.
        for leaf_identity in component_leaf_identities:
            reopened_raw = cache.read(leaf_identity)
            if type(reopened_raw) is not bytes or not reopened_raw:
                _fail("task0 component leaf exact reopen differs")
        bundle, bundle_identity = _exact_object(
            component_root["input_bundle_identity"],
            cache=cache,
            label="component input bundle",
        )
        receipt, receipt_identity = _exact_object(
            component_root["producer_receipt_identity"],
            cache=cache,
            label="component producer receipt",
        )
        catalog = inner["structural_catalogs"][SOURCE_TASK_ORDINAL]
        producer_v1.validate_component_input_bundle_v1(
            bundle, expected_catalog=catalog, expected_identity=bundle_identity
        )
        source.validate_component_producer_receipt_v1(
            receipt,
            structural_catalog=catalog,
            catalog_release=inner["catalog_release"],
            accepted_candidate_release=inner["candidate_release"],
            upstream_source_release=prerequisites["upstream_source_release"],
            upstream_pack_row_objects=prerequisites["upstream_pack_row_objects"],
            input_bundle=bundle,
            expected_catalog_release_identity=inner["catalog_release_identity"],
            expected_catalog_replay_receipt_identity=inner["receipt_identity"],
            expected_candidate_release_identity=inner[
                "candidate_release_identity"
            ],
            expected_upstream_source_release_identity=prerequisites[
                "upstream_source_release_identity"
            ],
            expected_producer_code_identity=plan[
                "component_producer_code_identity"
            ],
        )
        export, export_identity = _exact_object(
            root["source_export_identity"], cache=cache, label="source export"
        )
        capture, capture_identity = _exact_object(
            root["capture_receipt_identity"],
            cache=cache,
            label="capture receipt",
        )
        result, result_identity = _exact_object(
            root["operator_result_identity"],
            cache=cache,
            label="operator result",
        )
        release_v1.validate_matchup_source_export_v2(
            export,
            producer_receipt=receipt,
            producer_receipt_identity=receipt_identity,
            input_bundle=bundle,
            input_bundle_identity=bundle_identity,
            structural_catalog=catalog,
            catalog_identity=component_root["catalog_identity"],
        )
        release_v1.validate_matchup_capture_receipt_v2(
            capture,
            source_export=export,
            source_export_identity=export_identity,
            producer_receipt=receipt,
            producer_receipt_identity=receipt_identity,
            input_bundle=bundle,
            input_bundle_identity=bundle_identity,
            structural_catalog=catalog,
            catalog_identity=component_root["catalog_identity"],
        )
        release_v1.validate_matchup_operator_result_v2(
            result,
            source_export=export,
            source_export_identity=export_identity,
            capture_receipt=capture,
            capture_receipt_identity=capture_identity,
        )
        if (
            component_root_identity != root["component_task_release_identity"]
            or bundle_identity != component_root["input_bundle_identity"]
            or receipt_identity != component_root["producer_receipt_identity"]
            or export_identity != root["source_export_identity"]
            or capture_identity != root["capture_receipt_identity"]
            or result_identity != root["operator_result_identity"]
            or export["producer_release_identity"] != component_root_identity
            or result["producer_release_identity"] != component_root_identity
        ):
            _fail("task0 source/component identity chain differs")
    except CorpusR6MatchupSourceTask0V3Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupSourceTask0V3Error(
            f"task0 verifier failed closed: {exc}"
        ) from exc
    receipt_body: dict[str, object] = {
        "schema_version": TASK0_VERIFIER_RECEIPT_SCHEMA,
        "complete": True,
        "run_id": root["run_id"],
        "source_task_ordinal": SOURCE_TASK_ORDINAL,
        "task_id": root["task_id"],
        "slate": root["slate"],
        "worker_execution_name": worker_execution,
        "verifier_execution_name": verifier_execution,
        "worker_result_identity": root_identity,
        "capture_plan_v3_binding": binding,
        "executed_dependency_closure_sha256": closure[
            "dependency_closure_sha256"
        ],
        "runtime_binding_sha256": runtime["runtime_binding_sha256"],
        "component_task_release_identity": component_root_identity,
        "operator_result_identity": result_identity,
        "candidate_v2_capture_v3_predecessors_deep_reopened": True,
        "one_real_component_ordinal_exact_reopened": True,
        "component_leaf_identity_count_exact_reopened": len(
            component_leaf_identities
        ),
        "component_leaf_identity_manifest_sha256": batch_v3.canonical_sha256(
            component_leaf_identities
        ),
        "one_real_source_ordinal_exact_reopened": True,
        "publication_callback_exposed": False,
        "write_inventory_count": 0,
        "ambient_service_account_write_capability": "not_evaluated",
        "cloud_mutation_performed": False,
        "exact_read_cache_budget_summary": _read_budget_summary(
            cache.budget_receipt(), label="task0 exact-read cache budget"
        ),
        "transport_read_budget_summary": _read_budget_summary(
            transport.read_budget_receipt(), label="task0 transport read budget"
        ),
        **_policy(),
    }
    receipt_body["task0_verifier_receipt_sha256"] = batch_v3.canonical_sha256(
        receipt_body
    )
    return receipt_body


def validate_task0_verifier_receipt_v3(value: object) -> dict[str, object]:
    item = _mapping(value, label="task0 verifier receipt")
    retained = item.get("task0_verifier_receipt_sha256")
    body = dict(item)
    body.pop("task0_verifier_receipt_sha256", None)
    _validate_read_budget_summary(
        item.get("exact_read_cache_budget_summary"),
        label="task0 verifier cache budget summary",
    )
    _validate_read_budget_summary(
        item.get("transport_read_budget_summary"),
        label="task0 verifier transport budget summary",
    )
    if (
        item.get("schema_version") != TASK0_VERIFIER_RECEIPT_SCHEMA
        or item.get("complete") is not True
        or item.get("source_task_ordinal") != SOURCE_TASK_ORDINAL
        or item.get("candidate_v2_capture_v3_predecessors_deep_reopened")
        is not True
        or item.get("one_real_component_ordinal_exact_reopened") is not True
        or item.get("one_real_source_ordinal_exact_reopened") is not True
        or type(item.get("component_leaf_identity_count_exact_reopened")) is not int
        or int(item["component_leaf_identity_count_exact_reopened"]) < 1
        or type(item.get("component_leaf_identity_manifest_sha256")) is not str
        or re.fullmatch(
            r"[0-9a-f]{64}", str(item["component_leaf_identity_manifest_sha256"])
        ) is None
        or item.get("publication_callback_exposed") is not False
        or item.get("write_inventory_count") != 0
        or item.get("ambient_service_account_write_capability") != "not_evaluated"
        or item.get("cloud_mutation_performed") is not False
        or retained != batch_v3.canonical_sha256(body)
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
        or any(item.get(field) is not False for field in source.FALSE_AUTHORITY_FIELDS)
    ):
        _fail("task0 verifier receipt differs")
    worker = _execution_name(item.get("worker_execution_name"), label="worker")
    verifier = _execution_name(
        item.get("verifier_execution_name"), label="verifier"
    )
    if worker == verifier:
        _fail("task0 verifier receipt does not prove distinct execution names")
    _run_id(item.get("run_id"))
    _identity(item.get("worker_result_identity"), label="worker result")
    _identity(item.get("component_task_release_identity"), label="component root")
    _identity(item.get("operator_result_identity"), label="operator result")
    return item


def validate_provider_execution_spec_v3(value: object) -> dict[str, object]:
    """Validate the normalized provider-owned Cloud Run execution record."""

    item = _mapping(value, label="task0 provider execution spec")
    expected_fields = {
        "schema_version", "phase", "project", "region", "job", "job_uid",
        "job_generation", "execution_name", "execution_uid",
        "completion_time", "task_count", "parallelism", "max_retries",
        "timeout_seconds", "service_account", "cpu", "memory", "command",
        "args", "image_uri", "image_digest", "code_sha",
        "image_source_commit_sha", "build_id", "mode", "outcomes_allowed",
        "request_run_id", "payload_sha256", "payload_bytes",
        "bound_worker_execution", "bound_verifier_execution",
        "bound_publisher_execution",
        "succeeded_count", "failed_count", "cancelled_count", "running_count",
    }
    if set(item) != expected_fields:
        _fail("task0 provider execution spec fields differ")
    phase = item.get("phase")
    if phase not in {"worker", "verify", "publish", "reopen"}:
        _fail("task0 provider execution phase differs")
    execution = _execution_name(item.get("execution_name"), label="provider execution")
    if (
        item.get("schema_version") != TASK0_PROVIDER_EXECUTION_SPEC_SCHEMA
        or item.get("project") != PROVIDER_PROJECT
        or item.get("region") != PROVIDER_REGION
        or item.get("job") != PROVIDER_JOB
        or item.get("job_uid") != PROVIDER_JOB_UID
        or type(item.get("job_generation")) is not str
        or re.fullmatch(r"[1-9][0-9]*", str(item["job_generation"])) is None
        or type(item.get("execution_uid")) is not str
        or _UUID.fullmatch(str(item["execution_uid"])) is None
        or type(item.get("completion_time")) is not str
        or _RFC3339_UTC.fullmatch(str(item["completion_time"])) is None
        or item.get("task_count") != 1
        or item.get("parallelism") != 1
        or item.get("max_retries") != 0
        or item.get("timeout_seconds") != "86400s"
        or item.get("service_account") != PROVIDER_SERVICE_ACCOUNT
        or item.get("cpu") != "8"
        or item.get("memory") != "32Gi"
        or item.get("command") != ["/bin/bash"]
        or item.get("args")
        != [PROVIDER_CONTROLLER_PATH, "container-run", phase]
        or item.get("mode") != phase
        or item.get("outcomes_allowed") is not False
        or item.get("succeeded_count") != 1
        or item.get("failed_count") != 0
        or item.get("cancelled_count") != 0
        or item.get("running_count") != 0
        or type(item.get("payload_bytes")) is not int
        or not 1 <= int(item["payload_bytes"]) <= 262_144
    ):
        _fail("task0 provider execution spec differs")
    image_uri = item.get("image_uri")
    image_digest = item.get("image_digest")
    code_sha = item.get("code_sha")
    build_id = item.get("build_id")
    if (
        type(image_digest) is not str
        or re.fullmatch(r"sha256:[0-9a-f]{64}", image_digest) is None
        or type(image_uri) is not str
        or image_uri
        != f"us-central1-docker.pkg.dev/{PROVIDER_PROJECT}/nfl-dfs/nfl-dfs@{image_digest}"
        or type(code_sha) is not str
        or _HEX_40.fullmatch(code_sha) is None
        or item.get("image_source_commit_sha") != code_sha
        or type(build_id) is not str
        or _UUID.fullmatch(build_id) is None
    ):
        _fail("task0 provider image/code/build binding differs")
    _run_id(item.get("request_run_id"))
    _hex_digest(item.get("payload_sha256"), label="provider payload SHA")
    worker_binding = item.get("bound_worker_execution")
    verifier_binding = item.get("bound_verifier_execution")
    publisher_binding = item.get("bound_publisher_execution")
    if phase == "worker":
        if (
            worker_binding != "DISABLED"
            or verifier_binding != "DISABLED"
            or publisher_binding != "DISABLED"
        ):
            _fail("task0 worker provider execution bindings differ")
    elif phase == "verify":
        _execution_name(worker_binding, label="provider-bound worker execution")
        if verifier_binding != "DISABLED" or publisher_binding != "DISABLED":
            _fail("task0 verify provider execution bindings differ")
    elif phase == "publish":
        worker = _execution_name(
            worker_binding, label="provider-bound worker execution"
        )
        verifier = _execution_name(
            verifier_binding, label="provider-bound verifier execution"
        )
        if (
            publisher_binding != "DISABLED"
            or worker == verifier
            or execution in {worker, verifier}
        ):
            _fail("task0 publish provider execution separation differs")
    else:
        worker = _execution_name(
            worker_binding, label="provider-bound worker execution"
        )
        verifier = _execution_name(
            verifier_binding, label="provider-bound verifier execution"
        )
        publisher = _execution_name(
            publisher_binding, label="provider-bound publisher execution"
        )
        if len({worker, verifier, publisher, execution}) != 4:
            _fail("task0 independent reopen provider separation differs")
    return item


def _provider_payload_bytes(value: Mapping[str, object]) -> bytes:
    return batch_v3.canonical_json_bytes(dict(value)) + b"\n"


def validate_provider_publication_stdout_v3(value: object) -> dict[str, object]:
    item = _mapping(value, label="source-v3 provider publication stdout")
    retained = item.get("provider_publication_stdout_sha256")
    body = dict(item)
    body.pop("provider_publication_stdout_sha256", None)
    expected = {
        "schema_version", "complete", "run_id", "batch_release_identity",
        "source_release_v3_identity", "task_count",
        "task0_full_publication_authorization_sha256",
        "task0_verifier_provider_receipt_sha256",
        "task0_verifier_provider_receipt_identity",
        "task0_worker_execution_name", "task0_verifier_execution_name",
        "terminal_batch_root_requested_last", "same_process_deep_reopen_complete",
        "independent_process_deep_reopen_complete",
        "independent_process_deep_reopen_required", "cloud_mutation_performed",
        "full_publication_receipt_sha256", "outcome_columns_read",
        "uses_realized_outcomes", *source.FALSE_AUTHORITY_FIELDS,
        "provider_publication_stdout_sha256",
    }
    if set(item) != expected:
        _fail("source-v3 provider publication stdout fields differ")
    worker = _execution_name(
        item.get("task0_worker_execution_name"), label="task0 worker"
    )
    verifier = _execution_name(
        item.get("task0_verifier_execution_name"), label="task0 verifier"
    )
    if worker == verifier:
        _fail("source-v3 provider publication executions are not distinct")
    _run_id(item.get("run_id"))
    _identity(item.get("batch_release_identity"), label="batch release")
    _identity(item.get("source_release_v3_identity"), label="source release")
    _identity(
        item.get("task0_verifier_provider_receipt_identity"),
        label="verifier provider receipt",
    )
    for field in (
        "task0_full_publication_authorization_sha256",
        "task0_verifier_provider_receipt_sha256",
        "full_publication_receipt_sha256",
    ):
        _hex_digest(item.get(field), label=field)
    if (
        item.get("schema_version") != PROVIDER_PUBLICATION_STDOUT_SCHEMA
        or item.get("complete") is not True
        or item.get("task_count") != source.TASK_COUNT
        or item.get("terminal_batch_root_requested_last") is not True
        or item.get("same_process_deep_reopen_complete") is not True
        or item.get("independent_process_deep_reopen_complete") is not False
        or item.get("independent_process_deep_reopen_required") is not True
        or item.get("cloud_mutation_performed") is not True
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
        or any(item.get(field) is not False for field in source.FALSE_AUTHORITY_FIELDS)
        or retained != batch_v3.canonical_sha256(body)
    ):
        _fail("source-v3 provider publication stdout differs")
    return item


def _provider_publication_stdout_v3(value: object) -> dict[str, object]:
    publication = _mapping(value, label="source-v3 full publication receipt")
    retained = publication.get("publication_receipt_sha256")
    body = dict(publication)
    body.pop("publication_receipt_sha256", None)
    if (
        publication.get("schema_version") != batch_v3.PUBLICATION_RECEIPT_SCHEMA
        or retained != batch_v3.canonical_sha256(body)
    ):
        _fail("source-v3 full publication receipt differs")
    projected: dict[str, object] = {
        "schema_version": PROVIDER_PUBLICATION_STDOUT_SCHEMA,
        "complete": publication.get("complete"),
        "run_id": publication.get("run_id"),
        "batch_release_identity": publication.get("batch_release_identity"),
        "source_release_v3_identity": publication.get("source_release_v3_identity"),
        "task_count": publication.get("task_count"),
        "task0_full_publication_authorization_sha256": publication.get(
            "task0_full_publication_authorization_sha256"
        ),
        "task0_verifier_provider_receipt_sha256": publication.get(
            "task0_verifier_provider_receipt_sha256"
        ),
        "task0_verifier_provider_receipt_identity": publication.get(
            "task0_verifier_provider_receipt_identity"
        ),
        "task0_worker_execution_name": publication.get(
            "task0_worker_execution_name"
        ),
        "task0_verifier_execution_name": publication.get(
            "task0_verifier_execution_name"
        ),
        "terminal_batch_root_requested_last": publication.get(
            "terminal_batch_root_requested_last"
        ),
        "same_process_deep_reopen_complete": publication.get(
            "same_process_deep_reopen_complete"
        ),
        "independent_process_deep_reopen_complete": publication.get(
            "independent_process_deep_reopen_complete"
        ),
        "independent_process_deep_reopen_required": publication.get(
            "independent_process_deep_reopen_required"
        ),
        "cloud_mutation_performed": publication.get("cloud_mutation_performed"),
        "full_publication_receipt_sha256": retained,
        **_policy(),
    }
    projected["provider_publication_stdout_sha256"] = batch_v3.canonical_sha256(
        projected
    )
    return validate_provider_publication_stdout_v3(projected)


def _build_task0_provider_receipt_v3(
    *,
    provider_execution_spec: Mapping[str, object],
    operator_output: Mapping[str, object],
    worker_provider_receipt: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Bind one exact successful provider execution to its unique stdout JSON."""

    spec = validate_provider_execution_spec_v3(provider_execution_spec)
    output = _mapping(operator_output, label="task0 provider operator output")
    phase = str(spec["phase"])
    predecessor: dict[str, object] | None = None
    if phase == "worker":
        if worker_provider_receipt is not None:
            _fail("task0 worker provider receipt cannot have a predecessor")
        if (
            output.get("schema_version")
            != "corpus-r6-matchup-source-task0-worker-publication/v3"
            or output.get("complete") is not True
            or output.get("run_id") != spec["request_run_id"]
            or output.get("worker_execution_name") != spec["execution_name"]
            or output.get("task0_result_root_was_final_create_once_request")
            is not True
            or spec["payload_sha256"] != sha256(b"{}").hexdigest()
            or spec["payload_bytes"] != 2
        ):
            _fail("task0 worker provider stdout differs")
        worker_root = validate_task0_worker_result_structure_v3(
            output.get("worker_result")
        )
        if (
            worker_root["worker_execution_name"] != spec["execution_name"]
            or _identity(
                output.get("worker_result_identity"), label="worker stdout root"
            )["uri"]
            != worker_root["output_uri_inventory"]["result_root_uri"]
        ):
            _fail("task0 worker provider stdout identity differs")
    elif phase == "verify":
        if worker_provider_receipt is None:
            _fail("task0 verify provider receipt requires exact worker receipt")
        predecessor = validate_task0_provider_receipt_v3(worker_provider_receipt)
        predecessor_spec = predecessor["provider_execution_spec"]
        predecessor_output = predecessor["operator_output"]
        receipt = validate_task0_verifier_receipt_v3(output)
        predecessor_raw = _provider_payload_bytes(predecessor)
        if (
            predecessor_spec["phase"] != "worker"
            or receipt["run_id"] != spec["request_run_id"]
            or predecessor_output["run_id"] != receipt["run_id"]
            or receipt["worker_execution_name"]
            != predecessor_spec["execution_name"]
            or receipt["verifier_execution_name"] != spec["execution_name"]
            or spec["bound_worker_execution"]
            != predecessor_spec["execution_name"]
            or receipt["worker_result_identity"]
            != predecessor_output["worker_result_identity"]
            or spec["payload_sha256"]
            != sha256(predecessor_raw).hexdigest()
            or spec["payload_bytes"] != len(predecessor_raw)
        ):
            _fail("task0 verifier provider/predecessor binding differs")
    elif phase == "publish":
        if worker_provider_receipt is not None:
            _fail("task0 publish provider receipt cannot have a worker predecessor")
        output = validate_provider_publication_stdout_v3(output)
        verifier_identity = _identity(
            output.get("task0_verifier_provider_receipt_identity"),
            label="publication verifier provider receipt",
        )
        verifier_identity_raw = _provider_payload_bytes(verifier_identity)
        if (
            output.get("run_id") != spec["request_run_id"]
            or output.get("task0_worker_execution_name")
            != spec["bound_worker_execution"]
            or output.get("task0_verifier_execution_name")
            != spec["bound_verifier_execution"]
            or spec["payload_sha256"]
            != sha256(verifier_identity_raw).hexdigest()
            or spec["payload_bytes"] != len(verifier_identity_raw)
        ):
            _fail("task0 publish provider stdout differs")
    else:
        if worker_provider_receipt is not None:
            _fail("task0 reopen provider receipt cannot have a worker predecessor")
        receipt = validate_independent_reopen_receipt_v3(output)
        predecessor_identity = _identity(
            receipt.get("publication_provider_receipt_identity"),
            label="publication provider receipt",
        )
        predecessor_raw = _provider_payload_bytes(predecessor_identity)
        if (
            receipt["run_id"] != spec["request_run_id"]
            or receipt["publisher_execution_name"]
            != spec["bound_publisher_execution"]
            or receipt["reopen_execution_name"] != spec["execution_name"]
            or receipt["task0_worker_execution_name"]
            != spec["bound_worker_execution"]
            or receipt["task0_verifier_execution_name"]
            != spec["bound_verifier_execution"]
            or spec["payload_sha256"] != sha256(predecessor_raw).hexdigest()
            or spec["payload_bytes"] != len(predecessor_raw)
        ):
            _fail("independent reopen provider/predecessor binding differs")
    body: dict[str, object] = {
        "schema_version": TASK0_PROVIDER_RECEIPT_SCHEMA,
        "complete": True,
        "provider_execution_spec": spec,
        "operator_output": output,
    }
    if predecessor is not None:
        body["worker_provider_receipt"] = predecessor
    body["provider_receipt_sha256"] = batch_v3.canonical_sha256(body)
    return body


def validate_task0_provider_receipt_v3(value: object) -> dict[str, object]:
    item = _mapping(value, label="task0 provider receipt")
    retained = item.get("provider_receipt_sha256")
    body = dict(item)
    body.pop("provider_receipt_sha256", None)
    if (
        item.get("schema_version") != TASK0_PROVIDER_RECEIPT_SCHEMA
        or item.get("complete") is not True
        or retained != batch_v3.canonical_sha256(body)
    ):
        _fail("task0 provider receipt differs")
    spec = validate_provider_execution_spec_v3(
        item.get("provider_execution_spec")
    )
    predecessor_value = item.get("worker_provider_receipt")
    expected = _build_task0_provider_receipt_v3(
        provider_execution_spec=spec,
        operator_output=_mapping(
            item.get("operator_output"), label="task0 provider operator output"
        ),
        worker_provider_receipt=(
            None
            if predecessor_value is None
            else _mapping(predecessor_value, label="worker provider receipt")
        ),
    )
    if item != expected:
        _fail("task0 provider receipt normalized bytes differ")
    return item


def _exact_reopen_provider_receipt_v3(
    value: object,
) -> tuple[dict[str, object], dict[str, object]]:
    """Read one controller-persisted provider receipt by immutable identity.

    Full publication and the independent reopen deliberately do not accept
    provider receipt content from a caller.  The controller first derives the
    receipt from Cloud Run's exact execution record and unique stdout, writes
    those canonical bytes create-once, and passes only this generation-pinned
    identity to the provider worker.
    """

    identity = _identity(value, label="controller provider receipt")
    uri = str(identity["uri"])
    prefix = (
        f"gs://{batch_v3.OUTPUT_BUCKET}/"
        "research/corpus-r6-matchup-source-controller-v3/"
    )
    if not uri.startswith(prefix) or not uri.endswith("/provider-receipt.json"):
        _fail("controller provider receipt escapes its immutable namespace")
    try:
        transport = batch_mechanics._trusted_gcs_transport_v1(
            expected_write_uris=()
        )
        raw = transport.read_exact(identity)
    except Exception as exc:
        raise CorpusR6MatchupSourceTask0V3Error(
            f"controller provider receipt exact reopen failed: {exc}"
        ) from exc
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupSourceTask0V3Error(
            "controller provider receipt is not canonical JSON"
        ) from exc
    provider = validate_task0_provider_receipt_v3(parsed)
    if raw != _provider_payload_bytes(provider):
        _fail("controller provider receipt bytes are not exact canonical JSON")
    return provider, identity


def validate_full_publication_authorization_v3(
    value: object,
    *,
    expected_run_id: str | None = None,
    expected_capture_plan_binding: Mapping[str, object] | None = None,
    expected_closure_sha256: str | None = None,
    expected_runtime_sha256: str | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="task0 full-publication authorization")
    retained = item.get("task0_full_authorization_sha256")
    body = dict(item)
    body.pop("task0_full_authorization_sha256", None)
    provider = validate_task0_provider_receipt_v3(
        item.get("verifier_provider_receipt")
    )
    provider_spec = provider["provider_execution_spec"]
    verifier = provider["operator_output"]
    worker_provider = provider.get("worker_provider_receipt")
    if not isinstance(worker_provider, Mapping):
        _fail("task0 full authorization lacks worker provider receipt")
    worker_spec = _mapping(
        worker_provider.get("provider_execution_spec"),
        label="task0 worker provider spec",
    )
    expected_fields = {
        "schema_version", "complete", "run_id", "worker_execution_name",
        "verifier_execution_name", "worker_result_identity",
        "verifier_provider_receipt_identity",
        "verifier_provider_receipt", "verifier_provider_receipt_sha256",
        "capture_plan_v3_binding", "executed_dependency_closure_sha256",
        "runtime_binding_sha256", "full_publication_gate_passed",
        "publication_callback_exposed", "write_inventory_count",
        "ambient_service_account_write_capability", "outcome_columns_read",
        "uses_realized_outcomes", *source.FALSE_AUTHORITY_FIELDS,
        "task0_full_authorization_sha256",
    }
    if (
        set(item) != expected_fields
        or item.get("schema_version") != TASK0_FULL_AUTHORIZATION_SCHEMA
        or item.get("complete") is not True
        or provider_spec["phase"] != "verify"
        or worker_spec.get("phase") != "worker"
        or item.get("run_id") != verifier["run_id"]
        or item.get("worker_execution_name") != verifier["worker_execution_name"]
        or item.get("verifier_execution_name")
        != verifier["verifier_execution_name"]
        or item.get("worker_result_identity") != verifier["worker_result_identity"]
        or _identity(
            item.get("verifier_provider_receipt_identity"),
            label="verifier provider receipt",
        )["sha256"]
        != sha256(_provider_payload_bytes(provider)).hexdigest()
        or item.get("verifier_provider_receipt_sha256")
        != provider["provider_receipt_sha256"]
        or item.get("capture_plan_v3_binding")
        != verifier["capture_plan_v3_binding"]
        or item.get("executed_dependency_closure_sha256")
        != verifier["executed_dependency_closure_sha256"]
        or item.get("runtime_binding_sha256")
        != verifier["runtime_binding_sha256"]
        or item.get("full_publication_gate_passed") is not True
        or item.get("publication_callback_exposed") is not False
        or item.get("write_inventory_count") != 0
        or item.get("ambient_service_account_write_capability") != "not_evaluated"
        or retained != batch_v3.canonical_sha256(body)
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
        or any(item.get(field) is not False for field in source.FALSE_AUTHORITY_FIELDS)
    ):
        _fail("task0 full-publication authorization differs")
    run_id = _run_id(item.get("run_id"))
    if expected_run_id is not None and run_id != _run_id(expected_run_id):
        _fail("task0 full authorization differs from expected run ID")
    if (
        expected_capture_plan_binding is not None
        and item["capture_plan_v3_binding"] != dict(expected_capture_plan_binding)
    ):
        _fail("task0 full authorization differs from expected capture plan")
    if (
        expected_closure_sha256 is not None
        and item["executed_dependency_closure_sha256"]
        != _hex_digest(expected_closure_sha256, label="expected closure SHA")
    ):
        _fail("task0 full authorization differs from expected closure")
    if (
        expected_runtime_sha256 is not None
        and item["runtime_binding_sha256"]
        != _hex_digest(expected_runtime_sha256, label="expected runtime SHA")
    ):
        _fail("task0 full authorization differs from expected runtime")
    return item


def authorize_full_publication_v3(
    value: object,
    *,
    expected_run_id: str,
) -> dict[str, object]:
    """Bind exact provider-owned worker/verifier executions to Commit B."""

    provider, provider_identity = _exact_reopen_provider_receipt_v3(value)
    provider_spec = provider["provider_execution_spec"]
    receipt = validate_task0_verifier_receipt_v3(provider["operator_output"])
    worker_provider = provider.get("worker_provider_receipt")
    if provider_spec["phase"] != "verify" or not isinstance(
        worker_provider, Mapping
    ):
        _fail("full publication requires provider-bound verifier receipt")
    worker_spec = validate_provider_execution_spec_v3(
        worker_provider.get("provider_execution_spec")
    )
    run_id = _run_id(expected_run_id)
    expected_worker = _execution_name(
        os.environ.get(BOUND_WORKER_EXECUTION_ENV),
        label="controller-bound worker execution",
    )
    expected_verifier = _execution_name(
        os.environ.get(BOUND_VERIFIER_EXECUTION_ENV),
        label="controller-bound verifier execution",
    )
    if (
        receipt["run_id"] != run_id
        or worker_spec["execution_name"] != expected_worker
        or provider_spec["execution_name"] != expected_verifier
        or receipt["worker_execution_name"] != expected_worker
        or receipt["verifier_execution_name"] != expected_verifier
    ):
        _fail("task0 provider receipt differs from controller execution binding")
    closure, runtime, _, binding, _ = batch_v3._validate_local_context_v3()
    if (
        receipt["capture_plan_v3_binding"] != binding
        or receipt["executed_dependency_closure_sha256"]
        != closure["dependency_closure_sha256"]
        or receipt["runtime_binding_sha256"] != runtime["runtime_binding_sha256"]
    ):
        _fail("task0 provider receipt differs from full-publication runtime")
    body: dict[str, object] = {
        "schema_version": TASK0_FULL_AUTHORIZATION_SCHEMA,
        "complete": True,
        "run_id": run_id,
        "worker_execution_name": expected_worker,
        "verifier_execution_name": expected_verifier,
        "worker_result_identity": receipt["worker_result_identity"],
        "verifier_provider_receipt_identity": provider_identity,
        "verifier_provider_receipt": provider,
        "verifier_provider_receipt_sha256": provider[
            "provider_receipt_sha256"
        ],
        "capture_plan_v3_binding": binding,
        "executed_dependency_closure_sha256": closure[
            "dependency_closure_sha256"
        ],
        "runtime_binding_sha256": runtime["runtime_binding_sha256"],
        "full_publication_gate_passed": True,
        "publication_callback_exposed": False,
        "write_inventory_count": 0,
        "ambient_service_account_write_capability": "not_evaluated",
        **_policy(),
    }
    body["task0_full_authorization_sha256"] = batch_v3.canonical_sha256(body)
    return validate_full_publication_authorization_v3(
        body,
        expected_run_id=run_id,
        expected_capture_plan_binding=binding,
        expected_closure_sha256=str(closure["dependency_closure_sha256"]),
        expected_runtime_sha256=str(runtime["runtime_binding_sha256"]),
    )


def revalidate_full_publication_authorization_provider_source_v3(
    value: object,
    *,
    expected_run_id: str | None = None,
    expected_capture_plan_binding: Mapping[str, object] | None = None,
    expected_closure_sha256: str | None = None,
    expected_runtime_sha256: str | None = None,
) -> dict[str, object]:
    """Require the embedded receipt to still match its immutable GCS source."""

    item = validate_full_publication_authorization_v3(
        value,
        expected_run_id=expected_run_id,
        expected_capture_plan_binding=expected_capture_plan_binding,
        expected_closure_sha256=expected_closure_sha256,
        expected_runtime_sha256=expected_runtime_sha256,
    )
    provider, identity = _exact_reopen_provider_receipt_v3(
        item["verifier_provider_receipt_identity"]
    )
    if (
        identity != item["verifier_provider_receipt_identity"]
        or provider != item["verifier_provider_receipt"]
        or provider["provider_receipt_sha256"]
        != item["verifier_provider_receipt_sha256"]
    ):
        _fail("task0 full authorization differs from immutable provider source")
    return item


def validate_independent_reopen_receipt_v3(
    value: object,
) -> dict[str, object]:
    item = _mapping(value, label="source-v3 independent reopen receipt")
    retained = item.get("independent_reopen_receipt_sha256")
    body = dict(item)
    body.pop("independent_reopen_receipt_sha256", None)
    expected_fields = {
        "schema_version", "complete", "run_id",
        "publication_provider_receipt_identity", "publisher_execution_name",
        "reopen_execution_name", "batch_release_identity",
        "source_release_v3_identity", "source_task_count",
        "source_task_ordinal_manifest_sha256",
        "task0_full_publication_authorization_sha256",
        "task0_worker_execution_name", "task0_verifier_execution_name",
        "candidate_v2_capture_v3_component_v3_source_v3_deep_reopen_complete",
        "write_disabled_public_reopen_complete",
        "publication_callback_exposed", "write_inventory_count",
        "write_capability_enabled", "cloud_mutation_performed",
        "exact_read_cache_budget_summary", "transport_read_budget_summary",
        "outcome_columns_read", "uses_realized_outcomes",
        *source.FALSE_AUTHORITY_FIELDS,
        "independent_reopen_receipt_sha256",
    }
    if set(item) != expected_fields:
        _fail("source-v3 independent reopen receipt fields differ")
    publisher = _execution_name(
        item.get("publisher_execution_name"), label="publisher execution"
    )
    reopener = _execution_name(
        item.get("reopen_execution_name"), label="reopen execution"
    )
    if publisher == reopener:
        _fail("source-v3 publisher/reopen execution names are not distinct")
    _run_id(item.get("run_id"))
    _identity(
        item.get("publication_provider_receipt_identity"),
        label="publication provider receipt",
    )
    _identity(item.get("batch_release_identity"), label="batch release")
    _identity(item.get("source_release_v3_identity"), label="source release")
    worker = _execution_name(
        item.get("task0_worker_execution_name"), label="task0 worker"
    )
    verifier = _execution_name(
        item.get("task0_verifier_execution_name"), label="task0 verifier"
    )
    if len({worker, verifier, publisher, reopener}) != 4:
        _fail("source-v3 worker/verifier/publisher/reopen executions are not distinct")
    _hex_digest(
        item.get("task0_full_publication_authorization_sha256"),
        label="task0 authorization SHA",
    )
    _hex_digest(
        item.get("source_task_ordinal_manifest_sha256"),
        label="source ordinal manifest SHA",
    )
    _validate_read_budget_summary(
        item.get("exact_read_cache_budget_summary"),
        label="independent reopen cache budget summary",
    )
    _validate_read_budget_summary(
        item.get("transport_read_budget_summary"),
        label="independent reopen transport budget summary",
    )
    if (
        item.get("schema_version") != INDEPENDENT_REOPEN_RECEIPT_SCHEMA
        or item.get("complete") is not True
        or item.get("source_task_count") != source.TASK_COUNT
        or item.get("source_task_ordinal_manifest_sha256")
        != batch_v3.canonical_sha256(list(range(source.TASK_COUNT)))
        or item.get(
            "candidate_v2_capture_v3_component_v3_source_v3_deep_reopen_complete"
        ) is not True
        or item.get("write_disabled_public_reopen_complete") is not True
        or item.get("publication_callback_exposed") is not False
        or item.get("write_inventory_count") != 0
        or item.get("write_capability_enabled") is not False
        or item.get("cloud_mutation_performed") is not False
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
        or any(item.get(field) is not False for field in source.FALSE_AUTHORITY_FIELDS)
        or retained != batch_v3.canonical_sha256(body)
    ):
        _fail("source-v3 independent reopen receipt differs")
    return item


def independently_reopen_provider_publication_v3(
    *, publication_provider_receipt_identity: Mapping[str, object]
) -> dict[str, object]:
    """Deep-reopen the exact provider-derived publication with zero writes."""

    provider, provider_identity = _exact_reopen_provider_receipt_v3(
        publication_provider_receipt_identity
    )
    spec = validate_provider_execution_spec_v3(
        provider.get("provider_execution_spec")
    )
    publication = validate_provider_publication_stdout_v3(
        provider.get("operator_output")
    )
    publisher = _execution_name(
        os.environ.get(BOUND_PUBLISHER_EXECUTION_ENV),
        label="controller-bound publisher execution",
    )
    reopener = _execution_name(
        os.environ.get(EXECUTION_NAME_ENV), label="independent reopen execution"
    )
    verifier_provider_identity = _identity(
        publication.get("task0_verifier_provider_receipt_identity"),
        label="publication verifier provider receipt",
    )
    if (
        spec["phase"] != "publish"
        or spec["execution_name"] != publisher
        or publisher == reopener
        or publication.get("run_id") != spec["request_run_id"]
        or publication.get("terminal_batch_root_requested_last") is not True
        or publication.get("same_process_deep_reopen_complete") is not True
        or publication.get("independent_process_deep_reopen_complete") is not False
        or publication.get("independent_process_deep_reopen_required") is not True
        or publication.get("task0_worker_execution_name")
        != spec["bound_worker_execution"]
        or publication.get("task0_verifier_execution_name")
        != spec["bound_verifier_execution"]
    ):
        _fail("provider-bound source-v3 publication receipt differs")
    batch_identity = _identity(
        publication.get("batch_release_identity"), label="batch release"
    )
    reopened = batch_v3.reopen_matchup_source_batch_outer_candidate_authority_v3(
        batch_release_identity=batch_identity
    )
    if (
        reopened.get("batch_release_identity") != batch_identity
        or reopened.get("source_task_count") != source.TASK_COUNT
        or reopened.get("source_task_ordinals_reopened")
        != list(range(source.TASK_COUNT))
        or reopened.get("task0_worker_execution_name")
        != spec["bound_worker_execution"]
        or reopened.get("task0_verifier_execution_name")
        != spec["bound_verifier_execution"]
        or reopened.get("task0_full_publication_authorization_sha256")
        != publication.get("task0_full_publication_authorization_sha256")
        or reopened.get("task0_full_publication_authorization", {}).get(
            "verifier_provider_receipt_identity"
        )
        != verifier_provider_identity
        or reopened.get(
            "candidate_v2_capture_v3_component_v3_source_v3_deep_reopen_complete"
        ) is not True
        or reopened.get("write_disabled_public_reopen_complete") is not True
        or reopened.get("write_capability_enabled") is not False
        or reopened.get("cloud_mutation_performed") is not False
    ):
        _fail("provider-bound source-v3 independent reopen differs")
    body: dict[str, object] = {
        "schema_version": INDEPENDENT_REOPEN_RECEIPT_SCHEMA,
        "complete": True,
        "run_id": publication["run_id"],
        "publication_provider_receipt_identity": provider_identity,
        "publisher_execution_name": publisher,
        "reopen_execution_name": reopener,
        "batch_release_identity": batch_identity,
        "source_release_v3_identity": reopened["source_release_v3_identity"],
        "source_task_count": source.TASK_COUNT,
        "source_task_ordinal_manifest_sha256": batch_v3.canonical_sha256(
            list(range(source.TASK_COUNT))
        ),
        "task0_full_publication_authorization_sha256": reopened[
            "task0_full_publication_authorization_sha256"
        ],
        "task0_worker_execution_name": reopened["task0_worker_execution_name"],
        "task0_verifier_execution_name": reopened[
            "task0_verifier_execution_name"
        ],
        "candidate_v2_capture_v3_component_v3_source_v3_deep_reopen_complete": True,
        "write_disabled_public_reopen_complete": True,
        "publication_callback_exposed": False,
        "write_inventory_count": 0,
        "write_capability_enabled": False,
        "cloud_mutation_performed": False,
        "exact_read_cache_budget_summary": _read_budget_summary(
            reopened["exact_read_cache_budget_receipt"],
            label="independent reopen cache budget",
        ),
        "transport_read_budget_summary": _read_budget_summary(
            reopened["transport_read_budget_receipt"],
            label="independent reopen transport budget",
        ),
        **_policy(),
    }
    body["independent_reopen_receipt_sha256"] = batch_v3.canonical_sha256(body)
    return validate_independent_reopen_receipt_v3(body)


__all__ = [
    "CorpusR6MatchupSourceTask0V3Error",
    "BOUND_VERIFIER_EXECUTION_ENV",
    "BOUND_WORKER_EXECUTION_ENV",
    "BOUND_PUBLISHER_EXECUTION_ENV",
    "EXECUTION_NAME_ENV",
    "OUTPUT_INVENTORY_SCHEMA",
    "PROVIDER_PUBLICATION_STDOUT_SCHEMA",
    "SOURCE_TASK_ORDINAL",
    "TASK0_CLI_PATH",
    "TASK0_COMPONENT_RELEASE_SCHEMA",
    "TASK0_MODULE_PATH",
    "TASK0_FULL_AUTHORIZATION_SCHEMA",
    "INDEPENDENT_REOPEN_RECEIPT_SCHEMA",
    "TASK0_PROVIDER_EXECUTION_SPEC_SCHEMA",
    "TASK0_PROVIDER_RECEIPT_SCHEMA",
    "TASK0_VERIFIER_RECEIPT_SCHEMA",
    "TASK0_WORKER_RESULT_SCHEMA",
    "VERIFIER_ENABLE_ENV",
    "VERIFIER_ENABLE_VALUE",
    "WORKER_ENABLE_ENV",
    "WORKER_ENABLE_VALUE",
    "authorize_full_publication_v3",
    "independently_reopen_provider_publication_v3",
    "revalidate_full_publication_authorization_provider_source_v3",
    "output_prefix_for_run_v3",
    "publish_task0_worker_v3",
    "validate_task0_verifier_receipt_v3",
    "validate_full_publication_authorization_v3",
    "validate_independent_reopen_receipt_v3",
    "validate_provider_execution_spec_v3",
    "validate_provider_publication_stdout_v3",
    "validate_task0_provider_receipt_v3",
    "validate_task0_worker_result_structure_v3",
    "verify_task0_worker_v3",
]
