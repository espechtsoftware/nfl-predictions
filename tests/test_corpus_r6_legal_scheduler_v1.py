from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
from hashlib import sha256
from itertools import combinations, product
import json

import numpy as np
import pytest

from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import corpus_r6_legal_scheduler_v1 as scheduler
from nfl_dfs.research import residual_world_columns as rw


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1", 8_000),
        ("q-c", "QB", "C", "D", "g2", 7_500),
        ("rb-a1", "RB", "A", "B", "g1", 7_500),
        ("rb-a2", "RB", "A", "B", "g1", 4_000),
        ("rb-b", "RB", "B", "A", "g1", 6_500),
        ("rb-c", "RB", "C", "D", "g2", 7_000),
        ("rb-d", "RB", "D", "C", "g2", 4_500),
        ("wr-a1", "WR", "A", "B", "g1", 6_500),
        ("wr-a2", "WR", "A", "B", "g1", 5_000),
        ("wr-b", "WR", "B", "A", "g1", 5_500),
        ("wr-c1", "WR", "C", "D", "g2", 6_000),
        ("wr-c2", "WR", "C", "D", "g2", 4_000),
        ("wr-d", "WR", "D", "C", "g2", 4_500),
        ("te-a", "TE", "A", "B", "g1", 5_000),
        ("te-b", "TE", "B", "A", "g1", 4_000),
        ("te-c", "TE", "C", "D", "g2", 4_000),
        ("dst-b", "DST", "B", "A", "g1", 3_000),
        ("dst-c", "DST", "C", "D", "g2", 3_000),
    )
    return tuple(sorted((
        rw.PlayerSpec(player_id, position, team, opponent, game, salary)
        for player_id, position, team, opponent, game, salary in rows
    ), key=lambda player: player.player_id))


def _scores(players: tuple[rw.PlayerSpec, ...]) -> np.ndarray:
    # Entirely synthetic worlds. World 0 rewards several mutually illegal
    # correlations; world 1 rewards an over-cap collection; world 2 creates
    # broad ties to exercise canonical ordering.
    by_id = {player.player_id: index for index, player in enumerate(players)}
    points = np.full((len(players), 3), 8.0, dtype=np.float64)
    world_zero = {
        "q-a": 31, "q-c": 20,
        "rb-a1": 30, "rb-a2": 29, "rb-b": 18, "rb-c": 17, "rb-d": 25,
        "wr-a1": 23, "wr-a2": 22, "wr-b": 21,
        "wr-c1": 28, "wr-c2": 27, "wr-d": 26,
        "te-a": 19, "te-b": 18, "te-c": 17,
        "dst-b": 29, "dst-c": 28,
    }
    world_one = {
        "q-a": 35, "q-c": 18,
        "rb-a1": 34, "rb-a2": 12, "rb-b": 33, "rb-c": 32, "rb-d": 11,
        "wr-a1": 31, "wr-a2": 14, "wr-b": 30,
        "wr-c1": 29, "wr-c2": 13, "wr-d": 12,
        "te-a": 28, "te-b": 10, "te-c": 11,
        "dst-b": 20, "dst-c": 9,
    }
    for player_id, value in world_zero.items():
        points[by_id[player_id], 0] = value
    for player_id, value in world_one.items():
        points[by_id[player_id], 1] = value
    points[:, 2] = 15.0
    return np.rint(points * rw.MICRO_DK_SCALE).astype(np.int64)


def _all_dk_rosters(
    players: tuple[rw.PlayerSpec, ...],
) -> tuple[tuple[str, ...], ...]:
    by_position = {
        position: tuple(
            player.player_id for player in players if player.position == position
        )
        for position in scheduler.POSITIONS
    }
    result: set[tuple[str, ...]] = set()
    for rb_count, wr_count, te_count in rw.CLASSIC_SKILL_PATTERNS:
        for qb, rbs, wrs, tes, dst in product(
            by_position["QB"],
            combinations(by_position["RB"], rb_count),
            combinations(by_position["WR"], wr_count),
            combinations(by_position["TE"], te_count),
            by_position["DST"],
        ):
            roster = tuple(sorted((qb, *rbs, *wrs, *tes, dst)))
            try:
                legal.audit_dk_classic(players, roster)
            except legal.CorpusLegalFeasibilityError:
                continue
            result.add(roster)
    return tuple(sorted(result))


