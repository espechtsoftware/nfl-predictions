"""Append-only strategy-registry projection for corpus research.

Every scientific/configuration object is fetched by exact GCS identity and
remains authoritative there.  Neo4j receives compact, immutable entities and
relationships only.  In particular, world matrices are represented only by
``CorpusArtifactPointer`` identities, and an ``ActiveStrategyPointer`` is a
versioned research pointer backed by a reviewed promotion receipt; it never
mutates application configuration or licenses automatic promotion.

The traversable ``Lineup`` rows are a bounded evidence view, not the corpus
authority or a substitute for bulk lineup/matrix artifacts in GCS.

The registry namespace is intentionally distinct from retrieval and
parametric evidence.  Dedicated deployment/load manifest v2 authorizes it
while reserving both corpus-population and realized-outcome namespaces empty.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import math
import re
from typing import Final

from nfl_dfs.research.corpus_neo4j_transport import (
    CorpusNeo4jTransportError,
    ExactObjectStore,
    ObjectIdentity,
    object_identity,
)
from nfl_dfs.research.corpus_retrieval_neo4j import (
    CorpusRetrievalNeo4jError,
    Neo4jLoadPlan,
    _relationship,
    append_load_plan,
    canonical_json_bytes,
    canonical_sha256,
    parse_canonical_json_bytes,
)


REGISTRY_NAMESPACE: Final = "corpus-strategy-registry"
RELEASE_SCHEMA: Final = "corpus-strategy-registry-release/v2"
FILL_PRESET_SCHEMA: Final = "corpus-fill-preset/v2"
RETRIEVAL_PRESET_SCHEMA: Final = "corpus-retrieval-preset/v2"
SNAPSHOT_SCHEMA: Final = "corpus-registry-snapshot/v1"
STRUCTURE_SCHEMA: Final = "corpus-slate-structure/v1"
EXPERIMENT_SCHEMA: Final = "corpus-experiment-run/v2"
METRIC_SET_SCHEMA: Final = "corpus-experiment-metric-set/v2"
EFFECTIVE_PARAMETERS_SCHEMA: Final = "corpus-experiment-effective-parameters/v1"
PRE_EXECUTION_GATE_SCHEMA: Final = "corpus-experiment-pre-execution-gate/v1"
EVIDENCE_BINDING_SCHEMA: Final = "corpus-experiment-evidence-binding/v1"
RETROSPECTIVE_REGISTRATION_SCHEMA: Final = (
    "corpus-experiment-retrospective-registration/v1"
)
RETROSPECTIVE_EFFECTIVE_PARAMETERS_SCHEMA: Final = (
    "corpus-experiment-retrospective-effective-parameters/v1"
)
RETROSPECTIVE_EVIDENCE_BINDING_SCHEMA: Final = (
    "corpus-experiment-retrospective-evidence-binding/v1"
)
PROMOTION_SCHEMA: Final = "corpus-promotion-decision/v1"
ACTIVE_POINTER_SCHEMA: Final = "corpus-active-strategy-pointer/v1"
WINNER_AUTHORITY_SCHEMA: Final = "corpus-winner-import-authority/v1"
WINNER_EVIDENCE_SCHEMA: Final = "corpus-winner-evidence/v1"
PROJECTION_RECEIPT_SCHEMA: Final = "corpus-strategy-registry-projection/v2"
QUERY_RECEIPT_SCHEMA: Final = "corpus-strategy-registry-query-receipt/v2"

_SHA = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE = re.compile(r"^[^\s@]+@sha256:[0-9a-f]{64}$")
_BUILD = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"
)
_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{0,127}$")
_SLATE = re.compile(
    r"^[0-9]{4}-w(?:0[1-9]|[1-9][0-9]*)(?:-[a-z0-9][a-z0-9-]*)?$"
)

_MAX_TYPED_PARAMETERS: Final = 256
_MAX_ARTIFACT_POINTERS: Final = 128
_MAX_GAMES_PER_SLATE: Final = 32
_MAX_PLAYERS_PER_SLATE: Final = 1_000
_MAX_LINEUPS_PER_SLATE: Final = 10_000
_MAX_METRICS_PER_EXPERIMENT: Final = 256
_MAX_REGISTRY_OBJECTS: Final = 100_000

_RELEASE_KEYS = {
    "schema_version", "publication_mode", "registry_id", "output_prefix",
    "fill_presets", "retrieval_presets", "corpus_snapshots",
    "slate_structures", "experiment_runs", "metric_sets",
    "promotion_decisions", "active_strategy_pointers",
    "winner_import_requested", "winner_import_authority", "winner_evidence",
    "automatic_promotion", "application_config_mutation",
    "production_policy_authority", "gcs_remains_authoritative",
    "world_matrices_stored_in_graph", "raw_outcomes_stored_in_graph",
    "uses_realized_outcomes", "historical_outcome_read_authority",
    "outcome_namespace_read", "outcome_columns_read", "created_at_utc",
    "registry_release_sha256",
}

_EXPERIMENT_AUTHORITY_FIELDS: Final = (
    "pre_execution_gate",
    "accepted_execution",
    "accepted_result",
    "independent_verification",
    "effective_parameters",
    "selection_evidence",
    "metric_computation",
)
_EVIDENCE_ROLES: Final = (
    "accepted-execution",
    "accepted-result",
    "independent-verification",
    "selection-evidence",
    "metric-computation",
)


class CorpusStrategyRegistryError(RuntimeError):
    """The registry evidence or projection violates its frozen law."""


@dataclass(frozen=True, slots=True)
class StrategyRegistryBundle:
    plan: Neo4jLoadPlan
    release: dict[str, object]
    release_identity: ObjectIdentity
    winner_imported: bool
    winner_count: int


@dataclass(frozen=True, slots=True)
class ReadOnlyRegistryQuery:
    name: str
    cypher: str


QueryRunner = Callable[
    [str, str, Mapping[str, object]], Sequence[Mapping[str, object]]
]


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusStrategyRegistryError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if not isinstance(value, list):
        raise CorpusStrategyRegistryError(f"{label} must be an array")
    return value


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise CorpusStrategyRegistryError(f"{label} must be a nonempty string")
    return value


def _exact_keys(
    value: Mapping[str, object], expected: set[str], *, label: str,
) -> None:
    if set(value) != expected:
        raise CorpusStrategyRegistryError(f"{label} fields differ")


def _identifier(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if _ID.fullmatch(retained) is None:
        raise CorpusStrategyRegistryError(f"{label} is not canonical")
    return retained


def _timestamp(value: object, *, label: str) -> str:
    retained = _string(value, label=label)
    if _UTC.fullmatch(retained) is None:
        raise CorpusStrategyRegistryError(f"{label} is not second-precision UTC")
    return retained


def _identity_dict(value: object, *, label: str) -> dict[str, object]:
    try:
        return object_identity(value, label=label).as_dict()
    except CorpusNeo4jTransportError as exc:
        raise CorpusStrategyRegistryError(f"{label} differs") from exc


def _identity_key(value: object, *, label: str = "object identity") -> tuple[object, ...]:
    item = _identity_dict(value, label=label)
    return tuple(item[key] for key in ("uri", "generation", "sha256", "bytes"))


def _bind_raw(raw: bytes, identity: ObjectIdentity, *, label: str) -> bytes:
    if (
        type(raw) is not bytes
        or len(raw) != identity.bytes
        or sha256(raw).hexdigest() != identity.sha256
    ):
        raise CorpusStrategyRegistryError(f"{label} content identity differs")
    return raw


def _read_json(
    storage: ExactObjectStore,
    value: object,
    *,
    label: str,
) -> tuple[ObjectIdentity, dict[str, object]]:
    try:
        identity = object_identity(value, label=f"{label} identity")
        raw = _bind_raw(storage.read_exact(identity), identity, label=label)
    except CorpusNeo4jTransportError as exc:
        raise CorpusStrategyRegistryError(f"{label} exact read differs") from exc
    try:
        parsed = parse_canonical_json_bytes(raw, label=label)
    except CorpusRetrievalNeo4jError as exc:
        raise CorpusStrategyRegistryError(f"{label} is not canonical JSON") from exc
    return identity, dict(_mapping(parsed, label=label))


def _self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    digest = value.get(field)
    if not isinstance(digest, str) or _SHA.fullmatch(digest) is None:
        raise CorpusStrategyRegistryError(f"{label}.{field} differs")
    body = {key: item for key, item in value.items() if key != field}
    if canonical_sha256(body) != digest:
        raise CorpusStrategyRegistryError(f"{label} self-hash differs")
    return digest


def _require_outcome_firewall(
    value: Mapping[str, object], *, label: str,
) -> None:
    if (
        value.get("uses_realized_outcomes") is not False
        or value.get("historical_outcome_read_authority") is not False
        or value.get("outcome_namespace_read") is not False
        or value.get("outcome_columns_read") != []
    ):
        raise CorpusStrategyRegistryError(f"{label} outcome firewall differs")


def _typed_parameters(value: object, *, label: str) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    names: list[str] = []
    raw_parameters = _sequence(value, label=label)
    if not 0 <= len(raw_parameters) <= _MAX_TYPED_PARAMETERS:
        raise CorpusStrategyRegistryError(f"{label} count differs")
    for ordinal, raw in enumerate(raw_parameters):
        row = dict(_mapping(raw, label=f"{label}[{ordinal}]"))
        _exact_keys(row, {"name", "type", "value"}, label=f"{label}[{ordinal}]")
        name = _identifier(row["name"], label=f"{label}[{ordinal}].name")
        parameter_type = row.get("type")
        parameter_value = row.get("value")
        accepted = (
            (parameter_type == "boolean" and type(parameter_value) is bool)
            or (
                parameter_type == "integer"
                and type(parameter_value) is int
                and not isinstance(parameter_value, bool)
            )
            or (
                parameter_type == "number"
                and type(parameter_value) in {int, float}
                and not isinstance(parameter_value, bool)
                and math.isfinite(float(parameter_value))
            )
            or (parameter_type == "string" and isinstance(parameter_value, str))
            or (
                parameter_type == "json"
                and _is_bounded_json_parameter(parameter_value)
            )
        )
        if not accepted:
            raise CorpusStrategyRegistryError(
                f"{label}[{ordinal}] typed value differs"
            )
        names.append(name)
        rows.append(row)
    if names != sorted(set(names)):
        raise CorpusStrategyRegistryError(f"{label} names must be sorted and unique")
    return rows


def _is_bounded_json_parameter(value: object, *, depth: int = 0) -> bool:
    if depth > 8:
        return False
    if value is None or type(value) in {bool, int, str}:
        return True
    if type(value) is float:
        return math.isfinite(value)
    if isinstance(value, list):
        return len(value) <= 1_000 and all(
            _is_bounded_json_parameter(row, depth=depth + 1) for row in value
        )
    if isinstance(value, Mapping):
        return len(value) <= 1_000 and all(
            isinstance(key, str)
            and bool(key)
            and _is_bounded_json_parameter(row, depth=depth + 1)
            for key, row in value.items()
        )
    return False


def _validate_preset(
    value: Mapping[str, object], *, kind: str,
) -> dict[str, object]:
    schema, hash_field = (
        (FILL_PRESET_SCHEMA, "fill_preset_sha256")
        if kind == "fill" else
        (RETRIEVAL_PRESET_SCHEMA, "retrieval_preset_sha256")
    )
    label = f"{kind} preset"
    item = dict(value)
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "preset_id", "version",
            "parameters", "description", "deprecated", "research_only",
            "production_policy_authority", hash_field,
        },
        label=label,
    )
    if (
        item["schema_version"] != schema
        or item["publication_mode"] != "create_once"
        or type(item["version"]) is not int
        or item["version"] < 1
        or not isinstance(item["description"], str)
        or type(item["deprecated"]) is not bool
        or item["research_only"] is not True
        or item["production_policy_authority"] is not False
    ):
        raise CorpusStrategyRegistryError(f"{label} law differs")
    _identifier(item["preset_id"], label=f"{label} ID")
    _typed_parameters(item["parameters"], label=f"{label} parameters")
    _self_hash(item, field=hash_field, label=label)
    return item


def _validate_artifact_pointer(value: object, *, label: str) -> dict[str, object]:
    item = dict(_mapping(value, label=label))
    _exact_keys(
        item,
        {
            "role", "format", "object_identity", "contains_world_matrix",
            "contains_raw_outcomes",
        },
        label=label,
    )
    _identifier(item["role"], label=f"{label}.role")
    _string(item["format"], label=f"{label}.format")
    item["object_identity"] = _identity_dict(
        item["object_identity"], label=f"{label} object"
    )
    if (
        type(item["contains_world_matrix"]) is not bool
        or item["contains_raw_outcomes"] is not False
    ):
        raise CorpusStrategyRegistryError(f"{label} storage law differs")
    return item


def _validate_snapshot(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "snapshot_id", "task_index",
            "slate_id", "season", "week", "source_snapshot_manifest",
            "producing_fill_preset", "slate_structure", "artifact_pointers",
            "lineup_ids", "created_at_utc", "corpus_snapshot_sha256",
        },
        label="corpus snapshot",
    )
    if (
        item["schema_version"] != SNAPSHOT_SCHEMA
        or item["publication_mode"] != "create_once"
        or type(item["task_index"]) is not int
        or not 0 <= item["task_index"] < 54
        or type(item["season"]) is not int
        or type(item["week"]) is not int
        or item["week"] < 1
    ):
        raise CorpusStrategyRegistryError("corpus snapshot law differs")
    _identifier(item["snapshot_id"], label="snapshot ID")
    slate_id = _string(item["slate_id"], label="snapshot slate ID")
    if _SLATE.fullmatch(slate_id) is None:
        raise CorpusStrategyRegistryError("snapshot slate ID differs")
    item["source_snapshot_manifest"] = _identity_dict(
        item["source_snapshot_manifest"], label="source snapshot manifest"
    )
    item["producing_fill_preset"] = _identity_dict(
        item["producing_fill_preset"], label="snapshot producing fill preset"
    )
    item["slate_structure"] = _identity_dict(
        item["slate_structure"], label="snapshot slate structure"
    )
    raw_pointers = _sequence(item["artifact_pointers"], label="artifact pointers")
    if not 1 <= len(raw_pointers) <= _MAX_ARTIFACT_POINTERS:
        raise CorpusStrategyRegistryError("snapshot artifact pointer count differs")
    pointers = [
        _validate_artifact_pointer(raw, label=f"artifact pointer[{ordinal}]")
        for ordinal, raw in enumerate(raw_pointers)
    ]
    pointer_keys = [
        _identity_key(row["object_identity"], label="matrix artifact identity")
        for row in pointers
    ]
    pointer_roles = [str(row["role"]) for row in pointers]
    if (
        not pointers
        or not any(row["contains_world_matrix"] is True for row in pointers)
        or len(pointer_keys) != len(set(pointer_keys))
        or pointer_roles != sorted(set(pointer_roles))
    ):
        raise CorpusStrategyRegistryError("snapshot artifact pointer coverage differs")
    item["artifact_pointers"] = pointers
    lineup_ids = [
        _identifier(raw, label=f"snapshot lineup ID[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(item["lineup_ids"], label="snapshot lineup IDs")
        )
    ]
    if (
        not 1 <= len(lineup_ids) <= _MAX_LINEUPS_PER_SLATE
        or lineup_ids != sorted(set(lineup_ids))
    ):
        raise CorpusStrategyRegistryError("snapshot lineup membership differs")
    item["lineup_ids"] = lineup_ids
    _timestamp(item["created_at_utc"], label="snapshot created timestamp")
    _self_hash(item, field="corpus_snapshot_sha256", label="corpus snapshot")
    return item


def _validate_structure(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "task_index",
            "slate_id", "games", "teams", "players", "lineups",
            "slate_structure_sha256",
        },
        label="slate structure",
    )
    if (
        item["schema_version"] != STRUCTURE_SCHEMA
        or item["publication_mode"] != "create_once"
        or type(item["task_index"]) is not int
        or not 0 <= item["task_index"] < 54
    ):
        raise CorpusStrategyRegistryError("slate structure law differs")
    slate_id = _string(item["slate_id"], label="structure slate ID")
    if _SLATE.fullmatch(slate_id) is None:
        raise CorpusStrategyRegistryError("structure slate ID differs")
    games: list[dict[str, object]] = []
    game_ids: set[str] = set()
    teams_expected: dict[str, tuple[str, str]] = {}
    raw_games = _sequence(item["games"], label="games")
    if not 1 <= len(raw_games) <= _MAX_GAMES_PER_SLATE:
        raise CorpusStrategyRegistryError("game count differs")
    for ordinal, raw in enumerate(raw_games):
        row = dict(_mapping(raw, label=f"game[{ordinal}]"))
        _exact_keys(row, {"game_id", "home_team", "away_team"}, label="game")
        game_id = _identifier(row["game_id"], label="game ID")
        home = _identifier(row["home_team"], label="home team")
        away = _identifier(row["away_team"], label="away team")
        if game_id in game_ids or home == away or home in teams_expected or away in teams_expected:
            raise CorpusStrategyRegistryError("game/team identity coverage differs")
        game_ids.add(game_id)
        teams_expected[home] = (game_id, away)
        teams_expected[away] = (game_id, home)
        games.append(row)
    teams: list[dict[str, object]] = []
    seen_teams: set[str] = set()
    raw_teams = _sequence(item["teams"], label="teams")
    if len(raw_teams) != 2 * len(raw_games):
        raise CorpusStrategyRegistryError("team count differs")
    for ordinal, raw in enumerate(raw_teams):
        row = dict(_mapping(raw, label=f"team[{ordinal}]"))
        _exact_keys(row, {"team", "game_id", "opponent"}, label="team")
        team = _identifier(row["team"], label="team")
        expected = teams_expected.get(team)
        if expected is None or (row["game_id"], row["opponent"]) != expected or team in seen_teams:
            raise CorpusStrategyRegistryError("team/game binding differs")
        seen_teams.add(team)
        teams.append(row)
    if not games or seen_teams != set(teams_expected):
        raise CorpusStrategyRegistryError("team coverage differs")
    players: list[dict[str, object]] = []
    player_ids: set[str] = set()
    raw_players = _sequence(item["players"], label="players")
    if not 1 <= len(raw_players) <= _MAX_PLAYERS_PER_SLATE:
        raise CorpusStrategyRegistryError("player count differs")
    for ordinal, raw in enumerate(raw_players):
        row = dict(_mapping(raw, label=f"player[{ordinal}]"))
        _exact_keys(
            row, {"player_id", "display_name", "team", "positions"},
            label="player",
        )
        player_id = _identifier(row["player_id"], label="player ID")
        positions = list(_sequence(row["positions"], label="player positions"))
        if (
            player_id in player_ids
            or not isinstance(row["display_name"], str)
            or row["team"] not in seen_teams
            or not positions
            or any(not isinstance(position, str) or not position for position in positions)
            or positions != sorted(set(positions))
        ):
            raise CorpusStrategyRegistryError("player slate binding differs")
        player_ids.add(player_id)
        players.append(row)
    lineups: list[dict[str, object]] = []
    lineup_ids: set[str] = set()
    raw_lineups = _sequence(item["lineups"], label="lineups")
    if not 1 <= len(raw_lineups) <= _MAX_LINEUPS_PER_SLATE:
        raise CorpusStrategyRegistryError("lineup count differs")
    for ordinal, raw in enumerate(raw_lineups):
        row = dict(_mapping(raw, label=f"lineup[{ordinal}]"))
        _exact_keys(
            row, {"lineup_id", "player_ids", "salary", "source"},
            label="lineup",
        )
        lineup_id = _identifier(row["lineup_id"], label="lineup ID")
        roster = list(_sequence(row["player_ids"], label="lineup player IDs"))
        if (
            lineup_id in lineup_ids
            or len(roster) != 9
            or len(set(roster)) != 9
            or not set(roster).issubset(player_ids)
            or type(row["salary"]) is not int
            or row["salary"] < 0
            or row["source"] not in {"corpus", "generated", "retrieved"}
        ):
            raise CorpusStrategyRegistryError("lineup roster binding differs")
        lineup_ids.add(lineup_id)
        lineups.append(row)
    item.update({"games": games, "teams": teams, "players": players, "lineups": lineups})
    _self_hash(item, field="slate_structure_sha256", label="slate structure")
    return item


def _validate_release_binding(value: object) -> dict[str, str]:
    item = dict(_mapping(value, label="exact experiment release"))
    _exact_keys(item, {"code_commit", "image", "build_id"}, label="exact release")
    if (
        _COMMIT.fullmatch(str(item.get("code_commit", ""))) is None
        or _IMAGE.fullmatch(str(item.get("image", ""))) is None
        or _BUILD.fullmatch(str(item.get("build_id", ""))) is None
    ):
        raise CorpusStrategyRegistryError("exact experiment release differs")
    return {key: str(item[key]) for key in ("code_commit", "image", "build_id")}


def _validate_effective_parameters(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    retrospective = (
        item.get("schema_version")
        == RETROSPECTIVE_EFFECTIVE_PARAMETERS_SCHEMA
    )
    extra_fields = (
        {"source_effective_policy", "derivation_mode"}
        if retrospective else set()
    )
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "experiment_id",
            "fill_preset", "retrieval_preset", "fill_parameters",
            "retrieval_parameters", "uses_realized_outcomes",
            "historical_outcome_read_authority", "outcome_namespace_read",
            "outcome_columns_read", "effective_parameters_sha256",
            *extra_fields,
        },
        label="effective parameters",
    )
    if (
        item["schema_version"] not in {
            EFFECTIVE_PARAMETERS_SCHEMA,
            RETROSPECTIVE_EFFECTIVE_PARAMETERS_SCHEMA,
        }
        or item["publication_mode"] != "create_once"
        or (
            retrospective
            and item.get("derivation_mode")
            != "retrospective-pointer-binding"
        )
    ):
        raise CorpusStrategyRegistryError("effective parameters law differs")
    _identifier(item["experiment_id"], label="effective parameters experiment ID")
    item["fill_preset"] = _identity_dict(
        item["fill_preset"], label="effective parameters fill preset"
    )
    item["retrieval_preset"] = _identity_dict(
        item["retrieval_preset"], label="effective parameters retrieval preset"
    )
    item["fill_parameters"] = _typed_parameters(
        item["fill_parameters"], label="effective fill parameters"
    )
    item["retrieval_parameters"] = _typed_parameters(
        item["retrieval_parameters"], label="effective retrieval parameters"
    )
    if retrospective:
        item["source_effective_policy"] = _identity_dict(
            item["source_effective_policy"],
            label="source runtime effective policy",
        )
    _require_outcome_firewall(item, label="effective parameters")
    _self_hash(
        item, field="effective_parameters_sha256", label="effective parameters"
    )
    return item


def _validate_pre_execution_gate(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    retrospective = (
        item.get("schema_version") == RETROSPECTIVE_REGISTRATION_SCHEMA
    )
    if retrospective:
        expected_fields = {
            "schema_version", "publication_mode", "gate_id", "experiment_id",
            "task_index", "slate_id", "fill_preset", "retrieval_preset",
            "corpus_snapshot", "matrix_artifacts", "effective_parameters",
            "exact_release", "derivation_manifest", "batch_manifest",
            "task_acceptance", "task_result", "science_terminal",
            "independent_verification", "variant_result", "effective_policy",
            "task_sha256", "parameter_set_sha256",
            "registered_before_execution", "batch_law_frozen_before_execution",
            "retrospective_binding", "uses_realized_outcomes",
            "historical_outcome_read_authority", "outcome_namespace_read",
            "outcome_columns_read", "created_at_utc",
            "retrospective_registration_sha256",
        }
    else:
        expected_fields = {
            "schema_version", "publication_mode", "gate_id", "experiment_id",
            "task_index", "slate_id", "fill_preset", "retrieval_preset",
            "corpus_snapshot", "matrix_artifacts", "effective_parameters",
            "exact_release", "registered_before_execution", "gate_passed",
            "uses_realized_outcomes", "historical_outcome_read_authority",
            "outcome_namespace_read", "outcome_columns_read",
            "created_at_utc", "pre_execution_gate_sha256",
        }
    _exact_keys(
        item, expected_fields,
        label="pre-execution gate",
    )
    if (
        item["schema_version"] not in {
            PRE_EXECUTION_GATE_SCHEMA, RETROSPECTIVE_REGISTRATION_SCHEMA,
        }
        or item["publication_mode"] != "create_once"
        or type(item["task_index"]) is not int
        or not 0 <= item["task_index"] < 54
        or (
            not retrospective
            and (
                item["registered_before_execution"] is not True
                or item["gate_passed"] is not True
            )
        )
        or (
            retrospective
            and (
                item["registered_before_execution"] is not False
                or item["batch_law_frozen_before_execution"] is not True
                or item["retrospective_binding"] is not True
            )
        )
    ):
        raise CorpusStrategyRegistryError("pre-execution gate law differs")
    _identifier(item["gate_id"], label="pre-execution gate ID")
    _identifier(item["experiment_id"], label="pre-execution gate experiment ID")
    if _SLATE.fullmatch(str(item["slate_id"])) is None:
        raise CorpusStrategyRegistryError("pre-execution gate slate differs")
    for field in (
        "fill_preset", "retrieval_preset", "corpus_snapshot",
        "effective_parameters",
    ):
        item[field] = _identity_dict(item[field], label=f"pre-execution gate {field}")
    item["exact_release"] = _validate_release_binding(item["exact_release"])
    if retrospective:
        for field in (
            "derivation_manifest", "batch_manifest", "task_acceptance",
            "task_result", "science_terminal", "independent_verification",
            "variant_result", "effective_policy",
        ):
            item[field] = _identity_dict(
                item[field], label=f"retrospective registration {field}"
            )
        if (
            not isinstance(item["task_sha256"], str)
            or _SHA.fullmatch(item["task_sha256"]) is None
            or not isinstance(item["parameter_set_sha256"], str)
            or _SHA.fullmatch(item["parameter_set_sha256"]) is None
        ):
            raise CorpusStrategyRegistryError(
                "retrospective registration source hashes differ"
            )
    matrices = [
        _identity_dict(raw, label=f"pre-execution gate matrix[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(item["matrix_artifacts"], label="pre-execution gate matrices")
        )
    ]
    matrix_keys = [_identity_key(row) for row in matrices]
    if not matrices or matrix_keys != sorted(set(matrix_keys)):
        raise CorpusStrategyRegistryError("pre-execution gate matrix coverage differs")
    item["matrix_artifacts"] = matrices
    _require_outcome_firewall(item, label="pre-execution gate")
    _timestamp(item["created_at_utc"], label="pre-execution gate timestamp")
    _self_hash(
        item,
        field=(
            "retrospective_registration_sha256"
            if retrospective else "pre_execution_gate_sha256"
        ),
        label="pre-execution gate",
    )
    return item


def _validate_evidence_binding(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    retrospective = (
        item.get("schema_version") == RETROSPECTIVE_EVIDENCE_BINDING_SCHEMA
    )
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "evidence_id",
            "experiment_id", "evidence_role", "task_index", "slate_id",
            "exact_release", "dependencies", "accepted", "complete",
            "computed_metrics_sha256",
            "uses_realized_outcomes", "historical_outcome_read_authority",
            "outcome_namespace_read", "outcome_columns_read",
            "created_at_utc", "evidence_binding_sha256",
            *({"derivation_mode"} if retrospective else set()),
        },
        label="experiment evidence binding",
    )
    if (
        item["schema_version"] not in {
            EVIDENCE_BINDING_SCHEMA, RETROSPECTIVE_EVIDENCE_BINDING_SCHEMA,
        }
        or item["publication_mode"] != "create_once"
        or item["evidence_role"] not in _EVIDENCE_ROLES
        or type(item["task_index"]) is not int
        or not 0 <= item["task_index"] < 54
        or item["accepted"] is not True
        or item["complete"] is not True
        or (
            retrospective
            and item.get("derivation_mode")
            != "retrospective-pointer-binding"
        )
    ):
        raise CorpusStrategyRegistryError("experiment evidence law differs")
    _identifier(item["evidence_id"], label="experiment evidence ID")
    _identifier(item["experiment_id"], label="experiment evidence experiment ID")
    if _SLATE.fullmatch(str(item["slate_id"])) is None:
        raise CorpusStrategyRegistryError("experiment evidence slate differs")
    item["exact_release"] = _validate_release_binding(item["exact_release"])
    dependencies = [
        _identity_dict(raw, label=f"experiment evidence dependency[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(item["dependencies"], label="experiment evidence dependencies")
        )
    ]
    dependency_keys = [_identity_key(row) for row in dependencies]
    if not dependencies or dependency_keys != sorted(set(dependency_keys)):
        raise CorpusStrategyRegistryError("experiment evidence dependencies differ")
    item["dependencies"] = dependencies
    metrics_digest = item["computed_metrics_sha256"]
    if (
        item["evidence_role"] == "metric-computation"
        and (
            not isinstance(metrics_digest, str)
            or _SHA.fullmatch(metrics_digest) is None
        )
    ) or (
        item["evidence_role"] != "metric-computation"
        and metrics_digest is not None
    ):
        raise CorpusStrategyRegistryError("computed metric evidence binding differs")
    _require_outcome_firewall(item, label="experiment evidence")
    _timestamp(item["created_at_utc"], label="experiment evidence timestamp")
    _self_hash(
        item, field="evidence_binding_sha256", label="experiment evidence binding"
    )
    return item


def _validate_experiment(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "experiment_id", "task_index",
            "slate_id", "fill_preset", "retrieval_preset", "corpus_snapshot",
            "exact_release", "matrix_artifacts", "metric_set", "status",
            *_EXPERIMENT_AUTHORITY_FIELDS,
            "uses_realized_outcomes", "historical_outcome_read_authority",
            "outcome_namespace_read", "outcome_columns_read",
            "automatic_promotion", "application_config_mutation",
            "production_policy_authority", "experiment_run_sha256",
        },
        label="experiment run",
    )
    if (
        item["schema_version"] != EXPERIMENT_SCHEMA
        or item["publication_mode"] != "create_once"
        or type(item["task_index"]) is not int
        or not 0 <= item["task_index"] < 54
        or item["status"] != "complete-accepted"
        or item["automatic_promotion"] is not False
        or item["application_config_mutation"] is not False
        or item["production_policy_authority"] is not False
    ):
        raise CorpusStrategyRegistryError("experiment run law differs")
    _identifier(item["experiment_id"], label="experiment ID")
    if _SLATE.fullmatch(str(item["slate_id"])) is None:
        raise CorpusStrategyRegistryError("experiment slate differs")
    for field in ("fill_preset", "retrieval_preset", "corpus_snapshot", "metric_set"):
        item[field] = _identity_dict(item[field], label=f"experiment {field}")
    for field in _EXPERIMENT_AUTHORITY_FIELDS:
        item[field] = _identity_dict(item[field], label=f"experiment {field}")
    item["exact_release"] = _validate_release_binding(item["exact_release"])
    artifacts = [
        _identity_dict(raw, label=f"experiment matrix artifact[{ordinal}]")
        for ordinal, raw in enumerate(
            _sequence(item["matrix_artifacts"], label="experiment matrix artifacts")
        )
    ]
    keys = [_identity_key(row) for row in artifacts]
    if not artifacts or keys != sorted(set(keys)):
        raise CorpusStrategyRegistryError("experiment matrix artifact coverage differs")
    item["matrix_artifacts"] = artifacts
    _require_outcome_firewall(item, label="experiment run")
    _self_hash(item, field="experiment_run_sha256", label="experiment run")
    return item


def _metric_row(value: object, *, ordinal: int) -> dict[str, object]:
    row = dict(_mapping(value, label=f"metric[{ordinal}]"))
    _exact_keys(
        row,
        {
            "metric_id", "name", "value", "unit", "direction", "scope",
            "sample_count", "paired_key", "baseline_experiment_run",
        },
        label=f"metric[{ordinal}]",
    )
    numeric = row.get("value")
    if (
        type(numeric) not in {int, float}
        or isinstance(numeric, bool)
        or not math.isfinite(float(numeric))
        or type(row.get("sample_count")) is not int
        or row["sample_count"] < 1
        or row.get("direction") not in {"maximize", "minimize", "descriptive"}
        or row.get("scope") not in {
            "discovery", "heldout", "all-worlds-descriptive",
        }
    ):
        raise CorpusStrategyRegistryError(f"metric[{ordinal}] value/scope differs")
    _identifier(row["metric_id"], label="metric ID")
    _identifier(row["name"], label="metric name")
    _string(row["unit"], label="metric unit")
    _identifier(row["paired_key"], label="metric paired key")
    if row["baseline_experiment_run"] is not None:
        row["baseline_experiment_run"] = _identity_dict(
            row["baseline_experiment_run"], label="metric baseline experiment"
        )
    return row


def _validate_metric_set(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "experiment_id", "metrics",
            "paired_design", "heldout_design", "metric_set_sha256",
            *_EXPERIMENT_AUTHORITY_FIELDS,
            "uses_realized_outcomes", "historical_outcome_read_authority",
            "outcome_namespace_read", "outcome_columns_read",
        },
        label="metric set",
    )
    # The experiment points to this exact metric-set identity.  The reverse
    # binding is therefore a stable logical ID, avoiding an impossible pair of
    # mutually content-addressed JSON objects.
    _identifier(item["experiment_id"], label="metric experiment ID")
    for field in _EXPERIMENT_AUTHORITY_FIELDS:
        item[field] = _identity_dict(item[field], label=f"metric set {field}")
    paired = dict(_mapping(item["paired_design"], label="paired design"))
    heldout = dict(_mapping(item["heldout_design"], label="heldout design"))
    _exact_keys(
        paired,
        {
            "required", "comparison_axis", "same_snapshot", "same_worlds",
            "paired_key",
        },
        label="paired design",
    )
    _exact_keys(
        heldout,
        {
            "heldout_split_registered", "selection_informed_by_heldout",
            *(
                {"selection_informed_by_evaluation_worlds"}
                if "selection_informed_by_evaluation_worlds" in heldout
                else set()
            ),
        },
        label="heldout design",
    )
    paired_key = _identifier(paired["paired_key"], label="paired design key")
    comparison_axis = paired.get("comparison_axis")
    required = paired.get("required")
    heldout_registered = heldout == {
        "heldout_split_registered": True,
        "selection_informed_by_heldout": False,
    }
    all_worlds_descriptive = heldout == {
        "heldout_split_registered": False,
        "selection_informed_by_heldout": False,
        "selection_informed_by_evaluation_worlds": True,
    }
    if (
        item["schema_version"] != METRIC_SET_SCHEMA
        or item["publication_mode"] != "create_once"
        or type(required) is not bool
        or comparison_axis not in {"none", "fill", "retrieval"}
        or type(paired.get("same_snapshot")) is not bool
        or paired.get("same_worlds") is not True
        or (
            required is False
            and (
                comparison_axis != "none"
                or paired.get("same_snapshot") is not False
            )
        )
        or (
            required is True
            and comparison_axis == "retrieval"
            and paired.get("same_snapshot") is not True
        )
        or (
            required is True
            and comparison_axis == "fill"
            and paired.get("same_snapshot") is not False
        )
        or (required is True and comparison_axis == "none")
        or not (heldout_registered or all_worlds_descriptive)
    ):
        raise CorpusStrategyRegistryError("paired/heldout metric law differs")
    raw_metrics = _sequence(item["metrics"], label="metrics")
    if not 2 <= len(raw_metrics) <= _MAX_METRICS_PER_EXPERIMENT:
        raise CorpusStrategyRegistryError("metric count differs")
    metrics = [
        _metric_row(raw, ordinal=ordinal)
        for ordinal, raw in enumerate(raw_metrics)
    ]
    ids = [str(row["metric_id"]) for row in metrics]
    scopes = {str(row["scope"]) for row in metrics}
    if (
        not metrics
        or ids != sorted(set(ids))
        or any(row["paired_key"] != paired_key for row in metrics)
        or (
            heldout_registered
            and not {"discovery", "heldout"}.issubset(scopes)
        )
        or (
            all_worlds_descriptive
            and scopes != {"all-worlds-descriptive"}
        )
        or (
            required is True
            and any(row["baseline_experiment_run"] is None for row in metrics)
        )
        or (
            required is False
            and any(row["baseline_experiment_run"] is not None for row in metrics)
        )
    ):
        raise CorpusStrategyRegistryError("paired/heldout metric coverage differs")
    item.update({"paired_design": paired, "heldout_design": heldout, "metrics": metrics})
    _require_outcome_firewall(item, label="metric set")
    _self_hash(item, field="metric_set_sha256", label="metric set")
    return item


def _validate_promotion(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "decision_id", "version",
            "candidate_experiment", "incumbent_active_pointer", "metric_set",
            "registered_gates", "decision", "review", "automatic_promotion",
            "human_review_required", "application_config_mutation",
            "production_policy_authority", "promotion_decision_sha256",
        },
        label="promotion decision",
    )
    if (
        item["schema_version"] != PROMOTION_SCHEMA
        or item["publication_mode"] != "create_once"
        or type(item["version"]) is not int
        or item["version"] < 1
        or item["decision"] not in {"promote", "reject", "hold"}
        or item["automatic_promotion"] is not False
        or item["human_review_required"] is not True
        or item["application_config_mutation"] is not False
        or item["production_policy_authority"] is not False
    ):
        raise CorpusStrategyRegistryError("no-auto-promotion law differs")
    _identifier(item["decision_id"], label="promotion decision ID")
    item["candidate_experiment"] = _identity_dict(
        item["candidate_experiment"], label="promotion candidate experiment"
    )
    item["metric_set"] = _identity_dict(item["metric_set"], label="promotion metrics")
    if item["incumbent_active_pointer"] is not None:
        item["incumbent_active_pointer"] = _identity_dict(
            item["incumbent_active_pointer"], label="incumbent active pointer"
        )
    review = dict(_mapping(item["review"], label="promotion review"))
    _exact_keys(
        review, {"reviewer_id", "reviewed_at_utc", "independent_review"},
        label="promotion review",
    )
    _identifier(review["reviewer_id"], label="reviewer ID")
    _timestamp(review["reviewed_at_utc"], label="promotion review timestamp")
    if review["independent_review"] is not True:
        raise CorpusStrategyRegistryError("promotion review is not independent")
    gates: list[dict[str, object]] = []
    raw_gates = _sequence(item["registered_gates"], label="promotion gates")
    if not 1 <= len(raw_gates) <= _MAX_METRICS_PER_EXPERIMENT:
        raise CorpusStrategyRegistryError("promotion gate count differs")
    for ordinal, raw in enumerate(raw_gates):
        row = dict(_mapping(raw, label=f"promotion gate[{ordinal}]"))
        _exact_keys(
            row,
            {"metric_id", "scope", "operator", "threshold", "minimum_sample_count"},
            label="promotion gate",
        )
        if (
            row["scope"] not in {"discovery", "heldout", "all-worlds-descriptive"}
            or row["operator"] not in {">", ">=", "<", "<=", "=="}
            or type(row["threshold"]) not in {int, float}
            or isinstance(row["threshold"], bool)
            or not math.isfinite(float(row["threshold"]))
            or type(row["minimum_sample_count"]) is not int
            or row["minimum_sample_count"] < 1
        ):
            raise CorpusStrategyRegistryError("promotion gate differs")
        _identifier(row["metric_id"], label="promotion gate metric ID")
        gates.append(row)
    item.update({"review": review, "registered_gates": gates})
    _self_hash(item, field="promotion_decision_sha256", label="promotion decision")
    return item


def _validate_active_pointer(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "pointer_id", "version",
            "previous_pointer", "promotion_decision", "fill_preset",
            "retrieval_preset", "source_experiment", "effective_scope", "status",
            "automatic_activation", "application_config_mutation",
            "external_activation_required", "production_policy_authority",
            "active_strategy_pointer_sha256",
        },
        label="active strategy pointer",
    )
    if (
        item["schema_version"] != ACTIVE_POINTER_SCHEMA
        or item["publication_mode"] != "create_once"
        or type(item["version"]) is not int
        or item["version"] < 1
        or item["effective_scope"] != "research-retrieval"
        or item["status"] != "active"
        or item["automatic_activation"] is not False
        or item["application_config_mutation"] is not False
        or item["external_activation_required"] is not True
        or item["production_policy_authority"] is not False
    ):
        raise CorpusStrategyRegistryError("active pointer authority law differs")
    _identifier(item["pointer_id"], label="active pointer ID")
    for field in (
        "promotion_decision", "fill_preset", "retrieval_preset", "source_experiment",
    ):
        item[field] = _identity_dict(item[field], label=f"active pointer {field}")
    if item["previous_pointer"] is not None:
        item["previous_pointer"] = _identity_dict(
            item["previous_pointer"], label="previous active pointer"
        )
    _self_hash(
        item, field="active_strategy_pointer_sha256", label="active strategy pointer"
    )
    return item


def _validate_winner_authority(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "authority_id",
            "expected_winner_count", "source_manifest", "licenses",
            "created_at_utc", "winner_import_authority_sha256",
        },
        label="winner import authority",
    )
    licenses = dict(_mapping(item["licenses"], label="winner authority licenses"))
    expected_licenses = {
        "historical_outcome_read_authority": True,
        "winner_evidence_graph_import": True,
        "graph_research_only": True,
        "automatic_promotion": False,
        "production_policy_authority": False,
    }
    if (
        item["schema_version"] != WINNER_AUTHORITY_SCHEMA
        or item["publication_mode"] != "create_once"
        or item["expected_winner_count"] != 51
        or licenses != expected_licenses
    ):
        raise CorpusStrategyRegistryError("winner import authority is absent/unlicensed")
    _identifier(item["authority_id"], label="winner authority ID")
    item["source_manifest"] = _identity_dict(
        item["source_manifest"], label="winner source manifest"
    )
    item["licenses"] = licenses
    _timestamp(item["created_at_utc"], label="winner authority timestamp")
    _self_hash(
        item, field="winner_import_authority_sha256", label="winner import authority"
    )
    return item


def _validate_winner_evidence(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    _exact_keys(
        item,
        {
            "schema_version", "publication_mode", "authority", "source_manifest",
            "winners", "winner_evidence_sha256",
        },
        label="winner evidence",
    )
    if (
        item["schema_version"] != WINNER_EVIDENCE_SCHEMA
        or item["publication_mode"] != "create_once"
    ):
        raise CorpusStrategyRegistryError("winner evidence law differs")
    item["authority"] = _identity_dict(item["authority"], label="winner authority")
    item["source_manifest"] = _identity_dict(
        item["source_manifest"], label="winner source manifest"
    )
    winners: list[dict[str, object]] = []
    winner_ids: set[str] = set()
    contest_slates: set[tuple[str, str]] = set()
    for ordinal, raw in enumerate(_sequence(item["winners"], label="winners")):
        row = dict(_mapping(raw, label=f"winner[{ordinal}]"))
        _exact_keys(
            row,
            {
                "winner_id", "slate_id", "lineup_id", "player_ids",
                "winning_score", "contest_id",
            },
            label="winner row",
        )
        winner_id = _identifier(row["winner_id"], label="winner ID")
        lineup_id = _identifier(row["lineup_id"], label="winner lineup ID")
        contest_id = _identifier(row["contest_id"], label="winner contest ID")
        slate_id = _string(row["slate_id"], label="winner slate ID")
        roster = list(_sequence(row["player_ids"], label="winner player IDs"))
        score = row["winning_score"]
        if (
            winner_id in winner_ids
            or (contest_id, slate_id) in contest_slates
            or _SLATE.fullmatch(slate_id) is None
            or len(roster) != 9
            or len(set(roster)) != 9
            or any(not isinstance(player_id, str) for player_id in roster)
            or type(score) not in {int, float}
            or isinstance(score, bool)
            or not math.isfinite(float(score))
        ):
            raise CorpusStrategyRegistryError("winner evidence row differs")
        winner_ids.add(winner_id)
        contest_slates.add((contest_id, slate_id))
        row["lineup_id"] = lineup_id
        winners.append(row)
    if len(winners) != 51:
        raise CorpusStrategyRegistryError("winner evidence must contain exactly 51 winners")
    item["winners"] = winners
    _self_hash(item, field="winner_evidence_sha256", label="winner evidence")
    return item


def _validate_release(value: Mapping[str, object]) -> dict[str, object]:
    item = dict(value)
    _exact_keys(item, _RELEASE_KEYS, label="strategy registry release")
    if (
        item["schema_version"] != RELEASE_SCHEMA
        or item["publication_mode"] != "create_once"
        or item["automatic_promotion"] is not False
        or item["application_config_mutation"] is not False
        or item["production_policy_authority"] is not False
        or item["gcs_remains_authoritative"] is not True
        or item["world_matrices_stored_in_graph"] is not False
        or item["raw_outcomes_stored_in_graph"] is not False
    ):
        raise CorpusStrategyRegistryError("strategy registry authority law differs")
    _identifier(item["registry_id"], label="registry ID")
    prefix = _string(item["output_prefix"], label="registry output prefix")
    if not prefix.startswith("gs://") or not prefix.endswith("/"):
        raise CorpusStrategyRegistryError("registry output prefix differs")
    identity_fields = (
        "fill_presets", "retrieval_presets", "corpus_snapshots",
        "slate_structures", "experiment_runs", "metric_sets",
        "promotion_decisions", "active_strategy_pointers",
    )
    optional_identity_fields = {
        "promotion_decisions", "active_strategy_pointers",
    }
    all_keys: list[tuple[object, ...]] = []
    for field in identity_fields:
        values = list(_sequence(item[field], label=field))
        normalized = [
            _identity_dict(raw, label=f"{field}[{ordinal}]")
            for ordinal, raw in enumerate(values)
        ]
        keys = [_identity_key(row) for row in normalized]
        if (
            len(normalized) > _MAX_REGISTRY_OBJECTS
            or (not normalized and field not in optional_identity_fields)
            or keys != sorted(set(keys))
        ):
            raise CorpusStrategyRegistryError(f"{field} must be sorted and unique")
        item[field] = normalized
        all_keys.extend(keys)
    if len(all_keys) != len(set(all_keys)):
        raise CorpusStrategyRegistryError("registry object identities alias across roles")
    requested = item["winner_import_requested"]
    if type(requested) is not bool:
        raise CorpusStrategyRegistryError("winner import request differs")
    if requested:
        raise CorpusStrategyRegistryError(
            "winner import is forbidden by the outcome-blind registry v2 firewall"
        )
    if item["winner_import_authority"] is not None or item["winner_evidence"] is not None:
        raise CorpusStrategyRegistryError(
            "winner evidence cannot be projected without explicit authority request"
        )
    _require_outcome_firewall(item, label="strategy registry release")
    _timestamp(item["created_at_utc"], label="registry created timestamp")
    _self_hash(item, field="registry_release_sha256", label="strategy registry release")
    return item


def _source_node(
    *,
    kind: str,
    logical_id: str,
    registry_id: str,
    identity: Mapping[str, object],
    payload: Mapping[str, object],
    task_index: int = -1,
    slate_id: str = "",
    strategy_id: str = "",
    analysis_scope: str = "strategy-registry",
    metric_name: str = "",
    metric_value: float = 0.0,
    metric_value_present: bool = False,
) -> dict[str, object]:
    normalized = _identity_dict(identity, label=f"{kind} source identity")
    task_present = task_index >= 0
    if task_present != bool(slate_id):
        raise CorpusStrategyRegistryError(f"{kind} task/slate grain differs")
    # Logical identity, rather than content identity, is the MERGE key.  A
    # later release may replay the same exact object, but cannot silently
    # publish different content for an existing registry ID/version.
    node_id = "corpus-strategy-registry:" + canonical_sha256({
        "kind": kind,
        "logical_id": logical_id,
        "registry_id": registry_id,
    })
    return {
        "id": node_id,
        "kind": kind,
        "logical_id": logical_id,
        "run_id": registry_id,
        "task_id": slate_id,
        "payload_sha256": canonical_sha256(payload),
        "properties_json": canonical_json_bytes(payload).decode("utf-8"),
        "source_uri": normalized["uri"],
        "source_generation": normalized["generation"],
        "source_sha256": normalized["sha256"],
        "source_bytes": normalized["bytes"],
        "workstream_namespace": REGISTRY_NAMESPACE,
        "task_index": task_index,
        "task_index_present": task_present,
        "slate_id": slate_id,
        "parameter_set_id": "",
        "strategy_id": strategy_id,
        "analysis_scope": analysis_scope,
        "metric_name": metric_name,
        "metric_value": metric_value,
        "metric_value_present": metric_value_present,
    }


def _edge(
    source: str,
    relationship_type: str,
    target: str,
    properties: Mapping[str, object] | None = None,
    *,
    task_index: int = -1,
    slate_id: str = "",
) -> dict[str, object]:
    return _relationship(
        source,
        relationship_type,
        target,
        properties,
        task_index=task_index,
        task_index_present=task_index >= 0,
        slate_id=slate_id,
    )


def _fetch_rows(
    storage: ExactObjectStore,
    release: Mapping[str, object],
    field: str,
    validator: Callable[[Mapping[str, object]], dict[str, object]],
) -> list[tuple[ObjectIdentity, dict[str, object]]]:
    result = []
    for ordinal, identity_value in enumerate(_sequence(release[field], label=field)):
        identity, body = _read_json(
            storage, identity_value, label=f"{field}[{ordinal}]"
        )
        result.append((identity, validator(body)))
    return result


def prepare_strategy_registry_plan(
    *,
    parent_plan: Neo4jLoadPlan,
    storage: ExactObjectStore,
    release_identity: object,
) -> StrategyRegistryBundle:
    """Validate an exact registry release and append its immutable graph plan."""
    if not isinstance(parent_plan, Neo4jLoadPlan):
        raise CorpusStrategyRegistryError("parent Neo4j load plan differs")
    retained_release_identity, release_body = _read_json(
        storage, release_identity, label="strategy registry release"
    )
    release = _validate_release(release_body)
    fills = _fetch_rows(
        storage, release, "fill_presets",
        lambda value: _validate_preset(value, kind="fill"),
    )
    retrievals = _fetch_rows(
        storage, release, "retrieval_presets",
        lambda value: _validate_preset(value, kind="retrieval"),
    )
    snapshots = _fetch_rows(storage, release, "corpus_snapshots", _validate_snapshot)
    structures = _fetch_rows(storage, release, "slate_structures", _validate_structure)
    experiments = _fetch_rows(storage, release, "experiment_runs", _validate_experiment)
    metric_sets = _fetch_rows(storage, release, "metric_sets", _validate_metric_set)
    decisions = _fetch_rows(
        storage, release, "promotion_decisions", _validate_promotion
    )
    pointers = _fetch_rows(
        storage, release, "active_strategy_pointers", _validate_active_pointer
    )

    def indexed(
        rows: Sequence[tuple[ObjectIdentity, dict[str, object]]], *, label: str,
    ) -> dict[tuple[object, ...], tuple[ObjectIdentity, dict[str, object]]]:
        result = {_identity_key(identity.as_dict()): (identity, body) for identity, body in rows}
        if len(result) != len(rows):
            raise CorpusStrategyRegistryError(f"{label} identities repeat")
        return result

    fill_by_identity = indexed(fills, label="fill presets")
    retrieval_by_identity = indexed(retrievals, label="retrieval presets")
    snapshot_by_identity = indexed(snapshots, label="snapshots")
    structure_by_identity = indexed(structures, label="slate structures")
    experiment_by_identity = indexed(experiments, label="experiments")
    metrics_by_identity = indexed(metric_sets, label="metric sets")
    decision_by_identity = indexed(decisions, label="promotion decisions")
    pointer_by_identity = indexed(pointers, label="active pointers")

    preset_versions: set[tuple[str, str, int]] = set()
    preset_chains: dict[tuple[str, str], list[int]] = {}
    for kind, rows in (("fill", fills), ("retrieval", retrievals)):
        for _, body in rows:
            key = (kind, str(body["preset_id"]), int(body["version"]))
            if key in preset_versions:
                raise CorpusStrategyRegistryError("preset ID/version repeats")
            preset_versions.add(key)
            preset_chains.setdefault(key[:2], []).append(key[2])
    if any(
        sorted(versions) != list(range(1, len(versions) + 1))
        for versions in preset_chains.values()
    ):
        raise CorpusStrategyRegistryError("preset versions are not contiguous")
    structures_by_task: dict[
        tuple[int, str], tuple[ObjectIdentity, dict[str, object]]
    ] = {}
    for identity, structure in structures:
        task_key = (int(structure["task_index"]), str(structure["slate_id"]))
        if task_key in structures_by_task:
            raise CorpusStrategyRegistryError("slate structure task/slate repeats")
        structures_by_task[task_key] = (identity, structure)

    snapshot_fills: set[tuple[int, str, tuple[object, ...]]] = set()
    snapshot_ids: set[str] = set()
    artifact_owner: dict[
        tuple[object, ...], tuple[int, dict[str, object]]
    ] = {}
    referenced_structures: set[tuple[object, ...]] = set()
    for identity, snapshot in snapshots:
        task_key = (int(snapshot["task_index"]), str(snapshot["slate_id"]))
        snapshot_id = str(snapshot["snapshot_id"])
        fill_key = _identity_key(snapshot["producing_fill_preset"])
        structure_key = _identity_key(snapshot["slate_structure"])
        structure_row = structure_by_identity.get(structure_key)
        fill_task_key = (*task_key, fill_key)
        if (
            snapshot_id in snapshot_ids
            or fill_task_key in snapshot_fills
            or fill_key not in fill_by_identity
            or structure_row is None
            or (
                int(structure_row[1]["task_index"]),
                str(structure_row[1]["slate_id"]),
            ) != task_key
            or not set(snapshot["lineup_ids"]).issubset({
                str(row["lineup_id"]) for row in structure_row[1]["lineups"]
            })
        ):
            raise CorpusStrategyRegistryError(
                "snapshot fill/structure/task binding differs"
            )
        snapshot_fills.add(fill_task_key)
        snapshot_ids.add(snapshot_id)
        referenced_structures.add(structure_key)
        for pointer in snapshot["artifact_pointers"]:
            key = _identity_key(pointer["object_identity"])
            prior = artifact_owner.get(key)
            if prior is not None and (
                prior[0] != int(snapshot["task_index"])
                or prior[1] != pointer
            ):
                raise CorpusStrategyRegistryError(
                    "shared matrix artifact identity/role/task differs"
                )
            artifact_owner[key] = (int(snapshot["task_index"]), pointer)
    if referenced_structures != set(structure_by_identity):
        raise CorpusStrategyRegistryError(
            "every slate structure must be bound by a corpus snapshot"
        )

    experiments_by_id: dict[str, tuple[ObjectIdentity, dict[str, object]]] = {}
    for identity, experiment in experiments:
        experiment_id = str(experiment["experiment_id"])
        if experiment_id in experiments_by_id:
            raise CorpusStrategyRegistryError("experiment ID repeats")
        experiments_by_id[experiment_id] = (identity, experiment)
    authority_by_experiment: dict[
        tuple[object, ...],
        dict[str, tuple[ObjectIdentity, dict[str, object]]],
    ] = {}
    seen_authority_identities: set[tuple[object, ...]] = set()
    role_by_field = {
        "accepted_execution": "accepted-execution",
        "accepted_result": "accepted-result",
        "independent_verification": "independent-verification",
        "selection_evidence": "selection-evidence",
        "metric_computation": "metric-computation",
    }
    for experiment_identity, experiment in experiments:
        experiment_key = _identity_key(experiment_identity.as_dict())
        authority: dict[str, tuple[ObjectIdentity, dict[str, object]]] = {}
        effective_identity, effective = _read_json(
            storage,
            experiment["effective_parameters"],
            label=f"experiment {experiment['experiment_id']} effective parameters",
        )
        authority["effective_parameters"] = (
            effective_identity,
            _validate_effective_parameters(effective),
        )
        gate_identity, gate = _read_json(
            storage,
            experiment["pre_execution_gate"],
            label=f"experiment {experiment['experiment_id']} pre-execution gate",
        )
        authority["pre_execution_gate"] = (
            gate_identity,
            _validate_pre_execution_gate(gate),
        )
        for field, expected_role in role_by_field.items():
            evidence_identity, evidence = _read_json(
                storage,
                experiment[field],
                label=f"experiment {experiment['experiment_id']} {field}",
            )
            retained = _validate_evidence_binding(evidence)
            if retained["evidence_role"] != expected_role:
                raise CorpusStrategyRegistryError(
                    f"experiment {field} role binding differs"
                )
            authority[field] = (evidence_identity, retained)
        authority_keys = [
            _identity_key(identity.as_dict()) for identity, _ in authority.values()
        ]
        if (
            len(authority_keys) != len(set(authority_keys))
            or seen_authority_identities.intersection(authority_keys)
        ):
            raise CorpusStrategyRegistryError(
                "experiment authority identities alias across roles or experiments"
            )
        seen_authority_identities.update(authority_keys)
        authority_by_experiment[experiment_key] = authority
    metrics_by_experiment: dict[
        tuple[object, ...], tuple[ObjectIdentity, dict[str, object]]
    ] = {}
    for identity, metric_set in metric_sets:
        experiment_row = experiments_by_id.get(str(metric_set["experiment_id"]))
        if experiment_row is None:
            raise CorpusStrategyRegistryError("metric set experiment binding differs")
        experiment_key = _identity_key(experiment_row[0].as_dict())
        if experiment_key in metrics_by_experiment:
            raise CorpusStrategyRegistryError("metric set experiment binding differs")
        metrics_by_experiment[experiment_key] = (identity, metric_set)
    if set(metrics_by_experiment) != set(experiment_by_identity):
        raise CorpusStrategyRegistryError("every experiment needs one metric set")

    for identity, experiment in experiments:
        fill_key = _identity_key(experiment["fill_preset"])
        retrieval_key = _identity_key(experiment["retrieval_preset"])
        snapshot_key = _identity_key(experiment["corpus_snapshot"])
        metric_key = _identity_key(experiment["metric_set"])
        if (
            fill_key not in fill_by_identity
            or retrieval_key not in retrieval_by_identity
            or snapshot_key not in snapshot_by_identity
            or metric_key not in metrics_by_identity
            or metrics_by_experiment.get(_identity_key(identity.as_dict()), (None,))[0]
            != metrics_by_identity[metric_key][0]
        ):
            raise CorpusStrategyRegistryError("experiment registry reference differs")
        snapshot = snapshot_by_identity[snapshot_key][1]
        if (
            experiment["task_index"] != snapshot["task_index"]
            or experiment["slate_id"] != snapshot["slate_id"]
            or experiment["fill_preset"] != snapshot["producing_fill_preset"]
            or not {
                _identity_key(raw) for raw in experiment["matrix_artifacts"]
            }.issubset({
                _identity_key(raw["object_identity"])
                for raw in snapshot["artifact_pointers"]
                if raw["contains_world_matrix"] is True
            })
        ):
            raise CorpusStrategyRegistryError("experiment snapshot/matrix binding differs")
        metric_set = metrics_by_identity[metric_key][1]
        if any(
            metric_set[field] != experiment[field]
            for field in _EXPERIMENT_AUTHORITY_FIELDS
        ):
            raise CorpusStrategyRegistryError(
                "metric set experiment authority binding differs"
            )
        authority = authority_by_experiment[_identity_key(identity.as_dict())]
        effective_identity, effective = authority["effective_parameters"]
        if (
            effective["experiment_id"] != experiment["experiment_id"]
            or effective["fill_preset"] != experiment["fill_preset"]
            or effective["retrieval_preset"] != experiment["retrieval_preset"]
            or effective["fill_parameters"] != fill_by_identity[fill_key][1]["parameters"]
            or effective["retrieval_parameters"]
            != retrieval_by_identity[retrieval_key][1]["parameters"]
        ):
            raise CorpusStrategyRegistryError(
                "executed parameters differ from the registered presets"
            )
        gate_identity, gate = authority["pre_execution_gate"]
        retrospective = (
            gate["schema_version"] == RETROSPECTIVE_REGISTRATION_SCHEMA
        )
        if (
            gate["experiment_id"] != experiment["experiment_id"]
            or gate["task_index"] != experiment["task_index"]
            or gate["slate_id"] != experiment["slate_id"]
            or gate["fill_preset"] != experiment["fill_preset"]
            or gate["retrieval_preset"] != experiment["retrieval_preset"]
            or gate["corpus_snapshot"] != experiment["corpus_snapshot"]
            or gate["matrix_artifacts"] != experiment["matrix_artifacts"]
            or gate["effective_parameters"] != effective_identity.as_dict()
            or gate["exact_release"] != experiment["exact_release"]
        ):
            raise CorpusStrategyRegistryError(
                "pre-execution gate experiment binding differs"
            )
        if retrospective:
            if (
                effective["schema_version"]
                != RETROSPECTIVE_EFFECTIVE_PARAMETERS_SCHEMA
                or effective["source_effective_policy"]
                != gate["effective_policy"]
            ):
                raise CorpusStrategyRegistryError(
                    "retrospective effective-policy binding differs"
                )
            expected_dependencies = {
                "accepted_execution": [
                    gate_identity.as_dict(), effective_identity.as_dict(),
                    gate["task_acceptance"], gate["science_terminal"],
                ],
                "accepted_result": [
                    authority["accepted_execution"][0].as_dict(),
                    effective_identity.as_dict(), gate["task_result"],
                    gate["variant_result"],
                ],
                "independent_verification": [
                    authority["accepted_result"][0].as_dict(),
                    effective_identity.as_dict(),
                    gate["independent_verification"],
                ],
                "selection_evidence": [
                    authority["accepted_result"][0].as_dict(),
                    authority["independent_verification"][0].as_dict(),
                    effective_identity.as_dict(), gate["variant_result"],
                ],
                "metric_computation": [
                    authority["accepted_result"][0].as_dict(),
                    authority["independent_verification"][0].as_dict(),
                    effective_identity.as_dict(),
                    authority["selection_evidence"][0].as_dict(),
                    gate["independent_verification"],
                ],
            }
        else:
            if effective["schema_version"] != EFFECTIVE_PARAMETERS_SCHEMA:
                raise CorpusStrategyRegistryError(
                    "prospective effective-parameter binding differs"
                )
            expected_dependencies = {
                "accepted_execution": [
                    gate_identity.as_dict(), effective_identity.as_dict(),
                ],
                "accepted_result": [
                    authority["accepted_execution"][0].as_dict(),
                    effective_identity.as_dict(),
                ],
                "independent_verification": [
                    authority["accepted_result"][0].as_dict(),
                    effective_identity.as_dict(),
                ],
                "selection_evidence": [
                    authority["accepted_result"][0].as_dict(),
                    authority["independent_verification"][0].as_dict(),
                    effective_identity.as_dict(),
                ],
                "metric_computation": [
                    authority["accepted_result"][0].as_dict(),
                    authority["independent_verification"][0].as_dict(),
                    effective_identity.as_dict(),
                    authority["selection_evidence"][0].as_dict(),
                ],
            }
        for field, expected in expected_dependencies.items():
            evidence = authority[field][1]
            normalized_expected = sorted(expected, key=_identity_key)
            if (
                evidence["experiment_id"] != experiment["experiment_id"]
                or evidence["task_index"] != experiment["task_index"]
                or evidence["slate_id"] != experiment["slate_id"]
                or evidence["exact_release"] != experiment["exact_release"]
                or evidence["dependencies"] != normalized_expected
                or (
                    retrospective
                    and (
                        evidence["schema_version"]
                        != RETROSPECTIVE_EVIDENCE_BINDING_SCHEMA
                        or evidence["created_at_utc"]
                        != gate["created_at_utc"]
                    )
                )
                or (
                    not retrospective
                    and (
                        evidence["schema_version"] != EVIDENCE_BINDING_SCHEMA
                        or evidence["created_at_utc"] <= gate["created_at_utc"]
                    )
                )
            ):
                raise CorpusStrategyRegistryError(
                    f"experiment {field} evidence chain differs"
                )
        if authority["metric_computation"][1]["computed_metrics_sha256"] != (
            canonical_sha256(metric_set["metrics"])
        ):
            raise CorpusStrategyRegistryError(
                "metric values differ from the bound computation evidence"
            )
        paired = metric_set["paired_design"]
        baseline_values = [
            metric["baseline_experiment_run"] for metric in metric_set["metrics"]
            if metric["baseline_experiment_run"] is not None
        ]
        baseline_keys = {_identity_key(raw) for raw in baseline_values}
        if paired["required"] is False:
            continue
        if len(baseline_keys) != 1:
            raise CorpusStrategyRegistryError(
                "paired metrics must bind one exact baseline experiment"
            )
        baseline_row = experiment_by_identity.get(next(iter(baseline_keys)))
        if baseline_row is None:
            raise CorpusStrategyRegistryError("paired baseline is not registered")
        baseline_experiment = baseline_row[1]
        baseline_metric_set = metrics_by_identity[
            _identity_key(baseline_experiment["metric_set"])
        ][1]
        baseline_metrics_by_id = {
            str(row["metric_id"]): row for row in baseline_metric_set["metrics"]
        }
        for metric in metric_set["metrics"]:
            matched = baseline_metrics_by_id.get(str(metric["metric_id"]))
            if matched is None or any(
                matched[field] != metric[field]
                for field in (
                    "name", "unit", "direction", "scope", "sample_count",
                    "paired_key",
                )
            ):
                raise CorpusStrategyRegistryError(
                    "paired metric evaluation law differs from baseline"
                )
        candidate_matrices = {
            _identity_key(raw) for raw in experiment["matrix_artifacts"]
        }
        baseline_matrices = {
            _identity_key(raw) for raw in baseline_experiment["matrix_artifacts"]
        }
        if (
            baseline_experiment["task_index"] != experiment["task_index"]
            or baseline_experiment["slate_id"] != experiment["slate_id"]
            or baseline_experiment["exact_release"] != experiment["exact_release"]
            or baseline_matrices != candidate_matrices
        ):
            raise CorpusStrategyRegistryError(
                "paired experiments do not share slate/world/release law"
            )
        if paired["comparison_axis"] == "retrieval":
            if (
                baseline_experiment["corpus_snapshot"]
                != experiment["corpus_snapshot"]
                or baseline_experiment["fill_preset"] != experiment["fill_preset"]
                or baseline_experiment["retrieval_preset"]
                == experiment["retrieval_preset"]
            ):
                raise CorpusStrategyRegistryError(
                    "retrieval comparison is not isolated on one snapshot"
                )
        elif paired["comparison_axis"] == "fill":
            baseline_snapshot = snapshot_by_identity[
                _identity_key(baseline_experiment["corpus_snapshot"])
            ][1]
            candidate_snapshot = snapshot_by_identity[
                _identity_key(experiment["corpus_snapshot"])
            ][1]
            baseline_snapshot_worlds = {
                _identity_key(row["object_identity"])
                for row in baseline_snapshot["artifact_pointers"]
                if row["contains_world_matrix"] is True
            }
            candidate_snapshot_worlds = {
                _identity_key(row["object_identity"])
                for row in candidate_snapshot["artifact_pointers"]
                if row["contains_world_matrix"] is True
            }
            if (
                baseline_experiment["corpus_snapshot"]
                == experiment["corpus_snapshot"]
                or baseline_experiment["fill_preset"] == experiment["fill_preset"]
                or baseline_experiment["retrieval_preset"]
                != experiment["retrieval_preset"]
                or baseline_snapshot_worlds != candidate_snapshot_worlds
                or baseline_snapshot["source_snapshot_manifest"]
                != candidate_snapshot["source_snapshot_manifest"]
                or baseline_snapshot["slate_structure"]
                != candidate_snapshot["slate_structure"]
                or (
                    baseline_snapshot["season"], baseline_snapshot["week"]
                ) != (candidate_snapshot["season"], candidate_snapshot["week"])
            ):
                raise CorpusStrategyRegistryError(
                    "fill comparison is not isolated across matched snapshots"
                )

    decision_by_candidate: dict[tuple[object, ...], list[dict[str, object]]] = {}
    decision_versions: set[tuple[str, int]] = set()
    decision_chains: dict[str, list[int]] = {}
    for _, decision in decisions:
        decision_version = (str(decision["decision_id"]), int(decision["version"]))
        if decision_version in decision_versions:
            raise CorpusStrategyRegistryError("promotion decision ID/version repeats")
        decision_versions.add(decision_version)
        decision_chains.setdefault(decision_version[0], []).append(
            decision_version[1]
        )
        candidate_key = _identity_key(decision["candidate_experiment"])
        metric_key = _identity_key(decision["metric_set"])
        candidate = experiment_by_identity.get(candidate_key)
        if (
            candidate is None
            or metric_key not in metrics_by_identity
            or candidate[1]["metric_set"] != decision["metric_set"]
        ):
            raise CorpusStrategyRegistryError("promotion evidence binding differs")
        metric_set = metrics_by_identity[metric_key][1]
        metrics_by_id = {str(row["metric_id"]): row for row in metric_set["metrics"]}
        gate_passes: list[bool] = []
        for gate in decision["registered_gates"]:
            metric = metrics_by_id.get(str(gate["metric_id"]))
            if (
                metric is None
                or metric["scope"] != gate["scope"]
                or metric["sample_count"] < gate["minimum_sample_count"]
            ):
                raise CorpusStrategyRegistryError("promotion gate metric binding differs")
            observed = float(metric["value"])
            threshold = float(gate["threshold"])
            gate_passes.append({
                ">": observed > threshold,
                ">=": observed >= threshold,
                "<": observed < threshold,
                "<=": observed <= threshold,
                "==": observed == threshold,
            }[str(gate["operator"])])
        if not any(
            gate["scope"] == "heldout" for gate in decision["registered_gates"]
        ):
            raise CorpusStrategyRegistryError(
                "promotion decision lacks a registered heldout gate"
            )
        if decision["decision"] == "promote" and not all(gate_passes):
            raise CorpusStrategyRegistryError(
                "promote decision has an unsatisfied registered gate"
            )
        if decision["incumbent_active_pointer"] is not None and _identity_key(
            decision["incumbent_active_pointer"]
        ) not in pointer_by_identity:
            raise CorpusStrategyRegistryError("promotion incumbent pointer is absent")
        decision_by_candidate.setdefault(candidate_key, []).append(decision)
    if any(
        sorted(versions) != list(range(1, len(versions) + 1))
        for versions in decision_chains.values()
    ):
        raise CorpusStrategyRegistryError(
            "promotion decision versions are not contiguous"
        )

    pointer_versions: dict[str, list[tuple[ObjectIdentity, dict[str, object]]]] = {}
    for identity, pointer in pointers:
        decision_key = _identity_key(pointer["promotion_decision"])
        experiment_key = _identity_key(pointer["source_experiment"])
        decision = decision_by_identity.get(decision_key)
        experiment = experiment_by_identity.get(experiment_key)
        if (
            decision is None
            or experiment is None
            or decision[1]["decision"] != "promote"
            or decision[1]["candidate_experiment"] != pointer["source_experiment"]
            or experiment[1]["fill_preset"] != pointer["fill_preset"]
            or experiment[1]["retrieval_preset"] != pointer["retrieval_preset"]
        ):
            raise CorpusStrategyRegistryError("active pointer promotion binding differs")
        pointer_versions.setdefault(str(pointer["pointer_id"]), []).append((identity, pointer))
    for pointer_id, rows in pointer_versions.items():
        rows.sort(key=lambda row: int(row[1]["version"]))
        if [row[1]["version"] for row in rows] != list(range(1, len(rows) + 1)):
            raise CorpusStrategyRegistryError("active pointer versions are not contiguous")
        for ordinal, (identity, pointer) in enumerate(rows):
            expected_previous = None if ordinal == 0 else rows[ordinal - 1][0].as_dict()
            if pointer["previous_pointer"] != expected_previous:
                raise CorpusStrategyRegistryError(
                    f"active pointer chain differs for {pointer_id}"
                )

    winner_authority_row: tuple[ObjectIdentity, dict[str, object]] | None = None
    winner_evidence_row: tuple[ObjectIdentity, dict[str, object]] | None = None
    if release["winner_import_requested"] is True:
        authority_identity, authority_body = _read_json(
            storage,
            release["winner_import_authority"],
            label="winner import authority",
        )
        evidence_identity, evidence_body = _read_json(
            storage, release["winner_evidence"], label="winner evidence"
        )
        authority = _validate_winner_authority(authority_body)
        evidence = _validate_winner_evidence(evidence_body)
        if (
            evidence["authority"] != authority_identity.as_dict()
            or evidence["source_manifest"] != authority["source_manifest"]
        ):
            raise CorpusStrategyRegistryError("winner authority/evidence binding differs")
        winner_authority_row = (authority_identity, authority)
        winner_evidence_row = (evidence_identity, evidence)

    registry_id = str(release["registry_id"])
    nodes: list[dict[str, object]] = []
    edges: list[dict[str, object]] = []
    release_node = _source_node(
        kind="StrategyRegistryRelease",
        logical_id=(
            f"strategy-registry-release:{registry_id}:"
            f"{release['registry_release_sha256']}"
        ),
        registry_id=registry_id,
        identity=retained_release_identity.as_dict(),
        payload=release,
    )
    nodes.append(release_node)
    release_node_id = str(release_node["id"])

    fill_nodes: dict[tuple[object, ...], str] = {}
    retrieval_nodes: dict[tuple[object, ...], str] = {}
    for kind, rows, target in (
        ("FillPreset", fills, fill_nodes),
        ("RetrievalPreset", retrievals, retrieval_nodes),
    ):
        for identity, preset in rows:
            node = _source_node(
                kind=kind,
                logical_id=(
                    f"{kind.lower()}:{preset['preset_id']}:v{preset['version']}"
                ),
                registry_id=registry_id,
                identity=identity.as_dict(),
                payload=preset,
                strategy_id=str(preset["preset_id"]),
                analysis_scope="versioned-typed-preset",
            )
            nodes.append(node)
            target[_identity_key(identity.as_dict())] = str(node["id"])
            edges.append(_edge(
                release_node_id,
                "REGISTERS_FILL_PRESET" if kind == "FillPreset" else "REGISTERS_RETRIEVAL_PRESET",
                str(node["id"]),
                {"version": preset["version"]},
            ))
        by_preset_id: dict[str, list[tuple[ObjectIdentity, dict[str, object]]]] = {}
        for identity, preset in rows:
            by_preset_id.setdefault(str(preset["preset_id"]), []).append(
                (identity, preset)
            )
        for preset_rows in by_preset_id.values():
            preset_rows.sort(key=lambda row: int(row[1]["version"]))
            for previous, current in zip(preset_rows, preset_rows[1:]):
                edges.append(_edge(
                    target[_identity_key(current[0].as_dict())],
                    (
                        "SUPERSEDES_FILL_PRESET"
                        if kind == "FillPreset"
                        else "SUPERSEDES_RETRIEVAL_PRESET"
                    ),
                    target[_identity_key(previous[0].as_dict())],
                ))

    player_catalog: dict[str, str] = {}
    player_payloads: dict[str, dict[str, object]] = {}
    player_sources: dict[str, ObjectIdentity] = {}
    for structure_identity, structure in structures:
        for player in structure["players"]:
            player_id = str(player["player_id"])
            payload = {
                "player_id": player_id,
                "display_name": player["display_name"],
            }
            prior = player_payloads.get(player_id)
            if prior is not None and prior != payload:
                raise CorpusStrategyRegistryError("Player identity attributes conflict")
            player_payloads[player_id] = payload
            prior_source = player_sources.get(player_id)
            if (
                prior_source is None
                or _identity_key(structure_identity.as_dict())
                < _identity_key(prior_source.as_dict())
            ):
                player_sources[player_id] = structure_identity
    for player_id, payload in sorted(player_payloads.items()):
        node = _source_node(
            kind="Player",
            logical_id=f"player:{player_id}",
            registry_id=registry_id,
            identity=player_sources[player_id].as_dict(),
            payload=payload,
            analysis_scope="structure-sourced-player-dimension",
        )
        nodes.append(node)
        player_catalog[player_id] = str(node["id"])

    snapshot_nodes: dict[tuple[object, ...], str] = {}
    artifact_nodes: dict[tuple[object, ...], str] = {}
    slate_nodes: dict[str, str] = {}
    player_slate_nodes: dict[tuple[str, str], str] = {}
    lineup_nodes: dict[tuple[str, str], str] = {}
    for structure_identity, structure in structures:
        task_index = int(structure["task_index"])
        slate_id = str(structure["slate_id"])
        slate_node = _source_node(
            kind="Slate",
            logical_id=f"slate:{slate_id}",
            registry_id=registry_id,
            identity=structure_identity.as_dict(),
            payload={
                "slate_id": slate_id,
                "task_index": task_index,
                "slate_structure_sha256": structure["slate_structure_sha256"],
            },
            task_index=task_index,
            slate_id=slate_id,
            analysis_scope="slate-structure",
        )
        nodes.append(slate_node)
        slate_nodes[slate_id] = str(slate_node["id"])
        edges.append(_edge(
            release_node_id, "REGISTERS_SLATE", str(slate_node["id"]),
            task_index=task_index, slate_id=slate_id,
        ))
        game_nodes: dict[str, str] = {}
        team_nodes: dict[str, str] = {}
        for game in structure["games"]:
            game_id = str(game["game_id"])
            node = _source_node(
                kind="Game", logical_id=f"game:{slate_id}:{game_id}",
                registry_id=registry_id, identity=structure_identity.as_dict(),
                payload=game, task_index=task_index, slate_id=slate_id,
                analysis_scope="slate-game",
            )
            nodes.append(node)
            game_nodes[game_id] = str(node["id"])
            edges.append(_edge(
                str(slate_node["id"]), "HAS_GAME", str(node["id"]),
                task_index=task_index, slate_id=slate_id,
            ))
        for team in structure["teams"]:
            team_id = str(team["team"])
            node = _source_node(
                kind="TeamSlate", logical_id=f"team-slate:{slate_id}:{team_id}",
                registry_id=registry_id, identity=structure_identity.as_dict(),
                payload=team, task_index=task_index, slate_id=slate_id,
                analysis_scope="team-slate",
            )
            nodes.append(node)
            team_nodes[team_id] = str(node["id"])
            edges.append(_edge(
                game_nodes[str(team["game_id"])], "HAS_TEAM_SLATE", str(node["id"]),
                task_index=task_index, slate_id=slate_id,
            ))
        for player in structure["players"]:
            player_id = str(player["player_id"])
            node = _source_node(
                kind="PlayerSlate",
                logical_id=f"player-slate:{slate_id}:{player_id}",
                registry_id=registry_id,
                identity=structure_identity.as_dict(),
                payload=player,
                task_index=task_index,
                slate_id=slate_id,
                analysis_scope="player-slate",
            )
            nodes.append(node)
            player_slate_nodes[(slate_id, player_id)] = str(node["id"])
            edges.extend((
                _edge(
                    team_nodes[str(player["team"])], "HAS_PLAYER_SLATE", str(node["id"]),
                    task_index=task_index, slate_id=slate_id,
                ),
                _edge(
                    str(node["id"]), "REPRESENTS_PLAYER", player_catalog[player_id],
                    task_index=task_index, slate_id=slate_id,
                ),
            ))
        for lineup in structure["lineups"]:
            lineup_id = str(lineup["lineup_id"])
            node = _source_node(
                kind="Lineup",
                logical_id=f"lineup:{slate_id}:{lineup_id}",
                registry_id=registry_id,
                identity=structure_identity.as_dict(),
                payload=lineup,
                task_index=task_index,
                slate_id=slate_id,
                analysis_scope="lineup-roster",
            )
            nodes.append(node)
            lineup_nodes[(slate_id, lineup_id)] = str(node["id"])
            edges.append(_edge(
                str(node["id"]), "FOR_SLATE", str(slate_node["id"]),
                task_index=task_index, slate_id=slate_id,
            ))
            for slot, player_id in enumerate(lineup["player_ids"]):
                edges.append(_edge(
                    str(node["id"]), "ROSTERS_PLAYER_SLATE",
                    player_slate_nodes[(slate_id, str(player_id))],
                    {"roster_ordinal": slot},
                    task_index=task_index, slate_id=slate_id,
                ))

    for snapshot_identity, snapshot in snapshots:
        task_index = int(snapshot["task_index"])
        slate_id = str(snapshot["slate_id"])
        snapshot_key = _identity_key(snapshot_identity.as_dict())
        snapshot_node = _source_node(
            kind="CorpusSnapshot",
            logical_id=f"registry-snapshot:{snapshot['snapshot_id']}:{slate_id}",
            registry_id=registry_id,
            identity=snapshot_identity.as_dict(),
            payload=snapshot,
            task_index=task_index,
            slate_id=slate_id,
            analysis_scope="generation-pinned-fill-produced-snapshot",
        )
        nodes.append(snapshot_node)
        snapshot_nodes[snapshot_key] = str(snapshot_node["id"])
        edges.extend((
            _edge(
                release_node_id, "REGISTERS_CORPUS_SNAPSHOT",
                str(snapshot_node["id"]),
                {"snapshot_id": snapshot["snapshot_id"]},
                task_index=task_index, slate_id=slate_id,
            ),
            _edge(
                str(snapshot_node["id"]), "PRODUCED_BY_FILL_PRESET",
                fill_nodes[_identity_key(snapshot["producing_fill_preset"])],
                task_index=task_index, slate_id=slate_id,
            ),
            _edge(
                str(snapshot_node["id"]), "HAS_SLATE", slate_nodes[slate_id],
                task_index=task_index, slate_id=slate_id,
            ),
        ))
        for lineup_id in snapshot["lineup_ids"]:
            edges.append(_edge(
                str(snapshot_node["id"]), "CONTAINS_LINEUP",
                lineup_nodes[(slate_id, str(lineup_id))],
                task_index=task_index, slate_id=slate_id,
            ))
        for pointer in snapshot["artifact_pointers"]:
            artifact_identity = pointer["object_identity"]
            artifact_key = _identity_key(artifact_identity)
            artifact_node_id = artifact_nodes.get(artifact_key)
            if artifact_node_id is None:
                artifact_node = _source_node(
                    kind="CorpusArtifactPointer",
                    logical_id=(
                        f"registry-artifact:{artifact_identity['sha256']}:"
                        f"{pointer['role']}"
                    ),
                    registry_id=registry_id,
                    identity=artifact_identity,
                    payload=pointer,
                    task_index=task_index,
                    slate_id=slate_id,
                    analysis_scope="gcs-pointer-only-world-matrix",
                )
                nodes.append(artifact_node)
                artifact_node_id = str(artifact_node["id"])
                artifact_nodes[artifact_key] = artifact_node_id
            edges.append(_edge(
                str(snapshot_node["id"]), "REFERENCES_ARTIFACT",
                artifact_node_id,
                {
                    "role": pointer["role"],
                    "contains_world_matrix": pointer["contains_world_matrix"],
                    "matrix_body_in_graph": False,
                },
                task_index=task_index, slate_id=slate_id,
            ))

    experiment_nodes: dict[tuple[object, ...], str] = {}
    metric_nodes_by_set: dict[tuple[object, ...], dict[str, str]] = {}
    for experiment_identity, experiment in experiments:
        experiment_key = _identity_key(experiment_identity.as_dict())
        task_index = int(experiment["task_index"])
        slate_id = str(experiment["slate_id"])
        node = _source_node(
            kind="ExperimentRun",
            logical_id=f"experiment:{experiment['experiment_id']}",
            registry_id=registry_id,
            identity=experiment_identity.as_dict(),
            payload=experiment,
            task_index=task_index,
            slate_id=slate_id,
            analysis_scope="fill-x-retrieval-x-slate-exact-release",
        )
        nodes.append(node)
        experiment_nodes[experiment_key] = str(node["id"])
        edges.extend((
            _edge(
                release_node_id, "HAS_EXPERIMENT_RUN", str(node["id"]),
                task_index=task_index, slate_id=slate_id,
            ),
            _edge(
                str(node["id"]), "USES_FILL_PRESET",
                fill_nodes[_identity_key(experiment["fill_preset"])],
                task_index=task_index, slate_id=slate_id,
            ),
            _edge(
                str(node["id"]), "USES_RETRIEVAL_PRESET",
                retrieval_nodes[_identity_key(experiment["retrieval_preset"])],
                task_index=task_index, slate_id=slate_id,
            ),
            _edge(
                str(node["id"]), "USES_CORPUS_SNAPSHOT",
                snapshot_nodes[_identity_key(experiment["corpus_snapshot"])],
                task_index=task_index, slate_id=slate_id,
            ),
        ))
        authority_kinds = {
            "pre_execution_gate": (
                "ExperimentPreExecutionGate", "PASSED_PRE_EXECUTION_GATE"
            ),
            "effective_parameters": (
                "ExperimentEffectiveParameters", "EXECUTED_WITH_EFFECTIVE_PARAMETERS"
            ),
            "accepted_execution": (
                "ExperimentAcceptedExecution", "HAS_ACCEPTED_EXECUTION"
            ),
            "accepted_result": (
                "ExperimentAcceptedResult", "HAS_ACCEPTED_RESULT"
            ),
            "independent_verification": (
                "ExperimentIndependentVerification",
                "HAS_INDEPENDENT_VERIFICATION",
            ),
            "selection_evidence": (
                "ExperimentSelectionEvidence", "HAS_SELECTION_EVIDENCE"
            ),
            "metric_computation": (
                "ExperimentMetricComputation", "HAS_METRIC_COMPUTATION"
            ),
        }
        for field in _EXPERIMENT_AUTHORITY_FIELDS:
            authority_identity, authority_payload = authority_by_experiment[
                experiment_key
            ][field]
            authority_kind, relationship_type = authority_kinds[field]
            if (
                field == "pre_execution_gate"
                and authority_payload["schema_version"]
                == RETROSPECTIVE_REGISTRATION_SCHEMA
            ):
                authority_kind = "ExperimentRetrospectiveRegistration"
                relationship_type = "HAS_RETROSPECTIVE_REGISTRATION"
            authority_node = _source_node(
                kind=authority_kind,
                logical_id=(
                    f"experiment-authority:{experiment['experiment_id']}:{field}"
                ),
                registry_id=registry_id,
                identity=authority_identity.as_dict(),
                payload=authority_payload,
                task_index=task_index,
                slate_id=slate_id,
                analysis_scope="outcome-blind-execution-authority",
            )
            nodes.append(authority_node)
            edges.append(_edge(
                str(node["id"]), relationship_type, str(authority_node["id"]),
                {"uses_realized_outcomes": False},
                task_index=task_index,
                slate_id=slate_id,
            ))
        for artifact in experiment["matrix_artifacts"]:
            edges.append(_edge(
                str(node["id"]), "USES_MATRIX_ARTIFACT",
                artifact_nodes[_identity_key(artifact)],
                {"matrix_body_in_graph": False},
                task_index=task_index, slate_id=slate_id,
            ))
        metric_identity, metric_set = metrics_by_experiment[experiment_key]
        metric_set_key = _identity_key(metric_identity.as_dict())
        metric_set_node = _source_node(
            kind="ExperimentMetricSet",
            logical_id=f"metric-set:{experiment['experiment_id']}",
            registry_id=registry_id,
            identity=metric_identity.as_dict(),
            payload=metric_set,
            task_index=task_index,
            slate_id=slate_id,
            analysis_scope="paired-heldout-metric-set",
        )
        nodes.append(metric_set_node)
        edges.append(_edge(
            str(node["id"]), "HAS_METRIC_SET", str(metric_set_node["id"]),
            task_index=task_index, slate_id=slate_id,
        ))
        metric_nodes: dict[str, str] = {}
        for metric in metric_set["metrics"]:
            metric_id = str(metric["metric_id"])
            metric_node = _source_node(
                kind="Metric",
                logical_id=f"metric:{experiment['experiment_id']}:{metric_id}",
                registry_id=registry_id,
                identity=metric_identity.as_dict(),
                payload=metric,
                task_index=task_index,
                slate_id=slate_id,
                analysis_scope=str(metric["scope"]),
                metric_name=str(metric["name"]),
                metric_value=float(metric["value"]),
                metric_value_present=True,
            )
            nodes.append(metric_node)
            metric_nodes[metric_id] = str(metric_node["id"])
            edges.append(_edge(
                str(metric_set_node["id"]), "HAS_METRIC", str(metric_node["id"]),
                {
                    "scope": metric["scope"],
                    "paired_key": metric["paired_key"],
                    "selection_informed_by_heldout": False,
                },
                task_index=task_index, slate_id=slate_id,
            ))
        metric_nodes_by_set[metric_set_key] = metric_nodes

    # Build pairing relationships only after every experiment node exists, so
    # release ordering cannot influence the immutable plan.
    for metric_identity, metric_set in metric_sets:
        metric_set_key = _identity_key(metric_identity.as_dict())
        experiment_identity, experiment = experiments_by_id[
            str(metric_set["experiment_id"])
        ]
        task_index = int(experiment["task_index"])
        slate_id = str(experiment["slate_id"])
        for metric in metric_set["metrics"]:
            baseline = metric["baseline_experiment_run"]
            if baseline is None:
                continue
            candidate_edge = _edge(
                metric_nodes_by_set[metric_set_key][str(metric["metric_id"])],
                "PAIRED_AGAINST_EXPERIMENT",
                experiment_nodes[_identity_key(baseline)],
                {
                    "paired_key": metric["paired_key"],
                    "comparison_axis": metric_set["paired_design"][
                        "comparison_axis"
                    ],
                    "same_snapshot": metric_set["paired_design"][
                        "same_snapshot"
                    ],
                    "same_worlds": True,
                },
                task_index=task_index, slate_id=slate_id,
            )
            edges.append(candidate_edge)

    decision_nodes: dict[tuple[object, ...], str] = {}
    for decision_identity, decision in decisions:
        node = _source_node(
            kind="PromotionDecision",
            logical_id=f"promotion:{decision['decision_id']}:v{decision['version']}",
            registry_id=registry_id,
            identity=decision_identity.as_dict(),
            payload=decision,
            analysis_scope="reviewed-no-auto-promotion",
        )
        nodes.append(node)
        decision_nodes[_identity_key(decision_identity.as_dict())] = str(node["id"])
        edges.extend((
            _edge(release_node_id, "HAS_PROMOTION_DECISION", str(node["id"])),
            _edge(
                str(node["id"]), "EVALUATES_EXPERIMENT",
                experiment_nodes[_identity_key(decision["candidate_experiment"])],
                {"decision": decision["decision"], "automatic_promotion": False},
            ),
        ))
        metric_nodes = metric_nodes_by_set[_identity_key(decision["metric_set"])]
        for gate in decision["registered_gates"]:
            edges.append(_edge(
                str(node["id"]), "EVALUATES_METRIC",
                metric_nodes[str(gate["metric_id"])], gate,
            ))
    decisions_by_id: dict[
        str, list[tuple[ObjectIdentity, dict[str, object]]]
    ] = {}
    for identity, decision in decisions:
        decisions_by_id.setdefault(str(decision["decision_id"]), []).append(
            (identity, decision)
        )
    for decision_rows in decisions_by_id.values():
        decision_rows.sort(key=lambda row: int(row[1]["version"]))
        for previous, current in zip(decision_rows, decision_rows[1:]):
            edges.append(_edge(
                decision_nodes[_identity_key(current[0].as_dict())],
                "SUPERSEDES_PROMOTION_DECISION",
                decision_nodes[_identity_key(previous[0].as_dict())],
            ))

    pointer_nodes: dict[tuple[object, ...], str] = {}
    for pointer_identity, pointer in pointers:
        node = _source_node(
            kind="ActiveStrategyPointer",
            logical_id=f"active:{pointer['pointer_id']}:v{pointer['version']}",
            registry_id=registry_id,
            identity=pointer_identity.as_dict(),
            payload=pointer,
            strategy_id=str(pointer["pointer_id"]),
            analysis_scope="versioned-research-pointer-external-activation-required",
        )
        nodes.append(node)
        pointer_nodes[_identity_key(pointer_identity.as_dict())] = str(node["id"])
        edges.extend((
            _edge(release_node_id, "PUBLISHES_ACTIVE_POINTER", str(node["id"])),
            _edge(
                str(node["id"]), "ACTIVATED_BY_REVIEWED_DECISION",
                decision_nodes[_identity_key(pointer["promotion_decision"])],
                {"automatic_activation": False, "application_config_mutation": False},
            ),
            _edge(
                str(node["id"]), "POINTS_TO_FILL_PRESET",
                fill_nodes[_identity_key(pointer["fill_preset"])],
            ),
            _edge(
                str(node["id"]), "POINTS_TO_RETRIEVAL_PRESET",
                retrieval_nodes[_identity_key(pointer["retrieval_preset"])],
            ),
            _edge(
                str(node["id"]), "SOURCE_EXPERIMENT",
                experiment_nodes[_identity_key(pointer["source_experiment"])],
            ),
        ))
    for pointer_identity, pointer in pointers:
        if pointer["previous_pointer"] is not None:
            edges.append(_edge(
                pointer_nodes[_identity_key(pointer_identity.as_dict())],
                "SUPERSEDES_ACTIVE_POINTER",
                pointer_nodes[_identity_key(pointer["previous_pointer"])],
            ))
    for decision_identity, decision in decisions:
        if decision["incumbent_active_pointer"] is not None:
            edges.append(_edge(
                decision_nodes[_identity_key(decision_identity.as_dict())],
                "REVIEWS_AGAINST_ACTIVE_POINTER",
                pointer_nodes[_identity_key(decision["incumbent_active_pointer"])],
            ))

    winner_count = 0
    if winner_authority_row is not None and winner_evidence_row is not None:
        authority_identity, authority = winner_authority_row
        evidence_identity, evidence = winner_evidence_row
        authority_node = _source_node(
            kind="WinnerImportAuthority",
            logical_id=f"winner-authority:{authority['authority_id']}",
            registry_id=registry_id,
            identity=authority_identity.as_dict(),
            payload=authority,
            analysis_scope="separately-licensed-historical-winner-evidence",
        )
        evidence_node = _source_node(
            kind="WinnerEvidenceSet",
            logical_id=f"winner-evidence:{evidence['winner_evidence_sha256']}",
            registry_id=registry_id,
            identity=evidence_identity.as_dict(),
            payload={
                "schema_version": evidence["schema_version"],
                "winner_count": len(evidence["winners"]),
                "winner_evidence_sha256": evidence["winner_evidence_sha256"],
            },
            analysis_scope="51-winner-evidence",
        )
        nodes.extend((authority_node, evidence_node))
        edges.extend((
            _edge(release_node_id, "IMPORTS_WINNER_EVIDENCE", str(evidence_node["id"])),
            _edge(
                str(evidence_node["id"]), "AUTHORIZED_BY",
                str(authority_node["id"]),
                {"historical_outcome_read_authority": True, "graph_research_only": True},
            ),
        ))
        for winner in evidence["winners"]:
            slate_id = str(winner["slate_id"])
            if slate_id not in slate_nodes or any(
                (slate_id, str(player_id)) not in player_slate_nodes
                for player_id in winner["player_ids"]
            ):
                raise CorpusStrategyRegistryError(
                    "winner lineup cannot traverse registered slate/player structure"
                )
            node = _source_node(
                kind="WinningLineup",
                logical_id=f"winner:{winner['winner_id']}",
                registry_id=registry_id,
                identity=evidence_identity.as_dict(),
                payload=winner,
                analysis_scope="licensed-historical-winner",
                metric_name="winning_score",
                metric_value=float(winner["winning_score"]),
                metric_value_present=True,
            )
            nodes.append(node)
            winner_count += 1
            edges.extend((
                _edge(
                    str(evidence_node["id"]), "HAS_WINNING_LINEUP", str(node["id"]),
                    {"slate_id": slate_id},
                ),
                _edge(
                    str(node["id"]), "WINNER_FOR_SLATE", slate_nodes[slate_id],
                    {"contest_id": winner["contest_id"]},
                ),
            ))
            for ordinal, player_id in enumerate(winner["player_ids"]):
                edges.append(_edge(
                    str(node["id"]), "ROSTERS_PLAYER_SLATE",
                    player_slate_nodes[(slate_id, str(player_id))],
                    {"roster_ordinal": ordinal, "historical_winner": True},
                ))

    if any(
        row["workstream_namespace"] != REGISTRY_NAMESPACE for row in nodes
    ) or any(
        row["relationship_type"] in {
            "AUTHORIZES_PRODUCTION", "DEPLOYS", "MUTATES_POLICY", "AUTO_PROMOTES",
        }
        for row in edges
    ):
        raise CorpusStrategyRegistryError("registry projection authority boundary differs")
    try:
        plan = append_load_plan(parent_plan, nodes=nodes, relationships=edges)
    except CorpusRetrievalNeo4jError as exc:
        raise CorpusStrategyRegistryError(
            f"strategy registry graph structure differs: {exc}"
        ) from exc
    return StrategyRegistryBundle(
        plan=plan,
        release=release,
        release_identity=retained_release_identity,
        winner_imported=winner_count == 51,
        winner_count=winner_count,
    )


READ_ONLY_QUERIES: Final[tuple[ReadOnlyRegistryQuery, ...]] = (
    ReadOnlyRegistryQuery(
        "preset-registry",
        """
