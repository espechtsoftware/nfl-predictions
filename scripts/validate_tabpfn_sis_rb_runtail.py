#!/usr/bin/env python3
"""Mechanical validation for the adaptive SIS RB run-tail cache pair."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

from nfl_dfs.research.tabpfn_sis_rb_runtail import (
    SIS_RB_RUNTAIL_FEATURES,
    SIS_SOURCE_RUN,
    SOURCE_HASH_COLUMNS,
    feature_contract,
)


PREFIX = "TABPFN_SIS_RB_RUNTAIL_JSON="
TABLES = {
    "control": "tabpfn_sis_rb_runtail_control_v1",
    "treatment": "tabpfn_sis_rb_runtail_treatment_v1",
}
ROOT = Path(__file__).parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_tabpfn_sis_rb_rdef_shared",
    ROOT / "scripts/validate_tabpfn_sis_rb_rdef.py",
)
assert SPEC and SPEC.loader
SHARED = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SHARED)


def extract_report(path: Path) -> dict:
    payloads = [
        json.loads(line.split(PREFIX, 1)[1])
        for line in path.read_text(encoding="utf-8").splitlines()
        if PREFIX in line
    ]
    if len(payloads) != 1:
        raise ValueError(f"expected one SIS RB run-tail report in {path}")
    return payloads[0]


def validate_reports(
    control: dict, treatment: dict, code_sha: str,
    baseline_features: list[str],
) -> dict:
    control_features = feature_contract(baseline_features, "control")
    treatment_features = feature_contract(baseline_features, "treatment")
    reports = (control, treatment)
    checks = {
        "arm_identity": control.get("arm") == "control"
        and treatment.get("arm") == "treatment",
        "adaptive_identity": all(
            report.get("label_law") == "active_only"
            and report.get("feature_law") == "base"
            and report.get("active_context_only") is True
            for report in reports
        ),
        "code_identity": control.get("code_sha") == code_sha
        and treatment.get("code_sha") == code_sha,
        "output_table_identity": control.get("output_table", "").endswith(
            TABLES["control"]
        ) and treatment.get("output_table", "").endswith(TABLES["treatment"]),
        "same_source_snapshots": control.get("training_source")
        == treatment.get("training_source")
        and control.get("sis_source") == treatment.get("sis_source"),
        "source_identity": all(
            report.get("sis_source", {}).get("source_run_ids") == [SIS_SOURCE_RUN]
            and report.get("sis_source", {}).get("expected_source_run")
            == SIS_SOURCE_RUN
            and set(report.get("sis_source", {}).get(
                "source_hash_identities", {}
            )) == set(SOURCE_HASH_COLUMNS)
            and all(len(values) == 1 for values in report.get(
                "sis_source", {}
            ).get("source_hash_identities", {}).values())
            for report in reports
        ),
        "exact_feature_contracts": control.get("feature_columns")
        == control_features and treatment.get("feature_columns")
        == treatment_features and treatment_features
        == [*control_features, *SIS_RB_RUNTAIL_FEATURES],
        "distinct_feature_hashes": bool(control.get("feature_contract_sha256"))
        and bool(treatment.get("feature_contract_sha256"))
        and control.get("feature_contract_sha256")
        != treatment.get("feature_contract_sha256"),
        "same_hyperparameters": all(
            control.get(key) == treatment.get(key)
            for key in (
                "target_seasons", "quantiles", "context_max", "random_seed",
                "n_estimators", "device",
            )
        ),
        "exact_target_seasons": control.get("target_seasons")
        == SHARED.TARGET_SEASONS
        and treatment.get("target_seasons") == SHARED.TARGET_SEASONS,
        "exact_output_rows": all(
            report.get(key) == SHARED.EXPECTED_ROWS
            for report in reports for key in ("output_rows", "unique_keys")
        ),
        "same_coverage": control.get("active_rb_coverage")
        == treatment.get("active_rb_coverage"),
        "minimum_coverage": all(any(
            row.get("season") == season and row.get("support_rate", 0) >= 0.80
            for row in control.get("active_rb_coverage", [])
        ) for season in (2023, 2024, 2025)),
        "same_fold_counts": all(
            control.get("folds", {}).get(str(season), {}).get("target_rows")
            == treatment.get("folds", {}).get(str(season), {}).get("target_rows")
            and control.get("folds", {}).get(str(season), {}).get(
                "sampled_context_rows"
            ) == treatment.get("folds", {}).get(str(season), {}).get(
                "sampled_context_rows"
            )
            for season in SHARED.TARGET_SEASONS
        ),
        "active_context_contract": all(
            report.get("folds", {}).get(str(season), {}).get(
                "sampled_inactive_rows", -1
            ) == 0
            for report in reports for season in SHARED.TARGET_SEASONS
        ),
    }
    normalized = {key: bool(value) for key, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def validate_table_report_identity(
    frames: dict[str, object], reports: dict[str, dict], code_sha: str,
) -> dict:
    checks = {}
    for arm in TABLES:
        frame = frames[arm]
        required = {
            "arm", "label_law", "feature_law", "active_context_only",
            "code_sha", "feature_contract_sha256",
        }
        checks[f"{arm}_required_identity_columns"] = required.issubset(frame)
        if not checks[f"{arm}_required_identity_columns"] or frame.empty:
            checks[f"{arm}_row_identity"] = False
            continue
        checks[f"{arm}_row_identity"] = (
            frame.arm.eq(arm).all()
            and frame.label_law.eq("active_only").all()
            and frame.feature_law.eq("base").all()
            and frame.active_context_only.fillna(False).astype(bool).all()
            and frame.code_sha.eq(code_sha).all()
            and frame.feature_contract_sha256.eq(
                reports[arm].get("feature_contract_sha256")
            ).all()
        )
    normalized = {key: bool(value) for key, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--control-log", type=Path, required=True)
    parser.add_argument("--treatment-log", type=Path, required=True)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    reports = {
        "control": extract_report(args.control_log),
        "treatment": extract_report(args.treatment_log),
    }
    frames = {
        arm: query_df(f"SELECT * FROM `{settings.features}.{table}`")
        for arm, table in TABLES.items()
    }
    inherited = query_df(
        f"SELECT * FROM `{settings.features}.tabpfn_active_label_treatment_v2`"
    )
    report_validation = validate_reports(
        reports["control"], reports["treatment"], args.code_sha,
        args.features.read_text(encoding="utf-8").split(),
    )
    table_validation = SHARED.validate_tables(
        frames["control"], frames["treatment"]
    )
    table_report_identity = validate_table_report_identity(
        frames, reports, args.code_sha
    )
    reproduction = SHARED.validate_control_reproduction(
        frames["control"], inherited
    )
    passes = report_validation["passes"] and table_validation["passes"] \
        and table_report_identity["passes"] and reproduction["passes"]
    output = {
        "disposition": (
            "tabpfn-sis-rb-runtail-caches-valid" if passes
            else "tabpfn-sis-rb-runtail-caches-invalid"
        ),
        "passes": passes,
        "adaptive_retrospective": True,
        "label_law": "active_only",
        "feature_law": "base",
        "inherited_table": "tabpfn_active_label_treatment_v2",
        "tables": TABLES,
        "reports": reports,
        "report_validation": report_validation,
        "table_validation": table_validation,
        "table_report_identity": table_report_identity,
        "control_reproduction": reproduction,
    }
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not passes:
        raise SystemExit("SIS RB run-tail cache validation failed")


if __name__ == "__main__":
    main()
