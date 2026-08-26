"""Recoverable one-query outcome supply for the R6 full-union freeze.

The complete structural panel is the sole authority for the player/DST key
union.  This module requires and exact-replays a separately published,
outcome-blind actual-root smoke receipt and key projection, durably records an
attempt, executes or recovers one fixed-ID registered query, and then
publishes query evidence, the pure realized source, the reusable snapshot,
and a completion receipt.

Cloud clients are callbacks.  Importing this module performs no I/O and the
public transaction is deliberately default-off.  The query-evidence object
is separate from the pure snapshot contracts so a process crash after a
successful BigQuery job can recover the exact fixed job without submitting a
second query and can retain table/lease stability evidence without widening
the realized-source schema.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_outcome_snapshot_v1 as snapshot
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_label_score_map as shared


ATTEMPT_SCHEMA: Final = "corpus-r6-full-union-outcome-read-attempt/v1"
QUERY_CONTRACT_SCHEMA: Final = "corpus-r6-full-union-outcome-query-contract/v1"
QUERY_EVIDENCE_SCHEMA: Final = (
    "corpus-r6-full-union-outcome-query-evidence/v1"
)
COMPLETION_SCHEMA: Final = "corpus-r6-full-union-outcome-completion/v1"
OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE: Final = "research/corpus-r6-full-union-realized"
LEASE_RELEASE_OWNER: Final = "external-launcher-watcher"

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_REGISTERED_ROW_FIELDS: Final = frozenset({
    "season", "week", "source_kind", "source_key",
    "realized_score_micro",
})
_ATTEMPT_KEYS: Final = frozenset({
    "schema_version", "run_id", "object_uri",
    "panel_freeze_identity", "panel_freeze_sha256",
    "panel_freeze_object_sha256", "outcome_key_projection_identity",
    "outcome_key_projection_sha256", "actual_root_smoke_receipt_identity",
    "actual_root_smoke_receipt_sha256", "later_source_freeze_identity",
    "later_source_freeze_sha256", "outcome_key_count",
    "outcome_keys_sha256", "query_contract", "query_contract_sha256",
    "table_receipts_before_query", "table_receipt_set_sha256",
    "historical_outcome_lease", "started_at",
    "uses_realized_outcomes_at_creation", "attempt_precedes_query",
    "historical_retry_licensed", "historical_retune_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "attempt_sha256",
})
_QUERY_CONTRACT_KEYS: Final = frozenset({
    "schema_version", "job_id", "location", "sql_sha256",
    "parameters_sha256", "union_keys_sha256", "tables",
    "selected_columns", "source_snapshot_at", "query_count",
    "use_query_cache", "panel_freeze_object_sha256",
})
_QUERY_EVIDENCE_KEYS: Final = frozenset({
    "schema_version", "run_id", "object_uri",
    "panel_freeze_identity", "panel_freeze_sha256",
    "panel_freeze_object_sha256", "outcome_key_projection_identity",
    "outcome_key_projection_sha256", "actual_root_smoke_receipt_identity",
    "actual_root_smoke_receipt_sha256", "later_source_freeze_identity",
    "later_source_freeze_sha256", "attempt_identity", "attempt_sha256",
    "query_contract", "query_contract_sha256", "query_job_receipt",
    "query_job_disposition", "source_snapshot_at",
    "table_receipts_before_query", "table_receipts_after_query",
    "table_receipt_set_sha256", "historical_outcome_lease_before_query",
    "historical_outcome_lease_after_query",
    "historical_outcome_lease_sha256", "row_fields", "row_count",
    "rows_sha256", "rows", "one_exact_query", "query_cache_used",
    "table_metadata_stable_during_query",
    "historical_outcome_lease_unchanged_during_query",
    "full_field_standings_included", "payout_ladder_included",
    "historical_retry_licensed", "historical_retune_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "query_evidence_sha256",
})
_COMPLETION_KEYS: Final = frozenset({
    "schema_version", "run_id", "object_uri",
    "panel_freeze_identity", "panel_freeze_sha256",
    "panel_freeze_object_sha256", "outcome_key_projection_identity",
    "outcome_key_projection_sha256", "actual_root_smoke_receipt_identity",
    "actual_root_smoke_receipt_sha256", "later_source_freeze_identity",
    "later_source_freeze_sha256", "attempt_identity",
    "query_evidence_identity", "realized_source_identity",
    "outcome_snapshot_identity", "outcome_key_count", "query_job_id",
    "one_historical_outcome_read", "one_exact_query_job",
    "independent_source_snapshot_replay_complete", "rank_available",
    "roi_available", "rank_roi_unavailable_reason",
    "historical_outcome_lease_release_required", "lease_release_owner",
    "historical_retry_licensed", "historical_retune_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "completion_sha256",
})


class CorpusR6FullUnionOutcomeSupplyV1Error(RuntimeError):
    """The full-union one-query outcome boundary failed closed."""


@dataclass(frozen=True, slots=True)
class FullUnionOutcomeSupplyConfigV1:
    run_id: str
    job: str
    code_sha: str
    image: str
    enabled: bool = False

    @property
    def output_root(self) -> str:
        return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{self.run_id}"


@dataclass(frozen=True, slots=True)
class FullUnionOutcomeQueryResultV1:
    """One fixed-ID BigQuery job, newly created or recovered by exact ID."""

    result: shared.QueryResult
    disposition: str


@dataclass(frozen=True, slots=True)
class FullUnionOutcomeSupplyV1:
    outcome_key_projection: Mapping[str, object]
    outcome_key_projection_identity: Mapping[str, object]
    attempt: Mapping[str, object]
    attempt_identity: Mapping[str, object]
    query_evidence: Mapping[str, object]
    query_evidence_identity: Mapping[str, object]
    realized_source: Mapping[str, object]
    realized_source_identity: Mapping[str, object]
    outcome_snapshot: Mapping[str, object]
    outcome_snapshot_identity: Mapping[str, object]
    completion: Mapping[str, object]
    completion_identity: Mapping[str, object]


LeaseVerifier = Callable[[], Mapping[str, object]]
MetadataReader = Callable[[str], Mapping[str, object]]
QueryJobGetter = Callable[
    [registered.QuerySpec], FullUnionOutcomeQueryResultV1
]
Publisher = Callable[[str, bytes], registered.PublishedObject]
KnownObjectReader = Callable[[str], registered.PublishedObject | None]
ReadExact = Callable[[Mapping[str, object]], bytes]
Clock = Callable[[], datetime]


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _fail(message: str) -> None:
    raise CorpusR6FullUnionOutcomeSupplyV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc


def _json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc


def _with_self_hash(
    value: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    body = dict(value)
    body[field] = canonical_sha256(body)
    return body


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = _digest(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if retained != canonical_sha256(body):
        _fail(f"{label} self-hash differs")


def _validate_config(
    value: FullUnionOutcomeSupplyConfigV1,
) -> FullUnionOutcomeSupplyConfigV1:
    if (
        not isinstance(value, FullUnionOutcomeSupplyConfigV1)
        or _RUN_ID.fullmatch(value.run_id) is None
        or _JOB.fullmatch(value.job) is None
        or _CODE_SHA.fullmatch(value.code_sha) is None
        or _IMAGE.fullmatch(value.image) is None
        or type(value.enabled) is not bool
    ):
        _fail("R6 full-union outcome supply configuration differs")
    return value


def _now(clock: Clock, *, label: str) -> tuple[str, datetime]:
    try:
        value = clock()
    except Exception as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(
            f"{label} clock failed"
        ) from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        _fail(f"{label} clock must be timezone-aware")
    retained = value.astimezone(timezone.utc)
    return retained.isoformat(), retained


def _validated_object(
    value: object,
    *,
    uri: str,
    expected_raw: bytes | None,
    earliest: datetime | None,
    label: str,
) -> tuple[dict[str, object], datetime, dict[str, object]]:
    if not isinstance(value, registered.PublishedObject):
        _fail(f"{label} object callback returned the wrong result type")
    if type(value.created) is not bool:
        _fail(f"{label} object creation disposition differs")
    try:
        receipt = registered._content_identity(  # noqa: SLF001
            value.receipt, label=f"{label} receipt"
        )
        receipt_raw = _mapping(value.receipt, label=f"{label} receipt")
        created_text, created = shared._utc(  # noqa: SLF001
            value.created_at, label=f"{label} creation"
        )
        reopened = batch.parse_canonical_json_bytes(
            value.reopened_raw, label=f"reopened {label}"
        )
    except (
        registered.CorpusRealizedOutcomeError,
        shared.LR8ScoreMapError,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    raw = bytes(value.reopened_raw)
    if (
        receipt_raw.get("create_only") is not True
        or receipt["uri"] != uri
        or receipt["sha256"] != sha256(raw).hexdigest()
        or receipt["bytes"] != len(raw)
        or created_text != value.created_at
        or (earliest is not None and created < earliest)
        or (expected_raw is not None and raw != expected_raw)
    ):
        _fail(f"{label} exact create/reopen differs")
    return (
        {**receipt, "create_only": True},
        created,
        _mapping(reopened, label=f"reopened {label}"),
    )


def _read_known(
    read_known: KnownObjectReader, *, uri: str, label: str,
) -> tuple[dict[str, object], datetime, dict[str, object]] | None:
    try:
        value = read_known(uri)
    except Exception as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(
            f"{label} known-URI read failed"
        ) from exc
    if value is None:
        return None
    return _validated_object(
        value, uri=uri, expected_raw=None, earliest=None, label=label
    )


def _publish_or_recover(
    publish: Publisher,
    read_known: KnownObjectReader,
    *,
    uri: str,
    payload: Mapping[str, object],
    earliest: datetime,
    label: str,
) -> tuple[dict[str, object], datetime, dict[str, object]]:
    raw = canonical_json_bytes(payload)
    existing = _read_known(read_known, uri=uri, label=label)
    if existing is not None:
        receipt, created, reopened = existing
        if canonical_json_bytes(reopened) != raw or created < earliest:
            _fail(f"{label} exact recovery collision")
        return receipt, created, reopened
    try:
        published = publish(uri, raw)
    except Exception as exc:
        resolved = _read_known(read_known, uri=uri, label=label)
        if resolved is not None:
            receipt, created, reopened = resolved
            if canonical_json_bytes(reopened) == raw and created >= earliest:
                return receipt, created, reopened
        raise CorpusR6FullUnionOutcomeSupplyV1Error(
            f"{label} create-once publication failed"
        ) from exc
    return _validated_object(
        published,
        uri=uri,
        expected_raw=raw,
        earliest=earliest,
        label=label,
    )


def _identity_from_receipt(
    value: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    try:
        return registered._content_identity(value, label=label)  # noqa: SLF001
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc


def _legacy_config(
    config: FullUnionOutcomeSupplyConfigV1,
    *,
    panel_freeze_object_sha256: str,
) -> registered.SupplierConfig:
    return registered.SupplierConfig(
        run_id=config.run_id,
        job=config.job,
        code_sha=config.code_sha,
        image=config.image,
        expected_batch_acceptance_object_sha256=panel_freeze_object_sha256,
        enabled=True,
    )


def _validated_lease(
    value: object, *, legacy_config: registered.SupplierConfig,
) -> dict[str, object]:
    try:
        return registered._lease(value, config=legacy_config)  # noqa: SLF001
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc


def _table_receipt(value: object, *, table: str) -> dict[str, object]:
    try:
        return registered._table_receipt(value, table=table)  # noqa: SLF001
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc


def _table_receipts(value: object) -> list[dict[str, object]]:
    raw = _sequence(value, label="R6 full-union outcome table receipts")
    tables = (registered.SKILL_TABLE, registered.DST_TABLE)
    if len(raw) != len(tables):
        _fail("R6 full-union outcome table receipt count differs")
    return [
        _table_receipt(item, table=table)
        for item, table in zip(raw, tables, strict=True)
    ]


def _registered_keys(
    values: Sequence[snapshot.OutcomeKeyV1],
) -> tuple[registered.OutcomeKey, ...]:
    result: list[registered.OutcomeKey] = []
    for ordinal, row in enumerate(values):
        if not isinstance(row, snapshot.OutcomeKeyV1):
            _fail(f"projected outcome key[{ordinal}] type differs")
        result.append(registered.OutcomeKey(
            task_index=row.source_ordinal,
            season=row.season,
            week=row.week,
            slate_id=row.slate_id,
            player_id=row.player_id,
            source_kind=row.source_kind,
            source_key=row.source_key,
        ))
    return tuple(result)


def deterministic_query_job_id_v1(
    config: FullUnionOutcomeSupplyConfigV1,
    *,
    panel_freeze_object_sha256: str,
) -> str:
    """Return the only job ID, carrying the complete outer root SHA."""
    retained = _validate_config(config)
    root_sha = _digest(
        panel_freeze_object_sha256, label="panel-freeze object SHA"
    )
    return (
        f"r6_full_union_realized_{retained.run_id.replace('-', '_')}_"
        f"{root_sha}"
    )


def _build_query_spec(
    *,
    config: FullUnionOutcomeSupplyConfigV1,
    legacy_config: registered.SupplierConfig,
    outcome_keys: Sequence[snapshot.OutcomeKeyV1],
    source_snapshot_at: str,
    panel_freeze_object_sha256: str,
) -> registered.QuerySpec:
    try:
        base = registered.build_query_spec(
            config=legacy_config,
            outcome_keys=_registered_keys(outcome_keys),
            source_snapshot_at=source_snapshot_at,
        )
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    return registered.QuerySpec(
        sql=base.sql,
        parameters=base.parameters,
        job_id=deterministic_query_job_id_v1(
            config,
            panel_freeze_object_sha256=panel_freeze_object_sha256,
        ),
        location=base.location,
        sql_sha256=base.sql_sha256,
        parameters_sha256=base.parameters_sha256,
        union_keys_sha256=base.union_keys_sha256,
    )


def _query_contract(
    spec: registered.QuerySpec, *, panel_freeze_object_sha256: str,
) -> dict[str, object]:
    contract = {
        "schema_version": QUERY_CONTRACT_SCHEMA,
        "job_id": spec.job_id,
        "location": spec.location,
        "sql_sha256": spec.sql_sha256,
        "parameters_sha256": spec.parameters_sha256,
        "union_keys_sha256": spec.union_keys_sha256,
        "tables": [registered.SKILL_TABLE, registered.DST_TABLE],
        "selected_columns": list(registered.QUERY_ROW_FIELDS),
        "source_snapshot_at": spec.parameters[0].value,
        "query_count": 1,
        "use_query_cache": False,
        "panel_freeze_object_sha256": panel_freeze_object_sha256,
    }
    _exact_keys(contract, _QUERY_CONTRACT_KEYS, label="query contract")
    return contract


def _query_spec_from_contract(
    value: object,
    *,
    config: FullUnionOutcomeSupplyConfigV1,
    legacy_config: registered.SupplierConfig,
    outcome_keys: Sequence[snapshot.OutcomeKeyV1],
    panel_freeze_object_sha256: str,
) -> tuple[registered.QuerySpec, dict[str, object]]:
    contract = _mapping(value, label="R6 full-union query contract")
    _exact_keys(contract, _QUERY_CONTRACT_KEYS, label="R6 full-union query contract")
    source_snapshot_at = contract.get("source_snapshot_at")
    if type(source_snapshot_at) is not str:
        _fail("R6 full-union query source snapshot differs")
    spec = _build_query_spec(
        config=config,
        legacy_config=legacy_config,
        outcome_keys=outcome_keys,
        source_snapshot_at=source_snapshot_at,
        panel_freeze_object_sha256=panel_freeze_object_sha256,
    )
    expected = _query_contract(
        spec, panel_freeze_object_sha256=panel_freeze_object_sha256
    )
    if contract != expected:
        _fail("R6 full-union persisted query contract differs")
    return spec, expected


def _job_receipt(
    value: object, *, spec: registered.QuerySpec, not_before: datetime,
) -> tuple[dict[str, object], datetime]:
    try:
        return registered._job_receipt(  # noqa: SLF001
            value, spec=spec, not_before=not_before
        )
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc


def _registered_integer_micro_rows(
    value: object, *, outcome_keys: Sequence[snapshot.OutcomeKeyV1],
) -> list[dict[str, object]]:
    raw_rows = _sequence(value, label="authoritative query rows")
    expected = {
        (row.season, row.week, row.source_kind, row.source_key): row
        for row in outcome_keys
    }
    if len(expected) != len(outcome_keys):
        _fail("projected query-key union contains duplicates")
    result: list[dict[str, object]] = []
    observed: set[tuple[int, int, str, str]] = set()
    for ordinal, raw in enumerate(raw_rows):
        item = _mapping(raw, label=f"authoritative query row[{ordinal}]")
        if frozenset(item) != frozenset(registered.QUERY_ROW_FIELDS):
            _fail("authoritative query row fields differ")
        season = item["season"]
        week = item["week"]
        kind = item["source_kind"]
        key_value = item["source_key"]
        if (
            type(season) is not int
            or season < 2000
            or type(week) is not int
            or not 1 <= week <= 18
            or type(kind) is not str
            or kind not in {"skill", "dst"}
            or type(key_value) is not str
            or not key_value
        ):
            _fail("authoritative query key differs")
        key = (season, week, kind, key_value)
        if key in observed or key not in expected:
            _fail("authoritative query contains a duplicate or non-union key")
        observed.add(key)
        try:
            score = shared._micro_score(  # noqa: SLF001
                item["realized_score"]
            )
        except shared.LR8ScoreMapError as exc:
            raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
        result.append({
            "season": season,
            "week": week,
            "source_kind": kind,
            "source_key": key_value,
            "realized_score_micro": score,
        })
    expected_order = sorted(expected)
    observed_order = [
        (row["season"], row["week"], row["source_kind"], row["source_key"])
        for row in result
    ]
    if observed_order != expected_order or observed != set(expected):
        _fail("authoritative query is not the exact ordered player/DST union")
    try:
        snapshot.normalize_registered_integer_micro_rows_v1(
            result, outcome_keys=outcome_keys
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    return result


def validate_outcome_attempt_v1(
    value: object,
    *,
    config: FullUnionOutcomeSupplyConfigV1,
    object_uri: str,
    panel_freeze_identity: Mapping[str, object],
    projection: Mapping[str, object],
    projection_identity: Mapping[str, object],
    smoke_receipt: Mapping[str, object],
    smoke_receipt_identity: Mapping[str, object],
    query_contract: Mapping[str, object],
    table_receipts: Sequence[Mapping[str, object]],
    lease: Mapping[str, object],
) -> dict[str, object]:
    attempt = _mapping(value, label="R6 full-union outcome attempt")
    _exact_keys(attempt, _ATTEMPT_KEYS, label="R6 full-union outcome attempt")
    _self_hash(attempt, field="attempt_sha256", label="R6 outcome attempt")
    tables = [dict(item) for item in table_receipts]
    if (
        attempt.get("schema_version") != ATTEMPT_SCHEMA
        or attempt.get("run_id") != config.run_id
        or attempt.get("object_uri") != object_uri
        or attempt.get("panel_freeze_identity") != panel_freeze_identity
        or attempt.get("panel_freeze_sha256")
        != projection["panel_freeze_sha256"]
        or attempt.get("panel_freeze_object_sha256")
        != panel_freeze_identity["sha256"]
        or attempt.get("outcome_key_projection_identity")
        != projection_identity
        or attempt.get("outcome_key_projection_sha256")
        != projection["outcome_key_projection_sha256"]
        or attempt.get("actual_root_smoke_receipt_identity")
        != smoke_receipt_identity
        or attempt.get("actual_root_smoke_receipt_sha256")
        != smoke_receipt["actual_root_smoke_receipt_sha256"]
        or attempt.get("later_source_freeze_identity")
        != projection["later_source_freeze_identity"]
        or attempt.get("later_source_freeze_sha256")
        != projection["later_source_freeze_sha256"]
        or attempt.get("outcome_key_count") != projection["outcome_key_count"]
        or attempt.get("outcome_keys_sha256")
        != projection["outcome_keys_sha256"]
        or attempt.get("query_contract") != query_contract
        or attempt.get("query_contract_sha256")
        != canonical_sha256(query_contract)
        or attempt.get("table_receipts_before_query") != tables
        or attempt.get("table_receipt_set_sha256") != canonical_sha256(tables)
        or attempt.get("historical_outcome_lease") != lease
        or attempt.get("uses_realized_outcomes_at_creation") is not False
        or attempt.get("attempt_precedes_query") is not True
        or any(attempt.get(field) is not False for field in (
            "historical_retry_licensed", "historical_retune_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("R6 full-union outcome attempt replay differs")
    try:
        shared._utc(attempt.get("started_at"), label="attempt start")  # noqa: SLF001
    except shared.LR8ScoreMapError as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    return attempt


def validate_query_evidence_v1(
    value: object,
    *,
    config: FullUnionOutcomeSupplyConfigV1,
    object_uri: str,
    panel_freeze_identity: Mapping[str, object],
    projection: Mapping[str, object],
    projection_identity: Mapping[str, object],
    smoke_receipt: Mapping[str, object],
    smoke_receipt_identity: Mapping[str, object],
    attempt: Mapping[str, object],
    attempt_identity: Mapping[str, object],
    attempt_created_at: datetime,
    spec: registered.QuerySpec,
    query_contract: Mapping[str, object],
    outcome_keys: Sequence[snapshot.OutcomeKeyV1],
) -> tuple[dict[str, object], list[dict[str, object]], datetime]:
    evidence = _mapping(value, label="R6 full-union query evidence")
    _exact_keys(
        evidence, _QUERY_EVIDENCE_KEYS, label="R6 full-union query evidence"
    )
    _self_hash(
        evidence,
        field="query_evidence_sha256",
        label="R6 full-union query evidence",
    )
    before = _table_receipts(evidence.get("table_receipts_before_query"))
    after = _table_receipts(evidence.get("table_receipts_after_query"))
    legacy = _legacy_config(
        config,
        panel_freeze_object_sha256=str(panel_freeze_identity["sha256"]),
    )
    lease_before = _validated_lease(
        evidence.get("historical_outcome_lease_before_query"),
        legacy_config=legacy,
    )
    lease_after = _validated_lease(
        evidence.get("historical_outcome_lease_after_query"),
        legacy_config=legacy,
    )
    job_receipt, query_ended = _job_receipt(
        evidence.get("query_job_receipt"),
        spec=spec,
        not_before=attempt_created_at,
    )
    rows = _sequence(evidence.get("rows"), label="registered integer-micro rows")
    for ordinal, row in enumerate(rows):
        item = _mapping(row, label=f"registered integer-micro row[{ordinal}]")
        if frozenset(item) != _REGISTERED_ROW_FIELDS:
            _fail("registered integer-micro row fields differ")
    try:
        snapshot.normalize_registered_integer_micro_rows_v1(
            rows, outcome_keys=outcome_keys
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    disposition = evidence.get("query_job_disposition")
    if (
        evidence.get("schema_version") != QUERY_EVIDENCE_SCHEMA
        or evidence.get("run_id") != config.run_id
        or evidence.get("object_uri") != object_uri
        or evidence.get("panel_freeze_identity") != panel_freeze_identity
        or evidence.get("panel_freeze_sha256")
        != projection["panel_freeze_sha256"]
        or evidence.get("panel_freeze_object_sha256")
        != panel_freeze_identity["sha256"]
        or evidence.get("outcome_key_projection_identity")
        != projection_identity
        or evidence.get("outcome_key_projection_sha256")
        != projection["outcome_key_projection_sha256"]
        or evidence.get("actual_root_smoke_receipt_identity")
        != smoke_receipt_identity
        or evidence.get("actual_root_smoke_receipt_sha256")
        != smoke_receipt["actual_root_smoke_receipt_sha256"]
        or evidence.get("later_source_freeze_identity")
        != projection["later_source_freeze_identity"]
        or evidence.get("later_source_freeze_sha256")
        != projection["later_source_freeze_sha256"]
        or evidence.get("attempt_identity") != attempt_identity
        or evidence.get("attempt_sha256") != attempt["attempt_sha256"]
        or evidence.get("query_contract") != query_contract
        or evidence.get("query_contract_sha256")
        != canonical_sha256(query_contract)
        or evidence.get("query_job_receipt") != job_receipt
        or type(disposition) is not str
        or disposition not in {"created", "recovered"}
        or evidence.get("source_snapshot_at")
        != query_contract["source_snapshot_at"]
        or before != after
        or evidence.get("table_receipt_set_sha256")
        != canonical_sha256(before)
        or before != attempt["table_receipts_before_query"]
        or lease_before != lease_after
        or lease_before != attempt["historical_outcome_lease"]
        or evidence.get("historical_outcome_lease_sha256")
        != canonical_sha256(lease_before)
        or evidence.get("row_fields") != sorted(_REGISTERED_ROW_FIELDS)
        or evidence.get("row_count") != len(rows)
        or evidence.get("rows_sha256") != canonical_sha256(rows)
        or evidence.get("one_exact_query") is not True
        or evidence.get("query_cache_used") is not False
        or job_receipt["cache_hit"] is not False
        or evidence.get("table_metadata_stable_during_query") is not True
        or evidence.get(
            "historical_outcome_lease_unchanged_during_query"
        ) is not True
        or evidence.get("full_field_standings_included") is not False
        or evidence.get("payout_ladder_included") is not False
        or any(evidence.get(field) is not False for field in (
            "historical_retry_licensed", "historical_retune_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("R6 full-union query evidence replay differs")
    return evidence, [dict(row) for row in rows], query_ended


def validate_outcome_completion_v1(
    value: object,
    *,
    config: FullUnionOutcomeSupplyConfigV1,
    object_uri: str,
    panel_freeze_identity: Mapping[str, object],
    projection: Mapping[str, object],
    projection_identity: Mapping[str, object],
    smoke_receipt: Mapping[str, object],
    smoke_receipt_identity: Mapping[str, object],
    attempt_identity: Mapping[str, object],
    query_evidence_identity: Mapping[str, object],
    realized_source_identity: Mapping[str, object],
    outcome_snapshot_identity: Mapping[str, object],
    query_job_id: str,
) -> dict[str, object]:
    completion = _mapping(value, label="R6 full-union outcome completion")
    _exact_keys(
        completion, _COMPLETION_KEYS, label="R6 full-union outcome completion"
    )
    _self_hash(
        completion,
        field="completion_sha256",
        label="R6 full-union outcome completion",
    )
    if (
        completion.get("schema_version") != COMPLETION_SCHEMA
        or completion.get("run_id") != config.run_id
        or completion.get("object_uri") != object_uri
        or completion.get("panel_freeze_identity") != panel_freeze_identity
        or completion.get("panel_freeze_sha256")
        != projection["panel_freeze_sha256"]
        or completion.get("panel_freeze_object_sha256")
        != panel_freeze_identity["sha256"]
        or completion.get("outcome_key_projection_identity")
        != projection_identity
        or completion.get("outcome_key_projection_sha256")
        != projection["outcome_key_projection_sha256"]
        or completion.get("actual_root_smoke_receipt_identity")
        != smoke_receipt_identity
        or completion.get("actual_root_smoke_receipt_sha256")
        != smoke_receipt["actual_root_smoke_receipt_sha256"]
        or completion.get("later_source_freeze_identity")
        != projection["later_source_freeze_identity"]
        or completion.get("later_source_freeze_sha256")
        != projection["later_source_freeze_sha256"]
        or completion.get("attempt_identity") != attempt_identity
        or completion.get("query_evidence_identity")
        != query_evidence_identity
        or completion.get("realized_source_identity")
        != realized_source_identity
        or completion.get("outcome_snapshot_identity")
        != outcome_snapshot_identity
        or completion.get("outcome_key_count")
        != projection["outcome_key_count"]
        or completion.get("query_job_id") != query_job_id
        or completion.get("one_historical_outcome_read") is not True
        or completion.get("one_exact_query_job") is not True
        or completion.get("independent_source_snapshot_replay_complete")
        is not True
        or completion.get("rank_available") is not False
        or completion.get("roi_available") is not False
        or completion.get("rank_roi_unavailable_reason")
        != "full_field_standings_and_payout_ladder_not_supplied"
        or completion.get("historical_outcome_lease_release_required")
        is not True
        or completion.get("lease_release_owner") != LEASE_RELEASE_OWNER
        or any(completion.get(field) is not False for field in (
            "historical_retry_licensed", "historical_retune_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("R6 full-union outcome completion replay differs")
    return completion


def supply_full_union_outcome_snapshot_v1(
    *,
    config: FullUnionOutcomeSupplyConfigV1,
    panel_freeze_identity: object,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    actual_root_smoke_receipt: object,
    actual_root_smoke_receipt_identity: object,
    snapshot_module_sha256: object,
    snapshot_cli_sha256: object,
    snapshot_test_sha256: object,
    snapshot_cli_test_sha256: object,
    read_exact: ReadExact,
    verify_lease: LeaseVerifier,
    read_table_metadata: MetadataReader,
    get_or_create_query: QueryJobGetter,
    publish: Publisher,
    read_known: KnownObjectReader,
    clock: Clock,
) -> FullUnionOutcomeSupplyV1:
    """Create or recover the sole full-union player/DST outcome snapshot."""
    retained_config = _validate_config(config)
    if retained_config.enabled is not True:
        _fail("R6 full-union outcome supply is default-off")
    if not all(callable(value) for value in (
        read_exact, verify_lease, read_table_metadata, get_or_create_query,
        publish, read_known, clock,
    )):
        _fail("R6 full-union outcome supply callback differs")
    retained_root_identity = _identity(
        panel_freeze_identity, label="R6 full-union panel-freeze identity"
    )
    if not str(retained_root_identity["uri"]).endswith("/panel-freeze.json"):
        _fail("R6 full-union panel-freeze URI differs")

    uris = {
        "projection": f"{retained_config.output_root}/outcome-key-projection.json",
        "smoke": f"{retained_config.output_root}/actual-root-smoke-receipt.json",
        "attempt": f"{retained_config.output_root}/read-attempt.json",
        "query_evidence": f"{retained_config.output_root}/query-evidence.json",
        "source": f"{retained_config.output_root}/realized-source.json",
        "snapshot": f"{retained_config.output_root}/outcome-snapshot.json",
        "completion": f"{retained_config.output_root}/completion.json",
    }
    if len(set(uris.values())) != len(uris):
        _fail("R6 full-union outcome object URIs alias")

    retained_projection_identity = _identity(
        outcome_key_projection_identity,
        label="R6 full-union projection identity",
    )
    retained_smoke_identity = _identity(
        actual_root_smoke_receipt_identity,
        label="R6 full-union actual-root smoke identity",
    )
    if (
        retained_projection_identity["uri"] != uris["projection"]
        or retained_smoke_identity["uri"] != uris["smoke"]
    ):
        _fail("R6 full-union smoke/projection URI differs")
    known_projection = _read_known(
        read_known,
        uri=uris["projection"],
        label="R6 full-union outcome-key projection",
    )
    known_smoke = _read_known(
        read_known,
        uri=uris["smoke"],
        label="R6 full-union actual-root smoke receipt",
    )
    if known_projection is None or known_smoke is None:
        _fail("R6 full-union actual-root smoke/projection is absent")
    projection_receipt, projection_created_at, reopened_projection = (
        known_projection
    )
    projection_identity = _identity_from_receipt(
        projection_receipt, label="R6 full-union projection identity"
    )
    smoke_receipt_raw, smoke_created_at, reopened_smoke = known_smoke
    smoke_receipt_identity = _identity_from_receipt(
        smoke_receipt_raw, label="R6 full-union actual-root smoke identity"
    )
    if (
        projection_identity != retained_projection_identity
        or smoke_receipt_identity != retained_smoke_identity
        or canonical_json_bytes(reopened_projection)
        != canonical_json_bytes(outcome_key_projection)
        or canonical_json_bytes(reopened_smoke)
        != canonical_json_bytes(actual_root_smoke_receipt)
        or projection_created_at > smoke_created_at
    ):
        _fail("R6 full-union persisted smoke/projection identity differs")
    module_sha = _digest(snapshot_module_sha256, label="snapshot module SHA")
    cli_sha = _digest(snapshot_cli_sha256, label="snapshot CLI SHA")
    test_sha = _digest(snapshot_test_sha256, label="snapshot test SHA")
    cli_test_sha = _digest(
        snapshot_cli_test_sha256, label="snapshot CLI test SHA"
    )
    try:
        projection, validated_projection_identity, outcome_keys = (
            snapshot.validate_outcome_key_projection_v1(
                reopened_projection,
                identity=projection_identity,
                read_exact=read_exact,
            )
        )
        smoke_receipt, validated_smoke_identity = (
            snapshot.validate_actual_root_smoke_receipt_v1(
                reopened_smoke,
                identity=smoke_receipt_identity,
                expected_panel_freeze_identity=retained_root_identity,
                outcome_key_projection=projection,
                expected_outcome_key_projection_identity=projection_identity,
                expected_reviewed_source_commit_sha=retained_config.code_sha,
                expected_runtime_immutable_image=retained_config.image,
                expected_snapshot_module_sha256=module_sha,
                expected_snapshot_cli_sha256=cli_sha,
                expected_snapshot_test_sha256=test_sha,
                expected_snapshot_cli_test_sha256=cli_test_sha,
                read_exact=read_exact,
            )
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    if (
        validated_projection_identity != projection_identity
        or validated_smoke_identity != smoke_receipt_identity
        or projection.get("panel_freeze_identity") != retained_root_identity
        or smoke_receipt.get("panel_freeze_identity") != retained_root_identity
        or smoke_receipt.get("outcome_key_projection_identity")
        != projection_identity
        or projection.get("complete") is not True
        or projection.get("uses_realized_outcomes") is not False
        or projection.get("historical_scoring_licensed") is not False
    ):
        _fail("R6 full-union outcome-key projection boundary differs")
    root_object_sha = _digest(
        retained_root_identity["sha256"], label="panel-freeze object SHA"
    )
    legacy_config = _legacy_config(
        retained_config, panel_freeze_object_sha256=root_object_sha
    )

    known = {
        label: _read_known(read_known, uri=uris[label], label=f"R6 {label}")
        for label in ("attempt", "query_evidence", "source", "snapshot", "completion")
    }
    predecessor_order = (
        "attempt", "query_evidence", "source", "snapshot", "completion"
    )
    seen_missing = False
    for label in predecessor_order:
        if known[label] is None:
            seen_missing = True
        elif seen_missing:
            _fail(f"R6 full-union {label} is missing a required predecessor")

    def replay_attempt(
        retained: tuple[dict[str, object], datetime, dict[str, object]],
    ) -> tuple[
        dict[str, object], dict[str, object], datetime,
        registered.QuerySpec, dict[str, object],
        list[dict[str, object]], dict[str, object],
    ]:
        receipt, created_at, reopened = retained
        lease = _validated_lease(
            reopened.get("historical_outcome_lease"),
            legacy_config=legacy_config,
        )
        tables = _table_receipts(reopened.get("table_receipts_before_query"))
        spec, contract = _query_spec_from_contract(
            reopened.get("query_contract"),
            config=retained_config,
            legacy_config=legacy_config,
            outcome_keys=outcome_keys,
            panel_freeze_object_sha256=root_object_sha,
        )
        try:
            _, lease_acquired = shared._utc(  # noqa: SLF001
                lease["body"]["acquired_at"], label="lease acquired_at"
            )
            _, started_at = shared._utc(  # noqa: SLF001
                reopened.get("started_at"), label="attempt start"
            )
            _, source_snapshot = shared._utc(  # noqa: SLF001
                contract["source_snapshot_at"], label="source snapshot"
            )
        except shared.LR8ScoreMapError as exc:
            raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
        if not (
            smoke_created_at <= started_at
            and lease_acquired <= started_at <= source_snapshot <= created_at
        ):
            _fail("R6 full-union attempt durable chronology differs")
        attempt = validate_outcome_attempt_v1(
            reopened,
            config=retained_config,
            object_uri=uris["attempt"],
            panel_freeze_identity=retained_root_identity,
            projection=projection,
            projection_identity=projection_identity,
            smoke_receipt=smoke_receipt,
            smoke_receipt_identity=smoke_receipt_identity,
            query_contract=contract,
            table_receipts=tables,
            lease=lease,
        )
        attempt_identity = _identity_from_receipt(
            receipt, label="R6 full-union attempt identity"
        )
        return (
            attempt, attempt_identity, created_at, spec, contract, tables, lease
        )

    if known["attempt"] is None:
        lease_before = _validated_lease(
            verify_lease(), legacy_config=legacy_config
        )
        started_text, started_at = _now(clock, label="R6 full-union attempt")
        try:
            _, lease_acquired = shared._utc(  # noqa: SLF001
                lease_before["body"]["acquired_at"], label="lease acquired_at"
            )
        except shared.LR8ScoreMapError as exc:
            raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
        if started_at < smoke_created_at or started_at < lease_acquired:
            _fail("R6 full-union attempt predates its smoke or lease")
        source_snapshot_at, source_snapshot_time = _now(
            clock, label="R6 full-union source snapshot"
        )
        if source_snapshot_time < started_at:
            _fail("R6 full-union source snapshot predates its read attempt")
        spec = _build_query_spec(
            config=retained_config,
            legacy_config=legacy_config,
            outcome_keys=outcome_keys,
            source_snapshot_at=source_snapshot_at,
            panel_freeze_object_sha256=root_object_sha,
        )
        contract = _query_contract(
            spec, panel_freeze_object_sha256=root_object_sha
        )
        tables = (registered.SKILL_TABLE, registered.DST_TABLE)
        before = [
            _table_receipt(read_table_metadata(table), table=table)
            for table in tables
        ]
        attempt_payload = _with_self_hash({
            "schema_version": ATTEMPT_SCHEMA,
            "run_id": retained_config.run_id,
            "object_uri": uris["attempt"],
            "panel_freeze_identity": retained_root_identity,
            "panel_freeze_sha256": projection["panel_freeze_sha256"],
            "panel_freeze_object_sha256": root_object_sha,
            "outcome_key_projection_identity": projection_identity,
            "outcome_key_projection_sha256": projection[
                "outcome_key_projection_sha256"
            ],
            "actual_root_smoke_receipt_identity": smoke_receipt_identity,
            "actual_root_smoke_receipt_sha256": smoke_receipt[
                "actual_root_smoke_receipt_sha256"
            ],
            "later_source_freeze_identity": projection[
                "later_source_freeze_identity"
            ],
            "later_source_freeze_sha256": projection[
                "later_source_freeze_sha256"
            ],
            "outcome_key_count": projection["outcome_key_count"],
            "outcome_keys_sha256": projection["outcome_keys_sha256"],
            "query_contract": contract,
            "query_contract_sha256": canonical_sha256(contract),
            "table_receipts_before_query": before,
            "table_receipt_set_sha256": canonical_sha256(before),
            "historical_outcome_lease": lease_before,
            "started_at": started_text,
            "uses_realized_outcomes_at_creation": False,
            "attempt_precedes_query": True,
            "historical_retry_licensed": False,
            "historical_retune_licensed": False,
            "graph_mutation_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        }, field="attempt_sha256")
        known["attempt"] = _publish_or_recover(
            publish,
            read_known,
            uri=uris["attempt"],
            payload=attempt_payload,
            earliest=source_snapshot_time,
            label="R6 full-union outcome attempt",
        )

    if known["attempt"] is None:  # pragma: no cover - assigned above
        raise AssertionError("attempt recovery remained absent")
    (
        attempt, attempt_identity, attempt_created_at, spec, query_contract,
        before, lease_before,
    ) = replay_attempt(known["attempt"])

    if known["query_evidence"] is None:
        lease_current = _validated_lease(
            verify_lease(), legacy_config=legacy_config
        )
        if canonical_json_bytes(lease_current) != canonical_json_bytes(lease_before):
            _fail("R6 historical-outcome lease changed before the query")
        tables = (registered.SKILL_TABLE, registered.DST_TABLE)
        current_before = [
            _table_receipt(read_table_metadata(table), table=table)
            for table in tables
        ]
        if current_before != before:
            _fail("R6 outcome table metadata changed before the query")
        try:
            query_value = get_or_create_query(spec)
        except Exception as exc:
            raise CorpusR6FullUnionOutcomeSupplyV1Error(
                "R6 full-union fixed-ID outcome query failed"
            ) from exc
        if not isinstance(query_value, FullUnionOutcomeQueryResultV1):
            _fail("R6 full-union query callback returned the wrong result type")
        if (
            type(query_value.disposition) is not str
            or query_value.disposition not in {"created", "recovered"}
        ):
            _fail("R6 full-union query job disposition differs")
        queried = query_value.result
        if not isinstance(queried, shared.QueryResult):
            _fail("R6 full-union outcome query returned the wrong result type")
        job_receipt, query_ended = _job_receipt(
            queried.job_receipt, spec=spec, not_before=attempt_created_at
        )
        if job_receipt["cache_hit"] is not False:
            _fail("R6 full-union outcome query used cache")
        rows = _registered_integer_micro_rows(
            queried.rows, outcome_keys=outcome_keys
        )
        after = [
            _table_receipt(read_table_metadata(table), table=table)
            for table in tables
        ]
        if before != after:
            _fail("R6 outcome table metadata changed during the query")
        lease_after = _validated_lease(
            verify_lease(), legacy_config=legacy_config
        )
        if canonical_json_bytes(lease_before) != canonical_json_bytes(lease_after):
            _fail("R6 historical-outcome lease changed during the query")
        evidence_payload = _with_self_hash({
            "schema_version": QUERY_EVIDENCE_SCHEMA,
            "run_id": retained_config.run_id,
            "object_uri": uris["query_evidence"],
            "panel_freeze_identity": retained_root_identity,
            "panel_freeze_sha256": projection["panel_freeze_sha256"],
            "panel_freeze_object_sha256": root_object_sha,
            "outcome_key_projection_identity": projection_identity,
            "outcome_key_projection_sha256": projection[
                "outcome_key_projection_sha256"
            ],
            "actual_root_smoke_receipt_identity": smoke_receipt_identity,
            "actual_root_smoke_receipt_sha256": smoke_receipt[
                "actual_root_smoke_receipt_sha256"
            ],
            "later_source_freeze_identity": projection[
                "later_source_freeze_identity"
            ],
            "later_source_freeze_sha256": projection[
                "later_source_freeze_sha256"
            ],
            "attempt_identity": attempt_identity,
            "attempt_sha256": attempt["attempt_sha256"],
            "query_contract": query_contract,
            "query_contract_sha256": canonical_sha256(query_contract),
            "query_job_receipt": job_receipt,
            "query_job_disposition": query_value.disposition,
            "source_snapshot_at": query_contract["source_snapshot_at"],
            "table_receipts_before_query": before,
            "table_receipts_after_query": after,
            "table_receipt_set_sha256": canonical_sha256(before),
            "historical_outcome_lease_before_query": lease_before,
            "historical_outcome_lease_after_query": lease_after,
            "historical_outcome_lease_sha256": canonical_sha256(lease_before),
            "row_fields": sorted(_REGISTERED_ROW_FIELDS),
            "row_count": len(rows),
            "rows_sha256": canonical_sha256(rows),
            "rows": rows,
            "one_exact_query": True,
            "query_cache_used": False,
            "table_metadata_stable_during_query": True,
            "historical_outcome_lease_unchanged_during_query": True,
            "full_field_standings_included": False,
            "payout_ladder_included": False,
            "historical_retry_licensed": False,
            "historical_retune_licensed": False,
            "graph_mutation_licensed": False,
            "production_change_licensed": False,
            "decision_authority": False,
        }, field="query_evidence_sha256")
        known["query_evidence"] = _publish_or_recover(
            publish,
            read_known,
            uri=uris["query_evidence"],
            payload=evidence_payload,
            earliest=query_ended,
            label="R6 full-union query evidence",
        )

    if known["query_evidence"] is None:  # pragma: no cover
        raise AssertionError("query evidence recovery remained absent")
    evidence_receipt, evidence_created_at, reopened_evidence = known[
        "query_evidence"
    ]
    query_evidence_identity = _identity_from_receipt(
        evidence_receipt, label="R6 full-union query-evidence identity"
    )
    query_evidence, registered_rows, query_ended = validate_query_evidence_v1(
        reopened_evidence,
        config=retained_config,
        object_uri=uris["query_evidence"],
        panel_freeze_identity=retained_root_identity,
        projection=projection,
        projection_identity=projection_identity,
        smoke_receipt=smoke_receipt,
        smoke_receipt_identity=smoke_receipt_identity,
        attempt=attempt,
        attempt_identity=attempt_identity,
        attempt_created_at=attempt_created_at,
        spec=spec,
        query_contract=query_contract,
        outcome_keys=outcome_keys,
    )
    if evidence_created_at < query_ended:
        _fail("R6 query evidence predates its fixed query")

    try:
        expected_source = snapshot.build_realized_source_from_registered_rows_v1(
            outcome_key_projection=projection,
            outcome_key_projection_identity=projection_identity,
            registered_integer_micro_rows=registered_rows,
            read_exact=read_exact,
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    if known["source"] is None:
        known["source"] = _publish_or_recover(
            publish,
            read_known,
            uri=uris["source"],
            payload=expected_source,
            earliest=evidence_created_at,
            label="R6 full-union realized source",
        )
    if known["source"] is None:  # pragma: no cover
        raise AssertionError("realized source recovery remained absent")
    source_receipt, source_created_at, reopened_source = known["source"]
    realized_source_identity = _identity_from_receipt(
        source_receipt, label="R6 full-union realized-source identity"
    )
    try:
        realized_source, validated_source_identity, _ = (
            snapshot.validate_realized_source_v1(
                reopened_source,
                identity=realized_source_identity,
                outcome_key_projection=projection,
                outcome_key_projection_identity=projection_identity,
                read_exact=read_exact,
            )
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    if (
        validated_source_identity != realized_source_identity
        or canonical_json_bytes(realized_source) != canonical_json_bytes(expected_source)
        or source_created_at < evidence_created_at
    ):
        _fail("R6 full-union realized-source recovery differs")

    try:
        expected_snapshot = snapshot.build_outcome_snapshot_v1(
            outcome_key_projection=projection,
            outcome_key_projection_identity=projection_identity,
            realized_source=realized_source,
            realized_source_identity=realized_source_identity,
            read_exact=read_exact,
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    if known["snapshot"] is None:
        known["snapshot"] = _publish_or_recover(
            publish,
            read_known,
            uri=uris["snapshot"],
            payload=expected_snapshot,
            earliest=source_created_at,
            label="R6 full-union outcome snapshot",
        )
    if known["snapshot"] is None:  # pragma: no cover
        raise AssertionError("outcome snapshot recovery remained absent")
    snapshot_receipt, snapshot_created_at, reopened_snapshot = known["snapshot"]
    outcome_snapshot_identity = _identity_from_receipt(
        snapshot_receipt, label="R6 full-union outcome-snapshot identity"
    )
    try:
        outcome_snapshot, validated_snapshot_identity, _ = (
            snapshot.validate_outcome_snapshot_v1(
                reopened_snapshot,
                identity=outcome_snapshot_identity,
                outcome_key_projection=projection,
                outcome_key_projection_identity=projection_identity,
                realized_source=realized_source,
                realized_source_identity=realized_source_identity,
                read_exact=read_exact,
            )
        )
    except snapshot.CorpusR6FullUnionOutcomeSnapshotV1Error as exc:
        raise CorpusR6FullUnionOutcomeSupplyV1Error(str(exc)) from exc
    if (
        validated_snapshot_identity != outcome_snapshot_identity
        or canonical_json_bytes(outcome_snapshot)
        != canonical_json_bytes(expected_snapshot)
        or snapshot_created_at < source_created_at
    ):
        _fail("R6 full-union outcome-snapshot recovery differs")

    completion_payload = _with_self_hash({
        "schema_version": COMPLETION_SCHEMA,
        "run_id": retained_config.run_id,
        "object_uri": uris["completion"],
        "panel_freeze_identity": retained_root_identity,
        "panel_freeze_sha256": projection["panel_freeze_sha256"],
        "panel_freeze_object_sha256": root_object_sha,
        "outcome_key_projection_identity": projection_identity,
        "outcome_key_projection_sha256": projection[
            "outcome_key_projection_sha256"
        ],
        "actual_root_smoke_receipt_identity": smoke_receipt_identity,
        "actual_root_smoke_receipt_sha256": smoke_receipt[
            "actual_root_smoke_receipt_sha256"
        ],
        "later_source_freeze_identity": projection[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_sha256": projection[
            "later_source_freeze_sha256"
        ],
        "attempt_identity": attempt_identity,
        "query_evidence_identity": query_evidence_identity,
        "realized_source_identity": realized_source_identity,
        "outcome_snapshot_identity": outcome_snapshot_identity,
        "outcome_key_count": projection["outcome_key_count"],
        "query_job_id": query_evidence["query_job_receipt"]["job_id"],
        "one_historical_outcome_read": True,
        "one_exact_query_job": True,
        "independent_source_snapshot_replay_complete": True,
        "rank_available": False,
        "roi_available": False,
        "rank_roi_unavailable_reason": (
            "full_field_standings_and_payout_ladder_not_supplied"
        ),
        "historical_outcome_lease_release_required": True,
        "lease_release_owner": LEASE_RELEASE_OWNER,
        "historical_retry_licensed": False,
        "historical_retune_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }, field="completion_sha256")
    if known["completion"] is None:
        known["completion"] = _publish_or_recover(
            publish,
            read_known,
            uri=uris["completion"],
            payload=completion_payload,
            earliest=snapshot_created_at,
            label="R6 full-union outcome completion",
        )
    if known["completion"] is None:  # pragma: no cover
        raise AssertionError("outcome completion recovery remained absent")
    completion_receipt, completion_created_at, reopened_completion = known[
        "completion"
    ]
    if completion_created_at < snapshot_created_at:
        _fail("R6 outcome completion predates its snapshot")
    completion_identity = _identity_from_receipt(
        completion_receipt, label="R6 full-union completion identity"
    )
    completion = validate_outcome_completion_v1(
        reopened_completion,
        config=retained_config,
        object_uri=uris["completion"],
        panel_freeze_identity=retained_root_identity,
        projection=projection,
        projection_identity=projection_identity,
        smoke_receipt=smoke_receipt,
        smoke_receipt_identity=smoke_receipt_identity,
        attempt_identity=attempt_identity,
        query_evidence_identity=query_evidence_identity,
        realized_source_identity=realized_source_identity,
        outcome_snapshot_identity=outcome_snapshot_identity,
        query_job_id=str(query_evidence["query_job_receipt"]["job_id"]),
    )
    if completion != completion_payload:
        _fail("R6 full-union completion exact recovery differs")
    if smoke_created_at > attempt_created_at:
        _fail("R6 full-union attempt predates its actual-root smoke receipt")

    return FullUnionOutcomeSupplyV1(
        outcome_key_projection=projection,
        outcome_key_projection_identity=projection_identity,
        attempt=attempt,
        attempt_identity=attempt_identity,
        query_evidence=query_evidence,
        query_evidence_identity=query_evidence_identity,
        realized_source=realized_source,
        realized_source_identity=realized_source_identity,
        outcome_snapshot=outcome_snapshot,
        outcome_snapshot_identity=outcome_snapshot_identity,
        completion=completion,
        completion_identity=completion_identity,
    )


__all__ = [
    "ATTEMPT_SCHEMA",
    "COMPLETION_SCHEMA",
    "CorpusR6FullUnionOutcomeSupplyV1Error",
    "FullUnionOutcomeQueryResultV1",
    "FullUnionOutcomeSupplyConfigV1",
    "FullUnionOutcomeSupplyV1",
    "LEASE_RELEASE_OWNER",
    "OUTPUT_BUCKET",
    "OUTPUT_NAMESPACE",
    "QUERY_CONTRACT_SCHEMA",
    "QUERY_EVIDENCE_SCHEMA",
    "canonical_json_bytes",
    "canonical_sha256",
    "deterministic_query_job_id_v1",
    "supply_full_union_outcome_snapshot_v1",
    "validate_outcome_attempt_v1",
    "validate_outcome_completion_v1",
    "validate_query_evidence_v1",
]
