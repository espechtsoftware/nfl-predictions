"""Outcome-free legal-aware world-scheduling proxies for R6 research.

This module is deliberately isolated from the frozen Foundry producer,
verifier, manifests and candidate authority.  It provides two inexpensive
profile-specific signals over a player-by-world micro-DK matrix:

* a certified position/salary Lagrangian upper bound; and
* a bounded, solver-free feasible-core search whose witness is a legal roster.

Neither proxy reads realized outcomes.  Every ordering is total and stable:
larger score first, then smaller world index or canonical roster identity.

This is a non-authoritative offline compute contract.  Source-object,
producer-code/image and incumbent-candidate identities supplied here are typed
claims, not storage reads or runtime attestations.  A production consumer must
wrap these computations with caller-independent exact reads of pinned source
bytes, pinned code/image and incumbent authority, and a cumulative batch/run
work budget.  Receipts emitted here carry fixed false authority flags so they
cannot truthfully represent that outer admission step.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
import json
from itertools import combinations
import re
from typing import Final, Mapping, Sequence

import numpy as np

from . import corpus_legal_feasibility as legal
from . import residual_world_columns as rw


DOSE_RECEIPT_SCHEMA: Final = "corpus-r6-legal-scheduler-dose-v1"
PROXY_RECEIPT_SCHEMA: Final = "corpus-r6-legal-scheduler-proxy-receipt-v1"
POSITION_SALARY_PROXY_ID: Final = "position-salary-lagrangian-upper-bound"
FEASIBLE_CORE_PROXY_ID: Final = "bounded-feasible-core-lower-bound"
PROXY_VERSION: Final = "v1"
WORLD_TIE_BREAK: Final = "score-desc-world-index-asc"
ROSTER_TIE_BREAK: Final = "score-desc-canonical-player-id-asc"
POSITIONS: Final = ("QB", "RB", "WR", "TE", "DST")
_POSITION_INDEX: Final = {position: index for index, position in enumerate(POSITIONS)}
_INT64_MAX: Final = int(np.iinfo(np.int64).max)
_SHA256: Final = re.compile(r"[0-9a-f]{64}")
_IMAGE_DIGEST: Final = re.compile(r"sha256:[0-9a-f]{64}")
SUPPORTED_PROXY_IDS: Final = frozenset({
    POSITION_SALARY_PROXY_ID,
    FEASIBLE_CORE_PROXY_ID,
})
MAX_WORLDS_PER_BATCH: Final = rw.WORLDS_PER_BLOCK
MAX_PLAYERS_PER_BATCH: Final = 512
MAX_THETA_VALUES: Final = 64
MAX_TOP_PLAYERS_PER_POSITION: Final = 32
MAX_CHEAPEST_PLAYERS_PER_POSITION: Final = 8
MAX_STRUCTURAL_CORES: Final = 128
MAX_BEAM_WIDTH: Final = 256
MAX_STATE_EXPANSIONS: Final = 16_384
MAX_COMBINATION_CANDIDATES: Final = 4_096
MAX_CORE_CANDIDATES: Final = 4_096
MAX_INCUMBENT_CANDIDATES: Final = 512
OFFLINE_AUTHORITY_SCOPE: Final = "non-authoritative-offline-compute-only"
OUTER_EXACT_READ_PINNED_AUTHORITY_REQUIRED: Final = True
OUTER_CUMULATIVE_BATCH_RUN_BUDGET_REQUIRED: Final = True


class CorpusR6LegalSchedulerError(ValueError):
    """The isolated scheduler proxy contract was violated."""


def _strict_int(value: object, *, label: str, minimum: int | None = None) -> int:
    if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
        raise CorpusR6LegalSchedulerError(f"{label} must be an integer")
    result = int(value)
    if minimum is not None and result < minimum:
        raise CorpusR6LegalSchedulerError(f"{label} is below its minimum")
    return result


def _strict_string(value: object, *, label: str) -> str:
    if type(value) is not str or not value or value != value.strip():
        raise CorpusR6LegalSchedulerError(f"{label} must be one nonempty string")
    return value


def _strict_sha(value: object, *, label: str) -> str:
    result = _strict_string(value, label=label)
    if _SHA256.fullmatch(result) is None:
        raise CorpusR6LegalSchedulerError(f"{label} must be one lowercase SHA-256")
    return result


def _exact_keys(
    value: Mapping[str, object], expected: frozenset[str], *, label: str,
) -> None:
    if frozenset(value) != expected:
        raise CorpusR6LegalSchedulerError(f"{label} fields differ")


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
        raise CorpusR6LegalSchedulerError("value is not canonical JSON") from exc


def _canonical_sha256(value: object) -> str:
    return sha256(_canonical_json_bytes(value)).hexdigest()


def _offline_authority_payload() -> dict[str, object]:
    """Return fixed claims that prevent an offline receipt from implying admission."""
    return {
        "scope": OFFLINE_AUTHORITY_SCOPE,
        "authoritative": False,
        "source_artifact_claim_verified": False,
        "producer_code_image_claim_verified": False,
        "incumbent_candidate_claim_verified": False,
        "outer_exact_read_pinned_authority_required": (
            OUTER_EXACT_READ_PINNED_AUTHORITY_REQUIRED
        ),
        "outer_cumulative_batch_run_budget_required": (
            OUTER_CUMULATIVE_BATCH_RUN_BUDGET_REQUIRED
        ),
    }


@dataclass(frozen=True, slots=True)
class DoseReceipt:
    """Immutable self-hashed identity of one proxy dose."""

    proxy_id: str
    proxy_version: str
    canonical_payload: bytes
    dose_sha256: str


@dataclass(frozen=True, slots=True)
class ProxyReceipt:
    """Immutable non-authoritative offline receipt for one proxy computation."""

    proxy_id: str
    proxy_version: str
    profile_id: str
    profile_payload_sha256: str
    dose_sha256: str
    source_artifact_sha256: str
    input_binding_sha256: str
    producer_identity_sha256: str
    producer_result_sha256: str
    player_catalog_sha256: str
    player_score_matrix_sha256: str
    world_schedule_sha256: str
    score_vector_sha256: str
    selected_indices: tuple[int, ...]
    authoritative: bool
    outer_exact_read_pinned_authority_required: bool
    outer_cumulative_batch_run_budget_required: bool
    canonical_payload: bytes
    receipt_sha256: str


@dataclass(frozen=True, slots=True)
class SourceArtifactIdentity:
    """Typed caller claim about a source artifact; storage is not read here."""

    uri: str
    generation: int
    byte_count: int
    sha256: str
    scientific_contract_sha256: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "uri", _strict_string(self.uri, label="source URI"))
        object.__setattr__(
            self,
            "generation",
            _strict_int(self.generation, label="source generation", minimum=1),
        )
        object.__setattr__(
            self,
            "byte_count",
            _strict_int(self.byte_count, label="source byte count", minimum=1),
        )
        object.__setattr__(
            self, "sha256", _strict_sha(self.sha256, label="source SHA-256")
        )
        object.__setattr__(
            self,
            "scientific_contract_sha256",
            _strict_sha(
                self.scientific_contract_sha256,
                label="source scientific-contract SHA-256",
            ),
        )

    def as_payload(self) -> dict[str, object]:
        return {
            "uri": self.uri,
            "generation": self.generation,
            "byte_count": self.byte_count,
            "sha256": self.sha256,
            "scientific_contract_sha256": self.scientific_contract_sha256,
        }


@dataclass(frozen=True, slots=True)
class ProducerIdentity:
    """Typed caller claim about code/image identity; no attestation occurs here."""

    proxy_id: str
    code_sha256: str
    image_digest: str

    def __post_init__(self) -> None:
        proxy = _strict_string(self.proxy_id, label="producer proxy id")
        if proxy not in SUPPORTED_PROXY_IDS:
            raise CorpusR6LegalSchedulerError("producer proxy id is unsupported")
        object.__setattr__(self, "proxy_id", proxy)
        object.__setattr__(
            self,
            "code_sha256",
            _strict_sha(self.code_sha256, label="producer code SHA-256"),
        )
        digest = _strict_string(self.image_digest, label="producer image digest")
        if _IMAGE_DIGEST.fullmatch(digest) is None:
            raise CorpusR6LegalSchedulerError("producer image digest is malformed")
        object.__setattr__(self, "image_digest", digest)

    def as_payload(self) -> dict[str, object]:
        return {
            "proxy_id": self.proxy_id,
            "code_sha256": self.code_sha256,
            "image_digest": self.image_digest,
        }


@dataclass(frozen=True, slots=True)
class ProxyInputBinding:
    """Hash-bound inputs and identity claims accepted by the offline producers."""

    source_artifact: SourceArtifactIdentity
    ordered_world_ids: tuple[rw.WorldId, ...]
    world_schedule_sha256: str
    player_catalog_sha256: str
    player_score_matrix_sha256: str
    binding_sha256: str

    def as_payload(self) -> dict[str, object]:
        return {
            "source_artifact": self.source_artifact.as_payload(),
            "ordered_world_ids": [
                {"block": world.block, "index": world.index}
                for world in self.ordered_world_ids
            ],
            "world_schedule_sha256": self.world_schedule_sha256,
            "player_catalog_sha256": self.player_catalog_sha256,
            "player_score_matrix_sha256": self.player_score_matrix_sha256,
            "binding_sha256": self.binding_sha256,
        }


@dataclass(frozen=True, slots=True)
class SalaryPositionDose:
    """Signed Lagrange slopes, in micro-DK per salary dollar.

    Nonnegative slopes dualize the salary cap.  Negative slopes dualize the
    active salary floor.  Zero is mandatory and exactly reproduces the existing
    position-only bound.
    """

    theta_micro_per_salary_dollar: tuple[int, ...]

    def __post_init__(self) -> None:
        values = tuple(
            _strict_int(value, label="salary-position theta")
            for value in self.theta_micro_per_salary_dollar
        )
        if (
            not values
            or 0 not in values
            or values != tuple(sorted(set(values)))
        ):
            raise CorpusR6LegalSchedulerError(
                "salary-position theta grid must be sorted, unique and include zero"
            )
        if len(values) > MAX_THETA_VALUES:
            raise CorpusR6LegalSchedulerError(
                "salary-position theta grid exceeds its hard maximum"
            )
        object.__setattr__(self, "theta_micro_per_salary_dollar", values)

    def as_payload(self) -> dict[str, object]:
        return {
            "theta_micro_per_salary_dollar": list(
                self.theta_micro_per_salary_dollar
            ),
            "theta_zero_required": True,
            "maximum_theta_count": MAX_THETA_VALUES,
            "bound_law": (
                "min-theta-position-shape-of-score-minus-theta-salary-plus-"
                "theta-active-boundary"
            ),
        }

    def receipt(self) -> DoseReceipt:
        return _dose_receipt(POSITION_SALARY_PROXY_ID, self.as_payload())


@dataclass(frozen=True, slots=True)
class FeasibleCoreDose:
    """Deterministic limits for the solver-free feasible-core search."""

    top_by_position: tuple[tuple[str, int], ...]
    cheapest_per_position: int
    max_cores: int
    beam_width: int
    max_state_expansions: int
    max_combination_candidates: int
    max_core_candidates: int
    max_incumbent_candidates: int

    def __post_init__(self) -> None:
        normalized: list[tuple[str, int]] = []
        for raw_position, raw_count in self.top_by_position:
            position = _strict_string(raw_position, label="dose position").upper()
            count = _strict_int(
                raw_count, label=f"{position} top-player dose", minimum=1
            )
            normalized.append((position, count))
        values = tuple(normalized)
        if tuple(position for position, _ in values) != POSITIONS:
            raise CorpusR6LegalSchedulerError(
                "feasible-core top-player dose must use canonical position order"
            )
        if any(count > MAX_TOP_PLAYERS_PER_POSITION for _, count in values):
            raise CorpusR6LegalSchedulerError(
                "feasible-core top-player dose exceeds its hard maximum"
            )
        object.__setattr__(self, "top_by_position", values)
        limits = {
            "cheapest_per_position": MAX_CHEAPEST_PLAYERS_PER_POSITION,
            "max_cores": MAX_STRUCTURAL_CORES,
            "beam_width": MAX_BEAM_WIDTH,
            "max_state_expansions": MAX_STATE_EXPANSIONS,
            "max_combination_candidates": MAX_COMBINATION_CANDIDATES,
            "max_core_candidates": MAX_CORE_CANDIDATES,
            "max_incumbent_candidates": MAX_INCUMBENT_CANDIDATES,
        }
        for field_name, hard_maximum in limits.items():
            minimum = 0 if field_name == "cheapest_per_position" else 1
            value = _strict_int(
                getattr(self, field_name), label=field_name, minimum=minimum
            )
            if value > hard_maximum:
                raise CorpusR6LegalSchedulerError(
                    f"{field_name} exceeds its hard maximum"
                )
            object.__setattr__(
                self,
                field_name,
                value,
            )

    def as_payload(self) -> dict[str, object]:
        return {
            "top_by_position": {
                position: count for position, count in self.top_by_position
            },
            "cheapest_per_position": self.cheapest_per_position,
            "max_cores": self.max_cores,
            "beam_width": self.beam_width,
            "max_state_expansions": self.max_state_expansions,
            "max_combination_candidates": self.max_combination_candidates,
            "max_core_candidates": self.max_core_candidates,
            "max_incumbent_candidates": self.max_incumbent_candidates,
            "maximum_worlds_per_batch": MAX_WORLDS_PER_BATCH,
            "maximum_players_per_batch": MAX_PLAYERS_PER_BATCH,
            "state_expansion_law": "count-every-completion-player-considered",
            "combination_candidate_law": (
                "count-every-structural-combination-including-empty-identity"
            ),
            "core_candidate_law": "count-every-core-cross-product-considered",
            "incumbent_evaluation_law": (
                "candidate-count-times-bound-world-count"
            ),
            "work_caps_scope": "per-world-within-one-bounded-batch",
            "outer_cumulative_batch_run_budget_required": (
                OUTER_CUMULATIVE_BATCH_RUN_BUDGET_REQUIRED
            ),
            "fallback": "best-profile-legal-incumbent-candidate",
            "solver_calls": 0,
        }

    def receipt(self) -> DoseReceipt:
        return _dose_receipt(FEASIBLE_CORE_PROXY_ID, self.as_payload())


DEFAULT_SALARY_POSITION_DOSE: Final = SalaryPositionDose(
    (-4_000, -2_000, -1_000, 0, 1_000, 2_000, 4_000, 8_000)
)
DEFAULT_FEASIBLE_CORE_DOSE: Final = FeasibleCoreDose(
    top_by_position=(("QB", 4), ("RB", 10), ("WR", 14), ("TE", 6), ("DST", 4)),
    cheapest_per_position=2,
    max_cores=32,
    beam_width=64,
    max_state_expansions=4_096,
    max_combination_candidates=512,
    max_core_candidates=1_024,
    max_incumbent_candidates=256,
)


@dataclass(frozen=True, slots=True)
class FeasibleCoreBatch:
    """One legal witness and certified lower-bound score per world."""

    lower_bounds_micro: tuple[int, ...]
    rosters: tuple[tuple[str, ...], ...]
    state_expansions: tuple[int, ...]
    combination_candidates_considered: tuple[int, ...]
    core_candidates_considered: tuple[int, ...]
    incumbent_sentinel_scores_micro: tuple[int, ...]
    incumbent_sentinel_rosters: tuple[tuple[str, ...], ...]
    incumbent_candidates_evaluated: int
    incumbent_score_cells_evaluated: int
    dose_receipt: DoseReceipt


@dataclass(frozen=True, slots=True)
class PositionSalaryProxyResult:
    """Typed non-authoritative offline output of the position/salary producer."""

    profile: legal.EffectivePolicyProfile
    dose: SalaryPositionDose
    dose_receipt: DoseReceipt
    input_binding: ProxyInputBinding
    producer_identity: ProducerIdentity
    upper_bounds_micro: tuple[int, ...]
    result_sha256: str


@dataclass(frozen=True, slots=True)
class FeasibleCoreProxyResult:
    """Typed offline output with replayable caller-supplied incumbent claims."""

    profile: legal.EffectivePolicyProfile
    dose: FeasibleCoreDose
    input_binding: ProxyInputBinding
    producer_identity: ProducerIdentity
    incumbent_candidates: tuple[tuple[str, ...], ...]
    batch: FeasibleCoreBatch
    result_sha256: str


TypedProxyResult = PositionSalaryProxyResult | FeasibleCoreProxyResult


@dataclass(slots=True)
class _WorldWork:
    combination_candidates: int = 0
    core_candidates: int = 0
    state_expansions: int = 0


@dataclass(frozen=True, slots=True)
class _BeamState:
    rows: tuple[int, ...]
    score_micro: int
    salary: int


def _dose_receipt(proxy_id: str, dose: Mapping[str, object]) -> DoseReceipt:
    proxy = _strict_string(proxy_id, label="proxy id")
    if proxy not in SUPPORTED_PROXY_IDS:
        raise CorpusR6LegalSchedulerError("proxy id is unsupported")
    body = {
        "schema": DOSE_RECEIPT_SCHEMA,
        "proxy_id": proxy,
        "proxy_version": PROXY_VERSION,
        "dose": dict(dose),
    }
    digest = _canonical_sha256(body)
    payload = _canonical_json_bytes({**body, "dose_sha256": digest})
    return DoseReceipt(proxy, PROXY_VERSION, payload, digest)


def validate_dose_receipt(receipt: DoseReceipt) -> None:
    """Recompute an immutable dose receipt and fail on any discrepancy."""
    if not isinstance(receipt, DoseReceipt):
        raise CorpusR6LegalSchedulerError("dose receipt type differs")
    try:
        payload = json.loads(receipt.canonical_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6LegalSchedulerError("dose receipt payload is unreadable") from exc
    if not isinstance(payload, dict):
        raise CorpusR6LegalSchedulerError("dose receipt payload is not an object")
    _exact_keys(
        payload,
        frozenset({
            "schema", "proxy_id", "proxy_version", "dose", "dose_sha256",
        }),
        label="dose receipt",
    )
    if (
        payload["schema"] != DOSE_RECEIPT_SCHEMA
        or payload["proxy_id"] != receipt.proxy_id
        or payload["proxy_version"] != receipt.proxy_version
        or payload["dose_sha256"] != receipt.dose_sha256
    ):
        raise CorpusR6LegalSchedulerError("dose receipt fields differ")
    proxy = _strict_string(payload["proxy_id"], label="dose proxy id")
    if proxy not in SUPPORTED_PROXY_IDS:
        raise CorpusR6LegalSchedulerError("dose proxy id is unsupported")
    _strict_sha(payload["dose_sha256"], label="dose SHA-256")
    dose_payload = payload["dose"]
    if not isinstance(dose_payload, dict):
        raise CorpusR6LegalSchedulerError("dose payload is not an object")
    if proxy == POSITION_SALARY_PROXY_ID:
        _exact_keys(
            dose_payload,
            frozenset({
                "theta_micro_per_salary_dollar",
                "theta_zero_required",
                "maximum_theta_count",
                "bound_law",
            }),
            label="position/salary dose",
        )
        theta = dose_payload["theta_micro_per_salary_dollar"]
        if not isinstance(theta, list):
            raise CorpusR6LegalSchedulerError("position/salary theta is not a list")
        reconstructed: SalaryPositionDose | FeasibleCoreDose = SalaryPositionDose(
            tuple(theta)
        )
    else:
        _exact_keys(
            dose_payload,
            frozenset({
                "top_by_position",
                "cheapest_per_position",
                "max_cores",
                "beam_width",
                "max_state_expansions",
                "max_combination_candidates",
                "max_core_candidates",
                "max_incumbent_candidates",
                "maximum_worlds_per_batch",
                "maximum_players_per_batch",
                "state_expansion_law",
                "combination_candidate_law",
                "core_candidate_law",
                "incumbent_evaluation_law",
                "work_caps_scope",
                "outer_cumulative_batch_run_budget_required",
                "fallback",
                "solver_calls",
            }),
            label="feasible-core dose",
        )
        top = dose_payload["top_by_position"]
        if not isinstance(top, dict):
            raise CorpusR6LegalSchedulerError(
                "feasible-core top-player dose is not an object"
            )
        _exact_keys(top, frozenset(POSITIONS), label="top-player dose")
        reconstructed = FeasibleCoreDose(
            top_by_position=tuple((position, top[position]) for position in POSITIONS),
            cheapest_per_position=dose_payload["cheapest_per_position"],
            max_cores=dose_payload["max_cores"],
            beam_width=dose_payload["beam_width"],
            max_state_expansions=dose_payload["max_state_expansions"],
            max_combination_candidates=dose_payload[
                "max_combination_candidates"
            ],
            max_core_candidates=dose_payload["max_core_candidates"],
            max_incumbent_candidates=dose_payload[
                "max_incumbent_candidates"
            ],
        )
    if reconstructed.as_payload() != dose_payload:
        raise CorpusR6LegalSchedulerError("dose payload semantics differ")
    body = dict(payload)
    body.pop("dose_sha256", None)
    if (
        receipt.proxy_version != PROXY_VERSION
        or _canonical_sha256(body) != receipt.dose_sha256
        or _canonical_json_bytes(payload) != receipt.canonical_payload
    ):
        raise CorpusR6LegalSchedulerError("dose receipt hash/canonical bytes differ")


def _validate_profile(
    profile: legal.EffectivePolicyProfile,
) -> legal.EffectivePolicyProfile:
    if not isinstance(profile, legal.EffectivePolicyProfile):
        raise CorpusR6LegalSchedulerError("profile type differs")
    for frozen in legal.frozen_policy_profiles():
        if profile == frozen:
            return frozen
    raise CorpusR6LegalSchedulerError("profile is outside the frozen seven R6 doses")


def _canonical_players_and_scores(
    players: Sequence[rw.PlayerSpec], player_scores_micro: np.ndarray,
) -> tuple[tuple[rw.PlayerSpec, ...], np.ndarray]:
    rows = tuple(players)
    if not rows or any(not isinstance(player, rw.PlayerSpec) for player in rows):
        raise CorpusR6LegalSchedulerError("players must be PlayerSpec rows")
    ids = tuple(player.player_id for player in rows)
    if len(set(ids)) != len(ids):
        raise CorpusR6LegalSchedulerError("player ids repeat")
    matrix = np.asarray(player_scores_micro)
    if (
        matrix.ndim != 2
        or matrix.shape[0] != len(rows)
        or matrix.shape[1] == 0
        or matrix.dtype.kind not in "iu"
        or matrix.dtype.kind == "b"
        or matrix.dtype.itemsize > 8
    ):
        raise CorpusR6LegalSchedulerError(
            "player scores must be one aligned nonempty integer matrix"
        )
    if len(rows) > MAX_PLAYERS_PER_BATCH:
        raise CorpusR6LegalSchedulerError(
            "player count exceeds hard batch maximum"
        )
    if matrix.shape[1] > MAX_WORLDS_PER_BATCH:
        raise CorpusR6LegalSchedulerError(
            "world count exceeds hard batch maximum"
        )
    if matrix.dtype.kind == "u" and matrix.size and int(matrix.max()) > _INT64_MAX:
        raise CorpusR6LegalSchedulerError("player scores exceed signed int64")
    order = tuple(sorted(range(len(rows)), key=lambda index: ids[index]))
    canonical_rows = tuple(rows[index] for index in order)
    canonical_matrix = np.ascontiguousarray(matrix[list(order)], dtype=np.int64)
    maximum = max(abs(int(canonical_matrix.min())), abs(int(canonical_matrix.max())))
    if maximum * rw.ROSTER_SIZE > _INT64_MAX:
        raise CorpusR6LegalSchedulerError("nine-player score sum overflows int64")
    canonical_matrix.flags.writeable = False
    return canonical_rows, canonical_matrix


def _micro_vector(values: Sequence[object] | np.ndarray) -> np.ndarray:
    array = np.asarray(values)
    if (
        array.ndim != 1
        or array.size == 0
        or array.dtype.kind not in "iu"
        or array.dtype.kind == "b"
        or array.dtype.itemsize > 8
    ):
        raise CorpusR6LegalSchedulerError("proxy scores must be one integer vector")
    if array.dtype.kind == "u" and int(array.max()) > _INT64_MAX:
        raise CorpusR6LegalSchedulerError("proxy scores exceed signed int64")
    result = np.ascontiguousarray(array, dtype=np.int64)
    result.flags.writeable = False
    return result


def stable_rank_micro(
    values: Sequence[object] | np.ndarray, selected_count: int,
) -> tuple[int, ...]:
    """Rank exact scores descending with smaller world index as the total tie."""
    scores = _micro_vector(values)
    count = _strict_int(selected_count, label="selected count", minimum=1)
    if count > len(scores):
        raise CorpusR6LegalSchedulerError("selected count exceeds world count")
    # Convert to Python int before negation.  Negating int64.min in NumPy wraps
    # to itself and would silently put that value at the front of the ranking.
    ranked = sorted(
        range(len(scores)), key=lambda index: (-int(scores[index]), index)
    )
    return tuple(ranked[:count])


def _profile_salary_interval(
    profile: legal.EffectivePolicyProfile,
) -> tuple[int, int]:
    floor = _strict_int(
        profile.constraints.min_salary, label="profile salary floor", minimum=0
    )
    cap = _strict_int(
        profile.constraints.budget, label="profile salary cap", minimum=1
    )
    if profile.constraints.max_salary is not None:
        cap = min(
            cap,
            _strict_int(
                profile.constraints.max_salary,
                label="profile maximum salary",
                minimum=1,
            ),
        )
    if floor > cap:
        raise CorpusR6LegalSchedulerError("profile salary interval is empty")
    return floor, cap


def position_salary_upper_bounds_micro(
    player_scores_micro: np.ndarray,
    players: Sequence[rw.PlayerSpec],
    profile: legal.EffectivePolicyProfile,
    *,
    dose: SalaryPositionDose = DEFAULT_SALARY_POSITION_DOSE,
) -> np.ndarray:
    """Return a certified position/salary upper bound for every world.

    For a feasible roster with salary ``S`` and active interval ``[F, C]``:

    * ``theta >= 0`` adds ``theta * (C - S) >= 0``;
    * ``theta < 0`` adds ``theta * (F - S) >= 0``.

    Maximizing that adjusted objective over only the three DK position shapes
    relaxes every other legal constraint.  Taking the minimum across theta
    therefore remains an upper bound.
    """
    frozen_profile = _validate_profile(profile)
    if not isinstance(dose, SalaryPositionDose):
        raise CorpusR6LegalSchedulerError("salary-position dose type differs")
    validate_dose_receipt(dose.receipt())
    rows, scores = _canonical_players_and_scores(players, player_scores_micro)
    floor, cap = _profile_salary_interval(frozen_profile)
    salaries = np.asarray([player.salary for player in rows], dtype=np.int64)
    maximum_score = max(abs(int(scores.min())), abs(int(scores.max())))
    maximum_salary = int(salaries.max(initial=0))
    maximum_theta = max(abs(value) for value in dose.theta_micro_per_salary_dollar)
    maximum_adjusted = maximum_score + maximum_theta * maximum_salary
    maximum_total = (
        rw.ROSTER_SIZE * maximum_adjusted
        + maximum_theta * max(floor, cap)
    )
    if maximum_total > _INT64_MAX:
        raise CorpusR6LegalSchedulerError("salary-position bound overflows int64")

    result: np.ndarray | None = None
    positions = tuple(player.position for player in rows)
    for theta in dose.theta_micro_per_salary_dollar:
        adjusted = scores - np.int64(theta) * salaries[:, None]
        positional = rw.position_shape_upper_bounds_micro(adjusted, positions)
        boundary = cap if theta >= 0 else floor
        bound = positional + np.int64(theta * boundary)
        result = bound if result is None else np.minimum(result, bound)
    assert result is not None
    final = np.ascontiguousarray(result, dtype=np.int64)
    final.flags.writeable = False
    return final


def _profile_prohibited_violations(
    profile: legal.EffectivePolicyProfile, violations: Sequence[str],
) -> tuple[str, ...]:
    return tuple(
        field for field in violations if profile.value(field) not in (0, False)
    )


def audit_profile_roster(
    players: Sequence[rw.PlayerSpec],
    roster: Sequence[object],
    profile: legal.EffectivePolicyProfile,
) -> tuple[str, ...]:
    """Audit one witness against DK rules and its exact frozen R6 profile."""
    frozen = _validate_profile(profile)
    try:
        identity = legal.audit_dk_classic(tuple(players), roster)
        violations = legal.house_rule_violations(tuple(players), identity)
    except legal.CorpusLegalFeasibilityError as exc:
        raise CorpusR6LegalSchedulerError(str(exc)) from exc
    prohibited = _profile_prohibited_violations(frozen, violations)
    if prohibited:
        raise CorpusR6LegalSchedulerError(
            f"roster violates active profile rules: {prohibited}"
        )
    return violations


def _profile_legal(
    players: tuple[rw.PlayerSpec, ...],
    roster: tuple[str, ...],
    profile: legal.EffectivePolicyProfile,
) -> bool:
    try:
        audit_profile_roster(players, roster, profile)
    except CorpusR6LegalSchedulerError:
        return False
    return True


def _canonical_incumbents(
    players: tuple[rw.PlayerSpec, ...],
    incumbent_candidates: Sequence[Sequence[object]],
    profile: legal.EffectivePolicyProfile,
    dose: FeasibleCoreDose,
) -> tuple[tuple[str, ...], ...]:
    if isinstance(incumbent_candidates, (str, bytes)):
        raise CorpusR6LegalSchedulerError("incumbent candidates must be rosters")
    if len(incumbent_candidates) > dose.max_incumbent_candidates:
        raise CorpusR6LegalSchedulerError(
            "incumbent candidate count exceeds its dose maximum"
        )
    result: list[tuple[str, ...]] = []
    seen: set[tuple[str, ...]] = set()
    for ordinal, value in enumerate(incumbent_candidates):
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            raise CorpusR6LegalSchedulerError(
                f"incumbent candidate {ordinal} is not a roster"
            )
        identity = tuple(value)
        try:
            audited = legal.audit_dk_classic(players, identity)
        except legal.CorpusLegalFeasibilityError as exc:
            raise CorpusR6LegalSchedulerError(
                f"incumbent candidate {ordinal} is not DK legal: {exc}"
            ) from exc
        if audited in seen:
            raise CorpusR6LegalSchedulerError("incumbent candidate repeats")
        seen.add(audited)
        if _profile_legal(players, audited, profile):
            result.append(audited)
    if not result:
        raise CorpusR6LegalSchedulerError(
            "no incumbent candidate is legal under the requested profile"
        )
    return tuple(sorted(result))


def _incumbent_sentinels(
    players: tuple[rw.PlayerSpec, ...],
    scores: np.ndarray,
    incumbents: tuple[tuple[str, ...], ...],
) -> tuple[np.ndarray, tuple[tuple[str, ...], ...]]:
    row_by_id = {player.player_id: index for index, player in enumerate(players)}
    best_scores: np.ndarray | None = None
    best_roster_ordinals = np.zeros(scores.shape[1], dtype=np.int64)
    for ordinal, roster in enumerate(incumbents):
        rows = np.asarray([row_by_id[player_id] for player_id in roster], dtype=int)
        value = scores[rows].sum(axis=0, dtype=np.int64)
        if best_scores is None:
            best_scores = np.ascontiguousarray(value, dtype=np.int64)
        else:
            improved = value > best_scores
            best_scores[improved] = value[improved]
            best_roster_ordinals[improved] = ordinal
    assert best_scores is not None
    rosters = tuple(incumbents[int(index)] for index in best_roster_ordinals)
    best_scores.flags.writeable = False
    return best_scores, rosters


def _candidate_pool(
    players: tuple[rw.PlayerSpec, ...],
    values: np.ndarray,
    dose: FeasibleCoreDose,
) -> dict[str, tuple[int, ...]]:
    limits = dict(dose.top_by_position)
    result: dict[str, tuple[int, ...]] = {}
    for position in POSITIONS:
        rows = [
            index for index, player in enumerate(players)
            if player.position == position
        ]
        top = sorted(rows, key=lambda row: (-int(values[row]), players[row].player_id))[
            :limits[position]
        ]
        cheapest = sorted(
            rows, key=lambda row: (players[row].salary, players[row].player_id)
        )[:dose.cheapest_per_position]
        selected = set(top) | set(cheapest)
        result[position] = tuple(sorted(selected))
    return result


def _rank_combinations(
    choices: Sequence[int],
    count: int,
    values: np.ndarray,
    players: tuple[rw.PlayerSpec, ...],
    limit: int,
    work: _WorldWork,
    dose: FeasibleCoreDose,
) -> tuple[tuple[int, ...], ...]:
    if count == 0:
        if work.combination_candidates >= dose.max_combination_candidates:
            return ()
        work.combination_candidates += 1
        return ((),)
    if len(choices) < count:
        return ()
    materialized: list[tuple[int, ...]] = []
    for rows in combinations(sorted(choices), count):
        if work.combination_candidates >= dose.max_combination_candidates:
            break
        work.combination_candidates += 1
        materialized.append(rows)
    ranked = sorted(
        materialized,
        key=lambda rows: (
            -sum(int(values[row]) for row in rows),
            tuple(players[row].player_id for row in rows),
        ),
    )
    return tuple(ranked[:limit])


def _partial_allowed(
    players: tuple[rw.PlayerSpec, ...],
    rows: tuple[int, ...],
    profile: legal.EffectivePolicyProfile,
    salary_cap: int,
) -> bool:
    chosen = [players[row] for row in rows]
    if sum(player.salary for player in chosen) > salary_cap:
        return False
    if chosen and max(Counter(player.team for player in chosen).values()) > rw.MAX_FROM_TEAM:
        return False
    if bool(profile.value("forbid_two_rb_same_team")):
        rb_teams = [player.team for player in chosen if player.position == "RB"]
        if len(rb_teams) != len(set(rb_teams)):
            return False
    if bool(profile.value("forbid_rb_vs_dst")):
        dsts = [player for player in chosen if player.position == "DST"]
        rbs = [player for player in chosen if player.position == "RB"]
        if any(rb.team == dst.opponent for rb in rbs for dst in dsts):
            return False
    return True


def _structural_cores(
    players: tuple[rw.PlayerSpec, ...],
    values: np.ndarray,
    pool: Mapping[str, tuple[int, ...]],
    profile: legal.EffectivePolicyProfile,
    dose: FeasibleCoreDose,
    salary_cap: int,
    work: _WorldWork,
) -> tuple[tuple[int, ...], ...]:
    qb_stack_min = _strict_int(
        profile.value("qb_stack_min"), label="QB stack minimum", minimum=0
    )
    bring_back_min = _strict_int(
        profile.value("bring_back_min"), label="bring-back minimum", minimum=0
    )
    skill_rows = tuple(sorted((*pool["RB"], *pool["WR"], *pool["TE"])))
    catcher_rows = tuple(sorted((*pool["WR"], *pool["TE"])))
    candidates: set[tuple[int, ...]] = set()
    for qb_row in sorted(pool["QB"]):
        qb = players[qb_row]
        same_team = tuple(
            row for row in catcher_rows if players[row].team == qb.team
        )
        bring_backs = tuple(
            row for row in skill_rows if players[row].team == qb.opponent
        )
        same_sets = _rank_combinations(
            same_team,
            qb_stack_min,
            values,
            players,
            dose.max_cores,
            work,
            dose,
        )
        back_sets = _rank_combinations(
            bring_backs,
            bring_back_min,
            values,
            players,
            dose.max_cores,
            work,
            dose,
        )
        exhausted = False
        for same_rows in same_sets:
            for back_rows in back_sets:
                if work.core_candidates >= dose.max_core_candidates:
                    exhausted = True
                    break
                work.core_candidates += 1
                core_rows = tuple(sorted((qb_row, *same_rows, *back_rows)))
                if (
                    len(set(core_rows)) == len(core_rows)
                    and _partial_allowed(
                        players, core_rows, profile, salary_cap
                    )
                ):
                    candidates.add(core_rows)
            if exhausted:
                break
        if exhausted:
            break
    return tuple(sorted(
        candidates,
        key=lambda rows: (
            -sum(int(values[row]) for row in rows),
            tuple(players[row].player_id for row in rows),
        ),
    )[:dose.max_cores])


def _state_key(
    state: _BeamState, players: tuple[rw.PlayerSpec, ...],
) -> tuple[object, ...]:
    return (
        -state.score_micro,
        tuple(players[row].player_id for row in state.rows),
    )


def _remaining_slots(
    players: tuple[rw.PlayerSpec, ...],
    core_rows: tuple[int, ...],
    pattern: tuple[int, int, int],
) -> tuple[str, ...] | None:
    rb_count, wr_count, te_count = pattern
    target = {"QB": 1, "RB": rb_count, "WR": wr_count, "TE": te_count, "DST": 1}
    present = Counter(players[row].position for row in core_rows)
    if any(present[position] > target[position] for position in POSITIONS):
        return None
    slots: list[str] = []
    for position in ("DST", "RB", "WR", "TE"):
        slots.extend([position] * (target[position] - present[position]))
    return tuple(slots)


def _bounded_world_search(
    players: tuple[rw.PlayerSpec, ...],
    values: np.ndarray,
    profile: legal.EffectivePolicyProfile,
    dose: FeasibleCoreDose,
    sentinel_score: int,
    sentinel_roster: tuple[str, ...],
) -> tuple[int, tuple[str, ...], _WorldWork]:
    _, salary_cap = _profile_salary_interval(profile)
    work = _WorldWork()
    pool = _candidate_pool(players, values, dose)
    cores = _structural_cores(
        players, values, pool, profile, dose, salary_cap, work
    )
    best_score = int(sentinel_score)
    best_roster = sentinel_roster
    exhausted = False

    for core_rows in cores:
        if exhausted:
            break
        core = _BeamState(
            rows=core_rows,
            score_micro=sum(int(values[row]) for row in core_rows),
            salary=sum(players[row].salary for row in core_rows),
        )
        for pattern in rw.CLASSIC_SKILL_PATTERNS:
            if exhausted:
                break
            slots = _remaining_slots(players, core_rows, pattern)
            if slots is None:
                continue
            states = (core,)
            completed = not slots
            for slot_ordinal, position in enumerate(slots):
                next_by_rows: dict[tuple[int, ...], _BeamState] = {}
                for state in states:
                    same_position = [
                        row for row in state.rows
                        if players[row].position == position
                    ]
                    after_row = max(same_position, default=-1)
                    for row in pool[position]:
                        if work.state_expansions >= dose.max_state_expansions:
                            exhausted = True
                            break
                        work.state_expansions += 1
                        if row in state.rows or row <= after_row:
                            continue
                        candidate_rows = tuple(sorted((*state.rows, row)))
                        if not _partial_allowed(
                            players, candidate_rows, profile, salary_cap
                        ):
                            continue
                        candidate = _BeamState(
                            rows=candidate_rows,
                            score_micro=state.score_micro + int(values[row]),
                            salary=state.salary + players[row].salary,
                        )
                        previous = next_by_rows.get(candidate_rows)
                        if previous is None or _state_key(candidate, players) < _state_key(
                            previous, players
                        ):
                            next_by_rows[candidate_rows] = candidate
                    if exhausted:
                        break
                states = tuple(sorted(
                    next_by_rows.values(), key=lambda state: _state_key(state, players)
                )[:dose.beam_width])
                completed = slot_ordinal == len(slots) - 1 and bool(states)
                if not states or exhausted:
                    break
            if completed:
                for state in states:
                    roster = tuple(sorted(players[row].player_id for row in state.rows))
                    if not _profile_legal(players, roster, profile):
                        continue
                    if (
                        state.score_micro > best_score
                        or (
                            state.score_micro == best_score
                            and roster < best_roster
                        )
                    ):
                        best_score = state.score_micro
                        best_roster = roster
    return best_score, best_roster, work


def bounded_feasible_core_lower_bounds_micro(
    player_scores_micro: np.ndarray,
    players: Sequence[rw.PlayerSpec],
    profile: legal.EffectivePolicyProfile,
    incumbent_candidates: Sequence[Sequence[object]],
    *,
    dose: FeasibleCoreDose = DEFAULT_FEASIBLE_CORE_DOSE,
) -> FeasibleCoreBatch:
    """Return legal attainable lower bounds under deterministic work caps."""
    frozen_profile = _validate_profile(profile)
    if not isinstance(dose, FeasibleCoreDose):
        raise CorpusR6LegalSchedulerError("feasible-core dose type differs")
    dose_receipt = dose.receipt()
    validate_dose_receipt(dose_receipt)
    rows, scores = _canonical_players_and_scores(players, player_scores_micro)
    if scores.shape[1] > MAX_WORLDS_PER_BATCH:
        raise CorpusR6LegalSchedulerError(
            "feasible-core world count exceeds its hard batch maximum"
        )
    incumbents = _canonical_incumbents(
        rows, incumbent_candidates, frozen_profile, dose
    )
    sentinel_scores, sentinel_rosters = _incumbent_sentinels(
        rows, scores, incumbents
    )
    lower_bounds: list[int] = []
    rosters: list[tuple[str, ...]] = []
    expansions: list[int] = []
    combination_counts: list[int] = []
    core_counts: list[int] = []
    for world in range(scores.shape[1]):
        value, roster, work = _bounded_world_search(
            rows,
            scores[:, world],
            frozen_profile,
            dose,
            int(sentinel_scores[world]),
            sentinel_rosters[world],
        )
        if value < int(sentinel_scores[world]):
            raise CorpusR6LegalSchedulerError("feasible-core fell below its sentinel")
        if work.state_expansions > dose.max_state_expansions:
            raise CorpusR6LegalSchedulerError("feasible-core exceeded its work cap")
        if work.combination_candidates > dose.max_combination_candidates:
            raise CorpusR6LegalSchedulerError(
                "feasible-core exceeded its combination cap"
            )
        if work.core_candidates > dose.max_core_candidates:
            raise CorpusR6LegalSchedulerError("feasible-core exceeded its core cap")
        if not _profile_legal(rows, roster, frozen_profile):
            raise CorpusR6LegalSchedulerError("feasible-core witness is not legal")
        row_by_id = {player.player_id: index for index, player in enumerate(rows)}
        replayed = sum(int(scores[row_by_id[player_id], world]) for player_id in roster)
        if replayed != value:
            raise CorpusR6LegalSchedulerError("feasible-core witness score differs")
        lower_bounds.append(value)
        rosters.append(roster)
        expansions.append(work.state_expansions)
        combination_counts.append(work.combination_candidates)
        core_counts.append(work.core_candidates)
    return FeasibleCoreBatch(
        lower_bounds_micro=tuple(lower_bounds),
        rosters=tuple(rosters),
        state_expansions=tuple(expansions),
        combination_candidates_considered=tuple(combination_counts),
        core_candidates_considered=tuple(core_counts),
        incumbent_sentinel_scores_micro=tuple(
            int(value) for value in sentinel_scores
        ),
        incumbent_sentinel_rosters=sentinel_rosters,
        incumbent_candidates_evaluated=len(incumbents),
        incumbent_score_cells_evaluated=len(incumbents) * scores.shape[1],
        dose_receipt=dose_receipt,
    )


def _catalog_payload(players: Sequence[rw.PlayerSpec]) -> list[dict[str, object]]:
    rows = tuple(sorted(players, key=lambda player: player.player_id))
    if not rows or len({player.player_id for player in rows}) != len(rows):
        raise CorpusR6LegalSchedulerError("receipt player catalog is malformed")
    return [{
        "player_id": player.player_id,
        "position": player.position,
        "team": player.team,
        "opponent": player.opponent,
        "game_id": player.game_id,
        "salary": player.salary,
    } for player in rows]


def _score_vector_sha256(values: Sequence[object] | np.ndarray) -> str:
    scores = _micro_vector(values)
    return _canonical_sha256({
        "dtype": "<i8",
        "shape": [len(scores)],
        "values_sha256": sha256(
            scores.astype("<i8", copy=False).tobytes()
        ).hexdigest(),
    })


def _producer_identity_sha256(producer: ProducerIdentity) -> str:
    if not isinstance(producer, ProducerIdentity):
        raise CorpusR6LegalSchedulerError("producer identity type differs")
    return _canonical_sha256(producer.as_payload())


def build_proxy_input_binding(
    *,
    players: Sequence[rw.PlayerSpec],
    player_scores_micro: np.ndarray,
    ordered_world_ids: Sequence[rw.WorldId],
    source_artifact: SourceArtifactIdentity,
) -> ProxyInputBinding:
    """Hash-bind a source claim, catalog, matrix bytes and ordered world IDs."""
    if not isinstance(source_artifact, SourceArtifactIdentity):
        raise CorpusR6LegalSchedulerError("source artifact identity type differs")
    rows, scores = _canonical_players_and_scores(players, player_scores_micro)
    worlds = tuple(ordered_world_ids)
    if (
        len(worlds) != scores.shape[1]
        or not worlds
        or len(worlds) > MAX_WORLDS_PER_BATCH
        or any(not isinstance(world, rw.WorldId) for world in worlds)
        or len(set(worlds)) != len(worlds)
    ):
        raise CorpusR6LegalSchedulerError(
            "ordered world IDs do not bind one unique bounded matrix batch"
        )
    world_payload = [
        {"block": world.block, "index": world.index} for world in worlds
    ]
    schedule_sha = _canonical_sha256(world_payload)
    catalog_sha = _canonical_sha256(_catalog_payload(rows))
    matrix_sha = _canonical_sha256({
        "dtype": "<i8",
        "shape": [scores.shape[0], scores.shape[1]],
        "values_sha256": sha256(
            scores.astype("<i8", copy=False).tobytes(order="C")
        ).hexdigest(),
    })
    body = {
        "source_artifact": source_artifact.as_payload(),
        "ordered_world_ids": world_payload,
        "world_schedule_sha256": schedule_sha,
        "player_catalog_sha256": catalog_sha,
        "player_score_matrix_sha256": matrix_sha,
    }
    binding_sha = _canonical_sha256(body)
    return ProxyInputBinding(
        source_artifact=source_artifact,
        ordered_world_ids=worlds,
        world_schedule_sha256=schedule_sha,
        player_catalog_sha256=catalog_sha,
        player_score_matrix_sha256=matrix_sha,
        binding_sha256=binding_sha,
    )


def _position_result_body(
    *,
    profile: legal.EffectivePolicyProfile,
    dose_receipt: DoseReceipt,
    input_binding: ProxyInputBinding,
    producer_identity: ProducerIdentity,
    upper_bounds_micro: Sequence[object] | np.ndarray,
) -> dict[str, object]:
    return {
        "result_kind": "position-salary-upper-bound-result-v1",
        "profile_payload_sha256": _canonical_sha256(profile.as_payload()),
        "dose_sha256": dose_receipt.dose_sha256,
        "input_binding_sha256": input_binding.binding_sha256,
        "producer_identity_sha256": _producer_identity_sha256(producer_identity),
        "upper_bounds_micro_sha256": _score_vector_sha256(upper_bounds_micro),
    }


def produce_position_salary_proxy(
    *,
    player_scores_micro: np.ndarray,
    players: Sequence[rw.PlayerSpec],
    ordered_world_ids: Sequence[rw.WorldId],
    profile: legal.EffectivePolicyProfile,
    source_artifact: SourceArtifactIdentity,
    producer_identity: ProducerIdentity,
    dose: SalaryPositionDose = DEFAULT_SALARY_POSITION_DOSE,
) -> PositionSalaryProxyResult:
    """Compute one typed, non-authoritative offline upper-bound result."""
    frozen_profile = _validate_profile(profile)
    if (
        not isinstance(producer_identity, ProducerIdentity)
        or producer_identity.proxy_id != POSITION_SALARY_PROXY_ID
    ):
        raise CorpusR6LegalSchedulerError(
            "position/salary producer identity differs"
        )
    bounds = position_salary_upper_bounds_micro(
        player_scores_micro, players, frozen_profile, dose=dose
    )
    binding = build_proxy_input_binding(
        players=players,
        player_scores_micro=player_scores_micro,
        ordered_world_ids=ordered_world_ids,
        source_artifact=source_artifact,
    )
    dose_receipt = dose.receipt()
    body = _position_result_body(
        profile=frozen_profile,
        dose_receipt=dose_receipt,
        input_binding=binding,
        producer_identity=producer_identity,
        upper_bounds_micro=bounds,
    )
    return PositionSalaryProxyResult(
        profile=frozen_profile,
        dose=dose,
        dose_receipt=dose_receipt,
        input_binding=binding,
        producer_identity=producer_identity,
        upper_bounds_micro=tuple(int(value) for value in bounds),
        result_sha256=_canonical_sha256(body),
    )


def _feasible_batch_payload(batch: FeasibleCoreBatch) -> dict[str, object]:
    return {
        "lower_bounds_micro": list(batch.lower_bounds_micro),
        "witness_rosters": [list(roster) for roster in batch.rosters],
        "state_expansions": list(batch.state_expansions),
        "combination_candidates_considered": list(
            batch.combination_candidates_considered
        ),
        "core_candidates_considered": list(batch.core_candidates_considered),
        "incumbent_sentinel_scores_micro": list(
            batch.incumbent_sentinel_scores_micro
        ),
        "incumbent_sentinel_rosters": [
            list(roster) for roster in batch.incumbent_sentinel_rosters
        ],
        "incumbent_candidates_evaluated": batch.incumbent_candidates_evaluated,
        "incumbent_score_cells_evaluated": (
            batch.incumbent_score_cells_evaluated
        ),
        "dose_sha256": batch.dose_receipt.dose_sha256,
    }


def _feasible_result_body(
    *,
    profile: legal.EffectivePolicyProfile,
    dose: FeasibleCoreDose,
    input_binding: ProxyInputBinding,
    producer_identity: ProducerIdentity,
    incumbent_candidates: tuple[tuple[str, ...], ...],
    batch: FeasibleCoreBatch,
) -> dict[str, object]:
    return {
        "result_kind": "bounded-feasible-core-result-v1",
        "profile_payload_sha256": _canonical_sha256(profile.as_payload()),
        "dose_sha256": dose.receipt().dose_sha256,
        "input_binding_sha256": input_binding.binding_sha256,
        "producer_identity_sha256": _producer_identity_sha256(producer_identity),
        "incumbent_candidates_sha256": _canonical_sha256([
            list(roster) for roster in incumbent_candidates
        ]),
        "batch_sha256": _canonical_sha256(_feasible_batch_payload(batch)),
    }


def produce_feasible_core_proxy(
    *,
    player_scores_micro: np.ndarray,
    players: Sequence[rw.PlayerSpec],
    ordered_world_ids: Sequence[rw.WorldId],
    profile: legal.EffectivePolicyProfile,
    incumbent_candidates: Sequence[Sequence[object]],
    source_artifact: SourceArtifactIdentity,
    producer_identity: ProducerIdentity,
    dose: FeasibleCoreDose = DEFAULT_FEASIBLE_CORE_DOSE,
) -> FeasibleCoreProxyResult:
    """Compute one typed, non-authoritative offline feasible-core result."""
    frozen_profile = _validate_profile(profile)
    if (
        not isinstance(producer_identity, ProducerIdentity)
        or producer_identity.proxy_id != FEASIBLE_CORE_PROXY_ID
    ):
        raise CorpusR6LegalSchedulerError("feasible-core producer identity differs")
    rows, _ = _canonical_players_and_scores(players, player_scores_micro)
    canonical_incumbents = _canonical_incumbents(
        rows, incumbent_candidates, frozen_profile, dose
    )
    batch = bounded_feasible_core_lower_bounds_micro(
        player_scores_micro,
        players,
        frozen_profile,
        canonical_incumbents,
        dose=dose,
    )
    binding = build_proxy_input_binding(
        players=players,
        player_scores_micro=player_scores_micro,
        ordered_world_ids=ordered_world_ids,
        source_artifact=source_artifact,
    )
    body = _feasible_result_body(
        profile=frozen_profile,
        dose=dose,
        input_binding=binding,
        producer_identity=producer_identity,
        incumbent_candidates=canonical_incumbents,
        batch=batch,
    )
    return FeasibleCoreProxyResult(
        profile=frozen_profile,
        dose=dose,
        input_binding=binding,
        producer_identity=producer_identity,
        incumbent_candidates=canonical_incumbents,
        batch=batch,
        result_sha256=_canonical_sha256(body),
    )


def _result_receipt_evidence(result: TypedProxyResult) -> dict[str, object]:
    if isinstance(result, PositionSalaryProxyResult):
        return {
            "result_kind": "position-salary-upper-bound-result-v1",
            "result_sha256": result.result_sha256,
            "upper_bounds_micro_sha256": _score_vector_sha256(
                result.upper_bounds_micro
            ),
        }
    if isinstance(result, FeasibleCoreProxyResult):
        batch = result.batch
        return {
            "result_kind": "bounded-feasible-core-result-v1",
            "result_sha256": result.result_sha256,
            "batch_sha256": _canonical_sha256(_feasible_batch_payload(batch)),
            "witness_rosters_sha256": _canonical_sha256([
                list(roster) for roster in batch.rosters
            ]),
            "incumbent_sentinel_sha256": _canonical_sha256({
                "scores_micro": list(batch.incumbent_sentinel_scores_micro),
                "rosters": [
                    list(roster) for roster in batch.incumbent_sentinel_rosters
                ],
            }),
            "work_receipt_sha256": _canonical_sha256({
                "state_expansions": list(batch.state_expansions),
                "combination_candidates_considered": list(
                    batch.combination_candidates_considered
                ),
                "core_candidates_considered": list(
                    batch.core_candidates_considered
                ),
                "incumbent_candidates_evaluated": (
                    batch.incumbent_candidates_evaluated
                ),
                "incumbent_score_cells_evaluated": (
                    batch.incumbent_score_cells_evaluated
                ),
            }),
        }
    raise CorpusR6LegalSchedulerError("proxy result type is unsupported")


def _replay_typed_proxy_result(
    result: TypedProxyResult,
    *,
    players: Sequence[rw.PlayerSpec],
    player_scores_micro: np.ndarray,
    ordered_world_ids: Sequence[rw.WorldId],
) -> TypedProxyResult:
    """Recompute one typed result from the exact raw inputs before serialization."""
    try:
        if isinstance(result, PositionSalaryProxyResult):
            replayed: TypedProxyResult = produce_position_salary_proxy(
                player_scores_micro=player_scores_micro,
                players=players,
                ordered_world_ids=ordered_world_ids,
                profile=result.profile,
                source_artifact=result.input_binding.source_artifact,
                producer_identity=result.producer_identity,
                dose=result.dose,
            )
        elif isinstance(result, FeasibleCoreProxyResult):
            replayed = produce_feasible_core_proxy(
                player_scores_micro=player_scores_micro,
                players=players,
                ordered_world_ids=ordered_world_ids,
                profile=result.profile,
                incumbent_candidates=result.incumbent_candidates,
                source_artifact=result.input_binding.source_artifact,
                producer_identity=result.producer_identity,
                dose=result.dose,
            )
        else:
            raise CorpusR6LegalSchedulerError("proxy result type is unsupported")
        differs = result != replayed
        if isinstance(differs, (bool, np.bool_)) and bool(differs):
            raise CorpusR6LegalSchedulerError("typed producer result replay differs")
        if not isinstance(differs, (bool, np.bool_)):
            raise CorpusR6LegalSchedulerError(
                "typed producer result equality is malformed"
            )
    except CorpusR6LegalSchedulerError:
        raise
    except (AttributeError, TypeError, ValueError) as exc:
        raise CorpusR6LegalSchedulerError(
            "typed producer result cannot be replayed"
        ) from exc
    return replayed


def _serialize_offline_proxy_receipt(
    result: TypedProxyResult,
    *,
    selected_count: int,
) -> ProxyReceipt:
    """Serialize a result already proven equal to an exact raw-input replay."""
    if isinstance(result, PositionSalaryProxyResult):
        proxy = POSITION_SALARY_PROXY_ID
        scores = _micro_vector(result.upper_bounds_micro)
        dose_receipt = result.dose_receipt
    elif isinstance(result, FeasibleCoreProxyResult):
        proxy = FEASIBLE_CORE_PROXY_ID
        scores = _micro_vector(result.batch.lower_bounds_micro)
        dose_receipt = result.batch.dose_receipt
    else:
        raise CorpusR6LegalSchedulerError("proxy result type is unsupported")
    validate_dose_receipt(dose_receipt)
    frozen_profile = _validate_profile(result.profile)
    if result.producer_identity.proxy_id != proxy or dose_receipt.proxy_id != proxy:
        raise CorpusR6LegalSchedulerError("typed result proxy identities differ")
    if len(scores) != len(result.input_binding.ordered_world_ids):
        raise CorpusR6LegalSchedulerError("typed result world coverage differs")
    selected = stable_rank_micro(scores, selected_count)
    profile_sha = _canonical_sha256(frozen_profile.as_payload())
    producer_sha = _producer_identity_sha256(result.producer_identity)
    result_evidence = _result_receipt_evidence(result)
    body: dict[str, object] = {
        "schema": PROXY_RECEIPT_SCHEMA,
        "proxy_id": proxy,
        "proxy_version": PROXY_VERSION,
        "profile_id": frozen_profile.parameter_set_id,
        "profile_payload_sha256": profile_sha,
        "dose_sha256": dose_receipt.dose_sha256,
        "input_binding": result.input_binding.as_payload(),
        "producer_identity": result.producer_identity.as_payload(),
        "producer_result": result_evidence,
        "score_vector_sha256": _score_vector_sha256(scores),
        "world_count": len(scores),
        "selected_count": len(selected),
        "selected_indices": list(selected),
        "world_tie_break": WORLD_TIE_BREAK,
        "authority": _offline_authority_payload(),
        "accepted_input_contract": (
            "PlayerSpec-plus-signed-int64-micro-DK-matrix-plus-WorldId-only"
        ),
    }
    receipt_sha = _canonical_sha256(body)
    payload = _canonical_json_bytes({**body, "receipt_sha256": receipt_sha})
    binding = result.input_binding
    return ProxyReceipt(
        proxy_id=proxy,
        proxy_version=PROXY_VERSION,
        profile_id=frozen_profile.parameter_set_id,
        profile_payload_sha256=profile_sha,
        dose_sha256=dose_receipt.dose_sha256,
        source_artifact_sha256=binding.source_artifact.sha256,
        input_binding_sha256=binding.binding_sha256,
        producer_identity_sha256=producer_sha,
        producer_result_sha256=result.result_sha256,
        player_catalog_sha256=binding.player_catalog_sha256,
        player_score_matrix_sha256=binding.player_score_matrix_sha256,
        world_schedule_sha256=binding.world_schedule_sha256,
        score_vector_sha256=_score_vector_sha256(scores),
        selected_indices=selected,
        authoritative=False,
        outer_exact_read_pinned_authority_required=(
            OUTER_EXACT_READ_PINNED_AUTHORITY_REQUIRED
        ),
        outer_cumulative_batch_run_budget_required=(
            OUTER_CUMULATIVE_BATCH_RUN_BUDGET_REQUIRED
        ),
        canonical_payload=payload,
        receipt_sha256=receipt_sha,
    )


def build_proxy_receipt(
    result: TypedProxyResult,
    *,
    players: Sequence[rw.PlayerSpec],
    player_scores_micro: np.ndarray,
    ordered_world_ids: Sequence[rw.WorldId],
    selected_count: int,
) -> ProxyReceipt:
    """Replay exact raw inputs, then emit a non-authoritative offline receipt.

    Identity fields remain typed claims.  Production admission requires the
    outer exact-read/pinned-authority and cumulative-budget wrapper declared in
    the receipt; this function cannot promote its output to authority.
    """
    replayed = _replay_typed_proxy_result(
        result,
        players=players,
        player_scores_micro=player_scores_micro,
        ordered_world_ids=ordered_world_ids,
    )
    return _serialize_offline_proxy_receipt(
        replayed,
        selected_count=selected_count,
    )


def _source_identity_from_payload(value: object) -> SourceArtifactIdentity:
    if not isinstance(value, dict):
        raise CorpusR6LegalSchedulerError("source artifact payload is not an object")
    _exact_keys(
        value,
        frozenset({
            "uri", "generation", "byte_count", "sha256",
            "scientific_contract_sha256",
        }),
        label="source artifact",
    )
    return SourceArtifactIdentity(
        uri=value["uri"],
        generation=value["generation"],
        byte_count=value["byte_count"],
        sha256=value["sha256"],
        scientific_contract_sha256=value["scientific_contract_sha256"],
    )


def _producer_identity_from_payload(value: object) -> ProducerIdentity:
    if not isinstance(value, dict):
        raise CorpusR6LegalSchedulerError("producer payload is not an object")
    _exact_keys(
        value,
        frozenset({"proxy_id", "code_sha256", "image_digest"}),
        label="producer identity",
    )
    return ProducerIdentity(
        proxy_id=value["proxy_id"],
        code_sha256=value["code_sha256"],
        image_digest=value["image_digest"],
    )


def _validate_input_binding_payload(
    value: object,
    *,
    expected: ProxyInputBinding,
) -> None:
    if not isinstance(value, dict):
        raise CorpusR6LegalSchedulerError("input binding is not an object")
    _exact_keys(
        value,
        frozenset({
            "source_artifact", "ordered_world_ids", "world_schedule_sha256",
            "player_catalog_sha256", "player_score_matrix_sha256",
            "binding_sha256",
        }),
        label="input binding",
    )
    source = _source_identity_from_payload(value["source_artifact"])
    raw_worlds = value["ordered_world_ids"]
    if not isinstance(raw_worlds, list) or not raw_worlds:
        raise CorpusR6LegalSchedulerError("ordered world IDs are malformed")
    worlds: list[rw.WorldId] = []
    for raw_world in raw_worlds:
        if not isinstance(raw_world, dict):
            raise CorpusR6LegalSchedulerError("ordered world ID is not an object")
        _exact_keys(
            raw_world, frozenset({"block", "index"}), label="ordered world ID"
        )
        try:
            worlds.append(rw.WorldId(raw_world["block"], raw_world["index"]))
        except (rw.ResidualWorldError, TypeError, ValueError) as exc:
            raise CorpusR6LegalSchedulerError("ordered world ID is invalid") from exc
    for key in (
        "world_schedule_sha256",
        "player_catalog_sha256",
        "player_score_matrix_sha256",
        "binding_sha256",
    ):
        _strict_sha(value[key], label=key)
    reconstructed_body = dict(value)
    reconstructed_body.pop("binding_sha256")
    if (
        source != expected.source_artifact
        or tuple(worlds) != expected.ordered_world_ids
        or value != expected.as_payload()
        or _canonical_sha256(reconstructed_body) != value["binding_sha256"]
    ):
        raise CorpusR6LegalSchedulerError("input binding replay differs")


def validate_proxy_receipt(
    receipt: ProxyReceipt,
    result: TypedProxyResult,
    *,
    players: Sequence[rw.PlayerSpec],
    player_scores_micro: np.ndarray,
    ordered_world_ids: Sequence[rw.WorldId],
) -> None:
    """Exact-schema replay an offline receipt; this does not verify its claims."""
    if not isinstance(receipt, ProxyReceipt):
        raise CorpusR6LegalSchedulerError("proxy receipt type differs")
    try:
        payload = json.loads(receipt.canonical_payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CorpusR6LegalSchedulerError("proxy receipt payload is unreadable") from exc
    if not isinstance(payload, dict):
        raise CorpusR6LegalSchedulerError("proxy receipt payload is not an object")
    _exact_keys(
        payload,
        frozenset({
            "schema", "proxy_id", "proxy_version", "profile_id",
            "profile_payload_sha256", "dose_sha256", "input_binding",
            "producer_identity", "producer_result", "score_vector_sha256",
            "world_count", "selected_count", "selected_indices",
            "world_tie_break", "authority", "accepted_input_contract",
            "receipt_sha256",
        }),
        label="proxy receipt",
    )
    proxy = _strict_string(payload["proxy_id"], label="proxy id")
    if proxy not in SUPPORTED_PROXY_IDS:
        raise CorpusR6LegalSchedulerError("proxy id is unsupported")
    if (
        payload["schema"] != PROXY_RECEIPT_SCHEMA
        or payload["proxy_version"] != PROXY_VERSION
    ):
        raise CorpusR6LegalSchedulerError("proxy receipt schema/version differs")
    if (
        payload["world_tie_break"] != WORLD_TIE_BREAK
        or payload["accepted_input_contract"]
        != "PlayerSpec-plus-signed-int64-micro-DK-matrix-plus-WorldId-only"
    ):
        raise CorpusR6LegalSchedulerError("proxy receipt execution law differs")
    authority = payload["authority"]
    expected_authority = _offline_authority_payload()
    if not isinstance(authority, dict):
        raise CorpusR6LegalSchedulerError("offline authority flags are malformed")
    _exact_keys(
        authority, frozenset(expected_authority), label="offline authority flags"
    )
    if authority != expected_authority:
        raise CorpusR6LegalSchedulerError("offline authority flags differ")
    for key in (
        "profile_payload_sha256", "dose_sha256", "score_vector_sha256",
        "receipt_sha256",
    ):
        _strict_sha(payload[key], label=key)
    world_count = _strict_int(
        payload["world_count"], label="world count", minimum=1
    )
    selected_count = _strict_int(
        payload["selected_count"], label="selected count", minimum=1
    )
    raw_selected = payload["selected_indices"]
    if not isinstance(raw_selected, list):
        raise CorpusR6LegalSchedulerError("selected indices are not a list")
    selected = tuple(
        _strict_int(value, label="selected world index", minimum=0)
        for value in raw_selected
    )
    if (
        selected_count != len(selected)
        or selected_count > world_count
        or len(set(selected)) != len(selected)
        or any(index >= world_count for index in selected)
    ):
        raise CorpusR6LegalSchedulerError("selected index dose/range differs")

    replayed = _replay_typed_proxy_result(
        result,
        players=players,
        player_scores_micro=player_scores_micro,
        ordered_world_ids=ordered_world_ids,
    )
    if isinstance(replayed, PositionSalaryProxyResult):
        expected_proxy = POSITION_SALARY_PROXY_ID
        scores = replayed.upper_bounds_micro
        dose_receipt = replayed.dose_receipt
    elif isinstance(replayed, FeasibleCoreProxyResult):
        expected_proxy = FEASIBLE_CORE_PROXY_ID
        scores = replayed.batch.lower_bounds_micro
        dose_receipt = replayed.batch.dose_receipt
    else:
        raise CorpusR6LegalSchedulerError("proxy result type is unsupported")
    if proxy != expected_proxy:
        raise CorpusR6LegalSchedulerError("typed producer proxy differs")
    validate_dose_receipt(dose_receipt)
    rebuilt_binding = build_proxy_input_binding(
        players=players,
        player_scores_micro=player_scores_micro,
        ordered_world_ids=ordered_world_ids,
        source_artifact=replayed.input_binding.source_artifact,
    )
    if rebuilt_binding != replayed.input_binding:
        raise CorpusR6LegalSchedulerError("receipt input matrix replay differs")
    _validate_input_binding_payload(
        payload["input_binding"], expected=rebuilt_binding
    )
    producer = _producer_identity_from_payload(payload["producer_identity"])
    if producer != replayed.producer_identity:
        raise CorpusR6LegalSchedulerError("producer identity replay differs")
    evidence = payload["producer_result"]
    expected_evidence = _result_receipt_evidence(replayed)
    if not isinstance(evidence, dict):
        raise CorpusR6LegalSchedulerError("producer result evidence is malformed")
    _exact_keys(
        evidence, frozenset(expected_evidence), label="producer result evidence"
    )
    if evidence != expected_evidence:
        raise CorpusR6LegalSchedulerError("producer result evidence replay differs")
    frozen_profile = _validate_profile(result.profile)
    profile_sha = _canonical_sha256(frozen_profile.as_payload())
    expected_selected = stable_rank_micro(scores, selected_count)
    expected_fields = {
        "proxy_id": expected_proxy,
        "proxy_version": PROXY_VERSION,
        "profile_id": frozen_profile.parameter_set_id,
        "profile_payload_sha256": profile_sha,
        "dose_sha256": dose_receipt.dose_sha256,
        "source_artifact_sha256": rebuilt_binding.source_artifact.sha256,
        "input_binding_sha256": rebuilt_binding.binding_sha256,
        "producer_identity_sha256": _producer_identity_sha256(producer),
        "producer_result_sha256": replayed.result_sha256,
        "player_catalog_sha256": rebuilt_binding.player_catalog_sha256,
        "player_score_matrix_sha256": rebuilt_binding.player_score_matrix_sha256,
        "world_schedule_sha256": rebuilt_binding.world_schedule_sha256,
        "score_vector_sha256": _score_vector_sha256(scores),
        "selected_indices": expected_selected,
        "authoritative": False,
        "outer_exact_read_pinned_authority_required": (
            OUTER_EXACT_READ_PINNED_AUTHORITY_REQUIRED
        ),
        "outer_cumulative_batch_run_budget_required": (
            OUTER_CUMULATIVE_BATCH_RUN_BUDGET_REQUIRED
        ),
        "receipt_sha256": payload["receipt_sha256"],
    }
    if any(getattr(receipt, key) != value for key, value in expected_fields.items()):
        raise CorpusR6LegalSchedulerError("proxy receipt typed fields differ")
    if (
        world_count != len(scores)
        or selected != expected_selected
        or payload["profile_id"] != frozen_profile.parameter_set_id
        or payload["profile_payload_sha256"] != profile_sha
        or payload["dose_sha256"] != dose_receipt.dose_sha256
        or payload["score_vector_sha256"] != _score_vector_sha256(scores)
    ):
        raise CorpusR6LegalSchedulerError("proxy receipt scientific replay differs")
    body = dict(payload)
    body.pop("receipt_sha256")
    if (
        _canonical_sha256(body) != receipt.receipt_sha256
        or _canonical_json_bytes(payload) != receipt.canonical_payload
    ):
        raise CorpusR6LegalSchedulerError("proxy receipt hash/canonical bytes differ")


__all__ = [
    "CorpusR6LegalSchedulerError",
    "DEFAULT_FEASIBLE_CORE_DOSE",
    "DEFAULT_SALARY_POSITION_DOSE",
    "DoseReceipt",
    "FEASIBLE_CORE_PROXY_ID",
    "FeasibleCoreBatch",
    "FeasibleCoreDose",
    "FeasibleCoreProxyResult",
    "OFFLINE_AUTHORITY_SCOPE",
    "OUTER_CUMULATIVE_BATCH_RUN_BUDGET_REQUIRED",
    "OUTER_EXACT_READ_PINNED_AUTHORITY_REQUIRED",
    "POSITION_SALARY_PROXY_ID",
    "PositionSalaryProxyResult",
    "ProducerIdentity",
    "PROXY_VERSION",
    "ProxyInputBinding",
    "ProxyReceipt",
    "SalaryPositionDose",
    "SourceArtifactIdentity",
    "audit_profile_roster",
    "bounded_feasible_core_lower_bounds_micro",
    "build_proxy_input_binding",
    "build_proxy_receipt",
    "position_salary_upper_bounds_micro",
    "produce_feasible_core_proxy",
    "produce_position_salary_proxy",
    "stable_rank_micro",
    "validate_dose_receipt",
    "validate_proxy_receipt",
]
