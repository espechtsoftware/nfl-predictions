from __future__ import annotations

from collections import Counter
from dataclasses import replace
from hashlib import sha256

import numpy as np
import pytest

from nfl_dfs.research import (
    corpus_r6_current_bank_crossed_screen_contract_v1 as current_contract,
)
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
    corpus_r6_population_challenger_authority_v1 as population_authority,
)
from nfl_dfs.research import (
    corpus_r6_population_challenger_runtime_v1 as population_runtime,
)
from nfl_dfs.research import (
    corpus_r6_population_crossed_scoring_v1 as crossed,
)
from nfl_dfs.research import corpus_r6_population_profiles_v1 as profiles
from nfl_dfs.research import lr8_later_period_source as later
from nfl_dfs.research import residual_world_columns as rw


def _players(variant_count: int = 151) -> tuple[rw.PlayerSpec, ...]:
    rows = [
        ("dst-i", "DST", "I", "J", "g5"),
        ("q-a", "QB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"),
        ("rb-c", "RB", "C", "D", "g2"),
        ("rb-e", "RB", "E", "F", "g3"),
        ("te-g", "TE", "G", "H", "g4"),
        ("wr-a", "WR", "A", "B", "g1"),
        ("wr-c", "WR", "C", "D", "g2"),
        ("wr-d", "WR", "D", "C", "g2"),
        ("wr-f", "WR", "F", "E", "g3"),
    ]
    rows.extend(
        (f"wr-e-{ordinal:03d}", "WR", "E", "F", "g3")
        for ordinal in range(variant_count)
    )
    return tuple(sorted((
        rw.PlayerSpec(player_id, position, team, opponent, game_id, 5_500)
        for player_id, position, team, opponent, game_id in rows
    ), key=lambda player: player.player_id))


def _roster(profile_id: str, variant: int) -> tuple[str, ...]:
    variable = f"wr-e-{variant:03d}"
    if profile_id == profiles.PROFILE_ORDER[-1]:
        values = (
            "q-a", "rb-b", "rb-c", "wr-a", "wr-d", variable, "wr-f",
            "te-g", "dst-i",
        )
    else:
        values = (
            "q-a", "rb-c", "rb-e", "wr-c", "wr-d", variable, "wr-f",
            "te-g", "dst-i",
        )
    return tuple(sorted(values))


def _artifact_hashes() -> dict[str, str]:
    return {
        block: sha256(f"artifact-{block}".encode()).hexdigest()
        for block in rw.WORLD_BLOCKS
    }


def _source_authority() -> dict[str, object]:
    artifacts = _artifact_hashes()
    body = {
        "schema": population_runtime.SOURCE_AUTHORITY_SCHEMA,
        "source_ordinal": 0,
        "slate_id": "2023-w01",
        "projection_bundle_identity": {
            "uri": "gs://fixture/projection.json",
            "generation": "1",
            "sha256": "a" * 64,
            "bytes": 1,
        },
        "projection_bundle_sha256": "b" * 64,
        "later_source_identity": {
            "uri": "gs://fixture/later.json",
            "generation": "2",
            "sha256": "c" * 64,
            "bytes": 1,
        },
        "world_artifact_identities": {
            f"world_artifact_{block.casefold()}": {
                "uri": f"gs://fixture/{block}.npz",
                "generation": str(10 + ordinal),
                "sha256": artifacts[block],
                "bytes": 1,
            }
            for ordinal, block in enumerate(rw.WORLD_BLOCKS)
        },
        "world_artifact_identities_sha256": "d" * 64,
        "source_bank_task_result_identity": {
            "uri": "gs://fixture/task.json",
            "generation": "3",
            "sha256": "e" * 64,
            "bytes": 1,
        },
        "fold_projection_sha256s": [str(index) * 64 for index in range(1, 6)],
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
    }
    return {
        **body,
        "source_authority_sha256": population_authority.canonical_sha256_v1(body),
    }


