"""Evaluate the one preregistered prior-season coverage-fit candidate union."""

from __future__ import annotations

import json

import pandas as pd

from ..bq import query_df
from ..config import settings
from .candidate_union import select_candidate_union, tail_first_decision
from .route_tail_union import (
    EXPECTED_ENTRIES,
    EXPECTED_SLATES,
    THRESHOLDS,
    TREATED_SEASONS,
    _identifier,
    load_panel,
)


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
        raise ValueError("panel is not a complete exact-entry 107-slate book")
    return selected.groupby(["season", "week"], as_index=False).agg(
        selected_best=("actual_score", "max"))


def load_coverage_signals(panel: str) -> pd.DataFrame:
    panel = _identifier(panel, "panel id")
    return query_df(f"""
      SELECT season, week, id, pos, fp_cov_receiver_source_season,
             fp_cov_defense_source_season, coverage_control_p30,
             coverage_treatment_p30, coverage_delta_30
      FROM `{settings.predictions}.slate_player_features`
      WHERE panel_run_id = '{panel}'
      QUALIFY ROW_NUMBER() OVER (
        PARTITION BY season, week, id ORDER BY generated_at DESC
      ) = 1
      ORDER BY season, week, id
    """)


def _has_coverage_tag(row: pd.Series) -> bool:
    if str(row.get("tag", "")) == "coverage_tail":
        return True
    try:
        tags = json.loads(str(row.get("all_tags", "[]")))
    except (TypeError, ValueError, json.JSONDecodeError):
        return False
    return isinstance(tags, list) and "coverage_tail" in tags


def mechanism_failures(
    source: pd.DataFrame,
    treatment: pd.DataFrame,
    signals: pd.DataFrame,
) -> list[str]:
    """Validate source containment, novelty and PIT signal before scores."""
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
    for (season, week), slate in treatment.groupby(
            ["season", "week"], sort=True):
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
        if want and not novel_slate.apply(_has_coverage_tag, axis=1).all():
            failures.append(
                f"{season} week {week} has a non-coverage novel row")

    feature_keys = ["season", "week", "id"]
    if signals.empty or signals.duplicated(feature_keys).any():
        failures.append("coverage signal snapshot is empty or duplicate")
        return failures
    delta = pd.to_numeric(
        signals.coverage_delta_30, errors="coerce").fillna(0.0)
    nonzero = signals[delta.ne(0)].copy()
    covered = signals[
        signals.fp_cov_receiver_source_season.notna()].copy()
    if not set(nonzero.season.astype(int)).issubset(TREATED_SEASONS):
        failures.append("coverage signal is nonzero outside 2024/2025")
    if not nonzero.pos.isin(["WR", "TE"]).all():
        failures.append("coverage signal is nonzero outside WR/TE")
    required = nonzero[[
        "fp_cov_receiver_source_season", "fp_cov_defense_source_season",
        "coverage_control_p30", "coverage_treatment_p30",
    ]]
    if required.isna().any().any():
        failures.append("nonzero coverage signal lacks provenance/probability")
    if covered[[
            "fp_cov_defense_source_season", "coverage_control_p30",
            "coverage_treatment_p30",
    ]].isna().any().any():
        failures.append("covered coverage signal lacks provenance/probability")
    if not covered.empty:
        target = covered.season.astype(int)
        if not covered.fp_cov_receiver_source_season.astype(int).eq(
                target - 1).all():
            failures.append("coverage receiver signal uses non-prior season")
        if not covered.fp_cov_defense_source_season.astype(int).eq(
                target - 1).all():
            failures.append("coverage defense signal uses non-prior season")
    covered_slates = set(map(
        tuple, covered[["season", "week"]].drop_duplicates().to_numpy()))
    expected_treated = set(map(tuple, treatment[
        treatment.season.astype(int).isin(TREATED_SEASONS)
    ][["season", "week"]].drop_duplicates().to_numpy()))
    if covered_slates != expected_treated:
        failures.append("coverage signal does not cover every treated slate")
    return failures


def _pool_oracle(rows: pd.DataFrame) -> dict:
    weekly = rows.groupby(["season", "week"], as_index=False).agg(
        best=("actual_score", "max"))
    if len(weekly) != EXPECTED_SLATES:
        raise ValueError("candidate pool is not a complete 107-slate panel")
    return _metrics(weekly.best)


def evaluate_union(
    source: pd.DataFrame,
    treatment: pd.DataFrame,
    signals: pd.DataFrame,
) -> dict:
    failures = mechanism_failures(source, treatment, signals)
    if failures:
        raise ValueError(
            "coverage union mechanism invalid: " + "; ".join(failures))
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
                f"coverage union does not reproduce {season} week {week} "
                "selection")

    source_metrics = _metrics(paired.selected_best_source)
    union_metrics = _metrics(paired.selected_best_union)
    decision = tail_first_decision(source_metrics, union_metrics)
    delta = paired.selected_best_union - paired.selected_best_source
    novel = treatment.merge(
        source[keys + ["players"]], on=keys + ["players"], how="left",
        indicator=True).query('_merge == "left_only"')
    season_deltas = {}
    for season, frame in paired.groupby("season", sort=True):
        season_deltas[str(int(season))] = {
            "source": _metrics(frame.selected_best_source),
            "union": _metrics(frame.selected_best_union),
        }
    return {
        "disposition": (
            "promote-coverage-tail-union"
            if decision["promotion_candidate"] else "keep-source-incumbent"
        ),
        "source": source_metrics,
        "union": union_metrics,
        "source_pool_oracle": _pool_oracle(source),
        "union_pool_oracle": _pool_oracle(union),
        "tail_first_decision": decision,
        "mechanical_checks": {
            "complete_slates": len(paired),
            "entries_per_slate": EXPECTED_ENTRIES,
            "source_contained": True,
            "shared_world_statistics_equal": True,
            "persisted_treatment_reproduced": True,
            "strict_prior_receiver_and_defense_signal": True,
        },
        "candidate_audit": {
            "source_candidates": int(audit.source_candidates.sum()),
            "novel_coverage_candidates": int(len(novel)),
            "selected_coverage_slots": int(audit.selected_from_addon.sum()),
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
        "season_diagnostics": season_deltas,
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
        load_coverage_signals(treatment_panel),
    )
    report["panels"] = {
        "source": source_panel,
        "treatment": treatment_panel,
        "source_table": source_table,
        "treatment_table": treatment_table,
    }
    print("COVERAGE_TAIL_UNION_JSON=" + json.dumps(report, sort_keys=True))
    return report
