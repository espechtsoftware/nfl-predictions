"""Point-in-time breakout archetypes for experiments and calibration.

These labels encode the mechanisms found in the winner/missed-player audit;
they are not predictions and are not production model inputs. Their first use
is stratified evaluation, matched controls, and optional Mondrian conformal
groups so a generic uncertainty increase cannot masquerade as useful signal.
"""

from __future__ import annotations

from collections.abc import Mapping

import pandas as pd


def _number(value, default: float = 0.0) -> float:
    if value is None or pd.isna(value):
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _flag(value) -> bool:
    return False if value is None or pd.isna(value) else bool(value)


def classify_breakout_state(row: Mapping) -> str:
    """Assign one deterministic state using only pre-lock columns."""
    pos = str(row.get("position", ""))
    salary = _number(row.get("salary"))
    cold = _flag(row.get("is_cold_start", False))
    depth_delta = _number(row.get("depth_rank_delta"))
    vac_t = _number(row.get("team_vacated_target_share"))
    vac_c = _number(row.get("team_vacated_carry_share"))
    target_jump = _number(row.get("target_share_jump"))
    carry_jump = _number(row.get("carry_share_jump"))
    snap_jump = _number(row.get("snap_share_jump"))
    snap_last = _number(row.get("snap_share_last"))
    spread = _number(row.get("spread"))
    implied = _number(row.get("implied_team_total"), 99.0)

    if pos == "DST" and salary and salary <= 3000:
        return "cheap_dst_tail"
    if cold:
        return "cold_start_or_rookie"
    if depth_delta > 0 or vac_t >= 0.10 or vac_c >= 0.12:
        return "vacancy_or_promotion"
    if target_jump >= 0.05 or carry_jump >= 0.08 or snap_jump >= 0.12:
        return "fast_role_rise"
    if snap_last >= 0.70 and (spread > 0 or implied < 22):
        return "secure_role_bad_environment"
    return "ordinary"


def conformal_labels(position: str, archetype: str) -> dict[str, str]:
    """Labels for ``OnlineConformalCalibrator`` with a declared fallback.

    Callers use hierarchy ``('position_archetype', 'position')``. Thin cells
    automatically fall back to position and then global calibration.
    """
    pos = str(position).upper()
    state = str(archetype)
    return {
        "position_archetype": f"{pos}:{state}",
        "position": pos,
        "breakout_archetype": state,
    }
