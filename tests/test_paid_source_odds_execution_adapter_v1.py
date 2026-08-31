from __future__ import annotations

from hashlib import sha256
import json

import numpy as np
import pytest

from nfl_dfs.optimizer.construction_presets import LEGALITY_ONLY_PRESET_ID
from nfl_dfs.research import odds_prop_override_ablation_v1 as odds
from nfl_dfs.research import paid_source_ablation_registry_v1 as registry
from nfl_dfs.research import paid_source_odds_execution_adapter_v1 as execution


def _identity_for_raw(raw: bytes, label: str, generation: int = 1) -> dict[str, object]:
    return {
        "uri": f"gs://fixture-bucket/odds-execution/{label}",
        "generation": str(generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }


def _identity_for_body(body: object, label: str) -> dict[str, object]:
    return _identity_for_raw(registry.canonical_json_bytes(body), label)


def _opaque_identity(label: str) -> dict[str, object]:
    return _identity_for_body({"fixture": label}, f"{label}.json")


def _player_metadata() -> list[dict[str, object]]:
    specifications = (
        [(f"qb{index}", "QB") for index in range(3)]
        + [(f"rb{index}", "RB") for index in range(6)]
        + [(f"wr{index}", "WR") for index in range(10)]
        + [(f"te{index}", "TE") for index in range(4)]
        + [(f"dst{index}", "DST") for index in range(3)]
    )
    teams = ("A", "B", "C", "D", "E", "F")
    result: list[dict[str, object]] = []
    for ordinal, (player_id, position) in enumerate(specifications):
        team_index = ordinal % len(teams)
        opponent_index = team_index + 1 if team_index % 2 == 0 else team_index - 1
        result.append({
            "gsis_id": player_id,
            "position": position,
            "team": teams[team_index],
            "opponent": teams[opponent_index],
            "game_id": f"game-{team_index // 2}",
            "salary": 5_000,
            # This represents every non-market term in the incumbent leverage
            # objective. It is common across source states by construction.
            "leverage_objective_offset": ((ordinal % 5) - 2) * 0.07,
        })
    return result


def _support_and_inputs(
    *, leverage_solve_count: int = 82, boom_solve_count: int = 10,
) -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    bytes,
    dict[str, object],
]:
    slate = {"slate_id": "2024-w08", "season": 2024, "week": 8}
    common_lock = _opaque_identity("common-lock")
    metadata = _player_metadata()
    ordered_ids = sorted(str(row["gsis_id"]) for row in metadata)
    fallback = odds.build_dk_ppg_fallback_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=common_lock,
        source_snapshot_time_utc="2024-10-27T15:00:00Z",
        source_snapshot_identity=_opaque_identity("dk-player-snapshot"),
        rows=[
            {"gsis_id": player_id, "dk_ppg": 20.0 + ordinal * 0.11}
            for ordinal, player_id in enumerate(ordered_ids)
        ],
    )
    boosted_ids = {"qb2", "rb5", "wr9", "te3", "dst2"}
    props = odds.build_prop_snapshot_authority_v1(
        slate=slate,
        common_lock_time_utc="2024-10-27T17:00:00Z",
        common_lock_identity=common_lock,
        source_snapshot_identity=_opaque_identity("odds-prop-snapshot"),
        rows=[
            {
                "gsis_id": player_id,
                "prop_market_points": (
                    42.0 if player_id in boosted_ids else 8.0
                ),
                "latest_snapshot_time_utc": "2024-10-27T16:30:00Z",
            }
            for player_id in ordered_ids
            if player_id in boosted_ids
        ],
    )
    census = odds.build_odds_prop_override_support_census_v1(
        slate=slate,
        model_rows=[
            {"gsis_id": player_id, "model_mean": 21.0 + ordinal * 0.09}
            for ordinal, player_id in enumerate(ordered_ids)
        ],
        fallback_authority=fallback,
        fallback_authority_identity=_identity_for_body(
            fallback, "dk-fallback-authority.json"
        ),
        prop_authority=props,
        prop_authority_identity=_identity_for_body(
            props, "prop-authority.json"
        ),
    )

    metadata_by_id = {str(row["gsis_id"]): row for row in metadata}
    player_input = execution.build_odds_execution_player_input_v1(
        support_census=census,
        player_snapshot_time_utc="2024-10-27T16:00:00Z",
        source_player_snapshot_identity=_opaque_identity("optimizer-player-source"),
        player_rows=[metadata_by_id[player_id] for player_id in ordered_ids],
    )
    candidate_input = execution.build_odds_execution_candidate_input_v1(
        support_census=census,
        construction_preset_id=LEGALITY_ONLY_PRESET_ID,
        leverage_solve_count=leverage_solve_count,
        boom_solve_count=boom_solve_count,
    )
    rng = np.random.default_rng(20260830)
    raw_worlds = rng.normal(0.0, 9.0, size=(len(ordered_ids), 16))
    centered = raw_worlds - raw_worlds.mean(axis=1, keepdims=True)
    centered_bytes = execution.canonical_centered_world_bytes_v1(
        support_census=census,
        player_ids=ordered_ids,
        centered_worlds=centered,
    )
    return (
        census,
        player_input,
        _identity_for_body(player_input, "player-input.json"),
        candidate_input,
        _identity_for_body(candidate_input, "candidate-input.json"),
        centered_bytes,
        _identity_for_raw(centered_bytes, "centered-worlds.bin"),
    )


