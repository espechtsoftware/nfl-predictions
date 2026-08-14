#!/usr/bin/env python3
"""Mechanical validation for the frozen current-stack Route cache pair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


PREFIX = "TABPFN_ROUTE_CHANNEL_JSON="
TARGET_SEASONS = [2022, 2023, 2024, 2025]
EXPECTED_ROWS = 52_307
BASE_FEATURE_SHA = (
    "52cc95c500bc3bd4223baacb29be73e3df4d637ce289b6431735cddd46195b83"
)
SOURCE_ROWS = 102_927
SOURCE_CHECKSUM = 1_904_430_067_081_090_565
ROUTE_FEATURES = (
    "fp_route_share_last",
    "fp_route_share_l4",
    "fp_route_share_jump",
    "fp_route_cross_season",
)
TABLES = {
    "control": "tabpfn_route_channel_control_v1",
    "marginal": "tabpfn_route_channel_marginal_v1",
}
INCUMBENT_TABLE = "tabpfn_active_label_treatment_v2"
QUANTILE_COLUMNS = (
    "q01", "q05", "q10", "q20", "q30", "q40", "q50",
    "q60", "q70", "q80", "q90", "q95", "q99",
)
VALUE_COLUMNS = ("mean", *QUANTILE_COLUMNS)


def extract_report(path: Path) -> dict:
    payloads = [
        json.loads(line.split(PREFIX, 1)[1])
        for line in path.read_text(encoding="utf-8").splitlines()
        if PREFIX in line
    ]
    if len(payloads) != 1:
        raise ValueError(f"expected one Route-channel report in {path}; got {len(payloads)}")
    return payloads[0]


def validate_reports(
    control: dict,
    marginal: dict,
    incumbent_validation: dict,
    code_sha: str,
) -> dict:
    incumbent = incumbent_validation.get("reports", {}).get("treatment", {})
    checks: dict[str, bool] = {}
    checks["generated_disposition"] = all(
        report.get("disposition") == "tabpfn-route-channel-cache-generated"
        for report in (control, marginal)
    )
    checks["arm_identity"] = (
        control.get("arm") == "control"
        and marginal.get("arm") == "marginal"
        and control.get("active_context_only") is True
        and marginal.get("active_context_only") is True
        and control.get("route_marginal") is False
        and marginal.get("route_marginal") is True
    )
    checks["code_identity"] = (
        control.get("code_sha") == code_sha
        and marginal.get("code_sha") == code_sha
    )
    checks["output_table_identity"] = (
        control.get("output_table", "").endswith(TABLES["control"])
        and marginal.get("output_table", "").endswith(TABLES["marginal"])
    )
    checks["same_source_snapshot"] = (
        control.get("training_source") == marginal.get("training_source")
        and control.get("training_source") == incumbent.get("training_source")
        and control.get("training_source", {}).get("rows") == SOURCE_ROWS
        and control.get("training_source", {}).get("content_checksum")
        == SOURCE_CHECKSUM
    )
    checks["incumbent_validation_identity"] = (
        incumbent_validation.get("version") == "v2"
        and incumbent_validation.get("passes") is True
        and incumbent_validation.get("disposition")
        == "tabpfn-active-label-caches-valid"
    )
    base = list(control.get("feature_columns", []))
    treatment = list(marginal.get("feature_columns", []))
    incumbent_features = list(incumbent.get("feature_columns", []))
    checks["control_reuses_incumbent_features"] = (
        base == incumbent_features
        and control.get("base_feature_contract_sha256") == BASE_FEATURE_SHA
        and control.get("feature_contract_sha256") == BASE_FEATURE_SHA
        and incumbent.get("feature_contract_sha256") == BASE_FEATURE_SHA
    )
    checks["marginal_adds_exact_route_fields"] = (
        set(treatment) - set(base) == set(ROUTE_FEATURES)
        and set(base) - set(treatment) == set()
        and len(treatment) == len(base) + len(ROUTE_FEATURES)
        and marginal.get("route_features") == list(ROUTE_FEATURES)
        and marginal.get("base_feature_contract_sha256") == BASE_FEATURE_SHA
        and marginal.get("feature_contract_sha256") != BASE_FEATURE_SHA
    )
    checks["same_frozen_hyperparameters"] = all(
        control.get(key) == marginal.get(key) == incumbent.get(key)
        for key in (
            "target_seasons", "quantiles", "context_max", "random_seed",
            "n_estimators", "device",
        )
    )
    checks["exact_target_seasons"] = (
        control.get("target_seasons") == TARGET_SEASONS
        and marginal.get("target_seasons") == TARGET_SEASONS
    )
    checks["exact_output_rows"] = all(
        report.get("output_rows") == EXPECTED_ROWS
        and report.get("unique_keys") == EXPECTED_ROWS
        for report in (control, marginal)
    )
    checks["fold_counts_match"] = all(
        control.get("folds", {}).get(str(season), {}).get("target_rows")
        == marginal.get("folds", {}).get(str(season), {}).get("target_rows")
        == incumbent.get("folds", {}).get(str(season), {}).get("target_rows")
        and control.get("folds", {}).get(str(season), {}).get(
            "sampled_context_rows")
        == marginal.get("folds", {}).get(str(season), {}).get(
            "sampled_context_rows")
        == incumbent.get("folds", {}).get(str(season), {}).get(
            "sampled_context_rows")
        for season in TARGET_SEASONS
    )
    checks["contexts_active_only"] = all(
        control.get("folds", {}).get(str(season), {}).get(
            "sampled_inactive_rows") == 0
        and marginal.get("folds", {}).get(str(season), {}).get(
            "sampled_inactive_rows") == 0
        for season in TARGET_SEASONS
    )
    checks["route_support_exercised"] = all(
        marginal.get("folds", {}).get(str(season), {}).get(
            "route_target_rows", 0) > 0
        for season in TARGET_SEASONS
    ) and all(
        marginal.get("folds", {}).get(str(season), {}).get(
            "route_context_rows", 0) > 0
        for season in (2023, 2024, 2025)
    )
    normalized = {name: bool(value) for name, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def _table_basics(frame: pd.DataFrame, arm: str) -> dict[str, bool]:
    keys = ["season", "week", "gsis_id"]
    required = {
        *keys, *VALUE_COLUMNS, "arm", "active_context_only",
        "route_marginal", "base_feature_contract_sha256",
        "feature_contract_sha256", "code_sha",
    }
    checks = {
        "row_count": len(frame) == EXPECTED_ROWS,
        "unique_keys": not frame.duplicated(keys).any(),
        "required_columns": required.issubset(frame.columns),
        "exact_seasons": sorted(frame.season.astype(int).unique().tolist())
        == TARGET_SEASONS if not frame.empty and "season" in frame else False,
    }
    if checks["required_columns"]:
        values = frame[list(VALUE_COLUMNS)].to_numpy(float)
        checks.update({
            "finite_predictions": bool(np.isfinite(values).all()),
            "ordered_quantiles": bool(np.all(
                np.diff(frame[list(QUANTILE_COLUMNS)].to_numpy(float), axis=1)
                >= -1e-8
            )),
            "row_arm_identity": bool(frame.arm.eq(arm).all()),
            "active_context_only": bool(
                frame.active_context_only.astype(bool).all()),
            "route_marginal_identity": bool(
                frame.route_marginal.astype(bool).eq(arm == "marginal").all()),
            "base_feature_identity": bool(
                frame.base_feature_contract_sha256.eq(BASE_FEATURE_SHA).all()),
        })
    return checks


def validate_tables(
    control: pd.DataFrame,
    marginal: pd.DataFrame,
    incumbent: pd.DataFrame,
) -> dict:
    keys = ["season", "week", "gsis_id"]
    checks: dict[str, bool] = {}
    basics = {
        "control": _table_basics(control, "control"),
        "marginal": _table_basics(marginal, "marginal"),
    }
    checks["table_basics"] = all(
        all(values.values()) for values in basics.values())
    left = control.sort_values(keys).reset_index(drop=True)
    right = marginal.sort_values(keys).reset_index(drop=True)
    prior = incumbent.sort_values(keys).reset_index(drop=True)
    checks["exact_pair_key_equality"] = (
        len(left) == len(right) and left[keys].equals(right[keys])
    )
    checks["incumbent_key_equality"] = (
        len(left) == len(prior) and left[keys].equals(prior[keys])
    )
    if all(column in left for column in VALUE_COLUMNS) and all(
        column in right for column in VALUE_COLUMNS
    ):
        checks["marginal_predictions_changed"] = bool(np.any(np.abs(
            left[list(VALUE_COLUMNS)].to_numpy(float)
            - right[list(VALUE_COLUMNS)].to_numpy(float)
        ) > 1e-8))
    else:
        checks["marginal_predictions_changed"] = False
    reproduction_delta = float("inf")
    if checks["incumbent_key_equality"] and all(
        column in prior for column in VALUE_COLUMNS
    ):
        reproduction_delta = float(np.max(np.abs(
            left[list(VALUE_COLUMNS)].to_numpy(float)
            - prior[list(VALUE_COLUMNS)].to_numpy(float)
        ), initial=0.0))
    checks["control_reproduces_incumbent_at_1e_10"] = reproduction_delta <= 1e-10
    normalized = {name: bool(value) for name, value in checks.items()}
    return {
        "checks": normalized,
        "table_basics": basics,
        "control_incumbent_max_abs_delta": reproduction_delta,
        "passes": all(normalized.values()),
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-log", type=Path, required=True)
    parser.add_argument("--marginal-log", type=Path, required=True)
    parser.add_argument("--incumbent-validation", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    reports = {
        "control": extract_report(args.control_log),
        "marginal": extract_report(args.marginal_log),
    }
    incumbent_validation = json.loads(
        args.incumbent_validation.read_text(encoding="utf-8"))
    report_validation = validate_reports(
        reports["control"], reports["marginal"], incumbent_validation,
        args.code_sha,
    )
    tables = {
        arm: query_df(
            f"SELECT * FROM `{settings.features}.{table}` "
            "WHERE season IN (2022, 2023, 2024, 2025)"
        )
        for arm, table in TABLES.items()
    }
    incumbent = query_df(
        f"SELECT * FROM `{settings.features}.{INCUMBENT_TABLE}` "
        "WHERE season IN (2022, 2023, 2024, 2025)"
    )
    table_validation = validate_tables(
        tables["control"], tables["marginal"], incumbent)
    passes = bool(report_validation["passes"] and table_validation["passes"])
    output = {
        "disposition": (
            "tabpfn-route-channel-caches-valid"
            if passes else "tabpfn-route-channel-caches-invalid"
        ),
        "passes": passes,
        "report_validation": report_validation,
        "table_validation": table_validation,
        "reports": reports,
        "tables": TABLES,
        "incumbent_table": INCUMBENT_TABLE,
    }
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not passes:
        raise SystemExit("ABORT: Route-channel cache validation failed")
    print(f"TABPFN_ROUTE_CHANNEL_VALIDATED {args.output}")


if __name__ == "__main__":
    main()
