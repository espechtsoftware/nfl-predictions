"""Bounded supplier for the LR8 earlier-period player/DST score map.

The supplier is inert unless ``SupplierConfig.enabled`` is literal ``True``.
When enabled by a future transport, it validates the complete frozen LR8
training source, verifies the caller's live shared historical-outcome lease,
publishes a pre-query attempt create-once, executes one registered
authoritative query, and publishes one adapter-compatible score map
create-once.  All remote behavior is callback-owned; importing this module or
constructing a configuration performs no I/O.

The only scientific payload produced here is the exact player/DST map for the
35 frozen 2019/2021 slates.  It contains no roster totals, contest evidence,
later-period rows, or decision license.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_label_fit_adapter as adapter
from nfl_dfs.research import lr8_training_source as source


SUPPLIER_VERSION: Final = adapter.SCORE_SUPPLIER_VERSION
SOURCE_EXTRACT_VERSION: Final = adapter.SCORE_SOURCE_EXTRACT_VERSION
PROJECT: Final = "nfl-predictions-503414"
LOCATION: Final = "US"
BUCKET: Final = "nfl-predictions-503414-raw"
OUTPUT_NAMESPACE: Final = "research/lr8-authoritative-label-score-map"
SKILL_TABLE: Final = f"{PROJECT}.nfl_features.player_week_actuals"
DST_TABLE: Final = f"{PROJECT}.nfl_features.team_defense_week"
QUERY_ROW_FIELDS: Final = (
    "season",
    "week",
    "source_kind",
    "source_key",
    "realized_score",
)
EXTRACT_ROW_FIELDS: Final = adapter.SCORE_SOURCE_ROW_FIELDS

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_CODE_SHA: Final = re.compile(r"[0-9a-f]{40}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")
_RUN_ID: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,80}")
_JOB: Final = re.compile(r"[a-z0-9][a-z0-9-]{2,62}")
_IMAGE: Final = re.compile(r".+@sha256:[0-9a-f]{64}")
_MICRO_LIMIT: Final = ((1 << 63) - 1) // 9


class LR8ScoreMapError(RuntimeError):
    """The bounded LR8 score-map supplier failed closed."""


@dataclass(frozen=True, slots=True)
class SupplierConfig:
    """Exact runtime identity; default construction is deliberately inert."""

    run_id: str
    job: str
    code_sha: str
    image: str
    expected_source_manifest_sha256: str
    enabled: bool = False

    @property
    def output_root(self) -> str:
        return f"gs://{BUCKET}/{OUTPUT_NAMESPACE}/{self.run_id}"


@dataclass(frozen=True, slots=True)
class CatalogPlayer:
    season: int
    week: int
    player_id: str
    position: str
    source_kind: str
    source_key: str


@dataclass(frozen=True, slots=True)
class QueryParameter:
    name: str
    bq_type: str
    value: object
    array: bool = False


@dataclass(frozen=True, slots=True)
class QuerySpec:
    sql: str
    parameters: tuple[QueryParameter, ...]
    job_id: str
    location: str
    sql_sha256: str
    parameters_sha256: str
    catalog_keys_sha256: str


@dataclass(frozen=True, slots=True)
class QueryResult:
    rows: Sequence[Mapping[str, object]]
    job_receipt: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PublishedObject:
    """Create-once upload result plus the generation-reopened bytes."""

    receipt: Mapping[str, object]
    reopened_raw: bytes
    created_at: str
    created: bool


@dataclass(frozen=True, slots=True)
class ScoreMapSupply:
    attempt: Mapping[str, object]
    attempt_receipt: Mapping[str, object]
    source_extract: Mapping[str, object]
    source_extract_receipt: Mapping[str, object]
    score_map: Mapping[str, object]
    score_map_receipt: Mapping[str, object]


LeaseVerifier = Callable[[], Mapping[str, object]]
MetadataReader = Callable[[str], Mapping[str, object]]
QueryExecutor = Callable[[QuerySpec], QueryResult]
Publisher = Callable[[str, bytes], PublishedObject]
Clock = Callable[[], datetime]


def canonical_json(value: object) -> bytes:
    """Canonical create-once envelope, with one required terminal newline."""
    try:
        return adapter.canonical_json(value) + b"\n"
    except adapter.LR8LabelFitError as exc:
        raise LR8ScoreMapError(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(adapter.canonical_json(value)).hexdigest()


def authoritative_score_sql() -> str:
    """The only registered warehouse read used by this supplier."""
    sql = f"""WITH skill_scores AS (
  SELECT
    a.season,
    a.week,
    'skill' AS source_kind,
    CAST(a.gsis_id AS STRING) AS source_key,
    CAST(a.dk_points AS NUMERIC) AS realized_score
  FROM `{SKILL_TABLE}` FOR SYSTEM_TIME AS OF @source_snapshot_at AS a
  WHERE a.season IN UNNEST(@target_seasons)
    AND FORMAT('%d|%02d|%s', a.season, a.week, CAST(a.gsis_id AS STRING))
      IN UNNEST(@skill_keys)
), dst_scores AS (
  SELECT
    d.season,
    d.week,
    'dst' AS source_kind,
    UPPER(CAST(d.team AS STRING)) AS source_key,
    CAST(d.dst_dk_points AS NUMERIC) AS realized_score
  FROM `{DST_TABLE}` FOR SYSTEM_TIME AS OF @source_snapshot_at AS d
  WHERE d.season IN UNNEST(@target_seasons)
    AND FORMAT('%d|%02d|%s', d.season, d.week, UPPER(CAST(d.team AS STRING)))
      IN UNNEST(@dst_keys)
)
SELECT season, week, source_kind, source_key, realized_score
FROM skill_scores
UNION ALL
SELECT season, week, source_kind, source_key, realized_score
FROM dst_scores
ORDER BY season, week, source_kind, source_key"""
    compact = f" {sql.lower()} "
    forbidden = (
        " contest", " ownership", " payout", " standing", " winner",
        " insert ", " update ", " merge ", " delete ",
    )
    if any(token in compact for token in forbidden):
        raise AssertionError("LR8 authoritative score SQL exceeded its boundary")
    return sql


AUTHORITATIVE_SCORE_SQL: Final = authoritative_score_sql()
AUTHORITATIVE_SCORE_SQL_SHA256: Final = sha256(
    AUTHORITATIVE_SCORE_SQL.encode("utf-8")
).hexdigest()
if AUTHORITATIVE_SCORE_SQL_SHA256 != adapter.AUTHORITATIVE_SQL_SHA256:
    raise AssertionError("LR8 authoritative SQL differs from its registered hash")


def _strict_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise LR8ScoreMapError(f"{label} must be a canonical string")
    return value


def _strict_sha256(value: object, *, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise LR8ScoreMapError(f"{label} must be a lowercase SHA-256")
    return value


def _exact_int(
    value: object,
    *,
    label: str,
    minimum: int | None = 0,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise LR8ScoreMapError(f"{label} must be an exact integer")
    if minimum is not None and value < minimum:
        raise LR8ScoreMapError(f"{label} must be >= {minimum}")
    return value


def _utc(value: object, *, label: str) -> tuple[str, datetime]:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str) and value.strip() == value and value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise LR8ScoreMapError(f"{label} must be ISO-8601") from exc
    else:
        raise LR8ScoreMapError(f"{label} must be an aware UTC timestamp")
    if (
        parsed.tzinfo is None
        or parsed.utcoffset() is None
        or parsed.utcoffset().total_seconds() != 0
    ):
        raise LR8ScoreMapError(f"{label} must be an aware UTC timestamp")
    normalized = parsed.astimezone(timezone.utc)
    return normalized.isoformat(), normalized


def _now(clock: Clock, *, label: str) -> tuple[str, datetime]:
    value = clock()
    if not isinstance(value, datetime):
        raise LR8ScoreMapError(f"{label} clock returned the wrong type")
    return _utc(value, label=label)


def _content_receipt(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "sha256", "bytes",
    }:
        raise LR8ScoreMapError(f"{label} is not an exact content receipt")
    uri = value["uri"]
    generation = value["generation"]
    digest = value["sha256"]
    size = value["bytes"]
    if (
        not isinstance(uri, str)
        or not uri.startswith("gs://")
        or not uri.removeprefix("gs://").partition("/")[0]
        or not uri.removeprefix("gs://").partition("/")[2]
        or not isinstance(generation, str)
        or _GENERATION.fullmatch(generation) is None
        or not isinstance(digest, str)
        or _SHA256.fullmatch(digest) is None
        or isinstance(size, bool)
        or not isinstance(size, int)
        or size <= 0
    ):
        raise LR8ScoreMapError(f"{label} is not an exact content receipt")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": size,
    }


def _create_once_receipt(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "uri", "generation", "sha256", "bytes", "create_only",
    }:
        raise LR8ScoreMapError(f"{label} is not an exact create-once receipt")
    if not isinstance(value["create_only"], bool) or value["create_only"] is not True:
        raise LR8ScoreMapError(f"{label} is not create-once")
    content = _content_receipt(
        {key: value[key] for key in ("uri", "generation", "sha256", "bytes")},
        label=label,
    )
    return {**content, "create_only": True}


def _bound_content_receipt(
    value: object,
    payload: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    receipt = _content_receipt(value, label=label)
    raw = adapter.canonical_json(payload)
    identities = {
        (sha256(candidate).hexdigest(), len(candidate))
        for candidate in (raw, raw + b"\n")
    }
    if (receipt["sha256"], receipt["bytes"]) not in identities:
        raise LR8ScoreMapError(f"{label} does not bind the canonical bytes")
    return receipt


def _validate_config(config: SupplierConfig) -> SupplierConfig:
    if not isinstance(config, SupplierConfig):
        raise LR8ScoreMapError("supplier configuration differs")
    if _RUN_ID.fullmatch(config.run_id) is None:
        raise LR8ScoreMapError("supplier run id differs")
    if _JOB.fullmatch(config.job) is None:
        raise LR8ScoreMapError("supplier job differs")
    if _CODE_SHA.fullmatch(config.code_sha) is None:
        raise LR8ScoreMapError("supplier code SHA differs")
    if _IMAGE.fullmatch(config.image) is None:
        raise LR8ScoreMapError("supplier image differs")
    _strict_sha256(
        config.expected_source_manifest_sha256,
        label="expected training-source manifest hash",
    )
    return config


def _validate_training_source(
    value: Mapping[str, object],
    *,
    expected_manifest_sha256: str,
    receipt: Mapping[str, object],
) -> tuple[tuple[CatalogPlayer, ...], str, dict[str, object]]:
    if not isinstance(value, Mapping):
        raise LR8ScoreMapError("training source must be an object")
    expected = _strict_sha256(
        expected_manifest_sha256, label="training-source manifest hash"
    )
    frozen = dict(value)
    if frozen.get("manifest_sha256") != expected:
        raise LR8ScoreMapError("training-source manifest hash differs")
    body = {key: item for key, item in frozen.items() if key != "manifest_sha256"}
    if canonical_sha256(body) != expected:
        raise LR8ScoreMapError("training-source manifest bytes differ")
    source_receipt = _bound_content_receipt(
        receipt, frozen, label="training-source object receipt"
    )
    try:
        # The adapter owns the exact source-lattice validator.  Its returned
        # candidate surface is intentionally discarded here.
        adapter.frozen_fit_candidates(
            frozen,
            expected_manifest_sha256=expected,
            training_source_receipt=source_receipt,
        )
    except adapter.LR8LabelFitError as exc:
        raise LR8ScoreMapError(str(exc)) from exc

    raw_slates = frozen.get("slates")
    if not isinstance(raw_slates, list) or len(raw_slates) != source.EXPECTED_SLATES:
        raise LR8ScoreMapError("training-source slate lattice differs")
    players: list[CatalogPlayer] = []
    universe: list[dict[str, object]] = []
    for raw_slate, expected_key in zip(
        raw_slates, source.EXPECTED_SLATE_KEYS, strict=True
    ):
        if not isinstance(raw_slate, Mapping):
            raise LR8ScoreMapError("training-source slate differs")
        season, week = expected_key
        if raw_slate.get("season") != season or raw_slate.get("week") != week:
            raise LR8ScoreMapError("training-source slate order differs")
        catalog = raw_slate.get("catalog")
        if not isinstance(catalog, list):
            raise LR8ScoreMapError("training-source catalog differs")
        for raw_player in catalog:
            if not isinstance(raw_player, Mapping):
                raise LR8ScoreMapError("training-source catalog row differs")
            player_id = _strict_string(raw_player.get("id"), label="player id")
            position = _strict_string(
                raw_player.get("pos"), label="player position"
            ).upper()
            team = _strict_string(raw_player.get("team"), label="player team")
            source_kind = "dst" if position == "DST" else "skill"
            source_key = team.upper() if source_kind == "dst" else player_id
            players.append(CatalogPlayer(
                season=season,
                week=week,
                player_id=player_id,
                position=position,
                source_kind=source_kind,
                source_key=source_key,
            ))
            universe.append({
                "season": season,
                "week": week,
                "player_id": player_id,
                "position": position,
            })
    keys = [
        (row.season, row.week, row.source_kind, row.source_key) for row in players
    ]
    if len(set(keys)) != len(keys):
        raise LR8ScoreMapError("training-source authoritative keys repeat")
    if {(row.season, row.week) for row in players} != set(source.EXPECTED_SLATE_KEYS):
        raise LR8ScoreMapError("training-source catalog misses a required slate")
    return tuple(players), canonical_sha256(universe), source_receipt


def _parameter_payload(values: Sequence[QueryParameter]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for item in values:
        if not isinstance(item.array, bool):
            raise LR8ScoreMapError("query parameter array marker differs")
        rows.append({
            "name": _strict_string(item.name, label="query parameter name"),
            "type": _strict_string(item.bq_type, label="query parameter type"),
            "array": item.array,
            "value": item.value,
        })
    if len({row["name"] for row in rows}) != len(rows):
        raise LR8ScoreMapError("query parameter names repeat")
    canonical_json(rows)
    return rows


def _catalog_key_payload(
    values: Sequence[CatalogPlayer],
) -> list[dict[str, object]]:
    return [{
        "season": row.season,
        "week": row.week,
        "source_kind": row.source_kind,
        "source_key": row.source_key,
        "player_id": row.player_id,
        "position": row.position,
    } for row in values]


def build_query_spec(
    *,
    config: SupplierConfig,
    catalog: Sequence[CatalogPlayer],
    source_snapshot_at: str,
) -> QuerySpec:
    """Bind the one query to the exact frozen catalog source keys."""
    config = _validate_config(config)
    snapshot_text, _ = _utc(source_snapshot_at, label="source snapshot")
    players = tuple(catalog)
    skill_keys = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in players if row.source_kind == "skill"
    )
    dst_keys = sorted(
        f"{row.season}|{row.week:02d}|{row.source_key}"
        for row in players if row.source_kind == "dst"
    )
    if (
        not skill_keys
        or not dst_keys
        or len(skill_keys) + len(dst_keys) != len(players)
    ):
        raise LR8ScoreMapError("authoritative catalog key partition differs")
    if len(set(skill_keys)) != len(skill_keys) or len(set(dst_keys)) != len(dst_keys):
        raise LR8ScoreMapError("authoritative query keys repeat")
    parameters = (
        QueryParameter("source_snapshot_at", "TIMESTAMP", snapshot_text),
        QueryParameter(
            "target_seasons", "INT64", list(source.TARGET_SEASONS), array=True
        ),
        QueryParameter("skill_keys", "STRING", skill_keys, array=True),
        QueryParameter("dst_keys", "STRING", dst_keys, array=True),
    )
    payload = _parameter_payload(parameters)
    catalog_keys = _catalog_key_payload(players)
    job_id = (
        f"lr8_label_score_map_{config.run_id.replace('-', '_')[:48]}_"
        f"{config.expected_source_manifest_sha256[:12]}"
    )
    return QuerySpec(
        sql=AUTHORITATIVE_SCORE_SQL,
        parameters=parameters,
        job_id=job_id,
        location=LOCATION,
        sql_sha256=AUTHORITATIVE_SCORE_SQL_SHA256,
        parameters_sha256=sha256(canonical_json(payload)).hexdigest(),
        catalog_keys_sha256=canonical_sha256(catalog_keys),
    )


def _validate_lease(
    value: object,
    *,
    config: SupplierConfig,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {"body", "object_receipt"}:
        raise LR8ScoreMapError("historical-outcome lease binding differs")
    body = value["body"]
    if not isinstance(body, Mapping) or set(body) != {
        "version", "run_id", "job", "code_sha", "image", "acquired_at",
    }:
        raise LR8ScoreMapError("historical-outcome lease body differs")
    normalized_body = dict(body)
    if (
        normalized_body["version"] != adapter.HISTORICAL_OUTCOME_LEASE_VERSION
        or normalized_body["run_id"] != config.run_id
        or normalized_body["job"] != config.job
        or normalized_body["code_sha"] != config.code_sha
        or normalized_body["image"] != config.image
    ):
        raise LR8ScoreMapError("historical-outcome lease identity differs")
    acquired_at, _ = _utc(
        normalized_body["acquired_at"], label="lease acquired_at"
    )
    normalized_body["acquired_at"] = acquired_at
    receipt = _create_once_receipt(
        value["object_receipt"], label="historical-outcome lease receipt"
    )
    if receipt["uri"] != adapter.HISTORICAL_OUTCOME_LEASE_URI:
        raise LR8ScoreMapError("historical-outcome lease URI differs")
    raw = canonical_json(normalized_body)
    if receipt["sha256"] != sha256(raw).hexdigest() or receipt["bytes"] != len(raw):
        raise LR8ScoreMapError("historical-outcome lease receipt differs")
    return {"body": normalized_body, "object_receipt": receipt}


def _publish_exact(
    publisher: Publisher,
    *,
    uri: str,
    payload: Mapping[str, object],
    earliest: datetime,
    label: str,
) -> tuple[dict[str, object], datetime]:
    raw = canonical_json(payload)
    published = publisher(uri, raw)
    if not isinstance(published, PublishedObject) or published.created is not True:
        raise LR8ScoreMapError(f"{label} was not created exactly once")
    receipt = _create_once_receipt(published.receipt, label=f"{label} receipt")
    created_text, created_at = _utc(
        published.created_at, label=f"{label} creation"
    )
    if (
        receipt["uri"] != uri
        or receipt["sha256"] != sha256(raw).hexdigest()
        or receipt["bytes"] != len(raw)
        or not isinstance(published.reopened_raw, bytes)
        or published.reopened_raw != raw
        or created_at < earliest
        or created_text != published.created_at
    ):
        raise LR8ScoreMapError(f"{label} create-once reopen differs")
    return receipt, created_at


def _table_receipt(value: object, *, table: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "table_id", "etag", "modified", "num_rows", "schema_sha256",
    }:
        raise LR8ScoreMapError("authoritative table metadata fields differ")
    if value["table_id"] != table:
        raise LR8ScoreMapError("authoritative table identity differs")
    _strict_string(value["etag"], label="authoritative table etag")
    modified, _ = _utc(value["modified"], label="authoritative table modified")
    rows = _exact_int(value["num_rows"], label="authoritative table rows")
    schema_digest = _strict_sha256(
        value["schema_sha256"], label="authoritative table schema hash"
    )
    return {
        "table_id": table,
        "etag": value["etag"],
        "modified": modified,
        "num_rows": rows,
        "schema_sha256": schema_digest,
    }


def _job_receipt(
    value: object,
    *,
    spec: QuerySpec,
    not_before: datetime,
) -> tuple[dict[str, object], datetime]:
    fields = {
        "job_id", "location", "sql_sha256", "parameters_sha256",
        "created", "started", "ended", "total_bytes_processed",
        "cache_hit", "error_result",
    }
    if not isinstance(value, Mapping) or set(value) != fields:
        raise LR8ScoreMapError("authoritative query job receipt fields differ")
    if (
        value["job_id"] != spec.job_id
        or value["location"] != spec.location
        or value["sql_sha256"] != spec.sql_sha256
        or value["parameters_sha256"] != spec.parameters_sha256
        or value["error_result"] is not None
    ):
        raise LR8ScoreMapError("authoritative query job identity differs")
    created_text, created = _utc(value["created"], label="query created")
    started_text, started = _utc(value["started"], label="query started")
    ended_text, ended = _utc(value["ended"], label="query ended")
    if not not_before <= created <= started <= ended:
        raise LR8ScoreMapError("authoritative query chronology differs")
    total_bytes = _exact_int(
        value["total_bytes_processed"], label="query bytes processed"
    )
    if not isinstance(value["cache_hit"], bool):
        raise LR8ScoreMapError("query cache marker must be literal bool")
    return ({
        "job_id": spec.job_id,
        "location": spec.location,
        "sql_sha256": spec.sql_sha256,
        "parameters_sha256": spec.parameters_sha256,
        "created": created_text,
        "started": started_text,
        "ended": ended_text,
        "total_bytes_processed": total_bytes,
        "cache_hit": value["cache_hit"],
        "error_result": None,
    }, ended)


def _micro_score(value: object) -> int:
    if isinstance(value, bool) or isinstance(value, float) or value is None:
        raise LR8ScoreMapError("authoritative score must be exact decimal data")
    if isinstance(value, Decimal):
        number = value
    elif isinstance(value, int):
        number = Decimal(value)
    elif isinstance(value, str) and value and value.strip() == value:
        try:
            number = Decimal(value)
        except InvalidOperation as exc:
            raise LR8ScoreMapError("authoritative score is not decimal") from exc
    else:
        raise LR8ScoreMapError("authoritative score must be exact decimal data")
    if not number.is_finite():
        raise LR8ScoreMapError("authoritative score is non-finite")
    micro = number * Decimal(1_000_000)
    if micro != micro.to_integral_value():
        raise LR8ScoreMapError("authoritative score is not exact micro-DK")
    result = int(micro)
    if abs(result) > _MICRO_LIMIT:
        raise LR8ScoreMapError("authoritative score exceeds roster-sum range")
    return result


def _score_rows(
    values: object,
    *,
    catalog: Sequence[CatalogPlayer],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise LR8ScoreMapError("authoritative query rows must be a sequence")
    expected = {
        (row.season, row.week, row.source_kind, row.source_key): row
        for row in catalog
    }
    observed: dict[tuple[int, int, str, str], int] = {}
    extract_rows: list[dict[str, object]] = []
    for raw in values:
        if not isinstance(raw, Mapping) or set(raw) != set(QUERY_ROW_FIELDS):
            raise LR8ScoreMapError("authoritative query row fields differ")
        season = _exact_int(raw["season"], label="query season")
        week = _exact_int(raw["week"], label="query week", minimum=1)
        if (season, week) not in source.EXPECTED_SLATE_KEYS:
            raise LR8ScoreMapError("authoritative query contains a non-2019/2021 slate")
        kind = _strict_string(raw["source_kind"], label="query source kind")
        key_value = _strict_string(raw["source_key"], label="query source key")
        key = (season, week, kind, key_value)
        if key in observed:
            raise LR8ScoreMapError("authoritative query repeats a source key")
        if key not in expected:
            raise LR8ScoreMapError("authoritative query contains an extra source key")
        score = _micro_score(raw["realized_score"])
        observed[key] = score
        extract_rows.append({
            "season": season,
            "week": week,
            "source_kind": kind,
            "source_key": key_value,
            "realized_score_micro": score,
        })
    observed_order = [
        (row["season"], row["week"], row["source_kind"], row["source_key"])
        for row in extract_rows
    ]
    if observed_order != sorted(expected):
        if set(observed) != set(expected):
            missing = len(set(expected) - set(observed))
            extra = len(set(observed) - set(expected))
            raise LR8ScoreMapError(
                f"authoritative query coverage differs: missing={missing} extra={extra}"
            )
        raise LR8ScoreMapError("authoritative query rows are not canonically ordered")
    score_rows = []
    for player in sorted(
        catalog, key=lambda row: (row.season, row.week, row.player_id)
    ):
        realized = observed[
            (player.season, player.week, player.source_kind, player.source_key)
        ]
        score_rows.append({
            "season": player.season,
            "week": player.week,
            "player_id": player.player_id,
            "position": player.position,
            "realized_score_micro": realized,
            "actual_source": (
                adapter.DST_ACTUAL_SOURCE
                if player.position == "DST"
                else adapter.SKILL_ACTUAL_SOURCE
            ),
        })
    return extract_rows, score_rows


def supply_authoritative_score_map(
    *,
    config: SupplierConfig,
    training_source_freeze: Mapping[str, object],
    training_source_receipt: Mapping[str, object],
    verify_lease: LeaseVerifier,
    read_table_metadata: MetadataReader,
    execute_query: QueryExecutor,
    publish: Publisher,
    clock: Clock = lambda: datetime.now(timezone.utc),
) -> ScoreMapSupply:
    """Supply exactly one adapter-compatible 2019/2021 score map.

    The explicit enable gate is evaluated before configuration parsing, source
    validation, clocks, or any callback invocation.
    """
    if (
        not isinstance(config, SupplierConfig)
        or not isinstance(config.enabled, bool)
        or config.enabled is not True
    ):
        raise LR8ScoreMapError("LR8 authoritative score-map supplier is default-off")
    config = _validate_config(config)
    catalog, catalog_universe_sha256, source_receipt = _validate_training_source(
        training_source_freeze,
        expected_manifest_sha256=config.expected_source_manifest_sha256,
        receipt=training_source_receipt,
    )
    attempt_uri = f"{config.output_root}/label-read-attempt.json"
    extract_uri = f"{config.output_root}/authoritative-score-source.json"
    score_map_uri = f"{config.output_root}/authoritative-score-map.json"
    if len({
        adapter.HISTORICAL_OUTCOME_LEASE_URI,
        source_receipt["uri"],
        attempt_uri,
        extract_uri,
        score_map_uri,
    }) != 5:
        raise LR8ScoreMapError("supplier object URIs alias before outcome access")
    lease_before = _validate_lease(verify_lease(), config=config)
    started_text, started_at = _now(clock, label="label-read attempt start")
    _, lease_acquired = _utc(
        lease_before["body"]["acquired_at"], label="lease acquired_at"
    )
    if started_at < lease_acquired:
        raise LR8ScoreMapError("label-read attempt predates its outcome lease")

    query_identity = adapter.authoritative_query_identity()
    attempt = {
        "schema": adapter.LABEL_READ_ATTEMPT_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "supplier_boundary": adapter.SCORE_SUPPLIER_BOUNDARY,
        "stage": "before-authoritative-score-query",
        "training_source_manifest_sha256": config.expected_source_manifest_sha256,
        "training_source_object": source_receipt,
        "target_seasons": list(source.TARGET_SEASONS),
        "slate_keys": [list(key) for key in source.EXPECTED_SLATE_KEYS],
        "query_identity": query_identity,
        "query_sha256": adapter.AUTHORITATIVE_QUERY_SHA256,
        "historical_outcome_lease": lease_before,
        "started_at": started_text,
        "uses_realized_outcomes_at_creation": False,
        "retry_licensed": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "later_period_inputs_used": False,
        "production_inputs_used": False,
    }
    attempt_receipt, attempt_created = _publish_exact(
        publish,
        uri=attempt_uri,
        payload=attempt,
        earliest=started_at,
        label="label-read attempt",
    )

    snapshot_text, snapshot_at = _now(clock, label="source snapshot")
    if snapshot_at < attempt_created:
        raise LR8ScoreMapError("source snapshot predates the create-once attempt")
    query_spec = build_query_spec(
        config=config, catalog=catalog, source_snapshot_at=snapshot_text
    )
    tables_before = [
        _table_receipt(read_table_metadata(table), table=table)
        for table in (SKILL_TABLE, DST_TABLE)
    ]
    for table in tables_before:
        _, modified = _utc(table["modified"], label="table modified")
        if modified > snapshot_at:
            raise LR8ScoreMapError("authoritative table changed after source snapshot")
    queried = execute_query(query_spec)
    if not isinstance(queried, QueryResult):
        raise LR8ScoreMapError("authoritative query executor returned the wrong type")
    job_receipt, query_ended = _job_receipt(
        queried.job_receipt, spec=query_spec, not_before=snapshot_at
    )
    extract_rows, score_rows = _score_rows(queried.rows, catalog=catalog)
    tables_after = [
        _table_receipt(read_table_metadata(table), table=table)
        for table in (SKILL_TABLE, DST_TABLE)
    ]
    if tables_after != tables_before:
        raise LR8ScoreMapError("authoritative table metadata changed during query")
    lease_after = _validate_lease(verify_lease(), config=config)
    if canonical_json(lease_after) != canonical_json(lease_before):
        raise LR8ScoreMapError("historical-outcome lease changed during query")

    source_extract = {
        "schema": SOURCE_EXTRACT_VERSION,
        "supplier_version": SUPPLIER_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "supplier_boundary": adapter.SCORE_SUPPLIER_BOUNDARY,
        "training_source_manifest_sha256": config.expected_source_manifest_sha256,
        "training_source_object": source_receipt,
        "target_seasons": list(source.TARGET_SEASONS),
        "slate_keys": [list(key) for key in source.EXPECTED_SLATE_KEYS],
        "catalog_universe_sha256": catalog_universe_sha256,
        "catalog_keys": _catalog_key_payload(catalog),
        "catalog_keys_sha256": query_spec.catalog_keys_sha256,
        "query_identity": query_identity,
        "query_sha256": adapter.AUTHORITATIVE_QUERY_SHA256,
        "sql_sha256": query_spec.sql_sha256,
        "parameters": _parameter_payload(query_spec.parameters),
        "parameters_sha256": query_spec.parameters_sha256,
        "source_snapshot_at": snapshot_text,
        "job_receipt": job_receipt,
        "table_receipts": tables_before,
        "table_metadata_stable_during_query": True,
        "historical_outcome_lease_unchanged_during_query": True,
        "label_read_attempt": attempt,
        "label_read_attempt_receipt": attempt_receipt,
        "row_fields": list(EXTRACT_ROW_FIELDS),
        "rows": extract_rows,
        "rows_sha256": canonical_sha256(extract_rows),
        "query_completed_at": query_ended.isoformat(),
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "later_period_inputs_used": False,
        "production_inputs_used": False,
    }
    extract_receipt, extract_created = _publish_exact(
        publish,
        uri=extract_uri,
        payload=source_extract,
        earliest=query_ended,
        label="authoritative score source",
    )
    score_source_receipt = {
        key: extract_receipt[key]
        for key in ("uri", "generation", "sha256", "bytes")
    }

    score_map = {
        "schema": adapter.SCORE_MAP_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "supplier_boundary": adapter.SCORE_SUPPLIER_BOUNDARY,
        "training_source_manifest_sha256": config.expected_source_manifest_sha256,
        "training_source_object": source_receipt,
        "target_seasons": list(source.TARGET_SEASONS),
        "slate_keys": [list(key) for key in source.EXPECTED_SLATE_KEYS],
        "row_fields": list(adapter.SCORE_ROW_FIELDS),
        "score_unit": adapter.SCORE_UNIT,
        "catalog_universe_sha256": catalog_universe_sha256,
        "authoritative_source_id": adapter.AUTHORITATIVE_SOURCE_ID,
        "query_identity": query_identity,
        "query_sha256": adapter.AUTHORITATIVE_QUERY_SHA256,
        "score_source_receipts": [score_source_receipt],
        "score_source_extract": source_extract,
        "score_source_extract_receipt": extract_receipt,
        "label_read_attempt": attempt,
        "label_read_attempt_receipt": attempt_receipt,
        "rows": score_rows,
        "score_rows_sha256": adapter.canonical_sha256(score_rows),
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "later_period_inputs_used": False,
        "production_inputs_used": False,
    }
    score_map_receipt, _ = _publish_exact(
        publish,
        uri=score_map_uri,
        payload=score_map,
        earliest=extract_created,
        label="authoritative score map",
    )
    if len({
        adapter.HISTORICAL_OUTCOME_LEASE_URI,
        source_receipt["uri"],
        attempt_receipt["uri"],
        extract_receipt["uri"],
        score_map_receipt["uri"],
    }) != 5:
        raise LR8ScoreMapError("supplier object URIs alias")
    return ScoreMapSupply(
        attempt=attempt,
        attempt_receipt=attempt_receipt,
        source_extract=source_extract,
        source_extract_receipt=extract_receipt,
        score_map=score_map,
        score_map_receipt=score_map_receipt,
    )
