from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from itertools import combinations

import numpy as np
import pytest

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference import prospective_all_boom_ceiling as arm
from nfl_dfs.inference.generation_exposure import canonical_sha256
from nfl_dfs.inference.production_policy import ADOPTED_CLASSIC_POLICY
from nfl_dfs.optimizer.lineup import Lineup, StackRules


def _player(
    player_id: str,
    pos: str,
    team: str,
    opp: str,
    game_id: str,
) -> dict:
    return {
        "id": player_id,
        "name": player_id,
        "pos": pos,
        "team": team,
        "opp": opp,
        "game_id": game_id,
        "salary": 5_500,
        "proj": 10.0,
        "proj_tourney": 10.0,
    }


def _players_and_rosters() -> tuple[list[dict], list[list[str]]]:
    players = [_player("qb-a", "QB", "A", "B", "g1")]
    players.extend(
        _player(f"wr-a-{index:02d}", "WR", "A", "B", "g1")
        for index in range(20)
    )
    players.extend([
        _player("wr-b-00", "WR", "B", "A", "g1"),
        _player("wr-b-01", "WR", "B", "A", "g1"),
        _player("wr-c", "WR", "C", "D", "g2"),
        _player("rb-d", "RB", "D", "C", "g2"),
        _player("rb-e", "RB", "E", "F", "g3"),
        _player("rb-j", "RB", "J", "K", "g5"),
        _player("te-f", "TE", "F", "E", "g3"),
        _player("te-i", "TE", "I", "J", "g5"),
        _player("dst-g", "DST", "G", "H", "g4"),
    ])
    rosters: list[list[str]] = []
    a_receivers = [f"wr-a-{index:02d}" for index in range(20)]
    for bring_back in ("wr-b-00", "wr-b-01"):
        for first, second in combinations(a_receivers, 2):
            rosters.append([
                "qb-a", first, second, bring_back, "wr-c",
                "rb-d", "rb-e", "te-f", "dst-g",
            ])
    assert len(rosters) >= arm.BOOM_ATTEMPTS
    return players, rosters


def _source_batches() -> tuple[CandidateBatch, CandidateBatch, list[list[str]]]:
    players, rosters = _players_and_rosters()
    player_ids = tuple(player["id"] for player in players)
    by_id = {player["id"]: player for player in players}
    auxiliary = Lineup([by_id[player_id] for player_id in rosters[0]], tag="epi")
    generation_draws = np.zeros(
        (len(players), arm.WORLDS_PER_BANK), dtype=np.float32,
    )
    # Give the lab scheduler a strict order so the fixture's 200 roster
    # identities can be indexed directly by the chosen world ID.
    generation_draws[0] = np.arange(
        arm.WORLDS_PER_BANK, 0, -1, dtype=np.float32,
    )
    # The selection law is deliberately different from the generation
    # scheduler. Candidate totals must be rebuilt from this bank only.
    selection_draws = np.repeat(
        np.arange(1, len(players) + 1, dtype=np.float32)[:, None],
        arm.WORLDS_PER_BANK,
        axis=1,
    )
    preset_receipt = ADOPTED_CLASSIC_POLICY.construction_preset().receipt()
    source = CandidateBatch(
        candidates=(auxiliary,),
        candidate_totals=np.zeros((1, arm.WORLDS_PER_BANK), dtype=np.float32),
        player_ids=player_ids,
        player_rows=tuple(players),
        row_draws=generation_draws,
        all_tags={auxiliary.ids: ("epi", "epi:role-draw-1")},
        metadata={
            "model_version": "main-v1",
            "role_model_version": "role-v1",
            "construction_preset_receipt": preset_receipt,
            "generation_allocation": {
                "leverage_requested": 0,
                "leverage_solve_attempts": 0,
                "leverage_successful": 0,
                "boom_requested": 0,
                "boom_attempted": 0,
                "boom_successful": 0,
                "boom_solver_errors": 0,
                "boom_infeasible": 0,
                "boom_duplicates": 0,
                "boom_failures": 0,
                "boom_unique_added": 0,
                "boom_unique_fill": False,
                "core_requested": 0,
                "ce_requested": 0,
                "role_or_epistemic_requested": 12,
                "gumbel_requested": 0,
                "total_requested_with_replacement_families": 12,
                "unique_candidates_after_all_families": 1,
            },
            "uses_realized_outcomes": False,
            "uses_post_lock_outcomes": False,
        },
    )
    selection = CandidateBatch(
        candidates=(),
        candidate_totals=np.empty(
            (0, arm.WORLDS_PER_BANK), dtype=np.float32,
        ),
        player_ids=player_ids,
        player_rows=tuple(players),
        row_draws=selection_draws,
        all_tags={},
        metadata={
            "uses_realized_outcomes": False,
            "uses_post_lock_outcomes": False,
        },
    )
    return source, selection, rosters


