from __future__ import annotations

import copy
import json

import numpy as np
import pytest

from nfl_dfs.research import corpus_r6_supported232_generation_v1 as supported


def _players() -> list[dict[str, object]]:
    # p00..p08 form one roster legal under F7, F8, and F9: exactly one
    # same-team QB catcher, one bring-back, and at most three from game g01.
    rows = [
        ("p00", "QB", "A", "B", "g01", 6000, 30.0),
        ("p01", "WR", "A", "B", "g01", 5500, 29.0),
        ("p02", "RB", "B", "A", "g01", 5500, 28.0),
        ("p03", "RB", "C", "D", "g02", 5500, 27.0),
        ("p04", "WR", "D", "C", "g02", 5500, 26.0),
        ("p05", "WR", "E", "F", "g03", 5500, 25.0),
        ("p06", "TE", "F", "E", "g03", 5500, 24.0),
        ("p07", "WR", "G", "H", "g04", 5500, 23.0),
        ("p08", "DST", "H", "G", "g04", 4500, 22.0),
    ]
    for index in range(9, 16):
        team = f"Q{index}"
        opponent = f"O{index}"
        rows.append((
            f"p{index:02d}", "QB", team, opponent, f"g{index:02d}",
            6000, float(20 - index),
        ))
    return [{
        "id": player_id,
        "pos": position,
        "team": team,
        "opp": opponent,
        "game_id": game,
        "salary": salary,
        "proj_tourney": objective,
    } for player_id, position, team, opponent, game, salary, objective in rows]


def _bundle() -> dict[str, object]:
    return supported.build_player_bundle_v1(
        slate={"season": 2023, "week": 1, "slate_id": "2023-w01"},
        players=_players(),
    )


def _draws() -> np.ndarray:
    rows = len(_players())
    worlds = np.arange(supported.WORLDS_PER_ORIGIN, dtype=np.float32)
    matrix = np.empty((rows, supported.WORLDS_PER_ORIGIN), dtype=np.float32)
    for row in range(rows):
        matrix[row] = np.float32(row + 1) + worlds / np.float32(100_000.0)
    return np.ascontiguousarray(matrix, dtype=np.float32)


def _local_request(tmp_path):
    bundle = _bundle()
    draws = _draws()
    bundle_path = tmp_path / "players.json"
    draws_path = tmp_path / "draws.npy"
    bundle_path.write_bytes(supported.canonical_json_bytes_v1(bundle))
    np.save(draws_path, draws, allow_pickle=False)
    request = supported.build_local_task_request_v1(
        player_bundle=bundle,
        player_bundle_identity=supported.local_file_identity_v1(bundle_path),
        draws_identity=supported.local_file_identity_v1(draws_path),
        draws=draws,
        origin_id="R0",
    )
    return request, bundle, draws, bundle_path, draws_path


def test_supported232_registry_is_new_and_every_arm_has_exact_equal_work():
    registry = supported.supported232_arm_registry_v1()
    assert registry["arm_order"] == list(supported.ARM_ORDER)
    assert registry["attempts_per_cell"] == 232
    assert registry["attempts_per_origin_task"] == 2784
    expected = {
        "supported232-baseline-v1": {"leverage": 160, "boom": 40, "qbvar": 32},
        "supported232-boom-heavy-v1": {"leverage": 80, "boom": 120, "qbvar": 32},
        "supported232-all-boom-v1": {"leverage": 0, "boom": 200, "qbvar": 32},
        "supported232-qbvar-expanded-v1": {"leverage": 160, "boom": 8, "qbvar": 64},
    }
    assert {
        row["arm_id"]: row["attempts_by_family"] for row in registry["arms"]
    } == expected
    assert all(sum(dose.values()) == 232 for dose in expected.values())
    assert registry["families_excluded"] == ["role", "game", "dark"]
    assert registry["legacy_266_ids_reused"] is False
    assert not set(supported.ARM_ORDER).intersection({
        "boom-heavy-equal-work-v1",
        "all-boom-equal-work-v1",
        "qbvar-expanded-equal-work-v1",
    })


def test_player_bundle_requires_exact_proj_tourney_and_canonical_alignment():
    bundle = _bundle()
    assert supported.validate_player_bundle_v1(bundle) == bundle

    missing = _players()
    del missing[0]["proj_tourney"]
    with pytest.raises(
        supported.CorpusR6Supported232GenerationV1Error,
        match="player fields differ",
    ):
        supported.build_player_bundle_v1(
            slate=bundle["slate"], players=missing
        )

    reversed_rows = list(reversed(_players()))
    with pytest.raises(
        supported.CorpusR6Supported232GenerationV1Error,
        match="canonical unique ID order",
    ):
        supported.build_player_bundle_v1(
            slate=bundle["slate"], players=reversed_rows
        )


