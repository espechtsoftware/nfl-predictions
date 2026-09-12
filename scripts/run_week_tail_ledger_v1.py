#!/usr/bin/env python3
"""Write one post-settlement week tail ledger row (state audit §5.1).

Reads the published Week-N A5 book terminal by run id, exact-reopens every
book by its pinned identity, loads the candidate pools the books were drawn
from, joins realized DK points by internal player id, and writes a single
self-hashed ledger row to a create-only local path.  The row is an
observation: it licenses no adoption or allocation change.

Realized actuals come from the warehouse (``player_week_actuals`` and
``team_defense_week``) only after every represented game's latest play-by-play
row is an end-of-game marker; or from a caller-supplied JSON file, which is
for reality-contact smokes and is labelled as such in the row's identities.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import io
import json
from pathlib import Path
import re
import sys

import pandas as pd

from nfl_dfs.inference.prospective_generation_shadow_operator import (
    GCSImmutableObjectStore,
)
from nfl_dfs.research import week_tail_ledger_v1 as ledger
from nfl_dfs.research.object_identity import live_object_receipt

PUBLISH_ROOT = "gs://nfl-predictions-503414-raw/week1/prelock/2026-w01/a5-books"
POOL_SOURCES = ("D800_DEMAX", "D400_DEMAX")
_RUN_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,79}\Z")
_END_GAME = re.compile(r"^end( of)? game$")


def _identity_of(receipt: dict) -> dict:
    return {key: receipt[key] for key in ("uri", "generation", "sha256", "bytes")}


def _read_live(client, uri: str) -> tuple[dict, bytes]:
    receipt, raw = live_object_receipt(client, uri)
    return _identity_of(receipt), raw


def _actuals_from_bigquery(project: str, season: int, week: int, game_ids: set):
    from google.cloud import bigquery

    client = bigquery.Client(project=project)
    params = [
        bigquery.ScalarQueryParameter("season", "INT64", season),
        bigquery.ScalarQueryParameter("week", "INT64", week),
        bigquery.ArrayQueryParameter("games", "STRING", sorted(game_ids)),
    ]
    finality = client.query(
        f"""
        WITH latest AS (
          SELECT CAST(game_id AS STRING) AS game_id,
                 ARRAY_AGG(`desc` ORDER BY play_id DESC LIMIT 1)[OFFSET(0)] AS d
          FROM `{project}.nfl_raw.pbp`
          WHERE season = @season AND week = @week
            AND CAST(game_id AS STRING) IN UNNEST(@games)
          GROUP BY game_id
        )
        SELECT g AS game_id, l.d AS terminal_desc
        FROM UNNEST(@games) AS g LEFT JOIN latest l ON l.game_id = g
        """,
        job_config=bigquery.QueryJobConfig(query_parameters=params),
    ).result()
    not_final = [
        row.game_id for row in finality
        if not _END_GAME.match((row.terminal_desc or "").strip().lower())
    ]
    if not_final:
        raise SystemExit(f"games not final in play-by-play: {sorted(not_final)}")
    skill = client.query(
        f"""
        SELECT CAST(gsis_id AS STRING) AS internal_id, dk_points
        FROM `{project}.nfl_features.player_week_actuals`
        WHERE season = @season AND week = @week
        """,
        job_config=bigquery.QueryJobConfig(query_parameters=params[:2]),
    ).result()
    dst = client.query(
        f"""
        SELECT CONCAT(UPPER(CAST(team AS STRING)), '_DST') AS internal_id,
               dst_dk_points AS dk_points
        FROM `{project}.nfl_features.team_defense_week`
        WHERE season = @season AND week = @week
        """,
        job_config=bigquery.QueryJobConfig(query_parameters=params[:2]),
    ).result()
    actuals = {}
    for row in list(skill) + list(dst):
        if row.dk_points is None:
            continue
        if row.internal_id in actuals:
            raise SystemExit(f"duplicate actual for {row.internal_id}")
        actuals[row.internal_id] = float(row.dk_points)
    source = {
        "producer_class": "warehouse-player-and-dst-actuals",
        "tables": [
            f"{project}.nfl_features.player_week_actuals",
            f"{project}.nfl_features.team_defense_week",
        ],
        "finality_rule": "latest pbp row per represented game is an end-game marker",
        "represented_games": sorted(game_ids),
    }
    return actuals, source


def _actuals_from_json(path: Path) -> tuple[dict, dict]:
    raw = path.read_bytes()
    payload = json.loads(raw)
    if set(payload) != {"actual_by_internal_id", "producer_class"}:
        raise SystemExit("actuals JSON must carry actual_by_internal_id/producer_class")
    source = {
        "producer_class": str(payload["producer_class"]),
        "file": str(path),
        "sha256": sha256(raw).hexdigest(),
        "bytes": len(raw),
    }
    return dict(payload["actual_by_internal_id"]), source


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--publish-root", default=PUBLISH_ROOT)
    parser.add_argument("--season", type=int, required=True)
    parser.add_argument("--week", type=int, required=True)
    parser.add_argument("--captured-at", required=True)
    parser.add_argument("--actuals-source", choices=("bigquery", "json"), required=True)
    parser.add_argument("--actuals-json", type=Path)
    parser.add_argument("--bigquery-project", default="nfl-predictions-503414")
    parser.add_argument("--winner-score", type=float)
    parser.add_argument("--winner-source")
    parser.add_argument("--winner-contest-id")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    if not _RUN_ID.match(args.run_id):
        raise SystemExit("run id must be lowercase [a-z0-9-], at most 80 characters")
    if args.output.exists():
        raise SystemExit(f"output exists; ledger rows are create-only: {args.output}")
    if args.actuals_source == "json" and args.actuals_json is None:
        raise SystemExit("--actuals-json is required with --actuals-source json")
    winner = None
    if any(v is not None for v in (args.winner_score, args.winner_source,
                                    args.winner_contest_id)):
        if None in (args.winner_score, args.winner_source, args.winner_contest_id):
            raise SystemExit("winner needs --winner-score, --winner-source and "
                             "--winner-contest-id together")
        winner = {"score": args.winner_score, "source": args.winner_source,
                  "contest_id": args.winner_contest_id}

    from google.cloud import storage

    client = storage.Client()
    store = GCSImmutableObjectStore(client)
    root = f"{args.publish_root.rstrip('/')}/{args.run_id}"
    identities: dict[str, dict] = {}
    terminal_identity, terminal_raw = _read_live(client, f"{root}/terminal.json")
    identities["terminal"] = terminal_identity
    terminal = json.loads(terminal_raw)
    if (terminal.get("season"), terminal.get("week")) != (args.season, args.week):
        raise SystemExit("terminal season/week differ from the requested week")

    books: dict[str, list] = {}
    for book_id, ref in sorted(terminal["books"].items()):
        reopened = store.read_exact(identity=ref["artifact_identity"])
        book = json.loads(reopened["raw"])
        if book.get("policy") != book_id:
            raise SystemExit(f"book {book_id} policy label differs")
        identities[f"book:{book_id}"] = dict(ref["artifact_identity"])
        books[book_id] = list(book["entries"])

    pools: dict[str, list] = {}
    game_ids: set[str] = set()
    for source in POOL_SOURCES:
        identity, raw = _read_live(
            client, f"{root}/sources/{source}/candidates.parquet"
        )
        identities[f"pool:{source}"] = identity
        candidates = pd.read_parquet(io.BytesIO(raw))
        pools[source] = [str(row).split(",") for row in candidates["players"]]
        identity, raw = _read_live(client, f"{root}/sources/{source}/frame.parquet")
        identities[f"frame:{source}"] = identity
        frame = pd.read_parquet(io.BytesIO(raw))
        game_ids.update(str(value) for value in frame["game_id"].dropna().unique())

    if args.actuals_source == "bigquery":
        actuals, actual_source = _actuals_from_bigquery(
            args.bigquery_project, args.season, args.week, game_ids
        )
    else:
        actuals, actual_source = _actuals_from_json(args.actuals_json)

    row = ledger.build_week_tail_ledger_row_v1(
        season=args.season,
        week=args.week,
        slate_id=str(terminal["slate_id"]),
        lock_utc=str(terminal["lock_utc"]),
        captured_at=args.captured_at,
        books=books,
        pools=pools,
        actual_by_internal_id=actuals,
        input_identities=identities,
        winner=winner,
    )
    ledger.validate_week_tail_ledger_row_v1(row)
    document = {
        "row": row,
        "actual_source": actual_source,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "run_id": args.run_id,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(document, handle, indent=1, sort_keys=True)
        handle.write("\n")
    summary = {
        "pools": {
            p["pool_id"]: {"max": p["max"], **p["tail_counts"]} for p in row["pools"]
        },
        "books": {
            b["book_id"]: {"max": b["max"], **b["tail_counts"]} for b in row["books"]
        },
        "winner": None if row["winner"] is None else row["winner"]["score"],
        "row_sha256": row["row_sha256"],
        "output": str(args.output),
    }
    print(json.dumps(summary, sort_keys=True))


if __name__ == "__main__":
    sys.exit(main())
