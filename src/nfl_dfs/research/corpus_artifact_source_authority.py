"""Pure authority for the corpus batch's retained artifact-supported source.

The retained later-period freeze is useful, but its player universe is the
exact player set carried by the five R0--R4 world artifacts.  It is not, and
this module never calls it, a complete DraftKings salary universe.  A separate
salary-ID diagnostic measures that boundary without inventing world draws for
salary-only players.

The production-facing verifier consumes an already generation-pinned, closed
iterator of 270 bodies.  It never accepts a storage callback and never holds
more than one NPZ body/decoded block at a time.  Transport, object reopening,
and publication remain outside this module.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_parametric_batch import TASK_WORLD_SOURCE_ROLES
from nfl_dfs.research.object_identity import content_identity


REGISTRATION_SCHEMA: Final = "corpus-artifact-source-registration/v1"
SALARY_DIAGNOSTIC_SCHEMA: Final = (
    "corpus-salary-universe-coverage-diagnostic/v1"
)
COMPLETION_SCHEMA: Final = (
    "corpus-artifact-supported-source-authority-completion/v1"
)
UNIVERSE_SCOPE: Final = "exact-artifact-supported-r0-r4-player-universe"
SALARY_DIAGNOSTIC_SCOPE: Final = (
    "predeclared-query-relative-salary-player-id-coverage-diagnostic"
)
EXPECTED_TASK_COUNT: Final = len(later.EXPECTED_SLATE_KEYS)
EXPECTED_ARTIFACT_COUNT: Final = EXPECTED_TASK_COUNT * len(rw.WORLD_BLOCKS)

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")
_BIGQUERY_TABLE: Final = re.compile(
    r"[A-Za-z0-9_-]+\.[A-Za-z0-9_]+\.[A-Za-z0-9_]+"
)
_OBJECT_IDENTITY_KEYS: Final = frozenset({
    "uri", "generation", "sha256", "bytes",
})
_QUERY_IDENTITY_KEYS: Final = frozenset({
    "job_id", "location", "table", "sql_sha256", "parameters_sha256",
    "selected_columns", "realized_columns_selected",
})
_QUERY_RECEIPT_KEYS: Final = frozenset({
    "job_id", "location", "sql_sha256", "parameters_sha256", "created",
    "started", "ended", "total_bytes_processed", "cache_hit",
    "error_result",
})
_REGISTRATION_KEYS: Final = frozenset({
    "schema", "authority_id", "registered_at", "source_snapshot_at",
    "source_run_id", "source_queries", "salary_universe_query",
    "universe_scope", "uses_realized_outcomes", "registration_sha256",
})
_SALARY_DIAGNOSTIC_KEYS: Final = frozenset({
    "schema", "registration_sha256", "universe_scope", "query",
    "slate_count", "slates", "coverage_only", "world_draws_attached",
    "coverage_is_predeclared_query_relative",
    "query_result_independently_verified",
    "complete_dk_salary_coverage_claimed",
    "outcome_columns_read", "uses_realized_outcomes", "diagnostic_sha256",
})
_SALARY_QUERY_KEYS: Final = frozenset({
    "source_snapshot_at", "table", "query_receipt", "selected_columns",
    "realized_columns_selected",
})
_SALARY_SLATE_KEYS: Final = frozenset({
    "task_index", "season", "week", "slate_id", "salary_player_ids",
    "salary_player_ids_sha256",
})
_ARTIFACT_VALIDATION_KEYS: Final = frozenset({
    "artifact_ordinal", "role", "object", "candidate_rows", "player_count",
    "ordered_player_ids_sha256", "player_set_sha256", "npz_fields",
    "player_draws_dtype", "player_draws_shape", "world_count",
    "player_set_matches_catalog", "uses_realized_outcomes",
})
_TASK_KEYS: Final = frozenset({
    "task_index", "season", "week", "slate_id", "universe_scope",
    "registration_sha256", "later_source_freeze_manifest_sha256",
    "salary_diagnostic_sha256",
    "catalog_sha256", "catalog_player_count", "catalog_player_ids_sha256",
    "incumbent_candidates_sha256", "world_artifact_receipts",
    "world_artifact_receipt_set_sha256", "world_artifact_validations",
    "world_artifact_validation_set_sha256", "salary_coverage",
    "complete_dk_salary_universe_claimed", "task_source_authority_sha256",
})
_SALARY_COVERAGE_KEYS: Final = frozenset({
    "salary_player_count", "salary_player_ids_sha256",
    "artifact_supported_player_count", "artifact_supported_player_ids_sha256",
    "artifact_supported_in_salary_count", "salary_only_player_count",
    "salary_only_player_ids_sha256", "artifact_only_player_count",
    "artifact_only_player_ids_sha256", "artifact_equals_salary_diagnostic",
    "salary_only_players_have_world_draws",
    "coverage_is_predeclared_query_relative",
    "query_result_independently_verified",
    "complete_dk_salary_coverage_claimed",
})
_COMPLETION_KEYS: Final = frozenset({
    "schema", "authority_scope", "registration_object",
    "registration_sha256", "later_source_freeze_object",
    "later_source_freeze_manifest_sha256", "salary_diagnostic_object",
    "salary_diagnostic_sha256", "task_count", "world_blocks",
    "worlds_per_block", "artifact_count", "artifact_stream_order",
    "artifact_receipt_manifest_sha256",
    "artifact_validation_manifest_sha256", "tasks", "task_manifest_sha256",
    "salary_coverage_summary", "artifact_supported_universe_complete",
    "complete_dk_salary_universe_claimed",
    "salary_coverage_is_predeclared_query_relative",
    "salary_query_result_independently_verified",
    "complete_dk_salary_coverage_claimed",
    "salary_only_players_have_world_draws", "outcome_columns_read",
    "uses_realized_outcomes", "historical_scoring_licensed",
    "production_change_licensed", "live_strategy_authority",
    "completion_sha256",
})
_COVERAGE_SUMMARY_KEYS: Final = frozenset({
    "task_count", "exact_match_task_count", "artifact_player_slate_count",
    "salary_player_slate_count", "salary_only_player_slate_count",
    "coverage_numerator_artifact_player_slates",
    "coverage_denominator_salary_player_slates", "diagnostic_required",
    "diagnostic_grants_world_draws",
    "coverage_is_predeclared_query_relative",
    "query_result_independently_verified",
    "complete_dk_salary_coverage_claimed",
})


class CorpusArtifactSourceAuthorityError(ValueError):
    """A fail-closed artifact-supported source authority violation."""


@dataclass(frozen=True, slots=True)
class RetainedArtifactBody:
    """One exact item in the task-major, R0--R4 retained-body stream."""

    task_index: int
    role: str
    identity: Mapping[str, object]
    raw: bytes = field(compare=False, repr=False)


def canonical_json_bytes(value: object) -> bytes:
    """Return the canonical JSON representation used by this authority."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusArtifactSourceAuthorityError(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusArtifactSourceAuthorityError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if type(value) is not list:
        raise CorpusArtifactSourceAuthorityError(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} keys differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} must be a canonical string"
        )
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} must be a lowercase SHA-256"
        )
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} must be an exact integer >= {minimum}"
        )
    return value


