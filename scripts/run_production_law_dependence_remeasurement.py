#!/usr/bin/env python3
"""Run the sole historical remeasurement of the exact production law."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from typing import Mapping

from google.cloud import bigquery, storage
import numpy as np
import pandas as pd

from nfl_dfs.analysis.final_served_dependence import evaluate_dependence
from nfl_dfs.analysis.production_law_dependence import (
    REGISTERED_BLOCKS,
    aggregate_remeasurement,
)
from run_cbwu_seed_order_audit import (
    _download_artifact,
    _parse_gcs,
    _query,
    _upload_create_only,
)
from run_production_law_dependence_source_lock import (
    CBWU_REPORT,
    CBWU_REPORT_SHA256,
    OUTPUT_URI as SOURCE_LOCK_URI,
    PLAYER_TABLE,
    PROJECT,
    PROTOCOL,
    PROTOCOL_SHA256,
    REPAIR_COMPLETION,
    REPAIR_COMPLETION_SHA256,
    REPAIR_EXECUTION,
    REPAIR_EXECUTION_SHA256,
    REPAIR_VALIDATION,
    REPAIR_VALIDATION_SHA256,
    SOURCE_PANELS,
    TRANSFER_REPORT,
    TRANSFER_REPORT_SHA256,
)


RUN_ID = "20260817-production-law-dependence-remeasurement-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    f"production-law-dependence-runs/{RUN_ID}"
)
OUTPUT_URI = f"{OUTPUT_PREFIX}/report.json"
OUTCOME_SQL = f"""
SELECT season, week, id AS player_id, actual
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season IN (2023, 2024, 2025)
ORDER BY season, week, player_id
"""


def _download_json(
    client: storage.Client, uri: str,
) -> tuple[dict, dict[str, object], bytes]:
    bucket, name = _parse_gcs(uri)
    blob = client.bucket(bucket).blob(name)
    raw = blob.download_as_bytes()
    blob.reload()
    return json.loads(raw), {
        "uri": uri,
        "generation": str(blob.generation),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
        "updated": blob.updated.isoformat() if blob.updated else "",
    }, raw


def _catalog_digest(rows: list[dict]) -> str:
    return sha256(json.dumps(
        rows, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()).hexdigest()


def _validate_source_lock(
    lock: Mapping[str, object], *, generation: str, digest: str,
) -> tuple[list[dict], list[dict]]:
    fixed = {
        "version": "production-law-dependence-source-lock-v1",
        "run_id": "20260817-production-law-dependence-source-lock-v1",
        "uses_realized_outcomes": False,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
        "protocol_sha256": PROTOCOL_SHA256,
        "artifact_count": 270,
        "slates": 54,
        "source_panels": list(SOURCE_PANELS),
    }
    if any(lock.get(key) != value for key, value in fixed.items()) or \
            not generation.isdigit() or \
            not re.fullmatch(r"[0-9a-f]{64}", digest) or \
            not re.fullmatch(r"[0-9a-f]{40}", str(lock.get("code_sha", ""))) or \
            not re.fullmatch(
                r".+@sha256:[0-9a-f]{64}", str(lock.get("analysis_image", "")),
            ):
        raise RuntimeError("production-law dependence source lock differs")
    expected_hashes = {
        str(PROTOCOL): PROTOCOL_SHA256,
        str(TRANSFER_REPORT): TRANSFER_REPORT_SHA256,
        str(CBWU_REPORT): CBWU_REPORT_SHA256,
        str(REPAIR_VALIDATION): REPAIR_VALIDATION_SHA256,
        str(REPAIR_EXECUTION): REPAIR_EXECUTION_SHA256,
        str(REPAIR_COMPLETION): REPAIR_COMPLETION_SHA256,
    }
    if lock.get("source_hashes") != expected_hashes:
        raise RuntimeError("production-law dependence locked source hashes differ")
    law = lock.get("source_policy_receipt", {})
    if not isinstance(law, Mapping) or \
            law.get("policy_id") != "classic-k1-role12-boom40-poscal-cbwu-v4" or \
            law.get("simulation_law") != {
                "dirichlet_k": None,
                "game_mode": "possession",
                "game_sim_usage_env": "",
                "td_ledger": False,
                "team_factors": True,
                "usage_allocation": "production-multinomial",
            }:
        raise RuntimeError("production-law dependence locked policy differs")
    artifacts = lock.get("artifact_receipts")
    catalog = lock.get("catalog")
    if not isinstance(artifacts, list) or len(artifacts) != 270 or \
            not isinstance(catalog, list) or len(catalog) != lock.get("catalog_rows") or \
            _catalog_digest(catalog) != lock.get("catalog_sha256"):
        raise RuntimeError("production-law dependence locked population differs")
    artifact_fields = {
        "bytes", "candidate_rows", "generation", "panel_run_id", "season",
        "seed", "sha256", "updated", "uri", "week",
    }
    expected_grid = [
        (season, week, seed)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for seed in range(5)
    ]
    if [(row.get("season"), row.get("week"), row.get("seed"))
        for row in artifacts] != expected_grid:
        raise RuntimeError("production-law dependence locked artifact grid differs")
    for row in artifacts:
        seed = row.get("seed")
        if set(row) != artifact_fields or not isinstance(seed, int) or \
                seed not in range(5) or row.get("panel_run_id") != SOURCE_PANELS[seed] or \
                not re.fullmatch(r"[0-9a-f]{64}", str(row.get("sha256", ""))) or \
                not str(row.get("generation", "")).isdigit() or \
                not isinstance(row.get("bytes"), int) or int(row["bytes"]) <= 0:
            raise RuntimeError("production-law dependence locked artifact receipt differs")
    catalog_keys = [
        (row.get("season"), row.get("week"), row.get("player_id"))
        for row in catalog
    ]
    if catalog_keys != sorted(catalog_keys) or len(catalog_keys) != len(set(catalog_keys)):
        raise RuntimeError("production-law dependence locked catalog keys differ")
    catalog_fields = {
        "season", "week", "player_id", "position", "team", "mean_projection",
    }
    for row in catalog:
        try:
            mean = float(row.get("mean_projection"))
        except (TypeError, ValueError) as exc:
            raise RuntimeError(
                "production-law dependence locked served mean differs"
            ) from exc
        if set(row) != catalog_fields or not row.get("player_id") or \
                not row.get("position") or not row.get("team") or \
                not np.isfinite(mean):
            raise RuntimeError("production-law dependence locked catalog row differs")
    eligible = [
        row for row in catalog
        if row.get("position") in {"QB", "RB", "WR", "TE"}
        and float(row.get("mean_projection", float("-inf"))) >= 4.0
    ]
    if len(eligible) != lock.get("eligible_rows") or not eligible:
        raise RuntimeError("production-law dependence locked eligibility differs")
    return artifacts, catalog


def _validate_artifact_metadata(
    gcs: storage.Client, artifacts: list[dict],
) -> None:
    """Validate the complete immutable grid before any outcome query."""
    for index, row in enumerate(artifacts, start=1):
        bucket, name = _parse_gcs(str(row["uri"]))
        blob = gcs.bucket(bucket).blob(name)
        blob.reload()
        updated = blob.updated.isoformat() if blob.updated else ""
        if str(blob.generation) != str(row["generation"]) or \
                int(blob.size or -1) != int(row["bytes"]) or \
                updated != str(row["updated"]):
            raise RuntimeError("production-law dependence artifact metadata changed")
        if index % 25 == 0 or index == len(artifacts):
            print(
                "PRODUCTION_LAW_DEPENDENCE_PREFLIGHT_METADATA_COMPLETE",
                index, len(artifacts), flush=True,
            )


def _actual_maps(frame: pd.DataFrame) -> dict[tuple[int, int], dict[str, float]]:
    if frame.empty or frame.duplicated(["season", "week", "player_id"]).any():
        raise RuntimeError("production-law dependence outcomes differ")
    result = {}
    for (season, week), group in frame.groupby(["season", "week"], sort=True):
        values = pd.to_numeric(group.actual, errors="coerce")
        finite = np.isfinite(values.to_numpy(dtype=float))
        result[(int(season), int(week))] = {
            str(player_id): float(actual)
            for player_id, actual, keep in zip(
                group.player_id, values, finite, strict=True,
            )
            if keep
        }
    expected = {
        (season, week)
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    if set(result) != expected:
        raise RuntimeError("production-law dependence outcome slate grid differs")
    return result


def _receipt_subset(row: Mapping[str, object]) -> dict[str, object]:
    return {
        key: row[key]
        for key in ("uri", "sha256", "generation", "updated", "bytes")
    }


def _build_population(
    gcs: storage.Client,
    artifacts: list[dict],
    catalog: list[dict],
    actual: Mapping[tuple[int, int], Mapping[str, float]],
) -> tuple[pd.DataFrame, dict[str, np.ndarray], list[dict]]:
    by_slate: dict[tuple[int, int], list[dict]] = {}
    for row in catalog:
        by_slate.setdefault((int(row["season"]), int(row["week"])), []).append(row)
    artifact_by_key = {
        (int(row["season"]), int(row["week"]), int(row["seed"])): row
        for row in artifacts
    }
    frames = []
    chunks: dict[str, list[np.ndarray]] = {block: [] for block in REGISTERED_BLOCKS}
    downloads = []
    for season in (2023, 2024, 2025):
        for week in range(1, 19):
            slate = (season, week)
            eligible = [
                row for row in by_slate[slate]
                if row["position"] in {"QB", "RB", "WR", "TE"}
                and float(row["mean_projection"]) >= 4.0
            ]
            eligible.sort(key=lambda row: str(row["player_id"]))
            ids = [str(row["player_id"]) for row in eligible]
            missing = [player_id for player_id in ids if player_id not in actual[slate]]
            if missing:
                raise RuntimeError("production-law dependence eligible outcomes missing")
            frames.extend({
                "season": season,
                "week": week,
                "gsis_id": player_id,
                "team": str(row["team"]),
                "position": str(row["position"]),
                "actual": float(actual[slate][player_id]),
                "mean_projection": float(row["mean_projection"]),
            } for row, player_id in zip(eligible, ids, strict=True))
            common_universe = None
            for seed, block in enumerate(REGISTERED_BLOCKS):
                locked = artifact_by_key[(season, week, seed)]
                artifact, receipt = _download_artifact(
                    gcs, str(locked["uri"]), str(locked["sha256"]),
                )
                if receipt != _receipt_subset(locked):
                    raise RuntimeError("production-law dependence artifact receipt changed")
                player_ids = np.asarray(artifact["player_ids"]).astype(str).tolist()
                draws = np.asarray(artifact["player_draws"], dtype=np.float32)
                if len(player_ids) != len(set(player_ids)) or \
                        draws.shape != (len(player_ids), 10_000) or \
                        not np.isfinite(draws).all():
                    raise RuntimeError("production-law dependence player worlds differ")
                universe = set(player_ids)
                if common_universe is None:
                    common_universe = universe
                elif universe != common_universe:
                    raise RuntimeError("production-law dependence block universes differ")
                index = {player_id: row for row, player_id in enumerate(player_ids)}
                if set(ids) - universe:
                    raise RuntimeError("production-law dependence eligible universe differs")
                chunks[block].append(draws[[index[player_id] for player_id in ids]])
                downloads.append({
                    "season": season, "week": week, "block": block,
                    **receipt,
                })
            print(
                "PRODUCTION_LAW_DEPENDENCE_SLATE_SOURCE_COMPLETE",
                season, week, flush=True,
            )
    frame = pd.DataFrame(frames)
    block_draws = {
        block: np.concatenate(chunks[block], axis=0)
        for block in REGISTERED_BLOCKS
    }
    if any(values.shape != (len(frame), 10_000) for values in block_draws.values()):
        raise RuntimeError("production-law dependence assembled world grid differs")
    return frame, block_draws, downloads


def run(
    source_lock_uri: str,
    source_lock_generation: str,
    source_lock_sha256: str,
    output_uri: str,
) -> dict:
    if source_lock_uri != SOURCE_LOCK_URI or output_uri != OUTPUT_URI or \
            not PROTOCOL.is_file() or sha256(PROTOCOL.read_bytes()).hexdigest() != \
            PROTOCOL_SHA256:
        raise RuntimeError("production-law dependence run identity differs")
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("production-law dependence code/image is required")

    gcs = storage.Client(project=PROJECT)
    lock, lock_object, raw_lock = _download_json(gcs, source_lock_uri)
    if lock_object["generation"] != source_lock_generation or \
            lock_object["sha256"] != source_lock_sha256:
        raise RuntimeError("production-law dependence source-lock object changed")
    artifacts, catalog = _validate_source_lock(
        lock, generation=source_lock_generation, digest=source_lock_sha256,
    )
    # This complete metadata preflight is deliberately before the sole outcome
    # query.  It prevents a partial source grid from becoming an adaptive look.
    _validate_artifact_metadata(gcs, artifacts)

    bq = bigquery.Client(project=PROJECT)
    outcomes = _query(bq, OUTCOME_SQL, [
        bigquery.ScalarQueryParameter("r0_panel", "STRING", SOURCE_PANELS[0]),
    ])
    actual = _actual_maps(outcomes)
    frame, draws, downloads = _build_population(
        gcs, artifacts, catalog, actual,
    )
    if len(frame) != int(lock["eligible_rows"]):
        raise RuntimeError("production-law dependence eligible row count changed")

    block_reports = {}
    for block in REGISTERED_BLOCKS:
        block_reports[block] = evaluate_dependence(frame, draws[block])
        print("PRODUCTION_LAW_DEPENDENCE_BLOCK_COMPLETE", block, flush=True)
    combined = np.concatenate([draws[block] for block in REGISTERED_BLOCKS], axis=1)
    aggregate = evaluate_dependence(frame, combined)
    result = aggregate_remeasurement(block_reports, aggregate)
    result.update({
        "run_id": RUN_ID,
        "protocol_sha256": PROTOCOL_SHA256,
        "code_sha": code_sha,
        "analysis_image": image,
        "source_lock": lock_object,
        "source_lock_sha256": sha256(raw_lock).hexdigest(),
        "source_lock_code_sha": lock["code_sha"],
        "source_lock_image": lock["analysis_image"],
        "source_policy_receipt": lock["source_policy_receipt"],
        "source_panels": list(SOURCE_PANELS),
        "source_artifacts": downloads,
        "outcome_query_issued_after_complete_source_preflight": True,
        "outcome_population": {
            "slates": 54,
            "eligible_player_rows": len(frame),
            "missing_eligible_outcomes": 0,
            "duplicate_eligible_keys": int(frame.duplicated(
                ["season", "week", "gsis_id"]
            ).sum()),
        },
    })
    raw = (
        json.dumps(result, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("PRODUCTION_LAW_DEPENDENCE_REMEASUREMENT_RESULT " + json.dumps({
        "gate": result["gate"], "output": upload,
    }, sort_keys=True))
    return {**result, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-lock-uri", required=True)
    parser.add_argument("--source-lock-generation", required=True)
    parser.add_argument("--source-lock-sha256", required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(
        args.source_lock_uri,
        args.source_lock_generation,
        args.source_lock_sha256,
        args.output_uri,
    )


if __name__ == "__main__":
    main()