def _profile_legal_rosters(
    players: tuple[rw.PlayerSpec, ...],
    dk_rosters: tuple[tuple[str, ...], ...],
    profile: legal.EffectivePolicyProfile,
) -> tuple[tuple[str, ...], ...]:
    return tuple(
        roster for roster in dk_rosters
        if not any(
            profile.value(field) not in (0, False)
            for field in legal.house_rule_violations(players, roster)
        )
    )


def _roster_score(
    roster: tuple[str, ...],
    players: tuple[rw.PlayerSpec, ...],
    scores: np.ndarray,
    world: int,
) -> int:
    row = {player.player_id: index for index, player in enumerate(players)}
    return sum(int(scores[row[player_id], world]) for player_id in roster)


@pytest.fixture(scope="module")
def players() -> tuple[rw.PlayerSpec, ...]:
    return _players()


@pytest.fixture(scope="module")
def scores(players) -> np.ndarray:
    return _scores(players)


@pytest.fixture(scope="module")
def dk_rosters(players) -> tuple[tuple[str, ...], ...]:
    return _all_dk_rosters(players)


@pytest.fixture(scope="module")
def legal_by_profile(players, dk_rosters):
    return {
        profile.parameter_set_id: _profile_legal_rosters(
            players, dk_rosters, profile
        )
        for profile in legal.frozen_policy_profiles()
    }


@pytest.fixture(scope="module")
def incumbents(legal_by_profile) -> tuple[tuple[str, ...], ...]:
    rows = legal_by_profile["incumbent"]
    assert rows
    return rows[:12]


@pytest.fixture(scope="module")
def world_ids(scores) -> tuple[rw.WorldId, ...]:
    return tuple(rw.WorldId("R0", index) for index in range(scores.shape[1]))


@pytest.fixture(scope="module")
def source_artifact() -> scheduler.SourceArtifactIdentity:
    return scheduler.SourceArtifactIdentity(
        uri="gs://example/simulated-worlds.npz",
        generation=17,
        byte_count=12_345,
        sha256="a" * 64,
        scientific_contract_sha256="b" * 64,
    )


def _producer(proxy_id: str) -> scheduler.ProducerIdentity:
    return scheduler.ProducerIdentity(
        proxy_id=proxy_id,
        code_sha256="c" * 64,
        image_digest="sha256:" + "d" * 64,
    )


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode()


def _coherently_rehash_proxy(
    receipt: scheduler.ProxyReceipt,
    mutate,
) -> scheduler.ProxyReceipt:
    payload = json.loads(receipt.canonical_payload)
    mutate(payload)
    payload.pop("receipt_sha256", None)
    digest = sha256(_canonical(payload)).hexdigest()
    payload["receipt_sha256"] = digest
    return replace(
        receipt,
        canonical_payload=_canonical(payload),
        receipt_sha256=digest,
        selected_indices=tuple(payload.get("selected_indices", ())),
        proxy_id=str(payload.get("proxy_id", receipt.proxy_id)),
    )


def _coherently_rehash_dose(
    receipt: scheduler.DoseReceipt,
    mutate,
) -> scheduler.DoseReceipt:
    payload = json.loads(receipt.canonical_payload)
    mutate(payload)
    payload.pop("dose_sha256", None)
    digest = sha256(_canonical(payload)).hexdigest()
    payload["dose_sha256"] = digest
    return replace(
        receipt,
        canonical_payload=_canonical(payload),
        dose_sha256=digest,
        proxy_id=str(payload.get("proxy_id", receipt.proxy_id)),
    )