def _timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise CorpusArtifactSourceAuthorityError(f"{label} must be UTC")
    return text, parsed


def _parse_canonical_json(
    raw: bytes, *, label: str, later_source: bool = False,
) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CorpusArtifactSourceAuthorityError(
                    f"{label} contains duplicate key {key!r}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} contains non-finite number {value}"
        )

    if type(raw) is not bytes:
        raise CorpusArtifactSourceAuthorityError(f"{label} must be bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except CorpusArtifactSourceAuthorityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} is not valid JSON"
        ) from exc
    rebuilt = later.canonical_json(value) if later_source else canonical_json_bytes(value)
    if rebuilt != raw:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} is not canonical JSON"
        )
    return value


def _object_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, _OBJECT_IDENTITY_KEYS, label=label)
    uri = _string(item["uri"], label=f"{label}.uri")
    tail = uri.removeprefix("gs://")
    bucket, separator, name = tail.partition("/")
    if (
        not uri.startswith("gs://")
        or not bucket
        or not separator
        or not name
        or uri.endswith("/")
        or "//" in name
        or ".." in name.split("/")
    ):
        raise CorpusArtifactSourceAuthorityError(
            f"{label}.uri must be a canonical GCS object URI"
        )
    generation = _string(item["generation"], label=f"{label}.generation")
    if _GENERATION.fullmatch(generation) is None:
        raise CorpusArtifactSourceAuthorityError(
            f"{label}.generation must be a positive decimal string"
        )
    normalized = {
        "uri": uri,
        "generation": generation,
        "sha256": _sha(item["sha256"], label=f"{label}.sha256"),
        "bytes": _exact_int(item["bytes"], label=f"{label}.bytes", minimum=1),
    }
    try:
        content_identity(normalized)
    except (TypeError, ValueError) as exc:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} content identity differs"
        ) from exc
    return normalized


def _bind_raw_object(
    raw: bytes, identity: object, *, label: str,
) -> dict[str, object]:
    normalized = _object_identity(identity, label=label)
    if (
        type(raw) is not bytes
        or len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        raise CorpusArtifactSourceAuthorityError(
            f"{label} retained bytes differ"
        )
    return normalized


def _self_hashed(
    value: object, *, label: str, hash_field: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label=label))
    retained = _sha(item.get(hash_field), label=f"{label}.{hash_field}")
    body = {key: item[key] for key in item if key != hash_field}
    if retained != canonical_sha256(body):
        raise CorpusArtifactSourceAuthorityError(f"{label} self-hash differs")
    return item


def _query_identity(
    value: object, *, label: str, expected_columns: Sequence[str],
) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, _QUERY_IDENTITY_KEYS, label=label)
    table = _string(item["table"], label=f"{label}.table")
    if _BIGQUERY_TABLE.fullmatch(table) is None:
        raise CorpusArtifactSourceAuthorityError(
            f"{label}.table must be project.dataset.table"
        )
    columns = _sequence(item["selected_columns"], label=f"{label}.selected_columns")
    if list(columns) != list(expected_columns) or any(
        type(column) is not str for column in columns
    ):
        raise CorpusArtifactSourceAuthorityError(
            f"{label}.selected_columns differ"
        )
    realized = _sequence(
        item["realized_columns_selected"],
        label=f"{label}.realized_columns_selected",
    )
    if list(realized) != []:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} selects realized outcome columns"
        )
    return {
        "job_id": _string(item["job_id"], label=f"{label}.job_id"),
        "location": _string(item["location"], label=f"{label}.location"),
        "table": table,
        "sql_sha256": _sha(item["sql_sha256"], label=f"{label}.sql_sha256"),
        "parameters_sha256": _sha(
            item["parameters_sha256"], label=f"{label}.parameters_sha256"
        ),
        "selected_columns": list(columns),
        "realized_columns_selected": [],
    }


def _query_receipt(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, _QUERY_RECEIPT_KEYS, label=label)
    created, created_dt = _timestamp(item["created"], label=f"{label}.created")
    started, started_dt = _timestamp(item["started"], label=f"{label}.started")
    ended, ended_dt = _timestamp(item["ended"], label=f"{label}.ended")
    if not created_dt <= started_dt <= ended_dt:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} chronology differs"
        )
    if item["cache_hit"] is not False or item["error_result"] is not None:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} must be uncached terminal success"
        )
    return {
        "job_id": _string(item["job_id"], label=f"{label}.job_id"),
        "location": _string(item["location"], label=f"{label}.location"),
        "sql_sha256": _sha(item["sql_sha256"], label=f"{label}.sql_sha256"),
        "parameters_sha256": _sha(
            item["parameters_sha256"], label=f"{label}.parameters_sha256"
        ),
        "created": created,
        "started": started,
        "ended": ended,
        "total_bytes_processed": _exact_int(
            item["total_bytes_processed"],
            label=f"{label}.total_bytes_processed",
        ),
        "cache_hit": False,
        "error_result": None,
    }


