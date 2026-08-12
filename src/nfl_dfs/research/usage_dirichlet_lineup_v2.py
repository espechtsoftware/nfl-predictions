"""Pure mechanism guards for the PIT-clean fitted-usage exact-80 retry."""

from __future__ import annotations

import pandas as pd

from .served_position_lineup_v2 import comparison_report, tail_first_decision
from .served_tail_lineup import ROLE_FEATURES, lever_values


CONTROL_PANEL = "20260812-pitclean-e80-selected-usage-control-v2"
TREATMENT_PANEL = "20260812-pitclean-e80-selected-usage-fitted-v2"
CACHE_TABLE = "tabpfn_projections_pit_v2"
DISTRIBUTION_DERIVED_FEATURES = (
    "proj",
    "proj_tourney",
    "own_est",
    "proj_p10",
    "proj_p50",
    "proj_p90",
    "proj_std",
)


def _expected_replay_levers(
    *,
    base: str,
    role_selected: bool,
    position_spec: str,
) -> dict[str, str]:
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
    if position_spec != "identity":
        expected["SERVED_POSITION_SCALES"] = position_spec
    return expected


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
    expected_code_sha: str,
    fitted_k: str,
    base: str,
    role_selected: bool,
    position_spec: str,
) -> list[str]:
    """Require fitted conditional allocation to be the sole treatment lever."""
    failures: list[str] = []
    if evaluation_source.empty or control.empty or treatment.empty:
        return failures
    for name, rows in (
        ("source", evaluation_source),
        ("control", control),
        ("treatment", treatment),
    ):
        if not rows.code_sha.astype(str).eq(expected_code_sha).all():
            failures.append(f"{name} code SHA differs from frozen generation")
    if not (evaluation_source.seeds.iloc[0] == control.seeds.iloc[0]
            == treatment.seeds.iloc[0]):
        failures.append("source, control and treatment seed identities differ")

    source_levers = lever_values(evaluation_source.lever_env.iloc[0])
    control_levers = lever_values(control.lever_env.iloc[0])
    treatment_levers = lever_values(treatment.lever_env.iloc[0])
    expected = _expected_replay_levers(
        base=base,
        role_selected=role_selected,
        position_spec=position_spec,
    )
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
        if position_spec == "identity" and "SERVED_POSITION_SCALES" in levers:
            if str(levers["SERVED_POSITION_SCALES"]).lower() not in {
                    "", "0", "off", "false", "identity", "none"}:
                failures.append(f"{name} served-position law is not identity")
        if not role_selected:
            unexpected = {
                "EPISTEMIC_FAMILY", "ROLE_BELIEF_FEATURES",
                "ROLE_BELIEF_SEED", "REPLACEMENT_SLOTS",
            } & set(levers)
            if unexpected:
                failures.append(
                    f"{name} has unexpected role levers {sorted(unexpected)}")

    if control_levers.get("GAME_SIM_USAGE", "").lower() not in {
            "", "0", "off", "false", "none"}:
        failures.append("control usage allocation is not production multinomial")
    if "DIRICHLET_K" in control_levers:
        failures.append("control unexpectedly persists DIRICHLET_K")
    if treatment_levers.get("GAME_SIM_USAGE") != "dirichlet":
        failures.append("treatment usage allocation is not dirichlet")
    if treatment_levers.get("DIRICHLET_K") != fitted_k:
        failures.append("treatment DIRICHLET_K differs from repaired fit")
    treatment_other = {
        key: value for key, value in treatment_levers.items()
        if key not in {"GAME_SIM_USAGE", "DIRICHLET_K"}
    }
    if treatment_other != control_levers:
        failures.append("treatment changes replay levers beyond fitted usage K")
    if source_levers != control_levers:
        failures.append("same-image control changes selected-source replay levers")

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
    "CACHE_TABLE",
    "CONTROL_PANEL",
    "DISTRIBUTION_DERIVED_FEATURES",
    "TREATMENT_PANEL",
    "comparison_report",
    "mechanism_failures",
    "tail_first_decision",
]
