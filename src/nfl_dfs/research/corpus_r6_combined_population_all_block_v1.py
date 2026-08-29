"""Pure all-block exact-K80 confirmation over completed R6 populations.

The adapter consumes five already-validated, outcome-blind population
projections: the incumbent current-R6 union, F7, F8, F9, and the hard-230
challenger.  Every projection must bind the same later-source freeze and the
same generation-exact R0--R4 world artifacts.  Roster identities are
normalized to the incumbent per-slate law, duplicate rosters are collapsed
with all source memberships retained, and the complete union is cross-scored
once on the common player-world matrix.  The frozen eight full-union
strategies are then run once on the distinct all-block final fit at exact 80.

This module owns no storage, warehouse, outcome, deployment, or publication
client.  Exact-open/replay of predecessor objects belongs to the caller; the
small projection constructor below freezes the already-validated evidence
that is allowed to reach this scientific core.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from hashlib import sha256
from itertools import combinations
from typing import Final

import numpy as np

from nfl_dfs.research import corpus_batch_retrieval_runner_v2 as runner
from nfl_dfs.research import (
    corpus_extreme_tail_hard230_r6_source_decoder_v1 as hard_decoder,
)
from nfl_dfs.research import corpus_parametric_batch as batch
from nfl_dfs.research import corpus_r6_full_union_fast_lane_v1 as lane
from nfl_dfs.research import corpus_r6_full_union_panel_freeze_v1 as full_freeze
from nfl_dfs.research import corpus_r6_hard230_selector_bridge_v1 as hard_bridge
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as population_runtime,
)
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_legal_feasibility import (
    _score_matrix_sha256,
    cross_score_full_union,
)
from nfl_dfs.research.corpus_v12_import import canonical_lineup_id


ADAPTER_ID: Final = "combined-population-all-block-v1"
SOURCE_SCHEMA: Final = "corpus-r6-combined-population-source/v1"
UNION_SCHEMA: Final = "corpus-r6-combined-population-union/v1"
MATRIX_SCHEMA: Final = "corpus-r6-combined-population-score-matrix/v1"
RESULT_SCHEMA: Final = "corpus-r6-combined-population-all-block-result/v1"
CONTRIBUTION_SCHEMA: Final = (
    "corpus-r6-combined-population-selected-source-contribution/v1"
)
FIT_SCOPE_ID: Final = "all-block-final-fit"
ADMISSION_ID: Final = "combined-immutable-populations-full-union-v1"
DOSE_AUTHORITY: Final = "common-five-r-block-immutable-worlds-v1"
ENTRY_BUDGET: Final = 80
NORMALIZED_POPULATION_ID: Final = "incumbent-f7-f8-f9-hard230-union-v1"
SELECTOR_FAMILY: Final = "frozen-r6-full-union-eight"
INCUMBENT_SOURCE_ID: Final = "incumbent-current-r6"
HARD230_SOURCE_ID: Final = "hard230-replenishing-challenger"
PROFILE_SOURCE_IDS: Final = (
    "F7-qb-and-bringback-relaxed",
    "F8-game-cap-3",
    "F9-single-partner",
)
SOURCE_ORDER: Final = (
    INCUMBENT_SOURCE_ID,
    *PROFILE_SOURCE_IDS,
    HARD230_SOURCE_ID,
)
SOURCE_KIND_BY_ID: Final = {
    INCUMBENT_SOURCE_ID: "incumbent-current-r6",
    PROFILE_SOURCE_IDS[0]: "population-profile",
    PROFILE_SOURCE_IDS[1]: "population-profile",
    PROFILE_SOURCE_IDS[2]: "population-profile",
    HARD230_SOURCE_ID: "hard230-challenger",
}
WORLD_IDENTITY_KEYS: Final = tuple(
    f"world_artifact_{block.casefold()}" for block in rw.WORLD_BLOCKS
)

_SOURCE_FIELDS: Final = frozenset({
    "schema_version", "source_id", "source_kind", "slate_id",
    "source_artifact_binding", "source_artifact_binding_sha256",
    "later_source_identity", "world_artifact_identities", "lineup_count",
    "lineups", "lineups_sha256", "uses_realized_outcomes", "source_sha256",
})
_SOURCE_LINEUP_FIELDS: Final = frozenset({
    "source_lineup_id", "roster_player_ids", "occurrence_count",
    "source_detail_ids",
})
_UNION_LINEUP_FIELDS: Final = frozenset({
    "lineup_id", "roster_player_ids", "source_population_ids",
    "source_population_count", "source_lineup_ids_by_population",
    "source_occurrence_counts_by_population", "source_detail_ids_by_population",
})
_BOOK_FIELDS: Final = frozenset({
    "schema_version", "book_id", "fit_scope_id", "reconstruction_sha256",
    "training_blocks", "heldout_block", "admission_id", "admission_sha256",
    "strategy_id", "strategy_sha256", "strategy_application_scope",
    "input_lineup_ids_sha256", "training_score_matrix_sha256",
    "training_score_shape", "worlds_per_block", "dose_authority",
    "selected_local_indices", "selected_global_indices", "selected_lineup_ids",
    "selected_rosters", "entry_count", "marginal_trace", "training_metrics",
    "redundancy_diagnostics", "heldout_metrics_descriptive",
    "threshold_semantics", "uses_realized_outcomes", "promotion_authority",
    "book_sha256",
})


class CorpusR6CombinedPopulationAllBlockV1Error(ValueError):
    """The immutable population union or all-block selector replay differs."""


def _fail(message: str) -> None:
    raise CorpusR6CombinedPopulationAllBlockV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _hash(value: object) -> str:
    return batch.canonical_sha256(value)


def _with_hash(value: Mapping[str, object], *, field: str) -> dict[str, object]:
    body = dict(value)
    if field in body:
        _fail(f"{field} is already present")
    return {**body, field: _hash(body)}


def _digest(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be lowercase SHA-256")
    return value


def _identity(value: object, *, label: str) -> dict[str, object]:
    row = _mapping(value, label=label)
    if set(row) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} identity fields differ")
    if (
        type(row["uri"]) is not str
        or not row["uri"].startswith("gs://")
        or type(row["generation"]) is not str
        or not row["generation"].isdigit()
        or type(row["bytes"]) is not int
        or row["bytes"] < 1
    ):
        _fail(f"{label} identity values differ")
    _digest(row["sha256"], label=f"{label} SHA-256")
    return row


def _slate(value: object) -> dict[str, object]:
    row = _mapping(value, label="combined-population slate")
    if set(row) != {"season", "week", "slate_id"}:
        _fail("combined-population slate fields differ")
    if (
        type(row["season"]) is not int
        or type(row["week"]) is not int
        or not 1 <= int(row["week"]) <= 18
        or type(row["slate_id"]) is not str
        or row["slate_id"] != f"{row['season']}-w{int(row['week']):02d}"
    ):
        _fail("combined-population slate values differ")
    return row


def build_population_source_v1(
    *,
    source_id: str,
    slate_id: str,
    source_artifact_binding: Mapping[str, object],
    later_source_identity: Mapping[str, object],
    world_artifact_identities: Mapping[str, object],
    lineups: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Freeze one already-validated population into the common pure seam."""
    if source_id not in SOURCE_KIND_BY_ID:
        _fail("population source ID is outside the predeclared combined test")
    if type(slate_id) is not str or not slate_id:
        _fail("population source slate ID differs")
    binding = _mapping(source_artifact_binding, label=f"{source_id} binding")
    if not binding:
        _fail("population source artifact binding is empty")
    later_identity = _identity(
        later_source_identity, label=f"{source_id} later source"
    )
    raw_worlds = _mapping(
        world_artifact_identities, label=f"{source_id} world identities"
    )
    if tuple(raw_worlds) != WORLD_IDENTITY_KEYS:
        _fail("population source world identity order differs")
    worlds = {
        key: _identity(raw_worlds[key], label=f"{source_id} {key}")
        for key in WORLD_IDENTITY_KEYS
    }

    normalized: list[dict[str, object]] = []
    seen_source_ids: set[str] = set()
    seen_rosters: set[tuple[str, ...]] = set()
    for ordinal, raw in enumerate(lineups):
        row = _mapping(raw, label=f"{source_id} lineup[{ordinal}]")
        if set(row) != _SOURCE_LINEUP_FIELDS:
            _fail("population source lineup fields differ")
        source_lineup_id = row.get("source_lineup_id")
        roster = [
            str(player_id)
            for player_id in _sequence(
                row.get("roster_player_ids"), label="source roster"
            )
        ]
        occurrence_count = row.get("occurrence_count")
        details = [
            str(value)
            for value in _sequence(
                row.get("source_detail_ids"), label="source detail IDs"
            )
        ]
        if (
            type(source_lineup_id) is not str
            or not source_lineup_id
            or source_lineup_id in seen_source_ids
            or len(roster) != rw.ROSTER_SIZE
            or roster != sorted(set(roster))
            or tuple(roster) in seen_rosters
            or type(occurrence_count) is not int
            or occurrence_count < 1
            or details != sorted(set(details))
            or not details
        ):
            _fail("population source lineup values differ")
        seen_source_ids.add(source_lineup_id)
        seen_rosters.add(tuple(roster))
        normalized.append({
            "source_lineup_id": source_lineup_id,
            "roster_player_ids": roster,
            "occurrence_count": occurrence_count,
            "source_detail_ids": details,
        })
    normalized.sort(key=lambda row: (row["roster_player_ids"], row["source_lineup_id"]))
    if not normalized:
        _fail("population source is empty")
    body = {
        "schema_version": SOURCE_SCHEMA,
        "source_id": source_id,
        "source_kind": SOURCE_KIND_BY_ID[source_id],
        "slate_id": slate_id,
        "source_artifact_binding": binding,
        "source_artifact_binding_sha256": _hash(binding),
        "later_source_identity": later_identity,
        "world_artifact_identities": worlds,
        "lineup_count": len(normalized),
        "lineups": normalized,
        "lineups_sha256": _hash(normalized),
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="source_sha256")


