"""Post-freeze realized-outcome boundary for the R6 full-union panel.

The structural freeze deliberately stops before opening historical outcomes.
This module defines the next pure boundary:

1. exact-reopen the complete 54/54 structural-freeze root;
2. exact-reopen every slate leaf/result and the common later-source freeze;
3. derive the required player set from each slate's distinct
   ``all-block-final-fit`` candidate union;
4. bind the result-side R0--R4 world identities to the later-source artifact
   receipts and map skill players to player keys and DSTs to team keys; and
5. accept one exact, ordered, integer-micro-DK row for every projected key.

There is no warehouse, object-store, lease, query, graph, or publication
callback here.  A transport may use these contracts only after the panel root
exists.  Merely importing this module cannot open a realized outcome.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import re
from typing import Final

from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as freeze
from nfl_dfs.research import corpus_realized_grading as grading
from nfl_dfs.research import lr8_later_period_source as later_source
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_batch_evidence_contract import MICRO_DK_PER_POINT


OUTCOME_KEY_PROJECTION_SCHEMA: Final = (
    "corpus-r6-full-union-outcome-key-projection/v1"
)
ACTUAL_ROOT_SMOKE_RECEIPT_SCHEMA: Final = (
    "corpus-r6-full-union-actual-root-smoke-receipt/v1"
)
REALIZED_SOURCE_SCHEMA: Final = "corpus-r6-full-union-realized-source/v1"
OUTCOME_SNAPSHOT_SCHEMA: Final = "corpus-r6-full-union-outcome-snapshot/v1"
AUTHORITATIVE_SLATE_COUNT: Final = freeze.AUTHORITATIVE_SLATE_COUNT
ALL_BLOCK_FIT_SCOPE_ID: Final = freeze.FIT_SCOPE_IDS[-1]
WORLD_BLOCKS: Final = tuple(rw.WORLD_BLOCKS)
WORLD_ROLES: Final = tuple(
    f"world_artifact_{block.lower()}" for block in WORLD_BLOCKS
)
ALLOWED_POSITIONS: Final = frozenset({"QB", "RB", "WR", "TE", "DST"})

_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_COMMIT = re.compile(r"^[0-9a-f]{40}$")
_IMAGE = re.compile(r"^.+@sha256:[0-9a-f]{64}$")
_SLATE_ID = re.compile(r"^20[0-9]{2}-w(?:0[1-9]|1[0-8])$")

_KEY_FIELDS: Final = frozenset({
    "source_ordinal", "season", "week", "slate_id", "player_id",
    "position", "team", "source_kind", "source_key",
})
_SLATE_PROJECTION_FIELDS: Final = frozenset({
    "source_ordinal", "season", "week", "slate_id",
    "slate_freeze_identity", "task_result_identity",
    "population_descriptor_sha256", "all_block_lineup_count",
    "ordered_lineup_ids_sha256", "ordered_rosters_sha256",
    "ordered_population_sha256", "later_source_catalog_sha256",
    "r0_r4_world_artifact_identities",
    "r0_r4_world_artifact_identity_set_sha256",
    "required_player_count", "required_player_ids_sha256",
    "outcome_key_count", "outcome_keys_sha256",
    "slate_projection_sha256",
})
_PROJECTION_FIELDS: Final = frozenset({
    "schema_version", "panel_freeze_identity", "panel_freeze_sha256",
    "execution_manifest_sha256", "panel_index_identity",
    "panel_index_sha256", "later_source_freeze_identity",
    "later_source_freeze_sha256", "fit_scope_id", "world_blocks",
    "source_slate_count", "slates", "slates_sha256",
    "all_block_union_lineup_count", "required_player_count",
    "outcome_key_count", "outcome_keys", "outcome_keys_sha256",
    "complete", "uses_realized_outcomes", "historical_scoring_licensed",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "outcome_key_projection_sha256",
})
_SMOKE_SLATE_FIELDS: Final = frozenset({
    "source_ordinal", "slate_id", "slate_freeze_identity",
    "slate_freeze_sha256", "task_result_identity", "task_result_sha256",
    "population_descriptor_sha256", "final_fit_candidate_count",
    "r0_r4_scope_count", "r0_r4_book_count", "final_fit_book_count",
    "origin_evidence_count", "smoke_slate_replay_sha256",
})
_SMOKE_RECEIPT_FIELDS: Final = frozenset({
    "schema_version", "panel_freeze_identity", "panel_freeze_sha256",
    "outcome_key_projection_identity", "outcome_key_projection_sha256",
    "freeze_source_commit_sha", "freeze_immutable_image",
    "reviewed_source_commit_sha", "runtime_immutable_image",
    "snapshot_module_sha256", "snapshot_cli_sha256",
    "snapshot_test_sha256", "snapshot_cli_test_sha256",
    "source_slate_count", "slate_replays", "slate_replays_sha256",
    "root_leaf_result_replay_count", "r0_r4_scope_count",
    "final_fit_scope_count", "r0_r4_book_count", "final_fit_book_count",
    "rank_80_book_count", "r0_r4_candidate_count",
    "final_fit_candidate_count", "origin_evidence_count",
    "all_block_union_lineup_count", "required_player_count",
    "outcome_key_count", "root_leaf_result_replay_complete",
    "r0_r4_books_nonempty", "r0_r4_origins_nonempty",
    "r0_r4_origins_contained_in_training_blocks",
    "fold_populations_contained_in_final_fit",
    "books_contained_in_scope_and_final_fit", "uses_realized_outcomes",
    "historical_scoring_licensed", "historical_outcome_lease_acquired",
    "bigquery_client_constructed", "query_executed",
    "lineup_scoring_performed", "graph_mutation_licensed",
    "production_change_licensed", "promotion_authority",
    "decision_authority", "actual_root_smoke_receipt_sha256",
})
_SOURCE_ROW_FIELDS: Final = frozenset({
    "source_ordinal", "season", "week", "slate_id", "source_kind",
    "source_key", "player_id", "realized_score_micro",
})
_REGISTERED_MICRO_ROW_FIELDS: Final = frozenset({
    "season", "week", "source_kind", "source_key", "realized_score_micro",
})
_SOURCE_FIELDS: Final = frozenset({
    "schema_version", "outcome_key_projection_identity",
    "outcome_key_projection_sha256", "panel_freeze_identity",
    "panel_freeze_sha256", "later_source_freeze_identity",
    "later_source_freeze_sha256", "score_unit", "micro_dk_per_point",
    "row_fields", "row_count", "row_keys_sha256", "rows_sha256", "rows",
    "exact_union_coverage", "lineup_scoring_performed",
    "full_field_standings_included", "payout_ladder_included",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "realized_source_sha256",
})
_SNAPSHOT_ROW_FIELDS: Final = frozenset({
    "source_ordinal", "season", "week", "slate_id", "player_id",
    "realized_score_micro",
})
_SNAPSHOT_FIELDS: Final = frozenset({
    "schema_version", "outcome_key_projection_identity",
    "outcome_key_projection_sha256", "panel_freeze_identity",
    "panel_freeze_sha256", "later_source_freeze_identity",
    "later_source_freeze_sha256", "realized_source_identity",
    "realized_source_sha256", "score_unit", "micro_dk_per_point",
    "row_count", "row_keys_sha256", "rows_sha256", "rows",
    "exact_union_coverage", "lineup_scoring_performed",
    "full_field_standings_included", "payout_ladder_included",
    "graph_mutation_licensed", "production_change_licensed",
    "decision_authority", "outcome_snapshot_sha256",
})

ReadExact = Callable[[Mapping[str, object]], bytes]


class CorpusR6FullUnionOutcomeSnapshotV1Error(ValueError):
    """The post-freeze player/DST outcome boundary failed closed."""


@dataclass(frozen=True, slots=True)
class OutcomeKeyV1:
    source_ordinal: int
    season: int
    week: int
    slate_id: str
    player_id: str
    position: str
    team: str
    source_kind: str
    source_key: str


def _fail(message: str) -> None:
    raise CorpusR6FullUnionOutcomeSnapshotV1Error(message)


def canonical_json_bytes(value: object) -> bytes:
    try:
        return batch.canonical_json_bytes(value)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionOutcomeSnapshotV1Error(str(exc)) from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        _fail(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        _fail(f"{label} must be a canonical nonempty string")
    return value


def _integer(
    value: object, *, label: str, minimum: int | None = None,
) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        suffix = "" if minimum is None else f" >= {minimum}"
        _fail(f"{label} must be an exact integer{suffix}")
    return value


def _digest(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _commit(value: object, *, label: str) -> str:
    if type(value) is not str or _COMMIT.fullmatch(value) is None:
        _fail(f"{label} must be one lowercase 40-character Git commit")
    return value


def _immutable_image(value: object, *, label: str) -> str:
    if type(value) is not str or _IMAGE.fullmatch(value) is None:
        _fail(f"{label} must be one immutable image digest URI")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    try:
        return batch.normalize_object_identity(value, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionOutcomeSnapshotV1Error(str(exc)) from exc


def _json_identity(
    value: object, identity: object, *, label: str,
) -> dict[str, object]:
    try:
        return batch.validate_json_identity(value, identity, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionOutcomeSnapshotV1Error(str(exc)) from exc


def _self_hash(value: Mapping[str, object], *, field: str, label: str) -> str:
    retained = _digest(value.get(field), label=f"{label}.{field}")
    if canonical_sha256({key: item for key, item in value.items() if key != field}) != retained:
        _fail(f"{label} self-hash differs")
    return retained


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    result = dict(value)
    result[field] = canonical_sha256(result)
    return result


def _exact_read_json(
    identity_value: object, *, read_exact: ReadExact, label: str,
) -> tuple[dict[str, object], dict[str, object]]:
    identity = _identity(identity_value, label=f"{label} identity")
    raw = read_exact(identity)
    if (
        type(raw) is not bytes
        or len(raw) != identity["bytes"]
        or sha256(raw).hexdigest() != identity["sha256"]
    ):
        _fail(f"{label} exact-read content identity differs")
    try:
        value = batch.parse_canonical_json_bytes(raw, label=label)
    except batch.CorpusParametricBatchError as exc:
        raise CorpusR6FullUnionOutcomeSnapshotV1Error(str(exc)) from exc
    return _mapping(value, label=label), identity


def _object_identity_from_receipt(
    value: object, *, label: str,
) -> dict[str, object]:
    receipt = _mapping(value, label=label)
    try:
        projection = {
            key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")
        }
    except KeyError as exc:
        raise CorpusR6FullUnionOutcomeSnapshotV1Error(
            f"{label} lacks a content identity"
        ) from exc
    return _identity(projection, label=label)


def _normalized_later_source(
    *, root: Mapping[str, object], read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    expected_identity = _identity(
        root.get("later_source_freeze_identity"),
        label="panel-root later-source identity",
    )
    raw_source, retained_identity = _exact_read_json(
        expected_identity, read_exact=read_exact, label="later-source freeze"
    )
    internal_sha = _digest(
        raw_source.get("freeze_sha256"), label="later-source internal SHA"
    )
    try:
        source = later_source.validate_source_freeze(
            raw_source, expected_freeze_sha256=internal_sha
        )
    except later_source.LR8LaterSourceError as exc:
        raise CorpusR6FullUnionOutcomeSnapshotV1Error(
            "later-source freeze exact replay differs"
        ) from exc
    _json_identity(source, retained_identity, label="later-source freeze")
    if (
        retained_identity != expected_identity
        or source.get("slate_count") != AUTHORITATIVE_SLATE_COUNT
        or source.get("world_blocks") != list(WORLD_BLOCKS)
        or source.get("uses_realized_outcomes") is not False
        or source.get("historical_scoring_licensed") is not False
    ):
        _fail("later-source freeze boundary differs")
    return source, retained_identity


def _slate_key(value: object, *, label: str) -> tuple[int, int, str]:
    slate = _mapping(value, label=label)
    season = _integer(slate.get("season"), label=f"{label}.season", minimum=2000)
    week = _integer(slate.get("week"), label=f"{label}.week", minimum=1)
    slate_id = _string(slate.get("slate_id"), label=f"{label}.slate_id")
    if week > 18 or _SLATE_ID.fullmatch(slate_id) is None or slate_id != f"{season}-w{week:02d}":
        _fail(f"{label} identity differs")
    return season, week, slate_id


def _candidate_union(
    *, result: Mapping[str, object], leaf: Mapping[str, object], source_ordinal: int,
) -> tuple[list[dict[str, object]], set[str]]:
    surface = _mapping(result.get("full_union_surface"), label="full-union surface")
    scopes = _sequence(surface.get("scopes"), label="full-union scopes")
    if len(scopes) != freeze.SCOPE_COUNT:
        _fail("full-union scope census differs")
    final_scope = _mapping(scopes[-1], label="all-block-final-fit scope")
    candidate_view = _mapping(
        final_scope.get("candidate_view"), label="all-block candidate view"
    )
    candidates = [
        _mapping(value, label=f"all-block candidate[{ordinal}]")
        for ordinal, value in enumerate(_sequence(
            candidate_view.get("eligible_candidates"),
            label="all-block eligible candidates",
        ))
    ]
    if (
        final_scope.get("fit_scope_id") != ALL_BLOCK_FIT_SCOPE_ID
        or final_scope.get("training_blocks") != list(WORLD_BLOCKS)
        or final_scope.get("heldout_block") is not None
        or candidate_view.get("fit_scope_id") != ALL_BLOCK_FIT_SCOPE_ID
        or candidate_view.get("training_blocks") != list(WORLD_BLOCKS)
        or candidate_view.get("heldout_block") is not None
        or candidate_view.get("excluded_count") != 0
        or candidate_view.get("eligible_count") != len(candidates)
        or len(candidates) < freeze.lane.ENTRY_BUDGET
    ):
        _fail(f"slate[{source_ordinal}] all-block-final-fit population differs")

    population: list[dict[str, object]] = []
    required_players: set[str] = set()
    observed_lineups: set[str] = set()
    for candidate_ordinal, candidate in enumerate(candidates):
        lineup_id = _string(
            candidate.get("lineup_id"),
            label=f"candidate[{candidate_ordinal}].lineup_id",
        )
        roster = [
            _string(player_id, label="candidate roster player ID")
            for player_id in _sequence(
                candidate.get("roster_player_ids"), label="candidate roster"
            )
        ]
        origin_blocks = _sequence(
            candidate.get("training_origin_blocks"),
            label="candidate training origin blocks",
        )
        occurrence_counts = _mapping(
            candidate.get("training_occurrence_counts_by_block"),
            label="candidate occurrence counts",
        )
        expected_origins = [
            block for block in WORLD_BLOCKS if occurrence_counts.get(block)
        ]
        if (
            lineup_id in observed_lineups
            or len(roster) != rw.ROSTER_SIZE
            or roster != sorted(roster)
            or len(roster) != len(set(roster))
            or set(occurrence_counts) != set(WORLD_BLOCKS)
            or any(type(count) is not int or count < 0 for count in occurrence_counts.values())
            or origin_blocks != expected_origins
            or not origin_blocks
            or any(block not in WORLD_BLOCKS for block in origin_blocks)
            or candidate.get("training_occurrence_count")
            != sum(int(count) for count in occurrence_counts.values())
        ):
            _fail(
                f"slate[{source_ordinal}] candidate R0-R4 containment differs"
            )
        observed_lineups.add(lineup_id)
        required_players.update(roster)
        population.append({
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
        })

    descriptor = _mapping(
        leaf.get("all_block_union"), label="all-block population descriptor"
    )
    lineup_ids = [row["lineup_id"] for row in population]
    rosters = [row["roster_player_ids"] for row in population]
    if (
        descriptor.get("fit_scope_id") != ALL_BLOCK_FIT_SCOPE_ID
        or descriptor.get("lineup_count") != len(population)
        or descriptor.get("ordered_lineup_ids_sha256")
        != canonical_sha256(lineup_ids)
        or descriptor.get("ordered_rosters_sha256") != canonical_sha256(rosters)
        or descriptor.get("ordered_population_sha256") != canonical_sha256(population)
        or descriptor.get("eligible_equals_admitted") is not True
        or descriptor.get("excluded_count") != 0
        or not required_players
    ):
        _fail(f"slate[{source_ordinal}] all-block population binding differs")
    return population, required_players


def _world_identity_lattice(
    *,
    result: Mapping[str, object],
    source_slate: Mapping[str, object],
    source_ordinal: int,
) -> dict[str, dict[str, object]]:
    result_worlds = _mapping(
        result.get("world_artifact_identities"), label="result world identities"
    )
    artifacts = _sequence(
        source_slate.get("artifact_receipts"),
        label="later-source artifact receipts",
    )
    if set(result_worlds) != set(WORLD_ROLES) or len(artifacts) != len(WORLD_BLOCKS):
        _fail(f"slate[{source_ordinal}] R0-R4 artifact lattice differs")
    normalized: dict[str, dict[str, object]] = {}
    for role, block, raw_artifact in zip(
        WORLD_ROLES, WORLD_BLOCKS, artifacts, strict=True
    ):
        artifact = _mapping(
            raw_artifact, label=f"later-source {block} artifact receipt"
        )
        if (
            artifact.get("block") != block
            or artifact.get("season") != source_slate.get("season")
            or artifact.get("week") != source_slate.get("week")
        ):
            _fail(f"slate[{source_ordinal}] {block} receipt containment differs")
        source_identity = _object_identity_from_receipt(
            artifact, label=f"later-source {block} artifact identity"
        )
        result_identity = _identity(
            result_worlds[role], label=f"result {block} artifact identity"
        )
        if result_identity != source_identity:
            _fail(
                f"slate[{source_ordinal}] result/later-source {block} identity differs"
            )
        normalized[role] = result_identity
    return normalized


def _catalog_outcome_keys(
    *,
    source_ordinal: int,
    slate_key: tuple[int, int, str],
    required_players: set[str],
    source_slate: Mapping[str, object],
) -> list[OutcomeKeyV1]:
    season, week, slate_id = slate_key
    catalog_rows = _sequence(
        source_slate.get("catalog"), label="later-source player catalog"
    )
    catalog: dict[str, tuple[str, str]] = {}
    observed_order: list[str] = []
    for raw_player in catalog_rows:
        player = _mapping(raw_player, label="later-source catalog player")
        player_id = _string(player.get("id"), label="catalog player ID")
        position = _string(player.get("pos"), label="catalog player position").upper()
        team = _string(player.get("team"), label="catalog player team").upper()
        if position not in ALLOWED_POSITIONS:
            _fail(f"slate[{source_ordinal}] catalog position differs")
        observed_order.append(player_id)
        catalog[player_id] = (position, team)
    if (
        observed_order != sorted(observed_order)
        or len(catalog) != len(observed_order)
        or not required_players <= set(catalog)
    ):
        _fail(
            f"slate[{source_ordinal}] all-block players are not exactly covered "
            "by the frozen catalog"
        )
    result: list[OutcomeKeyV1] = []
    for player_id in sorted(required_players):
        position, team = catalog[player_id]
        source_kind = "dst" if position == "DST" else "skill"
        source_key = team if source_kind == "dst" else player_id
        result.append(OutcomeKeyV1(
            source_ordinal=source_ordinal,
            season=season,
            week=week,
            slate_id=slate_id,
            player_id=player_id,
            position=position,
            team=team,
            source_kind=source_kind,
            source_key=source_key,
        ))
    return sorted(
        result,
        key=lambda row: (row.season, row.week, row.source_kind, row.source_key),
    )


def _key_payload(value: OutcomeKeyV1) -> dict[str, object]:
    return {
        "source_ordinal": value.source_ordinal,
        "season": value.season,
        "week": value.week,
        "slate_id": value.slate_id,
        "player_id": value.player_id,
        "position": value.position,
        "team": value.team,
        "source_kind": value.source_kind,
        "source_key": value.source_key,
    }


def project_required_outcome_keys_v1(
    *, panel_freeze_identity: object, read_exact: ReadExact,
) -> dict[str, object]:
    """Exact-replay the 54/54 root and freeze its all-block score-key union."""
    try:
        root, retained_root_identity = freeze.reopen_panel_freeze_v1(
            panel_freeze_identity, read_exact=read_exact
        )
    except freeze.CorpusR6FullUnionPanelFreezeV1Error as exc:
        raise CorpusR6FullUnionOutcomeSnapshotV1Error(
            "54/54 structural-freeze root exact replay differs"
        ) from exc
    if (
        root.get("schema_version") != freeze.PANEL_FREEZE_SCHEMA
        or root.get("source_slate_count") != AUTHORITATIVE_SLATE_COUNT
        or root.get("complete") is not True
        or root.get("structural_freeze_only") is not True
        or root.get("outcome_key_projection_inputs_frozen") is not True
        or root.get("uses_realized_outcomes") is not False
        or root.get("historical_scoring_licensed") is not False
    ):
        _fail("54/54 structural-freeze root authority boundary differs")

    source, retained_source_identity = _normalized_later_source(
        root=root, read_exact=read_exact
    )
    root_rows = _sequence(root.get("slate_freezes"), label="panel slate freezes")
    source_slates = _sequence(source.get("slates"), label="later-source slates")
    if not (
        len(root_rows) == len(source_slates) == AUTHORITATIVE_SLATE_COUNT
    ):
        _fail("root/later-source slate census differs")

    slate_projections: list[dict[str, object]] = []
    keys: list[OutcomeKeyV1] = []
    union_lineup_count = 0
    for source_ordinal, (raw_root_row, raw_source_slate) in enumerate(
        zip(root_rows, source_slates, strict=True)
    ):
        root_row = _mapping(
            raw_root_row, label=f"panel slate descriptor[{source_ordinal}]"
        )
        source_slate = _mapping(
            raw_source_slate, label=f"later-source slate[{source_ordinal}]"
        )
        leaf_identity = _identity(
            root_row.get("slate_freeze_identity"),
            label=f"slate[{source_ordinal}] freeze identity",
        )
        try:
            leaf, _, _, _, result, reopened_leaf_identity = (
                freeze.reopen_slate_freeze_v1(
                    leaf_identity, read_exact=read_exact
                )
            )
        except freeze.CorpusR6FullUnionPanelFreezeV1Error as exc:
            raise CorpusR6FullUnionOutcomeSnapshotV1Error(
                f"slate[{source_ordinal}] structural leaf exact replay differs"
            ) from exc
        result_identity = _identity(
            leaf.get("task_result_identity"),
            label=f"slate[{source_ordinal}] task-result identity",
        )
        if (
            reopened_leaf_identity != leaf_identity
            or leaf.get("source_ordinal") != source_ordinal
            or root_row.get("source_ordinal") != source_ordinal
            or root_row.get("slate_freeze_identity") != leaf_identity
            or root_row.get("task_result_identity") != result_identity
            or leaf.get("later_source_freeze_identity") != retained_source_identity
        ):
            _fail(f"slate[{source_ordinal}] root/leaf/result binding differs")

        surface = _mapping(result.get("full_union_surface"), label="full-union surface")
        result_slate_key = _slate_key(
            surface.get("slate"), label=f"slate[{source_ordinal}] result slate"
        )
        source_slate_key = _slate_key(
            source_slate, label=f"slate[{source_ordinal}] later-source slate"
        )
        if (
            result_slate_key != source_slate_key
            or root_row.get("slate_id") != result_slate_key[2]
            or leaf.get("slate_id") != result_slate_key[2]
        ):
            _fail(f"slate[{source_ordinal}] identity alignment differs")

        population, required_players = _candidate_union(
            result=result, leaf=leaf, source_ordinal=source_ordinal
        )
        world_identities = _world_identity_lattice(
            result=result,
            source_slate=source_slate,
            source_ordinal=source_ordinal,
        )
        slate_keys = _catalog_outcome_keys(
            source_ordinal=source_ordinal,
            slate_key=result_slate_key,
            required_players=required_players,
            source_slate=source_slate,
        )
        slate_payload = [_key_payload(value) for value in slate_keys]
        descriptor = _mapping(
            leaf.get("all_block_union"), label="all-block population descriptor"
        )
        season, week, slate_id = result_slate_key
        slate_projection = _with_hash({
            "source_ordinal": source_ordinal,
            "season": season,
            "week": week,
            "slate_id": slate_id,
            "slate_freeze_identity": leaf_identity,
            "task_result_identity": result_identity,
            "population_descriptor_sha256": descriptor[
                "population_descriptor_sha256"
            ],
            "all_block_lineup_count": len(population),
            "ordered_lineup_ids_sha256": descriptor[
                "ordered_lineup_ids_sha256"
            ],
            "ordered_rosters_sha256": descriptor["ordered_rosters_sha256"],
            "ordered_population_sha256": descriptor[
                "ordered_population_sha256"
            ],
            "later_source_catalog_sha256": source_slate["catalog_sha256"],
            "r0_r4_world_artifact_identities": world_identities,
            "r0_r4_world_artifact_identity_set_sha256": canonical_sha256(
                world_identities
            ),
            "required_player_count": len(required_players),
            "required_player_ids_sha256": canonical_sha256(
                sorted(required_players)
            ),
            "outcome_key_count": len(slate_payload),
            "outcome_keys_sha256": canonical_sha256(slate_payload),
        }, field="slate_projection_sha256")
        slate_projections.append(slate_projection)
        keys.extend(slate_keys)
        union_lineup_count += len(population)

    player_keys = [(row.source_ordinal, row.player_id) for row in keys]
    source_keys = [
        (row.season, row.week, row.source_kind, row.source_key) for row in keys
    ]
    if (
        len(player_keys) != len(set(player_keys))
        or len(source_keys) != len(set(source_keys))
        or not any(row.source_kind == "skill" for row in keys)
        or not any(row.source_kind == "dst" for row in keys)
        or union_lineup_count != root.get("union_lineup_count")
    ):
        _fail("panel player/DST outcome-key union differs")
    keys.sort(
        key=lambda row: (row.season, row.week, row.source_kind, row.source_key)
    )
    outcome_key_payload = [_key_payload(value) for value in keys]
    body: dict[str, object] = {
        "schema_version": OUTCOME_KEY_PROJECTION_SCHEMA,
        "panel_freeze_identity": retained_root_identity,
        "panel_freeze_sha256": root["panel_freeze_sha256"],
        "execution_manifest_sha256": root["execution_manifest_sha256"],
        "panel_index_identity": root["panel_index_identity"],
        "panel_index_sha256": root["panel_index_sha256"],
        "later_source_freeze_identity": retained_source_identity,
        "later_source_freeze_sha256": source["freeze_sha256"],
        "fit_scope_id": ALL_BLOCK_FIT_SCOPE_ID,
        "world_blocks": list(WORLD_BLOCKS),
        "source_slate_count": len(slate_projections),
        "slates": slate_projections,
        "slates_sha256": canonical_sha256(slate_projections),
        "all_block_union_lineup_count": union_lineup_count,
        "required_player_count": len(keys),
        "outcome_key_count": len(keys),
        "outcome_keys": outcome_key_payload,
        "outcome_keys_sha256": canonical_sha256(outcome_key_payload),
        "complete": True,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="outcome_key_projection_sha256")


def _parse_projection_keys(value: object) -> tuple[dict[str, object], tuple[OutcomeKeyV1, ...]]:
    projection = _mapping(value, label="outcome-key projection")
    _exact_keys(projection, _PROJECTION_FIELDS, label="outcome-key projection")
    _self_hash(
        projection,
        field="outcome_key_projection_sha256",
        label="outcome-key projection",
    )
    raw_slates = _sequence(projection.get("slates"), label="projection slates")
    raw_keys = _sequence(projection.get("outcome_keys"), label="projection keys")
    slates: list[dict[str, object]] = []
    for source_ordinal, raw_slate in enumerate(raw_slates):
        slate = _mapping(raw_slate, label=f"projection slate[{source_ordinal}]")
        _exact_keys(
            slate, _SLATE_PROJECTION_FIELDS,
            label=f"projection slate[{source_ordinal}]",
        )
        _self_hash(
            slate,
            field="slate_projection_sha256",
            label=f"projection slate[{source_ordinal}]",
        )
        if slate.get("source_ordinal") != source_ordinal:
            _fail("projection slate ordinals differ")
        slates.append(slate)
    keys: list[OutcomeKeyV1] = []
    for ordinal, raw_key in enumerate(raw_keys):
        row = _mapping(raw_key, label=f"projection key[{ordinal}]")
        _exact_keys(row, _KEY_FIELDS, label=f"projection key[{ordinal}]")
        source_ordinal = _integer(
            row.get("source_ordinal"),
            label=f"projection key[{ordinal}].source_ordinal",
            minimum=0,
        )
        if source_ordinal >= len(slates):
            _fail("projection key source ordinal is outside the panel")
        season = _integer(
            row.get("season"), label="projection key season", minimum=2000
        )
        week = _integer(row.get("week"), label="projection key week", minimum=1)
        slate_id = _string(row.get("slate_id"), label="projection key slate ID")
        player_id = _string(row.get("player_id"), label="projection key player ID")
        position = _string(row.get("position"), label="projection key position")
        team = _string(row.get("team"), label="projection key team")
        source_kind = _string(
            row.get("source_kind"), label="projection key source kind"
        )
        source_key = _string(
            row.get("source_key"), label="projection key source key"
        )
        slate = slates[source_ordinal]
        if (
            position not in ALLOWED_POSITIONS
            or position != position.upper()
            or team != team.upper()
            or (source_kind == "dst") != (position == "DST")
            or source_kind not in {"skill", "dst"}
            or source_key != (team if source_kind == "dst" else player_id)
            or (season, week, slate_id)
            != (slate["season"], slate["week"], slate["slate_id"])
        ):
            _fail("projection skill/player or DST/team key law differs")
        keys.append(OutcomeKeyV1(
            source_ordinal=source_ordinal,
            season=season,
            week=week,
            slate_id=slate_id,
            player_id=player_id,
            position=position,
            team=team,
            source_kind=source_kind,
            source_key=source_key,
        ))
    expected_order = sorted(
        keys, key=lambda row: (row.season, row.week, row.source_kind, row.source_key)
    )
    player_keys = [(row.source_ordinal, row.player_id) for row in keys]
    query_keys = [
        (row.season, row.week, row.source_kind, row.source_key) for row in keys
    ]
    if (
        projection.get("schema_version") != OUTCOME_KEY_PROJECTION_SCHEMA
        or projection.get("fit_scope_id") != ALL_BLOCK_FIT_SCOPE_ID
        or projection.get("world_blocks") != list(WORLD_BLOCKS)
        or projection.get("source_slate_count") != AUTHORITATIVE_SLATE_COUNT
        or len(slates) != AUTHORITATIVE_SLATE_COUNT
        or projection.get("slates_sha256") != canonical_sha256(slates)
        or projection.get("required_player_count") != len(keys)
        or projection.get("outcome_key_count") != len(keys)
        or projection.get("outcome_keys_sha256")
        != canonical_sha256([_key_payload(value) for value in keys])
        or keys != expected_order
        or len(player_keys) != len(set(player_keys))
        or len(query_keys) != len(set(query_keys))
        or projection.get("complete") is not True
        or any(projection.get(field) is not False for field in (
            "uses_realized_outcomes", "historical_scoring_licensed",
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("outcome-key projection structure differs")
    for source_ordinal, slate in enumerate(slates):
        slate_keys = [row for row in keys if row.source_ordinal == source_ordinal]
        payload = [_key_payload(row) for row in slate_keys]
        if (
            slate["required_player_count"] != len(slate_keys)
            or slate["outcome_key_count"] != len(slate_keys)
            or slate["outcome_keys_sha256"] != canonical_sha256(payload)
            or slate["required_player_ids_sha256"]
            != canonical_sha256(sorted(row.player_id for row in slate_keys))
        ):
            _fail(f"projection slate[{source_ordinal}] key census differs")
    return projection, tuple(keys)


def validate_outcome_key_projection_v1(
    value: object,
    *,
    identity: object,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], tuple[OutcomeKeyV1, ...]]:
    """Replay a persisted projection all the way back to the exact root."""
    projection, keys = _parse_projection_keys(value)
    retained_identity = _json_identity(
        projection, identity, label="outcome-key projection identity"
    )
    expected = project_required_outcome_keys_v1(
        panel_freeze_identity=projection["panel_freeze_identity"],
        read_exact=read_exact,
    )
    if canonical_json_bytes(projection) != canonical_json_bytes(expected):
        _fail("outcome-key projection canonical replay differs")
    return projection, retained_identity, keys


def _smoke_slate_replay_v1(
    *,
    source_ordinal: int,
    root_row: Mapping[str, object],
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, int]]:
    """Replay and summarize one already-authoritative structural leaf."""
    leaf_identity = _identity(
        root_row.get("slate_freeze_identity"),
        label=f"smoke slate[{source_ordinal}] freeze identity",
    )
    try:
        leaf, _, _, _, result, retained_leaf_identity = (
            freeze.reopen_slate_freeze_v1(
                leaf_identity, read_exact=read_exact
            )
        )
    except freeze.CorpusR6FullUnionPanelFreezeV1Error as exc:
        raise CorpusR6FullUnionOutcomeSnapshotV1Error(
            f"smoke slate[{source_ordinal}] root/leaf/result replay differs"
        ) from exc
    result_identity = _identity(
        leaf.get("task_result_identity"),
        label=f"smoke slate[{source_ordinal}] result identity",
    )
    if (
        retained_leaf_identity != leaf_identity
        or root_row.get("source_ordinal") != source_ordinal
        or leaf.get("source_ordinal") != source_ordinal
        or root_row.get("slate_freeze_identity") != retained_leaf_identity
        or root_row.get("task_result_identity") != result_identity
    ):
        _fail(f"smoke slate[{source_ordinal}] root/leaf/result binding differs")

    surface = _mapping(
        result.get("full_union_surface"), label="smoke full-union surface"
    )
    scopes = [
        _mapping(value, label=f"smoke scope[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(surface.get("scopes"), label="smoke scopes")
        )
    ]
    if len(scopes) != len(WORLD_BLOCKS) + 1:
        _fail(f"smoke slate[{source_ordinal}] scope census differs")
    final_view = _mapping(
        scopes[-1].get("candidate_view"), label="smoke final candidate view"
    )
    final_candidates = [
        _mapping(value, label="smoke final candidate")
        for value in _sequence(
            final_view.get("eligible_candidates"),
            label="smoke final candidates",
        )
    ]
    final_ids = {
        _string(value.get("lineup_id"), label="smoke final lineup ID")
        for value in final_candidates
    }
    if (
        scopes[-1].get("fit_scope_id") != ALL_BLOCK_FIT_SCOPE_ID
        or scopes[-1].get("training_blocks") != list(WORLD_BLOCKS)
        or scopes[-1].get("heldout_block") is not None
        or not final_candidates
        or len(final_ids) != len(final_candidates)
    ):
        _fail(f"smoke slate[{source_ordinal}] final-fit population differs")

    r0_r4_candidates = 0
    r0_r4_books = 0
    final_books = 0
    origin_evidence = 0
    for scope_ordinal, (heldout, scope) in enumerate(
        zip([*WORLD_BLOCKS, None], scopes, strict=True)
    ):
        training_blocks = [block for block in WORLD_BLOCKS if block != heldout]
        view = _mapping(
            scope.get("candidate_view"),
            label=f"smoke scope[{scope_ordinal}] candidate view",
        )
        candidates = [
            _mapping(value, label="smoke scope candidate")
            for value in _sequence(
                view.get("eligible_candidates"), label="smoke scope candidates"
            )
        ]
        candidate_ids: set[str] = set()
        for candidate in candidates:
            lineup_id = _string(
                candidate.get("lineup_id"), label="smoke candidate lineup ID"
            )
            origins = [
                _string(value, label="smoke candidate origin")
                for value in _sequence(
                    candidate.get("training_origin_blocks"),
                    label="smoke candidate origins",
                )
            ]
            if (
                lineup_id in candidate_ids
                or not origins
                or not set(origins) <= set(training_blocks)
            ):
                _fail(
                    f"smoke slate[{source_ordinal}] R0-R4 origin containment differs"
                )
            candidate_ids.add(lineup_id)
            origin_evidence += len(origins)
        if (
            scope.get("heldout_block") != heldout
            or scope.get("training_blocks") != training_blocks
            or not candidates
            or not candidate_ids <= final_ids
        ):
            _fail(
                f"smoke slate[{source_ordinal}] fold/final containment differs"
            )
        books = [
            _mapping(value, label="smoke scope book")
            for value in _sequence(scope.get("books"), label="smoke scope books")
        ]
        if not books:
            _fail(f"smoke slate[{source_ordinal}] scope books are empty")
        for book in books:
            selected = {
                _string(value, label="smoke selected lineup ID")
                for value in _sequence(
                    book.get("selected_lineup_ids"),
                    label="smoke selected lineup IDs",
                )
            }
            if not selected or not selected <= candidate_ids or not selected <= final_ids:
                _fail(
                    f"smoke slate[{source_ordinal}] book containment differs"
                )
        if heldout is None:
            final_books += len(books)
        else:
            r0_r4_candidates += len(candidates)
            r0_r4_books += len(books)

    descriptor = _mapping(
        leaf.get("all_block_union"), label="smoke all-block descriptor"
    )
    replay = _with_hash({
        "source_ordinal": source_ordinal,
        "slate_id": _string(leaf.get("slate_id"), label="smoke slate ID"),
        "slate_freeze_identity": retained_leaf_identity,
        "slate_freeze_sha256": _digest(
            leaf.get("slate_freeze_sha256"), label="smoke slate-freeze SHA"
        ),
        "task_result_identity": result_identity,
        "task_result_sha256": _digest(
            result.get("task_result_sha256"), label="smoke task-result SHA"
        ),
        "population_descriptor_sha256": _digest(
            descriptor.get("population_descriptor_sha256"),
            label="smoke population descriptor SHA",
        ),
        "final_fit_candidate_count": len(final_candidates),
        "r0_r4_scope_count": len(WORLD_BLOCKS),
        "r0_r4_book_count": r0_r4_books,
        "final_fit_book_count": final_books,
        "origin_evidence_count": origin_evidence,
    }, field="smoke_slate_replay_sha256")
    return replay, {
        "r0_r4_candidate_count": r0_r4_candidates,
        "final_fit_candidate_count": len(final_candidates),
        "r0_r4_book_count": r0_r4_books,
        "final_fit_book_count": final_books,
        "origin_evidence_count": origin_evidence,
    }


def build_actual_root_smoke_receipt_v1(
    *,
    panel_freeze_identity: object,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    expected_reviewed_source_commit_sha: object,
    expected_runtime_immutable_image: object,
    snapshot_module_sha256: object,
    snapshot_cli_sha256: object,
    snapshot_test_sha256: object,
    snapshot_cli_test_sha256: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Prove the actual 54-slate root is ready without opening outcomes."""
    expected_root_identity = _identity(
        panel_freeze_identity, label="expected panel-freeze identity"
    )
    try:
        root, retained_root_identity = freeze.reopen_panel_freeze_v1(
            expected_root_identity, read_exact=read_exact
        )
    except freeze.CorpusR6FullUnionPanelFreezeV1Error as exc:
        raise CorpusR6FullUnionOutcomeSnapshotV1Error(
            "actual-root smoke panel replay differs"
        ) from exc
    if retained_root_identity != expected_root_identity:
        _fail("actual-root smoke did not retain the explicit panel identity")
    manifest, _, members, _ = freeze.reopen_execution_manifest_v1(
        root.get("manifest_identity"), read_exact=read_exact
    )
    projection, retained_projection_identity, keys = (
        validate_outcome_key_projection_v1(
            outcome_key_projection,
            identity=outcome_key_projection_identity,
            read_exact=read_exact,
        )
    )
    if (
        projection.get("panel_freeze_identity") != expected_root_identity
        or projection.get("panel_freeze_sha256") != root.get("panel_freeze_sha256")
    ):
        _fail("actual-root smoke projection/root binding differs")

    root_rows = [
        _mapping(value, label=f"smoke root row[{ordinal}]")
        for ordinal, value in enumerate(
            _sequence(root.get("slate_freezes"), label="smoke root rows")
        )
    ]
    if (
        root.get("complete") is not True
        or root.get("source_slate_count") != AUTHORITATIVE_SLATE_COUNT
        or len(root_rows) != AUTHORITATIVE_SLATE_COUNT
        or len(members) != AUTHORITATIVE_SLATE_COUNT
        or root.get("uses_realized_outcomes") is not False
        or root.get("historical_scoring_licensed") is not False
    ):
        _fail("actual-root smoke root completion/authority differs")
    replay_rows: list[dict[str, object]] = []
    totals = {
        "r0_r4_candidate_count": 0,
        "final_fit_candidate_count": 0,
        "r0_r4_book_count": 0,
        "final_fit_book_count": 0,
        "origin_evidence_count": 0,
    }
    for ordinal, row in enumerate(root_rows):
        replay, counts = _smoke_slate_replay_v1(
            source_ordinal=ordinal, root_row=row, read_exact=read_exact
        )
        replay_rows.append(replay)
        for field, count in counts.items():
            totals[field] += count
    rank_80_book_count = totals["r0_r4_book_count"] + totals[
        "final_fit_book_count"
    ]
    if (
        rank_80_book_count != root.get("rank_80_book_count")
        or totals["final_fit_candidate_count"]
        != root.get("union_lineup_count")
        or projection.get("all_block_union_lineup_count")
        != root.get("union_lineup_count")
        or projection.get("required_player_count") != len(keys)
        or projection.get("outcome_key_count") != len(keys)
    ):
        _fail("actual-root smoke aggregate census differs")

    body: dict[str, object] = {
        "schema_version": ACTUAL_ROOT_SMOKE_RECEIPT_SCHEMA,
        "panel_freeze_identity": retained_root_identity,
        "panel_freeze_sha256": root["panel_freeze_sha256"],
        "outcome_key_projection_identity": retained_projection_identity,
        "outcome_key_projection_sha256": projection[
            "outcome_key_projection_sha256"
        ],
        "freeze_source_commit_sha": _commit(
            manifest.get("source_commit_sha"), label="freeze source commit"
        ),
        "freeze_immutable_image": _immutable_image(
            manifest.get("immutable_image"), label="freeze immutable image"
        ),
        "reviewed_source_commit_sha": _commit(
            expected_reviewed_source_commit_sha,
            label="reviewed source commit",
        ),
        "runtime_immutable_image": _immutable_image(
            expected_runtime_immutable_image,
            label="runtime immutable image",
        ),
        "snapshot_module_sha256": _digest(
            snapshot_module_sha256, label="snapshot module SHA"
        ),
        "snapshot_cli_sha256": _digest(
            snapshot_cli_sha256, label="snapshot CLI SHA"
        ),
        "snapshot_test_sha256": _digest(
            snapshot_test_sha256, label="snapshot test SHA"
        ),
        "snapshot_cli_test_sha256": _digest(
            snapshot_cli_test_sha256, label="snapshot CLI test SHA"
        ),
        "source_slate_count": len(replay_rows),
        "slate_replays": replay_rows,
        "slate_replays_sha256": canonical_sha256(replay_rows),
        "root_leaf_result_replay_count": len(replay_rows),
        "r0_r4_scope_count": len(WORLD_BLOCKS) * len(replay_rows),
        "final_fit_scope_count": len(replay_rows),
        "r0_r4_book_count": totals["r0_r4_book_count"],
        "final_fit_book_count": totals["final_fit_book_count"],
        "rank_80_book_count": rank_80_book_count,
        "r0_r4_candidate_count": totals["r0_r4_candidate_count"],
        "final_fit_candidate_count": totals["final_fit_candidate_count"],
        "origin_evidence_count": totals["origin_evidence_count"],
        "all_block_union_lineup_count": projection[
            "all_block_union_lineup_count"
        ],
        "required_player_count": projection["required_player_count"],
        "outcome_key_count": projection["outcome_key_count"],
        "root_leaf_result_replay_complete": True,
        "r0_r4_books_nonempty": True,
        "r0_r4_origins_nonempty": True,
        "r0_r4_origins_contained_in_training_blocks": True,
        "fold_populations_contained_in_final_fit": True,
        "books_contained_in_scope_and_final_fit": True,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "historical_outcome_lease_acquired": False,
        "bigquery_client_constructed": False,
        "query_executed": False,
        "lineup_scoring_performed": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "promotion_authority": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="actual_root_smoke_receipt_sha256")


