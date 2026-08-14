"""Guards and tail-first law for the SIS RB run-tail five-seed arm."""

from __future__ import annotations

import re

import pandas as pd

from .served_tail_lineup import ROLE_FEATURES, lever_values
from .tabpfn_sis_pass_tail_lineup_v1 import (
    SEASONS,
    SEEDS,
    TAILS,
    arm_metrics,
    candidate_audit,
    feature_invariance_audit,
    tail_first_decision,
    threshold_crossing_diagnostics,
)


CONTROL_TABLE = "tabpfn_sis_rb_runtail_control_v1"
TREATMENT_TABLE = "tabpfn_sis_rb_runtail_treatment_v1"
FITTED_K = "28.154043586960896"
FORBIDDEN_COMPOSITION_LEVERS = {
    "DROP_FEATURES",
    "ENSEMBLE_WORLD_MODE",
    "EXTRA_FEATURES",
    "N_COVERAGE_TAIL",
    "N_ROUTE_TAIL",
    "SCHAAKE_DIAG",
    "SCHAAKE_DIAG_ONLY",
    "SCHAAKE_DIAG_STRICT",
    "SCHAAKE_TEMPLATE_MODE",
    "SIS_ASOE_BETA",
    "SIS_ASOE_TARGET_ALLOCATION",
    "TD_LEDGER",
    "TD_LEDGER_RANK_COUPLING",
}


def panel_id(arm: str, replicate: int) -> str:
    if arm not in {"control", "treatment"} or replicate not in SEEDS:
        raise ValueError("unknown SIS RB run-tail exact-80 cell")
    return f"20260814-sis-runtail-{arm}-r{replicate}-v1"


def _parse_seeds(value: str) -> tuple[int, int]:
    pairs = dict(re.findall(r"(?:^|;)([A-Z_]+)=([^;]+)", str(value or "")))
    return (
        int(pairs.get("REPLAY_PROJECTION_SEED", "0")),
        int(pairs.get("ROLE_BELIEF_SEED", "7331")),
    )


def _season_levers(rows: pd.DataFrame) -> dict[int, dict[str, str]]:
    output = {}
    for season, frame in rows.groupby("season"):
        values = frame.lever_env.fillna("").astype(str).unique()
        if len(values) == 1:
            output[int(season)] = lever_values(values[0])
    return output


def validate_schedule_specs(schedules: dict[int, str]) -> None:
    """Require one complete, canonical served-position spec per season."""
    if set(schedules) != set(SEASONS):
        raise ValueError("run-tail served schedules are incomplete")
    pattern = re.compile(
        r"^QB:(?:0|[0-9]+(?:\.[0-9]+)?),"
        r"RB:(?:0|[0-9]+(?:\.[0-9]+)?),"
        r"TE:(?:0|[0-9]+(?:\.[0-9]+)?),"
        r"WR:(?:0|[0-9]+(?:\.[0-9]+)?)$"
    )
    for season, spec in schedules.items():
        if not pattern.fullmatch(str(spec)):
            raise ValueError(f"run-tail {season} served schedule is not canonical")
        factors = [float(item.split(":", 1)[1]) for item in spec.split(",")]
        if not all(0.75 <= value <= 1.5 for value in factors):
            raise ValueError(f"run-tail {season} served schedule is outside grid")


