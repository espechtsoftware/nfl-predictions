#!/usr/bin/env python3
"""Run the winner anatomy diagnostics (protocol 20260819-winner-anatomy-v1).

Positive characterization of the 51 tracked Milly winners: roster
distance from the registered pool and selected books (null-calibrated),
actual Millionaire-contest ownership profile, and the realism of the
N1c world optima against realized corpus maxima (winners' own draws as
the control). Descriptive and outcome-aware; licenses nothing; runs
exactly once per frozen protocol version after the operator-directed
freeze of reports/2026-08-19-winner-anatomy-protocol.md.

The --smoke mode is the outcome-blind reality check required before the
freeze: it exercises every loader, join, and matcher on one slate and
prints contract facts only (counts and match rates — no overlaps, no
ownership values, no realism values).

Inputs:
  --n1c-report  frozen winner-world-optima report (rosters, legality,
                solved world identity, optimum rosters)
  --features    immutable slate-player snapshot parquet/csv
  --winners-root directory holding the two tracked winner CSVs
  --manifest    JSON list of {"season", "week", "artifacts": [npz paths]}
  --output      report JSON path (created exclusively; never overwrites)
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

import run_atlas_minimal_world_selection_c as base  # noqa: E402

from nfl_dfs.analysis.winner_anatomy import (  # noqa: E402
    PROTOCOL_ID,
    WinnerAnatomyError,
    anatomy_report,
    optimum_realism,
    ownership_profile,
    same_team_code,
)
from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.research.real_winner_overlap import (  # noqa: E402
    _TEAM_NICKNAMES,
    _name_matches,
    _name_tokens,
    evaluate_known_winner_overlap,
    load_known_winner_rows,
    match_known_winner_players,
)

NULL_REPS = 500
CAND_SQL = """
SELECT season, week, players, selected, actual_score
FROM `nfl-predictions-503414.nfl_predictions.replay_candidates_staging`
WHERE panel_run_id IN UNNEST(@panels)
"""
OWN_SQL = """
SELECT season, week, display_name, roster_position, pct_drafted
FROM `nfl-predictions-503414.nfl_raw.contest_ownership`
WHERE contest_name LIKE '%Millionaire%'
  AND season BETWEEN 2023 AND 2025
