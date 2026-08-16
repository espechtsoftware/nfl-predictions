#!/usr/bin/env python3
"""Run one immutable, outcome-free constraint-lattice slate shard."""

from __future__ import annotations

import argparse
from hashlib import sha256
import json
import os
from pathlib import Path
import re

from google.cloud import bigquery, storage

from nfl_dfs.analysis.constraint_lattice import (
    REGISTERED_BLOCKS,
    protocol_receipt,
    run_scorefree_slate,
)

from run_cbwu_seed_order_audit import (
    _candidate_batch,
    _download_artifact,
    _query,
    _upload_create_only,
)


PROJECT = "nfl-predictions-503414"
RUN_ID = "20260816-constraint-lattice-scorefree-v1"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/constraint-lattice-runs/"
    f"{RUN_ID}"
)
SOURCE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = (
    f"{PROJECT}.nfl_forensic_review."
    "final_forensic_20260814_player_corpus_repair4"
)
FORENSIC_MANIFEST_SHA256 = (
    "51edbe124846dc936ade71c4e5a9a07e252bcf6c7d7872b979715ccd1f6bab02"
)
SOURCE_PANELS = tuple(
    f"20260813-sis-asoe-treatment-r{seed}-v1" for seed in range(5)
)
PROTOCOL = Path("reports/2026-08-16-constraint-lattice-scorefree-protocol.md")
PROTOCOL_SHA256 = (
    "f8591d24dd56749e5b56235f9636687fd41bd1a78991fdb60cfbb092ee65bf62"
)
SOURCE_AMENDMENT = Path(
    "reports/2026-08-16-constraint-lattice-source-and-execution-amendment.md"
)
SOURCE_AMENDMENT_SHA256 = (
    "35ea1f0dba3be5311631d51057c7667cb624bcdc19be75e2b202c57e297e8321"
)
CBWU_REPORT = Path(
    "reports/cbwu-order-invariant-runs/"
    "20260815-cbwu-order-invariant-repair-v1/report.json"
)
CBWU_REPORT_SHA256 = (
    "556adeca6e0bf2855ad82296b1e708041a20446dc27e2c988c1d11e8c5bd4d33"
)
SOURCE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, tag, all_tags, players,
       score_artifact_uri, score_artifact_sha256
FROM `{SOURCE_TABLE}`
WHERE panel_run_id IN UNNEST(@panel_ids)
  AND season=@season AND week=@week
ORDER BY panel_run_id, cand_ix
"""
PLAYER_SQL = f"""
SELECT manifest_sha256, season, week, player_id, player_name, position,
       team, opponent, game_id, salary, mean_projection
