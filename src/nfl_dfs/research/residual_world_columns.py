"""Pure score-free primitives for residual-world portfolio columns.

This module implements the mathematical core frozen by protocol
``20260817-residual-world-column-generation-scorefree-v1``.  It deliberately
does not read BigQuery, GCS, realized outcomes, ownership, ranks, payouts, or
production configuration.  The legality model calls the constraints-only
builder shared with the ordinary optimizer, while retaining an independent
post-solve auditor.  Importing this module cannot alter the production CBC
invocation.

All solver-facing scores are integer micro-DraftKings points.  Tail tiers are
optimized by consecutive exact solves, never by a weighted scalar surrogate.
The helpers return enough information for a future runner to reconstruct every
objective and legality claim independently before accepting a shard.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import re
import shlex
import stat
import tempfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN, localcontext
from pathlib import Path
from typing import Final, Protocol

import numpy as np
import pulp

from nfl_dfs.optimizer.lineup import (
    StackRules,
    add_classic_lineup_constraints,
    select_tail_entries,
)
from nfl_dfs.research.residual_world_run_context import (
    ResidualRunContext,
    recompute_residual_run_context_binding,
    validate_residual_run_context,
    validate_residual_run_context_binding,
)


PROTOCOL_ID: Final = "20260817-residual-world-column-generation-scorefree-v1"
PROTOCOL_DOCUMENT_SHA256: Final = (
    "db02c7bb7994ea887ad32a935f3188bc78384c3c4b97a3dc712f3ffd2a8fc02a"
)
PROTOCOL_AMENDMENT_ID: Final = (
    "20260817-residual-world-exact-solver-selector-v1"
)
PROTOCOL_AMENDMENT_SHA256: Final = (
    "a13c09eb6e4ea1e4f0515a0aa4b750614a020fc930d3d1d9e53b1bfe787042ff"
)
MICRO_DK_SCALE: Final = 1_000_000
TAIL_THRESHOLDS_DK: Final = (240, 230, 220, 210, 200, 194, 187)
TAIL_THRESHOLDS_MICRO: Final = tuple(
    value * MICRO_DK_SCALE for value in TAIL_THRESHOLDS_DK
)
WORLD_BLOCKS: Final = ("R0", "R1", "R2", "R3", "R4")
WORLDS_PER_BLOCK: Final = 10_000
K_MAX: Final = 8
ENTRY_COUNT: Final = 80
CONTROL_TAIL_LINE_DK: Final = 194
FOLD_RESERVOIR_SIZE: Final = 96
FOLD_ACTIVE_SIZE: Final = 66
SHADOW_RESERVOIR_SIZE: Final = 100
SHADOW_ACTIVE_SIZE: Final = 70
SHADOW_RESERVOIR_PER_BLOCK: Final = 20
SHADOW_ACTIVE_PER_BLOCK: Final = 14
ROSTER_SIZE: Final = 9
MIN_SALARY: Final = 49_000
SALARY_CAP: Final = 50_000
MAX_FROM_TEAM: Final = 8
MIN_GAMES: Final = 2
BOUND_TIME_LIMIT_SECONDS: Final = 120
PRICING_TIME_LIMIT_SECONDS: Final = 600
CBC_RANDOM_SEED: Final = 170_817
CBC_INTEGER_TOLERANCE: Final = Decimal("1e-9")
CBC_INTEGER_TOLERANCE_OPTION: Final = "1e-9"
CBC_INTEGER_DECODE_EPS: Final = Decimal("1e-9")
PINNED_PULP_VERSION: Final = "3.3.2"
PINNED_CBC_VERSION: Final = "2.10.3"
CBC_WARM_START: Final = True
CBC_AUXILIARY_CUTS: Final = False
SCORE_RADIX: Final = 100
BOUND_OBJECTIVE_BASE: Final = 100
RESIDUAL_OBJECTIVE_CHUNK_BITS: Final = 4
CBC_EXACT_INTEGER_MAX: Final = (1 << 53) - 1
RAW_MICRO_MAX_ERROR_DK: Final = 4.5e-6 + 1e-9
CLASSIC_SKILL_PATTERNS: Final = ((2, 4, 1), (2, 3, 2), (3, 3, 1))
UNLICENSED_SCIENTIFIC_FLAGS: Final = (
    "uses_realized_outcomes",
    "production_change_licensed",
    "historical_scoring_licensed",
)


class ResidualWorldError(ValueError):
    """Base class for fail-closed protocol violations."""


class SolverFailure(ResidualWorldError):
    """Raised when an exact MILP does not terminate at ``Optimal``."""


class InsufficientResidualWorldSupport(ResidualWorldError):
    """Raised when a frozen reservoir or active quota cannot be filled."""


def _strict_integer(value: object, label: str) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(
        value, (int, np.integer)
    ):
        raise ResidualWorldError(f"{label} must be an integer")
    return int(value)


def _strict_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise ResidualWorldError(f"{label} must be a nonempty string")
    return value


def _threshold_tuple(values: Sequence[int]) -> tuple[int, ...]:
    thresholds = tuple(
        _strict_integer(value, "tail threshold") for value in values
    )
    if thresholds != tuple(sorted(set(thresholds), reverse=True)):
        raise ResidualWorldError("tail thresholds must be unique and descending")
    return thresholds


@dataclass(frozen=True, slots=True)
class FoldSpec:
    name: str
    construction_blocks: tuple[str, ...]
    evaluation_blocks: tuple[str, ...]
    reservoir_per_block: int
    active_per_block: int


FOLD_SPECS: Final = (
    FoldSpec("A", ("R0", "R2", "R4"), ("R1", "R3"), 32, 22),
    FoldSpec("B", ("R1", "R3"), ("R0", "R2", "R4"), 48, 33),
)


@dataclass(frozen=True, slots=True, order=True)
class WorldId:
    block: str
    index: int

    def __post_init__(self) -> None:
        block = _strict_string(self.block, "world block")
        index = _strict_integer(self.index, "world index")
        if block not in WORLD_BLOCKS or not 0 <= index < WORLDS_PER_BLOCK:
            raise ResidualWorldError("world identity is outside R0..R4 x 0..9999")
        object.__setattr__(self, "index", index)


@dataclass(frozen=True, slots=True)
class PlayerSpec:
    player_id: str
    position: str
    team: str
    opponent: str
    game_id: str
    salary: int

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> "PlayerSpec":
        return cls(
            player_id=_strict_string(value["id"], "player id"),
            position=_strict_string(value["pos"], "player position").upper(),
            team=_strict_string(value["team"], "player team"),
            opponent=_strict_string(value["opp"], "player opponent"),
            game_id=_strict_string(value["game_id"], "player game id"),
            salary=_strict_integer(value["salary"], "player salary"),
        )

    def __post_init__(self) -> None:
        _strict_string(self.player_id, "player id")
        position = _strict_string(self.position, "player position").upper()
        if position not in {"QB", "RB", "WR", "TE", "DST"}:
            raise ResidualWorldError("player has an unsupported position")
        team = _strict_string(self.team, "player team")
        opponent = _strict_string(self.opponent, "player opponent")
        if team == opponent:
            raise ResidualWorldError("player team/opponent is malformed")
        _strict_string(self.game_id, "player game id")
        salary = _strict_integer(self.salary, "player salary")
        if salary < 0:
            raise ResidualWorldError("player salary is malformed")
        object.__setattr__(self, "position", position)
        object.__setattr__(self, "salary", salary)


@dataclass(slots=True)
class LegalLineupModel:
    """Mutable PuLP model plus its canonical, independently owned variables."""

    problem: pulp.LpProblem
    players: tuple[PlayerSpec, ...]
    decision: dict[str, pulp.LpVariable]


@dataclass(frozen=True, slots=True)
class LegalBounds:
    lower_micro: tuple[int, ...]
    upper_micro: tuple[int, ...]
    lower_rosters: tuple[tuple[str, ...], ...]
    upper_rosters: tuple[tuple[str, ...], ...]
    solve_evidence: tuple["CbcSolveEvidence", ...] = field(
        default=(), compare=False, repr=False
    )


@dataclass(frozen=True, slots=True)
class TailUtility:
    threshold_counts: tuple[int, ...]
    sum_max_micro: int

    @property
    def vector(self) -> tuple[int, ...]:
        return (*self.threshold_counts, self.sum_max_micro)


@dataclass(frozen=True, slots=True)
class PricingResult:
    roster: tuple[str, ...]
    scores_micro: tuple[int, ...]
    marginal_threshold_counts: tuple[int, ...]
    residuals_micro: tuple[int, ...]
    residual_gain_micro: int
    objective_vector: tuple[int, ...]
    indicators_by_threshold: tuple[tuple[int, ...], ...]
    rank_sum: int
    rank_sum_ambiguous: bool
    admissible: bool
    sequential_optima: tuple[int, ...]
    ambiguity_distance: int = 0
    rank_first_roster: tuple[str, ...] = ()
    pricing_input_sha256: str = field(default="", compare=False)
    no_good_rosters: tuple[tuple[str, ...], ...] = ()
    solve_evidence: tuple["CbcSolveEvidence", ...] = field(
        default=(), compare=False, repr=False
    )


@dataclass(frozen=True, slots=True)
class WorldSelection:
    world_id: WorldId
    queue_threshold_micro: int
    book_max_micro: int
    upper_bound_micro: int

    def __post_init__(self) -> None:
        if not isinstance(self.world_id, WorldId):
            raise ResidualWorldError("world selection identity is malformed")
        threshold = _strict_integer(
            self.queue_threshold_micro, "world queue threshold"
        )
        maximum = _strict_integer(self.book_max_micro, "world book maximum")
        upper = _strict_integer(self.upper_bound_micro, "world upper bound")
        if not maximum < threshold <= upper:
            raise ResidualWorldError("world selection receipt is not eligible")
        object.__setattr__(self, "queue_threshold_micro", threshold)
        object.__setattr__(self, "book_max_micro", maximum)
        object.__setattr__(self, "upper_bound_micro", upper)


@dataclass(frozen=True, slots=True)
class PruningStep:
    dose: int
    removed_identity: tuple[str, ...]
    utility_before: TailUtility
    utility_after: TailUtility
    remaining_candidates: int


@dataclass(frozen=True, slots=True)
class PruningResult:
    original_candidates: int
    steps: tuple[PruningStep, ...]

    @property
    def removal_order(self) -> tuple[tuple[str, ...], ...]:
        return tuple(step.removed_identity for step in self.steps)


@dataclass(frozen=True, slots=True)
class AdaptiveStep:
    iteration: int
    pricing: PricingResult


@dataclass(frozen=True, slots=True)
class AdaptiveSequence:
    steps: tuple[AdaptiveStep, ...]
    columns: tuple[tuple[str, ...], ...]
    stopped_on_first_null: bool
    null_iteration: int | None


@dataclass(frozen=True, slots=True)
class WorldLegalBound:
    world_id: WorldId
    lower_micro: int
    upper_micro: int
    lower_roster: tuple[str, ...]
    upper_roster: tuple[str, ...]
    lower_evidence: tuple["CbcSolveEvidence", ...] = field(
        compare=False, repr=False
    )
    upper_evidence: tuple["CbcSolveEvidence", ...] = field(
        compare=False, repr=False
    )

    def __post_init__(self) -> None:
        lower = _strict_integer(self.lower_micro, "world legal lower bound")
        upper = _strict_integer(self.upper_micro, "world legal upper bound")
        if lower > upper:
            raise ResidualWorldError("world legal lower bound exceeds upper bound")
        lower_roster = canonical_identity(self.lower_roster)
        upper_roster = canonical_identity(self.upper_roster)
        lower_evidence = tuple(self.lower_evidence)
        upper_evidence = tuple(self.upper_evidence)
        if len(lower_evidence) != 2 or len(upper_evidence) != 2 or any(
            not isinstance(evidence, CbcSolveEvidence)
            for evidence in (*lower_evidence, *upper_evidence)
        ):
            raise ResidualWorldError(
                "world legal bound lacks retained exact-solve evidence"
            )
        object.__setattr__(self, "lower_micro", lower)
        object.__setattr__(self, "upper_micro", upper)
        object.__setattr__(self, "lower_roster", lower_roster)
        object.__setattr__(self, "upper_roster", upper_roster)
        object.__setattr__(self, "lower_evidence", lower_evidence)
        object.__setattr__(self, "upper_evidence", upper_evidence)


@dataclass(frozen=True, slots=True)
class ScoreParityReceipt:
    float64_totals_sha256: str
    selector_thresholds_sha256: str
    float64_thresholds_sha256: str
    micro_thresholds_sha256: str
    max_raw_micro_error_hex: str

    @property
    def sha256(self) -> str:
        return _canonical_json_sha256(_score_parity_scientific_receipt(self))


def _score_parity_scientific_receipt(
    receipt: ScoreParityReceipt,
) -> dict[str, str]:
    if not isinstance(receipt, ScoreParityReceipt):
        raise ResidualWorldError("score-parity receipt has the wrong type")
    return {
        "float64_totals_sha256": receipt.float64_totals_sha256,
        "selector_thresholds_sha256": receipt.selector_thresholds_sha256,
        "float64_thresholds_sha256": receipt.float64_thresholds_sha256,
        "micro_thresholds_sha256": receipt.micro_thresholds_sha256,
        "max_raw_micro_error_hex": receipt.max_raw_micro_error_hex,
    }


@dataclass(frozen=True, slots=True)
class PreparedFoldReservoir:
    """Immutable source/pruning/reservoir binding consumed by one fold run."""

    fold_name: str
    run_context: ResidualRunContext
    run_context_payload: tuple[tuple[str, object], ...]
    run_context_sha256: str
    fold_sha256: str
    world_ids_sha256: str
    player_catalog_sha256: str
    player_draws_sha256: str
    control_candidates: tuple[tuple[str, ...], ...]
    control_candidates_sha256: str
    control_source_tags: tuple[tuple[str, ...], ...]
    control_source_tags_sha256: str
    control_selector_totals_sha256: str
    control_micro_totals_sha256: str
    control_score_parity: ScoreParityReceipt
    control_score_parity_sha256: str
    control_book: tuple[tuple[str, ...], ...]
    control_book_sha256: str
    pruning: PruningResult
    reservoir_selections: tuple[WorldSelection, ...]
    reservoir_selections_sha256: str
    reservoir_bounds: tuple[WorldLegalBound, ...]
    reservoir_sha256: str


@dataclass(frozen=True, slots=True)
class FoldDoseStep:
    iteration: int
    reservoir_sha256: str
    reservoir_maxima_micro: tuple[int, ...]
    reservoir_maxima_sha256: str
    active_selections: tuple[WorldSelection, ...]
    reference_book_before: tuple[tuple[str, ...], ...]
    reference_book_sha256: str
    reference_maxima_micro: tuple[int, ...]
    complete_no_goods: tuple[tuple[str, ...], ...]
    complete_no_goods_sha256: str
    pricing: PricingResult
    treatment_pool_after: tuple[tuple[str, ...], ...] | None
    treatment_pool_sha256: str | None
    selected_book_after: tuple[tuple[str, ...], ...] | None
    selected_book_sha256: str | None


@dataclass(frozen=True, slots=True)
class FoldDoseAuditContext:
    """Immutable source material needed to re-audit a dose at serialization.

    These values are deliberately excluded from the scientific projection:
    their canonical hashes and the independently reconstructed receipts are
    what enter that projection.  Retaining the source values prevents a
    deserialized :class:`FoldDoseResult` from licensing itself by presenting
    only internally consistent hashes.
    """

    prepared: PreparedFoldReservoir
    players: tuple[PlayerSpec, ...]
    world_ids: tuple[WorldId, ...]
    raw_player_draws: np.ndarray = field(compare=False, repr=False)
    control_identities: tuple[tuple[str, ...], ...]
    control_source_tags: tuple[tuple[str, ...], ...]
    control_selector_totals: np.ndarray = field(compare=False, repr=False)
    control_micro_totals: np.ndarray = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FoldDoseResult:
    fold_name: str
    run_context: ResidualRunContext
    run_context_payload: tuple[tuple[str, object], ...]
    run_context_sha256: str
    prepared_fold_sha256: str
    prepared_reservoir_sha256: str
    control_book: tuple[tuple[str, ...], ...]
    control_source_tags: tuple[tuple[str, ...], ...]
    treatment_candidates: tuple[tuple[str, ...], ...]
    treatment_source_tags: tuple[tuple[str, ...], ...]
    treatment_source_tags_sha256: str
    treatment_book: tuple[tuple[str, ...], ...]
    generated_columns: tuple[tuple[str, ...], ...]
    steps: tuple[FoldDoseStep, ...]
    stopped_on_first_null: bool
    null_iteration: int | None
    selector_call_count: int
    audit_context: FoldDoseAuditContext = field(compare=False, repr=False)
    operational_evidence: "FoldDoseOperationalEvidence" = field(
        compare=False, repr=False
    )
    pricing_evidence_manifest_sha256: str
    generated_selector_totals_sha256: str
    generated_micro_totals_sha256: str
    generated_score_parity: ScoreParityReceipt
    generated_score_parity_sha256: str
    treatment_selector_totals_sha256: str
    treatment_micro_totals_sha256: str
    treatment_score_parity: ScoreParityReceipt
    treatment_score_parity_sha256: str
    generated_selector_totals: np.ndarray = field(compare=False, repr=False)
    generated_micro_totals: np.ndarray = field(compare=False, repr=False)
    treatment_selector_totals: np.ndarray = field(compare=False, repr=False)
    treatment_micro_totals: np.ndarray = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class FoldDoseOperationalEvidence:
    """Machine-local proof location, excluded from scientific equality."""

    evidence_root: str
    evidence_root_sha256: str


@dataclass(frozen=True, slots=True)
class CbcSolveEvidence:
    """Retained, strictly parsed proof that one CBC solve was exact-optimal."""

    solve_label: str
    evidence_directory: str
    log_path: str
    solution_path: str
    model_path: str
    variable_domain_manifest_path: str
    mip_start_path: str | None
    log_sha256: str
    solution_sha256: str
    model_sha256: str
    mip_start_sha256: str | None
    mip_start_values_sha256: str | None
    mip_start_renamed_values_sha256: str | None
    mip_start_variable_count: int
    predecessor_assignment_sha256: str | None
    mip_start_reconstructed_objective: int | None
    mip_start_values: tuple[tuple[str, int], ...] | None = field(
        compare=False, repr=False
    )
    cbc_path: str
    cbc_sha256: str
    cbc_version: str
    pulp_version: str
    command_line: str
    pulp_status: int
    pulp_solution_status: int
    objective: int
    problem_sense: int
    enumerated_nodes: int
    total_iterations: int
    cpu_seconds: Decimal
    wall_seconds: Decimal
    max_seconds: int
    warm_start: bool
    cuts: bool | None
    preprocess_off: bool
    random_seed: int
    random_cbc_seed: int
    threads: int
    time_mode: str
    relative_gap: Decimal
    absolute_gap: Decimal
    primal_tolerance: Decimal
    integer_tolerance: Decimal
    variable_domain_manifest_sha256: str
    canonical_assignment_sha256: str
    integer_decode_affected_count: int
    integer_decode_max_residual: Decimal
    variable_domain_manifest: tuple[
        tuple[str, str, str, int | None, int | None], ...
    ] = field(compare=False, repr=False)
    integer_decode_rows: tuple[
        tuple[str, str, int, str], ...
    ] = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class _BinaryNumber:
    """Little-endian exact binary representation owned by one MILP."""

    bits: tuple[pulp.LpVariable, ...]
    upper_bound: int


@dataclass(frozen=True, slots=True)
class _ParsedExactMps:
    sense: int
    objective_row: str
    rows: tuple[str, ...]
    row_senses: Mapping[str, str]
    columns: tuple[str, ...]
    integer_columns: frozenset[str]
    column_categories: Mapping[str, str]
    coefficients: Mapping[tuple[str, str], int]
    rhs: Mapping[str, int]
    bounds: Mapping[str, tuple[int | None, int | None]]


class PricingStep(Protocol):
    def __call__(
        self,
        iteration: int,
        previous_columns: tuple[tuple[str, ...], ...],
    ) -> PricingResult: ...


class _RetainedCbcSolver(pulp.PULP_CBC_CMD):
    """CBC command wrapper retaining unique MPS, solution, and log files."""

    def __init__(
        self,
        max_seconds: int,
        warm_start: bool,
        cuts: bool | None,
        *,
        evidence_root: str | Path | None = None,
    ) -> None:
        root = (
            None
            if evidence_root is None
            else str(_resolve_real_directory(
                Path(evidence_root), "CBC evidence root"
            ))
        )
        directory = Path(tempfile.mkdtemp(prefix="residual_cbc_", dir=root))
        self.evidence_directory = directory
        self.max_seconds_exact = max_seconds
        self.warm_start_exact = warm_start
        self.cuts_exact = cuts
        self.preprocess_off_exact = False
        self.artifact_paths: dict[str, Path] = {}
        self.evidence: CbcSolveEvidence | None = None
        self.mip_start_values: tuple[tuple[str, int], ...] | None = None
        self.predecessor_assignment_sha256: str | None = None
        self.mip_start_reconstructed_objective: int | None = None
        self.variable_domain_manifest: tuple[
            tuple[str, str, str, int | None, int | None], ...
        ] | None = None
        self.variable_domain_manifest_path: Path | None = None
        super().__init__(
            msg=False,
            timeLimit=max_seconds,
            gapRel=0.0,
            gapAbs=0.0,
            threads=1,
            warmStart=warm_start,
            cuts=cuts,
            options=[
                f"randomSeed {CBC_RANDOM_SEED}",
                f"randomCbcSeed {CBC_RANDOM_SEED}",
                "primalTolerance 1e-9",
                f"integerTolerance {CBC_INTEGER_TOLERANCE_OPTION}",
            ],
            logPath=str(directory / "cbc.log"),
            keepFiles=False,
            timeMode="elapsed",
        )

    def create_tmp_files(self, name: str, *args: str):  # type: ignore[override]
        paths = tuple(self.evidence_directory / f"model.{suffix}" for suffix in args)
        if any(path.exists() for path in paths):
            raise SolverFailure("CBC evidence artifact path was reused")
        self.artifact_paths.update(zip(args, paths, strict=True))
        return (str(path) for path in paths)

    def delete_tmp_files(self, *args: str) -> None:  # type: ignore[override]
        # Exact-solve evidence is intentionally retained for the runner to
        # persist and hash.  Every solver instance owns a create-only folder.
        return None

    def disable_preprocess(self) -> None:
        if self.preprocess_off_exact:
            raise SolverFailure("CBC preprocessing mode was configured twice")
        self.options.append("preprocess off")
        self.preprocess_off_exact = True


SolverFactory = Callable[[int, bool], _RetainedCbcSolver]


def _players(values: Sequence[PlayerSpec | Mapping[str, object]]) -> tuple[PlayerSpec, ...]:
    result = tuple(
        value if isinstance(value, PlayerSpec) else PlayerSpec.from_mapping(value)
        for value in values
    )
    if len(result) < ROSTER_SIZE:
        raise ResidualWorldError("legal lineup pool has fewer than nine players")
    if len({player.player_id for player in result}) != len(result):
        raise ResidualWorldError("legal lineup pool repeats a player id")
    # Preserve the caller's explicitly receipted player-row order so score
    # matrices remain aligned.  Every identity/rank tie below is nevertheless
    # derived from UTF-8-sorted ids and is therefore row-order invariant.
    return result


def canonical_identity(player_ids: Sequence[object]) -> tuple[str, ...]:
    if isinstance(player_ids, (str, bytes)):
        raise ResidualWorldError("lineup identity must be a roster sequence")
    identity = tuple(sorted(
        _strict_string(value, "lineup player id") for value in player_ids
    ))
    if len(identity) != ROSTER_SIZE or len(set(identity)) != ROSTER_SIZE:
        raise ResidualWorldError("lineup identity must contain nine unique ids")
    return identity


def complete_no_good_rosters(
    control_rosters: Sequence[Sequence[object]],
    previous_columns: Sequence[Sequence[object]],
) -> tuple[tuple[str, ...], ...]:
    """Bind all original controls and all earlier columns into one cut list."""
    controls = tuple(canonical_identity(value) for value in control_rosters)
    previous = tuple(canonical_identity(value) for value in previous_columns)
    combined = (*controls, *previous)
    if len(set(controls)) != len(controls):
        raise ResidualWorldError("control no-good roster repeats")
    if len(set(previous)) != len(previous):
        raise ResidualWorldError("previous generated no-good roster repeats")
    if len(set(combined)) != len(combined):
        raise ResidualWorldError(
            "generated no-good roster duplicates an original control"
        )
    return combined


def _canonical_json_sha256(value: object) -> str:
    payload = json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def validate_unlicensed_scientific_payload(
    payload: Mapping[str, object],
) -> None:
    """Fail closed unless all mandatory no-license flags are literally false."""
    if not isinstance(payload, Mapping) or any(
        payload.get(name) is not False for name in UNLICENSED_SCIENTIFIC_FLAGS
    ):
        raise ResidualWorldError(
            "scientific payload is missing an exact false authorization flag"
        )


def _array_sha256(values: np.ndarray) -> str:
    array = np.ascontiguousarray(values)
    digest = hashlib.sha256()
    digest.update(array.dtype.str.encode("ascii"))
    digest.update(b"\0")
    digest.update(json.dumps(array.shape, separators=(",", ":")).encode("ascii"))
    digest.update(b"\0")
    if array.size:
        digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def _fold_spec(name: str) -> FoldSpec:
    normalized = _strict_string(name, "fold name")
    matches = [spec for spec in FOLD_SPECS if spec.name == normalized]
    if len(matches) != 1:
        raise ResidualWorldError("fold name is not one frozen cross-fit fold")
    return matches[0]


def _fold_sha256(spec: FoldSpec) -> str:
    return _canonical_json_sha256({
        "name": spec.name,
        "construction_blocks": spec.construction_blocks,
        "evaluation_blocks": spec.evaluation_blocks,
        "reservoir_per_block": spec.reservoir_per_block,
        "active_per_block": spec.active_per_block,
    })


def _world_ids_sha256(world_ids: Sequence[WorldId]) -> str:
    return _canonical_json_sha256([
        [world.block, world.index] for world in world_ids
    ])


def _identities_sha256(identities: Sequence[Sequence[object]]) -> str:
    return _canonical_json_sha256([
        list(canonical_identity(identity)) for identity in identities
    ])


def _source_tags(
    values: Sequence[Sequence[object]], expected: int
) -> tuple[tuple[str, ...], ...]:
    if isinstance(values, (str, bytes)):
        raise ResidualWorldError("control source tags must be nested sequences")
    outer = tuple(values)
    if any(isinstance(value, (str, bytes)) for value in outer):
        raise ResidualWorldError("each control source tag row must be a sequence")
    rows = tuple(tuple(
        _strict_string(tag, "control source tag") for tag in value
    ) for value in outer)
    if len(rows) != expected:
        raise ResidualWorldError("control source tags are misaligned")
    if any(not row or len(set(row)) != len(row) for row in rows):
        raise ResidualWorldError(
            "each control candidate needs unique nonempty source tags"
        )
    return rows


def _source_tags_sha256(values: Sequence[Sequence[str]]) -> str:
    return _canonical_json_sha256([list(value) for value in values])


def _player_catalog_sha256(players: Sequence[PlayerSpec]) -> str:
    return _canonical_json_sha256([{
        "id": player.player_id,
        "pos": player.position,
        "team": player.team,
        "opp": player.opponent,
        "game_id": player.game_id,
        "salary": player.salary,
    } for player in players])


def _exact_world_order(world_ids: Sequence[WorldId]) -> tuple[WorldId, ...]:
    identities = tuple(world_ids)
    expected = tuple(
        WorldId(block, index)
        for block in WORLD_BLOCKS
        for index in range(WORLDS_PER_BLOCK)
    )
    if identities != expected:
        raise ResidualWorldError(
            "world matrix must use canonical R0..R4 x 0..9999 order"
        )
    return identities


def _selector_matrix(values: np.ndarray, rows: int, columns: int) -> np.ndarray:
    matrix = np.asarray(values)
    if matrix.dtype != np.float32 or matrix.shape != (rows, columns):
        raise ResidualWorldError(
            "selector totals must be one exact aligned float32 matrix"
        )
    if not np.isfinite(matrix).all():
        raise ResidualWorldError("selector totals must be finite")
    return matrix


def _player_draw_matrix(values: np.ndarray, rows: int, columns: int) -> np.ndarray:
    matrix = np.asarray(values)
    if matrix.dtype != np.float32 or matrix.shape != (rows, columns):
        raise ResidualWorldError(
            "player worlds must be one exact aligned float32 matrix"
        )
    if not np.isfinite(matrix).all():
        raise ResidualWorldError("player worlds must be finite")
    return matrix


def _cross_score_rosters(
    players: tuple[PlayerSpec, ...],
    raw_player_draws: np.ndarray,
    micro_player_draws: np.ndarray,
    identities: Sequence[Sequence[object]],
) -> tuple[np.ndarray, np.ndarray]:
    by_id = {player.player_id: index for index, player in enumerate(players)}
    world_count = raw_player_draws.shape[1]
    raw_rows: list[np.ndarray] = []
    micro_rows: list[np.ndarray] = []
    for value in identities:
        identity = canonical_identity(value)
        if not set(identity) <= set(by_id):
            raise ResidualWorldError("candidate roster is outside player catalog")
        # Canonical CBWU sums selected rows in the base player-row order, then
        # casts the result to float32 before concatenation/selection.
        indices = [
            index for index, player in enumerate(players)
            if player.player_id in identity
        ]
        raw_rows.append(
            raw_player_draws[indices].sum(axis=0).astype(np.float32)
        )
        micro_rows.append(
            micro_player_draws[indices].sum(axis=0, dtype=np.int64)
        )
    if not raw_rows:
        return (
            np.empty((0, world_count), dtype=np.float32),
            np.empty((0, world_count), dtype=np.int64),
        )
    return (
        np.stack(raw_rows).astype(np.float32, copy=False),
        np.stack(micro_rows).astype(np.int64, copy=False),
    )


def _validate_selector_indices(indices: Sequence[object], pool_size: int) -> tuple[int, ...]:
    selected = tuple(
        _strict_integer(value, "selector index") for value in indices
    )
    if len(selected) != ENTRY_COUNT or len(set(selected)) != ENTRY_COUNT:
        raise ResidualWorldError("unchanged selector did not return exact-80 unique rows")
    if any(not 0 <= value < pool_size for value in selected):
        raise ResidualWorldError("unchanged selector returned an out-of-range row")
    return selected


def _select_exact_book(
    identities: tuple[tuple[str, ...], ...],
    selector_totals: np.ndarray,
    construction_columns: np.ndarray,
) -> tuple[tuple[tuple[str, ...], ...], tuple[int, ...]]:
    selected = _validate_selector_indices(
        select_tail_entries(
            selector_totals[:, construction_columns],
            ENTRY_COUNT,
            float(CONTROL_TAIL_LINE_DK),
            env={"SELECT_LSE": "0"},
        ),
        len(identities),
    )
    return tuple(identities[index] for index in selected), selected


def _world_selections_sha256(values: Sequence[WorldSelection]) -> str:
    return _canonical_json_sha256([{
        "world_id": [value.world_id.block, value.world_id.index],
        "queue_threshold_micro": value.queue_threshold_micro,
        "book_max_micro": value.book_max_micro,
        "upper_bound_micro": value.upper_bound_micro,
    } for value in values])


def _pruning_scientific_receipt(pruning: PruningResult) -> dict[str, object]:
    return {
        "original_candidates": pruning.original_candidates,
        "steps": [{
            "dose": step.dose,
            "removed_identity": list(step.removed_identity),
            "utility_before": list(step.utility_before.vector),
            "utility_after": list(step.utility_after.vector),
            "remaining_candidates": step.remaining_candidates,
        } for step in pruning.steps],
    }


def _freeze_run_context_binding(
    context: ResidualRunContext,
) -> tuple[
    ResidualRunContext,
    tuple[tuple[str, object], ...],
    str,
]:
    """Validate and freeze the reviewed path-free run identity."""
    if not isinstance(context, ResidualRunContext):
        raise ResidualWorldError(
            "residual preparation requires the reviewed run-context type"
        )
    try:
        validated = validate_residual_run_context(context)
        payload, digest = recompute_residual_run_context_binding(validated)
    except (TypeError, ValueError) as exc:
        raise ResidualWorldError("residual run context is invalid") from exc
    if (
        payload.get("protocol_id") != PROTOCOL_ID
        or payload.get("protocol_sha256") != PROTOCOL_DOCUMENT_SHA256
        or payload.get("amendment_id") != PROTOCOL_AMENDMENT_ID
        or payload.get("amendment_sha256") != PROTOCOL_AMENDMENT_SHA256
    ):
        raise ResidualWorldError(
            "residual run context differs from the frozen protocol law"
        )
    return validated, tuple(payload.items()), digest


def _validate_run_context_binding(
    context: ResidualRunContext,
    stored_payload: tuple[tuple[str, object], ...],
    stored_sha256: str,
) -> tuple[ResidualRunContext, dict[str, object], str]:
    """Recompute one stored context receipt without trusting tuple/digest."""
    if not isinstance(stored_payload, tuple) or any(
        not isinstance(row, tuple)
        or len(row) != 2
        or not isinstance(row[0], str)
        for row in stored_payload
    ):
        raise ResidualWorldError("stored residual run-context payload is malformed")
    names = tuple(row[0] for row in stored_payload)
    if len(names) != len(set(names)):
        raise ResidualWorldError("stored residual run-context payload repeats a field")
    stored_mapping = dict(stored_payload)
    try:
        validated = validate_residual_run_context_binding(
            context,
            expected_payload=stored_mapping,
            expected_sha256=stored_sha256,
        )
        reconstructed, digest = recompute_residual_run_context_binding(
            validated
        )
    except (TypeError, ValueError) as exc:
        raise ResidualWorldError(
            "stored residual run-context binding differs from reconstruction"
        ) from exc
    if tuple(reconstructed.items()) != stored_payload:
        raise ResidualWorldError(
            "stored residual run-context field order or values changed"
        )
    if (
        reconstructed.get("protocol_id") != PROTOCOL_ID
        or reconstructed.get("protocol_sha256") != PROTOCOL_DOCUMENT_SHA256
        or reconstructed.get("amendment_id") != PROTOCOL_AMENDMENT_ID
        or reconstructed.get("amendment_sha256")
        != PROTOCOL_AMENDMENT_SHA256
    ):
        raise ResidualWorldError(
            "stored residual run context differs from the frozen protocol law"
        )
    return validated, reconstructed, digest


def prepared_fold_scientific_payload(
    prepared: PreparedFoldReservoir,
) -> dict[str, object]:
    """Return the path/time-free immutable preparation identity."""
    if not isinstance(prepared, PreparedFoldReservoir):
        raise ResidualWorldError("prepared fold receipt has the wrong type")
    _, run_context_payload, run_context_sha256 = _validate_run_context_binding(
        prepared.run_context,
        prepared.run_context_payload,
        prepared.run_context_sha256,
    )
    if prepared.control_score_parity.sha256 != (
        prepared.control_score_parity_sha256
    ):
        raise ResidualWorldError("control score-parity receipt hash changed")
    spec = _fold_spec(prepared.fold_name)
    if prepared.fold_sha256 != _fold_sha256(spec):
        raise ResidualWorldError("prepared fold definition hash changed")
    control_candidates = tuple(
        canonical_identity(identity) for identity in prepared.control_candidates
    )
    native_candidate_count = len(control_candidates)
    if (
        native_candidate_count < ENTRY_COUNT + K_MAX
        or control_candidates != prepared.control_candidates
        or len(set(control_candidates)) != native_candidate_count
        or _identities_sha256(control_candidates)
        != prepared.control_candidates_sha256
    ):
        raise ResidualWorldError(
            "prepared native candidate pool identity changed"
        )
    control_source_tags = _source_tags(
        prepared.control_source_tags, native_candidate_count
    )
    if (
        _source_tags_sha256(control_source_tags)
        != prepared.control_source_tags_sha256
    ):
        raise ResidualWorldError("prepared control source-tag hash changed")
    control_book = tuple(
        canonical_identity(identity) for identity in prepared.control_book
    )
    if (
        control_book != prepared.control_book
        or len(control_book) != ENTRY_COUNT
        or len(set(control_book)) != ENTRY_COUNT
        or not set(control_book) <= set(control_candidates)
        or _identities_sha256(control_book) != prepared.control_book_sha256
    ):
        raise ResidualWorldError("prepared control book hash changed")
    pruning = prepared.pruning
    removal_order = tuple(
        canonical_identity(identity) for identity in pruning.removal_order
    )
    if (
        pruning.original_candidates != native_candidate_count
        or len(pruning.steps) != K_MAX
        or tuple(step.dose for step in pruning.steps)
        != tuple(range(1, K_MAX + 1))
        or tuple(step.remaining_candidates for step in pruning.steps)
        != tuple(pruning.original_candidates - dose for dose in range(1, K_MAX + 1))
        or removal_order != pruning.removal_order
        or len(set(removal_order)) != K_MAX
        or not set(removal_order) <= set(control_candidates)
        or set(removal_order) & set(control_book)
    ):
        raise ResidualWorldError("prepared pruning receipt changed")
    selections = tuple(prepared.reservoir_selections)
    bounds = tuple(prepared.reservoir_bounds)
    if (
        len(selections) != FOLD_RESERVOIR_SIZE
        or len({value.world_id for value in selections}) != len(selections)
        or tuple(value.world_id for value in selections)
        != tuple(value.world_id for value in bounds)
        or _world_selections_sha256(selections)
        != prepared.reservoir_selections_sha256
        or _reservoir_sha256(selections, bounds) != prepared.reservoir_sha256
    ):
        raise ResidualWorldError("prepared residual reservoir hash changed")
    payload: dict[str, object] = {
        "protocol_id": PROTOCOL_ID,
        "protocol_document_sha256": PROTOCOL_DOCUMENT_SHA256,
        "protocol_amendment_id": PROTOCOL_AMENDMENT_ID,
        "protocol_amendment_sha256": PROTOCOL_AMENDMENT_SHA256,
        "run_context": run_context_payload,
        "run_context_sha256": run_context_sha256,
        "fold_name": prepared.fold_name,
        "fold_sha256": prepared.fold_sha256,
        "native_candidate_count": native_candidate_count,
        "world_ids_sha256": prepared.world_ids_sha256,
        "player_catalog_sha256": prepared.player_catalog_sha256,
        "player_draws_sha256": prepared.player_draws_sha256,
        "control_candidates_sha256": prepared.control_candidates_sha256,
        "control_source_tags_sha256": prepared.control_source_tags_sha256,
        "control_selector_totals_sha256": (
            prepared.control_selector_totals_sha256
        ),
        "control_micro_totals_sha256": prepared.control_micro_totals_sha256,
        "control_score_parity": _score_parity_scientific_receipt(
            prepared.control_score_parity
        ),
        "control_score_parity_sha256": prepared.control_score_parity_sha256,
        "control_book_sha256": prepared.control_book_sha256,
        "pruning": _pruning_scientific_receipt(prepared.pruning),
        "reservoir_selections_sha256": (
            prepared.reservoir_selections_sha256
        ),
        "reservoir_sha256": prepared.reservoir_sha256,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
    }
    validate_unlicensed_scientific_payload(payload)
    return payload


def prepared_fold_sha256(prepared: PreparedFoldReservoir) -> str:
    return _canonical_json_sha256(prepared_fold_scientific_payload(prepared))


def _pricing_input_sha256(
    players: Sequence[PlayerSpec],
    scores_micro: np.ndarray,
    book_maxima_micro: np.ndarray,
    lower_bounds_micro: np.ndarray,
    upper_bounds_micro: np.ndarray,
    thresholds_micro: Sequence[int],
    complete_no_goods: Sequence[Sequence[object]],
) -> str:
    return _canonical_json_sha256({
        "player_catalog_sha256": _player_catalog_sha256(players),
        "scores_micro_sha256": _array_sha256(
            np.asarray(scores_micro, dtype=np.int64)
        ),
        "book_maxima_micro_sha256": _array_sha256(
            np.asarray(book_maxima_micro, dtype=np.int64)
        ),
        "lower_bounds_micro_sha256": _array_sha256(
            np.asarray(lower_bounds_micro, dtype=np.int64)
        ),
        "upper_bounds_micro_sha256": _array_sha256(
            np.asarray(upper_bounds_micro, dtype=np.int64)
        ),
        "thresholds_micro": list(_threshold_tuple(thresholds_micro)),
        "complete_no_goods_sha256": _identities_sha256(complete_no_goods),
    })


def _reservoir_sha256(
    selections: Sequence[WorldSelection], bounds: Sequence[WorldLegalBound]
) -> str:
    return _canonical_json_sha256({
        "selection_sha256": _world_selections_sha256(selections),
        "bounds": [{
        "world_id": [bound.world_id.block, bound.world_id.index],
        "lower_micro": bound.lower_micro,
        "upper_micro": bound.upper_micro,
        "lower_roster": list(bound.lower_roster),
        "upper_roster": list(bound.upper_roster),
        "lower_evidence": [
            _cbc_scientific_receipt(evidence)
            for evidence in bound.lower_evidence
        ],
        "upper_evidence": [
            _cbc_scientific_receipt(evidence)
            for evidence in bound.upper_evidence
        ],
        } for bound in bounds],
    })


def _cbc_scientific_receipt(evidence: CbcSolveEvidence) -> dict[str, object]:
    """Path/time-free exact-solver identity for deterministic payloads."""
    payload: dict[str, object] = {
        "solve_label": evidence.solve_label,
        "model_sha256": evidence.model_sha256,
        "mip_start_sha256": evidence.mip_start_sha256,
        "mip_start_values_sha256": evidence.mip_start_values_sha256,
        "mip_start_renamed_values_sha256": (
            evidence.mip_start_renamed_values_sha256
        ),
        "mip_start_variable_count": evidence.mip_start_variable_count,
        "predecessor_assignment_sha256": (
            evidence.predecessor_assignment_sha256
        ),
        "mip_start_reconstructed_objective": (
            evidence.mip_start_reconstructed_objective
        ),
        "cbc_sha256": evidence.cbc_sha256,
        "cbc_version": evidence.cbc_version,
        "pulp_version": evidence.pulp_version,
        "pulp_status": evidence.pulp_status,
        "pulp_solution_status": evidence.pulp_solution_status,
        "objective": evidence.objective,
        "problem_sense": evidence.problem_sense,
        "max_seconds": evidence.max_seconds,
        "warm_start": evidence.warm_start,
        "cuts": evidence.cuts,
        "preprocess_off": evidence.preprocess_off,
        "random_seed": evidence.random_seed,
        "random_cbc_seed": evidence.random_cbc_seed,
        "threads": evidence.threads,
        "time_mode": evidence.time_mode,
        "relative_gap": str(evidence.relative_gap),
        "absolute_gap": str(evidence.absolute_gap),
        "primal_tolerance": str(evidence.primal_tolerance),
        "integer_tolerance": str(evidence.integer_tolerance),
        "integer_decode_epsilon": str(CBC_INTEGER_DECODE_EPS),
        "variable_domain_manifest_sha256": (
            evidence.variable_domain_manifest_sha256
        ),
        "canonical_assignment_sha256": (
            evidence.canonical_assignment_sha256
        ),
    }
    return payload


def bind_world_legal_bounds(
    world_ids: Sequence[WorldId], legal_bounds: LegalBounds
) -> tuple[WorldLegalBound, ...]:
    """Bind sorted world identities to exact bound witnesses/evidence.

    :func:`solve_legal_bounds` emits maximum then minimum evidence for each
    aligned score column.  This constructor is the only supported bridge into
    a prepared fold and preserves that ordering explicitly.
    """
    worlds = tuple(world_ids)
    n = len(worlds)
    if not isinstance(legal_bounds, LegalBounds):
        raise ResidualWorldError("reservoir legal bounds receipt is missing")
    if not (
        len(legal_bounds.lower_micro)
        == len(legal_bounds.upper_micro)
        == len(legal_bounds.lower_rosters)
        == len(legal_bounds.upper_rosters)
        == n
    ):
        raise ResidualWorldError("reservoir legal bounds are misaligned")
    if len(legal_bounds.solve_evidence) != 4 * n:
        raise ResidualWorldError(
            "reservoir legal bounds lack quotient/remainder solve evidence"
        )
    return tuple(WorldLegalBound(
        world_id=world,
        lower_micro=legal_bounds.lower_micro[index],
        upper_micro=legal_bounds.upper_micro[index],
        lower_roster=legal_bounds.lower_rosters[index],
        upper_roster=legal_bounds.upper_rosters[index],
        lower_evidence=legal_bounds.solve_evidence[4 * index + 2:4 * index + 4],
        upper_evidence=legal_bounds.solve_evidence[4 * index:4 * index + 2],
    ) for index, world in enumerate(worlds))


def _validate_roster_micro_parity(
    players: tuple[PlayerSpec, ...],
    raw_player_draws: np.ndarray,
    micro_player_draws: np.ndarray,
    identities: Sequence[Sequence[object]],
    selector_totals: np.ndarray,
    micro_totals: np.ndarray,
) -> ScoreParityReceipt:
    canonical_identities = tuple(
        canonical_identity(value) for value in identities
    )
    by_id = {player.player_id: index for index, player in enumerate(players)}
    world_count = raw_player_draws.shape[1]
    selector = np.asarray(selector_totals)
    micro_matrix = np.asarray(micro_totals)
    if selector.dtype != np.float32 or selector.shape != (
        len(canonical_identities), world_count
    ) or not np.isfinite(selector).all():
        raise ResidualWorldError(
            "candidate selector totals must be one aligned finite float32 matrix"
        )
    if micro_matrix.dtype != np.int64 or micro_matrix.shape != (
        len(canonical_identities), world_count
    ):
        raise ResidualWorldError(
            "candidate micro totals must be one aligned int64 matrix"
        )
    thresholds = np.asarray(TAIL_THRESHOLDS_MICRO, dtype=np.int64)
    raw64_rows: list[np.ndarray] = []
    selector_indicator_rows: list[np.ndarray] = []
    raw64_indicator_rows: list[np.ndarray] = []
    micro_indicator_rows: list[np.ndarray] = []
    maximum_error = 0.0
    for roster_index, identity in enumerate(canonical_identities):
        if not set(identity) <= set(by_id):
            raise ResidualWorldError("candidate roster is outside player catalog")
        indices = np.asarray([
            index for index, player in enumerate(players)
            if player.player_id in identity
        ])
        canonical_selector = raw_player_draws[indices].sum(
            axis=0
        ).astype(np.float32)
        if not np.array_equal(canonical_selector, selector[roster_index]):
            raise ResidualWorldError(
                "candidate selector totals do not reconstruct canonically"
            )
        raw64 = raw_player_draws[indices].astype(np.float64).sum(axis=0)
        micro = micro_player_draws[indices].sum(axis=0, dtype=np.int64)
        if not np.array_equal(micro, micro_matrix[roster_index]):
            raise ResidualWorldError("candidate micro totals do not reconstruct")
        difference = np.abs(raw64 - micro / MICRO_DK_SCALE)
        maximum_error = max(
            maximum_error, float(difference.max(initial=0.0))
        )
        if maximum_error > RAW_MICRO_MAX_ERROR_DK:
            raise ResidualWorldError("candidate raw/micro parity exceeds exact bound")
        selector_bits = selector[roster_index, :, None] >= (
            thresholds.astype(np.float64) / MICRO_DK_SCALE
        )
        raw64_bits = raw64[:, None] >= (
            thresholds.astype(np.float64) / MICRO_DK_SCALE
        )
        micro_bits = micro[:, None] >= thresholds
        if not (
            np.array_equal(selector_bits, raw64_bits)
            and np.array_equal(raw64_bits, micro_bits)
        ):
            raise ResidualWorldError(
                "selector/raw/micro registered-threshold indicators disagree"
            )
        for threshold in thresholds:
            if not np.array_equal(
                raw64 >= int(threshold) / MICRO_DK_SCALE,
                micro >= int(threshold),
            ):
                raise ResidualWorldError(
                    "candidate raw/micro threshold indicators disagree"
                )
        raw64_rows.append(raw64)
        selector_indicator_rows.append(selector_bits)
        raw64_indicator_rows.append(raw64_bits)
        micro_indicator_rows.append(micro_bits)
    if raw64_rows:
        raw64_matrix = np.stack(raw64_rows).astype(np.float64, copy=False)
        selector_indicators = np.stack(selector_indicator_rows)
        raw64_indicators = np.stack(raw64_indicator_rows)
        micro_indicators = np.stack(micro_indicator_rows)
    else:
        raw64_matrix = np.empty((0, world_count), dtype=np.float64)
        indicator_shape = (0, world_count, len(thresholds))
        selector_indicators = np.empty(indicator_shape, dtype=bool)
        raw64_indicators = np.empty(indicator_shape, dtype=bool)
        micro_indicators = np.empty(indicator_shape, dtype=bool)
    return ScoreParityReceipt(
        float64_totals_sha256=_array_sha256(raw64_matrix),
        selector_thresholds_sha256=_array_sha256(selector_indicators),
        float64_thresholds_sha256=_array_sha256(raw64_indicators),
        micro_thresholds_sha256=_array_sha256(micro_indicators),
        max_raw_micro_error_hex=maximum_error.hex(),
    )


def prepare_fold_reservoir(
    fold_name: str,
    players: Sequence[PlayerSpec | Mapping[str, object]],
    world_ids: Sequence[WorldId],
    raw_player_draws: np.ndarray,
    control_identities: Sequence[Sequence[object]],
    control_source_tags: Sequence[Sequence[object]],
    control_selector_totals: np.ndarray,
    control_micro_totals: np.ndarray,
    reservoir_bounds: Sequence[WorldLegalBound],
    *,
    run_context: ResidualRunContext,
) -> PreparedFoldReservoir:
    """Freeze Q_C, all-eight pruning, and exact 96-world reservoir bindings."""
    (
        frozen_run_context,
        run_context_payload,
        run_context_sha256,
    ) = _freeze_run_context_binding(run_context)
    spec = _fold_spec(fold_name)
    rows = _players(players)
    worlds = _exact_world_order(world_ids)
    raw = _player_draw_matrix(raw_player_draws, len(rows), len(worlds))
    player_micro = to_micro_dk(raw)
    controls = tuple(canonical_identity(value) for value in control_identities)
    if len(controls) < ENTRY_COUNT + K_MAX or len(set(controls)) != len(controls):
        raise ResidualWorldError(
            "control pool must contain at least 88 unique canonical identities"
        )
    for identity in controls:
        audit_legal_identity(rows, identity)
    source_tags = _source_tags(control_source_tags, len(controls))
    selector_totals = _selector_matrix(
        control_selector_totals, len(controls), len(worlds)
    )
    micro_totals = _micro_matrix(
        control_micro_totals, rows=len(controls), label="control micro totals"
    )
    if micro_totals.shape[1] != len(worlds):
        raise ResidualWorldError("control micro totals have the wrong world count")
    reconstructed_selector, reconstructed_micro = _cross_score_rosters(
        rows, raw, player_micro, controls
    )
    if not np.array_equal(reconstructed_selector, selector_totals):
        raise ResidualWorldError(
            "control selector totals differ from canonical float32 reconstruction"
        )
    if not np.array_equal(reconstructed_micro, micro_totals):
        raise ResidualWorldError("control micro totals differ from reconstruction")
    parity_receipt = _validate_roster_micro_parity(
        rows, raw, player_micro, controls, selector_totals, micro_totals
    )

    construction_columns = np.asarray([
        index for index, world in enumerate(worlds)
        if world.block in spec.construction_blocks
    ], dtype=int)
    control_book, selected_rows = _select_exact_book(
        controls, selector_totals, construction_columns
    )
    pruning = reverse_greedy_pruning_order(
        controls,
        micro_totals[:, construction_columns],
        control_book,
        steps=K_MAX,
        expected_protected_count=ENTRY_COUNT,
    )
    if len(pruning.steps) != K_MAX:
        raise ResidualWorldError("prepared pruning does not contain all eight doses")

    initial_maxima = micro_totals[
        np.asarray(selected_rows, dtype=int)[:, None], construction_columns
    ].max(axis=0)
    relaxed_upper = position_shape_upper_bounds_micro(
        player_micro[:, construction_columns],
        [player.position for player in rows],
    )
    construction_worlds = tuple(worlds[index] for index in construction_columns)
    expected_reservoir = select_block_stratified_worlds(
        construction_worlds,
        initial_maxima,
        relaxed_upper,
        tuple(
            (block, spec.reservoir_per_block)
            for block in spec.construction_blocks
        ),
    )
    expected_reservoir = _audit_block_selection(
        expected_reservoir,
        construction_worlds,
        initial_maxima,
        relaxed_upper,
        tuple(
            (block, spec.reservoir_per_block)
            for block in spec.construction_blocks
        ),
    )
    bounds = tuple(reservoir_bounds)
    if len(bounds) != FOLD_RESERVOIR_SIZE:
        raise ResidualWorldError("prepared fold reservoir is not exact-96")
    if tuple(bound.world_id for bound in bounds) != tuple(
        selection.world_id for selection in expected_reservoir
    ):
        raise ResidualWorldError(
            "prepared reservoir differs from deterministic relaxed selection"
        )
    if len({bound.world_id for bound in bounds}) != len(bounds):
        raise ResidualWorldError("prepared reservoir world identities repeat")
    for block in spec.construction_blocks:
        if sum(bound.world_id.block == block for bound in bounds) != (
            spec.reservoir_per_block
        ):
            raise ResidualWorldError("prepared reservoir block quota is wrong")
    _validate_bound_receipts(
        rows,
        player_micro,
        worlds,
        bounds,
    )

    return PreparedFoldReservoir(
        fold_name=spec.name,
        run_context=frozen_run_context,
        run_context_payload=run_context_payload,
        run_context_sha256=run_context_sha256,
        fold_sha256=_fold_sha256(spec),
        world_ids_sha256=_world_ids_sha256(worlds),
        player_catalog_sha256=_player_catalog_sha256(rows),
        player_draws_sha256=_array_sha256(raw),
        control_candidates=controls,
        control_candidates_sha256=_identities_sha256(controls),
        control_source_tags=source_tags,
        control_source_tags_sha256=_source_tags_sha256(source_tags),
        control_selector_totals_sha256=_array_sha256(selector_totals),
        control_micro_totals_sha256=_array_sha256(micro_totals),
        control_score_parity=parity_receipt,
        control_score_parity_sha256=parity_receipt.sha256,
        control_book=control_book,
        control_book_sha256=_identities_sha256(control_book),
        pruning=pruning,
        reservoir_selections=expected_reservoir,
        reservoir_selections_sha256=_world_selections_sha256(
            expected_reservoir
        ),
        reservoir_bounds=bounds,
        reservoir_sha256=_reservoir_sha256(expected_reservoir, bounds),
    )


def _materialize_treatment_scores(
    controls: tuple[tuple[str, ...], ...],
    control_selector_totals: np.ndarray,
    control_micro_totals: np.ndarray,
    pruning: PruningResult,
    generated: tuple[tuple[str, ...], ...],
    generated_selector_totals: Sequence[np.ndarray],
    generated_micro_totals: Sequence[np.ndarray],
) -> tuple[tuple[tuple[str, ...], ...], np.ndarray, np.ndarray]:
    identities = matched_budget_treatment_pool(controls, pruning, generated)
    removed = set(pruning.removal_order[:len(generated)])
    retained_indices = [
        index for index, identity in enumerate(controls) if identity not in removed
    ]
    selector_blocks = [control_selector_totals[retained_indices]]
    micro_blocks = [control_micro_totals[retained_indices]]
    if generated:
        selector_blocks.append(np.stack(generated_selector_totals))
        micro_blocks.append(np.stack(generated_micro_totals))
    selector = np.concatenate(selector_blocks, axis=0).astype(
        np.float32, copy=False
    )
    micro = np.concatenate(micro_blocks, axis=0).astype(np.int64, copy=False)
    if selector.shape[0] != len(controls) or micro.shape[0] != len(controls):
        raise ResidualWorldError("materialized treatment does not preserve exact B")
    return identities, selector, micro


def _readonly_copy(values: np.ndarray) -> np.ndarray:
    result = np.array(values, copy=True, order="C")
    result.flags.writeable = False
    return result


def _exact_model_bound(value: object, label: str) -> int | None:
    if value is None:
        return None
    try:
        parsed = Decimal(str(value))
    except InvalidOperation as exc:
        raise SolverFailure(f"{label} is not an exact integer") from exc
    if (
        not parsed.is_finite()
        or parsed != parsed.to_integral_value()
        or abs(parsed) >= CBC_EXACT_INTEGER_MAX + 1
    ):
        raise SolverFailure(f"{label} is outside the exact integer profile")
    return int(parsed)


def _materialize_zero_objective(problem: pulp.LpProblem) -> None:
    """Prevent PuLP from silently injecting an unregistered ``__dummy``.

    A genuinely constant-zero objective remains mathematically identical, but
    is represented by one deterministic fixed integer column and anchor row
    before the domain manifest is frozen or MPS bytes are written.
    """
    objective = problem.objective
    if objective is None:
        objective = pulp.LpAffineExpression()
        problem.setObjective(objective)
    constant = _exact_model_bound(objective.constant, "objective constant")
    if constant != 0:
        raise SolverFailure("frozen residual objective has a nonzero constant")
    if tuple(objective.items()):
        return
    variable_name = "residual_explicit_zero_objective"
    constraint_name = "residual_explicit_zero_objective_anchor"
    if any(variable.name == variable_name for variable in problem.variables()) or (
        constraint_name in problem.constraints
    ):
        raise SolverFailure("explicit zero objective symbol was partially reused")
    variable = pulp.LpVariable(
        variable_name, lowBound=0, upBound=0, cat="Integer"
    )
    problem += variable == 0, constraint_name
    problem.setObjective(variable)


def _prove_implied_integer_names(problem: pulp.LpProblem) -> set[str]:
    """Prove every registered continuous auxiliary integer by induction."""
    variables = {variable.name: variable for variable in problem.variables()}
    implied = set(getattr(problem, "_residual_implied_integer_names", set()))
    if not implied <= set(variables):
        raise SolverFailure("implied-integer manifest references an unknown variable")
    proven = {
        name for name, variable in variables.items()
        if variable.cat == pulp.LpInteger
        or (
            _exact_model_bound(variable.lowBound, "fixed lower bound") is not None
            and _exact_model_bound(variable.lowBound, "fixed lower bound")
            == _exact_model_bound(variable.upBound, "fixed upper bound")
        )
    }
    unresolved = set(implied)
    while unresolved:
        advanced = False
        for name in sorted(unresolved):
            variable = variables[name]
            for constraint in problem.constraints.values():
                if constraint.sense != pulp.LpConstraintEQ:
                    continue
                coefficient = constraint.get(variable, 0)
                exact_coefficient = _exact_model_bound(
                    coefficient, "implied-integer defining coefficient"
                )
                if exact_coefficient not in {-1, 1}:
                    continue
                if _exact_model_bound(
                    -constraint.constant, "implied-integer defining RHS"
                ) is None:
                    continue
                other_names: set[str] = set()
                valid = True
                for source, raw_coefficient in constraint.items():
                    exact = _exact_model_bound(
                        raw_coefficient, "implied-integer source coefficient"
                    )
                    if exact is None:
                        valid = False
                        break
                    if source.name != name and exact != 0:
                        other_names.add(source.name)
                if valid and other_names <= proven:
                    proven.add(name)
                    unresolved.remove(name)
                    advanced = True
                    break
        if not advanced:
            raise SolverFailure(
                "implied-integer auxiliary lacks an acyclic exact defining row"
            )
    return implied


def _variable_domain_manifest(
    problem: pulp.LpProblem,
) -> tuple[tuple[str, str, str, int | None, int | None], ...]:
    """Bind PuLP scientific names/domains to deterministic renamed columns."""
    _materialize_zero_objective(problem)
    variables = tuple(problem.variables())
    implied = _prove_implied_integer_names(problem)
    rows: list[tuple[str, str, str, int | None, int | None]] = []
    observed_implied: set[str] = set()
    for index, variable in enumerate(variables):
        lower = _exact_model_bound(variable.lowBound, "variable lower bound")
        upper = _exact_model_bound(variable.upBound, "variable upper bound")
        if lower is not None and upper is not None and lower > upper:
            raise SolverFailure("variable domain has reversed exact bounds")
        if variable.cat == pulp.LpInteger:
            domain = "binary" if variable.isBinary() else "integer"
        elif variable.name in implied:
            domain = "implied_integer"
            observed_implied.add(variable.name)
        elif lower is not None and lower == upper:
            domain = "fixed_integer"
        else:
            raise SolverFailure(
                "frozen residual model has an unregistered continuous column"
            )
        rows.append((
            f"X{index:07d}", variable.name, domain, lower, upper,
        ))
    if observed_implied != implied:
        raise SolverFailure("implied-integer manifest category changed")
    if not rows or len({row[0] for row in rows}) != len(rows) or len({
        row[1] for row in rows
    }) != len(rows):
        raise SolverFailure("variable domain manifest is not bijective")
    return tuple(rows)


def _variable_domain_manifest_sha256(
    manifest: Sequence[tuple[str, str, str, int | None, int | None]],
) -> str:
    return _canonical_json_sha256(_variable_domain_manifest_payload(manifest))


def _variable_domain_manifest_payload(
    manifest: Sequence[tuple[str, str, str, int | None, int | None]],
) -> list[list[object]]:
    return [list(row) for row in manifest]


def _problem_mps_receipt(problem: pulp.LpProblem) -> tuple[str, str]:
    """Serialize one model and bind its renamed/scientific domain manifest."""
    manifest = _variable_domain_manifest(problem)
    with tempfile.TemporaryDirectory(prefix="residual_pricing_receipt_") as path:
        model_path = Path(path) / "model.mps"
        problem.writeMPS(str(model_path), rename=1)
        parsed = _parse_exact_mps(model_path)
        _validate_problem_matches_mps(problem, parsed, manifest)
        return (
            _sha256_file(model_path),
            _variable_domain_manifest_sha256(manifest),
        )


def _expected_pricing_model_receipts(
    players: tuple[PlayerSpec, ...],
    scores_micro: np.ndarray,
    book_maxima_micro: np.ndarray,
    lower_bounds_micro: np.ndarray,
    upper_bounds_micro: np.ndarray,
    thresholds_micro: tuple[int, ...],
    complete_no_goods: tuple[tuple[str, ...], ...],
    pricing: PricingResult,
) -> tuple[tuple[str, str, str], ...]:
    """Rebuild every solved pricing face and return ordered MPS identities.

    This reconstruction never consumes a PuLP solution value.  It derives all
    frozen tier/chunk/rank/incidence equalities from the independently audited
    :class:`PricingResult` and raw integer inputs, so a valid but unrelated CBC
    solve cannot be substituted by matching only its label/objective/options.
    Initial values are deliberately omitted: PuLP does not serialize them in
    MPS, while their complete retained MST receipt is checked separately.
    """
    model = build_legal_lineup_model(
        players,
        name="residual_world_pricing",
        forbidden_rosters=complete_no_goods,
    )
    n_worlds = scores_micro.shape[1]
    binary_scores = [
        _binary_score_number(
            model,
            scores_micro[:, world],
            name=f"pricing_score_{world:04d}",
        )
        for world in range(n_worlds)
    ]
    tier_expressions: list[pulp.LpAffineExpression] = []
    tier_variable_counts: list[int] = []
    for tier_index, threshold in enumerate(thresholds_micro):
        variables: list[pulp.LpVariable] = []
        for world in range(n_worlds):
            if not (
                int(book_maxima_micro[world]) < threshold
                <= int(upper_bounds_micro[world])
            ):
                continue
            score_number, score_offset = binary_scores[world]
            variables.append(_binary_ge_indicator(
                model.problem,
                score_number,
                threshold - score_offset,
                name=f"tail_{tier_index:02d}_{world:04d}",
            ))
        tier_expressions.append(pulp.lpSum(variables))
        tier_variable_counts.append(len(variables))

    receipts: list[tuple[str, str, str]] = []
    for tier_index, expression in enumerate(tier_expressions):
        if tier_variable_counts[tier_index] == 0:
            continue
        label = f"pricing tier tail_{tier_index:02d}"
        model.problem.sense = pulp.LpMaximize
        model.problem.setObjective(expression)
        model_sha, manifest_sha = _problem_mps_receipt(model.problem)
        receipts.append((label, model_sha, manifest_sha))
        model.problem += expression == pricing.marginal_threshold_counts[
            tier_index
        ], f"freeze_tail_{tier_index:02d}"

    score_variables = [
        _score_expression(model, scores_micro[:, world])
        for world in range(n_worlds)
    ]
    residual_expressions: list[pulp.LpAffineExpression | pulp.LpVariable] = []
    for world, score in enumerate(score_variables):
        residual, _ = _add_exact_product_positive_part(
            model,
            score,
            binary_scores[world][0],
            binary_scores[world][1],
            scores_micro[:, world],
            int(lower_bounds_micro[world]),
            int(upper_bounds_micro[world]),
            int(book_maxima_micro[world]),
            name=f"world_{world:04d}",
            initial_roster=None,
        )
        residual_expressions.append(residual)
    residual_upper = sum(
        max(0, int(upper_bounds_micro[world]) - int(book_maxima_micro[world]))
        for world in range(n_worlds)
    )
    if residual_upper:
        residual_sum = pulp.lpSum(residual_expressions)
        residual_number = _binary_weighted_sum(
            model.problem,
            tuple(
                (variable, int(coefficient))
                for variable, coefficient in residual_sum.items()
            ),
            upper_bound=residual_upper,
            name="residual_gain_total",
            initialize_from_sources=False,
        )
        chunk_values = _residual_chunk_values(
            pricing.residual_gain_micro,
            residual_upper,
            bit_width=len(residual_number.bits),
        )
        chunk_mask = _residual_chunk_solver_mask(
            pricing.residual_gain_micro,
            residual_upper,
            bit_width=len(residual_number.bits),
        )
        for chunk_index, (expression, optimum, needs_solver) in enumerate(zip(
            _binary_objective_chunks(residual_number),
            chunk_values,
            chunk_mask,
            strict=True,
        )):
            if needs_solver:
                label = f"pricing tier residual_gain chunk {chunk_index:02d}"
                model.problem.sense = pulp.LpMaximize
                model.problem.setObjective(expression)
                model_sha, manifest_sha = _problem_mps_receipt(model.problem)
                receipts.append((label, model_sha, manifest_sha))
            model.problem += expression == optimum, (
                f"freeze_residual_gain_chunk_{chunk_index:02d}"
            )

    rank = {
        player_id: index + 1
        for index, player_id in enumerate(sorted(model.decision))
    }
    rank_expression = pulp.lpSum(
        model.decision[player.player_id] * rank[player.player_id]
        for player in model.players
    )
    model.problem.sense = pulp.LpMinimize
    model.problem.setObjective(rank_expression)
    model_sha, manifest_sha = _problem_mps_receipt(model.problem)
    receipts.append((
        "pricing tier canonical_rank_sum", model_sha, manifest_sha,
    ))
    model.problem += rank_expression == pricing.rank_sum, (
        "freeze_canonical_rank_sum"
    )

    first = audit_legal_identity(players, pricing.rank_first_roster)
    probe = _clone_residual_problem(model.problem)
    overlap = pulp.lpSum(model.decision[player_id] for player_id in first)
    probe.sense = pulp.LpMinimize
    probe.setObjective(overlap)
    model_sha, manifest_sha = _problem_mps_receipt(probe)
    receipts.append((
        "canonical ambiguity distance", model_sha, manifest_sha,
    ))

    if pricing.rank_sum_ambiguous:
        fixed_ones = 0
        player_ids = sorted(model.decision)
        index = 0
        while index < len(player_ids):
            remaining = len(player_ids) - index
            needed = ROSTER_SIZE - fixed_ones
            if needed == 0:
                for player_id in player_ids[index:]:
                    model.problem += model.decision[player_id] == 0, (
                        f"canonical_incidence_{index:04d}"
                    )
                    index += 1
                break
            if needed == remaining:
                for player_id in player_ids[index:]:
                    model.problem += model.decision[player_id] == 1, (
                        f"canonical_incidence_{index:04d}"
                    )
                    fixed_ones += 1
                    index += 1
                break
            chunk = player_ids[index:index + RESIDUAL_OBJECTIVE_CHUNK_BITS]
            expression = pulp.lpSum(
                model.decision[player_id] * (
                    1 << (len(chunk) - offset - 1)
                )
                for offset, player_id in enumerate(chunk)
            )
            model.problem.sense = pulp.LpMaximize
            model.problem.setObjective(expression)
            model_sha, manifest_sha = _problem_mps_receipt(model.problem)
            receipts.append((
                f"canonical incidence chunk {index:04d}",
                model_sha,
                manifest_sha,
            ))
            for offset, player_id in enumerate(chunk):
                bit = int(player_id in pricing.roster)
                model.problem += model.decision[player_id] == bit, (
                    f"canonical_incidence_{index + offset:04d}"
                )
                fixed_ones += bit
            index += len(chunk)
    return tuple(receipts)


def _rank_identity_from_solve_evidence(
    evidence: CbcSolveEvidence,
    players: tuple[PlayerSpec, ...],
    complete_no_goods: tuple[tuple[str, ...], ...],
) -> tuple[str, ...]:
    """Decode the rank solve's exact roster from its retained assignment.

    The ambiguity model is constructed relative to ``rank_first_roster``.
    Therefore that identity cannot be accepted merely because its claimed
    rank sum is correct: it must be the binary decision assignment proven by
    the immediately preceding canonical-rank solve.
    """
    model = build_legal_lineup_model(
        players,
        name="residual_world_rank_assignment_audit",
        forbidden_rosters=complete_no_goods,
    )
    assignment_rows = _scientific_assignment_from_evidence(evidence)
    assignment = dict(assignment_rows)
    if len(assignment) != len(assignment_rows):
        raise ResidualWorldError("pricing rank evidence repeats a variable")
    selected: list[str] = []
    for player_id, variable in model.decision.items():
        value = assignment.get(variable.name)
        if value not in {0, 1}:
            raise ResidualWorldError(
                "pricing rank evidence lacks an exact binary decision"
            )
        if value == 1:
            selected.append(player_id)
    try:
        return audit_legal_identity(players, selected)
    except ResidualWorldError as exc:
        raise ResidualWorldError(
            "pricing rank evidence does not decode one legal roster"
        ) from exc


def _audit_rank_ambiguity_evidence_bindings(
    pricing: PricingResult,
    rank_receipt: CbcSolveEvidence,
    ambiguity_receipt: CbcSolveEvidence,
    players: tuple[PlayerSpec, ...],
    complete_no_goods: tuple[tuple[str, ...], ...],
) -> None:
    """Bind both tie receipts to the claimed rank-first identity/distance."""
    if _rank_identity_from_solve_evidence(
        rank_receipt, players, complete_no_goods
    ) != pricing.rank_first_roster:
        raise ResidualWorldError(
            "pricing first rank-optimal roster differs from rank evidence"
        )
    if ambiguity_receipt.objective != (
        ROSTER_SIZE - pricing.ambiguity_distance
    ):
        raise ResidualWorldError(
            "pricing ambiguity distance differs from ambiguity evidence"
        )


def _audit_pricing_evidence_semantics(
    pricing: PricingResult,
    players: tuple[PlayerSpec, ...],
    maxima: np.ndarray,
    lower: np.ndarray,
    upper: np.ndarray,
    complete_no_goods: tuple[tuple[str, ...], ...],
    scores_micro: np.ndarray,
    evidence_root: Path,
) -> None:
    expected_input = _pricing_input_sha256(
        players,
        scores_micro,
        maxima,
        lower,
        upper,
        TAIL_THRESHOLDS_MICRO,
        complete_no_goods,
    )
    if pricing.pricing_input_sha256 != expected_input:
        raise ResidualWorldError("pricing evidence input binding changed")

    semantics: list[tuple[str, int, bool, bool | None, bool]] = []
    have_tail = False
    for tier_index, threshold in enumerate(TAIL_THRESHOLDS_MICRO):
        if any(
            int(maxima[world]) < threshold <= int(upper[world])
            for world in range(len(maxima))
        ):
            warm = have_tail
            semantics.append((
                f"pricing tier tail_{tier_index:02d}",
                pricing.marginal_threshold_counts[tier_index],
                warm,
                None if warm else False,
                False,
            ))
            have_tail = True
    if np.any(upper > maxima):
        residual_upper = sum(
            max(0, int(upper[world]) - int(maxima[world]))
            for world in range(len(maxima))
        )
        coefficient_width = max(
            max(
                max(abs(int(value)) for value in scores_micro[:, world]),
                abs(int(maxima[world])),
            )
            for world in range(len(maxima))
            if int(upper[world]) > int(maxima[world])
        )
        residual_width = max(
            1, residual_upper.bit_length(), coefficient_width.bit_length()
        )
        chunk_values = _residual_chunk_values(
            pricing.residual_gain_micro,
            residual_upper,
            bit_width=residual_width,
        )
        chunk_solver_mask = _residual_chunk_solver_mask(
            pricing.residual_gain_micro,
            residual_upper,
            bit_width=residual_width,
        )
        for chunk_index, (objective, needs_solver) in enumerate(zip(
            chunk_values, chunk_solver_mask, strict=True
        )):
            if not needs_solver:
                continue
            semantics.append((
                f"pricing tier residual_gain chunk {chunk_index:02d}",
                objective,
                True,
                False,
                True,
            ))
    semantics.append((
        "pricing tier canonical_rank_sum",
        pricing.rank_sum,
        True,
        False,
        True,
    ))
    semantics.append((
        "canonical ambiguity distance",
        ROSTER_SIZE - pricing.ambiguity_distance,
        True,
        False,
        True,
    ))
    if pricing.rank_sum_ambiguous:
        player_ids = sorted(player.player_id for player in players)
        fixed_ones = 0
        index = 0
        while index < len(player_ids):
            remaining = len(player_ids) - index
            needed = ROSTER_SIZE - fixed_ones
            if needed in {0, remaining}:
                fixed_ones += needed
                break
            chunk = player_ids[
                index:index + RESIDUAL_OBJECTIVE_CHUNK_BITS
            ]
            objective = sum(
                int(player_id in pricing.roster) * (
                    1 << (len(chunk) - offset - 1)
                )
                for offset, player_id in enumerate(chunk)
            )
            semantics.append((
                f"canonical incidence chunk {index:04d}",
                objective,
                True,
                False,
                True,
            ))
            fixed_ones += sum(player_id in pricing.roster for player_id in chunk)
            index += len(chunk)

    evidence = pricing.solve_evidence
    if len(evidence) != len(semantics):
        raise ResidualWorldError("pricing evidence count changed")
    expected_models = _expected_pricing_model_receipts(
        players,
        scores_micro,
        maxima,
        lower,
        upper,
        TAIL_THRESHOLDS_MICRO,
        complete_no_goods,
        pricing,
    )
    if tuple(label for label, _, _ in expected_models) != tuple(
        label for label, *_ in semantics
    ):
        raise ResidualWorldError(
            "pricing reconstructed model sequence differs from semantic law"
        )
    resolved_root = evidence_root.resolve()
    paths: list[Path] = []
    prior_receipt: CbcSolveEvidence | None = None
    rank_receipt: CbcSolveEvidence | None = None
    ambiguity_receipt: CbcSolveEvidence | None = None
    for receipt, (label, objective, warm, cuts, preprocess), (
        model_label, model_sha256, manifest_sha256
    ) in zip(
        evidence, semantics, expected_models, strict=True
    ):
        validate_cbc_solve_evidence(receipt)
        if warm:
            if prior_receipt is None:
                raise ResidualWorldError(
                    "warm pricing evidence lacks an ordered predecessor"
                )
            _validate_ordered_warm_predecessor(prior_receipt, receipt)
        directory = Path(receipt.evidence_directory).resolve()
        if directory.parent != resolved_root:
            raise ResidualWorldError("pricing evidence is outside its run root")
        paths.extend(
            Path(value).resolve() for value in (
                receipt.evidence_directory,
                receipt.log_path,
                receipt.solution_path,
                receipt.model_path,
                receipt.variable_domain_manifest_path,
                receipt.mip_start_path,
            ) if value is not None
        )
        if (
            receipt.solve_label != label
            or model_label != label
            or receipt.model_sha256 != model_sha256
            or receipt.variable_domain_manifest_sha256 != manifest_sha256
            or receipt.objective != objective
            or receipt.max_seconds != PRICING_TIME_LIMIT_SECONDS
            or receipt.warm_start != warm
            or receipt.cuts is not cuts
            or receipt.preprocess_off != preprocess
            or (
                receipt.predecessor_assignment_sha256
                != (
                    prior_receipt.canonical_assignment_sha256
                    if warm and prior_receipt is not None
                    else None
                )
            )
        ):
            raise ResidualWorldError("pricing evidence semantic law changed")
        if label == "pricing tier canonical_rank_sum":
            rank_receipt = receipt
        elif label == "canonical ambiguity distance":
            ambiguity_receipt = receipt
        prior_receipt = receipt
    if len(paths) != len(set(paths)):
        raise ResidualWorldError("pricing evidence path or receipt is reused")
    if rank_receipt is None or ambiguity_receipt is None:
        raise ResidualWorldError("pricing rank/ambiguity evidence is missing")
    _audit_rank_ambiguity_evidence_bindings(
        pricing,
        rank_receipt,
        ambiguity_receipt,
        players,
        complete_no_goods,
    )


def _audit_evidence_root_inventory(
    evidence_root: Path, steps: Sequence[FoldDoseStep]
) -> None:
    receipts = tuple(
        evidence for step in steps for evidence in step.pricing.solve_evidence
    )
    resolved_root = _resolve_real_directory(
        Path(evidence_root), "pricing evidence root"
    )
    raw_directories = tuple(
        Path(evidence.evidence_directory) for evidence in receipts
    )
    directory_rows = tuple(path.resolve() for path in raw_directories)
    if any(
        path.is_symlink() or resolved.parent != resolved_root
        for path, resolved in zip(
            raw_directories, directory_rows, strict=True
        )
    ):
        raise ResidualWorldError("pricing evidence directory escaped its run root")
    if len(directory_rows) != len(set(directory_rows)):
        raise ResidualWorldError("pricing evidence directory is reused across doses")
    artifact_rows = tuple(
        Path(value).resolve() for evidence in receipts for value in (
            evidence.log_path,
            evidence.solution_path,
            evidence.model_path,
            evidence.variable_domain_manifest_path,
            evidence.mip_start_path,
        ) if value is not None
    )
    if len(artifact_rows) != len(set(artifact_rows)):
        raise ResidualWorldError("pricing evidence artifact is reused across doses")
    expected_directories = set(directory_rows)
    raw_children = tuple(resolved_root.iterdir())
    if any(child.is_symlink() for child in raw_children):
        raise ResidualWorldError("pricing evidence root contains a symlink")
    actual_children = {child.resolve() for child in raw_children}
    if actual_children != expected_directories or any(
        not child.is_dir() for child in actual_children
    ):
        raise ResidualWorldError("pricing evidence root inventory changed")
    for evidence in receipts:
        directory = Path(evidence.evidence_directory).resolve()
        raw_files = tuple(
            Path(value) for value in (
                evidence.log_path,
                evidence.solution_path,
                evidence.model_path,
                evidence.variable_domain_manifest_path,
                evidence.mip_start_path,
            ) if value is not None
        )
        expected_files = {path.resolve() for path in raw_files}
        if any(
            path.is_symlink() or path.resolve().parent != directory
            for path in raw_files
        ):
            raise ResidualWorldError(
                "pricing evidence artifact escaped its solve directory"
            )
        actual_files = tuple(directory.iterdir())
        if (
            any(child.is_symlink() for child in actual_files)
            or len(actual_files) != len(expected_files)
            or {child.resolve() for child in actual_files} != expected_files
        ):
            raise ResidualWorldError("pricing evidence directory inventory changed")
    # Re-open and re-hash every proof only after the complete inventory is
    # known, immediately before a scientific dose result may escape.  A solve
    # that was valid at its own step cannot license output if a later step
    # replaced any retained artifact.
    for evidence in receipts:
        validate_cbc_solve_evidence(evidence)


def _audit_pricing_result(
    pricing: PricingResult,
    players: tuple[PlayerSpec, ...],
    active_scores_micro: np.ndarray,
    book_maxima_micro: np.ndarray,
    lower_bounds_micro: Sequence[int] | np.ndarray,
    upper_bounds_micro: Sequence[int] | np.ndarray,
    complete_no_goods: tuple[tuple[str, ...], ...],
    evidence_root: Path,
) -> None:
    """Independently reconstruct the result before it may update a dose."""
    if not isinstance(pricing, PricingResult):
        raise ResidualWorldError("pricing did not return its frozen receipt type")
    identity = audit_legal_identity(players, pricing.roster)
    if pricing.roster != identity:
        raise ResidualWorldError("pricing roster identity is not canonical")
    if identity in complete_no_goods or pricing.no_good_rosters != complete_no_goods:
        raise ResidualWorldError("pricing did not honor every complete no-good")
    row = {player.player_id: index for index, player in enumerate(players)}
    chosen = np.asarray([row[player_id] for player_id in identity], dtype=int)
    scores = active_scores_micro[chosen].sum(axis=0, dtype=np.int64)
    maxima = _micro_vector(
        book_maxima_micro, scores.shape[0], "dose book maxima"
    )
    lower = _micro_vector(
        lower_bounds_micro, scores.shape[0], "dose legal lower bounds"
    )
    upper = _micro_vector(
        upper_bounds_micro, scores.shape[0], "dose legal upper bounds"
    )
    if tuple(int(value) for value in scores) != pricing.scores_micro:
        raise ResidualWorldError("pricing active scores do not reconstruct")
    indicators = tuple(tuple(
        int(int(maxima[world]) < threshold <= int(scores[world]))
        for world in range(len(scores))
    ) for threshold in TAIL_THRESHOLDS_MICRO)
    counts = tuple(sum(values) for values in indicators)
    residuals = np.maximum(scores - maxima, 0).astype(np.int64)
    gain = sum(int(value) for value in residuals)
    objective = (*counts, gain)
    if pricing.indicators_by_threshold != indicators:
        raise ResidualWorldError("pricing tail indicators do not reconstruct")
    if pricing.marginal_threshold_counts != counts:
        raise ResidualWorldError("pricing tail counts do not reconstruct")
    if pricing.residuals_micro != tuple(int(value) for value in residuals) or (
        pricing.residual_gain_micro != gain
    ):
        raise ResidualWorldError("pricing positive residuals do not reconstruct")
    if pricing.objective_vector != objective or pricing.sequential_optima != objective:
        raise ResidualWorldError("pricing sequential objective does not reconstruct")
    expected_rank = sum(
        index + 1 for index, player_id in enumerate(sorted(row))
        if player_id in identity
    )
    if pricing.rank_sum != expected_rank:
        raise ResidualWorldError("pricing canonical rank sum does not reconstruct")
    first = audit_legal_identity(players, pricing.rank_first_roster)
    first_rank = sum(
        index + 1 for index, player_id in enumerate(sorted(row))
        if player_id in first
    )
    if pricing.rank_first_roster != first or first_rank != pricing.rank_sum:
        raise ResidualWorldError("pricing first rank-optimal roster is malformed")
    if first in complete_no_goods:
        raise ResidualWorldError(
            "pricing first rank-optimal roster violates a complete no-good"
        )
    first_chosen = np.asarray(
        [row[player_id] for player_id in first], dtype=int
    )
    first_scores = active_scores_micro[first_chosen].sum(
        axis=0, dtype=np.int64
    )
    if np.any(first_scores < lower) or np.any(first_scores > upper):
        raise ResidualWorldError(
            "pricing first rank-optimal roster is off its frozen legal face"
        )
    first_indicators = tuple(tuple(
        int(int(maxima[world]) < threshold <= int(first_scores[world]))
        for world in range(len(first_scores))
    ) for threshold in TAIL_THRESHOLDS_MICRO)
    first_counts = tuple(sum(values) for values in first_indicators)
    first_gain = sum(
        int(value) for value in np.maximum(first_scores - maxima, 0)
    )
    if first_counts != counts or first_gain != gain:
        raise ResidualWorldError(
            "pricing first rank-optimal roster is off its frozen objective face"
        )
    distance = _strict_integer(
        pricing.ambiguity_distance, "pricing ambiguity distance"
    )
    if not 0 <= distance <= ROSTER_SIZE or (
        pricing.rank_sum_ambiguous != (distance > 0)
    ):
        raise ResidualWorldError("pricing ambiguity receipt is inconsistent")
    if pricing.admissible != any(counts):
        raise ResidualWorldError("pricing admissibility disagrees with tail tiers")
    if not pricing.rank_sum_ambiguous and identity != first:
        raise ResidualWorldError(
            "unambiguous pricing identity differs from its rank solve"
        )
    _audit_pricing_evidence_semantics(
        pricing,
        players,
        maxima,
        lower,
        upper,
        complete_no_goods,
        active_scores_micro,
        evidence_root,
    )


def run_fold_doses(
    prepared: PreparedFoldReservoir,
    players: Sequence[PlayerSpec | Mapping[str, object]],
    world_ids: Sequence[WorldId],
    raw_player_draws: np.ndarray,
    control_identities: Sequence[Sequence[object]],
    control_source_tags: Sequence[Sequence[object]],
    control_selector_totals: np.ndarray,
    control_micro_totals: np.ndarray,
    *,
    evidence_root: str | Path,
) -> FoldDoseResult:
    """Execute the frozen pruning -> active -> pricing -> selector dose loop.

    This function intentionally calls the production selector and exact
    pricer directly.  Tests may monkeypatch those module symbols as spies, but
    callers cannot inject an alternate selector, pool update, or maxima law.
    """
    if not isinstance(prepared, PreparedFoldReservoir):
        raise ResidualWorldError("fold dose run lacks a prepared reservoir")
    rows = _players(players)
    worlds = _exact_world_order(world_ids)
    raw = _player_draw_matrix(raw_player_draws, len(rows), len(worlds))
    player_micro = to_micro_dk(raw)
    controls = tuple(canonical_identity(value) for value in control_identities)
    selector_totals = _selector_matrix(
        control_selector_totals, len(controls), len(worlds)
    )
    micro_totals = _micro_matrix(
        control_micro_totals, rows=len(controls), label="control micro totals"
    )
    if micro_totals.shape[1] != len(worlds):
        raise ResidualWorldError("control micro totals have the wrong world count")

    # Rebuild every immutable source/Q_C/pruning/reservoir binding.  This is
    # also the required direct unchanged-selector call for k=0.
    rebuilt = prepare_fold_reservoir(
        prepared.fold_name,
        rows,
        worlds,
        raw,
        controls,
        control_source_tags,
        selector_totals,
        micro_totals,
        prepared.reservoir_bounds,
        run_context=prepared.run_context,
    )
    if rebuilt != prepared:
        raise ResidualWorldError("prepared fold/source/Q_C binding changed")
    spec = _fold_spec(prepared.fold_name)
    construction_columns = np.asarray([
        index for index, world in enumerate(worlds)
        if world.block in spec.construction_blocks
    ], dtype=int)
    selector_call_count = 1

    # Q_C must reproduce in exact order under every one of the eight removal
    # prefixes before treatment generation is allowed.
    interim_books: list[tuple[tuple[str, ...], ...]] = []
    for dose in range(1, K_MAX + 1):
        removed = set(prepared.pruning.removal_order[:dose])
        retained_indices = [
            index for index, identity in enumerate(controls)
            if identity not in removed
        ]
        retained = tuple(controls[index] for index in retained_indices)
        selected, _ = _select_exact_book(
            retained,
            selector_totals[retained_indices],
            construction_columns,
        )
        selector_call_count += 1
        interim_books.append(selected)
    verify_protected_book_reproduction(prepared.control_book, interim_books)

    if not isinstance(evidence_root, (str, Path)) or not str(evidence_root):
        raise ResidualWorldError("dose run needs an explicit evidence root")
    evidence_path = Path(evidence_root)
    if not evidence_path.is_absolute():
        raise ResidualWorldError("dose evidence root must be absolute")
    if not evidence_path.parent.is_dir() or evidence_path.exists():
        raise ResidualWorldError(
            "dose evidence root parent must exist and target must be create-only"
        )
    evidence_path.mkdir(mode=0o700)

    def exact_solver_factory(
        max_seconds: int, warm_start: bool
    ) -> _RetainedCbcSolver:
        return make_cbc_solver(
            max_seconds, warm_start, evidence_root=evidence_path
        )

    reservoir_ids = tuple(
        bound.world_id for bound in prepared.reservoir_bounds
    )
    reservoir_global = np.asarray([
        WORLD_BLOCKS.index(world.block) * WORLDS_PER_BLOCK + world.index
        for world in reservoir_ids
    ], dtype=int)
    lower_by_world = {
        bound.world_id: bound.lower_micro for bound in prepared.reservoir_bounds
    }
    upper_by_world = {
        bound.world_id: bound.upper_micro for bound in prepared.reservoir_bounds
    }

    generated: list[tuple[str, ...]] = []
    generated_selector_rows: list[np.ndarray] = []
    generated_micro_rows: list[np.ndarray] = []
    steps: list[FoldDoseStep] = []
    current_identities = controls
    current_selector = selector_totals
    current_micro = micro_totals
    current_book = prepared.control_book
    current_book_rows = tuple(controls.index(identity) for identity in current_book)
    stopped = False
    null_iteration: int | None = None

    for iteration in range(1, K_MAX + 1):
        reference_book = current_book
        reference_maxima = current_micro[
            np.asarray(current_book_rows, dtype=int)[:, None], reservoir_global
        ].max(axis=0)
        active = select_block_stratified_worlds(
            reservoir_ids,
            reference_maxima,
            np.asarray([
                upper_by_world[world] for world in reservoir_ids
            ], dtype=np.int64),
            tuple(
                (block, spec.active_per_block)
                for block in spec.construction_blocks
            ),
        )
        active = _audit_block_selection(
            active,
            reservoir_ids,
            reference_maxima,
            np.asarray([
                upper_by_world[world] for world in reservoir_ids
            ], dtype=np.int64),
            tuple(
                (block, spec.active_per_block)
                for block in spec.construction_blocks
            ),
        )
        if len(active) != FOLD_ACTIVE_SIZE:
            raise ResidualWorldError("active residual set is not exact-66")
        active_worlds = tuple(selection.world_id for selection in active)
        active_positions = {
            world: index for index, world in enumerate(reservoir_ids)
        }
        active_reservoir_rows = np.asarray([
            active_positions[world] for world in active_worlds
        ], dtype=int)
        active_global_rows = reservoir_global[active_reservoir_rows]
        active_maxima = reference_maxima[active_reservoir_rows]
        active_lower = np.asarray([
            lower_by_world[world] for world in active_worlds
        ], dtype=np.int64)
        active_upper = np.asarray([
            upper_by_world[world] for world in active_worlds
        ], dtype=np.int64)
        complete_cuts = complete_no_good_rosters(controls, generated)
        pricing = solve_residual_pricing(
            rows,
            player_micro[:, active_global_rows],
            active_maxima,
            active_lower,
            active_upper,
            control_rosters=controls,
            previous_columns=generated,
            solver_factory=exact_solver_factory,
        )
        _audit_pricing_result(
            pricing,
            rows,
            player_micro[:, active_global_rows],
            active_maxima,
            active_lower,
            active_upper,
            complete_cuts,
            evidence_path,
        )
        if not pricing.admissible:
            if any(pricing.marginal_threshold_counts):
                raise ResidualWorldError("null dose has a positive registered tier")
            stopped = True
            null_iteration = iteration
            steps.append(FoldDoseStep(
                iteration=iteration,
                reservoir_sha256=prepared.reservoir_sha256,
                reservoir_maxima_micro=tuple(
                    int(value) for value in reference_maxima
                ),
                reservoir_maxima_sha256=_array_sha256(
                    np.asarray(reference_maxima, dtype=np.int64)
                ),
                active_selections=active,
                reference_book_before=reference_book,
                reference_book_sha256=_identities_sha256(reference_book),
                reference_maxima_micro=tuple(int(value) for value in active_maxima),
                complete_no_goods=complete_cuts,
                complete_no_goods_sha256=_identities_sha256(complete_cuts),
                pricing=pricing,
                treatment_pool_after=None,
                treatment_pool_sha256=None,
                selected_book_after=None,
                selected_book_sha256=None,
            ))
            break
        if not any(value > 0 for value in pricing.marginal_threshold_counts):
            raise ResidualWorldError("positive dose has no registered tail marginal")
        identity = canonical_identity(pricing.roster)
        if identity in controls or identity in generated:
            raise ResidualWorldError("positive dose repeats a banned identity")
        generated_raw, generated_micro = _cross_score_rosters(
            rows, raw, player_micro, [identity]
        )
        _validate_roster_micro_parity(
            rows,
            raw,
            player_micro,
            [identity],
            generated_raw,
            generated_micro,
        )
        if tuple(int(value) for value in generated_micro[0, active_global_rows]) != (
            pricing.scores_micro
        ):
            raise ResidualWorldError("priced column fails all-world cross-score")
        generated.append(identity)
        generated_selector_rows.append(generated_raw[0])
        generated_micro_rows.append(generated_micro[0])
        current_identities, current_selector, current_micro = (
            _materialize_treatment_scores(
                controls,
                selector_totals,
                micro_totals,
                prepared.pruning,
                tuple(generated),
                generated_selector_rows,
                generated_micro_rows,
            )
        )
        current_book, current_book_rows = _select_exact_book(
            current_identities, current_selector, construction_columns
        )
        selector_call_count += 1
        steps.append(FoldDoseStep(
            iteration=iteration,
            reservoir_sha256=prepared.reservoir_sha256,
            reservoir_maxima_micro=tuple(
                int(value) for value in reference_maxima
            ),
            reservoir_maxima_sha256=_array_sha256(
                np.asarray(reference_maxima, dtype=np.int64)
            ),
            active_selections=active,
            reference_book_before=reference_book,
            reference_book_sha256=_identities_sha256(reference_book),
            reference_maxima_micro=tuple(int(value) for value in active_maxima),
            complete_no_goods=complete_cuts,
            complete_no_goods_sha256=_identities_sha256(complete_cuts),
            pricing=pricing,
            treatment_pool_after=current_identities,
            treatment_pool_sha256=_identities_sha256(current_identities),
            selected_book_after=current_book,
            selected_book_sha256=_identities_sha256(current_book),
        ))

    generated_tuple = tuple(generated)
    final_identities, final_selector, final_micro = _materialize_treatment_scores(
        controls,
        selector_totals,
        micro_totals,
        prepared.pruning,
        generated_tuple,
        generated_selector_rows,
        generated_micro_rows,
    )
    if final_identities != current_identities:
        raise ResidualWorldError("final treatment identity order changed")
    if len(current_book) != ENTRY_COUNT or not set(current_book) <= set(
        final_identities
    ):
        raise ResidualWorldError("final treatment book is not exact-80 in pool")
    generated_selector_matrix = (
        np.stack(generated_selector_rows).astype(np.float32, copy=False)
        if generated_selector_rows else np.empty((0, len(worlds)), dtype=np.float32)
    )
    generated_micro_matrix = (
        np.stack(generated_micro_rows).astype(np.int64, copy=False)
        if generated_micro_rows else np.empty((0, len(worlds)), dtype=np.int64)
    )
    generated_parity = _validate_roster_micro_parity(
        rows,
        raw,
        player_micro,
        generated_tuple,
        generated_selector_matrix,
        generated_micro_matrix,
    )
    treatment_parity = _validate_roster_micro_parity(
        rows,
        raw,
        player_micro,
        final_identities,
        final_selector,
        final_micro,
    )
    removed = set(prepared.pruning.removal_order[:len(generated_tuple)])
    retained_source_tags = tuple(
        tags for identity, tags in zip(
            controls, prepared.control_source_tags, strict=True
        ) if identity not in removed
    )
    generated_source_tags = tuple(
        (f"residual_world:fold_{spec.name}:column_{index:02d}",)
        for index in range(1, len(generated_tuple) + 1)
    )
    treatment_source_tags = (*retained_source_tags, *generated_source_tags)
    if len(treatment_source_tags) != len(final_identities):
        raise ResidualWorldError("treatment source attribution is misaligned")
    _audit_evidence_root_inventory(evidence_path, steps)
    return FoldDoseResult(
        fold_name=spec.name,
        run_context=prepared.run_context,
        run_context_payload=prepared.run_context_payload,
        run_context_sha256=prepared.run_context_sha256,
        prepared_fold_sha256=prepared_fold_sha256(prepared),
        prepared_reservoir_sha256=prepared.reservoir_sha256,
        control_book=prepared.control_book,
        control_source_tags=prepared.control_source_tags,
        treatment_candidates=final_identities,
        treatment_source_tags=treatment_source_tags,
        treatment_source_tags_sha256=_source_tags_sha256(
            treatment_source_tags
        ),
        treatment_book=current_book,
        generated_columns=generated_tuple,
        steps=tuple(steps),
        stopped_on_first_null=stopped,
        null_iteration=null_iteration,
        selector_call_count=selector_call_count,
        audit_context=FoldDoseAuditContext(
            prepared=prepared,
            players=rows,
            world_ids=worlds,
            raw_player_draws=_readonly_copy(raw),
            control_identities=controls,
            control_source_tags=prepared.control_source_tags,
            control_selector_totals=_readonly_copy(selector_totals),
            control_micro_totals=_readonly_copy(micro_totals),
        ),
        operational_evidence=FoldDoseOperationalEvidence(
            evidence_root=str(evidence_path.resolve()),
            evidence_root_sha256=_canonical_json_sha256({
                "resolved_evidence_root": str(evidence_path.resolve())
            }),
        ),
        pricing_evidence_manifest_sha256=_pricing_evidence_manifest_sha256(
            steps
        ),
        generated_selector_totals_sha256=_array_sha256(
            generated_selector_matrix
        ),
        generated_micro_totals_sha256=_array_sha256(generated_micro_matrix),
        generated_score_parity=generated_parity,
        generated_score_parity_sha256=generated_parity.sha256,
        treatment_selector_totals_sha256=_array_sha256(final_selector),
        treatment_micro_totals_sha256=_array_sha256(final_micro),
        treatment_score_parity=treatment_parity,
        treatment_score_parity_sha256=treatment_parity.sha256,
        generated_selector_totals=_readonly_copy(generated_selector_matrix),
        generated_micro_totals=_readonly_copy(generated_micro_matrix),
        treatment_selector_totals=_readonly_copy(final_selector),
        treatment_micro_totals=_readonly_copy(final_micro),
    )


def _pricing_evidence_manifest_sha256(
    steps: Sequence[FoldDoseStep],
) -> str:
    return _canonical_json_sha256([{
        "iteration": step.iteration,
        "receipts": [
            _cbc_scientific_receipt(evidence)
            for evidence in step.pricing.solve_evidence
        ],
    } for step in steps])


def _audit_fold_dose_result_scientific_state(result: FoldDoseResult) -> None:
    """Rebuild a complete fold dose from retained source values.

    This is intentionally more than a hash check.  Every selector book,
    residual-world queue, pricing statistic, matched-budget replacement,
    score-parity receipt, and retained CBC artifact is reconstructed at the
    serialization boundary.
    """
    context = result.audit_context
    if not isinstance(context, FoldDoseAuditContext) or not isinstance(
        context.prepared, PreparedFoldReservoir
    ):
        raise ResidualWorldError("fold dose lacks its retained audit context")
    prepared_context, prepared_context_payload, prepared_context_sha256 = (
        _validate_run_context_binding(
            context.prepared.run_context,
            context.prepared.run_context_payload,
            context.prepared.run_context_sha256,
        )
    )
    result_context, result_context_payload, result_context_sha256 = (
        _validate_run_context_binding(
            result.run_context,
            result.run_context_payload,
            result.run_context_sha256,
        )
    )
    if (
        result_context != prepared_context
        or result_context_payload != prepared_context_payload
        or result_context_sha256 != prepared_context_sha256
    ):
        raise ResidualWorldError(
            "fold dose run context differs from its prepared receipt"
        )
    spec = _fold_spec(result.fold_name)
    if context.prepared.fold_name != spec.name:
        raise ResidualWorldError("fold dose prepared fold identity changed")
    rows = _players(context.players)
    if rows != tuple(context.players):
        raise ResidualWorldError("fold dose player catalog changed")
    worlds = _exact_world_order(context.world_ids)
    raw = _player_draw_matrix(
        context.raw_player_draws, len(rows), len(worlds)
    )
    player_micro = to_micro_dk(raw)
    controls = tuple(
        canonical_identity(identity) for identity in context.control_identities
    )
    native_candidate_count = len(controls)
    if (
        native_candidate_count < ENTRY_COUNT + K_MAX
        or len(set(controls)) != native_candidate_count
    ):
        raise ResidualWorldError("fold dose native control pool changed")
    for identity in controls:
        audit_legal_identity(rows, identity)
    control_tags = _source_tags(
        context.control_source_tags, native_candidate_count
    )
    selector_totals = _selector_matrix(
        context.control_selector_totals,
        native_candidate_count,
        len(worlds),
    )
    micro_totals = _micro_matrix(
        context.control_micro_totals,
        rows=native_candidate_count,
        label="retained control micro totals",
    )
    if micro_totals.shape[1] != len(worlds):
        raise ResidualWorldError("retained control micro totals are misaligned")

    # Rebuild the immutable preparation from retained values.  The final
    # scientific boundary deliberately replays the unchanged deterministic
    # selector: hashes, membership, and downstream maxima cannot prove the
    # exact ordered book when an attacker coherently changes a receipt.
    rebuilt_prepared = context.prepared
    if (
        rebuilt_prepared.fold_sha256 != _fold_sha256(spec)
        or rebuilt_prepared.world_ids_sha256 != _world_ids_sha256(worlds)
        or rebuilt_prepared.player_catalog_sha256
        != _player_catalog_sha256(rows)
        or rebuilt_prepared.player_draws_sha256 != _array_sha256(raw)
        or rebuilt_prepared.control_candidates != controls
        or rebuilt_prepared.control_candidates_sha256
        != _identities_sha256(controls)
        or rebuilt_prepared.control_source_tags != control_tags
        or rebuilt_prepared.control_source_tags_sha256
        != _source_tags_sha256(control_tags)
        or rebuilt_prepared.control_selector_totals_sha256
        != _array_sha256(selector_totals)
        or rebuilt_prepared.control_micro_totals_sha256
        != _array_sha256(micro_totals)
    ):
        raise ResidualWorldError("fold dose prepared source binding changed")
    reconstructed_selector, reconstructed_micro = _cross_score_rosters(
        rows, raw, player_micro, controls
    )
    if not np.array_equal(reconstructed_selector, selector_totals) or not (
        np.array_equal(reconstructed_micro, micro_totals)
    ):
        raise ResidualWorldError("fold dose prepared score matrices changed")
    control_parity = _validate_roster_micro_parity(
        rows,
        raw,
        player_micro,
        controls,
        selector_totals,
        micro_totals,
    )
    if (
        control_parity != rebuilt_prepared.control_score_parity
        or control_parity.sha256
        != rebuilt_prepared.control_score_parity_sha256
    ):
        raise ResidualWorldError("fold dose control score-parity changed")
    control_book = tuple(
        canonical_identity(identity) for identity in rebuilt_prepared.control_book
    )
    if (
        control_book != rebuilt_prepared.control_book
        or len(control_book) != ENTRY_COUNT
        or len(set(control_book)) != ENTRY_COUNT
        or not set(control_book) <= set(controls)
        or _identities_sha256(control_book)
        != rebuilt_prepared.control_book_sha256
    ):
        raise ResidualWorldError("fold dose prepared control book changed")
    construction_columns = np.asarray([
        index for index, world in enumerate(worlds)
        if world.block in spec.construction_blocks
    ], dtype=int)
    replayed_control_book, _ = _select_exact_book(
        controls, selector_totals, construction_columns
    )
    if replayed_control_book != control_book:
        raise ResidualWorldError(
            "fold dose prepared control book differs from selector replay"
        )
    expected_pruning = reverse_greedy_pruning_order(
        controls,
        micro_totals[:, construction_columns],
        control_book,
        steps=K_MAX,
        expected_protected_count=ENTRY_COUNT,
    )
    if expected_pruning != rebuilt_prepared.pruning:
        raise ResidualWorldError("fold dose prepared pruning changed")
    replayed_prefix_books: list[tuple[tuple[str, ...], ...]] = []
    for dose in range(1, K_MAX + 1):
        removed = set(expected_pruning.removal_order[:dose])
        retained_indices = [
            index for index, identity in enumerate(controls)
            if identity not in removed
        ]
        retained = tuple(controls[index] for index in retained_indices)
        selected, _ = _select_exact_book(
            retained,
            selector_totals[retained_indices],
            construction_columns,
        )
        replayed_prefix_books.append(selected)
    verify_protected_book_reproduction(
        control_book, replayed_prefix_books
    )
    initial_rows = np.asarray(
        [controls.index(identity) for identity in control_book], dtype=int
    )
    initial_maxima = micro_totals[
        initial_rows[:, None], construction_columns
    ].max(axis=0)
    relaxed_upper = position_shape_upper_bounds_micro(
        player_micro[:, construction_columns],
        [player.position for player in rows],
    )
    construction_worlds = tuple(worlds[index] for index in construction_columns)
    reservoir_selections = _audit_block_selection(
        rebuilt_prepared.reservoir_selections,
        construction_worlds,
        initial_maxima,
        relaxed_upper,
        tuple(
            (block, spec.reservoir_per_block)
            for block in spec.construction_blocks
        ),
    )
    bounds = tuple(rebuilt_prepared.reservoir_bounds)
    if (
        tuple(value.world_id for value in reservoir_selections)
        != tuple(bound.world_id for bound in bounds)
        or _world_selections_sha256(reservoir_selections)
        != rebuilt_prepared.reservoir_selections_sha256
        or _reservoir_sha256(reservoir_selections, bounds)
        != rebuilt_prepared.reservoir_sha256
    ):
        raise ResidualWorldError("fold dose prepared reservoir changed")
    _validate_bound_receipts(rows, player_micro, worlds, bounds)
    if (
        prepared_fold_sha256(rebuilt_prepared) != result.prepared_fold_sha256
        or rebuilt_prepared.reservoir_sha256
        != result.prepared_reservoir_sha256
    ):
        raise ResidualWorldError("fold dose prepared receipt hash changed")
    if (
        tuple(result.control_source_tags) != control_tags
        or tuple(result.control_book) != rebuilt_prepared.control_book
    ):
        raise ResidualWorldError("fold dose control source/book changed")

    steps = tuple(result.steps)
    if not steps or tuple(step.iteration for step in steps) != tuple(
        range(1, len(steps) + 1)
    ):
        raise ResidualWorldError("fold dose step order changed")
    generated_tuple = tuple(
        canonical_identity(identity) for identity in result.generated_columns
    )
    if (
        len(steps) > K_MAX
        or len(generated_tuple) > K_MAX
        or generated_tuple != tuple(result.generated_columns)
        or len(set(generated_tuple)) != len(generated_tuple)
        or set(generated_tuple) & set(controls)
    ):
        raise ResidualWorldError("fold dose generated-column sequence changed")

    generated_selector = _selector_matrix(
        result.generated_selector_totals,
        len(generated_tuple),
        len(worlds),
    )
    if generated_tuple:
        generated_micro = _micro_matrix(
            result.generated_micro_totals,
            rows=len(generated_tuple),
            label="retained generated micro totals",
        )
    else:
        generated_micro = np.asarray(result.generated_micro_totals)
        if generated_micro.dtype != np.int64 or generated_micro.shape != (
            0, len(worlds)
        ):
            raise ResidualWorldError(
                "retained generated micro totals are misaligned"
            )
    if generated_micro.shape[1] != len(worlds):
        raise ResidualWorldError("retained generated micro totals are misaligned")
    expected_generated_selector, expected_generated_micro = _cross_score_rosters(
        rows, raw, player_micro, generated_tuple
    )
    if not np.array_equal(generated_selector, expected_generated_selector):
        raise ResidualWorldError("generated selector totals changed")
    if not np.array_equal(generated_micro, expected_generated_micro):
        raise ResidualWorldError("generated micro totals changed")
    generated_parity = _validate_roster_micro_parity(
        rows,
        raw,
        player_micro,
        generated_tuple,
        generated_selector,
        generated_micro,
    )
    if (
        generated_parity != result.generated_score_parity
        or generated_parity.sha256 != result.generated_score_parity_sha256
        or _array_sha256(generated_selector)
        != result.generated_selector_totals_sha256
        or _array_sha256(generated_micro)
        != result.generated_micro_totals_sha256
    ):
        raise ResidualWorldError("generated score-parity receipt hash changed")

    treatment_candidates = tuple(
        canonical_identity(identity) for identity in result.treatment_candidates
    )
    if (
        treatment_candidates != tuple(result.treatment_candidates)
        or len(treatment_candidates) != native_candidate_count
        or len(set(treatment_candidates)) != native_candidate_count
    ):
        raise ResidualWorldError("fold dose final treatment identity changed")
    treatment_selector = _selector_matrix(
        result.treatment_selector_totals,
        native_candidate_count,
        len(worlds),
    )
    treatment_micro = _micro_matrix(
        result.treatment_micro_totals,
        rows=native_candidate_count,
        label="retained treatment micro totals",
    )
    if treatment_micro.shape[1] != len(worlds):
        raise ResidualWorldError("retained treatment micro totals are misaligned")
    treatment_parity = _validate_roster_micro_parity(
        rows,
        raw,
        player_micro,
        treatment_candidates,
        treatment_selector,
        treatment_micro,
    )
    if (
        treatment_parity != result.treatment_score_parity
        or treatment_parity.sha256 != result.treatment_score_parity_sha256
        or _array_sha256(treatment_selector)
        != result.treatment_selector_totals_sha256
        or _array_sha256(treatment_micro)
        != result.treatment_micro_totals_sha256
    ):
        raise ResidualWorldError("treatment score-parity receipt hash changed")

    operational = result.operational_evidence
    if not isinstance(operational, FoldDoseOperationalEvidence):
        raise ResidualWorldError("fold dose operational evidence is malformed")
    evidence_path = Path(operational.evidence_root)
    if not evidence_path.is_absolute():
        raise ResidualWorldError("fold dose evidence root is not absolute")
    resolved_evidence = evidence_path.resolve()
    if (
        str(resolved_evidence) != operational.evidence_root
        or _canonical_json_sha256({
            "resolved_evidence_root": str(resolved_evidence)
        }) != operational.evidence_root_sha256
    ):
        raise ResidualWorldError("fold dose operational evidence root changed")

    reservoir_ids = tuple(
        bound.world_id for bound in rebuilt_prepared.reservoir_bounds
    )
    if len(reservoir_ids) != FOLD_RESERVOIR_SIZE or len(
        set(reservoir_ids)
    ) != FOLD_RESERVOIR_SIZE:
        raise ResidualWorldError("fold dose reservoir identities changed")
    reservoir_positions = {world: index for index, world in enumerate(reservoir_ids)}
    global_positions = {world: index for index, world in enumerate(worlds)}
    reservoir_global = np.asarray(
        [global_positions[world] for world in reservoir_ids], dtype=int
    )
    reservoir_upper = np.asarray(
        [bound.upper_micro for bound in rebuilt_prepared.reservoir_bounds],
        dtype=np.int64,
    )
    lower_by_world = {
        bound.world_id: bound.lower_micro
        for bound in rebuilt_prepared.reservoir_bounds
    }
    upper_by_world = {
        bound.world_id: bound.upper_micro
        for bound in rebuilt_prepared.reservoir_bounds
    }
    generated: list[tuple[str, ...]] = []
    generated_selector_rows: list[np.ndarray] = []
    generated_micro_rows: list[np.ndarray] = []
    current_identities = controls
    current_selector = selector_totals
    current_micro = micro_totals
    prior_book = rebuilt_prepared.control_book
    saw_null = False
    for step in steps:
        if step.reservoir_sha256 != result.prepared_reservoir_sha256:
            raise ResidualWorldError("fold dose reservoir binding changed")
        if (
            tuple(step.reference_book_before) != prior_book
            or len(prior_book) != ENTRY_COUNT
            or len(set(prior_book)) != ENTRY_COUNT
            or not set(prior_book) <= set(current_identities)
            or _identities_sha256(prior_book) != step.reference_book_sha256
        ):
            raise ResidualWorldError("fold dose reference book hash changed")
        current_rows = {identity: index for index, identity in enumerate(
            current_identities
        )}
        book_rows = np.asarray(
            [current_rows[identity] for identity in prior_book], dtype=int
        )
        expected_reservoir_maxima = current_micro[
            book_rows[:, None], reservoir_global
        ].max(axis=0)
        observed_reservoir_maxima = _micro_vector(
            step.reservoir_maxima_micro,
            FOLD_RESERVOIR_SIZE,
            "fold dose reservoir maxima",
        )
        if (
            not np.array_equal(
                observed_reservoir_maxima, expected_reservoir_maxima
            )
            or _array_sha256(observed_reservoir_maxima)
            != step.reservoir_maxima_sha256
        ):
            raise ResidualWorldError("fold dose reservoir maxima hash changed")
        active = _audit_block_selection(
            step.active_selections,
            reservoir_ids,
            expected_reservoir_maxima,
            reservoir_upper,
            tuple(
                (block, spec.active_per_block)
                for block in spec.construction_blocks
            ),
        )
        if len(active) != FOLD_ACTIVE_SIZE:
            raise ResidualWorldError("fold dose active-world receipt changed")
        active_reservoir = np.asarray(
            [reservoir_positions[value.world_id] for value in active],
            dtype=int,
        )
        active_global = reservoir_global[active_reservoir]
        active_maxima = expected_reservoir_maxima[active_reservoir]
        if tuple(int(value) for value in active_maxima) != tuple(
            step.reference_maxima_micro
        ):
            raise ResidualWorldError("fold dose active maxima changed")
        active_lower = np.asarray(
            [lower_by_world[value.world_id] for value in active],
            dtype=np.int64,
        )
        active_upper = np.asarray(
            [upper_by_world[value.world_id] for value in active],
            dtype=np.int64,
        )
        expected_cuts = (*controls, *generated)
        if (
            tuple(step.complete_no_goods) != expected_cuts
            or _identities_sha256(expected_cuts)
            != step.complete_no_goods_sha256
            or step.pricing.no_good_rosters != expected_cuts
        ):
            raise ResidualWorldError("fold dose complete no-good receipt changed")
        _audit_pricing_result(
            step.pricing,
            rows,
            player_micro[:, active_global],
            active_maxima,
            active_lower,
            active_upper,
            expected_cuts,
            resolved_evidence,
        )
        pricing_identity = canonical_identity(step.pricing.roster)
        if not step.pricing.admissible:
            if (
                saw_null
                or step is not steps[-1]
                or step.treatment_pool_after is not None
                or step.treatment_pool_sha256 is not None
                or step.selected_book_after is not None
                or step.selected_book_sha256 is not None
            ):
                raise ResidualWorldError("fold dose null-step receipt changed")
            saw_null = True
            continue

        if (
            saw_null
            or len(generated) >= len(generated_tuple)
            or pricing_identity != generated_tuple[len(generated)]
        ):
            raise ResidualWorldError("fold dose positive-step identity changed")
        generated.append(pricing_identity)
        generated_selector_rows.append(generated_selector[len(generated) - 1])
        generated_micro_rows.append(generated_micro[len(generated) - 1])
        (
            expected_treatment,
            expected_selector,
            expected_micro,
        ) = _materialize_treatment_scores(
            controls,
            selector_totals,
            micro_totals,
            rebuilt_prepared.pruning,
            tuple(generated),
            generated_selector_rows,
            generated_micro_rows,
        )
        selected_book = tuple(
            canonical_identity(identity)
            for identity in (step.selected_book_after or ())
        )
        replayed_selected_book, _ = _select_exact_book(
            expected_treatment,
            expected_selector,
            construction_columns,
        )
        if (
            step.treatment_pool_after != expected_treatment
            or step.treatment_pool_sha256
            != _identities_sha256(expected_treatment)
            or step.selected_book_after != selected_book
            or len(selected_book) != ENTRY_COUNT
            or len(set(selected_book)) != ENTRY_COUNT
            or not set(selected_book) <= set(expected_treatment)
            or step.selected_book_sha256 != _identities_sha256(selected_book)
            or selected_book != replayed_selected_book
        ):
            raise ResidualWorldError("fold dose treatment pool/book changed")
        current_identities = expected_treatment
        current_selector = expected_selector
        current_micro = expected_micro
        prior_book = selected_book

    if tuple(generated) != generated_tuple:
        raise ResidualWorldError("fold dose generated-column sequence changed")
    if saw_null:
        if (
            not result.stopped_on_first_null
            or result.null_iteration != steps[-1].iteration
            or len(steps) != len(generated_tuple) + 1
        ):
            raise ResidualWorldError("fold dose first-null receipt changed")
    elif (
        result.stopped_on_first_null
        or result.null_iteration is not None
        or len(generated_tuple) != K_MAX
        or len(steps) != K_MAX
    ):
        raise ResidualWorldError("fold dose K_max completion receipt changed")
    if result.selector_call_count != 1 + K_MAX + len(generated_tuple):
        raise ResidualWorldError("fold dose selector call count changed")

    if (
        treatment_candidates != current_identities
        or not np.array_equal(treatment_selector, current_selector)
        or not np.array_equal(treatment_micro, current_micro)
        or tuple(result.treatment_book) != prior_book
    ):
        raise ResidualWorldError("fold dose final treatment pool changed")
    tag_by_control = dict(zip(controls, control_tags, strict=True))
    generated_tag = {
        identity: (f"residual_world:fold_{spec.name}:column_{index:02d}",)
        for index, identity in enumerate(generated_tuple, 1)
    }
    expected_tags = tuple(
        tag_by_control.get(identity, generated_tag.get(identity, ()))
        for identity in treatment_candidates
    )
    if (
        any(not tags for tags in expected_tags)
        or tuple(result.treatment_source_tags) != expected_tags
        or _source_tags_sha256(expected_tags)
        != result.treatment_source_tags_sha256
    ):
        raise ResidualWorldError("fold dose treatment source tags changed")
    if _pricing_evidence_manifest_sha256(steps) != (
        result.pricing_evidence_manifest_sha256
    ):
        raise ResidualWorldError("fold dose pricing evidence manifest changed")
    # This is deliberately last: every solve artifact is re-opened and
    # re-hashed immediately before the result can be serialized.
    _audit_evidence_root_inventory(resolved_evidence, steps)


def fold_dose_scientific_payload(result: FoldDoseResult) -> dict[str, object]:
    """Canonical result projection that never serializes local paths/timing."""
    if not isinstance(result, FoldDoseResult):
        raise ResidualWorldError("fold dose result has the wrong receipt type")
    _audit_fold_dose_result_scientific_state(result)
    if (
        _array_sha256(result.generated_selector_totals)
        != result.generated_selector_totals_sha256
        or _array_sha256(result.generated_micro_totals)
        != result.generated_micro_totals_sha256
        or _array_sha256(result.treatment_selector_totals)
        != result.treatment_selector_totals_sha256
        or _array_sha256(result.treatment_micro_totals)
        != result.treatment_micro_totals_sha256
    ):
        raise ResidualWorldError("fold dose score matrix hash changed")
    if (
        result.generated_score_parity.sha256
        != result.generated_score_parity_sha256
        or result.treatment_score_parity.sha256
        != result.treatment_score_parity_sha256
    ):
        raise ResidualWorldError("fold dose score-parity receipt hash changed")
    spec = _fold_spec(result.fold_name)
    _, run_context_payload, run_context_sha256 = _validate_run_context_binding(
        result.run_context,
        result.run_context_payload,
        result.run_context_sha256,
    )
    native_candidate_count = len(result.audit_context.control_identities)
    payload: dict[str, object] = {
        "protocol_id": PROTOCOL_ID,
        "protocol_document_sha256": PROTOCOL_DOCUMENT_SHA256,
        "protocol_amendment_id": PROTOCOL_AMENDMENT_ID,
        "protocol_amendment_sha256": PROTOCOL_AMENDMENT_SHA256,
        "run_context": run_context_payload,
        "run_context_sha256": run_context_sha256,
        "fold_name": result.fold_name,
        "fold_sha256": _fold_sha256(spec),
        "native_candidate_count": native_candidate_count,
        "prepared_fold_sha256": result.prepared_fold_sha256,
        "prepared_reservoir_sha256": result.prepared_reservoir_sha256,
        "control_candidates_sha256": _identities_sha256(
            result.audit_context.control_identities
        ),
        "control_book_sha256": _identities_sha256(result.control_book),
        "control_source_tags_sha256": _source_tags_sha256(
            result.control_source_tags
        ),
        "treatment_candidates_sha256": _identities_sha256(
            result.treatment_candidates
        ),
        "treatment_source_tags_sha256": result.treatment_source_tags_sha256,
        "treatment_book_sha256": _identities_sha256(result.treatment_book),
        "generated_columns_sha256": _identities_sha256(
            result.generated_columns
        ),
        "steps": [{
            "iteration": step.iteration,
            "reservoir_sha256": step.reservoir_sha256,
            "reservoir_maxima_sha256": step.reservoir_maxima_sha256,
            "active_selections_sha256": _world_selections_sha256(
                step.active_selections
            ),
            "reference_book_sha256": step.reference_book_sha256,
            "complete_no_goods_sha256": step.complete_no_goods_sha256,
            "pricing_input_sha256": step.pricing.pricing_input_sha256,
            "pricing_roster": list(step.pricing.roster),
            "pricing_scores_micro_sha256": _array_sha256(np.asarray(
                step.pricing.scores_micro, dtype=np.int64
            )),
            "pricing_marginal_threshold_counts": list(
                step.pricing.marginal_threshold_counts
            ),
            "pricing_indicators_sha256": _array_sha256(np.asarray(
                step.pricing.indicators_by_threshold, dtype=np.int8
            )),
            "pricing_residuals_micro_sha256": _array_sha256(np.asarray(
                step.pricing.residuals_micro, dtype=np.int64
            )),
            "pricing_residual_gain_micro": step.pricing.residual_gain_micro,
            "pricing_objective": list(step.pricing.objective_vector),
            "pricing_sequential_optima": list(
                step.pricing.sequential_optima
            ),
            "pricing_rank_sum": step.pricing.rank_sum,
            "pricing_rank_sum_ambiguous": step.pricing.rank_sum_ambiguous,
            "pricing_ambiguity_distance": step.pricing.ambiguity_distance,
            "pricing_rank_first_roster": list(
                step.pricing.rank_first_roster
            ),
            "pricing_admissible": step.pricing.admissible,
            "pricing_evidence": [
                _cbc_scientific_receipt(evidence)
                for evidence in step.pricing.solve_evidence
            ],
            "treatment_pool_sha256": step.treatment_pool_sha256,
            "selected_book_sha256": step.selected_book_sha256,
        } for step in result.steps],
        "stopped_on_first_null": result.stopped_on_first_null,
        "null_iteration": result.null_iteration,
        "selector_call_count": result.selector_call_count,
        "pricing_evidence_manifest_sha256": (
            result.pricing_evidence_manifest_sha256
        ),
        "generated_selector_totals_sha256": (
            result.generated_selector_totals_sha256
        ),
        "generated_micro_totals_sha256": result.generated_micro_totals_sha256,
        "generated_score_parity_sha256": (
            result.generated_score_parity_sha256
        ),
        "generated_score_parity": _score_parity_scientific_receipt(
            result.generated_score_parity
        ),
        "treatment_selector_totals_sha256": (
            result.treatment_selector_totals_sha256
        ),
        "treatment_micro_totals_sha256": result.treatment_micro_totals_sha256,
        "treatment_score_parity_sha256": (
            result.treatment_score_parity_sha256
        ),
        "treatment_score_parity": _score_parity_scientific_receipt(
            result.treatment_score_parity
        ),
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
    }
    validate_unlicensed_scientific_payload(payload)
    return payload


def build_legal_lineup_model(
    players: Sequence[PlayerSpec | Mapping[str, object]],
    *,
    name: str = "residual_world_legal_lineup",
    forbidden_rosters: Sequence[Sequence[object]] = (),
) -> LegalLineupModel:
    """Build the frozen domain through the shared production constraint adder."""
    rows = _players(players)
    games = {player.game_id for player in rows}
    if len(games) < MIN_GAMES:
        raise ResidualWorldError(
            "residual legality requires at least two populated games"
        )
    normalized_forbidden = tuple(
        canonical_identity(value) for value in forbidden_rosters
    )
    known = {player.player_id for player in rows}
    if any(not set(identity) <= known for identity in normalized_forbidden):
        raise ResidualWorldError("no-good roster references an unknown player")
    if len(set(normalized_forbidden)) != len(normalized_forbidden):
        raise ResidualWorldError("legal model no-good roster repeats")

    problem = pulp.LpProblem(name, pulp.LpMaximize)
    canonical_index = {
        player_id: index for index, player_id in enumerate(sorted(
            player.player_id for player in rows
        ))
    }
    decision = {
        player.player_id: pulp.LpVariable(
            f"x_{canonical_index[player.player_id]:04d}", cat="Binary"
        )
        for player in rows
    }
    mappings = [
        {
            "id": player.player_id,
            "pos": player.position,
            "team": player.team,
            "opp": player.opponent,
            "game_id": player.game_id,
            "salary": player.salary,
        }
        for player in rows
    ]
    add_classic_lineup_constraints(
        problem,
        decision,
        mappings,
        budget=SALARY_CAP,
        locks=None,
        bans=None,
        banned_lineups=[frozenset(identity) for identity in normalized_forbidden],
        stack=StackRules(
            qb_stack_min=2,
            bring_back_min=1,
            forbid_rb_vs_dst=True,
            forbid_two_rb_same_team=True,
        ),
        max_overlap=ROSTER_SIZE - 1,
        punt_max_salary=None,
        punt_min=0,
        game_lock=None,
        min_salary=MIN_SALARY,
        max_salary=None,
        max_per_game=0,
        min_games=MIN_GAMES,
        env={},
    )

    # PuLP requires an objective before the first solve.  Callers replace it.
    problem += pulp.lpSum([])
    return LegalLineupModel(problem=problem, players=rows, decision=decision)


def audit_legal_identity(
    players: Sequence[PlayerSpec | Mapping[str, object]],
    roster: Sequence[object],
) -> tuple[str, ...]:
    """Independently reconstruct every frozen legality rule or fail closed."""
    rows = _players(players)
    by_id = {player.player_id: player for player in rows}
    identity = canonical_identity(roster)
    if set(identity) - set(by_id):
        raise ResidualWorldError("lineup identity references an unknown player")
    chosen = [by_id[player_id] for player_id in identity]
    counts = {
        position: sum(player.position == position for player in chosen)
        for position in ("QB", "RB", "WR", "TE", "DST")
    }
    if not (
        counts["QB"] == 1
        and counts["DST"] == 1
        and 2 <= counts["RB"] <= 3
        and 3 <= counts["WR"] <= 4
        and 1 <= counts["TE"] <= 2
    ):
        raise ResidualWorldError("lineup has an illegal position shape")
    salary = sum(player.salary for player in chosen)
    if not MIN_SALARY <= salary <= SALARY_CAP:
        raise ResidualWorldError("lineup salary is outside the frozen range")
    if max(sum(player.team == team for player in chosen) for team in {
        player.team for player in chosen
    }) > MAX_FROM_TEAM:
        raise ResidualWorldError("lineup exceeds the team cap")
    if len({player.game_id for player in chosen}) < MIN_GAMES:
        raise ResidualWorldError("lineup uses fewer than two games")
    qb = next(player for player in chosen if player.position == "QB")
    if sum(
        player.team == qb.team and player.position in {"WR", "TE"}
        for player in chosen
    ) < 2:
        raise ResidualWorldError("lineup does not contain QB plus two catchers")
    if sum(
        player.team == qb.opponent and player.position in {"RB", "WR", "TE"}
        for player in chosen
    ) < 1:
        raise ResidualWorldError("lineup does not contain a QB bring-back")
    dst = next(player for player in chosen if player.position == "DST")
    if any(
        player.position == "RB" and player.team == dst.opponent
        for player in chosen
    ):
        raise ResidualWorldError("lineup contains an RB against its DST")
    rb_teams = [player.team for player in chosen if player.position == "RB"]
    if len(rb_teams) != len(set(rb_teams)):
        raise ResidualWorldError("lineup contains two RBs from one team")
    return identity


def to_micro_dk(player_draws: np.ndarray) -> np.ndarray:
    """Convert finite player draws to the protocol's exact int64 scale."""
    draws = np.asarray(player_draws, dtype=np.float64)
    if draws.ndim != 2 or draws.shape[0] == 0 or draws.shape[1] == 0:
        raise ResidualWorldError("player draws must be one nonempty matrix")
    if not np.isfinite(draws).all():
        raise ResidualWorldError("player draws must be finite")
    limit = np.iinfo(np.int64).max / (MICRO_DK_SCALE * ROSTER_SIZE)
    if np.max(np.abs(draws)) > limit:
        raise ResidualWorldError("player draws overflow micro-DK arithmetic")
    return np.rint(draws * MICRO_DK_SCALE).astype(np.int64)


