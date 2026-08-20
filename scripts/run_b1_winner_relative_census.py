#!/usr/bin/env python3
"""Run the source-locked winner-relative census over the frozen B1 union.

The outcome-facing execution is deliberately disabled until the protocol is
FROZEN and its exact SHA-256 is supplied.  ``--smoke`` uses only identities,
legality metadata and selected flags; it never selects ``actual`` or
``actual_score`` and exists to satisfy the real-artifact pre-freeze contract.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd
from google.cloud import bigquery

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_b1_union_c_census as b1  # noqa: E402

from nfl_dfs.analysis.winner_relative_union import (  # noqa: E402
    PROTOCOL_ID,
    WinnerRelativeUnionError,
    winner_relative_union_census,
)
from nfl_dfs.backtest.real_lines import REAL_LINES  # noqa: E402


PROJECT = "nfl-predictions-503414"
CANDIDATE_TABLE = f"{PROJECT}.nfl_predictions.replay_candidates_staging"
PLAYER_TABLE = f"{PROJECT}.nfl_predictions.slate_player_features"
PROTOCOL = ROOT / "reports/2026-08-20-b1-winner-relative-census-protocol.md"
B1_PROTOCOL = ROOT / "reports/2026-08-18-b1-union-c-census-protocol.md"
B1_REPORT = (
    ROOT / "reports/b1-union-c-census-runs/"
    "20260818-b1-union-c-census-v1/report.json"
)
B1_RUNNER = ROOT / "scripts/run_b1_union_c_census.py"
WINNER_LINES_SOURCE = ROOT / "src/nfl_dfs/backtest/real_lines.py"

B1_PROTOCOL_SHA256 = (
    "2d1cb29bda5fc25965661acb891566bd8e9daf108bb579ad9eca99d862c29789"
)
B1_REPORT_SHA256 = (
    "4e654a58563391ed3020b0b221756070cd07fb10e962fc80e4bbedfd5f2631b6"
)
B1_RUNNER_SHA256 = (
    "fc12e2871d638995603258f16d9e1beeee68f8a885ba3a53f9f32790d62c608f"
)
WINNER_LINES_SHA256 = (
    "13b7a7a1647fe9070b1e8583c9fc579c8fe882b1124e85eaa53d587de2759eb5"
)
EXPECTED_PANELS = 51
EXPECTED_SLATES = 54
EXPECTED_DISTINCT_LEGAL_ROSTERS = 127_778
EXPECTED_WINNER_SLATES = 51


CANDIDATE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, tag, all_tags,
       selected, selected_rank, players, actual_score, labels_complete
FROM `{CANDIDATE_TABLE}`
WHERE panel_run_id IN UNNEST(@panels)
ORDER BY panel_run_id, season, week, cand_ix
"""

PLAYER_SQL = f"""
SELECT season, week, id, name, pos, team, opp, game_id, salary, actual
FROM `{PLAYER_TABLE}`
WHERE panel_run_id = @panel
ORDER BY season, week, id
"""

CANDIDATE_SMOKE_SQL = f"""
SELECT panel_run_id, season, week, cand_ix, tag, all_tags,
       selected, selected_rank, players, labels_complete
FROM `{CANDIDATE_TABLE}`
WHERE panel_run_id IN UNNEST(@panels)
  AND season = @season AND week = @week
ORDER BY panel_run_id, cand_ix
"""

PLAYER_SMOKE_SQL = f"""
SELECT season, week, id, name, pos, team, opp, game_id, salary
FROM `{PLAYER_TABLE}`
WHERE panel_run_id = @panel
  AND season = @season AND week = @week
ORDER BY id
"""


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _require_hash(path: Path, expected: str) -> None:
    observed = _sha(path)
    if observed != expected:
        raise WinnerRelativeUnionError(
            f"source pin differs for {path}: expected {expected}, got {observed}")


def _panel_families() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for family, panels in b1.FAMILIES.items():
        for panel in panels:
            if panel in mapping:
                raise WinnerRelativeUnionError(
                    f"B1 panel appears in two source families: {panel}")
            mapping[panel] = family
    for panel in b1.SINGLES:
        if panel in mapping:
            raise WinnerRelativeUnionError(
                f"B1 singleton also appears in a family: {panel}")
        mapping[panel] = f"singleton:{panel}"
    if set(mapping) != set(b1.ALL_PANELS) or len(mapping) != EXPECTED_PANELS:
        raise WinnerRelativeUnionError(
            "B1 panel/family map differs from the frozen 51-panel population")
    return mapping