def validate_registration(value: object) -> dict[str, object]:
    """Validate the self-hashed source/query registration."""
    item = _self_hashed(
        value, label="source registration", hash_field="registration_sha256"
    )
    _exact_keys(item, _REGISTRATION_KEYS, label="source registration")
    if (
        item["schema"] != REGISTRATION_SCHEMA
        or item["universe_scope"] != UNIVERSE_SCOPE
        or item["uses_realized_outcomes"] is not False
    ):
        raise CorpusArtifactSourceAuthorityError(
            "source registration identity/license differs"
        )
    _string(item["authority_id"], label="source registration.authority_id")
    _, registered_at = _timestamp(
        item["registered_at"], label="source registration.registered_at"
    )
    snapshot, snapshot_at = _timestamp(
        item["source_snapshot_at"],
        label="source registration.source_snapshot_at",
    )
    run_id = _string(item["source_run_id"], label="source registration.source_run_id")
    queries = _mapping(item["source_queries"], label="source registration.source_queries")
    _exact_keys(
        queries,
        frozenset({"r0_candidates", "artifact_catalog"}),
        label="source registration.source_queries",
    )
    parameters_sha = later.canonical_sha256(
        later.source_parameter_payload(snapshot)
    )
    candidate = _query_identity(
        queries["r0_candidates"],
        label="source registration R0 query",
        expected_columns=sorted(later.R0_CANDIDATE_FIELDS),
    )
    catalog = _query_identity(
        queries["artifact_catalog"],
        label="source registration artifact-catalog query",
        expected_columns=sorted(later.CATALOG_FIELDS),
    )
    salary = _query_identity(
        item["salary_universe_query"],
        label="source registration salary-universe query",
        expected_columns=("id", "season", "week"),
    )
    if (
        candidate["job_id"] != f"{run_id}-r0-candidates"
        or catalog["job_id"] != f"{run_id}-full-catalog"
        or candidate["location"] != later.LOCATION
        or catalog["location"] != later.LOCATION
        or candidate["table"] != later.CANDIDATE_TABLE
        or catalog["table"] != later.CATALOG_TABLE
        or candidate["sql_sha256"] != later.CANDIDATE_SQL_SHA256
        or catalog["sql_sha256"] != later.CATALOG_SQL_SHA256
        or candidate["parameters_sha256"] != parameters_sha
        or catalog["parameters_sha256"] != parameters_sha
        or salary["job_id"] in {candidate["job_id"], catalog["job_id"]}
        or registered_at > snapshot_at
    ):
        raise CorpusArtifactSourceAuthorityError(
            "source registration exact query projection differs"
        )
    normalized = dict(item)
    normalized["source_queries"] = {
        "r0_candidates": candidate,
        "artifact_catalog": catalog,
    }
    normalized["salary_universe_query"] = salary
    return normalized