def validate_population_source_v1(value: object) -> dict[str, object]:
    source = _mapping(value, label="combined population source")
    if set(source) != _SOURCE_FIELDS:
        _fail("combined population source fields differ")
    source_id = source.get("source_id")
    if (
        source.get("schema_version") != SOURCE_SCHEMA
        or source_id not in SOURCE_KIND_BY_ID
        or source.get("source_kind") != SOURCE_KIND_BY_ID[source_id]
        or source.get("uses_realized_outcomes") is not False
        or source.get("source_sha256")
        != _hash({key: item for key, item in source.items() if key != "source_sha256"})
        or source.get("source_artifact_binding_sha256")
        != _hash(source.get("source_artifact_binding"))
    ):
        _fail("combined population source fixed authority differs")
    rebuilt = build_population_source_v1(
        source_id=str(source_id),
        slate_id=str(source.get("slate_id")),
        source_artifact_binding=_mapping(
            source.get("source_artifact_binding"), label="source binding"
        ),
        later_source_identity=_mapping(
            source.get("later_source_identity"), label="source later identity"
        ),
        world_artifact_identities=_mapping(
            source.get("world_artifact_identities"), label="source worlds"
        ),
        lineups=[
            _mapping(row, label="source lineup")
            for row in _sequence(source.get("lineups"), label="source lineups")
        ],
    )
    if batch.canonical_json_bytes(source) != batch.canonical_json_bytes(rebuilt):
        _fail("combined population source canonical replay differs")
    return rebuilt