def _build(
    source: CandidateBatch,
    selection: CandidateBatch,
    rosters: list[list[str]],
    *,
    solver=None,
) -> tuple[CandidateBatch, list[int]]:
    calls: list[int] = []

    def ordinary_solver(**kwargs):
        world_id = kwargs["world_id"]
        calls.append(world_id)
        rows = {row["id"]: row for row in kwargs["player_rows"]}
        return Lineup([rows[player_id] for player_id in rosters[world_id]])

    result = arm.build_all_boom_ceiling_batch(
        source,
        selection,
        stack=ADOPTED_CLASSIC_POLICY.construction_preset().stack,
        locks=set(),
        env=arm.all_boom_ceiling_environment({}),
        source_label="all_boom_ceiling_r0",
        solve_world=solver or ordinary_solver,
    )
    return result, calls


@pytest.fixture(scope="module")
def built_arm():
    source, selection, rosters = _source_batches()
    result, calls = _build(source, selection, rosters)
    return source, selection, rosters, result, calls


def test_identity_allocation_and_environment_are_optional_and_default_off():
    env = arm.all_boom_ceiling_environment({
        "N_LEV": "999",
        "N_BOOM": "1",
        "SELECT_LADDER": "220:1",
        "ATLAS_BOOM_WORLD_RANKING": "1",
    })
    receipt = arm.validate_all_boom_ceiling_environment(env)

    assert env["N_LEV"] == "0"
    assert env["N_BOOM"] == "200"
    assert env["GEN_TOTAL_BUDGET"] == "212"
    assert env["PROSPECTIVE_SHADOW_ID"] == arm.SHADOW_ID
    assert env["SELECT_LADDER"] == ""
    assert "ATLAS_BOOM_WORLD_RANKING" not in env
    assert receipt["core_allocation"] == {
        "leverage": 0, "boom": 200, "total": 200,
    }
    assert receipt["evidence_status"] == "unpassed_optional"
    assert receipt["production_enabled"] is False
    assert arm.SHADOW_ID != "2026-boom-first-v1"

    drift = dict(env)
    drift["N_BOOM"] = "199"
    with pytest.raises(arm.AllBoomCeilingContractError, match="drifts"):
        arm.validate_all_boom_ceiling_environment(drift)


def test_world_order_is_exact_lab_quantity_and_literal_lab_tie_order():
    positions = [
        "QB", "RB", "RB", "RB", "WR", "WR", "WR", "WR",
        "TE", "TE", "DST",
    ]
    rows = [{"pos": position} for position in positions]
    draws = np.zeros((len(rows), 4), dtype=np.float32)
    draws[:-1, 0] = 10.0
    draws[:-1, 1] = 7.0
    draws[-1, 1] = 50.0
    draws[:-1, 2:] = 5.0  # worlds 2 and 3 tie exactly

    values = arm.lab_legal_roster_ceiling_values(draws, rows)
    order = arm.legal_roster_ceiling_world_order(draws, rows)

    assert values.tolist() == [100.0, 70.0, 50.0, 50.0]
    assert np.array_equal(order, np.argsort(values)[::-1])
    # The ATLAS proxy includes DST and only one valid flex shape, so it would
    # prefer world 1 (56 skill/QB + 50 DST) to world 0 (80 + 0). PREREG-017
    # intentionally does the opposite.
    assert 56.0 + 50.0 > 80.0

    tie_draws = np.full((len(rows), 2), 5.0, dtype=np.float32)
    tie_values = arm.lab_legal_roster_ceiling_values(tie_draws, rows)
    tie_order = arm.legal_roster_ceiling_world_order(tie_draws, rows)
    assert tie_values.tolist() == [50.0, 50.0]
    assert tie_order.tolist() == np.argsort(tie_values)[::-1].tolist()
    assert tie_order.tolist() == [1, 0]


