from dataclasses import replace
from itertools import combinations

import numpy as np
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.lineup import Lineup
from nfl_dfs.research import boom_first_historical_paired_v1 as paired


def _identity(name: str) -> dict:
    return {
        "uri": f"gs://fixture/{name}.json",
        "generation": "1234",
        "sha256": "a" * 64,
        "bytes": 100,
    }


def _fixture_builder(*, worlds: int, mismatch: bool = False,
                     outcome_field: bool = False):
    calls: list[tuple] = []
    players = [
        {
            "id": f"p{index:02d}",
            "name": f"Player {index}",
            "pos": "WR",
            "team": f"T{index % 4}",
            "opp": f"T{(index + 1) % 4}",
            "game_id": f"g{index % 2}",
            "salary": 5_000,
            "proj": float(15 + index),
        }
        for index in range(14)
    ]
    roster_pool = list(combinations(range(len(players)), 9))

    def build(slate, arm, seed_label, projection_seed, role_seed, env):
        calls.append((
            slate.slate_id,
            arm,
            seed_label,
            projection_seed,
            role_seed,
            dict(env),
        ))
        seed_index = int(seed_label[1:])
        draws = np.asarray([
            [
                10.0 + player_index + seed_index * 0.1 + world_index * 0.01
                for world_index in range(worlds)
            ]
            for player_index in range(len(players))
        ], dtype=np.float32)
        if mismatch and arm == "treatment" and seed_label == "R2":
            draws = draws.copy()
            draws[0, 0] += 1.0
        rows = [dict(player) for player in players]
        if outcome_field:
            rows[0]["actual"] = 20.0
        count = 80 if arm == "control" else 82
        roster_offset = 0 if arm == "control" else 7
        rosters = roster_pool[roster_offset:roster_offset + count]
        lineups = tuple(Lineup(
            [rows[index] for index in roster],
            tag="lev" if arm == "control" else "boom",
        ) for roster in rosters)
        ordinal = {player["id"]: index for index, player in enumerate(rows)}
        totals = np.stack([
            draws[[ordinal[player["id"]] for player in lineup.players]].sum(axis=0)
            for lineup in lineups
        ]).astype(np.float32)
        leverage = int(env["N_LEV"])
        boom = int(env["N_BOOM"])
        return CandidateBatch(
            candidates=lineups,
            candidate_totals=totals,
            player_ids=tuple(player["id"] for player in rows),
            player_rows=tuple(rows),
            row_draws=draws,
            all_tags={lineup.ids: (lineup.tag,) for lineup in lineups},
            metadata={
                "role_player_world_receipt": paired.role_player_world_receipt(
                    tuple(player["id"] for player in rows),
                    draws,
                ),
                "generation_allocation": {
                    "leverage_requested": leverage,
                    "leverage_unique": leverage,
                    "leverage_solve_attempts": leverage,
                    "leverage_solver_errors": 0,
                    "leverage_infeasible": 0,
                    "leverage_successful": leverage,
                    "boom_requested": boom,
                    "boom_attempted": boom,
                    "boom_successful": boom,
                    "boom_solver_errors": 0,
                    "boom_infeasible": 0,
                    "boom_duplicates": 0,
                    "boom_failures": 0,
                    "boom_unique_added": boom,
                    "boom_unique_fill": False,
                    "ce_requested": 0,
                    "role_or_epistemic_requested": 12,
                    "gumbel_requested": 0,
                    "core_requested": leverage + boom,
                    "total_requested_with_replacement_families": (
                        leverage + boom + 12
                    ),
                    "unique_candidates_after_all_families": count,
                },
                "generation_timing_seconds": {
                    "leverage": 1.0 + seed_index,
                    "primary_boom": 2.0 + seed_index,
                    "all_generation_through_candidate_matrix": 3.0 + seed_index,
                },
            },
        )

    return build, calls, players


@pytest.fixture
def small_policy(monkeypatch):
    policy = replace(
        ADOPTED_CLASSIC_POLICY,
        multiseed_worlds_per_block=7,
    )
    monkeypatch.setattr(paired, "ADOPTED_CLASSIC_POLICY", policy)
    return policy


def _selection(small_policy):
    builder, calls, players = _fixture_builder(
        worlds=small_policy.multiseed_worlds_per_block
    )
    receipt = paired.build_score_blind_development_panel(
        [paired.DevelopmentSlate(2023, 1, "2023-w01", _identity("source"))],
        builder,
        panel_id="boom-first-dev-v1",
        code_sha="abcdef123456",
        image_digest="sha256:" + "b" * 64,
    )
    return receipt, calls, players