def validate_actual_root_smoke_receipt_v1(
    value: object,
    *,
    identity: object,
    expected_panel_freeze_identity: object,
    outcome_key_projection: object,
    expected_outcome_key_projection_identity: object,
    expected_reviewed_source_commit_sha: object,
    expected_runtime_immutable_image: object,
    expected_snapshot_module_sha256: object,
    expected_snapshot_cli_sha256: object,
    expected_snapshot_test_sha256: object,
    expected_snapshot_cli_test_sha256: object,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object]]:
    """Validate a persisted receipt against only explicit expected roots."""
    receipt = _mapping(value, label="actual-root smoke receipt")
    _exact_keys(
        receipt, _SMOKE_RECEIPT_FIELDS, label="actual-root smoke receipt"
    )
    if receipt.get("schema_version") != ACTUAL_ROOT_SMOKE_RECEIPT_SCHEMA:
        _fail("actual-root smoke receipt schema differs")
    _self_hash(
        receipt,
        field="actual_root_smoke_receipt_sha256",
        label="actual-root smoke receipt",
    )
    retained_identity = _json_identity(
        receipt, identity, label="actual-root smoke receipt identity"
    )
    expected = build_actual_root_smoke_receipt_v1(
        panel_freeze_identity=expected_panel_freeze_identity,
        outcome_key_projection=outcome_key_projection,
        outcome_key_projection_identity=(
            expected_outcome_key_projection_identity
        ),
        expected_reviewed_source_commit_sha=(
            expected_reviewed_source_commit_sha
        ),
        expected_runtime_immutable_image=expected_runtime_immutable_image,
        snapshot_module_sha256=expected_snapshot_module_sha256,
        snapshot_cli_sha256=expected_snapshot_cli_sha256,
        snapshot_test_sha256=expected_snapshot_test_sha256,
        snapshot_cli_test_sha256=expected_snapshot_cli_test_sha256,
        read_exact=read_exact,
    )
    if canonical_json_bytes(receipt) != canonical_json_bytes(expected):
        _fail("actual-root smoke receipt canonical replay differs")
    return receipt, retained_identity


