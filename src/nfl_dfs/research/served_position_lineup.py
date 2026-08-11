"""Pure guards and score summaries for the frozen position-scale replay."""

from __future__ import annotations

import pandas as pd

from .panel_compare import metrics, slate_scores
from .served_tail_lineup import (
    CANDIDATE_MEAN_ATOL,
    EVALUATION_SEASONS,
    HISTORICAL_SEASONS,
    ROLE_FEATURES,
    SOURCE_CODE_SHA,
    SOURCE_PANEL,
    SOURCE_SEASONS,
    expected_slate_pairs,
    lever_values,
    validate_candidate_panel,
)


CONTROL_PANEL = "20260811-lockfix-e80-k1-role12-position-control-v1"
TREATMENT_PANEL = "20260811-lockfix-e80-k1-role12-position-scales-v1"
POSITION_SPEC = "QB:0.970,RB:1.005,TE:0.940,WR:1.070"
TAIL_ORDER = (240, 230, 220, 210, 200)


def _frozen_levers() -> dict[str, str]:
    return {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331",
        "REPLACEMENT_SLOTS": "12",
    }


def mechanism_failures(
    source: pd.DataFrame,
    control: pd.DataFrame,
    treatment: pd.DataFrame,
    source_control_features: dict,
    control_treatment_features: dict,
    source_control_candidates: dict,
    control_treatment_candidates: dict,
    reproduction: dict,
    *,
    experiment_code_sha: str,
) -> list[str]:
    """Require factors to be the sole material control/treatment change."""
    failures: list[str] = []
    if source.empty or control.empty or treatment.empty:
        return failures
    if control.code_sha.iloc[0] != experiment_code_sha or \
            treatment.code_sha.iloc[0] != experiment_code_sha:
        failures.append("new panels do not share the immutable experiment code SHA")
    if not (source.seeds.iloc[0] == control.seeds.iloc[0]
            == treatment.seeds.iloc[0]):
        failures.append("source, control and treatment seed identities differ")

    source_levers = lever_values(source.lever_env.iloc[0])
    control_levers = lever_values(control.lever_env.iloc[0])
    treatment_levers = lever_values(treatment.lever_env.iloc[0])
    if control_levers.get("SERVED_POSITION_SCALES", "").lower() not in {
            "", "0", "off", "false", "identity", "none"}:
        failures.append("control served-position scale is not identity")
    if treatment_levers.get("SERVED_POSITION_SCALES") != POSITION_SPEC:
        failures.append("treatment served-position factors differ from frozen fit")
    for name, levers in (
        ("source", source_levers),
        ("control", control_levers),
        ("treatment", treatment_levers),
    ):
        for key, value in _frozen_levers().items():
            if levers.get(key) != value:
                failures.append(f"{name} {key} is not {value}")
    remove = {"SERVED_POSITION_SCALES"}
    control_other = {k: v for k, v in control_levers.items() if k not in remove}
    treatment_other = {
        k: v for k, v in treatment_levers.items() if k not in remove
    }
    if control_other != treatment_other:
        failures.append(
            "treatment changes replay levers other than served-position factors")
    source_other = {k: v for k, v in source_levers.items() if k not in remove}
    if source_other != control_other:
        failures.append("same-image control changes accepted-source replay levers")

    for name, audit in (
        ("source/control", source_control_features),
        ("control/treatment", control_treatment_features),
    ):
        if audit.get("left_rows") != audit.get("right_rows"):
            failures.append(f"{name} player-row counts differ")
        for field in ("left_only_rows", "right_only_rows", "mismatch_rows"):
            if audit.get(field):
                failures.append(f"{name} player snapshots differ in {field}")
        if float(audit.get("max_numeric_abs_delta", 0.0)) > 1e-12:
            failures.append(f"{name} player snapshot numeric values differ")

    for name, audit in (
        ("source/control", source_control_candidates),
        ("control/treatment", control_treatment_candidates),
    ):
        if audit.get("paired_slates") != 54:
            failures.append(f"{name} candidate audit does not cover 54 slates")
        if audit.get("common_rows", 0) <= 0:
            failures.append(f"{name} panels have no shared rosters")
        if audit.get("common_actual_mismatch"):
            failures.append(f"{name} shared candidate actuals differ")
        if audit.get("common_sim_mean_mismatch"):
            failures.append(f"{name} shared candidate means differ")
    if source_control_candidates.get("left_only_rows") or \
            source_control_candidates.get("right_only_rows"):
        failures.append("same-image control candidate pool differs from source")
    if int(reproduction.get("weekly_max_mismatches", -1)) != 0:
        failures.append("same-image control does not reproduce source weekly maxima")
    if int(reproduction.get("paired_slates", 0)) != 54:
        failures.append("source/control reproduction does not cover 54 slates")
    return failures