class _Binder:
    def __init__(self) -> None:
        self.raw_by_name: dict[str, bytes] = {}

    def __call__(self, name: str, raw: bytes) -> dict[str, object]:
        assert name not in self.raw_by_name
        self.raw_by_name[name] = raw
        return _identity_for_raw(raw, name, generation=len(self.raw_by_name))


def _runtime() -> dict[str, object]:
    return {
        "schema_version": execution.RUNTIME_ATTESTATION_SCHEMA,
        "execution_id": "fixture-odds-execution-1",
        "task_index": 0,
        "attempt": 1,
        "source_commit_sha": "a" * 40,
        "image_digest": "sha256:" + "b" * 64,
        "worker_started_at_utc": "2026-08-30T12:00:00Z",
    }


def test_execution_applies_on_off_before_generation_and_crossed_k80() -> None:
    (
        census,
        player_input,
        player_identity,
        candidate_input,
        candidate_identity,
        centered_bytes,
        centered_identity,
    ) = _support_and_inputs()
    binder = _Binder()
    result = execution.execute_odds_prop_override_cross_v1(
        support_census=census,
        player_input=player_input,
        player_input_identity=player_identity,
        candidate_input=candidate_input,
        candidate_input_identity=candidate_identity,
        centered_world_bytes=centered_bytes,
        centered_world_identity=centered_identity,
        runtime_attestation=_runtime(),
        bind_output=binder,
    )

    trace = result["influence_trace"]
    assert odds.validate_odds_prop_override_influence_trace_v1(trace) == trace
    assert [
        (row["population_cell_id"], row["selection_world_cell_id"])
        for row in trace["cell_outputs"]
    ] == list(registry.ODDS_CROSS_ORDER)
    assert all(
        len(row["selected_lineup_ids"]) == registry.ENTRY_BUDGET
        for row in trace["cell_outputs"]
    )

    # The source state reaches both upstream mechanisms: it changes the
    # generated population and produces two distinct shifted world matrices.
    assert trace["candidate_population_turnover"]["exact_membership_equal"] is False
    assert trace["candidate_population_turnover"]["membership_turnover_count"] > 0
    generation = result["execution_receipt"]["generation_receipts"]
    assert [row["cell_id"] for row in generation] == list(registry.ODDS_CELL_ORDER)
    assert all(row["unique_candidate_count"] >= 80 for row in generation)
    matrix_identities = result["execution_receipt"]["source_state_application"][
        "selection_world_matrix_identities"
    ]
    assert matrix_identities[0]["sha256"] != matrix_identities[1]["sha256"]

    # The crossed selector runs from each immutable population against each
    # immutable source-conditioned selection world, rather than reusing a
    # caller-built selected book.
    outputs = trace["cell_outputs"]
    assert outputs[0]["candidate_ids"] == outputs[1]["candidate_ids"]
    assert outputs[2]["candidate_ids"] == outputs[3]["candidate_ids"]
    assert outputs[0]["selection_world_identity"] == outputs[2][
        "selection_world_identity"
    ]
    assert outputs[1]["selection_world_identity"] == outputs[3][
        "selection_world_identity"
    ]
    assert outputs[0]["selected_lineup_ids"] != outputs[1]["selected_lineup_ids"]
    assert outputs[2]["selected_lineup_ids"] != outputs[3]["selected_lineup_ids"]

    receipt = result["execution_receipt"]
    retained_hash = receipt["execution_receipt_sha256"]
    assert retained_hash == registry.canonical_sha256({
        key: value for key, value in receipt.items()
        if key != "execution_receipt_sha256"
    })
    assert receipt["exact_k80_all_crossing_cells"] is True
    assert receipt["source_value_established"] is False
    assert receipt["outcome_columns_read"] == []
    assert all(
        set(row["families"][0])
        >= {
            "requested",
            "attempts",
            "retries",
            "solver_errors",
            "infeasible",
            "duplicates",
            "unique_candidates",
            "runtime_ms",
        }
        for row in generation
    )
    assert len(result["world_matrix_bytes_by_sha256"]) == 2

    # Inspect the exact output bytes: their row means are the support-census
    # 45/55 means, proving the adapter applied the source state before use.
    for cell_id, matrix_identity in zip(
        registry.ODDS_CELL_ORDER, matrix_identities, strict=True
    ):
        raw = result["world_matrix_bytes_by_sha256"][matrix_identity["sha256"]]
        header_raw, matrix_raw = raw.split(b"\n", 1)
        header = json.loads(header_raw)
        matrix = np.frombuffer(matrix_raw, dtype=header["dtype"]).reshape(
            header["shape"]
        )
        cell = next(
            value for value in census["cells"]
            if value["cell"]["cell_id"] == cell_id
        )
        np.testing.assert_allclose(
            matrix.mean(axis=1),
            [row["blended_mean"] for row in cell["rows"]],
            rtol=0.0,
            atol=1e-10,
        )


