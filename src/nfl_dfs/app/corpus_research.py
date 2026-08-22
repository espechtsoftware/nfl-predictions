"""Read-only corpus research dashboard and projection contract.

The web application never writes to Neo4j and never changes an active
strategy.  A caller may either inject a :class:`ReadOnlyQueryProjectionReader`
whose runner is restricted to the catalogued read queries, or point the
default reader at a receipt-bound materialized projection.  In both cases the
same hashes, authority flags, and row counts are revalidated before data is
returned to the browser.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from hashlib import sha256
import json
import logging
import math
import os
from pathlib import Path
import re
from typing import Final, Protocol

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse, JSONResponse


log = logging.getLogger(__name__)

router = APIRouter(tags=["corpus research"])

UI_PROJECTION_SCHEMA: Final = "corpus-research-ui-projection/v1"
UI_QUERY_RECEIPT_SCHEMA: Final = "corpus-research-ui-query-receipt/v1"
SOURCE_PROJECTION_SCHEMA: Final = "corpus-strategy-registry-projection/v2"
REGISTRY_NAMESPACE: Final = "corpus-strategy-registry"
PROJECTION_PATH_ENV: Final = "CORPUS_RESEARCH_UI_PROJECTION_PATH"
MAX_PROJECTION_BYTES: Final = 32 * 1024 * 1024
MAX_QUERY_ROWS: Final = 100_000

REQUIRED_VIEW_NAMES: Final = frozenset({
    "preset-registry",
    "strategy-lineage",
    "paired-heldout-fill-retrieval-comparison",
    "active-pointer-promotion-traversal",
    "lineup-player-team-game-traversal",
    "registry-firewall-census",
})

_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_FORBIDDEN_CYPHER = re.compile(
    r"\b(?:CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL|LOAD|FOREACH|"
    r"GRANT|DENY|REVOKE|ALTER|RENAME|START|STOP|TERMINATE|USE)\b",
    re.IGNORECASE,
)
_READ_QUERY_START = re.compile(r"^\s*(?:OPTIONAL\s+)?MATCH\b", re.IGNORECASE)


class CorpusResearchProjectionError(RuntimeError):
    """A UI projection or its read-only receipt is invalid."""


@dataclass(frozen=True, slots=True)
class ReadOnlyQuery:
    """One named query permitted to feed the browser projection."""

    name: str
    cypher: str


@dataclass(frozen=True, slots=True)
class ProjectionAvailability:
    """A validated projection, or a public not-ready explanation."""

    ready: bool
    projection: dict[str, object] | None
    reason_code: str
    message: str


class CorpusResearchProjectionReader(Protocol):
    """Read-only source boundary used by the FastAPI dependency."""

    def read(self) -> ProjectionAvailability:
        """Return one validated snapshot without mutating external state."""


QueryRunner = Callable[
    [str, str, Mapping[str, object]], Sequence[Mapping[str, object]]
]


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusResearchProjectionError(
            "projection contains a non-canonical JSON value"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return sha256(_canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusResearchProjectionError(f"{label} must be an object")
    if any(not isinstance(key, str) for key in value):
        raise CorpusResearchProjectionError(f"{label} keys must be strings")
    return dict(value)


def _rows(value: object, *, label: str) -> list[dict[str, object]]:
    if not isinstance(value, list):
        raise CorpusResearchProjectionError(f"{label} must be an array")
    if len(value) > MAX_QUERY_ROWS:
        raise CorpusResearchProjectionError(f"{label} exceeds the UI row limit")
    retained = [
        _normalise_json(row, label=f"{label}[{ordinal}]")
        for ordinal, row in enumerate(value)
    ]
    if any(not isinstance(row, dict) for row in retained):
        raise CorpusResearchProjectionError(f"{label} rows must be objects")
    return retained  # type: ignore[return-value]


def _normalise_json(value: object, *, label: str) -> object:
    if value is None or type(value) in {str, bool, int}:
        return value
    if type(value) is float:
        if not math.isfinite(value):
            raise CorpusResearchProjectionError(f"{label} must be finite")
        return value
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise CorpusResearchProjectionError(f"{label} keys must be strings")
        return {
            key: _normalise_json(value[key], label=f"{label}.{key}")
            for key in sorted(value)
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            _normalise_json(item, label=f"{label}[{ordinal}]")
            for ordinal, item in enumerate(value)
        ]
    raise CorpusResearchProjectionError(f"{label} is not JSON serializable")


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str
) -> str:
    digest = value.get(field)
    if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
        raise CorpusResearchProjectionError(f"{label}.{field} differs")
    body = {key: item for key, item in value.items() if key != field}
    if _canonical_sha256(body) != digest:
        raise CorpusResearchProjectionError(f"{label} self-hash differs")
    return digest


def _require_authority_firewall(
    value: Mapping[str, object], *, label: str
) -> None:
    required = {
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
    }
    for field, expected in required.items():
        if value.get(field) is not expected:
            raise CorpusResearchProjectionError(
                f"{label}.{field} must remain {str(expected).lower()}"
            )


def _validate_source_receipt(value: object) -> dict[str, object]:
    receipt = _mapping(value, label="source projection receipt")
    if receipt.get("schema_version") != SOURCE_PROJECTION_SCHEMA:
        raise CorpusResearchProjectionError(
            "source projection receipt schema differs"
        )
    registry_id = receipt.get("registry_id")
    namespace = receipt.get("registry_namespace")
    if (
        not isinstance(registry_id, str)
        or _ID.fullmatch(registry_id) is None
        or namespace != REGISTRY_NAMESPACE
        or receipt.get("publication_mode") != "create_once"
        or receipt.get("manifest_namespace_v2_authorized") is not True
    ):
        raise CorpusResearchProjectionError(
            "source projection registry identity differs"
        )
    release = _mapping(
        receipt.get("registry_release"),
        label="source projection registry release",
    )
    if (
        set(release) != {"uri", "generation", "sha256", "bytes"}
        or not isinstance(release.get("uri"), str)
        or not release["uri"].startswith("gs://")
        or not isinstance(release.get("generation"), str)
        or not release["generation"].isdigit()
        or not isinstance(release.get("sha256"), str)
        or _SHA.fullmatch(release["sha256"]) is None
        or not isinstance(release.get("bytes"), int)
        or isinstance(release.get("bytes"), bool)
        or release["bytes"] <= 0
    ):
        raise CorpusResearchProjectionError(
            "source projection registry release identity differs"
        )
    if (
        not isinstance(receipt.get("plan_sha256"), str)
        or _SHA.fullmatch(receipt["plan_sha256"]) is None
        or not isinstance(receipt.get("registry_node_count"), int)
        or isinstance(receipt.get("registry_node_count"), bool)
        or receipt["registry_node_count"] <= 0
        or not isinstance(receipt.get("registry_relationship_count"), int)
        or isinstance(receipt.get("registry_relationship_count"), bool)
        or receipt["registry_relationship_count"] < 0
        or not isinstance(receipt.get("winner_imported"), bool)
        or not isinstance(receipt.get("winner_count"), int)
        or isinstance(receipt.get("winner_count"), bool)
        or receipt["winner_count"] < 0
    ):
        raise CorpusResearchProjectionError(
            "source projection counts or plan identity differ"
        )
    if receipt["winner_imported"] != (receipt["winner_count"] == 51):
        raise CorpusResearchProjectionError(
            "source projection winner-import binding differs"
        )
    kind_counts = _mapping(
        receipt.get("kind_counts"), label="source projection kind counts"
    )
    if (
        not kind_counts
        or any(
            not isinstance(kind, str)
            or not isinstance(count, int)
            or isinstance(count, bool)
            or count < 0
            for kind, count in kind_counts.items()
        )
        or sum(kind_counts.values()) != receipt["registry_node_count"]
    ):
        raise CorpusResearchProjectionError(
            "source projection kind counts differ"
        )
    _require_authority_firewall(receipt, label="source projection receipt")
    _self_hash(
        receipt,
        field="projection_receipt_sha256",
        label="source projection receipt",
    )
    return receipt


def _validate_query(query: ReadOnlyQuery) -> None:
    if (
        not isinstance(query.name, str)
        or not isinstance(query.cypher, str)
        or _ID.fullmatch(query.name) is None
        or _READ_QUERY_START.search(query.cypher) is None
        or ";" in query.cypher
    ):
        raise CorpusResearchProjectionError("read-only query identity differs")
    if _FORBIDDEN_CYPHER.search(query.cypher):
        raise CorpusResearchProjectionError(
            f"query {query.name} contains a graph mutation or procedure"
        )


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_read_only_projection(
    *,
    source_projection_receipt: Mapping[str, object],
    database: str,
    queries: Sequence[ReadOnlyQuery],
    query_runner: QueryRunner,
    generated_at_utc: str | None = None,
) -> dict[str, object]:
    """Run a bounded read catalog and bind every returned row to a receipt.

    The supplied runner receives only catalogued Cypher that has passed the
    mutation/procedure firewall.  Returned rows are canonicalized, sorted,
    hashed, and retained for the UI.  This function has no graph write API.
    """

    source = _validate_source_receipt(source_projection_receipt)
    if not isinstance(database, str) or _ID.fullmatch(database) is None:
        raise CorpusResearchProjectionError("Neo4j database is not canonical")
    timestamp = generated_at_utc or _utc_now()
    if not isinstance(timestamp, str) or _UTC.fullmatch(timestamp) is None:
        raise CorpusResearchProjectionError(
            "projection timestamp must be second-precision UTC"
        )

    query_list = list(queries)
    names = [query.name for query in query_list]
    if (
        not REQUIRED_VIEW_NAMES.issubset(names)
        or len(names) != len(set(names))
        or not query_list
    ):
        raise CorpusResearchProjectionError(
            "read-only query catalog is incomplete or duplicated"
        )
    for query in query_list:
        _validate_query(query)

    parameters = {
        "namespace": REGISTRY_NAMESPACE,
        "registry_id": source["registry_id"],
    }
    views: dict[str, list[dict[str, object]]] = {}
    query_results: list[dict[str, object]] = []
    total_rows = 0
    for query in query_list:
        raw_rows = query_runner(database, query.cypher, parameters)
        if not isinstance(raw_rows, Sequence) or isinstance(
            raw_rows, (str, bytes)
        ):
            raise CorpusResearchProjectionError(
                f"query {query.name} did not return rows"
            )
        rows = _rows(list(raw_rows), label=f"query {query.name}")
        rows.sort(key=_canonical_sha256)
        total_rows += len(rows)
        if total_rows > MAX_QUERY_ROWS:
            raise CorpusResearchProjectionError(
                "combined query results exceed the UI row limit"
            )
        views[query.name] = rows
        query_results.append({
            "name": query.name,
            "cypher_sha256": sha256(query.cypher.encode("utf-8")).hexdigest(),
            "row_count": len(rows),
            "rows_sha256": _canonical_sha256(rows),
        })

    query_receipt_body: dict[str, object] = {
        "schema_version": UI_QUERY_RECEIPT_SCHEMA,
        "publication_mode": "read_only_materialization",
        "registry_id": source["registry_id"],
        "database": database,
        "namespace": REGISTRY_NAMESPACE,
        "source_projection_receipt_sha256": source[
            "projection_receipt_sha256"
        ],
        "generated_at_utc": timestamp,
        "queries": query_results,
        "read_only": True,
        "graph_mutation": False,
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
    }
    query_receipt = {
        **query_receipt_body,
        "query_receipt_sha256": _canonical_sha256(query_receipt_body),
    }
    projection_body: dict[str, object] = {
        "schema_version": UI_PROJECTION_SCHEMA,
        "registry_id": source["registry_id"],
        "database": database,
        "namespace": REGISTRY_NAMESPACE,
        "generated_at_utc": timestamp,
        "source_projection_receipt": source,
        "query_receipt": query_receipt,
        "views": views,
        "read_only": True,
        "graph_mutation": False,
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
    }
    return {
        **projection_body,
        "projection_sha256": _canonical_sha256(projection_body),
    }


def validate_read_only_projection(value: object) -> dict[str, object]:
    """Validate a materialized browser projection and all row hashes."""

    projection = _mapping(value, label="UI projection")
    expected_keys = {
        "schema_version", "registry_id", "database", "namespace",
        "generated_at_utc", "source_projection_receipt", "query_receipt",
        "views", "read_only", "graph_mutation", "automatic_promotion",
        "application_config_mutation", "production_policy_authority",
        "projection_sha256",
    }
    if set(projection) != expected_keys:
        raise CorpusResearchProjectionError("UI projection fields differ")
    if projection["schema_version"] != UI_PROJECTION_SCHEMA:
        raise CorpusResearchProjectionError("UI projection schema differs")
    if (
        not isinstance(projection["registry_id"], str)
        or _ID.fullmatch(projection["registry_id"]) is None
        or not isinstance(projection["database"], str)
        or _ID.fullmatch(projection["database"]) is None
        or projection["namespace"] != REGISTRY_NAMESPACE
        or not isinstance(projection["generated_at_utc"], str)
        or _UTC.fullmatch(projection["generated_at_utc"]) is None
    ):
        raise CorpusResearchProjectionError("UI projection identity differs")
    if projection.get("read_only") is not True:
        raise CorpusResearchProjectionError("UI projection must be read-only")
    for field in (
        "graph_mutation", "automatic_promotion",
        "application_config_mutation", "production_policy_authority",
    ):
        if projection.get(field) is not False:
            raise CorpusResearchProjectionError(
                f"UI projection.{field} must remain false"
            )
    _self_hash(projection, field="projection_sha256", label="UI projection")

    source = _validate_source_receipt(projection["source_projection_receipt"])
    if source["registry_id"] != projection["registry_id"]:
        raise CorpusResearchProjectionError(
            "UI/source projection registry binding differs"
        )

    receipt = _mapping(projection["query_receipt"], label="UI query receipt")
    expected_receipt_keys = {
        "schema_version", "publication_mode", "registry_id", "database",
        "namespace", "source_projection_receipt_sha256", "generated_at_utc",
        "queries", "read_only", "graph_mutation", "automatic_promotion",
        "application_config_mutation", "production_policy_authority",
        "gcs_remains_authoritative", "world_matrices_stored_in_graph",
        "query_receipt_sha256",
    }
    if set(receipt) != expected_receipt_keys:
        raise CorpusResearchProjectionError("UI query receipt fields differ")
    if (
        receipt["schema_version"] != UI_QUERY_RECEIPT_SCHEMA
        or receipt["publication_mode"] != "read_only_materialization"
        or receipt["registry_id"] != projection["registry_id"]
        or receipt["database"] != projection["database"]
        or receipt["namespace"] != REGISTRY_NAMESPACE
        or receipt["generated_at_utc"] != projection["generated_at_utc"]
        or receipt["source_projection_receipt_sha256"]
        != source["projection_receipt_sha256"]
    ):
        raise CorpusResearchProjectionError("UI query receipt binding differs")
    if receipt.get("read_only") is not True:
        raise CorpusResearchProjectionError("UI query receipt is not read-only")
    _require_authority_firewall(receipt, label="UI query receipt")
    if receipt.get("graph_mutation") is not False:
        raise CorpusResearchProjectionError(
            "UI query receipt.graph_mutation must remain false"
        )
    _self_hash(
        receipt, field="query_receipt_sha256", label="UI query receipt"
    )

    views = _mapping(projection["views"], label="UI views")
    raw_query_rows = receipt.get("queries")
    if not isinstance(raw_query_rows, list):
        raise CorpusResearchProjectionError("UI query catalog must be an array")
    query_rows: dict[str, dict[str, object]] = {}
    for ordinal, raw in enumerate(raw_query_rows):
        row = _mapping(raw, label=f"UI query catalog[{ordinal}]")
        if set(row) != {"name", "cypher_sha256", "row_count", "rows_sha256"}:
            raise CorpusResearchProjectionError("UI query catalog fields differ")
        name = row.get("name")
        if (
            not isinstance(name, str)
            or _ID.fullmatch(name) is None
            or name in query_rows
            or not isinstance(row.get("row_count"), int)
            or isinstance(row.get("row_count"), bool)
            or row["row_count"] < 0
            or not isinstance(row.get("cypher_sha256"), str)
            or _SHA.fullmatch(row["cypher_sha256"]) is None
            or not isinstance(row.get("rows_sha256"), str)
            or _SHA.fullmatch(row["rows_sha256"]) is None
        ):
            raise CorpusResearchProjectionError("UI query catalog row differs")
        query_rows[name] = row
    if set(views) != set(query_rows) or not REQUIRED_VIEW_NAMES.issubset(views):
        raise CorpusResearchProjectionError("UI view/query catalog differs")

    total_rows = 0
    normalized_views: dict[str, list[dict[str, object]]] = {}
    for name, raw in views.items():
        rows = _rows(raw, label=f"UI view {name}")
        if rows != sorted(rows, key=_canonical_sha256):
            raise CorpusResearchProjectionError(
                f"UI view {name} is not canonically ordered"
            )
        query_row = query_rows[name]
        if (
            query_row["row_count"] != len(rows)
            or query_row["rows_sha256"] != _canonical_sha256(rows)
        ):
            raise CorpusResearchProjectionError(
                f"UI view {name} row receipt differs"
            )
        total_rows += len(rows)
        normalized_views[name] = rows
    if total_rows > MAX_QUERY_ROWS:
        raise CorpusResearchProjectionError(
            "combined UI view rows exceed the limit"
        )
    return {
        **projection,
        "source_projection_receipt": source,
        "query_receipt": receipt,
        "views": normalized_views,
    }


class FileCorpusResearchProjectionReader:
    """Read one receipt-bound projection from an operator-configured file."""

    def __init__(self, path: Path | None) -> None:
        self._path = path

    @classmethod
    def from_environment(cls) -> FileCorpusResearchProjectionReader:
        raw = os.environ.get(PROJECTION_PATH_ENV, "").strip()
        return cls(Path(raw) if raw else None)

    def read(self) -> ProjectionAvailability:
        if self._path is None:
            return ProjectionAvailability(
                ready=False,
                projection=None,
                reason_code="projection-not-configured",
                message=(
                    "The read-only corpus projection is not connected yet. "
                    "Scoring can continue independently; this page will "
                    "activate after a receipt-bound graph projection is set."
                ),
            )
        try:
            size = self._path.stat().st_size
            if size <= 0 or size > MAX_PROJECTION_BYTES:
                raise CorpusResearchProjectionError(
                    "projection file size is outside the accepted bounds"
                )
            raw = self._path.read_bytes()
            if len(raw) != size:
                raise CorpusResearchProjectionError(
                    "projection file changed during the read"
                )
            projection = validate_read_only_projection(json.loads(raw))
        except (OSError, json.JSONDecodeError, CorpusResearchProjectionError):
            log.exception("Corpus research UI projection is not ready")
            return ProjectionAvailability(
                ready=False,
                projection=None,
                reason_code="projection-invalid-or-unavailable",
                message=(
                    "The corpus graph projection is unavailable or failed "
                    "its read-only receipt checks. No unverified data is shown."
                ),
            )
        return ProjectionAvailability(
            ready=True,
            projection=projection,
            reason_code="ready",
            message="Receipt-bound read-only corpus projection loaded.",
        )


class ReadOnlyQueryProjectionReader:
    """Adapter for a Neo4j read session supplied by application wiring."""

    def __init__(
        self,
        *,
        source_projection_receipt: Mapping[str, object],
        database: str,
        queries: Sequence[ReadOnlyQuery],
        query_runner: QueryRunner,
    ) -> None:
        self._source_projection_receipt = dict(source_projection_receipt)
        self._database = database
        self._queries = tuple(queries)
        self._query_runner = query_runner

    def read(self) -> ProjectionAvailability:
        try:
            projection = build_read_only_projection(
                source_projection_receipt=self._source_projection_receipt,
                database=self._database,
                queries=self._queries,
                query_runner=self._query_runner,
            )
            projection = validate_read_only_projection(projection)
        except Exception:  # The injected read driver has provider-specific errors.
            log.exception("Corpus research read-only query projection failed")
            return ProjectionAvailability(
                ready=False,
                projection=None,
                reason_code="graph-query-projection-failed",
                message=(
                    "The dedicated corpus graph did not produce a complete "
                    "receipt-bound read projection. No partial data is shown."
                ),
            )
        return ProjectionAvailability(
            ready=True,
            projection=projection,
            reason_code="ready",
            message="Receipt-bound read-only corpus projection loaded.",
        )


@lru_cache
def default_corpus_research_reader() -> CorpusResearchProjectionReader:
    return FileCorpusResearchProjectionReader.from_environment()


def get_corpus_research_reader() -> CorpusResearchProjectionReader:
    return default_corpus_research_reader()


def _read_validated(
    reader: CorpusResearchProjectionReader,
) -> ProjectionAvailability:
    try:
        availability = reader.read()
        if not availability.ready:
            return ProjectionAvailability(
                ready=False,
                projection=None,
                reason_code=str(availability.reason_code),
                message=str(availability.message),
            )
        if availability.projection is None:
            raise CorpusResearchProjectionError(
                "ready projection reader returned no projection"
            )
        validated = validate_read_only_projection(availability.projection)
    except Exception:  # Reader implementations may surface provider errors.
        log.exception("Corpus research reader failed the API boundary")
        return ProjectionAvailability(
            ready=False,
            projection=None,
            reason_code="projection-validation-failed",
            message=(
                "The corpus projection failed its API-boundary receipt checks. "
                "No partial or unverified data is shown."
            ),
        )
    return ProjectionAvailability(
        ready=True,
        projection=validated,
        reason_code=availability.reason_code,
        message=availability.message,
    )


def _status_payload(availability: ProjectionAvailability) -> dict[str, object]:
    status: dict[str, object] = {
        "schema_version": "corpus-research-ui-status/v1",
        "ready": availability.ready,
        "reason_code": availability.reason_code,
        "message": availability.message,
        "read_only": True,
        "graph_mutation": False,
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
    }
    projection = availability.projection
    if projection is not None:
        views = _mapping(projection["views"], label="status views")
        status.update({
            "registry_id": projection["registry_id"],
            "database": projection["database"],
            "generated_at_utc": projection["generated_at_utc"],
            "projection_sha256": projection["projection_sha256"],
            "view_row_counts": {
                name: len(rows) if isinstance(rows, list) else 0
                for name, rows in sorted(views.items())
            },
        })
    return status


@router.get("/corpus-research", response_class=HTMLResponse)
def corpus_research_page() -> HTMLResponse:
    return HTMLResponse(
        CORPUS_RESEARCH_HTML,
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/corpus-research/status")
def corpus_research_status(
    reader: CorpusResearchProjectionReader = Depends(
        get_corpus_research_reader
    ),
) -> JSONResponse:
    availability = _read_validated(reader)
    return JSONResponse(
        _status_payload(availability),
        headers={"Cache-Control": "no-store"},
    )


@router.get("/api/corpus-research/projection")
def corpus_research_projection(
    reader: CorpusResearchProjectionReader = Depends(
        get_corpus_research_reader
    ),
) -> JSONResponse:
    availability = _read_validated(reader)
    if not availability.ready or availability.projection is None:
        return JSONResponse(
            _status_payload(availability),
            status_code=503,
            headers={"Cache-Control": "no-store"},
        )
    return JSONResponse(
        {
            "status": _status_payload(availability),
            "projection": availability.projection,
        },
        headers={"Cache-Control": "no-store"},
    )


CORPUS_RESEARCH_HTML: Final = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Corpus Research Observatory</title>
  <link rel="icon" href="/static/logo.png">
  <link rel="stylesheet" href="/static/corpus_research.css">
</head>
<body>
  <header class="cr-topbar">
    <a class="cr-brand" href="/">
      <img src="/static/logo.png" alt=""><span>Fingerblasters' Brain</span>
    </a>
    <nav aria-label="Primary">
      <a href="/">Season</a><a href="/lineups/view">Lineups</a>
      <a href="/defense">Defense</a><a href="/market">Market</a>
      <a class="active" href="/corpus-research">Corpus research</a>
      <a href="/docs">API</a>
    </nav>
  </header>

  <main>
    <section class="cr-hero">
      <div>
        <p class="eyebrow">Dedicated research graph</p>
        <h1>Corpus Research Observatory</h1>
        <p class="lede">Trace how fill and retrieval strategies behave across
          slates, thresholds, and held-out evidence—without changing the
          corpus or the live application.</p>
      </div>
      <div class="safety-lock" aria-label="Research safety boundary">
        <span class="lock-dot"></span>
        <div><strong>Read-only research</strong>
          <small>No graph mutation · no automatic promotion</small></div>
      </div>
    </section>

    <section id="not-ready" class="not-ready" role="status">
      <div class="pulse-orbit" aria-hidden="true"><span></span></div>
      <div><h2>Connecting the research projection</h2>
        <p id="not-ready-message">Checking the receipt-bound graph view…</p>
        <small>Scoring and corpus construction operate independently of this
          visualization layer.</small></div>
    </section>

    <section id="research-content" hidden>
      <div class="meta-strip" aria-label="Projection status">
        <div><span>Registry</span><strong id="meta-registry">—</strong></div>
        <div><span>Projected</span><strong id="meta-time">—</strong></div>
        <div><span>Graph rows</span><strong id="meta-rows">—</strong></div>
        <div><span>Winner evidence</span><strong id="meta-winners">—</strong></div>
        <div class="receipt"><span>Receipt</span><strong id="meta-hash">—</strong></div>
      </div>

      <section class="panel lineage-panel">
        <div class="panel-head"><div><p class="eyebrow">Strategy provenance</p>
          <h2>Fill → snapshot → retrieval → experiment</h2></div>
          <label>Slate<select id="lineage-slate"></select></label></div>
        <svg id="lineage-chart" class="chart lineage" viewBox="0 0 1080 430"
          role="img" aria-label="Strategy lineage graph"></svg>
        <div id="preset-catalog" class="preset-catalog"
          aria-label="Registered fill and retrieval presets"></div>
      </section>

      <div class="panel-grid">
        <section class="panel">
          <div class="panel-head"><div><p class="eyebrow">Performance surface</p>
            <h2>Fill × retrieval heatmap</h2></div></div>
          <div class="controls two">
            <label>Metric<select id="heat-metric"></select></label>
            <label>Split<select id="heat-split"></select></label>
          </div>
          <svg id="heatmap-chart" class="chart" viewBox="0 0 720 430"
            role="img" aria-label="Fill and retrieval performance heatmap"></svg>
        </section>

        <section class="panel">
          <div class="panel-head"><div><p class="eyebrow">Paired evidence</p>
            <h2>Paired baseline deltas</h2></div>
            <label>Metric<select id="paired-metric"></select></label></div>
          <svg id="paired-chart" class="chart" viewBox="0 0 720 430"
            role="img" aria-label="Paired strategy baseline deltas"></svg>
          <div class="legend"><span class="disc"></span>Primary / descriptive delta
            <span class="held"></span>Held-out delta
            <span class="stable"></span>Same direction</div>
        </section>
      </div>

      <div class="panel-grid lower">
        <section class="panel">
          <div class="panel-head"><div><p class="eyebrow">Tail geometry</p>
            <h2>&gt;200 coverage vs diversity</h2></div></div>
          <div class="controls two">
            <label>Coverage metric<select id="scatter-x"></select></label>
            <label>Diversity metric<select id="scatter-y"></select></label>
          </div>
          <svg id="scatter-chart" class="chart" viewBox="0 0 720 430"
            role="img" aria-label="Coverage versus diversity scatter plot"></svg>
        </section>

        <section class="panel">
          <div class="panel-head"><div><p class="eyebrow">Governed decisions</p>
            <h2>Promotion history</h2></div>
            <span class="manual-pill">Human reviewed</span></div>
          <svg id="promotion-chart" class="chart" viewBox="0 0 720 430"
            role="img" aria-label="Promotion decision timeline"></svg>
        </section>
      </div>

      <section class="panel network-panel">
        <div class="panel-head"><div><p class="eyebrow">Structural intelligence</p>
          <h2>Lineup → player → team → game</h2>
          <p class="subhead">Select a lineup to inspect the football structure
            behind its score and winner relationship.</p></div>
          <div class="controls network-controls">
            <label>Slate<select id="network-slate"></select></label>
            <label>Lineup<select id="network-lineup"></select></label>
            <label class="check"><input id="winner-only" type="checkbox">
              Winners only</label>
          </div></div>
        <div class="network-layout">
          <svg id="network-chart" class="chart network" viewBox="0 0 920 540"
            role="img" aria-label="Lineup player team game network"></svg>
          <aside class="roster-detail">
            <div id="lineup-summary" class="lineup-summary"></div>
            <div class="table-wrap"><table>
              <thead><tr><th>Player</th><th>Team</th><th>Game</th></tr></thead>
              <tbody id="roster-body"></tbody>
            </table></div>
          </aside>
        </div>
      </section>

      <footer>
        <span>Visualization data is a rebuildable Neo4j projection.</span>
        <span>GCS receipts and immutable artifacts remain authoritative.</span>
      </footer>
    </section>
  </main>
  <script src="/static/vendor/react.production.min.js" defer></script>
  <script src="/static/vendor/react-dom.production.min.js" defer></script>
  <script src="/static/vendor/htm.min.js" defer></script>
  <script src="/static/corpus_research.js" defer></script>
</body>
</html>"""


__all__ = [
    "CORPUS_RESEARCH_HTML",
    "CorpusResearchProjectionError",
    "CorpusResearchProjectionReader",
    "FileCorpusResearchProjectionReader",
    "ProjectionAvailability",
    "ReadOnlyQuery",
    "ReadOnlyQueryProjectionReader",
    "REQUIRED_VIEW_NAMES",
    "REGISTRY_NAMESPACE",
    "SOURCE_PROJECTION_SCHEMA",
    "UI_PROJECTION_SCHEMA",
    "UI_QUERY_RECEIPT_SCHEMA",
    "build_read_only_projection",
    "default_corpus_research_reader",
    "get_corpus_research_reader",
    "router",
    "validate_read_only_projection",
]
