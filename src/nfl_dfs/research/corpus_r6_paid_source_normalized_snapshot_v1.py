"""Immutable ``nfl_raw`` snapshot producer for the FP/SIS seven-pack packs.

The paid-source tables are write-once normalized derivatives, but BigQuery
table names are not immutable content identities.  This module closes that
gap without changing the four-cell estimand: two fixed, time-travel queries
project exactly the registered Fantasy Points and SIS rows, bind provider job
and predecessor-relation metadata, and create generation-pinned artifacts
accepted by the existing seven-pack frozen-artifact contract.

The resulting evidence remains a retrospective prior-period reconstruction;
it is explicitly not an authoritative point-in-time acquisition.  Query and
storage callbacks are injected.  There is no listing, overwrite, outcome,
world, scoring, graph, deployment, IAM, or policy-promotion surface.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import re
from typing import Final

from nfl_dfs.research import corpus_r6_matchup_seven_pack_capture_v1 as capture
from nfl_dfs.research import corpus_r6_matchup_source_v2 as source


REQUEST_SCHEMA: Final = "corpus-r6-paid-source-normalized-snapshot-request/v1"
TASK0_SCHEMA: Final = "corpus-r6-paid-source-normalized-snapshot-task0/v1"
QUERY_SPEC_SCHEMA: Final = "corpus-r6-paid-source-normalized-query-spec/v1"
EXTRACT_SCHEMA: Final = "corpus-r6-paid-source-normalized-query-extract/v1"
QUERY_RECEIPT_SCHEMA: Final = "corpus-r6-paid-source-normalized-query-receipt/v1"
TERMINAL_SCHEMA: Final = "corpus-r6-paid-source-normalized-snapshot-terminal/v1"
REOPEN_SCHEMA: Final = "corpus-r6-paid-source-normalized-snapshot-reopen/v1"
PUBLICATION_RESULT_SCHEMA: Final = (
    "corpus-r6-paid-source-normalized-snapshot-publication-result/v1"
)

OUTPUT_PREFIX: Final = (
    "gs://nfl-predictions-503414-corpus-source/"
    "research/corpus-r6-paid-source-normalized-snapshots-v1"
)
PROJECT: Final = capture.PRODUCTION_PROJECT
DATASET: Final = capture.WAREHOUSE_DATASET
LOCATION: Final = capture.WAREHOUSE_LOCATION
MAX_BYTES_BILLED: Final = 5 * 1024 * 1024 * 1024
MAX_RESULT_ROWS: Final = 2_000_000
MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_paid_source_normalized_snapshot_v1.py"
)

_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{7,63}\Z")
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_UTC = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z\Z")

QueryWarehouse = Callable[[Mapping[str, object]], Mapping[str, object]]
ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]


class CorpusR6PaidSourceNormalizedSnapshotV1Error(RuntimeError):
    """The immutable normalized-source snapshot failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6PaidSourceNormalizedSnapshotV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one ordered array")
    return list(value)


def _timestamp(value: object, *, label: str) -> str:
    if type(value) is not str or _UTC.fullmatch(value) is None:
        _fail(f"{label} must be canonical UTC seconds")
    try:
        datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise CorpusR6PaidSourceNormalizedSnapshotV1Error(
            f"{label} must be canonical UTC seconds"
        ) from exc
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    create_once = item.pop("create_once", None)
    try:
        retained = source.normalize_object_identity_v2(item, label=label)
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6PaidSourceNormalizedSnapshotV1Error(str(exc)) from exc
    if create_once not in {None, True}:
        _fail(f"{label} create-once marker differs")
    return retained


def _code_identity(value: object) -> dict[str, str]:
    try:
        return source.normalize_code_identity_v2(
            value,
            expected_module_path=MODULE_PATH,
            label="normalized snapshot projection code",
        )
    except source.CorpusR6MatchupSourceV2Error as exc:
        raise CorpusR6PaidSourceNormalizedSnapshotV1Error(str(exc)) from exc


def _policy() -> dict[str, object]:
    return {
        "automatic_policy_promotion": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in source.FALSE_AUTHORITY_FIELDS},
    }


def _validate_policy(value: Mapping[str, object], *, label: str) -> None:
    if (
        value.get("outcome_columns_read") != []
        or value.get("uses_realized_outcomes") is not False
        or value.get("automatic_policy_promotion") is not False
        or any(value.get(field) is not False for field in source.FALSE_AUTHORITY_FIELDS)
    ):
        _fail(f"{label} claims outcome or downstream authority")


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    if field in value:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(value)
    result[field] = source.canonical_sha256(result)
    return result


def _validate_hash(value: Mapping[str, object], *, field: str, label: str) -> None:
    retained = value.get(field)
    if type(retained) is not str or _SHA.fullmatch(retained) is None:
        _fail(f"{label} self-hash differs")
    body = dict(value)
    del body[field]
    if source.canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")


_PACK_RELATIONS: Final = {
    source.FANTASY_POINTS_PACK: (
        "fantasy_points_route_share",
        "fantasy_points_alignment_player_l4",
        "fantasy_points_receiver_coverage_prior",
        "fantasy_points_defense_coverage_prior",
    ),
    source.SIS_PACK: (
        "sis_receiver_copula_player_game",
        "sis_team_run_context_game",
    ),
}

