from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from functools import lru_cache
from itertools import combinations, count
from pathlib import Path

import numpy as np
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference import prospective_cross_law_discovery as cross_law
from nfl_dfs.optimizer.construction_presets import (
    INCUMBENT_GPP_PRESET_ID,
    resolve_construction_preset,
)
from nfl_dfs.optimizer.lineup import Lineup


SEASON = 2026
WEEK = 1
LABEL = "R0"


def _players() -> list[dict[str, object]]:
    positions = (
        ["DST", "DST"]
        + ["QB"] * 4
        + ["RB"] * 8
        + ["WR"] * 12
        + ["TE"] * 6
    )
    rows: list[dict[str, object]] = []
    for index, position in enumerate(positions):
        team_number = index % 8
        game_number = team_number // 2
        rows.append({
            "id": f"p{index:02d}",
            "name": f"Player {index}",
            "pos": position,
            "team": f"T{team_number}",
            "opp": f"T{team_number ^ 1}",
            "game_id": f"G{game_number}",
            "salary": 5_500,
            "proj": 10.0 + index / 10.0,
            "actual": None,
        })
    return rows


def _lineup(players: list[dict[str, object]], indices: tuple[int, ...], tag: str) -> Lineup:
    return Lineup(players=[dict(players[index]) for index in indices], tag=tag)


def _candidate_totals(
    lineups: tuple[Lineup, ...],
    players: list[dict[str, object]],
    draws: np.ndarray,
) -> np.ndarray:
    by_id = {player["id"]: index for index, player in enumerate(players)}
    return np.stack([
        draws[[by_id[player["id"]] for player in lineup.players]].sum(axis=0)
        for lineup in lineups
    ])


def _allocation() -> dict[str, object]:
    return {
        "leverage_requested": 40,
        "leverage_unique": 40,
        "leverage_solve_attempts": 40,
        "leverage_solver_errors": 0,
        "leverage_infeasible": 0,
        "leverage_successful": 40,
        "boom_requested": 100,
        "boom_attempted": 100,
        "boom_successful": 100,
        "boom_solver_errors": 0,
        "boom_infeasible": 0,
        "boom_duplicates": 0,
        "boom_failures": 0,
        "boom_unique_added": 100,
        "boom_unique_fill": False,
        "ce_requested": 0,
        "role_or_epistemic_requested": 12,
        "gumbel_requested": 0,
        "core_requested": 140,
        "total_requested_with_replacement_families": 152,
        "unique_candidates_after_all_families": 152,
    }


def _base_batch(*, perturb: float = 0.0) -> tuple[CandidateBatch, object, dict[str, str]]:
    players = _players()
    rng = np.random.default_rng(141)
    draws = rng.normal(
        loc=np.arange(len(players), dtype=np.float32)[:, None] / 10.0,
        scale=8.0,
        size=(len(players), cross_law.BASE_WORLD_COUNT),
    ).astype(np.float32)
    if perturb:
        draws[2, 5] = np.float32(draws[2, 5] + perturb)
    base_lineups = (
        _lineup(players, (0, 2, 6, 7, 14, 15, 18, 19, 26), "lev"),
        _lineup(players, (1, 3, 10, 12, 18, 19, 20, 21, 27), "boom"),
    )
    preset = resolve_construction_preset(INCUMBENT_GPP_PRESET_ID)
    environment = preset.optimizer_environment()
    batch = CandidateBatch(
        candidates=base_lineups,
        candidate_totals=_candidate_totals(base_lineups, players, draws),
        player_ids=tuple(player["id"] for player in players),
        player_rows=tuple(deepcopy(players)),
        row_draws=draws,
        all_tags={
            base_lineups[0].ids: ("lev",),
            base_lineups[1].ids: ("boom",),
        },
        metadata={
            "season": SEASON,
            "week": WEEK,
            "generation_allocation": _allocation(),
            "construction_preset_receipt": preset.receipt(),
            "uses_realized_outcomes": False,
        },
    )
    return batch, preset, environment