def test_stable_micro_ranker_is_total_and_fails_closed():
    assert scheduler.stable_rank_micro(np.array([4, 7, 7, -1]), 3) == (1, 2, 0)
    assert scheduler.stable_rank_micro(
        np.array([np.iinfo(np.int64).min, 0], dtype=np.int64), 2
    ) == (1, 0)
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="integer vector"):
        scheduler.stable_rank_micro(np.array([1.0, 2.0]), 1)
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="exceeds"):
        scheduler.stable_rank_micro(np.array([1, 2]), 3)
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="integer"):
        scheduler.stable_rank_micro(np.array([True, False]), 1)


def test_theta_zero_exactly_matches_existing_position_bound(players, scores):
    profile = legal.frozen_policy_profiles()[0]
    observed = scheduler.position_salary_upper_bounds_micro(
        scores,
        players,
        profile,
        dose=scheduler.SalaryPositionDose((0,)),
    )
    expected = rw.position_shape_upper_bounds_micro(
        scores, tuple(player.position for player in players)
    )
    assert np.array_equal(observed, expected)
    assert observed.flags.writeable is False


def test_salary_relaxation_is_never_looser_and_can_be_stricter(players, scores):
    profile = legal.frozen_policy_profiles()[0]
    position_only = scheduler.position_salary_upper_bounds_micro(
        scores, players, profile, dose=scheduler.SalaryPositionDose((0,))
    )
    salary_aware = scheduler.position_salary_upper_bounds_micro(
        scores, players, profile
    )
    assert np.all(salary_aware <= position_only)
    assert np.any(salary_aware < position_only)
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="include zero"):
        scheduler.SalaryPositionDose((1_000, 2_000))
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="sorted"):
        scheduler.SalaryPositionDose((0, -1_000))


@pytest.mark.parametrize(
    "profile", legal.frozen_policy_profiles(), ids=lambda p: p.parameter_set_id
)
def test_position_salary_bound_dominates_exhaustive_profile_optimum(
    players, scores, legal_by_profile, profile,
):
    rosters = legal_by_profile[profile.parameter_set_id]
    assert rosters
    exact = np.asarray([
        max(_roster_score(roster, players, scores, world) for roster in rosters)
        for world in range(scores.shape[1])
    ], dtype=np.int64)
    bound = scheduler.position_salary_upper_bounds_micro(
        scores, players, profile
    )
    assert np.all(bound >= exact)


@pytest.mark.parametrize(
    "profile", legal.frozen_policy_profiles(), ids=lambda p: p.parameter_set_id
)
def test_feasible_core_is_exhaustively_proven_lower_bound_for_all_profiles(
    players, scores, incumbents, legal_by_profile, profile,
):
    rosters = legal_by_profile[profile.parameter_set_id]
    exact = tuple(
        max(_roster_score(roster, players, scores, world) for roster in rosters)
        for world in range(scores.shape[1])
    )
    first = scheduler.bounded_feasible_core_lower_bounds_micro(
        scores, players, profile, incumbents
    )
    second = scheduler.bounded_feasible_core_lower_bounds_micro(
        scores, players, profile, incumbents
    )

    assert first == second
    assert all(
        lower <= optimum
        for lower, optimum in zip(first.lower_bounds_micro, exact, strict=True)
    )
    assert all(
        lower >= sentinel
        for lower, sentinel in zip(
            first.lower_bounds_micro,
            first.incumbent_sentinel_scores_micro,
            strict=True,
        )
    )
    assert any(
        lower > sentinel
        for lower, sentinel in zip(
            first.lower_bounds_micro,
            first.incumbent_sentinel_scores_micro,
            strict=True,
        )
    )
    assert all(
        used <= scheduler.DEFAULT_FEASIBLE_CORE_DOSE.max_state_expansions
        for used in first.state_expansions
    )
    assert all(
        used <= scheduler.DEFAULT_FEASIBLE_CORE_DOSE.max_combination_candidates
        for used in first.combination_candidates_considered
    )
    assert all(
        used <= scheduler.DEFAULT_FEASIBLE_CORE_DOSE.max_core_candidates
        for used in first.core_candidates_considered
    )
    assert first.incumbent_candidates_evaluated == len(incumbents)
    assert first.incumbent_score_cells_evaluated == len(incumbents) * scores.shape[1]
    for world, roster in enumerate(first.rosters):
        scheduler.audit_profile_roster(players, roster, profile)
        assert _roster_score(roster, players, scores, world) == (
            first.lower_bounds_micro[world]
        )