def test_transform_preserves_noncore_and_records_all_200_attempts(built_arm):
    source, selection, _, result, calls = built_arm
    ledger = result.metadata["solve_exposure_ledger"]
    allocation = result.metadata["generation_allocation"]

    assert calls == list(range(arm.BOOM_ATTEMPTS))
    assert result.candidates[0].ids == source.candidates[0].ids
    assert result.metadata["passthrough_candidates"] is True
    assert result.metadata["passthrough_receipt"]["core_requested"] == 0
    assert allocation["leverage_requested"] == 0
    assert allocation["boom_requested"] == allocation["boom_attempted"] == 200
    assert allocation["boom_successful"] == 200
    assert allocation["core_requested"] == 200
    assert ledger["attempt_count"] == 200
    assert ledger["expected_requests_by_family"] == {"boom": 200}
    assert ledger["status_counts"]["dup"] == 1
    assert ledger["status_counts"]["new"] == 199
    assert ledger["rows"][0]["duplicate_origin"] == "preexisting"
    assert ledger["rows"][0]["world_id"] == 0
    assert result.metadata["world_order_receipt"]["atlas_proxy_used"] is False
    assert result.metadata["world_order_receipt"]["position_caps"] == {
        "QB": 1, "RB": 3, "WR": 4, "TE": 2,
    }
    assert result.metadata["world_order_receipt"]["tie_break"] == (
        "numpy-argsort-reversed"
    )
    transform = result.metadata["all_boom_ceiling"]
    transform_body = dict(transform)
    transform_sha = transform_body.pop("receipt_sha256")
    assert transform["schema_version"] == arm.TRANSFORM_SCHEMA
    assert transform["shadow_id"] == arm.SHADOW_ID
    assert transform["evidence_status"] == "unpassed_optional"
    assert transform["generation_allocation"] == allocation
    assert transform["passthrough_receipt"] == result.metadata[
        "passthrough_receipt"
    ]
    assert transform["solve_exposure_ledger"] == ledger
    assert transform["solve_exposure_ledger_sha256"] == ledger[
        "ledger_sha256"
    ]
    assert transform["world_order_receipt"] == result.metadata[
        "world_order_receipt"
    ]
    assert transform["generation_world_bank_receipt"] == result.metadata[
        "generation_world_bank_receipt"
    ]
    assert transform["selection_world_bank_receipt"] == result.metadata[
        "selection_world_bank_receipt"
    ]
    assert transform["environment_receipt"] == result.metadata[
        "environment_receipt"
    ]
    assert transform["construction_preset_receipt"] == result.metadata[
        "construction_preset_receipt"
    ]
    assert canonical_sha256(transform_body) == transform_sha
    assert result.metadata["evidence_status"] == "unpassed_optional"
    assert result.metadata["production_enabled"] is False
    assert result.metadata["adoption_authorized"] is False
    # Candidate scoring is rebuilt on the independent base-law selection
    # bank, not the all-zero generation bank.
    selection_index = {
        player_id: index for index, player_id in enumerate(selection.player_ids)
    }
    expected = selection.row_draws[[
        selection_index[player_id] for player_id in result.candidates[0].ids
    ]].sum(axis=0)
    assert np.array_equal(result.candidate_totals[0], expected)
    assert np.count_nonzero(result.candidate_totals[0]) == arm.WORLDS_PER_BANK


def test_selector_is_exact_base_law_coverage_194(monkeypatch, built_arm):
    _, _, _, result, _ = built_arm
    observed = {}

    def fake_selector(totals, n_entries, line, env):
        observed.update({
            "totals": totals,
            "n_entries": n_entries,
            "line": line,
            "env": env,
        })
        return list(range(n_entries - 1, -1, -1))

    monkeypatch.setattr(arm, "select_tail_entries", fake_selector)
    lineups, receipt = arm.select_all_boom_ceiling_book(result)

    assert observed["totals"] is result.candidate_totals
    assert observed["n_entries"] == 80
    assert observed["line"] == 194.0
    assert observed["env"] == {}
    assert [lineup.ids for lineup in lineups] == [
        result.candidates[index].ids for index in range(79, -1, -1)
    ]
    assert receipt["selection_id"] == "base-law-coverage-194-v1"
    assert receipt["law"] == "untouched-production-base-law"
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["production_enabled"] is False


