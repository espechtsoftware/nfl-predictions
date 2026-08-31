"""Create-once materializer for one outcome-blind R6 matchup-source triple.

This is the concrete operator code path named by
``corpus_r6_matchup_source_release_v1.OPERATOR_MODULE_PATH``.  It projects a
validated component bundle into the three immutable objects consumed by the
terminal source-release contract: source export, capture receipt, and operator
result.  Every object is written create-once and exact-reopened before the
next object can be derived.

This leaf operator does not establish candidate-population authority.  The
54-slate candidate-authority batch orchestrator is the only intended public
caller; it supplies the candidate identity selected from its one cached,
fully replayed fixed-G0 root.  No score, outcome, graph, fill, retrieval,
promotion, deployment, or production-policy input is accepted here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from hashlib import sha256
import json
from typing import Final

from nfl_dfs.research import corpus_r6_matchup_source_release_v1 as release_v1
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


OPERATOR_SCHEMA: Final = "corpus-r6-matchup-source-operator/v2"
OPERATOR_MODULE_PATH: Final = release_v1.OPERATOR_MODULE_PATH
CREATE_ONCE_RESUME_POLICY: Final = (
    "same_source_commit_only;restore_exact_clean_commit_before_resume;"
    "generation_exact_reopen_and_byte_equality;"
    "different_bytes_fail_before_dependent_object"
)

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]


class CorpusR6MatchupSourceOperatorV2Error(ValueError):
    """One source triple could not be built and exact-reopened."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupSourceOperatorV2Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSourceOperatorV2Error(str(exc)) from exc


