#!/usr/bin/env python3
"""Analyze simulator-implied diversity of an immutable selected panel."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from google.cloud import storage  # noqa: E402

from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402
from nfl_dfs.analysis.g1_archetype_topology import (  # noqa: E402
    encode_report_transport,
)
from nfl_dfs.research.portfolio_effective_rank import (  # noqa: E402
    analyze_selected_book,
    decode_score_artifact,
)


META_PREFIX = "PORTFOLIO_EFFECTIVE_RANK_META="
CHUNK_PREFIX = "PORTFOLIO_EFFECTIVE_RANK_CHUNK="


def _download(uri: str) -> bytes:
    bucket, separator, path = uri.removeprefix("gs://").partition("/")
    if not separator or not bucket or not path:
        raise ValueError(f"invalid score artifact URI {uri!r}")
    return storage.Client().bucket(bucket).blob(path).download_as_bytes()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--panel", required=True)
    parser.add_argument(
        "--source", choices=("promoted", "staging"), required=True,
        help="The panel's immutable warehouse location.")
    args = parser.parse_args()
    table = (
        f"{settings.predictions}.replay_candidates"
        if args.source == "promoted"
        else f"{settings.predictions}.replay_candidates_staging"
    )
    eligible = "AND research_eligible" if args.source == "promoted" else ""
    rows = query_df(
        f"""
        SELECT panel_run_id, season, week, cand_ix, players, selected,
               selected_rank, n_worlds, tail_line, sim_mean,
               score_artifact_uri, score_artifact_sha256
        FROM `{table}`
        WHERE panel_run_id = @panel {eligible}
        ORDER BY season, week, cand_ix
        """,
        params={"panel": args.panel},
    )
    if rows.empty:
        raise SystemExit("ABORT: panel has no candidate rows")
    if rows.panel_run_id.nunique() != 1 or str(rows.panel_run_id.iloc[0]) != args.panel:
        raise SystemExit("ABORT: panel identity differs")

    slates = []
    for (season, week), group in rows.groupby(["season", "week"], sort=True):
        uris = group.score_artifact_uri.fillna("").astype(str).unique()
        hashes = group.score_artifact_sha256.fillna("").astype(str).unique()
        if len(uris) != 1 or len(hashes) != 1 or not uris[0] or not hashes[0]:
            raise SystemExit(
                f"ABORT: {int(season)}w{int(week)} lacks one artifact identity")
        artifact = decode_score_artifact(_download(uris[0]), hashes[0])
        slates.append(analyze_selected_book(group.copy(), artifact))

    report = {
        "version": "v1",
        "panel": args.panel,
        "source": args.source,
        "slates": slates,
        "slate_count": len(slates),
        "simulator_implied_only": True,
        "reads_realized_outcomes": False,
    }
    meta, chunks = encode_report_transport(report)
    print(META_PREFIX + json.dumps(meta, separators=(",", ":"), sort_keys=True))
    for index, chunk in enumerate(chunks):
        print(f"{CHUNK_PREFIX}{index}/{len(chunks)}:{chunk}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
