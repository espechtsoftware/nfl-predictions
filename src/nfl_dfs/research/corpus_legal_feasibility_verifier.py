"""Independent verifier for the corpus legal-feasibility authority bundle.

This module is deliberately a second implementation, not a call-through to
the execution science core.  It consumes retained raw authorities and an
already-produced authority bundle, then reconstructs the source, registered
law, policies, solver evidence, generated populations, full-world scores, and
exact-80 books without invoking CBC or reading realized outcomes.

The verifier has no production, adoption, outcome-read, graph-write, retry,
or deployment authority.  A successful receipt remains outcome blind and has
``decision_authority=False``.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import shlex
import stat
import subprocess
import tempfile
from typing import Final, Protocol
import zlib

import numpy as np
import pulp

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
    TASK_WORLD_SOURCE_ROLES,
    WORLDS_PER_BLOCK,
    bind_task_request_to_manifest,
    canonical_sha256 as batch_canonical_sha256,
    frozen_parameter_sets,
    validate_task_result_receipt,
    validate_batch_manifest,
    validate_parameter_set,
)
from nfl_dfs.research.corpus_batch_evidence_contract import (
    CorpusBatchEvidenceContractError,
    validate_corpus_batch_evidence_contract_bytes,
    validate_corpus_batch_evidence_contract_identity,
)
from nfl_dfs.research.corpus_legal_feasibility import (
    ATTEMPT_LEDGER_SCHEMA,
    AUTHORITY_BUNDLE_SCHEMA,
    BATCH_RESULT_SCHEMA,
    CBC_OPTIONS,
    CBC_OPTIONS_PAYLOAD,
    CBC_THREADS,
    DRAFT_AUTHORITY_BUNDLE_SCHEMA,
    EVIDENCE_PACK_CODEC,
    EVIDENCE_SHARDS_PER_TASK,
    EVIDENCE_SHARDS_PER_VARIANT,
    EVIDENCE_SHARD_VISITS,
    MATRIX_AUTHORITY_SCHEMA,
    MAX_SHARD_SOLVER_EVIDENCE_COMPRESSED_BYTES,
    MAX_SHARD_SOLVER_EVIDENCE_INDEX_BYTES,
    MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES,
    MAX_SOLVER_EVIDENCE_BYTES_PER_STAGE,
    RUNTIME_POLICY_SCHEMA,
    SOLVER_PROOF_SCHEMA,
    SOURCE_COLUMN_ORDER,
    VARIANT_RESULT_SCHEMA,
    VISITS_PER_BLOCK,
    WORLD_SCHEDULE_SCHEMA,
)
from nfl_dfs.research.effective_policy_rule_inventory import (
    EffectivePolicyInventoryError,
    canonical_sha256 as inventory_canonical_sha256,
    validate_effective_policy_rule_inventory,
)
from nfl_dfs.research.lr8_later_period_source import (
    LR8LaterSourceError,
    canonical_json as later_source_canonical_json,
    prepare_later_slate,
    validate_source_freeze,
)


SCHEMA: Final = "corpus-legal-feasibility-independent-verification/v2"
EXPECTED_WORLD_COUNT: Final = len(rw.WORLD_BLOCKS) * rw.WORLDS_PER_BLOCK
ENTRY_COUNT: Final = SELECTED_ENTRY_BUDGET
TAIL_LINE_DK: Final = 194.0
MICRO_DK_SCALE: Final = 1_000_000
MAX_EXACT_INTEGER: Final = (1 << 53) - 1
CORE_SCIENCE_SCHEMA: Final = "corpus-legal-feasibility-science/v1"
PAIRED_MONOTONICITY_SCHEMA: Final = (
    "corpus-paired-primary-optimum-monotonicity/v1"
)
OUTSIDE_LAW_NONVACUITY_SCHEMA: Final = (
    "corpus-outside-incumbent-law-nonvacuity/v1"
)
SCORE_FREE_ENDPOINT_SCHEMA: Final = "corpus-score-free-endpoint-summary/v1"
SCORE_MATRIX_COVERAGE_SCHEMA: Final = "corpus-score-matrix-coverage/v1"
CONTENT_TASK_ROOT_SCHEMA: Final = "corpus-cbc-evidence-task-root/v1"
PUBLISHED_TASK_ROOT_SCHEMA: Final = (
    "corpus-cbc-published-task-evidence-root/v1"
)
SHARD_INDEX_SCHEMA: Final = "corpus-cbc-evidence-shard-index/v1"
TASK_TERMINAL_SCHEMA: Final = (
    "corpus-legal-feasibility-task-terminal/v1"
)
MAX_CANONICAL_JSON_AUTHORITY_BYTES: Final = 512 * 1024 * 1024
MAX_TASK_REQUEST_BYTES: Final = 1024 * 1024
MAX_TASK_TERMINAL_BYTES: Final = 8 * 1024 * 1024
MAX_TASK_RESULT_BYTES: Final = 8 * 1024 * 1024
MAX_EVIDENCE_CONTRACT_BYTES: Final = 32 * 1024 * 1024
_TASK_AUTHORITY_OBJECT_ROLES: Final = (
    "source_binding",
    "registered_law",
    "attempt_ledger",
    "matrix_authority",
    "content_task_evidence_root",
    "published_task_evidence_root",
    "draft_authority_bundle",
    "authority_bundle",
    "batch_result",
)
_TASK_VERIFIER_GATE_IDS: Final = (
    "gate:corpus:batch-manifest-seven-set-identity",
    "gate:corpus:source-world-compute-pairing",
    "gate:corpus:effective-policy-runtime-replay",
    "gate:corpus:solver-terminal-zero-retry-proof",
    "gate:corpus:paired-objective-relaxation-monotonicity",
    "gate:corpus:outside-incumbent-law-nonvacuity",
    "gate:corpus:dk-legality-and-exact80",
    "gate:corpus:independent-scorefree-replay",
    "gate:corpus:simulated-score-matrix-exact-roster-world-coverage",
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
_CODE_SOURCE_BUILD_PATHS: Final = ("Dockerfile", "cloudbuild.yaml")
_CODE_SOURCE_TERMINAL_VERIFICATION: Final = {
    "authority": "external-terminal-execution-receipt",
    "required": True,
    "verifies": [
        "cloud_build_id",
        "immutable_image",
        "source_commit_sha",
    ],
}
_REMOVED_FIELD_BY_SINGLE_CHALLENGER: Final = {
    1: "min_lineup_salary",
    2: "qb_stack_min",
    3: "bring_back_min",
    4: "forbid_rb_vs_dst",
    5: "forbid_two_rb_same_team",
}
_FULL_WORLD_LATTICE_DEFINITION: Final = {
    "block_order": list(rw.WORLD_BLOCKS),
    "worlds_per_block": rw.WORLDS_PER_BLOCK,
    "order": "block-major-then-world-index-ascending",
}

_SHA256: Final = re.compile(r"[0-9a-f]{64}")
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


class CorpusLegalFeasibilityVerificationError(ValueError):
    """One retained authority failed independent, fail-closed replay."""


class GenerationPinnedObjectReader(Protocol):
    """Read the exact generation named by one durable object identity.

    Implementations may reopen object storage or inject retained bytes in an
    offline test.  The verifier always rechecks byte count and SHA-256 after
    the read; a URI-only or current-generation read is not an implementation
    of this seam.
    """

    def read_generation(self, *, uri: str, generation: str) -> bytes: ...


@dataclass(frozen=True, slots=True)
class _RawSolverEvidenceShard:
    global_shard_ordinal: int
    compressed_object_identity: Mapping[str, object]
    index_object_identity: Mapping[str, object]
    index_sha256: str
    index_object_sha256: str
    shard_root_sha256: str


@dataclass(frozen=True, slots=True)
class _RawDraftAuthorities:
    schema: str
    source_binding_payload: bytes = field(compare=False, repr=False)
    source_binding_sha256: str
    artifact_source_authority_completion_object_sha256: str
    artifact_source_authority_completion_sha256: str
    artifact_source_authority_task_sha256: str
    registered_law_payload: bytes = field(compare=False, repr=False)
    registered_law_sha256: str
    runtime_policy_payloads: tuple[bytes, ...] = field(
        compare=False, repr=False
    )
    attempt_ledger_payload: bytes = field(compare=False, repr=False)
    attempt_ledger_sha256: str
    matrix_authority_payload: bytes = field(compare=False, repr=False)
    matrix_authority_sha256: str
    solver_evidence_shards: tuple[_RawSolverEvidenceShard, ...]
    solver_evidence_task_root_payload: bytes = field(
        compare=False, repr=False
    )
    solver_evidence_task_root_sha256: str
    variant_result_payloads: tuple[bytes, ...] = field(
        compare=False, repr=False
    )
    batch_result_payload: bytes = field(compare=False, repr=False)
    batch_result_sha256: str
    evidence_output_prefix: str
    canonical_draft_payload: bytes = field(compare=False, repr=False)
    draft_sha256: str


@dataclass(frozen=True, slots=True)
class _RawAuthorityBundle:
    schema: str
    draft: _RawDraftAuthorities
    published_task_evidence_root_payload: bytes = field(
        compare=False, repr=False
    )
    published_task_evidence_root_sha256: str
    canonical_bundle_payload: bytes = field(compare=False, repr=False)
    bundle_sha256: str
    terminal_receipt: Mapping[str, object]
    task_result: Mapping[str, object]
    evidence_contract: Mapping[str, object]
    object_reader: GenerationPinnedObjectReader = field(
        compare=False, repr=False
    )


@dataclass(frozen=True, slots=True)
class _VerifiedRawInputs:
    request: Mapping[str, object]
    manifest: Mapping[str, object]
    task: Mapping[str, object]
    inventory: Mapping[str, object]
    players: tuple[rw.PlayerSpec, ...]
    player_draws: np.ndarray = field(compare=False, repr=False)
    incumbent_candidates: tuple[tuple[str, ...], ...]
    source_freeze_sha256: str
    artifact_sha256_by_block: tuple[tuple[str, str], ...]
    artifact_source_authority_completion_object_sha256: str
    artifact_source_authority_completion_sha256: str
    artifact_source_authority_task_sha256: str
    source_binding_payload: bytes
    source_binding_sha256: str
    registered_law_payload: bytes
    registered_law_sha256: str
    code_source_object_sha256: str
    code_source_body_sha256: str
    immutable_image_sha256: str
    runtime_image_terminal_verification_required: bool
    solver_authority: Mapping[str, object]
    visit_schedule: tuple[rw.WorldId, ...]
    visit_schedule_sha256: str
    profiles: tuple[Mapping[str, object], ...]
    runtime_policy_payloads: tuple[bytes, ...]


@dataclass(frozen=True, slots=True)
class IndependentVerificationReceipt:
    """Canonical outcome-blind receipt emitted only after complete replay."""

    schema: str
    task_index: int
    season: int
    week: int
    slate_id: str
    source_binding_sha256: str
    registered_law_sha256: str
    attempt_ledger_sha256: str
    matrix_authority_sha256: str
    solver_evidence_task_root_sha256: str
    published_task_evidence_root_sha256: str
    draft_sha256: str
    authority_bundle_sha256: str
    artifact_source_authority_completion_object_sha256: str
    artifact_source_authority_completion_sha256: str
    artifact_source_authority_task_sha256: str
    evidence_contract_sha256: str
    task_result_sha256: str
    terminal_receipt_sha256: str
    variant_result_sha256s: tuple[str, ...]
    batch_result_sha256: str
    candidate_score_sha256s: tuple[str, ...]
    selected_score_sha256s: tuple[str, ...]
    paired_primary_optimum_summary: Mapping[str, object]
    outside_incumbent_law_summaries: tuple[Mapping[str, object], ...]
    score_free_endpoint_summaries: tuple[Mapping[str, object], ...]
    score_matrix_coverage_summaries: tuple[Mapping[str, object], ...]
    verified_cell_count: int
    verified_solver_stage_count: int
    verified_unique_candidate_count: int
    verified_selected_entry_count: int
    verified_gate_ids: tuple[str, ...]
    outcome_columns_read: tuple[str, ...] = ()
    uses_realized_outcomes: bool = False
    historical_scoring_licensed: bool = False
    production_change_licensed: bool = False
    decision_authority: bool = False
    canonical_payload: bytes = field(compare=False, repr=False, default=b"")
    verification_sha256: str = ""


def _canonical_json_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "value is not canonical JSON"
        ) from exc


def _canonical_sha256(value: object) -> str:
    return sha256(_canonical_json_bytes(value)).hexdigest()


def _duplicate_safe_object(
    pairs: list[tuple[str, object]], *, label: str
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise CorpusLegalFeasibilityVerificationError(
                f"{label} repeats key {key!r}"
            )
        result[key] = value
    return result


def _parse_canonical_json_bytes(raw: bytes, *, label: str) -> object:
    if type(raw) is not bytes or not raw:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} must be nonempty raw bytes"
        )

    def reject_constant(token: str) -> object:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} contains non-finite number {token}"
        )

    try:
        value = json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=lambda pairs: _duplicate_safe_object(
                pairs, label=label
            ),
            parse_constant=reject_constant,
        )
    except CorpusLegalFeasibilityVerificationError:
        raise
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} is not valid UTF-8 JSON"
        ) from exc
    if _canonical_json_bytes(value) != raw:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} is not canonical JSON"
        )
    return value


def _mapping(value: object, *, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} must be an object"
        )
    return value


def _sequence(value: object, *, label: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} must be an array"
        )
    return value


def _strict_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value.strip() != value:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} must be a canonical string"
        )
    return value


def _strict_int(
    value: object, *, label: str, minimum: int | None = None
) -> int:
    if type(value) is not int:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} must be an exact integer"
        )
    if minimum is not None and value < minimum:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} must be >= {minimum}"
        )
    return value


def _strict_sha(value: object, *, label: str) -> str:
    if type(value) is not str or _SHA256.fullmatch(value) is None:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} must be lowercase SHA-256"
        )
    return value


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str
) -> None:
    actual = frozenset(value)
    if actual != expected:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} fields differ; missing={sorted(expected - actual)}, "
            f"unknown={sorted(actual - expected)}"
        )


def _outcome_blind_columns(columns: Sequence[object]) -> tuple[str, ...]:
    result = tuple(
        _strict_string(value, label=f"source column[{index}]")
        for index, value in enumerate(_sequence(columns, label="source columns"))
    )
    if len(set(result)) != len(result):
        raise CorpusLegalFeasibilityVerificationError("source columns repeat")
    forbidden = sorted(
        column
        for column in result
        if any(
            fragment in column.casefold()
            for fragment in _FORBIDDEN_OUTCOME_FRAGMENTS
        )
    )
    if forbidden:
        raise CorpusLegalFeasibilityVerificationError(
            f"source columns contain outcome fields: {forbidden}"
        )
    return result


def _validate_raw_object_identity(
    raw: bytes, identity: object, *, label: str
) -> dict[str, object]:
    item = _normalize_object_identity(identity, label=label)
    if (
        type(raw) is not bytes
        or len(raw) != item["bytes"]
        or sha256(raw).hexdigest() != item["sha256"]
    ):
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} retained identity differs"
        )
    return item


def _normalize_object_identity(
    identity: object, *, label: str
) -> dict[str, object]:
    item = _mapping(identity, label=f"{label} identity")
    _exact_keys(
        item,
        frozenset({"uri", "generation", "sha256", "bytes"}),
        label=f"{label} identity",
    )
    uri = _strict_string(item["uri"], label=f"{label} URI")
    generation = _strict_string(
        item["generation"], label=f"{label} generation"
    )
    digest = _strict_sha(item["sha256"], label=f"{label} SHA")
    size = _strict_int(item["bytes"], label=f"{label} bytes", minimum=1)
    if (
        not uri.startswith("gs://")
        or not generation.isdecimal()
        or generation.startswith("0")
    ):
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} retained identity differs"
        )
    return {
        "uri": uri,
        "generation": generation,
        "sha256": digest,
        "bytes": size,
    }


def _read_generation_pinned_object(
    reader: GenerationPinnedObjectReader,
    identity: object,
    *,
    maximum_bytes: int,
    label: str,
) -> tuple[bytes, dict[str, object]]:
    normalized = _normalize_object_identity(identity, label=label)
    limit = _strict_int(
        maximum_bytes, label=f"{label} maximum bytes", minimum=1
    )
    if normalized["bytes"] > limit:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} exceeds the verifier byte bound"
        )
    method = getattr(reader, "read_generation", None)
    if not callable(method):
        raise CorpusLegalFeasibilityVerificationError(
            "object_reader must implement read_generation(uri=, generation=)"
        )
    try:
        raw = method(
            uri=str(normalized["uri"]),
            generation=str(normalized["generation"]),
        )
    except Exception as exc:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} exact generation cannot be reopened"
        ) from exc
    if type(raw) is not bytes:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} reader did not return exact bytes"
        )
    _validate_raw_object_identity(raw, normalized, label=label)
    return raw, normalized


def _profile_payloads() -> tuple[dict[str, object], ...]:
    result: list[dict[str, object]] = []
    for expected_ordinal, raw in enumerate(frozen_parameter_sets()):
        try:
            frozen = validate_parameter_set(raw)
        except ValueError as exc:
            raise CorpusLegalFeasibilityVerificationError(
                "frozen parameter set does not validate"
            ) from exc
        if (
            frozen["ordinal"] != expected_ordinal
            or frozen["parameter_set_id"]
            != PARAMETER_SET_ORDER[expected_ordinal]
        ):
            raise CorpusLegalFeasibilityVerificationError(
                "frozen parameter-set order differs"
            )
        values = dict(frozen["values"])
        result.append({
            "ordinal": expected_ordinal,
            "parameter_set_id": frozen["parameter_set_id"],
            "parameter_set_sha256": frozen["parameter_set_sha256"],
            "parameter_values": {
                name: values[name] for name in PARAMETER_ORDER
            },
            "stack_rules": {
                "qb_stack_min": values["qb_stack_min"],
                "bring_back_min": values["bring_back_min"],
                "forbid_rb_vs_dst": values["forbid_rb_vs_dst"],
                "forbid_two_rb_same_team": values[
                    "forbid_two_rb_same_team"
                ],
                "qb_stack_max": None,
                "bring_back_max": None,
                "require_rb_vs_dst": False,
                "require_two_rb_same_team": False,
            },
            "shared_constraints": {
                "budget": rw.SALARY_CAP,
                "locks": [],
                "bans": [],
                "banned_lineups": [],
                "max_overlap": rw.ROSTER_SIZE - 1,
                "punt_max_salary": None,
                "punt_min": 0,
                "game_lock": None,
                "min_salary": values["min_lineup_salary"],
                "max_salary": None,
                "max_per_game": 0,
                "env": {},
            },
        })
    _require_full_batch_shape([
        row["parameter_set_id"] for row in result
    ])
    return tuple(result)


def _runtime_operation(
    row: Mapping[str, object], profile: Mapping[str, object]
) -> tuple[object, str, str, str, str]:
    field_name = row["parametric_field"]
    baseline_state = str(row["baseline_state"])
    values = _mapping(profile["parameter_values"], label="profile values")
    if field_name is not None:
        name = str(field_name)
        effective = values[name]
        baseline = row["default_dose"]
        if type(effective) is not type(baseline):
            raise CorpusLegalFeasibilityVerificationError(
                f"runtime policy type differs for {name}"
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
    if stage == "simulation" and baseline_state == "active":
        return (
            row["default_dose"],
            "active",
            "frozen-baseline",
            "upstream_frozen",
            "frozen-upstream-retained",
        )
    if stage == "simulation" or baseline_state == "inactive":
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


def _experimental_rules(visit_schedule_sha256: str) -> list[dict[str, object]]:
    schedule_sha = _strict_sha(
        visit_schedule_sha256, label="visit-schedule SHA"
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
                "visits_per_block": VISITS_PER_BLOCK,
                "visit_schedule_sha256": schedule_sha,
            },
        },
        {
            "id": "experimental:one-world-optimum-per-visit",
            "application": "applied",
            "dose": {
                "objective": (
                    "exact-lexicographic-primary-micro-dk-then-stable-rank"
                ),
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
                    MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
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
    projection: Mapping[str, object], profile: Mapping[str, object]
) -> dict[str, object]:
    rows = tuple(
        _mapping(row, label="classified input")
        for row in _sequence(projection["inputs"], label="classified inputs")
    )
    by_classification = {
        classification: tuple(
            row for row in rows if row["classification"] == classification
        )
        for classification in (
            "forbidden_ambient",
            "frozen_mechanism_input",
            "infrastructure_only",
            "typed_parametric_rule",
        )
    }
    typed_input_by_field = {
        "min_lineup_salary": "MIN_LINEUP_SALARY",
        "qb_stack_min": "STACK_QB_MIN",
        "bring_back_min": "STACK_BRING_BACK",
        "forbid_rb_vs_dst": "FORBID_RB_DST",
        "forbid_two_rb_same_team": None,
    }
    expected_typed = {
        value for value in typed_input_by_field.values() if value is not None
    }
    observed_typed = {
        str(row["input_key"])
        for row in by_classification["typed_parametric_rule"]
    }
    if observed_typed != expected_typed:
        raise CorpusLegalFeasibilityVerificationError(
            "classified typed-input surface differs"
        )
    values = _mapping(profile["parameter_values"], label="profile values")
    typed_parameters = [{
        "field": field_name,
        "value": values[field_name],
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
    ambient = list(projection["ambient_process_keys_requiring_absence"])
    return {
        "typed_request_local_parameters": typed_parameters,
        "typed_request_local_parameter_count": len(typed_parameters),
        "frozen_mechanism_inputs": frozen_mechanisms,
        "frozen_mechanism_input_count": len(frozen_mechanisms),
        "infrastructure_inputs": infrastructure,
        "infrastructure_input_count": len(infrastructure),
        "infrastructure_inherited_as_science": False,
        "ambient_score_relevant_keys_requiring_absence": ambient,
        "ambient_score_relevant_key_count": len(ambient),
        "ambient_score_relevant_keys_present_in_semantic_input": [],
        "ambient_score_relevant_keys_present_sha256": _canonical_sha256([]),
        "all_ambient_score_relevant_semantic_inputs_absent": True,
        "worker_environment_inherited": False,
    }


def _build_runtime_policy_payload(
    inventory: Mapping[str, object],
    profile: Mapping[str, object],
    *,
    visit_schedule_sha256: str,
) -> bytes:
    rules: list[dict[str, object]] = []
    for raw_row in _sequence(inventory["rules"], label="inventory rules"):
        row = _mapping(raw_row, label="inventory rule")
        dose, state, relation, application, operation = _runtime_operation(
            row, profile
        )
        rules.append({
            "application": application,
            "baseline_state": row["baseline_state"],
            "classification": row["classification"],
            "default_dose": row["default_dose"],
            "dose_relation": relation,
            "effective_dose": dose,
            "effective_state": state,
            "id": row["id"],
            "inventory_row_sha256": inventory_canonical_sha256(row),
            "normalized_paths": row["normalized_paths"],
            "operation": operation,
            "parametric_field": row["parametric_field"],
            "source_locator_sha256": row["source_locator_sha256"],
            "stage": row["stage"],
        })
    experimental = _experimental_rules(visit_schedule_sha256)
    projection = _mapping(
        inventory["classified_input_projection"],
        label="classified input projection",
    )
    runtime_proof = _classified_input_runtime_proof(projection, profile)
    parametric_rows = {
        str(row["parametric_field"]): row
        for row in rules if row["parametric_field"] is not None
    }
    dk_rows = [row for row in rules if row["classification"] == "dk_hard"]
    other_house = [
        row for row in rules
        if row["classification"] == "house_soft"
        and row["parametric_field"] is None
    ]
    dk_only = (
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
            for row in other_house
        )
        and runtime_proof[
            "all_ambient_score_relevant_semantic_inputs_absent"
        ] is True
    )
    return _canonical_json_bytes({
        "schema": RUNTIME_POLICY_SCHEMA,
        "inventory_sha256": inventory["inventory_sha256"],
        "source_set_id": inventory["source_set_id"],
        "source_set_sha256": inventory["source_set_sha256"],
        "rule_universe_sha256": inventory["rule_universe_sha256"],
        "rule_count": len(rules),
        "classified_input_projection": projection,
        "classified_input_projection_sha256": inventory[
            "classified_input_projection_sha256"
        ],
        "classified_input_runtime_proof": runtime_proof,
        "classified_input_runtime_proof_sha256": _canonical_sha256(
            runtime_proof
        ),
        "experimental_rules": experimental,
        "experimental_rule_set_sha256": _canonical_sha256(experimental),
        "dk_classic_feasibility_only": dk_only,
        "parameter_set": profile,
        "rules": rules,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "worker_environment_inherited": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    })


def _player_map(
    players: Sequence[rw.PlayerSpec],
) -> tuple[tuple[rw.PlayerSpec, ...], dict[str, rw.PlayerSpec]]:
    rows = tuple(players)
    if not rows or any(type(player) is not rw.PlayerSpec for player in rows):
        raise CorpusLegalFeasibilityVerificationError(
            "player catalog must contain exact PlayerSpec rows"
        )
    player_ids = tuple(player.player_id for player in rows)
    if player_ids != tuple(sorted(player_ids)) or len(set(player_ids)) != len(rows):
        raise CorpusLegalFeasibilityVerificationError(
            "player catalog is not unique canonical id order"
        )
    return rows, {player.player_id: player for player in rows}


def _audit_dk_classic(
    players: Sequence[rw.PlayerSpec], roster: Sequence[object]
) -> tuple[str, ...]:
    """Independent DK Classic audit; no execution-core audit is imported."""
    rows, by_id = _player_map(players)
    raw = _sequence(roster, label="roster")
    identity = tuple(
        _strict_string(value, label=f"roster player[{index}]")
        for index, value in enumerate(raw)
    )
    if identity != tuple(sorted(identity)):
        raise CorpusLegalFeasibilityVerificationError(
            "roster ids are not canonical sorted"
        )
    if len(identity) != rw.ROSTER_SIZE or len(set(identity)) != rw.ROSTER_SIZE:
        raise CorpusLegalFeasibilityVerificationError(
            "roster must contain exactly nine unique ids"
        )
    if not set(identity) <= set(by_id):
        raise CorpusLegalFeasibilityVerificationError(
            "roster contains a player outside the prepared catalog"
        )
    chosen = tuple(by_id[player_id] for player_id in identity)
    positions = Counter(player.position for player in chosen)
    if (
        set(positions) - {"QB", "RB", "WR", "TE", "DST"}
        or positions["QB"] != 1
        or positions["DST"] != 1
        or not 2 <= positions["RB"] <= 3
        or not 3 <= positions["WR"] <= 4
        or not 1 <= positions["TE"] <= 2
        or sum(positions.values()) != rw.ROSTER_SIZE
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "roster DK position shape differs"
        )
    salary = sum(player.salary for player in chosen)
    if not 0 < salary <= rw.SALARY_CAP:
        raise CorpusLegalFeasibilityVerificationError(
            "roster DK salary cap differs"
        )
    if max(Counter(player.team for player in chosen).values()) > rw.MAX_FROM_TEAM:
        raise CorpusLegalFeasibilityVerificationError(
            "roster DK team cap differs"
        )
    if len({player.game_id for player in chosen}) < rw.MIN_GAMES:
        raise CorpusLegalFeasibilityVerificationError(
            "roster DK minimum-games rule differs"
        )
    if len(rows) != len(by_id):  # defensive: preserve exact catalog topology
        raise CorpusLegalFeasibilityVerificationError("player ids repeat")
    return identity


def _house_rule_violations(
    players: Sequence[rw.PlayerSpec], roster: Sequence[object]
) -> tuple[str, ...]:
    identity = _audit_dk_classic(players, roster)
    _, by_id = _player_map(players)
    chosen = tuple(by_id[player_id] for player_id in identity)
    qb = next(player for player in chosen if player.position == "QB")
    dst = next(player for player in chosen if player.position == "DST")
    violations: set[str] = set()
    if sum(player.salary for player in chosen) < 49_000:
        violations.add("min_lineup_salary")
    if sum(
        player.team == qb.team and player.position in {"WR", "TE"}
        for player in chosen
    ) < 2:
        violations.add("qb_stack_min")
    if sum(
        player.team == qb.opponent and player.position in {"RB", "WR", "TE"}
        for player in chosen
    ) < 1:
        violations.add("bring_back_min")
    if any(
        player.position == "RB" and player.team == dst.opponent
        for player in chosen
    ):
        violations.add("forbid_rb_vs_dst")
    rb_teams = [player.team for player in chosen if player.position == "RB"]
    if len(rb_teams) != len(set(rb_teams)):
        violations.add("forbid_two_rb_same_team")
    return tuple(name for name in PARAMETER_ORDER if name in violations)


def _audit_profile(
    players: Sequence[rw.PlayerSpec],
    roster: Sequence[object],
    parameter_values: Mapping[str, object],
) -> tuple[str, ...]:
    if set(parameter_values) != set(PARAMETER_ORDER):
        raise CorpusLegalFeasibilityVerificationError(
            "parameter assignment does not cover the frozen five fields"
        )
    violations = _house_rule_violations(players, roster)
    prohibited = tuple(
        name for name in violations if parameter_values[name] not in (0, False)
    )
    if prohibited:
        raise CorpusLegalFeasibilityVerificationError(
            f"roster violates active parameter rules: {prohibited}"
        )
    return violations


def _first_occurrence_unique(
    rosters: Sequence[Sequence[object]],
) -> tuple[tuple[tuple[str, ...], ...], tuple[int, ...]]:
    unique: list[tuple[str, ...]] = []
    first_indices: list[int] = []
    seen: set[tuple[str, ...]] = set()
    for index, raw_roster in enumerate(rosters):
        identity = tuple(
            _strict_string(value, label="dedup roster id")
            for value in _sequence(raw_roster, label="dedup roster")
        )
        if (
            identity != tuple(sorted(identity))
            or len(identity) != rw.ROSTER_SIZE
            or len(set(identity)) != rw.ROSTER_SIZE
        ):
            raise CorpusLegalFeasibilityVerificationError(
                "dedup roster is not one canonical nine-id identity"
            )
        if identity not in seen:
            seen.add(identity)
            unique.append(identity)
            first_indices.append(index)
    return tuple(unique), tuple(first_indices)


def _cross_score_full_union(
    players: Sequence[rw.PlayerSpec],
    player_draws: np.ndarray,
    rosters: Sequence[Sequence[object]],
) -> np.ndarray:
    rows, by_id = _player_map(players)
    matrix = np.asarray(player_draws)
    if (
        matrix.dtype != np.dtype(np.float32)
        or matrix.ndim != 2
        or matrix.shape != (len(rows), EXPECTED_WORLD_COUNT)
        or not matrix.flags.c_contiguous
        or matrix.flags.writeable
        or not np.isfinite(matrix).all()
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "player draws are not finite read-only C float32 players x 50000"
        )
    identities = tuple(_audit_dk_classic(rows, roster) for roster in rosters)
    if not identities or len(set(identities)) != len(identities):
        raise CorpusLegalFeasibilityVerificationError(
            "cross-score union is empty or duplicated"
        )
    player_index = {
        player.player_id: index for index, player in enumerate(rows)
    }
    if set(player_index) != set(by_id):
        raise CorpusLegalFeasibilityVerificationError(
            "cross-score player index differs"
        )
    scores = np.empty((len(identities), EXPECTED_WORLD_COUNT), dtype=np.float64)
    for candidate_index, roster in enumerate(identities):
        score_rows = [player_index[player_id] for player_id in roster]
        scores[candidate_index] = matrix[score_rows].sum(
            axis=0, dtype=np.float64
        )
    if not np.isfinite(scores).all():
        raise CorpusLegalFeasibilityVerificationError(
            "cross-score matrix contains non-finite totals"
        )
    scores.flags.writeable = False
    return scores


def _matrix_content_sha256(matrix: np.ndarray, *, dtype: str) -> str:
    if dtype == "float32-le":
        array = np.ascontiguousarray(matrix, dtype="<f4")
    elif dtype == "float64-le":
        array = np.ascontiguousarray(matrix, dtype="<f8")
    else:
        raise CorpusLegalFeasibilityVerificationError(
            "matrix hash dtype is outside the frozen law"
        )
    header = _canonical_json_bytes({"dtype": dtype, "shape": list(array.shape)})
    digest = sha256()
    digest.update(header)
    digest.update(b"\0")
    digest.update(memoryview(array).cast("B"))
    return digest.hexdigest()


def _score_free_endpoint_and_coverage(
    candidate_scores: np.ndarray,
    selected_scores: np.ndarray,
    generated_unique_rosters: Sequence[Sequence[object]],
    selected_rosters: Sequence[Sequence[object]],
    *,
    parameter_set_id: object,
    expected_world_count: int = EXPECTED_WORLD_COUNT,
) -> tuple[dict[str, object], dict[str, object]]:
    """Recompute exact score-free C/S summaries and matrix-row coverage."""
    parameter_id = _strict_string(
        parameter_set_id, label="score-free parameter-set id"
    )
    if parameter_id not in PARAMETER_SET_ORDER:
        raise CorpusLegalFeasibilityVerificationError(
            "score-free parameter-set id is outside the frozen seven"
        )
    world_count = _strict_int(
        expected_world_count,
        label="score-free expected world count",
        minimum=1,
    )
    if world_count != EXPECTED_WORLD_COUNT:
        raise CorpusLegalFeasibilityVerificationError(
            "score-free world count differs from the complete frozen lattice"
        )
    if (
        type(candidate_scores) is not np.ndarray
        or type(selected_scores) is not np.ndarray
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "score-free matrices must be exact numpy arrays"
        )
    candidate = candidate_scores
    selected = selected_scores
    if (
        candidate.dtype != np.dtype(np.float64)
        or selected.dtype != np.dtype(np.float64)
        or candidate.ndim != 2
        or selected.ndim != 2
        or candidate.shape[0] < 1
        or selected.shape[0] < 1
        or candidate.shape[1] != world_count
        or selected.shape[1] != world_count
        or not candidate.flags.c_contiguous
        or not selected.flags.c_contiguous
        or candidate.flags.writeable
        or selected.flags.writeable
        or not np.isfinite(candidate).all()
        or not np.isfinite(selected).all()
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "score-free matrices are not finite read-only C float64 rows x worlds"
        )

    generated_raw = tuple(
        _sequence(row, label="generated-unique roster")
        for row in _sequence(
            generated_unique_rosters, label="generated-unique rosters"
        )
    )
    selected_raw = tuple(
        _sequence(row, label="selected roster")
        for row in _sequence(selected_rosters, label="selected rosters")
    )
    generated, generated_first = _first_occurrence_unique(generated_raw)
    selected_identities, selected_first = _first_occurrence_unique(selected_raw)
    if (
        not generated
        or not selected_identities
        or len(generated) != len(generated_raw)
        or len(selected_identities) != len(selected_raw)
        or generated_first != tuple(range(len(generated)))
        or selected_first != tuple(range(len(selected_identities)))
        or candidate.shape[0] != len(generated)
        or selected.shape[0] != len(selected_identities)
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "score-free matrix roster-row cardinality differs"
        )
    candidate_row_by_roster = {
        roster: row for row, roster in enumerate(generated)
    }
    if not set(selected_identities) <= set(candidate_row_by_roster):
        raise CorpusLegalFeasibilityVerificationError(
            "selected score rows are outside the generated-unique population"
        )
    selected_candidate_rows = np.asarray(
        [candidate_row_by_roster[roster] for roster in selected_identities],
        dtype=np.int64,
    )
    candidate_subset = candidate[selected_candidate_rows]
    if not np.array_equal(
        selected.view(np.uint64), candidate_subset.view(np.uint64)
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "selected scores differ from their exact generated-unique rows"
        )

    candidate_score_sha = _matrix_content_sha256(candidate, dtype="float64-le")
    selected_score_sha = _matrix_content_sha256(selected, dtype="float64-le")
    candidate_world_max = np.max(candidate, axis=0)
    selected_world_max = np.max(selected, axis=0)
    if np.any(selected_world_max > candidate_world_max):
        raise CorpusLegalFeasibilityVerificationError(
            "selected world maximum exceeds the complete candidate ceiling"
        )
    candidate_ceiling = float(
        candidate_world_max.mean(dtype=np.float64)
    )
    selected_maximum = float(
        selected_world_max.mean(dtype=np.float64)
    )
    conversion_gap = float(candidate_ceiling - selected_maximum)
    if (
        not np.isfinite(candidate_ceiling)
        or not np.isfinite(selected_maximum)
        or not np.isfinite(conversion_gap)
        or conversion_gap < 0.0
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "score-free endpoint summary is non-finite or order-inconsistent"
        )

    lattice = dict(_FULL_WORLD_LATTICE_DEFINITION)
    coverage_body: dict[str, object] = {
        "schema": SCORE_MATRIX_COVERAGE_SCHEMA,
        "parameter_set_id": parameter_id,
        "dtype": "float64-le",
        "generated_unique_roster_count": len(generated),
        "candidate_score_row_count": candidate.shape[0],
        "selected_roster_count": len(selected_identities),
        "selected_score_row_count": selected.shape[0],
        "world_count": world_count,
        "ordered_world_lattice": lattice,
        "ordered_world_lattice_sha256": _canonical_sha256(lattice),
        "generated_unique_roster_identity_sha256": _canonical_sha256([
            list(roster) for roster in generated
        ]),
        "selected_roster_identity_sha256": _canonical_sha256([
            list(roster) for roster in selected_identities
        ]),
        "candidate_score_sha256": candidate_score_sha,
        "selected_score_sha256": selected_score_sha,
        "complete_generated_unique_roster_row_coverage": True,
        "complete_selected_roster_row_coverage": True,
        "selected_rows_are_exact_candidate_subset": True,
    }
    coverage = {
        **coverage_body,
        "coverage_sha256": _canonical_sha256(coverage_body),
    }
    endpoint_body: dict[str, object] = {
        "schema": SCORE_FREE_ENDPOINT_SCHEMA,
        "parameter_set_id": parameter_id,
        "world_count": world_count,
        "simulated_candidate_ceiling_c": candidate_ceiling,
        "simulated_exact80_maximum_s": selected_maximum,
        "simulated_conversion_gap_c_minus_s": conversion_gap,
        "candidate_world_max_sha256": _matrix_content_sha256(
            candidate_world_max, dtype="float64-le"
        ),
        "selected_world_max_sha256": _matrix_content_sha256(
            selected_world_max, dtype="float64-le"
        ),
        "score_matrix_coverage_sha256": coverage["coverage_sha256"],
    }
    endpoint = {
        **endpoint_body,
        "endpoint_summary_sha256": _canonical_sha256(endpoint_body),
    }
    return endpoint, coverage


def _paired_primary_optimum_summary(
    attempts: Sequence[Mapping[str, object]],
    *,
    visits_per_variant: int = MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
) -> dict[str, object]:
    """Replay every aligned incumbent/challenger primary-optimum comparison."""
    visit_count = _strict_int(
        visits_per_variant,
        label="paired-monotonicity visits per variant",
        minimum=1,
    )
    rows = tuple(
        _mapping(row, label=f"paired-monotonicity attempt[{index}]")
        for index, row in enumerate(
            _sequence(attempts, label="paired-monotonicity attempts")
        )
    )
    expected_count = len(PARAMETER_SET_ORDER) * visit_count
    if len(rows) != expected_count:
        raise CorpusLegalFeasibilityVerificationError(
            "paired-monotonicity attempt coverage differs"
        )

    primary_by_variant: list[list[int]] = [
        [] for _ in PARAMETER_SET_ORDER
    ]
    world_by_variant: list[list[tuple[str, int]]] = [
        [] for _ in PARAMETER_SET_ORDER
    ]
    for ordinal, row in enumerate(rows):
        variant = ordinal // visit_count
        visit = ordinal % visit_count
        observed_variant = _strict_int(
            row.get("variant_ordinal"),
            label=f"paired-monotonicity attempt[{ordinal}] variant",
            minimum=0,
        )
        observed_visit = _strict_int(
            row.get("visit_ordinal"),
            label=f"paired-monotonicity attempt[{ordinal}] visit",
            minimum=0,
        )
        parameter_id = _strict_string(
            row.get("parameter_set_id"),
            label=f"paired-monotonicity attempt[{ordinal}] parameter-set id",
        )
        status = _strict_string(
            row.get("status"),
            label=f"paired-monotonicity attempt[{ordinal}] status",
        )
        primary = _strict_int(
            row.get("primary_optimum_micro"),
            label=f"paired-monotonicity attempt[{ordinal}] primary optimum",
        )
        world = _mapping(
            row.get("world"),
            label=f"paired-monotonicity attempt[{ordinal}] world",
        )
        _exact_keys(
            world,
            frozenset({"block", "index"}),
            label=f"paired-monotonicity attempt[{ordinal}] world",
        )
        world_identity = (
            _strict_string(
                world["block"],
                label=f"paired-monotonicity attempt[{ordinal}] world block",
            ),
            _strict_int(
                world["index"],
                label=f"paired-monotonicity attempt[{ordinal}] world index",
                minimum=0,
            ),
        )
        if (
            observed_variant != variant
            or observed_visit != visit
            or parameter_id != PARAMETER_SET_ORDER[variant]
            or status != "optimal"
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"paired-monotonicity attempt[{ordinal}] identity differs"
            )
        primary_by_variant[variant].append(primary)
        world_by_variant[variant].append(world_identity)

    incumbent = tuple(primary_by_variant[0])
    incumbent_worlds = tuple(world_by_variant[0])
    comparison_rows: list[dict[str, object]] = []
    for challenger in range(1, len(PARAMETER_SET_ORDER)):
        challenger_values = tuple(primary_by_variant[challenger])
        challenger_worlds = tuple(world_by_variant[challenger])
        if challenger_worlds != incumbent_worlds:
            raise CorpusLegalFeasibilityVerificationError(
                f"paired-monotonicity challenger[{challenger}] worlds differ"
            )
        deltas = tuple(
            challenger_value - incumbent_value
            for incumbent_value, challenger_value in zip(
                incumbent, challenger_values, strict=True
            )
        )
        negative_visits = tuple(
            visit for visit, delta in enumerate(deltas) if delta < 0
        )
        if negative_visits:
            raise CorpusLegalFeasibilityVerificationError(
                "paired primary-optimum relaxation monotonicity fails for "
                f"challenger[{challenger}] visit[{negative_visits[0]}]"
            )
        comparison_rows.append({
            "challenger_variant_ordinal": challenger,
            "challenger_parameter_set_id": PARAMETER_SET_ORDER[challenger],
            "aligned_visit_comparison_count": len(deltas),
            "minimum_primary_optimum_delta_micro": min(deltas),
            "maximum_primary_optimum_delta_micro": max(deltas),
            "zero_delta_count": sum(delta == 0 for delta in deltas),
            "positive_delta_count": sum(delta > 0 for delta in deltas),
            "incumbent_primary_optimum_vector_sha256": _canonical_sha256(
                list(incumbent)
            ),
            "challenger_primary_optimum_vector_sha256": _canonical_sha256(
                list(challenger_values)
            ),
            "ordered_delta_vector_sha256": _canonical_sha256(list(deltas)),
            "all_deltas_nonnegative": True,
        })

    summary_body: dict[str, object] = {
        "schema": PAIRED_MONOTONICITY_SCHEMA,
        "incumbent_variant_ordinal": 0,
        "incumbent_parameter_set_id": PARAMETER_SET_ORDER[0],
        "challenger_count": len(PARAMETER_SET_ORDER) - 1,
        "visits_per_challenger": visit_count,
        "aligned_comparison_count": sum(
            row["aligned_visit_comparison_count"]
            for row in comparison_rows
        ),
        "pairing_order": "challenger-ordinal-then-visit-ordinal",
        "ordered_world_schedule_sha256": _canonical_sha256([
            {"block": block, "index": index}
            for block, index in incumbent_worlds
        ]),
        "challenger_summaries": comparison_rows,
        "all_deltas_nonnegative": True,
    }
    return {
        **summary_body,
        "paired_monotonicity_sha256": _canonical_sha256(summary_body),
    }


def _outside_law_nonvacuity_summary(
    players: Sequence[rw.PlayerSpec],
    rosters: Sequence[Sequence[object]],
    *,
    variant_ordinal: object,
    parameter_set_id: object,
) -> dict[str, object]:
    """Independently enforce the contract's generated-unique rule escape."""
    variant = _strict_int(
        variant_ordinal,
        label="outside-law variant ordinal",
        minimum=0,
    )
    if variant >= len(PARAMETER_SET_ORDER):
        raise CorpusLegalFeasibilityVerificationError(
            "outside-law variant ordinal is outside the frozen seven"
        )
    parameter_id = _strict_string(
        parameter_set_id, label="outside-law parameter-set id"
    )
    if parameter_id != PARAMETER_SET_ORDER[variant]:
        raise CorpusLegalFeasibilityVerificationError(
            "outside-law parameter-set identity differs"
        )
    identities = tuple(
        _audit_dk_classic(
            players,
            _sequence(row, label=f"outside-law roster[{index}]"),
        )
        for index, row in enumerate(
            _sequence(rosters, label="outside-law generated-unique rosters")
        )
    )
    if not identities or len(set(identities)) != len(identities):
        raise CorpusLegalFeasibilityVerificationError(
            "outside-law population is empty or not generated-unique"
        )
    violations_by_roster = tuple(
        _house_rule_violations(players, roster) for roster in identities
    )
    outside_rows = tuple(
        (roster, violations)
        for roster, violations in zip(
            identities, violations_by_roster, strict=True
        )
        if violations
    )
    removed_rule = _REMOVED_FIELD_BY_SINGLE_CHALLENGER.get(variant)
    if variant == 0:
        predicate = "incumbent-zero"
        qualifying_witness_count = 0
        passed = not outside_rows
    elif removed_rule is not None:
        predicate = "single-removal-rule-only-positive"
        invalid_outside = tuple(
            (roster, violations)
            for roster, violations in outside_rows
            if violations != (removed_rule,)
        )
        qualifying_witness_count = sum(
            violations == (removed_rule,)
            for violations in violations_by_roster
        )
        passed = not invalid_outside and qualifying_witness_count >= 1
    else:
        predicate = "all-five-any-rule-positive"
        qualifying_witness_count = len(outside_rows)
        passed = qualifying_witness_count >= 1
    if not passed:
        raise CorpusLegalFeasibilityVerificationError(
            f"outside-incumbent-law nonvacuity fails for variant[{variant}]"
        )

    outside_counts = Counter({name: 0 for name in PARAMETER_ORDER})
    for violations in violations_by_roster:
        outside_counts.update(violations)
    outside_projection = [
        {
            "roster": list(roster),
            "violations": list(violations),
        }
        for roster, violations in outside_rows
    ]
    summary_body: dict[str, object] = {
        "schema": OUTSIDE_LAW_NONVACUITY_SCHEMA,
        "variant_ordinal": variant,
        "parameter_set_id": parameter_id,
        "predicate": predicate,
        "removed_rule": removed_rule,
        "generated_unique_count": len(identities),
        "outside_incumbent_law_unique_count": len(outside_rows),
        "required_witness_count": 0 if variant == 0 else 1,
        "qualifying_witness_count": qualifying_witness_count,
        "independent_five_rule_violation_counts": {
            name: outside_counts[name] for name in PARAMETER_ORDER
        },
        "generated_unique_roster_identity_sha256": _canonical_sha256([
            list(roster) for roster in identities
        ]),
        "outside_roster_violation_rows_sha256": _canonical_sha256(
            outside_projection
        ),
        "passed": True,
    }
    return {
        **summary_body,
        "outside_law_nonvacuity_sha256": _canonical_sha256(summary_body),
    }


