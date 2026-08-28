"""Executable, outcome-blind outer optimizer for hard-230 replenishment.

The frozen :mod:`corpus_extreme_tail_generation_additions` contract is a pure
replay seam: it validates an ordered stream of solver occurrences but does not
create that stream.  This module supplies the smallest executable outer seam.
It solves the incumbent legal optimum for each world in one caller-authorized
order, derives both populations from the *same* solver calls, and stops only
when the hard-230 population reaches the paired target or the frozen public
ceiling is exhausted.

This is population generation, not the strict-230 admission selector and not
the historical T230 panel.  No realized outcome, field result, selector, or
production policy is read here.  Release mode requires an exact CBC proof on
every solver call and a create-once JSON evidence publisher supplied by the
outer execution layer.  The returned receipts retain false publication,
promotion, and decision authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from typing import Final, Protocol

import numpy as np

from nfl_dfs.research import corpus_extreme_tail_generation_additions as hard
from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import residual_world_columns as rw


OUTER_AUTHORITY_SCHEMA: Final = "hard-230-outer-optimizer-authority/v1"
OUTER_STREAM_SCHEMA: Final = "hard-230-outer-optimizer-stream/v1"
OUTER_SOLVER_EVIDENCE_SCHEMA: Final = "hard-230-outer-solver-evidence/v1"
OUTER_LEGALITY_EVIDENCE_SCHEMA: Final = "hard-230-outer-legality-evidence/v1"
OUTER_RECEIPT_SCHEMA: Final = "hard-230-outer-optimizer-receipt/v1"

RELEASE_EXECUTION_MODE: Final = "release"
FIXTURE_EXECUTION_MODE: Final = "test-fixture"
INCUMBENT_PROFILE_ID: Final = "incumbent"
COMPARATOR_POPULATION_ID: Final = "hard230-shared-stream-score-blind-prefix-v1"
DIAGNOSTIC_THRESHOLDS_MILLI: Final = (200_000, 220_000, 230_000)
MILLI_TO_MICRO: Final = 1_000

_FALSE_AUTHORITY_FIELDS: Final = (
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "selector_authority",
    "publication_authority",
    "promotion_authority",
    "decision_authority",
    "production_change_licensed",
)


class Hard230OuterOptimizerAdapterError(ValueError):
    """The optimizer input, proof, or generated stream is not authoritative."""


class ExactJsonPublisher(Protocol):
    """Create one immutable JSON object and return its exact GCS identity."""

    def __call__(
        self, *, role: str, deterministic_key: str, payload: bytes
    ) -> Mapping[str, object]: ...


SolverCallback = Callable[[legal.SolveRequest], legal.SolveOutcome]


@dataclass(frozen=True, slots=True)
class Hard230OuterOptimizerResult:
    """Local result plus every input needed to replay the frozen pure receipt."""

    outer_receipt: Mapping[str, object]
    hard230_generation_receipt: Mapping[str, object]
    generator_stream_identity: Mapping[str, object]
    occurrences: tuple[Mapping[str, object], ...]


def _fail(message: str) -> None:
    raise Hard230OuterOptimizerAdapterError(message)


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return legal.canonical_json_bytes(value)
    except (TypeError, ValueError, legal.CorpusLegalFeasibilityError) as exc:
        raise Hard230OuterOptimizerAdapterError(
            f"{label} is not finite canonical JSON"
        ) from exc


def _sha(value: object, *, label: str) -> str:
    return hashlib.sha256(_canonical(value, label=label)).hexdigest()


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    result[field] = _sha(result, label=field)
    return result


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one array")
    return value


def _nonempty(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be one nonempty exact string")
    return value


def _sha256(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase SHA-256")
    return value


def _git_sha(value: object, *, label: str) -> str:
    if (
        type(value) is not str
        or len(value) != 40
        or any(character not in "0123456789abcdef" for character in value)
    ):
        _fail(f"{label} must be one lowercase 40-character Git SHA")
    return value


def _object_identity(
    value: object, *, label: str, expected_payload: bytes | None = None
) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    uri = _nonempty(item.get("uri"), label=f"{label} URI")
    generation = _nonempty(item.get("generation"), label=f"{label} generation")
    byte_count = item.get("bytes")
    if (
        not uri.startswith("gs://")
        or not generation.isdigit()
        or type(byte_count) is not int
        or byte_count < 1
    ):
        _fail(f"{label} must be one generation-pinned nonempty GCS object")
    content_sha = _sha256(item.get("sha256"), label=f"{label} SHA-256")
    if expected_payload is not None and (
        content_sha != hashlib.sha256(expected_payload).hexdigest()
        or byte_count != len(expected_payload)
    ):
        _fail(f"{label} differs from the exact bytes supplied to the publisher")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": content_sha,
        "bytes": byte_count,
    }


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _execution_mode(value: object) -> str:
    if value not in {RELEASE_EXECUTION_MODE, FIXTURE_EXECUTION_MODE}:
        _fail("execution_mode must be exactly 'release' or 'test-fixture'")
    return str(value)


def _optimizer_authority(
    value: object, *, incumbent_profile_sha256: str
) -> dict[str, object]:
    item = _mapping(value, label="optimizer authority")
    expected = {
        "schema_version",
        "source_commit_sha",
        "immutable_image_digest",
        "outer_adapter_source_sha256",
        "solver_implementation_sha256",
        "solver_authority_sha256",
        "incumbent_profile_sha256",
        "optimizer_source_identity",
        "terminal_runtime_receipt_identity",
        "outcome_columns_read",
        "uses_realized_outcomes",
    }
    if set(item) != expected:
        _fail("optimizer authority fields differ")
    image = _nonempty(item.get("immutable_image_digest"), label="image digest")
    if not image.startswith("sha256:") or len(image) != 71:
        _fail("immutable_image_digest must be one sha256 registry digest")
    _sha256(image[7:], label="immutable image digest body")
    if item.get("schema_version") != OUTER_AUTHORITY_SCHEMA:
        _fail("optimizer authority schema differs")
    if item.get("incumbent_profile_sha256") != incumbent_profile_sha256:
        _fail("optimizer authority does not bind the exact incumbent legal profile")
    if item.get("outcome_columns_read") != [] or item.get("uses_realized_outcomes") is not False:
        _fail("hard-230 optimizer authority may not expose outcome columns")
    return {
        "schema_version": OUTER_AUTHORITY_SCHEMA,
        "source_commit_sha": _git_sha(
            item.get("source_commit_sha"), label="optimizer source commit"
        ),
        "immutable_image_digest": image,
        "outer_adapter_source_sha256": _sha256(
            item.get("outer_adapter_source_sha256"),
            label="outer adapter source SHA-256",
        ),
        "solver_implementation_sha256": _sha256(
            item.get("solver_implementation_sha256"),
            label="solver implementation SHA-256",
        ),
        "solver_authority_sha256": _sha256(
            item.get("solver_authority_sha256"), label="solver authority SHA-256"
        ),
        "incumbent_profile_sha256": incumbent_profile_sha256,
        "optimizer_source_identity": _object_identity(
            item.get("optimizer_source_identity"), label="optimizer source identity"
        ),
        "terminal_runtime_receipt_identity": _object_identity(
            item.get("terminal_runtime_receipt_identity"),
            label="terminal runtime receipt identity",
        ),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }


def _publish(
    publisher: ExactJsonPublisher,
    *,
    role: str,
    deterministic_key: str,
    body: Mapping[str, object],
) -> tuple[dict[str, object], bytes]:
    payload = _canonical(body, label=f"{role} evidence")
    try:
        raw_identity = publisher(
            role=role, deterministic_key=deterministic_key, payload=payload
        )
    except Exception as exc:
        raise Hard230OuterOptimizerAdapterError(
            f"exact JSON publisher failed for {role}"
        ) from exc
    return (
        _object_identity(
            raw_identity, label=f"published {role}", expected_payload=payload
        ),
        payload,
    )


def _ordered_records_sha256(rows: Sequence[object], *, label: str) -> str:
    """Mirror the frozen contract's length-prefixed ordered-record identity."""
    digest = hashlib.sha256()
    header = _canonical(
        {"encoding": "length-prefixed-canonical-json-records/v1", "label": label},
        label=f"{label} hash header",
    )
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    for row in rows:
        encoded = _canonical(row, label=f"{label} record")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    digest.update(len(rows).to_bytes(8, "big"))
    return digest.hexdigest()


