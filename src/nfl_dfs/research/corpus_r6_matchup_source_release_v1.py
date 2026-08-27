"""Terminal, ordinal-only R6-v2 matchup-source release contracts.

This module turns an already validated 54-entry component-producer release
into immutable per-slate source exports, capture receipts, operator results,
and one terminal source-release root.  Runtime selection is by the fixed
source-task ordinal only.  The public reopener derives every object identity
from the generation-pinned root; it accepts no caller-selected member,
catalog, bundle, receipt, or export identity.

The implementation owns no cloud, warehouse, Git, scoring, lineup-selection,
or outcome reader.  Publication and exact reads are injected.  Mechanics
authority is narrow: it authenticates the matchup-source projection only;
scoring, fill, retrieval, promotion, graph, production, and decision
authorities remain false.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
import math
import re
from typing import Final

from nfl_dfs.research import corpus_r6_matchup_component_producer_v1 as producer
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


MATCHUP_SOURCE_EXPORT_SCHEMA: Final = "corpus-r6-matchup-source-export/v2"
MATCHUP_CAPTURE_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-capture-receipt/v2"
)
MATCHUP_OPERATOR_RESULT_SCHEMA: Final = (
    "corpus-r6-matchup-source-operator-result/v2"
)
MATCHUP_SOURCE_RELEASE_SCHEMA: Final = "corpus-r6-matchup-source-release/v1"
MATCHUP_SOURCE_MEMBER_SCHEMA: Final = (
    "corpus-r6-matchup-source-release-member/v1"
)
OPERATOR_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_matchup_source_operator_v2.py"
)
TASK_COUNT: Final = source.TASK_COUNT
EVIDENCE_CLASS: Final = source.EVIDENCE_CLASS

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

_EXPORT_TRUE_AUTHORITIES: Final = frozenset({"authoritative_for_mechanics"})
_CAPTURE_TRUE_AUTHORITIES: Final = frozenset({
    "authoritative_for_mechanics", "capture_mechanics_authority",
})
_OPERATOR_TRUE_AUTHORITIES: Final = frozenset({
    *_CAPTURE_TRUE_AUTHORITIES,
    "source_execution_authority", "source_publication_authority",
})
_RELEASE_TRUE_AUTHORITIES: Final = frozenset({
    *_OPERATOR_TRUE_AUTHORITIES,
    "matchup_source_authority", "r6_source_authority",
})

_ANNOTATION_FIELDS: Final = frozenset({
    "gsis_id", "family", "position", "qb_depth1",
    "qb_depth_evidence_class", "raw_component_values",
    "component_observed_game_counts", "component_values",
    "component_support", "component_missingness_reasons",
    "matchup_component_count", "matchup_edge_score",
    "annotation_row_present",
    "component_source_bounds",
})
_CAPTURE_PLAN_BINDING_FIELDS: Final = frozenset({
    "commit_sha", "relative_path", "sha256", "bytes",
    "capture_plan_sha256",
})


class CorpusR6MatchupSourceReleaseV1Error(ValueError):
    """The terminal source release or one of its exact members is invalid."""


ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]


def _fail(message: str) -> None:
    raise CorpusR6MatchupSourceReleaseV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: set[str] | frozenset[str], *, label: str,
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} fields differ")


def _text(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _identifier(value: object, *, label: str) -> str:
    text = _text(value, label=label)
    if _IDENTIFIER.fullmatch(text) is None:
        _fail(f"{label} must be a canonical identifier")
    return text


def _digest(value: object, *, label: str) -> str:
    text = _text(value, label=label)
    if _SHA256.fullmatch(text) is None:
        _fail(f"{label} must be a lowercase SHA-256")
    return text


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _finite_or_none(value: object, *, label: str) -> float | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        _fail(f"{label} must be finite or null")
    result = float(value)
    if not math.isfinite(result):
        _fail(f"{label} must be finite or null")
    return result


def _namespace(value: object, *, label: str) -> str:
    text = _text(value, label=label)
    if (
        not text.startswith("gs://")
        or not text.endswith("/")
        or ".." in text
        or "//" in text[5:]
    ):
        _fail(f"{label} must be a canonical GCS prefix")
    return text


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSourceReleaseV1Error(str(exc)) from exc


def _code_identity(
    value: object, *, label: str, expected_path: str | None = None,
) -> dict[str, str]:
    try:
        return source.normalize_code_identity_v2(
            value, expected_module_path=expected_path, label=label
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSourceReleaseV1Error(str(exc)) from exc


def _slate(value: object, *, ordinal: int, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, catalog_v1.SLATE_FIELDS, label=label)
    expected = catalog_v1.expected_slate_for_source_task(ordinal)
    if item != expected:
        _fail(f"{label} differs from fixed source-task ordinal")
    return expected


def _authority_policy(true_fields: frozenset[str]) -> dict[str, object]:
    if not true_fields.issubset(source.FALSE_AUTHORITY_FIELDS):
        _fail("mechanics authority policy contains an unknown field")
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{
            field: field in true_fields for field in source.FALSE_AUTHORITY_FIELDS
        },
    }


def _validate_policy(
    value: Mapping[str, object], *, true_fields: frozenset[str], label: str,
) -> None:
    for field, expected in _authority_policy(true_fields).items():
        if value.get(field) != expected:
            _fail(f"{label} authority/outcome policy differs")


def _with_self_hash(
    body: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    if field in body:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(body)
    result[field] = source.canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label} self-hash")
    body = dict(value)
    del body[field]
    if source.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _bind_body(
    body: object, identity: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    normalized = _identity(identity, label=label)
    raw = source.canonical_json_bytes(body)
    if (
        normalized["sha256"] != sha256(raw).hexdigest()
        or normalized["bytes"] != len(raw)
    ):
        _fail(f"{label} differs from exact body")
    return normalized


def _parse_exact(
    identity: Mapping[str, object], *, read_exact: ReadExact, label: str,
) -> dict[str, object]:
    normalized = _identity(identity, label=label)
    try:
        raw = read_exact(normalized)
    except Exception as exc:
        raise CorpusR6MatchupSourceReleaseV1Error(
            f"{label} exact reopen failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        _fail(f"{label} exact bytes differ")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupSourceReleaseV1Error(
            f"{label} is not canonical JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if source.canonical_json_bytes(body) != raw:
        _fail(f"{label} canonical bytes differ")
    return body


def _capture_plan_binding(value: object) -> dict[str, object]:
    item = _mapping(value, label="capture-plan binding")
    _exact_keys(item, _CAPTURE_PLAN_BINDING_FIELDS, label="capture-plan binding")
    commit = _text(item["commit_sha"], label="capture-plan commit")
    if _COMMIT.fullmatch(commit) is None:
        _fail("capture-plan commit must be a lowercase Git SHA")
    path = _text(item["relative_path"], label="capture-plan relative path")
    if path.startswith("/") or ".." in path.split("/"):
        _fail("capture-plan relative path is unsafe")
    return {
        "commit_sha": commit,
        "relative_path": path,
        "sha256": _digest(item["sha256"], label="capture-plan file SHA"),
        "bytes": _exact_int(item["bytes"], label="capture-plan file bytes", minimum=1),
        "capture_plan_sha256": _digest(
            item["capture_plan_sha256"], label="capture-plan internal SHA"
        ),
    }


def _normalize_annotations(value: object) -> list[dict[str, object]]:
    rows = _sequence(value, label="matchup annotation rows")
    normalized: list[dict[str, object]] = []
    previous_id: str | None = None
    families = source.family_components_v1()
    positions = source.position_family_v1()
    for offset, row_value in enumerate(rows):
        row = _mapping(row_value, label=f"matchup annotation row[{offset}]")
        _exact_keys(row, _ANNOTATION_FIELDS, label="matchup annotation row")
        player_id = _text(row["gsis_id"], label="annotation player ID")
        if previous_id is not None and player_id <= previous_id:
            _fail("matchup annotation rows must be strictly player-ID ordered")
        previous_id = player_id
        family = _identifier(row["family"], label="annotation family")
        position = _text(row["position"], label="annotation position")
        if family not in families or positions.get(position) != family:
            _fail("matchup annotation family/position differs")
        components = frozenset(families[family])
        mappings: dict[str, dict[str, object]] = {}
        for field in (
            "raw_component_values", "component_observed_game_counts",
            "component_values", "component_support",
            "component_missingness_reasons", "component_source_bounds",
        ):
            retained = _mapping(row[field], label=f"annotation {field}")
            _exact_keys(retained, components, label=f"annotation {field}")
            mappings[field] = retained
        for component in components:
            _finite_or_none(
                mappings["raw_component_values"][component],
                label=f"annotation raw {component}",
            )
            value = _finite_or_none(
                mappings["component_values"][component],
                label=f"annotation value {component}",
            )
            observed = mappings["component_observed_game_counts"][component]
            supported = mappings["component_support"][component]
            reason = mappings["component_missingness_reasons"][component]
            if (
                (
                    observed is not None
                    and (type(observed) is not int or observed < 0)
                )
                or type(supported) is not bool
                or (supported is True) != (value is not None)
                or (reason is None) != (supported is True)
                or not isinstance(mappings["component_source_bounds"][component], list)
            ):
                _fail("matchup annotation component semantics differ")
        qb_depth = row["qb_depth1"]
        if qb_depth is not None and type(qb_depth) is not bool:
            _fail("annotation QB depth must be true, false, or null")
        edge = _finite_or_none(
            row["matchup_edge_score"], label="annotation matchup edge"
        )
        count = _exact_int(
            row["matchup_component_count"], label="annotation component count"
        )
        if count != sum(
            value is not None
            for value in mappings["component_values"].values()
        ) or (edge is not None and count < 2) or row[
            "annotation_row_present"
        ] is not (edge is not None):
            _fail("annotation matchup edge support differs")
        normalized.append(row)
    if not normalized:
        _fail("matchup source export requires annotation rows")
    return normalized


def _basic_producer_receipt(
    value: object,
    *,
    structural_catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    input_bundle: Mapping[str, object],
    input_bundle_identity: Mapping[str, object],
    producer_receipt_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    receipt = _mapping(value, label="component producer receipt")
    if receipt.get("schema_version") != source.PRODUCER_RECEIPT_SCHEMA:
        _fail("component producer receipt schema differs")
    _validate_self_hash(
        receipt, field="producer_receipt_sha256",
        label="component producer receipt",
    )
    catalog = source.validate_structural_catalog_v2(structural_catalog)
    normalized_catalog_identity = _bind_body(
        catalog, catalog_identity, label="structural catalog"
    )
    try:
        bundle = producer.validate_component_input_bundle_v1(
            input_bundle,
            expected_catalog=catalog,
            expected_identity=input_bundle_identity,
        )
    except producer.CorpusR6MatchupComponentProducerV1Error as exc:
        raise CorpusR6MatchupSourceReleaseV1Error(str(exc)) from exc
    normalized_bundle_identity = _bind_body(
        bundle, input_bundle_identity, label="component input bundle"
    )
    ordinal = int(catalog["source_task_ordinal"])
    annotations = _normalize_annotations(bundle.get("annotation_rows"))
    if (
        receipt.get("source_task_ordinal") != ordinal
        or receipt.get("slate") != catalog["slate"]
        or receipt.get("catalog_identity") != normalized_catalog_identity
        or receipt.get("input_bundle_identity") != normalized_bundle_identity
        or receipt.get("input_bundle_sha256")
        != normalized_bundle_identity["sha256"]
        or receipt.get("annotation_row_count") != len(annotations)
        or receipt.get("annotation_rows_sha256")
        != source.canonical_sha256(annotations)
        or receipt.get("family_registry") != bundle.get("family_registry")
        or receipt.get("family_registry_sha256")
        != bundle.get("family_registry_sha256")
        or receipt.get("qb_depth_census") != bundle.get("qb_depth_census")
        or receipt.get("admission_support_census")
        != bundle.get("admission_support_census")
        or receipt.get("support_preflight_passed") is not True
    ):
        _fail("component producer receipt differs from exact bundle/catalog")
    _validate_policy(
        receipt, true_fields=frozenset(), label="component producer receipt"
    )
    if producer_receipt_identity is not None:
        _bind_body(
            receipt,
            producer_receipt_identity,
            label="component producer receipt",
        )
    return receipt


def build_matchup_source_export_v2(
    *,
    producer_release_identity: Mapping[str, object],
    producer_receipt: Mapping[str, object],
    producer_receipt_identity: Mapping[str, object],
    input_bundle: Mapping[str, object],
    input_bundle_identity: Mapping[str, object],
    structural_catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    candidate_artifact_identity: Mapping[str, object],
) -> dict[str, object]:
    """Project one exact producer bundle into the source consumed by R6-v2."""
    catalog = source.validate_structural_catalog_v2(structural_catalog)
    catalog_id = _bind_body(catalog, catalog_identity, label="structural catalog")
    try:
        bundle = producer.validate_component_input_bundle_v1(
            input_bundle,
            expected_catalog=catalog,
            expected_identity=input_bundle_identity,
        )
    except producer.CorpusR6MatchupComponentProducerV1Error as exc:
        raise CorpusR6MatchupSourceReleaseV1Error(str(exc)) from exc
    bundle_id = _bind_body(
        bundle, input_bundle_identity, label="component input bundle"
    )
    receipt = _basic_producer_receipt(
        producer_receipt,
        structural_catalog=catalog,
        catalog_identity=catalog_id,
        input_bundle=bundle,
        input_bundle_identity=bundle_id,
        producer_receipt_identity=producer_receipt_identity,
    )
    receipt_id = _bind_body(
        receipt, producer_receipt_identity, label="component producer receipt"
    )
    release_id = _identity(
        producer_release_identity, label="producer release"
    )
    candidate_id = _identity(
        candidate_artifact_identity, label="accepted candidate artifact"
    )
    admission = _mapping(
        bundle["admission_support_census"], label="admission support census"
    )
    if candidate_id != _identity(
        admission.get("candidate_artifact_identity"),
        label="admission candidate artifact",
    ):
        _fail("source export candidate artifact differs from admission census")
    annotations = _normalize_annotations(bundle["annotation_rows"])
    ordinal = int(catalog["source_task_ordinal"])
    body: dict[str, object] = {
        "schema_version": MATCHUP_SOURCE_EXPORT_SCHEMA,
        "source_task_ordinal": ordinal,
        "task_id": catalog["task_id"],
        "slate": catalog["slate"],
        "lock_time_utc": bundle["lock_time_utc"],
        "evidence_class": EVIDENCE_CLASS,
        "authoritative_pit": False,
        "producer_release_identity": release_id,
        "producer_receipt_identity": receipt_id,
        "input_bundle_identity": bundle_id,
        "catalog_identity": catalog_id,
        "candidate_artifact_identity": candidate_id,
        "family_registry": bundle["family_registry"],
        "family_registry_sha256": bundle["family_registry_sha256"],
        "target_spine_sha256": bundle["target_spine_sha256"],
        "annotation_rows": annotations,
        "annotation_row_count": len(annotations),
        "annotation_rows_sha256": source.canonical_sha256(annotations),
        "qb_depth_census": bundle["qb_depth_census"],
        "admission_support_census": admission,
        **_authority_policy(_EXPORT_TRUE_AUTHORITIES),
    }
    return _with_self_hash(body, field="matchup_source_export_sha256")


def validate_matchup_source_export_v2(
    value: object,
    *,
    producer_receipt: Mapping[str, object],
    producer_receipt_identity: Mapping[str, object],
    input_bundle: Mapping[str, object],
    input_bundle_identity: Mapping[str, object],
    structural_catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="matchup source export v2")
    fields = {
        "schema_version", "source_task_ordinal", "task_id", "slate",
        "lock_time_utc", "evidence_class", "authoritative_pit",
        "producer_release_identity", "producer_receipt_identity",
        "input_bundle_identity", "catalog_identity",
        "candidate_artifact_identity", "family_registry",
        "family_registry_sha256", "target_spine_sha256",
        "annotation_rows", "annotation_row_count", "annotation_rows_sha256",
        "qb_depth_census", "admission_support_census",
        "outcome_columns_read", "uses_realized_outcomes",
        *source.FALSE_AUTHORITY_FIELDS, "matchup_source_export_sha256",
    }
    _exact_keys(item, fields, label="matchup source export v2")
    _validate_self_hash(
        item, field="matchup_source_export_sha256",
        label="matchup source export v2",
    )
    _validate_policy(
        item, true_fields=_EXPORT_TRUE_AUTHORITIES,
        label="matchup source export v2",
    )
    if (
        item["schema_version"] != MATCHUP_SOURCE_EXPORT_SCHEMA
        or item["evidence_class"] != EVIDENCE_CLASS
        or item["authoritative_pit"] is not False
    ):
        _fail("matchup source export v2 fixed law differs")
    expected = build_matchup_source_export_v2(
        producer_release_identity=item["producer_release_identity"],
        producer_receipt=producer_receipt,
        producer_receipt_identity=producer_receipt_identity,
        input_bundle=input_bundle,
        input_bundle_identity=input_bundle_identity,
        structural_catalog=structural_catalog,
        catalog_identity=catalog_identity,
        candidate_artifact_identity=item["candidate_artifact_identity"],
    )
    if source.canonical_json_bytes(expected) != source.canonical_json_bytes(item):
        _fail("matchup source export v2 differs from producer replay")
    return expected


def build_matchup_capture_receipt_v2(
    *,
    source_export: Mapping[str, object],
    source_export_identity: Mapping[str, object],
    producer_receipt: Mapping[str, object],
    producer_receipt_identity: Mapping[str, object],
    input_bundle: Mapping[str, object],
    input_bundle_identity: Mapping[str, object],
    structural_catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
) -> dict[str, object]:
    export = validate_matchup_source_export_v2(
        source_export,
        producer_receipt=producer_receipt,
        producer_receipt_identity=producer_receipt_identity,
        input_bundle=input_bundle,
        input_bundle_identity=input_bundle_identity,
        structural_catalog=structural_catalog,
        catalog_identity=catalog_identity,
    )
    export_id = _bind_body(
        export, source_export_identity, label="matchup source export v2"
    )
    receipt = _mapping(producer_receipt, label="component producer receipt")
    deletion = _mapping(
        receipt.get("target_or_later_deletion_proof"),
        label="target-or-later deletion proof",
    )
    admission = _mapping(
        receipt.get("admission_support_census"),
        label="admission support census",
    )
    body: dict[str, object] = {
        "schema_version": MATCHUP_CAPTURE_RECEIPT_SCHEMA,
        "source_task_ordinal": export["source_task_ordinal"],
        "task_id": export["task_id"],
        "slate": export["slate"],
        "lock_time_utc": export["lock_time_utc"],
        "source_export_identity": export_id,
        "source_export_sha256": export["matchup_source_export_sha256"],
        "producer_release_identity": export["producer_release_identity"],
        "producer_receipt_identity": export["producer_receipt_identity"],
        "input_bundle_identity": export["input_bundle_identity"],
        "catalog_identity": export["catalog_identity"],
        "candidate_artifact_identity": export["candidate_artifact_identity"],
        "target_spine_sha256": export["target_spine_sha256"],
        "annotation_rows_sha256": export["annotation_rows_sha256"],
        "deletion_proof_sha256": deletion["deletion_proof_sha256"],
        "support_census_sha256": admission[
            "admission_support_census_sha256"
        ],
        "producer_receipt_exact_reopened": True,
        "input_bundle_exact_reopened": True,
        "catalog_exact_reopened": True,
        "source_export_exact_reopened": True,
        **_authority_policy(_CAPTURE_TRUE_AUTHORITIES),
    }
    return _with_self_hash(body, field="matchup_capture_receipt_sha256")


def validate_matchup_capture_receipt_v2(
    value: object,
    *,
    source_export: Mapping[str, object],
    source_export_identity: Mapping[str, object],
    producer_receipt: Mapping[str, object],
    producer_receipt_identity: Mapping[str, object],
    input_bundle: Mapping[str, object],
    input_bundle_identity: Mapping[str, object],
    structural_catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="matchup capture receipt v2")
    fields = {
        "schema_version", "source_task_ordinal", "task_id", "slate",
        "lock_time_utc", "source_export_identity", "source_export_sha256",
        "producer_release_identity", "producer_receipt_identity",
        "input_bundle_identity", "catalog_identity",
        "candidate_artifact_identity", "target_spine_sha256",
        "annotation_rows_sha256", "deletion_proof_sha256",
        "support_census_sha256", "producer_receipt_exact_reopened",
        "input_bundle_exact_reopened", "catalog_exact_reopened",
        "source_export_exact_reopened", "outcome_columns_read",
        "uses_realized_outcomes", *source.FALSE_AUTHORITY_FIELDS,
        "matchup_capture_receipt_sha256",
    }
    _exact_keys(item, fields, label="matchup capture receipt v2")
    _validate_self_hash(
        item, field="matchup_capture_receipt_sha256",
        label="matchup capture receipt v2",
    )
    _validate_policy(
        item, true_fields=_CAPTURE_TRUE_AUTHORITIES,
        label="matchup capture receipt v2",
    )
    if (
        item["schema_version"] != MATCHUP_CAPTURE_RECEIPT_SCHEMA
        or any(
            item[field] is not True
            for field in (
                "producer_receipt_exact_reopened",
                "input_bundle_exact_reopened",
                "catalog_exact_reopened",
                "source_export_exact_reopened",
            )
        )
    ):
        _fail("matchup capture receipt v2 fixed law differs")
    expected = build_matchup_capture_receipt_v2(
        source_export=source_export,
        source_export_identity=source_export_identity,
        producer_receipt=producer_receipt,
        producer_receipt_identity=producer_receipt_identity,
        input_bundle=input_bundle,
        input_bundle_identity=input_bundle_identity,
        structural_catalog=structural_catalog,
        catalog_identity=catalog_identity,
    )
    if source.canonical_json_bytes(expected) != source.canonical_json_bytes(item):
        _fail("matchup capture receipt v2 differs from exact source replay")
    return expected


def build_matchup_operator_result_v2(
    *,
    source_task_ordinal: int,
    capture_plan_binding: Mapping[str, object],
    operator_code_identity: Mapping[str, object],
    output_prefix: str,
    source_export: Mapping[str, object],
    source_export_identity: Mapping[str, object],
    capture_receipt: Mapping[str, object],
    capture_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    ordinal = _exact_int(
        source_task_ordinal, label="operator source-task ordinal"
    )
    if ordinal >= TASK_COUNT:
        _fail("operator source-task ordinal must be in 0..53")
    export = _mapping(source_export, label="operator source export")
    receipt = _mapping(capture_receipt, label="operator capture receipt")
    _validate_self_hash(
        export, field="matchup_source_export_sha256", label="operator source export"
    )
    _validate_self_hash(
        receipt, field="matchup_capture_receipt_sha256",
        label="operator capture receipt",
    )
    export_id = _bind_body(
        export, source_export_identity, label="operator source export"
    )
    receipt_id = _bind_body(
        receipt, capture_receipt_identity, label="operator capture receipt"
    )
    expected_slate = _slate(export.get("slate"), ordinal=ordinal, label="export slate")
    prefix = _namespace(output_prefix, label="operator output prefix")
    expected_prefix = f"source-task-{ordinal:02d}-{expected_slate['slate_id']}/"
    if (
        not prefix.endswith(expected_prefix)
        or export.get("source_task_ordinal") != ordinal
        or receipt.get("source_task_ordinal") != ordinal
        or receipt.get("source_export_identity") != export_id
        or receipt.get("source_export_sha256")
        != export.get("matchup_source_export_sha256")
    ):
        _fail("operator result source/capture binding differs")
    body: dict[str, object] = {
        "schema_version": MATCHUP_OPERATOR_RESULT_SCHEMA,
        "source_task_ordinal": ordinal,
        "task_id": catalog_v1.task_id_for_source_task(ordinal),
        "slate": expected_slate,
        "lock_time_utc": export["lock_time_utc"],
        "capture_plan_binding": _capture_plan_binding(capture_plan_binding),
        "operator_code_identity": _code_identity(
            operator_code_identity,
            label="matchup source operator code",
            expected_path=OPERATOR_MODULE_PATH,
        ),
        "output_prefix": prefix,
        "source_export_identity": export_id,
        "capture_receipt_identity": receipt_id,
        "producer_release_identity": export["producer_release_identity"],
        "producer_receipt_identity": export["producer_receipt_identity"],
        "input_bundle_identity": export["input_bundle_identity"],
        "catalog_identity": export["catalog_identity"],
        "candidate_artifact_identity": export["candidate_artifact_identity"],
        "publication_mode": source.PUBLICATION_MODE,
        "source_export_exact_reopened": True,
        "capture_receipt_exact_reopened": True,
        "operator_result_exact_reopened": True,
        **_authority_policy(_OPERATOR_TRUE_AUTHORITIES),
    }
    return _with_self_hash(body, field="matchup_operator_result_sha256")


def validate_matchup_operator_result_v2(
    value: object,
    *,
    source_export: Mapping[str, object],
    source_export_identity: Mapping[str, object],
    capture_receipt: Mapping[str, object],
    capture_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="matchup operator result v2")
    fields = {
        "schema_version", "source_task_ordinal", "task_id", "slate",
        "lock_time_utc", "capture_plan_binding", "operator_code_identity",
        "output_prefix", "source_export_identity", "capture_receipt_identity",
        "producer_release_identity", "producer_receipt_identity",
        "input_bundle_identity", "catalog_identity",
        "candidate_artifact_identity", "publication_mode",
        "source_export_exact_reopened", "capture_receipt_exact_reopened",
        "operator_result_exact_reopened", "outcome_columns_read",
        "uses_realized_outcomes", *source.FALSE_AUTHORITY_FIELDS,
        "matchup_operator_result_sha256",
    }
    _exact_keys(item, fields, label="matchup operator result v2")
    _validate_self_hash(
        item, field="matchup_operator_result_sha256",
        label="matchup operator result v2",
    )
    _validate_policy(
        item, true_fields=_OPERATOR_TRUE_AUTHORITIES,
        label="matchup operator result v2",
    )
    if (
        item["schema_version"] != MATCHUP_OPERATOR_RESULT_SCHEMA
        or item["publication_mode"] != source.PUBLICATION_MODE
        or any(
            item[field] is not True
            for field in (
                "source_export_exact_reopened",
                "capture_receipt_exact_reopened",
                "operator_result_exact_reopened",
            )
        )
    ):
        _fail("matchup operator result v2 fixed law differs")
    expected = build_matchup_operator_result_v2(
        source_task_ordinal=item["source_task_ordinal"],
        capture_plan_binding=item["capture_plan_binding"],
        operator_code_identity=item["operator_code_identity"],
        output_prefix=item["output_prefix"],
        source_export=source_export,
        source_export_identity=source_export_identity,
        capture_receipt=capture_receipt,
        capture_receipt_identity=capture_receipt_identity,
    )
    if source.canonical_json_bytes(expected) != source.canonical_json_bytes(item):
        _fail("matchup operator result v2 differs from exact capture replay")
    return expected


def _producer_release_shape(
    value: object,
    *,
    identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="component producer release")
    if item.get("schema_version") != source.PRODUCER_RELEASE_SCHEMA:
        _fail("component producer release schema differs")
    _validate_self_hash(
        item, field="producer_release_sha256",
        label="component producer release",
    )
    _validate_policy(
        item, true_fields=frozenset(), label="component producer release"
    )
    entries = _sequence(item.get("entries"), label="producer release entries")
    if (
        item.get("task_count") != TASK_COUNT
        or len(entries) != TASK_COUNT
        or item.get("entry_manifest_sha256") != source.canonical_sha256(entries)
        or any(
            _mapping(entry, label=f"producer entry[{ordinal}]").get(
                "source_task_ordinal"
            ) != ordinal
            for ordinal, entry in enumerate(entries)
        )
    ):
        _fail("component producer release 54-entry lattice differs")
    if identity is not None:
        _bind_body(item, identity, label="component producer release")
    return item


def _validate_member(value: object, *, expected_ordinal: int) -> dict[str, object]:
    item = _mapping(value, label=f"matchup source member[{expected_ordinal}]")
    fields = {
        "schema_version", "source_task_ordinal", "task_id", "slate",
        "lock_time_utc", "producer_release_identity", "catalog_identity",
        "candidate_artifact_identity",
        "producer_receipt_identity", "input_bundle_identity",
        "source_export_identity", "capture_receipt_identity",
        "operator_result_identity", "producer_release_entry_sha256",
        "source_export_sha256", "capture_receipt_sha256",
        "operator_result_sha256", "matchup_source_member_sha256",
    }
    _exact_keys(item, fields, label="matchup source release member")
    _validate_self_hash(
        item, field="matchup_source_member_sha256",
        label="matchup source release member",
    )
    ordinal = _exact_int(
        item["source_task_ordinal"], label="member source-task ordinal"
    )
    if ordinal != expected_ordinal or ordinal >= TASK_COUNT:
        _fail("matchup source member ordinal differs")
    slate = _slate(item["slate"], ordinal=ordinal, label="member slate")
    if (
        item["schema_version"] != MATCHUP_SOURCE_MEMBER_SCHEMA
        or item["task_id"] != catalog_v1.task_id_for_source_task(ordinal)
        or type(item["lock_time_utc"]) is not str
        or _UTC.fullmatch(str(item["lock_time_utc"])) is None
    ):
        _fail("matchup source member task/time law differs")
    normalized = dict(item)
    normalized.update({
        "slate": slate,
        "producer_release_identity": _identity(
            item["producer_release_identity"], label="member producer release"
        ),
        "catalog_identity": _identity(item["catalog_identity"], label="member catalog"),
        "candidate_artifact_identity": _identity(
            item["candidate_artifact_identity"], label="member candidates"
        ),
        "producer_receipt_identity": _identity(
            item["producer_receipt_identity"], label="member producer receipt"
        ),
        "input_bundle_identity": _identity(
            item["input_bundle_identity"], label="member input bundle"
        ),
        "source_export_identity": _identity(
            item["source_export_identity"], label="member source export"
        ),
        "capture_receipt_identity": _identity(
            item["capture_receipt_identity"], label="member capture receipt"
        ),
        "operator_result_identity": _identity(
            item["operator_result_identity"], label="member operator result"
        ),
    })
    for field in (
        "producer_release_entry_sha256", "source_export_sha256",
        "capture_receipt_sha256", "operator_result_sha256",
    ):
        normalized[field] = _digest(item[field], label=f"member {field}")
    if source.canonical_json_bytes(normalized) != source.canonical_json_bytes(item):
        _fail("matchup source member canonical replay differs")
    return normalized


def _build_member(
    *,
    ordinal: int,
    producer_release_identity: Mapping[str, object],
    producer_entry: Mapping[str, object],
    source_export: Mapping[str, object],
    source_export_identity: Mapping[str, object],
    capture_receipt: Mapping[str, object],
    capture_receipt_identity: Mapping[str, object],
    operator_result: Mapping[str, object],
    operator_result_identity: Mapping[str, object],
) -> dict[str, object]:
    entry = _mapping(producer_entry, label=f"producer release entry[{ordinal}]")
    export = _mapping(source_export, label=f"source export[{ordinal}]")
    capture = _mapping(capture_receipt, label=f"capture receipt[{ordinal}]")
    result = _mapping(operator_result, label=f"operator result[{ordinal}]")
    _validate_self_hash(
        export, field="matchup_source_export_sha256", label="source export"
    )
    _validate_policy(
        export, true_fields=_EXPORT_TRUE_AUTHORITIES, label="source export"
    )
    _validate_self_hash(
        capture, field="matchup_capture_receipt_sha256", label="capture receipt"
    )
    _validate_policy(
        capture, true_fields=_CAPTURE_TRUE_AUTHORITIES, label="capture receipt"
    )
    _validate_self_hash(
        result, field="matchup_operator_result_sha256", label="operator result"
    )
    _validate_policy(
        result, true_fields=_OPERATOR_TRUE_AUTHORITIES, label="operator result"
    )
    export_id = _bind_body(export, source_export_identity, label="source export")
    capture_id = _bind_body(
        capture, capture_receipt_identity, label="capture receipt"
    )
    result_id = _bind_body(result, operator_result_identity, label="operator result")
    producer_release_id = _identity(
        producer_release_identity, label="component producer release"
    )
    slate = _slate(export.get("slate"), ordinal=ordinal, label="source export slate")
    expected_task = catalog_v1.task_id_for_source_task(ordinal)
    if (
        export.get("schema_version") != MATCHUP_SOURCE_EXPORT_SCHEMA
        or capture.get("schema_version") != MATCHUP_CAPTURE_RECEIPT_SCHEMA
        or result.get("schema_version") != MATCHUP_OPERATOR_RESULT_SCHEMA
        or export.get("evidence_class") != EVIDENCE_CLASS
        or export.get("authoritative_pit") is not False
        or any(
            capture.get(field) is not True
            for field in (
                "producer_receipt_exact_reopened",
                "input_bundle_exact_reopened",
                "catalog_exact_reopened",
                "source_export_exact_reopened",
            )
        )
        or result.get("publication_mode") != source.PUBLICATION_MODE
        or any(
            result.get(field) is not True
            for field in (
                "source_export_exact_reopened",
                "capture_receipt_exact_reopened",
                "operator_result_exact_reopened",
            )
        )
        or entry.get("source_task_ordinal") != ordinal
        or export.get("source_task_ordinal") != ordinal
        or capture.get("source_task_ordinal") != ordinal
        or result.get("source_task_ordinal") != ordinal
        or export.get("task_id") != expected_task
        or capture.get("task_id") != expected_task
        or result.get("task_id") != expected_task
        or entry.get("slate") != slate
        or capture.get("slate") != slate
        or result.get("slate") != slate
        or entry.get("lock_time_utc") != export.get("lock_time_utc")
        or capture.get("lock_time_utc") != export.get("lock_time_utc")
        or result.get("lock_time_utc") != export.get("lock_time_utc")
        or export.get("producer_release_identity") != producer_release_id
        or capture.get("source_export_identity") != export_id
        or capture.get("source_export_sha256")
        != export.get("matchup_source_export_sha256")
        or capture.get("producer_release_identity") != producer_release_id
        or capture.get("producer_receipt_identity")
        != export.get("producer_receipt_identity")
        or capture.get("input_bundle_identity")
        != export.get("input_bundle_identity")
        or capture.get("catalog_identity") != export.get("catalog_identity")
        or capture.get("candidate_artifact_identity")
        != export.get("candidate_artifact_identity")
        or result.get("source_export_identity") != export_id
        or result.get("capture_receipt_identity") != capture_id
        or result.get("producer_release_identity") != producer_release_id
        or result.get("producer_receipt_identity")
        != export.get("producer_receipt_identity")
        or result.get("input_bundle_identity")
        != export.get("input_bundle_identity")
        or result.get("catalog_identity") != export.get("catalog_identity")
        or result.get("candidate_artifact_identity")
        != export.get("candidate_artifact_identity")
        or entry.get("catalog_identity") != export.get("catalog_identity")
        or entry.get("producer_receipt_identity")
        != export.get("producer_receipt_identity")
        or entry.get("input_bundle_identity") != export.get("input_bundle_identity")
        or entry.get("candidate_artifact_identity")
        != export.get("candidate_artifact_identity")
    ):
        _fail("terminal source member differs from producer/export/capture")
    body: dict[str, object] = {
        "schema_version": MATCHUP_SOURCE_MEMBER_SCHEMA,
        "source_task_ordinal": ordinal,
        "task_id": expected_task,
        "slate": slate,
        "lock_time_utc": export["lock_time_utc"],
        "producer_release_identity": producer_release_id,
        "catalog_identity": export["catalog_identity"],
        "candidate_artifact_identity": export["candidate_artifact_identity"],
        "producer_receipt_identity": export["producer_receipt_identity"],
        "input_bundle_identity": export["input_bundle_identity"],
        "source_export_identity": export_id,
        "capture_receipt_identity": capture_id,
        "operator_result_identity": result_id,
        "producer_release_entry_sha256": source.canonical_sha256(entry),
        "source_export_sha256": export["matchup_source_export_sha256"],
        "capture_receipt_sha256": capture["matchup_capture_receipt_sha256"],
        "operator_result_sha256": result["matchup_operator_result_sha256"],
    }
    return _with_self_hash(body, field="matchup_source_member_sha256")


def build_matchup_source_release_v1(
    *,
    release_id: str,
    namespace: str,
    capture_plan_binding: Mapping[str, object],
    producer_release: Mapping[str, object],
    producer_release_identity: Mapping[str, object],
    source_exports: Sequence[Mapping[str, object]],
    source_export_identities: Sequence[Mapping[str, object]],
    capture_receipts: Sequence[Mapping[str, object]],
    capture_receipt_identities: Sequence[Mapping[str, object]],
    operator_results: Sequence[Mapping[str, object]],
    operator_result_identities: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    producer_root = _producer_release_shape(
        producer_release, identity=producer_release_identity
    )
    producer_root_id = _bind_body(
        producer_root, producer_release_identity, label="component producer release"
    )
    groups = [
        _sequence(source_exports, label="source exports"),
        _sequence(source_export_identities, label="source export identities"),
        _sequence(capture_receipts, label="capture receipts"),
        _sequence(capture_receipt_identities, label="capture receipt identities"),
        _sequence(operator_results, label="operator results"),
        _sequence(operator_result_identities, label="operator result identities"),
    ]
    if any(len(group) != TASK_COUNT for group in groups):
        _fail("terminal source release requires exactly 54 complete member triples")
    exports, export_ids, captures, capture_ids, results, result_ids = groups
    producer_entries = _sequence(
        producer_root["entries"], label="producer release entries"
    )
    members = [
        _build_member(
            ordinal=ordinal,
            producer_release_identity=producer_root_id,
            producer_entry=producer_entries[ordinal],
            source_export=_mapping(exports[ordinal], label="source export"),
            source_export_identity=_mapping(export_ids[ordinal], label="source export ID"),
            capture_receipt=_mapping(captures[ordinal], label="capture receipt"),
            capture_receipt_identity=_mapping(capture_ids[ordinal], label="capture receipt ID"),
            operator_result=_mapping(results[ordinal], label="operator result"),
            operator_result_identity=_mapping(result_ids[ordinal], label="operator result ID"),
        )
        for ordinal in range(TASK_COUNT)
    ]
    plan = _capture_plan_binding(capture_plan_binding)
    first_result = _mapping(results[0], label="first operator result")
    operator_code = _code_identity(
        first_result["operator_code_identity"],
        label="source release operator code",
        expected_path=OPERATOR_MODULE_PATH,
    )
    if any(
        _mapping(result, label="operator result").get("capture_plan_binding") != plan
        or _mapping(result, label="operator result").get("operator_code_identity")
        != operator_code
        for result in results
    ):
        _fail("terminal source release mixes plan or operator code identities")
    normalized_namespace = _namespace(namespace, label="source release namespace")
    for ordinal, member in enumerate(members):
        slate_id = member["slate"]["slate_id"]
        prefix = f"{normalized_namespace}source-task-{ordinal:02d}-{slate_id}/"
        result = _mapping(results[ordinal], label=f"operator result[{ordinal}]")
        if (
            result.get("output_prefix") != prefix
            or member["source_export_identity"]["uri"]
            != f"{prefix}matchup-source-export.json"
            or member["capture_receipt_identity"]["uri"]
            != f"{prefix}matchup-capture-receipt.json"
            or member["operator_result_identity"]["uri"]
            != f"{prefix}matchup-operator-result.json"
        ):
            _fail("terminal source member URI differs from fixed namespace law")
    all_output_uris = [
        str(member[field]["uri"])
        for member in members
        for field in (
            "source_export_identity", "capture_receipt_identity",
            "operator_result_identity",
        )
    ]
    if len(all_output_uris) != len(set(all_output_uris)):
        _fail("terminal source release repeats a member output URI")
    body: dict[str, object] = {
        "schema_version": MATCHUP_SOURCE_RELEASE_SCHEMA,
        "release_id": _identifier(release_id, label="matchup source release ID"),
        "publication_mode": source.PUBLICATION_MODE,
        "authority_boundary": "matchup-source-mechanics-only",
        "namespace": normalized_namespace,
        "capture_plan_binding": plan,
        "producer_release_identity": producer_root_id,
        "producer_release_sha256": producer_root["producer_release_sha256"],
        "catalog_release_identity": producer_root["catalog_release_identity"],
        "accepted_candidate_release_identity": producer_root[
            "accepted_candidate_release_identity"
        ],
        "upstream_source_release_identity": producer_root[
            "upstream_source_release_identity"
        ],
        "operator_code_identity": operator_code,
        "task_count": TASK_COUNT,
        "entries": members,
        "entry_manifest_sha256": source.canonical_sha256(members),
        **_authority_policy(_RELEASE_TRUE_AUTHORITIES),
    }
    return _with_self_hash(body, field="matchup_source_release_sha256")


def validate_matchup_source_release_v1(value: object) -> dict[str, object]:
    """Validate the terminal root without following any member identity."""
    item = _mapping(value, label="matchup source release")
    fields = {
        "schema_version", "release_id", "publication_mode",
        "authority_boundary", "namespace", "capture_plan_binding",
        "producer_release_identity", "producer_release_sha256",
        "catalog_release_identity", "accepted_candidate_release_identity",
        "upstream_source_release_identity", "operator_code_identity",
        "task_count", "entries", "entry_manifest_sha256",
        "outcome_columns_read", "uses_realized_outcomes",
        *source.FALSE_AUTHORITY_FIELDS, "matchup_source_release_sha256",
    }
    _exact_keys(item, fields, label="matchup source release")
    _validate_self_hash(
        item, field="matchup_source_release_sha256",
        label="matchup source release",
    )
    _validate_policy(
        item, true_fields=_RELEASE_TRUE_AUTHORITIES,
        label="matchup source release",
    )
    namespace = _namespace(item["namespace"], label="source release namespace")
    entries = [
        _validate_member(value, expected_ordinal=ordinal)
        for ordinal, value in enumerate(
            _sequence(item["entries"], label="source release entries")
        )
    ]
    if (
        item["schema_version"] != MATCHUP_SOURCE_RELEASE_SCHEMA
        or item["publication_mode"] != source.PUBLICATION_MODE
        or item["authority_boundary"] != "matchup-source-mechanics-only"
        or item["task_count"] != TASK_COUNT
        or len(entries) != TASK_COUNT
        or item["entry_manifest_sha256"] != source.canonical_sha256(entries)
    ):
        _fail("matchup source release fixed 54-entry law differs")
    normalized = dict(item)
    normalized.update({
        "release_id": _identifier(item["release_id"], label="source release ID"),
        "namespace": namespace,
        "capture_plan_binding": _capture_plan_binding(
            item["capture_plan_binding"]
        ),
        "producer_release_identity": _identity(
            item["producer_release_identity"], label="producer release"
        ),
        "producer_release_sha256": _digest(
            item["producer_release_sha256"], label="producer release SHA"
        ),
        "catalog_release_identity": _identity(
            item["catalog_release_identity"], label="catalog release"
        ),
        "accepted_candidate_release_identity": _identity(
            item["accepted_candidate_release_identity"],
            label="accepted candidate release",
        ),
        "upstream_source_release_identity": _identity(
            item["upstream_source_release_identity"],
            label="upstream source release",
        ),
        "operator_code_identity": _code_identity(
            item["operator_code_identity"],
            label="source release operator code",
            expected_path=OPERATOR_MODULE_PATH,
        ),
        "entries": entries,
    })
    output_uris: list[str] = []
    for ordinal, member in enumerate(entries):
        if member["producer_release_identity"] != normalized[
            "producer_release_identity"
        ]:
            _fail("matchup source member producer release differs from root")
        slate_id = member["slate"]["slate_id"]
        prefix = f"{namespace}source-task-{ordinal:02d}-{slate_id}/"
        expected = {
            "source_export_identity": f"{prefix}matchup-source-export.json",
            "capture_receipt_identity": f"{prefix}matchup-capture-receipt.json",
            "operator_result_identity": f"{prefix}matchup-operator-result.json",
        }
        for field, uri in expected.items():
            if member[field]["uri"] != uri:
                _fail("matchup source release member URI law differs")
            output_uris.append(uri)
    if len(output_uris) != len(set(output_uris)):
        _fail("matchup source release repeats a member output URI")
    if source.canonical_json_bytes(normalized) != source.canonical_json_bytes(item):
        _fail("matchup source release canonical replay differs")
    return normalized


def _selected_producer_entry(
    producer_release: Mapping[str, object], *, ordinal: int,
) -> dict[str, object]:
    entries = _sequence(
        producer_release["entries"], label="producer release entries"
    )
    entry = _mapping(entries[ordinal], label="selected producer release entry")
    if entry.get("source_task_ordinal") != ordinal:
        _fail("selected producer release entry ordinal differs")
    return entry


def _validate_selected_candidate_catalog_binding(
    *,
    candidate_artifact: Mapping[str, object],
    structural_catalog: Mapping[str, object],
    member: Mapping[str, object],
    ordinal: int,
) -> None:
    catalog_player_ids = {
        str(player["id"]) for player in structural_catalog["players"]
    }
    candidate_player_ids = {
        str(player_id)
        for row in candidate_artifact["rows"]
        for player_id in row["player_ids"]
    }
    if (
        structural_catalog["source_task_ordinal"] != ordinal
        or structural_catalog["task_id"] != member["task_id"]
        or structural_catalog["slate"] != member["slate"]
        or candidate_artifact["source_task_ordinal"] != ordinal
        or not candidate_player_ids.issubset(catalog_player_ids)
    ):
        _fail("selected candidate artifact differs from catalog task/universe")


def _reopen_validated_matchup_source_release_ordinal_v1(
    *,
    release: Mapping[str, object],
    ordinal: int,
    read_exact: ReadExact,
    producer_release: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Deep-replay one member from an already validated terminal root."""
    member = _mapping(
        release["entries"][ordinal], label="selected source release member"
    )
    if producer_release is None:
        normalized_producer_release = _producer_release_shape(
            _parse_exact(
                release["producer_release_identity"],
                read_exact=read_exact,
                label="component producer release",
            ),
            identity=release["producer_release_identity"],
        )
    else:
        normalized_producer_release = _producer_release_shape(
            producer_release,
            identity=release["producer_release_identity"],
        )
    producer_entry = _selected_producer_entry(
        normalized_producer_release, ordinal=ordinal
    )
    if (
        normalized_producer_release["producer_release_sha256"]
        != release["producer_release_sha256"]
        or normalized_producer_release["catalog_release_identity"]
        != release["catalog_release_identity"]
        or normalized_producer_release["accepted_candidate_release_identity"]
        != release["accepted_candidate_release_identity"]
        or normalized_producer_release["upstream_source_release_identity"]
        != release["upstream_source_release_identity"]
        or source.canonical_sha256(producer_entry)
        != member["producer_release_entry_sha256"]
        or producer_entry.get("slate") != member["slate"]
        or producer_entry.get("lock_time_utc") != member["lock_time_utc"]
        or producer_entry.get("catalog_identity")
        != member["catalog_identity"]
        or producer_entry.get("candidate_artifact_identity")
        != member["candidate_artifact_identity"]
        or producer_entry.get("producer_receipt_identity")
        != member["producer_receipt_identity"]
        or producer_entry.get("input_bundle_identity")
        != member["input_bundle_identity"]
    ):
        _fail("terminal source root differs from producer release")

    catalog = source.validate_structural_catalog_v2(_parse_exact(
        member["catalog_identity"], read_exact=read_exact,
        label="selected structural catalog",
    ))
    _bind_body(catalog, member["catalog_identity"], label="selected catalog")
    candidate_artifact = source.validate_accepted_candidate_artifact_v1(
        _parse_exact(
            member["candidate_artifact_identity"],
            read_exact=read_exact,
            label="selected candidate artifact",
        )
    )
    _bind_body(
        candidate_artifact,
        member["candidate_artifact_identity"],
        label="selected candidate artifact",
    )
    _validate_selected_candidate_catalog_binding(
        candidate_artifact=candidate_artifact,
        structural_catalog=catalog,
        member=member,
        ordinal=ordinal,
    )
    input_bundle = _parse_exact(
        member["input_bundle_identity"],
        read_exact=read_exact,
        label="selected component input bundle",
    )
    try:
        input_bundle = producer.validate_component_input_bundle_v1(
            input_bundle,
            expected_catalog=catalog,
            expected_identity=member["input_bundle_identity"],
        )
    except producer.CorpusR6MatchupComponentProducerV1Error as exc:
        raise CorpusR6MatchupSourceReleaseV1Error(str(exc)) from exc
    producer_receipt = _basic_producer_receipt(
        _parse_exact(
            member["producer_receipt_identity"],
            read_exact=read_exact,
            label="selected component producer receipt",
        ),
        structural_catalog=catalog,
        catalog_identity=member["catalog_identity"],
        input_bundle=input_bundle,
        input_bundle_identity=member["input_bundle_identity"],
        producer_receipt_identity=member["producer_receipt_identity"],
    )
    source_export = validate_matchup_source_export_v2(
        _parse_exact(
            member["source_export_identity"],
            read_exact=read_exact,
            label="selected matchup source export",
        ),
        producer_receipt=producer_receipt,
        producer_receipt_identity=member["producer_receipt_identity"],
        input_bundle=input_bundle,
        input_bundle_identity=member["input_bundle_identity"],
        structural_catalog=catalog,
        catalog_identity=member["catalog_identity"],
    )
    capture_receipt = validate_matchup_capture_receipt_v2(
        _parse_exact(
            member["capture_receipt_identity"],
            read_exact=read_exact,
            label="selected matchup capture receipt",
        ),
        source_export=source_export,
        source_export_identity=member["source_export_identity"],
        producer_receipt=producer_receipt,
        producer_receipt_identity=member["producer_receipt_identity"],
        input_bundle=input_bundle,
        input_bundle_identity=member["input_bundle_identity"],
        structural_catalog=catalog,
        catalog_identity=member["catalog_identity"],
    )
    operator_result = validate_matchup_operator_result_v2(
        _parse_exact(
            member["operator_result_identity"],
            read_exact=read_exact,
            label="selected matchup operator result",
        ),
        source_export=source_export,
        source_export_identity=member["source_export_identity"],
        capture_receipt=capture_receipt,
        capture_receipt_identity=member["capture_receipt_identity"],
    )
    if (
        operator_result["capture_plan_binding"]
        != release["capture_plan_binding"]
        or operator_result["operator_code_identity"]
        != release["operator_code_identity"]
        or source_export["producer_release_identity"]
        != release["producer_release_identity"]
        or source_export["producer_receipt_identity"]
        != member["producer_receipt_identity"]
        or source_export["input_bundle_identity"]
        != member["input_bundle_identity"]
        or source_export["catalog_identity"] != member["catalog_identity"]
        or source_export["candidate_artifact_identity"]
        != member["candidate_artifact_identity"]
        or source_export["matchup_source_export_sha256"]
        != member["source_export_sha256"]
        or capture_receipt["matchup_capture_receipt_sha256"]
        != member["capture_receipt_sha256"]
        or operator_result["matchup_operator_result_sha256"]
        != member["operator_result_sha256"]
    ):
        _fail("selected terminal source member body hashes differ")
    return {
        "release": release,
        "member": member,
        "producer_release": normalized_producer_release,
        "producer_release_entry": producer_entry,
        "structural_catalog": catalog,
        "candidate_artifact": candidate_artifact,
        "producer_receipt": producer_receipt,
        "input_bundle": input_bundle,
        "source_export": source_export,
        "capture_receipt": capture_receipt,
        "operator_result": operator_result,
        "structural_players": catalog["players"],
        "annotation_rows": source_export["annotation_rows"],
    }


