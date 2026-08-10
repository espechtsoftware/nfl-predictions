"""Corrected-history confirmation of the frozen extreme-tail selector.

The selector itself was frozen for prospective 2026 shadows before this
confirmation was defined. This module applies it exactly once to the final
mechanically accepted corrected candidate pool and compares the resulting
80-entry book with the persisted 194-coverage book.
"""

from __future__ import annotations

import json
import re

import numpy as np
import pandas as pd

from ..bq import query_df
from ..config import settings
from .candidate_union import tail_first_decision
from .live_shadow_portfolios import (
    coverage_order,
    extreme_lexicographic_order,
)


EXPECTED_SLATES = 107
EXPECTED_ENTRIES = 80
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)
ALLOWED_TABLES = {"replay_candidates", "replay_candidates_staging"}


def _identifier(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid {label} {value!r}")
    return value


def load_panel(panel: str, table: str = "replay_candidates") -> pd.DataFrame:
    """Load one explicit eligible panel from an allowlisted warehouse table."""
    panel = _identifier(panel, "panel id")
    if table not in ALLOWED_TABLES:
        raise ValueError(f"invalid candidate table {table!r}")
    return query_df(f"""
      SELECT season, week, cand_ix, players, selected, selected_rank,
             actual_score, p_line, sim_mean, n_worlds,
             clear_bits_187, clear_bits_194, clear_bits_200,
             clear_bits_210, clear_bits_220
      FROM `{settings.predictions}.{table}`
      WHERE panel_run_id = '{panel}' AND research_eligible
      ORDER BY season, week, cand_ix
    """)


def _metrics(values: pd.Series) -> dict:
    numeric = pd.to_numeric(values, errors="raise").astype(float)
    return {
        **{
            f"clear_{threshold}": int(numeric.ge(threshold).sum())
            for threshold in THRESHOLDS
        },
        "mean_weekly_max": float(numeric.mean()),
        "median_weekly_max": float(numeric.median()),
    }


def evaluate_panel(
    rows: pd.DataFrame,
    *,
    expected_slates: int = EXPECTED_SLATES,
    entry_count: int = EXPECTED_ENTRIES,
) -> dict:
    """Validate and score the single frozen extreme-selector confirmation."""
    needed = {
        "season", "week", "cand_ix", "players", "selected", "actual_score",
        "p_line", "sim_mean", "n_worlds", "clear_bits_187",
        "clear_bits_194", "clear_bits_200", "clear_bits_210",
        "clear_bits_220",
    }
    missing = needed - set(rows.columns)
    if missing:
        raise ValueError(f"candidate rows missing {sorted(missing)}")
    if rows.empty:
        raise ValueError("candidate panel is empty")
    if rows.duplicated(["season", "week", "cand_ix"]).any():
        raise ValueError("candidate panel has duplicate candidate keys")
    if pd.to_numeric(rows.actual_score, errors="coerce").isna().any():
        raise ValueError("candidate panel has missing actual scores")

    slate_groups = list(rows.groupby(["season", "week"], sort=True))
    if len(slate_groups) != expected_slates:
        raise ValueError(
            f"candidate panel has {len(slate_groups)} slates, "
            f"expected {expected_slates}")

    weekly: list[dict] = []
    movement = 0
    for (season, week), slate in slate_groups:
        if int(slate.selected.astype(bool).sum()) != entry_count:
            raise ValueError(
                f"{season} week {week} does not have {entry_count} "
                "persisted selections")
        control, control_order = coverage_order(slate, 194.0)
        extreme, extreme_order = extreme_lexicographic_order(slate)
        if not control.cand_ix.equals(extreme.cand_ix):
            raise ValueError(f"{season} week {week} selector order mismatch")

        control_ix = np.asarray(control_order[:entry_count], dtype=int)
        extreme_ix = np.asarray(extreme_order[:entry_count], dtype=int)
        persisted = set(
            control.index[control.selected.astype(bool)].to_numpy(dtype=int))
        if persisted != set(control_ix.tolist()):
            raise ValueError(
                f"{season} week {week} does not reproduce persisted "
                "194-coverage selection")
        if len(set(extreme_ix.tolist())) != entry_count:
            raise ValueError(
                f"{season} week {week} extreme selector is not exact-"
                f"{entry_count}")

        actual = pd.to_numeric(control.actual_score, errors="raise").to_numpy(
            dtype=float)
        control_set = set(control_ix.tolist())
        extreme_set = set(extreme_ix.tolist())
        movement += len(control_set - extreme_set)
        weekly.append({
            "season": int(season),
            "week": int(week),
            "control_best": float(actual[control_ix].max()),
            "extreme_best": float(actual[extreme_ix].max()),
            "pool_oracle": float(actual.max()),
            "changed_slots_each_direction": int(
                len(control_set - extreme_set)),
        })

    weekly_frame = pd.DataFrame(weekly)
    control_metrics = _metrics(weekly_frame.control_best)
    extreme_metrics = _metrics(weekly_frame.extreme_best)
    oracle_metrics = _metrics(weekly_frame.pool_oracle)
    decision = tail_first_decision(control_metrics, extreme_metrics)

    by_season = []
    for season, group in weekly_frame.groupby("season", sort=True):
        by_season.append({
            "season": int(season),
            "control": _metrics(group.control_best),
            "extreme": _metrics(group.extreme_best),
        })
    delta = weekly_frame.extreme_best - weekly_frame.control_best
    return {
        "disposition": (
            "promote-extreme-selector"
            if decision["promotion_candidate"]
            else "keep-coverage194-selector"
        ),
        "mechanical_checks": {
            "complete_slates": len(weekly_frame),
            "entries_per_slate": entry_count,
            "persisted_control_reproduced": True,
            "nested_extreme_masks_valid": True,
            "fixed_candidate_pool": True,
        },
        "control": control_metrics,
        "extreme": extreme_metrics,
        "pool_oracle_identical": oracle_metrics,
        "tail_first_decision": decision,
        "paired": {
            "wins": int(delta.gt(0).sum()),
            "ties": int(delta.eq(0).sum()),
            "losses": int(delta.lt(0).sum()),
            "largest_gain": float(delta.max()),
            "largest_loss": float(delta.min()),
            "changed_slots_each_direction": int(movement),
        },
        "by_season": by_season,
    }


def run(panel: str, table: str = "replay_candidates") -> dict:
    report = evaluate_panel(load_panel(panel, table))
    report["panel_run_id"] = panel
    report["candidate_table"] = table
    print("EXTREME_SELECTOR_CONFIRMATION_JSON=" + json.dumps(
        report, sort_keys=True))
    return report