def project_incumbent_current_r6_source_v1(
    *,
    task_result: object,
    panel_index_identity: object,
    panel_index_sha256: str,
    panel_member: Mapping[str, object],
) -> dict[str, object]:
    """Project the deep-validated incumbent all-block candidate population."""
    try:
        result = full_freeze.validate_task_result_v1(
            task_result,
            panel_index_identity=panel_index_identity,
            panel_index_sha256=panel_index_sha256,
            panel_member=panel_member,
        )
    except Exception as exc:
        raise CorpusR6CombinedPopulationAllBlockV1Error(
            f"incumbent full-union task result is invalid: {exc}"
        ) from exc
    surface = _mapping(result["full_union_surface"], label="incumbent surface")
    scopes = _sequence(surface.get("scopes"), label="incumbent scopes")
    final_scope = _mapping(scopes[-1], label="incumbent all-block scope")
    candidate_view = _mapping(
        final_scope.get("candidate_view"), label="incumbent candidate view"
    )
    candidates = [
        _mapping(row, label="incumbent all-block candidate")
        for row in _sequence(
            candidate_view.get("eligible_candidates"),
            label="incumbent all-block candidates",
        )
    ]
    if (
        final_scope.get("fit_scope_id") != FIT_SCOPE_ID
        or final_scope.get("heldout_block") is not None
        or final_scope.get("training_blocks") != list(rw.WORLD_BLOCKS)
        or candidate_view.get("excluded_count") != 0
        or len(candidates) != candidate_view.get("eligible_count")
    ):
        _fail("incumbent all-block candidate scope differs")
    return build_population_source_v1(
        source_id=INCUMBENT_SOURCE_ID,
        slate_id=str(result["slate_id"]),
        source_artifact_binding={
            "task_result_sha256": result["task_result_sha256"],
            "full_union_surface_sha256": result["full_union_surface_sha256"],
            "candidate_provenance_sha256": result[
                "candidate_provenance_sha256"
            ],
            "panel_index_identity": result["panel_index_identity"],
            "accepted_slate_membership_sha256": result[
                "accepted_slate_membership_sha256"
            ],
        },
        later_source_identity=result["later_source_freeze_identity"],
        world_artifact_identities=result["world_artifact_identities"],
        lineups=[{
            "source_lineup_id": row["lineup_id"],
            "roster_player_ids": row["roster_player_ids"],
            "occurrence_count": row["training_occurrence_count"],
            "source_detail_ids": row["training_source_arms"],
        } for row in candidates],
    )


def project_profile_sources_v1(
    *, profile_lineups_by_id: Mapping[str, object], players: Sequence[object]
) -> tuple[dict[str, object], ...]:
    """Project F7/F8/F9 immutable profile objects without rerunning solvers."""
    if tuple(profile_lineups_by_id) != PROFILE_SOURCE_IDS:
        _fail("profile lineup source order/census differs")
    projected: list[dict[str, object]] = []
    for profile_id in PROFILE_SOURCE_IDS:
        try:
            body = population_runtime.validate_profile_lineups_v1(
                profile_lineups_by_id[profile_id], players=players
            )
        except Exception as exc:
            raise CorpusR6CombinedPopulationAllBlockV1Error(
                f"{profile_id} immutable lineups are invalid: {exc}"
            ) from exc
        source = _mapping(body["source_authority"], label="profile source authority")
        unique_rows = [
            _mapping(row, label=f"{profile_id} unique lineup")
            for row in _sequence(body["unique_lineups"], label="profile unique lineups")
        ]
        projected.append(build_population_source_v1(
            source_id=profile_id,
            slate_id=str(_mapping(body["slate"], label="profile slate")["slate_id"]),
            source_artifact_binding={
                "lineups_sha256": body["lineups_sha256"],
                "profile_sha256": body["profile_sha256"],
                "source_authority_sha256": body["source_authority_sha256"],
                "work_sha256": body["work_sha256"],
                "world_schedule_sha256": body["world_schedule_sha256"],
            },
            later_source_identity=source["later_source_identity"],
            world_artifact_identities=source["world_artifact_identities"],
            lineups=[{
                "source_lineup_id": _mapping(
                    row["lineup_identity"], label="profile lineup identity"
                )["lineup_sha256"],
                "roster_player_ids": _mapping(
                    row["lineup_identity"], label="profile lineup identity"
                )["roster"],
                "occurrence_count": row["occurrence_count"],
                "source_detail_ids": [profile_id],
            } for row in unique_rows],
        ))
    return tuple(projected)


