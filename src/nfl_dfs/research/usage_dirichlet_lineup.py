"""Pure guards for the frozen data-fitted K exact-80 replay."""

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
EVALUATION_SOURCE_PANEL = (
    "20260811-lockfix-e80-k1-role12-position-scales-v1"
)
EVALUATION_SOURCE_CODE_SHA = "d86e4f6"
CONTROL_PANEL = "20260811-lockfix-e80-k1-role12-poscal-usage-control-v1"
TREATMENT_PANEL = "20260811-lockfix-e80-k1-role12-poscal-usage-k28246898-v1"
POSITION_SPEC = "QB:0.970,RB:1.005,TE:0.940,WR:1.070"
FITTED_K = "28.246898139750336"
K_REPORT_SHA256 = (
    "7fd2a735d22294a9f75469eda4ce5230c9e20b52620bbb0bb0d01e5a478a6996"
)

# These persisted player fields are outputs of the allocation mechanism, not
# invariant inputs. Dirichlet target/carry allocation is supposed to change
# each player's simulated marginal width/tail. Punt valuation then reads p90,
# and naive ownership reads that valuation, so all seven change downstream
# while the pre-simulation mean and every point-in-time input remain fixed.
DISTRIBUTION_DERIVED_FEATURES = (
    "proj",
    "proj_tourney",
    "own_est",
    "proj_p10",
    "proj_p50",
    "proj_p90",
    "proj_std",
)


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
        "SERVED_POSITION_SCALES": POSITION_SPEC,
    }


def mechanism_failures(
    evaluation_source: pd.DataFrame,
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
    """Require fitted-K allocation to be the only treatment difference."""
    failures: list[str] = []
    if evaluation_source.empty or control.empty or treatment.empty:
        return failures
    if control.code_sha.iloc[0] != experiment_code_sha or \
            treatment.code_sha.iloc[0] != experiment_code_sha:
        failures.append("new panels do not share the immutable experiment code SHA")
    if not (evaluation_source.seeds.iloc[0] == control.seeds.iloc[0]
            == treatment.seeds.iloc[0]):
        failures.append("source, control and treatment seed identities differ")

    source_levers = lever_values(evaluation_source.lever_env.iloc[0])
    control_levers = lever_values(control.lever_env.iloc[0])
    treatment_levers = lever_values(treatment.lever_env.iloc[0])
    for name, levers in (
        ("source", source_levers),
        ("control", control_levers),
        ("treatment", treatment_levers),
    ):
        for key, value in _frozen_levers().items():
            if levers.get(key) != value:
                failures.append(f"{name} {key} is not {value}")
    if control_levers.get("GAME_SIM_USAGE", "").lower() not in {
            "", "0", "off", "false", "none"}:
        failures.append("control usage allocation is not production default")
    if "DIRICHLET_K" in control_levers:
        failures.append("control unexpectedly persists DIRICHLET_K")
    if treatment_levers.get("GAME_SIM_USAGE") != "dirichlet":
        failures.append("treatment usage allocation is not dirichlet")
    if treatment_levers.get("DIRICHLET_K") != FITTED_K:
        failures.append("treatment DIRICHLET_K differs from frozen fit")

    treatment_other = {
        key: value for key, value in treatment_levers.items()
        if key not in {"GAME_SIM_USAGE", "DIRICHLET_K"}
    }
    if treatment_other != control_levers:
        failures.append("treatment changes replay levers beyond fitted usage K")
    if source_levers != control_levers:
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
    ignored = set(control_treatment_features.get(
        "ignored_numeric_fields", ()))
    if ignored != set(DISTRIBUTION_DERIVED_FEATURES):
        failures.append(
            "control/treatment invariance did not exclude exactly the "
            "registered distribution-derived fields")

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
    changed = (
        int(control_treatment_candidates.get("left_only_rows", 0))
        + int(control_treatment_candidates.get("right_only_rows", 0))
    )
    if changed <= 0:
        failures.append("fitted usage K did not change candidate membership")
    if int(reproduction.get("weekly_max_mismatches", -1)) != 0:
        failures.append("same-image control does not reproduce source weekly maxima")
    if int(reproduction.get("paired_slates", 0)) != 54:
        failures.append("source/control reproduction does not cover 54 slates")
    return failures


__all__ = [
    "CANDIDATE_MEAN_ATOL",
    "CONTROL_PANEL",
    "DISTRIBUTION_DERIVED_FEATURES",
    "EVALUATION_SEASONS",
    "EVALUATION_SOURCE_CODE_SHA",
    "EVALUATION_SOURCE_PANEL",
    "FITTED_K",
    "HISTORICAL_SOURCE_CODE_SHA",
    "HISTORICAL_SOURCE_PANEL",
    "K_REPORT_SHA256",
    "SOURCE_SEASONS",
    "TREATMENT_PANEL",
    "comparison_report",
    "mechanism_failures",
    "tail_first_decision",
    "validate_candidate_panel",
]
