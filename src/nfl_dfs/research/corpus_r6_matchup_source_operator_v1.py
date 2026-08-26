"""Bounded operator for one corrected, outcome-blind R6 matchup source.

The semantic source contract lives in :mod:`corpus_r6_matchup_source_v1`.
This module prepares a future production publication edge while keeping
authority outside the caller-authored input bundle:

* ``validate-only`` performs a complete semantic replay in memory but grants
  no trusted mechanical authority;
* ``execute`` is unconditionally unavailable until a pinned frozen 54-entry
  authority catalog is implemented and integrated; no external carrier or
  caller input currently unblocks it;
* private fixture machinery describes the intended per-slate binding of the
  accepted-v12 reconstruction, task and ordinals, bundle/catalog/source,
  family/code, and fixed environment identities, but grants no authority; and
* all external objects are read at URI/generation/SHA-256/byte identity and
  all publications are create-once and exact-reopened.

The operator never queries a warehouse, derives source rows, reads outcomes,
lists objects, mutates a graph, or promotes a strategy. A future frozen
54-entry R6 source catalog must become the sole source of the expected
per-slate authority identity before execute can be enabled.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from hashlib import sha256
import json
import re
from typing import Final, Protocol, runtime_checkable

from nfl_dfs.research import corpus_r6_matchup_source_v1 as source


INPUT_BUNDLE_SCHEMA: Final = "corpus-r6-matchup-source-operator-input/v1"
CODE_IDENTITY_SCHEMA: Final = "corpus-r6-matchup-source-code-identity/v1"
_CAPTURE_AUTHORITY_SCHEMA: Final = "corpus-r6-matchup-capture-authority/v1"
RESULT_RECEIPT_SCHEMA: Final = "corpus-r6-matchup-source-operator-result/v1"
VALIDATE_ONLY_MODE: Final = "validate-only"
EXECUTE_MODE: Final = "execute"

MAX_INPUT_BUNDLE_BYTES: Final = 64 * 1024 * 1024
MAX_CAPTURE_AUTHORITY_BYTES: Final = 8 * 1024 * 1024
MAX_PLAYER_CATALOG_BYTES: Final = 8 * 1024 * 1024
MAX_EXTERNAL_OBJECT_BYTES: Final = 128 * 1024 * 1024
MAX_RENDERED_SQL_BYTES: Final = 1024 * 1024
MAX_CODE_IDENTITY_BYTES: Final = 128 * 1024
MAX_OUTPUT_PREFIX_BYTES: Final = 1024
MAX_URI_BYTES: Final = 2048
MAX_GENERATION_DIGITS: Final = 20
MAX_COMPONENT_EXTRACTS: Final = 64
MAX_COMPONENT_ROWS_PER_EXTRACT: Final = 100_000
MAX_TOTAL_COMPONENT_ROWS: Final = 500_000
MAX_ANNOTATION_ROWS: Final = 10_000
MAX_CATALOG_PLAYERS: Final = 10_000
MAX_FAMILY_SOURCE_ROLES: Final = 64
MAX_TREE_DEPTH: Final = 32
MAX_OBJECT_FIELDS: Final = 256
MAX_ARRAY_ITEMS: Final = 500_000
MAX_STRING_BYTES: Final = 2 * 1024 * 1024
MAX_PUBLISHED_BYTES: Final = 128 * 1024 * 1024

_FALSE_AUTHORITY_FIELDS: Final = (
    "outcome_authority",
    "scoring_authority",
    "graph_authority",
    "fill_authority",
    "retrieval_authority",
    "promotion_authority",
    "production_authority",
    "production_policy_authority",
)
_CODE_ARTIFACT_ROLES: Final = (
    "family-definition-producer",
    "matchup-source-contract",
    "matchup-source-operator",
    "source-extract-producer",
)
_INPUT_FIELDS: Final = frozenset({
    "schema_version",
    "accepted_v12_reconstruction_identity",
    "task_binding",
    "slate",
    "lock_time_utc",
    "player_catalog_identity",
    "player_catalog_raw",
    "rendered_sql",
    "query_job_receipt",
    "component_extracts",
    "annotation_rows",
    "family_definition_identities",
    "code_identity",
    "output_prefix",
    "outcome_columns_read",
    "uses_realized_outcomes",
    "capture_mechanics_authority",
    *_FALSE_AUTHORITY_FIELDS,
    "input_bundle_sha256",
})
_TASK_BINDING_FIELDS: Final = frozenset({
    "season",
    "week",
    "slate_id",
    "task_id",
    "task_ordinal",
    "source_task_ordinal",
})
_CODE_ARTIFACT_FIELDS: Final = frozenset({
    "role", "path", "sha256", "bytes",
})
_CODE_IDENTITY_FIELDS: Final = frozenset({
    "schema_version",
    "repository_commit",
    "artifacts",
    "family_definition_registry_sha256",
    "outcome_columns_read",
    "uses_realized_outcomes",
    "code_identity_sha256",
})
_SOURCE_REGISTRATION_FIELDS: Final = frozenset({
    "role",
    "relation_or_object",
    "source_role_schema_sha256",
    "etag_or_generation",
    "exact_extract_sha256",
    "row_count",
})
_ALLOWED_ENVIRONMENT_FIELDS: Final = frozenset({
    "project", "bucket", "output_prefix",
})
_CAPTURE_AUTHORITY_FIELDS: Final = frozenset({
    "schema_version",
    "authority_scope",
    "accepted_v12_reconstruction_identity",
    "task_binding",
    "input_bundle_identity",
    "player_catalog_identity",
    "player_catalog_source_authority_identity",
    "registered_sources",
    "registered_source_set_sha256",
    "query_job_sha256",
    "family_definition_identities",
    "family_definition_registry_sha256",
    "code_identity",
    "allowed_environment",
    "capture_mechanics_authority",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
    "capture_authority_sha256",
})
_RESULT_FIELDS: Final = frozenset({
    "schema_version",
    "mode",
    "input_bundle_schema_version",
    "input_bundle_sha256",
    "input_bundle_identity",
    "accepted_v12_reconstruction_identity",
    "task_binding",
    "slate",
    "output_prefix",
    "player_catalog_identity",
    "player_catalog_source_authority_identity",
    "capture_authority_identity",
    "capture_authority_sha256",
    "registered_source_set_sha256",
    "query_job_sha256",
    "family_definition_registry_sha256",
    "code_identity_sha256",
    "rendered_sql_sha256",
    "storage_scope",
    "published",
    "source_export_identity",
    "query_receipt_identity",
    "source_export_preview",
    "query_receipt_preview",
    "capture_authority_exact_reopen_validated",
    "input_bundle_exact_reopen_validated",
    "accepted_v12_reconstruction_exact_reopen_validated",
    "catalog_exact_reopen_validated",
    "catalog_source_authority_exact_reopen_validated",
    "semantic_capture_replay_validated",
    "capture_mechanics_authority",
    "outcome_columns_read",
    "uses_realized_outcomes",
    *_FALSE_AUTHORITY_FIELDS,
    "operator_result_sha256",
})
_PREVIEW_FIELDS: Final = frozenset({"uri", "sha256", "bytes"})
_SHA: Final = re.compile(r"^[0-9a-f]{64}$")
_COMMIT: Final = re.compile(r"^[0-9a-f]{40}$")
_NAME: Final = re.compile(r"^[a-z][a-z0-9_-]{0,127}$")
_SAFE_PATH: Final = re.compile(r"^[A-Za-z0-9_.\-/]{1,512}$")
_PROJECT: Final = re.compile(r"^[a-z][a-z0-9_-]{3,62}$")
_BUCKET: Final = re.compile(r"^[a-z0-9][a-z0-9._-]{1,61}[a-z0-9]$")
_BQ_RELATION: Final = re.compile(
    r"^bq://([A-Za-z0-9_-]+)\.([A-Za-z_][A-Za-z0-9_]*)\."
    r"([A-Za-z_][A-Za-z0-9_]*)$"
)


class CorpusR6MatchupSourceOperatorV1Error(RuntimeError):
    """The bounded matchup-source operator failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupSourceOperatorV1Error(message)