@lru_cache(maxsize=1)
def _roster_indices() -> list[tuple[int, ...]]:
    """Deterministic fixture rosters that obey the incumbent construction."""

    players = _players()
    excluded = {
        frozenset((0, 2, 6, 7, 14, 15, 18, 19, 26)),
        frozenset((1, 3, 10, 12, 18, 19, 20, 21, 27)),
        frozenset((0, 2, 6, 7, 14, 18, 19, 22, 26)),
    }
    retained: list[tuple[int, ...]] = []
    for dst in range(0, 2):
        for qb in range(2, 6):
            for rbs in combinations(range(6, 14), 2):
                for wrs in combinations(range(14, 26), 4):
                    for te in range(26, 32):
                        chosen = (dst, qb, *rbs, *wrs, te)
                        chosen_set = frozenset(chosen)
                        if chosen_set in excluded:
                            continue
                        rows = [players[index] for index in chosen]
                        qb_row = players[qb]
                        same_team_catchers = sum(
                            row["team"] == qb_row["team"]
                            and row["pos"] in {"WR", "TE"}
                            for row in rows
                        )
                        bring_backs = sum(
                            row["team"] == qb_row["opp"]
                            and row["pos"] in {"RB", "WR", "TE"}
                            for row in rows
                        )
                        dst_row = players[dst]
                        rb_rows = [players[index] for index in rbs]
                        if (
                            same_team_catchers < 2
                            or bring_backs < 1
                            or any(
                                row["team"] == dst_row["opp"]
                                for row in rb_rows
                            )
                            or len({row["team"] for row in rb_rows}) != 2
                            or len({row["game_id"] for row in rows}) < 2
                        ):
                            continue
                        retained.append(chosen)
                        if len(retained) == 80:
                            return retained
    raise AssertionError("fixture could not build 80 construction-valid rosters")


def _install_solver(
    monkeypatch: pytest.MonkeyPatch,
    *,
    duplicate_first: bool = False,
    near_duplicate_first: bool = False,
    failure_at: int | None = None,
    infeasible_at: int | None = None,
) -> list[dict[str, object]]:
    indices = _roster_indices()
    calls: list[dict[str, object]] = []
    ticks = count()
    monkeypatch.setattr(
        cross_law.time,
        "perf_counter",
        lambda: next(ticks) * 0.125,
    )

    def solve(players, **kwargs):
        ordinal = len(calls)
        calls.append({"players": players, **kwargs})
        if ordinal == failure_at:
            raise RuntimeError("fixture solver error")
        if ordinal == infeasible_at:
            return None
        if duplicate_first and ordinal == 0:
            chosen = (0, 2, 6, 7, 14, 15, 18, 19, 26)
        elif near_duplicate_first and ordinal == 0:
            chosen = (0, 2, 6, 7, 14, 18, 19, 22, 26)
        else:
            chosen = indices[ordinal]
        return Lineup(players=[players[index] for index in chosen], tag="fixture")

    monkeypatch.setattr(cross_law, "optimize", solve)
    return calls


def _build(
    monkeypatch: pytest.MonkeyPatch,
    *,
    base: CandidateBatch | None = None,
    duplicate_first: bool = False,
    near_duplicate_first: bool = False,
) -> tuple[CandidateBatch, CandidateBatch, object, dict[str, str], list[dict[str, object]]]:
    if base is None:
        base, preset, environment = _base_batch()
    else:
        preset = resolve_construction_preset(INCUMBENT_GPP_PRESET_ID)
        environment = preset.optimizer_environment()
    calls = _install_solver(
        monkeypatch,
        duplicate_first=duplicate_first,
        near_duplicate_first=near_duplicate_first,
    )
    transformed = cross_law.build_cross_law_discovery_batch(
        base,
        season=SEASON,
        week=WEEK,
        cbwu_seed_label=LABEL,
        stack=preset.stack,
        policy_env=environment,
    )
    return base, transformed, preset, environment, calls


