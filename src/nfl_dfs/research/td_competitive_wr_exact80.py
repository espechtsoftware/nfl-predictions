"""Mechanical audit and tail law for competitive-WR five-seed exact-80."""

from __future__ import annotations

import re

import pandas as pd

from .served_tail_lineup import ROLE_FEATURES, lever_values
from .tabpfn_active_label_lineup_v2 import DISTRIBUTION_DERIVED_FEATURES
from . import tabpfn_sis_pass_tail_lineup_v1 as shared
from . import td_competitive_wr_lineup as treatment


SEEDS = {
    0: (0, 7331),
    1: (1137260708, 2690847602),
    2: (2875959182, 1630284992),
    3: (253722715, 3374646876),
    4: (1643280042, 3977633467),
}
SEASONS = (2023, 2024, 2025)
TAILS = (240, 230, 220, 210, 200, 194, 187)
FITTED_K = "28.154043586960896"
SCHEDULES = treatment.POSITION_SCHEDULES

feature_invariance_audit = shared.feature_invariance_audit
arm_metrics = shared.arm_metrics
tail_first_decision = shared.tail_first_decision
threshold_crossing_diagnostics = shared.threshold_crossing_diagnostics


def panel_id(arm: str, replicate: int) -> str:
    if arm not in {"control", "treatment"} or replicate not in SEEDS:
        raise ValueError("competitive-WR exact-80 cell is not registered")
    return f"20260814-td-comp-wr-{arm}-r{replicate}-v1"


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


def _equal_series(
    left: pd.Series,
    right: pd.Series,
    atol: float = 1e-12,
) -> pd.Series:
    return shared._equal_series(left, right, atol)


def candidate_audit(control: pd.DataFrame, treatment_rows: pd.DataFrame) -> dict:
    """Require unchanged labels/means but changed dependence-derived scores."""
    keys = ["season", "week", "players"]
    if control.duplicated(keys).any() or treatment_rows.duplicated(keys).any():
        return {"duplicate_rosters": True}
    joined = control.merge(
        treatment_rows,
        on=keys,
        how="outer",
        suffixes=("_c", "_t"),
        indicator=True,
        validate="one_to_one",
    )
    common = joined[joined._merge.eq("both")]
    actual_equal = _equal_series(
        common.actual_score_c, common.actual_score_t, 1e-8,
    )
    mean_equal = _equal_series(common.sim_mean_c, common.sim_mean_t, 1e-4)
    p_line_equal = _equal_series(common.p_line_c, common.p_line_t, 1e-12)
    artifact_equal = common.score_artifact_sha256_c.astype(str).eq(
        common.score_artifact_sha256_t.astype(str)
    )
    return {
        "paired_slates": int(len(set(zip(
            joined.season.astype(int), joined.week.astype(int), strict=True,
        )))),
        "common_rows": int(len(common)),
        "left_only_rows": int(joined._merge.eq("left_only").sum()),
        "right_only_rows": int(joined._merge.eq("right_only").sum()),
        "common_actual_mismatch": int((~actual_equal).sum()),
        "common_sim_mean_mismatch": int((~mean_equal).sum()),
        "common_p_line_mismatch": int((~p_line_equal).sum()),
        "common_artifact_sha_mismatch": int((~artifact_equal).sum()),
    }