def project_hard230_challenger_source_v1(
    *, slate_result: object, source_member: object
) -> dict[str, object]:
    """Project only the hard-230 challenger and prove common R0--R4 inputs."""
    try:
        normalized = hard_bridge.normalized_slate_for_grader_v1(slate_result)
    except Exception as exc:
        raise CorpusR6CombinedPopulationAllBlockV1Error(
            f"hard230 selector slate is invalid: {exc}"
        ) from exc
    result = _mapping(slate_result, label="hard230 selector slate")
    member = _mapping(source_member, label="hard230 source member")
    member_identity = _mapping(
        result.get("source_member_identity"), label="hard230 source member identity"
    )
    object_identity = _identity(
        member_identity.get("object_identity"), label="hard230 source member object"
    )
    member_bytes = hard_decoder._canonical(member, label="hard230 source member")
    member_sha = sha256(member_bytes).hexdigest()
    raw_worlds = _sequence(
        member.get("ordered_r_block_input_identities"),
        label="hard230 ordered R-block identities",
    )
    if len(raw_worlds) != len(WORLD_IDENTITY_KEYS):
        _fail("hard230 ordered R-block identity census differs")
    worlds = {
        key: _identity(identity, label=f"hard230 {key}")
        for key, identity in zip(WORLD_IDENTITY_KEYS, raw_worlds, strict=True)
    }
    source_lineage = _mapping(
        result.get("source_lineage"), label="hard230 source lineage"
    )
    score_matrix_identity = _mapping(
        result.get("score_matrix_identity"), label="hard230 score matrix identity"
    )
    false_fields = (
        "uses_realized_outcomes", "uses_heldout_scores",
        "historical_scoring_licensed", "selector_authority",
        "publication_authority", "promotion_authority", "decision_authority",
        "production_change_licensed", "graph_mutation_licensed",
    )
    if (
        member.get("schema_version") != hard_decoder.SOURCE_MEMBER_SCHEMA
        or member.get("contract_id") != hard_decoder.CONTRACT_ID
        or member.get("member_role")
        != "hard230-r6-fit-source-decoder-authority"
        or member.get("slate_id") != normalized["slate_id"]
        or member.get("fit_scope_id") != FIT_SCOPE_ID
        or member.get("heldout_block") is not None
        or member.get("training_blocks") != list(rw.WORLD_BLOCKS)
        or member.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
        or len(raw_worlds) != len(WORLD_IDENTITY_KEYS)
        or member.get("ordered_r_block_input_identities_sha256")
        != hard_decoder._sha(raw_worlds, label="hard230 ordered R-block identities")
        or member.get("later_source_freeze_identity")
        != normalized["later_source_identity"]
        or member.get("player_registry_sha256")
        != hard_decoder._sha(member.get("player_registry"), label="player registry")
        or member.get("outcome_columns_read") != []
        or member.get("candidate_totals_materialized") is not False
        or member.get("tail_line_materialized") is not False
        or member.get("excluded_heldout_block_opened") is not False
        or any(member.get(field) is not False for field in false_fields)
        or member_identity.get("slate_id") != normalized["slate_id"]
        or member_identity.get("member_sha256") != member_sha
        or object_identity["sha256"] != member_sha
        or object_identity["bytes"] != len(member_bytes)
        or source_lineage.get("source_member_sha256") != member_sha
        or source_lineage.get("player_registry_sha256")
        != member.get("player_registry_sha256")
        or score_matrix_identity.get("player_registry_sha256")
        != member.get("player_registry_sha256")
        or score_matrix_identity.get("matrix_shape")
        != [len(member.get("player_registry", [])), len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK]
    ):
        _fail("hard230 source member/common-world authority differs")
    populations = [
        _mapping(row, label="hard230 normalized population")
        for row in _sequence(normalized["populations"], label="hard230 populations")
    ]
    matches = [
        row for row in populations
        if _mapping(row.get("dimensions"), label="hard230 population dimensions").get(
            "population_role"
        ) == "hard230-challenger"
    ]
    if len(matches) != 1:
        _fail("hard230 challenger population census differs")
    challenger = matches[0]
    lineups = [
        _mapping(row, label="hard230 challenger lineup")
        for row in _sequence(challenger["lineups"], label="hard230 challenger lineups")
    ]
    return build_population_source_v1(
        source_id=HARD230_SOURCE_ID,
        slate_id=str(normalized["slate_id"]),
        source_artifact_binding={
            "slate_result_sha256": result["slate_result_sha256"],
            "source_member_identity": member_identity,
            "score_matrix_identity": score_matrix_identity,
            "source_lineage": source_lineage,
            "hard230_population_id": challenger["population_id"],
        },
        later_source_identity=normalized["later_source_identity"],
        world_artifact_identities=worlds,
        lineups=[{
            "source_lineup_id": row["lineup_id"],
            "roster_player_ids": row["roster_player_ids"],
            "occurrence_count": 1,
            "source_detail_ids": [str(challenger["population_id"])],
        } for row in lineups],
    )


def _membership_analysis(
    union_rows: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    membership = Counter()
    exclusive = Counter()
    patterns = Counter()
    pairwise = Counter()
    for raw in union_rows:
        row = _mapping(raw, label="union membership row")
        sources = tuple(str(value) for value in row["source_population_ids"])
        patterns[sources] += 1
        for source_id in sources:
            membership[source_id] += 1
        if len(sources) == 1:
            exclusive[sources[0]] += 1
        for pair in combinations(sources, 2):
            pairwise[pair] += 1
    return {
        "union_lineup_count": len(union_rows),
        "source_membership_counts": {
            source_id: membership[source_id] for source_id in SOURCE_ORDER
        },
        "source_exclusive_counts": {
            source_id: exclusive[source_id] for source_id in SOURCE_ORDER
        },
        "membership_pattern_counts": [
            {"source_population_ids": list(pattern), "lineup_count": count}
            for pattern, count in sorted(patterns.items())
        ],
        "pairwise_overlap_counts": [
            {"left_source_id": left, "right_source_id": right, "lineup_count": count}
            for (left, right), count in sorted(pairwise.items())
        ],
        "multi_source_lineup_count": sum(
            count for pattern, count in patterns.items() if len(pattern) > 1
        ),
        "challenger_only_lineup_count": sum(
            count for pattern, count in patterns.items()
            if INCUMBENT_SOURCE_ID not in pattern
        ),
    }


def build_combined_union_v1(
    *, slate: Mapping[str, object], sources: Sequence[Mapping[str, object]]
) -> dict[str, object]:
    """Normalize identities and retain all cross-population memberships."""
    retained_slate = _slate(slate)
    retained_sources = [validate_population_source_v1(row) for row in sources]
    if [row["source_id"] for row in retained_sources] != list(SOURCE_ORDER):
        _fail("combined population source order/census differs")
    later = retained_sources[0]["later_source_identity"]
    worlds = retained_sources[0]["world_artifact_identities"]
    if any(
        row["slate_id"] != retained_slate["slate_id"]
        or row["later_source_identity"] != later
        or row["world_artifact_identities"] != worlds
        for row in retained_sources
    ):
        _fail("combined populations do not share one slate/source/world authority")

    roster_by_id: dict[str, tuple[str, ...]] = {}
    memberships: dict[str, dict[str, dict[str, object]]] = defaultdict(dict)
    for source in retained_sources:
        source_id = str(source["source_id"])
        for raw_lineup in source["lineups"]:
            lineup = _mapping(raw_lineup, label="population source lineup")
            roster = tuple(str(value) for value in lineup["roster_player_ids"])
            lineup_id = canonical_lineup_id(retained_slate, roster)
            prior = roster_by_id.setdefault(lineup_id, roster)
            if prior != roster:
                _fail("canonical combined lineup identity collision")
            memberships[lineup_id][source_id] = {
                "source_lineup_id": lineup["source_lineup_id"],
                "occurrence_count": lineup["occurrence_count"],
                "source_detail_ids": lineup["source_detail_ids"],
            }
    union_rows: list[dict[str, object]] = []
    for lineup_id in sorted(roster_by_id):
        by_source = memberships[lineup_id]
        source_ids = [source_id for source_id in SOURCE_ORDER if source_id in by_source]
        union_rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": list(roster_by_id[lineup_id]),
            "source_population_ids": source_ids,
            "source_population_count": len(source_ids),
            "source_lineup_ids_by_population": {
                source_id: by_source[source_id]["source_lineup_id"]
                for source_id in source_ids
            },
            "source_occurrence_counts_by_population": {
                source_id: by_source[source_id]["occurrence_count"]
                for source_id in source_ids
            },
            "source_detail_ids_by_population": {
                source_id: by_source[source_id]["source_detail_ids"]
                for source_id in source_ids
            },
        })
    if len(union_rows) < ENTRY_BUDGET:
        _fail("combined population cannot satisfy exact K80")
    overlap = _membership_analysis(union_rows)
    source_registry = [{
        "source_id": source["source_id"],
        "source_kind": source["source_kind"],
        "source_sha256": source["source_sha256"],
        "source_lineup_count": source["lineup_count"],
        "source_artifact_binding_sha256": source[
            "source_artifact_binding_sha256"
        ],
    } for source in retained_sources]
    body = {
        "schema_version": UNION_SCHEMA,
        "slate": retained_slate,
        "later_source_identity": later,
        "world_artifact_identities": worlds,
        "source_registry": source_registry,
        "source_registry_sha256": _hash(source_registry),
        "source_count": len(source_registry),
        "lineup_order_law": "ascending-canonical-per-slate-lineup-id",
        "union_lineup_count": len(union_rows),
        "union_lineups": union_rows,
        "union_lineups_sha256": _hash(union_rows),
        "overlap_analysis": overlap,
        "overlap_analysis_sha256": _hash(overlap),
        "uses_realized_outcomes": False,
    }
    return _with_hash(body, field="union_sha256")


