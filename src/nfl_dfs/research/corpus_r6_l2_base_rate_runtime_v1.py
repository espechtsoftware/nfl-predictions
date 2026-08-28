"""Thin runtime adapter for the R6 L2b role-jump law.

Calibration-fold banks use the fold-specific pre-target registry.  The
2023-plus historical scoring panel instead uses one fixed prospective fit on
2018--2022 evidence; it never invents a 2023 or later refit.  Both paths
delegate residual bootstrapping and team-exclusive world generation to the
existing audited L2 primitives.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

import numpy as np
import pandas as pd

from .corpus_r6_belief_calibration_v1 import (
    BeliefCalibrationError,
    L2RoleJumpApplication,
)
from .corpus_r6_belief_law_challengers_v1 import (
    ChallengerBank,
    sample_l2_team_role_jump_bank_v1,
)
from .corpus_r6_l2_base_rate_v1 import (
    apply_l2_base_rate_calibration_v1,
    apply_l2_base_rate_historical_fold_v1,
    l2_base_rate_historical_residual_samples_by_group_v1,
    l2_base_rate_residual_samples_by_group_v1,
    validate_l2_base_rate_calibration_release_v1,
)
from .corpus_r6_l2_role_jump_components_v1 import (
    L2RoleJumpComponents,
    build_l2_role_jump_components_v1,
)


@dataclass(frozen=True, slots=True)
class L2BaseRateBank:
    """The three exact, independently auditable L2 runtime products."""

    application: L2RoleJumpApplication
    components: L2RoleJumpComponents
    bank: ChallengerBank


def _build_bank(
    *,
    application: L2RoleJumpApplication,
    residuals: Mapping[str, np.ndarray],
    minimum_group_support: int,
    target_players: pd.DataFrame,
    ordinary_draws: np.ndarray,
    player_ids: Sequence[object],
    world_ids: Sequence[object],
    calibration_source_identity: Mapping[str, object],
    source_identities: Mapping[str, Mapping[str, object]],
    component_seed: int,
    mixture_seed: int,
) -> L2BaseRateBank:
    ordered_players = tuple(str(value) for value in player_ids)
    target_player_ids = tuple(
        str(value) for value in target_players["gsis_id"].tolist()
    )
    if ordered_players != target_player_ids:
        raise BeliefCalibrationError(
            "L2b target/player order differs"
        )
    observed_groups = set(application.empirical_group_by_player)
    components = build_l2_role_jump_components_v1(
        ordinary_draws=ordinary_draws,
        player_ids=ordered_players,
        empirical_group_by_player=application.empirical_group_by_player,
        residual_samples_by_group={
            group: residuals[group] for group in observed_groups
        },
        calibration_source_identity=calibration_source_identity,
        base_seed=component_seed,
        minimum_group_support=minimum_group_support,
    )
    bank = sample_l2_team_role_jump_bank_v1(
        ordinary_draws=ordinary_draws,
        role_jump_draws=components.role_jump_draws,
        player_ids=ordered_players,
        world_ids=world_ids,
        team_ids=tuple(str(value) for value in target_players["team"]),
        role_jump_probabilities=application.role_jump_probabilities,
        seed=mixture_seed,
        calibration_id=str(application.receipt["calibration_id"]),
        source_identities=source_identities,
    )
    return L2BaseRateBank(application, components, bank)


def build_l2_base_rate_historical_bank_v1(
    *,
    release: Mapping[str, object],
    fold_id: str,
    target_players: pd.DataFrame,
    ordinary_draws: np.ndarray,
    player_ids: Sequence[object],
    world_ids: Sequence[object],
    calibration_source_identity: Mapping[str, object],
    source_identities: Mapping[str, Mapping[str, object]],
    component_seed: int,
    mixture_seed: int,
) -> L2BaseRateBank:
    """Generate CAL19/WF21/HOLD22 from that fold's pre-target registry."""
    validated = validate_l2_base_rate_calibration_release_v1(release)
    application = apply_l2_base_rate_historical_fold_v1(
        validated, fold_id, target_players
    )
    residuals = l2_base_rate_historical_residual_samples_by_group_v1(
        validated, fold_id
    )
    return _build_bank(
        application=application,
        residuals=residuals,
        minimum_group_support=validated["minimum_group_support"],
        target_players=target_players,
        ordinary_draws=ordinary_draws,
        player_ids=player_ids,
        world_ids=world_ids,
        calibration_source_identity=calibration_source_identity,
        source_identities=source_identities,
        component_seed=component_seed,
        mixture_seed=mixture_seed,
    )


def build_l2_base_rate_prospective_bank_v1(
    *,
    release: Mapping[str, object],
    target_players: pd.DataFrame,
    ordinary_draws: np.ndarray,
    player_ids: Sequence[object],
    world_ids: Sequence[object],
    calibration_source_identity: Mapping[str, object],
    source_identities: Mapping[str, Mapping[str, object]],
    component_seed: int,
    mixture_seed: int,
) -> L2BaseRateBank:
    """Generate a 2023-plus bank from the one fixed 2018--2022 fit."""
    validated = validate_l2_base_rate_calibration_release_v1(release)
    if not isinstance(target_players, pd.DataFrame) or (
        "season" not in target_players.columns
    ):
        raise BeliefCalibrationError("L2b prospective target season differs")
    seasons = pd.to_numeric(target_players["season"], errors="coerce")
    if (
        target_players.empty
        or seasons.isna().any()
        or seasons.nunique() != 1
        or int(seasons.iloc[0]) < 2023
        or not seasons.eq(int(seasons.iloc[0])).all()
    ):
        raise BeliefCalibrationError("L2b prospective target season differs")
    application = apply_l2_base_rate_calibration_v1(
        validated, target_players
    )
    return _build_bank(
        application=application,
        residuals=l2_base_rate_residual_samples_by_group_v1(validated),
        minimum_group_support=validated["minimum_group_support"],
        target_players=target_players,
        ordinary_draws=ordinary_draws,
        player_ids=player_ids,
        world_ids=world_ids,
        calibration_source_identity=calibration_source_identity,
        source_identities=source_identities,
        component_seed=component_seed,
        mixture_seed=mixture_seed,
    )


__all__ = [
    "L2BaseRateBank",
    "build_l2_base_rate_historical_bank_v1",
    "build_l2_base_rate_prospective_bank_v1",
]
