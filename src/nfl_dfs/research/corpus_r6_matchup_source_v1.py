"""Pure corrected matchup-source authority for the R6-v2 research path.

This module implements the two-object seam specified by
``2026-08-24-r6-v2-matchup-pit-lineage-disposition.md``.  It deliberately
does not alter or import the frozen source-blocked R6-v2 release.  Publication
and storage are injected callbacks; there is no cloud client, warehouse
client, object listing, process mutation, or realized-result dependency here.

The seam makes three distinctions explicit:

* the player catalog alone defines the complete target population;
* component extracts retain their exact rows, periods, source roles, and
  observation evidence; and
* a query receipt binds the catalog and source export by full content
  identity rather than by a caller-supplied point-in-time claim.

The current legacy ``corpus-r6-matchup-source-snapshot/v1`` object is not
accepted by this module.  Its bytes and source-blocked disposition remain
unchanged.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from datetime import datetime, timezone
from hashlib import sha256
import json
import math
import re
from typing import Final


SOURCE_EXPORT_SCHEMA: Final = "corpus-r6-matchup-source-export/v1"
QUERY_RECEIPT_SCHEMA: Final = "corpus-r6-matchup-query-receipt/v1"
REOPENED_SOURCE_SCHEMA: Final = "corpus-r6-matchup-reopened-source/v1"
PLAYER_CATALOG_SCHEMA: Final = "corpus-retrieval-player-catalog/v1"
FAMILY_DEFINITION_SCHEMA: Final = "corpus-annotation-metric-family/v1"
SOURCE_ROLE_SCHEMA: Final = "corpus-r6-matchup-source-role-schema/v1"
PUBLICATION_MODE: Final = "create_once"
SCHEDULE_SOURCE_ROLE: Final = "schedule-spine"
QB_DEPTH_SOURCE_ROLE: Final = "qb-depth-evidence"
INFRASTRUCTURE_SOURCE_ROLES: Final = (
    SCHEDULE_SOURCE_ROLE,
    QB_DEPTH_SOURCE_ROLE,
)
QB_DEPTH_UNKNOWN_POLICY: Final = "exclude-qb-from-matchup-admission"
TARGET_WEEK_PARTICIPATION_SYSTEMS: Final = (
    "weekly_stats",
    "sis",
    "pfr",
)

EVIDENCE_NON_PIT: Final = "non-pit-retrospective"
EVIDENCE_RETROSPECTIVE: Final = (
    "retrospective-prior-period-reconstruction"
)
EVIDENCE_CONTEMPORANEOUS: Final = "contemporaneous-prelock"
EVIDENCE_CLASSES: Final = (
    EVIDENCE_NON_PIT,
    EVIDENCE_RETROSPECTIVE,
    EVIDENCE_CONTEMPORANEOUS,
)
_EVIDENCE_RANK: Final = {
    evidence_class: rank
    for rank, evidence_class in enumerate(EVIDENCE_CLASSES)
}

ELIGIBLE_FAMILIES: Final = ("qb", "rb", "receiver")
_FAMILY_ID_BY_FAMILY: Final = {
    "qb": "qb-matchup",
    "rb": "rb-matchup",
    "receiver": "receiver-matchup",
}
_FAMILY_BY_POSITION: Final = {
    "QB": "qb",
    "RB": "rb",
    "WR": "receiver",
    "TE": "receiver",
}

OBSERVED_AT_BASES: Final = (
    "vendor-retrieved-at",
    "raw-object-created-at",
    "warehouse-ingested-at",
    "warehouse-table-modified-at",
    "historical-source-period-only",
    "unknown",
)
_CONTEMPORANEOUS_BASES: Final = frozenset({
    "vendor-retrieved-at",
    "raw-object-created-at",
    "warehouse-ingested-at",
    "warehouse-table-modified-at",
})
SOURCE_PERIOD_KINDS: Final = (
    "prior-game-window",
    "prior-season-full",
    "prelock-snapshot",
    "unavailable",
)

_SHA = re.compile(r"^[0-9a-f]{64}$")
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_NAME = re.compile(r"^[a-z][a-z0-9_-]*$")
_ALLOWED_POLICY_FIELDS: Final = frozenset({
    "outcome_columns_read",
    "uses_realized_outcomes",
})
_FORBIDDEN_RELATION_FRAGMENTS: Final = (
    "017s_lineup_matchup_evidence",
    "lineup_matchup_evidence",
)
_OUTCOME_WORDS: Final = frozenset({
    "actual",
    "actuals",
    "champion",
    "champions",
    "earnings",
    "outcome",
    "outcomes",
    "payout",
    "payouts",
    "profit",
    "prize",
    "prizes",
    "result",
    "results",
    "realized",
    "roi",
    "settled",
    "settlement",
    "winner",
    "winners",
    "winning",
    "winnings",
})
_RANK_WORDS: Final = frozenset({
    "field",
    "contest",
    "entry",
    "finish",
    "finishing",
    "leaderboard",
    "standing",
    "standings",
})
_ORDER_WORDS: Final = frozenset({
    "place",
    "placement",
    "position",
    "order",
    "ordinal",
    "percentile",
    "rank",
    "ranking",
    "ranks",
})
_POST_LOCK_WORDS: Final = frozenset({
    "afterlock",
    "future",
    "postgame",
    "postlock",
})
_FORBIDDEN_SEMANTIC_COMPACTS: Final = frozenset({
    "dkpoints",
    "draftkingspoints",
    "lineupscore",
    "postslatetimestamp",
    "tournamentrank",
})
_SQL_MUTATION_WORDS: Final = frozenset({
    "alter",
    "call",
    "create",
    "delete",
    "drop",
    "execute",
    "grant",
    "insert",
    "merge",
    "revoke",
    "truncate",
    "update",
})
_REQUIRED_QUERY_PARAMETERS: Final = frozenset({
    "season",
    "week",
    "slate_id",
    "task_id",
    "lock_time_utc",
    "source_roles",
})

_SOURCE_EXPORT_FIELDS: Final = frozenset({
    "schema_version",
    "publication_mode",
    "slate",
    "lock_time_utc",
    "created_at_utc",
    "evidence_class",
    "family_definition_identities",
    "player_catalog_identity",
    "player_catalog_content_sha256",
    "target_spine_replay",
    "percentile_universe",
    "source_extracts",
    "eligible_player_count",
    "eligible_players_sha256",
    "rows",
    "rows_sha256",
    "component_value_replay",
    "qb_depth_unknown_policy",
    "outcome_columns_read",
    "uses_realized_outcomes",
    "fill_authority",
    "retrieval_authority",
    "promotion_authority",
    "production_policy_authority",
    "matchup_source_export_sha256",
})
_QUERY_RECEIPT_FIELDS: Final = frozenset({
    "schema_version",
    "slate",
    "lock_time_utc",
    "created_at_utc",
    "rendered_sql_sha256",
    "rendered_sql_template_sha256",
    "rendered_sql_bytes",
    "query_parameters",
    "query_snapshot_at_utc",
    "query_job",
    "code_identity",
    "player_catalog_identity",
    "source_export_identity",
    "target_spine_sha256",
    "component_value_replay_sha256",
    "source_relations",
    "component_temporal_evidence",
    "maximum_source_event_time_utc",
    "maximum_observed_at_utc",
    "full_season_same_target_year_used",
    "target_week_participation_universe_used",
    "qb_depth_unknown_policy",
    "outcome_columns_read",
    "uses_realized_outcomes",
    "evidence_class",
    "authoritative_for_mechanics",
    "authoritative_pit",
    "fill_authority",
    "retrieval_authority",
    "promotion_authority",
    "production_policy_authority",
    "matchup_query_receipt_sha256",
})
_REOPENED_SOURCE_FIELDS: Final = frozenset({
    "schema_version",
    "slate",
    "lock_time_utc",
    "created_at_utc",
    "evidence_class",
    "source_export_identity",
    "query_receipt_identity",
    "player_catalog_identity",
    "family_definition_identities",
    "target_spine_replay",
    "component_value_replay",
    "percentile_universe",
    "source_extracts",
    "eligible_player_count",
    "eligible_players_sha256",
    "rows",
    "rows_sha256",
    "query_snapshot_at_utc",
    "maximum_source_event_time_utc",
    "maximum_observed_at_utc",
    "full_season_same_target_year_used",
    "target_week_participation_universe_used",
    "qb_depth_unknown_policy",
    "authoritative_for_mechanics",
    "authoritative_pit",
    "outcome_columns_read",
    "uses_realized_outcomes",
    "fill_authority",
    "retrieval_authority",
    "promotion_authority",
    "production_policy_authority",
})
_TARGET_DELETION_PROOF_FIELDS: Final = frozenset({
    "schema_version",
    "probe_source_systems",
    "probe_row_count",
    "probe_rows_sha256",
    "full_input_sha256",
    "deleted_input_sha256",
    "full_reduction_sha256",
    "deleted_reduction_sha256",
    "reduction_output",
    "target_week_participation_universe_used",
    "target_week_deletion_invariant",
    "target_week_deletion_proof_sha256",
})
_SOURCE_EXTRACT_FIELDS: Final = frozenset({
    "role",
    "relation_or_object",
    "source_identity_or_extract_sha256",
    "source_role_schema_sha256",
    "rows",
    "rows_sha256",
    "row_count",
    "source_period_kind",
    "source_season_week_min",
    "source_season_week_max",
    "maximum_source_event_time_utc",
    "observed_at_utc",
    "observed_at_basis",
    "evidence_class",
    "missingness_reason",
})
_FINAL_ROW_FIELDS: Final = frozenset({
    "gsis_id",
    "family",
    "position",
    "qb_depth1",
    "qb_depth_evidence_class",
    "component_values",
    "component_support",
    "component_source_bounds",
    "component_missing_reason_codes",
    "matchup_component_count",
    "matchup_edge_score",
    "annotation_row_present",
})
_ANNOTATION_INPUT_FIELDS: Final = _FINAL_ROW_FIELDS - {
    "annotation_row_present"
}
_COMPONENT_BOUND_FIELDS: Final = frozenset({
    "source_roles",
    "source_season_week_min",
    "source_season_week_max",
    "maximum_source_event_time_utc",
    "evidence_class",
})
_CAPTURE_METADATA_FIELDS: Final = frozenset({
    "created_at_utc",
    "query_parameters",
    "query_snapshot_at_utc",
    "query_job",
    "source_relations",
    "player_catalog_evidence",
})
_QUERY_JOB_FIELDS: Final = frozenset({
    "project",
    "location",
    "job_id",
    "created",
    "started",
    "ended",
    "cache_hit",
    "error_result",
    "total_bytes_processed",
})
_SOURCE_RELATION_FIELDS: Final = frozenset({
    "role",
    "table_or_object",
    "schema_sha256",
    "etag_or_generation",
    "modified_or_created_at_utc",
    "exact_extract_sha256",
    "row_count",
})
_CATALOG_EVIDENCE_FIELDS: Final = frozenset({
    "maximum_source_event_time_utc",
    "observed_at_utc",
    "observed_at_basis",
    "evidence_class",
})
_SOURCE_ROLE_SCHEMA_FIELDS: Final = frozenset({
    "schema_version",
    "role",
    "row_fields",
    "source_period_kind",
    "population_role",
    "source_role_schema_sha256",
})
_STANDARD_SOURCE_ROW_FIELDS: Final = frozenset({
    "role",
    "source_season",
    "source_week",
    "source_event_time_utc",
    "observed_at_utc",
})
_COMPONENT_SOURCE_ROW_FIELDS: Final = frozenset({
    *_STANDARD_SOURCE_ROW_FIELDS,
    "target_season",
    "target_week",
    "target_slate_id",
    "target_task_id",
    "gsis_id",
    "family",
    "team",
    "opponent",
    "game_id",
    "component",
    "component_value",
    "component_supported",
    "missing_reason_code",
})
_SCHEDULE_ROW_FIELDS: Final = tuple(sorted({
    *_STANDARD_SOURCE_ROW_FIELDS,
    "season",
    "week",
    "slate_id",
    "task_id",
    "game_id",
    "team",
    "opponent",
    "kickoff_time_utc",
    "lock_time_utc",
}))
_QB_DEPTH_ROW_FIELDS: Final = tuple(sorted({
    *_STANDARD_SOURCE_ROW_FIELDS,
    "season",
    "week",
    "slate_id",
    "task_id",
    "gsis_id",
    "team",
    "game_id",
    "depth1",
    "missingness_reason",
}))
_BQ_RELATION = re.compile(
    r"^bq://([A-Za-z0-9_-]+\.[A-Za-z_][A-Za-z0-9_]*\."
    r"[A-Za-z_][A-Za-z0-9_]*)$"
)
_RENDERED_SQL_TEMPLATE: Final = (
    "WITH contract_parameters AS (SELECT @season AS season, @week AS week, "
    "@slate_id AS slate_id, @task_id AS task_id, @lock_time_utc AS "
    "lock_time_utc, @source_roles AS source_roles), source_rows AS "
    "({source_selects}) SELECT contract_parameters.season, "
    "contract_parameters.week, contract_parameters.slate_id, "
    "contract_parameters.task_id, contract_parameters.lock_time_utc, "
    "contract_parameters.source_roles, source_rows.role, "
    "source_rows.source_event_time_utc, source_rows.observed_at_utc FROM "
    "contract_parameters CROSS JOIN source_rows"
)
RENDERED_SQL_TEMPLATE_SHA256: Final = sha256(
    _RENDERED_SQL_TEMPLATE.encode("utf-8")
).hexdigest()


class CorpusR6MatchupSourceV1Error(ValueError):
    """The corrected matchup-source contract cannot be proven."""


def _fail(message: str) -> None:
    raise CorpusR6MatchupSourceV1Error(message)


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
        raise CorpusR6MatchupSourceV1Error(
            "value is not canonical JSON"
        ) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _semantic_words(value: str) -> tuple[str, ...]:
    """Split identifiers across snake/kebab/camel boundaries for policy checks."""
    expanded = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", "_", value)
    return tuple(
        word.lower()
        for word in re.findall(r"[A-Za-z0-9]+", expanded)
        if word
    )


def _forbidden_semantic_identifier(value: str) -> bool:
    words = _semantic_words(value)
    word_set = set(words)
    compact = "".join(words)
    if compact in _FORBIDDEN_SEMANTIC_COMPACTS:
        return True
    if word_set.intersection(_OUTCOME_WORDS):
        return True
    if word_set.intersection({"leaderboard", "standing", "standings"}):
        return True
    if compact in _POST_LOCK_WORDS:
        return True
    if (
        ("post" in word_set or "after" in word_set)
        and word_set.intersection({"deadline", "kickoff", "lock", "slate"})
    ):
        return True
    if "plus" in word_set and word_set.intersection({"kickoff", "lock"}):
        return True
    if word_set.intersection(_ORDER_WORDS) and word_set.intersection(
        _RANK_WORDS
    ):
        return True
    if "place" in word_set and word_set.intersection({"first", "top"}):
        return True
    if word_set.intersection({"point", "points", "score"}) and word_set.intersection({
        "contest", "dk", "draftkings", "field", "final", "lineup",
        "observed", "official", "recorded"
    }):
        return True
    if "rank" in word_set and "tournament" in word_set:
        return True
    if word_set.intersection({"final", "finalized", "finalization"}) and word_set.intersection({
        "at", "date", "time", "timestamp"
    }):
        return True
    if "membership" in word_set and word_set.intersection({
        "winner", "winners", "winning"
    }):
        return True
    return any(fragment in value.lower() for fragment in _FORBIDDEN_RELATION_FRAGMENTS)


def _reject_semantic_identifier(value: object, *, label: str) -> str:
    text = _string(value, label=label)
    if _forbidden_semantic_identifier(text):
        _fail(f"{label} has forbidden outcome/post-lock semantics {text!r}")
    return text


def build_source_role_schema_v1(
    *,
    role: str,
    row_fields: Sequence[str],
    source_period_kind: str,
    population_role: str,
) -> dict[str, object]:
    """Build the self-hashed row schema frozen for one source role."""
    if type(role) is str and _forbidden_semantic_identifier(role):
        _fail("source role schema has forbidden outcome/post-lock semantics")
    if any(
        type(field) is str and _forbidden_semantic_identifier(field)
        for field in row_fields
    ):
        _fail("source role schema has forbidden outcome/post-lock semantics")
    if (
        type(role) is not str
        or _NAME.fullmatch(role) is None
    ):
        _fail("source role schema role must be nonempty")
    fields = [str(field) for field in row_fields]
    if (
        not fields
        or fields != sorted(fields)
        or len(fields) != len(set(fields))
        or not _STANDARD_SOURCE_ROW_FIELDS.issubset(fields)
        or any(_NAME.fullmatch(field) is None for field in fields)
        or (
            population_role == "component"
            and set(fields) != set(_COMPONENT_SOURCE_ROW_FIELDS)
        )
        or source_period_kind not in SOURCE_PERIOD_KINDS
        or source_period_kind == "unavailable"
        or population_role not in {
            "component",
            "schedule-spine",
            "qb-depth-evidence",
        }
    ):
        _fail("source role schema definition differs")
    body = {
        "schema_version": SOURCE_ROLE_SCHEMA,
        "role": role,
        "row_fields": fields,
        "source_period_kind": source_period_kind,
        "population_role": population_role,
    }
    return _with_self_hash(body, field="source_role_schema_sha256")


def _normalize_source_role_schema(
    value: object,
    *,
    expected_role: str,
    expected_population_role: str,
) -> dict[str, object]:
    item = dict(_mapping(value, label=f"{expected_role} source schema"))
    _exact_keys(
        item,
        _SOURCE_ROLE_SCHEMA_FIELDS,
        label=f"{expected_role} source schema",
    )
    rebuilt = build_source_role_schema_v1(
        role=_string(item["role"], label="source schema role"),
        row_fields=[
            _string(field, label="source schema row field")
            for field in _sequence(item["row_fields"], label="source schema fields")
        ],
        source_period_kind=str(item["source_period_kind"]),
        population_role=str(item["population_role"]),
    )
    if (
        rebuilt != item
        or rebuilt["role"] != expected_role
        or rebuilt["population_role"] != expected_population_role
    ):
        _fail(f"{expected_role} source schema identity differs")
    return rebuilt


def _infrastructure_source_schemas() -> dict[str, dict[str, object]]:
    return {
        SCHEDULE_SOURCE_ROLE: build_source_role_schema_v1(
            role=SCHEDULE_SOURCE_ROLE,
            row_fields=_SCHEDULE_ROW_FIELDS,
            source_period_kind="prelock-snapshot",
            population_role="schedule-spine",
        ),
        QB_DEPTH_SOURCE_ROLE: build_source_role_schema_v1(
            role=QB_DEPTH_SOURCE_ROLE,
            row_fields=_QB_DEPTH_ROW_FIELDS,
            source_period_kind="prelock-snapshot",
            population_role="qb-depth-evidence",
        ),
    }


def infrastructure_source_role_schemas_v1() -> dict[str, dict[str, object]]:
    """Return copies of the two contract-owned target-spine schemas."""
    return {
        role: dict(schema)
        for role, schema in _infrastructure_source_schemas().items()
    }


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an array")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    if set(value) != set(expected):
        _fail(f"{label} fields differ")


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be a nonempty string")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA.fullmatch(value) is None:
        _fail(f"{label} must be lowercase 64-hex")
    return value


def _timestamp(value: object, *, label: str) -> tuple[str, datetime]:
    if type(value) is not str or _UTC.fullmatch(value) is None:
        _fail(f"{label} must be canonical UTC seconds")
    try:
        parsed = datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc
        )
    except ValueError as exc:
        raise CorpusR6MatchupSourceV1Error(
            f"{label} is not a valid timestamp"
        ) from exc
    return value, parsed


def _optional_timestamp(
    value: object, *, label: str
) -> tuple[str | None, datetime | None]:
    if value is None:
        return None, None
    return _timestamp(value, label=label)


def _json_copy(value: object, *, label: str) -> object:
    try:
        return json.loads(canonical_json_bytes(value).decode("utf-8"))
    except json.JSONDecodeError as exc:  # pragma: no cover - dump is authoritative
        raise CorpusR6MatchupSourceV1Error(
            f"{label} cannot be normalized"
        ) from exc


def _parse_canonical_object(raw: bytes, *, label: str) -> dict[str, object]:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty raw bytes")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6MatchupSourceV1Error(
            f"{label} is not canonical JSON"
        ) from exc
    body = dict(_mapping(parsed, label=label))
    if canonical_json_bytes(body) != raw:
        _fail(f"{label} bytes are not canonical")
    return body


def _with_self_hash(
    body: Mapping[str, object], *, field: str
) -> dict[str, object]:
    result = dict(body)
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    body: Mapping[str, object], *, field: str, label: str
) -> None:
    retained = _digest(body.get(field), label=f"{label} self-hash")
    remainder = {key: value for key, value in body.items() if key != field}
    if canonical_sha256(remainder) != retained:
        _fail(f"{label} self-hash differs")


def normalize_object_identity(
    value: object, *, label: str
) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} identity fields differ")
    uri = item["uri"]
    generation = item["generation"]
    size = item["bytes"]
    if (
        type(uri) is not str
        or not uri.startswith("gs://")
        or "/" not in uri[5:]
        or type(generation) is not str
        or not generation.isdigit()
        or generation.startswith("0")
        or type(size) is not int
        or isinstance(size, bool)
        or size <= 0
    ):
        _fail(f"{label} identity values differ")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": _digest(item["sha256"], label=f"{label} sha256"),
        "bytes": size,
    }


def _bind_raw(
    raw: bytes, identity: Mapping[str, object], *, label: str
) -> None:
    if type(raw) is not bytes or not raw:
        _fail(f"{label} must be nonempty raw bytes")
    if (
        len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} content identity differs")


def _read_exact(
    read_exact: Callable[[Mapping[str, object]], bytes],
    identity: Mapping[str, object],
    *,
    label: str,
) -> bytes:
    raw = read_exact(dict(identity))
    _bind_raw(raw, identity, label=label)
    return raw


def _reject_outcome_fields(value: object, *, label: str) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            if type(key) is not str:
                _fail(f"{label} has a non-string field")
            if (
                key not in _ALLOWED_POLICY_FIELDS
                and _forbidden_semantic_identifier(key)
            ):
                _fail(
                    f"{label} contains forbidden outcome field or post-lock field "
                    f"{key!r}"
                )
            _reject_outcome_fields(nested, label=f"{label}.{key}")
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for offset, nested in enumerate(value):
            _reject_outcome_fields(nested, label=f"{label}[{offset}]")


def _normalize_slate(value: object, *, label: str) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"season", "week", "slate_id", "task_id"}:
        _fail(f"{label} fields differ")
    season = item["season"]
    week = item["week"]
    if (
        type(season) is not int
        or isinstance(season, bool)
        or season < 2000
        or type(week) is not int
        or isinstance(week, bool)
        or not 1 <= week <= 18
    ):
        _fail(f"{label} season/week differ")
    return {
        "season": season,
        "week": week,
        "slate_id": _string(item["slate_id"], label=f"{label} slate_id"),
        "task_id": _string(item["task_id"], label=f"{label} task_id"),
    }


def _normalize_period(
    value: object, *, label: str
) -> dict[str, object] | None:
    if value is None:
        return None
    item = _mapping(value, label=label)
    if set(item) != {"season", "week"}:
        _fail(f"{label} fields differ")
    season = item["season"]
    week = item["week"]
    if (
        type(season) is not int
        or isinstance(season, bool)
        or season < 2000
        or (
            week is not None
            and (
                type(week) is not int
                or isinstance(week, bool)
                or not 1 <= week <= 22
            )
        )
    ):
        _fail(f"{label} values differ")
    return {"season": season, "week": week}


def _period_key(value: Mapping[str, object]) -> tuple[int, int]:
    week = value["week"]
    return int(value["season"]), 0 if week is None else int(week)


def _normalize_family_definitions(
    value: object,
) -> tuple[
    dict[str, dict[str, object]],
    dict[str, tuple[str, ...]],
    dict[str, dict[str, object]],
    dict[str, dict[str, tuple[str, ...]]],
    dict[str, tuple[str, ...]],
]:
    supplied = _mapping(value, label="family definition identities")
    if set(supplied) != set(ELIGIBLE_FAMILIES):
        _fail("family definition identities do not cover qb/rb/receiver")
    definitions: dict[str, dict[str, object]] = {}
    roles_by_family: dict[str, tuple[str, ...]] = {}
    schemas_by_role: dict[str, dict[str, object]] = {}
    component_roles_by_family: dict[str, dict[str, tuple[str, ...]]] = {}
    missing_codes_by_family: dict[str, tuple[str, ...]] = {}
    all_roles: set[str] = set()
    for family in ELIGIBLE_FAMILIES:
        item = dict(_mapping(supplied[family], label=f"{family} definition"))
        expected = {
            "schema_version",
            "family_id",
            "version",
            "provisional",
            "source_roles",
            "fields",
            "missing_reason_codes",
            "description",
            "source_role_schemas",
            "component_source_roles",
            "family_definition_sha256",
        }
        if set(item) != expected:
            _fail(f"{family} family definition fields differ")
        if (
            item["schema_version"] != FAMILY_DEFINITION_SCHEMA
            or item["family_id"] != _FAMILY_ID_BY_FAMILY[family]
            or type(item["version"]) is not int
            or isinstance(item["version"], bool)
            or int(item["version"]) < 2
            or type(item["provisional"]) is not bool
        ):
            _fail(f"{family} family definition identity is not corrected")
        _validate_self_hash(
            item,
            field="family_definition_sha256",
            label=f"{family} family definition",
        )
        raw_roles = _sequence(
            item["source_roles"], label=f"{family} source roles"
        )
        roles = tuple(
            _string(role, label=f"{family} source role") for role in raw_roles
        )
        if (
            not roles
            or len(roles) != len(set(roles))
            or all_roles.intersection(roles)
        ):
            _fail(f"{family} source roles are not unique")
        if family == "receiver" and "fantasy-points-shell-fit" in roles:
            _fail("receiver definition retains the ambiguous FP shell role")
        if family == "receiver" and any(
            "fantasy-points" in role and "shell" in role for role in roles
        ) and not {
            "fantasy-points-receiver-shell",
            "fantasy-points-defense-shell",
        }.issubset(roles):
            _fail("receiver/defense Fantasy Points shell roles are not split")
        all_roles.update(roles)
        raw_fields = _sequence(item["fields"], label=f"{family} fields")
        field_names: list[str] = []
        for offset, raw_field in enumerate(raw_fields):
            field = _mapping(raw_field, label=f"{family} field[{offset}]")
            if set(field) != {
                "name",
                "field_type",
                "nullable",
                "description",
            }:
                _fail(f"{family} field[{offset}] schema differs")
            name = _string(field.get("name"), label=f"{family} field name")
            if (
                _NAME.fullmatch(name) is None
                or _forbidden_semantic_identifier(name)
                or field["field_type"] != "percentile"
                or field["nullable"] is not True
                or type(field["description"]) is not str
                or not field["description"]
            ):
                _fail(f"{family} field[{offset}] semantics differ")
            field_names.append(name)
        if not field_names or len(field_names) != len(set(field_names)):
            _fail(f"{family} definition fields are empty or duplicated")
        missing_codes = tuple(
            _string(code, label=f"{family} missing reason code")
            for code in _sequence(
                item["missing_reason_codes"],
                label=f"{family} missing reason codes",
            )
        )
        if (
            not missing_codes
            or list(missing_codes) != sorted(missing_codes)
            or len(missing_codes) != len(set(missing_codes))
            or any(_NAME.fullmatch(code) is None for code in missing_codes)
            or any(_forbidden_semantic_identifier(code) for code in missing_codes)
        ):
            _fail(f"{family} missing reason codes differ")
        raw_schemas = _mapping(
            item["source_role_schemas"],
            label=f"{family} source role schemas",
        )
        if set(raw_schemas) != set(roles):
            _fail(f"{family} source role schema coverage differs")
        for role in roles:
            schemas_by_role[role] = _normalize_source_role_schema(
                raw_schemas[role],
                expected_role=role,
                expected_population_role="component",
            )
        raw_component_roles = _mapping(
            item["component_source_roles"],
            label=f"{family} component source roles",
        )
        if set(raw_component_roles) != set(field_names):
            _fail(f"{family} component dictionary differs from family fields")
        normalized_component_roles: dict[str, tuple[str, ...]] = {}
        for component in sorted(field_names):
            component_roles = tuple(
                _string(role, label=f"{family}.{component} source role")
                for role in _sequence(
                    raw_component_roles[component],
                    label=f"{family}.{component} source roles",
                )
            )
            if (
                not component_roles
                or list(component_roles) != sorted(component_roles)
                or len(component_roles) != len(set(component_roles))
                or not set(component_roles).issubset(set(roles))
            ):
                _fail(f"{family}.{component} source role dictionary differs")
            normalized_component_roles[component] = component_roles
        if {
            role
            for component_roles in normalized_component_roles.values()
            for role in component_roles
        } != set(roles):
            _fail(f"{family} source roles are not all component-bound")
        _reject_outcome_fields(item, label=f"{family} family definition")
        definitions[family] = dict(
            _json_copy(item, label=f"{family} definition")
        )
        roles_by_family[family] = roles
        component_roles_by_family[family] = normalized_component_roles
        missing_codes_by_family[family] = missing_codes
    return (
        definitions,
        roles_by_family,
        schemas_by_role,
        component_roles_by_family,
        missing_codes_by_family,
    )


def _normalize_catalog(
    raw: bytes,
    identity: Mapping[str, object],
    *,
    expected_task_id: str,
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    dict[str, dict[str, str]],
    str,
]:
    _bind_raw(raw, identity, label="player catalog")
    body = _parse_canonical_object(raw, label="player catalog")
    if set(body) != {
        "schema_version",
        "task_id",
        "source_authority",
        "players",
        "player_catalog_sha256",
    }:
        _fail("player catalog fields differ")
    if (
        body["schema_version"] != PLAYER_CATALOG_SCHEMA
        or body["task_id"] != expected_task_id
    ):
        _fail("player catalog schema/task differs")
    _validate_self_hash(
        body, field="player_catalog_sha256", label="player catalog"
    )
    normalize_object_identity(
        body["source_authority"], label="player catalog source authority"
    )
    _reject_outcome_fields(body, label="player catalog")
    players = _sequence(body["players"], label="catalog players")
    seen: set[str] = set()
    ordered_all: list[str] = []
    eligible: list[dict[str, object]] = []
    context_by_id: dict[str, dict[str, str]] = {}
    for offset, raw_player in enumerate(players):
        player = _mapping(raw_player, label=f"catalog player[{offset}]")
        if set(player) != {
            "id", "name", "pos", "team", "opp", "game_id", "salary", "proj"
        }:
            _fail(f"catalog player[{offset}] fields differ")
        player_id = _string(player["id"], label=f"catalog player[{offset}] id")
        position = _string(
            player["pos"], label=f"catalog player[{offset}] position"
        ).upper()
        if player_id in seen:
            _fail("player catalog repeats a player ID")
        seen.add(player_id)
        ordered_all.append(player_id)
        context_by_id[player_id] = {
            "team": _string(
                player["team"], label=f"catalog player[{offset}] team"
            ),
            "opponent": _string(
                player["opp"], label=f"catalog player[{offset}] opponent"
            ),
            "game_id": _string(
                player["game_id"], label=f"catalog player[{offset}] game_id"
            ),
        }
        if position in _FAMILY_BY_POSITION:
            eligible.append({
                "gsis_id": player_id,
                "family": _FAMILY_BY_POSITION[position],
                "position": position,
            })
    if ordered_all != sorted(ordered_all) or not eligible:
        _fail("player catalog ordering or skill-player coverage differs")
    eligible.sort(key=lambda row: str(row["gsis_id"]))
    return body, eligible, context_by_id, sha256(raw).hexdigest()


def _normalize_source_extracts(
    value: object,
    *,
    slate: Mapping[str, object],
    lock_instant: datetime,
    roles_by_family: Mapping[str, Sequence[str]],
    schemas_by_role: Mapping[str, Mapping[str, object]],
) -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    expected_roles = {
        role for roles in roles_by_family.values() for role in roles
    }
    expected_roles.update(INFRASTRUCTURE_SOURCE_ROLES)
    all_schemas = {
        **{role: dict(schema) for role, schema in schemas_by_role.items()},
        **_infrastructure_source_schemas(),
    }
    if set(all_schemas) != expected_roles:
        _fail("source schema role coverage differs")
    normalized: list[dict[str, object]] = []
    by_role: dict[str, dict[str, object]] = {}
    target_key = (int(slate["season"]), int(slate["week"]))
    for offset, raw_extract in enumerate(
        _sequence(value, label="component extracts")
    ):
        item = _mapping(raw_extract, label=f"source extract[{offset}]")
        _exact_keys(item, _SOURCE_EXTRACT_FIELDS, label=f"source extract[{offset}]")
        role = _string(item["role"], label=f"source extract[{offset}] role")
        if role in by_role or role not in expected_roles:
            _fail(f"source extract[{offset}] role differs from frozen dictionaries")
        role_schema = all_schemas[role]
        schema_sha = _digest(
            item["source_role_schema_sha256"],
            label=f"source extract[{offset}] role schema",
        )
        if schema_sha != role_schema["source_role_schema_sha256"]:
            _fail(f"source extract[{offset}] frozen schema differs")
        relation = _reject_semantic_identifier(
            item["relation_or_object"],
            label=f"source extract[{offset}] relation",
        )
        rows = list(_sequence(item["rows"], label=f"source extract[{offset}] rows"))
        rows = list(_json_copy(rows, label=f"source extract[{offset}] rows"))
        _reject_outcome_fields(rows, label=f"source extract[{offset}] rows")
        rows_sha = _digest(
            item["rows_sha256"], label=f"source extract[{offset}] rows sha256"
        )
        if canonical_sha256(rows) != rows_sha:
            _fail(f"source extract[{offset}] rows hash differs")
        extract_sha = _digest(
            item["source_identity_or_extract_sha256"],
            label=f"source extract[{offset}] identity",
        )
        row_count = item["row_count"]
        if (
            extract_sha != rows_sha
            or type(row_count) is not int
            or isinstance(row_count, bool)
            or row_count < 0
            or row_count != len(rows)
        ):
            _fail(f"source extract[{offset}] content/count differs")
        period_kind = item["source_period_kind"]
        if period_kind not in SOURCE_PERIOD_KINDS:
            _fail(f"source extract[{offset}] period kind differs")
        supplied_period_min = _normalize_period(
            item["source_season_week_min"],
            label=f"source extract[{offset}] period min",
        )
        supplied_period_max = _normalize_period(
            item["source_season_week_max"],
            label=f"source extract[{offset}] period max",
        )
        supplied_maximum_event, _ = _optional_timestamp(
            item["maximum_source_event_time_utc"],
            label=f"source extract[{offset}] maximum event",
        )
        supplied_observed_at, _ = _optional_timestamp(
            item["observed_at_utc"],
            label=f"source extract[{offset}] observed at",
        )
        observed_basis = item["observed_at_basis"]
        evidence_class = item["evidence_class"]
        missingness = item["missingness_reason"]
        if observed_basis not in OBSERVED_AT_BASES or evidence_class not in EVIDENCE_CLASSES:
            _fail(f"source extract[{offset}] temporal enum differs")
        if period_kind == "unavailable":
            if (
                rows
                or supplied_period_min is not None
                or supplied_period_max is not None
                or supplied_maximum_event is not None
                or supplied_observed_at is not None
                or observed_basis != "unknown"
                or evidence_class != EVIDENCE_RETROSPECTIVE
                or type(missingness) is not str
                or not missingness
            ):
                _fail(f"source extract[{offset}] unavailable shape differs")
            period_min = None
            period_max = None
            maximum_event = None
            observed_at = None
        else:
            if period_kind != role_schema["source_period_kind"]:
                _fail(f"source extract[{offset}] period kind differs from schema")
            if (
                not rows
                or observed_basis == "unknown"
                or missingness is not None
            ):
                _fail(f"source extract[{offset}] temporal completeness differs")
            derived_periods: list[dict[str, object]] = []
            derived_events: list[tuple[str, datetime]] = []
            derived_observations: list[tuple[str, datetime]] = []
            expected_row_fields = set(role_schema["row_fields"])
            for row_ordinal, raw_row in enumerate(rows):
                row = _mapping(
                    raw_row,
                    label=f"source extract[{offset}] row[{row_ordinal}]",
                )
                if set(row) != expected_row_fields:
                    _fail(f"source extract[{offset}] retained row schema differs")
                if row["role"] != role:
                    _fail(f"source extract[{offset}] retained row role differs")
                period = _normalize_period(
                    {
                        "season": row["source_season"],
                        "week": row["source_week"],
                    },
                    label=f"source extract[{offset}] retained row period",
                )
                assert period is not None
                derived_periods.append(period)
                derived_events.append(_timestamp(
                    row["source_event_time_utc"],
                    label=f"source extract[{offset}] retained row event",
                ))
                derived_observations.append(_timestamp(
                    row["observed_at_utc"],
                    label=f"source extract[{offset}] retained row observation",
                ))
            period_min = dict(min(derived_periods, key=_period_key))
            period_max = dict(max(derived_periods, key=_period_key))
            maximum_event, maximum_event_instant = max(
                derived_events, key=lambda pair: pair[1]
            )
            observed_at, observed_instant = max(
                derived_observations, key=lambda pair: pair[1]
            )
            if (
                supplied_period_min != period_min
                or supplied_period_max != period_max
                or supplied_maximum_event != maximum_event
                or supplied_observed_at != observed_at
            ):
                _fail(f"source extract[{offset}] row-derived temporal fields drift")
            if maximum_event_instant >= lock_instant:
                _fail(f"source extract[{offset}] retained row reaches or follows lock")
            if period_kind == "prior-season-full":
                same_target_year = (
                    int(period_min["season"]) == int(slate["season"])
                    or int(period_max["season"]) == int(slate["season"])
                )
                if same_target_year:
                    _fail("same-target-season full-season source is forbidden")
                if (
                    period_min["week"] is not None
                    or period_max["week"] is not None
                    or int(period_min["season"]) != int(slate["season"]) - 1
                    or int(period_max["season"]) != int(slate["season"]) - 1
                ):
                    _fail("prior-season full source is not target season N-1")
            elif period_kind == "prior-game-window":
                if (
                    period_min["week"] is None
                    or period_max["week"] is None
                    or _period_key(period_max) >= target_key
                ):
                    _fail("prior-game source reaches the target period")
            elif period_kind == "prelock-snapshot":
                if (
                    period_min["week"] is None
                    or period_max["week"] is None
                    or _period_key(period_max) > target_key
                ):
                    _fail("prelock snapshot period exceeds the target")
            derived_evidence_class = (
                EVIDENCE_CONTEMPORANEOUS
                if observed_basis in _CONTEMPORANEOUS_BASES
                and observed_instant < lock_instant
                else EVIDENCE_RETROSPECTIVE
            )
            if evidence_class != derived_evidence_class:
                _fail(f"source extract[{offset}] evidence class is not row-derived")
        normalized_item = {
            "role": role,
            "relation_or_object": relation,
            "source_identity_or_extract_sha256": extract_sha,
            "source_role_schema_sha256": schema_sha,
            "rows": rows,
            "rows_sha256": rows_sha,
            "row_count": row_count,
            "source_period_kind": period_kind,
            "source_season_week_min": period_min,
            "source_season_week_max": period_max,
            "maximum_source_event_time_utc": maximum_event,
            "observed_at_utc": observed_at,
            "observed_at_basis": observed_basis,
            "evidence_class": evidence_class,
            "missingness_reason": missingness,
        }
        by_role[role] = normalized_item
        normalized.append(normalized_item)
    if set(by_role) != expected_roles:
        missing = sorted(expected_roles - set(by_role))
        extra = sorted(set(by_role) - expected_roles)
        _fail(f"source extract role coverage differs: missing={missing}, extra={extra}")
    normalized.sort(key=lambda row: str(row["role"]))
    return normalized, by_role


def _validate_schedule_and_depth_sources(
    *,
    slate: Mapping[str, object],
    lock_time_utc: str,
    eligible_players: Sequence[Mapping[str, object]],
    catalog_context_by_id: Mapping[str, Mapping[str, str]],
    extracts_by_role: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, dict[str, object]], dict[str, object]]:
    """Replay the two non-component authorities required by the target spine."""
    schedule_extract = extracts_by_role[SCHEDULE_SOURCE_ROLE]
    if int(schedule_extract["row_count"]) <= 0:
        _fail("standalone schedule spine is unavailable")
    schedule_by_team: dict[str, dict[str, object]] = {}
    for offset, raw_row in enumerate(schedule_extract["rows"]):
        row = dict(_mapping(raw_row, label=f"schedule row[{offset}]"))
        team = _string(row["team"], label=f"schedule row[{offset}] team")
        opponent = _string(
            row["opponent"], label=f"schedule row[{offset}] opponent"
        )
        game_id = _string(
            row["game_id"], label=f"schedule row[{offset}] game_id"
        )
        kickoff, kickoff_dt = _timestamp(
            row["kickoff_time_utc"], label=f"schedule row[{offset}] kickoff"
        )
        _, lock_dt = _timestamp(lock_time_utc, label="schedule-bound lock")
        if (
            team in schedule_by_team
            or team == opponent
            or row["season"] != slate["season"]
            or row["week"] != slate["week"]
            or row["slate_id"] != slate["slate_id"]
            or row["task_id"] != slate["task_id"]
            or row["source_season"] != slate["season"]
            or row["source_week"] != slate["week"]
            or row["lock_time_utc"] != lock_time_utc
            or kickoff_dt < lock_dt
        ):
            _fail(f"schedule row[{offset}] does not bind the target slate")
        schedule_by_team[team] = {
            **row,
            "team": team,
            "opponent": opponent,
            "game_id": game_id,
            "kickoff_time_utc": kickoff,
        }
    catalog_teams = {
        context["team"] for context in catalog_context_by_id.values()
    }
    if set(schedule_by_team) != catalog_teams:
        _fail("schedule spine team coverage differs from the player catalog")
    for team, row in schedule_by_team.items():
        opponent = str(row["opponent"])
        reciprocal = schedule_by_team.get(opponent)
        if (
            reciprocal is None
            or reciprocal["opponent"] != team
            or reciprocal["game_id"] != row["game_id"]
        ):
            _fail("schedule spine is not reciprocal by game")
    for player_id, context in catalog_context_by_id.items():
        scheduled = schedule_by_team.get(context["team"])
        if (
            scheduled is None
            or scheduled["opponent"] != context["opponent"]
            or scheduled["game_id"] != context["game_id"]
        ):
            _fail(f"schedule spine differs for catalog player {player_id!r}")

    target_spine_rows = []
    for player in eligible_players:
        player_id = str(player["gsis_id"])
        context = catalog_context_by_id[player_id]
        scheduled = schedule_by_team[context["team"]]
        target_spine_rows.append({
            **dict(player),
            "team": context["team"],
            "opponent": context["opponent"],
            "game_id": context["game_id"],
            "kickoff_time_utc": scheduled["kickoff_time_utc"],
        })
    target_spine_rows.sort(key=lambda row: str(row["gsis_id"]))
    target_spine_replay = _with_self_hash({
        "schema_version": "corpus-r6-target-spine-replay/v1",
        "population_authority": "accepted-player-catalog",
        "schedule_authority_role": SCHEDULE_SOURCE_ROLE,
        "schedule_rows_sha256": schedule_extract["rows_sha256"],
        "schedule_role_schema_sha256": schedule_extract[
            "source_role_schema_sha256"
        ],
        "schedule_team_count": len(schedule_by_team),
        "eligible_player_count": len(target_spine_rows),
        "rows_sha256": canonical_sha256(target_spine_rows),
    }, field="target_spine_sha256")

    depth_extract = extracts_by_role[QB_DEPTH_SOURCE_ROLE]
    if int(depth_extract["row_count"]) <= 0:
        _fail("QB depth evidence source is unavailable")
    expected_qbs = {
        str(player["gsis_id"])
        for player in eligible_players
        if player["family"] == "qb"
    }
    depth_by_id: dict[str, dict[str, object]] = {}
    for offset, raw_row in enumerate(depth_extract["rows"]):
        row = _mapping(raw_row, label=f"QB depth row[{offset}]")
        player_id = _string(
            row["gsis_id"], label=f"QB depth row[{offset}] player"
        )
        depth = row["depth1"]
        missingness = row["missingness_reason"]
        catalog_context = catalog_context_by_id.get(player_id)
        if (
            player_id not in expected_qbs
            or player_id in depth_by_id
            or (depth is not None and type(depth) is not bool)
            or (depth is None and (type(missingness) is not str or not missingness))
            or (depth is not None and missingness is not None)
            or row["season"] != slate["season"]
            or row["week"] != slate["week"]
            or row["source_season"] != slate["season"]
            or row["source_week"] != slate["week"]
            or row["slate_id"] != slate["slate_id"]
            or row["task_id"] != slate["task_id"]
            or catalog_context is None
            or row["team"] != catalog_context["team"]
            or row["game_id"] != catalog_context["game_id"]
        ):
            _fail(f"QB depth row[{offset}] differs from the catalog/slate")
        depth_by_id[player_id] = {
            "qb_depth1": depth,
            "qb_depth_evidence_class": (
                str(depth_extract["evidence_class"])
                if depth is not None
                else "unknown"
            ),
        }
    if set(depth_by_id) != expected_qbs:
        _fail("QB depth evidence does not cover every catalog QB exactly once")
    return depth_by_id, target_spine_replay


def _weakest_evidence(values: Sequence[str], *, label: str) -> str:
    if not values or any(value not in _EVIDENCE_RANK for value in values):
        _fail(f"{label} evidence classes differ")
    return min(values, key=lambda value: _EVIDENCE_RANK[value])


def _aggregate_period(
    extracts: Sequence[Mapping[str, object]], *, field: str, choose_max: bool
) -> dict[str, object] | None:
    periods = [
        extract[field]
        for extract in extracts
        if extract[field] is not None and int(extract["row_count"]) > 0
    ]
    if not periods:
        return None
    chooser = max if choose_max else min
    return dict(chooser(periods, key=_period_key))


def _expected_component_bound(
    source_roles: Sequence[object],
    *,
    family_roles: Sequence[str],
    extracts_by_role: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    roles = [_string(role, label="component source role") for role in source_roles]
    if not roles or roles != sorted(roles) or len(roles) != len(set(roles)):
        _fail("component source roles are not a canonical nonempty set")
    if not set(roles).issubset(set(family_roles)):
        _fail("component source role differs from its family dictionary")
    extracts = [extracts_by_role[role] for role in roles]
    used = [extract for extract in extracts if int(extract["row_count"]) > 0]
    maximum_events = [
        str(extract["maximum_source_event_time_utc"])
        for extract in used
        if extract["maximum_source_event_time_utc"] is not None
    ]
    evidence_values = [str(extract["evidence_class"]) for extract in extracts]
    return {
        "source_roles": roles,
        "source_season_week_min": _aggregate_period(
            extracts, field="source_season_week_min", choose_max=False
        ),
        "source_season_week_max": _aggregate_period(
            extracts, field="source_season_week_max", choose_max=True
        ),
        "maximum_source_event_time_utc": (
            max(maximum_events) if maximum_events else None
        ),
        "evidence_class": _weakest_evidence(
            evidence_values, label="component"
        ),
    }


def _frozen_mean(values: Sequence[float]) -> float:
    if not values:
        _fail("cannot derive a frozen mean from an empty value set")
    return round(math.fsum(values) / len(values), 12)


def _replay_component_values(
    *,
    slate: Mapping[str, object],
    eligible_players: Sequence[Mapping[str, object]],
    catalog_context_by_id: Mapping[str, Mapping[str, str]],
    roles_by_family: Mapping[str, Sequence[str]],
    component_roles_by_family: Mapping[
        str, Mapping[str, Sequence[str]]
    ],
    missing_codes_by_family: Mapping[str, Sequence[str]],
    extracts_by_role: Mapping[str, Mapping[str, object]],
) -> tuple[dict[str, dict[str, dict[str, object]]], int]:
    """Replay every numeric/null component from complete, declared extracts."""
    players_by_family = {
        family: [
            dict(player)
            for player in eligible_players
            if player["family"] == family
        ]
        for family in ELIGIBLE_FAMILIES
    }
    role_family = {
        role: family
        for family, roles in roles_by_family.items()
        for role in roles
    }
    role_cells: dict[tuple[str, str, str], dict[str, object]] = {}
    retained_source_cells = 0
    for role in sorted(role_family):
        family = role_family[role]
        extract = extracts_by_role[role]
        components = sorted(
            component
            for component, roles in component_roles_by_family[family].items()
            if role in roles
        )
        if not components:
            _fail(f"component source role {role!r} is not family-bound")
        expected_keys = {
            (str(player["gsis_id"]), component)
            for player in players_by_family[family]
            for component in components
        }
        allowed_codes = set(missing_codes_by_family[family])
        if int(extract["row_count"]) == 0:
            missing_code = extract["missingness_reason"]
            if missing_code not in allowed_codes:
                _fail(
                    f"unavailable component source {role!r} has an "
                    "undeclared missing reason"
                )
            for player_id, component in expected_keys:
                role_cells[(role, player_id, component)] = {
                    "supported": False,
                    "value": None,
                    "missing_reason_code": missing_code,
                }
            continue
        seen: set[tuple[str, str]] = set()
        ordering: list[tuple[str, str]] = []
        for offset, raw_row in enumerate(extract["rows"]):
            row = _mapping(raw_row, label=f"{role} component row[{offset}]")
            if not _COMPONENT_SOURCE_ROW_FIELDS.issubset(row):
                _fail(f"{role} component row[{offset}] replay fields differ")
            player_id = _string(
                row["gsis_id"], label=f"{role} component row[{offset}] player"
            )
            component = _string(
                row["component"],
                label=f"{role} component row[{offset}] component",
            )
            key = (player_id, component)
            player = next(
                (
                    candidate
                    for candidate in players_by_family[family]
                    if candidate["gsis_id"] == player_id
                ),
                None,
            )
            context = catalog_context_by_id.get(player_id)
            supported = row["component_supported"]
            component_value = row["component_value"]
            missing_code = row["missing_reason_code"]
            if (
                key not in expected_keys
                or key in seen
                or player is None
                or context is None
                or row["family"] != family
                or row["target_season"] != slate["season"]
                or row["target_week"] != slate["week"]
                or row["target_slate_id"] != slate["slate_id"]
                or row["target_task_id"] != slate["task_id"]
                or row["team"] != context["team"]
                or row["opponent"] != context["opponent"]
                or row["game_id"] != context["game_id"]
                or type(supported) is not bool
            ):
                _fail(f"{role} component row[{offset}] target replay differs")
            if supported:
                if (
                    isinstance(component_value, bool)
                    or not isinstance(component_value, (int, float))
                    or not math.isfinite(float(component_value))
                    or not 0.0 <= float(component_value) <= 1.0
                    or missing_code is not None
                ):
                    _fail(f"{role} component row[{offset}] value differs")
                normalized_value: float | None = float(component_value)
            else:
                if (
                    component_value is not None
                    or type(missing_code) is not str
                    or missing_code not in allowed_codes
                ):
                    _fail(
                        f"{role} component row[{offset}] missing reason differs"
                    )
                normalized_value = None
            seen.add(key)
            ordering.append(key)
            role_cells[(role, player_id, component)] = {
                "supported": supported,
                "value": normalized_value,
                "missing_reason_code": missing_code,
            }
            retained_source_cells += 1
        if seen != expected_keys or ordering != sorted(ordering):
            _fail(
                f"{role} component rows do not exactly cover the target spine"
            )

    replay: dict[str, dict[str, dict[str, object]]] = {}
    for player in eligible_players:
        player_id = str(player["gsis_id"])
        family = str(player["family"])
        replay[player_id] = {}
        for component, roles in sorted(
            component_roles_by_family[family].items()
        ):
            cells = [role_cells[(role, player_id, component)] for role in roles]
            supported_values = [
                float(cell["value"])
                for cell in cells
                if cell["supported"] is True
            ]
            missing_codes = sorted({
                str(cell["missing_reason_code"])
                for cell in cells
                if cell["missing_reason_code"] is not None
            })
            if supported_values:
                replay[player_id][component] = {
                    "value": _frozen_mean(supported_values),
                    "supported": True,
                    "missing_reason_codes": missing_codes,
                }
            else:
                if not missing_codes:
                    _fail(f"{family}.{component} has no supported value or reason")
                replay[player_id][component] = {
                    "value": None,
                    "supported": False,
                    "missing_reason_codes": missing_codes,
                }
    return replay, retained_source_cells


def _target_week_participation_probe_rows(
    *,
    slate: Mapping[str, object],
    eligible_players: Sequence[Mapping[str, object]],
) -> list[dict[str, object]]:
    """Create catalog-complete score-free target-week contamination probes."""
    rows = [
        {
            "source_system": source_system,
            "season": slate["season"],
            "week": slate["week"],
            "slate_id": slate["slate_id"],
            "task_id": slate["task_id"],
            "gsis_id": player["gsis_id"],
            "family": player["family"],
        }
        for source_system in TARGET_WEEK_PARTICIPATION_SYSTEMS
        for player in eligible_players
    ]
    rows.sort(key=lambda row: (str(row["source_system"]), str(row["gsis_id"])))
    return rows


def _reduce_deletion_probe_inputs(
    *,
    slate: Mapping[str, object],
    eligible_players: Sequence[Mapping[str, object]],
    catalog_context_by_id: Mapping[str, Mapping[str, str]],
    roles_by_family: Mapping[str, Sequence[str]],
    component_roles_by_family: Mapping[
        str, Mapping[str, Sequence[str]]
    ],
    missing_codes_by_family: Mapping[str, Sequence[str]],
    extracts_by_role: Mapping[str, Mapping[str, object]],
    qb_depth_by_id: Mapping[str, Mapping[str, object]],
    annotation_rows: Sequence[Mapping[str, object]],
    participation_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Reduce raw inputs while structurally deleting target-week participation.

    The declared component extracts and accepted catalog are the sole inputs to
    population, component, and percentile output.  Target-week row-existence
    carriers from weekly_stats, SIS, and PFR are accepted only as contamination
    probes and deleted before reduction.
    """
    eligible_by_id = {
        str(player["gsis_id"]): str(player["family"])
        for player in eligible_players
    }
    retained_participation: list[dict[str, object]] = []
    for offset, raw_row in enumerate(participation_rows):
        row = dict(_mapping(raw_row, label=f"participation probe[{offset}]"))
        if set(row) != {
            "source_system",
            "season",
            "week",
            "slate_id",
            "task_id",
            "gsis_id",
            "family",
        }:
            _fail(f"participation probe[{offset}] fields differ")
        source_system = _string(
            row["source_system"], label=f"participation probe[{offset}] source"
        )
        player_id = _string(
            row["gsis_id"], label=f"participation probe[{offset}] player"
        )
        if (
            source_system not in TARGET_WEEK_PARTICIPATION_SYSTEMS
            or row["season"] != slate["season"]
            or row["week"] != slate["week"]
            or row["slate_id"] != slate["slate_id"]
            or row["task_id"] != slate["task_id"]
            or player_id not in eligible_by_id
            or row["family"] != eligible_by_id[player_id]
        ):
            _fail(f"participation probe[{offset}] is not catalog-complete target-week data")
        # The deletion is the science law: no target-week participation row is
        # admitted to the population or component reducer.
        continue
    replayed_components, retained_source_cell_count = _replay_component_values(
        slate=slate,
        eligible_players=eligible_players,
        catalog_context_by_id=catalog_context_by_id,
        roles_by_family=roles_by_family,
        component_roles_by_family=component_roles_by_family,
        missing_codes_by_family=missing_codes_by_family,
        extracts_by_role=extracts_by_role,
    )
    reduced_rows = _normalize_annotation_rows(
        annotation_rows,
        eligible_players=eligible_players,
        roles_by_family=roles_by_family,
        component_roles_by_family=component_roles_by_family,
        extracts_by_role=extracts_by_role,
        qb_depth_by_id=qb_depth_by_id,
        component_replay_by_player=replayed_components,
    )
    component_roles = sorted(
        role
        for role in extracts_by_role
        if role not in INFRASTRUCTURE_SOURCE_ROLES
    )
    output = {
        "population_rows_sha256": canonical_sha256(list(eligible_players)),
        "component_source_rows_sha256": {
            role: extracts_by_role[role]["rows_sha256"]
            for role in component_roles
        },
        "component_values_sha256": canonical_sha256(replayed_components),
        "percentile_rows_sha256": canonical_sha256(reduced_rows),
        "retained_source_cell_count": retained_source_cell_count,
        "retained_target_week_participation_rows_sha256": canonical_sha256(
            retained_participation
        ),
    }
    return output


