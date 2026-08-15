#!/usr/bin/env python3
"""Run the frozen score-free exact-P generator constraint census."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re

import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.research.exact_p_generator_census import (
    PROTOCOL_ID,
    SCOPE,
    SEED_ORDER,
    analyze_exact_p_generator_census,
)


PROJECT = "nfl-predictions-503414"
FORENSIC_DATASET = "nfl_forensic_review"
PREDICTIONS_DATASET = "nfl_predictions"
TABLE_PREFIX = "final_forensic_20260814_"
MANIFEST_SHA256 = "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
PRELOCK_SHA256 = "869a648ade3919b8942d8489795b208484c448ca73873cfcacede84effb13e7e"
PROTOCOL_PATH = Path(
    "reports/2026-08-15-exact-p-generator-constraint-census-protocol.md"
)
PROTOCOL_SHA256 = "bca1db394240359edd80db4767cafbe8d39d1a6769ba6a60e2b35ded18c0056e"


def _query(
    client: bigquery.Client,
    sql: str,
    *,
    params: list[bigquery.ArrayQueryParameter] | None = None,
) -> pd.DataFrame:
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(query_parameters=params or []),
        location="US",
    )
    return job.result().to_dataframe(create_bqstorage_client=False)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("output URI must name one GCS object")
    bucket, _, name = uri[5:].partition("/")
    if not bucket or not name or ".." in name.split("/"):
        raise ValueError("output URI is invalid")
    return bucket, name


def _verify_repair4_tables(client: bigquery.Client) -> None:
    for suffix in (
        "player_corpus_repair4", "candidate_corpus_repair4",
        "oracle_rosters_repair4",
    ):
        table = client.get_table(
            f"{PROJECT}.{FORENSIC_DATASET}.{TABLE_PREFIX}{suffix}"
        )
        if table.labels.get("manifest") != MANIFEST_SHA256[:32]:
            raise RuntimeError(f"repair4 manifest label differs for {suffix}")


def _verify_prelock(client: bigquery.Client) -> dict:
    path = Path(
        "reports/final-forensic-runs/20260814-final-preseason-forensic-v1/"
        "prelock_panels.json"
    )
    frozen = json.loads(path.read_text(encoding="utf-8"))
    rows = [row for row in frozen if row.get("id") == SCOPE]
    if len(rows) != 1 or rows[0].get("prelock_row_hash") != PRELOCK_SHA256:
        raise RuntimeError("generator census frozen prelock identity differs")
    expected = rows[0]["prelock_candidate_summary"]
    observed = _query(client, f"""
        WITH hashed AS (
          SELECT season, week,
                 FARM_FINGERPRINT(TO_JSON_STRING(
                   (SELECT AS STRUCT t.* EXCEPT(actual_score, actual_rank))
                 )) AS row_fp
          FROM `{PROJECT}.{PREDICTIONS_DATASET}.replay_candidates_staging` t
          WHERE panel_run_id IN UNNEST(@panel_ids)
        )
        SELECT COUNT(*) AS row_count,
               COUNT(DISTINCT FORMAT('%d-%d', season, week)) AS slate_count,
               ARRAY_AGG(DISTINCT season ORDER BY season) AS seasons,
               BIT_XOR(row_fp) AS row_xor,
               CAST(SUM(CAST(row_fp AS BIGNUMERIC)) AS STRING) AS row_sum,
               MIN(row_fp) AS row_min,
               MAX(row_fp) AS row_max
        FROM hashed
    """, params=[bigquery.ArrayQueryParameter(
        "panel_ids", "STRING", list(SEED_ORDER),
    )]).iloc[0]
    actual = {
        "row_count": int(observed.row_count),
        "slate_count": int(observed.slate_count),
        "seasons": list(map(int, observed.seasons)),
        "row_xor": int(observed.row_xor),
        "row_sum": str(observed.row_sum),
        "row_min": int(observed.row_min),
        "row_max": int(observed.row_max),
    }
    if actual != expected:
        raise RuntimeError("generator census native prelock rows drifted")
    completeness = _query(client, f"""
        SELECT COUNT(*) AS row_count,
               LOGICAL_AND(labels_complete) AS labels_complete
        FROM `{PROJECT}.{PREDICTIONS_DATASET}.replay_candidates_staging`
        WHERE panel_run_id IN UNNEST(@panel_ids)
    """, params=[bigquery.ArrayQueryParameter(
        "panel_ids", "STRING", list(SEED_ORDER),
    )]).iloc[0]
    if int(completeness.row_count) != int(expected["row_count"]) or not bool(
        completeness.labels_complete
    ):
        raise RuntimeError("generator census native label completeness differs")
    return actual


def run(output_uri: str) -> dict:
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.search(
        r"@sha256:[0-9a-f]{64}$", image
    ) is None:
        raise RuntimeError("full CODE_SHA and immutable ANALYSIS_IMAGE are required")
    if not PROTOCOL_PATH.is_file() or _sha256(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("generator census protocol is missing or changed")
    client = bigquery.Client(project=PROJECT)
    _verify_repair4_tables(client)
    prelock = _verify_prelock(client)
    params = [bigquery.ArrayQueryParameter(
        "panel_ids", "STRING", list(SEED_ORDER),
    )]
    players = _query(client, f"""
        SELECT season, week, player_id AS id, position AS pos, team,
               opponent AS opp, game_id, salary
        FROM `{PROJECT}.{FORENSIC_DATASET}.{TABLE_PREFIX}player_corpus_repair4`
        WHERE scope = '{SCOPE}'
        ORDER BY season, week, player_id
    """)
    native = _query(client, f"""
        SELECT panel_run_id, season, week, cand_ix, players, tag, all_tags
        FROM `{PROJECT}.{PREDICTIONS_DATASET}.replay_candidates_staging`
        WHERE panel_run_id IN UNNEST(@panel_ids)
        ORDER BY panel_run_id, season, week, cand_ix
    """, params=params)
    retained = _query(client, f"""
        SELECT season, week, candidate_index, roster_ordered AS players, tag
        FROM `{PROJECT}.{FORENSIC_DATASET}.{TABLE_PREFIX}candidate_corpus_repair4`
        WHERE scope = '{SCOPE}'
        ORDER BY season, week, candidate_index
    """)
    exact_p = _query(client, f"""
        SELECT season, week, roster_key AS players
        FROM `{PROJECT}.{FORENSIC_DATASET}.{TABLE_PREFIX}oracle_rosters_repair4`
        WHERE scope = '{SCOPE}' AND layer = 'P'
        ORDER BY season, week
    """)
    result = analyze_exact_p_generator_census(
        players, native, retained, exact_p, expected_slates=54,
    )
    result.update({
        "protocol_sha256": PROTOCOL_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "prelock_row_hash": PRELOCK_SHA256,
        "prelock_candidate_summary": prelock,
        "analysis_code_sha": code_sha,
        "analysis_image": image,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tables": {
            "players": (
                f"{PROJECT}.{FORENSIC_DATASET}.{TABLE_PREFIX}"
                "player_corpus_repair4"
            ),
            "native_candidates": (
                f"{PROJECT}.{PREDICTIONS_DATASET}.replay_candidates_staging"
            ),
            "retained_candidates": (
                f"{PROJECT}.{FORENSIC_DATASET}.{TABLE_PREFIX}"
                "candidate_corpus_repair4"
            ),
            "exact_p": (
                f"{PROJECT}.{FORENSIC_DATASET}.{TABLE_PREFIX}"
                "oracle_rosters_repair4"
            ),
        },
    })
    payload = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    result_sha256 = hashlib.sha256(payload).hexdigest()
    bucket, name = _parse_gcs(output_uri)
    storage.Client(project=PROJECT).bucket(bucket).blob(name).upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    summary = {
        "protocol_id": PROTOCOL_ID,
        "output_uri": output_uri,
        "result_sha256": result_sha256,
        "disposition": result["disposition"],
        "slates": result["slates"],
        "loss_stage_counts": result["loss_stage_counts"],
        "family_primary_budget_share": result["family_primary_budget_share"],
        "family_statically_incapable_slates": (
            result["family_statically_incapable_slates"]
        ),
    }
    print("EXACT_P_GENERATOR_CENSUS " + json.dumps(
        summary, sort_keys=True, separators=(",", ":"),
    ))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.output_uri)


if __name__ == "__main__":
    main()