def tail_first_decision(control_metrics: dict, treatment_metrics: dict) -> dict:
    """Apply the operator's frozen 240/230/220/210/200 priority law."""
    deltas = {
        threshold: int(treatment_metrics[f"clear_{threshold}"])
        - int(control_metrics[f"clear_{threshold}"])
        for threshold in TAIL_ORDER
    }
    first = next(
        (threshold for threshold in TAIL_ORDER if deltas[threshold]), None)
    passes = first is not None and deltas[first] > 0
    return {
        "threshold_order": list(TAIL_ORDER),
        "deltas": {str(key): value for key, value in deltas.items()},
        "first_difference": first,
        "passes": passes,
        "neutral": first is None,
        "fails": first is not None and deltas[first] < 0,
    }


def combine_books(
    source_rows: pd.DataFrame,
    control_rows: pd.DataFrame,
    treatment_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Splice unchanged historical source with same-image evaluation books."""
    source = slate_scores(source_rows)
    history = source[source.season.isin(HISTORICAL_SEASONS)]
    control = pd.concat([history, slate_scores(control_rows)], ignore_index=True)
    treatment = pd.concat(
        [history, slate_scores(treatment_rows)], ignore_index=True)
    expected = expected_slate_pairs(SOURCE_SEASONS)
    for name, book in (("control", control), ("treatment", treatment)):
        got = set(zip(book.season.astype(int), book.week.astype(int)))
        if got != expected:
            raise ValueError(f"{name} is not the exact 107-slate book")
    return control, treatment


def comparison_report(
    source_rows: pd.DataFrame,
    control_rows: pd.DataFrame,
    treatment_rows: pd.DataFrame,
) -> dict:
    """Return frozen score decision plus secondary diagnostics."""
    control, treatment = combine_books(
        source_rows, control_rows, treatment_rows)
    control_metrics = metrics(control)
    treatment_metrics = metrics(treatment)
    decision = tail_first_decision(control_metrics, treatment_metrics)
    paired = control.merge(
        treatment, on=["season", "week"], suffixes=("_control", "_treatment"),
        validate="one_to_one")
    paired["selected_delta"] = (
        paired.selected_best_treatment - paired.selected_best_control)
    paired["oracle_delta"] = paired.oracle_treatment - paired.oracle_control
    changed = paired[
        paired.selected_delta.abs().gt(1e-9)
        | paired.oracle_delta.abs().gt(1e-9)
    ].sort_values(["selected_delta", "oracle_delta"], ascending=False)
    seasons = []
    for season in SOURCE_SEASONS:
        left = control[control.season.eq(season)]
        right = treatment[treatment.season.eq(season)]
        item: dict[str, int | float] = {
            "season": season,
            "slates": int(len(left)),
            "control_mean_best": float(left.selected_best.mean()),
            "treatment_mean_best": float(right.selected_best.mean()),
        }
        for threshold in (187, 194, 200, 210, 220, 230, 240):
            item[f"control_{threshold}"] = int(
                left.selected_best.ge(threshold).sum())
            item[f"treatment_{threshold}"] = int(
                right.selected_best.ge(threshold).sum())
        seasons.append(item)
    return {
        "control_metrics": control_metrics,
        "treatment_metrics": treatment_metrics,
        "evaluation_control_metrics": metrics(slate_scores(control_rows)),
        "evaluation_treatment_metrics": metrics(slate_scores(treatment_rows)),
        "season_metrics": seasons,
        "changed_weeks": changed.to_dict("records"),
        "tail_first_decision": decision,
    }