MATCH (release:CorpusRetrievalEntity)-[registers:CORPUS_RELATION]->
      (preset:CorpusRetrievalEntity)
WHERE release.workstream_namespace = $namespace
  AND release.run_id = $registry_id
  AND release.kind = 'StrategyRegistryRelease'
  AND preset.kind IN ['FillPreset', 'RetrievalPreset']
  AND registers.relationship_type IN [
    'REGISTERS_FILL_PRESET', 'REGISTERS_RETRIEVAL_PRESET'
  ]
RETURN preset.kind AS preset_kind, preset.strategy_id AS preset_id,
       preset.logical_id AS preset_version,
       preset.properties_json AS preset_record
ORDER BY preset_kind, preset_id, preset_version
""".strip(),
    ),
    ReadOnlyRegistryQuery(
        "strategy-lineage",
        """
MATCH (experiment:CorpusRetrievalEntity)-[usesSnapshot:CORPUS_RELATION]->
      (snapshot:CorpusRetrievalEntity)-[producedBy:CORPUS_RELATION]->
      (fill:CorpusRetrievalEntity)
MATCH (experiment)-[usesFill:CORPUS_RELATION]->(fill)
MATCH (experiment)-[usesRetrieval:CORPUS_RELATION]->
      (retrieval:CorpusRetrievalEntity)
