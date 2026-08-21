"""Strict, outcome-blind contract for the first corpus parameter batch.

This module is deliberately only a schema and validation layer.  It owns no
environment reads, optimizer calls, object-store client, historical outcome
reader, graph writer, or deployment path.  A future runner may consume these
objects only after separately proving that its request-local policy object
controls the effective engine law.

The scientific surface is closed: exactly five mandatory, typed parameters
and exactly seven complete assignments.  The batch freezes every other
score-relevant input as common law.  Workers receive only a generation-pinned
manifest identity and a task index.  Successful task receipts cover all seven
assignments in fixed order, and a terminal completion receipt is possible only
for a complete task-by-parameter-set matrix.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import json
import re
from typing import Final


PARAMETER_SPEC_SCHEMA: Final = "corpus-parametric-parameter-spec-v1"
PARAMETER_SET_SCHEMA: Final = "corpus-parametric-parameter-set-v1"
BATCH_MANIFEST_SCHEMA: Final = "corpus-parametric-batch-manifest-v2"
TASK_REQUEST_SCHEMA: Final = "corpus-parametric-task-request-v1"
TASK_RESULT_SCHEMA: Final = "corpus-parametric-task-result-v2"
BATCH_COMPLETION_SCHEMA: Final = "corpus-parametric-batch-completion-v2"
ESTIMAND: Final = (
    "matched-world legal-feasibility generation under frozen "
    "admission/selector"
)
PUBLICATION_MODE: Final = "create_once"
SOLVE_ATTEMPTS_PER_BLOCK: Final = 200
WORLDS_PER_BLOCK: Final = 10_000
MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION: Final = 1_000
SELECTED_ENTRY_BUDGET: Final = 80
SOLVER_TIMEOUT_SECONDS: Final = 120
SOLVER_TIMEOUT_LAW: Final = (
    "one monotonic total deadline per parameter-set visit across all solver stages"
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
SOURCE_RECEIPT_ROLES: Final = ("later_source_freeze",)
TASK_WORLD_SOURCE_ROLES: Final = (
    "world_artifact_r0",
    "world_artifact_r1",
    "world_artifact_r2",
    "world_artifact_r3",
    "world_artifact_r4",
)

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_IMAGE_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")
_CANONICAL_ID: Final = re.compile(r"[a-z0-9][a-z0-9._:-]*")
_UTC_TIMESTAMP: Final = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
)

_PARAMETER_SPEC_BODY: Final = {
    "schema_version": PARAMETER_SPEC_SCHEMA,
    "parameters": [
        {
            "name": "min_lineup_salary",
            "json_type": "integer",
            "domain": [0, 49_000],
        },
        {
            "name": "qb_stack_min",
            "json_type": "integer",
            "domain": [0, 2],
        },
        {
            "name": "bring_back_min",
            "json_type": "integer",
            "domain": [0, 1],
        },
        {
            "name": "forbid_rb_vs_dst",
            "json_type": "boolean",
            "domain": [False, True],
        },
        {
            "name": "forbid_two_rb_same_team",
            "json_type": "boolean",
            "domain": [False, True],
        },
    ],
}

_FROZEN_ASSIGNMENTS: Final = (
    {
        "min_lineup_salary": 49_000,
        "qb_stack_min": 2,
        "bring_back_min": 1,
        "forbid_rb_vs_dst": True,
        "forbid_two_rb_same_team": True,
    },
    {
        "min_lineup_salary": 0,
        "qb_stack_min": 2,
        "bring_back_min": 1,
        "forbid_rb_vs_dst": True,
        "forbid_two_rb_same_team": True,
    },
    {
        "min_lineup_salary": 49_000,
        "qb_stack_min": 0,
        "bring_back_min": 1,
        "forbid_rb_vs_dst": True,
        "forbid_two_rb_same_team": True,
    },
    {
        "min_lineup_salary": 49_000,
        "qb_stack_min": 2,
        "bring_back_min": 0,
        "forbid_rb_vs_dst": True,
        "forbid_two_rb_same_team": True,
    },
    {
        "min_lineup_salary": 49_000,
        "qb_stack_min": 2,
        "bring_back_min": 1,
        "forbid_rb_vs_dst": False,
        "forbid_two_rb_same_team": True,
    },
    {
        "min_lineup_salary": 49_000,
        "qb_stack_min": 2,
        "bring_back_min": 1,
        "forbid_rb_vs_dst": True,
        "forbid_two_rb_same_team": False,
    },
    {
        "min_lineup_salary": 0,
        "qb_stack_min": 0,
        "bring_back_min": 0,
        "forbid_rb_vs_dst": False,
        "forbid_two_rb_same_team": False,
    },
)

_OBJECT_IDENTITY_KEYS: Final = frozenset({
    "uri", "generation", "sha256", "bytes",
})
_IMAGE_IDENTITY_KEYS: Final = frozenset({"uri", "digest"})
_TASK_INPUT_KEYS: Final = frozenset({
    "task_index",
    "slate_id",
    "season",
    "week",
    "result_receipt_uri",
    "variant_output_prefix",
    "world_artifact_receipts",
    "world_artifact_receipt_set_sha256",
    "artifact_source_authority_task_sha256",
})
_TASK_KEYS: Final = _TASK_INPUT_KEYS | {"task_sha256"}
_SOLVE_BUDGET_KEYS: Final = frozenset({
    "solve_attempts_per_seed",
    "worlds_per_block",
    "solver_timeout_seconds",
    "candidate_entry_budget",
    "selected_entry_budget",
})
_SOLVER_KEYS: Final = frozenset({
    "name",
    "version",
    "binary_sha256",
    "options_sha256",
    "exact_mode",
})
_RETRY_LAW_KEYS: Final = frozenset({
    "max_attempts_per_task", "max_retries",
})
_COMMON_LAW_KEYS: Final = frozenset({
    "code_source",
    "immutable_image",
    "source_receipts",
    "source_receipt_set_sha256",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion",
    "artifact_source_authority_completion_sha256",
    "effective_policy_inventory_identity",
    "effective_policy_inventory_sha256",
    "effective_policy_rule_universe_sha256",
    "effective_policy_inventory_source_set_sha256",
    "effective_policy_classified_input_projection_sha256",
    "world_schedule",
    "world_seed",
    "objective",
    "solve_budget",
    "generator_families",
    "unique_fill",
    "deduplication",
    "admission",
    "cbwu",
    "selector",
    "line_194",
    "exact_80",
    "solver",
    "retry_law",
    "fresh_model_state_per_parameter_set",
    "worker_environment_inheritance",
    "worker_graph_mutation",
})
_MECHANISM_RECEIPT_KEYS: Final = (
    "code_source",
    "world_schedule",
    "objective",
    "generator_families",
    "unique_fill",
    "deduplication",
    "admission",
    "cbwu",
    "selector",
    "line_194",
    "exact_80",
)
_EXECUTION_KEYS: Final = frozenset({
    "execution_id",
    "execution_uid",
    "task_index",
    "attempt",
    "retry_count",
    "terminal_status",
    "terminal_receipt",
})
_VARIANT_RESULT_KEYS: Final = frozenset({
    "ordinal",
    "parameter_set_id",
    "parameter_set_sha256",
    "effective_policy_receipt",
    "result_object",
})


class CorpusParametricBatchError(ValueError):
    """A fail-closed corpus parametric contract violation."""


def canonical_json_bytes(value: object) -> bytes:
    """Return canonical UTF-8 JSON bytes, rejecting non-finite values."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusParametricBatchError("value is not canonical JSON") from exc


