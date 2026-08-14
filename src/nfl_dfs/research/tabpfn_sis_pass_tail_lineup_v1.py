"""Guards and tail-first law for the SIS pass-tail five-seed exact-80 arm."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from .served_tail_lineup import ROLE_FEATURES, lever_values
from .tabpfn_active_label_lineup_v2 import DISTRIBUTION_DERIVED_FEATURES


SEEDS = {
    0: (0, 7331), 1: (1137260708, 2690847602),
    2: (2875959182, 1630284992), 3: (253722715, 3374646876),
    4: (1643280042, 3977633467),
}
SEASONS = (2023, 2024, 2025)
TAILS = (240, 230, 220, 210, 200, 194, 187)
CONTROL_TABLE = "tabpfn_sis_pass_tail_control_v1"
TREATMENT_TABLE = "tabpfn_sis_pass_tail_treatment_v1"
FITTED_K = "28.154043586960896"
FROZEN_BETA = "0.07771181538347656"
CONTROL_SCHEDULES = {
    2023: "QB:0.76,RB:0.83,TE:0.99,WR:1.05",
    2024: "QB:0.81,RB:0.88,TE:0.97,WR:1.07",
    2025: "QB:0.85,RB:0.895,TE:0.96,WR:1.04",
}
TREATMENT_SCHEDULES = {
    2023: "QB:0.975,RB:0.99,TE:0.975,WR:1.04",
    2024: "QB:0.92,RB:0.97,TE:0.95,WR:1.055",
    2025: "QB:0.92,RB:0.965,TE:0.945,WR:1.04",
}


def panel_id(arm: str, replicate: int) -> str:
    return f"20260814-sis-pass-tail-{arm}-r{replicate}-v1"


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


def _equal_series(left: pd.Series, right: pd.Series, atol=1e-12) -> pd.Series:
    both_null = left.isna() & right.isna()
    # BigQuery BOOL values arrive as pandas bool/BooleanArray. Numeric
    # coercion accepts them, but NumPy deliberately rejects boolean
    # subtraction. They are exact invariants and need no tolerance.
    if pd.api.types.is_bool_dtype(left.dtype) or pd.api.types.is_bool_dtype(
        right.dtype
    ):
        return both_null | (
            left.notna() & right.notna()
            & left.astype("boolean").eq(right.astype("boolean"))
        )
    ln = pd.to_numeric(left, errors="coerce").astype("Float64")
    rn = pd.to_numeric(right, errors="coerce").astype("Float64")
    numeric = left.notna() & right.notna() & ln.notna() & rn.notna()
    return both_null | (numeric & (ln - rn).abs().le(atol)) | (
        (~numeric) & left.astype(str).eq(right.astype(str))
    )


def feature_invariance_audit(
    control: pd.DataFrame, treatment: pd.DataFrame,
) -> dict[str, object]:
    """Compare every snapshot field except provenance and registered outputs."""
    keys = ["season", "week", "id"]
    if control.duplicated(keys).any() or treatment.duplicated(keys).any():
        return {"invalid_keys": True}
    left = control.set_index(keys).sort_index()
    right = treatment.set_index(keys).sort_index()
    if set(left.columns) != set(right.columns):
        return {"column_set_differs": True}
    metadata = {
        "panel_run_id", "slate_run_id", "generated_at", "config_hash",
    }
    ignored = set(DISTRIBUTION_DERIVED_FEATURES)
    invariant = sorted(set(left.columns) - metadata - ignored)
    present_ignored = sorted(ignored & set(left.columns))
    common = left.index.intersection(right.index)
    mismatch = pd.Series(False, index=common)
    for field in invariant:
        mismatch |= ~_equal_series(left.loc[common, field], right.loc[common, field])
    changed = pd.Series(False, index=common)
    for field in present_ignored:
        changed |= ~_equal_series(left.loc[common, field], right.loc[common, field])
    return {
        "left_rows": int(len(left)), "right_rows": int(len(right)),
        "left_only_rows": int(len(left.index.difference(right.index))),
        "right_only_rows": int(len(right.index.difference(left.index))),
        "invariant_mismatch_rows": int(mismatch.sum()),
        "distribution_changed_rows": int(changed.sum()),
        "ignored_fields": sorted(ignored),
        "missing_ignored_fields": sorted(ignored - set(left.columns)),
        "invariant_fields": invariant,
    }


def candidate_audit(control: pd.DataFrame, treatment: pd.DataFrame) -> dict:
    keys = ["season", "week", "players"]
    if control.duplicated(keys).any() or treatment.duplicated(keys).any():
        return {"duplicate_rosters": True}
    joined = control.merge(
        treatment, on=keys, how="outer", suffixes=("_c", "_t"),
        indicator=True, validate="one_to_one",
    )
    common = joined[joined._merge.eq("both")]
    actual_equal = _equal_series(common.actual_score_c, common.actual_score_t, 1e-8)
    mean_equal = _equal_series(common.sim_mean_c, common.sim_mean_t, 1e-4)
    return {
        "paired_slates": int(len(set(zip(
            joined.season.astype(int), joined.week.astype(int)
        )))),
        "common_rows": int(len(common)),
        "left_only_rows": int(joined._merge.eq("left_only").sum()),
        "right_only_rows": int(joined._merge.eq("right_only").sum()),
        "common_actual_mismatch": int((~actual_equal).sum()),
        "common_sim_mean_mismatch": int((~mean_equal).sum()),
    }


def mechanism_failures(
    control: pd.DataFrame, treatment: pd.DataFrame, feature_audit: dict,
    candidates: dict, *, expected_code_sha: str, replicate: int,
    phase_s_arm: str,
) -> list[str]:
    failures: list[str] = []
    label = f"R{replicate}"
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
        "GAME_SIM_MODE": "possession", "MODEL_ENSEMBLE": "1",
        "TABPFN_MARGINALS": "1", "EPISTEMIC_FAMILY": "role_draws",
        "ROLE_BELIEF_FEATURES": ROLE_FEATURES,
        "ROLE_BELIEF_SEED": str(role_seed),
        "REPLAY_PROJECTION_SEED": str(base_seed),
        "REPLACEMENT_SLOTS": "12", "N_CE": "0", "N_EPISTEMIC": "12",
        "N_GUMBEL": "0", "N_BOOM": "40",
        "GAME_SIM_USAGE": "dirichlet", "DIRICHLET_K": FITTED_K,
        "CAND_ARTIFACT_PLAYER_WORLDS": "1",
    }
    if phase_s_arm == "treatment":
        expected.update({
            "SIS_ASOE_TARGET_ALLOCATION": "1", "SIS_ASOE_BETA": FROZEN_BETA,
        })
    for season in SEASONS:
        left = left_by_season.get(season, {})
        right = right_by_season.get(season, {})
        for name, levers in (("control", left), ("treatment", right)):
            for key, value in expected.items():
                if levers.get(key) != value:
                    failures.append(f"{label} {name} {season} {key} differs")
            if phase_s_arm == "control" and (
                "SIS_ASOE_TARGET_ALLOCATION" in levers or "SIS_ASOE_BETA" in levers
            ):
                failures.append(f"{label} {name} unexpectedly enables ASOE")
        if left.get("TABPFN_MARGINAL_TABLE") != CONTROL_TABLE:
            failures.append(f"{label} control {season} cache differs")
        if right.get("TABPFN_MARGINAL_TABLE") != TREATMENT_TABLE:
            failures.append(f"{label} treatment {season} cache differs")
        if left.get("SERVED_POSITION_SCALES") != CONTROL_SCHEDULES[season]:
            failures.append(f"{label} control {season} schedule differs")
        if right.get("SERVED_POSITION_SCALES") != TREATMENT_SCHEDULES[season]:
            failures.append(f"{label} treatment {season} schedule differs")
        remove = {"TABPFN_MARGINAL_TABLE", "SERVED_POSITION_SCALES"}
        if ({k: v for k, v in left.items() if k not in remove}
                != {k: v for k, v in right.items() if k not in remove}):
            failures.append(f"{label} arms differ beyond cache/schedule")
    if feature_audit.get("left_rows") != feature_audit.get("right_rows"):
        failures.append(f"{label} feature row counts differ")
    for field in ("invalid_keys", "column_set_differs", "left_only_rows",
                  "right_only_rows", "invariant_mismatch_rows"):
        if feature_audit.get(field):
            failures.append(f"{label} feature audit {field}")
    if set(feature_audit.get("ignored_fields", ())) != set(
            DISTRIBUTION_DERIVED_FEATURES):
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


def arm_metrics(frame: pd.DataFrame) -> tuple[dict, pd.Series]:
    selected = frame[frame.selected].groupby(["season", "week"])[
        "actual_score"].max().sort_index()
    oracle = frame.groupby(["season", "week"])["actual_score"].max().sort_index()
    return ({
        "selected_tail": {str(t): int(selected.ge(t).sum()) for t in TAILS},
        "oracle_tail": {str(t): int(oracle.ge(t).sum()) for t in TAILS},
        "selected_mean": float(selected.mean()),
        "selected_median": float(selected.median()),
        "candidate_rows": int(len(frame)),
    }, selected)


def tail_first_decision(metrics: dict[str, dict]) -> dict:
    totals = {
        arm: {str(t): sum(
            metrics[f"{arm}-R{r}"]["selected_tail"][str(t)] for r in SEEDS
        ) for t in TAILS}
        for arm in ("control", "treatment")
    }
    first = next((t for t in TAILS if
                  totals["treatment"][str(t)] != totals["control"][str(t)]), None)
    means = {arm: float(np.mean([
        metrics[f"{arm}-R{r}"]["selected_mean"] for r in SEEDS
    ])) for arm in ("control", "treatment")}
    if first is not None:
        comparison = np.sign(
            totals["treatment"][str(first)] - totals["control"][str(first)])
    else:
        comparison = np.sign(means["treatment"] - means["control"])
    return {
        "selected_tail_sums": totals, "deciding_threshold": first,
        "aggregate_weekly_best_mean": means,
        "selected_arm": "treatment" if comparison > 0 else "control",
        "control_retained_on_exact_tie": bool(comparison == 0),
    }


__all__ = [
    "CONTROL_SCHEDULES", "CONTROL_TABLE", "DISTRIBUTION_DERIVED_FEATURES",
    "FITTED_K", "FROZEN_BETA", "SEASONS", "SEEDS", "TAILS",
    "TREATMENT_SCHEDULES", "TREATMENT_TABLE", "arm_metrics",
    "candidate_audit", "feature_invariance_audit", "mechanism_failures",
    "panel_id", "tail_first_decision",
]