_REQUIRED_COLUMNS: Final = {
    "fantasy_points_route_share": frozenset({
        "gsis_id", "route_share", "season", "source_sha256", "week",
    }),
    "fantasy_points_alignment_player_l4": frozenset({
        "alignment_supported", "gsis_id", "player_wide_share", "season",
        "source_run_id", "source_file", "source_sha256", "split_duplicate",
        "target_week",
    }),
    "fantasy_points_receiver_coverage_prior": frozenset({
        "gsis_id", "man_fprr", "man_zone_source_sha256", "season",
        "separation_source_sha256", "split_duplicate", "zone_fprr",
    }),
    "fantasy_points_defense_coverage_prior": frozenset({
        "def_man_rate", "season", "source_file", "source_sha256", "team",
    }),
    "sis_receiver_copula_player_game": frozenset({
        "alignment", "completions", "coverage_snaps", "defense",
        "defender_name", "defender_player_id", "season", "source_run_id",
        "source_sha256", "targets", "touchdowns", "week", "yards",
    }),
    "sis_team_run_context_game": frozenset({
        "rdef_attempts", "rdef_boom_rate", "rdef_bust_rate",
        "rdef_epa_per_attempt", "rdef_stuffs", "rdef_yards_after_contact",
        "season", "source_run_id", "team", "week",
    }),
}

_PACK_SLICES: Final = {
    source.FANTASY_POINTS_PACK: (
        "fp-route-share", "fp-alignment", "fp-receiver-shell",
        "fp-defense-shell",
    ),
    source.SIS_PACK: ("sis-defender-alignment", "sis-run-context"),
}


def _relation_metadata_sql(relations: Sequence[str]) -> str:
    names = ",".join(f"'{name}'" for name in relations)
    return f"""
SELECT
  'relation-metadata' AS record_kind,
  table_id AS slice_kind,
  TO_JSON_STRING(STRUCT(
    '{PROJECT}' AS project_id,
    '{DATASET}' AS dataset_id,
    table_id AS relation_id,
    CAST(row_count AS INT64) AS row_count,
    CAST(size_bytes AS INT64) AS size_bytes,
    FORMAT_TIMESTAMP('%Y-%m-%dT%H:%M:%SZ',
      TIMESTAMP_MILLIS(last_modified_time), 'UTC') AS modified_time_utc,
    ARRAY(
      SELECT AS STRUCT column_name AS name, data_type, is_nullable,
        CAST(ordinal_position AS INT64) AS ordinal_position
      FROM `{PROJECT}.{DATASET}.INFORMATION_SCHEMA.COLUMNS`
      WHERE table_name = frozen_tables.table_id
      ORDER BY ordinal_position
    ) AS columns
  )) AS row_json
FROM `{PROJECT}.{DATASET}.__TABLES__` AS frozen_tables
WHERE frozen_tables.table_id IN ({names})
""".strip()


def _fp_rows(snapshot_at: str) -> str:
    at = f"TIMESTAMP('{snapshot_at}')"
    return f"""
SELECT 'row' AS record_kind, 'fp-route-share' AS slice_kind,
  TO_JSON_STRING(STRUCT(
    CAST(gsis_id AS STRING) AS gsis_id,
    CAST(route_share AS FLOAT64) AS route_share,
    CAST(season AS INT64) AS season,
    CAST(source_sha256 AS STRING) AS source_sha256,
    CAST(week AS INT64) AS week)) AS row_json
FROM `{PROJECT}.{DATASET}.fantasy_points_route_share`
FOR SYSTEM_TIME AS OF {at}
WHERE season BETWEEN 2022 AND 2025 AND week BETWEEN 1 AND 18
UNION ALL
SELECT 'row', 'fp-alignment', TO_JSON_STRING(STRUCT(
    CAST(alignment_supported AS BOOL) AS alignment_supported,
    CAST(gsis_id AS STRING) AS gsis_id,
    CAST(player_wide_share AS FLOAT64) AS player_wide_share,
    CAST(season AS INT64) AS season,
    CAST(source_sha256 AS STRING) AS source_sha256,
    CAST(split_duplicate AS BOOL) AS split_duplicate,
    CAST(target_week AS INT64) AS target_week))
FROM `{PROJECT}.{DATASET}.fantasy_points_alignment_player_l4`
FOR SYSTEM_TIME AS OF {at}
WHERE season BETWEEN 2022 AND 2025 AND target_week BETWEEN 1 AND 18
UNION ALL
SELECT 'row', 'fp-receiver-shell', TO_JSON_STRING(STRUCT(
    CAST(gsis_id AS STRING) AS gsis_id,
    CAST(man_fprr AS FLOAT64) AS man_fprr,
    CAST(season AS INT64) AS season,
    TO_HEX(SHA256(TO_JSON_STRING(STRUCT(
      CAST(man_zone_source_sha256 AS STRING) AS man_zone_source_sha256,
      CAST(separation_source_sha256 AS STRING) AS separation_source_sha256))))
      AS source_sha256,
    CAST(split_duplicate AS BOOL) AS split_duplicate,
    CAST(zone_fprr AS FLOAT64) AS zone_fprr))
FROM `{PROJECT}.{DATASET}.fantasy_points_receiver_coverage_prior`
FOR SYSTEM_TIME AS OF {at}
WHERE season BETWEEN 2022 AND 2025
UNION ALL
SELECT 'row', 'fp-defense-shell', TO_JSON_STRING(STRUCT(
    CAST(def_man_rate AS FLOAT64) AS def_man_rate,
    CAST(season AS INT64) AS season,
    CAST(source_sha256 AS STRING) AS source_sha256,
    CAST(team AS STRING) AS team))
FROM `{PROJECT}.{DATASET}.fantasy_points_defense_coverage_prior`
FOR SYSTEM_TIME AS OF {at}
WHERE season BETWEEN 2022 AND 2025
""".strip()