def _select_exact80(candidate_scores: np.ndarray) -> dict[str, object]:
    scores = np.asarray(candidate_scores)
    if (
        scores.dtype != np.dtype(np.float64)
        or scores.ndim != 2
        or scores.shape[0] < ENTRY_COUNT
        or scores.shape[1] != EXPECTED_WORLD_COUNT
        or not np.isfinite(scores).all()
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "selector requires finite float64 candidates x 50000 with >=80 rows"
        )
    clears = scores >= TAIL_LINE_DK
    packed = np.packbits(clears, axis=1, bitorder="little")
    p_line = clears.mean(axis=1, dtype=np.float64)
    mean_score = scores.mean(axis=1, dtype=np.float64)
    popcount = np.unpackbits(
        np.arange(256, dtype=np.uint8)[:, None], axis=1
    ).sum(axis=1, dtype=np.uint8)
    covered = np.zeros(packed.shape[1], dtype=np.uint8)
    remaining = list(range(scores.shape[0]))
    selected: list[int] = []
    while len(selected) < ENTRY_COUNT and remaining:
        gains = popcount[
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
    selected.extend(fill[: ENTRY_COUNT - len(selected)])
    if len(selected) != ENTRY_COUNT or len(set(selected)) != ENTRY_COUNT:
        raise CorpusLegalFeasibilityVerificationError(
            "selector did not return exact-80 unique indices"
        )
    return {
        "candidate_count": scores.shape[0],
        "world_count": scores.shape[1],
        "entry_count": ENTRY_COUNT,
        "tail_line_dk": TAIL_LINE_DK,
        "selected_indices": selected,
        "tie_law_applied": "gain,p_line,mean_score,first_occurrence",
    }


def _ranked_visit_schedule(
    player_draws: np.ndarray, *, visits_per_block: int
) -> tuple[rw.WorldId, ...]:
    count = _strict_int(
        visits_per_block, label="visits per block", minimum=1
    )
    if count > rw.WORLDS_PER_BLOCK:
        raise CorpusLegalFeasibilityVerificationError(
            "visits per block exceeds source worlds per block"
        )
    matrix = np.asarray(player_draws)
    if matrix.ndim != 2 or matrix.shape[1] != EXPECTED_WORLD_COUNT:
        raise CorpusLegalFeasibilityVerificationError(
            "ranked schedule source matrix differs"
        )
    result: list[rw.WorldId] = []
    for block_ordinal, block in enumerate(rw.WORLD_BLOCKS):
        start = block_ordinal * rw.WORLDS_PER_BLOCK
        stop = start + rw.WORLDS_PER_BLOCK
        totals = matrix[:, start:stop].sum(axis=0, dtype=np.float64)
        indices = np.arange(rw.WORLDS_PER_BLOCK, dtype=np.int64)
        ranked = np.lexsort((indices, -totals))[:count]
        result.extend(rw.WorldId(block, int(index)) for index in ranked)
    schedule = tuple(result)
    if len(set(schedule)) != len(schedule):
        raise CorpusLegalFeasibilityVerificationError(
            "ranked schedule repeats a world"
        )
    return schedule


def _micro_objective(
    player_draws: np.ndarray, *, world_column: int
) -> tuple[int, ...]:
    values = np.asarray(player_draws[:, world_column], dtype=np.float64)
    if values.ndim != 1 or values.size == 0 or not np.isfinite(values).all():
        raise CorpusLegalFeasibilityVerificationError(
            "visit objective is malformed"
        )
    limit = MAX_EXACT_INTEGER / (MICRO_DK_SCALE * rw.ROSTER_SIZE)
    if float(np.max(np.abs(values))) > limit:
        raise CorpusLegalFeasibilityVerificationError(
            "visit objective exceeds exact integer range"
        )
    micro = np.rint(values * MICRO_DK_SCALE).astype(np.int64)
    if max(abs(int(micro.min())), abs(int(micro.max()))) * rw.ROSTER_SIZE > (
        MAX_EXACT_INTEGER
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "nine-player objective exceeds exact integer range"
        )
    return tuple(int(value) for value in micro)


def _registered_mechanism_bodies() -> dict[str, object]:
    return {
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
            "maximum_exact_roster_integer": MAX_EXACT_INTEGER,
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
            "prove_all_combined_coefficients_and-nine-player-sum-below_2^53": (
                True
            ),
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
        "cbwu": {"schema": "corpus-cbwu/v1", "enabled": False},
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


def _file_sha256(path: Path) -> str:
    digest = sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC binary cannot be read"
        ) from exc
    return digest.hexdigest()


def _repository_source_sha256(
    repository_root: Path, relative_path: str
) -> str:
    relative = Path(relative_path)
    if (
        not relative_path
        or relative.is_absolute()
        or relative_path != relative.as_posix()
        or ".." in relative.parts
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "code-source repository path differs"
        )
    path = repository_root / relative
    try:
        before = os.lstat(path)
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except OSError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            f"code-source file {relative_path!r} cannot be opened"
        ) from exc
    try:
        opened = os.fstat(descriptor)
        if (
            stat.S_ISLNK(before.st_mode)
            or not stat.S_ISREG(before.st_mode)
            or not stat.S_ISREG(opened.st_mode)
            or (opened.st_dev, opened.st_ino)
            != (before.st_dev, before.st_ino)
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"code-source file {relative_path!r} is not one regular inode"
            )
        digest = sha256()
        while True:
            chunk = os.read(descriptor, 1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
        after = os.fstat(descriptor)
        if (
            after.st_dev,
            after.st_ino,
            after.st_size,
        ) != (
            opened.st_dev,
            opened.st_ino,
            opened.st_size,
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"code-source file {relative_path!r} changed while hashing"
            )
        return digest.hexdigest()
    finally:
        os.close(descriptor)


def _verify_code_source_body(
    value: object,
    *,
    repository_root: Path,
    immutable_image: Mapping[str, object],
) -> tuple[dict[str, object], bool]:
    item = _mapping(value, label="common-law code-source body")
    _exact_keys(
        item,
        frozenset({
            "schema",
            "source_commit_sha",
            "cloud_build_id",
            "implementation_sha256",
            "build_definition_sha256",
            "immutable_image",
            "terminal_verification",
        }),
        label="common-law code-source body",
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
        or item["schema"] != "corpus-legal-feasibility-code-source/v1"
    ):
        raise CorpusLegalFeasibilityVerificationError(
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
        raise CorpusLegalFeasibilityVerificationError(
            "code-source implementation/build path universe differs"
        )
    normalized_implementation: dict[str, str] = {}
    normalized_build: dict[str, str] = {}
    for path in _CODE_SOURCE_IMPLEMENTATION_PATHS:
        retained = _strict_sha(
            implementation[path], label=f"code-source {path} SHA"
        )
        if retained != _repository_source_sha256(repository_root, path):
            raise CorpusLegalFeasibilityVerificationError(
                f"runtime implementation bytes differ for {path!r}"
            )
        normalized_implementation[path] = retained
    for path in _CODE_SOURCE_BUILD_PATHS:
        retained = _strict_sha(
            build_definitions[path], label=f"code-source {path} SHA"
        )
        if retained != _repository_source_sha256(repository_root, path):
            raise CorpusLegalFeasibilityVerificationError(
                f"runtime build-definition bytes differ for {path!r}"
            )
        normalized_build[path] = retained
    normalized_image = dict(_mapping(
        item["immutable_image"], label="code-source immutable image"
    ))
    if (
        normalized_image != dict(immutable_image)
        or item["terminal_verification"]
        != _CODE_SOURCE_TERMINAL_VERIFICATION
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "code-source image/terminal-verification law differs"
        )
    local_commit_verified = False
    git_metadata = repository_root / ".git"
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
            raise CorpusLegalFeasibilityVerificationError(
                "runtime repository commit cannot be verified"
            ) from exc
        if (
            completed.returncode != 0
            or completed.stderr
            or completed.stdout.strip() != commit
        ):
            raise CorpusLegalFeasibilityVerificationError(
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


def _cbc_runtime_authority() -> dict[str, object]:
    solver = pulp.PULP_CBC_CMD(msg=False)
    path = Path(str(solver.path)).resolve()
    if not path.is_file():
        raise CorpusLegalFeasibilityVerificationError("CBC binary is absent")
    try:
        completed = subprocess.run(
            [str(path), "-version"],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC version receipt cannot be read"
        ) from exc
    versions = re.findall(
        r"^Version:\s+([^\s]+)\s*$",
        f"{completed.stdout}\n{completed.stderr}",
        re.MULTILINE,
    )
    if completed.returncode != 0 or len(versions) != 1:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC version receipt is ambiguous"
        )
    return {
        "name": "cbc",
        "version": versions[0],
        "binary_sha256": _file_sha256(path),
        "options_sha256": _canonical_sha256(CBC_OPTIONS_PAYLOAD),
        "exact_mode": True,
    }


def _validate_world_schedule(
    value: object,
    *,
    manifest: Mapping[str, object],
    task_index: int,
    player_draws: np.ndarray,
) -> tuple[tuple[rw.WorldId, ...], str]:
    item = _mapping(value, label="registered world schedule")
    _exact_keys(
        item,
        frozenset({
            "schema",
            "method",
            "score_accumulator",
            "tie_break",
            "block_order",
            "source_worlds_per_block",
            "visits_per_block",
            "slates",
        }),
        label="registered world schedule",
    )
    if (
        item["schema"] != WORLD_SCHEDULE_SCHEMA
        or item["method"] != "top-total-slate-player-draw-desc"
        or item["score_accumulator"]
        != "float64-sum-of-all-slate-player-draws"
        or item["tie_break"] != "world-index-ascending-stable"
        or item["block_order"] != list(rw.WORLD_BLOCKS)
        or item["source_worlds_per_block"] != WORLDS_PER_BLOCK
        or item["visits_per_block"] != VISITS_PER_BLOCK
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "registered world-schedule law differs"
        )
    tasks = _sequence(manifest["tasks"], label="manifest tasks")
    slates = _sequence(item["slates"], label="world-schedule slates")
    if len(tasks) != len(slates):
        raise CorpusLegalFeasibilityVerificationError(
            "world schedule does not cover every task"
        )
    selected: tuple[rw.WorldId, ...] | None = None
    selected_sha: str | None = None
    common = _mapping(manifest["common_law"], label="common law")
    row_keys = frozenset({
        "task_index",
        "season",
        "week",
        "slate_id",
        "later_source_freeze_manifest_sha256",
        "world_artifact_receipt_set_sha256",
        "blocks",
        "visit_schedule_sha256",
    })
    for ordinal, (raw_row, raw_task) in enumerate(
        zip(slates, tasks, strict=True)
    ):
        row = _mapping(raw_row, label=f"world schedule slate[{ordinal}]")
        task = _mapping(raw_task, label=f"manifest task[{ordinal}]")
        _exact_keys(row, row_keys, label=f"world schedule slate[{ordinal}]")
        if (
            _strict_int(
                row["task_index"],
                label=f"world schedule slate[{ordinal}] task index",
                minimum=0,
            )
            != ordinal
            or _strict_int(
                row["season"],
                label=f"world schedule slate[{ordinal}] season",
                minimum=1,
            )
            != task["season"]
            or _strict_int(
                row["week"],
                label=f"world schedule slate[{ordinal}] week",
                minimum=1,
            )
            != task["week"]
            or _strict_string(
                row["slate_id"],
                label=f"world schedule slate[{ordinal}] slate ID",
            )
            != task["slate_id"]
            or _strict_sha(
                row["later_source_freeze_manifest_sha256"],
                label=f"world schedule slate[{ordinal}] freeze SHA",
            )
            != common["later_source_freeze_manifest_sha256"]
            or _strict_sha(
                row["world_artifact_receipt_set_sha256"],
                label=f"world schedule slate[{ordinal}] artifact-set SHA",
            )
            != task["world_artifact_receipt_set_sha256"]
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"world schedule slate[{ordinal}] authority differs"
            )
        blocks = _sequence(row["blocks"], label="world-schedule blocks")
        if len(blocks) != len(rw.WORLD_BLOCKS):
            raise CorpusLegalFeasibilityVerificationError(
                "world-schedule block count differs"
            )
        schedule: list[rw.WorldId] = []
        for block, raw_block in zip(rw.WORLD_BLOCKS, blocks, strict=True):
            block_row = _mapping(raw_block, label=f"world schedule {block}")
            _exact_keys(
                block_row,
                frozenset({"block", "world_indices"}),
                label=f"world schedule {block}",
            )
            indices = tuple(
                _strict_int(value, label=f"{block} world", minimum=0)
                for value in _sequence(
                    block_row["world_indices"], label=f"{block} worlds"
                )
            )
            if (
                block_row["block"] != block
                or len(indices) != VISITS_PER_BLOCK
                or len(set(indices)) != len(indices)
                or any(index >= WORLDS_PER_BLOCK for index in indices)
            ):
                raise CorpusLegalFeasibilityVerificationError(
                    f"world schedule {block} dose differs"
                )
            schedule.extend(rw.WorldId(block, index) for index in indices)
        schedule_tuple = tuple(schedule)
        schedule_sha = _canonical_sha256([
            {"block": world.block, "index": world.index}
            for world in schedule_tuple
        ])
        if row["visit_schedule_sha256"] != schedule_sha:
            raise CorpusLegalFeasibilityVerificationError(
                "world-schedule row self-hash differs"
            )
        if ordinal == task_index:
            selected, selected_sha = schedule_tuple, schedule_sha
    rebuilt = _ranked_visit_schedule(
        player_draws, visits_per_block=VISITS_PER_BLOCK
    )
    if selected is None or selected_sha is None or selected != rebuilt:
        raise CorpusLegalFeasibilityVerificationError(
            "task world schedule differs from rebuilt ranking"
        )
    return selected, selected_sha


def _load_verified_raw_inputs(
    *,
    task_request: Mapping[str, object],
    batch_manifest_bytes: bytes,
    effective_policy_inventory_bytes: bytes,
    artifact_source_authority_completion_bytes: bytes,
    later_source_freeze_bytes: bytes,
    world_artifact_bodies: Mapping[str, bytes],
    common_law_bodies: Mapping[str, bytes],
    repository_root: Path,
) -> _VerifiedRawInputs:
    try:
        request, manifest = bind_task_request_to_manifest(
            task_request, batch_manifest_bytes
        )
        manifest = validate_batch_manifest(manifest)
    except ValueError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "task request does not bind the canonical batch manifest"
        ) from exc
    task_index = _strict_int(
        request["task_index"], label="task index", minimum=0
    )
    task = _mapping(manifest["tasks"][task_index], label="manifest task")
    common = _mapping(manifest["common_law"], label="common law")
    if not isinstance(repository_root, Path) or not repository_root.is_dir():
        raise CorpusLegalFeasibilityVerificationError(
            "repository_root must be an existing pathlib.Path directory"
        )

    completion_identity = _mapping(
        common["artifact_source_authority_completion"],
        label="artifact source-authority completion identity",
    )
    normalized_completion_identity = _validate_raw_object_identity(
        artifact_source_authority_completion_bytes,
        completion_identity,
        label="artifact source-authority completion",
    )
    completion_internal_sha = _strict_sha(
        common["artifact_source_authority_completion_sha256"],
        label="artifact source-authority completion internal SHA",
    )
    if completion_internal_sha == normalized_completion_identity["sha256"]:
        raise CorpusLegalFeasibilityVerificationError(
            "artifact source-authority object/internal hashes are conflated"
        )
    try:
        completion = validate_artifact_source_completion_bytes(
            artifact_source_authority_completion_bytes
        )
    except CorpusArtifactSourceAuthorityError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "artifact source-authority completion failed strict replay"
        ) from exc
    authority_tasks = _sequence(
        completion["tasks"], label="artifact source-authority tasks"
    )
    if task_index >= len(authority_tasks):
        raise CorpusLegalFeasibilityVerificationError(
            "artifact source-authority task row is absent"
        )
    authority_task = _mapping(
        authority_tasks[task_index],
        label=f"artifact source-authority task[{task_index}]",
    )
    task_authority_sha = _strict_sha(
        task["artifact_source_authority_task_sha256"],
        label="manifest artifact source-authority task SHA",
    )
    completion_manifest_sha = _strict_sha(
        common["later_source_freeze_manifest_sha256"],
        label="artifact source-authority later-source manifest SHA",
    )
    completion_source_identity = _mapping(
        common["source_receipts"], label="common-law sources"
    )["later_source_freeze"]
    if (
        completion["completion_sha256"] != completion_internal_sha
        or completion["authority_scope"]
        != ARTIFACT_SOURCE_UNIVERSE_SCOPE
        or completion["later_source_freeze_object"]
        != completion_source_identity
        or completion["later_source_freeze_manifest_sha256"]
        != completion_manifest_sha
        or authority_task["task_index"] != task_index
        or authority_task["season"] != task["season"]
        or authority_task["week"] != task["week"]
        or authority_task["slate_id"] != task["slate_id"]
        or authority_task["universe_scope"]
        != ARTIFACT_SOURCE_UNIVERSE_SCOPE
        or authority_task["task_source_authority_sha256"]
        != task_authority_sha
        or authority_task["later_source_freeze_manifest_sha256"]
        != completion_manifest_sha
        or authority_task["world_artifact_receipts"]
        != task["world_artifact_receipts"]
        or authority_task["world_artifact_receipt_set_sha256"]
        != task["world_artifact_receipt_set_sha256"]
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "artifact source-authority completion/task binding differs"
        )

    _validate_raw_object_identity(
        effective_policy_inventory_bytes,
        common["effective_policy_inventory_identity"],
        label="effective-policy inventory",
    )
    inventory_parsed = _mapping(
        _parse_canonical_json_bytes(
            effective_policy_inventory_bytes,
            label="effective-policy inventory",
        ),
        label="effective-policy inventory",
    )
    try:
        inventory = validate_effective_policy_rule_inventory(
            inventory_parsed, repository_root
        )
    except EffectivePolicyInventoryError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "effective-policy inventory does not regenerate"
        ) from exc
    inventory_hashes = {
        "effective_policy_inventory_sha256": inventory["inventory_sha256"],
        "effective_policy_rule_universe_sha256": inventory[
            "rule_universe_sha256"
        ],
        "effective_policy_inventory_source_set_sha256": inventory[
            "source_set_sha256"
        ],
        "effective_policy_classified_input_projection_sha256": inventory[
            "classified_input_projection_sha256"
        ],
    }
    if any(common[key] != value for key, value in inventory_hashes.items()):
        raise CorpusLegalFeasibilityVerificationError(
            "common-law inventory hashes differ from regenerated inventory"
        )

    source_identity = _mapping(
        common["source_receipts"], label="common-law sources"
    )["later_source_freeze"]
    _validate_raw_object_identity(
        later_source_freeze_bytes,
        source_identity,
        label="later-source freeze",
    )
    source_parsed = _mapping(
        _parse_canonical_json_bytes(
            later_source_freeze_bytes, label="later-source freeze"
        ),
        label="later-source freeze",
    )
    if later_source_canonical_json(source_parsed) != later_source_freeze_bytes:
        raise CorpusLegalFeasibilityVerificationError(
            "later-source freeze canonical encoding differs"
        )
    freeze_sha = _strict_sha(
        common["later_source_freeze_manifest_sha256"],
        label="later-source manifest SHA",
    )
    try:
        source_freeze = validate_source_freeze(
            source_parsed, expected_freeze_sha256=freeze_sha
        )
    except LR8LaterSourceError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "later-source freeze does not validate"
        ) from exc
    matching = [
        row for row in source_freeze["slates"]
        if (row["season"], row["week"], row["slate_id"])
        == (task["season"], task["week"], task["slate_id"])
    ]
    if len(matching) != 1:
        raise CorpusLegalFeasibilityVerificationError(
            "source freeze does not contain exactly one task slate"
        )
    source_row = matching[0]
    if (
        authority_task["catalog_sha256"] != source_row["catalog_sha256"]
        or authority_task["incumbent_candidates_sha256"]
        != source_row["incumbent_candidates_sha256"]
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "artifact source-authority task differs from later-source slate"
        )
    if (
        not isinstance(world_artifact_bodies, Mapping)
        or set(world_artifact_bodies) != set(TASK_WORLD_SOURCE_ROLES)
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "world-artifact raw roles differ"
        )
    task_identities = _mapping(
        task["world_artifact_receipts"], label="task world artifacts"
    )
    replayed: dict[str, dict[str, object]] = {}
    bodies_by_block: dict[str, bytes] = {}
    for block, role, source_receipt in zip(
        rw.WORLD_BLOCKS,
        TASK_WORLD_SOURCE_ROLES,
        source_row["artifact_receipts"],
        strict=True,
    ):
        source_item = _mapping(source_receipt, label=f"source {role}")
        source_exact = {
            key: source_item[key]
            for key in ("uri", "generation", "sha256", "bytes")
        }
        task_exact = dict(_mapping(task_identities[role], label=role))
        retained = world_artifact_bodies[role]
        verified = _validate_raw_object_identity(
            retained, task_exact, label=role
        )
        if source_exact != task_exact:
            raise CorpusLegalFeasibilityVerificationError(
                f"{role} source/task identities differ"
            )
        replayed[role] = verified
        bodies_by_block[block] = retained
    artifact_set_sha = _strict_sha(
        task["world_artifact_receipt_set_sha256"],
        label="world-artifact set SHA",
    )
    if artifact_set_sha != batch_canonical_sha256(replayed):
        raise CorpusLegalFeasibilityVerificationError(
            "world-artifact receipt-set hash differs"
        )
    try:
        prepared = prepare_later_slate(
            source_freeze,
            expected_source_freeze_sha256=freeze_sha,
            season=int(task["season"]),
            week=int(task["week"]),
            artifact_bodies=bodies_by_block,
        )
    except LR8LaterSourceError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "raw sources cannot rebuild PreparedLaterSlate"
        ) from exc
    raw_players = tuple(prepared.players)
    raw_draws = prepared.player_draws
    if (
        type(raw_draws) is not np.ndarray
        or raw_draws.dtype != np.dtype(np.float32)
        or raw_draws.shape != (len(raw_players), EXPECTED_WORLD_COUNT)
        or not raw_draws.flags.c_contiguous
        or raw_draws.flags.writeable
        or not np.isfinite(raw_draws).all()
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "prepared draw matrix differs"
        )
    order = np.argsort(
        np.asarray([player.player_id for player in raw_players], dtype=str),
        kind="stable",
    )
    players = tuple(raw_players[int(index)] for index in order)
    player_draws = np.ascontiguousarray(raw_draws[order], dtype=np.float32)
    player_draws.flags.writeable = False
    _player_map(players)
    expected_world_ids = tuple(
        rw.WorldId(block, index)
        for block in rw.WORLD_BLOCKS
        for index in range(rw.WORLDS_PER_BLOCK)
    )
    if tuple(prepared.world_ids) != expected_world_ids:
        raise CorpusLegalFeasibilityVerificationError(
            "prepared world-id lattice differs"
        )
    incumbents = tuple(
        _audit_dk_classic(players, roster)
        for roster in prepared.incumbent_candidates
    )
    if len(set(incumbents)) != len(incumbents):
        raise CorpusLegalFeasibilityVerificationError(
            "prepared incumbent candidates repeat"
        )
    artifact_by_block = tuple(
        (
            block,
            _strict_sha(
                prepared.artifact_sha256_by_block[block],
                label=f"prepared {block} SHA",
            ),
        )
        for block in rw.WORLD_BLOCKS
    )
    if (
        prepared.source_freeze_sha256 != freeze_sha
        or dict(artifact_by_block) != {
            block: replayed[role]["sha256"]
            for block, role in zip(
                rw.WORLD_BLOCKS, TASK_WORLD_SOURCE_ROLES, strict=True
            )
        }
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "prepared source/artifact identity differs"
        )
    source_body: dict[str, object] = {
        "schema": "corpus-authoritative-task-source/v1",
        "batch_manifest_sha256": manifest["batch_manifest_sha256"],
        "task_index": task_index,
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
            "season": prepared.season,
            "week": prepared.week,
            "slate_id": prepared.slate_id,
        },
        "later_source_freeze_object": source_identity,
        "later_source_freeze_manifest_sha256": freeze_sha,
        "world_artifact_receipts": replayed,
        "world_artifact_receipt_set_sha256": artifact_set_sha,
        "prepared_catalog_sha256": _canonical_sha256([{
            "id": player.player_id,
            "pos": player.position,
            "team": player.team,
            "opp": player.opponent,
            "game_id": player.game_id,
            "salary": player.salary,
        } for player in players]),
        "prepared_incumbent_candidates_sha256": _canonical_sha256([
            list(roster) for roster in incumbents
        ]),
        "prepared_player_draws_sha256": _matrix_content_sha256(
            player_draws, dtype="float32-le"
        ),
        "prepared_world_count": EXPECTED_WORLD_COUNT,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    source_sha = _canonical_sha256(source_body)
    source_payload = _canonical_json_bytes({
        **source_body, "binding_sha256": source_sha,
    })

    if (
        not isinstance(common_law_bodies, Mapping)
        or set(common_law_bodies) != set(_COMMON_LAW_BODY_ROLES)
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "common-law body roles differ"
        )
    identities: dict[str, dict[str, object]] = {}
    parsed_bodies: dict[str, object] = {}
    for role in _COMMON_LAW_BODY_ROLES:
        raw = common_law_bodies[role]
        identities[role] = _validate_raw_object_identity(
            raw, common[role], label=f"common-law {role}"
        )
        parsed_bodies[role] = _parse_canonical_json_bytes(
            raw, label=f"common-law {role}"
        )
    code_source, local_commit_verified = _verify_code_source_body(
        parsed_bodies["code_source"],
        repository_root=repository_root,
        immutable_image=_mapping(
            common["immutable_image"], label="manifest immutable image"
        ),
    )
    for role, expected in _registered_mechanism_bodies().items():
        if parsed_bodies[role] != expected:
            raise CorpusLegalFeasibilityVerificationError(
                f"common-law {role} semantics differ"
            )
    schedule, schedule_sha = _validate_world_schedule(
        parsed_bodies["world_schedule"],
        manifest=manifest,
        task_index=task_index,
        player_draws=player_draws,
    )
    solver_authority = _cbc_runtime_authority()
    if common["solver"] != solver_authority:
        raise CorpusLegalFeasibilityVerificationError(
            "runtime CBC authority differs from common law"
        )
    expected_budget = {
        "solve_attempts_per_seed": VISITS_PER_BLOCK,
        "worlds_per_block": WORLDS_PER_BLOCK,
        "solver_timeout_seconds": SOLVER_TIMEOUT_SECONDS,
        "candidate_entry_budget": MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION,
        "selected_entry_budget": ENTRY_COUNT,
    }
    if common["solve_budget"] != expected_budget:
        raise CorpusLegalFeasibilityVerificationError(
            "common-law solve budget differs"
        )
    ambient = list(inventory["classified_input_projection"][
        "ambient_process_keys_requiring_absence"
    ])
    if (
        len(ambient) != 97
        or common["worker_environment_inheritance"] is not False
        or common["worker_graph_mutation"] is not False
        or common["fresh_model_state_per_parameter_set"] is not True
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "ambient/worker common law differs"
        )
    law_body: dict[str, object] = {
        "schema": "corpus-authoritative-registered-law/v1",
        "common_law_sha256": manifest["common_law_sha256"],
        "mechanism_object_identities": identities,
        "mechanism_body_sha256": {
            role: sha256(common_law_bodies[role]).hexdigest()
            for role in _COMMON_LAW_BODY_ROLES
        },
        "code_source": code_source,
        "code_source_runtime_repository_head_verified": (
            local_commit_verified
        ),
        "immutable_image": common["immutable_image"],
        "immutable_image_sha256": _canonical_sha256(
            common["immutable_image"]
        ),
        "runtime_image_terminal_verification_required": True,
        "terminal_verification_law": _CODE_SOURCE_TERMINAL_VERIFICATION,
        "artifact_source_authority": {
            "completion_object": dict(normalized_completion_identity),
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
        "semantic_input_projection": {
            "typed_request_local_fields": list(PARAMETER_ORDER),
            "frozen_common_law_sha256": manifest["common_law_sha256"],
            "infrastructure_inherited_as_science": False,
            "ambient_score_relevant_keys_present": [],
        },
        "ambient_score_relevant_keys_requiring_absence": ambient,
        "ambient_score_relevant_key_count": len(ambient),
        "all_ambient_score_relevant_semantic_inputs_absent": True,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    law_sha = _canonical_sha256(law_body)
    law_payload = _canonical_json_bytes({
        **law_body, "binding_sha256": law_sha,
    })
    profiles = _profile_payloads()
    runtime_payloads = tuple(
        _build_runtime_policy_payload(
            inventory, profile, visit_schedule_sha256=schedule_sha
        )
        for profile in profiles
    )
    return _VerifiedRawInputs(
        request=request,
        manifest=manifest,
        task=task,
        inventory=inventory,
        players=players,
        player_draws=player_draws,
        incumbent_candidates=incumbents,
        source_freeze_sha256=freeze_sha,
        artifact_sha256_by_block=artifact_by_block,
        artifact_source_authority_completion_object_sha256=str(
            normalized_completion_identity["sha256"]
        ),
        artifact_source_authority_completion_sha256=(
            completion_internal_sha
        ),
        artifact_source_authority_task_sha256=task_authority_sha,
        source_binding_payload=source_payload,
        source_binding_sha256=source_sha,
        registered_law_payload=law_payload,
        registered_law_sha256=law_sha,
        code_source_object_sha256=str(identities["code_source"]["sha256"]),
        code_source_body_sha256=sha256(
            common_law_bodies["code_source"]
        ).hexdigest(),
        immutable_image_sha256=_canonical_sha256(
            common["immutable_image"]
        ),
        runtime_image_terminal_verification_required=True,
        solver_authority=solver_authority,
        visit_schedule=schedule,
        visit_schedule_sha256=schedule_sha,
        profiles=profiles,
        runtime_policy_payloads=runtime_payloads,
    )


def _violation_census(
    players: Sequence[rw.PlayerSpec], rosters: Sequence[Sequence[object]]
) -> dict[str, int]:
    counts = Counter({name: 0 for name in PARAMETER_ORDER})
    for roster in rosters:
        counts.update(_house_rule_violations(players, roster))
    return {name: counts[name] for name in PARAMETER_ORDER}


def _build_lexicographic_problem(
    players: Sequence[rw.PlayerSpec],
    profile: Mapping[str, object],
    objective_micro: Sequence[int],
    *,
    model_name: str,
) -> tuple[
    pulp.LpProblem,
    dict[str, pulp.LpVariable],
    pulp.LpAffineExpression,
    int,
    dict[str, int],
]:
    rows, _ = _player_map(players)
    objective = tuple(
        _strict_int(value, label="objective micro")
        for value in objective_micro
    )
    if len(objective) != len(rows):
        raise CorpusLegalFeasibilityVerificationError(
            "objective/player rows are misaligned"
        )
    values = _mapping(profile["parameter_values"], label="profile values")
    problem = pulp.LpProblem(
        _strict_string(model_name, label="model name"), pulp.LpMaximize
    )
    decision = {
        player.player_id: pulp.LpVariable(f"x_{index:04d}", cat="Binary")
        for index, player in enumerate(rows)
    }
    problem += pulp.lpSum(
        decision[player.player_id] * player.salary for player in rows
    ) <= rw.SALARY_CAP
    minimum_salary = int(values["min_lineup_salary"])
    if minimum_salary:
        problem += pulp.lpSum(
            decision[player.player_id] * player.salary for player in rows
        ) >= minimum_salary
    problem += pulp.lpSum(decision.values()) == rw.ROSTER_SIZE

    def count(position: str) -> pulp.LpAffineExpression:
        return pulp.lpSum(
            decision[player.player_id]
            for player in rows if player.position == position
        )

    problem += count("QB") == 1
    problem += count("DST") == 1
    problem += count("RB") >= 2
    problem += count("RB") <= 3
    problem += count("WR") >= 3
    problem += count("WR") <= 4
    problem += count("TE") >= 1
    problem += count("TE") <= 2
    teams = sorted({player.team for player in rows})
    for team in teams:
        problem += pulp.lpSum(
            decision[player.player_id]
            for player in rows if player.team == team
        ) <= rw.MAX_FROM_TEAM
    games = sorted({player.game_id for player in rows if player.game_id})
    if len(games) >= rw.MIN_GAMES:
        for game in games:
            problem += pulp.lpSum(
                decision[player.player_id]
                for player in rows if player.game_id != game
            ) >= 1

    catchers_by_team: dict[str, list[str]] = {}
    qbs_by_team: dict[str, list[str]] = {}
    for player in rows:
        if player.position in {"WR", "TE"}:
            catchers_by_team.setdefault(player.team, []).append(
                player.player_id
            )
        elif player.position == "QB":
            qbs_by_team.setdefault(player.team, []).append(player.player_id)
    qb_stack_min = int(values["qb_stack_min"])
    bring_back_min = int(values["bring_back_min"])
    for team in teams:
        qbs = qbs_by_team.get(team, [])
        if not qbs:
            continue
        qb_sum = pulp.lpSum(decision[player_id] for player_id in qbs)
        problem += pulp.lpSum(
            decision[player_id]
            for player_id in catchers_by_team.get(team, [])
        ) >= qb_stack_min * qb_sum
        if bring_back_min:
            opponents = {
                player.opponent
                for player in rows
                if player.position == "QB" and player.team == team
            }
            opponent_skill = [
                player.player_id
                for player in rows
                if player.team in opponents
                and player.position in {"RB", "WR", "TE"}
            ]
            problem += pulp.lpSum(
                decision[player_id] for player_id in opponent_skill
            ) >= bring_back_min * qb_sum
    if values["forbid_rb_vs_dst"] is True:
        for dst in (player for player in rows if player.position == "DST"):
            for rb_id in (
                player.player_id for player in rows
                if player.position == "RB" and player.team == dst.opponent
            ):
                problem += decision[rb_id] + decision[dst.player_id] <= 1
    if values["forbid_two_rb_same_team"] is True:
        rbs_by_team: dict[str, list[str]] = {}
        for player in rows:
            if player.position == "RB":
                rbs_by_team.setdefault(player.team, []).append(player.player_id)
        for ids in rbs_by_team.values():
            if len(ids) > 1:
                problem += pulp.lpSum(
                    decision[player_id] for player_id in ids
                ) <= 1
    primary_expression = pulp.lpSum(
        decision[player.player_id] * objective[index]
        for index, player in enumerate(rows)
    )
    problem.setObjective(primary_expression)
    ranked_ids = tuple(sorted(decision))
    radix = rw.ROSTER_SIZE * (len(ranked_ids) - rw.ROSTER_SIZE) + 1
    rank_by_id = {
        player_id: rank + 1 for rank, player_id in enumerate(ranked_ids)
    }
    player_index = {
        player.player_id: index for index, player in enumerate(rows)
    }
    coefficients = {
        player_id: objective[player_index[player_id]] * radix
        - rank_by_id[player_id]
        for player_id in ranked_ids
    }
    if (
        radix <= rw.ROSTER_SIZE * (len(ranked_ids) - rw.ROSTER_SIZE)
        or sum(sorted(
            (abs(value) for value in coefficients.values()), reverse=True
        )[:rw.ROSTER_SIZE]) > MAX_EXACT_INTEGER
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "combined lexicographic objective exceeds exact range"
        )
    combined = pulp.lpSum(
        coefficients[player_id] * decision[player_id]
        for player_id in ranked_ids
    )
    problem.sense = pulp.LpMaximize
    problem.setObjective(combined)
    return problem, decision, combined, radix, rank_by_id


def _objective_projection_sha256(problem: pulp.LpProblem) -> str:
    expression = problem.objective
    if expression is None:
        raise CorpusLegalFeasibilityVerificationError(
            "solver stage objective is absent"
        )
    return _canonical_sha256({
        "sense": int(problem.sense),
        "constant": str(expression.constant),
        "coefficients": [
            {"variable": variable.name, "coefficient": str(coefficient)}
            for variable, coefficient in sorted(
                expression.items(), key=lambda pair: pair[0].name
            )
        ],
    })


def _write_mps(
    problem: pulp.LpProblem,
) -> tuple[bytes, dict[str, str], dict[str, str]]:
    with tempfile.TemporaryDirectory(
        prefix="corpus_independent_mps_"
    ) as directory:
        path = Path(directory) / "model.mps"
        _, variable_names, constraint_names, _ = problem.writeMPS(
            str(path), rename=1
        )
        try:
            raw = path.read_bytes()
        except OSError as exc:
            raise CorpusLegalFeasibilityVerificationError(
                "independent MPS cannot be read"
            ) from exc
    if not raw:
        raise CorpusLegalFeasibilityVerificationError(
            "independent MPS is empty"
        )
    return raw, dict(variable_names), dict(constraint_names)


_CBC_NUMBER: Final = (
    r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?"
)
_CBC_COMMAND_LINE_SUFFIX: Final = " (default strategy 1)"
_CBC_OPTIMAL_TERMINAL: Final = "Result - Optimal solution found"
_CBC_INFEASIBLE_TERMINAL: Final = re.compile(
    r"(?:Result - Problem proven infeasible|"
    r"Problem is infeasible(?: - .*?)?)"
)
_CBC_SOLUTION_ROW: Final = re.compile(
    rf"^(?:(?P<marker>\*\*)\s+)?\s*(?P<ordinal>\d+)\s+"
    rf"(?P<name>[CX]\d{{7}})\s+(?P<value>{_CBC_NUMBER})\s+"
    rf"(?P<reduced>{_CBC_NUMBER})\s*$"
)
_CBC_WARNING_MARKER: Final = re.compile(r"\b(?:Cbc|Cgl|Clp|Coin)\d+W\b")
_CBC_FORBIDDEN_MARKER: Final = re.compile(
    r"Stopped on|Exiting on maximum|Partial search|within gap tolerance|"
    r"Upper bound:|^Gap:|unbounded|abandoned|\bnan\b|"
    r"\binf(?:inity)?\b|Exiting as integer gap|"
    r"maximum (?:time|node|solution)",
    re.IGNORECASE | re.MULTILINE,
)
_CBC_FINITE_INFEASIBILITY_DIAGNOSTIC: Final = re.compile(
    r"^(?:Clp\d+I\s+)?\d+\s+Obj\s+"
    rf"{_CBC_NUMBER}\s+Primal inf\s+{_CBC_NUMBER}"
    r"(?:\s+\(\d+\))?"
    rf"(?:\s+Dual inf\s+{_CBC_NUMBER}(?:\s+\(\d+\))?)?\s*$"
)


def _parse_cbc_solution(
    raw: bytes,
    *,
    expected_status: str,
    variable_names: Mapping[str, str],
    constraint_names: Mapping[str, str],
) -> dict[str, float]:
    if type(raw) is not bytes or not raw or not raw.endswith(b"\n"):
        raise CorpusLegalFeasibilityVerificationError(
            "CBC solution is empty or lacks terminal newline"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC solution is not UTF-8"
        ) from exc
    if "\x00" in text:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC solution contains NUL"
        )
    lines = text.splitlines()
    terminal = re.fullmatch(
        rf"{expected_status} - objective value {_CBC_NUMBER}", lines[0]
    )
    if terminal is None or len(lines) < 2:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC solution terminal grammar differs"
        )
    expected_names = set(variable_names.values()) | set(
        constraint_names.values()
    )
    values: dict[str, float] = {}
    for line in lines[1:]:
        match = _CBC_SOLUTION_ROW.fullmatch(line)
        if match is None:
            raise CorpusLegalFeasibilityVerificationError(
                "CBC solution row grammar differs"
            )
        name = match.group("name")
        if name in values or name not in expected_names:
            raise CorpusLegalFeasibilityVerificationError(
                "CBC solution row name coverage differs"
            )
        if expected_status == "Optimal" and match.group("marker") is not None:
            raise CorpusLegalFeasibilityVerificationError(
                "optimal CBC solution contains infeasibility marker"
            )
        value = float(match.group("value"))
        reduced = float(match.group("reduced"))
        if not np.isfinite(value) or not np.isfinite(reduced):
            raise CorpusLegalFeasibilityVerificationError(
                "CBC solution row is non-finite"
            )
        values[name] = value
    if set(values) != expected_names:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC solution does not cover every MPS row and variable"
        )
    return values


