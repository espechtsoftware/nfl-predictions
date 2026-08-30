"""Exact fixed-G0 authority for the R6 accepted-candidate population.

The matchup-source v2 candidate artifact is intentionally a small offline
contract: by itself it cannot prove that caller-supplied rosters came from an
accepted Foundry task.  This module closes that boundary.  It replays the
tracked August-23 G0 panel, exact-reopens every accepted task and all seven of
its result objects, and derives one complete cross-arm unique-roster union per
slate.  It never selects only the retained 80-entry books and never filters an
invalid or missing roster.

Publication is deliberately outside this module.  ``derive_*_material_v1``
returns exact artifact bytes for an outer create-once publisher.  The outer
boundary supplies the resulting generation identities to ``build_*_v1``,
which exact-reopens every supplied generation before emitting authority.
The catalog input is the fixed-URI terminal replay receipt licensed by the
tracked projection-successor final lock, which exact-reopens the preserved v2
lock and its failed-projection evidence, never a caller-selected release.  ``validate_*_v1``
then repeats every exact read, reopens all predecessors, re-derives the
complete bundle, and requires byte equality.

No public function accepts outcomes, score matrices, a cloud client, a graph
writer, a lineup selector, or downstream decision authority.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import json
from pathlib import Path
import re
from typing import Final

from nfl_dfs.research import corpus_extreme_tail_panel_execution as panel_execution
from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_adapter_v1 as catalog_adapter
from nfl_dfs.research import corpus_r6_player_catalog_fixed_g0_projection_successor_v1 as catalog_successor
from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1
from nfl_dfs.research import corpus_v12_import as v12_import
from nfl_dfs.research import residual_world_columns as rw


MATERIAL_SCHEMA: Final = "corpus-r6-fixed-g0-candidate-material/v1"
LINEAGE_SIDECAR_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-lineage-sidecar/v1"
)
SLATE_DERIVATION_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-slate-derivation/v1"
)
PANEL_DERIVATION_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-panel-derivation/v1"
)
AUTHORITY_BUNDLE_SCHEMA: Final = (
    "corpus-r6-fixed-g0-candidate-authority-bundle/v1"
)
FULL_UNION_LAW: Final = (
    "all-seven-accepted-arms-first-occurrence-unique-roster-union-v1"
)
LINEUP_ORDER_LAW: Final = "ascending-stable-per-slate-lineup-id"
LINEAGE_ORDER_LAW: Final = "arm-ordinal-then-visit-ordinal"
EXPECTED_ARM_COUNT: Final = 7
WORLD_SCHEDULE_SCHEMA: Final = legal.WORLD_SCHEDULE_SCHEMA
VISITS_PER_BLOCK: Final = legal.VISITS_PER_BLOCK
SALARY_CAP: Final = 50_000
CATALOG_REPLAY_RECEIPT_FILENAME: Final = "fixed-g0-replay-receipt.json"
_TASK_SOURCE_BINDING_FIELDS: Final = frozenset({
    "binding_sha256",
    "batch_manifest_sha256",
    "task_index",
    "task_sha256",
    "artifact_source_authority_completion_object_sha256",
    "artifact_source_authority_completion_sha256",
    "artifact_source_authority_task_sha256",
    "later_source_freeze_manifest_sha256",
    "world_artifact_receipt_set_sha256",
})
_CATALOG_REPLAY_FALSE_FIELDS: Final = (
    *catalog_v1.FALSE_AUTHORITY_FIELDS,
    "analytical_authority",
    "automatic_retry_licensed",
)
_CATALOG_REPLAY_FIELDS: Final = frozenset({
    "schema_version",
    "replay_id",
    "replay_scope",
    "pin_set_sha256",
    "tracked_root_binding",
    "official_publication_receipt_file",
    "official_publication_receipt_sha256",
    "adapter_review_binding",
    "lane_terminal_identities",
    "lane_completion_identities",
    "later_source_freeze_identity",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion_identity",
    "artifact_source_authority_completion_sha256",
    "derivation_code_identity",
    "catalog_namespace",
    "catalog_release_identity",
    "catalog_release_sha256",
    "task_count",
    "task_acceptance_body_count",
    "task_acceptance_body_manifest_sha256",
    "carrier_body_count",
    "carrier_body_manifest_sha256",
    "member_binding_manifest_sha256",
    "source_catalog_binding_manifest_sha256",
    "completion_binding_manifest_sha256",
    "structural_catalog_manifest_sha256",
    "catalog_identity_manifest_sha256",
    "accepted_panel_index_projection_only",
    "fresh_task_or_arm_body_revalidation_performed",
    "task_acceptance_bodies_reopened",
    "carrier_bodies_reopened",
    "source_completion_artifact_bodies_reopened",
    "world_matrix_bodies_reopened",
    "result_object_bodies_reopened",
    "execution_manifest_pin_required",
    "self_authorizing",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_CATALOG_REPLAY_FALSE_FIELDS,
    "replay_receipt_sha256",
})

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_CATALOG_SUCCESSOR_REVIEW_LOCK_COMMIT: Final = (
    "4c1559c2842e82eb02553669989a851cef3088ef"
)
_CATALOG_SUCCESSOR_FINAL_LOCK_COMMIT: Final = (
    "3c60aca22adbea768f24c3248385a44523dbb9bf"
)

ReadExact = Callable[[Mapping[str, object]], bytes]
GitHead = Callable[[Path], str]
GitBlob = Callable[[Path, str, str], bytes]
GitStatus = Callable[[Path, Sequence[str]], bytes]


class CorpusR6FixedG0CandidateAuthorityV1Error(ValueError):
    """The candidate release differs from its fixed-G0 predecessors."""


def _fail(message: str) -> None:
    raise CorpusR6FixedG0CandidateAuthorityV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _text(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be one nonempty canonical string")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _with_self_hash(
    body: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    result = dict(body)
    result[field] = source.canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label} {field}")
    unhashed = {key: item for key, item in value.items() if key != field}
    if source.canonical_sha256(unhashed) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _parse_canonical_json(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")

    def pairs(rows: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in rows:
            if key in result:
                _fail(f"{label} contains duplicate key {key!r}")
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        _fail(f"{label} contains non-finite value {value}")

    try:
        parsed = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(
            f"{label} is not valid JSON"
        ) from exc
    body = _mapping(parsed, label=label)
    if source.canonical_json_bytes(body) != raw:
        _fail(f"{label} bytes are not canonical JSON")
    return body


def _parse_tracked_canonical_json(
    raw: bytes, *, label: str,
) -> dict[str, object]:
    if type(raw) is not bytes or not raw or not raw.endswith(b"\n"):
        _fail(f"{label} must be one newline-terminated tracked JSON object")
    retained = raw[:-1]
    if not retained or retained.endswith(b"\n"):
        _fail(f"{label} newline law differs")
    return _parse_canonical_json(retained, label=label)


def _commit(value: object, *, label: str) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        _fail(f"{label} must be lowercase full Git commit")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        _fail(f"{label} fields differ")


def _require_false_fields(
    value: Mapping[str, object], fields: Sequence[str], *, label: str,
) -> None:
    differing = [field for field in fields if value.get(field) is not False]
    if differing:
        _fail(f"{label} carries non-false authorities {differing}")


def _historical_successor_focused_output(
    raw: bytes, *, expected_pass_count: int,
) -> dict[str, int]:
    """Validate the frozen pytest receipt using its reviewed case count."""

    if (
        type(raw) is not bytes
        or type(expected_pass_count) is not int
        or expected_pass_count < 1
    ):
        _fail("historical successor focused output differs")
    try:
        raw.decode("ascii")
    except UnicodeError as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(
            "historical successor focused output is not ASCII"
        ) from exc
    if not raw.endswith(b"\n"):
        _fail("historical successor focused output is incomplete")
    lines = raw[:-1].split(b"\n")
    if len(lines) < 2 or any(line == b"" for line in lines):
        _fail("historical successor focused output lines differ")
    completed = 0
    prior_percentage = -1
    for line in lines[:-1]:
        match = re.fullmatch(
            rb"(\.+)( +)\[([ ]{0,2})([1-9][0-9]?|100)%\]", line
        )
        if match is None:
            _fail("historical successor focused output progress differs")
        completed += len(match.group(1))
        percentage = int(match.group(4))
        if (
            len(match.group(3)) + len(match.group(4)) != 3
            or completed > expected_pass_count
            or percentage != completed * 100 // expected_pass_count
            or percentage <= prior_percentage
        ):
            _fail("historical successor focused output accounting differs")
        prior_percentage = percentage
    summary = lines[-1]
    if (
        completed != expected_pass_count
        or prior_percentage != 100
        or re.fullmatch(
            str(expected_pass_count).encode("ascii")
            + rb" passed in (?:0|[1-9][0-9]*)\.[0-9]{2}s",
            summary,
        )
        is None
    ):
        _fail("historical successor focused output summary differs")
    return {"passed_test_count": expected_pass_count, "exit_code": 0}


def _validate_historical_catalog_successor_review_lock(
    value: Mapping[str, object],
    *,
    implementation_commit: str,
    measurements: Sequence[Mapping[str, object]],
    evidence: Mapping[str, object],
    focused_output_file: Mapping[str, object],
    focused_raw: bytes,
) -> dict[str, object]:
    """Validate the reviewed lock under its frozen, not current, case census."""

    item = _mapping(value, label="historical catalog successor review lock")
    retained = _validate_self_hash(
        item,
        field="projection_successor_review_lock_sha256",
        label="historical catalog successor review lock",
    )
    adapter_count = item.get("expected_adapter_case_count")
    successor_count = item.get("expected_successor_case_count")
    pass_count = item.get("focused_test_passed_count")
    if (
        type(adapter_count) is not int
        or adapter_count < 0
        or type(successor_count) is not int
        or successor_count < 0
        or type(pass_count) is not int
        or pass_count < 1
        or pass_count != adapter_count + successor_count
    ):
        _fail("historical catalog successor reviewed case census differs")
    focused = _historical_successor_focused_output(
        focused_raw, expected_pass_count=pass_count
    )
    if (
        item.get("schema_version") != catalog_successor.REVIEW_LOCK_SCHEMA
        or item.get("implementation_commit_sha") != implementation_commit
        or item.get("implementation_measurements")
        != [dict(row) for row in measurements]
        or any(item.get(key) != expected for key, expected in evidence.items())
        or item.get("focused_test_output_file") != dict(focused_output_file)
        or item.get("focused_test_invocation_count") != 1
        or item.get("focused_test_passed_count")
        != focused["passed_test_count"]
        or item.get("independent_static_review_passed") is not True
        or item.get("p0_open_count") != 0
        or item.get("p1_open_count") != 0
        or item.get("p2_open_count") != 0
        or item.get("projection_attempt_count") != 1
        or item.get("first_projection_passed") is not False
        or item.get("corrected_projection_rerun_licensed") is not False
        or item.get("third_projection_attempt_licensed") is not False
        or item.get("projection_publication_licensed") is not False
        or item.get("gcs_mutation_licensed") is not False
        or item.get("world_matrix_bodies_read") is not False
        or item.get("result_object_bodies_read") is not False
        or item.get("outcome_columns_read") != []
        or any(
            item.get(field) is not False
            for field in catalog_successor._FALSE_AUTHORITY_FIELDS
        )
    ):
        _fail("historical catalog successor review lock differs")
    item["projection_successor_review_lock_sha256"] = retained
    return item


def _validate_historical_catalog_successor_final_lock(
    value: Mapping[str, object],
    *, review_lock_file: Mapping[str, object], review: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="historical catalog successor final lock")
    retained = _validate_self_hash(
        item,
        field="projection_successor_final_lock_sha256",
        label="historical catalog successor final lock",
    )
    if (
        item.get("schema_version") != catalog_successor.FINAL_LOCK_SCHEMA
        or item.get("evidence_source_commit_sha")
        != catalog_adapter.FIXED_SOURCE_COMMIT_SHA
        or item.get("implementation_commit_sha")
        != review.get("implementation_commit_sha")
        or item.get("implementation_measurements")
        != review.get("implementation_measurements")
        or item.get("projection_successor_review_lock_file")
        != dict(review_lock_file)
        or item.get("projection_successor_review_lock_internal_sha256")
        != review.get("projection_successor_review_lock_sha256")
        or item.get("old_final_lock_file") != review.get("old_final_lock_file")
        or item.get("projection_failure_report_file")
        != review.get("projection_failure_report_file")
        or item.get("focused_test_output_file")
        != review.get("focused_test_output_file")
        or item.get("focused_test_passed_count")
        != review.get("focused_test_passed_count")
        or item.get("corrected_projection_rerun_licensed") is not True
        or item.get("third_projection_attempt_licensed") is not False
        or item.get("projection_only_publication_licensed") is not True
        or item.get("gcs_create_once_required") is not True
        or item.get("gcs_exact_reopen_required") is not True
        or item.get("gcs_overwrite_licensed") is not False
        or item.get("world_matrix_bodies_read") is not False
        or item.get("result_object_bodies_read") is not False
        or item.get("outcome_columns_read") != []
        or any(
            item.get(field) is not False
            for field in catalog_successor._FALSE_AUTHORITY_FIELDS
        )
    ):
        _fail("historical catalog successor final lock differs")
    item["projection_successor_final_lock_sha256"] = retained
    return item


def _resolve_historical_catalog_successor_review_lock(
    *,
    repository: object,
    head: str,
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    """Reopen the immutable successor review without a false HEAD equality.

    The successor review describes the implementation that was reviewed at
    ``implementation_commit_sha``.  Later candidate consumers must therefore
    prove those measurements against that historical commit, while reopening
    the immutable review lock, evidence files, and focused-test receipt from
    the current tracked HEAD.  Requiring the historical implementation bytes
    to remain the current implementation bytes would turn every legitimate
    descendant change into a false authority failure.

    The current candidate implementation is bound separately by the v2 outer
    candidate authority, whose implementation measurement includes this v1
    module.  This historical reopener deliberately makes no claim about the
    equality of current and reviewed successor implementation bytes.
    """

    try:
        review_raw = repository.read_tracked(
            head, catalog_successor.REVIEW_LOCK_PATH
        )
        immutable_review_raw = repository.read_tracked(
            _CATALOG_SUCCESSOR_REVIEW_LOCK_COMMIT,
            catalog_successor.REVIEW_LOCK_PATH,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(
            "catalog successor review-lock tracked read failed"
        ) from exc
    if review_raw != immutable_review_raw:
        _fail("current catalog successor review lock differs from immutable lock")
    review_value = _parse_tracked_canonical_json(
        review_raw, label="tracked catalog successor review lock"
    )
    implementation_commit = _commit(
        review_value.get("implementation_commit_sha"),
        label="catalog successor reviewed implementation commit",
    )
    try:
        measurements = catalog_successor._normalize_measurements(
            review_value.get("implementation_measurements")
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(
            f"catalog successor historical measurements differ: {exc}"
        ) from exc
    for ordinal, measurement in enumerate(measurements):
        path = str(measurement["relative_path"])
        try:
            raw = repository.read_tracked(implementation_commit, path)
        except Exception as exc:
            raise CorpusR6FixedG0CandidateAuthorityV1Error(
                f"historical catalog successor implementation[{ordinal}] "
                "tracked read failed"
            ) from exc
        if (
            type(raw) is not bytes
            or len(raw) != measurement["bytes"]
            or sha256(raw).hexdigest() != measurement["sha256"]
        ):
            _fail(
                f"historical catalog successor implementation[{ordinal}] "
                "file binding differs"
            )

    try:
        evidence = catalog_successor.validate_successor_evidence_v1(
            repository=repository, head=head
        )
        focused_raw = repository.read_tracked(
            head, catalog_successor.FOCUSED_OUTPUT_PATH
        )
        focused_binding = {
            "relative_path": catalog_successor.FOCUSED_OUTPUT_PATH,
            "sha256": sha256(focused_raw).hexdigest(),
            "bytes": len(focused_raw),
        }
        review = _validate_historical_catalog_successor_review_lock(
            review_value,
            implementation_commit=implementation_commit,
            measurements=measurements,
            evidence=evidence,
            focused_output_file=focused_binding,
            focused_raw=focused_raw,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(
            f"catalog successor immutable review replay failed: {exc}"
        ) from exc
    return review, {
        "relative_path": catalog_successor.REVIEW_LOCK_PATH,
        "sha256": sha256(review_raw).hexdigest(),
        "bytes": len(review_raw),
    }, evidence


def _reopen_catalog_terminal_authority(
    *,
    repository_root: Path,
    catalog_replay_receipt_identity: Mapping[str, object],
    git_binding: Mapping[str, object],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    """Reopen the successor lock chain and its sole fixed-URI receipt."""
    head = _commit(git_head(repository_root), label="catalog authority Git HEAD")
    paths = [
        catalog_successor.FINAL_LOCK_PATH,
        catalog_successor.REVIEW_LOCK_PATH,
        catalog_successor.OLD_FINAL_LOCK_PATH,
        catalog_successor.FAILURE_REPORT_PATH,
        catalog_successor.FOCUSED_OUTPUT_PATH,
        *catalog_successor.IMPLEMENTATION_PATHS,
    ]
    try:
        status = git_status(repository_root, paths)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(
            "catalog successor authority Git status failed"
        ) from exc
    if type(status) is not bytes or status != b"":
        _fail("catalog successor authority must be tracked-clean")

    class _Repository:
        def read_tracked(self, commit: str, path: str) -> bytes:
            try:
                return git_blob(repository_root, commit, path)
            except Exception as exc:
                raise CorpusR6FixedG0CandidateAuthorityV1Error(
                    f"catalog successor tracked read failed: {path}"
                ) from exc

    repository = _Repository()
    try:
        review, review_file, evidence = (
            _resolve_historical_catalog_successor_review_lock(
                repository=repository, head=head
            )
        )
        final_lock_raw = repository.read_tracked(
            head, catalog_successor.FINAL_LOCK_PATH
        )
        immutable_final_lock_raw = repository.read_tracked(
            _CATALOG_SUCCESSOR_FINAL_LOCK_COMMIT,
            catalog_successor.FINAL_LOCK_PATH,
        )
        if final_lock_raw != immutable_final_lock_raw:
            _fail("current catalog successor final lock differs from immutable lock")
        final_lock = _validate_historical_catalog_successor_final_lock(
            _parse_tracked_canonical_json(
                final_lock_raw, label="catalog successor final lock"
            ),
            review_lock_file=review_file,
            review=review,
        )
        old_raw = repository.read_tracked(
            catalog_successor.OLD_FINAL_LOCK_COMMIT,
            catalog_successor.OLD_FINAL_LOCK_PATH,
        )
        old_final = catalog_successor._validate_old_final_lock(
            _parse_tracked_canonical_json(
                old_raw, label="preserved catalog terminal lock"
            )
        )
        base_review = catalog_successor._adapter_review_from_old_final(old_final)
        catalog_adapter._reopen_adapter_review_binding_v1(
            review=base_review, read_tracked=repository.read_tracked
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(
            f"catalog successor authority replay failed: {exc}"
        ) from exc
    # The final lock's evidence commit identifies the historical catalog
    # adapter review.  ``git_binding`` identifies the advancing tracked G0
    # panel HEAD and is exact-checked independently by ``_validate_catalog_root``.
    # Equating those commits would invalidate every legitimate descendant.
    if (
        final_lock.get("schema_version") != catalog_successor.FINAL_LOCK_SCHEMA
        or final_lock.get("projection_release_command")
        != list(catalog_successor.PROJECTION_COMMAND)
        or final_lock.get("old_final_lock_file")
        != evidence.get("old_final_lock_file")
        or final_lock.get("projection_failure_report_file")
        != evidence.get("projection_failure_report_file")
    ):
        _fail("catalog successor final-lock authority differs")
    final_lock_sha = _digest(
        final_lock.get("projection_successor_final_lock_sha256"),
        label="catalog successor final-lock internal SHA",
    )
    final_lock_binding = {
        "relative_path": catalog_successor.FINAL_LOCK_PATH,
        "git_commit_sha": head,
        "sha256": sha256(final_lock_raw).hexdigest(),
        "bytes": len(final_lock_raw),
        "projection_successor_final_lock_sha256": final_lock_sha,
    }

    normalized_receipt_identity, replay_receipt = _exact_read_object(
        catalog_replay_receipt_identity,
        read_exact=read_exact,
        label="fixed-G0 catalog replay receipt",
    )
    expected_receipt_uri = (
        f"{catalog_adapter.FIXED_CATALOG_NAMESPACE}"
        f"{CATALOG_REPLAY_RECEIPT_FILENAME}"
    )
    if normalized_receipt_identity["uri"] != expected_receipt_uri:
        _fail("catalog replay receipt URI differs from terminal namespace")
    _exact_keys(
        replay_receipt,
        _CATALOG_REPLAY_FIELDS,
        label="fixed-G0 catalog replay receipt",
    )
    _validate_self_hash(
        replay_receipt,
        field="replay_receipt_sha256",
        label="fixed-G0 catalog replay receipt",
    )
    _require_false_fields(
        replay_receipt,
        _CATALOG_REPLAY_FALSE_FIELDS,
        label="fixed-G0 catalog replay receipt",
    )
    if (
        replay_receipt.get("schema_version") != catalog_adapter.ADAPTER_SCHEMA
        or replay_receipt.get("catalog_namespace")
        != catalog_adapter.FIXED_CATALOG_NAMESPACE
        or replay_receipt.get("task_count") != source.TASK_COUNT
        or replay_receipt.get("task_acceptance_body_count")
        != source.TASK_COUNT
        or replay_receipt.get("carrier_body_count") != source.TASK_COUNT
        or replay_receipt.get("accepted_panel_index_projection_only") is not True
        or replay_receipt.get("fresh_task_or_arm_body_revalidation_performed")
        is not True
        or replay_receipt.get("task_acceptance_bodies_reopened") is not True
        or replay_receipt.get("carrier_bodies_reopened") is not True
        or replay_receipt.get("source_completion_artifact_bodies_reopened")
        is not False
        or replay_receipt.get("world_matrix_bodies_reopened") is not False
        or replay_receipt.get("result_object_bodies_reopened") is not False
        or replay_receipt.get("execution_manifest_pin_required") is not True
        or replay_receipt.get("self_authorizing") is not False
        or replay_receipt.get("outcome_columns_read") != []
        or replay_receipt.get("uses_realized_outcomes") is not False
    ):
        _fail("catalog replay receipt terminal authority differs")
    return final_lock_binding, normalized_receipt_identity, replay_receipt


def _exact_read_object(
    identity: Mapping[str, object],
    *,
    read_exact: ReadExact,
    label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    normalized = source.normalize_object_identity_v2(
        identity, label=f"{label} identity"
    )
    try:
        raw = read_exact(normalized)
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(
            f"{label} exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    return normalized, _parse_canonical_json(raw, label=label)


def _bind_body_identity(
    body: Mapping[str, object],
    identity: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    normalized = source.normalize_object_identity_v2(
        identity, label=f"{label} identity"
    )
    raw = source.canonical_json_bytes(body)
    if (
        normalized["bytes"] != len(raw)
        or normalized["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} differs from its exact object identity")
    return normalized


def _reopen_task_world_schedule(
    *,
    source_task_ordinal: int,
    imported: v12_import.V12ImportedTask,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    """Exact-open the carrier-bound schedule and retain this task's worlds.

    The accepted carrier is the only authority allowed to choose the schedule
    object.  This replay is deliberately narrower than recomputing the ranked
    worlds: it proves the exact occurrence coordinates used by every accepted
    arm, while the accepted Foundry task remains the ranking-law authority.
    """
    label = f"task[{source_task_ordinal}] world schedule"
    carrier = _mapping(imported.carrier, label=f"task[{source_task_ordinal}] carrier")
    identity, schedule_object = _exact_read_object(
        _mapping(carrier.get("world_schedule"), label=f"{label} identity"),
        read_exact=read_exact,
        label=label,
    )
    expected_top = {
        "schema",
        "method",
        "score_accumulator",
        "tie_break",
        "block_order",
        "source_worlds_per_block",
        "visits_per_block",
        "slates",
    }
    if (
        set(schedule_object) != expected_top
        or schedule_object.get("schema") != WORLD_SCHEDULE_SCHEMA
        or schedule_object.get("method") != "top-total-slate-player-draw-desc"
        or schedule_object.get("score_accumulator")
        != "float64-sum-of-all-slate-player-draws"
        or schedule_object.get("tie_break") != "world-index-ascending-stable"
        or schedule_object.get("block_order") != list(rw.WORLD_BLOCKS)
        or schedule_object.get("source_worlds_per_block") != rw.WORLDS_PER_BLOCK
        or schedule_object.get("visits_per_block") != VISITS_PER_BLOCK
    ):
        _fail(f"{label} law/schema differs")
    rows = _sequence(schedule_object.get("slates"), label=f"{label} slates")
    if not rows:
        _fail(f"{label} contains no slate rows")
    expected_row_keys = {
        "task_index",
        "season",
        "week",
        "slate_id",
        "later_source_freeze_manifest_sha256",
        "world_artifact_receipt_set_sha256",
        "blocks",
        "visit_schedule_sha256",
    }
    expected_lane = catalog_v1.expected_lane_for_source_task(source_task_ordinal)
    expected_slate = catalog_v1.expected_slate_for_source_task(source_task_ordinal)
    retained_row: dict[str, object] | None = None
    retained_schedule: list[dict[str, object]] | None = None
    seen_task_indexes: set[int] = set()
    for row_ordinal, raw_row in enumerate(rows):
        row = _mapping(raw_row, label=f"{label} slate[{row_ordinal}]")
        task_index = row.get("task_index")
        if (
            set(row) != expected_row_keys
            or type(task_index) is not int
            or task_index < 0
            or task_index in seen_task_indexes
        ):
            _fail(f"{label} slate[{row_ordinal}] fields/task index differ")
        seen_task_indexes.add(task_index)
        for field in (
            "later_source_freeze_manifest_sha256",
            "world_artifact_receipt_set_sha256",
            "visit_schedule_sha256",
        ):
            _digest(row.get(field), label=f"{label} slate[{row_ordinal}] {field}")
        block_rows = _sequence(
            row.get("blocks"), label=f"{label} slate[{row_ordinal}] blocks"
        )
        if len(block_rows) != len(rw.WORLD_BLOCKS):
            _fail(f"{label} slate[{row_ordinal}] block count differs")
        flattened: list[dict[str, object]] = []
        for block_id, raw_block in zip(rw.WORLD_BLOCKS, block_rows, strict=True):
            block = _mapping(
                raw_block, label=f"{label} slate[{row_ordinal}] {block_id}"
            )
            indices = _sequence(
                block.get("world_indices"),
                label=f"{label} slate[{row_ordinal}] {block_id} indices",
            )
            if (
                set(block) != {"block", "world_indices"}
                or block.get("block") != block_id
                or len(indices) != VISITS_PER_BLOCK
                or any(type(index) is not int for index in indices)
                or len(set(indices)) != len(indices)
                or any(index < 0 or index >= rw.WORLDS_PER_BLOCK for index in indices)
            ):
                _fail(f"{label} slate[{row_ordinal}] {block_id} dose/order differs")
            flattened.extend(
                {"block": block_id, "index": index} for index in indices
            )
        if row["visit_schedule_sha256"] != source.canonical_sha256(flattened):
            _fail(f"{label} slate[{row_ordinal}] self-hash differs")
        if task_index == expected_lane["task_ordinal"]:
            if retained_row is not None:
                _fail(f"{label} contains duplicate target rows")
            retained_row = row
            retained_schedule = flattened
    if retained_row is None or retained_schedule is None:
        _fail(f"{label} target task row is absent")
    if (
        retained_row.get("season") != expected_slate["season"]
        or retained_row.get("week") != expected_slate["week"]
        or retained_row.get("slate_id") != expected_slate["slate_id"]
        or retained_row.get("later_source_freeze_manifest_sha256")
        != carrier.get("later_source_freeze_manifest_sha256")
        or retained_row.get("world_artifact_receipt_set_sha256")
        != carrier.get("world_artifact_receipt_set_sha256")
    ):
        _fail(f"{label} target authority differs from accepted carrier")
    return identity, retained_row, retained_schedule


def _member_binding(
    member: Mapping[str, object], *, source_task_ordinal: int,
) -> dict[str, object]:
    expected_slate = catalog_v1.expected_slate_for_source_task(source_task_ordinal)
    expected_lane = catalog_v1.expected_lane_for_source_task(source_task_ordinal)
    item = _mapping(member, label=f"panel member[{source_task_ordinal}]")
    if (
        item.get("source_task_ordinal") != source_task_ordinal
        or item.get("slate_id") != expected_slate["slate_id"]
        or any(item.get(field) != value for field, value in expected_lane.items())
    ):
        _fail(f"panel member[{source_task_ordinal}] differs from fixed order")
    return catalog_v1.normalize_member_binding({
        "lane_id": expected_lane["lane_id"],
        "lane_ordinal": expected_lane["lane_ordinal"],
        "task_ordinal": expected_lane["task_ordinal"],
        "source_task_ordinal": source_task_ordinal,
        "task_id": catalog_v1.task_id_for_source_task(source_task_ordinal),
        "slate_id": expected_slate["slate_id"],
        "accepted_slate_membership_sha256": source.canonical_sha256(item),
        "task_acceptance_identity": item.get("task_acceptance_identity"),
        "carrier_identity": item.get("carrier_identity"),
        "source_task_authority_sha256": item.get(
            "source_task_authority_sha256"
        ),
    })


def _validate_catalog_root(
    root: Mapping[str, object],
    *,
    panel_identity: Mapping[str, object],
    panel: Mapping[str, object],
    git_binding: Mapping[str, object],
) -> dict[str, object]:
    normalized = catalog_v1.normalize_tracked_root_binding(root)
    if (
        normalized["g0_authority_lock_schema"]
        != panel_execution.G0_AUTHORITY_LOCK_SCHEMA
        or normalized["g0_authority_lock_relative_path"]
        != panel_execution.FROZEN_G0_AUTHORITY_LOCK_RELATIVE_PATH
        or normalized["g0_authority_lock_file_sha256"] != git_binding.get("sha256")
        or normalized["g0_authority_lock_sha256"]
        != git_binding.get("g0_authority_lock_sha256")
        or normalized["source_commit_sha"] != git_binding.get("source_commit_sha")
        or normalized["panel_object_identity"] != panel_identity
        or normalized["panel_index_sha256"] != panel.get("panel_index_sha256")
        or normalized["accepted_slate_count"] != source.TASK_COUNT
    ):
        _fail("catalog release differs from the exact tracked G0 root")
    return normalized


def _reopen_catalog_panel(
    *,
    catalog_release_identity: Mapping[str, object],
    catalog_replay_receipt: Mapping[str, object],
    panel_identity: Mapping[str, object],
    panel: Mapping[str, object],
    members: Sequence[Mapping[str, object]],
    git_binding: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    normalized_release_identity, raw_release = _exact_read_object(
        catalog_release_identity,
        read_exact=read_exact,
        label="fixed-G0 structural catalog release",
    )
    try:
        release = catalog_v1.validate_release_v1(
            raw_release,
            expected_catalog_namespace=catalog_adapter.FIXED_CATALOG_NAMESPACE,
        )
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(str(exc)) from exc
    expected_release_uri = (
        f"{catalog_adapter.FIXED_CATALOG_NAMESPACE}catalog-release.json"
    )
    if (
        normalized_release_identity["uri"] != expected_release_uri
        or release["catalog_namespace"]
        != catalog_adapter.FIXED_CATALOG_NAMESPACE
        or release["release_id"] != catalog_adapter.FIXED_RELEASE_ID
        or normalized_release_identity
        != source.normalize_object_identity_v2(
            catalog_replay_receipt.get("catalog_release_identity"),
            label="terminal catalog release identity",
        )
        or release["release_sha256"]
        != catalog_replay_receipt.get("catalog_release_sha256")
    ):
        _fail("catalog release differs from terminal replay authority")
    root = _validate_catalog_root(
        _mapping(release["tracked_root_binding"], label="catalog tracked root"),
        panel_identity=panel_identity,
        panel=panel,
        git_binding=git_binding,
    )
    entries = _sequence(release["entries"], label="catalog release entries")
    if len(entries) != source.TASK_COUNT or len(members) != source.TASK_COUNT:
        _fail("catalog/panel must contain exactly 54 ordered members")

    catalogs: list[dict[str, object]] = []
    catalog_bindings: list[dict[str, object]] = []
    member_bindings: list[dict[str, object]] = []
    source_bindings: list[dict[str, object]] = []
    completion_bindings: list[dict[str, object]] = []
    common_code_identity: dict[str, object] | None = None
    for source_ordinal, (entry_value, member_value) in enumerate(
        zip(entries, members, strict=True)
    ):
        entry = _mapping(entry_value, label=f"catalog release entry[{source_ordinal}]")
        member = _mapping(member_value, label=f"panel member[{source_ordinal}]")
        binding = _member_binding(member, source_task_ordinal=source_ordinal)
        expected_slate = catalog_v1.expected_slate_for_source_task(source_ordinal)
        expected_lane = catalog_v1.expected_lane_for_source_task(source_ordinal)
        if (
            entry.get("source_task_ordinal") != source_ordinal
            or entry.get("task_id")
            != catalog_v1.task_id_for_source_task(source_ordinal)
            or entry.get("slate") != expected_slate
            or any(entry.get(field) != value for field, value in expected_lane.items())
            or entry.get("accepted_slate_membership_sha256")
            != binding["accepted_slate_membership_sha256"]
            or entry.get("source_task_authority_sha256")
            != binding["source_task_authority_sha256"]
        ):
            _fail(f"catalog release entry[{source_ordinal}] differs from G0 member")
        catalog_identity, raw_catalog = _exact_read_object(
            _mapping(entry["catalog_identity"], label="catalog identity"),
            read_exact=read_exact,
            label=f"structural catalog[{source_ordinal}]",
        )
        try:
            structural_catalog = source.validate_structural_catalog_v2(raw_catalog)
        except Exception as exc:
            raise CorpusR6FixedG0CandidateAuthorityV1Error(str(exc)) from exc
        derivation_identity = source.normalize_object_identity_v2(
            entry["derivation_receipt_identity"],
            label=f"catalog derivation identity[{source_ordinal}]",
        )
        if structural_catalog["source_authority"] != derivation_identity:
            _fail(f"catalog[{source_ordinal}] source authority differs from release")
        _, raw_derivation = _exact_read_object(
            derivation_identity,
            read_exact=read_exact,
            label=f"catalog derivation[{source_ordinal}]",
        )
        try:
            derivation = catalog_v1.validate_derivation_receipt_v1(
                raw_derivation,
                expected_tracked_root_binding=root,
                expected_member_binding=binding,
                expected_source_catalog_binding=raw_derivation.get(
                    "source_catalog_binding"
                ),
                expected_completion_binding=raw_derivation.get(
                    "artifact_source_completion_binding"
                ),
                expected_derivation_code_identity=release[
                    "derivation_code_identity"
                ],
            )
        except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
            raise CorpusR6FixedG0CandidateAuthorityV1Error(str(exc)) from exc
        source_binding = catalog_v1.normalize_source_catalog_binding(
            derivation["source_catalog_binding"]
        )
        completion_binding = catalog_v1.normalize_completion_binding(
            derivation["artifact_source_completion_binding"]
        )
        code_identity = catalog_v1.normalize_code_identity(
            derivation["derivation_code_identity"]
        )
        if common_code_identity is None:
            common_code_identity = code_identity
        if (
            structural_catalog["source_task_ordinal"] != source_ordinal
            or structural_catalog["task_id"] != entry["task_id"]
            or structural_catalog["slate"] != expected_slate
            or structural_catalog["task_ordinal"] != expected_lane["task_ordinal"]
            or structural_catalog["source_catalog_sha256"]
            != derivation["structural_projection_sha256"]
            or structural_catalog["player_count"] != derivation["player_count"]
            or structural_catalog["ordered_player_ids_sha256"]
            != derivation["ordered_player_ids_sha256"]
            or entry["source_catalog_sha256"]
            != structural_catalog["source_catalog_sha256"]
            or entry["player_count"] != structural_catalog["player_count"]
            or entry["ordered_player_ids_sha256"]
            != structural_catalog["ordered_player_ids_sha256"]
            or source_binding["source_task_ordinal"] != source_ordinal
            or completion_binding["source_task_ordinal"] != source_ordinal
            or source_binding["catalog_sha256"]
            != structural_catalog["source_catalog_sha256"]
            or source_binding["catalog_player_count"]
            != structural_catalog["player_count"]
            or source_binding["catalog_player_ids_sha256"]
            != structural_catalog["ordered_player_ids_sha256"]
            or completion_binding["task_source_authority_sha256"]
            != binding["source_task_authority_sha256"]
            or code_identity != common_code_identity
            or code_identity["source_commit_sha"] != root["source_commit_sha"]
        ):
            _fail(f"catalog[{source_ordinal}] exact derivation closure differs")
        catalogs.append(structural_catalog)
        member_bindings.append(binding)
        source_bindings.append(source_binding)
        completion_bindings.append(completion_binding)
        catalog_bindings.append({
            "catalog_identity": catalog_identity,
            "catalog_sha256": structural_catalog["player_catalog_sha256"],
            "derivation_identity": derivation_identity,
            "derivation_sha256": derivation["derivation_sha256"],
            "member_binding": binding,
            "source_catalog_binding": source_binding,
            "completion_binding": completion_binding,
            "derivation_code_identity": code_identity,
        })
    if common_code_identity is None:
        _fail("catalog release omitted its derivation-code authority")
    try:
        reopened = catalog_v1.reopen_release_v1(
            release_identity=normalized_release_identity,
            expected_catalog_namespace=catalog_adapter.FIXED_CATALOG_NAMESPACE,
            expected_tracked_root_binding=root,
            expected_member_bindings=member_bindings,
            expected_source_catalog_bindings=source_bindings,
            expected_completion_bindings=completion_bindings,
            expected_derivation_code_identity=common_code_identity,
            read_exact=read_exact,
        )
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(str(exc)) from exc
    if source.canonical_json_bytes(reopened["release"]) != source.canonical_json_bytes(
        release
    ):
        _fail("catalog release differs from full external authority replay")
    if (
        release["tracked_root_binding"]
        != catalog_replay_receipt.get("tracked_root_binding")
        or release["later_source_freeze_identity"]
        != catalog_replay_receipt.get("later_source_freeze_identity")
        or release["later_source_freeze_manifest_sha256"]
        != catalog_replay_receipt.get("later_source_freeze_manifest_sha256")
        or release["artifact_source_authority_completion_identity"]
        != catalog_replay_receipt.get(
            "artifact_source_authority_completion_identity"
        )
        or release["artifact_source_authority_completion_sha256"]
        != catalog_replay_receipt.get(
            "artifact_source_authority_completion_sha256"
        )
        or release["derivation_code_identity"]
        != catalog_replay_receipt.get("derivation_code_identity")
        or source.canonical_sha256(member_bindings)
        != catalog_replay_receipt.get("member_binding_manifest_sha256")
        or source.canonical_sha256(source_bindings)
        != catalog_replay_receipt.get("source_catalog_binding_manifest_sha256")
        or source.canonical_sha256(completion_bindings)
        != catalog_replay_receipt.get("completion_binding_manifest_sha256")
        or source.canonical_sha256([catalog["players"] for catalog in catalogs])
        != catalog_replay_receipt.get("structural_catalog_manifest_sha256")
        or source.canonical_sha256([
            binding["catalog_identity"] for binding in catalog_bindings
        ])
        != catalog_replay_receipt.get("catalog_identity_manifest_sha256")
    ):
        _fail("catalog release lattice differs from terminal replay receipt")
    return release, normalized_release_identity, catalogs, catalog_bindings


def _canonical_roster(value: object, *, label: str) -> tuple[str, ...]:
    raw = _sequence(value, label=label)
    roster = tuple(_text(player, label=f"{label} player") for player in raw)
    if (
        len(roster) != 9
        or len(set(roster)) != 9
        or list(roster) != sorted(roster)
    ):
        _fail(f"{label} must contain nine unique canonical sorted player IDs")
    return roster


def _validate_roster_against_catalog(
    roster: Sequence[str],
    *,
    catalog: Mapping[str, object],
    label: str,
) -> None:
    players = _sequence(catalog["players"], label="structural catalog players")
    positions = {
        str(_mapping(player, label="structural player")["id"]): str(
            _mapping(player, label="structural player")["pos"]
        )
        for player in players
    }
    salaries = {
        str(_mapping(player, label="structural player")["id"]): int(
            _mapping(player, label="structural player")["salary"]
        )
        for player in players
    }
    if any(player_id not in positions for player_id in roster):
        _fail(f"{label} contains a player outside the exact structural catalog")
    roster_positions = [positions[player_id] for player_id in roster]
    if (
        len(roster) != 9
        or len(set(roster)) != 9
        or sum(position == "QB" for position in roster_positions) != 1
        or sum(position == "DST" for position in roster_positions) != 1
        or sum(position in {"RB", "WR", "TE"} for position in roster_positions)
        != 7
        or not 2 <= sum(position == "RB" for position in roster_positions) <= 3
        or not 3 <= sum(position == "WR" for position in roster_positions) <= 4
        or not 1 <= sum(position == "TE" for position in roster_positions) <= 2
        or sum(salaries[player_id] for player_id in roster) > SALARY_CAP
    ):
        _fail(f"{label} differs from DraftKings classic roster/salary law")


def _first_occurrence_unique(
    visits: Sequence[tuple[str, ...]],
) -> tuple[list[tuple[str, ...]], list[int]]:
    unique: list[tuple[str, ...]] = []
    first: list[int] = []
    seen: set[tuple[str, ...]] = set()
    for visit_ordinal, roster in enumerate(visits):
        if roster in seen:
            continue
        seen.add(roster)
        unique.append(roster)
        first.append(visit_ordinal)
    return unique, first


def _validate_result_task_source_binding(
    *,
    source_task_ordinal: int,
    arm_ordinal: int,
    body: Mapping[str, object],
    imported: v12_import.V12ImportedTask,
    catalog_binding: Mapping[str, object],
    common_binding_sha256: str | None,
) -> str:
    label = f"task[{source_task_ordinal}] arm[{arm_ordinal}]"
    result_binding = _mapping(
        body.get("task_source_binding"), label=f"{label} task-source binding"
    )
    _exact_keys(
        result_binding,
        _TASK_SOURCE_BINDING_FIELDS,
        label=f"{label} task-source binding",
    )
    for field in _TASK_SOURCE_BINDING_FIELDS - {"task_index"}:
        _digest(result_binding.get(field), label=f"{label} {field}")
    carrier = _mapping(imported.carrier, label=f"task[{source_task_ordinal}] carrier")
    expected_lane = catalog_v1.expected_lane_for_source_task(source_task_ordinal)
    source_binding = catalog_v1.normalize_source_catalog_binding(
        catalog_binding.get("source_catalog_binding")
    )
    completion_binding = catalog_v1.normalize_completion_binding(
        catalog_binding.get("completion_binding")
    )
    completion_identity = source.normalize_object_identity_v2(
        completion_binding["artifact_source_authority_completion_identity"],
        label=f"{label} completion identity",
    )
    carrier_completion_identity = source.normalize_object_identity_v2(
        carrier.get("artifact_source_authority_completion"),
        label=f"{label} carrier completion identity",
    )
    raw_worlds = _mapping(
        carrier.get("world_artifact_receipts"),
        label=f"task[{source_task_ordinal}] carrier world receipts",
    )
    if set(raw_worlds) != set(batch.TASK_WORLD_SOURCE_ROLES):
        _fail(f"task[{source_task_ordinal}] carrier world roles differ")
    worlds = {
        role: source.normalize_object_identity_v2(
            raw_worlds[role], label=f"{label} world receipt {role}"
        )
        for role in batch.TASK_WORLD_SOURCE_ROLES
    }
    artifact_sha_by_block = _mapping(
        body.get("artifact_sha256_by_block"),
        label=f"{label} artifact SHA map",
    )
    expected_artifact_sha_by_block = {
        block: worlds[role]["sha256"]
        for block, role in zip(
            rw.WORLD_BLOCKS, batch.TASK_WORLD_SOURCE_ROLES, strict=True
        )
    }
    binding_sha = _digest(
        result_binding.get("binding_sha256"), label=f"{label} binding SHA"
    )
    if common_binding_sha256 is not None and binding_sha != common_binding_sha256:
        _fail(f"task[{source_task_ordinal}] arm task-source bindings differ")
    if (
        type(result_binding.get("task_index")) is not int
        or result_binding["task_index"] != expected_lane["task_ordinal"]
        or carrier.get("task_index") != expected_lane["task_ordinal"]
        or result_binding["batch_manifest_sha256"]
        != carrier.get("batch_manifest_sha256")
        or result_binding["task_sha256"] != carrier.get("task_sha256")
        or result_binding[
            "artifact_source_authority_completion_object_sha256"
        ]
        != completion_identity["sha256"]
        or carrier_completion_identity != completion_identity
        or result_binding["artifact_source_authority_completion_sha256"]
        != completion_binding["artifact_source_authority_completion_sha256"]
        or carrier.get("artifact_source_authority_completion_sha256")
        != completion_binding["artifact_source_authority_completion_sha256"]
        or result_binding["artifact_source_authority_task_sha256"]
        != completion_binding["task_source_authority_sha256"]
        or carrier.get("artifact_source_authority_task_sha256")
        != completion_binding["task_source_authority_sha256"]
        or result_binding["later_source_freeze_manifest_sha256"]
        != source_binding["later_source_freeze_manifest_sha256"]
        or body.get("later_source_freeze_manifest_sha256")
        != source_binding["later_source_freeze_manifest_sha256"]
        or carrier.get("later_source_freeze_manifest_sha256")
        != source_binding["later_source_freeze_manifest_sha256"]
        or result_binding["world_artifact_receipt_set_sha256"]
        != source.canonical_sha256(worlds)
        or carrier.get("world_artifact_receipt_set_sha256")
        != source.canonical_sha256(worlds)
        or artifact_sha_by_block != expected_artifact_sha_by_block
    ):
        _fail(f"{label} completion/source/internal/task hash chain differs")
    return binding_sha


def _derive_slate_material(
    *,
    source_task_ordinal: int,
    member: Mapping[str, object],
    catalog: Mapping[str, object],
    catalog_binding: Mapping[str, object],
    imported: v12_import.V12ImportedTask,
    world_schedule_identity: Mapping[str, object],
    world_schedule_row: Mapping[str, object],
    visit_schedule: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[str, object], dict[str, object]]:
    variants = list(imported.variant_results)
    if len(variants) != EXPECTED_ARM_COUNT:
        _fail(f"task[{source_task_ordinal}] does not contain exactly seven arms")
    expected_slate = catalog_v1.expected_slate_for_source_task(source_task_ordinal)
    compatibility = _mapping(
        imported.compatibility_receipt,
        label=f"task[{source_task_ordinal}] compatibility receipt",
    )
    expected_lane = catalog_v1.expected_lane_for_source_task(source_task_ordinal)
    expected_acceptance_identity = source.normalize_object_identity_v2(
        member.get("task_acceptance_identity"), label="G0 task acceptance identity"
    )
    expected_carrier_identity = source.normalize_object_identity_v2(
        member.get("carrier_identity"), label="G0 task carrier identity"
    )
    if (
        compatibility.get("authoritative_task_acceptance_verified") is not True
        or compatibility.get("accepted_task_result_binding_verified") is not True
        or compatibility.get("independent_acceptance_authority_verified") is not True
        or compatibility.get("slate") != expected_slate
        or compatibility.get("accepted_task_index") != expected_lane["task_ordinal"]
        or compatibility.get("acceptance_receipt_identity")
        != expected_acceptance_identity
        or compatibility.get("carrier_identity") != expected_carrier_identity
    ):
        _fail(f"task[{source_task_ordinal}] is not authoritatively accepted")
    result_rows = _sequence(
        compatibility.get("result_objects"),
        label=f"task[{source_task_ordinal}] result bindings",
    )
    member_arms = _sequence(
        member.get("arms"), label=f"panel member[{source_task_ordinal}] arms"
    )
    if len(result_rows) != EXPECTED_ARM_COUNT or len(member_arms) != EXPECTED_ARM_COUNT:
        _fail(f"task[{source_task_ordinal}] does not bind exactly seven results")
    expected_results = [
        {
            "ordinal": arm_ordinal,
            "parameter_set_id": batch.PARAMETER_SET_ORDER[arm_ordinal],
            "result_object": source.normalize_object_identity_v2(
                _mapping(member_arms[arm_ordinal], label="panel arm")[
                    "result_identity"
                ],
                label=f"panel arm[{arm_ordinal}] result",
            ),
        }
        for arm_ordinal in range(EXPECTED_ARM_COUNT)
    ]
    if result_rows != expected_results:
        _fail(f"task[{source_task_ordinal}] carrier/result identities differ from G0")

    roster_by_id: dict[str, tuple[str, ...]] = {}
    occurrences: dict[str, list[dict[str, object]]] = defaultdict(list)
    arm_bindings: list[dict[str, object]] = []
    common_schedule_sha: str | None = None
    common_task_source_binding_sha: str | None = None
    total_visits = 0
    for arm_ordinal, body_value in enumerate(variants):
        body = _mapping(body_value, label=f"task[{source_task_ordinal}] arm[{arm_ordinal}]")
        profile = _mapping(body.get("profile"), label="variant profile")
        parameter_set_id = batch.PARAMETER_SET_ORDER[arm_ordinal]
        if (
            profile.get("ordinal") != arm_ordinal
            or profile.get("parameter_set_id") != parameter_set_id
            or body.get("slate") != expected_slate
        ):
            _fail(f"task[{source_task_ordinal}] arm[{arm_ordinal}] identity differs")
        common_task_source_binding_sha = _validate_result_task_source_binding(
            source_task_ordinal=source_task_ordinal,
            arm_ordinal=arm_ordinal,
            body=body,
            imported=imported,
            catalog_binding=catalog_binding,
            common_binding_sha256=common_task_source_binding_sha,
        )
        schedule_sha = _digest(
            body.get("visit_schedule_sha256"), label="visit schedule SHA"
        )
        if common_schedule_sha is None:
            common_schedule_sha = schedule_sha
        elif schedule_sha != common_schedule_sha:
            _fail(f"task[{source_task_ordinal}] arm schedules differ")
        visit_rosters = [
            _canonical_roster(
                roster,
                label=(
                    f"task[{source_task_ordinal}] arm[{arm_ordinal}] "
                    f"visit[{visit_ordinal}]"
                ),
            )
            for visit_ordinal, roster in enumerate(
                _sequence(body.get("visit_rosters"), label="variant visit rosters")
            )
        ]
        unique_rosters = [
            _canonical_roster(
                roster,
                label=(
                    f"task[{source_task_ordinal}] arm[{arm_ordinal}] "
                    f"unique[{unique_ordinal}]"
                ),
            )
            for unique_ordinal, roster in enumerate(
                _sequence(body.get("unique_rosters"), label="variant unique rosters")
            )
        ]
        replay_unique, replay_first = _first_occurrence_unique(visit_rosters)
        retained_first = _sequence(
            body.get("first_occurrence_visit_indices"),
            label="variant first-occurrence indices",
        )
        if (
            replay_unique != unique_rosters
            or retained_first != replay_first
            or len(unique_rosters) < source.ENTRY_BUDGET
        ):
            _fail(f"task[{source_task_ordinal}] arm[{arm_ordinal}] unique book differs")
        for roster in unique_rosters:
            _validate_roster_against_catalog(
                roster,
                catalog=catalog,
                label=f"task[{source_task_ordinal}] arm[{arm_ordinal}] roster",
            )
            lineup_id = v12_import.canonical_lineup_id(expected_slate, roster)
            prior = roster_by_id.setdefault(lineup_id, roster)
            if prior != roster:
                _fail("canonical lineup identity collision")
        if len(visit_rosters) != len(visit_schedule):
            _fail(f"task[{source_task_ordinal}] arm[{arm_ordinal}] visit coverage differs")
        for visit_ordinal, (roster, world) in enumerate(
            zip(visit_rosters, visit_schedule, strict=True)
        ):
            lineup_id = v12_import.canonical_lineup_id(expected_slate, roster)
            occurrences[lineup_id].append({
                "arm_ordinal": arm_ordinal,
                "parameter_set_id": parameter_set_id,
                "visit_ordinal": visit_ordinal,
                "block_id": world["block"],
                "objective_world_index": world["index"],
            })
        coverage = _mapping(body.get("coverage"), label="variant coverage")
        selected = _sequence(body.get("selected_rosters"), label="selected rosters")
        arm_bindings.append({
            "arm_ordinal": arm_ordinal,
            "parameter_set_id": parameter_set_id,
            "result_identity": expected_results[arm_ordinal]["result_object"],
            "result_sha256": _digest(
                body.get("result_sha256"), label="variant internal SHA"
            ),
            "task_source_binding_sha256": common_task_source_binding_sha,
            "visit_count": len(visit_rosters),
            "unique_count": len(unique_rosters),
            "selected_count": len(selected),
            "coverage": coverage,
            "visit_rosters_sha256": source.canonical_sha256([
                list(roster) for roster in visit_rosters
            ]),
            "unique_rosters_sha256": source.canonical_sha256([
                list(roster) for roster in unique_rosters
            ]),
            "first_occurrence_visit_indices_sha256": source.canonical_sha256(
                replay_first
            ),
            "selected_rosters_sha256": source.canonical_sha256(selected),
        })
        total_visits += len(visit_rosters)
    if (
        common_schedule_sha is None
        or common_task_source_binding_sha is None
        or set(roster_by_id) != set(occurrences)
    ):
        _fail(f"task[{source_task_ordinal}] full-union lineage coverage differs")
    if common_schedule_sha != world_schedule_row.get("visit_schedule_sha256"):
        _fail(f"task[{source_task_ordinal}] arms differ from exact world schedule")

    candidate_rows: list[dict[str, object]] = []
    lineage_rows: list[dict[str, object]] = []
    for lineup_id in sorted(roster_by_id):
        roster = roster_by_id[lineup_id]
        candidate_rows.append({
            "candidate_id": lineup_id,
            "player_ids": list(roster),
        })
        candidate_occurrences = occurrences[lineup_id]
        source_arm_ordinals = sorted({
            int(row["arm_ordinal"]) for row in candidate_occurrences
        })
        occurrence_counts_by_block = {
            block: sum(
                1 for row in candidate_occurrences if row["block_id"] == block
            )
            for block in rw.WORLD_BLOCKS
        }
        source_arms_by_block = {
            block: sorted({
                str(row["parameter_set_id"])
                for row in candidate_occurrences
                if row["block_id"] == block
            })
            for block in rw.WORLD_BLOCKS
        }
        lineage_rows.append({
            "candidate_id": lineup_id,
            "player_ids": list(roster),
            "roster_sha256": source.canonical_sha256(list(roster)),
            "source_arm_ordinals": source_arm_ordinals,
            "source_arms": [
                batch.PARAMETER_SET_ORDER[ordinal] for ordinal in source_arm_ordinals
            ],
            "origin_blocks": [
                block for block in rw.WORLD_BLOCKS
                if occurrence_counts_by_block[block]
            ],
            "occurrence_counts_by_block": occurrence_counts_by_block,
            "source_arms_by_block": source_arms_by_block,
            "occurrence_count": len(candidate_occurrences),
            "occurrences": candidate_occurrences,
        })
    if len(candidate_rows) < source.ENTRY_BUDGET:
        _fail(f"task[{source_task_ordinal}] full union is below the R6 entry budget")
    artifact = source.build_accepted_candidate_artifact_v1(
        source_task_ordinal=source_task_ordinal,
        rows=candidate_rows,
    )
    sidecar = _with_self_hash({
        "schema_version": LINEAGE_SIDECAR_SCHEMA,
        "source_task_ordinal": source_task_ordinal,
        "task_id": artifact["task_id"],
        "slate": expected_slate,
        "full_union_law": FULL_UNION_LAW,
        "lineup_order_law": LINEUP_ORDER_LAW,
        "lineage_order_law": LINEAGE_ORDER_LAW,
        "world_schedule_identity": dict(world_schedule_identity),
        "world_schedule_object_sha256": world_schedule_identity["sha256"],
        "world_schedule_task_row_sha256": source.canonical_sha256(
            world_schedule_row
        ),
        "visit_schedule_sha256": common_schedule_sha,
        "visits_per_block": VISITS_PER_BLOCK,
        "task_source_binding_sha256": common_task_source_binding_sha,
        "arm_count": EXPECTED_ARM_COUNT,
        "visit_occurrence_count": total_visits,
        "candidate_count": len(lineage_rows),
        "candidates": lineage_rows,
        "candidate_lineage_manifest_sha256": source.canonical_sha256(lineage_rows),
        **_policy(),
    }, field="candidate_lineage_sidecar_sha256")
    predecessor = {
        "source_task_ordinal": source_task_ordinal,
        "task_id": artifact["task_id"],
        "slate": expected_slate,
        "accepted_member": dict(member),
        "accepted_slate_membership_sha256": source.canonical_sha256(member),
        "task_acceptance_identity": expected_acceptance_identity,
        "task_acceptance_sha256": _digest(
            compatibility.get("accepted_task_acceptance_sha256"),
            label="task acceptance internal SHA",
        ),
        "carrier_identity": expected_carrier_identity,
        "carrier_hash_field": _text(
            compatibility.get("carrier_hash_field"), label="carrier hash field"
        ),
        "carrier_sha256": _digest(
            imported.carrier.get(str(compatibility["carrier_hash_field"])),
            label="carrier internal SHA",
        ),
        "catalog_binding": dict(catalog_binding),
        "arm_bindings": arm_bindings,
        "world_schedule_identity": dict(world_schedule_identity),
        "world_schedule_object_sha256": world_schedule_identity["sha256"],
        "world_schedule_task_row_sha256": source.canonical_sha256(
            world_schedule_row
        ),
        "visit_schedule_sha256": common_schedule_sha,
        "visits_per_block": VISITS_PER_BLOCK,
        "visit_occurrence_count": total_visits,
    }
    return artifact, sidecar, predecessor


def _derive_material(
    *,
    repository_root: Path,
    catalog_replay_receipt_identity: Mapping[str, object],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    try:
        (
            publication_receipt_binding,
            publication_receipt,
            panel,
            _lane_bindings,
            git_binding,
        ) = panel_execution.replay_published_v12_panel_v1(
            repository_root=repository_root,
            read_exact=read_exact,
            git_head=git_head,
            git_blob=git_blob,
            git_status=git_status,
        )
    except Exception as exc:
        raise CorpusR6FixedG0CandidateAuthorityV1Error(
            f"fixed G0 replay failed: {exc}"
        ) from exc
    panel_identity = source.normalize_object_identity_v2(
        publication_receipt.get("panel_object_identity"),
        label="fixed G0 panel identity",
    )
    members = _sequence(panel.get("accepted_slates"), label="fixed G0 members")
    if (
        panel.get("accepted_slate_count") != source.TASK_COUNT
        or len(members) != source.TASK_COUNT
        or [
            _mapping(member, label="fixed G0 member").get("source_task_ordinal")
            for member in members
        ]
        != list(range(source.TASK_COUNT))
    ):
        _fail("fixed G0 replay does not contain the exact ordered 54-member panel")
    (
        catalog_final_lock_binding,
        normalized_catalog_replay_receipt_identity,
        catalog_replay_receipt,
    ) = _reopen_catalog_terminal_authority(
        repository_root=repository_root,
        catalog_replay_receipt_identity=catalog_replay_receipt_identity,
        git_binding=_mapping(git_binding, label="G0 Git binding"),
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    (
        catalog_release,
        normalized_catalog_release_identity,
        catalogs,
        catalog_bindings,
    ) = _reopen_catalog_panel(
        catalog_release_identity=_mapping(
            catalog_replay_receipt.get("catalog_release_identity"),
            label="terminal catalog release identity",
        ),
        catalog_replay_receipt=catalog_replay_receipt,
        panel_identity=panel_identity,
        panel=panel,
        members=[_mapping(member, label="fixed G0 member") for member in members],
        git_binding=_mapping(git_binding, label="G0 Git binding"),
        read_exact=read_exact,
    )

    artifacts: list[dict[str, object]] = []
    sidecars: list[dict[str, object]] = []
    predecessors: list[dict[str, object]] = []
    for source_ordinal, member_value in enumerate(members):
        member = _mapping(member_value, label=f"fixed G0 member[{source_ordinal}]")
        try:
            imported = v12_import.reopen_v12_task(
                acceptance_receipt_identity=_mapping(
                    member["task_acceptance_identity"],
                    label="task acceptance identity",
                ),
                carrier_identity=_mapping(
                    member["carrier_identity"], label="carrier identity"
                ),
                read_exact=read_exact,
                require_authoritative=True,
            )
        except Exception as exc:
            raise CorpusR6FixedG0CandidateAuthorityV1Error(
                f"accepted task[{source_ordinal}] exact replay failed: {exc}"
            ) from exc
        (
            world_schedule_identity,
            world_schedule_row,
            visit_schedule,
        ) = _reopen_task_world_schedule(
            source_task_ordinal=source_ordinal,
            imported=imported,
            read_exact=read_exact,
        )
        artifact, sidecar, predecessor = _derive_slate_material(
            source_task_ordinal=source_ordinal,
            member=member,
            catalog=catalogs[source_ordinal],
            catalog_binding=catalog_bindings[source_ordinal],
            imported=imported,
            world_schedule_identity=world_schedule_identity,
            world_schedule_row=world_schedule_row,
            visit_schedule=visit_schedule,
        )
        artifacts.append(artifact)
        sidecars.append(sidecar)
        predecessors.append(predecessor)

    acceptance_manifest = [{
        "source_task_ordinal": ordinal,
        "identity": predecessor["task_acceptance_identity"],
        "self_hash": predecessor["task_acceptance_sha256"],
    } for ordinal, predecessor in enumerate(predecessors)]
    carrier_manifest = [{
        "source_task_ordinal": ordinal,
        "identity": predecessor["carrier_identity"],
        "self_hash": predecessor["carrier_sha256"],
    } for ordinal, predecessor in enumerate(predecessors)]
    if (
        catalog_replay_receipt.get("tracked_root_binding")
        != catalog_release["tracked_root_binding"]
        or source.canonical_sha256(acceptance_manifest)
        != catalog_replay_receipt.get("task_acceptance_body_manifest_sha256")
        or source.canonical_sha256(carrier_manifest)
        != catalog_replay_receipt.get("carrier_body_manifest_sha256")
    ):
        _fail("accepted task bodies differ from terminal catalog replay receipt")

    body: dict[str, object] = {
        "schema_version": MATERIAL_SCHEMA,
        "fixed_g0_panel_identity": panel_identity,
        "fixed_g0_panel_id": panel["panel_id"],
        "fixed_g0_panel_index_sha256": panel["panel_index_sha256"],
        "g0_authority_lock_sha256": git_binding["g0_authority_lock_sha256"],
        "g0_source_commit_sha": git_binding["source_commit_sha"],
        "publication_receipt_sha256": publication_receipt[
            "publication_receipt_sha256"
        ],
        "publication_receipt_file_sha256": publication_receipt_binding["sha256"],
        "catalog_terminal_final_lock_binding": catalog_final_lock_binding,
        "catalog_replay_receipt_identity": (
            normalized_catalog_replay_receipt_identity
        ),
        "catalog_replay_receipt_sha256": catalog_replay_receipt[
            "replay_receipt_sha256"
        ],
        "catalog_release_identity": normalized_catalog_release_identity,
        "catalog_release_sha256": catalog_release["release_sha256"],
        "task_count": source.TASK_COUNT,
        "arm_result_count": source.TASK_COUNT * EXPECTED_ARM_COUNT,
        "candidate_artifacts": artifacts,
        "candidate_artifact_manifest_sha256": source.canonical_sha256(artifacts),
        "lineage_sidecars": sidecars,
        "lineage_sidecar_manifest_sha256": source.canonical_sha256(sidecars),
        "slate_predecessor_bindings": predecessors,
        "slate_predecessor_manifest_sha256": source.canonical_sha256(predecessors),
        "full_union_law": FULL_UNION_LAW,
        "lineup_order_law": LINEUP_ORDER_LAW,
        "candidate_filter_applied": False,
        "selected_rosters_used_as_population": False,
        **_policy(),
    }
    return _with_self_hash(body, field="candidate_material_sha256")


def derive_fixed_g0_candidate_material_v1(
    *,
    repository_root: Path,
    catalog_replay_receipt_identity: Mapping[str, object],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Return exact candidate/lineage bodies for an outer create-once publisher."""
    return _derive_material(
        repository_root=repository_root,
        catalog_replay_receipt_identity=catalog_replay_receipt_identity,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )


