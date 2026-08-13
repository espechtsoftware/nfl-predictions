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
    parser.add_argument("--panel")
    parser.add_argument("--historical-panel")
    parser.add_argument("--selected-eval-panel")
    parser.add_argument(
        "--source", choices=("promoted", "staging"), required=True,
        help="The panel's immutable warehouse location.")
    args = parser.parse_args()
    single_panel = bool(args.panel)
    composite_panel = bool(args.historical_panel or args.selected_eval_panel)
    if single_panel == composite_panel:
        raise SystemExit(
            "ABORT: provide either --panel or both composite panel arguments")
    if composite_panel and not (
            args.historical_panel and args.selected_eval_panel):
        raise SystemExit(
            "ABORT: both --historical-panel and --selected-eval-panel are required")

    table = (
        f"{settings.predictions}.replay_candidates"
        if args.source == "promoted"
        else f"{settings.predictions}.replay_candidates_staging"
    )
    eligible = "AND research_eligible" if args.source == "promoted" else ""
    if single_panel:
        where = "panel_run_id = @panel"
        params = {"panel": args.panel}
    else:
        where = (
            "(panel_run_id = @historical_panel "
            "OR panel_run_id = @selected_eval_panel)")
        params = {
            "historical_panel": args.historical_panel,
            "selected_eval_panel": args.selected_eval_panel,
        }
    rows = query_df(
        f"""
        SELECT panel_run_id, season, week, cand_ix, players, selected,
               selected_rank, n_worlds, tail_line, sim_mean,
               score_artifact_uri, score_artifact_sha256
        FROM `{table}`
        WHERE {where} {eligible}
        ORDER BY season, week, cand_ix
        """,
        params=params,
    )
    if rows.empty:
        raise SystemExit("ABORT: panel has no candidate rows")
    if single_panel:
        if rows.panel_run_id.nunique() != 1 or \
                str(rows.panel_run_id.iloc[0]) != args.panel:
            raise SystemExit("ABORT: panel identity differs")
        panel_identity = args.panel
        historical_panel = None
        selected_eval_panel = None
    else:
        historical_seasons = {2019, 2021, 2022}
        evaluation_seasons = {2023, 2024, 2025}
        source_panels = set(rows.panel_run_id.astype(str))
        expected_panels = {args.historical_panel, args.selected_eval_panel}
        if source_panels != expected_panels:
            raise SystemExit("ABORT: composite panel identity differs")
        historical_mask = (
            rows.panel_run_id.astype(str).eq(args.historical_panel)
            & rows.season.astype(int).isin(historical_seasons)
        )
        evaluation_mask = (
            rows.panel_run_id.astype(str).eq(args.selected_eval_panel)
            & rows.season.astype(int).isin(evaluation_seasons)
        )
        rows = rows.loc[historical_mask | evaluation_mask].copy()
        historical_mask = rows.panel_run_id.astype(str).eq(
            args.historical_panel)
        evaluation_mask = rows.panel_run_id.astype(str).eq(
            args.selected_eval_panel)
        if set(rows.loc[historical_mask, "season"].astype(int)) != \
                historical_seasons or \
                set(rows.loc[evaluation_mask, "season"].astype(int)) != \
                evaluation_seasons:
            raise SystemExit("ABORT: composite season coverage differs")
        panel_identity = "composite-terminal-incumbent-v1"
        historical_panel = args.historical_panel
        selected_eval_panel = args.selected_eval_panel

    slates = []
    for (season, week), group in rows.groupby(["season", "week"], sort=True):
        if group.panel_run_id.nunique() != 1:
            raise SystemExit(
                f"ABORT: {int(season)}w{int(week)} has multiple source panels")
        uris = group.score_artifact_uri.fillna("").astype(str).unique()
        hashes = group.score_artifact_sha256.fillna("").astype(str).unique()
        if len(uris) != 1 or len(hashes) != 1 or not uris[0] or not hashes[0]:
            raise SystemExit(
                f"ABORT: {int(season)}w{int(week)} lacks one artifact identity")
        artifact = decode_score_artifact(_download(uris[0]), hashes[0])
        slate = analyze_selected_book(group.copy(), artifact)
        slate["source_panel"] = str(group.panel_run_id.iloc[0])
        slates.append(slate)

    report = {
        "version": "v1" if single_panel else "v2",
        "panel": panel_identity,
        "historical_panel": historical_panel,
        "selected_eval_panel": selected_eval_panel,
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