def _prepared(players: tuple[rw.PlayerSpec, ...]) -> later.PreparedLaterSlate:
    columns = np.arange(
        len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK, dtype=np.float32
    )
    draws = np.empty((len(players), len(columns)), dtype=np.float32, order="C")
    for ordinal in range(len(players)):
        draws[ordinal] = (
            np.float32(ordinal) * np.float32(0.125)
            + (columns % np.float32(97.0)) * np.float32(0.03125)
        )
    draws.flags.writeable = False
    return later.PreparedLaterSlate(
        season=2023,
        week=1,
        slate_id="2023-w01",
        players=players,
        world_ids=tuple(
            rw.WorldId(block, index)
            for block in rw.WORLD_BLOCKS
            for index in range(rw.WORLDS_PER_BLOCK)
        ),
        player_draws=draws,
        incumbent_candidates=(),
        source_freeze_sha256="f" * 64,
        artifact_sha256_by_block=_artifact_hashes(),
    )


def _profile_lineups(
    *,
    players: tuple[rw.PlayerSpec, ...],
    profile_id: str,
    unique_count: int = 150,
    heldout_only_extra: bool = True,
) -> dict[str, object]:
    attempts = unique_count + int(heldout_only_extra)
    work = profiles.SharedSolverWork(solve_attempts_per_block=attempts)
    profile = profiles.population_profile_v1(profile_id)
    source = _source_authority()
    schedule = [
        {"block": block, "index": local}
        for block in rw.WORLD_BLOCKS
        for local in range(attempts)
    ]
    shapes = {
        variant: profiles.audit_profile_roster_v1(
            players, _roster(profile_id, variant), profile_id
        )
        for variant in range(unique_count + int(heldout_only_extra))
    }
    visits: list[dict[str, object]] = []
    observed: list[tuple[str, ...]] = []
    profile_index = profiles.PROFILE_ORDER.index(profile_id)
    for visit_ordinal, world in enumerate(schedule):
        local = int(world["index"])
        variant = local
        if heldout_only_extra and local == unique_count and world["block"] != "R4":
            variant = 0
        roster = _roster(profile_id, variant)
        observed.append(roster)
        shape = shapes[variant]
        lineup = population_runtime._lineup_identity_v1(
            slate_id="2023-w01",
            profile_id=profile_id,
            profile_sha256=profile.fingerprint,
            roster=roster,
        )
        visit_body = {
            "schema": population_runtime.VISIT_RESULT_SCHEMA,
            "visit_ordinal": visit_ordinal,
            "world": world,
            "construction_serial": profile_index * len(schedule) + visit_ordinal,
            "objective_micro_sha256": profiles.canonical_sha256_v1(
                [visit_ordinal]
            ),
            "lineup_identity": lineup,
            "profile_shape": {
                key: shape[key] for key in (
                    "salary", "qb_partner_count", "bring_back_count",
                    "opposing_wr_count", "max_from_game", "rb_vs_dst_count",
                    "same_team_rb_pair_count",
                )
            },
            "primary_optimum_micro": 0,
            "secondary_rank_sum": 0,
            "lexicographic_radix": 1,
            "combined_optimum": 0,
            "solver_proof_sha256": None,
            "solver_proof": None,
        }
        visits.append({
            **visit_body,
            "visit_result_sha256": profiles.canonical_sha256_v1(visit_body),
        })
    counts = Counter(observed)
    first: dict[tuple[str, ...], int] = {}
    for ordinal, roster in enumerate(observed):
        first.setdefault(roster, ordinal)
    unique = [
        {
            "first_visit_ordinal": first_ordinal,
            "occurrence_count": counts[roster],
            "lineup_identity": population_runtime._lineup_identity_v1(
                slate_id="2023-w01",
                profile_id=profile_id,
                profile_sha256=profile.fingerprint,
                roster=roster,
            ),
        }
        for roster, first_ordinal in sorted(first.items(), key=lambda row: row[1])
    ]
    body = {
        "schema": population_authority.PROFILE_LINEUPS_SCHEMA,
        "slate": {"season": 2023, "week": 1, "slate_id": "2023-w01"},
        "source_authority": source,
        "source_authority_sha256": source["source_authority_sha256"],
        "profile": profile.payload(),
        "profile_sha256": profile.fingerprint,
        "profile_registry_sha256": profiles.population_profile_registry_v1()[
            "registry_sha256"
        ],
        "work": work.payload(),
        "work_sha256": profiles.canonical_sha256_v1(work.payload()),
        "world_schedule": schedule,
        "world_schedule_sha256": profiles.canonical_sha256_v1(schedule),
        "attempt_count": len(visits),
        "all_attempts_optimal": True,
        "visit_results": visits,
        "visit_results_sha256": profiles.canonical_sha256_v1(visits),
        "unique_lineup_count": len(unique),
        "unique_lineups": unique,
        "unique_lineups_sha256": profiles.canonical_sha256_v1(unique),
        "solver_authority": None,
        "solver_authority_sha256": None,
        "authoritative_solver_proofs_complete": False,
        "raw_solver_log_and_solution_bodies_persisted": False,
        "outcome_fields_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_performed": False,
        "production_default_change_licensed": False,
        "promotion_authority": False,
        "test_only": True,
    }
    result = {
        **body,
        "lineups_sha256": profiles.canonical_sha256_v1(body),
    }
    return population_runtime.validate_profile_lineups_v1(result, players=players)