def _masked_cbc_log(log: str) -> str:
    rows: list[str] = []
    for line in log.splitlines(keepends=True):
        body = line.rstrip("\r\n")
        ending = line[len(body):]
        if body.startswith("command line - "):
            rows.append("command line - <validated-separately>" + ending)
        elif _CBC_FINITE_INFEASIBILITY_DIAGNOSTIC.fullmatch(body):
            rows.append(re.sub(
                r"\binf\b",
                "finite_lp_diagnostic",
                body,
                flags=re.IGNORECASE,
            ) + ending)
        else:
            rows.append(body + ending)
    return "".join(rows)


def _validate_cbc_command_and_log(
    log_raw: bytes,
    *,
    receipt: Mapping[str, object],
    expected_status: str,
    model_sha256: str,
    solver_authority: Mapping[str, object],
) -> None:
    try:
        log = log_raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC log is not UTF-8"
        ) from exc
    if not log or "\x00" in log:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC log is empty or contains NUL"
        )
    command_lines = re.findall(r"^command line - .*?$", log, re.MULTILINE)
    if len(command_lines) != 1:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC log command-line cardinality differs"
        )
    command_line = command_lines[0]
    if sha256(command_line.encode("utf-8")).hexdigest() != receipt[
        "raw_command_sha256"
    ]:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC raw-command hash differs"
        )
    command_body = command_line.removeprefix("command line - ")
    if not command_body.endswith(_CBC_COMMAND_LINE_SUFFIX):
        raise CorpusLegalFeasibilityVerificationError(
            "CBC command default-strategy suffix differs"
        )
    command_arguments = command_body.removesuffix(_CBC_COMMAND_LINE_SUFFIX)
    try:
        tokens = shlex.split(command_arguments)
    except ValueError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC command line cannot be tokenized"
        ) from exc
    if len(tokens) < 6:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC command line is truncated"
        )
    binary_path = Path(tokens[0])
    model_path = Path(tokens[1])
    if (
        not binary_path.is_absolute()
        or not binary_path.is_file()
        or _file_sha256(binary_path) != solver_authority["binary_sha256"]
        or not model_path.is_absolute()
        or model_path.name != f"{model_sha256}.mps"
        or tokens[2:4] != ["-max", "-sec"]
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "CBC command binary/model/sense grammar differs"
        )
    try:
        stage_seconds = float(tokens[4])
    except ValueError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC command deadline is malformed"
        ) from exc
    requested_microseconds = _strict_int(
        receipt["cbc_requested_microseconds"],
        label="CBC requested microseconds",
        minimum=1,
    )
    if (
        command_line
        != (
            "command line - " + " ".join(tokens)
            + _CBC_COMMAND_LINE_SUFFIX
        )
        or tokens[4] != f"{requested_microseconds / 1_000_000:.6f}"
        or not np.isfinite(stage_seconds)
        or stage_seconds <= 0
        or stage_seconds > SOLVER_TIMEOUT_SECONDS
        or abs(
            stage_seconds * 1_000_000
            - requested_microseconds
        ) > 1.0
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "CBC command deadline differs from monotonic receipt"
        )
    option_tokens: list[str] = []
    for option in CBC_OPTIONS:
        name, value = option.split(" ", 1)
        option_tokens.extend((f"-{name}", value))
    expected_tail_prefix = [
        *option_tokens,
        "-ratio",
        "0.0",
        "-allow",
        "0.0",
        "-threads",
        str(CBC_THREADS),
        "-timeMode",
        "elapsed",
        "-solve",
        "-printingOptions",
        "all",
        "-solution",
    ]
    if tokens[5:-1] != expected_tail_prefix:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC command option grammar differs"
        )
    solution_path = Path(tokens[-1])
    if (
        not solution_path.is_absolute()
        or solution_path.parent != model_path.parent
        or solution_path.name != f"{model_sha256}.sol"
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "CBC solution path is not content-addressed with the MPS"
        )
    if re.findall(
        r"^Coin0008I MODEL read with (\d+) errors\s*$", log, re.MULTILINE
    ) != ["0"]:
        raise CorpusLegalFeasibilityVerificationError(
            "CBC MPS read receipt differs"
        )
    error_text = re.sub(
        r"^Coin0008I MODEL read with 0 errors\s*$",
        "",
        log,
        count=1,
        flags=re.MULTILINE,
    )
    lines = log.splitlines()
    optimal = [line for line in lines if line == _CBC_OPTIMAL_TERMINAL]
    infeasible = [
        line for line in lines
        if _CBC_INFEASIBLE_TERMINAL.fullmatch(line) is not None
    ]
    masked = _masked_cbc_log(log)
    masked = re.sub(
        r"^(?:Result - Problem proven infeasible|"
        r"Problem is infeasible(?: - .*?)?)[ \t]*$",
        "<exact-infeasible-terminal>",
        masked,
        flags=re.MULTILINE,
    )
    invalid = (
        _CBC_WARNING_MARKER.search(log) is not None
        or _CBC_FORBIDDEN_MARKER.search(masked) is not None
        or re.search(r"\berrors?\b", error_text, re.IGNORECASE) is not None
    )
    if expected_status == "optimal":
        terminals_ok = (
            optimal == [_CBC_OPTIMAL_TERMINAL] and not infeasible
        )
        exact_terminal = _CBC_OPTIMAL_TERMINAL
    else:
        terminals_ok = len(infeasible) == 1 and not optimal
        exact_terminal = infeasible[0] if infeasible else None
    if (
        invalid
        or not terminals_ok
        or receipt["exact_terminal_record"] != exact_terminal
        or receipt["warning_or_forbidden_marker_detected"] is not False
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "CBC clean exact terminal grammar differs"
        )


