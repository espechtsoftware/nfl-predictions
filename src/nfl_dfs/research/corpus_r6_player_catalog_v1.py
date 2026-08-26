"""Pure, outcome-blind structural player-catalog spine for historical R6.

This module publishes no data and owns no cloud, warehouse, Git, matrix,
outcome, optimizer, graph, or deployment client.  It consumes only explicit
authority projections that an outer boundary has already validated, then
cross-binds those projections to one exact six-field player population.

The catalog population is the accepted v12 artifact-supported structural
universe.  Names and projections are deliberately absent: neither field is
part of R6 population or matchup science.  Optional display annotations must
remain a separate, non-population authority.

Every object built here is explicitly a non-authoritative projection.  This
offline seam cannot promote a caller-supplied root, even when a complete
alternate chain is internally coherent.  A later outer adapter must replay
the repository-pinned G0 lock, derive these projections from exact bodies, and
pin the final release identity before any R6 source authority can exist.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch


PLAYER_CATALOG_SCHEMA: Final = "corpus-r6-accepted-player-catalog/v1"
DERIVATION_SCHEMA: Final = "corpus-r6-player-catalog-derivation/v1"
RELEASE_SCHEMA: Final = "corpus-r6-player-catalog-release/v1"
UNIVERSE_SCOPE: Final = "exact-artifact-supported-r0-r4-player-universe"
G0_AUTHORITY_LOCK_SCHEMA: Final = "foundry-v12-g0-authority-lock/v2"
DERIVATION_ALGORITHM: Final = (
    "accepted-v12-structural-catalog-projection-v1"
)
PLAYER_ORDER_LAW: Final = "strict-ascending-player-id"
PUBLICATION_MODE: Final = "create_once"
AUTHORITY_BOUNDARY: Final = "projection-only-pending-fixed-g0-replay"
TASK_COUNT: Final = 54
LANE_TASK_COUNTS: Final = {"v12a": 28, "v12b": 26}
SUPPORTED_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "DST"})
PLAYER_FIELD_ORDER: Final = (
    "id",
    "pos",
    "team",
    "opp",
    "game_id",
    "salary",
)

FALSE_AUTHORITY_FIELDS: Final = (
    "corpus_fill_licensed",
    "corpus_retrieval_licensed",
    "decision_authority",
    "fill_authority",
    "graph_mutation_licensed",
    "historical_scoring_authority",
    "historical_scoring_licensed",
    "live_strategy_authority",
    "production_change_licensed",
    "production_policy_authority",
    "publication_authority",
    "promotion_authority",
    "r6_source_authority",
    "retrieval_authority",
)
POLICY_FIELDS: Final = frozenset({
    "outcome_columns_read",
    "uses_realized_outcomes",
    *FALSE_AUTHORITY_FIELDS,
})

TRACKED_ROOT_FIELDS: Final = frozenset({
    "g0_authority_lock_schema",
    "g0_authority_lock_relative_path",
    "g0_authority_lock_file_sha256",
    "g0_authority_lock_sha256",
    "source_commit_sha",
    "panel_object_identity",
    "panel_index_sha256",
    "accepted_slate_count",
})
MEMBER_FIELDS: Final = frozenset({
    "lane_id",
    "lane_ordinal",
    "task_ordinal",
    "source_task_ordinal",
    "task_id",
    "slate_id",
    "accepted_slate_membership_sha256",
    "task_acceptance_identity",
    "carrier_identity",
    "source_task_authority_sha256",
})
SOURCE_CATALOG_FIELDS: Final = frozenset({
    "later_source_freeze_identity",
    "later_source_freeze_manifest_sha256",
    "source_task_ordinal",
    "slate",
    "catalog_sha256",
    "catalog_player_count",
    "catalog_player_ids_sha256",
})
COMPLETION_FIELDS: Final = frozenset({
    "artifact_source_authority_completion_identity",
    "artifact_source_authority_completion_sha256",
    "later_source_freeze_identity",
    "later_source_freeze_manifest_sha256",
    "source_task_ordinal",
    "slate",
    "universe_scope",
    "task_source_authority_sha256",
    "catalog_sha256",
    "catalog_player_count",
    "catalog_player_ids_sha256",
})
CODE_IDENTITY_FIELDS: Final = frozenset({
    "source_commit_sha",
    "module_path",
    "module_sha256",
})
SLATE_FIELDS: Final = frozenset({"season", "week", "slate_id"})
OBJECT_IDENTITY_FIELDS: Final = frozenset({
    "uri", "generation", "sha256", "bytes",
})

DERIVATION_FIELDS: Final = frozenset({
    "schema_version",
    "task_id",
    "slate",
    "task_ordinal",
    "source_task_ordinal",
    "universe_scope",
    "authority_boundary",
    "tracked_root_binding",
    "accepted_member_binding",
    "source_catalog_binding",
    "artifact_source_completion_binding",
    "derivation_code_identity",
    "derivation_algorithm",
    "structural_player_fields",
    "player_order_law",
    "structural_projection_sha256",
    "player_count",
    "ordered_player_ids_sha256",
    *POLICY_FIELDS,
    "derivation_sha256",
})
PLAYER_CATALOG_FIELDS: Final = frozenset({
    "schema_version",
    "task_id",
    "slate",
    "task_ordinal",
    "source_task_ordinal",
    "universe_scope",
    "authority_boundary",
    "source_authority",
    "players",
    "player_count",
    "ordered_player_ids_sha256",
    "source_catalog_sha256",
    *POLICY_FIELDS,
    "player_catalog_sha256",
})
RELEASE_ENTRY_FIELDS: Final = frozenset({
    "source_task_ordinal",
    "task_id",
    "slate",
    "lane_id",
    "lane_ordinal",
    "task_ordinal",
    "accepted_slate_membership_sha256",
    "source_task_authority_sha256",
    "catalog_identity",
    "derivation_receipt_identity",
    "source_catalog_sha256",
    "player_count",
    "ordered_player_ids_sha256",
})
RELEASE_FIELDS: Final = frozenset({
    "schema_version",
    "release_id",
    "publication_mode",
    "universe_scope",
    "authority_boundary",
    "catalog_namespace",
    "tracked_root_binding",
    "later_source_freeze_identity",
    "later_source_freeze_manifest_sha256",
    "artifact_source_authority_completion_identity",
    "artifact_source_authority_completion_sha256",
    "derivation_code_identity",
    "task_count",
    "entries",
    "entry_manifest_sha256",
    *POLICY_FIELDS,
    "release_sha256",
})

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_COMMIT: Final = re.compile(r"[0-9a-f]{40}")
_IDENTIFIER: Final = re.compile(r"[a-z0-9][a-z0-9._:-]*")

ReadExact = Callable[[Mapping[str, object]], bytes]
PublishCreateOnce = Callable[[str, bytes], Mapping[str, object]]


class CorpusR6PlayerCatalogV1Error(ValueError):
    """A fail-closed structural catalog contract violation."""


def _fail(message: str) -> None:
    raise CorpusR6PlayerCatalogV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    """Use the existing canonical JSON law behind accepted v12 objects."""
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6PlayerCatalogV1Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping):
        _fail(f"{label} must be an object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        _fail(f"{label} fields differ")


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        _fail(f"{label} must be one nonempty canonical string")
    return value


def _identifier(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _IDENTIFIER.fullmatch(result) is None:
        _fail(f"{label} must be one canonical identifier")
    return result


def _sha(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _SHA256.fullmatch(result) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return result


def _commit(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    if _COMMIT.fullmatch(result) is None:
        _fail(f"{label} must be one full lowercase Git commit")
    return result


def _exact_int(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or isinstance(value, bool) or value < minimum:
        _fail(f"{label} must be an exact integer >= {minimum}")
    return value


def _relative_path(value: object, *, label: str) -> str:
    result = _string(value, label=label)
    pieces = result.split("/")
    if result.startswith("/") or any(piece in {"", ".", ".."} for piece in pieces):
        _fail(f"{label} must be one canonical repository-relative path")
    return result


def normalize_object_identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6PlayerCatalogV1Error(str(exc)) from exc


def _self_hash(body: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(body)
    if field in result:
        _fail(f"{field} must not be supplied before self-hashing")
    result[field] = canonical_sha256(result)
    return result


def _validate_self_hash(
    value: Mapping[str, object], *, field: str, label: str,
) -> str:
    retained = _sha(value.get(field), label=f"{label}.{field}")
    unhashed = {key: item for key, item in value.items() if key != field}
    if retained != canonical_sha256(unhashed):
        _fail(f"{label} self-hash differs")
    return retained


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
    differing = [
        field for field in FALSE_AUTHORITY_FIELDS if value.get(field) is not False
    ]
    if differing:
        _fail(f"{label} carries non-false downstream authorities {differing}")


def expected_slate_for_source_task(source_task_ordinal: int) -> dict[str, object]:
    ordinal = _exact_int(
        source_task_ordinal, label="source task ordinal", minimum=0
    )
    if ordinal >= TASK_COUNT:
        _fail("source task ordinal is outside the frozen 54-slate lattice")
    season = 2023 + ordinal // 18
    week = ordinal % 18 + 1
    return {
        "season": season,
        "week": week,
        "slate_id": f"{season}-w{week:02d}",
    }


def task_id_for_source_task(source_task_ordinal: int) -> str:
    slate = expected_slate_for_source_task(source_task_ordinal)
    return f"slate-{slate['season']}-w{slate['week']}"


def expected_lane_for_source_task(
    source_task_ordinal: int,
) -> dict[str, object]:
    """Return the frozen v12 lane/task projection for source ordinal 0..53."""
    ordinal = _exact_int(
        source_task_ordinal, label="source task ordinal", minimum=0
    )
    expected_slate_for_source_task(ordinal)
    if ordinal < LANE_TASK_COUNTS["v12a"]:
        return {
            "lane_id": "v12a",
            "lane_ordinal": 0,
            "task_ordinal": ordinal,
        }
    return {
        "lane_id": "v12b",
        "lane_ordinal": 1,
        "task_ordinal": ordinal - LANE_TASK_COUNTS["v12a"],
    }


def _normalize_slate(
    value: object, *, source_task_ordinal: int, label: str,
) -> dict[str, object]:
    item = _mapping(value, label=label)
    _exact_keys(item, SLATE_FIELDS, label=label)
    expected = expected_slate_for_source_task(source_task_ordinal)
    normalized = {
        "season": _exact_int(item["season"], label=f"{label}.season", minimum=2023),
        "week": _exact_int(item["week"], label=f"{label}.week", minimum=1),
        "slate_id": _identifier(item["slate_id"], label=f"{label}.slate_id"),
    }
    if normalized != expected:
        _fail(f"{label} differs from the frozen source-task lattice")
    return normalized


def normalize_tracked_root_binding(value: object) -> dict[str, object]:
    item = _mapping(value, label="tracked root binding")
    _exact_keys(item, TRACKED_ROOT_FIELDS, label="tracked root binding")
    result = {
        "g0_authority_lock_schema": _string(
            item["g0_authority_lock_schema"], label="G0 authority-lock schema"
        ),
        "g0_authority_lock_relative_path": _relative_path(
            item["g0_authority_lock_relative_path"],
            label="G0 authority-lock relative path",
        ),
        "g0_authority_lock_file_sha256": _sha(
            item["g0_authority_lock_file_sha256"],
            label="G0 authority-lock file SHA",
        ),
        "g0_authority_lock_sha256": _sha(
            item["g0_authority_lock_sha256"],
            label="G0 authority-lock internal SHA",
        ),
        "source_commit_sha": _commit(
            item["source_commit_sha"], label="tracked root source commit"
        ),
        "panel_object_identity": normalize_object_identity(
            item["panel_object_identity"], label="tracked root panel identity"
        ),
        "panel_index_sha256": _sha(
            item["panel_index_sha256"], label="tracked root panel-index SHA"
        ),
        "accepted_slate_count": _exact_int(
            item["accepted_slate_count"],
            label="tracked root accepted slate count",
            minimum=1,
        ),
    }
    if (
        result["g0_authority_lock_schema"] != G0_AUTHORITY_LOCK_SCHEMA
        or result["accepted_slate_count"] != TASK_COUNT
    ):
        _fail("tracked root is not the frozen 54-slate G0 authority")
    return result


def normalize_code_identity(value: object) -> dict[str, str]:
    item = _mapping(value, label="derivation code identity")
    _exact_keys(item, CODE_IDENTITY_FIELDS, label="derivation code identity")
    return {
        "source_commit_sha": _commit(
            item["source_commit_sha"], label="derivation source commit"
        ),
        "module_path": _relative_path(
            item["module_path"], label="derivation module path"
        ),
        "module_sha256": _sha(
            item["module_sha256"], label="derivation module SHA"
        ),
    }


def normalize_member_binding(value: object) -> dict[str, object]:
    item = _mapping(value, label="accepted member binding")
    _exact_keys(item, MEMBER_FIELDS, label="accepted member binding")
    source_ordinal = _exact_int(
        item["source_task_ordinal"], label="member source task ordinal"
    )
    expected_slate = expected_slate_for_source_task(source_ordinal)
    lane_id = _identifier(item["lane_id"], label="member lane ID")
    lane_ordinal = _exact_int(item["lane_ordinal"], label="member lane ordinal")
    if lane_id not in LANE_TASK_COUNTS or lane_ordinal != (
        0 if lane_id == "v12a" else 1
    ):
        _fail("accepted member lane identity differs")
    task_ordinal = _exact_int(item["task_ordinal"], label="member task ordinal")
    expected_lane = expected_lane_for_source_task(source_ordinal)
    if (
        task_ordinal >= LANE_TASK_COUNTS[lane_id]
        or {
            "lane_id": lane_id,
            "lane_ordinal": lane_ordinal,
            "task_ordinal": task_ordinal,
        }
        != expected_lane
    ):
        _fail("accepted member lane/task differs from its source ordinal")
    result = {
        "lane_id": lane_id,
        "lane_ordinal": lane_ordinal,
        "task_ordinal": task_ordinal,
        "source_task_ordinal": source_ordinal,
        "task_id": _identifier(item["task_id"], label="member task ID"),
        "slate_id": _identifier(item["slate_id"], label="member slate ID"),
        "accepted_slate_membership_sha256": _sha(
            item["accepted_slate_membership_sha256"],
            label="accepted membership SHA",
        ),
        "task_acceptance_identity": normalize_object_identity(
            item["task_acceptance_identity"], label="member task acceptance"
        ),
        "carrier_identity": normalize_object_identity(
            item["carrier_identity"], label="member carrier"
        ),
        "source_task_authority_sha256": _sha(
            item["source_task_authority_sha256"],
            label="member source-task authority SHA",
        ),
    }
    if (
        result["task_id"] != task_id_for_source_task(source_ordinal)
        or result["slate_id"] != expected_slate["slate_id"]
    ):
        _fail("accepted member task/slate differs from its source ordinal")
    return result


def normalize_structural_players(value: object) -> list[dict[str, object]]:
    rows = _sequence(value, label="structural players")
    normalized: list[dict[str, object]] = []
    player_ids: list[str] = []
    for offset, raw in enumerate(rows):
        item = _mapping(raw, label=f"structural player[{offset}]")
        _exact_keys(
            item, frozenset(PLAYER_FIELD_ORDER), label=f"structural player[{offset}]"
        )
        player_id = _string(item["id"], label=f"structural player[{offset}].id")
        position = _string(
            item["pos"], label=f"structural player[{offset}].pos"
        )
        team = _string(item["team"], label=f"structural player[{offset}].team")
        opponent = _string(
            item["opp"], label=f"structural player[{offset}].opp"
        )
        if position not in SUPPORTED_POSITIONS or team == opponent:
            _fail(f"structural player[{offset}] position/team context differs")
        normalized.append({
            "id": player_id,
            "pos": position,
            "team": team,
            "opp": opponent,
            "game_id": _string(
                item["game_id"], label=f"structural player[{offset}].game_id"
            ),
            "salary": _exact_int(
                item["salary"], label=f"structural player[{offset}].salary"
            ),
        })
        player_ids.append(player_id)
    if (
        not normalized
        or player_ids != sorted(player_ids)
        or len(player_ids) != len(set(player_ids))
    ):
        _fail("structural players must be nonempty, unique, and ID-sorted")
    return normalized


def _player_hashes(players: Sequence[Mapping[str, object]]) -> dict[str, object]:
    normalized = normalize_structural_players(players)
    player_ids = [str(player["id"]) for player in normalized]
    return {
        "players": normalized,
        "player_count": len(normalized),
        "ordered_player_ids_sha256": canonical_sha256(player_ids),
        "structural_projection_sha256": canonical_sha256(normalized),
    }


def normalize_source_catalog_binding(value: object) -> dict[str, object]:
    item = _mapping(value, label="source catalog binding")
    _exact_keys(item, SOURCE_CATALOG_FIELDS, label="source catalog binding")
    source_ordinal = _exact_int(
        item["source_task_ordinal"], label="source catalog task ordinal"
    )
    result = {
        "later_source_freeze_identity": normalize_object_identity(
            item["later_source_freeze_identity"],
            label="later-source freeze identity",
        ),
        "later_source_freeze_manifest_sha256": _sha(
            item["later_source_freeze_manifest_sha256"],
            label="later-source internal freeze SHA",
        ),
        "source_task_ordinal": source_ordinal,
        "slate": _normalize_slate(
            item["slate"], source_task_ordinal=source_ordinal, label="source slate"
        ),
        "catalog_sha256": _sha(
            item["catalog_sha256"], label="source catalog SHA"
        ),
        "catalog_player_count": _exact_int(
            item["catalog_player_count"],
            label="source catalog player count",
            minimum=1,
        ),
        "catalog_player_ids_sha256": _sha(
            item["catalog_player_ids_sha256"],
            label="source catalog player-ID SHA",
        ),
    }
    if (
        result["later_source_freeze_manifest_sha256"]
        == result["later_source_freeze_identity"]["sha256"]
    ):
        _fail("later-source internal and object hashes must not be conflated")
    return result


def normalize_completion_binding(value: object) -> dict[str, object]:
    item = _mapping(value, label="artifact-source completion binding")
    _exact_keys(item, COMPLETION_FIELDS, label="artifact-source completion binding")
    source_ordinal = _exact_int(
        item["source_task_ordinal"], label="completion source task ordinal"
    )
    result = {
        "artifact_source_authority_completion_identity": normalize_object_identity(
            item["artifact_source_authority_completion_identity"],
            label="artifact-source completion identity",
        ),
        "artifact_source_authority_completion_sha256": _sha(
            item["artifact_source_authority_completion_sha256"],
            label="artifact-source internal completion SHA",
        ),
        "later_source_freeze_identity": normalize_object_identity(
            item["later_source_freeze_identity"],
            label="completion later-source identity",
        ),
        "later_source_freeze_manifest_sha256": _sha(
            item["later_source_freeze_manifest_sha256"],
            label="completion later-source internal SHA",
        ),
        "source_task_ordinal": source_ordinal,
        "slate": _normalize_slate(
            item["slate"],
            source_task_ordinal=source_ordinal,
            label="completion slate",
        ),
        "universe_scope": _string(
            item["universe_scope"], label="completion universe scope"
        ),
        "task_source_authority_sha256": _sha(
            item["task_source_authority_sha256"],
            label="completion task-source authority SHA",
        ),
        "catalog_sha256": _sha(
            item["catalog_sha256"], label="completion catalog SHA"
        ),
        "catalog_player_count": _exact_int(
            item["catalog_player_count"],
            label="completion catalog player count",
            minimum=1,
        ),
        "catalog_player_ids_sha256": _sha(
            item["catalog_player_ids_sha256"],
            label="completion catalog player-ID SHA",
        ),
    }
    if (
        result["universe_scope"] != UNIVERSE_SCOPE
        or result["artifact_source_authority_completion_sha256"]
        == result["artifact_source_authority_completion_identity"]["sha256"]
        or result["later_source_freeze_manifest_sha256"]
        == result["later_source_freeze_identity"]["sha256"]
    ):
        _fail("artifact-source completion identity/scope differs")
    return result


def _validate_authority_chain(
    *,
    tracked_root: Mapping[str, object],
    member: Mapping[str, object],
    source: Mapping[str, object],
    completion: Mapping[str, object],
    player_hashes: Mapping[str, object] | None = None,
) -> None:
    if tracked_root["accepted_slate_count"] != TASK_COUNT:
        _fail("tracked root accepted-slate count differs")
    source_ordinal = member["source_task_ordinal"]
    catalog_tuple = (
        source["catalog_sha256"],
        source["catalog_player_count"],
        source["catalog_player_ids_sha256"],
    )
    completion_catalog_tuple = (
        completion["catalog_sha256"],
        completion["catalog_player_count"],
        completion["catalog_player_ids_sha256"],
    )
    if (
        source["source_task_ordinal"] != source_ordinal
        or completion["source_task_ordinal"] != source_ordinal
        or source["slate"] != completion["slate"]
        or source["slate"]["slate_id"] != member["slate_id"]
        or source["later_source_freeze_identity"]
        != completion["later_source_freeze_identity"]
        or source["later_source_freeze_manifest_sha256"]
        != completion["later_source_freeze_manifest_sha256"]
        or member["source_task_authority_sha256"]
        != completion["task_source_authority_sha256"]
        or catalog_tuple != completion_catalog_tuple
    ):
        _fail("tracked member/source/completion authority chain differs")
    if player_hashes is not None and catalog_tuple != (
        player_hashes["structural_projection_sha256"],
        player_hashes["player_count"],
        player_hashes["ordered_player_ids_sha256"],
    ):
        _fail("structural players differ from source/completion catalog authority")


def build_derivation_receipt_v1(
    *,
    tracked_root_binding: Mapping[str, object],
    accepted_member_binding: Mapping[str, object],
    source_catalog_binding: Mapping[str, object],
    artifact_source_completion_binding: Mapping[str, object],
    structural_players: Sequence[Mapping[str, object]],
    derivation_code_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build one self-hashed derivation from already-validated authority facts."""
    root = normalize_tracked_root_binding(tracked_root_binding)
    member = normalize_member_binding(accepted_member_binding)
    source = normalize_source_catalog_binding(source_catalog_binding)
    completion = normalize_completion_binding(artifact_source_completion_binding)
    code = normalize_code_identity(derivation_code_identity)
    hashes = _player_hashes(structural_players)
    _validate_authority_chain(
        tracked_root=root,
        member=member,
        source=source,
        completion=completion,
        player_hashes=hashes,
    )
    source_ordinal = int(member["source_task_ordinal"])
    body: dict[str, object] = {
        "schema_version": DERIVATION_SCHEMA,
        "task_id": member["task_id"],
        "slate": source["slate"],
        "task_ordinal": member["task_ordinal"],
        "source_task_ordinal": source_ordinal,
        "universe_scope": UNIVERSE_SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "tracked_root_binding": root,
        "accepted_member_binding": member,
        "source_catalog_binding": source,
        "artifact_source_completion_binding": completion,
        "derivation_code_identity": code,
        "derivation_algorithm": DERIVATION_ALGORITHM,
        "structural_player_fields": list(PLAYER_FIELD_ORDER),
        "player_order_law": PLAYER_ORDER_LAW,
        "structural_projection_sha256": hashes[
            "structural_projection_sha256"
        ],
        "player_count": hashes["player_count"],
        "ordered_player_ids_sha256": hashes["ordered_player_ids_sha256"],
        **_policy(),
    }
    return _self_hash(body, field="derivation_sha256")