"""


def _load_features(path: Path) -> pd.DataFrame:
    if path.suffix == ".parquet":
        return pd.read_parquet(path)
    return pd.read_csv(path)


def _load_block(path: Path) -> tuple[np.ndarray, np.ndarray]:
    with np.load(path) as artifact:
        if not {"player_ids", "player_draws"} <= set(artifact.files):
            raise WinnerAnatomyError(f"{path} lacks player worlds")
        return (
            np.asarray(artifact["player_ids"], dtype=str),
            np.asarray(artifact["player_draws"], dtype=np.float64),
        )


def _match_ownership(
    player: pd.Series, slate_own: pd.DataFrame,
) -> float | None:
    """Frozen matching rule: DST by nickname->code; skill by exact
    case-insensitive name (winner spelling, then snapshot spelling),
    else a UNIQUE fuzzy token match; anything ambiguous is unmatched."""
    pos = str(player.pos).upper()
    if pos == "DST":
        rows = slate_own[slate_own.roster_position.astype(str).eq("DST")]
        for row in rows.itertuples(index=False):
            nickname = "".join(_name_tokens(row.display_name))
            code = _TEAM_NICKNAMES.get(nickname)
            if code is not None and same_team_code(code, str(player.team)):
                return float(row.pct_drafted)
        return None
    rows = slate_own[slate_own.roster_position.astype(str).eq(pos)]
    if rows.empty:
        return None
    names = rows.display_name.astype(str)
    for spelling in (str(player.winner_name), str(player["name"])):
        exact = rows[names.str.strip().str.lower().eq(
            spelling.strip().lower())]
        if len(exact) == 1:
            return float(exact.iloc[0].pct_drafted)
    fuzzy = rows[[
        _name_matches(player.winner_name, value)
        or _name_matches(player["name"], value)
        for value in names
    ]]
    if len(fuzzy) == 1:
        return float(fuzzy.iloc[0].pct_drafted)
    return None


def _overlap_entry(reports: pd.DataFrame, season: int, week: int) -> dict:
    rows = reports[
        reports.season.eq(season) & reports.week.eq(week)]
    if len(rows) != 2:
        raise WinnerAnatomyError(
            f"{season} week {week}: expected pool+selected overlap rows")
    by_book = {str(r.book): r for r in rows.itertuples(index=False)}
    payload = {}
    for book, row in by_book.items():
        payload[book] = {
            "n_entries": int(row.n_entries),
            "winner_player_coverage": int(row.winner_player_coverage),
            "max_overlap": int(row.max_overlap),
            "null_max_mean": float(row.null_max_mean),
            "max_minus_null": float(row.max_minus_null),
            "pair_any_rate": float(row.pair_any_rate),
        }
    payload["exact_winner_in_pool"] = bool(
        by_book["pool"].exact_winner_in_pool)
    payload["oracle_overlap"] = int(by_book["pool"].oracle_overlap)
    payload["selected_best_overlap"] = int(
        by_book["pool"].selected_best_overlap)
    return payload


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--n1c-report", required=True, type=Path)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--winners-root", required=True, type=Path)
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--smoke", metavar="SEASON:WEEK")
    args = parser.parse_args(argv)
    if not args.smoke and args.output is None:
        parser.error("--output is required outside --smoke mode")

    n1c = json.loads(args.n1c_report.read_text())
    slate_keys = {
        (int(w["season"]), int(w["week"])) for w in n1c["winners"]}
    if args.smoke:
        season, week = (int(x) for x in args.smoke.split(":"))
        if (season, week) not in slate_keys:
            raise WinnerAnatomyError(f"{season} week {week} not in report")
        slate_keys = {(season, week)}

    manifest = json.loads(args.manifest.read_text())
    block_paths = {
        Path(p).name: Path(p)
        for m in manifest for p in m["artifacts"]
    }
    features = _load_features(args.features)
    winners = load_known_winner_rows(args.winners_root)
    scoped = winners[[
        (int(s), int(w)) in slate_keys
        for s, w in zip(winners.season, winners.week)
    ]]
    resolved = match_known_winner_players(scoped, features)

    candidates = query_df(
        CAND_SQL, params={"panels": list(base.SOURCE_PANEL_IDS)})
    ownership = query_df(OWN_SQL)
    realized_max = (
        features.drop_duplicates(["season", "week", "id"])
        .groupby(features.id.astype(str)).actual.max().to_dict()
    )

    reports_frame, omitted_frame = evaluate_known_winner_overlap(
        candidates, resolved, null_reps=NULL_REPS)

    entries = []
    smoke_facts: list[str] = []
    for winner in sorted(
            n1c["winners"],
            key=lambda w: (int(w["season"]), int(w["week"]))):
        season, week = int(winner["season"]), int(winner["week"])
        if (season, week) not in slate_keys:
            continue
        roster_rows = resolved[
            resolved.season.eq(season) & resolved.week.eq(week)]
        if len(roster_rows) != 9:
            raise WinnerAnatomyError(
                f"{season} week {week}: resolved {len(roster_rows)} slots")
        if sorted(roster_rows.id.astype(str)) != sorted(
                map(str, winner["roster_ids"])):
            raise WinnerAnatomyError(
                f"{season} week {week}: resolution drifted from the "
                "frozen N1c roster")

        slate_own = ownership[
            ownership.season.astype(int).eq(season)
            & ownership.week.astype(int).eq(week)]
        if slate_own.empty:
            profile = None
            matched = 0
        else:
            pcts = [
                _match_ownership(row, slate_own)
                for _, row in roster_rows.iterrows()
            ]
            profile = ownership_profile(pcts)
            matched = int(profile["n_matched"])

        block_file = str(winner["world"]["block_file"])
        if block_file not in block_paths:
            raise WinnerAnatomyError(
                f"{season} week {week}: {block_file} missing from manifest")
        ids, draws = _load_block(block_paths[block_file])
        world_scores = dict(zip(
            ids.tolist(),
            draws[:, int(winner["world"]["world_index"])].tolist()))
        realism = {
            "optimum": optimum_realism(
                world_scores, realized_max,
                winner["solve"]["legal_roster"]),
            "winner": optimum_realism(
                world_scores, realized_max, winner["roster_ids"]),
        }
        if args.smoke:
            smoke_facts.append(
                f"SMOKE_OK slate={season}:{week} resolved=9 "
                f"ownership_rows={len(slate_own)} "
                f"ownership_matched={matched}/9 "
                f"world_scores={len(world_scores)} "
                f"realized_max_players={len(realized_max)}")
            continue
        entries.append({
            "season": season,
            "week": week,
            "roster_ids": list(map(str, winner["roster_ids"])),
            "production_valid": bool(
                winner["solve"]["winner_production_valid"]),
            "overlap": _overlap_entry(reports_frame, season, week),
            "ownership": profile,
            "realism": realism,
        })

    if args.smoke:
        pool_rows = candidates[
            candidates.season.astype(int).eq(season)
            & candidates.week.astype(int).eq(week)]
        print(f"SMOKE_OK candidates={len(pool_rows)} "
              f"selected={int(pool_rows.selected.sum())}")
        for line in smoke_facts:
            print(line)
        return 0

    report = anatomy_report(entries)
    report["null_reps"] = NULL_REPS
    report["omitted_winner_players"] = [
        {k: (int(v) if isinstance(v, (np.integer,)) else v)
         for k, v in record.items()}
        for record in omitted_frame.to_dict("records")
    ]
    report["n1c_report_path"] = str(args.n1c_report)
    report["manifest_path"] = str(args.manifest)
    payload = json.dumps(
        report, sort_keys=True, separators=(",", ":"),
        default=lambda o: (
            int(o) if isinstance(o, np.integer)
            else float(o) if isinstance(o, np.floating)
            else bool(o) if isinstance(o, np.bool_)
            else str(o)),
    ).encode()
    with args.output.open("xb") as handle:
        handle.write(payload)
    digest = hashlib.sha256(payload).hexdigest()
    print(
        "WINNER_ANATOMY_COMPLETE",
        f"protocol={PROTOCOL_ID}",
        f"winners={report['n_winners']}",
        f"output={args.output}",
        f"sha256={digest}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