def mechanism_failures(
    control: pd.DataFrame,
    treatment: pd.DataFrame,
    feature_audit: dict,
    candidates: dict,
    *,
    expected_code_sha: str,
    replicate: int,
    control_schedules: dict[int, str],
    treatment_schedules: dict[int, str],
) -> list[str]:
    """Prove that the arms differ only by cache and frozen served schedule."""
    failures: list[str] = []
    label = f"R{replicate}"
    try:
        validate_schedule_specs(control_schedules)
        validate_schedule_specs(treatment_schedules)
    except ValueError as exc:
        failures.append(str(exc))
    for name, rows in (("control", control), ("treatment", treatment)):
        if rows.empty or not rows.code_sha.astype(str).eq(expected_code_sha).all():
            failures.append(f"{label} {name} generation code differs")
        values = rows.seeds.fillna("").astype(str).unique()
        if len(values) != 1 or _parse_seeds(values[0]) != SEEDS[replicate]:
            failures.append(f"{label} {name} seed pair differs")
    left_by_season = _season_levers(control)
    right_by_season = _season_levers(treatment)
    if set(left_by_season) != set(SEASONS) or set(right_by_season) != set(SEASONS):
        failures.append(f"{label} season lever identity differs")
    base_seed, role_seed = SEEDS[replicate]
    expected = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1",
        "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
        "ROLE_BELIEF_SEED": str(role_seed),
        "REPLAY_PROJECTION_SEED": str(base_seed),
        "REPLACEMENT_SLOTS": "12",
        "N_CE": "0",
        "N_EPISTEMIC": "12",
        "N_GUMBEL": "0",
        "N_BOOM": "40",
        "GAME_SIM_USAGE": "dirichlet",
        "DIRICHLET_K": FITTED_K,
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
    }
    for season in SEASONS:
        left = left_by_season.get(season, {})
        right = right_by_season.get(season, {})
        for name, levers in (("control", left), ("treatment", right)):
            for key, value in expected.items():
                if levers.get(key) != value:
                    failures.append(f"{label} {name} {season} {key} differs")
            for key in sorted(FORBIDDEN_COMPOSITION_LEVERS & set(levers)):
                failures.append(
                    f"{label} {name} {season} unexpectedly composes {key}"
                )
        if left.get("TABPFN_MARGINAL_TABLE") != CONTROL_TABLE:
            failures.append(f"{label} control {season} cache differs")
        if right.get("TABPFN_MARGINAL_TABLE") != TREATMENT_TABLE:
            failures.append(f"{label} treatment {season} cache differs")
        if left.get("SERVED_POSITION_SCALES") != control_schedules.get(season):
            failures.append(f"{label} control {season} schedule differs")
        if right.get("SERVED_POSITION_SCALES") != treatment_schedules.get(season):
            failures.append(f"{label} treatment {season} schedule differs")
        remove = {"TABPFN_MARGINAL_TABLE", "SERVED_POSITION_SCALES"}
        if ({key: value for key, value in left.items() if key not in remove}
                != {key: value for key, value in right.items() if key not in remove}):
            failures.append(f"{label} arms differ beyond cache/schedule")
    if feature_audit.get("left_rows") != feature_audit.get("right_rows"):
        failures.append(f"{label} feature row counts differ")
    for field in (
        "invalid_keys",
        "column_set_differs",
        "left_only_rows",
        "right_only_rows",
        "invariant_mismatch_rows",
    ):
        if feature_audit.get(field):
            failures.append(f"{label} feature audit {field}")
    ignored = set(feature_audit.get("ignored_fields", ()))
    from .tabpfn_active_label_lineup_v2 import DISTRIBUTION_DERIVED_FEATURES

    if ignored != set(DISTRIBUTION_DERIVED_FEATURES):
        failures.append(f"{label} feature audit exclusions differ")
    if feature_audit.get("missing_ignored_fields"):
        failures.append(f"{label} registered distribution fields are missing")
    if not feature_audit.get("distribution_changed_rows"):
        failures.append(f"{label} cache does not change player distributions")
    for field in ("duplicate_rosters", "common_actual_mismatch"):
        if candidates.get(field):
            failures.append(f"{label} candidate audit {field}")
    if candidates.get("paired_slates") != 54 or not candidates.get("common_rows"):
        failures.append(f"{label} candidate pairing differs")
    if not sum(int(candidates.get(field, 0)) for field in (
        "left_only_rows", "right_only_rows", "common_sim_mean_mismatch"
    )):
        failures.append(f"{label} treatment does not reach candidate scoring")
    return failures


__all__ = [
    "CONTROL_TABLE",
    "FITTED_K",
    "FORBIDDEN_COMPOSITION_LEVERS",
    "SEASONS",
    "SEEDS",
    "TAILS",
    "TREATMENT_TABLE",
    "arm_metrics",
    "candidate_audit",
    "feature_invariance_audit",
    "mechanism_failures",
    "panel_id",
    "tail_first_decision",
    "threshold_crossing_diagnostics",
    "validate_schedule_specs",
]
