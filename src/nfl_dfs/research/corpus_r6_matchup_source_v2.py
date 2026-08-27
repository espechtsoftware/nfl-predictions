"""Offline successor contracts for the historical R6 matchup source.

This module is deliberately smaller than an executable source pipeline.  It
defines the immutable inputs and receipts that a later producer and ordinal-
only operator must exact-reopen.  It owns no CLI, cloud client, warehouse
client, object publication, Git inspection, outcome read, lineup selection,
or mechanics authority.

The contract corrects two defects in the v1 source seam:

* the target population is the accepted six-field structural catalog; and
* historical evidence is represented by exact source periods and objects,
  not by invented pre-lock event or observation timestamps.

Builders in this module canonicalize facts supplied by an outer producer.
They do not make those facts authoritative.  Every emitted object keeps all
outcome, downstream, publication, and source-mechanics authorities false.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
from typing import Final
from zoneinfo import ZoneInfo

from nfl_dfs.research import corpus_r6_player_catalog_v1 as catalog_v1


UPSTREAM_PACK_REGISTRY_SCHEMA: Final = (
    "corpus-r6-matchup-upstream-pack-registry/v1"
)
UPSTREAM_PACK_ROWS_SCHEMA: Final = "corpus-r6-matchup-upstream-pack-rows/v1"
UPSTREAM_RELEASE_SCHEMA: Final = "corpus-r6-matchup-upstream-release/v1"
ROLE_REGISTRY_SCHEMA: Final = "corpus-r6-matchup-role-registry/v2"
FAMILY_REGISTRY_SCHEMA: Final = "corpus-r6-matchup-family-registry/v1"
SEMANTIC_REGISTRY_SCHEMA: Final = "corpus-r6-matchup-semantic-registry/v2"
HISTORICAL_SOURCE_PERIOD_SCHEMA: Final = (
    "corpus-r6-matchup-historical-source-period/v1"
)
TARGET_SPINE_SCHEMA: Final = "corpus-r6-matchup-target-spine/v1"
ROLE_ENTRY_SCHEMA: Final = "corpus-r6-matchup-role-entry/v1"
DELETION_PROOF_SCHEMA: Final = (
    "corpus-r6-matchup-target-or-later-deletion-proof/v1"
)
ADMISSION_SUPPORT_SCHEMA: Final = (
    "corpus-r6-matchup-admission-support-census/v1"
)
CANDIDATE_SUPPORT_BINDING_SCHEMA: Final = (
    "corpus-r6-matchup-candidate-support-binding/v1"
)
CANDIDATE_SUPPORT_ROWS_SCHEMA: Final = (
    "corpus-r6-matchup-candidate-support-rows/v1"
)
ACCEPTED_CANDIDATE_RELEASE_SCHEMA: Final = (
    "corpus-r6-matchup-accepted-candidate-release/v1"
)
ACCEPTED_CANDIDATE_ARTIFACT_SCHEMA: Final = (
    "corpus-r6-matchup-accepted-candidate-artifact/v1"
)
PRODUCER_RECEIPT_SCHEMA: Final = (
    "corpus-r6-matchup-component-producer-receipt/v1"
)
PRODUCER_INPUT_BUNDLE_SCHEMA: Final = (
    "corpus-r6-matchup-component-input-bundle/v1"
)
ALL_54_SUPPORT_CENSUS_SCHEMA: Final = (
    "corpus-r6-matchup-all-54-support-census/v1"
)
PRODUCER_RELEASE_SCHEMA: Final = "corpus-r6-matchup-producer-release/v1"

TASK_COUNT: Final = 54
ROLE_COUNT: Final = 12
COMPONENT_ROLE_COUNT: Final = 10
ENTRY_BUDGET: Final = 80
MINIMUM_SUPPORTED_MATCHUP_PLAYERS: Final = 2
MINIMUM_LINEUP_ANNOTATION_COMPLETENESS: Final = 0.5
SIS_SHRINK_TARGETS: Final = 16.0
PUBLICATION_MODE: Final = "create_once"
AUTHORITY_BOUNDARY: Final = "offline-contract-only"
EVIDENCE_CLASS: Final = "retrospective-prior-period-reconstruction"
OBSERVED_AT_BASIS: Final = "historical-source-period-only"
PRODUCER_MODULE_PATH: Final = (
    "src/nfl_dfs/research/corpus_r6_matchup_component_producer_v1.py"
)

SCHEDULE_PACK: Final = "nfl-schedules-2022-2025"
WEEKLY_STATS_PACK: Final = "nfl-weekly-stats-2022-2025"
LEGACY_DEPTH_PACK: Final = "nfl-legacy-depth-2022-2024"
SNAPSHOT_DEPTH_PACK: Final = "nfl-snapshot-depth-2025"
PFR_DEFENSE_PACK: Final = "nfl-pfr-defense-and-snaps-2022-2025"
FANTASY_POINTS_PACK: Final = "fantasy-points-normalized-2022-2025"
SIS_PACK: Final = "sis-normalized-2022-2025"

PACK_IDS: Final = (
    SCHEDULE_PACK,
    WEEKLY_STATS_PACK,
    LEGACY_DEPTH_PACK,
    SNAPSHOT_DEPTH_PACK,
    PFR_DEFENSE_PACK,
    FANTASY_POINTS_PACK,
    SIS_PACK,
)

DELETION_PACK_IDS: Final = (
    WEEKLY_STATS_PACK,
    PFR_DEFENSE_PACK,
    SIS_PACK,
)
DELETION_SLICE_KINDS: Final = (
    "weekly-player-stats",
    "pfr-pass-rush",
    "pfr-secondary",
    "pfr-snap-positions",
    "sis-defender-alignment",
    "sis-run-context",
)

FALSE_AUTHORITY_FIELDS: Final = (
    "authoritative_for_mechanics",
    "authoritative_pit",
    "capture_mechanics_authority",
    "corpus_fill_licensed",
    "corpus_retrieval_licensed",
    "decision_authority",
    "fill_authority",
    "graph_authority",
    "graph_mutation_licensed",
    "historical_scoring_authority",
    "historical_scoring_licensed",
    "live_strategy_authority",
    "matchup_source_authority",
    "outcome_authority",
    "production_change_licensed",
    "production_authority",
    "production_policy_authority",
    "publication_authority",
    "promotion_authority",
    "r6_source_authority",
    "retrieval_authority",
    "scoring_authority",
    "source_execution_authority",
    "source_publication_authority",
)
POLICY_FIELDS: Final = frozenset({
    "outcome_columns_read",
    "uses_realized_outcomes",
    *FALSE_AUTHORITY_FIELDS,
})
FORBIDDEN_OUTCOME_CARRIER_FIELDS: Final = frozenset({
    "actual_score",
    "actual_points",
    "contest_finish",
    "contest_place",
    "contest_rank",
    "contest_score",
    "entry_rank",
    "lineup_actual",
    "lineup_points",
    "lineup_score",
    "payout",
    "realized_outcome",
    "realized_points",
    "realized_score",
    "winner",
    "winning_score",
})

OBJECT_IDENTITY_FIELDS: Final = frozenset({
    "uri", "generation", "sha256", "bytes",
})
CODE_IDENTITY_FIELDS: Final = frozenset({
    "source_commit_sha", "module_path", "module_sha256",
})
PERIOD_ENDPOINT_FIELDS: Final = frozenset({"season", "week"})
CATALOG_ENTRY_BINDING_FIELDS: Final = frozenset({
    "source_task_ordinal",
    "task_id",
    "slate",
    "lane_id",
    "lane_ordinal",
    "task_ordinal",
    "accepted_slate_membership_sha256",
    "source_task_authority_sha256",
    "catalog_identity",
    "source_catalog_sha256",
    "player_count",
    "ordered_player_ids_sha256",
})
MISSINGNESS_FIELDS: Final = frozenset({
    "identity_unresolved",
    "insufficient_history",
    "other_registered",
    "source_unavailable",
    "unknown_depth",
})

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._:-]*$")
_ROLE_NAME = re.compile(r"^[a-z][a-z0-9-]*$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")


class CorpusR6MatchupSourceV2Error(ValueError):
    """The offline R6 matchup-source successor contract is invalid."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupSourceV2Error(message)


def canonical_json_bytes(value: object) -> bytes:
    """Return the sole JSON representation admitted by this contract."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusR6MatchupSourceV2Error(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(
        type(key) is not str for key in value
    ):
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


def _identifier(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _IDENTIFIER.fullmatch(text) is None:
        _fail(f"{label} must be a canonical identifier")
    return text


def _role_name(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _ROLE_NAME.fullmatch(text) is None:
        _fail(f"{label} must be a canonical role name")
    return text


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be an integer >= {minimum}")
    return value


def _finite_number(value: object, *, label: str) -> float:
    if type(value) not in (int, float) or not math.isfinite(float(value)):
        _fail(f"{label} must be a finite number")
    return float(value)


def _timestamp(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _UTC.fullmatch(text) is None:
        _fail(f"{label} must be canonical UTC seconds")
    try:
        datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise CorpusR6MatchupSourceV2Error(
            f"{label} is not a valid timestamp"
        ) from exc
    return text


def _policy() -> dict[str, object]:
    return {
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        **{field: False for field in FALSE_AUTHORITY_FIELDS},
    }


def _validate_policy(value: Mapping[str, object], *, label: str) -> None:
    if value.get("outcome_columns_read") != []:
        _fail(f"{label}.outcome_columns_read must be empty")
    if value.get("uses_realized_outcomes") is not False:
        _fail(f"{label}.uses_realized_outcomes must be false")
    claimed = [
        field
        for field in FALSE_AUTHORITY_FIELDS
        if value.get(field) is not False
    ]
    if claimed:
        _fail(f"{label} carries non-false authorities {claimed}")


def _reject_outcome_carriers(value: object, *, label: str) -> None:
    """Reject realized lineup/contest labels while allowing prior box scores."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            if type(key) is not str:
                _fail(f"{label} contains a non-string field")
            normalized = key.strip().lower()
            if (
                normalized in FORBIDDEN_OUTCOME_CARRIER_FIELDS
                or (
                    "realized" in normalized
                    and normalized != "uses_realized_outcomes"
                )
            ):
                _fail(f"{label} contains forbidden outcome field {key!r}")
            if normalized == "outcome_columns_read" and item != []:
                _fail(f"{label}.outcome_columns_read must be empty")
            if normalized == "uses_realized_outcomes" and item is not False:
                _fail(f"{label}.uses_realized_outcomes must be false")
            if normalized in FALSE_AUTHORITY_FIELDS and item is not False:
                _fail(f"{label}.{key} must be false")
            _reject_outcome_carriers(item, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for ordinal, item in enumerate(value):
            _reject_outcome_carriers(item, label=f"{label}[{ordinal}]")


def _with_self_hash(
    body: Mapping[str, object], *, field: str,
) -> dict[str, object]:
    if field in body:
        _fail(f"{field} must not be supplied before hashing")
    result = dict(body)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _digest(value.get(field), label=f"{label}.{field}")
    body = dict(value)
    del body[field]
    if canonical_sha256(body) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def normalize_object_identity_v2(
    value: object, *, label: str = "object identity",
) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, OBJECT_IDENTITY_FIELDS, label=label)
    uri = _string(item["uri"], label=f"{label}.uri")
    if not uri.startswith("gs://") or ".." in uri or "//" in uri[5:]:
        _fail(f"{label}.uri must be a canonical GCS URI")
    generation = _string(item["generation"], label=f"{label}.generation")
    if (
        not generation.isdigit()
        or generation.startswith("0")
        or len(generation) > 64
        or int(generation) <= 0
    ):
        _fail(f"{label}.generation must be a positive decimal string")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _digest(item["sha256"], label=f"{label}.sha256"),
        "bytes": _exact_int(item["bytes"], label=f"{label}.bytes", minimum=1),
    }


def normalize_code_identity_v2(
    value: object,
    *,
    expected_module_path: str | None = None,
    label: str = "code identity",
) -> dict[str, str]:
    item = _mapping(value, label=label)
    _exact_keys(item, CODE_IDENTITY_FIELDS, label=label)
    commit = _string(item["source_commit_sha"], label=f"{label}.commit")
    if _COMMIT.fullmatch(commit) is None:
        _fail(f"{label}.source_commit_sha must be lowercase 40-hex")
    module_path = _string(item["module_path"], label=f"{label}.module_path")
    if (
        module_path.startswith("/")
        or ".." in module_path.split("/")
        or not module_path.endswith(".py")
    ):
        _fail(f"{label}.module_path must be repository-relative Python")
    if expected_module_path is not None and module_path != expected_module_path:
        _fail(f"{label}.module_path differs from the fixed module")
    return {
        "source_commit_sha": commit,
        "module_path": module_path,
        "module_sha256": _digest(
            item["module_sha256"], label=f"{label}.module_sha256"
        ),
    }


def _normalize_namespace(value: object) -> str:
    namespace = _string(value, label="namespace")
    if (
        not namespace.startswith("gs://")
        or not namespace.endswith("/")
        or ".." in namespace
        or "//" in namespace[5:]
    ):
        _fail("namespace must be a canonical GCS prefix")
    return namespace