def validate_derivation_receipt_v1(
    value: object,
    *,
    expected_tracked_root_binding: Mapping[str, object] | None = None,
    expected_member_binding: Mapping[str, object] | None = None,
    expected_source_catalog_binding: Mapping[str, object] | None = None,
    expected_completion_binding: Mapping[str, object] | None = None,
    expected_derivation_code_identity: Mapping[str, object] | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="catalog derivation receipt")
    _exact_keys(item, DERIVATION_FIELDS, label="catalog derivation receipt")
    retained_hash = _validate_self_hash(
        item, field="derivation_sha256", label="catalog derivation receipt"
    )
    _validate_policy(item, label="catalog derivation receipt")
    if (
        item["schema_version"] != DERIVATION_SCHEMA
        or item["universe_scope"] != UNIVERSE_SCOPE
        or item["authority_boundary"] != AUTHORITY_BOUNDARY
        or item["derivation_algorithm"] != DERIVATION_ALGORITHM
        or item["structural_player_fields"] != list(PLAYER_FIELD_ORDER)
        or item["player_order_law"] != PLAYER_ORDER_LAW
    ):
        _fail("catalog derivation fixed law differs")
    root = normalize_tracked_root_binding(item["tracked_root_binding"])
    member = normalize_member_binding(item["accepted_member_binding"])
    source = normalize_source_catalog_binding(item["source_catalog_binding"])
    completion = normalize_completion_binding(
        item["artifact_source_completion_binding"]
    )
    code = normalize_code_identity(item["derivation_code_identity"])
    structural_sha = _sha(
        item["structural_projection_sha256"],
        label="derivation structural projection SHA",
    )
    player_count = _exact_int(
        item["player_count"], label="derivation player count", minimum=1
    )
    player_ids_sha = _sha(
        item["ordered_player_ids_sha256"],
        label="derivation ordered-player-ID SHA",
    )
    _validate_authority_chain(
        tracked_root=root,
        member=member,
        source=source,
        completion=completion,
    )
    if (
        item["task_id"] != member["task_id"]
        or item["slate"] != source["slate"]
        or item["task_ordinal"] != member["task_ordinal"]
        or item["source_task_ordinal"] != member["source_task_ordinal"]
        or structural_sha != source["catalog_sha256"]
        or player_count != source["catalog_player_count"]
        or player_ids_sha != source["catalog_player_ids_sha256"]
    ):
        _fail("catalog derivation projection/task binding differs")
    if expected_tracked_root_binding is not None and root != (
        normalize_tracked_root_binding(expected_tracked_root_binding)
    ):
        _fail("catalog derivation differs from the expected tracked root")
    if expected_member_binding is not None and member != normalize_member_binding(
        expected_member_binding
    ):
        _fail("catalog derivation differs from the expected accepted member")
    if expected_source_catalog_binding is not None and source != (
        normalize_source_catalog_binding(expected_source_catalog_binding)
    ):
        _fail("catalog derivation differs from the expected source catalog")
    if expected_completion_binding is not None and completion != (
        normalize_completion_binding(expected_completion_binding)
    ):
        _fail("catalog derivation differs from the expected source completion")
    if expected_derivation_code_identity is not None and code != (
        normalize_code_identity(expected_derivation_code_identity)
    ):
        _fail("catalog derivation differs from the expected code identity")
    normalized = {
        "schema_version": DERIVATION_SCHEMA,
        "task_id": member["task_id"],
        "slate": source["slate"],
        "task_ordinal": member["task_ordinal"],
        "source_task_ordinal": member["source_task_ordinal"],
        "universe_scope": UNIVERSE_SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "tracked_root_binding": root,
        "accepted_member_binding": member,
        "source_catalog_binding": source,
        "artifact_source_completion_binding": completion,
        "derivation_code_identity": code,
        "derivation_algorithm": DERIVATION_ALGORITHM,
        "structural_player_fields": list(PLAYER_FIELD_ORDER),
        "player_order_law": PLAYER_ORDER_LAW,
        "structural_projection_sha256": structural_sha,
        "player_count": player_count,
        "ordered_player_ids_sha256": player_ids_sha,
        **_policy(),
        "derivation_sha256": retained_hash,
    }
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("catalog derivation canonical replay differs")
    return normalized


