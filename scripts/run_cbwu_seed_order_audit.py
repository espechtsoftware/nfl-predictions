#!/usr/bin/env python3
"""Run the frozen outcome-free CBWU cyclic seed-order audit."""

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

from nfl_dfs.backtest.engine import CandidateBatch
from nfl_dfs.inference.multiseed_portfolio import audit_cbwu_seed_orders
from nfl_dfs.optimizer.lineup import Lineup
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
SELECT panel_run_id, season, week, cand_ix, tag, all_tags, players,
       score_artifact_uri, score_artifact_sha256
FROM `{SOURCE_TABLE}`
WHERE panel_run_id IN UNNEST(@panel_ids)
  AND labels_complete
ORDER BY panel_run_id, season, week, cand_ix
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
    "selected", "payout", "contest_rank",
)


def validate_scorefree_queries() -> None:
    combined = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    present = [token for token in FORBIDDEN_QUERY_TOKENS if token in combined]
    if present:
        raise RuntimeError(
            "CBWU score-free query contains forbidden fields: "
            + ", ".join(present)
        )


def _parse_gcs(uri: str) -> tuple[str, str]:
    if not uri.startswith("gs://") or uri.endswith("/"):
        raise ValueError("CBWU GCS URI must name one object")
    bucket, marker, name = uri[5:].partition("/")
    if not marker or not bucket or not name or ".." in name.split("/"):
        raise ValueError("CBWU GCS URI is invalid")
    return bucket, name


def _download_artifact(
    client: storage.Client, uri: str, digest: str,
) -> tuple[dict[str, np.ndarray], dict[str, str | int]]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    raw = blob.download_as_bytes()
    blob.reload()
    artifact = decode_score_artifact(raw, digest)
    required = {"cand_ix", "totals", "player_ids", "player_draws"}
    if not required <= set(artifact):
        raise ValueError("CBWU source artifact lacks candidate/player worlds")
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


def _player_rows(frame: pd.DataFrame, player_ids: np.ndarray) -> tuple[dict, ...]:
    if frame.duplicated("player_id").any():
        raise RuntimeError("CBWU player catalog contains duplicate IDs")
    catalog = frame.set_index(frame.player_id.astype(str), drop=False)
    ids = [str(value) for value in player_ids]
    if len(set(ids)) != len(ids):
        raise RuntimeError("CBWU artifact contains duplicate player IDs")
    if set(ids) - set(catalog.index):
        raise RuntimeError("CBWU artifact players are missing from the catalog")
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
    return tuple(rows)


def _candidate_batch(
    frame: pd.DataFrame,
    artifact: dict[str, np.ndarray],
    catalog: pd.DataFrame,
) -> CandidateBatch:
    rows = frame.sort_values("cand_ix", kind="stable").reset_index(drop=True)
    indices = pd.to_numeric(rows.cand_ix, errors="raise").astype(int).tolist()
    if indices != list(range(len(rows))):
        raise RuntimeError("CBWU candidate indices are not canonical")
    artifact_indices = np.asarray(artifact["cand_ix"]).astype(int).tolist()
    if artifact_indices != indices:
        raise RuntimeError("CBWU artifact candidate indices differ")
    player_ids = tuple(np.asarray(artifact["player_ids"]).astype(str).tolist())
    player_rows = _player_rows(catalog, np.asarray(player_ids))
    by_id = {row["id"]: row for row in player_rows}
    candidates = []
    all_tags = {}
    for source in rows.itertuples(index=False):
        roster_ids = [value for value in str(source.players).split(",") if value]
        if len(roster_ids) != 9 or len(set(roster_ids)) != 9:
            raise RuntimeError("CBWU candidate roster is malformed")
        try:
            lineup = Lineup([by_id[player_id] for player_id in roster_ids], tag=str(source.tag))
        except KeyError as exc:
            raise RuntimeError("CBWU candidate is outside artifact universe") from exc
        try:
            tags = json.loads(str(source.all_tags))
        except json.JSONDecodeError as exc:
            raise RuntimeError("CBWU candidate tags are not JSON") from exc
        if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
            raise RuntimeError("CBWU candidate tags are malformed")
        candidates.append(lineup)
        all_tags[lineup.ids] = tuple(tags)
    totals = np.asarray(artifact["totals"], dtype=np.float32)
    draws = np.asarray(artifact["player_draws"], dtype=np.float32)
    if totals.shape != (len(candidates), 10_000):
        raise RuntimeError("CBWU candidate-world shape differs")
    if draws.shape != (len(player_rows), 10_000):
        raise RuntimeError("CBWU player-world shape differs")
    return CandidateBatch(
        candidates=tuple(candidates),
        candidate_totals=totals,
        player_ids=player_ids,
        player_rows=player_rows,
        row_draws=draws,
        all_tags=all_tags,
    )


