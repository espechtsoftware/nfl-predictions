#!/usr/bin/env python3
"""Build the season/week/team/opp map for archived slate snapshots.

Queries nfl_raw.schedules for every (season, week) present in the given
immutable snapshot file, keeps regular-season games, and emits one row
per team-side. Fails closed if any snapshot team lacks exactly one
opponent that week or if the pairing is not symmetric within the slate
(both sides of every game must appear in the snapshot). Prints the
output sha256 for protocol pinning.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from nfl_dfs.bq import query_df  # noqa: E402
from nfl_dfs.config import settings  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args(argv)

    features = (
        pd.read_parquet(args.features)
        if args.features.suffix == ".parquet"
        else pd.read_csv(args.features)
    )
    slates = (
        features[["season", "week"]].astype(int)
        .drop_duplicates().sort_values(["season", "week"])
    )
    seasons = sorted(slates.season.unique().tolist())
    schedule = query_df(
        f"""
        SELECT season, week, home_team, away_team
        FROM `{settings.raw}.schedules`
        WHERE game_type = 'REG' AND season IN UNNEST(@seasons)
        """,
        params={"seasons": seasons},
    )

    rows = []
    for season, week in slates.itertuples(index=False):
        games = schedule[
            schedule.season.astype(int).eq(season)
            & schedule.week.astype(int).eq(week)
        ]
        pairing: dict[str, str] = {}
        for game in games.itertuples(index=False):
            home, away = str(game.home_team), str(game.away_team)
            for team, opp in ((home, away), (away, home)):
                if team in pairing:
                    raise SystemExit(
                        f"{season} week {week}: {team} appears in two games")
                pairing[team] = opp
        slate_teams = set(
            features[
                features.season.astype(int).eq(season)
                & features.week.astype(int).eq(week)
            ].team.astype(str)
        )
        unmatched = sorted(slate_teams - set(pairing))
        if unmatched:
            raise SystemExit(
                f"{season} week {week}: snapshot teams without a "
                f"scheduled game: {unmatched}")
        broken = sorted(
            team for team in slate_teams if pairing[team] not in slate_teams)
        if broken:
            raise SystemExit(
                f"{season} week {week}: snapshot holds one side of a game "
                f"only: {broken}")
        rows.extend(
            {"season": season, "week": week, "team": team,
             "opp": pairing[team]}
            for team in sorted(slate_teams)
        )

    frame = pd.DataFrame(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    frame.to_parquet(args.output, index=False)
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(
        "OPP_MAP_COMPLETE",
        f"slates={len(slates)}",
        f"rows={len(frame)}",
        f"output={args.output}",
        f"sha256={digest}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