def test_each_single_rule_relaxation_accepts_only_its_adversarial_roster(
    players, dk_rosters,
):
    profiles = legal.frozen_policy_profiles()
    incumbent = profiles[0]
    relaxed_by_field = {
        field: profiles[index]
        for index, field in enumerate((
            "min_lineup_salary",
            "qb_stack_min",
            "bring_back_min",
            "forbid_rb_vs_dst",
            "forbid_two_rb_same_team",
        ), start=1)
    }
    for field, relaxed in relaxed_by_field.items():
        adversarial = next(
            roster for roster in dk_rosters
            if legal.house_rule_violations(players, roster) == (field,)
        )
        with pytest.raises(
            scheduler.CorpusR6LegalSchedulerError, match="active profile"
        ):
            scheduler.audit_profile_roster(players, adversarial, incumbent)
        assert scheduler.audit_profile_roster(
            players, adversarial, relaxed
        ) == (field,)
        for other in profiles[1:6]:
            if other.parameter_set_id == relaxed.parameter_set_id:
                continue
            with pytest.raises(scheduler.CorpusR6LegalSchedulerError):
                scheduler.audit_profile_roster(players, adversarial, other)
        assert scheduler.audit_profile_roster(
            players, adversarial, profiles[-1]
        ) == (field,)


def test_feasible_core_preserves_sentinel_under_tiny_cap_and_adversarial_scores(
    players, scores, incumbents,
):
    profile = legal.frozen_policy_profiles()[0]
    dose = scheduler.FeasibleCoreDose(
        top_by_position=(("QB", 1), ("RB", 3), ("WR", 4), ("TE", 2), ("DST", 1)),
        cheapest_per_position=0,
        max_cores=1,
        beam_width=1,
        max_state_expansions=1,
        max_combination_candidates=1,
        max_core_candidates=1,
        max_incumbent_candidates=len(incumbents),
    )
    result = scheduler.bounded_feasible_core_lower_bounds_micro(
        scores, players, profile, incumbents, dose=dose
    )
    assert result.lower_bounds_micro == result.incumbent_sentinel_scores_micro
    assert result.rosters == result.incumbent_sentinel_rosters
    assert all(value <= 1 for value in result.state_expansions)
    for roster in result.rosters:
        assert legal.house_rule_violations(players, roster) == ()


def test_player_row_order_and_incumbent_order_do_not_change_proxies(
    players, scores, incumbents,
):
    profile = legal.frozen_policy_profiles()[0]
    forward_upper = scheduler.position_salary_upper_bounds_micro(
        scores, players, profile
    )
    reverse_upper = scheduler.position_salary_upper_bounds_micro(
        scores[::-1], players[::-1], profile
    )
    assert np.array_equal(forward_upper, reverse_upper)

    forward_lower = scheduler.bounded_feasible_core_lower_bounds_micro(
        scores, players, profile, incumbents
    )
    reverse_lower = scheduler.bounded_feasible_core_lower_bounds_micro(
        scores[::-1], players[::-1], profile, tuple(reversed(incumbents))
    )
    assert forward_lower == reverse_lower