def _build_target_week_deletion_proof(
    *,
    slate: Mapping[str, object],
    eligible_players: Sequence[Mapping[str, object]],
    catalog_context_by_id: Mapping[str, Mapping[str, str]],
    roles_by_family: Mapping[str, Sequence[str]],
    component_roles_by_family: Mapping[
        str, Mapping[str, Sequence[str]]
    ],
    missing_codes_by_family: Mapping[str, Sequence[str]],
    extracts_by_role: Mapping[str, Mapping[str, object]],
    qb_depth_by_id: Mapping[str, Mapping[str, object]],
    annotation_rows: Sequence[Mapping[str, object]],
    component_replay_by_player: Mapping[
        str, Mapping[str, Mapping[str, object]]
    ],
    normalized_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    probes = _target_week_participation_probe_rows(
        slate=slate,
        eligible_players=eligible_players,
    )
    component_input = {
        role: extracts_by_role[role]["rows_sha256"]
        for role in sorted(extracts_by_role)
        if role not in INFRASTRUCTURE_SOURCE_ROLES
    }
    full_input_sha = canonical_sha256({
        "component_source_rows_sha256": component_input,
        "target_week_participation_rows": probes,
    })
    deleted_input_sha = canonical_sha256({
        "component_source_rows_sha256": component_input,
        "target_week_participation_rows": [],
    })
    full_reduction = _reduce_deletion_probe_inputs(
        slate=slate,
        eligible_players=eligible_players,
        catalog_context_by_id=catalog_context_by_id,
        roles_by_family=roles_by_family,
        component_roles_by_family=component_roles_by_family,
        missing_codes_by_family=missing_codes_by_family,
        extracts_by_role=extracts_by_role,
        qb_depth_by_id=qb_depth_by_id,
        annotation_rows=annotation_rows,
        participation_rows=probes,
    )
    deleted_reduction = _reduce_deletion_probe_inputs(
        slate=slate,
        eligible_players=eligible_players,
        catalog_context_by_id=catalog_context_by_id,
        roles_by_family=roles_by_family,
        component_roles_by_family=component_roles_by_family,
        missing_codes_by_family=missing_codes_by_family,
        extracts_by_role=extracts_by_role,
        qb_depth_by_id=qb_depth_by_id,
        annotation_rows=annotation_rows,
        participation_rows=[],
    )
    full_reduction_sha = canonical_sha256(full_reduction)
    deleted_reduction_sha = canonical_sha256(deleted_reduction)
    invariant = full_reduction_sha == deleted_reduction_sha
    participation_used = not invariant
    if (
        not probes
        or len(probes)
        != len(eligible_players) * len(TARGET_WEEK_PARTICIPATION_SYSTEMS)
        or full_input_sha == deleted_input_sha
        or not invariant
        or participation_used
        or full_reduction["component_values_sha256"]
        != canonical_sha256(component_replay_by_player)
        or full_reduction["percentile_rows_sha256"]
        != canonical_sha256(list(normalized_rows))
    ):
        _fail("target-week participation deletion proof does not replay")
    return _with_self_hash({
        "schema_version": "corpus-r6-target-week-deletion-proof/v1",
        "probe_source_systems": list(TARGET_WEEK_PARTICIPATION_SYSTEMS),
        "probe_row_count": len(probes),
        "probe_rows_sha256": canonical_sha256(probes),
        "full_input_sha256": full_input_sha,
        "deleted_input_sha256": deleted_input_sha,
        "full_reduction_sha256": full_reduction_sha,
        "deleted_reduction_sha256": deleted_reduction_sha,
        "reduction_output": full_reduction,
        "target_week_participation_universe_used": participation_used,
        "target_week_deletion_invariant": invariant,
    }, field="target_week_deletion_proof_sha256")


def _build_component_value_replay(
    *,
    slate: Mapping[str, object],
    eligible_players: Sequence[Mapping[str, object]],
    catalog_context_by_id: Mapping[str, Mapping[str, str]],
    target_spine_replay: Mapping[str, object],
    roles_by_family: Mapping[str, Sequence[str]],
    component_roles_by_family: Mapping[
        str, Mapping[str, Sequence[str]]
    ],
    missing_codes_by_family: Mapping[str, Sequence[str]],
    extracts_by_role: Mapping[str, Mapping[str, object]],
    qb_depth_by_id: Mapping[str, Mapping[str, object]],
    annotation_rows: Sequence[Mapping[str, object]],
    component_replay_by_player: Mapping[
        str, Mapping[str, Mapping[str, object]]
    ],
    retained_source_cell_count: int,
    normalized_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    component_roles = sorted({
        role for roles in roles_by_family.values() for role in roles
    })
    cells = [
        cell
        for player in component_replay_by_player.values()
        for cell in player.values()
    ]
    deletion_proof = _build_target_week_deletion_proof(
        slate=slate,
        eligible_players=eligible_players,
        catalog_context_by_id=catalog_context_by_id,
        roles_by_family=roles_by_family,
        component_roles_by_family=component_roles_by_family,
        missing_codes_by_family=missing_codes_by_family,
        extracts_by_role=extracts_by_role,
        qb_depth_by_id=qb_depth_by_id,
        annotation_rows=annotation_rows,
        component_replay_by_player=component_replay_by_player,
        normalized_rows=normalized_rows,
    )
    same_target_full_season_used = any(
        extract["source_period_kind"] == "prior-season-full"
        and extract["source_season_week_max"] is not None
        and extract["source_season_week_max"]["season"] == slate["season"]
        for extract in extracts_by_role.values()
    )
    return _with_self_hash({
        "schema_version": "corpus-r6-component-value-replay/v1",
        "target_spine_sha256": target_spine_replay["target_spine_sha256"],
        "population_input": "accepted-catalog-target-spine-only",
        "source_extract_rows_sha256": {
            role: extracts_by_role[role]["rows_sha256"]
            for role in component_roles
        },
        "retained_source_cell_count": retained_source_cell_count,
        "component_cell_count": len(cells),
        "supported_component_cell_count": sum(
            cell["supported"] is True for cell in cells
        ),
        "unsupported_component_cell_count": sum(
            cell["supported"] is False for cell in cells
        ),
        "full_season_same_target_year_used": same_target_full_season_used,
        "target_week_participation_universe_used": deletion_proof[
            "target_week_participation_universe_used"
        ],
        "target_week_deletion_invariant": deletion_proof[
            "target_week_deletion_invariant"
        ],
        "target_week_deletion_proof": deletion_proof,
        "normalized_rows_sha256": canonical_sha256(list(normalized_rows)),
    }, field="component_value_replay_sha256")


def _normalize_annotation_rows(
    value: object,
    *,
    eligible_players: Sequence[Mapping[str, object]],
    roles_by_family: Mapping[str, Sequence[str]],
    component_roles_by_family: Mapping[
        str, Mapping[str, Sequence[str]]
    ],
    extracts_by_role: Mapping[str, Mapping[str, object]],
    qb_depth_by_id: Mapping[str, Mapping[str, object]],
    component_replay_by_player: Mapping[
        str, Mapping[str, Mapping[str, object]]
    ],
) -> list[dict[str, object]]:
    eligible_by_id = {
        str(player["gsis_id"]): dict(player) for player in eligible_players
    }
    supplied_by_id: dict[str, dict[str, object]] = {}
    for offset, raw_row in enumerate(_sequence(value, label="annotation rows")):
        row = _mapping(raw_row, label=f"annotation row[{offset}]")
        _exact_keys(row, _ANNOTATION_INPUT_FIELDS, label=f"annotation row[{offset}]")
        player_id = _string(row["gsis_id"], label=f"annotation row[{offset}] id")
        if player_id not in eligible_by_id or player_id in supplied_by_id:
            _fail(f"annotation row[{offset}] player coverage differs")
        expected_player = eligible_by_id[player_id]
        family = row["family"]
        position = row["position"]
        if family != expected_player["family"] or position != expected_player["position"]:
            _fail(f"annotation row[{offset}] family/position differs from catalog")
        depth = row["qb_depth1"]
        depth_evidence = row["qb_depth_evidence_class"]
        if family == "qb":
            expected_depth = qb_depth_by_id[player_id]
            if (
                depth != expected_depth["qb_depth1"]
                or depth_evidence
                != expected_depth["qb_depth_evidence_class"]
            ):
                _fail(f"annotation row[{offset}] QB depth is not evidence-bound")
        elif depth is not None or depth_evidence != "not-applicable":
            _fail(f"annotation row[{offset}] non-QB depth differs")
        values = dict(_mapping(
            row["component_values"], label=f"annotation row[{offset}] values"
        ))
        support = dict(_mapping(
            row["component_support"], label=f"annotation row[{offset}] support"
        ))
        bounds = dict(_mapping(
            row["component_source_bounds"],
            label=f"annotation row[{offset}] bounds",
        ))
        missing_reasons = dict(_mapping(
            row["component_missing_reason_codes"],
            label=f"annotation row[{offset}] missing reasons",
        ))
        frozen_components = component_roles_by_family[str(family)]
        if (
            not values
            or set(values) != set(frozen_components)
            or set(values) != set(support)
            or set(values) != set(bounds)
            or set(values) != set(missing_reasons)
        ):
            _fail(f"annotation row[{offset}] component dictionaries differ")
        _reject_outcome_fields(values, label=f"annotation row[{offset}] values")
        normalized_values: dict[str, object] = {}
        normalized_support: dict[str, bool] = {}
        normalized_bounds: dict[str, object] = {}
        normalized_missing_reasons: dict[str, list[str]] = {}
        for component in sorted(values):
            if (
                _NAME.fullmatch(component) is None
                or _forbidden_semantic_identifier(component)
            ):
                _fail(f"annotation row[{offset}] component name differs")
            supported = support[component]
            component_value = values[component]
            expected_cell = component_replay_by_player[player_id][component]
            if type(supported) is not bool:
                _fail(f"annotation row[{offset}] component support differs")
            if supported:
                if (
                    isinstance(component_value, bool)
                    or not isinstance(component_value, (int, float))
                    or not math.isfinite(float(component_value))
                    or not 0.0 <= float(component_value) <= 1.0
                ):
                    _fail(f"annotation row[{offset}] supported component differs")
                normalized_values[component] = float(component_value)
            else:
                if component_value is not None:
                    _fail(f"annotation row[{offset}] unsupported component is non-null")
                normalized_values[component] = None
            raw_missing_codes = [
                _string(
                    code,
                    label=(
                        f"annotation row[{offset}] {component} missing reason"
                    ),
                )
                for code in _sequence(
                    missing_reasons[component],
                    label=(
                        f"annotation row[{offset}] {component} missing reasons"
                    ),
                )
            ]
            if (
                raw_missing_codes != sorted(raw_missing_codes)
                or len(raw_missing_codes) != len(set(raw_missing_codes))
                or supported != expected_cell["supported"]
                or normalized_values[component] != expected_cell["value"]
                or raw_missing_codes != expected_cell["missing_reason_codes"]
            ):
                _fail(
                    f"annotation row[{offset}] {component} is not source-replayed"
                )
            raw_bound = _mapping(
                bounds[component],
                label=f"annotation row[{offset}] {component} bound",
            )
            _exact_keys(
                raw_bound,
                _COMPONENT_BOUND_FIELDS,
                label=f"annotation row[{offset}] {component} bound",
            )
            if list(_sequence(
                raw_bound["source_roles"],
                label=f"annotation row[{offset}] {component} roles",
            )) != list(frozen_components[component]):
                _fail(
                    f"annotation row[{offset}] component roles differ from family"
                )
            expected_bound = _expected_component_bound(
                _sequence(
                    raw_bound["source_roles"],
                    label=f"annotation row[{offset}] {component} roles",
                ),
                family_roles=roles_by_family[str(family)],
                extracts_by_role=extracts_by_role,
            )
            if canonical_json_bytes(raw_bound) != canonical_json_bytes(expected_bound):
                _fail(f"annotation row[{offset}] component source bound drifts")
            normalized_support[component] = supported
            normalized_bounds[component] = expected_bound
            normalized_missing_reasons[component] = raw_missing_codes
        component_count = row["matchup_component_count"]
        supported_count = sum(normalized_support.values())
        edge = row["matchup_edge_score"]
        if (
            type(component_count) is not int
            or isinstance(component_count, bool)
            or component_count != supported_count
            or component_count < 0
        ):
            _fail(f"annotation row[{offset}] component count differs")
        expected_edge = (
            _frozen_mean([
                float(value)
                for component, value in normalized_values.items()
                if normalized_support[component]
            ])
            if component_count >= 2
            else None
        )
        if edge is None:
            if component_count >= 2:
                _fail(f"annotation row[{offset}] supported edge is missing")
            normalized_edge = None
        elif (
            isinstance(edge, bool)
            or not isinstance(edge, (int, float))
            or not math.isfinite(float(edge))
            or not 0.0 <= float(edge) <= 1.0
            or component_count < 2
        ):
            _fail(f"annotation row[{offset}] edge differs")
        else:
            normalized_edge = float(edge)
        if normalized_edge != expected_edge:
            _fail(f"annotation row[{offset}] edge is not the frozen component mean")
        supplied_by_id[player_id] = {
            **expected_player,
            "qb_depth1": depth,
            "qb_depth_evidence_class": depth_evidence,
            "component_values": normalized_values,
            "component_support": normalized_support,
            "component_source_bounds": normalized_bounds,
            "component_missing_reason_codes": normalized_missing_reasons,
            "matchup_component_count": component_count,
            "matchup_edge_score": normalized_edge,
            "annotation_row_present": True,
        }
    rows: list[dict[str, object]] = []
    for player in eligible_players:
        player_id = str(player["gsis_id"])
        if player_id in supplied_by_id:
            rows.append(supplied_by_id[player_id])
            continue
        family = str(player["family"])
        replayed_components = component_replay_by_player[player_id]
        if any(
            cell["supported"] is True
            for cell in replayed_components.values()
        ):
            _fail(
                f"annotation row for {player_id!r} is missing despite source support"
            )
        depth = qb_depth_by_id.get(player_id, {
            "qb_depth1": None,
            "qb_depth_evidence_class": "not-applicable",
        })
        rows.append({
            **dict(player),
            "qb_depth1": depth["qb_depth1"],
            "qb_depth_evidence_class": depth[
                "qb_depth_evidence_class"
            ],
            "component_values": {
                component: cell["value"]
                for component, cell in replayed_components.items()
            },
            "component_support": {
                component: bool(cell["supported"])
                for component, cell in replayed_components.items()
            },
            "component_source_bounds": {
                component: _expected_component_bound(
                    component_roles_by_family[family][component],
                    family_roles=roles_by_family[family],
                    extracts_by_role=extracts_by_role,
                )
                for component in replayed_components
            },
            "component_missing_reason_codes": {
                component: list(cell["missing_reason_codes"])
                for component, cell in replayed_components.items()
            },
            "matchup_component_count": 0,
            "matchup_edge_score": None,
            "annotation_row_present": False,
        })
    return rows


def _normalize_catalog_evidence(
    value: object,
    *,
    lock_instant: datetime,
) -> dict[str, object]:
    item = _mapping(value, label="player catalog temporal evidence")
    _exact_keys(item, _CATALOG_EVIDENCE_FIELDS, label="player catalog temporal evidence")
    maximum_event, maximum_event_instant = _timestamp(
        item["maximum_source_event_time_utc"],
        label="player catalog maximum source event",
    )
    observed_at, observed_instant = _timestamp(
        item["observed_at_utc"], label="player catalog observed at"
    )
    basis = item["observed_at_basis"]
    evidence_class = item["evidence_class"]
    if (
        maximum_event_instant >= lock_instant
        or basis not in OBSERVED_AT_BASES
        or basis == "unknown"
        or evidence_class not in EVIDENCE_CLASSES
    ):
        _fail("player catalog temporal evidence differs")
    if evidence_class == EVIDENCE_CONTEMPORANEOUS and (
        basis not in _CONTEMPORANEOUS_BASES
        or observed_instant >= lock_instant
    ):
        _fail("contemporaneous player catalog was not observed before lock")
    return {
        "role": "player-catalog",
        "source_period_kind": "prelock-snapshot",
        "source_season_week_min": None,
        "source_season_week_max": None,
        "maximum_source_event_time_utc": maximum_event,
        "observed_at_utc": observed_at,
        "observed_at_basis": basis,
        "evidence_class": evidence_class,
        "missingness_reason": None,
    }


def _temporal_evidence_for_extract(
    extract: Mapping[str, object],
) -> dict[str, object]:
    return {
        key: extract[key]
        for key in (
            "role",
            "source_period_kind",
            "source_season_week_min",
            "source_season_week_max",
            "maximum_source_event_time_utc",
            "observed_at_utc",
            "observed_at_basis",
            "evidence_class",
            "missingness_reason",
        )
    }


def _normalize_query_job(value: object) -> dict[str, object]:
    item = _mapping(value, label="query job")
    _exact_keys(item, _QUERY_JOB_FIELDS, label="query job")
    created, created_dt = _timestamp(item["created"], label="query job created")
    started, started_dt = _timestamp(item["started"], label="query job started")
    ended, ended_dt = _timestamp(item["ended"], label="query job ended")
    total_bytes = item["total_bytes_processed"]
    if (
        created_dt > started_dt
        or started_dt > ended_dt
        or type(item["cache_hit"]) is not bool
        or item["error_result"] is not None
        or type(total_bytes) is not int
        or isinstance(total_bytes, bool)
        or total_bytes < 0
    ):
        _fail("query job timing/result differs")
    return {
        "project": _string(item["project"], label="query job project"),
        "location": _string(item["location"], label="query job location"),
        "job_id": _string(item["job_id"], label="query job id"),
        "created": created,
        "started": started,
        "ended": ended,
        "cache_hit": item["cache_hit"],
        "error_result": None,
        "total_bytes_processed": total_bytes,
    }


def _normalize_source_relations(
    value: object,
    *,
    extracts_by_role: Mapping[str, Mapping[str, object]],
) -> list[dict[str, object]]:
    by_role: dict[str, dict[str, object]] = {}
    for offset, raw_relation in enumerate(
        _sequence(value, label="source relations")
    ):
        item = _mapping(raw_relation, label=f"source relation[{offset}]")
        _exact_keys(item, _SOURCE_RELATION_FIELDS, label=f"source relation[{offset}]")
        role = _string(item["role"], label=f"source relation[{offset}] role")
        if role in by_role or role not in extracts_by_role:
            _fail(f"source relation[{offset}] role differs")
        extract = extracts_by_role[role]
        modified, _ = _timestamp(
            item["modified_or_created_at_utc"],
            label=f"source relation[{offset}] modified",
        )
        row_count = item["row_count"]
        normalized = {
            "role": role,
            "table_or_object": _reject_semantic_identifier(
                item["table_or_object"],
                label=f"source relation[{offset}] object",
            ),
            "schema_sha256": _digest(
                item["schema_sha256"],
                label=f"source relation[{offset}] schema",
            ),
            "etag_or_generation": _string(
                item["etag_or_generation"],
                label=f"source relation[{offset}] generation",
            ),
            "modified_or_created_at_utc": modified,
            "exact_extract_sha256": _digest(
                item["exact_extract_sha256"],
                label=f"source relation[{offset}] extract",
            ),
            "row_count": row_count,
        }
        if (
            normalized["table_or_object"] != extract["relation_or_object"]
            or normalized["schema_sha256"]
            != extract["source_role_schema_sha256"]
            or normalized["exact_extract_sha256"] != extract["rows_sha256"]
            or type(row_count) is not int
            or isinstance(row_count, bool)
            or row_count != extract["row_count"]
        ):
            _fail(f"source relation[{offset}] does not bind its extract")
        by_role[role] = normalized
    if set(by_role) != set(extracts_by_role):
        _fail("source relation role coverage differs")
    return [by_role[role] for role in sorted(by_role)]


def _normalize_capture_metadata(
    value: object,
    *,
    slate: Mapping[str, object],
    lock_time_utc: str,
    lock_instant: datetime,
    extracts: Sequence[Mapping[str, object]],
    extracts_by_role: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    item = _mapping(value, label="query job receipt input")
    _exact_keys(item, _CAPTURE_METADATA_FIELDS, label="query job receipt input")
    created_at, created_dt = _timestamp(
        item["created_at_utc"], label="capture created at"
    )
    snapshot_at, snapshot_dt = _timestamp(
        item["query_snapshot_at_utc"], label="query snapshot at"
    )
    query_job = _normalize_query_job(item["query_job"])
    _, query_ended_dt = _timestamp(query_job["ended"], label="query job ended")
    if snapshot_dt > query_ended_dt or query_ended_dt > created_dt:
        _fail("query snapshot/job/capture chronology differs")
    query_parameters = dict(_mapping(
        item["query_parameters"], label="query parameters"
    ))
    query_parameters = dict(_json_copy(query_parameters, label="query parameters"))
    _reject_outcome_fields(query_parameters, label="query parameters")
    expected_parameters = {
        "season": slate["season"],
        "week": slate["week"],
        "slate_id": slate["slate_id"],
        "task_id": slate["task_id"],
        "lock_time_utc": lock_time_utc,
        "source_roles": sorted(extracts_by_role),
    }
    if query_parameters != expected_parameters:
        _fail("query parameters do not exactly bind slate/lock/source roles")
    source_relations = _normalize_source_relations(
        item["source_relations"], extracts_by_role=extracts_by_role
    )
    catalog_evidence = _normalize_catalog_evidence(
        item["player_catalog_evidence"], lock_instant=lock_instant
    )
    temporal = [catalog_evidence] + [
        _temporal_evidence_for_extract(extract) for extract in extracts
    ]
    temporal.sort(key=lambda row: str(row["role"]))
    for row in temporal:
        observed = row["observed_at_utc"]
        if observed is not None:
            _, observed_dt = _timestamp(observed, label="component observed at")
            if observed_dt > created_dt:
                _fail("component observation occurs after capture creation")
    for relation in source_relations:
        _, relation_dt = _timestamp(
            relation["modified_or_created_at_utc"],
            label="source relation modified",
        )
        if relation_dt > created_dt:
            _fail("source relation modification occurs after capture")
    used_temporal = [
        row for row in temporal
        if row["role"] == "player-catalog"
        or extracts_by_role[str(row["role"])]["row_count"] > 0
    ]
    evidence_class = _weakest_evidence(
        [str(row["evidence_class"]) for row in used_temporal],
        label="capture",
    )
    maximum_events = [
        str(row["maximum_source_event_time_utc"])
        for row in used_temporal
        if row["maximum_source_event_time_utc"] is not None
    ]
    observed_values = [
        str(row["observed_at_utc"])
        for row in used_temporal
        if row["observed_at_utc"] is not None
    ]
    authoritative_pit = (
        evidence_class == EVIDENCE_CONTEMPORANEOUS
        and created_dt < lock_instant
        and snapshot_dt < lock_instant
        and all(
            row["observed_at_utc"] is not None
            and _timestamp(
                row["observed_at_utc"], label="component observed at"
            )[1] < lock_instant
            for row in used_temporal
        )
    )
    return {
        "created_at_utc": created_at,
        "query_parameters": query_parameters,
        "query_snapshot_at_utc": snapshot_at,
        "query_job": query_job,
        "source_relations": source_relations,
        "component_temporal_evidence": temporal,
        "maximum_source_event_time_utc": max(maximum_events),
        "maximum_observed_at_utc": max(observed_values),
        "evidence_class": evidence_class,
        "authoritative_pit": authoritative_pit,
    }


def _build_source_export(
    *,
    slate: Mapping[str, object],
    lock_time_utc: str,
    created_at_utc: str,
    evidence_class: str,
    family_definitions: Mapping[str, Mapping[str, object]],
    player_catalog_identity: Mapping[str, object],
    player_catalog_content_sha256: str,
    target_spine_replay: Mapping[str, object],
    source_extracts: Sequence[Mapping[str, object]],
    eligible_players: Sequence[Mapping[str, object]],
    rows: Sequence[Mapping[str, object]],
    component_value_replay: Mapping[str, object],
) -> dict[str, object]:
    ordered_ids = [str(player["gsis_id"]) for player in eligible_players]
    body = {
        "schema_version": SOURCE_EXPORT_SCHEMA,
        "publication_mode": PUBLICATION_MODE,
        "slate": dict(slate),
        "lock_time_utc": lock_time_utc,
        "created_at_utc": created_at_utc,
        "evidence_class": evidence_class,
        "family_definition_identities": {
            family: dict(family_definitions[family])
            for family in ELIGIBLE_FAMILIES
        },
        "player_catalog_identity": dict(player_catalog_identity),
        "player_catalog_content_sha256": player_catalog_content_sha256,
        "target_spine_replay": dict(target_spine_replay),
        "percentile_universe": {
            "name": "catalog-skill-player-universe-v1",
            "ordered_player_ids_sha256": canonical_sha256(ordered_ids),
            "row_count": len(ordered_ids),
        },
        "source_extracts": list(source_extracts),
        "eligible_player_count": len(eligible_players),
        "eligible_players_sha256": canonical_sha256(list(eligible_players)),
        "rows": list(rows),
        "rows_sha256": canonical_sha256(list(rows)),
        "component_value_replay": dict(component_value_replay),
        "qb_depth_unknown_policy": QB_DEPTH_UNKNOWN_POLICY,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "fill_authority": False,
        "retrieval_authority": False,
        "promotion_authority": False,
        "production_policy_authority": False,
    }
    return _with_self_hash(body, field="matchup_source_export_sha256")


def _normalize_code_identity(value: object) -> dict[str, object]:
    item = dict(_mapping(value, label="code identity"))
    if not item:
        _fail("code identity is empty")
    item = dict(_json_copy(item, label="code identity"))
    _reject_outcome_fields(item, label="code identity")
    for key, nested in item.items():
        if key in _ALLOWED_POLICY_FIELDS:
            continue
        if type(nested) is str and _forbidden_semantic_identifier(nested):
            _fail(f"code identity value {key!r} has forbidden semantics")
    if item.get("uses_realized_outcomes", False) is not False:
        _fail("code identity is not outcome-blind")
    return item


def _sql_table_identifier(value: object, *, label: str) -> str:
    relation = _reject_semantic_identifier(value, label=label)
    match = _BQ_RELATION.fullmatch(relation)
    if match is None:
        _fail(f"{label} must be an exact bq://project.dataset.table relation")
    return match.group(1)


def build_rendered_sql_v1(
    source_relations: Sequence[Mapping[str, object]],
) -> bytes:
    """Render the only SQL template admitted by the corrected capture.

    Relations are emitted in their already-canonical role order.  Every
    referenced table is therefore structurally recoverable from the query and
    must match the receipt's role-to-relation list exactly, including repeated
    physical tables used by distinct roles.
    """
    role_relation_pairs: list[tuple[str, str]] = []
    for offset, raw_relation in enumerate(source_relations):
        relation = _mapping(raw_relation, label=f"SQL source relation[{offset}]")
        role = _string(
            relation.get("role"), label=f"SQL source relation[{offset}] role"
        )
        table = _sql_table_identifier(
            relation.get("table_or_object"),
            label=f"SQL source relation[{offset}] table",
        )
        role_relation_pairs.append((role, table))
    if (
        not role_relation_pairs
        or role_relation_pairs != sorted(role_relation_pairs)
        or len({role for role, _ in role_relation_pairs})
        != len(role_relation_pairs)
    ):
        _fail("SQL source relations are not a canonical role-ordered set")
    source_selects = " UNION ALL ".join(
        "SELECT role, source_event_time_utc, observed_at_utc "
        f"FROM `{table}`"
        for _, table in role_relation_pairs
    )
    return _RENDERED_SQL_TEMPLATE.format(
        source_selects=source_selects
    ).encode("utf-8")


def _normalize_rendered_sql(
    raw: bytes,
    *,
    source_relations: Sequence[Mapping[str, object]],
) -> tuple[str, str]:
    if type(raw) is not bytes or not raw:
        _fail("rendered SQL must be nonempty raw bytes")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusR6MatchupSourceV1Error(
            "rendered SQL is not UTF-8"
        ) from exc
    lowered = text.lower()
    if any(marker in text for marker in ("--", "/*", "*/", "#")):
        _fail("rendered SQL comments are forbidden in the audited query")
    if "'" in text or '"' in text:
        _fail("rendered SQL string literals are forbidden in the audited query")
    statements = [statement.strip() for statement in text.split(";") if statement.strip()]
    if len(statements) != 1:
        _fail("rendered SQL must contain exactly one read-only statement")
    words = re.findall(r"[A-Za-z_][A-Za-z0-9_$-]*", statements[0])
    if not words or words[0].lower() not in {"select", "with"}:
        _fail("rendered SQL must be a SELECT or WITH query")
    mutation = next(
        (word for word in words if word.lower() in _SQL_MUTATION_WORDS),
        None,
    )
    if mutation is not None:
        _fail(f"rendered SQL contains forbidden mutation word {mutation!r}")
    forbidden = next(
        (word for word in words if _forbidden_semantic_identifier(word)),
        None,
    )
    if forbidden is None:
        forbidden = next(
            (
                fragment
                for fragment in _FORBIDDEN_RELATION_FRAGMENTS
                if fragment in lowered
            ),
            None,
        )
    if forbidden is not None:
        _fail(
            "rendered SQL reaches forbidden outcome path/post-lock path "
            f"{forbidden!r}"
        )
    named_parameters = frozenset(
        parameter.lower()
        for parameter in re.findall(r"@([A-Za-z_][A-Za-z0-9_]*)", text)
    )
    if named_parameters != _REQUIRED_QUERY_PARAMETERS:
        _fail("rendered SQL named parameters do not exactly bind the query")
    expected_raw = build_rendered_sql_v1(source_relations)
    if raw != expected_raw:
        _fail("rendered SQL differs from the frozen exact relation-bound template")
    referenced_tables = re.findall(r"\bFROM\s+`([^`]+)`", text)
    expected_tables = [
        _sql_table_identifier(
            relation["table_or_object"], label="rendered SQL source relation"
        )
        for relation in source_relations
    ]
    if referenced_tables != expected_tables:
        _fail("rendered SQL referenced relations differ from source relations")
    return text, sha256(raw).hexdigest()


def _build_query_receipt(
    *,
    slate: Mapping[str, object],
    lock_time_utc: str,
    metadata: Mapping[str, object],
    rendered_sql_raw: bytes,
    code_identity: Mapping[str, object],
    player_catalog_identity: Mapping[str, object],
    source_export_identity: Mapping[str, object],
    target_spine_sha256: str,
    component_value_replay_sha256: str,
    full_season_same_target_year_used: bool,
    target_week_participation_universe_used: bool,
) -> dict[str, object]:
    rendered_sql, rendered_sql_sha = _normalize_rendered_sql(
        rendered_sql_raw,
        source_relations=metadata["source_relations"],
    )
    body = {
        "schema_version": QUERY_RECEIPT_SCHEMA,
        "slate": dict(slate),
        "lock_time_utc": lock_time_utc,
        "created_at_utc": metadata["created_at_utc"],
        "rendered_sql_sha256": rendered_sql_sha,
        "rendered_sql_template_sha256": RENDERED_SQL_TEMPLATE_SHA256,
        "rendered_sql_bytes": rendered_sql,
        "query_parameters": metadata["query_parameters"],
        "query_snapshot_at_utc": metadata["query_snapshot_at_utc"],
        "query_job": metadata["query_job"],
        "code_identity": dict(code_identity),
        "player_catalog_identity": dict(player_catalog_identity),
        "source_export_identity": dict(source_export_identity),
        "target_spine_sha256": target_spine_sha256,
        "component_value_replay_sha256": component_value_replay_sha256,
        "source_relations": metadata["source_relations"],
        "component_temporal_evidence": metadata["component_temporal_evidence"],
        "maximum_source_event_time_utc": metadata[
            "maximum_source_event_time_utc"
        ],
        "maximum_observed_at_utc": metadata["maximum_observed_at_utc"],
        "full_season_same_target_year_used": full_season_same_target_year_used,
        "target_week_participation_universe_used": (
            target_week_participation_universe_used
        ),
        "qb_depth_unknown_policy": QB_DEPTH_UNKNOWN_POLICY,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "evidence_class": metadata["evidence_class"],
        "authoritative_for_mechanics": True,
        "authoritative_pit": metadata["authoritative_pit"],
        "fill_authority": False,
        "retrieval_authority": False,
        "promotion_authority": False,
        "production_policy_authority": False,
    }
    return _with_self_hash(body, field="matchup_query_receipt_sha256")


def _validate_source_export(
    raw: bytes,
    *,
    identity: Mapping[str, object],
    catalog_raw: bytes,
    catalog_identity: Mapping[str, object],
) -> dict[str, object]:
    _bind_raw(raw, identity, label="matchup source export")
    body = _parse_canonical_object(raw, label="matchup source export")
    _exact_keys(body, _SOURCE_EXPORT_FIELDS, label="matchup source export")
    if (
        body["schema_version"] != SOURCE_EXPORT_SCHEMA
        or body["publication_mode"] != PUBLICATION_MODE
        or body["qb_depth_unknown_policy"] != QB_DEPTH_UNKNOWN_POLICY
        or body["outcome_columns_read"] != []
        or body["uses_realized_outcomes"] is not False
        or any(
            body[field] is not False
            for field in (
                "fill_authority",
                "retrieval_authority",
                "promotion_authority",
                "production_policy_authority",
            )
        )
    ):
        _fail("matchup source export policy differs")
    _validate_self_hash(
        body,
        field="matchup_source_export_sha256",
        label="matchup source export",
    )
    slate = _normalize_slate(body["slate"], label="source export slate")
    lock, lock_dt = _timestamp(body["lock_time_utc"], label="source export lock")
    created, created_dt = _timestamp(
        body["created_at_utc"], label="source export created at"
    )
    if body["evidence_class"] not in EVIDENCE_CLASSES:
        _fail("source export evidence class differs")
    supplied_catalog_identity = normalize_object_identity(
        body["player_catalog_identity"], label="source export player catalog"
    )
    if supplied_catalog_identity != dict(catalog_identity):
        _fail("source export binds a different player catalog")
    _, eligible, catalog_context_by_id, catalog_content_sha = _normalize_catalog(
        catalog_raw, catalog_identity, expected_task_id=str(slate["task_id"])
    )
    if body["player_catalog_content_sha256"] != catalog_content_sha:
        _fail("source export catalog content hash differs")
    (
        family_definitions,
        roles_by_family,
        schemas_by_role,
        component_roles_by_family,
        missing_codes_by_family,
    ) = _normalize_family_definitions(body["family_definition_identities"])
    extracts, extracts_by_role = _normalize_source_extracts(
        body["source_extracts"],
        slate=slate,
        lock_instant=lock_dt,
        roles_by_family=roles_by_family,
        schemas_by_role=schemas_by_role,
    )
    qb_depth_by_id, target_spine_replay = _validate_schedule_and_depth_sources(
        slate=slate,
        lock_time_utc=lock,
        eligible_players=eligible,
        catalog_context_by_id=catalog_context_by_id,
        extracts_by_role=extracts_by_role,
    )
    if body["target_spine_replay"] != target_spine_replay:
        _fail("source export target-spine replay differs")
    component_replay_by_player, retained_source_cell_count = (
        _replay_component_values(
            slate=slate,
            eligible_players=eligible,
            catalog_context_by_id=catalog_context_by_id,
            roles_by_family=roles_by_family,
            component_roles_by_family=component_roles_by_family,
            missing_codes_by_family=missing_codes_by_family,
            extracts_by_role=extracts_by_role,
        )
    )
    for extract in extracts:
        observed = extract["observed_at_utc"]
        if observed is not None and _timestamp(
            observed, label="source extract observed at"
        )[1] > created_dt:
            _fail("source extract observation occurs after export creation")
    raw_rows = _sequence(body["rows"], label="source export rows")
    annotation_inputs: list[dict[str, object]] = []
    for offset, raw_row in enumerate(raw_rows):
        row = dict(_mapping(raw_row, label=f"source export row[{offset}]"))
        _exact_keys(row, _FINAL_ROW_FIELDS, label=f"source export row[{offset}]")
        if type(row["annotation_row_present"]) is not bool:
            _fail(f"source export row[{offset}] presence differs")
        if row["annotation_row_present"] is True:
            annotation_inputs.append({
                key: row[key] for key in _ANNOTATION_INPUT_FIELDS
            })
    rebuilt_rows = _normalize_annotation_rows(
        annotation_inputs,
        eligible_players=eligible,
        roles_by_family=roles_by_family,
        component_roles_by_family=component_roles_by_family,
        extracts_by_role=extracts_by_role,
        qb_depth_by_id=qb_depth_by_id,
        component_replay_by_player=component_replay_by_player,
    )
    if canonical_json_bytes(list(raw_rows)) != canonical_json_bytes(rebuilt_rows):
        _fail("source export row completeness/canonical replay differs")
    ordered_ids = [str(player["gsis_id"]) for player in eligible]
    expected_universe = {
        "name": "catalog-skill-player-universe-v1",
        "ordered_player_ids_sha256": canonical_sha256(ordered_ids),
        "row_count": len(ordered_ids),
    }
    if (
        body["percentile_universe"] != expected_universe
        or body["eligible_player_count"] != len(eligible)
        or body["eligible_players_sha256"] != canonical_sha256(eligible)
        or body["rows_sha256"] != canonical_sha256(rebuilt_rows)
    ):
        _fail("source export population/universe hashes differ")
    component_value_replay = _build_component_value_replay(
        slate=slate,
        eligible_players=eligible,
        catalog_context_by_id=catalog_context_by_id,
        target_spine_replay=target_spine_replay,
        roles_by_family=roles_by_family,
        component_roles_by_family=component_roles_by_family,
        missing_codes_by_family=missing_codes_by_family,
        extracts_by_role=extracts_by_role,
        qb_depth_by_id=qb_depth_by_id,
        annotation_rows=annotation_inputs,
        component_replay_by_player=component_replay_by_player,
        retained_source_cell_count=retained_source_cell_count,
        normalized_rows=rebuilt_rows,
    )
    if body["component_value_replay"] != component_value_replay:
        _fail("source export component-value replay differs")
    used_extract_classes = [
        str(extract["evidence_class"])
        for extract in extracts
        if int(extract["row_count"]) > 0
    ]
    if used_extract_classes and _EVIDENCE_RANK[str(body["evidence_class"])] > min(
        _EVIDENCE_RANK[value] for value in used_extract_classes
    ):
        _fail("source export evidence class exceeds a component source")
    return {
        **body,
        "slate": slate,
        "lock_time_utc": lock,
        "created_at_utc": created,
        "family_definition_identities": family_definitions,
        "source_extracts": extracts,
        "rows": rebuilt_rows,
    }


def _validate_temporal_evidence(
    value: object,
    *,
    extracts_by_role: Mapping[str, Mapping[str, object]],
    lock_instant: datetime,
) -> tuple[list[dict[str, object]], str, str, str]:
    raw_items = _sequence(value, label="component temporal evidence")
    by_role: dict[str, dict[str, object]] = {}
    catalog_item: dict[str, object] | None = None
    expected_extract_items = {
        role: _temporal_evidence_for_extract(extract)
        for role, extract in extracts_by_role.items()
    }
    for offset, raw_item in enumerate(raw_items):
        item = dict(_mapping(raw_item, label=f"temporal evidence[{offset}]"))
        role = _string(item.get("role"), label=f"temporal evidence[{offset}] role")
        if role in by_role:
            _fail("component temporal evidence repeats a role")
        if role == "player-catalog":
            expected_fields = set(_temporal_evidence_for_extract({
                "role": role,
                "source_period_kind": "prelock-snapshot",
                "source_season_week_min": None,
                "source_season_week_max": None,
                "maximum_source_event_time_utc": None,
                "observed_at_utc": None,
                "observed_at_basis": "unknown",
                "evidence_class": EVIDENCE_NON_PIT,
                "missingness_reason": None,
            }))
            if set(item) != expected_fields:
                _fail("player catalog temporal evidence fields differ")
            catalog_evidence = {
                key: item[key]
                for key in _CATALOG_EVIDENCE_FIELDS
            }
            catalog_item = _normalize_catalog_evidence(
                catalog_evidence, lock_instant=lock_instant
            )
            if item != catalog_item:
                _fail("player catalog temporal evidence replay differs")
            normalized = catalog_item
        else:
            if role not in expected_extract_items or item != expected_extract_items[role]:
                _fail("component temporal evidence differs from source extracts")
            normalized = item
        by_role[role] = normalized
    if catalog_item is None or set(by_role) != {"player-catalog", *extracts_by_role}:
        _fail("component temporal evidence role coverage differs")
    ordered = [by_role[role] for role in sorted(by_role)]
    used = [catalog_item] + [
        by_role[role]
        for role, extract in extracts_by_role.items()
        if int(extract["row_count"]) > 0
    ]
    evidence_class = _weakest_evidence(
        [str(item["evidence_class"]) for item in used], label="query receipt"
    )
    maximum_events = [
        str(item["maximum_source_event_time_utc"])
        for item in used
        if item["maximum_source_event_time_utc"] is not None
    ]
    observed_values = [
        str(item["observed_at_utc"])
        for item in used
        if item["observed_at_utc"] is not None
    ]
    return ordered, evidence_class, max(maximum_events), max(observed_values)


def _validate_query_receipt(
    raw: bytes,
    *,
    identity: Mapping[str, object],
    source_export: Mapping[str, object],
    source_export_identity: Mapping[str, object],
    player_catalog_identity: Mapping[str, object],
) -> dict[str, object]:
    _bind_raw(raw, identity, label="matchup query receipt")
    body = _parse_canonical_object(raw, label="matchup query receipt")
    _exact_keys(body, _QUERY_RECEIPT_FIELDS, label="matchup query receipt")
    if (
        body["schema_version"] != QUERY_RECEIPT_SCHEMA
        or body["rendered_sql_template_sha256"]
        != RENDERED_SQL_TEMPLATE_SHA256
        or body["outcome_columns_read"] != []
        or body["uses_realized_outcomes"] is not False
        or body["authoritative_for_mechanics"] is not True
        or body["full_season_same_target_year_used"] is not False
        or body["target_week_participation_universe_used"] is not False
        or body["qb_depth_unknown_policy"] != QB_DEPTH_UNKNOWN_POLICY
        or any(
            body[field] is not False
            for field in (
                "fill_authority",
                "retrieval_authority",
                "promotion_authority",
                "production_policy_authority",
            )
        )
    ):
        _fail("matchup query receipt policy differs")
    _validate_self_hash(
        body,
        field="matchup_query_receipt_sha256",
        label="matchup query receipt",
    )
    slate = _normalize_slate(body["slate"], label="query receipt slate")
    if slate != source_export["slate"]:
        _fail("query receipt slate differs from source export")
    lock, lock_dt = _timestamp(body["lock_time_utc"], label="query receipt lock")
    created, created_dt = _timestamp(
        body["created_at_utc"], label="query receipt created at"
    )
    if (
        lock != source_export["lock_time_utc"]
        or created != source_export["created_at_utc"]
    ):
        _fail("query receipt time binding differs from source export")
    if normalize_object_identity(
        body["player_catalog_identity"], label="query receipt player catalog"
    ) != dict(player_catalog_identity):
        _fail("query receipt binds a different player catalog")
    if normalize_object_identity(
        body["source_export_identity"], label="query receipt source export"
    ) != dict(source_export_identity):
        _fail("query receipt binds a different source export")
    if (
        _digest(
            body["target_spine_sha256"],
            label="query receipt target-spine replay",
        )
        != source_export["target_spine_replay"]["target_spine_sha256"]
        or _digest(
            body["component_value_replay_sha256"],
            label="query receipt component-value replay",
        )
        != source_export["component_value_replay"][
            "component_value_replay_sha256"
        ]
        or body["full_season_same_target_year_used"]
        is not source_export["component_value_replay"][
            "full_season_same_target_year_used"
        ]
        or body["target_week_participation_universe_used"]
        is not source_export["component_value_replay"][
            "target_week_participation_universe_used"
        ]
    ):
        _fail("query receipt replay identities differ from source export")
    rendered_sql = _string(body["rendered_sql_bytes"], label="rendered SQL bytes")
    _, rendered_sha = _normalize_rendered_sql(
        rendered_sql.encode("utf-8"),
        source_relations=_sequence(
            body["source_relations"], label="query receipt source relations"
        ),
    )
    if body["rendered_sql_sha256"] != rendered_sha:
        _fail("rendered SQL hash differs")
    query_parameters = dict(_mapping(
        body["query_parameters"], label="query receipt parameters"
    ))
    _reject_outcome_fields(query_parameters, label="query receipt parameters")
    snapshot_at, snapshot_dt = _timestamp(
        body["query_snapshot_at_utc"], label="query receipt snapshot"
    )
    query_job = _normalize_query_job(body["query_job"])
    _, query_end_dt = _timestamp(query_job["ended"], label="query job ended")
    if snapshot_dt > query_end_dt or query_end_dt > created_dt:
        _fail("query receipt chronology differs")
    extracts_by_role = {
        str(extract["role"]): extract
        for extract in source_export["source_extracts"]
    }
    expected_parameters = {
        "season": slate["season"],
        "week": slate["week"],
        "slate_id": slate["slate_id"],
        "task_id": slate["task_id"],
        "lock_time_utc": lock,
        "source_roles": sorted(extracts_by_role),
    }
    if query_parameters != expected_parameters:
        _fail("query receipt parameters differ from slate/lock/source roles")
    source_relations = _normalize_source_relations(
        body["source_relations"], extracts_by_role=extracts_by_role
    )
    temporal, evidence_class, maximum_event, maximum_observed = (
        _validate_temporal_evidence(
            body["component_temporal_evidence"],
            extracts_by_role=extracts_by_role,
            lock_instant=lock_dt,
        )
    )
    for item in temporal:
        observed = item["observed_at_utc"]
        if observed is not None and _timestamp(
            observed, label="component observed at"
        )[1] > created_dt:
            _fail("component observation occurs after receipt creation")
    authoritative_pit = (
        evidence_class == EVIDENCE_CONTEMPORANEOUS
        and created_dt < lock_dt
        and snapshot_dt < lock_dt
        and all(
            item["observed_at_utc"] is not None
            and _timestamp(
                item["observed_at_utc"], label="component observed at"
            )[1] < lock_dt
            for item in temporal
            if item["role"] == "player-catalog"
            or int(extracts_by_role[str(item["role"])]["row_count"]) > 0
        )
    )
    if (
        body["evidence_class"] != evidence_class
        or source_export["evidence_class"] != evidence_class
        or body["maximum_source_event_time_utc"] != maximum_event
        or body["maximum_observed_at_utc"] != maximum_observed
        or body["authoritative_pit"] is not authoritative_pit
    ):
        _fail("query receipt derived temporal policy differs")
    code_identity = _normalize_code_identity(body["code_identity"])
    return {
        **body,
        "slate": slate,
        "lock_time_utc": lock,
        "created_at_utc": created,
        "query_snapshot_at_utc": snapshot_at,
        "query_job": query_job,
        "code_identity": code_identity,
        "source_relations": source_relations,
        "component_temporal_evidence": temporal,
    }


def _publish_and_reopen(
    *,
    uri: str,
    body: Mapping[str, object],
    publish_create_once: Callable[[str, bytes], Mapping[str, object]],
    read_exact: Callable[[Mapping[str, object]], bytes],
    label: str,
) -> tuple[dict[str, object], bytes]:
    raw = canonical_json_bytes(body)
    identity = normalize_object_identity(
        publish_create_once(uri, raw), label=f"published {label}"
    )
    if identity["uri"] != uri:
        _fail(f"published {label} URI differs")
    _bind_raw(raw, identity, label=f"published {label}")
    reopened = _read_exact(read_exact, identity, label=f"reopened {label}")
    if reopened != raw:
        _fail(f"reopened {label} bytes differ")
    return identity, reopened


def _normalize_output_prefix(value: object) -> str:
    prefix = _string(value, label="matchup output prefix").rstrip("/")
    if (
        not prefix.startswith("gs://")
        or "/" not in prefix[5:]
        or "?" in prefix
        or "#" in prefix
        or any(part in {"", ".", ".."} for part in prefix[5:].split("/"))
    ):
        _fail("matchup output prefix is not a bounded GCS prefix")
    return prefix


def capture_matchup_source_v1(
    *,
    slate: Mapping[str, object],
    lock_time_utc: str,
    player_catalog_identity: Mapping[str, object],
    player_catalog_raw: bytes,
    rendered_sql_raw: bytes,
    query_job_receipt: Mapping[str, object],
    component_extracts: Sequence[Mapping[str, object]],
    annotation_rows: Sequence[Mapping[str, object]],
    family_definition_identities: Mapping[str, Mapping[str, object]],
    code_identity: Mapping[str, object],
    publish_create_once: Callable[[str, bytes], Mapping[str, object]],
    read_exact: Callable[[Mapping[str, object]], bytes],
    output_prefix: str,
) -> dict[str, Mapping[str, object]]:
    """Publish, exact-reopen, and bind one corrected matchup source pair.

    Both storage operations are injected create-once calls.  The function
    returns only the normalized export and receipt identities; it exposes no
    live storage handle and no caller-supplied temporal verdict.
    """
    normalized_slate = _normalize_slate(slate, label="capture slate")
    lock, lock_dt = _timestamp(lock_time_utc, label="capture lock time")
    catalog_identity = normalize_object_identity(
        player_catalog_identity, label="player catalog"
    )
    exact_catalog_raw = _read_exact(
        read_exact, catalog_identity, label="player catalog"
    )
    if exact_catalog_raw != player_catalog_raw:
        _fail("provided player catalog bytes differ from exact reopen")
    _, eligible, catalog_context_by_id, catalog_content_sha = _normalize_catalog(
        exact_catalog_raw,
        catalog_identity,
        expected_task_id=str(normalized_slate["task_id"]),
    )
    (
        family_definitions,
        roles_by_family,
        schemas_by_role,
        component_roles_by_family,
        missing_codes_by_family,
    ) = _normalize_family_definitions(family_definition_identities)
    extracts, extracts_by_role = _normalize_source_extracts(
        component_extracts,
        slate=normalized_slate,
        lock_instant=lock_dt,
        roles_by_family=roles_by_family,
        schemas_by_role=schemas_by_role,
    )
    qb_depth_by_id, target_spine_replay = _validate_schedule_and_depth_sources(
        slate=normalized_slate,
        lock_time_utc=lock,
        eligible_players=eligible,
        catalog_context_by_id=catalog_context_by_id,
        extracts_by_role=extracts_by_role,
    )
    component_replay_by_player, retained_source_cell_count = (
        _replay_component_values(
            slate=normalized_slate,
            eligible_players=eligible,
            catalog_context_by_id=catalog_context_by_id,
            roles_by_family=roles_by_family,
            component_roles_by_family=component_roles_by_family,
            missing_codes_by_family=missing_codes_by_family,
            extracts_by_role=extracts_by_role,
        )
    )
    metadata = _normalize_capture_metadata(
        query_job_receipt,
        slate=normalized_slate,
        lock_time_utc=lock,
        lock_instant=lock_dt,
        extracts=extracts,
        extracts_by_role=extracts_by_role,
    )
    normalized_code_identity = _normalize_code_identity(code_identity)
    _normalize_rendered_sql(
        rendered_sql_raw,
        source_relations=metadata["source_relations"],
    )
    rows = _normalize_annotation_rows(
        annotation_rows,
        eligible_players=eligible,
        roles_by_family=roles_by_family,
        component_roles_by_family=component_roles_by_family,
        extracts_by_role=extracts_by_role,
        qb_depth_by_id=qb_depth_by_id,
        component_replay_by_player=component_replay_by_player,
    )
    component_value_replay = _build_component_value_replay(
        slate=normalized_slate,
        eligible_players=eligible,
        catalog_context_by_id=catalog_context_by_id,
        target_spine_replay=target_spine_replay,
        roles_by_family=roles_by_family,
        component_roles_by_family=component_roles_by_family,
        missing_codes_by_family=missing_codes_by_family,
        extracts_by_role=extracts_by_role,
        qb_depth_by_id=qb_depth_by_id,
        annotation_rows=annotation_rows,
        component_replay_by_player=component_replay_by_player,
        retained_source_cell_count=retained_source_cell_count,
        normalized_rows=rows,
    )
    export = _build_source_export(
        slate=normalized_slate,
        lock_time_utc=lock,
        created_at_utc=str(metadata["created_at_utc"]),
        evidence_class=str(metadata["evidence_class"]),
        family_definitions=family_definitions,
        player_catalog_identity=catalog_identity,
        player_catalog_content_sha256=catalog_content_sha,
        target_spine_replay=target_spine_replay,
        source_extracts=extracts,
        eligible_players=eligible,
        rows=rows,
        component_value_replay=component_value_replay,
    )
    prefix = _normalize_output_prefix(output_prefix)
    export_identity, _ = _publish_and_reopen(
        uri=f"{prefix}/matchup-source-export.json",
        body=export,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="matchup source export",
    )
    receipt = _build_query_receipt(
        slate=normalized_slate,
        lock_time_utc=lock,
        metadata=metadata,
        rendered_sql_raw=rendered_sql_raw,
        code_identity=normalized_code_identity,
        player_catalog_identity=catalog_identity,
        source_export_identity=export_identity,
        target_spine_sha256=str(target_spine_replay["target_spine_sha256"]),
        component_value_replay_sha256=str(
            component_value_replay["component_value_replay_sha256"]
        ),
        full_season_same_target_year_used=bool(
            component_value_replay["full_season_same_target_year_used"]
        ),
        target_week_participation_universe_used=bool(
            component_value_replay[
                "target_week_participation_universe_used"
            ]
        ),
    )
    receipt_identity, _ = _publish_and_reopen(
        uri=f"{prefix}/matchup-query-receipt.json",
        body=receipt,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="matchup query receipt",
    )
    reopen_matchup_source_snapshot(
        source_export_identity=export_identity,
        query_receipt_identity=receipt_identity,
        player_catalog_identity=catalog_identity,
        read_exact=read_exact,
        expected_slate=normalized_slate,
        required_evidence_class=str(metadata["evidence_class"]),
    )
    return {
        "source_export_identity": export_identity,
        "query_receipt_identity": receipt_identity,
    }


def validate_reopened_matchup_source_snapshot(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Validate the corrected, exact-reopened projection consumed by R6-v2.

    Exact object reads happen in :func:`reopen_matchup_source_snapshot`.  This
    projection validator gives downstream pure runners a fail-closed boundary:
    legacy caller-asserted PIT snapshots cannot be substituted, and every
    score-relevant row/proof hash must remain coherent after reopening.
    """
    body = dict(_mapping(value, label="reopened matchup source"))
    _exact_keys(body, _REOPENED_SOURCE_FIELDS, label="reopened matchup source")
    if (
        body["schema_version"] != REOPENED_SOURCE_SCHEMA
        or body["evidence_class"] not in EVIDENCE_CLASSES
        or body["qb_depth_unknown_policy"] != QB_DEPTH_UNKNOWN_POLICY
        or body["authoritative_for_mechanics"] is not True
        or type(body["authoritative_pit"]) is not bool
        or body["outcome_columns_read"] != []
        or body["uses_realized_outcomes"] is not False
        or body["full_season_same_target_year_used"] is not False
        or body["target_week_participation_universe_used"] is not False
        or any(
            body[field] is not False
            for field in (
                "fill_authority",
                "retrieval_authority",
                "promotion_authority",
                "production_policy_authority",
            )
        )
    ):
        _fail("reopened matchup source policy differs")
    slate = _normalize_slate(body["slate"], label="reopened matchup source slate")
    lock, lock_dt = _timestamp(body["lock_time_utc"], label="reopened source lock")
    created, _ = _timestamp(
        body["created_at_utc"], label="reopened source created"
    )
    query_snapshot, _ = _timestamp(
        body["query_snapshot_at_utc"], label="reopened source query snapshot"
    )
    maximum_event, maximum_event_dt = _timestamp(
        body["maximum_source_event_time_utc"],
        label="reopened source maximum event",
    )
    maximum_observed, _ = _timestamp(
        body["maximum_observed_at_utc"],
        label="reopened source maximum observed",
    )
    if maximum_event_dt >= lock_dt:
        _fail("reopened matchup source reaches or follows lock")
    source_identity = normalize_object_identity(
        body["source_export_identity"], label="reopened source export"
    )
    receipt_identity = normalize_object_identity(
        body["query_receipt_identity"], label="reopened query receipt"
    )
    catalog_identity = normalize_object_identity(
        body["player_catalog_identity"], label="reopened player catalog"
    )
    family_definitions = _mapping(
        body["family_definition_identities"],
        label="reopened family definitions",
    )
    if set(family_definitions) != set(ELIGIBLE_FAMILIES):
        _fail("reopened family definition coverage differs")
    source_extracts = list(_sequence(
        body["source_extracts"], label="reopened source extracts"
    ))
    if not source_extracts:
        _fail("reopened source extracts are empty")

    rows: list[dict[str, object]] = []
    eligible_rows: list[dict[str, object]] = []
    ordered_ids: list[str] = []
    for offset, raw_row in enumerate(
        _sequence(body["rows"], label="reopened source rows")
    ):
        row = dict(_mapping(raw_row, label=f"reopened source row[{offset}]"))
        _exact_keys(row, _FINAL_ROW_FIELDS, label=f"reopened source row[{offset}]")
        player_id = _string(
            row["gsis_id"], label=f"reopened source row[{offset}] player"
        )
        family = row["family"]
        position = row["position"]
        depth = row["qb_depth1"]
        depth_evidence = row["qb_depth_evidence_class"]
        if (
            family not in ELIGIBLE_FAMILIES
            or _FAMILY_BY_POSITION.get(str(position)) != family
            or (family == "qb" and depth is not None and type(depth) is not bool)
            or (
                family == "qb"
                and depth is None
                and depth_evidence != "unknown"
            )
            or (
                family == "qb"
                and depth is not None
                and depth_evidence not in EVIDENCE_CLASSES
            )
            or (
                family != "qb"
                and (depth is not None or depth_evidence != "not-applicable")
            )
            or type(row["annotation_row_present"]) is not bool
        ):
            _fail(f"reopened source row[{offset}] family/depth differs")
        values = dict(_mapping(
            row["component_values"], label=f"reopened source row[{offset}] values"
        ))
        support = dict(_mapping(
            row["component_support"], label=f"reopened source row[{offset}] support"
        ))
        bounds = dict(_mapping(
            row["component_source_bounds"],
            label=f"reopened source row[{offset}] bounds",
        ))
        missing = dict(_mapping(
            row["component_missing_reason_codes"],
            label=f"reopened source row[{offset}] missing reasons",
        ))
        if (
            not values
            or set(values) != set(support)
            or set(values) != set(bounds)
            or set(values) != set(missing)
        ):
            _fail(f"reopened source row[{offset}] component dictionaries differ")
        normalized_values: dict[str, object] = {}
        supported_values: list[float] = []
        for component in sorted(values):
            if _NAME.fullmatch(component) is None or _forbidden_semantic_identifier(component):
                _fail(f"reopened source row[{offset}] component name differs")
            component_supported = support[component]
            component_value = values[component]
            reason_codes = [
                _string(code, label="reopened component missing reason")
                for code in _sequence(
                    missing[component], label="reopened component missing reasons"
                )
            ]
            raw_bound = _mapping(
                bounds[component], label="reopened component source bound"
            )
            _exact_keys(
                raw_bound,
                _COMPONENT_BOUND_FIELDS,
                label="reopened component source bound",
            )
            if (
                type(component_supported) is not bool
                or reason_codes != sorted(reason_codes)
                or len(reason_codes) != len(set(reason_codes))
            ):
                _fail(f"reopened source row[{offset}] component support differs")
            if component_supported:
                if (
                    isinstance(component_value, bool)
                    or not isinstance(component_value, (int, float))
                    or not math.isfinite(float(component_value))
                    or not 0.0 <= float(component_value) <= 1.0
                ):
                    _fail(f"reopened source row[{offset}] component value differs")
                normalized_value: object = float(component_value)
                supported_values.append(float(component_value))
            else:
                if component_value is not None or not reason_codes:
                    _fail(f"reopened source row[{offset}] missing component differs")
                normalized_value = None
            normalized_values[component] = normalized_value
        component_count = row["matchup_component_count"]
        expected_edge = (
            _frozen_mean(supported_values) if len(supported_values) >= 2 else None
        )
        edge = row["matchup_edge_score"]
        if (
            type(component_count) is not int
            or isinstance(component_count, bool)
            or component_count != len(supported_values)
            or (
                edge is not None
                and (
                    isinstance(edge, bool)
                    or not isinstance(edge, (int, float))
                    or not math.isfinite(float(edge))
                    or not 0.0 <= float(edge) <= 1.0
                )
            )
            or (None if edge is None else float(edge)) != expected_edge
            or (
                row["annotation_row_present"] is False
                and len(supported_values) > 0
            )
        ):
            _fail(f"reopened source row[{offset}] frozen edge differs")
        row["component_values"] = normalized_values
        rows.append(row)
        ordered_ids.append(player_id)
        eligible_rows.append({
            "gsis_id": player_id,
            "family": family,
            "position": position,
        })
    if (
        not rows
        or ordered_ids != sorted(ordered_ids)
        or len(ordered_ids) != len(set(ordered_ids))
        or body["eligible_player_count"] != len(rows)
        or body["eligible_players_sha256"] != canonical_sha256(eligible_rows)
        or body["rows_sha256"] != canonical_sha256(rows)
    ):
        _fail("reopened source row population/hashes differ")
    expected_universe = {
        "name": "catalog-skill-player-universe-v1",
        "ordered_player_ids_sha256": canonical_sha256(ordered_ids),
        "row_count": len(rows),
    }
    if body["percentile_universe"] != expected_universe:
        _fail("reopened source percentile universe differs")

    target_replay = dict(_mapping(
        body["target_spine_replay"], label="reopened target-spine replay"
    ))
    _validate_self_hash(
        target_replay,
        field="target_spine_sha256",
        label="reopened target-spine replay",
    )
    if (
        target_replay.get("schema_version")
        != "corpus-r6-target-spine-replay/v1"
        or target_replay.get("population_authority")
        != "accepted-player-catalog"
        or target_replay.get("eligible_player_count") != len(rows)
    ):
        _fail("reopened target-spine replay policy differs")
    component_replay = dict(_mapping(
        body["component_value_replay"], label="reopened component replay"
    ))
    _validate_self_hash(
        component_replay,
        field="component_value_replay_sha256",
        label="reopened component replay",
    )
    deletion_proof = dict(_mapping(
        component_replay.get("target_week_deletion_proof"),
        label="reopened target-week deletion proof",
    ))
    _exact_keys(
        deletion_proof,
        _TARGET_DELETION_PROOF_FIELDS,
        label="reopened target-week deletion proof",
    )
    _validate_self_hash(
        deletion_proof,
        field="target_week_deletion_proof_sha256",
        label="reopened target-week deletion proof",
    )
    reduction_output = _mapping(
        deletion_proof["reduction_output"],
        label="reopened target-week deletion output",
    )
    probe_count = deletion_proof["probe_row_count"]
    for field in (
        "probe_rows_sha256",
        "full_input_sha256",
        "deleted_input_sha256",
        "full_reduction_sha256",
        "deleted_reduction_sha256",
    ):
        _digest(deletion_proof[field], label=f"deletion proof {field}")
    if (
        deletion_proof["schema_version"]
        != "corpus-r6-target-week-deletion-proof/v1"
        or deletion_proof["probe_source_systems"]
        != list(TARGET_WEEK_PARTICIPATION_SYSTEMS)
        or type(probe_count) is not int
        or isinstance(probe_count, bool)
        or probe_count != len(rows) * len(TARGET_WEEK_PARTICIPATION_SYSTEMS)
        or deletion_proof["full_input_sha256"]
        == deletion_proof["deleted_input_sha256"]
        or deletion_proof["full_reduction_sha256"]
        != canonical_sha256(reduction_output)
        or deletion_proof["full_reduction_sha256"]
        != deletion_proof["deleted_reduction_sha256"]
        or reduction_output.get("population_rows_sha256")
        != canonical_sha256(eligible_rows)
        or reduction_output.get("percentile_rows_sha256")
        != canonical_sha256(rows)
        or reduction_output.get("component_source_rows_sha256")
        != component_replay.get("source_extract_rows_sha256")
        or reduction_output.get(
            "retained_target_week_participation_rows_sha256"
        ) != canonical_sha256([])
        or deletion_proof["target_week_participation_universe_used"] is not False
        or deletion_proof["target_week_deletion_invariant"] is not True
        or component_replay.get("target_week_participation_universe_used")
        is not False
        or component_replay.get("target_week_deletion_invariant") is not True
        or component_replay.get("full_season_same_target_year_used") is not False
        or component_replay.get("normalized_rows_sha256")
        != canonical_sha256(rows)
        or component_replay.get("target_spine_sha256")
        != target_replay["target_spine_sha256"]
    ):
        _fail("reopened target-week deletion/component replay differs")
    return {
        **body,
        "slate": slate,
        "lock_time_utc": lock,
        "created_at_utc": created,
        "source_export_identity": source_identity,
        "query_receipt_identity": receipt_identity,
        "player_catalog_identity": catalog_identity,
        "rows": rows,
        "query_snapshot_at_utc": query_snapshot,
        "maximum_source_event_time_utc": maximum_event,
        "maximum_observed_at_utc": maximum_observed,
    }


def reopen_matchup_source_snapshot(
    *,
    source_export_identity: Mapping[str, object],
    query_receipt_identity: Mapping[str, object],
    player_catalog_identity: Mapping[str, object],
    read_exact: Callable[[Mapping[str, object]], bytes],
    expected_slate: Mapping[str, object],
    required_evidence_class: str,
) -> dict[str, object]:
    """Exact-read, cross-bind, and normalize one corrected source snapshot."""
    if required_evidence_class not in EVIDENCE_CLASSES:
        _fail("required evidence class is not registered")
    source_identity = normalize_object_identity(
        source_export_identity, label="source export"
    )
    receipt_identity = normalize_object_identity(
        query_receipt_identity, label="query receipt"
    )
    catalog_identity = normalize_object_identity(
        player_catalog_identity, label="player catalog"
    )
    normalized_expected_slate = _normalize_slate(
        expected_slate, label="expected slate"
    )
    catalog_raw = _read_exact(
        read_exact, catalog_identity, label="player catalog"
    )
    source_raw = _read_exact(
        read_exact, source_identity, label="matchup source export"
    )
    source = _validate_source_export(
        source_raw,
        identity=source_identity,
        catalog_raw=catalog_raw,
        catalog_identity=catalog_identity,
    )
    if source["slate"] != normalized_expected_slate:
        _fail("source export differs from the expected slate")
    receipt_raw = _read_exact(
        read_exact, receipt_identity, label="matchup query receipt"
    )
    receipt = _validate_query_receipt(
        receipt_raw,
        identity=receipt_identity,
        source_export=source,
        source_export_identity=source_identity,
        player_catalog_identity=catalog_identity,
    )
    evidence_class = str(receipt["evidence_class"])
    if _EVIDENCE_RANK[evidence_class] < _EVIDENCE_RANK[required_evidence_class]:
        _fail("matchup source evidence class is below the required minimum")
    reopened = {
        "schema_version": REOPENED_SOURCE_SCHEMA,
        "slate": source["slate"],
        "lock_time_utc": source["lock_time_utc"],
        "created_at_utc": source["created_at_utc"],
        "evidence_class": evidence_class,
        "source_export_identity": source_identity,
        "query_receipt_identity": receipt_identity,
        "player_catalog_identity": catalog_identity,
        "family_definition_identities": source[
            "family_definition_identities"
        ],
        "target_spine_replay": source["target_spine_replay"],
        "component_value_replay": source["component_value_replay"],
        "percentile_universe": source["percentile_universe"],
        "source_extracts": source["source_extracts"],
        "eligible_player_count": source["eligible_player_count"],
        "eligible_players_sha256": source["eligible_players_sha256"],
        "rows": source["rows"],
        "rows_sha256": source["rows_sha256"],
        "query_snapshot_at_utc": receipt["query_snapshot_at_utc"],
        "maximum_source_event_time_utc": receipt[
            "maximum_source_event_time_utc"
        ],
        "maximum_observed_at_utc": receipt["maximum_observed_at_utc"],
        "full_season_same_target_year_used": source[
            "component_value_replay"
        ]["full_season_same_target_year_used"],
        "target_week_participation_universe_used": source[
            "component_value_replay"
        ]["target_week_participation_universe_used"],
        "qb_depth_unknown_policy": QB_DEPTH_UNKNOWN_POLICY,
        "authoritative_for_mechanics": True,
        "authoritative_pit": receipt["authoritative_pit"],
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "fill_authority": False,
        "retrieval_authority": False,
        "promotion_authority": False,
        "production_policy_authority": False,
    }
    return validate_reopened_matchup_source_snapshot(reopened)


__all__ = [
    "CorpusR6MatchupSourceV1Error",
    "EVIDENCE_CLASSES",
    "EVIDENCE_CONTEMPORANEOUS",
    "EVIDENCE_NON_PIT",
    "EVIDENCE_RETROSPECTIVE",
    "FAMILY_DEFINITION_SCHEMA",
    "INFRASTRUCTURE_SOURCE_ROLES",
    "PLAYER_CATALOG_SCHEMA",
    "QB_DEPTH_SOURCE_ROLE",
    "QB_DEPTH_UNKNOWN_POLICY",
    "QUERY_RECEIPT_SCHEMA",
    "RENDERED_SQL_TEMPLATE_SHA256",
    "REOPENED_SOURCE_SCHEMA",
    "SCHEDULE_SOURCE_ROLE",
    "SOURCE_EXPORT_SCHEMA",
    "SOURCE_ROLE_SCHEMA",
    "TARGET_WEEK_PARTICIPATION_SYSTEMS",
    "build_source_role_schema_v1",
    "build_rendered_sql_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "capture_matchup_source_v1",
    "infrastructure_source_role_schemas_v1",
    "normalize_object_identity",
    "reopen_matchup_source_snapshot",
    "validate_reopened_matchup_source_snapshot",
]
