#!/usr/bin/env python3
"""Run the winner-world optima audit (protocol 20260819-winner-world-optima-v1).

For each tracked Milly winner in the frozen N1 report, recompute its best
generating world from the archived artifacts (cross-checked against the
report's recorded margin), then solve that world to exact optimality
under DraftKings-legal and production-contract constraints and place the
winner against both optima. Sim-side only: no realized score is read.

Runs exactly once per frozen protocol version after the operator-visible
freeze of reports/2026-08-19-winner-world-optima-protocol.md. The
--smoke mode is the outcome-blind reality check required before the
freeze: it exercises loading, frame construction, and both solvers on
one slate at a FIXED world (block 0, world 0 — chosen without reference
to any margin) and prints contract facts only.

Inputs:
  --report    frozen N1 report JSON (winner rosters + recorded margins)
  --features  immutable slate-player snapshot parquet/csv
  --opp-map   parquet of season/week/team/opp built from nfl_raw.schedules
  --manifest  JSON list of {"season", "week", "artifacts": [npz paths]}
  --output    report JSON path (created exclusively; never overwrites)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs.analysis.winner_law_audit import (  # noqa: E402
    winner_roster_world_totals,
)
from nfl_dfs.analysis.winner_world_optima import (  # noqa: E402
    PROTOCOL_ID,
    WinnerOptimaError,
    best_generating_world,
    solve_winner_world,
    winner_optima_report,
    world_player_frame,
)


def _load_block(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    with np.load(path) as artifact:
        keys = set(artifact.files)
        if not {"player_ids", "player_draws", "totals"} <= keys:
            raise WinnerOptimaError(
                f"{path} lacks player worlds/totals (keys: {sorted(keys)})")
        return (
            np.asarray(artifact["player_ids"], dtype=str),
            np.asarray(artifact["player_draws"], dtype=np.float64),
            np.asarray(artifact["totals"], dtype=np.float64),
        )


def _load_features(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _slate_opp(opp_map: pd.DataFrame, season: int, week: int) -> dict:
    scoped = opp_map[
        opp_map.season.astype(int).eq(season)
        & opp_map.week.astype(int).eq(week)
    ]
    if scoped.empty:
        raise WinnerOptimaError(
            f"{season} week {week}: no opponent mapping rows")
    mapping = dict(zip(scoped.team.astype(str), scoped.opp.astype(str)))
    for team, opp in mapping.items():
        if mapping.get(opp) != team:
            raise WinnerOptimaError(
                f"{season} week {week}: opponent map is not symmetric "
                f"for {team}/{opp}")
    return mapping


def _slate_rows(features: pd.DataFrame, season: int, week: int
                ) -> pd.DataFrame:
    scoped = features[
        features.season.astype(int).eq(season)
        & features.week.astype(int).eq(week)
    ]
    if scoped.empty:
        raise WinnerOptimaError(f"{season} week {week}: no snapshot rows")
    return scoped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--opp-map", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--smoke", metavar="SEASON:WEEK",
        help="outcome-blind contract smoke on one slate (no margins, "
             "no winner gaps; fixed block 0 world 0)")
    args = parser.parse_args(argv)
    if not args.smoke and args.output is None:
        parser.error("--output is required outside --smoke mode")

    n1_report = json.loads(args.report.read_text())
    manifest = json.loads(args.manifest.read_text())
    by_slate = {
        (int(m["season"]), int(m["week"])): [Path(p) for p in m["artifacts"]]
        for m in manifest
    }
    features = _load_features(args.features)
    opp_map = pd.read_parquet(args.opp_map)

    if args.smoke:
        season, week = (int(x) for x in args.smoke.split(":"))
        winner = next(
            (w for w in n1_report["winners"]
             if int(w["season"]) == season and int(w["week"]) == week),
            None)
        if winner is None:
            raise WinnerOptimaError(f"{season} week {week}: not in report")
        artifacts = by_slate[(season, week)]
        ids, draws, totals = _load_block(artifacts[0])
        frame = world_player_frame(
            _slate_rows(features, season, week),
            _slate_opp(opp_map, season, week),
            ids, draws[:, 0])
        solve = solve_winner_world(frame, winner["roster_ids"])
        print(f"SMOKE_OK slate={season}:{week} universe={len(ids)}")
        print(f"SMOKE_OK candidates={totals.shape[0]} "
              f"worlds_per_block={draws.shape[1]} blocks={len(artifacts)}")
        print(f"SMOKE_OK winner_resolved=9 "
              f"winner_dk_legal={solve['winner_dk_legal_in_snapshot']} "
              f"winner_production_valid={solve['winner_production_valid']} "
              f"winner_salary={solve['winner_salary']}")
        print(f"SMOKE_OK legal_players={len(solve['legal_roster'])} "
              f"production_players={len(solve['production_roster'])}")
        return 0

    entries = []
    for winner in sorted(
            n1_report["winners"],
            key=lambda w: (int(w["season"]), int(w["week"]))):
        season, week = int(winner["season"]), int(winner["week"])
        artifacts = by_slate.get((season, week))
        if not artifacts:
            raise WinnerOptimaError(
                f"{season} week {week}: winner slate missing from manifest")
        best = None
        best_block = None
        universe = None
        world_scores = None
        for block_ix, path in enumerate(artifacts):
            ids, draws, cand_totals = _load_block(path)
            winner_block = winner_roster_world_totals(
                winner["roster_ids"], ids, draws)
            candidate = best_generating_world(winner_block, cand_totals)
            if candidate is None:
                continue
            if best is None or candidate["margin"] > best["margin"]:
                best = candidate
                best_block = (block_ix, path.name)
                universe = ids
                world_scores = draws[:, candidate["world_index"]]
        if best is None:
            raise WinnerOptimaError(
                f"{season} week {week}: no generating world found, but the "
                "frozen N1b census recorded one — artifact drift")
        recorded = float(winner["world_assignment"]["max_margin"])
        if abs(best["margin"] - recorded) > 1e-6:
            raise WinnerOptimaError(
                f"{season} week {week}: recomputed margin {best['margin']} "
                f"differs from the frozen report ({recorded})")
        frame = world_player_frame(
            _slate_rows(features, season, week),
            _slate_opp(opp_map, season, week),
            universe, world_scores)
        solve = solve_winner_world(frame, winner["roster_ids"])
        entries.append({
            "season": season,
            "week": week,
            "roster_ids": list(winner["roster_ids"]),
            "world": {
                **best,
                "block_index": best_block[0],
                "block_file": best_block[1],
                "recorded_margin_match": True,
            },
            "solve": solve,
        })
        print(f"SOLVED {season}:{week} block={best_block[1]} "
              f"world={best['world_index']}")

    report = winner_optima_report(entries)
    report["n1_report_path"] = str(args.report)
    report["manifest_path"] = str(args.manifest)
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":")).encode()
    with args.output.open("xb") as handle:
        handle.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    print(
        "WINNER_WORLD_OPTIMA_COMPLETE",
        f"protocol={PROTOCOL_ID}",
        f"winners={report['n_winners']}",
        f"output={args.output}",
        f"sha256={digest}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