def _selected_contribution(
    *, strategy_id: str, selected_ids: Sequence[str], union_by_id: Mapping[str, object]
) -> dict[str, object]:
    rows = [
        _mapping(union_by_id[lineup_id], label="selected union lineup")
        for lineup_id in selected_ids
    ]
    analysis = _membership_analysis(rows)
    body = {
        "schema_version": CONTRIBUTION_SCHEMA,
        "strategy_id": strategy_id,
        "entry_budget": ENTRY_BUDGET,
        "selected_lineup_count": len(rows),
        "selected_source_membership_counts": analysis["source_membership_counts"],
        "selected_source_exclusive_counts": analysis["source_exclusive_counts"],
        "selected_membership_pattern_counts": analysis[
            "membership_pattern_counts"
        ],
        "selected_pairwise_overlap_counts": analysis["pairwise_overlap_counts"],
        "selected_multi_source_lineup_count": analysis[
            "multi_source_lineup_count"
        ],
        "selected_challenger_only_lineup_count": analysis[
            "challenger_only_lineup_count"
        ],
        "selected_incumbent_member_count": analysis[
            "source_membership_counts"
        ][INCUMBENT_SOURCE_ID],
        "selected_lineup_sources": [{
            "lineup_id": row["lineup_id"],
            "source_population_ids": row["source_population_ids"],
        } for row in rows],
    }
    return _with_hash(body, field="contribution_sha256")


