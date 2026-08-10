"""Outcome-blind candidate-pool unions on immutable replay support masks.

The helper preserves the incumbent's candidate order, appends only genuinely
new rosters from a second panel, and reruns the production coverage selector.
It never regenerates worlds or changes the final entry count.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .tail_portfolio import select_slate


REQUIRED_COLUMNS = {
    "season", "week", "cand_ix", "players", "selected", "actual_score",
    "p_line", "sim_mean", "n_worlds", "clear_bits_194",
}
TAIL_ORDER = (240, 230, 220, 210)


def _validate_panel(name: str, rows: pd.DataFrame) -> None:
    missing = REQUIRED_COLUMNS - set(rows.columns)
    if missing:
        raise ValueError(f"{name} candidates missing {sorted(missing)}")
    if rows.empty:
        raise ValueError(f"{name} candidates are empty")
    keys = ["season", "week", "players"]
    if rows.duplicated(keys).any():
        raise ValueError(f"{name} has duplicate slate/roster keys")
    if pd.to_numeric(rows.actual_score, errors="coerce").isna().any():
        raise ValueError(f"{name} has missing actual scores")


def _assert_shared_worlds(source: pd.DataFrame, addon: pd.DataFrame) -> None:
    """Fail closed if a roster common to both panels is not identical."""
    paired = source.merge(
        addon, on=["season", "week", "players"], how="inner",
        suffixes=("_source", "_addon"), validate="one_to_one",
    )
    if paired.empty:
        raise ValueError("source and add-on have no shared candidates")
    for column, tolerance in (
        ("actual_score", 1e-8), ("p_line", 1e-8), ("sim_mean", 1e-5),
    ):
        left = pd.to_numeric(paired[f"{column}_source"], errors="coerce")
        right = pd.to_numeric(paired[f"{column}_addon"], errors="coerce")
        if left.isna().any() or right.isna().any() or (
                (left - right).abs() > tolerance).any():
            raise ValueError(f"shared candidates differ in {column}")
    if not paired.n_worlds_source.eq(paired.n_worlds_addon).all():
        raise ValueError("shared candidates differ in n_worlds")
    if not paired.clear_bits_194_source.eq(
            paired.clear_bits_194_addon).all():
        raise ValueError("shared candidates differ in 194 support worlds")


def select_candidate_union(
    source: pd.DataFrame,
    addon: pd.DataFrame,
    *,
    entry_count: int = 80,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Append add-on-only rosters and select an exact-size union portfolio.

    Source candidates always precede add-on candidates. That stable ordering
    is an explicit tie-break: an exactly equivalent new roster cannot evict
    an incumbent merely because it came from a later panel.
    """
    if entry_count <= 0:
        raise ValueError("entry_count must be positive")
    _validate_panel("source", source)
    _validate_panel("add-on", addon)
    _assert_shared_worlds(source, addon)

    source_slates = set(zip(source.season.astype(int), source.week.astype(int)))
    addon_slates = set(zip(addon.season.astype(int), addon.week.astype(int)))
    if source_slates != addon_slates:
        raise ValueError("source and add-on slate sets differ")

    union_parts: list[pd.DataFrame] = []
    audits: list[dict] = []
    for season, week in sorted(source_slates):
        src = source[
            source.season.astype(int).eq(season)
            & source.week.astype(int).eq(week)
        ].sort_values("cand_ix", kind="stable").copy()
        add = addon[
            addon.season.astype(int).eq(season)
            & addon.week.astype(int).eq(week)
        ].sort_values("cand_ix", kind="stable").copy()
        if int(src.selected.sum()) != entry_count:
            raise ValueError(
                f"source {season} week {week} does not select "
                f"exactly {entry_count}")
        source_rosters = set(src.players.astype(str))
        addon_rosters = set(add.players.astype(str))
        novel = add[~add.players.astype(str).isin(source_rosters)].copy()

        src["union_origin"] = "source"
        src["origin_cand_ix"] = src.cand_ix.astype(int)
        novel["union_origin"] = "addon"
        novel["origin_cand_ix"] = novel.cand_ix.astype(int)
        combined = pd.concat([src, novel], ignore_index=True, sort=False)
        if len(combined) < entry_count:
            raise ValueError(
                f"union {season} week {week} has fewer than {entry_count} "
                "candidates")
        combined["source_selected"] = (
            combined.players.astype(str).isin(
                set(src.loc[src.selected, "players"].astype(str))))
        combined["selected"] = False
        combined["cand_ix"] = np.arange(len(combined), dtype=int)
        ordered, _, picked = select_slate(
            combined, entry_count=entry_count, select_line=194.0)
        ordered["selected"] = False
        ordered.loc[picked, "selected"] = True
        if int(ordered.selected.sum()) != entry_count:
            raise ValueError(
                f"union {season} week {week} selector returned "
                f"{int(ordered.selected.sum())}, want {entry_count}")

        selected_rosters = set(
            ordered.loc[ordered.selected, "players"].astype(str))
        source_selected = set(src.loc[src.selected, "players"].astype(str))
        audits.append({
            "season": season,
            "week": week,
            "source_candidates": int(len(src)),
            "addon_candidates": int(len(add)),
            "shared_candidates": int(len(source_rosters & addon_rosters)),
            "novel_addon_candidates": int(len(novel)),
            "union_candidates": int(len(ordered)),
            "selected_entries": int(ordered.selected.sum()),
            "selected_from_addon": int(
                ((ordered.union_origin == "addon") & ordered.selected).sum()),
            "selected_shared_with_source_book": int(
                len(selected_rosters & source_selected)),
            "selected_source_only": int(
                len(source_selected - selected_rosters)),
            "selected_union_only": int(
                len(selected_rosters - source_selected)),
        })
        union_parts.append(ordered)
    return (
        pd.concat(union_parts, ignore_index=True),
        pd.DataFrame(audits),
    )


def tail_first_decision(source_metrics: dict, union_metrics: dict) -> dict:
    """Apply the frozen highest-threshold-first operator comparison."""
    deltas = {
        threshold: int(union_metrics[f"clear_{threshold}"])
        - int(source_metrics[f"clear_{threshold}"])
        for threshold in TAIL_ORDER
    }
    first_difference = next(
        (threshold for threshold in TAIL_ORDER if deltas[threshold] != 0),
        None,
    )
    improves_210_plus = any(delta > 0 for delta in deltas.values())
    promotion_candidate = bool(
        first_difference is not None
        and deltas[first_difference] > 0
        and improves_210_plus
    )
    return {
        "threshold_order": list(TAIL_ORDER),
        "deltas": {str(key): value for key, value in deltas.items()},
        "first_difference": first_difference,
        "improves_210_plus": improves_210_plus,
        "pareto_nonworse_210_plus": all(
            delta >= 0 for delta in deltas.values()),
        "promotion_candidate": promotion_candidate,
        "tie_through_210": first_difference is None,
    }