def test_solver_or_contract_shortfall_fails_closed_with_complete_ledger():
    source, selection, rosters = _source_batches()
    calls = []

    def one_bad_solver(**kwargs):
        world_id = kwargs["world_id"]
        calls.append(world_id)
        rows = {row["id"]: row for row in kwargs["player_rows"]}
        chosen = [dict(rows[player_id]) for player_id in rosters[world_id]]
        if world_id == 0:
            chosen[0]["salary"] += 100  # identity/salary mutation is fatal
        return Lineup(chosen)

    with pytest.raises(
        arm.AllBoomCeilingContractError,
        match="did not complete 200 successful attempts",
    ) as caught:
        _build(source, selection, rosters, solver=one_bad_solver)

    assert calls == list(range(200))
    assert caught.value.exposure_ledger["attempt_count"] == 200
    assert caught.value.exposure_ledger["status_counts"]["error"] == 1


def test_passthrough_construction_and_allocation_drift_fail_before_solves():
    source, selection, _ = _source_batches()
    env = arm.all_boom_ceiling_environment({})
    preset = ADOPTED_CLASSIC_POLICY.construction_preset()

    with pytest.raises(arm.AllBoomCeilingContractError, match="passthrough"):
        arm.build_all_boom_ceiling_batch(
            source, selection, stack=preset.stack, locks=set(), env=env,
            passthrough_candidates=False,
        )
    with pytest.raises(arm.AllBoomCeilingContractError, match="stack differs"):
        arm.build_all_boom_ceiling_batch(
            source, selection, stack=StackRules(), locks=set(), env=env,
        )
    with pytest.raises(arm.AllBoomCeilingContractError, match="lock set"):
        arm.build_all_boom_ceiling_batch(
            source, selection, stack=preset.stack, locks={"qb-a"}, env=env,
        )

    bad_metadata = deepcopy(source.metadata)
    bad_metadata["generation_allocation"]["boom_requested"] = 1
    bad_source = CandidateBatch(
        candidates=source.candidates,
        candidate_totals=source.candidate_totals,
        player_ids=source.player_ids,
        player_rows=source.player_rows,
        row_draws=source.row_draws,
        all_tags=source.all_tags,
        metadata=bad_metadata,
    )
    with pytest.raises(arm.AllBoomCeilingContractError, match="does not prove 0"):
        arm.build_all_boom_ceiling_batch(
            bad_source, selection, stack=preset.stack, locks=set(), env=env,
        )


def _object_identity(name: str, created_at: datetime) -> dict:
    return {
        "uri": f"gs://shadow-test/{name}.bin",
        "generation": "12345",
        "sha256": "a" * 64,
        "bytes": 123,
        "create_only": True,
        "created_at": created_at,
    }


def test_prelock_receipt_is_create_only_outcome_free_and_unpassed(built_arm):
    _, _, _, result, _ = built_arm
    _, selection_receipt = arm.select_all_boom_ceiling_book(result)
    captured = datetime(2026, 9, 6, 15, 0, tzinfo=timezone.utc)
    generated = datetime(2026, 9, 6, 16, 0, tzinfo=timezone.utc)
    lock = datetime(2026, 9, 6, 17, 0, tzinfo=timezone.utc)
    identities = {
        "generation_world_object": _object_identity("generation", captured),
        "selection_world_object": _object_identity("selection", captured),
        "candidate_object": _object_identity("candidates", generated),
    }
    receipt = arm.build_prelock_receipt(
        result,
        selection_receipt,
        generated_at=generated,
        lock_at=lock,
        **identities,
    )

    assert receipt["strictly_prelock"] is True
    assert receipt["evidence_status"] == "unpassed_optional"
    assert receipt["persistence_contract"] == {
        "if_generation_match": 0,
        "create_only": True,
        "receipt_must_be_persisted_before_lock": True,
    }
    assert receipt["uses_realized_outcomes"] is False
    assert receipt["uses_post_lock_outcomes"] is False
    assert receipt["production_enabled"] is False
    assert receipt["adoption_authorized"] is False
    assert arm.validate_prelock_receipt(receipt) == receipt

    with pytest.raises(arm.AllBoomCeilingContractError, match="before lock"):
        arm.build_prelock_receipt(
            result,
            selection_receipt,
            generated_at=lock,
            lock_at=lock,
            **identities,
        )
    not_create_only = deepcopy(identities)
    not_create_only["candidate_object"]["create_only"] = False
    with pytest.raises(arm.AllBoomCeilingContractError, match="create-only"):
        arm.build_prelock_receipt(
            result,
            selection_receipt,
            generated_at=generated,
            lock_at=lock,
            **not_create_only,
        )

    tampered = deepcopy(receipt)
    tampered["production_enabled"] = True
    body = dict(tampered)
    body.pop("receipt_sha256")
    tampered["receipt_sha256"] = canonical_sha256(body)
    with pytest.raises(arm.AllBoomCeilingContractError, match="fixed law"):
        arm.validate_prelock_receipt(tampered)


