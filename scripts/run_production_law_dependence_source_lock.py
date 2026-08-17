#!/usr/bin/env python3
"""Create the sole outcome-free input lock for production-law dependence."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import math
import os
from pathlib import Path
import re

from google.cloud import bigquery, storage
import pandas as pd

from run_cbwu_seed_order_audit import _parse_gcs, _query, _upload_create_only


PROJECT = "nfl-predictions-503414"
RUN_ID = "20260817-production-law-dependence-source-lock-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    f"production-law-dependence-runs/{RUN_ID}"
)
OUTPUT_URI = f"{OUTPUT_PREFIX}/source-lock.json"
PROTOCOL = Path(
    "reports/2026-08-17-production-law-dependence-remeasurement-protocol.md"
)
PROTOCOL_SHA256 = (
    "0ab5850416d856537b47bedaf23b3fdce827dcf2f99e35f589520a123b63919f"
)
SOURCE_POPULATION_AMENDMENT = Path(
    "reports/2026-08-17-production-law-dependence-source-population-amendment.md"
)
SOURCE_POPULATION_AMENDMENT_SHA256 = (
    "16123cf7d96fb84a278fb29a86c99c1df56c8811a84ef69aa899a12305b25a3e"
)
TRANSFER_REPORT = Path(
    "reports/atlas-money-transfer-runs/"
    "20260815-atlas-current-money-transfer-v1/report.json"
)
TRANSFER_REPORT_SHA256 = (
    "8e568f8e5e343319ab4e4f48421b41f3266e56ecb592abce77f3ed6d246cd446"
)
CBWU_REPORT = Path(
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json"
)
CBWU_REPORT_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
REPAIR_VALIDATION = Path(
    "reports/atlas-mvp-source-repair-runs/"
    "20260816-atlas-mvp-source-repair-r3-2025-v1/validation.json"
)
REPAIR_VALIDATION_SHA256 = (
    "4938df8c8f7f84dea40baf2f76cd84f78cdc9e1a097c271b419e3dc8c6b5cd37"
)
REPAIR_EXECUTION = REPAIR_VALIDATION.with_name("execution.json")
REPAIR_EXECUTION_SHA256 = (
    "f2bb244daf1b2d9515bee59799095fcbdd44414acb16b06e65e8298bd87c62b7"
)
REPAIR_COMPLETION = REPAIR_VALIDATION.with_name("completion.txt")
REPAIR_COMPLETION_SHA256 = (
    "7bbff5dd3721ba436f79cb984091e7aa5815642629ab2c5615a6f2d9aacaa592"
)
SOURCE_PANELS = tuple(
    f"20260815-atlas-money-worlds-r{seed}-v1" for seed in range(5)
)
REPAIR_PANEL = "20260816-atlas-mvp-repair-r3-2025-v1"
REPAIR_ARTIFACT_URI = (
    "gs://nfl-predictions-503414-raw/cand_scores/"
    "20260816-atlas-mvp-repair-r3-2025-v1/2025_w1_1b661a12cf24.npz"
)
REPAIR_ARTIFACT_SHA256 = (
    "7eaef50c890150f6cdc329e80e4d68f08b4a8d2aac402fa5a51ba9ce4f860805"
)
CANDIDATE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"
CANDIDATE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, players,
       score_artifact_uri, score_artifact_sha256
FROM `{CANDIDATE_TABLE}`
WHERE (
  panel_run_id IN UNNEST(@source_panels)
  AND NOT (panel_run_id=@r3_panel AND season=2025 AND week=1)
) OR (
  panel_run_id=@repair_panel AND season=2025 AND week=1
)
ORDER BY season, week, panel_run_id, cand_ix
"""
PLAYER_SQL = f"""
SELECT season, week, id AS player_id, pos AS position, team,
       proj AS mean_projection
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season IN (2023, 2024, 2025)
ORDER BY season, week, player_id
"""
FORBIDDEN_QUERY_TOKENS = (
    "actual", "candidate_score", "lineup_score", " rank", "ownership",
    "selected", "payout", "labels_complete",
)


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _validate_repair_receipt() -> None:
    completion = dict(
        line.split("=", 1)
        for line in REPAIR_COMPLETION.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    validation = json.loads(REPAIR_VALIDATION.read_text(encoding="utf-8"))
    if completion.get("panel") != REPAIR_PANEL or \
            completion.get("repaired_artifact_uri") != REPAIR_ARTIFACT_URI or \
            completion.get("uses_realized_outcomes") != "false" or \
            completion.get("disposition") != "valid-mvp-source" or \
            validation.get("valid") is not True or \
            validation.get("uses_realized_outcomes") is not False or \
            validation.get("original_artifact_sha256") != \
            REPAIR_ARTIFACT_SHA256 or \
            validation.get("repaired_artifact_sha256") != \
            REPAIR_ARTIFACT_SHA256:
        raise RuntimeError(
            "production-law dependence repair receipt differs"
        )


def _validate_local_sources() -> dict[str, str]:
    expected = {
        str(PROTOCOL): PROTOCOL_SHA256,
        str(SOURCE_POPULATION_AMENDMENT): SOURCE_POPULATION_AMENDMENT_SHA256,
        str(TRANSFER_REPORT): TRANSFER_REPORT_SHA256,
        str(CBWU_REPORT): CBWU_REPORT_SHA256,
        str(REPAIR_VALIDATION): REPAIR_VALIDATION_SHA256,
        str(REPAIR_EXECUTION): REPAIR_EXECUTION_SHA256,
        str(REPAIR_COMPLETION): REPAIR_COMPLETION_SHA256,
    }
    for raw, digest in expected.items():
        path = Path(raw)
        if not path.is_file() or _file_sha(path) != digest:
            raise RuntimeError(f"production-law dependence source differs: {path}")
    present = [
        token for token in FORBIDDEN_QUERY_TOKENS
        if token in f"{PLAYER_SQL}\n{CANDIDATE_SQL}".lower()
    ]
    if present:
        raise RuntimeError(
            "production-law dependence catalog query is outcome-facing: "
            + ", ".join(present)
        )
    _validate_repair_receipt()
    return expected


def _validate_policy_and_artifacts(transfer: dict) -> list[dict]:
    if transfer.get("version") != "atlas-current-money-transfer-v1" or \
            transfer.get("uses_realized_outcomes") is not False or \
            transfer.get("candidate_or_lineup_scores_read") is not False or \
            transfer.get("transfer_disposition", {}).get("mechanical", {}).get(
                "passes"
            ) is not True:
        raise RuntimeError("production-law dependence transfer source differs")
    receipt = transfer.get("source_policy_receipt", {})
    law = receipt.get("simulation_law", {})
    if receipt.get("policy_id") != "classic-k1-role12-boom40-poscal-cbwu-v4" or \
            law != {
                "dirichlet_k": None,
                "game_mode": "possession",
                "game_sim_usage_env": "",
                "td_ledger": False,
                "team_factors": True,
                "usage_allocation": "production-multinomial",
            } or transfer.get("source_panels") != list(SOURCE_PANELS):
        raise RuntimeError("production-law dependence policy receipt differs")
    artifacts = transfer.get("source_artifacts")
    if not isinstance(artifacts, list) or len(artifacts) != 270:
        raise RuntimeError("production-law dependence artifact count differs")
    required = {
        "bytes", "candidate_rows", "generation", "panel_run_id", "season",
        "seed", "sha256", "updated", "uri", "week",
    }
    expected_grid = [
        (season, week, seed)
        for season in (2023, 2024, 2025)
        for week in range(1, 19)
        for seed in range(5)
    ]
    normalized = sorted(
        artifacts,
        key=lambda row: (int(row["season"]), int(row["week"]), int(row["seed"])),
    )
    if [(int(row["season"]), int(row["week"]), int(row["seed"]))
        for row in normalized] != expected_grid:
        raise RuntimeError("production-law dependence artifact grid differs")
    for row in normalized:
        if set(row) != required or \
                row["panel_run_id"] != SOURCE_PANELS[int(row["seed"])] or \
                not re.fullmatch(r"[0-9a-f]{64}", str(row["sha256"])) or \
                not str(row["generation"]).isdigit() or \
                not isinstance(row["bytes"], int) or row["bytes"] <= 0 or \
                not isinstance(row["candidate_rows"], int) or \
                row["candidate_rows"] < 80:
            raise RuntimeError("production-law dependence artifact receipt differs")
    return normalized


def _validate_object_metadata(gcs: storage.Client, artifacts: list[dict]) -> None:
    for index, row in enumerate(artifacts, start=1):
        bucket, name = _parse_gcs(str(row["uri"]))
        blob = gcs.bucket(bucket).blob(name)
        blob.reload()
        updated = blob.updated.isoformat() if blob.updated else ""
        if str(blob.generation) != str(row["generation"]) or \
                int(blob.size or -1) != int(row["bytes"]) or \
                updated != str(row["updated"]):
            raise RuntimeError("production-law dependence GCS source object changed")
        if index % 25 == 0 or index == len(artifacts):
            print(
                "PRODUCTION_LAW_DEPENDENCE_SOURCE_METADATA_COMPLETE",
                index, len(artifacts), flush=True,
            )


def _candidate_params() -> list[bigquery.QueryParameter]:
    return [
        bigquery.ArrayQueryParameter(
            "source_panels", "STRING", list(SOURCE_PANELS),
        ),
        bigquery.ScalarQueryParameter("r3_panel", "STRING", SOURCE_PANELS[3]),
        bigquery.ScalarQueryParameter("repair_panel", "STRING", REPAIR_PANEL),
    ]


def _candidate_unions(
    frame: pd.DataFrame, artifacts: list[dict],
) -> dict[tuple[int, int], set[str]]:
    if len(frame) != 68_199:
        raise RuntimeError("production-law dependence candidate row count differs")
    locked = {
        (int(row["season"]), int(row["week"]), int(row["seed"])): row
        for row in artifacts
    }
    panel_seed = {panel: seed for seed, panel in enumerate(SOURCE_PANELS)}
    panel_seed[REPAIR_PANEL] = 3
    unions: dict[tuple[int, int], set[str]] = {}
    groups = frame.groupby(["season", "week", "panel_run_id"], sort=True)
    if len(groups) != 270:
        raise RuntimeError("production-law dependence candidate panel grid differs")
    for (season_raw, week_raw, panel_raw), group in groups:
        season, week, panel = int(season_raw), int(week_raw), str(panel_raw)
        if panel not in panel_seed:
            raise RuntimeError("production-law dependence candidate panel differs")
        seed = panel_seed[panel]
        expected_panel = (
            REPAIR_PANEL if season == 2025 and week == 1 and seed == 3
            else SOURCE_PANELS[seed]
        )
        if panel != expected_panel:
            raise RuntimeError("production-law dependence repair substitution differs")
        indices = pd.to_numeric(group.cand_ix, errors="raise").astype(int).tolist()
        if indices != list(range(len(group))):
            raise RuntimeError("production-law dependence candidate indices differ")
        uris = group.score_artifact_uri.astype(str).unique().tolist()
        digests = group.score_artifact_sha256.astype(str).unique().tolist()
        source = locked[(season, week, seed)]
        repair_substitution = season == 2025 and week == 1 and seed == 3
        expected_uri = REPAIR_ARTIFACT_URI if repair_substitution else source["uri"]
        if repair_substitution and source["sha256"] != REPAIR_ARTIFACT_SHA256:
            raise RuntimeError(
                "production-law dependence repair byte identity differs"
            )
        if uris != [expected_uri] or digests != [source["sha256"]] or \
                len(group) != int(source["candidate_rows"]):
            raise RuntimeError("production-law dependence candidate artifact differs")
        union = unions.setdefault((season, week), set())
        for raw in group.players.astype(str):
            roster = [value for value in raw.split(",") if value]
            if len(roster) != 9 or len(set(roster)) != 9:
                raise RuntimeError("production-law dependence candidate roster differs")
            union.update(roster)
    expected_slates = {
        (season, week)
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    if set(unions) != expected_slates or sum(map(len, unions.values())) != 10_729:
        raise RuntimeError("production-law dependence candidate union differs")
    return unions


def _catalog_rows(
    frame: pd.DataFrame, candidate_unions: dict[tuple[int, int], set[str]],
) -> list[dict]:
    expected_slates = {
        (season, week)
        for season in (2023, 2024, 2025) for week in range(1, 19)
    }
    if frame.empty or frame.duplicated(["season", "week", "player_id"]).any() or \
            set(zip(frame.season.astype(int), frame.week.astype(int))) != expected_slates:
        raise RuntimeError("production-law dependence player catalog grid differs")
    projections = pd.to_numeric(frame.mean_projection, errors="coerce")
    if projections.isna().any() or not all(math.isfinite(float(value)) for value in projections):
        raise RuntimeError("production-law dependence served means are non-finite")
    catalog_keys = {
        (int(row.season), int(row.week), str(row.player_id))
        for row in frame.itertuples(index=False)
    }
    required_keys = {
        (season, week, player_id)
        for (season, week), players in candidate_unions.items()
        for player_id in players
    }
    if required_keys - catalog_keys:
        raise RuntimeError("production-law dependence candidate player is unbound")
    rows = []
    for row, projection in zip(frame.itertuples(index=False), projections, strict=True):
        position = str(row.position).upper()
        team = str(row.team).upper()
        player_id = str(row.player_id)
        if not player_id or not position or not team:
            raise RuntimeError("production-law dependence player identity is empty")
        if player_id not in candidate_unions[(int(row.season), int(row.week))]:
            continue
        rows.append({
            "season": int(row.season),
            "week": int(row.week),
            "player_id": player_id,
            "position": position,
            "team": team,
            "mean_projection": float(projection),
        })
    if rows != sorted(rows, key=lambda value: (
        value["season"], value["week"], value["player_id"],
    )):
        raise RuntimeError("production-law dependence catalog order differs")
    if len(rows) != 10_729:
        raise RuntimeError("production-law dependence candidate catalog count differs")
    return rows


def run(output_uri: str) -> dict:
    if output_uri != OUTPUT_URI:
        raise RuntimeError("production-law dependence source-lock URI differs")
    source_hashes = _validate_local_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("production-law dependence code/image is required")

    transfer = json.loads(TRANSFER_REPORT.read_text(encoding="utf-8"))
    artifacts = _validate_policy_and_artifacts(transfer)
    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    _validate_object_metadata(gcs, artifacts)
    candidates = _query(bq, CANDIDATE_SQL, _candidate_params())
    candidate_unions = _candidate_unions(candidates, artifacts)
    catalog = _query(bq, PLAYER_SQL, [
        bigquery.ScalarQueryParameter("r0_panel", "STRING", SOURCE_PANELS[0]),
    ])
    rows = _catalog_rows(catalog, candidate_unions)
    catalog_raw = json.dumps(
        rows, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()
    eligible = [
        row for row in rows
        if row["position"] in {"QB", "RB", "WR", "TE"}
        and row["mean_projection"] >= 4.0
    ]
    if len(eligible) != 9_469:
        raise RuntimeError(
            "production-law dependence eligible candidate-union count differs"
        )
    payload = {
        "version": "production-law-dependence-source-lock-v1",
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "actual_outcomes_queried": False,
        "candidate_or_lineup_scores_read": False,
        "production_change_licensed": False,
        "code_sha": code_sha,
        "analysis_image": image,
        "protocol_sha256": PROTOCOL_SHA256,
        "source_hashes": source_hashes,
        "source_policy_receipt": transfer["source_policy_receipt"],
        "source_population_amendment_sha256": (
            SOURCE_POPULATION_AMENDMENT_SHA256
        ),
        "source_panels": list(SOURCE_PANELS),
        "artifact_count": len(artifacts),
        "artifact_receipts": artifacts,
        "candidate_source_substitution": {
            "season": 2025,
            "week": 1,
            "seed": 3,
            "panel_run_id": REPAIR_PANEL,
            "original_uri": next(
                row["uri"] for row in artifacts
                if row["season"] == 2025 and row["week"] == 1
                and row["seed"] == 3
            ),
            "repaired_uri": REPAIR_ARTIFACT_URI,
            "sha256": REPAIR_ARTIFACT_SHA256,
            "byte_identical": True,
        },
        "candidate_rows": len(candidates),
        "candidate_union_rows": len(rows),
        "catalog_rows": len(rows),
        "eligible_rows": len(eligible),
        "slates": 54,
        "catalog_sha256": sha256(catalog_raw).hexdigest(),
        "catalog": rows,
    }
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        + "\n"
    ).encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("PRODUCTION_LAW_DEPENDENCE_SOURCE_LOCK_RESULT " + json.dumps(
        upload, sort_keys=True,
    ))
    return {**payload, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.output_uri)


if __name__ == "__main__":
    main()