def _source_row_key(value: Mapping[str, object]) -> tuple[int, int, str, str]:
    return (
        int(value["season"]), int(value["week"]),
        str(value["source_kind"]), str(value["source_key"]),
    )


def normalize_registered_integer_micro_rows_v1(
    value: object, *, outcome_keys: Sequence[OutcomeKeyV1],
) -> list[dict[str, object]]:
    """Map exact registered query keys back to source-ordinal/player rows.

    The one-query supply layer owns decimal-to-micro conversion.  This
    boundary accepts only already-converted exact Python integers and rejects
    every missing, extra, duplicate, or reordered query key.
    """
    keys = tuple(outcome_keys)
    expected: dict[tuple[int, int, str, str], OutcomeKeyV1] = {}
    expected_order: list[tuple[int, int, str, str]] = []
    player_keys: set[tuple[int, str]] = set()
    for ordinal, key in enumerate(keys):
        if not isinstance(key, OutcomeKeyV1):
            _fail(f"outcome key[{ordinal}] is not an OutcomeKeyV1")
        player_key = (key.source_ordinal, key.player_id)
        if (
            type(key.source_ordinal) is not int
            or key.source_ordinal < 0
            or key.source_ordinal >= AUTHORITATIVE_SLATE_COUNT
            or type(key.season) is not int
            or key.season < 2000
            or type(key.week) is not int
            or not 1 <= key.week <= 18
            or type(key.slate_id) is not str
            or key.slate_id != f"{key.season}-w{key.week:02d}"
            or type(key.player_id) is not str
            or not key.player_id
            or type(key.position) is not str
            or key.position not in ALLOWED_POSITIONS
            or type(key.team) is not str
            or not key.team
            or key.team != key.team.upper()
            or type(key.source_kind) is not str
            or key.source_kind not in {"skill", "dst"}
            or (key.source_kind == "dst") != (key.position == "DST")
            or type(key.source_key) is not str
            or not key.source_key
            or key.source_key
            != (key.team if key.source_kind == "dst" else key.player_id)
            or player_key in player_keys
        ):
            _fail(f"outcome key[{ordinal}] skill/player or DST/team law differs")
        player_keys.add(player_key)
        query_key = (key.season, key.week, key.source_kind, key.source_key)
        if query_key in expected:
            _fail("registered outcome-key union contains duplicates")
        expected[query_key] = key
        expected_order.append(query_key)
    if not expected or expected_order != sorted(expected):
        _fail("registered outcome-key union is empty or unordered")

    raw_rows = _sequence(value, label="registered integer-micro rows")
    observed: set[tuple[int, int, str, str]] = set()
    result: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(raw_rows):
        row = _mapping(raw_row, label=f"registered integer-micro row[{ordinal}]")
        _exact_keys(
            row,
            _REGISTERED_MICRO_ROW_FIELDS,
            label=f"registered integer-micro row[{ordinal}]",
        )
        query_key = (
            _integer(row.get("season"), label="registered row season", minimum=2000),
            _integer(row.get("week"), label="registered row week", minimum=1),
            _string(row.get("source_kind"), label="registered row source kind"),
            _string(row.get("source_key"), label="registered row source key"),
        )
        if query_key in observed:
            _fail("registered integer-micro rows contain duplicate outcome keys")
        observed.add(query_key)
        key = expected.get(query_key)
        if key is None:
            _fail("registered integer-micro rows contain extra non-union keys")
        score = _integer(
            row.get("realized_score_micro"),
            label="registered realized score micro",
        )
        if abs(score) > grading.MAX_ABS_PLAYER_SCORE_MICRO:
            _fail("registered realized score micro exceeds exact player-score bounds")
        result.append({
            "source_ordinal": key.source_ordinal,
            "season": key.season,
            "week": key.week,
            "slate_id": key.slate_id,
            "source_kind": key.source_kind,
            "source_key": key.source_key,
            "player_id": key.player_id,
            "realized_score_micro": score,
        })
    if set(expected) - observed:
        _fail("registered integer-micro rows are missing projected outcome keys")
    if observed - set(expected):
        _fail("registered integer-micro rows contain extra non-union keys")
    if [_source_row_key(row) for row in result] != expected_order:
        _fail("registered integer-micro rows are not the exact ordered key union")
    return result