WHERE experiment.workstream_namespace = $namespace
  AND experiment.run_id = $registry_id
  AND experiment.kind = 'ExperimentRun'
  AND snapshot.kind = 'CorpusSnapshot'
  AND fill.kind = 'FillPreset'
  AND retrieval.kind = 'RetrievalPreset'
  AND usesSnapshot.relationship_type = 'USES_CORPUS_SNAPSHOT'
  AND producedBy.relationship_type = 'PRODUCED_BY_FILL_PRESET'
  AND usesFill.relationship_type = 'USES_FILL_PRESET'
  AND usesRetrieval.relationship_type = 'USES_RETRIEVAL_PRESET'
RETURN fill.logical_id AS fill_preset,
       fill.properties_json AS fill_preset_record,
       snapshot.logical_id AS snapshot_id,
       snapshot.properties_json AS snapshot_record,
       retrieval.logical_id AS retrieval_preset,
       retrieval.properties_json AS retrieval_preset_record,
       experiment.logical_id AS experiment_id,
       experiment.properties_json AS experiment_record,
       experiment.slate_id AS slate_id
ORDER BY slate_id, fill_preset, snapshot_id, retrieval_preset, experiment_id
""".strip(),
    ),
    ReadOnlyRegistryQuery(
        "paired-heldout-fill-retrieval-comparison",
        """
