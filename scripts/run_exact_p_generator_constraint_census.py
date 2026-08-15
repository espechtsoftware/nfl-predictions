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
    validate_exact_p_census_plumbing,
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
REPAIR_PATH = Path(
    "reports/2026-08-15-exact-p-corrected-identity-source-repair.md"
)
REPAIR_SHA256 = "e1cb1cd1a131bd0884da499048b23de3295d2f42079a615f4d40b8af7b9b3bab"
IDENTITY_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-exact-p-corrected-identities-v1/result.json"
)
PREFLIGHT_OUTPUT_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-exact-p-generator-constraint-census-v1/preflight-2023.json"
)
FULL_OUTPUT_URI = (
    "gs://nfl-predictions-503414-raw/research/final-forensic-runs/"
    "20260814-final-preseason-forensic-v1/post-forensic-addenda/"
    "20260815-exact-p-generator-constraint-census-v1/result.json"
)


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


def _load_corrected_identities(
    client: storage.Client,
    *,
    uri: str,
    generation: int,
    sha256: str,
) -> tuple[pd.DataFrame, dict]:
    if uri != IDENTITY_URI or int(generation) <= 0 or re.fullmatch(
        r"[0-9a-f]{64}", sha256,
    ) is None:
        raise RuntimeError("corrected exact-P identity receipt is invalid")
    bucket_name, name = _parse_gcs(uri)
    payload = client.bucket(bucket_name).blob(
        name, generation=int(generation),
    ).download_as_bytes(if_generation_match=int(generation))
    if hashlib.sha256(payload).hexdigest() != sha256:
        raise RuntimeError("corrected exact-P identity bytes differ")
    source = json.loads(payload)
    if (
        source.get("version") != "exact-p-corrected-identities-v1"
        or source.get("mode") != "full"
        or source.get("manifest_sha256") != MANIFEST_SHA256
        or source.get("repair_protocol_sha256") != REPAIR_SHA256
        or source.get("slates") != 54
        or source.get("roster_slots") != 486
        or source.get("persisted_outcome_values") is not False
        or source.get("persisted_candidate_scores_or_membership") is not False
        or source.get("scientific_result_licensed") is not False
        or source.get("all_rosters_independently_legal") is not True
    ):
        raise RuntimeError("corrected exact-P identity contract differs")
    records = source.get("records", [])
    if len(records) != 54:
        raise RuntimeError("corrected exact-P identity population differs")
    rows = []
    for row in records:
        players = row.get("players", [])
        if len(players) != 9 or len(set(map(str, players))) != 9:
            raise RuntimeError("corrected exact-P roster is malformed")
        rows.append({
            "season": int(row["season"]),
            "week": int(row["week"]),
            "players": ",".join(sorted(map(str, players))),
        })
    frame = pd.DataFrame(rows)
    if frame[["season", "week"]].duplicated().any():
        raise RuntimeError("corrected exact-P slate keys repeat")
    return frame.sort_values(["season", "week"], kind="stable"), source


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


def run(
    output_uri: str,
    *,
    mode: str,
    identity_uri: str,
    identity_generation: int,
    identity_sha256: str,
) -> dict:
    expected_output = {
        "preflight-2023": PREFLIGHT_OUTPUT_URI,
        "full": FULL_OUTPUT_URI,
    }
    if mode not in expected_output or output_uri != expected_output[mode]:
        raise RuntimeError("generator census mode/output differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if re.fullmatch(r"[0-9a-f]{40}", code_sha) is None or re.search(
        r"@sha256:[0-9a-f]{64}$", image
    ) is None:
        raise RuntimeError("full CODE_SHA and immutable ANALYSIS_IMAGE are required")
    if (
        not PROTOCOL_PATH.is_file()
        or _sha256(PROTOCOL_PATH) != PROTOCOL_SHA256
        or not REPAIR_PATH.is_file()
        or _sha256(REPAIR_PATH) != REPAIR_SHA256
    ):
        raise RuntimeError("generator census protocol/repair is missing or changed")
    client = bigquery.Client(project=PROJECT)
    store = storage.Client(project=PROJECT)
    _verify_repair4_tables(client)
    prelock = _verify_prelock(client)
    exact_p, identity_source = _load_corrected_identities(
        store,
        uri=identity_uri,
        generation=identity_generation,
        sha256=identity_sha256,
    )
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
    if mode == "preflight-2023":
        result = validate_exact_p_census_plumbing(
            players[players.season.eq(2023)].copy(),
            native[native.season.eq(2023)].copy(),
            retained[retained.season.eq(2023)].copy(),
            exact_p[exact_p.season.eq(2023)].copy(),
            expected_slates=18,
        )
    else:
        result = analyze_exact_p_generator_census(
            players, native, retained, exact_p, expected_slates=54,
        )
    result.update({
        "mode": mode,
        "protocol_sha256": PROTOCOL_SHA256,
        "repair_protocol_sha256": REPAIR_SHA256,
        "manifest_sha256": MANIFEST_SHA256,
        "prelock_row_hash": PRELOCK_SHA256,
        "prelock_candidate_summary": prelock,
        "analysis_code_sha": code_sha,
        "analysis_image": image,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "corrected_identity_source": {
            "uri": identity_uri,
            "generation": int(identity_generation),
            "sha256": identity_sha256,
            "analysis_code_sha": identity_source.get("analysis_code_sha"),
            "analysis_image": identity_source.get("analysis_image"),
        },
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
            "exact_p": identity_uri,
        },
    })
    payload = json.dumps(
        result, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode("utf-8")
    result_sha256 = hashlib.sha256(payload).hexdigest()
    bucket, name = _parse_gcs(output_uri)
    store.bucket(bucket).blob(name).upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    summary = {
        "protocol_id": PROTOCOL_ID,
        "mode": mode,
        "output_uri": output_uri,
        "result_sha256": result_sha256,
        "slates": result["slates"],
        "scientific_result_licensed": bool(
            mode == "full" and result.get("historical_arm_licensed", False)
        ),
    }
    if mode == "full":
        summary.update({
            "disposition": result["disposition"],
            "loss_stage_counts": result["loss_stage_counts"],
            "family_primary_budget_share": result["family_primary_budget_share"],
            "family_statically_incapable_slates": (
                result["family_statically_incapable_slates"]
            ),
        })
    print("EXACT_P_GENERATOR_CENSUS " + json.dumps(
        summary, sort_keys=True, separators=(",", ":"),
    ))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("preflight-2023", "full"), required=True)
    parser.add_argument("--output-uri", required=True)
    parser.add_argument("--identity-uri", required=True)
    parser.add_argument("--identity-generation", type=int, required=True)
    parser.add_argument("--identity-sha256", required=True)
    args = parser.parse_args()
    run(
        args.output_uri,
        mode=args.mode,
        identity_uri=args.identity_uri,
        identity_generation=args.identity_generation,
        identity_sha256=args.identity_sha256,
    )


if __name__ == "__main__":
    main()
