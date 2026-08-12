"""Pure guards for the PIT-clean TabPFN SCHED exact-80 comparison."""

from __future__ import annotations

import pandas as pd

from .served_position_lineup_v2 import comparison_report, tail_first_decision
from .served_tail_lineup import ROLE_FEATURES, lever_values
from .tabpfn_active_label_lineup_v2 import DISTRIBUTION_DERIVED_FEATURES


CONTROL_PANEL = "20260812-pitclean-e80-selected-tabpfn-sched-control-v1"
TREATMENT_PANEL = "20260812-pitclean-e80-selected-tabpfn-sched-treatment-v1"
CONTROL_TABLE = "tabpfn_sched_control_v1"
TREATMENT_TABLE = "tabpfn_sched_treatment_v1"


def _season_levers(rows: pd.DataFrame) -> dict[int, dict[str, str]]:
    out = {}
    for season, frame in rows.groupby("season"):
        values = frame.lever_env.fillna("").astype(str).unique()
        if len(values) == 1:
            out[int(season)] = lever_values(values[0])
    return out


def _expected_common_levers(
    *, role_selected: bool, allocation: str, selected_k: str,
) -> dict[str, str]:
    expected = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "N_CE": "0",
        "N_EPISTEMIC": "12" if role_selected else "0",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
    }
    if role_selected:
        expected.update({
            "EPISTEMIC_FAMILY": "role_draws",
            "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
            "ROLE_BELIEF_SEED": "7331",
            "REPLACEMENT_SLOTS": "12",
        })
    if allocation == "dirichlet":
        expected.update({"GAME_SIM_USAGE": "dirichlet", "DIRICHLET_K": selected_k})
    elif allocation != "multinomial" or selected_k != "infinity":
        raise ValueError("invalid terminal usage law")
    return expected


def mechanism_failures(
    control: pd.DataFrame,
    treatment: pd.DataFrame,
    feature_audit: dict,
    candidate_audit: dict,
    *,
    expected_code_sha: str,
    role_selected: bool,
    allocation: str,
    selected_k: str,
    control_schedules: dict[int, str],
    treatment_schedules: dict[int, str],
    control_table: str = CONTROL_TABLE,
    treatment_table: str = TREATMENT_TABLE,
    mechanism_name: str = "SCHED",
) -> list[str]:
    failures: list[str] = []
    if control.empty or treatment.empty:
        return failures
    if not control.code_sha.astype(str).eq(expected_code_sha).all() or not \
            treatment.code_sha.astype(str).eq(expected_code_sha).all():
        failures.append(
            f"books do not share frozen {mechanism_name} generation code")
    if control.seeds.iloc[0] != treatment.seeds.iloc[0]:
        failures.append("control and treatment seed identities differ")
    control_by_season = _season_levers(control)
    treatment_by_season = _season_levers(treatment)
    expected_seasons = {2023, 2024, 2025}
    if set(control_by_season) != expected_seasons:
        failures.append("control does not have one lever specification per season")
    if set(treatment_by_season) != expected_seasons:
        failures.append("treatment does not have one lever specification per season")
    if set(control_schedules) != expected_seasons or \
            set(treatment_schedules) != expected_seasons:
        failures.append(f"{mechanism_name} position schedules are incomplete")
    expected = _expected_common_levers(
        role_selected=role_selected, allocation=allocation,
        selected_k=selected_k)
    for season in sorted(expected_seasons):
        left = control_by_season.get(season, {})
        right = treatment_by_season.get(season, {})
        for name, levers in (("control", left), ("treatment", right)):
            for key, value in expected.items():
                if levers.get(key) != value:
                    failures.append(f"{name} {season} {key} is not {value}")
            if allocation == "multinomial":
                if levers.get("GAME_SIM_USAGE", "").lower() not in {
                        "", "0", "off", "false", "none"}:
                    failures.append(f"{name} {season} usage is not multinomial")
                if "DIRICHLET_K" in levers:
                    failures.append(f"{name} {season} has stray DIRICHLET_K")
            if not role_selected:
                unexpected = {
                    "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES",
                    "ROLE_BELIEF_SEED", "REPLACEMENT_SLOTS",
                } & set(levers)
                if unexpected:
                    failures.append(f"{name} {season} has unexpected role levers")
        if left.get("TABPFN_MARGINAL_TABLE") != control_table:
            failures.append(f"control {season} cache table differs")
        if right.get("TABPFN_MARGINAL_TABLE") != treatment_table:
            failures.append(f"treatment {season} cache table differs")
        if left.get("SERVED_POSITION_SCALES") != control_schedules.get(season):
            failures.append(f"control {season} position schedule differs")
        if right.get("SERVED_POSITION_SCALES") != treatment_schedules.get(season):
            failures.append(f"treatment {season} position schedule differs")
        remove = {"TABPFN_MARGINAL_TABLE", "SERVED_POSITION_SCALES"}
        if ({k: v for k, v in left.items() if k not in remove}
                != {k: v for k, v in right.items() if k not in remove}):
            failures.append(
                f"{season} treatment changes levers beyond cache and schedule")

    if feature_audit.get("left_rows") != feature_audit.get("right_rows"):
        failures.append("control and treatment player-row counts differ")
    for field in ("left_only_rows", "right_only_rows", "mismatch_rows"):
        if feature_audit.get(field):
            failures.append(f"player snapshots differ in {field}")
    if float(feature_audit.get("max_numeric_abs_delta", 0.0)) > 1e-12:
        failures.append("player snapshot invariant values differ")
    if set(feature_audit.get("ignored_numeric_fields", ())) != set(
            DISTRIBUTION_DERIVED_FEATURES):
        failures.append("invariance audit excluded the wrong player outputs")
    if candidate_audit.get("paired_slates") != 54:
        failures.append("candidate audit does not cover 54 slates")
    if candidate_audit.get("common_rows", 0) <= 0:
        failures.append("control and treatment have no shared rosters")
    if candidate_audit.get("common_actual_mismatch"):
        failures.append("shared candidate actual scores differ")
    material = sum(int(candidate_audit.get(field, 0)) for field in (
        "left_only_rows", "right_only_rows", "common_sim_mean_mismatch"))
    if material <= 0:
        failures.append(
            f"{mechanism_name} treatment did not reach candidate scoring")
    return failures


__all__ = [
    "CONTROL_PANEL", "CONTROL_TABLE", "DISTRIBUTION_DERIVED_FEATURES",
    "TREATMENT_PANEL", "TREATMENT_TABLE", "comparison_report",
    "mechanism_failures", "tail_first_decision",
]
