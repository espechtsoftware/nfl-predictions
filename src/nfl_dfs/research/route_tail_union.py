"""Evaluate the one preregistered paid Route Share candidate union."""

from __future__ import annotations

import json
import re

import pandas as pd

from ..bq import query_df
from ..config import settings
from .candidate_union import select_candidate_union, tail_first_decision


EXPECTED_SLATES = 107
EXPECTED_ENTRIES = 80
TREATED_SEASONS = {2024, 2025}
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
    eligibility = "AND research_eligible" if table == "replay_candidates" else ""
    return query_df(f"""
      SELECT season, week, cand_ix, players, tag, all_tags, selected,
             selected_rank, actual_score, p_line, sim_mean, n_worlds,
             clear_bits_187, clear_bits_194, clear_bits_200,
             clear_bits_210, clear_bits_220,
             score_artifact_uri, score_artifact_sha256
      FROM `{settings.predictions}.{table}`
      WHERE panel_run_id = '{panel}' {eligibility}
      ORDER BY season, week, cand_ix
    """)


def load_route_signals(panel: str) -> pd.DataFrame:
    panel = _identifier(panel, "panel id")
    return query_df(f"""
      SELECT season, week, id, pos, fp_route_source_season,
             fp_route_source_week, route_control_p30,
             route_treatment_p30, route_delta_30
      FROM `{settings.predictions}.slate_player_features`
      WHERE panel_run_id = '{panel}'
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY season, week, id ORDER BY generated_at DESC
      ) = 1
      ORDER BY season, week, id
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


def _weekly(rows: pd.DataFrame) -> pd.DataFrame:
    selected = rows[rows.selected.astype(bool)].copy()
    counts = selected.groupby(["season", "week"]).size()
    if len(counts) != EXPECTED_SLATES or not counts.eq(EXPECTED_ENTRIES).all():
        raise ValueError("panel is not a complete exact-80 107-slate book")
    return selected.groupby(["season", "week"], as_index=False).agg(
        selected_best=("actual_score", "max"))


def _has_route_tag(row: pd.Series) -> bool:
    if str(row.get("tag", "")) == "route_tail":
        return True
    try:
        tags = json.loads(str(row.get("all_tags", "[]")))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return isinstance(tags, list) and "route_tail" in tags


def mechanism_failures(
    source: pd.DataFrame,
    treatment: pd.DataFrame,
    signals: pd.DataFrame,
) -> list[str]:
    """Validate the Route mechanism before any score comparison."""
    failures: list[str] = []
    candidate_keys = ["season", "week", "players"]
    for name, frame in (("source", source), ("treatment", treatment)):
        if frame.empty or frame.duplicated(candidate_keys).any():
            failures.append(f"{name} candidates are empty or duplicate")
        if frame.score_artifact_uri.fillna("").astype(str).str.strip().eq("").any():
            failures.append(f"{name} has missing score artifact URI")
        if frame.score_artifact_sha256.fillna("").astype(str).str.strip().eq("").any():
            failures.append(f"{name} has missing score artifact hash")
    if failures:
        return failures

    source_keys = set(map(tuple, source[candidate_keys].to_numpy()))
    treatment_keys = set(map(tuple, treatment[candidate_keys].to_numpy()))
    if not source_keys.issubset(treatment_keys):
        failures.append("treatment does not contain every source candidate")
    novel = treatment[
        ~treatment.set_index(candidate_keys).index.isin(source_keys)
    ].copy()
    for (season, week), slate in treatment.groupby(["season", "week"], sort=True):
        source_slate = source[
            source.season.eq(season) & source.week.eq(week)]
        novel_slate = novel[
            novel.season.eq(season) & novel.week.eq(week)]
        if source_slate.empty:
            failures.append(f"source missing {season} week {week}")
        want = 12 if int(season) in TREATED_SEASONS else 0
        if len(novel_slate) != want:
            failures.append(
                f"{season} week {week} has {len(novel_slate)} novel rows, "
                f"want {want}")
        if want and not novel_slate.apply(_has_route_tag, axis=1).all():
            failures.append(f"{season} week {week} has a non-Route novel row")

    feature_keys = ["season", "week", "id"]
    if signals.empty or signals.duplicated(feature_keys).any():
        failures.append("Route signal snapshot is empty or duplicate")
        return failures
    delta = pd.to_numeric(signals.route_delta_30, errors="coerce").fillna(0.0)
    nonzero = signals[delta.ne(0)].copy()
    covered = signals[signals.fp_route_source_season.notna()].copy()
    if not set(nonzero.season.astype(int)).issubset(TREATED_SEASONS):
        failures.append("Route signal is nonzero outside 2024/2025")
    if not nonzero.pos.isin(["RB", "WR", "TE"]).all():
        failures.append("Route signal is nonzero outside RB/WR/TE")
    required = nonzero[[
        "fp_route_source_season", "fp_route_source_week",
        "route_control_p30", "route_treatment_p30",
    ]]
    if required.isna().any().any():
        failures.append("nonzero Route signal lacks provenance/probability")
    if covered[[
            "fp_route_source_week", "route_control_p30",
            "route_treatment_p30",
    ]].isna().any().any():
        failures.append("covered Route signal lacks provenance/probability")
    if not nonzero.empty and not required.isna().any().any():
        source_order = (
            nonzero.fp_route_source_season.astype(int) * 100
            + nonzero.fp_route_source_week.astype(int))
        target_order = nonzero.season.astype(int) * 100 + nonzero.week.astype(int)
        if source_order.ge(target_order).any():
            failures.append("Route signal uses same/future week")
    covered_slates = set(map(tuple, covered[["season", "week"]].to_numpy()))
    expected_treated = set(map(tuple, treatment[
        treatment.season.astype(int).isin(TREATED_SEASONS)
    ][["season", "week"]].drop_duplicates().to_numpy()))
    if covered_slates != expected_treated:
        failures.append("Route signal does not cover every treated slate")
    return failures


def evaluate_union(
    source: pd.DataFrame,
    treatment: pd.DataFrame,
    signals: pd.DataFrame,
) -> dict:
    failures = mechanism_failures(source, treatment, signals)
    if failures:
        raise ValueError("Route union mechanism invalid: " + "; ".join(failures))
    source_weekly = _weekly(source)
    treatment_weekly = _weekly(treatment)
    union, audit = select_candidate_union(
        source, treatment, entry_count=EXPECTED_ENTRIES)
    union_weekly = _weekly(union)

    keys = ["season", "week"]
    paired = source_weekly.merge(
        union_weekly, on=keys, suffixes=("_source", "_union"),
        validate="one_to_one")
    paired = paired.merge(
        treatment_weekly.rename(
            columns={"selected_best": "selected_best_treatment"}),
        on=keys, validate="one_to_one")
    if len(paired) != EXPECTED_SLATES:
        raise ValueError("source, treatment and union slate sets differ")
    for season, week in paired[keys].itertuples(index=False):
        persisted = set(treatment[
            treatment.season.eq(season) & treatment.week.eq(week)
            & treatment.selected.astype(bool)
        ].players.astype(str))
        rebuilt = set(union[
            union.season.eq(season) & union.week.eq(week)
            & union.selected.astype(bool)
        ].players.astype(str))
        if persisted != rebuilt:
            raise ValueError(
                f"Route union does not reproduce {season} week {week} selection")

    source_metrics = _metrics(paired.selected_best_source)
    union_metrics = _metrics(paired.selected_best_union)
    decision = tail_first_decision(source_metrics, union_metrics)
    delta = paired.selected_best_union - paired.selected_best_source
    novel = treatment.merge(
        source[keys + ["players"]], on=keys + ["players"], how="left",
        indicator=True).query('_merge == "left_only"')
    return {
        "disposition": (
            "promote-route-tail-union"
            if decision["promotion_candidate"] else "keep-corrected-incumbent"
        ),
        "source": source_metrics,
        "union": union_metrics,
        "tail_first_decision": decision,
        "mechanical_checks": {
            "complete_slates": len(paired),
            "entries_per_slate": EXPECTED_ENTRIES,
            "source_contained": True,
            "shared_world_statistics_equal": True,
            "persisted_treatment_reproduced": True,
            "strict_prior_route_signal": True,
        },
        "candidate_audit": {
            "source_candidates": int(audit.source_candidates.sum()),
            "novel_route_candidates": int(len(novel)),
            "selected_route_slots": int(audit.selected_from_addon.sum()),
            "changed_slots_each_direction": int(
                audit.selected_source_only.sum()),
        },
        "paired": {
            "union_wins": int(delta.gt(0).sum()),
            "ties": int(delta.eq(0).sum()),
            "union_losses": int(delta.lt(0).sum()),
            "largest_gain": float(delta.max()),
            "largest_loss": float(delta.min()),
        },
    }


def run(
    source_panel: str,
    treatment_panel: str,
    source_table: str = "replay_candidates",
    treatment_table: str = "replay_candidates_staging",
) -> dict:
    report = evaluate_union(
        load_panel(source_panel, source_table),
        load_panel(treatment_panel, treatment_table),
        load_route_signals(treatment_panel),
    )
    report["panels"] = {
        "source": source_panel,
        "treatment": treatment_panel,
        "source_table": source_table,
        "treatment_table": treatment_table,
    }
    print("ROUTE_TAIL_UNION_JSON=" + json.dumps(report, sort_keys=True))
    return report
