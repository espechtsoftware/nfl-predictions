#!/usr/bin/env python3
"""Outcome-free before/after reconciliation for the 2026-08-11 PIT repair."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import pandas as pd
from google.cloud import bigquery


SNAPSHOT_PREFIX = "pit_pre_ac9a2c2_"
PLAYER_KEYS = ("gsis_id", "season", "week")
TEAM_KEYS = ("team", "season", "week")
TABLE_KEYS = {
    "player_week_usage": PLAYER_KEYS,
    "player_week_injury": PLAYER_KEYS,
    "team_week_vacated": TEAM_KEYS,
    "player_week_training": PLAYER_KEYS,
    "player_week_inference": PLAYER_KEYS,
    "defense_week_allowed": TEAM_KEYS,
    "team_week_pace": TEAM_KEYS,
    "defense_week_blitz": TEAM_KEYS,
    "team_week_target_concentration": TEAM_KEYS,
    "team_week_ftn_offense": TEAM_KEYS,
}
UNCHANGED_TABLES = {
    "player_week_inference", "team_week_pace", "defense_week_blitz",
    "team_week_target_concentration", "team_week_ftn_offense",
}
USAGE_ALLOWED_CHANGES = {
    "rz20_targets_smoothed", "gl3_carries_smoothed",
}
DEFENSE_POSITION_REPAIR_COLUMNS = {
    "qb_fp_allowed_adj_l6", "rb_fp_allowed_adj_l6",
    "wr_fp_allowed_adj_l6", "te_fp_allowed_adj_l6",
}
FLOAT_REBUILD_NOISE_COLUMNS = {
    "epa_per_dropback_allowed_l6", "epa_per_rush_allowed_l6", "xfp_l4",
}
TRAINING_ALLOWED_CHANGES = {
    "rz20_targets_smoothed", "gl3_carries_smoothed",
    "injury_status", "practice_level", "practice_participation_trend",
    "games_missed_l4", "team_vacated_target_share",
    "team_vacated_carry_share", "xtd_receiving_proxy",
    "vacated_capture_tgt", "vacated_capture_car", "ref_flags_prior",
    *DEFENSE_POSITION_REPAIR_COLUMNS,
}


def _safe_alias(column: str) -> str:
    return "changed__" + re.sub(r"[^A-Za-z0-9_]", "_", column)


def _key_text(keys: tuple[str, ...]) -> str:
    return "TO_JSON_STRING(STRUCT(" + ", ".join(keys) + "))"


def _profile(client: bigquery.Client, table: str, keys: tuple[str, ...]) -> dict:
    key = _key_text(keys)
    row = client.query(f"""
        SELECT COUNT(*) AS row_count, COUNT(DISTINCT {key}) AS key_count,
               BIT_XOR(FARM_FINGERPRINT(TO_JSON_STRING(t))) AS checksum
        FROM `{table}` t
    """).to_dataframe().iloc[0]
    return {
        "rows": int(row.row_count),
        "keys": int(row.key_count),
        "checksum": None if pd.isna(row.checksum) else int(row.checksum),
    }


def _schema(client: bigquery.Client, table: str) -> list[tuple[str, str, str]]:
    return [
        (field.name, field.field_type, field.mode)
        for field in client.get_table(table).schema
    ]


def _key_delta(
    client: bigquery.Client,
    old: str,
    new: str,
    keys: tuple[str, ...],
) -> dict:
    using = ", ".join(keys)
    first = keys[0]
    row = client.query(f"""
        SELECT
          COUNTIF(old_key IS NULL) AS new_only,
          COUNTIF(new_key IS NULL) AS old_only
        FROM (
          SELECT o.{first} AS old_key, n.{first} AS new_key
          FROM (SELECT DISTINCT {using} FROM `{old}`) o
          FULL OUTER JOIN (SELECT DISTINCT {using} FROM `{new}`) n
          USING ({using})
        )
    """).to_dataframe().iloc[0]
    return {"new_only": int(row.new_only), "old_only": int(row.old_only)}


def _column_changes(
    client: bigquery.Client,
    old: str,
    new: str,
    keys: tuple[str, ...],
) -> dict[str, int]:
    old_columns = {name for name, *_ in _schema(client, old)}
    new_columns = {name for name, *_ in _schema(client, new)}
    columns = sorted((old_columns & new_columns) - set(keys))
    expressions = []
    aliases = {}
    for column in columns:
        alias = _safe_alias(column)
        aliases[alias] = column
        expressions.append(
            "COUNTIF(COALESCE(TO_JSON_STRING(o.`{0}`), '__SQL_NULL__') "
            "!= COALESCE(TO_JSON_STRING(n.`{0}`), '__SQL_NULL__')) AS `{1}`"
            .format(column, alias)
        )
    using = ", ".join(keys)
    row = client.query(f"""
        SELECT {', '.join(expressions)}
        FROM `{old}` o JOIN `{new}` n USING ({using})
    """).to_dataframe().iloc[0]
    return {aliases[alias]: int(row[alias]) for alias in aliases}


def _numeric_delta_profile(
    client: bigquery.Client,
    old: str,
    new: str,
    keys: tuple[str, ...],
    columns: set[str],
) -> dict[str, dict]:
    """Measure exact and material drift separately for numeric rebuilds."""
    using = ", ".join(keys)
    expressions = []
    aliases: dict[str, tuple[str, str]] = {}
    for column in sorted(columns):
        safe = re.sub(r"[^A-Za-z0-9_]", "_", column)
        for metric, expression in (
            ("null_mismatches",
             f"COUNTIF((o.`{column}` IS NULL) != (n.`{column}` IS NULL))"),
            ("changes_gt_1e12",
             f"COUNTIF(ABS(o.`{column}` - n.`{column}`) > 1e-12)"),
            ("max_abs_delta",
             f"MAX(ABS(o.`{column}` - n.`{column}`))"),
        ):
            alias = f"{metric}__{safe}"
            aliases[alias] = (column, metric)
            expressions.append(f"{expression} AS `{alias}`")
    row = client.query(f"""
        SELECT {', '.join(expressions)}
        FROM `{old}` o JOIN `{new}` n USING ({using})
    """).to_dataframe().iloc[0]
    result = {column: {} for column in sorted(columns)}
    for alias, (column, metric) in aliases.items():
        value = row[alias]
        result[column][metric] = (
            None if pd.isna(value) else
            float(value) if metric == "max_abs_delta" else int(value)
        )
    return result


def run(output: Path) -> dict:
    from nfl_dfs.config import settings

    client = bigquery.Client(project=settings.project, location=settings.location)
    tables: dict[str, dict] = {}
    for name, keys in TABLE_KEYS.items():
        old = f"{settings.predictions}.{SNAPSHOT_PREFIX}{name}"
        new = f"{settings.features}.{name}"
        tables[name] = {
            "snapshot": old,
            "rebuilt": new,
            "before": _profile(client, old, keys),
            "after": _profile(client, new, keys),
            "key_delta": _key_delta(client, old, new, keys),
            "schema_before": _schema(client, old),
            "schema_after": _schema(client, new),
        }
    tables["player_week_usage"]["column_changes"] = _column_changes(
        client,
        tables["player_week_usage"]["snapshot"],
        tables["player_week_usage"]["rebuilt"],
        PLAYER_KEYS,
    )
    tables["player_week_training"]["column_changes"] = _column_changes(
        client,
        tables["player_week_training"]["snapshot"],
        tables["player_week_training"]["rebuilt"],
        PLAYER_KEYS,
    )
    tables["defense_week_allowed"]["column_changes"] = _column_changes(
        client,
        tables["defense_week_allowed"]["snapshot"],
        tables["defense_week_allowed"]["rebuilt"],
        TEAM_KEYS,
    )
    tables["defense_week_allowed"]["numeric_delta_profile"] = (
        _numeric_delta_profile(
            client,
            tables["defense_week_allowed"]["snapshot"],
            tables["defense_week_allowed"]["rebuilt"],
            TEAM_KEYS,
            FLOAT_REBUILD_NOISE_COLUMNS - {"xfp_l4"},
        )
    )
    tables["player_week_training"]["numeric_delta_profile"] = (
        _numeric_delta_profile(
            client,
            tables["player_week_training"]["snapshot"],
            tables["player_week_training"]["rebuilt"],
            PLAYER_KEYS,
            FLOAT_REBUILD_NOISE_COLUMNS,
        )
    )

    checks: dict[str, bool] = {}
    for name in ("player_week_usage", "player_week_training"):
        item = tables[name]
        checks[f"{name}_exact_keys"] = (
            item["key_delta"] == {"new_only": 0, "old_only": 0}
            and item["before"]["rows"] == item["after"]["rows"]
            and item["before"]["keys"] == item["after"]["keys"]
        )
        checks[f"{name}_schema_unchanged"] = (
            item["schema_before"] == item["schema_after"])

    usage_changes = tables["player_week_usage"]["column_changes"]
    checks["usage_only_registered_columns_change"] = all(
        count == 0 or column in USAGE_ALLOWED_CHANGES
        for column, count in usage_changes.items()
    )
    checks["both_usage_repairs_reach_rows"] = all(
        usage_changes.get(column, 0) > 0 for column in USAGE_ALLOWED_CHANGES)

    training_changes = tables["player_week_training"]["column_changes"]
    checks["training_only_registered_columns_change"] = all(
        count == 0 or column in (
            TRAINING_ALLOWED_CHANGES | FLOAT_REBUILD_NOISE_COLUMNS)
        for column, count in training_changes.items()
    )
    checks["training_smoothing_repair_reaches_rows"] = all(
        training_changes.get(column, 0) > 0 for column in USAGE_ALLOWED_CHANGES)
    checks["training_derived_repairs_reach_rows"] = all(
        training_changes.get(column, 0) > 0
        for column in (
            "xtd_receiving_proxy", "vacated_capture_tgt",
            "vacated_capture_car", "ref_flags_prior",
        )
    )

    defense = tables["defense_week_allowed"]
    defense_changes = defense["column_changes"]
    checks["defense_exact_keys_and_schema"] = (
        defense["key_delta"] == {"new_only": 0, "old_only": 0}
        and defense["before"]["rows"] == defense["after"]["rows"]
        and defense["before"]["keys"] == defense["after"]["keys"]
        and defense["schema_before"] == defense["schema_after"]
    )
    checks["defense_only_registered_columns_change"] = all(
        count == 0 or column in (
            DEFENSE_POSITION_REPAIR_COLUMNS | FLOAT_REBUILD_NOISE_COLUMNS)
        for column, count in defense_changes.items()
    )
    checks["defense_position_repair_reaches_rows"] = all(
        defense_changes.get(column, 0) > 0
        for column in DEFENSE_POSITION_REPAIR_COLUMNS
    )

    noise_profiles = [
        *defense["numeric_delta_profile"].values(),
        *tables["player_week_training"]["numeric_delta_profile"].values(),
    ]
    checks["floating_rebuild_noise_bounded"] = all(
        profile["null_mismatches"] == 0
        and profile["changes_gt_1e12"] == 0
        for profile in noise_profiles
    )

    injury = tables["player_week_injury"]
    checks["injury_exact_repaired_rows"] = (
        injury["after"] == {
            "rows": 57_550,
            "keys": 57_550,
            "checksum": injury["after"]["checksum"],
        }
        and injury["key_delta"]["new_only"] == 0
        and injury["key_delta"]["old_only"] == 8_312
    )
    checks["injury_provenance_columns_added"] = (
        {"injury_source_modified_at", "slate_lock_at"}
        == ({name for name, *_ in injury["schema_after"]}
            - {name for name, *_ in injury["schema_before"]})
    )
    checks["vacancy_unique"] = (
        tables["team_week_vacated"]["after"]["rows"]
        == tables["team_week_vacated"]["after"]["keys"])

    for name in UNCHANGED_TABLES:
        item = tables[name]
        checks[f"{name}_unchanged"] = (
            item["before"] == item["after"]
            and item["key_delta"] == {"new_only": 0, "old_only": 0}
            and item["schema_before"] == item["schema_after"]
        )

    checks = {name: bool(value) for name, value in checks.items()}
    report = {
        "disposition": (
            "pit-repair-warehouse-reconciled"
            if all(checks.values()) else "pit-repair-warehouse-invalid"
        ),
        "passes": all(checks.values()),
        "snapshot_prefix": SNAPSHOT_PREFIX,
        "checks": checks,
        "tables": tables,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.output)
    print(f"PIT_REPAIR_RECONCILIATION={json.dumps(report, sort_keys=True)}")
    if not report["passes"]:
        raise SystemExit("ABORT: PIT repair warehouse reconciliation failed")


if __name__ == "__main__":
    main()