@runtime_checkable
class CreateOncePublisher(Protocol):
    def publish_create_once(
        self, uri: str, raw: bytes,
    ) -> Mapping[str, object]: ...


@runtime_checkable
class ExactReader(Protocol):
    def read_exact(self, identity: Mapping[str, object]) -> bytes: ...


@runtime_checkable
class ExactObjectStore(CreateOncePublisher, ExactReader, Protocol):
    """Future exact storage seam; current execute admits no storage caller."""


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_fields(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} fields differ")


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _bounded_string(
    value: object, *, label: str, maximum_bytes: int = MAX_STRING_BYTES,
) -> str:
    if (
        type(value) is not str
        or not value
        or len(value.encode("utf-8")) > maximum_bytes
    ):
        _fail(f"{label} must be one bounded nonempty string")
    return value


def _canonical_copy(value: object, *, label: str) -> object:
    try:
        raw = source.canonical_json_bytes(value)
        return json.loads(raw.decode("utf-8"))
    except (source.CorpusR6MatchupSourceV1Error, json.JSONDecodeError) as exc:
        raise CorpusR6MatchupSourceOperatorV1Error(
            f"{label} is not canonical JSON"
        ) from exc


def _canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        parsed = json.loads(raw.decode("utf-8"))
        body = dict(_mapping(parsed, label=label))
        canonical = source.canonical_json_bytes(body)
    except (
        UnicodeDecodeError,
        json.JSONDecodeError,
        ValueError,
        OverflowError,
        MemoryError,
        RecursionError,
        source.CorpusR6MatchupSourceV1Error,
    ) as exc:
        raise CorpusR6MatchupSourceOperatorV1Error(
            f"{label} is not canonical JSON"
        ) from exc
    if raw != canonical:
        _fail(f"{label} bytes are not the canonical representation")
    return body


def _tree_bounds(value: object, *, label: str, depth: int = 0) -> None:
    """Apply parser ceilings without assigning semantics by denylist."""
    if depth > MAX_TREE_DEPTH:
        _fail(f"{label} exceeds the nesting bound")
    if isinstance(value, Mapping):
        if len(value) > MAX_OBJECT_FIELDS:
            _fail(f"{label} exceeds the object-field bound")
        for key, nested in value.items():
            if type(key) is not str:
                _fail(f"{label} has a non-string field")
            if len(key.encode("utf-8")) > 256:
                _fail(f"{label} has an overlong field")
            _tree_bounds(nested, label=f"{label}.{key}", depth=depth + 1)
        return
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        if len(value) > MAX_ARRAY_ITEMS:
            _fail(f"{label} exceeds the array bound")
        for offset, nested in enumerate(value):
            _tree_bounds(nested, label=f"{label}[{offset}]", depth=depth + 1)
        return
    if type(value) is str and len(value.encode("utf-8")) > MAX_STRING_BYTES:
        _fail(f"{label} exceeds the string bound")


def _require_false_policy(value: Mapping[str, object], *, label: str) -> None:
    if (
        value.get("outcome_columns_read") != []
        or value.get("uses_realized_outcomes") is not False
        or any(value.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS)
    ):
        _fail(f"{label} outcome/authority policy differs")


def _positive_generation(value: object, *, label: str) -> str:
    try:
        if type(value) is int:
            if value <= 0:
                _fail(f"{label} must be one positive generation")
            text = str(value)
        elif type(value) is str:
            text = value
        else:
            _fail(f"{label} must be one positive generation")
    except (ValueError, OverflowError) as exc:
        raise CorpusR6MatchupSourceOperatorV1Error(
            f"{label} must be one bounded positive generation"
        ) from exc
    if (
        not text.isdigit()
        or text.startswith("0")
        or len(text) > MAX_GENERATION_DIGITS
    ):
        _fail(f"{label} must be one bounded positive generation")
    return text


def _gcs_parts(uri: object) -> tuple[str, str]:
    text = _bounded_string(uri, label="GCS URI", maximum_bytes=MAX_URI_BYTES)
    if (
        not text.startswith("gs://")
        or "?" in text
        or "#" in text
        or "/" not in text[5:]
    ):
        _fail("GCS URI differs")
    bucket, name = text[5:].split("/", 1)
    if (
        _BUCKET.fullmatch(bucket) is None
        or not name
        or name.startswith("/")
        or name.endswith("/")
        or any(part in {"", ".", ".."} for part in name.split("/"))
    ):
        _fail("GCS URI differs")
    return bucket, name


def _normalize_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} identity fields differ")
    uri = _bounded_string(
        item["uri"], label=f"{label} URI", maximum_bytes=MAX_URI_BYTES
    )
    _gcs_parts(uri)
    size = item["bytes"]
    if (
        type(size) is not int
        or isinstance(size, bool)
        or not 0 < size <= MAX_EXTERNAL_OBJECT_BYTES
    ):
        _fail(f"{label} byte size differs")
    return {
        "uri": uri,
        "generation": _positive_generation(
            item["generation"], label=f"{label} generation"
        ),
        "sha256": _digest(item["sha256"], label=f"{label} SHA-256"),
        "bytes": size,
    }


def parse_external_identity_v1(
    raw: bytes, *, label: str = "external object identity",
) -> dict[str, object]:
    """Parse one canonical, bounded local identity carrier."""
    if type(raw) is not bytes or not raw or len(raw) > 4096:
        _fail(f"{label} file is empty or exceeds the byte bound")
    return _normalize_identity(_canonical_object(raw, label=label), label=label)


def _bind_raw(raw: bytes, identity: Mapping[str, object], *, label: str) -> None:
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} content identity differs")


def _normalize_output_prefix(value: object) -> str:
    prefix = _bounded_string(
        value, label="output prefix", maximum_bytes=MAX_OUTPUT_PREFIX_BYTES
    )
    if prefix.endswith("/"):
        _fail("output prefix must not have a trailing slash")
    _gcs_parts(f"{prefix}/authority-probe.json")
    return prefix


def _normalize_project(value: object, *, label: str) -> str:
    project = _bounded_string(value, label=label, maximum_bytes=63)
    if _PROJECT.fullmatch(project) is None:
        _fail(f"{label} differs")
    return project


def _exact_nonnegative_int(
    value: object, *, label: str, maximum: int,
) -> int:
    if (
        type(value) is not int
        or isinstance(value, bool)
        or not 0 <= value <= maximum
    ):
        _fail(f"{label} differs")
    return value


def _normalize_slate(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"season", "week", "slate_id", "task_id"}:
        _fail(f"{label} fields differ")
    season = item["season"]
    week = item["week"]
    if (
        type(season) is not int
        or isinstance(season, bool)
        or not 2000 <= season <= 2100
        or type(week) is not int
        or isinstance(week, bool)
        or not 1 <= week <= 18
    ):
        _fail(f"{label} season/week differ")
    slate_id = _bounded_string(
        item["slate_id"], label=f"{label} slate_id", maximum_bytes=128
    )
    task_id = _bounded_string(
        item["task_id"], label=f"{label} task_id", maximum_bytes=128
    )
    if task_id != f"slate-{season}-w{week}":
        _fail(f"{label} task_id is not canonical")
    return {
        "season": season,
        "week": week,
        "slate_id": slate_id,
        "task_id": task_id,
    }


