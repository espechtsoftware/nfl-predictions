#!/usr/bin/env python3
"""Capture outcome-free row identities for the final forensic freeze.

Only candidate fields other than ``actual_score``/``actual_rank`` and player
feature fields other than ``actual`` are hashed.  This script deliberately has
no outcome mode.  Its JSON output is a reviewed input to the separate manifest
builder; it does not launch the forensic analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from google.cloud import bigquery


PROJECT = "nfl-predictions-503414"
DATASET = "nfl_predictions"
OUTPUT = (
    "reports/final-forensic-runs/20260814-final-preseason-forensic-v1/"
    "prelock_panels.json"
)
SCOPES = (
    {
        "id": "component-107",
        "candidate_table": "replay_candidates",
        "panel_ids": ["20260811-pitclean-e80-k1-role12union-a12ab31"],
        "research_only": True,
        "estimand": "107-slate component/candidate/selector evidence",
        "scope_boundary": (
            "2019 and 2021-2025 component policy; not position/ASOE/CBWU v4"
        ),
    },
    {
        "id": "position-54",
        "candidate_table": "replay_candidates",
        "panel_ids": ["20260812-pitclean-e80-selected-position-scales-v2"],
        "research_only": True,
        "estimand": "54-slate position-calibrated finite-K evidence",
        "scope_boundary": "2023-2025 only; not a 107-slate CBWU v4 book",
    },
    {
        "id": "phase-s-cbwu-54",
        "candidate_table": "replay_candidates_staging",
        "panel_ids": [
            f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
        ],
        "research_only": False,
        "estimand": "54-slate five-search/five-world CBWU reconstruction evidence",
        "scope_boundary": (
            "2023-2025 Phase S treatment R0-R4 plus frozen fixed-budget CBWU "
            "analyzer; no persisted standalone CBWU panel and no 107-slate claim"
        ),
    },
)


def _summary_query(
    *, table: str, panel_ids: list[str], excluded: tuple[str, ...],
    research_only: bool,
) -> tuple[str, list[bigquery.ScalarQueryParameter]]:
    allowed = {
        "replay_candidates", "replay_candidates_staging", "slate_player_features"
    }
    if table not in allowed:
        raise ValueError(f"unapproved table {table}")
    exclusions = ", ".join(excluded)
    research = "AND research_eligible" if research_only else ""
    sql = f"""
    WITH hashed AS (
      SELECT
        season,
        week,
        FARM_FINGERPRINT(
          TO_JSON_STRING((SELECT AS STRUCT t.* EXCEPT({exclusions})))
        ) AS row_fp
      FROM `{PROJECT}.{DATASET}.{table}` AS t
      WHERE panel_run_id IN UNNEST(@panel_ids)
        {research}
    )
    SELECT
      COUNT(*) AS row_count,
      COUNT(DISTINCT FORMAT('%d-%d', season, week)) AS slate_count,
      ARRAY_AGG(DISTINCT season ORDER BY season) AS seasons,
      BIT_XOR(row_fp) AS row_xor,
      CAST(SUM(CAST(row_fp AS BIGNUMERIC)) AS STRING) AS row_sum,
      MIN(row_fp) AS row_min,
      MAX(row_fp) AS row_max
    FROM hashed
    """
    params = [bigquery.ArrayQueryParameter("panel_ids", "STRING", panel_ids)]
    return sql, params


def _capture(
    client: bigquery.Client, *, table: str, panel_ids: list[str],
    excluded: tuple[str, ...], research_only: bool,
) -> dict[str, Any]:
    sql, params = _summary_query(
        table=table,
        panel_ids=panel_ids,
        excluded=excluded,
        research_only=research_only,
    )
    rows = list(client.query(
        sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params),
        location="US",
    ).result())
    if len(rows) != 1 or not rows[0].row_count:
        raise RuntimeError(f"empty or non-scalar prelock summary for {table}")
    row = dict(rows[0].items())
    row["seasons"] = list(row["seasons"])
    for key in ("row_count", "slate_count", "row_xor", "row_min", "row_max"):
        row[key] = int(row[key])
    return row


def capture(client: bigquery.Client) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for scope in SCOPES:
        candidates = _capture(
            client,
            table=scope["candidate_table"],
            panel_ids=scope["panel_ids"],
            excluded=("actual_score", "actual_rank"),
            research_only=scope["research_only"],
        )
        features = _capture(
            client,
            table="slate_player_features",
            panel_ids=scope["panel_ids"],
            excluded=("actual",),
            research_only=scope["research_only"],
        )
        if candidates["slate_count"] != features["slate_count"]:
            raise RuntimeError(f"candidate/feature slate mismatch for {scope['id']}")
        if candidates["seasons"] != features["seasons"]:
            raise RuntimeError(f"candidate/feature season mismatch for {scope['id']}")
        hash_payload = json.dumps(
            {"candidates": candidates, "features": features},
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        records.append({
            "id": scope["id"],
            "table": (
                f"{PROJECT}.{DATASET}.{scope['candidate_table']} + "
                f"{PROJECT}.{DATASET}.slate_player_features"
            ),
            "panel_ids": scope["panel_ids"],
            "expected_rows": candidates["row_count"],
            "expected_player_rows": features["row_count"],
            "expected_slates": candidates["slate_count"],
            "seasons": candidates["seasons"],
            "prelock_row_hash": hashlib.sha256(hash_payload).hexdigest(),
            "prelock_candidate_summary": candidates,
            "prelock_feature_summary": features,
            "outcome_columns_excluded": [
                "replay_candidates.actual_score",
                "replay_candidates.actual_rank",
                "slate_player_features.actual",
            ],
            "estimand": scope["estimand"],
            "scope_boundary": scope["scope_boundary"],
        })
    return records


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", default=PROJECT)
    parser.add_argument("--output", default=OUTPUT)
    args = parser.parse_args()
    if args.project != PROJECT:
        raise SystemExit(f"project must remain frozen as {PROJECT}")
    records = capture(bigquery.Client(project=PROJECT, location="US"))
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n")
    print(json.dumps({
        "output": str(output),
        "panels": [
            {
                "id": row["id"],
                "rows": row["expected_rows"],
                "player_rows": row["expected_player_rows"],
                "slates": row["expected_slates"],
                "prelock_row_hash": row["prelock_row_hash"],
            }
            for row in records
        ],
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
