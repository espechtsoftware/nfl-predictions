from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
from itertools import combinations, product
from pathlib import Path

import numpy as np
import pulp
import pytest

from nfl_dfs.research import lr8_exact_solvers as exact
from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_training_source as source
from nfl_dfs.research import residual_world_columns as rw


def _players() -> tuple[rw.PlayerSpec, ...]:
    rows = (
        ("q-a", "QB", "A", "B", "g1"),
        ("q-c", "QB", "C", "D", "g2"),
        ("rb-a1", "RB", "A", "B", "g1"),
        ("rb-a2", "RB", "A", "B", "g1"),
        ("rb-b", "RB", "B", "A", "g1"),
        ("rb-c", "RB", "C", "D", "g2"),
        ("rb-d", "RB", "D", "C", "g2"),
        ("rb-e", "RB", "E", "F", "g3"),
        ("wr-a1", "WR", "A", "B", "g1"),
        ("wr-a2", "WR", "A", "B", "g1"),
        ("wr-b", "WR", "B", "A", "g1"),
        ("wr-c1", "WR", "C", "D", "g2"),
        ("wr-c2", "WR", "C", "D", "g2"),
        ("wr-d", "WR", "D", "C", "g2"),
        ("wr-e", "WR", "E", "F", "g3"),
        ("wr-f", "WR", "F", "E", "g3"),
        ("te-a", "TE", "A", "B", "g1"),
        ("te-b", "TE", "B", "A", "g1"),
        ("te-c", "TE", "C", "D", "g2"),
        ("te-d", "TE", "D", "C", "g2"),
        ("te-e", "TE", "E", "F", "g3"),
        ("dst-b", "DST", "B", "A", "g1"),
        ("dst-c", "DST", "C", "D", "g2"),
        ("dst-e", "DST", "E", "F", "g3"),
    )
    return tuple(sorted((
        rw.PlayerSpec(player_id, position, team, opponent, game, 5_000)
        for player_id, position, team, opponent, game in rows
    ), key=lambda player: player.player_id))


def _house_rule_violator() -> tuple[str, ...]:
    # Legal $45k DK Classic: naked q-a, no B skill bring-back, two A RBs,
    # and both A RBs oppose dst-b.  Every named former house rule is relaxed.
    return tuple(sorted((
        "q-a", "rb-a1", "rb-a2", "wr-c1", "wr-c2", "wr-d", "wr-e",
        "te-c", "dst-b",
    )))