def _validate_stage_receipt_common(
    receipt: Mapping[str, object],
    *,
    expected_stage: str,
    expected_status: str,
    expected_objective_sha256: str,
    expected_witness_sha256: str | None,
    expected_model: bytes,
    solver_authority: Mapping[str, object],
) -> None:
    expected_keys = frozenset({
        "stage",
        "status",
        "pulp_status",
        "pulp_solution_status",
        "remaining_before_microseconds",
        "cbc_requested_microseconds",
        "host_watchdog_microseconds",
        "elapsed_microseconds",
        "remaining_after_microseconds",
        "objective_sha256",
        "witness_sha256",
        "log_sha256",
        "log_bytes",
        "solution_sha256",
        "solution_bytes",
        "model_sha256",
        "model_bytes",
        "model_pre_exec_sha256",
        "model_post_exit_sha256",
        "model_regular_exclusive_inode",
        "model_path_command_bound",
        "raw_command_sha256",
        "exact_terminal_record",
        "warning_or_forbidden_marker_detected",
        "solver_binary_sha256",
        "solver_options_sha256",
    })
    _exact_keys(receipt, expected_keys, label="solver stage receipt")
    model_sha = sha256(expected_model).hexdigest()
    expected_pulp = 1 if expected_status == "optimal" else -1
    pulp_status = _strict_int(
        receipt["pulp_status"], label="stage pulp status"
    )
    pulp_solution_status = _strict_int(
        receipt["pulp_solution_status"], label="stage pulp solution status"
    )
    log_bytes = _strict_int(
        receipt["log_bytes"], label="stage log bytes", minimum=1
    )
    solution_bytes = _strict_int(
        receipt["solution_bytes"], label="stage solution bytes", minimum=1
    )
    model_bytes = _strict_int(
        receipt["model_bytes"], label="stage model bytes", minimum=1
    )
    if (
        receipt["stage"] != expected_stage
        or receipt["status"] != expected_status
        or pulp_status != expected_pulp
        or pulp_solution_status != expected_pulp
        or receipt["objective_sha256"] != expected_objective_sha256
        or receipt["witness_sha256"] != expected_witness_sha256
        or receipt["model_sha256"] != model_sha
        or model_bytes != len(expected_model)
        or receipt["model_pre_exec_sha256"] != model_sha
        or receipt["model_post_exit_sha256"] != model_sha
        or receipt["model_regular_exclusive_inode"] is not True
        or receipt["model_path_command_bound"] is not True
        or receipt["solver_binary_sha256"]
        != solver_authority["binary_sha256"]
        or receipt["solver_options_sha256"]
        != solver_authority["options_sha256"]
        or receipt["raw_command_sha256"] is None
        or receipt["solution_sha256"] is None
        or type(receipt["model_regular_exclusive_inode"]) is not bool
        or type(receipt["model_path_command_bound"]) is not bool
        or type(receipt["warning_or_forbidden_marker_detected"]) is not bool
        or log_bytes <= 0
        or solution_bytes <= 0
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "solver stage receipt authority differs"
        )
    before = _strict_int(
        receipt["remaining_before_microseconds"],
        label="stage remaining before",
        minimum=1,
    )
    elapsed = _strict_int(
        receipt["elapsed_microseconds"], label="stage elapsed", minimum=0
    )
    after = _strict_int(
        receipt["remaining_after_microseconds"],
        label="stage remaining after",
        minimum=1,
    )
    requested = _strict_int(
        receipt["cbc_requested_microseconds"],
        label="stage CBC requested microseconds",
        minimum=1,
    )
    watchdog = _strict_int(
        receipt["host_watchdog_microseconds"],
        label="stage host watchdog microseconds",
        minimum=1,
    )
    if (
        before > SOLVER_TIMEOUT_SECONDS * 1_000_000
        or after > before
        or elapsed > before + 10
        or requested > before
        or watchdog > requested
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "solver stage timing receipt differs"
        )


