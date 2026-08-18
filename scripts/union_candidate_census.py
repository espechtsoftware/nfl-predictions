#!/usr/bin/env python3
"""Run the all-arms union candidate census (B1).

Execution is gated on the operator freezing
reports/2026-08-18-all-arms-union-census-protocol.md (this script refuses
to run without --protocol-frozen). Outcome-facing and diagnostic-only: it
measures the union candidate ceiling over every registered panel's
rosters, revalidated and revalued under the corrected snapshots; it
licenses no adoption, promotion, or production change.

Inputs are two extracts (parquet/csv) so the census itself stays
deterministic and re-runnable from retained files:
  --candidates  season, week, panel_run_id, players, actual_score
                (all panels, mechanical inclusion — the extract query
                must not filter by arm)
  --players     corrected slate snapshots: season, week, id, pos, team,
                opp, game_id, salary, actual
  --anchors     optional JSON of named mean-C comparison anchors
  --output      report JSON path (create-only)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs.research.all_arms_union import (  # noqa: E402
    PROTOCOL_ID,
    THRESHOLDS,
    UnionCensusError,
    slate_union_census,
    union_census_report,
)


def _load(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", required=True, type=Path)
    parser.add_argument("--players", required=True, type=Path)
    parser.add_argument("--anchors", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--protocol-frozen", action="store_true",
        help="assert the operator has frozen the census protocol; "
             "execution refuses to proceed without it")
    args = parser.parse_args(argv)
    if not args.protocol_frozen:
        parser.error(
            "outcome-facing census requires --protocol-frozen after the "
            "operator freezes the protocol document")

    candidates = _load(args.candidates)
    players = _load(args.players)
    anchors = (
        json.loads(args.anchors.read_text()) if args.anchors else None)

    rows = []
    slates = candidates[["season", "week"]].drop_duplicates()
    for slate in slates.itertuples(index=False):
        season, week = int(slate.season), int(slate.week)
        slate_players = players[
            players.season.eq(season) & players.week.eq(week)]
        if slate_players.empty:
            raise UnionCensusError(
                f"{season} week {week}: no corrected snapshot rows")
        census = slate_union_census(
            candidates[candidates.season.eq(season)
                       & candidates.week.eq(week)],
            slate_players.drop(columns=["season", "week"]),
        )
        row = {"season": season, "week": week, **{
            k: v for k, v in census.items() if k != "thresholds"}}
        for t in THRESHOLDS:
            row[f"clears_{t}"] = census["thresholds"][str(t)]
        rows.append(row)

    frame = pd.DataFrame(rows).sort_values(["season", "week"])
    report = union_census_report(frame, comparison=anchors)
    report["per_slate"] = frame.to_dict(orient="records")
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":"),
        default=str).encode()
    with args.output.open("xb") as handle:
        handle.write(payload)
    print(
        "ALL_ARMS_UNION_CENSUS_COMPLETE",
        f"protocol={PROTOCOL_ID}",
        f"slates={report['n_slates']}",
        f"union_c_mean={report['union_c_mean']:.3f}",
        f"output={args.output}",
        f"sha256={hashlib.sha256(payload).hexdigest()}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
