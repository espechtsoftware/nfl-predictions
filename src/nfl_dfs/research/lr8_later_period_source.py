"""Real, outcome-blind LR8 2023--2025 source and construction boundary.

This module is intentionally I/O-free.  It validates the retained immutable
``atlas-money-worlds`` R0--R4 artifact lattice, binds a newly queried full DK
catalog and canonical R0 incumbent pool, prepares the exact 50,000-world slate
matrix, records every exact-pricing proof, and freezes the 108 A/B book cells.

The caller owns BigQuery, GCS, Cloud Run, create-once publication, and the
historical-outcome lease.  No function here accepts or exposes a realized
score.  In particular, the old August 17 catalog is not silently upgraded: a
fresh exact structural catalog and exact R0 roster extract are mandatory.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from hashlib import sha256
from io import BytesIO
import json
import math
import re
from typing import Final

import numpy as np

from nfl_dfs.research import lr8_exact_solvers as exact
from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import residual_world_columns as rw


SOURCE_FREEZE_VERSION: Final = "lr8-later-period-source-freeze-v1"
CONSTRUCTION_CELL_VERSION: Final = "lr8-later-period-construction-cell-v1"
BOOK_FREEZE_VERSION: Final = "lr8-later-period-108-book-freeze-v1"
SMOKE_VERSION: Final = "lr8-later-period-real-source-smoke-v1"
BASE_SOURCE_VERSION: Final = "production-law-dependence-source-lock-v1"
BASE_SOURCE_RUN_ID: Final = "20260817-production-law-dependence-source-lock-v1"
BASE_SOURCE_URI: Final = (
    "gs://nfl-predictions-503414-raw/research/"
    "production-law-dependence-runs/"
    "20260817-production-law-dependence-source-lock-v1/source-lock.json"
)
BASE_SOURCE_GENERATION: Final = "1786950155692968"
BASE_SOURCE_SHA256: Final = (
    "7ede34b6d13dacb6645836a85ff35dc82f757331423e49f84537d710c500346c"
)
BASE_SOURCE_BYTES: Final = 1_341_911
PROJECT: Final = "nfl-predictions-503414"
LOCATION: Final = "US"
CANDIDATE_TABLE: Final = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
CATALOG_TABLE: Final = f"{PROJECT}.nfl_predictions.slate_player_features"
CANDIDATE_SQL: Final = f"""
SELECT panel_run_id, season, week, cand_ix, players,
       score_artifact_uri, score_artifact_sha256
FROM `{CANDIDATE_TABLE}` FOR SYSTEM_TIME AS OF @source_snapshot_at
WHERE panel_run_id=@r0_panel
  AND season IN (2023, 2024, 2025)
ORDER BY season, week, cand_ix
"""
CATALOG_SQL: Final = f"""
SELECT season, week, id, pos, team, opp, game_id, salary
FROM `{CATALOG_TABLE}` FOR SYSTEM_TIME AS OF @source_snapshot_at
WHERE panel_run_id=@r0_panel
  AND season IN (2023, 2024, 2025)
