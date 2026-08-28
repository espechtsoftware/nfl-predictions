"""Score-free L1/L2 player-world laws for the R6 preseason shootout.

These are sampling primitives, not calibrated models and not production
authority.  L1 mixes ordinary and shootout component banks at the whole-game
level.  L2 mixes ordinary and empirical role-jump component banks while
allowing at most one role jump per team/world.  Calibration supplies the
probabilities; this module makes the resulting law deterministic, replayable,
and directly sampleable without looking at lineup outcomes.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Final

import numpy as np

from .belief_world_v1 import (
    build_belief_world_artifact,
    canonical_json_bytes,
    canonical_sha256,
    direct_sampling_design,
    player_world_matrix_sha256,
    validate_belief_world_artifact,
)
from .object_identity import IDENTITY_FIELDS, content_identity


L1_LAW_ID: Final = "l1-shootout-regime-v1"
L2_LAW_ID: Final = "l2-team-role-jump-mixture-v1"
L1_PROPOSAL_ID: Final = "direct-l1-shootout-regime-v1"
L2_PROPOSAL_ID: Final = "direct-l2-team-role-jump-mixture-v1"
RECEIPT_SCHEMA: Final = "corpus-r6-belief-law-challenger-receipt/v1"


class BeliefLawChallengerError(ValueError):
    """A score-free L1/L2 sampling boundary was violated."""


@dataclass(frozen=True, slots=True)
class ChallengerBank:
    """One sampled bank plus its compact replay receipt and latent states."""

    draws: np.ndarray
    latent_states: np.ndarray
    receipt: dict[str, object]
    belief_world_artifact: dict[str, object]


def _ids(values: Sequence[object], *, label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise BeliefLawChallengerError(f"{label} must be an ordered sequence")
    result = tuple(str(value) for value in values)
    if not result or any(not value for value in result):
        raise BeliefLawChallengerError(f"{label} must be nonempty identities")
    if len(set(result)) != len(result):
        raise BeliefLawChallengerError(f"{label} contains duplicate identities")
    return result


def _axis(
    values: Sequence[object], *, expected: int, label: str, unique: bool = False,
) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise BeliefLawChallengerError(f"{label} must be an ordered sequence")
    result = tuple(str(value) for value in values)
    if len(result) != expected or any(not value for value in result):
        raise BeliefLawChallengerError(f"{label} does not align with players")
    if unique and len(set(result)) != len(result):
        raise BeliefLawChallengerError(f"{label} contains duplicates")
    return result


def _matrix(value: np.ndarray, *, shape: tuple[int, int], label: str) -> np.ndarray:
    result = np.asarray(value, dtype=np.float64)
    if result.shape != shape or not np.isfinite(result).all():
        raise BeliefLawChallengerError(
            f"{label} must be a finite player-by-world matrix"
        )
    return np.ascontiguousarray(result, dtype=np.float64)


def _probabilities(
    values: Sequence[float], *, expected: int, label: str,
) -> np.ndarray:
    result = np.asarray(values, dtype=np.float64)
    if (
        result.shape != (expected,)
        or not np.isfinite(result).all()
        or np.any(result < 0.0)
        or np.any(result > 1.0)
    ):
        raise BeliefLawChallengerError(f"{label} must be finite values in [0,1]")
    return result


def _source_identities(
    values: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    if not isinstance(values, Mapping) or not values:
        raise BeliefLawChallengerError("source identities cannot be empty")
    retained: dict[str, dict[str, object]] = {}
    for label in sorted(values):
        if not isinstance(label, str) or not label:
            raise BeliefLawChallengerError("source identity label differs")
        try:
            identity = content_identity(values[label])
        except (TypeError, ValueError) as exc:
            raise BeliefLawChallengerError(
                f"source identity {label!r} differs"
            ) from exc
        retained[label] = dict(zip(IDENTITY_FIELDS, identity, strict=True))
    return retained


def _array_sha256(value: np.ndarray, *, dtype: str) -> str:
    stable = np.ascontiguousarray(value, dtype=np.dtype(dtype))
    header = canonical_json_bytes({"dtype": dtype, "shape": list(stable.shape)})
    return sha256(header + b"\0" + stable.tobytes(order="C")).hexdigest()


def _receipt(
    *,
    law_id: str,
    proposal_id: str,
    calibration_id: str,
    seed: int,
    player_ids: tuple[str, ...],
    world_ids: tuple[str, ...],
    component_a: np.ndarray,
    component_b: np.ndarray,
    probabilities: np.ndarray,
    latent_states: np.ndarray,
    latent_dtype: str,
    draws: np.ndarray,
    sources: Mapping[str, Mapping[str, object]],
    belief_artifact: Mapping[str, object],
    mechanism: Mapping[str, object],
) -> dict[str, object]:
    body: dict[str, object] = {
        "schema": RECEIPT_SCHEMA,
        "law_id": law_id,
        "proposal_id": proposal_id,
        "calibration_id": calibration_id,
        "seed": seed,
        "player_count": len(player_ids),
        "world_count": len(world_ids),
        "ordered_player_ids_sha256": canonical_sha256(list(player_ids)),
        "ordered_world_ids_sha256": canonical_sha256(list(world_ids)),
        "component_a_draws_sha256": player_world_matrix_sha256(component_a),
        "component_b_draws_sha256": player_world_matrix_sha256(component_b),
        "probabilities_sha256": _array_sha256(probabilities, dtype="<f8"),
        "latent_states_sha256": _array_sha256(
            latent_states, dtype=latent_dtype
        ),
        "result_draws_sha256": player_world_matrix_sha256(draws),
        "source_identities": _source_identities(sources),
        "belief_world_artifact_sha256": belief_artifact["artifact_sha256"],
        "player_world_binding_sha256": belief_artifact[
            "player_world_binding_sha256"
        ],
        "mechanism": dict(mechanism),
        "direct_target_sampling": True,
        "calibrated_model_claimed": False,
        "uses_lineup_outcomes": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    return body


def validate_challenger_receipt(value: Mapping[str, object]) -> dict[str, object]:
    """Validate the compact no-authority receipt without reopening matrices."""
    if not isinstance(value, Mapping) or value.get("schema") != RECEIPT_SCHEMA:
        raise BeliefLawChallengerError("challenger receipt schema differs")
    expected = {
        "schema", "law_id", "proposal_id", "calibration_id", "seed",
        "player_count", "world_count", "ordered_player_ids_sha256",
        "ordered_world_ids_sha256", "component_a_draws_sha256",
        "component_b_draws_sha256", "probabilities_sha256",
        "latent_states_sha256", "result_draws_sha256", "source_identities",
        "belief_world_artifact_sha256", "player_world_binding_sha256",
        "mechanism", "direct_target_sampling", "calibrated_model_claimed",
        "uses_lineup_outcomes", "historical_scoring_licensed",
        "production_change_licensed", "receipt_sha256",
    }
    if set(value) != expected:
        raise BeliefLawChallengerError("challenger receipt keys differ")
    if value.get("law_id") not in {L1_LAW_ID, L2_LAW_ID}:
        raise BeliefLawChallengerError("challenger law differs")
    if value.get("proposal_id") not in {L1_PROPOSAL_ID, L2_PROPOSAL_ID}:
        raise BeliefLawChallengerError("challenger proposal differs")
    for flag in (
        "calibrated_model_claimed", "uses_lineup_outcomes",
        "historical_scoring_licensed", "production_change_licensed",
    ):
        if value.get(flag) is not False:
            raise BeliefLawChallengerError(f"challenger {flag} boundary differs")
    if value.get("direct_target_sampling") is not True:
        raise BeliefLawChallengerError("challenger sampling boundary differs")
    _source_identities(value.get("source_identities"))
    digest = value.get("receipt_sha256")
    body = dict(value)
    body.pop("receipt_sha256", None)
    if digest != canonical_sha256(body):
        raise BeliefLawChallengerError("challenger receipt content hash differs")
    return dict(value)


def sample_l1_shootout_regime_bank_v1(
    *,
    ordinary_draws: np.ndarray,
    shootout_draws: np.ndarray,
    player_ids: Sequence[object],
    world_ids: Sequence[object],
    game_ids: Sequence[object],
    team_ids: Sequence[object],
    shootout_probability_by_game: Mapping[str, float],
    seed: int,
    calibration_id: str,
    source_identities: Mapping[str, Mapping[str, object]],
) -> ChallengerBank:
    """Sample one game-wide ordinary/shootout mixture bank.

    All players from both teams in a game share the same state in a world.
    The caller must construct ``shootout_draws`` with the intended correlated
    pace/pass/team-factor/usage mechanisms before entering this boundary.
    """
    players = _ids(player_ids, label="player IDs")
    worlds = _ids(world_ids, label="world IDs")
    shape = (len(players), len(worlds))
    ordinary = _matrix(ordinary_draws, shape=shape, label="ordinary draws")
    shootout = _matrix(shootout_draws, shape=shape, label="shootout draws")
    games = _axis(game_ids, expected=len(players), label="game IDs")
    teams = _axis(team_ids, expected=len(players), label="team IDs")
    ordered_games = tuple(dict.fromkeys(games))
    if set(shootout_probability_by_game) != set(ordered_games):
        raise BeliefLawChallengerError(
            "shootout probabilities must name every and only observed game"
        )
    probabilities = _probabilities(
        [shootout_probability_by_game[game] for game in ordered_games],
        expected=len(ordered_games),
        label="shootout probabilities",
    )
    for game in ordered_games:
        observed_teams = {teams[index] for index, value in enumerate(games) if value == game}
        if len(observed_teams) != 2:
            raise BeliefLawChallengerError(
                "each L1 game must contain exactly two observed teams"
            )
    rng = np.random.default_rng(seed)
    states = rng.random((len(ordered_games), len(worlds))) < probabilities[:, None]
    draws = ordinary.copy()
    for game_index, game in enumerate(ordered_games):
        rows = np.flatnonzero(np.asarray(games) == game)
        columns = np.flatnonzero(states[game_index])
        draws[np.ix_(rows, columns)] = shootout[np.ix_(rows, columns)]
    design = direct_sampling_design(
        f"{L1_LAW_ID}-seed-{seed}", proposal_id=L1_PROPOSAL_ID
    )
    artifact = build_belief_world_artifact(
        draws=draws,
        player_ids=players,
        world_ids=worlds,
        law_id=L1_LAW_ID,
        proposal_id=L1_PROPOSAL_ID,
        calibration_id=calibration_id,
        sampling_design=design,
    )
    validate_belief_world_artifact(artifact, draws=draws)
    receipt = _receipt(
        law_id=L1_LAW_ID,
        proposal_id=L1_PROPOSAL_ID,
        calibration_id=calibration_id,
        seed=seed,
        player_ids=players,
        world_ids=worlds,
        component_a=ordinary,
        component_b=shootout,
        probabilities=probabilities,
        latent_states=states,
        latent_dtype="|b1",
        draws=draws,
        sources=source_identities,
        belief_artifact=artifact,
        mechanism={
            "state_grain": "game-world",
            "states": ["ordinary", "shootout"],
            "both_teams_share_state": True,
            "probability_source": "external-point-in-time-calibration",
        },
    )
    validate_challenger_receipt(receipt)
    return ChallengerBank(draws, states, receipt, artifact)


def sample_l2_team_role_jump_bank_v1(
    *,
    ordinary_draws: np.ndarray,
    role_jump_draws: np.ndarray,
    player_ids: Sequence[object],
    world_ids: Sequence[object],
    team_ids: Sequence[object],
    role_jump_probabilities: Sequence[float],
    seed: int,
    calibration_id: str,
    source_identities: Mapping[str, Mapping[str, object]],
) -> ChallengerBank:
    """Sample an at-most-one-player role jump for each team and world."""
    players = _ids(player_ids, label="player IDs")
    worlds = _ids(world_ids, label="world IDs")
    shape = (len(players), len(worlds))
    ordinary = _matrix(ordinary_draws, shape=shape, label="ordinary draws")
    jump = _matrix(role_jump_draws, shape=shape, label="role-jump draws")
    teams = _axis(team_ids, expected=len(players), label="team IDs")
    probabilities = _probabilities(
        role_jump_probabilities,
        expected=len(players),
        label="role-jump probabilities",
    )
    ordered_teams = tuple(dict.fromkeys(teams))
    team_rows = [np.flatnonzero(np.asarray(teams) == team) for team in ordered_teams]
    for rows in team_rows:
        if float(probabilities[rows].sum()) > 1.0 + 1e-12:
            raise BeliefLawChallengerError(
                "role-jump probabilities exceed one within a team"
            )
    rng = np.random.default_rng(seed)
    selected = np.full((len(ordered_teams), len(worlds)), -1, dtype=np.int32)
    draws = ordinary.copy()
    for team_index, rows in enumerate(team_rows):
        uniforms = rng.random(len(worlds))
        cumulative = 0.0
        for row in rows:
            previous = cumulative
            cumulative += float(probabilities[row])
            columns = (uniforms >= previous) & (uniforms < cumulative)
            selected[team_index, columns] = int(row)
            draws[row, columns] = jump[row, columns]
    design = direct_sampling_design(
        f"{L2_LAW_ID}-seed-{seed}", proposal_id=L2_PROPOSAL_ID
    )
    artifact = build_belief_world_artifact(
        draws=draws,
        player_ids=players,
        world_ids=worlds,
        law_id=L2_LAW_ID,
        proposal_id=L2_PROPOSAL_ID,
        calibration_id=calibration_id,
        sampling_design=design,
    )
    validate_belief_world_artifact(artifact, draws=draws)
    receipt = _receipt(
        law_id=L2_LAW_ID,
        proposal_id=L2_PROPOSAL_ID,
        calibration_id=calibration_id,
        seed=seed,
        player_ids=players,
        world_ids=worlds,
        component_a=ordinary,
        component_b=jump,
        probabilities=probabilities,
        latent_states=selected,
        latent_dtype="<i4",
        draws=draws,
        sources=source_identities,
        belief_artifact=artifact,
        mechanism={
            "state_grain": "team-world",
            "states": ["ordinary", "one-player-role-jump"],
            "maximum_role_jumps_per_team_world": 1,
            "probability_source": "external-point-in-time-calibration",
        },
    )
    validate_challenger_receipt(receipt)
    return ChallengerBank(draws, selected, receipt, artifact)


__all__ = [
    "BeliefLawChallengerError",
    "ChallengerBank",
    "L1_LAW_ID",
    "L2_LAW_ID",
    "sample_l1_shootout_regime_bank_v1",
    "sample_l2_team_role_jump_bank_v1",
    "validate_challenger_receipt",
]