def _legal_rosters(players: tuple[rw.PlayerSpec, ...], count: int = 50):
    positions = {
        position: [
            player.player_id for player in players if player.position == position
        ]
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    result: list[tuple[str, ...]] = []
    for qb, rbs, wrs, te, dst in product(
        positions["QB"],
        combinations(positions["RB"], 2),
        combinations(positions["WR"], 4),
        positions["TE"],
        positions["DST"],
    ):
        roster = tuple(sorted((qb, *rbs, *wrs, te, dst)))
        try:
            lr8.audit_dk_classic_identity(players, roster)
        except lr8.LR8Error:
            continue
        if roster not in result:
            result.append(roster)
        if len(result) == count:
            break
    target = _house_rule_violator()
    assert lr8.audit_dk_classic_identity(players, target) == target
    if target not in result:
        result.append(target)
    return tuple(result)


def _artifact(
    players: tuple[rw.PlayerSpec, ...],
    rosters: tuple[tuple[str, ...], ...],
) -> dict[str, object]:
    rows = []
    for index, (season, week) in enumerate(lr8.TRAINING_CELLS):
        rows.append(lr8.AnatomyTrainingRow(
            season=season,
            week=week,
            features=lr8.lineup_anatomy(players, rosters[index]),
            realized_total_micro=(205 if index % 2 else 190)
            * rw.MICRO_DK_SCALE,
        ))
    return lr8.fit_soft_anatomy_law(rows)


class _Publisher:
    def __init__(self) -> None:
        self.calls: list[exact.ExactSolveProofBundle] = []

    def __call__(self, proof: exact.ExactSolveProofBundle):
        self.calls.append(proof)
        return ({
            "uri": f"gs://lr8-mocked-proof/{proof.proof_sha256}.json",
            "generation": "1",
            "sha256": proof.proof_sha256,
            "bytes": len(proof.proof_bytes),
        },)


def _rebind_proof(
    proof: exact.ExactSolveProofBundle,
    *,
    solve_evidence: tuple[rw.CbcSolveEvidence, ...] | None = None,
    result_payload: dict[str, object] | None = None,
) -> exact.ExactSolveProofBundle:
    evidence = proof.solve_evidence if solve_evidence is None else solve_evidence
    result = (
        dict(proof.result_payload)
        if result_payload is None
        else dict(result_payload)
    )
    payload = {
        "schema": proof.schema,
        "solve_kind": proof.solve_kind,
        "request_sha256": proof.request_sha256,
        "result": result,
        "cbc_solve_evidence": [
            rw._cbc_scientific_receipt(receipt)  # noqa: SLF001
            for receipt in evidence
        ],
    }
    proof_bytes = lr8.canonical_json(payload)
    return replace(
        proof,
        result_payload=result,
        proof_bytes=proof_bytes,
        proof_sha256=sha256(proof_bytes).hexdigest(),
        solve_evidence=evidence,
    )


def _cold_training_reference(
    request: source.WorldSolveRequest,
    evidence_root: Path,
) -> tuple[tuple[str, ...], int, dict[str, object]]:
    """Reproduce the frozen v2 objective with cold post-quotient solves."""
    players, scores, incumbents = exact._validate_training_request(  # noqa: SLF001
        request
    )
    micro = rw.to_micro_dk(scores[:, None])[:, 0]
    model = lr8.build_dk_classic_model(
        players,
        name="lr8_training_world_cold_parity",
        forbidden_rosters=incumbents,
    )
    quotient, remainder, offset = rw._bound_score_objective(  # noqa: SLF001
        model, micro, name="lr8_training_score"
    )
    factory = exact._solver_factory(evidence_root)  # noqa: SLF001
    evidence: list[rw.CbcSolveEvidence] = []
    quotient_optimum, receipt = exact._solve_and_freeze(  # noqa: SLF001
        model.problem,
        quotient,
        sense=pulp.LpMaximize,
        name="training_score_quotient",
        label="lr8 training score quotient",
        solver_factory=factory,
        warm_start=False,
    )
    evidence.append(receipt)
    remainder_optimum, receipt = exact._solve_and_freeze(  # noqa: SLF001
        model.problem,
        remainder,
        sense=pulp.LpMaximize,
        name="training_score_remainder",
        label="lr8 training score remainder",
        solver_factory=factory,
        warm_start=False,
        cuts_off=True,
        preprocess_off=True,
    )
    evidence.append(receipt)
    roster, canonical = exact._canonicalize(  # noqa: SLF001
        model,
        solver_factory=factory,
        solve_evidence=evidence,
        label_prefix="lr8_training",
        warm_chain=False,
    )
    objective = (
        quotient_optimum * rw.BOUND_OBJECTIVE_BASE
        + remainder_optimum
        + offset
    )
    return roster, objective, canonical


@pytest.fixture(scope="module")
def contract():
    players = _players()
    rosters = _legal_rosters(players)
    target = _house_rule_violator()
    incumbent = next(roster for roster in rosters if roster != target)
    artifact = _artifact(players, rosters)
    return players, rosters, target, incumbent, artifact


@pytest.fixture(scope="module")
def training_solve(contract, tmp_path_factory):
    players, _, target, incumbent, _ = contract
    scores = np.asarray([
        25.0 if player.player_id in target else 1.0 for player in players
    ], dtype=np.float32)
    draws = scores[:, None]
    request = source._solve_request(  # noqa: SLF001 - exact source seam
        season=2019,
        week=1,
        block="R0",
        players=players,
        player_draws=draws,
        world_index=0,
        incumbents=(incumbent,),
        catalog_digest=source.catalog_sha256(players),
        incumbent_digest=source.identities_sha256((incumbent,)),
    )
    root = tmp_path_factory.mktemp("lr8-training-solve").resolve()
    publisher = _Publisher()
    solver = exact.make_training_world_solver(
        evidence_root=root, publish_evidence=publisher
    )
    response = solver(request)
    return request, response, publisher.calls[0]


def _pricing_request(contract, *, null: bool = False) -> lr8.PricingRequest:
    players, _, target, incumbent, artifact = contract
    scores = np.stack([
        np.full(
            2,
            (25 if player.player_id in target else 1) * rw.MICRO_DK_SCALE,
            dtype=np.int64,
        )
        for player in players
    ])
    scores.flags.writeable = False
    maxima = np.full(
        2,
        lr8.BOOK_MAX_CAP_MICRO if null else 180 * rw.MICRO_DK_SCALE,
        dtype=np.int64,
    )
    maxima.flags.writeable = False
    return lr8.PricingRequest(
        fold_name="A",
        iteration=1,
        construction_blocks=("R0", "R2", "R4"),
        players=players,
        world_ids=(rw.WorldId("R0", 0), rw.WorldId("R2", 0)),
        player_scores_micro=scores,
        book_maxima_micro=maxima,
        control_rosters=(incumbent,),
        previous_columns=(),
        forbidden_rosters=(incumbent,),
        marginal_thresholds_micro=lr8.MARGINAL_THRESHOLDS_MICRO,
        book_max_cap_micro=lr8.BOOK_MAX_CAP_MICRO,
        portfolio_improvement_required=True,
        anatomy_linear_scale=lr8.ANATOMY_LINEAR_SCALE,
        anatomy_artifact=artifact,
    )


@pytest.fixture(scope="module")
def pricing_solve(contract, tmp_path_factory):
    request = _pricing_request(contract)
    publisher = _Publisher()
    step = exact.make_pricing_step(
        evidence_root=tmp_path_factory.mktemp("lr8-pricing-solve").resolve(),
        publish_evidence=publisher,
    )
    response = step(request)
    assert step.last_proof is publisher.calls[0]
    return request, response, step.last_proof


@pytest.fixture(scope="module")
def null_solve(contract, tmp_path_factory):
    request = _pricing_request(contract, null=True)
    publisher = _Publisher()
    step = exact.make_pricing_step(
        evidence_root=tmp_path_factory.mktemp("lr8-null-solve").resolve(),
        publish_evidence=publisher,
    )
    response = step(request)
    return request, response, step.last_proof


def test_fixed_canonical_law_is_rank_sum_then_incidence_not_global_lex():
    assert exact.CANONICAL_ROSTER_LAW == (
        "minimum-rank-sum-then-utf8-incidence-v1"
    )
    # For rank(a..e)=1..5, global lex prefers (a,e), while the retained first
    # tier prefers the lower rank-sum (b,c).  The protocol names that truth.
    global_lex_first = min(("a", "e"), ("b", "c"))
    rank = {value: index + 1 for index, value in enumerate("abcde")}
    rank_first = min(
        (("a", "e"), ("b", "c")),
        key=lambda roster: (sum(rank[value] for value in roster), roster),
    )
    assert global_lex_first == ("a", "e")
    assert rank_first == ("b", "c")


def test_training_warm_chain_is_complete_ordered_and_cold_objective_parity(
    training_solve, tmp_path,
):
    request, response, proof = training_solve
    assert exact.PROOF_SCHEMA == "lr8-exact-cbc-proof-v2"
    assert exact.EXACT_SOLVE_SECONDS == 300
    assert proof.result_payload["solve_chain_law"] == (
        exact.TRAINING_WARM_CHAIN_LAW
    )
    semantics = exact._training_stage_semantics(  # noqa: SLF001
        proof.result_payload, proof.solve_evidence
    )
    assert tuple(
        (receipt.solve_label, receipt.objective)
        for receipt in proof.solve_evidence
    ) == semantics
    assert [receipt.warm_start for receipt in proof.solve_evidence] == [
        False,
        *([True] * (len(proof.solve_evidence) - 1)),
    ]
    assert all(not receipt.preprocess_off for receipt in proof.solve_evidence)
    assert all(receipt.cuts is False for receipt in proof.solve_evidence)
    assert all(
        receipt.max_seconds == exact.EXACT_SOLVE_SECONDS
        for receipt in proof.solve_evidence
    )
    for prior, current in zip(
        proof.solve_evidence, proof.solve_evidence[1:], strict=False
    ):
        rw._validate_ordered_warm_predecessor(prior, current)  # noqa: SLF001

    cold_root = (tmp_path / "cold-objective-parity").resolve()
    cold_root.mkdir()
    cold_roster, cold_objective, cold_canonical = _cold_training_reference(
        request, cold_root
    )
    assert cold_roster == response.roster
    assert cold_objective == response.objective_micro
    assert cold_canonical == proof.result_payload["canonical"]


def _tie_training_proof(tmp_path):
    """Solve a catalog rigged so the minimum-rank face holds two rosters.

    Seven dominant players force all slots except WR3 and FLEX. Four
    equal-score candidates remain: rb-t1/rb-t2 (FLEX only) and
    wr-t1/wr-t2. The cheapest-rank pair (wr-t1, rb-t1) is excluded by the
    salary cap, leaving (wr-t1, rb-t2) and (wr-t2, rb-t1) tied at the
    minimum rank sum — so the canonical ambiguity distance is positive and
    at least one UTF-8 incidence chunk stage must run and be retained.
    """
    rows = (
        ("q-a", "QB", "A", "B", "g1", 6_000),
        ("rb-a1", "RB", "A", "B", "g1", 6_000),
        ("rb-b", "RB", "B", "A", "g1", 6_000),
        ("wr-a1", "WR", "A", "B", "g1", 6_000),
        ("wr-b", "WR", "B", "A", "g1", 6_000),
        ("te-a", "TE", "A", "B", "g1", 6_000),
        ("dst-b", "DST", "B", "A", "g1", 6_000),
        ("rb-t1", "RB", "C", "D", "g2", 4_500),
        ("rb-t2", "RB", "C", "D", "g2", 3_500),
        ("wr-t1", "WR", "C", "D", "g2", 4_500),
        ("wr-t2", "WR", "D", "C", "g2", 3_500),
    )
    players = tuple(sorted((
        rw.PlayerSpec(player_id, position, team, opponent, game, salary)
        for player_id, position, team, opponent, game, salary in rows
    ), key=lambda player: player.player_id))
    dominant = {
        "q-a", "rb-a1", "rb-b", "wr-a1", "wr-b", "te-a", "dst-b",
    }
    scores = np.asarray([
        50.0 if player.player_id in dominant else 20.0
        for player in players
    ], dtype=np.float32)
    # One legal no-good is required; excluding the rank-17 loser
    # (wr-t2, rb-t2) leaves the two tied minimum-rank rosters untouched.
    incumbent = tuple(sorted((*dominant, "wr-t2", "rb-t2")))
    request = source._solve_request(  # noqa: SLF001 - exact source seam
        season=2019,
        week=1,
        block="R0",
        players=players,
        player_draws=scores[:, None],
        world_index=0,
        incumbents=(incumbent,),
        catalog_digest=source.catalog_sha256(players),
        incumbent_digest=source.identities_sha256((incumbent,)),
    )
    publisher = _Publisher()
    solver = exact.make_training_world_solver(
        evidence_root=tmp_path.resolve(), publish_evidence=publisher
    )
    response = solver(request)
    assert response.roster in (
        tuple(sorted((*dominant, "wr-t1", "rb-t2"))),
        tuple(sorted((*dominant, "wr-t2", "rb-t1"))),
    )
    return publisher.calls[0]


def test_training_warm_chain_rejects_missing_reordered_and_wrong_predecessor(
    training_solve, tmp_path,
):
    _, _, proof = training_solve
    evidence = proof.solve_evidence
    # Unambiguous fixture: quotient, remainder, rank, ambiguity — and no
    # incidence chunk, because the canonical optimum is unique.
    assert len(evidence) == 4

    missing = _rebind_proof(
        proof, solve_evidence=(evidence[0], *evidence[2:])
    )
    with pytest.raises(exact.LR8ExactSolverError, match="stage count"):
        exact.validate_proof_bundle(missing)

    reordered = _rebind_proof(
        proof,
        solve_evidence=(
            evidence[0], evidence[2], evidence[1], *evidence[3:]
        ),
    )
    with pytest.raises(exact.LR8ExactSolverError, match="semantic law"):
        exact.validate_proof_bundle(reordered)

    wrong_predecessor_receipt = replace(
        evidence[1], predecessor_assignment_sha256="0" * 64
    )
    rw.validate_cbc_solve_evidence(wrong_predecessor_receipt)
    wrong_predecessor = _rebind_proof(
        proof,
        solve_evidence=(
            evidence[0], wrong_predecessor_receipt, *evidence[2:]
        ),
    )
    with pytest.raises(
        exact.LR8ExactSolverError, match="immediate ordered predecessor"
    ):
        exact.validate_proof_bundle(wrong_predecessor)

    tie_proof = _tie_training_proof(tmp_path)
    tie_evidence = tie_proof.solve_evidence
    assert len(tie_evidence) >= 5
    canonical = dict(tie_proof.result_payload["canonical"])
    assert len(canonical["incidence_chunk_optima"]) >= 1
    canonical["incidence_chunk_optima"] = canonical[
        "incidence_chunk_optima"
    ][:-1]
    truncated_payload = dict(tie_proof.result_payload)
    truncated_payload["canonical"] = canonical
    truncated = _rebind_proof(
        tie_proof,
        solve_evidence=tie_evidence[:-1],
        result_payload=truncated_payload,
    )
    with pytest.raises(
        exact.LR8ExactSolverError, match="incidence stage population"
    ):
        exact.validate_proof_bundle(truncated)


def test_training_adapter_is_exact_dk_only_and_independently_replays(
    contract, training_solve, tmp_path,
):
    players, _, target, _, _ = contract
    request, response, proof = training_solve
    assert response.roster == target
    assert lr8.audit_dk_classic_identity(players, response.roster) == target
    with pytest.raises(rw.ResidualWorldError):
        rw.audit_legal_identity(players, response.roster)
    assert response.objective_micro == 225 * rw.MICRO_DK_SCALE
    assert response.house_rules_applied == ()
    assert proof.result_payload["canonical"]["law"] == exact.CANONICAL_ROSTER_LAW
    assert proof.result_payload["house_rules_applied"] == []
    assert len(proof.solve_evidence) >= 4
    assert all(
        evidence.pulp_status == pulp.LpStatusOptimal
        for evidence in proof.solve_evidence
    )
    exact.validate_proof_bundle(proof)
    replay_root = (tmp_path / "training-replay").resolve()
    replay_root.mkdir()
    exact.validate_training_world_solution(
        request, response, proof, replay_evidence_root=replay_root
    )


def test_pricing_hierarchy_has_python_cbc_parity_and_replays(
    contract, pricing_solve, tmp_path,
):
    players, _, target, _, artifact = contract
    request, response, proof = pricing_solve
    assert response == target
    totals = np.full(2, 225 * rw.MICRO_DK_SCALE, dtype=np.int64)
    counts, _, gain, _ = lr8.clipped_marginal_utility(
        totals, request.book_maxima_micro
    )
    tier = lr8.operative_anatomy_linear_units(
        artifact, lr8.lineup_anatomy(players, target)
    )
    assert counts == (2, 2, 2, 2)
    assert gain == 60 * rw.MICRO_DK_SCALE
    assert proof.result_payload["threshold_counts"] == list(counts)
    assert proof.result_payload["anatomy_linear_predictor_units"] == tier
    assert proof.result_payload["clipped_gain_micro"] == gain
    stage_names = [stage["name"] for stage in proof.result_payload["stages"]]
    assert stage_names[:5] == [
        "positive_residual_exists", "g210", "g200", "g194", "g187",
    ]
    first_anatomy = next(
        index for index, name in enumerate(stage_names)
        if name.startswith("anatomy_linear_chunk_")
    )
    first_gain = next(
        index for index, name in enumerate(stage_names)
        if name.startswith("clipped_gain_chunk_")
    )
    assert first_anatomy < first_gain
    assert proof.result_payload["canonical"]["law"] == exact.CANONICAL_ROSTER_LAW
    replay_root = (tmp_path / "pricing-replay").resolve()
    replay_root.mkdir()
    exact.validate_pricing_solution(
        request, response, proof, replay_evidence_root=replay_root
    )


def test_null_is_one_exact_positive_domain_proof_and_anatomy_cannot_admit(
    null_solve, tmp_path,
):
    request, response, proof = null_solve
    assert response is None
    assert proof.result_payload["null"] is True
    assert proof.result_payload["positive_residual_optimum"] == 0
    assert proof.result_payload["stages"] == [{
        "name": "positive_residual_exists", "optimum": 0,
    }]
    assert len(proof.solve_evidence) == 1
    assert proof.solve_evidence[0].pulp_status == pulp.LpStatusOptimal
    replay_root = (tmp_path / "null-replay").resolve()
    replay_root.mkdir()
    exact.validate_pricing_solution(
        request, None, proof, replay_evidence_root=replay_root
    )


def test_response_poisons_reject_suboptimal_noncanonical_and_house_rule_claims(
    contract, training_solve, tmp_path,
):
    _, rosters, target, _, _ = contract
    request, response, proof = training_solve
    alternate = next(roster for roster in rosters if roster != target)
    replay_root = (tmp_path / "unused-replay").resolve()
    replay_root.mkdir()
    suboptimal = replace(response, roster=alternate, objective_micro=0)
    with pytest.raises(exact.LR8ExactSolverError, match="differs from proof"):
        exact.validate_training_world_solution(
            request, suboptimal, proof, replay_evidence_root=replay_root
        )
    noncanonical = replace(response, roster=alternate)
    with pytest.raises(exact.LR8ExactSolverError, match="differs from proof"):
        exact.validate_training_world_solution(
            request, noncanonical, proof, replay_evidence_root=replay_root
        )
    house_rule = replace(response, house_rules_applied=("salary_floor",))
    with pytest.raises(exact.LR8ExactSolverError, match="former house rule"):
        exact.validate_training_world_solution(
            request, house_rule, proof, replay_evidence_root=replay_root
        )


def test_stale_request_and_evidence_or_proof_drift_fail_before_replay(
    pricing_solve, tmp_path,
):
    request, response, proof = pricing_solve
    replay_root = (tmp_path / "unused-pricing-replay").resolve()
    replay_root.mkdir()
    stale = replace(request, iteration=2)
    with pytest.raises(exact.LR8ExactSolverError, match="stale"):
        exact.validate_pricing_solution(
            stale, response, proof, replay_evidence_root=replay_root
        )
    drifted_evidence = replace(
        proof.solve_evidence[0], model_sha256="0" * 64
    )
    drifted_proof = replace(
        proof,
        solve_evidence=(drifted_evidence, *proof.solve_evidence[1:]),
    )
    with pytest.raises((exact.LR8ExactSolverError, rw.SolverFailure)):
        exact.validate_proof_bundle(drifted_proof)
    with pytest.raises(exact.LR8ExactSolverError, match="bytes or hash drifted"):
        exact.validate_proof_bundle(replace(
            proof, proof_bytes=proof.proof_bytes + b"\n"
        ))


def test_publisher_must_return_receipts_even_for_exact_null(contract, tmp_path):
    request = _pricing_request(contract, null=True)
    root = (tmp_path / "publisher-null").resolve()
    root.mkdir()
    step = exact.make_pricing_step(
        evidence_root=root,
        publish_evidence=lambda _proof: (),
    )
    with pytest.raises(exact.LR8ExactSolverError, match="nonempty receipt"):
        step(request)