def _query(
    client: bigquery.Client,
    sql: str,
    parameters: list[bigquery.QueryParameter],
) -> tuple[pd.DataFrame, dict[str, Any]]:
    job = client.query(
        sql,
        job_config=bigquery.QueryJobConfig(query_parameters=parameters),
    )
    result = job.result()
    frame = result.to_dataframe(create_bqstorage_client=False)
    return frame, {
        "job_id": job.job_id,
        "location": job.location,
        "created": job.created.isoformat() if job.created else None,
        "started": job.started.isoformat() if job.started else None,
        "ended": job.ended.isoformat() if job.ended else None,
        "total_bytes_processed": int(job.total_bytes_processed or 0),
        "query_sha256": hashlib.sha256(sql.encode()).hexdigest(),
    }


def _stable_value(value: Any) -> Any:
    if value is None or pd.isna(value):
        return None
    if isinstance(value, (bool, str, int, float)):
        return value
    if hasattr(value, "item"):
        return value.item()
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _frame_sha(frame: pd.DataFrame, order: list[str]) -> str:
    missing = set(order) - set(frame.columns)
    if missing:
        raise WinnerRelativeUnionError(
            f"cannot hash frame; columns absent: {sorted(missing)}")
    digest = hashlib.sha256()
    ordered = frame.sort_values(order, kind="stable").reset_index(drop=True)
    digest.update(json.dumps(list(ordered.columns), separators=(",", ":")).encode())
    digest.update(b"\n")
    for row in ordered.itertuples(index=False, name=None):
        digest.update(json.dumps(
            [_stable_value(value) for value in row],
            sort_keys=True, separators=(",", ":"), allow_nan=False,
        ).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def _table_metadata(client: bigquery.Client, table_name: str) -> dict[str, Any]:
    table = client.get_table(table_name)
    return {
        "table": table_name,
        "etag": table.etag,
        "modified": table.modified.isoformat() if table.modified else None,
        "num_rows_at_read": int(table.num_rows or 0),
    }


def _parse_slate(value: str) -> tuple[int, int]:
    try:
        season, week = (int(part) for part in value.split(":"))
    except Exception as exc:
        raise argparse.ArgumentTypeError("smoke slate must be SEASON:WEEK") from exc
    return season, week


def _run_smoke(
    client: bigquery.Client,
    panel_families: dict[str, str],
    slate: tuple[int, int],
    receipt: Path,
) -> int:
    season, week = slate
    common = [
        bigquery.ArrayQueryParameter("panels", "STRING", sorted(panel_families)),
        bigquery.ScalarQueryParameter("season", "INT64", season),
        bigquery.ScalarQueryParameter("week", "INT64", week),
    ]
    candidates, cand_job = _query(client, CANDIDATE_SMOKE_SQL, common)
    players, player_job = _query(client, PLAYER_SMOKE_SQL, [
        bigquery.ScalarQueryParameter("panel", "STRING", b1.CANONICAL_PANEL),
        bigquery.ScalarQueryParameter("season", "INT64", season),
        bigquery.ScalarQueryParameter("week", "INT64", week),
    ])
    if candidates.empty or players.empty:
        raise WinnerRelativeUnionError("real-artifact smoke returned an empty source")
    if not candidates.labels_complete.fillna(False).astype(bool).all():
        raise WinnerRelativeUnionError("smoke found an incomplete-label B1 row")
    if candidates.duplicated(
            ["panel_run_id", "season", "week", "cand_ix"]).any():
        raise WinnerRelativeUnionError("smoke found duplicate candidate identities")
    catalog_ids = set(players.id.astype(str))
    roster_ids: set[str] = set()
    bad_rosters = 0
    for value in candidates.players:
        ids = [part for part in str(value).split(",") if part]
        if len(ids) != 9 or len(set(ids)) != 9:
            bad_rosters += 1
        roster_ids.update(ids)
    if bad_rosters or not roster_ids.issubset(catalog_ids):
        raise WinnerRelativeUnionError(
            "smoke found malformed/unmatched generated roster identities")
    if candidates.selected.isna().any() or candidates.selected_rank.isna().any():
        raise WinnerRelativeUnionError("smoke found missing selected metadata")
    selected = candidates[candidates.selected.astype(bool)]
    if (pd.to_numeric(selected.selected_rank, errors="raise") < 0).any():
        raise WinnerRelativeUnionError("smoke found invalid selected rank")
    record = {
        "status": "OUTCOME_BLIND_REALITY_SMOKE_OK",
        "protocol_id": PROTOCOL_ID,
        "season": season,
        "week": week,
        "candidate_rows": len(candidates),
        "panels_present": int(candidates.panel_run_id.nunique()),
        "selected_rows": len(selected),
        "catalog_rows": len(players),
        "candidate_query_job_id": cand_job["job_id"],
        "player_query_job_id": player_job["job_id"],
        "realized_outcome_columns_read": [],
    }
    payload = json.dumps(
        record, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()
    receipt.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    sha_path = receipt.with_suffix(receipt.suffix + ".sha256")
    with receipt.open("xb") as handle:
        handle.write(payload)
    try:
        with sha_path.open("x") as handle:
            handle.write(digest + "\n")
    except Exception:
        receipt.unlink(missing_ok=True)
        raise
    print(json.dumps({
        **record,
        "receipt": str(receipt),
        "receipt_sha256": digest,
    }, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", type=_parse_slate)
    parser.add_argument("--smoke-receipt", type=Path)
    parser.add_argument("--protocol-frozen", action="store_true")
    parser.add_argument("--protocol-sha256")
    args = parser.parse_args(argv)
    if bool(args.smoke) == bool(args.output):
        parser.error("choose exactly one of --smoke or --output")
    if bool(args.smoke) != bool(args.smoke_receipt):
        parser.error("--smoke and --smoke-receipt are required together")

    _require_hash(B1_PROTOCOL, B1_PROTOCOL_SHA256)
    _require_hash(B1_REPORT, B1_REPORT_SHA256)
    _require_hash(B1_RUNNER, B1_RUNNER_SHA256)
    panel_families = _panel_families()
    client = bigquery.Client(project=PROJECT)
    if args.smoke:
        return _run_smoke(client, panel_families, args.smoke, args.smoke_receipt)

    if not args.protocol_frozen or not args.protocol_sha256:
        parser.error(
            "outcome-facing execution requires --protocol-frozen and the "
            "exact --protocol-sha256")
    protocol_text = PROTOCOL.read_text()
    protocol_sha = _sha(PROTOCOL)
    if protocol_sha != args.protocol_sha256:
        raise WinnerRelativeUnionError(
            f"protocol SHA differs: expected {args.protocol_sha256}, got {protocol_sha}")
    if "**Status:** FROZEN" not in protocol_text:
        raise WinnerRelativeUnionError(
            "protocol document is not marked FROZEN")
    _require_hash(WINNER_LINES_SOURCE, WINNER_LINES_SHA256)

    candidates, cand_job = _query(client, CANDIDATE_SQL, [
        bigquery.ArrayQueryParameter("panels", "STRING", sorted(panel_families)),
    ])
    players, player_job = _query(client, PLAYER_SQL, [
        bigquery.ScalarQueryParameter("panel", "STRING", b1.CANONICAL_PANEL),
    ])
    if not candidates.labels_complete.fillna(False).astype(bool).all():
        raise WinnerRelativeUnionError(
            "frozen B1 extract contains incomplete candidate labels")
    report = winner_relative_union_census(
        candidates.drop(columns=["labels_complete"]),
        players,
        REAL_LINES,
        panel_families,
        expected_panels=sorted(panel_families),
        expected_slates=EXPECTED_SLATES,
        expected_distinct_legal_rosters=EXPECTED_DISTINCT_LEGAL_ROSTERS,
        expected_winner_slates=EXPECTED_WINNER_SLATES,
    )
    report["source_lock"] = {
        "executed_at": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": protocol_sha,
        "b1_protocol_sha256": B1_PROTOCOL_SHA256,
        "b1_report_sha256": B1_REPORT_SHA256,
        "b1_runner_sha256": B1_RUNNER_SHA256,
        "winner_lines_sha256": WINNER_LINES_SHA256,
        "canonical_snapshot_panel": b1.CANONICAL_PANEL,
        "candidate_extract": {
            **cand_job,
            **_table_metadata(client, CANDIDATE_TABLE),
            "rows": len(candidates),
            "content_sha256": _frame_sha(
                candidates,
                ["panel_run_id", "season", "week", "cand_ix"],
            ),
        },
        "player_extract": {
            **player_job,
            **_table_metadata(client, PLAYER_TABLE),
            "rows": len(players),
            "content_sha256": _frame_sha(
                players, ["season", "week", "id"]),
        },
    }

    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":"), allow_nan=False,
    ).encode()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(payload).hexdigest()
    sha_path = args.output.with_suffix(args.output.suffix + ".sha256")
    with args.output.open("xb") as handle:
        handle.write(payload)
    try:
        with sha_path.open("x") as handle:
            handle.write(digest + "\n")
    except Exception:
        args.output.unlink(missing_ok=True)
        raise
    print(json.dumps({
        "status": "B1_WINNER_RELATIVE_CENSUS_COMPLETE",
        "protocol_id": PROTOCOL_ID,
        "output": str(args.output),
        "sha256": digest,
        **report["summary"],
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
