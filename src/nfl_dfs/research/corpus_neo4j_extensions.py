"""Validated analytical and parametric extensions for the Neo4j load plan.

Retrieval analytics stay in ``corpus-retrieval-research``.  Parametric corpus
legal-feasibility experiments stay in ``corpus-parametric-research`` and must
point back to an accepted retrieval task-0 projection.  The distinct
``corpus-population-research`` namespace is reserved and never populated here.
Neither extension stores matrices/raw outcomes or creates a policy-feedback
edge.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import math
import re
from typing import Final

from nfl_dfs.research.corpus_retrieval_neo4j import (
    CorpusRetrievalNeo4jError,
    Neo4jLoadPlan,
    _bind_body,
    _exact_keys,
    _identity,
    _mapping,
    _relationship,
    _sequence,
    _string,
    _validate_self_hash,
    _validate_task_result,
    append_load_plan,
    canonical_json_bytes,
    canonical_sha256,
    parse_canonical_json_bytes,
)


RETRIEVAL_NAMESPACE: Final = "corpus-retrieval-research"
PARAMETRIC_NAMESPACE: Final = "corpus-parametric-research"
POPULATION_NAMESPACE: Final = "corpus-population-research"
PARAMETRIC_TASK_SCHEMA: Final = "corpus-parametric-task-result-v2"
PARAMETRIC_COMPLETION_SCHEMA: Final = "corpus-parametric-batch-completion-v2"
PARAMETRIC_TERMINAL_SCHEMA: Final = "corpus-legal-feasibility-task-terminal/v1"
PARAMETRIC_VERIFICATION_SCHEMA: Final = (
    "corpus-legal-feasibility-independent-verification/v2"
)
PARAMETER_ORDER: Final = (
    "min_lineup_salary",
    "qb_stack_min",
    "bring_back_min",
    "forbid_rb_vs_dst",
    "forbid_two_rb_same_team",
)
PARAMETER_SET_ORDER: Final = (
    "incumbent",
    "remove-salary-floor",
    "remove-qb-stack",
    "remove-bring-back",
    "allow-rb-vs-dst",
    "allow-two-rb",
    "remove-all-five-shared-constraints",
)
REMOVED_RULE: Final = {
    "remove-salary-floor": "min_lineup_salary",
    "remove-qb-stack": "qb_stack_min",
    "remove-bring-back": "bring_back_min",
    "allow-rb-vs-dst": "forbid_rb_vs_dst",
    "allow-two-rb": "forbid_two_rb_same_team",
}
AUTHORITY_ROLES: Final = (
    "source_binding",
    "registered_law",
    "attempt_ledger",
    "matrix_authority",
    "content_task_evidence_root",
    "published_task_evidence_root",
    "draft_authority_bundle",
    "authority_bundle",
    "batch_result",
)
VERIFIED_GATE_IDS: Final = (
    "gate:corpus:batch-manifest-seven-set-identity",
    "gate:corpus:source-world-compute-pairing",
    "gate:corpus:effective-policy-runtime-replay",
    "gate:corpus:solver-terminal-zero-retry-proof",
    "gate:corpus:paired-objective-relaxation-monotonicity",
    "gate:corpus:outside-incumbent-law-nonvacuity",
    "gate:corpus:dk-legality-and-exact80",
    "gate:corpus:independent-scorefree-replay",
    "gate:corpus:simulated-score-matrix-exact-roster-world-coverage",
)


def _source_node(
    *,
    kind: str,
    logical_id: str,
    run_id: str,
    task_id: str,
    identity: Mapping[str, object],
    payload: Mapping[str, object],
    namespace: str,
    task_index: int,
    task_index_present: bool,
    slate_id: str,
    parameter_set_id: str = "",
    strategy_id: str = "",
    analysis_scope: str = "authority",
    metric_name: str = "",
    metric_value: float = 0.0,
    metric_value_present: bool = False,
) -> dict[str, object]:
    normalized = _identity(identity, label=f"{kind} source identity")
    node_digest = canonical_sha256({
        "kind": kind,
        "logical_id": logical_id,
        "identity": normalized,
    })
    return {
        "id": f"corpus-extension:{node_digest}",
        "kind": kind,
        "logical_id": logical_id,
        "run_id": run_id,
        "task_id": task_id,
        "payload_sha256": canonical_sha256(payload),
        "properties_json": canonical_json_bytes(payload).decode("utf-8"),
        "source_uri": normalized["uri"],
        "source_generation": normalized["generation"],
        "source_sha256": normalized["sha256"],
        "source_bytes": normalized["bytes"],
        "workstream_namespace": namespace,
        "task_index": task_index,
        "task_index_present": task_index_present,
        "slate_id": slate_id,
        "parameter_set_id": parameter_set_id,
        "strategy_id": strategy_id,
        "analysis_scope": analysis_scope,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "metric_value_present": metric_value_present,
    }


def _authority_id(plan: Neo4jLoadPlan, kind: str) -> str:
    rows = [str(row["id"]) for row in plan.nodes if row.get("kind") == kind]
    if len(rows) != 1:
        raise CorpusRetrievalNeo4jError(f"parent plan has no unique {kind}")
    return rows[0]


def _json_sidecar(
    *, raw: bytes, receipt: Mapping[str, object], schema: str, hash_field: str,
) -> dict[str, object]:
    identity = _bind_body(raw, receipt["object_identity"], label=str(receipt["role"]))
    if receipt.get("format") != "canonical-json-v1":
        raise CorpusRetrievalNeo4jError("analytical sidecar is not canonical JSON")
    value = dict(_mapping(
        parse_canonical_json_bytes(raw, label=str(receipt["role"])),
        label=str(receipt["role"]),
    ))
    if value.get("schema_version") != schema:
        raise CorpusRetrievalNeo4jError(f"{receipt['role']} schema differs")
    _validate_self_hash(value, hash_field, label=str(receipt["role"]))
    semantic = _mapping(receipt["semantic"], label="sidecar semantic")
    if (
        semantic.get("schema_version") != schema
        or semantic.get("canonical_json_sha256") != identity["sha256"]
    ):
        raise CorpusRetrievalNeo4jError("analytical sidecar semantic receipt differs")
    return value


def append_retrieval_analytics(
    plan: Neo4jLoadPlan,
    *,
    task_result_raw: bytes,
    json_sidecar_bodies: Mapping[tuple[str, str], bytes],
) -> Neo4jLoadPlan:
    """Append validated compact JSON analytics; NPZ bodies remain in GCS."""
    task_result, _ = _validate_task_result(
        task_result_raw, plan.task_result_identity
    )
    receipts: dict[tuple[str, str], Mapping[str, object]] = {}
    for raw_receipt in _sequence(task_result["sidecars"], label="task sidecars"):
        receipt = _mapping(raw_receipt, label="task sidecar")
        key = (str(receipt.get("role", "")), str(receipt.get("strategy_id", "")))
        if key in receipts:
            raise CorpusRetrievalNeo4jError("task sidecar keys repeat")
        receipts[key] = receipt
    allowed = {
        "enrichment-discovery": (
            "corpus-retrieval-enrichment/v1", "enrichment_sha256"
        ),
        "enrichment-all-worlds": (
            "corpus-retrieval-enrichment/v1", "enrichment_sha256"
        ),
        "redundancy-topk": (
            "corpus-retrieval-redundancy-topk/v1", "redundancy_sha256"
        ),
        "strategy-selection": (
            "corpus-retrieval-selection/v1", "selection_sha256"
        ),
    }
    nodes: list[dict[str, object]] = []
    relationships: list[dict[str, object]] = []
    projection_id = _authority_id(plan, "CorpusGraphProjection")
    run_id, task_id = plan.run_id, plan.task_id
    for key, raw in sorted(json_sidecar_bodies.items()):
        if key not in receipts:
            raise CorpusRetrievalNeo4jError(f"unknown analytical sidecar {key}")
        role, strategy_id = key
        if role not in allowed:
            raise CorpusRetrievalNeo4jError(
                f"sidecar {role} is not a compact analytical JSON role"
            )
        schema, hash_field = allowed[role]
        receipt = receipts[key]
        body = _json_sidecar(
            raw=raw, receipt=receipt, schema=schema, hash_field=hash_field
        )
        source_identity = _identity(
            receipt["object_identity"], label=f"{role} identity"
        )
        if role.startswith("enrichment-"):
            categories = {
                "players": "player_id",
                "pairs": "player_ids",
                "tags": "tag",
                "stack_signatures": "stack_signature",
                "teams": "team",
                "team_pairs": "teams",
                "games": "game_id",
            }
            for category, key_name in categories.items():
                for row in _sequence(body.get(category), label=f"{role}.{category}"):
                    measurement = dict(_mapping(row, label=f"{role}.{category} row"))
                    value = measurement.get("enrichment_vs_all_lineups")
                    if type(value) not in {int, float} or isinstance(value, bool):
                        raise CorpusRetrievalNeo4jError("enrichment metric differs")
                    logical = (
                        f"retrieval-association:{role}:{category}:"
                        f"{canonical_sha256(measurement.get(key_name))}"
                    )
                    node = _source_node(
                        kind="CorpusAssociationMeasurement",
                        logical_id=logical,
                        run_id=run_id,
                        task_id=task_id,
                        identity=source_identity,
                        payload=measurement,
                        namespace=RETRIEVAL_NAMESPACE,
                        task_index=0,
                        task_index_present=True,
                        slate_id=task_id,
                        analysis_scope=str(body.get("analysis_scope", "")),
                        metric_name="enrichment_vs_all_lineups",
                        metric_value=float(value),
                        metric_value_present=True,
                    )
                    nodes.append(node)
                    relationships.append(_relationship(
                        projection_id, "HAS_ANALYTIC_MEASUREMENT", str(node["id"]),
                        {"category": category, "role": role},
                        task_index=0,
                        slate_id=task_id,
                    ))
        elif role == "redundancy-topk":
            for row in _sequence(body.get("pairs"), label="redundancy pairs"):
                measurement = dict(_mapping(row, label="redundancy pair"))
                value = measurement.get("pearson_score_correlation")
                if type(value) not in {int, float} or isinstance(value, bool):
                    raise CorpusRetrievalNeo4jError("correlation metric differs")
                node = _source_node(
                    kind="CorpusCorrelationMeasurement",
                    logical_id=(
                        "retrieval-correlation:"
                        + canonical_sha256({
                            "left": measurement.get("left_lineup_id"),
                            "right": measurement.get("right_lineup_id"),
                        })
                    ),
                    run_id=run_id,
                    task_id=task_id,
                    identity=source_identity,
                    payload=measurement,
                    namespace=RETRIEVAL_NAMESPACE,
                    task_index=0,
                    task_index_present=True,
                    slate_id=task_id,
                    analysis_scope=str(body.get("analysis_scope", "")),
                    metric_name="pearson_score_correlation",
                    metric_value=float(value),
                    metric_value_present=True,
                )
                nodes.append(node)
                relationships.append(_relationship(
                    projection_id, "HAS_ANALYTIC_MEASUREMENT", str(node["id"]),
                    {"category": "lineup-pair-correlation", "role": role},
                    task_index=0,
                    slate_id=task_id,
                ))
        else:
            metrics = _mapping(body.get("metrics"), label="selection metrics")
            for scope, raw_summary in sorted(metrics.items()):
                summary = _mapping(raw_summary, label=f"selection metrics {scope}")
                for metric_name, value in sorted(summary.items()):
                    if type(value) not in {int, float} or isinstance(value, bool):
                        continue
                    payload = {
                        "scope": scope,
                        "metric_name": metric_name,
                        "value": value,
                        "strategy_id": strategy_id,
                    }
                    node = _source_node(
                        kind="CorpusStrategySplitMeasurement",
                        logical_id=(
                            f"retrieval-strategy-metric:{strategy_id}:{scope}:"
                            f"{metric_name}"
                        ),
                        run_id=run_id,
                        task_id=task_id,
                        identity=source_identity,
                        payload=payload,
                        namespace=RETRIEVAL_NAMESPACE,
                        task_index=0,
                        task_index_present=True,
                        slate_id=task_id,
                        strategy_id=strategy_id,
                        analysis_scope=str(scope),
                        metric_name=str(metric_name),
                        metric_value=float(value),
                        metric_value_present=True,
                    )
                    nodes.append(node)
                    relationships.append(_relationship(
                        projection_id, "HAS_ANALYTIC_MEASUREMENT", str(node["id"]),
                        {"role": role, "strategy_id": strategy_id},
                        task_index=0,
                        slate_id=task_id,
                    ))
    return append_load_plan(plan, nodes=nodes, relationships=relationships)


def _parse_bound_self_hash(
    raw: bytes,
    identity: object,
    *,
    label: str,
    schema_field: str,
    schema: str,
    hash_field: str,
    exact_keys: set[str],
) -> tuple[dict[str, object], dict[str, object]]:
    retained = _bind_body(raw, identity, label=label)
    item = dict(_mapping(parse_canonical_json_bytes(raw, label=label), label=label))
    _exact_keys(item, exact_keys, label=label)
    if item.get(schema_field) != schema:
        raise CorpusRetrievalNeo4jError(f"{label} schema differs")
    _validate_self_hash(item, hash_field, label=label)
    return item, retained


def _variant_rows(value: object, *, label: str) -> list[dict[str, object]]:
    rows = _sequence(value, label=label)
    if len(rows) != len(PARAMETER_SET_ORDER):
        raise CorpusRetrievalNeo4jError(f"{label} must cover all seven arms")
    normalized: list[dict[str, object]] = []
    for ordinal, (raw, expected_id) in enumerate(
        zip(rows, PARAMETER_SET_ORDER, strict=True)
    ):
        row = dict(_mapping(raw, label=f"{label}[{ordinal}]"))
        if row.get("ordinal") != ordinal or row.get("parameter_set_id") != expected_id:
            raise CorpusRetrievalNeo4jError(f"{label} arm order differs")
        normalized.append(row)
    return normalized


def append_parametric_batch(
    plan: Neo4jLoadPlan,
    *,
    batch_completion_raw: bytes,
    batch_completion_identity: Mapping[str, object],
    task_result_raw: bytes,
    task_result_identity: Mapping[str, object],
    terminal_receipt_raw: bytes,
    terminal_receipt_identity: Mapping[str, object],
    independent_verification_raw: bytes,
    independent_verification_identity: Mapping[str, object],
) -> Neo4jLoadPlan:
    """Append one task from an accepted complete 54-task parametric suite.

    Repeated calls may add different task indexes from the same immutable
    completion receipt.  Suite nodes and the sole retrieval-task-0 lineage
    edge deduplicate exactly; every task-grain row retains its own task index
    and exact slate ID.  This is parameter research, never corpus population.
    """
    task_keys = {
        "schema_version", "publication_mode", "batch_manifest_identity",
        "batch_id", "batch_manifest_sha256", "parameter_schema_sha256",
        "common_law_sha256", "task_index", "task_sha256", "slate_id",
        "world_artifact_receipts", "world_artifact_receipt_set_sha256",
        "artifact_source_authority_task_sha256", "code_source",
        "immutable_image", "source_receipts", "source_receipt_set_sha256",
        "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion",
        "artifact_source_authority_completion_sha256",
        "effective_policy_inventory_identity",
        "effective_policy_inventory_sha256",
        "effective_policy_rule_universe_sha256",
        "effective_policy_inventory_source_set_sha256",
        "effective_policy_classified_input_projection_sha256",
        "world_schedule", "world_seed", "solver", "execution",
        "variant_results", "task_result_sha256",
    }
    task, task_identity = _parse_bound_self_hash(
        task_result_raw,
        task_result_identity,
        label="parametric task result",
        schema_field="schema_version",
        schema=PARAMETRIC_TASK_SCHEMA,
        hash_field="task_result_sha256",
        exact_keys=task_keys,
    )
    task_index = task.get("task_index")
    if (
        task.get("publication_mode") != "create_once"
        or type(task_index) is not int
        or not 0 <= task_index < 54
    ):
        raise CorpusRetrievalNeo4jError("parametric task index is not in 0..53")
    task_key = f"task-{task_index:04d}"
    slate_id = _string(task.get("slate_id"), label="parametric slate id")
    slate_match = re.fullmatch(
        r"(?P<season>[0-9]{4})-w(?P<week>[1-9][0-9]*)"
        r"(?:-[a-z0-9][a-z0-9-]*)?",
        slate_id,
    )
    if slate_match is None:
        raise CorpusRetrievalNeo4jError("parametric slate id is not canonical")
    season = int(slate_match.group("season"))
    week = int(slate_match.group("week"))
    variants = _variant_rows(task["variant_results"], label="parametric variants")
    execution = _mapping(task["execution"], label="parametric execution")
    if (
        execution.get("task_index") != task_index
        or execution.get("attempt") != 1
        or execution.get("retry_count") != 0
        or execution.get("terminal_status") != "succeeded"
        or _identity(
            execution.get("terminal_receipt"), label="task terminal identity"
        )
        != _identity(terminal_receipt_identity, label="terminal receipt identity")
    ):
        raise CorpusRetrievalNeo4jError("parametric execution is not terminal zero-retry")

    completion_keys = {
        "schema_version", "publication_mode", "batch_manifest_identity",
        "batch_id", "batch_manifest_sha256", "parameter_schema_sha256",
        "common_law_sha256", "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion",
        "artifact_source_authority_completion_sha256",
        "effective_policy_classified_input_projection_sha256", "coverage",
        "task_results", "batch_completion_sha256",
    }
    completion, completion_identity = _parse_bound_self_hash(
        batch_completion_raw,
        batch_completion_identity,
        label="parametric batch completion",
        schema_field="schema_version",
        schema=PARAMETRIC_COMPLETION_SCHEMA,
        hash_field="batch_completion_sha256",
        exact_keys=completion_keys,
    )
    coverage = _mapping(
        completion["coverage"], label="parametric completion coverage"
    )
    _exact_keys(
        coverage,
        {"task_count", "parameter_set_count", "matrix_cell_count", "complete"},
        label="parametric completion coverage",
    )
    if (
        coverage.get("complete") is not True
        or coverage.get("task_count") != 54
        or coverage.get("parameter_set_count") != 7
        or coverage.get("matrix_cell_count") != 378
    ):
        raise CorpusRetrievalNeo4jError("parametric completion is incomplete")
    completion_rows = _sequence(completion["task_results"], label="completion tasks")
    if len(completion_rows) != 54:
        raise CorpusRetrievalNeo4jError("parametric completion is incomplete")
    completion_task_keys = {
        "task_index", "task_sha256", "artifact_source_authority_task_sha256",
        "world_artifact_receipt_set_sha256", "task_result_sha256",
        "task_result_object",
    }
    normalized_completion_rows: list[dict[str, object]] = []
    completion_object_keys: set[tuple[object, ...]] = set()
    completion_task_hashes: set[str] = set()
    for ordinal, raw_row in enumerate(completion_rows):
        row = dict(_mapping(raw_row, label=f"completion task[{ordinal}]"))
        _exact_keys(row, completion_task_keys, label=f"completion task[{ordinal}]")
        if row.get("task_index") != ordinal:
            raise CorpusRetrievalNeo4jError(
                "parametric completion task order/index differs"
            )
        for field in (
            "task_sha256", "artifact_source_authority_task_sha256",
            "world_artifact_receipt_set_sha256", "task_result_sha256",
        ):
            value = row.get(field)
            if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
                raise CorpusRetrievalNeo4jError(
                    f"completion task[{ordinal}].{field} differs"
                )
        object_identity = _identity(
            row["task_result_object"],
            label=f"completion task[{ordinal}] result identity",
        )
        object_key = tuple(
            object_identity[key] for key in ("uri", "generation", "sha256", "bytes")
        )
        if object_key in completion_object_keys:
            raise CorpusRetrievalNeo4jError(
                "parametric completion task-result objects alias"
            )
        completion_object_keys.add(object_key)
        task_hash = str(row["task_sha256"])
        if task_hash in completion_task_hashes:
            raise CorpusRetrievalNeo4jError("parametric completion task hashes alias")
        completion_task_hashes.add(task_hash)
        row["task_result_object"] = object_identity
        normalized_completion_rows.append(row)
    accepted_task = normalized_completion_rows[task_index]
    normalized_task_identity = _identity(
        task_identity, label="parametric task result identity"
    )
    shared_binding_fields = (
        "batch_manifest_identity", "batch_id", "batch_manifest_sha256",
        "parameter_schema_sha256", "common_law_sha256",
        "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion",
        "artifact_source_authority_completion_sha256",
        "effective_policy_classified_input_projection_sha256",
    )
    if (
        accepted_task.get("task_sha256") != task["task_sha256"]
        or accepted_task.get("artifact_source_authority_task_sha256")
        != task["artifact_source_authority_task_sha256"]
        or accepted_task.get("world_artifact_receipt_set_sha256")
        != task["world_artifact_receipt_set_sha256"]
        or accepted_task.get("task_result_sha256") != task["task_result_sha256"]
        or accepted_task.get("task_result_object") != normalized_task_identity
        or any(completion.get(field) != task.get(field) for field in shared_binding_fields)
    ):
        raise CorpusRetrievalNeo4jError("parametric completion task binding differs")

    terminal_keys = {
        "schema", "batch_manifest_sha256", "evidence_contract_identity",
        "evidence_contract_sha256", "task_request_sha256", "task_index",
        "task_sha256", "execution_id", "execution_uid", "task_attempt",
        "max_retries", "succeeded_count", "failed_count", "cancelled_count",
        "retried_count", "completed_condition", "strict_terminal_success",
        "runtime_image_terminal_verification",
        "ambient_score_relevant_keys_present", "authorities",
        "runtime_policy_objects", "variant_result_objects",
        "outcome_columns_read", "uses_realized_outcomes",
        "historical_scoring_licensed", "production_change_licensed",
        "decision_authority", "terminal_receipt_sha256",
    }
    terminal, terminal_identity = _parse_bound_self_hash(
        terminal_receipt_raw,
        terminal_receipt_identity,
        label="parametric terminal receipt",
        schema_field="schema",
        schema=PARAMETRIC_TERMINAL_SCHEMA,
        hash_field="terminal_receipt_sha256",
        exact_keys=terminal_keys,
    )
    terminal_acceptance = {
        "task_index": task_index,
        "task_attempt": 0,
        "max_retries": 0,
        "succeeded_count": 1,
        "failed_count": 0,
        "cancelled_count": 0,
        "retried_count": 0,
        "completed_condition": "True",
        "strict_terminal_success": True,
        "ambient_score_relevant_keys_present": [],
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    if any(terminal.get(key) != expected for key, expected in terminal_acceptance.items()):
        raise CorpusRetrievalNeo4jError("parametric terminal receipt is not accepted")
    if (
        terminal.get("task_sha256") != task["task_sha256"]
        or terminal.get("batch_manifest_sha256") != task["batch_manifest_sha256"]
        or terminal.get("execution_id") != execution.get("execution_id")
        or terminal.get("execution_uid") != execution.get("execution_uid")
        or _identity(execution["terminal_receipt"], label="task terminal identity")
        != terminal_identity
    ):
        raise CorpusRetrievalNeo4jError("parametric terminal binding differs")
    authorities = _mapping(terminal["authorities"], label="terminal authorities")
    _exact_keys(authorities, set(AUTHORITY_ROLES), label="terminal authorities")
    authority_identities = {
        role: _identity(authorities[role], label=f"terminal authority {role}")
        for role in AUTHORITY_ROLES
    }
    policy_rows = _variant_rows(
        terminal["runtime_policy_objects"], label="terminal policy objects"
    )
    result_rows = _variant_rows(
        terminal["variant_result_objects"], label="terminal result objects"
    )
    for ordinal, (variant, policy, result) in enumerate(zip(
        variants, policy_rows, result_rows, strict=True
    )):
        if (
            policy.get("object_identity") != variant.get("effective_policy_receipt")
            or result.get("object_identity") != variant.get("result_object")
        ):
            raise CorpusRetrievalNeo4jError(
                f"parametric terminal variant[{ordinal}] binding differs"
            )

    verification_keys = {
        "schema", "task_index", "season", "week", "slate_id",
        "source_binding_sha256", "registered_law_sha256",
        "attempt_ledger_sha256", "matrix_authority_sha256",
        "solver_evidence_task_root_sha256",
        "published_task_evidence_root_sha256", "draft_sha256",
        "authority_bundle_sha256",
        "artifact_source_authority_completion_object_sha256",
        "artifact_source_authority_completion_sha256",
        "artifact_source_authority_task_sha256", "evidence_contract_sha256",
        "task_result_sha256", "terminal_receipt_sha256",
        "variant_result_sha256s", "batch_result_sha256",
        "candidate_score_sha256s", "selected_score_sha256s",
        "paired_primary_optimum_summary", "outside_incumbent_law_summaries",
        "score_free_endpoint_summaries", "score_matrix_coverage_summaries",
        "verified_cell_count", "verified_solver_stage_count",
        "verified_unique_candidate_count", "verified_selected_entry_count",
        "verified_gate_ids", "outcome_columns_read", "uses_realized_outcomes",
        "historical_scoring_licensed", "production_change_licensed",
        "decision_authority", "verification_sha256",
    }
    verification, verification_identity = _parse_bound_self_hash(
        independent_verification_raw,
        independent_verification_identity,
        label="independent parametric verification",
        schema_field="schema",
        schema=PARAMETRIC_VERIFICATION_SCHEMA,
        hash_field="verification_sha256",
        exact_keys=verification_keys,
    )
    if (
        verification.get("task_index") != task_index
        or verification.get("slate_id") != slate_id
        or verification.get("season") != season
        or verification.get("week") != week
        or verification.get("artifact_source_authority_task_sha256")
        != task["artifact_source_authority_task_sha256"]
        or verification.get("artifact_source_authority_completion_sha256")
        != task["artifact_source_authority_completion_sha256"]
        or verification.get("task_result_sha256") != task["task_result_sha256"]
        or verification.get("terminal_receipt_sha256")
        != terminal["terminal_receipt_sha256"]
        or verification.get("verified_cell_count") != 7_000
        or verification.get("verified_solver_stage_count") != 14_000
        or verification.get("verified_selected_entry_count") != 560
        or verification.get("verified_gate_ids") != list(VERIFIED_GATE_IDS)
        or verification.get("outcome_columns_read") != []
        or verification.get("uses_realized_outcomes") is not False
        or verification.get("historical_scoring_licensed") is not False
        or verification.get("production_change_licensed") is not False
        or verification.get("decision_authority") is not False
    ):
        raise CorpusRetrievalNeo4jError("independent verification is not accepted")
    for field in (
        "variant_result_sha256s", "candidate_score_sha256s",
        "selected_score_sha256s", "outside_incumbent_law_summaries",
        "score_free_endpoint_summaries", "score_matrix_coverage_summaries",
    ):
        if len(_sequence(verification[field], label=field)) != 7:
            raise CorpusRetrievalNeo4jError(f"independent verification {field} differs")
    batch_id = _string(task["batch_id"], label="parametric batch id")
    parent_projection = _authority_id(plan, "CorpusGraphProjection")
    nodes: list[dict[str, object]] = []

    suite_completion = _source_node(
        kind="CorpusParametricBatchCompletion",
        logical_id=f"corpus-parametric:{batch_id}:completion",
        run_id=batch_id,
        task_id="",
        identity=completion_identity,
        payload=completion,
        namespace=PARAMETRIC_NAMESPACE,
        task_index=-1,
        task_index_present=False,
        slate_id="",
        analysis_scope="complete-54-task-suite",
    )
    nodes.append(suite_completion)
    suite_completion_id = str(suite_completion["id"])
    workstream_payload = {
        "namespace": PARAMETRIC_NAMESPACE,
        "reserved_population_namespace": POPULATION_NAMESPACE,
        "population_namespace_populated": False,
        "parent_retrieval_task_id": plan.task_id,
        "parent_graph_projection_identity": plan.graph_projection_identity,
        "lineage_scope": "suite-root-only",
        "same_slate_derivation_claim": False,
        "automatic_policy_feedback": False,
        "corpus_fill_authority": False,
        "corpus_population_mutation_authority": False,
        "corpus_mutation_authority": False,
        "production_policy_authority": False,
        "decision_authority": False,
        "world_matrices_stored_in_graph": False,
        "raw_outcomes_stored_in_graph": False,
    }
    workstream = _source_node(
        kind="CorpusParametricWorkstream",
        logical_id=f"corpus-parametric:{batch_id}",
        run_id=batch_id,
        task_id="",
        identity=completion_identity,
        payload=workstream_payload,
        namespace=PARAMETRIC_NAMESPACE,
        task_index=-1,
        task_index_present=False,
        slate_id="",
        analysis_scope="score-free-parametric-suite",
    )
    nodes.append(workstream)
    workstream_id = str(workstream["id"])

    task_node = _source_node(
        kind="CorpusParametricTask",
        logical_id=f"corpus-parametric:{batch_id}:{task_key}:{slate_id}",
        run_id=batch_id,
        task_id=slate_id,
        identity=task_identity,
        payload={
            "batch_id": batch_id,
            "task_index": task_index,
            "task_key": task_key,
            "task_sha256": task["task_sha256"],
            "slate_id": slate_id,
            "corpus_fill_authority": False,
            "corpus_population_mutation_authority": False,
            "production_policy_authority": False,
            "decision_authority": False,
        },
        namespace=PARAMETRIC_NAMESPACE,
        task_index=task_index,
        task_index_present=True,
        slate_id=slate_id,
        analysis_scope="score-free-parametric-task",
    )
    nodes.append(task_node)
    task_node_id = str(task_node["id"])

    source_specs = (
        ("CorpusParametricTaskResult", "task-result", task_identity, task),
        ("CorpusParametricTaskTerminal", "terminal", terminal_identity, terminal),
        (
            "CorpusParametricIndependentVerification", "verification",
            verification_identity, verification,
        ),
    )
    ids: dict[str, str] = {}
    for kind, label, identity, payload in source_specs:
        node = _source_node(
            kind=kind,
            logical_id=(
                f"corpus-parametric:{batch_id}:{task_key}:{slate_id}:{label}"
            ),
            run_id=batch_id,
            task_id=slate_id,
            identity=identity,
            payload=payload,
            namespace=PARAMETRIC_NAMESPACE,
            task_index=task_index,
            task_index_present=True,
            slate_id=slate_id,
            analysis_scope="score-free-independent-verification",
        )
        nodes.append(node)
        ids[kind] = str(node["id"])

    def task_relationship(
        source: str,
        relationship_type: str,
        target: str,
        properties: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        return _relationship(
            source,
            relationship_type,
            target,
            properties,
            task_index=task_index,
            task_index_present=True,
            slate_id=slate_id,
        )

    relationships = [
        _relationship(
            workstream_id, "DERIVED_FROM_RETRIEVAL_TASK0", parent_projection,
            {
                "lineage_scope": "suite-root-only",
                "same_slate_derivation_claim": False,
                "automatic_policy_feedback": False,
            },
            task_index=-1,
            task_index_present=False,
            slate_id="",
        ),
        _relationship(
            workstream_id, "HAS_BATCH_COMPLETION", suite_completion_id,
            task_index=-1,
            task_index_present=False,
            slate_id="",
        ),
        task_relationship(
            workstream_id, "HAS_PARAMETRIC_TASK", task_node_id,
            {"task_index": task_index, "slate_id": slate_id},
        ),
        task_relationship(
            suite_completion_id, "INCLUDES_TASK_RESULT",
            ids["CorpusParametricTaskResult"],
            {"task_index": task_index, "slate_id": slate_id},
        ),
        task_relationship(
            task_node_id, "HAS_TASK_RESULT", ids["CorpusParametricTaskResult"],
        ),
        task_relationship(
            ids["CorpusParametricTaskResult"], "HAS_TERMINAL_RECEIPT",
            ids["CorpusParametricTaskTerminal"],
        ),
        task_relationship(
            ids["CorpusParametricTaskTerminal"], "INDEPENDENTLY_VERIFIED_BY",
            ids["CorpusParametricIndependentVerification"],
        ),
    ]

    arm_ids: dict[str, str] = {}
    for ordinal, (parameter_set_id, variant) in enumerate(zip(
        PARAMETER_SET_ORDER, variants, strict=True
    )):
        payload = {
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "parameter_set_sha256": variant.get("parameter_set_sha256"),
            "automatic_policy_feedback": False,
            "production_policy_authority": False,
        }
        node = _source_node(
            kind="CorpusParametricArm",
            logical_id=(
                f"corpus-parametric:{batch_id}:{task_key}:{slate_id}:"
                f"arm:{parameter_set_id}"
            ),
            run_id=batch_id,
            task_id=slate_id,
            identity=verification_identity,
            payload=payload,
            namespace=PARAMETRIC_NAMESPACE,
            task_index=task_index,
            task_index_present=True,
            slate_id=slate_id,
            parameter_set_id=parameter_set_id,
            analysis_scope="score-free",
        )
        nodes.append(node)
        arm_ids[parameter_set_id] = str(node["id"])
        relationships.append(task_relationship(
            task_node_id, "HAS_PARAMETER_ARM", str(node["id"]),
            {"ordinal": ordinal},
        ))

    rule_ids: dict[str, str] = {}
    for rule_name in PARAMETER_ORDER:
        node = _source_node(
            kind="CorpusParametricRule",
            logical_id=f"corpus-parametric:{batch_id}:rule:{rule_name}",
            run_id=batch_id,
            task_id="",
            identity=completion_identity,
            payload={
                "rule_name": rule_name,
                "corpus_fill_authority": False,
                "corpus_population_mutation_authority": False,
                "production_mutation": False,
                "decision_authority": False,
            },
            namespace=PARAMETRIC_NAMESPACE,
            task_index=-1,
            task_index_present=False,
            slate_id="",
            analysis_scope="rule-state",
        )
        nodes.append(node)
        rule_ids[rule_name] = str(node["id"])
    for parameter_set_id in PARAMETER_SET_ORDER:
        for rule_name in PARAMETER_ORDER:
            removed = (
                parameter_set_id == "remove-all-five-shared-constraints"
                or REMOVED_RULE.get(parameter_set_id) == rule_name
            )
            relationships.append(task_relationship(
                arm_ids[parameter_set_id], "RULE_STATE", rule_ids[rule_name],
                {"state": "removed" if removed else "retained"},
            ))

    artifact_rows: list[tuple[str, str, Mapping[str, object]]] = []
    artifact_rows.extend(
        (role, "", identity) for role, identity in authority_identities.items()
    )
    for variant in variants:
        parameter_id = str(variant["parameter_set_id"])
        artifact_rows.extend((
            ("effective-policy", parameter_id, _identity(
                variant["effective_policy_receipt"], label="effective policy identity"
            )),
            ("variant-result", parameter_id, _identity(
                variant["result_object"], label="variant result identity"
            )),
        ))
    for role, parameter_id, identity in artifact_rows:
        node = _source_node(
            kind="CorpusParametricArtifactPointer",
            logical_id=(
                f"corpus-parametric:{batch_id}:{task_key}:{slate_id}:"
                f"{role}:{parameter_id or 'task'}"
            ),
            run_id=batch_id,
            task_id=slate_id,
            identity=identity,
            payload={
                "role": role,
                "parameter_set_id": parameter_id,
                "large_body_stays_in_gcs": True,
            },
            namespace=PARAMETRIC_NAMESPACE,
            task_index=task_index,
            task_index_present=True,
            slate_id=slate_id,
            parameter_set_id=parameter_id,
            analysis_scope="pointer-only-large-bodies-remain-in-gcs",
        )
        nodes.append(node)
        relationships.append(task_relationship(
            ids["CorpusParametricTaskTerminal"],
            "REFERENCES_ARTIFACT", str(node["id"]),
            {"role": role, "parameter_set_id": parameter_id},
        ))

    def measurement(
        *, kind: str, parameter_id: str, name: str, value: object,
        payload: Mapping[str, object], scope: str,
    ) -> None:
        if type(value) not in {int, float} or isinstance(value, bool):
            raise CorpusRetrievalNeo4jError(f"parametric metric {name} differs")
        numeric = float(value)
        if not math.isfinite(numeric):
            raise CorpusRetrievalNeo4jError(f"parametric metric {name} is non-finite")
        node = _source_node(
            kind=kind,
            logical_id=(
                f"corpus-parametric:{batch_id}:{task_key}:{slate_id}:"
                f"{parameter_id}:"
                f"{scope}:{name}"
            ),
            run_id=batch_id,
            task_id=slate_id,
            identity=verification_identity,
            payload=payload,
            namespace=PARAMETRIC_NAMESPACE,
            task_index=task_index,
            task_index_present=True,
            slate_id=slate_id,
            parameter_set_id=parameter_id,
            analysis_scope=scope,
            metric_name=name,
            metric_value=numeric,
            metric_value_present=True,
        )
        nodes.append(node)
        relationships.append(task_relationship(
            arm_ids[parameter_id], "HAS_MEASUREMENT", str(node["id"]),
            {"scope": scope},
        ))

    endpoints = _sequence(
        verification["score_free_endpoint_summaries"], label="endpoint summaries"
    )
    coverages = _sequence(
        verification["score_matrix_coverage_summaries"], label="coverage summaries"
    )
    outside_rows = _sequence(
        verification["outside_incumbent_law_summaries"], label="outside summaries"
    )
    for ordinal, parameter_id in enumerate(PARAMETER_SET_ORDER):
        endpoint = dict(_mapping(endpoints[ordinal], label="endpoint summary"))
        coverage_row = dict(_mapping(coverages[ordinal], label="coverage summary"))
        outside = dict(_mapping(outside_rows[ordinal], label="outside summary"))
        if (
            endpoint.get("schema") != "corpus-score-free-endpoint-summary/v1"
            or coverage_row.get("schema") != "corpus-score-matrix-coverage/v1"
            or outside.get("schema")
            != "corpus-outside-incumbent-law-nonvacuity/v1"
        ):
            raise CorpusRetrievalNeo4jError("parametric summary schema differs")
        _validate_self_hash(
            endpoint, "endpoint_summary_sha256", label="endpoint summary"
        )
        _validate_self_hash(
            coverage_row, "coverage_sha256", label="coverage summary"
        )
        _validate_self_hash(
            outside, "outside_law_nonvacuity_sha256", label="outside summary"
        )
        if any(row.get("parameter_set_id") != parameter_id for row in (
            endpoint, coverage_row, outside
        )):
            raise CorpusRetrievalNeo4jError("parametric summary arm identity differs")
        if (
            coverage_row.get("world_count") != 50_000
            or coverage_row.get("selected_roster_count") != 80
            or coverage_row.get("complete_generated_unique_roster_row_coverage")
            is not True
            or coverage_row.get("complete_selected_roster_row_coverage") is not True
            or coverage_row.get("selected_rows_are_exact_candidate_subset") is not True
            or outside.get("passed") is not True
        ):
            raise CorpusRetrievalNeo4jError("parametric coverage diagnostic fails")
        for name in (
            "simulated_candidate_ceiling_c", "simulated_exact80_maximum_s",
            "simulated_conversion_gap_c_minus_s",
        ):
            measurement(
                kind="CorpusScoreFreeMeasurement",
                parameter_id=parameter_id,
                name=name,
                value=endpoint.get(name),
                payload=endpoint,
                scope="score-free-endpoint",
            )
        for name in (
            "generated_unique_roster_count", "candidate_score_row_count",
            "selected_roster_count", "selected_score_row_count", "world_count",
        ):
            measurement(
                kind="CorpusCoverageMeasurement",
                parameter_id=parameter_id,
                name=name,
                value=coverage_row.get(name),
                payload=coverage_row,
                scope="score-matrix-coverage",
            )
        measurement(
            kind="CorpusRuleEffectMeasurement",
            parameter_id=parameter_id,
            name="outside_incumbent_law_unique_count",
            value=outside.get("outside_incumbent_law_unique_count"),
            payload=outside,
            scope="outside-incumbent-law",
        )

    paired = _mapping(
        verification["paired_primary_optimum_summary"], label="paired summary"
    )
    if (
        paired.get("schema")
        != "corpus-paired-primary-optimum-monotonicity/v1"
        or paired.get("all_deltas_nonnegative") is not True
    ):
        raise CorpusRetrievalNeo4jError("paired relaxation monotonicity is not accepted")
    _validate_self_hash(
        paired, "paired_monotonicity_sha256", label="paired summary"
    )
    challenger_rows = _sequence(paired.get("challenger_summaries"), label="challengers")
    if len(challenger_rows) != 6:
        raise CorpusRetrievalNeo4jError("paired challenger coverage differs")
    for ordinal, raw in enumerate(challenger_rows, start=1):
        row = dict(_mapping(raw, label="challenger summary"))
        parameter_id = PARAMETER_SET_ORDER[ordinal]
        if (
            row.get("challenger_variant_ordinal") != ordinal
            or row.get("challenger_parameter_set_id") != parameter_id
            or row.get("all_deltas_nonnegative") is not True
        ):
            raise CorpusRetrievalNeo4jError("paired challenger identity differs")
        for name in (
            "minimum_primary_optimum_delta_micro",
            "maximum_primary_optimum_delta_micro", "zero_delta_count",
            "positive_delta_count",
        ):
            measurement(
                kind="CorpusRuleEffectMeasurement",
                parameter_id=parameter_id,
                name=name,
                value=row.get(name),
                payload=row,
                scope="paired-primary-optimum",
            )
    return append_load_plan(plan, nodes=nodes, relationships=relationships)


__all__ = [
    "AUTHORITY_ROLES",
    "PARAMETRIC_COMPLETION_SCHEMA",
    "PARAMETRIC_NAMESPACE",
    "PARAMETRIC_TASK_SCHEMA",
    "PARAMETRIC_TERMINAL_SCHEMA",
    "PARAMETRIC_VERIFICATION_SCHEMA",
    "PARAMETER_ORDER",
    "PARAMETER_SET_ORDER",
    "POPULATION_NAMESPACE",
    "VERIFIED_GATE_IDS",
    "RETRIEVAL_NAMESPACE",
    "append_parametric_batch",
    "append_retrieval_analytics",
]
