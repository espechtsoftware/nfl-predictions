"""One-query transport boundary for a frozen Core v1 catalog.

The Core catalog closes every lineup book before this module can run.  This
module then creates one read-attempt object, executes the registered player/DST
score query once, publishes one exact player source and one reusable snapshot,
and stops.  Grading is deliberately a separate pure step.

Cloud clients are callbacks.  Importing this module performs no I/O and the
public transaction is default-off.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_core_v1_catalog as core
from nfl_dfs.research import corpus_core_v1_outcome_snapshot as snapshot
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_label_score_map as shared


ATTEMPT_SCHEMA: Final = snapshot.READ_ATTEMPT_SCHEMA
COMPLETION_SCHEMA: Final = "corpus-core-v1-outcome-snapshot-completion/v1"
OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-retrieval"
OUTPUT_NAMESPACE: Final = "research/corpus-core-v1-realized"
LEASE_RELEASE_OWNER: Final = "external-launcher-watcher"

_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{7,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_ATTEMPT_KEYS: Final = frozenset({
    "schema_version",
    "run_id",
    "catalog_identity",
    "catalog_sha256",
    "later_source_freeze_identity",
    "later_source_freeze_sha256",
    "outcome_key_count",
    "outcome_keys",
    "outcome_keys_sha256",
    "query_contract",
    "query_contract_sha256",
    "table_receipts_before_query",
    "table_receipt_set_sha256",
    "historical_outcome_lease",
    "started_at",
    "uses_realized_outcomes_at_creation",
    "attempt_precedes_query",
    "historical_retry_licensed",
    "historical_retune_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
    "attempt_sha256",
})
_COMPLETION_KEYS: Final = frozenset({
    "schema_version",
    "run_id",
    "catalog_identity",
    "catalog_sha256",
    "attempt_identity",
    "player_source_identity",
    "outcome_snapshot_identity",
    "outcome_key_count",
    "one_historical_outcome_read",
    "independent_source_snapshot_replay_complete",
    "rank_available",
    "roi_available",
    "rank_roi_unavailable_reason",
    "historical_outcome_lease_release_required",
    "lease_release_owner",
    "historical_retry_licensed",
    "historical_retune_licensed",
    "graph_mutation_licensed",
    "production_change_licensed",
    "decision_authority",
    "completion_sha256",
})


class CorpusCoreV1OutcomeSupplyError(RuntimeError):
    """The one-query Core v1 outcome boundary failed closed."""


@dataclass(frozen=True, slots=True)
class CoreOutcomeSupplyConfig:
    run_id: str
    job: str
    code_sha: str
    image: str
    enabled: bool = False

    @property
    def output_root(self) -> str:
        return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{self.run_id}"


@dataclass(frozen=True, slots=True)
class CoreOutcomeSupply:
    attempt: Mapping[str, object]
    attempt_identity: Mapping[str, object]
    player_source: Mapping[str, object]
    player_source_identity: Mapping[str, object]
    outcome_snapshot: Mapping[str, object]
    outcome_snapshot_identity: Mapping[str, object]
    completion: Mapping[str, object]
    completion_identity: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class CoreOutcomeQueryResult:
    """One fixed-ID BigQuery job, newly created or recovered by exact ID."""

    result: shared.QueryResult
    disposition: str


LeaseVerifier = Callable[[], Mapping[str, object]]
MetadataReader = Callable[[str], Mapping[str, object]]
QueryJobGetter = Callable[[registered.QuerySpec], CoreOutcomeQueryResult]
Publisher = Callable[[str, bytes], registered.PublishedObject]
KnownObjectReader = Callable[[str], registered.PublishedObject | None]
Clock = Callable[[], datetime]


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _fail(message: str) -> None:
    raise CorpusCoreV1OutcomeSupplyError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = value.get(field)
    body = {key: item for key, item in value.items() if key != field}
    if type(retained) is not str or retained != canonical_sha256(body):
        _fail(f"{label} self-hash differs")


def _with_self_hash(
    value: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    body = dict(value)
    body[field] = canonical_sha256(body)
    return body


def _validate_config(value: CoreOutcomeSupplyConfig) -> CoreOutcomeSupplyConfig:
    if (
        not isinstance(value, CoreOutcomeSupplyConfig)
        or _RUN_ID.fullmatch(value.run_id) is None
        or _JOB.fullmatch(value.job) is None
        or _CODE_SHA.fullmatch(value.code_sha) is None
        or _IMAGE.fullmatch(value.image) is None
        or type(value.enabled) is not bool
    ):
        _fail("Core v1 outcome supply configuration differs")
    return value


def _now(clock: Clock, *, label: str) -> tuple[str, datetime]:
    try:
        value = clock()
    except Exception as exc:
        raise CorpusCoreV1OutcomeSupplyError(f"{label} clock failed") from exc
    if not isinstance(value, datetime) or value.tzinfo is None:
        _fail(f"{label} clock must be timezone-aware")
    retained = value.astimezone(timezone.utc)
    return retained.isoformat(), retained


def _legacy_config(
    config: CoreOutcomeSupplyConfig, *, catalog_sha256: str,
) -> registered.SupplierConfig:
    return registered.SupplierConfig(
        run_id=config.run_id,
        job=config.job,
        code_sha=config.code_sha,
        image=config.image,
        # The registered query/lease primitive needs one immutable authority
        # digest for deterministic identity.  Core supplies its catalog hash;
        # no synthetic batch acceptance is constructed.
        expected_batch_acceptance_object_sha256=catalog_sha256,
        enabled=True,
    )


def _outcome_key_payload(
    values: Sequence[snapshot.CoreOutcomeKey],
) -> list[dict[str, object]]:
    return [{
        "source_ordinal": row.source_ordinal,
        "season": row.season,
        "week": row.week,
        "slate_id": row.slate_id,
        "source_kind": row.source_kind,
        "source_key": row.source_key,
        "player_id": row.player_id,
    } for row in values]


def _query_contract(
    spec: registered.QuerySpec,
    *,
    outcome_keys: Sequence[snapshot.CoreOutcomeKey],
) -> dict[str, object]:
    contract = snapshot.core_query_contract(
        outcome_keys=outcome_keys,
        query_job_id=spec.job_id,
        source_snapshot_at=str(spec.parameters[0].value),
    )
    if (
        contract["job_id"] != spec.job_id
        or contract["location"] != spec.location
        or contract["sql_sha256"] != spec.sql_sha256
        or contract["parameters_sha256"] != spec.parameters_sha256
        or contract["union_keys_sha256"] != spec.union_keys_sha256
    ):
        _fail("Core v1 canonical query contract differs from its query spec")
    return contract


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
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc
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
    return {**receipt, "create_only": True}, created, dict(
        _mapping(reopened, label=f"reopened {label}")
    )


def _read_known(
    read_known: KnownObjectReader,
    *,
    uri: str,
    label: str,
) -> tuple[dict[str, object], datetime, dict[str, object]] | None:
    try:
        value = read_known(uri)
    except Exception as exc:
        raise CorpusCoreV1OutcomeSupplyError(f"{label} known-URI read failed") from exc
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
        raise CorpusCoreV1OutcomeSupplyError(
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
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc


def _validated_lease(
    value: object,
    *,
    legacy_config: registered.SupplierConfig,
) -> dict[str, object]:
    try:
        return registered._lease(value, config=legacy_config)  # noqa: SLF001
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc


def _table_receipt(value: object, *, table: str) -> dict[str, object]:
    try:
        return registered._table_receipt(value, table=table)  # noqa: SLF001
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc


def _table_receipts(value: object) -> list[dict[str, object]]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail("Core v1 outcome table receipts must be an array")
    tables = (registered.SKILL_TABLE, registered.DST_TABLE)
    if len(value) != len(tables):
        _fail("Core v1 outcome table receipt count differs")
    return [
        _table_receipt(raw, table=table)
        for raw, table in zip(value, tables, strict=True)
    ]


def _job_receipt(
    value: object,
    *,
    spec: registered.QuerySpec,
    not_before: datetime,
) -> tuple[dict[str, object], datetime]:
    try:
        return registered._job_receipt(  # noqa: SLF001
            value, spec=spec, not_before=not_before
        )
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc


def _query_spec_from_contract(
    value: object,
    *,
    legacy_config: registered.SupplierConfig,
    outcome_keys: Sequence[snapshot.CoreOutcomeKey],
) -> tuple[registered.QuerySpec, dict[str, object]]:
    contract = dict(_mapping(value, label="Core v1 query contract"))
    source_snapshot_at = contract.get("source_snapshot_at")
    if type(source_snapshot_at) is not str:
        _fail("Core v1 query contract source snapshot differs")
    try:
        spec = registered.build_query_spec(
            config=legacy_config,
            outcome_keys=snapshot.registered_query_keys(outcome_keys),
            source_snapshot_at=source_snapshot_at,
        )
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc
    expected = _query_contract(spec, outcome_keys=outcome_keys)
    if contract != expected:
        _fail("Core v1 persisted query contract differs")
    return spec, expected


def validate_core_outcome_attempt(
    value: object,
    *,
    config: CoreOutcomeSupplyConfig,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    source_freeze_identity: Mapping[str, object],
    outcome_keys: Sequence[snapshot.CoreOutcomeKey],
    query_contract: Mapping[str, object],
    table_receipts_before_query: Sequence[Mapping[str, object]],
    lease: Mapping[str, object],
) -> dict[str, object]:
    attempt = dict(_mapping(value, label="Core v1 outcome read attempt"))
    _exact_keys(attempt, _ATTEMPT_KEYS, label="Core v1 outcome read attempt")
    _self_hash(
        attempt, field="attempt_sha256", label="Core v1 outcome read attempt"
    )
    keys = _outcome_key_payload(outcome_keys)
    tables = [dict(value) for value in table_receipts_before_query]
    if (
        attempt.get("schema_version") != ATTEMPT_SCHEMA
        or attempt.get("run_id") != config.run_id
        or attempt.get("catalog_identity") != catalog_identity
        or attempt.get("catalog_sha256") != catalog["catalog_sha256"]
        or attempt.get("later_source_freeze_identity") != source_freeze_identity
        or attempt.get("later_source_freeze_sha256")
        != catalog["later_source_freeze_sha256"]
        or attempt.get("outcome_key_count") != len(keys)
        or attempt.get("outcome_keys") != keys
        or attempt.get("outcome_keys_sha256") != canonical_sha256(keys)
        or attempt.get("query_contract") != query_contract
        or attempt.get("query_contract_sha256")
        != canonical_sha256(query_contract)
        or attempt.get("table_receipts_before_query") != tables
        or attempt.get("table_receipt_set_sha256") != canonical_sha256(tables)
        or attempt.get("historical_outcome_lease") != lease
        or attempt.get("uses_realized_outcomes_at_creation") is not False
        or attempt.get("attempt_precedes_query") is not True
        or any(attempt.get(field) is not False for field in (
            "historical_retry_licensed",
            "historical_retune_licensed",
            "graph_mutation_licensed",
            "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("Core v1 outcome read attempt replay differs")
    try:
        shared._utc(attempt.get("started_at"), label="attempt start")  # noqa: SLF001
    except shared.LR8ScoreMapError as exc:
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc
    return attempt


def validate_core_outcome_completion(
    value: object,
    *,
    config: CoreOutcomeSupplyConfig,
    catalog_identity: Mapping[str, object],
    catalog_sha256: str,
    attempt_identity: Mapping[str, object],
    player_source_identity: Mapping[str, object],
    outcome_snapshot_identity: Mapping[str, object],
    outcome_key_count: int,
) -> dict[str, object]:
    completion = dict(_mapping(value, label="Core v1 outcome completion"))
    _exact_keys(completion, _COMPLETION_KEYS, label="Core v1 outcome completion")
    _self_hash(
        completion,
        field="completion_sha256",
        label="Core v1 outcome completion",
    )
    if (
        completion.get("schema_version") != COMPLETION_SCHEMA
        or completion.get("run_id") != config.run_id
        or completion.get("catalog_identity") != catalog_identity
        or completion.get("catalog_sha256") != catalog_sha256
        or completion.get("attempt_identity") != attempt_identity
        or completion.get("player_source_identity") != player_source_identity
        or completion.get("outcome_snapshot_identity")
        != outcome_snapshot_identity
        or completion.get("outcome_key_count") != outcome_key_count
        or completion.get("one_historical_outcome_read") is not True
        or completion.get("independent_source_snapshot_replay_complete") is not True
        or completion.get("rank_available") is not False
        or completion.get("roi_available") is not False
        or completion.get("rank_roi_unavailable_reason")
        != "full_field_standings_and_payout_ladder_not_supplied"
        or completion.get("historical_outcome_lease_release_required") is not True
        or completion.get("lease_release_owner") != LEASE_RELEASE_OWNER
        or any(completion.get(field) is not False for field in (
            "historical_retry_licensed",
            "historical_retune_licensed",
            "graph_mutation_licensed",
            "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("Core v1 outcome completion replay differs")
    return completion


def supply_core_v1_outcome_snapshot(
    *,
    config: CoreOutcomeSupplyConfig,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    source_freeze: Mapping[str, object],
    source_freeze_identity: Mapping[str, object],
    verify_lease: LeaseVerifier,
    read_table_metadata: MetadataReader,
    get_or_create_query: QueryJobGetter,
    publish: Publisher,
    read_known: KnownObjectReader,
    clock: Clock,
) -> CoreOutcomeSupply:
    """Create or recover the sole Core v1 score read and reusable snapshot."""
    retained_config = _validate_config(config)
    if retained_config.enabled is not True:
        _fail("Core v1 outcome supply is default-off")
    if not all(callable(value) for value in (
        verify_lease,
        read_table_metadata,
        get_or_create_query,
        publish,
        read_known,
        clock,
    )):
        _fail("Core v1 outcome supply callback differs")
    try:
        retained_catalog = core.validate_core_v1_catalog(catalog)
        retained_catalog_identity = batch.validate_json_identity(
            retained_catalog,
            catalog_identity,
            label="Core v1 catalog identity",
        )
        outcome_keys = snapshot.project_core_outcome_keys(
            catalog=retained_catalog,
            catalog_identity=retained_catalog_identity,
            source_freeze=source_freeze,
            source_freeze_identity=source_freeze_identity,
        )
    except (
        core.CorpusCoreV1CatalogError,
        snapshot.CorpusCoreV1OutcomeSnapshotError,
        batch.CorpusParametricBatchError,
    ) as exc:
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc
    legacy_config = _legacy_config(
        retained_config, catalog_sha256=retained_catalog["catalog_sha256"]
    )
    uris = {
        "attempt": f"{retained_config.output_root}/read-attempt.json",
        "source": f"{retained_config.output_root}/player-score-source.json",
        "snapshot": f"{retained_config.output_root}/player-outcome-snapshot.json",
        "completion": f"{retained_config.output_root}/completion.json",
    }
    if len(set(uris.values())) != len(uris):
        _fail("Core v1 outcome object URIs alias")
    key_payload = _outcome_key_payload(outcome_keys)

    def replay_attempt(
        retained: tuple[dict[str, object], datetime, dict[str, object]],
    ) -> tuple[
        dict[str, object],
        dict[str, object],
        datetime,
        registered.QuerySpec,
        dict[str, object],
        list[dict[str, object]],
        dict[str, object],
    ]:
        receipt, created_at, reopened = retained
        lease = _validated_lease(
            reopened.get("historical_outcome_lease"),
            legacy_config=legacy_config,
        )
        tables = _table_receipts(reopened.get("table_receipts_before_query"))
        spec, contract = _query_spec_from_contract(
            reopened.get("query_contract"),
            legacy_config=legacy_config,
            outcome_keys=outcome_keys,
        )
        try:
            _, lease_acquired_at = shared._utc(  # noqa: SLF001
                lease["body"]["acquired_at"], label="lease acquired_at"
            )
            _, attempt_started_at = shared._utc(  # noqa: SLF001
                reopened.get("started_at"), label="Core v1 attempt start"
            )
            _, source_snapshot_time = shared._utc(  # noqa: SLF001
                contract["source_snapshot_at"], label="Core v1 source snapshot"
            )
        except shared.LR8ScoreMapError as exc:
            raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc
        if not lease_acquired_at <= attempt_started_at <= source_snapshot_time <= created_at:
            _fail("Core v1 read attempt durable chronology differs")
        attempt = validate_core_outcome_attempt(
            reopened,
            config=retained_config,
            catalog=retained_catalog,
            catalog_identity=retained_catalog_identity,
            source_freeze_identity=source_freeze_identity,
            outcome_keys=outcome_keys,
            query_contract=contract,
            table_receipts_before_query=tables,
            lease=lease,
        )
        attempt_identity = _identity_from_receipt(
            receipt, label="Core v1 read attempt identity"
        )
        return (
            attempt,
            attempt_identity,
            created_at,
            spec,
            contract,
            tables,
            lease,
        )

    def completion_body(
        *,
        attempt_identity: Mapping[str, object],
        player_source_identity: Mapping[str, object],
        outcome_snapshot_identity: Mapping[str, object],
    ) -> dict[str, object]:
        return _with_self_hash({
            "schema_version": COMPLETION_SCHEMA,
            "run_id": retained_config.run_id,
            "catalog_identity": retained_catalog_identity,
            "catalog_sha256": retained_catalog["catalog_sha256"],
            "attempt_identity": attempt_identity,
            "player_source_identity": player_source_identity,
            "outcome_snapshot_identity": outcome_snapshot_identity,
            "outcome_key_count": len(outcome_keys),
            "one_historical_outcome_read": True,
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

    known_completion = _read_known(
        read_known,
        uri=uris["completion"],
        label="Core v1 outcome snapshot completion",
    )
    known_attempt = _read_known(
        read_known, uri=uris["attempt"], label="Core v1 outcome read attempt"
    )
    known_source = _read_known(
        read_known, uri=uris["source"], label="Core v1 realized player source"
    )
    known_snapshot = _read_known(
        read_known, uri=uris["snapshot"], label="Core v1 player outcome snapshot"
    )
    if known_completion is not None and any(
        value is None for value in (known_attempt, known_source, known_snapshot)
    ):
        _fail("Core v1 completion is missing a required predecessor")
    if known_source is not None and known_attempt is None:
        _fail("Core v1 player source is missing its read attempt")
    if known_snapshot is not None and known_source is None:
        _fail("Core v1 outcome snapshot is missing its player source")

    if known_attempt is None:
        lease_before = _validated_lease(
            verify_lease(), legacy_config=legacy_config
        )
        started_text, started_at = _now(clock, label="Core v1 attempt")
        try:
            _, lease_acquired = shared._utc(  # noqa: SLF001
                lease_before["body"]["acquired_at"], label="lease acquired_at"
            )
        except shared.LR8ScoreMapError as exc:
            raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc
        if started_at < lease_acquired:
            _fail("Core v1 attempt predates the historical-outcome lease")
        source_snapshot_at, source_snapshot_time = _now(
            clock, label="Core v1 source snapshot"
        )
        if source_snapshot_time < started_at:
            _fail("Core v1 source snapshot predates the read attempt")
        spec = registered.build_query_spec(
            config=legacy_config,
            outcome_keys=snapshot.registered_query_keys(outcome_keys),
            source_snapshot_at=source_snapshot_at,
        )
        query_contract = _query_contract(spec, outcome_keys=outcome_keys)
        tables = (registered.SKILL_TABLE, registered.DST_TABLE)
        before = [
            _table_receipt(read_table_metadata(table), table=table)
            for table in tables
        ]
        attempt_payload = _with_self_hash({
            "schema_version": ATTEMPT_SCHEMA,
            "run_id": retained_config.run_id,
            "catalog_identity": retained_catalog_identity,
            "catalog_sha256": retained_catalog["catalog_sha256"],
            "later_source_freeze_identity": source_freeze_identity,
            "later_source_freeze_sha256": retained_catalog[
                "later_source_freeze_sha256"
            ],
            "outcome_key_count": len(outcome_keys),
            "outcome_keys": key_payload,
            "outcome_keys_sha256": canonical_sha256(key_payload),
            "query_contract": query_contract,
            "query_contract_sha256": canonical_sha256(query_contract),
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
        known_attempt = _publish_or_recover(
            publish,
            read_known,
            uri=uris["attempt"],
            payload=attempt_payload,
            earliest=source_snapshot_time,
            label="Core v1 outcome read attempt",
        )

    (
        attempt,
        attempt_identity,
        attempt_created_at,
        spec,
        query_contract,
        before,
        lease_before,
    ) = replay_attempt(known_attempt)
    source_snapshot_at = str(query_contract["source_snapshot_at"])

    if known_source is None:
        lease_current = _validated_lease(
            verify_lease(), legacy_config=legacy_config
        )
        if canonical_json_bytes(lease_current) != canonical_json_bytes(lease_before):
            _fail("Core v1 historical-outcome lease changed before the query")
        tables = (registered.SKILL_TABLE, registered.DST_TABLE)
        current_before = [
            _table_receipt(read_table_metadata(table), table=table)
            for table in tables
        ]
        if current_before != before:
            _fail("Core v1 outcome table metadata changed before the query")
        try:
            query_value = get_or_create_query(spec)
        except Exception as exc:
            raise CorpusCoreV1OutcomeSupplyError(
                "Core v1 fixed-ID outcome query failed"
            ) from exc
        if not isinstance(query_value, CoreOutcomeQueryResult):
            _fail("Core v1 query callback returned the wrong result type")
        if (
            type(query_value.disposition) is not str
            or query_value.disposition not in {"created", "recovered"}
        ):
            _fail("Core v1 query job disposition differs")
        queried = query_value.result
        if not isinstance(queried, shared.QueryResult):
            _fail("Core v1 outcome query returned the wrong result type")
        job_receipt, query_ended = _job_receipt(
            queried.job_receipt, spec=spec, not_before=attempt_created_at
        )
        if job_receipt["cache_hit"] is not False:
            _fail("Core v1 outcome query used cache")
        try:
            source_rows = snapshot.normalize_authoritative_query_rows(
                queried.rows, outcome_keys=outcome_keys
            )
        except snapshot.CorpusCoreV1OutcomeSnapshotError as exc:
            raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc
        after = [
            _table_receipt(read_table_metadata(table), table=table)
            for table in tables
        ]
        if before != after:
            _fail("Core v1 outcome table metadata changed during the query")
        lease_after = _validated_lease(
            verify_lease(), legacy_config=legacy_config
        )
        if canonical_json_bytes(lease_before) != canonical_json_bytes(lease_after):
            _fail("Core v1 historical-outcome lease changed during the query")
        source_body: dict[str, object] = {
            "schema_version": snapshot.PLAYER_SOURCE_SCHEMA,
            "catalog_sha256": retained_catalog["catalog_sha256"],
            "attempt": attempt,
            "attempt_identity": attempt_identity,
            "attempt_created_at": attempt_created_at.isoformat(),
            "later_source_freeze_identity": source_freeze_identity,
            "later_source_freeze_sha256": retained_catalog[
                "later_source_freeze_sha256"
            ],
            "outcome_key_count": len(outcome_keys),
            "outcome_keys_sha256": canonical_sha256(key_payload),
            "query_contract": query_contract,
            "query_contract_sha256": canonical_sha256(query_contract),
            "query_job_id": spec.job_id,
            "query_job_receipt": job_receipt,
            "query_job_disposition": query_value.disposition,
            "source_snapshot_at": source_snapshot_at,
            "table_receipts_before_query": before,
            "table_receipts_after_query": after,
            "table_receipt_set_sha256": canonical_sha256(before),
            "historical_outcome_lease_before_query": lease_before,
            "historical_outcome_lease_after_query": lease_after,
            "historical_outcome_lease_sha256": canonical_sha256(lease_before),
            "row_fields": [
                "source_ordinal",
                "season",
                "week",
                "slate_id",
                "source_kind",
                "source_key",
                "player_id",
                "realized_score_micro",
            ],
            "row_count": len(source_rows),
            "rows_sha256": canonical_sha256(source_rows),
            "rows": source_rows,
            "one_exact_query": True,
            "query_cache_used": False,
            "table_metadata_stable_during_query": True,
            "historical_outcome_lease_unchanged_during_query": True,
            "full_field_standings_included": False,
            "payout_ladder_included": False,
            "production_change_licensed": False,
            "decision_authority": False,
        }
        player_source = _with_self_hash(source_body, field="source_sha256")
        known_source = _publish_or_recover(
            publish,
            read_known,
            uri=uris["source"],
            payload=player_source,
            earliest=query_ended,
            label="Core v1 realized player source",
        )

    source_receipt, source_created_at, reopened_source = known_source
    player_source_identity = _identity_from_receipt(
        source_receipt, label="Core v1 realized player source identity"
    )
    if (
        reopened_source.get("attempt") != attempt
        or reopened_source.get("attempt_identity") != attempt_identity
        or reopened_source.get("attempt_created_at") != attempt_created_at.isoformat()
    ):
        _fail("Core v1 player source attempt binding differs")
    replayed_job_receipt, replayed_query_ended = _job_receipt(
        reopened_source.get("query_job_receipt"),
        spec=spec,
        not_before=attempt_created_at,
    )
    if (
        reopened_source.get("query_job_receipt") != replayed_job_receipt
        or source_created_at < replayed_query_ended
    ):
        _fail("Core v1 player source/query durable chronology differs")
    try:
        snapshot.validate_core_player_source(
            reopened_source,
            identity=player_source_identity,
            catalog=retained_catalog,
            catalog_identity=retained_catalog_identity,
            outcome_keys=outcome_keys,
        )
        outcome_snapshot = snapshot.build_core_outcome_snapshot(
            catalog=retained_catalog,
            catalog_identity=retained_catalog_identity,
            player_source=reopened_source,
            player_source_identity=player_source_identity,
            outcome_keys=outcome_keys,
        )
    except snapshot.CorpusCoreV1OutcomeSnapshotError as exc:
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc

    if known_snapshot is None:
        known_snapshot = _publish_or_recover(
            publish,
            read_known,
            uri=uris["snapshot"],
            payload=outcome_snapshot,
            earliest=source_created_at,
            label="Core v1 player outcome snapshot",
        )
    snapshot_receipt, snapshot_created_at, reopened_snapshot = known_snapshot
    outcome_snapshot_identity = _identity_from_receipt(
        snapshot_receipt, label="Core v1 outcome snapshot identity"
    )
    try:
        snapshot.validate_core_outcome_snapshot(
            reopened_snapshot,
            identity=outcome_snapshot_identity,
            catalog=retained_catalog,
            catalog_identity=retained_catalog_identity,
            player_source=reopened_source,
            player_source_identity=player_source_identity,
            outcome_keys=outcome_keys,
        )
    except snapshot.CorpusCoreV1OutcomeSnapshotError as exc:
        raise CorpusCoreV1OutcomeSupplyError(str(exc)) from exc
    if snapshot_created_at < source_created_at:
        _fail("Core v1 outcome snapshot predates its player source")

    expected_completion = completion_body(
        attempt_identity=attempt_identity,
        player_source_identity=player_source_identity,
        outcome_snapshot_identity=outcome_snapshot_identity,
    )
    if known_completion is None:
        known_completion = _publish_or_recover(
            publish,
            read_known,
            uri=uris["completion"],
            payload=expected_completion,
            earliest=snapshot_created_at,
            label="Core v1 outcome snapshot completion",
        )
    completion_receipt, completion_created_at, reopened_completion = known_completion
    if completion_created_at < snapshot_created_at:
        _fail("Core v1 outcome completion predates its snapshot")
    completion_identity = _identity_from_receipt(
        completion_receipt, label="Core v1 outcome completion identity"
    )
    completion = validate_core_outcome_completion(
        reopened_completion,
        config=retained_config,
        catalog_identity=retained_catalog_identity,
        catalog_sha256=retained_catalog["catalog_sha256"],
        attempt_identity=attempt_identity,
        player_source_identity=player_source_identity,
        outcome_snapshot_identity=outcome_snapshot_identity,
        outcome_key_count=len(outcome_keys),
    )
    if completion != expected_completion:
        _fail("Core v1 outcome completion exact recovery differs")
    return CoreOutcomeSupply(
        attempt=attempt,
        attempt_identity=attempt_identity,
        player_source=reopened_source,
        player_source_identity=player_source_identity,
        outcome_snapshot=reopened_snapshot,
        outcome_snapshot_identity=outcome_snapshot_identity,
        completion=completion,
        completion_identity=completion_identity,
    )


__all__ = [
    "ATTEMPT_SCHEMA",
    "COMPLETION_SCHEMA",
    "CoreOutcomeQueryResult",
    "CoreOutcomeSupply",
    "CoreOutcomeSupplyConfig",
    "CorpusCoreV1OutcomeSupplyError",
    "LEASE_RELEASE_OWNER",
    "canonical_json_bytes",
    "canonical_sha256",
    "supply_core_v1_outcome_snapshot",
    "validate_core_outcome_attempt",
    "validate_core_outcome_completion",
]