def _micro_matrix(
    values: np.ndarray,
    *,
    rows: int | None = None,
    label: str = "micro-DK scores",
) -> np.ndarray:
    matrix = np.asarray(values)
    if matrix.dtype.kind not in "iu" or matrix.dtype.itemsize > 8:
        raise ResidualWorldError(f"{label} must be an integer matrix")
    if matrix.dtype.kind == "u" and matrix.size and int(matrix.max()) > np.iinfo(
        np.int64
    ).max:
        raise ResidualWorldError(f"{label} exceeds signed int64")
    matrix = matrix.astype(np.int64, copy=False)
    if matrix.ndim != 2 or not matrix.shape[0] or not matrix.shape[1]:
        raise ResidualWorldError(f"{label} must be one nonempty matrix")
    if rows is not None and matrix.shape[0] != rows:
        raise ResidualWorldError(f"{label} does not align to players")
    largest = max(abs(int(matrix.min())), abs(int(matrix.max())))
    if largest > CBC_EXACT_INTEGER_MAX // ROSTER_SIZE:
        raise ResidualWorldError(
            f"{label} exceeds CBC's exact nine-player integer range"
        )
    return matrix


def _micro_vector(values: Sequence[int] | np.ndarray, n: int, label: str) -> np.ndarray:
    array = np.asarray(values)
    if array.dtype.kind not in "iu" or array.dtype.itemsize > 8:
        raise ResidualWorldError(f"{label} must be integer micro-DK points")
    if array.dtype.kind == "u" and array.size and int(array.max()) > np.iinfo(
        np.int64
    ).max:
        raise ResidualWorldError(f"{label} exceeds signed int64")
    array = array.astype(np.int64, copy=False)
    if array.ndim != 1 or len(array) != n:
        raise ResidualWorldError(f"{label} is misaligned")
    return array


