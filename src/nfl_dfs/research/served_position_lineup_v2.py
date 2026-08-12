"""Pure guards and scoring law for PIT-clean position-scale Stage B."""

from __future__ import annotations

import pandas as pd

from .panel_compare import metrics, slate_scores
from .served_tail_lineup import (
    CANDIDATE_MEAN_ATOL,
    EVALUATION_SEASONS,
    HISTORICAL_SEASONS,
    ROLE_FEATURES,
    SOURCE_SEASONS,
    expected_slate_pairs,
    lever_values,
)


CONTROL_PANEL = "20260812-pitclean-e80-selected-position-control-v2"
TREATMENT_PANEL = "20260812-pitclean-e80-selected-position-scales-v2"
CACHE_TABLE = "tabpfn_projections_pit_v2"
TAIL_ORDER = (240, 230, 220, 210, 200, 194, 187)


def tail_first_decision(
    control_metrics: dict,
    treatment_metrics: dict,
) -> dict:
    """Apply the frozen seven-threshold law, then its mean-only tiebreaker."""
    deltas = {
        threshold: int(treatment_metrics[f"clear_{threshold}"])
        - int(control_metrics[f"clear_{threshold}"])
        for threshold in TAIL_ORDER
    }
    first = next(
        (threshold for threshold in TAIL_ORDER if deltas[threshold]), None)
    if first is not None:
        comparison = 1 if deltas[first] > 0 else -1
        tiebreaker = None
    else:
        mean_delta = (
            float(treatment_metrics["mean_best"])
            - float(control_metrics["mean_best"])
        )
        comparison = 1 if mean_delta > 1e-12 else -1 if mean_delta < -1e-12 else 0
        tiebreaker = "mean_best"
    return {
        "threshold_order": list(TAIL_ORDER),
        "deltas": {str(key): value for key, value in deltas.items()},
        "first_difference": first,
        "tiebreaker": tiebreaker,
        "comparison": comparison,
        "treatment_selected": comparison > 0,
    }


def _is_identity(value: str | None) -> bool:
    return str(value or "").lower() in {
        "", "0", "off", "false", "identity", "none",
    }


def _expected_replay_levers(*, base: str, role_selected: bool) -> dict[str, str]:
    expected = {
        "GAME_SIM_MODE": "possession",
        "N_CE": "0",
        "N_EPISTEMIC": "12" if role_selected else "0",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": CACHE_TABLE,
    }
    if base == "k1":
        expected["MODEL_ENSEMBLE"] = "1"
    elif base != "k3":
        raise ValueError(f"unknown selected base {base!r}")
    if role_selected:
        expected.update({
            "EPISTEMIC_FAMILY": "role_draws",
            "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
            "ROLE_BELIEF_SEED": "7331",
            "REPLACEMENT_SLOTS": "12",
        })
    return expected


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
    expected_code_sha: str,
    position_spec: str,
    base: str,
    role_selected: bool,
) -> list[str]:
    """Require the fitted position factors to be the only material change."""
    failures: list[str] = []
    if source.empty or control.empty or treatment.empty:
        return failures
    for name, rows in (
        ("source", source), ("control", control), ("treatment", treatment),
    ):
        if not rows.code_sha.astype(str).eq(expected_code_sha).all():
            failures.append(f"{name} code SHA differs from frozen generation")
    if not (source.seeds.iloc[0] == control.seeds.iloc[0]
            == treatment.seeds.iloc[0]):
        failures.append("source, control and treatment seed identities differ")

    source_levers = lever_values(source.lever_env.iloc[0])
    control_levers = lever_values(control.lever_env.iloc[0])
    treatment_levers = lever_values(treatment.lever_env.iloc[0])
    if not _is_identity(source_levers.get("SERVED_POSITION_SCALES")):
        failures.append("source served-position scale is not identity")
    if not _is_identity(control_levers.get("SERVED_POSITION_SCALES")):
        failures.append("control served-position scale is not identity")
    if treatment_levers.get("SERVED_POSITION_SCALES") != position_spec:
        failures.append("treatment served-position factors differ from repaired fit")

    expected = _expected_replay_levers(
        base=base, role_selected=role_selected)
    for name, levers in (
        ("source", source_levers),
        ("control", control_levers),
        ("treatment", treatment_levers),
    ):
        for key, value in expected.items():
            if levers.get(key) != value:
                failures.append(f"{name} {key} is not {value}")
        if base == "k3" and levers.get("MODEL_ENSEMBLE") not in {None, "3"}:
            failures.append(f"{name} MODEL_ENSEMBLE is not canonical K3")
        if not role_selected:
            unexpected = {
                "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES",
                "ROLE_BELIEF_SEED", "REPLACEMENT_SLOTS",
            } & set(levers)
            if unexpected:
                failures.append(
                    f"{name} has unexpected role levers {sorted(unexpected)}")

    remove = {"SERVED_POSITION_SCALES"}
    source_other = {k: v for k, v in source_levers.items() if k not in remove}
    control_other = {k: v for k, v in control_levers.items() if k not in remove}
    treatment_other = {
        k: v for k, v in treatment_levers.items() if k not in remove
    }
    if source_other != control_other:
        failures.append("same-image control changes selected-source replay levers")
    if control_other != treatment_other:
        failures.append(
            "treatment changes replay levers other than served-position factors")

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


def combine_books(
    source_rows: pd.DataFrame,
    control_rows: pd.DataFrame,
    treatment_rows: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Splice unchanged selected-source history onto the evaluation books."""
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
    """Return the frozen score decision and secondary season diagnostics."""
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
            "control_mean_best": float(left.selected_best.mean()),
            "treatment_mean_best": float(right.selected_best.mean()),
        }
        for threshold in TAIL_ORDER[::-1]:
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
        "decision": decision,
    }
