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
SERVED_SCHEMA: Final = "corpus-r6-l1-served-components/v1"
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
_SERVED_RECEIPT_KEYS: Final = frozenset({
    "schema", "n_players", "n_worlds", "projection_seed",
    "component_receipt_sha256", "ordinary_served_authority_sha256",
    "ordinary_reconstructed_sha256", "shootout_served_sha256",
    "ordinary_exact_byte_parity", "positions_sha256", "player_keys_sha256",
    "market_points_sha256", "served_environment",
    "served_environment_sha256", "served_pipeline",
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


@dataclass(frozen=True, slots=True)
class L1ServedComponentBanks:
    """Exact incumbent ordinary worlds plus final-served shootout worlds."""

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
    paired_projection_seed: int | None = None,
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
    if paired_projection_seed is None:
        ordinary_seed = _derived_seed(base_seed, "ordinary")
        shootout_seed = _derived_seed(base_seed, "shootout")
    else:
        if type(paired_projection_seed) is not int or paired_projection_seed < 0:
            raise L1ComponentError(
                "paired projection seed must be a nonnegative integer"
            )
        if base_seed != paired_projection_seed:
            raise L1ComponentError(
                "base seed must equal the paired projection seed"
            )
        ordinary_seed = paired_projection_seed
        shootout_seed = paired_projection_seed
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


def _player_keys_sha256(keys: pd.DataFrame) -> str:
    records: list[dict[str, object]] = []
    for row in keys.itertuples(index=False, name=None):
        record: dict[str, object] = {}
        for column, value in zip(keys.columns, row, strict=True):
            if pd.isna(value):
                value = None
            elif isinstance(value, (np.bool_, bool)):
                value = bool(value)
            elif isinstance(value, np.integer):
                value = int(value)
            elif isinstance(value, np.floating):
                value = float(value)
            else:
                value = str(value)
            record[str(column)] = value
        records.append(record)
    return canonical_sha256(records)


def _market_sha256(values: np.ndarray) -> str:
    return canonical_sha256([
        None if np.isnan(value) else float(value) for value in values
    ])


def _serve_historical_replay_worlds(
    raw_draws: np.ndarray,
    *,
    positions: pd.Series,
    player_keys: pd.DataFrame,
    market_points: np.ndarray,
    projection_seed: int,
    environment: Mapping[str, str],
    tabpfn_cache_rows: pd.DataFrame | None,
) -> np.ndarray:
    """Run the exact historical replay post-simulator serving sequence.

    ``replay_projections`` freezes the shaped matrix to float32 before the
    market mean shift.  The final engine artifact freezes to float32 again
    after the global and position spread scales.  Both boundaries are
    material: omitting either can make a superficially close reconstruction
    differ from the retained R6 bank.
    """
    from ..backtest.replay import (
        apply_draw_shape,
        apply_served_position_scales,
        apply_served_tail_scale,
    )
    from ..models.blend import (
        blend,
        effective_model_weight,
        shift_draws_to_means,
    )

    shaped = apply_draw_shape(
        np.asarray(raw_draws, dtype=np.float64),
        positions,
        projection_seed,
        keys=player_keys,
        env=dict(environment),
        tabpfn_cache_rows=tabpfn_cache_rows,
    )
    shaped = np.ascontiguousarray(shaped, dtype=np.float32)
    model_points_pre = shaped.mean(axis=1, dtype=np.float64)
    blended = blend(
        model_points_pre,
        market_points,
        effective_model_weight(dict(environment)),
    )
    served = shift_draws_to_means(shaped, blended)
    served = apply_served_tail_scale(served, positions, env=dict(environment))
    served = apply_served_position_scales(
        served, positions, env=dict(environment)
    )
    return np.ascontiguousarray(served, dtype=np.float32)


def build_l1_served_components_v1(
    *,
    component_banks: L1ComponentBanks,
    ordinary_served_authority: np.ndarray,
    positions: Sequence[object],
    player_keys: pd.DataFrame,
    market_points: Sequence[object],
    projection_seed: int,
    served_environment: Mapping[str, str] | None,
    tabpfn_cache_rows: pd.DataFrame | None,
    source_identities: Mapping[str, Mapping[str, object]],
) -> L1ServedComponentBanks:
    """Admit an L1 shootout bank only after exact ordinary-bank parity.

    The retained R6 ordinary matrix is authority.  Re-running only
    :func:`simulate` is insufficient because incumbent worlds subsequently
    pass through marginal shaping, the model/market mean blend, the final
    global tail scale, the adopted position scales, and two float32 freeze
    boundaries.  This adapter applies that complete historical replay path to
    both raw component banks and refuses to expose the shootout component
    unless the reconstructed ordinary bytes equal the retained authority.

    The eventual game/world mixture must use ``ordinary_draws`` returned here
    (the authority bytes), never the reconstructed copy.  Consequently a
    zero shootout probability is an exact no-op, while positive probability
    can replace only the game/world cells selected by the L1 mixture law.
    """
    receipt = validate_l1_simulator_component_receipt(component_banks.receipt)
    if type(projection_seed) is not int or projection_seed < 0:
        raise L1ComponentError("projection seed must be a nonnegative integer")
    if (
        receipt.get("ordinary_seed") != projection_seed
        or receipt.get("shootout_seed") != projection_seed
    ):
        raise L1ComponentError(
            "raw component banks were not paired on the exact projection seed"
        )
    raw_ordinary = np.asarray(component_banks.ordinary_draws)
    raw_shootout = np.asarray(component_banks.shootout_draws)
    authority = np.asarray(ordinary_served_authority)
    if (
        raw_ordinary.ndim != 2
        or raw_shootout.shape != raw_ordinary.shape
        or authority.shape != raw_ordinary.shape
        or authority.dtype != np.dtype(np.float32)
        or not np.isfinite(raw_ordinary).all()
        or not np.isfinite(raw_shootout).all()
        or not np.isfinite(authority).all()
    ):
        raise L1ComponentError(
            "raw and retained served matrices must be finite, aligned, and "
            "the retained authority must be float32"
        )
    n_players, n_worlds = raw_ordinary.shape
    labels = _axis(positions, expected=n_players, label="positions").str.upper()
    if not labels.isin(("QB", "RB", "WR", "TE")).all():
        raise L1ComponentError("served L1 positions must be QB/RB/WR/TE")
    if not isinstance(player_keys, pd.DataFrame) or len(player_keys) != n_players:
        raise L1ComponentError("player keys must align with component rows")
    required_keys = ("season", "week", "gsis_id")
    if not set(required_keys).issubset(player_keys.columns):
        raise L1ComponentError(
            "player keys must include season, week, and gsis_id"
        )
    keys = player_keys.reset_index(drop=True).copy(deep=True)
    if keys.loc[:, list(required_keys)].isna().any().any():
        raise L1ComponentError("player keys contain missing identities")
    if keys.duplicated(["season", "week", "gsis_id"]).any():
        raise L1ComponentError("player keys repeat a player-week identity")
    slate_keys = keys[["season", "week"]].drop_duplicates()
    if len(slate_keys) != 1:
        raise L1ComponentError("served L1 adapter requires exactly one slate")
    try:
        market = pd.to_numeric(
            pd.Series(list(market_points)), errors="raise"
        ).to_numpy(dtype=np.float64)
    except (TypeError, ValueError) as exc:
        raise L1ComponentError("market points differ") from exc
    if market.shape != (n_players,) or np.isinf(market).any():
        raise L1ComponentError(
            "market points must align and contain only finite values or NaN"
        )
    environment = _law_environment(served_environment)
    if receipt.get("ordinary_environment") != environment:
        raise L1ComponentError(
            "served environment differs from the raw ordinary component law"
        )
    if environment.get("TABPFN_MARGINALS", "") not in ("", "0"):
        if not isinstance(tabpfn_cache_rows, pd.DataFrame):
            raise L1ComponentError(
                "enabled TabPFN shaping requires explicit frozen cache rows"
            )
    elif tabpfn_cache_rows is not None and not isinstance(
        tabpfn_cache_rows, pd.DataFrame
    ):
        raise L1ComponentError("TabPFN cache rows must be a dataframe or None")

    reconstructed = _serve_historical_replay_worlds(
        raw_ordinary,
        positions=labels,
        player_keys=keys,
        market_points=market,
        projection_seed=projection_seed,
        environment=environment,
        tabpfn_cache_rows=tabpfn_cache_rows,
    )
    if reconstructed.tobytes(order="C") != authority.tobytes(order="C"):
        delta = float(np.max(np.abs(
            reconstructed.astype(np.float64) - authority.astype(np.float64)
        )))
        raise L1ComponentError(
            "ordinary final-served reconstruction differs from the retained "
            f"bank (max_abs_delta={delta:.9g}); shootout bank is inadmissible"
        )
    shootout = _serve_historical_replay_worlds(
        raw_shootout,
        positions=labels,
        player_keys=keys,
        market_points=market,
        projection_seed=projection_seed,
        environment=environment,
        tabpfn_cache_rows=tabpfn_cache_rows,
    )
    sources = _source_identities(source_identities)
    body: dict[str, object] = {
        "schema": SERVED_SCHEMA,
        "n_players": n_players,
        "n_worlds": n_worlds,
        "projection_seed": projection_seed,
        "component_receipt_sha256": receipt["receipt_sha256"],
        "ordinary_served_authority_sha256": player_world_matrix_sha256(
            authority
        ),
        "ordinary_reconstructed_sha256": player_world_matrix_sha256(
            reconstructed
        ),
        "shootout_served_sha256": player_world_matrix_sha256(shootout),
        "ordinary_exact_byte_parity": True,
        "positions_sha256": canonical_sha256(labels.tolist()),
        "player_keys_sha256": _player_keys_sha256(keys),
        "market_points_sha256": _market_sha256(market),
        "served_environment": environment,
        "served_environment_sha256": canonical_sha256(environment),
        "served_pipeline": [
            "apply_draw_shape",
            "historical_replay_float32_freeze",
            "market_mean_blend",
            "apply_served_tail_scale",
            "apply_served_position_scales",
            "engine_float32_freeze",
        ],
        "source_identities": sources,
        "uses_lineup_outcomes": False,
        "calibration_labels_read": False,
        "historical_scoring_licensed": False,
        "production_change_licensed": False,
    }
    body["receipt_sha256"] = canonical_sha256(body)
    validate_l1_served_component_receipt(body)
    ordinary = np.ascontiguousarray(authority, dtype=np.float32)
    return L1ServedComponentBanks(ordinary, shootout, body)


def validate_l1_served_component_receipt(
    value: Mapping[str, object],
) -> dict[str, object]:
    if (
        not isinstance(value, Mapping)
        or frozenset(value) != _SERVED_RECEIPT_KEYS
        or value.get("schema") != SERVED_SCHEMA
    ):
        raise L1ComponentError("L1 served-component receipt schema differs")
    if value.get("ordinary_exact_byte_parity") is not True:
        raise L1ComponentError("L1 ordinary served parity was not exact")
    if value.get("served_pipeline") != [
        "apply_draw_shape",
        "historical_replay_float32_freeze",
        "market_mean_blend",
        "apply_served_tail_scale",
        "apply_served_position_scales",
        "engine_float32_freeze",
    ]:
        raise L1ComponentError("L1 served pipeline differs")
    environment = value.get("served_environment")
    if (
        not isinstance(environment, Mapping)
        or value.get("served_environment_sha256")
        != canonical_sha256(dict(environment))
    ):
        raise L1ComponentError("L1 served environment identity differs")
    for flag in (
        "uses_lineup_outcomes", "calibration_labels_read",
        "historical_scoring_licensed", "production_change_licensed",
    ):
        if value.get(flag) is not False:
            raise L1ComponentError(f"L1 served {flag} boundary differs")
    _source_identities(value.get("source_identities"))
    digest = value.get("receipt_sha256")
    body = dict(value)
    body.pop("receipt_sha256", None)
    if digest != canonical_sha256(body):
        raise L1ComponentError("L1 served receipt content hash differs")
    return dict(value)


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
    "L1ServedComponentBanks",
    "SHOOTOUT_ENVIRONMENT",
    "build_l1_simulator_components_v1",
    "build_l1_served_components_v1",
    "validate_l1_simulator_component_receipt",
    "validate_l1_served_component_receipt",
]