def _slate_receipt(
    *,
    material: Mapping[str, object],
    predecessor: Mapping[str, object],
    artifact: Mapping[str, object],
    artifact_identity: Mapping[str, object],
    sidecar: Mapping[str, object],
) -> dict[str, object]:
    source_ordinal = int(predecessor["source_task_ordinal"])
    arm_bindings = _sequence(predecessor["arm_bindings"], label="arm bindings")
    body: dict[str, object] = {
        "schema_version": SLATE_DERIVATION_SCHEMA,
        "source_task_ordinal": source_ordinal,
        "task_id": predecessor["task_id"],
        "slate": predecessor["slate"],
        "fixed_g0_panel_identity": material["fixed_g0_panel_identity"],
        "fixed_g0_panel_index_sha256": material["fixed_g0_panel_index_sha256"],
        "g0_authority_lock_sha256": material["g0_authority_lock_sha256"],
        "catalog_terminal_final_lock_binding": material[
            "catalog_terminal_final_lock_binding"
        ],
        "catalog_replay_receipt_identity": material[
            "catalog_replay_receipt_identity"
        ],
        "catalog_replay_receipt_sha256": material[
            "catalog_replay_receipt_sha256"
        ],
        "accepted_member": predecessor["accepted_member"],
        "accepted_slate_membership_sha256": predecessor[
            "accepted_slate_membership_sha256"
        ],
        "task_acceptance_identity": predecessor["task_acceptance_identity"],
        "task_acceptance_sha256": predecessor["task_acceptance_sha256"],
        "carrier_identity": predecessor["carrier_identity"],
        "carrier_hash_field": predecessor["carrier_hash_field"],
        "carrier_sha256": predecessor["carrier_sha256"],
        "catalog_binding": predecessor["catalog_binding"],
        "arm_count": EXPECTED_ARM_COUNT,
        "arm_bindings": arm_bindings,
        "arm_binding_manifest_sha256": source.canonical_sha256(arm_bindings),
        "world_schedule_identity": predecessor["world_schedule_identity"],
        "world_schedule_object_sha256": predecessor[
            "world_schedule_object_sha256"
        ],
        "world_schedule_task_row_sha256": predecessor[
            "world_schedule_task_row_sha256"
        ],
        "visit_schedule_sha256": predecessor["visit_schedule_sha256"],
        "visits_per_block": predecessor["visits_per_block"],
        "visit_occurrence_count": predecessor["visit_occurrence_count"],
        "full_union_law": FULL_UNION_LAW,
        "lineup_order_law": LINEUP_ORDER_LAW,
        "candidate_filter_applied": False,
        "selected_rosters_used_as_population": False,
        "candidate_artifact_identity": artifact_identity,
        "candidate_artifact_sha256": artifact["candidate_artifact_sha256"],
        "candidate_count": artifact["candidate_count"],
        "ordered_candidate_ids_sha256": artifact[
            "ordered_candidate_ids_sha256"
        ],
        "candidate_row_manifest_sha256": artifact[
            "candidate_row_manifest_sha256"
        ],
        "lineage_sidecar_sha256": sidecar[
            "candidate_lineage_sidecar_sha256"
        ],
        "candidate_lineage_manifest_sha256": sidecar[
            "candidate_lineage_manifest_sha256"
        ],
        "exact_catalog_closure_verified": True,
        "dk_classic_roster_and_salary_verified": True,
        "all_unique_rosters_preserved": True,
        **_policy(),
    }
    return _with_self_hash(body, field="slate_derivation_sha256")