@pytest.fixture(scope="module")
def population_fixture():
    players = _players()
    prepared = _prepared(players)
    lineups = {
        profile_id: _profile_lineups(players=players, profile_id=profile_id)
        for profile_id in profiles.PROFILE_ORDER
    }
    plan = crossed.build_population_crossed_fold_plan_v1(
        profile_lineups_by_id=lineups,
        prepared=prepared,
        heldout_block="R4",
    )
    return players, prepared, lineups, plan


def test_fold_plan_excludes_heldout_visits_and_retains_exact_provenance(
    population_fixture,
):
    _players_value, _prepared_value, _lineups, plan = population_fixture
    assert plan["common_count"] == 150
    assert plan["training_blocks"] == ["R0", "R1", "R2", "R3"]
    assert plan["score_values_read_for_sampling"] is False
    for profile_plan in plan["profiles"]:
        profile_id = profile_plan["profile_id"]
        heldout_only_id = population_runtime._lineup_identity_v1(
            slate_id="2023-w01",
            profile_id=profile_id,
            profile_sha256=profiles.population_profile_v1(profile_id).fingerprint,
            roster=_roster(profile_id, 150),
        )["lineup_sha256"]
        assert profile_plan["eligible_lineup_count"] == 150
        assert heldout_only_id not in {
            row["lineup_id"]
            for row in profile_plan["eligible_candidate_rows"]
        }
        variant_zero_id = population_runtime._lineup_identity_v1(
            slate_id="2023-w01",
            profile_id=profile_id,
            profile_sha256=profiles.population_profile_v1(profile_id).fingerprint,
            roster=_roster(profile_id, 0),
        )["lineup_sha256"]
        row = next(
            item for item in profile_plan["eligible_candidate_rows"]
            if item["lineup_id"] == variant_zero_id
        )
        assert row["training_occurrence_counts_by_block"] == {
            block: 2 for block in ("R0", "R1", "R2", "R3")
        }
        assert row["training_occurrence_count"] == 8
        assert row["training_source_arms"] == [profile_id]


