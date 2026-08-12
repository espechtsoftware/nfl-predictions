"""Guards for the active-only fitted-usage standing-law revalidation."""

from __future__ import annotations

import pandas as pd

from .served_position_lineup_v2 import comparison_report as _comparison_report
from .served_tail_lineup import ROLE_FEATURES, lever_values
from .usage_dirichlet_lineup_v2 import DISTRIBUTION_DERIVED_FEATURES


CONTROL_PANEL = "20260812-pitclean-e80-active-label-usage-multinomial-v1"
TREATMENT_PANEL = "20260812-pitclean-e80-selected-tabpfn-active-v2"
CACHE_TABLE = "tabpfn_active_label_treatment_v2"
FITTED_K = "28.154043586960896"
POSITION_SPECS = {
    2023: "QB:0.965,RB:0.99,TE:0.945,WR:1.03",
    2024: "QB:0.905,RB:0.97,TE:0.95,WR:1.06",
    2025: "QB:0.925,RB:0.96,TE:0.94,WR:1.04",
}
TAIL_ORDER = (240, 230, 220, 210, 200, 194, 187)


def _expected_common(position_spec: str) -> dict[str, str]:
    return {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": CACHE_TABLE,
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
        "ROLE_BELIEF_SEED": "7331",
        "REPLACEMENT_SLOTS": "12",
        "SERVED_POSITION_SCALES": position_spec,
    }


def mechanism_failures(
    control: pd.DataFrame,
    treatment: pd.DataFrame,
    feature_audit: dict,
    candidate_audit: dict,
    *,
    expected_code_sha: str,
) -> list[str]:
    """Require fitted usage allocation to be the sole arm difference."""
    failures: list[str] = []
    if control.empty or treatment.empty:
        return ["control or treatment panel is empty"]
    for name, rows in (("control", control), ("treatment", treatment)):
        if not rows.code_sha.astype(str).eq(expected_code_sha).all():
            failures.append(f"{name} code SHA differs from frozen generation")
        if set(rows.season.astype(int)) != set(POSITION_SPECS):
            failures.append(f"{name} does not contain the three evaluation seasons")
    if set(control.seeds.astype(str)) != set(treatment.seeds.astype(str)):
        failures.append("control and treatment seed identities differ")

    for season, position_spec in POSITION_SPECS.items():
        arm_levers: dict[str, dict[str, str]] = {}
        for name, rows in (("control", control), ("treatment", treatment)):
            values = {
                str(value) for value in rows.loc[
                    rows.season.astype(int).eq(season), "lever_env"
                ].dropna().unique()
            }
            if len(values) != 1:
                failures.append(f"{name} {season} has {len(values)} lever identities")
                continue
            levers = lever_values(next(iter(values)))
            arm_levers[name] = levers
            for key, value in _expected_common(position_spec).items():
                if levers.get(key) != value:
                    failures.append(f"{name} {season} {key} is not {value}")
        if set(arm_levers) != {"control", "treatment"}:
            continue
        control_levers = arm_levers["control"]
        treatment_levers = arm_levers["treatment"]
        if control_levers.get("GAME_SIM_USAGE", "").lower() not in {
                "", "0", "off", "false", "none"}:
            failures.append(f"control {season} usage is not multinomial")
        if "DIRICHLET_K" in control_levers:
            failures.append(f"control {season} unexpectedly persists DIRICHLET_K")
        if treatment_levers.get("GAME_SIM_USAGE") != "dirichlet":
            failures.append(f"treatment {season} usage is not dirichlet")
        if treatment_levers.get("DIRICHLET_K") != FITTED_K:
            failures.append(f"treatment {season} fitted K differs")
        treatment_other = {
            key: value for key, value in treatment_levers.items()
            if key not in {"GAME_SIM_USAGE", "DIRICHLET_K"}
        }
        if treatment_other != control_levers:
            failures.append(
                f"{season} arms differ beyond fitted usage allocation")

    if feature_audit.get("left_rows") != feature_audit.get("right_rows"):
        failures.append("control/treatment player-row counts differ")
    for field in ("left_only_rows", "right_only_rows", "mismatch_rows"):
        if feature_audit.get(field):
            failures.append(f"control/treatment player features differ in {field}")
    if float(feature_audit.get("max_numeric_abs_delta", 0.0)) > 1e-12:
        failures.append("control/treatment invariant player values differ")
    if set(feature_audit.get("ignored_numeric_fields", ())) != set(
            DISTRIBUTION_DERIVED_FEATURES):
        failures.append("feature audit exclusion set differs from protocol")

    if candidate_audit.get("paired_slates") != 54:
        failures.append("candidate audit does not cover 54 slates")
    if candidate_audit.get("common_rows", 0) <= 0:
        failures.append("control/treatment have no common candidates")
    if candidate_audit.get("common_actual_mismatch"):
        failures.append("common candidate actuals differ")
    if candidate_audit.get("common_sim_mean_mismatch"):
        failures.append("common candidate simulated means differ")
    if not (candidate_audit.get("left_only_rows", 0)
            or candidate_audit.get("right_only_rows", 0)):
        failures.append("fitted usage allocation did not change candidate membership")
    return failures


def comparison_report(
    historical: pd.DataFrame,
    control: pd.DataFrame,
    treatment: pd.DataFrame,
) -> dict:
    """Return the frozen decision plus mandatory decision-cost disclosure."""
    report = _comparison_report(historical, control, treatment)
    decision = report["decision"]
    exact_tie = int(decision["comparison"]) == 0
    if exact_tie:
        decision["treatment_selected"] = True
    decision["incumbent_retained_on_exact_tie"] = exact_tie

    crossings = []
    major = []
    for row in report["changed_weeks"]:
        left = float(row["selected_best_control"])
        right = float(row["selected_best_treatment"])
        gains = [threshold for threshold in TAIL_ORDER if left < threshold <= right]
        losses = [threshold for threshold in TAIL_ORDER if right < threshold <= left]
        if gains or losses:
            crossings.append({
                "season": int(row["season"]),
                "week": int(row["week"]),
                "control": left,
                "treatment": right,
                "gained_thresholds": gains,
                "lost_thresholds": losses,
            })
        if abs(float(row["selected_delta"])) >= 10:
            major.append({
                "season": int(row["season"]),
                "week": int(row["week"]),
                "control": left,
                "treatment": right,
                "delta": float(row["selected_delta"]),
            })
    report["decision_cost_disclosure"] = {
        "threshold_crossings": crossings,
        "absolute_weekly_deltas_at_least_10": major,
        "known_treatment_before_protocol": True,
        "payout_or_roi_imputed": False,
    }
    return report


__all__ = [
    "CACHE_TABLE",
    "CONTROL_PANEL",
    "DISTRIBUTION_DERIVED_FEATURES",
    "FITTED_K",
    "POSITION_SPECS",
    "TREATMENT_PANEL",
    "comparison_report",
    "mechanism_failures",
]
