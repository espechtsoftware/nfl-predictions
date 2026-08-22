#!/usr/bin/env python3
"""Create-once transport for the corpus artifact source authority.

The heavy science remains in ``lr8_later_period_source`` and
``corpus_artifact_source_authority``.  This module supplies only the missing
operational boundary: a pre-query registration, three fixed point-in-time
structural queries, generation-pinned object transport, a closed task-major
R0--R4 stream, and create-once publication.

``validate-only`` and ``dry-run`` are client-free.  ``execute`` requires both
the literal flag and ``CORPUS_ARTIFACT_SOURCE_AUTHORITY_ENABLED=1`` before a
storage or BigQuery client can be constructed.  The worker never lists the
artifact source namespace and never reads a realized-outcome field.
"""

from __future__ import annotations

import argparse
from collections.abc import Callable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Final, Protocol


ROOT: Final = Path(__file__).resolve().parents[1]
SRC: Final = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from nfl_dfs.research import corpus_artifact_source_authority as authority  # noqa: E402
from nfl_dfs.research import lr8_later_period_source as later  # noqa: E402
from nfl_dfs.research import residual_world_columns as rw  # noqa: E402
from nfl_dfs.research.corpus_parametric_batch import (  # noqa: E402
    TASK_WORLD_SOURCE_ROLES,
)


PROJECT: Final = "nfl-predictions-503414"
LOCATION: Final = "US"
ENABLE_ENV: Final = "CORPUS_ARTIFACT_SOURCE_AUTHORITY_ENABLED"
IMAGE_ENV: Final = "CORPUS_ARTIFACT_SOURCE_IMAGE"
CODE_ENV: Final = "CODE_SHA"

PLAN_SCHEMA: Final = "corpus-artifact-source-publication-plan/v1"
PREFIX_CLAIM_SCHEMA: Final = "corpus-artifact-source-prefix-claim/v1"
QUERY_CAPTURE_SCHEMA: Final = "corpus-artifact-source-query-capture/v1"
PUBLICATION_COMPLETION_SCHEMA: Final = (
    "corpus-artifact-source-publication-completion/v1"
)
PRODUCER_GET_TRACE_SCHEMA: Final = "corpus-artifact-source-producer-get-trace/v1"
PRODUCER_QUERY_TRACE_SCHEMA: Final = (
    "corpus-artifact-source-producer-query-trace/v1"
)
LAUNCH_LEDGER_SCHEMA: Final = "corpus-artifact-source-launch-ledger/v1"

SALARY_SQL_RELATIVE_PATH: Final = (
    "reports/corpus-parametric-runs/"
    "20260821-corpus-artifact-source-authority-v1/"
    "governance/salary-player-id-query.sql"
)
SALARY_SQL_PATH: Final = ROOT / SALARY_SQL_RELATIVE_PATH
SALARY_SQL_SHA256: Final = (
    "6693650e117b35cf755149ea085f0ed54641cc64ba2a456a2c6920bc1dc5795b"
)
SALARY_TABLE: Final = later.CATALOG_TABLE
SALARY_SELECTED_COLUMNS: Final = ("id", "season", "week")

BASE_SOURCE_OBJECT: Final = {
    "uri": later.BASE_SOURCE_URI,
    "generation": later.BASE_SOURCE_GENERATION,
    "sha256": later.BASE_SOURCE_SHA256,
    "bytes": later.BASE_SOURCE_BYTES,
}

QUERY_ROLES: Final = (
    "r0_candidates",
    "artifact_catalog",
    "salary_player_ids",
)
QUERY_ROW_ORDERS: Final = {
    "r0_candidates": "season-week-cand_ix-ascending",
    "artifact_catalog": "season-week-id-ascending",
    "salary_player_ids": "season-week-id-ascending-distinct",
}

_PUBLICATION_COMPLETION_KEYS: Final = frozenset({
    "schema",
    "run_id",
    "plan_sha256",
    "output_prefix",
    "prefix_claim",
    "registration_object",
    "registration_sha256",
    "query_captures",
    "later_source_freeze_object",
    "later_source_freeze_manifest_sha256",
    "salary_diagnostic_object",
    "salary_diagnostic_sha256",
    "source_authority_completion_object",
    "source_authority_completion_sha256",
    "base_source_lock_object",
    "task_count",
    "artifact_count",
    "artifact_reads",
    "artifact_list_used",
    "producer_get_trace",
    "producer_query_trace",
    "producer_trace_complete_before_terminal_publication",
    "inventory_before_publication",
    "inventory_before_publication_sha256",
    "create_once",
    "outcome_columns_read",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "production_change_licensed",
    "live_strategy_authority",
    "publication_completion_sha256",
})
_CAPTURE_PUBLICATION_KEYS: Final = frozenset({
    "object", "job_id", "row_count", "rows_sha256", "capture_sha256",
})

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")
_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,159}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_FORBIDDEN_OUTCOME_FRAGMENTS: Final = (
    "actual",
    "contest_rank",
    "fantasy_points",
    "first_place",
    "outcome",
    "payout",
    "realized",
    "standings",
    "winner",
)


class CorpusArtifactSourcePreparationError(RuntimeError):
    """The source-authority transport failed closed."""


@dataclass(frozen=True, slots=True)
class QueryOutcome:
    rows: tuple[Mapping[str, object], ...]
    receipt: Mapping[str, object]


class StorageBoundary(Protocol):
    def read(self, identity: Mapping[str, object]) -> bytes: ...

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]: ...

    def require_absent(self, uris: Sequence[str]) -> None: ...