def run_combined_population_all_block_v1(
    *,
    slate: Mapping[str, object],
    sources: Sequence[Mapping[str, object]],
    players: Sequence[object],
    player_draws: np.ndarray,
    worlds_per_block: int = rw.WORLDS_PER_BLOCK,
    require_authoritative: bool = True,
) -> dict[str, object]:
    """Cross-score one immutable union once and run the frozen eight K80 laws."""
    if type(worlds_per_block) is not int or worlds_per_block < 1:
        _fail("worlds per block must be one positive exact integer")
    if type(require_authoritative) is not bool:
        _fail("require_authoritative must be one exact boolean")
    if require_authoritative and worlds_per_block != rw.WORLDS_PER_BLOCK:
        _fail("authoritative combined test requires the complete 10,000-world blocks")
    if worlds_per_block != rw.WORLDS_PER_BLOCK:
        _fail("frozen eight-strategy registry requires 10,000-world blocks")
    union = build_combined_union_v1(slate=slate, sources=sources)
    player_rows = tuple(players)
    player_ids = [str(getattr(player, "player_id", "")) for player in player_rows]
    draws = np.asarray(player_draws)
    if (
        not player_ids
        or player_ids != sorted(set(player_ids))
        or draws is not player_draws
        or draws.dtype != np.dtype(np.float32)
        or draws.ndim != 2
        or draws.shape != (
            len(player_ids), len(rw.WORLD_BLOCKS) * worlds_per_block
        )
        or not draws.flags.c_contiguous
        or not np.isfinite(draws).all()
    ):
        _fail("common five-block player-world matrix differs")
    union_rows = [
        _mapping(row, label="combined union lineup") for row in union["union_lineups"]
    ]
    rosters = [row["roster_player_ids"] for row in union_rows]
    try:
        union_scores = cross_score_full_union(
            player_rows,
            draws,
            rosters,
            expected_worlds=len(rw.WORLD_BLOCKS) * worlds_per_block,
        )
    except Exception as exc:
        raise CorpusR6CombinedPopulationAllBlockV1Error(
            f"combined-population cross-score failed: {exc}"
        ) from exc
    if (
        union_scores.dtype != np.dtype(np.float64)
        or union_scores.shape != (len(union_rows), draws.shape[1])
        or not np.isfinite(union_scores).all()
    ):
        _fail("combined union score matrix differs")
    matrix_binding = _with_hash({
        "schema_version": MATRIX_SCHEMA,
        "union_sha256": union["union_sha256"],
        "later_source_identity": union["later_source_identity"],
        "world_artifact_identities_sha256": _hash(
            union["world_artifact_identities"]
        ),
        "player_ids_sha256": _hash(player_ids),
        "lineup_ids_sha256": _hash([row["lineup_id"] for row in union_rows]),
        "score_unit": "DraftKings-points",
        "dtype": "float64-le",
        "shape": list(union_scores.shape),
        "worlds_per_block": worlds_per_block,
        "block_order": list(rw.WORLD_BLOCKS),
        "score_matrix_sha256": _score_matrix_sha256(union_scores),
        "player_world_matrix_read_count": 1,
        "union_score_matrix_materialization_count": 1,
        "population_regeneration_performed": False,
        "uses_realized_outcomes": False,
    }, field="matrix_binding_sha256")

    lineup_ids = [str(row["lineup_id"]) for row in union_rows]
    admission = _with_hash({
        "schema_version": runner.ADMISSION_SCHEMA,
        "admission_id": ADMISSION_ID,
        "fit_scope_id": FIT_SCOPE_ID,
        "selection_provenance_sha256": union["union_sha256"],
        "admitted_lineup_ids": lineup_ids,
        "admitted_count": len(lineup_ids),
        "excluded_eligible_candidates": [],
        "dose_authority": DOSE_AUTHORITY,
        "admission_inputs": "immutable-source-membership-and-stable-lineup-id-only",
        "uses_simulated_scores": False,
        "uses_matchup_values": False,
        "uses_realized_outcomes": False,
    }, field="admission_sha256")
    admitted_global = np.arange(len(lineup_ids), dtype=np.int64)
    roster_by_id = {
        str(row["lineup_id"]): row["roster_player_ids"] for row in union_rows
    }
    global_index_by_id = {
        lineup_id: ordinal for ordinal, lineup_id in enumerate(lineup_ids)
    }
    strategies = lane.frozen_full_union_strategies_v1()
    if (
        len(strategies) != lane.STRATEGY_COUNT
        or any(strategy.get("entry_budget") != ENTRY_BUDGET for strategy in strategies)
    ):
        _fail("frozen combined strategy registry is not exact K80")
    books = [
        runner._run_book(
            strategy=strategy,
            admission=admission,
            admitted_ids=lineup_ids,
            admitted_global=admitted_global,
            training_scores=union_scores,
            training_score_matrix_sha256=matrix_binding[
                "score_matrix_sha256"
            ],
            roster_by_id=roster_by_id,
            global_index_by_id=global_index_by_id,
            scores=union_scores,
            heldout_columns=None,
            training_blocks=rw.WORLD_BLOCKS,
            heldout_block=None,
            worlds_per_block=worlds_per_block,
            fit_scope_id=FIT_SCOPE_ID,
            reconstruction_sha256=matrix_binding["matrix_binding_sha256"],
            dose_authority=DOSE_AUTHORITY,
        )
        for strategy in strategies
    ]
    if (
        len(books) != lane.STRATEGY_COUNT
        or len({book["book_id"] for book in books}) != len(books)
        or any(book.get("entry_count") != ENTRY_BUDGET for book in books)
    ):
        _fail("combined all-block book lattice differs")
    union_by_id = {str(row["lineup_id"]): row for row in union_rows}
    contributions = [
        _selected_contribution(
            strategy_id=str(book["strategy_id"]),
            selected_ids=[str(value) for value in book["selected_lineup_ids"]],
            union_by_id=union_by_id,
        )
        for book in books
    ]
    body = {
        "schema_version": RESULT_SCHEMA,
        "adapter_id": ADAPTER_ID,
        "slate": union["slate"],
        "fit_scope_id": FIT_SCOPE_ID,
        "entry_budget": ENTRY_BUDGET,
        "union": union,
        "union_sha256": union["union_sha256"],
        "matrix_binding": matrix_binding,
        "matrix_binding_sha256": matrix_binding["matrix_binding_sha256"],
        "admission": admission,
        "admission_sha256": admission["admission_sha256"],
        "strategy_registry": strategies,
        "strategy_registry_sha256": _hash(strategies),
        "strategy_count": len(strategies),
        "book_count": len(books),
        "books": books,
        "books_sha256": _hash(books),
        "selected_source_contributions": contributions,
        "selected_source_contributions_sha256": _hash(contributions),
        "all_books_exact_k80": True,
        "all_block_final_fit_only": True,
        "population_regeneration_performed": False,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "promotion_authority": False,
        "production_change_licensed": False,
        "complete": True,
    }
    return _with_hash(body, field="result_sha256")


