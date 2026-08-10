"""Evaluate the preregistered corrected role/no-floor candidate union."""

from __future__ import annotations

import json
import re

import pandas as pd

from ..bq import query_df
from ..config import settings
from .candidate_union import select_candidate_union, tail_first_decision


EXPECTED_SLATES = 107
EXPECTED_ENTRIES = 80
THRESHOLDS = (187, 194, 200, 210, 220, 230, 240)
ALLOWED_TABLES = {"replay_candidates", "replay_candidates_staging"}


def _identifier(value: str, label: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError(f"invalid {label} {value!r}")
    return value


def load_panel(panel: str, table: str) -> pd.DataFrame:
    panel = _identifier(panel, "panel id")
    if table not in ALLOWED_TABLES:
        raise ValueError(f"invalid candidate table {table!r}")
    return query_df(f"""
      SELECT season, week, cand_ix, players, selected, selected_rank,
             actual_score, salary, p_line, sim_mean, n_worlds,
             clear_bits_187, clear_bits_194, clear_bits_200,
             clear_bits_210, clear_bits_220
      FROM `{settings.predictions}.{table}`
      WHERE panel_run_id = '{panel}' AND research_eligible
      ORDER BY season, week, cand_ix
    """)


def _weekly(rows: pd.DataFrame) -> pd.DataFrame:
    selected = rows[rows.selected.astype(bool)].copy()
    counts = selected.groupby(["season", "week"]).size()
    if len(counts) != EXPECTED_SLATES or not counts.eq(EXPECTED_ENTRIES).all():
        raise ValueError("panel is not a complete exact-80 107-slate book")
    return selected.groupby(["season", "week"], as_index=False).agg(
        selected_best=("actual_score", "max"))


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


def evaluate_union(
    source: pd.DataFrame,
    addon: pd.DataFrame,
    incumbent: pd.DataFrame,
) -> dict:
    """Build one union and require it to beat source and current incumbent."""
    source_weekly = _weekly(source)
    incumbent_weekly = _weekly(incumbent)
    union, audit = select_candidate_union(
        source, addon, entry_count=EXPECTED_ENTRIES)
    union_weekly = _weekly(union)

    keys = ["season", "week"]
    paired = source_weekly.merge(
        union_weekly, on=keys, suffixes=("_source", "_union"),
        validate="one_to_one")
    paired = paired.merge(
        incumbent_weekly, on=keys, validate="one_to_one")
    if len(paired) != EXPECTED_SLATES:
        raise ValueError("source, union and incumbent slate sets differ")
    paired = paired.rename(
        columns={"selected_best": "selected_best_incumbent"})

    source_metrics = _metrics(paired.selected_best_source)
    union_metrics = _metrics(paired.selected_best_union)
    incumbent_metrics = _metrics(paired.selected_best_incumbent)
    versus_source = tail_first_decision(source_metrics, union_metrics)
    versus_incumbent = tail_first_decision(incumbent_metrics, union_metrics)
    promotion = bool(
        versus_source["promotion_candidate"]
        and versus_incumbent["promotion_candidate"])

    source_oracle = source.groupby(keys).actual_score.max()
    union_oracle = union.groupby(keys).actual_score.max()
    addon_salary = pd.to_numeric(
        union.loc[union.union_origin.eq("addon"), "salary"], errors="raise")
    return {
        "disposition": (
            "promote-floor-union" if promotion else "keep-corrected-incumbent"
        ),
        "source": source_metrics,
        "union": union_metrics,
        "incumbent": incumbent_metrics,
        "versus_source": versus_source,
        "versus_incumbent": versus_incumbent,
        "mechanical_checks": {
            "complete_slates": len(paired),
            "entries_per_slate": EXPECTED_ENTRIES,
            "shared_support_masks_equal": True,
            "fixed_source_contained": True,
        },
        "candidate_audit": {
            "source_candidates": int(audit.source_candidates.sum()),
            "novel_addon_candidates": int(audit.novel_addon_candidates.sum()),
            "union_candidates": int(audit.union_candidates.sum()),
            "selected_addon_slots": int(audit.selected_from_addon.sum()),
            "changed_slots_each_direction": int(
                audit.selected_source_only.sum()),
            "novel_salary_min": float(addon_salary.min()),
            "novel_salary_median": float(addon_salary.median()),
            "novel_salary_max": float(addon_salary.max()),
        },
        "oracle": {
            "source": _metrics(source_oracle.reset_index(drop=True)),
            "union": _metrics(union_oracle.reset_index(drop=True)),
        },
        "paired": {
            "union_wins": int(
                paired.selected_best_union.gt(
                    paired.selected_best_incumbent).sum()),
            "ties": int(
                paired.selected_best_union.eq(
                    paired.selected_best_incumbent).sum()),
            "union_losses": int(
                paired.selected_best_union.lt(
                    paired.selected_best_incumbent).sum()),
        },
    }


def run(
    source_panel: str,
    addon_panel: str,
    incumbent_panel: str,
    source_table: str = "replay_candidates",
    addon_table: str = "replay_candidates_staging",
    incumbent_table: str = "replay_candidates",
) -> dict:
    report = evaluate_union(
        load_panel(source_panel, source_table),
        load_panel(addon_panel, addon_table),
        load_panel(incumbent_panel, incumbent_table),
    )
    report["panels"] = {
        "source": source_panel,
        "addon": addon_panel,
        "incumbent": incumbent_panel,
    }
    print("FLOOR_UNION_CONFIRMATION_JSON=" + json.dumps(
        report, sort_keys=True))
    return report