def _sis_rows(snapshot_at: str) -> str:
    at = f"TIMESTAMP('{snapshot_at}')"
    return f"""
SELECT 'row' AS record_kind, 'sis-defender-alignment' AS slice_kind,
  TO_JSON_STRING(STRUCT(
    CAST(alignment AS STRING) AS alignment,
    CAST(completions AS FLOAT64) AS completions,
    CAST(coverage_snaps AS FLOAT64) AS coverage_snaps,
    CAST(defense AS STRING) AS defense,
    CAST(defender_name AS STRING) AS defender_name,
    CAST(defender_player_id AS STRING) AS defender_player_id,
    CAST(season AS INT64) AS season,
    CAST(targets AS FLOAT64) AS targets,
    CAST(touchdowns AS FLOAT64) AS touchdowns,
    CAST(week AS INT64) AS week,
    CAST(yards AS FLOAT64) AS yards)) AS row_json
FROM `{PROJECT}.{DATASET}.sis_receiver_copula_player_game`
FOR SYSTEM_TIME AS OF {at}
WHERE season BETWEEN 2022 AND 2025 AND week BETWEEN 1 AND 18
UNION ALL
SELECT 'row', 'sis-run-context', TO_JSON_STRING(STRUCT(
    CAST(rdef_attempts AS FLOAT64) AS rdef_attempts,
    CAST(rdef_boom_rate AS FLOAT64) AS rdef_boom_rate,
    CAST(rdef_bust_rate AS FLOAT64) AS rdef_bust_rate,
    CAST(rdef_epa_per_attempt AS FLOAT64) AS rdef_epa_per_attempt,
    CAST(rdef_stuffs AS FLOAT64) AS rdef_stuffs,
    CAST(rdef_yards_after_contact AS FLOAT64) AS rdef_yards_after_contact,
    CAST(season AS INT64) AS season,
    CAST(team AS STRING) AS team,
    CAST(week AS INT64) AS week))
FROM `{PROJECT}.{DATASET}.sis_team_run_context_game`
FOR SYSTEM_TIME AS OF {at}
WHERE season BETWEEN 2022 AND 2025 AND week BETWEEN 1 AND 18
""".strip()


def frozen_query_specs_v1(*, run_id: str, snapshot_at_utc: str) -> list[dict[str, object]]:
    if type(run_id) is not str or _RUN_ID.fullmatch(run_id) is None:
        _fail("normalized snapshot run ID differs")
    snapshot = _timestamp(snapshot_at_utc, label="normalized snapshot time")
    specs: list[dict[str, object]] = []
    for ordinal, pack_id in enumerate((source.FANTASY_POINTS_PACK, source.SIS_PACK)):
        relations = _PACK_RELATIONS[pack_id]
        rows = _fp_rows(snapshot) if ordinal == 0 else _sis_rows(snapshot)
        query = f"""
WITH projected AS (
{rows}
), relation_metadata AS (
{_relation_metadata_sql(relations)}
)
SELECT record_kind, slice_kind, row_json FROM projected
UNION ALL
SELECT record_kind, slice_kind, row_json FROM relation_metadata
ORDER BY record_kind, slice_kind, row_json
""".strip()
        query_sha = sha256(query.encode("utf-8")).hexdigest()
        body: dict[str, object] = {
            "schema_version": QUERY_SPEC_SCHEMA,
            "ordinal": ordinal,
            "pack_id": pack_id,
            "project_id": PROJECT,
            "dataset_id": DATASET,
            "location": LOCATION,
            "snapshot_at_utc": snapshot,
            "use_legacy_sql": False,
            "use_query_cache": False,
            "maximum_bytes_billed": MAX_BYTES_BILLED,
            "input_relations": list(relations),
            "slice_kinds": list(_PACK_SLICES[pack_id]),
            "canonical_query": query,
            "query_sha256": query_sha,
            "job_id": (
                "r6_paid_snapshot_"
                f"{run_id.replace('-', '_')}_{ordinal}_{query_sha[:12]}"
            ),
            "evidence_class": source.EVIDENCE_CLASS,
            "authoritative_pit": False,
        }
        specs.append(_with_hash(body, field="query_spec_sha256"))
    return specs


def _uris(run_id: str) -> dict[str, object]:
    prefix = f"{OUTPUT_PREFIX}/{run_id}"
    packs: dict[str, dict[str, object]] = {}
    all_nonterminal: list[str] = []
    for pack_id in (source.FANTASY_POINTS_PACK, source.SIS_PACK):
        pack_prefix = f"{prefix}/packs/{pack_id}"
        row = {
            "extract_uri": f"{pack_prefix}/source-query-extract.json",
            "query_receipt_uri": f"{pack_prefix}/source-query-receipt.json",
            "shard_uris": {
                slice_kind: f"{pack_prefix}/shards/{slice_kind}.json"
                for slice_kind in _PACK_SLICES[pack_id]
            },
            "manifest_uri": f"{pack_prefix}/artifact-pack-manifest.json",
        }
        packs[pack_id] = row
        all_nonterminal.extend([
            str(row["extract_uri"]), str(row["query_receipt_uri"]),
            *[str(value) for value in row["shard_uris"].values()],
            str(row["manifest_uri"]),
        ])
    if len(all_nonterminal) != 12 or len(all_nonterminal) != len(set(all_nonterminal)):
        _fail("normalized snapshot output inventory differs")
    return {
        "prefix": prefix,
        "packs": packs,
        "nonterminal_uris": sorted(all_nonterminal),
        "terminal_uri": f"{prefix}/snapshot-terminal.json",
    }