def _normalize_realized_rows(
    value: object, *, outcome_keys: Sequence[OutcomeKeyV1],
) -> list[dict[str, object]]:
    raw_rows = _sequence(value, label="realized source rows")
    expected = {
        (row.season, row.week, row.source_kind, row.source_key): row
        for row in outcome_keys
    }
    observed_keys: set[tuple[int, int, str, str]] = set()
    result: list[dict[str, object]] = []
    for ordinal, raw_row in enumerate(raw_rows):
        row = _mapping(raw_row, label=f"realized source row[{ordinal}]")
        _exact_keys(
            row, _SOURCE_ROW_FIELDS, label=f"realized source row[{ordinal}]"
        )
        key = (
            _integer(row.get("season"), label="realized row season", minimum=2000),
            _integer(row.get("week"), label="realized row week", minimum=1),
            _string(row.get("source_kind"), label="realized row source kind"),
            _string(row.get("source_key"), label="realized row source key"),
        )
        if key in observed_keys:
            _fail("realized source contains duplicate outcome keys")
        observed_keys.add(key)
        expected_key = expected.get(key)
        if expected_key is None:
            _fail("realized source contains extra non-union outcome keys")
        score = _integer(
            row.get("realized_score_micro"),
            label="realized score micro",
        )
        if abs(score) > grading.MAX_ABS_PLAYER_SCORE_MICRO:
            _fail("realized score micro exceeds exact player-score bounds")
        normalized = {
            "source_ordinal": _integer(
                row.get("source_ordinal"),
                label="realized row source ordinal",
                minimum=0,
            ),
            "season": key[0],
            "week": key[1],
            "slate_id": _string(
                row.get("slate_id"), label="realized row slate ID"
            ),
            "source_kind": key[2],
            "source_key": key[3],
            "player_id": _string(
                row.get("player_id"), label="realized row player ID"
            ),
            "realized_score_micro": score,
        }
        if (
            normalized["source_ordinal"] != expected_key.source_ordinal
            or normalized["slate_id"] != expected_key.slate_id
            or normalized["player_id"] != expected_key.player_id
        ):
            _fail("realized source row differs from its projected outcome key")
        result.append(normalized)
    expected_keys = set(expected)
    missing = expected_keys - observed_keys
    if missing:
        _fail("realized source is missing projected outcome keys")
    if observed_keys - expected_keys:
        _fail("realized source contains extra non-union outcome keys")
    expected_order = sorted(expected)
    if [_source_row_key(row) for row in result] != expected_order:
        _fail("realized source rows are not the exact ordered outcome-key union")
    return result


