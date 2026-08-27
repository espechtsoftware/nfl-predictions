"""Pure, outcome-free contracts for Lane 2 player-belief world banks.

This module deliberately does not generate projections, query a warehouse, or
select historical lineups.  It binds an already generated player-by-world
matrix to an explicit target law and proposal, validates importance weights,
and registers the pre-2023 calibration/support-census boundary.

Candidate generation and belief probabilities are separate contracts.  In
particular, adaptation elites are never valid importance-sampling evaluation
worlds, even when a density ratio can be computed for the unconditioned
proposal that originally generated them.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
import json
import math
import re
from typing import Final

import numpy as np


BELIEF_WORLD_SCHEMA: Final = "lane2-belief-world-artifact/v1"
SAMPLING_DESIGN_SCHEMA: Final = "lane2-world-sampling-design/v1"
BASELINE_IDENTITY_SCHEMA: Final = "lane2-served-baseline-identity/v1"
FOLD_REGISTRY_SCHEMA: Final = "lane2-calibration-fold-registry/v1"
SUPPORT_CENSUS_SCHEMA: Final = "lane2-belief-support-census/v1"

SERVED_BASELINE_LAW_ID: Final = "served-baseline-v1"
DIRECT_SAMPLING_PROPOSAL_ID: Final = "direct-served-baseline-v1"
LINEUP_DEVELOPMENT_SEASONS: Final = (2023, 2024, 2025)
PRIMARY_EXCLUDED_SEASONS: Final = (2020,)

_IDENTIFIER: Final = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/@+-]*")
_SHA256: Final = re.compile(r"[0-9a-f]{64}")

# Only values that define the player-outcome distribution belong in the law
# identity.  Candidate generators and lineup selectors remain visible in the
# full policy receipt but cannot change this projection.
SERVED_BASELINE_LAW_ENV_KEYS: Final = (
    "MODEL_REGISTRY_VARIANT",
    "MODEL_ENSEMBLE",
    "BLEND_MODEL_WEIGHT",
    "LIVE_SIMS",
    "GAME_SIM_MODE",
    "GAME_SIM_PACE",
    "GAME_SIM_TEAM_FACTORS",
    "GAME_SIM_USAGE",
    "TD_LEDGER",
    "SIM_WIDEN_DRAWS",
    "ROOKIE_WIDEN",
    "TABPFN_MARGINALS",
    "TABPFN_MARGINAL_TABLE",
    "EMP_MARGINALS",
    "EMP_POS",
    "SHAPE_MIX",
    "SERVED_TAIL_SCALE",
    "SERVED_POSITION_SCALES",
    "DST_CORR_DRAWS",
)

_FORBIDDEN_CENSUS_FIELDS: Final = frozenset({
    "actual",
    "actual_points",
    "y_dk_points",
    "dk_points",
    "fantasy_points",
    "fantasy_points_ppr",
    "lineup_score",
    "selected_score",
    "winner_score",
    "payout",
    "roi",
    "winnings",
    "rank",
    "finish_position",
})

_SUPPORT_TABLES: Final = {
    "player": {
        "dimensions": ("week", "position"),
        "counts": (
            "player_rows",
            "active_rows",
            "salary_rows",
            "component_rows",
            "game_id_rows",
            "team_id_rows",
            "market_rows",
            "tabpfn_rows",
            "empirical_fallback_rows",
        ),
    },
    "role": {
        "dimensions": ("week", "position", "state", "previous_state"),
        "counts": (
            "transition_rows",
            "prelock_injury_rows",
            "emission_rows",
        ),
    },
    "dependence": {
        "dimensions": ("week", "pair_type"),
        "counts": ("pair_instances", "complete_game_instances"),
    },
    "usage": {
        "dimensions": ("week", "opportunity_kind"),
        "counts": (
            "team_groups",
            "player_rows",
            "prior_mean_positive_rows",
        ),
    },
    "rare_breakout": {
        "dimensions": ("week", "position", "archetype"),
        "counts": (
            "eligible_rows",
            "deep_target_context_rows",
            "base_rate_context_rows",
        ),
    },
    "matchup": {
        "dimensions": ("week", "position", "component"),
        "counts": ("source_rows", "candidate_rows"),
    },
}


class BeliefWorldError(ValueError):
    """A Lane 2 belief-world or support-boundary contract was violated."""


def canonical_json_bytes(value: object) -> bytes:
    """Canonical finite JSON used for every identity in this module."""
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BeliefWorldError("value is not canonical finite JSON") from exc


def canonical_sha256(value: object) -> str:
    return sha256(canonical_json_bytes(value)).hexdigest()


def _identifier(value: object, *, label: str) -> str:
    if type(value) is not str or _IDENTIFIER.fullmatch(value) is None:
        raise BeliefWorldError(f"{label} must be a canonical identifier")
    return value


def _canonical_ids(values: Sequence[object], *, label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise BeliefWorldError(f"{label} must be an ordered sequence")
    result = tuple(_identifier(value, label=f"{label} item") for value in values)
    if not result:
        raise BeliefWorldError(f"{label} cannot be empty")
    if len(set(result)) != len(result):
        raise BeliefWorldError(f"{label} contains duplicate identities")
    return result


def ordered_identity_sha256(values: Sequence[object], *, label: str) -> str:
    """Hash an exact ordered identity axis; reordering changes the digest."""
    return canonical_sha256(list(_canonical_ids(values, label=label)))


def player_world_matrix_sha256(draws: np.ndarray) -> str:
    """Canonical hash of a finite player-by-world matrix.

    A little-endian float64 representation prevents platform dtype and byte
    order from changing the binding.  The artifact remains a receipt rather
    than a second copy of the potentially large matrix.
    """
    values = np.asarray(draws, dtype=np.float64)
    if values.ndim != 2 or not values.size or not np.isfinite(values).all():
        raise BeliefWorldError("player-world draws must be a finite 2-D matrix")
    stable = np.ascontiguousarray(values, dtype=np.dtype("<f8"))
    header = canonical_json_bytes({
        "dtype": "<f8",
        "shape": [int(value) for value in stable.shape],
    })
    return sha256(header + b"\0" + stable.tobytes(order="C")).hexdigest()


def stable_logsumexp(values: np.ndarray, axis: int | None = None) -> np.ndarray:
    """Numerically stable log-sum-exp with explicit empty/support rejection."""
    array = np.asarray(values, dtype=np.float64)
    if not array.size or np.isnan(array).any() or np.isposinf(array).any():
        raise BeliefWorldError("log densities must be nonempty and not NaN/+inf")
    if axis is None:
        maximum = float(np.max(array))
        if math.isinf(maximum) and maximum < 0.0:
            raise BeliefWorldError("log-density support is empty")
        return np.asarray(
            maximum + math.log(float(np.exp(array - maximum).sum())),
            dtype=np.float64,
        )
    maximum = np.max(array, axis=axis, keepdims=True)
    if np.isneginf(maximum).any():
        raise BeliefWorldError("log-density support is empty")
    total = np.sum(np.exp(array - maximum), axis=axis, keepdims=True)
    result = maximum + np.log(total)
    if axis is not None:
        result = np.squeeze(result, axis=axis)
    return result


def mixture_log_density(
    component_log_densities: np.ndarray,
    component_probabilities: Sequence[float],
) -> np.ndarray:
    """Evaluate the full mixture denominator ``log sum_k pi_k q_k(z)``."""
    components = np.asarray(component_log_densities, dtype=np.float64)
    probabilities = np.asarray(component_probabilities, dtype=np.float64)
    if components.ndim != 2 or components.shape[0] != len(probabilities):
        raise BeliefWorldError(
            "component log densities must be component-by-world aligned"
        )
    if (
        not np.isfinite(probabilities).all()
        or np.any(probabilities <= 0.0)
        or not math.isclose(
            float(probabilities.sum()), 1.0, rel_tol=0.0, abs_tol=1e-12
        )
    ):
        raise BeliefWorldError(
            "mixture probabilities must be positive, finite, and sum to one"
        )
    return stable_logsumexp(
        components + np.log(probabilities)[:, None], axis=0
    )


def add_discrete_log_probability(
    conditional_log_density: Sequence[float],
    discrete_probability: Sequence[float] | float,
) -> np.ndarray:
    """Include a sampled discrete mode/player/state probability in a density."""
    density = np.asarray(conditional_log_density, dtype=np.float64)
    probability = np.asarray(discrete_probability, dtype=np.float64)
    if density.ndim != 1 or not density.size or not np.isfinite(density).all():
        raise BeliefWorldError("conditional log density must be finite and 1-D")
    try:
        probability = np.broadcast_to(probability, density.shape)
    except ValueError as exc:
        raise BeliefWorldError(
            "discrete probabilities do not align with worlds"
        ) from exc
    if not np.isfinite(probability).all() or np.any(probability <= 0.0) or np.any(
        probability > 1.0
    ):
        raise BeliefWorldError("discrete probabilities must be in (0, 1]")
    return density + np.log(probability)


@dataclass(frozen=True, slots=True)
class ImportanceWeights:
    log_weight: np.ndarray
    normalized_weight: np.ndarray
    log_normalizer: float
    effective_sample_size: float
    effective_sample_fraction: float
    max_normalized_weight: float
    top_one_percent_mass: float
    entropy: float


def normalize_log_importance_weights(
    log_target_density: Sequence[float],
    log_proposal_density: Sequence[float],
    *,
    proposal_supports_target: bool,
) -> ImportanceWeights:
    """Normalize exact ``p/q`` ratios and report concentration diagnostics."""
    if proposal_supports_target is not True:
        raise BeliefWorldError("proposal support over the target was not established")
    target = np.asarray(log_target_density, dtype=np.float64)
    proposal = np.asarray(log_proposal_density, dtype=np.float64)
    if target.ndim != 1 or proposal.ndim != 1 or target.shape != proposal.shape:
        raise BeliefWorldError("target/proposal log densities must be aligned 1-D arrays")
    if not target.size:
        raise BeliefWorldError("importance-weight bank cannot be empty")
    if not np.isfinite(target).all() or not np.isfinite(proposal).all():
        raise BeliefWorldError(
            "sampled target/proposal log densities must be finite"
        )
    log_weight = target - proposal
    log_normalizer = float(stable_logsumexp(log_weight))
    normalized = np.exp(log_weight - log_normalizer)
    normalized /= normalized.sum(dtype=np.float64)
    if (
        not np.isfinite(normalized).all()
        or np.any(normalized < 0.0)
        or not math.isclose(
            float(normalized.sum()), 1.0, rel_tol=0.0, abs_tol=1e-12
        )
    ):
        raise BeliefWorldError("normalized importance weights are invalid")
    squared = float(np.square(normalized).sum(dtype=np.float64))
    ess = 1.0 / squared
    positive = normalized[normalized > 0.0]
    entropy = -float(np.sum(positive * np.log(positive), dtype=np.float64))
    top_count = max(1, int(math.ceil(0.01 * len(normalized))))
    top_mass = float(np.sort(normalized)[-top_count:].sum(dtype=np.float64))
    return ImportanceWeights(
        log_weight=log_weight,
        normalized_weight=normalized,
        log_normalizer=log_normalizer,
        effective_sample_size=ess,
        effective_sample_fraction=ess / len(normalized),
        max_normalized_weight=float(normalized.max()),
        top_one_percent_mass=top_mass,
        entropy=entropy,
    )


_SAMPLING_DESIGN_KEYS: Final = frozenset({
    "schema",
    "adaptation_bank_id",
    "evaluation_bank_id",
    "proposal_frozen_before_evaluation",
    "evaluation_worlds_are_fresh",
    "evaluation_worlds_are_adaptation_elites",
    "proposal_density_evaluation",
    "density_proposal_id",
    "proposal_supports_target",
})


def validate_sampling_design(
    design: Mapping[str, object], *, proposal_id: str,
) -> dict[str, object]:
    """Reject adaptive/elite evaluation and selected-component denominators."""
    if not isinstance(design, Mapping) or frozenset(design) != _SAMPLING_DESIGN_KEYS:
        raise BeliefWorldError("sampling design schema differs")
    if design.get("schema") != SAMPLING_DESIGN_SCHEMA:
        raise BeliefWorldError("sampling design version differs")
    density_proposal = _identifier(
        design.get("density_proposal_id"), label="density proposal ID"
    )
    if density_proposal != proposal_id:
        raise BeliefWorldError("weight density does not name the sampled proposal")
    evaluation_bank = _identifier(
        design.get("evaluation_bank_id"), label="evaluation bank ID"
    )
    adaptation_bank = design.get("adaptation_bank_id")
    if adaptation_bank is not None:
        adaptation_bank = _identifier(adaptation_bank, label="adaptation bank ID")
        if adaptation_bank == evaluation_bank:
            raise BeliefWorldError(
                "adaptation and evaluation banks must be independent"
            )
    if design.get("evaluation_worlds_are_adaptation_elites") is not False:
        raise BeliefWorldError(
            "adaptation elites cannot be weighted evaluation worlds"
        )
    if design.get("proposal_frozen_before_evaluation") is not True:
        raise BeliefWorldError("proposal was not frozen before evaluation sampling")
    if design.get("evaluation_worlds_are_fresh") is not True:
        raise BeliefWorldError("evaluation worlds are not a fresh proposal sample")
    if design.get("proposal_supports_target") is not True:
        raise BeliefWorldError("proposal support over the target was not established")
    density_kind = design.get("proposal_density_evaluation")
    if density_kind not in {"direct-target", "full-mixture"}:
        raise BeliefWorldError(
            "proposal density must be direct-target or the full mixture"
        )
    if density_kind == "direct-target" and adaptation_bank is not None:
        raise BeliefWorldError(
            "a direct-target proposal cannot have an adaptation bank"
        )
    return dict(design)


def direct_sampling_design(
    evaluation_bank_id: str,
    *,
    proposal_id: str = DIRECT_SAMPLING_PROPOSAL_ID,
) -> dict[str, object]:
    """Construct the nonadaptive design used by directly sampled law worlds."""
    design = {
        "schema": SAMPLING_DESIGN_SCHEMA,
        "adaptation_bank_id": None,
        "evaluation_bank_id": _identifier(
            evaluation_bank_id, label="evaluation bank ID"
        ),
        "proposal_frozen_before_evaluation": True,
        "evaluation_worlds_are_fresh": True,
        "evaluation_worlds_are_adaptation_elites": False,
        "proposal_density_evaluation": "direct-target",
        "density_proposal_id": _identifier(proposal_id, label="proposal ID"),
        "proposal_supports_target": True,
    }
    return validate_sampling_design(design, proposal_id=proposal_id)


_ARTIFACT_KEYS: Final = frozenset({
    "schema",
    "law_id",
    "proposal_id",
    "calibration_id",
    "sampling_design",
    "player_count",
    "world_count",
    "player_world_shape",
    "ordered_player_ids",
    "ordered_world_ids",
    "ordered_player_ids_sha256",
    "ordered_world_ids_sha256",
    "draws_sha256",
    "player_world_binding_sha256",
    "proposal_component_ids",
    "proposal_component_probabilities",
    "log_target_density",
    "log_proposal_density",
    "log_weight",
    "normalized_weight",
    "weight_diagnostics",
    "uses_realized_outcomes",
    "historical_scoring_licensed",
    "production_change_licensed",
    "artifact_sha256",
})


def _finite_vector(
    value: object, *, label: str, expected: int,
) -> np.ndarray:
    if not isinstance(value, list) or len(value) != expected:
        raise BeliefWorldError(f"{label} must contain one value per world")
    array = np.asarray(value, dtype=np.float64)
    if array.ndim != 1 or not np.isfinite(array).all():
        raise BeliefWorldError(f"{label} must be finite")
    return array


def build_belief_world_artifact(
    *,
    draws: np.ndarray,
    player_ids: Sequence[object],
    world_ids: Sequence[object],
    law_id: str,
    proposal_id: str,
    calibration_id: str,
    sampling_design: Mapping[str, object],
    log_target_density: Sequence[float] | None = None,
    log_proposal_density: Sequence[float] | None = None,
    proposal_component_ids: Sequence[object] | None = None,
    proposal_component_probabilities: Sequence[float] | None = None,
) -> dict[str, object]:
    """Build a checksum-bound, columnar receipt for one world bank."""
    law_id = _identifier(law_id, label="law ID")
    proposal_id = _identifier(proposal_id, label="proposal ID")
    calibration_id = _identifier(calibration_id, label="calibration ID")
    players = _canonical_ids(player_ids, label="player IDs")
    worlds = _canonical_ids(world_ids, label="world IDs")
    values = np.asarray(draws, dtype=np.float64)
    if values.shape != (len(players), len(worlds)):
        raise BeliefWorldError("player/world identities do not align with draws")
    draws_digest = player_world_matrix_sha256(values)
    design = validate_sampling_design(sampling_design, proposal_id=proposal_id)

    explicit_densities = log_target_density is not None
    if explicit_densities != (log_proposal_density is not None):
        raise BeliefWorldError("target and proposal log densities must be paired")
    if log_target_density is None:
        if design["proposal_density_evaluation"] != "direct-target":
            raise BeliefWorldError("only direct sampling may omit explicit densities")
        target = np.zeros(len(worlds), dtype=np.float64)
        proposal = np.zeros(len(worlds), dtype=np.float64)
    else:
        target = np.asarray(log_target_density, dtype=np.float64)
        proposal = np.asarray(log_proposal_density, dtype=np.float64)
    if (
        design["proposal_density_evaluation"] == "direct-target"
        and explicit_densities
        and not np.array_equal(target, proposal)
    ):
        raise BeliefWorldError(
            "direct-target sampling requires identical target/proposal density"
        )
    weights = normalize_log_importance_weights(
        target,
        proposal,
        proposal_supports_target=bool(design["proposal_supports_target"]),
    )

    if proposal_component_ids is None:
        component_ids = tuple(proposal_id for _ in worlds)
    else:
        component_ids = tuple(
            _identifier(value, label="proposal component ID")
            for value in proposal_component_ids
        )
    if len(component_ids) != len(worlds):
        raise BeliefWorldError("proposal component IDs do not align with worlds")
    if proposal_component_probabilities is None:
        component_probabilities = np.ones(len(worlds), dtype=np.float64)
    else:
        component_probabilities = np.asarray(
            proposal_component_probabilities, dtype=np.float64
        )
    if (
        component_probabilities.shape != (len(worlds),)
        or not np.isfinite(component_probabilities).all()
        or np.any(component_probabilities <= 0.0)
        or np.any(component_probabilities > 1.0)
    ):
        raise BeliefWorldError(
            "selected proposal component probabilities must be in (0, 1]"
        )
    if design["proposal_density_evaluation"] == "direct-target" and (
        any(component != proposal_id for component in component_ids)
        or not np.all(component_probabilities == 1.0)
    ):
        raise BeliefWorldError(
            "direct-target worlds must name only the unit-probability proposal"
        )

    player_digest = ordered_identity_sha256(players, label="player IDs")
    world_digest = ordered_identity_sha256(worlds, label="world IDs")
    binding = canonical_sha256({
        "draws_sha256": draws_digest,
        "ordered_player_ids_sha256": player_digest,
        "ordered_world_ids_sha256": world_digest,
        "shape": [len(players), len(worlds)],
    })
    artifact: dict[str, object] = {
        "schema": BELIEF_WORLD_SCHEMA,
        "law_id": law_id,
        "proposal_id": proposal_id,
        "calibration_id": calibration_id,
        "sampling_design": design,
        "player_count": len(players),
        "world_count": len(worlds),
        "player_world_shape": [len(players), len(worlds)],
        "ordered_player_ids": list(players),
        "ordered_world_ids": list(worlds),
        "ordered_player_ids_sha256": player_digest,
        "ordered_world_ids_sha256": world_digest,
        "draws_sha256": draws_digest,
        "player_world_binding_sha256": binding,
        "proposal_component_ids": list(component_ids),
        "proposal_component_probabilities": component_probabilities.tolist(),
        "log_target_density": target.tolist(),
        "log_proposal_density": proposal.tolist(),
        "log_weight": weights.log_weight.tolist(),
        "normalized_weight": weights.normalized_weight.tolist(),
        "weight_diagnostics": {
            "log_normalizer": weights.log_normalizer,
            "effective_sample_size": weights.effective_sample_size,
            "effective_sample_fraction": weights.effective_sample_fraction,
            "max_normalized_weight": weights.max_normalized_weight,
            "top_one_percent_mass": weights.top_one_percent_mass,
            "entropy": weights.entropy,
        },
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    artifact["artifact_sha256"] = canonical_sha256(artifact)
    validate_belief_world_artifact(artifact, draws=values)
    return artifact


def validate_belief_world_artifact(
    artifact: Mapping[str, object], *, draws: np.ndarray | None = None,
) -> dict[str, object]:
    """Fail closed on schema, identity, support, or weight drift."""
    if not isinstance(artifact, Mapping) or frozenset(artifact) != _ARTIFACT_KEYS:
        raise BeliefWorldError("belief-world artifact keys differ")
    if artifact.get("schema") != BELIEF_WORLD_SCHEMA:
        raise BeliefWorldError("belief-world artifact version differs")
    law_id = _identifier(artifact.get("law_id"), label="law ID")
    proposal_id = _identifier(artifact.get("proposal_id"), label="proposal ID")
    _identifier(artifact.get("calibration_id"), label="calibration ID")
    del law_id
    design = validate_sampling_design(
        artifact.get("sampling_design"), proposal_id=proposal_id
    )
    players = _canonical_ids(
        artifact.get("ordered_player_ids"), label="player IDs"
    )
    worlds = _canonical_ids(artifact.get("ordered_world_ids"), label="world IDs")
    if artifact.get("player_count") != len(players) or artifact.get(
        "world_count"
    ) != len(worlds):
        raise BeliefWorldError("belief-world axis counts differ")
    if artifact.get("player_world_shape") != [len(players), len(worlds)]:
        raise BeliefWorldError("belief-world shape differs")
    player_digest = ordered_identity_sha256(players, label="player IDs")
    world_digest = ordered_identity_sha256(worlds, label="world IDs")
    if artifact.get("ordered_player_ids_sha256") != player_digest or artifact.get(
        "ordered_world_ids_sha256"
    ) != world_digest:
        raise BeliefWorldError("ordered identity digest differs")
    draws_digest = artifact.get("draws_sha256")
    if type(draws_digest) is not str or _SHA256.fullmatch(draws_digest) is None:
        raise BeliefWorldError("draws SHA-256 differs")
    if draws is not None and player_world_matrix_sha256(draws) != draws_digest:
        raise BeliefWorldError("player-world matrix differs from its receipt")
    binding = canonical_sha256({
        "draws_sha256": draws_digest,
        "ordered_player_ids_sha256": player_digest,
        "ordered_world_ids_sha256": world_digest,
        "shape": [len(players), len(worlds)],
    })
    if artifact.get("player_world_binding_sha256") != binding:
        raise BeliefWorldError("player-world binding differs")

    target = _finite_vector(
        artifact.get("log_target_density"),
        label="target log density",
        expected=len(worlds),
    )
    proposal = _finite_vector(
        artifact.get("log_proposal_density"),
        label="proposal log density",
        expected=len(worlds),
    )
    if (
        design["proposal_density_evaluation"] == "direct-target"
        and not np.array_equal(target, proposal)
    ):
        raise BeliefWorldError(
            "direct-target sampling requires identical target/proposal density"
        )
    expected_weights = normalize_log_importance_weights(
        target, proposal, proposal_supports_target=True
    )
    log_weight = _finite_vector(
        artifact.get("log_weight"), label="log weight", expected=len(worlds)
    )
    normalized = _finite_vector(
        artifact.get("normalized_weight"),
        label="normalized weight",
        expected=len(worlds),
    )
    if not np.array_equal(log_weight, expected_weights.log_weight) or not np.allclose(
        normalized,
        expected_weights.normalized_weight,
        rtol=0.0,
        atol=1e-15,
    ):
        raise BeliefWorldError("importance-weight values differ")
    diagnostics = artifact.get("weight_diagnostics")
    expected_diagnostic_keys = {
        "log_normalizer",
        "effective_sample_size",
        "effective_sample_fraction",
        "max_normalized_weight",
        "top_one_percent_mass",
        "entropy",
    }
    if not isinstance(diagnostics, Mapping) or set(diagnostics) != expected_diagnostic_keys:
        raise BeliefWorldError("weight diagnostics differ")
    expected_values = {
        "log_normalizer": expected_weights.log_normalizer,
        "effective_sample_size": expected_weights.effective_sample_size,
        "effective_sample_fraction": expected_weights.effective_sample_fraction,
        "max_normalized_weight": expected_weights.max_normalized_weight,
        "top_one_percent_mass": expected_weights.top_one_percent_mass,
        "entropy": expected_weights.entropy,
    }
    for key, expected in expected_values.items():
        try:
            value = float(diagnostics[key])
        except (TypeError, ValueError) as exc:
            raise BeliefWorldError("weight diagnostic is not numeric") from exc
        if not math.isclose(value, expected, rel_tol=0.0, abs_tol=1e-12):
            raise BeliefWorldError(f"weight diagnostic {key} differs")
    components = artifact.get("proposal_component_ids")
    probabilities = artifact.get("proposal_component_probabilities")
    if not isinstance(components, list) or len(components) != len(worlds):
        raise BeliefWorldError("proposal components do not align with worlds")
    tuple(_identifier(value, label="proposal component ID") for value in components)
    component_probabilities = _finite_vector(
        probabilities,
        label="proposal component probabilities",
        expected=len(worlds),
    )
    if np.any(component_probabilities <= 0.0) or np.any(
        component_probabilities > 1.0
    ):
        raise BeliefWorldError("proposal component probability is outside (0, 1]")
    if design["proposal_density_evaluation"] == "direct-target" and (
        any(component != proposal_id for component in components)
        or not np.all(component_probabilities == 1.0)
    ):
        raise BeliefWorldError(
            "direct-target worlds must name only the unit-probability proposal"
        )
    for flag in (
        "uses_realized_outcomes",
        "historical_scoring_licensed",
        "production_change_licensed",
    ):
        if artifact.get(flag) is not False:
            raise BeliefWorldError(f"belief-world {flag} boundary differs")
    digest = artifact.get("artifact_sha256")
    if type(digest) is not str or _SHA256.fullmatch(digest) is None:
        raise BeliefWorldError("artifact SHA-256 differs")
    unhashed = dict(artifact)
    unhashed.pop("artifact_sha256")
    if canonical_sha256(unhashed) != digest:
        raise BeliefWorldError("belief-world artifact content hash differs")
    return dict(artifact)


def served_baseline_environment(
    base: Mapping[str, str] | None = None,
) -> dict[str, str]:
    """Exact adapter to the pinned incumbent production environment."""
    from ..inference.production_policy import ADOPTED_CLASSIC_POLICY

    return ADOPTED_CLASSIC_POLICY.engine_environment(base)


def served_baseline_identity(
    base: Mapping[str, str] | None = None,
) -> dict[str, object]:
    """Separate the exact served law identity from its candidate policy."""
    from ..inference.production_policy import ADOPTED_CLASSIC_POLICY

    full_environment = served_baseline_environment(base)
    missing = [
        key for key in SERVED_BASELINE_LAW_ENV_KEYS if key not in full_environment
    ]
    if missing:
        raise BeliefWorldError(
            f"served baseline policy lacks law environment keys {missing}"
        )
    law_environment = {
        key: full_environment[key] for key in SERVED_BASELINE_LAW_ENV_KEYS
    }
    body: dict[str, object] = {
        "schema": BASELINE_IDENTITY_SCHEMA,
        "law_id": SERVED_BASELINE_LAW_ID,
        "direct_sampling_proposal_id": DIRECT_SAMPLING_PROPOSAL_ID,
        "policy_id": ADOPTED_CLASSIC_POLICY.policy_id,
        "source_panel": ADOPTED_CLASSIC_POLICY.source_panel,
        "model_variant": ADOPTED_CLASSIC_POLICY.model_variant,
        "full_policy_environment": full_environment,
        "full_policy_environment_sha256": canonical_sha256(full_environment),
        "law_environment": law_environment,
        "law_environment_sha256": canonical_sha256(law_environment),
        "candidate_generation_is_not_part_of_law": True,
        "uses_realized_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["identity_sha256"] = canonical_sha256(body)
    return body


@dataclass(frozen=True, slots=True)
class CalibrationFold:
    fold_id: str
    season: int
    phase: str
    component_train_first_season: int
    component_train_last_season: int
    prior_label_folds: tuple[str, ...]

    def receipt(self) -> dict[str, object]:
        return {
            "fold_id": self.fold_id,
            "season": self.season,
            "phase": self.phase,
            "component_train_first_season": self.component_train_first_season,
            "component_train_last_season": self.component_train_last_season,
            "prior_label_folds": list(self.prior_label_folds),
            "target_universe": "regular-season-sunday-main-1300-to-1900",
            "lineup_development_label": False,
        }


CALIBRATION_FOLDS: Final = (
    CalibrationFold("CAL19", 2019, "calibration", 2015, 2018, ()),
    CalibrationFold("WF21", 2021, "walk-forward", 2015, 2020, ("CAL19",)),
    CalibrationFold(
        "HOLD22", 2022, "holdout", 2015, 2021, ("CAL19", "WF21")
    ),
)


def calibration_fold_registry() -> dict[str, object]:
    """Return the label-separated, expanding-season Lane 2 fold registry."""
    body: dict[str, object] = {
        "schema": FOLD_REGISTRY_SCHEMA,
        "folds": [fold.receipt() for fold in CALIBRATION_FOLDS],
        "primary_excluded_seasons": list(PRIMARY_EXCLUDED_SEASONS),
        "primary_exclusion_reason": "predeclared-covid-regime-exclusion",
        "lineup_development_seasons": list(LINEUP_DEVELOPMENT_SEASONS),
        "calibration_labels_disjoint_from_lineup_development": True,
        "uses_realized_outcomes": False,
        "labels_read": False,
        "historical_scoring_licensed": False,
    }
    body["registry_sha256"] = canonical_sha256(body)
    return body


def support_census_contract() -> dict[str, object]:
    """Describe the only fields allowed in a pre-label Lane 2 census."""
    body: dict[str, object] = {
        "schema": SUPPORT_CENSUS_SCHEMA,
        "fold_registry_sha256": calibration_fold_registry()["registry_sha256"],
        "tables": {
            name: {
                "dimensions": list(spec["dimensions"]),
                "counts": list(spec["counts"]),
            }
            for name, spec in _SUPPORT_TABLES.items()
        },
        "forbidden_outcome_fields": sorted(_FORBIDDEN_CENSUS_FIELDS),
        "uses_realized_outcomes": False,
        "fantasy_or_lineup_labels_read": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["contract_sha256"] = canonical_sha256(body)
    return body


def _reject_forbidden_census_fields(value: object) -> None:
    if isinstance(value, Mapping):
        for key, nested in value.items():
            normalized = str(key).strip().lower()
            if normalized in _FORBIDDEN_CENSUS_FIELDS:
                raise BeliefWorldError(
                    f"support census contains forbidden outcome field {key!r}"
                )
            _reject_forbidden_census_fields(nested)
    elif isinstance(value, list):
        for nested in value:
            _reject_forbidden_census_fields(nested)


def build_support_census(
    records: Sequence[Mapping[str, object]],
) -> dict[str, object]:
    """Validate and canonically bind synthetic/precomputed support counts only."""
    if isinstance(records, (str, bytes)) or not isinstance(records, Sequence):
        raise BeliefWorldError("support census records must be an array")
    if not records:
        raise BeliefWorldError("support census cannot be empty")
    fold_by_id = {fold.fold_id: fold for fold in CALIBRATION_FOLDS}
    normalized: list[dict[str, object]] = []
    for record in records:
        _reject_forbidden_census_fields(record)
        if not isinstance(record, Mapping) or set(record) != {
            "fold_id",
            "season",
            "table",
            "dimensions",
            "counts",
        }:
            raise BeliefWorldError("support census record schema differs")
        fold_id = _identifier(record.get("fold_id"), label="support fold ID")
        if fold_id not in fold_by_id:
            raise BeliefWorldError("support census names an unregistered fold")
        season = record.get("season")
        if type(season) is not int or season != fold_by_id[fold_id].season:
            raise BeliefWorldError("support census season/fold binding differs")
        table = record.get("table")
        if type(table) is not str or table not in _SUPPORT_TABLES:
            raise BeliefWorldError("support census table differs")
        spec = _SUPPORT_TABLES[table]
        dimensions = record.get("dimensions")
        counts = record.get("counts")
        if not isinstance(dimensions, Mapping) or set(dimensions) != set(
            spec["dimensions"]
        ):
            raise BeliefWorldError("support census dimensions differ")
        if not isinstance(counts, Mapping) or set(counts) != set(spec["counts"]):
            raise BeliefWorldError("support census count fields differ")
        canonical_dimensions: dict[str, object] = {}
        for name in spec["dimensions"]:
            value = dimensions[name]
            if name == "week":
                if type(value) is not int or not 1 <= value <= 18:
                    raise BeliefWorldError("support census week is outside 1--18")
            elif type(value) is not str or not value or value.strip() != value:
                raise BeliefWorldError(
                    f"support census dimension {name} is not canonical"
                )
            canonical_dimensions[name] = value
        canonical_counts: dict[str, int] = {}
        for name in spec["counts"]:
            value = counts[name]
            if type(value) is not int or value < 0:
                raise BeliefWorldError(
                    f"support census count {name} must be an integer >= 0"
                )
            canonical_counts[name] = value
        normalized.append({
            "fold_id": fold_id,
            "season": season,
            "table": table,
            "dimensions": canonical_dimensions,
            "counts": canonical_counts,
        })
    fold_order = {fold.fold_id: index for index, fold in enumerate(CALIBRATION_FOLDS)}
    normalized.sort(key=lambda row: (
        fold_order[str(row["fold_id"])],
        str(row["table"]),
        canonical_json_bytes(row["dimensions"]),
    ))
    identities = [
        (row["fold_id"], row["table"], canonical_sha256(row["dimensions"]))
        for row in normalized
    ]
    if len(identities) != len(set(identities)):
        raise BeliefWorldError("support census cell repeats")
    body: dict[str, object] = {
        "schema": SUPPORT_CENSUS_SCHEMA,
        "fold_registry_sha256": calibration_fold_registry()["registry_sha256"],
        "support_contract_sha256": support_census_contract()["contract_sha256"],
        "records": normalized,
        "record_count": len(normalized),
        "uses_realized_outcomes": False,
        "fantasy_or_lineup_labels_read": False,
        "effect_fields_inspected": False,
        "treatment_constructed": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["census_sha256"] = canonical_sha256(body)
    return body


__all__ = [
    "BASELINE_IDENTITY_SCHEMA",
    "BELIEF_WORLD_SCHEMA",
    "CALIBRATION_FOLDS",
    "DIRECT_SAMPLING_PROPOSAL_ID",
    "FOLD_REGISTRY_SCHEMA",
    "ImportanceWeights",
    "LINEUP_DEVELOPMENT_SEASONS",
    "PRIMARY_EXCLUDED_SEASONS",
    "SAMPLING_DESIGN_SCHEMA",
    "SERVED_BASELINE_LAW_ENV_KEYS",
    "SERVED_BASELINE_LAW_ID",
    "SUPPORT_CENSUS_SCHEMA",
    "BeliefWorldError",
    "add_discrete_log_probability",
    "build_belief_world_artifact",
    "build_support_census",
    "calibration_fold_registry",
    "canonical_json_bytes",
    "canonical_sha256",
    "direct_sampling_design",
    "mixture_log_density",
    "normalize_log_importance_weights",
    "ordered_identity_sha256",
    "player_world_matrix_sha256",
    "served_baseline_environment",
    "served_baseline_identity",
    "stable_logsumexp",
    "support_census_contract",
    "validate_belief_world_artifact",
    "validate_sampling_design",
]
