#!/usr/bin/env python3
"""Materialize the frozen corrected exact-P identity source."""

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

from nfl_dfs.research.exact_p_identity_source import (
    derive_corrected_p_identities,
    preflight_receipt,
)


PROJECT = "nfl-predictions-503414"
DATASET = "nfl_forensic_review"
TABLE_PREFIX = "final_forensic_20260814_"
SCOPE = "phase-s-cbwu-54"
MANIFEST_SHA256 = "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
PARENT_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-exact-stack-construction-v1/result.json"
)
PARENT_GENERATION = 1786794534795445
PARENT_SHA256 = "1d9e6b1f8d4e6174ae4aa717acf62fe657f0f3fbfd9271289a36b4a58664e7f3"
PROTOCOL_PATH = Path(
    "reports/2026-08-15-exact-p-corrected-identity-source-repair.md"
)
PROTOCOL_SHA256 = "e1cb1cd1a131bd0884da499048b23de3295d2f42079a615f4d40b8af7b9b3bab"
OUTPUTS = {
    "preflight-2023": (
        "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
        "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
        "20260815-exact-p-corrected-identities-v1/preflight-2023.json"
    ),
    "full": (
        "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
        "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
        "20260815-exact-p-corrected-identities-v1/result.json"
    ),
}


def _query(client: bigquery.Client, sql: str) -> pd.DataFrame:
    return client.query(sql, location="US").result().to_dataframe(
        create_bqstorage_client=False,
    )


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("GCS URI must name one object")
    bucket, _, name = uri[5:].partition("/")
    if not bucket or not name or ".." in name.split("/"):
        raise ValueError("GCS URI is invalid")
    return bucket, name


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_parent(client: storage.Client) -> dict:
    bucket_name, name = _parse_gcs(PARENT_URI)
    blob = client.bucket(bucket_name).blob(name, generation=PARENT_GENERATION)
    payload = blob.download_as_bytes(if_generation_match=PARENT_GENERATION)
    if hashlib.sha256(payload).hexdigest() != PARENT_SHA256:
        raise RuntimeError("exact-stack parent bytes differ")
    source = json.loads(payload)
    if (
        source.get("manifest_sha256") != MANIFEST_SHA256
        or source.get("scope") != SCOPE
        or source.get("slates") != 54
    ):
        raise RuntimeError("exact-stack parent identity differs")
    return source


def _verify_tables(client: bigquery.Client) -> None:
    for suffix in (
        "player_corpus_repair4", "candidate_corpus_repair4",
        "oracle_rosters_repair4",
    ):
        table = client.get_table(f"{PROJECT}.{DATASET}.{TABLE_PREFIX}{suffix}")
        if table.labels.get("manifest") != MANIFEST_SHA256[:32]:
            raise RuntimeError(f"repair4 manifest label differs for {suffix}")


def run(mode: str, output_uri: str) -> dict:
    if mode not in OUTPUTS or output_uri != OUTPUTS[mode]:
        raise RuntimeError("corrected identity mode/output differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.search(
        r"@sha256:[0-9a-f]{64}$", image,
    ) is None:
        raise RuntimeError("full CODE_SHA and immutable ANALYSIS_IMAGE are required")
    if not PROTOCOL_PATH.is_file() or _sha256(PROTOCOL_PATH) != PROTOCOL_SHA256:
        raise RuntimeError("corrected identity repair protocol differs")

    bq = bigquery.Client(project=PROJECT)
    store = storage.Client(project=PROJECT)
    _verify_tables(bq)
    source = _load_parent(store)
    players = _query(bq, f"""
        SELECT season, week, player_id AS id, position AS pos, team,
               opponent AS opp, game_id, salary, actual_score AS actual
        FROM `{PROJECT}.{DATASET}.{TABLE_PREFIX}player_corpus_repair4`
        WHERE scope = '{SCOPE}'
        ORDER BY season, week, player_id
    """)
    candidates = _query(bq, f"""
        SELECT season, week, roster_ordered AS players
        FROM `{PROJECT}.{DATASET}.{TABLE_PREFIX}candidate_corpus_repair4`
        WHERE scope = '{SCOPE}'
        ORDER BY season, week, candidate_index
    """)
    if mode == "preflight-2023":
        players = players[players.season.eq(2023)].copy()
        candidates = candidates[candidates.season.eq(2023)].copy()
        source = dict(source)
        source["records"] = [
            row for row in source["records"] if int(row["season"]) == 2023
        ]
        source["tail_counts"] = dict(source["tail_counts"])
        source["tail_counts"]["exact_p"] = {
            str(tail): int(sum(
                float(row["exact_p"]) >= int(tail)
                for row in source["records"]
            ))
            for tail in source["tail_counts"]["exact_p"]
        }
        result = preflight_receipt(derive_corrected_p_identities(
            players, candidates, source, expected_slates=18,
        ))
    else:
        result = derive_corrected_p_identities(
            players, candidates, source, expected_slates=54,
        )
    result.update({
        "mode": mode,
        "repair_protocol_sha256": PROTOCOL_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "exact_stack_parent_uri": PARENT_URI,
        "exact_stack_parent_generation": PARENT_GENERATION,
        "exact_stack_parent_sha256": PARENT_SHA256,
        "analysis_code_sha": code_sha,
        "analysis_image": image,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_tables": [
            f"{PROJECT}.{DATASET}.{TABLE_PREFIX}player_corpus_repair4",
            f"{PROJECT}.{DATASET}.{TABLE_PREFIX}candidate_corpus_repair4",
            f"{PROJECT}.{DATASET}.{TABLE_PREFIX}oracle_rosters_repair4",
        ],
    })
    payload = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    bucket, name = _parse_gcs(output_uri)
    store.bucket(bucket).blob(name).upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    summary = {
        "mode": mode,
        "output_uri": output_uri,
        "result_sha256": hashlib.sha256(payload).hexdigest(),
        "slates": result["slates"],
        "roster_slots": result["roster_slots"],
        "scientific_result_licensed": False,
    }
    print("EXACT_P_CORRECTED_IDENTITIES " + json.dumps(
        summary, sort_keys=True, separators=(",", ":"),
    ))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=tuple(OUTPUTS), required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.mode, args.output_uri)


if __name__ == "__main__":
    main()
