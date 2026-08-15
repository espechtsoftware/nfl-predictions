#!/usr/bin/env python3
"""Run the frozen outcome-free ATLAS world-ranking diagnostic on R0--R4."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from typing import Any

import numpy as np
import pandas as pd
from google.cloud import bigquery, storage

from nfl_dfs.analysis.atlas_world_ranking import (
    aggregate_scorefree_gate,
    complete_world_ranking_diagnostic,
)
from nfl_dfs.optimizer.lineup import StackRules
from nfl_dfs.research.portfolio_effective_rank import decode_score_artifact


PROJECT = "nfl-predictions-503414"
SOURCE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = (
    f"{PROJECT}.nfl_forensic_review."
    "final_forensic_20260814_player_corpus_repair4"
)
FORENSIC_MANIFEST_SHA256 = (
    "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
)
SOURCE_PANEL_IDS = tuple(
    f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
)
SOURCE_SQL = f"""
SELECT panel_run_id, season, week,
       ANY_VALUE(source.score_artifact_uri) AS score_artifact_uri,
       ANY_VALUE(source.score_artifact_sha256) AS score_artifact_sha256,
       COUNT(*) AS candidate_rows
FROM `{SOURCE_TABLE}` AS source
WHERE panel_run_id IN UNNEST(@panel_ids)
  AND labels_complete
GROUP BY panel_run_id, season, week
HAVING COUNT(DISTINCT source.score_artifact_uri) = 1
   AND COUNT(DISTINCT source.score_artifact_sha256) = 1
ORDER BY panel_run_id, season, week
"""
PLAYER_SQL = f"""
SELECT manifest_sha256, season, week, player_id, player_name, position,
       team, opponent, game_id, salary, mean_projection