def test_exact_overlay_preserves_every_marginal_and_dst_bitwise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, transformed, _, _, calls = _build(monkeypatch)
    receipt = transformed.metadata["cross_law_discovery"]

    assert len(calls) == cross_law.DISCOVERY_ATTEMPTS == 60
    assert len(receipt["exposure_ledger"]["rows"]) == 60
    assert receipt["attempt_count"] == receipt["milp_attempt_count"] == 60
    assert receipt["all_player_marginals_bitwise_identical"] is True
    assert receipt["dst_rows_bitwise_untouched"] is True
    assert receipt["dst_row_indices"] == [0, 1]
    assert receipt["law"] == {
        "law": "symmetric-widened-game-coupling-rank-transport",
        "lam_lo": 0.0,
        "lam_hi": 1.0,
        "base": 0.5,
        "slope": 0.0,
        "lam_team": 0.7,
        "dst_untouched": True,
        "marginal_restoration": "exact-bitwise-rank-transport",
        "selection_bank": "untouched-base-row-draws",
    }
    trace = receipt["same_team_co_boom_trace"]
    assert trace["uses_realized_outcomes"] is False
    assert trace["eligible_team_count"] >= 1
    assert 0.0 <= trace["base_rate"] <= 1.0
    assert 0.0 <= trace["discovery_rate"] <= 1.0
    assert trace["discovery_minus_base"] == pytest.approx(
        trace["discovery_rate"] - trace["base_rate"]
    )
    influence = receipt["production_influence_trace"]
    assert influence["schema_version"] == cross_law.INFLUENCE_TRACE_SCHEMA
    assert influence["uses_realized_outcomes"] is False
    marginal = influence["per_player_marginal_proof"]
    assert marginal["player_count"] == len(base.player_ids)
    assert marginal["identical_player_count"] == len(base.player_ids)
    assert marginal["all_bitwise_multisets_identical"] is True
    joint = influence["joint_dependence"]
    assert joint["uses_realized_outcomes"] is False
    assert joint["team_co_boom"]["eligible_team_count"] == 8
    assert joint["game_co_boom"]["eligible_game_count"] == 4
    assert joint["cross_team_dependence"]["same_game_cross_team"][
        "pair_count"
    ] == 4
    assert joint["cross_team_dependence"]["different_game_cross_team"][
        "pair_count"
    ] == 24
    world_rank = influence["world_rank_correlation"]
    assert -1.0 <= world_rank["spearman_rho"] <= 1.0
    assert world_rank["top_world_count"] == cross_law.DISCOVERY_ATTEMPTS
    assert 0 <= world_rank["top_world_overlap_count"] <= 60
    construction = influence["construction_integrity"]
    assert construction["base_candidate_count"] == len(base.candidates)
    assert construction["discovery_candidate_count"] == receipt[
        "new_candidate_count"
    ]
    assert construction["all_candidates_pass"] is True
    assert construction["same_stack_rules_for_base_and_discovery"] is True
    binding = influence["world_content_binding"]
    assert binding["base_world_bank_receipt"] == receipt[
        "base_world_bank_receipt"
    ]
    assert binding["discovery_world_bank_receipt"] == receipt[
        "discovery_world_bank_receipt"
    ]
    assert binding["suite_must_persist_base_and_discovery_create_only"] is True
    assert binding["suite_must_bind_independent_audit_bank_identity"] is True
    assert cross_law._array_receipt(transformed.row_draws) == (
        cross_law._array_receipt(base.row_draws)
    )

    games, teams, positions, _ = cross_law._validate_player_rows(base)
    seed = receipt["seed_receipt"]["numpy_seed_uint64"]
    discovery = cross_law._apply_discovery_overlay(
        base.row_draws,
        games=games,
        teams=teams,
        positions=positions,
        seed=seed,
    )
    for index in range(len(base.player_ids)):
        assert cross_law._bitwise_multiset_sha256(base.row_draws[index]) == (
            cross_law._bitwise_multiset_sha256(discovery[index])
        )
    assert np.array_equal(discovery[:2], base.row_draws[:2])


