"""Panel-level matched controls for preregistered breakout archetypes.

This is deliberately an analysis path, not a model feature.  Each archetype
is compared with ordinary players of the same slate and position on pre-lock
salary, environment, trailing role, and production.  Results remain
descriptive until they transport through the scoring ladder.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd

from ..research.breakout_state import classify_breakout_state
from ..research.matched_controls import (
    DEFAULT_MATCH_COLUMNS,
    matched_report,
    nearest_matched_controls,
)


REQUIRED_SNAPSHOT_COLUMNS = {
    "season", "week", "slate_run_id", "id", "gsis_id", "name", "pos",
    "salary", "actual", "implied_team_total", "spread", "snap_share_l4",
    "target_share_l4", "carry_share_l4", "dk_points_l4",
    "target_share_last", "carry_share_last", "snap_share_last",
    "target_share_jump", "carry_share_jump", "snap_share_jump",
    "is_cold_start", "depth_rank_delta", "team_vacated_target_share",
    "team_vacated_carry_share",
}


def prepare_archetype_frame(features: pd.DataFrame) -> pd.DataFrame:
    """Validate an immutable snapshot and assign point-in-time states."""
    missing = REQUIRED_SNAPSHOT_COLUMNS - set(features.columns)
    if missing:
        raise ValueError(
            "panel snapshot predates archetype fields: " + ", ".join(sorted(missing))
        )
    out = features.copy()
    out["position"] = out["pos"]
    out["display_name"] = out["name"]
    out["y_dk_points"] = pd.to_numeric(out["actual"], errors="coerce")
    out = out[out.y_dk_points.notna()].copy()
    out["breakout_archetype"] = out.apply(classify_breakout_state, axis=1)
    return out


def matched_archetype_pairs(features: pd.DataFrame) -> pd.DataFrame:
    """Match each nonordinary state only to ordinary same-slate controls."""
    frame = prepare_archetype_frame(features)
    rows: list[pd.DataFrame] = []
    states = sorted(set(frame.breakout_archetype) - {"ordinary"})
    for state in states:
        subset = frame[frame.breakout_archetype.isin((state, "ordinary"))].copy()
        subset["is_treatment"] = subset.breakout_archetype.eq(state)
        pairs = nearest_matched_controls(
            subset,
            "is_treatment",
            outcome_col="y_dk_points",
            match_cols=DEFAULT_MATCH_COLUMNS,
            group_cols=("season", "week", "slate_run_id", "position"),
        )
        if not pairs.empty:
            pairs.insert(0, "breakout_archetype", state)
            rows.append(pairs)
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def summarize_archetype_pairs(
    pairs: pd.DataFrame, tail: float = 20.0
) -> pd.DataFrame:
    """One preregistered point/tail report per archetype."""
    rows: list[dict] = []
    if pairs.empty:
        return pd.DataFrame()
    for state, group in pairs.groupby("breakout_archetype"):
        report = matched_report(group, tail=tail)
        report.update({
            "breakout_archetype": state,
            "tail_threshold": float(tail),
            "n_seasons": int(group.season.nunique()),
            "n_slates": int(group[["season", "week", "slate_run_id"]]
                            .drop_duplicates().shape[0]),
        })
        rows.append(report)
    return pd.DataFrame(rows).sort_values("breakout_archetype")


def run(panel_run_id: str, tail: float = 20.0) -> dict:
    """Persist matched pairs and summaries from one accepted panel."""
    from ..bq import load_dataframe, query_df
    from ..config import settings

    features = query_df(
        f"""SELECT *
            FROM `{settings.predictions}.slate_player_features`
            WHERE panel_run_id=@panel AND research_eligible""",
        params={"panel": panel_run_id},
    )
    if features.empty:
        raise RuntimeError(f"accepted panel snapshots unavailable for {panel_run_id}")
    pairs = matched_archetype_pairs(features)
    summary = summarize_archetype_pairs(pairs, tail=tail)
    if pairs.empty:
        raise RuntimeError(f"no matchable archetype pairs for {panel_run_id}")
    generated_at = datetime.now(timezone.utc)
    for frame in (pairs, summary):
        frame.insert(0, "generated_at", generated_at)
        frame.insert(1, "panel_run_id", panel_run_id)
    load_dataframe(
        pairs,
        f"{settings.predictions}.archetype_matched_pairs",
        write_disposition="WRITE_APPEND",
    )
    load_dataframe(
        summary,
        f"{settings.predictions}.archetype_matched_summary",
        write_disposition="WRITE_APPEND",
    )
    return {
        "pairs": int(len(pairs)),
        "archetypes": int(summary.breakout_archetype.nunique()),
        "summary": summary.drop(columns=["generated_at", "panel_run_id"])
        .to_dict("records"),
    }