def _exact_json(
    identity_value: object,
    *,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6MatchupSourceOperatorV2Error(
            f"{label} exact reopen failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise CorpusR6MatchupSourceOperatorV2Error(
            f"{label} must be canonical JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if source.canonical_json_bytes(body) != raw:
        _fail(f"{label} canonical bytes differ")
    return body, identity


def _publish_json(
    body: Mapping[str, object],
    *,
    uri: str,
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    raw = source.canonical_json_bytes(body)
    try:
        identity = _identity(
            publish_create_once(uri, raw), label=f"published {label}"
        )
    except Exception as exc:
        raise CorpusR6MatchupSourceOperatorV2Error(
            f"{label} create-once publication failed"
        ) from exc
    if identity["uri"] != uri:
        _fail(f"published {label} URI differs")
    reopened, reopened_identity = _exact_json(
        identity, read_exact=read_exact, label=f"published {label}"
    )
    if source.canonical_json_bytes(reopened) != raw:
        _fail(f"published {label} exact reopen differs")
    return reopened, reopened_identity


def publish_matchup_source_triple_v2(
    *,
    source_task_ordinal: int,
    output_prefix: str,
    capture_plan_binding: Mapping[str, object],
    operator_code_identity: Mapping[str, object],
    producer_release_identity: Mapping[str, object],
    producer_receipt: Mapping[str, object],
    producer_receipt_identity: Mapping[str, object],
    input_bundle: Mapping[str, object],
    input_bundle_identity: Mapping[str, object],
    structural_catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    candidate_artifact_identity: Mapping[str, object],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Materialize or exactly resume one source triple in dependency order.

    A create-once callback may return a pre-existing generation only when its
    exact reopened bytes equal the deterministic request.  Any unequal or
    unreadable collision stops before the next dependent object is derived.
    Thus a crash after export or capture can be resumed safely without an
    overwrite, while a coherent-looking foreign prefix cannot be adopted.
    """
    if (
        type(source_task_ordinal) is not int
        or not 0 <= source_task_ordinal < source.TASK_COUNT
    ):
        _fail("source-task ordinal must be in 0..53")
    if not callable(publish_create_once) or not callable(read_exact):
        _fail("source triple requires create-once publisher and exact reader")
    try:
        retained_operator_code = source.normalize_code_identity_v2(
            operator_code_identity,
            expected_module_path=OPERATOR_MODULE_PATH,
            label="source operator code identity",
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSourceOperatorV2Error(str(exc)) from exc
    try:
        export = release_v1.build_matchup_source_export_v2(
            producer_release_identity=producer_release_identity,
            producer_receipt=producer_receipt,
            producer_receipt_identity=producer_receipt_identity,
            input_bundle=input_bundle,
            input_bundle_identity=input_bundle_identity,
            structural_catalog=structural_catalog,
            catalog_identity=catalog_identity,
            candidate_artifact_identity=candidate_artifact_identity,
        )
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceOperatorV2Error(str(exc)) from exc
    slate_id = str(export["slate"]["slate_id"])
    expected_suffix = f"source-task-{source_task_ordinal:02d}-{slate_id}/"
    if not output_prefix.endswith(expected_suffix):
        _fail("source triple output prefix differs from ordinal/slate")
    export, export_identity = _publish_json(
        export,
        uri=f"{output_prefix}matchup-source-export.json",
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="matchup source export",
    )
    try:
        capture = release_v1.build_matchup_capture_receipt_v2(
            source_export=export,
            source_export_identity=export_identity,
            producer_receipt=producer_receipt,
            producer_receipt_identity=producer_receipt_identity,
            input_bundle=input_bundle,
            input_bundle_identity=input_bundle_identity,
            structural_catalog=structural_catalog,
            catalog_identity=catalog_identity,
        )
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceOperatorV2Error(str(exc)) from exc
    capture, capture_identity = _publish_json(
        capture,
        uri=f"{output_prefix}matchup-capture-receipt.json",
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="matchup capture receipt",
    )
    try:
        result = release_v1.build_matchup_operator_result_v2(
            source_task_ordinal=source_task_ordinal,
            capture_plan_binding=capture_plan_binding,
            operator_code_identity=retained_operator_code,
            output_prefix=output_prefix,
            source_export=export,
            source_export_identity=export_identity,
            capture_receipt=capture,
            capture_receipt_identity=capture_identity,
        )
    except release_v1.CorpusR6MatchupSourceReleaseV1Error as exc:
        raise CorpusR6MatchupSourceOperatorV2Error(str(exc)) from exc
    result, result_identity = _publish_json(
        result,
        uri=f"{output_prefix}matchup-operator-result.json",
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="matchup operator result",
    )
    return {
        "schema_version": OPERATOR_SCHEMA,
        "source_task_ordinal": source_task_ordinal,
        "task_id": export["task_id"],
        "slate": export["slate"],
        "source_export": export,
        "source_export_identity": export_identity,
        "capture_receipt": capture,
        "capture_receipt_identity": capture_identity,
        "operator_result": result,
        "operator_result_identity": result_identity,
        "candidate_artifact_identity": _identity(
            candidate_artifact_identity, label="candidate artifact"
        ),
        "all_three_create_once_requested": True,
        "all_three_exact_reopened": True,
        "create_once_resume_policy": CREATE_ONCE_RESUME_POLICY,
        "same_commit_recovery_required": True,
        "recovery_source_commit_sha": retained_operator_code[
            "source_commit_sha"
        ],
        "partial_triple_exact_equal_resume_allowed": True,
        "every_returned_generation_exact_reopened_before_dependent": True,
        "different_bytes_collision_rejected": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "outcome_freedom_status": {
            "independent_source_lineage_attested": False,
            "outcome_free_authority": False,
            "promotion_eligible": False,
            "unattested_by_this_operator_boundary": True,
        },
        "promotion_eligible": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


__all__ = [
    "CREATE_ONCE_RESUME_POLICY",
    "CorpusR6MatchupSourceOperatorV2Error",
    "OPERATOR_MODULE_PATH",
    "OPERATOR_SCHEMA",
    "publish_matchup_source_triple_v2",
]
