"""Frozen exact-80 TD-ledger rank-coupling replay lever.

This research-only treatment keeps each incumbent final-served player
marginal bit-exact and replaces only its world order with the stable order
from an independently generated ``TD_LEDGER=1`` book.  It is deliberately
strict and off by default; the registered experiment is the only supported
configuration.
"""

from __future__ import annotations

from contextlib import contextmanager
from hashlib import sha256
import os
from typing import Iterator, Mapping

import numpy as np

from ..analysis.td_ledger_rank_coupling import rank_couple_marginals


TREATMENT_ENV = "TD_LEDGER_RANK_COUPLING"
ACTIVE_CACHE = "tabpfn_active_label_treatment_v2"
DIRICHLET_K = 28.154043586960896
ROLE_FEATURES = (
    "target_share_last",
    "carry_share_last",
    "snap_share_last",
    "target_share_jump",
    "carry_share_jump",
    "snap_share_jump",
)
SEED_PAIRS = {
    0: 7331,
    1137260708: 2690847602,
    2875959182: 1630284992,
    253722715: 3374646876,
    1643280042: 3977633467,
}
POSITION_SCHEDULES = {
    2023: "QB:0.965,RB:0.99,TE:0.945,WR:1.03",
    2024: "QB:0.905,RB:0.97,TE:0.95,WR:1.06",
    2025: "QB:0.925,RB:0.96,TE:0.94,WR:1.04",
}


def _enabled(value: object) -> bool:
    return str(value or "").strip().lower() not in {
        "", "0", "off", "false", "no", "none",
    }


def treatment_enabled(env: Mapping[str, str] | None = None) -> bool:
    source = os.environ if env is None else env
    return _enabled(source.get(TREATMENT_ENV))


def validate_frozen_environment(
    season: int,
    env: Mapping[str, str] | None = None,
) -> None:
    """Fail closed unless the process is the preregistered exact-80 arm."""
    source = os.environ if env is None else env
    if not treatment_enabled(source):
        return
    if season not in POSITION_SCHEDULES:
        raise ValueError("TD rank coupling season is outside 2023-2025")
    if _enabled(source.get("TD_LEDGER")):
        raise ValueError("TD rank coupling control cannot enable TD_LEDGER directly")
    incompatible = (
        "SIS_ASOE_TARGET_ALLOCATION",
        "ENSEMBLE_WORLD_MODE",
        "SCHAAKE_DIAG",
        "SCHAAKE_DIAG_ONLY",
        "N_ROUTE_TAIL",
        "N_COVERAGE_TAIL",
    )
    enabled = [name for name in incompatible if _enabled(source.get(name))]
    if enabled:
        raise ValueError(
            "TD rank coupling cannot compose with " + ",".join(enabled)
        )
    exact = {
        "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": ACTIVE_CACHE,
        "GAME_SIM_MODE": "possession",
        "GAME_SIM_USAGE": "dirichlet",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "REPLACEMENT_SLOTS": "12",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ",".join(ROLE_FEATURES),
        "SERVED_POSITION_SCALES": POSITION_SCHEDULES[season],
    }
    differences = {
        name: (source.get(name), expected)
        for name, expected in exact.items()
        if str(source.get(name, "")) != expected
    }
    if differences:
        raise ValueError(f"TD rank coupling frozen environment differs: {differences}")
    try:
        k = float(source.get("DIRICHLET_K", ""))
        baseline_seed = int(source.get("REPLAY_PROJECTION_SEED", "0") or 0)
        role_seed = int(source.get("ROLE_BELIEF_SEED", "7331") or 7331)
    except (TypeError, ValueError) as exc:
        raise ValueError("TD rank coupling K or seed is invalid") from exc
    if not np.isclose(k, DIRICHLET_K, rtol=0, atol=0):
        raise ValueError("TD rank coupling Dirichlet K differs")
    if SEED_PAIRS.get(baseline_seed) != role_seed:
        raise ValueError("TD rank coupling seed pair is not registered")


@contextmanager
def rank_source_environment(
    env: dict[str, str] | None = None,
) -> Iterator[None]:
    """Temporarily enable only the TD ledger for a rank-source replay."""
    target = os.environ if env is None else env
    if _enabled(target.get("TD_LEDGER")):
        raise ValueError("rank-source environment already has TD_LEDGER enabled")
    previous = target.get("TD_LEDGER")
    target["TD_LEDGER"] = "1"
    try:
        yield
    finally:
        if previous is None:
            target.pop("TD_LEDGER", None)
        else:
            target["TD_LEDGER"] = previous


def _draw_hash(values: np.ndarray) -> str:
    array = np.ascontiguousarray(values)
    return sha256(array.view(np.uint8)).hexdigest()


def rank_couple_final_served(
    control_draws: np.ndarray,
    rank_source_draws: np.ndarray,
    repeated_rank_source_draws: np.ndarray,
) -> tuple[np.ndarray, dict]:
    """Apply and validate the exact frozen final-served permutation."""
    control = np.asarray(control_draws)
    source = np.asarray(rank_source_draws)
    repeated_source = np.asarray(repeated_rank_source_draws)
    if control.ndim != 2 or source.shape != control.shape or (
        repeated_source.shape != control.shape
    ):
        raise ValueError("TD rank-coupling draw books do not align")
    if not (
        np.isfinite(control).all()
        and np.isfinite(source).all()
        and np.isfinite(repeated_source).all()
    ):
        raise ValueError("TD rank-coupling draw books contain nonfinite values")
    if not np.array_equal(source, repeated_source):
        raise ValueError("TD rank source is not bit-exact on repeat")

    treatment = rank_couple_marginals(control, source)
    repeated = rank_couple_marginals(control, repeated_source)
    exact_multisets = bool(np.array_equal(
        np.sort(control, axis=1, kind="stable"),
        np.sort(treatment, axis=1, kind="stable"),
    ))
    deterministic = bool(np.array_equal(treatment, repeated))
    changed = np.not_equal(control, treatment)
    changed_rows = int(np.count_nonzero(changed.any(axis=1)))
    changed_cells = int(np.count_nonzero(changed))
    maximum_mean_delta = float(np.max(np.abs(
        control.mean(axis=1, dtype=np.float64)
        - treatment.mean(axis=1, dtype=np.float64)
    ), initial=0.0))
    if not exact_multisets:
        raise ValueError("TD rank coupling changed a player marginal")
    if not deterministic:
        raise ValueError("TD rank coupling is not bit-exact on repeat")
    if maximum_mean_delta > 1e-10:
        raise ValueError(
            f"TD rank coupling changed a row mean by {maximum_mean_delta:.3g}"
        )
    if changed_rows == 0:
        raise ValueError("TD rank coupling changed no eligible player row")
    audit = {
        "control_sha256": _draw_hash(control),
        "rank_source_sha256": _draw_hash(source),
        "treatment_sha256": _draw_hash(treatment),
        "exact_sorted_draw_multisets": exact_multisets,
        "deterministic_output": deterministic,
        "maximum_mean_delta": maximum_mean_delta,
        "changed_rows": changed_rows,
        "changed_world_cells": changed_cells,
    }
    return treatment, audit


__all__ = [
    "POSITION_SCHEDULES",
    "SEED_PAIRS",
    "TREATMENT_ENV",
    "rank_couple_final_served",
    "rank_source_environment",
    "treatment_enabled",
    "validate_frozen_environment",
]
