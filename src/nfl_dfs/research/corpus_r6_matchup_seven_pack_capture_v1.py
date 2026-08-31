"""Guarded global capture for the frozen R6 matchup seven-pack.

This module closes the missing input boundary between the historical raw
sources and ``corpus_r6_matchup_source_v2``.  It owns exactly five fixed
warehouse extracts and two projections that can be derived only from
generation-pinned artifact manifests.  Every output is canonical JSON,
create-once, generation-exact reopened, retrospective-only, and outcome
blind.  The seven row objects and seven provenance objects are written before
the source-v2 upstream release; that terminal release is always the final
write.

Cloud and warehouse clients are injected.  There is no listing, overwrite,
delete, synthetic-data fallback, scorer, graph client, deployment, IAM, or
policy mutation in this module.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


WAREHOUSE_QUERY_SPEC_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-warehouse-query-spec/v1"
)
WAREHOUSE_QUERY_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-warehouse-query-receipt/v1"
)
ARTIFACT_ROW_SHARD_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-artifact-row-shard/v1"
)
ARTIFACT_PACK_MANIFEST_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-artifact-pack-manifest/v1"
)
ARTIFACT_PROJECTION_MANIFEST_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-artifact-projection-manifest/v1"
)
IMPLEMENTATION_AUTHORITY_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-implementation-authority/v1"
)
PUBLICATION_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-publication-receipt/v1"
)
REOPEN_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-seven-pack-reopen-receipt/v1"
)

PRODUCTION_PROJECT: Final = "nfl-predictions-503414"
WAREHOUSE_DATASET: Final = "nfl_raw"
WAREHOUSE_LOCATION: Final = "US"
OUTPUT_BUCKET: Final = "nfl-predictions-503414-corpus-source"
OUTPUT_NAMESPACE: Final = "research/corpus-r6-matchup-seven-pack-captures-v1"
RELEASE_FILENAME: Final = "upstream-release.json"
CORE_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_matchup_seven_pack_capture_v1.py"
)
OPERATOR_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_matchup_seven_pack_capture_operator_v1.py"
)
CLI_MODULE_PATH: Final = "scripts/run_corpus_r6_matchup_seven_pack_capture_v1.py"
SOURCE_CONTRACT_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_matchup_source_v2.py"
)
PLAYER_CATALOG_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_player_catalog_v1.py"
)
NORMALIZED_SNAPSHOT_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_paid_source_normalized_snapshot_v1.py"
)
CAPTURE_PLAN_BRIDGE_MODULE_PATH: Final = (
    "src/nfl_dfs/research/"
    "corpus_r6_matchup_capture_plan_from_seven_pack_v1.py"
)
IMPLEMENTATION_PATHS: Final = (
    CORE_MODULE_PATH,
    OPERATOR_MODULE_PATH,
    CLI_MODULE_PATH,
    NORMALIZED_SNAPSHOT_MODULE_PATH,
    CAPTURE_PLAN_BRIDGE_MODULE_PATH,
    SOURCE_CONTRACT_MODULE_PATH,
    PLAYER_CATALOG_MODULE_PATH,
)

WAREHOUSE_PACK_IDS: Final = source.PACK_IDS[:5]
ARTIFACT_PACK_IDS: Final = source.PACK_IDS[5:]
WAREHOUSE_QUERY_COUNT: Final = 5
OUTPUT_OBJECT_COUNT: Final = 15
MAX_QUERY_RESULT_RECORDS: Final = 2_000_000
MAX_ARTIFACT_SHARDS_PER_PACK: Final = 512
MAX_SOURCE_MANIFESTS_PER_PACK: Final = 512
MAX_SOURCE_ARTIFACTS_PER_PACK: Final = 2_048
MAX_EXACT_READS: Final = 12_000
MAX_EXACT_READ_BYTES: Final = 32 * 1024 * 1024 * 1024
MAX_EXACT_OBJECT_BYTES: Final = 512 * 1024 * 1024
MAX_QUERY_BYTES_BILLED: Final = 5 * 1024 * 1024 * 1024
EVIDENCE_CLASS: Final = source.EVIDENCE_CLASS
OBSERVED_AT_BASIS: Final = source.OBSERVED_AT_BASIS
MISSING_ID_RETENTION_RULE: Final = (
    "exclude-from-positive-rows-and-account-by-canonical-row-hash-never-zero"
)

_RUN_ID = re.compile(r"^[a-z0-9][a-z0-9-]{7,63}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_TIMESTAMP = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnceOrExactPrior = Callable[[str, bytes], Mapping[str, object]]
QueryWarehouse = Callable[[Mapping[str, object]], Mapping[str, object]]


class CorpusR6MatchupSevenPackCaptureV1Error(RuntimeError):
    """The seven-pack capture could not be proven exactly."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupSevenPackCaptureV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} fields differ")


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _run_id(value: object) -> str:
    if type(value) is not str or _RUN_ID.fullmatch(value) is None:
        _fail("run ID must be a canonical 8-64 character lowercase identifier")
    return value


