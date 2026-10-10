"""The receptions-per-game file for study 116's RB receptions floor (the operator 10-10: "Let's try another experiment where we
have a minimum number of receptions for a running back"; then "Please try it now and only of successful include it this week",
"successful" = "116 and re-check pass (Recommended)"). Format agreed with the lab reviewer 10-10 before building; one file for
the live union (--mix-min-rb-rec / --mix-rb-rec-source) and study 38's snapshot (S38_RB_REC_FILE).

    python rb_rec_file.py --season 2026 --week 5 --out ~/private/paper-corun/rbrec/w05.csv

Line 1: '# ' + JSON metadata {season, week, games, source, generated_utc}. Then gsis_id,rec_games,rec_sum,rec_per_game: every
gsis_id with at least one stat-line game in season W before week W (nfl_features.player_week_actuals, has_stat_line -- equal to
nflverse weekly REG's player-weeks, checked 10-10), all positions (the table has none; the union applies the floor to the
frame's RBs). The window is study 116's (nfl2 experiments/s116_rec_floor.py): his last up-to-GAMES stat-line games of season W,
strictly before week W; rec_per_game = rec_sum / rec_games. A player without such a game is not in the file (the union keeps
him)."""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from google.cloud import bigquery

GAMES = 4
SOURCE = "nfl_features.player_week_actuals (has_stat_line; season W, weeks < W)"
COLS = ["gsis_id", "rec_games", "rec_sum", "rec_per_game"]


def window(w: pd.DataFrame, games: int = GAMES) -> pd.DataFrame:
    """Per gsis_id: the last up-to-`games` rows by week (one row per player-week, refused otherwise), their receptions summed
    and averaged."""
    if w.duplicated(["gsis_id", "week"]).any():
        raise SystemExit("player_week_actuals holds a repeated (gsis_id, week) stat-line row")
    w = w.sort_values(["gsis_id", "week"])
    last = w.groupby("gsis_id", sort=True).tail(games)
    g = last.groupby("gsis_id", sort=True)["receptions"].agg(rec_games="size", rec_sum="sum").reset_index()
    g["rec_games"] = g["rec_games"].astype(int)
    g["rec_sum"] = g["rec_sum"].astype(float)
    g["rec_per_game"] = g["rec_sum"] / g["rec_games"]
    return g[COLS]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.week < 2:
        raise SystemExit(f"week {a.week}: no game this season precedes it")
    q = """SELECT gsis_id, week, CAST(receptions AS FLOAT64) AS receptions FROM `nfl_features.player_week_actuals`
           WHERE season = @s AND week < @w AND has_stat_line AND gsis_id IS NOT NULL"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("s", "INT64", a.season),
                                                    bigquery.ScalarQueryParameter("w", "INT64", a.week)])
    w = bigquery.Client(project="nfl-predictions-503414").query(q, job_config=cfg).to_dataframe()
    if w.empty or w["receptions"].isna().any():
        raise SystemExit(f"season {a.season} weeks < {a.week}: no stat-line rows, or a missing receptions value")
    g = window(w)
    meta = {"season": a.season, "week": a.week, "games": GAMES, "source": SOURCE,
            "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}
    a.out.parent.mkdir(parents=True, exist_ok=True)
    with open(a.out, "w") as fh:
        fh.write("# " + json.dumps(meta) + "\n")
        g.to_csv(fh, index=False)
    print(f"wrote {a.out}: {len(g)} players, weeks {sorted(w.week.unique().tolist())}; rec_per_game < 2.0: "
          f"{int((g.rec_per_game < 2.0).sum())}, < 1.5: {int((g.rec_per_game < 1.5).sum())} (all positions)")


if __name__ == "__main__":
    main()