def test_materialized_fit_and_heldout_scores_have_exact_order_dtype_and_sums(
    population_fixture,
):
    players, prepared, _lineups, plan = population_fixture
    result = crossed.materialize_population_crossed_profile_fold_v1(
        plan=plan, prepared=prepared, profile_id=profiles.PROFILE_ORDER[-1]
    )
    selection = result.selection
    evaluation = result.evaluation
    assert selection.training_score_matrix.shape == (150, 40_000)
    assert evaluation.heldout_score_matrix.shape == (150, 10_000)
    assert selection.training_score_matrix.dtype == np.dtype(np.float64)
    assert selection.training_score_matrix.flags.c_contiguous
    assert evaluation.heldout_score_matrix.flags.c_contiguous
    assert selection.training_score_matrix.flags.writeable is False
    assert evaluation.heldout_score_matrix.flags.writeable is False

    player_index = {player.player_id: index for index, player in enumerate(players)}
    roster = selection.candidate_rows[0]["roster_player_ids"]
    rows = [player_index[player_id] for player_id in roster]
    expected_fit = np.concatenate([
        prepared.player_draws[
            rows,
            ordinal * rw.WORLDS_PER_BLOCK:(ordinal + 1) * rw.WORLDS_PER_BLOCK,
        ].sum(axis=0, dtype=np.float64)
        for ordinal in range(4)
    ])
    expected_heldout = prepared.player_draws[
        rows, 4 * rw.WORLDS_PER_BLOCK:5 * rw.WORLDS_PER_BLOCK
    ].sum(axis=0, dtype=np.float64)
    np.testing.assert_array_equal(selection.training_score_matrix[0], expected_fit)
    np.testing.assert_array_equal(
        evaluation.heldout_score_matrix[0], expected_heldout
    )


def test_heldout_draw_changes_cannot_change_sampling_or_fit_matrix(
    population_fixture,
):
    _players_value, prepared, _lineups, plan = population_fixture
    first = crossed.materialize_population_crossed_profile_fold_v1(
        plan=plan, prepared=prepared, profile_id=profiles.PROFILE_ORDER[0]
    )
    changed_draws = prepared.player_draws.copy(order="C")
    changed_draws[:, 4 * rw.WORLDS_PER_BLOCK:] += np.float32(1_000.0)
    changed_draws.flags.writeable = False
    changed = crossed.materialize_population_crossed_profile_fold_v1(
        plan=plan,
        prepared=replace(prepared, player_draws=changed_draws),
        profile_id=profiles.PROFILE_ORDER[0],
    )
    assert first.selection.sampled_lineup_ids == changed.selection.sampled_lineup_ids
    assert first.selection.candidate_rows == changed.selection.candidate_rows
    assert first.selection.binding == changed.selection.binding
    np.testing.assert_array_equal(
        first.selection.training_score_matrix,
        changed.selection.training_score_matrix,
    )
    assert not np.array_equal(
        first.evaluation.heldout_score_matrix,
        changed.evaluation.heldout_score_matrix,
    )


def test_selector_dispatch_receives_only_fit_matrix_and_actual_profile_arm(
    population_fixture, monkeypatch: pytest.MonkeyPatch,
):
    _players_value, prepared, _lineups, plan = population_fixture
    selection = crossed.materialize_population_crossed_profile_fold_v1(
        plan=plan, prepared=prepared, profile_id=profiles.PROFILE_ORDER[-1]
    ).selection
    calls: list[dict[str, object]] = []

    def _capture(**kwargs):
        calls.append(kwargs)
        return {"result_sha256": f"{len(calls)}" * 64}

    monkeypatch.setattr(successor, "run_grouped_native_selectors_v1", _capture)
    monkeypatch.setattr(rank150, "run_exact_rank150_continuation_v1", _capture)
    monkeypatch.setattr(diversity, "run_effective_independent_shots_selector_v1", _capture)
    result = crossed.run_population_crossed_selectors_v1(selection)
    assert len(calls) == 3
    assert result["source_arm_id"] == "F9-single-partner"
    assert result["heldout_matrix_or_digest_read"] is False
    for call in calls:
        assert call["source_arm_registry"] == ["F9-single-partner"]
        assert call["training_score_matrix"] is selection.training_score_matrix
        assert call["candidate_rows"][0]["training_source_arms"] == [
            "F9-single-partner"
        ]
        assert "heldout_score_matrix" not in call