def build_fixed_g0_candidate_authority_v1(
    *,
    release_id: str,
    namespace: str,
    repository_root: Path,
    catalog_replay_receipt_identity: Mapping[str, object],
    candidate_artifact_identities: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Build the current R6 release and exact fixed-G0 derivation receipts."""
    material = _derive_material(
        repository_root=repository_root,
        catalog_replay_receipt_identity=catalog_replay_receipt_identity,
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    raw_identities = _sequence(
        candidate_artifact_identities, label="candidate artifact identities"
    )
    if len(raw_identities) != source.TASK_COUNT:
        _fail("candidate authority requires exactly 54 artifact identities")
    artifacts = [
        _mapping(value, label=f"candidate artifact[{ordinal}]")
        for ordinal, value in enumerate(material["candidate_artifacts"])
    ]
    sidecars = [
        _mapping(value, label=f"lineage sidecar[{ordinal}]")
        for ordinal, value in enumerate(material["lineage_sidecars"])
    ]
    predecessors = [
        _mapping(value, label=f"predecessor[{ordinal}]")
        for ordinal, value in enumerate(material["slate_predecessor_bindings"])
    ]
    entries: list[dict[str, object]] = []
    receipts: list[dict[str, object]] = []
    normalized_artifact_identities: list[dict[str, object]] = []
    for source_ordinal, (artifact, sidecar, predecessor, raw_identity) in enumerate(
        zip(artifacts, sidecars, predecessors, raw_identities, strict=True)
    ):
        identity = _bind_body_identity(
            artifact,
            _mapping(raw_identity, label="candidate artifact identity"),
            label=f"candidate artifact[{source_ordinal}]",
        )
        expected_uri = (
            f"{namespace}source-task-{source_ordinal:02d}-"
            f"{artifact['slate']['slate_id']}/accepted-candidates.json"
        )
        if identity["uri"] != expected_uri:
            _fail(f"candidate artifact[{source_ordinal}] URI differs from capture law")
        reopened_identity, reopened_artifact = _exact_read_object(
            identity,
            read_exact=read_exact,
            label=f"published candidate artifact[{source_ordinal}]",
        )
        try:
            validated_reopened_artifact = (
                source.validate_accepted_candidate_artifact_v1(
                    reopened_artifact
                )
            )
        except Exception as exc:
            raise CorpusR6FixedG0CandidateAuthorityV1Error(str(exc)) from exc
        if (
            reopened_identity != identity
            or source.canonical_json_bytes(validated_reopened_artifact)
            != source.canonical_json_bytes(artifact)
        ):
            _fail(
                f"published candidate artifact[{source_ordinal}] bytes differ"
            )
        normalized_artifact_identities.append(identity)
        catalog_binding = _mapping(
            predecessor["catalog_binding"], label="candidate catalog binding"
        )
        entry_body: dict[str, object] = {
            "source_task_ordinal": source_ordinal,
            "task_id": artifact["task_id"],
            "slate": artifact["slate"],
            "catalog_identity": catalog_binding["catalog_identity"],
            "candidate_artifact": artifact,
            "candidate_artifact_identity": identity,
            "candidate_count": artifact["candidate_count"],
            "ordered_candidate_ids_sha256": artifact[
                "ordered_candidate_ids_sha256"
            ],
        }
        entries.append({
            **entry_body,
            "accepted_candidate_release_entry_sha256": source.canonical_sha256(
                entry_body
            ),
        })
        receipts.append(_slate_receipt(
            material=material,
            predecessor=predecessor,
            artifact=artifact,
            artifact_identity=identity,
            sidecar=sidecar,
        ))
    release = source.build_accepted_candidate_release_v1(
        release_id=release_id,
        namespace=namespace,
        source_candidate_panel_identity=material["fixed_g0_panel_identity"],
        entries=entries,
    )
    panel_rows = [{
        "source_task_ordinal": ordinal,
        "task_id": receipt["task_id"],
        "slate": receipt["slate"],
        "accepted_slate_membership_sha256": receipt[
            "accepted_slate_membership_sha256"
        ],
        "slate_derivation_sha256": receipt["slate_derivation_sha256"],
        "candidate_artifact_identity": receipt["candidate_artifact_identity"],
        "candidate_count": receipt["candidate_count"],
        "ordered_candidate_ids_sha256": receipt[
            "ordered_candidate_ids_sha256"
        ],
        "lineage_sidecar_sha256": receipt["lineage_sidecar_sha256"],
        "world_schedule_identity": receipt["world_schedule_identity"],
        "world_schedule_task_row_sha256": receipt[
            "world_schedule_task_row_sha256"
        ],
        "visit_schedule_sha256": receipt["visit_schedule_sha256"],
    } for ordinal, receipt in enumerate(receipts)]
    total_candidates = sum(int(row["candidate_count"]) for row in receipts)
    total_visits = sum(int(row["visit_occurrence_count"]) for row in receipts)
    panel_receipt = _with_self_hash({
        "schema_version": PANEL_DERIVATION_SCHEMA,
        "fixed_g0_panel_identity": material["fixed_g0_panel_identity"],
        "fixed_g0_panel_id": material["fixed_g0_panel_id"],
        "fixed_g0_panel_index_sha256": material["fixed_g0_panel_index_sha256"],
        "g0_authority_lock_sha256": material["g0_authority_lock_sha256"],
        "g0_source_commit_sha": material["g0_source_commit_sha"],
        "publication_receipt_sha256": material["publication_receipt_sha256"],
        "publication_receipt_file_sha256": material[
            "publication_receipt_file_sha256"
        ],
        "catalog_terminal_final_lock_binding": material[
            "catalog_terminal_final_lock_binding"
        ],
        "catalog_replay_receipt_identity": material[
            "catalog_replay_receipt_identity"
        ],
        "catalog_replay_receipt_sha256": material[
            "catalog_replay_receipt_sha256"
        ],
        "catalog_release_identity": material["catalog_release_identity"],
        "catalog_release_sha256": material["catalog_release_sha256"],
        "candidate_release_id": release["release_id"],
        "candidate_namespace": release["namespace"],
        "candidate_release_sha256": release[
            "accepted_candidate_release_sha256"
        ],
        "candidate_release_body_sha256": source.canonical_sha256(release),
        "task_count": source.TASK_COUNT,
        "arm_result_count": source.TASK_COUNT * EXPECTED_ARM_COUNT,
        "total_candidate_count": total_candidates,
        "total_visit_occurrence_count": total_visits,
        "full_union_law": FULL_UNION_LAW,
        "lineup_order_law": LINEUP_ORDER_LAW,
        "candidate_filter_applied": False,
        "selected_rosters_used_as_population": False,
        "slates": panel_rows,
        "slate_derivation_manifest_sha256": source.canonical_sha256(receipts),
        "candidate_artifact_identity_manifest_sha256": source.canonical_sha256(
            normalized_artifact_identities
        ),
        "lineage_sidecar_manifest_sha256": source.canonical_sha256(sidecars),
        "all_54_exact_predecessors_reopened": True,
        "all_378_result_objects_reopened": True,
        "exact_catalog_closure_verified": True,
        **_policy(),
    }, field="panel_derivation_sha256")
    bundle_body: dict[str, object] = {
        "schema_version": AUTHORITY_BUNDLE_SCHEMA,
        "candidate_release": release,
        "candidate_artifacts": artifacts,
        "candidate_artifact_manifest_sha256": source.canonical_sha256(artifacts),
        "lineage_sidecars": sidecars,
        "lineage_sidecar_manifest_sha256": source.canonical_sha256(sidecars),
        "slate_derivation_receipts": receipts,
        "slate_derivation_manifest_sha256": source.canonical_sha256(receipts),
        "panel_derivation_receipt": panel_receipt,
        "task_count": source.TASK_COUNT,
        **_policy(),
    }
    return _with_self_hash(bundle_body, field="candidate_authority_bundle_sha256")


def validate_fixed_g0_candidate_authority_v1(
    value: object,
    *,
    repository_root: Path,
    catalog_replay_receipt_identity: Mapping[str, object],
    read_exact: ReadExact,
    git_head: GitHead,
    git_blob: GitBlob,
    git_status: GitStatus,
) -> dict[str, object]:
    """Exact-replay all predecessors and byte-compare the complete authority bundle."""
    item = _mapping(value, label="fixed-G0 candidate authority bundle")
    _validate_self_hash(
        item,
        field="candidate_authority_bundle_sha256",
        label="fixed-G0 candidate authority bundle",
    )
    if item.get("schema_version") != AUTHORITY_BUNDLE_SCHEMA:
        _fail("fixed-G0 candidate authority bundle schema differs")
    release = source.validate_accepted_candidate_release_v1(
        item.get("candidate_release")
    )
    panel_receipt = _mapping(
        item.get("panel_derivation_receipt"), label="panel derivation receipt"
    )
    _validate_self_hash(
        panel_receipt,
        field="panel_derivation_sha256",
        label="panel derivation receipt",
    )
    expected_catalog_replay_receipt_identity = source.normalize_object_identity_v2(
        catalog_replay_receipt_identity,
        label="expected fixed-G0 catalog replay receipt",
    )
    if (
        panel_receipt.get("catalog_replay_receipt_identity")
        != expected_catalog_replay_receipt_identity
    ):
        _fail("candidate authority differs from the expected catalog replay receipt")
    identities = [
        _mapping(entry, label=f"candidate release entry[{ordinal}]")[
            "candidate_artifact_identity"
        ]
        for ordinal, entry in enumerate(
            _sequence(release["entries"], label="candidate release entries")
        )
    ]
    artifacts = _sequence(item.get("candidate_artifacts"), label="candidate artifacts")
    if len(artifacts) != source.TASK_COUNT:
        _fail("fixed-G0 candidate bundle must retain exactly 54 artifacts")
    for ordinal, (identity, artifact_value) in enumerate(
        zip(identities, artifacts, strict=True)
    ):
        _, reopened_artifact = _exact_read_object(
            _mapping(identity, label="candidate artifact identity"),
            read_exact=read_exact,
            label=f"published candidate artifact[{ordinal}]",
        )
        artifact = source.validate_accepted_candidate_artifact_v1(artifact_value)
        if source.canonical_json_bytes(reopened_artifact) != source.canonical_json_bytes(
            artifact
        ):
            _fail(f"published candidate artifact[{ordinal}] bytes differ")
    rebuilt = build_fixed_g0_candidate_authority_v1(
        release_id=str(release["release_id"]),
        namespace=str(release["namespace"]),
        repository_root=repository_root,
        catalog_replay_receipt_identity=(
            expected_catalog_replay_receipt_identity
        ),
        candidate_artifact_identities=[
            _mapping(identity, label="candidate artifact identity")
            for identity in identities
        ],
        read_exact=read_exact,
        git_head=git_head,
        git_blob=git_blob,
        git_status=git_status,
    )
    if source.canonical_json_bytes(rebuilt) != source.canonical_json_bytes(item):
        _fail(
            "fixed-G0 candidate release/receipts differ from exact predecessor replay"
        )
    return rebuilt


__all__ = [
    "AUTHORITY_BUNDLE_SCHEMA",
    "CorpusR6FixedG0CandidateAuthorityV1Error",
    "FULL_UNION_LAW",
    "LINEAGE_SIDECAR_SCHEMA",
    "LINEUP_ORDER_LAW",
    "MATERIAL_SCHEMA",
    "PANEL_DERIVATION_SCHEMA",
    "SLATE_DERIVATION_SCHEMA",
    "build_fixed_g0_candidate_authority_v1",
    "derive_fixed_g0_candidate_material_v1",
    "validate_fixed_g0_candidate_authority_v1",
]