def make_cbc_solver(
    max_seconds: int,
    warm_start: bool = CBC_WARM_START,
    *,
    evidence_root: str | Path | None = None,
) -> _RetainedCbcSolver:
    if pulp.__version__ != PINNED_PULP_VERSION:
        raise SolverFailure(
            f"residual proof requires PuLP {PINNED_PULP_VERSION}"
        )
    seconds = _strict_integer(max_seconds, "CBC time limit")
    if seconds <= 0:
        raise ResidualWorldError("CBC time limit must be a positive integer")
    warm = bool(warm_start)
    return _RetainedCbcSolver(
        seconds,
        warm,
        # Radix/positive-part auxiliaries are continuous exact equalities.
        # CBC 2.10.3 can generate invalid cuts for this numerically structured
        # subproblem; auxiliary solves are identified by warm_start=False.
        None if warm else CBC_AUXILIARY_CUTS,
        evidence_root=evidence_root,
    )


def _default_solver_factory(
    max_seconds: int, warm_start: bool
) -> _RetainedCbcSolver:
    return make_cbc_solver(max_seconds, warm_start)


def _score_expression(
    model: LegalLineupModel,
    coefficients: np.ndarray,
) -> pulp.LpAffineExpression:
    return pulp.lpSum(
        model.decision[player.player_id] * int(coefficients[index])
        for index, player in enumerate(model.players)
    )