class QueryBoundary(Protocol):
    def require_unused_job_ids(self, job_ids: Sequence[str]) -> None: ...

    def run_query(
        self,
        *,
        sql: str,
        query_identity: Mapping[str, object],
        parameters: Sequence[Mapping[str, object]],
    ) -> QueryOutcome: ...


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusArtifactSourcePreparationError(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def parse_canonical_json_bytes(raw: bytes, *, label: str) -> object:
    def unique(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise CorpusArtifactSourcePreparationError(
                    f"{label} repeats key {key!r}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise CorpusArtifactSourcePreparationError(
            f"{label} contains non-finite value {value}"
        )

    if type(raw) is not bytes:
        raise CorpusArtifactSourcePreparationError(f"{label} must be bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=unique,
            parse_constant=reject_constant,
        )
    except CorpusArtifactSourcePreparationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusArtifactSourcePreparationError(
            f"{label} is not UTF-8 JSON"
        ) from exc
    if canonical_json_bytes(value) != raw:
        raise CorpusArtifactSourcePreparationError(
            f"{label} is not canonical JSON"
        )
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusArtifactSourcePreparationError(f"{label} must be an object")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise CorpusArtifactSourcePreparationError(
            f"{label} keys differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusArtifactSourcePreparationError(
            f"{label} must be a nonempty canonical string"
        )
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        raise CorpusArtifactSourcePreparationError(
            f"{label} must be an exact integer >= {minimum}"
        )
    return value


def _sha(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _SHA256.fullmatch(text) is None:
        raise CorpusArtifactSourcePreparationError(
            f"{label} must be a lowercase SHA-256"
        )
    return text


def _timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    text = _string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise CorpusArtifactSourcePreparationError(
            f"{label} must be ISO-8601"
        ) from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(None):
        raise CorpusArtifactSourcePreparationError(f"{label} must be UTC")
    return text, parsed


def normalize_object_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(
        item,
        frozenset({"uri", "generation", "sha256", "bytes"}),
        label=label,
    )
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
        raise CorpusArtifactSourcePreparationError(
            f"{label}.uri must be one canonical GCS object URI"
        )
    generation = _string(item["generation"], label=f"{label}.generation")
    if _GENERATION.fullmatch(generation) is None:
        raise CorpusArtifactSourcePreparationError(
            f"{label}.generation must be positive decimal"
        )
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _sha(item["sha256"], label=f"{label}.sha256"),
        "bytes": _exact_int(item["bytes"], label=f"{label}.bytes", minimum=1),
    }


def _gcs_prefix(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    tail = text.removeprefix("gs://")
    bucket, separator, name = tail.partition("/")
    if (
        not text.startswith("gs://")
        or not bucket
        or not separator
        or not name
        or not text.endswith("/")
        or "//" in name
        or ".." in name.split("/")
    ):
        raise CorpusArtifactSourcePreparationError(
            f"{label} must be one narrow canonical GCS prefix"
        )
    return text


def _self_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        raise CorpusArtifactSourcePreparationError(f"{field} is already present")
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> None:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if retained != canonical_sha256(body):
        raise CorpusArtifactSourcePreparationError(f"{label} self-hash differs")


def _identity_for_raw(uri: str, generation: str, raw: bytes) -> dict[str, object]:
    return normalize_object_identity({
        "uri": uri,
        "generation": generation,
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }, label="raw object identity")


def _bind_raw(
    raw: bytes, identity: object, *, label: str,
) -> dict[str, object]:
    normalized = normalize_object_identity(identity, label=label)
    if (
        type(raw) is not bytes
        or len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        raise CorpusArtifactSourcePreparationError(
            f"{label} bytes differ from generation-pinned identity"
        )
    return normalized


class _TracingStorageBoundary:
    """Fail-closed, observed GET boundary for the source producer.

    The delivered plan is the only bootstrap read.  Once parsed, the exact
    base lock, its 270 retained artifact identities, and the nine deterministic
    output names are the complete storage authority.  The trace is sealed
    immediately before the terminal publication, and no producer GET occurs
    after that seal.
    """

    def __init__(
        self,
        storage: StorageBoundary,
        *,
        delivered_plan_identity: Mapping[str, object] | None = None,
        delivered_intent_identity: Mapping[str, object] | None = None,
    ) -> None:
        self._storage = storage
        self._allowed_inputs: dict[tuple[str, str], dict[str, object]] = {}
        self._allowed_outputs: set[str] = set()
        self._output_uris: list[str] = []
        self._published: dict[tuple[str, str], dict[str, object]] = {}
        self._events: list[dict[str, object]] = []
        self._absence_uris: list[str] | None = None
        self._sealed = False
        self._delivered_plan_identity = (
            None
            if delivered_plan_identity is None
            else normalize_object_identity(
                delivered_plan_identity, label="delivered trace plan"
            )
        )
        self._delivered_intent_identity = (
            None
            if delivered_intent_identity is None
            else normalize_object_identity(
                delivered_intent_identity, label="delivered trace intent"
            )
        )
        delivered = [
            identity
            for identity in (
                self._delivered_plan_identity,
                self._delivered_intent_identity,
            )
            if identity is not None
        ]
        if delivered:
            self._authorize_inputs(delivered)

    def _authorize_inputs(self, values: Sequence[Mapping[str, object]]) -> None:
        if self._sealed:
            raise CorpusArtifactSourcePreparationError(
                "producer GET authority is already sealed"
            )
        for ordinal, value in enumerate(values):
            identity = normalize_object_identity(
                value, label=f"producer allowed input[{ordinal}]"
            )
            key = (str(identity["uri"]), str(identity["generation"]))
            retained = self._allowed_inputs.get(key)
            if retained is not None and retained != identity:
                raise CorpusArtifactSourcePreparationError(
                    "producer GET authority aliases one object generation"
                )
            self._allowed_inputs[key] = identity

    def configure_plan(self, plan: Mapping[str, object]) -> None:
        frozen = validate_execution_plan(plan)
        self._authorize_inputs([
            normalize_object_identity(
                frozen["base_source_lock_object"], label="trace base source lock"
            )
        ])
        output_uris = list(
            _publication_uris(str(frozen["output_prefix"])).values()
        )
        outputs = set(output_uris)
        if self._allowed_outputs and self._allowed_outputs != outputs:
            raise CorpusArtifactSourcePreparationError(
                "producer output authority cannot be replaced"
            )
        self._allowed_outputs = outputs
        self._output_uris = output_uris

    def authorize_artifacts(
        self, receipts: Sequence[Mapping[str, object]]
    ) -> None:
        identities = [
            {
                key: receipt[key]
                for key in ("uri", "generation", "sha256", "bytes")
            }
            for receipt in receipts
        ]
        self._authorize_inputs(identities)

    def read(self, identity: Mapping[str, object]) -> bytes:
        if self._sealed:
            raise CorpusArtifactSourcePreparationError(
                "producer attempted a GET after trace seal"
            )
        normalized = normalize_object_identity(identity, label="producer traced GET")
        key = (str(normalized["uri"]), str(normalized["generation"]))
        allowed = self._allowed_inputs.get(key) or self._published.get(key)
        if allowed != normalized:
            raise CorpusArtifactSourcePreparationError(
                f"producer GET is outside exact authority: {normalized['uri']}"
            )
        raw = self._storage.read(normalized)
        _bind_raw(raw, normalized, label="producer traced GET body")
        self._events.append({
            "ordinal": len(self._events),
            "identity": normalized,
        })
        return raw

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]:
        terminal_after_seal = (
            self._sealed
            and bool(self._output_uris)
            and uri == self._output_uris[-1]
        )
        if (
            uri not in self._allowed_outputs
            or (self._sealed and not terminal_after_seal)
        ):
            raise CorpusArtifactSourcePreparationError(
                f"producer publication is outside exact authority: {uri}"
            )
        if any(identity["uri"] == uri for identity in self._published.values()):
            raise CorpusArtifactSourcePreparationError(
                f"producer publication repeats deterministic URI: {uri}"
            )
        identity = normalize_object_identity(
            self._storage.publish(uri, raw), label="producer traced publication"
        )
        _bind_raw(raw, identity, label="producer traced publication body")
        if identity["uri"] != uri:
            raise CorpusArtifactSourcePreparationError(
                "producer publication URI alias differs"
            )
        key = (str(identity["uri"]), str(identity["generation"]))
        self._published[key] = identity
        return identity

    def require_absent(self, uris: Sequence[str]) -> None:
        expected = list(self._output_uris)
        observed = list(uris)
        if (
            self._sealed
            or self._absence_uris is not None
            or observed != expected
        ):
            raise CorpusArtifactSourcePreparationError(
                "producer exact-name absence boundary differs"
            )
        self._storage.require_absent(observed)
        self._absence_uris = observed

    def seal_trace(self) -> dict[str, object]:
        if self._sealed or self._absence_uris is None:
            raise CorpusArtifactSourcePreparationError(
                "producer GET trace cannot be sealed"
            )
        self._sealed = True
        body = {
            "schema": PRODUCER_GET_TRACE_SCHEMA,
            "delivered_plan_object": self._delivered_plan_identity,
            "delivered_intent_object": self._delivered_intent_identity,
            "events": list(self._events),
            "event_count": len(self._events),
            "events_sha256": canonical_sha256(self._events),
            "absence_check_uris": list(self._absence_uris),
            "object_list_used": False,
            "complete": True,
        }
        return _self_hash(body, field="trace_sha256")

    @property
    def delivered_plan_identity(self) -> Mapping[str, object] | None:
        return self._delivered_plan_identity

    @property
    def delivered_intent_identity(self) -> Mapping[str, object] | None:
        return self._delivered_intent_identity


class _TracingQueryBoundary:
    """Restrict and record the exact three registered query operations."""

    def __init__(
        self, query: QueryBoundary, *, registration: Mapping[str, object]
    ) -> None:
        self._query = query
        self._identities = _query_identities(registration)
        self._specs = _query_specs(registration)
        self._events: list[dict[str, object]] = []
        self._absence_checked = False
        self._next_role = 0
        self._sealed = False

    def require_unused_job_ids(self, job_ids: Sequence[str]) -> None:
        expected = [str(self._identities[role]["job_id"]) for role in QUERY_ROLES]
        if self._sealed or self._absence_checked or list(job_ids) != expected:
            raise CorpusArtifactSourcePreparationError(
                "producer query-ID absence authority differs"
            )
        self._query.require_unused_job_ids(job_ids)
        for job_id in expected:
            self._events.append({
                "ordinal": len(self._events),
                "operation": "require-unused-job-id",
                "job_id": job_id,
            })
        self._absence_checked = True

    def run_query(
        self,
        *,
        sql: str,
        query_identity: Mapping[str, object],
        parameters: Sequence[Mapping[str, object]],
    ) -> QueryOutcome:
        if (
            self._sealed
            or not self._absence_checked
            or self._next_role >= len(QUERY_ROLES)
        ):
            raise CorpusArtifactSourcePreparationError(
                "producer query sequence differs"
            )
        role = QUERY_ROLES[self._next_role]
        expected_sql, expected_parameters = self._specs[role]
        if (
            dict(query_identity) != self._identities[role]
            or sql != expected_sql
            or list(parameters) != list(expected_parameters)
        ):
            raise CorpusArtifactSourcePreparationError(
                f"producer query authority differs for {role}"
            )
        outcome = self._query.run_query(
            sql=sql,
            query_identity=query_identity,
            parameters=parameters,
        )
        receipt = dict(_mapping(outcome.receipt, label=f"{role} query receipt"))
        self._events.append({
            "ordinal": len(self._events),
            "operation": "run-query",
            "role": role,
            "job_id": query_identity["job_id"],
            "sql_sha256": sha256(sql.encode("utf-8")).hexdigest(),
            "parameters_sha256": canonical_sha256(list(parameters)),
            "receipt_sha256": canonical_sha256(receipt),
        })
        self._next_role += 1
        return outcome

    def seal_trace(self) -> dict[str, object]:
        if (
            self._sealed
            or not self._absence_checked
            or self._next_role != len(QUERY_ROLES)
        ):
            raise CorpusArtifactSourcePreparationError(
                "producer query trace is incomplete"
            )
        self._sealed = True
        body = {
            "schema": PRODUCER_QUERY_TRACE_SCHEMA,
            "events": list(self._events),
            "event_count": len(self._events),
            "events_sha256": canonical_sha256(self._events),
            "complete": True,
        }
        return _self_hash(body, field="trace_sha256")


def require_execute_gate(*, execute: bool, environ: Mapping[str, str]) -> None:
    """Run before either cloud client factory is called."""
    if execute is not True:
        raise CorpusArtifactSourcePreparationError("literal --execute is required")
    if environ.get(ENABLE_ENV) != "1":
        raise CorpusArtifactSourcePreparationError(f"{ENABLE_ENV}=1 is required")


def _salary_sql_bytes() -> bytes:
    try:
        raw = SALARY_SQL_PATH.read_bytes()
    except OSError as exc:
        raise CorpusArtifactSourcePreparationError(
            "frozen salary-ID SQL file is absent"
        ) from exc
    if sha256(raw).hexdigest() != SALARY_SQL_SHA256:
        raise CorpusArtifactSourcePreparationError(
            "frozen salary-ID SQL hash differs"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusArtifactSourcePreparationError(
            "frozen salary-ID SQL is not UTF-8"
        ) from exc
    lowered = text.lower()
    if (
        f"`{SALARY_TABLE}`" not in text
        or "for system_time as of @source_snapshot_at" not in lowered
        or "select distinct season, week, id" not in lowered
        or any(fragment in lowered for fragment in _FORBIDDEN_OUTCOME_FRAGMENTS)
    ):
        raise CorpusArtifactSourcePreparationError(
            "frozen salary-ID SQL boundary differs"
        )
    return raw


def salary_parameter_payload(snapshot: str) -> list[dict[str, object]]:
    normalized, _ = _timestamp(snapshot, label="salary source snapshot")
    return [{
        "name": "source_snapshot_at",
        "type": "TIMESTAMP",
        "value": normalized,
    }]


def validate_base_source_lock_bytes(
    raw: bytes,
    *,
    identity: object | None = None,
) -> tuple[dict[str, object], tuple[dict[str, object], ...]]:
    """Bind the exact retained 54-slate/270-artifact identity lattice."""
    if identity is None:
        identity = BASE_SOURCE_OBJECT
    normalized_identity = _bind_raw(raw, identity, label="base source lock")
    if normalized_identity != BASE_SOURCE_OBJECT:
        raise CorpusArtifactSourcePreparationError(
            "base source-lock object identity differs"
        )
    # The retained, generation-pinned object uses the producer's canonical
    # JSON-line representation: one canonical JSON document plus one LF.
    document_raw = raw[:-1] if raw.endswith(b"\n") else raw
    value = _mapping(
        parse_canonical_json_bytes(document_raw, label="base source lock"),
        label="base source lock",
    )
    try:
        receipts = later._artifact_receipts(value)  # noqa: SLF001
    except later.LR8LaterSourceError as exc:
        raise CorpusArtifactSourcePreparationError(
            "base source-lock 54xR0-R4 lattice differs"
        ) from exc
    if (
        len(receipts) != authority.EXPECTED_ARTIFACT_COUNT
        or value.get("slates") != authority.EXPECTED_TASK_COUNT
        or value.get("artifact_count") != authority.EXPECTED_ARTIFACT_COUNT
    ):
        raise CorpusArtifactSourcePreparationError(
            "base source-lock coverage differs"
        )
    return dict(value), receipts


def _query_identity(
    *,
    job_id: str,
    table: str,
    sql_sha256: str,
    parameters_sha256: str,
    selected_columns: Sequence[str],
) -> dict[str, object]:
    return {
        "job_id": job_id,
        "location": LOCATION,
        "table": table,
        "sql_sha256": sql_sha256,
        "parameters_sha256": parameters_sha256,
        "selected_columns": list(selected_columns),
        "realized_columns_selected": [],
    }


def build_registration(
    *,
    run_id: str,
    registered_at: str,
    source_snapshot_at: str,
) -> dict[str, object]:
    if _RUN_ID.fullmatch(run_id) is None:
        raise CorpusArtifactSourcePreparationError("source run ID differs")
    registered_text, registered_dt = _timestamp(
        registered_at, label="registration timestamp"
    )
    snapshot_text, snapshot_dt = _timestamp(
        source_snapshot_at, label="source snapshot"
    )
    if registered_dt > snapshot_dt:
        raise CorpusArtifactSourcePreparationError(
            "registration timestamp must not follow source snapshot"
        )
    source_params_sha = later.canonical_sha256(
        later.source_parameter_payload(snapshot_text)
    )
    salary_params_sha = canonical_sha256(
        salary_parameter_payload(snapshot_text)
    )
    body: dict[str, object] = {
        "schema": authority.REGISTRATION_SCHEMA,
        "authority_id": run_id,
        "registered_at": registered_text,
        "source_snapshot_at": snapshot_text,
        "source_run_id": run_id,
        "source_queries": {
            "r0_candidates": _query_identity(
                job_id=f"{run_id}-r0-candidates",
                table=later.CANDIDATE_TABLE,
                sql_sha256=later.CANDIDATE_SQL_SHA256,
                parameters_sha256=source_params_sha,
                selected_columns=sorted(later.R0_CANDIDATE_FIELDS),
            ),
            "artifact_catalog": _query_identity(
                job_id=f"{run_id}-full-catalog",
                table=later.CATALOG_TABLE,
                sql_sha256=later.CATALOG_SQL_SHA256,
                parameters_sha256=source_params_sha,
                selected_columns=sorted(later.CATALOG_FIELDS),
            ),
        },
        "salary_universe_query": _query_identity(
            job_id=f"{run_id}-salary-player-ids",
            table=SALARY_TABLE,
            sql_sha256=SALARY_SQL_SHA256,
            parameters_sha256=salary_params_sha,
            selected_columns=SALARY_SELECTED_COLUMNS,
        ),
        "universe_scope": authority.UNIVERSE_SCOPE,
        "uses_realized_outcomes": False,
    }
    registration = _self_hash(body, field="registration_sha256")
    try:
        return authority.validate_registration(registration)
    except authority.CorpusArtifactSourceAuthorityError as exc:
        raise CorpusArtifactSourcePreparationError(
            "pre-query registration failed pure validation"
        ) from exc


def _publication_uris(output_prefix: str) -> dict[str, str]:
    return {
        "prefix_claim": f"{output_prefix}governance/prefix-claim.json",
        "registration": f"{output_prefix}governance/source-registration.json",
        "r0_candidates": f"{output_prefix}queries/r0-candidates.json",
        "artifact_catalog": f"{output_prefix}queries/artifact-catalog.json",
        "salary_player_ids": f"{output_prefix}queries/salary-player-ids.json",
        "later_source_freeze": f"{output_prefix}source/later-source-freeze.json",
        "salary_diagnostic": f"{output_prefix}source/salary-diagnostic.json",
        "source_authority_completion": (
            f"{output_prefix}source/artifact-source-authority-completion.json"
        ),
        "publication_completion": (
            f"{output_prefix}governance/publication-completion.json"
        ),
    }


_PLAN_KEYS: Final = frozenset({
    "schema",
    "project",
    "location",
    "run_id",
    "registered_at",
    "source_snapshot_at",
    "output_prefix",
    "runtime_identity",
    "base_source_lock_object",
    "base_source_lock_artifact_manifest_sha256",
    "task_count",
    "artifact_count",
    "artifact_stream_order",
    "salary_sql_file",
    "salary_sql_sha256",
    "publication_uris",
    "publication_object_count",
    "registration",
    "create_once",
    "query_cache_allowed",
    "query_retry_allowed",
    "artifact_list_allowed",
    "outcome_columns_read",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "production_change_licensed",
    "plan_sha256",
})


def build_execution_plan(
    *,
    run_id: str,
    registered_at: str,
    source_snapshot_at: str,
    output_prefix: str,
    code_sha: str,
    image: str,
    job: str,
    base_source_lock_bytes: bytes,
) -> dict[str, object]:
    _salary_sql_bytes()
    source, receipts = validate_base_source_lock_bytes(base_source_lock_bytes)
    del source
    prefix = _gcs_prefix(output_prefix, label="output prefix")
    if _RUN_ID.fullmatch(run_id) is None or not prefix.endswith(f"/{run_id}/"):
        raise CorpusArtifactSourcePreparationError(
            "output prefix must end with exact source run ID"
        )
    if _CODE_SHA.fullmatch(code_sha) is None or _IMAGE.fullmatch(image) is None:
        raise CorpusArtifactSourcePreparationError(
            "immutable code/image identity differs"
        )
    runtime = {
        "run_id": run_id,
        "code_sha": code_sha,
        "image": image,
        "job": _string(job, label="runtime job"),
    }
    registration = build_registration(
        run_id=run_id,
        registered_at=registered_at,
        source_snapshot_at=source_snapshot_at,
    )
    body: dict[str, object] = {
        "schema": PLAN_SCHEMA,
        "project": PROJECT,
        "location": LOCATION,
        "run_id": run_id,
        "registered_at": registration["registered_at"],
        "source_snapshot_at": registration["source_snapshot_at"],
        "output_prefix": prefix,
        "runtime_identity": runtime,
        "base_source_lock_object": dict(BASE_SOURCE_OBJECT),
        "base_source_lock_artifact_manifest_sha256": canonical_sha256([
            {
                "season": row["season"],
                "week": row["week"],
                "block": row["block"],
                "uri": row["uri"],
                "generation": row["generation"],
                "sha256": row["sha256"],
                "bytes": row["bytes"],
            }
            for row in receipts
        ]),
        "task_count": authority.EXPECTED_TASK_COUNT,
        "artifact_count": authority.EXPECTED_ARTIFACT_COUNT,
        "artifact_stream_order": "task-index-major_then-r0-r1-r2-r3-r4",
        "salary_sql_file": SALARY_SQL_RELATIVE_PATH,
        "salary_sql_sha256": SALARY_SQL_SHA256,
        "publication_uris": _publication_uris(prefix),
        "publication_object_count": len(_publication_uris(prefix)),
        "registration": registration,
        "create_once": True,
        "query_cache_allowed": False,
        "query_retry_allowed": False,
        "artifact_list_allowed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    return validate_execution_plan(_self_hash(body, field="plan_sha256"))


def validate_execution_plan(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="source publication plan"))
    _exact_keys(item, _PLAN_KEYS, label="source publication plan")
    _validate_self_hash(
        item, field="plan_sha256", label="source publication plan"
    )
    if (
        item["schema"] != PLAN_SCHEMA
        or item["project"] != PROJECT
        or item["location"] != LOCATION
        or item["task_count"] != authority.EXPECTED_TASK_COUNT
        or item["artifact_count"] != authority.EXPECTED_ARTIFACT_COUNT
        or item["artifact_stream_order"]
        != "task-index-major_then-r0-r1-r2-r3-r4"
        or item["salary_sql_file"] != SALARY_SQL_RELATIVE_PATH
        or item["salary_sql_sha256"] != SALARY_SQL_SHA256
        or item["publication_object_count"] != 9
        or item["create_once"] is not True
        or item["query_cache_allowed"] is not False
        or item["query_retry_allowed"] is not False
        or item["artifact_list_allowed"] is not False
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
        or item["historical_scoring_licensed"] is not False
        or item["production_change_licensed"] is not False
    ):
        raise CorpusArtifactSourcePreparationError(
            "source publication plan authority differs"
        )
    _salary_sql_bytes()
    run_id = _string(item["run_id"], label="plan run ID")
    if _RUN_ID.fullmatch(run_id) is None:
        raise CorpusArtifactSourcePreparationError("plan run ID differs")
    registered_text, registered_dt = _timestamp(
        item["registered_at"], label="plan registration timestamp"
    )
    snapshot_text, snapshot_dt = _timestamp(
        item["source_snapshot_at"], label="plan source snapshot"
    )
    if registered_dt > snapshot_dt:
        raise CorpusArtifactSourcePreparationError(
            "plan registration follows source snapshot"
        )
    prefix = _gcs_prefix(item["output_prefix"], label="plan output prefix")
    if not prefix.endswith(f"/{run_id}/"):
        raise CorpusArtifactSourcePreparationError(
            "plan output prefix/run ID differ"
        )
    if item["publication_uris"] != _publication_uris(prefix):
        raise CorpusArtifactSourcePreparationError(
            "plan deterministic publication URIs differ"
        )
    if normalize_object_identity(
        item["base_source_lock_object"], label="plan base source lock"
    ) != BASE_SOURCE_OBJECT:
        raise CorpusArtifactSourcePreparationError(
            "plan base source-lock identity differs"
        )
    _sha(
        item["base_source_lock_artifact_manifest_sha256"],
        label="plan artifact-manifest SHA",
    )
    runtime = _mapping(item["runtime_identity"], label="plan runtime identity")
    _exact_keys(
        runtime,
        frozenset({"run_id", "code_sha", "image", "job"}),
        label="plan runtime identity",
    )
    if (
        runtime["run_id"] != run_id
        or _CODE_SHA.fullmatch(str(runtime["code_sha"])) is None
        or _IMAGE.fullmatch(str(runtime["image"])) is None
    ):
        raise CorpusArtifactSourcePreparationError(
            "plan runtime identity differs"
        )
    _string(runtime["job"], label="plan runtime job")
    try:
        registration = authority.validate_registration(item["registration"])
    except authority.CorpusArtifactSourceAuthorityError as exc:
        raise CorpusArtifactSourcePreparationError(
            "plan registration differs"
        ) from exc
    if (
        registration["source_run_id"] != run_id
        or registration["registered_at"] != registered_text
        or registration["source_snapshot_at"] != snapshot_text
    ):
        raise CorpusArtifactSourcePreparationError(
            "plan registration binding differs"
        )
    job_ids = [
        registration["source_queries"]["r0_candidates"]["job_id"],
        registration["source_queries"]["artifact_catalog"]["job_id"],
        registration["salary_universe_query"]["job_id"],
    ]
    if len(set(job_ids)) != len(QUERY_ROLES):
        raise CorpusArtifactSourcePreparationError(
            "plan query job IDs repeat"
        )
    item["registration"] = registration
    return item


def build_prefix_claim(plan: Mapping[str, object]) -> dict[str, object]:
    normalized = validate_execution_plan(plan)
    body = {
        "schema": PREFIX_CLAIM_SCHEMA,
        "run_id": normalized["run_id"],
        "plan_sha256": normalized["plan_sha256"],
        "output_prefix": normalized["output_prefix"],
        "publication_uris": normalized["publication_uris"],
        "base_source_lock_object": normalized["base_source_lock_object"],
        "source_snapshot_at": normalized["source_snapshot_at"],
        "registration_sha256": normalized["registration"][
            "registration_sha256"
        ],
        "create_once": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    return _self_hash(body, field="claim_sha256")


def _json_query_value(value: object, *, label: str) -> object:
    if value is None or type(value) in {str, bool, int}:
        return value
    if isinstance(value, Decimal):
        if not value.is_finite() or value != value.to_integral_value():
            raise CorpusArtifactSourcePreparationError(
                f"{label} contains a nonintegral decimal"
            )
        return int(value)
    if type(value) is float:
        if not math.isfinite(value):
            raise CorpusArtifactSourcePreparationError(
                f"{label} contains a non-finite float"
            )
        return value
    if isinstance(value, datetime):
        if value.tzinfo is None or value.utcoffset() is None:
            raise CorpusArtifactSourcePreparationError(
                f"{label} contains a naive timestamp"
            )
        return value.astimezone(timezone.utc).isoformat()
    if isinstance(value, Mapping):
        return {
            _string(key, label=f"{label} key"): _json_query_value(
                item, label=f"{label}.{key}"
            )
            for key, item in value.items()
        }
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return [
            _json_query_value(item, label=f"{label}[{index}]")
            for index, item in enumerate(value)
        ]
    raise CorpusArtifactSourcePreparationError(
        f"{label} contains an unsupported query value"
    )


def _normalize_query_row(
    role: str, value: Mapping[str, object], *, index: int,
) -> dict[str, object]:
    row = {
        key: _json_query_value(item, label=f"{role} row[{index}].{key}")
        for key, item in value.items()
    }
    expected_fields = {
        "r0_candidates": later.R0_CANDIDATE_FIELDS,
        "artifact_catalog": later.CATALOG_FIELDS,
        "salary_player_ids": frozenset({"season", "week", "id"}),
    }.get(role)
    if expected_fields is None or set(row) != set(expected_fields):
        raise CorpusArtifactSourcePreparationError(
            f"{role} row[{index}] fields differ"
        )
    for key in row:
        lowered = key.lower()
        if any(fragment in lowered for fragment in _FORBIDDEN_OUTCOME_FRAGMENTS):
            raise CorpusArtifactSourcePreparationError(
                f"{role} row[{index}] exposes an outcome field"
            )
    season = row.get("season")
    week = row.get("week")
    if type(season) is not int or type(week) is not int:
        raise CorpusArtifactSourcePreparationError(
            f"{role} row[{index}] slate identity differs"
        )
    if (season, week) not in set(later.EXPECTED_SLATE_KEYS):
        raise CorpusArtifactSourcePreparationError(
            f"{role} row[{index}] slate is outside the frozen lattice"
        )
    if role == "r0_candidates":
        if (
            type(row["cand_ix"]) is not int
            or type(row["players"]) is not list
            or any(type(player) is not str or not player for player in row["players"])
            or row["panel_run_id"] != later.R0_PANEL
            or type(row["score_artifact_uri"]) is not str
            or not str(row["score_artifact_uri"]).startswith("gs://")
            or _SHA256.fullmatch(str(row["score_artifact_sha256"])) is None
        ):
            raise CorpusArtifactSourcePreparationError(
                f"{role} row[{index}] candidate identity differs"
            )
    elif role == "artifact_catalog":
        for key in ("id", "pos", "team", "opp", "game_id"):
            _string(row[key], label=f"{role} row[{index}].{key}")
        salary = row["salary"]
        if type(salary) is float and salary.is_integer():
            row["salary"] = int(salary)
        if type(row["salary"]) is not int or int(row["salary"]) <= 0:
            raise CorpusArtifactSourcePreparationError(
                f"{role} row[{index}] salary differs"
            )
    else:
        _string(row["id"], label=f"{role} row[{index}].id")
    return row


def normalize_query_rows(
    role: str, rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], ...]:
    if type(rows) not in {list, tuple}:
        raise CorpusArtifactSourcePreparationError(
            f"{role} query rows must be one ordered sequence"
        )
    normalized = tuple(
        _normalize_query_row(role, row, index=index)
        for index, row in enumerate(rows)
    )
    if not normalized:
        raise CorpusArtifactSourcePreparationError(f"{role} query is empty")
    if role == "r0_candidates":
        keys = tuple(
            (row["season"], row["week"], row["cand_ix"])
            for row in normalized
        )
    else:
        keys = tuple(
            (row["season"], row["week"], row["id"])
            for row in normalized
        )
    if keys != tuple(sorted(keys)) or len(keys) != len(set(keys)):
        raise CorpusArtifactSourcePreparationError(
            f"{role} query row order/uniqueness differs"
        )
    observed_slates = {(int(row["season"]), int(row["week"])) for row in normalized}
    if observed_slates != set(later.EXPECTED_SLATE_KEYS):
        raise CorpusArtifactSourcePreparationError(
            f"{role} query does not cover the exact 54 slates"
        )
    return normalized


def _normalize_query_receipt(
    value: object,
    *,
    query_identity: Mapping[str, object],
    registered_at: str,
) -> dict[str, object]:
    try:
        receipt = authority._query_receipt(  # noqa: SLF001
            value, label="query execution receipt"
        )
    except authority.CorpusArtifactSourceAuthorityError as exc:
        raise CorpusArtifactSourcePreparationError(
            "query execution receipt differs"
        ) from exc
    if any(
        receipt[key] != query_identity[key]
        for key in ("job_id", "location", "sql_sha256", "parameters_sha256")
    ):
        raise CorpusArtifactSourcePreparationError(
            "query receipt differs from pre-query registration"
        )
    registered_dt = _timestamp(registered_at, label="registration timestamp")[1]
    created_dt = _timestamp(receipt["created"], label="query created")[1]
    if created_dt < registered_dt:
        raise CorpusArtifactSourcePreparationError(
            "query job predates its registration"
        )
    return receipt


def build_query_capture(
    *,
    role: str,
    query_identity: Mapping[str, object],
    query_outcome: QueryOutcome,
    registered_at: str,
) -> dict[str, object]:
    if role not in QUERY_ROLES:
        raise CorpusArtifactSourcePreparationError("query capture role differs")
    rows = normalize_query_rows(role, query_outcome.rows)
    receipt = _normalize_query_receipt(
        query_outcome.receipt,
        query_identity=query_identity,
        registered_at=registered_at,
    )
    body = {
        "schema": QUERY_CAPTURE_SCHEMA,
        "role": role,
        "query_identity": dict(query_identity),
        "query_receipt": receipt,
        "row_count": len(rows),
        "row_order": QUERY_ROW_ORDERS[role],
        "rows_sha256": canonical_sha256(list(rows)),
        "rows": list(rows),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, field="capture_sha256")


def validate_query_capture(
    value: object,
    *,
    role: str,
    query_identity: Mapping[str, object],
    registered_at: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label=f"{role} query capture"))
    _exact_keys(item, frozenset({
        "schema", "role", "query_identity", "query_receipt", "row_count",
        "row_order", "rows_sha256", "rows", "outcome_columns_read",
        "uses_realized_outcomes", "capture_sha256",
    }), label=f"{role} query capture")
    _validate_self_hash(
        item, field="capture_sha256", label=f"{role} query capture"
    )
    if (
        item["schema"] != QUERY_CAPTURE_SCHEMA
        or item["role"] != role
        or item["query_identity"] != query_identity
        or item["row_order"] != QUERY_ROW_ORDERS[role]
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
    ):
        raise CorpusArtifactSourcePreparationError(
            f"{role} query capture authority differs"
        )
    rows = normalize_query_rows(
        role,
        tuple(
            _mapping(row, label=f"{role} retained row")
            for row in _sequence(item["rows"], label=f"{role} rows")
        ),
    )
    if (
        item["row_count"] != len(rows)
        or item["rows_sha256"] != canonical_sha256(list(rows))
    ):
        raise CorpusArtifactSourcePreparationError(
            f"{role} retained row digest differs"
        )
    item["query_receipt"] = _normalize_query_receipt(
        item["query_receipt"],
        query_identity=query_identity,
        registered_at=registered_at,
    )
    item["rows"] = list(rows)
    return item


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if type(value) is not list:
        raise CorpusArtifactSourcePreparationError(f"{label} must be an array")
    return value


def build_salary_diagnostic(
    *,
    registration: Mapping[str, object],
    salary_capture: Mapping[str, object],
) -> dict[str, object]:
    registered = authority.validate_registration(registration)
    query_identity = registered["salary_universe_query"]
    capture = validate_query_capture(
        salary_capture,
        role="salary_player_ids",
        query_identity=query_identity,
        registered_at=str(registered["registered_at"]),
    )
    by_slate: dict[tuple[int, int], list[str]] = {
        key: [] for key in later.EXPECTED_SLATE_KEYS
    }
    for row in capture["rows"]:
        by_slate[(int(row["season"]), int(row["week"]))].append(str(row["id"]))
    slates = []
    for task_index, (season, week) in enumerate(later.EXPECTED_SLATE_KEYS):
        ids = by_slate[(season, week)]
        if not ids or ids != sorted(set(ids)):
            raise CorpusArtifactSourcePreparationError(
                f"salary query slate[{task_index}] IDs differ"
            )
        slates.append({
            "task_index": task_index,
            "season": season,
            "week": week,
            "slate_id": f"{season}-w{week:02d}",
            "salary_player_ids": ids,
            "salary_player_ids_sha256": authority.canonical_sha256(ids),
        })
    body = {
        "schema": authority.SALARY_DIAGNOSTIC_SCHEMA,
        "registration_sha256": registered["registration_sha256"],
        "universe_scope": authority.SALARY_DIAGNOSTIC_SCOPE,
        "query": {
            "source_snapshot_at": registered["source_snapshot_at"],
            "table": query_identity["table"],
            "query_receipt": capture["query_receipt"],
            "selected_columns": query_identity["selected_columns"],
            "realized_columns_selected": [],
        },
        "slate_count": authority.EXPECTED_TASK_COUNT,
        "slates": slates,
        "coverage_only": True,
        "world_draws_attached": False,
        "coverage_is_predeclared_query_relative": True,
        "query_result_independently_verified": False,
        "complete_dk_salary_coverage_claimed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, field="diagnostic_sha256")


def _artifact_body_stream(
    *,
    source_freeze: Mapping[str, object],
    storage: StorageBoundary,
) -> Iterator[authority.RetainedArtifactBody]:
    slates = _sequence(source_freeze.get("slates"), label="source-freeze slates")
    for task_index, raw_slate in enumerate(slates):
        slate = _mapping(raw_slate, label=f"source-freeze slate[{task_index}]")
        receipts = _sequence(
            slate.get("artifact_receipts"),
            label=f"source-freeze slate[{task_index}] artifacts",
        )
        for role, raw_receipt in zip(
            TASK_WORLD_SOURCE_ROLES, receipts, strict=True
        ):
            receipt = _mapping(
                raw_receipt,
                label=f"source-freeze task[{task_index}] {role}",
            )
            identity = normalize_object_identity({
                key: receipt[key]
                for key in ("uri", "generation", "sha256", "bytes")
            }, label=f"task[{task_index}] {role} object")
            raw = storage.read(identity)
            yield authority.RetainedArtifactBody(
                task_index=task_index,
                role=role,
                identity=identity,
                raw=raw,
            )


def _inventory_rows(
    identities: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    rows = [
        {
            "uri": identity["uri"],
            "generation": identity["generation"],
            "bytes": identity["bytes"],
        }
        for identity in identities
    ]
    return sorted(rows, key=lambda row: (str(row["uri"]), str(row["generation"])))


def _reopen_exact_publications(
    storage: StorageBoundary,
    publications: Sequence[tuple[Mapping[str, object], bytes]],
) -> None:
    """Reopen a closed set by exact name and generation; never enumerate it."""
    for ordinal, (identity, expected_raw) in enumerate(publications):
        normalized = normalize_object_identity(
            identity, label=f"publication[{ordinal}] identity"
        )
        observed_raw = storage.read(normalized)
        if observed_raw != expected_raw:
            raise CorpusArtifactSourcePreparationError(
                f"publication[{ordinal}] did not reopen byte-identically"
            )


def _query_identities(
    registration: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    return {
        "r0_candidates": registration["source_queries"]["r0_candidates"],
        "artifact_catalog": registration["source_queries"]["artifact_catalog"],
        "salary_player_ids": registration["salary_universe_query"],
    }


def _query_specs(
    registration: Mapping[str, object],
) -> dict[str, tuple[str, list[dict[str, object]]]]:
    snapshot = str(registration["source_snapshot_at"])
    return {
        "r0_candidates": (
            later.CANDIDATE_SQL,
            later.source_parameter_payload(snapshot),
        ),
        "artifact_catalog": (
            later.CATALOG_SQL,
            later.source_parameter_payload(snapshot),
        ),
        "salary_player_ids": (
            _salary_sql_bytes().decode("utf-8"),
            salary_parameter_payload(snapshot),
        ),
    }


def validate_producer_get_trace(
    value: object,
    *,
    delivered_plan_identity: Mapping[str, object] | None,
    delivered_intent_identity: Mapping[str, object] | None,
    plan: Mapping[str, object],
    artifact_receipts: Sequence[Mapping[str, object]],
    publication_identities: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Replay the complete producer GET sequence before terminal publication."""
    item = dict(_mapping(value, label="producer GET trace"))
    _exact_keys(
        item,
        frozenset({
            "schema", "delivered_plan_object", "delivered_intent_object",
            "events", "event_count", "events_sha256", "absence_check_uris",
            "object_list_used", "complete", "trace_sha256",
        }),
        label="producer GET trace",
    )
    _validate_self_hash(item, field="trace_sha256", label="producer GET trace")
    frozen_plan = validate_execution_plan(plan)
    expected_plan = (
        None
        if delivered_plan_identity is None
        else normalize_object_identity(
            delivered_plan_identity, label="expected delivered plan"
        )
    )
    expected_intent = (
        None
        if delivered_intent_identity is None
        else normalize_object_identity(
            delivered_intent_identity, label="expected delivered intent"
        )
    )
    roles_before_terminal = (
        "prefix_claim", "registration", *QUERY_ROLES,
        "later_source_freeze", "salary_diagnostic",
        "source_authority_completion",
    )
    retained_publications = {
        role: normalize_object_identity(
            publication_identities[role], label=f"producer trace {role}"
        )
        for role in roles_before_terminal
    }
    artifact_identities = [
        normalize_object_identity(
            {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")},
            label=f"producer trace artifact[{ordinal}]",
        )
        for ordinal, receipt in enumerate(artifact_receipts)
    ]
    if len(artifact_identities) != authority.EXPECTED_ARTIFACT_COUNT:
        raise CorpusArtifactSourcePreparationError(
            "producer trace artifact authority is incomplete"
        )
    expected_sequence = [
        *([] if expected_plan is None else [expected_plan]),
        *([] if expected_intent is None else [expected_intent]),
        normalize_object_identity(
            frozen_plan["base_source_lock_object"], label="producer trace base lock"
        ),
        retained_publications["prefix_claim"],
        retained_publications["registration"],
        *(retained_publications[role] for role in QUERY_ROLES),
        retained_publications["later_source_freeze"],
        retained_publications["salary_diagnostic"],
        *artifact_identities,
        retained_publications["source_authority_completion"],
        *(retained_publications[role] for role in roles_before_terminal),
    ]
    raw_events = _sequence(item["events"], label="producer GET events")
    events: list[dict[str, object]] = []
    for ordinal, raw in enumerate(raw_events):
        event = dict(_mapping(raw, label=f"producer GET event[{ordinal}]"))
        _exact_keys(
            event, frozenset({"ordinal", "identity"}),
            label=f"producer GET event[{ordinal}]",
        )
        identity = normalize_object_identity(
            event["identity"], label=f"producer GET event[{ordinal}] identity"
        )
        if event["ordinal"] != ordinal:
            raise CorpusArtifactSourcePreparationError(
                "producer GET trace ordinal differs"
            )
        events.append({"ordinal": ordinal, "identity": identity})
    if (
        item["schema"] != PRODUCER_GET_TRACE_SCHEMA
        or item["delivered_plan_object"] != expected_plan
        or item["delivered_intent_object"] != expected_intent
        or [event["identity"] for event in events] != expected_sequence
        or item["event_count"] != len(expected_sequence)
        or item["events_sha256"] != canonical_sha256(events)
        or item["absence_check_uris"]
        != list(_publication_uris(str(frozen_plan["output_prefix"])).values())
        or item["object_list_used"] is not False
        or item["complete"] is not True
    ):
        raise CorpusArtifactSourcePreparationError(
            "producer GET trace is incomplete, extra, or reordered"
        )
    item["events"] = events
    return item


def validate_producer_query_trace(
    value: object,
    *,
    registration: Mapping[str, object],
    captures: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Replay the exact absence-check and fixed-query call sequence."""
    item = dict(_mapping(value, label="producer query trace"))
    _exact_keys(
        item,
        frozenset({
            "schema", "events", "event_count", "events_sha256", "complete",
            "trace_sha256",
        }),
        label="producer query trace",
    )
    _validate_self_hash(
        item, field="trace_sha256", label="producer query trace"
    )
    identities = _query_identities(registration)
    specs = _query_specs(registration)
    expected: list[dict[str, object]] = []
    for role in QUERY_ROLES:
        expected.append({
            "ordinal": len(expected),
            "operation": "require-unused-job-id",
            "job_id": identities[role]["job_id"],
        })
    for role in QUERY_ROLES:
        sql, parameters = specs[role]
        capture = _mapping(captures[role], label=f"query trace {role} capture")
        receipt = _mapping(
            capture["query_receipt"], label=f"query trace {role} receipt"
        )
        expected.append({
            "ordinal": len(expected),
            "operation": "run-query",
            "role": role,
            "job_id": identities[role]["job_id"],
            "sql_sha256": sha256(sql.encode("utf-8")).hexdigest(),
            "parameters_sha256": canonical_sha256(list(parameters)),
            "receipt_sha256": canonical_sha256(dict(receipt)),
        })
    events = [
        dict(_mapping(raw, label=f"producer query event[{ordinal}]"))
        for ordinal, raw in enumerate(
            _sequence(item["events"], label="producer query events")
        )
    ]
    if (
        item["schema"] != PRODUCER_QUERY_TRACE_SCHEMA
        or events != expected
        or item["event_count"] != len(expected)
        or item["events_sha256"] != canonical_sha256(expected)
        or item["complete"] is not True
    ):
        raise CorpusArtifactSourcePreparationError(
            "producer query trace is incomplete, extra, or reordered"
        )
    item["events"] = events
    return item


def _build_publication_completion(
    *,
    plan: Mapping[str, object],
    claim_identity: Mapping[str, object],
    registration_identity: Mapping[str, object],
    capture_identities: Mapping[str, Mapping[str, object]],
    captures: Mapping[str, Mapping[str, object]],
    source_identity: Mapping[str, object],
    source_freeze: Mapping[str, object],
    salary_identity: Mapping[str, object],
    salary_diagnostic: Mapping[str, object],
    completion_identity: Mapping[str, object],
    completion: Mapping[str, object],
    inventory_before_publication: Sequence[Mapping[str, object]],
    producer_get_trace: Mapping[str, object],
    producer_query_trace: Mapping[str, object],
) -> dict[str, object]:
    body = {
        "schema": PUBLICATION_COMPLETION_SCHEMA,
        "run_id": plan["run_id"],
        "plan_sha256": plan["plan_sha256"],
        "output_prefix": plan["output_prefix"],
        "prefix_claim": dict(claim_identity),
        "registration_object": dict(registration_identity),
        "registration_sha256": plan["registration"]["registration_sha256"],
        "query_captures": {
            role: {
                "object": dict(capture_identities[role]),
                "job_id": captures[role]["query_receipt"]["job_id"],
                "row_count": captures[role]["row_count"],
                "rows_sha256": captures[role]["rows_sha256"],
                "capture_sha256": captures[role]["capture_sha256"],
            }
            for role in QUERY_ROLES
        },
        "later_source_freeze_object": dict(source_identity),
        "later_source_freeze_manifest_sha256": source_freeze["freeze_sha256"],
        "salary_diagnostic_object": dict(salary_identity),
        "salary_diagnostic_sha256": salary_diagnostic["diagnostic_sha256"],
        "source_authority_completion_object": dict(completion_identity),
        "source_authority_completion_sha256": completion["completion_sha256"],
        "base_source_lock_object": plan["base_source_lock_object"],
        "task_count": authority.EXPECTED_TASK_COUNT,
        "artifact_count": authority.EXPECTED_ARTIFACT_COUNT,
        "artifact_reads": "exact-generation-get-only-one-at-a-time",
        "artifact_list_used": False,
        "producer_get_trace": dict(producer_get_trace),
        "producer_query_trace": dict(producer_query_trace),
        "producer_trace_complete_before_terminal_publication": True,
        "inventory_before_publication": list(inventory_before_publication),
        "inventory_before_publication_sha256": canonical_sha256(
            list(inventory_before_publication)
        ),
        "create_once": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "live_strategy_authority": False,
    }
    return _self_hash(body, field="publication_completion_sha256")


def _validate_trace_envelope(
    value: object, *, schema: str, label: str
) -> dict[str, object]:
    item = dict(_mapping(value, label=label))
    expected_keys = (
        frozenset({
            "schema", "delivered_plan_object", "delivered_intent_object",
            "events", "event_count", "events_sha256", "absence_check_uris",
            "object_list_used", "complete", "trace_sha256",
        })
        if schema == PRODUCER_GET_TRACE_SCHEMA
        else frozenset({
            "schema", "events", "event_count", "events_sha256", "complete",
            "trace_sha256",
        })
    )
    _exact_keys(item, expected_keys, label=label)
    _validate_self_hash(item, field="trace_sha256", label=label)
    events = list(_sequence(item["events"], label=f"{label} events"))
    if (
        item["schema"] != schema
        or item["event_count"] != len(events)
        or item["events_sha256"] != canonical_sha256(events)
        or item["complete"] is not True
    ):
        raise CorpusArtifactSourcePreparationError(f"{label} envelope differs")
    return item


def validate_publication_completion_bytes(raw: bytes) -> dict[str, object]:
    """Validate the canonical terminal transport publication, without clients."""
    item = dict(_mapping(
        parse_canonical_json_bytes(raw, label="source publication completion"),
        label="source publication completion",
    ))
    _exact_keys(
        item,
        _PUBLICATION_COMPLETION_KEYS,
        label="source publication completion",
    )
    _validate_self_hash(
        item,
        field="publication_completion_sha256",
        label="source publication completion",
    )
    run_id = _string(item["run_id"], label="publication run ID")
    prefix = _gcs_prefix(
        item["output_prefix"], label="publication output prefix"
    )
    if _RUN_ID.fullmatch(run_id) is None or not prefix.endswith(f"/{run_id}/"):
        raise CorpusArtifactSourcePreparationError(
            "publication run ID/output prefix differs"
        )
    uris = _publication_uris(prefix)
    if (
        item["schema"] != PUBLICATION_COMPLETION_SCHEMA
        or item["task_count"] != authority.EXPECTED_TASK_COUNT
        or item["artifact_count"] != authority.EXPECTED_ARTIFACT_COUNT
        or item["artifact_reads"]
        != "exact-generation-get-only-one-at-a-time"
        or item["artifact_list_used"] is not False
        or item["producer_trace_complete_before_terminal_publication"] is not True
        or item["create_once"] is not True
        or item["outcome_columns_read"] != []
        or item["uses_realized_outcomes"] is not False
        or item["historical_scoring_licensed"] is not False
        or item["production_change_licensed"] is not False
        or item["live_strategy_authority"] is not False
    ):
        raise CorpusArtifactSourcePreparationError(
            "source publication completion authority differs"
        )
    item["producer_get_trace"] = _validate_trace_envelope(
        item["producer_get_trace"],
        schema=PRODUCER_GET_TRACE_SCHEMA,
        label="producer GET trace",
    )
    item["producer_query_trace"] = _validate_trace_envelope(
        item["producer_query_trace"],
        schema=PRODUCER_QUERY_TRACE_SCHEMA,
        label="producer query trace",
    )
    _sha(item["plan_sha256"], label="publication plan SHA")
    registration_sha = _sha(
        item["registration_sha256"], label="publication registration SHA"
    )
    source_manifest_sha = _sha(
        item["later_source_freeze_manifest_sha256"],
        label="publication later-source manifest SHA",
    )
    salary_sha = _sha(
        item["salary_diagnostic_sha256"],
        label="publication salary diagnostic SHA",
    )
    completion_sha = _sha(
        item["source_authority_completion_sha256"],
        label="publication source-authority completion SHA",
    )
    del source_manifest_sha, salary_sha
    base_identity = normalize_object_identity(
        item["base_source_lock_object"],
        label="publication base source lock",
    )
    if base_identity != BASE_SOURCE_OBJECT:
        raise CorpusArtifactSourcePreparationError(
            "publication base source-lock identity differs"
        )

    expected_objects: list[dict[str, object]] = []
    direct_objects = {
        "prefix_claim": "prefix_claim",
        "registration_object": "registration",
        "later_source_freeze_object": "later_source_freeze",
        "salary_diagnostic_object": "salary_diagnostic",
        "source_authority_completion_object": "source_authority_completion",
    }
    normalized_direct: dict[str, dict[str, object]] = {}
    for field, uri_role in direct_objects.items():
        identity = normalize_object_identity(
            item[field], label=f"publication {field}"
        )
        if identity["uri"] != uris[uri_role]:
            raise CorpusArtifactSourcePreparationError(
                f"publication {field} URI differs"
            )
        normalized_direct[field] = identity
        expected_objects.append(identity)
    if (
        normalized_direct["registration_object"]["sha256"] == registration_sha
        or normalized_direct["source_authority_completion_object"]["sha256"]
        == completion_sha
    ):
        raise CorpusArtifactSourcePreparationError(
            "publication object/internal hashes are conflated"
        )

    captures = _mapping(
        item["query_captures"], label="publication query captures"
    )
    _exact_keys(captures, frozenset(QUERY_ROLES), label="publication captures")
    normalized_captures: dict[str, dict[str, object]] = {}
    expected_job_ids = {
        "r0_candidates": f"{run_id}-r0-candidates",
        "artifact_catalog": f"{run_id}-full-catalog",
        "salary_player_ids": f"{run_id}-salary-player-ids",
    }
    for role in QUERY_ROLES:
        capture = dict(_mapping(captures[role], label=f"publication {role}"))
        _exact_keys(
            capture,
            _CAPTURE_PUBLICATION_KEYS,
            label=f"publication {role}",
        )
        identity = normalize_object_identity(
            capture["object"], label=f"publication {role} object"
        )
        if (
            identity["uri"] != uris[role]
            or capture["job_id"] != expected_job_ids[role]
            or _exact_int(
                capture["row_count"],
                label=f"publication {role} row count",
                minimum=authority.EXPECTED_TASK_COUNT,
            ) < authority.EXPECTED_TASK_COUNT
        ):
            raise CorpusArtifactSourcePreparationError(
                f"publication {role} query binding differs"
            )
        rows_sha = _sha(
            capture["rows_sha256"], label=f"publication {role} rows SHA"
        )
        capture_sha = _sha(
            capture["capture_sha256"],
            label=f"publication {role} capture SHA",
        )
        if identity["sha256"] in {rows_sha, capture_sha}:
            raise CorpusArtifactSourcePreparationError(
                f"publication {role} object/internal hashes are conflated"
            )
        capture["object"] = identity
        normalized_captures[role] = capture
        expected_objects.append(identity)

    inventory = [
        dict(_mapping(row, label="publication inventory row"))
        for row in _sequence(
            item["inventory_before_publication"],
            label="publication inventory",
        )
    ]
    expected_inventory = _inventory_rows(expected_objects)
    if (
        inventory != expected_inventory
        or item["inventory_before_publication_sha256"]
        != canonical_sha256(expected_inventory)
    ):
        raise CorpusArtifactSourcePreparationError(
            "publication exact-name object manifest differs"
        )
    item.update(normalized_direct)
    item["base_source_lock_object"] = base_identity
    item["query_captures"] = normalized_captures
    item["inventory_before_publication"] = inventory
    return item


def execute_authority(
    *,
    plan: object,
    execute: bool,
    environ: Mapping[str, str],
    storage_factory: Callable[[], StorageBoundary],
    query_factory: Callable[[], QueryBoundary],
) -> dict[str, object]:
    """Execute one create-once authority publication without retry."""
    require_execute_gate(execute=execute, environ=environ)
    frozen_plan = validate_execution_plan(plan)

    # Source and namespace validity are proven before the first publication.
    raw_storage = storage_factory()
    storage = (
        raw_storage
        if isinstance(raw_storage, _TracingStorageBoundary)
        else _TracingStorageBoundary(raw_storage)
    )
    storage.configure_plan(frozen_plan)
    base_identity = normalize_object_identity(
        frozen_plan["base_source_lock_object"], label="base source lock"
    )
    base_raw = storage.read(base_identity)
    base_source, base_receipts = validate_base_source_lock_bytes(
        base_raw, identity=base_identity
    )
    expected_manifest_sha = canonical_sha256([
        {
            "season": row["season"],
            "week": row["week"],
            "block": row["block"],
            "uri": row["uri"],
            "generation": row["generation"],
            "sha256": row["sha256"],
            "bytes": row["bytes"],
        }
        for row in base_receipts
    ])
    if expected_manifest_sha != frozen_plan[
        "base_source_lock_artifact_manifest_sha256"
    ]:
        raise CorpusArtifactSourcePreparationError(
            "base source-lock artifact manifest differs from plan"
        )
    storage.authorize_artifacts(base_receipts)
    prefix = str(frozen_plan["output_prefix"])
    uris = frozen_plan["publication_uris"]
    storage.require_absent([str(uris[key]) for key in _publication_uris(prefix)])
    claim_raw = canonical_json_bytes(build_prefix_claim(frozen_plan))
    claim_identity = normalize_object_identity(
        storage.publish(str(uris["prefix_claim"]), claim_raw),
        label="published prefix claim",
    )
    if storage.read(claim_identity) != claim_raw:
        raise CorpusArtifactSourcePreparationError(
            "published prefix claim did not reopen byte-identically"
        )
    registration = frozen_plan["registration"]
    registration_raw = authority.canonical_json_bytes(registration)
    registration_identity = normalize_object_identity(
        storage.publish(str(uris["registration"]), registration_raw),
        label="published registration",
    )
    if storage.read(registration_identity) != registration_raw:
        raise CorpusArtifactSourcePreparationError(
            "published registration did not reopen byte-identically"
        )

    # Constructing the query client and every query operation happens only
    # after the generation-pinned registration has been published/reopened.
    query_boundary = _TracingQueryBoundary(
        query_factory(), registration=registration
    )
    query_identities = _query_identities(registration)
    job_ids = [str(query_identities[role]["job_id"]) for role in QUERY_ROLES]
    query_boundary.require_unused_job_ids(job_ids)
    query_specs = _query_specs(registration)
    captures: dict[str, dict[str, object]] = {}
    capture_identities: dict[str, dict[str, object]] = {}
    capture_raws: dict[str, bytes] = {}
    for role in QUERY_ROLES:
        sql, parameters = query_specs[role]
        outcome = query_boundary.run_query(
            sql=sql,
            query_identity=query_identities[role],
            parameters=parameters,
        )
        capture = build_query_capture(
            role=role,
            query_identity=query_identities[role],
            query_outcome=outcome,
            registered_at=str(registration["registered_at"]),
        )
        capture_raw = canonical_json_bytes(capture)
        capture_identity = normalize_object_identity(
            storage.publish(str(uris[role]), capture_raw),
            label=f"published {role} capture",
        )
        if storage.read(capture_identity) != capture_raw:
            raise CorpusArtifactSourcePreparationError(
                f"published {role} capture did not reopen byte-identically"
            )
        captures[role] = capture
        capture_identities[role] = capture_identity
        capture_raws[role] = capture_raw

    try:
        source_freeze = later.build_source_freeze(
            base_source_lock=base_source,
            base_source_lock_object=base_identity,
            base_source_lock_sha256=str(base_identity["sha256"]),
            r0_candidate_rows=captures["r0_candidates"]["rows"],
            full_catalog_rows=captures["artifact_catalog"]["rows"],
            query_provenance={
                "candidate_query": captures["r0_candidates"]["query_receipt"],
                "catalog_query": captures["artifact_catalog"]["query_receipt"],
                "candidate_table": later.CANDIDATE_TABLE,
                "catalog_table": later.CATALOG_TABLE,
                "source_snapshot_at": registration["source_snapshot_at"],
            },
            runtime_identity=frozen_plan["runtime_identity"],
        )
    except later.LR8LaterSourceError as exc:
        raise CorpusArtifactSourcePreparationError(
            "later-source freeze construction failed"
        ) from exc
    source_raw = later.canonical_json(source_freeze)
    source_identity = normalize_object_identity(
        storage.publish(str(uris["later_source_freeze"]), source_raw),
        label="published later-source freeze",
    )
    if storage.read(source_identity) != source_raw:
        raise CorpusArtifactSourcePreparationError(
            "published later-source freeze did not reopen byte-identically"
        )
    salary_diagnostic = build_salary_diagnostic(
        registration=registration,
        salary_capture=captures["salary_player_ids"],
    )
    salary_raw = authority.canonical_json_bytes(salary_diagnostic)
    salary_identity = normalize_object_identity(
        storage.publish(str(uris["salary_diagnostic"]), salary_raw),
        label="published salary diagnostic",
    )
    if storage.read(salary_identity) != salary_raw:
        raise CorpusArtifactSourcePreparationError(
            "published salary diagnostic did not reopen byte-identically"
        )

    try:
        completion_raw = authority.verify_artifact_supported_source_authority(
            later_source_freeze_bytes=source_raw,
            later_source_freeze_object=source_identity,
            registration_bytes=registration_raw,
            registration_object=registration_identity,
            salary_diagnostic_bytes=salary_raw,
            salary_diagnostic_object=salary_identity,
            artifact_bodies=_artifact_body_stream(
                source_freeze=source_freeze,
                storage=storage,
            ),
        )
        completion = authority.validate_completion_bytes(completion_raw)
    except authority.CorpusArtifactSourceAuthorityError as exc:
        raise CorpusArtifactSourcePreparationError(
            "pure artifact-source authority verification failed"
        ) from exc
    completion_identity = normalize_object_identity(
        storage.publish(
            str(uris["source_authority_completion"]), completion_raw
        ),
        label="published source-authority completion",
    )
    if storage.read(completion_identity) != completion_raw:
        raise CorpusArtifactSourcePreparationError(
            "published source-authority completion did not reopen byte-identically"
        )

    before_publications = [
        (claim_identity, claim_raw),
        (registration_identity, registration_raw),
        *(
            (capture_identities[role], capture_raws[role])
            for role in QUERY_ROLES
        ),
        (source_identity, source_raw),
        (salary_identity, salary_raw),
        (completion_identity, completion_raw),
    ]
    _reopen_exact_publications(storage, before_publications)
    before_publication_identities = [row[0] for row in before_publications]
    expected_before = _inventory_rows(before_publication_identities)
    producer_get_trace = storage.seal_trace()
    producer_query_trace = query_boundary.seal_trace()
    validate_producer_get_trace(
        producer_get_trace,
        delivered_plan_identity=storage.delivered_plan_identity,
        delivered_intent_identity=storage.delivered_intent_identity,
        plan=frozen_plan,
        artifact_receipts=base_receipts,
        publication_identities={
            role: identity
            for role, identity in zip(
                (
                    "prefix_claim", "registration", *QUERY_ROLES,
                    "later_source_freeze", "salary_diagnostic",
                    "source_authority_completion",
                ),
                before_publication_identities,
                strict=True,
            )
        },
    )
    validate_producer_query_trace(
        producer_query_trace,
        registration=registration,
        captures=captures,
    )
    publication = _build_publication_completion(
        plan=frozen_plan,
        claim_identity=claim_identity,
        registration_identity=registration_identity,
        capture_identities=capture_identities,
        captures=captures,
        source_identity=source_identity,
        source_freeze=source_freeze,
        salary_identity=salary_identity,
        salary_diagnostic=salary_diagnostic,
        completion_identity=completion_identity,
        completion=completion,
        inventory_before_publication=expected_before,
        producer_get_trace=producer_get_trace,
        producer_query_trace=producer_query_trace,
    )
    publication_raw = canonical_json_bytes(publication)
    publication = validate_publication_completion_bytes(publication_raw)
    publication_identity = normalize_object_identity(
        storage.publish(str(uris["publication_completion"]), publication_raw),
        label="published transport completion",
    )
    final_publications = [
        *before_publications,
        (publication_identity, publication_raw),
    ]
    final_identities = [row[0] for row in final_publications]
    final_inventory = _inventory_rows(final_identities)
    return {
        "schema": "corpus-artifact-source-publication-result/v1",
        "run_id": frozen_plan["run_id"],
        "registration": registration_identity,
        "later_source_freeze": source_identity,
        "salary_diagnostic": salary_identity,
        "source_authority_completion": completion_identity,
        "source_authority_completion_sha256": completion[
            "completion_sha256"
        ],
        "publication_completion": publication_identity,
        "query_row_digests": {
            role: captures[role]["rows_sha256"] for role in QUERY_ROLES
        },
        "artifact_count": authority.EXPECTED_ARTIFACT_COUNT,
        "artifact_streamed_one_at_a_time": True,
        "final_object_count": len(final_inventory),
        "final_inventory_sha256": canonical_sha256(final_inventory),
        "producer_get_trace_sha256": producer_get_trace["trace_sha256"],
        "producer_query_trace_sha256": producer_query_trace["trace_sha256"],
        "uses_realized_outcomes": False,
    }


_LAUNCH_LEDGER_KEYS: Final = frozenset({
    "schema_version", "created_at_utc", "transport_contract", "plan_object",
    "run_id", "job", "execution_names_before", "worker_args",
    "worker_args_sha256", "launch_authority_consumed", "one_execution",
    "max_retries", "automatic_retry_licensed", "uses_realized_outcomes",
    "production_change_licensed", "launch_ledger_sha256",
    "execution_intent", "intent_nonce",
})


def _cloud_worker_base_args(plan_identity: Mapping[str, object]) -> list[str]:
    plan = normalize_object_identity(plan_identity, label="worker plan identity")
    return [
        "scripts/prepare_corpus_artifact_source_authority.py",
        "cloud-worker",
        "--plan-uri", str(plan["uri"]),
        "--plan-generation", str(plan["generation"]),
        "--plan-sha256", str(plan["sha256"]),
        "--plan-bytes", str(plan["bytes"]),
    ]


def _validate_execution_intent(
    value: object,
    *,
    intent_identity: Mapping[str, object],
    plan_identity: Mapping[str, object],
    plan: Mapping[str, object],
) -> dict[str, object]:
    """Validate the consumed one-launch ledger without importing transport."""
    item = dict(_mapping(value, label="source execution intent"))
    _exact_keys(item, _LAUNCH_LEDGER_KEYS, label="source execution intent")
    _validate_self_hash(
        item, field="launch_ledger_sha256", label="source execution intent"
    )
    retained_plan = normalize_object_identity(
        plan_identity, label="execution-intent plan"
    )
    retained_intent = normalize_object_identity(
        intent_identity, label="execution-intent object"
    )
    plan_uri = str(retained_plan["uri"])
    suffix = "input/publication-plan.json"
    if not plan_uri.endswith(suffix):
        raise CorpusArtifactSourcePreparationError(
            "execution-intent plan URI differs"
        )
    delivery_prefix = plan_uri[: -len(suffix)]
    if (
        retained_intent["uri"]
        != f"{delivery_prefix}governance/launch-ledger.json"
    ):
        raise CorpusArtifactSourcePreparationError(
            "execution-intent object URI differs"
        )
    contract_identity = normalize_object_identity(
        item["transport_contract"], label="execution-intent contract"
    )
    if (
        contract_identity["uri"]
        != f"{delivery_prefix}governance/transport-contract.json"
    ):
        raise CorpusArtifactSourcePreparationError(
            "execution-intent contract URI differs"
        )
    job = dict(_mapping(item["job"], label="execution-intent job"))
    _exact_keys(
        job,
        frozenset({
            "name", "uid", "generation", "observed_generation",
            "spec_sha256",
        }),
        label="execution-intent job",
    )
    generation = _string(job["generation"], label="execution-intent generation")
    names = list(
        _sequence(
            item["execution_names_before"],
            label="execution-intent execution names",
        )
    )
    expected_args = _cloud_worker_base_args(retained_plan)
    expected_nonce = canonical_sha256({
        "transport_contract": contract_identity,
        "plan_object": retained_plan,
        "job": job,
        "run_id": plan["run_id"],
    })
    if (
        item["schema_version"] != LAUNCH_LEDGER_SCHEMA
        or item["plan_object"] != retained_plan
        or item["run_id"] != plan["run_id"]
        or job["name"] != plan["runtime_identity"]["job"]
        or type(job["uid"]) is not str
        or not job["uid"]
        or _GENERATION.fullmatch(generation) is None
        or job["observed_generation"] != generation
        or _SHA256.fullmatch(str(job["spec_sha256"])) is None
        or names != sorted(names)
        or len(names) != len(set(names))
        or any(type(name) is not str or _RUN_ID.fullmatch(name) is None for name in names)
        or item["worker_args"] != expected_args
        or item["worker_args_sha256"] != canonical_sha256(expected_args)
        or item["launch_authority_consumed"] is not True
        or item["execution_intent"] is not True
        or item["intent_nonce"] != expected_nonce
        or item["one_execution"] is not True
        or item["max_retries"] != 0
        or item["automatic_retry_licensed"] is not False
        or item["uses_realized_outcomes"] is not False
        or item["production_change_licensed"] is not False
    ):
        raise CorpusArtifactSourcePreparationError(
            "execution-intent launch binding differs"
        )
    _timestamp(item["created_at_utc"], label="execution-intent timestamp")
    item["transport_contract"] = contract_identity
    item["plan_object"] = retained_plan
    item["job"] = job
    item["execution_names_before"] = names
    return item


def execute_cloud_worker(
    *,
    plan_identity: object,
    intent_identity: object,
    execute: bool,
    environ: Mapping[str, str],
    storage_factory: Callable[[], StorageBoundary],
    query_factory: Callable[[], QueryBoundary],
) -> dict[str, object]:
    """Generation-GET one delivered plan and execute through that GCS seam.

    This is the only Cloud Run worker entry point.  The literal/environment
    gate precedes construction of either cloud client.  The delivered plan is
    content-addressed, canonical, outside its nine-object output prefix, and
    bound to the immutable image/code/job observed by the runtime.
    """
    require_execute_gate(execute=execute, environ=environ)
    execution_id = environ.get("CLOUD_RUN_EXECUTION", "")
    if (
        environ.get("CLOUD_RUN_TASK_INDEX") != "0"
        or environ.get("CLOUD_RUN_TASK_COUNT") != "1"
        or environ.get("CLOUD_RUN_TASK_ATTEMPT") != "0"
        or _RUN_ID.fullmatch(execution_id) is None
    ):
        raise CorpusArtifactSourcePreparationError(
            "Cloud Run task/execution runtime binding differs"
        )
    normalized_identity = normalize_object_identity(
        plan_identity, label="delivered source publication plan"
    )
    normalized_intent_identity = normalize_object_identity(
        intent_identity, label="delivered source execution intent"
    )
    storage = _TracingStorageBoundary(
        storage_factory(),
        delivered_plan_identity=normalized_identity,
        delivered_intent_identity=normalized_intent_identity,
    )
    raw = storage.read(normalized_identity)
    plan = validate_execution_plan(
        parse_canonical_json_bytes(raw, label="delivered source publication plan")
    )
    if str(normalized_identity["uri"]).startswith(str(plan["output_prefix"])):
        raise CorpusArtifactSourcePreparationError(
            "delivered plan must be outside the nine-object source prefix"
        )
    intent_raw = storage.read(normalized_intent_identity)
    intent = _validate_execution_intent(
        parse_canonical_json_bytes(
            intent_raw, label="delivered source execution intent"
        ),
        intent_identity=normalized_intent_identity,
        plan_identity=normalized_identity,
        plan=plan,
    )
    storage.configure_plan(plan)
    runtime = _mapping(plan["runtime_identity"], label="plan runtime identity")
    expected_runtime = {
        "CLOUD_RUN_JOB": runtime["job"],
        IMAGE_ENV: runtime["image"],
        CODE_ENV: runtime["code_sha"],
    }
    if any(environ.get(key) != value for key, value in expected_runtime.items()):
        raise CorpusArtifactSourcePreparationError(
            "Cloud Run image/code/job runtime binding differs"
        )
    result = execute_authority(
        plan=plan,
        execute=True,
        environ=environ,
        storage_factory=lambda: storage,
        query_factory=query_factory,
    )
    return {
        **result,
        "delivered_plan_object": normalized_identity,
        "delivered_plan_sha256": plan["plan_sha256"],
        "execution_intent_object": normalized_intent_identity,
        "execution_intent_sha256": intent["launch_ledger_sha256"],
    }


class GCSStorage:
    """Generation-pinned GCS adapter; constructed only after execute gate."""

    def __init__(self, *, project: str = PROJECT):
        from google.cloud import storage

        self._client = storage.Client(project=project)

    @staticmethod
    def _parts(uri: str) -> tuple[str, str]:
        candidate = normalize_object_identity({
            "uri": uri,
            "generation": "1",
            "sha256": "0" * 64,
            "bytes": 1,
        }, label="GCS URI")
        return tuple(candidate["uri"].removeprefix("gs://").split("/", 1))  # type: ignore[return-value]

    def read(self, identity: Mapping[str, object]) -> bytes:
        normalized = normalize_object_identity(identity, label="GCS read identity")
        bucket, name = self._parts(str(normalized["uri"]))
        generation = int(str(normalized["generation"]))
        try:
            blob = self._client.bucket(bucket).blob(name, generation=generation)
            blob.reload(if_generation_match=generation)
            raw = blob.download_as_bytes(if_generation_match=generation)
        except Exception as exc:
            raise CorpusArtifactSourcePreparationError(
                "generation-pinned GCS read failed"
            ) from exc
        _bind_raw(raw, normalized, label="generation-pinned GCS object")
        return raw

    def publish(self, uri: str, raw: bytes) -> Mapping[str, object]:
        if type(raw) is not bytes or not raw:
            raise CorpusArtifactSourcePreparationError(
                "create-once publication body must be nonempty bytes"
            )
        bucket, name = self._parts(uri)
        try:
            blob = self._client.bucket(bucket).blob(name)
            blob.upload_from_string(
                raw,
                content_type="application/json",
                if_generation_match=0,
            )
            generation = str(blob.generation)
        except Exception as exc:
            raise CorpusArtifactSourcePreparationError(
                "create-once GCS publication failed"
            ) from exc
        return _identity_for_raw(uri, generation, raw)

    def require_absent(self, uris: Sequence[str]) -> None:
        """Prove every deterministic output name absent without bucket LIST."""
        from google.api_core.exceptions import NotFound

        if not uris or len(uris) != len(set(uris)):
            raise CorpusArtifactSourcePreparationError(
                "deterministic publication URI set differs"
            )
        for uri in uris:
            bucket, name = self._parts(uri)
            try:
                self._client.bucket(bucket).blob(name).reload()
            except NotFound:
                continue
            except Exception as exc:
                raise CorpusArtifactSourcePreparationError(
                    "exact-name publication absence check failed"
                ) from exc
            raise CorpusArtifactSourcePreparationError(
                f"partial source-authority namespace exists at {uri}"
            )


class BigQueryBoundary:
    """Fixed-query adapter; constructed only after registration publication."""

    def __init__(self, *, project: str = PROJECT):
        from google.cloud import bigquery

        self._bigquery = bigquery
        self._client = bigquery.Client(project=project)

    def require_unused_job_ids(self, job_ids: Sequence[str]) -> None:
        from google.api_core.exceptions import NotFound

        if len(job_ids) != len(set(job_ids)):
            raise CorpusArtifactSourcePreparationError("query job IDs repeat")
        for job_id in job_ids:
            try:
                self._client.get_job(job_id, location=LOCATION)
            except NotFound:
                continue
            except Exception as exc:
                raise CorpusArtifactSourcePreparationError(
                    "query-ID absence check failed"
                ) from exc
            raise CorpusArtifactSourcePreparationError(
                f"predeclared query job ID already exists: {job_id}"
            )

    @staticmethod
    def _job_time(value: object, *, label: str) -> str:
        if not isinstance(value, datetime) or value.tzinfo is None:
            raise CorpusArtifactSourcePreparationError(
                f"{label} timestamp differs"
            )
        return value.astimezone(timezone.utc).isoformat()

    def run_query(
        self,
        *,
        sql: str,
        query_identity: Mapping[str, object],
        parameters: Sequence[Mapping[str, object]],
    ) -> QueryOutcome:
        parameter_objects = [
            self._bigquery.ScalarQueryParameter(
                str(row["name"]), str(row["type"]), row["value"]
            )
            for row in parameters
        ]
        try:
            job = self._client.query(
                sql,
                job_config=self._bigquery.QueryJobConfig(
                    query_parameters=parameter_objects,
                    use_query_cache=False,
                ),
                job_id=str(query_identity["job_id"]),
                location=LOCATION,
                job_retry=None,
            )
            result = job.result()
            rows = tuple(
                dict(row.items()) if hasattr(row, "items") else dict(row)
                for row in result
            )
        except Exception as exc:
            raise CorpusArtifactSourcePreparationError(
                "registered outcome-blind query failed"
            ) from exc
        receipt = {
            "job_id": job.job_id,
            "location": job.location,
            "sql_sha256": sha256(sql.encode("utf-8")).hexdigest(),
            "parameters_sha256": canonical_sha256(list(parameters)),
            "created": self._job_time(job.created, label="query created"),
            "started": self._job_time(job.started, label="query started"),
            "ended": self._job_time(job.ended, label="query ended"),
            "total_bytes_processed": int(job.total_bytes_processed or 0),
            "cache_hit": job.cache_hit,
            "error_result": job.error_result,
        }
        return QueryOutcome(rows=rows, receipt=receipt)


def _load_canonical_file(path: Path, *, label: str) -> object:
    if path.is_symlink() or not path.is_file():
        raise CorpusArtifactSourcePreparationError(f"{label} file is unsafe")
    return parse_canonical_json_bytes(path.read_bytes(), label=label)


def _write_once(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("xb") as handle:
            handle.write(raw)
    except FileExistsError:
        if path.is_symlink() or path.read_bytes() != raw:
            raise CorpusArtifactSourcePreparationError(
                f"immutable local output differs: {path}"
            )


def _add_plan_arguments(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--registered-at-utc", required=True)
    parser.add_argument("--source-snapshot-at", required=True)
    parser.add_argument("--output-prefix", required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--image", required=True)
    parser.add_argument("--job", required=True)
    parser.add_argument("--base-source-lock-file", type=Path, required=True)
    parser.add_argument("--output", type=Path)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(description=__doc__)
    commands = root.add_subparsers(dest="command", required=True)
    commands.add_parser("parked", help="default-off no-client command")
    for name in ("validate-only", "dry-run"):
        command = commands.add_parser(name, help="client-free publication plan")
        _add_plan_arguments(command)
    execute = commands.add_parser("execute", help="run one create-once authority")
    execute.add_argument("--plan", type=Path, required=True)
    execute.add_argument("--execute", action="store_true")
    worker = commands.add_parser(
        "cloud-worker", help="generation-pinned Cloud Run plan worker"
    )
    worker.add_argument("--plan-uri", required=True)
    worker.add_argument("--plan-generation", required=True)
    worker.add_argument("--plan-sha256", required=True)
    worker.add_argument("--plan-bytes", type=int, required=True)
    worker.add_argument("--intent-uri", required=True)
    worker.add_argument("--intent-generation", required=True)
    worker.add_argument("--intent-sha256", required=True)
    worker.add_argument("--intent-bytes", type=int, required=True)
    worker.add_argument("--execute", action="store_true")
    return root


def main(argv: Sequence[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.command == "parked":
        print(
            "CORPUS_ARTIFACT_SOURCE_AUTHORITY_PARKED "
            "default_off=true client_constructed=false"
        )
        return 0
    if args.command in {"validate-only", "dry-run"}:
        base_path = args.base_source_lock_file
        if base_path.is_symlink() or not base_path.is_file():
            raise CorpusArtifactSourcePreparationError(
                "base source-lock file is unsafe"
            )
        plan = build_execution_plan(
            run_id=args.run_id,
            registered_at=args.registered_at_utc,
            source_snapshot_at=args.source_snapshot_at,
            output_prefix=args.output_prefix,
            code_sha=args.code_sha,
            image=args.image,
            job=args.job,
            base_source_lock_bytes=base_path.read_bytes(),
        )
        raw = canonical_json_bytes(plan)
        if args.output is not None:
            _write_once(args.output, raw)
        print(raw.decode("utf-8"))
        return 0
    if args.command == "execute":
        # The gate precedes plan loading and both client factories.
        require_execute_gate(execute=args.execute, environ=os.environ)
        plan = _load_canonical_file(args.plan, label="source publication plan")
        result = execute_authority(
            plan=plan,
            execute=True,
            environ=os.environ,
            storage_factory=lambda: GCSStorage(project=PROJECT),
            query_factory=lambda: BigQueryBoundary(project=PROJECT),
        )
        print(canonical_json_bytes(result).decode("utf-8"))
        return 0
    if args.command == "cloud-worker":
        # The worker function gates before constructing either cloud client.
        result = execute_cloud_worker(
            plan_identity={
                "uri": args.plan_uri,
                "generation": args.plan_generation,
                "sha256": args.plan_sha256,
                "bytes": args.plan_bytes,
            },
            intent_identity={
                "uri": args.intent_uri,
                "generation": args.intent_generation,
                "sha256": args.intent_sha256,
                "bytes": args.intent_bytes,
            },
            execute=args.execute,
            environ=os.environ,
            storage_factory=lambda: GCSStorage(project=PROJECT),
            query_factory=lambda: BigQueryBoundary(project=PROJECT),
        )
        print(canonical_json_bytes(result).decode("utf-8"))
        return 0
    raise CorpusArtifactSourcePreparationError("command differs")


__all__ = [
    "BASE_SOURCE_OBJECT",
    "CorpusArtifactSourcePreparationError",
    "ENABLE_ENV",
    "PLAN_SCHEMA",
    "PUBLICATION_COMPLETION_SCHEMA",
    "build_execution_plan",
    "execute_cloud_worker",
    "execute_authority",
    "validate_execution_plan",
    "validate_publication_completion_bytes",
]


if __name__ == "__main__":
    raise SystemExit(main())