def _validate_persisted_books_and_contributions_v1(
    *,
    result: Mapping[str, object],
    union: Mapping[str, object],
    matrix: Mapping[str, object],
    admission: Mapping[str, object],
    strategies: Sequence[object],
    books: Sequence[Mapping[str, object]],
    contributions: Sequence[object],
) -> None:
    """Replay every persisted selection/book binding without score access."""
    union_rows = [
        _mapping(row, label="persisted union lineup")
        for row in _sequence(union.get("union_lineups"), label="persisted union")
    ]
    lineup_ids = [str(row.get("lineup_id")) for row in union_rows]
    roster_by_id = {
        str(row.get("lineup_id")): list(row.get("roster_player_ids", []))
        for row in union_rows
    }
    if (
        admission.get("schema_version") != runner.ADMISSION_SCHEMA
        or admission.get("admission_sha256")
        != _hash({key: item for key, item in admission.items() if key != "admission_sha256"})
        or admission.get("admission_id") != ADMISSION_ID
        or admission.get("fit_scope_id") != FIT_SCOPE_ID
        or admission.get("selection_provenance_sha256") != union.get("union_sha256")
        or admission.get("admitted_lineup_ids") != lineup_ids
        or admission.get("admitted_count") != len(lineup_ids)
        or admission.get("excluded_eligible_candidates") != []
        or admission.get("dose_authority") != DOSE_AUTHORITY
        or admission.get("admission_inputs")
        != "immutable-source-membership-and-stable-lineup-id-only"
        or admission.get("uses_simulated_scores") is not False
        or admission.get("uses_matchup_values") is not False
        or admission.get("uses_realized_outcomes") is not False
    ):
        _fail("persisted combined admission differs")
    if (
        matrix.get("schema_version") != MATRIX_SCHEMA
        or matrix.get("matrix_binding_sha256")
        != _hash({
            key: item for key, item in matrix.items()
            if key != "matrix_binding_sha256"
        })
        or matrix.get("union_sha256") != union.get("union_sha256")
        or matrix.get("later_source_identity") != union.get("later_source_identity")
        or matrix.get("world_artifact_identities_sha256")
        != _hash(union.get("world_artifact_identities"))
        or matrix.get("lineup_ids_sha256") != _hash(lineup_ids)
        or matrix.get("dtype") != "float64-le"
        or matrix.get("shape") != [len(lineup_ids), len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK]
        or matrix.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
        or matrix.get("block_order") != list(rw.WORLD_BLOCKS)
        or matrix.get("player_world_matrix_read_count") != 1
        or matrix.get("union_score_matrix_materialization_count") != 1
        or matrix.get("population_regeneration_performed") is not False
        or matrix.get("uses_realized_outcomes") is not False
    ):
        _fail("persisted combined matrix binding differs")
    _digest(matrix.get("player_ids_sha256"), label="persisted player registry")
    score_matrix_sha = _digest(
        matrix.get("score_matrix_sha256"), label="persisted score matrix"
    )
    retained_strategies = [
        _mapping(row, label="persisted combined strategy") for row in strategies
    ]
    if retained_strategies != lane.frozen_full_union_strategies_v1():
        _fail("persisted combined strategy registry differs")
    seen_book_ids: set[str] = set()
    for ordinal, (strategy, raw_book, raw_contribution) in enumerate(zip(
        retained_strategies, books, contributions, strict=True
    )):
        book = _mapping(raw_book, label=f"persisted combined book[{ordinal}]")
        contribution = _mapping(
            raw_contribution, label=f"persisted combined contribution[{ordinal}]"
        )
        selected_ids = [
            str(value) for value in _sequence(
                book.get("selected_lineup_ids"), label="persisted selected IDs"
            )
        ]
        selected_local = _sequence(
            book.get("selected_local_indices"), label="persisted local indices"
        )
        selected_global = _sequence(
            book.get("selected_global_indices"), label="persisted global indices"
        )
        selected_rosters = _sequence(
            book.get("selected_rosters"), label="persisted selected rosters"
        )
        traces = _sequence(book.get("marginal_trace"), label="persisted traces")
        book_id = book.get("book_id")
        if (
            set(book) != _BOOK_FIELDS
            or book.get("book_sha256")
            != _hash({key: item for key, item in book.items() if key != "book_sha256"})
            or type(book_id) is not str
            or not book_id
            or book_id in seen_book_ids
            or strategy.get("strategy_sha256")
            != _hash({
                key: item for key, item in strategy.items()
                if key != "strategy_sha256"
            })
            or book.get("schema_version") != runner.BOOK_SCHEMA
            or book.get("book_id")
            != f"{FIT_SCOPE_ID}:{ADMISSION_ID}:{strategy['strategy_id']}"
            or book.get("fit_scope_id") != FIT_SCOPE_ID
            or book.get("reconstruction_sha256") != matrix.get("matrix_binding_sha256")
            or book.get("training_blocks") != list(rw.WORLD_BLOCKS)
            or book.get("heldout_block") is not None
            or book.get("admission_id") != ADMISSION_ID
            or book.get("admission_sha256") != admission.get("admission_sha256")
            or book.get("strategy_id") != strategy.get("strategy_id")
            or book.get("strategy_sha256") != strategy.get("strategy_sha256")
            or book.get("strategy_application_scope")
            != "explicit-all-five-block-final-fit"
            or book.get("input_lineup_ids_sha256") != _hash(lineup_ids)
            or book.get("training_score_matrix_sha256") != score_matrix_sha
            or book.get("training_score_shape")
            != [len(lineup_ids), len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK]
            or book.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
            or book.get("dose_authority") != DOSE_AUTHORITY
            or book.get("entry_count") != ENTRY_BUDGET
            or len(selected_ids) != ENTRY_BUDGET
            or len(set(selected_ids)) != ENTRY_BUDGET
            or len(selected_local) != ENTRY_BUDGET
            or len(set(selected_local)) != ENTRY_BUDGET
            or any(type(index) is not int or not 0 <= index < len(lineup_ids) for index in selected_local)
            or selected_ids != [lineup_ids[int(index)] for index in selected_local]
            or selected_global != selected_local
            or len(selected_rosters) != ENTRY_BUDGET
            or selected_rosters != [roster_by_id[lineup_id] for lineup_id in selected_ids]
            or len(traces) != ENTRY_BUDGET
            or book.get("heldout_metrics_descriptive") is not None
            or book.get("uses_realized_outcomes") is not False
            or book.get("promotion_authority") is not False
        ):
            _fail("persisted combined exact-K80 book differs")
        for rank, raw_trace in enumerate(traces):
            trace = _mapping(raw_trace, label="persisted marginal trace")
            if (
                trace.get("selection_rank") != rank
                or trace.get("lineup_id") != selected_ids[rank]
                or trace.get("admitted_lineup_index") != selected_local[rank]
                or trace.get("global_lineup_index") != selected_global[rank]
            ):
                _fail("persisted combined marginal trace binding differs")
        expected_contribution = _selected_contribution(
            strategy_id=str(strategy["strategy_id"]),
            selected_ids=selected_ids,
            union_by_id={str(row["lineup_id"]): row for row in union_rows},
        )
        if batch.canonical_json_bytes(contribution) != batch.canonical_json_bytes(
            expected_contribution
        ):
            _fail("persisted combined source contribution replay differs")
        seen_book_ids.add(str(book_id))
    if len(seen_book_ids) != lane.STRATEGY_COUNT:
        _fail("persisted combined book census differs")