def _fit_scope(heldout_block: str | None) -> tuple[str, tuple[str, ...]]:
    if heldout_block is None:
        return "all-block-final-fit", tuple(hard.WORLD_BLOCKS)
    if heldout_block not in hard.WORLD_BLOCKS:
        _fail("heldout_block must be null or one exact R0..R4 block")
    return (
        f"holdout-{heldout_block}",
        tuple(block for block in hard.WORLD_BLOCKS if block != heldout_block),
    )


def _preflight_source(
    *,
    candidate_origin_id: str,
    heldout_block: str | None,
    worlds_per_block: int,
    source_member_identity: Mapping[str, object],
    score_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    score_matrix: np.ndarray,
    score_matrix_identity: Mapping[str, object],
    ordered_generator_world_indices: Sequence[int],
    paired_control: Mapping[str, object],
    require_production_width: bool,
) -> dict[str, object]:
    try:
        width = hard._validated_world_count(
            worlds_per_block, require_production_width=require_production_width
        )
    except hard.CorpusExtremeTailGenerationAdditionsError as exc:
        raise Hard230OuterOptimizerAdapterError(str(exc)) from exc
    fit_scope_id, training_blocks = _fit_scope(heldout_block)
    origin = _nonempty(candidate_origin_id, label="candidate origin")
    if origin not in hard.WORLD_BLOCKS:
        _fail(
            "outer optimizer v1 supports only incumbent K5 origins R0..R4; "
            "R5..R19 lack a bound optimizer WorldId authority"
        )
    if origin not in training_blocks:
        _fail("candidate origin may not equal the heldout block")
    try:
        pure_context = hard._prepare_score_context(
            source_member_identity=source_member_identity,
            score_block_identities=score_block_identities,
            player_registry=player_registry,
            score_matrix=score_matrix,
            score_matrix_identity=score_matrix_identity,
            expected_block_ids=training_blocks,
            worlds_per_block=width,
        )
        world_order = tuple(
            hard._ordered_generator_world_indices(
                ordered_generator_world_indices, worlds_per_block=width
            )
        )
        control = hard._paired_control(
            paired_control,
            origin_id=origin,
            fit_scope_id=fit_scope_id,
            heldout_block=heldout_block,
            training_blocks=training_blocks,
            context=pure_context,
        )
    except hard.CorpusExtremeTailGenerationAdditionsError as exc:
        message = str(exc)
        if "player registry count is outside" in message:
            message = "player registry is outside the frozen hard-230 9..512-player bound"
        raise Hard230OuterOptimizerAdapterError(message) from exc
    specs = tuple(
        rw.PlayerSpec.from_mapping(row) for row in pure_context["player_registry"]
    )
    player_ids = tuple(player.player_id for player in specs)
    lineage = hard._source_lineage(pure_context)
    target = int(control["retained_count"])
    computed_ceiling = min(
        hard.HARD230_MAXIMUM_SOLVER_CALL_CEILING,
        max(
            hard.HARD230_MINIMUM_SOLVER_CALL_CEILING,
            hard.HARD230_SOLVER_CALLS_PER_TARGET * target,
        ),
    )
    effective_ceiling = min(width, computed_ceiling)
    if target > effective_ceiling:
        _fail("paired target exceeds the frozen effective solver-call ceiling")
    return {
        "fit_scope_id": fit_scope_id,
        "training_blocks": training_blocks,
        "origin": origin,
        "origin_block_ordinal": training_blocks.index(origin),
        "players": specs,
        "player_ids": player_ids,
        "player_index": pure_context["player_index"],
        "world_order": world_order,
        "lineage": lineage,
        "target": target,
        "computed_ceiling": computed_ceiling,
        "effective_ceiling": effective_ceiling,
        "paired_control_identity": control["receipt_identity"],
    }