MATCH (experiment:CorpusRetrievalEntity)-[hasSet:CORPUS_RELATION]->
      (metricSet:CorpusRetrievalEntity)-[hasMetric:CORPUS_RELATION]->
      (metric:CorpusRetrievalEntity)
MATCH (experiment)-[usesFill:CORPUS_RELATION]->(fill:CorpusRetrievalEntity)
MATCH (experiment)-[usesRetrieval:CORPUS_RELATION]->(retrieval:CorpusRetrievalEntity)
WHERE experiment.workstream_namespace = $namespace
  AND experiment.run_id = $registry_id
  AND experiment.kind = 'ExperimentRun'
  AND metricSet.kind = 'ExperimentMetricSet'
  AND metric.kind = 'Metric'
  AND hasSet.relationship_type = 'HAS_METRIC_SET'
  AND hasMetric.relationship_type = 'HAS_METRIC'
  AND usesFill.relationship_type = 'USES_FILL_PRESET'
  AND usesRetrieval.relationship_type = 'USES_RETRIEVAL_PRESET'
OPTIONAL MATCH (metric)-[paired:CORPUS_RELATION]->(baseline:CorpusRetrievalEntity)
WHERE paired.relationship_type = 'PAIRED_AGAINST_EXPERIMENT'
RETURN experiment.logical_id AS experiment_id, experiment.slate_id AS slate_id,
       fill.logical_id AS fill_preset, retrieval.logical_id AS retrieval_preset,
       metric.metric_name AS metric_name, metric.analysis_scope AS split,
       metric.metric_value AS value, baseline.logical_id AS paired_baseline,
       paired.properties_json AS pairing_law
