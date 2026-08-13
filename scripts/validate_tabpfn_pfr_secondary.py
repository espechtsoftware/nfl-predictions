#!/usr/bin/env python3
"""Mechanical validation for frozen PFR secondary TabPFN caches."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd


PREFIX = "TABPFN_PFR_SECONDARY_JSON="
ARMS = ("control", "drop_rates", "drop_top_cb", "drop_all")
RATE_FEATURES = (
    "cb_ypt_allowed_l6",
    "cb_comp_rate_allowed_l6",
    "db_ypt_allowed_l6",
)
ARM_DROPS = {
    "control": (),
    "drop_rates": RATE_FEATURES,
    "drop_top_cb": ("top_cb_out",),
    "drop_all": (*RATE_FEATURES, "top_cb_out"),
}
TABLES = {arm: f"tabpfn_pfr_secondary_{arm}_v1" for arm in ARMS}
TARGET_SEASONS = [2022, 2023, 2024, 2025]
EXPECTED_ROWS = 52_307
QUANTILES = (
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
        raise ValueError(f"expected one PFR report in {path}; got {len(payloads)}")
    return payloads[0]


def validate_reports(reports: dict[str, dict], code_sha: str) -> dict:
    control_features = set(reports["control"].get("feature_columns", []))
    checks = {
        "exact_arms": set(reports) == set(ARMS),
        "arm_identity": all(reports[arm].get("arm") == arm for arm in ARMS),
        "code_identity": all(
            reports[arm].get("code_sha") == code_sha for arm in ARMS),
        "table_identity": all(
            reports[arm].get("output_table", "").endswith(TABLES[arm])
            for arm in ARMS),
        "same_source_snapshot": len({
            json.dumps(reports[arm].get("training_source"), sort_keys=True)
            for arm in ARMS
        }) == 1,
        "same_frozen_hyperparameters": all(
            all(reports[arm].get(key) == reports["control"].get(key)
                for key in ("target_seasons", "quantiles", "context_max",
                            "random_seed", "n_estimators", "device"))
            for arm in ARMS),
        "exact_target_seasons": all(
            reports[arm].get("target_seasons") == TARGET_SEASONS
            for arm in ARMS),
        "exact_output_rows": all(
            reports[arm].get("output_rows") == EXPECTED_ROWS
            and reports[arm].get("unique_keys") == EXPECTED_ROWS
            for arm in ARMS),
        "active_only_law": all(
            reports[arm].get("label_law") == "active_only"
            and all(reports[arm]["folds"][str(season)][
                "sampled_inactive_rows"] == 0 for season in TARGET_SEASONS)
            for arm in ARMS),
        "exact_feature_subtraction": all(
            set(reports[arm].get("feature_columns", []))
            == control_features - set(ARM_DROPS[arm])
            and reports[arm].get("dropped_features") == list(ARM_DROPS[arm])
            for arm in ARMS),
        "distinct_feature_hashes": len({
            reports[arm].get("feature_contract_sha256") for arm in ARMS
        }) == len(ARMS),
    }
    normalized = {name: bool(value) for name, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def validate_tables(
    tables: dict[str, pd.DataFrame], inherited: pd.DataFrame,
) -> dict:
    keys = ["season", "week", "gsis_id"]
    value_columns = ["mean", *QUANTILES]
    sorted_tables = {
        arm: table.sort_values(keys).reset_index(drop=True)
        for arm, table in tables.items()
    }
    base = sorted_tables["control"]
    inherited = inherited.sort_values(keys).reset_index(drop=True)
    checks = {
        "row_counts": all(len(table) == EXPECTED_ROWS for table in tables.values()),
        "unique_keys": all(
            not table.duplicated(keys).any() for table in tables.values()),
        "exact_key_equality": all(
            base[keys].equals(sorted_tables[arm][keys]) for arm in ARMS[1:]),
        "inherited_key_equality": base[keys].equals(inherited[keys]),
        "required_columns": all({
            *value_columns, "arm", "label_law", "feature_law",
            "dropped_features", "feature_contract_sha256", "code_sha",
        }.issubset(table.columns) for table in tables.values()),
    }
    if checks["required_columns"]:
        arrays = {
            arm: sorted_tables[arm][value_columns].to_numpy(float)
            for arm in ARMS
        }
        inherited_values = inherited[value_columns].to_numpy(float)
        checks["finite_predictions"] = all(
            np.isfinite(values).all() for values in arrays.values())
        checks["ordered_quantiles"] = all(
            np.all(np.diff(values[:, 1:], axis=1) >= -1e-8)
            for values in arrays.values())
        checks["row_contract_identity"] = all(
            sorted_tables[arm].arm.eq(arm).all()
            and sorted_tables[arm].label_law.eq("active_only").all()
            and sorted_tables[arm].feature_law.eq(arm).all()
            and sorted_tables[arm].dropped_features.eq(
                ",".join(ARM_DROPS[arm])).all()
            for arm in ARMS)
        checks["exact_inherited_control"] = bool(
            np.array_equal(arrays["control"], inherited_values))
        checks["each_treatment_changes_predictions"] = all(
            np.any(np.abs(arrays[arm] - arrays["control"]) > 1e-8)
            for arm in ARMS[1:])
        checks["treatments_are_distinct"] = all(
            np.any(np.abs(arrays[left] - arrays[right]) > 1e-8)
            for index, left in enumerate(ARMS[1:])
            for right in ARMS[index + 2:])
    else:
        for name in (
            "finite_predictions", "ordered_quantiles", "row_contract_identity",
            "exact_inherited_control", "each_treatment_changes_predictions",
            "treatments_are_distinct",
        ):
            checks[name] = False
    normalized = {name: bool(value) for name, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    for arm in ARMS:
        parser.add_argument(f"--{arm.replace('_', '-')}-log", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    reports = {
        arm: extract_report(getattr(args, f"{arm}_log")) for arm in ARMS
    }
    report_validation = validate_reports(reports, args.code_sha)
    tables = {
        arm: query_df(f"""
            SELECT * FROM `{settings.features}.{TABLES[arm]}`
            WHERE season IN (2022, 2023, 2024, 2025)
        """) for arm in ARMS
    }
    inherited = query_df(f"""
        SELECT * FROM `{settings.features}.tabpfn_active_label_treatment_v2`
        WHERE season IN (2022, 2023, 2024, 2025)
    """)
    table_validation = validate_tables(tables, inherited)
    passes = report_validation["passes"] and table_validation["passes"]
    output = {
        "disposition": (
            "tabpfn-pfr-secondary-caches-valid" if passes
            else "tabpfn-pfr-secondary-caches-invalid"),
        "passes": bool(passes),
        "report_validation": report_validation,
        "table_validation": table_validation,
        "reports": reports,
        "tables": TABLES,
        "inherited_control": "tabpfn_active_label_treatment_v2",
    }
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    if not passes:
        raise SystemExit("ABORT: PFR secondary cache validation failed")
    print(f"TABPFN_PFR_SECONDARY_VALIDATED {args.output}")


if __name__ == "__main__":
    main()