def normalized_slate_for_grader_v1(
    value: object, *, source_ordinal: int
) -> dict[str, object]:
    """Project one completed result onto the public direct-roster grader seam."""
    result = _mapping(value, label="combined all-block result")
    if type(source_ordinal) is not int or source_ordinal < 0:
        _fail("combined grader source ordinal differs")
    if (
        result.get("schema_version") != RESULT_SCHEMA
        or result.get("adapter_id") != ADAPTER_ID
        or result.get("fit_scope_id") != FIT_SCOPE_ID
        or result.get("entry_budget") != ENTRY_BUDGET
        or result.get("strategy_count") != lane.STRATEGY_COUNT
        or result.get("book_count") != lane.STRATEGY_COUNT
        or result.get("all_books_exact_k80") is not True
        or result.get("all_block_final_fit_only") is not True
        or result.get("population_regeneration_performed") is not False
        or result.get("outcome_columns_read") != []
        or result.get("uses_realized_outcomes") is not False
        or result.get("historical_scoring_licensed") is not False
        or result.get("promotion_authority") is not False
        or result.get("production_change_licensed") is not False
        or result.get("complete") is not True
        or result.get("result_sha256")
        != _hash({key: item for key, item in result.items() if key != "result_sha256"})
    ):
        _fail("combined all-block result fixed authority differs")
    union = _mapping(result.get("union"), label="combined result union")
    matrix = _mapping(result.get("matrix_binding"), label="combined matrix binding")
    admission = _mapping(result.get("admission"), label="combined admission")
    strategies = _sequence(
        result.get("strategy_registry"), label="combined strategies"
    )
    books = [
        _mapping(row, label="combined book")
        for row in _sequence(result.get("books"), label="combined books")
    ]
    contributions = _sequence(
        result.get("selected_source_contributions"),
        label="combined source contributions",
    )
    if (
        result.get("union_sha256") != union.get("union_sha256")
        or union.get("union_sha256")
        != _hash({key: item for key, item in union.items() if key != "union_sha256"})
        or result.get("matrix_binding_sha256")
        != matrix.get("matrix_binding_sha256")
        or matrix.get("matrix_binding_sha256")
        != _hash({
            key: item for key, item in matrix.items()
            if key != "matrix_binding_sha256"
        })
        or result.get("admission_sha256") != admission.get("admission_sha256")
        or admission.get("admission_sha256")
        != _hash({key: item for key, item in admission.items() if key != "admission_sha256"})
        or strategies != lane.frozen_full_union_strategies_v1()
        or result.get("strategy_registry_sha256") != _hash(strategies)
        or result.get("books_sha256") != _hash(books)
        or result.get("selected_source_contributions_sha256")
        != _hash(contributions)
        or len(books) != lane.STRATEGY_COUNT
        or len(contributions) != lane.STRATEGY_COUNT
    ):
        _fail("combined result nested authority differs")
    _validate_persisted_books_and_contributions_v1(
        result=result,
        union=union,
        matrix=matrix,
        admission=admission,
        strategies=strategies,
        books=books,
        contributions=contributions,
    )
    union_rows = [
        _mapping(row, label="combined normalized lineup")
        for row in _sequence(union.get("union_lineups"), label="combined union lineups")
    ]
    if (
        any(set(row) != _UNION_LINEUP_FIELDS for row in union_rows)
        or union.get("union_lineup_count") != len(union_rows)
        or union.get("union_lineups_sha256") != _hash(union_rows)
    ):
        _fail("combined normalized union lineup registry differs")
    lineup_ids = {str(row["lineup_id"]) for row in union_rows}
    normalized_books: list[dict[str, object]] = []
    for strategy, book, contribution in zip(
        strategies, books, contributions, strict=True
    ):
        selected = [
            str(lineup_id)
            for lineup_id in _sequence(
                book.get("selected_lineup_ids"), label="combined selected IDs"
            )
        ]
        strategy_id = str(_mapping(strategy, label="combined strategy")["strategy_id"])
        if (
            book.get("strategy_id") != strategy_id
            or book.get("entry_count") != ENTRY_BUDGET
            or len(selected) != ENTRY_BUDGET
            or len(set(selected)) != ENTRY_BUDGET
            or not set(selected) <= lineup_ids
            or _mapping(contribution, label="combined contribution").get("strategy_id")
            != strategy_id
        ):
            _fail("combined normalized book differs")
        coordinate = {
            "adapter_id": ADAPTER_ID,
            "metric_kind": "selected-book",
            "fit_scope_id": FIT_SCOPE_ID,
            "selector_family": SELECTOR_FAMILY,
            "selector_id": strategy_id,
            "entry_budget": ENTRY_BUDGET,
        }
        normalized_books.append({
            "coordinate": coordinate,
            "coordinate_sha256": _hash(coordinate),
            "population_id": NORMALIZED_POPULATION_ID,
            "selected_lineup_ids": selected,
        })
    return {
        "source_ordinal": source_ordinal,
        "slate_id": str(_mapping(union["slate"], label="combined union slate")["slate_id"]),
        "populations": [{
            "population_id": NORMALIZED_POPULATION_ID,
            "dimensions": {
                "source_population_ids": list(SOURCE_ORDER),
                "source_count": len(SOURCE_ORDER),
                "union_lineup_count": len(union_rows),
                "fit_scope_id": FIT_SCOPE_ID,
            },
            "lineups": [{
                "lineup_id": row["lineup_id"],
                "roster_player_ids": row["roster_player_ids"],
                "roster_sha256": _hash(row["roster_player_ids"]),
            } for row in union_rows],
        }],
        "books": normalized_books,
        "later_source_identity": union["later_source_identity"],
    }


def validate_exact_science_replay_v1(
    persisted: object, replayed: object, *, source_ordinal: int
) -> dict[str, object]:
    """Reject even internally coherent selector-book substitution."""
    persisted_row = _mapping(persisted, label="persisted combined science")
    replayed_row = _mapping(replayed, label="replayed combined science")
    normalized_slate_for_grader_v1(persisted_row, source_ordinal=source_ordinal)
    normalized_slate_for_grader_v1(replayed_row, source_ordinal=source_ordinal)
    if batch.canonical_json_bytes(persisted_row) != batch.canonical_json_bytes(replayed_row):
        _fail("persisted combined science differs from exact frozen-source replay")
    return persisted_row


__all__ = [
    "ADAPTER_ID",
    "ENTRY_BUDGET",
    "HARD230_SOURCE_ID",
    "INCUMBENT_SOURCE_ID",
    "PROFILE_SOURCE_IDS",
    "RESULT_SCHEMA",
    "SOURCE_ORDER",
    "CorpusR6CombinedPopulationAllBlockV1Error",
    "build_combined_union_v1",
    "build_population_source_v1",
    "project_hard230_challenger_source_v1",
    "project_incumbent_current_r6_source_v1",
    "project_profile_sources_v1",
    "run_combined_population_all_block_v1",
    "validate_exact_science_replay_v1",
    "normalized_slate_for_grader_v1",
    "validate_population_source_v1",
]