FROM `{PLAYER_TABLE}`
WHERE scope = 'phase-s-cbwu-54'
ORDER BY season, week, player_id
"""
FORBIDDEN_QUERY_TOKENS = (
    "actual_score", "actual_rank", "actual_ownership", "selected_rank",
    "payout", "contest_rank",
)


def validate_scorefree_queries() -> None:
    combined = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    present = [token for token in FORBIDDEN_QUERY_TOKENS if token in combined]
    if present:
        raise RuntimeError(
            "ATLAS score-free query contains forbidden fields: "
            + ", ".join(present)
        )


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("ATLAS GCS URI must name one object")
    bucket, marker, name = uri[5:].partition("/")
    if not marker or not bucket or not name or ".." in name.split("/"):
        raise ValueError("ATLAS GCS URI is invalid")
    return bucket, name


def _download_artifact(
    client: storage.Client, uri: str, digest: str,
) -> tuple[dict[str, np.ndarray], dict[str, str | int]]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    raw = blob.download_as_bytes()
    blob.reload()
    artifact = decode_score_artifact(raw, digest)
    if not {"player_ids", "player_draws"} <= set(artifact):
        raise ValueError("ATLAS source artifact lacks player worlds")
    return artifact, {
        "uri": uri,
        "sha256": digest,
        "generation": str(blob.generation),
        "updated": blob.updated.isoformat() if blob.updated else "",
        "bytes": len(raw),
    }


def _upload_create_only(
    client: storage.Client, uri: str, payload: bytes,
) -> dict[str, str | int | bool]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    blob.upload_from_string(
        payload, content_type="application/json", if_generation_match=0,
    )
    blob.reload()
    return {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": hashlib.sha256(payload).hexdigest(),
        "bytes": len(payload),
        "create_only": True,
    }


def _query(client: bigquery.Client, sql: str, params=None) -> pd.DataFrame:
    config = bigquery.QueryJobConfig(query_parameters=params or [])
    return client.query(sql, job_config=config, location="US").result().to_dataframe(
        create_bqstorage_client=False,
    )


def _player_rows(frame: pd.DataFrame, player_ids: np.ndarray) -> list[dict]:
    if frame.duplicated("player_id").any():
        raise RuntimeError("ATLAS player catalog contains duplicate IDs")
    catalog = frame.set_index(frame.player_id.astype(str), drop=False)
    ids = [str(value) for value in player_ids]
    if len(set(ids)) != len(ids):
        raise RuntimeError("ATLAS artifact contains duplicate player IDs")
    missing = set(ids) - set(catalog.index)
    if missing:
        raise RuntimeError(
            "ATLAS artifact players are missing from the player catalog"
        )
    rows = []
    for player_id in ids:
        source = catalog.loc[player_id]
        projection = pd.to_numeric(source.mean_projection, errors="coerce")
        rows.append({
            "id": player_id,
            "name": str(source.player_name),
            "pos": str(source.position).upper(),
            "team": str(source.team),
            "opp": str(source.opponent),
            "game_id": str(source.game_id),
            "salary": int(source.salary),
            "proj": float(projection) if np.isfinite(projection) else 0.0,
        })
    return rows


def run(output_uri: str) -> dict[str, Any]:
    validate_scorefree_queries()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image
    ):
        raise RuntimeError("ATLAS exact code SHA and immutable image are required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    sources = _query(
        bq,
        SOURCE_SQL,
        [bigquery.ArrayQueryParameter(
            "panel_ids", "STRING", list(SOURCE_PANEL_IDS)
        )],
    )
    players = _query(bq, PLAYER_SQL)
    if len(sources) != 270:
        raise RuntimeError(f"ATLAS expected 270 seed/slate sources, got {len(sources)}")
    if set(sources.panel_run_id.astype(str)) != set(SOURCE_PANEL_IDS):
        raise RuntimeError("ATLAS source panel identities differ")
    manifests = set(players.manifest_sha256.astype(str))
    if manifests != {FORENSIC_MANIFEST_SHA256}:
        raise RuntimeError("ATLAS pre-lock player corpus manifest differs")
    slates = sorted({
        (int(row.season), int(row.week)) for row in sources.itertuples()
    })
    if len(slates) != 54:
        raise RuntimeError(f"ATLAS expected 54 slates, got {len(slates)}")

    stack = StackRules(
        qb_stack_min=2,
        bring_back_min=1,
        forbid_rb_vs_dst=True,
        forbid_two_rb_same_team=True,
    )
    env = {
        "MIN_LINEUP_SALARY": "49000",
        "PUNT_MIN": "0",
        "VALUE2_MIN": "0",
        "OWN_BARBELL": "",
        "MAX_PER_GAME": "0",
    }
    diagnostics = []
    receipts = []
    for source in sources.itertuples(index=False):
        panel_id = str(source.panel_run_id)
        seed = SOURCE_PANEL_IDS.index(panel_id)
        season, week = int(source.season), int(source.week)
        artifact, receipt = _download_artifact(
            gcs,
            str(source.score_artifact_uri),
            str(source.score_artifact_sha256),
        )
        player_frame = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ].copy()
        player_ids = np.asarray(artifact["player_ids"]).astype(str)
        player_rows = _player_rows(player_frame, player_ids)
        draws = np.asarray(artifact["player_draws"], dtype=np.float32)
        if draws.shape != (len(player_rows), 10_000):
            raise RuntimeError("ATLAS source player-world shape differs")
        diagnostic = complete_world_ranking_diagnostic(
            player_rows,
            draws,
            stack=stack,
            env=env,
            n_worlds=40,
        )
        diagnostics.append({
            "seed": seed,
            "panel_run_id": panel_id,
            "season": season,
            "week": week,
            **diagnostic,
        })
        receipts.append({
            "seed": seed,
            "panel_run_id": panel_id,
            "season": season,
            "week": week,
            "candidate_rows": int(source.candidate_rows),
            **receipt,
        })

    gate = aggregate_scorefree_gate(diagnostics)
    report = {
        "version": "atlas-world-ranking-scorefree-v1",
        "uses_realized_outcomes": False,
        "code_sha": code_sha,
        "image": image,
        "source_table": SOURCE_TABLE,
        "player_table": PLAYER_TABLE,
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_artifacts": receipts,
        "production_constraints": {
            "salary_floor": 49_000,
            "salary_cap": 50_000,
            "qb_stack_min": 2,
            "bring_back_min": 1,
            "forbid_rb_vs_dst": True,
            "forbid_two_rb_same_team": True,
        },
        "gate": gate,
        "diagnostics": diagnostics,
        "consequence": (
            "score-free premise only; cannot promote, reject, or score a "
            "money lineup and cannot tune ATLAS parameters"
        ),
    }
    payload = (json.dumps(
        report, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ) + "\n").encode()
    report["output"] = _upload_create_only(gcs, output_uri, payload)
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    result = run(args.output_uri)
    print(json.dumps({
        "version": result["version"],
        "gate": result["gate"],
        "output": result["output"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
