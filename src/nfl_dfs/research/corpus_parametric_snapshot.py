"""Generation-pinned reader and science comparator for parametric tasks.

This module reopens the seven per-arm variant results named by a self-hashed
carrier object (the producer worker completion or the closed task result),
validates every byte against its pinned identity and canonical self-hash,
and projects the IMAGE-INVARIANT science subset of an accepted task: slate
identity, source-artifact identities, visit schedule hash, arm profiles,
visit rosters, first-occurrence unions, cross-score matrix hashes, exact-80
selector receipts, selected books, coverage counts, and house-rule censuses.

Two accepted tasks over the same slate, sources, and registered schedule are
SCIENCE-EQUIVALENT when that subset is identical, regardless of image, build,
inventory, wall-clock, or law-binding hashes, which necessarily differ across
rebuilds and are explicitly excluded and enumerated in every receipt.

The comparator writes the machine-readable receipt consumed by the Foundry
batch driver's fan-out gate (`equivalent=true`, `comparison="science-only"`).

FREEZE GATE: before its first production use, this module must pass one
outcome-blind reality smoke against the real accepted v4 task-0 artifacts;
synthetic-fixture validation alone does not license the gate (frozen-chain
lesson 1). It reads no realized outcome and carries no promotion authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from typing import Final

from nfl_dfs.research.corpus_legal_feasibility import (
    VARIANT_RESULT_SCHEMA,
    canonical_json_bytes,
    canonical_sha256,
)
from nfl_dfs.research.corpus_parametric_batch import (
    MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
    PARAMETER_SET_ORDER,
    SELECTED_ENTRY_BUDGET,
)


SCIENCE_PROJECTION_SCHEMA: Final = (
    "corpus-parametric-task-science-projection/v1"
)
EQUIVALENCE_RECEIPT_SCHEMA: Final = (
    "corpus-parametric-task-science-equivalence/v1"
)

_SHA_LENGTH: Final = 64

VARIANT_RESULT_KEYS: Final = frozenset({
    "schema", "slate", "later_source_freeze_manifest_sha256",
    "artifact_sha256_by_block", "task_source_binding",
    "visit_schedule_sha256", "attempt_ledger_sha256",
    "matrix_authority_sha256", "solver_evidence_task_root_sha256",
    "profile", "runtime_effective_policy", "coverage",
    "variant_attempt_rows_sha256", "visit_rosters", "unique_rosters",
    "first_occurrence_visit_indices", "candidate_score_sha256", "selector",
    "selected_rosters", "selected_score_sha256",
    "house_rule_violation_census", "outcome_columns_read",
    "uses_realized_outcomes", "historical_scoring_licensed",
    "production_change_licensed", "result_sha256",
})

# The image-invariant science subset compared for equivalence, in canonical
# order.  Everything else in a variant result is either a law/image binding
# or a wall-clock artifact and is enumerated as excluded in every receipt.
SCIENCE_ARM_FIELDS: Final = (
    "slate",
    "later_source_freeze_manifest_sha256",
    "artifact_sha256_by_block",
    "visit_schedule_sha256",
    "profile",
    "coverage",
    "visit_rosters",
    "unique_rosters",
    "first_occurrence_visit_indices",
    "candidate_score_sha256",
    "selector",
    "selected_rosters",
    "selected_score_sha256",
    "house_rule_violation_census",
)
EXCLUDED_IMAGE_VARIANT_FIELDS: Final = (
    "task_source_binding",
    "attempt_ledger_sha256",
    "matrix_authority_sha256",
    "solver_evidence_task_root_sha256",
    "runtime_effective_policy",
    "variant_attempt_rows_sha256",
    "result_sha256",
)

CARRIER_HASH_FIELDS: Final = (
    "task_result_sha256",
    "worker_completion_sha256",
)


class CorpusParametricSnapshotError(ValueError):
    """Raised when snapshot inputs differ from their pinned contracts."""


def _fail(message: str) -> None:
    raise CorpusParametricSnapshotError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        _fail(f"{label} must be an array")
    return value


def _sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != _SHA_LENGTH
        or any(ch not in "0123456789abcdef" for ch in value)
    ):
        _fail(f"{label} must be lowercase 64-hex")
    return value


def normalize_object_identity(
    value: object, *, label: str
) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} identity fields differ")
    uri = item["uri"]
    generation = item["generation"]
    size = item["bytes"]
    if (
        type(uri) is not str
        or not uri.startswith("gs://")
        or type(generation) is not str
        or not generation.isdigit()
        or generation.startswith("0")
        or type(size) is not int
        or size <= 0
    ):
        _fail(f"{label} identity values differ")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _sha(item["sha256"], label=f"{label} sha256"),
        "bytes": size,
    }


def _bind_raw(
    raw: bytes, identity: Mapping[str, object] | None, *, label: str
) -> None:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty raw bytes")
    if identity is None:
        return
    normalized = normalize_object_identity(identity, label=f"{label} identity")
    if (
        len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        _fail(f"{label} content identity differs")


def _parse_canonical(raw: bytes, *, label: str) -> dict[str, object]:
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusParametricSnapshotError(
            f"{label} is not valid JSON"
        ) from exc
    body = dict(_mapping(parsed, label=label))
    if canonical_json_bytes(body) != raw:
        _fail(f"{label} bytes are not canonical")
    return body


def _validate_self_hash(
    body: Mapping[str, object], *, field: str, label: str
) -> None:
    expected = _sha(body.get(field), label=f"{label} {field}")
    remainder = {
        key: value for key, value in body.items() if key != field
    }
    if canonical_sha256(remainder) != expected:
        _fail(f"{label} self-hash differs")


def validate_variant_result_bytes(
    raw: bytes,
    *,
    identity: Mapping[str, object] | None = None,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Validate one per-arm variant result object exactly.

    ``require_authoritative`` additionally enforces the accepted-production
    shape: full registered visit dose, complete optimality, exact-80
    selection, present source binding, and 64-hex law/evidence hashes.
    Synthetic engine-built fixtures may validate structurally with it off.
    """
    _bind_raw(raw, identity, label="variant result")
    body = _parse_canonical(raw, label="variant result")
    if set(body) != VARIANT_RESULT_KEYS:
        _fail("variant result keys differ")
    if body["schema"] != VARIANT_RESULT_SCHEMA:
        _fail("variant result schema differs")
    _validate_self_hash(body, field="result_sha256", label="variant result")
    if (
        body["uses_realized_outcomes"] is not False
        or body["historical_scoring_licensed"] is not False
        or body["production_change_licensed"] is not False
        or body["outcome_columns_read"] != []
    ):
        _fail("variant result outcome/authority guards differ")
    slate = _mapping(body["slate"], label="variant slate")
    if set(slate) != {"season", "week", "slate_id"}:
        _fail("variant slate fields differ")
    profile = _mapping(body["profile"], label="variant profile")
    ordinal = profile.get("ordinal")
    parameter_set_id = profile.get("parameter_set_id")
    if (
        type(ordinal) is not int
        or not 0 <= ordinal < len(PARAMETER_SET_ORDER)
        or parameter_set_id != PARAMETER_SET_ORDER[ordinal]
    ):
        _fail("variant profile ordinal/id differs")
    coverage = _mapping(body["coverage"], label="variant coverage")
    if set(coverage) != {
        "scheduled_visits", "attempted_visits", "optimal_visits",
        "unique_candidates", "selected_entries",
    } or any(
        type(value) is not int or value < 0 for value in coverage.values()
    ):
        _fail("variant coverage fields differ")
    rosters = _sequence(body["visit_rosters"], label="visit rosters")
    unique = _sequence(body["unique_rosters"], label="unique rosters")
    selected = _sequence(body["selected_rosters"], label="selected rosters")
    if (
        len(rosters) != coverage["optimal_visits"]
        or len(unique) != coverage["unique_candidates"]
        or len(selected) != coverage["selected_entries"]
    ):
        _fail("variant roster counts differ from coverage")
    selector = _mapping(body["selector"], label="variant selector")
    if set(selector) != {
        "candidate_count", "world_count", "entry_count", "tail_line_dk",
        "selected_indices", "tie_law_applied",
    }:
        _fail("variant selector fields differ")
    if (
        selector["candidate_count"] != len(unique)
        or selector["entry_count"] != len(selected)
        or len(
            _sequence(selector["selected_indices"], label="selected indices")
        ) != len(selected)
    ):
        _fail("variant selector counts differ")
    _sha(
        body["candidate_score_sha256"], label="candidate score sha",
    )
    _sha(body["selected_score_sha256"], label="selected score sha")
    _sha(body["visit_schedule_sha256"], label="visit schedule sha")
    _sha(
        body["later_source_freeze_manifest_sha256"],
        label="source freeze sha",
    )
    if require_authoritative:
        if body["task_source_binding"] is None:
            _fail("authoritative variant result lacks a source binding")
        for field in (
            "attempt_ledger_sha256", "matrix_authority_sha256",
            "solver_evidence_task_root_sha256",
        ):
            _sha(body[field], label=field)
        if (
            coverage["scheduled_visits"]
            != MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
            or coverage["attempted_visits"] != coverage["scheduled_visits"]
            or coverage["optimal_visits"] != coverage["scheduled_visits"]
            or coverage["selected_entries"] != SELECTED_ENTRY_BUDGET
            or coverage["unique_candidates"] < SELECTED_ENTRY_BUDGET
        ):
            _fail("authoritative variant coverage dose differs")
    return body