def _verify_attempt_stage_evidence(
    *,
    raw_inputs: _VerifiedRawInputs,
    attempt: Mapping[str, object],
    proof: Mapping[str, object],
    stage_rows: Sequence[Mapping[str, object]],
    raw_members: Sequence[bytes],
) -> None:
    variant = int(attempt["variant_ordinal"])
    visit = int(attempt["visit_ordinal"])
    profile = raw_inputs.profiles[variant]
    world = raw_inputs.visit_schedule[visit]
    flat = (
        rw.WORLD_BLOCKS.index(world.block) * rw.WORLDS_PER_BLOCK + world.index
    )
    objective = _micro_objective(
        raw_inputs.player_draws, world_column=flat
    )
    problem, decision, combined, radix, rank_by_id = (
        _build_lexicographic_problem(
            raw_inputs.players,
            profile,
            objective,
            model_name=(
                f"corpus_authoritative_v{variant:02d}_visit_{visit:04d}"
            ),
        )
    )
    roster = _audit_dk_classic(
        raw_inputs.players,
        _sequence(attempt["roster"], label="attempt roster"),
    )
    _audit_profile(
        raw_inputs.players,
        roster,
        _mapping(profile["parameter_values"], label="profile values"),
    )
    primary = sum(
        objective[index]
        for index, player in enumerate(raw_inputs.players)
        if player.player_id in roster
    )
    rank_sum = sum(rank_by_id[player_id] for player_id in roster)
    combined_optimum = primary * radix - rank_sum
    if (
        attempt["primary_optimum_micro"] != primary
        or attempt["secondary_rank_sum"] != rank_sum
        or attempt["lexicographic_radix"] != radix
        or attempt["combined_optimum"] != combined_optimum
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "attempt lexicographic objective does not reconstruct"
        )
    stage_one_objective_sha = _objective_projection_sha256(problem)
    stage_one_mps, variable_names, constraint_names = _write_mps(problem)
    problem += (
        combined == combined_optimum,
        "freeze_lexicographic_combined_optimum",
    )
    problem += pulp.lpSum(
        decision[player_id] for player_id in roster
    ) <= rw.ROSTER_SIZE - 1, "exclude_combined_witness"
    problem.setObjective(combined)
    stage_two_objective_sha = _objective_projection_sha256(problem)
    stage_two_mps, stage_two_variables, stage_two_constraints = _write_mps(
        problem
    )
    receipts = tuple(
        _mapping(row["stage_receipt"], label="stage receipt")
        for row in stage_rows
    )
    proof_stages = tuple(
        _mapping(row, label="solver proof stage")
        for row in _sequence(proof["stages"], label="solver proof stages")
    )
    if receipts != proof_stages or len(receipts) != 2 or len(raw_members) != 4:
        raise CorpusLegalFeasibilityVerificationError(
            "attempt shard/proof stage cross-link differs"
        )
    stage_specs = (
        (
            receipts[0],
            "lexicographic_combined_optimum",
            "optimal",
            stage_one_objective_sha,
            _canonical_sha256(list(roster)),
            stage_one_mps,
            variable_names,
            constraint_names,
            raw_members[0],
            raw_members[1],
            "Optimal",
        ),
        (
            receipts[1],
            "combined_optimum_collision",
            "infeasible",
            stage_two_objective_sha,
            None,
            stage_two_mps,
            stage_two_variables,
            stage_two_constraints,
            raw_members[2],
            raw_members[3],
            "Infeasible",
        ),
    )
    previous_after = SOLVER_TIMEOUT_SECONDS * 1_000_000
    total_elapsed = 0
    for (
        receipt,
        stage_name,
        status,
        objective_sha,
        witness_sha,
        model_raw,
        variables,
        constraints,
        log_raw,
        solution_raw,
        solution_status,
    ) in stage_specs:
        _validate_stage_receipt_common(
            receipt,
            expected_stage=stage_name,
            expected_status=status,
            expected_objective_sha256=objective_sha,
            expected_witness_sha256=witness_sha,
            expected_model=model_raw,
            solver_authority=raw_inputs.solver_authority,
        )
        if (
            len(log_raw) != receipt["log_bytes"]
            or sha256(log_raw).hexdigest() != receipt["log_sha256"]
            or len(solution_raw) != receipt["solution_bytes"]
            or sha256(solution_raw).hexdigest() != receipt["solution_sha256"]
            or len(log_raw) + len(solution_raw)
            > MAX_SOLVER_EVIDENCE_BYTES_PER_STAGE
        ):
            raise CorpusLegalFeasibilityVerificationError(
                "packed raw solver evidence differs from stage receipt"
            )
        _validate_cbc_command_and_log(
            log_raw,
            receipt=receipt,
            expected_status=status,
            model_sha256=sha256(model_raw).hexdigest(),
            solver_authority=raw_inputs.solver_authority,
        )
        solution_values = _parse_cbc_solution(
            solution_raw,
            expected_status=solution_status,
            variable_names=variables,
            constraint_names=constraints,
        )
        if status == "optimal":
            inverse_variables = {
                renamed: original for original, renamed in variables.items()
            }
            by_variable = {
                variable.name: player_id
                for player_id, variable in decision.items()
            }
            selected: list[str] = []
            for renamed, original in inverse_variables.items():
                value = solution_values[renamed]
                rounded = round(value)
                if abs(value - rounded) > 1e-7 or rounded not in (0, 1):
                    raise CorpusLegalFeasibilityVerificationError(
                        "optimal CBC solution variable is nonbinary"
                    )
                if rounded == 1:
                    selected.append(by_variable[original])
            if tuple(sorted(selected)) != roster:
                raise CorpusLegalFeasibilityVerificationError(
                    "CBC solution witness differs from attempt roster"
                )
        before = int(receipt["remaining_before_microseconds"])
        after = int(receipt["remaining_after_microseconds"])
        total_elapsed += int(receipt["elapsed_microseconds"])
        if before > previous_after:
            raise CorpusLegalFeasibilityVerificationError(
                "solver stage deadline increased between stages"
            )
        previous_after = after
    if total_elapsed >= SOLVER_TIMEOUT_SECONDS * 1_000_000:
        raise CorpusLegalFeasibilityVerificationError(
            "solver stages exhausted the total cell deadline"
        )
    proof_elapsed = _strict_int(
        proof["total_elapsed_microseconds"],
        label="solver proof total elapsed microseconds",
        minimum=0,
    )
    elapsed_at_last_terminal = (
        SOLVER_TIMEOUT_SECONDS * 1_000_000 - previous_after
    )
    if (
        proof_elapsed >= SOLVER_TIMEOUT_SECONDS * 1_000_000
        or proof_elapsed + 10 < total_elapsed
        or proof_elapsed + 10 < elapsed_at_last_terminal
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "solver proof total elapsed time differs from stage receipts"
        )


def _parse_attempt_ledger(
    raw_inputs: _VerifiedRawInputs,
    draft: _RawDraftAuthorities,
) -> tuple[Mapping[str, object], ...]:
    ledger = _mapping(
        _parse_canonical_json_bytes(
            draft.attempt_ledger_payload, label="attempt ledger"
        ),
        label="attempt ledger",
    )
    _exact_keys(
        ledger,
        frozenset({
            "schema",
            "source_binding_sha256",
            "registered_law_sha256",
            "visit_schedule_sha256",
            "parameter_set_order",
            "attempt_count",
            "attempts",
            "outcome_columns_read",
            "uses_realized_outcomes",
            "attempt_ledger_sha256",
        }),
        label="attempt ledger",
    )
    ledger_body = {
        key: ledger[key] for key in ledger if key != "attempt_ledger_sha256"
    }
    attempts = tuple(
        _mapping(row, label=f"attempt[{index}]")
        for index, row in enumerate(
            _sequence(ledger["attempts"], label="attempts")
        )
    )
    if (
        ledger["schema"] != ATTEMPT_LEDGER_SCHEMA
        or ledger["source_binding_sha256"]
        != raw_inputs.source_binding_sha256
        or ledger["registered_law_sha256"]
        != raw_inputs.registered_law_sha256
        or ledger["visit_schedule_sha256"]
        != raw_inputs.visit_schedule_sha256
        or ledger["parameter_set_order"] != list(PARAMETER_SET_ORDER)
        or ledger["attempt_count"] != 7_000
        or len(attempts) != 7_000
        or ledger["outcome_columns_read"] != []
        or ledger["uses_realized_outcomes"] is not False
        or ledger["attempt_ledger_sha256"] != _canonical_sha256(ledger_body)
        or ledger["attempt_ledger_sha256"] != draft.attempt_ledger_sha256
        or sha256(draft.attempt_ledger_payload).hexdigest()
        != sha256(_canonical_json_bytes(ledger)).hexdigest()
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "attempt ledger authority differs"
        )
    attempt_keys = frozenset({
        "variant_ordinal",
        "parameter_set_id",
        "visit_ordinal",
        "world",
        "construction_serial",
        "status",
        "roster",
        "primary_optimum_micro",
        "secondary_rank_sum",
        "lexicographic_radix",
        "combined_optimum",
        "solver_proof",
        "detail",
    })
    proof_keys = frozenset({
        "schema",
        "solver",
        "solver_authority_sha256",
        "total_deadline_seconds",
        "total_elapsed_microseconds",
        "timeout_law",
        "stages",
        "proof_sha256",
    })
    solver_authority_sha = _canonical_sha256(raw_inputs.solver_authority)
    for ordinal, attempt in enumerate(attempts):
        _exact_keys(attempt, attempt_keys, label=f"attempt[{ordinal}]")
        variant = ordinal // MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
        visit = ordinal % MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
        observed_variant = _strict_int(
            attempt["variant_ordinal"],
            label=f"attempt[{ordinal}] variant",
            minimum=0,
        )
        observed_visit = _strict_int(
            attempt["visit_ordinal"],
            label=f"attempt[{ordinal}] visit",
            minimum=0,
        )
        observed_serial = _strict_int(
            attempt["construction_serial"],
            label=f"attempt[{ordinal}] construction serial",
            minimum=0,
        )
        world = raw_inputs.visit_schedule[visit]
        world_row = _mapping(
            attempt["world"], label=f"attempt[{ordinal}] world"
        )
        _exact_keys(
            world_row,
            frozenset({"block", "index"}),
            label=f"attempt[{ordinal}] world",
        )
        observed_world_index = _strict_int(
            world_row["index"],
            label=f"attempt[{ordinal}] world index",
            minimum=0,
        )
        proof = _mapping(
            attempt["solver_proof"], label=f"attempt[{ordinal}] proof"
        )
        _exact_keys(proof, proof_keys, label=f"attempt[{ordinal}] proof")
        proof_body = {
            key: proof[key] for key in proof if key != "proof_sha256"
        }
        stages = tuple(
            _mapping(row, label=f"attempt[{ordinal}] stage")
            for row in _sequence(proof["stages"], label="proof stages")
        )
        roster = _audit_dk_classic(
            raw_inputs.players,
            _sequence(attempt["roster"], label="attempt roster"),
        )
        profile = raw_inputs.profiles[variant]
        _audit_profile(
            raw_inputs.players,
            roster,
            _mapping(profile["parameter_values"], label="profile values"),
        )
        flat = (
            rw.WORLD_BLOCKS.index(world.block) * rw.WORLDS_PER_BLOCK
            + world.index
        )
        objective = _micro_objective(
            raw_inputs.player_draws, world_column=flat
        )
        index = {
            player.player_id: row
            for row, player in enumerate(raw_inputs.players)
        }
        primary = sum(objective[index[player_id]] for player_id in roster)
        rank_by_id = {
            player_id: rank + 1
            for rank, player_id in enumerate(sorted(index))
        }
        rank_sum = sum(rank_by_id[player_id] for player_id in roster)
        radix = rw.ROSTER_SIZE * (
            len(raw_inputs.players) - rw.ROSTER_SIZE
        ) + 1
        observed_primary = _strict_int(
            attempt["primary_optimum_micro"],
            label=f"attempt[{ordinal}] primary optimum",
        )
        observed_secondary = _strict_int(
            attempt["secondary_rank_sum"],
            label=f"attempt[{ordinal}] rank sum",
            minimum=0,
        )
        observed_radix = _strict_int(
            attempt["lexicographic_radix"],
            label=f"attempt[{ordinal}] radix",
            minimum=1,
        )
        observed_combined = _strict_int(
            attempt["combined_optimum"],
            label=f"attempt[{ordinal}] combined optimum",
        )
        observed_deadline = _strict_int(
            proof["total_deadline_seconds"],
            label=f"attempt[{ordinal}] deadline",
            minimum=1,
        )
        observed_proof_elapsed = _strict_int(
            proof["total_elapsed_microseconds"],
            label=f"attempt[{ordinal}] total elapsed",
            minimum=0,
        )
        if (
            observed_variant != variant
            or attempt["parameter_set_id"] != PARAMETER_SET_ORDER[variant]
            or observed_visit != visit
            or world_row["block"] != world.block
            or observed_world_index != world.index
            or observed_serial != ordinal
            or attempt["status"] != "optimal"
            or observed_primary != primary
            or observed_secondary != rank_sum
            or observed_radix != radix
            or observed_combined != primary * radix - rank_sum
            or attempt["detail"] != "unique lexicographic combined optimum"
            or proof["schema"] != SOLVER_PROOF_SCHEMA
            or proof["solver"] != raw_inputs.solver_authority
            or proof["solver_authority_sha256"] != solver_authority_sha
            or observed_deadline != SOLVER_TIMEOUT_SECONDS
            or observed_proof_elapsed
            >= SOLVER_TIMEOUT_SECONDS * 1_000_000
            or proof["timeout_law"] != SOLVER_TIMEOUT_LAW
            or len(stages) != 2
            or [stage.get("stage") for stage in stages] != [
                "lexicographic_combined_optimum",
                "combined_optimum_collision",
            ]
            or [stage.get("status") for stage in stages]
            != ["optimal", "infeasible"]
            or proof["proof_sha256"] != _canonical_sha256(proof_body)
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"attempt[{ordinal}] authority does not reconstruct"
            )
    return attempts


def _bounded_decompress(
    compressed: bytes, *, expected_bytes: int, label: str
) -> bytes:
    if type(compressed) is not bytes or not compressed:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} compressed payload is empty"
        )
    decompressor = zlib.decompressobj()
    try:
        raw = decompressor.decompress(compressed, expected_bytes + 1)
        if len(raw) <= expected_bytes:
            raw += decompressor.flush(expected_bytes + 1 - len(raw))
    except zlib.error as exc:
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} decompression failed"
        ) from exc
    if (
        len(raw) != expected_bytes
        or not decompressor.eof
        or decompressor.unused_data
        or decompressor.unconsumed_tail
        or zlib.compress(raw, level=9) != compressed
    ):
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} is noncanonical, truncated, or trailing"
        )
    return raw


