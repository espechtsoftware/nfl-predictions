#!/usr/bin/env python3
"""Mechanical validation for the frozen TabPFN SCHED cache pair."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


PREFIX = "TABPFN_SCHED_JSON="
TARGET_SEASONS = [2022, 2023, 2024, 2025]
EXPECTED_ROWS = 52_307
SCHED_FEATURES = ["net_rest_diff", "body_clock_hour"]
TABLES = {
    "control": "tabpfn_sched_control_v1",
    "treatment": "tabpfn_sched_treatment_v1",
}
QUANTILE_COLUMNS = (
    "q01", "q05", "q10", "q20", "q30", "q40", "q50",
    "q60", "q70", "q80", "q90", "q95", "q99",
)


def extract_report(path: Path) -> dict:
    payloads = [
        json.loads(line.split(PREFIX, 1)[1])
        for line in path.read_text(encoding="utf-8").splitlines()
        if PREFIX in line
    ]
    if len(payloads) != 1:
        raise ValueError(f"expected one SCHED report in {path}; got {len(payloads)}")
    return payloads[0]


def expected_features(path: Path) -> tuple[list[str], list[str]]:
    control = sorted(path.read_text(encoding="utf-8").split())
    return control, [*control, *SCHED_FEATURES]


def validate_reports(
    control: dict,
    treatment: dict,
    code_sha: str,
    label_law: str,
    control_features: list[str],
    treatment_features: list[str],
) -> dict:
    active_only = label_law == "active_only"
    warmup = control.get("inherited_rng_warmup", {})
    treatment_warmup = treatment.get("inherited_rng_warmup", {})
    checks = {
        "arm_identity": (
            control.get("arm") == "control"
            and treatment.get("arm") == "treatment"
        ),
        "label_law_identity": (
            control.get("label_law") == label_law
            and treatment.get("label_law") == label_law
            and control.get("active_context_only") is active_only
            and treatment.get("active_context_only") is active_only
        ),
        "code_identity": (
            control.get("code_sha") == code_sha
            and treatment.get("code_sha") == code_sha
        ),
        "output_table_identity": (
            control.get("output_table", "").endswith(TABLES["control"])
            and treatment.get("output_table", "").endswith(TABLES["treatment"])
        ),
        "same_source_snapshot": (
            control.get("training_source") == treatment.get("training_source")
        ),
        "exact_feature_contracts": (
            control.get("feature_columns") == control_features
            and treatment.get("feature_columns") == treatment_features
            and treatment_features == [*control_features, *SCHED_FEATURES]
        ),
        "distinct_feature_hashes": (
            bool(control.get("feature_contract_sha256"))
            and bool(treatment.get("feature_contract_sha256"))
            and control.get("feature_contract_sha256")
            != treatment.get("feature_contract_sha256")
        ),
        "same_frozen_hyperparameters": all(
            control.get(key) == treatment.get(key)
            for key in (
                "target_seasons", "quantiles", "context_max",
                "random_seed", "n_estimators", "device",
            )
        ),
        "exact_target_seasons": (
            control.get("target_seasons") == TARGET_SEASONS
            and treatment.get("target_seasons") == TARGET_SEASONS
        ),
        "exact_output_rows": (
            control.get("output_rows") == EXPECTED_ROWS
            and treatment.get("output_rows") == EXPECTED_ROWS
            and control.get("unique_keys") == EXPECTED_ROWS
            and treatment.get("unique_keys") == EXPECTED_ROWS
        ),
        "target_counts_match": all(
            control.get("folds", {}).get(str(season), {}).get("target_rows")
            == treatment.get("folds", {}).get(str(season), {}).get("target_rows")
            for season in TARGET_SEASONS
        ),
        "context_counts_match": all(
            control.get("folds", {}).get(str(season), {}).get(
                "sampled_context_rows")
            == treatment.get("folds", {}).get(str(season), {}).get(
                "sampled_context_rows")
            for season in TARGET_SEASONS
        ),
        "inherited_rng_sequence": (
            set(warmup) == {"2019", "2021"}
            and set(treatment_warmup) == {"2019", "2021"}
            if label_law == "current"
            else warmup == {} and treatment_warmup == {}
        ),
        "active_context_contract": all(
            (
                control.get("folds", {}).get(str(season), {}).get(
                    "sampled_inactive_rows", -1) == 0
                and treatment.get("folds", {}).get(str(season), {}).get(
                    "sampled_inactive_rows", -1) == 0
            ) if active_only else (
                control.get("folds", {}).get(str(season), {}).get(
                    "sampled_inactive_rows", 0) > 0
                and treatment.get("folds", {}).get(str(season), {}).get(
                    "sampled_inactive_rows", 0) > 0
            )
            for season in TARGET_SEASONS
        ),
    }
    normalized = {name: bool(value) for name, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def validate_tables(control: pd.DataFrame, treatment: pd.DataFrame) -> dict:
    keys = ["season", "week", "gsis_id"]
    left = control.sort_values(keys).reset_index(drop=True)
    right = treatment.sort_values(keys).reset_index(drop=True)
    required = {
        "mean", *QUANTILE_COLUMNS, "arm", "label_law",
        "active_context_only", "feature_contract_sha256", "code_sha",
    }
    checks = {
        "row_counts": len(left) == EXPECTED_ROWS and len(right) == EXPECTED_ROWS,
        "unique_keys": (
            not left.duplicated(keys).any() and not right.duplicated(keys).any()
        ),
        "exact_key_equality": left[keys].equals(right[keys]),
        "exact_seasons": (
            sorted(left.season.astype(int).unique().tolist()) == TARGET_SEASONS
            and sorted(right.season.astype(int).unique().tolist())
            == TARGET_SEASONS
        ),
        "required_columns": (
            required.issubset(left.columns) and required.issubset(right.columns)
        ),
    }
    if checks["required_columns"]:
        left_values = left[["mean", *QUANTILE_COLUMNS]].to_numpy(float)
        right_values = right[["mean", *QUANTILE_COLUMNS]].to_numpy(float)
        checks.update({
            "finite_predictions": (
                np.isfinite(left_values).all()
                and np.isfinite(right_values).all()
            ),
            "ordered_quantiles": (
                np.all(np.diff(left_values[:, 1:], axis=1) >= -1e-8)
                and np.all(np.diff(right_values[:, 1:], axis=1) >= -1e-8)
            ),
            "row_arm_identity": (
                left.arm.eq("control").all()
                and right.arm.eq("treatment").all()
            ),
            "row_common_law": (
                left.label_law.nunique() == 1
                and right.label_law.nunique() == 1
                and left.label_law.iloc[0] == right.label_law.iloc[0]
                and left.active_context_only.nunique() == 1
                and right.active_context_only.nunique() == 1
                and bool(left.active_context_only.iloc[0])
                == bool(right.active_context_only.iloc[0])
            ),
            "row_code_identity": (
                left.code_sha.nunique() == 1
                and right.code_sha.nunique() == 1
                and left.code_sha.iloc[0] == right.code_sha.iloc[0]
            ),
            "distinct_feature_hashes": (
                left.feature_contract_sha256.nunique() == 1
                and right.feature_contract_sha256.nunique() == 1
                and left.feature_contract_sha256.iloc[0]
                != right.feature_contract_sha256.iloc[0]
            ),
            "predictions_changed": bool(
                np.any(np.abs(left_values - right_values) > 1e-8)
            ),
        })
    else:
        for name in (
            "finite_predictions", "ordered_quantiles", "row_arm_identity",
            "row_common_law", "row_code_identity", "distinct_feature_hashes",
            "predictions_changed",
        ):
            checks[name] = False
    normalized = {name: bool(value) for name, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def validate_control_reproduction(
    control: pd.DataFrame, inherited: pd.DataFrame,
) -> dict:
    """Prove that the separately generated 33-feature control is inherited law."""
    keys = ["season", "week", "gsis_id"]
    columns = ["mean", *QUANTILE_COLUMNS]
    left = control.sort_values(keys).reset_index(drop=True)
    right = inherited.sort_values(keys).reset_index(drop=True)
    same_keys = (
        len(left) == EXPECTED_ROWS
        and len(right) == EXPECTED_ROWS
        and not left.duplicated(keys).any()
        and not right.duplicated(keys).any()
        and left[keys].equals(right[keys])
    )
    required = set(columns).issubset(left.columns) \
        and set(columns).issubset(right.columns)
    maximum_delta = float("inf")
    if same_keys and required:
        maximum_delta = float(np.max(np.abs(
            left[columns].to_numpy(float)
            - right[columns].to_numpy(float)
        ), initial=0.0))
    checks = {
        "exact_keys": same_keys,
        "required_prediction_columns": required,
        "maximum_abs_delta_at_most_1e_10": maximum_delta <= 1e-10,
    }
    return {
        "checks": {name: bool(value) for name, value in checks.items()},
        "passes": all(checks.values()),
        "maximum_abs_delta": maximum_delta,
    }


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-log", type=Path, required=True)
    parser.add_argument("--treatment-log", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--label-law", choices=("current", "active_only"),
                        required=True)
    parser.add_argument("--inherited-table", choices=(
        "tabpfn_projections_pit_v2", "tabpfn_active_label_treatment_v2",
    ), required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    control_features, treatment_features = expected_features(args.features)
    reports = {
        "control": extract_report(args.control_log),
        "treatment": extract_report(args.treatment_log),
    }
    report_validation = validate_reports(
        reports["control"], reports["treatment"], args.code_sha,
        args.label_law, control_features, treatment_features)
    tables = {
        arm: query_df(
            f"SELECT * FROM `{settings.features}.{table}` "
            "WHERE season IN (2022, 2023, 2024, 2025)"
        )
        for arm, table in TABLES.items()
    }
    table_validation = validate_tables(tables["control"], tables["treatment"])
    inherited = query_df(
        f"SELECT * FROM `{settings.features}.{args.inherited_table}` "
        "WHERE season IN (2022, 2023, 2024, 2025)"
    )
    control_reproduction = validate_control_reproduction(
        tables["control"], inherited)
    output = {
        "disposition": (
            "tabpfn-sched-caches-valid"
            if report_validation["passes"] and table_validation["passes"]
            and control_reproduction["passes"]
            else "tabpfn-sched-caches-invalid"
        ),
        "passes": bool(
            report_validation["passes"] and table_validation["passes"]
            and control_reproduction["passes"]),
        "label_law": args.label_law,
        "inherited_table": args.inherited_table,
        "report_validation": report_validation,
        "table_validation": table_validation,
        "control_reproduction": control_reproduction,
        "reports": reports,
        "tables": TABLES,
    }
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not output["passes"]:
        raise SystemExit("ABORT: SCHED cache validation failed")
    print(f"TABPFN_SCHED_VALIDATED {args.output}")


if __name__ == "__main__":
    main()
