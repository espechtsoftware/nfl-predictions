"""Frozen exact-80 competitive-WR TD allocation replay lever.

The treatment is deliberately unavailable unless both score-free stages have
been harvested and their immutable report identities are supplied by the
launcher.  It keeps every incumbent player marginal unchanged and permutes
only Stage-T-eligible WR rows with the preregistered centered TD priority.
"""

from __future__ import annotations

from hashlib import sha256
import os
import re
from typing import Mapping

import numpy as np
import pandas as pd

from ..analysis.td_competitive_wr_allocation import (
    apply_competitive_wr_allocation,
)
from . import td_ledger_rank_lineup as incumbent


TREATMENT_ENV = "TD_COMPETITIVE_WR_ALLOCATION"
REFERENCE_REPORT_SHA_ENV = "TD_COMP_WR_REFERENCE_REPORT_SHA256"
TREATMENT_REPORT_SHA_ENV = "TD_COMP_WR_TREATMENT_REPORT_SHA256"
PROTOCOL_SHA_ENV = "TD_COMP_WR_PROTOCOL_SHA256"
LICENSE_ENV = "TD_COMP_WR_EXACT80_LICENSED"

ACTIVE_CACHE = incumbent.ACTIVE_CACHE
DIRICHLET_K = incumbent.DIRICHLET_K
ROLE_FEATURES = incumbent.ROLE_FEATURES
SEED_PAIRS = incumbent.SEED_PAIRS
POSITION_SCHEDULES = incumbent.POSITION_SCHEDULES


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
    """Fail closed unless this is the licensed preregistered exact-80 arm."""
    source = os.environ if env is None else env
    if not treatment_enabled(source):
        return
    if _enabled(source.get(incumbent.TREATMENT_ENV)):
        raise ValueError("competitive-WR cannot compose with global TD ranks")
    incumbent.validate_frozen_environment(
        season,
        {**source, incumbent.TREATMENT_ENV: "1"},
    )
    if str(source.get(LICENSE_ENV, "")) != "1":
        raise ValueError("competitive-WR exact-80 score-free license is missing")
    for name in (
        REFERENCE_REPORT_SHA_ENV,
        TREATMENT_REPORT_SHA_ENV,
        PROTOCOL_SHA_ENV,
    ):
        if not re.fullmatch(r"[0-9a-f]{64}", str(source.get(name, ""))):
            raise ValueError(f"competitive-WR immutable identity is missing: {name}")


rank_source_environment = incumbent.rank_source_environment


def _draw_hash(values: np.ndarray) -> str:
    array = np.ascontiguousarray(values)
    return sha256(array.view(np.uint8)).hexdigest()


def allocate_final_served(
    control_draws: np.ndarray,
    rank_source_draws: np.ndarray,
    repeated_rank_source_draws: np.ndarray,
    frame: pd.DataFrame,
) -> tuple[np.ndarray, dict]:
    """Apply the frozen centered-WR permutation with exact invariants."""
    control = np.asarray(control_draws)
    source = np.asarray(rank_source_draws)
    repeated_source = np.asarray(repeated_rank_source_draws)
    if control.ndim != 2 or source.shape != control.shape or (
        repeated_source.shape != control.shape
    ):
        raise ValueError("competitive-WR draw books do not align")
    if not (
        np.isfinite(control).all()
        and np.isfinite(source).all()
        and np.isfinite(repeated_source).all()
    ):
        raise ValueError("competitive-WR draw books contain nonfinite values")
    if not np.array_equal(source, repeated_source):
        raise ValueError("competitive-WR TD rank source is not bit-exact on repeat")

    treatment, allocation, eligible = apply_competitive_wr_allocation(
        control, source, frame,
    )
    repeated, repeated_allocation, repeated_eligible = (
        apply_competitive_wr_allocation(control, repeated_source, frame)
    )
    changed_rows_mask = np.not_equal(control, treatment).any(axis=1)
    exact_multisets = bool(np.array_equal(
        np.sort(control, axis=1, kind="stable"),
        np.sort(treatment, axis=1, kind="stable"),
    ))
    deterministic = bool(
        np.array_equal(treatment, repeated)
        and allocation == repeated_allocation
        and np.array_equal(eligible, repeated_eligible)
    )
    maximum_mean_delta = float(np.max(np.abs(
        control.mean(axis=1, dtype=np.float64)
        - treatment.mean(axis=1, dtype=np.float64)
    ), initial=0.0))
    only_eligible_changed = bool(np.all(~changed_rows_mask | eligible))
    ineligible_exact = bool(np.array_equal(
        control[~eligible], treatment[~eligible],
    ))
    changed_rows = int(changed_rows_mask.sum())
    if not exact_multisets:
        raise ValueError("competitive-WR allocation changed a player marginal")
    if not deterministic:
        raise ValueError("competitive-WR allocation is not bit-exact on repeat")
    if maximum_mean_delta > 1e-10:
        raise ValueError(
            f"competitive-WR allocation changed a row mean by "
            f"{maximum_mean_delta:.3g}"
        )
    if not only_eligible_changed or not ineligible_exact:
        raise ValueError("competitive-WR allocation changed an ineligible row")
    if changed_rows == 0:
        raise ValueError("competitive-WR allocation changed no eligible WR row")

    audit = {
        **allocation,
        "control_sha256": _draw_hash(control),
        "rank_source_sha256": _draw_hash(source),
        "treatment_sha256": _draw_hash(treatment),
        "exact_sorted_draw_multisets": exact_multisets,
        "deterministic_output": deterministic,
        "maximum_mean_delta": maximum_mean_delta,
        "only_eligible_wr_rows_changed": only_eligible_changed,
        "all_ineligible_rows_bit_exact": ineligible_exact,
        "changed_rows": changed_rows,
        "changed_world_cells": int(np.not_equal(control, treatment).sum()),
    }
    return treatment, audit


__all__ = [
    "ACTIVE_CACHE",
    "DIRICHLET_K",
    "LICENSE_ENV",
    "POSITION_SCHEDULES",
    "PROTOCOL_SHA_ENV",
    "REFERENCE_REPORT_SHA_ENV",
    "ROLE_FEATURES",
    "SEED_PAIRS",
    "TREATMENT_ENV",
    "TREATMENT_REPORT_SHA_ENV",
    "allocate_final_served",
    "rank_source_environment",
    "treatment_enabled",
    "validate_frozen_environment",
]
