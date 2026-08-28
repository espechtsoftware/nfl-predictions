"""Native, outcome-blind hard-230 replenishing population successor.

This contract replaces the incompatible v1 stop-at-control-target stream law.
One ordered incumbent-optimizer stream is solved exactly once.  The first P0-
sized prefix of unique legal rosters is the score-blind comparator, while the
challenger retains only unique legal rosters with an inclusive 230-DK hit in a
permitted fit world and keeps consuming the same stream until its target or
the precommitted ceiling.  The two populations therefore have identical
solver budgets and identical observed solver calls without counterfactual
re-execution.

The module is deliberately transport-free.  Exact P0-target, world-order and
runtime authorities are generation-pinned inputs.  Solver/legality evidence
is handed to a caller-owned recorder; the companion process module shards and
publishes those records create-once.  No realized, heldout-score, field,
ownership, rank, payout, selector, promotion or production-policy input is
accepted here.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Final, Protocol

import numpy as np

from nfl_dfs.research import corpus_extreme_tail_generation_additions as source
from nfl_dfs.research import corpus_legal_feasibility as legal
from nfl_dfs.research import residual_world_columns as rw


CONTRACT_ID: Final = "20260828-hard230-population-successor-v1"
STRATEGY_ID: Final = "hard-230-generate-replenish-successor-v1"
GENERATOR_LAW_ID: Final = (
    "incumbent-shared-world-stream-control-prefix-hard230-replenishment-v2"
)
P0_TARGET_SCHEMA: Final = "hard230-p0-target-authority/v1"
WORLD_PERMUTATION_SCHEMA: Final = "hard230-world-permutation-authority/v1"
RUNTIME_AUTHORITY_SCHEMA: Final = "hard230-population-runtime-authority/v1"
EVIDENCE_RECORD_SCHEMA: Final = "hard230-population-evidence-record/v1"
RECEIPT_SCHEMA: Final = "hard230-population-successor-receipt/v1"

P0_POPULATION_ID: Final = "P0-incumbent-native"
CONTROL_POPULATION_ID: Final = "P0-sized-shared-stream-score-blind-prefix-v1"
CHALLENGER_POPULATION_ID: Final = "G-hard230-generate-replenish-successor-v1"
RELEASE_EXECUTION_MODE: Final = "release"
FIXTURE_EXECUTION_MODE: Final = "test-fixture"
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
PRODUCTION_WORLDS_PER_BLOCK: Final = 10_000
MIN_PLAYER_COUNT: Final = 9
MAX_PLAYER_COUNT: Final = 1_024
MIN_GAME_COUNT: Final = 2
MAX_GAME_COUNT: Final = 64
MAX_ABS_PLAYER_SCORE_MILLI: Final = 1_000_000
THRESHOLD_MILLI_DK: Final = 230_000
DIAGNOSTIC_THRESHOLDS_MILLI_DK: Final = (200_000, 220_000, 230_000)
MINIMUM_SOLVER_CALL_CEILING: Final = 200
SOLVER_CALLS_PER_TARGET: Final = 20
MAXIMUM_SOLVER_CALL_CEILING: Final = 10_000
MILLI_TO_MICRO: Final = 1_000

_FALSE_AUTHORITY_FIELDS: Final = (
    "uses_realized_outcomes",
    "uses_heldout_scores",
    "historical_scoring_licensed",
    "selector_authority",
    "publication_authority",
    "promotion_authority",
    "decision_authority",
    "production_change_licensed",
    "graph_mutation_licensed",
)


class Hard230PopulationSuccessorV1Error(ValueError):
    """A successor authority, source, solver proof or receipt failed closed."""


class EvidenceRecorder(Protocol):
    """Capture exact canonical evidence bytes under one deterministic key."""

    def __call__(
        self, *, role: str, deterministic_key: str, payload: bytes
    ) -> None: ...


SolverCallback = Callable[[legal.SolveRequest], legal.SolveOutcome]


@dataclass(frozen=True, slots=True)
class Hard230PopulationSuccessorResult:
    receipt: Mapping[str, object]
    occurrences: tuple[Mapping[str, object], ...]
    evidence_records: tuple[Mapping[str, object], ...]


def _fail(message: str) -> None:
    raise Hard230PopulationSuccessorV1Error(message)


def _canonical(value: object, *, label: str) -> bytes:
    try:
        return legal.canonical_json_bytes(value)
    except (TypeError, ValueError, legal.CorpusLegalFeasibilityError) as exc:
        raise Hard230PopulationSuccessorV1Error(
            f"{label} is not finite canonical JSON"
        ) from exc


def _sha(value: object, *, label: str) -> str:
    return hashlib.sha256(_canonical(value, label=label)).hexdigest()


def _self_hash(body: Mapping[str, object], field: str) -> dict[str, object]:
    result = dict(body)
    if field in result:
        _fail(f"{field} cannot already be present")
    result[field] = _sha(result, label=field)
    return result


def _mapping(value: object, *, label: str) -> dict[str, object]:
    if not isinstance(value, Mapping) or any(type(key) is not str for key in value):
        _fail(f"{label} must be one string-keyed object")
    return dict(value)


def _sequence(value: object, *, label: str) -> list[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        _fail(f"{label} must be one array")
    return list(value)


def _nonempty(value: object, *, label: str) -> str:
    if type(value) is not str or not value:
        _fail(f"{label} must be one nonempty exact string")
    return value


def _integer(value: object, *, label: str, minimum: int = 0) -> int:
    if type(value) is not int or value < minimum:
        _fail(f"{label} must be one exact integer >= {minimum}")
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
    value: object, *, label: str, payload: bytes | None = None
) -> dict[str, object]:
    item = _mapping(value, label=label)
    if set(item) != {"uri", "generation", "sha256", "bytes"}:
        _fail(f"{label} fields differ")
    uri = _nonempty(item.get("uri"), label=f"{label} URI")
    generation = _nonempty(item.get("generation"), label=f"{label} generation")
    byte_count = _integer(item.get("bytes"), label=f"{label} bytes", minimum=1)
    digest = _sha256(item.get("sha256"), label=f"{label} SHA-256")
    if not uri.startswith("gs://") or not generation.isdigit():
        _fail(f"{label} must be one generation-pinned GCS object")
    if payload is not None and (
        digest != hashlib.sha256(payload).hexdigest() or byte_count != len(payload)
    ):
        _fail(f"{label} differs from the exact canonical authority bytes")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": byte_count,
    }


def bind_authority_identity_v1(
    authority: Mapping[str, object], identity: Mapping[str, object], *, label: str
) -> dict[str, object]:
    return _object_identity(
        identity,
        label=f"{label} identity",
        payload=_canonical(authority, label=label),
    )


def _false_authorities() -> dict[str, bool]:
    return {field: False for field in _FALSE_AUTHORITY_FIELDS}


def _scope(heldout_block: str | None) -> tuple[str, tuple[str, ...]]:
    if heldout_block is None:
        return "all-block-final-fit", WORLD_BLOCKS
    if heldout_block not in WORLD_BLOCKS:
        _fail("heldout_block must be null or one exact R0..R4 block")
    return (
        f"holdout-{heldout_block}",
        tuple(block for block in WORLD_BLOCKS if block != heldout_block),
    )


def _canonical_lineup_ids(value: object, *, label: str) -> list[str]:
    rows = _sequence(value, label=label)
    normalized = [_nonempty(row, label=f"{label} member") for row in rows]
    if not normalized or len(normalized) > MAXIMUM_SOLVER_CALL_CEILING:
        _fail(f"{label} count is outside 1..10,000")
    if len(set(normalized)) != len(normalized):
        _fail(f"{label} must be unique")
    return normalized


def build_p0_target_authority_v1(
    *,
    slate_id: str,
    candidate_origin_id: str,
    heldout_block: str | None,
    source_lineage: Mapping[str, object],
    retained_lineup_ids: Sequence[str],
    population_receipt_identity: Mapping[str, object],
) -> dict[str, object]:
    """Build the exact pre-outcome P0 population-size target authority."""
    fit_scope_id, training_blocks = _scope(heldout_block)
    origin = _nonempty(candidate_origin_id, label="candidate origin")
    if origin not in WORLD_BLOCKS or origin not in training_blocks:
        _fail("candidate origin must be one non-heldout K5 block")
    lineup_ids = _canonical_lineup_ids(
        retained_lineup_ids, label="P0 retained lineup IDs"
    )
    lineage = _mapping(source_lineage, label="P0 source lineage")
    body = {
        "schema_version": P0_TARGET_SCHEMA,
        "contract_id": CONTRACT_ID,
        "slate_id": _nonempty(slate_id, label="slate ID"),
        "candidate_origin_id": origin,
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "population_id": P0_POPULATION_ID,
        "retained_count": len(lineup_ids),
        "retained_lineup_ids": lineup_ids,
        "retained_lineup_ids_sha256": _sha(
            lineup_ids, label="P0 retained lineup IDs"
        ),
        "source_lineage": lineage,
        "source_lineage_sha256": _sha(lineage, label="P0 source lineage"),
        "population_receipt_identity": _object_identity(
            population_receipt_identity, label="P0 population receipt"
        ),
        "target_is_population_size_only": True,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    return _self_hash(body, "p0_target_authority_sha256")


def validate_p0_target_authority_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="P0 target authority")
    retained = _sha256(
        item.pop("p0_target_authority_sha256", None),
        label="P0 target authority SHA-256",
    )
    if retained != _sha(item, label="P0 target authority body"):
        _fail("P0 target authority self-hash differs")
    expected = build_p0_target_authority_v1(
        slate_id=item.get("slate_id"),
        candidate_origin_id=item.get("candidate_origin_id"),
        heldout_block=item.get("heldout_block"),
        source_lineage=item.get("source_lineage"),
        retained_lineup_ids=item.get("retained_lineup_ids"),
        population_receipt_identity=item.get("population_receipt_identity"),
    )
    if _canonical(expected, label="expected P0 target") != _canonical(
        {**item, "p0_target_authority_sha256": retained}, label="P0 target"
    ):
        _fail("P0 target authority fields differ")
    return expected


def build_world_permutation_authority_v1(
    *,
    slate_id: str,
    candidate_origin_id: str,
    heldout_block: str | None,
    worlds_per_block: int,
    ordered_world_indices: Sequence[int],
    source_lineage: Mapping[str, object],
    derivation_identity: Mapping[str, object],
) -> dict[str, object]:
    """Bind the entire score-blind world order, not merely an informal seed."""
    fit_scope_id, training_blocks = _scope(heldout_block)
    origin = _nonempty(candidate_origin_id, label="candidate origin")
    width = _integer(worlds_per_block, label="worlds per block", minimum=1)
    if width > PRODUCTION_WORLDS_PER_BLOCK:
        _fail("world width exceeds 10,000")
    raw_order = _sequence(ordered_world_indices, label="world permutation")
    if any(type(value) is not int for value in raw_order):
        _fail("world permutation members must be exact integers")
    order = [int(value) for value in raw_order]
    if len(order) != width or sorted(order) != list(range(width)):
        _fail("world permutation must contain every source world exactly once")
    if origin not in WORLD_BLOCKS or origin not in training_blocks:
        _fail("candidate origin must be one non-heldout K5 block")
    lineage = _mapping(source_lineage, label="permutation source lineage")
    body = {
        "schema_version": WORLD_PERMUTATION_SCHEMA,
        "contract_id": CONTRACT_ID,
        "slate_id": _nonempty(slate_id, label="slate ID"),
        "candidate_origin_id": origin,
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "worlds_per_block": width,
        "ordered_world_indices": order,
        "ordered_world_indices_sha256": _sha(
            order, label="world permutation"
        ),
        "permutation_law_id": "precommitted-score-blind-full-permutation-v1",
        "derivation_identity": _object_identity(
            derivation_identity, label="world permutation derivation"
        ),
        "source_lineage": lineage,
        "source_lineage_sha256": _sha(lineage, label="permutation lineage"),
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    return _self_hash(body, "world_permutation_authority_sha256")


def validate_world_permutation_authority_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="world permutation authority")
    retained = _sha256(
        item.pop("world_permutation_authority_sha256", None),
        label="world permutation authority SHA-256",
    )
    if retained != _sha(item, label="world permutation authority body"):
        _fail("world permutation authority self-hash differs")
    expected = build_world_permutation_authority_v1(
        slate_id=item.get("slate_id"),
        candidate_origin_id=item.get("candidate_origin_id"),
        heldout_block=item.get("heldout_block"),
        worlds_per_block=item.get("worlds_per_block"),
        ordered_world_indices=item.get("ordered_world_indices"),
        source_lineage=item.get("source_lineage"),
        derivation_identity=item.get("derivation_identity"),
    )
    if _canonical(expected, label="expected world permutation") != _canonical(
        {**item, "world_permutation_authority_sha256": retained},
        label="world permutation authority",
    ):
        _fail("world permutation authority fields differ")
    return expected


def build_runtime_authority_v1(
    *,
    slate_id: str,
    candidate_origin_id: str,
    heldout_block: str | None,
    source_commit_sha: str,
    immutable_image_digest: str,
    contract_source_sha256: str,
    process_source_sha256: str,
    solver_implementation_sha256: str,
    solver_authority_sha256: str,
    optimizer_source_identity: Mapping[str, object],
    terminal_build_receipt_identity: Mapping[str, object],
    task_manifest_identity: Mapping[str, object],
    launch_intent_identity: Mapping[str, object],
    process_budget_identity: Mapping[str, object],
    p0_target_authority_identity: Mapping[str, object],
    world_permutation_authority_identity: Mapping[str, object],
) -> dict[str, object]:
    fit_scope_id, training_blocks = _scope(heldout_block)
    origin = _nonempty(candidate_origin_id, label="candidate origin")
    if origin not in WORLD_BLOCKS or origin not in training_blocks:
        _fail("candidate origin must be one non-heldout K5 block")
    image = _nonempty(immutable_image_digest, label="immutable image digest")
    if not image.startswith("sha256:") or len(image) != 71:
        _fail("immutable image digest must be one sha256 registry digest")
    _sha256(image[7:], label="immutable image digest body")
    profile = legal.frozen_policy_profiles()[0]
    if profile.parameter_set_id != "incumbent":
        _fail("frozen profile zero is no longer incumbent")
    contract_sha = _sha256(
        contract_source_sha256, label="contract source SHA-256"
    )
    solver_sha = _sha256(
        solver_implementation_sha256, label="solver implementation SHA-256"
    )
    if contract_sha != hashlib.sha256(Path(__file__).read_bytes()).hexdigest():
        _fail("contract source SHA-256 differs from the executing module")
    if solver_sha != hashlib.sha256(Path(legal.__file__).read_bytes()).hexdigest():
        _fail("solver implementation SHA-256 differs from the executing module")
    body = {
        "schema_version": RUNTIME_AUTHORITY_SCHEMA,
        "contract_id": CONTRACT_ID,
        "slate_id": _nonempty(slate_id, label="slate ID"),
        "candidate_origin_id": origin,
        "fit_scope_id": fit_scope_id,
        "heldout_block": heldout_block,
        "training_blocks": list(training_blocks),
        "source_commit_sha": _git_sha(source_commit_sha, label="source commit"),
        "immutable_image_digest": image,
        "contract_source_sha256": contract_sha,
        "process_source_sha256": _sha256(
            process_source_sha256, label="process source SHA-256"
        ),
        "solver_implementation_sha256": solver_sha,
        "solver_authority_sha256": _sha256(
            solver_authority_sha256, label="solver authority SHA-256"
        ),
        "incumbent_profile_sha256": profile.parameter_set_sha256,
        "optimizer_source_identity": _object_identity(
            optimizer_source_identity, label="optimizer source"
        ),
        "terminal_build_receipt_identity": _object_identity(
            terminal_build_receipt_identity, label="terminal build receipt"
        ),
        "task_manifest_identity": _object_identity(
            task_manifest_identity, label="task manifest"
        ),
        "launch_intent_identity": _object_identity(
            launch_intent_identity, label="launch intent"
        ),
        "process_budget_identity": _object_identity(
            process_budget_identity, label="process budget"
        ),
        "p0_target_authority_identity": _object_identity(
            p0_target_authority_identity, label="P0 target authority"
        ),
        "world_permutation_authority_identity": _object_identity(
            world_permutation_authority_identity,
            label="world permutation authority",
        ),
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    return _self_hash(body, "runtime_authority_sha256")


def validate_runtime_authority_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="runtime authority")
    retained = _sha256(
        item.pop("runtime_authority_sha256", None),
        label="runtime authority SHA-256",
    )
    if retained != _sha(item, label="runtime authority body"):
        _fail("runtime authority self-hash differs")
    expected = build_runtime_authority_v1(
        slate_id=item.get("slate_id"),
        candidate_origin_id=item.get("candidate_origin_id"),
        heldout_block=item.get("heldout_block"),
        source_commit_sha=item.get("source_commit_sha"),
        immutable_image_digest=item.get("immutable_image_digest"),
        contract_source_sha256=item.get("contract_source_sha256"),
        process_source_sha256=item.get("process_source_sha256"),
        solver_implementation_sha256=item.get("solver_implementation_sha256"),
        solver_authority_sha256=item.get("solver_authority_sha256"),
        optimizer_source_identity=item.get("optimizer_source_identity"),
        terminal_build_receipt_identity=item.get("terminal_build_receipt_identity"),
        task_manifest_identity=item.get("task_manifest_identity"),
        launch_intent_identity=item.get("launch_intent_identity"),
        process_budget_identity=item.get("process_budget_identity"),
        p0_target_authority_identity=item.get("p0_target_authority_identity"),
        world_permutation_authority_identity=item.get(
            "world_permutation_authority_identity"
        ),
    )
    if _canonical(expected, label="expected runtime authority") != _canonical(
        {**item, "runtime_authority_sha256": retained}, label="runtime authority"
    ):
        _fail("runtime authority fields differ")
    return expected


def _player_registry_1024(
    value: object,
) -> tuple[list[dict[str, object]], tuple[rw.PlayerSpec, ...]]:
    rows = _sequence(value, label="player registry")
    if not MIN_PLAYER_COUNT <= len(rows) <= MAX_PLAYER_COUNT:
        _fail("player registry count is outside the successor 9..1,024 bound")
    normalized: list[dict[str, object]] = []
    specs: list[rw.PlayerSpec] = []
    for ordinal, raw in enumerate(rows):
        row = _mapping(raw, label=f"player registry[{ordinal}]")
        if set(row) != {"id", "pos", "team", "opp", "game_id", "salary"}:
            _fail(f"player registry[{ordinal}] fields differ")
        try:
            player = rw.PlayerSpec.from_mapping(row)
        except (KeyError, TypeError, ValueError, rw.ResidualWorldError) as exc:
            raise Hard230PopulationSuccessorV1Error(
                f"player registry[{ordinal}] is malformed"
            ) from exc
        specs.append(player)
        normalized.append(
            {
                "id": player.player_id,
                "pos": player.position,
                "team": player.team,
                "opp": player.opponent,
                "game_id": player.game_id,
                "salary": player.salary,
            }
        )
    player_ids = [str(row["id"]) for row in normalized]
    if player_ids != sorted(player_ids) or len(player_ids) != len(set(player_ids)):
        _fail("player registry must contain unique IDs in ascending order")
    game_count = len({str(row["game_id"]) for row in normalized})
    if not MIN_GAME_COUNT <= game_count <= MAX_GAME_COUNT:
        _fail("player-to-game membership is outside the 2..64-game bound")
    return normalized, tuple(specs)


def _prepare_source(
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
    require_production_width: bool,
) -> dict[str, object]:
    if type(require_production_width) is not bool:
        _fail("require_production_width must be an exact boolean")
    width = _integer(worlds_per_block, label="worlds per block", minimum=1)
    if width > PRODUCTION_WORLDS_PER_BLOCK or (
        require_production_width and width != PRODUCTION_WORLDS_PER_BLOCK
    ):
        _fail("production width must be exactly 10,000 worlds per block")
    fit_scope_id, training_blocks = _scope(heldout_block)
    origin = _nonempty(candidate_origin_id, label="candidate origin")
    if origin not in WORLD_BLOCKS or origin not in training_blocks:
        _fail("candidate origin must be one non-heldout K5 block")
    try:
        member = source._source_member_identity(source_member_identity)
        blocks = source._score_block_identities(
            score_block_identities,
            expected_block_ids=training_blocks,
            worlds_per_block=width,
            source_member_sha256=str(member["member_sha256"]),
        )
        players, specs = _player_registry_1024(player_registry)
        matrix = source._validate_matrix_primitive(
            score_matrix,
            expected_rows=len(players),
            expected_columns=len(training_blocks) * width,
        )
        matrix_identity = source._score_matrix_identity(
            score_matrix_identity,
            matrix=matrix,
            source_member=member,
            block_identities=blocks,
            player_registry=players,
        )
    except source.CorpusExtremeTailGenerationAdditionsError as exc:
        raise Hard230PopulationSuccessorV1Error(str(exc)) from exc
    if member["slate_id"] != slate_id:
        _fail("source member slate differs")
    block_sha = _sha(blocks, label="score block identities")
    player_sha = _sha(players, label="player registry")
    lineage = {
        "source_member_sha256": member["member_sha256"],
        "score_block_ids": list(training_blocks),
        "score_block_identities_sha256": block_sha,
        "player_registry_sha256": player_sha,
        "score_matrix_sha256": matrix_identity[
            "canonical_score_matrix_sha256"
        ],
        "matrix_derivation_proof_identity_sha256": _sha(
            matrix_identity["derivation_proof_identity"],
            label="matrix derivation proof identity",
        ),
    }
    return {
        "width": width,
        "fit_scope_id": fit_scope_id,
        "training_blocks": training_blocks,
        "origin": origin,
        "origin_ordinal": training_blocks.index(origin),
        "players": specs,
        "player_registry": players,
        "player_index": {
            str(row["id"]): ordinal for ordinal, row in enumerate(players)
        },
        "matrix": matrix,
        "matrix_identity": matrix_identity,
        "lineage": lineage,
    }


def _execution_mode(value: object) -> str:
    if value not in {RELEASE_EXECUTION_MODE, FIXTURE_EXECUTION_MODE}:
        _fail("execution mode must be exactly release or test-fixture")
    return str(value)


def _record_evidence(
    recorder: EvidenceRecorder,
    records: list[dict[str, object]],
    *,
    role: str,
    deterministic_key: str,
    body: Mapping[str, object],
) -> dict[str, object]:
    payload = _canonical(body, label=f"{role} evidence")
    try:
        recorder(role=role, deterministic_key=deterministic_key, payload=payload)
    except Exception as exc:
        raise Hard230PopulationSuccessorV1Error(
            f"evidence recorder failed for {role}"
        ) from exc
    record = {
        "schema_version": EVIDENCE_RECORD_SCHEMA,
        "record_ordinal": len(records),
        "role": role,
        "deterministic_key": deterministic_key,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "payload_bytes": len(payload),
    }
    record["record_id"] = (
        f"hard230-evidence-{record['record_ordinal']:05d}-"
        f"{record['payload_sha256'][:24]}"
    )
    records.append(record)
    return dict(record)


def _proof_payload(outcome: legal.SolveOutcome) -> object:
    if outcome.solver_proof is None:
        return None
    raw = outcome.solver_proof.canonical_payload
    if type(raw) is not bytes:
        _fail("solver proof payload must be exact canonical bytes")
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise Hard230PopulationSuccessorV1Error(
            "solver proof payload is not canonical JSON"
        ) from exc
    if _canonical(parsed, label="solver proof payload") != raw:
        _fail("solver proof payload bytes are not canonical JSON")
    return parsed


def _score_roster(
    roster: Sequence[str], *, matrix: np.ndarray, player_index: Mapping[str, int]
) -> np.ndarray:
    result = np.zeros(matrix.shape[1], dtype="<i8")
    for player_id in roster:
        result += matrix[player_index[player_id], :]
    return result


def _vector_sha256(vector: np.ndarray, *, label: str) -> str:
    array = np.ascontiguousarray(vector, dtype="<i8")
    digest = hashlib.sha256()
    header = _canonical(
        {
            "encoding": "little-endian-int64-vector/v1",
            "label": label,
            "length": int(array.shape[0]),
        },
        label=f"{label} header",
    )
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    digest.update(memoryview(array).cast("B"))
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
    available = {threshold: 0 for threshold in DIAGNOSTIC_THRESHOLDS_MILLI_DK}
    event_counts = {threshold: 0 for threshold in DIAGNOSTIC_THRESHOLDS_MILLI_DK}
    matrix_digest = hashlib.sha256()
    lineup_ids = [row["lineup_id"] for row in rosters]
    header = _canonical(
        {
            "encoding": "roster-major-little-endian-int64-milli-dk/v1",
            "population_id": population_id,
            "lineup_ids": lineup_ids,
            "shape": [len(rosters), world_count],
            "source_lineage": source_lineage,
        },
        label="population score matrix header",
    )
    matrix_digest.update(len(header).to_bytes(8, "big"))
    matrix_digest.update(header)
    normalized: list[dict[str, object]] = []
    for row in rosters:
        roster = [str(value) for value in row["roster_player_ids"]]
        score = _score_roster(roster, matrix=matrix, player_index=player_index)
        matrix_digest.update(memoryview(score).cast("B"))
        maxima = score.copy() if maxima is None else np.maximum(maxima, score)
        for threshold in DIAGNOSTIC_THRESHOLDS_MILLI_DK:
            hit_count = int(np.count_nonzero(score >= threshold))
            available[threshold] += int(hit_count > 0)
            event_counts[threshold] += hit_count
        normalized.append(
            {
                "lineup_id": row["lineup_id"],
                "roster_player_ids": roster,
                "roster_sha256": row["roster_sha256"],
                "first_occurrence_ordinal": row["first_occurrence_ordinal"],
                "fit_world_score_vector_sha256": _vector_sha256(
                    score, label=f"{population_id}:{row['lineup_id']}:fit"
                ),
            }
        )
    threshold_rows = []
    for threshold in DIAGNOSTIC_THRESHOLDS_MILLI_DK:
        threshold_rows.append(
            {
                "threshold_milli_dk": threshold,
                "available_lineup_count": available[threshold],
                "availability_denominator_lineup_count": len(rosters),
                "lineup_world_hit_count": event_counts[threshold],
                "lineup_world_density_denominator": len(rosters) * world_count,
                "oracle_world_hit_count": (
                    0
                    if maxima is None
                    else int(np.count_nonzero(maxima >= threshold))
                ),
                "oracle_world_count": world_count,
            }
        )
    return {
        "population_id": population_id,
        "diagnostic_scope": "simulated-permitted-fit-worlds-only",
        "population_lineup_count": len(rosters),
        "population_rosters": normalized,
        "population_rosters_sha256": _sha(
            normalized, label=f"{population_id} roster records"
        ),
        "fit_world_count": world_count,
        "lineup_score_matrix_sha256": matrix_digest.hexdigest(),
        "oracle_world_max_vector_sha256": (
            None
            if maxima is None
            else _vector_sha256(maxima, label=f"{population_id}:oracle")
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
        "source_lineage": dict(source_lineage),
        "uses_heldout_scores": False,
        "uses_realized_outcomes": False,
    }


def _ordered_records_sha256(rows: Sequence[object], *, label: str) -> str:
    digest = hashlib.sha256()
    header = _canonical(
        {"encoding": "length-prefixed-canonical-json-records/v1", "label": label},
        label=f"{label} header",
    )
    digest.update(len(header).to_bytes(8, "big"))
    digest.update(header)
    for row in rows:
        encoded = _canonical(row, label=f"{label} record")
        digest.update(len(encoded).to_bytes(8, "big"))
        digest.update(encoded)
    digest.update(len(rows).to_bytes(8, "big"))
    return digest.hexdigest()


def run_hard230_population_successor_v1(
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
    p0_target_authority: Mapping[str, object],
    p0_target_authority_identity: Mapping[str, object],
    world_permutation_authority: Mapping[str, object],
    world_permutation_authority_identity: Mapping[str, object],
    runtime_authority: Mapping[str, object],
    runtime_authority_identity: Mapping[str, object],
    evidence_recorder: EvidenceRecorder,
    execution_mode: str = RELEASE_EXECUTION_MODE,
    require_production_width: bool = True,
    solver_callback: SolverCallback = legal.default_cbc_solver,
) -> Hard230PopulationSuccessorResult:
    """Execute one native replenishing population cell on one shared stream."""
    mode = _execution_mode(execution_mode)
    slate = _nonempty(slate_id, label="slate ID")
    context = _prepare_source(
        slate_id=slate,
        candidate_origin_id=candidate_origin_id,
        heldout_block=heldout_block,
        worlds_per_block=worlds_per_block,
        source_member_identity=source_member_identity,
        score_block_identities=score_block_identities,
        player_registry=player_registry,
        score_matrix=score_matrix,
        score_matrix_identity=score_matrix_identity,
        require_production_width=require_production_width,
    )
    p0 = validate_p0_target_authority_v1(p0_target_authority)
    p0_identity = bind_authority_identity_v1(
        p0, p0_target_authority_identity, label="P0 target authority"
    )
    permutation = validate_world_permutation_authority_v1(
        world_permutation_authority
    )
    permutation_identity = bind_authority_identity_v1(
        permutation,
        world_permutation_authority_identity,
        label="world permutation authority",
    )
    runtime = validate_runtime_authority_v1(runtime_authority)
    runtime_identity = bind_authority_identity_v1(
        runtime, runtime_authority_identity, label="runtime authority"
    )
    exact_common = {
        "slate_id": slate,
        "candidate_origin_id": context["origin"],
        "fit_scope_id": context["fit_scope_id"],
        "heldout_block": heldout_block,
        "training_blocks": list(context["training_blocks"]),
    }
    for label, authority in (
        ("P0 target", p0),
        ("world permutation", permutation),
        ("runtime", runtime),
    ):
        if any(authority.get(key) != value for key, value in exact_common.items()):
            _fail(f"{label} authority cell scope differs")
    if p0["source_lineage"] != context["lineage"]:
        _fail("P0 target source lineage differs from loaded score source")
    if permutation["source_lineage"] != context["lineage"]:
        _fail("world permutation lineage differs from loaded score source")
    if permutation["worlds_per_block"] != context["width"]:
        _fail("world permutation width differs from loaded score source")
    if runtime["p0_target_authority_identity"] != p0_identity:
        _fail("runtime authority does not bind the exact P0 target identity")
    if runtime["world_permutation_authority_identity"] != permutation_identity:
        _fail("runtime authority does not bind the exact permutation identity")
    profile = legal.frozen_policy_profiles()[0]
    if runtime["incumbent_profile_sha256"] != profile.parameter_set_sha256:
        _fail("runtime authority does not bind the incumbent profile")

    target = int(p0["retained_count"])
    computed_ceiling = min(
        MAXIMUM_SOLVER_CALL_CEILING,
        max(MINIMUM_SOLVER_CALL_CEILING, SOLVER_CALLS_PER_TARGET * target),
    )
    effective_ceiling = min(int(context["width"]), computed_ceiling)
    if target > effective_ceiling:
        _fail("P0 target exceeds the precommitted effective solver-call ceiling")
    order = list(permutation["ordered_world_indices"])
    configuration = {
        "schema_version": "hard230-population-generator-configuration/v1",
        "contract_id": CONTRACT_ID,
        "strategy_id": STRATEGY_ID,
        "generator_law_id": GENERATOR_LAW_ID,
        **exact_common,
        "source_lineage": context["lineage"],
        "p0_target_authority_identity": p0_identity,
        "world_permutation_authority_identity": permutation_identity,
        "runtime_authority_identity": runtime_identity,
        "target_retained_count": target,
        "computed_solver_call_ceiling": computed_ceiling,
        "effective_solver_call_ceiling": effective_ceiling,
        "retention_threshold_milli_dk": THRESHOLD_MILLI_DK,
        "control_retention_law": "first-target-unique-legal-rosters-score-blind",
        "challenger_retention_law": (
            "first-target-unique-legal-rosters-with-inclusive-230-fit-world-hit"
        ),
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    configuration_sha = _sha(configuration, label="generator configuration")
    stream_id = (
        f"hard230v2-{slate}-{context['fit_scope_id']}-{context['origin']}-"
        f"{configuration_sha[:20]}"
    )
    matrix = context["matrix"]
    player_index = context["player_index"]
    origin_offset = int(context["origin_ordinal"]) * int(context["width"])
    evidence_records: list[dict[str, object]] = []
    occurrences: list[dict[str, object]] = []
    control: list[dict[str, object]] = []
    control_hashes: set[str] = set()
    challenger: list[dict[str, object]] = []
    seen: set[str] = set()
    rejection_counts = {
        "non-optimal-solver-result": 0,
        "duplicate-generated-roster": 0,
        "no-inclusive-230-permitted-fit-world-hit": 0,
    }

    for position in range(effective_ceiling):
        world_index = int(order[position])
        objective_milli = matrix[:, origin_offset + world_index]
        objective_micro = tuple(int(value) * MILLI_TO_MICRO for value in objective_milli)
        model = legal.build_fresh_legal_model(
            context["players"],
            profile,
            objective_micro,
            construction_serial=position,
            model_name=(
                f"hard230v2_{slate}_{context['fit_scope_id']}_"
                f"{context['origin']}_{position}"
            ),
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
        outcome = legal._normalize_solver_outcome(
            solver_callback(request), request=request, profile=profile
        )
        if mode == RELEASE_EXECUTION_MODE:
            try:
                legal._validate_authoritative_solver_proof(
                    outcome,
                    solver_authority_sha256=str(
                        runtime["solver_authority_sha256"]
                    ),
                )
            except legal.CorpusLegalFeasibilityError as exc:
                raise Hard230PopulationSuccessorV1Error(
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
        solver_input = {
            "stream_id": stream_id,
            "generator_configuration_sha256": configuration_sha,
            "stream_position": position,
            "candidate_origin_id": context["origin"],
            "source_world_index": world_index,
            "source_lineage": context["lineage"],
        }
        solver_output = {"solver_status": status, "roster_player_ids": roster}
        solver_evidence = {
            "schema_version": "hard230-population-solver-evidence/v1",
            "execution_mode": mode,
            "runtime_authority_identity": runtime_identity,
            "runtime_authority_sha256": runtime["runtime_authority_sha256"],
            "solver_input": solver_input,
            "solver_input_sha256": _sha(solver_input, label="solver input"),
            "solver_output": solver_output,
            "solver_output_sha256": _sha(solver_output, label="solver output"),
            "primary_optimum_micro": outcome.primary_optimum_micro,
            "secondary_rank_sum": outcome.secondary_rank_sum,
            "lexicographic_radix": outcome.lexicographic_radix,
            "combined_optimum": outcome.combined_optimum,
            "canonical_solver_proof": _proof_payload(outcome),
            "authoritative_solver_proof_validated": (
                mode == RELEASE_EXECUTION_MODE
            ),
            "outcome_columns_read": [],
            **_false_authorities(),
        }
        solver_ref = _record_evidence(
            evidence_recorder,
            evidence_records,
            role="hard230-solver-proof",
            deterministic_key=f"{stream_id}/solver-{position:05d}",
            body=solver_evidence,
        )

        lineup_id: str | None = None
        roster_sha: str | None = None
        legality_ref: dict[str, object] | None = None
        new_unique = False
        inclusive_230_hit = False
        max_fit_score: int | None = None
        if status == "optimal":
            if roster is None:
                _fail(f"optimal solver occurrence[{position}] lacks a roster")
            try:
                audited = legal.audit_dk_classic(context["players"], roster)
                legal._audit_profile_compliance(context["players"], audited, profile)
            except legal.CorpusLegalFeasibilityError as exc:
                raise Hard230PopulationSuccessorV1Error(
                    f"optimizer returned illegal occurrence[{position}]: {exc}"
                ) from exc
            roster = list(audited)
            roster_sha = _sha(roster, label="canonical roster")
            lineup_id = f"lineup-v1-{roster_sha}"
            legality_input = {
                "legality_law_id": source.LEGALITY_AUDIT_LAW_ID,
                "roster_player_ids": roster,
                "player_registry_sha256": context["lineage"][
                    "player_registry_sha256"
                ],
            }
            legality_output = {"legality_passed": True}
            legality_evidence = {
                "schema_version": "hard230-population-legality-evidence/v1",
                "runtime_authority_identity": runtime_identity,
                "legality_input": legality_input,
                "legality_input_sha256": _sha(
                    legality_input, label="legality input"
                ),
                "legality_output": legality_output,
                "legality_output_sha256": _sha(
                    legality_output, label="legality output"
                ),
                "outcome_columns_read": [],
                **_false_authorities(),
            }
            legality_ref = _record_evidence(
                evidence_recorder,
                evidence_records,
                role="hard230-legality-proof",
                deterministic_key=(
                    f"{stream_id}/legality-{position:05d}-{roster_sha[:16]}"
                ),
                body=legality_evidence,
            )
            if roster_sha not in seen:
                new_unique = True
                seen.add(roster_sha)
                roster_record = {
                    "lineup_id": lineup_id,
                    "roster_player_ids": roster,
                    "roster_sha256": roster_sha,
                    "first_occurrence_ordinal": position,
                }
                if len(control) < target:
                    control.append(roster_record)
                    control_hashes.add(roster_sha)
                fit_scores = _score_roster(
                    roster, matrix=matrix, player_index=player_index
                )
                max_fit_score = int(fit_scores.max())
                inclusive_230_hit = max_fit_score >= THRESHOLD_MILLI_DK
                if inclusive_230_hit:
                    challenger.append(roster_record)
                else:
                    rejection_counts[
                        "no-inclusive-230-permitted-fit-world-hit"
                    ] += 1
            else:
                rejection_counts["duplicate-generated-roster"] += 1
        else:
            if roster is not None:
                _fail("non-optimal solver occurrence returned a roster")
            rejection_counts["non-optimal-solver-result"] += 1
        occurrence = {
            "stream_position": position,
            "source_world_index": world_index,
            "solver_status": status,
            "solver_evidence_record": solver_ref,
            "lineup_id": lineup_id,
            "roster_player_ids": roster,
            "roster_sha256": roster_sha,
            "legality_evidence_record": legality_ref,
            "new_unique_legal_roster": new_unique,
            "inclusive_230_fit_world_hit": inclusive_230_hit,
            "maximum_fit_score_milli_dk": max_fit_score,
            "retained_by_score_blind_control": (
                new_unique and roster_sha in control_hashes
            ),
            "retained_by_hard230_challenger": (
                new_unique and inclusive_230_hit
            ),
            "outcome_columns_read": [],
            "uses_heldout_scores": False,
            "uses_realized_outcomes": False,
        }
        occurrences.append(occurrence)
        if len(challenger) == target:
            break

    hard_target_reached = len(challenger) == target
    termination_reason = (
        "hard230-target-reached"
        if hard_target_reached
        else "effective-ceiling-exhausted-with-shortfall"
    )
    control_diagnostics = _population_diagnostics(
        population_id=CONTROL_POPULATION_ID,
        rosters=control,
        matrix=matrix,
        player_index=player_index,
        source_lineage=context["lineage"],
    )
    challenger_diagnostics = _population_diagnostics(
        population_id=CHALLENGER_POPULATION_ID,
        rosters=challenger,
        matrix=matrix,
        player_index=player_index,
        source_lineage=context["lineage"],
    )
    body = {
        "schema_version": RECEIPT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "strategy_id": STRATEGY_ID,
        "generator_law_id": GENERATOR_LAW_ID,
        "mechanism_class": "native-population-generation-with-replenishment",
        "is_selector": False,
        "is_strict230_selector": False,
        "is_legacy_t230_panel": False,
        "does_not_use_frozen_stop_at_control_target_companion_law": True,
        "execution_mode": mode,
        **exact_common,
        "source_lineage": context["lineage"],
        "player_count": len(context["players"]),
        "maximum_player_count": MAX_PLAYER_COUNT,
        "p0_target_authority_identity": p0_identity,
        "world_permutation_authority_identity": permutation_identity,
        "runtime_authority_identity": runtime_identity,
        "generator_configuration": configuration,
        "generator_configuration_sha256": configuration_sha,
        "stream_id": stream_id,
        "target_retained_count": target,
        "computed_solver_call_ceiling": computed_ceiling,
        "effective_solver_call_ceiling": effective_ceiling,
        "actual_shared_solver_call_count": len(occurrences),
        "control_solver_call_budget": effective_ceiling,
        "challenger_solver_call_budget": effective_ceiling,
        "equal_solver_call_budget": True,
        "control_observed_solver_call_count": len(occurrences),
        "challenger_observed_solver_call_count": len(occurrences),
        "equal_observed_solver_call_count": True,
        "solver_occurrences_shared_not_reexecuted": True,
        "ordered_occurrences_sha256": _ordered_records_sha256(
            occurrences, label="hard230 successor occurrences"
        ),
        "occurrence_count": len(occurrences),
        "evidence_record_count": len(evidence_records),
        "ordered_evidence_records_sha256": _ordered_records_sha256(
            evidence_records, label="hard230 successor evidence records"
        ),
        "authoritative_solver_proofs_validated": mode == RELEASE_EXECUTION_MODE,
        "fixture_solver_proof_bypass": mode == FIXTURE_EXECUTION_MODE,
        "termination_reason": termination_reason,
        "hard230_exact_target_reached": hard_target_reached,
        "control_shortfall": target - len(control),
        "hard230_shortfall": target - len(challenger),
        "threshold_was_not_lowered": True,
        "retention_threshold_milli_dk": THRESHOLD_MILLI_DK,
        "rejection_counts": rejection_counts,
        "diagnostic_thresholds_milli_dk": list(
            DIAGNOSTIC_THRESHOLDS_MILLI_DK
        ),
        "score_blind_control_population": control_diagnostics,
        "hard230_challenger_population": challenger_diagnostics,
        "diagnostics_are_fit_world_only_not_heldout_effects": True,
        "outcome_columns_read": [],
        **_false_authorities(),
    }
    receipt = _self_hash(body, "successor_receipt_sha256")
    return Hard230PopulationSuccessorResult(
        receipt=receipt,
        occurrences=tuple(occurrences),
        evidence_records=tuple(evidence_records),
    )


def validate_successor_receipt_v1(value: object) -> dict[str, object]:
    item = _mapping(value, label="hard230 successor receipt")
    retained = _sha256(
        item.pop("successor_receipt_sha256", None),
        label="hard230 successor receipt SHA-256",
    )
    if retained != _sha(item, label="hard230 successor receipt body"):
        _fail("hard230 successor receipt self-hash differs")
    if item.get("schema_version") != RECEIPT_SCHEMA:
        _fail("hard230 successor receipt schema differs")
    if any(item.get(field) is not False for field in _FALSE_AUTHORITY_FIELDS):
        _fail("hard230 successor receipt claims forbidden authority")
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
        or item.get(
            "does_not_use_frozen_stop_at_control_target_companion_law"
        ) is not True
        or item.get("threshold_was_not_lowered") is not True
    ):
        _fail("hard230 successor receipt does not bind the replenishing shared law")
    return {**item, "successor_receipt_sha256": retained}


__all__ = [
    "CHALLENGER_POPULATION_ID",
    "CONTRACT_ID",
    "CONTROL_POPULATION_ID",
    "DIAGNOSTIC_THRESHOLDS_MILLI_DK",
    "FIXTURE_EXECUTION_MODE",
    "Hard230PopulationSuccessorResult",
    "Hard230PopulationSuccessorV1Error",
    "MAX_PLAYER_COUNT",
    "P0_TARGET_SCHEMA",
    "RELEASE_EXECUTION_MODE",
    "RUNTIME_AUTHORITY_SCHEMA",
    "WORLD_PERMUTATION_SCHEMA",
    "bind_authority_identity_v1",
    "build_p0_target_authority_v1",
    "build_runtime_authority_v1",
    "build_world_permutation_authority_v1",
    "run_hard230_population_successor_v1",
    "validate_p0_target_authority_v1",
    "validate_runtime_authority_v1",
    "validate_successor_receipt_v1",
    "validate_world_permutation_authority_v1",
]