def _normalize_task_binding(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_fields(item, _TASK_BINDING_FIELDS, label=label)
    slate = _normalize_slate(
        {key: item[key] for key in ("season", "week", "slate_id", "task_id")},
        label=f"{label} slate",
    )
    return {
        **slate,
        "task_ordinal": _exact_nonnegative_int(
            item["task_ordinal"], label=f"{label} task ordinal", maximum=53
        ),
        "source_task_ordinal": _exact_nonnegative_int(
            item["source_task_ordinal"],
            label=f"{label} source task ordinal",
            maximum=53,
        ),
    }


def build_code_identity_v1(
    *,
    repository_commit: str,
    artifacts: Sequence[Mapping[str, object]],
    family_definition_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Build the strict positive code identity transported by the bundle."""
    body: dict[str, object] = {
        "schema_version": CODE_IDENTITY_SCHEMA,
        "repository_commit": repository_commit,
        "artifacts": _canonical_copy(artifacts, label="code artifacts"),
        "family_definition_registry_sha256": source.canonical_sha256(
            family_definition_identities
        ),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    body["code_identity_sha256"] = source.canonical_sha256(body)
    return validate_code_identity_v1(
        body, family_definition_identities=family_definition_identities
    )


def validate_code_identity_v1(
    value: object,
    *,
    family_definition_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    body = dict(_mapping(value, label="code identity"))
    _exact_fields(body, _CODE_IDENTITY_FIELDS, label="code identity")
    if (
        body["schema_version"] != CODE_IDENTITY_SCHEMA
        or type(body["repository_commit"]) is not str
        or _COMMIT.fullmatch(str(body["repository_commit"])) is None
    ):
        _fail("code identity schema/commit differs")
    if (
        body["outcome_columns_read"] != []
        or body["uses_realized_outcomes"] is not False
    ):
        _fail("code identity outcome policy differs")
    raw_artifacts = _sequence(body["artifacts"], label="code artifacts")
    artifacts: list[dict[str, object]] = []
    for offset, raw_artifact in enumerate(raw_artifacts):
        artifact = _mapping(raw_artifact, label=f"code artifact[{offset}]")
        _exact_fields(
            artifact, _CODE_ARTIFACT_FIELDS, label=f"code artifact[{offset}]"
        )
        role = _bounded_string(
            artifact["role"],
            label=f"code artifact[{offset}] role",
            maximum_bytes=128,
        )
        path = _bounded_string(
            artifact["path"],
            label=f"code artifact[{offset}] path",
            maximum_bytes=512,
        )
        size = artifact["bytes"]
        if (
            _NAME.fullmatch(role) is None
            or _SAFE_PATH.fullmatch(path) is None
            or path.startswith("/")
            or ".." in path.split("/")
            or not path.endswith(".py")
            or type(size) is not int
            or isinstance(size, bool)
            or not 0 < size <= 16 * 1024 * 1024
        ):
            _fail(f"code artifact[{offset}] values differ")
        artifacts.append({
            "role": role,
            "path": path,
            "sha256": _digest(
                artifact["sha256"], label=f"code artifact[{offset}] SHA-256"
            ),
            "bytes": size,
        })
    if [item["role"] for item in artifacts] != list(_CODE_ARTIFACT_ROLES):
        _fail("code artifact role coverage/order differs")
    expected_family_sha = source.canonical_sha256(family_definition_identities)
    if body["family_definition_registry_sha256"] != expected_family_sha:
        _fail("code identity family registry differs")
    retained = _digest(
        body["code_identity_sha256"], label="code identity self-hash"
    )
    unhashed = {
        key: nested for key, nested in body.items()
        if key != "code_identity_sha256"
    }
    if source.canonical_sha256(unhashed) != retained:
        _fail("code identity self-hash differs")
    body["artifacts"] = artifacts
    return deepcopy(body)


def _count_bundle_rows(body: Mapping[str, object]) -> None:
    catalog = _mapping(body["player_catalog_raw"], label="player catalog raw")
    players = _sequence(catalog.get("players"), label="player catalog players")
    if len(players) > MAX_CATALOG_PLAYERS:
        _fail("player catalog exceeds the player-count bound")
    extracts = _sequence(body["component_extracts"], label="component extracts")
    if not extracts or len(extracts) > MAX_COMPONENT_EXTRACTS:
        _fail("component extract count differs or exceeds the bound")
    total_rows = 0
    for offset, raw_extract in enumerate(extracts):
        extract = _mapping(raw_extract, label=f"component extract[{offset}]")
        rows = _sequence(
            extract.get("rows"), label=f"component extract[{offset}] rows"
        )
        if len(rows) > MAX_COMPONENT_ROWS_PER_EXTRACT:
            _fail(f"component extract[{offset}] exceeds its row bound")
        total_rows += len(rows)
    if total_rows > MAX_TOTAL_COMPONENT_ROWS:
        _fail("component extracts exceed the total row bound")
    if len(_sequence(body["annotation_rows"], label="annotation rows")) > MAX_ANNOTATION_ROWS:
        _fail("annotation rows exceed the row-count bound")
    families = _mapping(
        body["family_definition_identities"], label="family definitions"
    )
    role_count = 0
    for family, raw_definition in families.items():
        definition = _mapping(raw_definition, label=f"{family} family definition")
        role_count += len(_sequence(
            definition.get("source_roles"), label=f"{family} family source roles"
        ))
    if role_count > MAX_FAMILY_SOURCE_ROLES:
        _fail("family definitions exceed the source-role bound")


def _catalog_source_authority_identity(
    catalog: Mapping[str, object], *, expected_task_id: str,
) -> dict[str, object]:
    if (
        set(catalog) != {
            "schema_version", "task_id", "source_authority", "players",
            "player_catalog_sha256",
        }
        or catalog.get("schema_version") != source.PLAYER_CATALOG_SCHEMA
        or catalog.get("task_id") != expected_task_id
    ):
        _fail("player catalog schema/task differs")
    retained = _digest(
        catalog.get("player_catalog_sha256"), label="player catalog self-hash"
    )
    unhashed = {
        key: value for key, value in catalog.items()
        if key != "player_catalog_sha256"
    }
    if source.canonical_sha256(unhashed) != retained:
        _fail("player catalog self-hash differs")
    return _normalize_identity(
        catalog["source_authority"], label="player catalog source authority"
    )


def parse_input_bundle_v1(raw: bytes) -> dict[str, object]:
    """Parse the strict bounded transport bundle without granting authority."""
    if type(raw) is not bytes or not raw or len(raw) > MAX_INPUT_BUNDLE_BYTES:
        _fail("input bundle is empty or exceeds the byte bound")
    body = _canonical_object(raw, label="input bundle")
    _exact_fields(body, _INPUT_FIELDS, label="input bundle")
    if body["schema_version"] != INPUT_BUNDLE_SCHEMA:
        _fail("input bundle schema differs")
    _require_false_policy(body, label="input bundle")
    if body["capture_mechanics_authority"] is not False:
        _fail("input bundle cannot grant capture mechanics authority")
    retained = _digest(body["input_bundle_sha256"], label="input bundle self-hash")
    unhashed = {
        key: value for key, value in body.items()
        if key != "input_bundle_sha256"
    }
    if source.canonical_sha256(unhashed) != retained:
        _fail("input bundle self-hash differs")
    _tree_bounds(body, label="input bundle")
    _count_bundle_rows(body)

    slate = _normalize_slate(body["slate"], label="input bundle slate")
    task_binding = _normalize_task_binding(
        body["task_binding"], label="input task binding"
    )
    if {key: task_binding[key] for key in slate} != slate:
        _fail("input task binding differs from its slate")
    accepted_identity = _normalize_identity(
        body["accepted_v12_reconstruction_identity"],
        label="accepted-v12 reconstruction",
    )
    catalog_identity = _normalize_identity(
        body["player_catalog_identity"], label="player catalog identity"
    )
    catalog_raw = source.canonical_json_bytes(body["player_catalog_raw"])
    if len(catalog_raw) > MAX_PLAYER_CATALOG_BYTES:
        _fail("player catalog exceeds the byte bound")
    _bind_raw(catalog_raw, catalog_identity, label="player catalog raw")
    _catalog_source_authority_identity(
        _mapping(body["player_catalog_raw"], label="player catalog raw"),
        expected_task_id=str(slate["task_id"]),
    )
    rendered_sql = _bounded_string(
        body["rendered_sql"],
        label="rendered SQL",
        maximum_bytes=MAX_RENDERED_SQL_BYTES,
    )
    families = _mapping(
        body["family_definition_identities"], label="family definitions"
    )
    code = validate_code_identity_v1(
        body["code_identity"], family_definition_identities=families
    )
    if len(source.canonical_json_bytes(code)) > MAX_CODE_IDENTITY_BYTES:
        _fail("code identity exceeds the byte bound")
    normalized = deepcopy(body)
    normalized["accepted_v12_reconstruction_identity"] = accepted_identity
    normalized["task_binding"] = task_binding
    normalized["slate"] = slate
    normalized["player_catalog_identity"] = catalog_identity
    normalized["code_identity"] = code
    normalized["rendered_sql"] = rendered_sql
    normalized["output_prefix"] = _normalize_output_prefix(body["output_prefix"])
    return normalized


def build_input_bundle_v1(
    *,
    accepted_v12_reconstruction_identity: Mapping[str, object],
    task_binding: Mapping[str, object],
    slate: Mapping[str, object],
    lock_time_utc: str,
    player_catalog_identity: Mapping[str, object],
    player_catalog_raw: Mapping[str, object],
    rendered_sql_raw: bytes,
    query_job_receipt: Mapping[str, object],
    component_extracts: Sequence[Mapping[str, object]],
    annotation_rows: Sequence[Mapping[str, object]],
    family_definition_identities: Mapping[str, Mapping[str, object]],
    code_identity: Mapping[str, object],
    output_prefix: str,
) -> dict[str, object]:
    """Build the sole canonical, explicitly non-authoritative input bundle."""
    if type(rendered_sql_raw) is not bytes:
        _fail("rendered SQL must be raw bytes")
    try:
        rendered_sql = rendered_sql_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusR6MatchupSourceOperatorV1Error(
            "rendered SQL is not UTF-8"
        ) from exc
    body: dict[str, object] = {
        "schema_version": INPUT_BUNDLE_SCHEMA,
        "accepted_v12_reconstruction_identity": _canonical_copy(
            accepted_v12_reconstruction_identity,
            label="accepted-v12 reconstruction identity",
        ),
        "task_binding": _canonical_copy(task_binding, label="task binding"),
        "slate": _canonical_copy(slate, label="slate"),
        "lock_time_utc": lock_time_utc,
        "player_catalog_identity": _canonical_copy(
            player_catalog_identity, label="player catalog identity"
        ),
        "player_catalog_raw": _canonical_copy(
            player_catalog_raw, label="player catalog raw"
        ),
        "rendered_sql": rendered_sql,
        "query_job_receipt": _canonical_copy(
            query_job_receipt, label="query job receipt"
        ),
        "component_extracts": _canonical_copy(
            component_extracts, label="component extracts"
        ),
        "annotation_rows": _canonical_copy(annotation_rows, label="annotation rows"),
        "family_definition_identities": _canonical_copy(
            family_definition_identities, label="family definitions"
        ),
        "code_identity": _canonical_copy(code_identity, label="code identity"),
        "output_prefix": output_prefix,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "capture_mechanics_authority": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["input_bundle_sha256"] = source.canonical_sha256(body)
    return parse_input_bundle_v1(source.canonical_json_bytes(body))


def _expected_roles(
    family_definition_identities: Mapping[str, object],
) -> set[str]:
    if set(family_definition_identities) != set(source.ELIGIBLE_FAMILIES):
        _fail("family definition coverage differs")
    roles = set(source.INFRASTRUCTURE_SOURCE_ROLES)
    for family in source.ELIGIBLE_FAMILIES:
        definition = _mapping(
            family_definition_identities[family],
            label=f"{family} family definition",
        )
        for raw_role in _sequence(
            definition.get("source_roles"), label=f"{family} source roles"
        ):
            role = _bounded_string(
                raw_role, label=f"{family} source role", maximum_bytes=128
            )
            if _NAME.fullmatch(role) is None or role in roles:
                _fail("family source roles are invalid or duplicated")
            roles.add(role)
    return roles


def _registered_sources_from_bundle(
    bundle: Mapping[str, object],
) -> list[dict[str, object]]:
    metadata = _mapping(bundle["query_job_receipt"], label="query job receipt")
    relations = _sequence(metadata.get("source_relations"), label="source relations")
    relation_by_role: dict[str, Mapping[str, object]] = {}
    for offset, raw_relation in enumerate(relations):
        relation = _mapping(raw_relation, label=f"source relation[{offset}]")
        expected = {
            "role",
            "table_or_object",
            "schema_sha256",
            "etag_or_generation",
            "modified_or_created_at_utc",
            "exact_extract_sha256",
            "row_count",
        }
        if set(relation) != expected:
            _fail(f"source relation[{offset}] fields differ")
        role = _bounded_string(
            relation["role"],
            label=f"source relation[{offset}] role",
            maximum_bytes=128,
        )
        if _NAME.fullmatch(role) is None or role in relation_by_role:
            _fail("source relation role coverage differs")
        relation_by_role[role] = relation
    extract_by_role: dict[str, Mapping[str, object]] = {}
    for offset, raw_extract in enumerate(
        _sequence(bundle["component_extracts"], label="component extracts")
    ):
        extract = _mapping(raw_extract, label=f"component extract[{offset}]")
        role = _bounded_string(
            extract.get("role"),
            label=f"component extract[{offset}] role",
            maximum_bytes=128,
        )
        if role in extract_by_role:
            _fail("component extract role coverage differs")
        extract_by_role[role] = extract
    expected_roles = _expected_roles(
        _mapping(bundle["family_definition_identities"], label="family definitions")
    )
    if set(relation_by_role) != expected_roles or set(extract_by_role) != expected_roles:
        _fail("registered source role coverage differs")
    registered: list[dict[str, object]] = []
    for role in sorted(expected_roles):
        relation = relation_by_role[role]
        extract = extract_by_role[role]
        table = _bounded_string(
            relation["table_or_object"], label=f"{role} relation", maximum_bytes=512
        )
        if _BQ_RELATION.fullmatch(table) is None:
            _fail(f"{role} relation must be one exact BigQuery relation")
        schema_sha = _digest(
            relation["schema_sha256"], label=f"{role} relation schema"
        )
        extract_sha = _digest(
            relation["exact_extract_sha256"], label=f"{role} exact extract"
        )
        etag = _bounded_string(
            relation["etag_or_generation"],
            label=f"{role} etag/generation",
            maximum_bytes=256,
        )
        row_count = relation["row_count"]
        if (
            type(row_count) is not int
            or isinstance(row_count, bool)
            or not 0 <= row_count <= MAX_COMPONENT_ROWS_PER_EXTRACT
            or extract.get("relation_or_object") != table
            or extract.get("source_role_schema_sha256") != schema_sha
            or extract.get("source_identity_or_extract_sha256") != extract_sha
            or extract.get("rows_sha256") != extract_sha
            or extract.get("row_count") != row_count
        ):
            _fail(f"{role} registered source does not bind its exact extract")
        registered.append({
            "role": role,
            "relation_or_object": table,
            "source_role_schema_sha256": schema_sha,
            "etag_or_generation": etag,
            "exact_extract_sha256": extract_sha,
            "row_count": row_count,
        })
    return registered


def _query_job_sha256(bundle: Mapping[str, object]) -> str:
    metadata = _mapping(bundle["query_job_receipt"], label="query job receipt")
    query_job = _mapping(metadata.get("query_job"), label="query job")
    return source.canonical_sha256(query_job)


def _build_capture_authority_fixture_v1(
    *,
    input_bundle: Mapping[str, object],
    input_bundle_identity: Mapping[str, object],
    allowed_project: str,
    allowed_bucket: str,
    allowed_output_prefix: str,
) -> dict[str, object]:
    """Build a carrier for external review and immutable publication.

    This helper is intentionally never called by execute. Content becomes
    authority only after a future source catalog publishes it immutably and
    supplies its exact object identity to this operator.
    """
    bundle_raw = source.canonical_json_bytes(input_bundle)
    bundle = parse_input_bundle_v1(bundle_raw)
    bundle_identity = _normalize_identity(input_bundle_identity, label="input bundle")
    _bind_raw(bundle_raw, bundle_identity, label="input bundle")
    slate = _mapping(bundle["slate"], label="bundle slate")
    catalog = _mapping(bundle["player_catalog_raw"], label="player catalog raw")
    source_authority_identity = _catalog_source_authority_identity(
        catalog, expected_task_id=str(slate["task_id"])
    )
    registered = _registered_sources_from_bundle(bundle)
    families = _mapping(
        bundle["family_definition_identities"], label="family definitions"
    )
    code = validate_code_identity_v1(
        bundle["code_identity"], family_definition_identities=families
    )
    body: dict[str, object] = {
        "schema_version": _CAPTURE_AUTHORITY_SCHEMA,
        "authority_scope": "one-corrected-r6-matchup-source-capture",
        "accepted_v12_reconstruction_identity": deepcopy(
            bundle["accepted_v12_reconstruction_identity"]
        ),
        "task_binding": deepcopy(bundle["task_binding"]),
        "input_bundle_identity": bundle_identity,
        "player_catalog_identity": deepcopy(bundle["player_catalog_identity"]),
        "player_catalog_source_authority_identity": source_authority_identity,
        "registered_sources": registered,
        "registered_source_set_sha256": source.canonical_sha256(registered),
        "query_job_sha256": _query_job_sha256(bundle),
        "family_definition_identities": deepcopy(families),
        "family_definition_registry_sha256": source.canonical_sha256(families),
        "code_identity": code,
        "allowed_environment": {
            "project": allowed_project,
            "bucket": allowed_bucket,
            "output_prefix": allowed_output_prefix,
        },
        "capture_mechanics_authority": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["capture_authority_sha256"] = source.canonical_sha256(body)
    return _validate_capture_authority_v1(body)


def _validate_capture_authority_v1(value: object) -> dict[str, object]:
    body = dict(_mapping(value, label="capture authority"))
    _exact_fields(body, _CAPTURE_AUTHORITY_FIELDS, label="capture authority")
    _tree_bounds(body, label="capture authority")
    if (
        body["schema_version"] != _CAPTURE_AUTHORITY_SCHEMA
        or body["authority_scope"]
        != "one-corrected-r6-matchup-source-capture"
        or body["capture_mechanics_authority"] is not True
    ):
        _fail("capture authority scope differs")
    _require_false_policy(body, label="capture authority")
    body["accepted_v12_reconstruction_identity"] = _normalize_identity(
        body["accepted_v12_reconstruction_identity"],
        label="authority accepted-v12 reconstruction",
    )
    body["task_binding"] = _normalize_task_binding(
        body["task_binding"], label="authority task binding"
    )
    body["input_bundle_identity"] = _normalize_identity(
        body["input_bundle_identity"], label="authority input bundle"
    )
    body["player_catalog_identity"] = _normalize_identity(
        body["player_catalog_identity"], label="authority player catalog"
    )
    body["player_catalog_source_authority_identity"] = _normalize_identity(
        body["player_catalog_source_authority_identity"],
        label="authority catalog source authority",
    )
    registered: list[dict[str, object]] = []
    for offset, raw_registration in enumerate(
        _sequence(body["registered_sources"], label="authority registered sources")
    ):
        registration = _mapping(
            raw_registration, label=f"authority source[{offset}]"
        )
        _exact_fields(
            registration,
            _SOURCE_REGISTRATION_FIELDS,
            label=f"authority source[{offset}]",
        )
        role = _bounded_string(
            registration["role"],
            label=f"authority source[{offset}] role",
            maximum_bytes=128,
        )
        relation = _bounded_string(
            registration["relation_or_object"],
            label=f"authority source[{offset}] relation",
            maximum_bytes=512,
        )
        etag = _bounded_string(
            registration["etag_or_generation"],
            label=f"authority source[{offset}] etag/generation",
            maximum_bytes=256,
        )
        row_count = registration["row_count"]
        if (
            _NAME.fullmatch(role) is None
            or _BQ_RELATION.fullmatch(relation) is None
            or type(row_count) is not int
            or isinstance(row_count, bool)
            or not 0 <= row_count <= MAX_COMPONENT_ROWS_PER_EXTRACT
        ):
            _fail(f"authority source[{offset}] values differ")
        registered.append({
            "role": role,
            "relation_or_object": relation,
            "source_role_schema_sha256": _digest(
                registration["source_role_schema_sha256"],
                label=f"authority source[{offset}] schema",
            ),
            "etag_or_generation": etag,
            "exact_extract_sha256": _digest(
                registration["exact_extract_sha256"],
                label=f"authority source[{offset}] extract",
            ),
            "row_count": row_count,
        })
    roles = [str(item["role"]) for item in registered]
    if (
        not registered
        or roles != sorted(roles)
        or len(roles) != len(set(roles))
    ):
        _fail("authority registered source order/uniqueness differs")
    if body["registered_source_set_sha256"] != source.canonical_sha256(registered):
        _fail("authority registered source set hash differs")
    body["registered_sources"] = registered
    _digest(body["query_job_sha256"], label="authority query job SHA-256")
    families = _mapping(
        body["family_definition_identities"], label="authority family definitions"
    )
    _expected_roles(families)
    if (
        body["family_definition_registry_sha256"]
        != source.canonical_sha256(families)
    ):
        _fail("authority family registry differs")
    body["code_identity"] = validate_code_identity_v1(
        body["code_identity"], family_definition_identities=families
    )
    environment = _mapping(
        body["allowed_environment"], label="allowed environment"
    )
    _exact_fields(
        environment, _ALLOWED_ENVIRONMENT_FIELDS, label="allowed environment"
    )
    project = _normalize_project(environment["project"], label="allowed project")
    bucket = _bounded_string(
        environment["bucket"], label="allowed bucket", maximum_bytes=63
    )
    if _BUCKET.fullmatch(bucket) is None:
        _fail("allowed bucket differs")
    output_prefix = _normalize_output_prefix(environment["output_prefix"])
    if _gcs_parts(f"{output_prefix}/authority-probe.json")[0] != bucket:
        _fail("allowed output prefix differs from allowed bucket")
    body["allowed_environment"] = {
        "project": project,
        "bucket": bucket,
        "output_prefix": output_prefix,
    }
    retained = _digest(
        body["capture_authority_sha256"], label="capture authority self-hash"
    )
    unhashed = {
        key: nested for key, nested in body.items()
        if key != "capture_authority_sha256"
    }
    if source.canonical_sha256(unhashed) != retained:
        _fail("capture authority self-hash differs")
    return deepcopy(body)


class MemoryExactObjectStore:
    """Deterministic exact store for local validation and focused tests."""

    def __init__(self) -> None:
        self._objects: dict[str, tuple[dict[str, object], bytes]] = {}
        self._next_generation = 1_000_000

    def seed_exact(
        self, identity: Mapping[str, object], raw: bytes,
    ) -> dict[str, object]:
        normalized = _normalize_identity(identity, label="seed identity")
        _bind_raw(raw, normalized, label="seed object")
        uri = str(normalized["uri"])
        if uri in self._objects:
            _fail("seed URI already exists")
        self._objects[uri] = (deepcopy(normalized), raw)
        return deepcopy(normalized)

    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw or len(raw) > MAX_PUBLISHED_BYTES:
            _fail("create-once payload is empty or exceeds the byte bound")
        _gcs_parts(uri)
        if uri in self._objects:
            _fail("create-once URI already exists")
        identity = {
            "uri": uri,
            "generation": str(self._next_generation),
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }
        self._next_generation += 1
        self._objects[uri] = (deepcopy(identity), raw)
        return deepcopy(identity)

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        normalized = _normalize_identity(identity, label="exact-read identity")
        retained = self._objects.get(str(normalized["uri"]))
        if retained is None or retained[0] != normalized:
            _fail("exact-read identity/generation differs")
        _bind_raw(retained[1], normalized, label="exact-read object")
        return retained[1]


class GenerationPinnedGCSStore:
    """GCS create-once writes and generation-pinned exact reads only."""

    def __init__(self, client: object):
        if client is None:
            _fail("GCS client is required")
        self._client = client

    def read_exact(self, identity: Mapping[str, object]) -> bytes:
        normalized = _normalize_identity(identity, label="GCS exact-read identity")
        bucket_name, object_name = _gcs_parts(normalized["uri"])
        generation = int(str(normalized["generation"]))
        try:
            blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                object_name, generation=generation
            )
            blob.reload(if_generation_match=generation)
            metadata_size = getattr(blob, "size", None)
            if (
                type(metadata_size) is not int
                or isinstance(metadata_size, bool)
                or metadata_size != normalized["bytes"]
                or not 0 < metadata_size <= MAX_EXTERNAL_OBJECT_BYTES
            ):
                _fail("generation-pinned GCS metadata size differs")
            # Request at most the expected bytes plus one inclusive range byte.
            # Exact generation metadata already fixes object size; the bounded
            # range prevents an adapter/server defect from requesting an
            # unbounded response before content validation.
            raw = blob.download_as_bytes(
                if_generation_match=generation,
                start=0,
                end=metadata_size,
            )
        except Exception as exc:
            raise CorpusR6MatchupSourceOperatorV1Error(
                "generation-pinned GCS read failed"
            ) from exc
        reopened_generation = _positive_generation(
            getattr(blob, "generation", None), label="reopened GCS generation"
        )
        if reopened_generation != normalized["generation"]:
            _fail("generation-pinned GCS generation differs")
        _bind_raw(raw, normalized, label="generation-pinned GCS object")
        return raw

    def publish_create_once(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw or len(raw) > MAX_PUBLISHED_BYTES:
            _fail("GCS create-once payload is empty or exceeds the byte bound")
        bucket_name, object_name = _gcs_parts(uri)
        try:
            upload_blob = self._client.bucket(bucket_name).blob(  # type: ignore[attr-defined]
                object_name
            )
            upload_blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
        except Exception as exc:
            raise CorpusR6MatchupSourceOperatorV1Error(
                "create-once GCS publication failed"
            ) from exc
        generation = _positive_generation(
            getattr(upload_blob, "generation", None),
            label="created GCS generation",
        )
        identity = _normalize_identity({
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        }, label="created GCS object")
        if self.read_exact(identity) != raw:
            _fail("created GCS object did not reopen exactly")
        return identity


def _store_boundary(store: object) -> ExactObjectStore:
    if (
        store is None
        or not callable(getattr(store, "publish_create_once", None))
        or not callable(getattr(store, "read_exact", None))
    ):
        _fail("an exact-reader/create-once store is required")
    return store  # type: ignore[return-value]


def _read_store_exact(
    store: ExactReader,
    identity: Mapping[str, object],
    *,
    label: str,
    maximum_bytes: int = MAX_EXTERNAL_OBJECT_BYTES,
) -> bytes:
    normalized = _normalize_identity(identity, label=f"{label} identity")
    if int(normalized["bytes"]) > maximum_bytes:
        _fail(f"{label} exceeds the byte bound")
    try:
        raw = store.read_exact(normalized)
    except CorpusR6MatchupSourceOperatorV1Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupSourceOperatorV1Error(
            f"{label} exact read failed"
        ) from exc
    _bind_raw(raw, normalized, label=label)
    return raw


def _authorize_execute(
    *,
    input_bundle_raw: bytes,
    bundle: Mapping[str, object],
    capture_authority_identity: Mapping[str, object],
    execution_project: str,
    store: ExactObjectStore,
) -> dict[str, object]:
    """Exact-open the external carrier and every prepublication authority."""
    project = _normalize_project(execution_project, label="execution project")
    authority_identity = _normalize_identity(
        capture_authority_identity, label="expected capture authority"
    )
    authority_raw = _read_store_exact(
        store,
        authority_identity,
        label="capture authority",
        maximum_bytes=MAX_CAPTURE_AUTHORITY_BYTES,
    )
    authority = _validate_capture_authority_v1(
        _canonical_object(authority_raw, label="capture authority")
    )
    environment = _mapping(
        authority["allowed_environment"], label="allowed environment"
    )
    if project != environment["project"]:
        _fail("execution project differs from capture authority")

    bundle_identity = _normalize_identity(
        authority["input_bundle_identity"], label="authority input bundle"
    )
    _bind_raw(input_bundle_raw, bundle_identity, label="local input bundle")
    exact_bundle_raw = _read_store_exact(
        store,
        bundle_identity,
        label="immutable input bundle",
        maximum_bytes=MAX_INPUT_BUNDLE_BYTES,
    )
    if exact_bundle_raw != input_bundle_raw:
        _fail("local input bundle differs from immutable authority bundle")
    if authority["task_binding"] != bundle["task_binding"]:
        _fail("capture authority task/ordinal binding differs")

    accepted_identity = _normalize_identity(
        bundle["accepted_v12_reconstruction_identity"],
        label="bundle accepted-v12 reconstruction",
    )
    if accepted_identity != authority["accepted_v12_reconstruction_identity"]:
        _fail("capture authority accepted-v12 reconstruction differs")
    _read_store_exact(
        store,
        accepted_identity,
        label="accepted-v12 reconstruction",
        maximum_bytes=MAX_EXTERNAL_OBJECT_BYTES,
    )

    catalog_identity = _normalize_identity(
        bundle["player_catalog_identity"], label="bundle player catalog"
    )
    if catalog_identity != authority["player_catalog_identity"]:
        _fail("capture authority player catalog differs")
    catalog_raw = source.canonical_json_bytes(bundle["player_catalog_raw"])
    exact_catalog_raw = _read_store_exact(
        store,
        catalog_identity,
        label="player catalog",
        maximum_bytes=MAX_PLAYER_CATALOG_BYTES,
    )
    if exact_catalog_raw != catalog_raw:
        _fail("bundle player catalog differs from exact authority catalog")
    catalog_body = _canonical_object(exact_catalog_raw, label="player catalog")
    slate = _mapping(bundle["slate"], label="bundle slate")
    catalog_source_identity = _catalog_source_authority_identity(
        catalog_body, expected_task_id=str(slate["task_id"])
    )
    if (
        catalog_source_identity
        != authority["player_catalog_source_authority_identity"]
    ):
        _fail("capture authority catalog source authority differs")
    _read_store_exact(
        store,
        catalog_source_identity,
        label="player catalog source authority",
        maximum_bytes=MAX_CAPTURE_AUTHORITY_BYTES,
    )

    registered = _registered_sources_from_bundle(bundle)
    if (
        registered != authority["registered_sources"]
        or source.canonical_sha256(registered)
        != authority["registered_source_set_sha256"]
    ):
        _fail("capture authority registered source identities differ")
    query_job_sha = _query_job_sha256(bundle)
    if query_job_sha != authority["query_job_sha256"]:
        _fail("capture authority query job identity differs")
    families = _mapping(
        bundle["family_definition_identities"], label="bundle family definitions"
    )
    if (
        dict(families) != authority["family_definition_identities"]
        or source.canonical_sha256(families)
        != authority["family_definition_registry_sha256"]
    ):
        _fail("capture authority family identities differ")
    code = validate_code_identity_v1(
        bundle["code_identity"], family_definition_identities=families
    )
    if code != authority["code_identity"]:
        _fail("capture authority code identity differs")
    if bundle["output_prefix"] != environment["output_prefix"]:
        _fail("bundle output prefix differs from capture authority")
    output_bucket, _ = _gcs_parts(
        f"{bundle['output_prefix']}/authority-probe.json"
    )
    if output_bucket != environment["bucket"]:
        _fail("bundle output bucket differs from capture authority")
    metadata = _mapping(bundle["query_job_receipt"], label="query job receipt")
    query_job = _mapping(metadata.get("query_job"), label="query job")
    if query_job.get("project") != project:
        _fail("query job project differs from capture authority")
    for registration in registered:
        match = _BQ_RELATION.fullmatch(str(registration["relation_or_object"]))
        if match is None or match.group(1) != project:
            _fail("registered relation project differs from capture authority")
    return {
        "authority": authority,
        "authority_identity": authority_identity,
        "bundle_identity": bundle_identity,
        "accepted_identity": accepted_identity,
        "catalog_source_identity": catalog_source_identity,
    }


def _capture(
    *, bundle: Mapping[str, object], active_store: ExactObjectStore,
) -> dict[str, Mapping[str, object]]:
    catalog_identity = _normalize_identity(
        bundle["player_catalog_identity"], label="player catalog identity"
    )
    catalog_raw = source.canonical_json_bytes(bundle["player_catalog_raw"])
    try:
        return source.capture_matchup_source_v1(
            slate=_mapping(bundle["slate"], label="bundle slate"),
            lock_time_utc=str(bundle["lock_time_utc"]),
            player_catalog_identity=catalog_identity,
            player_catalog_raw=catalog_raw,
            rendered_sql_raw=str(bundle["rendered_sql"]).encode("utf-8"),
            query_job_receipt=_mapping(
                bundle["query_job_receipt"], label="query job receipt"
            ),
            component_extracts=[
                _mapping(item, label="component extract")
                for item in _sequence(
                    bundle["component_extracts"], label="component extracts"
                )
            ],
            annotation_rows=[
                _mapping(item, label="annotation row")
                for item in _sequence(
                    bundle["annotation_rows"], label="annotation rows"
                )
            ],
            family_definition_identities=_mapping(
                bundle["family_definition_identities"],
                label="family definitions",
            ),
            code_identity=_mapping(bundle["code_identity"], label="code identity"),
            publish_create_once=active_store.publish_create_once,
            read_exact=active_store.read_exact,
            output_prefix=str(bundle["output_prefix"]),
        )
    except source.CorpusR6MatchupSourceV1Error as exc:
        raise CorpusR6MatchupSourceOperatorV1Error(str(exc)) from exc


def _memory_capture(
    bundle: Mapping[str, object],
) -> tuple[dict[str, Mapping[str, object]], MemoryExactObjectStore]:
    store = MemoryExactObjectStore()
    catalog_identity = _normalize_identity(
        bundle["player_catalog_identity"], label="player catalog identity"
    )
    store.seed_exact(
        catalog_identity, source.canonical_json_bytes(bundle["player_catalog_raw"])
    )
    return _capture(bundle=bundle, active_store=store), store


def _preview(identity: Mapping[str, object]) -> dict[str, object]:
    normalized = _normalize_identity(identity, label="artifact identity")
    return {
        "uri": normalized["uri"],
        "sha256": normalized["sha256"],
        "bytes": normalized["bytes"],
    }


def _build_result_receipt(
    *,
    bundle: Mapping[str, object],
    mode: str,
    source_export_identity: Mapping[str, object],
    query_receipt_identity: Mapping[str, object],
    authorization: Mapping[str, object] | None,
) -> dict[str, object]:
    executing = mode == EXECUTE_MODE
    export_identity = _normalize_identity(
        source_export_identity, label="source export identity"
    )
    receipt_identity = _normalize_identity(
        query_receipt_identity, label="query receipt identity"
    )
    catalog = _mapping(bundle["player_catalog_raw"], label="player catalog raw")
    slate = _mapping(bundle["slate"], label="bundle slate")
    catalog_source_identity = _catalog_source_authority_identity(
        catalog, expected_task_id=str(slate["task_id"])
    )
    registered = _registered_sources_from_bundle(bundle)
    code = _mapping(bundle["code_identity"], label="code identity")
    authority = (
        _mapping(authorization["authority"], label="capture authority")
        if authorization is not None
        else None
    )
    body: dict[str, object] = {
        "schema_version": RESULT_RECEIPT_SCHEMA,
        "mode": mode,
        "input_bundle_schema_version": INPUT_BUNDLE_SCHEMA,
        "input_bundle_sha256": bundle["input_bundle_sha256"],
        "input_bundle_identity": (
            deepcopy(authorization["bundle_identity"]) if executing else None
        ),
        "accepted_v12_reconstruction_identity": deepcopy(
            bundle["accepted_v12_reconstruction_identity"]
        ),
        "task_binding": deepcopy(bundle["task_binding"]),
        "slate": deepcopy(bundle["slate"]),
        "output_prefix": bundle["output_prefix"],
        "player_catalog_identity": deepcopy(bundle["player_catalog_identity"]),
        "player_catalog_source_authority_identity": catalog_source_identity,
        "capture_authority_identity": (
            deepcopy(authorization["authority_identity"]) if executing else None
        ),
        "capture_authority_sha256": (
            authority["capture_authority_sha256"] if authority is not None else None
        ),
        "registered_source_set_sha256": source.canonical_sha256(registered),
        "query_job_sha256": _query_job_sha256(bundle),
        "family_definition_registry_sha256": source.canonical_sha256(
            bundle["family_definition_identities"]
        ),
        "code_identity_sha256": code["code_identity_sha256"],
        "rendered_sql_sha256": sha256(
            str(bundle["rendered_sql"]).encode("utf-8")
        ).hexdigest(),
        "storage_scope": (
            "provided-exact-store" if executing else "ephemeral-memory"
        ),
        "published": executing,
        "source_export_identity": export_identity if executing else None,
        "query_receipt_identity": receipt_identity if executing else None,
        "source_export_preview": _preview(export_identity),
        "query_receipt_preview": _preview(receipt_identity),
        "capture_authority_exact_reopen_validated": executing,
        "input_bundle_exact_reopen_validated": executing,
        "accepted_v12_reconstruction_exact_reopen_validated": executing,
        "catalog_exact_reopen_validated": executing,
        "catalog_source_authority_exact_reopen_validated": executing,
        "semantic_capture_replay_validated": True,
        "capture_mechanics_authority": executing,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in _FALSE_AUTHORITY_FIELDS},
    }
    body["operator_result_sha256"] = source.canonical_sha256(body)
    return validate_operator_result_receipt_v1(body)


def validate_operator_result_receipt_v1(
    value: Mapping[str, object],
) -> dict[str, object]:
    body = dict(_mapping(value, label="operator result receipt"))
    _exact_fields(body, _RESULT_FIELDS, label="operator result receipt")
    mode = body["mode"]
    if (
        body["schema_version"] != RESULT_RECEIPT_SCHEMA
        or type(mode) is not str
        or mode not in {VALIDATE_ONLY_MODE, EXECUTE_MODE}
        or body["input_bundle_schema_version"] != INPUT_BUNDLE_SCHEMA
        or body["semantic_capture_replay_validated"] is not True
    ):
        _fail("operator result policy differs")
    if mode == EXECUTE_MODE:
        _fail("frozen 54-entry authority catalog unavailable")
    _require_false_policy(body, label="operator result")
    for field in (
        "input_bundle_sha256",
        "registered_source_set_sha256",
        "query_job_sha256",
        "family_definition_registry_sha256",
        "code_identity_sha256",
        "rendered_sql_sha256",
    ):
        _digest(body[field], label=f"operator result {field}")
    task_binding = _normalize_task_binding(
        body["task_binding"], label="result task binding"
    )
    slate = _normalize_slate(body["slate"], label="result slate")
    if {key: task_binding[key] for key in slate} != slate:
        _fail("result task binding differs from slate")
    _normalize_output_prefix(body["output_prefix"])
    _normalize_identity(
        body["accepted_v12_reconstruction_identity"],
        label="result accepted-v12 reconstruction",
    )
    _normalize_identity(
        body["player_catalog_identity"], label="result player catalog"
    )
    _normalize_identity(
        body["player_catalog_source_authority_identity"],
        label="result catalog source authority",
    )
    previews: dict[str, Mapping[str, object]] = {}
    for label, raw_preview in (
        ("source export", body["source_export_preview"]),
        ("query receipt", body["query_receipt_preview"]),
    ):
        preview = _mapping(raw_preview, label=f"{label} preview")
        _exact_fields(preview, _PREVIEW_FIELDS, label=f"{label} preview")
        _gcs_parts(preview["uri"])
        _digest(preview["sha256"], label=f"{label} preview SHA-256")
        size = preview["bytes"]
        if type(size) is not int or isinstance(size, bool) or size <= 0:
            _fail(f"{label} preview values differ")
        previews[label] = preview
    if (
        previews["source export"]["uri"]
        != f"{body['output_prefix']}/matchup-source-export.json"
        or previews["query receipt"]["uri"]
        != f"{body['output_prefix']}/matchup-query-receipt.json"
    ):
        _fail("operator result artifact URIs differ from output prefix")
    exact_flags = (
        "capture_authority_exact_reopen_validated",
        "input_bundle_exact_reopen_validated",
        "accepted_v12_reconstruction_exact_reopen_validated",
        "catalog_exact_reopen_validated",
        "catalog_source_authority_exact_reopen_validated",
    )
    if mode == EXECUTE_MODE:
        if (
            body["published"] is not True
            or body["storage_scope"] != "provided-exact-store"
            or body["capture_mechanics_authority"] is not True
            or any(body[field] is not True for field in exact_flags)
        ):
            _fail("executing result authority/publication scope differs")
        _normalize_identity(body["input_bundle_identity"], label="result input bundle")
        _normalize_identity(
            body["capture_authority_identity"], label="result capture authority"
        )
        _digest(
            body["capture_authority_sha256"],
            label="result capture authority SHA-256",
        )
        export = _normalize_identity(
            body["source_export_identity"], label="result source export"
        )
        receipt = _normalize_identity(
            body["query_receipt_identity"], label="result query receipt"
        )
        if _preview(export) != body["source_export_preview"]:
            _fail("source export preview differs from identity")
        if _preview(receipt) != body["query_receipt_preview"]:
            _fail("query receipt preview differs from identity")
    else:
        if (
            body["published"] is not False
            or body["storage_scope"] != "ephemeral-memory"
            or body["capture_mechanics_authority"] is not False
            or any(body[field] is not False for field in exact_flags)
            or body["input_bundle_identity"] is not None
            or body["capture_authority_identity"] is not None
            or body["capture_authority_sha256"] is not None
            or body["source_export_identity"] is not None
            or body["query_receipt_identity"] is not None
        ):
            _fail("validate-only result falsely claims trusted authority")
    retained = _digest(
        body["operator_result_sha256"], label="operator result self-hash"
    )
    unhashed = {
        key: nested for key, nested in body.items()
        if key != "operator_result_sha256"
    }
    if source.canonical_sha256(unhashed) != retained:
        _fail("operator result self-hash differs")
    return deepcopy(body)


def _publish_operator_result(
    *,
    store: ExactObjectStore,
    output_prefix: str,
    receipt: Mapping[str, object],
) -> dict[str, object]:
    raw = source.canonical_json_bytes(receipt)
    uri = f"{output_prefix}/matchup-source-operator-result.json"
    try:
        identity = _normalize_identity(
            store.publish_create_once(uri, raw),
            label="published operator result",
        )
    except CorpusR6MatchupSourceOperatorV1Error:
        raise
    except Exception as exc:
        raise CorpusR6MatchupSourceOperatorV1Error(
            "operator result create-once publication failed"
        ) from exc
    if identity["uri"] != uri:
        _fail("published operator result URI differs")
    _bind_raw(raw, identity, label="published operator result")
    reopened = _read_store_exact(
        store, identity, label="reopened operator result"
    )
    if reopened != raw:
        _fail("reopened operator result bytes differ")
    validate_operator_result_receipt_v1(
        _canonical_object(reopened, label="reopened operator result")
    )
    return identity


def run_matchup_source_operator_v1(
    *,
    input_bundle_raw: bytes,
    validate_only: bool,
) -> dict[str, object]:
    """Validate locally; execute remains blocked pending the frozen catalog."""
    if type(validate_only) is not bool:
        _fail("validate_only must be boolean")
    bundle = parse_input_bundle_v1(input_bundle_raw)
    if not validate_only:
        # Only the forthcoming pinned 54-member source catalog may choose the
        # expected per-slate authority root. A caller-supplied carrier, even a
        # perfectly coherent immutable one, is deliberately insufficient.
        _fail("frozen 54-entry authority catalog unavailable")
    artifacts, active_memory_store = _memory_capture(bundle)
    authorization: dict[str, object] | None = None
    mode = VALIDATE_ONLY_MODE
    active_store: ExactObjectStore = active_memory_store

    export_identity = _normalize_identity(
        artifacts["source_export_identity"], label="captured source export"
    )
    receipt_identity = _normalize_identity(
        artifacts["query_receipt_identity"], label="captured query receipt"
    )
    _read_store_exact(
        active_store, export_identity, label="operator source export reopen"
    )
    _read_store_exact(
        active_store, receipt_identity, label="operator query receipt reopen"
    )
    result_receipt = _build_result_receipt(
        bundle=bundle,
        mode=mode,
        source_export_identity=export_identity,
        query_receipt_identity=receipt_identity,
        authorization=authorization,
    )
    result_identity: dict[str, object] | None = None
    return {
        "receipt": result_receipt,
        "operator_result_identity": result_identity,
    }


__all__ = [
    "CODE_IDENTITY_SCHEMA",
    "CorpusR6MatchupSourceOperatorV1Error",
    "EXECUTE_MODE",
    "GenerationPinnedGCSStore",
    "INPUT_BUNDLE_SCHEMA",
    "MAX_CAPTURE_AUTHORITY_BYTES",
    "MAX_GENERATION_DIGITS",
    "MAX_INPUT_BUNDLE_BYTES",
    "MemoryExactObjectStore",
    "RESULT_RECEIPT_SCHEMA",
    "VALIDATE_ONLY_MODE",
    "build_code_identity_v1",
    "build_input_bundle_v1",
    "parse_external_identity_v1",
    "parse_input_bundle_v1",
    "run_matchup_source_operator_v1",
    "validate_code_identity_v1",
    "validate_operator_result_receipt_v1",
]