def read_task_variant_results(
    carrier_raw: bytes,
    *,
    carrier_identity: Mapping[str, object] | None,
    read_exact: Callable[[Mapping[str, object]], bytes],
    require_authoritative: bool = True,
) -> tuple[dict[str, object], list[dict[str, object]]]:
    """Reopen the seven per-arm variant results named by a carrier object."""
    _bind_raw(carrier_raw, carrier_identity, label="carrier")
    carrier = _parse_canonical(carrier_raw, label="carrier")
    present = [
        field for field in CARRIER_HASH_FIELDS if field in carrier
    ]
    if len(present) != 1:
        _fail("carrier must have exactly one known self-hash field")
    _validate_self_hash(carrier, field=present[0], label="carrier")
    # Two carrier dialects name the seven per-arm results: the retrieval
    # continuation's "variant_result_objects" rows carry object_identity
    # directly, while the parametric task result's "variant_results" rows
    # carry the identity under result_object beside the arm's policy
    # receipt. Each dialect is validated against its own exact row shape.
    if "variant_result_objects" in carrier:
        rows = _sequence(
            carrier.get("variant_result_objects"),
            label="carrier variant result objects",
        )
        identity_field = "object_identity"
        expected_row_fields = {"ordinal", "parameter_set_id", "object_identity"}
    else:
        rows = _sequence(
            carrier.get("variant_results"),
            label="carrier variant result objects",
        )
        identity_field = "result_object"
        expected_row_fields = {
            "ordinal", "parameter_set_id", "parameter_set_sha256",
            "effective_policy_receipt", "result_object",
        }
    if len(rows) != len(PARAMETER_SET_ORDER):
        _fail("carrier does not name exactly seven variant results")
    results: list[dict[str, object]] = []
    for expected_ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"variant object[{expected_ordinal}]")
        if set(row) != expected_row_fields:
            _fail("variant object row fields differ")
        if (
            row["ordinal"] != expected_ordinal
            or row["parameter_set_id"]
            != PARAMETER_SET_ORDER[expected_ordinal]
        ):
            _fail("variant object ordering differs")
        identity = normalize_object_identity(
            row[identity_field],
            label=f"variant object[{expected_ordinal}]",
        )
        body = validate_variant_result_bytes(
            read_exact(identity),
            identity=identity,
            require_authoritative=require_authoritative,
        )
        if body["profile"]["ordinal"] != expected_ordinal:
            _fail("variant payload ordinal differs from carrier row")
        results.append(body)
    slates = {
        canonical_sha256(body["slate"]) for body in results
    }
    schedules = {body["visit_schedule_sha256"] for body in results}
    sources = {
        body["later_source_freeze_manifest_sha256"] for body in results
    }
    if len(slates) != 1 or len(schedules) != 1 or len(sources) != 1:
        _fail("variant results disagree on slate/schedule/source identity")
    return carrier, results