def test_seed_and_overlay_are_deterministic_and_bound_to_all_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, transformed_a, preset, environment, _ = _build(monkeypatch)
    receipt_a = transformed_a.metadata["cross_law_discovery"]
    _install_solver(monkeypatch)
    transformed_b = cross_law.build_cross_law_discovery_batch(
        base,
        season=SEASON,
        week=WEEK,
        cbwu_seed_label=LABEL,
        stack=preset.stack,
        policy_env=environment,
    )
    receipt_b = transformed_b.metadata["cross_law_discovery"]
    assert receipt_a == receipt_b
    assert [lineup.ids for lineup in transformed_a.candidates] == [
        lineup.ids for lineup in transformed_b.candidates
    ]

    base_changed, _, _ = _base_batch(perturb=0.125)
    original_receipt = cross_law._array_receipt(base.row_draws)
    changed_receipt = cross_law._array_receipt(base_changed.row_draws)
    seed_a, _ = cross_law._discovery_seed(
        season=SEASON,
        week=WEEK,
        cbwu_seed_label=LABEL,
        base_world_receipt=original_receipt,
    )
    seed_b, _ = cross_law._discovery_seed(
        season=SEASON,
        week=WEEK,
        cbwu_seed_label="R1",
        base_world_receipt=original_receipt,
    )
    seed_c, _ = cross_law._discovery_seed(
        season=SEASON,
        week=WEEK,
        cbwu_seed_label=LABEL,
        base_world_receipt=changed_receipt,
    )
    assert len({seed_a, seed_b, seed_c}) == 3
    seed_receipt = receipt_a["seed_receipt"]
    assert seed_receipt["derivation"] == (
        "SHA256(canonical-seed-material);first-8-digest-bytes;"
        "unsigned-big-endian-uint64"
    )
    assert seed_receipt["seed_digest_first_8_bytes_hex"] == (
        seed_receipt["seed_material_sha256"][:16]
    )
    assert int(seed_receipt["seed_digest_first_8_bytes_hex"], 16) == (
        seed_receipt["numpy_seed_uint64"]
    )
    assert seed_receipt["numpy_generator"] == "numpy.random.default_rng-PCG64"


def test_all_candidate_selection_scores_use_only_untouched_base_law(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, transformed, _, _, _ = _build(monkeypatch)
    expected = cross_law._candidate_totals(
        transformed.candidates,
        player_ids=base.player_ids,
        base_draws=base.row_draws,
    )
    assert cross_law._array_receipt(expected) == cross_law._array_receipt(
        transformed.candidate_totals
    )
    receipt = transformed.metadata["cross_law_discovery"]
    assert receipt[
        "all_candidate_selection_scores_from_untouched_base_row_draws"
    ] is True
    assert receipt["discovery_worlds_used_for_selection_scoring"] is False

    games, teams, positions, _ = cross_law._validate_player_rows(base)
    discovery = cross_law._apply_discovery_overlay(
        base.row_draws,
        games=games,
        teams=teams,
        positions=positions,
        seed=receipt["seed_receipt"]["numpy_seed_uint64"],
    )
    discovery_scores = cross_law._candidate_totals(
        transformed.candidates,
        player_ids=base.player_ids,
        base_draws=discovery,
    )
    assert not np.array_equal(discovery_scores, transformed.candidate_totals)


def test_dedupes_against_existing_pool_and_ledgers_every_attempt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, transformed, _, _, calls = _build(
        monkeypatch, duplicate_first=True
    )
    receipt = transformed.metadata["cross_law_discovery"]
    ledger = receipt["exposure_ledger"]
    rows = ledger["rows"]
    assert len(calls) == len(rows) == 60
    assert rows[0]["status"] == "dup"
    assert rows[0]["duplicate_origin"] == "preexisting"
    assert receipt["duplicate_candidate_count"] == 1
    assert receipt["new_candidate_count"] == 59
    assert len(transformed.candidates) == len(base.candidates) + 59
    assert len({lineup.ids for lineup in transformed.candidates}) == len(
        transformed.candidates
    )
    assert all(row["world_id"] is not None for row in rows)
    assert all(row["family"] == cross_law.FAMILY for row in rows)
    assert all(row["duration_seconds"] == 0.125 for row in rows)
    novelty = receipt["production_influence_trace"][
        "candidate_novelty_and_yield"
    ]
    assert novelty["attempt_count"] == 60
    assert novelty["solve_failure_count"] == 0
    assert novelty["exact_duplicate_count"] == 1
    assert novelty["exact_duplicate_rate"] == pytest.approx(1 / 60)
    assert novelty["unique_family_yield_count"] == 59
    assert novelty["unique_family_yield_rate"] == pytest.approx(59 / 60)
    assert novelty["solve_runtime_seconds"] == {
        "total": 7.5,
        "mean_per_attempt": 0.125,
        "minimum_attempt": 0.125,
        "maximum_attempt": 0.125,
        "ledger_duration_seconds_by_family": {cross_law.FAMILY: 7.5},
        "ledger_duration_seconds_by_status": {
            "dup": 0.125,
            "error": 0.0,
            "exhausted": 0.0,
            "infeasible": 0.0,
            "new": 7.375,
        },
    }


def test_near_duplicate_trace_is_distinct_from_exact_duplicate_rate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, transformed, _, _, _ = _build(
        monkeypatch, near_duplicate_first=True
    )
    novelty = transformed.metadata["cross_law_discovery"][
        "production_influence_trace"
    ]["candidate_novelty_and_yield"]
    assert novelty["exact_duplicate_count"] == 0
    assert novelty["near_duplicate_of_base_count"] >= 1
    assert novelty["near_duplicate_of_base_rate"] >= 1 / 60
    assert novelty["definition"]["near_duplicate"] == (
        "non-exact-roster-sharing-exactly-eight-of-nine-player-IDs"
    )


@pytest.mark.parametrize(("failure_at", "infeasible_at", "message"), [
    (7, None, "attempt\\[7\\] failed"),
    (None, 11, "attempt\\[11\\] was infeasible"),
])
def test_solver_error_or_short_attempt_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    failure_at: int | None,
    infeasible_at: int | None,
    message: str,
) -> None:
    base, preset, environment = _base_batch()
    calls = _install_solver(
        monkeypatch,
        failure_at=failure_at,
        infeasible_at=infeasible_at,
    )
    with pytest.raises(cross_law.ProspectiveCrossLawDiscoveryError, match=message):
        cross_law.build_cross_law_discovery_batch(
            base,
            season=SEASON,
            week=WEEK,
            cbwu_seed_label=LABEL,
            stack=preset.stack,
            policy_env=environment,
        )
    expected_calls = failure_at if failure_at is not None else infeasible_at
    assert len(calls) == int(expected_calls) + 1