def build_snapshot_request_v1(
    *, run_id: str, snapshot_at_utc: str,
    projection_code_identity: Mapping[str, object],
) -> dict[str, object]:
    specs = frozen_query_specs_v1(
        run_id=run_id, snapshot_at_utc=snapshot_at_utc
    )
    code = _code_identity(projection_code_identity)
    inventory = _uris(run_id)
    body: dict[str, object] = {
        "schema_version": REQUEST_SCHEMA,
        "run_id": run_id,
        "snapshot_at_utc": snapshot_at_utc,
        "query_specs": specs,
        "query_spec_manifest_sha256": source.canonical_sha256(specs),
        "projection_code_identity": code,
        "output_inventory": inventory,
        "output_inventory_sha256": source.canonical_sha256(inventory),
        "query_count": 2,
        "output_object_count": 13,
        "external_actions_default_off": True,
        "listing_allowed": False,
        "overwrite_allowed": False,
        "synthetic_fallback_allowed": False,
        "evidence_class": source.EVIDENCE_CLASS,
        "observed_at_basis": source.OBSERVED_AT_BASIS,
        "authoritative_pit": False,
        **_policy(),
    }
    return _with_hash(body, field="snapshot_request_sha256")


def validate_snapshot_request_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="normalized snapshot request")
    _validate_hash(item, field="snapshot_request_sha256", label="snapshot request")
    _validate_policy(item, label="snapshot request")
    expected = build_snapshot_request_v1(
        run_id=item.get("run_id"),
        snapshot_at_utc=item.get("snapshot_at_utc"),
        projection_code_identity=item.get("projection_code_identity"),
    )
    if item != expected:
        _fail("normalized snapshot request canonical replay differs")
    return expected


def _parse_json_text(value: object, *, label: str) -> dict[str, object]:
    if type(value) is not str:
        _fail(f"{label} must be JSON text")
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise CorpusR6PaidSourceNormalizedSnapshotV1Error(
            f"{label} JSON differs"
        ) from exc
    return _mapping(parsed, label=label)


def _relation_metadata(
    value: object, *, expected_relation: str,
) -> dict[str, object]:
    item = _mapping(value, label=f"{expected_relation} metadata")
    if set(item) != {
        "project_id", "dataset_id", "relation_id", "row_count", "size_bytes",
        "modified_time_utc", "columns",
    }:
        _fail(f"{expected_relation} metadata fields differ")
    columns: list[dict[str, object]] = []
    for ordinal, raw in enumerate(_sequence(item["columns"], label="columns"), 1):
        column = _mapping(raw, label=f"{expected_relation} column[{ordinal}]")
        if set(column) != {"name", "data_type", "is_nullable", "ordinal_position"}:
            _fail(f"{expected_relation} column fields differ")
        if (
            type(column["name"]) is not str
            or type(column["data_type"]) is not str
            or column["is_nullable"] not in {"YES", "NO"}
            or column["ordinal_position"] != ordinal
        ):
            _fail(f"{expected_relation} column metadata differs")
        columns.append(column)
    if (
        item["project_id"] != PROJECT
        or item["dataset_id"] != DATASET
        or item["relation_id"] != expected_relation
        or type(item["row_count"]) is not int
        or item["row_count"] < 1
        or type(item["size_bytes"]) is not int
        or item["size_bytes"] < 1
        or not _REQUIRED_COLUMNS[expected_relation] <= {
            str(column["name"]) for column in columns
        }
    ):
        _fail(f"{expected_relation} predecessor metadata differs")
    _timestamp(item["modified_time_utc"], label=f"{expected_relation} modified time")
    return {**item, "columns": columns}


def _job_metadata(value: object, *, spec: Mapping[str, object]) -> dict[str, object]:
    item = _mapping(value, label="normalized snapshot BigQuery job")
    if set(item) != {
        "project_id", "location", "job_id", "query_sha256", "state",
        "error_result", "cache_hit", "total_bytes_processed", "created_utc",
        "started_utc", "ended_utc",
    }:
        _fail("normalized snapshot BigQuery job fields differ")
    created = _timestamp(item["created_utc"], label="BigQuery created")
    started = _timestamp(item["started_utc"], label="BigQuery started")
    ended = _timestamp(item["ended_utc"], label="BigQuery ended")
    if (
        item["project_id"] != spec["project_id"]
        or item["location"] != spec["location"]
        or item["job_id"] != spec["job_id"]
        or item["query_sha256"] != spec["query_sha256"]
        or item["state"] != "DONE"
        or item["error_result"] is not None
        or item["cache_hit"] is not False
        or type(item["total_bytes_processed"]) is not int
        or not 0 <= item["total_bytes_processed"] <= spec["maximum_bytes_billed"]
        or not created <= started <= ended
    ):
        _fail("normalized snapshot BigQuery job differs from its fixed query")
    return item


