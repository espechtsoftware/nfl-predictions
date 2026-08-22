"""Pure, versioned retrieval engine for immutable lineup corpora.

The corpus *producer* and the corpus *retriever* are deliberately separate.
This module consumes one immutable, generation-pinned snapshot made of five
candidate/world blocks.  It never generates a lineup, reads an outcome,
changes a live policy, or talks to GCP.  Callers provide two tiny capability
seams: an exact-object reader and a create-once publisher.

V1 is intentionally narrow enough to run against the retained 2023-W1
R0--R4 artifacts: candidate provenance and a player catalog are canonical
JSON objects; each world block is the retained NPZ body containing
``cand_ix``, ``totals``, ``player_ids`` and ``player_draws``.  The engine
forms the complete unique-roster union, scores every roster in every one of
the 50,000 worlds, runs four deterministic exact-budget retrieval laws on
R0--R3, and evaluates them on untouched R4.

Large bodies are create-once NPZ/JSON sidecars.  Task authorities and graph
projections contain compact summaries plus generation/SHA/byte pointers.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
from io import BytesIO
from itertools import combinations
import json
import math
import re
from typing import Any, Final

import numpy as np


SNAPSHOT_SCHEMA: Final = "corpus-retrieval-snapshot-manifest/v1"
STRATEGY_SCHEMA: Final = "corpus-retrieval-strategy/v1"
SUITE_SCHEMA: Final = "corpus-retrieval-suite-manifest/v1"
CANDIDATE_ROWS_SCHEMA: Final = "corpus-retrieval-candidate-rows/v1"
PLAYER_CATALOG_SCHEMA: Final = "corpus-retrieval-player-catalog/v1"
INPUT_QUERY_AUTHORITY_SCHEMA: Final = "corpus-retrieval-input-query-authority/v1"
TASK_RESULT_SCHEMA: Final = "corpus-retrieval-task-result/v1"
COMPLETION_SCHEMA: Final = "corpus-retrieval-batch-completion/v1"
LINEUP_TABLE_SCHEMA: Final = "corpus-retrieval-unique-lineups/v1"
SELECTION_SCHEMA: Final = "corpus-retrieval-selection/v1"
ENRICHMENT_SCHEMA: Final = "corpus-retrieval-enrichment/v1"
REDUNDANCY_SCHEMA: Final = "corpus-retrieval-redundancy-topk/v1"
GRAPH_SCHEMA: Final = "corpus-retrieval-graph-projection/v1"
FILL_INSIGHT_SCHEMA: Final = "corpus-retrieval-fill-insight-input/v1"

PUBLICATION_MODE: Final = "create_once"
SCORE_UNIT: Final = "dk_points_float32"
PRIMARY_EVENT_OPERATOR: Final = ">"
PRIMARY_EVENT_THRESHOLD: Final = 200.0
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
DISCOVERY_BLOCKS: Final = ("R0", "R1", "R2", "R3")
HELDOUT_BLOCKS: Final = ("R4",)
WORLDS_PER_BLOCK: Final = 10_000
ROSTER_SIZE: Final = 9
DEFAULT_ENTRY_BUDGET: Final = 80
MAX_REDUNDANCY_PAIRS: Final = 2_000
REDUNDANCY_CORRELATION_REPLAY_ABS_TOLERANCE: Final = 1e-15
MIN_ENRICHMENT_LINEUP_SUPPORT: Final = 5
NPZ_FORMAT: Final = "retained-candidate-world-npz/v1"

_SHA = re.compile(r"[0-9a-f]{64}")
_COMMIT = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")
_DIGEST = re.compile(r"sha256:[0-9a-f]{64}")
_GENERATION = re.compile(r"[1-9][0-9]*")
_ID = re.compile(r"[a-z0-9][a-z0-9._:-]*")
_UTC = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z"
)

ObjectReader = Callable[[Mapping[str, object]], bytes]
CreateOncePublisher = Callable[[str, bytes, str], Mapping[str, object]]


class CorpusRetrievalError(ValueError):
    """A fail-closed corpus retrieval contract violation."""


def canonical_json_bytes(value: object) -> bytes:
    """Canonical JSON bytes with no non-finite number spellings."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusRetrievalError("value is not canonical JSON") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def parse_canonical_json_bytes(raw: bytes, *, label: str) -> object:
    """Parse canonical JSON while rejecting duplicate keys."""

    def pairs(values: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in values:
            if key in result:
                raise CorpusRetrievalError(
                    f"{label} contains duplicate key {key!r}"
                )
            result[key] = value
        return result

    def reject_constant(value: str) -> object:
        raise CorpusRetrievalError(f"{label} contains {value}")

    if type(raw) is not bytes:
        raise CorpusRetrievalError(f"{label} must be bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
        )
    except CorpusRetrievalError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusRetrievalError(f"{label} is not valid JSON") from exc
    if canonical_json_bytes(value) != raw:
        raise CorpusRetrievalError(f"{label} is not canonical JSON")
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusRetrievalError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CorpusRetrievalError(f"{label} must be an array")
    return value


def _keys(
    value: Mapping[str, object], expected: set[str] | frozenset[str], *, label: str,
) -> None:
    actual = set(value)
    if actual != set(expected):
        raise CorpusRetrievalError(
            f"{label} keys differ; missing={sorted(set(expected) - actual)}, "
            f"unknown={sorted(actual - set(expected))}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusRetrievalError(f"{label} must be a canonical string")
    return value


def _identifier(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _ID.fullmatch(result) is None:
        raise CorpusRetrievalError(f"{label} must be a lowercase identifier")
    return result


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        raise CorpusRetrievalError(f"{label} must be a lowercase SHA-256")
    return value


def _integer(value: object, *, label: str, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise CorpusRetrievalError(f"{label} must be an exact integer")
    if minimum is not None and value < minimum:
        raise CorpusRetrievalError(f"{label} must be >= {minimum}")
    return value


def _boolean(value: object, *, label: str) -> bool:
    if type(value) is not bool:
        raise CorpusRetrievalError(f"{label} must be a literal Boolean")
    return value


def _timestamp(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _UTC.fullmatch(result) is None:
        raise CorpusRetrievalError(f"{label} must be second-resolution UTC")
    return result


def _gcs_uri(value: object, *, label: str, prefix: bool = False) -> str:
    result = _string(value, label=label)
    if not result.startswith("gs://"):
        raise CorpusRetrievalError(f"{label} must be a GCS URI")
    bucket, marker, name = result[5:].partition("/")
    if not marker or not bucket or not name or ".." in name.split("/"):
        raise CorpusRetrievalError(f"{label} is not a canonical GCS URI")
    if prefix != result.endswith("/"):
        kind = "prefix" if prefix else "object"
        raise CorpusRetrievalError(f"{label} must name a GCS {kind}")
    return result


def normalize_object_identity(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    _keys(item, {"uri", "generation", "sha256", "bytes"}, label=label)
    generation = _string(item["generation"], label=f"{label}.generation")
    if _GENERATION.fullmatch(generation) is None:
        raise CorpusRetrievalError(f"{label}.generation must be positive")
    return {
        "uri": _gcs_uri(item["uri"], label=f"{label}.uri"),
        "generation": generation,
        "sha256": _digest(item["sha256"], label=f"{label}.sha256"),
        "bytes": _integer(item["bytes"], label=f"{label}.bytes", minimum=1),
    }


def _read_exact(
    identity: Mapping[str, object], reader: ObjectReader, *, label: str,
) -> bytes:
    expected = normalize_object_identity(identity, label=label)
    raw = reader(expected)
    if type(raw) is not bytes:
        raise CorpusRetrievalError(f"{label} reader did not return bytes")
    if len(raw) != expected["bytes"] or sha256(raw).hexdigest() != expected["sha256"]:
        raise CorpusRetrievalError(f"{label} content identity differs")
    return raw


def _publish_exact(
    *, uri: str, raw: bytes, media_type: str, publisher: CreateOncePublisher,
) -> dict[str, object]:
    expected_uri = _gcs_uri(uri, label="publication uri")
    if type(raw) is not bytes or not raw:
        raise CorpusRetrievalError("publication body must be nonempty bytes")
    retained = normalize_object_identity(
        publisher(expected_uri, raw, media_type), label="published object"
    )
    if (
        retained["uri"] != expected_uri
        or retained["bytes"] != len(raw)
        or retained["sha256"] != sha256(raw).hexdigest()
    ):
        raise CorpusRetrievalError("publisher returned a different object identity")
    return retained


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    item: Mapping[str, object], field: str, *, label: str,
) -> str:
    retained = _digest(item[field], label=f"{label}.{field}")
    body = {key: value for key, value in item.items() if key != field}
    if retained != canonical_sha256(body):
        raise CorpusRetrievalError(f"{label} self-hash differs")
    return retained


def object_identity_for_bytes(
    *, uri: str, generation: str, raw: bytes,
) -> dict[str, object]:
    """Pure fixture helper; it does not claim that publication occurred."""
    return normalize_object_identity(
        {
            "uri": uri,
            "generation": generation,
            "sha256": sha256(raw).hexdigest(),
            "bytes": len(raw),
        },
        label="fixture object identity",
    )


def _normalize_input_query_receipt(
    value: object, *, label: str,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    _keys(item, {
        "job_id", "project", "location", "sql_sha256", "snapshot_at_utc",
        "created", "started", "ended", "total_bytes_processed", "cache_hit",
        "error_result", "row_count", "rows_sha256", "normalized_rows_sha256",
    }, label=label)
    if type(item["cache_hit"]) is not bool or item["error_result"] is not None:
        raise CorpusRetrievalError(f"{label} did not finish cleanly")
    return {
        "job_id": _string(item["job_id"], label=f"{label} job id"),
        "project": _string(item["project"], label=f"{label} project"),
        "location": _string(item["location"], label=f"{label} location"),
        "sql_sha256": _digest(item["sql_sha256"], label=f"{label} SQL SHA"),
        "snapshot_at_utc": _timestamp(
            item["snapshot_at_utc"], label=f"{label} snapshot time"
        ),
        "created": _string(item["created"], label=f"{label} created"),
        "started": _string(item["started"], label=f"{label} started"),
        "ended": _string(item["ended"], label=f"{label} ended"),
        "total_bytes_processed": _integer(
            item["total_bytes_processed"],
            label=f"{label} bytes processed",
            minimum=0,
        ),
        "cache_hit": item["cache_hit"],
        "error_result": None,
        "row_count": _integer(
            item["row_count"], label=f"{label} row count", minimum=1
        ),
        "rows_sha256": _digest(
            item["rows_sha256"], label=f"{label} rows SHA"
        ),
        "normalized_rows_sha256": _digest(
            item["normalized_rows_sha256"],
            label=f"{label} normalized rows SHA",
        ),
    }


def build_input_query_authority(
    *, task_id: str, snapshot_at_utc: str,
    candidate_query: Mapping[str, object],
    player_query: Mapping[str, object],
) -> dict[str, object]:
    candidate = _normalize_input_query_receipt(
        candidate_query, label="candidate query receipt"
    )
    player = _normalize_input_query_receipt(
        player_query, label="player query receipt"
    )
    snapshot_time = _timestamp(snapshot_at_utc, label="input query snapshot time")
    if (
        candidate["snapshot_at_utc"] != snapshot_time
        or player["snapshot_at_utc"] != snapshot_time
        or candidate["project"] != player["project"]
        or candidate["location"] != player["location"]
    ):
        raise CorpusRetrievalError("input queries do not share one frozen scope")
    body = {
        "schema_version": INPUT_QUERY_AUTHORITY_SCHEMA,
        "task_id": _identifier(task_id, label="input query task id"),
        "snapshot_at_utc": snapshot_time,
        "candidate_query": candidate,
        "player_query": player,
        "actual_outcome_columns_selected": False,
        "uses_realized_outcomes": False,
    }
    return _self_hash(body, "query_authority_sha256")


def validate_input_query_authority(value: object) -> dict[str, object]:
    item = _mapping(value, label="input query authority")
    _keys(item, {
        "schema_version", "task_id", "snapshot_at_utc", "candidate_query",
        "player_query", "actual_outcome_columns_selected",
        "uses_realized_outcomes", "query_authority_sha256",
    }, label="input query authority")
    if (
        item["schema_version"] != INPUT_QUERY_AUTHORITY_SCHEMA
        or item["actual_outcome_columns_selected"] is not False
        or item["uses_realized_outcomes"] is not False
    ):
        raise CorpusRetrievalError("input query authority outcome policy differs")
    rebuilt = build_input_query_authority(
        task_id=_identifier(item["task_id"], label="input query task id"),
        snapshot_at_utc=_timestamp(
            item["snapshot_at_utc"], label="input query snapshot time"
        ),
        candidate_query=_mapping(
            item["candidate_query"], label="candidate query receipt"
        ),
        player_query=_mapping(item["player_query"], label="player query receipt"),
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(item):
        raise CorpusRetrievalError("input query authority canonical replay differs")
    return rebuilt


def normalize_candidate_query_rows(
    rows: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Canonicalize outcome-free candidate query rows without provenance."""
    normalized_rows: list[dict[str, object]] = []
    for offset, raw in enumerate(rows):
        row = _mapping(raw, label=f"candidate row[{offset}]")
        required = {
            "panel_id", "season", "week", "cand_ix", "tag", "all_tags", "players"
        }
        if set(row) != required:
            raise CorpusRetrievalError(
                f"candidate row[{offset}] keys differ from the score-free schema"
            )
        players_raw = row["players"]
        if type(players_raw) is str:
            players = [part for part in players_raw.split(",") if part]
        else:
            players = [
                _string(value, label=f"candidate row[{offset}].players")
                for value in _sequence(players_raw, label="candidate players")
            ]
        tags_raw = row["all_tags"]
        if type(tags_raw) is str:
            try:
                tags_raw = json.loads(tags_raw)
            except json.JSONDecodeError as exc:
                raise CorpusRetrievalError("candidate all_tags is not JSON") from exc
        tags = sorted({
            _string(value, label=f"candidate row[{offset}].all_tags")
            for value in _sequence(tags_raw, label="candidate all_tags")
        })
        tag = _string(row["tag"], label=f"candidate row[{offset}].tag")
        if tag not in tags:
            tags.append(tag)
            tags.sort()
        if len(players) != ROSTER_SIZE or len(set(players)) != ROSTER_SIZE:
            raise CorpusRetrievalError("candidate roster must contain nine unique IDs")
        normalized_rows.append({
            "panel_id": _identifier(row["panel_id"], label="candidate panel_id"),
            "season": _integer(row["season"], label="candidate season", minimum=2000),
            "week": _integer(row["week"], label="candidate week", minimum=1),
            "cand_ix": _integer(row["cand_ix"], label="candidate cand_ix", minimum=0),
            "tag": tag,
            "all_tags": tags,
            "players": players,
        })
    normalized_rows.sort(key=lambda row: (str(row["panel_id"]), int(row["cand_ix"])))
    return normalized_rows


def build_candidate_rows_object(
    *,
    task_id: str,
    source_authority: Mapping[str, object],
    source_sql_sha256: str,
    source_query_receipt: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Normalize outcome-free warehouse rows into a canonical source body."""
    normalized_rows = normalize_candidate_query_rows(rows)
    normalized_sql_sha = _digest(
        source_sql_sha256, label="source SQL SHA-256"
    )
    query_receipt = _normalize_input_query_receipt(
        source_query_receipt, label="candidate query receipt"
    )
    if (
        query_receipt["sql_sha256"] != normalized_sql_sha
        or query_receipt["row_count"] != len(normalized_rows)
        or query_receipt["normalized_rows_sha256"]
        != canonical_sha256(normalized_rows)
    ):
        raise CorpusRetrievalError("candidate query receipt differs from rows/SQL")
    body = {
        "schema_version": CANDIDATE_ROWS_SCHEMA,
        "task_id": _identifier(task_id, label="candidate rows task_id"),
        "source_authority": normalize_object_identity(
            source_authority, label="candidate rows source authority"
        ),
        "source_sql_sha256": normalized_sql_sha,
        "source_query_receipt": query_receipt,
        "rows": normalized_rows,
    }
    return _self_hash(body, "candidate_rows_sha256")


def validate_candidate_rows_object(value: object) -> dict[str, object]:
    item = _mapping(value, label="candidate rows object")
    _keys(item, {
        "schema_version", "task_id", "source_authority", "source_sql_sha256",
        "source_query_receipt", "rows", "candidate_rows_sha256",
    }, label="candidate rows object")
    if item["schema_version"] != CANDIDATE_ROWS_SCHEMA:
        raise CorpusRetrievalError("candidate rows schema differs")
    rebuilt = build_candidate_rows_object(
        task_id=_identifier(item["task_id"], label="candidate rows task_id"),
        source_authority=_mapping(
            item["source_authority"], label="candidate rows source authority"
        ),
        source_sql_sha256=_digest(item["source_sql_sha256"], label="source SQL SHA"),
        source_query_receipt=_mapping(
            item["source_query_receipt"], label="source query receipt"
        ),
        rows=_sequence(item["rows"], label="candidate rows"),
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(item):
        raise CorpusRetrievalError("candidate rows canonical replay differs")
    return rebuilt


def normalize_player_query_rows(
    players: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Canonicalize point-in-time player query rows without provenance."""
    normalized: list[dict[str, object]] = []
    fields = {"id", "name", "pos", "team", "opp", "game_id", "salary", "proj"}
    for offset, raw in enumerate(players):
        row = _mapping(raw, label=f"player[{offset}]")
        _keys(row, fields, label=f"player[{offset}]")
        projection = row["proj"]
        if type(projection) not in (int, float) or not math.isfinite(float(projection)):
            raise CorpusRetrievalError("player projection must be finite")
        normalized.append({
            "id": _string(row["id"], label="player id"),
            "name": _string(row["name"], label="player name"),
            "pos": _string(row["pos"], label="player position").upper(),
            "team": _string(row["team"], label="player team"),
            "opp": _string(row["opp"], label="player opponent"),
            "game_id": _string(row["game_id"], label="player game_id"),
            "salary": _integer(row["salary"], label="player salary", minimum=0),
            "proj": float(projection),
        })
    normalized.sort(key=lambda row: str(row["id"]))
    ids = [str(row["id"]) for row in normalized]
    if not normalized or len(ids) != len(set(ids)):
        raise CorpusRetrievalError("player catalog is empty or repeats IDs")
    return normalized


def build_player_catalog_object(
    *,
    task_id: str,
    source_authority: Mapping[str, object],
    players: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Normalize the source-lock player catalog used for roster analytics."""
    normalized = normalize_player_query_rows(players)
    body = {
        "schema_version": PLAYER_CATALOG_SCHEMA,
        "task_id": _identifier(task_id, label="player catalog task_id"),
        "source_authority": normalize_object_identity(
            source_authority, label="player catalog source authority"
        ),
        "players": normalized,
    }
    return _self_hash(body, "player_catalog_sha256")


def validate_player_catalog_object(value: object) -> dict[str, object]:
    item = _mapping(value, label="player catalog")
    _keys(item, {
        "schema_version", "task_id", "source_authority", "players",
        "player_catalog_sha256",
    }, label="player catalog")
    if item["schema_version"] != PLAYER_CATALOG_SCHEMA:
        raise CorpusRetrievalError("player catalog schema differs")
    rebuilt = build_player_catalog_object(
        task_id=_identifier(item["task_id"], label="player catalog task_id"),
        source_authority=_mapping(item["source_authority"], label="source authority"),
        players=_sequence(item["players"], label="players"),
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(item):
        raise CorpusRetrievalError("player catalog canonical replay differs")
    return rebuilt


def _normalize_producer(value: object) -> dict[str, object]:
    item = _mapping(value, label="snapshot producer")
    _keys(item, {
        "producer_id", "producer_version", "producer_run_id", "producer_authority",
    }, label="snapshot producer")
    return {
        "producer_id": _identifier(item["producer_id"], label="producer id"),
        "producer_version": _identifier(
            item["producer_version"], label="producer version"
        ),
        "producer_run_id": _identifier(
            item["producer_run_id"], label="producer run id"
        ),
        "producer_authority": normalize_object_identity(
            item["producer_authority"], label="producer authority"
        ),
    }


def _normalize_snapshot_task(
    value: object, *, expected_index: int,
) -> dict[str, object]:
    item = _mapping(value, label=f"snapshot task[{expected_index}]")
    input_keys = {
        "task_index", "task_id", "slate", "candidate_rows_object",
        "player_catalog_object", "world_blocks",
    }
    if set(item) not in (input_keys, input_keys | {"task_sha256"}):
        _keys(item, input_keys, label=f"snapshot task[{expected_index}]")
    index = _integer(item["task_index"], label="snapshot task index", minimum=0)
    if index != expected_index:
        raise CorpusRetrievalError("snapshot tasks are not in ordinal order")
    task_id = _identifier(item["task_id"], label="snapshot task id")
    slate = _mapping(item["slate"], label="snapshot task slate")
    _keys(slate, {"season", "week", "slate_id"}, label="snapshot task slate")
    normalized_slate = {
        "season": _integer(slate["season"], label="slate season", minimum=2000),
        "week": _integer(slate["week"], label="slate week", minimum=1),
        "slate_id": _identifier(slate["slate_id"], label="slate id"),
    }
    raw_blocks = _sequence(item["world_blocks"], label="world blocks")
    if len(raw_blocks) != len(WORLD_BLOCKS):
        raise CorpusRetrievalError("snapshot task must contain exact R0--R4 blocks")
    blocks: list[dict[str, object]] = []
    panel_ids: set[str] = set()
    object_keys: set[tuple[object, ...]] = set()
    for ordinal, (raw_block, expected_id) in enumerate(
        zip(raw_blocks, WORLD_BLOCKS, strict=True)
    ):
        block = _mapping(raw_block, label=f"world block {expected_id}")
        _keys(block, {
            "ordinal", "block_id", "panel_id", "artifact_object", "format",
            "expected_candidate_count", "expected_player_count",
            "expected_world_count",
        }, label=f"world block {expected_id}")
        if (
            _integer(block["ordinal"], label="world block ordinal", minimum=0)
            != ordinal
            or block["block_id"] != expected_id
            or block["format"] != NPZ_FORMAT
        ):
            raise CorpusRetrievalError("world block order/id/format differs")
        panel_id = _identifier(block["panel_id"], label="world block panel id")
        if panel_id in panel_ids:
            raise CorpusRetrievalError("world blocks repeat panel ids")
        panel_ids.add(panel_id)
        artifact = normalize_object_identity(
            block["artifact_object"], label=f"world block {expected_id} artifact"
        )
        object_key = tuple(artifact[key] for key in ("uri", "generation", "sha256", "bytes"))
        if object_key in object_keys:
            raise CorpusRetrievalError("world blocks repeat artifact identities")
        object_keys.add(object_key)
        blocks.append({
            "ordinal": ordinal,
            "block_id": expected_id,
            "panel_id": panel_id,
            "artifact_object": artifact,
            "format": NPZ_FORMAT,
            "expected_candidate_count": _integer(
                block["expected_candidate_count"],
                label="expected candidate count", minimum=DEFAULT_ENTRY_BUDGET,
            ),
            "expected_player_count": _integer(
                block["expected_player_count"],
                label="expected player count", minimum=ROSTER_SIZE,
            ),
            "expected_world_count": _integer(
                block["expected_world_count"],
                label="expected world count", minimum=1,
            ),
        })
        if blocks[-1]["expected_world_count"] != WORLDS_PER_BLOCK:
            raise CorpusRetrievalError("v1 requires exactly 10,000 worlds per block")
    body = {
        "task_index": index,
        "task_id": task_id,
        "slate": normalized_slate,
        "candidate_rows_object": normalize_object_identity(
            item["candidate_rows_object"], label="candidate rows object identity"
        ),
        "player_catalog_object": normalize_object_identity(
            item["player_catalog_object"], label="player catalog object identity"
        ),
        "world_blocks": blocks,
    }
    result = _self_hash(body, "task_sha256")
    if "task_sha256" in item and canonical_json_bytes(result) != canonical_json_bytes(item):
        raise CorpusRetrievalError("snapshot task self-hash differs")
    return result


def build_snapshot_manifest(
    *,
    snapshot_id: str,
    created_at_utc: str,
    producer: Mapping[str, object],
    tasks: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Build the immutable retrieval snapshot pointer manifest."""
    normalized_tasks = [
        _normalize_snapshot_task(task, expected_index=index)
        for index, task in enumerate(tasks)
    ]
    if not normalized_tasks:
        raise CorpusRetrievalError("snapshot tasks are empty")
    task_ids = [str(task["task_id"]) for task in normalized_tasks]
    if len(task_ids) != len(set(task_ids)):
        raise CorpusRetrievalError("snapshot tasks repeat task ids")
    body = {
        "schema_version": SNAPSHOT_SCHEMA,
        "snapshot_id": _identifier(snapshot_id, label="snapshot id"),
        "created_at_utc": _timestamp(created_at_utc, label="snapshot created_at"),
        "publication_mode": PUBLICATION_MODE,
        "producer": _normalize_producer(producer),
        "score_unit": SCORE_UNIT,
        "primary_event": {
            "operator": PRIMARY_EVENT_OPERATOR,
            "threshold": PRIMARY_EVENT_THRESHOLD,
            "semantics": "strict-score-greater-than-200-dk-points",
        },
        "feature_policy": {
            "point_in_time_only": True,
            "realized_outcomes_present": False,
            "selection_may_use_declared_features_only": True,
        },
        "tasks": normalized_tasks,
        "licenses": {
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
        },
    }
    return _self_hash(body, "snapshot_manifest_sha256")


def validate_snapshot_manifest(value: object) -> dict[str, object]:
    item = _mapping(value, label="snapshot manifest")
    _keys(item, {
        "schema_version", "snapshot_id", "created_at_utc", "publication_mode",
        "producer", "score_unit", "primary_event", "feature_policy", "tasks",
        "licenses", "snapshot_manifest_sha256",
    }, label="snapshot manifest")
    if item["schema_version"] != SNAPSHOT_SCHEMA:
        raise CorpusRetrievalError("snapshot schema differs")
    rebuilt = build_snapshot_manifest(
        snapshot_id=_identifier(item["snapshot_id"], label="snapshot id"),
        created_at_utc=_timestamp(item["created_at_utc"], label="created_at"),
        producer=_mapping(item["producer"], label="producer"),
        tasks=_sequence(item["tasks"], label="snapshot tasks"),
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(item):
        raise CorpusRetrievalError("snapshot manifest canonical replay differs")
    return rebuilt


def _strategy(
    *, ordinal: int, strategy_id: str, method: str, entry_budget: int,
    parameters: Mapping[str, object], tie_law: Sequence[str], description: str,
) -> dict[str, object]:
    body = {
        "schema_version": STRATEGY_SCHEMA,
        "ordinal": ordinal,
        "strategy_id": strategy_id,
        "method": method,
        "entry_budget": entry_budget,
        "parameters": dict(parameters),
        "tie_law": list(tie_law),
        "selection_inputs": "discovery-block-simulated-scores-only",
        "description": description,
    }
    return _self_hash(body, "strategy_sha256")


def frozen_retrieval_strategies(
    entry_budget: int = DEFAULT_ENTRY_BUDGET,
) -> list[dict[str, object]]:
    """The four registered v1 retrieval laws, all at one exact budget."""
    budget = _integer(entry_budget, label="entry budget", minimum=1)
    if budget != DEFAULT_ENTRY_BUDGET:
        raise CorpusRetrievalError("retrieval v1 requires an exact-80 budget")
    return [
        _strategy(
            ordinal=0,
            strategy_id="coverage-194-v1",
            method="greedy-threshold-coverage-v1",
            entry_budget=budget,
            parameters={"threshold": 194.0, "operator": ">="},
            tie_law=[
                "largest-marginal-new-world-count",
                "largest-individual-threshold-count",
                "largest-discovery-mean-score",
                "ascending-lineup-id",
            ],
            description="Incumbent binary world coverage at 194 DK points.",
        ),
        _strategy(
            ordinal=1,
            strategy_id="strict-200-coverage-v1",
            method="greedy-threshold-coverage-v1",
            entry_budget=budget,
            parameters={"threshold": 200.0, "operator": ">"},
            tie_law=[
                "largest-marginal-new-world-count",
                "largest-individual-threshold-count",
                "largest-discovery-mean-score",
                "ascending-lineup-id",
            ],
            description="Strict primary-event world coverage above 200.",
        ),
        _strategy(
            ordinal=2,
            strategy_id="tail-ladder-200-210-220-v1",
            method="greedy-tail-ladder-v1",
            entry_budget=budget,
            parameters={
                "rungs": [
                    {"threshold": 200.0, "operator": ">", "weight": 1},
                    {"threshold": 210.0, "operator": ">", "weight": 4},
                    {"threshold": 220.0, "operator": ">", "weight": 12},
                ]
            },
            tie_law=[
                "largest-weighted-marginal-rung-utility",
                "largest-individual-strict-gt-200-count",
                "largest-discovery-mean-score",
                "ascending-lineup-id",
            ],
            description="Tail-focused marginal utility above 200/210/220.",
        ),
        _strategy(
            ordinal=3,
            strategy_id="mean-score-v1",
            method="rank-mean-score-v1",
            entry_budget=budget,
            parameters={},
            tie_law=[
                "largest-discovery-mean-score",
                "largest-individual-strict-gt-200-count",
                "ascending-lineup-id",
            ],
            description="Highest discovery-world mean score with stable ties.",
        ),
    ]


def validate_retrieval_strategy(
    value: object, *, expected_ordinal: int, entry_budget: int,
) -> dict[str, object]:
    item = _mapping(value, label=f"strategy[{expected_ordinal}]")
    _keys(item, {
        "schema_version", "ordinal", "strategy_id", "method", "entry_budget",
        "parameters", "tie_law", "selection_inputs", "description",
        "strategy_sha256",
    }, label=f"strategy[{expected_ordinal}]")
    frozen = frozen_retrieval_strategies(entry_budget)
    if expected_ordinal >= len(frozen):
        raise CorpusRetrievalError("v1 has exactly four registered strategies")
    expected = frozen[expected_ordinal]
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        raise CorpusRetrievalError(f"strategy[{expected_ordinal}] differs from registry")
    return expected


_ROADMAP_LADDER_RUNGS: Final = (
    {"threshold": 200.0, "operator": ">", "weight": 1},
    {"threshold": 210.0, "operator": ">", "weight": 4},
    {"threshold": 220.0, "operator": ">", "weight": 12},
)


def frozen_retrieval_strategies_v2(
    entry_budget: int = DEFAULT_ENTRY_BUDGET,
) -> list[dict[str, object]]:
    """The v2 registry: the four v1 laws byte-identical plus three roadmap laws.

    Ordinals 0-3 are exactly the v1 bodies (same strategy_sha256), so every
    accepted v1 artifact remains valid under its own validator.  Ordinals
    4-6 realize the offseason roadmap's R2/R3/R5 retrieval directions as
    exact frozen laws: greedy expected book maximum, distinct-block-support
    scaled tail ladder, and weakest-block regime-robust ladder.
    """
    budget = _integer(entry_budget, label="entry budget", minimum=1)
    if budget != DEFAULT_ENTRY_BUDGET:
        raise CorpusRetrievalError("retrieval v2 requires an exact-80 budget")
    return frozen_retrieval_strategies(budget) + [
        _strategy(
            ordinal=4,
            strategy_id="expected-max-v1",
            method="greedy-expected-max-v1",
            entry_budget=budget,
            parameters={},
            tie_law=[
                "largest-marginal-expected-max-gain",
                "largest-individual-strict-gt-200-count",
                "largest-discovery-mean-score",
                "ascending-lineup-id",
            ],
            description=(
                "Greedy marginal gain in the expected discovery-world book "
                "maximum (submodular expected-max objective)."
            ),
        ),
        _strategy(
            ordinal=5,
            strategy_id="block-supported-tail-ladder-v1",
            method="greedy-block-supported-ladder-v1",
            entry_budget=budget,
            parameters={
                "rungs": [dict(rung) for rung in _ROADMAP_LADDER_RUNGS],
                "support_scaling": "distinct-discovery-block-count",
            },
            tie_law=[
                "largest-block-supported-marginal-rung-utility",
                "largest-individual-strict-gt-200-count",
                "largest-discovery-mean-score",
                "ascending-lineup-id",
            ],
            description=(
                "Tail ladder above 200/210/220 with each lineup's marginal "
                "coverage scaled by its distinct-discovery-block event "
                "support, discounting one-block tail accidents."
            ),
        ),
        _strategy(
            ordinal=6,
            strategy_id="regime-robust-ladder-v1",
            method="greedy-blockmin-ladder-v1",
            entry_budget=budget,
            parameters={"rungs": [dict(rung) for rung in _ROADMAP_LADDER_RUNGS]},
            tie_law=[
                "greatest-post-addition-leximin-block-utility-profile",
                "largest-individual-strict-gt-200-count",
                "largest-discovery-mean-score",
                "ascending-lineup-id",
            ],
            description=(
                "Regime-robust ladder that leximin-maximizes the "
                "ascending-sorted per-block weighted rung coverage profile "
                "so no single world family dominates the book."
            ),
        ),
    ]


def validate_retrieval_strategy_v2(
    value: object, *, expected_ordinal: int, entry_budget: int,
) -> dict[str, object]:
    item = _mapping(value, label=f"strategy[{expected_ordinal}]")
    _keys(item, {
        "schema_version", "ordinal", "strategy_id", "method", "entry_budget",
        "parameters", "tie_law", "selection_inputs", "description",
        "strategy_sha256",
    }, label=f"strategy[{expected_ordinal}]")
    frozen = frozen_retrieval_strategies_v2(entry_budget)
    if expected_ordinal >= len(frozen):
        raise CorpusRetrievalError("v2 has exactly seven registered strategies")
    expected = frozen[expected_ordinal]
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        raise CorpusRetrievalError(
            f"strategy[{expected_ordinal}] differs from v2 registry"
        )
    return expected


def _normalize_engine_release(value: object) -> dict[str, str]:
    item = _mapping(value, label="engine release")
    _keys(item, {
        "engine_version", "code_repository", "code_commit", "image_uri",
        "image_digest",
    }, label="engine release")
    commit = _string(item["code_commit"], label="code commit")
    digest = _string(item["image_digest"], label="image digest")
    image_uri = _string(item["image_uri"], label="image URI")
    if _COMMIT.fullmatch(commit) is None:
        raise CorpusRetrievalError("code commit must be lowercase 40/64 hex")
    if _DIGEST.fullmatch(digest) is None or not image_uri.endswith(f"@{digest}"):
        raise CorpusRetrievalError("engine image is not immutable")
    return {
        "engine_version": _identifier(item["engine_version"], label="engine version"),
        "code_repository": _string(item["code_repository"], label="repository"),
        "code_commit": commit,
        "image_uri": image_uri,
        "image_digest": digest,
    }


def _validate_manifest_identity(
    manifest: Mapping[str, object], identity: object, *, label: str,
) -> dict[str, object]:
    normalized = normalize_object_identity(identity, label=label)
    raw = canonical_json_bytes(manifest)
    if normalized["sha256"] != sha256(raw).hexdigest() or normalized["bytes"] != len(raw):
        raise CorpusRetrievalError(f"{label} does not bind manifest bytes")
    return normalized


def build_suite_manifest(
    *,
    run_id: str,
    created_at_utc: str,
    output_prefix: str,
    snapshot_manifest: Mapping[str, object],
    snapshot_manifest_identity: Mapping[str, object],
    entry_budget: int,
    engine_release: Mapping[str, object],
    strategies: Sequence[Mapping[str, object]] | None = None,
) -> dict[str, object]:
    """Build a one-snapshot, equal-budget retrieval suite."""
    snapshot = validate_snapshot_manifest(snapshot_manifest)
    snapshot_identity = _validate_manifest_identity(
        snapshot, snapshot_manifest_identity, label="snapshot manifest identity"
    )
    normalized_run_id = _identifier(run_id, label="run id")
    prefix = _gcs_uri(output_prefix, label="output prefix", prefix=True)
    if not prefix.endswith(f"/{normalized_run_id}/"):
        raise CorpusRetrievalError("output prefix must end in /<run_id>/")
    budget = _integer(entry_budget, label="entry budget", minimum=1)
    if budget != DEFAULT_ENTRY_BUDGET:
        raise CorpusRetrievalError("retrieval v1 requires an exact-80 budget")
    raw_strategies = list(strategies or frozen_retrieval_strategies(budget))
    if len(raw_strategies) != 4:
        raise CorpusRetrievalError("v1 suite must contain all four strategies")
    normalized_strategies = [
        validate_retrieval_strategy(row, expected_ordinal=index, entry_budget=budget)
        for index, row in enumerate(raw_strategies)
    ]
    tasks = [{
        "task_index": int(task["task_index"]),
        "task_id": str(task["task_id"]),
        "snapshot_task_sha256": str(task["task_sha256"]),
        "result_uri": f"{prefix}tasks/{int(task['task_index']):04d}/result.json",
    } for task in snapshot["tasks"]]
    body = {
        "schema_version": SUITE_SCHEMA,
        "run_id": normalized_run_id,
        "created_at_utc": _timestamp(created_at_utc, label="suite created_at"),
        "publication_mode": PUBLICATION_MODE,
        "output_prefix": prefix,
        "suite_manifest_uri": f"{prefix}governance/suite-manifest.json",
        "snapshot_manifest_identity": snapshot_identity,
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_manifest_sha256": snapshot["snapshot_manifest_sha256"],
        "entry_budget": budget,
        "discovery_blocks": list(DISCOVERY_BLOCKS),
        "heldout_blocks": list(HELDOUT_BLOCKS),
        "strategies": normalized_strategies,
        "engine_release": _normalize_engine_release(engine_release),
        "tasks": tasks,
        "licenses": {
            "analytics_only": True,
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
        },
    }
    return _self_hash(body, "suite_manifest_sha256")


def validate_suite_manifest(value: object) -> dict[str, object]:
    item = _mapping(value, label="suite manifest")
    _keys(item, {
        "schema_version", "run_id", "created_at_utc", "publication_mode",
        "output_prefix", "suite_manifest_uri", "snapshot_manifest_identity",
        "snapshot_id", "snapshot_manifest_sha256", "entry_budget",
        "discovery_blocks", "heldout_blocks", "strategies", "engine_release",
        "tasks", "licenses", "suite_manifest_sha256",
    }, label="suite manifest")
    if item["schema_version"] != SUITE_SCHEMA or item["publication_mode"] != PUBLICATION_MODE:
        raise CorpusRetrievalError("suite schema/publication mode differs")
    run_id = _identifier(item["run_id"], label="suite run id")
    prefix = _gcs_uri(item["output_prefix"], label="suite output prefix", prefix=True)
    if not prefix.endswith(f"/{run_id}/") or item["suite_manifest_uri"] != (
        f"{prefix}governance/suite-manifest.json"
    ):
        raise CorpusRetrievalError("suite deterministic namespace differs")
    budget = _integer(item["entry_budget"], label="suite entry budget", minimum=1)
    if budget != DEFAULT_ENTRY_BUDGET:
        raise CorpusRetrievalError("retrieval v1 requires an exact-80 budget")
    if list(item["discovery_blocks"]) != list(DISCOVERY_BLOCKS) or list(
        item["heldout_blocks"]
    ) != list(HELDOUT_BLOCKS):
        raise CorpusRetrievalError("suite discovery/heldout split differs")
    strategies = _sequence(item["strategies"], label="suite strategies")
    if len(strategies) != 4:
        raise CorpusRetrievalError("suite strategy count differs")
    normalized_strategies = [
        validate_retrieval_strategy(row, expected_ordinal=index, entry_budget=budget)
        for index, row in enumerate(strategies)
    ]
    snapshot_identity = normalize_object_identity(
        item["snapshot_manifest_identity"], label="snapshot manifest identity"
    )
    tasks_raw = _sequence(item["tasks"], label="suite tasks")
    tasks: list[dict[str, object]] = []
    for index, raw in enumerate(tasks_raw):
        task = _mapping(raw, label=f"suite task[{index}]")
        _keys(task, {
            "task_index", "task_id", "snapshot_task_sha256", "result_uri",
        }, label=f"suite task[{index}]")
        if _integer(task["task_index"], label="suite task index", minimum=0) != index:
            raise CorpusRetrievalError("suite tasks are not ordinal")
        tasks.append({
            "task_index": index,
            "task_id": _identifier(task["task_id"], label="suite task id"),
            "snapshot_task_sha256": _digest(
                task["snapshot_task_sha256"], label="snapshot task SHA"
            ),
            "result_uri": _gcs_uri(task["result_uri"], label="task result URI"),
        })
        if tasks[-1]["result_uri"] != f"{prefix}tasks/{index:04d}/result.json":
            raise CorpusRetrievalError("suite task result URI differs")
    licenses = _mapping(item["licenses"], label="suite licenses")
    expected_licenses = {
        "analytics_only": True,
        "corpus_fill_authority": False,
        "historical_outcome_read_authority": False,
        "live_money_policy_authority": False,
        "production_default_change_authority": False,
    }
    if dict(licenses) != expected_licenses:
        raise CorpusRetrievalError("suite licenses differ")
    normalized = {
        "schema_version": SUITE_SCHEMA,
        "run_id": run_id,
        "created_at_utc": _timestamp(item["created_at_utc"], label="created_at"),
        "publication_mode": PUBLICATION_MODE,
        "output_prefix": prefix,
        "suite_manifest_uri": f"{prefix}governance/suite-manifest.json",
        "snapshot_manifest_identity": snapshot_identity,
        "snapshot_id": _identifier(item["snapshot_id"], label="snapshot id"),
        "snapshot_manifest_sha256": _digest(
            item["snapshot_manifest_sha256"], label="snapshot manifest SHA"
        ),
        "entry_budget": budget,
        "discovery_blocks": list(DISCOVERY_BLOCKS),
        "heldout_blocks": list(HELDOUT_BLOCKS),
        "strategies": normalized_strategies,
        "engine_release": _normalize_engine_release(item["engine_release"]),
        "tasks": tasks,
        "licenses": expected_licenses,
    }
    normalized = _self_hash(normalized, "suite_manifest_sha256")
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        raise CorpusRetrievalError("suite manifest canonical replay differs")
    return normalized


def task_transport_binding(
    suite_manifest: Mapping[str, object], task_index: int,
) -> dict[str, object]:
    """Return the only fields transport needs to bind a worker invocation."""
    suite = validate_suite_manifest(suite_manifest)
    index = _integer(task_index, label="task index", minimum=0)
    if index >= len(suite["tasks"]):
        raise CorpusRetrievalError("task index is outside the suite")
    task = suite["tasks"][index]
    return {
        "output_prefix": suite["output_prefix"],
        "snapshot_manifest_identity": suite["snapshot_manifest_identity"],
        "task_index": index,
        "task_id": task["task_id"],
        "result_uri": task["result_uri"],
    }


def _array_descriptor(name: str, value: np.ndarray) -> dict[str, object]:
    array = np.ascontiguousarray(value)
    return {
        "name": name,
        "dtype": array.dtype.str,
        "shape": [int(size) for size in array.shape],
        "data_sha256": sha256(array.tobytes(order="C")).hexdigest(),
    }


def canonical_npz_bytes(
    arrays: Sequence[tuple[str, np.ndarray]],
) -> tuple[bytes, list[dict[str, object]]]:
    """Write deterministic compressed NPZ bytes with an exact member order."""
    if not arrays:
        raise CorpusRetrievalError("NPZ arrays are empty")
    names = [name for name, _ in arrays]
    if len(names) != len(set(names)) or any(_ID.fullmatch(name) is None for name in names):
        raise CorpusRetrievalError("NPZ member names are not unique identifiers")
    normalized: list[tuple[str, np.ndarray]] = []
    descriptors: list[dict[str, object]] = []
    for name, raw in arrays:
        array = np.ascontiguousarray(raw)
        if array.dtype.hasobject:
            raise CorpusRetrievalError("NPZ object arrays are forbidden")
        normalized.append((name, array))
        descriptors.append(_array_descriptor(name, array))
    buffer = BytesIO()
    np.savez_compressed(buffer, **{name: value for name, value in normalized})
    result = buffer.getvalue()
    # NumPy's writer is deterministic for identical ordered members in the
    # pinned runtime.  A second write makes that an enforced contract.
    repeat = BytesIO()
    np.savez_compressed(repeat, **{name: value for name, value in normalized})
    if result != repeat.getvalue():
        raise CorpusRetrievalError("NPZ writer is not byte deterministic")
    return result, descriptors


def _load_npz_arrays(
    raw: bytes,
    *,
    expected: Sequence[tuple[str, str, tuple[int | None, ...]]],
    label: str,
    require_canonical: bool,
) -> tuple[dict[str, np.ndarray], list[dict[str, object]]]:
    try:
        with np.load(BytesIO(raw), allow_pickle=False) as archive:
            if archive.files != [name for name, _, _ in expected]:
                raise CorpusRetrievalError(f"{label} NPZ member order differs")
            arrays = {name: np.asarray(archive[name]) for name, _, _ in expected}
    except CorpusRetrievalError:
        raise
    except Exception as exc:
        raise CorpusRetrievalError(f"{label} is not a safe NPZ") from exc
    for name, dtype, shape in expected:
        array = arrays[name]
        if array.dtype.str != dtype or array.ndim != len(shape):
            raise CorpusRetrievalError(f"{label}.{name} dtype/rank differs")
        if any(
            expected_size is not None and actual_size != expected_size
            for actual_size, expected_size in zip(array.shape, shape, strict=True)
        ):
            raise CorpusRetrievalError(f"{label}.{name} shape differs")
        if np.issubdtype(array.dtype, np.floating) and not np.isfinite(array).all():
            raise CorpusRetrievalError(f"{label}.{name} contains non-finite values")
    descriptors = [_array_descriptor(name, arrays[name]) for name, _, _ in expected]
    if require_canonical:
        rebuilt, _ = canonical_npz_bytes([(name, arrays[name]) for name, _, _ in expected])
        if rebuilt != raw:
            raise CorpusRetrievalError(f"{label} NPZ bytes are not canonical")
    return arrays, descriptors


def _load_source_artifact(
    raw: bytes, *, expected_candidates: int, expected_players: int,
) -> dict[str, np.ndarray]:
    """Decode one retained source artifact without importing producer code."""
    try:
        with np.load(BytesIO(raw), allow_pickle=False) as archive:
            if archive.files != [
                "cand_ix", "totals", "tail_line", "player_ids", "player_draws"
            ]:
                raise CorpusRetrievalError("source NPZ member order differs")
            arrays = {name: np.asarray(archive[name]) for name in archive.files}
    except CorpusRetrievalError:
        raise
    except Exception as exc:
        raise CorpusRetrievalError("source artifact is not a safe NPZ") from exc
    cand_ix = arrays["cand_ix"]
    totals = arrays["totals"]
    tail_line = arrays["tail_line"]
    player_ids = arrays["player_ids"]
    draws = arrays["player_draws"]
    if (
        cand_ix.dtype != np.dtype("int32")
        or cand_ix.shape != (expected_candidates,)
        or not np.array_equal(cand_ix, np.arange(expected_candidates, dtype=np.int32))
        or totals.dtype != np.dtype("float32")
        or totals.shape != (expected_candidates, WORLDS_PER_BLOCK)
        or tail_line.dtype != np.dtype("float32")
        or tail_line.shape != ()
        or float(tail_line) != 194.0
        or player_ids.ndim != 1
        or player_ids.shape != (expected_players,)
        or player_ids.dtype.kind != "U"
        or draws.dtype != np.dtype("float32")
        or draws.shape != (expected_players, WORLDS_PER_BLOCK)
        or not np.isfinite(totals).all()
        or not np.isfinite(draws).all()
    ):
        raise CorpusRetrievalError("source artifact array contract differs")
    ids = [str(value) for value in player_ids]
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        raise CorpusRetrievalError("source artifact player ids differ")
    return {
        "cand_ix": cand_ix,
        "totals": totals,
        "tail_line": tail_line,
        "player_ids": player_ids,
        "player_draws": draws,
    }


def _lineup_id(roster: Sequence[str]) -> str:
    return f"lineup:{sha256(canonical_json_bytes(sorted(roster))).hexdigest()}"


def _lineup_features(
    roster: Sequence[str], players: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    rows = [players[player_id] for player_id in roster]
    positions = Counter(str(row["pos"]) for row in rows)
    teams = Counter(str(row["team"]) for row in rows)
    games = Counter(str(row["game_id"]) for row in rows)
    qbs = [row for row in rows if row["pos"] == "QB"]
    qb_stack = 0
    bring_back = 0
    if len(qbs) == 1:
        qb = qbs[0]
        qb_team = str(qb["team"])
        qb_opp = str(qb["opp"])
        qb_stack = sum(
            1 for row in rows
            if row["id"] != qb["id"] and row["team"] == qb_team
            and row["pos"] in {"WR", "TE", "RB"}
        )
        bring_back = sum(
            1 for row in rows
            if row["team"] == qb_opp and row["pos"] in {"WR", "TE", "RB"}
        )
    return {
        "salary": int(sum(int(row["salary"]) for row in rows)),
        "projection": float(sum(float(row["proj"]) for row in rows)),
        "positions": dict(sorted(positions.items())),
        "teams": sorted(teams),
        "games": sorted(games),
        "team_player_counts": dict(sorted(teams.items())),
        "game_player_counts": dict(sorted(games.items())),
        "team_count": len(teams),
        "max_players_same_team": max(teams.values()),
        "game_count": len(games),
        "max_players_same_game": max(games.values()),
        "qb_stack_teammates": qb_stack,
        "bring_back_players": bring_back,
    }


def _prepare_task_sources(
    *,
    snapshot: Mapping[str, object],
    task_index: int,
    reader: ObjectReader,
) -> tuple[dict[str, object], list[dict[str, object]], np.ndarray, list[dict[str, object]]]:
    """Reopen exact sources and create the complete unique-lineup matrix."""
    task = snapshot["tasks"][task_index]
    candidate_raw = _read_exact(
        task["candidate_rows_object"], reader, label="candidate rows object"
    )
    candidate_body = validate_candidate_rows_object(
        parse_canonical_json_bytes(candidate_raw, label="candidate rows object")
    )
    player_raw = _read_exact(
        task["player_catalog_object"], reader, label="player catalog object"
    )
    player_body = validate_player_catalog_object(
        parse_canonical_json_bytes(player_raw, label="player catalog object")
    )
    if candidate_body["task_id"] != task["task_id"] or player_body["task_id"] != task["task_id"]:
        raise CorpusRetrievalError("task source bodies bind another task")
    if candidate_body["source_authority"] != player_body["source_authority"]:
        raise CorpusRetrievalError(
            "candidate and player inputs bind different source authorities"
        )
    query_authority_raw = _read_exact(
        candidate_body["source_authority"],
        reader,
        label="candidate/player source authority",
    )
    query_authority = validate_input_query_authority(
        parse_canonical_json_bytes(
            query_authority_raw, label="candidate/player source authority"
        )
    )
    _read_exact(
        snapshot["producer"]["producer_authority"],
        reader,
        label="snapshot producer authority",
    )
    if (
        query_authority["task_id"] != task["task_id"]
        or query_authority["candidate_query"]
        != candidate_body["source_query_receipt"]
        or query_authority["candidate_query"]["sql_sha256"]
        != candidate_body["source_sql_sha256"]
        or query_authority["candidate_query"]["row_count"]
        != len(candidate_body["rows"])
        or query_authority["candidate_query"]["normalized_rows_sha256"]
        != canonical_sha256(candidate_body["rows"])
        or query_authority["player_query"]["row_count"]
        != len(player_body["players"])
        or query_authority["player_query"]["normalized_rows_sha256"]
        != canonical_sha256(player_body["players"])
    ):
        raise CorpusRetrievalError("candidate/player query authority differs")
    season = int(task["slate"]["season"])
    week = int(task["slate"]["week"])
    rows_by_panel: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in candidate_body["rows"]:
        if int(row["season"]) != season or int(row["week"]) != week:
            raise CorpusRetrievalError("candidate row binds another slate")
        rows_by_panel[str(row["panel_id"])].append(row)
    players = {str(row["id"]): row for row in player_body["players"]}
    player_order = list(players)
    artifacts: list[dict[str, np.ndarray]] = []
    source_receipts: list[dict[str, object]] = []
    for block in task["world_blocks"]:
        panel_id = str(block["panel_id"])
        source_rows = sorted(rows_by_panel.get(panel_id, []), key=lambda row: int(row["cand_ix"]))
        expected_count = int(block["expected_candidate_count"])
        if [int(row["cand_ix"]) for row in source_rows] != list(range(expected_count)):
            raise CorpusRetrievalError(f"candidate rows do not cover {panel_id}")
        raw = _read_exact(
            block["artifact_object"], reader,
            label=f"world block {block['block_id']} artifact",
        )
        artifact = _load_source_artifact(
            raw,
            expected_candidates=expected_count,
            expected_players=int(block["expected_player_count"]),
        )
        artifact_ids = [str(value) for value in artifact["player_ids"]]
        if set(artifact_ids) != set(player_order):
            raise CorpusRetrievalError("world block/player catalog universes differ")
        artifacts.append(artifact)
        source_receipts.append({
            "ordinal": int(block["ordinal"]),
            "block_id": str(block["block_id"]),
            "panel_id": panel_id,
            "artifact_object": block["artifact_object"],
            "candidate_count": expected_count,
            "player_count": len(artifact_ids),
            "world_count": WORLDS_PER_BLOCK,
        })
    expected_panels = {str(block["panel_id"]) for block in task["world_blocks"]}
    if set(rows_by_panel) != expected_panels:
        raise CorpusRetrievalError("candidate rows contain missing/extra panels")

    memberships: dict[tuple[str, ...], list[dict[str, object]]] = defaultdict(list)
    for block, artifact in zip(task["world_blocks"], artifacts, strict=True):
        panel_rows = sorted(rows_by_panel[str(block["panel_id"])], key=lambda row: int(row["cand_ix"]))
        artifact_ids = set(str(value) for value in artifact["player_ids"])
        for row in panel_rows:
            roster_ordered = tuple(str(value) for value in row["players"])
            if set(roster_ordered) - artifact_ids:
                raise CorpusRetrievalError("candidate roster is outside world artifact")
            roster = tuple(sorted(roster_ordered))
            memberships[roster].append({
                "block_id": str(block["block_id"]),
                "panel_id": str(block["panel_id"]),
                "cand_ix": int(row["cand_ix"]),
                "tag": str(row["tag"]),
                "all_tags": list(row["all_tags"]),
            })
    roster_order = sorted(memberships)
    if len(roster_order) < DEFAULT_ENTRY_BUDGET:
        raise CorpusRetrievalError("unique lineup union is below exact-80")

    lineup_rows: list[dict[str, object]] = []
    score_blocks: list[np.ndarray] = []
    for block, artifact in zip(task["world_blocks"], artifacts, strict=True):
        by_id = {str(value): index for index, value in enumerate(artifact["player_ids"])}
        block_scores = np.stack([
            artifact["player_draws"][
                [by_id[player_id] for player_id in roster]
            ].sum(axis=0, dtype=np.float32)
            for roster in roster_order
        ]).astype(np.float32, copy=False)
        # Every native row is an independent reconstruction check.  The
        # producer's summation order can differ in its last float32 bit, so
        # the retained tolerance is explicit and small.
        lineup_index_by_roster = {
            roster: lineup_index for lineup_index, roster in enumerate(roster_order)
        }
        thresholds = (194.0, 200.0, 210.0, 220.0)
        for source_row in rows_by_panel[str(block["panel_id"])]:
            roster = tuple(sorted(str(value) for value in source_row["players"]))
            reconstructed = block_scores[lineup_index_by_roster[roster]]
            native = artifact["totals"][int(source_row["cand_ix"])]
            if not np.allclose(reconstructed, native, rtol=0, atol=1e-4):
                raise CorpusRetrievalError(
                    "reconstructed native candidate totals differ"
                )
            # The small retained numeric tolerance must never change any
            # registered selection/event boundary.
            for threshold in thresholds:
                bound = np.float32(threshold)
                if (
                    not np.array_equal(reconstructed >= bound, native >= bound)
                    or not np.array_equal(reconstructed > bound, native > bound)
                ):
                    raise CorpusRetrievalError(
                        "native reconstruction changes a registered threshold"
                    )
        score_blocks.append(block_scores)
    scores = np.ascontiguousarray(np.concatenate(score_blocks, axis=1), dtype=np.float32)
    if scores.shape != (len(roster_order), len(WORLD_BLOCKS) * WORLDS_PER_BLOCK):
        raise CorpusRetrievalError("complete lineup/world matrix shape differs")

    for lineup_index, roster in enumerate(roster_order):
        sources = sorted(
            memberships[roster],
            key=lambda row: (WORLD_BLOCKS.index(str(row["block_id"])), int(row["cand_ix"])),
        )
        tags = sorted({tag for source in sources for tag in source["all_tags"]})
        lineup_rows.append({
            "lineup_index": lineup_index,
            "lineup_id": _lineup_id(roster),
            "roster_player_ids": list(roster),
            "source_memberships": sources,
            "tags": tags,
            "features": _lineup_features(roster, players),
        })
    return task, lineup_rows, scores, source_receipts


def _support(scores: np.ndarray, threshold: float, operator: str) -> np.ndarray:
    if operator == ">":
        return scores > np.float32(threshold)
    if operator == ">=":
        return scores >= np.float32(threshold)
    raise CorpusRetrievalError(f"unsupported threshold operator {operator!r}")


def _discovery_lineup_view(
    lineup_rows: Sequence[Mapping[str, object]],
) -> tuple[list[int], list[dict[str, object]]]:
    """Project the full union onto R0--R3 identities and score-free lineage.

    A lineup first exposed by the R4 candidate panel is not eligible for
    discovery selection or producer insight.  For lineups independently
    present in R0--R3, R4 memberships and tags are also removed from the
    discovery view.  The returned indices continue to address the full score
    matrix.
    """
    eligible_indices: list[int] = []
    discovery_rows: list[dict[str, object]] = []
    discovery_blocks = set(DISCOVERY_BLOCKS)
    for row in lineup_rows:
        memberships = [
            dict(membership)
            for membership in row["source_memberships"]
            if str(membership["block_id"]) in discovery_blocks
        ]
        if not memberships:
            continue
        index = int(row["lineup_index"])
        eligible_indices.append(index)
        discovery_rows.append({
            **dict(row),
            "source_memberships": memberships,
            "tags": sorted({
                str(tag)
                for membership in memberships
                for tag in membership["all_tags"]
            }),
        })
    if eligible_indices != sorted(eligible_indices) or len(eligible_indices) < (
        DEFAULT_ENTRY_BUDGET
    ):
        raise CorpusRetrievalError(
            "R0--R3 discovery lineup universe cannot satisfy exact-80"
        )
    return eligible_indices, discovery_rows


def _select_coverage(
    scores: np.ndarray,
    *,
    budget: int,
    threshold: float,
    operator: str,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    clears = _support(scores, threshold, operator)
    counts = clears.sum(axis=1, dtype=np.int64)
    means = scores.mean(axis=1, dtype=np.float64)
    covered = np.zeros(scores.shape[1], dtype=bool)
    remaining = set(range(scores.shape[0]))
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < budget and remaining:
        ranked = sorted(
            remaining,
            key=lambda index: (
                -int(np.count_nonzero(clears[index] & ~covered)),
                -int(counts[index]),
                -float(means[index]),
                lineup_ids[index],
            ),
        )
        best = ranked[0]
        gain = int(np.count_nonzero(clears[best] & ~covered))
        if gain == 0:
            break
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": gain,
            "discovery_primary_event_count": int(counts[best]),
            "discovery_mean_score": float(means[best]),
        })
        covered |= clears[best]
        remaining.remove(best)
    fill = sorted(
        remaining,
        key=lambda index: (-int(counts[index]), -float(means[index]), lineup_ids[index]),
    )
    for best in fill[: budget - len(selected)]:
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": 0,
            "discovery_primary_event_count": int(counts[best]),
            "discovery_mean_score": float(means[best]),
        })
    return selected, trace


def _select_ladder(
    scores: np.ndarray,
    *,
    budget: int,
    rungs: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    rung_masks = [
        _support(scores, float(rung["threshold"]), str(rung["operator"]))
        for rung in rungs
    ]
    weights = [int(rung["weight"]) for rung in rungs]
    if any(weight <= 0 for weight in weights):
        raise CorpusRetrievalError("ladder weights must be positive integers")
    means = scores.mean(axis=1, dtype=np.float64)
    primary_counts = _support(
        scores, PRIMARY_EVENT_THRESHOLD, PRIMARY_EVENT_OPERATOR
    ).sum(axis=1, dtype=np.int64)
    covered = [np.zeros(scores.shape[1], dtype=bool) for _ in rungs]
    remaining = set(range(scores.shape[0]))
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < budget and remaining:
        utilities = {
            index: sum(
                weight * int(np.count_nonzero(mask[index] & ~seen))
                for weight, mask, seen in zip(weights, rung_masks, covered, strict=True)
            )
            for index in remaining
        }
        best = sorted(
            remaining,
            key=lambda index: (
                -utilities[index],
                -int(primary_counts[index]),
                -float(means[index]),
                lineup_ids[index],
            ),
        )[0]
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": int(utilities[best]),
            "discovery_primary_event_count": int(primary_counts[best]),
            "discovery_mean_score": float(means[best]),
        })
        for mask, seen in zip(rung_masks, covered, strict=True):
            seen |= mask[best]
        remaining.remove(best)
    return selected, trace


def _select_mean(
    scores: np.ndarray,
    *,
    budget: int,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    means = scores.mean(axis=1, dtype=np.float64)
    primary_counts = _support(
        scores, PRIMARY_EVENT_THRESHOLD, PRIMARY_EVENT_OPERATOR
    ).sum(axis=1, dtype=np.int64)
    selected = sorted(
        range(scores.shape[0]),
        key=lambda index: (-float(means[index]), -int(primary_counts[index]), lineup_ids[index]),
    )[:budget]
    trace = [{
        "selection_rank": rank,
        "lineup_index": index,
        "lineup_id": lineup_ids[index],
        "marginal_utility": float(means[index]),
        "discovery_primary_event_count": int(primary_counts[index]),
        "discovery_mean_score": float(means[index]),
    } for rank, index in enumerate(selected)]
    return selected, trace


def _discovery_block_view(scores: np.ndarray) -> tuple[int, int]:
    """Return (block count, worlds per block) for a discovery score matrix."""
    if scores.ndim != 2 or scores.shape[1] % WORLDS_PER_BLOCK != 0:
        raise CorpusRetrievalError(
            "discovery scores are not whole world blocks"
        )
    blocks = scores.shape[1] // WORLDS_PER_BLOCK
    if blocks < 2:
        raise CorpusRetrievalError(
            "block-aware selection requires at least two discovery blocks"
        )
    return blocks, WORLDS_PER_BLOCK


def _select_expected_max(
    scores: np.ndarray,
    *,
    budget: int,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    """Greedy marginal gain in the expected book maximum across worlds.

    E[max over the book] is monotone submodular in the selected set, so the
    deterministic greedy build is the principled construction.  Marginal
    gains are exact float64 means of per-world improvements.
    """
    values = scores.astype(np.float64)
    means = values.mean(axis=1)
    primary_counts = _support(
        scores, PRIMARY_EVENT_THRESHOLD, PRIMARY_EVENT_OPERATOR
    ).sum(axis=1, dtype=np.int64)
    current: np.ndarray | None = None
    remaining = set(range(scores.shape[0]))
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < budget and remaining:
        order = sorted(remaining)
        rows = np.asarray(order, dtype=np.int64)
        if current is None:
            gains = means[rows]
        else:
            gains = np.maximum(values[rows] - current, 0.0).mean(axis=1)
        gain_by_index = {
            index: float(gain) for index, gain in zip(order, gains)
        }
        best = sorted(
            order,
            key=lambda index: (
                -gain_by_index[index],
                -int(primary_counts[index]),
                -float(means[index]),
                lineup_ids[index],
            ),
        )[0]
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": gain_by_index[best],
            "discovery_primary_event_count": int(primary_counts[best]),
            "discovery_mean_score": float(means[best]),
        })
        current = (
            values[best].copy() if current is None
            else np.maximum(current, values[best])
        )
        remaining.remove(best)
    return selected, trace


def _select_block_supported_ladder(
    scores: np.ndarray,
    *,
    budget: int,
    rungs: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    """Tail-ladder coverage scaled by each lineup's distinct-block support.

    A lineup's marginal new-world count at each rung is multiplied by the
    number of distinct discovery blocks in which that lineup has at least
    one rung event.  One-block wonders keep a quarter of their raw credit;
    lineups whose tail appears in every block keep full credit.  This is the
    frozen, exact-integer realization of "shrunk cross-block support, not
    raw event counts".
    """
    blocks, per_block = _discovery_block_view(scores)
    rung_masks = [
        _support(scores, float(rung["threshold"]), str(rung["operator"]))
        for rung in rungs
    ]
    weights = [int(rung["weight"]) for rung in rungs]
    if any(weight <= 0 for weight in weights):
        raise CorpusRetrievalError("ladder weights must be positive integers")
    support_factors = [
        mask.reshape(scores.shape[0], blocks, per_block)
        .any(axis=2)
        .sum(axis=1, dtype=np.int64)
        for mask in rung_masks
    ]
    means = scores.mean(axis=1, dtype=np.float64)
    primary_counts = _support(
        scores, PRIMARY_EVENT_THRESHOLD, PRIMARY_EVENT_OPERATOR
    ).sum(axis=1, dtype=np.int64)
    covered = [np.zeros(scores.shape[1], dtype=bool) for _ in rungs]
    remaining = set(range(scores.shape[0]))
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < budget and remaining:
        utilities = {
            index: sum(
                weight
                * int(support[index])
                * int(np.count_nonzero(mask[index] & ~seen))
                for weight, support, mask, seen in zip(
                    weights, support_factors, rung_masks, covered, strict=True
                )
            )
            for index in remaining
        }
        best = sorted(
            remaining,
            key=lambda index: (
                -utilities[index],
                -int(primary_counts[index]),
                -float(means[index]),
                lineup_ids[index],
            ),
        )[0]
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": int(utilities[best]),
            "discovery_primary_event_count": int(primary_counts[best]),
            "discovery_mean_score": float(means[best]),
        })
        for mask, seen in zip(rung_masks, covered, strict=True):
            seen |= mask[best]
        remaining.remove(best)
    return selected, trace


def _select_blockmin_ladder(
    scores: np.ndarray,
    *,
    budget: int,
    rungs: Sequence[Mapping[str, object]],
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    """Regime-robust ladder: leximin over per-block covered utility.

    Each step picks the lineup whose addition gives the lexicographically
    greatest ascending-sorted profile of per-discovery-block weighted rung
    coverage.  Leximin subsumes maximin and stays discriminative while some
    blocks are still empty, so one rare world family cannot dominate the
    book and new regimes are opened before existing ones are deepened.
    """
    blocks, per_block = _discovery_block_view(scores)
    rung_masks = [
        _support(scores, float(rung["threshold"]), str(rung["operator"]))
        for rung in rungs
    ]
    weights = [int(rung["weight"]) for rung in rungs]
    if any(weight <= 0 for weight in weights):
        raise CorpusRetrievalError("ladder weights must be positive integers")
    means = scores.mean(axis=1, dtype=np.float64)
    primary_counts = _support(
        scores, PRIMARY_EVENT_THRESHOLD, PRIMARY_EVENT_OPERATOR
    ).sum(axis=1, dtype=np.int64)
    covered = [np.zeros(scores.shape[1], dtype=bool) for _ in rungs]
    block_utilities = np.zeros(blocks, dtype=np.int64)
    remaining = set(range(scores.shape[0]))
    selected: list[int] = []
    trace: list[dict[str, object]] = []
    while len(selected) < budget and remaining:
        order = sorted(remaining)
        rows = np.asarray(order, dtype=np.int64)
        added = np.zeros((len(order), blocks), dtype=np.int64)
        for weight, mask, seen in zip(
            weights, rung_masks, covered, strict=True
        ):
            fresh = mask[rows] & ~seen
            added += weight * fresh.reshape(
                len(order), blocks, per_block
            ).sum(axis=2, dtype=np.int64)
        after = block_utilities[None, :] + added
        leximin_key = {
            index: tuple(
                -int(value) for value in np.sort(after[position])
            )
            for position, index in enumerate(order)
        }
        best = sorted(
            order,
            key=lambda index: (
                leximin_key[index],
                -int(primary_counts[index]),
                -float(means[index]),
                lineup_ids[index],
            ),
        )[0]
        best_position = order.index(best)
        selected.append(best)
        trace.append({
            "selection_rank": len(selected) - 1,
            "lineup_index": best,
            "lineup_id": lineup_ids[best],
            "marginal_utility": int(added[best_position].sum()),
            "discovery_primary_event_count": int(primary_counts[best]),
            "discovery_mean_score": float(means[best]),
        })
        block_utilities = block_utilities + added[best_position]
        for mask, seen in zip(rung_masks, covered, strict=True):
            seen |= mask[best]
        remaining.remove(best)
    return selected, trace


def _run_strategy(
    strategy: Mapping[str, object],
    *,
    discovery_scores: np.ndarray,
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    budget = int(strategy["entry_budget"])
    method = str(strategy["method"])
    parameters = strategy["parameters"]
    if method == "greedy-threshold-coverage-v1":
        return _select_coverage(
            discovery_scores,
            budget=budget,
            threshold=float(parameters["threshold"]),
            operator=str(parameters["operator"]),
            lineup_ids=lineup_ids,
        )
    if method == "greedy-tail-ladder-v1":
        return _select_ladder(
            discovery_scores,
            budget=budget,
            rungs=parameters["rungs"],
            lineup_ids=lineup_ids,
        )
    if method == "rank-mean-score-v1":
        return _select_mean(
            discovery_scores, budget=budget, lineup_ids=lineup_ids
        )
    if method == "greedy-expected-max-v1":
        return _select_expected_max(
            discovery_scores, budget=budget, lineup_ids=lineup_ids
        )
    if method == "greedy-block-supported-ladder-v1":
        return _select_block_supported_ladder(
            discovery_scores,
            budget=budget,
            rungs=parameters["rungs"],
            lineup_ids=lineup_ids,
        )
    if method == "greedy-blockmin-ladder-v1":
        return _select_blockmin_ladder(
            discovery_scores,
            budget=budget,
            rungs=parameters["rungs"],
            lineup_ids=lineup_ids,
        )
    raise CorpusRetrievalError(f"unregistered retrieval method {method!r}")


def _run_discovery_strategy(
    strategy: Mapping[str, object],
    *,
    full_scores: np.ndarray,
    discovery_indices: Sequence[int],
    lineup_ids: Sequence[str],
) -> tuple[list[int], list[dict[str, object]]]:
    """Run one law through the exact heldout-safe local/global index seam."""
    indices = [int(value) for value in discovery_indices]
    if (
        full_scores.ndim != 2
        or full_scores.shape[0] != len(lineup_ids)
        or full_scores.shape[1] != len(WORLD_BLOCKS) * WORLDS_PER_BLOCK
        or len(indices) < DEFAULT_ENTRY_BUDGET
        or indices != sorted(set(indices))
        or indices[0] < 0
        or indices[-1] >= full_scores.shape[0]
    ):
        raise CorpusRetrievalError("discovery strategy input coverage differs")
    discovery_stop = len(DISCOVERY_BLOCKS) * WORLDS_PER_BLOCK
    index_array = np.asarray(indices, dtype=np.int32)
    eligible_scores = full_scores[index_array, :discovery_stop]
    eligible_ids = [lineup_ids[index] for index in indices]
    selected_local, trace_local = _run_strategy(
        strategy,
        discovery_scores=eligible_scores,
        lineup_ids=eligible_ids,
    )
    selected = [indices[value] for value in selected_local]
    trace = [{
        **row,
        "lineup_index": indices[int(row["lineup_index"])],
    } for row in trace_local]
    return selected, trace


def _score_summary(scores: np.ndarray) -> dict[str, object]:
    if scores.ndim != 2 or scores.shape[0] == 0 or scores.shape[1] == 0:
        raise CorpusRetrievalError("score summary requires a nonempty matrix")
    world_best = scores.max(axis=0)
    primary = scores > np.float32(PRIMARY_EVENT_THRESHOLD)
    return {
        "lineup_count": int(scores.shape[0]),
        "world_count": int(scores.shape[1]),
        "lineup_world_count": int(scores.size),
        "strict_gt_200_event_count": int(np.count_nonzero(primary)),
        "lineups_with_strict_gt_200": int(np.count_nonzero(primary.any(axis=1))),
        "worlds_with_any_strict_gt_200": int(np.count_nonzero(primary.any(axis=0))),
        "lineup_world_event_rate": float(np.count_nonzero(primary) / scores.size),
        "portfolio_world_best_mean": float(world_best.mean(dtype=np.float64)),
        "portfolio_world_best_max": float(world_best.max()),
        "portfolio_worlds_ge_194": int(np.count_nonzero(world_best >= np.float32(194.0))),
        "portfolio_worlds_gt_200": int(np.count_nonzero(world_best > np.float32(200.0))),
        "portfolio_worlds_gt_210": int(np.count_nonzero(world_best > np.float32(210.0))),
        "portfolio_worlds_gt_220": int(np.count_nonzero(world_best > np.float32(220.0))),
    }


def _split_metrics(scores: np.ndarray, selected: Sequence[int]) -> dict[str, object]:
    picked = scores[np.asarray(selected, dtype=np.int32)]
    discovery_stop = len(DISCOVERY_BLOCKS) * WORLDS_PER_BLOCK
    return {
        "discovery_r0_r3": _score_summary(picked[:, :discovery_stop]),
        "heldout_r4": _score_summary(picked[:, discovery_stop:]),
        "all_r0_r4_descriptive": _score_summary(picked),
    }


def _build_enrichment(
    *, lineup_rows: Sequence[Mapping[str, object]], scores: np.ndarray,
    analysis_scope: str, world_blocks: Sequence[str],
) -> dict[str, object]:
    scope = _identifier(analysis_scope, label="enrichment analysis scope")
    blocks = [
        _string(value, label="enrichment world block")
        for value in world_blocks
    ]
    expected_scope = (
        "discovery-r0-r3"
        if blocks == list(DISCOVERY_BLOCKS)
        else "all-r0-r4-descriptive"
        if blocks == list(WORLD_BLOCKS)
        else ""
    )
    if (
        not expected_scope
        or scope != expected_scope
        or scores.ndim != 2
        or scores.shape[0] != len(lineup_rows)
        or scores.shape[1] != len(blocks) * WORLDS_PER_BLOCK
    ):
        raise CorpusRetrievalError("enrichment world scope differs")
    event_counts = (scores > np.float32(PRIMARY_EVENT_THRESHOLD)).sum(
        axis=1, dtype=np.int64
    )
    worlds = scores.shape[1]
    total_events = int(event_counts.sum())
    global_rate = total_events / scores.size

    player_lineups: dict[str, list[int]] = defaultdict(list)
    pair_lineups: dict[tuple[str, str], list[int]] = defaultdict(list)
    tag_lineups: dict[str, list[int]] = defaultdict(list)
    stack_lineups: dict[str, list[int]] = defaultdict(list)
    team_lineups: dict[str, list[int]] = defaultdict(list)
    team_pair_lineups: dict[tuple[str, str], list[int]] = defaultdict(list)
    game_lineups: dict[str, list[int]] = defaultdict(list)
    for local_index, row in enumerate(lineup_rows):
        roster = [str(value) for value in row["roster_player_ids"]]
        for player_id in roster:
            player_lineups[player_id].append(local_index)
        for left, right in combinations(roster, 2):
            pair_lineups[(left, right)].append(local_index)
        for tag in row["tags"]:
            tag_lineups[str(tag)].append(local_index)
        features = row["features"]
        signature = (
            f"qb-stack:{features['qb_stack_teammates']}|"
            f"bring-back:{features['bring_back_players']}|"
            f"games:{features['game_count']}"
        )
        stack_lineups[signature].append(local_index)
        teams = [str(value) for value in features["teams"]]
        games = [str(value) for value in features["games"]]
        for team in teams:
            team_lineups[team].append(local_index)
        for left, right in combinations(teams, 2):
            team_pair_lineups[(left, right)].append(local_index)
        for game in games:
            game_lineups[game].append(local_index)

    def rows_for(groups: Mapping[object, Sequence[int]], *, key_name: str) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for key, indices_raw in groups.items():
            indices = sorted(set(int(value) for value in indices_raw))
            lineup_support = len(indices)
            opportunity_count = lineup_support * worlds
            event_count = int(event_counts[indices].sum())
            rate = event_count / opportunity_count
            result.append({
                key_name: list(key) if isinstance(key, tuple) else str(key),
                "lineup_support": lineup_support,
                "lineup_world_support": opportunity_count,
                "strict_gt_200_event_count": event_count,
                "strict_gt_200_event_rate": rate,
                "enrichment_vs_all_lineups": rate / global_rate if global_rate else 0.0,
                "minimum_support_qualified": (
                    lineup_support >= MIN_ENRICHMENT_LINEUP_SUPPORT
                ),
            })
        result.sort(key=lambda row: canonical_json_bytes(row[key_name]))
        return result

    body = {
        "schema_version": ENRICHMENT_SCHEMA,
        "analysis_scope": scope,
        "world_blocks": blocks,
        "heldout_worlds_used": blocks == list(WORLD_BLOCKS),
        "primary_event": {
            "operator": PRIMARY_EVENT_OPERATOR,
            "threshold": PRIMARY_EVENT_THRESHOLD,
        },
        "lineup_count": len(lineup_rows),
        "world_count": worlds,
        "global_event_count": total_events,
        "global_event_rate": global_rate,
        "minimum_lineup_support": MIN_ENRICHMENT_LINEUP_SUPPORT,
        "players": rows_for(player_lineups, key_name="player_id"),
        "pairs": rows_for(pair_lineups, key_name="player_ids"),
        "tags": rows_for(tag_lineups, key_name="tag"),
        "stack_signatures": rows_for(stack_lineups, key_name="stack_signature"),
        "teams": rows_for(team_lineups, key_name="team"),
        "team_pairs": rows_for(team_pair_lineups, key_name="teams"),
        "games": rows_for(game_lineups, key_name="game_id"),
    }
    return _self_hash(body, "enrichment_sha256")


def _build_redundancy(
    *, lineup_rows: Sequence[Mapping[str, object]], scores: np.ndarray,
) -> dict[str, object]:
    if (
        scores.ndim != 2
        or scores.shape[0] != len(lineup_rows)
        or scores.shape[1] != len(WORLD_BLOCKS) * WORLDS_PER_BLOCK
    ):
        raise CorpusRetrievalError("redundancy requires the full R0--R4 matrix")
    rosters = [set(str(value) for value in row["roster_player_ids"]) for row in lineup_rows]
    lineup_ids = [str(row["lineup_id"]) for row in lineup_rows]
    candidates = []
    for first, second in combinations(range(len(rosters)), 2):
        if lineup_ids[first] <= lineup_ids[second]:
            left, right = first, second
        else:
            left, right = second, first
        candidates.append((
            -len(rosters[left] & rosters[right]),
            lineup_ids[left], lineup_ids[right], left, right,
        ))
    candidates.sort()
    retained = candidates[: min(MAX_REDUNDANCY_PAIRS, len(candidates))]
    event = scores > np.float32(PRIMARY_EVENT_THRESHOLD)
    means = scores.mean(axis=1, dtype=np.float64)
    # Keep peak memory bounded: never materialize a second float64 copy of the
    # complete lineup/world matrix merely to obtain row norms.
    centered_norms = np.asarray([
        float(np.linalg.norm(scores[index].astype(np.float64) - means[index]))
        for index in range(scores.shape[0])
    ])
    score_vector_groups: dict[str, list[int]] = defaultdict(list)
    for index in range(scores.shape[0]):
        raw = np.ascontiguousarray(scores[index], dtype="<f4").tobytes(order="C")
        score_vector_groups[sha256(raw).hexdigest()].append(index)
    exact_duplicate_groups = [{
        "score_vector_sha256": digest,
        "lineup_indices": indices,
        "lineup_ids": [lineup_ids[index] for index in indices],
    } for digest, indices in sorted(score_vector_groups.items()) if len(indices) > 1]
    pairs: list[dict[str, object]] = []
    for neg_overlap, left_id, right_id, left, right in retained:
        left_centered = scores[left].astype(np.float64) - means[left]
        right_centered = scores[right].astype(np.float64) - means[right]
        denominator = centered_norms[left] * centered_norms[right]
        correlation = (
            float(np.dot(left_centered, right_centered) / denominator)
            if denominator > 0 else 0.0
        )
        intersection = int(np.count_nonzero(event[left] & event[right]))
        union = int(np.count_nonzero(event[left] | event[right]))
        pairs.append({
            "left_lineup_index": left,
            "right_lineup_index": right,
            "left_lineup_id": left_id,
            "right_lineup_id": right_id,
            "shared_player_count": -neg_overlap,
            "pearson_score_correlation": correlation,
            "exact_score_vector_duplicate": bool(
                np.array_equal(scores[left], scores[right])
            ),
            "strict_gt_200_event_intersection": intersection,
            "strict_gt_200_event_union": union,
            "strict_gt_200_event_jaccard": intersection / union if union else 0.0,
        })
    body = {
        "schema_version": REDUNDANCY_SCHEMA,
        "analysis_scope": "all-r0-r4-descriptive",
        "world_blocks": list(WORLD_BLOCKS),
        "heldout_worlds_used": True,
        "selection_law": (
            "top high-overlap pairs by shared-player-count descending, then "
            "lineup IDs ascending; correlations are computed only after this prefilter"
        ),
        "correlation_scope": "retained-high-overlap-pairs-only",
        "pair_universe_count": len(candidates),
        "retained_pair_limit": MAX_REDUNDANCY_PAIRS,
        "retained_pair_count": len(pairs),
        "exact_duplicate_score_vector_groups": exact_duplicate_groups,
        "pairs": pairs,
    }
    return _self_hash(body, "redundancy_sha256")


def _redundancy_semantic_replay_equal(
    published: object, rebuilt: object,
) -> bool:
    """Compare redundancy evidence across BLAS implementations.

    The retained artifact and its self-hash remain byte-exact authorities.
    Recomputing a Pearson dot product on another CPU/BLAS implementation can
    differ in the final binary64 bit, so replay permits only that one scalar
    field to move by at most the declared absolute tolerance. Pair identity,
    order, overlap, event counts, duplicate flags, and every other field stay
    exact. A relative tolerance would make the allowance scale with content
    and is deliberately forbidden.
    """
    left = dict(_mapping(published, label="published redundancy replay"))
    right = dict(_mapping(rebuilt, label="rebuilt redundancy replay"))
    _validate_self_hash(left, "redundancy_sha256", label="published redundancy")
    _validate_self_hash(right, "redundancy_sha256", label="rebuilt redundancy")
    left.pop("redundancy_sha256", None)
    right.pop("redundancy_sha256", None)
    left_pairs = list(_sequence(
        left.pop("pairs", None), label="published redundancy pairs"
    ))
    right_pairs = list(_sequence(
        right.pop("pairs", None), label="rebuilt redundancy pairs"
    ))
    if (
        canonical_json_bytes(left) != canonical_json_bytes(right)
        or len(left_pairs) != len(right_pairs)
    ):
        return False
    pair_keys = {
        "left_lineup_index", "right_lineup_index", "left_lineup_id",
        "right_lineup_id", "shared_player_count",
        "pearson_score_correlation", "exact_score_vector_duplicate",
        "strict_gt_200_event_intersection", "strict_gt_200_event_union",
        "strict_gt_200_event_jaccard",
    }
    for index, (left_raw, right_raw) in enumerate(
        zip(left_pairs, right_pairs, strict=True)
    ):
        left_pair = dict(_mapping(
            left_raw, label=f"published redundancy pair[{index}]"
        ))
        right_pair = dict(_mapping(
            right_raw, label=f"rebuilt redundancy pair[{index}]"
        ))
        _keys(
            left_pair, pair_keys, label=f"published redundancy pair[{index}]"
        )
        _keys(
            right_pair, pair_keys, label=f"rebuilt redundancy pair[{index}]"
        )
        left_correlation = left_pair.pop("pearson_score_correlation")
        right_correlation = right_pair.pop("pearson_score_correlation")
        if canonical_json_bytes(left_pair) != canonical_json_bytes(right_pair):
            return False
        if (
            type(left_correlation) is not float
            or type(right_correlation) is not float
            or not math.isfinite(left_correlation)
            or not math.isfinite(right_correlation)
            or abs(left_correlation) > 1.0 + REDUNDANCY_CORRELATION_REPLAY_ABS_TOLERANCE
            or abs(right_correlation) > 1.0 + REDUNDANCY_CORRELATION_REPLAY_ABS_TOLERANCE
            or not math.isclose(
                left_correlation,
                right_correlation,
                rel_tol=0.0,
                abs_tol=REDUNDANCY_CORRELATION_REPLAY_ABS_TOLERANCE,
            )
        ):
            return False
    return True


def _top_supported(
    rows: Sequence[Mapping[str, object]], *, key: str, limit: int = 20,
) -> list[dict[str, object]]:
    qualified = [row for row in rows if row["minimum_support_qualified"] is True]
    ordered = sorted(
        qualified,
        key=lambda row: (
            -float(row["enrichment_vs_all_lineups"]),
            -int(row["strict_gt_200_event_count"]),
            canonical_json_bytes(row[key]),
        ),
    )
    return [dict(row) for row in ordered[:limit]]


def _build_fill_insight(
    *, enrichment: Mapping[str, object],
    source_enrichment_object: Mapping[str, object],
    task_id: str,
) -> dict[str, object]:
    if (
        enrichment.get("analysis_scope") != "discovery-r0-r3"
        or enrichment.get("world_blocks") != list(DISCOVERY_BLOCKS)
        or enrichment.get("heldout_worlds_used") is not False
    ):
        raise CorpusRetrievalError(
            "fill insight requires heldout-free discovery enrichment"
        )
    source_identity = normalize_object_identity(
        source_enrichment_object, label="fill source enrichment object"
    )
    enrichment_raw = canonical_json_bytes(enrichment)
    if (
        source_identity["sha256"] != sha256(enrichment_raw).hexdigest()
        or source_identity["bytes"] != len(enrichment_raw)
    ):
        raise CorpusRetrievalError(
            "fill source enrichment identity does not bind enrichment bytes"
        )
    body = {
        "schema_version": FILL_INSIGHT_SCHEMA,
        "task_id": task_id,
        "knowledge_class": "retrieval-derived-observation",
        "primary_event": {
            "operator": PRIMARY_EVENT_OPERATOR,
            "threshold": PRIMARY_EVENT_THRESHOLD,
        },
        "source_enrichment_object": source_identity,
        "source_enrichment_sha256": enrichment["enrichment_sha256"],
        "source_analysis_scope": enrichment["analysis_scope"],
        "source_world_blocks": enrichment["world_blocks"],
        "heldout_worlds_used": False,
        "top_supported_players": _top_supported(
            enrichment["players"], key="player_id"
        ),
        "top_supported_pairs": _top_supported(
            enrichment["pairs"], key="player_ids"
        ),
        "top_supported_tags": _top_supported(enrichment["tags"], key="tag"),
        "top_supported_stack_signatures": _top_supported(
            enrichment["stack_signatures"], key="stack_signature"
        ),
        "top_supported_teams": _top_supported(enrichment["teams"], key="team"),
        "top_supported_team_pairs": _top_supported(
            enrichment["team_pairs"], key="teams"
        ),
        "top_supported_games": _top_supported(
            enrichment["games"], key="game_id"
        ),
        "interpretation": (
            "input for an independently governed corpus producer; not a fill instruction"
        ),
        "licenses": {
            "corpus_generation": False,
            "corpus_mutation": False,
            "live_policy_change": False,
        },
    }
    return _self_hash(body, "fill_insight_sha256")


def _sidecar_receipt(
    *,
    role: str,
    strategy_id: str,
    format_name: str,
    identity: Mapping[str, object],
    semantic: Mapping[str, object],
) -> dict[str, object]:
    return {
        "role": _identifier(role, label="sidecar role"),
        "strategy_id": strategy_id,
        "format": _identifier(format_name, label="sidecar format"),
        "object_identity": normalize_object_identity(identity, label="sidecar identity"),
        "semantic": dict(semantic),
    }


def _publish_json_sidecar(
    *,
    uri: str,
    role: str,
    body: Mapping[str, object],
    publisher: CreateOncePublisher,
    strategy_id: str = "",
) -> dict[str, object]:
    raw = canonical_json_bytes(body)
    identity = _publish_exact(
        uri=uri, raw=raw, media_type="application/json", publisher=publisher
    )
    return _sidecar_receipt(
        role=role,
        strategy_id=strategy_id,
        format_name="canonical-json-v1",
        identity=identity,
        semantic={
            "schema_version": body.get("schema_version", "none"),
            "canonical_json_sha256": sha256(raw).hexdigest(),
        },
    )


def _publish_npz_sidecar(
    *,
    uri: str,
    role: str,
    arrays: Sequence[tuple[str, np.ndarray]],
    publisher: CreateOncePublisher,
    strategy_id: str = "",
) -> tuple[dict[str, object], bytes]:
    raw, descriptors = canonical_npz_bytes(arrays)
    identity = _publish_exact(
        uri=uri, raw=raw, media_type="application/octet-stream", publisher=publisher
    )
    return _sidecar_receipt(
        role=role,
        strategy_id=strategy_id,
        format_name="canonical-compressed-npz-v1",
        identity=identity,
        semantic={
            "member_order": [name for name, _ in arrays],
            "arrays": descriptors,
            "npz_sha256": sha256(raw).hexdigest(),
        },
    ), raw


def _event_arrays(scores: np.ndarray) -> tuple[list[tuple[str, np.ndarray]], dict[str, object]]:
    event = scores > np.float32(PRIMARY_EVENT_THRESHOLD)
    global_world, lineup = np.nonzero(event.T)
    block = (global_world // WORLDS_PER_BLOCK).astype(np.uint8, copy=False)
    within = (global_world % WORLDS_PER_BLOCK).astype(np.int32, copy=False)
    lineup = lineup.astype(np.int32, copy=False)
    event_scores = scores[lineup, global_world].astype(np.float32, copy=False)
    arrays = [
        ("lineup_index", lineup),
        ("block_index", block),
        ("world_index", within),
        ("score", event_scores),
    ]
    counts_by_block = np.bincount(block.astype(np.int64), minlength=len(WORLD_BLOCKS))
    summary = {
        "operator": PRIMARY_EVENT_OPERATOR,
        "threshold": PRIMARY_EVENT_THRESHOLD,
        "sort_order": ["block_index", "world_index", "lineup_index"],
        "event_count": int(len(lineup)),
        "lineups_with_event": int(np.count_nonzero(event.any(axis=1))),
        "worlds_with_any_event": int(np.count_nonzero(event.any(axis=0))),
        "event_count_by_block": [int(value) for value in counts_by_block],
        "lineup_world_count": int(scores.size),
        "lineup_world_event_rate": float(len(lineup) / scores.size),
    }
    return arrays, summary


def _normalize_execution(
    value: object, *, suite: Mapping[str, object], task_index: int,
) -> dict[str, object]:
    item = _mapping(value, label="execution")
    _keys(item, {
        "execution_id", "execution_name", "task_index", "attempt", "retry_count",
        "mode", "code_commit", "image_uri", "image_digest",
    }, label="execution")
    index = _integer(item["task_index"], label="execution task index", minimum=0)
    if index != task_index:
        raise CorpusRetrievalError("execution task index differs")
    if (
        _integer(item["attempt"], label="execution attempt", minimum=0) != 0
        or _integer(item["retry_count"], label="execution retry count", minimum=0) != 0
    ):
        raise CorpusRetrievalError("retrieval v1 permits attempt=0/retry_count=0 only")
    mode = _identifier(item["mode"], label="execution mode")
    if mode not in {"local-real-smoke", "cloud-run-task"}:
        raise CorpusRetrievalError("execution mode differs")
    release = suite["engine_release"]
    normalized = {
        "execution_id": _identifier(item["execution_id"], label="execution id"),
        "execution_name": _string(item["execution_name"], label="execution name"),
        "task_index": index,
        "attempt": 0,
        "retry_count": 0,
        "mode": mode,
        "code_commit": _string(item["code_commit"], label="execution code commit"),
        "image_uri": _string(item["image_uri"], label="execution image URI"),
        "image_digest": _string(item["image_digest"], label="execution image digest"),
    }
    if any(
        normalized[key] != release[key]
        for key in ("code_commit", "image_uri", "image_digest")
    ):
        raise CorpusRetrievalError("execution code/image differs from suite release")
    return normalized


def _build_graph_projection(
    *,
    suite: Mapping[str, object],
    snapshot: Mapping[str, object],
    task: Mapping[str, object],
    lineup_rows: Sequence[Mapping[str, object]],
    lineup_event_counts: np.ndarray,
    strategy_rows: Sequence[Mapping[str, object]],
    artifact_sidecars: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    if any(row["role"] == "graph-projection" for row in artifact_sidecars):
        raise CorpusRetrievalError("graph projection cannot point to itself")
    nodes: list[dict[str, object]] = [
        {
            "id": f"snapshot:{snapshot['snapshot_id']}",
            "kind": "CorpusSnapshot",
            "properties": {"snapshot_manifest_sha256": snapshot["snapshot_manifest_sha256"]},
        },
        {
            "id": f"retrieval-task:{suite['run_id']}:{task['task_id']}",
            "kind": "RetrievalTask",
            "properties": {
                "run_id": suite["run_id"],
                "task_id": task["task_id"],
                "season": task["slate"]["season"],
                "week": task["slate"]["week"],
                "discovery_blocks": list(DISCOVERY_BLOCKS),
                "heldout_blocks": list(HELDOUT_BLOCKS),
                "heldout_content_is_descriptive_only": True,
            },
        },
    ]
    edges: list[dict[str, object]] = [{
        "from": f"retrieval-task:{suite['run_id']}:{task['task_id']}",
        "type": "USES_SNAPSHOT",
        "to": f"snapshot:{snapshot['snapshot_id']}",
        "properties": {},
    }]
    for lineup, event_count in zip(lineup_rows, lineup_event_counts, strict=True):
        lineup_node = f"candidate:{task['task_id']}:{lineup['lineup_id']}"
        discovery_membership_count = sum(
            1 for membership in lineup["source_memberships"]
            if str(membership["block_id"]) in DISCOVERY_BLOCKS
        )
        nodes.append({
            "id": lineup_node,
            "kind": "LineupCandidate",
            "properties": {
                "lineup_index": lineup["lineup_index"],
                "roster_player_ids": lineup["roster_player_ids"],
                "tags": lineup["tags"],
                "features": lineup["features"],
                "source_membership_count": len(lineup["source_memberships"]),
                "discovery_source_membership_count": discovery_membership_count,
                "discovery_eligible": discovery_membership_count > 0,
                "strict_gt_200_event_count_all_r0_r4_descriptive": int(event_count),
            },
        })
        edges.append({
            "from": f"retrieval-task:{suite['run_id']}:{task['task_id']}",
            "type": "CONTAINS_CANDIDATE",
            "to": lineup_node,
            "properties": {},
        })
        for membership in lineup["source_memberships"]:
            panel_node = f"population:{task['task_id']}:{membership['panel_id']}"
            edges.append({
                "from": lineup_node,
                "type": "MEMBER_OF_SOURCE_POPULATION",
                "to": panel_node,
                "properties": {
                    "block_id": membership["block_id"],
                    "cand_ix": membership["cand_ix"],
                    "tag": membership["tag"],
                },
            })
    for block in task["world_blocks"]:
        nodes.append({
            "id": f"population:{task['task_id']}:{block['panel_id']}",
            "kind": "CorpusPopulation",
            "properties": {"block_id": block["block_id"], "panel_id": block["panel_id"]},
        })
    result_nodes: dict[str, str] = {}
    for strategy_result in strategy_rows:
        strategy_id = str(strategy_result["strategy_id"])
        result_node = f"retrieval-result:{suite['run_id']}:{task['task_id']}:{strategy_id}"
        result_nodes[strategy_id] = result_node
        nodes.append({
            "id": result_node,
            "kind": "RetrievalStrategyResult",
            "properties": {
                "strategy_id": strategy_id,
                "strategy_sha256": strategy_result["strategy_sha256"],
                "entry_budget": suite["entry_budget"],
                "metrics": strategy_result["metrics"],
            },
        })
        edges.append({
            "from": result_node,
            "type": "RETRIEVES_FROM",
            "to": f"retrieval-task:{suite['run_id']}:{task['task_id']}",
            "properties": {},
        })
        for rank, lineup_index in enumerate(strategy_result["selected_lineup_indices"]):
            edges.append({
                "from": result_node,
                "type": "SELECTED",
                "to": (
                    f"candidate:{task['task_id']}:"
                    f"{lineup_rows[int(lineup_index)]['lineup_id']}"
                ),
                "properties": {"selection_rank": rank},
            })
    artifact_pointers: list[dict[str, object]] = []
    for sidecar in artifact_sidecars:
        role = str(sidecar["role"])
        strategy_id = str(sidecar["strategy_id"])
        artifact_node = (
            f"retrieval-artifact:{suite['run_id']}:{task['task_id']}:"
            f"{role}:{strategy_id or 'task'}"
        )
        if role in {"enrichment-discovery", "fill-insight"}:
            knowledge_scope = "discovery-r0-r3"
        elif role in {"strategy-selection", "strategy-selected-scores"}:
            knowledge_scope = "discovery-selected-with-r4-descriptive-evaluation"
        elif role == "unique-lineups":
            knowledge_scope = "candidate-identities-no-world-outcomes"
        else:
            knowledge_scope = "all-r0-r4-descriptive"
        pointer = {
            "role": role,
            "strategy_id": strategy_id,
            "format": sidecar["format"],
            "object_identity": sidecar["object_identity"],
            "semantic": sidecar["semantic"],
        }
        artifact_pointers.append(pointer)
        nodes.append({
            "id": artifact_node,
            "kind": "RetrievalArtifact",
            "properties": {
                **pointer,
                "knowledge_scope": knowledge_scope,
                "eligible_as_separately_governed_producer_input": (
                    role == "fill-insight"
                ),
            },
        })
        owner = result_nodes.get(
            strategy_id,
            f"retrieval-task:{suite['run_id']}:{task['task_id']}",
        )
        edges.append({
            "from": owner,
            "type": "HAS_ANALYTIC_ARTIFACT",
            "to": artifact_node,
            "properties": {},
        })
    nodes.sort(key=lambda row: str(row["id"]))
    edges.sort(key=lambda row: (
        str(row["from"]), str(row["type"]), str(row["to"]), canonical_json_bytes(row["properties"])
    ))
    body = {
        "schema_version": GRAPH_SCHEMA,
        "dedicated_analytical_graph_only": True,
        "authoritative_source": "create-once-sidecars-and-task-result",
        "large_bodies_are_pointers": True,
        "analytic_artifact_pointers": artifact_pointers,
        "nodes": nodes,
        "edges": edges,
        "licenses": {
            "decision_authority": False,
            "corpus_fill_authority": False,
            "corpus_producer_input_authority": False,
            "fill_insight_uses_discovery_blocks_only": True,
            "heldout_content_is_descriptive_only": True,
            "live_money_policy_authority": False,
        },
    }
    return _self_hash(body, "graph_projection_sha256")


def run_retrieval_task(
    *,
    suite_manifest: Mapping[str, object],
    suite_manifest_identity: Mapping[str, object],
    snapshot_manifest: Mapping[str, object],
    snapshot_manifest_identity: Mapping[str, object],
    task_index: int,
    execution: Mapping[str, object],
    read_object: ObjectReader,
    publish_create_once: CreateOncePublisher,
) -> dict[str, object]:
    """Run one complete task and publish its authority last.

    Returns exactly ``{"authority": ..., "object_identity": ...}``.
    """
    suite = validate_suite_manifest(suite_manifest)
    snapshot = validate_snapshot_manifest(snapshot_manifest)
    suite_identity = _validate_manifest_identity(
        suite, suite_manifest_identity, label="suite manifest identity"
    )
    snapshot_identity = _validate_manifest_identity(
        snapshot, snapshot_manifest_identity, label="snapshot manifest identity"
    )
    if suite["snapshot_manifest_identity"] != snapshot_identity or (
        suite["snapshot_id"] != snapshot["snapshot_id"]
        or suite["snapshot_manifest_sha256"] != snapshot["snapshot_manifest_sha256"]
    ):
        raise CorpusRetrievalError("suite does not bind the supplied snapshot")
    index = _integer(task_index, label="task index", minimum=0)
    if index >= len(suite["tasks"]) or index >= len(snapshot["tasks"]):
        raise CorpusRetrievalError("task index is outside suite/snapshot")
    suite_task = suite["tasks"][index]
    snapshot_task = snapshot["tasks"][index]
    if (
        suite_task["task_id"] != snapshot_task["task_id"]
        or suite_task["snapshot_task_sha256"] != snapshot_task["task_sha256"]
    ):
        raise CorpusRetrievalError("suite task does not bind snapshot task")
    normalized_execution = _normalize_execution(execution, suite=suite, task_index=index)
    task, lineup_rows, scores, source_receipts = _prepare_task_sources(
        snapshot=snapshot, task_index=index, reader=read_object
    )
    budget = int(suite["entry_budget"])
    if len(lineup_rows) < budget:
        raise CorpusRetrievalError("candidate union cannot satisfy exact budget")
    prefix = f"{suite['output_prefix']}tasks/{index:04d}/"
    sidecars: list[dict[str, object]] = []

    lineup_body = _self_hash({
        "schema_version": LINEUP_TABLE_SCHEMA,
        "task_id": task["task_id"],
        "lineup_count": len(lineup_rows),
        "roster_size": ROSTER_SIZE,
        "lineup_index_law": "canonical roster-player-id tuple ascending",
        "lineups": lineup_rows,
    }, "lineup_table_sha256")
    sidecars.append(_publish_json_sidecar(
        uri=f"{prefix}artifacts/unique-lineups.json",
        role="unique-lineups",
        body=lineup_body,
        publisher=publish_create_once,
    ))

    world_columns = scores.shape[1]
    full_score_arrays = [
        ("lineup_index", np.arange(len(lineup_rows), dtype=np.int32)),
        ("scores", scores),
        ("block_index", np.repeat(
            np.arange(len(WORLD_BLOCKS), dtype=np.uint8), WORLDS_PER_BLOCK
        )),
        ("world_index", np.tile(
            np.arange(WORLDS_PER_BLOCK, dtype=np.int32), len(WORLD_BLOCKS)
        )),
    ]
    matrix_receipt, _ = _publish_npz_sidecar(
        uri=f"{prefix}artifacts/unique-lineup-scores.npz",
        role="unique-lineup-scores",
        arrays=full_score_arrays,
        publisher=publish_create_once,
    )
    sidecars.append(matrix_receipt)

    event_arrays, event_summary = _event_arrays(scores)
    event_receipt, _ = _publish_npz_sidecar(
        uri=f"{prefix}artifacts/strict-gt-200-events.npz",
        role="strict-gt-200-events",
        arrays=event_arrays,
        publisher=publish_create_once,
    )
    event_receipt["semantic"] = {
        **event_receipt["semantic"],
        "event_summary": event_summary,
    }
    sidecars.append(event_receipt)

    discovery_stop = len(DISCOVERY_BLOCKS) * WORLDS_PER_BLOCK
    discovery_indices, discovery_lineup_rows = _discovery_lineup_view(lineup_rows)
    discovery_index_array = np.asarray(discovery_indices, dtype=np.int32)
    discovery_scores = scores[discovery_index_array, :discovery_stop]
    discovery_enrichment = _build_enrichment(
        lineup_rows=discovery_lineup_rows,
        scores=discovery_scores,
        analysis_scope="discovery-r0-r3",
        world_blocks=DISCOVERY_BLOCKS,
    )
    discovery_enrichment_receipt = _publish_json_sidecar(
        uri=f"{prefix}artifacts/enrichment-discovery-r0-r3.json",
        role="enrichment-discovery",
        body=discovery_enrichment,
        publisher=publish_create_once,
    )
    sidecars.append(discovery_enrichment_receipt)
    full_enrichment = _build_enrichment(
        lineup_rows=lineup_rows,
        scores=scores,
        analysis_scope="all-r0-r4-descriptive",
        world_blocks=WORLD_BLOCKS,
    )
    sidecars.append(_publish_json_sidecar(
        uri=f"{prefix}artifacts/enrichment-all-r0-r4.json",
        role="enrichment-all-worlds",
        body=full_enrichment,
        publisher=publish_create_once,
    ))
    redundancy = _build_redundancy(lineup_rows=lineup_rows, scores=scores)
    sidecars.append(_publish_json_sidecar(
        uri=f"{prefix}artifacts/redundancy-topk.json",
        role="redundancy-topk",
        body=redundancy,
        publisher=publish_create_once,
    ))
    fill_insight = _build_fill_insight(
        enrichment=discovery_enrichment,
        source_enrichment_object=discovery_enrichment_receipt["object_identity"],
        task_id=str(task["task_id"]),
    )
    sidecars.append(_publish_json_sidecar(
        uri=f"{prefix}artifacts/fill-insight.json",
        role="fill-insight",
        body=fill_insight,
        publisher=publish_create_once,
    ))

    lineup_ids = [str(row["lineup_id"]) for row in lineup_rows]
    strategy_results: list[dict[str, object]] = []
    for strategy in suite["strategies"]:
        ordinal = int(strategy["ordinal"])
        strategy_id = str(strategy["strategy_id"])
        selected, trace = _run_discovery_strategy(
            strategy,
            full_scores=scores,
            discovery_indices=discovery_indices,
            lineup_ids=lineup_ids,
        )
        if len(selected) != budget or len(set(selected)) != budget:
            raise CorpusRetrievalError("retrieval strategy did not return exact budget")
        selected_array = np.asarray(selected, dtype=np.int32)
        metrics = _split_metrics(scores, selected)
        selection_body = _self_hash({
            "schema_version": SELECTION_SCHEMA,
            "task_id": task["task_id"],
            "strategy": strategy,
            "selection_law": "R0--R3 discovery only; R4 held out",
            "entry_budget": budget,
            "selected_lineup_indices": selected,
            "selected_lineup_ids": [lineup_ids[value] for value in selected],
            "selected_lineups": [lineup_rows[value] for value in selected],
            "selection_trace": trace,
            "metrics": metrics,
        }, "selection_sha256")
        strategy_prefix = f"{prefix}strategies/{ordinal:02d}-{strategy_id}/"
        selection_receipt = _publish_json_sidecar(
            uri=f"{strategy_prefix}selection.json",
            role="strategy-selection",
            strategy_id=strategy_id,
            body=selection_body,
            publisher=publish_create_once,
        )
        sidecars.append(selection_receipt)
        score_receipt, _ = _publish_npz_sidecar(
            uri=f"{strategy_prefix}selected-scores.npz",
            role="strategy-selected-scores",
            strategy_id=strategy_id,
            arrays=[
                ("selection_rank", np.arange(budget, dtype=np.int32)),
                ("lineup_index", selected_array),
                ("scores", scores[selected_array]),
            ],
            publisher=publish_create_once,
        )
        sidecars.append(score_receipt)
        strategy_results.append({
            "ordinal": ordinal,
            "strategy_id": strategy_id,
            "strategy_sha256": strategy["strategy_sha256"],
            "entry_budget": budget,
            "selected_lineup_indices": selected,
            "selected_lineup_ids_sha256": canonical_sha256(
                [lineup_ids[value] for value in selected]
            ),
            "selection_object": selection_receipt["object_identity"],
            "selected_scores_object": score_receipt["object_identity"],
            "metrics": metrics,
        })

    lineup_event_counts = (scores > np.float32(PRIMARY_EVENT_THRESHOLD)).sum(
        axis=1, dtype=np.int64
    )
    graph = _build_graph_projection(
        suite=suite,
        snapshot=snapshot,
        task=task,
        lineup_rows=lineup_rows,
        lineup_event_counts=lineup_event_counts,
        strategy_rows=strategy_results,
        artifact_sidecars=sidecars,
    )
    graph_receipt = _publish_json_sidecar(
        uri=f"{prefix}graph-projection.json",
        role="graph-projection",
        body=graph,
        publisher=publish_create_once,
    )
    sidecars.append(graph_receipt)

    result_body = {
        "schema_version": TASK_RESULT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "suite_manifest_identity": suite_identity,
        "suite_manifest_sha256": suite["suite_manifest_sha256"],
        "snapshot_manifest_identity": snapshot_identity,
        "snapshot_manifest_sha256": snapshot["snapshot_manifest_sha256"],
        "run_id": suite["run_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "task_index": index,
        "task_id": task["task_id"],
        "snapshot_task_sha256": task["task_sha256"],
        "execution": normalized_execution,
        "coverage": {
            "source_block_count": len(WORLD_BLOCKS),
            "source_candidate_rows": sum(
                int(row["candidate_count"]) for row in source_receipts
            ),
            "unique_lineup_count": len(lineup_rows),
            "discovery_eligible_lineup_count": len(discovery_indices),
            "heldout_only_lineup_count": len(lineup_rows) - len(discovery_indices),
            "world_count": world_columns,
            "lineup_world_score_count": int(scores.size),
            "every_unique_lineup_scored_in_every_world": True,
            "strategy_count": len(strategy_results),
            "exact_budget_per_strategy": budget,
            "all_strategies_exact_budget": True,
        },
        "primary_event_summary": event_summary,
        "source_receipts": source_receipts,
        "sidecars": sidecars,
        "strategy_results": strategy_results,
        "graph_projection_object": graph_receipt["object_identity"],
        "fill_insight_object": next(
            row["object_identity"] for row in sidecars if row["role"] == "fill-insight"
        ),
        "licenses": {
            "analytics_authority": True,
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
        },
    }
    authority = _self_hash(result_body, "task_result_sha256")
    result_identity = _publish_exact(
        uri=str(suite_task["result_uri"]),
        raw=canonical_json_bytes(authority),
        media_type="application/json",
        publisher=publish_create_once,
    )
    return {"authority": authority, "object_identity": result_identity}


def _sidecar_map(
    value: object, *, suite: Mapping[str, object], task_index: int,
) -> tuple[list[dict[str, object]], dict[tuple[str, str], dict[str, object]]]:
    rows_raw = _sequence(value, label="task result sidecars")
    expected_order: list[tuple[str, str, str]] = [
        ("unique-lineups", "", "artifacts/unique-lineups.json"),
        ("unique-lineup-scores", "", "artifacts/unique-lineup-scores.npz"),
        ("strict-gt-200-events", "", "artifacts/strict-gt-200-events.npz"),
        (
            "enrichment-discovery", "",
            "artifacts/enrichment-discovery-r0-r3.json",
        ),
        (
            "enrichment-all-worlds", "",
            "artifacts/enrichment-all-r0-r4.json",
        ),
        ("redundancy-topk", "", "artifacts/redundancy-topk.json"),
        ("fill-insight", "", "artifacts/fill-insight.json"),
    ]
    for strategy in suite["strategies"]:
        ordinal = int(strategy["ordinal"])
        strategy_id = str(strategy["strategy_id"])
        relative = f"strategies/{ordinal:02d}-{strategy_id}/"
        expected_order.extend([
            ("strategy-selection", strategy_id, f"{relative}selection.json"),
            ("strategy-selected-scores", strategy_id, f"{relative}selected-scores.npz"),
        ])
    expected_order.append(("graph-projection", "", "graph-projection.json"))
    if len(rows_raw) != len(expected_order):
        raise CorpusRetrievalError("task sidecar coverage differs")
    prefix = f"{suite['output_prefix']}tasks/{task_index:04d}/"
    rows: list[dict[str, object]] = []
    by_key: dict[tuple[str, str], dict[str, object]] = {}
    seen_objects: set[tuple[object, ...]] = set()
    for offset, (raw, expected) in enumerate(zip(rows_raw, expected_order, strict=True)):
        row = _mapping(raw, label=f"sidecar[{offset}]")
        _keys(row, {
            "role", "strategy_id", "format", "object_identity", "semantic",
        }, label=f"sidecar[{offset}]")
        role = _identifier(row["role"], label="sidecar role")
        strategy_id = str(row["strategy_id"])
        format_name = _identifier(row["format"], label="sidecar format")
        if (role, strategy_id) != expected[:2]:
            raise CorpusRetrievalError("task sidecar order/role differs")
        expected_format = (
            "canonical-compressed-npz-v1"
            if expected[2].endswith(".npz") else "canonical-json-v1"
        )
        if format_name != expected_format:
            raise CorpusRetrievalError("task sidecar format differs")
        identity = normalize_object_identity(
            row["object_identity"], label=f"sidecar[{offset}] identity"
        )
        if identity["uri"] != f"{prefix}{expected[2]}":
            raise CorpusRetrievalError("task sidecar deterministic URI differs")
        object_key = tuple(identity[key] for key in ("uri", "generation", "sha256", "bytes"))
        if object_key in seen_objects:
            raise CorpusRetrievalError("task sidecar identities repeat")
        seen_objects.add(object_key)
        normalized = {
            "role": role,
            "strategy_id": strategy_id,
            "format": format_name,
            "object_identity": identity,
            "semantic": dict(_mapping(row["semantic"], label="sidecar semantic")),
        }
        rows.append(normalized)
        by_key[(role, strategy_id)] = normalized
    return rows, by_key


def _parse_json_sidecar(
    receipt: Mapping[str, object], reader: ObjectReader, *, label: str,
) -> dict[str, object]:
    raw = _read_exact(receipt["object_identity"], reader, label=label)
    value = parse_canonical_json_bytes(raw, label=label)
    return dict(_mapping(value, label=label))


def _validate_result_structure(
    *,
    published_result: object,
    suite: Mapping[str, object],
    suite_identity: Mapping[str, object],
    snapshot: Mapping[str, object],
    snapshot_identity: Mapping[str, object],
    reader: ObjectReader,
) -> tuple[dict[str, object], list[dict[str, object]], dict[tuple[str, str], dict[str, object]]]:
    published = _mapping(published_result, label="published task result")
    _keys(published, {"authority", "object_identity"}, label="published task result")
    authority = dict(_mapping(published["authority"], label="task result authority"))
    result_identity = normalize_object_identity(
        published["object_identity"], label="task result object identity"
    )
    raw_authority = canonical_json_bytes(authority)
    if (
        result_identity["sha256"] != sha256(raw_authority).hexdigest()
        or result_identity["bytes"] != len(raw_authority)
    ):
        raise CorpusRetrievalError("task result identity differs from authority")
    reopened = _read_exact(result_identity, reader, label="task result object")
    if reopened != raw_authority:
        raise CorpusRetrievalError("task result object differs from supplied authority")
    _keys(authority, {
        "schema_version", "publication_mode", "suite_manifest_identity",
        "suite_manifest_sha256", "snapshot_manifest_identity",
        "snapshot_manifest_sha256", "run_id", "snapshot_id", "task_index",
        "task_id", "snapshot_task_sha256", "execution", "coverage",
        "primary_event_summary", "source_receipts", "sidecars", "strategy_results",
        "graph_projection_object", "fill_insight_object", "licenses",
        "task_result_sha256",
    }, label="task result authority")
    if authority["schema_version"] != TASK_RESULT_SCHEMA or authority[
        "publication_mode"
    ] != PUBLICATION_MODE:
        raise CorpusRetrievalError("task result schema/publication mode differs")
    _validate_self_hash(authority, "task_result_sha256", label="task result")
    index = _integer(authority["task_index"], label="result task index", minimum=0)
    if index >= len(suite["tasks"]) or index >= len(snapshot["tasks"]):
        raise CorpusRetrievalError("result task index is outside manifests")
    suite_task = suite["tasks"][index]
    snapshot_task = snapshot["tasks"][index]
    if result_identity["uri"] != suite_task["result_uri"]:
        raise CorpusRetrievalError("task result object URI differs")
    expected_bindings = {
        "suite_manifest_identity": suite_identity,
        "suite_manifest_sha256": suite["suite_manifest_sha256"],
        "snapshot_manifest_identity": snapshot_identity,
        "snapshot_manifest_sha256": snapshot["snapshot_manifest_sha256"],
        "run_id": suite["run_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "task_id": suite_task["task_id"],
        "snapshot_task_sha256": snapshot_task["task_sha256"],
    }
    for field, expected in expected_bindings.items():
        if authority[field] != expected:
            raise CorpusRetrievalError(f"task result {field} binding differs")
    _normalize_execution(authority["execution"], suite=suite, task_index=index)
    sidecars, by_key = _sidecar_map(authority["sidecars"], suite=suite, task_index=index)
    if authority["graph_projection_object"] != by_key[("graph-projection", "")][
        "object_identity"
    ] or authority["fill_insight_object"] != by_key[("fill-insight", "")][
        "object_identity"
    ]:
        raise CorpusRetrievalError("task result named sidecar binding differs")
    return authority, sidecars, by_key


def validate_retrieval_task_result(
    *,
    published_result: Mapping[str, object],
    suite_manifest: Mapping[str, object],
    suite_manifest_identity: Mapping[str, object],
    snapshot_manifest: Mapping[str, object],
    snapshot_manifest_identity: Mapping[str, object],
    read_object: ObjectReader,
    replay: bool = True,
) -> dict[str, object]:
    """Reopen every retained sidecar and optionally replay source selection."""
    if type(replay) is not bool:
        raise CorpusRetrievalError("replay must be a literal Boolean")
    suite = validate_suite_manifest(suite_manifest)
    snapshot = validate_snapshot_manifest(snapshot_manifest)
    suite_identity = _validate_manifest_identity(
        suite, suite_manifest_identity, label="suite manifest identity"
    )
    snapshot_identity = _validate_manifest_identity(
        snapshot, snapshot_manifest_identity, label="snapshot manifest identity"
    )
    if suite["snapshot_manifest_identity"] != snapshot_identity:
        raise CorpusRetrievalError("suite snapshot identity differs")
    authority, sidecars, by_key = _validate_result_structure(
        published_result=published_result,
        suite=suite,
        suite_identity=suite_identity,
        snapshot=snapshot,
        snapshot_identity=snapshot_identity,
        reader=read_object,
    )
    index = int(authority["task_index"])
    coverage = _mapping(authority["coverage"], label="task result coverage")
    _keys(coverage, {
        "source_block_count", "source_candidate_rows", "unique_lineup_count",
        "discovery_eligible_lineup_count", "heldout_only_lineup_count",
        "world_count", "lineup_world_score_count",
        "every_unique_lineup_scored_in_every_world", "strategy_count",
        "exact_budget_per_strategy", "all_strategies_exact_budget",
    }, label="task result coverage")
    lineup_count = _integer(
        coverage["unique_lineup_count"], label="unique lineup count", minimum=1
    )
    discovery_lineup_count = _integer(
        coverage["discovery_eligible_lineup_count"],
        label="discovery eligible lineup count",
        minimum=DEFAULT_ENTRY_BUDGET,
    )
    heldout_only_lineup_count = _integer(
        coverage["heldout_only_lineup_count"],
        label="heldout-only lineup count",
        minimum=0,
    )
    world_count = _integer(coverage["world_count"], label="world count", minimum=1)
    if (
        coverage["source_block_count"] != len(WORLD_BLOCKS)
        or discovery_lineup_count + heldout_only_lineup_count != lineup_count
        or world_count != len(WORLD_BLOCKS) * WORLDS_PER_BLOCK
        or coverage["lineup_world_score_count"] != lineup_count * world_count
        or coverage["every_unique_lineup_scored_in_every_world"] is not True
        or coverage["strategy_count"] != 4
        or coverage["exact_budget_per_strategy"] != suite["entry_budget"]
        or coverage["all_strategies_exact_budget"] is not True
    ):
        raise CorpusRetrievalError("task result score/budget coverage differs")
    snapshot_task = snapshot["tasks"][index]
    expected_source_receipts = [{
        "ordinal": int(block["ordinal"]),
        "block_id": str(block["block_id"]),
        "panel_id": str(block["panel_id"]),
        "artifact_object": block["artifact_object"],
        "candidate_count": int(block["expected_candidate_count"]),
        "player_count": int(block["expected_player_count"]),
        "world_count": int(block["expected_world_count"]),
    } for block in snapshot_task["world_blocks"]]
    if (
        authority["source_receipts"] != expected_source_receipts
        or coverage["source_candidate_rows"] != sum(
            row["candidate_count"] for row in expected_source_receipts
        )
    ):
        raise CorpusRetrievalError("task result source coverage differs")

    lineup_body = _parse_json_sidecar(
        by_key[("unique-lineups", "")], read_object, label="unique lineup table"
    )
    if (
        lineup_body.get("schema_version") != LINEUP_TABLE_SCHEMA
        or lineup_body.get("lineup_count") != lineup_count
        or lineup_body.get("roster_size") != ROSTER_SIZE
        or by_key[("unique-lineups", "")]["semantic"] != {
            "schema_version": LINEUP_TABLE_SCHEMA,
            "canonical_json_sha256": by_key[("unique-lineups", "")][
                "object_identity"
            ]["sha256"],
        }
    ):
        raise CorpusRetrievalError("unique lineup table contract differs")
    _validate_self_hash(lineup_body, "lineup_table_sha256", label="lineup table")
    lineup_rows = list(_sequence(lineup_body["lineups"], label="lineup rows"))
    if [row["lineup_index"] for row in lineup_rows] != list(range(lineup_count)):
        raise CorpusRetrievalError("lineup table indices differ")
    lineup_ids = [str(row["lineup_id"]) for row in lineup_rows]
    if len(lineup_ids) != len(set(lineup_ids)):
        raise CorpusRetrievalError("lineup table IDs repeat")
    discovery_indices, discovery_lineup_rows = _discovery_lineup_view(lineup_rows)
    if len(discovery_indices) != discovery_lineup_count:
        raise CorpusRetrievalError("discovery lineup coverage differs")

    matrix_raw = _read_exact(
        by_key[("unique-lineup-scores", "")]["object_identity"],
        read_object,
        label="unique lineup score matrix",
    )
    matrix_arrays, matrix_descriptors = _load_npz_arrays(
        matrix_raw,
        expected=[
            ("lineup_index", "<i4", (lineup_count,)),
            ("scores", "<f4", (lineup_count, world_count)),
            ("block_index", "|u1", (world_count,)),
            ("world_index", "<i4", (world_count,)),
        ],
        label="unique lineup score matrix",
        require_canonical=True,
    )
    if (
        not np.array_equal(matrix_arrays["lineup_index"], np.arange(lineup_count, dtype=np.int32))
        or not np.array_equal(matrix_arrays["block_index"], np.repeat(
            np.arange(len(WORLD_BLOCKS), dtype=np.uint8), WORLDS_PER_BLOCK
        ))
        or not np.array_equal(matrix_arrays["world_index"], np.tile(
            np.arange(WORLDS_PER_BLOCK, dtype=np.int32), len(WORLD_BLOCKS)
        ))
        or by_key[("unique-lineup-scores", "")]["semantic"] != {
            "member_order": [
                "lineup_index", "scores", "block_index", "world_index"
            ],
            "arrays": matrix_descriptors,
            "npz_sha256": by_key[("unique-lineup-scores", "")][
                "object_identity"
            ]["sha256"],
        }
    ):
        raise CorpusRetrievalError("unique lineup matrix semantic receipt differs")
    scores = matrix_arrays["scores"]

    event_summary = dict(_mapping(
        authority["primary_event_summary"], label="primary event summary"
    ))
    event_count = _integer(event_summary["event_count"], label="event count", minimum=0)
    event_raw = _read_exact(
        by_key[("strict-gt-200-events", "")]["object_identity"],
        read_object,
        label="strict event artifact",
    )
    event_arrays, event_descriptors = _load_npz_arrays(
        event_raw,
        expected=[
            ("lineup_index", "<i4", (event_count,)),
            ("block_index", "|u1", (event_count,)),
            ("world_index", "<i4", (event_count,)),
            ("score", "<f4", (event_count,)),
        ],
        label="strict event artifact",
        require_canonical=True,
    )
    event_semantic = by_key[("strict-gt-200-events", "")]["semantic"]
    if (
        event_semantic != {
            "member_order": [
                "lineup_index", "block_index", "world_index", "score"
            ],
            "arrays": event_descriptors,
            "npz_sha256": by_key[("strict-gt-200-events", "")][
                "object_identity"
            ]["sha256"],
            "event_summary": event_summary,
        }
    ):
        raise CorpusRetrievalError("strict event semantic receipt differs")
    expected_event_arrays, expected_event_summary = _event_arrays(scores)
    if event_summary != expected_event_summary or any(
        not np.array_equal(event_arrays[name], array)
        for name, array in expected_event_arrays
    ):
        raise CorpusRetrievalError("strict >200 event artifact differs from full matrix")

    discovery_enrichment = _parse_json_sidecar(
        by_key[("enrichment-discovery", "")],
        read_object,
        label="discovery enrichment",
    )
    full_enrichment = _parse_json_sidecar(
        by_key[("enrichment-all-worlds", "")],
        read_object,
        label="all-world descriptive enrichment",
    )
    redundancy = _parse_json_sidecar(
        by_key[("redundancy-topk", "")], read_object, label="redundancy"
    )
    fill_insight = _parse_json_sidecar(
        by_key[("fill-insight", "")], read_object, label="fill insight"
    )
    graph = _parse_json_sidecar(
        by_key[("graph-projection", "")], read_object, label="graph projection"
    )
    for body, schema, hash_field, label, sidecar_key in (
        (
            discovery_enrichment,
            ENRICHMENT_SCHEMA,
            "enrichment_sha256",
            "discovery enrichment",
            ("enrichment-discovery", ""),
        ),
        (
            full_enrichment,
            ENRICHMENT_SCHEMA,
            "enrichment_sha256",
            "all-world descriptive enrichment",
            ("enrichment-all-worlds", ""),
        ),
        (
            redundancy, REDUNDANCY_SCHEMA, "redundancy_sha256", "redundancy",
            ("redundancy-topk", ""),
        ),
        (
            fill_insight, FILL_INSIGHT_SCHEMA, "fill_insight_sha256",
            "fill insight", ("fill-insight", ""),
        ),
        (
            graph, GRAPH_SCHEMA, "graph_projection_sha256", "graph projection",
            ("graph-projection", ""),
        ),
    ):
        if body.get("schema_version") != schema:
            raise CorpusRetrievalError(f"{label} schema differs")
        _validate_self_hash(body, hash_field, label=label)
        if by_key[sidecar_key]["semantic"] != {
            "schema_version": schema,
            "canonical_json_sha256": by_key[sidecar_key]["object_identity"][
                "sha256"
            ],
        }:
            raise CorpusRetrievalError(f"{label} semantic receipt differs")

    strategy_values = _sequence(
        authority["strategy_results"], label="strategy results"
    )
    if len(strategy_values) != len(suite["strategies"]):
        raise CorpusRetrievalError("strategy result coverage differs")
    normalized_strategy_results: list[dict[str, object]] = []
    selection_bodies: dict[str, dict[str, object]] = {}
    for strategy, raw_result in zip(suite["strategies"], strategy_values, strict=True):
        result = dict(_mapping(raw_result, label="strategy result"))
        _keys(result, {
            "ordinal", "strategy_id", "strategy_sha256", "entry_budget",
            "selected_lineup_indices", "selected_lineup_ids_sha256",
            "selection_object", "selected_scores_object", "metrics",
        }, label="strategy result")
        strategy_id = str(strategy["strategy_id"])
        selected = [
            _integer(value, label="selected lineup index", minimum=0)
            for value in _sequence(
                result["selected_lineup_indices"], label="selected indices"
            )
        ]
        if (
            result["ordinal"] != strategy["ordinal"]
            or result["strategy_id"] != strategy_id
            or result["strategy_sha256"] != strategy["strategy_sha256"]
            or result["entry_budget"] != suite["entry_budget"]
            or len(selected) != suite["entry_budget"]
            or len(set(selected)) != len(selected)
            or any(value >= lineup_count for value in selected)
        ):
            raise CorpusRetrievalError("strategy result identity/budget differs")
        if result["selected_lineup_ids_sha256"] != canonical_sha256(
            [lineup_ids[value] for value in selected]
        ):
            raise CorpusRetrievalError("selected lineup identity SHA differs")
        selection_receipt = by_key[("strategy-selection", strategy_id)]
        selected_score_receipt = by_key[("strategy-selected-scores", strategy_id)]
        if (
            result["selection_object"] != selection_receipt["object_identity"]
            or result["selected_scores_object"] != selected_score_receipt["object_identity"]
        ):
            raise CorpusRetrievalError("strategy sidecar bindings differ")
        selection = _parse_json_sidecar(
            selection_receipt, read_object, label=f"selection {strategy_id}"
        )
        _keys(selection, {
            "schema_version", "task_id", "strategy", "selection_law",
            "entry_budget", "selected_lineup_indices", "selected_lineup_ids",
            "selected_lineups", "selection_trace", "metrics",
            "selection_sha256",
        }, label=f"selection {strategy_id}")
        if selection.get("schema_version") != SELECTION_SCHEMA:
            raise CorpusRetrievalError("selection schema differs")
        _validate_self_hash(selection, "selection_sha256", label="selection")
        if (
            selection_receipt["semantic"] != {
                "schema_version": SELECTION_SCHEMA,
                "canonical_json_sha256": selection_receipt["object_identity"][
                    "sha256"
                ],
            }
            or selection["task_id"] != snapshot_task["task_id"]
            or selection["strategy"] != strategy
            or selection["selection_law"] != "R0--R3 discovery only; R4 held out"
            or selection["entry_budget"] != suite["entry_budget"]
            or selection["selected_lineup_indices"] != selected
            or selection["selected_lineup_ids"] != [lineup_ids[value] for value in selected]
            or selection["selected_lineups"] != [lineup_rows[value] for value in selected]
            or selection["metrics"] != result["metrics"]
            or result["metrics"] != _split_metrics(scores, selected)
        ):
            raise CorpusRetrievalError("selection body differs from strategy result")
        selection_bodies[strategy_id] = selection
        selected_raw = _read_exact(
            selected_score_receipt["object_identity"],
            read_object,
            label=f"selected scores {strategy_id}",
        )
        selected_arrays, selected_descriptors = _load_npz_arrays(
            selected_raw,
            expected=[
                ("selection_rank", "<i4", (suite["entry_budget"],)),
                ("lineup_index", "<i4", (suite["entry_budget"],)),
                ("scores", "<f4", (suite["entry_budget"], world_count)),
            ],
            label=f"selected scores {strategy_id}",
            require_canonical=True,
        )
        if (
            selected_score_receipt["semantic"] != {
                "member_order": ["selection_rank", "lineup_index", "scores"],
                "arrays": selected_descriptors,
                "npz_sha256": selected_score_receipt["object_identity"]["sha256"],
            }
            or not np.array_equal(
                selected_arrays["selection_rank"],
                np.arange(suite["entry_budget"], dtype=np.int32),
            )
            or not np.array_equal(selected_arrays["lineup_index"], np.asarray(selected, dtype=np.int32))
            or not np.array_equal(selected_arrays["scores"], scores[selected])
        ):
            raise CorpusRetrievalError("selected score artifact differs")
        normalized_strategy_results.append(result)

    # Rebuild every analytical JSON artifact from the retained canonical score
    # matrix.  This is mandatory even when callers skip the more expensive
    # source-artifact replay.
    discovery_stop = len(DISCOVERY_BLOCKS) * WORLDS_PER_BLOCK
    discovery_index_array = np.asarray(discovery_indices, dtype=np.int32)
    discovery_scores = scores[discovery_index_array, :discovery_stop]
    rebuilt_discovery_enrichment = _build_enrichment(
        lineup_rows=discovery_lineup_rows,
        scores=discovery_scores,
        analysis_scope="discovery-r0-r3",
        world_blocks=DISCOVERY_BLOCKS,
    )
    rebuilt_full_enrichment = _build_enrichment(
        lineup_rows=lineup_rows,
        scores=scores,
        analysis_scope="all-r0-r4-descriptive",
        world_blocks=WORLD_BLOCKS,
    )
    rebuilt_redundancy = _build_redundancy(
        lineup_rows=lineup_rows, scores=scores
    )
    rebuilt_fill = _build_fill_insight(
        enrichment=rebuilt_discovery_enrichment,
        source_enrichment_object=by_key[("enrichment-discovery", "")][
            "object_identity"
        ],
        task_id=str(snapshot_task["task_id"]),
    )
    rebuilt_graph = _build_graph_projection(
        suite=suite,
        snapshot=snapshot,
        task=snapshot_task,
        lineup_rows=lineup_rows,
        lineup_event_counts=(
            scores > np.float32(PRIMARY_EVENT_THRESHOLD)
        ).sum(axis=1, dtype=np.int64),
        strategy_rows=normalized_strategy_results,
        artifact_sidecars=[
            row for row in sidecars if row["role"] != "graph-projection"
        ],
    )
    if any(
        canonical_json_bytes(left) != canonical_json_bytes(right)
        for left, right in (
            (discovery_enrichment, rebuilt_discovery_enrichment),
            (full_enrichment, rebuilt_full_enrichment),
            (fill_insight, rebuilt_fill),
            (graph, rebuilt_graph),
        )
    ) or not _redundancy_semantic_replay_equal(
        redundancy, rebuilt_redundancy
    ):
        raise CorpusRetrievalError("analytics or graph semantic replay differs")

    for strategy, result in zip(
        suite["strategies"], normalized_strategy_results, strict=True
    ):
        strategy_id = str(strategy["strategy_id"])
        selected, trace = _run_discovery_strategy(
            strategy,
            full_scores=scores,
            discovery_indices=discovery_indices,
            lineup_ids=lineup_ids,
        )
        if (
            selected != result["selected_lineup_indices"]
            or trace != selection_bodies[strategy_id]["selection_trace"]
            or _split_metrics(scores, selected) != result["metrics"]
        ):
            raise CorpusRetrievalError("strategy selection/trace replay differs")

    if replay:
        _, replay_lineups, replay_scores, source_receipts = _prepare_task_sources(
            snapshot=snapshot, task_index=index, reader=read_object
        )
        if (
            canonical_json_bytes(replay_lineups) != canonical_json_bytes(lineup_rows)
            or not np.array_equal(replay_scores, scores)
        ):
            raise CorpusRetrievalError(
                "source replay differs from retained corpus matrix"
            )
        if authority["source_receipts"] != source_receipts:
            raise CorpusRetrievalError("source receipt replay differs")

    expected_licenses = {
        "analytics_authority": True,
        "corpus_fill_authority": False,
        "historical_outcome_read_authority": False,
        "live_money_policy_authority": False,
        "production_default_change_authority": False,
    }
    if authority["licenses"] != expected_licenses:
        raise CorpusRetrievalError("task result licenses differ")
    return authority


def build_retrieval_batch_completion(
    *,
    suite_manifest: Mapping[str, object],
    suite_manifest_identity: Mapping[str, object],
    snapshot_manifest: Mapping[str, object],
    snapshot_manifest_identity: Mapping[str, object],
    published_results: Sequence[Mapping[str, object]],
    read_object: ObjectReader,
) -> dict[str, object]:
    """Build a compact completion only after exact task coverage validates."""
    suite = validate_suite_manifest(suite_manifest)
    snapshot = validate_snapshot_manifest(snapshot_manifest)
    suite_identity = _validate_manifest_identity(
        suite, suite_manifest_identity, label="suite manifest identity"
    )
    snapshot_identity = _validate_manifest_identity(
        snapshot, snapshot_manifest_identity, label="snapshot manifest identity"
    )
    if len(published_results) != len(suite["tasks"]):
        raise CorpusRetrievalError("published results do not cover every task")
    bindings: list[dict[str, object]] = []
    for index, published in enumerate(published_results):
        authority = validate_retrieval_task_result(
            published_result=published,
            suite_manifest=suite,
            suite_manifest_identity=suite_identity,
            snapshot_manifest=snapshot,
            snapshot_manifest_identity=snapshot_identity,
            read_object=read_object,
            replay=False,
        )
        if authority["task_index"] != index:
            raise CorpusRetrievalError("published results are not in task order")
        identity = normalize_object_identity(
            published["object_identity"], label="published result identity"
        )
        bindings.append({
            "task_index": index,
            "task_id": authority["task_id"],
            "snapshot_task_sha256": authority["snapshot_task_sha256"],
            "task_result_sha256": authority["task_result_sha256"],
            "task_result_object": identity,
            "unique_lineup_count": authority["coverage"]["unique_lineup_count"],
            "lineup_world_score_count": authority["coverage"]["lineup_world_score_count"],
            "strategy_count": authority["coverage"]["strategy_count"],
            "exact_budget_per_strategy": authority["coverage"]["exact_budget_per_strategy"],
        })
    body = {
        "schema_version": COMPLETION_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "suite_manifest_identity": suite_identity,
        "suite_manifest_sha256": suite["suite_manifest_sha256"],
        "snapshot_manifest_identity": snapshot_identity,
        "snapshot_manifest_sha256": snapshot["snapshot_manifest_sha256"],
        "run_id": suite["run_id"],
        "snapshot_id": snapshot["snapshot_id"],
        "coverage": {
            "task_count": len(bindings),
            "strategy_count": len(suite["strategies"]),
            "task_strategy_cell_count": len(bindings) * len(suite["strategies"]),
            "all_tasks_complete": True,
            "all_strategies_equal_budget": True,
        },
        "task_results": bindings,
        "licenses": {
            "analytical_graph_projection_ready": True,
            "corpus_fill_authority": False,
            "historical_outcome_read_authority": False,
            "live_money_policy_authority": False,
            "production_default_change_authority": False,
        },
    }
    return _self_hash(body, "batch_completion_sha256")


def validate_retrieval_batch_completion(
    value: object,
    *,
    suite_manifest: Mapping[str, object],
    suite_manifest_identity: Mapping[str, object],
    snapshot_manifest: Mapping[str, object],
    snapshot_manifest_identity: Mapping[str, object],
    published_results: Sequence[Mapping[str, object]],
    read_object: ObjectReader,
) -> dict[str, object]:
    item = _mapping(value, label="retrieval batch completion")
    _keys(item, {
        "schema_version", "publication_mode", "suite_manifest_identity",
        "suite_manifest_sha256", "snapshot_manifest_identity",
        "snapshot_manifest_sha256", "run_id", "snapshot_id", "coverage",
        "task_results", "licenses", "batch_completion_sha256",
    }, label="retrieval batch completion")
    if item["schema_version"] != COMPLETION_SCHEMA:
        raise CorpusRetrievalError("completion schema differs")
    _validate_self_hash(item, "batch_completion_sha256", label="completion")
    rebuilt = build_retrieval_batch_completion(
        suite_manifest=suite_manifest,
        suite_manifest_identity=suite_manifest_identity,
        snapshot_manifest=snapshot_manifest,
        snapshot_manifest_identity=snapshot_manifest_identity,
        published_results=published_results,
        read_object=read_object,
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(item):
        raise CorpusRetrievalError("completion replay differs")
    return rebuilt


__all__ = [
    "CANDIDATE_ROWS_SCHEMA",
    "COMPLETION_SCHEMA",
    "CorpusRetrievalError",
    "DEFAULT_ENTRY_BUDGET",
    "DISCOVERY_BLOCKS",
    "HELDOUT_BLOCKS",
    "PLAYER_CATALOG_SCHEMA",
    "SNAPSHOT_SCHEMA",
    "STRATEGY_SCHEMA",
    "SUITE_SCHEMA",
    "TASK_RESULT_SCHEMA",
    "WORLD_BLOCKS",
    "build_candidate_rows_object",
    "build_player_catalog_object",
    "build_retrieval_batch_completion",
    "build_snapshot_manifest",
    "build_suite_manifest",
    "canonical_json_bytes",
    "canonical_npz_bytes",
    "canonical_sha256",
    "frozen_retrieval_strategies",
    "normalize_candidate_query_rows",
    "normalize_player_query_rows",
    "object_identity_for_bytes",
    "run_retrieval_task",
    "task_transport_binding",
    "validate_candidate_rows_object",
    "validate_player_catalog_object",
    "validate_retrieval_batch_completion",
    "validate_retrieval_task_result",
    "validate_snapshot_manifest",
    "validate_suite_manifest",
]