def test_typed_receipts_bind_source_matrix_worlds_producer_and_witnesses(
    players, scores, incumbents, world_ids, source_artifact,
):
    profile = legal.frozen_policy_profiles()[0]
    dose = scheduler.DEFAULT_SALARY_POSITION_DOSE.receipt()
    scheduler.validate_dose_receipt(dose)
    assert dose == scheduler.DEFAULT_SALARY_POSITION_DOSE.receipt()
    with pytest.raises(FrozenInstanceError):
        dose.dose_sha256 = "0" * 64  # type: ignore[misc]
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="differ"):
        scheduler.validate_dose_receipt(replace(dose, dose_sha256="0" * 64))

    result = scheduler.produce_position_salary_proxy(
        player_scores_micro=scores,
        players=players,
        ordered_world_ids=world_ids,
        profile=profile,
        source_artifact=source_artifact,
        producer_identity=_producer(scheduler.POSITION_SALARY_PROXY_ID),
    )
    receipt = scheduler.build_proxy_receipt(
        result,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
        selected_count=2,
    )
    scheduler.validate_proxy_receipt(
        receipt,
        result,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
    )
    payload = json.loads(receipt.canonical_payload)
    assert payload["selected_indices"] == list(
        scheduler.stable_rank_micro(result.upper_bounds_micro, 2)
    )
    assert "uses_realized_outcomes" not in payload
    assert payload["input_binding"]["source_artifact"] == (
        source_artifact.as_payload()
    )
    assert payload["input_binding"]["ordered_world_ids"] == [
        {"block": world.block, "index": world.index} for world in world_ids
    ]
    assert receipt.player_score_matrix_sha256 == (
        result.input_binding.player_score_matrix_sha256
    )
    assert receipt.producer_identity_sha256 == sha256(
        _canonical(result.producer_identity.as_payload())
    ).hexdigest()
    with pytest.raises(FrozenInstanceError):
        receipt.receipt_sha256 = "0" * 64  # type: ignore[misc]
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="differ"):
        scheduler.validate_proxy_receipt(
            replace(receipt, receipt_sha256="0" * 64),
            result,
            players=players,
            player_scores_micro=scores,
            ordered_world_ids=world_ids,
        )

    feasible = scheduler.produce_feasible_core_proxy(
        player_scores_micro=scores,
        players=players,
        ordered_world_ids=world_ids,
        profile=profile,
        incumbent_candidates=incumbents,
        source_artifact=source_artifact,
        producer_identity=_producer(scheduler.FEASIBLE_CORE_PROXY_ID),
    )
    feasible_receipt = scheduler.build_proxy_receipt(
        feasible,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
        selected_count=2,
    )
    scheduler.validate_proxy_receipt(
        feasible_receipt,
        feasible,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
    )
    evidence = json.loads(feasible_receipt.canonical_payload)["producer_result"]
    assert set(evidence) == {
        "result_kind", "result_sha256", "batch_sha256",
        "witness_rosters_sha256", "incumbent_sentinel_sha256",
        "work_receipt_sha256",
    }
    assert feasible_receipt.dose_sha256 != receipt.dose_sha256


def test_receipt_builder_replays_before_emitting_and_rejects_forged_result(
    players, scores, world_ids, source_artifact,
):
    result = scheduler.produce_position_salary_proxy(
        player_scores_micro=scores,
        players=players,
        ordered_world_ids=world_ids,
        profile=legal.frozen_policy_profiles()[0],
        source_artifact=source_artifact,
        producer_identity=_producer(scheduler.POSITION_SALARY_PROXY_ID),
    )
    forged = replace(
        result,
        upper_bounds_micro=(999, 999, 999),
        result_sha256="not-a-sha",
    )
    with pytest.raises(
        scheduler.CorpusR6LegalSchedulerError, match="result replay differs"
    ):
        scheduler.build_proxy_receipt(
            forged,
            players=players,
            player_scores_micro=scores,
            ordered_world_ids=world_ids,
            selected_count=1,
        )