ORDER BY season, week, id
"""
SMOKE_TERMINAL_VERSION: Final = "lr8-later-period-smoke-terminal-v1"
SOURCE_PANELS: Final = tuple(
    f"20260815-atlas-money-worlds-r{seed}-v1" for seed in range(5)
)
R0_PANEL: Final = SOURCE_PANELS[0]
EXPECTED_SLATE_KEYS: Final = tuple(
    (season, week)
    for season in lr8.EVALUATION_SEASONS
    for week in lr8.EVALUATION_WEEKS
)
EXPECTED_ARTIFACT_KEYS: Final = tuple(
    (season, week, block)
    for season, week in EXPECTED_SLATE_KEYS
    for block in rw.WORLD_BLOCKS
)
EXPECTED_ARTIFACTS: Final = len(EXPECTED_ARTIFACT_KEYS)
REPAIRED_R3_KEY: Final = (2025, 1, "R3")
REPAIRED_R3_SHA256: Final = (
    "7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805"
)
NPZ_FIELDS: Final = frozenset({
    "cand_ix", "totals", "tail_line", "player_ids", "player_draws",
})

R0_CANDIDATE_FIELDS: Final = frozenset({
    "panel_run_id", "season", "week", "cand_ix", "players",
    "score_artifact_uri", "score_artifact_sha256",
})
CATALOG_FIELDS: Final = frozenset({
    "season", "week", "id", "pos", "team", "opp", "game_id", "salary",
})
ARTIFACT_RECEIPT_FIELDS: Final = frozenset({
    "bytes", "candidate_rows", "generation", "panel_run_id", "season",
    "seed", "sha256", "updated", "uri", "week",
})
OBJECT_RECEIPT_FIELDS: Final = frozenset({
    "uri", "generation", "sha256", "bytes",
})
QUERY_RECEIPT_FIELDS: Final = frozenset({
    "job_id", "location", "sql_sha256", "parameters_sha256", "created",
    "started", "ended", "total_bytes_processed", "cache_hit", "error_result",
})
BOOK_CELL_FIELDS: Final = frozenset({
    "season", "week", "fold_name", "candidate_budget_control",
    "candidate_budget_treatment", "control_candidates",
    "treatment_candidates", "control_book", "treatment_book", "cell_sha256",
})

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_GENERATION: Final = re.compile(r"[1-9][0-9]*")


class LR8LaterSourceError(ValueError):
    """The real later-period source or construction contract failed closed."""


@dataclass(frozen=True, slots=True)
class ArtifactWorldBlock:
    block: str
    player_ids: tuple[str, ...]
    player_draws: np.ndarray = field(compare=False, repr=False)
    artifact_sha256: str


@dataclass(frozen=True, slots=True)
class PreparedLaterSlate:
    season: int
    week: int
    slate_id: str
    players: tuple[rw.PlayerSpec, ...]
    world_ids: tuple[rw.WorldId, ...]
    player_draws: np.ndarray = field(compare=False, repr=False)
    incumbent_candidates: tuple[tuple[str, ...], ...]
    source_freeze_sha256: str
    artifact_sha256_by_block: Mapping[str, str]


ProofValidator = Callable[[exact.ExactSolveProofBundle], None]


def canonical_json(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json(value)).hexdigest()


CANDIDATE_SQL_SHA256: Final = sha256(CANDIDATE_SQL.encode("utf-8")).hexdigest()
CATALOG_SQL_SHA256: Final = sha256(CATALOG_SQL.encode("utf-8")).hexdigest()


def source_parameter_payload(snapshot: str) -> list[dict[str, object]]:
    return [
        {"name": "r0_panel", "type": "STRING", "value": R0_PANEL},
        {
            "name": "source_snapshot_at",
            "type": "TIMESTAMP",
            "value": _timestamp(snapshot, label="source parameter snapshot"),
        },
    ]


def _base_source_object(value: object) -> dict[str, object]:
    receipt = _object_receipt(value, label="base source lock")
    expected = {
        "uri": BASE_SOURCE_URI,
        "generation": BASE_SOURCE_GENERATION,
        "sha256": BASE_SOURCE_SHA256,
        "bytes": BASE_SOURCE_BYTES,
    }
    if receipt != expected:
        raise LR8LaterSourceError("base source-lock object identity differs")
    return receipt


def _strict_string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise LR8LaterSourceError(f"{label} must be a canonical string")
    return value


def _strict_sha(value: object, *, label: str) -> str:
    text = value if isinstance(value, str) else ""
    if _SHA256.fullmatch(text) is None:
        raise LR8LaterSourceError(f"{label} must be a lowercase SHA-256")
    return text


def _exact_int(
    value: object, *, label: str, minimum: int | None = 0,
) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8LaterSourceError(f"{label} must be an exact integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise LR8LaterSourceError(f"{label} must be >= {minimum}")
    return result


def _salary(value: object) -> int:
    if isinstance(value, (bool, np.bool_)):
        raise LR8LaterSourceError("catalog salary must be an exact positive integer")
    if isinstance(value, (int, np.integer)):
        result = int(value)
    elif isinstance(value, (float, np.floating)):
        number = float(value)
        if not math.isfinite(number) or not number.is_integer():
            raise LR8LaterSourceError(
                "catalog salary must be an exact positive integer"
            )
        result = int(number)
        if number != result:
            raise LR8LaterSourceError(
                "catalog salary must be an exact positive integer"
            )
    else:
        raise LR8LaterSourceError("catalog salary must be an exact positive integer")
    if result <= 0:
        raise LR8LaterSourceError("catalog salary must be an exact positive integer")
    return result


def _timestamp(value: object, *, label: str) -> str:
    text = _strict_string(value, label=label)
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise LR8LaterSourceError(f"{label} must be ISO-8601") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise LR8LaterSourceError(f"{label} must be timezone-aware")
    return text


def _object_receipt(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != OBJECT_RECEIPT_FIELDS:
        raise LR8LaterSourceError(f"{label} receipt fields differ")
    uri = _strict_string(value["uri"], label=f"{label} URI")
    if not uri.startswith("gs://"):
        raise LR8LaterSourceError(f"{label} URI must use gs://")
    generation = _strict_string(value["generation"], label=f"{label} generation")
    if _GENERATION.fullmatch(generation) is None:
        raise LR8LaterSourceError(f"{label} generation differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _strict_sha(value["sha256"], label=f"{label} SHA-256"),
        "bytes": _exact_int(value["bytes"], label=f"{label} bytes", minimum=1),
    }


def _bound_object_receipt(
    value: object, payload: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    receipt = _object_receipt(value, label=label)
    raw = canonical_json(payload)
    identities = {
        (sha256(candidate).hexdigest(), len(candidate))
        for candidate in (raw, raw + b"\n")
    }
    if (receipt["sha256"], receipt["bytes"]) not in identities:
        raise LR8LaterSourceError(f"{label} does not bind canonical bytes")
    return receipt


def _query_receipt(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != QUERY_RECEIPT_FIELDS:
        raise LR8LaterSourceError(f"{label} query receipt fields differ")
    created = _timestamp(value["created"], label=f"{label} created")
    started = _timestamp(value["started"], label=f"{label} started")
    ended = _timestamp(value["ended"], label=f"{label} ended")
    if not created <= started <= ended:
        raise LR8LaterSourceError(f"{label} query chronology differs")
    if value["cache_hit"] is not False or value["error_result"] is not None:
        raise LR8LaterSourceError(f"{label} query was cached or failed")
    return {
        "job_id": _strict_string(value["job_id"], label=f"{label} job"),
        "location": _strict_string(value["location"], label=f"{label} location"),
        "sql_sha256": _strict_sha(value["sql_sha256"], label=f"{label} SQL"),
        "parameters_sha256": _strict_sha(
            value["parameters_sha256"], label=f"{label} parameters"
        ),
        "created": created,
        "started": started,
        "ended": ended,
        "total_bytes_processed": _exact_int(
            value["total_bytes_processed"],
            label=f"{label} processed bytes",
        ),
        "cache_hit": False,
        "error_result": None,
    }


def _artifact_receipts(
    base_source_lock: Mapping[str, object],
) -> tuple[dict[str, object], ...]:
    if (
        base_source_lock.get("version") != BASE_SOURCE_VERSION
        or base_source_lock.get("run_id") != BASE_SOURCE_RUN_ID
        or base_source_lock.get("source_panels") != list(SOURCE_PANELS)
        or base_source_lock.get("slates") != len(EXPECTED_SLATE_KEYS)
        or base_source_lock.get("artifact_count") != EXPECTED_ARTIFACTS
        or base_source_lock.get("actual_outcomes_queried") is not False
        or base_source_lock.get("candidate_or_lineup_scores_read") is not False
        or base_source_lock.get("uses_realized_outcomes") is not False
    ):
        raise LR8LaterSourceError("retained source-lock identity differs")
    raw = base_source_lock.get("artifact_receipts")
    if not isinstance(raw, list) or len(raw) != EXPECTED_ARTIFACTS:
        raise LR8LaterSourceError("retained artifact receipt lattice differs")
    receipts: list[dict[str, object]] = []
    observed: list[tuple[int, int, str]] = []
    for item in raw:
        if not isinstance(item, Mapping) or set(item) != ARTIFACT_RECEIPT_FIELDS:
            raise LR8LaterSourceError("retained artifact receipt fields differ")
        seed = _exact_int(item["seed"], label="artifact seed")
        if seed >= len(rw.WORLD_BLOCKS):
            raise LR8LaterSourceError("retained artifact seed differs")
        block = rw.WORLD_BLOCKS[seed]
        season = _exact_int(item["season"], label="artifact season")
        week = _exact_int(item["week"], label="artifact week", minimum=1)
        panel = _strict_string(item["panel_run_id"], label="artifact panel")
        if panel != SOURCE_PANELS[seed]:
            raise LR8LaterSourceError("retained artifact panel differs")
        uri = _strict_string(item["uri"], label="artifact URI")
        generation = _strict_string(item["generation"], label="artifact generation")
        if not uri.startswith("gs://") or _GENERATION.fullmatch(generation) is None:
            raise LR8LaterSourceError("retained artifact object identity differs")
        receipt = {
            "season": season,
            "week": week,
            "block": block,
            "panel_run_id": panel,
            "candidate_rows": _exact_int(
                item["candidate_rows"], label="artifact candidate rows", minimum=1
            ),
            "uri": uri,
            "generation": generation,
            "sha256": _strict_sha(item["sha256"], label="artifact SHA-256"),
            "bytes": _exact_int(item["bytes"], label="artifact bytes", minimum=1),
            "updated": _timestamp(item["updated"], label="artifact updated"),
        }
        receipts.append(receipt)
        observed.append((season, week, block))
    if tuple(observed) != EXPECTED_ARTIFACT_KEYS:
        raise LR8LaterSourceError("retained artifact order/lattice differs")
    repaired = next(
        row for row in receipts
        if (row["season"], row["week"], row["block"]) == REPAIRED_R3_KEY
    )
    if repaired["sha256"] != REPAIRED_R3_SHA256:
        raise LR8LaterSourceError("repaired 2025-W1/R3 artifact differs")
    return tuple(receipts)


def _roster(value: object) -> tuple[str, ...]:
    if isinstance(value, str):
        raw: Sequence[object] = value.split(",")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        raw = value
    else:
        raise LR8LaterSourceError("incumbent roster is malformed")
    try:
        return rw.canonical_identity(raw)
    except rw.ResidualWorldError as exc:
        raise LR8LaterSourceError("incumbent roster is malformed") from exc


def _catalog_player(value: Mapping[str, object]) -> rw.PlayerSpec:
    if set(value) != CATALOG_FIELDS:
        raise LR8LaterSourceError("full DK catalog fields differ")
    try:
        return rw.PlayerSpec.from_mapping({
            "id": _strict_string(value["id"], label="catalog player id"),
            "pos": _strict_string(value["pos"], label="catalog position"),
            "team": _strict_string(value["team"], label="catalog team"),
            "opp": _strict_string(value["opp"], label="catalog opponent"),
            "game_id": _strict_string(value["game_id"], label="catalog game"),
            "salary": _salary(value["salary"]),
        })
    except (KeyError, TypeError, rw.ResidualWorldError) as exc:
        raise LR8LaterSourceError("full DK catalog row is malformed") from exc


def _catalog_payload(players: Sequence[rw.PlayerSpec]) -> list[dict[str, object]]:
    return [{
        "id": player.player_id,
        "pos": player.position,
        "team": player.team,
        "opp": player.opponent,
        "game_id": player.game_id,
        "salary": player.salary,
    } for player in players]


def build_source_freeze(
    *,
    base_source_lock: Mapping[str, object],
    base_source_lock_object: Mapping[str, object],
    base_source_lock_sha256: str,
    r0_candidate_rows: Sequence[Mapping[str, object]],
    full_catalog_rows: Sequence[Mapping[str, object]],
    query_provenance: Mapping[str, object],
    runtime_identity: Mapping[str, object],
) -> dict[str, object]:
    """Bind the real retained worlds to a fresh outcome-blind structural source."""
    base_digest = _strict_sha(
        base_source_lock_sha256, label="base source-lock SHA-256"
    )
    base_object = _base_source_object(base_source_lock_object)
    if base_object["sha256"] != base_digest or base_digest != BASE_SOURCE_SHA256:
        raise LR8LaterSourceError("base source-lock object hash differs")
    artifacts = _artifact_receipts(base_source_lock)
    artifact_by_key = {
        (int(row["season"]), int(row["week"]), str(row["block"])): row
        for row in artifacts
    }
    if not isinstance(query_provenance, Mapping) or set(query_provenance) != {
        "candidate_query", "catalog_query", "candidate_table",
        "catalog_table", "source_snapshot_at",
    }:
        raise LR8LaterSourceError("later source query provenance fields differ")
    candidate_query = _query_receipt(
        query_provenance["candidate_query"], label="R0 candidate"
    )
    catalog_query = _query_receipt(
        query_provenance["catalog_query"], label="full catalog"
    )
    candidate_table = _strict_string(
        query_provenance["candidate_table"], label="candidate table"
    )
    catalog_table = _strict_string(
        query_provenance["catalog_table"], label="catalog table"
    )
    snapshot = _timestamp(
        query_provenance["source_snapshot_at"], label="source snapshot"
    )
    source_parameters_sha256 = canonical_sha256(
        source_parameter_payload(snapshot)
    )
    if not isinstance(runtime_identity, Mapping) or set(runtime_identity) != {
        "run_id", "code_sha", "image", "job",
    }:
        raise LR8LaterSourceError("later source runtime identity fields differ")
    normalized_runtime = {
        key: _strict_string(runtime_identity[key], label=f"runtime {key}")
        for key in ("run_id", "code_sha", "image", "job")
    }
    if (
        candidate_table != CANDIDATE_TABLE
        or catalog_table != CATALOG_TABLE
        or candidate_query["job_id"]
        != f"{normalized_runtime['run_id']}-r0-candidates"
        or catalog_query["job_id"]
        != f"{normalized_runtime['run_id']}-full-catalog"
        or candidate_query["location"] != LOCATION
        or catalog_query["location"] != LOCATION
        or candidate_query["sql_sha256"] != CANDIDATE_SQL_SHA256
        or catalog_query["sql_sha256"] != CATALOG_SQL_SHA256
        or candidate_query["parameters_sha256"] != source_parameters_sha256
        or catalog_query["parameters_sha256"] != source_parameters_sha256
    ):
        raise LR8LaterSourceError("later source exact query contract differs")

    candidates_by_slate: dict[tuple[int, int], list[tuple[int, tuple[str, ...]]]] = {
        key: [] for key in EXPECTED_SLATE_KEYS
    }
    for row in r0_candidate_rows:
        if not isinstance(row, Mapping) or set(row) != R0_CANDIDATE_FIELDS:
            raise LR8LaterSourceError("canonical R0 candidate fields differ")
        season = _exact_int(row["season"], label="candidate season")
        week = _exact_int(row["week"], label="candidate week", minimum=1)
        key = (season, week)
        if key not in candidates_by_slate or row["panel_run_id"] != R0_PANEL:
            raise LR8LaterSourceError("canonical R0 candidate slate/panel differs")
        artifact = artifact_by_key[(season, week, "R0")]
        if (
            row["score_artifact_uri"] != artifact["uri"]
            or row["score_artifact_sha256"] != artifact["sha256"]
        ):
            raise LR8LaterSourceError("canonical R0 candidate artifact differs")
        candidates_by_slate[key].append((
            _exact_int(row["cand_ix"], label="candidate index"),
            _roster(row["players"]),
        ))

    catalog_by_slate: dict[tuple[int, int], list[rw.PlayerSpec]] = {
        key: [] for key in EXPECTED_SLATE_KEYS
    }
    observed_catalog_keys: set[tuple[int, int, str]] = set()
    for row in full_catalog_rows:
        if not isinstance(row, Mapping):
            raise LR8LaterSourceError("full DK catalog row must be an object")
        season = _exact_int(row.get("season"), label="catalog season")
        week = _exact_int(row.get("week"), label="catalog week", minimum=1)
        key = (season, week)
        if key not in catalog_by_slate:
            raise LR8LaterSourceError("full DK catalog slate differs")
        player = _catalog_player(row)
        player_key = (season, week, player.player_id)
        if player_key in observed_catalog_keys:
            raise LR8LaterSourceError("full DK catalog repeats a player")
        observed_catalog_keys.add(player_key)
        catalog_by_slate[key].append(player)

    slates: list[dict[str, object]] = []
    for season, week in EXPECTED_SLATE_KEYS:
        indexed = candidates_by_slate[(season, week)]
        r0_artifact = artifact_by_key[(season, week, "R0")]
        if [index for index, _ in indexed] != list(range(len(indexed))) or (
            len(indexed) != int(r0_artifact["candidate_rows"])
        ):
            raise LR8LaterSourceError("canonical R0 candidate order/count differs")
        incumbents = tuple(roster for _, roster in indexed)
        if len(incumbents) < lr8.ENTRIES + lr8.K_MAX_PER_FOLD or (
            len(set(incumbents)) != len(incumbents)
        ):
            raise LR8LaterSourceError("canonical R0 incumbent support differs")
        players = tuple(sorted(
            catalog_by_slate[(season, week)], key=lambda player: player.player_id
        ))
        if not players or len({player.player_id for player in players}) != len(players):
            raise LR8LaterSourceError("full DK catalog is empty or unordered")
        player_ids = {player.player_id for player in players}
        if any(not set(roster) <= player_ids for roster in incumbents):
            raise LR8LaterSourceError("R0 incumbent is absent from the full catalog")
        for roster in incumbents:
            try:
                lr8.audit_dk_classic_identity(players, roster)
            except lr8.LR8Error as exc:
                raise LR8LaterSourceError(
                    "canonical R0 incumbent is not DK Classic legal"
                ) from exc
        catalog = _catalog_payload(players)
        roster_payload = [list(roster) for roster in incumbents]
        slate_artifacts = [
            dict(artifact_by_key[(season, week, block)]) for block in rw.WORLD_BLOCKS
        ]
        slates.append({
            "season": season,
            "week": week,
            "slate_id": f"{season}-w{week:02d}",
            "catalog": catalog,
            "catalog_sha256": canonical_sha256(catalog),
            "incumbent_candidates": roster_payload,
            "incumbent_candidates_sha256": canonical_sha256(roster_payload),
            "artifact_receipts": slate_artifacts,
            "artifact_receipts_sha256": canonical_sha256(slate_artifacts),
        })

    payload: dict[str, object] = {
        "schema": SOURCE_FREEZE_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "runtime_identity": normalized_runtime,
        "base_source_lock_sha256": base_digest,
        "base_source_lock_object": base_object,
        "base_source_version": BASE_SOURCE_VERSION,
        "base_source_run_id": BASE_SOURCE_RUN_ID,
        "source_panels": list(SOURCE_PANELS),
        "canonical_incumbent_panel": R0_PANEL,
        "seasons": list(lr8.EVALUATION_SEASONS),
        "weeks": list(lr8.EVALUATION_WEEKS),
        "slate_count": len(EXPECTED_SLATE_KEYS),
        "artifact_count": EXPECTED_ARTIFACTS,
        "world_blocks": list(rw.WORLD_BLOCKS),
        "worlds_per_block": rw.WORLDS_PER_BLOCK,
        "source_query": {
            "candidate_table": candidate_table,
            "catalog_table": catalog_table,
            "source_snapshot_at": snapshot,
            "candidate_query": candidate_query,
            "catalog_query": catalog_query,
            "selected_columns": {
                "candidates": sorted(R0_CANDIDATE_FIELDS),
                "catalog": sorted(CATALOG_FIELDS),
            },
            "realized_columns_selected": [],
        },
        "slates": slates,
        "repaired_2025_w1_r3_sha256": REPAIRED_R3_SHA256,
        "hard_constraints": "dk_nfl_classic_only",
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "production_inputs_used": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    payload["freeze_sha256"] = canonical_sha256(payload)
    return validate_source_freeze(
        payload, expected_freeze_sha256=str(payload["freeze_sha256"])
    )


def validate_source_freeze(
    value: Mapping[str, object], *, expected_freeze_sha256: str,
) -> dict[str, object]:
    expected = _strict_sha(expected_freeze_sha256, label="source freeze SHA-256")
    if not isinstance(value, Mapping):
        raise LR8LaterSourceError("later source freeze must be an object")
    frozen = dict(value)
    digest = frozen.pop("freeze_sha256", None)
    if digest != expected or canonical_sha256(frozen) != expected:
        raise LR8LaterSourceError("later source freeze hash differs")
    required = {
        "schema", "protocol_id", "runtime_identity", "base_source_lock_sha256",
        "base_source_lock_object", "base_source_version", "base_source_run_id",
        "source_panels", "canonical_incumbent_panel", "seasons", "weeks",
        "slate_count", "artifact_count", "world_blocks", "worlds_per_block",
        "source_query", "slates", "repaired_2025_w1_r3_sha256",
        "hard_constraints", "uses_realized_outcomes",
        "candidate_or_lineup_scores_read", "b1_inputs_used", "a2a_inputs_used",
        "production_inputs_used", "historical_scoring_licensed",
        "production_change_licensed",
    }
    if set(frozen) != required:
        raise LR8LaterSourceError("later source freeze fields differ")
    if (
        frozen["schema"] != SOURCE_FREEZE_VERSION
        or frozen["protocol_id"] != lr8.PROTOCOL_ID
        or frozen["base_source_version"] != BASE_SOURCE_VERSION
        or frozen["base_source_run_id"] != BASE_SOURCE_RUN_ID
        or frozen["source_panels"] != list(SOURCE_PANELS)
        or frozen["canonical_incumbent_panel"] != R0_PANEL
        or frozen["seasons"] != list(lr8.EVALUATION_SEASONS)
        or frozen["weeks"] != list(lr8.EVALUATION_WEEKS)
        or frozen["slate_count"] != len(EXPECTED_SLATE_KEYS)
        or frozen["artifact_count"] != EXPECTED_ARTIFACTS
        or frozen["world_blocks"] != list(rw.WORLD_BLOCKS)
        or frozen["worlds_per_block"] != rw.WORLDS_PER_BLOCK
        or frozen["repaired_2025_w1_r3_sha256"] != REPAIRED_R3_SHA256
        or frozen["hard_constraints"] != "dk_nfl_classic_only"
    ):
        raise LR8LaterSourceError("later source freeze identity differs")
    for field in (
        "uses_realized_outcomes", "candidate_or_lineup_scores_read",
        "b1_inputs_used", "a2a_inputs_used", "production_inputs_used",
        "historical_scoring_licensed", "production_change_licensed",
    ):
        if frozen[field] is not False:
            raise LR8LaterSourceError(f"later source {field} must be false")
    _strict_sha(frozen["base_source_lock_sha256"], label="base source hash")
    base_object = _base_source_object(frozen["base_source_lock_object"])
    if (
        base_object["sha256"] != frozen["base_source_lock_sha256"]
        or frozen["base_source_lock_sha256"] != BASE_SOURCE_SHA256
    ):
        raise LR8LaterSourceError("base source receipt/hash differs")
    runtime = frozen["runtime_identity"]
    if not isinstance(runtime, Mapping) or set(runtime) != {
        "run_id", "code_sha", "image", "job",
    }:
        raise LR8LaterSourceError("source runtime identity differs")
    for key in runtime:
        _strict_string(runtime[key], label=f"runtime {key}")
    source_query = frozen["source_query"]
    if not isinstance(source_query, Mapping) or set(source_query) != {
        "candidate_table", "catalog_table", "source_snapshot_at",
        "candidate_query", "catalog_query", "selected_columns",
        "realized_columns_selected",
    }:
        raise LR8LaterSourceError("source query contract differs")
    _strict_string(source_query["candidate_table"], label="candidate table")
    _strict_string(source_query["catalog_table"], label="catalog table")
    snapshot = _timestamp(
        source_query["source_snapshot_at"], label="source snapshot"
    )
    source_parameters_sha256 = canonical_sha256(
        source_parameter_payload(snapshot)
    )
    candidate_query = _query_receipt(
        source_query["candidate_query"], label="R0 candidate"
    )
    catalog_query = _query_receipt(
        source_query["catalog_query"], label="full catalog"
    )
    if (
        source_query["candidate_table"] != CANDIDATE_TABLE
        or source_query["catalog_table"] != CATALOG_TABLE
        or candidate_query["job_id"] != f"{runtime['run_id']}-r0-candidates"
        or catalog_query["job_id"] != f"{runtime['run_id']}-full-catalog"
        or candidate_query["location"] != LOCATION
        or catalog_query["location"] != LOCATION
        or candidate_query["sql_sha256"] != CANDIDATE_SQL_SHA256
        or catalog_query["sql_sha256"] != CATALOG_SQL_SHA256
        or candidate_query["parameters_sha256"] != source_parameters_sha256
        or catalog_query["parameters_sha256"] != source_parameters_sha256
    ):
        raise LR8LaterSourceError("source query exact identity differs")
    if source_query["selected_columns"] != {
        "candidates": sorted(R0_CANDIDATE_FIELDS),
        "catalog": sorted(CATALOG_FIELDS),
    } or source_query["realized_columns_selected"] != []:
        raise LR8LaterSourceError("source query column boundary differs")
    slates = frozen["slates"]
    if not isinstance(slates, list) or len(slates) != len(EXPECTED_SLATE_KEYS):
        raise LR8LaterSourceError("later source slate lattice differs")
    for raw, expected_key in zip(slates, EXPECTED_SLATE_KEYS, strict=True):
        if not isinstance(raw, Mapping) or set(raw) != {
            "season", "week", "slate_id", "catalog", "catalog_sha256",
            "incumbent_candidates", "incumbent_candidates_sha256",
            "artifact_receipts", "artifact_receipts_sha256",
        }:
            raise LR8LaterSourceError("later source slate fields differ")
        season = _exact_int(raw["season"], label="slate season")
        week = _exact_int(raw["week"], label="slate week", minimum=1)
        if (season, week) != expected_key or raw["slate_id"] != f"{season}-w{week:02d}":
            raise LR8LaterSourceError("later source slate order differs")
        catalog = raw["catalog"]
        if not isinstance(catalog, list) or not catalog:
            raise LR8LaterSourceError("later source catalog differs")
        players = tuple(_catalog_player({
            "season": season,
            "week": week,
            **dict(row),
        }) for row in catalog if isinstance(row, Mapping))
        if len(players) != len(catalog) or tuple(
            player.player_id for player in players
        ) != tuple(sorted(player.player_id for player in players)):
            raise LR8LaterSourceError("later source catalog order differs")
        if canonical_sha256(catalog) != raw["catalog_sha256"]:
            raise LR8LaterSourceError("later source catalog hash differs")
        incumbents_raw = raw["incumbent_candidates"]
        if not isinstance(incumbents_raw, list):
            raise LR8LaterSourceError("later source incumbents differ")
        incumbents = tuple(_roster(row) for row in incumbents_raw)
        if (
            len(incumbents) < lr8.ENTRIES + lr8.K_MAX_PER_FOLD
            or len(set(incumbents)) != len(incumbents)
            or [list(row) for row in incumbents] != incumbents_raw
            or canonical_sha256(incumbents_raw)
            != raw["incumbent_candidates_sha256"]
        ):
            raise LR8LaterSourceError("later source incumbent contract differs")
        for roster in incumbents:
            try:
                lr8.audit_dk_classic_identity(players, roster)
            except lr8.LR8Error as exc:
                raise LR8LaterSourceError(
                    "later source incumbent legality differs"
                ) from exc
        artifacts = raw["artifact_receipts"]
        if not isinstance(artifacts, list) or len(artifacts) != len(rw.WORLD_BLOCKS):
            raise LR8LaterSourceError("later source slate artifact lattice differs")
        if canonical_sha256(artifacts) != raw["artifact_receipts_sha256"]:
            raise LR8LaterSourceError("later source slate artifact hash differs")
        for artifact, block in zip(artifacts, rw.WORLD_BLOCKS, strict=True):
            if not isinstance(artifact, Mapping) or (
                artifact.get("season"), artifact.get("week"), artifact.get("block")
            ) != (season, week, block):
                raise LR8LaterSourceError("later source artifact identity differs")
            _object_receipt({
                key: artifact[key] for key in OBJECT_RECEIPT_FIELDS
            }, label="world artifact")
            if _exact_int(
                artifact.get("candidate_rows"),
                label="world artifact candidate rows",
                minimum=1,
            ) < 1:
                raise LR8LaterSourceError("world artifact candidate count differs")
    frozen["base_source_lock_object"] = base_object
    frozen["freeze_sha256"] = expected
    return frozen


def load_artifact_worlds(
    receipt: Mapping[str, object], raw: bytes,
) -> ArtifactWorldBlock:
    """Validate one exact retained NPZ and expose only its player-world matrix."""
    if not isinstance(raw, bytes):
        raise LR8LaterSourceError("world artifact body must be bytes")
    block = _strict_string(receipt.get("block"), label="world artifact block")
    if block not in rw.WORLD_BLOCKS:
        raise LR8LaterSourceError("world artifact block differs")
    digest = _strict_sha(receipt.get("sha256"), label="world artifact SHA-256")
    if sha256(raw).hexdigest() != digest or len(raw) != _exact_int(
        receipt.get("bytes"), label="world artifact bytes", minimum=1
    ):
        raise LR8LaterSourceError("world artifact bytes differ from receipt")
    try:
        with np.load(BytesIO(raw), allow_pickle=False) as artifact:
            if set(artifact.files) != NPZ_FIELDS:
                raise LR8LaterSourceError("world artifact NPZ members differ")
            cand_ix = np.asarray(artifact["cand_ix"])
            totals = np.asarray(artifact["totals"])
            tail_line = np.asarray(artifact["tail_line"])
            player_ids = tuple(np.asarray(artifact["player_ids"]).astype(str).tolist())
            player_draws = np.asarray(artifact["player_draws"])
    except LR8LaterSourceError:
        raise
    except Exception as exc:
        raise LR8LaterSourceError("world artifact NPZ is unreadable") from exc
    candidate_rows = _exact_int(
        receipt.get("candidate_rows"), label="world artifact candidate rows", minimum=1
    )
    if (
        cand_ix.ndim != 1
        or not np.array_equal(cand_ix, np.arange(candidate_rows, dtype=cand_ix.dtype))
        or totals.shape != (candidate_rows, rw.WORLDS_PER_BLOCK)
        or tail_line.size != 1
        or player_draws.dtype != np.float32
        or player_draws.ndim != 2
        or player_draws.shape != (len(player_ids), rw.WORLDS_PER_BLOCK)
        or not player_ids
        or len(set(player_ids)) != len(player_ids)
        or any(not player_id for player_id in player_ids)
        or not np.isfinite(totals).all()
        or not np.isfinite(tail_line).all()
        or not np.isfinite(player_draws).all()
    ):
        raise LR8LaterSourceError("world artifact NPZ scientific shape differs")
    draws = np.ascontiguousarray(player_draws, dtype=np.float32)
    draws.flags.writeable = False
    return ArtifactWorldBlock(
        block=block,
        player_ids=player_ids,
        player_draws=draws,
        artifact_sha256=digest,
    )


def prepare_later_slate(
    source_freeze: Mapping[str, object],
    *,
    expected_source_freeze_sha256: str,
    season: int,
    week: int,
    artifact_bodies: Mapping[str, bytes],
) -> PreparedLaterSlate:
    frozen = validate_source_freeze(
        source_freeze, expected_freeze_sha256=expected_source_freeze_sha256
    )
    key = (
        _exact_int(season, label="prepared season"),
        _exact_int(week, label="prepared week", minimum=1),
    )
    if key not in EXPECTED_SLATE_KEYS or set(artifact_bodies) != set(rw.WORLD_BLOCKS):
        raise LR8LaterSourceError("prepared slate key/artifact blocks differ")
    row = frozen["slates"][EXPECTED_SLATE_KEYS.index(key)]
    players = tuple(rw.PlayerSpec.from_mapping(value) for value in row["catalog"])
    incumbents = tuple(_roster(value) for value in row["incumbent_candidates"])
    blocks: list[ArtifactWorldBlock] = []
    for receipt, block in zip(
        row["artifact_receipts"], rw.WORLD_BLOCKS, strict=True
    ):
        loaded = load_artifact_worlds(receipt, artifact_bodies[block])
        if loaded.block != block:
            raise LR8LaterSourceError("prepared world block order differs")
        blocks.append(loaded)
    catalog_ids = tuple(player.player_id for player in players)
    aligned: list[np.ndarray] = []
    for block in blocks:
        if set(block.player_ids) != set(catalog_ids):
            raise LR8LaterSourceError(
                "retained player-world ids do not equal the full DK catalog"
            )
        index = {player_id: row for row, player_id in enumerate(block.player_ids)}
        aligned.append(block.player_draws[[index[player_id] for player_id in catalog_ids]])
    draws = np.ascontiguousarray(np.concatenate(aligned, axis=1), dtype=np.float32)
    if draws.shape != (
        len(players), len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK
    ):
        raise LR8LaterSourceError("prepared five-block world matrix differs")
    draws.flags.writeable = False
    worlds = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(rw.WORLDS_PER_BLOCK)
    )
    return PreparedLaterSlate(
        season=key[0],
        week=key[1],
        slate_id=str(row["slate_id"]),
        players=players,
        world_ids=worlds,
        player_draws=draws,
        incumbent_candidates=incumbents,
        source_freeze_sha256=str(frozen["freeze_sha256"]),
        artifact_sha256_by_block={
            block.block: block.artifact_sha256 for block in blocks
        },
    )


class ProofCollectingPricingStep:
    """Wrap one exact pricing callback and retain each request/proof envelope."""

    def __init__(
        self,
        step: Callable[[lr8.PricingRequest], Sequence[object] | None],
        *,
        proof_validator: ProofValidator = exact.validate_proof_bundle,
    ) -> None:
        if not callable(step) or not callable(proof_validator):
            raise LR8LaterSourceError("pricing proof collector callbacks differ")
        self._step = step
        self._proof_validator = proof_validator
        self.records: list[dict[str, object]] = []

    def __call__(self, request: lr8.PricingRequest) -> tuple[str, ...] | None:
        response = self._step(request)
        proof = getattr(self._step, "last_proof", None)
        receipts = getattr(self._step, "last_evidence_receipts", None)
        if not isinstance(proof, exact.ExactSolveProofBundle):
            raise LR8LaterSourceError("exact pricing callback did not expose its proof")
        self._proof_validator(proof)
        request_sha = exact.pricing_request_sha256(request)
        if proof.request_sha256 != request_sha:
            raise LR8LaterSourceError("exact pricing proof request hash differs")
        if isinstance(receipts, (str, bytes)):
            raise LR8LaterSourceError("exact pricing evidence receipts differ")
        try:
            evidence = tuple(
                _object_receipt(value, label="pricing evidence") for value in receipts
            )
        except TypeError as exc:
            raise LR8LaterSourceError("exact pricing evidence receipts differ") from exc
        if not evidence:
            raise LR8LaterSourceError("exact pricing proof retained no evidence objects")
        proof_objects = [
            row for row in evidence
            if row["sha256"] == proof.proof_sha256
            and row["bytes"] == len(proof.proof_bytes)
        ]
        if len(proof_objects) != 1:
            raise LR8LaterSourceError("pricing proof object receipt differs")
        roster = None if response is None else rw.canonical_identity(response)
        if proof.result_payload.get("roster") != (
            None if roster is None else list(roster)
        ):
            raise LR8LaterSourceError("pricing response/proof roster differs")
        self.records.append({
            "fold_name": request.fold_name,
            "iteration": request.iteration,
            "request_sha256": request_sha,
            "response_roster": None if roster is None else list(roster),
            "proof_sha256": proof.proof_sha256,
            "proof_object": proof_objects[0],
            "evidence_objects": list(evidence),
            "result": dict(proof.result_payload),
        })
        return roster


def _book_cell_payload(
    season: int, week: int, fold: lr8.FoldMechanicsResult,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "season": season,
        "week": week,
        "fold_name": fold.fold_name,
        "candidate_budget_control": fold.candidate_budget,
        "candidate_budget_treatment": len(fold.treatment_candidates),
        "control_candidates": [list(row) for row in fold.control_candidates],
        "treatment_candidates": [list(row) for row in fold.treatment_candidates],
        "control_book": [list(row) for row in fold.control_book],
        "treatment_book": [list(row) for row in fold.treatment_book],
    }
    payload["cell_sha256"] = canonical_sha256(payload)
    return payload


def _validate_proof_records(
    result: lr8.LR8MechanicsResult,
    records: Sequence[Mapping[str, object]],
) -> None:
    expected = [
        (fold.fold_name, step.iteration, step)
        for fold in result.folds for step in fold.steps
    ]
    if len(records) != len(expected) or not 2 <= len(records) <= 16:
        raise LR8LaterSourceError("construction pricing proof count differs")
    for raw, (fold_name, iteration, step) in zip(records, expected, strict=True):
        if not isinstance(raw, Mapping) or set(raw) != {
            "fold_name", "iteration", "request_sha256", "response_roster",
            "proof_sha256", "proof_object", "evidence_objects", "result",
        }:
            raise LR8LaterSourceError("construction proof envelope fields differ")
        if raw["fold_name"] != fold_name or raw["iteration"] != iteration:
            raise LR8LaterSourceError("construction proof call order differs")
        _strict_sha(raw["request_sha256"], label="pricing request hash")
        proof_sha = _strict_sha(raw["proof_sha256"], label="pricing proof hash")
        proof_object = _object_receipt(raw["proof_object"], label="pricing proof")
        if proof_object["sha256"] != proof_sha:
            raise LR8LaterSourceError("construction proof receipt/hash differs")
        evidence = raw["evidence_objects"]
        if not isinstance(evidence, list) or not evidence:
            raise LR8LaterSourceError("construction evidence objects differ")
        for receipt in evidence:
            _object_receipt(receipt, label="pricing evidence")
        response = raw["response_roster"]
        expected_response = None if step.roster is None else list(step.roster)
        if response != expected_response:
            raise LR8LaterSourceError("construction proof/mechanics roster differs")
        proof_result = raw["result"]
        if not isinstance(proof_result, Mapping) or proof_result.get("roster") != response:
            raise LR8LaterSourceError("construction proof result differs")
        if step.null:
            if proof_result.get("null") is not True:
                raise LR8LaterSourceError("construction null proof differs")
        elif (
            proof_result.get("null") is not False
            or proof_result.get("threshold_counts") != list(step.threshold_counts)
            or proof_result.get("anatomy_linear_predictor_units")
            != step.anatomy_tier_units
            or proof_result.get("clipped_gain_micro")
            != step.clipped_residual_gain_micro
        ):
            raise LR8LaterSourceError("construction exact objective proof differs")


def run_construction_cell(
    prepared: PreparedLaterSlate,
    *,
    anatomy_artifact: Mapping[str, object],
    pricing_steps: Mapping[str, Callable[[lr8.PricingRequest], Sequence[object] | None]],
    mode: str,
    smoke_authority: Mapping[str, object] | None = None,
    proof_validator: ProofValidator = exact.validate_proof_bundle,
) -> dict[str, object]:
    """Run one real source slate and freeze both A/B exact proof envelopes."""
    if not isinstance(prepared, PreparedLaterSlate):
        raise LR8LaterSourceError("prepared later slate has the wrong type")
    if mode not in {"smoke", "full"} or set(pricing_steps) != {"A", "B"}:
        raise LR8LaterSourceError("construction mode/pricing folds differ")
    if (
        prepared.player_draws.dtype != np.float32
        or prepared.player_draws.shape != (
            len(prepared.players), len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK
        )
        or prepared.player_draws.flags.writeable
        or len(prepared.world_ids) != len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK
        or len(prepared.incumbent_candidates) < lr8.ENTRIES + lr8.K_MAX_PER_FOLD
    ):
        raise LR8LaterSourceError("prepared later slate scientific shape differs")
    artifact = lr8.validate_soft_anatomy_artifact(anatomy_artifact)
    if mode == "smoke":
        if (prepared.season, prepared.week) != EXPECTED_SLATE_KEYS[0] or (
            smoke_authority is not None
        ):
            raise LR8LaterSourceError("real-source smoke must be exactly 2023-W1")
    else:
        validate_smoke_authority(
            smoke_authority,
            source_freeze_sha256=prepared.source_freeze_sha256,
            anatomy_artifact_sha256=str(artifact["artifact_sha256"]),
        )
    collectors = {
        fold: ProofCollectingPricingStep(
            pricing_steps[fold], proof_validator=proof_validator
        ) for fold in ("A", "B")
    }
    try:
        result = lr8.run_lr8_mechanics(
            season=prepared.season,
            week=prepared.week,
            slate_id=prepared.slate_id,
            players=prepared.players,
            world_ids=prepared.world_ids,
            raw_player_draws=prepared.player_draws,
            incumbent_candidates=prepared.incumbent_candidates,
            anatomy_artifact=artifact,
            pricing_steps=collectors,
        )
    except (lr8.LR8Error, exact.LR8ExactSolverError) as exc:
        raise LR8LaterSourceError(str(exc)) from exc
    records = tuple(collectors[fold].records[index]
                    for fold in ("A", "B")
                    for index in range(len(collectors[fold].records)))
    _validate_proof_records(result, records)
    mechanics = lr8.mechanics_payload(result)
    books = [_book_cell_payload(result.season, result.week, fold) for fold in result.folds]
    payload: dict[str, object] = {
        "schema": (
            SMOKE_VERSION if mode == "smoke" else CONSTRUCTION_CELL_VERSION
        ),
        "protocol_id": lr8.PROTOCOL_ID,
        "mode": mode,
        "season": result.season,
        "week": result.week,
        "slate_id": result.slate_id,
        "source_freeze_sha256": prepared.source_freeze_sha256,
        "anatomy_artifact_sha256": artifact["artifact_sha256"],
        "artifact_sha256_by_block": dict(prepared.artifact_sha256_by_block),
        "mechanics": mechanics,
        "pricing_proofs": list(records),
        "pricing_proof_manifest_sha256": canonical_sha256(list(records)),
        "book_cells": books,
        "book_cells_sha256": canonical_sha256(books),
        "smoke_authority": None if mode == "smoke" else dict(smoke_authority),
        "pricing_optimality_proven": True,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "production_inputs_used": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    payload["cell_sha256"] = canonical_sha256(payload)
    validate_construction_cell(
        payload, expected_cell_sha256=str(payload["cell_sha256"]), mode=mode
    )
    return payload


def validate_smoke_terminal(
    value: object,
    *,
    terminal_object: Mapping[str, object],
    smoke_object: Mapping[str, object],
    smoke_sha256: str,
    source_freeze_sha256: str,
    anatomy_artifact_sha256: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping):
        raise LR8LaterSourceError("real-source smoke terminal must be an object")
    terminal = dict(value)
    digest = terminal.pop("terminal_sha256", None)
    if _strict_sha(digest, label="smoke terminal hash") != canonical_sha256(terminal):
        raise LR8LaterSourceError("real-source smoke terminal hash differs")
    if set(terminal) != {
        "schema", "execution_name", "execution_metadata_object",
        "finish_ledger_object", "smoke_object", "smoke_sha256",
        "source_freeze_sha256", "anatomy_artifact_sha256", "task_count",
        "succeeded_count", "failed_count", "cancelled_count",
        "retried_count", "completed_condition", "strict_terminal_success",
    }:
        raise LR8LaterSourceError("real-source smoke terminal fields differ")
    expected_smoke_object = _object_receipt(smoke_object, label="real-source smoke")
    if (
        terminal["schema"] != SMOKE_TERMINAL_VERSION
        or terminal["smoke_object"] != expected_smoke_object
        or terminal["smoke_sha256"] != smoke_sha256
        or terminal["source_freeze_sha256"] != source_freeze_sha256
        or terminal["anatomy_artifact_sha256"] != anatomy_artifact_sha256
        or _exact_int(terminal["task_count"], label="smoke task count") != 1
        or _exact_int(terminal["succeeded_count"], label="smoke success count") != 1
        or _exact_int(terminal["failed_count"], label="smoke failed count") != 0
        or _exact_int(terminal["cancelled_count"], label="smoke cancelled count") != 0
        or _exact_int(terminal["retried_count"], label="smoke retry count") != 0
        or terminal["completed_condition"] != "True"
        or terminal["strict_terminal_success"] is not True
    ):
        raise LR8LaterSourceError("real-source smoke terminal status differs")
    _strict_string(terminal["execution_name"], label="smoke execution name")
    _object_receipt(
        terminal["execution_metadata_object"], label="smoke execution metadata"
    )
    _object_receipt(terminal["finish_ledger_object"], label="smoke finish ledger")
    terminal["terminal_sha256"] = digest
    _bound_object_receipt(terminal_object, terminal, label="smoke terminal")
    return terminal


def validate_smoke_authority(
    value: object,
    *,
    source_freeze_sha256: str,
    anatomy_artifact_sha256: str,
) -> dict[str, object]:
    if not isinstance(value, Mapping) or set(value) != {
        "object", "smoke_sha256", "source_freeze_sha256",
        "anatomy_artifact_sha256", "terminal", "terminal_object",
    }:
        raise LR8LaterSourceError("real-source smoke authority fields differ")
    receipt = _object_receipt(value["object"], label="real-source smoke")
    smoke_sha = _strict_sha(value["smoke_sha256"], label="smoke cell hash")
    if (
        value["source_freeze_sha256"] != source_freeze_sha256
        or value["anatomy_artifact_sha256"] != anatomy_artifact_sha256
        or receipt["sha256"] == smoke_sha
    ):
        raise LR8LaterSourceError("real-source smoke authority differs")
    terminal_object = _object_receipt(
        value["terminal_object"], label="smoke terminal"
    )
    terminal = validate_smoke_terminal(
        value["terminal"],
        terminal_object=terminal_object,
        smoke_object=receipt,
        smoke_sha256=smoke_sha,
        source_freeze_sha256=source_freeze_sha256,
        anatomy_artifact_sha256=anatomy_artifact_sha256,
    )
    return {
        "object": receipt,
        "smoke_sha256": smoke_sha,
        "source_freeze_sha256": source_freeze_sha256,
        "anatomy_artifact_sha256": anatomy_artifact_sha256,
        "terminal": terminal,
        "terminal_object": terminal_object,
    }


def validate_construction_cell(
    value: Mapping[str, object], *, expected_cell_sha256: str, mode: str,
) -> dict[str, object]:
    expected = _strict_sha(expected_cell_sha256, label="construction cell hash")
    if not isinstance(value, Mapping):
        raise LR8LaterSourceError("construction cell must be an object")
    cell = dict(value)
    digest = cell.pop("cell_sha256", None)
    if digest != expected or canonical_sha256(cell) != expected:
        raise LR8LaterSourceError("construction cell hash differs")
    expected_schema = SMOKE_VERSION if mode == "smoke" else CONSTRUCTION_CELL_VERSION
    if cell.get("schema") != expected_schema or cell.get("mode") != mode or (
        cell.get("protocol_id") != lr8.PROTOCOL_ID
    ):
        raise LR8LaterSourceError("construction cell identity differs")
    season = _exact_int(cell.get("season"), label="cell season")
    week = _exact_int(cell.get("week"), label="cell week", minimum=1)
    if (season, week) not in EXPECTED_SLATE_KEYS or (
        cell.get("slate_id") != f"{season}-w{week:02d}"
    ):
        raise LR8LaterSourceError("construction cell slate differs")
    _strict_sha(cell.get("source_freeze_sha256"), label="cell source hash")
    _strict_sha(cell.get("anatomy_artifact_sha256"), label="cell anatomy hash")
    artifacts = cell.get("artifact_sha256_by_block")
    if not isinstance(artifacts, Mapping) or list(artifacts) != list(rw.WORLD_BLOCKS):
        raise LR8LaterSourceError("construction cell artifact hashes differ")
    for value_sha in artifacts.values():
        _strict_sha(value_sha, label="construction artifact hash")
    proofs = cell.get("pricing_proofs")
    if not isinstance(proofs, list):
        raise LR8LaterSourceError("construction cell proof manifest differs")
    mechanics = cell.get("mechanics")
    if not isinstance(mechanics, Mapping) or mechanics.get("season") != season or (
        mechanics.get("week") != week
    ):
        raise LR8LaterSourceError("construction mechanics identity differs")
    mechanics_body = dict(mechanics)
    mechanics_sha = mechanics_body.pop("report_sha256", None)
    if (
        _strict_sha(mechanics_sha, label="mechanics report hash")
        != canonical_sha256(mechanics_body)
        or mechanics.get("schema") != "lr8-historical-mechanics-result-v1"
        or mechanics.get("protocol_id") != lr8.PROTOCOL_ID
        or mechanics.get("slate_id") != cell.get("slate_id")
        or mechanics.get("anatomy_artifact_sha256")
        != cell.get("anatomy_artifact_sha256")
        or mechanics.get("candidate_budget_fixed") is not True
        or mechanics.get("entry_budget") != lr8.ENTRIES
        or mechanics.get("deployment_fold_rule") != "odd_week_A_even_week_B"
        or mechanics.get("later_period_realized_outcomes_used") is not False
        or mechanics.get("historical_execution_licensed") is not False
        or mechanics.get("production_change_licensed") is not False
    ):
        raise LR8LaterSourceError("construction mechanics contract differs")
    # Reconstruct the minimal dataclass view needed for proof/object parity.
    folds_raw = mechanics.get("folds")
    if (
        not isinstance(folds_raw, list)
        or len(folds_raw) != 2
        or any(not isinstance(row, Mapping) for row in folds_raw)
        or [row.get("fold_name") for row in folds_raw] != ["A", "B"]
    ):
        raise LR8LaterSourceError("construction mechanics folds differ")
    if any(not isinstance(row.get("steps"), list) for row in folds_raw):
        raise LR8LaterSourceError("construction mechanics steps differ")
    expected_calls = sum(len(row["steps"]) for row in folds_raw)
    if len(proofs) != expected_calls or not 2 <= expected_calls <= 16:
        raise LR8LaterSourceError("construction proof/mechanics count differs")
    if canonical_sha256(proofs) != cell.get("pricing_proof_manifest_sha256"):
        raise LR8LaterSourceError("construction proof manifest hash differs")
    expected_proof_steps = [
        (fold["fold_name"], step)
        for fold in folds_raw
        for step in fold["steps"]
    ]
    for proof, (fold_name, step) in zip(
        proofs, expected_proof_steps, strict=True,
    ):
        if not isinstance(proof, Mapping) or set(proof) != {
            "fold_name", "iteration", "request_sha256", "response_roster",
            "proof_sha256", "proof_object", "evidence_objects", "result",
        } or not isinstance(step, Mapping):
            raise LR8LaterSourceError("construction proof row differs")
        if (
            proof["fold_name"] != fold_name
            or proof["iteration"] != step.get("iteration")
            or proof["response_roster"] != step.get("roster")
        ):
            raise LR8LaterSourceError("construction proof/step identity differs")
        _strict_sha(proof.get("request_sha256"), label="pricing request hash")
        proof_sha = _strict_sha(proof.get("proof_sha256"), label="pricing proof hash")
        if _object_receipt(
            proof.get("proof_object"), label="pricing proof"
        )["sha256"] != proof_sha:
            raise LR8LaterSourceError("construction proof object differs")
        evidence = proof.get("evidence_objects")
        if not isinstance(evidence, list) or not evidence:
            raise LR8LaterSourceError("construction proof evidence differs")
        for receipt in evidence:
            _object_receipt(receipt, label="pricing evidence")
        result = proof.get("result")
        if not isinstance(result, Mapping) or result.get("roster") != step.get("roster"):
            raise LR8LaterSourceError("construction proof result roster differs")
        if step.get("null") is True:
            if result.get("null") is not True:
                raise LR8LaterSourceError("construction proof null result differs")
        elif (
            step.get("null") is not False
            or result.get("null") is not False
            or result.get("threshold_counts") != step.get("threshold_counts")
            or result.get("anatomy_linear_predictor_units")
            != step.get("anatomy_tier_units")
            or result.get("clipped_gain_micro")
            != step.get("clipped_residual_gain_micro")
        ):
            raise LR8LaterSourceError("construction proof objective result differs")
    books = cell.get("book_cells")
    if not isinstance(books, list) or len(books) != 2 or [
        row.get("fold_name") for row in books
    ] != ["A", "B"] or canonical_sha256(books) != cell.get("book_cells_sha256"):
        raise LR8LaterSourceError("construction cell books differ")
    for book, fold in zip(books, folds_raw, strict=True):
        if not isinstance(book, Mapping) or set(book) != BOOK_CELL_FIELDS:
            raise LR8LaterSourceError("construction book row differs")
        body = dict(book)
        book_sha = body.pop("cell_sha256", None)
        if _strict_sha(book_sha, label="book cell hash") != canonical_sha256(body):
            raise LR8LaterSourceError("construction book cell hash differs")
        if (
            body.get("season") != season
            or body.get("week") != week
            or body.get("fold_name") != fold.get("fold_name")
            or body.get("candidate_budget_control")
            != body.get("candidate_budget_treatment")
            or body.get("candidate_budget_control")
            != len(body.get("control_candidates", []))
            or body.get("candidate_budget_treatment")
            != len(body.get("treatment_candidates", []))
            or body.get("candidate_budget_control") != fold.get("candidate_budget")
            or body.get("control_candidates") != fold.get("control_candidates")
            or body.get("treatment_candidates") != fold.get("treatment_candidates")
            or body.get("control_book") != fold.get("control_book")
            or body.get("treatment_book") != fold.get("treatment_book")
            or len(body.get("control_book", [])) != lr8.ENTRIES
            or len(body.get("treatment_book", [])) != lr8.ENTRIES
        ):
            raise LR8LaterSourceError(
                "construction book/mechanics binding differs"
            )
    for field in (
        "uses_realized_outcomes", "candidate_or_lineup_scores_read",
        "b1_inputs_used", "a2a_inputs_used", "production_inputs_used",
        "historical_scoring_licensed", "production_change_licensed",
    ):
        if cell.get(field) is not False:
            raise LR8LaterSourceError(f"construction {field} must be false")
    if cell.get("pricing_optimality_proven") is not True:
        raise LR8LaterSourceError("construction pricing proof marker differs")
    if mode == "smoke":
        if (season, week) != EXPECTED_SLATE_KEYS[0] or cell.get("smoke_authority") is not None:
            raise LR8LaterSourceError("construction smoke identity differs")
    else:
        validate_smoke_authority(
            cell.get("smoke_authority"),
            source_freeze_sha256=str(cell["source_freeze_sha256"]),
            anatomy_artifact_sha256=str(cell["anatomy_artifact_sha256"]),
        )
    cell["cell_sha256"] = expected
    return cell


def aggregate_book_freeze(
    cells: Sequence[Mapping[str, object]],
    *,
    cell_objects: Sequence[Mapping[str, object]],
    source_freeze: Mapping[str, object],
    source_freeze_object: Mapping[str, object],
    anatomy_freeze: Mapping[str, object],
    anatomy_freeze_sha256: str,
    anatomy_freeze_object: Mapping[str, object],
    smoke_authority: Mapping[str, object],
) -> dict[str, object]:
    """Validate exact 54-cell coverage and freeze the score-ready 108 books."""
    rows = tuple(cells)
    receipts = tuple(_object_receipt(row, label="construction cell") for row in cell_objects)
    if len(rows) != len(EXPECTED_SLATE_KEYS) or len(receipts) != len(rows):
        raise LR8LaterSourceError("construction aggregate cell count differs")
    validated: list[dict[str, object]] = []
    for cell, receipt, key in zip(rows, receipts, EXPECTED_SLATE_KEYS, strict=True):
        if not isinstance(cell, Mapping):
            raise LR8LaterSourceError("construction aggregate cell differs")
        validated_cell = validate_construction_cell(
            cell, expected_cell_sha256=str(cell.get("cell_sha256", "")), mode="full"
        )
        if (validated_cell["season"], validated_cell["week"]) != key:
            raise LR8LaterSourceError("construction aggregate cell order differs")
        if receipt["sha256"] != sha256(canonical_json(cell)).hexdigest():
            raise LR8LaterSourceError("construction cell object bytes/hash differs")
        validated.append(validated_cell)
    source_hashes = {str(row["source_freeze_sha256"]) for row in validated}
    anatomy_hashes = {str(row["anatomy_artifact_sha256"]) for row in validated}
    if len(source_hashes) != 1 or len(anatomy_hashes) != 1:
        raise LR8LaterSourceError("construction aggregate source/anatomy differs")
    source_hash = next(iter(source_hashes))
    anatomy_hash = next(iter(anatomy_hashes))
    source_object = _object_receipt(source_freeze_object, label="later source freeze")
    anatomy_hash_expected = _strict_sha(
        anatomy_freeze_sha256, label="anatomy fit freeze hash"
    )
    if (
        not isinstance(anatomy_freeze, Mapping)
        or anatomy_freeze.get("freeze_sha256") != anatomy_hash_expected
        or anatomy_freeze.get("anatomy_artifact_sha256") != anatomy_hash
    ):
        raise LR8LaterSourceError("anatomy fit freeze binding differs")
    anatomy_object = _bound_object_receipt(
        anatomy_freeze_object, anatomy_freeze, label="anatomy freeze"
    )
    frozen_source = validate_source_freeze(
        source_freeze, expected_freeze_sha256=source_hash
    )
    source_raw = canonical_json(source_freeze)
    if (
        source_object["sha256"] != sha256(source_raw).hexdigest()
        or source_object["bytes"] != len(source_raw)
    ):
        raise LR8LaterSourceError("later source freeze object bytes/hash differs")
    authority = validate_smoke_authority(
        smoke_authority,
        source_freeze_sha256=source_hash,
        anatomy_artifact_sha256=anatomy_hash,
    )
    if any(row["smoke_authority"] != authority for row in validated):
        raise LR8LaterSourceError("construction cells use different smoke authority")
    books = [book for row in validated for book in row["book_cells"]]
    expected_book_keys = [
        (season, week, fold)
        for season, week in EXPECTED_SLATE_KEYS for fold in ("A", "B")
    ]
    if [
        (book["season"], book["week"], book["fold_name"]) for book in books
    ] != expected_book_keys:
        raise LR8LaterSourceError("108-book freeze order differs")
    catalogs = []
    for slate in frozen_source["slates"]:
        players = [{
            "id": player["id"],
            "pos": player["pos"],
            "team": player["team"],
        } for player in slate["catalog"]]
        catalogs.append({
            "season": slate["season"],
            "week": slate["week"],
            "players": players,
            "catalog_sha256": canonical_sha256(players),
        })
    payload: dict[str, object] = {
        "schema": BOOK_FREEZE_VERSION,
        "protocol_id": lr8.PROTOCOL_ID,
        "source_freeze_sha256": source_hash,
        "source_freeze_object": source_object,
        "anatomy_artifact_sha256": anatomy_hash,
        "anatomy_freeze_sha256": anatomy_hash_expected,
        "anatomy_freeze_object": anatomy_object,
        "smoke_authority": authority,
        "seasons": list(lr8.EVALUATION_SEASONS),
        "weeks": list(lr8.EVALUATION_WEEKS),
        "cell_count": len(validated),
        "book_cell_count": len(books),
        "cell_objects": list(receipts),
        "cell_object_manifest_sha256": canonical_sha256(list(receipts)),
        "catalogs": catalogs,
        "catalogs_sha256": canonical_sha256(catalogs),
        "book_cells": books,
        "book_cells_sha256": canonical_sha256(books),
        "primary_deployment_rule": "odd_week_A_even_week_B",
        "candidate_and_entry_budgets_frozen": True,
        "pricing_optimality_proven": True,
        # This narrow authority licenses only the evaluator's later-period
        # one-shot score read after all 54 construction cells prove terminal.
        "later_period_score_read_licensed": True,
        "uses_realized_outcomes": False,
        "candidate_or_lineup_scores_read": False,
        "historical_outcome_lease_acquired": False,
        "b1_inputs_used": False,
        "a2a_inputs_used": False,
        "winner_inputs_used": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    payload["freeze_sha256"] = canonical_sha256(payload)
    return validate_book_freeze(
        payload, expected_freeze_sha256=str(payload["freeze_sha256"])
    )


def validate_book_freeze(
    value: Mapping[str, object], *, expected_freeze_sha256: str,
) -> dict[str, object]:
    expected = _strict_sha(expected_freeze_sha256, label="108-book freeze hash")
    if not isinstance(value, Mapping):
        raise LR8LaterSourceError("108-book freeze must be an object")
    frozen = dict(value)
    digest = frozen.pop("freeze_sha256", None)
    if digest != expected or canonical_sha256(frozen) != expected:
        raise LR8LaterSourceError("108-book freeze hash differs")
    required = {
        "schema", "protocol_id", "source_freeze_sha256",
        "source_freeze_object", "anatomy_artifact_sha256",
        "anatomy_freeze_sha256", "anatomy_freeze_object", "smoke_authority",
        "seasons", "weeks",
        "cell_count", "book_cell_count", "cell_objects",
        "cell_object_manifest_sha256", "catalogs", "catalogs_sha256",
        "book_cells", "book_cells_sha256", "primary_deployment_rule",
        "candidate_and_entry_budgets_frozen", "pricing_optimality_proven",
        "later_period_score_read_licensed", "uses_realized_outcomes",
        "candidate_or_lineup_scores_read", "historical_outcome_lease_acquired",
        "b1_inputs_used", "a2a_inputs_used", "winner_inputs_used",
        "historical_scoring_licensed", "production_change_licensed",
    }
    if set(frozen) != required:
        raise LR8LaterSourceError("108-book freeze fields differ")
    if (
        frozen.get("schema") != BOOK_FREEZE_VERSION
        or frozen.get("protocol_id") != lr8.PROTOCOL_ID
        or frozen.get("seasons") != list(lr8.EVALUATION_SEASONS)
        or frozen.get("weeks") != list(lr8.EVALUATION_WEEKS)
        or frozen.get("cell_count") != len(EXPECTED_SLATE_KEYS)
        or frozen.get("book_cell_count") != len(EXPECTED_SLATE_KEYS) * 2
        or frozen.get("primary_deployment_rule") != "odd_week_A_even_week_B"
        or frozen.get("candidate_and_entry_budgets_frozen") is not True
        or frozen.get("pricing_optimality_proven") is not True
        or frozen.get("later_period_score_read_licensed") is not True
        or frozen.get("uses_realized_outcomes") is not False
        or frozen.get("candidate_or_lineup_scores_read") is not False
        or frozen.get("historical_outcome_lease_acquired") is not False
        or frozen.get("b1_inputs_used") is not False
        or frozen.get("a2a_inputs_used") is not False
        or frozen.get("winner_inputs_used") is not False
        or frozen.get("historical_scoring_licensed") is not False
        or frozen.get("production_change_licensed") is not False
    ):
        raise LR8LaterSourceError("108-book freeze identity differs")
    source_hash = _strict_sha(frozen.get("source_freeze_sha256"), label="source hash")
    anatomy_hash = _strict_sha(
        frozen.get("anatomy_artifact_sha256"), label="anatomy hash"
    )
    _strict_sha(frozen.get("anatomy_freeze_sha256"), label="anatomy fit hash")
    _object_receipt(frozen.get("source_freeze_object"), label="source freeze")
    _object_receipt(frozen.get("anatomy_freeze_object"), label="anatomy freeze")
    validate_smoke_authority(
        frozen.get("smoke_authority"),
        source_freeze_sha256=source_hash,
        anatomy_artifact_sha256=anatomy_hash,
    )
    cell_objects = frozen.get("cell_objects")
    books = frozen.get("book_cells")
    if not isinstance(cell_objects, list) or len(cell_objects) != len(EXPECTED_SLATE_KEYS):
        raise LR8LaterSourceError("108-book cell object manifest differs")
    for receipt in cell_objects:
        _object_receipt(receipt, label="construction cell")
    if canonical_sha256(cell_objects) != frozen.get("cell_object_manifest_sha256"):
        raise LR8LaterSourceError("108-book cell object hash differs")
    catalogs = frozen.get("catalogs")
    if not isinstance(catalogs, list) or len(catalogs) != len(EXPECTED_SLATE_KEYS):
        raise LR8LaterSourceError("108-book catalogs differ")
    if canonical_sha256(catalogs) != frozen.get("catalogs_sha256"):
        raise LR8LaterSourceError("108-book catalog manifest hash differs")
    catalog_ids: dict[tuple[int, int], set[str]] = {}
    for catalog, key in zip(catalogs, EXPECTED_SLATE_KEYS, strict=True):
        if not isinstance(catalog, Mapping) or set(catalog) != {
            "season", "week", "players", "catalog_sha256",
        } or (catalog.get("season"), catalog.get("week")) != key:
            raise LR8LaterSourceError("108-book catalog identity differs")
        players = catalog.get("players")
        if not isinstance(players, list) or not players or (
            canonical_sha256(players) != catalog.get("catalog_sha256")
        ):
            raise LR8LaterSourceError("108-book catalog hash differs")
        ids: list[str] = []
        for player in players:
            if not isinstance(player, Mapping) or set(player) != {
                "id", "pos", "team",
            }:
                raise LR8LaterSourceError("108-book catalog player fields differ")
            ids.append(_strict_string(player["id"], label="catalog player id"))
            _strict_string(player["pos"], label="catalog player position")
            _strict_string(player["team"], label="catalog player team")
        if ids != sorted(ids) or len(ids) != len(set(ids)):
            raise LR8LaterSourceError("108-book catalog order/uniqueness differs")
        catalog_ids[key] = set(ids)
    if not isinstance(books, list) or len(books) != len(EXPECTED_SLATE_KEYS) * 2:
        raise LR8LaterSourceError("108-book rows differ")
    if canonical_sha256(books) != frozen.get("book_cells_sha256"):
        raise LR8LaterSourceError("108-book row hash differs")
    expected_keys = [
        (season, week, fold)
        for season, week in EXPECTED_SLATE_KEYS for fold in ("A", "B")
    ]
    if [(row.get("season"), row.get("week"), row.get("fold_name"))
        for row in books if isinstance(row, Mapping)] != expected_keys:
        raise LR8LaterSourceError("108-book row order differs")
    for book, key in zip(books, expected_keys, strict=True):
        if not isinstance(book, Mapping) or set(book) != BOOK_CELL_FIELDS:
            raise LR8LaterSourceError("108-book cell fields differ")
        body = dict(book)
        cell_sha = body.pop("cell_sha256")
        if _strict_sha(cell_sha, label="108-book cell hash") != canonical_sha256(body):
            raise LR8LaterSourceError("108-book cell hash differs")
        candidate_fields = ("control_candidates", "treatment_candidates")
        book_fields = ("control_book", "treatment_book")
        normalized: dict[str, tuple[tuple[str, ...], ...]] = {}
        for field in (*candidate_fields, *book_fields):
            raw_rows = book[field]
            if not isinstance(raw_rows, list):
                raise LR8LaterSourceError("108-book roster rows differ")
            rosters = tuple(_roster(row) for row in raw_rows)
            if [list(row) for row in rosters] != raw_rows or (
                len(set(rosters)) != len(rosters)
            ):
                raise LR8LaterSourceError("108-book roster order/uniqueness differs")
            normalized[field] = rosters
        control_n = _exact_int(
            book["candidate_budget_control"], label="control candidate budget",
            minimum=lr8.ENTRIES,
        )
        treatment_n = _exact_int(
            book["candidate_budget_treatment"], label="treatment candidate budget",
            minimum=lr8.ENTRIES,
        )
        union_ids = {
            player_id for field in candidate_fields
            for roster in normalized[field] for player_id in roster
        }
        if (
            (book["season"], book["week"], book["fold_name"]) != key
            or control_n != treatment_n
            or len(normalized["control_candidates"]) != control_n
            or len(normalized["treatment_candidates"]) != treatment_n
            or len(normalized["control_book"]) != lr8.ENTRIES
            or len(normalized["treatment_book"]) != lr8.ENTRIES
            or not set(normalized["control_book"]) <= set(
                normalized["control_candidates"]
            )
            or not set(normalized["treatment_book"]) <= set(
                normalized["treatment_candidates"]
            )
            or not union_ids <= catalog_ids[key[:2]]
        ):
            raise LR8LaterSourceError("108-book budget/catalog coverage differs")
    frozen["freeze_sha256"] = expected
    return frozen


__all__ = [
    "ArtifactWorldBlock",
    "BASE_SOURCE_BYTES",
    "BASE_SOURCE_GENERATION",
    "BASE_SOURCE_SHA256",
    "BASE_SOURCE_URI",
    "BOOK_FREEZE_VERSION",
    "CANDIDATE_SQL",
    "CANDIDATE_SQL_SHA256",
    "CANDIDATE_TABLE",
    "CATALOG_SQL",
    "CATALOG_SQL_SHA256",
    "CATALOG_TABLE",
    "CONSTRUCTION_CELL_VERSION",
    "EXPECTED_ARTIFACT_KEYS",
    "EXPECTED_SLATE_KEYS",
    "LR8LaterSourceError",
    "PreparedLaterSlate",
    "ProofCollectingPricingStep",
    "SMOKE_VERSION",
    "SMOKE_TERMINAL_VERSION",
    "SOURCE_FREEZE_VERSION",
    "SOURCE_PANELS",
    "aggregate_book_freeze",
    "build_source_freeze",
    "canonical_json",
    "canonical_sha256",
    "load_artifact_worlds",
    "prepare_later_slate",
    "run_construction_cell",
    "source_parameter_payload",
    "validate_book_freeze",
    "validate_construction_cell",
    "validate_smoke_authority",
    "validate_smoke_terminal",
    "validate_source_freeze",
]
