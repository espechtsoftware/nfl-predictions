"""Exact player/DST projection and reusable outcomes for Core v1.

This module contains no warehouse, object-store, lease, or process callback.
It closes the outcome key union from an already-frozen Core v1 book catalog
and its common later-source freeze, adapts the registered corpus score query's
exact row law, and builds one reusable integer-micro-DK snapshot.  The actual
one-query/lease/create-once transaction remains a thin transport concern.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_core_v1_catalog as core
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_realized_grading as legacy_grading
from nfl_dfs.research import corpus_realized_outcome_transport as registered
from nfl_dfs.research import lr8_later_period_source as later_source
from nfl_dfs.research import lr8_label_score_map as shared_score
from nfl_dfs.research.corpus_batch_evidence_contract import MICRO_DK_PER_POINT


OUTCOME_SNAPSHOT_SCHEMA: Final = "corpus-core-v1-player-outcome-snapshot/v1"
PLAYER_SOURCE_SCHEMA: Final = "corpus-core-v1-realized-player-source/v1"
READ_ATTEMPT_SCHEMA: Final = "corpus-core-v1-realized-read-attempt/v1"
EXPECTED_SOURCE_SLATE_COUNT: Final = 54

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_GIT_SHA: Final = re.compile(r"[0-9a-f]{40}")
_IMAGE_DIGEST: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_READ_ATTEMPT_KEYS: Final = frozenset({
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
_SNAPSHOT_KEYS: Final = frozenset({
    "schema_version",
    "catalog_sha256",
    "score_unit",
    "micro_dk_per_point",
    "source_identity",
    "row_count",
    "row_keys_sha256",
    "rows_sha256",
    "rows",
    "full_field_standings_included",
    "payout_ladder_included",
    "outcome_snapshot_sha256",
})
_SNAPSHOT_ROW_KEYS: Final = frozenset({
    "source_ordinal",
    "season",
    "week",
    "slate_id",
    "player_id",
    "realized_score_micro",
})
_PLAYER_SOURCE_KEYS: Final = frozenset({
    "schema_version",
    "catalog_sha256",
    "attempt",
    "attempt_identity",
    "attempt_created_at",
    "later_source_freeze_identity",
    "later_source_freeze_sha256",
    "outcome_key_count",
    "outcome_keys_sha256",
    "query_contract",
    "query_contract_sha256",
    "query_job_id",
    "query_job_receipt",
    "query_job_disposition",
    "source_snapshot_at",
    "table_receipts_before_query",
    "table_receipts_after_query",
    "table_receipt_set_sha256",
    "historical_outcome_lease_before_query",
    "historical_outcome_lease_after_query",
    "historical_outcome_lease_sha256",
    "row_fields",
    "row_count",
    "rows_sha256",
    "rows",
    "one_exact_query",
    "query_cache_used",
    "table_metadata_stable_during_query",
    "historical_outcome_lease_unchanged_during_query",
    "full_field_standings_included",
    "payout_ladder_included",
    "production_change_licensed",
    "decision_authority",
    "source_sha256",
})
_PLAYER_SOURCE_ROW_KEYS: Final = frozenset({
    "source_ordinal",
    "season",
    "week",
    "slate_id",
    "source_kind",
    "source_key",
    "player_id",
    "realized_score_micro",
})
_PLAYER_SOURCE_ROW_FIELDS: Final = (
    "source_ordinal",
    "season",
    "week",
    "slate_id",
    "source_kind",
    "source_key",
    "player_id",
    "realized_score_micro",
)


class CorpusCoreV1OutcomeSnapshotError(ValueError):
    """The exact Core v1 player/DST outcome boundary failed closed."""


@dataclass(frozen=True, slots=True)
class CoreOutcomeKey:
    source_ordinal: int
    season: int
    week: int
    slate_id: str
    player_id: str
    source_kind: str
    source_key: str


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _fail(message: str) -> None:
    raise CorpusCoreV1OutcomeSnapshotError(message)


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
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


def _exact_int(
    value: object, *, label: str, minimum: int | None = None,
) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        _fail(f"{label} must be an exact integer{suffix}")
    return value


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a canonical nonempty string")
    return value


def _sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc


def _json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _validated_catalog(
    value: Mapping[str, object], *, identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    try:
        catalog = core.validate_core_v1_catalog(value)
    except core.CorpusCoreV1CatalogError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc
    if identity is not None:
        _json_identity(catalog, identity, label="Core v1 catalog identity")
    return catalog


def _required_player_ids(catalog: Mapping[str, object]) -> list[set[str]]:
    slates = _sequence(catalog.get("slates"), label="Core v1 catalog slates")
    if len(slates) != EXPECTED_SOURCE_SLATE_COUNT:
        _fail("Core v1 catalog must contain exactly 54 slates")
    result: list[set[str]] = []
    for source_ordinal, raw_slate in enumerate(slates):
        slate = _mapping(raw_slate, label=f"catalog slate[{source_ordinal}]")
        if slate.get("source_ordinal") != source_ordinal:
            _fail("Core v1 catalog source ordinals are reordered")
        population = _mapping(
            slate.get("union_population"), label="catalog union population"
        )
        rosters = _sequence(population.get("rosters"), label="union rosters")
        players: set[str] = set()
        for raw_roster in rosters:
            roster = _sequence(raw_roster, label="union roster")
            if len(roster) != 9:
                _fail("catalog union roster is not exact nine")
            players.update(_string(value, label="union player ID") for value in roster)
        if not players:
            _fail("catalog union player set is empty")
        result.append(players)
    return result


def project_core_outcome_keys(
    *,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    source_freeze: Mapping[str, object],
    source_freeze_identity: Mapping[str, object],
) -> tuple[CoreOutcomeKey, ...]:
    """Close the exact skill/DST source-key union before any score query."""
    retained_catalog = _validated_catalog(catalog, identity=catalog_identity)
    expected_freeze_sha256 = _sha(
        retained_catalog.get("later_source_freeze_sha256"),
        label="catalog later-source freeze SHA",
    )
    expected_freeze_identity = _identity(
        retained_catalog.get("later_source_freeze_identity"),
        label="catalog later-source freeze identity",
    )
    supplied_freeze_identity = _identity(
        source_freeze_identity, label="supplied later-source freeze identity"
    )
    if supplied_freeze_identity != expected_freeze_identity:
        _fail("supplied later-source freeze identity differs from the catalog")
    try:
        frozen = later_source.validate_source_freeze(
            source_freeze, expected_freeze_sha256=expected_freeze_sha256
        )
    except later_source.LR8LaterSourceError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(
            "later-source freeze replay differs"
        ) from exc
    _json_identity(frozen, supplied_freeze_identity, label="later-source freeze")

    catalog_slates = _sequence(
        retained_catalog.get("slates"), label="Core v1 catalog slates"
    )
    source_slates = _sequence(frozen.get("slates"), label="later-source slates")
    required_by_slate = _required_player_ids(retained_catalog)
    if not (
        len(catalog_slates)
        == len(source_slates)
        == len(required_by_slate)
        == EXPECTED_SOURCE_SLATE_COUNT
    ):
        _fail("catalog/later-source 54-slate coverage differs")

    outcome_keys: list[CoreOutcomeKey] = []
    for source_ordinal, (raw_catalog_slate, raw_source_slate, required) in enumerate(
        zip(catalog_slates, source_slates, required_by_slate, strict=True)
    ):
        catalog_slate = _mapping(
            raw_catalog_slate, label=f"catalog slate[{source_ordinal}]"
        )
        source_slate = _mapping(
            raw_source_slate, label=f"later-source slate[{source_ordinal}]"
        )
        slate = _mapping(catalog_slate.get("slate"), label="catalog slate key")
        if (
            source_slate.get("season") != slate.get("season")
            or source_slate.get("week") != slate.get("week")
            or source_slate.get("slate_id") != slate.get("slate_id")
        ):
            _fail("catalog/later-source slate identity differs")
        raw_players = _sequence(
            source_slate.get("catalog"), label="later-source player catalog"
        )
        players: dict[str, tuple[str, str]] = {}
        observed_ids: list[str] = []
        for raw_player in raw_players:
            player = _mapping(raw_player, label="later-source catalog player")
            player_id = _string(player.get("id"), label="catalog player ID")
            position = _string(player.get("pos"), label="catalog player position")
            team = _string(player.get("team"), label="catalog player team")
            observed_ids.append(player_id)
            players[player_id] = (position.upper(), team.upper())
        if (
            observed_ids != sorted(observed_ids)
            or len(players) != len(observed_ids)
            or not required <= set(players)
        ):
            _fail("catalog union is not covered by the frozen player catalog")
        for player_id in sorted(required):
            position, team = players[player_id]
            source_kind = "dst" if position == "DST" else "skill"
            outcome_keys.append(CoreOutcomeKey(
                source_ordinal=source_ordinal,
                season=_exact_int(slate.get("season"), label="slate season", minimum=2000),
                week=_exact_int(slate.get("week"), label="slate week", minimum=1),
                slate_id=_string(slate.get("slate_id"), label="slate ID"),
                player_id=player_id,
                source_kind=source_kind,
                source_key=team if source_kind == "dst" else player_id,
            ))
    source_keys = [
        (row.season, row.week, row.source_kind, row.source_key)
        for row in outcome_keys
    ]
    if (
        len(source_keys) != len(set(source_keys))
        or not any(row.source_kind == "skill" for row in outcome_keys)
        or not any(row.source_kind == "dst" for row in outcome_keys)
    ):
        _fail("Core v1 player/DST source-key union differs")
    return tuple(sorted(
        outcome_keys, key=lambda row: (row.source_ordinal, row.player_id)
    ))


def registered_query_keys(
    values: Sequence[CoreOutcomeKey],
) -> tuple[registered.OutcomeKey, ...]:
    """Adapt Core source ordinals to the existing registered query row law."""
    rows = tuple(values)
    if not rows:
        _fail("registered query key union cannot be empty")
    return tuple(registered.OutcomeKey(
        task_index=row.source_ordinal,
        season=row.season,
        week=row.week,
        slate_id=row.slate_id,
        player_id=row.player_id,
        source_kind=row.source_kind,
        source_key=row.source_key,
    ) for row in rows)


def _outcome_key_payload(
    values: Sequence[CoreOutcomeKey],
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


def _canonical_utc(value: object, *, label: str) -> str:
    try:
        retained, _ = shared_score._utc(value, label=label)  # noqa: SLF001
    except shared_score.LR8ScoreMapError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc
    return retained


def core_query_contract(
    *,
    outcome_keys: Sequence[CoreOutcomeKey],
    query_job_id: str,
    source_snapshot_at: str,
) -> dict[str, object]:
    """Bind the registered SQL, parameters and union to one no-cache query."""
    keys = tuple(outcome_keys)
    job_id = _string(query_job_id, label="Core v1 query job ID")
    snapshot = _canonical_utc(
        source_snapshot_at, label="Core v1 query source snapshot"
    )
    registered_keys = registered_query_keys(keys)
    skill = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in registered_keys if row.source_kind == "skill"
    )
    dst = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in registered_keys if row.source_kind == "dst"
    )
    if (
        not skill
        or not dst
        or len(skill) + len(dst) != len(registered_keys)
        or len(skill) != len(set(skill))
        or len(dst) != len(set(dst))
    ):
        _fail("Core v1 query player/DST union differs")
    parameter_payload = [
        {
            "name": "source_snapshot_at",
            "type": "TIMESTAMP",
            "array": False,
            "value": snapshot,
        },
        {
            "name": "target_seasons",
            "type": "INT64",
            "array": True,
            "value": sorted({row.season for row in registered_keys}),
        },
        {
            "name": "skill_keys",
            "type": "STRING",
            "array": True,
            "value": skill,
        },
        {
            "name": "dst_keys",
            "type": "STRING",
            "array": True,
            "value": dst,
        },
    ]
    registered_union = [{
        "task_index": row.task_index,
        "season": row.season,
        "week": row.week,
        "slate_id": row.slate_id,
        "source_kind": row.source_kind,
        "source_key": row.source_key,
        "player_id": row.player_id,
    } for row in registered_keys]
    return {
        "schema_version": registered.QUERY_CONTRACT_SCHEMA,
        "job_id": job_id,
        "location": registered.LOCATION,
        "sql_sha256": registered.AUTHORITATIVE_SCORE_SQL_SHA256,
        "parameters": parameter_payload,
        "parameters_sha256": canonical_sha256(parameter_payload),
        "union_keys_sha256": canonical_sha256(registered_union),
        "tables": [registered.SKILL_TABLE, registered.DST_TABLE],
        "selected_columns": list(registered.QUERY_ROW_FIELDS),
        "source_snapshot_at": snapshot,
        "outcome_key_count": len(keys),
        "outcome_keys_sha256": canonical_sha256(_outcome_key_payload(keys)),
        "query_count": 1,
        "use_query_cache": False,
    }


def core_query_contract_sha256(
    *,
    outcome_keys: Sequence[CoreOutcomeKey],
    query_job_id: str,
    source_snapshot_at: str,
) -> str:
    return canonical_sha256(core_query_contract(
        outcome_keys=outcome_keys,
        query_job_id=query_job_id,
        source_snapshot_at=source_snapshot_at,
    ))


def _validated_outcome_keys(
    values: Sequence[CoreOutcomeKey], *, catalog: Mapping[str, object],
) -> tuple[CoreOutcomeKey, ...]:
    rows = tuple(values)
    catalog_slates = _sequence(catalog.get("slates"), label="catalog slates")
    required = _required_player_ids(catalog)
    required_player_keys = sorted(
        (source_ordinal, player_id)
        for source_ordinal, players in enumerate(required)
        for player_id in players
    )
    player_keys: list[tuple[int, str]] = []
    query_keys: list[tuple[int, int, str, str]] = []
    for ordinal, row in enumerate(rows):
        if not isinstance(row, CoreOutcomeKey):
            _fail(f"outcome key[{ordinal}] is not a CoreOutcomeKey")
        source_ordinal = _exact_int(
            row.source_ordinal,
            label=f"outcome key[{ordinal}].source_ordinal",
            minimum=0,
        )
        if source_ordinal >= len(catalog_slates):
            _fail(f"outcome key[{ordinal}] source ordinal is outside the catalog")
        catalog_slate = _mapping(
            catalog_slates[source_ordinal], label="outcome-key catalog slate"
        )
        slate = _mapping(catalog_slate.get("slate"), label="outcome-key slate")
        season = _exact_int(
            row.season, label=f"outcome key[{ordinal}].season", minimum=2000
        )
        week = _exact_int(
            row.week, label=f"outcome key[{ordinal}].week", minimum=1
        )
        slate_id = _string(
            row.slate_id, label=f"outcome key[{ordinal}].slate_id"
        )
        player_id = _string(
            row.player_id, label=f"outcome key[{ordinal}].player_id"
        )
        source_kind = _string(
            row.source_kind, label=f"outcome key[{ordinal}].source_kind"
        )
        source_key = _string(
            row.source_key, label=f"outcome key[{ordinal}].source_key"
        )
        if source_kind not in {"skill", "dst"}:
            _fail(f"outcome key[{ordinal}] source kind differs")
        if (
            season != slate.get("season")
            or week != slate.get("week")
            or slate_id != slate.get("slate_id")
        ):
            _fail(f"outcome key[{ordinal}] slate identity differs from the catalog")
        player_keys.append((source_ordinal, player_id))
        query_keys.append((season, week, source_kind, source_key))
    if (
        player_keys != required_player_keys
        or len(player_keys) != len(set(player_keys))
        or len(query_keys) != len(set(query_keys))
        or not any(row.source_kind == "skill" for row in rows)
        or not any(row.source_kind == "dst" for row in rows)
    ):
        _fail("outcome keys do not exactly equal the Core v1 player/DST union")
    return rows


def normalize_authoritative_query_rows(
    values: object, *, outcome_keys: Sequence[CoreOutcomeKey],
) -> list[dict[str, object]]:
    """Reuse the registered exact query-row and micro-DK conversion law."""
    try:
        retained = registered._query_rows(  # noqa: SLF001
            values, outcome_keys=registered_query_keys(outcome_keys)
        )
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc
    return [{
        "source_ordinal": row["task_index"],
        "season": row["season"],
        "week": row["week"],
        "slate_id": row["slate_id"],
        "source_kind": row["source_kind"],
        "source_key": row["source_key"],
        "player_id": row["player_id"],
        "realized_score_micro": row["realized_score_micro"],
    } for row in retained]


def _normalize_player_source_row(
    value: object, *, expected: CoreOutcomeKey, label: str,
) -> dict[str, object]:
    row = _mapping(value, label=label)
    _exact_keys(row, _PLAYER_SOURCE_ROW_KEYS, label=label)
    score = _exact_int(
        row.get("realized_score_micro"),
        label=f"{label}.realized_score_micro",
    )
    if abs(score) > legacy_grading.MAX_ABS_PLAYER_SCORE_MICRO:
        _fail(f"{label} realized score exceeds exact nine-player sum bounds")
    result = {
        "source_ordinal": _exact_int(
            row.get("source_ordinal"),
            label=f"{label}.source_ordinal",
            minimum=0,
        ),
        "season": _exact_int(
            row.get("season"), label=f"{label}.season", minimum=2000
        ),
        "week": _exact_int(row.get("week"), label=f"{label}.week", minimum=1),
        "slate_id": _string(row.get("slate_id"), label=f"{label}.slate_id"),
        "source_kind": _string(
            row.get("source_kind"), label=f"{label}.source_kind"
        ),
        "source_key": _string(
            row.get("source_key"), label=f"{label}.source_key"
        ),
        "player_id": _string(row.get("player_id"), label=f"{label}.player_id"),
        "realized_score_micro": score,
    }
    expected_payload = {
        "source_ordinal": expected.source_ordinal,
        "season": expected.season,
        "week": expected.week,
        "slate_id": expected.slate_id,
        "source_kind": expected.source_kind,
        "source_key": expected.source_key,
        "player_id": expected.player_id,
    }
    if {key: result[key] for key in expected_payload} != expected_payload:
        _fail(f"{label} differs from its frozen player/DST outcome key")
    return result


def _normalized_query_job_receipt(
    value: object,
    *,
    query_contract: Mapping[str, object],
    not_before: datetime,
) -> dict[str, object]:
    spec = shared_score.QuerySpec(
        sql=registered.AUTHORITATIVE_SCORE_SQL,
        parameters=(),
        job_id=str(query_contract["job_id"]),
        location=str(query_contract["location"]),
        sql_sha256=str(query_contract["sql_sha256"]),
        parameters_sha256=str(query_contract["parameters_sha256"]),
        catalog_keys_sha256=str(query_contract["union_keys_sha256"]),
    )
    try:
        retained, _ = shared_score._job_receipt(  # noqa: SLF001
            value,
            spec=spec,
            not_before=not_before,
        )
    except shared_score.LR8ScoreMapError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc
    if retained["cache_hit"] is not False:
        _fail("Core v1 query job receipt used cache")
    return retained


def _normalized_table_receipts(value: object) -> list[dict[str, object]]:
    rows = _sequence(value, label="Core v1 outcome table receipts")
    tables = (registered.SKILL_TABLE, registered.DST_TABLE)
    if len(rows) != len(tables):
        _fail("Core v1 outcome table receipt count differs")
    result: list[dict[str, object]] = []
    for raw, table in zip(rows, tables, strict=True):
        try:
            result.append(registered._table_receipt(raw, table=table))  # noqa: SLF001
        except registered.CorpusRealizedOutcomeError as exc:
            raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc
    return result


def _normalized_lease(value: object) -> dict[str, object]:
    lease = _mapping(value, label="Core v1 historical-outcome lease")
    _exact_keys(
        lease,
        frozenset({"body", "object_receipt"}),
        label="Core v1 historical-outcome lease",
    )
    body = dict(_mapping(lease.get("body"), label="historical lease body"))
    _exact_keys(
        body,
        frozenset({
            "version", "run_id", "job", "code_sha", "image", "acquired_at",
        }),
        label="historical lease body",
    )
    acquired_at = _canonical_utc(
        body.get("acquired_at"), label="historical lease acquired_at"
    )
    code_sha = body.get("code_sha")
    image = body.get("image")
    if type(code_sha) is not str or _GIT_SHA.fullmatch(code_sha) is None:
        _fail("lease code SHA must be one Git SHA-1")
    if type(image) is not str or _IMAGE_DIGEST.fullmatch(image) is None:
        _fail("lease image must be immutable")
    normalized_body = {
        "version": _string(body.get("version"), label="lease version"),
        "run_id": _string(body.get("run_id"), label="lease run ID"),
        "job": _string(body.get("job"), label="lease job"),
        "code_sha": code_sha,
        "image": image,
        "acquired_at": acquired_at,
    }
    if normalized_body["version"] != shared_score.adapter.HISTORICAL_OUTCOME_LEASE_VERSION:
        _fail("historical lease version differs")
    receipt_raw = _mapping(
        lease.get("object_receipt"), label="historical lease receipt"
    )
    if set(receipt_raw) != {"uri", "generation", "sha256", "bytes", "create_only"}:
        _fail("historical lease receipt fields differ")
    receipt_identity = _identity(
        {key: receipt_raw[key] for key in ("uri", "generation", "sha256", "bytes")},
        label="historical lease object identity",
    )
    if receipt_raw.get("create_only") is not True:
        _fail("historical lease receipt is not create-only")
    if receipt_identity["uri"] != shared_score.adapter.HISTORICAL_OUTCOME_LEASE_URI:
        _fail("historical lease URI differs")
    raw = shared_score.canonical_json(normalized_body)
    if (
        receipt_identity["sha256"] != sha256(raw).hexdigest()
        or receipt_identity["bytes"] != len(raw)
    ):
        _fail("historical lease receipt does not bind its body")
    return {
        "body": normalized_body,
        "object_receipt": {**receipt_identity, "create_only": True},
    }


def validate_core_player_source(
    value: object,
    *,
    identity: Mapping[str, object],
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    outcome_keys: Sequence[CoreOutcomeKey],
) -> tuple[
    dict[str, object],
    dict[str, object],
    list[dict[str, object]],
]:
    """Bind retained realized rows to their exact persisted source object."""
    retained_catalog = _validated_catalog(catalog, identity=catalog_identity)
    retained_keys = _validated_outcome_keys(
        outcome_keys, catalog=retained_catalog
    )
    source = dict(_mapping(value, label="Core v1 realized player source"))
    _exact_keys(source, _PLAYER_SOURCE_KEYS, label="Core v1 realized player source")
    retained_identity = _json_identity(
        source, identity, label="Core v1 realized player source identity"
    )
    _self_hash(
        source,
        field="source_sha256",
        label="Core v1 realized player source",
    )
    raw_rows = _sequence(source.get("rows"), label="realized player source rows")
    expected_by_query_key = {
        (row.season, row.week, row.source_kind, row.source_key): row
        for row in retained_keys
    }
    if len(raw_rows) != len(expected_by_query_key):
        _fail("realized player source row count differs from the frozen union")
    rows: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(raw_rows):
        raw = _mapping(raw_row, label=f"realized player source row[{ordinal}]")
        query_key = (
            raw.get("season"),
            raw.get("week"),
            raw.get("source_kind"),
            raw.get("source_key"),
        )
        expected = expected_by_query_key.get(query_key)
        if expected is None:
            _fail("realized player source contains a non-union query key")
        rows.append(_normalize_player_source_row(
            raw,
            expected=expected,
            label=f"realized player source row[{ordinal}]",
        ))
    observed_query_keys = [
        (row["season"], row["week"], row["source_kind"], row["source_key"])
        for row in rows
    ]
    if observed_query_keys != sorted(expected_by_query_key):
        _fail("realized player source rows are not the exact ordered query union")
    expected_freeze_identity = _identity(
        retained_catalog.get("later_source_freeze_identity"),
        label="catalog later-source freeze identity",
    )
    expected_freeze_sha256 = _sha(
        retained_catalog.get("later_source_freeze_sha256"),
        label="catalog later-source freeze SHA",
    )
    attempt = dict(_mapping(
        source.get("attempt"), label="Core v1 source-bound read attempt"
    ))
    _exact_keys(
        attempt,
        _READ_ATTEMPT_KEYS,
        label="Core v1 source-bound read attempt",
    )
    _self_hash(
        attempt,
        field="attempt_sha256",
        label="Core v1 source-bound read attempt",
    )
    attempt_identity = _json_identity(
        attempt,
        source.get("attempt_identity"),
        label="Core v1 source-bound read attempt identity",
    )
    attempt_created_text = _canonical_utc(
        source.get("attempt_created_at"),
        label="Core v1 source-bound read attempt creation",
    )
    try:
        _, attempt_started = shared_score._utc(  # noqa: SLF001
            attempt.get("started_at"), label="Core v1 read attempt start"
        )
        _, attempt_created = shared_score._utc(  # noqa: SLF001
            attempt_created_text, label="Core v1 read attempt creation"
        )
    except shared_score.LR8ScoreMapError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc
    if attempt_created < attempt_started:
        _fail("Core v1 read attempt creation predates its start")

    table_receipts_before = _normalized_table_receipts(
        source.get("table_receipts_before_query")
    )
    table_receipts_after = _normalized_table_receipts(
        source.get("table_receipts_after_query")
    )
    historical_lease_before = _normalized_lease(
        source.get("historical_outcome_lease_before_query")
    )
    historical_lease_after = _normalized_lease(
        source.get("historical_outcome_lease_after_query")
    )
    attempt_lease = _normalized_lease(attempt.get("historical_outcome_lease"))
    lease_body = historical_lease_before["body"]
    run_id = _string(attempt.get("run_id"), label="Core v1 read attempt run ID")
    if lease_body["run_id"] != run_id:
        _fail("Core v1 read attempt and historical lease run IDs differ")
    try:
        expected_job_id = registered.deterministic_query_job_id(
            registered.SupplierConfig(
                run_id=run_id,
                job=str(lease_body["job"]),
                code_sha=str(lease_body["code_sha"]),
                image=str(lease_body["image"]),
                expected_batch_acceptance_object_sha256=str(
                    retained_catalog["catalog_sha256"]
                ),
                enabled=True,
            )
        )
    except registered.CorpusRealizedOutcomeError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc
    query_job_id = _string(
        source.get("query_job_id"), label="realized player source query job ID"
    )
    if query_job_id != expected_job_id:
        _fail("Core v1 realized player source query job ID differs")
    source_snapshot_at = _canonical_utc(
        source.get("source_snapshot_at"),
        label="realized player source snapshot time",
    )
    try:
        _, source_snapshot_time = shared_score._utc(  # noqa: SLF001
            source_snapshot_at, label="Core v1 source snapshot"
        )
        _, lease_acquired_at = shared_score._utc(  # noqa: SLF001
            lease_body["acquired_at"], label="Core v1 lease acquired_at"
        )
    except shared_score.LR8ScoreMapError as exc:
        raise CorpusCoreV1OutcomeSnapshotError(str(exc)) from exc
    if not lease_acquired_at <= attempt_started <= source_snapshot_time <= attempt_created:
        _fail("Core v1 read attempt durable chronology differs")
    expected_query_contract = core_query_contract(
        outcome_keys=retained_keys,
        query_job_id=query_job_id,
        source_snapshot_at=source_snapshot_at,
    )
    query_job_receipt = _normalized_query_job_receipt(
        source.get("query_job_receipt"),
        query_contract=expected_query_contract,
        not_before=attempt_created,
    )
    outcome_key_payload = _outcome_key_payload(retained_keys)
    catalog_identity_value = _identity(
        catalog_identity, label="Core v1 catalog identity"
    )
    attempt_table_receipts = _normalized_table_receipts(
        attempt.get("table_receipts_before_query")
    )
    disposition = source.get("query_job_disposition")
    if (
        source.get("schema_version") != PLAYER_SOURCE_SCHEMA
        or source.get("catalog_sha256") != retained_catalog["catalog_sha256"]
        or source.get("attempt") != attempt
        or source.get("attempt_identity") != attempt_identity
        or source.get("attempt_created_at") != attempt_created_text
        or source.get("later_source_freeze_identity") != expected_freeze_identity
        or source.get("later_source_freeze_sha256") != expected_freeze_sha256
        or source.get("outcome_key_count") != len(retained_keys)
        or source.get("outcome_keys_sha256")
        != canonical_sha256(outcome_key_payload)
        or source.get("query_contract") != expected_query_contract
        or source.get("query_contract_sha256")
        != canonical_sha256(expected_query_contract)
        or source.get("query_job_id") != query_job_id
        or source.get("query_job_receipt") != query_job_receipt
        or type(disposition) is not str
        or disposition not in {"created", "recovered"}
        or source.get("source_snapshot_at") != source_snapshot_at
        or source.get("table_receipts_before_query") != table_receipts_before
        or source.get("table_receipts_after_query") != table_receipts_after
        or table_receipts_before != table_receipts_after
        or _sha(
            source.get("table_receipt_set_sha256"),
            label="realized player source table receipt set SHA",
        ) != canonical_sha256(table_receipts_before)
        or source.get("historical_outcome_lease_before_query")
        != historical_lease_before
        or source.get("historical_outcome_lease_after_query")
        != historical_lease_after
        or historical_lease_before != historical_lease_after
        or _sha(
            source.get("historical_outcome_lease_sha256"),
            label="realized player source historical lease SHA",
        ) != canonical_sha256(historical_lease_before)
        or attempt.get("schema_version") != READ_ATTEMPT_SCHEMA
        or attempt.get("catalog_identity") != catalog_identity_value
        or attempt.get("catalog_sha256") != retained_catalog["catalog_sha256"]
        or attempt.get("later_source_freeze_identity")
        != expected_freeze_identity
        or attempt.get("later_source_freeze_sha256") != expected_freeze_sha256
        or attempt.get("outcome_key_count") != len(retained_keys)
        or attempt.get("outcome_keys") != outcome_key_payload
        or attempt.get("outcome_keys_sha256")
        != canonical_sha256(outcome_key_payload)
        or attempt.get("query_contract") != expected_query_contract
        or attempt.get("query_contract_sha256")
        != canonical_sha256(expected_query_contract)
        or attempt.get("table_receipts_before_query") != attempt_table_receipts
        or attempt_table_receipts != table_receipts_before
        or attempt.get("table_receipt_set_sha256")
        != canonical_sha256(attempt_table_receipts)
        or attempt_lease != historical_lease_before
        or attempt.get("uses_realized_outcomes_at_creation") is not False
        or attempt.get("attempt_precedes_query") is not True
        or any(attempt.get(field) is not False for field in (
            "historical_retry_licensed",
            "historical_retune_licensed",
            "graph_mutation_licensed",
            "production_change_licensed",
            "decision_authority",
        ))
        or source.get("row_fields") != list(_PLAYER_SOURCE_ROW_FIELDS)
        or source.get("row_count") != len(rows)
        or source.get("rows_sha256") != canonical_sha256(rows)
        or source.get("rows") != rows
        or source.get("one_exact_query") is not True
        or source.get("query_cache_used") is not False
        or source.get("table_metadata_stable_during_query") is not True
        or source.get("historical_outcome_lease_unchanged_during_query") is not True
        or source.get("full_field_standings_included") is not False
        or source.get("payout_ladder_included") is not False
        or source.get("production_change_licensed") is not False
        or source.get("decision_authority") is not False
    ):
        _fail("Core v1 realized player source law differs")
    return source, retained_identity, rows


def _normalize_snapshot_row(
    value: object, *, catalog_slates: Sequence[object], label: str,
) -> dict[str, object]:
    row = _mapping(value, label=label)
    _exact_keys(row, _SNAPSHOT_ROW_KEYS, label=label)
    source_ordinal = _exact_int(
        row.get("source_ordinal"), label=f"{label}.source_ordinal", minimum=0
    )
    if source_ordinal >= len(catalog_slates):
        _fail(f"{label} source ordinal is outside the catalog")
    catalog_slate = _mapping(
        catalog_slates[source_ordinal], label="snapshot catalog slate"
    )
    slate = _mapping(catalog_slate.get("slate"), label="snapshot slate key")
    score = _exact_int(
        row.get("realized_score_micro"), label=f"{label}.realized_score_micro"
    )
    if abs(score) > legacy_grading.MAX_ABS_PLAYER_SCORE_MICRO:
        _fail(f"{label} realized score exceeds exact nine-player sum bounds")
    result = {
        "source_ordinal": source_ordinal,
        "season": _exact_int(row.get("season"), label=f"{label}.season", minimum=2000),
        "week": _exact_int(row.get("week"), label=f"{label}.week", minimum=1),
        "slate_id": _string(row.get("slate_id"), label=f"{label}.slate_id"),
        "player_id": _string(row.get("player_id"), label=f"{label}.player_id"),
        "realized_score_micro": score,
    }
    if (
        result["season"] != slate.get("season")
        or result["week"] != slate.get("week")
        or result["slate_id"] != slate.get("slate_id")
    ):
        _fail(f"{label} slate identity differs from the catalog")
    return result


def _row_keys(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [{
        "source_ordinal": row["source_ordinal"],
        "season": row["season"],
        "week": row["week"],
        "slate_id": row["slate_id"],
        "player_id": row["player_id"],
    } for row in rows]


def _snapshot_rows_from_player_source(
    rows: Sequence[Mapping[str, object]], *, catalog: Mapping[str, object],
) -> list[dict[str, object]]:
    catalog_slates = _sequence(catalog.get("slates"), label="catalog slates")
    result = [
        _normalize_snapshot_row(
            {key: raw[key] for key in _SNAPSHOT_ROW_KEYS},
            catalog_slates=catalog_slates,
            label=f"outcome row[{ordinal}]",
        )
        for ordinal, raw in enumerate(rows)
    ]
    result.sort(key=lambda row: (row["source_ordinal"], row["player_id"]))
    return result


def build_core_outcome_snapshot(
    *,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    player_source: Mapping[str, object],
    player_source_identity: Mapping[str, object],
    outcome_keys: Sequence[CoreOutcomeKey],
) -> dict[str, object]:
    """Build one reusable exact-micro snapshot after the sole source read."""
    retained_catalog = _validated_catalog(catalog, identity=catalog_identity)
    _, retained_source_identity, source_rows = validate_core_player_source(
        player_source,
        identity=player_source_identity,
        catalog=retained_catalog,
        catalog_identity=catalog_identity,
        outcome_keys=outcome_keys,
    )
    normalized = _snapshot_rows_from_player_source(
        source_rows, catalog=retained_catalog
    )
    observed_keys = [
        (row["source_ordinal"], row["player_id"]) for row in normalized
    ]
    required = _required_player_ids(retained_catalog)
    required_keys = sorted(
        (source_ordinal, player_id)
        for source_ordinal, players in enumerate(required)
        for player_id in players
    )
    if observed_keys != required_keys or len(observed_keys) != len(set(observed_keys)):
        _fail("outcome rows do not exactly equal the Core v1 union player keys")
    row_keys = _row_keys(normalized)
    body: dict[str, object] = {
        "schema_version": OUTCOME_SNAPSHOT_SCHEMA,
        "catalog_sha256": retained_catalog["catalog_sha256"],
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "source_identity": retained_source_identity,
        "row_count": len(normalized),
        "row_keys_sha256": canonical_sha256(row_keys),
        "rows_sha256": canonical_sha256(normalized),
        "rows": normalized,
        "full_field_standings_included": False,
        "payout_ladder_included": False,
    }
    body["outcome_snapshot_sha256"] = canonical_sha256(body)
    retained, _ = _validate_snapshot_structure(
        body,
        catalog=retained_catalog,
        source_identity=retained_source_identity,
        expected_rows=normalized,
    )
    return retained


def _validate_snapshot_structure(
    value: object,
    *,
    catalog: Mapping[str, object],
    source_identity: Mapping[str, object],
    expected_rows: Sequence[Mapping[str, object]],
) -> tuple[dict[str, object], dict[tuple[int, str], int]]:
    snapshot = dict(_mapping(value, label="Core v1 outcome snapshot"))
    _exact_keys(snapshot, _SNAPSHOT_KEYS, label="Core v1 outcome snapshot")
    _self_hash(
        snapshot,
        field="outcome_snapshot_sha256",
        label="Core v1 outcome snapshot",
    )
    raw_rows = _sequence(snapshot.get("rows"), label="snapshot rows")
    catalog_slates = _sequence(catalog.get("slates"), label="catalog slates")
    rows = [
        _normalize_snapshot_row(
            raw, catalog_slates=catalog_slates, label=f"snapshot row[{ordinal}]"
        )
        for ordinal, raw in enumerate(raw_rows)
    ]
    expected_order = sorted(
        rows, key=lambda row: (row["source_ordinal"], row["player_id"])
    )
    observed_keys = [(row["source_ordinal"], row["player_id"]) for row in rows]
    required = _required_player_ids(catalog)
    required_keys = sorted(
        (source_ordinal, player_id)
        for source_ordinal, players in enumerate(required)
        for player_id in players
    )
    row_keys = _row_keys(rows)
    if (
        snapshot.get("schema_version") != OUTCOME_SNAPSHOT_SCHEMA
        or snapshot.get("catalog_sha256") != catalog["catalog_sha256"]
        or snapshot.get("score_unit") != "micro_dk"
        or snapshot.get("micro_dk_per_point") != MICRO_DK_PER_POINT
        or snapshot.get("source_identity") != source_identity
        or snapshot.get("row_count") != len(rows)
        or rows != expected_order
        or rows != list(expected_rows)
        or observed_keys != required_keys
        or len(observed_keys) != len(set(observed_keys))
        or snapshot.get("row_keys_sha256") != canonical_sha256(row_keys)
        or snapshot.get("rows_sha256") != canonical_sha256(rows)
        or snapshot.get("full_field_standings_included") is not False
        or snapshot.get("payout_ladder_included") is not False
    ):
        _fail("Core v1 outcome snapshot law differs")
    return snapshot, {
        key: row["realized_score_micro"]
        for key, row in zip(observed_keys, rows, strict=True)
    }


def validate_core_outcome_snapshot(
    value: object,
    *,
    identity: Mapping[str, object],
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    player_source: Mapping[str, object],
    player_source_identity: Mapping[str, object],
    outcome_keys: Sequence[CoreOutcomeKey],
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[tuple[int, str], int],
]:
    """Replay the persisted source and its derived score snapshot exactly."""
    retained_catalog = _validated_catalog(catalog, identity=catalog_identity)
    _, retained_source_identity, source_rows = validate_core_player_source(
        player_source,
        identity=player_source_identity,
        catalog=retained_catalog,
        catalog_identity=catalog_identity,
        outcome_keys=outcome_keys,
    )
    snapshot, score_map = _validate_snapshot_structure(
        value,
        catalog=retained_catalog,
        source_identity=retained_source_identity,
        expected_rows=_snapshot_rows_from_player_source(
            source_rows, catalog=retained_catalog
        ),
    )
    retained_snapshot_identity = _json_identity(
        snapshot, identity, label="Core v1 outcome snapshot identity"
    )
    return snapshot, retained_snapshot_identity, score_map


__all__ = [
    "CoreOutcomeKey",
    "CorpusCoreV1OutcomeSnapshotError",
    "OUTCOME_SNAPSHOT_SCHEMA",
    "PLAYER_SOURCE_SCHEMA",
    "READ_ATTEMPT_SCHEMA",
    "build_core_outcome_snapshot",
    "canonical_json_bytes",
    "canonical_sha256",
    "core_query_contract",
    "core_query_contract_sha256",
    "normalize_authoritative_query_rows",
    "project_core_outcome_keys",
    "registered_query_keys",
    "validate_core_outcome_snapshot",
    "validate_core_player_source",
]