ORDER BY slate_id, fill_preset, retrieval_preset, metric_name, split
""".strip(),
    ),
    ReadOnlyRegistryQuery(
        "active-pointer-promotion-traversal",
        """
MATCH (decision:CorpusRetrievalEntity)-[evaluates:CORPUS_RELATION]->
      (experiment:CorpusRetrievalEntity)
MATCH (experiment)-[fillRel:CORPUS_RELATION]->(fill:CorpusRetrievalEntity)
MATCH (experiment)-[retrievalRel:CORPUS_RELATION]->(retrieval:CorpusRetrievalEntity)
MATCH (decision)-[gateRel:CORPUS_RELATION]->(gateMetric:CorpusRetrievalEntity)
WHERE decision.workstream_namespace = $namespace
  AND decision.run_id = $registry_id
  AND decision.kind = 'PromotionDecision'
  AND experiment.kind = 'ExperimentRun'
  AND evaluates.relationship_type = 'EVALUATES_EXPERIMENT'
  AND fillRel.relationship_type = 'USES_FILL_PRESET'
  AND retrievalRel.relationship_type = 'USES_RETRIEVAL_PRESET'
  AND gateRel.relationship_type = 'EVALUATES_METRIC'
  AND gateMetric.kind = 'Metric'
OPTIONAL MATCH (active:CorpusRetrievalEntity)-[activated:CORPUS_RELATION]->(decision)
WHERE activated.relationship_type = 'ACTIVATED_BY_REVIEWED_DECISION'
  AND active.workstream_namespace = $namespace
  AND active.run_id = $registry_id