def mechanism_failures(
    control: pd.DataFrame,
    treatment_rows: pd.DataFrame,
    feature_audit: dict,
    candidates: dict,
    *,
    expected_code_sha: str,
    replicate: int,
    reference_report_sha: str,
    treatment_report_sha: str,
    protocol_sha: str,
) -> list[str]:
    failures: list[str] = []
    label = f"R{replicate}"
    for name, rows in (("control", control), ("treatment", treatment_rows)):
        if rows.empty or not rows.code_sha.astype(str).eq(expected_code_sha).all():
            failures.append(f"{label} {name} generation code differs")
        values = rows.seeds.fillna("").astype(str).unique()
        if len(values) != 1 or _parse_seeds(values[0]) != SEEDS[replicate]:
            failures.append(f"{label} {name} seed pair differs")

    control_by_season = _season_levers(control)
    treatment_by_season = _season_levers(treatment_rows)
    if set(control_by_season) != set(SEASONS) or set(treatment_by_season) != set(
        SEASONS
    ):
        failures.append(f"{label} season lever identity differs")
    base_seed, role_seed = SEEDS[replicate]
    common = {
        "GAME_SIM_MODE": "possession",
        "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1",
        "TABPFN_MARGINAL_TABLE": treatment.ACTIVE_CACHE,
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
    treatment_only = {
        treatment.TREATMENT_ENV: "1",
        treatment.LICENSE_ENV: "1",
        treatment.REFERENCE_REPORT_SHA_ENV: reference_report_sha,
        treatment.TREATMENT_REPORT_SHA_ENV: treatment_report_sha,
        treatment.PROTOCOL_SHA_ENV: protocol_sha,
    }
    prohibited = {
        "TD_LEDGER",
        "TD_LEDGER_RANK_COUPLING",
        "SIS_ASOE_TARGET_ALLOCATION",
        "SIS_ASOE_BETA",
        "ENSEMBLE_WORLD_MODE",
        "SCHAAKE_DIAG",
        "SCHAAKE_DIAG_ONLY",
        "N_ROUTE_TAIL",
        "N_COVERAGE_TAIL",
        "TABPFN_MEAN",
        "ALT_CEIL",
        "SERVED_TAIL_SCALE",
    }
    for season in SEASONS:
        left = control_by_season.get(season, {})
        right = treatment_by_season.get(season, {})
        expected_common = {
            **common,
            "SERVED_POSITION_SCALES": SCHEDULES[season],
        }
        for name, levers in (("control", left), ("treatment", right)):
            for key, value in expected_common.items():
                if levers.get(key) != value:
                    failures.append(f"{label} {name} {season} {key} differs")
            enabled = sorted(prohibited & set(levers))
            if enabled:
                failures.append(
                    f"{label} {name} {season} prohibited levers {enabled}"
                )
        for key in treatment_only:
            if key in left:
                failures.append(
                    f"{label} control {season} unexpectedly sets {key}"
                )
        for key, value in treatment_only.items():
            if right.get(key) != value:
                failures.append(
                    f"{label} treatment {season} {key} differs"
                )
        if left != {key: value for key, value in right.items()
                    if key not in treatment_only}:
            failures.append(
                f"{label} arms differ beyond competitive-WR license"
            )

    for field in (
        "invalid_keys",
        "column_set_differs",
        "left_only_rows",
        "right_only_rows",
        "invariant_mismatch_rows",
    ):
        if feature_audit.get(field):
            failures.append(f"{label} feature audit {field}")
    if feature_audit.get("left_rows") != feature_audit.get("right_rows"):
        failures.append(f"{label} feature row counts differ")
    if set(feature_audit.get("ignored_fields", ())) != set(
        DISTRIBUTION_DERIVED_FEATURES
    ):
        failures.append(f"{label} feature audit exclusions differ")
    if feature_audit.get("missing_ignored_fields"):
        failures.append(f"{label} registered distribution fields are missing")
    for field in (
        "duplicate_rosters",
        "common_actual_mismatch",
        "common_sim_mean_mismatch",
    ):
        if candidates.get(field):
            failures.append(f"{label} candidate audit {field}")
    if candidates.get("paired_slates") != 54 or not candidates.get("common_rows"):
        failures.append(f"{label} candidate pairing differs")
    if not sum(int(candidates.get(field, 0)) for field in (
        "left_only_rows",
        "right_only_rows",
        "common_p_line_mismatch",
        "common_artifact_sha_mismatch",
    )):
        failures.append(f"{label} treatment does not reach candidate scoring")
    return failures


__all__ = [
    "FITTED_K",
    "SCHEDULES",
    "SEASONS",
    "SEEDS",
    "TAILS",
    "arm_metrics",
    "candidate_audit",
    "feature_invariance_audit",
    "mechanism_failures",
    "panel_id",
    "tail_first_decision",
    "threshold_crossing_diagnostics",
]