def _verify_solver_evidence_shards(
    *,
    raw_inputs: _VerifiedRawInputs,
    draft: _RawDraftAuthorities,
    attempts: Sequence[Mapping[str, object]],
    object_reader: GenerationPinnedObjectReader,
) -> tuple[tuple[dict[str, object], ...], int]:
    shards = tuple(draft.solver_evidence_shards)
    if (
        len(shards) != EVIDENCE_SHARDS_PER_TASK
        or any(type(shard) is not _RawSolverEvidenceShard for shard in shards)
        or tuple(shard.global_shard_ordinal for shard in shards)
        != tuple(range(EVIDENCE_SHARDS_PER_TASK))
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "solver evidence shard object coverage differs"
        )
    shard_roots: list[dict[str, object]] = []
    total_stage_count = 0
    index_keys = frozenset({
        "schema",
        "codec",
        "zlib_runtime_version",
        "compressed_object_basename",
        "index_object_basename",
        "global_shard_ordinal",
        "variant_ordinal",
        "variant_shard_ordinal",
        "visit_start",
        "visit_stop",
        "attempt_count",
        "stage_count",
        "member_count",
        "compressed_sha256",
        "compressed_bytes",
        "uncompressed_sha256",
        "uncompressed_bytes",
        "maximum_uncompressed_bytes",
        "attempt_roots",
        "stages",
        "members",
        "evidence_index_sha256",
    })
    member_keys = frozenset({
        "member_ordinal",
        "stage_ordinal",
        "member_type",
        "offset",
        "length",
        "sha256",
    })
    stage_keys = frozenset({
        "stage_ordinal",
        "local_attempt_ordinal",
        "global_attempt_ordinal",
        "local_stage_ordinal",
        "stage_receipt_sha256",
        "stage_receipt",
        "log_member_ordinal",
        "solution_member_ordinal",
    })
    attempt_root_keys = frozenset({
        "local_attempt_ordinal",
        "visit_ordinal",
        "solver_proof_sha256",
        "stage_receipt_sha256",
    })
    for global_shard, shard in enumerate(shards):
        descriptor_global = _strict_int(
            shard.global_shard_ordinal,
            label="descriptor global shard ordinal",
            minimum=0,
        )
        compressed_name = f"shard-{global_shard:03d}.zlib"
        index_name = f"shard-{global_shard:03d}.index.json"
        expected_compressed_uri = (
            f"{draft.evidence_output_prefix}solver-evidence/"
            f"{compressed_name}"
        )
        expected_index_uri = (
            f"{draft.evidence_output_prefix}solver-evidence/{index_name}"
        )
        compressed_identity = _normalize_object_identity(
            shard.compressed_object_identity,
            label=f"evidence shard[{global_shard}] compressed object",
        )
        index_identity = _normalize_object_identity(
            shard.index_object_identity,
            label=f"evidence shard[{global_shard}] index object",
        )
        if (
            compressed_identity["uri"] != expected_compressed_uri
            or index_identity["uri"] != expected_index_uri
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"evidence shard[{global_shard}] durable URI differs"
            )
        compressed, _ = _read_generation_pinned_object(
            object_reader,
            compressed_identity,
            maximum_bytes=MAX_SHARD_SOLVER_EVIDENCE_COMPRESSED_BYTES,
            label=f"evidence shard[{global_shard}] compressed object",
        )
        index_raw, _ = _read_generation_pinned_object(
            object_reader,
            index_identity,
            maximum_bytes=MAX_SHARD_SOLVER_EVIDENCE_INDEX_BYTES,
            label=f"evidence shard[{global_shard}] index object",
        )
        index = _mapping(
            _parse_canonical_json_bytes(
                index_raw,
                label=f"evidence shard[{global_shard}] index",
            ),
            label=f"evidence shard[{global_shard}] index",
        )
        _exact_keys(
            index, index_keys, label=f"evidence shard[{global_shard}] index"
        )
        body = {
            key: index[key]
            for key in index if key != "evidence_index_sha256"
        }
        variant = global_shard // EVIDENCE_SHARDS_PER_VARIANT
        variant_shard = global_shard % EVIDENCE_SHARDS_PER_VARIANT
        visit_start = variant_shard * EVIDENCE_SHARD_VISITS
        visit_stop = visit_start + EVIDENCE_SHARD_VISITS
        expected_uncompressed = _strict_int(
            index["uncompressed_bytes"],
            label="shard uncompressed bytes",
            minimum=1,
        )
        observed_global = _strict_int(
            index["global_shard_ordinal"],
            label="shard global ordinal",
            minimum=0,
        )
        observed_variant = _strict_int(
            index["variant_ordinal"], label="shard variant", minimum=0
        )
        observed_variant_shard = _strict_int(
            index["variant_shard_ordinal"],
            label="shard variant-shard ordinal",
            minimum=0,
        )
        observed_visit_start = _strict_int(
            index["visit_start"], label="shard visit start", minimum=0
        )
        observed_visit_stop = _strict_int(
            index["visit_stop"], label="shard visit stop", minimum=1
        )
        observed_attempt_count = _strict_int(
            index["attempt_count"], label="shard attempt count", minimum=1
        )
        observed_stage_count = _strict_int(
            index["stage_count"], label="shard stage count", minimum=1
        )
        observed_member_count = _strict_int(
            index["member_count"], label="shard member count", minimum=1
        )
        observed_compressed_bytes = _strict_int(
            index["compressed_bytes"],
            label="shard compressed bytes",
            minimum=1,
        )
        observed_maximum = _strict_int(
            index["maximum_uncompressed_bytes"],
            label="shard maximum uncompressed bytes",
            minimum=1,
        )
        if (
            index["schema"] != SHARD_INDEX_SCHEMA
            or index["codec"] != EVIDENCE_PACK_CODEC
            or index["zlib_runtime_version"] != zlib.ZLIB_VERSION
            or index["compressed_object_basename"] != compressed_name
            or index["index_object_basename"] != index_name
            or observed_global != global_shard
            or observed_variant != variant
            or observed_variant_shard != variant_shard
            or observed_visit_start != visit_start
            or observed_visit_stop != visit_stop
            or observed_attempt_count != EVIDENCE_SHARD_VISITS
            or observed_stage_count != 2 * EVIDENCE_SHARD_VISITS
            or observed_member_count != 4 * EVIDENCE_SHARD_VISITS
            or index["compressed_sha256"] != sha256(compressed).hexdigest()
            or observed_compressed_bytes != len(compressed)
            or observed_maximum
            != MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES
            or expected_uncompressed
            > MAX_SHARD_SOLVER_EVIDENCE_UNCOMPRESSED_BYTES
            or index["evidence_index_sha256"] != _canonical_sha256(body)
            or index["evidence_index_sha256"] != shard.index_sha256
            or sha256(index_raw).hexdigest() != shard.index_object_sha256
            or descriptor_global != global_shard
            or compressed_identity["sha256"] != index["compressed_sha256"]
            or compressed_identity["bytes"] != index["compressed_bytes"]
            or index_identity["sha256"] != sha256(index_raw).hexdigest()
            or index_identity["bytes"] != len(index_raw)
            or shard.index_object_sha256 != index_identity["sha256"]
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"evidence shard[{global_shard}] header differs"
            )
        uncompressed = _bounded_decompress(
            compressed,
            expected_bytes=expected_uncompressed,
            label=f"evidence shard[{global_shard}]",
        )
        if sha256(uncompressed).hexdigest() != index["uncompressed_sha256"]:
            raise CorpusLegalFeasibilityVerificationError(
                f"evidence shard[{global_shard}] raw hash differs"
            )
        raw_members: list[bytes] = []
        members = tuple(
            _mapping(row, label="evidence member")
            for row in _sequence(index["members"], label="evidence members")
        )
        if len(members) != 4 * EVIDENCE_SHARD_VISITS:
            raise CorpusLegalFeasibilityVerificationError(
                "evidence member count differs"
            )
        offset = 0
        for ordinal, member in enumerate(members):
            _exact_keys(member, member_keys, label=f"evidence member[{ordinal}]")
            member_ordinal = _strict_int(
                member["member_ordinal"],
                label="member ordinal",
                minimum=0,
            )
            member_stage = _strict_int(
                member["stage_ordinal"],
                label="member stage ordinal",
                minimum=0,
            )
            member_offset = _strict_int(
                member["offset"], label="member offset", minimum=0
            )
            length = _strict_int(
                member["length"], label="member length", minimum=0
            )
            if (
                member_ordinal != ordinal
                or member_stage != ordinal // 2
                or member["member_type"]
                != ("cbc_log_utf8" if ordinal % 2 == 0 else "cbc_solution_utf8")
                or member_offset != offset
                or offset + length > len(uncompressed)
            ):
                raise CorpusLegalFeasibilityVerificationError(
                    "evidence member order/offset differs"
                )
            raw_member = uncompressed[offset:offset + length]
            if member["sha256"] != sha256(raw_member).hexdigest():
                raise CorpusLegalFeasibilityVerificationError(
                    "evidence member hash differs"
                )
            raw_members.append(raw_member)
            offset += length
        if offset != len(uncompressed):
            raise CorpusLegalFeasibilityVerificationError(
                "evidence members leave gaps or trailing bytes"
            )
        stage_rows = tuple(
            _mapping(row, label="evidence stage")
            for row in _sequence(index["stages"], label="evidence stages")
        )
        attempt_roots = tuple(
            _mapping(row, label="evidence attempt root")
            for row in _sequence(
                index["attempt_roots"], label="evidence attempt roots"
            )
        )
        if (
            len(stage_rows) != 2 * EVIDENCE_SHARD_VISITS
            or len(attempt_roots) != EVIDENCE_SHARD_VISITS
        ):
            raise CorpusLegalFeasibilityVerificationError(
                "evidence stage/attempt-root cardinality differs"
            )
        for local_attempt in range(EVIDENCE_SHARD_VISITS):
            visit = visit_start + local_attempt
            global_attempt = (
                variant * MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION + visit
            )
            attempt = attempts[global_attempt]
            proof = _mapping(attempt["solver_proof"], label="attempt proof")
            attempt_root = attempt_roots[local_attempt]
            _exact_keys(
                attempt_root,
                attempt_root_keys,
                label=f"attempt root[{local_attempt}]",
            )
            root_local_attempt = _strict_int(
                attempt_root["local_attempt_ordinal"],
                label="attempt-root local ordinal",
                minimum=0,
            )
            root_visit = _strict_int(
                attempt_root["visit_ordinal"],
                label="attempt-root visit ordinal",
                minimum=0,
            )
            local_stages = stage_rows[
                2 * local_attempt:2 * local_attempt + 2
            ]
            stage_hashes: list[str] = []
            for local_stage, stage in enumerate(local_stages):
                stage_ordinal = 2 * local_attempt + local_stage
                _exact_keys(
                    stage, stage_keys, label=f"stage[{stage_ordinal}]"
                )
                receipt = _mapping(
                    stage["stage_receipt"], label="stage receipt"
                )
                receipt_sha = _canonical_sha256(receipt)
                observed_stage = _strict_int(
                    stage["stage_ordinal"],
                    label="evidence stage ordinal",
                    minimum=0,
                )
                observed_local_attempt = _strict_int(
                    stage["local_attempt_ordinal"],
                    label="evidence stage local attempt",
                    minimum=0,
                )
                observed_global_attempt = _strict_int(
                    stage["global_attempt_ordinal"],
                    label="evidence stage global attempt",
                    minimum=0,
                )
                observed_local_stage = _strict_int(
                    stage["local_stage_ordinal"],
                    label="evidence local stage ordinal",
                    minimum=0,
                )
                observed_log_member = _strict_int(
                    stage["log_member_ordinal"],
                    label="evidence log-member ordinal",
                    minimum=0,
                )
                observed_solution_member = _strict_int(
                    stage["solution_member_ordinal"],
                    label="evidence solution-member ordinal",
                    minimum=0,
                )
                if (
                    observed_stage != stage_ordinal
                    or observed_local_attempt != local_attempt
                    or observed_global_attempt != global_attempt
                    or observed_local_stage != local_stage
                    or stage["stage_receipt_sha256"] != receipt_sha
                    or observed_log_member != 2 * stage_ordinal
                    or observed_solution_member
                    != 2 * stage_ordinal + 1
                ):
                    raise CorpusLegalFeasibilityVerificationError(
                        "evidence stage root/cross-link differs"
                    )
                stage_hashes.append(receipt_sha)
            if (
                root_local_attempt != local_attempt
                or root_visit != visit
                or attempt_root["solver_proof_sha256"] != proof["proof_sha256"]
                or attempt_root["stage_receipt_sha256"] != stage_hashes
            ):
                raise CorpusLegalFeasibilityVerificationError(
                    "evidence attempt root differs"
                )
            member_slice = raw_members[
                4 * local_attempt:4 * local_attempt + 4
            ]
            _verify_attempt_stage_evidence(
                raw_inputs=raw_inputs,
                attempt=attempt,
                proof=proof,
                stage_rows=local_stages,
                raw_members=member_slice,
            )
        shard_root = _canonical_sha256({
            "global_shard_ordinal": global_shard,
            "compressed_sha256": index["compressed_sha256"],
            "compressed_bytes": index["compressed_bytes"],
            "index_sha256": index["evidence_index_sha256"],
            "index_object_sha256": sha256(index_raw).hexdigest(),
            "index_bytes": len(index_raw),
            "attempt_roots_sha256": _canonical_sha256(list(attempt_roots)),
        })
        if shard.shard_root_sha256 != shard_root:
            raise CorpusLegalFeasibilityVerificationError(
                "evidence shard root differs"
            )
        shard_roots.append({
            "global_shard_ordinal": global_shard,
            "variant_ordinal": variant,
            "variant_shard_ordinal": variant_shard,
            "visit_start": visit_start,
            "visit_stop": visit_stop,
            "compressed_sha256": index["compressed_sha256"],
            "compressed_bytes": index["compressed_bytes"],
            "uncompressed_sha256": index["uncompressed_sha256"],
            "uncompressed_bytes": index["uncompressed_bytes"],
            "index_sha256": index["evidence_index_sha256"],
            "index_object_sha256": sha256(index_raw).hexdigest(),
            "index_bytes": len(index_raw),
            "compressed_object_basename": compressed_name,
            "index_object_basename": index_name,
            "shard_root_sha256": shard_root,
        })
        total_stage_count += len(stage_rows)
    return tuple(shard_roots), total_stage_count


def _parse_self_hashed_payload(
    raw: bytes,
    *,
    label: str,
    hash_field: str,
) -> Mapping[str, object]:
    item = _mapping(
        _parse_canonical_json_bytes(raw, label=label), label=label
    )
    retained = _strict_sha(item.get(hash_field), label=f"{label} hash")
    body = {key: item[key] for key in item if key != hash_field}
    if retained != _canonical_sha256(body):
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} self-hash differs"
        )
    return item


def _verify_content_task_root(
    draft: _RawDraftAuthorities,
    shard_rows: Sequence[Mapping[str, object]],
) -> str:
    rows = [dict(row) for row in shard_rows]
    body: dict[str, object] = {
        "schema": CONTENT_TASK_ROOT_SCHEMA,
        "shard_visit_count": EVIDENCE_SHARD_VISITS,
        "shards_per_variant": EVIDENCE_SHARDS_PER_VARIANT,
        "shard_count": EVIDENCE_SHARDS_PER_TASK,
        "shards": rows,
    }
    task_root_sha = _canonical_sha256(body)
    expected = _canonical_json_bytes({
        **body, "task_evidence_root_sha256": task_root_sha,
    })
    parsed = _parse_self_hashed_payload(
        draft.solver_evidence_task_root_payload,
        label="content task evidence root",
        hash_field="task_evidence_root_sha256",
    )
    _exact_keys(
        parsed,
        frozenset({
            "schema",
            "shard_visit_count",
            "shards_per_variant",
            "shard_count",
            "shards",
            "task_evidence_root_sha256",
        }),
        label="content task evidence root",
    )
    if (
        draft.solver_evidence_task_root_payload != expected
        or draft.solver_evidence_task_root_sha256 != task_root_sha
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "content task evidence root does not reconstruct"
        )
    return task_root_sha


def _verify_matrix_authority(
    *,
    raw_inputs: _VerifiedRawInputs,
    draft: _RawDraftAuthorities,
    attempts: Sequence[Mapping[str, object]],
    shard_rows: Sequence[Mapping[str, object]],
    task_root_sha256: str,
) -> str:
    objective_rows: list[dict[str, object]] = []
    for world in raw_inputs.visit_schedule:
        flat = (
            rw.WORLD_BLOCKS.index(world.block) * rw.WORLDS_PER_BLOCK
            + world.index
        )
        objective_rows.append({
            "block": world.block,
            "index": world.index,
            "objective_micro_sha256": _canonical_sha256(list(
                _micro_objective(raw_inputs.player_draws, world_column=flat)
            )),
        })
    runtime_hashes = [
        sha256(raw).hexdigest() for raw in raw_inputs.runtime_policy_payloads
    ]
    body: dict[str, object] = {
        "schema": MATRIX_AUTHORITY_SCHEMA,
        "slate": {
            "season": raw_inputs.task["season"],
            "week": raw_inputs.task["week"],
            "slate_id": raw_inputs.task["slate_id"],
        },
        "source_binding_sha256": raw_inputs.source_binding_sha256,
        "registered_law_sha256": raw_inputs.registered_law_sha256,
        "common_law_sha256": raw_inputs.manifest["common_law_sha256"],
        "artifact_source_authority_completion_object_sha256": (
            raw_inputs.artifact_source_authority_completion_object_sha256
        ),
        "artifact_source_authority_completion_sha256": (
            raw_inputs.artifact_source_authority_completion_sha256
        ),
        "artifact_source_authority_task_sha256": (
            raw_inputs.artifact_source_authority_task_sha256
        ),
        "code_source_object_sha256": (
            raw_inputs.code_source_object_sha256
        ),
        "code_source_body_sha256": raw_inputs.code_source_body_sha256,
        "immutable_image_sha256": raw_inputs.immutable_image_sha256,
        "runtime_image_terminal_verification_required": (
            raw_inputs.runtime_image_terminal_verification_required
        ),
        "world_schedule_object_sha256": raw_inputs.manifest["common_law"][
            "world_schedule"
        ]["sha256"],
        "visit_schedule": [
            {"block": world.block, "index": world.index}
            for world in raw_inputs.visit_schedule
        ],
        "visit_schedule_sha256": raw_inputs.visit_schedule_sha256,
        "objective_rows": objective_rows,
        "objective_rows_sha256": _canonical_sha256(objective_rows),
        "registered_dose": {
            "parameter_set_count": len(PARAMETER_SET_ORDER),
            "visits_per_block": VISITS_PER_BLOCK,
            "source_worlds_per_block": WORLDS_PER_BLOCK,
            "visits_per_parameter_set": (
                MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
            ),
            "matrix_cell_count": len(attempts),
            "selected_entry_count": ENTRY_COUNT,
            "solver_total_deadline_seconds_per_cell": SOLVER_TIMEOUT_SECONDS,
        },
        "fresh_model_construction_serials_sha256": _canonical_sha256(
            list(range(len(attempts)))
        ),
        "runtime_policy_sha256_by_parameter_set": [{
            "parameter_set_id": parameter_set_id,
            "runtime_policy_sha256": runtime_hash,
        } for parameter_set_id, runtime_hash in zip(
            PARAMETER_SET_ORDER, runtime_hashes, strict=True
        )],
        "attempt_ledger_sha256": draft.attempt_ledger_sha256,
        "solver_evidence": {
            "codec": EVIDENCE_PACK_CODEC,
            "shard_visit_count": EVIDENCE_SHARD_VISITS,
            "shard_count": EVIDENCE_SHARDS_PER_TASK,
            "task_evidence_root_sha256": task_root_sha256,
            "shard_rows_sha256": _canonical_sha256([
                dict(row) for row in shard_rows
            ]),
        },
        "all_cells_attempted": len(attempts) == 7_000,
        "all_cells_optimal": all(
            attempt["status"] == "optimal" for attempt in attempts
        ),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
    }
    matrix_sha = _canonical_sha256(body)
    expected = _canonical_json_bytes({
        **body, "matrix_authority_sha256": matrix_sha,
    })
    parsed = _parse_self_hashed_payload(
        draft.matrix_authority_payload,
        label="matrix authority",
        hash_field="matrix_authority_sha256",
    )
    if (
        parsed.get("schema") != MATRIX_AUTHORITY_SCHEMA
        or draft.matrix_authority_payload != expected
        or draft.matrix_authority_sha256 != matrix_sha
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "matrix authority does not reconstruct"
        )
    return matrix_sha


def _task_source_projection(raw_inputs: _VerifiedRawInputs) -> dict[str, object]:
    return {
        "binding_sha256": raw_inputs.source_binding_sha256,
        "batch_manifest_sha256": raw_inputs.manifest[
            "batch_manifest_sha256"
        ],
        "task_index": raw_inputs.request["task_index"],
        "task_sha256": raw_inputs.task["task_sha256"],
        "artifact_source_authority_completion_object_sha256": (
            raw_inputs.artifact_source_authority_completion_object_sha256
        ),
        "artifact_source_authority_completion_sha256": (
            raw_inputs.artifact_source_authority_completion_sha256
        ),
        "artifact_source_authority_task_sha256": (
            raw_inputs.artifact_source_authority_task_sha256
        ),
        "later_source_freeze_manifest_sha256": (
            raw_inputs.source_freeze_sha256
        ),
        "world_artifact_receipt_set_sha256": raw_inputs.task[
            "world_artifact_receipt_set_sha256"
        ],
    }


def _runtime_binding_projection(
    raw: bytes,
    *,
    expected_profile: Mapping[str, object],
    label: str,
) -> dict[str, object]:
    item = _mapping(
        _parse_canonical_json_bytes(raw, label=label), label=label
    )
    if (
        item.get("schema") != RUNTIME_POLICY_SCHEMA
        or item.get("parameter_set") != expected_profile
        or item.get("outcome_columns_read") != []
        or item.get("uses_realized_outcomes") is not False
        or item.get("historical_scoring_licensed") is not False
        or item.get("production_change_licensed") is not False
    ):
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} authority differs"
        )
    return {
        "runtime_policy_sha256": sha256(raw).hexdigest(),
        "inventory_sha256": item["inventory_sha256"],
        "source_set_id": item["source_set_id"],
        "source_set_sha256": item["source_set_sha256"],
        "rule_universe_sha256": item["rule_universe_sha256"],
        "rule_count": item["rule_count"],
        "classified_input_projection_sha256": item[
            "classified_input_projection_sha256"
        ],
        "classified_input_runtime_proof_sha256": item[
            "classified_input_runtime_proof_sha256"
        ],
        "experimental_rule_set_sha256": item[
            "experimental_rule_set_sha256"
        ],
        "dk_classic_feasibility_only": item[
            "dk_classic_feasibility_only"
        ],
    }


def _verify_variant_results(
    *,
    raw_inputs: _VerifiedRawInputs,
    draft: _RawDraftAuthorities,
    attempts: Sequence[Mapping[str, object]],
    matrix_authority_sha256: str,
    task_root_sha256: str,
) -> tuple[
    tuple[str, ...],
    tuple[str, ...],
    tuple[str, ...],
    tuple[Mapping[str, object], ...],
    tuple[Mapping[str, object], ...],
    tuple[Mapping[str, object], ...],
    int,
    int,
]:
    payloads = tuple(draft.variant_result_payloads)
    if len(payloads) != len(PARAMETER_SET_ORDER):
        raise CorpusLegalFeasibilityVerificationError(
            "variant-result payload count differs"
        )
    result_hashes: list[str] = []
    candidate_hashes: list[str] = []
    selected_hashes: list[str] = []
    outside_law_summaries: list[Mapping[str, object]] = []
    endpoint_summaries: list[Mapping[str, object]] = []
    coverage_summaries: list[Mapping[str, object]] = []
    total_unique = 0
    total_selected = 0
    for variant, (
        parameter_set_id,
        profile,
        runtime_raw,
        retained_raw,
    ) in enumerate(zip(
        PARAMETER_SET_ORDER,
        raw_inputs.profiles,
        raw_inputs.runtime_policy_payloads,
        payloads,
        strict=True,
    )):
        start = variant * MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
        stop = start + MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
        attempt_rows = tuple(attempts[start:stop])
        if len(attempt_rows) != MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION:
            raise CorpusLegalFeasibilityVerificationError(
                f"variant[{variant}] attempt coverage differs"
            )
        visit_rosters = tuple(
            _audit_dk_classic(
                raw_inputs.players,
                _sequence(row["roster"], label="variant visit roster"),
            )
            for row in attempt_rows
        )
        values = _mapping(
            profile["parameter_values"], label="profile parameter values"
        )
        for roster in visit_rosters:
            _audit_profile(raw_inputs.players, roster, values)
        unique, first_indices = _first_occurrence_unique(visit_rosters)
        for roster in unique:
            _audit_profile(raw_inputs.players, roster, values)
        outside_law_summary = _outside_law_nonvacuity_summary(
            raw_inputs.players,
            unique,
            variant_ordinal=variant,
            parameter_set_id=parameter_set_id,
        )
        scores = _cross_score_full_union(
            raw_inputs.players, raw_inputs.player_draws, unique
        )
        selector = _select_exact80(scores)
        selected_indices = tuple(
            _strict_int(value, label="selector index", minimum=0)
            for value in _sequence(
                selector["selected_indices"], label="selector indices"
            )
        )
        selected_rosters = tuple(unique[index] for index in selected_indices)
        selected_scores = np.ascontiguousarray(
            scores[np.asarray(selected_indices, dtype=np.int64)],
            dtype=np.float64,
        )
        selected_scores.flags.writeable = False
        endpoint_summary, coverage_summary = (
            _score_free_endpoint_and_coverage(
                scores,
                selected_scores,
                unique,
                selected_rosters,
                parameter_set_id=parameter_set_id,
            )
        )
        candidate_sha = _strict_sha(
            coverage_summary["candidate_score_sha256"],
            label=f"score coverage[{variant}] candidate SHA",
        )
        selected_sha = _strict_sha(
            coverage_summary["selected_score_sha256"],
            label=f"score coverage[{variant}] selected SHA",
        )
        census = {
            "unique_candidate_counts": _violation_census(
                raw_inputs.players, unique
            ),
            "visit_counts": _violation_census(
                raw_inputs.players, visit_rosters
            ),
            "selected_counts": _violation_census(
                raw_inputs.players, selected_rosters
            ),
        }
        runtime_projection = _runtime_binding_projection(
            runtime_raw,
            expected_profile=profile,
            label=f"runtime policy[{variant}]",
        )
        body: dict[str, object] = {
            "schema": VARIANT_RESULT_SCHEMA,
            "slate": {
                "season": raw_inputs.task["season"],
                "week": raw_inputs.task["week"],
                "slate_id": raw_inputs.task["slate_id"],
            },
            "later_source_freeze_manifest_sha256": (
                raw_inputs.source_freeze_sha256
            ),
            "artifact_sha256_by_block": dict(
                raw_inputs.artifact_sha256_by_block
            ),
            "task_source_binding": _task_source_projection(raw_inputs),
            "visit_schedule_sha256": raw_inputs.visit_schedule_sha256,
            "attempt_ledger_sha256": draft.attempt_ledger_sha256,
            "variant_attempt_rows_sha256": _canonical_sha256(
                [dict(row) for row in attempt_rows]
            ),
            "matrix_authority_sha256": matrix_authority_sha256,
            "solver_evidence_task_root_sha256": task_root_sha256,
            "profile": dict(profile),
            "runtime_effective_policy": runtime_projection,
            "coverage": {
                "scheduled_visits": len(raw_inputs.visit_schedule),
                "attempted_visits": len(attempt_rows),
                "optimal_visits": sum(
                    row["status"] == "optimal" for row in attempt_rows
                ),
                "unique_candidates": len(unique),
                "selected_entries": len(selected_rosters),
            },
            "visit_rosters": [list(roster) for roster in visit_rosters],
            "unique_rosters": [list(roster) for roster in unique],
            "first_occurrence_visit_indices": list(first_indices),
            "candidate_score_sha256": candidate_sha,
            "selector": selector,
            "selected_rosters": [list(roster) for roster in selected_rosters],
            "selected_score_sha256": selected_sha,
            "house_rule_violation_census": census,
            "outcome_columns_read": [],
            "uses_realized_outcomes": False,
            "historical_scoring_licensed": False,
            "production_change_licensed": False,
        }
        result_sha = _canonical_sha256(body)
        expected_raw = _canonical_json_bytes({
            **body, "result_sha256": result_sha,
        })
        parsed = _parse_self_hashed_payload(
            retained_raw,
            label=f"variant result[{variant}]",
            hash_field="result_sha256",
        )
        if (
            parsed.get("schema") != VARIANT_RESULT_SCHEMA
            or retained_raw != expected_raw
            or parsed["profile"]["ordinal"] != variant
            or parsed["profile"]["parameter_set_id"] != parameter_set_id
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"variant result[{variant}] does not reconstruct"
            )
        result_hashes.append(result_sha)
        candidate_hashes.append(candidate_sha)
        selected_hashes.append(selected_sha)
        outside_law_summaries.append(outside_law_summary)
        endpoint_summaries.append(endpoint_summary)
        coverage_summaries.append(coverage_summary)
        total_unique += len(unique)
        total_selected += len(selected_rosters)
    return (
        tuple(result_hashes),
        tuple(candidate_hashes),
        tuple(selected_hashes),
        tuple(outside_law_summaries),
        tuple(endpoint_summaries),
        tuple(coverage_summaries),
        total_unique,
        total_selected,
    )


