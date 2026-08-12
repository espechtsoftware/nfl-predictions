#!/usr/bin/env python3
"""Mechanical, outcome-free validation of the canonical PIT-clean cache."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd


PREFIX = "TABPFN_GEN_JSON="
TARGET_SEASONS = [2019, 2021, 2022, 2023, 2024, 2025]
OUTPUT_TABLE = "tabpfn_projections_pit_v2"
QUANTILE_COLUMNS = (
    "q01", "q05", "q10", "q20", "q30", "q40", "q50",
    "q60", "q70", "q80", "q90", "q95", "q99",
)


def extract_report(path: Path) -> dict:
    payloads = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if PREFIX in line:
            payloads.append(json.loads(line.split(PREFIX, 1)[1]))
    if len(payloads) != 1:
        raise ValueError(f"expected one canonical report in {path}; got {len(payloads)}")
    return payloads[0]


def validate_report(
    report: dict,
    *,
    code_sha: str,
    feature_sha: str,
    source_identity: dict,
    expected_rows: int,
) -> dict:
    checks = {
        "disposition": report.get("disposition") == "tabpfn-canonical-cache-generated",
        "code_identity": report.get("code_sha") == code_sha,
        "output_table_identity": report.get("output_table", "").endswith(OUTPUT_TABLE),
        "write_once": str(report.get("write_disposition", "")).endswith("WRITE_EMPTY"),
        "target_seasons": report.get("target_seasons") == TARGET_SEASONS,
        "context_law": report.get("context_law") == "all-prior-nonnull-labels",
        "frozen_hyperparameters": (
            report.get("context_max") == 28_000
            and report.get("random_seed") == 7
            and report.get("n_estimators") == 4
        ),
        "feature_contract": report.get("feature_contract_sha256") == feature_sha,
        "source_identity": report.get("training_source") == source_identity,
        "output_rows": (
            report.get("output_rows") == expected_rows
            and report.get("unique_keys") == expected_rows
        ),
    }
    normalized = {name: bool(value) for name, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def validate_table(table: pd.DataFrame, expected_keys: pd.DataFrame) -> dict:
    keys = ["season", "week", "gsis_id"]
    left = table.sort_values(keys).reset_index(drop=True)
    right = expected_keys.sort_values(keys).reset_index(drop=True)
    required = {"mean", *QUANTILE_COLUMNS}
    checks = {
        "row_count": len(left) == len(right),
        "unique_keys": not left.duplicated(keys).any(),
        "exact_keys": left[keys].equals(right[keys]),
        "exact_seasons": sorted(left.season.astype(int).unique().tolist()) == TARGET_SEASONS,
        "required_columns": required.issubset(left.columns),
    }
    if checks["required_columns"]:
        values = left[["mean", *QUANTILE_COLUMNS]].to_numpy(float)
        checks["finite_predictions"] = np.isfinite(values).all()
        checks["ordered_quantiles"] = np.all(
            np.diff(left[list(QUANTILE_COLUMNS)].to_numpy(float), axis=1) >= -1e-8
        )
    else:
        checks["finite_predictions"] = False
        checks["ordered_quantiles"] = False
    normalized = {name: bool(value) for name, value in checks.items()}
    return {"checks": normalized, "passes": all(normalized.values())}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path, required=True)
    parser.add_argument("--code-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    from google.cloud import bigquery
    from nfl_dfs.bq import query_df
    from nfl_dfs.config import settings

    report = extract_report(args.log)
    source_table = f"{settings.project}.nfl_features.player_week_training"
    client = bigquery.Client(project=settings.project)
    source_meta = client.get_table(source_table)
    source_schema = json.dumps(
        [(field.name, field.field_type, field.mode) for field in source_meta.schema],
        separators=(",", ":"),
    )
    source_checksum = int(client.query(f"""
        SELECT BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
        FROM `{source_table}` t
    """).to_dataframe().iloc[0]["checksum"])
    source_counts = query_df(f"""
        SELECT
          COUNT(*) AS rows,
          COUNTIF(COALESCE(was_active, FALSE)) AS active_rows,
          COUNTIF(NOT COALESCE(was_active, FALSE)) AS inactive_rows
        FROM `{source_table}`
        WHERE position IN ('QB', 'RB', 'WR', 'TE')
    """).iloc[0]
    source_identity = {
        "table": source_table,
        "last_modified": source_meta.modified.isoformat(),
        "schema_sha256": hashlib.sha256(source_schema.encode()).hexdigest(),
        "content_checksum": source_checksum,
        "rows": int(source_counts["rows"]),
        "active_rows": int(source_counts["active_rows"]),
        "inactive_rows": int(source_counts["inactive_rows"]),
    }
    expected_keys = query_df(f"""
        SELECT season, week, gsis_id
        FROM `{source_table}`
        WHERE position IN ('QB', 'RB', 'WR', 'TE')
          AND season IN ({','.join(map(str, TARGET_SEASONS))})
    """)
    table = query_df(
        f"SELECT * FROM `{settings.features}.{OUTPUT_TABLE}`"
    )
    feature_path = Path(__file__).parent / "tabpfn_gen" / "features.txt"
    feature_sha = hashlib.sha256(feature_path.read_bytes()).hexdigest()
    report_validation = validate_report(
        report,
        code_sha=args.code_sha,
        feature_sha=feature_sha,
        source_identity=source_identity,
        expected_rows=len(expected_keys),
    )
    table_validation = validate_table(table, expected_keys)
    passes = bool(report_validation["passes"] and table_validation["passes"])
    output = {
        "disposition": (
            "tabpfn-canonical-pit-cache-valid"
            if passes else "tabpfn-canonical-pit-cache-invalid"
        ),
        "passes": passes,
        "report_validation": report_validation,
        "table_validation": table_validation,
        "report": report,
    }
    args.output.write_text(
        json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    if not passes:
        raise SystemExit("ABORT: canonical PIT-clean cache validation failed")
    print(f"TABPFN_CANONICAL_PIT_VALIDATED {args.output}")


if __name__ == "__main__":
    main()