def test_fake_identity_claims_are_explicitly_non_authoritative(
    players, scores, world_ids,
):
    claimed_source = scheduler.SourceArtifactIdentity(
        uri="gs://does-not-exist/offline-claim.npz",
        generation=999,
        byte_count=1,
        sha256="e" * 64,
        scientific_contract_sha256="f" * 64,
    )
    claimed_producer = scheduler.ProducerIdentity(
        proxy_id=scheduler.POSITION_SALARY_PROXY_ID,
        code_sha256="1" * 64,
        image_digest="sha256:" + "2" * 64,
    )
    result = scheduler.produce_position_salary_proxy(
        player_scores_micro=scores,
        players=players,
        ordered_world_ids=world_ids,
        profile=legal.frozen_policy_profiles()[0],
        source_artifact=claimed_source,
        producer_identity=claimed_producer,
    )
    receipt = scheduler.build_proxy_receipt(
        result,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
        selected_count=1,
    )
    scheduler.validate_proxy_receipt(
        receipt,
        result,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
    )
    authority = json.loads(receipt.canonical_payload)["authority"]
    assert authority == {
        "scope": scheduler.OFFLINE_AUTHORITY_SCOPE,
        "authoritative": False,
        "source_artifact_claim_verified": False,
        "producer_code_image_claim_verified": False,
        "incumbent_candidate_claim_verified": False,
        "outer_exact_read_pinned_authority_required": True,
        "outer_cumulative_batch_run_budget_required": True,
    }
    assert receipt.authoritative is False
    assert receipt.outer_exact_read_pinned_authority_required is True
    assert receipt.outer_cumulative_batch_run_budget_required is True


def test_empty_structural_combination_is_charged_under_cap_and_replayed(
    players, scores, incumbents, world_ids, source_artifact,
):
    profile = legal.frozen_policy_profiles()[-1]
    dose = replace(
        scheduler.DEFAULT_FEASIBLE_CORE_DOSE,
        max_cores=4,
        beam_width=1,
        max_state_expansions=1,
        max_combination_candidates=1,
        max_core_candidates=4,
    )
    result = scheduler.produce_feasible_core_proxy(
        player_scores_micro=scores,
        players=players,
        ordered_world_ids=world_ids,
        profile=profile,
        incumbent_candidates=incumbents,
        source_artifact=source_artifact,
        producer_identity=_producer(scheduler.FEASIBLE_CORE_PROXY_ID),
        dose=dose,
    )
    assert result.batch.combination_candidates_considered == (1, 1, 1)
    assert result.batch.core_candidates_considered == (0, 0, 0)
    assert result.batch.lower_bounds_micro == (
        result.batch.incumbent_sentinel_scores_micro
    )
    receipt = scheduler.build_proxy_receipt(
        result,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
        selected_count=2,
    )
    scheduler.validate_proxy_receipt(
        receipt,
        result,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
    )


def test_repeated_batches_retain_outer_cumulative_budget_requirement(
    players, scores, source_artifact,
):
    receipts: list[scheduler.ProxyReceipt] = []
    for block in ("R0", "R1"):
        worlds = tuple(rw.WorldId(block, index) for index in range(scores.shape[1]))
        result = scheduler.produce_position_salary_proxy(
            player_scores_micro=scores,
            players=players,
            ordered_world_ids=worlds,
            profile=legal.frozen_policy_profiles()[0],
            source_artifact=source_artifact,
            producer_identity=_producer(scheduler.POSITION_SALARY_PROXY_ID),
        )
        receipts.append(
            scheduler.build_proxy_receipt(
                result,
                players=players,
                player_scores_micro=scores,
                ordered_world_ids=worlds,
                selected_count=1,
            )
        )
    assert receipts[0].world_schedule_sha256 != receipts[1].world_schedule_sha256
    for receipt in receipts:
        authority = json.loads(receipt.canonical_payload)["authority"]
        assert authority["authoritative"] is False
        assert authority["outer_cumulative_batch_run_budget_required"] is True


