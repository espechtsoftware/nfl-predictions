"""Outcome-blind F7/F8/F9 population-to-selector scoring bridge.

The population runtime emits one visit ledger per named construction profile.
This module rotates those ledgers by R block, excludes the held-out visits,
freezes an equal-count sample across the three profiles, and cross-scores only
that sample against the already-prepared player-world draws.  Selection and
evaluation are deliberately separate objects: selector entry points cannot
receive the held-out matrix by accident.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from typing import Final

import numpy as np

from nfl_dfs.research import (
    corpus_r6_current_bank_diversity_selector_v1 as diversity,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_rank150_v1 as rank150,
)
from nfl_dfs.research import (
    corpus_r6_current_bank_selector_successor_v1 as successor,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as population_runtime,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw


PLAN_SCHEMA: Final = "corpus-r6-population-crossed-fold-plan/v1"
PROFILE_PLAN_SCHEMA: Final = "corpus-r6-population-crossed-profile-plan/v1"
SELECTION_BINDING_SCHEMA: Final = (
    "corpus-r6-population-crossed-selection-input/v1"
)
EVALUATION_BINDING_SCHEMA: Final = (
    "corpus-r6-population-crossed-evaluation-input/v1"
)
SELECTOR_RESULT_SCHEMA: Final = (
    "corpus-r6-population-crossed-selector-result/v1"
)
MINIMUM_COMMON_COUNT: Final = rank150.RANKING_DEPTH
MAXIMUM_COMMON_COUNT: Final = successor.MAX_CANDIDATES


class CorpusR6PopulationCrossedScoringV1Error(ValueError):
    """The population crossed-scoring bridge failed closed."""


def _fail(message: str) -> None:
    raise CorpusR6PopulationCrossedScoringV1Error(message)


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be a string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        _fail(f"{label} must be an ordered array")
    return list(value)


def _hash(value: object) -> str:
    return profiles.canonical_sha256_v1(value)


def _with_hash(
    value: Mapping[str, object], *, field_name: str
) -> dict[str, object]:
    body = dict(value)
    if field_name in body:
        _fail(f"{field_name} is already present")
    return {**body, field_name: _hash(body)}


def _matrix_hash(value: np.ndarray, *, label: str) -> str:
    matrix = np.asarray(value)
    if (
        matrix.dtype != np.dtype(np.float64)
        or matrix.ndim != 2
        or not matrix.flags.c_contiguous
    ):
        _fail(f"{label} must be one C-contiguous float64 matrix")
    digest = sha256()
    digest.update(profiles.canonical_json_bytes_v1({
        "dtype": "float64-le",
        "shape": [int(item) for item in matrix.shape],
    }))
    digest.update(b"\0")
    little = np.ascontiguousarray(matrix, dtype="<f8")
    digest.update(memoryview(little).cast("B"))
    return digest.hexdigest()


def _validate_prepared_slate_v1(prepared: object) -> later.PreparedLaterSlate:
    if not isinstance(prepared, later.PreparedLaterSlate):
        _fail("prepared slate type differs")
    player_ids = [player.player_id for player in prepared.players]
    expected_worlds = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(rw.WORLDS_PER_BLOCK)
    )
    draws = np.asarray(prepared.player_draws)
    if (
        not player_ids
        or len(player_ids) != len(set(player_ids))
        or draws is not prepared.player_draws
        or draws.dtype != np.dtype(np.float32)
        or draws.shape != (len(player_ids), len(expected_worlds))
        or not draws.flags.c_contiguous
        or prepared.world_ids != expected_worlds
        or set(prepared.artifact_sha256_by_block) != set(rw.WORLD_BLOCKS)
    ):
        _fail("prepared five-block player-draw authority differs")
    return prepared


def _candidate_rows_for_fit_v1(
    profile_lineups: Mapping[str, object], *, heldout_block: str
) -> list[dict[str, object]]:
    profile = _mapping(profile_lineups.get("profile"), label="profile")
    profile_id = str(profile.get("profile_id"))
    training_blocks = tuple(
        block for block in rw.WORLD_BLOCKS if block != heldout_block
    )
    roster_by_id: dict[str, tuple[str, ...]] = {}
    counts_by_id: dict[str, Counter[str]] = {}
    for raw in _sequence(
        profile_lineups.get("visit_results"), label="profile visit results"
    ):
        visit = _mapping(raw, label="profile visit result")
        world = _mapping(visit.get("world"), label="visit world")
        block = str(world.get("block"))
        lineup = _mapping(visit.get("lineup_identity"), label="lineup identity")
        lineup_id = str(lineup.get("lineup_sha256"))
        roster = tuple(
            str(player_id)
            for player_id in _sequence(lineup.get("roster"), label="lineup roster")
        )
        prior = roster_by_id.setdefault(lineup_id, roster)
        if prior != roster:
            _fail("one lineup identity maps to multiple rosters")
        if block == heldout_block:
            continue
        if block not in training_blocks:
            _fail("visit block lies outside the canonical fold")
        counts_by_id.setdefault(lineup_id, Counter())[block] += 1

    rows: list[dict[str, object]] = []
    for lineup_id in sorted(counts_by_id):
        counts = counts_by_id[lineup_id]
        by_block = {block: int(counts[block]) for block in training_blocks}
        arms_by_block = {
            block: ([profile_id] if by_block[block] > 0 else [])
            for block in training_blocks
        }
        rows.append({
            "lineup_id": lineup_id,
            "roster_player_ids": list(roster_by_id[lineup_id]),
            "training_origin_blocks": [
                block for block in training_blocks if by_block[block] > 0
            ],
            "training_source_arms": [profile_id],
            "training_occurrence_counts_by_block": by_block,
            "training_source_arms_by_block": arms_by_block,
            "training_occurrence_count": sum(by_block.values()),
        })
    try:
        successor._validated_candidates(
            rows,
            sampled_lineup_ids=[str(row["lineup_id"]) for row in rows],
            training_blocks=training_blocks,
            source_arm_registry=[profile_id],
        )
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6PopulationCrossedScoringV1Error(str(exc)) from exc
    return rows


def _sample_ids_v1(
    eligible_ids: Sequence[str], *, target: int, seed_material: Mapping[str, object]
) -> list[str]:
    ids = [str(value) for value in eligible_ids]
    if (
        ids != sorted(set(ids))
        or not MINIMUM_COMMON_COUNT <= target <= MAXIMUM_COMMON_COUNT
        or len(ids) < target
    ):
        _fail("equal-count sample inputs differ")
    if len(ids) == target:
        return ids
    seed = profiles.canonical_json_bytes_v1(dict(seed_material))
    ranked = sorted(
        ids,
        key=lambda lineup_id: (
            sha256(seed + b"\0" + lineup_id.encode("utf-8")).digest(),
            lineup_id,
        ),
    )
    return sorted(ranked[:target])


def _source_artifact_hashes_v1(
    source: Mapping[str, object], *, prepared: later.PreparedLaterSlate
) -> dict[str, str]:
    raw = _mapping(
        source.get("world_artifact_identities"),
        label="source world artifact identities",
    )
    expected_keys = [
        f"world_artifact_{block.casefold()}" for block in rw.WORLD_BLOCKS
    ]
    if list(raw) != expected_keys:
        _fail("source world artifact key order differs")
    hashes: dict[str, str] = {}
    for block, key in zip(rw.WORLD_BLOCKS, expected_keys, strict=True):
        identity = _mapping(raw[key], label=f"{block} world artifact identity")
        digest = identity.get("sha256")
        if type(digest) is not str or digest != prepared.artifact_sha256_by_block[block]:
            _fail("prepared/source world artifact hash differs")
        hashes[block] = digest
    return hashes


def build_population_crossed_fold_plan_v1(
    *,
    profile_lineups_by_id: object,
    prepared: object,
    heldout_block: str,
) -> dict[str, object]:
    """Freeze one score-blind equal-count plan for all three population arms."""
    retained = _validate_prepared_slate_v1(prepared)
    if heldout_block not in rw.WORLD_BLOCKS:
        _fail("heldout block must be one canonical R block")
    if not isinstance(profile_lineups_by_id, Mapping) or set(
        profile_lineups_by_id
    ) != set(profiles.PROFILE_ORDER):
        _fail("profile lineup mapping must contain exactly F7/F8/F9")

    validated: dict[str, dict[str, object]] = {}
    for profile_id in profiles.PROFILE_ORDER:
        try:
            body = population_runtime.validate_profile_lineups_v1(
                profile_lineups_by_id[profile_id], players=retained.players
            )
        except (
            population_runtime.CorpusR6PopulationChallengerRuntimeV1Error,
            profiles.CorpusR6PopulationProfileError,
        ) as exc:
            raise CorpusR6PopulationCrossedScoringV1Error(
                f"{profile_id} lineups are invalid: {exc}"
            ) from exc
        if (
            body["profile"]["profile_id"] != profile_id
            or body["slate"]["slate_id"] != retained.slate_id
            or body["slate"]["season"] != retained.season
            or body["slate"]["week"] != retained.week
        ):
            _fail("profile/slate identity differs from prepared draws")
        validated[profile_id] = body

    source_hashes = {
        str(body["source_authority_sha256"]) for body in validated.values()
    }
    work_hashes = {str(body["work_sha256"]) for body in validated.values()}
    schedule_hashes = {
        str(body["world_schedule_sha256"]) for body in validated.values()
    }
    if any(len(values) != 1 for values in (
        source_hashes, work_hashes, schedule_hashes
    )):
        _fail("F7/F8/F9 do not share one source, work dose, and visit schedule")
    source = _mapping(
        validated[profiles.PROFILE_ORDER[0]]["source_authority"],
        label="shared source authority",
    )
    if any(body["source_authority"] != source for body in validated.values()):
        _fail("F7/F8/F9 source authority bodies differ")
    artifact_hashes = _source_artifact_hashes_v1(source, prepared=retained)

    training_blocks = [
        block for block in rw.WORLD_BLOCKS if block != heldout_block
    ]
    eligible_by_profile = {
        profile_id: _candidate_rows_for_fit_v1(
            validated[profile_id], heldout_block=heldout_block
        )
        for profile_id in profiles.PROFILE_ORDER
    }
    common_count = min(
        MAXIMUM_COMMON_COUNT,
        *(len(rows) for rows in eligible_by_profile.values()),
    )
    if common_count < MINIMUM_COMMON_COUNT:
        _fail(
            "population fold has fewer than 150 fit-eligible unique lineups "
            "in at least one profile"
        )
    seed_material = {
        "schema": PLAN_SCHEMA,
        "purpose": "outcome-blind-equal-count-population-profile-sample",
        "slate_id": retained.slate_id,
        "heldout_block": heldout_block,
    }
    by_id = {
        profile_id: {
            str(row["lineup_id"]): row
            for row in eligible_by_profile[profile_id]
        }
        for profile_id in profiles.PROFILE_ORDER
    }
    profile_plans: list[dict[str, object]] = []
    for profile_id in profiles.PROFILE_ORDER:
        eligible = eligible_by_profile[profile_id]
        eligible_ids = [str(row["lineup_id"]) for row in eligible]
        sampled_ids = _sample_ids_v1(
            eligible_ids, target=common_count, seed_material=seed_material
        )
        sampled = [by_id[profile_id][lineup_id] for lineup_id in sampled_ids]
        profile_plans.append(_with_hash({
            "schema": PROFILE_PLAN_SCHEMA,
            "profile_id": profile_id,
            "source_arm_id": profile_id,
            "profile_sha256": validated[profile_id]["profile_sha256"],
            "profile_lineups_sha256": validated[profile_id]["lineups_sha256"],
            "eligible_lineup_count": len(eligible),
            "eligible_candidate_rows": eligible,
            "eligible_candidate_rows_sha256": _hash(eligible),
            "sampled_lineup_count": len(sampled_ids),
            "sampled_lineup_ids": sampled_ids,
            "sampled_lineup_ids_sha256": _hash(sampled_ids),
            "sampled_candidate_rows": sampled,
            "sampled_candidate_rows_sha256": _hash(sampled),
            "heldout_visits_excluded_from_eligibility": True,
            "uses_realized_outcomes": False,
        }, field_name="profile_plan_sha256"))

    body = {
        "schema": PLAN_SCHEMA,
        "slate": {
            "season": retained.season,
            "week": retained.week,
            "slate_id": retained.slate_id,
        },
        "heldout_block": heldout_block,
        "training_blocks": training_blocks,
        "worlds_per_block": rw.WORLDS_PER_BLOCK,
        "common_count": common_count,
        "common_count_law": "min-250-and-smallest-profile-fit-eligible-count",
        "minimum_common_count": MINIMUM_COMMON_COUNT,
        "maximum_common_count": MAXIMUM_COMMON_COUNT,
        "sample_seed_material": seed_material,
        "sample_seed_material_sha256": _hash(seed_material),
        "profile_order": list(profiles.PROFILE_ORDER),
        "profiles": profile_plans,
        "profile_plan_sha256s": [
            row["profile_plan_sha256"] for row in profile_plans
        ],
        "source_authority_sha256": next(iter(source_hashes)),
        "work_sha256": next(iter(work_hashes)),
        "world_schedule_sha256": next(iter(schedule_hashes)),
        "prepared_player_ids_sha256": _hash([
            player.player_id for player in retained.players
        ]),
        "world_artifact_sha256_by_block": artifact_hashes,
        "score_values_read_for_sampling": False,
        "heldout_score_values_read_for_sampling": False,
        "realized_outcomes_read": False,
    }
    return validate_population_crossed_fold_plan_v1(
        _with_hash(body, field_name="plan_sha256")
    )


def validate_population_crossed_fold_plan_v1(
    value: object,
) -> dict[str, object]:
    plan = _mapping(value, label="population crossed fold plan")
    if plan.get("schema") != PLAN_SCHEMA or plan.get("plan_sha256") != _hash({
        key: item for key, item in plan.items() if key != "plan_sha256"
    }):
        _fail("population crossed fold plan schema/self-hash differs")
    heldout = plan.get("heldout_block")
    training_blocks = [block for block in rw.WORLD_BLOCKS if block != heldout]
    if (
        heldout not in rw.WORLD_BLOCKS
        or plan.get("training_blocks") != training_blocks
        or plan.get("worlds_per_block") != rw.WORLDS_PER_BLOCK
        or plan.get("minimum_common_count") != MINIMUM_COMMON_COUNT
        or plan.get("maximum_common_count") != MAXIMUM_COMMON_COUNT
        or plan.get("profile_order") != list(profiles.PROFILE_ORDER)
        or plan.get("sample_seed_material_sha256")
        != _hash(plan.get("sample_seed_material"))
        or plan.get("score_values_read_for_sampling") is not False
        or plan.get("heldout_score_values_read_for_sampling") is not False
        or plan.get("realized_outcomes_read") is not False
    ):
        _fail("population crossed fold fixed authority differs")
    rows = [
        _mapping(raw, label="population profile plan")
        for raw in _sequence(plan.get("profiles"), label="profile plans")
    ]
    if (
        [row.get("profile_id") for row in rows] != list(profiles.PROFILE_ORDER)
        or plan.get("profile_plan_sha256s")
        != [row.get("profile_plan_sha256") for row in rows]
    ):
        _fail("population profile-plan order differs")
    counts: list[int] = []
    common_count = plan.get("common_count")
    if type(common_count) is not int:
        _fail("population common count must be an exact integer")
    for profile_id, row in zip(profiles.PROFILE_ORDER, rows, strict=True):
        if row.get("profile_plan_sha256") != _hash({
            key: item for key, item in row.items() if key != "profile_plan_sha256"
        }):
            _fail("population profile plan self-hash differs")
        eligible = [
            _mapping(item, label="eligible candidate")
            for item in _sequence(
                row.get("eligible_candidate_rows"), label="eligible candidates"
            )
        ]
        eligible_ids = [str(item.get("lineup_id")) for item in eligible]
        sampled_ids = [
            str(item) for item in _sequence(
                row.get("sampled_lineup_ids"), label="sampled lineup ids"
            )
        ]
        sampled = [
            _mapping(item, label="sampled candidate")
            for item in _sequence(
                row.get("sampled_candidate_rows"), label="sampled candidates"
            )
        ]
        expected_sampled_ids = _sample_ids_v1(
            eligible_ids,
            target=common_count,
            seed_material=_mapping(
                plan.get("sample_seed_material"), label="sample seed material"
            ),
        )
        by_id = {str(item["lineup_id"]): item for item in eligible}
        if (
            row.get("schema") != PROFILE_PLAN_SCHEMA
            or row.get("profile_id") != profile_id
            or row.get("source_arm_id") != profile_id
            or row.get("eligible_lineup_count") != len(eligible)
            or eligible_ids != sorted(set(eligible_ids))
            or row.get("eligible_candidate_rows_sha256") != _hash(eligible)
            or row.get("sampled_lineup_count") != common_count
            or sampled_ids != expected_sampled_ids
            or row.get("sampled_lineup_ids_sha256") != _hash(sampled_ids)
            or sampled != [by_id[lineup_id] for lineup_id in sampled_ids]
            or row.get("sampled_candidate_rows_sha256") != _hash(sampled)
            or row.get("heldout_visits_excluded_from_eligibility") is not True
            or row.get("uses_realized_outcomes") is not False
        ):
            _fail("population profile plan contents differ")
        try:
            successor._validated_candidates(
                eligible,
                sampled_lineup_ids=eligible_ids,
                training_blocks=training_blocks,
                source_arm_registry=[profile_id],
            )
        except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
            raise CorpusR6PopulationCrossedScoringV1Error(str(exc)) from exc
        counts.append(len(eligible))
    if common_count != min(MAXIMUM_COMMON_COUNT, *counts):
        _fail("population common-count law differs")
    return plan


@dataclass(frozen=True, slots=True)
class PopulationCrossedSelectionInputsV1:
    profile_id: str
    heldout_block_label_only: str
    training_blocks: tuple[str, ...]
    worlds_per_block: int
    sampled_lineup_ids: tuple[str, ...]
    candidate_rows: tuple[Mapping[str, object], ...]
    training_score_matrix: np.ndarray = field(compare=False, repr=False)
    binding: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PopulationCrossedEvaluationInputsV1:
    profile_id: str
    heldout_block: str
    worlds_per_block: int
    sampled_lineup_ids: tuple[str, ...]
    roster_player_ids: tuple[tuple[str, ...], ...]
    heldout_score_matrix: np.ndarray = field(compare=False, repr=False)
    binding: Mapping[str, object]


@dataclass(frozen=True, slots=True)
class PopulationCrossedFoldInputsV1:
    selection: PopulationCrossedSelectionInputsV1
    evaluation: PopulationCrossedEvaluationInputsV1


def _score_rosters_v1(
    *,
    prepared: later.PreparedLaterSlate,
    rosters: Sequence[Sequence[str]],
    blocks: Sequence[str],
) -> np.ndarray:
    player_index = {
        player.player_id: index for index, player in enumerate(prepared.players)
    }
    unknown = sorted({
        player_id
        for roster in rosters
        for player_id in roster
        if player_id not in player_index
    })
    if unknown:
        _fail(f"candidate roster contains unknown players: {unknown}")
    if (
        not blocks
        or list(blocks) != [block for block in rw.WORLD_BLOCKS if block in set(blocks)]
    ):
        _fail("score blocks must be one canonical ordered subset")
    scores = np.empty(
        (len(rosters), len(blocks) * rw.WORLDS_PER_BLOCK),
        dtype=np.float64,
        order="C",
    )
    for block_ordinal, block in enumerate(blocks):
        source_start = rw.WORLD_BLOCKS.index(block) * rw.WORLDS_PER_BLOCK
        source_stop = source_start + rw.WORLDS_PER_BLOCK
        target_start = block_ordinal * rw.WORLDS_PER_BLOCK
        target_stop = target_start + rw.WORLDS_PER_BLOCK
        for roster_ordinal, roster in enumerate(rosters):
            if len(roster) != rw.ROSTER_SIZE or len(set(roster)) != rw.ROSTER_SIZE:
                _fail("candidate roster must contain nine unique players")
            rows = [player_index[player_id] for player_id in roster]
            scores[roster_ordinal, target_start:target_stop] = (
                prepared.player_draws[rows, source_start:source_stop].sum(
                    axis=0, dtype=np.float64
                )
            )
    if not scores.flags.c_contiguous or not np.isfinite(scores).all():
        _fail("cross-scored roster matrix differs")
    scores.flags.writeable = False
    return scores


def materialize_population_crossed_profile_fold_v1(
    *, plan: object, prepared: object, profile_id: str
) -> PopulationCrossedFoldInputsV1:
    """Materialize one profile/fold at a time to bound peak matrix memory."""
    retained_plan = validate_population_crossed_fold_plan_v1(plan)
    retained = _validate_prepared_slate_v1(prepared)
    slate = _mapping(retained_plan.get("slate"), label="plan slate")
    if (
        profile_id not in profiles.PROFILE_ORDER
        or slate
        != {
            "season": retained.season,
            "week": retained.week,
            "slate_id": retained.slate_id,
        }
        or retained_plan.get("prepared_player_ids_sha256")
        != _hash([player.player_id for player in retained.players])
        or retained_plan.get("world_artifact_sha256_by_block")
        != dict(retained.artifact_sha256_by_block)
    ):
        _fail("plan/prepared/profile materialization authority differs")
    profile_plan = next(
        row for row in retained_plan["profiles"] if row["profile_id"] == profile_id
    )
    sampled_ids = tuple(str(value) for value in profile_plan["sampled_lineup_ids"])
    candidates = tuple(
        _mapping(row, label="sampled candidate")
        for row in profile_plan["sampled_candidate_rows"]
    )
    rosters = tuple(
        tuple(str(player_id) for player_id in row["roster_player_ids"])
        for row in candidates
    )
    training_blocks = tuple(str(value) for value in retained_plan["training_blocks"])
    heldout = str(retained_plan["heldout_block"])
    training_scores = _score_rosters_v1(
        prepared=retained, rosters=rosters, blocks=training_blocks
    )
    heldout_scores = _score_rosters_v1(
        prepared=retained, rosters=rosters, blocks=(heldout,)
    )
    selection_binding = _with_hash({
        "schema": SELECTION_BINDING_SCHEMA,
        "plan_sha256": retained_plan["plan_sha256"],
        "profile_id": profile_id,
        "source_arm_registry": [profile_id],
        "heldout_block_label_only": heldout,
        "training_blocks": list(training_blocks),
        "worlds_per_block": rw.WORLDS_PER_BLOCK,
        "sampled_lineup_ids_sha256": _hash(list(sampled_ids)),
        "candidate_rows_sha256": _hash(list(candidates)),
        "training_score_shape": list(training_scores.shape),
        "training_score_matrix_sha256": _matrix_hash(
            training_scores, label="training score matrix"
        ),
        "heldout_score_columns_present": False,
        "realized_outcomes_read": False,
    }, field_name="selection_binding_sha256")
    evaluation_binding = _with_hash({
        "schema": EVALUATION_BINDING_SCHEMA,
        "plan_sha256": retained_plan["plan_sha256"],
        "profile_id": profile_id,
        "heldout_block": heldout,
        "worlds_per_block": rw.WORLDS_PER_BLOCK,
        "sampled_lineup_ids_sha256": _hash(list(sampled_ids)),
        "roster_player_ids_sha256": _hash([list(roster) for roster in rosters]),
        "heldout_score_shape": list(heldout_scores.shape),
        "heldout_score_matrix_sha256": _matrix_hash(
            heldout_scores, label="heldout score matrix"
        ),
        "simulated_scores_only": True,
        "realized_outcomes_read": False,
    }, field_name="evaluation_binding_sha256")
    result = PopulationCrossedFoldInputsV1(
        selection=PopulationCrossedSelectionInputsV1(
            profile_id=profile_id,
            heldout_block_label_only=heldout,
            training_blocks=training_blocks,
            worlds_per_block=rw.WORLDS_PER_BLOCK,
            sampled_lineup_ids=sampled_ids,
            candidate_rows=candidates,
            training_score_matrix=training_scores,
            binding=selection_binding,
        ),
        evaluation=PopulationCrossedEvaluationInputsV1(
            profile_id=profile_id,
            heldout_block=heldout,
            worlds_per_block=rw.WORLDS_PER_BLOCK,
            sampled_lineup_ids=sampled_ids,
            roster_player_ids=rosters,
            heldout_score_matrix=heldout_scores,
            binding=evaluation_binding,
        ),
    )
    validate_population_crossed_selection_inputs_v1(result.selection)
    validate_population_crossed_evaluation_inputs_v1(result.evaluation)
    return result


def validate_population_crossed_selection_inputs_v1(
    value: object,
) -> PopulationCrossedSelectionInputsV1:
    if not isinstance(value, PopulationCrossedSelectionInputsV1):
        _fail("population selection input type differs")
    expected_binding = _with_hash({
        "schema": SELECTION_BINDING_SCHEMA,
        "plan_sha256": value.binding.get("plan_sha256"),
        "profile_id": value.profile_id,
        "source_arm_registry": [value.profile_id],
        "heldout_block_label_only": value.heldout_block_label_only,
        "training_blocks": list(value.training_blocks),
        "worlds_per_block": value.worlds_per_block,
        "sampled_lineup_ids_sha256": _hash(list(value.sampled_lineup_ids)),
        "candidate_rows_sha256": _hash(list(value.candidate_rows)),
        "training_score_shape": list(value.training_score_matrix.shape),
        "training_score_matrix_sha256": _matrix_hash(
            value.training_score_matrix, label="training score matrix"
        ),
        "heldout_score_columns_present": False,
        "realized_outcomes_read": False,
    }, field_name="selection_binding_sha256")
    if (
        value.profile_id not in profiles.PROFILE_ORDER
        or value.binding != expected_binding
        or value.training_score_matrix.flags.writeable
    ):
        _fail("population selection input binding differs")
    try:
        successor._validated_inputs(
            sampled_lineup_ids=value.sampled_lineup_ids,
            training_score_matrix=value.training_score_matrix,
            candidate_rows=value.candidate_rows,
            training_blocks=value.training_blocks,
            worlds_per_block=value.worlds_per_block,
            source_arm_registry=[value.profile_id],
        )
    except successor.CorpusR6CurrentBankSelectorSuccessorV1Error as exc:
        raise CorpusR6PopulationCrossedScoringV1Error(str(exc)) from exc
    return value


def validate_population_crossed_evaluation_inputs_v1(
    value: object,
) -> PopulationCrossedEvaluationInputsV1:
    if not isinstance(value, PopulationCrossedEvaluationInputsV1):
        _fail("population evaluation input type differs")
    scores = np.asarray(value.heldout_score_matrix)
    expected_binding = _with_hash({
        "schema": EVALUATION_BINDING_SCHEMA,
        "plan_sha256": value.binding.get("plan_sha256"),
        "profile_id": value.profile_id,
        "heldout_block": value.heldout_block,
        "worlds_per_block": value.worlds_per_block,
        "sampled_lineup_ids_sha256": _hash(list(value.sampled_lineup_ids)),
        "roster_player_ids_sha256": _hash([
            list(roster) for roster in value.roster_player_ids
        ]),
        "heldout_score_shape": list(scores.shape),
        "heldout_score_matrix_sha256": _matrix_hash(
            scores, label="heldout score matrix"
        ),
        "simulated_scores_only": True,
        "realized_outcomes_read": False,
    }, field_name="evaluation_binding_sha256")
    if (
        value.profile_id not in profiles.PROFILE_ORDER
        or value.heldout_block not in rw.WORLD_BLOCKS
        or value.worlds_per_block != rw.WORLDS_PER_BLOCK
        or value.sampled_lineup_ids != tuple(sorted(set(value.sampled_lineup_ids)))
        or len(value.roster_player_ids) != len(value.sampled_lineup_ids)
        or scores.shape
        != (len(value.sampled_lineup_ids), rw.WORLDS_PER_BLOCK)
        or scores.dtype != np.dtype(np.float64)
        or not scores.flags.c_contiguous
        or scores.flags.writeable
        or not np.isfinite(scores).all()
        or value.binding != expected_binding
    ):
        _fail("population evaluation input binding differs")
    return value


def heldout_scores_for_selected_lineups_v1(
    value: object, *, selected_lineup_ids: object
) -> np.ndarray:
    """Return evaluator-ready held-out rows in selector order."""
    retained = validate_population_crossed_evaluation_inputs_v1(value)
    selected = [
        str(item)
        for item in _sequence(selected_lineup_ids, label="selected lineup ids")
    ]
    if not selected or len(selected) != len(set(selected)):
        _fail("selected lineup ids must be nonempty and unique")
    ordinal = {
        lineup_id: index
        for index, lineup_id in enumerate(retained.sampled_lineup_ids)
    }
    if not set(selected) <= set(ordinal):
        _fail("selected lineup ids are outside the sampled evaluation rows")
    rows = np.ascontiguousarray(
        retained.heldout_score_matrix[[ordinal[lineup_id] for lineup_id in selected]],
        dtype=np.float64,
    )
    rows.flags.writeable = False
    return rows


def run_population_crossed_selectors_v1(value: object) -> dict[str, object]:
    """Run grouped rank-80, exact rank-150, and DPP from fit columns only."""
    selection = validate_population_crossed_selection_inputs_v1(value)
    kwargs = {
        "sampled_lineup_ids": selection.sampled_lineup_ids,
        "training_score_matrix": selection.training_score_matrix,
        "candidate_rows": selection.candidate_rows,
        "training_blocks": selection.training_blocks,
        "worlds_per_block": selection.worlds_per_block,
        "source_arm_registry": [selection.profile_id],
    }
    presets = successor.frozen_native_preset_registry_v1()
    grouped = successor.run_grouped_native_selectors_v1(
        **kwargs, preset_registry=presets
    )
    ranked = rank150.run_exact_rank150_continuation_v1(
        **kwargs, preset_registry=presets
    )
    dpp = diversity.run_effective_independent_shots_selector_v1(**kwargs)
    body = {
        "schema": SELECTOR_RESULT_SCHEMA,
        "profile_id": selection.profile_id,
        "source_arm_id": selection.profile_id,
        "heldout_block_label_only": selection.heldout_block_label_only,
        "selection_binding": dict(selection.binding),
        "selection_binding_sha256": selection.binding[
            "selection_binding_sha256"
        ],
        "grouped_result": grouped,
        "grouped_result_sha256": grouped["result_sha256"],
        "rank150_result": ranked,
        "rank150_result_sha256": ranked["result_sha256"],
        "dpp_result": dpp,
        "dpp_result_sha256": dpp["result_sha256"],
        "selector_input_source_arm_registry": [selection.profile_id],
        "heldout_score_columns_present": False,
        "heldout_matrix_or_digest_read": False,
        "realized_outcomes_read": False,
    }
    return _with_hash(body, field_name="selector_result_sha256")


__all__ = [
    "CorpusR6PopulationCrossedScoringV1Error",
    "MAXIMUM_COMMON_COUNT",
    "MINIMUM_COMMON_COUNT",
    "PopulationCrossedEvaluationInputsV1",
    "PopulationCrossedFoldInputsV1",
    "PopulationCrossedSelectionInputsV1",
    "build_population_crossed_fold_plan_v1",
    "heldout_scores_for_selected_lineups_v1",
    "materialize_population_crossed_profile_fold_v1",
    "run_population_crossed_selectors_v1",
    "validate_population_crossed_evaluation_inputs_v1",
    "validate_population_crossed_fold_plan_v1",
    "validate_population_crossed_selection_inputs_v1",
]
