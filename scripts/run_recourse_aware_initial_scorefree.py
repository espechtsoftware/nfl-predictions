#!/usr/bin/env python3
"""Run one immutable, outcome-free recourse-aware initial-book slate shard."""

from __future__ import annotations

import argparse
from datetime import date, datetime, time, timedelta
import gc
from hashlib import sha256
import json
import os
from pathlib import Path
import re
from zoneinfo import ZoneInfo

from google.cloud import bigquery, storage
import pandas as pd

from nfl_dfs.analysis.constraint_lattice import (
    REGISTERED_BLOCKS,
    build_training_control,
)
from nfl_dfs.analysis.recourse_aware_initial import evaluate_scorefree_fold
from nfl_dfs.research.realistic_recourse_sizing import decision_instant

from run_cbwu_seed_order_audit import _query, _upload_create_only
from run_constraint_lattice_scorefree import (
    CBWU_REPORT_SHA256,
    FORENSIC_MANIFEST_SHA256,
    PLAYER_TABLE,
    SOURCE_PANELS,
    load_slate_sources,
    validate_local_sources as validate_lattice_sources,
)


PROJECT = "nfl-predictions-503414"
RUN_ID = "20260829-recourse-aware-initial-book-scorefree-kickoff-v3"
OUTPUT_PREFIX = (
    "gs://nfl-predictions-503414-raw/research/"
    f"recourse-aware-initial-book-runs/{RUN_ID}"
)
SCIENCE_PROTOCOL = Path(
    "reports/2026-08-17-recourse-aware-initial-book-scorefree-protocol.md"
)
SCIENCE_PROTOCOL_SHA256 = (
    "0085b5f77b4e859982fc4f664161cdafe2bb6ec07ea0351fb618ddf58319c077"
)
EXECUTION_PROTOCOL = Path(
    "reports/2026-08-17-recourse-aware-initial-book-execution-protocol.md"
)
EXECUTION_PROTOCOL_SHA256 = (
    "3991fdbf36c2018b2ec11625a6be62990c100fdf1f47bde3985c2327e3248c9b"
)
KICKOFF_POPULATION_AMENDMENT = Path(
    "reports/2026-08-29-recourse-aware-initial-book-"
    "kickoff-population-amendment.md"
)
KICKOFF_POPULATION_AMENDMENT_SHA256 = (
    "fec2d7f531cc3dea4a395fec5e02322ee46e88b43d00c09228a083470c4c69db"
)
KICKOFF_AMENDMENT = Path(
    "reports/2026-08-29-recourse-aware-initial-book-"
    "kickoff-time-reconstruction-amendment.md"
)
KICKOFF_AMENDMENT_SHA256 = (
    "89b2e5a5296bfbee5a4cebaf6f87bd091900fc79361c409a21214f28ac1edf64"
)
EASTERN = ZoneInfo("America/New_York")
SUNDAY_MAIN_WEEK1 = {
    2023: date(2023, 9, 10),
    2024: date(2024, 9, 8),
    2025: date(2025, 9, 7),
}
STRICT_KICKOFF_TIME = re.compile(r"(?:[01][0-9]|2[0-3]):[0-5][0-9]")
KICKOFF_SQL = f"""
SELECT manifest_sha256, player_id, kickoff_time
FROM `{PLAYER_TABLE}`
WHERE scope='phase-s-cbwu-54' AND season=@season AND week=@week
  AND player_id IN UNNEST(@player_ids)
ORDER BY player_id
"""
FORBIDDEN_QUERY_TOKENS = (
    "actual_score", "final_score", "actual_rank", "actual_ownership",
    "selected_rank", "contest_rank", "payout", "roi", "labels_complete",
)