def test_exact_schema_validators_reject_coherently_rehashed_receipts(
    players, scores, world_ids, source_artifact,
):
    profile = legal.frozen_policy_profiles()[0]
    result = scheduler.produce_position_salary_proxy(
        player_scores_micro=scores,
        players=players,
        ordered_world_ids=world_ids,
        profile=profile,
        source_artifact=source_artifact,
        producer_identity=_producer(scheduler.POSITION_SALARY_PROXY_ID),
    )
    receipt = scheduler.build_proxy_receipt(
        result,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
        selected_count=2,
    )

    mutations = (
        lambda row: row.__setitem__("extra", 1),
        lambda row: row.pop("accepted_input_contract"),
        lambda row: row.__setitem__("selected_count", 0),
        lambda row: row.__setitem__("selected_indices", [-1, 0]),
        lambda row: row.__setitem__("selected_indices", [0, 0]),
        lambda row: row.__setitem__("selected_indices", [0, 99]),
        lambda row: row.__setitem__("proxy_id", "unsupported-proxy"),
        lambda row: row.__setitem__("profile_payload_sha256", "not-a-sha"),
        lambda row: row["input_binding"].__setitem__("extra", 1),
        lambda row: row["producer_result"].__setitem__("extra", 1),
        lambda row: row["authority"].__setitem__("authoritative", True),
        lambda row: row["authority"].__setitem__(
            "outer_cumulative_batch_run_budget_required", False
        ),
        lambda row: row["authority"].__setitem__("extra", 1),
    )
    for mutate in mutations:
        forged = _coherently_rehash_proxy(receipt, mutate)
        with pytest.raises(scheduler.CorpusR6LegalSchedulerError):
            scheduler.validate_proxy_receipt(
                forged,
                result,
                players=players,
                player_scores_micro=scores,
                ordered_world_ids=world_ids,
            )

    position_dose = scheduler.DEFAULT_SALARY_POSITION_DOSE.receipt()
    feasible_dose = scheduler.DEFAULT_FEASIBLE_CORE_DOSE.receipt()
    dose_mutations = (
        (position_dose, lambda row: row.__setitem__("extra", 1)),
        (position_dose, lambda row: row["dose"].__setitem__(
            "theta_micro_per_salary_dollar", [0, 0]
        )),
        (position_dose, lambda row: row.__setitem__(
            "proxy_id", "unsupported-proxy"
        )),
        (feasible_dose, lambda row: row["dose"].__setitem__("max_cores", 0)),
        (feasible_dose, lambda row: row["dose"].__setitem__("extra", 1)),
        (feasible_dose, lambda row: row["dose"].pop("beam_width")),
        (feasible_dose, lambda row: row["dose"].__setitem__(
            "outer_cumulative_batch_run_budget_required", False
        )),
    )
    for original, mutate in dose_mutations:
        with pytest.raises(scheduler.CorpusR6LegalSchedulerError):
            scheduler.validate_dose_receipt(
                _coherently_rehash_dose(original, mutate)
            )


