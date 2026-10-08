#!/usr/bin/env python3
"""Study row 68: is the Millionaire field getting sharper? One Monday line per week (descriptive; it gates nothing).

The operator's 10-07 question was whether AI-built systems are raising big-tournament winning scores. The line compares
the week's Millionaire winning score with what that slate's scoring predicts, using a FROZEN fit on 2023-25:

    expected = A + B x top10,  where top10 is the mean DraftKings points of the slate's 10 best skill players
    (QB / RB / WR / TE) in the Sunday 13:00-16:30 ET games;  residual = winning score - expected  (sd SD).

Provenance: reports/2026-10-07-brainstorm/winning_trend.py @ f1689126 (48 weeks: the 2023-24 Millionaire rosters file
and reports/2025-milly-winners.csv), refitted at full precision on 2026-10-08. A positive residual means the winner
scored more than the slate's scoring alone predicts; a run of positive residuals would be the sign of a sharper field.
Field size moves the winning score too (W1 2026: 832k entries vs about 162k after), so the line always prints it.

    python scripts/field_sharpness.py --season 2026 --week 5 [--contest <Millionaire id>] [--summary <path>]
        [--top10-source auto|actuals|milly] [--check-sources]

The top-10 source: `actuals` = nfl_features.player_week_actuals x player_week_role on the schedule's Sunday 13:00-16:30
ET games (exactly as the fit was made); `milly` = the week's Millionaire contest_ownership fpts (DraftKings' own scoring,
available with Monday's standings import), DST rows dropped. `auto` uses actuals when the week has them for at least 10
slate players, else milly; the line names the source used. --check-sources prints both for every 2026 week to date.
The Millionaire: --contest, else the week's largest-field contest in nfl_raw.contest_entries (rank-1 points and
expected_entries).
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

A, B, SD = 33.831007, 6.368607, 12.094059          # the frozen 2023-25 fit (48 weeks; residual sd with ddof 1)
SEASON_MEANS = {2023: (1.128256, 16), 2024: (-4.143626, 15), 2025: (2.594253, 17)}   # season: (mean residual, weeks)
PROVENANCE = "fit: reports/2026-10-07-brainstorm/winning_trend.py @ f1689126, 2023-25, 48 weeks"
SKILL = ("QB", "RB", "WR", "TE")
P = "nfl-predictions-503414"


def expected(top10: float) -> float:
    return A + B * float(top10)


def residual(win: float, top10: float) -> float:
    return float(win) - expected(top10)


def choose_source(requested: str, n_actuals: int) -> str:
    """`auto` takes the actuals when at least 10 slate skill players have them, else the Millionaire's fpts."""
    if requested in ("actuals", "milly"):
        return requested
    if requested != "auto":
        raise ValueError(f"unknown top-10 source {requested!r}")
    return "actuals" if n_actuals >= 10 else "milly"


def top10_mean(points) -> float:
    s = pd.Series(points, dtype=float).dropna().sort_values(ascending=False)
    if len(s) < 10:
        raise ValueError(f"only {len(s)} players have points; the top 10 needs 10")
    return float(s.iloc[:10].mean())


def season_line(season: int, week: int, win: float, field_n: int, top10: float, source: str, contest: str,
                to_date: list[float]) -> str:
    r = residual(win, top10)
    hist = " / ".join(f"{s} {m:+.1f}" for s, (m, _) in sorted(SEASON_MEANS.items()))
    mean = sum(to_date) / len(to_date) if to_date else float("nan")
    return (f"{season} W{week}: Millionaire {contest} winning score {win:.2f}, field {field_n:,} entries; slate top-10 "
            f"{top10:.2f} ({source}) -> expected {expected(top10):.1f}; residual {r:+.1f} (sd {SD:.1f}); {season} to date "
            f"{mean:+.1f} over {len(to_date)} week(s) ({hist}) [{PROVENANCE}]")


# ------------------------------------------------------------------------------------------------- BigQuery reads
def _q(sql: str, **params) -> pd.DataFrame:
    from google.cloud import bigquery
    typ = {int: "INT64", str: "STRING"}
    jc = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter(k, typ[type(v)], v) for k, v in params.items()])
    return bigquery.Client(project=P).query(sql, job_config=jc).to_dataframe()