def _timestamp(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _TIMESTAMP.fullmatch(text) is None:
        _fail(f"{label} must be canonical UTC seconds")
    try:
        datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(
            f"{label} is not a valid timestamp"
        ) from exc
    return text


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _validate_policy(value: Mapping[str, object], *, label: str) -> None:
    if value.get("outcome_columns_read") != []:
        _fail(f"{label}.outcome_columns_read must be empty")
    if value.get("uses_realized_outcomes") is not False:
        _fail(f"{label}.uses_realized_outcomes must be false")
    differing = [
        field for field in source.FALSE_AUTHORITY_FIELDS
        if value.get(field) is not False
    ]
    if differing:
        _fail(f"{label} carries non-false authorities {differing}")


def _with_hash(body: Mapping[str, object], *, field_name: str) -> dict[str, object]:
    if field_name in body:
        _fail(f"{field_name} must not be supplied before hashing")
    result = dict(body)
    result[field_name] = source.canonical_sha256(result)
    return result


def _validate_hash(
    value: Mapping[str, object], *, field_name: str, label: str,
) -> str:
    retained = _digest(value.get(field_name), label=f"{label}.{field_name}")
    body = dict(value)
    del body[field_name]
    if source.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _canonical_object(raw: object, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty bytes")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(
            f"{label} is not canonical JSON"
        ) from exc
    item = _mapping(value, label=label)
    if source.canonical_json_bytes(item) != raw:
        _fail(f"{label} bytes differ from canonical JSON")
    return item


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return source.normalize_object_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(str(exc)) from exc


def _code_identity(value: object, *, label: str) -> dict[str, str]:
    try:
        return source.normalize_code_identity_v2(value, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(str(exc)) from exc


def _bind_bytes(
    identity_value: object, raw: bytes, *, label: str,
) -> dict[str, object]:
    identity = _identity(identity_value, label=f"{label} identity")
    if (
        len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} differs from its exact identity")
    return identity


def _sorted_identities(
    values: object, *, label: str, minimum: int, maximum: int,
) -> list[dict[str, object]]:
    raw = _sequence(values, label=label)
    if not minimum <= len(raw) <= maximum:
        _fail(f"{label} count differs")
    normalized = [
        _identity(value, label=f"{label}[{ordinal}]")
        for ordinal, value in enumerate(raw)
    ]
    uris = [str(value["uri"]) for value in normalized]
    if uris != sorted(uris) or len(uris) != len(set(uris)):
        _fail(f"{label} must be unique and URI-sorted")
    return normalized


@dataclass
class BoundedExactReaderV1:
    """Charge every generation-pinned payload before invoking its reader."""

    read_exact: ReadExact
    max_operations: int = MAX_EXACT_READS
    max_bytes: int = MAX_EXACT_READ_BYTES
    max_object_bytes: int = MAX_EXACT_OBJECT_BYTES
    operations: int = 0
    bytes_reserved: int = 0
    charges: list[dict[str, object]] = field(default_factory=list)

    def read(self, identity_value: Mapping[str, object], *, label: str) -> bytes:
        identity = _identity(identity_value, label=f"{label} identity")
        byte_count = int(identity["bytes"])
        next_operations = self.operations + 1
        next_bytes = self.bytes_reserved + byte_count
        if (
            byte_count > self.max_object_bytes
            or next_operations > self.max_operations
            or next_bytes > self.max_bytes
        ):
            _fail("generation-pinned exact-read budget exhausted")
        self.operations = next_operations
        self.bytes_reserved = next_bytes
        charge = {
            "ordinal": self.operations - 1,
            "uri": identity["uri"],
            "generation": identity["generation"],
            "bytes": byte_count,
            "charged_before_read": True,
        }
        charge["charge_sha256"] = source.canonical_sha256(charge)
        self.charges.append(charge)
        try:
            raw = self.read_exact(identity)
        except Exception as exc:
            raise CorpusR6MatchupSevenPackCaptureV1Error(
                f"{label} generation-exact read failed"
            ) from exc
        if type(raw) is not bytes:
            _fail(f"{label} reader did not return bytes")
        _bind_bytes(identity, raw, label=label)
        return raw

    def receipt(self) -> dict[str, object]:
        body = {
            "max_operations": self.max_operations,
            "max_bytes": self.max_bytes,
            "max_object_bytes": self.max_object_bytes,
            "operations": self.operations,
            "bytes_reserved": self.bytes_reserved,
            "charges": [dict(value) for value in self.charges],
            "charges_sha256": source.canonical_sha256(self.charges),
            "all_reads_generation_pinned": True,
            "all_reads_charged_before_access": True,
        }
        return _with_hash(body, field_name="read_budget_sha256")


def output_namespace_for_run_v1(run_id: object) -> str:
    normalized = _run_id(run_id)
    return f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/{normalized}/"


def output_uri_inventory_v1(run_id: object) -> tuple[str, ...]:
    prefix = output_namespace_for_run_v1(run_id)
    uris = [
        f"{prefix}packs/{pack_id}/rows.json"
        for pack_id in source.PACK_IDS
    ]
    uris.extend(
        f"{prefix}packs/{pack_id}/"
        + (
            "warehouse-query-receipt.json"
            if pack_id in WAREHOUSE_PACK_IDS
            else "artifact-projection-manifest.json"
        )
        for pack_id in source.PACK_IDS
    )
    uris.append(f"{prefix}{RELEASE_FILENAME}")
    if len(uris) != OUTPUT_OBJECT_COUNT or len(uris) != len(set(uris)):
        _fail("seven-pack output URI inventory differs")
    return tuple(sorted(uris))


def _metadata_sql(relations: Sequence[str]) -> str:
    quoted = ",".join(f"'{value}'" for value in relations)
    return f"""
SELECT
  'relation-metadata' AS record_kind,
  table_id AS slice_kind,
  TO_JSON_STRING(STRUCT(
    '{PRODUCTION_PROJECT}' AS project_id,
    '{WAREHOUSE_DATASET}' AS dataset_id,
    table_id AS relation_id,
    row_count AS row_count,
    size_bytes AS size_bytes,
    FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ',
      TIMESTAMP_MILLIS(last_modified_time), 'UTC') AS modified_time_utc,
    ARRAY(
      SELECT AS STRUCT
        column_name AS name,
        data_type AS data_type,
        is_nullable AS is_nullable,
        ordinal_position AS ordinal_position
      FROM `{PRODUCTION_PROJECT}.{WAREHOUSE_DATASET}.INFORMATION_SCHEMA.COLUMNS`
      WHERE table_name = frozen_tables.table_id
      ORDER BY ordinal_position
    ) AS columns
  )) AS row_json
FROM `{PRODUCTION_PROJECT}.{WAREHOUSE_DATASET}.__TABLES__` AS frozen_tables
WHERE frozen_tables.table_id IN ({quoted})
""".strip()


_SCHEDULE_ROWS_SQL: Final = f"""
SELECT
  'row' AS record_kind,
  'schedule-games' AS slice_kind,
  TO_JSON_STRING(STRUCT(
    away_team, game_id, game_type,
    FORMAT_DATE('%Y-%m-%d', DATE(gameday)) AS gameday,
    CAST(gametime AS STRING) AS gametime,
    home_team,
    FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ',
      TIMESTAMP(DATETIME(DATE(gameday), SAFE.PARSE_TIME('%H:%M',
        CAST(gametime AS STRING))), 'America/New_York'), 'UTC')
      AS kickoff_time_utc,
    CAST(season AS INT64) AS season,
    CAST(week AS INT64) AS week
  )) AS row_json
FROM `{PRODUCTION_PROJECT}.{WAREHOUSE_DATASET}.schedules`
WHERE season BETWEEN 2022 AND 2025
  AND week BETWEEN 1 AND 18
  AND game_type = 'REG'
""".strip()

_WEEKLY_ROWS_SQL: Final = f"""
SELECT
  'row' AS record_kind,
  'weekly-player-stats' AS slice_kind,
  TO_JSON_STRING(STRUCT(
    air_yards_share, carries, fumbles_lost_total, opponent_team,
    passing_interceptions, passing_tds, passing_yards, player_id, position,
    receiving_tds, receiving_yards, receptions, rushing_tds, rushing_yards,
    CAST(season AS INT64) AS season, target_share, targets, team,
    CAST(week AS INT64) AS week
  )) AS row_json
FROM `{PRODUCTION_PROJECT}.{WAREHOUSE_DATASET}.weekly_stats`
WHERE season BETWEEN 2022 AND 2025
  AND week BETWEEN 1 AND 18
  AND season_type = 'REG'
""".strip()

_LEGACY_DEPTH_ROWS_SQL: Final = f"""
SELECT
  'row' AS record_kind,
  'legacy-depth' AS slice_kind,
  TO_JSON_STRING(STRUCT(
    club_code, depth_position, depth_team, formation, gsis_id,
    jersey_number, position, CAST(season AS INT64) AS season,
    CAST(week AS INT64) AS week
  )) AS row_json
FROM `{PRODUCTION_PROJECT}.{WAREHOUSE_DATASET}.depth_charts`
WHERE season BETWEEN 2022 AND 2024
  AND week BETWEEN 1 AND 18
""".strip()

_SNAPSHOT_DEPTH_ROWS_SQL: Final = f"""
SELECT
  'row' AS record_kind,
  'snapshot-depth' AS slice_kind,
  TO_JSON_STRING(STRUCT(
    FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ', TIMESTAMP(dt), 'UTC') AS dt,
    gsis_id, pos_abb, CAST(pos_rank AS INT64) AS pos_rank, team
  )) AS row_json
FROM `{PRODUCTION_PROJECT}.{WAREHOUSE_DATASET}.depth_charts_snapshots`
WHERE EXTRACT(YEAR FROM DATE(dt)) = 2025
""".strip()

_PFR_ROWS_SQL: Final = f"""
SELECT
  'row' AS record_kind,
  'pfr-pass-rush' AS slice_kind,
  TO_JSON_STRING(STRUCT(
    def_pressures, def_sacks, def_times_blitzed, def_times_hurried,
    game_id, pfr_player_id, CAST(season AS INT64) AS season, team,
    CAST(week AS INT64) AS week
  )) AS row_json
FROM `{PRODUCTION_PROJECT}.{WAREHOUSE_DATASET}.pfr_advstats_def`
WHERE season BETWEEN 2022 AND 2025 AND week BETWEEN 1 AND 18
UNION ALL
SELECT
  'row', 'pfr-secondary',
  TO_JSON_STRING(STRUCT(
    def_completions_allowed, def_targets, def_yards_allowed,
    game_id, pfr_player_id, CAST(season AS INT64) AS season, team,
    CAST(week AS INT64) AS week
  ))
FROM `{PRODUCTION_PROJECT}.{WAREHOUSE_DATASET}.pfr_advstats_def`
WHERE season BETWEEN 2022 AND 2025 AND week BETWEEN 1 AND 18
UNION ALL
SELECT
  'row', 'pfr-snap-positions',
  TO_JSON_STRING(STRUCT(
    defense_snaps, game_id, pfr_player_id, position,
    CAST(season AS INT64) AS season, team, CAST(week AS INT64) AS week
  ))
FROM `{PRODUCTION_PROJECT}.{WAREHOUSE_DATASET}.snap_counts`
WHERE season BETWEEN 2022 AND 2025 AND week BETWEEN 1 AND 18
""".strip()

_WAREHOUSE_DEFINITIONS: Final = (
    (source.SCHEDULE_PACK, ("schedule-games",), ("schedules",), _SCHEDULE_ROWS_SQL),
    (
        source.WEEKLY_STATS_PACK,
        ("weekly-player-stats",),
        ("weekly_stats",),
        _WEEKLY_ROWS_SQL,
    ),
    (
        source.LEGACY_DEPTH_PACK,
        ("legacy-depth",),
        ("depth_charts",),
        _LEGACY_DEPTH_ROWS_SQL,
    ),
    (
        source.SNAPSHOT_DEPTH_PACK,
        ("snapshot-depth",),
        ("depth_charts_snapshots",),
        _SNAPSHOT_DEPTH_ROWS_SQL,
    ),
    (
        source.PFR_DEFENSE_PACK,
        ("pfr-pass-rush", "pfr-secondary", "pfr-snap-positions"),
        ("pfr_advstats_def", "snap_counts"),
        _PFR_ROWS_SQL,
    ),
)


def _render_warehouse_query(row_sql: str, relations: Sequence[str]) -> str:
    rendered = f"""
WITH captured AS (
{row_sql}
), relation_metadata AS (
{_metadata_sql(relations)}
)
SELECT record_kind, slice_kind, row_json FROM captured
UNION ALL
SELECT record_kind, slice_kind, row_json FROM relation_metadata
ORDER BY record_kind, slice_kind, row_json
""".strip()
    if "realized" in rendered.lower() or "contest" in rendered.lower():
        _fail("warehouse query contains a forbidden outcome carrier")
    return rendered


def frozen_warehouse_query_specs_v1(run_id: object) -> list[dict[str, object]]:
    normalized_run_id = _run_id(run_id)
    specs: list[dict[str, object]] = []
    for ordinal, (pack_id, slices, relations, row_sql) in enumerate(
        _WAREHOUSE_DEFINITIONS
    ):
        query = _render_warehouse_query(row_sql, relations)
        query_sha = sha256(query.encode("utf-8")).hexdigest()
        job_id = (
            "r6_matchup_7pack_"
            f"{normalized_run_id.replace('-', '_')}_{ordinal}_{query_sha[:12]}"
        )
        body: dict[str, object] = {
            "schema_version": WAREHOUSE_QUERY_SPEC_SCHEMA,
            "ordinal": ordinal,
            "pack_id": pack_id,
            "project_id": PRODUCTION_PROJECT,
            "dataset_id": WAREHOUSE_DATASET,
            "location": WAREHOUSE_LOCATION,
            "use_legacy_sql": False,
            "use_query_cache": False,
            "maximum_bytes_billed": MAX_QUERY_BYTES_BILLED,
            "named_parameters": [],
            "input_relations": list(relations),
            "slice_kinds": list(slices),
            "canonical_query": query,
            "query_sha256": query_sha,
            "job_id": job_id,
        }
        specs.append(_with_hash(body, field_name="query_spec_sha256"))
    if (
        len(specs) != WAREHOUSE_QUERY_COUNT
        or [value["pack_id"] for value in specs] != list(WAREHOUSE_PACK_IDS)
    ):
        _fail("warehouse query registry differs from the fixed five-pack law")
    return specs


def validate_warehouse_query_spec_v1(
    value: object, *, expected_run_id: object,
) -> dict[str, object]:
    item = _mapping(value, label="warehouse query spec")
    expected = frozen_warehouse_query_specs_v1(expected_run_id)
    ordinal = _exact_int(item.get("ordinal"), label="query ordinal")
    if ordinal >= len(expected) or item != expected[ordinal]:
        _fail("warehouse query spec differs from the frozen query registry")
    return expected[ordinal]


def _registry_entry(pack_id: str) -> dict[str, object]:
    registry = source.frozen_upstream_pack_registry_v1()
    for raw in registry["packs"]:
        entry = dict(raw)
        if entry["pack_id"] == pack_id:
            return entry
    _fail("pack ID is not registered")


def _schema_for_slice(pack_id: str, slice_kind: str) -> dict[str, object]:
    entry = _registry_entry(pack_id)
    for raw in entry["positive_row_schemas"]:
        schema = dict(raw)
        if schema["slice_kind"] == slice_kind:
            return schema
    _fail("slice kind is not registered for pack")


_IDENTITY_FIELDS: Final = {
    "schedule-games": ("game_id", "home_team", "away_team", "season", "week"),
    "weekly-player-stats": ("player_id", "team", "season", "week"),
    "legacy-depth": ("gsis_id", "season", "week"),
    "snapshot-depth": ("gsis_id", "team", "dt"),
    "pfr-pass-rush": ("pfr_player_id", "game_id", "season", "week"),
    "pfr-secondary": ("pfr_player_id", "game_id", "season", "week"),
    "pfr-snap-positions": ("pfr_player_id", "game_id", "season", "week"),
    "fp-route-share": ("gsis_id", "season", "week"),
    "fp-alignment": ("gsis_id", "season", "target_week"),
    "fp-receiver-shell": ("gsis_id", "season"),
    "fp-defense-shell": ("team", "season"),
    "sis-defender-alignment": (
        "defender_player_id", "defense", "alignment", "season", "week",
    ),
    "sis-run-context": ("team", "season", "week"),
}


def _json_scalar(value: object, *, label: str) -> object:
    if value is None or type(value) in (str, bool, int):
        return value
    if type(value) is float and value == value and value not in (float("inf"), -float("inf")):
        return value
    _fail(f"{label} must be a finite JSON scalar")


def _normalize_source_row(
    *, pack_id: str, slice_kind: str, value: object,
) -> dict[str, object]:
    schema = _schema_for_slice(pack_id, slice_kind)
    expected_fields = frozenset(str(field) for field in schema["row_fields"])
    row = _mapping(value, label=f"{slice_kind} row")
    _exact_keys(row, expected_fields, label=f"{slice_kind} row")
    normalized = {
        field: _json_scalar(row[field], label=f"{slice_kind}.{field}")
        for field in sorted(expected_fields)
    }
    period = _registry_entry(pack_id)
    if "season" in normalized:
        season = normalized["season"]
        if (
            type(season) is not int
            or not int(period["source_period_min"]["season"])
            <= season
            <= int(period["source_period_max"]["season"])
        ):
            _fail(f"{slice_kind}.season escapes the registered source period")
    for field_name in ("week", "target_week"):
        if field_name in normalized and (
            type(normalized[field_name]) is not int
            or not 1 <= int(normalized[field_name]) <= 18
        ):
            _fail(f"{slice_kind}.{field_name} escapes regular-season weeks")
    if "source_sha256" in normalized:
        _digest(
            normalized["source_sha256"], label=f"{slice_kind}.source_sha256"
        )
    for field_name in ("alignment_supported", "split_duplicate"):
        if field_name in normalized and type(normalized[field_name]) is not bool:
            _fail(f"{slice_kind}.{field_name} must be boolean")
    if "kickoff_time_utc" in normalized:
        _timestamp(
            normalized["kickoff_time_utc"],
            label=f"{slice_kind}.kickoff_time_utc",
        )
    if "dt" in normalized:
        dt = _timestamp(normalized["dt"], label=f"{slice_kind}.dt")
        if not dt.startswith("2025-"):
            _fail("snapshot-depth.dt escapes the registered 2025 source period")
    if "gameday" in normalized:
        gameday = _string(normalized["gameday"], label=f"{slice_kind}.gameday")
        try:
            parsed_day = datetime.strptime(gameday, "%Y-%m-%d")
        except ValueError as exc:
            raise CorpusR6MatchupSevenPackCaptureV1Error(
                f"{slice_kind}.gameday is not canonical"
            ) from exc
        if not 2022 <= parsed_day.year <= 2025:
            _fail(f"{slice_kind}.gameday escapes the registered source period")
    if "game_type" in normalized and normalized["game_type"] != "REG":
        _fail(f"{slice_kind}.game_type differs from the regular-season law")
    return normalized


def _row_identity_resolved(slice_kind: str, row: Mapping[str, object]) -> bool:
    fields = _IDENTITY_FIELDS.get(slice_kind)
    if fields is None:
        _fail("slice identity law is not registered")
    for field_name in fields:
        value = row.get(field_name)
        if value is None or type(value) is str and not value.strip():
            return False
    return True


def _missing_accounting(
    rows_by_slice: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    fingerprints: list[dict[str, str]] = []
    source_count = 0
    retained_count = 0
    by_slice: list[dict[str, object]] = []
    for slice_kind in sorted(rows_by_slice):
        rows = list(rows_by_slice[slice_kind])
        resolved = [row for row in rows if _row_identity_resolved(slice_kind, row)]
        missing = [row for row in rows if not _row_identity_resolved(slice_kind, row)]
        for row in missing:
            fingerprints.append({
                "slice_kind": slice_kind,
                "canonical_row_sha256": source.canonical_sha256(row),
            })
        source_count += len(rows)
        retained_count += len(resolved)
        by_slice.append({
            "slice_kind": slice_kind,
            "source_row_count": len(rows),
            "retained_row_count": len(resolved),
            "missing_id_count": len(missing),
            "missing_id_rows_sha256": source.canonical_sha256(sorted(
                [
                    source.canonical_sha256(row)
                    for row in missing
                ]
            )),
        })
    fingerprints.sort(key=source.canonical_json_bytes)
    body = {
        "retention_rule": MISSING_ID_RETENTION_RULE,
        "source_row_count": source_count,
        "retained_row_count": retained_count,
        "missing_id_count": len(fingerprints),
        "missing_id_fingerprints": fingerprints,
        "missing_id_fingerprints_sha256": source.canonical_sha256(fingerprints),
        "slices": by_slice,
        "slice_accounting_sha256": source.canonical_sha256(by_slice),
    }
    if source_count != retained_count + len(fingerprints):
        _fail("missing-ID accounting does not explain every source row")
    return body


def _validate_missing_accounting_v1(
    value: object, *, expected_pack_id: str, expected_retained_count: int,
) -> dict[str, object]:
    item = _mapping(value, label="missing-ID accounting")
    _exact_keys(
        item,
        frozenset({
            "retention_rule", "source_row_count", "retained_row_count",
            "missing_id_count", "missing_id_fingerprints",
            "missing_id_fingerprints_sha256", "slices", "slice_accounting_sha256",
        }),
        label="missing-ID accounting",
    )
    source_count = _exact_int(
        item["source_row_count"], label="missing-ID source row count"
    )
    retained_count = _exact_int(
        item["retained_row_count"], label="missing-ID retained row count"
    )
    missing_count = _exact_int(
        item["missing_id_count"], label="missing-ID count"
    )
    raw_fingerprints = _sequence(
        item["missing_id_fingerprints"], label="missing-ID fingerprints"
    )
    fingerprints: list[dict[str, str]] = []
    for ordinal, raw in enumerate(raw_fingerprints):
        fingerprint = _mapping(raw, label=f"missing-ID fingerprint[{ordinal}]")
        _exact_keys(
            fingerprint,
            frozenset({"slice_kind", "canonical_row_sha256"}),
            label=f"missing-ID fingerprint[{ordinal}]",
        )
        fingerprints.append({
            "slice_kind": _string(
                fingerprint["slice_kind"], label="missing-ID fingerprint slice"
            ),
            "canonical_row_sha256": _digest(
                fingerprint["canonical_row_sha256"],
                label="missing-ID row fingerprint",
            ),
        })
    if (
        fingerprints != sorted(fingerprints, key=source.canonical_json_bytes)
        or item["missing_id_fingerprints_sha256"]
        != source.canonical_sha256(fingerprints)
    ):
        _fail("missing-ID fingerprint manifest differs")
    raw_slices = _sequence(item["slices"], label="missing-ID slices")
    expected_slices = sorted(
        str(schema["slice_kind"])
        for schema in _registry_entry(expected_pack_id)["positive_row_schemas"]
    )
    slices: list[dict[str, object]] = []
    for ordinal, raw in enumerate(raw_slices):
        entry = _mapping(raw, label=f"missing-ID slice[{ordinal}]")
        _exact_keys(
            entry,
            frozenset({
                "slice_kind", "source_row_count", "retained_row_count",
                "missing_id_count", "missing_id_rows_sha256",
            }),
            label=f"missing-ID slice[{ordinal}]",
        )
        normalized = {
            "slice_kind": _string(
                entry["slice_kind"], label="missing-ID slice kind"
            ),
            "source_row_count": _exact_int(
                entry["source_row_count"], label="missing-ID slice source count"
            ),
            "retained_row_count": _exact_int(
                entry["retained_row_count"],
                label="missing-ID slice retained count",
            ),
            "missing_id_count": _exact_int(
                entry["missing_id_count"], label="missing-ID slice missing count"
            ),
            "missing_id_rows_sha256": _digest(
                entry["missing_id_rows_sha256"],
                label="missing-ID slice row manifest",
            ),
        }
        if normalized["source_row_count"] != (
            normalized["retained_row_count"] + normalized["missing_id_count"]
        ):
            _fail("missing-ID slice accounting does not balance")
        slice_fingerprints = sorted(
            value["canonical_row_sha256"] for value in fingerprints
            if value["slice_kind"] == normalized["slice_kind"]
        )
        if (
            len(slice_fingerprints) != normalized["missing_id_count"]
            or normalized["missing_id_rows_sha256"]
            != source.canonical_sha256(slice_fingerprints)
        ):
            _fail("missing-ID slice fingerprints differ")
        slices.append(normalized)
    if (
        [value["slice_kind"] for value in slices] != expected_slices
        or item["retention_rule"] != MISSING_ID_RETENTION_RULE
        or source_count != retained_count + missing_count
        or retained_count != expected_retained_count
        or sum(int(value["source_row_count"]) for value in slices)
        != source_count
        or sum(int(value["retained_row_count"]) for value in slices)
        != retained_count
        or sum(int(value["missing_id_count"]) for value in slices)
        != missing_count
        or item["slice_accounting_sha256"] != source.canonical_sha256(slices)
    ):
        _fail("missing-ID aggregate accounting differs")
    normalized_item = dict(item)
    normalized_item["missing_id_fingerprints"] = fingerprints
    normalized_item["slices"] = slices
    if source.canonical_json_bytes(normalized_item) != source.canonical_json_bytes(
        item
    ):
        _fail("missing-ID accounting canonical structure differs")
    return normalized_item


def _positive_slices(
    *, pack_id: str, rows_by_slice: Mapping[str, Sequence[Mapping[str, object]]],
) -> list[dict[str, object]]:
    entry = _registry_entry(pack_id)
    expected_kinds = [
        str(schema["slice_kind"]) for schema in entry["positive_row_schemas"]
    ]
    if set(rows_by_slice) != set(expected_kinds):
        _fail("source rows do not cover every registered slice exactly")
    slices: list[dict[str, object]] = []
    for slice_kind in expected_kinds:
        retained = [
            dict(row) for row in rows_by_slice[slice_kind]
            if _row_identity_resolved(slice_kind, row)
        ]
        if not retained:
            _fail("every source-pack slice needs at least one resolved positive row")
        slices.append({"slice_kind": slice_kind, "rows": retained})
    try:
        return source.build_upstream_pack_rows_v1(
            pack_id=pack_id, slices=slices
        )["slices"]
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(str(exc)) from exc


def _build_pack_rows(
    *, pack_id: str, rows_by_slice: Mapping[str, Sequence[Mapping[str, object]]],
) -> dict[str, object]:
    slices = _positive_slices(pack_id=pack_id, rows_by_slice=rows_by_slice)
    try:
        return source.build_upstream_pack_rows_v1(
            pack_id=pack_id,
            slices=[
                {"slice_kind": value["slice_kind"], "rows": value["rows"]}
                for value in slices
            ],
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(str(exc)) from exc


def build_artifact_row_shard_v1(
    *, pack_id: str, slice_kind: str,
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if pack_id not in ARTIFACT_PACK_IDS:
        _fail("artifact row shard pack is not FP or SIS")
    normalized = [
        _normalize_source_row(
            pack_id=pack_id, slice_kind=slice_kind, value=value
        )
        for value in rows
    ]
    if not normalized:
        _fail("artifact row shard must not be empty")
    normalized.sort(key=source.canonical_json_bytes)
    encoded = [source.canonical_json_bytes(value) for value in normalized]
    if len(encoded) != len(set(encoded)):
        _fail("artifact row shard contains duplicate rows")
    missing = [
        value for value in normalized
        if not _row_identity_resolved(slice_kind, value)
    ]
    body: dict[str, object] = {
        "schema_version": ARTIFACT_ROW_SHARD_SCHEMA,
        "pack_id": pack_id,
        "slice_kind": slice_kind,
        "row_schema_sha256": _schema_for_slice(pack_id, slice_kind)[
            "row_schema_sha256"
        ],
        "rows": normalized,
        "row_count": len(normalized),
        "rows_sha256": source.canonical_sha256(normalized),
        "retained_row_count": len(normalized) - len(missing),
        "missing_id_count": len(missing),
        "missing_id_rows_sha256": source.canonical_sha256(sorted(
            [source.canonical_sha256(value) for value in missing]
        )),
        "evidence_class": EVIDENCE_CLASS,
        "authoritative_pit": False,
        **_policy(),
    }
    return _with_hash(body, field_name="artifact_row_shard_sha256")


def validate_artifact_row_shard_v1(
    value: object, *, expected_pack_id: str | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="artifact row shard")
    rows = _sequence(item.get("rows"), label="artifact shard rows")
    rebuilt = build_artifact_row_shard_v1(
        pack_id=_string(item.get("pack_id"), label="artifact shard pack"),
        slice_kind=_string(item.get("slice_kind"), label="artifact shard slice"),
        rows=[_mapping(row, label="artifact shard row") for row in rows],
    )
    if rebuilt != item:
        _fail("artifact row shard canonical replay differs")
    if expected_pack_id is not None and rebuilt["pack_id"] != expected_pack_id:
        _fail("artifact row shard differs from expected pack")
    return rebuilt


def build_artifact_pack_manifest_v1(
    *, manifest_id: str, pack_id: str,
    shard_objects: Sequence[Mapping[str, object]],
    shard_identities: Sequence[Mapping[str, object]],
    source_manifest_identities: Sequence[Mapping[str, object]],
    source_artifact_identities: Sequence[Mapping[str, object]],
    projection_code_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build the normalized frozen-manifest boundary for one vendor pack.

    Original heterogeneous vendor/run manifests and source artifacts remain
    immutable predecessors.  The normalized shards are not accepted unless
    this manifest binds all predecessor identities, every registered slice,
    and missing-ID accounting derived from the shard bodies.
    """
    if pack_id not in ARTIFACT_PACK_IDS:
        _fail("artifact pack manifest is not FP or SIS")
    if type(manifest_id) is not str or _RUN_ID.fullmatch(manifest_id) is None:
        _fail("artifact manifest ID must be a canonical identifier")
    objects = list(shard_objects)
    identities = list(shard_identities)
    if not 1 <= len(objects) == len(identities) <= MAX_ARTIFACT_SHARDS_PER_PACK:
        _fail("artifact manifest shard count differs")
    descriptors: list[dict[str, object]] = []
    rows_by_slice: dict[str, list[dict[str, object]]] = {}
    for ordinal, (body_value, identity_value) in enumerate(
        zip(objects, identities, strict=True)
    ):
        body = validate_artifact_row_shard_v1(
            body_value, expected_pack_id=pack_id
        )
        raw = source.canonical_json_bytes(body)
        identity = _bind_bytes(
            identity_value, raw, label=f"artifact row shard[{ordinal}]"
        )
        slice_kind = str(body["slice_kind"])
        rows_by_slice.setdefault(slice_kind, []).extend(
            dict(row) for row in body["rows"]
        )
        descriptors.append({
            "ordinal": ordinal,
            "slice_kind": slice_kind,
            "identity": identity,
            "row_count": body["row_count"],
            "rows_sha256": body["rows_sha256"],
            "retained_row_count": body["retained_row_count"],
            "missing_id_count": body["missing_id_count"],
            "artifact_row_shard_sha256": body["artifact_row_shard_sha256"],
        })
    descriptor_uris = [str(value["identity"]["uri"]) for value in descriptors]
    if descriptor_uris != sorted(descriptor_uris) or len(descriptor_uris) != len(
        set(descriptor_uris)
    ):
        _fail("artifact shard identities must be unique and URI-sorted")
    # This also proves all registered slices have at least one resolved row and
    # catches duplicate rows across shards.
    rows_object = _build_pack_rows(pack_id=pack_id, rows_by_slice=rows_by_slice)
    accounting = _missing_accounting(rows_by_slice)
    source_manifests = _sorted_identities(
        source_manifest_identities,
        label="artifact source manifests",
        minimum=1,
        maximum=MAX_SOURCE_MANIFESTS_PER_PACK,
    )
    source_artifacts = _sorted_identities(
        source_artifact_identities,
        label="artifact source objects",
        minimum=1,
        maximum=MAX_SOURCE_ARTIFACTS_PER_PACK,
    )
    all_uris = (
        descriptor_uris
        + [str(value["uri"]) for value in source_manifests]
        + [str(value["uri"]) for value in source_artifacts]
    )
    if len(all_uris) != len(set(all_uris)):
        _fail("artifact manifest reuses an object URI across semantic roles")
    code = _code_identity(
        projection_code_identity, label="artifact projection code identity"
    )
    body: dict[str, object] = {
        "schema_version": ARTIFACT_PACK_MANIFEST_SCHEMA,
        "manifest_id": manifest_id,
        "pack_id": pack_id,
        "source_kind": "frozen-artifact-projection",
        "evidence_class": EVIDENCE_CLASS,
        "authoritative_pit": False,
        "source_manifest_identities": source_manifests,
        "source_manifest_identity_manifest_sha256": source.canonical_sha256(
            source_manifests
        ),
        "source_artifact_identities": source_artifacts,
        "source_artifact_identity_manifest_sha256": source.canonical_sha256(
            source_artifacts
        ),
        "projection_code_identity": code,
        "shard_count": len(descriptors),
        "shards": descriptors,
        "shard_manifest_sha256": source.canonical_sha256(descriptors),
        "positive_row_schema_manifest_sha256": _registry_entry(pack_id)[
            "positive_row_schema_manifest_sha256"
        ],
        "projected_row_count": rows_object["row_count"],
        "projected_rows_sha256": rows_object["rows_sha256"],
        "missing_id_accounting": accounting,
        "missing_id_accounting_sha256": source.canonical_sha256(accounting),
        **_policy(),
    }
    return _with_hash(body, field_name="artifact_pack_manifest_sha256")


_ARTIFACT_MANIFEST_FIELDS: Final = frozenset({
    "schema_version",
    "manifest_id",
    "pack_id",
    "source_kind",
    "evidence_class",
    "authoritative_pit",
    "source_manifest_identities",
    "source_manifest_identity_manifest_sha256",
    "source_artifact_identities",
    "source_artifact_identity_manifest_sha256",
    "projection_code_identity",
    "shard_count",
    "shards",
    "shard_manifest_sha256",
    "positive_row_schema_manifest_sha256",
    "projected_row_count",
    "projected_rows_sha256",
    "missing_id_accounting",
    "missing_id_accounting_sha256",
    *source.POLICY_FIELDS,
    "artifact_pack_manifest_sha256",
})


def validate_artifact_pack_manifest_structure_v1(
    value: object, *, expected_pack_id: str | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="artifact pack manifest")
    _exact_keys(item, _ARTIFACT_MANIFEST_FIELDS, label="artifact pack manifest")
    _validate_hash(
        item,
        field_name="artifact_pack_manifest_sha256",
        label="artifact pack manifest",
    )
    _validate_policy(item, label="artifact pack manifest")
    pack_id = _string(item["pack_id"], label="artifact manifest pack")
    if (
        pack_id not in ARTIFACT_PACK_IDS
        or expected_pack_id is not None and pack_id != expected_pack_id
        or item["schema_version"] != ARTIFACT_PACK_MANIFEST_SCHEMA
        or item["source_kind"] != "frozen-artifact-projection"
        or item["evidence_class"] != EVIDENCE_CLASS
        or item["authoritative_pit"] is not False
        or type(item["manifest_id"]) is not str
        or _RUN_ID.fullmatch(str(item["manifest_id"])) is None
    ):
        _fail("artifact pack manifest fixed law differs")
    source_manifests = _sorted_identities(
        item["source_manifest_identities"],
        label="artifact source manifests",
        minimum=1,
        maximum=MAX_SOURCE_MANIFESTS_PER_PACK,
    )
    source_artifacts = _sorted_identities(
        item["source_artifact_identities"],
        label="artifact source objects",
        minimum=1,
        maximum=MAX_SOURCE_ARTIFACTS_PER_PACK,
    )
    if (
        item["source_manifest_identity_manifest_sha256"]
        != source.canonical_sha256(source_manifests)
        or item["source_artifact_identity_manifest_sha256"]
        != source.canonical_sha256(source_artifacts)
    ):
        _fail("artifact predecessor identity manifest differs")
    code = _code_identity(
        item["projection_code_identity"], label="artifact projection code"
    )
    raw_descriptors = _sequence(item["shards"], label="artifact shard descriptors")
    count = _exact_int(item["shard_count"], label="artifact shard count", minimum=1)
    if count != len(raw_descriptors) or count > MAX_ARTIFACT_SHARDS_PER_PACK:
        _fail("artifact shard count differs")
    descriptors: list[dict[str, object]] = []
    descriptor_fields = frozenset({
        "ordinal", "slice_kind", "identity", "row_count", "rows_sha256",
        "retained_row_count", "missing_id_count", "artifact_row_shard_sha256",
    })
    for ordinal, raw in enumerate(raw_descriptors):
        descriptor = _mapping(raw, label=f"artifact shard descriptor[{ordinal}]")
        _exact_keys(
            descriptor, descriptor_fields,
            label=f"artifact shard descriptor[{ordinal}]",
        )
        normalized = {
            "ordinal": _exact_int(
                descriptor["ordinal"], label="artifact shard ordinal"
            ),
            "slice_kind": _string(
                descriptor["slice_kind"], label="artifact shard slice"
            ),
            "identity": _identity(
                descriptor["identity"], label="artifact shard identity"
            ),
            "row_count": _exact_int(
                descriptor["row_count"], label="artifact shard row count", minimum=1
            ),
            "rows_sha256": _digest(
                descriptor["rows_sha256"], label="artifact shard rows SHA"
            ),
            "retained_row_count": _exact_int(
                descriptor["retained_row_count"],
                label="artifact shard retained count",
            ),
            "missing_id_count": _exact_int(
                descriptor["missing_id_count"], label="artifact shard missing count"
            ),
            "artifact_row_shard_sha256": _digest(
                descriptor["artifact_row_shard_sha256"],
                label="artifact shard internal SHA",
            ),
        }
        if (
            normalized["ordinal"] != ordinal
            or normalized["retained_row_count"]
            + normalized["missing_id_count"] != normalized["row_count"]
        ):
            _fail("artifact shard descriptor count/order differs")
        _schema_for_slice(pack_id, str(normalized["slice_kind"]))
        descriptors.append(normalized)
    uris = [str(value["identity"]["uri"]) for value in descriptors]
    if uris != sorted(uris) or len(uris) != len(set(uris)):
        _fail("artifact shard descriptor URIs differ")
    all_uris = (
        uris
        + [str(value["uri"]) for value in source_manifests]
        + [str(value["uri"]) for value in source_artifacts]
    )
    if len(all_uris) != len(set(all_uris)):
        _fail("artifact manifest predecessor URIs overlap")
    projected_count = _exact_int(
        item["projected_row_count"],
        label="artifact projected row count",
        minimum=1,
    )
    accounting = _validate_missing_accounting_v1(
        item["missing_id_accounting"],
        expected_pack_id=pack_id,
        expected_retained_count=projected_count,
    )
    if (
        item["shard_manifest_sha256"] != source.canonical_sha256(descriptors)
        or item["missing_id_accounting_sha256"]
        != source.canonical_sha256(accounting)
        or item["positive_row_schema_manifest_sha256"]
        != _registry_entry(pack_id)["positive_row_schema_manifest_sha256"]
        or _SHA256.fullmatch(str(item["projected_rows_sha256"])) is None
    ):
        _fail("artifact manifest aggregate binding differs")
    normalized = dict(item)
    normalized["source_manifest_identities"] = source_manifests
    normalized["source_artifact_identities"] = source_artifacts
    normalized["projection_code_identity"] = code
    normalized["shards"] = descriptors
    if source.canonical_json_bytes(normalized) != source.canonical_json_bytes(item):
        _fail("artifact pack manifest canonical structure differs")
    return normalized


def _open_artifact_pack_manifest_v1(
    *, manifest_identity: Mapping[str, object], reader: BoundedExactReaderV1,
    expected_pack_id: str,
) -> dict[str, object]:
    normalized_identity = _identity(
        manifest_identity, label=f"{expected_pack_id} artifact manifest"
    )
    raw = reader.read(
        normalized_identity, label=f"{expected_pack_id} artifact manifest"
    )
    manifest = validate_artifact_pack_manifest_structure_v1(
        _canonical_object(raw, label=f"{expected_pack_id} artifact manifest"),
        expected_pack_id=expected_pack_id,
    )
    rows_by_slice: dict[str, list[dict[str, object]]] = {}
    shard_objects: list[dict[str, object]] = []
    shard_identities: list[dict[str, object]] = []
    for ordinal, raw_descriptor in enumerate(manifest["shards"]):
        descriptor = dict(raw_descriptor)
        identity = dict(descriptor["identity"])
        shard_raw = reader.read(
            identity, label=f"{expected_pack_id} artifact shard[{ordinal}]"
        )
        shard = validate_artifact_row_shard_v1(
            _canonical_object(
                shard_raw, label=f"{expected_pack_id} artifact shard[{ordinal}]"
            ),
            expected_pack_id=expected_pack_id,
        )
        if (
            shard["slice_kind"] != descriptor["slice_kind"]
            or shard["row_count"] != descriptor["row_count"]
            or shard["rows_sha256"] != descriptor["rows_sha256"]
            or shard["retained_row_count"] != descriptor["retained_row_count"]
            or shard["missing_id_count"] != descriptor["missing_id_count"]
            or shard["artifact_row_shard_sha256"]
            != descriptor["artifact_row_shard_sha256"]
        ):
            _fail("artifact shard differs from its manifest descriptor")
        slice_kind = str(shard["slice_kind"])
        rows_by_slice.setdefault(slice_kind, []).extend(
            dict(row) for row in shard["rows"]
        )
        shard_objects.append(shard)
        shard_identities.append(identity)
    rows_object = _build_pack_rows(
        pack_id=expected_pack_id, rows_by_slice=rows_by_slice
    )
    accounting = _missing_accounting(rows_by_slice)
    rebuilt = build_artifact_pack_manifest_v1(
        manifest_id=str(manifest["manifest_id"]),
        pack_id=expected_pack_id,
        shard_objects=shard_objects,
        shard_identities=shard_identities,
        source_manifest_identities=manifest["source_manifest_identities"],
        source_artifact_identities=manifest["source_artifact_identities"],
        projection_code_identity=manifest["projection_code_identity"],
    )
    if rebuilt != manifest:
        _fail("artifact pack manifest deep replay differs")
    # Exact-open every frozen predecessor.  Their heterogeneous bytes are not
    # reinterpreted here; the normalized manifest and projection code bind how
    # they were transformed into the canonical shards.
    for ordinal, identity in enumerate(manifest["source_manifest_identities"]):
        reader.read(
            identity, label=f"{expected_pack_id} source manifest[{ordinal}]"
        )
    for ordinal, identity in enumerate(manifest["source_artifact_identities"]):
        reader.read(
            identity, label=f"{expected_pack_id} source artifact[{ordinal}]"
        )
    return {
        "manifest_identity": normalized_identity,
        "manifest": manifest,
        "rows_object": rows_object,
        "missing_id_accounting": accounting,
    }


def build_implementation_authority_v1(
    *, source_commit_sha: str,
    measurements: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if type(source_commit_sha) is not str or _COMMIT.fullmatch(source_commit_sha) is None:
        _fail("implementation source commit must be lowercase 40-hex")
    raw = list(measurements)
    if len(raw) != len(IMPLEMENTATION_PATHS):
        _fail("implementation measurement count differs")
    normalized: list[dict[str, object]] = []
    for ordinal, (value, expected_path) in enumerate(
        zip(raw, IMPLEMENTATION_PATHS, strict=True)
    ):
        item = _mapping(value, label=f"implementation measurement[{ordinal}]")
        _exact_keys(
            item, frozenset({"relative_path", "sha256", "bytes"}),
            label=f"implementation measurement[{ordinal}]",
        )
        retained = {
            "relative_path": _string(
                item["relative_path"], label="implementation path"
            ),
            "sha256": _digest(item["sha256"], label="implementation SHA"),
            "bytes": _exact_int(
                item["bytes"], label="implementation bytes", minimum=1
            ),
        }
        if retained["relative_path"] != expected_path:
            _fail("implementation measurement path/order differs")
        normalized.append(retained)
    body = {
        "schema_version": IMPLEMENTATION_AUTHORITY_SCHEMA,
        "source_commit_sha": source_commit_sha,
        "measurements": normalized,
        "measurement_manifest_sha256": source.canonical_sha256(normalized),
        "local_project_runtime_surface_paths": list(IMPLEMENTATION_PATHS),
        "local_project_runtime_surface_manifest_sha256": source.canonical_sha256(
            list(IMPLEMENTATION_PATHS)
        ),
        "local_project_runtime_surface_complete": True,
        "third_party_runtime_image_binding_present": False,
        "third_party_runtime_image_binding_required_for_authority": True,
        "git_head_exact": True,
        "git_status_clean_for_implementation_paths": True,
        "working_tree_equals_commit_blobs": True,
    }
    return _with_hash(body, field_name="implementation_authority_sha256")


def validate_implementation_authority_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="implementation authority")
    _validate_hash(
        item,
        field_name="implementation_authority_sha256",
        label="implementation authority",
    )
    rebuilt = build_implementation_authority_v1(
        source_commit_sha=_string(
            item.get("source_commit_sha"), label="implementation commit"
        ),
        measurements=[
            _mapping(value, label="implementation measurement")
            for value in _sequence(
                item.get("measurements"), label="implementation measurements"
            )
        ],
    )
    if rebuilt != item:
        _fail("implementation authority canonical replay differs")
    return rebuilt


def _parse_result_row_json(value: object, *, label: str) -> dict[str, object]:
    text = _string(value, label=label)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(
            f"{label} is not JSON"
        ) from exc
    return _mapping(parsed, label=label)


def _normalize_relation_metadata(
    value: object, *, expected_relation: str,
) -> dict[str, object]:
    item = _mapping(value, label=f"{expected_relation} relation metadata")
    fields = frozenset({
        "project_id", "dataset_id", "relation_id", "row_count", "size_bytes",
        "modified_time_utc", "columns",
    })
    _exact_keys(item, fields, label=f"{expected_relation} relation metadata")
    raw_columns = _sequence(
        item["columns"], label=f"{expected_relation} schema columns"
    )
    columns: list[dict[str, object]] = []
    seen_names: set[str] = set()
    for ordinal, raw in enumerate(raw_columns):
        column = _mapping(raw, label=f"{expected_relation} column[{ordinal}]")
        _exact_keys(
            column,
            frozenset({"name", "data_type", "is_nullable", "ordinal_position"}),
            label=f"{expected_relation} column[{ordinal}]",
        )
        normalized = {
            "name": _string(column["name"], label="warehouse column name"),
            "data_type": _string(
                column["data_type"], label="warehouse column data type"
            ),
            "is_nullable": _string(
                column["is_nullable"], label="warehouse column nullability"
            ),
            "ordinal_position": _exact_int(
                column["ordinal_position"],
                label="warehouse column ordinal",
                minimum=1,
            ),
        }
        if (
            normalized["name"] in seen_names
            or normalized["ordinal_position"] != ordinal + 1
            or normalized["is_nullable"] not in ("YES", "NO")
        ):
            _fail("warehouse relation column order/identity differs")
        seen_names.add(str(normalized["name"]))
        columns.append(normalized)
    if not columns:
        _fail("warehouse relation metadata has no columns")
    normalized_item = {
        "project_id": _string(item["project_id"], label="metadata project"),
        "dataset_id": _string(item["dataset_id"], label="metadata dataset"),
        "relation_id": _string(item["relation_id"], label="metadata relation"),
        "row_count": _exact_int(item["row_count"], label="metadata row count"),
        "size_bytes": _exact_int(item["size_bytes"], label="metadata byte count"),
        "modified_time_utc": _timestamp(
            item["modified_time_utc"], label="metadata modified time"
        ),
        "columns": columns,
        "columns_sha256": source.canonical_sha256(columns),
    }
    if (
        normalized_item["project_id"] != PRODUCTION_PROJECT
        or normalized_item["dataset_id"] != WAREHOUSE_DATASET
        or normalized_item["relation_id"] != expected_relation
    ):
        _fail("warehouse relation metadata authority differs")
    return normalized_item


_REQUIRED_RELATION_COLUMNS: Final = {
    "schedules": frozenset({
        "away_team", "game_id", "game_type", "gameday", "gametime",
        "home_team", "season", "week",
    }),
    "weekly_stats": frozenset({
        "air_yards_share", "carries", "fumbles_lost_total", "opponent_team",
        "passing_interceptions", "passing_tds", "passing_yards", "player_id",
        "position", "receiving_tds", "receiving_yards", "receptions",
        "rushing_tds", "rushing_yards", "season", "season_type",
        "target_share", "targets", "team", "week",
    }),
    "depth_charts": frozenset({
        "club_code", "depth_position", "depth_team", "formation", "gsis_id",
        "jersey_number", "position", "season", "week",
    }),
    "depth_charts_snapshots": frozenset({
        "dt", "gsis_id", "pos_abb", "pos_rank", "team",
    }),
    "pfr_advstats_def": frozenset({
        "def_completions_allowed", "def_pressures", "def_sacks", "def_targets",
        "def_times_blitzed", "def_times_hurried", "def_yards_allowed",
        "game_id", "pfr_player_id", "season", "team", "week",
    }),
    "snap_counts": frozenset({
        "defense_snaps", "game_id", "pfr_player_id", "position", "season",
        "team", "week",
    }),
}


def _validate_relation_metadata_receipt_v1(
    value: object, *, expected_relation: str,
) -> dict[str, object]:
    item = _mapping(value, label=f"{expected_relation} receipt metadata")
    _exact_keys(
        item,
        frozenset({
            "project_id", "dataset_id", "relation_id", "row_count",
            "size_bytes", "modified_time_utc", "columns", "columns_sha256",
        }),
        label=f"{expected_relation} receipt metadata",
    )
    base = dict(item)
    retained_columns_sha = _digest(
        base.pop("columns_sha256"),
        label=f"{expected_relation} receipt column manifest",
    )
    normalized = _normalize_relation_metadata(
        base, expected_relation=expected_relation
    )
    column_names = {str(value["name"]) for value in normalized["columns"]}
    if (
        retained_columns_sha != normalized["columns_sha256"]
        or not _REQUIRED_RELATION_COLUMNS[expected_relation] <= column_names
        or normalized != item
    ):
        _fail("warehouse relation receipt metadata differs")
    return normalized


def _normalize_job_metadata(
    value: object, *, spec: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="warehouse query job metadata")
    fields = frozenset({
        "project_id", "location", "job_id", "query_sha256", "state",
        "error_result", "cache_hit", "total_bytes_processed", "created_utc",
        "started_utc", "ended_utc",
    })
    _exact_keys(item, fields, label="warehouse query job metadata")
    created = _timestamp(item["created_utc"], label="warehouse job created")
    started = _timestamp(item["started_utc"], label="warehouse job started")
    ended = _timestamp(item["ended_utc"], label="warehouse job ended")
    if not created <= started <= ended:
        _fail("warehouse query chronology differs")
    normalized = {
        "project_id": _string(item["project_id"], label="warehouse job project"),
        "location": _string(item["location"], label="warehouse job location"),
        "job_id": _string(item["job_id"], label="warehouse job ID"),
        "query_sha256": _digest(
            item["query_sha256"], label="warehouse job query SHA"
        ),
        "state": _string(item["state"], label="warehouse job state"),
        "error_result": item["error_result"],
        "cache_hit": item["cache_hit"],
        "total_bytes_processed": _exact_int(
            item["total_bytes_processed"], label="warehouse bytes processed"
        ),
        "created_utc": created,
        "started_utc": started,
        "ended_utc": ended,
    }
    if (
        normalized["project_id"] != spec["project_id"]
        or normalized["location"] != spec["location"]
        or normalized["job_id"] != spec["job_id"]
        or normalized["query_sha256"] != spec["query_sha256"]
        or normalized["state"] != "DONE"
        or normalized["error_result"] is not None
        or normalized["cache_hit"] is not False
        or normalized["total_bytes_processed"] > spec["maximum_bytes_billed"]
    ):
        _fail("warehouse query job result differs from the fixed request")
    return normalized


def _capture_warehouse_result_v1(
    *, spec: Mapping[str, object], result_value: object,
) -> dict[str, object]:
    result = _mapping(result_value, label="warehouse query result")
    _exact_keys(
        result, frozenset({"job_metadata", "result_rows"}),
        label="warehouse query result",
    )
    job = _normalize_job_metadata(result["job_metadata"], spec=spec)
    records = _sequence(result["result_rows"], label="warehouse result rows")
    if not 1 <= len(records) <= MAX_QUERY_RESULT_RECORDS:
        _fail("warehouse query result row count differs")
    rows_by_slice: dict[str, list[dict[str, object]]] = {
        str(value): [] for value in spec["slice_kinds"]
    }
    metadata_by_relation: dict[str, dict[str, object]] = {}
    record_fields = frozenset({"record_kind", "slice_kind", "row_json"})
    for ordinal, raw in enumerate(records):
        record = _mapping(raw, label=f"warehouse result row[{ordinal}]")
        _exact_keys(record, record_fields, label=f"warehouse result row[{ordinal}]")
        kind = _string(record["record_kind"], label="warehouse record kind")
        discriminator = _string(
            record["slice_kind"], label="warehouse record discriminator"
        )
        parsed = _parse_result_row_json(
            record["row_json"], label=f"warehouse result row[{ordinal}].row_json"
        )
        if kind == "row":
            if discriminator not in rows_by_slice:
                _fail("warehouse query returned an unregistered slice")
            rows_by_slice[discriminator].append(_normalize_source_row(
                pack_id=str(spec["pack_id"]),
                slice_kind=discriminator,
                value=parsed,
            ))
        elif kind == "relation-metadata":
            if discriminator not in spec["input_relations"]:
                _fail("warehouse query returned unregistered relation metadata")
            if discriminator in metadata_by_relation:
                _fail("warehouse query repeated relation metadata")
            metadata_by_relation[discriminator] = _normalize_relation_metadata(
                parsed, expected_relation=discriminator
            )
        else:
            _fail("warehouse query returned an unknown record kind")
    if set(metadata_by_relation) != set(spec["input_relations"]):
        _fail("warehouse query did not return exact relation metadata")
    metadata = [
        metadata_by_relation[str(relation)] for relation in spec["input_relations"]
    ]
    for relation in metadata:
        column_names = {str(value["name"]) for value in relation["columns"]}
        if not _REQUIRED_RELATION_COLUMNS[str(relation["relation_id"])] <= column_names:
            _fail("warehouse relation lacks a required direct column")
    rows_object = _build_pack_rows(
        pack_id=str(spec["pack_id"]), rows_by_slice=rows_by_slice
    )
    accounting = _missing_accounting(rows_by_slice)
    slice_receipts = [
        {
            "slice_kind": value["slice_kind"],
            "row_count": value["row_count"],
            "rows_sha256": value["rows_sha256"],
        }
        for value in rows_object["slices"]
    ]
    return {
        "spec": dict(spec),
        "job_metadata": job,
        "input_relation_metadata": metadata,
        "input_relation_metadata_sha256": source.canonical_sha256(metadata),
        "rows_object": rows_object,
        "missing_id_accounting": accounting,
        "slice_receipts": slice_receipts,
    }


def build_warehouse_query_receipt_v1(
    *, capture: Mapping[str, object], rows_identity: Mapping[str, object],
    implementation_authority: Mapping[str, object],
) -> dict[str, object]:
    spec = _mapping(capture.get("spec"), label="captured query spec")
    rows = _mapping(capture.get("rows_object"), label="captured query rows")
    normalized_rows_identity = _identity(
        rows_identity, label="captured warehouse row object"
    )
    _bind_bytes(
        normalized_rows_identity,
        source.canonical_json_bytes(rows),
        label="captured warehouse row object",
    )
    authority = validate_implementation_authority_v1(implementation_authority)
    accounting = _mapping(
        capture.get("missing_id_accounting"),
        label="warehouse missing-ID accounting",
    )
    body: dict[str, object] = {
        "schema_version": WAREHOUSE_QUERY_RECEIPT_SCHEMA,
        "pack_id": spec["pack_id"],
        "query_spec": spec,
        "query_spec_sha256": spec["query_spec_sha256"],
        "job_metadata": capture["job_metadata"],
        "input_relation_metadata": capture["input_relation_metadata"],
        "input_relation_metadata_sha256": capture[
            "input_relation_metadata_sha256"
        ],
        "positive_row_schema_manifest_sha256": _registry_entry(
            str(spec["pack_id"])
        )["positive_row_schema_manifest_sha256"],
        "slice_receipts": capture["slice_receipts"],
        "slice_receipt_manifest_sha256": source.canonical_sha256(
            capture["slice_receipts"]
        ),
        "exact_rows_identity": normalized_rows_identity,
        "row_count": rows["row_count"],
        "rows_sha256": rows["rows_sha256"],
        "missing_id_accounting": accounting,
        "missing_id_accounting_sha256": source.canonical_sha256(accounting),
        "implementation_authority": authority,
        "implementation_authority_sha256": authority[
            "implementation_authority_sha256"
        ],
        "evidence_class": EVIDENCE_CLASS,
        "observed_at_basis": OBSERVED_AT_BASIS,
        "authoritative_pit": False,
        **_policy(),
    }
    return _with_hash(body, field_name="warehouse_query_receipt_sha256")


_WAREHOUSE_QUERY_RECEIPT_FIELDS: Final = frozenset({
    "schema_version",
    "pack_id",
    "query_spec",
    "query_spec_sha256",
    "job_metadata",
    "input_relation_metadata",
    "input_relation_metadata_sha256",
    "positive_row_schema_manifest_sha256",
    "slice_receipts",
    "slice_receipt_manifest_sha256",
    "exact_rows_identity",
    "row_count",
    "rows_sha256",
    "missing_id_accounting",
    "missing_id_accounting_sha256",
    "implementation_authority",
    "implementation_authority_sha256",
    "evidence_class",
    "observed_at_basis",
    *source.POLICY_FIELDS,
    "warehouse_query_receipt_sha256",
})


def validate_warehouse_query_receipt_v1(
    value: object, *, expected_run_id: object, expected_pack_id: str,
    expected_rows: Mapping[str, object],
    expected_rows_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="warehouse query receipt")
    _exact_keys(
        item,
        _WAREHOUSE_QUERY_RECEIPT_FIELDS,
        label="warehouse query receipt",
    )
    _validate_hash(
        item,
        field_name="warehouse_query_receipt_sha256",
        label="warehouse query receipt",
    )
    _validate_policy(item, label="warehouse query receipt")
    spec = validate_warehouse_query_spec_v1(
        item["query_spec"], expected_run_id=expected_run_id
    )
    if (
        spec["pack_id"] != expected_pack_id
        or item["query_spec_sha256"] != spec["query_spec_sha256"]
    ):
        _fail("warehouse query receipt query law differs")
    job = _normalize_job_metadata(item["job_metadata"], spec=spec)
    if job != item["job_metadata"]:
        _fail("warehouse query receipt job metadata differs")
    rows = source.validate_upstream_pack_rows_v1(
        expected_rows, expected_pack_id=expected_pack_id
    )
    identity = _identity(expected_rows_identity, label="expected warehouse rows")
    _bind_bytes(identity, source.canonical_json_bytes(rows), label="warehouse rows")
    if (
        item.get("schema_version") != WAREHOUSE_QUERY_RECEIPT_SCHEMA
        or item.get("pack_id") != expected_pack_id
        or item.get("exact_rows_identity") != identity
        or item.get("row_count") != rows["row_count"]
        or item.get("rows_sha256") != rows["rows_sha256"]
        or item.get("positive_row_schema_manifest_sha256")
        != _registry_entry(expected_pack_id)["positive_row_schema_manifest_sha256"]
        or item.get("evidence_class") != EVIDENCE_CLASS
        or item.get("observed_at_basis") != OBSERVED_AT_BASIS
        or item.get("authoritative_pit") is not False
    ):
        _fail("warehouse query receipt row/evidence binding differs")
    raw_metadata = _sequence(
        item.get("input_relation_metadata"), label="warehouse input metadata"
    )
    expected_relations = [str(value) for value in spec["input_relations"]]
    if len(raw_metadata) != len(expected_relations):
        _fail("warehouse input relation metadata count differs")
    metadata = [
        _validate_relation_metadata_receipt_v1(
            raw, expected_relation=expected_relation
        )
        for raw, expected_relation in zip(
            raw_metadata, expected_relations, strict=True
        )
    ]
    if (
        metadata != raw_metadata
        or item.get("input_relation_metadata_sha256")
        != source.canonical_sha256(metadata)
    ):
        _fail("warehouse input relation metadata hash differs")
    slices = _sequence(
        item.get("slice_receipts"), label="warehouse slice receipts"
    )
    expected_slices = [
        {
            "slice_kind": value["slice_kind"],
            "row_count": value["row_count"],
            "rows_sha256": value["rows_sha256"],
        }
        for value in rows["slices"]
    ]
    if (
        slices != expected_slices
        or item.get("slice_receipt_manifest_sha256")
        != source.canonical_sha256(expected_slices)
    ):
        _fail("warehouse slice receipt hash differs")
    accounting = _validate_missing_accounting_v1(
        item.get("missing_id_accounting"),
        expected_pack_id=expected_pack_id,
        expected_retained_count=int(rows["row_count"]),
    )
    if item.get("missing_id_accounting_sha256") != source.canonical_sha256(accounting):
        _fail("warehouse missing-ID accounting hash differs")
    authority = validate_implementation_authority_v1(
        item.get("implementation_authority")
    )
    if item.get("implementation_authority_sha256") != authority[
        "implementation_authority_sha256"
    ]:
        _fail("warehouse implementation authority differs")
    return item


def build_artifact_projection_manifest_v1(
    *, opened: Mapping[str, object], rows_identity: Mapping[str, object],
    implementation_authority: Mapping[str, object],
) -> dict[str, object]:
    manifest = validate_artifact_pack_manifest_structure_v1(opened.get("manifest"))
    manifest_identity = _identity(
        opened.get("manifest_identity"), label="artifact pack manifest identity"
    )
    _bind_bytes(
        manifest_identity,
        source.canonical_json_bytes(manifest),
        label="artifact pack manifest",
    )
    rows = source.validate_upstream_pack_rows_v1(
        opened.get("rows_object"), expected_pack_id=str(manifest["pack_id"])
    )
    normalized_rows_identity = _identity(
        rows_identity, label="artifact projection rows"
    )
    _bind_bytes(
        normalized_rows_identity,
        source.canonical_json_bytes(rows),
        label="artifact projection rows",
    )
    accounting = _mapping(
        opened.get("missing_id_accounting"),
        label="artifact projection missing accounting",
    )
    authority = validate_implementation_authority_v1(implementation_authority)
    body: dict[str, object] = {
        "schema_version": ARTIFACT_PROJECTION_MANIFEST_SCHEMA,
        "pack_id": manifest["pack_id"],
        "input_artifact_pack_manifest_identity": manifest_identity,
        "input_artifact_pack_manifest_sha256": manifest[
            "artifact_pack_manifest_sha256"
        ],
        "source_manifest_identities": manifest["source_manifest_identities"],
        "source_manifest_identity_manifest_sha256": manifest[
            "source_manifest_identity_manifest_sha256"
        ],
        "source_artifact_identity_manifest_sha256": manifest[
            "source_artifact_identity_manifest_sha256"
        ],
        "shard_manifest_sha256": manifest["shard_manifest_sha256"],
        "projection_code_identity": manifest["projection_code_identity"],
        "exact_rows_identity": normalized_rows_identity,
        "row_count": rows["row_count"],
        "rows_sha256": rows["rows_sha256"],
        "positive_row_schema_manifest_sha256": rows[
            "positive_row_schema_manifest_sha256"
        ],
        "missing_id_accounting": accounting,
        "missing_id_accounting_sha256": source.canonical_sha256(accounting),
        "implementation_authority": authority,
        "implementation_authority_sha256": authority[
            "implementation_authority_sha256"
        ],
        "evidence_class": EVIDENCE_CLASS,
        "observed_at_basis": OBSERVED_AT_BASIS,
        "authoritative_pit": False,
        **_policy(),
    }
    return _with_hash(body, field_name="artifact_projection_manifest_sha256")


_ARTIFACT_PROJECTION_MANIFEST_FIELDS: Final = frozenset({
    "schema_version",
    "pack_id",
    "input_artifact_pack_manifest_identity",
    "input_artifact_pack_manifest_sha256",
    "source_manifest_identities",
    "source_manifest_identity_manifest_sha256",
    "source_artifact_identity_manifest_sha256",
    "shard_manifest_sha256",
    "projection_code_identity",
    "exact_rows_identity",
    "row_count",
    "rows_sha256",
    "positive_row_schema_manifest_sha256",
    "missing_id_accounting",
    "missing_id_accounting_sha256",
    "implementation_authority",
    "implementation_authority_sha256",
    "evidence_class",
    "observed_at_basis",
    *source.POLICY_FIELDS,
    "artifact_projection_manifest_sha256",
})


def validate_artifact_projection_manifest_v1(
    value: object, *, expected_pack_id: str,
    expected_rows: Mapping[str, object],
    expected_rows_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="artifact projection manifest")
    _exact_keys(
        item,
        _ARTIFACT_PROJECTION_MANIFEST_FIELDS,
        label="artifact projection manifest",
    )
    _validate_hash(
        item,
        field_name="artifact_projection_manifest_sha256",
        label="artifact projection manifest",
    )
    _validate_policy(item, label="artifact projection manifest")
    rows = source.validate_upstream_pack_rows_v1(
        expected_rows, expected_pack_id=expected_pack_id
    )
    rows_identity = _identity(
        expected_rows_identity, label="artifact projection expected rows"
    )
    _bind_bytes(
        rows_identity,
        source.canonical_json_bytes(rows),
        label="artifact projection expected rows",
    )
    input_identity = _identity(
        item.get("input_artifact_pack_manifest_identity"),
        label="artifact projection input manifest",
    )
    source_manifests = _sorted_identities(
        item.get("source_manifest_identities"),
        label="artifact projection source manifests",
        minimum=1,
        maximum=MAX_SOURCE_MANIFESTS_PER_PACK,
    )
    accounting = _validate_missing_accounting_v1(
        item.get("missing_id_accounting"),
        expected_pack_id=expected_pack_id,
        expected_retained_count=int(rows["row_count"]),
    )
    code = _code_identity(
        item.get("projection_code_identity"), label="artifact projection code"
    )
    authority = validate_implementation_authority_v1(
        item.get("implementation_authority")
    )
    for field_name in (
        "input_artifact_pack_manifest_sha256",
        "source_manifest_identity_manifest_sha256",
        "source_artifact_identity_manifest_sha256",
        "shard_manifest_sha256",
    ):
        _digest(item.get(field_name), label=f"artifact projection {field_name}")
    if (
        item.get("schema_version") != ARTIFACT_PROJECTION_MANIFEST_SCHEMA
        or item.get("pack_id") != expected_pack_id
        or item.get("exact_rows_identity") != rows_identity
        or item.get("row_count") != rows["row_count"]
        or item.get("rows_sha256") != rows["rows_sha256"]
        or item.get("positive_row_schema_manifest_sha256")
        != rows["positive_row_schema_manifest_sha256"]
        or item.get("source_manifest_identity_manifest_sha256")
        != source.canonical_sha256(source_manifests)
        or item.get("missing_id_accounting_sha256")
        != source.canonical_sha256(accounting)
        or item.get("implementation_authority_sha256")
        != authority["implementation_authority_sha256"]
        or item.get("evidence_class") != EVIDENCE_CLASS
        or item.get("observed_at_basis") != OBSERVED_AT_BASIS
        or item.get("authoritative_pit") is not False
    ):
        _fail("artifact projection manifest binding differs")
    normalized = dict(item)
    normalized["input_artifact_pack_manifest_identity"] = input_identity
    normalized["source_manifest_identities"] = source_manifests
    normalized["projection_code_identity"] = code
    normalized["implementation_authority"] = authority
    if source.canonical_json_bytes(normalized) != source.canonical_json_bytes(item):
        _fail("artifact projection manifest canonical structure differs")
    return normalized


def _publish_and_reopen_json_v1(
    *, uri: str, value: Mapping[str, object],
    publish_create_once: PublishCreateOnceOrExactPrior,
    reader: BoundedExactReaderV1, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    raw = source.canonical_json_bytes(value)
    if not raw or len(raw) > MAX_EXACT_OBJECT_BYTES:
        _fail(f"{label} exceeds the canonical object bound")
    try:
        published = publish_create_once(uri, raw)
    except Exception as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = _bind_bytes(published, raw, label=label)
    reopened_raw = reader.read(identity, label=f"{label} published reopen")
    reopened = _canonical_object(reopened_raw, label=f"{label} published reopen")
    if reopened != dict(value):
        _fail(f"{label} published bytes differ")
    return identity, reopened


def _pack_entry_v1(
    *, registry_entry: Mapping[str, object], rows: Mapping[str, object],
    rows_identity: Mapping[str, object], provenance_identity: Mapping[str, object],
    artifact_manifest_identities: Sequence[Mapping[str, object]],
    projection_code_identity: Mapping[str, object],
) -> dict[str, object]:
    warehouse = registry_entry["provenance_kind"] == "warehouse-query-receipt"
    artifacts = [
        _identity(value, label="release artifact manifest")
        for value in artifact_manifest_identities
    ]
    artifact_uris = [str(value["uri"]) for value in artifacts]
    if artifact_uris != sorted(artifact_uris) or len(artifact_uris) != len(
        set(artifact_uris)
    ):
        _fail("release artifact manifest identities differ")
    return {
        "pack_id": registry_entry["pack_id"],
        "source_kind": registry_entry["source_kind"],
        "provenance_kind": registry_entry["provenance_kind"],
        "positive_row_schemas": registry_entry["positive_row_schemas"],
        "positive_row_schema_manifest_sha256": registry_entry[
            "positive_row_schema_manifest_sha256"
        ],
        "exact_rows_identity": _identity(rows_identity, label="release pack rows"),
        "row_count": rows["row_count"],
        "rows_sha256": rows["rows_sha256"],
        "source_period_min": registry_entry["source_period_min"],
        "source_period_max": registry_entry["source_period_max"],
        "warehouse_query_receipt_identity": (
            _identity(provenance_identity, label="warehouse query receipt")
            if warehouse else None
        ),
        "frozen_artifact_manifest_identities": [] if warehouse else artifacts,
        "projection_code_identity": _code_identity(
            projection_code_identity, label="release pack projection code"
        ),
    }


def _expected_rows_uri(namespace: str, pack_id: str) -> str:
    return f"{namespace}packs/{pack_id}/rows.json"


def _expected_provenance_uri(namespace: str, pack_id: str) -> str:
    suffix = (
        "warehouse-query-receipt.json"
        if pack_id in WAREHOUSE_PACK_IDS
        else "artifact-projection-manifest.json"
    )
    return f"{namespace}packs/{pack_id}/{suffix}"


def _core_code_identity(
    implementation_authority: Mapping[str, object],
) -> dict[str, str]:
    authority = validate_implementation_authority_v1(implementation_authority)
    matching = [
        dict(value) for value in authority["measurements"]
        if value["relative_path"] == CORE_MODULE_PATH
    ]
    if len(matching) != 1:
        _fail("core implementation measurement differs")
    measurement = matching[0]
    return {
        "source_commit_sha": authority["source_commit_sha"],
        "module_path": CORE_MODULE_PATH,
        "module_sha256": measurement["sha256"],
    }


def _artifact_manifest_inputs(
    value: object,
) -> dict[str, dict[str, object]]:
    item = _mapping(value, label="artifact manifest identities")
    if set(item) != set(ARTIFACT_PACK_IDS):
        _fail("artifact manifest identity registry must contain exact FP/SIS packs")
    return {
        pack_id: _identity(item[pack_id], label=f"{pack_id} input manifest")
        for pack_id in ARTIFACT_PACK_IDS
    }


def preflight_seven_pack_inputs_v1(
    *, fixed_source_root_identity: Mapping[str, object],
    artifact_manifest_identities: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Read-only predecessor replay; no query or publication callback exists."""
    reader = BoundedExactReaderV1(read_exact=read_exact)
    fixed_root = _identity(
        fixed_source_root_identity, label="seven-pack fixed source root"
    )
    reader.read(fixed_root, label="seven-pack fixed source root")
    manifests = _artifact_manifest_inputs(artifact_manifest_identities)
    opened = {
        pack_id: _open_artifact_pack_manifest_v1(
            manifest_identity=manifests[pack_id],
            reader=reader,
            expected_pack_id=pack_id,
        )
        for pack_id in ARTIFACT_PACK_IDS
    }
    body: dict[str, object] = {
        "schema_version": "corpus-r6-matchup-seven-pack-input-preflight/v1",
        "fixed_source_root_identity": fixed_root,
        "artifact_manifest_identities": manifests,
        "artifact_pack_count": len(opened),
        "artifact_pack_rows_sha256": {
            pack_id: opened[pack_id]["rows_object"]["rows_sha256"]
            for pack_id in ARTIFACT_PACK_IDS
        },
        "generation_exact_predecessor_replay_complete": True,
        "warehouse_query_count": 0,
        "publication_count": 0,
        "synthetic_fallback_used": False,
        "read_budget": reader.receipt(),
        **_policy(),
    }
    return _with_hash(body, field_name="input_preflight_sha256")


def publish_seven_pack_capture_v1(
    *, run_id: str, fixed_source_root_identity: Mapping[str, object],
    artifact_manifest_identities: Mapping[str, object],
    implementation_authority: Mapping[str, object],
    query_warehouse: QueryWarehouse, read_exact: ReadExact,
    publish_create_once: PublishCreateOnceOrExactPrior,
) -> dict[str, object]:
    """Capture five queries and two frozen-manifest packs; publish root last."""
    normalized_run_id = _run_id(run_id)
    namespace = output_namespace_for_run_v1(normalized_run_id)
    inventory = output_uri_inventory_v1(normalized_run_id)
    authority = validate_implementation_authority_v1(implementation_authority)
    core_code = _core_code_identity(authority)
    manifests = _artifact_manifest_inputs(artifact_manifest_identities)
    fixed_root = _identity(
        fixed_source_root_identity, label="seven-pack fixed source root"
    )
    reader = BoundedExactReaderV1(read_exact=read_exact)
    reader.read(fixed_root, label="seven-pack fixed source root")

    # Open both artifact chains and execute all five warehouse jobs before the
    # first write.  A bad query result or manifest can therefore never create a
    # partial capture prefix.
    artifact_opened = {
        pack_id: _open_artifact_pack_manifest_v1(
            manifest_identity=manifests[pack_id],
            reader=reader,
            expected_pack_id=pack_id,
        )
        for pack_id in ARTIFACT_PACK_IDS
    }
    query_specs = frozen_warehouse_query_specs_v1(normalized_run_id)
    warehouse_captures: dict[str, dict[str, object]] = {}
    for spec in query_specs:
        try:
            query_result = query_warehouse(spec)
        except Exception as exc:
            raise CorpusR6MatchupSevenPackCaptureV1Error(
                f"warehouse query for {spec['pack_id']} failed"
            ) from exc
        warehouse_captures[str(spec["pack_id"])] = _capture_warehouse_result_v1(
            spec=spec, result_value=query_result
        )

    registry = source.frozen_upstream_pack_registry_v1()
    pack_entries: list[dict[str, object]] = []
    pack_rows: list[dict[str, object]] = []
    output_bindings: list[dict[str, object]] = []
    write_order: list[str] = []
    for registry_value in registry["packs"]:
        registry_entry = dict(registry_value)
        pack_id = str(registry_entry["pack_id"])
        if pack_id in WAREHOUSE_PACK_IDS:
            capture = warehouse_captures[pack_id]
            rows = dict(capture["rows_object"])
        else:
            capture = artifact_opened[pack_id]
            rows = dict(capture["rows_object"])
        rows_uri = _expected_rows_uri(namespace, pack_id)
        if rows_uri not in inventory:
            _fail("pack rows URI escapes the precomputed inventory")
        rows_identity, reopened_rows = _publish_and_reopen_json_v1(
            uri=rows_uri,
            value=rows,
            publish_create_once=publish_create_once,
            reader=reader,
            label=f"{pack_id} rows",
        )
        rows = source.validate_upstream_pack_rows_v1(
            reopened_rows, expected_pack_id=pack_id
        )
        write_order.append(rows_uri)
        provenance_uri = _expected_provenance_uri(namespace, pack_id)
        if provenance_uri not in inventory:
            _fail("pack provenance URI escapes the precomputed inventory")
        if pack_id in WAREHOUSE_PACK_IDS:
            provenance = build_warehouse_query_receipt_v1(
                capture=capture,
                rows_identity=rows_identity,
                implementation_authority=authority,
            )
        else:
            provenance = build_artifact_projection_manifest_v1(
                opened=capture,
                rows_identity=rows_identity,
                implementation_authority=authority,
            )
        provenance_identity, reopened_provenance = _publish_and_reopen_json_v1(
            uri=provenance_uri,
            value=provenance,
            publish_create_once=publish_create_once,
            reader=reader,
            label=f"{pack_id} provenance",
        )
        write_order.append(provenance_uri)
        if pack_id in WAREHOUSE_PACK_IDS:
            validate_warehouse_query_receipt_v1(
                reopened_provenance,
                expected_run_id=normalized_run_id,
                expected_pack_id=pack_id,
                expected_rows=rows,
                expected_rows_identity=rows_identity,
            )
            release_artifacts: list[dict[str, object]] = []
            projection_code = core_code
        else:
            projection = validate_artifact_projection_manifest_v1(
                reopened_provenance,
                expected_pack_id=pack_id,
                expected_rows=rows,
                expected_rows_identity=rows_identity,
            )
            manifest = dict(capture["manifest"])
            release_artifacts = sorted(
                [
                    provenance_identity,
                    dict(capture["manifest_identity"]),
                    *[dict(value) for value in manifest["source_manifest_identities"]],
                ],
                key=lambda value: str(value["uri"]),
            )
            projection_code = dict(projection["projection_code_identity"])
        pack_entries.append(_pack_entry_v1(
            registry_entry=registry_entry,
            rows=rows,
            rows_identity=rows_identity,
            provenance_identity=provenance_identity,
            artifact_manifest_identities=release_artifacts,
            projection_code_identity=projection_code,
        ))
        pack_rows.append(rows)
        output_bindings.append({
            "pack_id": pack_id,
            "rows_identity": rows_identity,
            "provenance_identity": provenance_identity,
            "row_count": rows["row_count"],
            "rows_sha256": rows["rows_sha256"],
        })

    # Reopen every row/provenance output once more as one complete seven-pack
    # immediately before constructing the root.
    for ordinal, binding in enumerate(output_bindings):
        rows_raw = reader.read(
            binding["rows_identity"], label=f"pre-root rows[{ordinal}]"
        )
        rows = source.validate_upstream_pack_rows_v1(
            _canonical_object(rows_raw, label=f"pre-root rows[{ordinal}]"),
            expected_pack_id=str(binding["pack_id"]),
        )
        provenance_raw = reader.read(
            binding["provenance_identity"],
            label=f"pre-root provenance[{ordinal}]",
        )
        provenance = _canonical_object(
            provenance_raw, label=f"pre-root provenance[{ordinal}]"
        )
        if binding["pack_id"] in WAREHOUSE_PACK_IDS:
            validate_warehouse_query_receipt_v1(
                provenance,
                expected_run_id=normalized_run_id,
                expected_pack_id=str(binding["pack_id"]),
                expected_rows=rows,
                expected_rows_identity=binding["rows_identity"],
            )
        else:
            validate_artifact_projection_manifest_v1(
                provenance,
                expected_pack_id=str(binding["pack_id"]),
                expected_rows=rows,
                expected_rows_identity=binding["rows_identity"],
            )

    try:
        release = source.build_upstream_release_v1(
            release_id=f"{normalized_run_id}-seven-pack",
            namespace=namespace,
            fixed_source_root_identity=fixed_root,
            packs=pack_entries,
            pack_row_objects=pack_rows,
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(str(exc)) from exc
    root_uri = f"{namespace}{RELEASE_FILENAME}"
    if root_uri not in inventory or len(write_order) != OUTPUT_OBJECT_COUNT - 1:
        _fail("seven-pack preterminal write set differs")
    root_identity, reopened_release = _publish_and_reopen_json_v1(
        uri=root_uri,
        value=release,
        publish_create_once=publish_create_once,
        reader=reader,
        label="seven-pack terminal release",
    )
    write_order.append(root_uri)
    if write_order[-1] != root_uri or len(write_order) != OUTPUT_OBJECT_COUNT:
        _fail("seven-pack terminal release was not written last")
    source.validate_upstream_release_v1(
        reopened_release,
        pack_row_objects=pack_rows,
        expected_fixed_source_root_identity=fixed_root,
        expected_namespace=namespace,
    )
    same_process_reopen = reopen_seven_pack_capture_v1(
        release_identity=root_identity,
        read_exact=read_exact,
        expected_fixed_source_root_identity=fixed_root,
    )
    body: dict[str, object] = {
        "schema_version": PUBLICATION_RECEIPT_SCHEMA,
        "run_id": normalized_run_id,
        "namespace": namespace,
        "output_uri_inventory": list(inventory),
        "output_uri_inventory_sha256": source.canonical_sha256(list(inventory)),
        "fixed_source_root_identity": fixed_root,
        "artifact_manifest_identities": manifests,
        "implementation_authority": authority,
        "implementation_authority_sha256": authority[
            "implementation_authority_sha256"
        ],
        "warehouse_query_count": len(query_specs),
        "pack_count": len(pack_entries),
        "output_bindings": output_bindings,
        "output_binding_manifest_sha256": source.canonical_sha256(output_bindings),
        "write_order": write_order,
        "write_order_sha256": source.canonical_sha256(write_order),
        "write_count": len(write_order),
        "terminal_release_identity": root_identity,
        "terminal_release_sha256": release["upstream_release_sha256"],
        "terminal_release_root_last": True,
        "all_seven_rows_and_provenance_reopened_before_root": True,
        "same_process_full_reopen_complete": same_process_reopen["complete"],
        "independent_process_reopen_required": True,
        "exact_equal_resume_required": True,
        "retry_invariant_root_sha256": release["upstream_release_sha256"],
        "synthetic_fallback_used": False,
        "read_budget": reader.receipt(),
        **_policy(),
    }
    return _with_hash(body, field_name="publication_receipt_sha256")


def _run_id_from_namespace_v1(namespace: str) -> str:
    prefix = f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/"
    if not namespace.startswith(prefix) or not namespace.endswith("/"):
        _fail("seven-pack namespace differs from the fixed namespace")
    run_component = namespace[len(prefix):].removesuffix("/")
    normalized_run_id = _run_id(run_component)
    if output_namespace_for_run_v1(normalized_run_id) != namespace:
        _fail("seven-pack release run namespace differs")
    return normalized_run_id


def _release_namespace(identity: Mapping[str, object]) -> str:
    uri = str(identity["uri"])
    suffix = RELEASE_FILENAME
    prefix = f"gs://{OUTPUT_BUCKET}/{OUTPUT_NAMESPACE}/"
    if not uri.startswith(prefix) or not uri.endswith(suffix):
        _fail("seven-pack release URI differs from the fixed namespace")
    namespace = uri[:-len(suffix)]
    _run_id_from_namespace_v1(namespace)
    return namespace


def reopen_seven_pack_capture_v1(
    *, release_identity: Mapping[str, object], read_exact: ReadExact,
    expected_fixed_source_root_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Write-disabled, bounded, generation-exact replay of the complete root."""
    root_identity = _identity(release_identity, label="seven-pack release")
    namespace = _release_namespace(root_identity)
    expected_run_id = _run_id_from_namespace_v1(namespace)
    reader = BoundedExactReaderV1(read_exact=read_exact)
    root_raw = reader.read(root_identity, label="seven-pack release")
    root = _canonical_object(root_raw, label="seven-pack release")
    if (
        root.get("schema_version") != source.UPSTREAM_RELEASE_SCHEMA
        or root.get("namespace") != namespace
        or root.get("pack_count") != len(source.PACK_IDS)
        or len(_sequence(root.get("packs"), label="seven-pack release packs"))
        != len(source.PACK_IDS)
    ):
        _fail("seven-pack release structure differs")
    retained_root_sha = _digest(
        root.get("upstream_release_sha256"), label="seven-pack release SHA"
    )
    unhashed = dict(root)
    del unhashed["upstream_release_sha256"]
    if source.canonical_sha256(unhashed) != retained_root_sha:
        _fail("seven-pack release self-hash differs")
    fixed_root = _identity(
        root.get("fixed_source_root_identity"), label="seven-pack fixed source root"
    )
    if expected_fixed_source_root_identity is not None and fixed_root != _identity(
        expected_fixed_source_root_identity,
        label="expected seven-pack fixed source root",
    ):
        _fail("seven-pack release fixed source root differs")
    reader.read(fixed_root, label="seven-pack fixed source root")

    pack_rows: list[dict[str, object]] = []
    provenance_objects: list[dict[str, object]] = []
    implementation_sha: str | None = None
    raw_packs = _sequence(root["packs"], label="seven-pack packs")
    for ordinal, (expected_pack_id, raw_pack) in enumerate(
        zip(source.PACK_IDS, raw_packs, strict=True)
    ):
        pack = _mapping(raw_pack, label=f"seven-pack pack[{ordinal}]")
        if pack.get("pack_id") != expected_pack_id:
            _fail("seven-pack release pack order differs")
        rows_identity = _identity(
            pack.get("exact_rows_identity"), label=f"{expected_pack_id} rows"
        )
        if rows_identity["uri"] != _expected_rows_uri(namespace, expected_pack_id):
            _fail("seven-pack release row URI differs")
        rows_raw = reader.read(rows_identity, label=f"{expected_pack_id} rows")
        rows = source.validate_upstream_pack_rows_v1(
            _canonical_object(rows_raw, label=f"{expected_pack_id} rows"),
            expected_pack_id=expected_pack_id,
        )
        if (
            rows["row_count"] != pack.get("row_count")
            or rows["rows_sha256"] != pack.get("rows_sha256")
        ):
            _fail("seven-pack release rows differ from pack binding")
        if expected_pack_id in WAREHOUSE_PACK_IDS:
            provenance_identity = _identity(
                pack.get("warehouse_query_receipt_identity"),
                label=f"{expected_pack_id} query receipt",
            )
            if (
                provenance_identity["uri"]
                != _expected_provenance_uri(namespace, expected_pack_id)
                or pack.get("frozen_artifact_manifest_identities") != []
            ):
                _fail("warehouse pack provenance identity differs")
            provenance_raw = reader.read(
                provenance_identity, label=f"{expected_pack_id} query receipt"
            )
            provenance = validate_warehouse_query_receipt_v1(
                _canonical_object(
                    provenance_raw, label=f"{expected_pack_id} query receipt"
                ),
                expected_run_id=expected_run_id,
                expected_pack_id=expected_pack_id,
                expected_rows=rows,
                expected_rows_identity=rows_identity,
            )
            expected_code = _core_code_identity(
                provenance["implementation_authority"]
            )
        else:
            if pack.get("warehouse_query_receipt_identity") is not None:
                _fail("artifact pack carries warehouse provenance")
            manifest_identities = _sorted_identities(
                pack.get("frozen_artifact_manifest_identities"),
                label=f"{expected_pack_id} release manifest identities",
                minimum=3,
                maximum=MAX_SOURCE_MANIFESTS_PER_PACK + 2,
            )
            expected_provenance_uri = _expected_provenance_uri(
                namespace, expected_pack_id
            )
            matching = [
                value for value in manifest_identities
                if value["uri"] == expected_provenance_uri
            ]
            if len(matching) != 1:
                _fail("artifact projection provenance identity differs")
            provenance_identity = matching[0]
            provenance_raw = reader.read(
                provenance_identity,
                label=f"{expected_pack_id} artifact projection manifest",
            )
            provenance = validate_artifact_projection_manifest_v1(
                _canonical_object(
                    provenance_raw,
                    label=f"{expected_pack_id} artifact projection manifest",
                ),
                expected_pack_id=expected_pack_id,
                expected_rows=rows,
                expected_rows_identity=rows_identity,
            )
            opened = _open_artifact_pack_manifest_v1(
                manifest_identity=provenance[
                    "input_artifact_pack_manifest_identity"
                ],
                reader=reader,
                expected_pack_id=expected_pack_id,
            )
            opened_manifest = dict(opened["manifest"])
            if (
                opened["rows_object"] != rows
                or provenance["input_artifact_pack_manifest_sha256"]
                != opened_manifest["artifact_pack_manifest_sha256"]
                or provenance["source_manifest_identities"]
                != opened_manifest["source_manifest_identities"]
                or provenance["source_manifest_identity_manifest_sha256"]
                != opened_manifest["source_manifest_identity_manifest_sha256"]
                or provenance["source_artifact_identity_manifest_sha256"]
                != opened_manifest["source_artifact_identity_manifest_sha256"]
                or provenance["shard_manifest_sha256"]
                != opened_manifest["shard_manifest_sha256"]
                or provenance["projection_code_identity"]
                != opened_manifest["projection_code_identity"]
                or provenance["missing_id_accounting"]
                != opened_manifest["missing_id_accounting"]
                or rows["row_count"] != opened_manifest["projected_row_count"]
                or rows["rows_sha256"]
                != opened_manifest["projected_rows_sha256"]
            ):
                _fail("artifact projection closure differs from frozen manifest replay")
            expected_manifest_set = sorted(
                [
                    provenance_identity,
                    dict(opened["manifest_identity"]),
                    *[
                        dict(value)
                        for value in opened["manifest"]["source_manifest_identities"]
                    ],
                ],
                key=lambda value: str(value["uri"]),
            )
            if manifest_identities != expected_manifest_set:
                _fail("release artifact manifest closure differs")
            expected_code = dict(provenance["projection_code_identity"])
        if pack.get("projection_code_identity") != expected_code:
            _fail("seven-pack projection code binding differs")
        current_implementation_sha = str(
            provenance["implementation_authority_sha256"]
        )
        if implementation_sha is None:
            implementation_sha = current_implementation_sha
        elif current_implementation_sha != implementation_sha:
            _fail("seven-pack provenance uses mixed implementation authorities")
        pack_rows.append(rows)
        provenance_objects.append(provenance)
    try:
        release = source.validate_upstream_release_v1(
            root,
            pack_row_objects=pack_rows,
            expected_fixed_source_root_identity=fixed_root,
            expected_namespace=namespace,
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6MatchupSevenPackCaptureV1Error(str(exc)) from exc
    body: dict[str, object] = {
        "schema_version": REOPEN_RECEIPT_SCHEMA,
        "complete": True,
        "release_identity": root_identity,
        "upstream_release_sha256": release["upstream_release_sha256"],
        "fixed_source_root_identity": fixed_root,
        "pack_count": len(pack_rows),
        "pack_rows_sha256": [value["rows_sha256"] for value in pack_rows],
        "provenance_object_count": len(provenance_objects),
        "implementation_authority_sha256": implementation_sha,
        "all_seven_rows_exact_reopened": True,
        "all_seven_provenance_objects_exact_reopened": True,
        "all_artifact_manifest_shards_and_predecessors_exact_reopened": True,
        "write_capability_present": False,
        "warehouse_query_capability_present": False,
        "synthetic_fallback_used": False,
        "read_budget": reader.receipt(),
        **_policy(),
    }
    return _with_hash(body, field_name="reopen_receipt_sha256")


__all__ = [
    "ARTIFACT_PACK_IDS",
    "ARTIFACT_PACK_MANIFEST_SCHEMA",
    "ARTIFACT_PROJECTION_MANIFEST_SCHEMA",
    "ARTIFACT_ROW_SHARD_SCHEMA",
    "BoundedExactReaderV1",
    "CAPTURE_PLAN_BRIDGE_MODULE_PATH",
    "CLI_MODULE_PATH",
    "CORE_MODULE_PATH",
    "CorpusR6MatchupSevenPackCaptureV1Error",
    "IMPLEMENTATION_PATHS",
    "MISSING_ID_RETENTION_RULE",
    "NORMALIZED_SNAPSHOT_MODULE_PATH",
    "OPERATOR_MODULE_PATH",
    "OUTPUT_OBJECT_COUNT",
    "PLAYER_CATALOG_MODULE_PATH",
    "PRODUCTION_PROJECT",
    "SOURCE_CONTRACT_MODULE_PATH",
    "WAREHOUSE_LOCATION",
    "WAREHOUSE_PACK_IDS",
    "build_artifact_pack_manifest_v1",
    "build_artifact_projection_manifest_v1",
    "build_artifact_row_shard_v1",
    "build_implementation_authority_v1",
    "build_warehouse_query_receipt_v1",
    "frozen_warehouse_query_specs_v1",
    "output_namespace_for_run_v1",
    "output_uri_inventory_v1",
    "preflight_seven_pack_inputs_v1",
    "publish_seven_pack_capture_v1",
    "reopen_seven_pack_capture_v1",
    "validate_artifact_pack_manifest_structure_v1",
    "validate_artifact_projection_manifest_v1",
    "validate_artifact_row_shard_v1",
    "validate_implementation_authority_v1",
    "validate_warehouse_query_receipt_v1",
    "validate_warehouse_query_spec_v1",
]