def extract_task_science(
    variant_results: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Project the image-invariant science subset of one task's arms."""
    if len(variant_results) != len(PARAMETER_SET_ORDER):
        _fail("science projection requires exactly seven arms")
    arms = []
    for expected_ordinal, body in enumerate(variant_results):
        record = _mapping(body, label="variant result")
        if record["profile"]["ordinal"] != expected_ordinal:
            _fail("science projection arm order differs")
        arms.append({
            field: record[field] for field in SCIENCE_ARM_FIELDS
        })
    body = {
        "schema": SCIENCE_PROJECTION_SCHEMA,
        "arm_count": len(arms),
        "compared_fields": list(SCIENCE_ARM_FIELDS),
        "excluded_image_variant_fields": list(
            EXCLUDED_IMAGE_VARIANT_FIELDS
        ),
        "slate": arms[0]["slate"],
        "arms": arms,
        "uses_realized_outcomes": False,
    }
    body["science_projection_sha256"] = canonical_sha256(body)
    return body


def compare_task_science(
    baseline: Mapping[str, object],
    challenger: Mapping[str, object],
    *,
    baseline_label: str,
    challenger_label: str,
) -> dict[str, object]:
    """Compare two science projections field by field, arm by arm."""
    for label, projection in (
        (baseline_label, baseline), (challenger_label, challenger),
    ):
        record = _mapping(projection, label=f"{label} projection")
        if record.get("schema") != SCIENCE_PROJECTION_SCHEMA:
            _fail(f"{label} projection schema differs")
        _validate_self_hash(
            record,
            field="science_projection_sha256",
            label=f"{label} projection",
        )
    differing: list[dict[str, object]] = []
    for ordinal, (base_arm, challenger_arm) in enumerate(zip(
        baseline["arms"], challenger["arms"], strict=True
    )):
        for field in SCIENCE_ARM_FIELDS:
            if canonical_json_bytes(base_arm[field]) != canonical_json_bytes(
                challenger_arm[field]
            ):
                differing.append({"arm_ordinal": ordinal, "field": field})
    body = {
        "schema_version": EQUIVALENCE_RECEIPT_SCHEMA,
        "comparison": "science-only",
        "equivalent": not differing,
        "baseline_label": baseline_label,
        "challenger_label": challenger_label,
        "baseline_projection_sha256": baseline["science_projection_sha256"],
        "challenger_projection_sha256": (
            challenger["science_projection_sha256"]
        ),
        "arm_count": len(baseline["arms"]),
        "compared_fields": list(SCIENCE_ARM_FIELDS),
        "excluded_image_variant_fields": list(
            EXCLUDED_IMAGE_VARIANT_FIELDS
        ),
        "differing_fields": differing,
        "uses_realized_outcomes": False,
        "promotion_authority": False,
    }
    body["equivalence_receipt_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "CARRIER_HASH_FIELDS",
    "CorpusParametricSnapshotError",
    "EQUIVALENCE_RECEIPT_SCHEMA",
    "EXCLUDED_IMAGE_VARIANT_FIELDS",
    "SCIENCE_ARM_FIELDS",
    "SCIENCE_PROJECTION_SCHEMA",
    "VARIANT_RESULT_KEYS",
    "compare_task_science",
    "extract_task_science",
    "normalize_object_identity",
    "read_task_variant_results",
    "validate_variant_result_bytes",
]
