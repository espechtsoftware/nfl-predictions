#!/usr/bin/env python3
"""Run the repair4 exact-stack construction addendum create-only in GCS."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re

import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.research.post_forensic_construction import (
    PROTOCOL_ID,
    SCOPE,
    analyze_exact_stack_construction,
)


PROJECT = "nfl-predictions-503414"
DATASET = "nfl_forensic_review"
MANIFEST_SHA256 = "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
TABLE_PREFIX = "final_forensic_20260814_"


def _query(client: bigquery.Client, sql: str) -> pd.DataFrame:
    return client.query(sql, location="US").result().to_dataframe(
        create_bqstorage_client=False
    )


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("output URI must name one GCS object")
    bucket, _, name = uri[5:].partition("/")
    if not bucket or not name or ".." in name.split("/"):
        raise ValueError("output URI is invalid")
    return bucket, name


def _verify_tables(client: bigquery.Client) -> None:
    for suffix in ("player_corpus_repair4", "candidate_corpus_repair4",
                   "oracle_rosters_repair4"):
        table = client.get_table(f"{PROJECT}.{DATASET}.{TABLE_PREFIX}{suffix}")
        if table.labels.get("manifest") != MANIFEST_SHA256[:32]:
            raise RuntimeError(f"repair4 manifest label differs for {suffix}")


def run(output_uri: str) -> dict:
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.search(
        r"@sha256:[0-9a-f]{64}$", image
    ) is None:
        raise RuntimeError("full CODE_SHA and immutable ANALYSIS_IMAGE are required")
    client = bigquery.Client(project=PROJECT)
    _verify_tables(client)
    players = _query(client, f"""
        SELECT season, week, player_id AS id, position AS pos, team,
               opponent AS opp, game_id, salary, actual_score AS actual,
               actual_ownership
        FROM `{PROJECT}.{DATASET}.{TABLE_PREFIX}player_corpus_repair4`
        WHERE scope = '{SCOPE}'
        ORDER BY season, week, player_id
    """)
    candidates = _query(client, f"""
        SELECT season, week, candidate_index, roster_ordered AS players,
               actual_score, selected, selected_rank, tag, all_tags
        FROM `{PROJECT}.{DATASET}.{TABLE_PREFIX}candidate_corpus_repair4`
        WHERE scope = '{SCOPE}'
        ORDER BY season, week, candidate_index
    """)
    oracles = _query(client, f"""
        SELECT season, week, layer, roster_key AS players, actual_score
        FROM `{PROJECT}.{DATASET}.{TABLE_PREFIX}oracle_rosters_repair4`
        WHERE scope = '{SCOPE}'
        ORDER BY season, week, layer
    """)
    result = analyze_exact_stack_construction(
        players, candidates, oracles, expected_slates=54,
    )
    result.update({
        "manifest_sha256": MANIFEST_SHA256,
        "analysis_code_sha": code_sha,
        "analysis_image": image,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tables": [
            f"{PROJECT}.{DATASET}.{TABLE_PREFIX}{suffix}"
            for suffix in (
                "player_corpus_repair4", "candidate_corpus_repair4",
                "oracle_rosters_repair4",
            )
        ],
    })
    payload = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    result_sha256 = hashlib.sha256(payload).hexdigest()
    bucket_name, object_name = _parse_gcs(output_uri)
    storage.Client(project=PROJECT).bucket(bucket_name).blob(
        object_name
    ).upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    summary = {
        "protocol_id": PROTOCOL_ID,
        "output_uri": output_uri,
        "result_sha256": result_sha256,
        "slates": result["slates"],
        "published_scope_defect": result["published_scope_defect"],
        "corrected_gap_points": result["corrected_gap_points"],
        "tail_counts": result["tail_counts"],
        "swap_distance": result["swap_distance"],
    }
    print("POST_FORENSIC_CONSTRUCTION_ADDENDUM " + json.dumps(
        summary, sort_keys=True, separators=(",", ":")
    ))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.output_uri)


if __name__ == "__main__":
    main()
