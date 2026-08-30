"""Immutable realized-grade bridge for the construction/allocation cross.

The score-blind construction terminal is the only selection input.  The only
recognized realized input is a separately published catalog-wide outcome
completion root.  ``prepare`` never opens that realized root.  ``grade`` must
hold the shared historical-outcome lease before the first realized byte is
opened, projects the recognized snapshot into one exact outcome document per
slate, delegates all scoring to ``corpus_r6_construction_allocation_grade_v1``,
publishes every child create-once, and publishes the terminal grade root last.

The recognized catalog completion already owns the live shared historical-
outcome lease.  This bridge verifies that exact live lease before opening the
snapshot and again before publication; it never acquires, releases, or deletes
the catalog lease.  Its disposition remains the external launcher/watcher's
responsibility.

The generic scientific operator is deliberately incapable of object listing,
overwrite, or deletion.  Live-lease observation is injected through a narrow
verifier for one fixed known name.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Final, Protocol

from . import corpus_r6_catalog_wide_outcome_successor_v1 as catalog_outcomes
from . import corpus_r6_construction_allocation_cross_operator_v1 as selection_operator
from . import corpus_r6_construction_allocation_cross_v1 as cross
from . import corpus_r6_construction_allocation_grade_v1 as grade_science
from . import corpus_r6_full_union_outcome_snapshot_v1 as ordinary_outcomes


MANIFEST_SCHEMA: Final = "corpus-r6-construction-allocation-grade-manifest/v1"
SELECTION_REOPEN_SCHEMA: Final = (
    "corpus-r6-construction-allocation-grade-selection-reopen/v1"
)
OUTCOME_CLOSURE_SCHEMA: Final = (
    "corpus-r6-construction-allocation-grade-outcome-closure/v1"
)
TERMINAL_SCHEMA: Final = "corpus-r6-construction-allocation-grade-terminal/v1"
TERMINAL_ENVELOPE_SCHEMA: Final = (
    "corpus-r6-construction-allocation-grade-terminal-envelope/v1"
)
REOPEN_SCHEMA: Final = "corpus-r6-construction-allocation-grade-reopen/v1"
RECOGNIZED_OUTCOME_COMPLETION_SCHEMA: Final = (
    "corpus-r6-catalog-wide-outcome-completion/v1"
)
RECOGNIZED_OUTCOME_NAMESPACE: Final = (
    "gs://nfl-predictions-503414-corpus-retrieval/research/"
    "corpus-r6-catalog-wide-realized/"
)
HISTORICAL_OUTCOME_LEASE_URI: Final = (
    "gs://nfl-predictions-503414-raw/research-governance/"
    "historical-outcome-active-v1.json"
)

MAXIMUM_MANIFEST_BYTES: Final = 4_000_000
MAXIMUM_OUTCOME_COMPLETION_BYTES: Final = 4_000_000
MAXIMUM_OUTCOME_PREDECESSOR_BYTES: Final = 192_000_000
MAXIMUM_OUTCOME_DOCUMENT_BYTES: Final = 4_000_000
MAXIMUM_GRADE_REPORT_BYTES: Final = 256_000_000
MAXIMUM_TERMINAL_BYTES: Final = 8_000_000

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{2,159}\Z")
_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{2,100}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_IMAGE = re.compile(r".+@sha256:[0-9a-f]{64}\Z")
_IMAGE_DIGEST = re.compile(r"sha256:[0-9a-f]{64}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")

_MANIFEST_FIELDS: Final = frozenset({
    "schema_version", "run_id", "grade_id", "frozen_at", "code_sha",
    "immutable_image", "image_digest", "output_prefix",
    "selection_terminal_envelope", "selection_terminal_envelope_sha256",
    "selection_terminal_identity", "selection_receipt_sha256",
    "selection_scientific_sha256", "recognized_outcome_completion_schema",
    "outcome_authority_identity", "expected_slate_ids",
    "outcome_document_uris", "outcome_document_uris_sha256",
    "selection_reopen_uri", "outcome_closure_uri", "grade_report_uri",
    "terminal_uri", "publication_order",
    "historical_outcome_lease_required_before_first_outcome_read",
    "outcome_authority_opened_during_prepare",
    "realized_outcomes_read_during_prepare", "object_listing_licensed",
    "overwrite_licensed", "scientific_object_delete_licensed",
    "automatic_retry_licensed", "automatic_policy_promotion",
    "production_policy_authority", "manifest_sha256",
})
_COMPLETION_FIELDS: Final = frozenset({
    "schema_version", "run_id", "outcome_key_projection_identity",
    "registered_request_identity", "query_evidence_identity",
    "realized_source_identity", "outcome_snapshot_identity",
    "historical_outcome_lease_identity", "source_snapshot_at",
    "source_slate_count", "outcome_key_count", "delta_query_key_count",
    "one_historical_outcome_read", "one_exact_query_job",
    "historical_outcome_lease_release_required", "lease_release_owner",
    "lineup_scoring_performed", "graph_mutation_licensed",
    "production_change_licensed", "decision_authority", "complete",
    "completion_sha256",
})
_TERMINAL_FIELDS: Final = frozenset({
    "schema_version", "run_id", "grade_id", "code_sha", "immutable_image",
    "image_digest", "manifest_identity", "manifest_sha256",
    "selection_terminal_identity", "selection_terminal_envelope_sha256",
    "selection_reopen_identity", "selection_reopen_sha256",
    "outcome_authority_identity", "outcome_authority_sha256",
    "outcome_snapshot_identity", "outcome_snapshot_sha256",
    "outcome_closure_identity", "outcome_closure_sha256",
    "outcome_document_identities", "outcome_document_identities_sha256",
    "grade_report_identity", "grade_report_sha256",
    "historical_outcome_lease_identity",
    "historical_outcome_lease_unchanged_through_grade",
    "historical_outcome_lease_body_sha256",
    "historical_outcome_lease_release_required", "lease_release_owner",
    "additional_historical_outcome_read", "source_slate_count",
    "prefixes", "thresholds", "publication_order_completed",
    "all_children_create_once_and_exact_reopened",
    "terminal_grade_root_published_last",
    "selection_and_all_predecessors_reopened_before_outcome_join",
    "outcome_authority_and_all_predecessors_generation_exact_reopened",
    "grade_recomputed_by_construction_allocation_grade_v1",
    "uses_realized_outcomes", "historical_evidence_status",
    "automatic_retry_licensed", "automatic_policy_promotion",
    "production_policy_authority", "complete", "terminal_sha256",
})
_TERMINAL_ENVELOPE_FIELDS: Final = frozenset({
    "schema_version", "terminal_identity", "terminal_sha256",
    "manifest_identity", "manifest_sha256",
    "historical_outcome_lease_identity",
    "terminal_root_was_last_scientific_publication",
    "historical_outcome_lease_release_required", "lease_release_owner",
    "complete",
    "envelope_sha256",
})


class ConstructionAllocationGradeOperatorV1Error(RuntimeError):
    """An immutable grade input, output, or predecessor differed."""


def _fail(message: str) -> None:
    raise ConstructionAllocationGradeOperatorV1Error(message)


ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]


class HistoricalOutcomeLeaseVerifierV1(Protocol):
    """Verify one completion-owned lease at its fixed live object name."""

    def __call__(
        self, *, expected_identity: Mapping[str, object], catalog_run_id: str,
    ) -> Mapping[str, object]: ...


@dataclass(frozen=True, slots=True)
class OpenedOutcomeAuthorityV1:
    completion: dict[str, object]
    completion_identity: dict[str, object]
    snapshot: dict[str, object]
    snapshot_identity: dict[str, object]
    player_scores: dict[tuple[int, str], int]
    slate_keys: dict[int, tuple[int, int, str]]
    lease_body: dict[str, object]
    lease_identity: dict[str, object]
    lease_body_sha256: str
    closure_receipt: dict[str, object]


def _canonical(value: object) -> bytes:
    try:
        return cross.canonical_json_bytes(value)
    except Exception as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            "canonical JSON differs"
        ) from exc


def _hash(value: object) -> str:
    return sha256(_canonical(value)).hexdigest()


def _utc_timestamp(value: object, *, label: str) -> str:
    if type(value) is not str or not value.endswith("Z"):
        _fail(f"{label} must be an explicit UTC timestamp")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            f"{label} differs"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        _fail(f"{label} is not UTC")
    return value


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} already exists")
    return {**body, field: _hash(body)}


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} is not one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} is not one ordered array")
    return list(value)


def _identity(
    value: object, *, label: str, expected_uri: str | None = None,
    expected_raw: bytes | None = None, require_create_once: bool = False,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    uri, generation, digest, size = (
        item.get("uri"), item.get("generation"), item.get("sha256"),
        item.get("bytes"),
    )
    if (
        type(uri) is not str or not uri.startswith("gs://")
        or type(generation) not in {str, int} or not str(generation)
        or type(digest) is not str or _SHA.fullmatch(digest) is None
        or type(size) is not int or size <= 0
        or (require_create_once and item.get("create_once") is not True)
    ):
        _fail(f"{label} content identity differs")
    retained: dict[str, object] = {
        "uri": uri, "generation": str(generation), "sha256": digest,
        "bytes": size,
    }
    if require_create_once or item.get("create_once") is True:
        retained["create_once"] = True
    if expected_uri is not None and uri != expected_uri:
        _fail(f"{label} URI differs")
    if expected_raw is not None and (
        size != len(expected_raw) or digest != sha256(expected_raw).hexdigest()
    ):
        _fail(f"{label} bytes differ")
    return retained


def _parse_document(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} bytes differ")
    try:
        value = json.loads(raw)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            f"{label} is not JSON"
        ) from exc
    document = _mapping(value, label=label)
    if raw not in {_canonical(document), _canonical(document) + b"\n"}:
        _fail(f"{label} is not canonical JSON")
    return document


def _read_document(
    identity: object, *, read_exact: ReadExact, label: str,
    maximum_bytes: int,
) -> tuple[dict[str, object], dict[str, object], bytes]:
    retained = _identity(identity, label=f"{label} identity")
    if retained["bytes"] > maximum_bytes:
        _fail(f"{label} exceeds its exact byte ceiling")
    try:
        raw = read_exact(retained)
    except Exception as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            f"{label} generation-exact read failed"
        ) from exc
    if (
        type(raw) is not bytes or len(raw) != retained["bytes"]
        or sha256(raw).hexdigest() != retained["sha256"]
    ):
        _fail(f"{label} generation-exact bytes differ")
    return _parse_document(raw, label=label), retained, raw


def _publish(
    *, uri: str, value: Mapping[str, object],
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
    label: str, maximum_bytes: int,
) -> dict[str, object]:
    raw = _canonical(value)
    if not raw or len(raw) > maximum_bytes:
        _fail(f"{label} publication exceeds its byte ceiling")
    try:
        published = publish_create_once(uri, raw)
    except Exception as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _identity(
        published, label=f"{label} publication", expected_uri=uri,
        expected_raw=raw, require_create_once=True,
    )
    if read_exact(identity) != raw:
        _fail(f"{label} create-once exact reopen differs")
    return identity


def _output_prefix(value: object) -> str:
    if type(value) is not str or not value.startswith("gs://"):
        _fail("grade output prefix differs")
    retained = value.rstrip("/")
    path = retained[5:]
    if not path or path.startswith("/") or "//" in path or any(
        part in {"", ".", ".."} for part in path.split("/")
    ):
        _fail("grade output prefix differs")
    return retained


def _validate_selection_envelope_shape(value: object) -> dict[str, object]:
    envelope = _mapping(value, label="selection terminal envelope")
    body = dict(envelope)
    retained_hash = body.pop("envelope_sha256", None)
    if (
        envelope.get("schema_version")
        != selection_operator.TERMINAL_ENVELOPE_SCHEMA
        or type(retained_hash) is not str or _SHA.fullmatch(retained_hash) is None
        or _hash(body) != retained_hash
        or envelope.get("complete") is not True
        or envelope.get("create_once") is not True
        or envelope.get("uses_target_slate_outcomes") is not False
    ):
        _fail("selection terminal envelope differs")
    terminal_identity = _identity(
        envelope.get("terminal_identity"), label="selection terminal identity",
        require_create_once=True,
    )
    if envelope.get("terminal_identity") != terminal_identity:
        _fail("selection terminal envelope identity differs")
    return envelope


def _reopen_selection(
    envelope: Mapping[str, object], *, read_exact: ReadExact,
) -> dict[str, object]:
    retained = _validate_selection_envelope_shape(envelope)
    try:
        reopened = selection_operator.reopen_terminal_bundle_v1(
            retained, read_exact=read_exact
        )
    except Exception as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            "selection terminal/predecessor closure differs"
        ) from exc
    selection = _mapping(reopened.get("selection"), label="reopened selection")
    slates = _sequence(selection.get("slates"), label="reopened selection slates")
    if (
        reopened.get("complete") is not True
        or reopened.get("outcome_data_accessed") is not False
        or [row.get("slate_id") for row in slates if isinstance(row, Mapping)]
        != list(cross.EXPECTED_SLATE_IDS)
    ):
        _fail("reopened selection authority differs")
    return reopened


def _recognized_outcome_identity(value: object) -> dict[str, object]:
    identity = _identity(value, label="recognized outcome completion")
    uri = str(identity["uri"])
    if (
        not uri.startswith(RECOGNIZED_OUTCOME_NAMESPACE)
        or not uri.endswith("/completion.json")
        or identity["bytes"] > MAXIMUM_OUTCOME_COMPLETION_BYTES
    ):
        _fail("recognized outcome completion namespace differs")
    return identity


def prepare_grade_manifest_v1(
    *, run_id: str, grade_id: str, frozen_at: str, code_sha: str,
    immutable_image: str, output_prefix: str,
    selection_terminal_envelope: Mapping[str, object],
    outcome_authority_identity: Mapping[str, object],
    read_exact: ReadExact, publish_create_once: PublishCreateOnce,
) -> dict[str, object]:
    """Freeze the grade request without opening the realized authority."""

    if (
        _RUN_ID.fullmatch(run_id) is None or _ID.fullmatch(grade_id) is None
        or _COMMIT.fullmatch(code_sha) is None
        or _IMAGE.fullmatch(immutable_image) is None
    ):
        _fail("grade manifest scalar authority differs")
    if not callable(read_exact) or not callable(publish_create_once):
        _fail("grade manifest callbacks differ")
    prefix = f"{_output_prefix(output_prefix)}/{run_id}"
    envelope = _validate_selection_envelope_shape(selection_terminal_envelope)
    reopened = _reopen_selection(envelope, read_exact=read_exact)
    outcome_identity = _recognized_outcome_identity(outcome_authority_identity)
    selection = reopened["selection"]
    slate_ids = [str(row["slate_id"]) for row in selection["slates"]]
    outcome_uris = [
        f"{prefix}/slates/{ordinal:02d}-{slate_id}/outcome.json"
        for ordinal, slate_id in enumerate(slate_ids)
    ]
    body: dict[str, object] = {
        "schema_version": MANIFEST_SCHEMA,
        "run_id": run_id,
        "grade_id": grade_id,
        "frozen_at": _utc_timestamp(frozen_at, label="grade frozen_at"),
        "code_sha": code_sha,
        "immutable_image": immutable_image,
        "image_digest": immutable_image.rsplit("@", 1)[-1],
        "output_prefix": prefix,
        "selection_terminal_envelope": envelope,
        "selection_terminal_envelope_sha256": envelope["envelope_sha256"],
        "selection_terminal_identity": envelope["terminal_identity"],
        "selection_receipt_sha256": selection["receipt_sha256"],
        "selection_scientific_sha256": selection["scientific_sha256"],
        "recognized_outcome_completion_schema": (
            RECOGNIZED_OUTCOME_COMPLETION_SCHEMA
        ),
        "outcome_authority_identity": outcome_identity,
        "expected_slate_ids": slate_ids,
        "outcome_document_uris": outcome_uris,
        "outcome_document_uris_sha256": _hash(outcome_uris),
        "selection_reopen_uri": f"{prefix}/selection-reopen.json",
        "outcome_closure_uri": f"{prefix}/outcome-closure.json",
        "grade_report_uri": f"{prefix}/grade-report.json",
        "terminal_uri": f"{prefix}/grade-terminal.json",
        "publication_order": [
            "derived-slate-outcomes", "selection-reopen",
            "outcome-predecessor-closure", "grade-report",
            "terminal-grade-root-last",
        ],
        "historical_outcome_lease_required_before_first_outcome_read": True,
        "outcome_authority_opened_during_prepare": False,
        "realized_outcomes_read_during_prepare": False,
        "object_listing_licensed": False,
        "overwrite_licensed": False,
        "scientific_object_delete_licensed": False,
        "automatic_retry_licensed": False,
        "automatic_policy_promotion": False,
        "production_policy_authority": False,
    }
    manifest = _with_hash(body, field="manifest_sha256")
    manifest_uri = f"{prefix}/grade-manifest.json"
    manifest_identity = _publish(
        uri=manifest_uri, value=manifest,
        publish_create_once=publish_create_once, read_exact=read_exact,
        label="grade manifest", maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )
    return {
        "schema_version": "corpus-r6-construction-allocation-grade-prepared/v1",
        "manifest_identity": manifest_identity,
        "manifest_sha256": manifest["manifest_sha256"],
        "selection_terminal_identity": envelope["terminal_identity"],
        "outcome_authority_identity": outcome_identity,
        "outcome_authority_opened": False,
        "uses_realized_outcomes": False,
        "complete": True,
    }


def validate_grade_manifest_v1(value: object) -> dict[str, object]:
    manifest = _mapping(value, label="grade manifest")
    body = dict(manifest)
    retained_hash = body.pop("manifest_sha256", None)
    if (
        frozenset(manifest) != _MANIFEST_FIELDS
        or manifest.get("schema_version") != MANIFEST_SCHEMA
        or type(retained_hash) is not str or _SHA.fullmatch(retained_hash) is None
        or _hash(body) != retained_hash
        or _RUN_ID.fullmatch(str(manifest.get("run_id", ""))) is None
        or _ID.fullmatch(str(manifest.get("grade_id", ""))) is None
        or _COMMIT.fullmatch(str(manifest.get("code_sha", ""))) is None
        or _IMAGE.fullmatch(str(manifest.get("immutable_image", ""))) is None
        or _IMAGE_DIGEST.fullmatch(str(manifest.get("image_digest", ""))) is None
        or _utc_timestamp(manifest.get("frozen_at"), label="grade frozen_at")
        != manifest.get("frozen_at")
        or str(manifest.get("immutable_image", "")).rsplit("@", 1)[-1]
        != manifest.get("image_digest")
        or _SHA.fullmatch(str(manifest.get("selection_receipt_sha256", ""))) is None
        or _SHA.fullmatch(str(manifest.get("selection_scientific_sha256", ""))) is None
        or manifest.get("recognized_outcome_completion_schema")
        != RECOGNIZED_OUTCOME_COMPLETION_SCHEMA
        or manifest.get("expected_slate_ids") != list(cross.EXPECTED_SLATE_IDS)
        or manifest.get("historical_outcome_lease_required_before_first_outcome_read")
        is not True
        or manifest.get("outcome_authority_opened_during_prepare") is not False
        or manifest.get("realized_outcomes_read_during_prepare") is not False
        or any(manifest.get(field) is not False for field in (
            "object_listing_licensed", "overwrite_licensed",
            "scientific_object_delete_licensed", "automatic_retry_licensed",
            "automatic_policy_promotion", "production_policy_authority",
        ))
    ):
        _fail("grade manifest fixed authority differs")
    prefix = _output_prefix(manifest.get("output_prefix"))
    if not prefix.endswith("/" + str(manifest["run_id"])):
        _fail("grade manifest run prefix differs")
    envelope = _validate_selection_envelope_shape(
        manifest.get("selection_terminal_envelope")
    )
    outcome_identity = _recognized_outcome_identity(
        manifest.get("outcome_authority_identity")
    )
    slate_ids = list(cross.EXPECTED_SLATE_IDS)
    outcome_uris = [
        f"{prefix}/slates/{ordinal:02d}-{slate_id}/outcome.json"
        for ordinal, slate_id in enumerate(slate_ids)
    ]
    expected_uris = {
        "selection_reopen_uri": f"{prefix}/selection-reopen.json",
        "outcome_closure_uri": f"{prefix}/outcome-closure.json",
        "grade_report_uri": f"{prefix}/grade-report.json",
        "terminal_uri": f"{prefix}/grade-terminal.json",
    }
    if (
        manifest.get("selection_terminal_envelope_sha256")
        != envelope["envelope_sha256"]
        or manifest.get("selection_terminal_identity")
        != envelope["terminal_identity"]
        or manifest.get("outcome_authority_identity") != outcome_identity
        or manifest.get("outcome_document_uris") != outcome_uris
        or manifest.get("outcome_document_uris_sha256") != _hash(outcome_uris)
        or any(manifest.get(key) != value for key, value in expected_uris.items())
        or manifest.get("publication_order") != [
            "derived-slate-outcomes", "selection-reopen",
            "outcome-predecessor-closure", "grade-report",
            "terminal-grade-root-last",
        ]
    ):
        _fail("grade manifest exact binding differs")
    return manifest


def open_grade_manifest_v1(
    manifest_identity: object, *, read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    document, identity, _ = _read_document(
        manifest_identity, read_exact=read_exact, label="grade manifest",
        maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )
    manifest = validate_grade_manifest_v1(document)
    expected_uri = f"{manifest['output_prefix']}/grade-manifest.json"
    if identity["uri"] != expected_uri:
        _fail("grade manifest identity URI differs")
    return manifest, identity


def _completion_body(value: Mapping[str, object]) -> dict[str, object]:
    completion = dict(value)
    body = dict(completion)
    retained = body.pop("completion_sha256", None)
    identity_fields = (
        "outcome_key_projection_identity", "registered_request_identity",
        "query_evidence_identity", "realized_source_identity",
        "outcome_snapshot_identity", "historical_outcome_lease_identity",
    )
    if (
        frozenset(completion) != _COMPLETION_FIELDS
        or completion.get("schema_version")
        != RECOGNIZED_OUTCOME_COMPLETION_SCHEMA
        or type(retained) is not str or _SHA.fullmatch(retained) is None
        or _hash(body) != retained
        or _RUN_ID.fullmatch(str(completion.get("run_id", ""))) is None
        or completion.get("source_slate_count") != len(cross.EXPECTED_SLATE_IDS)
        or completion.get("one_historical_outcome_read") is not True
        or completion.get("one_exact_query_job") is not True
        or completion.get("historical_outcome_lease_release_required") is not True
        or completion.get("lease_release_owner") != "external-launcher-watcher"
        or completion.get("lineup_scoring_performed") is not False
        or any(completion.get(field) is not False for field in (
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
        or completion.get("complete") is not True
        or any(not isinstance(completion.get(field), Mapping) for field in identity_fields)
    ):
        _fail("recognized outcome completion differs")
    for field in identity_fields:
        _identity(completion[field], label=f"outcome completion {field}")
    return completion


def _read_predecessor(
    identity: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    document, retained, _ = _read_document(
        identity, read_exact=read_exact, label=label,
        maximum_bytes=MAXIMUM_OUTCOME_PREDECESSOR_BYTES,
    )
    return document, retained


def _validate_registered_request(
    request: Mapping[str, object], *, request_identity: Mapping[str, object],
    projection: Mapping[str, object], projection_identity: Mapping[str, object],
    base_snapshot_identity: Mapping[str, object],
    later_source_identity: Mapping[str, object],
) -> dict[str, object]:
    item = dict(request)
    body = dict(item)
    retained_hash = body.pop("registered_request_sha256", None)
    queried = item.get("queried_keys")
    if (
        item.get("schema_version")
        != "corpus-r6-catalog-wide-registered-request/v1"
        or type(retained_hash) is not str or _SHA.fullmatch(retained_hash) is None
        or _hash(body) != retained_hash
        or item.get("outcome_key_projection_identity") != dict(projection_identity)
        or item.get("outcome_key_projection_sha256")
        != projection.get("outcome_key_projection_sha256")
        or item.get("base_outcome_snapshot_identity")
        != dict(base_snapshot_identity)
        or item.get("later_source_freeze_identity")
        != dict(later_source_identity)
        or not isinstance(queried, list)
        or item.get("queried_key_count") != len(queried)
        or item.get("queried_keys_sha256") != catalog_outcomes.digest(queried)
        or item.get("historical_outcome_lease_required") is not True
        or item.get("query_execution_performed") is not False
        or item.get("uses_realized_outcomes") is not False
        or item.get("complete") is not True
        or request_identity["sha256"] != sha256(_canonical(item)).hexdigest()
    ):
        _fail("registered outcome request predecessor differs")
    return item


def open_recognized_outcome_authority_v1(
    outcome_authority_identity: object, *, read_exact: ReadExact,
    verify_live_lease: HistoricalOutcomeLeaseVerifierV1,
) -> OpenedOutcomeAuthorityV1:
    """Generation-exact replay of the catalog snapshot and every predecessor."""

    reopened_identities: list[dict[str, object]] = []
    seen_identity_bytes: set[bytes] = set()

    def tracked_read(identity: Mapping[str, object]) -> bytes:
        retained = _identity(identity, label="outcome predecessor exact read")
        raw = read_exact(identity)
        key = _canonical(retained)
        if key not in seen_identity_bytes:
            seen_identity_bytes.add(key)
            reopened_identities.append(retained)
        return raw

    expected_completion_identity = _recognized_outcome_identity(
        outcome_authority_identity
    )
    completion_raw, completion_identity, _ = _read_document(
        expected_completion_identity, read_exact=tracked_read,
        label="recognized outcome completion",
        maximum_bytes=MAXIMUM_OUTCOME_COMPLETION_BYTES,
    )
    completion = _completion_body(completion_raw)
    expected_completion_uri = (
        f"{RECOGNIZED_OUTCOME_NAMESPACE}{completion['run_id']}/completion.json"
    )
    if completion_identity["uri"] != expected_completion_uri:
        _fail("recognized outcome completion URI/run binding differs")
    if not callable(verify_live_lease):
        _fail("live historical-outcome lease verifier differs")
    lease_receipt = _live_lease_receipt(
        verify_live_lease(
            expected_identity=completion["historical_outcome_lease_identity"],
            catalog_run_id=str(completion["run_id"]),
        ),
        expected_identity=completion["historical_outcome_lease_identity"],
        catalog_run_id=str(completion["run_id"]),
    )
    lease_body = lease_receipt["body"]
    lease_identity = lease_receipt["object_receipt"]
    lease_body_sha256 = _hash(lease_body)

    projection, projection_identity = _read_predecessor(
        completion["outcome_key_projection_identity"], read_exact=tracked_read,
        label="catalog outcome projection",
    )
    request, request_identity = _read_predecessor(
        completion["registered_request_identity"], read_exact=tracked_read,
        label="catalog registered request",
    )
    evidence, evidence_identity = _read_predecessor(
        completion["query_evidence_identity"], read_exact=tracked_read,
        label="catalog query evidence",
    )
    source, source_identity = _read_predecessor(
        completion["realized_source_identity"], read_exact=tracked_read,
        label="catalog realized source",
    )
    snapshot, snapshot_identity = _read_predecessor(
        completion["outcome_snapshot_identity"], read_exact=tracked_read,
        label="catalog outcome snapshot",
    )
    later_source, later_source_identity = _read_predecessor(
        projection.get("later_source_freeze_identity"), read_exact=tracked_read,
        label="catalog later-source freeze",
    )
    base_snapshot, base_snapshot_identity = _read_predecessor(
        projection.get("base_outcome_snapshot_identity"), read_exact=tracked_read,
        label="catalog base outcome snapshot",
    )
    base_projection, base_projection_identity = _read_predecessor(
        base_snapshot.get("outcome_key_projection_identity"), read_exact=tracked_read,
        label="base outcome projection",
    )
    base_source, base_source_identity = _read_predecessor(
        base_snapshot.get("realized_source_identity"), read_exact=tracked_read,
        label="base realized source",
    )

    try:
        ordinary_outcomes.validate_outcome_snapshot_v1(
            base_snapshot,
            identity=base_snapshot_identity,
            outcome_key_projection=base_projection,
            outcome_key_projection_identity=base_projection_identity,
            realized_source=base_source,
            realized_source_identity=base_source_identity,
            read_exact=tracked_read,
        )
        retained_projection, retained_projection_identity = (
            catalog_outcomes.validate_catalog_wide_projection_v1(
                projection, identity=projection_identity,
                later_source=later_source,
                later_source_identity=later_source_identity,
                later_source_sha256=str(projection["later_source_freeze_sha256"]),
            )
        )
        _validate_registered_request(
            request, request_identity=request_identity,
            projection=retained_projection,
            projection_identity=retained_projection_identity,
            base_snapshot_identity=base_snapshot_identity,
            later_source_identity=later_source_identity,
        )
        catalog_outcomes.validate_catalog_wide_query_evidence_v1(
            evidence, identity=evidence_identity,
            projection=retained_projection,
            projection_identity=retained_projection_identity,
            base_snapshot=base_snapshot,
        )
        catalog_outcomes.validate_catalog_wide_realized_source_v1(
            source, identity=source_identity,
            projection=retained_projection,
            projection_identity=retained_projection_identity,
            base_snapshot=base_snapshot, query_evidence=evidence,
            query_evidence_identity=evidence_identity,
        )
        expected_snapshot = catalog_outcomes.build_catalog_wide_snapshot_v1(
            projection=retained_projection,
            projection_identity=retained_projection_identity,
            later_source=later_source,
            later_source_identity=later_source_identity,
            later_source_sha256=str(projection["later_source_freeze_sha256"]),
            base_snapshot=base_snapshot,
            base_snapshot_identity=base_snapshot_identity,
            base_snapshot_sha256=str(projection["base_outcome_snapshot_sha256"]),
            realized_source=source,
            realized_source_identity=source_identity,
            query_evidence=evidence,
            query_evidence_identity=evidence_identity,
        )
        retained_snapshot_identity, player_scores = (
            catalog_outcomes.validate_catalog_wide_snapshot_v1(
                snapshot, identity=snapshot_identity
            )
        )
    except Exception as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            "recognized outcome predecessor closure differs"
        ) from exc
    if _canonical(snapshot) != _canonical(expected_snapshot):
        _fail("recognized outcome snapshot canonical reconstruction differs")

    completion_identity_fields = {
        "outcome_key_projection_identity": projection_identity,
        "registered_request_identity": request_identity,
        "query_evidence_identity": evidence_identity,
        "realized_source_identity": source_identity,
        "outcome_snapshot_identity": snapshot_identity,
    }
    if any(
        completion.get(field) != identity
        for field, identity in completion_identity_fields.items()
    ):
        _fail("recognized completion/predecessor identity binding differs")
    if retained_snapshot_identity != snapshot_identity:
        _fail("recognized outcome snapshot retained identity differs")

    rows = _sequence(snapshot.get("rows"), label="catalog outcome rows")
    slate_keys: dict[int, tuple[int, int, str]] = {}
    for row in rows:
        item = _mapping(row, label="catalog outcome row")
        ordinal = int(item["source_ordinal"])
        key = (int(item["season"]), int(item["week"]), str(item["slate_id"]))
        if ordinal in slate_keys and slate_keys[ordinal] != key:
            _fail("recognized outcome snapshot splits one slate ordinal")
        slate_keys[ordinal] = key
    if (
        set(slate_keys) != set(range(len(cross.EXPECTED_SLATE_IDS)))
        or [slate_keys[index][2] for index in range(len(slate_keys))]
        != list(cross.EXPECTED_SLATE_IDS)
    ):
        _fail("recognized outcome snapshot slate lattice differs")

    identities = list(reopened_identities)
    if _canonical(lease_identity) not in seen_identity_bytes:
        identities.append(lease_identity)
    closure = _with_hash({
        "schema_version": OUTCOME_CLOSURE_SCHEMA,
        "outcome_completion_identity": completion_identity,
        "outcome_completion_sha256": completion["completion_sha256"],
        "outcome_snapshot_identity": snapshot_identity,
        "outcome_snapshot_sha256": snapshot["outcome_snapshot_sha256"],
        "predecessor_identities": identities,
        "predecessor_identities_sha256": _hash(identities),
        "predecessor_identity_count": len(identities),
        "historical_outcome_lease_identity": lease_identity,
        "historical_outcome_lease_body_sha256": lease_body_sha256,
        "historical_outcome_lease_verified_before_snapshot_open": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        "source_slate_count": len(slate_keys),
        "outcome_row_count": len(rows),
        "all_content_identities_generation_exact_reopened": True,
        "all_observed_predecessor_identities_enumerated": True,
        "base_snapshot_and_panel_predecessor_replayed": True,
        "catalog_snapshot_reconstructed_from_persisted_source": True,
        "recognized_authority_only": True,
        "uses_realized_outcomes": True,
        "additional_historical_outcome_read": False,
        "complete": True,
    }, field="closure_sha256")
    return OpenedOutcomeAuthorityV1(
        completion=completion,
        completion_identity=completion_identity,
        snapshot=snapshot,
        snapshot_identity=snapshot_identity,
        player_scores=dict(player_scores),
        slate_keys=slate_keys,
        lease_body=lease_body,
        lease_identity=lease_identity,
        lease_body_sha256=lease_body_sha256,
        closure_receipt=closure,
    )


def _live_lease_receipt(
    value: Mapping[str, object], *, expected_identity: object,
    catalog_run_id: str,
) -> dict[str, object]:
    receipt = _mapping(value, label="historical-outcome lease")
    if set(receipt) != {"body", "object_receipt"}:
        _fail("historical-outcome lease receipt differs")
    body = _mapping(receipt["body"], label="historical-outcome lease body")
    identity = _identity(
        receipt["object_receipt"], label="historical-outcome active object"
    )
    if (
        identity["uri"] != HISTORICAL_OUTCOME_LEASE_URI
        or identity != _identity(
            expected_identity, label="completion historical-outcome lease"
        )
        or body.get("version") != "historical-outcome-active-v1"
        or body.get("run_id") != catalog_run_id
        or type(body.get("job")) is not str or not body["job"]
        or _COMMIT.fullmatch(str(body.get("code_sha", ""))) is None
        or type(body.get("image")) is not str or not body["image"]
        or set(body) != {"version", "run_id", "job", "code_sha", "image", "acquired_at"}
    ):
        _fail("historical-outcome lease authority differs")
    try:
        acquired_at = datetime.fromisoformat(str(body.get("acquired_at")))
    except ValueError as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            "historical-outcome lease timestamp differs"
        ) from exc
    if acquired_at.tzinfo is None or acquired_at.utcoffset() is None:
        _fail("historical-outcome lease timestamp is not timezone-aware")
    return {"body": body, "object_receipt": identity}


def _selection_reopen_receipt(
    *, manifest: Mapping[str, object], reopened: Mapping[str, object],
) -> dict[str, object]:
    selection = _mapping(reopened.get("selection"), label="reopened selection")
    upstream = _mapping(
        reopened.get("upstream_reopen_receipt"), label="selection upstream reopen"
    )
    if (
        selection.get("receipt_sha256") != manifest.get("selection_receipt_sha256")
        or selection.get("scientific_sha256")
        != manifest.get("selection_scientific_sha256")
    ):
        _fail("grade manifest/selection scientific binding differs")
    return _with_hash({
        "schema_version": SELECTION_REOPEN_SCHEMA,
        "selection_terminal_identity": manifest["selection_terminal_identity"],
        "selection_terminal_envelope_sha256": manifest[
            "selection_terminal_envelope_sha256"
        ],
        "selection_receipt_sha256": selection["receipt_sha256"],
        "selection_scientific_sha256": selection["scientific_sha256"],
        "upstream_reopen_receipt_sha256": upstream["receipt_sha256"],
        "slate_count": len(selection["slates"]),
        "terminal_and_all_selection_predecessors_generation_exact_reopened": True,
        "outcome_data_accessed_during_selection": False,
        "complete": True,
    }, field="selection_reopen_sha256")


def _outcomes_by_slate(
    authority: OpenedOutcomeAuthorityV1,
) -> dict[str, dict[str, str]]:
    by_slate: dict[str, dict[str, str]] = {
        slate_id: {} for slate_id in cross.EXPECTED_SLATE_IDS
    }
    for (ordinal, player_id), micro in authority.player_scores.items():
        if ordinal not in authority.slate_keys:
            _fail("outcome player score has no slate authority")
        slate_id = authority.slate_keys[ordinal][2]
        if player_id in by_slate[slate_id]:
            _fail("outcome player repeats within a slate")
        # The grade science accepts decimal DK points and converts to exact
        # integer-millionths.  Formatting by integer arithmetic avoids float.
        sign = "-" if micro < 0 else ""
        absolute = abs(int(micro))
        by_slate[slate_id][str(player_id)] = (
            f"{sign}{absolute // 1_000_000}.{absolute % 1_000_000:06d}"
        )
    if any(not values for values in by_slate.values()):
        _fail("recognized outcome authority leaves one slate empty")
    return by_slate


def _recompute_report(
    *, manifest: Mapping[str, object],
    outcome_identities: Mapping[str, Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    try:
        report = grade_science.grade_published_cross_v1(
            manifest["selection_terminal_envelope"],
            read_exact=read_exact,
            grade_id=str(manifest["grade_id"]),
            outcome_identities=outcome_identities,
        )
        return grade_science.validate_published_grade_v1(report)
    except Exception as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            "construction/allocation grade recomputation differs"
        ) from exc


def _validate_runtime(
    manifest: Mapping[str, object], *, code_sha: str, immutable_image: str,
) -> None:
    if (
        code_sha != manifest.get("code_sha")
        or immutable_image != manifest.get("immutable_image")
        or _COMMIT.fullmatch(code_sha) is None
        or _IMAGE.fullmatch(immutable_image) is None
    ):
        _fail("grade runtime code/image differs from frozen manifest")


def _reverify_authority_lease(
    authority: OpenedOutcomeAuthorityV1, *,
    verify_live_lease: HistoricalOutcomeLeaseVerifierV1,
) -> dict[str, object]:
    receipt = _live_lease_receipt(
        verify_live_lease(
            expected_identity=authority.lease_identity,
            catalog_run_id=str(authority.completion["run_id"]),
        ),
        expected_identity=authority.lease_identity,
        catalog_run_id=str(authority.completion["run_id"]),
    )
    if (
        receipt["object_receipt"] != authority.lease_identity
        or receipt["body"] != authority.lease_body
        or _hash(receipt["body"]) != authority.lease_body_sha256
    ):
        _fail("historical-outcome lease changed during grade")
    return receipt


def publish_grade_v1(
    *, manifest_identity: object, code_sha: str, immutable_image: str,
    read_exact: ReadExact, publish_create_once: PublishCreateOnce,
    verify_live_lease: HistoricalOutcomeLeaseVerifierV1,
) -> dict[str, object]:
    """Verify the catalog lease, grade once, root-last publish, and reopen."""

    manifest, retained_manifest_identity = open_grade_manifest_v1(
        manifest_identity, read_exact=read_exact
    )
    _validate_runtime(manifest, code_sha=code_sha, immutable_image=immutable_image)
    # Complete selection closure before the first outcome read.
    reopened_selection = _reopen_selection(
        manifest["selection_terminal_envelope"], read_exact=read_exact
    )
    selection_receipt = _selection_reopen_receipt(
        manifest=manifest, reopened=reopened_selection
    )

    try:
        authority = open_recognized_outcome_authority_v1(
            manifest["outcome_authority_identity"], read_exact=read_exact,
            verify_live_lease=verify_live_lease,
        )
        lease_identity = authority.lease_identity

        actuals_by_slate = _outcomes_by_slate(authority)
        # A recognized completion proves the lease before its realized
        # snapshot opens.  Re-observe that exact live generation again after
        # outcome replay but before *any* child publication, so a lease change
        # cannot poison create-once names under a terminal that will be
        # withheld.  The later check remains the final root-publication gate.
        _reverify_authority_lease(
            authority, verify_live_lease=verify_live_lease
        )
        outcome_identities: dict[str, dict[str, object]] = {}
        for ordinal, slate_id in enumerate(cross.EXPECTED_SLATE_IDS):
            document = grade_science.outcome_document_v1(
                slate_id=slate_id,
                actual_points=actuals_by_slate[slate_id],
            )
            outcome_identities[slate_id] = _publish(
                uri=manifest["outcome_document_uris"][ordinal], value=document,
                publish_create_once=publish_create_once, read_exact=read_exact,
                label=f"derived outcome[{ordinal}]",
                maximum_bytes=MAXIMUM_OUTCOME_DOCUMENT_BYTES,
            )

        selection_reopen_identity = _publish(
            uri=str(manifest["selection_reopen_uri"]), value=selection_receipt,
            publish_create_once=publish_create_once, read_exact=read_exact,
            label="selection reopen receipt", maximum_bytes=MAXIMUM_MANIFEST_BYTES,
        )
        outcome_closure_identity = _publish(
            uri=str(manifest["outcome_closure_uri"]),
            value=authority.closure_receipt,
            publish_create_once=publish_create_once, read_exact=read_exact,
            label="outcome predecessor closure", maximum_bytes=MAXIMUM_MANIFEST_BYTES,
        )
        report = _recompute_report(
            manifest=manifest, outcome_identities=outcome_identities,
            read_exact=read_exact,
        )
        report_identity = _publish(
            uri=str(manifest["grade_report_uri"]), value=report,
            publish_create_once=publish_create_once, read_exact=read_exact,
            label="construction/allocation grade report",
            maximum_bytes=MAXIMUM_GRADE_REPORT_BYTES,
        )
        _reverify_authority_lease(
            authority, verify_live_lease=verify_live_lease
        )

        ordered_outcome_identities = [
            outcome_identities[slate_id] for slate_id in cross.EXPECTED_SLATE_IDS
        ]
        terminal = _with_hash({
            "schema_version": TERMINAL_SCHEMA,
            "run_id": manifest["run_id"],
            "grade_id": manifest["grade_id"],
            "code_sha": code_sha,
            "immutable_image": immutable_image,
            "image_digest": manifest["image_digest"],
            "manifest_identity": retained_manifest_identity,
            "manifest_sha256": manifest["manifest_sha256"],
            "selection_terminal_identity": manifest["selection_terminal_identity"],
            "selection_terminal_envelope_sha256": manifest[
                "selection_terminal_envelope_sha256"
            ],
            "selection_reopen_identity": selection_reopen_identity,
            "selection_reopen_sha256": selection_receipt[
                "selection_reopen_sha256"
            ],
            "outcome_authority_identity": authority.completion_identity,
            "outcome_authority_sha256": authority.completion[
                "completion_sha256"
            ],
            "outcome_snapshot_identity": authority.snapshot_identity,
            "outcome_snapshot_sha256": authority.snapshot[
                "outcome_snapshot_sha256"
            ],
            "outcome_closure_identity": outcome_closure_identity,
            "outcome_closure_sha256": authority.closure_receipt["closure_sha256"],
            "outcome_document_identities": ordered_outcome_identities,
            "outcome_document_identities_sha256": _hash(
                ordered_outcome_identities
            ),
            "grade_report_identity": report_identity,
            "grade_report_sha256": report["report_sha256"],
            "historical_outcome_lease_identity": lease_identity,
            "historical_outcome_lease_unchanged_through_grade": True,
            "historical_outcome_lease_body_sha256": authority.lease_body_sha256,
            "historical_outcome_lease_release_required": True,
            "lease_release_owner": "external-launcher-watcher",
            "additional_historical_outcome_read": False,
            "source_slate_count": len(cross.EXPECTED_SLATE_IDS),
            "prefixes": list(cross.PREFIXES),
            "thresholds": list(cross.THRESHOLDS),
            "publication_order_completed": manifest["publication_order"],
            "all_children_create_once_and_exact_reopened": True,
            "terminal_grade_root_published_last": True,
            "selection_and_all_predecessors_reopened_before_outcome_join": True,
            "outcome_authority_and_all_predecessors_generation_exact_reopened": True,
            "grade_recomputed_by_construction_allocation_grade_v1": True,
            "uses_realized_outcomes": True,
            "historical_evidence_status": "descriptive-diagnostic-only",
            "automatic_retry_licensed": False,
            "automatic_policy_promotion": False,
            "production_policy_authority": False,
            "complete": True,
        }, field="terminal_sha256")
        terminal_identity = _publish(
            uri=str(manifest["terminal_uri"]), value=terminal,
            publish_create_once=publish_create_once, read_exact=read_exact,
            label="terminal grade root", maximum_bytes=MAXIMUM_TERMINAL_BYTES,
        )
        envelope = _with_hash({
            "schema_version": TERMINAL_ENVELOPE_SCHEMA,
            "terminal_identity": terminal_identity,
            "terminal_sha256": terminal["terminal_sha256"],
            "manifest_identity": retained_manifest_identity,
            "manifest_sha256": manifest["manifest_sha256"],
            "historical_outcome_lease_identity": lease_identity,
            "terminal_root_was_last_scientific_publication": True,
            "historical_outcome_lease_release_required": True,
            "lease_release_owner": "external-launcher-watcher",
            "complete": True,
        }, field="envelope_sha256")
        reopened = reopen_grade_terminal_v1(
            envelope, read_exact=read_exact, expected_manifest=manifest,
            verify_live_lease=verify_live_lease,
        )
        return {
            "schema_version": "corpus-r6-construction-allocation-grade-published/v1",
            "terminal_envelope": envelope,
            "terminal_identity": terminal_identity,
            "grade_report_identity": report_identity,
            "historical_outcome_lease_identity": lease_identity,
            "historical_outcome_lease_release_required": True,
            "lease_release_owner": "external-launcher-watcher",
            "historical_outcome_lease_released": False,
            "terminal_reopen_receipt_sha256": reopened["reopen_sha256"],
            "uses_realized_outcomes": True,
            "automatic_retry_licensed": False,
            "complete": True,
        }
    except Exception:
        raise


def _validate_terminal_envelope(value: object) -> dict[str, object]:
    envelope = _mapping(value, label="grade terminal envelope")
    body = dict(envelope)
    retained_hash = body.pop("envelope_sha256", None)
    if (
        frozenset(envelope) != _TERMINAL_ENVELOPE_FIELDS
        or envelope.get("schema_version") != TERMINAL_ENVELOPE_SCHEMA
        or type(retained_hash) is not str or _SHA.fullmatch(retained_hash) is None
        or _hash(body) != retained_hash
        or envelope.get("terminal_root_was_last_scientific_publication") is not True
        or envelope.get("historical_outcome_lease_release_required") is not True
        or envelope.get("lease_release_owner") != "external-launcher-watcher"
        or envelope.get("complete") is not True
    ):
        _fail("grade terminal envelope differs")
    _identity(
        envelope.get("terminal_identity"), label="grade terminal root",
        require_create_once=True,
    )
    _identity(
        envelope.get("manifest_identity"), label="grade manifest root",
        require_create_once=True,
    )
    return envelope


def reopen_grade_terminal_v1(
    terminal_envelope: Mapping[str, object], *, read_exact: ReadExact,
    verify_live_lease: HistoricalOutcomeLeaseVerifierV1,
    expected_manifest: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Deep replay terminal, every child, and both predecessor closures."""

    envelope = _validate_terminal_envelope(terminal_envelope)
    terminal_raw, terminal_identity, _ = _read_document(
        envelope["terminal_identity"], read_exact=read_exact,
        label="terminal grade root", maximum_bytes=MAXIMUM_TERMINAL_BYTES,
    )
    body = dict(terminal_raw)
    retained_terminal_hash = body.pop("terminal_sha256", None)
    if (
        frozenset(terminal_raw) != _TERMINAL_FIELDS
        or terminal_raw.get("schema_version") != TERMINAL_SCHEMA
        or type(retained_terminal_hash) is not str
        or _SHA.fullmatch(retained_terminal_hash) is None
        or _hash(body) != retained_terminal_hash
        or retained_terminal_hash != envelope.get("terminal_sha256")
        or terminal_raw.get("terminal_grade_root_published_last") is not True
        or terminal_raw.get("all_children_create_once_and_exact_reopened") is not True
        or terminal_raw.get(
            "selection_and_all_predecessors_reopened_before_outcome_join"
        ) is not True
        or terminal_raw.get(
            "outcome_authority_and_all_predecessors_generation_exact_reopened"
        ) is not True
        or terminal_raw.get("grade_recomputed_by_construction_allocation_grade_v1")
        is not True
        or terminal_raw.get("historical_outcome_lease_unchanged_through_grade")
        is not True
        or terminal_raw.get("historical_outcome_lease_release_required") is not True
        or terminal_raw.get("lease_release_owner") != "external-launcher-watcher"
        or terminal_raw.get("additional_historical_outcome_read") is not False
        or terminal_raw.get("source_slate_count") != len(cross.EXPECTED_SLATE_IDS)
        or terminal_raw.get("prefixes") != list(cross.PREFIXES)
        or terminal_raw.get("thresholds") != list(cross.THRESHOLDS)
        or terminal_raw.get("uses_realized_outcomes") is not True
        or terminal_raw.get("historical_evidence_status")
        != "descriptive-diagnostic-only"
        or terminal_raw.get("complete") is not True
        or any(terminal_raw.get(field) is not False for field in (
            "automatic_retry_licensed", "automatic_policy_promotion",
            "production_policy_authority",
        ))
    ):
        _fail("terminal grade root fixed law differs")
    if terminal_identity != envelope["terminal_identity"]:
        _fail("grade terminal envelope/root identity differs")

    manifest, manifest_identity = open_grade_manifest_v1(
        terminal_raw["manifest_identity"], read_exact=read_exact
    )
    if expected_manifest is not None and manifest != dict(expected_manifest):
        _fail("terminal grade expected manifest differs")
    if (
        manifest_identity != terminal_raw.get("manifest_identity")
        or manifest_identity != envelope.get("manifest_identity")
        or manifest["manifest_sha256"] != terminal_raw.get("manifest_sha256")
        or manifest["manifest_sha256"] != envelope.get("manifest_sha256")
        or terminal_identity["uri"] != manifest["terminal_uri"]
        or terminal_raw.get("run_id") != manifest["run_id"]
        or terminal_raw.get("grade_id") != manifest["grade_id"]
        or terminal_raw.get("code_sha") != manifest["code_sha"]
        or terminal_raw.get("immutable_image") != manifest["immutable_image"]
        or terminal_raw.get("image_digest") != manifest["image_digest"]
        or terminal_raw.get("selection_terminal_identity")
        != manifest["selection_terminal_identity"]
        or terminal_raw.get("selection_terminal_envelope_sha256")
        != manifest["selection_terminal_envelope_sha256"]
        or terminal_raw.get("outcome_authority_identity")
        != manifest["outcome_authority_identity"]
        or terminal_raw.get("publication_order_completed")
        != manifest["publication_order"]
    ):
        _fail("terminal grade manifest binding differs")
    reopened_selection = _reopen_selection(
        manifest["selection_terminal_envelope"], read_exact=read_exact
    )
    selection_receipt = _selection_reopen_receipt(
        manifest=manifest, reopened=reopened_selection
    )
    stored_selection_receipt, selection_reopen_identity, _ = _read_document(
        terminal_raw["selection_reopen_identity"], read_exact=read_exact,
        label="selection reopen child", maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )
    if (
        stored_selection_receipt != selection_receipt
        or selection_reopen_identity != terminal_raw["selection_reopen_identity"]
        or selection_reopen_identity["uri"] != manifest["selection_reopen_uri"]
        or selection_receipt["selection_reopen_sha256"]
        != terminal_raw.get("selection_reopen_sha256")
    ):
        _fail("terminal selection-reopen child differs")

    authority = open_recognized_outcome_authority_v1(
        manifest["outcome_authority_identity"], read_exact=read_exact,
        verify_live_lease=verify_live_lease,
    )
    if (
        authority.completion_identity != terminal_raw.get("outcome_authority_identity")
        or authority.completion["completion_sha256"]
        != terminal_raw.get("outcome_authority_sha256")
        or authority.snapshot_identity != terminal_raw.get("outcome_snapshot_identity")
        or authority.snapshot["outcome_snapshot_sha256"]
        != terminal_raw.get("outcome_snapshot_sha256")
        or authority.lease_identity
        != terminal_raw.get("historical_outcome_lease_identity")
        or authority.lease_body_sha256
        != terminal_raw.get("historical_outcome_lease_body_sha256")
        or envelope.get("historical_outcome_lease_identity")
        != authority.lease_identity
    ):
        _fail("terminal outcome authority binding differs")
    stored_closure, closure_identity, _ = _read_document(
        terminal_raw["outcome_closure_identity"], read_exact=read_exact,
        label="outcome closure child", maximum_bytes=MAXIMUM_MANIFEST_BYTES,
    )
    if (
        stored_closure != authority.closure_receipt
        or closure_identity != terminal_raw["outcome_closure_identity"]
        or closure_identity["uri"] != manifest["outcome_closure_uri"]
        or authority.closure_receipt["closure_sha256"]
        != terminal_raw.get("outcome_closure_sha256")
    ):
        _fail("terminal outcome-closure child differs")

    raw_outcome_identities = _sequence(
        terminal_raw.get("outcome_document_identities"),
        label="terminal outcome document identities",
    )
    if (
        len(raw_outcome_identities) != len(cross.EXPECTED_SLATE_IDS)
        or terminal_raw.get("outcome_document_identities_sha256")
        != _hash(raw_outcome_identities)
    ):
        _fail("terminal outcome-document identity lattice differs")
    outcome_identities: dict[str, dict[str, object]] = {}
    for ordinal, (slate_id, raw_identity) in enumerate(zip(
        cross.EXPECTED_SLATE_IDS, raw_outcome_identities, strict=True
    )):
        document, identity, _ = _read_document(
            raw_identity, read_exact=read_exact,
            label=f"derived outcome[{ordinal}]",
            maximum_bytes=MAXIMUM_OUTCOME_DOCUMENT_BYTES,
        )
        if (
            identity["uri"] != manifest["outcome_document_uris"][ordinal]
            or document.get("schema_version")
            != grade_science.OUTCOME_DOCUMENT_SCHEMA
            or document.get("slate_id") != slate_id
        ):
            _fail(f"derived outcome[{ordinal}] binding differs")
        outcome_identities[slate_id] = identity

    report_document, report_identity, report_raw = _read_document(
        terminal_raw["grade_report_identity"], read_exact=read_exact,
        label="construction/allocation grade report",
        maximum_bytes=MAXIMUM_GRADE_REPORT_BYTES,
    )
    try:
        stored_report = grade_science.validate_published_grade_v1(
            report_document
        )
    except Exception as exc:
        raise ConstructionAllocationGradeOperatorV1Error(
            "published construction/allocation grade differs"
        ) from exc
    recomputed_report = _recompute_report(
        manifest=manifest, outcome_identities=outcome_identities,
        read_exact=read_exact,
    )
    if (
        report_identity != terminal_raw.get("grade_report_identity")
        or report_identity["uri"] != manifest["grade_report_uri"]
        or stored_report != recomputed_report
        or report_raw != _canonical(recomputed_report)
        or recomputed_report["report_sha256"]
        != terminal_raw.get("grade_report_sha256")
    ):
        _fail("terminal grade report does not equal independent recomputation")
    _reverify_authority_lease(
        authority, verify_live_lease=verify_live_lease
    )

    receipt = _with_hash({
        "schema_version": REOPEN_SCHEMA,
        "terminal_identity": terminal_identity,
        "terminal_sha256": retained_terminal_hash,
        "manifest_identity": manifest_identity,
        "selection_terminal_identity": manifest["selection_terminal_identity"],
        "outcome_authority_identity": authority.completion_identity,
        "outcome_snapshot_identity": authority.snapshot_identity,
        "historical_outcome_lease_identity": authority.lease_identity,
        "historical_outcome_lease_body_sha256": authority.lease_body_sha256,
        "historical_outcome_lease_unchanged_during_reopen": True,
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": "external-launcher-watcher",
        "grade_report_identity": report_identity,
        "outcome_document_count": len(outcome_identities),
        "selection_predecessor_closure_replayed": True,
        "outcome_predecessor_closure_replayed": True,
        "all_grade_children_generation_exact_reopened": True,
        "grade_independently_recomputed": True,
        "object_listing_used": False,
        "overwrite_used": False,
        "scientific_object_delete_used": False,
        "uses_realized_outcomes": True,
        "complete": True,
    }, field="reopen_sha256")
    return receipt


__all__ = [
    "ConstructionAllocationGradeOperatorV1Error",
    "HISTORICAL_OUTCOME_LEASE_URI",
    "HistoricalOutcomeLeaseVerifierV1",
    "MANIFEST_SCHEMA",
    "OUTCOME_CLOSURE_SCHEMA",
    "OpenedOutcomeAuthorityV1",
    "RECOGNIZED_OUTCOME_COMPLETION_SCHEMA",
    "REOPEN_SCHEMA",
    "SELECTION_REOPEN_SCHEMA",
    "TERMINAL_ENVELOPE_SCHEMA",
    "TERMINAL_SCHEMA",
    "open_grade_manifest_v1",
    "open_recognized_outcome_authority_v1",
    "prepare_grade_manifest_v1",
    "publish_grade_v1",
    "reopen_grade_terminal_v1",
    "validate_grade_manifest_v1",
]