def test_execution_fails_closed_before_solver_when_plan_cannot_reach_k80() -> None:
    (
        census,
        player_input,
        player_identity,
        candidate_input,
        candidate_identity,
        centered_bytes,
        centered_identity,
    ) = _support_and_inputs(leverage_solve_count=10, boom_solve_count=5)
    with pytest.raises(
        execution.OddsExecutionContractMissingV1Error,
        match="candidate-generation-input.at-least-80-requested-solves",
    ) as raised:
        execution.execute_odds_prop_override_cross_v1(
            support_census=census,
            player_input=player_input,
            player_input_identity=player_identity,
            candidate_input=candidate_input,
            candidate_input_identity=candidate_identity,
            centered_world_bytes=centered_bytes,
            centered_world_identity=centered_identity,
            runtime_attestation=_runtime(),
            bind_output=_Binder(),
        )
    assert raised.value.missing_requirements == (
        "candidate-generation-input.at-least-80-requested-solves",
    )


def test_execution_rejects_post_lock_players_and_inexact_world_identity() -> None:
    (
        census,
        player_input,
        player_identity,
        candidate_input,
        candidate_identity,
        centered_bytes,
        centered_identity,
    ) = _support_and_inputs()
    with pytest.raises(
        execution.PaidSourceOddsExecutionAdapterV1Error,
        match="not strictly before common lock",
    ):
        execution.build_odds_execution_player_input_v1(
            support_census=census,
            player_snapshot_time_utc="2024-10-27T17:00:00Z",
            source_player_snapshot_identity=_opaque_identity("post-lock-player-source"),
            player_rows=player_input["player_rows"],
        )

    poisoned_identity = dict(centered_identity)
    poisoned_identity["sha256"] = "0" * 64
    with pytest.raises(
        execution.PaidSourceOddsExecutionAdapterV1Error,
        match="differs from exact bytes",
    ):
        execution.execute_odds_prop_override_cross_v1(
            support_census=census,
            player_input=player_input,
            player_input_identity=player_identity,
            candidate_input=candidate_input,
            candidate_input_identity=candidate_identity,
            centered_world_bytes=centered_bytes,
            centered_world_identity=poisoned_identity,
            runtime_attestation=_runtime(),
            bind_output=_Binder(),
        )
