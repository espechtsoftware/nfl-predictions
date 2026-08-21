"""Exact retained-CBC callbacks for the default-off LR8 research arm.

This module is deliberately transport-free.  It builds only DraftKings NFL
Classic legality, retains every exact CBC solve, and hands one canonical proof
bundle to a caller-owned create-once publisher.  It neither fabricates object
storage receipts nor applies any of the former construction house rules.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from pathlib import Path
import math
from typing import Final

import numpy as np
import pulp

from nfl_dfs.research import lr8_historical_arm as lr8
from nfl_dfs.research import lr8_training_source as source
from nfl_dfs.research import residual_world_columns as rw


PROOF_SCHEMA: Final = "lr8-exact-cbc-proof-v1"
TRAINING_SOLVE_KIND: Final = "lr8-training-world-optimum"
PRICING_SOLVE_KIND: Final = "lr8-positive-residual-pricing"
EXACT_SOLVE_SECONDS: Final = 300
CANONICAL_CHUNK_BITS: Final = rw.RESIDUAL_OBJECTIVE_CHUNK_BITS
CANONICAL_ROSTER_LAW: Final = "minimum-rank-sum-then-utf8-incidence-v1"
GAIN_OBJECTIVE_CHUNK_BITS: Final = 20


class LR8ExactSolverError(ValueError):
    """A fail-closed LR8 exact-solver or proof violation."""


@dataclass(frozen=True, slots=True)
class ExactSolveProofBundle:
    """Canonical proof bytes plus the retained local CBC evidence they bind."""

    schema: str
    solve_kind: str
    request_sha256: str
    result_payload: Mapping[str, object]
    proof_bytes: bytes = field(compare=False, repr=False)
    proof_sha256: str
    solve_evidence: tuple[rw.CbcSolveEvidence, ...] = field(
        compare=False, repr=False
    )


EvidencePublisher = Callable[
    [ExactSolveProofBundle], Sequence[Mapping[str, object]]
]


@dataclass(frozen=True, slots=True)
class _ExactResult:
    roster: tuple[str, ...] | None
    result_payload: Mapping[str, object]
    proof: ExactSolveProofBundle


@dataclass(frozen=True, slots=True)
class _AnatomyGraph:
    feature_expressions: tuple[pulp.LpAffineExpression | pulp.LpVariable, ...]
    tier_number: rw._BinaryNumber  # noqa: SLF001
    tier_offset: int


def _literal_bool(value: object, *, label: str, expected: bool) -> None:
    if type(value) is not bool or value is not expected:
        raise LR8ExactSolverError(f"{label} must be literal {expected}")


def _exact_int(value: object, *, label: str, minimum: int | None = None) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise LR8ExactSolverError(f"{label} must be an exact integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise LR8ExactSolverError(f"{label} must be >= {minimum}")
    return result


def _canonical_rosters(
    values: Sequence[Sequence[object]], *, label: str, allow_empty: bool = False,
) -> tuple[tuple[str, ...], ...]:
    if isinstance(values, (str, bytes)):
        raise LR8ExactSolverError(f"{label} must be a roster sequence")
    try:
        result = tuple(rw.canonical_identity(value) for value in values)
    except (TypeError, rw.ResidualWorldError) as exc:
        raise LR8ExactSolverError(f"{label} is malformed") from exc
    if (not allow_empty and not result) or len(set(result)) != len(result):
        raise LR8ExactSolverError(f"{label} is empty or repeats identities")
    return result


def _catalog_payload(players: Sequence[rw.PlayerSpec]) -> list[dict[str, object]]:
    return [{
        "id": player.player_id,
        "pos": player.position,
        "team": player.team,
        "opp": player.opponent,
        "game_id": player.game_id,
        "salary": player.salary,
    } for player in players]


def _array_sha256(value: np.ndarray) -> str:
    array = np.ascontiguousarray(value)
    digest = sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(lr8.canonical_json(list(array.shape)))
    digest.update(b"\0")
    if array.size:
        digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def _identity_sha256(values: Sequence[Sequence[object]]) -> str:
    identities = _canonical_rosters(values, label="roster identities")
    return lr8.canonical_sha256([list(value) for value in identities])


def _validate_evidence_root(value: Path) -> Path:
    if not isinstance(value, Path):
        raise LR8ExactSolverError("evidence_root must be a pathlib.Path")
    if not value.is_absolute() or not value.exists() or not value.is_dir() or (
        value.is_symlink()
    ):
        raise LR8ExactSolverError(
            "evidence_root must be an existing absolute real directory"
        )
    return value.resolve(strict=True)


def _solver_factory(root: Path) -> rw.SolverFactory:
    def factory(max_seconds: int, warm_start: bool):
        return rw.make_cbc_solver(
            max_seconds, warm_start, evidence_root=root
        )

    return factory


def _solve_and_freeze(
    problem: pulp.LpProblem,
    expression: pulp.LpAffineExpression | pulp.LpVariable,
    *,
    sense: int,
    name: str,
    label: str,
    solver_factory: rw.SolverFactory,
    warm_start: bool,
    cuts_off: bool = False,
    preprocess_off: bool = False,
) -> tuple[int, rw.CbcSolveEvidence]:
    problem.sense = sense
    problem.setObjective(expression)
    solver = solver_factory(EXACT_SOLVE_SECONDS, warm_start)
    if warm_start or cuts_off:
        if solver.cuts_exact is None:  # noqa: SLF001 - retained exact seam
            solver.optionsDict["cuts"] = False
            solver.cuts_exact = False  # noqa: SLF001
        if solver.cuts_exact is not False:  # noqa: SLF001
            raise LR8ExactSolverError("exact solve did not disable cuts")
    if warm_start or preprocess_off:
        solver.disable_preprocess()
    evidence = rw._solve(problem, solver, label)  # noqa: SLF001
    rw.validate_cbc_solve_evidence(evidence)
    optimum = rw._integer_value(expression)  # noqa: SLF001
    if evidence.objective != optimum:
        raise LR8ExactSolverError(f"{label} evidence objective differs")
    problem += expression == optimum, f"freeze_{name}"
    return optimum, evidence


def _solve_without_freeze(
    problem: pulp.LpProblem,
    expression: pulp.LpAffineExpression | pulp.LpVariable,
    *,
    sense: int,
    label: str,
    solver_factory: rw.SolverFactory,
    warm_start: bool,
    cuts_off: bool = False,
    preprocess_off: bool = False,
) -> tuple[int, rw.CbcSolveEvidence]:
    problem.sense = sense
    problem.setObjective(expression)
    solver = solver_factory(EXACT_SOLVE_SECONDS, warm_start)
    if warm_start or cuts_off:
        if solver.cuts_exact is None:  # noqa: SLF001
            solver.optionsDict["cuts"] = False
            solver.cuts_exact = False  # noqa: SLF001
        if solver.cuts_exact is not False:  # noqa: SLF001
            raise LR8ExactSolverError("exact solve did not disable cuts")
    if warm_start or preprocess_off:
        solver.disable_preprocess()
    evidence = rw._solve(problem, solver, label)  # noqa: SLF001
    rw.validate_cbc_solve_evidence(evidence)
    optimum = rw._integer_value(expression)  # noqa: SLF001
    if evidence.objective != optimum:
        raise LR8ExactSolverError(f"{label} evidence objective differs")
    return optimum, evidence


def _solved_roster(model: rw.LegalLineupModel) -> tuple[str, ...]:
    selected: list[str] = []
    for player_id, variable in model.decision.items():
        raw = variable.value()
        if raw is None or not math.isfinite(float(raw)) or abs(
            float(raw) - round(float(raw))
        ) > 1e-9:
            raise LR8ExactSolverError("CBC roster decision is not exact binary")
        bit = int(round(float(raw)))
        if bit not in {0, 1}:
            raise LR8ExactSolverError("CBC roster decision is not binary")
        if bit:
            selected.append(player_id)
    try:
        return lr8.audit_dk_classic_identity(model.players, selected)
    except lr8.LR8Error as exc:
        raise LR8ExactSolverError("CBC roster is not DK Classic legal") from exc


def _canonicalize(
    model: rw.LegalLineupModel,
    *,
    solver_factory: rw.SolverFactory,
    solve_evidence: list[rw.CbcSolveEvidence],
    label_prefix: str,
) -> tuple[tuple[str, ...], dict[str, object]]:
    """Prove the retained minimum-rank then UTF-8-incidence tie law.

    Incidence minimization is intentionally restricted to the minimum rank-sum
    face.  This is the preexisting residual-column canonical law; it is not a
    claim that rank minimization always equals the globally lexicographically
    smallest roster.
    """
    rank = {
        player_id: index + 1
        for index, player_id in enumerate(sorted(model.decision))
    }
    rank_expression = pulp.lpSum(
        rank[player_id] * model.decision[player_id]
        for player_id in sorted(model.decision)
    )
    rank_optimum, rank_evidence = _solve_and_freeze(
        model.problem,
        rank_expression,
        sense=pulp.LpMinimize,
        name=f"{label_prefix}_canonical_rank",
        label=f"{label_prefix} canonical rank sum",
        solver_factory=solver_factory,
        warm_start=False,
        cuts_off=True,
        preprocess_off=True,
    )
    solve_evidence.append(rank_evidence)
    first = _solved_roster(model)

    probe = rw._clone_residual_problem(  # noqa: SLF001
        model.problem, copy_proven_assignment=True
    )
    overlap = pulp.lpSum(model.decision[player_id] for player_id in first)
    minimum_overlap, ambiguity_evidence = _solve_without_freeze(
        probe,
        overlap,
        sense=pulp.LpMinimize,
        label=f"{label_prefix} canonical ambiguity distance",
        solver_factory=solver_factory,
        warm_start=False,
        cuts_off=True,
        preprocess_off=True,
    )
    solve_evidence.append(ambiguity_evidence)
    ambiguity_distance = rw.ROSTER_SIZE - minimum_overlap
    if not 0 <= ambiguity_distance <= rw.ROSTER_SIZE:
        raise LR8ExactSolverError("canonical ambiguity distance is malformed")

    incidence_optima: list[int] = []
    if ambiguity_distance:
        rw._copy_proven_assignment(probe, model.problem)  # noqa: SLF001
        fixed_ones = 0
        player_ids = sorted(model.decision)
        index = 0
        while index < len(player_ids):
            remaining = len(player_ids) - index
            needed = rw.ROSTER_SIZE - fixed_ones
            if needed == 0:
                for player_id in player_ids[index:]:
                    model.problem += model.decision[player_id] == 0, (
                        f"{label_prefix}_canonical_incidence_{index:04d}"
                    )
                    index += 1
                break
            if needed == remaining:
                for player_id in player_ids[index:]:
                    model.problem += model.decision[player_id] == 1, (
                        f"{label_prefix}_canonical_incidence_{index:04d}"
                    )
                    fixed_ones += 1
                    index += 1
                break
            chunk = player_ids[index:index + CANONICAL_CHUNK_BITS]
            expression = pulp.lpSum(
                model.decision[player_id] * (1 << (len(chunk) - offset - 1))
                for offset, player_id in enumerate(chunk)
            )
            optimum, evidence = _solve_without_freeze(
                model.problem,
                expression,
                sense=pulp.LpMaximize,
                label=f"{label_prefix} canonical incidence chunk {index:04d}",
                solver_factory=solver_factory,
                warm_start=False,
                cuts_off=True,
                preprocess_off=True,
            )
            solve_evidence.append(evidence)
            reconstructed = 0
            for offset, player_id in enumerate(chunk):
                bit = rw._integer_value(  # noqa: SLF001
                    model.decision[player_id]
                )
                if bit not in {0, 1}:
                    raise LR8ExactSolverError(
                        "canonical incidence decision is not binary"
                    )
                reconstructed += bit * (1 << (len(chunk) - offset - 1))
                model.problem += model.decision[player_id] == bit, (
                    f"{label_prefix}_canonical_incidence_{index + offset:04d}"
                )
                fixed_ones += bit
            if reconstructed != optimum:
                raise LR8ExactSolverError(
                    "canonical incidence objective failed reconstruction"
                )
            incidence_optima.append(optimum)
            index += len(chunk)
    roster = _solved_roster(model)
    if sum(rank[player_id] for player_id in roster) != rank_optimum:
        raise LR8ExactSolverError("canonical roster left the frozen rank face")
    return roster, {
        "law": CANONICAL_ROSTER_LAW,
        "rank_sum": rank_optimum,
        "rank_first_roster": list(first),
        "ambiguity_distance": ambiguity_distance,
        "incidence_chunk_optima": incidence_optima,
    }


def _proof_bundle(
    *,
    solve_kind: str,
    request_sha256: str,
    result_payload: Mapping[str, object],
    solve_evidence: Sequence[rw.CbcSolveEvidence],
) -> ExactSolveProofBundle:
    evidence = tuple(solve_evidence)
    if not evidence:
        raise LR8ExactSolverError("exact solve retained no CBC evidence")
    for receipt in evidence:
        rw.validate_cbc_solve_evidence(receipt)
    payload = {
        "schema": PROOF_SCHEMA,
        "solve_kind": solve_kind,
        "request_sha256": request_sha256,
        "result": dict(result_payload),
        "cbc_solve_evidence": [
            rw._cbc_scientific_receipt(receipt)  # noqa: SLF001
            for receipt in evidence
        ],
    }
    proof_bytes = lr8.canonical_json(payload)
    return ExactSolveProofBundle(
        schema=PROOF_SCHEMA,
        solve_kind=solve_kind,
        request_sha256=request_sha256,
        result_payload=dict(result_payload),
        proof_bytes=proof_bytes,
        proof_sha256=sha256(proof_bytes).hexdigest(),
        solve_evidence=evidence,
    )


def validate_proof_bundle(value: ExactSolveProofBundle) -> None:
    if not isinstance(value, ExactSolveProofBundle):
        raise LR8ExactSolverError("exact proof bundle has the wrong type")
    if value.schema != PROOF_SCHEMA or value.solve_kind not in {
        TRAINING_SOLVE_KIND, PRICING_SOLVE_KIND,
    }:
        raise LR8ExactSolverError("exact proof schema differs")
    if (
        not isinstance(value.request_sha256, str)
        or len(value.request_sha256) != 64
        or any(character not in "0123456789abcdef" for character in value.request_sha256)
    ):
        raise LR8ExactSolverError("exact proof request hash is malformed")
    payload = {
        "schema": value.schema,
        "solve_kind": value.solve_kind,
        "request_sha256": value.request_sha256,
        "result": dict(value.result_payload),
        "cbc_solve_evidence": [
            rw._cbc_scientific_receipt(receipt)  # noqa: SLF001
            for receipt in value.solve_evidence
        ],
    }
    expected = lr8.canonical_json(payload)
    if value.proof_bytes != expected or value.proof_sha256 != sha256(
        expected
    ).hexdigest():
        raise LR8ExactSolverError("exact proof bytes or hash drifted")
    if not value.solve_evidence:
        raise LR8ExactSolverError("exact proof has no retained CBC evidence")
    for receipt in value.solve_evidence:
        rw.validate_cbc_solve_evidence(receipt)


def _publish(
    proof: ExactSolveProofBundle,
    publisher: EvidencePublisher,
) -> tuple[Mapping[str, object], ...]:
    if not callable(publisher):
        raise LR8ExactSolverError("evidence publisher must be callable")
    receipts = publisher(proof)
    if isinstance(receipts, (str, bytes)):
        raise LR8ExactSolverError("evidence publisher returned the wrong type")
    try:
        result = tuple(receipts)
    except TypeError as exc:
        raise LR8ExactSolverError(
            "evidence publisher returned the wrong type"
        ) from exc
    if not result or any(not isinstance(receipt, Mapping) for receipt in result):
        raise LR8ExactSolverError(
            "evidence publisher must return nonempty receipt mappings"
        )
    return result


def _validate_training_request(
    request: source.WorldSolveRequest,
) -> tuple[tuple[rw.PlayerSpec, ...], np.ndarray, tuple[tuple[str, ...], ...]]:
    if not isinstance(request, source.WorldSolveRequest):
        raise LR8ExactSolverError("training world request has the wrong type")
    season = _exact_int(request.season, label="training request season")
    week = _exact_int(request.week, label="training request week", minimum=1)
    if (season, week) not in source.EXPECTED_SLATE_KEYS:
        raise LR8ExactSolverError("training request cell is outside exact source")
    if request.block not in source.BLOCK_SEED_PAIRS:
        raise LR8ExactSolverError("training request block differs")
    if _exact_int(
        request.projection_seed, label="training projection seed"
    ) != source.BLOCK_SEED_PAIRS[request.block][0]:
        raise LR8ExactSolverError("training request projection seed differs")
    world_index = _exact_int(
        request.world_index, label="training world index", minimum=0
    )
    if world_index >= source.WORLDS_PER_BLOCK:
        raise LR8ExactSolverError("training request world index differs")
    players = tuple(request.players)
    try:
        catalog_hash = source.catalog_sha256(players)
    except source.LR8TrainingSourceError as exc:
        raise LR8ExactSolverError("training request catalog differs") from exc
    if players != tuple(sorted(players, key=lambda player: player.player_id)):
        raise LR8ExactSolverError("training request catalog is not canonical")
    if request.catalog_sha256 != catalog_hash:
        raise LR8ExactSolverError("training request catalog hash differs")
    scores = np.asarray(request.player_scores)
    if (
        scores.dtype != np.float32
        or scores.shape != (len(players),)
        or not np.isfinite(scores).all()
        or scores.flags.writeable
    ):
        raise LR8ExactSolverError(
            "training request scores must be read-only aligned finite float32"
        )
    if request.player_scores_sha256 != source.array_sha256(scores):
        raise LR8ExactSolverError("training request score hash differs")
    incumbents = _canonical_rosters(
        request.incumbent_no_goods, label="training incumbent no-goods"
    )
    if request.incumbent_no_goods_sha256 != source.identities_sha256(incumbents):
        raise LR8ExactSolverError("training request no-good hash differs")
    for roster in incumbents:
        try:
            lr8.audit_dk_classic_identity(players, roster)
        except lr8.LR8Error as exc:
            raise LR8ExactSolverError(
                "training incumbent no-good is not DK legal"
            ) from exc
    if request.candidate_world_family != source.CANDIDATE_WORLD_FAMILY:
        raise LR8ExactSolverError("training request world family differs")
    _literal_bool(
        request.role_belief_worlds_used,
        label="training role-belief-world use",
        expected=False,
    )
    if request.hard_domain_id != source.HARD_DOMAIN_ID:
        raise LR8ExactSolverError("training request hard domain differs")
    if request.former_house_rules_not_applied != source.FORMER_HOUSE_RULES_NOT_APPLIED:
        raise LR8ExactSolverError("training request former-house-rule law differs")
    payload = {
        "season": season,
        "week": week,
        "block": request.block,
        "projection_seed": request.projection_seed,
        "world_index": world_index,
        "catalog_sha256": catalog_hash,
        "player_scores_sha256": request.player_scores_sha256,
        "incumbent_no_goods_sha256": request.incumbent_no_goods_sha256,
        "candidate_world_family": source.CANDIDATE_WORLD_FAMILY,
        "role_belief_worlds_used": False,
        "hard_domain_id": source.HARD_DOMAIN_ID,
        "former_house_rules_not_applied": list(
            source.FORMER_HOUSE_RULES_NOT_APPLIED
        ),
    }
    if request.request_sha256 != source.canonical_sha256(payload):
        raise LR8ExactSolverError("training request hash differs")
    return players, scores, incumbents


def _solve_training_core(
    request: source.WorldSolveRequest,
    *,
    evidence_root: Path,
) -> _ExactResult:
    players, scores, incumbents = _validate_training_request(request)
    micro = rw.to_micro_dk(scores[:, None])[:, 0]
    model = lr8.build_dk_classic_model(
        players,
        name="lr8_training_world_exact",
        forbidden_rosters=incumbents,
    )
    quotient, remainder, offset = rw._bound_score_objective(  # noqa: SLF001
        model, micro, name="lr8_training_score"
    )
    factory = _solver_factory(evidence_root)
    evidence: list[rw.CbcSolveEvidence] = []
    quotient_optimum, receipt = _solve_and_freeze(
        model.problem,
        quotient,
        sense=pulp.LpMaximize,
        name="training_score_quotient",
        label="lr8 training score quotient",
        solver_factory=factory,
        warm_start=False,
    )
    evidence.append(receipt)
    remainder_optimum, receipt = _solve_and_freeze(
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
    objective = (
        quotient_optimum * rw.BOUND_OBJECTIVE_BASE
        + remainder_optimum
        + offset
    )
    roster, canonical = _canonicalize(
        model,
        solver_factory=factory,
        solve_evidence=evidence,
        label_prefix="lr8_training",
    )
    row = {player.player_id: index for index, player in enumerate(players)}
    reconstructed = sum(int(micro[row[player_id]]) for player_id in roster)
    if reconstructed != objective or objective < 0:
        raise LR8ExactSolverError("training optimum objective failed replay")
    if roster in incumbents:
        raise LR8ExactSolverError("training optimum violates incumbent no-good")
    result_payload: dict[str, object] = {
        "roster": list(roster),
        "objective_micro": objective,
        "score_quotient": quotient_optimum,
        "score_remainder": remainder_optimum,
        "score_offset": offset,
        "canonical": canonical,
        "dk_classic_only": True,
        "incumbent_no_goods_enforced": True,
        "house_rules_applied": [],
    }
    proof = _proof_bundle(
        solve_kind=TRAINING_SOLVE_KIND,
        request_sha256=request.request_sha256,
        result_payload=result_payload,
        solve_evidence=evidence,
    )
    return _ExactResult(roster, result_payload, proof)


def make_training_world_solver(
    *,
    evidence_root: Path,
    publish_evidence: EvidencePublisher,
) -> source.WorldSolver:
    """Return the exact score-only callback required by the training source."""
    root = _validate_evidence_root(evidence_root)
    if not callable(publish_evidence):
        raise LR8ExactSolverError("evidence publisher must be callable")

    def solve(request: source.WorldSolveRequest) -> source.ExactWorldOptimum:
        result = _solve_training_core(request, evidence_root=root)
        receipts = _publish(result.proof, publish_evidence)
        if result.roster is None:  # pragma: no cover - training domain is feasible
            raise AssertionError("training solve returned null")
        return source.ExactWorldOptimum(
            roster=result.roster,
            request_sha256=request.request_sha256,
            objective_micro=int(result.result_payload["objective_micro"]),
            evidence_receipts=receipts,
            exact_optimal=True,
            canonical_roster_tiebreak=True,
            dk_classic_only=True,
            incumbent_no_goods_enforced=True,
            house_rules_applied=(),
        )

    return solve


def _binary_product(
    problem: pulp.LpProblem,
    left: pulp.LpVariable,
    right: pulp.LpVariable,
    *,
    name: str,
) -> pulp.LpVariable:
    product = pulp.LpVariable(name, cat="Binary")
    problem += product <= left, f"{name}_left"
    problem += product <= right, f"{name}_right"
    problem += product >= left + right - 1, f"{name}_lower"
    return product


def _represented_indicator(
    problem: pulp.LpProblem,
    variables: Sequence[pulp.LpVariable],
    *,
    name: str,
) -> pulp.LpVariable:
    if not variables:
        raise LR8ExactSolverError("represented group is empty")
    indicator = pulp.LpVariable(name, cat="Binary")
    total = pulp.lpSum(variables)
    problem += total >= indicator, f"{name}_lower"
    problem += total <= len(variables) * indicator, f"{name}_upper"
    return indicator


def _exact_group_max(
    problem: pulp.LpProblem,
    counts: Sequence[pulp.LpAffineExpression],
    *,
    upper: int,
    name: str,
) -> pulp.LpVariable:
    if not counts:
        raise LR8ExactSolverError("exact maximum has no groups")
    maximum = pulp.LpVariable(name, lowBound=0, upBound=upper, cat="Integer")
    witnesses = [
        pulp.LpVariable(f"{name}_witness_{index:03d}", cat="Binary")
        for index in range(len(counts))
    ]
    problem += pulp.lpSum(witnesses) == 1, f"{name}_one_witness"
    for index, (count, witness) in enumerate(zip(counts, witnesses, strict=True)):
        problem += maximum >= count, f"{name}_lower_{index:03d}"
        problem += maximum <= count + upper * (1 - witness), (
            f"{name}_upper_{index:03d}"
        )
    return maximum


def _build_anatomy_graph(
    model: rw.LegalLineupModel,
    artifact: Mapping[str, object],
) -> _AnatomyGraph:
    frozen = lr8.validate_soft_anatomy_artifact(artifact)
    problem = model.problem
    players = model.players
    decision = model.decision

    salary = pulp.lpSum(
        player.salary * decision[player.player_id] for player in players
    )

    games = sorted({player.game_id for player in players})
    game_groups = [
        [decision[player.player_id] for player in players if player.game_id == game]
        for game in games
    ]
    game_represented = [
        _represented_indicator(
            problem, variables, name=f"anatomy_game_used_{index:03d}"
        )
        for index, variables in enumerate(game_groups)
    ]
    game_counts = [pulp.lpSum(variables) for variables in game_groups]

    teams = sorted({player.team for player in players})
    team_groups = [
        [decision[player.player_id] for player in players if player.team == team]
        for team in teams
    ]
    team_represented = [
        _represented_indicator(
            problem, variables, name=f"anatomy_team_used_{index:03d}"
        )
        for index, variables in enumerate(team_groups)
    ]
    team_counts = [pulp.lpSum(variables) for variables in team_groups]

    max_game = _exact_group_max(
        problem,
        game_counts,
        upper=lr8.ANATOMY_FEATURE_ABS_UPPER[3],
        name="anatomy_max_game",
    )
    max_team = _exact_group_max(
        problem,
        team_counts,
        upper=lr8.ANATOMY_FEATURE_ABS_UPPER[4],
        name="anatomy_max_team",
    )

    qbs = [player for player in players if player.position == "QB"]
    skills = [
        player for player in players if player.position in {"RB", "WR", "TE"}
    ]
    qb_partner_products: list[pulp.LpVariable] = []
    bring_back_products: list[pulp.LpVariable] = []
    for qb_index, qb in enumerate(qbs):
        qb_var = decision[qb.player_id]
        for skill_index, skill in enumerate(skills):
            skill_var = decision[skill.player_id]
            if skill.team == qb.team and skill.position in {"WR", "TE"}:
                qb_partner_products.append(_binary_product(
                    problem,
                    qb_var,
                    skill_var,
                    name=(
                        f"anatomy_qb_partner_{qb_index:03d}_{skill_index:03d}"
                    ),
                ))
            if skill.team == qb.opponent:
                bring_back_products.append(_binary_product(
                    problem,
                    qb_var,
                    skill_var,
                    name=(
                        f"anatomy_bring_back_{qb_index:03d}_{skill_index:03d}"
                    ),
                ))
    qb_partners = pulp.lpSum(qb_partner_products)
    bring_backs = pulp.lpSum(bring_back_products)

    dsts = [player for player in players if player.position == "DST"]
    rbs = [player for player in players if player.position == "RB"]
    rb_dst_products: list[pulp.LpVariable] = []
    for dst_index, dst in enumerate(dsts):
        for rb_index, rb in enumerate(rbs):
            if rb.team == dst.opponent:
                rb_dst_products.append(_binary_product(
                    problem,
                    decision[dst.player_id],
                    decision[rb.player_id],
                    name=f"anatomy_rb_dst_{dst_index:03d}_{rb_index:03d}",
                ))
    rb_against_dst = pulp.lpSum(rb_dst_products)

    same_team_rb_products: list[pulp.LpVariable] = []
    for left_index, left in enumerate(rbs):
        for right_index in range(left_index + 1, len(rbs)):
            right = rbs[right_index]
            if left.team == right.team:
                same_team_rb_products.append(_binary_product(
                    problem,
                    decision[left.player_id],
                    decision[right.player_id],
                    name=(
                        f"anatomy_same_rb_{left_index:03d}_{right_index:03d}"
                    ),
                ))
    same_team_rb_pairs = pulp.lpSum(same_team_rb_products)

    partner_bins = [
        pulp.LpVariable(f"anatomy_qb_partner_count_{count}", cat="Binary")
        for count in range(lr8.ANATOMY_FEATURE_ABS_UPPER[5] + 1)
    ]
    problem += pulp.lpSum(partner_bins) == 1, "anatomy_qb_partner_one_count"
    problem += qb_partners == pulp.lpSum(
        count * variable for count, variable in enumerate(partner_bins)
    ), "anatomy_qb_partner_count_link"

    salary_by_position = {
        position: pulp.lpSum(
            player.salary * decision[player.player_id]
            for player in players if player.position == position
        )
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    features: tuple[pulp.LpAffineExpression | pulp.LpVariable, ...] = (
        salary,
        pulp.lpSum(game_represented),
        pulp.lpSum(team_represented),
        max_game,
        max_team,
        qb_partners,
        bring_backs,
        rb_against_dst,
        same_team_rb_pairs,
        partner_bins[0],
        partner_bins[1],
        salary_by_position["QB"],
        salary_by_position["RB"],
        salary_by_position["WR"],
        salary_by_position["TE"],
        salary_by_position["DST"],
    )
    if len(features) != len(lr8.ANATOMY_FEATURES):
        raise AssertionError("LR8 anatomy graph width changed")
    bound = int(frozen["operative_worst_case_abs_units"])
    expression = int(frozen["operative_intercept_units"]) + pulp.lpSum(
        int(weight) * feature
        for weight, feature in zip(
            frozen["operative_raw_weight_units"], features, strict=True
        )
    )
    constant_raw = float(expression.constant)
    constant = int(round(constant_raw))
    if not math.isfinite(constant_raw) or constant_raw != constant:
        raise LR8ExactSolverError("anatomy linear tier constant is not exact")
    fixed_one = pulp.LpVariable("anatomy_linear_fixed_one", cat="Binary")
    problem += fixed_one == 1, "anatomy_linear_fixed_one_anchor"
    terms = [
        (variable, int(coefficient))
        for variable, coefficient in expression.items()
        if int(coefficient) != 0
    ]
    terms.append((fixed_one, constant + bound))
    tier_number = rw._binary_weighted_sum(  # noqa: SLF001
        problem,
        terms,
        upper_bound=2 * bound,
        name="anatomy_linear_shifted",
    )
    return _AnatomyGraph(features, tier_number, -bound)


def pricing_request_sha256(request: lr8.PricingRequest) -> str:
    players, scores, maxima, forbidden, artifact = _validate_pricing_request(
        request, compute_hash=False
    )
    return lr8.canonical_sha256({
        "protocol_id": lr8.PROTOCOL_ID,
        "fold_name": request.fold_name,
        "iteration": request.iteration,
        "construction_blocks": list(request.construction_blocks),
        "player_catalog": _catalog_payload(players),
        "world_ids": [
            [world.block, world.index] for world in request.world_ids
        ],
        "player_scores_micro_sha256": _array_sha256(scores),
        "book_maxima_micro_sha256": _array_sha256(maxima),
        "control_rosters": [list(value) for value in request.control_rosters],
        "previous_columns": [list(value) for value in request.previous_columns],
        "forbidden_rosters": [list(value) for value in forbidden],
        "marginal_thresholds_micro": list(request.marginal_thresholds_micro),
        "book_max_cap_micro": request.book_max_cap_micro,
        "portfolio_improvement_required": True,
        "anatomy_linear_scale": request.anatomy_linear_scale,
        "anatomy_artifact_sha256": artifact["artifact_sha256"],
    })


def _validate_pricing_request(
    request: lr8.PricingRequest,
    *,
    compute_hash: bool = True,
) -> tuple[
    tuple[rw.PlayerSpec, ...],
    np.ndarray,
    np.ndarray,
    tuple[tuple[str, ...], ...],
    dict[str, object],
]:
    if not isinstance(request, lr8.PricingRequest):
        raise LR8ExactSolverError("pricing request has the wrong type")
    specs = {spec.name: spec for spec in lr8.FOLD_SPECS}
    if request.fold_name not in specs or request.construction_blocks != specs[
        request.fold_name
    ].construction_blocks:
        raise LR8ExactSolverError("pricing fold construction blocks differ")
    iteration = _exact_int(
        request.iteration, label="pricing iteration", minimum=1
    )
    if iteration > lr8.K_MAX_PER_FOLD:
        raise LR8ExactSolverError("pricing iteration exceeds K_max")
    players = tuple(request.players)
    if (
        len(players) < rw.ROSTER_SIZE
        or any(not isinstance(player, rw.PlayerSpec) for player in players)
        or len({player.player_id for player in players}) != len(players)
    ):
        raise LR8ExactSolverError("pricing player catalog differs")
    scores = np.asarray(request.player_scores_micro)
    maxima = np.asarray(request.book_maxima_micro)
    if (
        scores.dtype != np.int64
        or scores.ndim != 2
        or scores.shape[0] != len(players)
        or scores.shape[1] == 0
        or scores.flags.writeable
    ):
        raise LR8ExactSolverError(
            "pricing scores must be read-only aligned nonempty int64"
        )
    if (
        maxima.dtype != np.int64
        or maxima.shape != (scores.shape[1],)
        or maxima.flags.writeable
    ):
        raise LR8ExactSolverError(
            "pricing book maxima must be read-only aligned int64"
        )
    largest = max(abs(int(scores.min())), abs(int(scores.max())))
    if largest > rw.CBC_EXACT_INTEGER_MAX // rw.ROSTER_SIZE:
        raise LR8ExactSolverError("pricing scores exceed exact CBC range")
    worlds = tuple(request.world_ids)
    if len(worlds) != scores.shape[1] or any(
        not isinstance(world, rw.WorldId) for world in worlds
    ) or len(set(worlds)) != len(worlds):
        raise LR8ExactSolverError("pricing world identities differ")
    block_rank = {block: index for index, block in enumerate(rw.WORLD_BLOCKS)}
    if worlds != tuple(sorted(
        worlds, key=lambda world: (block_rank[world.block], world.index)
    )) or any(world.block not in request.construction_blocks for world in worlds):
        raise LR8ExactSolverError("pricing worlds are not canonical construction worlds")
    controls = _canonical_rosters(
        request.control_rosters, label="pricing controls"
    )
    previous = _canonical_rosters(
        request.previous_columns,
        label="pricing previous columns",
        allow_empty=True,
    )
    forbidden = _canonical_rosters(
        request.forbidden_rosters, label="pricing complete no-goods"
    )
    if forbidden != (*controls, *previous):
        raise LR8ExactSolverError(
            "pricing no-goods do not contain exact controls plus prior columns"
        )
    for roster in forbidden:
        try:
            lr8.audit_dk_classic_identity(players, roster)
        except lr8.LR8Error as exc:
            raise LR8ExactSolverError(
                "pricing no-good is not DK Classic legal"
            ) from exc
    if request.marginal_thresholds_micro != lr8.MARGINAL_THRESHOLDS_MICRO:
        raise LR8ExactSolverError("pricing thresholds differ")
    if _exact_int(
        request.book_max_cap_micro, label="pricing book-max cap", minimum=1
    ) != lr8.BOOK_MAX_CAP_MICRO:
        raise LR8ExactSolverError("pricing book-max cap differs")
    _literal_bool(
        request.portfolio_improvement_required,
        label="pricing positive-residual requirement",
        expected=True,
    )
    if _exact_int(
        request.anatomy_linear_scale,
        label="pricing anatomy linear scale",
        minimum=1,
    ) != lr8.ANATOMY_LINEAR_SCALE:
        raise LR8ExactSolverError("pricing anatomy linear scale differs")
    artifact = lr8.validate_soft_anatomy_artifact(request.anatomy_artifact)
    if compute_hash:
        # Exercise the complete hash serialization at this validation boundary.
        pricing_request_sha256(request)
    return players, scores, maxima, forbidden, artifact


def _clipped_gain_number(
    model: rw.LegalLineupModel,
    scores: np.ndarray,
    maxima: np.ndarray,
    cap: int,
    binary_scores: Sequence[tuple[rw._BinaryNumber, int]],  # noqa: SLF001
) -> tuple[rw._BinaryNumber, int]:  # noqa: SLF001
    terms: list[tuple[pulp.LpVariable, int]] = []
    upper_total = 0
    for world, (score_number, offset) in enumerate(binary_scores):
        upper = offset + score_number.upper_bound
        reference = min(int(maxima[world]), cap)
        if reference >= cap:
            continue
        score_expression = rw._score_expression(  # noqa: SLF001
            model, scores[:, world]
        )
        first, _ = rw._add_exact_product_positive_part(  # noqa: SLF001
            model,
            score_expression,
            score_number,
            offset,
            scores[:, world],
            min(offset, reference),
            upper,
            reference,
            name=f"lr8_gain_reference_{world:04d}",
        )
        second, _ = rw._add_exact_product_positive_part(  # noqa: SLF001
            model,
            score_expression,
            score_number,
            offset,
            scores[:, world],
            min(offset, cap),
            upper,
            cap,
            name=f"lr8_gain_cap_{world:04d}",
        )
        expression = first - second
        if rw._integer_value(expression.constant) != 0:  # noqa: SLF001
            raise LR8ExactSolverError("clipped-gain graph has a constant term")
        terms.extend(
            (variable, int(coefficient))
            for variable, coefficient in expression.items()
        )
        upper_total += max(0, min(upper, cap) - reference)
    number = rw._binary_weighted_sum(  # noqa: SLF001
        model.problem,
        terms,
        upper_bound=upper_total,
        name="lr8_clipped_gain_total",
    )
    return number, upper_total


def _gain_objective_chunks(
    number: rw._BinaryNumber,  # noqa: SLF001
) -> tuple[pulp.LpAffineExpression, ...]:
    """Return exact MSB-first chunks with bounded, exactly serialized weights."""
    chunks: list[pulp.LpAffineExpression] = []
    high = len(number.bits) - 1
    while high >= 0:
        low = max(0, high - GAIN_OBJECTIVE_CHUNK_BITS + 1)
        chunks.append(pulp.lpSum(
            number.bits[place] * (1 << (place - low))
            for place in range(low, high + 1)
        ))
        high = low - 1
    return tuple(chunks)


def _pricing_roster_replay(
    players: tuple[rw.PlayerSpec, ...],
    scores: np.ndarray,
    maxima: np.ndarray,
    artifact: Mapping[str, object],
    roster: tuple[str, ...],
) -> tuple[tuple[int, ...], int, int, tuple[int, ...]]:
    row = {player.player_id: index for index, player in enumerate(players)}
    chosen = np.asarray([row[player_id] for player_id in roster], dtype=int)
    totals = scores[chosen].sum(axis=0, dtype=np.int64)
    counts, _, gain, _ = lr8.clipped_marginal_utility(totals, maxima)
    anatomy = lr8.lineup_anatomy(players, roster)
    tier = lr8.operative_anatomy_linear_units(artifact, anatomy)
    return counts, tier, gain, tuple(int(value) for value in totals)


def _solve_pricing_core(
    request: lr8.PricingRequest,
    *,
    evidence_root: Path,
) -> _ExactResult:
    players, scores, maxima, forbidden, artifact = _validate_pricing_request(
        request, compute_hash=False
    )
    request_hash = pricing_request_sha256(request)
    model = lr8.build_dk_classic_model(
        players,
        name="lr8_exact_pricing",
        forbidden_rosters=forbidden,
    )
    binary_scores = tuple(
        rw._binary_score_number(  # noqa: SLF001
            model, scores[:, world], name=f"lr8_score_{world:04d}"
        )
        for world in range(scores.shape[1])
    )

    threshold_values: list[pulp.LpVariable] = []
    for tier_index, threshold in enumerate(request.marginal_thresholds_micro):
        indicators: list[pulp.LpVariable] = []
        for world, (number, offset) in enumerate(binary_scores):
            if int(maxima[world]) >= threshold:
                continue
            indicators.append(rw._binary_ge_indicator(  # noqa: SLF001
                model.problem,
                number,
                threshold - offset,
                name=f"lr8_threshold_{tier_index:02d}_{world:04d}",
            ))
        value = pulp.LpVariable(
            f"lr8_threshold_count_{tier_index:02d}",
            lowBound=0,
            upBound=scores.shape[1],
            cat="Integer",
        )
        model.problem += value == pulp.lpSum(indicators), (
            f"lr8_threshold_count_link_{tier_index:02d}"
        )
        threshold_values.append(value)

    anatomy = _build_anatomy_graph(model, artifact)
    gain_number, gain_upper = _clipped_gain_number(
        model,
        scores,
        maxima,
        request.book_max_cap_micro,
        binary_scores,
    )
    positive = pulp.LpVariable("lr8_positive_residual", cat="Binary")
    if gain_number.bits:
        for place, bit in enumerate(gain_number.bits):
            model.problem += positive >= bit, (
                f"lr8_positive_residual_lower_{place:03d}"
            )
        model.problem += positive <= pulp.lpSum(gain_number.bits), (
            "lr8_positive_residual_upper"
        )
    else:  # pragma: no cover - binary numbers always expose at least one bit
        model.problem += positive == 0, "lr8_positive_residual_empty"

    factory = _solver_factory(evidence_root)
    evidence: list[rw.CbcSolveEvidence] = []
    stages: list[dict[str, object]] = []
    positive_optimum, receipt = _solve_and_freeze(
        model.problem,
        positive,
        sense=pulp.LpMaximize,
        name="positive_residual",
        label="lr8 pricing positive-residual existence",
        solver_factory=factory,
        warm_start=False,
    )
    evidence.append(receipt)
    stages.append({"name": "positive_residual_exists", "optimum": positive_optimum})
    if positive_optimum == 0:
        result_payload: dict[str, object] = {
            "roster": None,
            "null": True,
            "positive_residual_optimum": 0,
            "gain_upper_bound_micro": gain_upper,
            "stages": stages,
            "dk_classic_only": True,
            "house_rules_applied": [],
        }
        proof = _proof_bundle(
            solve_kind=PRICING_SOLVE_KIND,
            request_sha256=request_hash,
            result_payload=result_payload,
            solve_evidence=evidence,
        )
        return _ExactResult(None, result_payload, proof)
    if positive_optimum != 1:
        raise LR8ExactSolverError("positive-residual optimum is not binary")

    threshold_optima: list[int] = []
    for tier_index, expression in enumerate(threshold_values):
        optimum, receipt = _solve_and_freeze(
            model.problem,
            expression,
            sense=pulp.LpMaximize,
            name=f"threshold_{tier_index:02d}",
            label=f"lr8 pricing threshold tier {tier_index:02d}",
            solver_factory=factory,
            warm_start=False,
            cuts_off=True,
            preprocess_off=True,
        )
        evidence.append(receipt)
        threshold_optima.append(optimum)
        stages.append({"name": f"g{lr8.MARGINAL_THRESHOLDS_DK[tier_index]}", "optimum": optimum})

    anatomy_chunk_optima: list[int] = []
    for chunk_index, expression in enumerate(
        _gain_objective_chunks(anatomy.tier_number)
    ):
        optimum, receipt = _solve_and_freeze(
            model.problem,
            expression,
            sense=pulp.LpMaximize,
            name=f"anatomy_linear_chunk_{chunk_index:02d}",
            label=f"lr8 pricing anatomy-linear chunk {chunk_index:02d}",
            solver_factory=factory,
            warm_start=False,
            cuts_off=True,
            preprocess_off=True,
        )
        evidence.append(receipt)
        anatomy_chunk_optima.append(optimum)
        stages.append({
            "name": f"anatomy_linear_chunk_{chunk_index:02d}",
            "optimum": optimum,
        })
    anatomy_optimum = (
        rw._binary_value(anatomy.tier_number)  # noqa: SLF001
        + anatomy.tier_offset
    )

    gain_chunk_optima: list[int] = []
    for chunk_index, expression in enumerate(
        _gain_objective_chunks(gain_number)
    ):
        optimum, receipt = _solve_and_freeze(
            model.problem,
            expression,
            sense=pulp.LpMaximize,
            name=f"clipped_gain_chunk_{chunk_index:02d}",
            label=f"lr8 pricing clipped-gain chunk {chunk_index:02d}",
            solver_factory=factory,
            warm_start=False,
            cuts_off=True,
            preprocess_off=True,
        )
        evidence.append(receipt)
        gain_chunk_optima.append(optimum)
        stages.append({"name": f"clipped_gain_chunk_{chunk_index:02d}", "optimum": optimum})
    gain_optimum = rw._binary_value(gain_number)  # noqa: SLF001

    roster, canonical = _canonicalize(
        model,
        solver_factory=factory,
        solve_evidence=evidence,
        label_prefix="lr8_pricing",
    )
    if roster in forbidden:
        raise LR8ExactSolverError("pricing roster violates a complete no-good")
    counts, anatomy_tier, gain, totals = _pricing_roster_replay(
        players, scores, maxima, artifact, roster
    )
    if (
        counts != tuple(threshold_optima)
        or anatomy_tier != anatomy_optimum
        or gain != gain_optimum
        or gain <= 0
    ):
        raise LR8ExactSolverError("pricing hierarchy failed independent replay")
    for expression, expected in zip(
        anatomy.feature_expressions,
        lr8.lineup_anatomy(players, roster),
        strict=True,
    ):
        if rw._integer_value(expression) != int(expected):  # noqa: SLF001
            raise LR8ExactSolverError("CBC anatomy graph failed feature parity")
    result_payload = {
        "roster": list(roster),
        "null": False,
        "positive_residual_optimum": 1,
        "threshold_counts": list(counts),
        "anatomy_linear_predictor_units": anatomy_tier,
        "anatomy_chunk_optima": anatomy_chunk_optima,
        "clipped_gain_micro": gain,
        "candidate_scores_micro": list(totals),
        "gain_upper_bound_micro": gain_upper,
        "gain_chunk_optima": gain_chunk_optima,
        "canonical": canonical,
        "stages": stages,
        "dk_classic_only": True,
        "house_rules_applied": [],
    }
    proof = _proof_bundle(
        solve_kind=PRICING_SOLVE_KIND,
        request_sha256=request_hash,
        result_payload=result_payload,
        solve_evidence=evidence,
    )
    return _ExactResult(roster, result_payload, proof)


class ExactPricingStep:
    """Stateful pricing callback exposing the last locally verified proof."""

    def __init__(
        self,
        *,
        evidence_root: Path,
        publish_evidence: EvidencePublisher,
    ) -> None:
        self._evidence_root = _validate_evidence_root(evidence_root)
        if not callable(publish_evidence):
            raise LR8ExactSolverError("evidence publisher must be callable")
        self._publisher = publish_evidence
        self.last_proof: ExactSolveProofBundle | None = None
        self.last_evidence_receipts: tuple[Mapping[str, object], ...] = ()

    def __call__(self, request: lr8.PricingRequest) -> tuple[str, ...] | None:
        result = _solve_pricing_core(request, evidence_root=self._evidence_root)
        receipts = _publish(result.proof, self._publisher)
        self.last_proof = result.proof
        self.last_evidence_receipts = receipts
        return result.roster


def make_pricing_step(
    *,
    evidence_root: Path,
    publish_evidence: EvidencePublisher,
) -> ExactPricingStep:
    """Return the exact positive-residual LR8 pricing callback."""
    return ExactPricingStep(
        evidence_root=evidence_root,
        publish_evidence=publish_evidence,
    )


def validate_training_world_solution(
    request: source.WorldSolveRequest,
    response: source.ExactWorldOptimum,
    proof: ExactSolveProofBundle,
    *,
    replay_evidence_root: Path,
) -> None:
    """Independently rebuild and re-solve one claimed training optimum."""
    _validate_training_request(request)
    validate_proof_bundle(proof)
    if proof.solve_kind != TRAINING_SOLVE_KIND or proof.request_sha256 != (
        request.request_sha256
    ):
        raise LR8ExactSolverError("training proof is stale or the wrong kind")
    if not isinstance(response, source.ExactWorldOptimum):
        raise LR8ExactSolverError("training response has the wrong type")
    for label, value in (
        ("exact_optimal", response.exact_optimal),
        ("canonical_roster_tiebreak", response.canonical_roster_tiebreak),
        ("dk_classic_only", response.dk_classic_only),
        ("incumbent_no_goods_enforced", response.incumbent_no_goods_enforced),
    ):
        _literal_bool(value, label=f"training response {label}", expected=True)
    if response.house_rules_applied != ():
        raise LR8ExactSolverError("training response applied a former house rule")
    if response.request_sha256 != request.request_sha256:
        raise LR8ExactSolverError("training response is stale")
    if (
        proof.result_payload.get("roster") != list(response.roster)
        or proof.result_payload.get("objective_micro") != response.objective_micro
        or proof.result_payload.get("house_rules_applied") != []
    ):
        raise LR8ExactSolverError("training response differs from proof payload")
    if not response.evidence_receipts or any(
        not isinstance(value, Mapping) for value in response.evidence_receipts
    ):
        raise LR8ExactSolverError("training response lacks publisher receipts")
    replay = _solve_training_core(
        request, evidence_root=_validate_evidence_root(replay_evidence_root)
    )
    if (
        replay.roster != response.roster
        or replay.result_payload["objective_micro"] != response.objective_micro
        or replay.result_payload != proof.result_payload
    ):
        raise LR8ExactSolverError(
            "training response is suboptimal, noncanonical, or proof-drifted"
        )


def validate_pricing_solution(
    request: lr8.PricingRequest,
    response: Sequence[object] | None,
    proof: ExactSolveProofBundle,
    *,
    replay_evidence_root: Path,
) -> None:
    """Independently rebuild and re-solve one claimed pricing/null response."""
    request_hash = pricing_request_sha256(request)
    validate_proof_bundle(proof)
    if proof.solve_kind != PRICING_SOLVE_KIND or proof.request_sha256 != request_hash:
        raise LR8ExactSolverError("pricing proof is stale or the wrong kind")
    roster = None if response is None else rw.canonical_identity(response)
    if proof.result_payload.get("roster") != (
        None if roster is None else list(roster)
    ) or proof.result_payload.get("house_rules_applied") != []:
        raise LR8ExactSolverError("pricing response differs from proof payload")
    replay = _solve_pricing_core(
        request, evidence_root=_validate_evidence_root(replay_evidence_root)
    )
    if replay.roster != roster or replay.result_payload != proof.result_payload:
        raise LR8ExactSolverError(
            "pricing response is suboptimal, noncanonical, null-wrong, or drifted"
        )


__all__ = [
    "CANONICAL_ROSTER_LAW",
    "EXACT_SOLVE_SECONDS",
    "GAIN_OBJECTIVE_CHUNK_BITS",
    "EvidencePublisher",
    "ExactPricingStep",
    "ExactSolveProofBundle",
    "LR8ExactSolverError",
    "PRICING_SOLVE_KIND",
    "PROOF_SCHEMA",
    "TRAINING_SOLVE_KIND",
    "make_pricing_step",
    "make_training_world_solver",
    "pricing_request_sha256",
    "validate_pricing_solution",
    "validate_proof_bundle",
    "validate_training_world_solution",
]