def _registration_from_bytes(
    raw: bytes, identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    object_identity = _bind_raw_object(raw, identity, label="registration object")
    registration = validate_registration(
        _parse_canonical_json(raw, label="source registration")
    )
    if object_identity["sha256"] == registration["registration_sha256"]:
        raise CorpusArtifactSourceAuthorityError(
            "registration object/internal hashes are conflated"
        )
    return registration, object_identity


def _salary_diagnostic_from_bytes(
    raw: bytes,
    identity: object,
    *,
    registration: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    object_identity = _bind_raw_object(
        raw, identity, label="salary diagnostic object"
    )
    item = _self_hashed(
        _parse_canonical_json(raw, label="salary diagnostic"),
        label="salary diagnostic",
        hash_field="diagnostic_sha256",
    )
    _exact_keys(item, _SALARY_DIAGNOSTIC_KEYS, label="salary diagnostic")
    if (
        item["schema"] != SALARY_DIAGNOSTIC_SCHEMA
        or item["registration_sha256"] != registration["registration_sha256"]
        or item["universe_scope"] != SALARY_DIAGNOSTIC_SCOPE
        or item["slate_count"] != EXPECTED_TASK_COUNT
        or item["coverage_only"] is not True
        or item["world_draws_attached"] is not False
        or item["coverage_is_predeclared_query_relative"] is not True
        or item["query_result_independently_verified"] is not False
        or item["complete_dk_salary_coverage_claimed"] is not False
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
    ):
        raise CorpusArtifactSourceAuthorityError(
            "salary diagnostic identity/license differs"
        )
    query = _mapping(item["query"], label="salary diagnostic.query")
    _exact_keys(query, _SALARY_QUERY_KEYS, label="salary diagnostic.query")
    snapshot, _ = _timestamp(
        query["source_snapshot_at"],
        label="salary diagnostic.query.source_snapshot_at",
    )
    selected = _sequence(
        query["selected_columns"],
        label="salary diagnostic.query.selected_columns",
    )
    realized = _sequence(
        query["realized_columns_selected"],
        label="salary diagnostic.query.realized_columns_selected",
    )
    receipt = _query_receipt(
        query["query_receipt"], label="salary diagnostic query receipt"
    )
    registered_query = registration["salary_universe_query"]
    if (
        snapshot != registration["source_snapshot_at"]
        or query["table"] != registered_query["table"]
        or list(selected) != registered_query["selected_columns"]
        or list(realized) != []
        or any(
            receipt[key] != registered_query[key]
            for key in (
                "job_id", "location", "sql_sha256", "parameters_sha256"
            )
        )
    ):
        raise CorpusArtifactSourceAuthorityError(
            "salary diagnostic differs from its predeclared query"
        )
    slates = _sequence(item["slates"], label="salary diagnostic.slates")
    if len(slates) != EXPECTED_TASK_COUNT:
        raise CorpusArtifactSourceAuthorityError(
            "salary diagnostic slate coverage differs"
        )
    for task_index, (raw_slate, key) in enumerate(
        zip(slates, later.EXPECTED_SLATE_KEYS, strict=True)
    ):
        slate = _mapping(raw_slate, label=f"salary diagnostic.slates[{task_index}]")
        _exact_keys(
            slate,
            _SALARY_SLATE_KEYS,
            label=f"salary diagnostic.slates[{task_index}]",
        )
        ids = _sequence(
            slate["salary_player_ids"],
            label=f"salary diagnostic.slates[{task_index}].salary_player_ids",
        )
        normalized_ids = tuple(
            _string(value, label="salary diagnostic player id") for value in ids
        )
        if (
            type(slate["task_index"]) is not int
            or slate["task_index"] != task_index
            or type(slate["season"]) is not int
            or type(slate["week"]) is not int
            or (slate["season"], slate["week"]) != key
            or slate["slate_id"] != f"{key[0]}-w{key[1]:02d}"
            or not normalized_ids
            or normalized_ids != tuple(sorted(set(normalized_ids)))
            or slate["salary_player_ids_sha256"]
            != canonical_sha256(list(normalized_ids))
        ):
            raise CorpusArtifactSourceAuthorityError(
                f"salary diagnostic slate[{task_index}] identity differs"
            )
    if object_identity["sha256"] == item["diagnostic_sha256"]:
        raise CorpusArtifactSourceAuthorityError(
            "salary diagnostic object/internal hashes are conflated"
        )
    return dict(item), object_identity


def _source_freeze_from_bytes(
    raw: bytes, identity: object,
) -> tuple[dict[str, object], dict[str, object]]:
    object_identity = _bind_raw_object(
        raw, identity, label="later-source freeze object"
    )
    parsed = _mapping(
        _parse_canonical_json(
            raw, label="later-source freeze", later_source=True
        ),
        label="later-source freeze",
    )
    internal_sha = _sha(
        parsed.get("freeze_sha256"),
        label="later-source freeze.freeze_sha256",
    )
    try:
        source = later.validate_source_freeze(
            parsed, expected_freeze_sha256=internal_sha
        )
    except later.LR8LaterSourceError as exc:
        raise CorpusArtifactSourceAuthorityError(
            "later-source freeze failed schema replay"
        ) from exc
    if object_identity["sha256"] == internal_sha:
        raise CorpusArtifactSourceAuthorityError(
            "later-source freeze object/internal hashes are conflated"
        )
    return source, object_identity


def _source_query_projection(
    source: Mapping[str, object], *, registration: Mapping[str, object],
) -> tuple[datetime, datetime, datetime]:
    runtime = source["runtime_identity"]
    source_query = source["source_query"]
    queries = registration["source_queries"]
    candidate_receipt = _query_receipt(
        source_query["candidate_query"], label="source R0 query receipt"
    )
    catalog_receipt = _query_receipt(
        source_query["catalog_query"], label="source catalog query receipt"
    )
    registered_at_text, registered_at = _timestamp(
        registration["registered_at"], label="source registration.registered_at"
    )
    del registered_at_text
    candidate_created = _timestamp(
        candidate_receipt["created"], label="source R0 query receipt.created"
    )[1]
    catalog_created = _timestamp(
        catalog_receipt["created"], label="source catalog query receipt.created"
    )[1]
    if (
        runtime["run_id"] != registration["source_run_id"]
        or source_query["source_snapshot_at"]
        != registration["source_snapshot_at"]
        or source_query["candidate_table"]
        != queries["r0_candidates"]["table"]
        or source_query["catalog_table"]
        != queries["artifact_catalog"]["table"]
        or source_query["selected_columns"]["candidates"]
        != queries["r0_candidates"]["selected_columns"]
        or source_query["selected_columns"]["catalog"]
        != queries["artifact_catalog"]["selected_columns"]
        or source_query["realized_columns_selected"] != []
        or any(
            candidate_receipt[key] != queries["r0_candidates"][key]
            for key in (
                "job_id", "location", "sql_sha256", "parameters_sha256"
            )
        )
        or any(
            catalog_receipt[key] != queries["artifact_catalog"][key]
            for key in (
                "job_id", "location", "sql_sha256", "parameters_sha256"
            )
        )
        or registered_at > candidate_created
        or registered_at > catalog_created
    ):
        raise CorpusArtifactSourceAuthorityError(
            "later-source freeze differs from predeclared query identity"
        )
    return registered_at, candidate_created, catalog_created


def _artifact_identity_from_source(
    value: object, *, label: str,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    try:
        projection = {
            key: item[key] for key in ("uri", "generation", "sha256", "bytes")
        }
    except KeyError as exc:
        raise CorpusArtifactSourceAuthorityError(
            f"{label} lacks object identity"
        ) from exc
    return _object_identity(projection, label=label)


def _salary_coverage(
    catalog_ids: tuple[str, ...], salary_ids: tuple[str, ...],
) -> dict[str, object]:
    catalog_set = set(catalog_ids)
    salary_set = set(salary_ids)
    artifact_only = tuple(sorted(catalog_set - salary_set))
    if artifact_only:
        raise CorpusArtifactSourceAuthorityError(
            "artifact-supported player IDs are absent from salary diagnostic"
        )
    salary_only = tuple(sorted(salary_set - catalog_set))
    return {
        "salary_player_count": len(salary_ids),
        "salary_player_ids_sha256": canonical_sha256(list(salary_ids)),
        "artifact_supported_player_count": len(catalog_ids),
        "artifact_supported_player_ids_sha256": canonical_sha256(
            list(catalog_ids)
        ),
        "artifact_supported_in_salary_count": len(catalog_ids),
        "salary_only_player_count": len(salary_only),
        "salary_only_player_ids_sha256": canonical_sha256(list(salary_only)),
        "artifact_only_player_count": 0,
        "artifact_only_player_ids_sha256": canonical_sha256([]),
        "artifact_equals_salary_diagnostic": not salary_only,
        "salary_only_players_have_world_draws": False,
        "coverage_is_predeclared_query_relative": True,
        "query_result_independently_verified": False,
        "complete_dk_salary_coverage_claimed": False,
    }


def _task_hash(body: Mapping[str, object]) -> dict[str, object]:
    result = dict(body)
    result["task_source_authority_sha256"] = canonical_sha256(result)
    return result


def verify_artifact_supported_source_authority(
    *,
    later_source_freeze_bytes: bytes,
    later_source_freeze_object: object,
    registration_bytes: bytes,
    registration_object: object,
    salary_diagnostic_bytes: bytes,
    salary_diagnostic_object: object,
    artifact_bodies: Iterator[RetainedArtifactBody],
) -> bytes:
    """Stream-verify all 270 bodies and return a self-hashed completion.

    ``artifact_bodies`` is deliberately an iterator rather than a loader or a
    mapping.  Its only legal order is task 0 R0..R4, task 1 R0..R4, through
    task 53 R0..R4, followed by immediate exhaustion.
    """
    if not isinstance(artifact_bodies, Iterator):
        raise CorpusArtifactSourceAuthorityError(
            "artifact bodies must be one closed iterator"
        )
    registration, registration_identity = _registration_from_bytes(
        registration_bytes, registration_object
    )
    source, source_identity = _source_freeze_from_bytes(
        later_source_freeze_bytes, later_source_freeze_object
    )
    salary, salary_identity = _salary_diagnostic_from_bytes(
        salary_diagnostic_bytes,
        salary_diagnostic_object,
        registration=registration,
    )
    registered_at, _, _ = _source_query_projection(
        source, registration=registration
    )
    salary_created = _timestamp(
        salary["query"]["query_receipt"]["created"],
        label="salary diagnostic query receipt.created",
    )[1]
    if registered_at > salary_created:
        raise CorpusArtifactSourceAuthorityError(
            "salary query precedes its registration"
        )

    reserved_uris = {
        registration_identity["uri"], source_identity["uri"],
        salary_identity["uri"],
    }
    if len(reserved_uris) != 3:
        raise CorpusArtifactSourceAuthorityError(
            "registration/source/diagnostic object URIs overlap"
        )
    seen_artifact_uris: set[str] = set()
    tasks: list[dict[str, object]] = []
    receipt_manifest: list[dict[str, object]] = []
    validation_manifest: list[dict[str, object]] = []
    artifact_ordinal = 0

    source_slates = _sequence(source["slates"], label="later-source slates")
    salary_slates = _sequence(salary["slates"], label="salary slates")
    for task_index, (raw_source_slate, raw_salary_slate, expected_key) in enumerate(
        zip(
            source_slates,
            salary_slates,
            later.EXPECTED_SLATE_KEYS,
            strict=True,
        )
    ):
        source_slate = _mapping(
            raw_source_slate, label=f"later-source slate[{task_index}]"
        )
        salary_slate = _mapping(
            raw_salary_slate, label=f"salary slate[{task_index}]"
        )
        season, week = expected_key
        if (
            (source_slate["season"], source_slate["week"])
            != expected_key
            or source_slate["slate_id"] != f"{season}-w{week:02d}"
            or salary_slate["task_index"] != task_index
            or (salary_slate["season"], salary_slate["week"])
            != expected_key
        ):
            raise CorpusArtifactSourceAuthorityError(
                f"task[{task_index}] source/salary identity differs"
            )
        catalog_rows = _sequence(
            source_slate["catalog"], label=f"task[{task_index}] catalog"
        )
        catalog_ids = tuple(
            _string(
                _mapping(row, label="catalog player")["id"],
                label="catalog player id",
            )
            for row in catalog_rows
        )
        if catalog_ids != tuple(sorted(set(catalog_ids))):
            raise CorpusArtifactSourceAuthorityError(
                f"task[{task_index}] catalog player order differs"
            )
        salary_ids = tuple(salary_slate["salary_player_ids"])
        coverage = _salary_coverage(catalog_ids, salary_ids)

        source_artifacts = _sequence(
            source_slate["artifact_receipts"],
            label=f"task[{task_index}] artifact receipts",
        )
        if len(source_artifacts) != len(TASK_WORLD_SOURCE_ROLES):
            raise CorpusArtifactSourceAuthorityError(
                f"task[{task_index}] artifact role count differs"
            )
        task_receipts: dict[str, object] = {}
        task_validations: dict[str, object] = {}
        for block, role, raw_source_receipt in zip(
            rw.WORLD_BLOCKS,
            TASK_WORLD_SOURCE_ROLES,
            source_artifacts,
            strict=True,
        ):
            try:
                record = next(artifact_bodies)
            except StopIteration as exc:
                raise CorpusArtifactSourceAuthorityError(
                    f"artifact stream ended before ordinal {artifact_ordinal}"
                ) from exc
            if type(record) is not RetainedArtifactBody:
                raise CorpusArtifactSourceAuthorityError(
                    f"artifact[{artifact_ordinal}] record type differs"
                )
            source_receipt = _mapping(
                raw_source_receipt,
                label=f"task[{task_index}] {role} source receipt",
            )
            expected_identity = _artifact_identity_from_source(
                source_receipt,
                label=f"task[{task_index}] {role} object",
            )
            reopened_identity = _object_identity(
                record.identity,
                label=f"artifact[{artifact_ordinal}] reopened object",
            )
            if (
                type(record.task_index) is not int
                or record.task_index != task_index
                or type(record.role) is not str
                or record.role != role
                or source_receipt.get("block") != block
                or reopened_identity != expected_identity
            ):
                raise CorpusArtifactSourceAuthorityError(
                    f"artifact[{artifact_ordinal}] role/order/identity differs"
                )
            uri = str(expected_identity["uri"])
            if uri in reserved_uris or uri in seen_artifact_uris:
                raise CorpusArtifactSourceAuthorityError(
                    f"artifact[{artifact_ordinal}] URI overlaps/repeats"
                )
            seen_artifact_uris.add(uri)
            _bind_raw_object(
                record.raw,
                reopened_identity,
                label=f"artifact[{artifact_ordinal}]",
            )
            try:
                loaded = later.load_artifact_worlds(source_receipt, record.raw)
            except later.LR8LaterSourceError as exc:
                raise CorpusArtifactSourceAuthorityError(
                    f"artifact[{artifact_ordinal}] NPZ validation failed"
                ) from exc
            sorted_ids = tuple(sorted(loaded.player_ids))
            if loaded.block != block or sorted_ids != catalog_ids:
                raise CorpusArtifactSourceAuthorityError(
                    f"artifact[{artifact_ordinal}] player IDs differ from catalog"
                )
            validation = {
                "artifact_ordinal": artifact_ordinal,
                "role": role,
                "object": expected_identity,
                "candidate_rows": _exact_int(
                    source_receipt.get("candidate_rows"),
                    label=f"artifact[{artifact_ordinal}].candidate_rows",
                    minimum=1,
                ),
                "player_count": len(loaded.player_ids),
                "ordered_player_ids_sha256": canonical_sha256(
                    list(loaded.player_ids)
                ),
                "player_set_sha256": canonical_sha256(list(sorted_ids)),
                "npz_fields": sorted(later.NPZ_FIELDS),
                "player_draws_dtype": "float32",
                "player_draws_shape": [
                    len(loaded.player_ids), rw.WORLDS_PER_BLOCK,
                ],
                "world_count": rw.WORLDS_PER_BLOCK,
                "player_set_matches_catalog": True,
                "uses_realized_outcomes": False,
            }
            task_receipts[role] = expected_identity
            task_validations[role] = validation
            receipt_manifest.append({
                "artifact_ordinal": artifact_ordinal,
                "task_index": task_index,
                "role": role,
                "object": expected_identity,
            })
            validation_manifest.append(validation)
            artifact_ordinal += 1
            del loaded, record

        task_body: dict[str, object] = {
            "task_index": task_index,
            "season": season,
            "week": week,
            "slate_id": source_slate["slate_id"],
            "universe_scope": UNIVERSE_SCOPE,
            "registration_sha256": registration["registration_sha256"],
            "later_source_freeze_manifest_sha256": source["freeze_sha256"],
            "salary_diagnostic_sha256": salary["diagnostic_sha256"],
            "catalog_sha256": source_slate["catalog_sha256"],
            "catalog_player_count": len(catalog_ids),
            "catalog_player_ids_sha256": canonical_sha256(list(catalog_ids)),
            "incumbent_candidates_sha256": source_slate[
                "incumbent_candidates_sha256"
            ],
            "world_artifact_receipts": task_receipts,
            "world_artifact_receipt_set_sha256": canonical_sha256(task_receipts),
            "world_artifact_validations": task_validations,
            "world_artifact_validation_set_sha256": canonical_sha256(
                task_validations
            ),
            "salary_coverage": coverage,
            "complete_dk_salary_universe_claimed": False,
        }
        tasks.append(_task_hash(task_body))

    exhausted = object()
    extra = next(artifact_bodies, exhausted)
    if extra is not exhausted:
        raise CorpusArtifactSourceAuthorityError(
            "artifact stream contains entries after exact 270 coverage"
        )
    if (
        artifact_ordinal != EXPECTED_ARTIFACT_COUNT
        or len(seen_artifact_uris) != EXPECTED_ARTIFACT_COUNT
        or len(tasks) != EXPECTED_TASK_COUNT
    ):
        raise CorpusArtifactSourceAuthorityError(
            "artifact stream coverage differs"
        )

    exact_match_tasks = sum(
        task["salary_coverage"]["artifact_equals_salary_diagnostic"] is True
        for task in tasks
    )
    artifact_player_slates = sum(
        int(task["salary_coverage"]["artifact_supported_player_count"])
        for task in tasks
    )
    salary_player_slates = sum(
        int(task["salary_coverage"]["salary_player_count"])
        for task in tasks
    )
    salary_only_player_slates = sum(
        int(task["salary_coverage"]["salary_only_player_count"])
        for task in tasks
    )
    coverage_summary = {
        "task_count": EXPECTED_TASK_COUNT,
        "exact_match_task_count": exact_match_tasks,
        "artifact_player_slate_count": artifact_player_slates,
        "salary_player_slate_count": salary_player_slates,
        "salary_only_player_slate_count": salary_only_player_slates,
        "coverage_numerator_artifact_player_slates": artifact_player_slates,
        "coverage_denominator_salary_player_slates": salary_player_slates,
        "diagnostic_required": True,
        "diagnostic_grants_world_draws": False,
        "coverage_is_predeclared_query_relative": True,
        "query_result_independently_verified": False,
        "complete_dk_salary_coverage_claimed": False,
    }
    body: dict[str, object] = {
        "schema": COMPLETION_SCHEMA,
        "authority_scope": UNIVERSE_SCOPE,
        "registration_object": registration_identity,
        "registration_sha256": registration["registration_sha256"],
        "later_source_freeze_object": source_identity,
        "later_source_freeze_manifest_sha256": source["freeze_sha256"],
        "salary_diagnostic_object": salary_identity,
        "salary_diagnostic_sha256": salary["diagnostic_sha256"],
        "task_count": EXPECTED_TASK_COUNT,
        "world_blocks": list(rw.WORLD_BLOCKS),
        "worlds_per_block": rw.WORLDS_PER_BLOCK,
        "artifact_count": EXPECTED_ARTIFACT_COUNT,
        "artifact_stream_order": "task-index-major_then-r0-r1-r2-r3-r4",
        "artifact_receipt_manifest_sha256": canonical_sha256(receipt_manifest),
        "artifact_validation_manifest_sha256": canonical_sha256(
            validation_manifest
        ),
        "tasks": tasks,
        "task_manifest_sha256": canonical_sha256(tasks),
        "salary_coverage_summary": coverage_summary,
        "artifact_supported_universe_complete": True,
        "complete_dk_salary_universe_claimed": False,
        "salary_coverage_is_predeclared_query_relative": True,
        "salary_query_result_independently_verified": False,
        "complete_dk_salary_coverage_claimed": False,
        "salary_only_players_have_world_draws": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "live_strategy_authority": False,
    }
    body["completion_sha256"] = canonical_sha256(body)
    raw = canonical_json_bytes(body)
    validate_completion_bytes(raw)
    return raw


def _validate_artifact_validation(
    value: object, *, expected_ordinal: int, expected_role: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label="artifact validation"))
    _exact_keys(item, _ARTIFACT_VALIDATION_KEYS, label="artifact validation")
    ordinal = _exact_int(
        item["artifact_ordinal"], label="artifact validation ordinal"
    )
    candidate_rows = _exact_int(
        item["candidate_rows"],
        label="artifact validation candidate rows",
        minimum=1,
    )
    player_count = _exact_int(
        item["player_count"],
        label="artifact validation player count",
        minimum=1,
    )
    if (
        ordinal != expected_ordinal
        or type(item["role"]) is not str
        or item["role"] != expected_role
        or item["npz_fields"] != sorted(later.NPZ_FIELDS)
        or item["player_draws_dtype"] != "float32"
        or item["player_draws_shape"]
        != [player_count, rw.WORLDS_PER_BLOCK]
        or item["world_count"] != rw.WORLDS_PER_BLOCK
        or item["player_set_matches_catalog"] is not True
        or item["uses_realized_outcomes"] is not False
    ):
        raise CorpusArtifactSourceAuthorityError(
            "artifact validation identity differs"
        )
    item["object"] = _object_identity(
        item["object"], label="artifact validation.object"
    )
    _sha(item["ordered_player_ids_sha256"], label="ordered player ID hash")
    _sha(item["player_set_sha256"], label="player-set hash")
    return item


def validate_completion_bytes(raw: bytes) -> dict[str, object]:
    """Strictly validate a canonical source-authority completion receipt."""
    item = _self_hashed(
        _parse_canonical_json(raw, label="source authority completion"),
        label="source authority completion",
        hash_field="completion_sha256",
    )
    _exact_keys(item, _COMPLETION_KEYS, label="source authority completion")
    if (
        item["schema"] != COMPLETION_SCHEMA
        or item["authority_scope"] != UNIVERSE_SCOPE
        or item["task_count"] != EXPECTED_TASK_COUNT
        or item["world_blocks"] != list(rw.WORLD_BLOCKS)
        or item["worlds_per_block"] != rw.WORLDS_PER_BLOCK
        or item["artifact_count"] != EXPECTED_ARTIFACT_COUNT
        or item["artifact_stream_order"]
        != "task-index-major_then-r0-r1-r2-r3-r4"
        or item["artifact_supported_universe_complete"] is not True
        or item["complete_dk_salary_universe_claimed"] is not False
        or item["salary_coverage_is_predeclared_query_relative"] is not True
        or item["salary_query_result_independently_verified"] is not False
        or item["complete_dk_salary_coverage_claimed"] is not False
        or item["salary_only_players_have_world_draws"] is not False
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
        or item["historical_scoring_licensed"] is not False
        or item["production_change_licensed"] is not False
        or item["live_strategy_authority"] is not False
    ):
        raise CorpusArtifactSourceAuthorityError(
            "source authority completion identity/license differs"
        )
    registration_identity = _object_identity(
        item["registration_object"], label="completion registration object"
    )
    source_identity = _object_identity(
        item["later_source_freeze_object"], label="completion source object"
    )
    salary_identity = _object_identity(
        item["salary_diagnostic_object"], label="completion salary object"
    )
    if len({
        registration_identity["uri"], source_identity["uri"],
        salary_identity["uri"],
    }) != 3:
        raise CorpusArtifactSourceAuthorityError(
            "completion common object URIs overlap"
        )
    _sha(item["registration_sha256"], label="completion registration SHA")
    source_internal = _sha(
        item["later_source_freeze_manifest_sha256"],
        label="completion later-source manifest SHA",
    )
    salary_internal = _sha(
        item["salary_diagnostic_sha256"],
        label="completion salary diagnostic SHA",
    )
    if (
        item["registration_sha256"] == registration_identity["sha256"]
        or source_internal == source_identity["sha256"]
        or salary_internal == salary_identity["sha256"]
    ):
        raise CorpusArtifactSourceAuthorityError(
            "completion object/internal hashes are conflated"
        )
    tasks_raw = _sequence(item["tasks"], label="completion tasks")
    if len(tasks_raw) != EXPECTED_TASK_COUNT:
        raise CorpusArtifactSourceAuthorityError(
            "completion task coverage differs"
        )
    normalized_tasks: list[dict[str, object]] = []
    receipt_manifest: list[dict[str, object]] = []
    validation_manifest: list[dict[str, object]] = []
    seen_uris = {
        str(registration_identity["uri"]), str(source_identity["uri"]),
        str(salary_identity["uri"]),
    }
    expected_ordinal = 0
    for task_index, (raw_task, key) in enumerate(
        zip(tasks_raw, later.EXPECTED_SLATE_KEYS, strict=True)
    ):
        task = dict(_mapping(raw_task, label=f"completion task[{task_index}]"))
        _exact_keys(task, _TASK_KEYS, label=f"completion task[{task_index}]")
        retained_task_sha = _sha(
            task["task_source_authority_sha256"],
            label=f"completion task[{task_index}] SHA",
        )
        task_body = {
            name: task[name]
            for name in task if name != "task_source_authority_sha256"
        }
        coverage = _mapping(
            task["salary_coverage"],
            label=f"completion task[{task_index}] salary coverage",
        )
        _exact_keys(
            coverage,
            _SALARY_COVERAGE_KEYS,
            label=f"completion task[{task_index}] salary coverage",
        )
        count_fields = (
            "salary_player_count", "artifact_supported_player_count",
            "artifact_supported_in_salary_count", "salary_only_player_count",
            "artifact_only_player_count",
        )
        if any(type(coverage[field]) is not int or coverage[field] < 0 for field in count_fields):
            raise CorpusArtifactSourceAuthorityError(
                f"completion task[{task_index}] salary counts differ"
            )
        if (
            type(task["task_index"]) is not int
            or task["task_index"] != task_index
            or type(task["season"]) is not int
            or type(task["week"]) is not int
            or (task["season"], task["week"]) != key
            or task["slate_id"] != f"{key[0]}-w{key[1]:02d}"
            or task["universe_scope"] != UNIVERSE_SCOPE
            or task["registration_sha256"] != item["registration_sha256"]
            or task["later_source_freeze_manifest_sha256"]
            != source_internal
            or task["salary_diagnostic_sha256"] != salary_internal
            or type(task["catalog_player_count"]) is not int
            or task["catalog_player_count"] < 1
            or coverage["artifact_supported_player_count"]
            != task["catalog_player_count"]
            or coverage["artifact_supported_in_salary_count"]
            != task["catalog_player_count"]
            or coverage["artifact_supported_player_ids_sha256"]
            != task["catalog_player_ids_sha256"]
            or coverage["salary_player_count"]
            != coverage["artifact_supported_in_salary_count"]
            + coverage["salary_only_player_count"]
            or coverage["artifact_only_player_count"] != 0
            or coverage["artifact_only_player_ids_sha256"]
            != canonical_sha256([])
            or coverage["artifact_equals_salary_diagnostic"]
            is not (coverage["salary_only_player_count"] == 0)
            or coverage["salary_only_players_have_world_draws"] is not False
            or coverage["coverage_is_predeclared_query_relative"] is not True
            or coverage["query_result_independently_verified"] is not False
            or coverage["complete_dk_salary_coverage_claimed"] is not False
            or task["complete_dk_salary_universe_claimed"] is not False
            or retained_task_sha != canonical_sha256(task_body)
        ):
            raise CorpusArtifactSourceAuthorityError(
                f"completion task[{task_index}] identity differs"
            )
        for hash_name in (
            "registration_sha256", "later_source_freeze_manifest_sha256",
            "salary_diagnostic_sha256",
            "catalog_sha256", "catalog_player_ids_sha256",
            "incumbent_candidates_sha256", "world_artifact_receipt_set_sha256",
            "world_artifact_validation_set_sha256",
        ):
            _sha(task[hash_name], label=f"completion task[{task_index}] {hash_name}")
        for hash_name in (
            "salary_player_ids_sha256", "artifact_supported_player_ids_sha256",
            "salary_only_player_ids_sha256", "artifact_only_player_ids_sha256",
        ):
            _sha(coverage[hash_name], label=f"completion coverage {hash_name}")
        receipts = _mapping(
            task["world_artifact_receipts"],
            label=f"completion task[{task_index}] receipts",
        )
        validations = _mapping(
            task["world_artifact_validations"],
            label=f"completion task[{task_index}] validations",
        )
        _exact_keys(
            receipts,
            frozenset(TASK_WORLD_SOURCE_ROLES),
            label=f"completion task[{task_index}] receipts",
        )
        _exact_keys(
            validations,
            frozenset(TASK_WORLD_SOURCE_ROLES),
            label=f"completion task[{task_index}] validations",
        )
        normalized_receipts: dict[str, object] = {}
        normalized_validations: dict[str, object] = {}
        for role in TASK_WORLD_SOURCE_ROLES:
            receipt = _object_identity(
                receipts[role],
                label=f"completion task[{task_index}] {role} object",
            )
            if receipt["uri"] in seen_uris:
                raise CorpusArtifactSourceAuthorityError(
                    "completion artifact URI overlaps/repeats"
                )
            seen_uris.add(str(receipt["uri"]))
            validation = _validate_artifact_validation(
                validations[role],
                expected_ordinal=expected_ordinal,
                expected_role=role,
            )
            if validation["object"] != receipt or (
                validation["player_set_sha256"]
                != task["catalog_player_ids_sha256"]
            ):
                raise CorpusArtifactSourceAuthorityError(
                    "completion artifact validation/task binding differs"
                )
            normalized_receipts[role] = receipt
            normalized_validations[role] = validation
            receipt_manifest.append({
                "artifact_ordinal": expected_ordinal,
                "task_index": task_index,
                "role": role,
                "object": receipt,
            })
            validation_manifest.append(validation)
            expected_ordinal += 1
        if (
            task["world_artifact_receipt_set_sha256"]
            != canonical_sha256(normalized_receipts)
            or task["world_artifact_validation_set_sha256"]
            != canonical_sha256(normalized_validations)
        ):
            raise CorpusArtifactSourceAuthorityError(
                f"completion task[{task_index}] artifact-set hash differs"
            )
        normalized_tasks.append(task)
    if expected_ordinal != EXPECTED_ARTIFACT_COUNT:
        raise CorpusArtifactSourceAuthorityError(
            "completion artifact coverage differs"
        )
    summary = _mapping(
        item["salary_coverage_summary"], label="completion coverage summary"
    )
    _exact_keys(summary, _COVERAGE_SUMMARY_KEYS, label="completion coverage summary")
    expected_summary = {
        "task_count": EXPECTED_TASK_COUNT,
        "exact_match_task_count": sum(
            task["salary_coverage"]["artifact_equals_salary_diagnostic"] is True
            for task in normalized_tasks
        ),
        "artifact_player_slate_count": sum(
            task["salary_coverage"]["artifact_supported_player_count"]
            for task in normalized_tasks
        ),
        "salary_player_slate_count": sum(
            task["salary_coverage"]["salary_player_count"]
            for task in normalized_tasks
        ),
        "salary_only_player_slate_count": sum(
            task["salary_coverage"]["salary_only_player_count"]
            for task in normalized_tasks
        ),
        "coverage_numerator_artifact_player_slates": sum(
            task["salary_coverage"]["artifact_supported_player_count"]
            for task in normalized_tasks
        ),
        "coverage_denominator_salary_player_slates": sum(
            task["salary_coverage"]["salary_player_count"]
            for task in normalized_tasks
        ),
        "diagnostic_required": True,
        "diagnostic_grants_world_draws": False,
        "coverage_is_predeclared_query_relative": True,
        "query_result_independently_verified": False,
        "complete_dk_salary_coverage_claimed": False,
    }
    if (
        dict(summary) != expected_summary
        or item["artifact_receipt_manifest_sha256"]
        != canonical_sha256(receipt_manifest)
        or item["artifact_validation_manifest_sha256"]
        != canonical_sha256(validation_manifest)
        or item["task_manifest_sha256"] != canonical_sha256(normalized_tasks)
    ):
        raise CorpusArtifactSourceAuthorityError(
            "completion coverage/manifest hash differs"
        )
    return dict(item)


__all__ = [
    "COMPLETION_SCHEMA",
    "CorpusArtifactSourceAuthorityError",
    "EXPECTED_ARTIFACT_COUNT",
    "EXPECTED_TASK_COUNT",
    "REGISTRATION_SCHEMA",
    "RetainedArtifactBody",
    "SALARY_DIAGNOSTIC_SCHEMA",
    "SALARY_DIAGNOSTIC_SCOPE",
    "UNIVERSE_SCOPE",
    "canonical_json_bytes",
    "canonical_sha256",
    "validate_completion_bytes",
    "validate_registration",
    "verify_artifact_supported_source_authority",
]
