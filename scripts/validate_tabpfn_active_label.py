#!/usr/bin/env python3
"""Mechanical validation for the frozen TabPFN active-label caches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


PREFIX = "TABPFN_ACTIVE_LABEL_JSON="
TARGET_SEASONS = [2022, 2023, 2024, 2025]
EXPECTED_ROWS = 52_307
QUANTILE_COLUMNS = (
    "q01", "q05", "q10", "q20", "q30", "q40", "q50",
    "q60", "q70", "q80", "q90", "q95", "q99",
)
def tables_for_version(version: str) -> dict[str, str]:
    if version not in {"v1", "v2"}:
        raise ValueError(f"unsupported active-label cache version {version!r}")
    return {
        "control": f"tabpfn_active_label_control_{version}",
        "active_only": f"tabpfn_active_label_treatment_{version}",
    }


def extract_report(path: Path) -> dict:
    payloads = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if PREFIX in line:
            payloads.append(json.loads(line.split(PREFIX, 1)[1]))
    if len(payloads) != 1:
        raise ValueError(f"expected one active-label report in {path}; got {len(payloads)}")
    return payloads[0]


def validate_reports(
    control: dict, treatment: dict, code_sha: str, version: str = "v1",
) -> dict:
    checks: dict[str, bool] = {}
    registered = tables_for_version(version)
    checks["arm_identity"] = (
        control.get("arm") == "control"
        and treatment.get("arm") == "active_only"
        and not control.get("active_context_only")
        and treatment.get("active_context_only") is True
    )
    checks["code_identity"] = (
        control.get("code_sha") == code_sha
        and treatment.get("code_sha") == code_sha
    )
    checks["output_table_identity"] = (
        control.get("output_table", "").endswith(registered["control"])
        and treatment.get("output_table", "").endswith(
            registered["active_only"])
    )
    checks["same_source_snapshot"] = (
        control.get("training_source") == treatment.get("training_source")
    )
    checks["same_feature_contract"] = (
        control.get("feature_columns") == treatment.get("feature_columns")
        and control.get("feature_contract_sha256")
        == treatment.get("feature_contract_sha256")
    )
    checks["same_frozen_hyperparameters"] = all(
        control.get(key) == treatment.get(key)
        for key in ("target_seasons", "quantiles", "context_max",
                    "random_seed", "n_estimators", "device")
    )
    checks["exact_target_seasons"] = (
        control.get("target_seasons") == TARGET_SEASONS
        and treatment.get("target_seasons") == TARGET_SEASONS
    )
    checks["exact_output_rows"] = (
        control.get("output_rows") == EXPECTED_ROWS
        and treatment.get("output_rows") == EXPECTED_ROWS
        and control.get("unique_keys") == EXPECTED_ROWS
        and treatment.get("unique_keys") == EXPECTED_ROWS
    )
    checks["target_counts_match"] = all(
        control["folds"][str(season)]["target_rows"]
        == treatment["folds"][str(season)]["target_rows"]
        for season in TARGET_SEASONS
    )
    checks["treatment_contexts_active_only"] = all(
        treatment["folds"][str(season)]["sampled_inactive_rows"] == 0
        for season in TARGET_SEASONS
    )
    checks["control_exercises_defect"] = all(
        control["folds"][str(season)]["sampled_inactive_rows"] > 0
        for season in TARGET_SEASONS
    )
    checks["treatment_removes_eligible_inactive_labels"] = all(
        treatment["folds"][str(season)]["eligible_context_rows"]
        < control["folds"][str(season)]["eligible_context_rows"]
        for season in TARGET_SEASONS
    )
    normalized = {name: bool(value) for name, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def validate_tables(control: pd.DataFrame, treatment: pd.DataFrame) -> dict:
    keys = ["season", "week", "gsis_id"]
    checks: dict[str, bool] = {}
    checks["row_counts"] = (
        len(control) == EXPECTED_ROWS and len(treatment) == EXPECTED_ROWS
    )
    checks["unique_keys"] = (
        not control.duplicated(keys).any()
        and not treatment.duplicated(keys).any()
    )
    left = control.sort_values(keys).reset_index(drop=True)
    right = treatment.sort_values(keys).reset_index(drop=True)
    checks["exact_key_equality"] = left[keys].equals(right[keys])
    checks["exact_seasons"] = (
        sorted(left.season.astype(int).unique().tolist()) == TARGET_SEASONS
        and sorted(right.season.astype(int).unique().tolist()) == TARGET_SEASONS
    )
    required = {"mean", *QUANTILE_COLUMNS, "arm", "active_context_only",
                "feature_contract_sha256", "code_sha"}
    checks["required_columns"] = (
        required.issubset(control.columns) and required.issubset(treatment.columns)
    )
    if checks["required_columns"]:
        control_values = left[["mean", *QUANTILE_COLUMNS]].to_numpy(float)
        treatment_values = right[["mean", *QUANTILE_COLUMNS]].to_numpy(float)
        checks["finite_predictions"] = (
            np.isfinite(control_values).all()
            and np.isfinite(treatment_values).all()
        )
        checks["ordered_quantiles"] = (
            np.all(np.diff(control_values[:, 1:], axis=1) >= -1e-8)
            and np.all(np.diff(treatment_values[:, 1:], axis=1) >= -1e-8)
        )
        checks["row_arm_identity"] = (
            left.arm.eq("control").all()
            and not left.active_context_only.astype(bool).any()
            and right.arm.eq("active_only").all()
            and right.active_context_only.astype(bool).all()
        )
        checks["predictions_changed"] = bool(
            np.any(np.abs(control_values - treatment_values) > 1e-8)
        )
    else:
        for name in ("finite_predictions", "ordered_quantiles",
                     "row_arm_identity", "predictions_changed"):
            checks[name] = False
    normalized = {name: bool(value) for name, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-log", type=Path, required=True)
    parser.add_argument("--treatment-log", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--version", choices=("v1", "v2"), default="v1")
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    reports = {
        "control": extract_report(args.control_log),
        "treatment": extract_report(args.treatment_log),
    }
    report_validation = validate_reports(
        reports["control"], reports["treatment"], args.code_sha, args.version)
    registered_tables = tables_for_version(args.version)
    tables = {
        arm: query_df(
            f"SELECT * FROM `{settings.features}.{table}` "
            "WHERE season IN (2022, 2023, 2024, 2025)"
        )
        for arm, table in registered_tables.items()
    }
    table_validation = validate_tables(tables["control"], tables["active_only"])
    output = {
        "disposition": (
            "tabpfn-active-label-caches-valid"
            if report_validation["passes"] and table_validation["passes"]
            else "tabpfn-active-label-caches-invalid"
        ),
        "passes": bool(report_validation["passes"] and table_validation["passes"]),
        "report_validation": report_validation,
        "table_validation": table_validation,
        "reports": reports,
        "version": args.version,
        "tables": registered_tables,
    }
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not output["passes"]:
        raise SystemExit("ABORT: active-label cache validation failed")
    print(f"TABPFN_ACTIVE_LABEL_VALIDATED {args.output}")


if __name__ == "__main__":
    main()