def canonical_sha256(value: object) -> str:
    """Hash canonical JSON bytes."""
    return sha256(canonical_json_bytes(value)).hexdigest()


def parse_canonical_json_bytes(raw: bytes, *, label: str) -> object:
    """Parse one canonical JSON value with duplicate-key rejection."""

    def _duplicate_safe(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CorpusParametricBatchError(
                    f"{label} contains duplicate key {key!r}"
                )
            result[key] = value
        return result

    def _reject_constant(value: str) -> object:
        raise CorpusParametricBatchError(
            f"{label} contains non-finite number {value}"
        )

    if type(raw) is not bytes:
        raise CorpusParametricBatchError(f"{label} must be bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=_duplicate_safe,
            parse_constant=_reject_constant,
        )
    except CorpusParametricBatchError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusParametricBatchError(f"{label} is not valid JSON") from exc
    if canonical_json_bytes(value) != raw:
        raise CorpusParametricBatchError(f"{label} is not canonical JSON")
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusParametricBatchError(f"{label} must be an object")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = sorted(expected - actual)
        unknown = sorted(actual - expected)
        raise CorpusParametricBatchError(
            f"{label} keys differ; missing={missing}, unknown={unknown}"
        )


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CorpusParametricBatchError(f"{label} must be an array")
    return value


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusParametricBatchError(f"{label} must be a canonical string")
    return value


def _canonical_id(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _CANONICAL_ID.fullmatch(result) is None:
        raise CorpusParametricBatchError(f"{label} must be a canonical id")
    return result


def _sha256(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CorpusParametricBatchError(f"{label} must be a lowercase SHA-256")
    return value


def _exact_int(
    value: object, *, label: str, minimum: int | None = None,
) -> int:
    if type(value) is not int:
        raise CorpusParametricBatchError(f"{label} must be an exact integer")
    if minimum is not None and value < minimum:
        raise CorpusParametricBatchError(f"{label} must be >= {minimum}")
    return value


def _exact_bool(value: object, *, label: str) -> bool:
    if type(value) is not bool:
        raise CorpusParametricBatchError(f"{label} must be a literal Boolean")
    return value


def _utc_timestamp(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _UTC_TIMESTAMP.fullmatch(result) is None:
        raise CorpusParametricBatchError(
            f"{label} must be second-resolution UTC ending in Z"
        )
    return result


def _gcs_uri(value: object, *, label: str, prefix: bool = False) -> str:
    result = _string(value, label=label)
    tail = result.removeprefix("gs://")
    bucket, separator, object_name = tail.partition("/")
    if not result.startswith("gs://") or not bucket or not separator or not object_name:
        raise CorpusParametricBatchError(f"{label} must be a GCS object URI")
    if "//" in object_name:
        raise CorpusParametricBatchError(f"{label} is not canonical")
    if prefix:
        if not result.endswith("/"):
            raise CorpusParametricBatchError(f"{label} must end with /")
    elif result.endswith("/"):
        raise CorpusParametricBatchError(f"{label} must name an object")
    return result


def normalize_object_identity(value: object, *, label: str) -> dict[str, object]:
    """Validate the representation-free identity of one retained GCS object."""
    item = _mapping(value, label=label)
    _exact_keys(item, _OBJECT_IDENTITY_KEYS, label=label)
    uri = _gcs_uri(item["uri"], label=f"{label}.uri")
    generation = _string(item["generation"], label=f"{label}.generation")
    if _GENERATION.fullmatch(generation) is None:
        raise CorpusParametricBatchError(
            f"{label}.generation must be a positive decimal string"
        )
    digest = _sha256(item["sha256"], label=f"{label}.sha256")
    size = _exact_int(item["bytes"], label=f"{label}.bytes", minimum=1)
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": size,
    }


def normalize_image_identity(value: object, *, label: str) -> dict[str, str]:
    """Validate an immutable image URI whose suffix agrees with its digest."""
    item = _mapping(value, label=label)
    _exact_keys(item, _IMAGE_IDENTITY_KEYS, label=label)
    uri = _string(item["uri"], label=f"{label}.uri")
    digest = _string(item["digest"], label=f"{label}.digest")
    if _IMAGE_DIGEST.fullmatch(digest) is None:
        raise CorpusParametricBatchError(
            f"{label}.digest must be an immutable sha256 digest"
        )
    if not uri.endswith(f"@{digest}"):
        raise CorpusParametricBatchError(
            f"{label}.uri must end with the exact immutable digest"
        )
    return {"uri": uri, "digest": digest}


def object_identity_for_json(
    value: object, *, uri: str, generation: str,
) -> dict[str, object]:
    """Construct a generation-pinned identity for canonical JSON bytes.

    Supplying a generation is an assertion by the caller; this pure helper
    does not upload an object or claim that create-only publication occurred.
    """
    canonical_uri = _gcs_uri(uri, label="object identity uri")
    canonical_generation = _string(generation, label="object identity generation")
    if _GENERATION.fullmatch(canonical_generation) is None:
        raise CorpusParametricBatchError(
            "object identity generation must be a positive decimal string"
        )
    raw = canonical_json_bytes(value)
    return {
        "uri": canonical_uri,
        "generation": canonical_generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def validate_json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    """Require a retained-object identity to match canonical JSON bytes."""
    normalized = normalize_object_identity(identity, label=label)
    raw = canonical_json_bytes(value)
    if normalized["sha256"] != sha256(raw).hexdigest():
        raise CorpusParametricBatchError(f"{label} content SHA-256 differs")
    if normalized["bytes"] != len(raw):
        raise CorpusParametricBatchError(f"{label} byte count differs")
    return normalized


def parameter_spec_manifest() -> dict[str, object]:
    """Return the one versioned five-field allowlist with its self-hash."""
    result = deepcopy(_PARAMETER_SPEC_BODY)
    result["parameter_schema_sha256"] = canonical_sha256(result)
    return result


PARAMETER_SCHEMA_SHA256: Final = parameter_spec_manifest()[
    "parameter_schema_sha256"
]


def validate_parameter_spec_manifest(value: object) -> dict[str, object]:
    """Require exact equality with the frozen allowlist and its self-hash."""
    item = _mapping(value, label="parameter spec")
    expected = parameter_spec_manifest()
    _exact_keys(item, frozenset(expected), label="parameter spec")
    _sha256(
        item["parameter_schema_sha256"],
        label="parameter spec.parameter_schema_sha256",
    )
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        raise CorpusParametricBatchError(
            "parameter spec differs from the frozen five-field allowlist"
        )
    return expected


def validate_parameter_values(value: object) -> dict[str, object]:
    """Validate one complete assignment without defaults or coercion."""
    item = _mapping(value, label="parameter values")
    _exact_keys(item, frozenset(PARAMETER_ORDER), label="parameter values")
    result: dict[str, object] = {}
    specs = _PARAMETER_SPEC_BODY["parameters"]
    for spec in specs:
        name = spec["name"]
        candidate = item[name]
        if spec["json_type"] == "integer":
            normalized: object = _exact_int(candidate, label=f"parameter {name}")
        else:
            normalized = _exact_bool(candidate, label=f"parameter {name}")
        if not any(
            type(normalized) is type(allowed) and normalized == allowed
            for allowed in spec["domain"]
        ):
            raise CorpusParametricBatchError(
                f"parameter {name} is outside its frozen typed domain"
            )
        result[name] = normalized
    return result


def _build_parameter_set(
    *, ordinal: int, parameter_set_id: str, values: Mapping[str, object],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": PARAMETER_SET_SCHEMA,
        "ordinal": ordinal,
        "parameter_set_id": parameter_set_id,
        "parameter_schema_sha256": PARAMETER_SCHEMA_SHA256,
        "values": validate_parameter_values(values),
    }
    body["parameter_set_sha256"] = canonical_sha256(body)
    return body


def frozen_parameter_sets() -> tuple[dict[str, object], ...]:
    """Return the exact seven complete parameter assignments in run order."""
    return tuple(
        _build_parameter_set(
            ordinal=ordinal,
            parameter_set_id=parameter_set_id,
            values=values,
        )
        for ordinal, (parameter_set_id, values) in enumerate(
            zip(PARAMETER_SET_ORDER, _FROZEN_ASSIGNMENTS, strict=True)
        )
    )


def validate_parameter_set(value: object) -> dict[str, object]:
    """Validate one self-hashed member of the frozen seven-row matrix."""
    item = _mapping(value, label="parameter set")
    expected_keys = frozenset({
        "schema_version",
        "ordinal",
        "parameter_set_id",
        "parameter_schema_sha256",
        "values",
        "parameter_set_sha256",
    })
    _exact_keys(item, expected_keys, label="parameter set")
    ordinal = _exact_int(item["ordinal"], label="parameter set.ordinal", minimum=0)
    if ordinal >= len(PARAMETER_SET_ORDER):
        raise CorpusParametricBatchError("parameter set ordinal is outside the batch")
    parameter_set_id = _canonical_id(
        item["parameter_set_id"], label="parameter set.parameter_set_id"
    )
    expected = frozen_parameter_sets()[ordinal]
    if parameter_set_id != PARAMETER_SET_ORDER[ordinal]:
        raise CorpusParametricBatchError("parameter set id and ordinal disagree")
    _sha256(
        item["parameter_schema_sha256"],
        label="parameter set.parameter_schema_sha256",
    )
    _sha256(
        item["parameter_set_sha256"],
        label="parameter set.parameter_set_sha256",
    )
    validate_parameter_values(item["values"])
    body = {key: item[key] for key in item if key != "parameter_set_sha256"}
    if item["parameter_set_sha256"] != canonical_sha256(body):
        raise CorpusParametricBatchError("parameter set self-hash differs")
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        raise CorpusParametricBatchError(
            "parameter set differs from its frozen assignment"
        )
    return expected


def _normalize_solve_budget(value: object) -> dict[str, int]:
    item = _mapping(value, label="common law.solve_budget")
    _exact_keys(item, _SOLVE_BUDGET_KEYS, label="common law.solve_budget")
    result = {
        key: _exact_int(
            item[key], label=f"common law.solve_budget.{key}", minimum=1,
        )
        for key in _SOLVE_BUDGET_KEYS
    }
    exact_values = {
        "solve_attempts_per_seed": SOLVE_ATTEMPTS_PER_BLOCK,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "solver_timeout_seconds": SOLVER_TIMEOUT_SECONDS,
        "candidate_entry_budget": MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
        "selected_entry_budget": SELECTED_ENTRY_BUDGET,
    }
    for key, expected in exact_values.items():
        if result[key] == expected:
            continue
        if key == "solve_attempts_per_seed":
            detail = "200 visits per world-artifact block"
        elif key == "candidate_entry_budget":
            detail = (
                "1,000 maximum visit outputs before first-occurrence "
                "deduplication"
            )
        elif key == "solver_timeout_seconds":
            detail = (
                "120 seconds under the one-monotonic-total-deadline law "
                "per parameter-set visit"
            )
        elif key == "selected_entry_budget":
            detail = "exact-80"
        else:
            detail = "10,000 source worlds per block"
        raise CorpusParametricBatchError(
            f"common law.solve_budget.{key} must equal {detail}"
        )
    return result


def _normalize_solver(value: object) -> dict[str, object]:
    item = _mapping(value, label="common law.solver")
    _exact_keys(item, _SOLVER_KEYS, label="common law.solver")
    result: dict[str, object] = {
        "name": _string(item["name"], label="common law.solver.name"),
        "version": _string(item["version"], label="common law.solver.version"),
        "binary_sha256": _sha256(
            item["binary_sha256"], label="common law.solver.binary_sha256"
        ),
        "options_sha256": _sha256(
            item["options_sha256"], label="common law.solver.options_sha256"
        ),
        "exact_mode": _exact_bool(
            item["exact_mode"], label="common law.solver.exact_mode"
        ),
    }
    if result["exact_mode"] is not True:
        raise CorpusParametricBatchError("common law.solver.exact_mode must be true")
    return result


def _normalize_retry_law(value: object) -> dict[str, int]:
    item = _mapping(value, label="common law.retry_law")
    _exact_keys(item, _RETRY_LAW_KEYS, label="common law.retry_law")
    attempts = _exact_int(
        item["max_attempts_per_task"],
        label="common law.retry_law.max_attempts_per_task",
        minimum=1,
    )
    retries = _exact_int(
        item["max_retries"], label="common law.retry_law.max_retries", minimum=0,
    )
    if attempts != 1 or retries != 0:
        raise CorpusParametricBatchError(
            "v1 retry law must be exactly one attempt and zero retries"
        )
    return {"max_attempts_per_task": attempts, "max_retries": retries}


def normalize_common_law(value: object) -> dict[str, object]:
    """Validate every score-relevant field that variants must share."""
    item = _mapping(value, label="common law")
    _exact_keys(item, _COMMON_LAW_KEYS, label="common law")
    result: dict[str, object] = {}
    for key in _MECHANISM_RECEIPT_KEYS:
        result[key] = normalize_object_identity(
            item[key], label=f"common law.{key}"
        )
    source_values = _mapping(
        item["source_receipts"], label="common law.source_receipts"
    )
    _exact_keys(
        source_values,
        frozenset(SOURCE_RECEIPT_ROLES),
        label="common law.source_receipts",
    )
    sources = {
        role: normalize_object_identity(
            source_values[role], label=f"common law.source_receipts.{role}"
        )
        for role in SOURCE_RECEIPT_ROLES
    }
    result["source_receipts"] = sources
    source_set_sha256 = _sha256(
        item["source_receipt_set_sha256"],
        label="common law.source_receipt_set_sha256",
    )
    if source_set_sha256 != canonical_sha256(sources):
        raise CorpusParametricBatchError(
            "common law source-receipt-set hash differs"
        )
    result["source_receipt_set_sha256"] = source_set_sha256
    freeze_manifest_sha256 = _sha256(
        item["later_source_freeze_manifest_sha256"],
        label="common law.later_source_freeze_manifest_sha256",
    )
    if freeze_manifest_sha256 == sources["later_source_freeze"]["sha256"]:
        raise CorpusParametricBatchError(
            "later-source-freeze manifest and retained-object hashes "
            "must not be conflated"
        )
    result["later_source_freeze_manifest_sha256"] = freeze_manifest_sha256
    authority_completion = normalize_object_identity(
        item["artifact_source_authority_completion"],
        label="common law.artifact_source_authority_completion",
    )
    authority_completion_sha256 = _sha256(
        item["artifact_source_authority_completion_sha256"],
        label="common law.artifact_source_authority_completion_sha256",
    )
    if authority_completion_sha256 == authority_completion["sha256"]:
        raise CorpusParametricBatchError(
            "artifact-source-authority completion internal and retained-object "
            "hashes must not be conflated"
        )
    occupied_common_uris = {
        result[key]["uri"] for key in _MECHANISM_RECEIPT_KEYS
    }
    occupied_common_uris.update(
        identity["uri"] for identity in sources.values()
    )
    if authority_completion["uri"] in occupied_common_uris:
        raise CorpusParametricBatchError(
            "artifact-source-authority completion URI overlaps a common source"
        )
    result["artifact_source_authority_completion"] = authority_completion
    result["artifact_source_authority_completion_sha256"] = (
        authority_completion_sha256
    )
    result["effective_policy_inventory_identity"] = normalize_object_identity(
        item["effective_policy_inventory_identity"],
        label="common law.effective_policy_inventory_identity",
    )
    if (
        result["effective_policy_inventory_identity"]["uri"]
        == authority_completion["uri"]
    ):
        raise CorpusParametricBatchError(
            "artifact-source-authority completion URI overlaps policy inventory"
        )
    for key in (
        "effective_policy_inventory_sha256",
        "effective_policy_rule_universe_sha256",
        "effective_policy_inventory_source_set_sha256",
        "effective_policy_classified_input_projection_sha256",
    ):
        result[key] = _sha256(item[key], label=f"common law.{key}")
    result["immutable_image"] = normalize_image_identity(
        item["immutable_image"], label="common law.immutable_image"
    )
    result["world_seed"] = _exact_int(
        item["world_seed"], label="common law.world_seed", minimum=0
    )
    result["solve_budget"] = _normalize_solve_budget(item["solve_budget"])
    result["solver"] = _normalize_solver(item["solver"])
    result["retry_law"] = _normalize_retry_law(item["retry_law"])
    result["fresh_model_state_per_parameter_set"] = _exact_bool(
        item["fresh_model_state_per_parameter_set"],
        label="common law.fresh_model_state_per_parameter_set",
    )
    result["worker_environment_inheritance"] = _exact_bool(
        item["worker_environment_inheritance"],
        label="common law.worker_environment_inheritance",
    )
    result["worker_graph_mutation"] = _exact_bool(
        item["worker_graph_mutation"], label="common law.worker_graph_mutation"
    )
    required_booleans = {
        "fresh_model_state_per_parameter_set": True,
        "worker_environment_inheritance": False,
        "worker_graph_mutation": False,
    }
    for key, expected in required_booleans.items():
        if result[key] is not expected:
            raise CorpusParametricBatchError(
                f"common law.{key} must be literal {str(expected).lower()}"
            )
    return result


def _require_strict_descendant(
    value: str, *, parent: str, label: str,
) -> None:
    if value == parent or not value.startswith(parent):
        raise CorpusParametricBatchError(
            f"{label} must be strictly under the batch output prefix"
        )


def _output_prefix_for_batch(value: object, *, batch_id: str) -> str:
    result = _gcs_uri(value, label="output_prefix", prefix=True)
    if not result.endswith(f"/{batch_id}/"):
        raise CorpusParametricBatchError(
            "output_prefix must end with the exact batch_id"
        )
    return result


def _validate_input_namespace(
    common_law: Mapping[str, object], *, output_prefix: str,
) -> None:
    identities = [
        common_law[key] for key in _MECHANISM_RECEIPT_KEYS
    ]
    identities.extend(common_law["source_receipts"].values())
    identities.append(common_law["effective_policy_inventory_identity"])
    identities.append(common_law["artifact_source_authority_completion"])
    for identity in identities:
        uri = identity["uri"]
        if _artifact_namespace_overlaps(uri, output_prefix=output_prefix):
            raise CorpusParametricBatchError(
                "source/common artifact namespace overlaps batch output_prefix"
            )


def _artifact_namespace_overlaps(uri: str, *, output_prefix: str) -> bool:
    return uri.startswith(output_prefix) or output_prefix.startswith(f"{uri}/")


def _normalize_world_artifact_receipts(
    value: object, *, task_index: int, output_prefix: str,
) -> dict[str, dict[str, object]]:
    item = _mapping(
        value, label=f"task[{task_index}].world_artifact_receipts"
    )
    _exact_keys(
        item,
        frozenset(TASK_WORLD_SOURCE_ROLES),
        label=f"task[{task_index}].world_artifact_receipts",
    )
    result = {
        role: normalize_object_identity(
            item[role],
            label=f"task[{task_index}].world_artifact_receipts.{role}",
        )
        for role in TASK_WORLD_SOURCE_ROLES
    }
    uris = [identity["uri"] for identity in result.values()]
    if len(set(uris)) != len(uris):
        raise CorpusParametricBatchError(
            f"task[{task_index}] world artifact URIs repeat"
        )
    if any(
        _artifact_namespace_overlaps(uri, output_prefix=output_prefix)
        for uri in uris
    ):
        raise CorpusParametricBatchError(
            "task world artifact namespace overlaps batch output_prefix"
        )
    return result


def _normalize_task_input(
    value: object, *, expected_index: int, output_prefix: str,
) -> dict[str, object]:
    item = _mapping(value, label=f"task[{expected_index}]")
    _exact_keys(item, _TASK_INPUT_KEYS, label=f"task[{expected_index}]")
    task_index = _exact_int(
        item["task_index"], label=f"task[{expected_index}].task_index", minimum=0
    )
    if task_index != expected_index:
        raise CorpusParametricBatchError("task indexes must be contiguous from zero")
    result_receipt_uri = _gcs_uri(
        item["result_receipt_uri"],
        label=f"task[{expected_index}].result_receipt_uri",
    )
    variant_output_prefix = _gcs_uri(
        item["variant_output_prefix"],
        label=f"task[{expected_index}].variant_output_prefix",
        prefix=True,
    )
    _require_strict_descendant(
        result_receipt_uri,
        parent=output_prefix,
        label=f"task[{expected_index}].result_receipt_uri",
    )
    _require_strict_descendant(
        variant_output_prefix,
        parent=output_prefix,
        label=f"task[{expected_index}].variant_output_prefix",
    )
    if result_receipt_uri.startswith(variant_output_prefix):
        raise CorpusParametricBatchError(
            "task result receipt may not occupy the variant output prefix"
        )
    world_artifacts = _normalize_world_artifact_receipts(
        item["world_artifact_receipts"],
        task_index=expected_index,
        output_prefix=output_prefix,
    )
    world_artifact_set_sha256 = _sha256(
        item["world_artifact_receipt_set_sha256"],
        label=f"task[{expected_index}].world_artifact_receipt_set_sha256",
    )
    if world_artifact_set_sha256 != canonical_sha256(world_artifacts):
        raise CorpusParametricBatchError(
            f"task[{expected_index}] world-artifact-set hash differs"
        )
    authority_task_sha256 = _sha256(
        item["artifact_source_authority_task_sha256"],
        label=(
            f"task[{expected_index}].artifact_source_authority_task_sha256"
        ),
    )
    body: dict[str, object] = {
        "task_index": task_index,
        "slate_id": _canonical_id(
            item["slate_id"], label=f"task[{expected_index}].slate_id"
        ),
        "season": _exact_int(
            item["season"], label=f"task[{expected_index}].season", minimum=2000
        ),
        "week": _exact_int(
            item["week"], label=f"task[{expected_index}].week", minimum=1
        ),
        "result_receipt_uri": result_receipt_uri,
        "variant_output_prefix": variant_output_prefix,
        "world_artifact_receipts": world_artifacts,
        "world_artifact_receipt_set_sha256": world_artifact_set_sha256,
        "artifact_source_authority_task_sha256": authority_task_sha256,
    }
    body["task_sha256"] = canonical_sha256(body)
    return body


def _validate_task_collection(
    tasks: Sequence[Mapping[str, object]], *, output_prefix: str,
) -> None:
    identities = [(task["slate_id"], task["season"], task["week"]) for task in tasks]
    if len(set(identities)) != len(identities):
        raise CorpusParametricBatchError("tasks repeat a slate identity")
    result_uris = [task["result_receipt_uri"] for task in tasks]
    prefixes = [task["variant_output_prefix"] for task in tasks]
    governance_prefix = f"{output_prefix}governance/"
    if any(
        uri.startswith(governance_prefix)
        for uri in (*result_uris, *prefixes)
    ):
        raise CorpusParametricBatchError(
            "task artifact namespace overlaps batch governance"
        )
    if len(set(result_uris)) != len(result_uris):
        raise CorpusParametricBatchError("tasks repeat a result receipt URI")
    if len(set(prefixes)) != len(prefixes):
        raise CorpusParametricBatchError("tasks repeat a variant output prefix")
    for left_index, left in enumerate(prefixes):
        for right in prefixes[left_index + 1:]:
            if left.startswith(right) or right.startswith(left):
                raise CorpusParametricBatchError(
                    "task variant output prefixes overlap"
                )
    for result_uri in result_uris:
        if any(result_uri.startswith(prefix) for prefix in prefixes):
            raise CorpusParametricBatchError(
                "task result receipt crosses into a variant output prefix"
            )


def _normalize_tasks(
    value: object, *, output_prefix: str,
) -> list[dict[str, object]]:
    items = _sequence(value, label="tasks")
    if not items:
        raise CorpusParametricBatchError("tasks is empty")
    tasks = [
        _normalize_task_input(
            item, expected_index=index, output_prefix=output_prefix
        )
        for index, item in enumerate(items)
    ]
    _validate_task_collection(tasks, output_prefix=output_prefix)
    return tasks


def _validate_task(
    value: object, *, expected_index: int, output_prefix: str,
) -> dict[str, object]:
    item = _mapping(value, label=f"task[{expected_index}]")
    _exact_keys(item, _TASK_KEYS, label=f"task[{expected_index}]")
    raw = {key: item[key] for key in _TASK_INPUT_KEYS}
    expected = _normalize_task_input(
        raw, expected_index=expected_index, output_prefix=output_prefix
    )
    _sha256(item["task_sha256"], label=f"task[{expected_index}].task_sha256")
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        raise CorpusParametricBatchError(f"task[{expected_index}] self-hash differs")
    return expected


def build_batch_manifest(
    *,
    batch_id: str,
    created_at_utc: str,
    output_prefix: str,
    common_law: Mapping[str, object],
    tasks: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the frozen seven-setting manifest without any implicit value."""
    normalized_common_law = normalize_common_law(common_law)
    common_law_sha256 = canonical_sha256(normalized_common_law)
    normalized_batch_id = _canonical_id(batch_id, label="batch_id")
    normalized_output_prefix = _output_prefix_for_batch(
        output_prefix, batch_id=normalized_batch_id
    )
    _validate_input_namespace(
        normalized_common_law, output_prefix=normalized_output_prefix
    )
    body: dict[str, object] = {
        "schema_version": BATCH_MANIFEST_SCHEMA,
        "batch_id": normalized_batch_id,
        "created_at_utc": _utc_timestamp(created_at_utc, label="created_at_utc"),
        "estimand": ESTIMAND,
        "publication_mode": PUBLICATION_MODE,
        "output_prefix": normalized_output_prefix,
        "manifest_uri": (
            f"{normalized_output_prefix}governance/batch-manifest.json"
        ),
        "create_once_prefix_claim_uri": (
            f"{normalized_output_prefix}governance/prefix-claim.json"
        ),
        "parameter_spec": parameter_spec_manifest(),
        "parameter_sets": list(frozen_parameter_sets()),
        "common_law": normalized_common_law,
        "common_law_sha256": common_law_sha256,
        "tasks": _normalize_tasks(tasks, output_prefix=normalized_output_prefix),
    }
    body["batch_manifest_sha256"] = canonical_sha256(body)
    return body


def validate_batch_manifest(value: object) -> dict[str, object]:
    """Validate a manifest, including all nested hashes and exact cardinality."""
    item = _mapping(value, label="batch manifest")
    keys = frozenset({
        "schema_version",
        "batch_id",
        "created_at_utc",
        "estimand",
        "publication_mode",
        "output_prefix",
        "manifest_uri",
        "create_once_prefix_claim_uri",
        "parameter_spec",
        "parameter_sets",
        "common_law",
        "common_law_sha256",
        "tasks",
        "batch_manifest_sha256",
    })
    _exact_keys(item, keys, label="batch manifest")
    if item["schema_version"] != BATCH_MANIFEST_SCHEMA:
        raise CorpusParametricBatchError("batch manifest schema differs")
    batch_id = _canonical_id(item["batch_id"], label="batch manifest.batch_id")
    created_at = _utc_timestamp(
        item["created_at_utc"], label="batch manifest.created_at_utc"
    )
    if item["estimand"] != ESTIMAND:
        raise CorpusParametricBatchError("batch manifest estimand differs")
    if item["publication_mode"] != PUBLICATION_MODE:
        raise CorpusParametricBatchError("batch manifest must be create_once")
    output_prefix = _output_prefix_for_batch(
        item["output_prefix"], batch_id=batch_id
    )
    manifest_uri = _gcs_uri(
        item["manifest_uri"], label="batch manifest.manifest_uri"
    )
    expected_manifest_uri = f"{output_prefix}governance/batch-manifest.json"
    if manifest_uri != expected_manifest_uri:
        raise CorpusParametricBatchError(
            "batch manifest URI differs from its deterministic path"
        )
    prefix_claim_uri = _gcs_uri(
        item["create_once_prefix_claim_uri"],
        label="batch manifest.create_once_prefix_claim_uri",
    )
    expected_claim_uri = f"{output_prefix}governance/prefix-claim.json"
    if prefix_claim_uri != expected_claim_uri:
        raise CorpusParametricBatchError(
            "batch prefix-claim URI differs from its deterministic path"
        )
    parameter_spec = validate_parameter_spec_manifest(item["parameter_spec"])
    set_values = _sequence(item["parameter_sets"], label="parameter sets")
    if len(set_values) != len(PARAMETER_SET_ORDER):
        raise CorpusParametricBatchError(
            "batch must contain exactly seven parameter sets"
        )
    parameter_sets = [validate_parameter_set(value) for value in set_values]
    if [row["ordinal"] for row in parameter_sets] != list(range(7)):
        raise CorpusParametricBatchError("parameter sets are not in fixed order")
    common_law = normalize_common_law(item["common_law"])
    _validate_input_namespace(common_law, output_prefix=output_prefix)
    common_hash = _sha256(
        item["common_law_sha256"], label="batch manifest.common_law_sha256"
    )
    if common_hash != canonical_sha256(common_law):
        raise CorpusParametricBatchError("batch common-law hash differs")
    task_values = _sequence(item["tasks"], label="tasks")
    if not task_values:
        raise CorpusParametricBatchError("tasks is empty")
    tasks = [
        _validate_task(
            task, expected_index=index, output_prefix=output_prefix
        )
        for index, task in enumerate(task_values)
    ]
    _validate_task_collection(tasks, output_prefix=output_prefix)
    retained_hash = _sha256(
        item["batch_manifest_sha256"],
        label="batch manifest.batch_manifest_sha256",
    )
    body = {key: item[key] for key in item if key != "batch_manifest_sha256"}
    if retained_hash != canonical_sha256(body):
        raise CorpusParametricBatchError("batch manifest self-hash differs")
    return {
        "schema_version": BATCH_MANIFEST_SCHEMA,
        "batch_id": batch_id,
        "created_at_utc": created_at,
        "estimand": ESTIMAND,
        "publication_mode": PUBLICATION_MODE,
        "output_prefix": output_prefix,
        "manifest_uri": manifest_uri,
        "create_once_prefix_claim_uri": prefix_claim_uri,
        "parameter_spec": parameter_spec,
        "parameter_sets": parameter_sets,
        "common_law": common_law,
        "common_law_sha256": common_hash,
        "tasks": tasks,
        "batch_manifest_sha256": retained_hash,
    }


def _validated_manifest_identity(
    manifest: Mapping[str, object], identity: object,
) -> dict[str, object]:
    normalized = validate_json_identity(
        manifest, identity, label="batch manifest identity"
    )
    if normalized["uri"] != manifest["manifest_uri"]:
        raise CorpusParametricBatchError(
            "batch manifest identity URI differs from the frozen manifest URI"
        )
    return normalized


def build_task_request(
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
    task_index: int,
) -> dict[str, object]:
    """Build the complete worker input: manifest identity plus task index."""
    manifest = validate_batch_manifest(batch_manifest)
    identity = _validated_manifest_identity(manifest, batch_manifest_identity)
    index = _exact_int(task_index, label="task request.task_index", minimum=0)
    if index >= len(manifest["tasks"]):
        raise CorpusParametricBatchError("task request index is outside the batch")
    body: dict[str, object] = {
        "schema_version": TASK_REQUEST_SCHEMA,
        "batch_manifest_identity": identity,
        "task_index": index,
    }
    body["task_request_sha256"] = canonical_sha256(body)
    return body


def validate_task_request(value: object) -> dict[str, object]:
    """Validate a worker request without loading or defaulting the manifest."""
    item = _mapping(value, label="task request")
    keys = frozenset({
        "schema_version",
        "batch_manifest_identity",
        "task_index",
        "task_request_sha256",
    })
    _exact_keys(item, keys, label="task request")
    if item["schema_version"] != TASK_REQUEST_SCHEMA:
        raise CorpusParametricBatchError("task request schema differs")
    identity = normalize_object_identity(
        item["batch_manifest_identity"], label="task request manifest identity"
    )
    index = _exact_int(item["task_index"], label="task request.task_index", minimum=0)
    retained_hash = _sha256(
        item["task_request_sha256"], label="task request.task_request_sha256"
    )
    body = {key: item[key] for key in item if key != "task_request_sha256"}
    if retained_hash != canonical_sha256(body):
        raise CorpusParametricBatchError("task request self-hash differs")
    return {
        "schema_version": TASK_REQUEST_SCHEMA,
        "batch_manifest_identity": identity,
        "task_index": index,
        "task_request_sha256": retained_hash,
    }


def bind_task_request_to_manifest(
    request: object, manifest_raw: bytes,
) -> tuple[dict[str, object], dict[str, object]]:
    """Bind a minimal request to the exact canonical manifest it identifies."""
    normalized_request = validate_task_request(request)
    parsed = parse_canonical_json_bytes(manifest_raw, label="batch manifest")
    manifest = validate_batch_manifest(parsed)
    _validated_manifest_identity(
        manifest, normalized_request["batch_manifest_identity"]
    )
    if normalized_request["task_index"] >= len(manifest["tasks"]):
        raise CorpusParametricBatchError("task request index is outside the batch")
    return normalized_request, manifest


def _normalize_execution(value: object, *, task_index: int) -> dict[str, object]:
    item = _mapping(value, label="execution")
    _exact_keys(item, _EXECUTION_KEYS, label="execution")
    retained_index = _exact_int(
        item["task_index"], label="execution.task_index", minimum=0
    )
    if retained_index != task_index:
        raise CorpusParametricBatchError("execution task index differs")
    attempt = _exact_int(item["attempt"], label="execution.attempt", minimum=1)
    retry_count = _exact_int(
        item["retry_count"], label="execution.retry_count", minimum=0
    )
    terminal_status = _string(
        item["terminal_status"], label="execution.terminal_status"
    )
    if terminal_status != "succeeded":
        raise CorpusParametricBatchError("execution must be terminal succeeded")
    return {
        "execution_id": _canonical_id(
            item["execution_id"], label="execution.execution_id"
        ),
        "execution_uid": _string(
            item["execution_uid"], label="execution.execution_uid"
        ),
        "task_index": retained_index,
        "attempt": attempt,
        "retry_count": retry_count,
        "terminal_status": terminal_status,
        "terminal_receipt": normalize_object_identity(
            item["terminal_receipt"], label="execution.terminal_receipt"
        ),
    }


def _normalize_variant_results(
    value: object,
    *,
    manifest: Mapping[str, object],
    task: Mapping[str, object],
) -> list[dict[str, object]]:
    rows = _sequence(value, label="variant results")
    parameter_sets = manifest["parameter_sets"]
    if len(rows) != len(parameter_sets):
        raise CorpusParametricBatchError(
            "task result must contain exactly seven variant results"
        )
    normalized: list[dict[str, object]] = []
    seen_uris: set[str] = set()
    for ordinal, (row_value, parameter_set) in enumerate(
        zip(rows, parameter_sets, strict=True)
    ):
        row = _mapping(row_value, label=f"variant result[{ordinal}]")
        _exact_keys(row, _VARIANT_RESULT_KEYS, label=f"variant result[{ordinal}]")
        retained_ordinal = _exact_int(
            row["ordinal"], label=f"variant result[{ordinal}].ordinal", minimum=0
        )
        if retained_ordinal != ordinal:
            raise CorpusParametricBatchError("variant results are not in fixed order")
        parameter_set_id = _canonical_id(
            row["parameter_set_id"],
            label=f"variant result[{ordinal}].parameter_set_id",
        )
        parameter_set_sha256 = _sha256(
            row["parameter_set_sha256"],
            label=f"variant result[{ordinal}].parameter_set_sha256",
        )
        if (
            parameter_set_id != parameter_set["parameter_set_id"]
            or parameter_set_sha256 != parameter_set["parameter_set_sha256"]
        ):
            raise CorpusParametricBatchError(
                "variant result parameter-set binding differs"
            )
        effective_policy = normalize_object_identity(
            row["effective_policy_receipt"],
            label=f"variant result[{ordinal}].effective_policy_receipt",
        )
        result_object = normalize_object_identity(
            row["result_object"], label=f"variant result[{ordinal}].result_object"
        )
        if not effective_policy["uri"].startswith(task["variant_output_prefix"]):
            raise CorpusParametricBatchError(
                "variant effective-policy receipt is outside its frozen "
                "output prefix"
            )
        if not result_object["uri"].startswith(task["variant_output_prefix"]):
            raise CorpusParametricBatchError(
                "variant result object is outside its frozen output prefix"
            )
        for uri in (effective_policy["uri"], result_object["uri"]):
            if uri in seen_uris:
                raise CorpusParametricBatchError(
                    "variant effective-policy/result URIs repeat"
                )
            seen_uris.add(uri)
        variant_prefix = (
            f"{task['variant_output_prefix']}{parameter_set_id}/"
        )
        if effective_policy["uri"] != f"{variant_prefix}effective-policy.json":
            raise CorpusParametricBatchError(
                "variant effective-policy URI differs from its deterministic path"
            )
        if result_object["uri"] != f"{variant_prefix}result.json":
            raise CorpusParametricBatchError(
                "variant result URI differs from its deterministic path"
            )
        normalized.append({
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "parameter_set_sha256": parameter_set_sha256,
            "effective_policy_receipt": effective_policy,
            "result_object": result_object,
        })
    return normalized


def build_task_result_receipt(
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
    task_index: int,
    execution: Mapping[str, object],
    variant_results: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build a successful all-seven result binding for one slate task."""
    manifest = validate_batch_manifest(batch_manifest)
    identity = _validated_manifest_identity(manifest, batch_manifest_identity)
    index = _exact_int(task_index, label="task result.task_index", minimum=0)
    if index >= len(manifest["tasks"]):
        raise CorpusParametricBatchError("task result index is outside the batch")
    task = manifest["tasks"][index]
    normalized_execution = _normalize_execution(execution, task_index=index)
    retry_law = manifest["common_law"]["retry_law"]
    if (
        normalized_execution["attempt"] > retry_law["max_attempts_per_task"]
        or normalized_execution["retry_count"] > retry_law["max_retries"]
        or normalized_execution["attempt"]
        != normalized_execution["retry_count"] + 1
    ):
        raise CorpusParametricBatchError("execution exceeds the frozen retry law")
    normalized_variants = _normalize_variant_results(
        variant_results, manifest=manifest, task=task
    )
    common_law = manifest["common_law"]
    body: dict[str, object] = {
        "schema_version": TASK_RESULT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "batch_manifest_identity": identity,
        "batch_id": manifest["batch_id"],
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "parameter_schema_sha256": PARAMETER_SCHEMA_SHA256,
        "common_law_sha256": manifest["common_law_sha256"],
        "task_index": index,
        "task_sha256": task["task_sha256"],
        "slate_id": task["slate_id"],
        "world_artifact_receipts": task["world_artifact_receipts"],
        "world_artifact_receipt_set_sha256": task[
            "world_artifact_receipt_set_sha256"
        ],
        "artifact_source_authority_task_sha256": task[
            "artifact_source_authority_task_sha256"
        ],
        "code_source": common_law["code_source"],
        "immutable_image": common_law["immutable_image"],
        "source_receipts": common_law["source_receipts"],
        "source_receipt_set_sha256": common_law["source_receipt_set_sha256"],
        "later_source_freeze_manifest_sha256": common_law[
            "later_source_freeze_manifest_sha256"
        ],
        "artifact_source_authority_completion": common_law[
            "artifact_source_authority_completion"
        ],
        "artifact_source_authority_completion_sha256": common_law[
            "artifact_source_authority_completion_sha256"
        ],
        "effective_policy_inventory_identity": common_law[
            "effective_policy_inventory_identity"
        ],
        "effective_policy_inventory_sha256": common_law[
            "effective_policy_inventory_sha256"
        ],
        "effective_policy_rule_universe_sha256": common_law[
            "effective_policy_rule_universe_sha256"
        ],
        "effective_policy_inventory_source_set_sha256": common_law[
            "effective_policy_inventory_source_set_sha256"
        ],
        "effective_policy_classified_input_projection_sha256": common_law[
            "effective_policy_classified_input_projection_sha256"
        ],
        "world_schedule": common_law["world_schedule"],
        "world_seed": common_law["world_seed"],
        "solver": common_law["solver"],
        "execution": normalized_execution,
        "variant_results": normalized_variants,
    }
    body["task_result_sha256"] = canonical_sha256(body)
    return body


def validate_task_result_receipt(
    value: object,
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
) -> dict[str, object]:
    """Replay one task binding against its exact batch manifest."""
    item = _mapping(value, label="task result")
    keys = frozenset({
        "schema_version",
        "publication_mode",
        "batch_manifest_identity",
        "batch_id",
        "batch_manifest_sha256",
        "parameter_schema_sha256",
        "common_law_sha256",
        "task_index",
        "task_sha256",
        "slate_id",
        "world_artifact_receipts",
        "world_artifact_receipt_set_sha256",
        "artifact_source_authority_task_sha256",
        "code_source",
        "immutable_image",
        "source_receipts",
        "source_receipt_set_sha256",
        "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion",
        "artifact_source_authority_completion_sha256",
        "effective_policy_inventory_identity",
        "effective_policy_inventory_sha256",
        "effective_policy_rule_universe_sha256",
        "effective_policy_inventory_source_set_sha256",
        "effective_policy_classified_input_projection_sha256",
        "world_schedule",
        "world_seed",
        "solver",
        "execution",
        "variant_results",
        "task_result_sha256",
    })
    _exact_keys(item, keys, label="task result")
    retained_hash = _sha256(
        item["task_result_sha256"], label="task result.task_result_sha256"
    )
    body = {key: item[key] for key in item if key != "task_result_sha256"}
    if retained_hash != canonical_sha256(body):
        raise CorpusParametricBatchError("task result self-hash differs")
    rebuilt = build_task_result_receipt(
        batch_manifest=batch_manifest,
        batch_manifest_identity=batch_manifest_identity,
        task_index=_exact_int(
            item["task_index"], label="task result.task_index", minimum=0
        ),
        execution=_mapping(item["execution"], label="task result.execution"),
        variant_results=_sequence(
            item["variant_results"], label="task result.variant_results"
        ),
    )
    if canonical_json_bytes(item) != canonical_json_bytes(rebuilt):
        raise CorpusParametricBatchError(
            "task result binding differs from the frozen batch"
        )
    return rebuilt


def build_batch_completion_receipt(
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
    retained_task_results: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build terminal coverage evidence for every task-by-variant cell.

    Each input row must contain exactly ``receipt`` and ``object_identity``.
    The latter must match the canonical receipt bytes and the task's frozen
    result-receipt URI.  Missing, duplicated, reordered, or drifted task
    results are fatal.
    """
    manifest = validate_batch_manifest(batch_manifest)
    identity = _validated_manifest_identity(manifest, batch_manifest_identity)
    rows = _sequence(retained_task_results, label="retained task results")
    if len(rows) != len(manifest["tasks"]):
        raise CorpusParametricBatchError(
            "retained task results do not cover every batch task"
        )
    result_bindings: list[dict[str, object]] = []
    seen_objects: set[tuple[object, ...]] = set()
    for task_index, (row_value, task) in enumerate(
        zip(rows, manifest["tasks"], strict=True)
    ):
        row = _mapping(row_value, label=f"retained task result[{task_index}]")
        _exact_keys(
            row,
            frozenset({"receipt", "object_identity"}),
            label=f"retained task result[{task_index}]",
        )
        receipt = validate_task_result_receipt(
            row["receipt"],
            batch_manifest=manifest,
            batch_manifest_identity=identity,
        )
        if receipt["task_index"] != task_index:
            raise CorpusParametricBatchError(
                "retained task results are not in fixed task order"
            )
        object_identity = validate_json_identity(
            receipt,
            row["object_identity"],
            label=f"retained task result[{task_index}].object_identity",
        )
        if object_identity["uri"] != task["result_receipt_uri"]:
            raise CorpusParametricBatchError(
                "task result receipt URI differs from the frozen task"
            )
        object_key = tuple(object_identity[key] for key in (
            "uri", "generation", "sha256", "bytes",
        ))
        if object_key in seen_objects:
            raise CorpusParametricBatchError("retained task result objects repeat")
        seen_objects.add(object_key)
        result_bindings.append({
            "task_index": task_index,
            "task_sha256": task["task_sha256"],
            "artifact_source_authority_task_sha256": task[
                "artifact_source_authority_task_sha256"
            ],
            "world_artifact_receipt_set_sha256": task[
                "world_artifact_receipt_set_sha256"
            ],
            "task_result_sha256": receipt["task_result_sha256"],
            "task_result_object": object_identity,
        })
    body: dict[str, object] = {
        "schema_version": BATCH_COMPLETION_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "batch_manifest_identity": identity,
        "batch_id": manifest["batch_id"],
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "parameter_schema_sha256": PARAMETER_SCHEMA_SHA256,
        "common_law_sha256": manifest["common_law_sha256"],
        "later_source_freeze_manifest_sha256": manifest["common_law"][
            "later_source_freeze_manifest_sha256"
        ],
        "artifact_source_authority_completion": manifest["common_law"][
            "artifact_source_authority_completion"
        ],
        "artifact_source_authority_completion_sha256": manifest["common_law"][
            "artifact_source_authority_completion_sha256"
        ],
        "effective_policy_classified_input_projection_sha256": manifest[
            "common_law"
        ]["effective_policy_classified_input_projection_sha256"],
        "coverage": {
            "task_count": len(manifest["tasks"]),
            "parameter_set_count": len(PARAMETER_SET_ORDER),
            "matrix_cell_count": len(manifest["tasks"]) * len(PARAMETER_SET_ORDER),
            "complete": True,
        },
        "task_results": result_bindings,
    }
    body["batch_completion_sha256"] = canonical_sha256(body)
    return body


def validate_batch_completion_receipt(
    value: object,
    *,
    batch_manifest: Mapping[str, object],
    batch_manifest_identity: Mapping[str, object],
    retained_task_results: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Replay a completion self-hash and complete result matrix."""
    item = _mapping(value, label="batch completion")
    expected_keys = frozenset({
        "schema_version",
        "publication_mode",
        "batch_manifest_identity",
        "batch_id",
        "batch_manifest_sha256",
        "parameter_schema_sha256",
        "common_law_sha256",
        "later_source_freeze_manifest_sha256",
        "artifact_source_authority_completion",
        "artifact_source_authority_completion_sha256",
        "effective_policy_classified_input_projection_sha256",
        "coverage",
        "task_results",
        "batch_completion_sha256",
    })
    _exact_keys(item, expected_keys, label="batch completion")
    retained_hash = _sha256(
        item["batch_completion_sha256"],
        label="batch completion.batch_completion_sha256",
    )
    body = {key: item[key] for key in item if key != "batch_completion_sha256"}
    if retained_hash != canonical_sha256(body):
        raise CorpusParametricBatchError("batch completion self-hash differs")
    rebuilt = build_batch_completion_receipt(
        batch_manifest=batch_manifest,
        batch_manifest_identity=batch_manifest_identity,
        retained_task_results=retained_task_results,
    )
    if canonical_json_bytes(item) != canonical_json_bytes(rebuilt):
        raise CorpusParametricBatchError(
            "batch completion differs from the replayed result matrix"
        )
    return rebuilt