def _aggregate_audits(audits: list[dict]) -> dict[str, Any]:
    if len(audits) != 54:
        raise ValueError("CBWU aggregate requires exactly 54 slates")
    comparisons = []
    for audit in audits:
        if audit.get("uses_realized_outcomes") is not False:
            raise ValueError("CBWU audit contains outcome-facing data")
        rotations = audit.get("rotations", [])
        if len(rotations) != 5:
            raise ValueError("CBWU audit lacks five cyclic rotations")
        canonical_coverage = float(rotations[0]["selected_world_coverage"])
        for rotation_index, row in enumerate(rotations[1:], start=1):
            comparisons.append({
                "season": int(audit["season"]),
                "week": int(audit["week"]),
                "rotation_index": rotation_index,
                "candidate_jaccard": float(
                    row["candidate_identity_jaccard_vs_canonical"]
                ),
                "selected_jaccard": float(
                    row["selected_identity_jaccard_vs_canonical"]
                ),
                "world_coverage_delta": float(
                    row["selected_world_coverage"] - canonical_coverage
                ),
            })
    candidate = np.asarray([row["candidate_jaccard"] for row in comparisons])
    selected = np.asarray([row["selected_jaccard"] for row in comparisons])
    coverage = np.asarray([row["world_coverage_delta"] for row in comparisons])
    invariant = bool(np.all(candidate == 1.0) and np.all(selected == 1.0))
    return {
        "slates": 54,
        "cyclic_comparisons": len(comparisons),
        "candidate_jaccard": {
            "minimum": float(candidate.min()),
            "mean": float(candidate.mean()),
        },
        "selected_jaccard": {
            "minimum": float(selected.min()),
            "mean": float(selected.mean()),
        },
        "selected_world_coverage_delta": {
            "minimum": float(coverage.min()),
            "mean": float(coverage.mean()),
            "maximum": float(coverage.max()),
        },
        "candidate_changed_comparisons": int(np.sum(candidate < 1.0)),
        "selected_changed_comparisons": int(np.sum(selected < 1.0)),
        "order_invariant": invariant,
        "disposition": (
            "cbwu-order-invariant"
            if invariant else "cbwu-order-sensitive-requires-repair"
        ),
    }


def run(output_uri: str) -> dict[str, Any]:
    validate_scorefree_queries()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image
    ):
        raise RuntimeError("CBWU exact code SHA and immutable image are required")

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
    if set(sources.panel_run_id.astype(str)) != set(SOURCE_PANEL_IDS):
        raise RuntimeError("CBWU source panel identities differ")
    if set(players.manifest_sha256.astype(str)) != {FORENSIC_MANIFEST_SHA256}:
        raise RuntimeError("CBWU pre-lock player corpus manifest differs")
    group_keys = sources[["panel_run_id", "season", "week"]].drop_duplicates()
    if len(group_keys) != 270:
        raise RuntimeError(f"CBWU expected 270 seed/slate sources, got {len(group_keys)}")
    slates = sorted({
        (int(row.season), int(row.week)) for row in group_keys.itertuples()
    })
    if len(slates) != 54:
        raise RuntimeError(f"CBWU expected 54 slates, got {len(slates)}")

    audits = []
    receipts = []
    for season, week in slates:
        slate_catalog = players[
            players.season.astype(int).eq(season)
            & players.week.astype(int).eq(week)
        ].copy()
        books = {}
        for seed, panel_id in enumerate(SOURCE_PANEL_IDS):
            group = sources[
                sources.panel_run_id.astype(str).eq(panel_id)
                & sources.season.astype(int).eq(season)
                & sources.week.astype(int).eq(week)
            ].copy()
            if group.empty:
                raise RuntimeError(f"CBWU source is missing {panel_id} {season}w{week}")
            uris = group.score_artifact_uri.astype(str).unique()
            digests = group.score_artifact_sha256.astype(str).unique()
            if len(uris) != 1 or len(digests) != 1:
                raise RuntimeError("CBWU source lacks one artifact identity")
            artifact, receipt = _download_artifact(gcs, uris[0], digests[0])
            books[f"R{seed}"] = _candidate_batch(group, artifact, slate_catalog)
            receipts.append({
                "seed": seed,
                "panel_run_id": panel_id,
                "season": season,
                "week": week,
                "candidate_rows": len(group),
                **receipt,
            })
        audit = audit_cbwu_seed_orders(
            books,
            tuple(books),
            n_entries=80,
            tail_line=194.0,
            expected_worlds_per_book=10_000,
        )
        audits.append({"season": season, "week": week, **audit})

    aggregate = _aggregate_audits(audits)
    report = {
        "version": "cbwu-seed-order-scorefree-v1",
        "uses_realized_outcomes": False,
        "code_sha": code_sha,
        "image": image,
        "source_table": SOURCE_TABLE,
        "player_table": PLAYER_TABLE,
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "source_panels": list(SOURCE_PANEL_IDS),
        "source_artifacts": receipts,
        "aggregate": aggregate,
        "slates": audits,
        "consequence": (
            "score-free order audit only; a sensitive result requires an "
            "order-proof or order-invariant repair and cannot select the "
            "historically best order"
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
        "aggregate": result["aggregate"],
        "output": result["output"],
    }, sort_keys=True))


if __name__ == "__main__":
    main()