def test_unknown_players_fail_and_selected_heldout_rows_preserve_selector_order(
    population_fixture,
):
    _players_value, prepared, _lineups, plan = population_fixture
    result = crossed.materialize_population_crossed_profile_fold_v1(
        plan=plan, prepared=prepared, profile_id=profiles.PROFILE_ORDER[1]
    )
    selected = [
        result.evaluation.sampled_lineup_ids[7],
        result.evaluation.sampled_lineup_ids[2],
    ]
    rows = crossed.heldout_scores_for_selected_lineups_v1(
        result.evaluation, selected_lineup_ids=selected
    )
    np.testing.assert_array_equal(
        rows[0], result.evaluation.heldout_score_matrix[7]
    )
    np.testing.assert_array_equal(
        rows[1], result.evaluation.heldout_score_matrix[2]
    )
    with pytest.raises(
        crossed.CorpusR6PopulationCrossedScoringV1Error,
        match="unknown players",
    ):
        crossed._score_rosters_v1(
            prepared=prepared,
            rosters=[(*_roster(profiles.PROFILE_ORDER[0], 0)[:-1], "unknown")],
            blocks=("R0",),
        )


def test_common_sample_caps_at_250_and_plan_fails_below_150(population_fixture):
    players, prepared, _lineups, _plan = population_fixture
    ids = [f"{index:064x}" for index in range(300)]
    seed = {"slate_id": "2023-w01", "heldout_block": "R4"}
    sample = crossed._sample_ids_v1(ids, target=250, seed_material=seed)
    assert len(sample) == 250
    assert sample == crossed._sample_ids_v1(ids, target=250, seed_material=seed)
    too_small = {
        profile_id: _profile_lineups(
            players=players,
            profile_id=profile_id,
            unique_count=149,
            heldout_only_extra=False,
        )
        for profile_id in profiles.PROFILE_ORDER
    }
    with pytest.raises(
        crossed.CorpusR6PopulationCrossedScoringV1Error,
        match="fewer than 150",
    ):
        crossed.build_population_crossed_fold_plan_v1(
            profile_lineups_by_id=too_small,
            prepared=prepared,
            heldout_block="R4",
        )


def _selector_fixture(source_arm: str):
    ids = [f"{index:064x}" for index in range(150)]
    blocks = ["R0", "R1", "R2", "R3"]
    candidates = [
        {
            "lineup_id": lineup_id,
            "roster_player_ids": [f"p{index:02d}" for index in range(9)],
            "training_origin_blocks": blocks,
            "training_source_arms": [source_arm],
            "training_occurrence_counts_by_block": {
                block: 1 for block in blocks
            },
            "training_source_arms_by_block": {
                block: [source_arm] for block in blocks
            },
            "training_occurrence_count": 4,
        }
        for lineup_id in ids
    ]
    scores = np.ascontiguousarray(
        np.arange(150 * 32, dtype=np.float64).reshape(150, 32) / 10.0
    )
    return ids, candidates, scores, blocks


def test_all_selector_seams_accept_actual_population_arm_and_default_is_identical():
    profile_id = profiles.PROFILE_ORDER[0]
    ids, candidates, scores, blocks = _selector_fixture(profile_id)
    presets = successor.frozen_native_preset_registry_v1()
    grouped = successor.run_grouped_native_selectors_v1(
        sampled_lineup_ids=ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=8,
        preset_registry=presets,
        source_arm_registry=[profile_id],
    )
    ranked = rank150.run_exact_rank150_continuation_v1(
        sampled_lineup_ids=ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=8,
        preset_registry=presets,
        source_arm_registry=[profile_id],
    )
    dpp = diversity.run_effective_independent_shots_selector_v1(
        sampled_lineup_ids=ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=8,
        source_arm_registry=[profile_id],
    )
    assert grouped["selector_count"] == 3
    assert ranked["ranking_depth"] == 150
    assert dpp["entry_budget"] == 150

    current_arm = str(current_contract.PROFILE_IDENTITIES[0][1])
    ids, candidates, scores, blocks = _selector_fixture(current_arm)
    legacy = successor.run_grouped_native_selectors_v1(
        sampled_lineup_ids=ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=8,
        preset_registry=presets,
    )
    explicit = successor.run_grouped_native_selectors_v1(
        sampled_lineup_ids=ids,
        training_score_matrix=scores,
        candidate_rows=candidates,
        training_blocks=blocks,
        worlds_per_block=8,
        preset_registry=presets,
        source_arm_registry=[current_arm],
    )
    assert successor._canonical(legacy) == successor._canonical(explicit)