def _solver_input(
    *,
    stream_id: str,
    generator_configuration_sha256: str,
    candidate_origin_id: str,
    position: int,
    world_index: int,
    source_lineage: Mapping[str, object],
) -> dict[str, object]:
    return {
        "strategy_id": hard.HARD230_STRATEGY_ID,
        "generator_law_id": hard.HARD230_GENERATOR_LAW_ID,
        "stream_id": stream_id,
        "generator_configuration_sha256": generator_configuration_sha256,
        "candidate_origin_id": candidate_origin_id,
        "stream_position": position,
        "source_world_index": world_index,
        **dict(source_lineage),
    }


def _solver_proof_payload(value: legal.SolveOutcome) -> object:
    proof = value.solver_proof
    if proof is None:
        return None
    if type(proof.canonical_payload) is not bytes:
        _fail("solver proof payload must be exact canonical bytes")
    try:
        return json.loads(proof.canonical_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Hard230OuterOptimizerAdapterError(
            "solver proof payload is not canonical JSON"
        ) from exc


def _score_roster(
    roster: Sequence[str], *, matrix: np.ndarray, player_index: Mapping[str, int]
) -> np.ndarray:
    scores = np.zeros(matrix.shape[1], dtype=np.dtype("<i8"))
    for player_id in roster:
        scores += matrix[player_index[player_id], :]
    return scores


def _score_vector_sha256(vector: np.ndarray, *, label: str) -> str:
    canonical = np.ascontiguousarray(vector, dtype=np.dtype("<i8"))
    digest = hashlib.sha256()
    header = _canonical(
        {
            "encoding": "little-endian-int64-vector/v1",
            "label": label,
            "length": int(canonical.shape[0]),
        },
        label=f"{label} header",
    )
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    digest.update(memoryview(canonical).cast("B"))
    return digest.hexdigest()


def _population_diagnostics(
    *,
    population_id: str,
    rosters: Sequence[Mapping[str, object]],
    matrix: np.ndarray,
    player_index: Mapping[str, int],
    source_lineage: Mapping[str, object],
) -> dict[str, object]:
    world_count = int(matrix.shape[1])
    maxima: np.ndarray | None = None
    available = {threshold: 0 for threshold in DIAGNOSTIC_THRESHOLDS_MILLI}
    event_counts = {threshold: 0 for threshold in DIAGNOSTIC_THRESHOLDS_MILLI}
    score_digest = hashlib.sha256()
    header = _canonical(
        {
            "encoding": "roster-major-little-endian-int64-milli-dk/v1",
            "population_id": population_id,
            "lineup_ids": [row["lineup_id"] for row in rosters],
            "shape": [len(rosters), world_count],
            "source_lineage": source_lineage,
        },
        label="population score matrix header",
    )
    score_digest.update(len(header).to_bytes(8, "big"))
    score_digest.update(header)
    normalized_rosters: list[dict[str, object]] = []
    for row in rosters:
        roster = list(_sequence(row.get("roster_player_ids"), label="population roster"))
        lineup_id = _nonempty(row.get("lineup_id"), label="population lineup ID")
        roster_sha = _sha256(row.get("roster_sha256"), label="population roster SHA-256")
        if roster_sha != _sha(roster, label="population roster"):
            _fail("population roster identity differs")
        scores = _score_roster(roster, matrix=matrix, player_index=player_index)
        score_digest.update(memoryview(scores).cast("B"))
        maxima = scores.copy() if maxima is None else np.maximum(maxima, scores)
        for threshold in DIAGNOSTIC_THRESHOLDS_MILLI:
            hits = scores >= threshold
            count = int(np.count_nonzero(hits))
            event_counts[threshold] += count
            available[threshold] += int(count > 0)
        normalized_rosters.append(
            {
                "lineup_id": lineup_id,
                "roster_player_ids": roster,
                "roster_sha256": roster_sha,
                "fit_world_score_vector_sha256": _score_vector_sha256(
                    scores, label=f"{population_id}:{lineup_id}:fit-world-scores"
                ),
            }
        )
    threshold_rows: list[dict[str, object]] = []
    for threshold in DIAGNOSTIC_THRESHOLDS_MILLI:
        oracle_hits = (
            0 if maxima is None else int(np.count_nonzero(maxima >= threshold))
        )
        threshold_rows.append(
            {
                "threshold_milli_dk": threshold,
                "available_lineup_count": available[threshold],
                "availability_denominator_lineup_count": len(rosters),
                "lineup_world_hit_count": event_counts[threshold],
                "lineup_world_density_denominator": len(rosters) * world_count,
                "oracle_world_hit_count": oracle_hits,
                "oracle_world_count": world_count,
            }
        )
    return {
        "population_id": population_id,
        "diagnostic_scope": "simulated-permitted-fit-worlds-only",
        "source_lineage": dict(source_lineage),
        "population_lineup_count": len(rosters),
        "population_rosters": normalized_rosters,
        "population_rosters_sha256": _sha(
            normalized_rosters, label=f"{population_id} roster records"
        ),
        "fit_world_count": world_count,
        "lineup_score_matrix_sha256": score_digest.hexdigest(),
        "oracle_world_max_vector_sha256": (
            None
            if maxima is None
            else _score_vector_sha256(
                maxima, label=f"{population_id}:fit-world-oracle-maxima"
            )
        ),
        "oracle_world_max_sum_milli_dk": (
            None if maxima is None else int(maxima.sum(dtype=np.int64))
        ),
        "oracle_maximum_score_milli_dk": (
            None if maxima is None else int(maxima.max())
        ),
        "threshold_diagnostics": threshold_rows,
        "thresholds_sha256": _sha(
            threshold_rows, label=f"{population_id} threshold diagnostics"
        ),
        "uses_heldout_scores": False,
        "uses_realized_outcomes": False,
    }


def run_hard230_outer_optimizer_v1(
    *,
    slate_id: str,
    candidate_origin_id: str,
    heldout_block: str | None,
    worlds_per_block: int,
    source_member_identity: Mapping[str, object],
    score_block_identities: Sequence[Mapping[str, object]],
    player_registry: Sequence[Mapping[str, object]],
    score_matrix: np.ndarray,
    score_matrix_identity: Mapping[str, object],
    ordered_generator_world_indices: Sequence[int],
    paired_control: Mapping[str, object],
    optimizer_authority: Mapping[str, object],
    evidence_publisher: ExactJsonPublisher,
    execution_mode: str = RELEASE_EXECUTION_MODE,
    require_production_width: bool = True,
    solver_callback: SolverCallback = legal.default_cbc_solver,
) -> Hard230OuterOptimizerResult:
    """Solve and replay one hard-230 population cell without reading outcomes.

    Release mode validates the canonical CBC proof emitted by every solve.
    ``test-fixture`` mode exists only for bounded offline shape tests; its outer
    receipt states that proof validation was bypassed and grants no authority.
    """
    mode = _execution_mode(execution_mode)
    slate = _nonempty(slate_id, label="slate ID")
    context = _preflight_source(
        candidate_origin_id=candidate_origin_id,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        source_member_identity=source_member_identity,
        score_block_identities=score_block_identities,
        player_registry=player_registry,
        score_matrix=score_matrix,
        score_matrix_identity=score_matrix_identity,
        ordered_generator_world_indices=ordered_generator_world_indices,
        paired_control=paired_control,
        require_production_width=require_production_width,
    )
    profile = legal.frozen_policy_profiles()[0]
    if profile.parameter_set_id != INCUMBENT_PROFILE_ID:
        _fail("frozen profile zero is no longer the incumbent legal optimizer")
    authority = _optimizer_authority(
        optimizer_authority,
        incumbent_profile_sha256=profile.parameter_set_sha256,
    )
    authority_sha = _sha(authority, label="optimizer authority")
    config_body = {
        "schema_version": "hard-230-outer-generator-configuration/v1",
        "strategy_id": hard.HARD230_STRATEGY_ID,
        "generator_law_id": hard.HARD230_GENERATOR_LAW_ID,
        "slate_id": slate,
        "candidate_origin_id": context["origin"],
        "fit_scope_id": context["fit_scope_id"],
        "heldout_block": heldout_block,
        "training_blocks": list(context["training_blocks"]),
        "source_lineage": context["lineage"],
        "ordered_world_indices_sha256": _sha(
            list(context["world_order"]), label="ordered generator worlds"
        ),
        "paired_target_retained_count": context["target"],
        "computed_solver_call_ceiling": context["computed_ceiling"],
        "effective_solver_call_ceiling": context["effective_ceiling"],
        "incumbent_profile": profile.as_payload(),
        "optimizer_authority_sha256": authority_sha,
        "retention_threshold_milli_dk": hard.HARD230_THRESHOLD_MILLI,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    configuration_sha = _sha(config_body, label="generator configuration")
    stream_id = (
        f"hard230-{slate}-{context['fit_scope_id']}-{context['origin']}-"
        f"{configuration_sha[:20]}"
    )

    raw_occurrences: list[dict[str, object]] = []
    control_occurrences: list[dict[str, object]] = []
    proof_objects: list[dict[str, object]] = []
    seen_legal_rosters: set[str] = set()
    score_blind_rosters: list[dict[str, object]] = []
    hard_rosters: list[dict[str, object]] = []
    player_index = context["player_index"]
    matrix = score_matrix
    origin_offset = int(context["origin_block_ordinal"]) * worlds_per_block

    for position in range(int(context["effective_ceiling"])):
        world_index = int(context["world_order"][position])
        objective_milli = matrix[:, origin_offset + world_index]
        objective_micro = tuple(
            int(value) * MILLI_TO_MICRO for value in objective_milli
        )
        model = legal.build_fresh_legal_model(
            context["players"],
            profile,
            objective_micro,
            construction_serial=position,
            model_name=f"hard230_{slate}_{context['fit_scope_id']}_{context['origin']}_{position}",
        )
        request = legal.SolveRequest(
            variant_ordinal=0,
            parameter_set_id=profile.parameter_set_id,
            visit_ordinal=position,
            world=rw.WorldId(str(context["origin"]), world_index),
            objective_micro=objective_micro,
            timeout_seconds=legal.SOLVER_TIMEOUT_SECONDS,
            model=model,
        )
        raw_outcome = solver_callback(request)
        outcome = legal._normalize_solver_outcome(  # exact incumbent replay seam
            raw_outcome, request=request, profile=profile
        )
        if mode == RELEASE_EXECUTION_MODE:
            try:
                legal._validate_authoritative_solver_proof(
                    outcome,
                    solver_authority_sha256=str(authority["solver_authority_sha256"]),
                )
            except legal.CorpusLegalFeasibilityError as exc:
                raise Hard230OuterOptimizerAdapterError(
                    f"solver proof[{position}] is not authoritative: {exc}"
                ) from exc
        status = (
            "optimal"
            if outcome.status == legal.SolverStatus.OPTIMAL
            else "infeasible"
            if outcome.status == legal.SolverStatus.INFEASIBLE
            else "error"
        )
        roster = None if outcome.roster is None else list(outcome.roster)
        if status == "optimal" and roster is None:
            _fail(f"optimal solver occurrence[{position}] lacks a roster")
        solver_input = _solver_input(
            stream_id=stream_id,
            generator_configuration_sha256=configuration_sha,
            candidate_origin_id=str(context["origin"]),
            position=position,
            world_index=world_index,
            source_lineage=context["lineage"],
        )
        solver_output = {"solver_status": status, "roster_player_ids": roster}
        solver_evidence = {
            "schema_version": OUTER_SOLVER_EVIDENCE_SCHEMA,
            "execution_mode": mode,
            "optimizer_authority": authority,
            "optimizer_authority_sha256": authority_sha,
            "solver_input": solver_input,
            "solver_input_sha256": _sha(solver_input, label="solver input"),
            "solver_output": solver_output,
            "solver_output_sha256": _sha(solver_output, label="solver output"),
            "raw_solver_status": outcome.status.value,
            "primary_optimum_micro": outcome.primary_optimum_micro,
            "secondary_rank_sum": outcome.secondary_rank_sum,
            "lexicographic_radix": outcome.lexicographic_radix,
            "combined_optimum": outcome.combined_optimum,
            "canonical_solver_proof": _solver_proof_payload(outcome),
            "authoritative_solver_proof_validated": mode == RELEASE_EXECUTION_MODE,
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
        }
        solver_key = f"{stream_id}/solver-{position:05d}"
        solver_object, _solver_payload = _publish(
            evidence_publisher,
            role="hard230-solver-proof",
            deterministic_key=solver_key,
            body=solver_evidence,
        )
        proof_objects.append(solver_object)
        solver_proof_identity = {
            "proof_id": f"hard230-solver-{_sha(solver_evidence, label='solver evidence')[:24]}",
            "proof_kind": "incumbent-world-optimum-solver-result-v1",
            "implementation_sha256": authority["solver_implementation_sha256"],
            "input_sha256": solver_evidence["solver_input_sha256"],
            "output_sha256": solver_evidence["solver_output_sha256"],
            "proof_object_identity": solver_object,
        }

        roster_sha: str | None = None
        lineup_id: str | None = None
        legality_proof_identity: dict[str, object] | None = None
        legality_object: dict[str, object] | None = None
        is_new_legal = False
        if roster is not None:
            try:
                audited = legal.audit_dk_classic(context["players"], roster)
                legal._audit_profile_compliance(context["players"], audited, profile)
            except legal.CorpusLegalFeasibilityError as exc:
                raise Hard230OuterOptimizerAdapterError(
                    f"optimizer returned an illegal occurrence[{position}]: {exc}"
                ) from exc
            roster = list(audited)
            roster_sha = _sha(roster, label="generated roster")
            lineup_id = f"hard230-roster-{roster_sha}"
            legality_input = {
                "legality_audit_law_id": hard.LEGALITY_AUDIT_LAW_ID,
                "roster_player_ids": roster,
                "player_registry_sha256": context["lineage"]["player_registry_sha256"],
            }
            legality_output = {"legality_passed": True}
            legality_evidence = {
                "schema_version": OUTER_LEGALITY_EVIDENCE_SCHEMA,
                "execution_mode": mode,
                "optimizer_authority_sha256": authority_sha,
                "legality_input": legality_input,
                "legality_input_sha256": _sha(
                    legality_input, label="legality input"
                ),
                "legality_output": legality_output,
                "legality_output_sha256": _sha(
                    legality_output, label="legality output"
                ),
                "uses_realized_outcomes": False,
            }
            legality_key = f"{stream_id}/legality-{position:05d}-{roster_sha[:16]}"
            legality_object, _legality_payload = _publish(
                evidence_publisher,
                role="hard230-legality-proof",
                deterministic_key=legality_key,
                body=legality_evidence,
            )
            proof_objects.append(legality_object)
            legality_proof_identity = {
                "proof_id": f"hard230-legality-{roster_sha[:24]}-{position:05d}",
                "proof_kind": "independent-classic-legality-audit-v1",
                "implementation_sha256": hard.LEGALITY_AUDIT_IMPLEMENTATION_SHA256,
                "input_sha256": legality_evidence["legality_input_sha256"],
                "output_sha256": legality_evidence["legality_output_sha256"],
                "proof_object_identity": legality_object,
            }
            if roster_sha not in seen_legal_rosters:
                seen_legal_rosters.add(roster_sha)
                is_new_legal = True
                roster_record = {
                    "lineup_id": lineup_id,
                    "roster_player_ids": roster,
                    "roster_sha256": roster_sha,
                    "first_occurrence_ordinal": position,
                }
                if len(score_blind_rosters) < int(context["target"]):
                    score_blind_rosters.append(roster_record)
                scores = _score_roster(
                    roster, matrix=matrix, player_index=player_index
                )
                if int(scores.max()) >= hard.HARD230_THRESHOLD_MILLI:
                    hard_rosters.append(roster_record)

        raw_occurrences.append(
            {
                "stream_position": position,
                "source_world_index": world_index,
                "solver_call_ordinal": position,
                "solver_status": status,
                "solver_proof_identity": solver_proof_identity,
                "roster_player_ids": roster,
                "legality_proof_identity": legality_proof_identity,
                "uses_realized_outcomes": False,
                "uses_atlas_world_ranking": False,
            }
        )
        control_occurrences.append(
            {
                "occurrence_ordinal": position,
                "solver_status": status,
                "lineup_id": lineup_id,
                "roster_player_ids": roster,
                "roster_sha256": roster_sha,
                "legality_passed": True if roster is not None else None,
                "solver_proof_identity": solver_object,
                "legality_proof_identity": legality_object,
                "new_unique_legal_roster": is_new_legal,
            }
        )
        if len(hard_rosters) == int(context["target"]):
            break

    hard_target_reached = len(hard_rosters) == int(context["target"])
    termination_reason = (
        "hard230-paired-target-reached"
        if hard_target_reached
        else "frozen-effective-ceiling-exhausted-with-shortfall"
    )
    stream_body = {
        "schema_version": OUTER_STREAM_SCHEMA,
        "stream_id": stream_id,
        "execution_mode": mode,
        "strategy_id": hard.HARD230_STRATEGY_ID,
        "generator_law_id": hard.HARD230_GENERATOR_LAW_ID,
        "slate_id": slate,
        "candidate_origin_id": context["origin"],
        "fit_scope_id": context["fit_scope_id"],
        "source_lineage": context["lineage"],
        "generator_configuration": config_body,
        "generator_configuration_sha256": configuration_sha,
        "optimizer_authority": authority,
        "optimizer_authority_sha256": authority_sha,
        "source_stream_world_count": worlds_per_block,
        "computed_solver_call_ceiling": context["computed_ceiling"],
        "effective_solver_call_ceiling": context["effective_ceiling"],
        "actual_solver_call_count": len(raw_occurrences),
        "ordered_world_indices_sha256": _sha(
            list(context["world_order"]), label="ordered generator worlds"
        ),
        "occurrence_inputs_sha256": _ordered_records_sha256(
            raw_occurrences, label="generator occurrence inputs"
        ),
        "control_occurrence_ledger_sha256": _sha(
            control_occurrences, label="control occurrence ledger"
        ),
        "termination_reason": termination_reason,
        "hard230_retained_count": len(hard_rosters),
        "hard230_shortfall": int(context["target"]) - len(hard_rosters),
        "score_blind_prefix_retained_count": len(score_blind_rosters),
        "solver_stream_shared_between_populations": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    stream_object, _stream_payload = _publish(
        evidence_publisher,
        role="hard230-generator-stream",
        deterministic_key=f"{stream_id}/stream-manifest",
        body=stream_body,
    )
    generator_stream_identity = {
        "stream_id": stream_id,
        "candidate_origin_id": context["origin"],
        "generator_law_id": hard.HARD230_GENERATOR_LAW_ID,
        "generator_configuration_sha256": configuration_sha,
        "solver_implementation_sha256": authority["solver_implementation_sha256"],
        "source_member_sha256": context["lineage"]["source_member_sha256"],
        "score_block_identities_sha256": context["lineage"][
            "score_block_identities_sha256"
        ],
        "player_registry_sha256": context["lineage"]["player_registry_sha256"],
        "score_matrix_sha256": context["lineage"]["score_matrix_sha256"],
        "ordered_world_indices_sha256": _sha(
            list(context["world_order"]), label="ordered generator worlds"
        ),
        "ordered_occurrence_inputs_sha256": _ordered_records_sha256(
            raw_occurrences, label="generator occurrence inputs"
        ),
        "occurrence_count": len(raw_occurrences),
        "stream_manifest_identity": stream_object,
    }
    generation_receipt = hard.build_hard230_generation_replenishment_v1(
        candidate_origin_id=str(context["origin"]),
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        source_member_identity=source_member_identity,
        score_block_identities=score_block_identities,
        player_registry=player_registry,
        score_matrix=score_matrix,
        score_matrix_identity=score_matrix_identity,
        generator_stream_identity=generator_stream_identity,
        ordered_generator_world_indices=ordered_generator_world_indices,
        paired_control=paired_control,
        occurrences=raw_occurrences,
        require_production_width=require_production_width,
    )
    if int(generation_receipt["solver_call_count"]) != len(raw_occurrences):
        _fail("pure hard-230 replay changed the exact solver-call accounting")

    control_population = _population_diagnostics(
        population_id=COMPARATOR_POPULATION_ID,
        rosters=score_blind_rosters,
        matrix=matrix,
        player_index=player_index,
        source_lineage=context["lineage"],
    )
    hard_population = _population_diagnostics(
        population_id="G-hard230-generate-replenish",
        rosters=hard_rosters,
        matrix=matrix,
        player_index=player_index,
        source_lineage=context["lineage"],
    )
    outer_body = {
        "schema_version": OUTER_RECEIPT_SCHEMA,
        "strategy_id": hard.HARD230_STRATEGY_ID,
        "mechanism_class": "population-generation-with-deterministic-replenishment",
        "is_selector": False,
        "is_strict230_admission_filter": False,
        "is_legacy_t230_panel": False,
        "execution_mode": mode,
        "slate_id": slate,
        "candidate_origin_id": context["origin"],
        "fit_scope_id": context["fit_scope_id"],
        "heldout_block": heldout_block,
        "training_blocks": list(context["training_blocks"]),
        "source_lineage": context["lineage"],
        "optimizer_authority": authority,
        "optimizer_authority_sha256": authority_sha,
        "generator_stream_identity": generator_stream_identity,
        "paired_control_receipt_identity": context["paired_control_identity"],
        "paired_target_retained_count": context["target"],
        "computed_solver_call_ceiling": context["computed_ceiling"],
        "effective_solver_call_ceiling": context["effective_ceiling"],
        "actual_shared_solver_call_count": len(raw_occurrences),
        "control_observed_solver_call_count": len(raw_occurrences),
        "challenger_observed_solver_call_count": len(raw_occurrences),
        "control_solver_call_budget": context["effective_ceiling"],
        "challenger_solver_call_budget": context["effective_ceiling"],
        "equal_solver_call_budget": True,
        "equal_observed_solver_call_count": True,
        "solver_occurrences_shared_not_reexecuted": True,
        "control_occurrence_ledger_sha256": _sha(
            control_occurrences, label="control occurrence ledger"
        ),
        "proof_object_identities_sha256": _sha(
            proof_objects, label="solver and legality proof object identities"
        ),
        "authoritative_solver_proofs_validated": mode == RELEASE_EXECUTION_MODE,
        "fixture_solver_proof_bypass": mode == FIXTURE_EXECUTION_MODE,
        "termination_reason": termination_reason,
        "hard230_exact_target_reached": hard_target_reached,
        "hard230_shortfall": int(context["target"]) - len(hard_rosters),
        "thresholds_milli_dk": list(DIAGNOSTIC_THRESHOLDS_MILLI),
        "score_blind_comparator_population": control_population,
        "hard230_population": hard_population,
        "hard230_generation_receipt_sha256": generation_receipt[
            "hard230_generation_receipt_sha256"
        ],
        "diagnostics_are_fit_world_only_not_heldout_effects": True,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    outer_receipt = _self_hash(body=outer_body, field="outer_receipt_sha256")
    return Hard230OuterOptimizerResult(
        outer_receipt=outer_receipt,
        hard230_generation_receipt=generation_receipt,
        generator_stream_identity=generator_stream_identity,
        occurrences=tuple(raw_occurrences),
    )


def validate_hard230_outer_receipt_v1(value: object) -> dict[str, object]:
    """Validate canonical self-identity and the non-authoritative boundary."""
    item = dict(_mapping(value, label="hard-230 outer receipt"))
    retained_sha = _sha256(
        item.pop("outer_receipt_sha256", None), label="outer receipt SHA-256"
    )
    if retained_sha != _sha(item, label="hard-230 outer receipt body"):
        _fail("hard-230 outer receipt self-hash differs")
    if item.get("schema_version") != OUTER_RECEIPT_SCHEMA:
        _fail("hard-230 outer receipt schema differs")
    if any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS):
        _fail("hard-230 outer receipt claims forbidden authority")
    if (
        item.get("equal_solver_call_budget") is not True
        or item.get("control_solver_call_budget")
        != item.get("challenger_solver_call_budget")
        or item.get("equal_observed_solver_call_count") is not True
        or item.get("control_observed_solver_call_count")
        != item.get("challenger_observed_solver_call_count")
        or item.get("control_observed_solver_call_count")
        != item.get("actual_shared_solver_call_count")
        or item.get("solver_occurrences_shared_not_reexecuted") is not True
    ):
        _fail("hard-230 outer receipt does not bind equal shared solver work")
    return {**item, "outer_receipt_sha256": retained_sha}


__all__ = [
    "COMPARATOR_POPULATION_ID",
    "DIAGNOSTIC_THRESHOLDS_MILLI",
    "FIXTURE_EXECUTION_MODE",
    "Hard230OuterOptimizerAdapterError",
    "Hard230OuterOptimizerResult",
    "OUTER_AUTHORITY_SCHEMA",
    "OUTER_RECEIPT_SCHEMA",
    "RELEASE_EXECUTION_MODE",
    "run_hard230_outer_optimizer_v1",
    "validate_hard230_outer_receipt_v1",
]
