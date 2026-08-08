"""Matched-control evaluation for proposed breakout mechanisms.

Winner anecdotes are discovery data, not evidence. This module matches every
signal-positive player to a same-slate, same-position signal-negative player
using pre-lock covariates only, then reports point and tail outcome deltas.
It deliberately never matches on outcome, player identity, or future data.
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np
import pandas as pd


DEFAULT_MATCH_COLUMNS = (
    "salary", "implied_team_total", "spread", "snap_share_l4",
    "target_share_l4", "carry_share_l4", "dk_points_l4",
)


def nearest_matched_controls(
    frame: pd.DataFrame,
    treatment_col: str,
    outcome_col: str = "y_dk_points",
    match_cols: Sequence[str] = DEFAULT_MATCH_COLUMNS,
    group_cols: Sequence[str] = ("season", "week", "position"),
    with_replacement: bool = False,
) -> pd.DataFrame:
    """Return one nearest pre-lock control for each treated player."""
    need = set(group_cols) | {treatment_col, outcome_col} | set(match_cols)
    missing = need - set(frame.columns)
    if missing:
        raise ValueError(f"matched-control frame missing {sorted(missing)}")
    df = frame.copy()
    for col in match_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    rows: list[dict] = []
    for group_key, group in df.groupby(list(group_cols), dropna=False):
        treated_mask = group[treatment_col].fillna(False).astype(bool)
        treated = group[treated_mask]
        controls = group[~treated_mask].copy()
        if treated.empty or controls.empty:
            continue
        # Scale inside the slate/position so salary units cannot dominate.
        center = group[list(match_cols)].median()
        scale = (group[list(match_cols)].quantile(0.75)
                 - group[list(match_cols)].quantile(0.25)).replace(0, 1).fillna(1)
        z = (group[list(match_cols)].fillna(center) - center) / scale
        available = set(controls.index)
        for ti in treated.index:
            pool = list(available if not with_replacement else controls.index)
            if not pool:
                break
            distance = ((z.loc[pool] - z.loc[ti]) ** 2).mean(axis=1)
            ci = distance.idxmin()
            if not with_replacement:
                available.remove(ci)
            key_values = (group_key if isinstance(group_key, tuple)
                          else (group_key,))
            row = dict(zip(group_cols, key_values))
            row.update({
                "treated_index": ti,
                "control_index": ci,
                "distance": float(distance.loc[ci]),
                "treated_outcome": float(df.loc[ti, outcome_col]),
                "control_outcome": float(df.loc[ci, outcome_col]),
                "outcome_delta": float(df.loc[ti, outcome_col]
                                       - df.loc[ci, outcome_col]),
            })
            for optional in ("gsis_id", "display_name"):
                if optional in df:
                    row[f"treated_{optional}"] = df.loc[ti, optional]
                    row[f"control_{optional}"] = df.loc[ci, optional]
            rows.append(row)
    return pd.DataFrame(rows)


def matched_report(pairs: pd.DataFrame, tail: float = 20.0) -> dict[str, float | int]:
    """Predeclared effect summaries; returns empty-safe diagnostics."""
    if pairs.empty:
        return {"n_pairs": 0, "mean_delta": float("nan"),
                "median_delta": float("nan"), "tail_lift": float("nan")}
    treated_tail = pairs.treated_outcome.ge(tail).mean()
    control_tail = pairs.control_outcome.ge(tail).mean()
    return {
        "n_pairs": int(len(pairs)),
        "mean_delta": float(pairs.outcome_delta.mean()),
        "median_delta": float(pairs.outcome_delta.median()),
        "treated_tail_rate": float(treated_tail),
        "control_tail_rate": float(control_tail),
        "tail_lift": float(treated_tail - control_tail),
    }