def test_outcome_fields_and_batch_tampering_fail_closed(built_arm):
    source, selection, _, result, _ = built_arm
    tainted_rows = list(source.player_rows)
    tainted_rows[0] = {**tainted_rows[0], "actual_points": 35.0}
    tainted = CandidateBatch(
        candidates=source.candidates,
        candidate_totals=source.candidate_totals,
        player_ids=source.player_ids,
        player_rows=tuple(tainted_rows),
        row_draws=source.row_draws,
        all_tags=source.all_tags,
        metadata=source.metadata,
    )
    with pytest.raises(arm.AllBoomCeilingContractError, match="outcome field"):
        arm.build_all_boom_ceiling_batch(
            tainted,
            selection,
            stack=ADOPTED_CLASSIC_POLICY.construction_preset().stack,
            locks=set(),
            env=arm.all_boom_ceiling_environment({}),
        )

    drifted = CandidateBatch(
        candidates=result.candidates,
        candidate_totals=result.candidate_totals.copy(),
        player_ids=result.player_ids,
        player_rows=result.player_rows,
        row_draws=result.row_draws,
        all_tags=result.all_tags,
        metadata={**result.metadata, "evidence_status": "passed"},
    )
    with pytest.raises(arm.AllBoomCeilingContractError, match="evidence_status"):
        arm.validate_all_boom_ceiling_batch(drifted)

    changed_totals = result.candidate_totals.copy()
    changed_totals[0, 0] += 1.0
    drifted_totals = CandidateBatch(
        candidates=result.candidates,
        candidate_totals=changed_totals,
        player_ids=result.player_ids,
        player_rows=result.player_rows,
        row_draws=result.row_draws,
        all_tags=result.all_tags,
        metadata=result.metadata,
    )
    with pytest.raises(arm.AllBoomCeilingContractError, match="base law"):
        arm.validate_all_boom_ceiling_batch(drifted_totals)

    changed_transform = deepcopy(result.metadata)
    changed_transform["all_boom_ceiling"][
        "solve_exposure_ledger_sha256"
    ] = "0" * 64
    transform_body = dict(changed_transform["all_boom_ceiling"])
    transform_body.pop("receipt_sha256")
    changed_transform["all_boom_ceiling"]["receipt_sha256"] = (
        canonical_sha256(transform_body)
    )
    drifted_transform = CandidateBatch(
        candidates=result.candidates,
        candidate_totals=result.candidate_totals,
        player_ids=result.player_ids,
        player_rows=result.player_rows,
        row_draws=result.row_draws,
        all_tags=result.all_tags,
        metadata=changed_transform,
    )
    with pytest.raises(arm.AllBoomCeilingContractError, match="binding differs"):
        arm.validate_all_boom_ceiling_batch(drifted_transform)

    outcome_transform = deepcopy(result.metadata)
    outcome_transform["all_boom_ceiling"]["outcome"] = 1
    transform_body = dict(outcome_transform["all_boom_ceiling"])
    transform_body.pop("receipt_sha256")
    outcome_transform["all_boom_ceiling"]["receipt_sha256"] = (
        canonical_sha256(transform_body)
    )
    tainted_transform = CandidateBatch(
        candidates=result.candidates,
        candidate_totals=result.candidate_totals,
        player_ids=result.player_ids,
        player_rows=result.player_rows,
        row_draws=result.row_draws,
        all_tags=result.all_tags,
        metadata=outcome_transform,
    )
    with pytest.raises(arm.AllBoomCeilingContractError, match="outcome field"):
        arm.validate_all_boom_ceiling_batch(tainted_transform)