def milly(season: int, week: int, contest: str | None) -> tuple[str, float, int]:
    d = _q(f"""SELECT contest_id, MAX(expected_entries) n, MAX(IF(rank = 1, CAST(points AS FLOAT64), NULL)) win
               FROM `{P}.nfl_raw.contest_entries` WHERE season = @s AND week = @w GROUP BY 1""", s=season, w=week)
    if contest:
        d = d[d.contest_id.astype(str) == str(contest)]
    if d.empty:
        raise SystemExit(f"FIELD SHARPNESS REFUSED: no contest_entries for {season} W{week}" + (f" contest {contest}" if contest else ""))
    row = d.sort_values("n", ascending=False).iloc[0]
    if pd.isna(row.win):
        raise SystemExit(f"FIELD SHARPNESS REFUSED: contest {row.contest_id} has no rank-1 entry")
    return str(row.contest_id), float(row.win), int(row.n)


def actuals_points(season: int, week: int) -> pd.Series:
    d = _q(f"""WITH g AS (SELECT home_team team FROM `{P}.nfl_raw.schedules` WHERE season = @s AND week = @w AND game_type = 'REG'
                 AND weekday = 'Sunday' AND gametime BETWEEN '13:00' AND '16:30'
               UNION ALL SELECT away_team FROM `{P}.nfl_raw.schedules` WHERE season = @s AND week = @w AND game_type = 'REG'
                 AND weekday = 'Sunday' AND gametime BETWEEN '13:00' AND '16:30')
               SELECT a.dk_points dk FROM `{P}.nfl_features.player_week_actuals` a
               JOIN `{P}.nfl_features.player_week_role` r ON r.gsis_id = a.gsis_id AND r.season = a.season AND r.week = a.week
               JOIN g ON g.team = a.team
               WHERE a.season = @s AND a.week = @w AND r.position IN ('QB', 'RB', 'WR', 'TE')""", s=season, w=week)
    return pd.to_numeric(d.dk, errors="coerce").dropna()


def milly_points(season: int, week: int, contest: str) -> pd.Series:
    d = _q(f"""SELECT display_name, MAX(CAST(fpts AS FLOAT64)) fpts, LOGICAL_OR(roster_position = 'DST') is_dst
               FROM `{P}.nfl_raw.contest_ownership` WHERE season = @s AND week = @w AND contest_id = @c GROUP BY 1""",
           s=season, w=week, c=str(contest))
    return pd.to_numeric(d[~d.is_dst.astype(bool)].fpts, errors="coerce").dropna()


def week_value(season: int, week: int, contest: str | None, source: str) -> dict:
    cid, win, n = milly(season, week, contest)
    act = actuals_points(season, week)
    src = choose_source(source, len(act))
    top10 = top10_mean(act if src == "actuals" else milly_points(season, week, cid))
    return {"week": week, "contest": cid, "win": win, "n": n, "top10": top10, "source": src, "residual": residual(win, top10)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--contest", default=None); ap.add_argument("--summary", type=Path, default=None)
    ap.add_argument("--top10-source", default="auto", choices=["auto", "actuals", "milly"])
    ap.add_argument("--check-sources", action="store_true", help="print both top-10 sources for every week to date")
    a = ap.parse_args(argv)
    if a.check_sources:
        for w in range(1, a.week + 1):
            cid, _, _ = milly(a.season, w, a.contest if w == a.week else None)
            act, mil = actuals_points(a.season, w), milly_points(a.season, w, cid)
            t_a = top10_mean(act) if len(act) >= 10 else float("nan"); t_m = top10_mean(mil)
            print(f"{a.season} W{w}: top-10 actuals {t_a:.2f} (n {len(act)}) vs Millionaire fpts {t_m:.2f} (n {len(mil)}); "
                  f"difference {t_a - t_m:+.2f}")
    vals = [week_value(a.season, w, a.contest if w == a.week else None, a.top10_source) for w in range(1, a.week + 1)]
    cur = vals[-1]
    line = season_line(a.season, a.week, cur["win"], cur["n"], cur["top10"], cur["source"], cur["contest"],
                       [v["residual"] for v in vals])
    print(line)
    if a.summary:
        a.summary.parent.mkdir(parents=True, exist_ok=True)
        with a.summary.open("a") as f:
            f.write(line + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
