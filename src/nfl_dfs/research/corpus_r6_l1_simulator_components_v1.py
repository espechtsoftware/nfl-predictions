"""Outcome-free simulator adapter for L1 ordinary/shootout components.

The adapter runs the incumbent player-component surface once under its served
law and once under the fixed L1 mechanism composition.  It does not choose a
shootout probability, inspect labels, mix the components, score lineups, or
authorize production.  Those operations live behind separate calibration and
belief-bank boundaries.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from hashlib import sha256
from typing import Final

import numpy as np
import pandas as pd

from ..models.components import COMPONENT_NAMES
from ..models.simulate import (
    canonicalize_simulation_components,
    simulate,
    simulation_component_sha256,
)
from .belief_world_v1 import (
    SERVED_BASELINE_LAW_ENV_KEYS,
    canonical_json_bytes,
    canonical_sha256,
    player_world_matrix_sha256,
    served_baseline_environment,
)
from .object_identity import IDENTITY_FIELDS, content_identity


SCHEMA: Final = "corpus-r6-l1-simulator-components/v1"
SHOOTOUT_ENVIRONMENT: Final = {
    "GAME_SIM_MODE": "possession",
    "GAME_SIM_PACE": "vegas",
    "GAME_SIM_TEAM_FACTORS": "0",
    "GAME_SIM_USAGE": "dirichlet",
    "TD_LEDGER": "1",
}
_RECEIPT_KEYS: Final = frozenset({
    "schema", "n_players", "n_worlds", "base_seed", "ordinary_seed",
    "shootout_seed", "component_sha256", "game_ids_sha256",
    "team_ids_sha256", "game_totals_sha256", "bigplay_rate_sha256",
    "ordinary_environment", "shootout_environment", "usage_dirichlet_k",
    "td_allocation_k", "ordinary_draws_sha256", "shootout_draws_sha256",
    "source_identities", "uses_lineup_outcomes", "calibration_labels_read",
    "historical_scoring_licensed", "production_change_licensed",
    "receipt_sha256",
})


class L1ComponentError(ValueError):
    """The L1 simulator-component boundary was violated."""


@dataclass(frozen=True, slots=True)
class L1ComponentBanks:
    ordinary_draws: np.ndarray
    shootout_draws: np.ndarray
    receipt: dict[str, object]


def _derived_seed(seed: int, label: str) -> int:
    if type(seed) is not int or seed < 0:
        raise L1ComponentError("base seed must be a nonnegative integer")
    digest = sha256(canonical_json_bytes([seed, label])).digest()
    return int.from_bytes(digest[:8], "big") & ((1 << 63) - 1)


def _source_identities(
    values: Mapping[str, Mapping[str, object]],
) -> dict[str, dict[str, object]]:
    if not isinstance(values, Mapping) or not values:
        raise L1ComponentError("source identities cannot be empty")
    result: dict[str, dict[str, object]] = {}
    for label in sorted(values):
        if not isinstance(label, str) or not label:
            raise L1ComponentError("source identity label differs")
        try:
            identity = content_identity(values[label])
        except (TypeError, ValueError) as exc:
            raise L1ComponentError(f"source identity {label!r} differs") from exc
        result[label] = dict(zip(IDENTITY_FIELDS, identity, strict=True))
    return result


def _law_environment(value: Mapping[str, str] | None) -> dict[str, str]:
    full = served_baseline_environment() if value is None else {
        str(key): str(item) for key, item in value.items()
    }
    missing = [key for key in SERVED_BASELINE_LAW_ENV_KEYS if key not in full]
    if missing:
        raise L1ComponentError(f"ordinary law environment lacks {missing}")
    return {key: full[key] for key in SERVED_BASELINE_LAW_ENV_KEYS}


def _axis(values: Sequence[object], *, expected: int, label: str) -> pd.Series:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise L1ComponentError(f"{label} must be an ordered sequence")
    result = pd.Series(list(values), dtype="object")
    if len(result) != expected or result.isna().any() or (result.astype(str) == "").any():
        raise L1ComponentError(f"{label} must align with components")
    return result.astype(str)


def _numeric_axis(
    values: Sequence[object] | None, *, expected: int, label: str,
) -> pd.Series | None:
    if values is None:
        return None
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise L1ComponentError(f"{label} must be an ordered sequence")
    result = pd.to_numeric(pd.Series(list(values)), errors="coerce")
    if len(result) != expected or result.isna().all():
        raise L1ComponentError(f"{label} must align and contain finite support")
    finite = result.dropna().to_numpy(dtype=float)
    if not np.isfinite(finite).all():
        raise L1ComponentError(f"{label} contains nonfinite values")
    return result


def build_l1_simulator_components_v1(
    *,
    components: pd.DataFrame,
    game_ids: Sequence[object],
    team_ids: Sequence[object],
    game_totals: Sequence[object],
    n_sims: int,
    base_seed: int,
    ordinary_environment: Mapping[str, str] | None,
    source_identities: Mapping[str, Mapping[str, object]],
    usage_dirichlet_k: float,
    td_allocation_k: float | None = None,
    bigplay_rate: Sequence[object] | None = None,
) -> L1ComponentBanks:
    """Generate paired ordinary and L1-shootout conditional component banks."""
    if not isinstance(components, pd.DataFrame) or components.empty:
        raise L1ComponentError("components must be a nonempty frame")
    if list(components.columns) != list(COMPONENT_NAMES):
        raise L1ComponentError("component columns or order differ")
    if type(n_sims) is not int or n_sims < 100 or n_sims > 100_000:
        raise L1ComponentError("n_sims must be an integer in [100,100000]")
    if (
        not np.isfinite(usage_dirichlet_k)
        or usage_dirichlet_k <= 0.0
        or usage_dirichlet_k > 1_000.0
    ):
        raise L1ComponentError("usage Dirichlet k is outside (0,1000]")
    if td_allocation_k is not None and (
        not np.isfinite(td_allocation_k)
        or td_allocation_k <= 0.0
        or td_allocation_k > 1_000.0
    ):
        raise L1ComponentError("TD allocation k is outside (0,1000]")
    stable = canonicalize_simulation_components(components)
    games = _axis(game_ids, expected=len(stable), label="game IDs")
    teams = _axis(team_ids, expected=len(stable), label="team IDs")
    totals = _numeric_axis(
        game_totals, expected=len(stable), label="game totals"
    )
    bigplay = _numeric_axis(
        bigplay_rate, expected=len(stable), label="big-play rates"
    )
    for game in games.unique():
        if teams[games == game].nunique() != 2:
            raise L1ComponentError(
                "each L1 game must contain exactly two observed teams"
            )
    ordinary_env = _law_environment(ordinary_environment)
    shootout_env = dict(ordinary_env)
    shootout_env.update(SHOOTOUT_ENVIRONMENT)
    ordinary_seed = _derived_seed(base_seed, "ordinary")
    shootout_seed = _derived_seed(base_seed, "shootout")
    common = {
        "comps": stable,
        "n_sims": n_sims,
        "keep_draws": True,
        "game_ids": games,
        "team_ids": teams,
        "game_totals": totals,
        "bigplay_rate": bigplay,
    }
    ordinary_result = simulate(
        **common, seed=ordinary_seed, env=ordinary_env
    )
    shootout_result = simulate(
        **common,
        seed=shootout_seed,
        env=shootout_env,
        params={
            "usage_dirichlet_k": float(usage_dirichlet_k),
            **(
                {"td_alloc_k": float(td_allocation_k)}
                if td_allocation_k is not None else {}
            ),
        },
    )
    if ordinary_result.draws is None or shootout_result.draws is None:
        raise L1ComponentError("simulator did not retain component draws")
    ordinary = np.ascontiguousarray(ordinary_result.draws, dtype=np.float64)
    shootout = np.ascontiguousarray(shootout_result.draws, dtype=np.float64)
    if ordinary.shape != (len(stable), n_sims) or shootout.shape != ordinary.shape:
        raise L1ComponentError("simulator component-bank shape differs")
    body: dict[str, object] = {
        "schema": SCHEMA,
        "n_players": len(stable),
        "n_worlds": n_sims,
        "base_seed": base_seed,
        "ordinary_seed": ordinary_seed,
        "shootout_seed": shootout_seed,
        "component_sha256": simulation_component_sha256(stable),
        "game_ids_sha256": canonical_sha256(games.tolist()),
        "team_ids_sha256": canonical_sha256(teams.tolist()),
        "game_totals_sha256": canonical_sha256(
            [None if pd.isna(value) else float(value) for value in totals]
        ),
        "bigplay_rate_sha256": (
            None if bigplay is None else canonical_sha256(
                [None if pd.isna(value) else float(value) for value in bigplay]
            )
        ),
        "ordinary_environment": ordinary_env,
        "shootout_environment": shootout_env,
        "usage_dirichlet_k": float(usage_dirichlet_k),
        "td_allocation_k": (
            None if td_allocation_k is None else float(td_allocation_k)
        ),
        "ordinary_draws_sha256": player_world_matrix_sha256(ordinary),
        "shootout_draws_sha256": player_world_matrix_sha256(shootout),
        "source_identities": _source_identities(source_identities),
        "uses_lineup_outcomes": False,
        "calibration_labels_read": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    validate_l1_simulator_component_receipt(body)
    return L1ComponentBanks(ordinary, shootout, body)


def validate_l1_simulator_component_receipt(
    value: Mapping[str, object],
) -> dict[str, object]:
    if (
        not isinstance(value, Mapping)
        or frozenset(value) != _RECEIPT_KEYS
        or value.get("schema") != SCHEMA
    ):
        raise L1ComponentError("L1 component receipt schema differs")
    for flag in (
        "uses_lineup_outcomes", "calibration_labels_read",
        "historical_scoring_licensed", "production_change_licensed",
    ):
        if value.get(flag) is not False:
            raise L1ComponentError(f"L1 component {flag} boundary differs")
    shootout = value.get("shootout_environment")
    if not isinstance(shootout, Mapping) or any(
        shootout.get(key) != expected
        for key, expected in SHOOTOUT_ENVIRONMENT.items()
    ):
        raise L1ComponentError("L1 shootout environment differs")
    _source_identities(value.get("source_identities"))
    digest = value.get("receipt_sha256")
    body = dict(value)
    body.pop("receipt_sha256", None)
    if digest != canonical_sha256(body):
        raise L1ComponentError("L1 component receipt content hash differs")
    return dict(value)


__all__ = [
    "L1ComponentBanks",
    "L1ComponentError",
    "SHOOTOUT_ENVIRONMENT",
    "build_l1_simulator_components_v1",
    "validate_l1_simulator_component_receipt",
]