def reopen_matchup_source_release_ordinal_v1(
    *,
    release_identity: Mapping[str, object],
    source_task_ordinal: int,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-open one member selected only by ordinal from the pinned root.

    The terminal root authenticates the capture-plan file identity copied from
    every operator result.  This object-store reopener deliberately performs
    no repository or filesystem read; secure Git-blob replay of that fixed
    plan belongs to the ordinal-only production operator that created the
    results.
    """
    ordinal = _exact_int(
        source_task_ordinal, label="source release ordinal"
    )
    if ordinal >= TASK_COUNT:
        _fail("source release ordinal must be in 0..53")
    normalized_release_identity = _identity(
        release_identity, label="matchup source release root"
    )
    release = validate_matchup_source_release_v1(_parse_exact(
        normalized_release_identity,
        read_exact=read_exact,
        label="matchup source release root",
    ))
    if normalized_release_identity["uri"] != (
        f"{release['namespace']}matchup-source-release.json"
    ):
        _fail("matchup source release root URI differs from namespace")
    return {
        "release_identity": normalized_release_identity,
        **_reopen_validated_matchup_source_release_ordinal_v1(
            release=release,
            ordinal=ordinal,
            read_exact=read_exact,
        ),
    }


def publish_matchup_source_release_root_last_v1(
    *,
    release_id: str,
    namespace: str,
    capture_plan_binding: Mapping[str, object],
    producer_release: Mapping[str, object],
    producer_release_identity: Mapping[str, object],
    source_exports: Sequence[Mapping[str, object]],
    source_export_identities: Sequence[Mapping[str, object]],
    capture_receipts: Sequence[Mapping[str, object]],
    capture_receipt_identities: Sequence[Mapping[str, object]],
    operator_results: Sequence[Mapping[str, object]],
    operator_result_identities: Sequence[Mapping[str, object]],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Deep-replay all 54 members, then publish the terminal root last."""
    root = build_matchup_source_release_v1(
        release_id=release_id,
        namespace=namespace,
        capture_plan_binding=capture_plan_binding,
        producer_release=producer_release,
        producer_release_identity=producer_release_identity,
        source_exports=source_exports,
        source_export_identities=source_export_identities,
        capture_receipts=capture_receipts,
        capture_receipt_identities=capture_receipt_identities,
        operator_results=operator_results,
        operator_result_identities=operator_result_identities,
    )
    producer_expected = source.canonical_json_bytes(producer_release)
    producer_reopened = _producer_release_shape(
        _parse_exact(
            producer_release_identity,
            read_exact=read_exact,
            label="component producer release",
        ),
        identity=producer_release_identity,
    )
    if source.canonical_json_bytes(producer_reopened) != producer_expected:
        _fail("component producer release exact-reopened bytes differ")
    for ordinal in range(TASK_COUNT):
        _reopen_validated_matchup_source_release_ordinal_v1(
            release=root,
            ordinal=ordinal,
            read_exact=read_exact,
            producer_release=producer_reopened,
        )
    root_raw = source.canonical_json_bytes(root)
    root_uri = f"{root['namespace']}matchup-source-release.json"
    try:
        root_identity = _identity(
            publish_create_once(root_uri, root_raw),
            label="published matchup source release root",
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceReleaseV1Error(
            "matchup source release root publication failed"
        ) from exc
    if root_identity["uri"] != root_uri:
        _fail("published matchup source release root URI differs")
    _bind_body(root, root_identity, label="published matchup source release root")
    reopened_root = _parse_exact(
        root_identity,
        read_exact=read_exact,
        label="published matchup source release root",
    )
    if validate_matchup_source_release_v1(reopened_root) != root:
        _fail("published matchup source release root exact replay differs")
    return {"release": root, "release_identity": root_identity}


__all__ = [
    "CorpusR6MatchupSourceReleaseV1Error",
    "MATCHUP_CAPTURE_RECEIPT_SCHEMA",
    "MATCHUP_OPERATOR_RESULT_SCHEMA",
    "MATCHUP_SOURCE_EXPORT_SCHEMA",
    "MATCHUP_SOURCE_MEMBER_SCHEMA",
    "MATCHUP_SOURCE_RELEASE_SCHEMA",
    "OPERATOR_MODULE_PATH",
    "build_matchup_capture_receipt_v2",
    "build_matchup_operator_result_v2",
    "build_matchup_source_export_v2",
    "build_matchup_source_release_v1",
    "publish_matchup_source_release_root_last_v1",
    "reopen_matchup_source_release_ordinal_v1",
    "validate_matchup_capture_receipt_v2",
    "validate_matchup_operator_result_v2",
    "validate_matchup_source_export_v2",
    "validate_matchup_source_release_v1",
]