def test_receipt_replay_rejects_matrix_world_witness_and_sentinel_changes(
    players, scores, incumbents, world_ids, source_artifact,
):
    profile = legal.frozen_policy_profiles()[0]
    result = scheduler.produce_feasible_core_proxy(
        player_scores_micro=scores,
        players=players,
        ordered_world_ids=world_ids,
        profile=profile,
        incumbent_candidates=incumbents,
        source_artifact=source_artifact,
        producer_identity=_producer(scheduler.FEASIBLE_CORE_PROXY_ID),
    )
    receipt = scheduler.build_proxy_receipt(
        result,
        players=players,
        player_scores_micro=scores,
        ordered_world_ids=world_ids,
        selected_count=2,
    )

    changed_scores = scores.copy()
    changed_scores[0, 0] += 1
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError):
        scheduler.validate_proxy_receipt(
            receipt,
            result,
            players=players,
            player_scores_micro=changed_scores,
            ordered_world_ids=world_ids,
        )
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError):
        scheduler.validate_proxy_receipt(
            receipt,
            result,
            players=players,
            player_scores_micro=scores,
            ordered_world_ids=tuple(reversed(world_ids)),
        )

    forged_witness = replace(
        result.batch,
        rosters=(tuple(reversed(result.batch.rosters[0])), *result.batch.rosters[1:]),
    )
    forged_result = replace(result, batch=forged_witness)
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError):
        scheduler.build_proxy_receipt(
            forged_result,
            players=players,
            player_scores_micro=scores,
            ordered_world_ids=world_ids,
            selected_count=2,
        )

    forged_sentinel = replace(
        result.batch,
        incumbent_sentinel_scores_micro=(
            result.batch.incumbent_sentinel_scores_micro[0] + 1,
            *result.batch.incumbent_sentinel_scores_micro[1:],
        ),
    )
    forged_result = replace(result, batch=forged_sentinel)
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError):
        scheduler.build_proxy_receipt(
            forged_result,
            players=players,
            player_scores_micro=scores,
            ordered_world_ids=world_ids,
            selected_count=2,
        )


def test_input_and_witness_contracts_fail_closed(players, scores, incumbents):
    profile = legal.frozen_policy_profiles()[0]
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="integer matrix"):
        scheduler.position_salary_upper_bounds_micro(
            scores.astype(np.float64), players, profile
        )
    duplicate_players = (*players, players[-1])
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="repeat"):
        scheduler.position_salary_upper_bounds_micro(
            np.vstack((scores, scores[-1])), duplicate_players, profile
        )
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="repeats"):
        scheduler.bounded_feasible_core_lower_bounds_micro(
            scores, players, profile, (*incumbents, incumbents[0])
        )
    malformed = tuple(sorted((*incumbents[0][1:], "not-a-player")))
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="not DK legal"):
        scheduler.bounded_feasible_core_lower_bounds_micro(
            scores, players, profile, (malformed,)
        )


def test_hard_dose_and_precap_work_limits_fail_closed(players, scores, incumbents):
    profile = legal.frozen_policy_profiles()[0]
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="hard maximum"):
        scheduler.SalaryPositionDose(tuple(range(-32, 33)))
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="hard maximum"):
        replace(
            scheduler.DEFAULT_FEASIBLE_CORE_DOSE,
            max_combination_candidates=scheduler.MAX_COMBINATION_CANDIDATES + 1,
        )
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="hard maximum"):
        scheduler.FeasibleCoreDose(
            top_by_position=(
                ("QB", scheduler.MAX_TOP_PLAYERS_PER_POSITION + 1),
                ("RB", 3), ("WR", 4), ("TE", 2), ("DST", 1),
            ),
            cheapest_per_position=0,
            max_cores=1,
            beam_width=1,
            max_state_expansions=1,
            max_combination_candidates=1,
            max_core_candidates=1,
            max_incumbent_candidates=1,
        )
    one_incumbent = replace(
        scheduler.DEFAULT_FEASIBLE_CORE_DOSE,
        max_incumbent_candidates=1,
    )
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="candidate count"):
        scheduler.bounded_feasible_core_lower_bounds_micro(
            scores, players, profile, incumbents, dose=one_incumbent
        )
    with pytest.raises(TypeError):
        scheduler.build_proxy_receipt(  # type: ignore[call-arg]
            proxy_id=scheduler.POSITION_SALARY_PROXY_ID,
            scores_micro=np.array([1, 2], dtype=np.int64),
            selected_count=1,
        )

    too_many_worlds = np.tile(
        scores[:, :1], (1, scheduler.MAX_WORLDS_PER_BATCH + 1)
    )
    with pytest.raises(scheduler.CorpusR6LegalSchedulerError, match="hard batch"):
        scheduler.position_salary_upper_bounds_micro(
            too_many_worlds, players, profile
        )