def _capture_result(
    *, spec: Mapping[str, object], result_value: object,
) -> tuple[dict[str, object], dict[str, list[dict[str, object]]]]:
    result = _mapping(result_value, label="normalized snapshot query result")
    if set(result) != {"job_metadata", "result_rows"}:
        _fail("normalized snapshot query result fields differ")
    job = _job_metadata(result["job_metadata"], spec=spec)
    records = _sequence(result["result_rows"], label="query result rows")
    if not 1 <= len(records) <= MAX_RESULT_ROWS:
        _fail("normalized snapshot query result count differs")
    rows: dict[str, list[dict[str, object]]] = {
        str(value): [] for value in spec["slice_kinds"]
    }
    metadata: dict[str, dict[str, object]] = {}
    canonical_records: list[dict[str, str]] = []
    for ordinal, raw in enumerate(records):
        record = _mapping(raw, label=f"query result[{ordinal}]")
        if set(record) != {"record_kind", "slice_kind", "row_json"}:
            _fail("normalized snapshot query record fields differ")
        kind = record["record_kind"]
        discriminator = record["slice_kind"]
        parsed = _parse_json_text(record["row_json"], label="query row_json")
        if kind == "row" and discriminator in rows:
            normalized = capture._normalize_source_row(
                pack_id=str(spec["pack_id"]),
                slice_kind=str(discriminator),
                value=parsed,
            )
            rows[str(discriminator)].append(normalized)
        elif kind == "relation-metadata" and discriminator in spec["input_relations"]:
            if discriminator in metadata:
                _fail("normalized snapshot repeated predecessor metadata")
            metadata[str(discriminator)] = _relation_metadata(
                parsed, expected_relation=str(discriminator)
            )
        else:
            _fail("normalized snapshot query returned an unregistered record")
        canonical_records.append({
            "record_kind": str(kind),
            "slice_kind": str(discriminator),
            "row_json": json.dumps(
                parsed, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                allow_nan=False,
            ),
        })
    if set(metadata) != set(spec["input_relations"]) or any(
        not values for values in rows.values()
    ):
        _fail("normalized snapshot query omitted a relation or registered slice")
    # BigQuery exposes historical table rows through time travel, while the
    # legacy metadata views report the current relation metadata.  Prevent a
    # mixed past-row/future-metadata receipt: the fixed snapshot instant must
    # be at or after every reported predecessor modification.  A concurrent
    # or backdated capture therefore fails instead of claiming one coherent
    # predecessor snapshot.
    snapshot_time = datetime.strptime(
        str(spec["snapshot_at_utc"]), "%Y-%m-%dT%H:%M:%SZ"
    ).replace(tzinfo=timezone.utc)
    if any(
        datetime.strptime(
            str(value["modified_time_utc"]), "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=timezone.utc) > snapshot_time
        for value in metadata.values()
    ):
        _fail("normalized snapshot predecessor metadata is newer than its rows")
    for values in rows.values():
        values.sort(key=source.canonical_json_bytes)
    canonical_records.sort(
        key=lambda row: (row["record_kind"], row["slice_kind"], row["row_json"])
    )
    extract = {
        "schema_version": EXTRACT_SCHEMA,
        "pack_id": spec["pack_id"],
        "query_spec_sha256": spec["query_spec_sha256"],
        "snapshot_at_utc": spec["snapshot_at_utc"],
        "job_metadata": job,
        "input_relation_metadata": [
            metadata[str(name)] for name in spec["input_relations"]
        ],
        "input_relation_metadata_sha256": source.canonical_sha256([
            metadata[str(name)] for name in spec["input_relations"]
        ]),
        "result_records": canonical_records,
        "result_record_count": len(canonical_records),
        "result_records_sha256": source.canonical_sha256(canonical_records),
        "projected_rows_by_slice_sha256": {
            name: source.canonical_sha256(values)
            for name, values in sorted(rows.items())
        },
        "evidence_class": source.EVIDENCE_CLASS,
        "observed_at_basis": source.OBSERVED_AT_BASIS,
        "authoritative_pit": False,
        **_policy(),
    }
    return _with_hash(extract, field="query_extract_sha256"), rows


def run_normalized_snapshot_task0_v1(
    request_value: object, *, query_warehouse: QueryWarehouse,
) -> dict[str, object]:
    """Execute one fixed FP query as a non-publishing mechanical gate."""

    request = validate_snapshot_request_v1(request_value)
    if not callable(query_warehouse):
        _fail("normalized snapshot task0 query callback differs")
    spec = request["query_specs"][0]
    try:
        result = query_warehouse(spec)
    except Exception as exc:
        raise CorpusR6PaidSourceNormalizedSnapshotV1Error(
            "normalized snapshot task0 query failed"
        ) from exc
    extract, rows = _capture_result(spec=spec, result_value=result)
    counts = {name: len(values) for name, values in sorted(rows.items())}
    body: dict[str, object] = {
        "schema_version": TASK0_SCHEMA,
        "snapshot_request_sha256": request["snapshot_request_sha256"],
        "run_id": request["run_id"],
        "pack_id": spec["pack_id"],
        "query_spec_sha256": spec["query_spec_sha256"],
        "query_extract_sha256": extract["query_extract_sha256"],
        "job_metadata": extract["job_metadata"],
        "input_relation_metadata_sha256": extract[
            "input_relation_metadata_sha256"
        ],
        "projected_row_counts_by_slice": counts,
        "projected_row_count": sum(counts.values()),
        "all_registered_fp_slices_nonempty": all(value > 0 for value in counts.values()),
        "publication_count": 0,
        "publication_callback_present": False,
        "write_api_reachable_from_task0": False,
        "runtime_principal_write_authority_status": "not-evaluated",
        "recognized_outcome_callback_present": False,
        "runtime_principal_outcome_authority_status": "not-evaluated",
        "outcome_artifacts_read": [],
        "full_snapshot_launched": False,
        "mechanical_launch_gate_passed": True,
        "evidence_class": source.EVIDENCE_CLASS,
        "observed_at_basis": source.OBSERVED_AT_BASIS,
        "authoritative_pit": False,
        "complete": True,
        **_policy(),
    }
    return _with_hash(body, field="snapshot_task0_sha256")


def validate_normalized_snapshot_task0_v1(
    value: object, *, request_value: object,
) -> dict[str, object]:
    receipt = _mapping(value, label="normalized snapshot task0 receipt")
    request = validate_snapshot_request_v1(request_value)
    _validate_hash(receipt, field="snapshot_task0_sha256", label="task0 receipt")
    _validate_policy(receipt, label="task0 receipt")
    expected_fields = {
        "schema_version", "snapshot_request_sha256", "run_id", "pack_id",
        "query_spec_sha256", "query_extract_sha256", "job_metadata",
        "input_relation_metadata_sha256", "projected_row_counts_by_slice",
        "projected_row_count", "all_registered_fp_slices_nonempty",
        "publication_count", "publication_callback_present",
        "write_api_reachable_from_task0",
        "runtime_principal_write_authority_status",
        "recognized_outcome_callback_present",
        "runtime_principal_outcome_authority_status", "outcome_artifacts_read",
        "full_snapshot_launched",
        "mechanical_launch_gate_passed", "evidence_class",
        "observed_at_basis", "authoritative_pit", "complete",
        "snapshot_task0_sha256", *_policy().keys(),
    }
    if set(receipt) != expected_fields:
        _fail("normalized snapshot task0 receipt fields differ")
    spec = request["query_specs"][0]
    _job_metadata(receipt.get("job_metadata"), spec=spec)
    if (
        receipt.get("schema_version") != TASK0_SCHEMA
        or receipt.get("snapshot_request_sha256")
        != request["snapshot_request_sha256"]
        or receipt.get("run_id") != request["run_id"]
        or receipt.get("pack_id") != source.FANTASY_POINTS_PACK
        or receipt.get("query_spec_sha256")
        != request["query_specs"][0]["query_spec_sha256"]
        or type(receipt.get("projected_row_count")) is not int
        or receipt.get("projected_row_count", 0) < 4
        or receipt.get("all_registered_fp_slices_nonempty") is not True
        or receipt.get("publication_count") != 0
        or receipt.get("publication_callback_present") is not False
        or receipt.get("write_api_reachable_from_task0") is not False
        or receipt.get("runtime_principal_write_authority_status")
        != "not-evaluated"
        or receipt.get("recognized_outcome_callback_present") is not False
        or receipt.get("runtime_principal_outcome_authority_status")
        != "not-evaluated"
        or receipt.get("outcome_artifacts_read") != []
        or receipt.get("full_snapshot_launched") is not False
        or receipt.get("mechanical_launch_gate_passed") is not True
        or receipt.get("evidence_class") != source.EVIDENCE_CLASS
        or receipt.get("observed_at_basis") != source.OBSERVED_AT_BASIS
        or receipt.get("authoritative_pit") is not False
        or receipt.get("complete") is not True
        or type(receipt.get("query_extract_sha256")) is not str
        or _SHA.fullmatch(str(receipt.get("query_extract_sha256"))) is None
        or type(receipt.get("input_relation_metadata_sha256")) is not str
        or _SHA.fullmatch(
            str(receipt.get("input_relation_metadata_sha256"))
        ) is None
    ):
        _fail("normalized snapshot task0 receipt differs")
    counts = _mapping(
        receipt.get("projected_row_counts_by_slice"), label="task0 slice counts"
    )
    if (
        set(counts) != set(_PACK_SLICES[source.FANTASY_POINTS_PACK])
        or any(type(value) is not int or value < 1 for value in counts.values())
        or sum(counts.values()) != receipt["projected_row_count"]
    ):
        _fail("normalized snapshot task0 slice counts differ")
    return receipt


def _publish(
    *, uri: str, value: Mapping[str, object],
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    raw = source.canonical_json_bytes(value)
    try:
        identity = _identity(
            publish_create_once(uri, raw), label="normalized snapshot publication"
        )
        reopened = read_exact(identity)
    except Exception as exc:
        raise CorpusR6PaidSourceNormalizedSnapshotV1Error(
            "normalized snapshot create-once publication failed"
        ) from exc
    if (
        identity["uri"] != uri
        or type(reopened) is not bytes
        or reopened != raw
        or len(reopened) != identity["bytes"]
        or sha256(reopened).hexdigest() != identity["sha256"]
    ):
        _fail("normalized snapshot publication exact reopen differs")
    return identity


def publish_normalized_snapshot_v1(
    request_value: object, *, task0_receipt_value: object,
    query_warehouse: QueryWarehouse,
    publish_create_once: PublishCreateOnce, read_exact: ReadExact,
) -> dict[str, object]:
    request = validate_snapshot_request_v1(request_value)
    task0 = validate_normalized_snapshot_task0_v1(
        task0_receipt_value, request_value=request
    )
    if not all(callable(value) for value in (query_warehouse, publish_create_once, read_exact)):
        _fail("normalized snapshot callbacks differ")
    inventory = request["output_inventory"]
    publication: list[dict[str, object]] = []
    manifest_identities: dict[str, dict[str, object]] = {}
    query_receipt_identities: dict[str, dict[str, object]] = {}
    extract_identities: dict[str, dict[str, object]] = {}
    for spec in request["query_specs"]:
        pack_id = str(spec["pack_id"])
        pack_inventory = inventory["packs"][pack_id]
        try:
            query_result = query_warehouse(spec)
        except Exception as exc:
            raise CorpusR6PaidSourceNormalizedSnapshotV1Error(
                f"normalized snapshot query failed for {pack_id}"
            ) from exc
        extract, rows_by_slice = _capture_result(
            spec=spec, result_value=query_result
        )
        if spec["ordinal"] == 0:
            row_counts = {
                name: len(values) for name, values in sorted(rows_by_slice.items())
            }
            if (
                extract["query_extract_sha256"] != task0["query_extract_sha256"]
                or extract["job_metadata"] != task0["job_metadata"]
                or extract["input_relation_metadata_sha256"]
                != task0["input_relation_metadata_sha256"]
                or row_counts != task0["projected_row_counts_by_slice"]
                or sum(row_counts.values()) != task0["projected_row_count"]
            ):
                _fail("normalized snapshot FP rerun differs from its task0 gate")
        extract_identity = _publish(
            uri=str(pack_inventory["extract_uri"]), value=extract,
            publish_create_once=publish_create_once, read_exact=read_exact,
        )
        extract_identities[pack_id] = extract_identity
        publication.append({"role": "source-query-extract", "pack_id": pack_id,
                            "identity": extract_identity})
        query_receipt = _with_hash({
            "schema_version": QUERY_RECEIPT_SCHEMA,
            "pack_id": pack_id,
            "query_spec": spec,
            "query_spec_sha256": spec["query_spec_sha256"],
            "job_metadata": extract["job_metadata"],
            "input_relation_metadata": extract["input_relation_metadata"],
            "input_relation_metadata_sha256": extract[
                "input_relation_metadata_sha256"
            ],
            "exact_query_extract_identity": extract_identity,
            "exact_query_extract_sha256": extract["query_extract_sha256"],
            "result_record_count": extract["result_record_count"],
            "result_records_sha256": extract["result_records_sha256"],
            "snapshot_at_utc": request["snapshot_at_utc"],
            "provider_job_and_query_bound": True,
            "projected_rows_time_travel_pinned": True,
            "relation_metadata_observed_at_query_time": True,
            "relation_metadata_modified_no_later_than_snapshot": True,
            "evidence_class": source.EVIDENCE_CLASS,
            "observed_at_basis": source.OBSERVED_AT_BASIS,
            "authoritative_pit": False,
            **_policy(),
        }, field="query_receipt_sha256")
        receipt_identity = _publish(
            uri=str(pack_inventory["query_receipt_uri"]), value=query_receipt,
            publish_create_once=publish_create_once, read_exact=read_exact,
        )
        query_receipt_identities[pack_id] = receipt_identity
        publication.append({"role": "source-query-receipt", "pack_id": pack_id,
                            "identity": receipt_identity})
        shard_pairs: list[tuple[dict[str, object], dict[str, object]]] = []
        for slice_kind in sorted(rows_by_slice):
            shard = capture.build_artifact_row_shard_v1(
                pack_id=pack_id, slice_kind=slice_kind,
                rows=rows_by_slice[slice_kind],
            )
            shard_identity = _publish(
                uri=str(pack_inventory["shard_uris"][slice_kind]), value=shard,
                publish_create_once=publish_create_once, read_exact=read_exact,
            )
            shard_pairs.append((shard, shard_identity))
            publication.append({"role": "normalized-row-shard", "pack_id": pack_id,
                                "slice_kind": slice_kind,
                                "identity": shard_identity})
        shard_pairs.sort(key=lambda pair: str(pair[1]["uri"]))
        manifest = capture.build_artifact_pack_manifest_v1(
            # Keep the immutable manifest identifier within the capture
            # contract's 64-character ceiling even when the caller uses the
            # request contract's maximum-length run id.  The query digest
            # suffix keeps independently defined slices distinct after the
            # bounded prefix.
            manifest_id=(
                f"{str(request['run_id'])[:53]}-"
                f"{str(spec['query_sha256'])[:8]}-{spec['ordinal']}"
            ),
            pack_id=pack_id,
            shard_objects=[pair[0] for pair in shard_pairs],
            shard_identities=[pair[1] for pair in shard_pairs],
            source_manifest_identities=[receipt_identity],
            source_artifact_identities=[extract_identity],
            projection_code_identity=request["projection_code_identity"],
        )
        manifest_identity = _publish(
            uri=str(pack_inventory["manifest_uri"]), value=manifest,
            publish_create_once=publish_create_once, read_exact=read_exact,
        )
        manifest_identities[pack_id] = manifest_identity
        publication.append({"role": "artifact-pack-manifest", "pack_id": pack_id,
                            "identity": manifest_identity})
    published_uris = [str(row["identity"]["uri"]) for row in publication]
    if sorted(published_uris) != inventory["nonterminal_uris"]:
        _fail("normalized snapshot publication differs from fixed inventory")
    terminal = _with_hash({
        "schema_version": TERMINAL_SCHEMA,
        "run_id": request["run_id"],
        "snapshot_request_sha256": request["snapshot_request_sha256"],
        "snapshot_task0_sha256": task0["snapshot_task0_sha256"],
        "snapshot_at_utc": request["snapshot_at_utc"],
        "projection_code_identity": request["projection_code_identity"],
        "artifact_manifest_identities": manifest_identities,
        "source_query_receipt_identities": query_receipt_identities,
        "source_query_extract_identities": extract_identities,
        "nonterminal_publication": publication,
        "nonterminal_publication_sha256": source.canonical_sha256(publication),
        "nonterminal_object_count": len(publication),
        "query_count": 2,
        "all_outputs_create_once_exact_reopened": True,
        "terminal_published_last": True,
        "compatible_with_seven_pack_artifact_manifest_contract": True,
        "evidence_class": source.EVIDENCE_CLASS,
        "observed_at_basis": source.OBSERVED_AT_BASIS,
        "authoritative_pit": False,
        "automatic_policy_promotion": False,
        "complete": True,
        **_policy(),
    }, field="snapshot_terminal_sha256")
    terminal_identity = _publish(
        uri=str(inventory["terminal_uri"]), value=terminal,
        publish_create_once=publish_create_once, read_exact=read_exact,
    )
    reopened = reopen_normalized_snapshot_v1(
        terminal_identity=terminal_identity, read_exact=read_exact
    )
    return {
        "schema_version": PUBLICATION_RESULT_SCHEMA,
        "terminal": terminal,
        "terminal_identity": terminal_identity,
        "snapshot_terminal_sha256": terminal["snapshot_terminal_sha256"],
        "artifact_manifest_identities": manifest_identities,
        "independent_reopen": reopened,
        "complete": True,
        **_policy(),
    }


def _parse_exact(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> dict[str, object]:
    identity = _identity(identity_value, label=f"{label} identity")
    try:
        raw = read_exact(identity)
    except Exception as exc:
        raise CorpusR6PaidSourceNormalizedSnapshotV1Error(
            f"{label} exact read failed"
        ) from exc
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact bytes differ")
    try:
        item = _mapping(json.loads(raw.decode("utf-8")), label=label)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6PaidSourceNormalizedSnapshotV1Error(
            f"{label} canonical JSON differs"
        ) from exc
    if source.canonical_json_bytes(item) != raw:
        _fail(f"{label} canonical bytes differ")
    return item


def reopen_normalized_snapshot_v1(
    *, terminal_identity: Mapping[str, object], read_exact: ReadExact,
) -> dict[str, object]:
    identity = _identity(terminal_identity, label="normalized snapshot terminal")
    terminal = _parse_exact(
        identity, read_exact=read_exact, label="normalized snapshot terminal"
    )
    _validate_hash(terminal, field="snapshot_terminal_sha256", label="terminal")
    _validate_policy(terminal, label="terminal")
    if (
        terminal.get("schema_version") != TERMINAL_SCHEMA
        or terminal.get("nonterminal_object_count") != 12
        or terminal.get("query_count") != 2
        or terminal.get("terminal_published_last") is not True
        or terminal.get("compatible_with_seven_pack_artifact_manifest_contract")
        is not True
        or terminal.get("evidence_class") != source.EVIDENCE_CLASS
        or terminal.get("observed_at_basis") != source.OBSERVED_AT_BASIS
        or terminal.get("authoritative_pit") is not False
        or terminal.get("automatic_policy_promotion") is not False
        or terminal.get("complete") is not True
    ):
        _fail("normalized snapshot terminal fixed law differs")
    manifests = _mapping(
        terminal.get("artifact_manifest_identities"), label="terminal manifests"
    )
    if set(manifests) != set(capture.ARTIFACT_PACK_IDS):
        _fail("normalized snapshot terminal manifest registry differs")
    reader = capture.BoundedExactReaderV1(read_exact)
    for pack_id in capture.ARTIFACT_PACK_IDS:
        capture._open_artifact_pack_manifest_v1(
            manifest_identity=manifests[pack_id], reader=reader,
            expected_pack_id=pack_id,
        )
    body: dict[str, object] = {
        "schema_version": REOPEN_SCHEMA,
        "terminal_identity": identity,
        "snapshot_terminal_sha256": terminal["snapshot_terminal_sha256"],
        "artifact_manifest_identities": manifests,
        "artifact_manifest_count": 2,
        "both_manifests_and_all_exact_predecessors_reopened": True,
        "read_budget_receipt": reader.receipt(),
        "recognized_outcome_callback_present": False,
        "runtime_principal_outcome_authority_status": "not-evaluated",
        "outcome_artifacts_read": [],
        "publication_callback_present": False,
        "runtime_principal_write_authority_status": "not-evaluated",
        "automatic_policy_promotion": False,
        "complete": True,
        **_policy(),
    }
    return _with_hash(body, field="snapshot_reopen_sha256")


__all__ = [
    "CorpusR6PaidSourceNormalizedSnapshotV1Error",
    "OUTPUT_PREFIX",
    "MODULE_PATH",
    "QUERY_SPEC_SCHEMA",
    "PUBLICATION_RESULT_SCHEMA",
    "REQUEST_SCHEMA",
    "TERMINAL_SCHEMA",
    "TASK0_SCHEMA",
    "build_snapshot_request_v1",
    "frozen_query_specs_v1",
    "publish_normalized_snapshot_v1",
    "reopen_normalized_snapshot_v1",
    "run_normalized_snapshot_task0_v1",
    "validate_snapshot_request_v1",
    "validate_normalized_snapshot_task0_v1",
]
