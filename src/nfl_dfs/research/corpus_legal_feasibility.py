"""Outcome-blind, request-local corpus legal-feasibility science core.

The module deliberately does not call the backtest engine, production lineup
entry points, candidate families, CBWU admission, object storage, BigQuery,
or any realized-outcome reader.  It consumes one already prepared later-
period slate, applies the seven frozen parameter assignments, and solves the
same canonical simulated-world visits under a fresh constraints-only model
for every assignment/visit cell.

The default solver is a research seam, not an execution authority.  It uses
one-thread CBC with an integer micro-DK primary objective.  Primary ties are
resolved by the minimum UTF-8 player-id rank sum; a final no-good solve proves
that this secondary optimum names one roster.  A rank-sum collision is
reported as ambiguous and fails closed.  Most tests inject callbacks; one
bounded regression runs the bundled CBC through both proof stages.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from decimal import Decimal, InvalidOperation
from enum import Enum
import fcntl
from functools import lru_cache
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import tempfile
import time
from typing import Final, Protocol
import zlib

import numpy as np
import pulp

from nfl_dfs.optimizer.lineup import StackRules, add_classic_lineup_constraints
from nfl_dfs.research import residual_world_columns as rw
from nfl_dfs.research.corpus_artifact_source_authority import (
    CorpusArtifactSourceAuthorityError,
    UNIVERSE_SCOPE as ARTIFACT_SOURCE_UNIVERSE_SCOPE,
    validate_completion_bytes as validate_artifact_source_completion_bytes,
)
from nfl_dfs.research.corpus_parametric_batch import (
    MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
    PARAMETER_ORDER,
    PARAMETER_SET_ORDER,
    SELECTED_ENTRY_BUDGET,
    SOLVER_TIMEOUT_LAW,
    SOLVER_TIMEOUT_SECONDS,
    SOLVE_ATTEMPTS_PER_BLOCK,
    TASK_WORLD_SOURCE_ROLES,
    WORLDS_PER_BLOCK,
    bind_task_request_to_manifest,
    canonical_sha256 as batch_canonical_sha256,
    frozen_parameter_sets,
    validate_batch_manifest,
    validate_parameter_set,
)
from nfl_dfs.research.effective_policy_rule_inventory import (
    EffectivePolicyInventoryError,
    PARAMETRIC_FIELDS,
    SCHEMA as INVENTORY_SCHEMA,
    canonical_sha256 as inventory_canonical_sha256,
    validate_effective_policy_rule_inventory,
)
from nfl_dfs.research.lr8_later_period_source import (
    LR8LaterSourceError,
    PreparedLaterSlate,
    canonical_json as later_source_canonical_json,
    prepare_later_slate,
    validate_source_freeze,
)


SCHEMA: Final = "corpus-legal-feasibility-science/v1"
AUTHORITY_BUNDLE_SCHEMA: Final = "corpus-legal-feasibility-authority-bundle/v1"
DRAFT_AUTHORITY_BUNDLE_SCHEMA: Final = (
    "corpus-legal-feasibility-draft-authority-bundle/v1"
)
ATTEMPT_LEDGER_SCHEMA: Final = "corpus-legal-feasibility-attempt-ledger/v1"
MATRIX_AUTHORITY_SCHEMA: Final = "corpus-legal-feasibility-matrix-authority/v1"
SOLVER_PROOF_SCHEMA: Final = "corpus-cbc-solver-proof/v1"
WORLD_SCHEDULE_SCHEMA: Final = "corpus-ranked-world-schedule/v1"
RUNTIME_POLICY_SCHEMA: Final = "corpus-runtime-effective-policy/v1"
VARIANT_RESULT_SCHEMA: Final = "corpus-legal-feasibility-variant-result/v2"
BATCH_RESULT_SCHEMA: Final = "corpus-legal-feasibility-batch-result/v1"
VISITS_PER_BLOCK: Final = SOLVE_ATTEMPTS_PER_BLOCK
ENTRY_COUNT: Final = SELECTED_ENTRY_BUDGET
TAIL_LINE_DK: Final = 194.0
MICRO_DK_SCALE: Final = 1_000_000
EXPECTED_WORLD_COUNT: Final = len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK
MAX_EXACT_CBC_INTEGER: Final = (1 << 53) - 1

CBC_THREADS: Final = 1
CBC_RANDOM_SEED: Final = 20_260_821
CBC_INTEGER_TOLERANCE: Final = "1e-9"
CBC_PRIMAL_TOLERANCE: Final = "1e-9"
CBC_INTEGER_TOLERANCE_VALUE: Final = float(CBC_INTEGER_TOLERANCE)
CBC_OPTIONS: Final = (
    f"randomSeed {CBC_RANDOM_SEED}",
    f"randomCbcSeed {CBC_RANDOM_SEED}",
    f"integerTolerance {CBC_INTEGER_TOLERANCE}",
    f"primalTolerance {CBC_PRIMAL_TOLERANCE}",
)
CBC_OPTIONS_PAYLOAD: Final = {
    "gap_abs": 0.0,
    "gap_rel": 0.0,
    "integer_tolerance": CBC_INTEGER_TOLERANCE,
    "primal_tolerance": CBC_PRIMAL_TOLERANCE,
    "random_cbc_seed": CBC_RANDOM_SEED,
    "random_seed": CBC_RANDOM_SEED,
    "threads": CBC_THREADS,
}
_CBC_COMMAND_LINE_SUFFIX: Final = " (default strategy 1)"
_CBC_OPTIMAL_TERMINAL: Final = "Result - Optimal solution found"
_CBC_INFEASIBLE_TERMINAL: Final = re.compile(
    r"(?:Result - Problem proven infeasible|"
    r"Problem is infeasible(?: - .*?)?)"
)

_COMMON_LAW_BODY_ROLES: Final = (
    "code_source",
    "world_schedule",
    "objective",
    "generator_families",
    "unique_fill",
    "deduplication",
    "admission",
    "cbwu",
    "selector",
    "line_194",
    "exact_80",
)
_CODE_SOURCE_IMPLEMENTATION_PATHS: Final = (
    "src/nfl_dfs/optimizer/lineup.py",
    "src/nfl_dfs/research/corpus_artifact_source_authority.py",
    "src/nfl_dfs/research/corpus_legal_feasibility.py",
    "src/nfl_dfs/research/corpus_legal_feasibility_verifier.py",
    "src/nfl_dfs/research/corpus_parametric_batch.py",
    "src/nfl_dfs/research/effective_policy_rule_inventory.py",
    "src/nfl_dfs/research/lr8_later_period_source.py",
    "src/nfl_dfs/research/residual_world_columns.py",
)
_CODE_SOURCE_BUILD_PATHS: Final = (
    "Dockerfile.corpus-research-expansion",
    "cloudbuild.corpus-research-expansion.yaml",
)
_CODE_SOURCE_TERMINAL_VERIFICATION: Final = {
    "authority": "external-terminal-execution-receipt",
    "required": True,
    "verifies": [
        "cloud_build_id",
        "immutable_image",
        "source_commit_sha",
    ],
}
EVIDENCE_PACK_CODEC: Final = "zlib-rfc1950-level9/v1"
MAX_SOLVER_STAGES_PER_VISIT: Final = 2
EVIDENCE_SHARD_VISITS: Final = 100
EVIDENCE_SHARDS_PER_VARIANT: Final = (
    MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION // EVIDENCE_SHARD_VISITS
)
EVIDENCE_SHARDS_PER_TASK: Final = (
    len(PARAMETER_SET_ORDER) * EVIDENCE_SHARDS_PER_VARIANT
)
MAX_SHARD_SOLVER_STAGE_COUNT: Final = (
    EVIDENCE_SHARD_VISITS * MAX_SOLVER_STAGES_PER_VISIT
)
MAX_SOLVER_EVIDENCE_BYTES_PER_STAGE: Final = 512 * 1024
MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES: Final = (
    MAX_SHARD_SOLVER_STAGE_COUNT * MAX_SOLVER_EVIDENCE_BYTES_PER_STAGE
)
MAX_SHARD_SOLVER_EVIDENCE_COMPRESSED_BYTES: Final = (
    MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES
    + (MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES >> 12)
    + (MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES >> 14)
    + (MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES >> 25)
    + 13
)
MAX_SHARD_SOLVER_EVIDENCE_INDEX_BYTES: Final = 16 * 1024 * 1024
CLOCK_MEASUREMENT_TOLERANCE_MICROSECONDS: Final = 10

_REGISTERED_MECHANISM_BODIES: Final = {
    "objective": {
        "schema": "corpus-generation-objective/v1",
        "objective": "maximize-selected-player-draw-sum",
        "source_dtype": "float32",
        "promotion_before_scaling": "exact-float32-to-float64",
        "micro_dk_scale": MICRO_DK_SCALE,
        "rounding": "numpy-rint-ieee754-nearest-ties-to-even",
        "integer_dtype": "signed-int64",
        "reject_nonfinite": True,
        "selected_player_count": rw.ROSTER_SIZE,
        "maximum_exact_roster_integer": MAX_EXACT_CBC_INTEGER,
        "per_player_absolute_bound_law": (
            "abs(draw)<=maximum_exact_roster_integer/"
            "(micro_dk_scale*selected_player_count)"
        ),
        "reject_if_nine_player_integer_sum_exceeds_bound": True,
        "secondary_objective": "minimum-utf8-player-id-rank-sum",
        "rank_origin": 1,
        "rank_order": "canonical-utf8-player-id-ascending",
        "rank_sum_range": "9*(player_count-9)",
        "lexicographic_radix": "9*(player_count-9)+1",
        "combined_objective": "primary_micro*radix-rank_sum",
        "combined_coefficient_law": "player_micro*radix-player_rank",
        "prove_all_combined_coefficients_and-nine-player-sum-below_2^53": True,
        "collision_proof": (
            "freeze-combined-optimum-plus-no-good-must-be-infeasible"
        ),
        "one_optimum_per_visit": True,
        "outcome_blind": True,
    },
    "generator_families": {
        "schema": "corpus-generator-families/v1",
        "engine": False,
        "tail_select_lineups": False,
        "optimize_many": False,
        "candidate_family_injection": False,
        "no_good_feedback_between_visits": False,
    },
    "unique_fill": {
        "schema": "corpus-unique-fill/v1",
        "enabled": False,
        "retry_budget": 0,
    },
    "deduplication": {
        "schema": "corpus-deduplication/v1",
        "identity": "canonical-sorted-nine-player-ids",
        "order": "first-visit-occurrence",
        "candidate_truncation": False,
        "maximum_visit_outputs_before_deduplication": (
            MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
        ),
    },
    "admission": {
        "schema": "corpus-admission/v1",
        "law": "full-first-occurrence-unique-union",
        "family_admission": False,
    },
    "cbwu": {
        "schema": "corpus-cbwu/v1",
        "enabled": False,
    },
    "selector": {
        "schema": "corpus-selector/v1",
        "law": "direct-greedy-line-coverage",
        "tie_law": [
            "marginal-uncovered-worlds-desc",
            "p-line-desc",
            "mean-score-desc",
            "first-occurrence-asc",
        ],
        "fill_law": [
            "p-line-desc",
            "mean-score-desc",
            "first-occurrence-asc",
        ],
    },
    "line_194": {
        "schema": "corpus-line-threshold/v1",
        "line_dk": TAIL_LINE_DK,
        "comparison": "greater-than-or-equal",
    },
    "exact_80": {
        "schema": "corpus-exact-entry-count/v1",
        "entry_count": ENTRY_COUNT,
        "fail_if_unique_candidates_below_entry_count": True,
    },
}

SOURCE_COLUMN_ORDER: Final = (
    "id",
    "pos",
    "team",
    "opp",
    "game_id",
    "salary",
    "player_draws",
)
_FORBIDDEN_OUTCOME_FRAGMENTS: Final = (
    "actual",
    "contest_rank",
    "fantasy_points",
    "first_place",
    "outcome",
    "payout",
    "realized",
    "standings",
    "winner",
)
_SHA256: Final = re.compile(r"[0-9a-f]{64}")

_INVENTORY_TOP_LEVEL_KEYS: Final = frozenset({
    "classified_input_projection",
    "classified_input_projection_sha256",
    "complete_for_scope",
    "effective_policy",
    "forbidden_ambient_process_keys",
    "legal_feasibility_parameters",
    "rule_count",
    "rule_universe_sha256",
    "rules",
    "schema",
    "scope",
    "source_identities",
    "source_set_id",
    "source_set_sha256",
    "inventory_sha256",
})
_INVENTORY_RULE_KEYS: Final = frozenset({
    "baseline_state",
    "classification",
    "default_dose",
    "id",
    "label",
    "normalized_paths",
    "optional",
    "parametric_field",
    "source_locator_sha256",
    "source_locators",
    "stage",
})
_CLASSIFIED_INPUT_PROJECTION_KEYS: Final = frozenset({
    "ambient_process_keys_requiring_absence",
    "classification_counts",
    "direct_input_read_site_count",
    "input_count",
    "input_keys_sha256",
    "inputs",
})
_INPUT_CLASSIFICATIONS: Final = frozenset({
    "forbidden_ambient",
    "frozen_mechanism_input",
    "infrastructure_only",
    "typed_parametric_rule",
})


class CorpusLegalFeasibilityError(ValueError):
    """A fail-closed science-core contract violation."""


class InsufficientCandidateSupport(CorpusLegalFeasibilityError):
    """One or more variants generated fewer than exact-80 unique rosters."""


class SolverStatus(str, Enum):
    OPTIMAL = "optimal"
    INFEASIBLE = "infeasible"
    TIMEOUT = "timeout"
    ERROR = "error"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class SolverStageReceipt:
    stage: str
    status: SolverStatus
    pulp_status: int | None
    pulp_solution_status: int | None
    remaining_before_microseconds: int
    cbc_requested_microseconds: int | None
    host_watchdog_microseconds: int | None
    elapsed_microseconds: int
    remaining_after_microseconds: int
    objective_sha256: str
    witness_sha256: str | None
    log_sha256: str
    log_bytes: int
    raw_cbc_log: str = field(compare=False, repr=False)
    solution_sha256: str | None
    solution_bytes: int
    raw_cbc_solution: bytes = field(compare=False, repr=False)
    model_sha256: str | None
    model_bytes: int
    model_pre_exec_sha256: str | None
    model_post_exit_sha256: str | None
    model_regular_exclusive_inode: bool
    model_path_command_bound: bool
    raw_command_sha256: str | None
    exact_terminal_record: str | None
    warning_or_forbidden_marker_detected: bool
    solver_binary_sha256: str
    solver_options_sha256: str


@dataclass(frozen=True, slots=True)
class SolverProof:
    canonical_payload: bytes
    proof_sha256: str
    solver_authority_sha256: str
    total_deadline_seconds: int
    total_elapsed_microseconds: int
    timeout_law: str
    stages: tuple[SolverStageReceipt, ...]


@dataclass(frozen=True, slots=True)
class StackRuleDose:
    """All eight StackRules fields, never defaults or process state."""

    qb_stack_min: int
    bring_back_min: int
    forbid_rb_vs_dst: bool
    forbid_two_rb_same_team: bool
    qb_stack_max: int | None
    bring_back_max: int | None
    require_rb_vs_dst: bool
    require_two_rb_same_team: bool

    def as_stack_rules(self) -> StackRules:
        return StackRules(
            qb_stack_min=self.qb_stack_min,
            bring_back_min=self.bring_back_min,
            forbid_rb_vs_dst=self.forbid_rb_vs_dst,
            forbid_two_rb_same_team=self.forbid_two_rb_same_team,
            qb_stack_max=self.qb_stack_max,
            bring_back_max=self.bring_back_max,
            require_rb_vs_dst=self.require_rb_vs_dst,
            require_two_rb_same_team=self.require_two_rb_same_team,
        )

    def as_payload(self) -> dict[str, object]:
        return {
            "qb_stack_min": self.qb_stack_min,
            "bring_back_min": self.bring_back_min,
            "forbid_rb_vs_dst": self.forbid_rb_vs_dst,
            "forbid_two_rb_same_team": self.forbid_two_rb_same_team,
            "qb_stack_max": self.qb_stack_max,
            "bring_back_max": self.bring_back_max,
            "require_rb_vs_dst": self.require_rb_vs_dst,
            "require_two_rb_same_team": self.require_two_rb_same_team,
        }


@dataclass(frozen=True, slots=True)
class ConstraintDose:
    """The complete request-local shared-constraint call law."""

    budget: int
    locks: tuple[str, ...]
    bans: tuple[str, ...]
    banned_lineups: tuple[tuple[str, ...], ...]
    max_overlap: int
    punt_max_salary: int | None
    punt_min: int
    game_lock: tuple[str, int] | None
    min_salary: int
    max_salary: int | None
    max_per_game: int
    env: tuple[tuple[str, str], ...]

    def as_payload(self) -> dict[str, object]:
        return {
            "budget": self.budget,
            "locks": list(self.locks),
            "bans": list(self.bans),
            "banned_lineups": [list(row) for row in self.banned_lineups],
            "max_overlap": self.max_overlap,
            "punt_max_salary": self.punt_max_salary,
            "punt_min": self.punt_min,
            "game_lock": self.game_lock,
            "min_salary": self.min_salary,
            "max_salary": self.max_salary,
            "max_per_game": self.max_per_game,
            "env": dict(self.env),
        }


@dataclass(frozen=True, slots=True)
class EffectivePolicyProfile:
    ordinal: int
    parameter_set_id: str
    parameter_set_sha256: str
    parameter_values: tuple[tuple[str, object], ...]
    stack: StackRuleDose
    constraints: ConstraintDose

    def value(self, name: str) -> object:
        values = dict(self.parameter_values)
        if name not in values:
            raise CorpusLegalFeasibilityError(f"unknown policy field {name!r}")
        return values[name]

    def as_payload(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "parameter_set_id": self.parameter_set_id,
            "parameter_set_sha256": self.parameter_set_sha256,
            "parameter_values": dict(self.parameter_values),
            "stack_rules": self.stack.as_payload(),
            "shared_constraints": self.constraints.as_payload(),
        }


@dataclass(slots=True)
class FreshLegalModel:
    """One newly allocated problem; never shared across cells."""

    problem: pulp.LpProblem
    players: tuple[rw.PlayerSpec, ...]
    decision: dict[str, pulp.LpVariable]
    construction_serial: int


@dataclass(frozen=True, slots=True)
class SolveRequest:
    variant_ordinal: int
    parameter_set_id: str
    visit_ordinal: int
    world: rw.WorldId
    objective_micro: tuple[int, ...]
    timeout_seconds: int
    model: FreshLegalModel = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class SolveOutcome:
    status: SolverStatus
    roster: tuple[str, ...] | None = None
    primary_optimum_micro: int | None = None
    secondary_rank_sum: int | None = None
    lexicographic_radix: int | None = None
    combined_optimum: int | None = None
    solver_proof: SolverProof | None = field(
        default=None, compare=False, repr=False
    )
    detail: str = ""


@dataclass(frozen=True, slots=True)
class AttemptRecord:
    variant_ordinal: int
    parameter_set_id: str
    visit_ordinal: int
    world: rw.WorldId
    construction_serial: int
    status: SolverStatus
    roster: tuple[str, ...] | None
    primary_optimum_micro: int | None
    secondary_rank_sum: int | None
    lexicographic_radix: int | None
    combined_optimum: int | None
    solver_proof: SolverProof | None = field(compare=False, repr=False)
    detail: str


@dataclass(frozen=True, slots=True)
class RuntimePolicyBinding:
    canonical_payload: bytes
    runtime_policy_sha256: str
    inventory_sha256: str
    source_set_id: str
    source_set_sha256: str
    rule_universe_sha256: str
    rule_count: int
    classified_input_projection_sha256: str
    classified_input_runtime_proof_sha256: str
    experimental_rule_set_sha256: str
    dk_classic_feasibility_only: bool


@dataclass(frozen=True, slots=True)
class TaskSourceBinding:
    canonical_payload: bytes
    binding_sha256: str
    batch_manifest_sha256: str
    task_index: int
    task_sha256: str
    artifact_source_authority_completion_object_sha256: str
    artifact_source_authority_completion_sha256: str
    artifact_source_authority_task_sha256: str
    later_source_freeze_manifest_sha256: str
    world_artifact_receipt_set_sha256: str


@dataclass(frozen=True, slots=True)
class RegisteredLawBinding:
    canonical_payload: bytes
    binding_sha256: str
    common_law_sha256: str
    code_source_object_sha256: str
    code_source_body_sha256: str
    immutable_image_sha256: str
    runtime_image_terminal_verification_required: bool
    artifact_source_authority_completion_object_sha256: str
    artifact_source_authority_completion_sha256: str
    artifact_source_authority_task_sha256: str
    world_schedule_object_sha256: str
    visit_schedule_sha256: str
    solver_authority_sha256: str


@dataclass(frozen=True, slots=True)
class SolverEvidenceShard:
    global_shard_ordinal: int
    variant_ordinal: int
    variant_shard_ordinal: int
    visit_start: int
    visit_stop: int
    compressed_path: Path = field(compare=False, repr=False)
    compressed_sha256: str
    compressed_bytes: int
    compressed_device: int = field(compare=False, repr=False)
    compressed_inode: int = field(compare=False, repr=False)
    uncompressed_sha256: str
    uncompressed_bytes: int
    index_path: Path = field(compare=False, repr=False)
    index_sha256: str
    index_object_sha256: str
    index_bytes: int
    index_device: int = field(compare=False, repr=False)
    index_inode: int = field(compare=False, repr=False)
    shard_root_sha256: str


@dataclass(frozen=True, slots=True)
class _AuthoritativeSource:
    prepared: PreparedLaterSlate = field(compare=False, repr=False)
    binding: TaskSourceBinding


@dataclass(frozen=True, slots=True)
class _AuthoritativeInputs:
    request: Mapping[str, object] = field(compare=False, repr=False)
    manifest: Mapping[str, object] = field(compare=False, repr=False)
    inventory: Mapping[str, object] = field(compare=False, repr=False)
    source: _AuthoritativeSource
    law: RegisteredLawBinding
    ambient_process_keys_present: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class VariantGeneration:
    profile: EffectivePolicyProfile
    runtime_policy: RuntimePolicyBinding
    attempts: tuple[AttemptRecord, ...]
    visit_rosters: tuple[tuple[str, ...], ...]


@dataclass(frozen=True, slots=True)
class _SlateSnapshot:
    season: int
    week: int
    slate_id: str
    players: tuple[rw.PlayerSpec, ...]
    player_draws: np.ndarray = field(compare=False, repr=False)
    world_ids: tuple[rw.WorldId, ...]
    incumbent_candidates: tuple[tuple[str, ...], ...]
    source_freeze_sha256: str
    artifact_sha256_by_block: tuple[tuple[str, str], ...]


@dataclass(frozen=True, slots=True)
class GenerationMatrix:
    schema: str
    slate: _SlateSnapshot = field(compare=False, repr=False)
    source_columns: tuple[str, ...]
    visit_schedule: tuple[rw.WorldId, ...]
    visit_schedule_sha256: str
    visits_per_block: int
    timeout_seconds: int
    source_inventory_validator_applied: bool
    task_source_binding: TaskSourceBinding | None
    variants: tuple[VariantGeneration, ...]
    attempts: tuple[AttemptRecord, ...]
    registered_law: RegisteredLawBinding | None = None
    canonical_attempt_ledger_payload: bytes = b""
    attempt_ledger_sha256: str = ""
    canonical_matrix_authority_payload: bytes = b""
    matrix_authority_sha256: str = ""
    solver_evidence_shard_rows: tuple[tuple[str, object], ...] = ()
    solver_evidence_task_root_payload: bytes = b""
    solver_evidence_task_root_sha256: str = ""


@dataclass(frozen=True, slots=True)
class TestGenerationMatrix(GenerationMatrix):
    """Bounded callback-harness matrix; never an authority."""


@dataclass(frozen=True, slots=True)
class AuthoritativeGenerationMatrix(GenerationMatrix):
    """Raw-source/default-CBC matrix eligible for authoritative finalization."""


@dataclass(frozen=True, slots=True)
class ViolationCensus:
    unique_candidate_counts: tuple[tuple[str, int], ...]
    visit_counts: tuple[tuple[str, int], ...]
    selected_counts: tuple[tuple[str, int], ...]


@dataclass(frozen=True, slots=True)
class SelectorReceipt:
    candidate_count: int
    world_count: int
    entry_count: int
    tail_line_dk: float
    selected_indices: tuple[int, ...]
    tie_law_applied: str


@dataclass(frozen=True, slots=True)
class VariantScienceResult:
    profile: EffectivePolicyProfile
    runtime_policy: RuntimePolicyBinding
    attempts: tuple[AttemptRecord, ...]
    visit_rosters: tuple[tuple[str, ...], ...]
    unique_rosters: tuple[tuple[str, ...], ...]
    first_occurrence_visit_indices: tuple[int, ...]
    candidate_score_sha256: str
    selector: SelectorReceipt
    selected_rosters: tuple[tuple[str, ...], ...]
    selected_scores: np.ndarray = field(compare=False, repr=False)
    house_rule_census: ViolationCensus
    canonical_result_payload: bytes
    result_sha256: str


@dataclass(frozen=True, slots=True)
class BatchScienceResult:
    schema: str
    season: int
    week: int
    slate_id: str
    source_freeze_sha256: str
    artifact_sha256_by_block: tuple[tuple[str, str], ...]
    source_columns: tuple[str, ...]
    visit_schedule: tuple[rw.WorldId, ...]
    visit_schedule_sha256: str
    attempt_count: int
    matrix_cell_count: int
    variants: tuple[VariantScienceResult, ...]
    uses_realized_outcomes: bool
    historical_scoring_licensed: bool
    production_change_licensed: bool
    canonical_result_payload: bytes
    result_sha256: str


@dataclass(frozen=True, slots=True)
class DraftAuthorityBundle:
    schema: str
    source_binding_payload: bytes
    source_binding_sha256: str
    artifact_source_authority_completion_object_sha256: str
    artifact_source_authority_completion_sha256: str
    artifact_source_authority_task_sha256: str
    registered_law_payload: bytes
    registered_law_sha256: str
    runtime_policy_payloads: tuple[bytes, ...]
    attempt_ledger_payload: bytes
    attempt_ledger_sha256: str
    matrix_authority_payload: bytes
    matrix_authority_sha256: str
    solver_evidence_shards: tuple[SolverEvidenceShard, ...] = field(
        compare=False, repr=False
    )
    solver_evidence_task_root_payload: bytes
    solver_evidence_task_root_sha256: str
    variant_result_payloads: tuple[bytes, ...]
    batch_result_payload: bytes
    batch_result_sha256: str
    evidence_output_prefix: str
    canonical_draft_payload: bytes
    draft_sha256: str
    generation_matrix: AuthoritativeGenerationMatrix = field(
        compare=False, repr=False
    )
    result: BatchScienceResult = field(compare=False, repr=False)


@dataclass(frozen=True, slots=True)
class AuthorityBundle:
    schema: str
    draft: DraftAuthorityBundle = field(compare=False, repr=False)
    solver_evidence_object_identities: tuple[Mapping[str, object], ...]
    published_task_evidence_root_payload: bytes
    published_task_evidence_root_sha256: str
    canonical_bundle_payload: bytes
    bundle_sha256: str


class BatchExecutionError(CorpusLegalFeasibilityError):
    """All cells were attempted, but at least one did not prove optimal."""

    def __init__(
        self,
        attempts: Sequence[AttemptRecord],
        *,
        generation_matrix: GenerationMatrix | None = None,
        solver_evidence_shards: Sequence[SolverEvidenceShard] = (),
    ) -> None:
        self.attempts = tuple(attempts)
        self.generation_matrix = generation_matrix
        self.solver_evidence_shards = tuple(solver_evidence_shards)
        counts = Counter(attempt.status.value for attempt in self.attempts)
        failures = sum(
            count for status, count in counts.items()
            if status != SolverStatus.OPTIMAL.value
        )
        super().__init__(
            "solver matrix contains "
            f"{failures} non-optimal cells after all {len(self.attempts)} attempts; "
            f"status_counts={dict(sorted(counts.items()))}"
        )


class SolverCallback(Protocol):
    def __call__(self, request: SolveRequest) -> SolveOutcome: ...


InventoryValidator = Callable[
    [Mapping[str, object]], Mapping[str, object]
]


def canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusLegalFeasibilityError("value is not canonical JSON") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _parse_canonical_json_bytes(raw: bytes, *, label: str) -> object:
    if type(raw) is not bytes or not raw:
        raise CorpusLegalFeasibilityError(f"{label} must be nonempty raw bytes")
    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=lambda pairs: _duplicate_safe_object(pairs),
            parse_constant=lambda token: _reject_nonfinite_constant(token),
        )
    except CorpusLegalFeasibilityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusLegalFeasibilityError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    if canonical_json_bytes(value) != raw:
        raise CorpusLegalFeasibilityError(f"{label} is not canonical JSON")
    return value


def _validate_raw_object_identity(
    raw: bytes,
    identity: Mapping[str, object],
    *,
    label: str,
) -> dict[str, object]:
    item = _mapping(identity, label=f"{label} identity")
    if frozenset(item) != frozenset({"uri", "generation", "sha256", "bytes"}):
        raise CorpusLegalFeasibilityError(f"{label} identity fields differ")
    uri = _strict_string(item["uri"], label=f"{label} identity URI")
    generation = _strict_string(
        item["generation"], label=f"{label} identity generation"
    )
    digest = _strict_sha(item["sha256"], label=f"{label} identity SHA")
    size = _strict_int(item["bytes"], label=f"{label} identity bytes", minimum=1)
    if (
        not uri.startswith("gs://")
        or not generation.isdecimal()
        or generation.startswith("0")
        or type(raw) is not bytes
        or len(raw) != size
        or sha256(raw).hexdigest() != digest
    ):
        raise CorpusLegalFeasibilityError(f"{label} retained identity differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": size,
    }


@contextmanager
def _sealed_empty_evidence_directory(
    evidence_directory: Path,
) -> Iterator[tuple[Path, int]]:
    """Exclusively hold one real, initially empty task-evidence directory."""
    if not isinstance(evidence_directory, Path):
        raise CorpusLegalFeasibilityError(
            "evidence directory must be a pathlib Path"
        )
    if not evidence_directory.is_absolute():
        raise CorpusLegalFeasibilityError(
            "evidence directory must be an absolute canonical path"
        )
    try:
        resolved = evidence_directory.resolve(strict=True)
        before = os.lstat(evidence_directory)
    except (OSError, RuntimeError) as exc:
        raise CorpusLegalFeasibilityError(
            "evidence directory does not exist as a real directory"
        ) from exc
    if (
        resolved != evidence_directory
        or stat.S_ISLNK(before.st_mode)
        or not stat.S_ISDIR(before.st_mode)
        or not hasattr(os, "O_DIRECTORY")
        or not hasattr(os, "O_NOFOLLOW")
    ):
        raise CorpusLegalFeasibilityError(
            "evidence directory must be a canonical nonsymlink directory"
        )
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    try:
        directory_fd = os.open(evidence_directory, flags)
    except OSError as exc:
        raise CorpusLegalFeasibilityError(
            "evidence directory cannot be opened without following links"
        ) from exc
    locked = False
    try:
        opened = os.fstat(directory_fd)
        if (
            not stat.S_ISDIR(opened.st_mode)
            or (opened.st_dev, opened.st_ino)
            != (before.st_dev, before.st_ino)
        ):
            raise CorpusLegalFeasibilityError(
                "evidence directory identity changed while opening"
            )
        try:
            fcntl.flock(directory_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            locked = True
        except OSError as exc:
            raise CorpusLegalFeasibilityError(
                "evidence directory is already owned by another writer"
            ) from exc
        if os.listdir(directory_fd):
            raise CorpusLegalFeasibilityError(
                "evidence directory must be exactly empty at task start"
            )
        yield evidence_directory, directory_fd
        os.fsync(directory_fd)
    finally:
        if locked:
            fcntl.flock(directory_fd, fcntl.LOCK_UN)
        os.close(directory_fd)


def _write_create_once_evidence_file(
    raw: bytes,
    *,
    evidence_directory: Path,
    directory_fd: int,
    basename: str,
    maximum_bytes: int,
) -> tuple[Path, str, int, int, int]:
    """Write, fsync, reopen, and hash one exclusive regular evidence file."""
    if (
        type(raw) is not bytes
        or not raw
        or len(raw) > maximum_bytes
        or type(basename) is not str
        or not basename
        or Path(basename).name != basename
        or "/" in basename
        or "\0" in basename
    ):
        raise CorpusLegalFeasibilityError(
            "create-once evidence file request differs"
        )
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW
    try:
        file_fd = os.open(basename, flags, 0o600, dir_fd=directory_fd)
    except OSError as exc:
        raise CorpusLegalFeasibilityError(
            f"evidence file {basename!r} cannot be created exactly once"
        ) from exc
    try:
        opened = os.fstat(file_fd)
        if not stat.S_ISREG(opened.st_mode) or opened.st_nlink != 1:
            raise CorpusLegalFeasibilityError(
                "create-once evidence target is not one regular inode"
            )
        view = memoryview(raw)
        written = 0
        while written < len(view):
            count = os.write(file_fd, view[written:])
            if count <= 0:
                raise CorpusLegalFeasibilityError(
                    "create-once evidence write made no progress"
                )
            written += count
        os.fsync(file_fd)
        completed = os.fstat(file_fd)
        if (
            (completed.st_dev, completed.st_ino)
            != (opened.st_dev, opened.st_ino)
            or completed.st_nlink != 1
            or completed.st_size != len(raw)
        ):
            raise CorpusLegalFeasibilityError(
                "create-once evidence inode changed while writing"
            )
    finally:
        os.close(file_fd)
    os.fsync(directory_fd)
    path = evidence_directory / basename
    digest, size, device, inode = _hash_regular_evidence_file(
        path,
        expected_device=opened.st_dev,
        expected_inode=opened.st_ino,
        expected_size=len(raw),
        maximum_bytes=maximum_bytes,
    )
    expected_digest = sha256(raw).hexdigest()
    if digest != expected_digest:
        raise CorpusLegalFeasibilityError(
            "create-once evidence bytes changed on reopen"
        )
    return path, digest, size, device, inode


def _hash_regular_evidence_file(
    path: Path,
    *,
    expected_device: int,
    expected_inode: int,
    expected_size: int,
    maximum_bytes: int,
) -> tuple[str, int, int, int]:
    """Hash one bounded local evidence file without following its final link."""
    if (
        not isinstance(path, Path)
        or not path.is_absolute()
        or type(expected_device) is not int
        or type(expected_inode) is not int
        or type(expected_size) is not int
        or expected_size <= 0
        or expected_size > maximum_bytes
    ):
        raise CorpusLegalFeasibilityError(
            "local evidence descriptor differs"
        )
    try:
        file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise CorpusLegalFeasibilityError(
            "local evidence file cannot be reopened without following links"
        ) from exc
    try:
        before = os.fstat(file_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino)
            != (expected_device, expected_inode)
            or before.st_size != expected_size
        ):
            raise CorpusLegalFeasibilityError(
                "local evidence file identity differs"
            )
        digest = sha256()
        size = 0
        while True:
            chunk = os.read(file_fd, 1024 * 1024)
            if not chunk:
                break
            size += len(chunk)
            if size > expected_size or size > maximum_bytes:
                raise CorpusLegalFeasibilityError(
                    "local evidence file exceeds its retained bound"
                )
            digest.update(chunk)
        after = os.fstat(file_fd)
        if (
            size != expected_size
            or (after.st_dev, after.st_ino, after.st_size, after.st_nlink)
            != (before.st_dev, before.st_ino, before.st_size, before.st_nlink)
        ):
            raise CorpusLegalFeasibilityError(
                "local evidence file changed while hashing"
            )
        return digest.hexdigest(), size, before.st_dev, before.st_ino
    finally:
        os.close(file_fd)


def _read_regular_evidence_file(
    path: Path,
    *,
    expected_device: int,
    expected_inode: int,
    expected_size: int,
    maximum_bytes: int,
) -> bytes:
    """Read one bounded descriptor from one no-follow regular-file handle."""
    if expected_size <= 0 or expected_size > maximum_bytes:
        raise CorpusLegalFeasibilityError(
            "local evidence index descriptor differs"
        )
    try:
        file_fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise CorpusLegalFeasibilityError(
            "local evidence index cannot be opened without following links"
        ) from exc
    try:
        before = os.fstat(file_fd)
        if (
            not stat.S_ISREG(before.st_mode)
            or before.st_nlink != 1
            or (before.st_dev, before.st_ino)
            != (expected_device, expected_inode)
            or before.st_size != expected_size
        ):
            raise CorpusLegalFeasibilityError(
                "local evidence index identity differs"
            )
        chunks: list[bytes] = []
        size = 0
        while True:
            chunk = os.read(file_fd, min(1024 * 1024, expected_size - size + 1))
            if not chunk:
                break
            size += len(chunk)
            if size > expected_size or size > maximum_bytes:
                raise CorpusLegalFeasibilityError(
                    "local evidence index exceeds its retained bound"
                )
            chunks.append(chunk)
        after = os.fstat(file_fd)
        if (
            size != expected_size
            or (after.st_dev, after.st_ino, after.st_size, after.st_nlink)
            != (before.st_dev, before.st_ino, before.st_size, before.st_nlink)
        ):
            raise CorpusLegalFeasibilityError(
                "local evidence index changed while reading"
            )
        return b"".join(chunks)
    finally:
        os.close(file_fd)


def _validate_local_evidence_object_identity(
    path: Path,
    identity: Mapping[str, object],
    *,
    expected_sha256: str,
    expected_size: int,
    expected_device: int,
    expected_inode: int,
    maximum_bytes: int,
    label: str,
) -> dict[str, object]:
    """Bind one reopened local descriptor to a generation-pinned object."""
    item = _mapping(identity, label=f"{label} identity")
    if frozenset(item) != frozenset({"uri", "generation", "sha256", "bytes"}):
        raise CorpusLegalFeasibilityError(f"{label} identity fields differ")
    uri = _strict_string(item["uri"], label=f"{label} identity URI")
    generation = _strict_string(
        item["generation"], label=f"{label} identity generation"
    )
    digest = _strict_sha(item["sha256"], label=f"{label} identity SHA")
    size = _strict_int(
        item["bytes"], label=f"{label} identity bytes", minimum=1
    )
    local_digest, local_size, _, _ = _hash_regular_evidence_file(
        path,
        expected_device=expected_device,
        expected_inode=expected_inode,
        expected_size=expected_size,
        maximum_bytes=maximum_bytes,
    )
    if (
        not uri.startswith("gs://")
        or not generation.isdecimal()
        or generation.startswith("0")
        or digest != expected_sha256
        or size != expected_size
        or local_digest != digest
        or local_size != size
    ):
        raise CorpusLegalFeasibilityError(f"{label} retained identity differs")
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": size,
    }


def _strict_int(value: object, *, label: str, minimum: int | None = None) -> int:
    if type(value) is not int:
        raise CorpusLegalFeasibilityError(f"{label} must be an exact integer")
    if minimum is not None and value < minimum:
        raise CorpusLegalFeasibilityError(f"{label} must be >= {minimum}")
    return value


def _strict_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusLegalFeasibilityError(f"{label} must be a canonical string")
    return value


def _strict_sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CorpusLegalFeasibilityError(f"{label} must be lowercase SHA-256")
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusLegalFeasibilityError(f"{label} must be an object")
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CorpusLegalFeasibilityError(f"{label} must be an array")
    return value


def validate_outcome_blind_column_names(
    columns: Sequence[object],
) -> tuple[str, ...]:
    """Reject duplicated or outcome-bearing source-column declarations."""
    raw = _sequence(columns, label="source columns")
    result = tuple(
        _strict_string(value, label=f"source column[{index}]")
        for index, value in enumerate(raw)
    )
    if len(set(result)) != len(result):
        raise CorpusLegalFeasibilityError("source columns repeat")
    forbidden = sorted(
        column for column in result
        if any(fragment in column.casefold() for fragment in _FORBIDDEN_OUTCOME_FRAGMENTS)
    )
    if forbidden:
        raise CorpusLegalFeasibilityError(
            f"source columns contain forbidden outcome fields: {forbidden}"
        )
    return result


def _validate_inventory(
    value: Mapping[str, object],
    *,
    validator: InventoryValidator | None,
) -> dict[str, object]:
    candidate: Mapping[str, object] = value
    if validator is not None:
        validated = validator(value)
        if not isinstance(validated, Mapping):
            raise CorpusLegalFeasibilityError(
                "inventory validator did not return an object"
            )
        candidate = validated
    item = _mapping(candidate, label="effective-policy inventory")
    if frozenset(item) != _INVENTORY_TOP_LEVEL_KEYS:
        raise CorpusLegalFeasibilityError(
            "effective-policy inventory top-level fields differ"
        )
    if item["schema"] != INVENTORY_SCHEMA or item["complete_for_scope"] is not True:
        raise CorpusLegalFeasibilityError(
            "effective-policy inventory scope/schema differs"
        )
    body = {key: item[key] for key in item if key != "inventory_sha256"}
    inventory_sha = _strict_sha(
        item["inventory_sha256"], label="inventory.inventory_sha256"
    )
    if inventory_sha != inventory_canonical_sha256(body):
        raise CorpusLegalFeasibilityError("inventory self-hash differs")
    source_set_sha = _strict_sha(
        item["source_set_sha256"], label="inventory.source_set_sha256"
    )
    if source_set_sha != inventory_canonical_sha256(item["source_identities"]):
        raise CorpusLegalFeasibilityError("inventory source-set hash differs")
    _strict_string(item["source_set_id"], label="inventory.source_set_id")
    projection = _mapping(
        item["classified_input_projection"],
        label="inventory.classified_input_projection",
    )
    if frozenset(projection) != _CLASSIFIED_INPUT_PROJECTION_KEYS:
        raise CorpusLegalFeasibilityError(
            "inventory classified-input projection fields differ"
        )
    projection_sha = _strict_sha(
        item["classified_input_projection_sha256"],
        label="inventory.classified_input_projection_sha256",
    )
    if projection_sha != inventory_canonical_sha256(projection):
        raise CorpusLegalFeasibilityError(
            "inventory classified-input projection hash differs"
        )
    input_rows_raw = _sequence(
        projection["inputs"], label="classified-input projection.inputs"
    )
    input_rows = [
        _mapping(row, label=f"classified input[{index}]")
        for index, row in enumerate(input_rows_raw)
    ]
    input_keys = [
        _strict_string(row.get("input_key"), label="classified input key")
        for row in input_rows
    ]
    classifications = [
        _strict_string(
            row.get("classification"), label="classified input classification"
        )
        for row in input_rows
    ]
    if (
        not input_rows
        or input_keys != sorted(input_keys)
        or len(set(input_keys)) != len(input_keys)
        or any(value not in _INPUT_CLASSIFICATIONS for value in classifications)
        or projection["input_count"] != len(input_rows)
        or projection["input_keys_sha256"]
        != inventory_canonical_sha256(input_keys)
        or projection["direct_input_read_site_count"]
        != sum(int(row["direct_read_site_count"]) for row in input_rows)
        or projection["classification_counts"]
        != dict(sorted(Counter(classifications).items()))
    ):
        raise CorpusLegalFeasibilityError(
            "inventory classified-input projection topology differs"
        )
    required_absent = [
        str(row["input_key"]) for row in input_rows
        if row.get("ambient_process_requirement") == "absent"
    ]
    if projection["ambient_process_keys_requiring_absence"] != required_absent:
        raise CorpusLegalFeasibilityError(
            "inventory ambient-process absence projection differs"
        )
    rules_raw = _sequence(item["rules"], label="inventory.rules")
    rule_count = _strict_int(item["rule_count"], label="inventory.rule_count")
    if rule_count <= 0 or len(rules_raw) != rule_count:
        raise CorpusLegalFeasibilityError(
            "inventory rule count does not cover its complete rule universe"
        )
    rules: list[dict[str, object]] = []
    for index, raw in enumerate(rules_raw):
        row = _mapping(raw, label=f"inventory.rules[{index}]")
        if frozenset(row) != _INVENTORY_RULE_KEYS:
            raise CorpusLegalFeasibilityError(
                f"inventory rule[{index}] fields differ"
            )
        copied = dict(row)
        _strict_string(copied["id"], label=f"inventory rule[{index}].id")
        _strict_sha(
            copied["source_locator_sha256"],
            label=f"inventory rule[{index}].source_locator_sha256",
        )
        rules.append(copied)
    ids = [str(row["id"]) for row in rules]
    if ids != sorted(ids) or len(set(ids)) != len(ids):
        raise CorpusLegalFeasibilityError(
            "inventory rules are not unique canonical id order"
        )
    universe_projection = [{
        key: row[key] for key in (
            "baseline_state",
            "classification",
            "default_dose",
            "id",
            "normalized_paths",
            "optional",
            "parametric_field",
            "source_locator_sha256",
            "stage",
        )
    } for row in rules]
    universe_sha = _strict_sha(
        item["rule_universe_sha256"], label="inventory.rule_universe_sha256"
    )
    if universe_sha != inventory_canonical_sha256(universe_projection):
        raise CorpusLegalFeasibilityError("inventory rule-universe hash differs")
    expected_fields = {
        field: values[0] for field, values in PARAMETRIC_FIELDS.items()
    }
    observed_fields = {
        str(row["parametric_field"]): str(row["id"])
        for row in rules if row["parametric_field"] is not None
    }
    if observed_fields != expected_fields or set(observed_fields) != set(PARAMETER_ORDER):
        raise CorpusLegalFeasibilityError(
            "inventory parametric surface differs from the frozen five fields"
        )
    result = dict(item)
    result["rules"] = rules
    return result


def frozen_policy_profiles() -> tuple[EffectivePolicyProfile, ...]:
    """Map the frozen seven assignments to fully explicit optimizer doses."""
    profiles: list[EffectivePolicyProfile] = []
    for expected_ordinal, parameter_set in enumerate(frozen_parameter_sets()):
        frozen = validate_parameter_set(parameter_set)
        if (
            frozen["ordinal"] != expected_ordinal
            or frozen["parameter_set_id"] != PARAMETER_SET_ORDER[expected_ordinal]
        ):
            raise CorpusLegalFeasibilityError("frozen parameter-set order differs")
        values = frozen["values"]
        stack = StackRuleDose(
            qb_stack_min=int(values["qb_stack_min"]),
            bring_back_min=int(values["bring_back_min"]),
            forbid_rb_vs_dst=bool(values["forbid_rb_vs_dst"]),
            forbid_two_rb_same_team=bool(values["forbid_two_rb_same_team"]),
            qb_stack_max=None,
            bring_back_max=None,
            require_rb_vs_dst=False,
            require_two_rb_same_team=False,
        )
        constraints = ConstraintDose(
            budget=rw.SALARY_CAP,
            locks=(),
            bans=(),
            banned_lineups=(),
            max_overlap=rw.ROSTER_SIZE - 1,
            punt_max_salary=None,
            punt_min=0,
            game_lock=None,
            min_salary=int(values["min_lineup_salary"]),
            max_salary=None,
            max_per_game=0,
            env=(),
        )
        profiles.append(EffectivePolicyProfile(
            ordinal=expected_ordinal,
            parameter_set_id=str(frozen["parameter_set_id"]),
            parameter_set_sha256=str(frozen["parameter_set_sha256"]),
            parameter_values=tuple(
                (name, values[name]) for name in PARAMETER_ORDER
            ),
            stack=stack,
            constraints=constraints,
        ))
    return tuple(profiles)


def _runtime_operation(
    row: Mapping[str, object], profile: EffectivePolicyProfile,
) -> tuple[object, str, str, str, str]:
    field_name = row["parametric_field"]
    baseline_state = str(row["baseline_state"])
    if field_name is not None:
        effective = profile.value(str(field_name))
        baseline = row["default_dose"]
        if type(effective) is not type(baseline):
            raise CorpusLegalFeasibilityError(
                f"runtime policy type differs for {field_name}"
            )
        if effective == baseline:
            return (
                effective,
                "active",
                "retained-baseline",
                "applied",
                "enforced-request-local",
            )
        return (
            effective,
            "inactive",
            "removed-by-parameter-assignment",
            "disabled",
            "disabled-by-parameter-assignment",
        )
    classification = str(row["classification"])
    rule_id = str(row["id"])
    stage = str(row["stage"])
    if classification == "dk_hard":
        return (
            row["default_dose"],
            baseline_state,
            "frozen-baseline",
            "applied",
            "enforced-request-local",
        )
    if rule_id in {"rule:first-producer-dedup-order", "rule:selector-line194"}:
        return (
            row["default_dose"],
            baseline_state,
            "frozen-baseline",
            "applied",
            "retained-request-local",
        )
    if stage == "simulation":
        if baseline_state == "active":
            return (
                row["default_dose"],
                "active",
                "frozen-baseline",
                "upstream_frozen",
                "frozen-upstream-retained",
            )
        return (
            None,
            "inactive",
            "nonoperative-baseline",
            "not_applicable",
            "nonoperative-baseline",
        )
    if baseline_state == "inactive":
        return (
            None,
            "inactive",
            "nonoperative-baseline",
            "not_applicable",
            "nonoperative-baseline",
        )
    return (
        None,
        "inactive",
        "bypassed-experimental-path",
        "not_applicable",
        "nonoperative-bypassed-path",
    )


def _experimental_rule_projection(
    *, visits_per_block: int, visit_schedule_sha256: str,
) -> list[dict[str, object]]:
    count = _strict_int(
        visits_per_block, label="experimental visits_per_block", minimum=1
    )
    if count > rw.WORLDS_PER_BLOCK:
        raise CorpusLegalFeasibilityError(
            "experimental visits_per_block exceeds retained block worlds"
        )
    schedule_sha = _strict_sha(
        visit_schedule_sha256, label="experimental visit-schedule SHA"
    )
    return [
        {
            "id": "experimental:matched-fixed-world-schedule",
            "application": "applied",
            "dose": {
                "blocks": list(rw.WORLD_BLOCKS),
                "order": "block-then-ranked-world",
                "ranking": "total-slate-player-draw-desc",
                "ranking_accumulator": "float64",
                "ranking_tie": "world-index-ascending-stable",
                "source_worlds_per_block": rw.WORLDS_PER_BLOCK,
                "visits_per_block": count,
                "visit_schedule_sha256": schedule_sha,
            },
        },
        {
            "id": "experimental:one-world-optimum-per-visit",
            "application": "applied",
            "dose": {
                "objective": "exact-lexicographic-primary-micro-dk-then-stable-rank",
                "solver_stages": [
                    "lexicographic-combined-optimum",
                    "combined-optimum-collision-proof",
                ],
                "fresh_model_per_variant_visit": True,
                "every_visit_attempted": True,
            },
        },
        {
            "id": "experimental:no-production-generation-recipes",
            "application": "applied",
            "dose": {
                "candidate_family_injection": False,
                "no_good_feedback_between_visits": False,
                "engine_or_tail_select_lineups": False,
            },
        },
        {
            "id": "experimental:first-occurrence-unique-union",
            "application": "applied",
            "dose": {
                "identity": "canonical-sorted-nine-player-ids",
                "order": "first-visit-occurrence",
                "candidate_truncation": False,
                "maximum_visit_outputs_before_deduplication": (
                    len(rw.WORLD_BLOCKS) * count
                ),
            },
        },
        {
            "id": "experimental:common-full-world-cross-score",
            "application": "applied",
            "dose": {
                "world_count": EXPECTED_WORLD_COUNT,
                "same_world_matrix_all_variants": True,
            },
        },
        {
            "id": "experimental:direct-exact80-line194-selector",
            "application": "applied",
            "dose": {
                "admission": "full-unique-union",
                "cbwu": False,
                "entries": ENTRY_COUNT,
                "line_dk": TAIL_LINE_DK,
                "tie_order": [
                    "marginal-uncovered-worlds-desc",
                    "p-line-desc",
                    "mean-score-desc",
                    "first-occurrence-asc",
                ],
            },
        },
    ]


def _classified_input_runtime_proof(
    projection: Mapping[str, object],
    profile: EffectivePolicyProfile,
    *,
    ambient_process_keys_present: Sequence[str],
) -> dict[str, object]:
    rows = [
        _mapping(row, label="classified-input runtime row")
        for row in _sequence(projection["inputs"], label="classified inputs")
    ]
    by_classification: dict[str, list[Mapping[str, object]]] = {
        classification: [
            row for row in rows
            if row["classification"] == classification
        ]
        for classification in _INPUT_CLASSIFICATIONS
    }
    typed_input_by_field = {
        "min_lineup_salary": "MIN_LINEUP_SALARY",
        "qb_stack_min": "STACK_QB_MIN",
        "bring_back_min": "STACK_BRING_BACK",
        "forbid_rb_vs_dst": "FORBID_RB_DST",
        "forbid_two_rb_same_team": None,
    }
    inventory_typed_keys = {
        str(row["input_key"])
        for row in by_classification["typed_parametric_rule"]
    }
    expected_inventory_typed = {
        key for key in typed_input_by_field.values() if key is not None
    }
    if inventory_typed_keys != expected_inventory_typed:
        raise CorpusLegalFeasibilityError(
            "classified-input typed parameter projection differs"
        )
    typed_parameters = [{
        "field": field_name,
        "value": profile.value(field_name),
        "inventory_input_key": typed_input_by_field[field_name],
        "delivery": (
            "explicit-shared-constraint-argument"
            if field_name == "min_lineup_salary"
            else "explicit-stack-rules-field"
        ),
        "request_local": True,
        "ambient_process_state": "absent",
    } for field_name in PARAMETER_ORDER]
    frozen_mechanisms = [{
        "input_key": row["input_key"],
        "inventory_row_sha256": inventory_canonical_sha256(row),
        "baseline_effective_policy": row["baseline_effective_policy"],
        "request_mapping_requirement": row["request_mapping_requirement"],
        "runtime_application": "frozen-in-retained-law-or-not-consulted",
        "mutated_by_variant": False,
    } for row in by_classification["frozen_mechanism_input"]]
    infrastructure = [{
        "input_key": row["input_key"],
        "inventory_row_sha256": inventory_canonical_sha256(row),
        "science_application": "not_inherited",
    } for row in by_classification["infrastructure_only"]]
    ambient_required = list(
        projection["ambient_process_keys_requiring_absence"]
    )
    present = tuple(
        _strict_string(value, label="present ambient process key")
        for value in ambient_process_keys_present
    )
    if (
        present != tuple(sorted(set(present)))
        or not set(present) <= set(ambient_required)
    ):
        raise CorpusLegalFeasibilityError(
            "observed ambient process-key projection differs"
        )
    return {
        "typed_request_local_parameters": typed_parameters,
        "typed_request_local_parameter_count": len(typed_parameters),
        "frozen_mechanism_inputs": frozen_mechanisms,
        "frozen_mechanism_input_count": len(frozen_mechanisms),
        "infrastructure_inputs": infrastructure,
        "infrastructure_input_count": len(infrastructure),
        "infrastructure_inherited_as_science": False,
        "ambient_score_relevant_keys_requiring_absence": ambient_required,
        "ambient_score_relevant_key_count": len(ambient_required),
        "ambient_score_relevant_keys_present_in_semantic_input": list(present),
        "ambient_score_relevant_keys_present_sha256": canonical_sha256(
            list(present)
        ),
        "all_ambient_score_relevant_semantic_inputs_absent": not present,
        "worker_environment_inherited": False,
    }


def build_runtime_effective_policy(
    inventory: Mapping[str, object],
    profile: EffectivePolicyProfile,
    *,
    visits_per_block: int,
    visit_schedule_sha256: str,
    ambient_process_keys_present: Sequence[str],
    inventory_validator: InventoryValidator | None = None,
) -> RuntimePolicyBinding:
    """Bind every source-inventory row to one request-local assignment."""
    frozen = _validate_inventory(inventory, validator=inventory_validator)
    rows: list[dict[str, object]] = []
    for row in frozen["rules"]:
        (
            effective_dose,
            effective_state,
            relation,
            application,
            operation,
        ) = _runtime_operation(row, profile)
        rows.append({
            "application": application,
            "baseline_state": row["baseline_state"],
            "classification": row["classification"],
            "default_dose": row["default_dose"],
            "dose_relation": relation,
            "effective_dose": effective_dose,
            "effective_state": effective_state,
            "id": row["id"],
            "inventory_row_sha256": inventory_canonical_sha256(row),
            "normalized_paths": row["normalized_paths"],
            "operation": operation,
            "parametric_field": row["parametric_field"],
            "source_locator_sha256": row["source_locator_sha256"],
            "stage": row["stage"],
        })
    experimental_rules = _experimental_rule_projection(
        visits_per_block=visits_per_block,
        visit_schedule_sha256=visit_schedule_sha256,
    )
    experimental_rule_set_sha = canonical_sha256(experimental_rules)
    classified_input_projection = frozen["classified_input_projection"]
    classified_input_projection_sha = str(
        frozen["classified_input_projection_sha256"]
    )
    classified_input_runtime_proof = _classified_input_runtime_proof(
        classified_input_projection,
        profile,
        ambient_process_keys_present=ambient_process_keys_present,
    )
    classified_input_runtime_proof_sha = canonical_sha256(
        classified_input_runtime_proof
    )
    # Derive the label only after the complete runtime row projection exists.
    # The neutral parameter-set id alone is never evidence of DK-only status.
    parametric_rows = {
        str(row["parametric_field"]): row
        for row in rows if row["parametric_field"] is not None
    }
    dk_rows = [row for row in rows if row["classification"] == "dk_hard"]
    other_house_rows = [
        row for row in rows
        if row["classification"] == "house_soft"
        and row["parametric_field"] is None
    ]
    dk_classic_feasibility_only = (
        set(parametric_rows) == set(PARAMETER_ORDER)
        and all(
            parametric_rows[name]["effective_dose"] in (0, False)
            and parametric_rows[name]["operation"]
            == "disabled-by-parameter-assignment"
            for name in PARAMETER_ORDER
        )
        and bool(dk_rows)
        and all(row["operation"] == "enforced-request-local" for row in dk_rows)
        and all(
            row["application"] == "not_applicable"
            and row["effective_state"] == "inactive"
            and row["effective_dose"] is None
            for row in other_house_rows
        )
        and classified_input_runtime_proof[
            "all_ambient_score_relevant_semantic_inputs_absent"
        ] is True
    )
    payload: dict[str, object] = {
        "schema": RUNTIME_POLICY_SCHEMA,
        "inventory_sha256": frozen["inventory_sha256"],
        "source_set_id": frozen["source_set_id"],
        "source_set_sha256": frozen["source_set_sha256"],
        "rule_universe_sha256": frozen["rule_universe_sha256"],
        "rule_count": len(rows),
        "classified_input_projection": classified_input_projection,
        "classified_input_projection_sha256": (
            classified_input_projection_sha
        ),
        "classified_input_runtime_proof": classified_input_runtime_proof,
        "classified_input_runtime_proof_sha256": (
            classified_input_runtime_proof_sha
        ),
        "experimental_rules": experimental_rules,
        "experimental_rule_set_sha256": experimental_rule_set_sha,
        "dk_classic_feasibility_only": dk_classic_feasibility_only,
        "parameter_set": profile.as_payload(),
        "rules": rows,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "worker_environment_inherited": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    raw = canonical_json_bytes(payload)
    return RuntimePolicyBinding(
        canonical_payload=raw,
        runtime_policy_sha256=sha256(raw).hexdigest(),
        inventory_sha256=str(frozen["inventory_sha256"]),
        source_set_id=str(frozen["source_set_id"]),
        source_set_sha256=str(frozen["source_set_sha256"]),
        rule_universe_sha256=str(frozen["rule_universe_sha256"]),
        rule_count=len(rows),
        classified_input_projection_sha256=classified_input_projection_sha,
        classified_input_runtime_proof_sha256=(
            classified_input_runtime_proof_sha
        ),
        experimental_rule_set_sha256=experimental_rule_set_sha,
        dk_classic_feasibility_only=dk_classic_feasibility_only,
    )


def validate_runtime_effective_policy(
    binding: RuntimePolicyBinding,
    inventory: Mapping[str, object],
    profile: EffectivePolicyProfile,
    *,
    visits_per_block: int,
    visit_schedule_sha256: str,
    ambient_process_keys_present: Sequence[str],
    inventory_validator: InventoryValidator | None = None,
) -> RuntimePolicyBinding:
    if not isinstance(binding, RuntimePolicyBinding):
        raise CorpusLegalFeasibilityError("runtime policy binding type differs")
    try:
        parsed = json.loads(
            binding.canonical_payload.decode("utf-8"),
            object_pairs_hook=lambda pairs: _duplicate_safe_object(pairs),
            parse_constant=lambda value: _reject_nonfinite_constant(value),
        )
    except CorpusLegalFeasibilityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusLegalFeasibilityError(
            "runtime policy payload is not valid JSON"
        ) from exc
    if canonical_json_bytes(parsed) != binding.canonical_payload:
        raise CorpusLegalFeasibilityError("runtime policy payload is not canonical")
    rebuilt = build_runtime_effective_policy(
        inventory,
        profile,
        visits_per_block=visits_per_block,
        visit_schedule_sha256=visit_schedule_sha256,
        ambient_process_keys_present=ambient_process_keys_present,
        inventory_validator=inventory_validator,
    )
    if binding != rebuilt:
        raise CorpusLegalFeasibilityError(
            "runtime policy does not replay against every inventory row"
        )
    return rebuilt


def _duplicate_safe_object(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusLegalFeasibilityError(
                f"canonical payload repeats key {key!r}"
            )
        result[key] = value
    return result


def _reject_nonfinite_constant(value: str) -> object:
    raise CorpusLegalFeasibilityError(
        f"canonical payload contains non-finite value {value}"
    )


def audit_dk_classic(
    players: Sequence[rw.PlayerSpec], roster: Sequence[object],
) -> tuple[str, ...]:
    """Independent DK Classic hard-rule audit (no house feasibility rules)."""
    if isinstance(roster, (str, bytes)) or not isinstance(roster, Sequence):
        raise CorpusLegalFeasibilityError("roster must be one id sequence")
    identity = tuple(
        _strict_string(value, label="roster player id") for value in roster
    )
    if identity != tuple(sorted(identity)):
        raise CorpusLegalFeasibilityError("roster ids must be canonical sorted")
    if len(identity) != rw.ROSTER_SIZE or len(set(identity)) != rw.ROSTER_SIZE:
        raise CorpusLegalFeasibilityError("roster must contain nine unique ids")
    by_id = {player.player_id: player for player in players}
    if len(by_id) != len(players) or not set(identity) <= set(by_id):
        raise CorpusLegalFeasibilityError("roster player universe differs")
    chosen = [by_id[player_id] for player_id in identity]
    counts = Counter(player.position for player in chosen)
    if not (
        counts == Counter({
            "QB": 1,
            "RB": counts["RB"],
            "WR": counts["WR"],
            "TE": counts["TE"],
            "DST": 1,
        })
        and 2 <= counts["RB"] <= 3
        and 3 <= counts["WR"] <= 4
        and 1 <= counts["TE"] <= 2
        and sum(counts.values()) == rw.ROSTER_SIZE
    ):
        raise CorpusLegalFeasibilityError("roster DK position shape differs")
    salary = sum(player.salary for player in chosen)
    if not 0 < salary <= rw.SALARY_CAP:
        raise CorpusLegalFeasibilityError("roster DK salary cap differs")
    if max(Counter(player.team for player in chosen).values()) > rw.MAX_FROM_TEAM:
        raise CorpusLegalFeasibilityError("roster DK team cap differs")
    if len({player.game_id for player in chosen}) < rw.MIN_GAMES:
        raise CorpusLegalFeasibilityError("roster DK minimum-games rule differs")
    return identity


def house_rule_violations(
    players: Sequence[rw.PlayerSpec], roster: Sequence[object],
) -> tuple[str, ...]:
    identity = audit_dk_classic(players, roster)
    by_id = {player.player_id: player for player in players}
    chosen = [by_id[player_id] for player_id in identity]
    qb = next(player for player in chosen if player.position == "QB")
    dst = next(player for player in chosen if player.position == "DST")
    violations: list[str] = []
    if sum(player.salary for player in chosen) < 49_000:
        violations.append("min_lineup_salary")
    same_team_catchers = sum(
        player.team == qb.team and player.position in {"WR", "TE"}
        for player in chosen
    )
    if same_team_catchers < 2:
        violations.append("qb_stack_min")
    bring_backs = sum(
        player.team == qb.opponent and player.position in {"RB", "WR", "TE"}
        for player in chosen
    )
    if bring_backs < 1:
        violations.append("bring_back_min")
    if any(
        player.position == "RB" and player.team == dst.opponent
        for player in chosen
    ):
        violations.append("forbid_rb_vs_dst")
    rb_teams = [player.team for player in chosen if player.position == "RB"]
    if len(rb_teams) != len(set(rb_teams)):
        violations.append("forbid_two_rb_same_team")
    return tuple(
        field_name for field_name in PARAMETER_ORDER if field_name in violations
    )


def _audit_profile_compliance(
    players: Sequence[rw.PlayerSpec],
    roster: tuple[str, ...],
    profile: EffectivePolicyProfile,
) -> tuple[str, ...]:
    violations = house_rule_violations(players, roster)
    prohibited = tuple(
        name for name in violations
        if profile.value(name) not in (0, False)
    )
    if prohibited:
        raise CorpusLegalFeasibilityError(
            f"solver roster violates active profile rules: {prohibited}"
        )
    return violations


def _validate_prepared_slate(prepared: PreparedLaterSlate) -> _SlateSnapshot:
    if type(prepared) is not PreparedLaterSlate:
        raise CorpusLegalFeasibilityError(
            "science input must be one exact PreparedLaterSlate"
        )
    season = _strict_int(prepared.season, label="prepared season", minimum=1)
    week = _strict_int(prepared.week, label="prepared week", minimum=1)
    slate_id = _strict_string(prepared.slate_id, label="prepared slate id")
    if type(prepared.players) is not tuple or len(prepared.players) < rw.ROSTER_SIZE:
        raise CorpusLegalFeasibilityError("prepared player catalog differs")
    if any(type(player) is not rw.PlayerSpec for player in prepared.players):
        raise CorpusLegalFeasibilityError("prepared player row type differs")
    player_ids = [player.player_id for player in prepared.players]
    if len(set(player_ids)) != len(player_ids):
        raise CorpusLegalFeasibilityError("prepared player ids repeat")
    draws = prepared.player_draws
    if (
        type(draws) is not np.ndarray
        or draws.dtype != np.dtype(np.float32)
        or draws.ndim != 2
        or draws.shape != (len(prepared.players), EXPECTED_WORLD_COUNT)
        or not draws.flags.c_contiguous
        or draws.flags.writeable
        or not np.isfinite(draws).all()
    ):
        raise CorpusLegalFeasibilityError(
            "prepared player-draw matrix must be finite read-only C float32 "
            "players x 50,000"
        )
    if type(prepared.world_ids) is not tuple or len(prepared.world_ids) != EXPECTED_WORLD_COUNT:
        raise CorpusLegalFeasibilityError("prepared world-id lattice differs")
    for flat_index, world in enumerate(prepared.world_ids):
        expected = rw.WorldId(
            rw.WORLD_BLOCKS[flat_index // rw.WORLDS_PER_BLOCK],
            flat_index % rw.WORLDS_PER_BLOCK,
        )
        if type(world) is not rw.WorldId or world != expected:
            raise CorpusLegalFeasibilityError(
                "prepared worlds must be canonical R0..R4 x 0..9999"
            )
    order = np.argsort(np.asarray(player_ids, dtype=str), kind="stable")
    players = tuple(prepared.players[int(index)] for index in order)
    copied_draws = np.ascontiguousarray(draws[order], dtype=np.float32)
    copied_draws.flags.writeable = False
    incumbents_raw = prepared.incumbent_candidates
    if type(incumbents_raw) is not tuple:
        raise CorpusLegalFeasibilityError("prepared incumbent candidates differ")
    incumbents: list[tuple[str, ...]] = []
    for roster in incumbents_raw:
        incumbents.append(audit_dk_classic(players, roster))
    if len(set(incumbents)) != len(incumbents):
        raise CorpusLegalFeasibilityError("prepared incumbent candidates repeat")
    source_sha = _strict_sha(
        prepared.source_freeze_sha256, label="prepared source-freeze SHA"
    )
    artifacts = prepared.artifact_sha256_by_block
    if not isinstance(artifacts, Mapping) or set(artifacts) != set(rw.WORLD_BLOCKS):
        raise CorpusLegalFeasibilityError("prepared artifact block map differs")
    artifact_rows = tuple(
        (
            block,
            _strict_sha(artifacts[block], label=f"prepared artifact {block} SHA"),
        )
        for block in rw.WORLD_BLOCKS
    )
    return _SlateSnapshot(
        season=season,
        week=week,
        slate_id=slate_id,
        players=players,
        player_draws=copied_draws,
        world_ids=tuple(prepared.world_ids),
        incumbent_candidates=tuple(incumbents),
        source_freeze_sha256=source_sha,
        artifact_sha256_by_block=artifact_rows,
    )


def _matrix_content_sha256(matrix: np.ndarray) -> str:
    array = np.ascontiguousarray(matrix, dtype="<f4")
    header = canonical_json_bytes({
        "dtype": "float32-le", "shape": list(array.shape),
    })
    digest = sha256()
    digest.update(header)
    digest.update(b"\0")
    digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def _load_authoritative_source(
    *,
    batch_manifest: Mapping[str, object],
    task_index: int,
    artifact_source_authority_completion_bytes: bytes,
    retained_source_freeze_bytes: bytes,
    retained_world_artifact_bodies: Mapping[str, bytes],
) -> _AuthoritativeSource:
    """Build the sole authoritative PreparedLaterSlate from retained bytes."""
    try:
        manifest = validate_batch_manifest(batch_manifest)
    except ValueError as exc:
        raise CorpusLegalFeasibilityError(
            "batch manifest failed source validation"
        ) from exc
    index = _strict_int(task_index, label="source task index", minimum=0)
    if index >= len(manifest["tasks"]):
        raise CorpusLegalFeasibilityError("source task index is outside batch")
    task = manifest["tasks"][index]
    common = manifest["common_law"]
    common_source = common["source_receipts"]["later_source_freeze"]
    completion_identity = _mapping(
        common.get("artifact_source_authority_completion"),
        label="artifact source-authority completion identity",
    )
    normalized_completion_identity = _validate_raw_object_identity(
        artifact_source_authority_completion_bytes,
        completion_identity,
        label="artifact source-authority completion",
    )
    completion_internal_sha = _strict_sha(
        common.get("artifact_source_authority_completion_sha256"),
        label="artifact source-authority completion internal SHA",
    )
    if completion_internal_sha == normalized_completion_identity["sha256"]:
        raise CorpusLegalFeasibilityError(
            "artifact source-authority object/internal hashes are conflated"
        )
    try:
        completion = validate_artifact_source_completion_bytes(
            artifact_source_authority_completion_bytes
        )
    except CorpusArtifactSourceAuthorityError as exc:
        raise CorpusLegalFeasibilityError(
            "artifact source-authority completion failed strict replay"
        ) from exc
    authority_tasks = _sequence(
        completion.get("tasks"), label="artifact source-authority tasks"
    )
    if index >= len(authority_tasks):
        raise CorpusLegalFeasibilityError(
            "artifact source-authority task row is absent"
        )
    authority_task = _mapping(
        authority_tasks[index],
        label=f"artifact source-authority task[{index}]",
    )
    task_authority_sha = _strict_sha(
        task.get("artifact_source_authority_task_sha256"),
        label="manifest artifact source-authority task SHA",
    )
    manifest_sha = _strict_sha(
        common.get("later_source_freeze_manifest_sha256"),
        label="later-source freeze manifest SHA",
    )
    if (
        completion.get("completion_sha256") != completion_internal_sha
        or completion.get("authority_scope")
        != ARTIFACT_SOURCE_UNIVERSE_SCOPE
        or completion.get("later_source_freeze_object") != common_source
        or completion.get("later_source_freeze_manifest_sha256")
        != manifest_sha
        or authority_task.get("task_index") != index
        or authority_task.get("season") != task["season"]
        or authority_task.get("week") != task["week"]
        or authority_task.get("slate_id") != task["slate_id"]
        or authority_task.get("universe_scope")
        != ARTIFACT_SOURCE_UNIVERSE_SCOPE
        or authority_task.get("task_source_authority_sha256")
        != task_authority_sha
        or authority_task.get("later_source_freeze_manifest_sha256")
        != manifest_sha
        or authority_task.get("world_artifact_receipts")
        != task["world_artifact_receipts"]
        or authority_task.get("world_artifact_receipt_set_sha256")
        != task["world_artifact_receipt_set_sha256"]
    ):
        raise CorpusLegalFeasibilityError(
            "artifact source-authority completion/task binding differs"
        )
    if type(retained_source_freeze_bytes) is not bytes or (
        len(retained_source_freeze_bytes) != common_source["bytes"]
        or sha256(retained_source_freeze_bytes).hexdigest()
        != common_source["sha256"]
    ):
        raise CorpusLegalFeasibilityError(
            "later-source freeze retained-object identity differs"
        )
    try:
        source_body = json.loads(
            retained_source_freeze_bytes.decode("utf-8"),
            object_pairs_hook=lambda pairs: _duplicate_safe_object(pairs),
            parse_constant=lambda value: _reject_nonfinite_constant(value),
        )
    except CorpusLegalFeasibilityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusLegalFeasibilityError(
            "later-source freeze bytes are not valid JSON"
        ) from exc
    if later_source_canonical_json(source_body) != retained_source_freeze_bytes:
        raise CorpusLegalFeasibilityError(
            "later-source freeze retained bytes are not canonical"
        )
    try:
        source_freeze = validate_source_freeze(
            source_body, expected_freeze_sha256=manifest_sha
        )
    except LR8LaterSourceError as exc:
        raise CorpusLegalFeasibilityError(
            "later-source freeze internal manifest failed replay"
        ) from exc
    matching = [
        row for row in source_freeze["slates"]
        if (row["season"], row["week"], row["slate_id"])
        == (task["season"], task["week"], task["slate_id"])
    ]
    if len(matching) != 1:
        raise CorpusLegalFeasibilityError(
            "later-source freeze does not contain exactly one task slate"
        )
    source_row = matching[0]
    if (
        authority_task.get("catalog_sha256")
        != source_row["catalog_sha256"]
        or authority_task.get("incumbent_candidates_sha256")
        != source_row["incumbent_candidates_sha256"]
    ):
        raise CorpusLegalFeasibilityError(
            "artifact source-authority task differs from later-source slate"
        )
    if (
        not isinstance(retained_world_artifact_bodies, Mapping)
        or set(retained_world_artifact_bodies) != set(TASK_WORLD_SOURCE_ROLES)
    ):
        raise CorpusLegalFeasibilityError(
            "world-artifact retained-body roles differ"
        )
    task_identities = task["world_artifact_receipts"]
    replayed: dict[str, dict[str, object]] = {}
    bodies_by_block: dict[str, bytes] = {}
    for block, role, source_receipt in zip(
        rw.WORLD_BLOCKS,
        TASK_WORLD_SOURCE_ROLES,
        source_row["artifact_receipts"],
        strict=True,
    ):
        source_identity = {
            key: source_receipt[key]
            for key in ("uri", "generation", "sha256", "bytes")
        }
        task_identity = dict(task_identities[role])
        retained = retained_world_artifact_bodies[role]
        if source_identity != task_identity or type(retained) is not bytes or (
            len(retained) != task_identity["bytes"]
            or sha256(retained).hexdigest() != task_identity["sha256"]
        ):
            raise CorpusLegalFeasibilityError(
                f"{role} source/task/body content identity differs"
            )
        replayed[role] = task_identity
        bodies_by_block[block] = retained
    artifact_set_sha = str(task["world_artifact_receipt_set_sha256"])
    if artifact_set_sha != batch_canonical_sha256(replayed):
        raise CorpusLegalFeasibilityError(
            "world-artifact receipt-set hash differs"
        )
    try:
        prepared = prepare_later_slate(
            source_freeze,
            expected_source_freeze_sha256=manifest_sha,
            season=int(task["season"]),
            week=int(task["week"]),
            artifact_bodies=bodies_by_block,
        )
    except LR8LaterSourceError as exc:
        raise CorpusLegalFeasibilityError(
            "retained sources cannot construct PreparedLaterSlate"
        ) from exc
    snapshot = _validate_prepared_slate(prepared)
    if (
        snapshot.slate_id != task["slate_id"]
        or snapshot.source_freeze_sha256 != manifest_sha
        or dict(snapshot.artifact_sha256_by_block)
        != {
            block: replayed[role]["sha256"]
            for block, role in zip(
                rw.WORLD_BLOCKS, TASK_WORLD_SOURCE_ROLES, strict=True
            )
        }
    ):
        raise CorpusLegalFeasibilityError(
            "constructed PreparedLaterSlate identity differs"
        )
    source_payload: dict[str, object] = {
        "schema": "corpus-authoritative-task-source/v1",
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "task_index": index,
        "task_sha256": task["task_sha256"],
        "artifact_source_authority_completion_object": (
            normalized_completion_identity
        ),
        "artifact_source_authority_completion_sha256": (
            completion_internal_sha
        ),
        "artifact_source_authority_task_sha256": task_authority_sha,
        "artifact_source_authority_scope": ARTIFACT_SOURCE_UNIVERSE_SCOPE,
        "slate": {
            "season": snapshot.season,
            "week": snapshot.week,
            "slate_id": snapshot.slate_id,
        },
        "later_source_freeze_object": common_source,
        "later_source_freeze_manifest_sha256": manifest_sha,
        "world_artifact_receipts": replayed,
        "world_artifact_receipt_set_sha256": artifact_set_sha,
        "prepared_catalog_sha256": canonical_sha256([
            {
                "id": player.player_id,
                "pos": player.position,
                "team": player.team,
                "opp": player.opponent,
                "game_id": player.game_id,
                "salary": player.salary,
            }
            for player in snapshot.players
        ]),
        "prepared_incumbent_candidates_sha256": canonical_sha256([
            list(roster) for roster in snapshot.incumbent_candidates
        ]),
        "prepared_player_draws_sha256": _matrix_content_sha256(
            snapshot.player_draws
        ),
        "prepared_world_count": snapshot.player_draws.shape[1],
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    binding_sha = canonical_sha256(source_payload)
    binding = TaskSourceBinding(
        canonical_payload=canonical_json_bytes({
            **source_payload, "binding_sha256": binding_sha,
        }),
        binding_sha256=binding_sha,
        batch_manifest_sha256=str(manifest["batch_manifest_sha256"]),
        task_index=index,
        task_sha256=str(task["task_sha256"]),
        artifact_source_authority_completion_object_sha256=str(
            normalized_completion_identity["sha256"]
        ),
        artifact_source_authority_completion_sha256=completion_internal_sha,
        artifact_source_authority_task_sha256=task_authority_sha,
        later_source_freeze_manifest_sha256=manifest_sha,
        world_artifact_receipt_set_sha256=artifact_set_sha,
    )
    return _AuthoritativeSource(prepared=prepared, binding=binding)


def _load_authoritative_inventory(
    *,
    raw: bytes,
    common_law: Mapping[str, object],
    repository_root: Path,
) -> dict[str, object]:
    identity = _mapping(
        common_law["effective_policy_inventory_identity"],
        label="common-law inventory identity",
    )
    _validate_raw_object_identity(raw, identity, label="effective-policy inventory")
    parsed = _mapping(
        _parse_canonical_json_bytes(raw, label="effective-policy inventory"),
        label="effective-policy inventory",
    )
    if not isinstance(repository_root, Path) or not repository_root.is_dir():
        raise CorpusLegalFeasibilityError(
            "repository_root must be one existing pathlib.Path directory"
        )
    try:
        regenerated = validate_effective_policy_rule_inventory(
            parsed, repository_root
        )
    except EffectivePolicyInventoryError as exc:
        raise CorpusLegalFeasibilityError(
            "effective-policy inventory does not regenerate from frozen source"
        ) from exc
    inventory = _validate_inventory(regenerated, validator=None)
    expected = {
        "effective_policy_inventory_sha256": inventory["inventory_sha256"],
        "effective_policy_rule_universe_sha256": (
            inventory["rule_universe_sha256"]
        ),
        "effective_policy_inventory_source_set_sha256": (
            inventory["source_set_sha256"]
        ),
        "effective_policy_classified_input_projection_sha256": (
            inventory["classified_input_projection_sha256"]
        ),
    }
    if any(common_law[key] != value for key, value in expected.items()):
        raise CorpusLegalFeasibilityError(
            "manifest effective-policy inventory hashes differ from regenerated v2"
        )
    return inventory


def _validate_registered_world_schedule(
    value: object,
    *,
    manifest: Mapping[str, object],
    snapshot: _SlateSnapshot,
    task_index: int,
) -> tuple[tuple[rw.WorldId, ...], str]:
    item = _mapping(value, label="registered world schedule")
    expected_top = frozenset({
        "schema",
        "method",
        "score_accumulator",
        "tie_break",
        "block_order",
        "source_worlds_per_block",
        "visits_per_block",
        "slates",
    })
    if frozenset(item) != expected_top or item["schema"] != WORLD_SCHEDULE_SCHEMA:
        raise CorpusLegalFeasibilityError(
            "registered world-schedule schema/fields differ"
        )
    if (
        item["method"] != "top-total-slate-player-draw-desc"
        or item["score_accumulator"]
        != "float64-sum-of-all-slate-player-draws"
        or item["tie_break"] != "world-index-ascending-stable"
        or item["block_order"] != list(rw.WORLD_BLOCKS)
        or item["source_worlds_per_block"] != WORLDS_PER_BLOCK
        or item["visits_per_block"] != VISITS_PER_BLOCK
    ):
        raise CorpusLegalFeasibilityError(
            "registered world-schedule ranking law/dose differs"
        )
    slate_rows = _sequence(item["slates"], label="world schedule.slates")
    tasks = _sequence(manifest["tasks"], label="manifest tasks")
    if len(slate_rows) != len(tasks):
        raise CorpusLegalFeasibilityError(
            "registered world schedule does not cover every manifest task"
        )
    retained_schedule: tuple[rw.WorldId, ...] | None = None
    retained_schedule_sha: str | None = None
    expected_row_keys = frozenset({
        "task_index",
        "season",
        "week",
        "slate_id",
        "later_source_freeze_manifest_sha256",
        "world_artifact_receipt_set_sha256",
        "blocks",
        "visit_schedule_sha256",
    })
    for ordinal, (raw_row, task) in enumerate(
        zip(slate_rows, tasks, strict=True)
    ):
        row = _mapping(raw_row, label=f"world schedule slate[{ordinal}]")
        if frozenset(row) != expected_row_keys:
            raise CorpusLegalFeasibilityError(
                f"world schedule slate[{ordinal}] fields differ"
            )
        common = manifest["common_law"]
        if (
            row["task_index"] != ordinal
            or row["season"] != task["season"]
            or row["week"] != task["week"]
            or row["slate_id"] != task["slate_id"]
            or row["later_source_freeze_manifest_sha256"]
            != common["later_source_freeze_manifest_sha256"]
            or row["world_artifact_receipt_set_sha256"]
            != task["world_artifact_receipt_set_sha256"]
        ):
            raise CorpusLegalFeasibilityError(
                f"world schedule slate[{ordinal}] authority differs"
            )
        block_rows = _sequence(
            row["blocks"], label=f"world schedule slate[{ordinal}].blocks"
        )
        if len(block_rows) != len(rw.WORLD_BLOCKS):
            raise CorpusLegalFeasibilityError(
                f"world schedule slate[{ordinal}] block count differs"
            )
        schedule: list[rw.WorldId] = []
        for block, raw_block in zip(rw.WORLD_BLOCKS, block_rows, strict=True):
            block_row = _mapping(
                raw_block, label=f"world schedule slate[{ordinal}] {block}"
            )
            if frozenset(block_row) != frozenset({"block", "world_indices"}):
                raise CorpusLegalFeasibilityError(
                    f"world schedule slate[{ordinal}] {block} fields differ"
                )
            indices_raw = _sequence(
                block_row["world_indices"],
                label=f"world schedule slate[{ordinal}] {block} indices",
            )
            indices = tuple(
                _strict_int(
                    index,
                    label=f"world schedule slate[{ordinal}] {block} index",
                    minimum=0,
                )
                for index in indices_raw
            )
            if (
                block_row["block"] != block
                or len(indices) != VISITS_PER_BLOCK
                or len(set(indices)) != len(indices)
                or any(index >= WORLDS_PER_BLOCK for index in indices)
            ):
                raise CorpusLegalFeasibilityError(
                    f"world schedule slate[{ordinal}] {block} dose/order differs"
                )
            schedule.extend(rw.WorldId(block, index) for index in indices)
        schedule_tuple = tuple(schedule)
        schedule_sha = canonical_sha256([
            {"block": world.block, "index": world.index}
            for world in schedule_tuple
        ])
        if row["visit_schedule_sha256"] != schedule_sha:
            raise CorpusLegalFeasibilityError(
                f"world schedule slate[{ordinal}] self-hash differs"
            )
        if ordinal == task_index:
            retained_schedule = schedule_tuple
            retained_schedule_sha = schedule_sha
    if retained_schedule is None or retained_schedule_sha is None:
        raise CorpusLegalFeasibilityError("task schedule row is absent")
    recomputed = _ranked_schedule_from_snapshot(
        snapshot, visits_per_block=VISITS_PER_BLOCK
    )
    if retained_schedule != recomputed:
        raise CorpusLegalFeasibilityError(
            "registered world schedule differs from rebuilt outcome-blind ranking"
        )
    return retained_schedule, retained_schedule_sha


def _repository_source_sha256(
    repository_root: Path, relative_path: str,
) -> str:
    """Hash one exact regular repository file without accepting symlinks."""
    relative = Path(relative_path)
    if (
        not relative_path
        or relative.is_absolute()
        or relative_path != relative.as_posix()
        or ".." in relative.parts
    ):
        raise CorpusLegalFeasibilityError(
            "code-source repository path differs"
        )
    path = repository_root / relative
    try:
        before = os.lstat(path)
    except OSError as exc:
        raise CorpusLegalFeasibilityError(
            f"code-source file {relative_path!r} is absent"
        ) from exc
    if stat.S_ISLNK(before.st_mode) or not stat.S_ISREG(before.st_mode):
        raise CorpusLegalFeasibilityError(
            f"code-source file {relative_path!r} is not a regular file"
        )
    digest = sha256()
    try:
        with path.open("rb") as handle:
            opened = os.fstat(handle.fileno())
            if (opened.st_dev, opened.st_ino) != (before.st_dev, before.st_ino):
                raise CorpusLegalFeasibilityError(
                    f"code-source file {relative_path!r} changed while opening"
                )
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
            after = os.fstat(handle.fileno())
    except OSError as exc:
        raise CorpusLegalFeasibilityError(
            f"code-source file {relative_path!r} cannot be read"
        ) from exc
    if (
        (after.st_dev, after.st_ino, after.st_size)
        != (opened.st_dev, opened.st_ino, opened.st_size)
    ):
        raise CorpusLegalFeasibilityError(
            f"code-source file {relative_path!r} changed while hashing"
        )
    return digest.hexdigest()


def _validate_code_source_body(
    value: object,
    *,
    repository_root: Path,
    immutable_image: Mapping[str, object],
) -> tuple[dict[str, object], bool]:
    """Replay the retained build/source receipt against runtime source bytes."""
    item = _mapping(value, label="common-law code-source body")
    expected_keys = frozenset({
        "schema",
        "source_commit_sha",
        "cloud_build_id",
        "implementation_sha256",
        "build_definition_sha256",
        "immutable_image",
        "terminal_verification",
    })
    if (
        frozenset(item) != expected_keys
        or item["schema"] != "corpus-legal-feasibility-code-source/v1"
    ):
        raise CorpusLegalFeasibilityError(
            "common-law code-source schema/fields differ"
        )
    commit = _strict_string(
        item["source_commit_sha"], label="code-source commit SHA"
    )
    build_id = _strict_string(
        item["cloud_build_id"], label="code-source Cloud Build ID"
    )
    if (
        re.fullmatch(r"[0-9a-f]{40}", commit) is None
        or re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{12}",
            build_id,
        ) is None
    ):
        raise CorpusLegalFeasibilityError(
            "code-source commit/build identity differs"
        )
    implementation = _mapping(
        item["implementation_sha256"],
        label="code-source implementation SHA map",
    )
    build_definitions = _mapping(
        item["build_definition_sha256"],
        label="code-source build-definition SHA map",
    )
    if (
        tuple(sorted(implementation)) != _CODE_SOURCE_IMPLEMENTATION_PATHS
        or tuple(sorted(build_definitions)) != _CODE_SOURCE_BUILD_PATHS
    ):
        raise CorpusLegalFeasibilityError(
            "code-source implementation/build path universe differs"
        )
    normalized_implementation: dict[str, str] = {}
    normalized_build: dict[str, str] = {}
    for path in _CODE_SOURCE_IMPLEMENTATION_PATHS:
        retained = _strict_sha(
            implementation[path], label=f"code-source {path} SHA"
        )
        actual = _repository_source_sha256(repository_root, path)
        if retained != actual:
            raise CorpusLegalFeasibilityError(
                f"runtime implementation bytes differ for {path!r}"
            )
        normalized_implementation[path] = retained
    for path in _CODE_SOURCE_BUILD_PATHS:
        retained = _strict_sha(
            build_definitions[path], label=f"code-source {path} SHA"
        )
        actual = _repository_source_sha256(repository_root, path)
        if retained != actual:
            raise CorpusLegalFeasibilityError(
                f"runtime build-definition bytes differ for {path!r}"
            )
        normalized_build[path] = retained
    normalized_image = dict(_mapping(
        item["immutable_image"], label="code-source immutable image"
    ))
    if normalized_image != dict(immutable_image):
        raise CorpusLegalFeasibilityError(
            "code-source immutable image differs from manifest"
        )
    if item["terminal_verification"] != _CODE_SOURCE_TERMINAL_VERIFICATION:
        raise CorpusLegalFeasibilityError(
            "code-source terminal-verification law differs"
        )
    git_metadata = repository_root / ".git"
    local_commit_verified = False
    if git_metadata.exists() or git_metadata.is_symlink():
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "--verify", "HEAD"],
                cwd=repository_root,
                check=False,
                capture_output=True,
                text=True,
                timeout=5,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            raise CorpusLegalFeasibilityError(
                "runtime repository commit cannot be verified"
            ) from exc
        runtime_commit = completed.stdout.strip()
        if (
            completed.returncode != 0
            or completed.stderr
            or runtime_commit != commit
        ):
            raise CorpusLegalFeasibilityError(
                "runtime repository HEAD differs from code-source receipt"
            )
        local_commit_verified = True
    return ({
        "schema": "corpus-legal-feasibility-code-source/v1",
        "source_commit_sha": commit,
        "cloud_build_id": build_id,
        "implementation_sha256": normalized_implementation,
        "build_definition_sha256": normalized_build,
        "immutable_image": normalized_image,
        "terminal_verification": dict(_CODE_SOURCE_TERMINAL_VERIFICATION),
    }, local_commit_verified)


def _load_registered_common_law(
    *,
    raw_bodies: Mapping[str, bytes],
    manifest: Mapping[str, object],
    snapshot: _SlateSnapshot,
    task_index: int,
    inventory: Mapping[str, object],
    solver_authority: Mapping[str, object],
    ambient_process_keys_present: Sequence[str],
    repository_root: Path,
    task_source_binding: TaskSourceBinding,
) -> RegisteredLawBinding:
    if not isinstance(raw_bodies, Mapping) or set(raw_bodies) != set(
        _COMMON_LAW_BODY_ROLES
    ):
        raise CorpusLegalFeasibilityError(
            "retained common-law body roles differ"
        )
    common = _mapping(manifest["common_law"], label="manifest common law")
    task = _mapping(
        _sequence(manifest["tasks"], label="manifest tasks")[task_index],
        label="manifest task",
    )
    identities: dict[str, dict[str, object]] = {}
    parsed: dict[str, object] = {}
    for role in _COMMON_LAW_BODY_ROLES:
        raw = raw_bodies[role]
        identities[role] = _validate_raw_object_identity(
            raw, _mapping(common[role], label=f"common law {role}"),
            label=f"common-law {role}",
        )
        parsed[role] = _parse_canonical_json_bytes(
            raw, label=f"common-law {role}"
        )
    code_source, local_commit_verified = _validate_code_source_body(
        parsed["code_source"],
        repository_root=repository_root,
        immutable_image=_mapping(
            common["immutable_image"], label="manifest immutable image"
        ),
    )
    for role, expected in _REGISTERED_MECHANISM_BODIES.items():
        if canonical_json_bytes(parsed[role]) != canonical_json_bytes(expected):
            raise CorpusLegalFeasibilityError(
                f"registered common-law {role} semantics differ"
            )
    schedule, schedule_sha = _validate_registered_world_schedule(
        parsed["world_schedule"],
        manifest=manifest,
        snapshot=snapshot,
        task_index=task_index,
    )
    budget = common["solve_budget"]
    expected_budget = {
        "solve_attempts_per_seed": VISITS_PER_BLOCK,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "solver_timeout_seconds": SOLVER_TIMEOUT_SECONDS,
        "candidate_entry_budget": MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
        "selected_entry_budget": ENTRY_COUNT,
    }
    if budget != expected_budget or len(schedule) != MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION:
        raise CorpusLegalFeasibilityError(
            "registered common-law solve budget differs from exact v1 dose"
        )
    if common["solver"] != solver_authority:
        raise CorpusLegalFeasibilityError(
            "runtime CBC binary/options authority differs from manifest"
        )
    completion_identity = _mapping(
        common["artifact_source_authority_completion"],
        label="registered artifact source-authority completion identity",
    )
    completion_object_sha = _strict_sha(
        completion_identity["sha256"],
        label="registered source-authority object SHA",
    )
    completion_internal_sha = _strict_sha(
        common["artifact_source_authority_completion_sha256"],
        label="registered source-authority internal SHA",
    )
    task_authority_sha = _strict_sha(
        task["artifact_source_authority_task_sha256"],
        label="registered source-authority task SHA",
    )
    if (
        completion_object_sha == completion_internal_sha
        or task_source_binding.artifact_source_authority_completion_object_sha256
        != completion_object_sha
        or task_source_binding.artifact_source_authority_completion_sha256
        != completion_internal_sha
        or task_source_binding.artifact_source_authority_task_sha256
        != task_authority_sha
    ):
        raise CorpusLegalFeasibilityError(
            "registered source-authority law/source binding differs"
        )
    semantic_input = {
        "typed_request_local_fields": list(PARAMETER_ORDER),
        "frozen_common_law_sha256": manifest["common_law_sha256"],
        "infrastructure_inherited_as_science": False,
        "ambient_score_relevant_keys_present": list(
            ambient_process_keys_present
        ),
    }
    ambient = inventory["classified_input_projection"][
        "ambient_process_keys_requiring_absence"
    ]
    if (
        len(ambient) != 97
        or tuple(ambient_process_keys_present)
        != tuple(sorted(set(ambient_process_keys_present)))
        or bool(ambient_process_keys_present)
        or common["worker_environment_inheritance"] is not False
        or common["worker_graph_mutation"] is not False
        or common["fresh_model_state_per_parameter_set"] is not True
    ):
        raise CorpusLegalFeasibilityError(
            "registered worker/ambient-input law differs"
        )
    body: dict[str, object] = {
        "schema": "corpus-authoritative-registered-law/v1",
        "common_law_sha256": manifest["common_law_sha256"],
        "mechanism_object_identities": identities,
        "mechanism_body_sha256": {
            role: sha256(raw_bodies[role]).hexdigest()
            for role in _COMMON_LAW_BODY_ROLES
        },
        "code_source": code_source,
        "code_source_runtime_repository_head_verified": (
            local_commit_verified
        ),
        "immutable_image": common["immutable_image"],
        "immutable_image_sha256": canonical_sha256(
            common["immutable_image"]
        ),
        "runtime_image_terminal_verification_required": True,
        "terminal_verification_law": _CODE_SOURCE_TERMINAL_VERIFICATION,
        "artifact_source_authority": {
            "completion_object": dict(completion_identity),
            "completion_sha256": completion_internal_sha,
            "task_source_authority_sha256": task_authority_sha,
            "universe_scope": ARTIFACT_SOURCE_UNIVERSE_SCOPE,
            "artifact_supported_universe_complete": True,
            "complete_dk_salary_universe_claimed": False,
        },
        "solve_budget": expected_budget,
        "solver": solver_authority,
        "solver_timeout_law": SOLVER_TIMEOUT_LAW,
        "world_seed": common["world_seed"],
        "visit_schedule_sha256": schedule_sha,
        "inventory_binding": {
            "inventory_sha256": inventory["inventory_sha256"],
            "rule_universe_sha256": inventory["rule_universe_sha256"],
            "source_set_sha256": inventory["source_set_sha256"],
            "classified_input_projection_sha256": inventory[
                "classified_input_projection_sha256"
            ],
        },
        "semantic_input_projection": semantic_input,
        "ambient_score_relevant_keys_requiring_absence": list(ambient),
        "ambient_score_relevant_key_count": len(ambient),
        "all_ambient_score_relevant_semantic_inputs_absent": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    binding_sha = canonical_sha256(body)
    return RegisteredLawBinding(
        canonical_payload=canonical_json_bytes({
            **body, "binding_sha256": binding_sha,
        }),
        binding_sha256=binding_sha,
        common_law_sha256=str(manifest["common_law_sha256"]),
        code_source_object_sha256=str(identities["code_source"]["sha256"]),
        code_source_body_sha256=sha256(
            raw_bodies["code_source"]
        ).hexdigest(),
        immutable_image_sha256=canonical_sha256(common["immutable_image"]),
        runtime_image_terminal_verification_required=True,
        artifact_source_authority_completion_object_sha256=(
            completion_object_sha
        ),
        artifact_source_authority_completion_sha256=completion_internal_sha,
        artifact_source_authority_task_sha256=task_authority_sha,
        world_schedule_object_sha256=str(
            identities["world_schedule"]["sha256"]
        ),
        visit_schedule_sha256=schedule_sha,
        solver_authority_sha256=canonical_sha256(solver_authority),
    )


def _load_authoritative_inputs(
    *,
    task_request: Mapping[str, object],
    batch_manifest_bytes: bytes,
    effective_policy_inventory_bytes: bytes,
    artifact_source_authority_completion_bytes: bytes,
    later_source_freeze_bytes: bytes,
    world_artifact_bodies: Mapping[str, bytes],
    common_law_bodies: Mapping[str, bytes],
    repository_root: Path,
) -> _AuthoritativeInputs:
    """Close every authority before constructing the first solver model."""
    if type(batch_manifest_bytes) is not bytes:
        raise CorpusLegalFeasibilityError("batch manifest must be raw bytes")
    try:
        request, manifest = bind_task_request_to_manifest(
            task_request, batch_manifest_bytes
        )
    except ValueError as exc:
        raise CorpusLegalFeasibilityError(
            "task request does not bind the exact raw batch manifest"
        ) from exc
    task_index = int(request["task_index"])
    common = _mapping(manifest["common_law"], label="manifest common law")
    inventory = _load_authoritative_inventory(
        raw=effective_policy_inventory_bytes,
        common_law=common,
        repository_root=repository_root,
    )
    source = _load_authoritative_source(
        batch_manifest=manifest,
        task_index=task_index,
        artifact_source_authority_completion_bytes=(
            artifact_source_authority_completion_bytes
        ),
        retained_source_freeze_bytes=later_source_freeze_bytes,
        retained_world_artifact_bodies=world_artifact_bodies,
    )
    solver_authority = _cbc_runtime_authority()
    ambient_required = tuple(
        inventory["classified_input_projection"][
            "ambient_process_keys_requiring_absence"
        ]
    )
    ambient_present = tuple(sorted(
        key for key in ambient_required if key in os.environ
    ))
    if ambient_present:
        raise CorpusLegalFeasibilityError(
            "authoritative process exposes forbidden score-relevant ambient keys: "
            f"{list(ambient_present)}"
        )
    law = _load_registered_common_law(
        raw_bodies=common_law_bodies,
        manifest=manifest,
        snapshot=_validate_prepared_slate(source.prepared),
        task_index=task_index,
        task_source_binding=source.binding,
        inventory=inventory,
        solver_authority=solver_authority,
        ambient_process_keys_present=ambient_present,
        repository_root=repository_root,
    )
    return _AuthoritativeInputs(
        request=request,
        manifest=manifest,
        inventory=inventory,
        source=source,
        law=law,
        ambient_process_keys_present=ambient_present,
    )


def _ranked_schedule_from_snapshot(
    snapshot: _SlateSnapshot,
    *,
    visits_per_block: int,
) -> tuple[rw.WorldId, ...]:
    count = _strict_int(
        visits_per_block, label="visits_per_block", minimum=1
    )
    if count > rw.WORLDS_PER_BLOCK:
        raise CorpusLegalFeasibilityError(
            "visits_per_block exceeds retained worlds per block"
        )
    schedule_rows: list[rw.WorldId] = []
    for block_ordinal, block in enumerate(rw.WORLD_BLOCKS):
        start = block_ordinal * rw.WORLDS_PER_BLOCK
        stop = start + rw.WORLDS_PER_BLOCK
        totals = snapshot.player_draws[:, start:stop].sum(
            axis=0, dtype=np.float64
        )
        indices = np.arange(rw.WORLDS_PER_BLOCK, dtype=np.int64)
        ranked = np.lexsort((indices, -totals))[:count]
        schedule_rows.extend(
            rw.WorldId(block, int(index)) for index in ranked
        )
    schedule = tuple(schedule_rows)
    if len(set(schedule)) != len(schedule):
        raise CorpusLegalFeasibilityError("ranked visit schedule repeats worlds")
    return schedule


def canonical_visit_schedule(
    prepared: PreparedLaterSlate,
    *,
    visits_per_block: int = VISITS_PER_BLOCK,
) -> tuple[rw.WorldId, ...]:
    """Rank each R0..R4 block by total slate draw, then stable world index."""
    return _ranked_schedule_from_snapshot(
        _validate_prepared_slate(prepared),
        visits_per_block=visits_per_block,
    )


def _micro_objective(
    draws: np.ndarray, *, world_column: int,
) -> tuple[int, ...]:
    values = np.asarray(draws[:, world_column], dtype=np.float64)
    if values.ndim != 1 or not np.isfinite(values).all():
        raise CorpusLegalFeasibilityError("visit objective is malformed")
    limit = MAX_EXACT_CBC_INTEGER / (MICRO_DK_SCALE * rw.ROSTER_SIZE)
    if values.size == 0 or float(np.max(np.abs(values))) > limit:
        raise CorpusLegalFeasibilityError(
            "visit objective exceeds exact micro-DK CBC range"
        )
    micro = np.rint(values * MICRO_DK_SCALE).astype(np.int64)
    if max(abs(int(micro.min())), abs(int(micro.max()))) * rw.ROSTER_SIZE > MAX_EXACT_CBC_INTEGER:
        raise CorpusLegalFeasibilityError(
            "visit objective exceeds exact nine-player integer range"
        )
    return tuple(int(value) for value in micro)


def build_fresh_legal_model(
    players: Sequence[rw.PlayerSpec],
    profile: EffectivePolicyProfile,
    objective_micro: Sequence[int],
    *,
    construction_serial: int,
    model_name: str,
) -> FreshLegalModel:
    rows = tuple(players)
    if tuple(player.player_id for player in rows) != tuple(sorted(
        player.player_id for player in rows
    )):
        raise CorpusLegalFeasibilityError("model players are not canonical id order")
    objective = tuple(
        _strict_int(value, label="objective micro-DK") for value in objective_micro
    )
    if len(objective) != len(rows):
        raise CorpusLegalFeasibilityError("objective/player rows are misaligned")
    serial = _strict_int(
        construction_serial, label="construction serial", minimum=0
    )
    problem = pulp.LpProblem(
        _strict_string(model_name, label="model name"), pulp.LpMaximize
    )
    decision = {
        player.player_id: pulp.LpVariable(f"x_{index:04d}", cat="Binary")
        for index, player in enumerate(rows)
    }
    player_mappings = [{
        "id": player.player_id,
        "pos": player.position,
        "team": player.team,
        "opp": player.opponent,
        "game_id": player.game_id,
        "salary": player.salary,
    } for player in rows]
    dose = profile.constraints
    add_classic_lineup_constraints(
        problem,
        decision,
        player_mappings,
        budget=dose.budget,
        locks=set(dose.locks),
        bans=set(dose.bans),
        banned_lineups=[frozenset(value) for value in dose.banned_lineups],
        stack=profile.stack.as_stack_rules(),
        max_overlap=dose.max_overlap,
        punt_max_salary=dose.punt_max_salary,
        punt_min=dose.punt_min,
        game_lock=dose.game_lock,
        min_salary=dose.min_salary,
        max_salary=dose.max_salary,
        max_per_game=dose.max_per_game,
        env=dict(dose.env),
    )
    problem.setObjective(pulp.lpSum(
        decision[player.player_id] * objective[index]
        for index, player in enumerate(rows)
    ))
    model_variables = tuple(problem.variables())
    if (
        len(model_variables) != len(rows)
        or {variable.name for variable in model_variables}
        != {variable.name for variable in decision.values()}
        or any(
            variable.cat != pulp.LpInteger
            or variable.lowBound != 0
            or variable.upBound != 1
            for variable in model_variables
        )
    ):
        raise CorpusLegalFeasibilityError(
            "legal model must contain exactly one binary variable per player and no auxiliaries"
        )
    return FreshLegalModel(
        problem=problem,
        players=rows,
        decision=decision,
        construction_serial=serial,
    )


def classify_pulp_status(problem: pulp.LpProblem) -> SolverStatus:
    """Classify PuLP/CBC status, refusing integer-feasible timeout as optimal."""
    if problem.status == pulp.LpStatusOptimal and (
        problem.sol_status == pulp.LpSolutionOptimal
    ):
        return SolverStatus.OPTIMAL
    if problem.status == pulp.LpStatusInfeasible:
        return SolverStatus.INFEASIBLE
    if problem.status == pulp.LpStatusNotSolved or (
        problem.sol_status in {
            pulp.LpSolutionIntegerFeasible,
            pulp.LpSolutionNoSolutionFound,
        }
    ):
        return SolverStatus.TIMEOUT
    return SolverStatus.ERROR


def _exact_mps_integer(value: object, *, label: str) -> int:
    """Convert one intended/serialized MPS number without float rounding."""
    if isinstance(value, bool):
        raise CorpusLegalFeasibilityError(f"{label} is not an exact integer")
    try:
        decimal = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise CorpusLegalFeasibilityError(
            f"{label} is not an exact decimal integer"
        ) from exc
    if not decimal.is_finite() or decimal != decimal.to_integral_value():
        raise CorpusLegalFeasibilityError(f"{label} is not an exact integer")
    integer = int(decimal)
    if abs(integer) > MAX_EXACT_CBC_INTEGER:
        raise CorpusLegalFeasibilityError(
            f"{label} exceeds the exact CBC integer range"
        )
    return integer


def _parse_exact_integer_mps(raw: bytes) -> dict[str, object]:
    """Parse the exact free-format MPS subset emitted by pinned PuLP."""
    if type(raw) is not bytes or not raw:
        raise CorpusLegalFeasibilityError("CBC MPS bytes are absent")
    try:
        lines = raw.decode("ascii").splitlines()
    except UnicodeDecodeError as exc:
        raise CorpusLegalFeasibilityError("CBC MPS is not ASCII") from exc
    if (
        len(lines) < 8
        or lines[0] not in {"*SENSE:Maximize", "*SENSE:Minimize"}
        or lines[1] != "NAME          MODEL"
        or lines[-1] != "ENDATA"
    ):
        raise CorpusLegalFeasibilityError("CBC MPS envelope differs")

    section_order = ("ROWS", "COLUMNS", "RHS", "BOUNDS", "ENDATA")
    next_section = 0
    section = ""
    objective_row: str | None = None
    row_senses: dict[str, str] = {}
    coefficients: dict[tuple[str, str], int] = {}
    rhs: dict[str, int] = {}
    bounds: dict[str, tuple[str, int | None]] = {}
    variables: set[str] = set()
    integer_region = False
    marker_count = 0

    for line_number, line in enumerate(lines[2:], start=3):
        if line in section_order:
            if (
                next_section >= len(section_order)
                or line != section_order[next_section]
            ):
                raise CorpusLegalFeasibilityError(
                    "CBC MPS section order differs"
                )
            section = line
            next_section += 1
            continue
        if not line or section in {"", "ENDATA"}:
            raise CorpusLegalFeasibilityError(
                f"CBC MPS line {line_number} is outside one section"
            )
        tokens = line.split()
        if section == "ROWS":
            if len(tokens) != 2 or tokens[0] not in {"N", "E", "L", "G"}:
                raise CorpusLegalFeasibilityError("CBC MPS row differs")
            sense, name = tokens
            if sense == "N":
                if objective_row is not None:
                    raise CorpusLegalFeasibilityError(
                        "CBC MPS repeats its objective row"
                    )
                objective_row = name
            elif name in row_senses:
                raise CorpusLegalFeasibilityError("CBC MPS repeats a row")
            else:
                row_senses[name] = sense
        elif section == "COLUMNS":
            if tokens == ["MARK", "'MARKER'", "'INTORG'"]:
                if integer_region:
                    raise CorpusLegalFeasibilityError(
                        "CBC MPS nests integer markers"
                    )
                integer_region = True
                marker_count += 1
                continue
            if tokens == ["MARK", "'MARKER'", "'INTEND'"]:
                if not integer_region:
                    raise CorpusLegalFeasibilityError(
                        "CBC MPS closes an absent integer marker"
                    )
                integer_region = False
                marker_count += 1
                continue
            if len(tokens) != 3:
                raise CorpusLegalFeasibilityError("CBC MPS column differs")
            variable, row, token = tokens
            key = (variable, row)
            if key in coefficients:
                raise CorpusLegalFeasibilityError(
                    "CBC MPS repeats a coefficient"
                )
            coefficients[key] = _exact_mps_integer(
                token, label=f"CBC MPS coefficient {variable}/{row}"
            )
            variables.add(variable)
        elif section == "RHS":
            if len(tokens) != 3 or tokens[0] != "RHS":
                raise CorpusLegalFeasibilityError("CBC MPS RHS differs")
            row = tokens[1]
            if row in rhs:
                raise CorpusLegalFeasibilityError("CBC MPS repeats an RHS")
            rhs[row] = _exact_mps_integer(
                tokens[2], label=f"CBC MPS RHS {row}"
            )
        elif section == "BOUNDS":
            if len(tokens) not in {3, 4} or tokens[1] != "BND":
                raise CorpusLegalFeasibilityError("CBC MPS bound differs")
            kind, _, variable, *numeric = tokens
            if variable in bounds or kind not in {
                "BV", "FX", "LO", "UP", "FR", "MI", "PL"
            }:
                raise CorpusLegalFeasibilityError(
                    "CBC MPS bound kind/order differs"
                )
            if kind in {"BV", "FR", "MI", "PL"}:
                if numeric:
                    raise CorpusLegalFeasibilityError(
                        "CBC MPS nonnumeric bound has a value"
                    )
                bound_value = None
            else:
                if len(numeric) != 1:
                    raise CorpusLegalFeasibilityError(
                        "CBC MPS numeric bound lacks one value"
                    )
                bound_value = _exact_mps_integer(
                    numeric[0], label=f"CBC MPS {kind} bound {variable}"
                )
            bounds[variable] = (kind, bound_value)
            variables.add(variable)

    if (
        next_section != len(section_order)
        or objective_row is None
        or integer_region
        or marker_count % 2
        or not row_senses
        or set(rhs) != set(row_senses)
        or set(bounds) != variables
        or any(row != objective_row and row not in row_senses for _, row in coefficients)
    ):
        raise CorpusLegalFeasibilityError(
            "CBC MPS row/variable/integer topology differs"
        )
    return {
        "sense": lines[0].removeprefix("*SENSE:"),
        "objective_row": objective_row,
        "row_senses": [
            {"row": row, "sense": row_senses[row]}
            for row in sorted(row_senses)
        ],
        "coefficients": [
            {"variable": variable, "row": row, "value": value}
            for (variable, row), value in sorted(coefficients.items())
        ],
        "rhs": [
            {"row": row, "value": rhs[row]} for row in sorted(rhs)
        ],
        "bounds": [
            {
                "variable": variable,
                "kind": bounds[variable][0],
                "value": bounds[variable][1],
            }
            for variable in sorted(bounds)
        ],
    }


def _expected_exact_integer_mps(
    problem: pulp.LpProblem,
    *,
    variables: Sequence[pulp.LpVariable],
    variable_names: Mapping[str, str],
    constraint_names: Mapping[str, str],
    objective_name: str,
) -> dict[str, object]:
    """Project the in-memory LP into the exact integer MPS semantics."""
    rows = tuple(variables)
    if (
        not rows
        or set(variable_names) != {variable.name for variable in rows}
        or set(constraint_names) != set(problem.constraints)
        or not objective_name
        or problem.objective is None
    ):
        raise CorpusLegalFeasibilityError(
            "CBC MPS writer name authority differs"
        )
    row_sense_by_value = {
        pulp.LpConstraintEQ: "E",
        pulp.LpConstraintLE: "L",
        pulp.LpConstraintGE: "G",
    }
    coefficients: dict[tuple[str, str], int] = {}
    for source_name, constraint in problem.constraints.items():
        retained_name = constraint_names[source_name]
        for variable, value in constraint.items():
            coefficients[(variable_names[variable.name], retained_name)] = (
                _exact_mps_integer(
                    value,
                    label=(
                        "intended MPS coefficient "
                        f"{variable.name}/{source_name}"
                    ),
                )
            )
    objective = problem.objective
    if objective.isNumericalConstant():
        dummy = [variable for variable in rows if variable.name == "__dummy"]
        if len(dummy) != 1:
            raise CorpusLegalFeasibilityError(
                "constant CBC objective lacks its exact fixed dummy"
            )
        objective_items = ((dummy[0], 1),)
    else:
        objective_items = tuple(objective.items())
    for variable, value in objective_items:
        coefficients[(variable_names[variable.name], objective_name)] = (
            _exact_mps_integer(
                value, label=f"intended MPS objective {variable.name}"
            )
        )

    bounds: dict[str, tuple[str, int | None]] = {}
    for variable in rows:
        name = variable_names[variable.name]
        low = variable.lowBound
        high = variable.upBound
        if low is not None and low == high:
            bounds[name] = (
                "FX", _exact_mps_integer(low, label=f"intended fixed bound {name}")
            )
        elif (
            low == 0
            and high == 1
            and variable.cat == pulp.LpInteger
        ):
            bounds[name] = ("BV", None)
        else:
            raise CorpusLegalFeasibilityError(
                "authoritative CBC model contains a nonbinary/nonfixed variable"
            )
    return {
        "sense": "Maximize" if problem.sense == pulp.LpMaximize else "Minimize",
        "objective_row": objective_name,
        "row_senses": [
            {
                "row": constraint_names[name],
                "sense": row_sense_by_value[constraint.sense],
            }
            for name, constraint in sorted(
                problem.constraints.items(), key=lambda item: constraint_names[item[0]]
            )
        ],
        "coefficients": [
            {"variable": variable, "row": row, "value": value}
            for (variable, row), value in sorted(coefficients.items())
        ],
        "rhs": [
            {
                "row": constraint_names[name],
                "value": _exact_mps_integer(
                    -constraint.constant,
                    label=f"intended MPS RHS {name}",
                ),
            }
            for name, constraint in sorted(
                problem.constraints.items(), key=lambda item: constraint_names[item[0]]
            )
        ],
        "bounds": [
            {
                "variable": variable,
                "kind": bounds[variable][0],
                "value": bounds[variable][1],
            }
            for variable in sorted(bounds)
        ],
    }


def _validate_exact_integer_mps_semantics(
    raw: bytes,
    problem: pulp.LpProblem,
    *,
    variables: Sequence[pulp.LpVariable],
    variable_names: Mapping[str, str],
    constraint_names: Mapping[str, str],
    objective_name: str,
) -> str:
    """Fail if serialized MPS changes any intended integer semantic."""
    parsed = _parse_exact_integer_mps(raw)
    expected = _expected_exact_integer_mps(
        problem,
        variables=variables,
        variable_names=variable_names,
        constraint_names=constraint_names,
        objective_name=objective_name,
    )
    if parsed != expected:
        raise CorpusLegalFeasibilityError(
            "serialized CBC MPS integer semantics differ from the in-memory model"
        )
    return canonical_sha256(parsed)


class _RetainedStageCbcSolver(pulp.PULP_CBC_CMD):
    """Exact CBC stage with pre/post-hashed content-addressed MPS evidence."""

    def __init__(
        self, *, absolute_deadline: float, evidence_directory: Path,
    ) -> None:
        if (
            type(absolute_deadline) not in (int, float)
            or isinstance(absolute_deadline, bool)
            or not np.isfinite(float(absolute_deadline))
        ):
            raise CorpusLegalFeasibilityError(
                "CBC absolute monotonic deadline differs"
            )
        self.absolute_deadline = float(absolute_deadline)
        self.evidence_directory = evidence_directory
        self.artifact_paths: dict[str, Path] = {}
        self.model_pre_exec_sha256: str | None = None
        self.model_post_exit_sha256: str | None = None
        self.model_integer_semantics_sha256: str | None = None
        self.model_variables: tuple[pulp.LpVariable, ...] = ()
        self.model_variable_names: dict[str, str] = {}
        self.model_constraint_names: dict[str, str] = {}
        self.model_objective_name: str | None = None
        self.model_bytes_exact = 0
        self.model_regular_exclusive_inode = False
        self.model_path_command_bound = False
        self.expected_command_line: str | None = None
        self.watchdog_timed_out = False
        self.cbc_requested_microseconds: int | None = None
        self.host_watchdog_microseconds: int | None = None
        super().__init__(
            msg=False,
            timeLimit=None,
            threads=CBC_THREADS,
            gapRel=0.0,
            gapAbs=0.0,
            options=list(CBC_OPTIONS),
            timeMode="elapsed",
            logPath=str(evidence_directory / "cbc.log"),
            keepFiles=False,
        )

    def actualSolve(self, lp: pulp.LpProblem, **kwargs: object) -> int:
        if kwargs:
            raise pulp.PulpSolverError("CBC stage received unsupported kwargs")
        binary = Path(str(self.path)).resolve()
        if not binary.is_file():
            raise pulp.PulpSolverError("CBC stage binary is absent")
        staging = self.evidence_directory / "exclusive-staging.mps"
        if staging.exists() or staging.is_symlink():
            raise pulp.PulpSolverError("CBC MPS staging path was reused")
        vs, variable_names, constraint_names, objective_name = lp.writeMPS(
            str(staging), rename=1
        )
        try:
            raw_staging = staging.read_bytes()
        except OSError as exc:
            raise pulp.PulpSolverError(
                "CBC MPS staging bytes cannot be read"
            ) from exc
        self.model_variables = tuple(vs)
        self.model_variable_names = dict(variable_names)
        self.model_constraint_names = dict(constraint_names)
        self.model_objective_name = str(objective_name)
        try:
            self.model_integer_semantics_sha256 = (
                _validate_exact_integer_mps_semantics(
                    raw_staging,
                    lp,
                    variables=self.model_variables,
                    variable_names=self.model_variable_names,
                    constraint_names=self.model_constraint_names,
                    objective_name=self.model_objective_name,
                )
            )
        except CorpusLegalFeasibilityError as exc:
            raise pulp.PulpSolverError(
                "CBC MPS changes intended integer semantics"
            ) from exc
        before_staging = staging.lstat()
        if (
            staging.is_symlink()
            or not staging.is_file()
            or before_staging.st_nlink != 1
        ):
            raise pulp.PulpSolverError(
                "CBC MPS staging artifact is not one exclusive regular inode"
            )
        pre_sha = _file_sha256(staging)
        model_path = self.evidence_directory / f"{pre_sha}.mps"
        if model_path.exists() or model_path.is_symlink():
            raise pulp.PulpSolverError("content-addressed CBC MPS path was reused")
        staging.replace(model_path)
        before = model_path.lstat()
        if (
            model_path.is_symlink()
            or not model_path.is_file()
            or before.st_nlink != 1
            or before.st_ino != before_staging.st_ino
        ):
            raise pulp.PulpSolverError(
                "content-addressed CBC MPS inode binding differs"
            )
        solution_path = self.evidence_directory / f"{pre_sha}.sol"
        log_path = self.evidence_directory / f"{pre_sha}.log"
        if solution_path.exists() or log_path.exists():
            raise pulp.PulpSolverError("CBC output evidence path was reused")
        self.artifact_paths = {
            "mps": model_path,
            "sol": solution_path,
            "log": log_path,
        }
        timed_out = False
        try:
            with log_path.open("xb") as log_handle:
                remaining_us = int(
                    max(0.0, self.absolute_deadline - time.monotonic())
                    * 1_000_000
                )
                if remaining_us <= 0:
                    self.watchdog_timed_out = True
                    raise pulp.PulpSolverError(
                        "CBC deadline expired before process spawn"
                    )
                self.cbc_requested_microseconds = remaining_us
                requested_seconds = remaining_us / 1_000_000
                requested_text = f"{requested_seconds:.6f}"
                args = [str(binary), str(model_path)]
                if lp.sense == pulp.constants.LpMaximize:
                    args.append("-max")
                args.extend(("-sec", requested_text))
                for option in CBC_OPTIONS:
                    name, value = option.split(" ", 1)
                    args.extend((f"-{name}", value))
                args.extend((
                    "-ratio", "0.0",
                    "-allow", "0.0",
                    "-threads", str(CBC_THREADS),
                    "-timeMode", "elapsed",
                    "-solve",
                    "-printingOptions", "all",
                    "-solution", str(solution_path),
                ))
                self.expected_command_line = (
                    "command line - " + " ".join(args)
                    + _CBC_COMMAND_LINE_SUFFIX
                )
                process = subprocess.Popen(
                    args,
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=log_handle,
                )
                watchdog_us = int(
                    max(0.0, self.absolute_deadline - time.monotonic())
                    * 1_000_000
                )
                self.host_watchdog_microseconds = watchdog_us
                if watchdog_us <= 0:
                    process.terminate()
                    try:
                        process.wait(timeout=0.25)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    self.watchdog_timed_out = True
                    raise pulp.PulpSolverError(
                        "CBC deadline expired during process spawn"
                    )
                try:
                    return_code = process.wait(
                        timeout=watchdog_us / 1_000_000
                    )
                except subprocess.TimeoutExpired:
                    process.terminate()
                    try:
                        process.wait(timeout=0.25)
                    except subprocess.TimeoutExpired:
                        process.kill()
                        process.wait()
                    timed_out = True
                    return_code = process.returncode
        except OSError as exc:
            raise pulp.PulpSolverError("CBC stage process failed") from exc
        after = model_path.lstat()
        post_sha = _file_sha256(model_path)
        self.model_pre_exec_sha256 = pre_sha
        self.model_post_exit_sha256 = post_sha
        self.model_bytes_exact = before.st_size
        self.model_regular_exclusive_inode = (
            not model_path.is_symlink()
            and model_path.is_file()
            and before.st_nlink == after.st_nlink == 1
            and before.st_ino == after.st_ino
            and before.st_size == after.st_size
            and pre_sha == post_sha
        )
        self.model_path_command_bound = True
        if timed_out:
            self.watchdog_timed_out = True
            raise pulp.PulpSolverError(
                "CBC stage exceeded its monotonic host watchdog"
            )
        if return_code != 0 or not solution_path.is_file():
            raise pulp.PulpSolverError("CBC stage did not retain a solution")
        (
            status,
            values,
            reduced_costs,
            shadow_prices,
            slacks,
            solution_status,
        ) = self.readsol_MPS(
            str(solution_path),
            lp,
            vs,
            variable_names,
            constraint_names,
        )
        lp.assignVarsVals(values)
        lp.assignVarsDj(reduced_costs)
        lp.assignConsPi(shadow_prices)
        lp.assignConsSlack(slacks, activity=True)
        lp.assignStatus(status, solution_status)
        return int(status)


def _cbc_solver(
    *, absolute_deadline: float, evidence_directory: Path,
) -> _RetainedStageCbcSolver:
    return _RetainedStageCbcSolver(
        absolute_deadline=absolute_deadline,
        evidence_directory=evidence_directory,
    )


def _file_sha256(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CorpusLegalFeasibilityError(
            "CBC binary cannot be read for identity"
        ) from exc
    return digest.hexdigest()


@lru_cache(maxsize=1)
def _cbc_runtime_authority() -> dict[str, object]:
    """Inspect the exact default CBC binary and pinned one-thread options."""
    solver = pulp.PULP_CBC_CMD(msg=False)
    path = Path(str(solver.path)).resolve()
    if not path.is_file():
        raise CorpusLegalFeasibilityError("default CBC binary is absent")
    try:
        completed = subprocess.run(
            [str(path), "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CorpusLegalFeasibilityError(
            "default CBC version receipt cannot be read"
        ) from exc
    output = f"{completed.stdout}\n{completed.stderr}"
    matches = re.findall(r"^Version:\s+([^\s]+)\s*$", output, re.MULTILINE)
    if completed.returncode != 0 or len(matches) != 1:
        raise CorpusLegalFeasibilityError(
            "default CBC version receipt is ambiguous"
        )
    return {
        "name": "cbc",
        "version": matches[0],
        "binary_sha256": _file_sha256(path),
        "options_sha256": canonical_sha256(CBC_OPTIONS_PAYLOAD),
        "exact_mode": True,
    }


_CBC_WARNING_MARKER: Final = re.compile(r"\b(?:Cbc|Cgl|Clp|Coin)\d+W\b")
_CBC_FORBIDDEN_MARKER: Final = re.compile(
    r"Stopped on|Exiting on maximum|Partial search|within gap tolerance|"
    r"Upper bound:|^Gap:|unbounded|abandoned|\bnan\b|"
    r"\binf(?:inity)?\b|Exiting as integer gap|"
    r"maximum (?:time|node|solution)",
    re.IGNORECASE | re.MULTILINE,
)
_CBC_TIMEOUT_MARKER: Final = re.compile(
    r"Stopped on|Exiting on maximum|Partial search|maximum time|time limit",
    re.IGNORECASE,
)
_CBC_FINITE_INFEASIBILITY_DIAGNOSTIC: Final = re.compile(
    r"^(?:Clp\d+I\s+)?\d+\s+Obj\s+"
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?\s+"
    r"Primal inf\s+[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[Ee][+-]?\d+)?(?:\s+\(\d+\))?"
    r"(?:\s+Dual inf\s+[+-]?(?:\d+(?:\.\d*)?|\.\d+)"
    r"(?:[Ee][+-]?\d+)?(?:\s+\(\d+\))?)?\s*$"
)


def _cbc_marker_projection(log: str) -> str:
    rows: list[str] = []
    for line in log.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        if body.startswith("command line - "):
            rows.append("command line - <validated-separately>" + ending)
        elif _CBC_FINITE_INFEASIBILITY_DIAGNOSTIC.fullmatch(body):
            rows.append(re.sub(
                r"\binf\b", "finite_lp_diagnostic", body,
                flags=re.IGNORECASE,
            ) + ending)
        else:
            rows.append(body + ending)
    return "".join(rows)


def _classify_cbc_log(
    log: str,
    solution: bytes,
    *,
    pulp_status: SolverStatus,
    expected_command_line: str,
) -> tuple[SolverStatus, str | None, bool]:
    if not log or "\x00" in log:
        return SolverStatus.ERROR, None, True
    warning = _CBC_WARNING_MARKER.search(log) is not None
    command_lines = re.findall(r"^command line - .*?$", log, re.MULTILINE)
    model_reads = re.findall(
        r"^Coin0008I MODEL read with (\d+) errors\s*$", log, re.MULTILINE
    )
    masked = _cbc_marker_projection(log)
    lines = log.splitlines()
    optimal = [line for line in lines if line == _CBC_OPTIMAL_TERMINAL]
    infeasible = [
        line for line in lines
        if _CBC_INFEASIBLE_TERMINAL.fullmatch(line) is not None
    ]
    masked_for_infeasible = re.sub(
        r"^(?:Result - Problem proven infeasible|"
        r"Problem is infeasible(?: - .*?)?)[ \t]*$",
        "<exact-infeasible-terminal>",
        masked,
        flags=re.MULTILINE,
    )
    forbidden = _CBC_FORBIDDEN_MARKER.search(masked_for_infeasible) is not None
    error_text = re.sub(
        r"^Coin0008I MODEL read with 0 errors\s*$", "", log,
        count=1,
        flags=re.MULTILINE,
    )
    unexpected_error = re.search(
        r"\berrors?\b", error_text, re.IGNORECASE
    ) is not None
    invalid = (
        warning
        or command_lines != [expected_command_line]
        or model_reads != ["0"]
        or unexpected_error
    )
    try:
        solution_text = solution.decode("utf-8")
    except UnicodeDecodeError:
        solution_text = ""
        invalid = True
    first_solution_line = (
        solution_text.splitlines()[0] if solution_text.splitlines() else ""
    )
    optimal_solution = re.fullmatch(
        r"Optimal - objective value "
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?",
        first_solution_line,
    ) is not None
    infeasible_solution = re.fullmatch(
        r"Infeasible - objective value "
        r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?",
        first_solution_line,
    ) is not None
    if (
        pulp_status == SolverStatus.OPTIMAL
        and optimal == [_CBC_OPTIMAL_TERMINAL]
        and not infeasible
        and not forbidden
        and not invalid
        and optimal_solution
    ):
        return SolverStatus.OPTIMAL, optimal[0], False
    if (
        pulp_status == SolverStatus.INFEASIBLE
        and len(infeasible) == 1
        and not optimal
        and not forbidden
        and not invalid
        and infeasible_solution
    ):
        return SolverStatus.INFEASIBLE, infeasible[0], False
    if pulp_status == SolverStatus.TIMEOUT or _CBC_TIMEOUT_MARKER.search(log):
        return SolverStatus.TIMEOUT, None, True
    return SolverStatus.ERROR, None, True


def _objective_projection_sha256(problem: pulp.LpProblem) -> str:
    expression = problem.objective
    if expression is None:
        raise CorpusLegalFeasibilityError("CBC stage objective is absent")
    return canonical_sha256({
        "sense": int(problem.sense),
        "constant": str(expression.constant),
        "coefficients": [
            {"variable": variable.name, "coefficient": str(coefficient)}
            for variable, coefficient in sorted(
                expression.items(), key=lambda pair: pair[0].name
            )
        ],
    })


def _stage_receipt_payload(receipt: SolverStageReceipt) -> dict[str, object]:
    return {
        "stage": receipt.stage,
        "status": receipt.status.value,
        "pulp_status": receipt.pulp_status,
        "pulp_solution_status": receipt.pulp_solution_status,
        "remaining_before_microseconds": (
            receipt.remaining_before_microseconds
        ),
        "cbc_requested_microseconds": receipt.cbc_requested_microseconds,
        "host_watchdog_microseconds": receipt.host_watchdog_microseconds,
        "elapsed_microseconds": receipt.elapsed_microseconds,
        "remaining_after_microseconds": receipt.remaining_after_microseconds,
        "objective_sha256": receipt.objective_sha256,
        "witness_sha256": receipt.witness_sha256,
        "log_sha256": receipt.log_sha256,
        "log_bytes": receipt.log_bytes,
        "solution_sha256": receipt.solution_sha256,
        "solution_bytes": receipt.solution_bytes,
        "model_sha256": receipt.model_sha256,
        "model_bytes": receipt.model_bytes,
        "model_pre_exec_sha256": receipt.model_pre_exec_sha256,
        "model_post_exit_sha256": receipt.model_post_exit_sha256,
        "model_regular_exclusive_inode": (
            receipt.model_regular_exclusive_inode
        ),
        "model_path_command_bound": receipt.model_path_command_bound,
        "raw_command_sha256": receipt.raw_command_sha256,
        "exact_terminal_record": receipt.exact_terminal_record,
        "warning_or_forbidden_marker_detected": (
            receipt.warning_or_forbidden_marker_detected
        ),
        "solver_binary_sha256": receipt.solver_binary_sha256,
        "solver_options_sha256": receipt.solver_options_sha256,
    }


def _solve_cbc_stage(
    problem: pulp.LpProblem,
    *,
    stage: str,
    started_at: float,
    deadline: float,
    solver_authority: Mapping[str, object],
) -> SolverStageReceipt:
    stage_name = _strict_string(stage, label="CBC stage")
    before = time.monotonic()
    remaining = max(0.0, deadline - before)
    before_us = max(0, int(round(remaining * 1_000_000)))
    objective_sha = _objective_projection_sha256(problem)
    binary_sha = _strict_sha(
        solver_authority["binary_sha256"], label="CBC binary SHA"
    )
    options_sha = _strict_sha(
        solver_authority["options_sha256"], label="CBC options SHA"
    )
    if remaining <= 0:
        log = "NOT_STARTED: monotonic total deadline exhausted\n"
        raw = log.encode("utf-8")
        return SolverStageReceipt(
            stage=stage_name,
            status=SolverStatus.TIMEOUT,
            pulp_status=None,
            pulp_solution_status=None,
            remaining_before_microseconds=0,
            cbc_requested_microseconds=None,
            host_watchdog_microseconds=None,
            elapsed_microseconds=max(
                0, int(round((before - started_at) * 1_000_000))
            ),
            remaining_after_microseconds=0,
            objective_sha256=objective_sha,
            witness_sha256=None,
            log_sha256=sha256(raw).hexdigest(),
            log_bytes=len(raw),
            raw_cbc_log=log,
            solution_sha256=None,
            solution_bytes=0,
            raw_cbc_solution=b"",
            model_sha256=None,
            model_bytes=0,
            model_pre_exec_sha256=None,
            model_post_exit_sha256=None,
            model_regular_exclusive_inode=False,
            model_path_command_bound=False,
            raw_command_sha256=None,
            exact_terminal_record=None,
            warning_or_forbidden_marker_detected=True,
            solver_binary_sha256=binary_sha,
            solver_options_sha256=options_sha,
        )
    log = ""
    caught = False
    raw_solution = b""
    raw_model = b""
    with tempfile.TemporaryDirectory(prefix="corpus_cbc_stage_") as directory:
        evidence_directory = Path(directory)
        retained_solver: _RetainedStageCbcSolver | None = None
        try:
            retained_solver = _cbc_solver(
                absolute_deadline=deadline,
                evidence_directory=evidence_directory,
            )
            problem.solve(retained_solver)
        except (pulp.PulpSolverError, OSError, ValueError):
            caught = True
        log_path = (
            None if retained_solver is None
            else retained_solver.artifact_paths.get("log")
        )
        if log_path is not None and log_path.is_file():
            try:
                raw_log = log_path.read_bytes()
                log = raw_log.decode("utf-8")
            except (OSError, UnicodeDecodeError):
                caught = True
                raw_log = b""
        else:
            raw_log = b""
            caught = True
        if retained_solver is not None:
            solution_path = retained_solver.artifact_paths.get("sol")
            model_path = retained_solver.artifact_paths.get("mps")
            try:
                if solution_path is not None and solution_path.is_file():
                    raw_solution = solution_path.read_bytes()
                if model_path is not None and model_path.is_file():
                    raw_model = model_path.read_bytes()
            except OSError:
                caught = True
        if not raw_model:
            caught = True
        if retained_solver is not None and raw_model:
            try:
                replayed_semantics_sha = _validate_exact_integer_mps_semantics(
                    raw_model,
                    problem,
                    variables=retained_solver.model_variables,
                    variable_names=retained_solver.model_variable_names,
                    constraint_names=retained_solver.model_constraint_names,
                    objective_name=(
                        ""
                        if retained_solver.model_objective_name is None
                        else retained_solver.model_objective_name
                    ),
                )
                if replayed_semantics_sha != (
                    retained_solver.model_integer_semantics_sha256
                ):
                    caught = True
            except CorpusLegalFeasibilityError:
                caught = True
        if (
            retained_solver is None
            or retained_solver.expected_command_line is None
            or not retained_solver.model_regular_exclusive_inode
            or not retained_solver.model_path_command_bound
            or retained_solver.model_integer_semantics_sha256 is None
        ):
            caught = True
    after = time.monotonic()
    after_us = max(0, int(round(max(0.0, deadline - after) * 1_000_000)))
    elapsed_us = max(0, int(round((after - before) * 1_000_000)))
    if caught:
        status, terminal, poison = (
            (
                SolverStatus.TIMEOUT, None, True
            )
            if retained_solver is not None
            and retained_solver.watchdog_timed_out
            else (SolverStatus.ERROR, None, True)
        )
    else:
        status, terminal, poison = _classify_cbc_log(
            log,
            raw_solution,
            pulp_status=classify_pulp_status(problem),
            expected_command_line=(
                "" if retained_solver is None
                else str(retained_solver.expected_command_line)
            ),
        )
    if status in {SolverStatus.OPTIMAL, SolverStatus.INFEASIBLE} and after >= deadline:
        status, terminal, poison = SolverStatus.TIMEOUT, None, True
    return SolverStageReceipt(
        stage=stage_name,
        status=status,
        pulp_status=(None if caught else int(problem.status)),
        pulp_solution_status=(None if caught else int(problem.sol_status)),
        remaining_before_microseconds=before_us,
        cbc_requested_microseconds=(
            None
            if retained_solver is None
            else retained_solver.cbc_requested_microseconds
        ),
        host_watchdog_microseconds=(
            None
            if retained_solver is None
            else retained_solver.host_watchdog_microseconds
        ),
        elapsed_microseconds=elapsed_us,
        remaining_after_microseconds=after_us,
        objective_sha256=objective_sha,
        witness_sha256=None,
        log_sha256=sha256(raw_log).hexdigest(),
        log_bytes=len(raw_log),
        raw_cbc_log=log,
        solution_sha256=(
            None if not raw_solution else sha256(raw_solution).hexdigest()
        ),
        solution_bytes=len(raw_solution),
        raw_cbc_solution=raw_solution,
        model_sha256=sha256(raw_model).hexdigest(),
        model_bytes=len(raw_model),
        model_pre_exec_sha256=(
            None if retained_solver is None
            else retained_solver.model_pre_exec_sha256
        ),
        model_post_exit_sha256=(
            None if retained_solver is None
            else retained_solver.model_post_exit_sha256
        ),
        model_regular_exclusive_inode=(
            retained_solver is not None
            and retained_solver.model_regular_exclusive_inode
        ),
        model_path_command_bound=(
            retained_solver is not None
            and retained_solver.model_path_command_bound
        ),
        raw_command_sha256=(
            None
            if retained_solver is None
            or retained_solver.expected_command_line is None
            else sha256(
                retained_solver.expected_command_line.encode("utf-8")
            ).hexdigest()
        ),
        exact_terminal_record=terminal,
        warning_or_forbidden_marker_detected=poison,
        solver_binary_sha256=binary_sha,
        solver_options_sha256=options_sha,
    )


def _build_solver_proof(
    solver_authority: Mapping[str, object],
    stages: Sequence[SolverStageReceipt],
    *,
    total_elapsed_microseconds: int,
) -> SolverProof:
    rows = tuple(stages)
    elapsed = _strict_int(
        total_elapsed_microseconds,
        label="solver proof total elapsed microseconds",
        minimum=0,
    )
    body: dict[str, object] = {
        "schema": SOLVER_PROOF_SCHEMA,
        "solver": dict(solver_authority),
        "solver_authority_sha256": canonical_sha256(solver_authority),
        "total_deadline_seconds": SOLVER_TIMEOUT_SECONDS,
        "total_elapsed_microseconds": elapsed,
        "timeout_law": SOLVER_TIMEOUT_LAW,
        "stages": [_stage_receipt_payload(row) for row in rows],
    }
    proof_sha = canonical_sha256(body)
    return SolverProof(
        canonical_payload=canonical_json_bytes({
            **body, "proof_sha256": proof_sha,
        }),
        proof_sha256=proof_sha,
        solver_authority_sha256=canonical_sha256(solver_authority),
        total_deadline_seconds=SOLVER_TIMEOUT_SECONDS,
        total_elapsed_microseconds=elapsed,
        timeout_law=SOLVER_TIMEOUT_LAW,
        stages=rows,
    )


def _decode_binary_roster(model: FreshLegalModel) -> tuple[str, ...]:
    chosen: list[str] = []
    for player_id in sorted(model.decision):
        value = model.decision[player_id].value()
        if (
            value is None
            or not np.isfinite(float(value))
            or abs(float(value) - round(float(value)))
            > CBC_INTEGER_TOLERANCE_VALUE
        ):
            raise CorpusLegalFeasibilityError(
                "solver returned a nonintegral decision"
            )
        if int(round(float(value))) == 1:
            chosen.append(player_id)
    return audit_dk_classic(model.players, tuple(chosen))


def _objective_value_as_int(
    expression: pulp.LpAffineExpression | pulp.LpVariable | int | float,
    *,
    label: str,
) -> int:
    raw = pulp.value(expression)
    if raw is None or not np.isfinite(float(raw)):
        raise CorpusLegalFeasibilityError(f"{label} objective is absent/non-finite")
    rounded = int(round(float(raw)))
    if abs(float(raw) - rounded) > 1e-5:
        raise CorpusLegalFeasibilityError(f"{label} objective is nonintegral")
    return rounded


def default_cbc_solver(request: SolveRequest) -> SolveOutcome:
    """Exact two-stage lexicographic optimum plus uniqueness proof."""
    if not isinstance(request, SolveRequest):
        return SolveOutcome(SolverStatus.ERROR, detail="request type differs")
    if request.timeout_seconds != SOLVER_TIMEOUT_SECONDS:
        return SolveOutcome(
            SolverStatus.ERROR,
            detail="authoritative CBC requires the exact 120-second cell deadline",
        )
    try:
        solver_authority = _cbc_runtime_authority()
    except CorpusLegalFeasibilityError as exc:
        return SolveOutcome(SolverStatus.ERROR, detail=str(exc))
    started_at = time.monotonic()
    deadline = started_at + SOLVER_TIMEOUT_SECONDS
    stages: list[SolverStageReceipt] = []

    def finish(
        status: SolverStatus,
        *,
        roster: tuple[str, ...] | None = None,
        primary: int | None = None,
        secondary: int | None = None,
        radix: int | None = None,
        combined: int | None = None,
        detail: str,
    ) -> SolveOutcome:
        return SolveOutcome(
            status,
            roster=roster,
            primary_optimum_micro=primary,
            secondary_rank_sum=secondary,
            lexicographic_radix=radix,
            combined_optimum=combined,
            solver_proof=_build_solver_proof(
                solver_authority,
                stages,
                total_elapsed_microseconds=max(
                    0,
                    int(round((time.monotonic() - started_at) * 1_000_000)),
                ),
            ),
            detail=detail,
        )

    model = request.model
    problem = model.problem
    ranked_ids = tuple(sorted(model.decision))
    player_count = len(ranked_ids)
    rank_range = rw.ROSTER_SIZE * (player_count - rw.ROSTER_SIZE)
    radix = rank_range + 1
    if player_count < rw.ROSTER_SIZE or radix <= rank_range:
        return finish(
            SolverStatus.ERROR, detail="lexicographic rank range is malformed"
        )
    player_index = {
        player.player_id: index for index, player in enumerate(model.players)
    }
    rank_by_id = {
        player_id: rank + 1 for rank, player_id in enumerate(ranked_ids)
    }
    combined_coefficients = {
        player_id: request.objective_micro[player_index[player_id]] * radix
        - rank_by_id[player_id]
        for player_id in ranked_ids
    }
    if sum(sorted(
        (abs(value) for value in combined_coefficients.values()),
        reverse=True,
    )[:rw.ROSTER_SIZE]) > MAX_EXACT_CBC_INTEGER:
        return finish(
            SolverStatus.ERROR,
            radix=radix,
            detail="lexicographic combined objective exceeds exact integer range",
        )
    combined_expression = pulp.lpSum(
        combined_coefficients[player_id] * model.decision[player_id]
        for player_id in ranked_ids
    )
    problem.sense = pulp.LpMaximize
    problem.setObjective(combined_expression)
    primary_stage = _solve_cbc_stage(
        problem,
        stage="lexicographic_combined_optimum",
        started_at=started_at,
        deadline=deadline,
        solver_authority=solver_authority,
    )
    stages.append(primary_stage)
    if primary_stage.status != SolverStatus.OPTIMAL:
        return finish(
            primary_stage.status,
            radix=radix,
            detail="combined solve did not prove exact Optimal from raw CBC evidence",
        )
    try:
        selected = _decode_binary_roster(model)
        combined_optimum = _objective_value_as_int(
            combined_expression, label="combined"
        )
    except CorpusLegalFeasibilityError as exc:
        return finish(SolverStatus.ERROR, radix=radix, detail=str(exc))
    primary_optimum = sum(
        request.objective_micro[player_index[player_id]]
        for player_id in selected
    )
    rank_optimum = sum(rank_by_id[player_id] for player_id in selected)
    if combined_optimum != primary_optimum * radix - rank_optimum:
        return finish(
            SolverStatus.ERROR,
            radix=radix,
            combined=combined_optimum,
            detail="combined optimum does not reconstruct primary and rank",
        )
    stages[-1] = replace(
        stages[-1], witness_sha256=canonical_sha256(list(selected))
    )
    problem += (
        combined_expression == combined_optimum,
        "freeze_lexicographic_combined_optimum",
    )
    problem += pulp.lpSum(
        model.decision[player_id] for player_id in selected
    ) <= rw.ROSTER_SIZE - 1, "exclude_combined_witness"
    # Keep the frozen combined objective for the feasibility-only collision
    # proof.  PuLP serializes a zero objective through a synthetic dummy
    # variable whose MPS coefficient is not present in the in-memory model,
    # defeating the exact semantic replay before CBC can be classified.
    problem.setObjective(combined_expression)
    collision_stage = _solve_cbc_stage(
        problem,
        stage="combined_optimum_collision",
        started_at=started_at,
        deadline=deadline,
        solver_authority=solver_authority,
    )
    stages.append(collision_stage)
    if collision_stage.status == SolverStatus.INFEASIBLE:
        return finish(
            SolverStatus.OPTIMAL,
            roster=selected,
            primary=primary_optimum,
            secondary=rank_optimum,
            radix=radix,
            combined=combined_optimum,
            detail="unique lexicographic combined optimum",
        )
    if collision_stage.status == SolverStatus.OPTIMAL:
        try:
            collision = _decode_binary_roster(model)
            stages[-1] = replace(
                stages[-1], witness_sha256=canonical_sha256(list(collision))
            )
        except CorpusLegalFeasibilityError as exc:
            return finish(
                SolverStatus.ERROR,
                primary=primary_optimum,
                secondary=rank_optimum,
                radix=radix,
                combined=combined_optimum,
                detail=str(exc),
            )
        return finish(
            SolverStatus.AMBIGUOUS,
            primary=primary_optimum,
            secondary=rank_optimum,
            radix=radix,
            combined=combined_optimum,
            detail="combined optimum has a rank-sum collision",
        )
    return finish(
        collision_stage.status,
        primary=primary_optimum,
        secondary=rank_optimum,
        radix=radix,
        combined=combined_optimum,
        detail="combined collision proof did not terminate exactly",
    )


def _make_mock_optimal_outcome(
    request: SolveRequest, roster: Sequence[object],
) -> SolveOutcome:
    """Build strict injected-solver evidence without invoking a solver."""
    identity = audit_dk_classic(request.model.players, roster)
    index = {
        player.player_id: row for row, player in enumerate(request.model.players)
    }
    primary = sum(request.objective_micro[index[player_id]] for player_id in identity)
    rank_by_id = {
        player_id: rank + 1
        for rank, player_id in enumerate(sorted(index))
    }
    radix = rw.ROSTER_SIZE * (len(index) - rw.ROSTER_SIZE) + 1
    rank_sum = sum(rank_by_id[player_id] for player_id in identity)
    return SolveOutcome(
        SolverStatus.OPTIMAL,
        roster=identity,
        primary_optimum_micro=primary,
        secondary_rank_sum=rank_sum,
        lexicographic_radix=radix,
        combined_optimum=primary * radix - rank_sum,
        detail="injected solver proof",
    )


def _normalize_solver_outcome(
    value: object,
    *,
    request: SolveRequest,
    profile: EffectivePolicyProfile,
) -> SolveOutcome:
    if not isinstance(value, SolveOutcome) or not isinstance(value.status, SolverStatus):
        return SolveOutcome(
            SolverStatus.ERROR, detail="solver callback result type/status differs"
        )
    if type(value.detail) is not str:
        return SolveOutcome(SolverStatus.ERROR, detail="solver detail type differs")
    if value.status != SolverStatus.OPTIMAL:
        if value.roster is not None:
            return SolveOutcome(
                SolverStatus.ERROR,
                detail="non-optimal solver status carried a roster",
            )
        return value
    if (
        value.roster is None
        or type(value.primary_optimum_micro) is not int
        or type(value.secondary_rank_sum) is not int
        or type(value.lexicographic_radix) is not int
        or type(value.combined_optimum) is not int
    ):
        return SolveOutcome(
            SolverStatus.ERROR, detail="optimal solver evidence is incomplete"
        )
    try:
        identity = audit_dk_classic(request.model.players, value.roster)
        _audit_profile_compliance(request.model.players, identity, profile)
    except CorpusLegalFeasibilityError as exc:
        return SolveOutcome(SolverStatus.ERROR, detail=str(exc))
    player_index = {
        player.player_id: index
        for index, player in enumerate(request.model.players)
    }
    achieved = sum(
        request.objective_micro[player_index[player_id]] for player_id in identity
    )
    rank_by_id = {
        player_id: rank + 1
        for rank, player_id in enumerate(sorted(player_index))
    }
    rank_sum = sum(rank_by_id[player_id] for player_id in identity)
    radix = rw.ROSTER_SIZE * (
        len(request.model.players) - rw.ROSTER_SIZE
    ) + 1
    if (
        achieved != value.primary_optimum_micro
        or rank_sum != value.secondary_rank_sum
        or value.lexicographic_radix != radix
        or value.combined_optimum != achieved * radix - rank_sum
    ):
        return SolveOutcome(
            SolverStatus.ERROR,
            detail="solver objective/rank evidence does not reconstruct",
        )
    return SolveOutcome(
        SolverStatus.OPTIMAL,
        roster=identity,
        primary_optimum_micro=achieved,
        secondary_rank_sum=rank_sum,
        lexicographic_radix=radix,
        combined_optimum=achieved * radix - rank_sum,
        solver_proof=value.solver_proof,
        detail=value.detail,
    )


def _attempt_record(request: SolveRequest, outcome: SolveOutcome) -> AttemptRecord:
    return AttemptRecord(
        variant_ordinal=request.variant_ordinal,
        parameter_set_id=request.parameter_set_id,
        visit_ordinal=request.visit_ordinal,
        world=request.world,
        construction_serial=request.model.construction_serial,
        status=outcome.status,
        roster=outcome.roster,
        primary_optimum_micro=outcome.primary_optimum_micro,
        secondary_rank_sum=outcome.secondary_rank_sum,
        lexicographic_radix=outcome.lexicographic_radix,
        combined_optimum=outcome.combined_optimum,
        solver_proof=outcome.solver_proof,
        detail=outcome.detail,
    )


def _validate_authoritative_solver_proof(
    outcome: SolveOutcome,
    *,
    solver_authority_sha256: str,
) -> None:
    proof = outcome.solver_proof
    if proof is None or type(proof.canonical_payload) is not bytes:
        raise CorpusLegalFeasibilityError(
            "authoritative solver outcome lacks a canonical stage proof"
        )
    parsed = _mapping(
        _parse_canonical_json_bytes(
            proof.canonical_payload, label="authoritative solver proof"
        ),
        label="authoritative solver proof",
    )
    retained_sha = _strict_sha(
        parsed.get("proof_sha256"), label="solver proof SHA"
    )
    body = {key: parsed[key] for key in parsed if key != "proof_sha256"}
    if (
        retained_sha != canonical_sha256(body)
        or retained_sha != proof.proof_sha256
        or proof.solver_authority_sha256 != solver_authority_sha256
        or proof.total_deadline_seconds != SOLVER_TIMEOUT_SECONDS
        or proof.total_elapsed_microseconds
        != parsed.get("total_elapsed_microseconds")
        or proof.total_elapsed_microseconds < 0
        or proof.total_elapsed_microseconds
        >= SOLVER_TIMEOUT_SECONDS * 1_000_000
        or proof.timeout_law != SOLVER_TIMEOUT_LAW
        or not proof.stages
        or len(proof.stages) > MAX_SOLVER_STAGES_PER_VISIT
    ):
        raise CorpusLegalFeasibilityError(
            "authoritative solver proof identity/deadline differs"
        )
    expected_names = (
        "lexicographic_combined_optimum",
        "combined_optimum_collision",
    )
    if tuple(stage.stage for stage in proof.stages) != expected_names[:len(
        proof.stages
    )]:
        raise CorpusLegalFeasibilityError(
            "authoritative solver stage order differs"
        )
    previous_after = SOLVER_TIMEOUT_SECONDS * 1_000_000
    total_stage_elapsed = 0
    for stage in proof.stages:
        total_stage_elapsed += stage.elapsed_microseconds
        requested_us = stage.cbc_requested_microseconds
        watchdog_us = stage.host_watchdog_microseconds
        requested_text = (
            None
            if requested_us is None
            else f"{requested_us / 1_000_000:.6f}"
        )
        if (
            stage.remaining_before_microseconds < 0
            or stage.elapsed_microseconds < 0
            or stage.remaining_after_microseconds < 0
            or stage.remaining_before_microseconds > previous_after
            or stage.remaining_after_microseconds
            > stage.remaining_before_microseconds
            or stage.elapsed_microseconds
            > stage.remaining_before_microseconds
            + CLOCK_MEASUREMENT_TOLERANCE_MICROSECONDS
            or stage.solver_binary_sha256
            != parsed["solver"]["binary_sha256"]
            or stage.solver_options_sha256
            != parsed["solver"]["options_sha256"]
            or sha256(stage.raw_cbc_log.encode("utf-8")).hexdigest()
            != stage.log_sha256
            or len(stage.raw_cbc_log.encode("utf-8")) != stage.log_bytes
            or (
                None
                if not stage.raw_cbc_solution
                else sha256(stage.raw_cbc_solution).hexdigest()
            ) != stage.solution_sha256
            or len(stage.raw_cbc_solution) != stage.solution_bytes
            or (
                requested_us is not None
                and (
                    type(requested_us) is not int
                    or requested_us <= 0
                    or requested_us > stage.remaining_before_microseconds
                    or f"-sec {requested_text}" not in stage.raw_cbc_log
                )
            )
            or (
                watchdog_us is not None
                and (
                    type(watchdog_us) is not int
                    or watchdog_us <= 0
                    or requested_us is None
                    or watchdog_us > requested_us
                )
            )
        ):
            raise CorpusLegalFeasibilityError(
                "authoritative solver stage timing/content binding differs"
            )
        if stage.status in {SolverStatus.OPTIMAL, SolverStatus.INFEASIBLE} and (
            stage.warning_or_forbidden_marker_detected
            or stage.exact_terminal_record is None
            or stage.model_sha256 is None
            or stage.solution_sha256 is None
            or stage.remaining_after_microseconds <= 0
            or stage.model_pre_exec_sha256 != stage.model_sha256
            or stage.model_post_exit_sha256 != stage.model_sha256
            or not stage.model_regular_exclusive_inode
            or not stage.model_path_command_bound
            or stage.raw_command_sha256 is None
            or requested_us is None
            or watchdog_us is None
        ):
            raise CorpusLegalFeasibilityError(
                "exact solver stage lacks clean raw CBC terminal evidence"
            )
        previous_after = stage.remaining_after_microseconds
    if total_stage_elapsed >= SOLVER_TIMEOUT_SECONDS * 1_000_000:
        raise CorpusLegalFeasibilityError(
            "authoritative solver proof consumed/exceeded the total deadline"
        )
    if proof.stages:
        elapsed_at_last_terminal = (
            SOLVER_TIMEOUT_SECONDS * 1_000_000
            - proof.stages[-1].remaining_after_microseconds
        )
        if (
            proof.total_elapsed_microseconds
            + CLOCK_MEASUREMENT_TOLERANCE_MICROSECONDS
            < elapsed_at_last_terminal
            or proof.total_elapsed_microseconds
            + CLOCK_MEASUREMENT_TOLERANCE_MICROSECONDS
            < total_stage_elapsed
        ):
            raise CorpusLegalFeasibilityError(
                "solver proof total monotonic elapsed time differs"
            )
    solver = _mapping(parsed["solver"], label="solver proof authority")
    rebuilt = _build_solver_proof(
        solver,
        proof.stages,
        total_elapsed_microseconds=proof.total_elapsed_microseconds,
    )
    if rebuilt.canonical_payload != proof.canonical_payload:
        raise CorpusLegalFeasibilityError(
            "authoritative solver proof does not replay from stage receipts"
        )
    if outcome.status == SolverStatus.OPTIMAL:
        statuses = tuple(stage.status for stage in proof.stages)
        legal = statuses == (
            SolverStatus.OPTIMAL, SolverStatus.INFEASIBLE
        )
        if not legal:
            raise CorpusLegalFeasibilityError(
                "optimal cell does not carry a complete uniqueness proof"
            )


def _execute_generation_matrix_for_test(
    prepared: PreparedLaterSlate,
    inventory: Mapping[str, object],
    *,
    solver: SolverCallback,
    semantic_environment: Mapping[str, object],
    inventory_validator: InventoryValidator | None = None,
    visits_per_block: int = VISITS_PER_BLOCK,
    timeout_seconds: int = 120,
    source_columns: Sequence[object] = SOURCE_COLUMN_ORDER,
) -> GenerationMatrix:
    """Private bounded harness; it is never an execution authority."""
    snapshot = _validate_prepared_slate(prepared)
    columns = validate_outcome_blind_column_names(source_columns)
    count = _strict_int(
        visits_per_block, label="visits_per_block", minimum=1
    )
    if count > rw.WORLDS_PER_BLOCK:
        raise CorpusLegalFeasibilityError(
            "visits_per_block exceeds retained worlds per block"
        )
    timeout = _strict_int(
        timeout_seconds, label="solver timeout seconds", minimum=1
    )
    schedule = canonical_visit_schedule(
        prepared, visits_per_block=count
    )
    schedule_sha = canonical_sha256([
        {"block": world.block, "index": world.index} for world in schedule
    ])
    objectives: list[tuple[int, ...]] = []
    for world in schedule:
        column = rw.WORLD_BLOCKS.index(world.block) * rw.WORLDS_PER_BLOCK + world.index
        if snapshot.world_ids[column] != world:
            raise CorpusLegalFeasibilityError("schedule/source world identity differs")
        objectives.append(_micro_objective(
            snapshot.player_draws, world_column=column
        ))
    profiles = frozen_policy_profiles()
    frozen_inventory = _validate_inventory(
        inventory, validator=inventory_validator
    )
    if not isinstance(semantic_environment, Mapping) or any(
        type(key) is not str for key in semantic_environment
    ):
        raise CorpusLegalFeasibilityError(
            "private semantic_environment must be one explicit string-key map"
        )
    ambient_required = set(
        frozen_inventory["classified_input_projection"][
            "ambient_process_keys_requiring_absence"
        ]
    )
    ambient_present = tuple(sorted(
        set(semantic_environment) & ambient_required
    ))
    if not callable(solver):
        raise CorpusLegalFeasibilityError(
            "private test harness requires an injected solver callback"
        )
    callback: SolverCallback = solver
    all_attempts: list[AttemptRecord] = []
    generated: list[VariantGeneration] = []
    serial = 0
    for profile in profiles:
        runtime_policy = build_runtime_effective_policy(
            frozen_inventory,
            profile,
            visits_per_block=count,
            visit_schedule_sha256=schedule_sha,
            ambient_process_keys_present=ambient_present,
            inventory_validator=None,
        )
        variant_attempts: list[AttemptRecord] = []
        variant_rosters: list[tuple[str, ...]] = []
        for visit_ordinal, (world, objective) in enumerate(
            zip(schedule, objectives, strict=True)
        ):
            model = build_fresh_legal_model(
                snapshot.players,
                profile,
                objective,
                construction_serial=serial,
                model_name=(
                    f"corpus_legal_v{profile.ordinal:02d}_"
                    f"visit_{visit_ordinal:04d}"
                ),
            )
            serial += 1
            request = SolveRequest(
                variant_ordinal=profile.ordinal,
                parameter_set_id=profile.parameter_set_id,
                visit_ordinal=visit_ordinal,
                world=world,
                objective_micro=objective,
                timeout_seconds=timeout,
                model=model,
            )
            try:
                raw_outcome: object = callback(request)
            except Exception as exc:  # solver boundary must complete the matrix
                raw_outcome = SolveOutcome(
                    SolverStatus.ERROR,
                    detail=f"solver callback raised {type(exc).__name__}",
                )
            outcome = _normalize_solver_outcome(
                raw_outcome, request=request, profile=profile
            )
            record = _attempt_record(request, outcome)
            variant_attempts.append(record)
            all_attempts.append(record)
            if outcome.status == SolverStatus.OPTIMAL:
                assert outcome.roster is not None
                variant_rosters.append(outcome.roster)
        generated.append(VariantGeneration(
            profile=profile,
            runtime_policy=runtime_policy,
            attempts=tuple(variant_attempts),
            visit_rosters=tuple(variant_rosters),
        ))
    expected_cells = len(PARAMETER_SET_ORDER) * len(schedule)
    if len(all_attempts) != expected_cells or serial != expected_cells:
        raise CorpusLegalFeasibilityError("generation matrix coverage differs")
    if any(attempt.status != SolverStatus.OPTIMAL for attempt in all_attempts):
        raise BatchExecutionError(all_attempts)
    if any(
        len(variant.visit_rosters) != len(schedule)
        or tuple(attempt.world for attempt in variant.attempts) != schedule
        for variant in generated
    ):
        raise CorpusLegalFeasibilityError(
            "variant visits are not a complete matched schedule"
        )
    return TestGenerationMatrix(
        schema=SCHEMA,
        slate=snapshot,
        source_columns=columns,
        visit_schedule=schedule,
        visit_schedule_sha256=schedule_sha,
        visits_per_block=count,
        timeout_seconds=timeout,
        source_inventory_validator_applied=inventory_validator is not None,
        task_source_binding=None,
        variants=tuple(generated),
        attempts=tuple(all_attempts),
    )


def _build_authoritative_matrix_payloads(
    matrix: GenerationMatrix,
    *,
    solver_evidence_shards: Sequence[SolverEvidenceShard],
) -> GenerationMatrix:
    if matrix.task_source_binding is None or matrix.registered_law is None:
        raise CorpusLegalFeasibilityError(
            "authoritative matrix lacks source/registered-law binding"
        )
    root_payload, task_root_sha, shard_rows = _build_solver_evidence_task_root(
        solver_evidence_shards
    )
    attempt_rows = [_attempt_payload(attempt) for attempt in matrix.attempts]
    ledger_body: dict[str, object] = {
        "schema": ATTEMPT_LEDGER_SCHEMA,
        "source_binding_sha256": matrix.task_source_binding.binding_sha256,
        "registered_law_sha256": matrix.registered_law.binding_sha256,
        "visit_schedule_sha256": matrix.visit_schedule_sha256,
        "parameter_set_order": list(PARAMETER_SET_ORDER),
        "attempt_count": len(attempt_rows),
        "attempts": attempt_rows,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    ledger_sha = canonical_sha256(ledger_body)
    ledger_payload = canonical_json_bytes({
        **ledger_body, "attempt_ledger_sha256": ledger_sha,
    })
    objective_rows: list[dict[str, object]] = []
    for world in matrix.visit_schedule:
        flat = (
            rw.WORLD_BLOCKS.index(world.block) * rw.WORLDS_PER_BLOCK
            + world.index
        )
        objective_rows.append({
            "block": world.block,
            "index": world.index,
            "objective_micro_sha256": canonical_sha256(list(
                _micro_objective(matrix.slate.player_draws, world_column=flat)
            )),
        })
    matrix_body: dict[str, object] = {
        "schema": MATRIX_AUTHORITY_SCHEMA,
        "slate": {
            "season": matrix.slate.season,
            "week": matrix.slate.week,
            "slate_id": matrix.slate.slate_id,
        },
        "source_binding_sha256": matrix.task_source_binding.binding_sha256,
        "registered_law_sha256": matrix.registered_law.binding_sha256,
        "common_law_sha256": matrix.registered_law.common_law_sha256,
        "artifact_source_authority_completion_object_sha256": (
            matrix.registered_law
            .artifact_source_authority_completion_object_sha256
        ),
        "artifact_source_authority_completion_sha256": (
            matrix.registered_law.artifact_source_authority_completion_sha256
        ),
        "artifact_source_authority_task_sha256": (
            matrix.registered_law.artifact_source_authority_task_sha256
        ),
        "code_source_object_sha256": (
            matrix.registered_law.code_source_object_sha256
        ),
        "code_source_body_sha256": (
            matrix.registered_law.code_source_body_sha256
        ),
        "immutable_image_sha256": (
            matrix.registered_law.immutable_image_sha256
        ),
        "runtime_image_terminal_verification_required": (
            matrix.registered_law.runtime_image_terminal_verification_required
        ),
        "world_schedule_object_sha256": (
            matrix.registered_law.world_schedule_object_sha256
        ),
        "visit_schedule": [
            {"block": world.block, "index": world.index}
            for world in matrix.visit_schedule
        ],
        "visit_schedule_sha256": matrix.visit_schedule_sha256,
        "objective_rows": objective_rows,
        "objective_rows_sha256": canonical_sha256(objective_rows),
        "registered_dose": {
            "parameter_set_count": len(PARAMETER_SET_ORDER),
            "visits_per_block": VISITS_PER_BLOCK,
            "source_worlds_per_block": WORLDS_PER_BLOCK,
            "visits_per_parameter_set": (
                MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
            ),
            "matrix_cell_count": len(matrix.attempts),
            "selected_entry_count": ENTRY_COUNT,
            "solver_total_deadline_seconds_per_cell": SOLVER_TIMEOUT_SECONDS,
        },
        "fresh_model_construction_serials_sha256": canonical_sha256([
            attempt.construction_serial for attempt in matrix.attempts
        ]),
        "runtime_policy_sha256_by_parameter_set": [{
            "parameter_set_id": variant.profile.parameter_set_id,
            "runtime_policy_sha256": variant.runtime_policy.runtime_policy_sha256,
        } for variant in matrix.variants],
        "attempt_ledger_sha256": ledger_sha,
        "solver_evidence": {
            "codec": EVIDENCE_PACK_CODEC,
            "shard_visit_count": EVIDENCE_SHARD_VISITS,
            "shard_count": EVIDENCE_SHARDS_PER_TASK,
            "task_evidence_root_sha256": task_root_sha,
            "shard_rows_sha256": canonical_sha256([
                value for _, value in shard_rows
            ]),
        },
        "all_cells_attempted": len(matrix.attempts)
        == len(PARAMETER_SET_ORDER) * MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
        "all_cells_optimal": all(
            attempt.status == SolverStatus.OPTIMAL
            for attempt in matrix.attempts
        ),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    matrix_sha = canonical_sha256(matrix_body)
    matrix_payload = canonical_json_bytes({
        **matrix_body, "matrix_authority_sha256": matrix_sha,
    })
    return replace(
        matrix,
        canonical_attempt_ledger_payload=ledger_payload,
        attempt_ledger_sha256=ledger_sha,
        canonical_matrix_authority_payload=matrix_payload,
        matrix_authority_sha256=matrix_sha,
        solver_evidence_shard_rows=shard_rows,
        solver_evidence_task_root_payload=root_payload,
        solver_evidence_task_root_sha256=task_root_sha,
    )


def _execute_authoritative_generation(
    inputs: _AuthoritativeInputs,
    *,
    evidence_directory: Path,
    evidence_directory_fd: int,
) -> tuple[AuthoritativeGenerationMatrix, tuple[SolverEvidenceShard, ...]]:
    """Execute exact registered law; there is deliberately no callback seam."""
    snapshot = _validate_prepared_slate(inputs.source.prepared)
    columns = validate_outcome_blind_column_names(SOURCE_COLUMN_ORDER)
    schedule = _ranked_schedule_from_snapshot(
        snapshot, visits_per_block=VISITS_PER_BLOCK
    )
    schedule_sha = canonical_sha256([
        {"block": world.block, "index": world.index} for world in schedule
    ])
    if (
        schedule_sha != inputs.law.visit_schedule_sha256
        or len(schedule) != MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
    ):
        raise CorpusLegalFeasibilityError(
            "authoritative generation schedule differs from registered law"
        )
    objectives: list[tuple[int, ...]] = []
    for world in schedule:
        flat = (
            rw.WORLD_BLOCKS.index(world.block) * rw.WORLDS_PER_BLOCK
            + world.index
        )
        objectives.append(_micro_objective(
            snapshot.player_draws, world_column=flat
        ))
    profiles = frozen_policy_profiles()
    all_attempts: list[AttemptRecord] = []
    generated: list[VariantGeneration] = []
    evidence_shards: list[SolverEvidenceShard] = []
    serial = 0
    for profile in profiles:
        runtime_policy = build_runtime_effective_policy(
            inputs.inventory,
            profile,
            visits_per_block=VISITS_PER_BLOCK,
            visit_schedule_sha256=schedule_sha,
            ambient_process_keys_present=(
                inputs.ambient_process_keys_present
            ),
            inventory_validator=None,
        )
        variant_attempts: list[AttemptRecord] = []
        raw_shard_attempts: list[AttemptRecord] = []
        variant_rosters: list[tuple[str, ...]] = []
        for visit_ordinal, (world, objective) in enumerate(
            zip(schedule, objectives, strict=True)
        ):
            model = build_fresh_legal_model(
                snapshot.players,
                profile,
                objective,
                construction_serial=serial,
                model_name=(
                    f"corpus_authoritative_v{profile.ordinal:02d}_"
                    f"visit_{visit_ordinal:04d}"
                ),
            )
            serial += 1
            request = SolveRequest(
                variant_ordinal=profile.ordinal,
                parameter_set_id=profile.parameter_set_id,
                visit_ordinal=visit_ordinal,
                world=world,
                objective_micro=objective,
                timeout_seconds=SOLVER_TIMEOUT_SECONDS,
                model=model,
            )
            outcome = _normalize_solver_outcome(
                default_cbc_solver(request),
                request=request,
                profile=profile,
            )
            try:
                _validate_authoritative_solver_proof(
                    outcome,
                    solver_authority_sha256=(
                        inputs.law.solver_authority_sha256
                    ),
                )
            except CorpusLegalFeasibilityError as exc:
                outcome = SolveOutcome(
                    SolverStatus.ERROR,
                    solver_proof=outcome.solver_proof,
                    detail=f"solver proof validation failed: {exc}",
                )
            record = _attempt_record(request, outcome)
            raw_shard_attempts.append(record)
            if outcome.status == SolverStatus.OPTIMAL:
                assert outcome.roster is not None
                variant_rosters.append(outcome.roster)
            if len(raw_shard_attempts) == EVIDENCE_SHARD_VISITS:
                shard_ordinal = visit_ordinal // EVIDENCE_SHARD_VISITS
                evidence_shards.append(_build_solver_evidence_shard(
                    raw_shard_attempts,
                    variant_ordinal=profile.ordinal,
                    variant_shard_ordinal=shard_ordinal,
                    evidence_directory=evidence_directory,
                    evidence_directory_fd=evidence_directory_fd,
                ))
                compact = [
                    _compact_attempt_evidence(attempt)
                    for attempt in raw_shard_attempts
                ]
                variant_attempts.extend(compact)
                all_attempts.extend(compact)
                raw_shard_attempts.clear()
        if raw_shard_attempts:
            raise CorpusLegalFeasibilityError(
                "authoritative evidence shard ended at a partial boundary"
            )
        generated.append(VariantGeneration(
            profile=profile,
            runtime_policy=runtime_policy,
            attempts=tuple(variant_attempts),
            visit_rosters=tuple(variant_rosters),
        ))
    expected_cells = len(PARAMETER_SET_ORDER) * len(schedule)
    matrix = AuthoritativeGenerationMatrix(
        schema=SCHEMA,
        slate=snapshot,
        source_columns=columns,
        visit_schedule=schedule,
        visit_schedule_sha256=schedule_sha,
        visits_per_block=VISITS_PER_BLOCK,
        timeout_seconds=SOLVER_TIMEOUT_SECONDS,
        source_inventory_validator_applied=True,
        task_source_binding=inputs.source.binding,
        variants=tuple(generated),
        attempts=tuple(all_attempts),
        registered_law=inputs.law,
    )
    if len(all_attempts) != expected_cells or serial != expected_cells:
        raise CorpusLegalFeasibilityError(
            "authoritative generation did not attempt the complete matrix"
        )
    matrix = _build_authoritative_matrix_payloads(
        matrix,
        solver_evidence_shards=evidence_shards,
    )
    if any(attempt.status != SolverStatus.OPTIMAL for attempt in all_attempts):
        raise BatchExecutionError(
            all_attempts,
            generation_matrix=matrix,
            solver_evidence_shards=evidence_shards,
        )
    if any(
        len(variant.visit_rosters) != len(schedule)
        for variant in generated
    ):
        raise CorpusLegalFeasibilityError(
            "authoritative variant roster coverage differs"
        )
    return matrix, tuple(evidence_shards)


def first_occurrence_unique(
    rosters: Sequence[Sequence[object]],
) -> tuple[tuple[tuple[str, ...], ...], tuple[int, ...]]:
    """Return exact-roster unique union in first visit occurrence order."""
    unique: list[tuple[str, ...]] = []
    first_indices: list[int] = []
    seen: set[tuple[str, ...]] = set()
    for index, roster in enumerate(rosters):
        if isinstance(roster, (str, bytes)) or not isinstance(roster, Sequence):
            raise CorpusLegalFeasibilityError("dedup roster is malformed")
        identity = tuple(
            _strict_string(value, label="dedup roster id") for value in roster
        )
        if (
            identity != tuple(sorted(identity))
            or len(identity) != rw.ROSTER_SIZE
            or len(set(identity)) != rw.ROSTER_SIZE
        ):
            raise CorpusLegalFeasibilityError(
                "dedup roster must be canonical nine-id identity"
            )
        if identity in seen:
            continue
        seen.add(identity)
        unique.append(identity)
        first_indices.append(index)
    return tuple(unique), tuple(first_indices)


def cross_score_full_union(
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    rosters: Sequence[Sequence[object]],
    *,
    expected_worlds: int | None = None,
) -> np.ndarray:
    """Cross-score every unique roster on the one common simulated-world law."""
    rows = tuple(players)
    matrix = np.asarray(player_draws)
    if (
        matrix.dtype != np.dtype(np.float32)
        or matrix.ndim != 2
        or matrix.shape[0] != len(rows)
        or not np.isfinite(matrix).all()
    ):
        raise CorpusLegalFeasibilityError("cross-score player matrix differs")
    if expected_worlds is not None and matrix.shape[1] != expected_worlds:
        raise CorpusLegalFeasibilityError("cross-score world count differs")
    identities = tuple(audit_dk_classic(rows, roster) for roster in rosters)
    if not identities or len(set(identities)) != len(identities):
        raise CorpusLegalFeasibilityError(
            "cross-score roster union is empty or duplicated"
        )
    index = {player.player_id: row for row, player in enumerate(rows)}
    scores = np.empty((len(identities), matrix.shape[1]), dtype=np.float64)
    for candidate_index, roster in enumerate(identities):
        player_rows = [index[player_id] for player_id in roster]
        scores[candidate_index] = matrix[player_rows].sum(
            axis=0, dtype=np.float64
        )
    if not np.isfinite(scores).all():
        raise CorpusLegalFeasibilityError("cross-score totals are non-finite")
    scores.flags.writeable = False
    return scores


def _score_matrix_sha256(scores: np.ndarray) -> str:
    matrix = np.ascontiguousarray(scores, dtype="<f8")
    header = canonical_json_bytes({
        "dtype": "float64-le",
        "shape": list(matrix.shape),
    })
    digest = sha256()
    digest.update(header)
    digest.update(b"\0")
    digest.update(memoryview(matrix).cast("B"))
    return digest.hexdigest()


def select_exact80(
    candidate_scores: np.ndarray,
    *,
    entries: int = ENTRY_COUNT,
    tail_line_dk: float = TAIL_LINE_DK,
) -> SelectorReceipt:
    """Greedy line coverage with explicit first-occurrence terminal ties."""
    scores = np.asarray(candidate_scores)
    entry_count = _strict_int(entries, label="selector entries", minimum=1)
    if (
        scores.ndim != 2
        or scores.shape[1] == 0
        or scores.shape[0] < entry_count
        or not np.isfinite(scores).all()
    ):
        raise InsufficientCandidateSupport(
            "selector requires one finite candidate matrix with at least exact-80"
        )
    if type(tail_line_dk) not in (int, float) or isinstance(tail_line_dk, bool):
        raise CorpusLegalFeasibilityError("selector tail line must be numeric")
    tail_line = float(tail_line_dk)
    if not np.isfinite(tail_line):
        raise CorpusLegalFeasibilityError("selector tail line must be finite")
    clears = scores >= tail_line
    packed = np.packbits(clears, axis=1, bitorder="little")
    p_line = clears.mean(axis=1, dtype=np.float64)
    mean_score = scores.mean(axis=1, dtype=np.float64)
    byte_popcount = np.unpackbits(
        np.arange(256, dtype=np.uint8)[:, None], axis=1
    ).sum(axis=1, dtype=np.uint8)
    covered = np.zeros(packed.shape[1], dtype=np.uint8)
    remaining = list(range(scores.shape[0]))
    selected: list[int] = []
    while len(selected) < entry_count and remaining:
        gains = byte_popcount[
            np.bitwise_and(packed, np.bitwise_not(covered))
        ].sum(axis=1, dtype=np.int64)
        best = max(
            remaining,
            key=lambda index: (
                int(gains[index]),
                float(p_line[index]),
                float(mean_score[index]),
                -index,
            ),
        )
        if int(gains[best]) == 0:
            break
        selected.append(best)
        covered |= packed[best]
        remaining.remove(best)
    fill = sorted(
        remaining,
        key=lambda index: (
            -float(p_line[index]),
            -float(mean_score[index]),
            index,
        ),
    )
    selected.extend(fill[:entry_count - len(selected)])
    if len(selected) != entry_count or len(set(selected)) != entry_count:
        raise InsufficientCandidateSupport("selector did not return exact unique entries")
    return SelectorReceipt(
        candidate_count=scores.shape[0],
        world_count=scores.shape[1],
        entry_count=entry_count,
        tail_line_dk=tail_line,
        selected_indices=tuple(selected),
        tie_law_applied="gain,p_line,mean_score,first_occurrence",
    )


def _violation_counts(
    players: Sequence[rw.PlayerSpec],
    rosters: Sequence[tuple[str, ...]],
) -> tuple[tuple[str, int], ...]:
    counts = Counter({name: 0 for name in PARAMETER_ORDER})
    for roster in rosters:
        counts.update(house_rule_violations(players, roster))
    return tuple((name, counts[name]) for name in PARAMETER_ORDER)


def _validate_generation_matrix_authority(matrix: GenerationMatrix) -> None:
    if not isinstance(matrix, GenerationMatrix) or matrix.schema != SCHEMA:
        raise CorpusLegalFeasibilityError("generation matrix schema/type differs")
    count = _strict_int(
        matrix.visits_per_block, label="matrix visits_per_block", minimum=1
    )
    if count > rw.WORLDS_PER_BLOCK:
        raise CorpusLegalFeasibilityError(
            "matrix visits_per_block exceeds retained worlds"
        )
    expected_schedule = _ranked_schedule_from_snapshot(
        matrix.slate, visits_per_block=count
    )
    expected_schedule_sha = canonical_sha256([
        {"block": world.block, "index": world.index}
        for world in expected_schedule
    ])
    expected_profiles = frozen_policy_profiles()
    expected_cells = len(expected_profiles) * len(expected_schedule)
    if (
        matrix.visit_schedule != expected_schedule
        or matrix.visit_schedule_sha256 != expected_schedule_sha
        or len(matrix.variants) != len(expected_profiles)
        or len(matrix.attempts) != expected_cells
        or [attempt.construction_serial for attempt in matrix.attempts]
        != list(range(expected_cells))
        or any(attempt.status != SolverStatus.OPTIMAL for attempt in matrix.attempts)
    ):
        raise CorpusLegalFeasibilityError(
            "generation matrix schedule/coverage authority differs"
        )
    flattened: list[AttemptRecord] = []
    for expected_profile, variant in zip(
        expected_profiles, matrix.variants, strict=True
    ):
        if (
            variant.profile != expected_profile
            or len(variant.attempts) != len(expected_schedule)
            or len(variant.visit_rosters) != len(expected_schedule)
            or tuple(attempt.world for attempt in variant.attempts)
            != expected_schedule
            or tuple(attempt.roster for attempt in variant.attempts)
            != variant.visit_rosters
            or any(
                attempt.variant_ordinal != expected_profile.ordinal
                or attempt.parameter_set_id
                != expected_profile.parameter_set_id
                for attempt in variant.attempts
            )
        ):
            raise CorpusLegalFeasibilityError(
                "generation variant authority differs"
            )
        try:
            runtime_payload = json.loads(
                variant.runtime_policy.canonical_payload.decode("utf-8"),
                object_pairs_hook=lambda pairs: _duplicate_safe_object(pairs),
                parse_constant=lambda value: _reject_nonfinite_constant(value),
            )
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CorpusLegalFeasibilityError(
                "generation runtime policy is not valid JSON"
            ) from exc
        if (
            canonical_json_bytes(runtime_payload)
            != variant.runtime_policy.canonical_payload
            or sha256(variant.runtime_policy.canonical_payload).hexdigest()
            != variant.runtime_policy.runtime_policy_sha256
            or runtime_payload.get("parameter_set")
            != expected_profile.as_payload()
            or runtime_payload.get("experimental_rule_set_sha256")
            != variant.runtime_policy.experimental_rule_set_sha256
            or runtime_payload.get("experimental_rules")
            != _experimental_rule_projection(
                visits_per_block=matrix.visits_per_block,
                visit_schedule_sha256=matrix.visit_schedule_sha256,
            )
        ):
            raise CorpusLegalFeasibilityError(
                "generation runtime-policy authority differs"
            )
        flattened.extend(variant.attempts)
    if tuple(flattened) != matrix.attempts:
        raise CorpusLegalFeasibilityError(
            "generation attempt flattening/order differs"
        )


def _attempt_payload(attempt: AttemptRecord) -> dict[str, object]:
    solver_proof = (
        None
        if attempt.solver_proof is None
        else _parse_canonical_json_bytes(
            attempt.solver_proof.canonical_payload,
            label="attempt solver proof",
        )
    )
    return {
        "variant_ordinal": attempt.variant_ordinal,
        "parameter_set_id": attempt.parameter_set_id,
        "visit_ordinal": attempt.visit_ordinal,
        "world": {"block": attempt.world.block, "index": attempt.world.index},
        "construction_serial": attempt.construction_serial,
        "status": attempt.status.value,
        "roster": None if attempt.roster is None else list(attempt.roster),
        "primary_optimum_micro": attempt.primary_optimum_micro,
        "secondary_rank_sum": attempt.secondary_rank_sum,
        "lexicographic_radix": attempt.lexicographic_radix,
        "combined_optimum": attempt.combined_optimum,
        "solver_proof": solver_proof,
        "detail": attempt.detail,
    }


def _build_solver_evidence_shard(
    attempts: Sequence[AttemptRecord],
    *,
    variant_ordinal: int,
    variant_shard_ordinal: int,
    evidence_directory: Path,
    evidence_directory_fd: int,
) -> SolverEvidenceShard:
    rows = tuple(attempts)
    variant = _strict_int(variant_ordinal, label="evidence variant", minimum=0)
    shard = _strict_int(
        variant_shard_ordinal, label="evidence variant shard", minimum=0
    )
    visit_start = shard * EVIDENCE_SHARD_VISITS
    visit_stop = visit_start + EVIDENCE_SHARD_VISITS
    if (
        variant >= len(PARAMETER_SET_ORDER)
        or shard >= EVIDENCE_SHARDS_PER_VARIANT
        or len(rows) != EVIDENCE_SHARD_VISITS
        or tuple(attempt.variant_ordinal for attempt in rows)
        != (variant,) * EVIDENCE_SHARD_VISITS
        or tuple(attempt.visit_ordinal for attempt in rows)
        != tuple(range(visit_start, visit_stop))
    ):
        raise CorpusLegalFeasibilityError(
            "solver evidence shard coverage/order differs"
        )
    uncompressed = bytearray()
    members: list[dict[str, object]] = []
    stages: list[dict[str, object]] = []
    attempt_roots: list[dict[str, object]] = []
    for local_attempt, attempt in enumerate(rows):
        proof = attempt.solver_proof
        if proof is not None and len(proof.stages) not in (1, 2):
            raise CorpusLegalFeasibilityError(
                "evidence-shard attempt exceeds bounded stage proof"
            )
        stage_roots: list[str] = []
        proof_stages = () if proof is None else proof.stages
        for local_stage, stage in enumerate(proof_stages):
            stage_ordinal = len(stages)
            log_raw = stage.raw_cbc_log.encode("utf-8")
            solution_raw = stage.raw_cbc_solution
            if (
                len(log_raw) != stage.log_bytes
                or sha256(log_raw).hexdigest() != stage.log_sha256
                or len(solution_raw) != stage.solution_bytes
                or (None if not solution_raw else sha256(solution_raw).hexdigest())
                != stage.solution_sha256
                or len(log_raw) + len(solution_raw)
                > MAX_SOLVER_EVIDENCE_BYTES_PER_STAGE
            ):
                raise CorpusLegalFeasibilityError(
                    "evidence-shard raw member identity differs"
                )
            member_ordinals: list[int] = []
            for member_type, raw in (
                ("cbc_log_utf8", log_raw),
                ("cbc_solution_utf8", solution_raw),
            ):
                ordinal = len(members)
                offset = len(uncompressed)
                uncompressed.extend(raw)
                members.append({
                    "member_ordinal": ordinal,
                    "stage_ordinal": stage_ordinal,
                    "member_type": member_type,
                    "offset": offset,
                    "length": len(raw),
                    "sha256": sha256(raw).hexdigest(),
                })
                member_ordinals.append(ordinal)
            stage_payload = _stage_receipt_payload(stage)
            stage_root = canonical_sha256(stage_payload)
            stage_roots.append(stage_root)
            stages.append({
                "stage_ordinal": stage_ordinal,
                "local_attempt_ordinal": local_attempt,
                "global_attempt_ordinal": (
                    variant * MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
                    + attempt.visit_ordinal
                ),
                "local_stage_ordinal": local_stage,
                "stage_receipt_sha256": stage_root,
                "stage_receipt": stage_payload,
                "log_member_ordinal": member_ordinals[0],
                "solution_member_ordinal": member_ordinals[1],
            })
        attempt_roots.append({
            "local_attempt_ordinal": local_attempt,
            "visit_ordinal": attempt.visit_ordinal,
            "solver_proof_sha256": (
                None if proof is None else proof.proof_sha256
            ),
            "stage_receipt_sha256": stage_roots,
        })
    if (
        len(stages) > MAX_SHARD_SOLVER_STAGE_COUNT
        or len(uncompressed) > MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES
    ):
        raise CorpusLegalFeasibilityError(
            "solver evidence shard exceeds its fixed bound"
        )
    raw = bytes(uncompressed)
    compressed = zlib.compress(raw, level=9)
    global_shard = variant * EVIDENCE_SHARDS_PER_VARIANT + shard
    compressed_basename = f"shard-{global_shard:03d}.zlib"
    index_basename = f"shard-{global_shard:03d}.index.json"
    body: dict[str, object] = {
        "schema": "corpus-cbc-evidence-shard-index/v1",
        "codec": EVIDENCE_PACK_CODEC,
        "zlib_runtime_version": zlib.ZLIB_VERSION,
        "compressed_object_basename": compressed_basename,
        "index_object_basename": index_basename,
        "global_shard_ordinal": global_shard,
        "variant_ordinal": variant,
        "variant_shard_ordinal": shard,
        "visit_start": visit_start,
        "visit_stop": visit_stop,
        "attempt_count": len(rows),
        "stage_count": len(stages),
        "member_count": len(members),
        "compressed_sha256": sha256(compressed).hexdigest(),
        "compressed_bytes": len(compressed),
        "uncompressed_sha256": sha256(raw).hexdigest(),
        "uncompressed_bytes": len(raw),
        "maximum_uncompressed_bytes": (
            MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES
        ),
        "attempt_roots": attempt_roots,
        "stages": stages,
        "members": members,
    }
    index_sha = canonical_sha256(body)
    index_payload = canonical_json_bytes({
        **body, "evidence_index_sha256": index_sha,
    })
    if len(index_payload) > MAX_SHARD_SOLVER_EVIDENCE_INDEX_BYTES:
        raise CorpusLegalFeasibilityError(
            "solver evidence shard index exceeds its fixed bound"
        )
    shard_root = canonical_sha256({
        "global_shard_ordinal": global_shard,
        "compressed_sha256": body["compressed_sha256"],
        "compressed_bytes": body["compressed_bytes"],
        "index_sha256": index_sha,
        "index_object_sha256": sha256(index_payload).hexdigest(),
        "index_bytes": len(index_payload),
        "attempt_roots_sha256": canonical_sha256(attempt_roots),
    })
    (
        compressed_path,
        compressed_sha,
        compressed_size,
        compressed_device,
        compressed_inode,
    ) = _write_create_once_evidence_file(
        compressed,
        evidence_directory=evidence_directory,
        directory_fd=evidence_directory_fd,
        basename=compressed_basename,
        maximum_bytes=MAX_SHARD_SOLVER_EVIDENCE_COMPRESSED_BYTES,
    )
    index_path, written_index_sha, index_size, index_device, index_inode = (
        _write_create_once_evidence_file(
            index_payload,
            evidence_directory=evidence_directory,
            directory_fd=evidence_directory_fd,
            basename=index_basename,
            maximum_bytes=MAX_SHARD_SOLVER_EVIDENCE_INDEX_BYTES,
        )
    )
    if (
        compressed_sha != body["compressed_sha256"]
        or compressed_size != body["compressed_bytes"]
        or written_index_sha != sha256(index_payload).hexdigest()
        or index_size != len(index_payload)
    ):
        raise CorpusLegalFeasibilityError(
            "create-once solver evidence file identity differs"
        )
    return SolverEvidenceShard(
        global_shard_ordinal=global_shard,
        variant_ordinal=variant,
        variant_shard_ordinal=shard,
        visit_start=visit_start,
        visit_stop=visit_stop,
        compressed_path=compressed_path,
        compressed_sha256=compressed_sha,
        compressed_bytes=compressed_size,
        compressed_device=compressed_device,
        compressed_inode=compressed_inode,
        uncompressed_sha256=str(body["uncompressed_sha256"]),
        uncompressed_bytes=len(raw),
        index_path=index_path,
        index_sha256=index_sha,
        index_object_sha256=written_index_sha,
        index_bytes=index_size,
        index_device=index_device,
        index_inode=index_inode,
        shard_root_sha256=shard_root,
    )


def _compact_attempt_evidence(attempt: AttemptRecord) -> AttemptRecord:
    proof = attempt.solver_proof
    if proof is None:
        return attempt
    compact_stages = tuple(replace(
        stage, raw_cbc_log="", raw_cbc_solution=b""
    ) for stage in proof.stages)
    return replace(attempt, solver_proof=replace(proof, stages=compact_stages))


def _build_solver_evidence_task_root(
    shards: Sequence[SolverEvidenceShard],
) -> tuple[bytes, str, tuple[tuple[str, object], ...]]:
    rows = tuple(shards)
    if (
        len(rows) != EVIDENCE_SHARDS_PER_TASK
        or tuple(row.global_shard_ordinal for row in rows)
        != tuple(range(EVIDENCE_SHARDS_PER_TASK))
    ):
        raise CorpusLegalFeasibilityError(
            "solver evidence task shard coverage differs"
        )
    shard_rows = [{
        "global_shard_ordinal": row.global_shard_ordinal,
        "variant_ordinal": row.variant_ordinal,
        "variant_shard_ordinal": row.variant_shard_ordinal,
        "visit_start": row.visit_start,
        "visit_stop": row.visit_stop,
        "compressed_sha256": row.compressed_sha256,
        "compressed_bytes": row.compressed_bytes,
        "uncompressed_sha256": row.uncompressed_sha256,
        "uncompressed_bytes": row.uncompressed_bytes,
        "index_sha256": row.index_sha256,
        "index_object_sha256": row.index_object_sha256,
        "index_bytes": row.index_bytes,
        "compressed_object_basename": row.compressed_path.name,
        "index_object_basename": row.index_path.name,
        "shard_root_sha256": row.shard_root_sha256,
    } for row in rows]
    body: dict[str, object] = {
        "schema": "corpus-cbc-evidence-task-root/v1",
        "shard_visit_count": EVIDENCE_SHARD_VISITS,
        "shards_per_variant": EVIDENCE_SHARDS_PER_VARIANT,
        "shard_count": EVIDENCE_SHARDS_PER_TASK,
        "shards": shard_rows,
    }
    task_root = canonical_sha256(body)
    payload = canonical_json_bytes({
        **body, "task_evidence_root_sha256": task_root,
    })
    return (
        payload,
        task_root,
        tuple((str(row["global_shard_ordinal"]), row) for row in shard_rows),
    )


def _reopen_solver_evidence_shard(
    shard: SolverEvidenceShard,
) -> Mapping[str, object]:
    """Reopen one descriptor and bind both local files to its index/root."""
    expected_global = (
        shard.variant_ordinal * EVIDENCE_SHARDS_PER_VARIANT
        + shard.variant_shard_ordinal
    )
    if (
        shard.global_shard_ordinal != expected_global
        or shard.visit_start
        != shard.variant_shard_ordinal * EVIDENCE_SHARD_VISITS
        or shard.visit_stop != shard.visit_start + EVIDENCE_SHARD_VISITS
        or shard.compressed_path.name
        != f"shard-{expected_global:03d}.zlib"
        or shard.index_path.name
        != f"shard-{expected_global:03d}.index.json"
    ):
        raise CorpusLegalFeasibilityError(
            "local solver evidence shard descriptor order differs"
        )
    compressed_sha, compressed_size, _, _ = _hash_regular_evidence_file(
        shard.compressed_path,
        expected_device=shard.compressed_device,
        expected_inode=shard.compressed_inode,
        expected_size=shard.compressed_bytes,
        maximum_bytes=MAX_SHARD_SOLVER_EVIDENCE_COMPRESSED_BYTES,
    )
    index_raw = _read_regular_evidence_file(
        shard.index_path,
        expected_device=shard.index_device,
        expected_inode=shard.index_inode,
        expected_size=shard.index_bytes,
        maximum_bytes=MAX_SHARD_SOLVER_EVIDENCE_INDEX_BYTES,
    )
    index_object_sha = sha256(index_raw).hexdigest()
    parsed = _mapping(
        _parse_canonical_json_bytes(
            index_raw, label="local solver evidence shard index"
        ),
        label="local solver evidence shard index",
    )
    if "evidence_index_sha256" not in parsed:
        raise CorpusLegalFeasibilityError(
            "local solver evidence index self-hash is missing"
        )
    index_body = {
        key: parsed[key] for key in parsed if key != "evidence_index_sha256"
    }
    if (
        compressed_sha != shard.compressed_sha256
        or compressed_size != shard.compressed_bytes
        or index_object_sha != shard.index_object_sha256
        or parsed["evidence_index_sha256"] != shard.index_sha256
        or canonical_sha256(index_body) != shard.index_sha256
        or parsed.get("schema") != "corpus-cbc-evidence-shard-index/v1"
        or parsed.get("codec") != EVIDENCE_PACK_CODEC
        or parsed.get("global_shard_ordinal") != shard.global_shard_ordinal
        or parsed.get("variant_ordinal") != shard.variant_ordinal
        or parsed.get("variant_shard_ordinal")
        != shard.variant_shard_ordinal
        or parsed.get("visit_start") != shard.visit_start
        or parsed.get("visit_stop") != shard.visit_stop
        or parsed.get("compressed_object_basename")
        != shard.compressed_path.name
        or parsed.get("index_object_basename") != shard.index_path.name
        or parsed.get("compressed_sha256") != shard.compressed_sha256
        or parsed.get("compressed_bytes") != shard.compressed_bytes
        or parsed.get("uncompressed_sha256") != shard.uncompressed_sha256
        or parsed.get("uncompressed_bytes") != shard.uncompressed_bytes
        or parsed.get("maximum_uncompressed_bytes")
        != MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES
    ):
        raise CorpusLegalFeasibilityError(
            "local solver evidence shard/index identity differs"
        )
    expected_root = canonical_sha256({
        "global_shard_ordinal": shard.global_shard_ordinal,
        "compressed_sha256": shard.compressed_sha256,
        "compressed_bytes": shard.compressed_bytes,
        "index_sha256": shard.index_sha256,
        "index_object_sha256": shard.index_object_sha256,
        "index_bytes": shard.index_bytes,
        "attempt_roots_sha256": canonical_sha256(
            parsed.get("attempt_roots")
        ),
    })
    if expected_root != shard.shard_root_sha256:
        raise CorpusLegalFeasibilityError(
            "local solver evidence shard root differs"
        )
    return parsed


def _runtime_binding_payload(
    binding: RuntimePolicyBinding,
) -> dict[str, object]:
    return {
        "runtime_policy_sha256": binding.runtime_policy_sha256,
        "inventory_sha256": binding.inventory_sha256,
        "source_set_id": binding.source_set_id,
        "source_set_sha256": binding.source_set_sha256,
        "rule_universe_sha256": binding.rule_universe_sha256,
        "rule_count": binding.rule_count,
        "classified_input_projection_sha256": (
            binding.classified_input_projection_sha256
        ),
        "classified_input_runtime_proof_sha256": (
            binding.classified_input_runtime_proof_sha256
        ),
        "experimental_rule_set_sha256": (
            binding.experimental_rule_set_sha256
        ),
        "dk_classic_feasibility_only": binding.dk_classic_feasibility_only,
    }


def _selector_payload(selector: SelectorReceipt) -> dict[str, object]:
    return {
        "candidate_count": selector.candidate_count,
        "world_count": selector.world_count,
        "entry_count": selector.entry_count,
        "tail_line_dk": selector.tail_line_dk,
        "selected_indices": list(selector.selected_indices),
        "tie_law_applied": selector.tie_law_applied,
    }


def _census_payload(census: ViolationCensus) -> dict[str, object]:
    return {
        "unique_candidate_counts": dict(census.unique_candidate_counts),
        "visit_counts": dict(census.visit_counts),
        "selected_counts": dict(census.selected_counts),
    }


def _build_variant_result_payload(
    *,
    matrix: GenerationMatrix,
    variant: VariantGeneration,
    unique: tuple[tuple[str, ...], ...],
    first_indices: tuple[int, ...],
    candidate_score_sha256: str,
    selector: SelectorReceipt,
    selected_rosters: tuple[tuple[str, ...], ...],
    selected_score_sha256: str,
    census: ViolationCensus,
) -> tuple[bytes, str]:
    attempt_rows = [_attempt_payload(attempt) for attempt in variant.attempts]
    body: dict[str, object] = {
        "schema": VARIANT_RESULT_SCHEMA,
        "slate": {
            "season": matrix.slate.season,
            "week": matrix.slate.week,
            "slate_id": matrix.slate.slate_id,
        },
        "later_source_freeze_manifest_sha256": (
            matrix.slate.source_freeze_sha256
        ),
        "artifact_sha256_by_block": dict(
            matrix.slate.artifact_sha256_by_block
        ),
        "task_source_binding": (
            None if matrix.task_source_binding is None else {
                "binding_sha256": matrix.task_source_binding.binding_sha256,
                "batch_manifest_sha256": (
                    matrix.task_source_binding.batch_manifest_sha256
                ),
                "task_index": matrix.task_source_binding.task_index,
                "task_sha256": matrix.task_source_binding.task_sha256,
                "artifact_source_authority_completion_object_sha256": (
                    matrix.task_source_binding
                    .artifact_source_authority_completion_object_sha256
                ),
                "artifact_source_authority_completion_sha256": (
                    matrix.task_source_binding
                    .artifact_source_authority_completion_sha256
                ),
                "artifact_source_authority_task_sha256": (
                    matrix.task_source_binding
                    .artifact_source_authority_task_sha256
                ),
                "later_source_freeze_manifest_sha256": (
                    matrix.task_source_binding.later_source_freeze_manifest_sha256
                ),
                "world_artifact_receipt_set_sha256": (
                    matrix.task_source_binding.world_artifact_receipt_set_sha256
                ),
            }
        ),
        "visit_schedule_sha256": matrix.visit_schedule_sha256,
        "attempt_ledger_sha256": matrix.attempt_ledger_sha256,
        "matrix_authority_sha256": matrix.matrix_authority_sha256,
        "solver_evidence_task_root_sha256": (
            matrix.solver_evidence_task_root_sha256
        ),
        "profile": variant.profile.as_payload(),
        "runtime_effective_policy": _runtime_binding_payload(
            variant.runtime_policy
        ),
        "coverage": {
            "scheduled_visits": len(matrix.visit_schedule),
            "attempted_visits": len(variant.attempts),
            "optimal_visits": sum(
                attempt.status == SolverStatus.OPTIMAL
                for attempt in variant.attempts
            ),
            "unique_candidates": len(unique),
            "selected_entries": len(selected_rosters),
        },
        "variant_attempt_rows_sha256": canonical_sha256(attempt_rows),
        "visit_rosters": [list(roster) for roster in variant.visit_rosters],
        "unique_rosters": [list(roster) for roster in unique],
        "first_occurrence_visit_indices": list(first_indices),
        "candidate_score_sha256": candidate_score_sha256,
        "selector": _selector_payload(selector),
        "selected_rosters": [list(roster) for roster in selected_rosters],
        "selected_score_sha256": selected_score_sha256,
        "house_rule_violation_census": _census_payload(census),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    result_sha = canonical_sha256(body)
    payload = {**body, "result_sha256": result_sha}
    return canonical_json_bytes(payload), result_sha


def validate_canonical_variant_result(
    result: VariantScienceResult,
    *,
    matrix: GenerationMatrix,
    generation: VariantGeneration,
) -> None:
    if not isinstance(result, VariantScienceResult):
        raise CorpusLegalFeasibilityError("variant result type differs")
    if not isinstance(matrix, GenerationMatrix) or not isinstance(
        generation, VariantGeneration
    ):
        raise CorpusLegalFeasibilityError(
            "variant replay authorities have wrong type"
        )
    if (
        result.profile != generation.profile
        or result.runtime_policy != generation.runtime_policy
        or result.attempts != generation.attempts
        or result.visit_rosters != generation.visit_rosters
    ):
        raise CorpusLegalFeasibilityError(
            "variant result differs from its generation authority"
        )
    unique, first_indices = first_occurrence_unique(generation.visit_rosters)
    if (
        result.unique_rosters != unique
        or result.first_occurrence_visit_indices != first_indices
    ):
        raise CorpusLegalFeasibilityError(
            "variant first-occurrence union does not replay"
        )
    for roster in unique:
        _audit_profile_compliance(matrix.slate.players, roster, result.profile)
    scores = cross_score_full_union(
        matrix.slate.players,
        matrix.slate.player_draws,
        unique,
        expected_worlds=EXPECTED_WORLD_COUNT,
    )
    candidate_score_sha = _score_matrix_sha256(scores)
    selector = select_exact80(scores)
    selected_rosters = tuple(
        unique[index] for index in selector.selected_indices
    )
    selected_scores = np.ascontiguousarray(
        scores[np.asarray(selector.selected_indices, dtype=np.int64)],
        dtype=np.float64,
    )
    selected_scores.flags.writeable = False
    census = ViolationCensus(
        unique_candidate_counts=_violation_counts(
            matrix.slate.players, unique
        ),
        visit_counts=_violation_counts(
            matrix.slate.players, generation.visit_rosters
        ),
        selected_counts=_violation_counts(
            matrix.slate.players, selected_rosters
        ),
    )
    if (
        result.candidate_score_sha256 != candidate_score_sha
        or result.selector != selector
        or result.selected_rosters != selected_rosters
        or result.house_rule_census != census
        or type(result.selected_scores) is not np.ndarray
        or result.selected_scores.dtype != np.dtype(np.float64)
        or result.selected_scores.flags.writeable
        or not np.array_equal(result.selected_scores, selected_scores)
    ):
        raise CorpusLegalFeasibilityError(
            "variant scores/selector/census do not replay"
        )
    rebuilt_payload, rebuilt_sha = _build_variant_result_payload(
        matrix=matrix,
        variant=generation,
        unique=unique,
        first_indices=first_indices,
        candidate_score_sha256=candidate_score_sha,
        selector=selector,
        selected_rosters=selected_rosters,
        selected_score_sha256=_score_matrix_sha256(selected_scores),
        census=census,
    )
    try:
        parsed = json.loads(
            result.canonical_result_payload.decode("utf-8"),
            object_pairs_hook=lambda pairs: _duplicate_safe_object(pairs),
            parse_constant=lambda value: _reject_nonfinite_constant(value),
        )
    except CorpusLegalFeasibilityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusLegalFeasibilityError(
            "variant result payload is not valid JSON"
        ) from exc
    if canonical_json_bytes(parsed) != result.canonical_result_payload:
        raise CorpusLegalFeasibilityError(
            "variant result payload is not canonical"
        )
    item = _mapping(parsed, label="variant result payload")
    retained_sha = _strict_sha(
        item.get("result_sha256"), label="variant result SHA"
    )
    body = {key: item[key] for key in item if key != "result_sha256"}
    if (
        retained_sha != canonical_sha256(body)
        or retained_sha != result.result_sha256
        or retained_sha != rebuilt_sha
        or result.canonical_result_payload != rebuilt_payload
    ):
        raise CorpusLegalFeasibilityError("variant result self-hash differs")


def _build_batch_result_payload(
    matrix: GenerationMatrix,
    variants: Sequence[VariantScienceResult],
) -> tuple[bytes, str]:
    body: dict[str, object] = {
        "schema": BATCH_RESULT_SCHEMA,
        "slate": {
            "season": matrix.slate.season,
            "week": matrix.slate.week,
            "slate_id": matrix.slate.slate_id,
        },
        "later_source_freeze_manifest_sha256": (
            matrix.slate.source_freeze_sha256
        ),
        "artifact_sha256_by_block": dict(
            matrix.slate.artifact_sha256_by_block
        ),
        "task_source_binding": (
            None if matrix.task_source_binding is None else {
                "binding_sha256": matrix.task_source_binding.binding_sha256,
                "batch_manifest_sha256": (
                    matrix.task_source_binding.batch_manifest_sha256
                ),
                "task_index": matrix.task_source_binding.task_index,
                "task_sha256": matrix.task_source_binding.task_sha256,
                "artifact_source_authority_completion_object_sha256": (
                    matrix.task_source_binding
                    .artifact_source_authority_completion_object_sha256
                ),
                "artifact_source_authority_completion_sha256": (
                    matrix.task_source_binding
                    .artifact_source_authority_completion_sha256
                ),
                "artifact_source_authority_task_sha256": (
                    matrix.task_source_binding
                    .artifact_source_authority_task_sha256
                ),
                "later_source_freeze_manifest_sha256": (
                    matrix.task_source_binding.later_source_freeze_manifest_sha256
                ),
                "world_artifact_receipt_set_sha256": (
                    matrix.task_source_binding.world_artifact_receipt_set_sha256
                ),
            }
        ),
        "source_columns": list(matrix.source_columns),
        "visit_schedule": [
            {"block": world.block, "index": world.index}
            for world in matrix.visit_schedule
        ],
        "visit_schedule_sha256": matrix.visit_schedule_sha256,
        "attempt_ledger_sha256": matrix.attempt_ledger_sha256,
        "matrix_authority_sha256": matrix.matrix_authority_sha256,
        "solver_evidence_task_root_sha256": (
            matrix.solver_evidence_task_root_sha256
        ),
        "coverage": {
            "parameter_sets": len(variants),
            "visits_per_parameter_set": len(matrix.visit_schedule),
            "matrix_cells": len(matrix.attempts),
            "all_cells_attempted": True,
            "all_cells_optimal": True,
            "exact_80_every_variant": all(
                len(variant.selected_rosters) == ENTRY_COUNT
                for variant in variants
            ),
        },
        "variant_results": [{
            "ordinal": variant.profile.ordinal,
            "parameter_set_id": variant.profile.parameter_set_id,
            "parameter_set_sha256": variant.profile.parameter_set_sha256,
            "runtime_policy_sha256": (
                variant.runtime_policy.runtime_policy_sha256
            ),
            "result_sha256": variant.result_sha256,
        } for variant in variants],
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    result_sha = canonical_sha256(body)
    return canonical_json_bytes({**body, "result_sha256": result_sha}), result_sha


def validate_canonical_batch_result(
    result: BatchScienceResult,
    *,
    matrix: GenerationMatrix,
) -> None:
    if not isinstance(result, BatchScienceResult):
        raise CorpusLegalFeasibilityError("batch result type differs")
    if not isinstance(matrix, GenerationMatrix):
        raise CorpusLegalFeasibilityError("batch replay authority type differs")
    _validate_generation_matrix_authority(matrix)
    if (
        result.schema != SCHEMA
        or result.season != matrix.slate.season
        or result.week != matrix.slate.week
        or result.slate_id != matrix.slate.slate_id
        or result.source_freeze_sha256 != matrix.slate.source_freeze_sha256
        or result.artifact_sha256_by_block
        != matrix.slate.artifact_sha256_by_block
        or result.source_columns != matrix.source_columns
        or result.visit_schedule != matrix.visit_schedule
        or result.visit_schedule_sha256 != matrix.visit_schedule_sha256
        or result.attempt_count != len(matrix.attempts)
        or result.matrix_cell_count != len(PARAMETER_SET_ORDER)
        * len(matrix.visit_schedule)
        or result.uses_realized_outcomes is not False
        or result.historical_scoring_licensed is not False
        or result.production_change_licensed is not False
        or len(result.variants) != len(matrix.variants)
    ):
        raise CorpusLegalFeasibilityError(
            "batch result fields differ from generation authority"
        )
    for variant, generation in zip(
        result.variants, matrix.variants, strict=True
    ):
        validate_canonical_variant_result(
            variant, matrix=matrix, generation=generation
        )
    rebuilt_payload, rebuilt_sha = _build_batch_result_payload(
        matrix, result.variants
    )
    try:
        parsed = json.loads(
            result.canonical_result_payload.decode("utf-8"),
            object_pairs_hook=lambda pairs: _duplicate_safe_object(pairs),
            parse_constant=lambda value: _reject_nonfinite_constant(value),
        )
    except CorpusLegalFeasibilityError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusLegalFeasibilityError(
            "batch result payload is not valid JSON"
        ) from exc
    if canonical_json_bytes(parsed) != result.canonical_result_payload:
        raise CorpusLegalFeasibilityError("batch result payload is not canonical")
    item = _mapping(parsed, label="batch result payload")
    retained_sha = _strict_sha(item.get("result_sha256"), label="batch result SHA")
    body = {key: item[key] for key in item if key != "result_sha256"}
    if (
        retained_sha != canonical_sha256(body)
        or retained_sha != result.result_sha256
        or retained_sha != rebuilt_sha
        or result.canonical_result_payload != rebuilt_payload
    ):
        raise CorpusLegalFeasibilityError("batch result self-hash differs")


def _finalize_matrix_common(matrix: GenerationMatrix) -> BatchScienceResult:
    """Deduplicate, cross-score full unions, and select exact-80 books."""
    _validate_generation_matrix_authority(matrix)
    expected_cells = len(PARAMETER_SET_ORDER) * len(matrix.visit_schedule)
    if len(matrix.attempts) != expected_cells or any(
        attempt.status != SolverStatus.OPTIMAL for attempt in matrix.attempts
    ):
        raise CorpusLegalFeasibilityError(
            "only one complete all-Optimal generation matrix may be finalized"
        )
    unions: list[tuple[tuple[tuple[str, ...], ...], tuple[int, ...]]] = []
    short: dict[str, int] = {}
    for variant in matrix.variants:
        unique, first_indices = first_occurrence_unique(variant.visit_rosters)
        unions.append((unique, first_indices))
        if len(unique) < ENTRY_COUNT:
            short[variant.profile.parameter_set_id] = len(unique)
    if short:
        raise InsufficientCandidateSupport(
            f"variant unique unions are below exact-80: {dict(sorted(short.items()))}"
        )
    results: list[VariantScienceResult] = []
    for variant, (unique, first_indices) in zip(
        matrix.variants, unions, strict=True
    ):
        for roster in unique:
            _audit_profile_compliance(
                matrix.slate.players, roster, variant.profile
            )
        scores = cross_score_full_union(
            matrix.slate.players,
            matrix.slate.player_draws,
            unique,
            expected_worlds=EXPECTED_WORLD_COUNT,
        )
        selector = select_exact80(scores)
        selected_rosters = tuple(
            unique[index] for index in selector.selected_indices
        )
        selected_scores = np.ascontiguousarray(
            scores[np.asarray(selector.selected_indices, dtype=np.int64)],
            dtype=np.float64,
        )
        selected_scores.flags.writeable = False
        candidate_score_sha = _score_matrix_sha256(scores)
        selected_score_sha = _score_matrix_sha256(selected_scores)
        census = ViolationCensus(
            unique_candidate_counts=_violation_counts(
                matrix.slate.players, unique
            ),
            visit_counts=_violation_counts(
                matrix.slate.players, variant.visit_rosters
            ),
            selected_counts=_violation_counts(
                matrix.slate.players, selected_rosters
            ),
        )
        canonical_result_payload, result_sha = _build_variant_result_payload(
            matrix=matrix,
            variant=variant,
            unique=unique,
            first_indices=first_indices,
            candidate_score_sha256=candidate_score_sha,
            selector=selector,
            selected_rosters=selected_rosters,
            selected_score_sha256=selected_score_sha,
            census=census,
        )
        variant_result = VariantScienceResult(
            profile=variant.profile,
            runtime_policy=variant.runtime_policy,
            attempts=variant.attempts,
            visit_rosters=variant.visit_rosters,
            unique_rosters=unique,
            first_occurrence_visit_indices=first_indices,
            candidate_score_sha256=candidate_score_sha,
            selector=selector,
            selected_rosters=selected_rosters,
            selected_scores=selected_scores,
            house_rule_census=census,
            canonical_result_payload=canonical_result_payload,
            result_sha256=result_sha,
        )
        results.append(variant_result)
    if tuple(result.profile.parameter_set_id for result in results) != PARAMETER_SET_ORDER:
        raise CorpusLegalFeasibilityError("final variant order differs")
    canonical_result_payload, batch_result_sha = _build_batch_result_payload(
        matrix, results
    )
    result = BatchScienceResult(
        schema=SCHEMA,
        season=matrix.slate.season,
        week=matrix.slate.week,
        slate_id=matrix.slate.slate_id,
        source_freeze_sha256=matrix.slate.source_freeze_sha256,
        artifact_sha256_by_block=matrix.slate.artifact_sha256_by_block,
        source_columns=matrix.source_columns,
        visit_schedule=matrix.visit_schedule,
        visit_schedule_sha256=matrix.visit_schedule_sha256,
        attempt_count=len(matrix.attempts),
        matrix_cell_count=expected_cells,
        variants=tuple(results),
        uses_realized_outcomes=False,
        historical_scoring_licensed=False,
        production_change_licensed=False,
        canonical_result_payload=canonical_result_payload,
        result_sha256=batch_result_sha,
    )
    validate_canonical_batch_result(result, matrix=matrix)
    return result


def _finalize_test_generation_matrix(
    matrix: GenerationMatrix,
) -> BatchScienceResult:
    if (
        type(matrix) is not TestGenerationMatrix
        or
        matrix.task_source_binding is not None
        or matrix.registered_law is not None
        or matrix.canonical_attempt_ledger_payload
        or matrix.canonical_matrix_authority_payload
        or matrix.solver_evidence_task_root_payload
    ):
        raise CorpusLegalFeasibilityError(
            "private finalizer received an authoritative matrix"
        )
    return _finalize_matrix_common(matrix)


def _require_authoritative_generation_matrix(
    matrix: GenerationMatrix,
) -> AuthoritativeGenerationMatrix:
    expected_visits = MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
    expected_cells = len(PARAMETER_SET_ORDER) * expected_visits
    if (
        type(matrix) is not AuthoritativeGenerationMatrix
        or matrix.task_source_binding is None
        or matrix.registered_law is None
        or matrix.visits_per_block != VISITS_PER_BLOCK
        or matrix.timeout_seconds != SOLVER_TIMEOUT_SECONDS
        or matrix.source_columns != SOURCE_COLUMN_ORDER
        or matrix.source_inventory_validator_applied is not True
        or len(matrix.visit_schedule) != expected_visits
        or len(matrix.variants) != len(PARAMETER_SET_ORDER)
        or len(matrix.attempts) != expected_cells
        or tuple(
            variant.profile.parameter_set_id for variant in matrix.variants
        ) != PARAMETER_SET_ORDER
        or not matrix.canonical_attempt_ledger_payload
        or not matrix.attempt_ledger_sha256
        or not matrix.canonical_matrix_authority_payload
        or not matrix.matrix_authority_sha256
        or not matrix.solver_evidence_task_root_payload
        or not matrix.solver_evidence_task_root_sha256
        or len(matrix.solver_evidence_shard_rows)
        != EVIDENCE_SHARDS_PER_TASK
        or any(attempt.solver_proof is None for attempt in matrix.attempts)
        or any(
            attempt.status != SolverStatus.OPTIMAL
            or attempt.roster is None
            or tuple(stage.status for stage in attempt.solver_proof.stages)
            != (SolverStatus.OPTIMAL, SolverStatus.INFEASIBLE)
            for attempt in matrix.attempts
        )
        or sum(
            len(attempt.solver_proof.stages) for attempt in matrix.attempts
        ) != expected_cells * MAX_SOLVER_STAGES_PER_VISIT
    ):
        raise CorpusLegalFeasibilityError(
            "authoritative finalizer requires complete source/law/ledger/"
            "matrix/shard/CBC uniqueness proof authority"
        )
    _validate_generation_matrix_authority(matrix)
    for attempt in matrix.attempts:
        assert attempt.solver_proof is not None
        proof_item = _mapping(
            _parse_canonical_json_bytes(
                attempt.solver_proof.canonical_payload,
                label="retained authoritative solver proof",
            ),
            label="retained authoritative solver proof",
        )
        solver = _mapping(
            proof_item.get("solver"), label="retained solver authority"
        )
        rebuilt = _build_solver_proof(
            solver,
            attempt.solver_proof.stages,
            total_elapsed_microseconds=(
                attempt.solver_proof.total_elapsed_microseconds
            ),
        )
        if (
            rebuilt.canonical_payload != attempt.solver_proof.canonical_payload
            or rebuilt.proof_sha256 != attempt.solver_proof.proof_sha256
        ):
            raise CorpusLegalFeasibilityError(
                "retained authoritative solver proof does not replay"
            )
    return matrix


def _finalize_authoritative_generation_matrix(
    matrix: GenerationMatrix,
) -> BatchScienceResult:
    _require_authoritative_generation_matrix(matrix)
    return _finalize_matrix_common(matrix)


def _run_corpus_legal_feasibility_for_test(
    prepared: PreparedLaterSlate,
    inventory: Mapping[str, object],
    *,
    solver: SolverCallback,
    semantic_environment: Mapping[str, object],
    inventory_validator: InventoryValidator | None = None,
    visits_per_block: int = VISITS_PER_BLOCK,
    timeout_seconds: int = 120,
    source_columns: Sequence[object] = SOURCE_COLUMN_ORDER,
) -> BatchScienceResult:
    matrix = _execute_generation_matrix_for_test(
        prepared,
        inventory,
        solver=solver,
        semantic_environment=semantic_environment,
        inventory_validator=inventory_validator,
        visits_per_block=visits_per_block,
        timeout_seconds=timeout_seconds,
        source_columns=source_columns,
    )
    return _finalize_test_generation_matrix(matrix)


def _parse_self_hashed_authority(
    raw: bytes,
    *,
    label: str,
    schema: str,
    hash_field: str,
    expected_sha256: str,
) -> Mapping[str, object]:
    item = _mapping(
        _parse_canonical_json_bytes(raw, label=label), label=label
    )
    retained_sha = _strict_sha(item.get(hash_field), label=f"{label} SHA")
    body = {key: item[key] for key in item if key != hash_field}
    if (
        item.get("schema") != schema
        or retained_sha != expected_sha256
        or retained_sha != canonical_sha256(body)
    ):
        raise CorpusLegalFeasibilityError(f"{label} self-hash/schema differs")
    return item


def _validated_evidence_output_prefix(value: object) -> str:
    prefix = _strict_string(value, label="evidence output prefix")
    if (
        not prefix.startswith("gs://")
        or not prefix.endswith("/")
        or len(prefix) <= len("gs://") + 1
        or any(token in prefix for token in ("\\", "?", "#", "\0"))
    ):
        raise CorpusLegalFeasibilityError(
            "evidence output prefix is not one canonical gs:// prefix"
        )
    return prefix


def _build_authority_draft_body(
    *,
    task_request_sha256: object,
    source_binding: TaskSourceBinding,
    registered_law: RegisteredLawBinding,
    matrix: AuthoritativeGenerationMatrix,
    evidence_shards: Sequence[SolverEvidenceShard],
    result: BatchScienceResult,
    evidence_output_prefix: object,
) -> dict[str, object]:
    task_request_sha = _strict_sha(
        task_request_sha256, label="task request SHA"
    )
    prefix = _validated_evidence_output_prefix(evidence_output_prefix)
    shards = tuple(evidence_shards)
    return {
        "schema": DRAFT_AUTHORITY_BUNDLE_SCHEMA,
        "task_request_sha256": task_request_sha,
        "batch_manifest_sha256": source_binding.batch_manifest_sha256,
        "task_sha256": source_binding.task_sha256,
        "source_binding_sha256": source_binding.binding_sha256,
        "registered_law_sha256": registered_law.binding_sha256,
        "artifact_source_authority_completion_object_sha256": (
            registered_law.artifact_source_authority_completion_object_sha256
        ),
        "artifact_source_authority_completion_sha256": (
            registered_law.artifact_source_authority_completion_sha256
        ),
        "artifact_source_authority_task_sha256": (
            registered_law.artifact_source_authority_task_sha256
        ),
        "code_source_object_sha256": registered_law.code_source_object_sha256,
        "code_source_body_sha256": registered_law.code_source_body_sha256,
        "immutable_image_sha256": registered_law.immutable_image_sha256,
        "runtime_image_terminal_verification_required": (
            registered_law.runtime_image_terminal_verification_required
        ),
        "runtime_policy_sha256": [
            variant.runtime_policy.runtime_policy_sha256
            for variant in matrix.variants
        ],
        "attempt_ledger_sha256": matrix.attempt_ledger_sha256,
        "matrix_authority_sha256": matrix.matrix_authority_sha256,
        "solver_evidence": {
            "shard_count": len(shards),
            "task_evidence_root_sha256": (
                matrix.solver_evidence_task_root_sha256
            ),
            "shard_root_sha256": [shard.shard_root_sha256 for shard in shards],
        },
        "variant_result_sha256": [
            variant.result_sha256 for variant in result.variants
        ],
        "batch_result_sha256": result.result_sha256,
        "evidence_output_prefix": prefix,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }


def _validate_shard_attempt_cross_links(
    matrix: AuthoritativeGenerationMatrix,
    shards: Sequence[SolverEvidenceShard],
) -> None:
    for shard in shards:
        index = _reopen_solver_evidence_shard(shard)
        attempts = matrix.variants[shard.variant_ordinal].attempts[
            shard.visit_start:shard.visit_stop
        ]
        attempt_roots = _sequence(
            index.get("attempt_roots"), label="evidence shard attempt roots"
        )
        stage_rows = _sequence(
            index.get("stages"), label="evidence shard stages"
        )
        if (
            len(attempts) != EVIDENCE_SHARD_VISITS
            or len(attempt_roots) != EVIDENCE_SHARD_VISITS
            or len(stage_rows)
            != EVIDENCE_SHARD_VISITS * MAX_SOLVER_STAGES_PER_VISIT
            or index.get("attempt_count") != EVIDENCE_SHARD_VISITS
            or index.get("stage_count") != len(stage_rows)
        ):
            raise CorpusLegalFeasibilityError(
                "solver evidence shard attempt/stage coverage differs"
            )
        expected_stage_ordinal = 0
        for local_attempt, (attempt, raw_root) in enumerate(
            zip(attempts, attempt_roots, strict=True)
        ):
            proof = attempt.solver_proof
            if proof is None:
                raise CorpusLegalFeasibilityError(
                    "solver evidence shard attempt lacks its proof"
                )
            root = _mapping(
                raw_root, label="evidence shard attempt root"
            )
            expected_stage_hashes = [
                canonical_sha256(_stage_receipt_payload(stage))
                for stage in proof.stages
            ]
            if root != {
                "local_attempt_ordinal": local_attempt,
                "visit_ordinal": attempt.visit_ordinal,
                "solver_proof_sha256": proof.proof_sha256,
                "stage_receipt_sha256": expected_stage_hashes,
            }:
                raise CorpusLegalFeasibilityError(
                    "solver evidence attempt root differs from ledger proof"
                )
            for local_stage, stage in enumerate(proof.stages):
                stage_row = _mapping(
                    stage_rows[expected_stage_ordinal],
                    label="evidence shard stage row",
                )
                receipt = _stage_receipt_payload(stage)
                expected = {
                    "stage_ordinal": expected_stage_ordinal,
                    "local_attempt_ordinal": local_attempt,
                    "global_attempt_ordinal": (
                        shard.variant_ordinal
                        * MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
                        + attempt.visit_ordinal
                    ),
                    "local_stage_ordinal": local_stage,
                    "stage_receipt_sha256": canonical_sha256(receipt),
                    "stage_receipt": receipt,
                    "log_member_ordinal": expected_stage_ordinal * 2,
                    "solution_member_ordinal": expected_stage_ordinal * 2 + 1,
                }
                if stage_row != expected:
                    raise CorpusLegalFeasibilityError(
                        "solver evidence stage differs from ledger proof"
                    )
                expected_stage_ordinal += 1


def _validate_authoritative_draft_component_graph(
    draft: DraftAuthorityBundle,
) -> tuple[Mapping[str, object], tuple[tuple[str, object], ...]]:
    if type(draft.generation_matrix) is not AuthoritativeGenerationMatrix:
        raise CorpusLegalFeasibilityError(
            "authority draft lacks its authoritative generation matrix"
        )
    matrix = _require_authoritative_generation_matrix(draft.generation_matrix)
    if type(draft.result) is not BatchScienceResult:
        raise CorpusLegalFeasibilityError(
            "authority draft requires one non-null exact batch result"
        )
    if len(draft.solver_evidence_shards) != EVIDENCE_SHARDS_PER_TASK:
        raise CorpusLegalFeasibilityError(
            "authority draft shard coverage differs"
        )

    source_binding = matrix.task_source_binding
    registered_law = matrix.registered_law
    assert source_binding is not None and registered_law is not None
    source_item = _parse_self_hashed_authority(
        draft.source_binding_payload,
        label="authority source binding",
        schema="corpus-authoritative-task-source/v1",
        hash_field="binding_sha256",
        expected_sha256=source_binding.binding_sha256,
    )
    law_item = _parse_self_hashed_authority(
        draft.registered_law_payload,
        label="authority registered law",
        schema="corpus-authoritative-registered-law/v1",
        hash_field="binding_sha256",
        expected_sha256=registered_law.binding_sha256,
    )
    source_completion = _mapping(
        source_item.get("artifact_source_authority_completion_object"),
        label="source completion object",
    )
    law_source = _mapping(
        law_item.get("artifact_source_authority"),
        label="registered-law source authority",
    )
    law_mechanisms = _mapping(
        law_item.get("mechanism_object_identities"),
        label="registered-law mechanism identities",
    )
    law_code_identity = _mapping(
        law_mechanisms.get("code_source"),
        label="registered-law code-source identity",
    )
    law_body_hashes = _mapping(
        law_item.get("mechanism_body_sha256"),
        label="registered-law mechanism body hashes",
    )
    law_completion = _mapping(
        law_source.get("completion_object"),
        label="registered-law source completion object",
    )
    law_world_identity = _mapping(
        law_mechanisms.get("world_schedule"),
        label="registered-law world-schedule identity",
    )
    law_solver = _mapping(
        law_item.get("solver"), label="registered-law solver authority"
    )
    source_keys = frozenset({
        "schema",
        "batch_manifest_sha256",
        "task_index",
        "task_sha256",
        "artifact_source_authority_completion_object",
        "artifact_source_authority_completion_sha256",
        "artifact_source_authority_task_sha256",
        "artifact_source_authority_scope",
        "slate",
        "later_source_freeze_object",
        "later_source_freeze_manifest_sha256",
        "world_artifact_receipts",
        "world_artifact_receipt_set_sha256",
        "prepared_catalog_sha256",
        "prepared_incumbent_candidates_sha256",
        "prepared_player_draws_sha256",
        "prepared_world_count",
        "outcome_columns_read",
        "uses_realized_outcomes",
        "binding_sha256",
    })
    law_keys = frozenset({
        "schema",
        "common_law_sha256",
        "mechanism_object_identities",
        "mechanism_body_sha256",
        "code_source",
        "code_source_runtime_repository_head_verified",
        "immutable_image",
        "immutable_image_sha256",
        "runtime_image_terminal_verification_required",
        "terminal_verification_law",
        "artifact_source_authority",
        "solve_budget",
        "solver",
        "solver_timeout_law",
        "world_seed",
        "visit_schedule_sha256",
        "inventory_binding",
        "semantic_input_projection",
        "ambient_score_relevant_keys_requiring_absence",
        "ambient_score_relevant_key_count",
        "all_ambient_score_relevant_semantic_inputs_absent",
        "outcome_columns_read",
        "uses_realized_outcomes",
        "binding_sha256",
    })
    if (
        frozenset(source_item) != source_keys
        or frozenset(law_item) != law_keys
        or draft.source_binding_payload != source_binding.canonical_payload
        or draft.source_binding_sha256 != source_binding.binding_sha256
        or source_item.get("batch_manifest_sha256")
        != source_binding.batch_manifest_sha256
        or source_item.get("task_index") != source_binding.task_index
        or source_item.get("task_sha256") != source_binding.task_sha256
        or source_completion.get("sha256")
        != source_binding.artifact_source_authority_completion_object_sha256
        or source_item.get("artifact_source_authority_completion_sha256")
        != source_binding.artifact_source_authority_completion_sha256
        or source_item.get("artifact_source_authority_task_sha256")
        != source_binding.artifact_source_authority_task_sha256
        or source_item.get("later_source_freeze_manifest_sha256")
        != source_binding.later_source_freeze_manifest_sha256
        or source_item.get("world_artifact_receipt_set_sha256")
        != source_binding.world_artifact_receipt_set_sha256
        or source_item.get("outcome_columns_read") != []
        or source_item.get("uses_realized_outcomes") is not False
        or draft.registered_law_payload != registered_law.canonical_payload
        or draft.registered_law_sha256 != registered_law.binding_sha256
        or law_item.get("common_law_sha256")
        != registered_law.common_law_sha256
        or law_code_identity.get("sha256")
        != registered_law.code_source_object_sha256
        or law_body_hashes.get("code_source")
        != registered_law.code_source_body_sha256
        or law_item.get("immutable_image_sha256")
        != registered_law.immutable_image_sha256
        or law_item.get("runtime_image_terminal_verification_required")
        != registered_law.runtime_image_terminal_verification_required
        or law_source.get("completion_sha256")
        != registered_law.artifact_source_authority_completion_sha256
        or law_completion.get("sha256")
        != registered_law.artifact_source_authority_completion_object_sha256
        or law_source.get("task_source_authority_sha256")
        != registered_law.artifact_source_authority_task_sha256
        or law_world_identity.get("sha256")
        != registered_law.world_schedule_object_sha256
        or law_item.get("visit_schedule_sha256")
        != registered_law.visit_schedule_sha256
        or canonical_sha256(law_solver)
        != registered_law.solver_authority_sha256
        or law_item.get("outcome_columns_read") != []
        or law_item.get("uses_realized_outcomes") is not False
    ):
        raise CorpusLegalFeasibilityError(
            "authority source/registered-law component graph differs"
        )

    expected_runtime_payloads = tuple(
        variant.runtime_policy.canonical_payload for variant in matrix.variants
    )
    if draft.runtime_policy_payloads != expected_runtime_payloads:
        raise CorpusLegalFeasibilityError(
            "authority runtime-policy payload order differs"
        )
    for variant, raw in zip(
        matrix.variants, draft.runtime_policy_payloads, strict=True
    ):
        runtime = _mapping(
            _parse_canonical_json_bytes(raw, label="authority runtime policy"),
            label="authority runtime policy",
        )
        binding = variant.runtime_policy
        runtime_keys = frozenset({
            "schema",
            "inventory_sha256",
            "source_set_id",
            "source_set_sha256",
            "rule_universe_sha256",
            "rule_count",
            "classified_input_projection",
            "classified_input_projection_sha256",
            "classified_input_runtime_proof",
            "classified_input_runtime_proof_sha256",
            "experimental_rules",
            "experimental_rule_set_sha256",
            "dk_classic_feasibility_only",
            "parameter_set",
            "rules",
            "outcome_columns_read",
            "uses_realized_outcomes",
            "worker_environment_inherited",
            "historical_scoring_licensed",
            "production_change_licensed",
        })
        if (
            frozenset(runtime) != runtime_keys
            or runtime.get("schema") != RUNTIME_POLICY_SCHEMA
            or sha256(raw).hexdigest() != binding.runtime_policy_sha256
            or runtime.get("parameter_set") != variant.profile.as_payload()
            or runtime.get("inventory_sha256") != binding.inventory_sha256
            or runtime.get("source_set_id") != binding.source_set_id
            or runtime.get("source_set_sha256") != binding.source_set_sha256
            or runtime.get("rule_universe_sha256")
            != binding.rule_universe_sha256
            or runtime.get("rule_count") != binding.rule_count
            or runtime.get("classified_input_projection_sha256")
            != binding.classified_input_projection_sha256
            or runtime.get("classified_input_runtime_proof_sha256")
            != binding.classified_input_runtime_proof_sha256
            or runtime.get("experimental_rule_set_sha256")
            != binding.experimental_rule_set_sha256
            or runtime.get("dk_classic_feasibility_only")
            != binding.dk_classic_feasibility_only
            or runtime.get("outcome_columns_read") != []
            or runtime.get("uses_realized_outcomes") is not False
            or runtime.get("worker_environment_inherited") is not False
            or runtime.get("historical_scoring_licensed") is not False
            or runtime.get("production_change_licensed") is not False
        ):
            raise CorpusLegalFeasibilityError(
                "authority runtime-policy component differs"
            )

    rebuilt_matrix = _build_authoritative_matrix_payloads(
        matrix,
        solver_evidence_shards=draft.solver_evidence_shards,
    )
    if (
        rebuilt_matrix.canonical_attempt_ledger_payload
        != matrix.canonical_attempt_ledger_payload
        or rebuilt_matrix.attempt_ledger_sha256 != matrix.attempt_ledger_sha256
        or rebuilt_matrix.canonical_matrix_authority_payload
        != matrix.canonical_matrix_authority_payload
        or rebuilt_matrix.matrix_authority_sha256 != matrix.matrix_authority_sha256
        or rebuilt_matrix.solver_evidence_task_root_payload
        != matrix.solver_evidence_task_root_payload
        or rebuilt_matrix.solver_evidence_task_root_sha256
        != matrix.solver_evidence_task_root_sha256
        or rebuilt_matrix.solver_evidence_shard_rows
        != matrix.solver_evidence_shard_rows
        or draft.attempt_ledger_payload
        != rebuilt_matrix.canonical_attempt_ledger_payload
        or draft.attempt_ledger_sha256 != rebuilt_matrix.attempt_ledger_sha256
        or draft.matrix_authority_payload
        != rebuilt_matrix.canonical_matrix_authority_payload
        or draft.matrix_authority_sha256 != rebuilt_matrix.matrix_authority_sha256
        or draft.solver_evidence_task_root_payload
        != rebuilt_matrix.solver_evidence_task_root_payload
        or draft.solver_evidence_task_root_sha256
        != rebuilt_matrix.solver_evidence_task_root_sha256
    ):
        raise CorpusLegalFeasibilityError(
            "authority ledger/matrix/evidence component replay differs"
        )
    _validate_shard_attempt_cross_links(matrix, draft.solver_evidence_shards)

    validate_canonical_batch_result(draft.result, matrix=matrix)
    if (
        draft.variant_result_payloads
        != tuple(
            variant.canonical_result_payload for variant in draft.result.variants
        )
        or draft.batch_result_payload != draft.result.canonical_result_payload
        or draft.batch_result_sha256 != draft.result.result_sha256
    ):
        raise CorpusLegalFeasibilityError(
            "authority variant/batch result component replay differs"
        )

    parsed = _mapping(
        _parse_canonical_json_bytes(
            draft.canonical_draft_payload, label="authority draft"
        ),
        label="authority draft",
    )
    retained_draft_sha = _strict_sha(
        parsed.get("draft_sha256"), label="authority draft SHA"
    )
    draft_body = {key: parsed[key] for key in parsed if key != "draft_sha256"}
    expected_body = _build_authority_draft_body(
        task_request_sha256=parsed.get("task_request_sha256"),
        source_binding=source_binding,
        registered_law=registered_law,
        matrix=matrix,
        evidence_shards=draft.solver_evidence_shards,
        result=draft.result,
        evidence_output_prefix=draft.evidence_output_prefix,
    )
    if (
        draft.schema != DRAFT_AUTHORITY_BUNDLE_SCHEMA
        or retained_draft_sha != draft.draft_sha256
        or retained_draft_sha != canonical_sha256(draft_body)
        or draft_body != expected_body
        or draft.artifact_source_authority_completion_object_sha256
        != registered_law.artifact_source_authority_completion_object_sha256
        or draft.artifact_source_authority_completion_sha256
        != registered_law.artifact_source_authority_completion_sha256
        or draft.artifact_source_authority_task_sha256
        != registered_law.artifact_source_authority_task_sha256
        or draft.artifact_source_authority_completion_object_sha256
        == draft.artifact_source_authority_completion_sha256
    ):
        raise CorpusLegalFeasibilityError(
            "authority draft canonical component graph differs"
        )
    return parsed, rebuilt_matrix.solver_evidence_shard_rows


def run_authoritative_corpus_legal_feasibility(
    *,
    task_request: Mapping[str, object],
    batch_manifest_bytes: bytes,
    effective_policy_inventory_bytes: bytes,
    artifact_source_authority_completion_bytes: bytes,
    later_source_freeze_bytes: bytes,
    world_artifact_bodies: Mapping[str, bytes],
    common_law_bodies: Mapping[str, bytes],
    repository_root: Path,
    evidence_directory: Path,
) -> DraftAuthorityBundle:
    """Run one registered task and return a transport-unlicensed draft."""
    inputs = _load_authoritative_inputs(
        task_request=task_request,
        batch_manifest_bytes=batch_manifest_bytes,
        effective_policy_inventory_bytes=effective_policy_inventory_bytes,
        artifact_source_authority_completion_bytes=(
            artifact_source_authority_completion_bytes
        ),
        later_source_freeze_bytes=later_source_freeze_bytes,
        world_artifact_bodies=world_artifact_bodies,
        common_law_bodies=common_law_bodies,
        repository_root=repository_root,
    )
    with _sealed_empty_evidence_directory(evidence_directory) as (
        sealed_directory,
        directory_fd,
    ):
        matrix, evidence_shards = _execute_authoritative_generation(
            inputs,
            evidence_directory=sealed_directory,
            evidence_directory_fd=directory_fd,
        )
    if (
        matrix.registered_law is None
        or matrix.task_source_binding is None
        or not matrix.canonical_attempt_ledger_payload
        or not matrix.canonical_matrix_authority_payload
        or not matrix.solver_evidence_task_root_payload
        or not matrix.solver_evidence_task_root_sha256
        or matrix.visits_per_block != VISITS_PER_BLOCK
        or matrix.timeout_seconds != SOLVER_TIMEOUT_SECONDS
        or matrix.source_columns != SOURCE_COLUMN_ORDER
    ):
        raise CorpusLegalFeasibilityError(
            "authoritative matrix finalization prerequisites differ"
        )
    result = _finalize_authoritative_generation_matrix(matrix)
    runtime_payloads = tuple(
        variant.runtime_policy.canonical_payload
        for variant in matrix.variants
    )
    variant_payloads = tuple(
        variant.canonical_result_payload for variant in result.variants
    )
    task = inputs.manifest["tasks"][inputs.request["task_index"]]
    body = _build_authority_draft_body(
        task_request_sha256=inputs.request["task_request_sha256"],
        source_binding=inputs.source.binding,
        registered_law=inputs.law,
        matrix=matrix,
        evidence_shards=evidence_shards,
        result=result,
        evidence_output_prefix=task["variant_output_prefix"],
    )
    draft_sha = canonical_sha256(body)
    draft_payload = canonical_json_bytes({
        **body, "draft_sha256": draft_sha,
    })
    return DraftAuthorityBundle(
        schema=DRAFT_AUTHORITY_BUNDLE_SCHEMA,
        source_binding_payload=inputs.source.binding.canonical_payload,
        source_binding_sha256=inputs.source.binding.binding_sha256,
        artifact_source_authority_completion_object_sha256=(
            inputs.law.artifact_source_authority_completion_object_sha256
        ),
        artifact_source_authority_completion_sha256=(
            inputs.law.artifact_source_authority_completion_sha256
        ),
        artifact_source_authority_task_sha256=(
            inputs.law.artifact_source_authority_task_sha256
        ),
        registered_law_payload=inputs.law.canonical_payload,
        registered_law_sha256=inputs.law.binding_sha256,
        runtime_policy_payloads=runtime_payloads,
        attempt_ledger_payload=matrix.canonical_attempt_ledger_payload,
        attempt_ledger_sha256=matrix.attempt_ledger_sha256,
        matrix_authority_payload=matrix.canonical_matrix_authority_payload,
        matrix_authority_sha256=matrix.matrix_authority_sha256,
        solver_evidence_shards=evidence_shards,
        solver_evidence_task_root_payload=(
            matrix.solver_evidence_task_root_payload
        ),
        solver_evidence_task_root_sha256=(
            matrix.solver_evidence_task_root_sha256
        ),
        variant_result_payloads=variant_payloads,
        batch_result_payload=result.canonical_result_payload,
        batch_result_sha256=result.result_sha256,
        evidence_output_prefix=str(task["variant_output_prefix"]),
        canonical_draft_payload=draft_payload,
        draft_sha256=draft_sha,
        generation_matrix=matrix,
        result=result,
    )


def finalize_authoritative_corpus_bundle(
    draft: DraftAuthorityBundle,
    *,
    solver_evidence_object_identities: Sequence[Mapping[str, object]],
) -> AuthorityBundle:
    """Bind create-once generation-pinned pack+index objects to a draft."""
    if type(draft) is not DraftAuthorityBundle:
        raise CorpusLegalFeasibilityError("authority finalizer requires a draft")
    _, rebuilt_shard_rows = _validate_authoritative_draft_component_graph(
        draft
    )
    evidence_parents = {
        shard.compressed_path.parent
        for shard in draft.solver_evidence_shards
    } | {
        shard.index_path.parent for shard in draft.solver_evidence_shards
    }
    expected_local_names = {
        name
        for shard in draft.solver_evidence_shards
        for name in (shard.compressed_path.name, shard.index_path.name)
    }
    if (
        len(evidence_parents) != 1
        or len(expected_local_names) != EVIDENCE_SHARDS_PER_TASK * 2
    ):
        raise CorpusLegalFeasibilityError(
            "authority draft local evidence directory topology differs"
        )
    evidence_parent = next(iter(evidence_parents))
    try:
        parent_stat = os.lstat(evidence_parent)
        local_names = set(os.listdir(evidence_parent))
    except OSError as exc:
        raise CorpusLegalFeasibilityError(
            "authority draft local evidence directory cannot be reopened"
        ) from exc
    if (
        stat.S_ISLNK(parent_stat.st_mode)
        or not stat.S_ISDIR(parent_stat.st_mode)
        or evidence_parent.resolve(strict=True) != evidence_parent
        or local_names != expected_local_names
    ):
        raise CorpusLegalFeasibilityError(
            "authority draft local evidence directory contents differ"
        )
    identities_raw = tuple(solver_evidence_object_identities)
    if len(identities_raw) != EVIDENCE_SHARDS_PER_TASK:
        raise CorpusLegalFeasibilityError(
            "published evidence identity count differs"
        )
    identities: list[dict[str, object]] = []
    published_rows: list[dict[str, object]] = []
    for shard, raw_identity_row in zip(
        draft.solver_evidence_shards, identities_raw, strict=True
    ):
        _reopen_solver_evidence_shard(shard)
        identity_row = _mapping(
            raw_identity_row,
            label=(
                "published evidence shard identity row "
                f"{shard.global_shard_ordinal}"
            ),
        )
        if frozenset(identity_row) != frozenset({
            "global_shard_ordinal",
            "compressed_object_identity",
            "index_object_identity",
        }):
            raise CorpusLegalFeasibilityError(
                "published evidence shard identity-row fields differ"
            )
        if (
            _strict_int(
                identity_row["global_shard_ordinal"],
                label="published evidence shard ordinal",
                minimum=0,
            )
            != shard.global_shard_ordinal
        ):
            raise CorpusLegalFeasibilityError(
                "published evidence shard identity-row order differs"
            )
        compressed_identity = _validate_local_evidence_object_identity(
            shard.compressed_path,
            _mapping(
                identity_row["compressed_object_identity"],
                label="published compressed evidence identity",
            ),
            expected_sha256=shard.compressed_sha256,
            expected_size=shard.compressed_bytes,
            expected_device=shard.compressed_device,
            expected_inode=shard.compressed_inode,
            maximum_bytes=MAX_SHARD_SOLVER_EVIDENCE_COMPRESSED_BYTES,
            label=(
                "published compressed evidence shard "
                f"{shard.global_shard_ordinal}"
            ),
        )
        index_identity = _validate_local_evidence_object_identity(
            shard.index_path,
            _mapping(
                identity_row["index_object_identity"],
                label="published evidence-index identity",
            ),
            expected_sha256=shard.index_object_sha256,
            expected_size=shard.index_bytes,
            expected_device=shard.index_device,
            expected_inode=shard.index_inode,
            maximum_bytes=MAX_SHARD_SOLVER_EVIDENCE_INDEX_BYTES,
            label=(
                "published evidence index "
                f"{shard.global_shard_ordinal}"
            ),
        )
        expected_compressed_uri = (
            f"{draft.evidence_output_prefix}solver-evidence/"
            f"shard-{shard.global_shard_ordinal:03d}.zlib"
        )
        expected_index_uri = (
            f"{draft.evidence_output_prefix}solver-evidence/"
            f"shard-{shard.global_shard_ordinal:03d}.index.json"
        )
        if (
            compressed_identity["uri"] != expected_compressed_uri
            or index_identity["uri"] != expected_index_uri
        ):
            raise CorpusLegalFeasibilityError(
                "published evidence URI differs from deterministic path"
            )
        normalized_identity_row = {
            "global_shard_ordinal": shard.global_shard_ordinal,
            "compressed_object_identity": compressed_identity,
            "index_object_identity": index_identity,
        }
        identities.append(normalized_identity_row)
        published_rows.append({
            "global_shard_ordinal": shard.global_shard_ordinal,
            "compressed_object_identity": compressed_identity,
            "index_object_identity": index_identity,
            "index_sha256": shard.index_sha256,
            "index_object_sha256": shard.index_object_sha256,
            "shard_root_sha256": shard.shard_root_sha256,
        })
    published_body: dict[str, object] = {
        "schema": "corpus-cbc-published-task-evidence-root/v1",
        "content_task_evidence_root_sha256": (
            draft.solver_evidence_task_root_sha256
        ),
        "shard_count": EVIDENCE_SHARDS_PER_TASK,
        "content_shard_rows_sha256": canonical_sha256([
            value for _, value in rebuilt_shard_rows
        ]),
        "published_shards": published_rows,
    }
    published_root_sha = canonical_sha256(published_body)
    published_root_payload = canonical_json_bytes({
        **published_body,
        "published_task_evidence_root_sha256": published_root_sha,
    })
    bundle_body: dict[str, object] = {
        "schema": AUTHORITY_BUNDLE_SCHEMA,
        "draft_sha256": draft.draft_sha256,
        "content_task_evidence_root_sha256": (
            draft.solver_evidence_task_root_sha256
        ),
        "published_task_evidence_root_sha256": published_root_sha,
        "published_shard_identity_set_sha256": canonical_sha256(identities),
        "batch_result_sha256": draft.batch_result_sha256,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    bundle_sha = canonical_sha256(bundle_body)
    return AuthorityBundle(
        schema=AUTHORITY_BUNDLE_SCHEMA,
        draft=draft,
        solver_evidence_object_identities=tuple(identities),
        published_task_evidence_root_payload=published_root_payload,
        published_task_evidence_root_sha256=published_root_sha,
        canonical_bundle_payload=canonical_json_bytes({
            **bundle_body, "bundle_sha256": bundle_sha,
        }),
        bundle_sha256=bundle_sha,
    )


__all__ = [
    "AUTHORITY_BUNDLE_SCHEMA",
    "AuthorityBundle",
    "DraftAuthorityBundle",
    "BatchExecutionError",
    "BATCH_RESULT_SCHEMA",
    "BatchScienceResult",
    "CBC_OPTIONS",
    "CBC_THREADS",
    "ConstraintDose",
    "CorpusLegalFeasibilityError",
    "EffectivePolicyProfile",
    "ENTRY_COUNT",
    "InsufficientCandidateSupport",
    "RUNTIME_POLICY_SCHEMA",
    "RuntimePolicyBinding",
    "SCHEMA",
    "SOURCE_COLUMN_ORDER",
    "SelectorReceipt",
    "SolveOutcome",
    "SolveRequest",
    "SolverStatus",
    "StackRuleDose",
    "TaskSourceBinding",
    "TAIL_LINE_DK",
    "VISITS_PER_BLOCK",
    "VariantScienceResult",
    "VARIANT_RESULT_SCHEMA",
    "audit_dk_classic",
    "build_fresh_legal_model",
    "build_runtime_effective_policy",
    "canonical_visit_schedule",
    "classify_pulp_status",
    "cross_score_full_union",
    "default_cbc_solver",
    "first_occurrence_unique",
    "frozen_policy_profiles",
    "house_rule_violations",
    "select_exact80",
    "validate_outcome_blind_column_names",
    "validate_runtime_effective_policy",
    "run_authoritative_corpus_legal_feasibility",
    "finalize_authoritative_corpus_bundle",
]