def _register_implied_integer(
    problem: pulp.LpProblem, variable: pulp.LpVariable
) -> None:
    """Declare one continuous auxiliary as mathematically integer-valued.

    Only exact equality circuits whose sources are already registered integer
    may use this seam.  The complete declaration is captured before each MPS
    serialization and independently reproduced when pricing/bound models are
    rebuilt for semantic evidence validation.
    """
    names = getattr(problem, "_residual_implied_integer_names", None)
    if names is None:
        names = set()
        setattr(problem, "_residual_implied_integer_names", names)
    if variable.name in names:
        raise ResidualWorldError("implied-integer auxiliary was registered twice")
    names.add(variable.name)


def _centered_score_expression(
    model: LegalLineupModel,
    coefficients: np.ndarray,
) -> tuple[pulp.LpAffineExpression, int]:
    """Return a centered direct score objective and its fixed-roster offset."""
    values = np.asarray(coefficients, dtype=np.int64)
    center = (int(values.min()) + int(values.max())) // 2
    return _score_expression(model, values - center), center * ROSTER_SIZE


def _bound_score_objective(
    model: LegalLineupModel,
    coefficients: np.ndarray,
    *,
    name: str,
) -> tuple[pulp.LpAffineExpression, pulp.LpVariable, int]:
    """Expose small quotient/remainder objectives for an exact bound solve.

    CBC serializes a large integral objective through a decimal double and can
    write ``N.00000003`` even when the independently reconstructed value is
    exactly ``N``.  A prospective base-100 quotient then remainder
    solve is lexicographically identical to optimizing the full micro-DK
    integer, while each solver objective remains small and exactly serialized.
    """
    values = np.asarray(coefficients, dtype=np.int64)
    center = int(values.min())
    shifted = values - center
    upper = sum(sorted((int(value) for value in shifted), reverse=True)[:ROSTER_SIZE])
    width = 1
    power = BOUND_OBJECTIVE_BASE
    while upper >= power:
        width += 1
        power *= BOUND_OBJECTIVE_BASE
    digits: list[pulp.LpVariable] = []
    carry: pulp.LpVariable | None = None
    carry_upper = 0
    for place in range(width):
        divisor = BOUND_OBJECTIVE_BASE ** place
        coefficient_digits = np.asarray([
            (int(value) // divisor) % BOUND_OBJECTIVE_BASE
            for value in shifted
        ], dtype=np.int64)
        digit = pulp.LpVariable(
            f"{name}_digit_{place:02d}",
            lowBound=0,
            upBound=BOUND_OBJECTIVE_BASE - 1,
            cat="Integer",
        )
        expression = _score_expression(model, coefficient_digits)
        if carry is not None:
            expression += carry
        digits.append(digit)
        if place == width - 1:
            model.problem += expression == digit, (
                f"{name}_carry_link_{place:02d}"
            )
        else:
            carry_upper = (
                sum(sorted(
                    (int(value) for value in coefficient_digits),
                    reverse=True,
                )[:ROSTER_SIZE])
                + carry_upper
            ) // BOUND_OBJECTIVE_BASE
            next_carry = pulp.LpVariable(
                f"{name}_carry_{place + 1:02d}",
                lowBound=0,
                upBound=carry_upper,
                cat="Integer",
            )
            model.problem += expression == (
                digit + BOUND_OBJECTIVE_BASE * next_carry
            ), f"{name}_carry_link_{place:02d}"
            carry = next_carry
    quotient = pulp.lpSum(
        digit * (BOUND_OBJECTIVE_BASE ** (place - 1))
        for place, digit in enumerate(digits)
        if place >= 1
    )
    return quotient, digits[0], center * ROSTER_SIZE


def _digit_score_expression(
    model: LegalLineupModel,
    coefficients: np.ndarray,
    *,
    name: str,
) -> pulp.LpAffineExpression:
    """Return one exact score through bounded base-100 digit/carry rows.

    Unlike the old continuous Horner prefixes, every auxiliary here is a
    small general integer.  The resulting affine expression is the same
    micro-DK integer as the direct nine-player sum, while CBC cannot hide a
    fractional prefix or an ulp-sized bound violation in retained evidence.
    """
    quotient, remainder, offset = _bound_score_objective(
        model, coefficients, name=name
    )
    return BOUND_OBJECTIVE_BASE * quotient + remainder + offset


def _exact_score_variable(
    model: LegalLineupModel,
    coefficients: np.ndarray,
    *,
    name: str,
    lower_bound: int | None = None,
    upper_bound: int | None = None,
    integer_auxiliaries: bool = False,
) -> pulp.LpVariable:
    """Link an exact integer score using only radix-sized coefficients.

    A direct micro-DK row has coefficients around ``1e8``.  CBC scales such a
    row and can accept a several-micro-point violation even when every
    variable is integral.  Signed base-100 Horner accumulation is exactly the
    same integer sum, but every matrix coefficient is at most 100.
    """
    values = tuple(int(value) for value in np.asarray(coefficients, dtype=np.int64))
    maximum = max(abs(value) for value in values)
    width = 1
    while maximum >= SCORE_RADIX:
        maximum //= SCORE_RADIX
        width += 1

    prefixes = [0] * len(values)
    previous: pulp.LpVariable | None = None
    for place in range(width - 1, -1, -1):
        divisor = SCORE_RADIX ** place
        digits = [
            (1 if value >= 0 else -1) * ((abs(value) // divisor) % SCORE_RADIX)
            for value in values
        ]
        prefixes = [
            prefix * SCORE_RADIX + digit
            for prefix, digit in zip(prefixes, digits, strict=True)
        ]
        ordered = sorted(prefixes)
        loose_lower = sum(ordered[:ROSTER_SIZE])
        loose_upper = sum(ordered[-ROSTER_SIZE:])
        final = place == 0
        variable = pulp.LpVariable(
            f"{name}_digit_{place:02d}",
            lowBound=(lower_bound if final and lower_bound is not None else loose_lower),
            upBound=(upper_bound if final and upper_bound is not None else loose_upper),
            # Every prefix is an integer-valued function of binary x.  Keep
            # the redundant auxiliaries continuous; exact integer objectives
            # are exposed through a dedicated terminal objective variable.
            cat="Integer" if integer_auxiliaries else "Continuous",
        )
        if not integer_auxiliaries:
            _register_implied_integer(model.problem, variable)
        digit_expression = _score_expression(
            model, np.asarray(digits, dtype=np.int64)
        )
        if previous is None:
            model.problem += variable == digit_expression, (
                f"{name}_link_{place:02d}"
            )
        else:
            model.problem += variable == (
                SCORE_RADIX * previous + digit_expression
            ), f"{name}_link_{place:02d}"
        previous = variable
    if previous is None:  # pragma: no cover - width is always at least one
        raise AssertionError("exact score radix width is empty")
    return previous


def _constant_times_binary(
    problem: pulp.LpProblem,
    constant: int,
    binary: pulp.LpVariable,
    *,
    name: str,
) -> pulp.LpAffineExpression | pulp.LpVariable:
    """Return an exact ``constant * binary`` with radix-sized rows."""
    value = _strict_integer(constant, "indicator multiplier")
    if value < 0:
        raise ResidualWorldError("indicator multiplier must be nonnegative")
    if value < SCORE_RADIX:
        return value * binary
    digits: list[int] = []
    remainder = value
    while remainder:
        digits.append(remainder % SCORE_RADIX)
        remainder //= SCORE_RADIX
    previous: pulp.LpVariable | None = None
    prefix = 0
    for ordinal, digit in enumerate(reversed(digits)):
        prefix = prefix * SCORE_RADIX + digit
        variable = pulp.LpVariable(
            f"{name}_product_{ordinal:02d}",
            lowBound=0,
            upBound=prefix,
            # Exactly integer whenever ``binary`` is integral.
            cat="Continuous",
        )
        _register_implied_integer(problem, variable)
        if previous is None:
            problem += variable == digit * binary, f"{name}_product_link_{ordinal:02d}"
        else:
            problem += variable == SCORE_RADIX * previous + digit * binary, (
                f"{name}_product_link_{ordinal:02d}"
            )
        previous = variable
    if previous is None:  # constant zero is returned by the fast path
        raise AssertionError("constant product radix width is empty")
    return previous


def _exact_weighted_sum_variable(
    problem: pulp.LpProblem,
    terms: Sequence[tuple[pulp.LpVariable, int]],
    *,
    name: str,
    lower_bound: int,
    upper_bound: int,
) -> pulp.LpVariable:
    """Link an arbitrary bounded binary/implied-binary weighted sum."""
    if not terms:
        raise ResidualWorldError("exact weighted sum has no terms")
    coefficients = tuple(
        _strict_integer(coefficient, "exact weighted coefficient")
        for _, coefficient in terms
    )
    maximum = max(abs(value) for value in coefficients)
    width = 1
    while maximum >= SCORE_RADIX:
        maximum //= SCORE_RADIX
        width += 1
    prefixes = [0] * len(terms)
    previous: pulp.LpVariable | None = None
    for place in range(width - 1, -1, -1):
        divisor = SCORE_RADIX ** place
        digits = [
            (1 if value >= 0 else -1) * ((abs(value) // divisor) % SCORE_RADIX)
            for value in coefficients
        ]
        prefixes = [
            prefix * SCORE_RADIX + digit
            for prefix, digit in zip(prefixes, digits, strict=True)
        ]
        loose_lower = sum(min(0, value) for value in prefixes)
        loose_upper = sum(max(0, value) for value in prefixes)
        final = place == 0
        variable = pulp.LpVariable(
            f"{name}_digit_{place:02d}",
            lowBound=lower_bound if final else loose_lower,
            upBound=upper_bound if final else loose_upper,
            cat="Continuous",
        )
        _register_implied_integer(problem, variable)
        digit_expression = pulp.lpSum(
            source * digit for (source, _), digit in zip(terms, digits, strict=True)
        )
        if previous is None:
            problem += variable == digit_expression, f"{name}_link_{place:02d}"
        else:
            problem += variable == SCORE_RADIX * previous + digit_expression, (
                f"{name}_link_{place:02d}"
            )
        previous = variable
    if previous is None:  # pragma: no cover - width is always at least one
        raise AssertionError("exact weighted radix width is empty")
    return previous


def _binary_weighted_sum(
    problem: pulp.LpProblem,
    terms: Sequence[tuple[pulp.LpVariable, int]],
    *,
    upper_bound: int,
    name: str,
    initialize_from_sources: bool = False,
) -> _BinaryNumber:
    """Represent a known-nonnegative integer sum with a signed bit adder."""
    upper = _strict_integer(upper_bound, "binary sum upper bound")
    if upper < 0:
        raise ResidualWorldError("binary sum upper bound is negative")
    normalized = tuple(
        (variable, _strict_integer(coefficient, "binary sum coefficient"))
        for variable, coefficient in terms
        if coefficient != 0
    )
    # Signed terms can cancel to a small upper bound while still carrying
    # through a higher source bit (for example 5-3=2).  Process every source
    # coefficient bit before requiring the terminal carry to be zero.
    coefficient_width = max(
        (abs(coefficient).bit_length() for _, coefficient in normalized),
        default=1,
    )
    width = max(1, upper.bit_length(), coefficient_width)
    bits = tuple(
        pulp.LpVariable(f"{name}_bit_{place:02d}", cat="Binary")
        for place in range(width)
    )
    carry: pulp.LpVariable | None = None
    carry_lower = 0
    carry_upper = 0
    initial_carry = 0
    for place, bit in enumerate(bits):
        digit_terms = tuple(
            (
                variable,
                (1 if coefficient >= 0 else -1)
                * ((abs(coefficient) >> place) & 1),
            )
            for variable, coefficient in normalized
        )
        expression = pulp.lpSum(
            variable * digit for variable, digit in digit_terms
        )
        expression_lower = carry_lower
        expression_upper = carry_upper
        for variable, digit in digit_terms:
            lower = _exact_model_bound(
                variable.lowBound, "binary-adder source lower bound"
            )
            upper_bound = _exact_model_bound(
                variable.upBound, "binary-adder source upper bound"
            )
            if lower is None or upper_bound is None:
                raise ResidualWorldError(
                    "binary-adder source does not have a finite exact domain"
                )
            first = digit * lower
            second = digit * upper_bound
            expression_lower += min(first, second)
            expression_upper += max(first, second)
        if carry is not None:
            expression += carry
        initial_total: int | None = None
        if initialize_from_sources:
            initial_total = initial_carry
            for variable, coefficient in normalized:
                raw = variable.value()
                if raw is None or abs(float(raw) - round(float(raw))) > 1e-9:
                    raise SolverFailure(
                        "binary sum MIP-start source is not exact integral"
                    )
                initial_total += int(round(float(raw))) * (
                    (1 if coefficient >= 0 else -1)
                    * ((abs(coefficient) >> place) & 1)
                )
            initial_bit = initial_total % 2
            bit.setInitialValue(initial_bit)
        if place == width - 1:
            problem += expression == bit, f"{name}_adder_{place:02d}"
            if initial_total is not None and initial_total != initial_bit:
                raise SolverFailure("binary sum MIP start exceeds exact width")
            continue
        # From expression == bit + 2*next_carry and bit in {0,1}, these
        # conservative finite integer bounds contain every feasible carry.
        # They are part of the retained exact-domain manifest and eliminate
        # Coin's implicit unbounded integer range from the proof surface.
        next_lower = (expression_lower - 1) // 2
        next_upper = -((-expression_upper) // 2)
        next_carry = pulp.LpVariable(
            f"{name}_carry_{place + 1:02d}",
            lowBound=next_lower,
            upBound=next_upper,
            cat="Integer",
        )
        problem += expression == bit + 2 * next_carry, (
            f"{name}_adder_{place:02d}"
        )
        if initial_total is not None:
            initial_carry = (initial_total - initial_bit) // 2
            next_carry.setInitialValue(initial_carry)
        carry = next_carry
        carry_lower = next_lower
        carry_upper = next_upper
    return _BinaryNumber(bits, upper)


def _binary_value(number: _BinaryNumber) -> int:
    return sum(
        (1 << place) * int(round(float(bit.value())))
        for place, bit in enumerate(number.bits)
    )


def _binary_objective_chunks(
    number: _BinaryNumber,
) -> tuple[pulp.LpAffineExpression, ...]:
    """Return most-significant-first exact four-bit objective chunks."""
    chunks: list[pulp.LpAffineExpression] = []
    high = len(number.bits) - 1
    while high >= 0:
        low = max(0, high - RESIDUAL_OBJECTIVE_CHUNK_BITS + 1)
        chunks.append(pulp.lpSum(
            number.bits[place] * (1 << (place - low))
            for place in range(low, high + 1)
        ))
        high = low - 1
    return tuple(chunks)


def _residual_chunk_solver_mask(
    value: int, upper_bound: int, *, bit_width: int
) -> tuple[bool, ...]:
    """Return which MSB-first chunks are not forced zero by the exact bound."""
    upper = _strict_integer(upper_bound, "residual chunk upper bound")
    result = _strict_integer(value, "residual chunk value")
    width = _strict_integer(bit_width, "residual chunk bit width")
    if upper < 0 or not 0 <= result <= upper or width < max(1, upper.bit_length()):
        raise ResidualWorldError("residual chunk mask inputs are outside bounds")
    prefix = 0
    flags: list[bool] = []
    high = width - 1
    while high >= 0:
        low = max(0, high - RESIDUAL_OBJECTIVE_CHUNK_BITS + 1)
        chunk_width = high - low + 1
        mask = (1 << chunk_width) - 1
        base = prefix << (chunk_width + low)
        if base > upper:
            raise ResidualWorldError("residual chunk prefix exceeds exact bound")
        maximum = min(mask, (upper - base) >> low)
        chunk = (result >> low) & mask
        if chunk > maximum:
            raise ResidualWorldError("residual chunk exceeds exact prefix bound")
        flags.append(maximum > 0)
        prefix = (prefix << chunk_width) | chunk
        high = low - 1
    return tuple(flags)


def _residual_chunk_values(
    value: int, upper_bound: int, *, bit_width: int | None = None
) -> tuple[int, ...]:
    upper = _strict_integer(upper_bound, "residual chunk upper bound")
    result = _strict_integer(value, "residual chunk value")
    if upper < 0 or not 0 <= result <= upper:
        raise ResidualWorldError("residual chunk value is outside its bound")
    width = max(1, upper.bit_length()) if bit_width is None else _strict_integer(
        bit_width, "residual chunk bit width"
    )
    if width < max(1, upper.bit_length()):
        raise ResidualWorldError("residual chunk bit width is too small")
    values: list[int] = []
    high = width - 1
    while high >= 0:
        low = max(0, high - RESIDUAL_OBJECTIVE_CHUNK_BITS + 1)
        mask = (1 << (high - low + 1)) - 1
        values.append((result >> low) & mask)
        high = low - 1
    return tuple(values)


def _binary_ge_indicator(
    problem: pulp.LpProblem,
    number: _BinaryNumber,
    threshold: int,
    *,
    name: str,
    initial_number: int | None = None,
) -> pulp.LpVariable:
    """Return a binary equal to ``number >= threshold`` by Boolean circuit."""
    target = _strict_integer(threshold, "binary comparison threshold")
    initial = None if initial_number is None else _strict_integer(
        initial_number, "binary comparison MIP-start value"
    )
    if initial is not None and not 0 <= initial <= number.upper_bound:
        raise SolverFailure("binary comparison MIP start is outside its bound")
    indicator = pulp.LpVariable(f"{name}_indicator", cat="Binary")
    if target <= 0:
        problem += indicator == 1, f"{name}_always_true"
        if initial is not None:
            indicator.setInitialValue(1)
        return indicator
    if target > number.upper_bound:
        problem += indicator == 0, f"{name}_always_false"
        if initial is not None:
            indicator.setInitialValue(0)
        return indicator

    prefix: pulp.LpAffineExpression | pulp.LpVariable = pulp.lpSum([]) + 1
    initial_prefix = 1
    greater: list[pulp.LpVariable] = []
    initial_greater: list[int] = []
    for place in range(len(number.bits) - 1, -1, -1):
        bit = number.bits[place]
        initial_bit = None if initial is None else ((initial >> place) & 1)
        target_bit = (target >> place) & 1
        if target_bit == 0:
            decisive = pulp.LpVariable(
                f"{name}_greater_{place:02d}", cat="Binary"
            )
            problem += decisive <= prefix, f"{name}_greater_prefix_{place:02d}"
            problem += decisive <= bit, f"{name}_greater_bit_{place:02d}"
            problem += decisive >= prefix + bit - 1, (
                f"{name}_greater_lower_{place:02d}"
            )
            greater.append(decisive)
            if initial_bit is not None:
                initial_decisive = initial_prefix & initial_bit
                decisive.setInitialValue(initial_decisive)
                initial_greater.append(initial_decisive)
            literal = 1 - bit
            initial_literal = None if initial_bit is None else 1 - initial_bit
        else:
            literal = bit
            initial_literal = initial_bit
        next_prefix = pulp.LpVariable(
            f"{name}_equal_{place:02d}", cat="Binary"
        )
        problem += next_prefix <= prefix, f"{name}_equal_prefix_{place:02d}"
        problem += next_prefix <= literal, f"{name}_equal_bit_{place:02d}"
        problem += next_prefix >= prefix + literal - 1, (
            f"{name}_equal_lower_{place:02d}"
        )
        if initial_literal is not None:
            initial_prefix &= initial_literal
            next_prefix.setInitialValue(initial_prefix)
        prefix = next_prefix
    # Greater-at-first-difference terms and final equality are disjoint.
    problem += indicator == pulp.lpSum([*greater, prefix]), f"{name}_result"
    if initial is not None:
        indicator.setInitialValue(sum(initial_greater) + initial_prefix)
    return indicator


def _binary_score_number(
    model: LegalLineupModel,
    coefficients: np.ndarray,
    *,
    name: str,
) -> tuple[_BinaryNumber, int]:
    """Represent the lineup score after a fixed-cardinality nonnegative shift."""
    values = tuple(int(value) for value in np.asarray(coefficients, dtype=np.int64))
    center = min(values)
    shifted = tuple(value - center for value in values)
    upper = sum(sorted(shifted)[-ROSTER_SIZE:])
    number = _binary_weighted_sum(
        model.problem,
        tuple(
            (model.decision[player.player_id], shifted[index])
            for index, player in enumerate(model.players)
        ),
        upper_bound=upper,
        name=name,
    )
    return number, center * ROSTER_SIZE


def _binary_positive_part(
    model: LegalLineupModel,
    score_number: _BinaryNumber,
    score_offset: int,
    coefficients: np.ndarray,
    upper: int,
    maximum: int,
    *,
    name: str,
) -> tuple[_BinaryNumber | None, pulp.LpVariable | None]:
    """Represent ``max(0,S-m)`` exactly with Boolean products and an adder."""
    hi = _strict_integer(upper, "positive-part upper bound")
    current = _strict_integer(maximum, "positive-part reference maximum")
    if hi <= current:
        return None, None
    positive = _binary_ge_indicator(
        model.problem,
        score_number,
        current + 1 - score_offset,
        name=f"{name}_positive",
    )
    products: list[pulp.LpVariable] = []
    for index, player in enumerate(model.players):
        product = pulp.LpVariable(
            f"{name}_selected_positive_{index:04d}",
            lowBound=0,
            upBound=1,
            cat="Continuous",
        )
        _register_implied_integer(model.problem, product)
        selected = model.decision[player.player_id]
        model.problem += product <= selected, f"{name}_product_x_{index:04d}"
        model.problem += product <= positive, f"{name}_product_b_{index:04d}"
        model.problem += product >= selected + positive - 1, (
            f"{name}_product_lower_{index:04d}"
        )
        products.append(product)
    terms = [
        (product, int(coefficients[index]))
        for index, product in enumerate(products)
    ]
    terms.append((positive, -current))
    return _binary_weighted_sum(
        model.problem,
        terms,
        upper_bound=hi - current,
        name=f"{name}_residual",
    ), positive


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _resolve_real_directory(path: Path, label: str) -> Path:
    """Resolve an existing directory only after lstat-checking every component."""
    raw = Path(path)
    absolute = raw if raw.is_absolute() else Path.cwd() / raw
    if ".." in absolute.parts:
        raise SolverFailure(f"{label} is not a canonical directory path")
    current = Path(absolute.anchor)
    for part in absolute.parts[1:]:
        if part in {"", "."}:
            continue
        current /= part
        try:
            metadata = current.lstat()
        except OSError as exc:
            raise SolverFailure(f"{label} cannot be inspected exactly") from exc
        if stat.S_ISLNK(metadata.st_mode) or not stat.S_ISDIR(metadata.st_mode):
            raise SolverFailure(f"{label} or an ancestor is not a real directory")
    return absolute.resolve(strict=True)


def _stable_regular_file_bytes(path: Path) -> tuple[bytes, str]:
    """Read and hash one non-symlink regular inode without a path TOCTOU.

    The file descriptor, rather than a second path open, owns both the bytes
    consumed by the parser and their digest.  Device/inode/size/mtime are
    checked before and after the read so in-place mutation also fails closed.
    """
    raw_path = Path(path)
    if raw_path.is_symlink():
        raise SolverFailure("CBC retained artifact is a symlink")
    flags = os.O_RDONLY | getattr(os, "O_CLOEXEC", 0) | getattr(
        os, "O_NOFOLLOW", 0
    )
    try:
        descriptor = os.open(raw_path, flags)
    except OSError as exc:
        raise SolverFailure("CBC retained artifact cannot be opened exactly") from exc
    try:
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode) or before.st_size <= 0:
            raise SolverFailure("CBC retained artifact is not a nonempty regular file")
        chunks: list[bytes] = []
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            chunks.append(chunk)
        after = os.fstat(descriptor)
    finally:
        os.close(descriptor)
    identity_before = (
        before.st_dev,
        before.st_ino,
        before.st_size,
        before.st_mtime_ns,
        before.st_ctime_ns,
    )
    identity_after = (
        after.st_dev,
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
        after.st_ctime_ns,
    )
    payload = b"".join(chunks)
    if identity_before != identity_after or len(payload) != before.st_size:
        raise SolverFailure("CBC retained artifact changed while being read")
    return payload, hashlib.sha256(payload).hexdigest()


def _cbc_binary_sha256(path: str) -> str:
    return _sha256_file(Path(path).resolve())


_CBC_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
_MPS_WRITER_NUMBER = r"[ -]\d\.\d{12}e[+-]\d{2,3}"
_CBC_WARNING = re.compile(r"\b(?:Cbc|Cgl|Clp|Coin)\d+W\b")
_CBC_FORBIDDEN = re.compile(
    r"Stopped on|Exiting on maximum|Partial search|within gap tolerance|"
    r"Upper bound:|^Gap:|infeasible|unbounded|abandoned|\bnan\b|"
    r"\binf(?:inity)?\b|"
    r"Exiting as integer gap|maximum (?:time|node|solution)",
    re.IGNORECASE | re.MULTILINE,
)
_CBC_FINITE_INFEASIBILITY_DIAGNOSTIC = re.compile(
    rf"^(?:Clp\d+I\s+)?\d+\s+Obj\s+(?P<objective>{_CBC_NUMBER})\s+"
    rf"Primal inf\s+(?P<primal>{_CBC_NUMBER})(?:\s+\(\d+\))?"
    rf"(?:\s+Dual inf\s+(?P<dual>{_CBC_NUMBER})(?:\s+\(\d+\))?)?\s*$"
)


def _finite_cbc_decimal(value: str, label: str) -> Decimal:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise SolverFailure(f"CBC {label} is not finite numeric evidence") from exc
    # CBC consumes IEEE binary64.  A syntactically finite Decimal outside that
    # executable range is not a finite CBC number and may never be masked.
    try:
        as_float = float(parsed)
    except (OverflowError, ValueError) as exc:
        raise SolverFailure(f"CBC {label} is outside binary64 range") from exc
    if not parsed.is_finite() or not math.isfinite(as_float):
        raise SolverFailure(f"CBC {label} is outside binary64 range")
    return parsed


def _decode_integer_token(value: str, label: str) -> tuple[int, Decimal]:
    """Decode one registered integer token at the literal amendment boundary.

    Decimal precision is sized from the token itself, so ambient process
    context cannot round a just-over-boundary residue onto ``1e-9``.
    """
    raw = _finite_cbc_decimal(value, label)
    if abs(raw) >= CBC_EXACT_INTEGER_MAX + 1:
        raise SolverFailure(f"CBC {label} exceeds the exact integer range")
    precision = max(64, len(raw.as_tuple().digits) + 32)
    with localcontext() as context:
        context.prec = precision
        canonical_decimal = raw.to_integral_value(rounding=ROUND_HALF_EVEN)
        signed_residual = raw - canonical_decimal
        # Keep the comparison inside the same widened context.  Applying
        # ``abs`` after leaving it would let a hostile low-precision ambient
        # Decimal context round a just-over-boundary residue back to 1e-9.
        if signed_residual.copy_abs() > CBC_INTEGER_DECODE_EPS:
            raise SolverFailure("CBC integer token exceeds decode epsilon")
    return int(canonical_decimal), signed_residual


_CBC_BENIGN_PRESOLVED_MIP = re.compile(
    r"^Cbc3007W No integer variables - nothing to do[ \t]*$",
    re.MULTILINE,
)


def _cbc_warning_marker_text(log: str) -> str:
    """Mask only CBC's benign fully-presolved-MIP notice before warning scan.

    With preprocessing enabled (mandated by the LR8-v3 warm-chain protocol),
    CBC presolve can fix every integer variable of a small exact stage and
    then prints ``Cbc3007W No integer variables - nothing to do`` before
    solving the remaining problem to its exact optimum.  The message code
    ends in ``W`` so the blanket warning law would poison a correct exact
    receipt — the same misclassified-benign-terminal defect class that
    terminally failed the corpus v4 producer (``Integer infeasible``
    solution headers).  Only this complete, observed line is masked; the
    exact ``Result - Optimal solution found`` terminal and every other
    warning code remain enforced.
    """
    return _CBC_BENIGN_PRESOLVED_MIP.sub(
        "<benign presolved-mip notice>", log
    )


def _cbc_forbidden_marker_text(log: str) -> str:
    """Mask only CBC's finite intermediate LP infeasibility diagnostics.

    CBC writes ``Primal inf <finite>`` (and occasionally a paired
    ``Dual inf <finite>``) while iterating toward a subsequently proven exact
    optimum.  Here ``inf`` abbreviates *infeasibility*; it is not a nonfinite
    number.  Only the complete, observed CBC diagnostic grammar is masked.
    Every other bare ``inf`` remains visible to :data:`_CBC_FORBIDDEN`.
    """
    masked: list[str] = []
    for line in log.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        # The command is parsed independently against exact registered
        # executable/model/solution paths and options.  Path components are
        # opaque and may legitimately contain tokens such as ``inf``.
        if body.startswith("command line - "):
            masked.append("command line - <independently validated>" + ending)
            continue
        diagnostic = _CBC_FINITE_INFEASIBILITY_DIAGNOSTIC.fullmatch(body)
        if re.search(r"\binf\b", body, re.IGNORECASE) and diagnostic is not None:
            for group in ("objective", "primal", "dual"):
                token = diagnostic.group(group)
                if token is not None:
                    _finite_cbc_decimal(token, f"finite LP diagnostic {group}")
            body = re.sub(
                r"\binf\b", "finite_lp_diagnostic", body,
                flags=re.IGNORECASE,
            )
        masked.append(body + ending)
    return "".join(masked)


def _one_match(pattern: str, text: str, label: str) -> re.Match[str]:
    matches = list(re.finditer(pattern, text, re.MULTILINE))
    if len(matches) != 1:
        raise SolverFailure(f"CBC evidence has {len(matches)} {label} records")
    return matches[0]


def _decimal_integer(value: str, label: str) -> int:
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise SolverFailure(f"CBC {label} is not finite numeric evidence") from exc
    if not parsed.is_finite() or parsed != parsed.to_integral_value():
        raise SolverFailure(f"CBC {label} is not an exact integer")
    return int(parsed)


def _mps_integer(value: str, label: str) -> int:
    try:
        parsed = Decimal(value.strip())
    except InvalidOperation as exc:
        raise SolverFailure(f"CBC MPS {label} is nonnumeric") from exc
    if (
        not parsed.is_finite()
        or parsed != parsed.to_integral_value()
        or abs(parsed) >= CBC_EXACT_INTEGER_MAX + 1
    ):
        raise SolverFailure(f"CBC MPS {label} is outside exact integer range")
    return int(parsed)


def _parse_exact_mps_bytes(payload: bytes) -> _ParsedExactMps:
    """Parse only the pinned PuLP 3.3.2 free-MPS byte profile."""
    try:
        text = payload.decode("ascii")
    except UnicodeDecodeError as exc:
        raise SolverFailure("CBC retained MPS is not strict ASCII") from exc
    if not text.endswith("\n") or "\r" in text or "\x00" in text:
        raise SolverFailure("CBC retained MPS line-ending profile changed")
    lines = text[:-1].split("\n")
    if len(lines) < 8 or lines[0] not in {
        "*SENSE:Maximize", "*SENSE:Minimize",
    } or lines[1] != "NAME          MODEL":
        raise SolverFailure("CBC retained MPS header changed")
    sense = (
        pulp.LpMaximize if lines[0].endswith("Maximize") else pulp.LpMinimize
    )
    required_sections = ("ROWS", "COLUMNS", "RHS", "BOUNDS", "ENDATA")
    section_index = -1
    section: str | None = None
    objective_row: str | None = None
    rows: list[str] = []
    row_senses: dict[str, str] = {}
    columns: list[str] = []
    coefficients: dict[tuple[str, str], int] = {}
    integer_columns: set[str] = set()
    closed_columns: set[str] = set()
    current_column: str | None = None
    marker_active = False
    marker_column: str | None = None
    marker_seen_columns: set[str] = set()
    rhs: dict[str, int] = {}
    bound_records: dict[str, list[tuple[str, int | None]]] = {}
    bound_order: list[str] = []
    closed_bound_columns: set[str] = set()
    current_bound_column: str | None = None

    for line_number, line in enumerate(lines[2:], 3):
        if not line or line != line.rstrip():
            raise SolverFailure("CBC retained MPS whitespace profile changed")
        marker = line
        if marker in required_sections:
            expected_index = section_index + 1
            if expected_index >= len(required_sections) or marker != (
                required_sections[expected_index]
            ):
                raise SolverFailure("CBC retained MPS section order changed")
            if marker == "RHS" and marker_active:
                raise SolverFailure("CBC retained MPS integer marker is unbalanced")
            section_index = expected_index
            section = marker
            if marker == "ENDATA" and line_number != len(lines):
                raise SolverFailure("CBC retained MPS has data after ENDATA")
            continue
        if section == "ROWS":
            match = re.fullmatch(r" ([NLGE])  (OBJ|C\d{7})", line)
            if match is None:
                raise SolverFailure("CBC retained MPS row record changed")
            row_type, name = match.groups()
            if not rows and objective_row is None and (row_type, name) != (
                "N", "OBJ"
            ):
                raise SolverFailure("CBC retained MPS objective is not first")
            if name in row_senses or name == objective_row:
                raise SolverFailure("CBC retained MPS repeats a row")
            if row_type == "N":
                if objective_row is not None or name != "OBJ":
                    raise SolverFailure("CBC retained MPS objective row changed")
                objective_row = name
            else:
                expected_name = f"C{len(rows):07d}"
                if name != expected_name:
                    raise SolverFailure("CBC retained MPS row names are not contiguous")
                rows.append(name)
                row_senses[name] = row_type
        elif section == "COLUMNS":
            marker_match = re.fullmatch(
                r"    MARK      'MARKER'                 '(INTORG|INTEND)'",
                line,
            )
            if marker_match is not None:
                marker_kind = marker_match.group(1)
                if marker_kind == "INTORG":
                    if marker_active:
                        raise SolverFailure("CBC retained MPS nests INTORG markers")
                    marker_active = True
                    marker_column = None
                else:
                    if not marker_active or marker_column is None:
                        raise SolverFailure("CBC retained MPS has an empty INTORG block")
                    marker_active = False
                    assert marker_column is not None
                    marker_seen_columns.add(marker_column)
                    marker_column = None
                continue
            match = re.fullmatch(
                rf"    (X\d{{7}})  (OBJ     |C\d{{7}})  ({_MPS_WRITER_NUMBER})",
                line,
            )
            if match is None:
                raise SolverFailure("CBC retained MPS column record changed")
            column, row, raw_coefficient = match.groups()
            row = row.rstrip()
            is_new_column = current_column != column
            if current_column != column:
                if current_column is not None:
                    closed_columns.add(current_column)
                if column in closed_columns:
                    raise SolverFailure("CBC retained MPS column is noncontiguous")
                current_column = column
                if column != f"X{len(columns):07d}":
                    raise SolverFailure(
                        "CBC retained MPS column names are not contiguous"
                    )
                columns.append(column)
            if marker_active:
                if marker_column is None:
                    if not is_new_column:
                        raise SolverFailure(
                            "CBC retained MPS integer marker starts mid-column"
                        )
                    if column in marker_seen_columns:
                        raise SolverFailure(
                            "CBC retained MPS repeats an integer marker block"
                        )
                    marker_column = column
                    integer_columns.add(column)
                elif marker_column != column:
                    raise SolverFailure(
                        "CBC retained MPS integer block contains multiple columns"
                    )
            elif column in integer_columns:
                raise SolverFailure("CBC retained MPS integer column left its marker")
            if row != objective_row and row not in row_senses:
                raise SolverFailure("CBC retained MPS coefficient has unknown row")
            key = (column, row)
            coefficient = _mps_integer(raw_coefficient, "coefficient")
            if coefficient == 0 or key in coefficients:
                raise SolverFailure("CBC retained MPS coefficient repeats or is zero")
            coefficients[key] = coefficient
        elif section == "RHS":
            match = re.fullmatch(
                rf"    RHS       (C\d{{7}})  ({_MPS_WRITER_NUMBER})",
                line,
            )
            if match is None or match.group(1) not in row_senses:
                raise SolverFailure("CBC retained MPS RHS record changed")
            row, raw_rhs = match.groups()
            if row in rhs:
                raise SolverFailure("CBC retained MPS repeats an RHS row")
            rhs[row] = _mps_integer(raw_rhs, "RHS")
        elif section == "BOUNDS":
            match = re.fullmatch(
                rf" (BV|LO|UP|FX|FR|MI) BND       (X\d{{7}})"
                rf"(?:  ({_MPS_WRITER_NUMBER}))?",
                line,
            )
            if match is None:
                raise SolverFailure("CBC retained MPS bound record changed")
            bound_type, column, raw_value = match.groups()
            if column not in columns or bound_type not in {
                "BV", "LO", "UP", "FX", "FR", "MI",
            }:
                raise SolverFailure("CBC retained MPS bound form is unsupported")
            needs_value = bound_type in {"LO", "UP", "FX"}
            if (raw_value is not None) != needs_value:
                raise SolverFailure("CBC retained MPS bound value changed")
            value = (
                _mps_integer(raw_value, "bound") if raw_value is not None else None
            )
            if current_bound_column != column:
                if current_bound_column is not None:
                    closed_bound_columns.add(current_bound_column)
                if column in closed_bound_columns:
                    raise SolverFailure("CBC retained MPS bound column is noncontiguous")
                current_bound_column = column
            if column not in bound_records:
                bound_records[column] = []
                bound_order.append(column)
            bound_records[column].append((bound_type, value))
        else:
            raise SolverFailure("CBC retained MPS contains data outside a section")

    if section_index != len(required_sections) - 1 or section != "ENDATA":
        raise SolverFailure("CBC retained MPS is truncated")
    if marker_active or marker_seen_columns != integer_columns:
        raise SolverFailure("CBC retained MPS integer marker profile changed")
    if objective_row != "OBJ" or not rows or not columns:
        raise SolverFailure("CBC retained MPS has an incomplete symbol table")
    if tuple(rhs) != tuple(rows):
        raise SolverFailure("CBC retained MPS RHS is incomplete or reordered")
    expected_bound_order = tuple(
        column for column in columns if column in bound_records
    )
    if tuple(bound_order) != expected_bound_order:
        raise SolverFailure("CBC retained MPS bounds are reordered")

    bounds: dict[str, tuple[int | None, int | None]] = {}
    column_categories: dict[str, str] = {}
    for column in columns:
        records = bound_records.get(column, [])
        is_integer = column in integer_columns
        if not records:
            bounds[column] = (0, 1) if is_integer else (0, None)
            column_categories[column] = (
                "integer" if is_integer else "continuous"
            )
            continue
        kinds = tuple(kind for kind, _ in records)
        if len(records) == 1:
            kind, value = records[0]
            if kind == "BV":
                if not is_integer:
                    raise SolverFailure("CBC retained BV column is not integer")
                bounds[column] = (0, 1)
            elif kind == "FR":
                bounds[column] = (None, None)
            elif kind == "FX":
                assert value is not None
                bounds[column] = (value, value)
            elif kind == "LO":
                assert value is not None
                bounds[column] = (value, None)
            elif kind == "UP":
                assert value is not None
                bounds[column] = (0, value)
            else:
                raise SolverFailure("CBC retained MI bound lacks its paired UP")
        elif kinds == ("MI", "UP"):
            upper = records[1][1]
            assert upper is not None
            bounds[column] = (None, upper)
        elif kinds == ("LO", "UP"):
            lower = records[0][1]
            upper = records[1][1]
            assert lower is not None and upper is not None
            bounds[column] = (lower, upper)
        else:
            raise SolverFailure("CBC retained MPS has conflicting bound records")
        lower, upper = bounds[column]
        if lower is not None and upper is not None and lower > upper:
            raise SolverFailure("CBC retained MPS has reversed bounds")
        column_categories[column] = (
            "binary"
            if kinds == ("BV",)
            else "integer"
            if is_integer
            else "continuous"
        )

    return _ParsedExactMps(
        sense=sense,
        objective_row=objective_row,
        rows=tuple(rows),
        row_senses=row_senses,
        columns=tuple(columns),
        integer_columns=frozenset(integer_columns),
        column_categories=column_categories,
        coefficients=coefficients,
        rhs=rhs,
        bounds=bounds,
    )


def _parse_exact_mps(model_path: Path) -> _ParsedExactMps:
    payload, _ = _stable_regular_file_bytes(Path(model_path))
    return _parse_exact_mps_bytes(payload)


def _exact_pulp_integer(value: object, label: str) -> int:
    result = _exact_model_bound(value, label)
    if result is None:
        raise SolverFailure(f"{label} is not one finite exact integer")
    return result


def _validate_mps_exact_activity_profile(model: _ParsedExactMps) -> None:
    """Conservatively bound every executed row/objective below binary64 2^53.

    The L1 box bound deliberately does not exploit cancellation: opposite-sign
    coefficients can cancel at an extremum while individual double products
    still exceed the exact-integer range executed by CBC.
    """
    for row in (*model.rows, model.objective_row):
        magnitude = 0
        for (column, coefficient_row), coefficient in model.coefficients.items():
            if coefficient_row != row:
                continue
            lower, upper = model.bounds[column]
            if lower is None or upper is None:
                raise SolverFailure(
                    "CBC exact MPS has an unbounded row or objective domain"
                )
            magnitude += abs(coefficient) * max(abs(lower), abs(upper))
        if magnitude >= CBC_EXACT_INTEGER_MAX + 1:
            raise SolverFailure(
                "CBC worst-case row or objective activity exceeds exact range"
            )


def _validate_implied_integer_structure(
    model: _ParsedExactMps,
    manifest: Sequence[tuple[str, str, str, int | None, int | None]],
) -> None:
    """Prove MPS continuous/implied columns integral by exact row induction."""
    manifest_by_column = {row[0]: row for row in manifest}
    proven = {
        renamed for renamed, _, domain, lower, upper in manifest
        if domain in {"binary", "integer"}
        or (domain == "fixed_integer" and lower is not None and lower == upper)
    }
    unresolved = {
        renamed for renamed, _, domain, _, _ in manifest
        if domain == "implied_integer"
    }
    while unresolved:
        advanced = False
        for column in sorted(unresolved):
            for row in model.rows:
                if model.row_senses[row] != "E":
                    continue
                coefficient = model.coefficients.get((column, row), 0)
                if coefficient not in {-1, 1}:
                    continue
                sources = {
                    source for (source, source_row), value
                    in model.coefficients.items()
                    if source_row == row and source != column and value != 0
                }
                if sources <= proven:
                    proven.add(column)
                    unresolved.remove(column)
                    advanced = True
                    break
        if not advanced:
            missing = sorted(
                manifest_by_column[column][1] for column in unresolved
            )
            raise SolverFailure(
                "CBC implied-integer columns lack an exact defining proof: "
                f"{missing}"
            )


def _validate_problem_matches_mps(
    problem: pulp.LpProblem,
    model: _ParsedExactMps,
    manifest: Sequence[tuple[str, str, str, int | None, int | None]],
) -> None:
    """Prove the retained renamed MPS equals the registered PuLP graph exactly."""
    _materialize_zero_objective(problem)
    if problem.sense != model.sense:
        raise SolverFailure("CBC MPS sense differs from registered PuLP model")
    if problem.objective is None or _exact_pulp_integer(
        problem.objective.constant, "PuLP objective constant"
    ) != 0:
        raise SolverFailure("frozen residual objective constant is not exact zero")
    constraint_names, variable_names, objective_name = problem.normalisedNames()
    if objective_name != model.objective_row:
        raise SolverFailure("CBC MPS objective name differs from PuLP normalization")
    variables = tuple(problem.variables())
    if tuple(variable_names[variable.name] for variable in variables) != (
        model.columns
    ):
        raise SolverFailure("CBC MPS column order differs from PuLP normalization")
    if tuple(constraint_names[name] for name in problem.constraints) != model.rows:
        raise SolverFailure("CBC MPS row order differs from PuLP normalization")
    expected_senses = {
        pulp.LpConstraintLE: "L",
        pulp.LpConstraintEQ: "E",
        pulp.LpConstraintGE: "G",
    }
    if {
        constraint_names[name]: expected_senses[constraint.sense]
        for name, constraint in problem.constraints.items()
    } != dict(model.row_senses):
        raise SolverFailure("CBC MPS row senses differ from registered PuLP model")
    expected_rhs = {
        constraint_names[name]: _exact_pulp_integer(
            -constraint.constant, "PuLP constraint RHS"
        )
        for name, constraint in problem.constraints.items()
    }
    if expected_rhs != dict(model.rhs):
        raise SolverFailure("CBC MPS RHS differs from registered PuLP model")
    expected_coefficients: dict[tuple[str, str], int] = {}
    for variable, coefficient in problem.objective.items():
        exact = _exact_pulp_integer(coefficient, "PuLP objective coefficient")
        if exact:
            expected_coefficients[(variable_names[variable.name], objective_name)] = exact
    for scientific_row, constraint in problem.constraints.items():
        renamed_row = constraint_names[scientific_row]
        for variable, coefficient in constraint.items():
            exact = _exact_pulp_integer(
                coefficient, "PuLP constraint coefficient"
            )
            if exact:
                key = (variable_names[variable.name], renamed_row)
                if key in expected_coefficients:
                    raise SolverFailure("registered PuLP coefficient repeats")
                expected_coefficients[key] = exact
    if expected_coefficients != dict(model.coefficients):
        raise SolverFailure("CBC MPS coefficients differ from registered PuLP model")
    frozen_manifest = tuple(manifest)
    if frozen_manifest != _variable_domain_manifest(problem):
        raise SolverFailure("CBC variable-domain manifest differs from PuLP model")
    expected_bounds = {
        renamed: (lower, upper)
        for renamed, _, _, lower, upper in frozen_manifest
    }
    expected_categories = {
        renamed: (
            "binary" if domain == "binary"
            else "integer" if domain == "integer"
            else "continuous"
        )
        for renamed, _, domain, _, _ in frozen_manifest
    }
    if expected_bounds != dict(model.bounds):
        raise SolverFailure("CBC MPS bounds differ from registered PuLP model")
    if expected_categories != dict(model.column_categories):
        raise SolverFailure(
            "CBC MPS categories differ from registered PuLP model"
        )
    _validate_implied_integer_structure(model, manifest)
    _validate_mps_exact_activity_profile(model)


def _validate_solution_body(
    solution: str,
    model_path: Path,
    variable_domain_manifest: Sequence[
        tuple[str, str, str, int | None, int | None]
    ],
    *,
    parsed_model: _ParsedExactMps | None = None,
) -> tuple[int, str, int, Decimal, tuple[tuple[str, str, int, str], ...], int]:
    """Decode near-integral tokens, then prove the exact retained MPS."""
    model = parsed_model if parsed_model is not None else _parse_exact_mps(model_path)
    manifest = tuple(variable_domain_manifest)
    if tuple(row[0] for row in manifest) != model.columns or len({
        row[1] for row in manifest
    }) != len(manifest):
        raise SolverFailure("CBC variable-domain manifest is not bijective to MPS")
    for renamed, scientific, domain, lower, upper in manifest:
        if not scientific or domain not in {
            "binary", "integer", "implied_integer", "fixed_integer",
        }:
            raise SolverFailure("CBC variable-domain manifest has an unknown domain")
        expected_category = (
            domain if domain in {"binary", "integer"} else "continuous"
        )
        if model.column_categories[renamed] != expected_category:
            raise SolverFailure("CBC MPS category disagrees with manifest")
        if model.bounds[renamed] != (lower, upper):
            raise SolverFailure("CBC MPS bounds disagree with variable manifest")
        if domain == "binary" and (lower, upper) != (0, 1):
            raise SolverFailure("CBC binary manifest bounds changed")
        if domain == "fixed_integer" and (lower is None or lower != upper):
            raise SolverFailure("CBC fixed-integer manifest bounds changed")

    if not solution.endswith("\n") or "\r" in solution or "\x00" in solution:
        raise SolverFailure("CBC solution line-ending profile changed")
    body = solution[:-1].split("\n")[1:]
    if len(body) != len(model.rows) + len(model.columns):
        raise SolverFailure("CBC solution body is missing or has extra rows")
    row_activity: dict[str, Decimal] = {}
    raw_columns: dict[str, Decimal] = {}
    raw_tokens: dict[str, str] = {}
    expected_names = (*model.rows, *model.columns)
    observed: list[str] = []
    for position, line in enumerate(body):
        fields = line.split()
        if fields and fields[0] == "**":
            raise SolverFailure(
                "CBC solution body contains a violated row or column"
            )
        if len(fields) != 4:
            raise SolverFailure("CBC solution body row is malformed")
        try:
            index = int(fields[0])
            values = (Decimal(fields[2]), Decimal(fields[3]))
        except (ValueError, InvalidOperation) as exc:
            raise SolverFailure("CBC solution body row is nonnumeric") from exc
        if not all(value.is_finite() for value in values):
            raise SolverFailure("CBC solution body row is nonfinite")
        local_position = (
            position if position < len(model.rows) else position - len(model.rows)
        )
        if index != local_position:
            raise SolverFailure("CBC solution body index sequence changed")
        name = fields[1]
        observed.append(name)
        if position < len(model.rows):
            row_activity[name] = values[0]
        else:
            raw_columns[name] = values[0]
            raw_tokens[name] = fields[2]
    if tuple(observed) != expected_names or len(set(observed)) != len(observed):
        raise SolverFailure("CBC solution body does not match its exact MPS")

    assignment: dict[str, int] = {}
    # Operational evidence retains every raw CBC assignment token.  The
    # scientific receipt binds only the canonical assignment digest, but a
    # reviewer must still be able to reconstruct the exact decoding boundary
    # (including signed zero/nonzero residue) from the retained proof bundle.
    decode_rows: list[tuple[str, str, int, str]] = []
    affected_count = 0
    maximum_residual = Decimal(0)
    scientific_by_renamed = {row[0]: row[1] for row in manifest}
    for renamed in model.columns:
        canonical, signed_residual = _decode_integer_token(
            raw_tokens[renamed], f"assignment token {renamed}"
        )
        residual = abs(signed_residual)
        lower, upper = model.bounds[renamed]
        if (lower is not None and canonical < lower) or (
            upper is not None and canonical > upper
        ):
            raise SolverFailure("CBC canonical assignment violates a bound")
        assignment[renamed] = canonical
        maximum_residual = max(maximum_residual, residual)
        affected_count += int(bool(residual))
        decode_rows.append((
            renamed, raw_tokens[renamed], canonical, str(signed_residual),
        ))

    _validate_mps_exact_activity_profile(model)

    def exact_activity(row: str) -> int:
        total = sum(
            coefficient * assignment[column]
            for (column, coefficient_row), coefficient in model.coefficients.items()
            if coefficient_row == row
        )
        if abs(total) >= CBC_EXACT_INTEGER_MAX + 1:
            raise SolverFailure("CBC reconstructed activity exceeds exact range")
        return total

    for row in model.rows:
        activity = exact_activity(row)
        # CBC's printed row value reflects its internal floating-point point,
        # while each printed column token is independently rounded.  The row
        # token remains mandatory, ordered, unique, finite, marker-free and
        # retained through the solution hash, but its numeric drift cannot
        # license or reject feasibility.  The canonical integer assignment and
        # exact retained MPS below are the decisive proof.
        _ = row_activity[row]
        target = model.rhs[row]
        relation = model.row_senses[row]
        if (
            (relation == "L" and activity > target)
            or (relation == "G" and activity < target)
            or (relation == "E" and activity != target)
        ):
            raise SolverFailure("CBC canonical assignment violates an MPS row")

    objective = exact_activity(model.objective_row)
    canonical_assignment_sha256 = _canonical_json_sha256([
        [renamed, scientific_by_renamed[renamed], assignment[renamed]]
        for renamed in model.columns
    ])
    return (
        objective,
        canonical_assignment_sha256,
        affected_count,
        maximum_residual,
        tuple(decode_rows),
        model.sense,
    )


def _validate_mip_start_body(
    mip_start: str,
    expected_values: Sequence[int] | None = None,
) -> tuple[str, int]:
    """Validate PuLP's complete renamed integer MIP-start artifact."""
    lines = mip_start.splitlines()
    if not lines or lines[0] != "Stopped on time - objective value 0":
        raise SolverFailure("CBC MIP start header changed")
    values: list[list[object]] = []
    for expected_index, line in enumerate(lines[1:]):
        fields = line.split()
        if len(fields) != 4:
            raise SolverFailure("CBC MIP start row is malformed")
        try:
            index = int(fields[0])
            value = Decimal(fields[2])
            reduced_cost = Decimal(fields[3])
        except (ValueError, InvalidOperation) as exc:
            raise SolverFailure("CBC MIP start row is nonnumeric") from exc
        expected_name = f"X{expected_index:07d}"
        if index != expected_index or fields[1] != expected_name:
            raise SolverFailure("CBC MIP start row order or name changed")
        if (
            not value.is_finite()
            or value != value.to_integral_value()
            or not reduced_cost.is_finite()
            or reduced_cost != 0
        ):
            raise SolverFailure("CBC MIP start is not exact integral/zero-cost")
        integer = int(value)
        if expected_values is not None and (
            expected_index >= len(expected_values)
            or integer != expected_values[expected_index]
        ):
            raise SolverFailure("CBC MIP start differs from captured values")
        values.append([expected_name, integer])
    if expected_values is not None and len(values) != len(expected_values):
        raise SolverFailure("CBC MIP start is incomplete")
    return _canonical_json_sha256(values), len(values)


def _validate_assignment_against_problem(
    problem: pulp.LpProblem,
    values: Mapping[str, int],
) -> int:
    """Reconstruct one complete scientific assignment against PuLP exactly."""
    variables = tuple(problem.variables())
    if set(values) != {variable.name for variable in variables}:
        raise SolverFailure("CBC MIP start is not complete for the current model")
    for variable in variables:
        value = values[variable.name]
        lower = _exact_model_bound(variable.lowBound, "MIP-start lower bound")
        upper = _exact_model_bound(variable.upBound, "MIP-start upper bound")
        if (lower is not None and value < lower) or (
            upper is not None and value > upper
        ):
            raise SolverFailure("CBC MIP start violates a current variable bound")
        if variable.cat == pulp.LpInteger and variable.isBinary() and value not in {
            0, 1
        }:
            raise SolverFailure("CBC MIP start violates a current binary domain")

    def activity(expression: pulp.LpAffineExpression) -> int:
        total = _exact_pulp_integer(expression.constant, "MIP-start constant")
        for variable, coefficient in expression.items():
            total += _exact_pulp_integer(
                coefficient, "MIP-start coefficient"
            ) * values[variable.name]
        if abs(total) >= CBC_EXACT_INTEGER_MAX + 1:
            raise SolverFailure("CBC MIP-start activity exceeds exact range")
        return total

    for constraint in problem.constraints.values():
        residual = activity(constraint)
        if (
            (constraint.sense == pulp.LpConstraintLE and residual > 0)
            or (constraint.sense == pulp.LpConstraintGE and residual < 0)
            or (constraint.sense == pulp.LpConstraintEQ and residual != 0)
        ):
            raise SolverFailure("CBC MIP start violates a current PuLP row")
    if problem.objective is None:
        raise SolverFailure("CBC MIP start has no current objective")
    return activity(problem.objective)


def _validate_assignment_against_mps(
    model: _ParsedExactMps,
    manifest: Sequence[tuple[str, str, str, int | None, int | None]],
    values: Mapping[str, int],
) -> int:
    """Reconstruct a scientific assignment against the retained executed MPS."""
    by_scientific = {scientific: renamed for renamed, scientific, *_ in manifest}
    if set(values) != set(by_scientific):
        raise SolverFailure("CBC MIP start names differ from the current manifest")
    assignment = {by_scientific[name]: value for name, value in values.items()}
    for column, value in assignment.items():
        lower, upper = model.bounds[column]
        if (lower is not None and value < lower) or (
            upper is not None and value > upper
        ):
            raise SolverFailure("CBC MIP start violates a retained MPS bound")
        if model.column_categories[column] == "binary" and value not in {0, 1}:
            raise SolverFailure("CBC MIP start violates a retained binary domain")

    def activity(row: str) -> int:
        total = sum(
            coefficient * assignment[column]
            for (column, coefficient_row), coefficient in model.coefficients.items()
            if coefficient_row == row
        )
        if abs(total) >= CBC_EXACT_INTEGER_MAX + 1:
            raise SolverFailure("CBC MIP-start MPS activity exceeds exact range")
        return total

    for row in model.rows:
        observed = activity(row)
        target = model.rhs[row]
        sense = model.row_senses[row]
        if (
            (sense == "L" and observed > target)
            or (sense == "G" and observed < target)
            or (sense == "E" and observed != target)
        ):
            raise SolverFailure("CBC MIP start violates a retained MPS row")
    return activity(model.objective_row)


def _validated_predecessor_receipt(
    problem: pulp.LpProblem,
) -> tuple[tuple[tuple[str, int], ...], CbcSolveEvidence]:
    """Return the exact immediately preceding retained solve assignment.

    A pair of mutable attributes is not proof.  Revalidate the retained CBC
    bundle, then require the in-memory predecessor values and renamed digest
    to be exactly the assignment independently decoded from that bundle.
    """
    values = getattr(problem, "_residual_proven_assignment", None)
    digest = getattr(problem, "_residual_proven_assignment_sha256", None)
    evidence = getattr(problem, "_residual_proven_evidence", None)
    if (
        values is None
        or not isinstance(digest, str)
        or not isinstance(evidence, CbcSolveEvidence)
    ):
        raise SolverFailure("CBC predecessor lacks a retained proven assignment")
    validate_cbc_solve_evidence(evidence)
    manifest = tuple(evidence.variable_domain_manifest)
    expected = _scientific_assignment_from_evidence(evidence)
    try:
        frozen_values = tuple((name, value) for name, value in values)
    except (TypeError, ValueError) as exc:
        raise SolverFailure("CBC predecessor assignment is malformed") from exc
    if (
        frozen_values != expected
        or digest != evidence.canonical_assignment_sha256
        or _canonical_json_sha256([
            [manifest_row[0], name, value]
            for manifest_row, (name, value) in zip(
                manifest, frozen_values, strict=True
            )
        ]) != digest
    ):
        raise SolverFailure("CBC predecessor assignment differs from its proof")
    return frozen_values, evidence


def _scientific_assignment_from_evidence(
    evidence: CbcSolveEvidence,
) -> tuple[tuple[str, int], ...]:
    """Reconstruct canonical scientific values from one validated solve."""
    manifest = tuple(evidence.variable_domain_manifest)
    decode_rows = tuple(evidence.integer_decode_rows)
    if len(manifest) != len(decode_rows):
        raise SolverFailure("CBC canonical assignment receipt is misaligned")
    assignment: list[tuple[str, int]] = []
    for manifest_row, decode_row in zip(manifest, decode_rows, strict=True):
        renamed, scientific, *_ = manifest_row
        if (
            not isinstance(scientific, str)
            or not scientific
            or decode_row[0] != renamed
            or isinstance(decode_row[2], bool)
            or not isinstance(decode_row[2], int)
        ):
            raise SolverFailure("CBC canonical assignment receipt is malformed")
        assignment.append((scientific, decode_row[2]))
    if len({name for name, _ in assignment}) != len(assignment):
        raise SolverFailure("CBC canonical assignment repeats a scientific name")
    return tuple(assignment)


def _validate_ordered_warm_predecessor(
    prior: CbcSolveEvidence,
    current: CbcSolveEvidence,
) -> None:
    """Prove one warm MST contains the immediately prior exact assignment."""
    validate_cbc_solve_evidence(prior)
    validate_cbc_solve_evidence(current)
    if not current.warm_start or current.mip_start_values is None:
        raise SolverFailure("ordered predecessor audit requires a warm solve")
    if current.predecessor_assignment_sha256 != (
        prior.canonical_assignment_sha256
    ):
        raise SolverFailure("warm solve names the wrong predecessor proof")
    prior_values = _scientific_assignment_from_evidence(prior)
    current_values = tuple(current.mip_start_values)
    if any(
        not isinstance(row, tuple)
        or len(row) != 2
        or not isinstance(row[0], str)
        or not row[0]
        or isinstance(row[1], bool)
        or not isinstance(row[1], int)
        for row in current_values
    ):
        raise SolverFailure("warm MIP-start scientific values are malformed")
    current_map = dict(current_values)
    if len(current_map) != len(current_values) or any(
        current_map.get(name) != value for name, value in prior_values
    ):
        raise SolverFailure(
            "warm MIP start does not contain its prior canonical assignment"
        )
    prior_names = {name for name, _ in prior_values}
    if prior_names == set(current_map) and current_values != prior_values:
        raise SolverFailure("same-model warm MIP start differs from predecessor")


def _copy_proven_assignment(
    source: pulp.LpProblem,
    destination: pulp.LpProblem,
) -> None:
    values, evidence = _validated_predecessor_receipt(source)
    source_names = {variable.name for variable in source.variables()}
    if source_names != {name for name, _ in values}:
        raise SolverFailure("CBC predecessor is not complete for its source model")
    _validate_assignment_against_problem(source, dict(values))
    setattr(destination, "_residual_proven_assignment", values)
    setattr(
        destination,
        "_residual_proven_assignment_sha256",
        evidence.canonical_assignment_sha256,
    )
    setattr(destination, "_residual_proven_evidence", evidence)
    destination_by_name = {
        variable.name: variable for variable in destination.variables()
    }
    if not {name for name, _ in values} <= set(destination_by_name):
        raise SolverFailure("CBC predecessor variables are absent after model copy")
    for name, value in values:
        destination_by_name[name].varValue = int(value)


def _clone_residual_problem(
    problem: pulp.LpProblem,
    *,
    copy_proven_assignment: bool = False,
) -> pulp.LpProblem:
    """Clone PuLP state without dropping residual proof metadata.

    PuLP 3.3.2's ``deepcopy`` copies objectives/constraints/SOS only.  The
    implied-integer registry is part of the reviewed exact model law, so every
    research clone freezes an independent immutable copy and proves it names
    columns that actually remain in the clone.  Proven-solve provenance is a
    separate opt-in because semantic receipt rebuilds must remain score-free
    and solver-artifact independent.
    """
    if type(copy_proven_assignment) is not bool:
        raise SolverFailure("residual clone provenance flag must be boolean")
    raw_names = getattr(problem, "_residual_implied_integer_names", set())
    try:
        names = frozenset(raw_names)
    except TypeError as exc:
        raise SolverFailure("residual implied-integer registry is malformed") from exc
    if any(not isinstance(name, str) or not name for name in names):
        raise SolverFailure("residual implied-integer registry is malformed")
    clone = problem.deepcopy()
    clone_variable_names = {variable.name for variable in clone.variables()}
    if not names <= clone_variable_names:
        raise SolverFailure(
            "residual implied-integer registry references a missing clone column"
        )
    setattr(clone, "_residual_implied_integer_names", names)
    if frozenset(getattr(clone, "_residual_implied_integer_names")) != names:
        raise SolverFailure("residual implied-integer registry changed during clone")
    if copy_proven_assignment:
        _copy_proven_assignment(problem, clone)
    return clone


def _command_value(tokens: Sequence[str], flag: str) -> str:
    indices = [index for index, value in enumerate(tokens) if value == flag]
    if len(indices) != 1 or indices[0] + 1 >= len(tokens):
        raise SolverFailure(f"CBC command does not contain exactly one {flag}")
    return tokens[indices[0] + 1]


def _validate_exact_command_tokens(
    command: str,
    *,
    cbc_path: str | Path,
    model_path: str | Path,
    solution_path: str | Path,
    mip_start_path: str | Path | None,
    sense: int,
    max_seconds: int,
    warm_start: bool,
    cuts: bool | None,
    preprocess_off: bool,
) -> None:
    tokens = shlex.split(command)
    if len(tokens) < 2 or Path(tokens[0]).resolve() != Path(cbc_path).resolve():
        raise SolverFailure("CBC command executable changed")
    if Path(tokens[1]).resolve() != Path(model_path).resolve():
        raise SolverFailure("CBC command model path changed")
    expected = [tokens[0], tokens[1]]
    if sense == pulp.LpMaximize:
        expected.append("-max")
    elif sense != pulp.LpMinimize:
        raise SolverFailure("CBC command has an unknown objective sense")
    if warm_start:
        if mip_start_path is None:
            raise SolverFailure("CBC warm command lacks a registered MIP start")
        expected.extend(("-mips", str(mip_start_path)))
    elif mip_start_path is not None:
        raise SolverFailure("CBC cold command receipts a MIP start")
    expected.extend(("-sec", str(max_seconds)))
    if cuts is False:
        expected.extend(("-cuts", "off"))
    elif cuts is not None:
        raise SolverFailure("CBC command cuts receipt is malformed")
    expected.extend((
        "-randomSeed", str(CBC_RANDOM_SEED),
        "-randomCbcSeed", str(CBC_RANDOM_SEED),
        "-primalTolerance", "1e-9",
        "-integerTolerance", CBC_INTEGER_TOLERANCE_OPTION,
    ))
    if preprocess_off:
        expected.extend(("-preprocess", "off"))
    expected.extend((
        "-ratio", "0.0",
        "-allow", "0.0",
        "-threads", "1",
        "-timeMode", "elapsed",
        "-solve",
        "-printingOptions", "all",
        "-solution", str(solution_path),
    ))
    if tokens != expected:
        raise SolverFailure("CBC command differs from the exact registered grammar")


def _validate_retained_command(
    evidence: CbcSolveEvidence,
    command: str,
) -> None:
    _validate_exact_command_tokens(
        command,
        cbc_path=evidence.cbc_path,
        model_path=evidence.model_path,
        solution_path=evidence.solution_path,
        mip_start_path=evidence.mip_start_path,
        sense=evidence.problem_sense,
        max_seconds=evidence.max_seconds,
        warm_start=evidence.warm_start,
        cuts=evidence.cuts,
        preprocess_off=evidence.preprocess_off,
    )


def _parse_cbc_evidence(
    problem: pulp.LpProblem,
    solver: _RetainedCbcSolver,
    label: str,
) -> CbcSolveEvidence:
    if solver.evidence is not None:
        raise SolverFailure("CBC evidence path or receipt was reused")
    required = {
        "log": solver.evidence_directory / "cbc.log",
        "solution": solver.artifact_paths.get("sol"),
        "model": solver.artifact_paths.get("mps"),
    }
    if any(path is None or not path.is_file() or path.stat().st_size == 0 for path in required.values()):
        raise SolverFailure("CBC retained evidence is missing or empty")
    log_path = required["log"]
    solution_path = required["solution"]
    model_path = required["model"]
    assert log_path is not None and solution_path is not None and model_path is not None
    manifest_path = solver.variable_domain_manifest_path
    if (
        manifest_path is None
        or not manifest_path.is_file()
        or manifest_path.stat().st_size == 0
    ):
        raise SolverFailure("CBC retained variable-domain manifest is missing")
    log_bytes, log_sha256 = _stable_regular_file_bytes(log_path)
    solution_bytes, solution_sha256 = _stable_regular_file_bytes(solution_path)
    model_bytes, model_sha256 = _stable_regular_file_bytes(model_path)
    manifest_bytes, manifest_artifact_sha256 = _stable_regular_file_bytes(
        manifest_path
    )
    try:
        log = log_bytes.decode("utf-8")
        solution = solution_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SolverFailure("CBC retained log/solution is not UTF-8") from exc

    if problem.status != pulp.LpStatusOptimal or problem.sol_status != (
        pulp.LpSolutionOptimal
    ):
        raise SolverFailure(
            f"{label} is {pulp.LpStatus[problem.status]}/"
            f"{pulp.LpSolution.get(problem.sol_status, problem.sol_status)}"
        )
    if _CBC_WARNING.search(_cbc_warning_marker_text(log)):
        raise SolverFailure("CBC exact solve emitted a solver warning")
    if _CBC_FORBIDDEN.search(_cbc_forbidden_marker_text(log)):
        raise SolverFailure("CBC exact solve contains a forbidden terminal marker")
    _one_match(
        r"^Result - Optimal solution found\s*$",
        log,
        "exact optimal terminal",
    )
    model_reads = re.findall(
        r"^Coin0008I MODEL read with (\d+) errors\s*$", log, re.MULTILINE
    )
    if model_reads != ["0"]:
        raise SolverFailure("CBC did not prove exactly one error-free model read")
    log_without_model_receipt = re.sub(
        r"^Coin0008I MODEL read with 0 errors\s*$", "", log,
        count=1, flags=re.MULTILINE,
    )
    if re.search(r"\berrors?\b", log_without_model_receipt, re.IGNORECASE):
        raise SolverFailure("CBC exact solve contains an error marker")
    if "Result - Optimal solution found" not in log:
        raise SolverFailure("CBC log lacks one exact optimal terminal record")

    first_line = solution.splitlines()[0] if solution.splitlines() else ""
    solution_match = re.fullmatch(
        rf"Optimal - objective value ({_CBC_NUMBER})", first_line
    )
    if solution_match is None:
        raise SolverFailure("CBC solution header is not exact Optimal")
    if solver.variable_domain_manifest is None:
        raise SolverFailure("CBC solve lacks its variable-domain manifest")
    try:
        retained_manifest_payload = json.loads(manifest_bytes.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SolverFailure("CBC variable-domain manifest is malformed") from exc
    if retained_manifest_payload != _variable_domain_manifest_payload(
        solver.variable_domain_manifest
    ):
        raise SolverFailure("CBC variable-domain manifest artifact changed")
    parsed_model = _parse_exact_mps_bytes(model_bytes)
    _validate_problem_matches_mps(
        problem, parsed_model, solver.variable_domain_manifest
    )
    (
        mps_objective,
        canonical_assignment_sha256,
        integer_decode_affected_count,
        integer_decode_max_residual,
        integer_decode_rows,
        mps_sense,
    ) = _validate_solution_body(
        solution,
        model_path,
        solver.variable_domain_manifest,
        parsed_model=parsed_model,
    )
    solution_objective = _decimal_integer(
        solution_match.group(1), "solution objective"
    )
    log_objective = _decimal_integer(
        _one_match(
            rf"^Objective value:\s+({_CBC_NUMBER})\s*$",
            log,
            "objective",
        ).group(1),
        "log objective",
    )
    if solution_objective != log_objective:
        raise SolverFailure("CBC log and solution objectives disagree")
    if mps_objective != solution_objective:
        raise SolverFailure("CBC retained MPS objective does not reconstruct")
    if mps_sense != problem.sense:
        raise SolverFailure("CBC retained MPS sense differs from registered model")
    reconstructed = _integer_value(problem.objective)
    if reconstructed != solution_objective:
        raise SolverFailure("CBC objective failed PuLP integer reconstruction")

    command = _one_match(
        r"^command line - (.+) \(default strategy 1\)$",
        log,
        "command line with exact default strategy",
    ).group(1)
    tokens = shlex.split(command)
    if not tokens or str(Path(tokens[0]).resolve()) != str(Path(solver.path).resolve()):
        raise SolverFailure("CBC command executable differs from the pinned solver")
    if len(tokens) < 2 or Path(tokens[1]) != model_path:
        raise SolverFailure("CBC command model path differs from its receipt")
    if Decimal(_command_value(tokens, "-sec")) != solver.max_seconds_exact:
        raise SolverFailure("CBC command has the wrong exact time limit")
    for flag in ("-ratio", "-allow"):
        if Decimal(_command_value(tokens, flag)) != 0:
            raise SolverFailure(f"CBC command has nonzero {flag}")
    if _command_value(tokens, "-threads") != "1":
        raise SolverFailure("CBC command is not single-threaded")
    if _command_value(tokens, "-timeMode") != "elapsed":
        raise SolverFailure("CBC command does not use elapsed time")
    for flag in ("-randomSeed", "-randomCbcSeed"):
        if _command_value(tokens, flag) != str(CBC_RANDOM_SEED):
            raise SolverFailure(f"CBC command has the wrong {flag}")
    if Decimal(_command_value(tokens, "-primalTolerance")) != Decimal("1e-9"):
        raise SolverFailure("CBC command has the wrong primal tolerance")
    if Decimal(_command_value(tokens, "-integerTolerance")) != (
        CBC_INTEGER_TOLERANCE
    ):
        raise SolverFailure("CBC command has the wrong integer tolerance")
    if ("-mips" in tokens) != solver.warm_start_exact:
        raise SolverFailure("CBC warm-start command differs from its receipt")
    if solver.warm_start_exact and Path(_command_value(tokens, "-mips")) != (
        solver.artifact_paths.get("mst")
    ):
        raise SolverFailure("CBC MIP-start path differs from its receipt")
    mip_start_path = solver.artifact_paths.get("mst")
    if solver.warm_start_exact and (
        mip_start_path is None
        or not mip_start_path.is_file()
        or mip_start_path.stat().st_size == 0
    ):
        raise SolverFailure("CBC warm start is missing its retained artifact")
    mip_start_sha256: str | None = None
    mip_start_values_sha256: str | None = None
    mip_start_renamed_values_sha256: str | None = None
    mip_start_variable_count = 0
    if solver.warm_start_exact:
        if solver.mip_start_values is None or mip_start_path is None:
            raise SolverFailure("CBC warm start lacks captured complete values")
        mip_start_bytes, mip_start_sha256 = _stable_regular_file_bytes(
            mip_start_path
        )
        try:
            mip_start_text = mip_start_bytes.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise SolverFailure("CBC MIP start is not UTF-8") from exc
        mip_start_values_sha256 = _canonical_json_sha256([
            [name, value] for name, value in solver.mip_start_values
        ])
        mip_start_renamed_values_sha256, mip_start_variable_count = (
            _validate_mip_start_body(
                mip_start_text,
                [value for _, value in solver.mip_start_values],
            )
        )
        mip_start_objective = _validate_assignment_against_mps(
            parsed_model,
            solver.variable_domain_manifest,
            dict(solver.mip_start_values),
        )
        if mip_start_objective != solver.mip_start_reconstructed_objective:
            raise SolverFailure(
                "CBC MIP-start PuLP/MPS objective reconstruction differs"
            )
        if solver.predecessor_assignment_sha256 is None:
            raise SolverFailure("CBC warm start lacks predecessor identity")
    elif (
        solver.predecessor_assignment_sha256 is not None
        or solver.mip_start_reconstructed_objective is not None
    ):
        raise SolverFailure("CBC cold solve unexpectedly binds a predecessor")
    if solver.cuts_exact is False and not (
        tokens.count("-cuts") == 1 and _command_value(tokens, "-cuts") == "off"
    ):
        raise SolverFailure("CBC cuts-off solve differs from its receipt")
    if solver.cuts_exact is None and "-cuts" in tokens:
        raise SolverFailure("CBC default-cuts solve differs from its receipt")
    preprocess_off = "-preprocess" in tokens
    if preprocess_off and not (
        tokens.count("-preprocess") == 1
        and _command_value(tokens, "-preprocess") == "off"
    ):
        raise SolverFailure("CBC preprocessing option is not exact off")
    if preprocess_off != solver.preprocess_off_exact:
        raise SolverFailure("CBC preprocessing command differs from its receipt")
    if any(flag in tokens for flag in ("-maxNodes", "-maxSolutions")):
        raise SolverFailure("CBC command contains an unregistered solve limit")
    if tokens.count("-solve") != 1:
        raise SolverFailure("CBC command does not contain exactly one -solve")
    if _command_value(tokens, "-printingOptions") != "all":
        raise SolverFailure("CBC command does not request full solution printing")
    _command_value(tokens, "-solution")
    allowed_flags = {
        "-max", "-mips", "-sec", "-cuts", "-randomSeed",
        "-randomCbcSeed", "-primalTolerance", "-integerTolerance",
        "-ratio", "-allow",
        "-threads", "-timeMode", "-preprocess", "-solve",
        "-printingOptions", "-solution",
    }
    unexpected_flags = {
        value for value in tokens[1:] if value.startswith("-")
        and value not in allowed_flags
    }
    if unexpected_flags:
        raise SolverFailure(
            f"CBC command contains unregistered options {sorted(unexpected_flags)}"
        )
    if tokens.count("-max") != int(problem.sense == pulp.LpMaximize):
        raise SolverFailure("CBC command objective sense differs from the model")
    if Path(_command_value(tokens, "-solution")) != solution_path:
        raise SolverFailure("CBC command solution path differs from its receipt")
    _validate_exact_command_tokens(
        command,
        cbc_path=solver.path,
        model_path=model_path,
        solution_path=solution_path,
        mip_start_path=mip_start_path if solver.warm_start_exact else None,
        sense=problem.sense,
        max_seconds=solver.max_seconds_exact,
        warm_start=solver.warm_start_exact,
        cuts=solver.cuts_exact,
        preprocess_off=solver.preprocess_off_exact,
    )

    nodes = int(_one_match(
        r"^Enumerated nodes:\s+(\d+)\s*$", log, "node-count"
    ).group(1))
    iterations = int(_one_match(
        r"^Total iterations:\s+(\d+)\s*$", log, "iteration-count"
    ).group(1))
    cpu = Decimal(_one_match(
        rf"^Time \(CPU seconds\):\s+({_CBC_NUMBER})\s*$", log, "CPU-time"
    ).group(1))
    wall = Decimal(_one_match(
        rf"^Time \(Wallclock seconds\):\s+({_CBC_NUMBER})\s*$",
        log,
        "wall-time",
    ).group(1))
    if not cpu.is_finite() or not wall.is_finite() or cpu < 0 or wall < 0:
        raise SolverFailure("CBC solve time is invalid")
    if wall >= solver.max_seconds_exact:
        raise SolverFailure("CBC solve reached its registered wall-time limit")
    version = _one_match(
        r"^Version:\s+([^\s]+)\s*$", log, "version"
    ).group(1)
    if version != PINNED_CBC_VERSION:
        raise SolverFailure(
            f"residual proof requires CBC {PINNED_CBC_VERSION}"
        )
    evidence = CbcSolveEvidence(
        solve_label=label,
        evidence_directory=str(solver.evidence_directory),
        log_path=str(log_path),
        solution_path=str(solution_path),
        model_path=str(model_path),
        variable_domain_manifest_path=str(manifest_path),
        mip_start_path=(str(mip_start_path) if solver.warm_start_exact else None),
        log_sha256=log_sha256,
        solution_sha256=solution_sha256,
        model_sha256=model_sha256,
        mip_start_sha256=mip_start_sha256,
        mip_start_values_sha256=mip_start_values_sha256,
        mip_start_renamed_values_sha256=mip_start_renamed_values_sha256,
        mip_start_variable_count=mip_start_variable_count,
        predecessor_assignment_sha256=(
            solver.predecessor_assignment_sha256
        ),
        mip_start_reconstructed_objective=(
            solver.mip_start_reconstructed_objective
        ),
        mip_start_values=solver.mip_start_values,
        cbc_path=str(Path(solver.path).resolve()),
        cbc_sha256=_cbc_binary_sha256(solver.path),
        cbc_version=version,
        pulp_version=pulp.__version__,
        command_line=command,
        pulp_status=int(problem.status),
        pulp_solution_status=int(problem.sol_status),
        objective=solution_objective,
        problem_sense=int(problem.sense),
        enumerated_nodes=nodes,
        total_iterations=iterations,
        cpu_seconds=cpu,
        wall_seconds=wall,
        max_seconds=solver.max_seconds_exact,
        warm_start=solver.warm_start_exact,
        cuts=solver.cuts_exact,
        preprocess_off=solver.preprocess_off_exact,
        random_seed=CBC_RANDOM_SEED,
        random_cbc_seed=CBC_RANDOM_SEED,
        threads=1,
        time_mode="elapsed",
        relative_gap=Decimal(0),
        absolute_gap=Decimal(0),
        primal_tolerance=Decimal("1e-9"),
        integer_tolerance=CBC_INTEGER_TOLERANCE,
        variable_domain_manifest_sha256=manifest_artifact_sha256,
        canonical_assignment_sha256=canonical_assignment_sha256,
        integer_decode_affected_count=integer_decode_affected_count,
        integer_decode_max_residual=integer_decode_max_residual,
        variable_domain_manifest=solver.variable_domain_manifest,
        integer_decode_rows=integer_decode_rows,
    )
    proven_assignment = tuple(
        (manifest_row[1], decode_row[2])
        for manifest_row, decode_row in zip(
            solver.variable_domain_manifest,
            integer_decode_rows,
            strict=True,
        )
    )
    setattr(problem, "_residual_proven_assignment", proven_assignment)
    setattr(
        problem,
        "_residual_proven_assignment_sha256",
        canonical_assignment_sha256,
    )
    setattr(problem, "_residual_proven_evidence", evidence)
    solver.evidence = evidence
    return evidence


def validate_cbc_solve_evidence(evidence: CbcSolveEvidence) -> None:
    """Re-hash and structurally revalidate one retained CBC receipt.

    The original PuLP problem is required for objective/constraint
    reconstruction and is audited at solve time.  This second boundary makes
    later source preparation fail closed if any retained artifact, binary, or
    parsed receipt field has changed since that solve.
    """
    if not isinstance(evidence, CbcSolveEvidence):
        raise SolverFailure("CBC retained evidence receipt has the wrong type")
    for value, label in (
        (evidence.objective, "objective"),
        (evidence.max_seconds, "time limit"),
        (evidence.enumerated_nodes, "node count"),
        (evidence.total_iterations, "iteration count"),
        (evidence.problem_sense, "problem sense"),
        (evidence.integer_decode_affected_count, "decode affected count"),
        (evidence.random_seed, "random seed"),
        (evidence.random_cbc_seed, "CBC random seed"),
        (evidence.threads, "thread count"),
    ):
        if isinstance(value, bool) or not isinstance(value, int):
            raise SolverFailure(f"CBC retained {label} is not an integer")
    directory = _resolve_real_directory(
        Path(evidence.evidence_directory), "CBC retained evidence directory"
    )
    required = (
        (Path(evidence.log_path), evidence.log_sha256, "log"),
        (Path(evidence.solution_path), evidence.solution_sha256, "solution"),
        (Path(evidence.model_path), evidence.model_sha256, "model"),
        (
            Path(evidence.variable_domain_manifest_path),
            evidence.variable_domain_manifest_sha256,
            "variable-domain manifest",
        ),
    )
    if evidence.warm_start:
        if (
            evidence.mip_start_path is None
            or evidence.mip_start_sha256 is None
            or evidence.mip_start_values_sha256 is None
            or evidence.mip_start_renamed_values_sha256 is None
            or evidence.mip_start_variable_count <= 0
            or evidence.mip_start_values is None
            or not isinstance(evidence.predecessor_assignment_sha256, str)
            or len(evidence.predecessor_assignment_sha256) != 64
            or isinstance(evidence.mip_start_reconstructed_objective, bool)
            or not isinstance(evidence.mip_start_reconstructed_objective, int)
        ):
            raise SolverFailure("CBC warm evidence lacks its MIP start")
        required = (*required, (
            Path(evidence.mip_start_path), evidence.mip_start_sha256, "MIP start",
        ))
    elif (
        evidence.mip_start_path is not None
        or evidence.mip_start_sha256 is not None
        or evidence.mip_start_values_sha256 is not None
        or evidence.mip_start_renamed_values_sha256 is not None
        or evidence.mip_start_variable_count != 0
        or evidence.mip_start_values is not None
        or evidence.predecessor_assignment_sha256 is not None
        or evidence.mip_start_reconstructed_objective is not None
    ):
        raise SolverFailure("CBC cold evidence unexpectedly receipts a MIP start")
    seen_paths: set[Path] = set()
    retained_bytes: dict[str, bytes] = {}
    for path, expected_sha, label in required:
        absolute = path if path.is_absolute() else Path.cwd() / path
        resolved = path.resolve()
        if (
            ".." in absolute.parts
            or path.is_symlink()
            or absolute.parent != directory
            or resolved.parent != directory
            or resolved in seen_paths
        ):
            raise SolverFailure(f"CBC retained {label} path is reused or misplaced")
        seen_paths.add(resolved)
        payload, observed_sha = _stable_regular_file_bytes(path)
        if observed_sha != expected_sha:
            raise SolverFailure(f"CBC retained {label} hash changed")
        retained_bytes[label] = payload
    if evidence.pulp_status != pulp.LpStatusOptimal or (
        evidence.pulp_solution_status != pulp.LpSolutionOptimal
    ):
        raise SolverFailure("CBC retained receipt is not exact Optimal")
    manifest = tuple(evidence.variable_domain_manifest)
    if (
        not manifest
        or _variable_domain_manifest_sha256(manifest)
        != evidence.variable_domain_manifest_sha256
        or len({row[0] for row in manifest}) != len(manifest)
        or len({row[1] for row in manifest}) != len(manifest)
    ):
        raise SolverFailure("CBC retained variable-domain manifest changed")
    try:
        retained_manifest = json.loads(
            retained_bytes["variable-domain manifest"].decode("utf-8")
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SolverFailure(
            "CBC retained variable-domain manifest is malformed"
        ) from exc
    if retained_manifest != _variable_domain_manifest_payload(manifest):
        raise SolverFailure("CBC retained variable-domain manifest changed")
    decode_rows = tuple(evidence.integer_decode_rows)
    if (
        len(decode_rows) != len(manifest)
        or any(
            not isinstance(row, tuple) or len(row) != 4
            for row in decode_rows
        )
    ):
        raise SolverFailure("CBC retained integer-decode receipt changed")
    try:
        decoded = tuple(
            _decode_integer_token(row[1], f"retained assignment token {row[0]}")
            for row in decode_rows
        )
        decode_residuals = tuple(Decimal(row[3]) for row in decode_rows)
    except (InvalidOperation, TypeError) as exc:
        raise SolverFailure("CBC retained decode residual is nonnumeric") from exc
    if (
        tuple(row[0] for row in decode_rows)
        != tuple(row[0] for row in manifest)
        or any(
            not value.is_finite()
            or abs(value) > CBC_INTEGER_DECODE_EPS
            for value in decode_residuals
        )
        or any(
            isinstance(row[2], bool)
            or not isinstance(row[2], int)
            or canonical != row[2]
            or signed_residual != residual
            for row, (canonical, signed_residual), residual in zip(
                decode_rows,
                decoded,
                decode_residuals,
                strict=True,
            )
        )
        or sum(value != 0 for value in decode_residuals)
        != evidence.integer_decode_affected_count
        or max((abs(value) for value in decode_residuals), default=Decimal(0))
        != evidence.integer_decode_max_residual
    ):
        raise SolverFailure("CBC retained integer-decode residual changed")
    if evidence.max_seconds <= 0 or evidence.wall_seconds >= evidence.max_seconds:
        raise SolverFailure("CBC retained receipt reached its time limit")
    if evidence.cpu_seconds < 0 or evidence.wall_seconds < 0 or not (
        evidence.cpu_seconds.is_finite() and evidence.wall_seconds.is_finite()
    ):
        raise SolverFailure("CBC retained receipt has invalid solve time")
    cbc_path = Path(evidence.cbc_path)
    if not cbc_path.is_file() or _sha256_file(cbc_path.resolve()) != (
        evidence.cbc_sha256
    ):
        raise SolverFailure("CBC retained binary identity changed")
    if (
        pulp.__version__ != PINNED_PULP_VERSION
        or evidence.pulp_version != PINNED_PULP_VERSION
        or evidence.cbc_version != PINNED_CBC_VERSION
    ):
        raise SolverFailure("CBC retained PuLP version differs from runtime")
    if (
        evidence.random_seed != CBC_RANDOM_SEED
        or evidence.random_cbc_seed != CBC_RANDOM_SEED
        or evidence.threads != 1
        or evidence.time_mode != "elapsed"
        or evidence.relative_gap != 0
        or evidence.absolute_gap != 0
        or evidence.primal_tolerance != Decimal("1e-9")
        or evidence.integer_tolerance != CBC_INTEGER_TOLERANCE
    ):
        raise SolverFailure("CBC retained exact solver-law receipt changed")

    try:
        log = retained_bytes["log"].decode("utf-8")
        solution = retained_bytes["solution"].decode("utf-8")
    except UnicodeDecodeError as exc:
        raise SolverFailure("CBC retained log/solution is not UTF-8") from exc
    if _CBC_WARNING.search(_cbc_warning_marker_text(log)) or _CBC_FORBIDDEN.search(
        _cbc_forbidden_marker_text(log)
    ):
        raise SolverFailure("CBC retained exact evidence has a forbidden marker")
    _one_match(
        r"^Result - Optimal solution found\s*$", log,
        "retained exact optimal terminal",
    )
    if re.findall(
        r"^Coin0008I MODEL read with (\d+) errors\s*$", log, re.MULTILINE
    ) != ["0"]:
        raise SolverFailure("CBC retained model-read receipt is not exact zero")
    without_model_receipt = re.sub(
        r"^Coin0008I MODEL read with 0 errors\s*$", "", log,
        count=1, flags=re.MULTILINE,
    )
    if re.search(r"\berrors?\b", without_model_receipt, re.IGNORECASE):
        raise SolverFailure("CBC retained evidence contains an error marker")
    first_line = solution.splitlines()[0] if solution.splitlines() else ""
    solution_match = re.fullmatch(
        rf"Optimal - objective value ({_CBC_NUMBER})", first_line
    )
    if solution_match is None or _decimal_integer(
        solution_match.group(1), "retained solution objective"
    ) != evidence.objective:
        raise SolverFailure("CBC retained solution objective changed")
    parsed_model = _parse_exact_mps_bytes(retained_bytes["model"])
    (
        mps_objective,
        canonical_assignment_sha256,
        affected_count,
        maximum_residual,
        reparsed_decode_rows,
        mps_sense,
    ) = _validate_solution_body(
        solution,
        Path(evidence.model_path),
        manifest,
        parsed_model=parsed_model,
    )
    if (
        mps_objective != evidence.objective
        or canonical_assignment_sha256 != evidence.canonical_assignment_sha256
        or affected_count != evidence.integer_decode_affected_count
        or maximum_residual != evidence.integer_decode_max_residual
        or reparsed_decode_rows != decode_rows
        or mps_sense != evidence.problem_sense
    ):
        raise SolverFailure("CBC retained MPS objective changed")
    log_objective = _decimal_integer(_one_match(
        rf"^Objective value:\s+({_CBC_NUMBER})\s*$", log,
        "retained objective",
    ).group(1), "retained log objective")
    if log_objective != evidence.objective:
        raise SolverFailure("CBC retained log objective changed")
    if evidence.warm_start:
        assert evidence.mip_start_path is not None
        assert evidence.mip_start_values is not None
        captured_values = tuple(evidence.mip_start_values)
        if (
            len(captured_values) != evidence.mip_start_variable_count
            or any(
                not isinstance(row, tuple) or len(row) != 2
                for row in captured_values
            )
        ):
            raise SolverFailure("CBC retained MIP-start receipt is malformed")
        captured_names: list[str] = []
        captured_integers: list[int] = []
        for name, value in captured_values:
            if not isinstance(name, str) or not name or isinstance(value, bool) or (
                not isinstance(value, int)
            ):
                raise SolverFailure("CBC retained MIP-start receipt is malformed")
            captured_names.append(name)
            captured_integers.append(value)
        if tuple(captured_names) != tuple(row[1] for row in manifest):
            raise SolverFailure("CBC retained MIP-start names differ from manifest")
        if _canonical_json_sha256([
            [name, value] for name, value in captured_values
        ]) != evidence.mip_start_values_sha256:
            raise SolverFailure("CBC retained original MIP-start values changed")
        renamed_sha, variable_count = _validate_mip_start_body(
            retained_bytes["MIP start"].decode("utf-8"),
            captured_integers,
        )
        if (
            renamed_sha != evidence.mip_start_renamed_values_sha256
            or variable_count != evidence.mip_start_variable_count
        ):
            raise SolverFailure("CBC retained MIP-start values changed")
        mip_objective = _validate_assignment_against_mps(
            parsed_model,
            manifest,
            dict(captured_values),
        )
        if mip_objective != evidence.mip_start_reconstructed_objective:
            raise SolverFailure("CBC retained MIP-start objective changed")
    command = _one_match(
        r"^command line - (.+) \(default strategy 1\)$",
        log,
        "retained command line with exact default strategy",
    ).group(1)
    if command != evidence.command_line:
        raise SolverFailure("CBC retained command line changed")
    _validate_retained_command(evidence, command)
    version = _one_match(r"^Version:\s+([^\s]+)\s*$", log, "retained version").group(1)
    if version != evidence.cbc_version or version != PINNED_CBC_VERSION:
        raise SolverFailure("CBC retained version changed")
    nodes = int(_one_match(
        r"^Enumerated nodes:\s+(\d+)\s*$", log, "retained node-count"
    ).group(1))
    iterations = int(_one_match(
        r"^Total iterations:\s+(\d+)\s*$", log, "retained iteration-count"
    ).group(1))
    cpu = Decimal(_one_match(
        rf"^Time \(CPU seconds\):\s+({_CBC_NUMBER})\s*$", log,
        "retained CPU-time",
    ).group(1))
    wall = Decimal(_one_match(
        rf"^Time \(Wallclock seconds\):\s+({_CBC_NUMBER})\s*$", log,
        "retained wall-time",
    ).group(1))
    if (nodes, iterations, cpu, wall) != (
        evidence.enumerated_nodes,
        evidence.total_iterations,
        evidence.cpu_seconds,
        evidence.wall_seconds,
    ):
        raise SolverFailure("CBC retained parsed metrics changed")


def _bound_model_sha256(
    players: tuple[PlayerSpec, ...], coefficients: np.ndarray,
    world_index: int, sense: int, direction: str, stage: str,
    quotient_optimum: int,
) -> tuple[str, int, str]:
    model = build_legal_lineup_model(
        players, name=f"residual_bound_{world_index:05d}_{direction}"
    )
    quotient, remainder, offset = _bound_score_objective(
        model,
        coefficients,
        name=f"bound_{world_index:05d}_{direction}",
    )
    model.problem.sense = sense
    if stage == "quotient":
        model.problem.setObjective(quotient)
    elif stage == "remainder":
        model.problem += quotient == quotient_optimum, (
            f"freeze_{direction}_quotient"
        )
        model.problem.setObjective(remainder)
    else:  # pragma: no cover - internal caller is closed
        raise AssertionError("unknown bound solve stage")
    model_sha256, manifest_sha256 = _problem_mps_receipt(model.problem)
    return model_sha256, offset, manifest_sha256


def _validate_bound_receipts(
    players: tuple[PlayerSpec, ...],
    player_scores_micro: np.ndarray,
    all_worlds: tuple[WorldId, ...],
    bounds: tuple[WorldLegalBound, ...],
) -> None:
    row = {player.player_id: index for index, player in enumerate(players)}
    global_index = {world: index for index, world in enumerate(all_worlds)}
    all_evidence = tuple(
        evidence for bound in bounds
        for evidence in (*bound.upper_evidence, *bound.lower_evidence)
    )
    evidence_paths = [
        str(Path(path).resolve()) for evidence in all_evidence for path in (
            evidence.evidence_directory,
            evidence.log_path,
            evidence.solution_path,
            evidence.model_path,
            evidence.variable_domain_manifest_path,
            evidence.mip_start_path,
        ) if path is not None
    ]
    if len(evidence_paths) != len(set(evidence_paths)):
        raise ResidualWorldError("legal-bound solve evidence is reused")
    for local_index, bound in enumerate(bounds):
        column = global_index.get(bound.world_id)
        if column is None:
            raise ResidualWorldError("legal-bound world is outside source matrix")
        audit_legal_identity(players, bound.lower_roster)
        audit_legal_identity(players, bound.upper_roster)
        lower_rows = [row[player_id] for player_id in bound.lower_roster]
        upper_rows = [row[player_id] for player_id in bound.upper_roster]
        if int(player_scores_micro[lower_rows, column].sum(dtype=np.int64)) != (
            bound.lower_micro
        ):
            raise ResidualWorldError("legal lower-bound witness does not reconstruct")
        if int(player_scores_micro[upper_rows, column].sum(dtype=np.int64)) != (
            bound.upper_micro
        ):
            raise ResidualWorldError("legal upper-bound witness does not reconstruct")
        for direction, sense, total, receipts in (
            ("maximum", pulp.LpMaximize, bound.upper_micro, bound.upper_evidence),
            ("minimum", pulp.LpMinimize, bound.lower_micro, bound.lower_evidence),
        ):
            quotient_receipt, remainder_receipt = receipts
            for evidence in receipts:
                validate_cbc_solve_evidence(evidence)
            expected_labels = (
                f"world {local_index} legal {direction} quotient",
                f"world {local_index} legal {direction} remainder",
            )
            if tuple(evidence.solve_label for evidence in receipts) != expected_labels:
                raise ResidualWorldError("legal-bound evidence order changed")
            expected_laws = ((False, False, False), (False, False, True))
            if any(
                evidence.max_seconds != BOUND_TIME_LIMIT_SECONDS
                or evidence.warm_start != warm
                or evidence.cuts is not cuts
                or evidence.preprocess_off != preprocess
                for evidence, (warm, cuts, preprocess) in zip(
                    receipts, expected_laws, strict=True
                )
            ):
                raise ResidualWorldError("legal-bound solver contract changed")
            _, offset, _ = _bound_model_sha256(
                players,
                player_scores_micro[:, column],
                local_index,
                sense,
                direction,
                "quotient",
                0,
            )
            shifted = total - offset
            quotient, remainder = divmod(shifted, BOUND_OBJECTIVE_BASE)
            if shifted < 0 or (
                quotient_receipt.objective,
                remainder_receipt.objective,
            ) != (quotient, remainder):
                raise ResidualWorldError("legal-bound digit objectives disagree")
            quotient_sha, quotient_offset, quotient_manifest_sha = (
                _bound_model_sha256(
                players,
                player_scores_micro[:, column],
                local_index,
                sense,
                direction,
                "quotient",
                quotient,
                )
            )
            remainder_sha, remainder_offset, remainder_manifest_sha = (
                _bound_model_sha256(
                players,
                player_scores_micro[:, column],
                local_index,
                sense,
                direction,
                "remainder",
                quotient,
                )
            )
            if quotient_offset != remainder_offset or quotient_offset != offset:
                raise AssertionError("bound objective offsets differ by stage")
            if (
                quotient_receipt.model_sha256 != quotient_sha
                or remainder_receipt.model_sha256 != remainder_sha
                or quotient_receipt.variable_domain_manifest_sha256
                != quotient_manifest_sha
                or remainder_receipt.variable_domain_manifest_sha256
                != remainder_manifest_sha
            ):
                raise ResidualWorldError(
                    "legal-bound solver model differs from source"
                )


def _solve(
    problem: pulp.LpProblem,
    solver: pulp.LpSolver,
    label: str,
) -> CbcSolveEvidence:
    if not isinstance(solver, _RetainedCbcSolver):
        raise SolverFailure("exact solve lacks retained CBC evidence coordination")
    if solver.mip_start_values is not None:
        raise SolverFailure("CBC MIP-start value receipt was reused")
    if solver.variable_domain_manifest is not None:
        raise SolverFailure("CBC variable-domain manifest receipt was reused")
    solver.variable_domain_manifest = _variable_domain_manifest(problem)
    manifest_path = solver.evidence_directory / "variable-domain-manifest.json"
    if manifest_path.exists():
        raise SolverFailure("CBC variable-domain manifest path was reused")
    manifest_path.write_text(
        json.dumps(
            _variable_domain_manifest_payload(
                solver.variable_domain_manifest
            ),
            ensure_ascii=False,
            separators=(",", ":"),
        ),
        encoding="utf-8",
    )
    solver.variable_domain_manifest_path = manifest_path
    if solver.warm_start_exact:
        predecessor_values, predecessor_evidence = (
            _validated_predecessor_receipt(problem)
        )
        predecessor_sha256 = predecessor_evidence.canonical_assignment_sha256
        predecessor = dict(predecessor_values)
        if len(predecessor) != len(tuple(predecessor_values)):
            raise SolverFailure("CBC predecessor assignment repeats a variable")
        captured: list[tuple[str, int]] = []
        for variable in problem.variables():
            raw = variable.value()
            if raw is None or not math.isfinite(float(raw)):
                raise SolverFailure("CBC warm start has an unset/nonfinite value")
            integer, _ = _decode_integer_token(
                repr(float(raw)), f"warm-start value {variable.name}"
            )
            if variable.name in predecessor and predecessor[variable.name] != integer:
                raise SolverFailure(
                    "CBC warm start differs from its predecessor assignment"
                )
            # PuLP otherwise writes tiny floating residue (for example
            # ``-4e-15``) from the preceding exact solve into the MST.  The
            # registered warm-start law is the independently reconstructed
            # complete integer incumbent, so normalize every stored value
            # before PuLP serializes the retained start artifact.
            variable.setInitialValue(integer, check=True)
            captured.append((variable.name, integer))
        if not captured:
            raise SolverFailure("CBC warm start has no model variables")
        if not set(predecessor) <= {name for name, _ in captured}:
            raise SolverFailure("CBC warm start dropped a predecessor variable")
        solver.mip_start_values = tuple(captured)
        solver.predecessor_assignment_sha256 = predecessor_sha256
        solver.mip_start_reconstructed_objective = (
            _validate_assignment_against_problem(problem, dict(captured))
        )
    problem.solve(solver)
    return _parse_cbc_evidence(problem, solver, label)


def _integer_value(expression: pulp.LpAffineExpression | pulp.LpVariable) -> int:
    raw = pulp.value(expression)
    if raw is None:
        raw = float(expression.constant) if isinstance(
            expression, pulp.LpAffineExpression
        ) else 0.0
    value = int(round(float(raw)))
    if abs(float(raw) - value) > 1e-5:
        raise SolverFailure("exact integer objective reconstructed as fractional")
    return value


def _solved_roster(model: LegalLineupModel) -> tuple[str, ...]:
    identity = canonical_identity([
        player_id for player_id, variable in model.decision.items()
        if variable.value() is not None and variable.value() > 0.5
    ])
    return audit_legal_identity(model.players, identity)


def solve_legal_bounds(
    players: Sequence[PlayerSpec | Mapping[str, object]],
    player_scores_micro: np.ndarray,
    *,
    solver_factory: SolverFactory = _default_solver_factory,
) -> LegalBounds:
    """Solve exact legal ``L_w`` and ``H_w`` for every supplied world."""
    rows = _players(players)
    scores = _micro_matrix(player_scores_micro, rows=len(rows))
    lower: list[int] = []
    upper: list[int] = []
    lower_rosters: list[tuple[str, ...]] = []
    upper_rosters: list[tuple[str, ...]] = []
    evidence: list[CbcSolveEvidence] = []
    row_index = {player.player_id: index for index, player in enumerate(rows)}
    for world in range(scores.shape[1]):
        def solve_bound(
            sense: int, direction: str
        ) -> tuple[int, tuple[str, ...], tuple[CbcSolveEvidence, ...]]:
            model = build_legal_lineup_model(
                rows, name=f"residual_bound_{world:05d}_{direction}"
            )
            quotient, remainder, offset = _bound_score_objective(
                model,
                scores[:, world],
                name=f"bound_{world:05d}_{direction}",
            )
            model.problem.sense = sense
            model.problem.setObjective(quotient)
            quotient_evidence = _solve(
                model.problem,
                solver_factory(BOUND_TIME_LIMIT_SECONDS, False),
                f"world {world} legal {direction} quotient",
            )
            quotient_optimum = _integer_value(quotient)
            if quotient_evidence.objective != quotient_optimum:
                raise SolverFailure(
                    f"legal {direction} quotient evidence disagrees"
                )
            model.problem += quotient == quotient_optimum, (
                f"freeze_{direction}_quotient"
            )
            model.problem.setObjective(remainder)
            remainder_solver = solver_factory(BOUND_TIME_LIMIT_SECONDS, False)
            if not isinstance(remainder_solver, _RetainedCbcSolver):
                raise SolverFailure(
                    "legal bound remainder lacks retained CBC coordination"
                )
            if remainder_solver.cuts_exact is None:
                remainder_solver.optionsDict["cuts"] = False
                remainder_solver.cuts_exact = False
            elif remainder_solver.cuts_exact is not False:
                raise SolverFailure("legal bound remainder cuts contract changed")
            remainder_solver.disable_preprocess()
            remainder_evidence = _solve(
                model.problem,
                remainder_solver,
                f"world {world} legal {direction} remainder",
            )
            remainder_optimum = _integer_value(remainder)
            if remainder_evidence.objective != remainder_optimum:
                raise SolverFailure(
                    f"legal {direction} remainder evidence disagrees"
                )
            total = (
                quotient_optimum * BOUND_OBJECTIVE_BASE
                + remainder_optimum
                + offset
            )
            return total, _solved_roster(model), (
                quotient_evidence, remainder_evidence
            )

        maximum, maximum_roster, maximum_evidence = solve_bound(
            pulp.LpMaximize, "maximum"
        )
        maximum_rows = [row_index[player_id] for player_id in maximum_roster]
        if int(scores[maximum_rows, world].sum(dtype=np.int64)) != maximum:
            raise SolverFailure("legal maximum witness failed reconstruction")
        evidence.extend(maximum_evidence)
        minimum, minimum_roster, minimum_evidence = solve_bound(
            pulp.LpMinimize, "minimum"
        )
        minimum_rows = [row_index[player_id] for player_id in minimum_roster]
        if int(scores[minimum_rows, world].sum(dtype=np.int64)) != minimum:
            raise SolverFailure("legal minimum witness failed reconstruction")
        evidence.extend(minimum_evidence)
        if minimum > maximum:
            raise SolverFailure("legal world minimum exceeds maximum")
        lower.append(minimum)
        upper.append(maximum)
        lower_rosters.append(minimum_roster)
        upper_rosters.append(maximum_roster)
    return LegalBounds(
        tuple(lower),
        tuple(upper),
        tuple(lower_rosters),
        tuple(upper_rosters),
        tuple(evidence),
    )


def _freeze_integer_objective(
    problem: pulp.LpProblem,
    expression: pulp.LpAffineExpression,
    *,
    sense: int,
    name: str,
    solver_factory: SolverFactory,
    warm_start: bool,
    cuts_off: bool = False,
    preprocess_off: bool = False,
) -> tuple[int, CbcSolveEvidence]:
    problem.sense = sense
    problem.setObjective(expression)
    solver = solver_factory(PRICING_TIME_LIMIT_SECONDS, warm_start)
    if not isinstance(solver, _RetainedCbcSolver):
        raise SolverFailure("pricing tier lacks retained CBC coordination")
    if cuts_off and solver.cuts_exact is None:
        solver.optionsDict["cuts"] = False
        solver.cuts_exact = False
    if cuts_off and solver.cuts_exact is not False:
        raise SolverFailure("pricing tier cuts contract changed")
    if preprocess_off:
        solver.disable_preprocess()
    evidence = _solve(
        problem,
        solver,
        f"pricing tier {name}",
    )
    optimum = _integer_value(expression)
    if evidence.objective != optimum:
        raise SolverFailure(f"pricing tier {name} objective evidence disagrees")
    problem += expression == optimum, f"freeze_{name}"
    return optimum, evidence


def _add_exact_positive_part(
    problem: pulp.LpProblem,
    score: pulp.LpAffineExpression | pulp.LpVariable,
    lower: int,
    upper: int,
    maximum: int,
    *,
    name: str,
) -> tuple[pulp.LpAffineExpression | pulp.LpVariable, pulp.LpVariable | None]:
    """Add the frozen exact graph for ``max(0, score-maximum)``."""
    lo = _strict_integer(lower, "positive-part lower bound")
    hi = _strict_integer(upper, "positive-part upper bound")
    current = _strict_integer(maximum, "positive-part reference maximum")
    if lo > hi:
        raise ResidualWorldError("positive-part lower bound exceeds upper bound")
    if hi <= current:
        return pulp.lpSum([]), None
    if lo > current:
        return score - current, None

    positive = pulp.LpVariable(f"{name}_positive", cat="Binary")
    residual = pulp.LpVariable(
        f"{name}_residual",
        lowBound=0,
        upBound=hi - current,
        cat="Integer",
    )
    delta = score - current
    problem += delta <= (hi - current) * positive, f"{name}_positive_upper"
    problem += delta >= 1 - (current - lo + 1) * (1 - positive), (
        f"{name}_positive_lower"
    )
    problem += residual >= delta, f"{name}_residual_lower_score"
    problem += residual >= 0, f"{name}_residual_lower_zero"
    problem += residual <= (hi - current) * positive, (
        f"{name}_residual_upper_positive"
    )
    problem += residual <= delta + (current - lo) * (1 - positive), (
        f"{name}_residual_upper_score"
    )
    return residual, positive


def _add_exact_product_positive_part(
    model: LegalLineupModel,
    score: pulp.LpAffineExpression | pulp.LpVariable,
    score_number: _BinaryNumber,
    score_offset: int,
    coefficients: np.ndarray,
    lower: int,
    upper: int,
    maximum: int,
    *,
    name: str,
    initial_roster: frozenset[str] | None = None,
) -> tuple[pulp.LpAffineExpression | pulp.LpVariable, pulp.LpVariable | None]:
    """Exact positive part via ``z_p=x_p*b`` and a radix-linked d.

    This is algebraically the same graph as :func:`_add_exact_positive_part`,
    but its residual equality contains no large big-M row.  It is used by the
    CBC pricing path after randomized tests exposed invalid numerical cuts in
    the compact graph; the compact formulation remains directly unit-tested.
    """
    lo = _strict_integer(lower, "positive-part lower bound")
    hi = _strict_integer(upper, "positive-part upper bound")
    current = _strict_integer(maximum, "positive-part reference maximum")
    if hi <= current:
        return pulp.lpSum([]), None
    if lo > current:
        return score - current, None

    initial_positive: int | None = None
    initial_score: int | None = None
    if initial_roster is not None:
        initial_score = sum(
            int(coefficients[index])
            for index, player in enumerate(model.players)
            if player.player_id in initial_roster
        )
        if not lo <= initial_score <= hi:
            raise SolverFailure("residual MIP start score is outside exact L/H")
        initial_positive = int(initial_score > current)
    positive = _binary_ge_indicator(
        model.problem,
        score_number,
        current + 1 - score_offset,
        name=f"{name}_positive",
        initial_number=(
            None if initial_score is None else initial_score - score_offset
        ),
    )
    if initial_positive is not None and int(round(float(
        positive.value()
    ))) != initial_positive:
        raise SolverFailure("positive-part comparator MIP start disagrees")

    products: list[pulp.LpVariable] = []
    for index, player in enumerate(model.players):
        product = pulp.LpVariable(
            f"{name}_selected_positive_{index:04d}",
            lowBound=0,
            upBound=1,
            cat="Binary",
        )
        if initial_positive is not None:
            product.setInitialValue(int(
                initial_positive and player.player_id in initial_roster
            ))
        selected = model.decision[player.player_id]
        model.problem += product <= selected, f"{name}_product_x_{index:04d}"
        model.problem += product <= positive, f"{name}_product_b_{index:04d}"
        model.problem += product >= selected + positive - 1, (
            f"{name}_product_lower_{index:04d}"
        )
        products.append(product)
    residual = pulp.lpSum(
        product * int(coefficients[index])
        for index, product in enumerate(products)
    ) - current * positive
    return residual, positive


def solve_residual_pricing(
    players: Sequence[PlayerSpec | Mapping[str, object]],
    player_scores_micro: np.ndarray,
    book_maxima_micro: Sequence[int] | np.ndarray,
    lower_bounds_micro: Sequence[int] | np.ndarray,
    upper_bounds_micro: Sequence[int] | np.ndarray,
    *,
    control_rosters: Sequence[Sequence[object]] = (),
    previous_columns: Sequence[Sequence[object]] = (),
    thresholds_micro: Sequence[int] = TAIL_THRESHOLDS_MICRO,
    solver_factory: SolverFactory = _default_solver_factory,
) -> PricingResult:
    """Price one exact portfolio complement on the supplied active worlds."""
    rows = _players(players)
    scores = _micro_matrix(player_scores_micro, rows=len(rows))
    n_worlds = scores.shape[1]
    book_max = _micro_vector(book_maxima_micro, n_worlds, "book maxima")
    lower = _micro_vector(lower_bounds_micro, n_worlds, "legal lower bounds")
    upper = _micro_vector(upper_bounds_micro, n_worlds, "legal upper bounds")
    if np.any(lower > upper):
        raise ResidualWorldError("legal lower bound exceeds upper bound")
    if np.any(book_max < lower) or np.any(book_max > upper):
        raise ResidualWorldError("book maximum is outside its exact legal bounds")
    thresholds = _threshold_tuple(thresholds_micro)

    normalized_forbidden = complete_no_good_rosters(
        control_rosters, previous_columns
    )
    pricing_input_digest = _pricing_input_sha256(
        rows,
        scores,
        book_max,
        lower,
        upper,
        thresholds,
        normalized_forbidden,
    )
    model = build_legal_lineup_model(
        rows,
        name="residual_world_pricing",
        forbidden_rosters=normalized_forbidden,
    )

    binary_scores = [
        _binary_score_number(
            model,
            scores[:, world],
            name=f"pricing_score_{world:04d}",
        )
        for world in range(n_worlds)
    ]
    indicator_variables: list[list[pulp.LpVariable | None]] = [
        [None] * n_worlds for _ in thresholds
    ]
    tier_expressions: list[pulp.LpAffineExpression] = []
    tier_variable_counts: list[int] = []
    for tier_index, threshold in enumerate(thresholds):
        variables: list[pulp.LpVariable] = []
        for world in range(n_worlds):
            if not (int(book_max[world]) < threshold <= int(upper[world])):
                continue
            score_number, score_offset = binary_scores[world]
            variable = _binary_ge_indicator(
                model.problem,
                score_number,
                threshold - score_offset,
                name=f"tail_{tier_index:02d}_{world:04d}",
            )
            indicator_variables[tier_index][world] = variable
            variables.append(variable)
        tier_expressions.append(pulp.lpSum(variables))
        tier_variable_counts.append(len(variables))

    row_index = {player.player_id: index for index, player in enumerate(rows)}

    def current_scores() -> np.ndarray:
        identity = _solved_roster(model)
        chosen = np.asarray([row_index[player_id] for player_id in identity], dtype=int)
        return scores[chosen].sum(axis=0, dtype=np.int64)

    optima: list[int] = []
    solve_evidence: list[CbcSolveEvidence] = []
    have_proven_tail_incumbent = False
    for tier_index, expression in enumerate(tier_expressions):
        if tier_variable_counts[tier_index] == 0:
            # The tier is the structural constant zero: no active world has
            # m<t<=H.  Do not manufacture a warning-emitting trivial CBC run.
            optima.append(0)
            continue
        optimum, evidence = _freeze_integer_objective(
            model.problem,
            expression,
            sense=pulp.LpMaximize,
            name=f"tail_{tier_index:02d}",
            solver_factory=solver_factory,
            warm_start=have_proven_tail_incumbent,
        )
        reconstructed = current_scores()
        for world, (number, offset) in enumerate(binary_scores):
            if _binary_value(number) + offset != int(reconstructed[world]):
                raise SolverFailure("binary score adder failed exact reconstruction")
        expected = sum(
            int(int(book_max[world]) < thresholds[tier_index] <= int(reconstructed[world]))
            for world in range(n_worlds)
        )
        if optimum != expected:
            raise SolverFailure("tail tier failed immediate exact reconstruction")
        optima.append(optimum)
        solve_evidence.append(evidence)
        have_proven_tail_incumbent = True

    # Preserve the exact binary tail face and its immediately preceding proven
    # incumbent.  Rebuilding through continuous Horner prefixes produced
    # starred CBC rows; rebuilding cold through an equivalent integer face
    # triggered CBC's reproducible false-Infeasible path.  The residual solve
    # therefore starts once, prospectively, from this complete audited face.
    if not have_proven_tail_incumbent:
        raise SolverFailure("pricing has no proven tail-optimal incumbent")
    tail_seed_roster = frozenset(_solved_roster(model))
    tail_seed_scores = current_scores()
    score_variables = [
        _score_expression(model, scores[:, world])
        for world in range(n_worlds)
    ]

    residual_expressions: list[pulp.LpAffineExpression | pulp.LpVariable] = []
    positive_variables: list[pulp.LpVariable | None] = []
    for world, score in enumerate(score_variables):
        residual, positive = _add_exact_product_positive_part(
            model,
            score,
            binary_scores[world][0],
            binary_scores[world][1],
            scores[:, world],
            int(lower[world]),
            int(upper[world]),
            int(book_max[world]),
            name=f"world_{world:04d}",
            initial_roster=tail_seed_roster,
        )
        residual_expressions.append(residual)
        positive_variables.append(positive)
    residual_expression_sum = pulp.lpSum(residual_expressions)
    residual_upper = sum(
        max(0, int(upper[world]) - int(book_max[world]))
        for world in range(n_worlds)
    )
    residual_seed = sum(
        max(0, int(tail_seed_scores[world]) - int(book_max[world]))
        for world in range(n_worlds)
    )
    residual_number: _BinaryNumber | None = None
    if residual_upper == 0:
        residual_optimum = 0
    else:
        residual_number = _binary_weighted_sum(
            model.problem,
            tuple(
                (variable, int(coefficient))
                for variable, coefficient in residual_expression_sum.items()
            ),
            upper_bound=residual_upper,
            name="residual_gain_total",
            initialize_from_sources=True,
        )
        if _binary_value(residual_number) != residual_seed:
            raise SolverFailure("residual MIP start does not reconstruct")
        chunk_optima: list[int] = []
        chunk_prefix = 0
        high = len(residual_number.bits) - 1
        for chunk_index, chunk_expression in enumerate(
            _binary_objective_chunks(residual_number)
        ):
            low = max(0, high - RESIDUAL_OBJECTIVE_CHUNK_BITS + 1)
            chunk_width = high - low + 1
            base = chunk_prefix << (chunk_width + low)
            if base > residual_upper:
                raise SolverFailure("residual chunk prefix exceeds exact upper")
            maximum_chunk = min(
                (1 << chunk_width) - 1,
                (residual_upper - base) >> low,
            )
            if maximum_chunk == 0:
                # With all more-significant chunks frozen, the independently
                # proven aggregate upper bound forces this entire chunk to
                # zero.  Structural/forced bits never invoke CBC.
                chunk_optimum = 0
            else:
                model.problem.sense = pulp.LpMaximize
                model.problem.setObjective(chunk_expression)
                residual_solver = solver_factory(
                    PRICING_TIME_LIMIT_SECONDS, True
                )
                if not isinstance(residual_solver, _RetainedCbcSolver):
                    raise SolverFailure(
                        "residual pricing lacks retained CBC coordination"
                    )
                if residual_solver.cuts_exact is None:
                    residual_solver.optionsDict["cuts"] = False
                    residual_solver.cuts_exact = False
                elif residual_solver.cuts_exact is not False:
                    raise SolverFailure("residual pricing cuts contract changed")
                residual_solver.disable_preprocess()
                residual_evidence = _solve(
                    model.problem,
                    residual_solver,
                    f"pricing tier residual_gain chunk {chunk_index:02d}",
                )
                chunk_optimum = _integer_value(chunk_expression)
                if residual_evidence.objective != chunk_optimum:
                    raise SolverFailure(
                        "residual chunk evidence disagrees with objective"
                    )
                solve_evidence.append(residual_evidence)
            model.problem += chunk_expression == chunk_optimum, (
                f"freeze_residual_gain_chunk_{chunk_index:02d}"
            )
            chunk_optima.append(chunk_optimum)
            chunk_prefix = (chunk_prefix << chunk_width) | chunk_optimum
            high = low - 1
        residual_scores = current_scores()
        residual_optimum = sum(
            int(value) for value in np.maximum(residual_scores - book_max, 0)
        )
        if _binary_value(residual_number) != residual_optimum:
            raise SolverFailure("residual binary adder disagrees with optimum")
        if tuple(chunk_optima) != _residual_chunk_values(
            residual_optimum,
            residual_upper,
            bit_width=len(residual_number.bits),
        ):
            raise SolverFailure("residual chunks disagree with exact optimum")
    optima.append(residual_optimum)

    rank = {
        player_id: index + 1 for index, player_id in enumerate(sorted(
            model.decision
        ))
    }
    rank_expression = pulp.lpSum(
        model.decision[player.player_id] * rank[player.player_id]
        for player in model.players
    )
    rank_optimum, rank_evidence = _freeze_integer_objective(
        model.problem,
        rank_expression,
        sense=pulp.LpMinimize,
        name="canonical_rank_sum",
        solver_factory=solver_factory,
        warm_start=True,
        cuts_off=True,
        preprocess_off=True,
    )
    solve_evidence.append(rank_evidence)
    first = canonical_identity([
        player_id for player_id, variable in model.decision.items()
        if variable.value() is not None and variable.value() > 0.5
    ])

    def graph_bit_snapshot() -> tuple[
        tuple[tuple[int | None, ...], ...], tuple[int | None, ...]
    ]:
        tail = tuple(tuple(
            None if variable is None else int(round(float(variable.value())))
            for variable in variables
        ) for variables in indicator_variables)
        positive = tuple(
            None if variable is None else int(round(float(variable.value())))
            for variable in positive_variables
        )
        return tail, positive

    rank_graph_snapshot = graph_bit_snapshot()

    # Determine whether rank sum actually identifies one roster without ever
    # relying on an ``Infeasible`` status.  The first roster remains feasible,
    # so maximizing its exact Hamming distance must terminate Optimal: zero is
    # a uniqueness proof and a positive optimum proves ambiguity.
    probe_problem = _clone_residual_problem(
        model.problem, copy_proven_assignment=True
    )
    overlap_expression = pulp.lpSum(
        model.decision[player_id] for player_id in first
    )
    probe_problem.sense = pulp.LpMinimize
    probe_problem.setObjective(overlap_expression)
    ambiguity_solver = solver_factory(PRICING_TIME_LIMIT_SECONDS, True)
    if not isinstance(ambiguity_solver, _RetainedCbcSolver):
        raise SolverFailure("canonical ambiguity lacks retained CBC coordination")
    if ambiguity_solver.cuts_exact is None:
        ambiguity_solver.optionsDict["cuts"] = False
        ambiguity_solver.cuts_exact = False
    if ambiguity_solver.cuts_exact is not False:
        raise SolverFailure("canonical ambiguity cuts contract changed")
    ambiguity_solver.disable_preprocess()
    ambiguity_evidence = _solve(
        probe_problem,
        ambiguity_solver,
        "canonical ambiguity distance",
    )
    minimum_overlap = _integer_value(overlap_expression)
    ambiguity_distance = ROSTER_SIZE - minimum_overlap
    if ambiguity_evidence.objective != minimum_overlap:
        raise SolverFailure("canonical ambiguity evidence disagrees")
    solve_evidence.append(ambiguity_evidence)
    if not 0 <= ambiguity_distance <= ROSTER_SIZE:
        raise SolverFailure("canonical ambiguity distance is outside 0..9")
    ambiguous = ambiguity_distance > 0

    if ambiguous:
        _copy_proven_assignment(probe_problem, model.problem)
        fixed_ones = 0
        incidence_bits: dict[str, int] = {}
        player_ids = sorted(model.decision)
        index = 0
        while index < len(player_ids):
            remaining = len(player_ids) - index
            needed = ROSTER_SIZE - fixed_ones
            if needed == 0:
                for player_id in player_ids[index:]:
                    model.problem += model.decision[player_id] == 0, (
                        f"canonical_incidence_{index:04d}"
                    )
                    incidence_bits[player_id] = 0
                    index += 1
                break
            elif needed == remaining:
                for player_id in player_ids[index:]:
                    model.problem += model.decision[player_id] == 1, (
                        f"canonical_incidence_{index:04d}"
                    )
                    incidence_bits[player_id] = 1
                    fixed_ones += 1
                    index += 1
                break
            else:
                chunk = player_ids[
                    index:index + RESIDUAL_OBJECTIVE_CHUNK_BITS
                ]
                chunk_expression = pulp.lpSum(
                    model.decision[player_id] * (
                        1 << (len(chunk) - offset - 1)
                    )
                    for offset, player_id in enumerate(chunk)
                )
                model.problem.sense = pulp.LpMaximize
                model.problem.setObjective(chunk_expression)
                incidence_solver = solver_factory(
                    PRICING_TIME_LIMIT_SECONDS, True
                )
                if not isinstance(incidence_solver, _RetainedCbcSolver):
                    raise SolverFailure(
                        "canonical incidence lacks retained CBC coordination"
                    )
                if incidence_solver.cuts_exact is None:
                    incidence_solver.optionsDict["cuts"] = False
                    incidence_solver.cuts_exact = False
                if incidence_solver.cuts_exact is not False:
                    raise SolverFailure(
                        "canonical incidence cuts contract changed"
                    )
                # This fixed tie-only mode preserves the exact proven face and
                # its complete incumbent while avoiding CBC's reproducible
                # presolve false-Infeasible path.
                incidence_solver.disable_preprocess()
                bit_evidence = _solve(
                    model.problem,
                    incidence_solver,
                    f"canonical incidence chunk {index:04d}",
                )
                chunk_optimum = _integer_value(chunk_expression)
                if bit_evidence.objective != chunk_optimum:
                    raise SolverFailure("canonical incidence evidence disagrees")
                solve_evidence.append(bit_evidence)
                reconstructed = 0
                for offset, player_id in enumerate(chunk):
                    bit = _integer_value(model.decision[player_id])
                    if bit not in {0, 1}:
                        raise SolverFailure(
                            "canonical incidence bit is not binary"
                        )
                    reconstructed += bit * (
                        1 << (len(chunk) - offset - 1)
                    )
                    model.problem += model.decision[player_id] == bit, (
                        f"canonical_incidence_{index + offset:04d}"
                    )
                    fixed_ones += bit
                    incidence_bits[player_id] = bit
                if reconstructed != chunk_optimum:
                    raise SolverFailure(
                        "canonical incidence chunk failed reconstruction"
                    )
                index += len(chunk)
        roster = canonical_identity([
            player_id for player_id, bit in incidence_bits.items() if bit == 1
        ])
        final_graph_snapshot = graph_bit_snapshot()
    else:
        roster = first
        final_graph_snapshot = rank_graph_snapshot

    audit_legal_identity(rows, roster)
    for player_id, variable in model.decision.items():
        value = variable.value()
        if value is None or abs(float(value) - round(float(value))) > 1e-9:
            raise SolverFailure("final roster decision is not exact integral")
        if int(round(float(value))) != int(player_id in roster):
            raise SolverFailure("final roster decisions disagree with identity")
    reconstructed_rank = sum(rank[player_id] for player_id in roster)
    if reconstructed_rank != rank_optimum:
        raise SolverFailure("final roster rank differs from its frozen optimum")
    for forbidden in normalized_forbidden:
        if len(set(roster) & set(forbidden)) > ROSTER_SIZE - 1:
            raise SolverFailure("priced roster violates a complete no-good cut")
    if roster in normalized_forbidden:
        raise SolverFailure("priced roster repeats a forbidden identity")
    chosen_rows = np.asarray([row_index[player_id] for player_id in roster], dtype=int)
    reconstructed_scores = scores[chosen_rows].sum(axis=0, dtype=np.int64)
    if np.any(reconstructed_scores < lower) or np.any(reconstructed_scores > upper):
        raise SolverFailure("priced roster violates an exact legal bound")
    indicators = tuple(tuple(
        int(int(book_max[world]) < threshold <= int(reconstructed_scores[world]))
        for world in range(n_worlds)
    ) for threshold in thresholds)
    counts = tuple(sum(values) for values in indicators)
    residuals = np.maximum(reconstructed_scores - book_max, 0).astype(np.int64)
    gain = sum(int(value) for value in residuals)
    if counts != tuple(optima[:-1]) or gain != residual_optimum:
        raise SolverFailure("priced objective failed independent reconstruction")
    snapshot_tail, snapshot_positive = final_graph_snapshot
    for tier_index, variables in enumerate(snapshot_tail):
        for world, value in enumerate(variables):
            if value is not None and value != indicators[tier_index][world]:
                raise SolverFailure("tail indicator failed exact bi-implication")
    for world in range(n_worlds):
        graph_value = max(
            0, int(reconstructed_scores[world] - book_max[world])
        )
        if graph_value != int(residuals[world]):
            raise SolverFailure("positive-part residual failed exact graph")
        positive = snapshot_positive[world]
        if positive is not None and positive != int(
            reconstructed_scores[world] > book_max[world]
        ):
            raise SolverFailure("positive-part branch failed exact graph")

    objective = (*counts, gain)
    return PricingResult(
        roster=roster,
        scores_micro=tuple(int(value) for value in reconstructed_scores),
        marginal_threshold_counts=counts,
        residuals_micro=tuple(int(value) for value in residuals),
        residual_gain_micro=gain,
        objective_vector=objective,
        indicators_by_threshold=indicators,
        rank_sum=rank_optimum,
        rank_sum_ambiguous=ambiguous,
        admissible=any(value > 0 for value in counts),
        sequential_optima=tuple(optima),
        ambiguity_distance=ambiguity_distance,
        rank_first_roster=first,
        pricing_input_sha256=pricing_input_digest,
        no_good_rosters=normalized_forbidden,
        solve_evidence=tuple(solve_evidence),
    )


def validate_raw_micro_parity(
    raw_player_draws: np.ndarray,
    player_scores_micro: np.ndarray,
    roster_rows: Sequence[int],
    *,
    thresholds_micro: Sequence[int] = TAIL_THRESHOLDS_MICRO,
) -> float:
    """Validate raw float32/micro-DK score and threshold parity.

    Returns the maximum absolute DK-point reconstruction error.  The caller
    supplies row indices only after roster identity has been frozen.
    """
    raw = np.asarray(raw_player_draws)
    if raw.dtype != np.float32 or raw.ndim != 2 or not np.isfinite(raw).all():
        raise ResidualWorldError("raw parity draws must be one finite float32 matrix")
    micro = _micro_matrix(player_scores_micro, rows=raw.shape[0])
    if raw.shape != micro.shape:
        raise ResidualWorldError("raw and micro-DK draw matrices differ")
    canonical_micro = to_micro_dk(raw)
    if not np.array_equal(micro, canonical_micro):
        raise ResidualWorldError(
            "micro-DK matrix differs from canonical float32 quantization"
        )
    chosen = np.asarray(tuple(
        _strict_integer(value, "raw/micro parity roster row")
        for value in roster_rows
    ), dtype=int)
    if len(chosen) != ROSTER_SIZE or len(set(chosen.tolist())) != ROSTER_SIZE:
        raise ResidualWorldError("raw/micro parity roster rows are malformed")
    if np.any(chosen < 0) or np.any(chosen >= raw.shape[0]):
        raise ResidualWorldError("raw/micro parity roster row is out of range")
    raw_score = raw[chosen].astype(np.float64).sum(axis=0)
    micro_score = micro[chosen].sum(axis=0, dtype=np.int64)
    difference = np.abs(raw_score - micro_score / MICRO_DK_SCALE)
    maximum = float(difference.max(initial=0.0))
    if maximum > RAW_MICRO_MAX_ERROR_DK:
        raise ResidualWorldError("raw/micro-DK score mismatch exceeds exact bound")
    for threshold in _threshold_tuple(thresholds_micro):
        if not np.array_equal(
            raw_score >= (int(threshold) / MICRO_DK_SCALE),
            micro_score >= int(threshold),
        ):
            raise ResidualWorldError("raw/micro-DK threshold indicators disagree")
    return maximum


def position_shape_upper_bounds_micro(
    player_scores_micro: np.ndarray,
    positions: Sequence[object],
) -> np.ndarray:
    """Return the relaxed exact-slot upper bound used only for reservoirs."""
    scores = _micro_matrix(player_scores_micro)
    pos = np.asarray([str(value).upper() for value in positions], dtype=object)
    if len(pos) != scores.shape[0]:
        raise ResidualWorldError("positions do not align to player scores")

    def top(position: str, count: int) -> np.ndarray:
        rows = np.flatnonzero(pos == position)
        if len(rows) < count:
            raise ResidualWorldError(
                f"position-shape bound needs at least {count} {position} rows"
            )
        values = scores[rows]
        split = values.shape[0] - count
        return np.partition(values, split, axis=0)[split:].sum(
            axis=0, dtype=np.int64
        )

    fixed = top("QB", 1) + top("DST", 1)
    shapes = [
        top("RB", rb) + top("WR", wr) + top("TE", te)
        for rb, wr, te in CLASSIC_SKILL_PATTERNS
    ]
    return fixed + np.maximum.reduce(shapes)


def _independent_block_selection(
    world_ids: Sequence[WorldId],
    book_maxima_micro: Sequence[int] | np.ndarray,
    upper_bounds_micro: Sequence[int] | np.ndarray,
    block_quotas: Sequence[tuple[str, int]],
    *,
    thresholds_micro: Sequence[int] = TAIL_THRESHOLDS_MICRO,
) -> tuple[WorldSelection, ...]:
    """Independently reconstruct the frozen cyclic selection receipt.

    This deliberately does not call either public selection helper.  It is a
    fail-closed boundary against a helper regression or monkeypatched result.
    """
    worlds = tuple(world_ids)
    n = len(worlds)
    if not worlds or len(set(worlds)) != n:
        raise ResidualWorldError("selection audit worlds are empty or repeat")
    maxima = _micro_vector(book_maxima_micro, n, "selection audit maxima")
    upper = _micro_vector(upper_bounds_micro, n, "selection audit upper bounds")
    if np.any(upper < maxima):
        raise ResidualWorldError("selection audit upper bound is below maximum")
    quotas = tuple(
        (_strict_string(block, "selection audit block"),
         _strict_integer(quota, "selection audit quota"))
        for block, quota in block_quotas
    )
    if (
        not quotas
        or any(quota <= 0 for _, quota in quotas)
        or len({block for block, _ in quotas}) != len(quotas)
        or set(world.block for world in worlds) != {block for block, _ in quotas}
    ):
        raise ResidualWorldError("selection audit block quotas are malformed")
    thresholds = _threshold_tuple(thresholds_micro)
    result: list[WorldSelection] = []
    for block, quota in quotas:
        block_rows = [
            index for index, world in enumerate(worlds) if world.block == block
        ]
        queues = {
            threshold: sorted(
                (
                    index for index in block_rows
                    if int(maxima[index]) < threshold <= int(upper[index])
                ),
                key=lambda index: (
                    threshold - int(maxima[index]),
                    -(int(upper[index]) - threshold),
                    worlds[index],
                ),
            )
            for threshold in thresholds
        }
        cursors = {threshold: 0 for threshold in thresholds}
        selected: set[WorldId] = set()
        while len(selected) < quota:
            progressed = False
            for threshold in thresholds:
                queue = queues[threshold]
                cursor = cursors[threshold]
                while cursor < len(queue) and worlds[queue[cursor]] in selected:
                    cursor += 1
                cursors[threshold] = cursor
                if cursor == len(queue):
                    continue
                index = queue[cursor]
                cursors[threshold] = cursor + 1
                selected.add(worlds[index])
                result.append(WorldSelection(
                    worlds[index], threshold, int(maxima[index]), int(upper[index])
                ))
                progressed = True
                if len(selected) == quota:
                    break
            if not progressed:
                raise InsufficientResidualWorldSupport(
                    "independent tail queues cannot fill the declared quota"
                )
    return tuple(result)


def _audit_block_selection(
    observed: Sequence[WorldSelection],
    world_ids: Sequence[WorldId],
    book_maxima_micro: Sequence[int] | np.ndarray,
    upper_bounds_micro: Sequence[int] | np.ndarray,
    block_quotas: Sequence[tuple[str, int]],
) -> tuple[WorldSelection, ...]:
    receipt = tuple(observed)
    if any(not isinstance(value, WorldSelection) for value in receipt):
        raise ResidualWorldError("world selection receipt has a malformed row")
    expected = _independent_block_selection(
        world_ids,
        book_maxima_micro,
        upper_bounds_micro,
        block_quotas,
        thresholds_micro=TAIL_THRESHOLDS_MICRO,
    )
    if receipt != expected:
        raise ResidualWorldError(
            "world selection differs from independent deterministic receipt"
        )
    if len({value.world_id for value in receipt}) != len(receipt):
        raise ResidualWorldError("world selection receipt repeats an identity")
    return receipt


def select_cyclic_threshold_worlds(
    world_ids: Sequence[WorldId],
    book_maxima_micro: Sequence[int] | np.ndarray,
    upper_bounds_micro: Sequence[int] | np.ndarray,
    quota: int,
    *,
    thresholds_micro: Sequence[int] = TAIL_THRESHOLDS_MICRO,
) -> tuple[WorldSelection, ...]:
    """Apply the frozen cyclic tail-queue algorithm to one block."""
    identities = tuple(world_ids)
    if not identities or len(set(identities)) != len(identities):
        raise ResidualWorldError("world identities are empty or repeat")
    if len({world.block for world in identities}) != 1:
        raise ResidualWorldError("cyclic world selection must receive one block")
    quota = _strict_integer(quota, "cyclic world quota")
    if not 1 <= quota <= len(identities):
        raise ResidualWorldError("cyclic world quota is outside the block")
    n = len(identities)
    maxima = _micro_vector(book_maxima_micro, n, "world book maxima")
    bounds = _micro_vector(upper_bounds_micro, n, "world upper bounds")
    if np.any(bounds < maxima):
        raise ResidualWorldError("world upper bound is below current book maximum")
    thresholds = _threshold_tuple(thresholds_micro)

    queues: dict[int, list[int]] = {}
    cursors: dict[int, int] = {}
    for threshold in thresholds:
        eligible = [
            index for index in range(n)
            if int(maxima[index]) < threshold <= int(bounds[index])
        ]
        queues[threshold] = sorted(eligible, key=lambda index: (
            threshold - int(maxima[index]),
            -(int(bounds[index]) - threshold),
            identities[index],
        ))
        cursors[threshold] = 0

    chosen: list[WorldSelection] = []
    selected: set[WorldId] = set()
    while len(chosen) < quota:
        progressed = False
        for threshold in thresholds:
            queue = queues[threshold]
            cursor = cursors[threshold]
            while cursor < len(queue) and identities[queue[cursor]] in selected:
                cursor += 1
            cursors[threshold] = cursor
            if cursor >= len(queue):
                continue
            index = queue[cursor]
            cursors[threshold] = cursor + 1
            world = identities[index]
            selected.add(world)
            chosen.append(WorldSelection(
                world_id=world,
                queue_threshold_micro=threshold,
                book_max_micro=int(maxima[index]),
                upper_bound_micro=int(bounds[index]),
            ))
            progressed = True
            if len(chosen) == quota:
                break
        if not progressed:
            raise InsufficientResidualWorldSupport(
                f"tail queues exhausted at {len(chosen)} of {quota} worlds"
            )
    return tuple(chosen)


def select_block_stratified_worlds(
    world_ids: Sequence[WorldId],
    book_maxima_micro: Sequence[int] | np.ndarray,
    upper_bounds_micro: Sequence[int] | np.ndarray,
    block_quotas: Sequence[tuple[str, int]],
    *,
    thresholds_micro: Sequence[int] = TAIL_THRESHOLDS_MICRO,
) -> tuple[WorldSelection, ...]:
    """Select exact per-block quotas in the declared construction order."""
    identities = tuple(world_ids)
    if len(set(identities)) != len(identities):
        raise ResidualWorldError("block-stratified world identities repeat")
    n = len(identities)
    maxima = _micro_vector(book_maxima_micro, n, "world book maxima")
    bounds = _micro_vector(upper_bounds_micro, n, "world upper bounds")
    quota_rows = tuple((
        _strict_string(block, "world block"),
        _strict_integer(quota, "block quota"),
    ) for block, quota in block_quotas)
    if any(quota <= 0 for _, quota in quota_rows):
        raise ResidualWorldError("block quota must be one positive integer")
    if not quota_rows or len({block for block, _ in quota_rows}) != len(quota_rows):
        raise ResidualWorldError("block quotas are empty or repeat")
    if set(world.block for world in identities) != {block for block, _ in quota_rows}:
        raise ResidualWorldError("block quotas do not cover the supplied worlds")
    result: list[WorldSelection] = []
    for block, quota in quota_rows:
        indices = [index for index, world in enumerate(identities) if world.block == block]
        result.extend(select_cyclic_threshold_worlds(
            [identities[index] for index in indices],
            maxima[indices],
            bounds[indices],
            quota,
            thresholds_micro=thresholds_micro,
        ))
    return tuple(result)


def utility_from_maxima(
    maxima_micro: Sequence[int] | np.ndarray,
    *,
    thresholds_micro: Sequence[int] = TAIL_THRESHOLDS_MICRO,
    sum_max_cap_micro: int | None = None,
) -> TailUtility:
    maxima = np.asarray(maxima_micro)
    if maxima.dtype.kind not in "iu" or maxima.ndim != 1 or not len(maxima):
        raise ResidualWorldError("tail utility maxima must be one integer vector")
    if maxima.dtype.kind == "u" and int(maxima.max()) > np.iinfo(np.int64).max:
        raise ResidualWorldError("tail utility maxima exceed signed int64")
    maxima = maxima.astype(np.int64, copy=False)
    thresholds = _threshold_tuple(thresholds_micro)
    counts = tuple(int(np.count_nonzero(maxima >= threshold)) for threshold in thresholds)
    if sum_max_cap_micro is None:
        summed = maxima
    else:
        cap = _strict_integer(sum_max_cap_micro, "tail utility sum-max cap")
        if cap <= 0:
            raise ResidualWorldError("tail utility sum-max cap must be positive")
        summed = np.minimum(maxima, cap)
    return TailUtility(counts, sum(int(value) for value in summed))


def tail_utility(
    candidate_scores_micro: np.ndarray,
    *,
    thresholds_micro: Sequence[int] = TAIL_THRESHOLDS_MICRO,
    sum_max_cap_micro: int | None = None,
) -> TailUtility:
    scores = _micro_matrix(candidate_scores_micro, label="candidate scores")
    return utility_from_maxima(
        scores.max(axis=0),
        thresholds_micro=thresholds_micro,
        sum_max_cap_micro=sum_max_cap_micro,
    )


def reverse_greedy_pruning_order(
    candidate_identities: Sequence[Sequence[object]],
    candidate_scores_micro: np.ndarray,
    protected_identities: Sequence[Sequence[object]],
    *,
    steps: int = K_MAX,
    expected_protected_count: int | None = None,
    thresholds_micro: Sequence[int] = TAIL_THRESHOLDS_MICRO,
    sum_max_cap_micro: int | None = None,
) -> PruningResult:
    """Freeze the deterministic matched-budget reverse-greedy removals."""
    identities = tuple(canonical_identity(value) for value in candidate_identities)
    if len(set(identities)) != len(identities):
        raise ResidualWorldError("pruning candidate identities repeat")
    scores = _micro_matrix(
        candidate_scores_micro, rows=len(identities), label="candidate scores"
    )
    normalized_protected = tuple(
        canonical_identity(value) for value in protected_identities
    )
    if len(set(normalized_protected)) != len(normalized_protected):
        raise ResidualWorldError("protected book identities repeat")
    protected = set(normalized_protected)
    if not protected <= set(identities):
        raise ResidualWorldError("protected book is not a candidate subset")
    if expected_protected_count is not None:
        protected_count = _strict_integer(
            expected_protected_count, "expected protected count"
        )
        if len(protected) != protected_count:
            raise ResidualWorldError("protected book count differs from protocol")
    steps = _strict_integer(steps, "pruning steps")
    if not 0 <= steps <= K_MAX:
        raise ResidualWorldError("pruning steps must be in the frozen 0..8 range")
    if len(identities) - len(protected) < steps:
        raise ResidualWorldError("not enough unprotected candidates to prune")

    remaining = list(range(len(identities)))
    result: list[PruningStep] = []
    for dose in range(1, steps + 1):
        matrix = scores[remaining]
        before = utility_from_maxima(
            matrix.max(axis=0),
            thresholds_micro=thresholds_micro,
            sum_max_cap_micro=sum_max_cap_micro,
        )
        if len(remaining) < 2:
            raise ResidualWorldError("pruning would empty the candidate pool")
        maxima = matrix.max(axis=0)
        maximum_count = np.count_nonzero(matrix == maxima, axis=0)
        second = np.partition(matrix, len(remaining) - 2, axis=0)[-2]
        choices: list[tuple[tuple[int, ...], tuple[str, ...], int, TailUtility]] = []
        for local_index, original_index in enumerate(remaining):
            identity = identities[original_index]
            if identity in protected:
                continue
            unique_maximum = (matrix[local_index] == maxima) & (maximum_count == 1)
            after_maxima = np.where(unique_maximum, second, maxima)
            utility = utility_from_maxima(
                after_maxima,
                thresholds_micro=thresholds_micro,
                sum_max_cap_micro=sum_max_cap_micro,
            )
            choices.append((utility.vector, identity, original_index, utility))
        if not choices:
            raise ResidualWorldError("pruning has no unprotected candidate")
        # Greatest utility wins; exact ties remove the lexicographically
        # greatest canonical identity, preserving the smallest identity.
        _, identity, original_index, after = max(
            choices, key=lambda value: (value[0], value[1])
        )
        remaining.remove(original_index)
        result.append(PruningStep(
            dose=dose,
            removed_identity=identity,
            utility_before=before,
            utility_after=after,
            remaining_candidates=len(remaining),
        ))
    return PruningResult(len(identities), tuple(result))


def matched_budget_treatment_pool(
    control_identities: Sequence[Sequence[object]],
    pruning: PruningResult,
    generated_columns: Sequence[Sequence[object]],
) -> tuple[tuple[str, ...], ...]:
    """Replace the realized pruning prefix with ``k`` novel columns."""
    control = tuple(canonical_identity(value) for value in control_identities)
    if len(set(control)) != len(control):
        raise ResidualWorldError("control candidate identities repeat")
    generated = tuple(canonical_identity(value) for value in generated_columns)
    if not isinstance(pruning, PruningResult):
        raise ResidualWorldError("matched-budget pruning receipt is missing")
    if pruning.original_candidates != len(control):
        raise ResidualWorldError("pruning receipt candidate count is misaligned")
    if tuple(step.dose for step in pruning.steps) != tuple(
        range(1, len(pruning.steps) + 1)
    ):
        raise ResidualWorldError("pruning receipt doses are not consecutive")
    if any(
        step.remaining_candidates != len(control) - step.dose
        for step in pruning.steps
    ):
        raise ResidualWorldError("pruning receipt remaining counts are invalid")
    if len(generated) > len(pruning.steps) or len(generated) > K_MAX:
        raise ResidualWorldError("generated dose exceeds realized pruning")
    removed = pruning.removal_order[:len(generated)]
    if len(set(removed)) != len(removed) or not set(removed) <= set(control):
        raise ResidualWorldError("pruning prefix is not a valid control subset")
    if len(set(generated)) != len(generated):
        raise ResidualWorldError("generated column identities repeat")
    if set(generated) & set(control):
        raise ResidualWorldError("generated column resurrects a control identity")
    retained = tuple(identity for identity in control if identity not in set(removed))
    treatment = (*retained, *generated)
    if len(treatment) != len(control) or len(set(treatment)) != len(treatment):
        raise ResidualWorldError("treatment candidate budget is not exact")
    return treatment


def verify_protected_book_reproduction(
    expected_ordered_book: Sequence[Sequence[object]],
    interim_ordered_books: Sequence[Sequence[Sequence[object]]],
) -> None:
    """Require every pre-generated dose to reproduce the protected book."""
    expected = tuple(canonical_identity(value) for value in expected_ordered_book)
    if len(set(expected)) != len(expected):
        raise ResidualWorldError("protected selected book identities repeat")
    if len(expected) != ENTRY_COUNT:
        raise ResidualWorldError("protected selected book is not exact-80")
    if len(interim_ordered_books) != K_MAX:
        raise ResidualWorldError("protected selector audit does not contain 8 doses")
    for dose, book in enumerate(interim_ordered_books, start=1):
        observed = tuple(canonical_identity(value) for value in book)
        if observed != expected:
            raise ResidualWorldError(
                f"protected selected book changes at pruning dose {dose}"
            )


def run_adaptive_column_sequence(
    pricing_step: PricingStep,
    *,
    k_max: int = K_MAX,
) -> AdaptiveSequence:
    """Run a sequential dose and stop irrevocably at the first null column.

    ``pricing_step`` owns construction-book updates and active-world rebuilding
    for its iteration.  This small orchestrator owns the protocol state
    machine: prior columns are passed in canonical order, every positive
    result is retained, and a null result terminates the sequence immediately.
    """
    k_max = _strict_integer(k_max, "adaptive column maximum")
    if k_max != K_MAX:
        raise ResidualWorldError("adaptive column maximum must remain frozen at 8")
    columns: list[tuple[str, ...]] = []
    steps: list[AdaptiveStep] = []
    for iteration in range(1, k_max + 1):
        result = pricing_step(iteration, tuple(columns))
        if canonical_identity(result.roster) != result.roster:
            raise ResidualWorldError("adaptive pricing roster is not canonical")
        if len(result.marginal_threshold_counts) != len(TAIL_THRESHOLDS_MICRO):
            raise ResidualWorldError("adaptive pricing tail vector has wrong width")
        if result.objective_vector != (
            *result.marginal_threshold_counts, result.residual_gain_micro
        ):
            raise ResidualWorldError("adaptive pricing objective is inconsistent")
        steps.append(AdaptiveStep(iteration, result))
        if not result.admissible:
            if any(result.marginal_threshold_counts):
                raise ResidualWorldError("null pricing result has a positive tail tier")
            return AdaptiveSequence(
                steps=tuple(steps),
                columns=tuple(columns),
                stopped_on_first_null=True,
                null_iteration=iteration,
            )
        if not any(value > 0 for value in result.marginal_threshold_counts):
            raise ResidualWorldError("admissible pricing result has no positive tail tier")
        if result.roster in columns:
            raise ResidualWorldError("adaptive pricing repeated a generated identity")
        columns.append(result.roster)
    return AdaptiveSequence(
        steps=tuple(steps),
        columns=tuple(columns),
        stopped_on_first_null=False,
        null_iteration=None,
    )