def _file_sha(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def validate_local_sources() -> dict[str, str]:
    expected = {
        str(SCIENCE_PROTOCOL): SCIENCE_PROTOCOL_SHA256,
        str(EXECUTION_PROTOCOL): EXECUTION_PROTOCOL_SHA256,
        str(KICKOFF_POPULATION_AMENDMENT): (
            KICKOFF_POPULATION_AMENDMENT_SHA256
        ),
        str(KICKOFF_AMENDMENT): KICKOFF_AMENDMENT_SHA256,
    }
    for raw_path, digest in expected.items():
        path = Path(raw_path)
        if not path.is_file() or _file_sha(path) != digest:
            raise RuntimeError(f"recourse-aware frozen source differs: {path}")
    lattice = validate_lattice_sources()
    present = [
        token for token in FORBIDDEN_QUERY_TOKENS if token in KICKOFF_SQL.lower()
    ]
    if present:
        raise RuntimeError(
            "recourse-aware query contains forbidden fields: "
            + ", ".join(present)
        )
    return {**lattice, **expected}


def _sunday_main_date(season: int, week: int) -> date:
    if type(season) is not int or season not in SUNDAY_MAIN_WEEK1 or \
            type(week) is not int or week not in range(1, 19):
        raise RuntimeError("recourse-aware Sunday-main coordinate differs")
    return SUNDAY_MAIN_WEEK1[season] + timedelta(days=7 * (week - 1))


def _wall_clock_timestamp(raw: object, slate_date: date) -> pd.Timestamp:
    if type(raw) is not str or STRICT_KICKOFF_TIME.fullmatch(raw) is None:
        raise RuntimeError(
            "recourse-aware kickoff time is not strict HH:MM Eastern wall clock"
        )
    hour, minute = map(int, raw.split(":"))
    return pd.Timestamp(datetime.combine(
        slate_date, time(hour=hour, minute=minute), tzinfo=EASTERN,
    ))


def _slate_kickoffs(
    bq: bigquery.Client,
    *,
    season: int,
    week: int,
    expected_player_ids: set[str],
) -> tuple[dict[str, pd.Timestamp], pd.Timestamp]:
    ordered_player_ids = sorted(expected_player_ids)
    if (
        not ordered_player_ids
        or any(not player_id for player_id in ordered_player_ids)
        or len(ordered_player_ids) != len(expected_player_ids)
    ):
        raise RuntimeError("recourse-aware expected player population differs")
    params = [
        bigquery.ScalarQueryParameter("season", "INT64", int(season)),
        bigquery.ScalarQueryParameter("week", "INT64", int(week)),
        bigquery.ArrayQueryParameter(
            "player_ids", "STRING", ordered_player_ids,
        ),
    ]
    frame = _query(bq, KICKOFF_SQL, params)
    if frame.empty or frame.player_id.astype(str).duplicated().any() or \
            set(frame.manifest_sha256.astype(str)) != {
                FORENSIC_MANIFEST_SHA256
            } or set(frame.player_id.astype(str)) != expected_player_ids:
        raise RuntimeError("recourse-aware kickoff population differs")
    slate_date = _sunday_main_date(season, week)
    stamps = [
        _wall_clock_timestamp(raw, slate_date)
        for raw in frame.kickoff_time.tolist()
    ]
    kickoffs = {
        str(player_id): pd.Timestamp(stamp)
        for player_id, stamp in zip(frame.player_id, stamps, strict=True)
    }
    local_dates = {
        value.tz_convert("America/New_York").date() for value in kickoffs.values()
    }
    if local_dates != {slate_date}:
        raise RuntimeError("recourse-aware kickoff has multi-date ambiguity")
    decision = decision_instant(slate_date)
    if not any(value <= decision for value in kickoffs.values()) or \
            not any(value > decision for value in kickoffs.values()):
        raise RuntimeError("recourse-aware decision lacks early/late games")
    return kickoffs, decision


def run(
    season: int,
    week: int,
    output_uri: str,
    *,
    run_id: str = RUN_ID,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict:
    expected_uri = f"{output_prefix}/slate-{season}-{week}.json"
    if season not in {2023, 2024, 2025} or week not in range(1, 19) or \
            output_uri != expected_uri or run_id != RUN_ID:
        raise RuntimeError("recourse-aware shard identity differs")
    source_hashes = validate_local_sources()
    code_sha = os.environ.get("CODE_SHA", "").strip()
    image = os.environ.get("ANALYSIS_IMAGE", "").strip()
    if not re.fullmatch(r"[0-9a-f]{40}", code_sha) or not re.fullmatch(
        r".+@sha256:[0-9a-f]{64}", image,
    ):
        raise RuntimeError("recourse-aware code/image identity is required")

    bq = bigquery.Client(project=PROJECT)
    gcs = storage.Client(project=PROJECT)
    books, artifact_receipts = load_slate_sources(
        bq, gcs, season=season, week=week,
    )
    player_ids = {str(value) for value in books["R0"].player_ids}
    kickoffs, decision = _slate_kickoffs(
        bq,
        season=season,
        week=week,
        expected_player_ids=player_ids,
    )

    folds = []
    for block in REGISTERED_BLOCKS:
        control = build_training_control(
            books,
            block,
            expected_worlds_per_block=10_000,
        )
        fold = evaluate_scorefree_fold(control, kickoffs, decision)
        fold["season"] = int(season)
        fold["week"] = int(week)
        folds.append(fold)
        del control
        gc.collect()
        print("RECOURSE_INITIAL_FOLD_COMPLETE", season, week, block, flush=True)

    if len(folds) != 5 or {row["heldout_block"] for row in folds} != set(
        REGISTERED_BLOCKS
    ):
        raise RuntimeError("recourse-aware shard fold grid differs")
    payload = {
        "version": "recourse-aware-initial-book-scorefree-shard-v1",
        "run_id": run_id,
        "uses_realized_outcomes": False,
        "production_change_licensed": False,
        "historical_scoring_licensed": False,
        "season": int(season),
        "week": int(week),
        "code_sha": code_sha,
        "analysis_image": image,
        "source_hashes": source_hashes,
        "source_panels": list(SOURCE_PANELS),
        "forensic_manifest_sha256": FORENSIC_MANIFEST_SHA256,
        "cbwu_report_sha256": CBWU_REPORT_SHA256,
        "decision_time": decision.isoformat(),
        "artifact_receipts": artifact_receipts,
        "folds": folds,
    }
    raw = (
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n"
    ).encode()
    upload = _upload_create_only(gcs, output_uri, raw)
    print("RECOURSE_INITIAL_SHARD_RESULT " + json.dumps(upload, sort_keys=True))
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