def _bind_body_to_identity(
    body: Mapping[str, object], identity: Mapping[str, object], *, label: str,
) -> dict[str, object]:
    normalized = normalize_object_identity(identity, label=f"{label} identity")
    raw = canonical_json_bytes(body)
    if (
        len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        _fail(f"{label} body differs from its exact object identity")
    return normalized


def build_player_catalog_v1(
    *,
    derivation_receipt: Mapping[str, object],
    derivation_receipt_identity: Mapping[str, object],
    structural_players: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    derivation = validate_derivation_receipt_v1(derivation_receipt)
    authority_identity = _bind_body_to_identity(
        derivation,
        derivation_receipt_identity,
        label="catalog derivation receipt",
    )
    hashes = _player_hashes(structural_players)
    if (
        hashes["structural_projection_sha256"]
        != derivation["structural_projection_sha256"]
        or hashes["player_count"] != derivation["player_count"]
        or hashes["ordered_player_ids_sha256"]
        != derivation["ordered_player_ids_sha256"]
    ):
        _fail("catalog players differ from their derivation receipt")
    body: dict[str, object] = {
        "schema_version": PLAYER_CATALOG_SCHEMA,
        "task_id": derivation["task_id"],
        "slate": derivation["slate"],
        "task_ordinal": derivation["task_ordinal"],
        "source_task_ordinal": derivation["source_task_ordinal"],
        "universe_scope": UNIVERSE_SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_authority": authority_identity,
        "players": hashes["players"],
        "player_count": hashes["player_count"],
        "ordered_player_ids_sha256": hashes["ordered_player_ids_sha256"],
        "source_catalog_sha256": hashes["structural_projection_sha256"],
        **_policy(),
    }
    return _self_hash(body, field="player_catalog_sha256")


def validate_player_catalog_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="R6 player catalog")
    _exact_keys(item, PLAYER_CATALOG_FIELDS, label="R6 player catalog")
    retained_hash = _validate_self_hash(
        item, field="player_catalog_sha256", label="R6 player catalog"
    )
    _validate_policy(item, label="R6 player catalog")
    source_ordinal = _exact_int(
        item["source_task_ordinal"], label="catalog source task ordinal"
    )
    slate = _normalize_slate(
        item["slate"], source_task_ordinal=source_ordinal, label="catalog slate"
    )
    task_ordinal = _exact_int(
        item["task_ordinal"], label="catalog task ordinal"
    )
    retained_player_count = _exact_int(
        item["player_count"], label="catalog player count", minimum=1
    )
    hashes = _player_hashes(_sequence(item["players"], label="catalog players"))
    source_authority = normalize_object_identity(
        item["source_authority"], label="catalog source authority"
    )
    source_catalog_sha = _sha(
        item["source_catalog_sha256"], label="catalog source structural SHA"
    )
    if (
        item["schema_version"] != PLAYER_CATALOG_SCHEMA
        or item["universe_scope"] != UNIVERSE_SCOPE
        or item["authority_boundary"] != AUTHORITY_BOUNDARY
        or item["task_id"] != task_id_for_source_task(source_ordinal)
        or retained_player_count != hashes["player_count"]
        or item["ordered_player_ids_sha256"]
        != hashes["ordered_player_ids_sha256"]
        or source_catalog_sha != hashes["structural_projection_sha256"]
    ):
        _fail("R6 player catalog population/task binding differs")
    normalized = {
        "schema_version": PLAYER_CATALOG_SCHEMA,
        "task_id": task_id_for_source_task(source_ordinal),
        "slate": slate,
        "task_ordinal": task_ordinal,
        "source_task_ordinal": source_ordinal,
        "universe_scope": UNIVERSE_SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "source_authority": source_authority,
        "players": hashes["players"],
        "player_count": hashes["player_count"],
        "ordered_player_ids_sha256": hashes["ordered_player_ids_sha256"],
        "source_catalog_sha256": source_catalog_sha,
        **_policy(),
        "player_catalog_sha256": retained_hash,
    }
    if canonical_json_bytes(normalized) != canonical_json_bytes(item):
        _fail("R6 player catalog canonical replay differs")
    return normalized


def _read_exact_object(
    identity: Mapping[str, object], *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    normalized = normalize_object_identity(identity, label=f"{label} identity")
    try:
        raw = read_exact(normalized)
    except Exception as exc:
        raise CorpusR6PlayerCatalogV1Error(f"{label} exact read failed") from exc
    if (
        type(raw) is not bytes
        or len(raw) != normalized["bytes"]
        or sha256(raw).hexdigest() != normalized["sha256"]
    ):
        _fail(f"{label} exact content identity differs")
    try:
        parsed = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6PlayerCatalogV1Error(str(exc)) from exc
    return normalized, _mapping(parsed, label=label)


def reopen_player_catalog_v1(
    *,
    player_catalog_identity: Mapping[str, object],
    expected_tracked_root_binding: Mapping[str, object],
    expected_member_binding: Mapping[str, object],
    expected_source_catalog_binding: Mapping[str, object],
    expected_completion_binding: Mapping[str, object],
    expected_derivation_code_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-reopen one catalog against all externally resolved source facts.

    The expected bindings are intentionally mandatory.  An internally coherent
    receipt is not source authority unless an outer, fixed G0 replay supplied
    the exact root, member, later-source, and completion projections.
    """
    catalog_identity, raw_catalog = _read_exact_object(
        player_catalog_identity, read_exact=read_exact, label="R6 player catalog"
    )
    catalog = validate_player_catalog_v1(raw_catalog)
    receipt_identity, raw_receipt = _read_exact_object(
        _mapping(catalog["source_authority"], label="catalog source authority"),
        read_exact=read_exact,
        label="catalog derivation receipt",
    )
    derivation = validate_derivation_receipt_v1(
        raw_receipt,
        expected_tracked_root_binding=expected_tracked_root_binding,
        expected_member_binding=expected_member_binding,
        expected_source_catalog_binding=expected_source_catalog_binding,
        expected_completion_binding=expected_completion_binding,
        expected_derivation_code_identity=expected_derivation_code_identity,
    )
    if (
        catalog["task_id"] != derivation["task_id"]
        or catalog["slate"] != derivation["slate"]
        or catalog["task_ordinal"] != derivation["task_ordinal"]
        or catalog["source_task_ordinal"]
        != derivation["source_task_ordinal"]
        or catalog["source_catalog_sha256"]
        != derivation["structural_projection_sha256"]
        or catalog["player_count"] != derivation["player_count"]
        or catalog["ordered_player_ids_sha256"]
        != derivation["ordered_player_ids_sha256"]
    ):
        _fail("R6 player catalog differs from its exact derivation receipt")
    return {
        "player_catalog_identity": catalog_identity,
        "player_catalog": catalog,
        "derivation_receipt_identity": receipt_identity,
        "derivation_receipt": derivation,
    }


def _authority_object_uris(
    *,
    tracked_root: Mapping[str, object],
    members: Sequence[Mapping[str, object]],
    sources: Sequence[Mapping[str, object]],
    completions: Sequence[Mapping[str, object]],
) -> set[str]:
    roles: list[tuple[str, Mapping[str, object]]] = [
        (
            "tracked panel",
            _mapping(
                tracked_root["panel_object_identity"],
                label="tracked panel identity",
            ),
        ),
        (
            "later-source freeze",
            _mapping(
                sources[0]["later_source_freeze_identity"],
                label="later-source freeze identity",
            ),
        ),
        (
            "artifact-source completion",
            _mapping(
                completions[0][
                    "artifact_source_authority_completion_identity"
                ],
                label="artifact-source completion identity",
            ),
        ),
    ]
    for source_ordinal, member in enumerate(members):
        roles.extend((
            (
                f"task {source_ordinal} acceptance",
                _mapping(
                    member["task_acceptance_identity"],
                    label=f"task {source_ordinal} acceptance identity",
                ),
            ),
            (
                f"task {source_ordinal} carrier",
                _mapping(
                    member["carrier_identity"],
                    label=f"task {source_ordinal} carrier identity",
                ),
            ),
        ))
    uri_roles: dict[str, str] = {}
    for role, identity in roles:
        uri = str(identity["uri"])
        if uri in uri_roles:
            _fail(
                "authority object URI is reused by semantic roles "
                f"{uri_roles[uri]!r} and {role!r}"
            )
        uri_roles[uri] = role
    return set(uri_roles)


def _normalize_release_entry(
    value: object, *, expected_source_task_ordinal: int,
) -> dict[str, object]:
    item = _mapping(value, label="catalog release entry")
    _exact_keys(item, RELEASE_ENTRY_FIELDS, label="catalog release entry")
    source_ordinal = _exact_int(
        item["source_task_ordinal"], label="release source task ordinal"
    )
    if source_ordinal != expected_source_task_ordinal:
        _fail("catalog release source-task order differs")
    lane_id = _identifier(item["lane_id"], label="release lane ID")
    lane_ordinal = _exact_int(item["lane_ordinal"], label="release lane ordinal")
    task_ordinal = _exact_int(item["task_ordinal"], label="release task ordinal")
    expected_lane = expected_lane_for_source_task(source_ordinal)
    if (
        lane_id not in LANE_TASK_COUNTS
        or lane_ordinal != (0 if lane_id == "v12a" else 1)
        or task_ordinal >= LANE_TASK_COUNTS[lane_id]
        or {
            "lane_id": lane_id,
            "lane_ordinal": lane_ordinal,
            "task_ordinal": task_ordinal,
        }
        != expected_lane
    ):
        _fail("catalog release lane/task identity differs")
    task_id = _identifier(item["task_id"], label="release task ID")
    if task_id != task_id_for_source_task(source_ordinal):
        _fail("catalog release task ID differs from its source ordinal")
    return {
        "source_task_ordinal": source_ordinal,
        "task_id": task_id,
        "slate": _normalize_slate(
            item["slate"],
            source_task_ordinal=source_ordinal,
            label="release slate",
        ),
        "lane_id": lane_id,
        "lane_ordinal": lane_ordinal,
        "task_ordinal": task_ordinal,
        "accepted_slate_membership_sha256": _sha(
            item["accepted_slate_membership_sha256"],
            label="release membership SHA",
        ),
        "source_task_authority_sha256": _sha(
            item["source_task_authority_sha256"],
            label="release source-task authority SHA",
        ),
        "catalog_identity": normalize_object_identity(
            item["catalog_identity"], label="release catalog identity"
        ),
        "derivation_receipt_identity": normalize_object_identity(
            item["derivation_receipt_identity"],
            label="release derivation identity",
        ),
        "source_catalog_sha256": _sha(
            item["source_catalog_sha256"], label="release source catalog SHA"
        ),
        "player_count": _exact_int(
            item["player_count"], label="release player count", minimum=1
        ),
        "ordered_player_ids_sha256": _sha(
            item["ordered_player_ids_sha256"],
            label="release player-ID SHA",
        ),
    }


def _normalize_authority_lattice(
    *,
    expected_tracked_root_binding: Mapping[str, object],
    expected_member_bindings: Sequence[Mapping[str, object]],
    expected_source_catalog_bindings: Sequence[Mapping[str, object]],
    expected_completion_bindings: Sequence[Mapping[str, object]],
) -> tuple[
    dict[str, object],
    list[dict[str, object]],
    list[dict[str, object]],
    list[dict[str, object]],
]:
    root = normalize_tracked_root_binding(expected_tracked_root_binding)
    if not all(
        isinstance(values, Sequence) and not isinstance(values, (str, bytes))
        for values in (
            expected_member_bindings,
            expected_source_catalog_bindings,
            expected_completion_bindings,
        )
    ):
        _fail("expected authority lattice inputs must be ordered arrays")
    if not all(
        len(values) == TASK_COUNT
        for values in (
            expected_member_bindings,
            expected_source_catalog_bindings,
            expected_completion_bindings,
        )
    ):
        _fail("expected authority lattice must contain exactly 54 tasks")
    members: list[dict[str, object]] = []
    sources: list[dict[str, object]] = []
    completions: list[dict[str, object]] = []
    lane_tasks: set[tuple[object, object]] = set()
    for source_ordinal in range(TASK_COUNT):
        member = normalize_member_binding(expected_member_bindings[source_ordinal])
        source = normalize_source_catalog_binding(
            expected_source_catalog_bindings[source_ordinal]
        )
        completion = normalize_completion_binding(
            expected_completion_bindings[source_ordinal]
        )
        if any(
            value["source_task_ordinal"] != source_ordinal
            for value in (member, source, completion)
        ):
            _fail("expected authority lattice source-task order differs")
        _validate_authority_chain(
            tracked_root=root,
            member=member,
            source=source,
            completion=completion,
        )
        lane_task = (member["lane_ordinal"], member["task_ordinal"])
        if lane_task in lane_tasks:
            _fail("expected authority lattice repeats a lane task")
        lane_tasks.add(lane_task)
        members.append(member)
        sources.append(source)
        completions.append(completion)
    if len(lane_tasks) != TASK_COUNT:
        _fail("expected authority lattice lane-task coverage differs")
    common_source_identity = sources[0]["later_source_freeze_identity"]
    common_source_sha = sources[0]["later_source_freeze_manifest_sha256"]
    common_completion_identity = completions[0][
        "artifact_source_authority_completion_identity"
    ]
    common_completion_sha = completions[0][
        "artifact_source_authority_completion_sha256"
    ]
    if any(
        source["later_source_freeze_identity"] != common_source_identity
        or source["later_source_freeze_manifest_sha256"] != common_source_sha
        or completion["artifact_source_authority_completion_identity"]
        != common_completion_identity
        or completion["artifact_source_authority_completion_sha256"]
        != common_completion_sha
        for source, completion in zip(sources, completions, strict=True)
    ):
        _fail("expected authority lattice common source roots differ")
    _authority_object_uris(
        tracked_root=root,
        members=members,
        sources=sources,
        completions=completions,
    )
    return root, members, sources, completions


def build_release_v1(
    *,
    release_id: str,
    catalog_namespace: str,
    expected_tracked_root_binding: Mapping[str, object],
    expected_member_bindings: Sequence[Mapping[str, object]],
    expected_source_catalog_bindings: Sequence[Mapping[str, object]],
    expected_completion_bindings: Sequence[Mapping[str, object]],
    expected_derivation_code_identity: Mapping[str, object],
    player_catalog_identities: Sequence[Mapping[str, object]],
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build a non-authoritative projection after reopening all 54 pairs."""
    normalized_release_id = _identifier(release_id, label="catalog release ID")
    normalized_namespace = _output_prefix(catalog_namespace)
    root, members, sources, completions = _normalize_authority_lattice(
        expected_tracked_root_binding=expected_tracked_root_binding,
        expected_member_bindings=expected_member_bindings,
        expected_source_catalog_bindings=expected_source_catalog_bindings,
        expected_completion_bindings=expected_completion_bindings,
    )
    code_identity = normalize_code_identity(expected_derivation_code_identity)
    if (
        isinstance(player_catalog_identities, (str, bytes))
        or not isinstance(player_catalog_identities, Sequence)
        or len(player_catalog_identities) != TASK_COUNT
    ):
        _fail("catalog release requires exactly 54 ordered catalog identities")
    entries: list[dict[str, object]] = []
    occupied_uris = _authority_object_uris(
        tracked_root=root,
        members=members,
        sources=sources,
        completions=completions,
    )
    for source_ordinal in range(TASK_COUNT):
        reopened = reopen_player_catalog_v1(
            player_catalog_identity=player_catalog_identities[source_ordinal],
            expected_tracked_root_binding=root,
            expected_member_binding=members[source_ordinal],
            expected_source_catalog_binding=sources[source_ordinal],
            expected_completion_binding=completions[source_ordinal],
            expected_derivation_code_identity=code_identity,
            read_exact=read_exact,
        )
        catalog = _mapping(
            reopened["player_catalog"], label="reopened release catalog"
        )
        derivation = _mapping(
            reopened["derivation_receipt"], label="reopened release derivation"
        )
        member = members[source_ordinal]
        catalog_identity = normalize_object_identity(
            reopened["player_catalog_identity"], label="release catalog"
        )
        receipt_identity = normalize_object_identity(
            reopened["derivation_receipt_identity"], label="release derivation"
        )
        slate_id = str(catalog["slate"]["slate_id"])
        expected_uris = _catalog_child_uris(
            normalized_namespace,
            source_task_ordinal=source_ordinal,
            slate_id=slate_id,
        )
        if (
            catalog_identity["uri"] != expected_uris["catalog"]
            or receipt_identity["uri"] != expected_uris["derivation"]
        ):
            _fail("catalog release child URI differs from its fixed namespace")
        for identity in (catalog_identity, receipt_identity):
            uri = str(identity["uri"])
            if uri in occupied_uris:
                _fail("catalog release object URI repeats")
            occupied_uris.add(uri)
        entries.append({
            "source_task_ordinal": source_ordinal,
            "task_id": catalog["task_id"],
            "slate": catalog["slate"],
            "lane_id": member["lane_id"],
            "lane_ordinal": member["lane_ordinal"],
            "task_ordinal": member["task_ordinal"],
            "accepted_slate_membership_sha256": member[
                "accepted_slate_membership_sha256"
            ],
            "source_task_authority_sha256": member[
                "source_task_authority_sha256"
            ],
            "catalog_identity": catalog_identity,
            "derivation_receipt_identity": receipt_identity,
            "source_catalog_sha256": catalog["source_catalog_sha256"],
            "player_count": catalog["player_count"],
            "ordered_player_ids_sha256": catalog[
                "ordered_player_ids_sha256"
            ],
        })
        if derivation["source_task_ordinal"] != source_ordinal:
            _fail("reopened derivation order differs during release")
    body: dict[str, object] = {
        "schema_version": RELEASE_SCHEMA,
        "release_id": normalized_release_id,
        "publication_mode": PUBLICATION_MODE,
        "universe_scope": UNIVERSE_SCOPE,
        "authority_boundary": AUTHORITY_BOUNDARY,
        "catalog_namespace": normalized_namespace,
        "tracked_root_binding": root,
        "later_source_freeze_identity": sources[0][
            "later_source_freeze_identity"
        ],
        "later_source_freeze_manifest_sha256": sources[0][
            "later_source_freeze_manifest_sha256"
        ],
        "artifact_source_authority_completion_identity": completions[0][
            "artifact_source_authority_completion_identity"
        ],
        "artifact_source_authority_completion_sha256": completions[0][
            "artifact_source_authority_completion_sha256"
        ],
        "derivation_code_identity": code_identity,
        "task_count": TASK_COUNT,
        "entries": entries,
        "entry_manifest_sha256": canonical_sha256(entries),
        **_policy(),
    }
    return _self_hash(body, field="release_sha256")


def validate_release_v1(
    value: object,
    *,
    expected_tracked_root_binding: Mapping[str, object] | None = None,
    expected_catalog_namespace: str | None = None,
) -> dict[str, object]:
    item = _mapping(value, label="catalog release")
    _exact_keys(item, RELEASE_FIELDS, label="catalog release")
    retained_hash = _validate_self_hash(
        item, field="release_sha256", label="catalog release"
    )
    _validate_policy(item, label="catalog release")
    root = normalize_tracked_root_binding(item["tracked_root_binding"])
    namespace = _output_prefix(item["catalog_namespace"])
    if expected_tracked_root_binding is not None and root != (
        normalize_tracked_root_binding(expected_tracked_root_binding)
    ):
        _fail("catalog release differs from the expected tracked root")
    if expected_catalog_namespace is not None and namespace != _output_prefix(
        expected_catalog_namespace
    ):
        _fail("catalog release differs from the expected namespace")
    source_identity = normalize_object_identity(
        item["later_source_freeze_identity"], label="release later-source identity"
    )
    source_sha = _sha(
        item["later_source_freeze_manifest_sha256"],
        label="release later-source internal SHA",
    )
    completion_identity = normalize_object_identity(
        item["artifact_source_authority_completion_identity"],
        label="release artifact-source completion identity",
    )
    completion_sha = _sha(
        item["artifact_source_authority_completion_sha256"],
        label="release artifact-source internal SHA",
    )
    code_identity = normalize_code_identity(item["derivation_code_identity"])
    if source_sha == source_identity["sha256"] or (
        completion_sha == completion_identity["sha256"]
    ):
        _fail("catalog release internal/object hash layers are conflated")
    raw_entries = _sequence(item["entries"], label="catalog release entries")
    task_count = _exact_int(
        item["task_count"], label="catalog release task count", minimum=1
    )
    if len(raw_entries) != TASK_COUNT or task_count != TASK_COUNT:
        _fail("catalog release must contain exactly 54 tasks")
    entries = [
        _normalize_release_entry(value, expected_source_task_ordinal=ordinal)
        for ordinal, value in enumerate(raw_entries)
    ]
    lane_tasks = [(entry["lane_ordinal"], entry["task_ordinal"]) for entry in entries]
    object_uris = [
        str(entry[field]["uri"])
        for entry in entries
        for field in ("catalog_identity", "derivation_receipt_identity")
    ]
    for entry in entries:
        expected_uris = _catalog_child_uris(
            namespace,
            source_task_ordinal=int(entry["source_task_ordinal"]),
            slate_id=str(entry["slate"]["slate_id"]),
        )
        if (
            entry["catalog_identity"]["uri"] != expected_uris["catalog"]
            or entry["derivation_receipt_identity"]["uri"]
            != expected_uris["derivation"]
        ):
            _fail("catalog release child URI differs from its fixed namespace")
    root_uris = {
        str(root["panel_object_identity"]["uri"]),
        str(source_identity["uri"]),
        str(completion_identity["uri"]),
    }
    if (
        len(root_uris) != 3
        or len(lane_tasks) != len(set(lane_tasks))
        or len(object_uris) != len(set(object_uris))
        or not root_uris.isdisjoint(object_uris)
        or item["entry_manifest_sha256"] != canonical_sha256(entries)
    ):
        _fail("catalog release entry coverage/hash differs")
    normalized = {
        "schema_version": RELEASE_SCHEMA,
        "release_id": _identifier(item["release_id"], label="catalog release ID"),
        "publication_mode": item["publication_mode"],
        "universe_scope": item["universe_scope"],
        "authority_boundary": item["authority_boundary"],
        "catalog_namespace": namespace,
        "tracked_root_binding": root,
        "later_source_freeze_identity": source_identity,
        "later_source_freeze_manifest_sha256": source_sha,
        "artifact_source_authority_completion_identity": completion_identity,
        "artifact_source_authority_completion_sha256": completion_sha,
        "derivation_code_identity": code_identity,
        "task_count": TASK_COUNT,
        "entries": entries,
        "entry_manifest_sha256": canonical_sha256(entries),
        **_policy(),
        "release_sha256": retained_hash,
    }
    if (
        normalized["publication_mode"] != PUBLICATION_MODE
        or normalized["universe_scope"] != UNIVERSE_SCOPE
        or normalized["authority_boundary"] != AUTHORITY_BOUNDARY
        or canonical_json_bytes(normalized) != canonical_json_bytes(item)
    ):
        _fail("catalog release fixed law/canonical replay differs")
    return normalized


def reopen_release_v1(
    *,
    release_identity: Mapping[str, object],
    expected_catalog_namespace: str,
    expected_tracked_root_binding: Mapping[str, object],
    expected_member_bindings: Sequence[Mapping[str, object]],
    expected_source_catalog_bindings: Sequence[Mapping[str, object]],
    expected_completion_bindings: Sequence[Mapping[str, object]],
    expected_derivation_code_identity: Mapping[str, object],
    read_exact: ReadExact,
) -> dict[str, object]:
    namespace = _output_prefix(expected_catalog_namespace)
    normalized_identity, raw_release = _read_exact_object(
        release_identity, read_exact=read_exact, label="catalog release"
    )
    release = validate_release_v1(
        raw_release,
        expected_tracked_root_binding=expected_tracked_root_binding,
        expected_catalog_namespace=namespace,
    )
    if normalized_identity["uri"] != f"{namespace}catalog-release.json":
        _fail("catalog release identity differs from its fixed namespace")
    entries = _sequence(release["entries"], label="catalog release entries")
    catalog_identities = [
        _mapping(entry, label="catalog release entry")["catalog_identity"]
        for entry in entries
    ]
    rebuilt = build_release_v1(
        release_id=str(release["release_id"]),
        catalog_namespace=namespace,
        expected_tracked_root_binding=expected_tracked_root_binding,
        expected_member_bindings=expected_member_bindings,
        expected_source_catalog_bindings=expected_source_catalog_bindings,
        expected_completion_bindings=expected_completion_bindings,
        expected_derivation_code_identity=expected_derivation_code_identity,
        player_catalog_identities=catalog_identities,
        read_exact=read_exact,
    )
    if canonical_json_bytes(rebuilt) != canonical_json_bytes(release):
        _fail("catalog release differs from exact catalog/derivation replay")
    return {
        "release_identity": normalized_identity,
        "release": release,
    }


def _output_prefix(value: object) -> str:
    prefix = _string(value, label="catalog output prefix")
    tail = prefix.removeprefix("gs://")
    bucket, separator, object_name = tail.partition("/")
    object_segments = object_name.removesuffix("/").split("/")
    if (
        not prefix.startswith("gs://")
        or not bucket
        or not separator
        or not object_name
        or not prefix.endswith("/")
        or "//" in object_name
        or any(segment in {"", ".", ".."} for segment in object_segments)
    ):
        _fail("catalog output prefix must be one canonical GCS prefix")
    return prefix


def _catalog_child_uris(
    output_prefix: str,
    *,
    source_task_ordinal: int,
    slate_id: str,
) -> dict[str, str]:
    prefix = _output_prefix(output_prefix)
    ordinal = _exact_int(
        source_task_ordinal, label="catalog child source ordinal"
    )
    expected_slate = expected_slate_for_source_task(ordinal)
    normalized_slate_id = _identifier(slate_id, label="catalog child slate ID")
    if normalized_slate_id != expected_slate["slate_id"]:
        _fail("catalog child slate differs from its source ordinal")
    task_prefix = f"{prefix}tasks/{ordinal:04d}-{normalized_slate_id}/"
    return {
        "derivation": f"{task_prefix}catalog-derivation-receipt.json",
        "catalog": f"{task_prefix}player-catalog.json",
    }


def _publish_and_reopen(
    *,
    uri: str,
    body: Mapping[str, object],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    label: str,
) -> dict[str, object]:
    """Create or resume an immutable object and exact-reopen its generation.

    The injected publisher must use create-if-absent semantics.  On an
    occupied URI it may return the retained identity only after proving that
    generation's bytes are identical to ``body``.  This function then exact-
    reopens the returned generation and independently verifies its bytes.
    """
    raw = canonical_json_bytes(body)
    try:
        retained = publish_create_once(uri, raw)
    except Exception as exc:
        raise CorpusR6PlayerCatalogV1Error(
            f"{label} create-once publication failed"
        ) from exc
    identity = normalize_object_identity(retained, label=f"{label} identity")
    if identity["uri"] != uri:
        _fail(f"{label} publisher returned a different URI")
    reopened_identity, reopened = _read_exact_object(
        identity, read_exact=read_exact, label=label
    )
    if (
        reopened_identity != identity
        or canonical_json_bytes(reopened) != raw
    ):
        _fail(f"{label} create-once exact reopen differs")
    return identity


def publish_catalog_pair_create_once_v1(
    *,
    output_prefix: str,
    derivation_receipt: Mapping[str, object],
    structural_players: Sequence[Mapping[str, object]],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    request_authoritative_publication: bool = False,
) -> dict[str, object]:
    """Publish a resumable, explicitly non-authoritative projection pair."""
    if request_authoritative_publication is not False:
        _fail(
            "authoritative catalog publication requires a separately pinned "
            "fixed-G0 replay manifest"
        )
    derivation = validate_derivation_receipt_v1(derivation_receipt)
    hashes = _player_hashes(structural_players)
    if (
        hashes["structural_projection_sha256"]
        != derivation["structural_projection_sha256"]
        or hashes["player_count"] != derivation["player_count"]
        or hashes["ordered_player_ids_sha256"]
        != derivation["ordered_player_ids_sha256"]
    ):
        _fail("catalog pair preflight differs from its derivation receipt")
    source_ordinal = int(derivation["source_task_ordinal"])
    slate_id = str(_mapping(derivation["slate"], label="derivation slate")["slate_id"])
    prefix = _output_prefix(output_prefix)
    child_uris = _catalog_child_uris(
        prefix, source_task_ordinal=source_ordinal, slate_id=slate_id
    )
    receipt_identity = _publish_and_reopen(
        uri=child_uris["derivation"],
        body=derivation,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="catalog derivation receipt",
    )
    catalog = build_player_catalog_v1(
        derivation_receipt=derivation,
        derivation_receipt_identity=receipt_identity,
        structural_players=structural_players,
    )
    catalog_identity = _publish_and_reopen(
        uri=child_uris["catalog"],
        body=catalog,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="R6 player catalog",
    )
    member = _mapping(
        derivation["accepted_member_binding"], label="derivation member"
    )
    source = _mapping(
        derivation["source_catalog_binding"], label="derivation source catalog"
    )
    completion = _mapping(
        derivation["artifact_source_completion_binding"],
        label="derivation source completion",
    )
    reopen_player_catalog_v1(
        player_catalog_identity=catalog_identity,
        expected_tracked_root_binding=_mapping(
            derivation["tracked_root_binding"], label="derivation tracked root"
        ),
        expected_member_binding=member,
        expected_source_catalog_binding=source,
        expected_completion_binding=completion,
        expected_derivation_code_identity=_mapping(
            derivation["derivation_code_identity"],
            label="derivation code identity",
        ),
        read_exact=read_exact,
    )
    return {
        "derivation_receipt_identity": receipt_identity,
        "player_catalog_identity": catalog_identity,
    }


def publish_release_create_once_v1(
    *,
    output_prefix: str,
    release_id: str,
    expected_tracked_root_binding: Mapping[str, object],
    expected_member_bindings: Sequence[Mapping[str, object]],
    expected_source_catalog_bindings: Sequence[Mapping[str, object]],
    expected_completion_bindings: Sequence[Mapping[str, object]],
    expected_derivation_code_identity: Mapping[str, object],
    player_catalog_identities: Sequence[Mapping[str, object]],
    publish_create_once: PublishCreateOnce,
    read_exact: ReadExact,
    request_authoritative_publication: bool = False,
) -> dict[str, object]:
    """Publish one non-authoritative projection release after full preflight."""
    if request_authoritative_publication is not False:
        _fail(
            "authoritative release publication requires a separately pinned "
            "fixed-G0 replay manifest"
        )
    release = build_release_v1(
        release_id=release_id,
        catalog_namespace=output_prefix,
        expected_tracked_root_binding=expected_tracked_root_binding,
        expected_member_bindings=expected_member_bindings,
        expected_source_catalog_bindings=expected_source_catalog_bindings,
        expected_completion_bindings=expected_completion_bindings,
        expected_derivation_code_identity=expected_derivation_code_identity,
        player_catalog_identities=player_catalog_identities,
        read_exact=read_exact,
    )
    identity = _publish_and_reopen(
        uri=f"{_output_prefix(output_prefix)}catalog-release.json",
        body=release,
        publish_create_once=publish_create_once,
        read_exact=read_exact,
        label="catalog release",
    )
    reopen_release_v1(
        release_identity=identity,
        expected_catalog_namespace=output_prefix,
        expected_tracked_root_binding=expected_tracked_root_binding,
        expected_member_bindings=expected_member_bindings,
        expected_source_catalog_bindings=expected_source_catalog_bindings,
        expected_completion_bindings=expected_completion_bindings,
        expected_derivation_code_identity=expected_derivation_code_identity,
        read_exact=read_exact,
    )
    return identity


__all__ = [
    "AUTHORITY_BOUNDARY",
    "COMPLETION_FIELDS",
    "DERIVATION_ALGORITHM",
    "DERIVATION_SCHEMA",
    "FALSE_AUTHORITY_FIELDS",
    "G0_AUTHORITY_LOCK_SCHEMA",
    "LANE_TASK_COUNTS",
    "MEMBER_FIELDS",
    "PLAYER_CATALOG_SCHEMA",
    "PLAYER_FIELD_ORDER",
    "PLAYER_ORDER_LAW",
    "PUBLICATION_MODE",
    "RELEASE_SCHEMA",
    "SOURCE_CATALOG_FIELDS",
    "SUPPORTED_POSITIONS",
    "TASK_COUNT",
    "UNIVERSE_SCOPE",
    "CorpusR6PlayerCatalogV1Error",
    "PublishCreateOnce",
    "ReadExact",
    "build_derivation_receipt_v1",
    "build_player_catalog_v1",
    "build_release_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "expected_lane_for_source_task",
    "expected_slate_for_source_task",
    "normalize_code_identity",
    "normalize_completion_binding",
    "normalize_member_binding",
    "normalize_object_identity",
    "normalize_source_catalog_binding",
    "normalize_structural_players",
    "normalize_tracked_root_binding",
    "publish_catalog_pair_create_once_v1",
    "publish_release_create_once_v1",
    "reopen_player_catalog_v1",
    "reopen_release_v1",
    "task_id_for_source_task",
    "validate_derivation_receipt_v1",
    "validate_player_catalog_v1",
    "validate_release_v1",
]