def test_builds_exact_five_seed_same_world_pair_and_freezes_exact80(small_policy):
    receipt, calls, _ = _selection(small_policy)

    assert receipt["schema_version"] == paired.SELECTION_SCHEMA
    assert receipt["uses_target_slate_outcomes"] is False
    assert receipt["selection_completed_before_target_slate_outcomes"] is True
    assert receipt[
        "prior_only_historical_labels_may_train_later_targets"
    ] is True
    assert receipt["sealed_2025_outcomes_read"] is False
    assert receipt["prefix_sizes"] == [20, 40, 80]
    assert receipt["entry_count"] == 80
    assert len(calls) == 10
    assert [(row[1], row[2]) for row in calls] == [
        (arm, f"R{seed}")
        for seed in range(5)
        for arm in ("control", "treatment")
    ]
    assert [(calls[index * 2][3], calls[index * 2][4])
            for index in range(5)] == list(small_policy.multiseed_seed_pairs)
    for row in calls:
        arm, env = row[1], row[5]
        assert env["MODEL_ENSEMBLE"] == "1"
        assert env["MULTISEED_PORTFOLIO"] == "CBWU"
        assert env["N_EPISTEMIC"] == "12"
        assert (env["N_LEV"], env["N_BOOM"]) == (
            ("160", "40") if arm == "control" else ("40", "160")
        )

    slate = receipt["slates"][0]
    assert slate["same_player_worlds"] is True
    assert slate["same_role_player_worlds"] is True
    assert receipt["development_seasons"] == [2023]
    assert receipt["panel_authority"]["supplied"] is False
    assert receipt["h1_readiness"][
        "score_blind_selection_ready_for_h1_grading"
    ] is False
    assert receipt["h1_readiness"]["h1_complete"] is False
    assert slate["arms"]["control"]["combined_candidate_count"] == 80
    assert slate["arms"]["treatment"]["combined_candidate_count"] == 82
    assert len(slate["arms"]["control"]["selected_rosters"]) == 80
    assert len(slate["arms"]["treatment"]["selected_rosters"]) == 80
    assert (
        slate["arms"]["control"]["combined_player_world_sha256"]
        == slate["arms"]["treatment"]["combined_player_world_sha256"]
    )
    assert receipt["requested_allocation"]["equal_core_requested"] is True
    assert receipt["requested_allocation"][
        "nominal_full_slate_requested_per_native_book"
    ] == 266
    assert receipt["requested_allocation"][
        "requested_family_slots_per_five_book_arm"
    ] == 1060
    assert receipt["requested_allocation"][
        "nominal_all_requested_per_five_book_arm"
    ] == 1330
    assert paired.validate_score_blind_selection_receipt(receipt) == receipt


def test_panel_authority_is_exact_and_h1_remains_nonpromotable(small_policy):
    builder, _, _ = _fixture_builder(
        worlds=small_policy.multiseed_worlds_per_block
    )
    slates = [
        paired.DevelopmentSlate(
            2023, 1, "2023-w01", _identity("source-2023")
        ),
        paired.DevelopmentSlate(
            2024, 2, "2024-w02", _identity("source-2024")
        ),
    ]
    authority = paired.DevelopmentPanelAuthority(
        panel_id="boom-first-authoritative-dev-v1",
        expected_slate_ids=("2023-w01", "2024-w02"),
        identity=_identity("panel-index"),
    )
    receipt = paired.build_score_blind_development_panel(
        slates,
        builder,
        panel_id="boom-first-authoritative-dev-v1",
        code_sha="abcdef123456",
        image_digest="sha256:" + "b" * 64,
        panel_authority=authority,
    )

    assert receipt["development_seasons"] == [2023, 2024]
    assert receipt["panel_authority"]["membership_matches"] is True
    assert receipt["h1_readiness"][
        "score_blind_selection_ready_for_h1_grading"
    ] is True
    assert receipt["h1_readiness"]["statistical_diagnostics_implemented"] is False
    assert receipt["h1_readiness"]["h1_complete"] is False
    assert receipt["h1_readiness"]["promotion_eligible"] is False

    mismatched = replace(
        authority,
        expected_slate_ids=("2023-w01",),
    )
    with pytest.raises(
        paired.BoomFirstHistoricalPairedError,
        match="membership differs from immutable authority",
    ):
        paired.build_score_blind_development_panel(
            slates,
            builder,
            panel_id="boom-first-authoritative-dev-v1",
            code_sha="abcdef123456",
            image_digest="sha256:" + "b" * 64,
            panel_authority=mismatched,
        )


def test_rejects_native_solver_shortfall(small_policy):
    slate = paired.DevelopmentSlate(2023, 1, "2023-w01", _identity("source"))
    builder, _, _ = _fixture_builder(
        worlds=small_policy.multiseed_worlds_per_block
    )

    def shortfall(*args, **kwargs):
        batch = builder(*args, **kwargs)
        metadata = dict(batch.metadata)
        allocation = dict(metadata["generation_allocation"])
        allocation["leverage_successful"] -= 1
        metadata["generation_allocation"] = allocation
        return replace(batch, metadata=metadata)

    with pytest.raises(
        paired.BoomFirstHistoricalPairedError, match="requested-solve receipt"
    ):
        paired.build_score_blind_development_panel(
            [slate], shortfall, panel_id="solver-shortfall",
            code_sha="abcdef1", image_digest="sha256:" + "c" * 64,
        )