def build_realized_source_v1(
    *,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    realized_rows: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Bind one exact integer-micro row set to the frozen key projection."""
    projection, projection_identity, keys = validate_outcome_key_projection_v1(
        outcome_key_projection,
        identity=outcome_key_projection_identity,
        read_exact=read_exact,
    )
    rows = _normalize_realized_rows(realized_rows, outcome_keys=keys)
    return _build_realized_source_from_validated_projection(
        projection=projection,
        projection_identity=projection_identity,
        rows=rows,
    )


def build_realized_source_from_registered_rows_v1(
    *,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    registered_integer_micro_rows: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Bind the registered query-key row shape without any query transport."""
    projection, projection_identity, keys = validate_outcome_key_projection_v1(
        outcome_key_projection,
        identity=outcome_key_projection_identity,
        read_exact=read_exact,
    )
    rows = normalize_registered_integer_micro_rows_v1(
        registered_integer_micro_rows, outcome_keys=keys
    )
    return _build_realized_source_from_validated_projection(
        projection=projection,
        projection_identity=projection_identity,
        rows=rows,
    )


def _build_realized_source_from_validated_projection(
    *,
    projection: Mapping[str, object],
    projection_identity: Mapping[str, object],
    rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    row_keys = [{
        "source_ordinal": row["source_ordinal"],
        "season": row["season"],
        "week": row["week"],
        "slate_id": row["slate_id"],
        "source_kind": row["source_kind"],
        "source_key": row["source_key"],
        "player_id": row["player_id"],
    } for row in rows]
    body: dict[str, object] = {
        "schema_version": REALIZED_SOURCE_SCHEMA,
        "outcome_key_projection_identity": projection_identity,
        "outcome_key_projection_sha256": projection[
            "outcome_key_projection_sha256"
        ],
        "panel_freeze_identity": projection["panel_freeze_identity"],
        "panel_freeze_sha256": projection["panel_freeze_sha256"],
        "later_source_freeze_identity": projection[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_sha256": projection[
            "later_source_freeze_sha256"
        ],
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "row_fields": sorted(_SOURCE_ROW_FIELDS),
        "row_count": len(rows),
        "row_keys_sha256": canonical_sha256(row_keys),
        "rows_sha256": canonical_sha256(rows),
        "rows": rows,
        "exact_union_coverage": True,
        "lineup_scoring_performed": False,
        "full_field_standings_included": False,
        "payout_ladder_included": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="realized_source_sha256")


def validate_realized_source_v1(
    value: object,
    *,
    identity: object,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    projection, projection_identity, keys = validate_outcome_key_projection_v1(
        outcome_key_projection,
        identity=outcome_key_projection_identity,
        read_exact=read_exact,
    )
    return _validate_realized_source_against_projection(
        value,
        identity=identity,
        projection=projection,
        projection_identity=projection_identity,
        keys=keys,
    )


def _validate_realized_source_against_projection(
    value: object,
    *,
    identity: object,
    projection: Mapping[str, object],
    projection_identity: Mapping[str, object],
    keys: Sequence[OutcomeKeyV1],
) -> tuple[dict[str, object], dict[str, object], list[dict[str, object]]]:
    """Validate a source after its exact root-bound projection is validated."""
    source = _mapping(value, label="realized source")
    _exact_keys(source, _SOURCE_FIELDS, label="realized source")
    _self_hash(source, field="realized_source_sha256", label="realized source")
    retained_identity = _json_identity(
        source, identity, label="realized source identity"
    )
    rows = _normalize_realized_rows(source.get("rows"), outcome_keys=keys)
    row_keys = [{
        "source_ordinal": row["source_ordinal"],
        "season": row["season"],
        "week": row["week"],
        "slate_id": row["slate_id"],
        "source_kind": row["source_kind"],
        "source_key": row["source_key"],
        "player_id": row["player_id"],
    } for row in rows]
    if (
        source.get("schema_version") != REALIZED_SOURCE_SCHEMA
        or source.get("outcome_key_projection_identity") != projection_identity
        or source.get("outcome_key_projection_sha256")
        != projection["outcome_key_projection_sha256"]
        or source.get("panel_freeze_identity") != projection["panel_freeze_identity"]
        or source.get("panel_freeze_sha256") != projection["panel_freeze_sha256"]
        or source.get("later_source_freeze_identity")
        != projection["later_source_freeze_identity"]
        or source.get("later_source_freeze_sha256")
        != projection["later_source_freeze_sha256"]
        or source.get("score_unit") != "micro_dk"
        or source.get("micro_dk_per_point") != MICRO_DK_PER_POINT
        or source.get("row_fields") != sorted(_SOURCE_ROW_FIELDS)
        or source.get("row_count") != len(rows)
        or source.get("row_keys_sha256") != canonical_sha256(row_keys)
        or source.get("rows_sha256") != canonical_sha256(rows)
        or source.get("rows") != rows
        or source.get("exact_union_coverage") is not True
        or source.get("lineup_scoring_performed") is not False
        or source.get("full_field_standings_included") is not False
        or source.get("payout_ladder_included") is not False
        or any(source.get(field) is not False for field in (
            "graph_mutation_licensed", "production_change_licensed",
            "decision_authority",
        ))
    ):
        _fail("realized source law differs")
    return source, retained_identity, rows


def _snapshot_rows(rows: Sequence[Mapping[str, object]]) -> list[dict[str, object]]:
    return [{
        "source_ordinal": row["source_ordinal"],
        "season": row["season"],
        "week": row["week"],
        "slate_id": row["slate_id"],
        "player_id": row["player_id"],
        "realized_score_micro": row["realized_score_micro"],
    } for row in rows]


def build_outcome_snapshot_v1(
    *,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    realized_source: object,
    realized_source_identity: object,
    read_exact: ReadExact,
) -> dict[str, object]:
    """Build the reusable score snapshot from one exact persisted source."""
    projection, projection_identity, keys = validate_outcome_key_projection_v1(
        outcome_key_projection,
        identity=outcome_key_projection_identity,
        read_exact=read_exact,
    )
    source, source_identity, source_rows = _validate_realized_source_against_projection(
        realized_source,
        identity=realized_source_identity,
        projection=projection,
        projection_identity=projection_identity,
        keys=keys,
    )
    rows = _snapshot_rows(source_rows)
    row_keys = [{key: row[key] for key in (
        "source_ordinal", "season", "week", "slate_id", "player_id"
    )} for row in rows]
    body: dict[str, object] = {
        "schema_version": OUTCOME_SNAPSHOT_SCHEMA,
        "outcome_key_projection_identity": projection_identity,
        "outcome_key_projection_sha256": projection[
            "outcome_key_projection_sha256"
        ],
        "panel_freeze_identity": projection["panel_freeze_identity"],
        "panel_freeze_sha256": projection["panel_freeze_sha256"],
        "later_source_freeze_identity": projection[
            "later_source_freeze_identity"
        ],
        "later_source_freeze_sha256": projection[
            "later_source_freeze_sha256"
        ],
        "realized_source_identity": source_identity,
        "realized_source_sha256": source["realized_source_sha256"],
        "score_unit": "micro_dk",
        "micro_dk_per_point": MICRO_DK_PER_POINT,
        "row_count": len(rows),
        "row_keys_sha256": canonical_sha256(row_keys),
        "rows_sha256": canonical_sha256(rows),
        "rows": rows,
        "exact_union_coverage": True,
        "lineup_scoring_performed": False,
        "full_field_standings_included": False,
        "payout_ladder_included": False,
        "graph_mutation_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    return _with_hash(body, field="outcome_snapshot_sha256")


def validate_outcome_snapshot_v1(
    value: object,
    *,
    identity: object,
    outcome_key_projection: object,
    outcome_key_projection_identity: object,
    realized_source: object,
    realized_source_identity: object,
    read_exact: ReadExact,
) -> tuple[dict[str, object], dict[str, object], dict[tuple[int, str], int]]:
    expected = build_outcome_snapshot_v1(
        outcome_key_projection=outcome_key_projection,
        outcome_key_projection_identity=outcome_key_projection_identity,
        realized_source=realized_source,
        realized_source_identity=realized_source_identity,
        read_exact=read_exact,
    )
    snapshot = _mapping(value, label="outcome snapshot")
    _exact_keys(snapshot, _SNAPSHOT_FIELDS, label="outcome snapshot")
    _self_hash(
        snapshot, field="outcome_snapshot_sha256", label="outcome snapshot"
    )
    retained_identity = _json_identity(
        snapshot, identity, label="outcome snapshot identity"
    )
    if canonical_json_bytes(snapshot) != canonical_json_bytes(expected):
        _fail("outcome snapshot canonical replay differs")
    score_map: dict[tuple[int, str], int] = {}
    for ordinal, raw_row in enumerate(_sequence(snapshot["rows"], label="snapshot rows")):
        row = _mapping(raw_row, label=f"snapshot row[{ordinal}]")
        _exact_keys(row, _SNAPSHOT_ROW_FIELDS, label=f"snapshot row[{ordinal}]")
        key = (int(row["source_ordinal"]), str(row["player_id"]))
        if key in score_map:
            _fail("outcome snapshot repeats a player key")
        score_map[key] = int(row["realized_score_micro"])
    return snapshot, retained_identity, score_map


__all__ = [
    "ACTUAL_ROOT_SMOKE_RECEIPT_SCHEMA",
    "ALL_BLOCK_FIT_SCOPE_ID",
    "AUTHORITATIVE_SLATE_COUNT",
    "CorpusR6FullUnionOutcomeSnapshotV1Error",
    "OUTCOME_KEY_PROJECTION_SCHEMA",
    "OUTCOME_SNAPSHOT_SCHEMA",
    "OutcomeKeyV1",
    "REALIZED_SOURCE_SCHEMA",
    "WORLD_BLOCKS",
    "build_actual_root_smoke_receipt_v1",
    "build_outcome_snapshot_v1",
    "build_realized_source_v1",
    "build_realized_source_from_registered_rows_v1",
    "canonical_json_bytes",
    "canonical_sha256",
    "normalize_registered_integer_micro_rows_v1",
    "project_required_outcome_keys_v1",
    "validate_outcome_key_projection_v1",
    "validate_outcome_snapshot_v1",
    "validate_realized_source_v1",
    "validate_actual_root_smoke_receipt_v1",
]