def test_local_request_exact_opens_inputs_and_dry_validates_without_calls(tmp_path):
    request, bundle, draws, _bundle_path, draws_path = _local_request(tmp_path)
    assert supported.validate_local_task_request_v1(request) == request
    dry = supported.validate_local_task_inputs_v1(
        request, player_bundle=bundle, draws=draws
    )
    assert dry["ready_for_local_generation"] is True
    assert dry["optimizer_calls_made"] == 0
    assert dry["total_optimizer_calls"] == 2784
    assert dry["point_in_time_objective_present"] is True
    assert dry["draw_mean_substitution_used"] is False

    loaded, retained_bundle, retained_draws = (
        supported.load_and_dry_validate_local_task_v1(request)
    )
    assert loaded == dry
    assert retained_bundle == bundle
    assert np.array_equal(retained_draws, draws)

    # Exact local identity fails closed if the NPY is replaced after request.
    np.save(draws_path, draws + np.float32(1.0), allow_pickle=False)
    with pytest.raises(
        supported.CorpusR6Supported232GenerationV1Error,
        match="content identity differs",
    ):
        supported.load_and_dry_validate_local_task_v1(request)


def test_full_runtime_makes_232_calls_per_cell_and_preserves_no_good_and_locks(
    tmp_path,
):
    request, bundle, draws, _bundle_path, _draws_path = _local_request(tmp_path)
    legal_roster = tuple(f"p{index:02d}" for index in range(9))
    summaries: list[tuple[object, ...]] = []

    def fake_optimizer(spec: supported.OptimizerCallSpec):
        summaries.append((
            spec.global_call_ordinal,
            spec.arm_id,
            spec.profile_id,
            spec.family_id,
            spec.family_slot,
            spec.locks,
            len(spec.banned_lineups),
            spec.max_overlap,
        ))
        # Exercise sequential leverage feedback once in every cell. Other
        # calls are still actual callback attempts with explicit receipts.
        if spec.family_id == "leverage" and spec.family_slot == 0:
            return supported.OptimizerCallOutcome(
                status="optimal", roster=legal_roster, detail="fixture-optimal"
            )
        return supported.OptimizerCallOutcome(
            status="infeasible", detail="fixture-infeasible"
        )

    result = supported.execute_local_task_v1(
        request,
        player_bundle=bundle,
        draws=draws,
        optimizer=fake_optimizer,
    )
    assert supported.validate_generation_result_v1(result) == result
    assert len(summaries) == supported.ATTEMPTS_PER_TASK == 2784
    assert [row[0] for row in summaries] == list(range(2784))
    assert result["cell_count"] == 12
    assert all(cell["attempted_optimizer_calls"] == 232 for cell in result["cells"])
    assert all(
        cell["occurrence_count"]
        == (0 if cell["arm_id"] == "supported232-all-boom-v1" else 1)
        for cell in result["cells"]
    )
    assert all(cell["role_game_dark_excluded"] for cell in result["cells"])

    for cell in result["cells"]:
        leverage = [row for row in cell["calls"] if row["family_id"] == "leverage"]
        if leverage:
            assert leverage[0]["banned_lineup_count"] == 0
            assert all(row["banned_lineup_count"] == 1 for row in leverage[1:])
            assert all(row["max_overlap"] == 7 for row in leverage)
        qbvar = [row for row in cell["calls"] if row["family_id"] == "qbvar"]
        assert qbvar
        assert all(len(row["locks"]) == 1 for row in qbvar)
        assert all(row["max_overlap"] == 6 for row in qbvar)
        assert all(row["banned_lineup_count"] == 0 for row in qbvar)

    mutated = copy.deepcopy(result)
    mutated["cells"][0]["calls"][0]["status"] = "error"
    with pytest.raises(
        supported.CorpusR6Supported232GenerationV1Error,
        match="self-hash differs",
    ):
        supported.validate_generation_result_v1(mutated)


def test_legacy_optimizer_callback_uses_profile_and_dynamic_family_constraints():
    rows = tuple(_players())
    objective = tuple(float(row["proj_tourney"]) for row in rows)
    spec = supported.OptimizerCallSpec(
        arm_id="supported232-baseline-v1",
        profile_id="F9-single-partner",
        origin_id="R0",
        global_call_ordinal=0,
        cell_call_ordinal=0,
        family_id="qbvar",
        family_slot=0,
        family_slot_count=32,
        objective_kind="point-in-time-proj-tourney-qb-lock",
        objective_values=objective,
        objective_source=(("kind", "base-objective-qb-lock"),),
        locks=("p00",),
        banned_lineups=(),
        max_overlap=6,
        players=rows,
    )
    outcome = supported.legacy_optimizer_callback_v1(spec)
    assert outcome.status == "optimal"
    assert outcome.roster is not None
    assert "p00" in outcome.roster


def test_request_rejects_any_attempt_to_claim_solver_or_production_authority(
    tmp_path,
):
    request, _bundle, _draws, _bundle_path, _draws_path = _local_request(tmp_path)
    for field, value in (
        ("solver_proof_authority_claimed", True),
        ("production_change_licensed", True),
        ("promotion_authority", True),
    ):
        mutated = copy.deepcopy(request)
        mutated[field] = value
        body = {key: row for key, row in mutated.items() if key != "request_sha256"}
        mutated["request_sha256"] = supported.canonical_sha256_v1(body)
        with pytest.raises(
            supported.CorpusR6Supported232GenerationV1Error,
            match="fixed policy differs",
        ):
            supported.validate_local_task_request_v1(mutated)