RETURN active.logical_id AS active_pointer, decision.logical_id AS decision,
       experiment.logical_id AS experiment, fill.logical_id AS fill_preset,
       retrieval.logical_id AS retrieval_preset,
       gateMetric.metric_name AS gate_metric,
       gateMetric.analysis_scope AS gate_scope,
       gateMetric.metric_value AS observed_value,
       decision.properties_json AS decision_record,
       active.properties_json AS active_pointer_record
ORDER BY active_pointer, gate_metric, gate_scope
""".strip(),
    ),
    ReadOnlyRegistryQuery(
        "lineup-player-team-game-traversal",
        """
MATCH (lineup:CorpusRetrievalEntity)-[rosters:CORPUS_RELATION]->
      (playerSlate:CorpusRetrievalEntity)-[represents:CORPUS_RELATION]->
      (player:CorpusRetrievalEntity)
MATCH (lineup)-[forSlate:CORPUS_RELATION]->(slate:CorpusRetrievalEntity)
MATCH (teamSlate:CorpusRetrievalEntity)-[hasPlayer:CORPUS_RELATION]->(playerSlate)
MATCH (game:CorpusRetrievalEntity)-[hasTeam:CORPUS_RELATION]->(teamSlate)
WHERE lineup.workstream_namespace = $namespace
  AND lineup.run_id = $registry_id
  AND lineup.kind IN ['Lineup', 'WinningLineup']
  AND rosters.relationship_type = 'ROSTERS_PLAYER_SLATE'
  AND represents.relationship_type = 'REPRESENTS_PLAYER'
  AND hasPlayer.relationship_type = 'HAS_PLAYER_SLATE'
  AND hasTeam.relationship_type = 'HAS_TEAM_SLATE'
  AND forSlate.relationship_type IN ['FOR_SLATE', 'WINNER_FOR_SLATE']
  AND slate.kind = 'Slate'