def test_rejects_world_drift_and_any_outcome_field(small_policy):
    slate = paired.DevelopmentSlate(2024, 2, "2024-w02", _identity("source"))
    builder, _, _ = _fixture_builder(worlds=7, mismatch=True)
    with pytest.raises(
        paired.BoomFirstHistoricalPairedError, match="player worlds differ"
    ):
        paired.build_score_blind_development_panel(
            [slate], builder, panel_id="world-drift", code_sha="abcdef1",
            image_digest="sha256:" + "c" * 64,
        )

    builder, _, _ = _fixture_builder(worlds=7, outcome_field=True)
    with pytest.raises(
        paired.BoomFirstHistoricalPairedError, match="outcome fields"
    ):
        paired.build_score_blind_development_panel(
            [slate], builder, panel_id="outcome-drift", code_sha="abcdef1",
            image_digest="sha256:" + "c" * 64,
        )


def test_rejects_role_world_drift_across_arms(small_policy):
    slate = paired.DevelopmentSlate(
        2023, 1, "2023-w01", _identity("source")
    )
    builder, _, _ = _fixture_builder(
        worlds=small_policy.multiseed_worlds_per_block
    )

    def role_drift(*args, **kwargs):
        batch = builder(*args, **kwargs)
        if args[1] != "treatment" or args[2] != "R2":
            return batch
        metadata = dict(batch.metadata)
        role_receipt = dict(metadata["role_player_world_receipt"])
        role_receipt["player_world_sha256"] = "d" * 64
        metadata["role_player_world_receipt"] = role_receipt
        return replace(batch, metadata=metadata)

    with pytest.raises(
        paired.BoomFirstHistoricalPairedError,
        match="role player worlds differ across arms",
    ):
        paired.build_score_blind_development_panel(
            [slate],
            role_drift,
            panel_id="role-world-drift",
            code_sha="abcdef1",
            image_digest="sha256:" + "c" * 64,
        )


def test_grades_only_after_frozen_selection_and_reports_paired_prefixes(
    small_policy,
):
    receipt, _, players = _selection(small_policy)
    actuals = {
        player["id"]: 5.0 + index * 0.25
        for index, player in enumerate(players)
    }
    report = paired.grade_development_panel(
        receipt,
        grade_id="boom-first-dev-grade-v1",
        actual_points_by_slate={"2023-w01": actuals},
        outcome_identities={"2023-w01": _identity("outcomes")},
    )

    assert report["schema_version"] == paired.GRADE_SCHEMA
    assert report["selection_receipt_sha256"] == receipt["receipt_sha256"]
    assert report["selection_completed_before_target_slate_outcomes"] is True
    assert report["target_slate_outcomes_read_for_grading"] is True
    assert report["target_slate_outcomes_absent_during_selection"] is True
    assert report["development_target_outcomes_only"] is True
    assert report["h1_readiness"]["h1_complete"] is False
    assert report["sealed_2025_outcomes_read"] is False
    assert [row["prefix"] for row in report["aggregate_results"]] == [20, 40, 80]
    for weekly in report["weekly_results"][0]["prefixes"]:
        assert weekly["paired_delta_micro"] == (
            weekly["treatment_weekly_max_micro"]
            - weekly["control_weekly_max_micro"]
        )
    for aggregate in report["aggregate_results"]:
        assert [row["threshold"] for row in aggregate["thresholds"]] == [
            194, 200, 210, 220, 230,
        ]
        assert aggregate["slate_count"] == 1
        assert aggregate["control_mean_selector_regret_points"] >= 0
        assert aggregate["treatment_mean_selector_regret_points"] >= 0
    assert len(report["report_sha256"]) == 64


def test_sealed_2025_and_incomplete_or_tampered_outcomes_fail_closed(
    small_policy,
):
    with pytest.raises(
        paired.BoomFirstHistoricalPairedError, match="sealed 2025"
    ):
        paired.DevelopmentSlate(2025, 1, "2025-w01", _identity("sealed"))

    receipt, _, players = _selection(small_policy)
    tampered = dict(receipt)
    tampered["tail_line"] = 200.0
    with pytest.raises(
        paired.BoomFirstHistoricalPairedError, match="self-hash"
    ):
        paired.grade_development_panel(
            tampered,
            grade_id="tampered",
            actual_points_by_slate={
                "2023-w01": {player["id"]: 1.0 for player in players}
            },
            outcome_identities={"2023-w01": _identity("outcomes")},
        )

    incomplete = {player["id"]: 1.0 for player in players[:-1]}
    with pytest.raises(
        paired.BoomFirstHistoricalPairedError, match="lacks realized players"
    ):
        paired.grade_development_panel(
            receipt,
            grade_id="incomplete",
            actual_points_by_slate={"2023-w01": incomplete},
            outcome_identities={"2023-w01": _identity("outcomes")},
        )