def _verify_batch_result(
    *,
    raw_inputs: _VerifiedRawInputs,
    draft: _RawDraftAuthorities,
    variant_result_sha256s: Sequence[str],
    matrix_authority_sha256: str,
    task_root_sha256: str,
) -> str:
    result_hashes = tuple(variant_result_sha256s)
    if len(result_hashes) != len(PARAMETER_SET_ORDER):
        raise CorpusLegalFeasibilityVerificationError(
            "batch variant-result coverage differs"
        )
    runtime_hashes = tuple(
        sha256(raw).hexdigest() for raw in raw_inputs.runtime_policy_payloads
    )
    body: dict[str, object] = {
        "schema": BATCH_RESULT_SCHEMA,
        "slate": {
            "season": raw_inputs.task["season"],
            "week": raw_inputs.task["week"],
            "slate_id": raw_inputs.task["slate_id"],
        },
        "later_source_freeze_manifest_sha256": (
            raw_inputs.source_freeze_sha256
        ),
        "artifact_sha256_by_block": dict(
            raw_inputs.artifact_sha256_by_block
        ),
        "task_source_binding": _task_source_projection(raw_inputs),
        "source_columns": list(SOURCE_COLUMN_ORDER),
        "visit_schedule": [
            {"block": world.block, "index": world.index}
            for world in raw_inputs.visit_schedule
        ],
        "visit_schedule_sha256": raw_inputs.visit_schedule_sha256,
        "attempt_ledger_sha256": draft.attempt_ledger_sha256,
        "matrix_authority_sha256": matrix_authority_sha256,
        "solver_evidence_task_root_sha256": task_root_sha256,
        "coverage": {
            "parameter_sets": len(PARAMETER_SET_ORDER),
            "visits_per_parameter_set": len(raw_inputs.visit_schedule),
            "matrix_cells": (
                len(PARAMETER_SET_ORDER)
                * MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION
            ),
            "all_cells_attempted": True,
            "all_cells_optimal": True,
            "exact_80_every_variant": True,
        },
        "variant_results": [{
            "ordinal": variant,
            "parameter_set_id": parameter_set_id,
            "parameter_set_sha256": raw_inputs.profiles[variant][
                "parameter_set_sha256"
            ],
            "runtime_policy_sha256": runtime_hashes[variant],
            "result_sha256": result_hashes[variant],
        } for variant, parameter_set_id in enumerate(PARAMETER_SET_ORDER)],
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    batch_sha = _canonical_sha256(body)
    expected = _canonical_json_bytes({
        **body, "result_sha256": batch_sha,
    })
    parsed = _parse_self_hashed_payload(
        draft.batch_result_payload,
        label="batch result",
        hash_field="result_sha256",
    )
    if (
        parsed.get("schema") != BATCH_RESULT_SCHEMA
        or draft.batch_result_payload != expected
        or draft.batch_result_sha256 != batch_sha
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "batch result does not reconstruct"
        )
    return batch_sha


def _verify_draft_envelope(
    *,
    raw_inputs: _VerifiedRawInputs,
    draft: _RawDraftAuthorities,
    variant_result_sha256s: Sequence[str],
    batch_result_sha256: str,
    task_root_sha256: str,
) -> str:
    runtime_hashes = [
        sha256(raw).hexdigest() for raw in raw_inputs.runtime_policy_payloads
    ]
    shard_hashes = [
        shard.shard_root_sha256 for shard in draft.solver_evidence_shards
    ]
    body: dict[str, object] = {
        "schema": DRAFT_AUTHORITY_BUNDLE_SCHEMA,
        "task_request_sha256": raw_inputs.request["task_request_sha256"],
        "batch_manifest_sha256": raw_inputs.manifest[
            "batch_manifest_sha256"
        ],
        "task_sha256": raw_inputs.task["task_sha256"],
        "source_binding_sha256": raw_inputs.source_binding_sha256,
        "registered_law_sha256": raw_inputs.registered_law_sha256,
        "artifact_source_authority_completion_object_sha256": (
            raw_inputs.artifact_source_authority_completion_object_sha256
        ),
        "artifact_source_authority_completion_sha256": (
            raw_inputs.artifact_source_authority_completion_sha256
        ),
        "artifact_source_authority_task_sha256": (
            raw_inputs.artifact_source_authority_task_sha256
        ),
        "code_source_object_sha256": (
            raw_inputs.code_source_object_sha256
        ),
        "code_source_body_sha256": raw_inputs.code_source_body_sha256,
        "immutable_image_sha256": raw_inputs.immutable_image_sha256,
        "runtime_image_terminal_verification_required": (
            raw_inputs.runtime_image_terminal_verification_required
        ),
        "runtime_policy_sha256": runtime_hashes,
        "attempt_ledger_sha256": draft.attempt_ledger_sha256,
        "matrix_authority_sha256": draft.matrix_authority_sha256,
        "solver_evidence": {
            "shard_count": EVIDENCE_SHARDS_PER_TASK,
            "task_evidence_root_sha256": task_root_sha256,
            "shard_root_sha256": shard_hashes,
        },
        "variant_result_sha256": list(variant_result_sha256s),
        "batch_result_sha256": batch_result_sha256,
        "evidence_output_prefix": raw_inputs.task["variant_output_prefix"],
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    draft_sha = _canonical_sha256(body)
    expected = _canonical_json_bytes({**body, "draft_sha256": draft_sha})
    parsed = _parse_self_hashed_payload(
        draft.canonical_draft_payload,
        label="draft authority bundle",
        hash_field="draft_sha256",
    )
    expected_output_prefix = _strict_string(
        raw_inputs.task["variant_output_prefix"],
        label="task variant output prefix",
    )
    if (
        parsed.get("schema") != DRAFT_AUTHORITY_BUNDLE_SCHEMA
        or draft.schema != DRAFT_AUTHORITY_BUNDLE_SCHEMA
        or draft.canonical_draft_payload != expected
        or draft.draft_sha256 != draft_sha
        or draft.source_binding_payload != raw_inputs.source_binding_payload
        or draft.source_binding_sha256 != raw_inputs.source_binding_sha256
        or draft.artifact_source_authority_completion_object_sha256
        != raw_inputs.artifact_source_authority_completion_object_sha256
        or draft.artifact_source_authority_completion_sha256
        != raw_inputs.artifact_source_authority_completion_sha256
        or draft.artifact_source_authority_task_sha256
        != raw_inputs.artifact_source_authority_task_sha256
        or draft.registered_law_payload != raw_inputs.registered_law_payload
        or draft.registered_law_sha256 != raw_inputs.registered_law_sha256
        or tuple(draft.runtime_policy_payloads)
        != raw_inputs.runtime_policy_payloads
        or draft.solver_evidence_task_root_sha256 != task_root_sha256
        or draft.batch_result_sha256 != batch_result_sha256
        or draft.evidence_output_prefix != expected_output_prefix
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "draft authority bundle does not reconstruct"
        )
    return draft_sha


def _verify_published_envelope(
    *,
    authority_bundle: _RawAuthorityBundle,
    draft_sha256: str,
    shard_rows: Sequence[Mapping[str, object]],
    task_root_sha256: str,
    batch_result_sha256: str,
) -> str:
    draft = authority_bundle.draft
    shards = tuple(draft.solver_evidence_shards)
    if len(shards) != EVIDENCE_SHARDS_PER_TASK:
        raise CorpusLegalFeasibilityVerificationError(
            "published shard identity coverage differs"
        )
    identities: list[dict[str, object]] = []
    published_rows: list[dict[str, object]] = []
    for ordinal, shard in enumerate(shards):
        if _strict_int(
            shard.global_shard_ordinal,
            label=f"published shard[{ordinal}] ordinal",
            minimum=0,
        ) != ordinal:
            raise CorpusLegalFeasibilityVerificationError(
                "published shard identity order differs"
            )
        compressed_identity = _normalize_object_identity(
            shard.compressed_object_identity,
            label=f"published compressed shard[{ordinal}]",
        )
        index_identity = _normalize_object_identity(
            shard.index_object_identity,
            label=f"published index shard[{ordinal}]",
        )
        if (
            compressed_identity["uri"]
            != (
                f"{draft.evidence_output_prefix}solver-evidence/"
                f"shard-{ordinal:03d}.zlib"
            )
            or index_identity["uri"]
            != (
                f"{draft.evidence_output_prefix}solver-evidence/"
                f"shard-{ordinal:03d}.index.json"
            )
            or index_identity["sha256"] != shard.index_object_sha256
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"published shard[{ordinal}] identity differs"
            )
        normalized = {
            "global_shard_ordinal": ordinal,
            "compressed_object_identity": compressed_identity,
            "index_object_identity": index_identity,
        }
        identities.append(normalized)
        published_rows.append({
            **normalized,
            "index_sha256": shard.index_sha256,
            "index_object_sha256": shard.index_object_sha256,
            "shard_root_sha256": shard.shard_root_sha256,
        })
    content_rows = [dict(row) for row in shard_rows]
    published_body: dict[str, object] = {
        "schema": PUBLISHED_TASK_ROOT_SCHEMA,
        "content_task_evidence_root_sha256": task_root_sha256,
        "shard_count": EVIDENCE_SHARDS_PER_TASK,
        "content_shard_rows_sha256": _canonical_sha256(content_rows),
        "published_shards": published_rows,
    }
    published_sha = _canonical_sha256(published_body)
    expected_published = _canonical_json_bytes({
        **published_body,
        "published_task_evidence_root_sha256": published_sha,
    })
    parsed_published = _parse_self_hashed_payload(
        authority_bundle.published_task_evidence_root_payload,
        label="published task evidence root",
        hash_field="published_task_evidence_root_sha256",
    )
    if (
        parsed_published.get("schema") != PUBLISHED_TASK_ROOT_SCHEMA
        or authority_bundle.published_task_evidence_root_payload
        != expected_published
        or authority_bundle.published_task_evidence_root_sha256
        != published_sha
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "published task evidence authority does not reconstruct"
        )
    bundle_body: dict[str, object] = {
        "schema": AUTHORITY_BUNDLE_SCHEMA,
        "draft_sha256": draft_sha256,
        "content_task_evidence_root_sha256": task_root_sha256,
        "published_task_evidence_root_sha256": published_sha,
        "published_shard_identity_set_sha256": _canonical_sha256(identities),
        "batch_result_sha256": batch_result_sha256,
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    bundle_sha = _canonical_sha256(bundle_body)
    expected_bundle = _canonical_json_bytes({
        **bundle_body, "bundle_sha256": bundle_sha,
    })
    parsed_bundle = _parse_self_hashed_payload(
        authority_bundle.canonical_bundle_payload,
        label="final authority bundle",
        hash_field="bundle_sha256",
    )
    if (
        parsed_bundle.get("schema") != AUTHORITY_BUNDLE_SCHEMA
        or authority_bundle.schema != AUTHORITY_BUNDLE_SCHEMA
        or authority_bundle.canonical_bundle_payload != expected_bundle
        or authority_bundle.bundle_sha256 != bundle_sha
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "final authority bundle does not reconstruct"
        )
    return bundle_sha


def _require_full_batch_shape(parameter_set_ids: Sequence[object]) -> None:
    observed = tuple(
        _strict_string(value, label="parameter-set id")
        for value in parameter_set_ids
    )
    if observed != PARAMETER_SET_ORDER:
        raise CorpusLegalFeasibilityVerificationError(
            "authority does not contain all seven parameter sets in frozen order"
        )
    if len(observed) * MAX_VISIT_OUTPUTS_BEFORE_DEDUPLICATION != 7_000:
        raise CorpusLegalFeasibilityVerificationError(
            "frozen seven-arm matrix cell count differs"
        )


def _require_task_verifier_gates(
    evidence_contract: Mapping[str, object],
) -> tuple[str, ...]:
    rows = tuple(
        _mapping(row, label=f"evidence-contract gate[{index}]")
        for index, row in enumerate(_sequence(
            evidence_contract.get("pre_outcome_gate_registry"),
            label="evidence-contract gates",
        ))
    )
    by_id: dict[str, Mapping[str, object]] = {}
    for row in rows:
        gate_id = _strict_string(
            row.get("id"), label="evidence-contract gate id"
        )
        if gate_id in by_id:
            raise CorpusLegalFeasibilityVerificationError(
                "evidence-contract gate IDs repeat"
            )
        by_id[gate_id] = row
    if any(
        gate_id not in by_id
        or by_id[gate_id].get("required_for_outcome_read") is not True
        for gate_id in _TASK_VERIFIER_GATE_IDS
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "evidence contract omits a required task-verifier gate"
        )
    return _TASK_VERIFIER_GATE_IDS


def _normalize_terminal_object_rows(
    value: object,
    *,
    label: str,
) -> tuple[dict[str, object], ...]:
    rows = tuple(
        _mapping(row, label=f"{label}[{ordinal}]")
        for ordinal, row in enumerate(_sequence(value, label=label))
    )
    if len(rows) != len(PARAMETER_SET_ORDER):
        raise CorpusLegalFeasibilityVerificationError(
            f"{label} does not cover all seven parameter sets"
        )
    normalized: list[dict[str, object]] = []
    for ordinal, (row, parameter_set_id) in enumerate(zip(
        rows, PARAMETER_SET_ORDER, strict=True
    )):
        _exact_keys(
            row,
            frozenset({"ordinal", "parameter_set_id", "object_identity"}),
            label=f"{label}[{ordinal}]",
        )
        if (
            _strict_int(
                row["ordinal"], label=f"{label}[{ordinal}] ordinal", minimum=0
            )
            != ordinal
            or _strict_string(
                row["parameter_set_id"],
                label=f"{label}[{ordinal}] parameter-set id",
            )
            != parameter_set_id
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"{label} order differs"
            )
        normalized.append({
            "ordinal": ordinal,
            "parameter_set_id": parameter_set_id,
            "object_identity": _normalize_object_identity(
                row["object_identity"], label=f"{label}[{ordinal}] object"
            ),
        })
    return tuple(normalized)


def _validate_task_terminal_receipt(
    raw: bytes,
    *,
    terminal_identity: Mapping[str, object],
    request: Mapping[str, object],
    manifest: Mapping[str, object],
    task_result: Mapping[str, object],
    evidence_contract_identity: Mapping[str, object],
    evidence_contract_sha256: str,
) -> Mapping[str, object]:
    terminal = _parse_self_hashed_payload(
        raw,
        label="task terminal receipt",
        hash_field="terminal_receipt_sha256",
    )
    _exact_keys(
        terminal,
        frozenset({
            "schema",
            "batch_manifest_sha256",
            "evidence_contract_identity",
            "evidence_contract_sha256",
            "task_request_sha256",
            "task_index",
            "task_sha256",
            "execution_id",
            "execution_uid",
            "task_attempt",
            "max_retries",
            "succeeded_count",
            "failed_count",
            "cancelled_count",
            "retried_count",
            "completed_condition",
            "strict_terminal_success",
            "runtime_image_terminal_verification",
            "ambient_score_relevant_keys_present",
            "authorities",
            "runtime_policy_objects",
            "variant_result_objects",
            "outcome_columns_read",
            "uses_realized_outcomes",
            "historical_scoring_licensed",
            "production_change_licensed",
            "decision_authority",
            "terminal_receipt_sha256",
        }),
        label="task terminal receipt",
    )
    task_index = _strict_int(
        request["task_index"], label="task request index", minimum=0
    )
    task = _mapping(manifest["tasks"][task_index], label="manifest task")
    execution = _mapping(task_result["execution"], label="task execution")
    normalized_terminal_identity = _normalize_object_identity(
        terminal_identity, label="task terminal receipt"
    )
    normalized_contract_identity = _normalize_object_identity(
        evidence_contract_identity, label="batch evidence contract"
    )
    retained_contract_identity = _normalize_object_identity(
        terminal["evidence_contract_identity"],
        label="terminal evidence contract",
    )
    runtime_image = _mapping(
        terminal["runtime_image_terminal_verification"],
        label="terminal runtime-image verification",
    )
    _exact_keys(
        runtime_image,
        frozenset({
            "source_commit_sha",
            "cloud_build_id",
            "immutable_image",
            "terminal_verification_required",
        }),
        label="terminal runtime-image verification",
    )
    if (
        re.fullmatch(
            r"[0-9a-f]{40}",
            _strict_string(
                runtime_image["source_commit_sha"],
                label="terminal source commit SHA",
            ),
        )
        is None
        or re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
            r"[0-9a-f]{4}-[0-9a-f]{12}",
            _strict_string(
                runtime_image["cloud_build_id"],
                label="terminal Cloud Build ID",
            ),
        )
        is None
        or runtime_image["immutable_image"]
        != manifest["common_law"]["immutable_image"]
        or runtime_image["terminal_verification_required"] is not True
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "terminal runtime-image authority differs"
        )
    terminal_uri = str(normalized_terminal_identity["uri"])
    if (
        terminal["schema"] != TASK_TERMINAL_SCHEMA
        or terminal["batch_manifest_sha256"]
        != manifest["batch_manifest_sha256"]
        or retained_contract_identity != normalized_contract_identity
        or terminal["evidence_contract_sha256"]
        != evidence_contract_sha256
        or terminal["task_request_sha256"]
        != request["task_request_sha256"]
        or terminal["task_index"] != task_index
        or terminal["task_sha256"] != task["task_sha256"]
        or terminal["execution_id"] != execution["execution_id"]
        or terminal["execution_uid"] != execution["execution_uid"]
        or _strict_int(
            terminal["task_attempt"], label="terminal task attempt", minimum=0
        )
        != 0
        or _strict_int(
            terminal["max_retries"], label="terminal max retries", minimum=0
        )
        != 0
        or _strict_int(
            terminal["succeeded_count"],
            label="terminal succeeded count",
            minimum=0,
        )
        != 1
        or _strict_int(
            terminal["failed_count"], label="terminal failed count", minimum=0
        )
        != 0
        or _strict_int(
            terminal["cancelled_count"],
            label="terminal cancelled count",
            minimum=0,
        )
        != 0
        or _strict_int(
            terminal["retried_count"],
            label="terminal retried count",
            minimum=0,
        )
        != 0
        or terminal["completed_condition"] != "True"
        or terminal["strict_terminal_success"] is not True
        or terminal["ambient_score_relevant_keys_present"] != []
        or terminal["outcome_columns_read"] != []
        or terminal["uses_realized_outcomes"] is not False
        or terminal["historical_scoring_licensed"] is not False
        or terminal["production_change_licensed"] is not False
        or terminal["decision_authority"] is not False
        or execution["attempt"] != 1
        or execution["retry_count"] != 0
        or execution["terminal_status"] != "succeeded"
        or _normalize_object_identity(
            execution["terminal_receipt"], label="task-result terminal receipt"
        )
        != normalized_terminal_identity
        or not terminal_uri.startswith(task["variant_output_prefix"])
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "task terminal status/retry/license authority differs"
        )

    authorities = _mapping(
        terminal["authorities"], label="terminal authority objects"
    )
    _exact_keys(
        authorities,
        frozenset(_TASK_AUTHORITY_OBJECT_ROLES),
        label="terminal authority objects",
    )
    normalized_authorities = {
        role: _normalize_object_identity(
            authorities[role], label=f"terminal authority {role}"
        )
        for role in _TASK_AUTHORITY_OBJECT_ROLES
    }
    runtime_rows = _normalize_terminal_object_rows(
        terminal["runtime_policy_objects"], label="runtime-policy objects"
    )
    result_rows = _normalize_terminal_object_rows(
        terminal["variant_result_objects"], label="variant-result objects"
    )
    task_variants = tuple(
        _mapping(row, label=f"task-result variant[{ordinal}]")
        for ordinal, row in enumerate(_sequence(
            task_result["variant_results"], label="task-result variants"
        ))
    )
    for ordinal, (runtime_row, result_row, task_variant) in enumerate(zip(
        runtime_rows, result_rows, task_variants, strict=True
    )):
        if (
            runtime_row["object_identity"]
            != _normalize_object_identity(
                task_variant["effective_policy_receipt"],
                label=f"task-result policy[{ordinal}]",
            )
            or result_row["object_identity"]
            != _normalize_object_identity(
                task_variant["result_object"],
                label=f"task-result result[{ordinal}]",
            )
            or runtime_row["parameter_set_id"]
            != task_variant["parameter_set_id"]
            or result_row["parameter_set_id"]
            != task_variant["parameter_set_id"]
        ):
            raise CorpusLegalFeasibilityVerificationError(
                f"terminal/task-result variant[{ordinal}] identities differ"
            )
    all_output_identities = [
        *normalized_authorities.values(),
        *(row["object_identity"] for row in runtime_rows),
        *(row["object_identity"] for row in result_rows),
        normalized_terminal_identity,
    ]
    uris = [str(identity["uri"]) for identity in all_output_identities]
    if (
        len(set(uris)) != len(uris)
        or any(
            not uri.startswith(task["variant_output_prefix"])
            for uri in uris
        )
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "task authority object namespace/uniqueness differs"
        )
    return terminal


def _read_task_source_objects(
    *,
    reader: GenerationPinnedObjectReader,
    request: Mapping[str, object],
    manifest: Mapping[str, object],
) -> tuple[bytes, bytes, bytes, dict[str, bytes], dict[str, bytes]]:
    task_index = int(request["task_index"])
    task = _mapping(manifest["tasks"][task_index], label="manifest task")
    common = _mapping(manifest["common_law"], label="common law")
    inventory_raw, _ = _read_generation_pinned_object(
        reader,
        common["effective_policy_inventory_identity"],
        maximum_bytes=MAX_CANONICAL_JSON_AUTHORITY_BYTES,
        label="effective-policy inventory",
    )
    completion_raw, _ = _read_generation_pinned_object(
        reader,
        common["artifact_source_authority_completion"],
        maximum_bytes=MAX_CANONICAL_JSON_AUTHORITY_BYTES,
        label="artifact source-authority completion",
    )
    source_raw, _ = _read_generation_pinned_object(
        reader,
        common["source_receipts"]["later_source_freeze"],
        maximum_bytes=MAX_CANONICAL_JSON_AUTHORITY_BYTES,
        label="later-source freeze",
    )
    world_bodies: dict[str, bytes] = {}
    for role in TASK_WORLD_SOURCE_ROLES:
        world_bodies[role], _ = _read_generation_pinned_object(
            reader,
            task["world_artifact_receipts"][role],
            maximum_bytes=MAX_CANONICAL_JSON_AUTHORITY_BYTES,
            label=f"task world artifact {role}",
        )
    common_bodies: dict[str, bytes] = {}
    for role in _COMMON_LAW_BODY_ROLES:
        common_bodies[role], _ = _read_generation_pinned_object(
            reader,
            common[role],
            maximum_bytes=MAX_CANONICAL_JSON_AUTHORITY_BYTES,
            label=f"common-law {role}",
        )
    return (
        inventory_raw,
        completion_raw,
        source_raw,
        world_bodies,
        common_bodies,
    )


def _normalize_published_shards(
    published_root: Mapping[str, object],
) -> tuple[_RawSolverEvidenceShard, ...]:
    published_shards = tuple(
        _mapping(row, label=f"published shard[{ordinal}]")
        for ordinal, row in enumerate(_sequence(
            published_root.get("published_shards"),
            label="published shards",
        ))
    )
    if len(published_shards) != EVIDENCE_SHARDS_PER_TASK:
        raise CorpusLegalFeasibilityVerificationError(
            "published root does not contain all 70 shard pairs"
        )
    shards: list[_RawSolverEvidenceShard] = []
    shard_uris: list[str] = []
    for ordinal, row in enumerate(published_shards):
        _exact_keys(
            row,
            frozenset({
                "global_shard_ordinal",
                "compressed_object_identity",
                "index_object_identity",
                "index_sha256",
                "index_object_sha256",
                "shard_root_sha256",
            }),
            label=f"published shard[{ordinal}]",
        )
        if _strict_int(
            row["global_shard_ordinal"],
            label=f"published shard[{ordinal}] ordinal",
            minimum=0,
        ) != ordinal:
            raise CorpusLegalFeasibilityVerificationError(
                "published shard order differs"
            )
        compressed_identity = _normalize_object_identity(
            row["compressed_object_identity"],
            label=f"published compressed shard[{ordinal}]",
        )
        index_identity = _normalize_object_identity(
            row["index_object_identity"],
            label=f"published index shard[{ordinal}]",
        )
        index_object_sha = _strict_sha(
            row["index_object_sha256"],
            label=f"published shard[{ordinal}] index-object SHA",
        )
        if index_object_sha != index_identity["sha256"]:
            raise CorpusLegalFeasibilityVerificationError(
                f"published shard[{ordinal}] index identity differs"
            )
        shard_uris.extend((
            str(compressed_identity["uri"]),
            str(index_identity["uri"]),
        ))
        shards.append(_RawSolverEvidenceShard(
            global_shard_ordinal=ordinal,
            compressed_object_identity=compressed_identity,
            index_object_identity=index_identity,
            index_sha256=_strict_sha(
                row["index_sha256"],
                label=f"published shard[{ordinal}] index SHA",
            ),
            index_object_sha256=index_object_sha,
            shard_root_sha256=_strict_sha(
                row["shard_root_sha256"],
                label=f"published shard[{ordinal}] root SHA",
            ),
        ))
    if len(set(shard_uris)) != EVIDENCE_SHARDS_PER_TASK * 2:
        raise CorpusLegalFeasibilityVerificationError(
            "published shard object URIs repeat"
        )
    return tuple(shards)


def _require_disjoint_task_output_uris(
    *,
    terminal: Mapping[str, object],
    terminal_identity: object,
    shards: Sequence[_RawSolverEvidenceShard],
) -> None:
    """Require one create-once URI for every retained task output object."""
    authorities = _mapping(
        terminal["authorities"], label="terminal authority objects"
    )
    runtime_rows = _normalize_terminal_object_rows(
        terminal["runtime_policy_objects"], label="runtime-policy objects"
    )
    result_rows = _normalize_terminal_object_rows(
        terminal["variant_result_objects"], label="variant-result objects"
    )
    normalized_terminal_identity = _normalize_object_identity(
        terminal_identity,
        label="terminal self identity",
    )
    non_shard_identities = [
        *(
            _normalize_object_identity(
                authorities[role], label=f"terminal authority {role}"
            )
            for role in _TASK_AUTHORITY_OBJECT_ROLES
        ),
        *(row["object_identity"] for row in runtime_rows),
        *(row["object_identity"] for row in result_rows),
        normalized_terminal_identity,
    ]
    shard_identities = [
        identity
        for shard in shards
        for identity in (
            _normalize_object_identity(
                shard.compressed_object_identity,
                label=(
                    f"published compressed shard[{shard.global_shard_ordinal}]"
                ),
            ),
            _normalize_object_identity(
                shard.index_object_identity,
                label=f"published index shard[{shard.global_shard_ordinal}]",
            ),
        )
    ]
    uris = [
        str(identity["uri"])
        for identity in (*non_shard_identities, *shard_identities)
    ]
    if len(set(uris)) != len(uris):
        raise CorpusLegalFeasibilityVerificationError(
            "task output object URIs are not globally create-once unique"
        )


def _load_raw_task_authority_bundle(
    *,
    reader: GenerationPinnedObjectReader,
    terminal: Mapping[str, object],
    task_result: Mapping[str, object],
    evidence_contract: Mapping[str, object],
) -> _RawAuthorityBundle:
    authority_identities = _mapping(
        terminal["authorities"], label="terminal authority objects"
    )
    authority_raw: dict[str, bytes] = {}
    for role in _TASK_AUTHORITY_OBJECT_ROLES:
        authority_raw[role], _ = _read_generation_pinned_object(
            reader,
            authority_identities[role],
            maximum_bytes=MAX_CANONICAL_JSON_AUTHORITY_BYTES,
            label=f"task authority {role}",
        )

    runtime_rows = _normalize_terminal_object_rows(
        terminal["runtime_policy_objects"], label="runtime-policy objects"
    )
    result_rows = _normalize_terminal_object_rows(
        terminal["variant_result_objects"], label="variant-result objects"
    )
    runtime_payloads: list[bytes] = []
    result_payloads: list[bytes] = []
    for ordinal, row in enumerate(runtime_rows):
        raw, _ = _read_generation_pinned_object(
            reader,
            row["object_identity"],
            maximum_bytes=MAX_CANONICAL_JSON_AUTHORITY_BYTES,
            label=f"runtime policy[{ordinal}]",
        )
        _mapping(
            _parse_canonical_json_bytes(raw, label=f"runtime policy[{ordinal}]"),
            label=f"runtime policy[{ordinal}]",
        )
        runtime_payloads.append(raw)
    for ordinal, row in enumerate(result_rows):
        raw, _ = _read_generation_pinned_object(
            reader,
            row["object_identity"],
            maximum_bytes=MAX_CANONICAL_JSON_AUTHORITY_BYTES,
            label=f"variant result[{ordinal}]",
        )
        _parse_self_hashed_payload(
            raw,
            label=f"variant result[{ordinal}]",
            hash_field="result_sha256",
        )
        result_payloads.append(raw)

    source_binding = _parse_self_hashed_payload(
        authority_raw["source_binding"],
        label="task source binding",
        hash_field="binding_sha256",
    )
    registered_law = _parse_self_hashed_payload(
        authority_raw["registered_law"],
        label="registered law",
        hash_field="binding_sha256",
    )
    attempt_ledger = _parse_self_hashed_payload(
        authority_raw["attempt_ledger"],
        label="attempt ledger",
        hash_field="attempt_ledger_sha256",
    )
    matrix_authority = _parse_self_hashed_payload(
        authority_raw["matrix_authority"],
        label="matrix authority",
        hash_field="matrix_authority_sha256",
    )
    content_root = _parse_self_hashed_payload(
        authority_raw["content_task_evidence_root"],
        label="content task evidence root",
        hash_field="task_evidence_root_sha256",
    )
    published_root = _parse_self_hashed_payload(
        authority_raw["published_task_evidence_root"],
        label="published task evidence root",
        hash_field="published_task_evidence_root_sha256",
    )
    draft_row = _parse_self_hashed_payload(
        authority_raw["draft_authority_bundle"],
        label="draft authority bundle",
        hash_field="draft_sha256",
    )
    bundle_row = _parse_self_hashed_payload(
        authority_raw["authority_bundle"],
        label="final authority bundle",
        hash_field="bundle_sha256",
    )
    batch_result = _parse_self_hashed_payload(
        authority_raw["batch_result"],
        label="batch result",
        hash_field="result_sha256",
    )

    shards = _normalize_published_shards(published_root)
    task_execution = _mapping(
        task_result["execution"], label="task-result execution"
    )
    _require_disjoint_task_output_uris(
        terminal=terminal,
        terminal_identity=task_execution["terminal_receipt"],
        shards=shards,
    )

    runtime_verification = _mapping(
        terminal["runtime_image_terminal_verification"],
        label="terminal runtime-image verification",
    )
    registered_code_source = _mapping(
        registered_law.get("code_source"),
        label="registered-law code source",
    )
    if (
        runtime_verification["source_commit_sha"]
        != registered_code_source.get("source_commit_sha")
        or runtime_verification["cloud_build_id"]
        != registered_code_source.get("cloud_build_id")
        or runtime_verification["immutable_image"]
        != registered_law.get("immutable_image")
        or registered_law.get(
            "runtime_image_terminal_verification_required"
        )
        is not True
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "terminal runtime image does not bind the registered law"
        )

    evidence_output_prefix = _strict_string(
        draft_row.get("evidence_output_prefix"),
        label="draft evidence output prefix",
    )
    raw_draft = _RawDraftAuthorities(
        schema=_strict_string(draft_row.get("schema"), label="draft schema"),
        source_binding_payload=authority_raw["source_binding"],
        source_binding_sha256=_strict_sha(
            source_binding.get("binding_sha256"),
            label="source-binding SHA",
        ),
        artifact_source_authority_completion_object_sha256=_strict_sha(
            draft_row.get(
                "artifact_source_authority_completion_object_sha256"
            ),
            label="draft source-authority completion-object SHA",
        ),
        artifact_source_authority_completion_sha256=_strict_sha(
            draft_row.get("artifact_source_authority_completion_sha256"),
            label="draft source-authority completion SHA",
        ),
        artifact_source_authority_task_sha256=_strict_sha(
            draft_row.get("artifact_source_authority_task_sha256"),
            label="draft source-authority task SHA",
        ),
        registered_law_payload=authority_raw["registered_law"],
        registered_law_sha256=_strict_sha(
            registered_law.get("binding_sha256"),
            label="registered-law SHA",
        ),
        runtime_policy_payloads=tuple(runtime_payloads),
        attempt_ledger_payload=authority_raw["attempt_ledger"],
        attempt_ledger_sha256=_strict_sha(
            attempt_ledger.get("attempt_ledger_sha256"),
            label="attempt-ledger SHA",
        ),
        matrix_authority_payload=authority_raw["matrix_authority"],
        matrix_authority_sha256=_strict_sha(
            matrix_authority.get("matrix_authority_sha256"),
            label="matrix-authority SHA",
        ),
        solver_evidence_shards=shards,
        solver_evidence_task_root_payload=authority_raw[
            "content_task_evidence_root"
        ],
        solver_evidence_task_root_sha256=_strict_sha(
            content_root.get("task_evidence_root_sha256"),
            label="content task-root SHA",
        ),
        variant_result_payloads=tuple(result_payloads),
        batch_result_payload=authority_raw["batch_result"],
        batch_result_sha256=_strict_sha(
            batch_result.get("result_sha256"), label="batch-result SHA"
        ),
        evidence_output_prefix=evidence_output_prefix,
        canonical_draft_payload=authority_raw["draft_authority_bundle"],
        draft_sha256=_strict_sha(
            draft_row.get("draft_sha256"), label="draft SHA"
        ),
    )
    return _RawAuthorityBundle(
        schema=_strict_string(bundle_row.get("schema"), label="bundle schema"),
        draft=raw_draft,
        published_task_evidence_root_payload=authority_raw[
            "published_task_evidence_root"
        ],
        published_task_evidence_root_sha256=_strict_sha(
            published_root.get("published_task_evidence_root_sha256"),
            label="published task-root SHA",
        ),
        canonical_bundle_payload=authority_raw["authority_bundle"],
        bundle_sha256=_strict_sha(
            bundle_row.get("bundle_sha256"), label="authority-bundle SHA"
        ),
        terminal_receipt=terminal,
        task_result=task_result,
        evidence_contract=evidence_contract,
        object_reader=reader,
    )


def verify_corpus_legal_feasibility_authority(
    *,
    task_request_bytes: bytes,
    task_result_identity: Mapping[str, object],
    evidence_contract_identity: Mapping[str, object],
    object_reader: GenerationPinnedObjectReader,
    repository_root: Path,
) -> IndependentVerificationReceipt:
    """Independently replay one durable outcome-blind seven-arm task.

    Every retained object is reopened through ``object_reader`` at the exact
    generation named by its canonical ``uri/generation/sha256/bytes``
    identity.  Producer dataclasses and producer-local paths are deliberately
    outside this boundary.
    """
    if (
        type(task_request_bytes) is not bytes
        or not task_request_bytes
        or len(task_request_bytes) > MAX_TASK_REQUEST_BYTES
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "task request bytes are empty, mistyped, or oversized"
        )
    if (
        not isinstance(repository_root, Path)
        or not repository_root.is_absolute()
        or not repository_root.is_dir()
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "repository_root must be one existing absolute directory"
        )
    request_value = _mapping(
        _parse_canonical_json_bytes(
            task_request_bytes, label="task request"
        ),
        label="task request",
    )
    manifest_identity = _mapping(
        request_value.get("batch_manifest_identity"),
        label="task-request manifest identity",
    )
    batch_manifest_bytes, normalized_manifest_identity = (
        _read_generation_pinned_object(
            object_reader,
            manifest_identity,
            maximum_bytes=MAX_CANONICAL_JSON_AUTHORITY_BYTES,
            label="batch manifest",
        )
    )
    try:
        request, manifest = bind_task_request_to_manifest(
            request_value, batch_manifest_bytes
        )
        manifest = validate_batch_manifest(manifest)
    except ValueError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "task request does not bind the reopened batch manifest"
        ) from exc

    evidence_contract_raw, normalized_evidence_contract_identity = (
        _read_generation_pinned_object(
            object_reader,
            evidence_contract_identity,
            maximum_bytes=MAX_EVIDENCE_CONTRACT_BYTES,
            label="batch evidence contract",
        )
    )
    try:
        evidence_contract = validate_corpus_batch_evidence_contract_bytes(
            evidence_contract_raw,
            batch_manifest=manifest,
            batch_manifest_identity=normalized_manifest_identity,
        )
        validate_corpus_batch_evidence_contract_identity(
            evidence_contract,
            normalized_evidence_contract_identity,
            batch_manifest=manifest,
            batch_manifest_identity=normalized_manifest_identity,
        )
    except CorpusBatchEvidenceContractError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "batch evidence contract does not bind the task manifest"
        ) from exc
    verified_gate_ids = _require_task_verifier_gates(evidence_contract)
    evidence_contract_sha = _strict_sha(
        evidence_contract.get("evidence_contract_sha256"),
        label="evidence-contract SHA",
    )

    task_result_raw, normalized_task_result_identity = (
        _read_generation_pinned_object(
            object_reader,
            task_result_identity,
            maximum_bytes=MAX_TASK_RESULT_BYTES,
            label="task result receipt",
        )
    )
    task_result_value = _mapping(
        _parse_canonical_json_bytes(
            task_result_raw, label="task result receipt"
        ),
        label="task result receipt",
    )
    try:
        task_result = validate_task_result_receipt(
            task_result_value,
            batch_manifest=manifest,
            batch_manifest_identity=normalized_manifest_identity,
        )
    except ValueError as exc:
        raise CorpusLegalFeasibilityVerificationError(
            "task result receipt does not bind the frozen task"
        ) from exc
    task_index = int(request["task_index"])
    task = _mapping(manifest["tasks"][task_index], label="manifest task")
    if (
        normalized_task_result_identity["uri"] != task["result_receipt_uri"]
        or task_result["task_index"] != task_index
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "task result durable identity differs from the manifest"
        )
    terminal_identity = _normalize_object_identity(
        _mapping(task_result["execution"], label="task execution")[
            "terminal_receipt"
        ],
        label="task terminal receipt",
    )
    terminal_raw, _ = _read_generation_pinned_object(
        object_reader,
        terminal_identity,
        maximum_bytes=MAX_TASK_TERMINAL_BYTES,
        label="task terminal receipt",
    )
    terminal = _validate_task_terminal_receipt(
        terminal_raw,
        terminal_identity=terminal_identity,
        request=request,
        manifest=manifest,
        task_result=task_result,
        evidence_contract_identity=normalized_evidence_contract_identity,
        evidence_contract_sha256=evidence_contract_sha,
    )
    authority_bundle = _load_raw_task_authority_bundle(
        reader=object_reader,
        terminal=terminal,
        task_result=task_result,
        evidence_contract=evidence_contract,
    )
    draft = authority_bundle.draft
    (
        effective_policy_inventory_bytes,
        artifact_source_authority_completion_bytes,
        later_source_freeze_bytes,
        world_artifact_bodies,
        common_law_bodies,
    ) = _read_task_source_objects(
        reader=object_reader,
        request=request,
        manifest=manifest,
    )
    raw_inputs = _load_verified_raw_inputs(
        task_request=request,
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
    _require_full_batch_shape([
        profile["parameter_set_id"] for profile in raw_inputs.profiles
    ])
    if (
        draft.source_binding_payload != raw_inputs.source_binding_payload
        or draft.source_binding_sha256 != raw_inputs.source_binding_sha256
        or draft.artifact_source_authority_completion_object_sha256
        != raw_inputs.artifact_source_authority_completion_object_sha256
        or draft.artifact_source_authority_completion_sha256
        != raw_inputs.artifact_source_authority_completion_sha256
        or draft.artifact_source_authority_task_sha256
        != raw_inputs.artifact_source_authority_task_sha256
        or draft.registered_law_payload != raw_inputs.registered_law_payload
        or draft.registered_law_sha256 != raw_inputs.registered_law_sha256
        or tuple(draft.runtime_policy_payloads)
        != raw_inputs.runtime_policy_payloads
        or _outcome_blind_columns(SOURCE_COLUMN_ORDER)
        != tuple(SOURCE_COLUMN_ORDER)
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "draft source/law/runtime authorities differ from raw replay"
        )
    for variant, (raw, profile) in enumerate(zip(
        draft.runtime_policy_payloads, raw_inputs.profiles, strict=True
    )):
        _runtime_binding_projection(
            raw,
            expected_profile=profile,
            label=f"draft runtime policy[{variant}]",
        )
    attempts = _parse_attempt_ledger(raw_inputs, draft)
    paired_summary = _paired_primary_optimum_summary(attempts)
    shard_rows, stage_count = _verify_solver_evidence_shards(
        raw_inputs=raw_inputs,
        draft=draft,
        attempts=attempts,
        object_reader=object_reader,
    )
    task_root_sha = _verify_content_task_root(draft, shard_rows)
    matrix_sha = _verify_matrix_authority(
        raw_inputs=raw_inputs,
        draft=draft,
        attempts=attempts,
        shard_rows=shard_rows,
        task_root_sha256=task_root_sha,
    )
    (
        variant_hashes,
        candidate_hashes,
        selected_hashes,
        outside_law_summaries,
        endpoint_summaries,
        coverage_summaries,
        unique_count,
        selected_count,
    ) = _verify_variant_results(
        raw_inputs=raw_inputs,
        draft=draft,
        attempts=attempts,
        matrix_authority_sha256=matrix_sha,
        task_root_sha256=task_root_sha,
    )
    batch_sha = _verify_batch_result(
        raw_inputs=raw_inputs,
        draft=draft,
        variant_result_sha256s=variant_hashes,
        matrix_authority_sha256=matrix_sha,
        task_root_sha256=task_root_sha,
    )
    draft_sha = _verify_draft_envelope(
        raw_inputs=raw_inputs,
        draft=draft,
        variant_result_sha256s=variant_hashes,
        batch_result_sha256=batch_sha,
        task_root_sha256=task_root_sha,
    )
    bundle_sha = _verify_published_envelope(
        authority_bundle=authority_bundle,
        draft_sha256=draft_sha,
        shard_rows=shard_rows,
        task_root_sha256=task_root_sha,
        batch_result_sha256=batch_sha,
    )
    if (
        len(attempts) != 7_000
        or stage_count != 14_000
        or selected_count != len(PARAMETER_SET_ORDER) * ENTRY_COUNT
        or authority_bundle.bundle_sha256 != bundle_sha
        or len(outside_law_summaries) != len(PARAMETER_SET_ORDER)
        or len(endpoint_summaries) != len(PARAMETER_SET_ORDER)
        or len(coverage_summaries) != len(PARAMETER_SET_ORDER)
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "final independent verification coverage differs"
        )
    body: dict[str, object] = {
        "schema": SCHEMA,
        "task_index": raw_inputs.request["task_index"],
        "season": raw_inputs.task["season"],
        "week": raw_inputs.task["week"],
        "slate_id": raw_inputs.task["slate_id"],
        "source_binding_sha256": raw_inputs.source_binding_sha256,
        "registered_law_sha256": raw_inputs.registered_law_sha256,
        "attempt_ledger_sha256": draft.attempt_ledger_sha256,
        "matrix_authority_sha256": matrix_sha,
        "solver_evidence_task_root_sha256": task_root_sha,
        "published_task_evidence_root_sha256": (
            authority_bundle.published_task_evidence_root_sha256
        ),
        "draft_sha256": draft_sha,
        "authority_bundle_sha256": bundle_sha,
        "artifact_source_authority_completion_object_sha256": (
            raw_inputs.artifact_source_authority_completion_object_sha256
        ),
        "artifact_source_authority_completion_sha256": (
            raw_inputs.artifact_source_authority_completion_sha256
        ),
        "artifact_source_authority_task_sha256": (
            raw_inputs.artifact_source_authority_task_sha256
        ),
        "evidence_contract_sha256": evidence_contract_sha,
        "task_result_sha256": task_result["task_result_sha256"],
        "terminal_receipt_sha256": terminal["terminal_receipt_sha256"],
        "variant_result_sha256s": list(variant_hashes),
        "batch_result_sha256": batch_sha,
        "candidate_score_sha256s": list(candidate_hashes),
        "selected_score_sha256s": list(selected_hashes),
        "paired_primary_optimum_summary": dict(paired_summary),
        "outside_incumbent_law_summaries": [
            dict(row) for row in outside_law_summaries
        ],
        "score_free_endpoint_summaries": [
            dict(row) for row in endpoint_summaries
        ],
        "score_matrix_coverage_summaries": [
            dict(row) for row in coverage_summaries
        ],
        "verified_cell_count": len(attempts),
        "verified_solver_stage_count": stage_count,
        "verified_unique_candidate_count": unique_count,
        "verified_selected_entry_count": selected_count,
        "verified_gate_ids": list(verified_gate_ids),
        "outcome_columns_read": [],
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
        "decision_authority": False,
    }
    verification_sha = _canonical_sha256(body)
    payload = _canonical_json_bytes({
        **body, "verification_sha256": verification_sha,
    })
    parsed_receipt = _parse_self_hashed_payload(
        payload,
        label="independent verification receipt",
        hash_field="verification_sha256",
    )
    if (
        parsed_receipt.get("schema") != SCHEMA
        or parsed_receipt.get("decision_authority") is not False
        or parsed_receipt.get("uses_realized_outcomes") is not False
        or parsed_receipt.get("historical_scoring_licensed") is not False
        or parsed_receipt.get("production_change_licensed") is not False
    ):
        raise CorpusLegalFeasibilityVerificationError(
            "independent verification receipt authority differs"
        )
    return IndependentVerificationReceipt(
        schema=SCHEMA,
        task_index=int(raw_inputs.request["task_index"]),
        season=int(raw_inputs.task["season"]),
        week=int(raw_inputs.task["week"]),
        slate_id=str(raw_inputs.task["slate_id"]),
        source_binding_sha256=raw_inputs.source_binding_sha256,
        registered_law_sha256=raw_inputs.registered_law_sha256,
        attempt_ledger_sha256=draft.attempt_ledger_sha256,
        matrix_authority_sha256=matrix_sha,
        solver_evidence_task_root_sha256=task_root_sha,
        published_task_evidence_root_sha256=(
            authority_bundle.published_task_evidence_root_sha256
        ),
        draft_sha256=draft_sha,
        authority_bundle_sha256=bundle_sha,
        artifact_source_authority_completion_object_sha256=(
            raw_inputs.artifact_source_authority_completion_object_sha256
        ),
        artifact_source_authority_completion_sha256=(
            raw_inputs.artifact_source_authority_completion_sha256
        ),
        artifact_source_authority_task_sha256=(
            raw_inputs.artifact_source_authority_task_sha256
        ),
        evidence_contract_sha256=evidence_contract_sha,
        task_result_sha256=str(task_result["task_result_sha256"]),
        terminal_receipt_sha256=str(terminal["terminal_receipt_sha256"]),
        variant_result_sha256s=variant_hashes,
        batch_result_sha256=batch_sha,
        candidate_score_sha256s=candidate_hashes,
        selected_score_sha256s=selected_hashes,
        paired_primary_optimum_summary=paired_summary,
        outside_incumbent_law_summaries=outside_law_summaries,
        score_free_endpoint_summaries=endpoint_summaries,
        score_matrix_coverage_summaries=coverage_summaries,
        verified_cell_count=len(attempts),
        verified_solver_stage_count=stage_count,
        verified_unique_candidate_count=unique_count,
        verified_selected_entry_count=selected_count,
        verified_gate_ids=verified_gate_ids,
        canonical_payload=payload,
        verification_sha256=verification_sha,
    )


__all__ = [
    "CorpusLegalFeasibilityVerificationError",
    "GenerationPinnedObjectReader",
    "IndependentVerificationReceipt",
    "SCHEMA",
    "TASK_TERMINAL_SCHEMA",
    "verify_corpus_legal_feasibility_authority",
]