OPTIONAL MATCH (snapshot:CorpusRetrievalEntity)-[contains:CORPUS_RELATION]->(lineup)
WHERE contains.relationship_type = 'CONTAINS_LINEUP'
OPTIONAL MATCH (snapshot)-[produced:CORPUS_RELATION]->(fill:CorpusRetrievalEntity)
WHERE produced.relationship_type = 'PRODUCED_BY_FILL_PRESET'
RETURN lineup.logical_id AS lineup, lineup.kind AS lineup_kind,
       lineup.kind = 'WinningLineup' AS is_winner,
       lineup.metric_value_present AS score_present,
       lineup.metric_value AS score, lineup.properties_json AS lineup_record,
       slate.slate_id AS slate_id,
       player.logical_id AS player, teamSlate.logical_id AS team_slate,
       game.logical_id AS game, player.properties_json AS player_record,
       snapshot.logical_id AS corpus_snapshot,
       fill.logical_id AS producing_fill_preset
ORDER BY slate_id, lineup, corpus_snapshot, player
""".strip(),
    ),
    ReadOnlyRegistryQuery(
        "registry-firewall-census",
        """
MATCH (node:CorpusRetrievalEntity)
WHERE node.workstream_namespace = $namespace AND node.run_id = $registry_id
RETURN node.kind AS kind, count(node) AS node_count
ORDER BY kind
""".strip(),
    ),
)


def _validate_read_only_queries() -> list[dict[str, str]]:
    forbidden = re.compile(
        r"\b(?:CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|CALL|LOAD|FOREACH)\b",
        re.IGNORECASE,
    )
    rows = []
    names: set[str] = set()
    for query in READ_ONLY_QUERIES:
        if query.name in names or forbidden.search(query.cypher):
            raise CorpusStrategyRegistryError("registry query catalog is not read-only")
        names.add(query.name)
        rows.append({
            "name": query.name,
            "sha256": sha256(query.cypher.encode("utf-8")).hexdigest(),
        })
    return rows


def query_catalog() -> list[dict[str, str]]:
    """Return the immutable bounded read-only registry query catalog."""
    return _validate_read_only_queries()


def build_projection_receipt(
    bundle: StrategyRegistryBundle,
    *,
    governed_load_manifest: object,
    governed_registry_load_receipt: object,
) -> dict[str, object]:
    registry_nodes = [
        row for row in bundle.plan.nodes
        if row["workstream_namespace"] == REGISTRY_NAMESPACE
    ]
    registry_node_ids = {str(node["id"]) for node in registry_nodes}
    registry_edges = [
        row for row in bundle.plan.relationships
        if row["from_id"] in registry_node_ids
        or row["to_id"] in registry_node_ids
    ]
    body = {
        "schema_version": PROJECTION_RECEIPT_SCHEMA,
        "publication_mode": "create_once",
        "registry_release": bundle.release_identity.as_dict(),
        "governed_load_manifest": _identity_dict(
            governed_load_manifest, label="governed registry load manifest"
        ),
        "governed_registry_load_receipt": _identity_dict(
            governed_registry_load_receipt,
            label="governed strategy registry load receipt",
        ),
        "registry_id": bundle.release["registry_id"],
        "plan_sha256": bundle.plan.plan_sha256,
        "registry_node_count": len(registry_nodes),
        "registry_relationship_count": len(registry_edges),
        "kind_counts": {
            kind: sum(row["kind"] == kind for row in registry_nodes)
            for kind in sorted({str(row["kind"]) for row in registry_nodes})
        },
        "winner_imported": bundle.winner_imported,
        "winner_count": bundle.winner_count,
        "registry_namespace": REGISTRY_NAMESPACE,
        "manifest_namespace_v2_authorized": True,
        "gcs_remains_authoritative": True,
        "world_matrices_stored_in_graph": False,
        "raw_outcomes_stored_in_graph": False,
        "uses_realized_outcomes": False,
        "historical_outcome_read_authority": False,
        "outcome_namespace_read": False,
        "outcome_columns_read": [],
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
    }
    return {**body, "projection_receipt_sha256": canonical_sha256(body)}


def run_read_only_traversal_receipt(
    *,
    bundle: StrategyRegistryBundle,
    database: str,
    query_runner: QueryRunner,
    governed_load_manifest: object,
    governed_registry_load_receipt: object,
    registry_projection_receipt: object,
) -> dict[str, object]:
    _identifier(database, label="registry query database")
    catalog = _validate_read_only_queries()
    results = []
    parameters = {
        "namespace": REGISTRY_NAMESPACE,
        "registry_id": bundle.release["registry_id"],
    }
    for query in READ_ONLY_QUERIES:
        raw_rows = query_runner(database, query.cypher, parameters)
        if not isinstance(raw_rows, Sequence) or isinstance(raw_rows, (str, bytes)):
            raise CorpusStrategyRegistryError("read-only query result must be rows")
        rows = [
            dict(_mapping(raw, label=f"query {query.name} row")) for raw in raw_rows
        ]
        rows.sort(key=canonical_sha256)
        results.append({
            "name": query.name,
            "row_count": len(rows),
            "rows_sha256": canonical_sha256(rows),
        })
    body = {
        "schema_version": QUERY_RECEIPT_SCHEMA,
        "publication_mode": "create_once",
        "registry_release": bundle.release_identity.as_dict(),
        "governed_load_manifest": _identity_dict(
            governed_load_manifest, label="governed registry query manifest"
        ),
        "governed_registry_load_receipt": _identity_dict(
            governed_registry_load_receipt,
            label="governed registry query load receipt",
        ),
        "registry_projection_receipt": _identity_dict(
            registry_projection_receipt,
            label="governed registry projection receipt",
        ),
        "registry_id": bundle.release["registry_id"],
        "database": database,
        "plan_sha256": bundle.plan.plan_sha256,
        "query_catalog": catalog,
        "query_catalog_sha256": canonical_sha256(catalog),
        "results": results,
        "winner_imported": bundle.winner_imported,
        "winner_count": bundle.winner_count,
        "read_only": True,
        "graph_mutation": False,
        "automatic_promotion": False,
        "application_config_mutation": False,
        "production_policy_authority": False,
        "gcs_remains_authoritative": True,
        "raw_outcomes_stored_in_graph": False,
        "uses_realized_outcomes": False,
        "historical_outcome_read_authority": False,
        "outcome_namespace_read": False,
        "outcome_columns_read": [],
    }
    return {**body, "query_receipt_sha256": canonical_sha256(body)}


def validate_registry_receipt(
    *, bundle: StrategyRegistryBundle, receipt: object,
) -> dict[str, object]:
    """Validate a registry receipt without publishing or running a query."""
    item = dict(_mapping(receipt, label="registry receipt"))
    schema = item.get("schema_version")
    hash_field = {
        PROJECTION_RECEIPT_SCHEMA: "projection_receipt_sha256",
        QUERY_RECEIPT_SCHEMA: "query_receipt_sha256",
    }.get(schema)
    if hash_field is None:
        raise CorpusStrategyRegistryError("registry receipt schema differs")
    if (
        item.get("publication_mode") != "create_once"
        or item.get("registry_release") != bundle.release_identity.as_dict()
        or item.get("registry_id") != bundle.release["registry_id"]
        or item.get("plan_sha256") != bundle.plan.plan_sha256
        or item.get("gcs_remains_authoritative") is not True
        or item.get("automatic_promotion") is not False
        or item.get("application_config_mutation") is not False
        or item.get("production_policy_authority") is not False
        or item.get("raw_outcomes_stored_in_graph") is not False
        or item.get("uses_realized_outcomes") is not False
        or item.get("historical_outcome_read_authority") is not False
        or item.get("outcome_namespace_read") is not False
        or item.get("outcome_columns_read") != []
    ):
        raise CorpusStrategyRegistryError("registry receipt authority differs")
    _self_hash(item, field=hash_field, label="registry receipt")
    if schema == PROJECTION_RECEIPT_SCHEMA:
        expected = build_projection_receipt(
            bundle,
            governed_load_manifest=item.get("governed_load_manifest"),
            governed_registry_load_receipt=item.get(
                "governed_registry_load_receipt"
            ),
        )
        if item != expected:
            raise CorpusStrategyRegistryError("projection receipt differs")
        return item
    expected_fields = {
        "schema_version", "publication_mode", "registry_release",
        "governed_load_manifest", "governed_registry_load_receipt",
        "registry_projection_receipt", "registry_id", "database",
        "plan_sha256", "query_catalog", "query_catalog_sha256", "results",
        "winner_imported", "winner_count", "read_only", "graph_mutation",
        "automatic_promotion", "application_config_mutation",
        "production_policy_authority", "gcs_remains_authoritative",
        "raw_outcomes_stored_in_graph", "uses_realized_outcomes",
        "historical_outcome_read_authority", "outcome_namespace_read",
        "outcome_columns_read", "query_receipt_sha256",
    }
    if (
        set(item) != expected_fields
        or item.get("winner_imported") is not bundle.winner_imported
        or item.get("winner_count") != bundle.winner_count
        or item.get("read_only") is not True
        or item.get("graph_mutation") is not False
        or item.get("query_catalog") != _validate_read_only_queries()
        or item.get("query_catalog_sha256")
        != canonical_sha256(item["query_catalog"])
    ):
        raise CorpusStrategyRegistryError("query receipt differs")
    _identifier(item.get("database"), label="query receipt database")
    for field in (
        "governed_load_manifest", "governed_registry_load_receipt",
        "registry_projection_receipt",
    ):
        _identity_dict(item.get(field), label=f"query receipt {field}")
    results = _sequence(item.get("results"), label="query receipt results")
    if (
        len(results) != len(READ_ONLY_QUERIES)
        or [row.get("name") for row in results if isinstance(row, Mapping)]
        != [query.name for query in READ_ONLY_QUERIES]
    ):
        raise CorpusStrategyRegistryError("query receipt result coverage differs")
    for ordinal, raw in enumerate(results):
        row = _mapping(raw, label=f"query receipt result[{ordinal}]")
        if (
            set(row) != {"name", "row_count", "rows_sha256"}
            or type(row["row_count"]) is not int
            or row["row_count"] < 0
            or _SHA.fullmatch(str(row["rows_sha256"])) is None
        ):
            raise CorpusStrategyRegistryError("query receipt result binding differs")
    return item


def publish_registry_receipt(
    *,
    bundle: StrategyRegistryBundle,
    storage: ExactObjectStore,
    uri: str,
    receipt: Mapping[str, object],
) -> ObjectIdentity:
    """Publish an exact projector/query receipt with create-once semantics."""
    retained_uri = _string(uri, label="registry receipt URI")
    output_prefix = str(bundle.release["output_prefix"])
    if (
        not retained_uri.startswith(output_prefix)
        or not retained_uri.endswith(".json")
    ):
        raise CorpusStrategyRegistryError(
            "registry receipt URI is outside the exact output prefix"
        )
    item = validate_registry_receipt(bundle=bundle, receipt=receipt)
    schema = item.get("schema_version")
    hash_field = {
        PROJECTION_RECEIPT_SCHEMA: "projection_receipt_sha256",
        QUERY_RECEIPT_SCHEMA: "query_receipt_sha256",
    }.get(schema)
    if hash_field is None:
        raise CorpusStrategyRegistryError("registry receipt schema differs")
    if (
        item.get("publication_mode") != "create_once"
        or item.get("registry_release") != bundle.release_identity.as_dict()
        or item.get("registry_id") != bundle.release["registry_id"]
        or item.get("plan_sha256") != bundle.plan.plan_sha256
        or item.get("gcs_remains_authoritative") is not True
        or item.get("automatic_promotion") is not False
        or item.get("application_config_mutation") is not False
        or item.get("production_policy_authority") is not False
    ):
        raise CorpusStrategyRegistryError("registry receipt authority differs")
    _self_hash(item, field=hash_field, label="registry receipt")
    if schema == PROJECTION_RECEIPT_SCHEMA:
        if item != build_projection_receipt(
            bundle,
            governed_load_manifest=item.get("governed_load_manifest"),
            governed_registry_load_receipt=item.get(
                "governed_registry_load_receipt"
            ),
        ):
            raise CorpusStrategyRegistryError("projection receipt differs")
    else:
        expected_query_fields = {
            "schema_version", "publication_mode", "registry_release",
            "governed_load_manifest", "governed_registry_load_receipt",
            "registry_projection_receipt", "registry_id", "database",
            "plan_sha256", "query_catalog",
            "query_catalog_sha256", "results", "winner_imported",
            "winner_count", "read_only", "graph_mutation",
            "automatic_promotion", "application_config_mutation",
            "production_policy_authority", "gcs_remains_authoritative",
            "raw_outcomes_stored_in_graph", "uses_realized_outcomes",
            "historical_outcome_read_authority", "outcome_namespace_read",
            "outcome_columns_read",
            "query_receipt_sha256",
        }
        _identifier(item.get("database"), label="query receipt database")
        for field in (
            "governed_load_manifest", "governed_registry_load_receipt",
            "registry_projection_receipt",
        ):
            _identity_dict(item.get(field), label=f"query receipt {field}")
        if (
            set(item) != expected_query_fields
            or item.get("read_only") is not True
            or item.get("graph_mutation") is not False
            or item.get("winner_imported") is not bundle.winner_imported
            or item.get("winner_count") != bundle.winner_count
            or item.get("raw_outcomes_stored_in_graph") is not False
            or item.get("uses_realized_outcomes") is not False
            or item.get("historical_outcome_read_authority") is not False
            or item.get("outcome_namespace_read") is not False
            or item.get("outcome_columns_read") != []
            or item.get("query_catalog") != _validate_read_only_queries()
            or item.get("query_catalog_sha256")
            != canonical_sha256(item["query_catalog"])
        ):
            raise CorpusStrategyRegistryError("query receipt differs")
        results = _sequence(item.get("results"), label="query receipt results")
        if [row.get("name") for row in results if isinstance(row, Mapping)] != [
            query.name for query in READ_ONLY_QUERIES
        ] or len(results) != len(READ_ONLY_QUERIES):
            raise CorpusStrategyRegistryError("query receipt result coverage differs")
        for ordinal, raw in enumerate(results):
            row = _mapping(raw, label=f"query receipt result[{ordinal}]")
            if (
                set(row) != {"name", "row_count", "rows_sha256"}
                or type(row["row_count"]) is not int
                or row["row_count"] < 0
                or not isinstance(row["rows_sha256"], str)
                or _SHA.fullmatch(str(row["rows_sha256"])) is None
            ):
                raise CorpusStrategyRegistryError(
                    "query receipt result binding differs"
                )
    raw = canonical_json_bytes(item)
    try:
        identity = storage.publish_create_once(retained_uri, raw)
        replay = _bind_raw(
            storage.read_exact(identity), identity,
            label="published registry receipt",
        )
    except CorpusNeo4jTransportError as exc:
        raise CorpusStrategyRegistryError(
            "registry receipt create-once publication failed"
        ) from exc
    if replay != raw:
        raise CorpusStrategyRegistryError(
            "registry receipt create-once replay differs"
        )
    return identity


__all__ = [
    "ACTIVE_POINTER_SCHEMA",
    "CorpusStrategyRegistryError",
    "EFFECTIVE_PARAMETERS_SCHEMA",
    "EVIDENCE_BINDING_SCHEMA",
    "EXPERIMENT_SCHEMA",
    "FILL_PRESET_SCHEMA",
    "METRIC_SET_SCHEMA",
    "PROMOTION_SCHEMA",
    "PRE_EXECUTION_GATE_SCHEMA",
    "PROJECTION_RECEIPT_SCHEMA",
    "QUERY_RECEIPT_SCHEMA",
    "READ_ONLY_QUERIES",
    "REGISTRY_NAMESPACE",
    "RELEASE_SCHEMA",
    "RETROSPECTIVE_EFFECTIVE_PARAMETERS_SCHEMA",
    "RETROSPECTIVE_EVIDENCE_BINDING_SCHEMA",
    "RETROSPECTIVE_REGISTRATION_SCHEMA",
    "RETRIEVAL_PRESET_SCHEMA",
    "ReadOnlyRegistryQuery",
    "SNAPSHOT_SCHEMA",
    "STRUCTURE_SCHEMA",
    "StrategyRegistryBundle",
    "WINNER_AUTHORITY_SCHEMA",
    "WINNER_EVIDENCE_SCHEMA",
    "build_projection_receipt",
    "prepare_strategy_registry_plan",
    "publish_registry_receipt",
    "query_catalog",
    "run_read_only_traversal_receipt",
    "validate_registry_receipt",
]
