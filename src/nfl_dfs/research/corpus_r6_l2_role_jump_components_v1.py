"""Empirical role-jump component builder for the R6 L2 belief law.

The builder consumes an already frozen, walk-forward calibration artifact:
finite score residuals for each predeclared position/archetype group.  It
samples a conditional jump component around the ordinary player-world bank.
It never queries outcomes, chooses jump probabilities, scores lineups, or
changes production.  The L2 mixture core separately enforces at most one jump
per team/world.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Final

import numpy as np

from .belief_world_v1 import (
    canonical_json_bytes,
    canonical_sha256,
    player_world_matrix_sha256,
)
from .object_identity import IDENTITY_FIELDS, content_identity


SCHEMA: Final = "corpus-r6-l2-role-jump-components/v1"
_RECEIPT_KEYS: Final = frozenset({
    "schema", "player_count", "world_count", "base_seed", "player_ids_sha256",
    "empirical_group_by_player_sha256", "ordinary_draws_sha256",
    "role_jump_draws_sha256", "residual_group_receipts", "minimum_group_support",
    "calibration_source_identity", "sampling", "uses_lineup_outcomes",
    "derived_historical_player_residuals_consumed",
    "calibration_artifact_content_validated_here",
    "historical_lineup_scoring_licensed", "production_change_licensed",
    "receipt_sha256",
})


class L2ComponentError(ValueError):
    """The empirical role-jump component boundary was violated."""


@dataclass(frozen=True, slots=True)
class L2RoleJumpComponents:
    role_jump_draws: np.ndarray
    sampled_residuals: np.ndarray
    receipt: dict[str, object]


def _array_sha256(value: np.ndarray) -> str:
    stable = np.ascontiguousarray(value, dtype=np.dtype("<f8"))
    header = canonical_json_bytes({"dtype": "<f8", "shape": list(stable.shape)})
    return sha256(header + b"\0" + stable.tobytes(order="C")).hexdigest()


def _identity(value: Mapping[str, object]) -> dict[str, object]:
    try:
        retained = content_identity(value)
    except (TypeError, ValueError) as exc:
        raise L2ComponentError("calibration source identity differs") from exc
    return dict(zip(IDENTITY_FIELDS, retained, strict=True))


def build_l2_role_jump_components_v1(
    *,
    ordinary_draws: np.ndarray,
    player_ids: Sequence[object],
    empirical_group_by_player: Sequence[object],
    residual_samples_by_group: Mapping[str, Sequence[float]],
    calibration_source_identity: Mapping[str, object],
    base_seed: int,
    minimum_group_support: int,
) -> L2RoleJumpComponents:
    """Sample group-conditional role-jump residuals with replacement."""
    ordinary = np.asarray(ordinary_draws, dtype=np.float64)
    if ordinary.ndim != 2 or not ordinary.size or not np.isfinite(ordinary).all():
        raise L2ComponentError("ordinary draws must be a finite 2-D matrix")
    if type(base_seed) is not int or base_seed < 0:
        raise L2ComponentError("base seed must be a nonnegative integer")
    if (
        type(minimum_group_support) is not int
        or minimum_group_support < 20
        or minimum_group_support > 100_000
    ):
        raise L2ComponentError("minimum group support must be in [20,100000]")
    if isinstance(player_ids, (str, bytes)) or not isinstance(player_ids, Sequence):
        raise L2ComponentError("player IDs must be an ordered sequence")
    players = tuple(str(value) for value in player_ids)
    if (
        len(players) != ordinary.shape[0]
        or any(not value for value in players)
        or len(set(players)) != len(players)
    ):
        raise L2ComponentError("player IDs do not align uniquely with draws")
    if (
        isinstance(empirical_group_by_player, (str, bytes))
        or not isinstance(empirical_group_by_player, Sequence)
    ):
        raise L2ComponentError("empirical groups must be an ordered sequence")
    groups = tuple(str(value) for value in empirical_group_by_player)
    if len(groups) != len(players) or any(not value for value in groups):
        raise L2ComponentError("empirical groups do not align with players")
    observed_groups = set(groups)
    if not isinstance(residual_samples_by_group, Mapping) or set(
        residual_samples_by_group
    ) != observed_groups:
        raise L2ComponentError(
            "residual samples must name every and only observed empirical group"
        )
    residuals: dict[str, np.ndarray] = {}
    group_receipts: dict[str, dict[str, object]] = {}
    for group in sorted(observed_groups):
        values = np.asarray(residual_samples_by_group[group], dtype=np.float64)
        if (
            values.ndim != 1
            or len(values) < minimum_group_support
            or not np.isfinite(values).all()
        ):
            raise L2ComponentError(
                f"residual group {group!r} lacks finite minimum support"
            )
        if float(values.mean()) <= 0.0 or float(np.quantile(values, 0.9)) <= 0.0:
            raise L2ComponentError(
                f"residual group {group!r} is not a positive jump component"
            )
        stable = np.ascontiguousarray(values, dtype=np.float64)
        residuals[group] = stable
        group_receipts[group] = {
            "row_count": len(stable),
            "samples_sha256": _array_sha256(stable),
            "mean": float(stable.mean()),
            "q50": float(np.quantile(stable, 0.5)),
            "q90": float(np.quantile(stable, 0.9)),
        }
    rng = np.random.default_rng(base_seed)
    sampled = np.empty_like(ordinary)
    for player_index, group in enumerate(groups):
        values = residuals[group]
        indexes = rng.integers(0, len(values), size=ordinary.shape[1])
        sampled[player_index] = values[indexes]
    jump = np.ascontiguousarray(ordinary + sampled, dtype=np.float64)
    body: dict[str, object] = {
        "schema": SCHEMA,
        "player_count": ordinary.shape[0],
        "world_count": ordinary.shape[1],
        "base_seed": base_seed,
        "player_ids_sha256": canonical_sha256(list(players)),
        "empirical_group_by_player_sha256": canonical_sha256(list(groups)),
        "ordinary_draws_sha256": player_world_matrix_sha256(ordinary),
        "role_jump_draws_sha256": player_world_matrix_sha256(jump),
        "residual_group_receipts": group_receipts,
        "minimum_group_support": minimum_group_support,
        "calibration_source_identity": _identity(calibration_source_identity),
        "sampling": {
            "method": "group-conditional-empirical-residual-bootstrap",
            "replacement": True,
            "one_draw_per_player_world": True,
            "jump_probability_applied_here": False,
            "team_exclusivity_applied_here": False,
        },
        "uses_lineup_outcomes": False,
        "derived_historical_player_residuals_consumed": True,
        "calibration_artifact_content_validated_here": False,
        "historical_lineup_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    validate_l2_role_jump_component_receipt(body)
    return L2RoleJumpComponents(jump, sampled, body)


def validate_l2_role_jump_component_receipt(
    value: Mapping[str, object],
) -> dict[str, object]:
    if (
        not isinstance(value, Mapping)
        or frozenset(value) != _RECEIPT_KEYS
        or value.get("schema") != SCHEMA
    ):
        raise L2ComponentError("L2 role-jump receipt schema differs")
    for flag in (
        "uses_lineup_outcomes", "historical_lineup_scoring_licensed",
        "production_change_licensed", "calibration_artifact_content_validated_here",
    ):
        if value.get(flag) is not False:
            raise L2ComponentError(f"L2 role-jump {flag} boundary differs")
    if value.get("derived_historical_player_residuals_consumed") is not True:
        raise L2ComponentError("L2 role-jump calibration input boundary differs")
    sampling = value.get("sampling")
    if not isinstance(sampling, Mapping) or sampling != {
        "method": "group-conditional-empirical-residual-bootstrap",
        "replacement": True,
        "one_draw_per_player_world": True,
        "jump_probability_applied_here": False,
        "team_exclusivity_applied_here": False,
    }:
        raise L2ComponentError("L2 role-jump sampling contract differs")
    _identity(value.get("calibration_source_identity"))
    digest = value.get("receipt_sha256")
    body = dict(value)
    body.pop("receipt_sha256", None)
    if digest != canonical_sha256(body):
        raise L2ComponentError("L2 role-jump receipt content hash differs")
    return dict(value)


__all__ = [
    "L2ComponentError",
    "L2RoleJumpComponents",
    "build_l2_role_jump_components_v1",
    "validate_l2_role_jump_component_receipt",
]
