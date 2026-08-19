#!/usr/bin/env python3
"""Run the winner structure census (protocol 20260819-winner-structure-census-v1).

Stack anatomy of the 51 tracked Milly winners versus every registered
candidate and every selected book on the 54-slate corpus, plus the
eight-constructible-winners forensic. Pure roster structure — no
realized score, ownership, or simulated total is read — so this census
is safe to run while an outcome-reading arm is in flight.

Inputs:
  --n1c-report  frozen winner-world-optima report (rosters + legality)
  --n1-report   frozen winner-law-audit report (generating-world ranks)
  --anatomy     frozen winner-anatomy report (pool overlap, omissions)
  --features    immutable slate-player snapshot parquet/csv
  --opp-map     season/week/team/opp parquet
  --output      report JSON path (created exclusively)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_atlas_minimal_world_selection_c as base  # noqa: E402

from nfl_dfs.analysis.winner_structure_census import (  # noqa: E402
    PROTOCOL_ID,
    StructureCensusError,
    roster_structure,
    structure_census,
    structure_report,
)
from nfl_dfs.bq import query_df  # noqa: E402

CAND_SQL = """
SELECT season, week, players, selected
FROM `nfl-predictions-503414.nfl_predictions.replay_candidates_staging`
WHERE panel_run_id IN UNNEST(@panels)
"""


def _slate_maps(features: pd.DataFrame, opp_map: pd.DataFrame,
                season: int, week: int) -> tuple[dict, dict, dict]:
    rows = features[
        features.season.astype(int).eq(season)
        & features.week.astype(int).eq(week)
    ].drop_duplicates("id")
    if rows.empty:
        raise StructureCensusError(f"{season} week {week}: no snapshot rows")
    pos_of = dict(zip(rows.id.astype(str), rows.pos.astype(str).str.upper()))
    team_of = dict(zip(rows.id.astype(str), rows.team.astype(str)))
    scoped = opp_map[
        opp_map.season.astype(int).eq(season)
        & opp_map.week.astype(int).eq(week)]
    by_team = dict(zip(scoped.team.astype(str), scoped.opp.astype(str)))
    opp_of = {
        pid: by_team.get(team, "") for pid, team in team_of.items()
    }
    return pos_of, team_of, opp_of


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n1c-report", required=True, type=Path)
    parser.add_argument("--n1-report", required=True, type=Path)
    parser.add_argument("--anatomy", required=True, type=Path)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--opp-map", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", metavar="SEASON:WEEK")
    args = parser.parse_args(argv)
    if not args.smoke and args.output is None:
        parser.error("--output is required outside --smoke mode")

    n1c = json.loads(args.n1c_report.read_text())
    n1 = json.loads(args.n1_report.read_text())
    anatomy = json.loads(args.anatomy.read_text())
    features = (
        pd.read_parquet(args.features)
        if args.features.suffix == ".parquet" else pd.read_csv(args.features)
    )
    opp_map = pd.read_parquet(args.opp_map)
    candidates = query_df(
        CAND_SQL, params={"panels": list(base.SOURCE_PANEL_IDS)})

    slate_keys = sorted(
        {(int(w["season"]), int(w["week"])) for w in n1c["winners"]})
    if args.smoke:
        season, week = (int(x) for x in args.smoke.split(":"))
        slate_keys = [(season, week)]

    n1_by_slate = {
        (int(w["season"]), int(w["week"])): w for w in n1["winners"]}
    anatomy_by_slate = {
        (int(w["season"]), int(w["week"])): w for w in anatomy["winners"]}
    omitted_by_slate: dict[tuple[int, int], list[str]] = {}
    for record in anatomy.get("omitted_winner_players", []):
        key = (int(record["season"]), int(record["week"]))
        omitted_by_slate.setdefault(key, []).append(str(record.get("id")))

    winner_structs, pool_structs, selected_structs = [], [], []
    constructible_cases = []
    skipped_pool = 0
    for winner in sorted(
            n1c["winners"],
            key=lambda w: (int(w["season"]), int(w["week"]))):
        season, week = int(winner["season"]), int(winner["week"])
        if (season, week) not in slate_keys:
            continue
        pos_of, team_of, opp_of = _slate_maps(
            features, opp_map, season, week)
        w_struct = roster_structure(
            winner["roster_ids"], pos_of, team_of, opp_of)
        w_struct["season"], w_struct["week"] = season, week
        winner_structs.append(w_struct)

        slate_cands = candidates[
            candidates.season.astype(int).eq(season)
            & candidates.week.astype(int).eq(week)]
        if slate_cands.empty:
            raise StructureCensusError(
                f"{season} week {week}: no registered candidates")
        for row in slate_cands.itertuples(index=False):
            roster = [v for v in str(row.players).split(",") if v]
            try:
                struct = roster_structure(roster, pos_of, team_of, opp_of)
            except StructureCensusError:
                # A candidate references a player outside the snapshot
                # dedup (should not happen); count rather than die so one
                # stray row cannot kill a 67k-roster census — but report it.
                skipped_pool += 1
                continue
            pool_structs.append(struct)
            if bool(row.selected):
                selected_structs.append(struct)

        if bool(winner["solve"]["winner_production_valid"]):
            n1_row = n1_by_slate.get((season, week), {})
            anatomy_row = anatomy_by_slate.get((season, week), {})
            assignment = n1_row.get("world_assignment", {})
            constructible_cases.append({
                "season": season,
                "week": week,
                "structure": {
                    k: v for k, v in w_struct.items()
                    if k not in ("season", "week")},
                "pool_max_overlap": anatomy_row.get(
                    "overlap", {}).get("pool", {}).get("max_overlap"),
                "pool_max_minus_null": anatomy_row.get(
                    "overlap", {}).get("pool", {}).get("max_minus_null"),
                "players_missing_from_pool": omitted_by_slate.get(
                    (season, week), []),
                "n_generating_worlds": assignment.get(
                    "n_generating_worlds"),
                "best_generating_rank": assignment.get(
                    "best_rank_slate_total"),
                "winner_gap_to_world_optimum": winner["solve"]["legal_gap"],
            })

    if args.smoke:
        print(f"SMOKE_OK slate={slate_keys[0][0]}:{slate_keys[0][1]} "
              f"winner_structs={len(winner_structs)} "
              f"pool_structs={len(pool_structs)} "
              f"selected_structs={len(selected_structs)} "
              f"skipped={skipped_pool}")
        return 0

    report = structure_report(
        structure_census(winner_structs),
        structure_census(pool_structs),
        structure_census(selected_structs),
        constructible_cases,
    )
    report["skipped_pool_rosters"] = skipped_pool
    report["n_winner_slates"] = len(winner_structs)
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":")).encode()
    with args.output.open("xb") as handle:
        handle.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    print(
        "WINNER_STRUCTURE_CENSUS_COMPLETE",
        f"protocol={PROTOCOL_ID}",
        f"winners={len(winner_structs)}",
        f"output={args.output}",
        f"sha256={digest}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