def test_marginal_drift_is_detected_before_any_milp(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, preset, environment = _base_batch()
    solver_calls = _install_solver(monkeypatch)
    original = cross_law._rank_transport

    def drift(row: np.ndarray, latent: np.ndarray) -> np.ndarray:
        result = original(row, latent).copy()
        result[0] = np.nextafter(result[0], np.float32(np.inf))
        return result

    monkeypatch.setattr(cross_law, "_rank_transport", drift)
    with pytest.raises(
        cross_law.ProspectiveCrossLawDiscoveryError,
        match="drifted at least one player marginal",
    ):
        cross_law.build_cross_law_discovery_batch(
            base,
            season=SEASON,
            week=WEEK,
            cbwu_seed_label=LABEL,
            stack=preset.stack,
            policy_env=environment,
        )
    assert solver_calls == []


@pytest.mark.parametrize("tamper", ["scores", "row_draws", "ledger", "law"])
def test_independent_validator_rejects_transformed_tampering(
    monkeypatch: pytest.MonkeyPatch, tamper: str
) -> None:
    base, transformed, preset, environment, _ = _build(monkeypatch)
    metadata = deepcopy(transformed.metadata)
    totals = transformed.candidate_totals.copy()
    row_draws = transformed.row_draws.copy()
    if tamper == "scores":
        totals[-1, 0] += np.float32(1.0)
    elif tamper == "row_draws":
        row_draws[2, 0] += np.float32(1.0)
    elif tamper == "ledger":
        metadata["cross_law_discovery"]["exposure_ledger"]["rows"][0]["status"] = "dup"
    else:
        metadata["cross_law_discovery"]["law"]["lam_team"] = 0.6
    tampered = replace(
        transformed,
        candidate_totals=totals,
        row_draws=row_draws,
        metadata=metadata,
    )
    with pytest.raises(cross_law.ProspectiveCrossLawDiscoveryError):
        cross_law.validate_cross_law_discovery_batch(
            base,
            tampered,
            season=SEASON,
            week=WEEK,
            cbwu_seed_label=LABEL,
            stack=preset.stack,
            policy_env=environment,
        )


def test_native_allocation_and_construction_law_tampering_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, preset, environment = _base_batch()
    _install_solver(monkeypatch)
    metadata = deepcopy(base.metadata)
    metadata["generation_allocation"]["boom_requested"] = 160
    wrong_allocation = replace(base, metadata=metadata)
    with pytest.raises(
        cross_law.ProspectiveCrossLawDiscoveryError,
        match="native allocation differs",
    ):
        cross_law.build_cross_law_discovery_batch(
            wrong_allocation,
            season=SEASON,
            week=WEEK,
            cbwu_seed_label=LABEL,
            stack=preset.stack,
            policy_env=environment,
        )

    wrong_env = dict(environment)
    wrong_env["MIN_LINEUP_SALARY"] = "0"
    with pytest.raises(
        cross_law.ProspectiveCrossLawDiscoveryError,
        match="optimizer environment differs",
    ):
        cross_law.build_cross_law_discovery_batch(
            base,
            season=SEASON,
            week=WEEK,
            cbwu_seed_label=LABEL,
            stack=preset.stack,
            policy_env=wrong_env,
        )

    rows = [dict(row) for row in base.player_rows]
    rows[0]["salary"] = 1_000
    mismatched_salary = replace(base, player_rows=tuple(rows))
    calls = _install_solver(monkeypatch)
    with pytest.raises(
        cross_law.ProspectiveCrossLawDiscoveryError,
        match="violates bound construction",
    ):
        cross_law.build_cross_law_discovery_batch(
            mismatched_salary,
            season=SEASON,
            week=WEEK,
            cbwu_seed_label=LABEL,
            stack=preset.stack,
            policy_env=environment,
        )
    assert calls == []


def test_nonnull_realized_outcome_is_rejected_before_solver(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, preset, environment = _base_batch()
    rows = [dict(row) for row in base.player_rows]
    rows[5]["actual"] = 31.7
    tainted = replace(base, player_rows=tuple(rows))
    calls = _install_solver(monkeypatch)
    with pytest.raises(
        cross_law.ProspectiveCrossLawDiscoveryError,
        match="received realized outcome data",
    ):
        cross_law.build_cross_law_discovery_batch(
            tainted,
            season=SEASON,
            week=WEEK,
            cbwu_seed_label=LABEL,
            stack=preset.stack,
            policy_env=environment,
        )
    assert calls == []


def test_receipt_is_self_hashed_and_binds_both_banks_and_fixed_law(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, transformed, _, _, _ = _build(monkeypatch)
    receipt = deepcopy(transformed.metadata["cross_law_discovery"])
    retained = receipt.pop("receipt_sha256")
    assert retained == cross_law.canonical_sha256(receipt)
    assert receipt["law_sha256"] == cross_law.LAW_SHA256
    assert receipt["base_world_bank_receipt"] == cross_law._array_receipt(
        base.row_draws
    )
    assert receipt["discovery_world_bank_receipt"] != receipt[
        "base_world_bank_receipt"
    ]
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["outcome_columns_read"] == []
    assert receipt["cloud_mutation_performed"] is False
    assert receipt["production_policy_changed"] is False


def test_public_outcome_free_rebuilder_returns_exact_read_only_discovery_bank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    base, transformed, _, _, _ = _build(monkeypatch)
    receipt = transformed.metadata["cross_law_discovery"]
    discovery = cross_law.rebuild_cross_law_discovery_world_matrix(
        base, receipt
    )
    assert discovery.flags.c_contiguous
    assert discovery.flags.writeable is False
    assert cross_law._array_receipt(discovery) == receipt[
        "discovery_world_bank_receipt"
    ]
    assert not np.array_equal(discovery, base.row_draws)

    changed, _, _ = _base_batch(perturb=0.125)
    with pytest.raises(
        cross_law.ProspectiveCrossLawDiscoveryError,
        match="base world identity differs",
    ):
        cross_law.rebuild_cross_law_discovery_world_matrix(changed, receipt)