def _bind_body_to_identity(
    body: Mapping[str, object],
    identity: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    normalized = normalize_object_identity_v2(identity, label=f"{label} identity")
    raw = canonical_json_bytes(body)
    if (
        normalized["bytes"] != len(raw)
        or normalized["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} differs from its exact object identity")
    return normalized


def _bind_value_to_identity(
    value: object,
    identity: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    normalized = normalize_object_identity_v2(identity, label=f"{label} identity")
    raw = canonical_json_bytes(value)
    if (
        normalized["bytes"] != len(raw)
        or normalized["sha256"] != sha256(raw).hexdigest()
    ):
        _fail(f"{label} differs from its exact object identity")
    return normalized


def validate_structural_catalog_v2(value: object) -> dict[str, object]:
    """Validate the accepted catalog and reassert its exact six-field rows."""
    try:
        catalog = catalog_v1.validate_player_catalog_v1(value)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupSourceV2Error(str(exc)) from exc
    expected_fields = set(catalog_v1.PLAYER_FIELD_ORDER)
    players = _sequence(catalog["players"], label="catalog players")
    if any(
        set(_mapping(player, label="catalog player")) != expected_fields
        for player in players
    ):
        _fail("catalog player rows must contain exactly six structural fields")
    return catalog


def _validate_catalog_release_body(
    value: object,
    identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    try:
        release = catalog_v1.validate_release_v1(value)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupSourceV2Error(str(exc)) from exc
    normalized_identity = _bind_body_to_identity(
        release, identity, label="structural catalog release"
    )
    expected_uri = f"{release['catalog_namespace']}catalog-release.json"
    if normalized_identity["uri"] != expected_uri:
        _fail("structural catalog release identity differs from its namespace")
    return release, normalized_identity


def _row_schema(slice_kind: str, fields: Sequence[str]) -> dict[str, object]:
    ordered = sorted(fields)
    body = {
        "slice_kind": slice_kind,
        "row_fields": ordered,
    }
    return {
        **body,
        "row_schema_sha256": canonical_sha256(body),
    }


_PACK_DEFINITIONS: Final = (
    {
        "pack_id": SCHEDULE_PACK,
        "source_kind": "warehouse-query",
        "provenance_kind": "warehouse-query-receipt",
        "period_min": {"season": 2022, "week": 1},
        "period_max": {"season": 2025, "week": 18},
        "schemas": (
            ("schedule-games", (
                "away_team", "game_id", "game_type", "gameday", "gametime",
                "home_team", "kickoff_time_utc", "season", "week",
            )),
        ),
    },
    {
        "pack_id": WEEKLY_STATS_PACK,
        "source_kind": "warehouse-query",
        "provenance_kind": "warehouse-query-receipt",
        "period_min": {"season": 2022, "week": 1},
        "period_max": {"season": 2025, "week": 18},
        "schemas": (
            ("weekly-player-stats", (
                "air_yards_share", "carries", "fumbles_lost_total",
                "opponent_team", "passing_interceptions", "passing_tds",
                "passing_yards", "player_id", "position", "receiving_tds",
                "receiving_yards", "receptions", "rushing_tds",
                "rushing_yards", "season", "target_share", "targets", "team",
                "week",
            )),
        ),
    },
    {
        "pack_id": LEGACY_DEPTH_PACK,
        "source_kind": "warehouse-query",
        "provenance_kind": "warehouse-query-receipt",
        "period_min": {"season": 2022, "week": 1},
        "period_max": {"season": 2024, "week": 18},
        "schemas": (
            ("legacy-depth", (
                "club_code", "depth_position", "depth_team", "formation",
                "gsis_id", "jersey_number", "position", "season", "week",
            )),
        ),
    },
    {
        "pack_id": SNAPSHOT_DEPTH_PACK,
        "source_kind": "warehouse-query",
        "provenance_kind": "warehouse-query-receipt",
        "period_min": {"season": 2025, "week": 1},
        "period_max": {"season": 2025, "week": 18},
        "schemas": (
            ("snapshot-depth", (
                "dt", "gsis_id", "pos_abb", "pos_rank", "team",
            )),
        ),
    },
    {
        "pack_id": PFR_DEFENSE_PACK,
        "source_kind": "warehouse-query",
        "provenance_kind": "warehouse-query-receipt",
        "period_min": {"season": 2022, "week": 1},
        "period_max": {"season": 2025, "week": 18},
        "schemas": (
            ("pfr-pass-rush", (
                "def_pressures", "def_sacks", "def_times_blitzed",
                "def_times_hurried", "game_id", "pfr_player_id", "season",
                "team", "week",
            )),
            ("pfr-secondary", (
                "def_completions_allowed", "def_targets", "def_yards_allowed",
                "game_id", "pfr_player_id", "season", "team", "week",
            )),
            ("pfr-snap-positions", (
                "defense_snaps", "game_id", "pfr_player_id", "position",
                "season", "team", "week",
            )),
        ),
    },
    {
        "pack_id": FANTASY_POINTS_PACK,
        "source_kind": "frozen-artifact-projection",
        "provenance_kind": "frozen-artifact-manifests",
        "period_min": {"season": 2022, "week": 1},
        "period_max": {"season": 2025, "week": 18},
        "schemas": (
            ("fp-route-share", (
                "gsis_id", "route_share", "season", "source_sha256", "week",
            )),
            ("fp-alignment", (
                "alignment_supported", "gsis_id", "player_wide_share", "season",
                "source_sha256", "split_duplicate", "target_week",
            )),
            ("fp-receiver-shell", (
                "gsis_id", "man_fprr", "season", "source_sha256",
                "split_duplicate", "zone_fprr",
            )),
            ("fp-defense-shell", (
                "def_man_rate", "season", "source_sha256", "team",
            )),
        ),
    },
    {
        "pack_id": SIS_PACK,
        "source_kind": "frozen-artifact-projection",
        "provenance_kind": "frozen-artifact-manifests",
        "period_min": {"season": 2022, "week": 1},
        "period_max": {"season": 2025, "week": 18},
        "schemas": (
            ("sis-defender-alignment", (
                "alignment", "completions", "coverage_snaps", "defense",
                "defender_name", "defender_player_id", "season", "targets",
                "touchdowns", "week", "yards",
            )),
            ("sis-run-context", (
                "rdef_attempts", "rdef_boom_rate", "rdef_bust_rate",
                "rdef_epa_per_attempt", "rdef_stuffs",
                "rdef_yards_after_contact", "season", "team", "week",
            )),
        ),
    },
)


def frozen_upstream_pack_registry_v1() -> dict[str, object]:
    packs: list[dict[str, object]] = []
    for ordinal, definition in enumerate(_PACK_DEFINITIONS):
        schemas = [
            _row_schema(str(slice_kind), fields)
            for slice_kind, fields in definition["schemas"]
        ]
        entry_body = {
            "ordinal": ordinal,
            "pack_id": definition["pack_id"],
            "source_kind": definition["source_kind"],
            "provenance_kind": definition["provenance_kind"],
            "positive_row_schemas": schemas,
            "positive_row_schema_manifest_sha256": canonical_sha256(schemas),
            "source_period_min": definition["period_min"],
            "source_period_max": definition["period_max"],
        }
        packs.append({
            **entry_body,
            "pack_schema_sha256": canonical_sha256(entry_body),
        })
    body: dict[str, object] = {
        "schema_version": UPSTREAM_PACK_REGISTRY_SCHEMA,
        "registry_id": "r6-matchup-seven-source-packs-v1",
        "pack_count": len(packs),
        "packs": packs,
        "pack_manifest_sha256": canonical_sha256(packs),
    }
    return _with_self_hash(body, field="upstream_pack_registry_sha256")


def validate_upstream_pack_registry_v1(value: object) -> dict[str, object]:
    expected = frozen_upstream_pack_registry_v1()
    item = _mapping(value, label="upstream pack registry")
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("upstream pack registry differs from the frozen seven-pack law")
    return expected


def _positive_scalar(value: object, *, label: str) -> object:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float) and math.isfinite(value):
        return value
    _fail(f"{label} must be a finite JSON scalar")


def build_upstream_pack_rows_v1(
    *,
    pack_id: str,
    slices: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Canonicalize one complete positive source-pack row object."""
    registry = frozen_upstream_pack_registry_v1()
    definitions = {
        str(entry["pack_id"]): entry for entry in registry["packs"]
    }
    normalized_pack_id = _identifier(pack_id, label="pack rows ID")
    if normalized_pack_id not in definitions:
        _fail("pack rows ID is not registered")
    definition = definitions[normalized_pack_id]
    schemas = _sequence(
        definition["positive_row_schemas"], label="positive row schemas"
    )
    raw_slices = _sequence(slices, label="upstream pack row slices")
    if len(raw_slices) != len(schemas):
        _fail("upstream pack rows require every registered slice exactly once")
    normalized_slices: list[dict[str, object]] = []
    all_row_bytes: set[bytes] = set()
    total = 0
    for ordinal, schema_value in enumerate(schemas):
        schema = _mapping(schema_value, label="positive row schema")
        raw_slice = _mapping(
            raw_slices[ordinal], label=f"upstream pack slice[{ordinal}]"
        )
        _exact_keys(
            raw_slice,
            frozenset({"slice_kind", "rows"}),
            label=f"upstream pack slice[{ordinal}]",
        )
        slice_kind = _string(
            raw_slice["slice_kind"],
            label=f"upstream pack slice[{ordinal}].slice_kind",
        )
        if slice_kind != schema["slice_kind"]:
            _fail("upstream pack row slice order or kind differs")
        expected_fields = frozenset(
            _sequence(schema["row_fields"], label="positive row fields")
        )
        raw_rows = _sequence(
            raw_slice["rows"], label=f"{slice_kind} positive rows"
        )
        if not raw_rows:
            _fail("every registered source-pack slice must contain positive rows")
        normalized_rows: list[dict[str, object]] = []
        for row_ordinal, row_value in enumerate(raw_rows):
            row = _mapping(
                row_value, label=f"{slice_kind} row[{row_ordinal}]"
            )
            _exact_keys(row, expected_fields, label=f"{slice_kind} row")
            normalized_rows.append({
                field: _positive_scalar(
                    row[field], label=f"{slice_kind}.{field}"
                )
                for field in sorted(expected_fields)
            })
        normalized_rows.sort(key=canonical_json_bytes)
        row_bytes = [canonical_json_bytes(row) for row in normalized_rows]
        if len(row_bytes) != len(set(row_bytes)):
            _fail("upstream pack rows contain duplicate positive rows")
        if any(raw in all_row_bytes for raw in row_bytes):
            _fail("upstream pack rows repeat a row across semantic slices")
        all_row_bytes.update(row_bytes)
        total += len(normalized_rows)
        normalized_slices.append({
            "slice_kind": slice_kind,
            "row_schema_sha256": schema["row_schema_sha256"],
            "rows": normalized_rows,
            "row_count": len(normalized_rows),
            "rows_sha256": canonical_sha256(normalized_rows),
        })
    body: dict[str, object] = {
        "schema_version": UPSTREAM_PACK_ROWS_SCHEMA,
        "pack_id": normalized_pack_id,
        "positive_row_schema_manifest_sha256": definition[
            "positive_row_schema_manifest_sha256"
        ],
        "slice_count": len(normalized_slices),
        "slices": normalized_slices,
        "slice_manifest_sha256": canonical_sha256(normalized_slices),
        "row_count": total,
        "rows_sha256": canonical_sha256(
            [row for item in normalized_slices for row in item["rows"]]
        ),
        **_policy(),
    }
    return _with_self_hash(body, field="pack_rows_sha256")


def validate_upstream_pack_rows_v1(
    value: object,
    *,
    expected_pack_id: str | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="upstream pack rows")
    _validate_policy(item, label="upstream pack rows")
    raw_slices = _sequence(item.get("slices"), label="upstream pack row slices")
    rebuilt = build_upstream_pack_rows_v1(
        pack_id=item.get("pack_id"),
        slices=[
            {
                "slice_kind": _mapping(
                    raw, label="upstream pack row slice"
                ).get("slice_kind"),
                "rows": _mapping(
                    raw, label="upstream pack row slice"
                ).get("rows"),
            }
            for raw in raw_slices
        ],
    )
    if rebuilt != item:
        _fail("upstream pack rows canonical replay differs")
    if expected_pack_id is not None and rebuilt["pack_id"] != _identifier(
        expected_pack_id, label="expected pack rows ID"
    ):
        _fail("upstream pack rows differ from expected pack")
    return rebuilt


def _requirement(pack_id: str, slice_kind: str, period_rule: str) -> dict[str, str]:
    return {
        "pack_id": pack_id,
        "slice_kind": slice_kind,
        "period_rule": period_rule,
    }


_FAMILY_DEFINITIONS: Final = (
    (
        "receiver",
        ("WR", "TE"),
        (
            "role_concession",
            "alignment_vulnerability",
            "defender_workload_quality",
            "shell_fit",
        ),
    ),
    (
        "rb",
        ("RB",),
        ("rushing_concession", "receiving_concession", "run_context"),
    ),
    (
        "qb",
        ("QB",),
        ("qb_concession", "pressure_inverted", "secondary"),
    ),
)


def frozen_family_registry_v1() -> dict[str, object]:
    """Return the sole family/component identity used by source and reducer."""
    families: list[dict[str, object]] = []
    for ordinal, (family, positions, components) in enumerate(
        _FAMILY_DEFINITIONS
    ):
        entry_body = {
            "ordinal": ordinal,
            "family": family,
            "positions": list(positions),
            "components": list(components),
            "component_count": len(components),
            "minimum_edge_components": 2,
            "component_orientation": "offense-favorable-percentile",
        }
        families.append({
            **entry_body,
            "family_schema_sha256": canonical_sha256(entry_body),
        })
    body: dict[str, object] = {
        "schema_version": FAMILY_REGISTRY_SCHEMA,
        "registry_id": "r6-matchup-fixed-three-family-ten-component-v1",
        "family_count": len(families),
        "component_count": sum(
            int(family["component_count"]) for family in families
        ),
        "families": families,
        "family_manifest_sha256": canonical_sha256(families),
    }
    return _with_self_hash(body, field="family_registry_sha256")


def validate_family_registry_v1(value: object) -> dict[str, object]:
    expected = frozen_family_registry_v1()
    item = _mapping(value, label="family registry")
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("family registry differs from the fixed family/component law")
    if expected["component_count"] != COMPONENT_ROLE_COUNT:
        _fail("family registry must contain exactly ten components")
    return expected


def family_components_v1() -> dict[str, tuple[str, ...]]:
    registry = frozen_family_registry_v1()
    return {
        str(entry["family"]): tuple(str(value) for value in entry["components"])
        for entry in registry["families"]
    }


def position_family_v1() -> dict[str, str]:
    registry = frozen_family_registry_v1()
    return {
        str(position): str(entry["family"])
        for entry in registry["families"]
        for position in entry["positions"]
    }


_ROLE_DEFINITIONS: Final = (
    (
        "schedule-spine", "target-spine", "infrastructure", None,
        (_requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),),
    ),
    (
        "qb-depth-evidence", "qb-gate", "qb", None,
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(LEGACY_DEPTH_PACK, "legacy-depth", "legacy-depth"),
            _requirement(
                SNAPSHOT_DEPTH_PACK, "snapshot-depth", "snapshot-depth"
            ),
        ),
    ),
    (
        "receiver-role-concession", "component", "receiver", "role_concession",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                SCHEDULE_PACK, "schedule-games", "prior-regular-game-window"
            ),
            _requirement(
                WEEKLY_STATS_PACK,
                "weekly-player-stats",
                "prior-regular-game-window",
            ),
            _requirement(LEGACY_DEPTH_PACK, "legacy-depth", "legacy-depth"),
            _requirement(
                SNAPSHOT_DEPTH_PACK, "snapshot-depth", "snapshot-depth"
            ),
            _requirement(
                FANTASY_POINTS_PACK,
                "fp-route-share",
                "prior-regular-game-window",
            ),
        ),
    ),
    (
        "receiver-alignment-vulnerability",
        "component",
        "receiver",
        "alignment_vulnerability",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                SCHEDULE_PACK, "schedule-games", "prior-regular-game-window"
            ),
            _requirement(
                FANTASY_POINTS_PACK, "fp-alignment", "alignment-w4"
            ),
            _requirement(
                SIS_PACK,
                "sis-defender-alignment",
                "prior-eight-common-defense-games",
            ),
        ),
    ),
    (
        "receiver-defender-workload-quality",
        "component",
        "receiver",
        "defender_workload_quality",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                SCHEDULE_PACK, "schedule-games", "prior-regular-game-window"
            ),
            _requirement(
                FANTASY_POINTS_PACK, "fp-alignment", "alignment-w4"
            ),
            _requirement(
                SIS_PACK,
                "sis-defender-alignment",
                "prior-eight-common-defense-games",
            ),
        ),
    ),
    (
        "receiver-prior-season-shell-fit",
        "component",
        "receiver",
        "shell_fit",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                FANTASY_POINTS_PACK,
                "fp-receiver-shell",
                "prior-season-n-minus-one",
            ),
            _requirement(
                FANTASY_POINTS_PACK,
                "fp-defense-shell",
                "prior-season-n-minus-one",
            ),
        ),
    ),
    (
        "rb-rushing-concession", "component", "rb", "rushing_concession",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                SCHEDULE_PACK, "schedule-games", "prior-regular-game-window"
            ),
            _requirement(
                WEEKLY_STATS_PACK,
                "weekly-player-stats",
                "prior-regular-game-window",
            ),
            _requirement(LEGACY_DEPTH_PACK, "legacy-depth", "legacy-depth"),
            _requirement(
                SNAPSHOT_DEPTH_PACK, "snapshot-depth", "snapshot-depth"
            ),
            _requirement(
                FANTASY_POINTS_PACK,
                "fp-route-share",
                "prior-regular-game-window",
            ),
        ),
    ),
    (
        "rb-receiving-concession", "component", "rb", "receiving_concession",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                SCHEDULE_PACK, "schedule-games", "prior-regular-game-window"
            ),
            _requirement(
                WEEKLY_STATS_PACK,
                "weekly-player-stats",
                "prior-regular-game-window",
            ),
            _requirement(LEGACY_DEPTH_PACK, "legacy-depth", "legacy-depth"),
            _requirement(
                SNAPSHOT_DEPTH_PACK, "snapshot-depth", "snapshot-depth"
            ),
            _requirement(
                FANTASY_POINTS_PACK,
                "fp-route-share",
                "prior-regular-game-window",
            ),
        ),
    ),
    (
        "rb-run-context", "component", "rb", "run_context",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                SCHEDULE_PACK, "schedule-games", "prior-regular-game-window"
            ),
            _requirement(SIS_PACK, "sis-run-context", "prior-eight-games"),
        ),
    ),
    (
        "qb-concession", "component", "qb", "qb_concession",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                SCHEDULE_PACK, "schedule-games", "prior-regular-game-window"
            ),
            _requirement(
                WEEKLY_STATS_PACK,
                "weekly-player-stats",
                "prior-eight-games",
            ),
        ),
    ),
    (
        "qb-pressure-inverted", "component", "qb", "pressure_inverted",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                SCHEDULE_PACK, "schedule-games", "prior-regular-game-window"
            ),
            _requirement(PFR_DEFENSE_PACK, "pfr-pass-rush", "prior-eight-games"),
        ),
    ),
    (
        "qb-secondary", "component", "qb", "secondary",
        (
            _requirement(SCHEDULE_PACK, "schedule-games", "target-slate"),
            _requirement(
                SCHEDULE_PACK, "schedule-games", "prior-regular-game-window"
            ),
            _requirement(PFR_DEFENSE_PACK, "pfr-secondary", "prior-six-games"),
            _requirement(
                PFR_DEFENSE_PACK,
                "pfr-snap-positions",
                "prior-six-games",
            ),
        ),
    ),
)


def frozen_role_registry_v2() -> dict[str, object]:
    family_registry = frozen_family_registry_v1()
    roles: list[dict[str, object]] = []
    for ordinal, definition in enumerate(_ROLE_DEFINITIONS):
        role, population_role, family, component, requirements = definition
        body = {
            "ordinal": ordinal,
            "role": role,
            "population_role": population_role,
            "family": family,
            "component": component,
            "period_requirements": list(requirements),
            "upstream_pack_ids": list(dict.fromkeys(
                requirement["pack_id"] for requirement in requirements
            )),
        }
        roles.append({
            **body,
            "source_role_schema_sha256": canonical_sha256(body),
        })
    body: dict[str, object] = {
        "schema_version": ROLE_REGISTRY_SCHEMA,
        "registry_id": "r6-matchup-fixed-12-role-registry-v2",
        "role_count": ROLE_COUNT,
        "component_role_count": COMPONENT_ROLE_COUNT,
        "family_registry_id": family_registry["registry_id"],
        "family_registry_sha256": family_registry["family_registry_sha256"],
        "roles": roles,
        "role_manifest_sha256": canonical_sha256(roles),
    }
    return _with_self_hash(body, field="role_registry_sha256")


def validate_role_registry_v2(value: object) -> dict[str, object]:
    expected = frozen_role_registry_v2()
    item = _mapping(value, label="role registry")
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("role registry differs from the fixed 12-role registry")
    component_pairs = [
        (entry["family"], entry["component"])
        for entry in expected["roles"]
        if entry["population_role"] == "component"
    ]
    if len(component_pairs) != len(set(component_pairs)):
        _fail("component registry is not one-role-per-component")
    family_components = family_components_v1()
    if set(component_pairs) != {
        (family, component)
        for family, components in family_components.items()
        for component in components
    }:
        _fail("role registry differs from the frozen family registry")
    return expected


def frozen_semantic_registry_v2() -> dict[str, object]:
    laws: dict[str, object] = {
        "target_population": "exact-six-field-structural-catalog-family-only",
        "target_game_spine": (
            "catalog-game-id-exact-schedule-team-opponent-reciprocity"
        ),
        "target_lock": "minimum-kickoff-of-exact-catalog-game-set",
        "source_game_scope": "regular-season-only",
        "source_game_order": "exact-schedule-kickoff-cross-season",
        "source_game_cutoff": "strictly-before-target-lock",
        "history_row_event_binding": (
            "every-game-row-exact-joins-schedule-kickoff-before-order-or-window"
        ),
        "percentile_denominator": "supported-n-minus-one",
        "percentile_numerator": "strictly-less-supported-values",
        "percentile_tie_law": "equal-values-equal-rank",
        "single_supported_value_percentile": 0.0,
        "component_orientation": "offense-favorable",
        "pressure_orientation": "negate-before-ranking",
        "receiver_rb_role_windows": "cross-season-last-one-and-four-strict-prior",
        "receiver_rb_role_primary_score": (
            "unweighted-mean-of-supported-last-one-last-four-and-depth-percentiles"
        ),
        "receiver_rb_role_sensitivities": (
            "retained-last-one-and-last-four-consensus-ranks-and-labels"
        ),
        "receiver_rb_role_window_observation_counts": (
            "each-component-last-one-requires-exactly-one-complete-game;"
            "last-four-requires-exactly-four-complete-games;otherwise-null"
        ),
        "receiver_rb_role_salary_tie_break": "catalog-salary-final-only",
        "source_game_role_peer_population": (
            "exact-source-game-pregame-depth-when-available;otherwise-"
            "strict-prior-target-and-route-evidence-with-latest-prior-team;"
            "postgame-participation-never-defines-peers"
        ),
        "source_game_role_depth_law": (
            "legacy-exact-source-week-or-latest-snapshot-strictly-before-"
            "source-game-day"
        ),
        "minimum_role_components": 2,
        "minimum_role_peer_count": 2,
        "defense_concession_window": "prior-eight-defense-games-cross-season",
        "minimum_defense_games": 4,
        "receiver_rb_concession_metric": "raw-dk-allowed-per-game",
        "defense_component_game_denominator": (
            "complete-observed-role-or-position-games-never-schedule-zero-fill"
        ),
        "fp_alignment_window": "exact-target-w-minus-4-through-w-minus-1",
        "fp_alignment_weeks_1_through_4": "unavailable-not-zero",
        "fp_shell_source_season": "target-season-minus-one-both-sides",
        "sis_alignment_horizon": "common-prior-eight-target-defense-games",
        "sis_alignment_aggregation": "coverage-exposure-weighted",
        "sis_top_two_selection": "dominant-alignment-prior-coverage-workload",
        "sis_top_two_aggregation": "coverage-workload-weighted",
        "sis_top_two_tie_break": "stable-defender-id",
        "sis_shrink_targets": SIS_SHRINK_TARGETS,
        "sis_defender_rate_formula": (
            "(defender-dk-allowed+16.0*league-alignment-dk-per-target)/"
            "(defender-targets+16.0)"
        ),
        "sis_league_prior_population": (
            "all-supported-defense-rows-on-exact-common-prior-eight-"
            "target-defense-game-week-horizon"
        ),
        "sis_defender_workload": "sum-coverage-snaps-on-common-horizon",
        "traded_defender_isolation": "target-defense-team-rows-only",
        "rb_run_context": "attempt-weighted-prior-eight-epa-allowed",
        "qb_secondary": "ratio-of-sums-yards-per-target-prior-six",
        "qb_secondary_minimum_prior_games": 4,
        "player_edge": "unweighted-mean-of-supported-component-percentiles",
        "minimum_player_edge_components": 2,
        "missingness": "registered-null-never-zero",
        "annotation_missingness": (
            "one-explicit-reason-per-component-null;null-reason-for-supported"
        ),
        "qb_gate": "literal-qb-depth1-is-true",
        "historical_evidence": EVIDENCE_CLASS,
        "historical_observation_basis": OBSERVED_AT_BASIS,
        "snapshot_depth_2025_time_law": (
            "latest-snapshot-strictly-before-game-day;"
            "date-only-same-gameday-is-unknown"
        ),
        "historical_authoritative_pit": False,
    }
    body: dict[str, object] = {
        "schema_version": SEMANTIC_REGISTRY_SCHEMA,
        "registry_id": "r6-matchup-corrected-semantic-laws-v2",
        "laws": laws,
        "law_manifest_sha256": canonical_sha256(laws),
    }
    return _with_self_hash(body, field="semantic_registry_sha256")


def validate_semantic_registry_v2(value: object) -> dict[str, object]:
    expected = frozen_semantic_registry_v2()
    item = _mapping(value, label="semantic registry")
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("semantic registry differs from the corrected frozen laws")
    return expected


def _normalize_period_endpoint(
    value: object, *, label: str, allow_none: bool = False,
) -> dict[str, object] | None:
    if value is None:
        if allow_none:
            return None
        _fail(f"{label} must not be null")
    item = _mapping(value, label=label)
    _exact_keys(item, PERIOD_ENDPOINT_FIELDS, label=label)
    season = _exact_int(item["season"], label=f"{label}.season", minimum=2000)
    week_value = item["week"]
    if week_value is None:
        week = None
    else:
        week = _exact_int(week_value, label=f"{label}.week", minimum=1)
        if week > 18:
            _fail(f"{label}.week must be <= 18")
    return {"season": season, "week": week}


def _period_sort_key(value: Mapping[str, object]) -> tuple[int, int]:
    week = value["week"]
    return int(value["season"]), 0 if week is None else int(week)


def _normalize_pack_entry(
    value: object,
    *,
    expected_registry_entry: Mapping[str, object],
    pack_rows_object: Mapping[str, object],
) -> dict[str, object]:
    fields = frozenset({
        "pack_id",
        "source_kind",
        "provenance_kind",
        "positive_row_schemas",
        "positive_row_schema_manifest_sha256",
        "exact_rows_identity",
        "row_count",
        "rows_sha256",
        "source_period_min",
        "source_period_max",
        "warehouse_query_receipt_identity",
        "frozen_artifact_manifest_identities",
        "projection_code_identity",
    })
    item = _mapping(value, label="upstream pack")
    _exact_keys(item, fields, label="upstream pack")
    pack_id = _identifier(item["pack_id"], label="upstream pack ID")
    if (
        pack_id != expected_registry_entry["pack_id"]
        or item["source_kind"] != expected_registry_entry["source_kind"]
        or item["provenance_kind"]
        != expected_registry_entry["provenance_kind"]
        or item["positive_row_schemas"]
        != expected_registry_entry["positive_row_schemas"]
        or item["positive_row_schema_manifest_sha256"]
        != expected_registry_entry["positive_row_schema_manifest_sha256"]
    ):
        _fail(f"upstream pack {pack_id!r} differs from its positive schema")
    period_min = _normalize_period_endpoint(
        item["source_period_min"], label=f"{pack_id} period minimum"
    )
    period_max = _normalize_period_endpoint(
        item["source_period_max"], label=f"{pack_id} period maximum"
    )
    if (
        period_min != expected_registry_entry["source_period_min"]
        or period_max != expected_registry_entry["source_period_max"]
    ):
        _fail(f"upstream pack {pack_id!r} source period differs")
    exact_rows_identity = normalize_object_identity_v2(
        item["exact_rows_identity"], label=f"{pack_id} exact rows"
    )
    exact_rows = validate_upstream_pack_rows_v1(
        pack_rows_object, expected_pack_id=pack_id
    )
    _bind_body_to_identity(
        exact_rows, exact_rows_identity, label=f"{pack_id} exact rows"
    )
    row_count = _exact_int(
        item["row_count"], label=f"{pack_id} row count", minimum=1
    )
    rows_sha = _digest(item["rows_sha256"], label=f"{pack_id} rows SHA")
    if (
        row_count != exact_rows["row_count"]
        or rows_sha != exact_rows["rows_sha256"]
        or exact_rows["positive_row_schema_manifest_sha256"]
        != expected_registry_entry["positive_row_schema_manifest_sha256"]
    ):
        _fail(f"upstream pack {pack_id!r} exact positive rows differ")
    query_identity_value = item["warehouse_query_receipt_identity"]
    artifact_values = _sequence(
        item["frozen_artifact_manifest_identities"],
        label=f"{pack_id} artifact manifest identities",
    )
    if expected_registry_entry["provenance_kind"] == "warehouse-query-receipt":
        if query_identity_value is None or artifact_values:
            _fail(f"upstream pack {pack_id!r} warehouse provenance differs")
        query_identity = normalize_object_identity_v2(
            query_identity_value, label=f"{pack_id} query receipt"
        )
        artifact_identities: list[dict[str, object]] = []
    else:
        if query_identity_value is not None or not artifact_values:
            _fail(f"upstream pack {pack_id!r} artifact provenance differs")
        query_identity = None
        artifact_identities = [
            normalize_object_identity_v2(
                identity, label=f"{pack_id} artifact manifest"
            )
            for identity in artifact_values
        ]
        uris = [str(identity["uri"]) for identity in artifact_identities]
        if uris != sorted(uris) or len(uris) != len(set(uris)):
            _fail(f"upstream pack {pack_id!r} artifact identities differ")
    code = normalize_code_identity_v2(
        item["projection_code_identity"], label=f"{pack_id} projection code"
    )
    return {
        "pack_id": pack_id,
        "source_kind": expected_registry_entry["source_kind"],
        "provenance_kind": expected_registry_entry["provenance_kind"],
        "positive_row_schemas": expected_registry_entry["positive_row_schemas"],
        "positive_row_schema_manifest_sha256": expected_registry_entry[
            "positive_row_schema_manifest_sha256"
        ],
        "exact_rows_identity": exact_rows_identity,
        "row_count": row_count,
        "rows_sha256": rows_sha,
        "source_period_min": period_min,
        "source_period_max": period_max,
        "warehouse_query_receipt_identity": query_identity,
        "frozen_artifact_manifest_identities": artifact_identities,
        "projection_code_identity": code,
    }


def build_upstream_release_v1(
    *,
    release_id: str,
    namespace: str,
    fixed_source_root_identity: Mapping[str, object],
    packs: Sequence[Mapping[str, object]],
    pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    normalized_namespace = _normalize_namespace(namespace)
    registry = frozen_upstream_pack_registry_v1()
    raw_packs = _sequence(packs, label="upstream packs")
    raw_row_objects = _sequence(
        pack_row_objects, label="upstream pack row objects"
    )
    if len(raw_packs) != len(PACK_IDS) or len(raw_row_objects) != len(PACK_IDS):
        _fail("upstream release requires exactly seven packs and row objects")
    normalized = [
        _normalize_pack_entry(
            pack,
            expected_registry_entry=registry["packs"][ordinal],
            pack_rows_object=raw_row_objects[ordinal],
        )
        for ordinal, pack in enumerate(raw_packs)
    ]
    normalized_root = normalize_object_identity_v2(
        fixed_source_root_identity, label="fixed source root"
    )
    for pack in normalized:
        expected_rows_uri = (
            f"{normalized_namespace}packs/{pack['pack_id']}/rows.json"
        )
        if pack["exact_rows_identity"]["uri"] != expected_rows_uri:
            _fail("upstream pack rows identity differs from capture law")
    all_uris = [str(normalized_root["uri"])]
    for pack in normalized:
        all_uris.append(str(pack["exact_rows_identity"]["uri"]))
        if pack["warehouse_query_receipt_identity"] is not None:
            all_uris.append(
                str(pack["warehouse_query_receipt_identity"]["uri"])
            )
        all_uris.extend(
            str(identity["uri"])
            for identity in pack["frozen_artifact_manifest_identities"]
        )
    if len(all_uris) != len(set(all_uris)):
        _fail("upstream release reuses an object URI across semantic roles")
    body: dict[str, object] = {
        "schema_version": UPSTREAM_RELEASE_SCHEMA,
        "release_id": _identifier(release_id, label="upstream release ID"),
        "publication_mode": PUBLICATION_MODE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "namespace": normalized_namespace,
        "fixed_source_root_identity": normalized_root,
        "upstream_pack_registry": registry,
        "upstream_pack_registry_sha256": registry[
            "upstream_pack_registry_sha256"
        ],
        "pack_count": len(PACK_IDS),
        "packs": normalized,
        "pack_manifest_sha256": canonical_sha256(normalized),
        **_policy(),
    }
    return _with_self_hash(body, field="upstream_release_sha256")


def validate_upstream_release_v1(
    value: object,
    *,
    pack_row_objects: Sequence[Mapping[str, object]],
    expected_fixed_source_root_identity: Mapping[str, object] | None = None,
    expected_namespace: str | None = None,
) -> dict[str, object]:
    fields = frozenset({
        "schema_version",
        "release_id",
        "publication_mode",
        "authority_boundary",
        "namespace",
        "fixed_source_root_identity",
        "upstream_pack_registry",
        "upstream_pack_registry_sha256",
        "pack_count",
        "packs",
        "pack_manifest_sha256",
        *POLICY_FIELDS,
        "upstream_release_sha256",
    })
    item = _mapping(value, label="upstream release")
    _exact_keys(item, fields, label="upstream release")
    retained_hash = _validate_self_hash(
        item, field="upstream_release_sha256", label="upstream release"
    )
    _validate_policy(item, label="upstream release")
    if (
        item["schema_version"] != UPSTREAM_RELEASE_SCHEMA
        or item["publication_mode"] != PUBLICATION_MODE
        or item["authority_boundary"] != AUTHORITY_BOUNDARY
    ):
        _fail("upstream release fixed law differs")
    registry = validate_upstream_pack_registry_v1(
        item["upstream_pack_registry"]
    )
    if item["upstream_pack_registry_sha256"] != registry[
        "upstream_pack_registry_sha256"
    ]:
        _fail("upstream pack registry hash differs")
    raw_packs = _sequence(item["packs"], label="upstream release packs")
    raw_row_objects = _sequence(
        pack_row_objects, label="upstream pack row objects"
    )
    if (
        item["pack_count"] != len(PACK_IDS)
        or len(raw_packs) != len(PACK_IDS)
        or len(raw_row_objects) != len(PACK_IDS)
    ):
        _fail("upstream release must contain exactly seven packs")
    packs = [
        _normalize_pack_entry(
            pack,
            expected_registry_entry=registry["packs"][ordinal],
            pack_rows_object=raw_row_objects[ordinal],
        )
        for ordinal, pack in enumerate(raw_packs)
    ]
    if item["pack_manifest_sha256"] != canonical_sha256(packs):
        _fail("upstream release pack manifest differs")
    root = normalize_object_identity_v2(
        item["fixed_source_root_identity"], label="fixed source root"
    )
    namespace = _normalize_namespace(item["namespace"])
    if expected_fixed_source_root_identity is not None and root != (
        normalize_object_identity_v2(
            expected_fixed_source_root_identity, label="expected source root"
        )
    ):
        _fail("upstream release differs from the expected fixed source root")
    if expected_namespace is not None and namespace != _normalize_namespace(
        expected_namespace
    ):
        _fail("upstream release differs from the expected namespace")
    uris = [str(root["uri"])]
    for pack in packs:
        uris.append(str(pack["exact_rows_identity"]["uri"]))
        if pack["warehouse_query_receipt_identity"] is not None:
            uris.append(str(pack["warehouse_query_receipt_identity"]["uri"]))
        uris.extend(
            str(identity["uri"])
            for identity in pack["frozen_artifact_manifest_identities"]
        )
    if len(uris) != len(set(uris)):
        _fail("upstream release reuses an object URI across semantic roles")
    normalized = {
        "schema_version": UPSTREAM_RELEASE_SCHEMA,
        "release_id": _identifier(item["release_id"], label="release ID"),
        "publication_mode": PUBLICATION_MODE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "namespace": namespace,
        "fixed_source_root_identity": root,
        "upstream_pack_registry": registry,
        "upstream_pack_registry_sha256": registry[
            "upstream_pack_registry_sha256"
        ],
        "pack_count": len(PACK_IDS),
        "packs": packs,
        "pack_manifest_sha256": canonical_sha256(packs),
        **_policy(),
        "upstream_release_sha256": retained_hash,
    }
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("upstream release canonical replay differs")
    return normalized


def _pack_by_id(
    upstream_release: Mapping[str, object],
) -> dict[str, Mapping[str, object]]:
    return {
        str(pack["pack_id"]): pack
        for pack in upstream_release["packs"]
    }


def _temporal_eligibility_law(pack_id: str, slice_kind: str) -> str:
    if pack_id == SNAPSHOT_DEPTH_PACK and slice_kind == "snapshot-depth":
        return (
            "latest-snapshot-strictly-before-game-day;"
            "date-only-same-gameday-is-unknown"
        )
    if pack_id == SCHEDULE_PACK and slice_kind == "schedule-games":
        return "kickoff-is-target-or-source-event-never-observation-time"
    return "exact-historical-source-period-only"


def build_historical_source_period_v1(
    *,
    pack_id: str,
    slice_kind: str,
    period_kind: str,
    source_period_min: Mapping[str, object] | None,
    source_period_max: Mapping[str, object] | None,
    upstream_pack_rows_identity: Mapping[str, object],
    exact_slice_identity: Mapping[str, object],
    slice_row_count: int,
    slice_rows_sha256: str,
    row_event_kickoff_times_utc: Sequence[str | None],
) -> dict[str, object]:
    """Build period evidence with row-aligned exact schedule event times."""
    normalized_row_count = _exact_int(
        slice_row_count, label="period slice row count"
    )
    raw_event_times = _sequence(
        row_event_kickoff_times_utc,
        label="period row event kickoff times",
    )
    if len(raw_event_times) != normalized_row_count:
        _fail("period event-kickoff vector must align one-to-one with rows")
    event_times = [
        None
        if value is None
        else _timestamp(value, label="period row event kickoff")
        for value in raw_event_times
    ]
    supported_event_times = [value for value in event_times if value is not None]
    body: dict[str, object] = {
        "schema_version": HISTORICAL_SOURCE_PERIOD_SCHEMA,
        "pack_id": _identifier(pack_id, label="period pack ID"),
        "slice_kind": _identifier(slice_kind, label="period slice kind"),
        "period_kind": _identifier(period_kind, label="period kind"),
        "source_period_min": (
            None
            if source_period_min is None
            else _normalize_period_endpoint(
                source_period_min, label="source period minimum"
            )
        ),
        "source_period_max": (
            None
            if source_period_max is None
            else _normalize_period_endpoint(
                source_period_max, label="source period maximum"
            )
        ),
        "upstream_pack_rows_identity": normalize_object_identity_v2(
            upstream_pack_rows_identity, label="upstream pack rows"
        ),
        "exact_slice_identity": normalize_object_identity_v2(
            exact_slice_identity, label="exact period slice"
        ),
        "slice_row_count": normalized_row_count,
        "slice_rows_sha256": _digest(
            slice_rows_sha256, label="period slice rows SHA"
        ),
        "row_event_kickoff_times_utc": event_times,
        "row_event_kickoff_manifest_sha256": canonical_sha256(event_times),
        "minimum_source_event_time_utc": (
            min(supported_event_times) if supported_event_times else None
        ),
        "maximum_source_event_time_utc": (
            max(supported_event_times) if supported_event_times else None
        ),
        "observed_at_utc": None,
        "observed_at_basis": OBSERVED_AT_BASIS,
        "temporal_eligibility_law": _temporal_eligibility_law(
            pack_id, slice_kind
        ),
        "evidence_class": EVIDENCE_CLASS,
        "authoritative_pit": False,
    }
    if body["slice_rows_sha256"] != body["exact_slice_identity"]["sha256"]:
        _fail("period slice rows differ from their exact object identity")
    if period_kind == "unavailable":
        if (
            body["source_period_min"] is not None
            or body["source_period_max"] is not None
            or body["slice_row_count"] != 0
        ):
            _fail("unavailable period must have null bounds and zero rows")
    elif (
        body["source_period_min"] is None
        or body["source_period_max"] is None
        or _period_sort_key(body["source_period_min"])
        > _period_sort_key(body["source_period_max"])
    ):
        _fail("available period bounds differ")
    return _with_self_hash(body, field="historical_source_period_sha256")


def _expected_period_shape(
    *,
    rule: str,
    slate: Mapping[str, object],
) -> tuple[str, dict[str, object] | None, dict[str, object] | None]:
    season = int(slate["season"])
    week = int(slate["week"])
    target = {"season": season, "week": week}
    if rule == "target-slate":
        return "target-slate", target, target
    if rule == "legacy-depth":
        if season <= 2024:
            return "prelock-snapshot", target, target
        return "unavailable", None, None
    if rule == "snapshot-depth":
        if season == 2025:
            return "prelock-snapshot", target, target
        return "unavailable", None, None
    if rule == "alignment-w4":
        if week <= 4:
            return "unavailable", None, None
        return (
            "alignment-window",
            {"season": season, "week": week - 4},
            {"season": season, "week": week - 1},
        )
    if rule == "prior-season-n-minus-one":
        prior = {"season": season - 1, "week": None}
        return "prior-season-full", prior, prior
    if rule in {
        "prior-regular-game-window",
        "prior-eight-common-defense-games",
        "prior-eight-games",
        "prior-six-games",
    }:
        return "prior-game-window", None, None
    _fail(f"unknown fixed period rule {rule!r}")


def _normalize_historical_source_period(
    value: object,
    *,
    requirement: Mapping[str, object],
    slate: Mapping[str, object],
    upstream_pack: Mapping[str, object],
) -> dict[str, object]:
    fields = frozenset({
        "schema_version",
        "pack_id",
        "slice_kind",
        "period_kind",
        "source_period_min",
        "source_period_max",
        "upstream_pack_rows_identity",
        "exact_slice_identity",
        "slice_row_count",
        "slice_rows_sha256",
        "row_event_kickoff_times_utc",
        "row_event_kickoff_manifest_sha256",
        "minimum_source_event_time_utc",
        "maximum_source_event_time_utc",
        "observed_at_utc",
        "observed_at_basis",
        "temporal_eligibility_law",
        "evidence_class",
        "authoritative_pit",
        "historical_source_period_sha256",
    })
    item = _mapping(value, label="historical source period")
    _exact_keys(item, fields, label="historical source period")
    retained_hash = _validate_self_hash(
        item,
        field="historical_source_period_sha256",
        label="historical source period",
    )
    pack_id = _identifier(item["pack_id"], label="period pack ID")
    slice_kind = _identifier(item["slice_kind"], label="period slice kind")
    if (
        item["schema_version"] != HISTORICAL_SOURCE_PERIOD_SCHEMA
        or pack_id != requirement["pack_id"]
        or slice_kind != requirement["slice_kind"]
        or item["observed_at_utc"] is not None
        or item["observed_at_basis"] != OBSERVED_AT_BASIS
        or item["temporal_eligibility_law"]
        != _temporal_eligibility_law(pack_id, slice_kind)
        or item["evidence_class"] != EVIDENCE_CLASS
        or item["authoritative_pit"] is not False
    ):
        _fail("historical source period provenance differs")
    expected_kind, exact_min, exact_max = _expected_period_shape(
        rule=str(requirement["period_rule"]), slate=slate
    )
    period_kind = _identifier(item["period_kind"], label="period kind")
    period_min = _normalize_period_endpoint(
        item["source_period_min"],
        label="period minimum",
        allow_none=True,
    )
    period_max = _normalize_period_endpoint(
        item["source_period_max"],
        label="period maximum",
        allow_none=True,
    )
    if period_kind != expected_kind:
        _fail("historical source period kind differs from its semantic rule")
    if exact_min is not None:
        if period_min != exact_min or period_max != exact_max:
            _fail("historical source period exact bounds differ")
    elif expected_kind == "unavailable":
        if period_min is not None or period_max is not None:
            _fail("unavailable historical source period must have null bounds")
    else:
        if period_min is None or period_max is None:
            _fail("prior-game source period requires exact bounds")
        if (
            period_min["week"] is None
            or period_max["week"] is None
            or _period_sort_key(period_min) > _period_sort_key(period_max)
        ):
            _fail("prior-game source period bounds differ")
    pack_identity = normalize_object_identity_v2(
        item["upstream_pack_rows_identity"], label="period upstream pack rows"
    )
    if pack_identity != upstream_pack["exact_rows_identity"]:
        _fail("historical period is bound to the wrong upstream pack")
    slice_identity = normalize_object_identity_v2(
        item["exact_slice_identity"], label="period exact slice"
    )
    slice_count = _exact_int(
        item["slice_row_count"], label="period slice row count"
    )
    slice_sha = _digest(item["slice_rows_sha256"], label="period slice SHA")
    if slice_sha != slice_identity["sha256"]:
        _fail("historical period slice identity differs")
    raw_event_times = _sequence(
        item["row_event_kickoff_times_utc"],
        label="historical period row event kickoffs",
    )
    if len(raw_event_times) != slice_count:
        _fail("historical period event-kickoff vector differs from row count")
    event_times = [
        None
        if value is None
        else _timestamp(value, label="historical period row event kickoff")
        for value in raw_event_times
    ]
    supported_event_times = [value for value in event_times if value is not None]
    event_min = min(supported_event_times) if supported_event_times else None
    event_max = max(supported_event_times) if supported_event_times else None
    if (
        item["row_event_kickoff_manifest_sha256"]
        != canonical_sha256(event_times)
        or item["minimum_source_event_time_utc"] != event_min
        or item["maximum_source_event_time_utc"] != event_max
    ):
        _fail("historical period event-kickoff manifest differs")
    if expected_kind == "unavailable":
        if slice_count != 0:
            _fail("unavailable historical period must retain zero rows")
    elif slice_count > int(upstream_pack["row_count"]):
        _fail("historical period slice exceeds its upstream pack")
    normalized = {
        "schema_version": HISTORICAL_SOURCE_PERIOD_SCHEMA,
        "pack_id": pack_id,
        "slice_kind": slice_kind,
        "period_kind": period_kind,
        "source_period_min": period_min,
        "source_period_max": period_max,
        "upstream_pack_rows_identity": pack_identity,
        "exact_slice_identity": slice_identity,
        "slice_row_count": slice_count,
        "slice_rows_sha256": slice_sha,
        "row_event_kickoff_times_utc": event_times,
        "row_event_kickoff_manifest_sha256": canonical_sha256(event_times),
        "minimum_source_event_time_utc": event_min,
        "maximum_source_event_time_utc": event_max,
        "observed_at_utc": None,
        "observed_at_basis": OBSERVED_AT_BASIS,
        "temporal_eligibility_law": _temporal_eligibility_law(
            pack_id, slice_kind
        ),
        "evidence_class": EVIDENCE_CLASS,
        "authoritative_pit": False,
        "historical_source_period_sha256": retained_hash,
    }
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("historical source period canonical replay differs")
    return normalized


def validate_historical_source_period_v1(
    value: object,
    *,
    role: str,
    period_ordinal: int,
    slate: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Validate one period against its frozen role, pack, and target slate."""
    registry = frozen_role_registry_v2()
    definitions = {
        str(entry["role"]): entry for entry in registry["roles"]
    }
    normalized_role = _role_name(role, label="historical period role")
    if normalized_role not in definitions:
        _fail("historical period role is not registered")
    definition = definitions[normalized_role]
    requirements = _sequence(
        definition["period_requirements"], label="role period requirements"
    )
    ordinal = _exact_int(
        period_ordinal, label="historical period ordinal"
    )
    if ordinal >= len(requirements):
        _fail("historical period ordinal is outside its fixed role")
    source_ordinal = (int(slate.get("season", 0)) - 2023) * 18 + (
        int(slate.get("week", 0)) - 1
    )
    try:
        normalized_slate = catalog_v1.expected_slate_for_source_task(
            source_ordinal
        )
    except (TypeError, ValueError, catalog_v1.CorpusR6PlayerCatalogV1Error) as exc:
        raise CorpusR6MatchupSourceV2Error(
            "historical period target slate differs from the fixed lattice"
        ) from exc
    if dict(slate) != normalized_slate:
        _fail("historical period target slate differs from the fixed lattice")
    upstream = validate_upstream_release_v1(
        upstream_source_release, pack_row_objects=upstream_pack_row_objects
    )
    requirement = _mapping(
        requirements[ordinal], label="historical period requirement"
    )
    return _normalize_historical_source_period(
        value,
        requirement=requirement,
        slate=normalized_slate,
        upstream_pack=_pack_by_id(upstream)[str(requirement["pack_id"])],
    )


def build_target_spine_v1(
    *,
    structural_catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    schedule_slice_identity: Mapping[str, object],
    games: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Bind the catalog game set to exact schedule rows and derive its lock."""
    catalog = validate_structural_catalog_v2(structural_catalog)
    catalog_id = _bind_body_to_identity(
        catalog, catalog_identity, label="target-spine catalog"
    )
    upstream = validate_upstream_release_v1(
        upstream_source_release, pack_row_objects=upstream_pack_row_objects
    )
    schedule_pack = _pack_by_id(upstream)[SCHEDULE_PACK]
    expected_pairs: dict[tuple[str, str], set[str]] = {}
    catalog_game_pairs: dict[str, set[tuple[str, str]]] = {}
    for player in catalog["players"]:
        pair = tuple(sorted((str(player["team"]), str(player["opp"]))))
        game_id = str(player["game_id"])
        expected_pairs.setdefault(pair, set()).add(game_id)
        catalog_game_pairs.setdefault(game_id, set()).add(pair)
    if (
        any(len(pairs) != 1 for pairs in catalog_game_pairs.values())
        or any(len(game_ids) != 1 for game_ids in expected_pairs.values())
    ):
        _fail("catalog game identity differs from its unordered team pair")
    raw_games = _sequence(games, label="target schedule games")
    normalized_games: list[dict[str, object]] = []
    for offset, raw in enumerate(raw_games):
        item = _mapping(raw, label=f"target schedule game[{offset}]")
        _exact_keys(
            item,
            frozenset({
                "season",
                "week",
                "game_type",
                "gameday",
                "gametime",
                "game_id",
                "home_team",
                "away_team",
                "kickoff_time_utc",
            }),
            label=f"target schedule game[{offset}]",
        )
        season = _exact_int(
            item["season"], label=f"target schedule game[{offset}].season"
        )
        week = _exact_int(
            item["week"], label=f"target schedule game[{offset}].week", minimum=1
        )
        game_type = _string(
            item["game_type"], label=f"target schedule game[{offset}].game_type"
        )
        gameday = _string(
            item["gameday"], label=f"target schedule game[{offset}].gameday"
        )
        gametime = _string(
            item["gametime"], label=f"target schedule game[{offset}].gametime"
        )
        try:
            game_date = datetime.strptime(gameday, "%Y-%m-%d")
            local_time = datetime.strptime(gametime, "%H:%M").time()
            derived_kickoff = datetime.combine(
                game_date.date(), local_time, tzinfo=ZoneInfo("America/New_York")
            ).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except ValueError as exc:
            raise CorpusR6MatchupSourceV2Error(
                "target schedule game date/time is invalid"
            ) from exc
        kickoff = _timestamp(
            item["kickoff_time_utc"],
            label=f"target schedule game[{offset}].kickoff",
        )
        if (
            season != catalog["slate"]["season"]
            or week != catalog["slate"]["week"]
            or game_type != "REG"
            or game_date.weekday() != 6
            or local_time.strftime("%H:%M") not in {"13:00", "16:05", "16:25"}
            or kickoff != derived_kickoff
        ):
            _fail("target schedule game season/week/main-slate time differs")
        normalized_games.append({
            "season": season,
            "week": week,
            "game_type": game_type,
            "gameday": gameday,
            "gametime": gametime,
            "game_id": _string(
                item["game_id"], label=f"target schedule game[{offset}].game_id"
            ),
            "home_team": _string(
                item["home_team"], label=f"target schedule game[{offset}].home"
            ),
            "away_team": _string(
                item["away_team"], label=f"target schedule game[{offset}].away"
            ),
            "kickoff_time_utc": kickoff,
        })
    game_ids = [str(game["game_id"]) for game in normalized_games]
    game_pairs = [
        tuple(sorted((str(game["home_team"]), str(game["away_team"]))))
        for game in normalized_games
    ]
    if (
        not normalized_games
        or game_ids != sorted(game_ids)
        or len(game_ids) != len(set(game_ids))
        or len(game_pairs) != len(set(game_pairs))
        or set(game_pairs) != set(expected_pairs)
    ):
        _fail("target schedule games differ from the exact catalog game set")
    for game, pair in zip(normalized_games, game_pairs, strict=True):
        if game["home_team"] == game["away_team"] or pair not in expected_pairs:
            _fail("target schedule game team/opponent reciprocity differs")
    schedule_rows_object = next(
        validate_upstream_pack_rows_v1(rows, expected_pack_id=SCHEDULE_PACK)
        for rows in upstream_pack_row_objects
        if _mapping(rows, label="upstream pack rows").get("pack_id")
        == SCHEDULE_PACK
    )
    schedule_rows = next(
        slice_entry["rows"]
        for slice_entry in schedule_rows_object["slices"]
        if slice_entry["slice_kind"] == "schedule-games"
    )
    if any(game not in schedule_rows for game in normalized_games):
        _fail("target schedule slice contains rows outside the frozen pack")
    slice_identity = _bind_value_to_identity(
        normalized_games, schedule_slice_identity, label="target schedule slice"
    )
    lock_time = min(str(game["kickoff_time_utc"]) for game in normalized_games)
    body: dict[str, object] = {
        "schema_version": TARGET_SPINE_SCHEMA,
        "source_task_ordinal": catalog["source_task_ordinal"],
        "task_id": catalog["task_id"],
        "slate": catalog["slate"],
        "catalog_identity": catalog_id,
        "schedule_pack_rows_identity": schedule_pack["exact_rows_identity"],
        "schedule_slice_identity": slice_identity,
        "target_event_time_basis": "exact-schedule-kickoff",
        "observation_evidence_basis": OBSERVED_AT_BASIS,
        "games": normalized_games,
        "game_count": len(normalized_games),
        "game_manifest_sha256": canonical_sha256(normalized_games),
        "canonical_game_keys": ["|".join(pair) for pair in sorted(game_pairs)],
        "canonical_game_key_manifest_sha256": canonical_sha256(
            ["|".join(pair) for pair in sorted(game_pairs)]
        ),
        "lock_time_utc": lock_time,
        **_policy(),
    }
    return _with_self_hash(body, field="target_spine_sha256")


def validate_target_spine_v1(
    value: object,
    *,
    structural_catalog: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    item = _mapping(value, label="target spine")
    retained = _digest(
        item.get("target_spine_sha256"), label="target spine SHA"
    )
    rebuilt = build_target_spine_v1(
        structural_catalog=structural_catalog,
        catalog_identity=item.get("catalog_identity"),
        upstream_source_release=upstream_source_release,
        upstream_pack_row_objects=upstream_pack_row_objects,
        schedule_slice_identity=item.get("schedule_slice_identity"),
        games=item.get("games"),
    )
    if rebuilt["target_spine_sha256"] != retained or rebuilt != item:
        _fail("target spine canonical replay differs")
    _validate_policy(item, label="target spine")
    return rebuilt


def _empty_missingness() -> dict[str, int]:
    return {field: 0 for field in sorted(MISSINGNESS_FIELDS)}


def build_role_entry_v1(
    *,
    role: str,
    source_periods: Sequence[Mapping[str, object]],
    expected_population_count: int,
    retained_rows_sha256: str,
    retained_row_count: int,
    supported_cell_count: int,
    missingness_counts: Mapping[str, object],
) -> dict[str, object]:
    registry = frozen_role_registry_v2()
    roles = {str(entry["role"]): entry for entry in registry["roles"]}
    normalized_role = _role_name(role, label="role entry role")
    if normalized_role not in roles:
        _fail("role entry role is not registered")
    definition = roles[normalized_role]
    periods = _sequence(source_periods, label="role entry source periods")
    period_event_maxima = [
        _mapping(period, label="role source period").get(
            "maximum_source_event_time_utc"
        )
        for period in periods
    ]
    supported_event_maxima = [
        _timestamp(value, label="role source event maximum")
        for value in period_event_maxima if value is not None
    ]
    body: dict[str, object] = {
        "schema_version": ROLE_ENTRY_SCHEMA,
        "ordinal": definition["ordinal"],
        "role": normalized_role,
        "population_role": definition["population_role"],
        "family": definition["family"],
        "component": definition["component"],
        "source_role_schema_sha256": definition[
            "source_role_schema_sha256"
        ],
        "upstream_pack_ids": definition["upstream_pack_ids"],
        "source_periods": periods,
        "source_period_manifest_sha256": canonical_sha256(periods),
        "maximum_source_event_time_utc": (
            max(supported_event_maxima) if supported_event_maxima else None
        ),
        "observed_at_utc": None,
        "observed_at_basis": OBSERVED_AT_BASIS,
        "evidence_class": EVIDENCE_CLASS,
        "authoritative_pit": False,
        "expected_population_count": _exact_int(
            expected_population_count, label="expected population count"
        ),
        "retained_row_count": _exact_int(
            retained_row_count, label="retained role row count"
        ),
        "retained_rows_sha256": _digest(
            retained_rows_sha256, label="retained role rows SHA"
        ),
        "supported_cell_count": _exact_int(
            supported_cell_count, label="supported role cell count"
        ),
        "missingness_counts": dict(missingness_counts),
    }
    return _with_self_hash(body, field="role_entry_sha256")


def _normalize_missingness(
    value: object, *, expected_missing_count: int,
) -> dict[str, int]:
    item = _mapping(value, label="role missingness counts")
    _exact_keys(item, MISSINGNESS_FIELDS, label="role missingness counts")
    result = {
        field: _exact_int(item[field], label=f"missingness {field}")
        for field in sorted(MISSINGNESS_FIELDS)
    }
    if sum(result.values()) != expected_missing_count:
        _fail("role missingness counts do not explain every unsupported cell")
    return result


def _normalize_role_entry(
    value: object,
    *,
    definition: Mapping[str, object],
    slate: Mapping[str, object],
    upstream_release: Mapping[str, object],
) -> dict[str, object]:
    fields = frozenset({
        "schema_version",
        "ordinal",
        "role",
        "population_role",
        "family",
        "component",
        "source_role_schema_sha256",
        "upstream_pack_ids",
        "source_periods",
        "source_period_manifest_sha256",
        "maximum_source_event_time_utc",
        "observed_at_utc",
        "observed_at_basis",
        "evidence_class",
        "authoritative_pit",
        "expected_population_count",
        "retained_row_count",
        "retained_rows_sha256",
        "supported_cell_count",
        "missingness_counts",
        "role_entry_sha256",
    })
    item = _mapping(value, label="role entry")
    _exact_keys(item, fields, label="role entry")
    retained_hash = _validate_self_hash(
        item, field="role_entry_sha256", label="role entry"
    )
    fixed_fields = (
        "ordinal",
        "role",
        "population_role",
        "family",
        "component",
        "source_role_schema_sha256",
        "upstream_pack_ids",
    )
    if (
        item["schema_version"] != ROLE_ENTRY_SCHEMA
        or any(item[field] != definition[field] for field in fixed_fields)
        or item["observed_at_utc"] is not None
        or item["observed_at_basis"] != OBSERVED_AT_BASIS
        or item["evidence_class"] != EVIDENCE_CLASS
        or item["authoritative_pit"] is not False
    ):
        _fail("role entry fixed provenance/registry binding differs")
    raw_periods = _sequence(item["source_periods"], label="role source periods")
    requirements = _sequence(
        definition["period_requirements"], label="role period requirements"
    )
    if len(raw_periods) != len(requirements):
        _fail("role entry period coverage differs")
    packs = _pack_by_id(upstream_release)
    periods = [
        _normalize_historical_source_period(
            period,
            requirement=_mapping(requirements[offset], label="period requirement"),
            slate=slate,
            upstream_pack=packs[str(requirements[offset]["pack_id"])],
        )
        for offset, period in enumerate(raw_periods)
    ]
    period_event_maxima = [
        period["maximum_source_event_time_utc"]
        for period in periods
        if period["maximum_source_event_time_utc"] is not None
    ]
    expected_event_maximum = (
        max(period_event_maxima) if period_event_maxima else None
    )
    if item["source_period_manifest_sha256"] != canonical_sha256(periods):
        _fail("role source-period manifest differs")
    expected_count = _exact_int(
        item["expected_population_count"], label="expected population count"
    )
    retained_count = _exact_int(
        item["retained_row_count"], label="retained row count"
    )
    supported_count = _exact_int(
        item["supported_cell_count"], label="supported cell count"
    )
    if retained_count != expected_count or supported_count > expected_count:
        _fail("role entry must retain one row per expected population cell")
    missingness = _normalize_missingness(
        item["missingness_counts"],
        expected_missing_count=expected_count - supported_count,
    )
    normalized = {
        "schema_version": ROLE_ENTRY_SCHEMA,
        **{field: definition[field] for field in fixed_fields},
        "source_periods": periods,
        "source_period_manifest_sha256": canonical_sha256(periods),
        "maximum_source_event_time_utc": expected_event_maximum,
        "observed_at_utc": None,
        "observed_at_basis": OBSERVED_AT_BASIS,
        "evidence_class": EVIDENCE_CLASS,
        "authoritative_pit": False,
        "expected_population_count": expected_count,
        "retained_row_count": retained_count,
        "retained_rows_sha256": _digest(
            item["retained_rows_sha256"], label="retained rows SHA"
        ),
        "supported_cell_count": supported_count,
        "missingness_counts": missingness,
        "role_entry_sha256": retained_hash,
    }
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("role entry canonical replay differs")
    return normalized


def build_target_or_later_deletion_proof_v1(
    *,
    source_task_ordinal: int,
    target_period: Mapping[str, object],
    full_input_sha256: str,
    deleted_input_sha256: str,
    full_input_row_count: int,
    deleted_input_row_count: int,
    deleted_row_count: int,
    deleted_rows_sha256: str,
    deleted_row_counts_by_pack: Mapping[str, object],
    deleted_row_counts_by_slice: Mapping[str, object],
    full_output_sha256: str,
    deleted_output_sha256: str,
) -> dict[str, object]:
    ordinal = _exact_int(
        source_task_ordinal, label="deletion-proof source task ordinal"
    )
    try:
        slate = catalog_v1.expected_slate_for_source_task(ordinal)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupSourceV2Error(str(exc)) from exc
    normalized_target = _normalize_period_endpoint(
        target_period, label="deletion-proof target period"
    )
    if normalized_target != {
        "season": slate["season"], "week": slate["week"]
    }:
        _fail("deletion-proof target differs from the fixed task lattice")
    pack_counts_value = _mapping(
        deleted_row_counts_by_pack, label="deleted row counts by pack"
    )
    _exact_keys(
        pack_counts_value,
        frozenset(DELETION_PACK_IDS),
        label="deleted row counts by pack",
    )
    pack_counts = {
        pack_id: _exact_int(
            pack_counts_value[pack_id],
            label=f"deleted row count for {pack_id}",
            minimum=1,
        )
        for pack_id in DELETION_PACK_IDS
    }
    slice_counts_value = _mapping(
        deleted_row_counts_by_slice, label="deleted row counts by slice"
    )
    _exact_keys(
        slice_counts_value,
        frozenset(DELETION_SLICE_KINDS),
        label="deleted row counts by slice",
    )
    slice_counts = {
        slice_kind: _exact_int(
            slice_counts_value[slice_kind],
            label=f"deleted row count for {slice_kind}",
            minimum=1,
        )
        for slice_kind in DELETION_SLICE_KINDS
    }
    full_count = _exact_int(
        full_input_row_count, label="full deletion-proof input row count"
    )
    deleted_count = _exact_int(
        deleted_input_row_count,
        label="deleted deletion-proof input row count",
    )
    removed_count = _exact_int(
        deleted_row_count,
        label="deleted target-or-later row count",
        minimum=1,
    )
    if (
        sum(pack_counts.values()) != removed_count
        or sum(slice_counts.values()) != removed_count
        or full_count - deleted_count != removed_count
    ):
        _fail("deletion-proof row accounting differs")
    body: dict[str, object] = {
        "schema_version": DELETION_PROOF_SCHEMA,
        "source_task_ordinal": ordinal,
        "target_period": normalized_target,
        "source_systems": ["weekly_stats", "sis", "pfr"],
        "full_input_pack_ids": list(PACK_IDS),
        "deletable_pack_ids": list(DELETION_PACK_IDS),
        "deletion_slice_kinds": list(DELETION_SLICE_KINDS),
        "deletion_predicate": "season-week-greater-than-or-equal-target",
        "physically_rebuilt_pack_bodies": True,
        "same_reducer_replayed": True,
        "full_input_sha256": _digest(
            full_input_sha256, label="full deletion-proof input SHA"
        ),
        "deleted_input_sha256": _digest(
            deleted_input_sha256, label="deleted deletion-proof input SHA"
        ),
        "full_input_row_count": full_count,
        "deleted_input_row_count": deleted_count,
        "deleted_row_count": removed_count,
        "deleted_rows_sha256": _digest(
            deleted_rows_sha256, label="deleted target-or-later rows SHA"
        ),
        "deleted_row_counts_by_pack": pack_counts,
        "deleted_row_counts_by_slice": slice_counts,
        "full_output_sha256": _digest(
            full_output_sha256, label="full deletion-proof output SHA"
        ),
        "deleted_output_sha256": _digest(
            deleted_output_sha256, label="deleted deletion-proof output SHA"
        ),
        "target_or_later_deletion_invariant": True,
    }
    if body["full_output_sha256"] != body["deleted_output_sha256"]:
        _fail("target-or-later deletion changes producer output")
    if body["full_input_sha256"] == body["deleted_input_sha256"]:
        _fail("deleted target-or-later rows did not change the input identity")
    return _with_self_hash(body, field="deletion_proof_sha256")


def validate_target_or_later_deletion_proof_v1(
    value: object,
) -> dict[str, object]:
    fields = frozenset({
        "schema_version",
        "source_task_ordinal",
        "target_period",
        "source_systems",
        "full_input_pack_ids",
        "deletable_pack_ids",
        "deletion_slice_kinds",
        "deletion_predicate",
        "physically_rebuilt_pack_bodies",
        "same_reducer_replayed",
        "full_input_sha256",
        "deleted_input_sha256",
        "full_input_row_count",
        "deleted_input_row_count",
        "deleted_row_count",
        "deleted_rows_sha256",
        "deleted_row_counts_by_pack",
        "deleted_row_counts_by_slice",
        "full_output_sha256",
        "deleted_output_sha256",
        "target_or_later_deletion_invariant",
        "deletion_proof_sha256",
    })
    item = _mapping(value, label="deletion proof")
    _exact_keys(item, fields, label="deletion proof")
    _validate_self_hash(
        item, field="deletion_proof_sha256", label="deletion proof"
    )
    rebuilt = build_target_or_later_deletion_proof_v1(
        source_task_ordinal=item["source_task_ordinal"],
        target_period=item["target_period"],
        full_input_sha256=item["full_input_sha256"],
        deleted_input_sha256=item["deleted_input_sha256"],
        full_input_row_count=item["full_input_row_count"],
        deleted_input_row_count=item["deleted_input_row_count"],
        deleted_row_count=item["deleted_row_count"],
        deleted_rows_sha256=item["deleted_rows_sha256"],
        deleted_row_counts_by_pack=item["deleted_row_counts_by_pack"],
        deleted_row_counts_by_slice=item["deleted_row_counts_by_slice"],
        full_output_sha256=item["full_output_sha256"],
        deleted_output_sha256=item["deleted_output_sha256"],
    )
    if (
        item["schema_version"] != DELETION_PROOF_SCHEMA
        or item["source_systems"] != ["weekly_stats", "sis", "pfr"]
        or item["full_input_pack_ids"] != list(PACK_IDS)
        or item["deletable_pack_ids"] != list(DELETION_PACK_IDS)
        or item["deletion_slice_kinds"] != list(DELETION_SLICE_KINDS)
        or item["deletion_predicate"]
        != "season-week-greater-than-or-equal-target"
        or item["physically_rebuilt_pack_bodies"] is not True
        or item["same_reducer_replayed"] is not True
        or item["target_or_later_deletion_invariant"] is not True
        or rebuilt != item
    ):
        _fail("target-or-later deletion proof differs")
    return rebuilt


def build_accepted_candidate_artifact_v1(
    *,
    source_task_ordinal: int,
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    try:
        slate = catalog_v1.expected_slate_for_source_task(source_task_ordinal)
        task_id = catalog_v1.task_id_for_source_task(source_task_ordinal)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupSourceV2Error(str(exc)) from exc
    raw_rows = _sequence(rows, label="accepted candidate artifact rows")
    if not raw_rows:
        _fail("accepted candidate artifact must contain candidates")
    normalized: list[dict[str, object]] = []
    for ordinal, row_value in enumerate(raw_rows):
        row = _mapping(row_value, label=f"candidate artifact row[{ordinal}]")
        _exact_keys(
            row,
            frozenset({"candidate_id", "player_ids"}),
            label=f"candidate artifact row[{ordinal}]",
        )
        candidate_id = _string(
            row["candidate_id"], label="accepted candidate ID"
        )
        raw_player_ids = _sequence(
            row["player_ids"], label="accepted candidate player IDs"
        )
        player_ids = [
            _string(player_id, label="accepted candidate player ID")
            for player_id in raw_player_ids
        ]
        if len(player_ids) != 9 or len(player_ids) != len(set(player_ids)):
            _fail("accepted candidate roster must contain nine unique players")
        normalized.append({
            "candidate_id": candidate_id,
            "player_ids": player_ids,
            "roster_sha256": canonical_sha256(player_ids),
        })
    candidate_ids = [str(row["candidate_id"]) for row in normalized]
    if len(candidate_ids) != len(set(candidate_ids)):
        _fail("accepted candidate artifact repeats a candidate ID")
    body: dict[str, object] = {
        "schema_version": ACCEPTED_CANDIDATE_ARTIFACT_SCHEMA,
        "source_task_ordinal": source_task_ordinal,
        "task_id": task_id,
        "slate": slate,
        "rows": normalized,
        "candidate_count": len(normalized),
        "ordered_candidate_ids_sha256": canonical_sha256(candidate_ids),
        "candidate_row_manifest_sha256": canonical_sha256(normalized),
        **_policy(),
    }
    return _with_self_hash(body, field="candidate_artifact_sha256")


def validate_accepted_candidate_artifact_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="accepted candidate artifact")
    _validate_policy(item, label="accepted candidate artifact")
    rows = _sequence(item.get("rows"), label="accepted candidate rows")
    rebuilt = build_accepted_candidate_artifact_v1(
        source_task_ordinal=item.get("source_task_ordinal"),
        rows=[{
            "candidate_id": _mapping(row, label="accepted candidate row").get(
                "candidate_id"
            ),
            "player_ids": _mapping(row, label="accepted candidate row").get(
                "player_ids"
            ),
        } for row in rows],
    )
    if rebuilt != item:
        _fail("accepted candidate artifact canonical replay differs")
    return rebuilt


def _normalize_accepted_candidate_entry(
    value: object,
    *,
    expected_ordinal: int,
) -> dict[str, object]:
    item = _mapping(value, label="accepted candidate release entry")
    _exact_keys(
        item,
        frozenset({
            "source_task_ordinal",
            "task_id",
            "slate",
            "catalog_identity",
            "candidate_artifact",
            "candidate_artifact_identity",
            "candidate_count",
            "ordered_candidate_ids_sha256",
            "accepted_candidate_release_entry_sha256",
        }),
        label="accepted candidate release entry",
    )
    ordinal = _exact_int(
        item["source_task_ordinal"], label="candidate source task ordinal"
    )
    if ordinal != expected_ordinal:
        _fail("accepted candidate release entries differ from fixed order")
    try:
        slate = catalog_v1.expected_slate_for_source_task(ordinal)
        task_id = catalog_v1.task_id_for_source_task(ordinal)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupSourceV2Error(str(exc)) from exc
    artifact = validate_accepted_candidate_artifact_v1(
        item["candidate_artifact"]
    )
    if artifact["source_task_ordinal"] != ordinal:
        _fail("accepted candidate artifact differs from release task")
    artifact_identity = _bind_body_to_identity(
        artifact,
        item["candidate_artifact_identity"],
        label="accepted candidate artifact",
    )
    body: dict[str, object] = {
        "source_task_ordinal": ordinal,
        "task_id": task_id,
        "slate": slate,
        "catalog_identity": normalize_object_identity_v2(
            item["catalog_identity"], label="candidate entry catalog"
        ),
        "candidate_artifact": artifact,
        "candidate_artifact_identity": artifact_identity,
        "candidate_count": _exact_int(
            item["candidate_count"],
            label="accepted candidate count",
            minimum=1,
        ),
        "ordered_candidate_ids_sha256": _digest(
            item["ordered_candidate_ids_sha256"],
            label="accepted ordered candidate IDs SHA",
        ),
    }
    entry_hash = _digest(
        item["accepted_candidate_release_entry_sha256"],
        label="accepted candidate release entry SHA",
    )
    if item["task_id"] != task_id or item["slate"] != slate:
        _fail("accepted candidate release entry differs from fixed lattice")
    if (
        body["candidate_count"] != artifact["candidate_count"]
        or body["ordered_candidate_ids_sha256"]
        != artifact["ordered_candidate_ids_sha256"]
    ):
        _fail("accepted candidate entry differs from exact roster artifact")
    if canonical_sha256(body) != entry_hash:
        _fail("accepted candidate release entry self-hash differs")
    return {**body, "accepted_candidate_release_entry_sha256": entry_hash}


def build_accepted_candidate_release_v1(
    *,
    release_id: str,
    namespace: str,
    source_candidate_panel_identity: Mapping[str, object],
    entries: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    normalized_namespace = _normalize_namespace(namespace)
    raw_entries = _sequence(entries, label="accepted candidate entries")
    if len(raw_entries) != TASK_COUNT:
        _fail("accepted candidate release requires exactly 54 entries")
    normalized = [
        _normalize_accepted_candidate_entry(entry, expected_ordinal=ordinal)
        for ordinal, entry in enumerate(raw_entries)
    ]
    artifact_uris = [
        str(entry["candidate_artifact_identity"]["uri"])
        for entry in normalized
    ]
    if len(artifact_uris) != len(set(artifact_uris)):
        _fail("accepted candidate release repeats an artifact URI")
    for ordinal, entry in enumerate(normalized):
        expected_uri = (
            f"{normalized_namespace}source-task-{ordinal:02d}-"
            f"{entry['slate']['slate_id']}/accepted-candidates.json"
        )
        if entry["candidate_artifact_identity"]["uri"] != expected_uri:
            _fail("accepted candidate artifact URI differs from capture law")
    body: dict[str, object] = {
        "schema_version": ACCEPTED_CANDIDATE_RELEASE_SCHEMA,
        "release_id": _identifier(
            release_id, label="accepted candidate release ID"
        ),
        "publication_mode": PUBLICATION_MODE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "namespace": normalized_namespace,
        "source_candidate_panel_identity": normalize_object_identity_v2(
            source_candidate_panel_identity,
            label="source candidate panel",
        ),
        "task_count": TASK_COUNT,
        "entries": normalized,
        "entry_manifest_sha256": canonical_sha256(normalized),
        **_policy(),
    }
    return _with_self_hash(body, field="accepted_candidate_release_sha256")


def validate_accepted_candidate_release_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="accepted candidate release")
    _validate_policy(item, label="accepted candidate release")
    rebuilt = build_accepted_candidate_release_v1(
        release_id=item.get("release_id"),
        namespace=item.get("namespace"),
        source_candidate_panel_identity=item.get(
            "source_candidate_panel_identity"
        ),
        entries=item.get("entries"),
    )
    if rebuilt != item:
        _fail("accepted candidate release canonical replay differs")
    return rebuilt


def _validate_accepted_candidate_release_body(
    value: object,
    identity: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    release = validate_accepted_candidate_release_v1(value)
    normalized_identity = _bind_body_to_identity(
        release, identity, label="accepted candidate release"
    )
    if normalized_identity["uri"] != (
        f"{release['namespace']}accepted-candidate-release.json"
    ):
        _fail("accepted candidate release identity differs from namespace")
    return release, normalized_identity


def build_candidate_support_binding_v1(
    *,
    source_task_ordinal: int,
    catalog_identity: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
) -> dict[str, object]:
    try:
        slate = catalog_v1.expected_slate_for_source_task(source_task_ordinal)
        task_id = catalog_v1.task_id_for_source_task(source_task_ordinal)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupSourceV2Error(str(exc)) from exc
    release, release_identity = _validate_accepted_candidate_release_body(
        accepted_candidate_release, accepted_candidate_release_identity
    )
    entry = _mapping(
        release["entries"][source_task_ordinal],
        label="accepted candidate release selected entry",
    )
    normalized_catalog_identity = normalize_object_identity_v2(
        catalog_identity, label="candidate-support catalog"
    )
    if entry["catalog_identity"] != normalized_catalog_identity:
        _fail("accepted candidate release entry differs from catalog")
    body: dict[str, object] = {
        "schema_version": CANDIDATE_SUPPORT_BINDING_SCHEMA,
        "source_task_ordinal": source_task_ordinal,
        "task_id": task_id,
        "slate": slate,
        "catalog_identity": normalized_catalog_identity,
        "accepted_candidate_release_identity": release_identity,
        "accepted_candidate_release_entry_sha256": entry[
            "accepted_candidate_release_entry_sha256"
        ],
        "candidate_artifact_identity": entry["candidate_artifact_identity"],
        "candidate_count": entry["candidate_count"],
        "ordered_candidate_ids_sha256": entry[
            "ordered_candidate_ids_sha256"
        ],
        **_policy(),
    }
    return _with_self_hash(body, field="candidate_support_binding_sha256")


def validate_candidate_support_binding_v1(
    value: object,
    *,
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    expected_source_task_ordinal: int | None = None,
    expected_catalog_identity: Mapping[str, object] | None = None,
    expected_candidate_release_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="candidate support binding")
    _validate_policy(item, label="candidate support binding")
    rebuilt = build_candidate_support_binding_v1(
        source_task_ordinal=item.get("source_task_ordinal"),
        catalog_identity=item.get("catalog_identity"),
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
    )
    if rebuilt != item:
        _fail("candidate support binding canonical replay differs")
    if (
        expected_source_task_ordinal is not None
        and rebuilt["source_task_ordinal"] != expected_source_task_ordinal
    ):
        _fail("candidate support binding differs from expected source task")
    if expected_catalog_identity is not None and rebuilt["catalog_identity"] != (
        normalize_object_identity_v2(
            expected_catalog_identity, label="expected candidate catalog"
        )
    ):
        _fail("candidate support binding differs from expected catalog")
    if expected_candidate_release_identity is not None and rebuilt[
        "accepted_candidate_release_identity"
    ] != normalize_object_identity_v2(
        expected_candidate_release_identity,
        label="expected candidate release",
    ):
        _fail("candidate support binding differs from expected candidate root")
    return rebuilt


def build_candidate_support_rows_v1(
    *,
    candidate_support_binding: Mapping[str, object],
    structural_catalog: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    binding = validate_candidate_support_binding_v1(
        candidate_support_binding,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
    )
    catalog = validate_structural_catalog_v2(structural_catalog)
    _bind_body_to_identity(
        catalog, binding["catalog_identity"], label="candidate-support catalog"
    )
    release = validate_accepted_candidate_release_v1(
        accepted_candidate_release
    )
    artifact = release["entries"][binding["source_task_ordinal"]][
        "candidate_artifact"
    ]
    artifact_rows = artifact["rows"]
    catalog_positions = {
        str(player["id"]): str(player["pos"]) for player in catalog["players"]
    }
    roster_qbs: dict[str, str] = {}
    for artifact_row in artifact_rows:
        player_ids = [str(value) for value in artifact_row["player_ids"]]
        if any(player_id not in catalog_positions for player_id in player_ids):
            _fail("accepted candidate roster contains a non-catalog player")
        qb_ids = [
            player_id for player_id in player_ids
            if catalog_positions[player_id] == "QB"
        ]
        if len(qb_ids) != 1:
            _fail("accepted candidate roster must contain exactly one catalog QB")
        roster_qbs[str(artifact_row["candidate_id"])] = qb_ids[0]
    raw_rows = _sequence(rows, label="candidate support rows")
    if len(raw_rows) != binding["candidate_count"]:
        _fail("candidate support rows differ from accepted candidate count")
    normalized: list[dict[str, object]] = []
    for ordinal, row_value in enumerate(raw_rows):
        row = _mapping(row_value, label=f"candidate support row[{ordinal}]")
        _exact_keys(
            row,
            frozenset({
                "candidate_id",
                "qb_player_id",
                "qb_depth_true",
                "supported_matchup_player_count",
                "annotation_completeness",
            }),
            label=f"candidate support row[{ordinal}]",
        )
        candidate_id = _string(
            row["candidate_id"],
            label=f"candidate support row[{ordinal}].candidate_id",
        )
        qb_depth_true = row["qb_depth_true"]
        if type(qb_depth_true) is not bool:
            _fail("candidate QB-depth support must be a literal boolean")
        qb_player_id = _string(
            row["qb_player_id"], label="candidate support QB player ID"
        )
        if roster_qbs.get(candidate_id) != qb_player_id:
            _fail("candidate support QB differs from exact candidate roster")
        supported = _exact_int(
            row["supported_matchup_player_count"],
            label="supported matchup player count",
        )
        completeness = row["annotation_completeness"]
        if (
            isinstance(completeness, bool)
            or not isinstance(completeness, (int, float))
            or not math.isfinite(float(completeness))
            or not 0.0 <= float(completeness) <= 1.0
        ):
            _fail("candidate annotation completeness must be finite in [0,1]")
        normalized.append({
            "candidate_id": candidate_id,
            "qb_player_id": qb_player_id,
            "qb_depth_true": qb_depth_true,
            "supported_matchup_player_count": supported,
            "annotation_completeness": float(completeness),
        })
    candidate_ids = [str(row["candidate_id"]) for row in normalized]
    if len(candidate_ids) != len(set(candidate_ids)):
        _fail("candidate support rows repeat a candidate ID")
    if canonical_sha256(candidate_ids) != binding["ordered_candidate_ids_sha256"]:
        _fail("candidate support row order differs from accepted candidates")
    qualifying_ids = [
        str(row["candidate_id"])
        for row in normalized
        if row["qb_depth_true"] is True
        and row["supported_matchup_player_count"]
        >= MINIMUM_SUPPORTED_MATCHUP_PLAYERS
        and row["annotation_completeness"]
        >= MINIMUM_LINEUP_ANNOTATION_COMPLETENESS
    ]
    body: dict[str, object] = {
        "schema_version": CANDIDATE_SUPPORT_ROWS_SCHEMA,
        "candidate_support_binding_sha256": binding[
            "candidate_support_binding_sha256"
        ],
        "candidate_count": len(normalized),
        "rows": normalized,
        "rows_sha256": canonical_sha256(normalized),
        "qualifying_candidate_count": len(qualifying_ids),
        "qualifying_candidate_ids_sha256": canonical_sha256(qualifying_ids),
        **_policy(),
    }
    return _with_self_hash(body, field="candidate_support_rows_sha256")


def build_admission_support_census_v1(
    *,
    candidate_support_binding: Mapping[str, object],
    structural_catalog: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    candidate_support_rows: Sequence[Mapping[str, object]],
    candidate_support_rows_identity: Mapping[str, object],
) -> dict[str, object]:
    candidate_binding = validate_candidate_support_binding_v1(
        candidate_support_binding,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
    )
    support_rows = build_candidate_support_rows_v1(
        candidate_support_binding=candidate_binding,
        structural_catalog=structural_catalog,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
        rows=candidate_support_rows,
    )
    support_rows_identity = _bind_body_to_identity(
        support_rows,
        candidate_support_rows_identity,
        label="candidate support rows",
    )
    rows = support_rows["rows"]
    supported = {
        "zero": sum(row["supported_matchup_player_count"] == 0 for row in rows),
        "one": sum(row["supported_matchup_player_count"] == 1 for row in rows),
        "two_or_more": sum(
            row["supported_matchup_player_count"] >= 2 for row in rows
        ),
    }
    completeness = {
        "zero": sum(row["annotation_completeness"] == 0.0 for row in rows),
        "between_zero_and_half": sum(
            0.0 < row["annotation_completeness"]
            < MINIMUM_LINEUP_ANNOTATION_COMPLETENESS
            for row in rows
        ),
        "ge_half": sum(
            row["annotation_completeness"]
            >= MINIMUM_LINEUP_ANNOTATION_COMPLETENESS
            for row in rows
        ),
    }
    qualifying = int(support_rows["qualifying_candidate_count"])
    body: dict[str, object] = {
        "schema_version": ADMISSION_SUPPORT_SCHEMA,
        "qb_depth_requirement": "literal-true",
        "minimum_supported_matchup_players": MINIMUM_SUPPORTED_MATCHUP_PLAYERS,
        "minimum_lineup_annotation_completeness": (
            MINIMUM_LINEUP_ANNOTATION_COMPLETENESS
        ),
        "entry_budget": ENTRY_BUDGET,
        "candidate_support_binding": candidate_binding,
        "candidate_support_binding_sha256": candidate_binding[
            "candidate_support_binding_sha256"
        ],
        "candidate_artifact_identity": candidate_binding[
            "candidate_artifact_identity"
        ],
        "candidate_count": candidate_binding["candidate_count"],
        "ordered_candidate_ids_sha256": candidate_binding[
            "ordered_candidate_ids_sha256"
        ],
        "candidate_support_rows": support_rows,
        "candidate_support_rows_identity": support_rows_identity,
        "qb_depth_true_candidate_count": sum(
            row["qb_depth_true"] is True for row in rows
        ),
        "supported_player_distribution": supported,
        "completeness_distribution": completeness,
        "qualifying_candidate_count": qualifying,
        "qualifying_candidate_ids_sha256": support_rows[
            "qualifying_candidate_ids_sha256"
        ],
        "entry_budget_satisfied": qualifying >= ENTRY_BUDGET,
    }
    return _with_self_hash(body, field="admission_support_census_sha256")


def validate_admission_support_census_v1(
    value: object,
    *,
    structural_catalog: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="admission support census")
    _validate_self_hash(
        item,
        field="admission_support_census_sha256",
        label="admission support census",
    )
    support_rows = _mapping(
        item.get("candidate_support_rows"), label="candidate support rows"
    )
    rebuilt = build_admission_support_census_v1(
        candidate_support_binding=item.get("candidate_support_binding"),
        structural_catalog=structural_catalog,
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=accepted_candidate_release_identity,
        candidate_support_rows=support_rows.get("rows"),
        candidate_support_rows_identity=item.get(
            "candidate_support_rows_identity"
        ),
    )
    if rebuilt != item:
        _fail("admission support census canonical replay differs")
    return rebuilt


def _normalize_qb_depth_census(
    value: object, *, expected_qb_player_ids: Sequence[str],
) -> dict[str, object]:
    fields = frozenset({
        "catalog_qb_count",
        "rows",
        "row_manifest_sha256",
        "depth_true_count",
        "depth_false_count",
        "depth_unknown_count",
        "qb_depth_complete",
    })
    item = _mapping(value, label="QB depth census")
    _exact_keys(item, fields, label="QB depth census")
    expected_ids = list(expected_qb_player_ids)
    if not expected_ids or expected_ids != sorted(expected_ids):
        _fail("catalog QB IDs must be positive and ordered")
    raw_rows = _sequence(item["rows"], label="QB depth rows")
    rows: list[dict[str, object]] = []
    for ordinal, row_value in enumerate(raw_rows):
        row = _mapping(row_value, label=f"QB depth row[{ordinal}]")
        _exact_keys(
            row,
            frozenset({"player_id", "qb_depth1"}),
            label=f"QB depth row[{ordinal}]",
        )
        depth = row["qb_depth1"]
        if depth is not None and type(depth) is not bool:
            _fail("QB depth status must be true, false, or null")
        rows.append({
            "player_id": _string(row["player_id"], label="QB depth player ID"),
            "qb_depth1": depth,
        })
    if [row["player_id"] for row in rows] != expected_ids:
        _fail("QB depth rows differ from exact catalog QB IDs")
    total = len(rows)
    true_count = sum(row["qb_depth1"] is True for row in rows)
    false_count = sum(row["qb_depth1"] is False for row in rows)
    unknown_count = sum(row["qb_depth1"] is None for row in rows)
    if (
        item["catalog_qb_count"] != total
        or item["depth_true_count"] != true_count
        or item["depth_false_count"] != false_count
        or item["depth_unknown_count"] != unknown_count
        or item["row_manifest_sha256"] != canonical_sha256(rows)
        or item["qb_depth_complete"] is not (unknown_count == 0)
    ):
        _fail("QB depth census differs from the catalog")
    return {
        "catalog_qb_count": total,
        "rows": rows,
        "row_manifest_sha256": canonical_sha256(rows),
        "depth_true_count": true_count,
        "depth_false_count": false_count,
        "depth_unknown_count": unknown_count,
        "qb_depth_complete": unknown_count == 0,
    }


def _catalog_entry_binding(
    value: object,
    *,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
) -> dict[str, object]:
    item = _mapping(value, label="catalog release entry binding")
    _exact_keys(
        item,
        CATALOG_ENTRY_BINDING_FIELDS,
        label="catalog release entry binding",
    )
    ordinal = _exact_int(
        item["source_task_ordinal"], label="catalog entry source ordinal"
    )
    try:
        expected_slate = catalog_v1.expected_slate_for_source_task(ordinal)
        expected_lane = catalog_v1.expected_lane_for_source_task(ordinal)
        expected_task_id = catalog_v1.task_id_for_source_task(ordinal)
    except catalog_v1.CorpusR6PlayerCatalogV1Error as exc:
        raise CorpusR6MatchupSourceV2Error(str(exc)) from exc
    normalized_identity = normalize_object_identity_v2(
        item["catalog_identity"], label="catalog entry catalog"
    )
    result = {
        "source_task_ordinal": ordinal,
        "task_id": _identifier(item["task_id"], label="catalog entry task ID"),
        "slate": _mapping(item["slate"], label="catalog entry slate"),
        "lane_id": _identifier(item["lane_id"], label="catalog entry lane ID"),
        "lane_ordinal": _exact_int(
            item["lane_ordinal"], label="catalog entry lane ordinal"
        ),
        "task_ordinal": _exact_int(
            item["task_ordinal"], label="catalog entry task ordinal"
        ),
        "accepted_slate_membership_sha256": _digest(
            item["accepted_slate_membership_sha256"],
            label="catalog entry membership SHA",
        ),
        "source_task_authority_sha256": _digest(
            item["source_task_authority_sha256"],
            label="catalog entry source-task SHA",
        ),
        "catalog_identity": normalized_identity,
        "source_catalog_sha256": _digest(
            item["source_catalog_sha256"], label="catalog entry structural SHA"
        ),
        "player_count": _exact_int(
            item["player_count"], label="catalog entry player count", minimum=1
        ),
        "ordered_player_ids_sha256": _digest(
            item["ordered_player_ids_sha256"],
            label="catalog entry player-ID SHA",
        ),
    }
    if (
        result["task_id"] != expected_task_id
        or result["slate"] != expected_slate
        or {key: result[key] for key in expected_lane} != expected_lane
        or result["catalog_identity"] != catalog_identity
        or result["source_task_ordinal"] != catalog["source_task_ordinal"]
        or result["task_id"] != catalog["task_id"]
        or result["slate"] != catalog["slate"]
        or result["task_ordinal"] != catalog["task_ordinal"]
        or result["source_catalog_sha256"] != catalog["source_catalog_sha256"]
        or result["player_count"] != catalog["player_count"]
        or result["ordered_player_ids_sha256"]
        != catalog["ordered_player_ids_sha256"]
    ):
        _fail("catalog release entry differs from the six-field catalog")
    return result


def _family_population_counts(
    catalog: Mapping[str, object],
) -> dict[str, int]:
    result = {family: 0 for family in family_components_v1()}
    position_family = position_family_v1()
    for player in catalog["players"]:
        family = position_family.get(str(player["pos"]))
        if family is not None:
            result[family] += 1
    return result


def _normalize_all_role_entries(
    values: object,
    *,
    slate: Mapping[str, object],
    catalog: Mapping[str, object],
    upstream_release: Mapping[str, object],
    qb_depth_census: Mapping[str, object],
) -> list[dict[str, object]]:
    raw_entries = _sequence(values, label="producer role entries")
    registry = frozen_role_registry_v2()
    if len(raw_entries) != ROLE_COUNT:
        _fail("producer receipt requires exactly 12 ordered role entries")
    entries = [
        _normalize_role_entry(
            entry,
            definition=registry["roles"][ordinal],
            slate=slate,
            upstream_release=upstream_release,
        )
        for ordinal, entry in enumerate(raw_entries)
    ]
    populations = _family_population_counts(catalog)
    game_count = len({str(player["game_id"]) for player in catalog["players"]})
    for entry in entries:
        if entry["role"] == "schedule-spine":
            expected = game_count
        elif entry["role"] == "qb-depth-evidence":
            expected = populations["qb"]
        else:
            expected = populations[str(entry["family"])]
        if entry["expected_population_count"] != expected:
            _fail(f"role {entry['role']!r} population differs from catalog")
    depth_entry = entries[1]
    known_depth = (
        int(qb_depth_census["depth_true_count"])
        + int(qb_depth_census["depth_false_count"])
    )
    if (
        depth_entry["supported_cell_count"] != known_depth
        or depth_entry["missingness_counts"]["unknown_depth"]
        != qb_depth_census["depth_unknown_count"]
    ):
        _fail("QB depth role differs from the QB depth census")
    if int(slate["week"]) <= 4:
        for role in (
            "receiver-alignment-vulnerability",
            "receiver-defender-workload-quality",
        ):
            entry = next(item for item in entries if item["role"] == role)
            if (
                entry["supported_cell_count"] != 0
                or entry["missingness_counts"]["source_unavailable"]
                != entry["expected_population_count"]
            ):
                _fail("W1-W4 alignment must be unavailable, never zero-valued")
    return entries


def _component_support_census(
    role_entries: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    result: list[dict[str, object]] = []
    for entry in role_entries:
        if entry["population_role"] != "component":
            continue
        expected = int(entry["expected_population_count"])
        supported = int(entry["supported_cell_count"])
        rate = 0.0 if expected == 0 else round(supported / expected, 12)
        result.append({
            "role": entry["role"],
            "family": entry["family"],
            "component": entry["component"],
            "expected_population_count": expected,
            "supported_cell_count": supported,
            "support_rate": rate,
        })
    if len(result) != COMPONENT_ROLE_COUNT:
        _fail("component support census must contain exactly ten components")
    return result


def _normalize_annotation_rows_v1(
    values: object,
    *,
    catalog: Mapping[str, object],
    role_entries: Sequence[Mapping[str, object]],
    role_row_objects: Sequence[Mapping[str, object]],
    qb_depth_census: Mapping[str, object],
) -> list[dict[str, object]]:
    """Rebuild every derived annotation field from authenticated role rows."""
    family_components = family_components_v1()
    component_rows: dict[str, dict[str, Mapping[str, object]]] = {}
    bounds: dict[str, list[dict[str, object]]] = {}
    for entry, row_object_value in zip(
        role_entries, role_row_objects, strict=True
    ):
        if entry["population_role"] != "component":
            continue
        component = str(entry["component"])
        row_object = _mapping(row_object_value, label=f"{component} role rows")
        rows = _sequence(row_object["rows"], label=f"{component} rows")
        normalized_component_rows: dict[str, Mapping[str, object]] = {}
        raw_values: dict[str, float] = {}
        for row_value in rows:
            retained_row = _mapping(row_value, label=f"{component} row")
            _exact_keys(
                retained_row,
                frozenset({
                    "gsis_id", "component", "raw_value", "percentile",
                    "supported", "observed_game_count", "missingness_reason",
                }),
                label=f"{component} row",
            )
            player_id = _string(
                retained_row["gsis_id"], label=f"{component} player ID"
            )
            if player_id in normalized_component_rows:
                _fail("component role rows repeat a player")
            raw_value = retained_row["raw_value"]
            if raw_value is not None:
                raw_values[player_id] = _finite_number(
                    raw_value, label=f"{component} raw value"
                )
            observed_count = retained_row["observed_game_count"]
            if observed_count is not None and (
                type(observed_count) is not int or observed_count < 0
            ):
                _fail("component role observed count differs")
            reason = retained_row["missingness_reason"]
            if reason is not None and reason not in MISSINGNESS_FIELDS:
                _fail("component role row has an unregistered missingness reason")
            normalized_component_rows[player_id] = retained_row
        ordered_values = sorted(raw_values.values())
        denominator = len(ordered_values) - 1
        expected_percentiles = {
            player_id: (
                0.0 if denominator == 0
                else sum(other < value for other in ordered_values) / denominator
            )
            for player_id, value in raw_values.items()
        }
        for player_id, retained_row in normalized_component_rows.items():
            expected_supported = player_id in expected_percentiles
            expected_percentile = expected_percentiles.get(player_id)
            if (
                retained_row["component"] != component
                or retained_row["supported"] is not expected_supported
                or retained_row["percentile"] != expected_percentile
                or (
                    expected_supported
                    and retained_row["missingness_reason"] is not None
                )
                or (
                    not expected_supported
                    and retained_row["missingness_reason"] is None
                )
            ):
                _fail("component role row semantics differ")
        component_rows[component] = normalized_component_rows
        bounds[component] = [
            {
                "period_kind": period["period_kind"],
                "source_period_min": period["source_period_min"],
                "source_period_max": period["source_period_max"],
                "minimum_source_event_time_utc": period[
                    "minimum_source_event_time_utc"
                ],
                "maximum_source_event_time_utc": period[
                    "maximum_source_event_time_utc"
                ],
                "row_event_kickoff_manifest_sha256": period[
                    "row_event_kickoff_manifest_sha256"
                ],
                "exact_slice_identity": period["exact_slice_identity"],
                "historical_source_period_sha256": period[
                    "historical_source_period_sha256"
                ],
            }
            for period in entry["source_periods"]
        ]
    depth = {
        str(row["player_id"]): row["qb_depth1"]
        for row in qb_depth_census["rows"]
    }
    position_family = position_family_v1()
    expected_players = [
        player for player in catalog["players"]
        if str(player["pos"]) in position_family
    ]
    expected_players.sort(key=lambda player: str(player["id"]))
    raw_rows = _sequence(values, label="annotation rows")
    if len(raw_rows) != len(expected_players):
        _fail("annotation rows differ from eligible catalog population")
    normalized: list[dict[str, object]] = []
    for player, raw_value in zip(expected_players, raw_rows, strict=True):
        row = _mapping(raw_value, label="annotation row")
        expected_fields = frozenset({
            "gsis_id", "family", "position", "qb_depth1",
            "qb_depth_evidence_class", "raw_component_values",
            "component_observed_game_counts", "component_values",
            "component_support", "component_missingness_reasons",
            "matchup_component_count",
            "matchup_edge_score", "annotation_row_present",
            "component_source_bounds",
        })
        _exact_keys(row, expected_fields, label="annotation row")
        player_id = str(player["id"])
        family = position_family[str(player["pos"])]
        components = family_components[family]
        raw_components = _mapping(
            row["raw_component_values"], label="annotation raw components"
        )
        values_by_component = _mapping(
            row["component_values"], label="annotation component values"
        )
        support = _mapping(
            row["component_support"], label="annotation component support"
        )
        observed = _mapping(
            row["component_observed_game_counts"],
            label="annotation observed counts",
        )
        missingness_reasons = _mapping(
            row["component_missingness_reasons"],
            label="annotation component missingness reasons",
        )
        source_bounds = _mapping(
            row["component_source_bounds"], label="annotation source bounds"
        )
        for mapping_value, label in (
            (raw_components, "raw components"),
            (values_by_component, "component values"),
            (support, "component support"),
            (observed, "observed counts"),
            (missingness_reasons, "component missingness reasons"),
            (source_bounds, "component source bounds"),
        ):
            _exact_keys(mapping_value, frozenset(components), label=label)
        for component in components:
            retained = component_rows[component].get(player_id)
            if retained is None:
                _fail("annotation player is absent from component role rows")
            if (
                raw_components[component] != retained["raw_value"]
                or values_by_component[component] != retained["percentile"]
                or support[component] is not retained["supported"]
                or observed[component] != retained["observed_game_count"]
                or missingness_reasons[component]
                != retained["missingness_reason"]
                or source_bounds[component] != bounds[component]
            ):
                _fail("annotation component differs from role-row evidence")
            count = observed[component]
            if count is not None and (type(count) is not int or count < 0):
                _fail("annotation observed count must be null or nonnegative int")
        retained_values = [
            float(values_by_component[component])
            for component in components if support[component] is True
        ]
        edge = (
            sum(retained_values) / len(retained_values)
            if len(retained_values) >= 2 else None
        )
        expected_depth = depth.get(player_id) if family == "qb" else None
        expected_evidence = (
            EVIDENCE_CLASS if family == "qb" and expected_depth is not None
            else "unknown" if family == "qb" else None
        )
        if (
            row["gsis_id"] != player_id
            or row["family"] != family
            or row["position"] != player["pos"]
            or row["qb_depth1"] is not expected_depth
            or row["qb_depth_evidence_class"] != expected_evidence
            or row["matchup_component_count"] != len(retained_values)
            or row["matchup_edge_score"] != edge
            or row["annotation_row_present"] is not (edge is not None)
        ):
            _fail("annotation final-row semantics differ")
        normalized.append(dict(row))
    normalized.sort(key=lambda row: str(row["gsis_id"]))
    if [row["gsis_id"] for row in normalized] != sorted(
        str(player["id"]) for player in expected_players
    ):
        _fail("annotation rows must be ordered by player ID")
    return normalized


def _validate_component_input_bundle_binding_v1(
    value: object,
    identity: Mapping[str, object],
    *,
    producer_id: str,
    catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    catalog_replay_receipt_identity: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release_identity: Mapping[str, object],
    target_spine: Mapping[str, object],
    role_entries: Sequence[Mapping[str, object]],
    qb_depth_census: Mapping[str, object],
    admission_support_census: Mapping[str, object],
) -> tuple[dict[str, object], dict[str, object]]:
    """Bind the exact embedded producer bundle, not only its asserted hash.

    The source contract deliberately does not import the producer module (the
    producer already imports this module).  It nevertheless owns the exact
    cross-boundary bundle schema and verifies every receipt-relevant body and
    manifest before accepting the bundle identity.
    """
    fields = frozenset({
        "schema_version",
        "producer_id",
        "source_task_ordinal",
        "task_id",
        "slate",
        "lock_time_utc",
        "catalog_identity",
        "catalog_release_identity",
        "catalog_replay_receipt_identity",
        "accepted_candidate_release_identity",
        "upstream_source_release_identity",
        "family_registry",
        "family_registry_sha256",
        "semantic_output",
        "semantic_output_sha256",
        "target_spine",
        "target_spine_sha256",
        "source_slices",
        "source_slice_manifest_sha256",
        "role_entries",
        "role_entry_manifest_sha256",
        "role_row_objects",
        "role_row_manifest_sha256",
        "annotation_rows",
        "annotation_row_count",
        "annotation_rows_sha256",
        "qb_depth_census",
        "admission_support_census",
        *POLICY_FIELDS,
        "input_bundle_sha256",
    })
    item = _mapping(value, label="component input bundle")
    _exact_keys(item, fields, label="component input bundle")
    _reject_outcome_carriers(item, label="component input bundle")
    _validate_self_hash(
        item, field="input_bundle_sha256", label="component input bundle"
    )
    _validate_policy(item, label="component input bundle")
    normalized_identity = _bind_body_to_identity(
        item, identity, label="component input bundle"
    )
    source_slices = _sequence(
        item["source_slices"], label="component input source slices"
    )
    role_rows = _sequence(
        item["role_row_objects"], label="component input role rows"
    )
    annotations = _sequence(
        item["annotation_rows"], label="component input annotations"
    )
    semantic_output = _mapping(
        item["semantic_output"], label="component semantic output"
    )
    _exact_keys(
        semantic_output,
        frozenset({
            "source_task_ordinal", "task_id", "slate", "lock_time_utc",
            "target_games", "target_roles", "qb_depth_census",
            "annotation_rows", "annotation_rows_sha256",
            "raw_component_manifest_sha256",
        }),
        label="component semantic output",
    )
    normalized_roles = [dict(entry) for entry in role_entries]
    family_registry = frozen_family_registry_v1()
    normalized_producer_id = _identifier(producer_id, label="producer ID")
    normalized_catalog_identity = normalize_object_identity_v2(
        catalog_identity, label="bundle expected catalog"
    )
    if (
        item["schema_version"] != PRODUCER_INPUT_BUNDLE_SCHEMA
        or item["producer_id"] != normalized_producer_id
        or item["source_task_ordinal"] != catalog["source_task_ordinal"]
        or item["task_id"] != catalog["task_id"]
        or item["slate"] != catalog["slate"]
        or item["lock_time_utc"] != target_spine["lock_time_utc"]
        or item["catalog_identity"] != normalized_catalog_identity
        or item["catalog_release_identity"]
        != normalize_object_identity_v2(
            catalog_release_identity, label="bundle expected catalog release"
        )
        or item["catalog_replay_receipt_identity"]
        != normalize_object_identity_v2(
            catalog_replay_receipt_identity,
            label="bundle expected catalog replay",
        )
        or item["accepted_candidate_release_identity"]
        != normalize_object_identity_v2(
            accepted_candidate_release_identity,
            label="bundle expected candidate release",
        )
        or item["upstream_source_release_identity"]
        != normalize_object_identity_v2(
            upstream_source_release_identity,
            label="bundle expected upstream release",
        )
        or item["family_registry"] != family_registry
        or item["family_registry_sha256"]
        != family_registry["family_registry_sha256"]
        or item["semantic_output_sha256"]
        != canonical_sha256(semantic_output)
        or semantic_output["source_task_ordinal"]
        != catalog["source_task_ordinal"]
        or semantic_output["task_id"] != catalog["task_id"]
        or semantic_output["slate"] != catalog["slate"]
        or semantic_output["lock_time_utc"] != target_spine["lock_time_utc"]
        or semantic_output["target_games"] != target_spine["games"]
        or semantic_output["qb_depth_census"] != qb_depth_census
        or semantic_output["annotation_rows"] != annotations
        or semantic_output["annotation_rows_sha256"]
        != canonical_sha256(annotations)
        or item["target_spine"] != target_spine
        or item["target_spine_sha256"] != target_spine["target_spine_sha256"]
        or item["source_slice_manifest_sha256"]
        != canonical_sha256(source_slices)
        or item["role_entries"] != normalized_roles
        or item["role_entry_manifest_sha256"]
        != canonical_sha256(normalized_roles)
        or item["role_row_manifest_sha256"] != canonical_sha256(role_rows)
        or item["annotation_row_count"] != len(annotations)
        or item["annotation_rows_sha256"] != canonical_sha256(annotations)
        or item["qb_depth_census"] != qb_depth_census
        or item["admission_support_census"] != admission_support_census
    ):
        _fail("component input bundle canonical cross-binding differs")
    expected_source_periods = [
        (str(role["role"]), period_ordinal, period)
        for role in normalized_roles
        for period_ordinal, period in enumerate(role["source_periods"])
    ]
    if len(source_slices) != len(expected_source_periods):
        _fail("component source-slice bodies differ from role periods")
    source_slice_fields = frozenset({
        "role",
        "period_ordinal",
        "pack_id",
        "slice_kind",
        "rows",
        "row_count",
        "rows_sha256",
        "row_event_kickoff_times_utc",
        "row_event_kickoff_manifest_sha256",
        "exact_slice_identity",
        "historical_source_period_sha256",
    })
    for ordinal, (slice_value, expected) in enumerate(
        zip(source_slices, expected_source_periods, strict=True)
    ):
        role, period_ordinal, period = expected
        slice_entry = _mapping(
            slice_value, label=f"component source slice[{ordinal}]"
        )
        _exact_keys(
            slice_entry,
            source_slice_fields,
            label=f"component source slice[{ordinal}]",
        )
        rows = _sequence(
            slice_entry["rows"],
            label=f"component source slice[{ordinal}].rows",
        )
        event_kickoffs = _sequence(
            slice_entry["row_event_kickoff_times_utc"],
            label=f"component source slice[{ordinal}].event kickoffs",
        )
        normalized_event_kickoffs = [
            None
            if value is None
            else _timestamp(
                value,
                label=f"component source slice[{ordinal}].event kickoff",
            )
            for value in event_kickoffs
        ]
        lock_time = _timestamp(
            target_spine["lock_time_utc"], label="component target lock"
        )
        game_event_slices = {
            "schedule-games", "weekly-player-stats", "fp-route-share",
            "pfr-pass-rush", "pfr-secondary", "pfr-snap-positions",
            "sis-defender-alignment", "sis-run-context",
        }
        exact_identity = normalize_object_identity_v2(
            slice_entry["exact_slice_identity"],
            label=f"component source slice[{ordinal}] identity",
        )
        if (
            slice_entry["role"] != role
            or slice_entry["period_ordinal"] != period_ordinal
            or slice_entry["pack_id"] != period["pack_id"]
            or slice_entry["slice_kind"] != period["slice_kind"]
            or slice_entry["row_count"] != len(rows)
            or slice_entry["row_count"] != period["slice_row_count"]
            or slice_entry["rows_sha256"] != canonical_sha256(rows)
            or slice_entry["rows_sha256"] != period["slice_rows_sha256"]
            or len(event_kickoffs) != len(rows)
            or normalized_event_kickoffs
            != period["row_event_kickoff_times_utc"]
            or slice_entry["row_event_kickoff_manifest_sha256"]
            != canonical_sha256(normalized_event_kickoffs)
            or slice_entry["row_event_kickoff_manifest_sha256"]
            != period["row_event_kickoff_manifest_sha256"]
            or exact_identity != period["exact_slice_identity"]
            or exact_identity["sha256"] != canonical_sha256(rows)
            or exact_identity["bytes"] != len(canonical_json_bytes(rows))
            or slice_entry["historical_source_period_sha256"]
            != period["historical_source_period_sha256"]
        ):
            _fail("component source-slice body differs from its role period")
        if period["period_kind"] == "prior-game-window" and (
            slice_entry["slice_kind"] in game_event_slices
            and (
                any(value is None for value in normalized_event_kickoffs)
                or any(
                    str(value) >= lock_time
                    for value in normalized_event_kickoffs
                    if value is not None
                )
            )
        ):
            _fail("prior-game source rows must exact-bind kickoffs before lock")
        if (
            period["period_kind"] == "target-slate"
            and slice_entry["slice_kind"] == "schedule-games"
            and (
                not normalized_event_kickoffs
                or any(value is None for value in normalized_event_kickoffs)
                or any(
                    str(value) < lock_time
                    for value in normalized_event_kickoffs
                    if value is not None
                )
                or lock_time not in normalized_event_kickoffs
            )
        ):
            _fail("target schedule rows must exact-bind kickoffs at/after lock")
    for ordinal, row_object_value in enumerate(role_rows):
        row_object = _mapping(
            row_object_value, label=f"component role rows[{ordinal}]"
        )
        _exact_keys(
            row_object,
            frozenset({"role", "rows", "row_count", "rows_sha256"}),
            label=f"component role rows[{ordinal}]",
        )
        rows = _sequence(
            row_object["rows"], label=f"component role rows[{ordinal}].rows"
        )
        if (
            row_object["row_count"] != len(rows)
            or row_object["rows_sha256"] != canonical_sha256(rows)
            or ordinal >= len(normalized_roles)
            or row_object["role"] != normalized_roles[ordinal]["role"]
            or row_object["rows_sha256"]
            != normalized_roles[ordinal]["retained_rows_sha256"]
        ):
            _fail("component role-row object differs from its role entry")
    if len(role_rows) != len(normalized_roles):
        _fail("component role-row bodies differ from the complete role panel")
    normalized_annotations = _normalize_annotation_rows_v1(
        annotations,
        catalog=catalog,
        role_entries=normalized_roles,
        role_row_objects=role_rows,
        qb_depth_census=qb_depth_census,
    )
    if annotations != normalized_annotations:
        _fail("component annotations differ from canonical role-row replay")
    return item, normalized_identity


def build_component_producer_receipt_v1(
    *,
    producer_id: str,
    structural_catalog: Mapping[str, object],
    catalog_identity: Mapping[str, object],
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    catalog_replay_receipt_identity: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    upstream_source_release_identity: Mapping[str, object],
    producer_code_identity: Mapping[str, object],
    target_spine: Mapping[str, object],
    role_entries: Sequence[Mapping[str, object]],
    annotation_row_count: int,
    annotation_rows_sha256: str,
    input_bundle: Mapping[str, object],
    input_bundle_identity: Mapping[str, object],
    target_or_later_deletion_proof: Mapping[str, object],
    qb_depth_census: Mapping[str, object],
    admission_support_census: Mapping[str, object],
) -> dict[str, object]:
    normalized_producer_id = _identifier(producer_id, label="producer ID")
    catalog = validate_structural_catalog_v2(structural_catalog)
    catalog_id = _bind_body_to_identity(
        catalog, catalog_identity, label="structural catalog"
    )
    catalog_release_body, catalog_release_id = _validate_catalog_release_body(
        catalog_release, catalog_release_identity
    )
    catalog_replay_id = normalize_object_identity_v2(
        catalog_replay_receipt_identity,
        label="fixed-G0 catalog replay receipt",
    )
    candidate_release_body, candidate_release_id = (
        _validate_accepted_candidate_release_body(
            accepted_candidate_release, accepted_candidate_release_identity
        )
    )
    source_ordinal = int(catalog["source_task_ordinal"])
    raw_catalog_release_entry = _mapping(
        catalog_release_body["entries"][source_ordinal],
        label="exact catalog release entry",
    )
    entry_binding = _catalog_entry_binding(
        {
            field: raw_catalog_release_entry[field]
            for field in CATALOG_ENTRY_BINDING_FIELDS
        },
        catalog=catalog,
        catalog_identity=catalog_id,
    )
    upstream = validate_upstream_release_v1(
        upstream_source_release, pack_row_objects=upstream_pack_row_objects
    )
    upstream_id = _bind_body_to_identity(
        upstream,
        upstream_source_release_identity,
        label="upstream source release",
    )
    if upstream_id["uri"] != f"{upstream['namespace']}upstream-release.json":
        _fail("upstream release identity differs from its namespace")
    code = normalize_code_identity_v2(
        producer_code_identity,
        expected_module_path=PRODUCER_MODULE_PATH,
        label="component producer code",
    )
    normalized_target_spine = validate_target_spine_v1(
        target_spine,
        structural_catalog=catalog,
        upstream_source_release=upstream,
        upstream_pack_row_objects=upstream_pack_row_objects,
    )
    populations = _family_population_counts(catalog)
    catalog_qb_ids = [
        str(player["id"])
        for player in catalog["players"]
        if player["pos"] == "QB"
    ]
    depth_census = _normalize_qb_depth_census(
        qb_depth_census, expected_qb_player_ids=catalog_qb_ids
    )
    entries = _normalize_all_role_entries(
        role_entries,
        slate=catalog["slate"],
        catalog=catalog,
        upstream_release=upstream,
        qb_depth_census=depth_census,
    )
    components = _component_support_census(entries)
    schedule_period = entries[0]["source_periods"][0]
    if (
        normalized_target_spine["schedule_slice_identity"]
        != schedule_period["exact_slice_identity"]
        or normalized_target_spine["game_count"]
        != schedule_period["slice_row_count"]
    ):
        _fail("target spine differs from the schedule-spine role slice")
    deletion_proof = validate_target_or_later_deletion_proof_v1(
        target_or_later_deletion_proof
    )
    admission = validate_admission_support_census_v1(
        admission_support_census,
        structural_catalog=catalog,
        accepted_candidate_release=candidate_release_body,
        accepted_candidate_release_identity=candidate_release_id,
    )
    candidate_binding = validate_candidate_support_binding_v1(
        admission["candidate_support_binding"],
        accepted_candidate_release=candidate_release_body,
        accepted_candidate_release_identity=candidate_release_id,
        expected_source_task_ordinal=source_ordinal,
        expected_catalog_identity=catalog_id,
        expected_candidate_release_identity=candidate_release_id,
    )
    depth_by_qb = {
        str(row["player_id"]): row["qb_depth1"]
        for row in depth_census["rows"]
    }
    if any(
        row["qb_depth_true"] is not (
            depth_by_qb[str(row["qb_player_id"])] is True
        )
        for row in admission["candidate_support_rows"]["rows"]
    ):
        _fail("candidate QB-depth support differs from exact QB depth rows")
    annotation_count = _exact_int(
        annotation_row_count, label="annotation row count"
    )
    eligible_count = sum(populations.values())
    if annotation_count != eligible_count:
        _fail("annotation rows must cover every eligible catalog player")
    role_registry = frozen_role_registry_v2()
    family_registry = frozen_family_registry_v1()
    semantic_registry = frozen_semantic_registry_v2()
    input_body, input_identity = _validate_component_input_bundle_binding_v1(
        input_bundle,
        input_bundle_identity,
        producer_id=normalized_producer_id,
        catalog=catalog,
        catalog_identity=catalog_id,
        catalog_release_identity=catalog_release_id,
        catalog_replay_receipt_identity=catalog_replay_id,
        accepted_candidate_release_identity=candidate_release_id,
        upstream_source_release_identity=upstream_id,
        target_spine=normalized_target_spine,
        role_entries=entries,
        qb_depth_census=depth_census,
        admission_support_census=admission,
    )
    if (
        deletion_proof["source_task_ordinal"] != source_ordinal
        or deletion_proof["target_period"] != {
            "season": catalog["slate"]["season"],
            "week": catalog["slate"]["week"],
        }
        or deletion_proof["full_output_sha256"] != input_identity["sha256"]
        or input_body["annotation_row_count"] != annotation_count
        or input_body["annotation_rows_sha256"]
        != _digest(annotation_rows_sha256, label="annotation rows SHA")
    ):
        _fail("deletion proof output differs from the exact input bundle")
    support_preflight_passed = bool(
        depth_census["qb_depth_complete"]
        and admission["entry_budget_satisfied"]
        and deletion_proof["target_or_later_deletion_invariant"]
    )
    body: dict[str, object] = {
        "schema_version": PRODUCER_RECEIPT_SCHEMA,
        "producer_id": normalized_producer_id,
        "source_task_ordinal": catalog["source_task_ordinal"],
        "task_binding": entry_binding,
        "slate": catalog["slate"],
        "lock_time_utc": normalized_target_spine["lock_time_utc"],
        "target_spine": normalized_target_spine,
        "target_spine_sha256": normalized_target_spine[
            "target_spine_sha256"
        ],
        "catalog_release_identity": catalog_release_id,
        "catalog_replay_receipt_identity": catalog_replay_id,
        "catalog_identity": catalog_id,
        "upstream_source_release_identity": upstream_id,
        "upstream_pack_manifest_sha256": upstream["pack_manifest_sha256"],
        "family_registry": family_registry,
        "family_registry_sha256": family_registry["family_registry_sha256"],
        "role_registry": role_registry,
        "role_registry_sha256": role_registry["role_registry_sha256"],
        "semantic_registry": semantic_registry,
        "semantic_registry_sha256": semantic_registry[
            "semantic_registry_sha256"
        ],
        "producer_code_identity": code,
        "role_entries": entries,
        "role_entry_manifest_sha256": canonical_sha256(entries),
        "annotation_row_count": annotation_count,
        "annotation_rows_sha256": _digest(
            annotation_rows_sha256, label="annotation rows SHA"
        ),
        "input_bundle_identity": input_identity,
        "input_bundle_sha256": input_identity["sha256"],
        "target_or_later_deletion_proof": deletion_proof,
        "qb_depth_census": depth_census,
        "component_support_census": components,
        "component_support_census_sha256": canonical_sha256(components),
        "admission_support_census": admission,
        "accepted_candidate_release_identity": candidate_binding[
            "accepted_candidate_release_identity"
        ],
        "support_preflight_passed": support_preflight_passed,
        **_policy(),
    }
    return _with_self_hash(body, field="producer_receipt_sha256")


def validate_component_producer_receipt_v1(
    value: object,
    *,
    structural_catalog: Mapping[str, object],
    catalog_release: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    input_bundle: Mapping[str, object],
    expected_catalog_release_identity: Mapping[str, object] | None = None,
    expected_catalog_replay_receipt_identity: Mapping[str, object] | None = None,
    expected_candidate_release_identity: Mapping[str, object] | None = None,
    expected_upstream_source_release_identity: Mapping[str, object] | None = None,
    expected_producer_code_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    fields = frozenset({
        "schema_version",
        "producer_id",
        "source_task_ordinal",
        "task_binding",
        "slate",
        "lock_time_utc",
        "target_spine",
        "target_spine_sha256",
        "catalog_release_identity",
        "catalog_replay_receipt_identity",
        "catalog_identity",
        "upstream_source_release_identity",
        "upstream_pack_manifest_sha256",
        "family_registry",
        "family_registry_sha256",
        "role_registry",
        "role_registry_sha256",
        "semantic_registry",
        "semantic_registry_sha256",
        "producer_code_identity",
        "role_entries",
        "role_entry_manifest_sha256",
        "annotation_row_count",
        "annotation_rows_sha256",
        "input_bundle_identity",
        "input_bundle_sha256",
        "target_or_later_deletion_proof",
        "qb_depth_census",
        "component_support_census",
        "component_support_census_sha256",
        "admission_support_census",
        "accepted_candidate_release_identity",
        "support_preflight_passed",
        *POLICY_FIELDS,
        "producer_receipt_sha256",
    })
    item = _mapping(value, label="component producer receipt")
    _exact_keys(item, fields, label="component producer receipt")
    retained_hash = _validate_self_hash(
        item, field="producer_receipt_sha256", label="component producer receipt"
    )
    _validate_policy(item, label="component producer receipt")
    if item["schema_version"] != PRODUCER_RECEIPT_SCHEMA:
        _fail("component producer receipt schema differs")
    catalog = validate_structural_catalog_v2(structural_catalog)
    catalog_id = _bind_body_to_identity(
        catalog, item["catalog_identity"], label="structural catalog"
    )
    catalog_release_body, catalog_release_id = _validate_catalog_release_body(
        catalog_release, item["catalog_release_identity"]
    )
    catalog_replay_id = normalize_object_identity_v2(
        item["catalog_replay_receipt_identity"],
        label="fixed-G0 catalog replay receipt",
    )
    candidate_release_body, candidate_release_id = (
        _validate_accepted_candidate_release_body(
            accepted_candidate_release,
            item["accepted_candidate_release_identity"],
        )
    )
    source_ordinal = int(catalog["source_task_ordinal"])
    raw_catalog_release_entry = _mapping(
        catalog_release_body["entries"][source_ordinal],
        label="exact catalog release entry",
    )
    entry_binding = _catalog_entry_binding(
        {
            field: raw_catalog_release_entry[field]
            for field in CATALOG_ENTRY_BINDING_FIELDS
        },
        catalog=catalog,
        catalog_identity=catalog_id,
    )
    if item["task_binding"] != entry_binding:
        _fail("component receipt task binding differs from catalog release")
    upstream = validate_upstream_release_v1(
        upstream_source_release, pack_row_objects=upstream_pack_row_objects
    )
    upstream_id = _bind_body_to_identity(
        upstream,
        item["upstream_source_release_identity"],
        label="upstream source release",
    )
    if upstream_id["uri"] != f"{upstream['namespace']}upstream-release.json":
        _fail("upstream release identity differs from its namespace")
    code = normalize_code_identity_v2(
        item["producer_code_identity"],
        expected_module_path=PRODUCER_MODULE_PATH,
        label="component producer code",
    )
    if expected_catalog_release_identity is not None and catalog_release_id != (
        normalize_object_identity_v2(
            expected_catalog_release_identity, label="expected catalog release"
        )
    ):
        _fail("component receipt differs from expected catalog release")
    if (
        expected_catalog_replay_receipt_identity is not None
        and catalog_replay_id
        != normalize_object_identity_v2(
            expected_catalog_replay_receipt_identity,
            label="expected fixed-G0 catalog replay receipt",
        )
    ):
        _fail("component receipt differs from expected catalog replay")
    if expected_candidate_release_identity is not None and candidate_release_id != (
        normalize_object_identity_v2(
            expected_candidate_release_identity,
            label="expected candidate release",
        )
    ):
        _fail("component receipt differs from expected candidate release")
    if expected_upstream_source_release_identity is not None and upstream_id != (
        normalize_object_identity_v2(
            expected_upstream_source_release_identity,
            label="expected upstream release",
        )
    ):
        _fail("component receipt differs from expected upstream release")
    if expected_producer_code_identity is not None and code != (
        normalize_code_identity_v2(
            expected_producer_code_identity,
            expected_module_path=PRODUCER_MODULE_PATH,
            label="expected producer code",
        )
    ):
        _fail("component receipt differs from expected producer code")
    populations = _family_population_counts(catalog)
    catalog_qb_ids = [
        str(player["id"])
        for player in catalog["players"]
        if player["pos"] == "QB"
    ]
    normalized_target_spine = validate_target_spine_v1(
        item["target_spine"],
        structural_catalog=catalog,
        upstream_source_release=upstream,
        upstream_pack_row_objects=upstream_pack_row_objects,
    )
    depth = _normalize_qb_depth_census(
        item["qb_depth_census"], expected_qb_player_ids=catalog_qb_ids
    )
    roles = _normalize_all_role_entries(
        item["role_entries"],
        slate=catalog["slate"],
        catalog=catalog,
        upstream_release=upstream,
        qb_depth_census=depth,
    )
    components = _component_support_census(roles)
    schedule_period = roles[0]["source_periods"][0]
    if (
        normalized_target_spine["schedule_slice_identity"]
        != schedule_period["exact_slice_identity"]
        or normalized_target_spine["game_count"]
        != schedule_period["slice_row_count"]
    ):
        _fail("receipt target spine differs from schedule-spine role")
    deletion = validate_target_or_later_deletion_proof_v1(
        item["target_or_later_deletion_proof"]
    )
    admission = validate_admission_support_census_v1(
        item["admission_support_census"],
        structural_catalog=catalog,
        accepted_candidate_release=candidate_release_body,
        accepted_candidate_release_identity=candidate_release_id,
    )
    candidate_binding = validate_candidate_support_binding_v1(
        admission["candidate_support_binding"],
        accepted_candidate_release=candidate_release_body,
        accepted_candidate_release_identity=candidate_release_id,
        expected_source_task_ordinal=source_ordinal,
        expected_catalog_identity=catalog_id,
        expected_candidate_release_identity=candidate_release_id,
    )
    depth_by_qb = {
        str(row["player_id"]): row["qb_depth1"] for row in depth["rows"]
    }
    if any(
        row["qb_depth_true"] is not (
            depth_by_qb[str(row["qb_player_id"])] is True
        )
        for row in admission["candidate_support_rows"]["rows"]
    ):
        _fail("receipt candidate QB support differs from QB depth rows")
    input_body, input_identity = _validate_component_input_bundle_binding_v1(
        input_bundle,
        item["input_bundle_identity"],
        producer_id=_identifier(item["producer_id"], label="producer ID"),
        catalog=catalog,
        catalog_identity=catalog_id,
        catalog_release_identity=catalog_release_id,
        catalog_replay_receipt_identity=catalog_replay_id,
        accepted_candidate_release_identity=candidate_release_id,
        upstream_source_release_identity=upstream_id,
        target_spine=normalized_target_spine,
        role_entries=roles,
        qb_depth_census=depth,
        admission_support_census=admission,
    )
    if (
        deletion["source_task_ordinal"] != source_ordinal
        or deletion["target_period"] != {
            "season": catalog["slate"]["season"],
            "week": catalog["slate"]["week"],
        }
        or deletion["full_output_sha256"] != input_identity["sha256"]
        or input_body["annotation_row_count"] != item["annotation_row_count"]
        or input_body["annotation_rows_sha256"]
        != item["annotation_rows_sha256"]
    ):
        _fail("receipt deletion proof differs from exact input bundle")
    expected_preflight = bool(
        depth["qb_depth_complete"]
        and admission["entry_budget_satisfied"]
        and deletion["target_or_later_deletion_invariant"]
    )
    family_registry = validate_family_registry_v1(item["family_registry"])
    role_registry = validate_role_registry_v2(item["role_registry"])
    semantic_registry = validate_semantic_registry_v2(item["semantic_registry"])
    annotation_count = _exact_int(
        item["annotation_row_count"], label="annotation row count"
    )
    normalized = {
        "schema_version": PRODUCER_RECEIPT_SCHEMA,
        "producer_id": _identifier(item["producer_id"], label="producer ID"),
        "source_task_ordinal": catalog["source_task_ordinal"],
        "task_binding": entry_binding,
        "slate": catalog["slate"],
        "lock_time_utc": normalized_target_spine["lock_time_utc"],
        "target_spine": normalized_target_spine,
        "target_spine_sha256": normalized_target_spine[
            "target_spine_sha256"
        ],
        "catalog_release_identity": catalog_release_id,
        "catalog_replay_receipt_identity": catalog_replay_id,
        "catalog_identity": catalog_id,
        "upstream_source_release_identity": upstream_id,
        "upstream_pack_manifest_sha256": upstream["pack_manifest_sha256"],
        "family_registry": family_registry,
        "family_registry_sha256": family_registry["family_registry_sha256"],
        "role_registry": role_registry,
        "role_registry_sha256": role_registry["role_registry_sha256"],
        "semantic_registry": semantic_registry,
        "semantic_registry_sha256": semantic_registry[
            "semantic_registry_sha256"
        ],
        "producer_code_identity": code,
        "role_entries": roles,
        "role_entry_manifest_sha256": canonical_sha256(roles),
        "annotation_row_count": annotation_count,
        "annotation_rows_sha256": _digest(
            item["annotation_rows_sha256"], label="annotation rows SHA"
        ),
        "input_bundle_identity": input_identity,
        "input_bundle_sha256": input_identity["sha256"],
        "target_or_later_deletion_proof": deletion,
        "qb_depth_census": depth,
        "component_support_census": components,
        "component_support_census_sha256": canonical_sha256(components),
        "admission_support_census": admission,
        "accepted_candidate_release_identity": candidate_binding[
            "accepted_candidate_release_identity"
        ],
        "support_preflight_passed": expected_preflight,
        **_policy(),
        "producer_receipt_sha256": retained_hash,
    }
    if (
        annotation_count != sum(populations.values())
        or item["source_task_ordinal"] != catalog["source_task_ordinal"]
        or item["slate"] != catalog["slate"]
        or item["lock_time_utc"] != normalized_target_spine["lock_time_utc"]
        or item["target_spine_sha256"]
        != normalized_target_spine["target_spine_sha256"]
        or item["upstream_pack_manifest_sha256"]
        != upstream["pack_manifest_sha256"]
        or item["family_registry_sha256"]
        != family_registry["family_registry_sha256"]
        or item["role_registry_sha256"] != role_registry["role_registry_sha256"]
        or item["semantic_registry_sha256"]
        != semantic_registry["semantic_registry_sha256"]
        or item["role_entry_manifest_sha256"] != canonical_sha256(roles)
        or item["component_support_census"] != components
        or item["component_support_census_sha256"]
        != canonical_sha256(components)
        or item["input_bundle_sha256"] != input_identity["sha256"]
        or item["accepted_candidate_release_identity"]
        != candidate_binding["accepted_candidate_release_identity"]
        or item["support_preflight_passed"] is not expected_preflight
        or canonical_json_bytes(normalized) != canonical_json_bytes(item)
    ):
        _fail("component producer receipt canonical cross-binding differs")
    return normalized


def build_all_54_support_census_v1(
    producer_receipts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    receipts = _sequence(producer_receipts, label="support-census receipts")
    if len(receipts) != TASK_COUNT:
        _fail("all-54 support census requires exactly 54 receipts")
    entries: list[dict[str, object]] = []
    for ordinal, raw in enumerate(receipts):
        receipt = _mapping(raw, label=f"support receipt {ordinal}")
        if receipt.get("source_task_ordinal") != ordinal:
            _fail("support-census receipts differ from source-task order")
        depth = _mapping(receipt.get("qb_depth_census"), label="support depth")
        admission = _mapping(
            receipt.get("admission_support_census"), label="support admission"
        )
        deletion = _mapping(
            receipt.get("target_or_later_deletion_proof"),
            label="support deletion proof",
        )
        entry = {
            "source_task_ordinal": ordinal,
            "slate": receipt.get("slate"),
            "qb_depth_census": depth,
            "component_support_census": receipt.get(
                "component_support_census"
            ),
            "admission_support_census": admission,
            "target_or_later_deletion_invariant": deletion.get(
                "target_or_later_deletion_invariant"
            ),
            "support_preflight_passed": receipt.get(
                "support_preflight_passed"
            ),
        }
        entry["support_entry_sha256"] = canonical_sha256(entry)
        entries.append(entry)
    all_passed = all(entry["support_preflight_passed"] is True for entry in entries)
    body: dict[str, object] = {
        "schema_version": ALL_54_SUPPORT_CENSUS_SCHEMA,
        "task_count": TASK_COUNT,
        "entry_budget": ENTRY_BUDGET,
        "minimum_supported_matchup_players": MINIMUM_SUPPORTED_MATCHUP_PLAYERS,
        "minimum_lineup_annotation_completeness": (
            MINIMUM_LINEUP_ANNOTATION_COMPLETENESS
        ),
        "qb_depth_requirement": "literal-true",
        "entries": entries,
        "entry_manifest_sha256": canonical_sha256(entries),
        "all_slates_passed": all_passed,
        **_policy(),
    }
    return _with_self_hash(body, field="all_54_support_census_sha256")


def validate_all_54_support_census_v1(
    value: object,
    *,
    producer_receipts: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    expected = build_all_54_support_census_v1(producer_receipts)
    item = _mapping(value, label="all-54 support census")
    if canonical_json_bytes(item) != canonical_json_bytes(expected):
        _fail("all-54 support census differs from producer receipts")
    _validate_policy(item, label="all-54 support census")
    return expected


def _producer_capture_prefix(
    namespace: str,
    *,
    source_task_ordinal: int,
    slate_id: str,
) -> str:
    return (
        f"{namespace}source-task-{source_task_ordinal:02d}-{slate_id}/"
    )


def build_producer_release_v1(
    *,
    release_id: str,
    namespace: str,
    catalog_release: Mapping[str, object],
    catalog_release_identity: Mapping[str, object],
    catalog_replay_receipt_identity: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    accepted_candidate_release_identity: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    upstream_source_release_identity: Mapping[str, object],
    producer_code_identity: Mapping[str, object],
    producer_receipts: Sequence[Mapping[str, object]],
    producer_receipt_identities: Sequence[Mapping[str, object]],
    input_bundles: Sequence[Mapping[str, object]],
    structural_catalogs: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    normalized_namespace = _normalize_namespace(namespace)
    catalog_release_body, catalog_release_id = _validate_catalog_release_body(
        catalog_release, catalog_release_identity
    )
    catalog_replay_id = normalize_object_identity_v2(
        catalog_replay_receipt_identity,
        label="fixed-G0 catalog replay receipt",
    )
    candidate_release_body, candidate_release_id = (
        _validate_accepted_candidate_release_body(
            accepted_candidate_release, accepted_candidate_release_identity
        )
    )
    upstream = validate_upstream_release_v1(
        upstream_source_release, pack_row_objects=upstream_pack_row_objects
    )
    upstream_id = _bind_body_to_identity(
        upstream,
        upstream_source_release_identity,
        label="upstream source release",
    )
    if upstream_id["uri"] != f"{upstream['namespace']}upstream-release.json":
        _fail("upstream release identity differs from its namespace")
    code = normalize_code_identity_v2(
        producer_code_identity,
        expected_module_path=PRODUCER_MODULE_PATH,
        label="producer code",
    )
    role_registry = frozen_role_registry_v2()
    family_registry = frozen_family_registry_v1()
    semantic_registry = frozen_semantic_registry_v2()
    receipts = _sequence(producer_receipts, label="producer receipts")
    receipt_ids = _sequence(
        producer_receipt_identities, label="producer receipt identities"
    )
    bundles = _sequence(input_bundles, label="producer input bundles")
    catalogs = _sequence(structural_catalogs, label="structural catalogs")
    if any(
        len(values) != TASK_COUNT
        for values in (receipts, receipt_ids, bundles, catalogs)
    ):
        _fail("producer release requires exactly 54 receipts, bundles, and catalogs")
    entries: list[dict[str, object]] = []
    normalized_receipts: list[dict[str, object]] = []
    for ordinal in range(TASK_COUNT):
        receipt = validate_component_producer_receipt_v1(
            receipts[ordinal],
            structural_catalog=catalogs[ordinal],
            catalog_release=catalog_release_body,
            accepted_candidate_release=candidate_release_body,
            upstream_source_release=upstream,
            upstream_pack_row_objects=upstream_pack_row_objects,
            input_bundle=bundles[ordinal],
            expected_catalog_release_identity=catalog_release_id,
            expected_catalog_replay_receipt_identity=catalog_replay_id,
            expected_candidate_release_identity=candidate_release_id,
            expected_upstream_source_release_identity=upstream_id,
            expected_producer_code_identity=code,
        )
        if receipt["source_task_ordinal"] != ordinal:
            _fail("producer receipt order differs from the fixed 54-task lattice")
        if receipt["support_preflight_passed"] is not True:
            _fail("producer release cannot include a failed support preflight")
        if receipt["accepted_candidate_release_identity"] != candidate_release_id:
            _fail("producer receipt differs from accepted candidate root")
        receipt_identity = _bind_body_to_identity(
            receipt,
            receipt_ids[ordinal],
            label=f"producer receipt {ordinal}",
        )
        capture_prefix = _producer_capture_prefix(
            normalized_namespace,
            source_task_ordinal=ordinal,
            slate_id=str(receipt["slate"]["slate_id"]),
        )
        if (
            receipt_identity["uri"]
            != f"{capture_prefix}producer/component-producer-receipt.json"
            or receipt["input_bundle_identity"]["uri"]
            != f"{capture_prefix}producer/component-input-bundle.json"
        ):
            _fail("producer receipt or input bundle URI differs from capture law")
        source_slices = _sequence(
            _mapping(bundles[ordinal], label="producer input bundle")[
                "source_slices"
            ],
            label=f"producer source slices[{ordinal}]",
        )
        for slice_value in source_slices:
            slice_entry = _mapping(
                slice_value, label=f"producer source slice[{ordinal}]"
            )
            role_definition = next(
                definition
                for definition in role_registry["roles"]
                if definition["role"] == slice_entry["role"]
            )
            expected_slice_uri = (
                f"{capture_prefix}producer/slices/"
                f"{int(role_definition['ordinal']):02d}-"
                f"{int(slice_entry['period_ordinal']):02d}-"
                f"{slice_entry['slice_kind']}.json"
            )
            if slice_entry["exact_slice_identity"]["uri"] != expected_slice_uri:
                _fail("producer source-slice URI differs from capture law")
        if receipt["admission_support_census"][
            "candidate_support_rows_identity"
        ]["uri"] != f"{capture_prefix}producer/candidate-support-rows.json":
            _fail("candidate-support rows URI differs from capture law")
        entries.append({
            "source_task_ordinal": ordinal,
            "task_binding": receipt["task_binding"],
            "slate": receipt["slate"],
            "lock_time_utc": receipt["lock_time_utc"],
            "catalog_identity": receipt["catalog_identity"],
            "producer_receipt_identity": receipt_identity,
            "input_bundle_identity": receipt["input_bundle_identity"],
            "candidate_artifact_identity": receipt[
                "admission_support_census"
            ]["candidate_artifact_identity"],
            "ordered_candidate_ids_sha256": receipt[
                "admission_support_census"
            ]["ordered_candidate_ids_sha256"],
            "qualifying_candidate_count": receipt[
                "admission_support_census"
            ]["qualifying_candidate_count"],
            "qualifying_candidate_ids_sha256": receipt[
                "admission_support_census"
            ]["qualifying_candidate_ids_sha256"],
            "role_entry_manifest_sha256": receipt[
                "role_entry_manifest_sha256"
            ],
            "support_census_sha256": receipt[
                "admission_support_census"
            ]["admission_support_census_sha256"],
            "capture_output_prefix": capture_prefix,
            "support_preflight_passed": True,
        })
        normalized_receipts.append(receipt)
    identity_uris = [
        str(entry[field]["uri"])
        for entry in entries
        for field in (
            "catalog_identity",
            "producer_receipt_identity",
            "input_bundle_identity",
            "candidate_artifact_identity",
        )
    ]
    output_prefixes = [str(entry["capture_output_prefix"]) for entry in entries]
    if (
        len(identity_uris) != len(set(identity_uris))
        or len(output_prefixes) != len(set(output_prefixes))
    ):
        _fail("producer release repeats an object identity or capture prefix")
    producer_ids = {
        str(receipt["producer_id"]) for receipt in normalized_receipts
    }
    if len(producer_ids) != 1:
        _fail("producer release mixes component producer identities")
    normalized_producer_id = next(iter(producer_ids))
    census = build_all_54_support_census_v1(normalized_receipts)
    if census["all_slates_passed"] is not True:
        _fail("producer release all-54 support census did not pass")
    body: dict[str, object] = {
        "schema_version": PRODUCER_RELEASE_SCHEMA,
        "release_id": _identifier(release_id, label="producer release ID"),
        "producer_id": normalized_producer_id,
        "publication_mode": PUBLICATION_MODE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "namespace": normalized_namespace,
        "catalog_release_identity": catalog_release_id,
        "catalog_replay_receipt_identity": catalog_replay_id,
        "accepted_candidate_release_identity": candidate_release_id,
        "upstream_source_release_identity": upstream_id,
        "upstream_pack_manifest_sha256": upstream["pack_manifest_sha256"],
        "family_registry": family_registry,
        "family_registry_sha256": family_registry["family_registry_sha256"],
        "role_registry": role_registry,
        "role_registry_sha256": role_registry["role_registry_sha256"],
        "semantic_registry": semantic_registry,
        "semantic_registry_sha256": semantic_registry[
            "semantic_registry_sha256"
        ],
        "producer_code_identity": code,
        "task_count": TASK_COUNT,
        "entries": entries,
        "entry_manifest_sha256": canonical_sha256(entries),
        "all_54_support_census": census,
        "all_54_support_census_sha256": census[
            "all_54_support_census_sha256"
        ],
        **_policy(),
    }
    return _with_self_hash(body, field="producer_release_sha256")


def validate_producer_release_v1(
    value: object,
    *,
    catalog_release: Mapping[str, object],
    accepted_candidate_release: Mapping[str, object],
    upstream_source_release: Mapping[str, object],
    upstream_pack_row_objects: Sequence[Mapping[str, object]],
    producer_receipts: Sequence[Mapping[str, object]],
    input_bundles: Sequence[Mapping[str, object]],
    structural_catalogs: Sequence[Mapping[str, object]],
    expected_catalog_release_identity: Mapping[str, object],
    expected_catalog_replay_receipt_identity: Mapping[str, object],
    expected_candidate_release_identity: Mapping[str, object],
    expected_upstream_source_release_identity: Mapping[str, object],
    expected_producer_code_identity: Mapping[str, object],
    expected_namespace: str,
) -> dict[str, object]:
    item = _mapping(value, label="producer release")
    retained = _digest(
        item.get("producer_release_sha256"), label="producer release SHA"
    )
    receipt_ids = [
        _mapping(entry, label="producer release entry")[
            "producer_receipt_identity"
        ]
        for entry in _sequence(item.get("entries"), label="producer release entries")
    ]
    rebuilt = build_producer_release_v1(
        release_id=item.get("release_id"),
        namespace=item.get("namespace"),
        catalog_release=catalog_release,
        catalog_release_identity=item.get("catalog_release_identity"),
        catalog_replay_receipt_identity=item.get(
            "catalog_replay_receipt_identity"
        ),
        accepted_candidate_release=accepted_candidate_release,
        accepted_candidate_release_identity=item.get(
            "accepted_candidate_release_identity"
        ),
        upstream_source_release=upstream_source_release,
        upstream_pack_row_objects=upstream_pack_row_objects,
        upstream_source_release_identity=item.get(
            "upstream_source_release_identity"
        ),
        producer_code_identity=item.get("producer_code_identity"),
        producer_receipts=producer_receipts,
        producer_receipt_identities=receipt_ids,
        input_bundles=input_bundles,
        structural_catalogs=structural_catalogs,
    )
    if rebuilt["producer_release_sha256"] != retained or rebuilt != item:
        _fail("producer release canonical replay differs")
    if rebuilt["catalog_release_identity"] != normalize_object_identity_v2(
        expected_catalog_release_identity, label="expected catalog release"
    ):
        _fail("producer release differs from expected catalog root")
    if rebuilt["catalog_replay_receipt_identity"] != (
        normalize_object_identity_v2(
            expected_catalog_replay_receipt_identity,
            label="expected fixed-G0 catalog replay receipt",
        )
    ):
        _fail("producer release differs from expected catalog replay")
    if rebuilt["accepted_candidate_release_identity"] != (
        normalize_object_identity_v2(
            expected_candidate_release_identity,
            label="expected candidate release",
        )
    ):
        _fail("producer release differs from expected candidate root")
    if rebuilt["upstream_source_release_identity"] != normalize_object_identity_v2(
        expected_upstream_source_release_identity,
        label="expected upstream source release",
    ):
        _fail("producer release differs from expected upstream root")
    if rebuilt["producer_code_identity"] != normalize_code_identity_v2(
        expected_producer_code_identity,
        expected_module_path=PRODUCER_MODULE_PATH,
        label="expected producer code",
    ):
        _fail("producer release differs from expected producer code")
    if rebuilt["namespace"] != _normalize_namespace(expected_namespace):
        _fail("producer release differs from expected namespace")
    _validate_policy(rebuilt, label="producer release")
    return rebuilt


__all__ = [
    "ACCEPTED_CANDIDATE_ARTIFACT_SCHEMA",
    "ACCEPTED_CANDIDATE_RELEASE_SCHEMA",
    "ADMISSION_SUPPORT_SCHEMA",
    "ALL_54_SUPPORT_CENSUS_SCHEMA",
    "AUTHORITY_BOUNDARY",
    "COMPONENT_ROLE_COUNT",
    "CANDIDATE_SUPPORT_BINDING_SCHEMA",
    "CANDIDATE_SUPPORT_ROWS_SCHEMA",
    "CorpusR6MatchupSourceV2Error",
    "DELETION_PROOF_SCHEMA",
    "DELETION_PACK_IDS",
    "DELETION_SLICE_KINDS",
    "ENTRY_BUDGET",
    "EVIDENCE_CLASS",
    "FALSE_AUTHORITY_FIELDS",
    "FAMILY_REGISTRY_SCHEMA",
    "HISTORICAL_SOURCE_PERIOD_SCHEMA",
    "OBSERVED_AT_BASIS",
    "PACK_IDS",
    "PRODUCER_MODULE_PATH",
    "PRODUCER_INPUT_BUNDLE_SCHEMA",
    "PRODUCER_RECEIPT_SCHEMA",
    "PRODUCER_RELEASE_SCHEMA",
    "ROLE_COUNT",
    "ROLE_ENTRY_SCHEMA",
    "TASK_COUNT",
    "SIS_SHRINK_TARGETS",
    "TARGET_SPINE_SCHEMA",
    "UPSTREAM_PACK_ROWS_SCHEMA",
    "UPSTREAM_RELEASE_SCHEMA",
    "build_admission_support_census_v1",
    "build_accepted_candidate_artifact_v1",
    "build_accepted_candidate_release_v1",
    "build_all_54_support_census_v1",
    "build_candidate_support_binding_v1",
    "build_candidate_support_rows_v1",
    "build_component_producer_receipt_v1",
    "build_historical_source_period_v1",
    "build_producer_release_v1",
    "build_role_entry_v1",
    "build_target_spine_v1",
    "build_target_or_later_deletion_proof_v1",
    "build_upstream_release_v1",
    "build_upstream_pack_rows_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "family_components_v1",
    "frozen_family_registry_v1",
    "frozen_role_registry_v2",
    "frozen_semantic_registry_v2",
    "frozen_upstream_pack_registry_v1",
    "normalize_code_identity_v2",
    "normalize_object_identity_v2",
    "position_family_v1",
    "validate_admission_support_census_v1",
    "validate_accepted_candidate_artifact_v1",
    "validate_accepted_candidate_release_v1",
    "validate_all_54_support_census_v1",
    "validate_candidate_support_binding_v1",
    "validate_component_producer_receipt_v1",
    "validate_family_registry_v1",
    "validate_historical_source_period_v1",
    "validate_producer_release_v1",
    "validate_role_registry_v2",
    "validate_semantic_registry_v2",
    "validate_structural_catalog_v2",
    "validate_target_spine_v1",
    "validate_target_or_later_deletion_proof_v1",
    "validate_upstream_pack_registry_v1",
    "validate_upstream_pack_rows_v1",
    "validate_upstream_release_v1",
]
