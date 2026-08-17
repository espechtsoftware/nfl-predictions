#!/usr/bin/env python3
"""Immutable outcome-free source loader for coherent market-state studies."""

from __future__ import annotations

from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path

import numpy as np
from google.cloud import bigquery, storage

from nfl_dfs.analysis.constraint_lattice import REGISTERED_BLOCKS
from run_cbwu_seed_order_audit import _candidate_batch, _download_artifact, _query


PROJECT = "nfl-predictions-503414"
SOURCE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"
SOURCE_PANELS = tuple(
    f"20260815-atlas-money-worlds-r{seed}-v1" for seed in range(5)
)
REPAIR_PANEL = "20260816-atlas-mvp-repair-r3-2025-v1"
PROTOCOL = Path(
    "reports/2026-08-16-coherent-market-state-scorefree-protocol.md"
)
PROTOCOL_SHA256 = (
    "ddf40d804614aa3011604cda49c1c599309418fd7d0298a56529e87de4ef1208"
)
SUPPORT = Path(
    "reports/2026-08-16-coherent-market-state-support-census.md"
)
SUPPORT_SHA256 = (
    "677171a16e339083b2eb1272926e9024ecab63b531ecc861d5237f94e61c0e63"
)
EXECUTION_PROTOCOL = Path(
    "reports/2026-08-17-coherent-market-state-execution-protocol.md"
)
EXECUTION_PROTOCOL_SHA256 = (
    "0dd8175e88c9e01c29971663e0455f83b3d693c97b34f8bf8de2b2d054fafcbd"
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
SOURCE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, tag, all_tags, players,
       score_artifact_uri, score_artifact_sha256
FROM `{SOURCE_TABLE}`
WHERE season=@season AND week=@week AND (
  (panel_run_id IN UNNEST(@source_panels)
   AND NOT (panel_run_id=@r3_panel AND season=2025 AND week=1))
  OR (panel_run_id=@repair_panel AND season=2025 AND week=1)
)
ORDER BY panel_run_id, cand_ix
"""
PLAYER_SQL = f"""
SELECT season, week, id AS player_id, name AS player_name, pos AS position,
       team, opp AS opponent, game_id, salary, proj AS mean_projection,
       market_points, model_points_pre
FROM `{PLAYER_TABLE}`
WHERE panel_run_id=@r0_panel AND season=@season AND week=@week
ORDER BY player_id
"""
FORBIDDEN_QUERY_TOKENS = (
    "actual_score", "actual_rank", "actual_ownership", "actual ",
    "selected_rank", "selected ", "payout", "contest_rank",
    "labels_complete",
)


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_local_sources() -> dict[str, str]:
    """Bind every protocol, acquisition and source-repair receipt."""
    expected = {
        str(PROTOCOL): PROTOCOL_SHA256,
        str(SUPPORT): SUPPORT_SHA256,
        str(EXECUTION_PROTOCOL): EXECUTION_PROTOCOL_SHA256,
        str(TRANSFER_REPORT): TRANSFER_REPORT_SHA256,
        str(CBWU_REPORT): CBWU_REPORT_SHA256,
        str(REPAIR_VALIDATION): REPAIR_VALIDATION_SHA256,
        str(REPAIR_EXECUTION): REPAIR_EXECUTION_SHA256,
        str(REPAIR_COMPLETION): REPAIR_COMPLETION_SHA256,
    }
    for raw_path, digest in expected.items():
        path = Path(raw_path)
        if not path.is_file() or _file_sha(path) != digest:
            raise RuntimeError(f"coherent-state frozen source differs: {path}")

    transfer = json.loads(TRANSFER_REPORT.read_text(encoding="utf-8"))
    cbwu = json.loads(CBWU_REPORT.read_text(encoding="utf-8"))
    repair = json.loads(REPAIR_VALIDATION.read_text(encoding="utf-8"))
    repair_execution = json.loads(REPAIR_EXECUTION.read_text(encoding="utf-8"))
    repair_completion = dict(
        line.split("=", 1)
        for line in REPAIR_COMPLETION.read_text(encoding="utf-8").splitlines()
        if "=" in line
    )
    terminal = [
        row for row in repair_execution.get("status", {}).get("conditions", [])
        if row.get("type") == "Completed"
    ]
    if transfer.get("gate", {}).get("passes_original_all_six") is not True or \
            transfer.get("uses_realized_outcomes") is not False or \
            cbwu.get("aggregate", {}).get("passes_scorefree_gate") is not True or \
            cbwu.get("uses_realized_outcomes") is not False or \
            repair.get("valid") is not True or \
            repair.get("uses_realized_outcomes") is not False or \
            len(terminal) != 1 or terminal[0].get("status") != "True" or \
            repair_completion.get("disposition") != "valid-mvp-source" or \
            repair_completion.get("uses_realized_outcomes") != "false":
        raise RuntimeError("coherent-state source disposition differs")
    combined = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    present = [token for token in FORBIDDEN_QUERY_TOKENS if token in combined]
    if present:
        raise RuntimeError(
            "coherent-state query contains forbidden fields: " + ", ".join(present)
        )
    return expected


def _source_params(season: int, week: int):
    return [
        bigquery.ArrayQueryParameter("source_panels", "STRING", list(SOURCE_PANELS)),
        bigquery.ScalarQueryParameter("r3_panel", "STRING", SOURCE_PANELS[3]),
        bigquery.ScalarQueryParameter("repair_panel", "STRING", REPAIR_PANEL),
        bigquery.ScalarQueryParameter("season", "INT64", int(season)),
        bigquery.ScalarQueryParameter("week", "INT64", int(week)),
    ]


def _player_params(season: int, week: int):
    return [
        bigquery.ScalarQueryParameter("r0_panel", "STRING", SOURCE_PANELS[0]),
        bigquery.ScalarQueryParameter("season", "INT64", int(season)),
        bigquery.ScalarQueryParameter("week", "INT64", int(week)),
    ]


def _canonical_panel(panel: str) -> str:
    return SOURCE_PANELS[3] if panel == REPAIR_PANEL else panel


def _enrich_batch(batch, catalog):
    indexed = catalog.set_index(catalog.player_id.astype(str), drop=False)
    if not indexed.index.is_unique:
        raise RuntimeError("coherent-state player catalog IDs repeat")
    enriched = []

    def optional_float(value):
        try:
            numeric = float(value)
        except (TypeError, ValueError):
            return None
        return numeric if np.isfinite(numeric) else None

    for row in batch.player_rows:
        source = indexed.loc[str(row["id"])]
        enriched.append({
            **row,
            "mean_projection": float(source.mean_projection),
            "market_points": optional_float(source.market_points),
            "model_points_pre": optional_float(source.model_points_pre),
        })
    return replace(batch, player_rows=tuple(enriched))


def load_slate_sources(
    bq: bigquery.Client,
    gcs: storage.Client,
    *,
    season: int,
    week: int,
):
    """Load the exact five money books and pre-lock disagreement features."""
    sources = _query(bq, SOURCE_SQL, _source_params(season, week))
    catalog = _query(bq, PLAYER_SQL, _player_params(season, week))
    if sources.empty or catalog.empty:
        raise RuntimeError("coherent-state source/catalog is empty")
    canonical = sources.panel_run_id.astype(str).map(_canonical_panel)
    if set(canonical) != set(SOURCE_PANELS):
        raise RuntimeError("coherent-state source panel grid differs")

    books = {}
    receipts = []
    for block, panel in zip(REGISTERED_BLOCKS, SOURCE_PANELS, strict=True):
        group = sources[canonical.eq(panel)].copy()
        uris = group.score_artifact_uri.astype(str).unique()
        digests = group.score_artifact_sha256.astype(str).unique()
        raw_panels = group.panel_run_id.astype(str).unique()
        expected_raw = (
            REPAIR_PANEL
            if panel == SOURCE_PANELS[3] and season == 2025 and week == 1
            else panel
        )
        if group.empty or len(uris) != 1 or len(digests) != 1 or \
                list(raw_panels) != [expected_raw]:
            raise RuntimeError("coherent-state native source identity differs")
        artifact, receipt = _download_artifact(gcs, uris[0], digests[0])
        books[block] = _enrich_batch(
            _candidate_batch(group, artifact, catalog), catalog,
        )
        receipts.append({
            "block": block,
            "source_panel": str(raw_panels[0]),
            "canonical_panel": panel,
            "candidate_rows": len(group),
            **receipt,
        })
    return books, receipts


__all__ = [
    "PLAYER_SQL",
    "PROJECT",
    "REPAIR_PANEL",
    "SOURCE_PANELS",
    "SOURCE_SQL",
    "load_slate_sources",
    "validate_local_sources",
]