FROM `{PLAYER_TABLE}`
WHERE scope='phase-s-cbwu-54' AND season=@season AND week=@week
ORDER BY player_id
"""
FORBIDDEN_QUERY_TOKENS = (
    "actual_score", "actual_rank", "actual_ownership", "selected_rank",
    "selected ", "payout", "contest_rank", "labels_complete",
)


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_local_sources() -> dict[str, str]:
    expected = {
        str(PROTOCOL): PROTOCOL_SHA256,
        str(SOURCE_AMENDMENT): SOURCE_AMENDMENT_SHA256,
        str(CBWU_REPORT): CBWU_REPORT_SHA256,
    }
    for raw_path, digest in expected.items():
        path = Path(raw_path)
        if not path.is_file() or _file_sha(path) != digest:
            raise RuntimeError(f"constraint-lattice frozen source differs: {path}")
    report = json.loads(CBWU_REPORT.read_text(encoding="utf-8"))
    if report.get("version") != "cbwu-order-invariant-repair-scorefree-v1" or \
            report.get("uses_realized_outcomes") is not False or \
            report.get("forensic_manifest_sha256") != FORENSIC_MANIFEST_SHA256 or \
            tuple(report.get("source_panels", ())) != SOURCE_PANELS or \
            report.get("aggregate", {}).get("passes_scorefree_gate") is not True or \
            report.get("aggregate", {}).get("slates") != 54 or \
            len(report.get("source_artifacts", ())) != 270:
        raise RuntimeError("constraint-lattice CBWU-OI source disposition differs")
    combined = f"{SOURCE_SQL}\n{PLAYER_SQL}".lower()
    present = [token for token in FORBIDDEN_QUERY_TOKENS if token in combined]
    if present:
        raise RuntimeError(
            "constraint-lattice query contains forbidden fields: "
            + ", ".join(present)
        )
    return expected


def _query_params(season: int, week: int):
    return [
        bigquery.ArrayQueryParameter("panel_ids", "STRING", list(SOURCE_PANELS)),
        bigquery.ScalarQueryParameter("season", "INT64", int(season)),
        bigquery.ScalarQueryParameter("week", "INT64", int(week)),
    ]


def _player_params(season: int, week: int):
    return [
        bigquery.ScalarQueryParameter("season", "INT64", int(season)),
        bigquery.ScalarQueryParameter("week", "INT64", int(week)),
    ]


def run(season: int, week: int, output_uri: str) -> dict:
    expected_uri = f"{OUTPUT_PREFIX}/slate-{season}-{week}.json"
    if season not in {2023, 2024, 2025} or week not in range(1, 19) or \
            output_uri != expected_uri:
        raise RuntimeError("constraint-lattice shard identity differs")
    source_hashes = validate_local_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("constraint-lattice code/image identity is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    sources = _query(bq, SOURCE_SQL, _query_params(season, week))
    catalog = _query(bq, PLAYER_SQL, _player_params(season, week))
    if sources.empty or catalog.empty or \
            set(catalog.manifest_sha256.astype(str)) != {
                FORENSIC_MANIFEST_SHA256
            }:
        raise RuntimeError("constraint-lattice source/catalog is incomplete")
    keys = sources[["panel_run_id", "season", "week"]].drop_duplicates()
    if len(keys) != 5 or set(keys.panel_run_id.astype(str)) != set(SOURCE_PANELS):
        raise RuntimeError("constraint-lattice source panel grid differs")

    books = {}
    artifact_receipts = []
    for block, panel in zip(REGISTERED_BLOCKS, SOURCE_PANELS, strict=True):
        group = sources[sources.panel_run_id.astype(str).eq(panel)].copy()
        uris = group.score_artifact_uri.astype(str).unique()
        digests = group.score_artifact_sha256.astype(str).unique()
        if group.empty or len(uris) != 1 or len(digests) != 1:
            raise RuntimeError("constraint-lattice native source identity differs")
        artifact, receipt = _download_artifact(gcs, uris[0], digests[0])
        books[block] = _candidate_batch(group, artifact, catalog)
        artifact_receipts.append({
            "block": block,
            "source_panel": panel,
            "candidate_rows": len(group),
            **receipt,
        })

    result = run_scorefree_slate(
        books,
        season=season,
        week=week,
        expected_worlds_per_block=10_000,
        progress_callback=lambda block: print(
            "CONSTRAINT_LATTICE_FOLD_COMPLETE",
            season,
            week,
            block,
            flush=True,
        ),
    )
    payload = {
        "version": "constraint-lattice-scorefree-shard-v1",
        "run_id": RUN_ID,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "season": season,
        "week": week,
        "code_sha": code_sha,
        "analysis_image": image,
        "source_hashes": source_hashes,
        "source_panels": list(SOURCE_PANELS),
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "protocol_receipt": protocol_receipt(),
        "artifact_receipts": artifact_receipts,
        "slate": result,
    }
    raw = (json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("CONSTRAINT_LATTICE_SHARD_RESULT " + json.dumps(upload, sort_keys=True))
    return {**payload, "output": upload}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--output-uri", required=True)
    args = parser.parse_args()
    run(args.season, args.week, args.output_uri)


if __name__ == "__main__":
    main()
