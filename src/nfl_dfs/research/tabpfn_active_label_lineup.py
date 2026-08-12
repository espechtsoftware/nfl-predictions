"""Pure guards for the frozen TabPFN active-label exact-80 replay."""

from __future__ import annotations

import pandas as pd

from .served_position_lineup import comparison_report, tail_first_decision
from .served_tail_lineup import (
    CANDIDATE_MEAN_ATOL,
    EVALUATION_SEASONS,
    ROLE_FEATURES,
    SOURCE_SEASONS,
    lever_values,
    validate_candidate_panel,
)


HISTORICAL_SOURCE_PANEL = "20260810-lockfix-e80-k1-role12union-8677d21"
HISTORICAL_SOURCE_CODE_SHA = "8677d21"
CONTROL_PANEL = "20260811-lockfix-e80-k1-tabpfn-current-label-v1"
TREATMENT_PANEL = "20260811-lockfix-e80-k1-tabpfn-active-label-v1"
CONTROL_TABLE = "tabpfn_active_label_control_v1"
TREATMENT_TABLE = "tabpfn_active_label_treatment_v1"
FINAL_SERVED_REPORT_SHA256 = (
    "36982de7412ddd1d77ae92cf7951d42b6a5ea550fe568d2bb279672012c4d2c6"
)
CACHE_VALIDATION_SHA256 = (
    "fe72d38634b0036e185ade288429356b74fc5c65ebae1c8f424e926f12aecc01"
)

CONTROL_POSITION_SPECS = {
    2023: "QB:0.990,RB:0.995,TE:0.940,WR:1.020",
    2024: "QB:0.910,RB:0.990,TE:0.950,WR:1.085",
    2025: "QB:0.935,RB:0.975,TE:0.945,WR:1.090",
}
TREATMENT_POSITION_SPECS = {
    2023: "QB:0.955,RB:0.985,TE:0.975,WR:1.005",
    2024: "QB:0.895,RB:0.980,TE:0.975,WR:1.040",
    2025: "QB:0.920,RB:0.955,TE:0.955,WR:1.030",
}

DISTRIBUTION_DERIVED_FEATURES = (
    "proj",
    "proj_tourney",
    "own_est",
    "proj_p10",
    "proj_p50",
    "proj_p90",
    "proj_std",
)


def _frozen_common_levers() -> dict[str, str]:
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


def _season_levers(rows: pd.DataFrame) -> dict[int, dict[str, str]]:
    out: dict[int, dict[str, str]] = {}
    for season, frame in rows.groupby("season"):
        values = frame.lever_env.fillna("").astype(str).unique()
        if len(values) == 1:
            out[int(season)] = lever_values(values[0])
    return out


def mechanism_failures(
    control: pd.DataFrame,
    treatment: pd.DataFrame,
    feature_audit: dict,
    candidate_audit: dict,
    *,
    experiment_code_sha: str,
) -> list[str]:
    """Require cache plus its frozen schedule to be the only arm change."""
    failures: list[str] = []
    if control.empty or treatment.empty:
        return failures
    if not control.code_sha.astype(str).eq(experiment_code_sha).all() or \
            not treatment.code_sha.astype(str).eq(experiment_code_sha).all():
        failures.append("books do not share the immutable experiment code SHA")
    if control.seeds.iloc[0] != treatment.seeds.iloc[0]:
        failures.append("control and treatment seed identities differ")

    control_by_season = _season_levers(control)
    treatment_by_season = _season_levers(treatment)
    expected_seasons = set(EVALUATION_SEASONS)
    if set(control_by_season) != expected_seasons:
        failures.append("control does not have one lever specification per season")
    if set(treatment_by_season) != expected_seasons:
        failures.append("treatment does not have one lever specification per season")

    for season in EVALUATION_SEASONS:
        left = control_by_season.get(season, {})
        right = treatment_by_season.get(season, {})
        for name, levers in (("control", left), ("treatment", right)):
            for key, value in _frozen_common_levers().items():
                if levers.get(key) != value:
                    failures.append(f"{name} {season} {key} is not {value}")
            if levers.get("GAME_SIM_USAGE", "").lower() not in {
                    "", "0", "off", "false", "none"}:
                failures.append(f"{name} {season} usage is not production default")
            if "DIRICHLET_K" in levers:
                failures.append(f"{name} {season} unexpectedly persists DIRICHLET_K")
        if left.get("TABPFN_MARGINAL_TABLE") != CONTROL_TABLE:
            failures.append(f"control {season} cache table differs from frozen table")
        if right.get("TABPFN_MARGINAL_TABLE") != TREATMENT_TABLE:
            failures.append(
                f"treatment {season} cache table differs from frozen table")
        if left.get("SERVED_POSITION_SCALES") != \
                CONTROL_POSITION_SPECS[season]:
            failures.append(f"control {season} position schedule differs")
        if right.get("SERVED_POSITION_SCALES") != \
                TREATMENT_POSITION_SPECS[season]:
            failures.append(f"treatment {season} position schedule differs")
        remove = {"TABPFN_MARGINAL_TABLE", "SERVED_POSITION_SCALES"}
        left_common = {key: value for key, value in left.items()
                       if key not in remove}
        right_common = {key: value for key, value in right.items()
                        if key not in remove}
        if left_common != right_common:
            failures.append(
                f"{season} treatment changes levers beyond cache and schedule")

    if feature_audit.get("left_rows") != feature_audit.get("right_rows"):
        failures.append("control and treatment player-row counts differ")
    for field in ("left_only_rows", "right_only_rows", "mismatch_rows"):
        if feature_audit.get(field):
            failures.append(f"player snapshots differ in {field}")
    if float(feature_audit.get("max_numeric_abs_delta", 0.0)) > 1e-12:
        failures.append("player snapshot invariant values differ")
    ignored = set(feature_audit.get("ignored_numeric_fields", ()))
    if ignored != set(DISTRIBUTION_DERIVED_FEATURES):
        failures.append(
            "invariance audit did not exclude exactly the registered outputs")

    if candidate_audit.get("paired_slates") != 54:
        failures.append("candidate audit does not cover 54 slates")
    if candidate_audit.get("common_rows", 0) <= 0:
        failures.append("control and treatment have no shared rosters")
    if candidate_audit.get("common_actual_mismatch"):
        failures.append("shared candidate actual scores differ")
    material_changes = sum(int(candidate_audit.get(field, 0)) for field in (
        "left_only_rows", "right_only_rows", "common_sim_mean_mismatch"))
    if material_changes <= 0:
        failures.append("active-label treatment did not reach candidate scoring")
    return failures


__all__ = [
    "CACHE_VALIDATION_SHA256",
    "CANDIDATE_MEAN_ATOL",
    "CONTROL_PANEL",
    "CONTROL_POSITION_SPECS",
    "CONTROL_TABLE",
    "DISTRIBUTION_DERIVED_FEATURES",
    "EVALUATION_SEASONS",
    "FINAL_SERVED_REPORT_SHA256",
    "HISTORICAL_SOURCE_CODE_SHA",
    "HISTORICAL_SOURCE_PANEL",
    "SOURCE_SEASONS",
    "TREATMENT_PANEL",
    "TREATMENT_POSITION_SPECS",
    "TREATMENT_TABLE",
    "comparison_report",
    "mechanism_failures",
    "tail_first_decision",
    "validate_candidate_panel",
]
