#!/usr/bin/env python
"""Score served projections for one slate against realized DK points.

Read-only: it queries nfl_predictions.player_projections and nfl_raw.weekly_stats
and writes nothing. Realized points use the same DK classic formula as
sql/features/013_player_week_actuals.sql, read straight from weekly_stats, so the
read does not wait on the weekly feature rebuild (player_week_actuals only picks
up a week once build-features runs after every game in it has been played).

Only run this after the operator has released the week's outcomes. Current-week
outcomes are never read before that release.

Two populations are excluded from scoring and reported as counts instead:
DST, because weekly_stats carries no team-defence rows; and zero-variance
stand-ins (proj_points and proj_std both 0), which are hard will-not-play
markers rather than forecasts -- scoring them credits the model for predicting
0 for a player who scored 0 and masks real error at the position.

Usage:
  python scripts/week_proper_scores.py --season 2026 --week 2 --slate 153430 \
      --batch 2026-09-20T16:02:22.753255+00:00 [--batch <another>] \
      [--out week2-proper-scores.json]

With no --batch, every batch for that slate is listed and nothing is scored.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from pathlib import Path

from google.cloud import bigquery

PROJECT = os.environ.get("GCP_PROJECT", "nfl-predictions-503414")
MIN_CALIBRATION_ROWS = 25

DK = """
      0.04*passing_yards + 4*passing_tds + IF(passing_yards>=300,3,0)
    - passing_interceptions
    + 0.1*rushing_yards + 6*rushing_tds + IF(rushing_yards>=100,3,0)
    + receptions + 0.1*receiving_yards + 6*receiving_tds
    + IF(receiving_yards>=100,3,0)
    - (sack_fumbles_lost + rushing_fumbles_lost + receiving_fumbles_lost)
    + 2*(passing_2pt_conversions + rushing_2pt_conversions
         + receiving_2pt_conversions)
    + 6*special_teams_tds
"""


def list_batches(client: bigquery.Client, season: int, week: int) -> None:
    q = f"""
    SELECT generated_at, slate_id, COUNT(*) n
    FROM `{PROJECT}.nfl_predictions.player_projections`
    WHERE season={season} AND week={week}
    GROUP BY 1, 2 ORDER BY 1, 2
    """
    for r in client.query(q).result():
        print(f"  {r.generated_at.isoformat()}  slate={r.slate_id}  n={r.n}")


def fetch(client: bigquery.Client, season: int, week: int, slate: int,
          generated_at: str) -> list[dict]:
    q = f"""
    WITH actual AS (
      SELECT player_id AS gsis_id, {DK} AS dk_points
      FROM `{PROJECT}.nfl_raw.weekly_stats`
      WHERE CAST(season AS INT64)={season} AND CAST(week AS INT64)={week}
        AND season_type='REG' AND player_id IS NOT NULL
    )
    SELECT p.gsis_id, p.display_name, p.position, p.team, p.salary, p.slate_id,
           p.proj_points, p.proj_p10, p.proj_p50, p.proj_p90, p.proj_std,
           p.p_20_plus, a.dk_points AS realized, a.gsis_id IS NOT NULL AS played
    FROM `{PROJECT}.nfl_predictions.player_projections` p
    LEFT JOIN actual a USING (gsis_id)
    WHERE p.season={season} AND p.week={week} AND p.slate_id={slate}
      AND p.generated_at = TIMESTAMP('{generated_at}')
    """
    return [dict(r) for r in client.query(q).result()]


def crps_gauss(mu: float, sigma: float, y: float) -> float | None:
    """Closed-form CRPS of a Gaussian predictive distribution."""
    if sigma is None or sigma <= 0:
        return None
    z = (y - mu) / sigma
    cdf = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    pdf = math.exp(-0.5 * z * z) / math.sqrt(2.0 * math.pi)
    return sigma * (z * (2.0 * cdf - 1.0) + 2.0 * pdf - 1.0 / math.sqrt(math.pi))


def pinball(q: float, pred: float, y: float) -> float:
    return (y - pred) * q if y >= pred else (pred - y) * (1.0 - q)


def median(xs: list[float]) -> float:
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


def panel(rows: list[dict], label: str) -> dict:
    """Score one batch. DST is excluded: weekly_stats carries no team-defence rows."""
    allskill = [r for r in rows if r["position"] in {"QB", "RB", "WR", "TE"}]
    dst = [r for r in rows if r["position"] == "DST"]
    for r in allskill:
        r["y"] = float(r["realized"]) if r["realized"] is not None else 0.0
    # A row with proj_std == 0 and proj_points == 0 is a hard "will not play"
    # stand-in, not a probabilistic forecast. Scoring it as one credits the
    # model for arithmetic (0 predicted, 0 scored) and hides real QB error.
    degenerate = [r for r in allskill if not r["proj_std"]]
    skill = [r for r in allskill if r["proj_std"]]

    def block(sub: list[dict]) -> dict | None:
        if not sub:
            return None
        err = [r["y"] - r["proj_points"] for r in sub]
        crps = [c for c in (crps_gauss(r["proj_points"], r["proj_std"], r["y"]) for r in sub) if c is not None]
        return {
            "n": len(sub),
            "mean_proj": sum(r["proj_points"] for r in sub) / len(sub),
            "mean_realized": sum(r["y"] for r in sub) / len(sub),
            "mean_bias": sum(err) / len(err),
            "bias_se": (math.sqrt(sum((e - sum(err) / len(err)) ** 2 for e in err)
                                  / max(1, len(err) - 1)) / math.sqrt(len(err))),
            "cov_p90_se": math.sqrt(0.9 * 0.1 / len(sub)),
            "cov_p10_se": math.sqrt(0.1 * 0.9 / len(sub)),
            "rmse": math.sqrt(sum(e * e for e in err) / len(err)),
            "median_abs_err": median([abs(e) for e in err]),
            "crps": sum(crps) / len(crps) if crps else None,
            "cov_p10": sum(1 for r in sub if r["y"] < r["proj_p10"]) / len(sub),
            "cov_p50": sum(1 for r in sub if r["y"] < r["proj_p50"]) / len(sub),
            "cov_p90": sum(1 for r in sub if r["y"] < r["proj_p90"]) / len(sub),
            "pinball_p90": sum(pinball(0.90, r["proj_p90"], r["y"]) for r in sub) / len(sub),
            "pinball_p10": sum(pinball(0.10, r["proj_p10"], r["y"]) for r in sub) / len(sub),
        }

    out = {"label": label, "slate": rows[0].get("slate_id", "?"), "n_rows": len(rows), "n_skill": len(skill), "n_dst": len(dst),
           "n_degenerate": len(degenerate),
           "degenerate_by_pos": {p: sum(1 for r in degenerate if r["position"] == p)
                                 for p in ("QB", "RB", "WR", "TE")},
           "degenerate_nonzero_realized": sum(1 for r in degenerate if r["y"] > 0),
           "degenerate_max_realized": max([r["y"] for r in degenerate], default=0.0),
           "n_no_stat_line": sum(1 for r in skill if not r["played"]),
           "all": block(skill),
           "by_position": {p: block([r for r in skill if r["position"] == p])
                           for p in ("QB", "RB", "WR", "TE")},
           "played_only": block([r for r in skill if r["played"]])}

    # Calibration of the published 20+ probability, in deciles of p_20_plus.
    have = [r for r in skill if r["p_20_plus"] is not None]
    have.sort(key=lambda r: r["p_20_plus"])
    buckets = []
    # Quintiles of fewer than 25 rows are too small to read; say so rather than
    # returning an empty list that looks like "nothing to report".
    if len(have) < MIN_CALIBRATION_ROWS:
        out["p20_calibration_note"] = (
            f"{len(have)} of {len(skill)} scored rows carry p_20_plus; "
            f"{MIN_CALIBRATION_ROWS} are required for quintiles, so no "
            f"calibration was computed")
    else:
        out["p20_calibration_note"] = ""
        size = len(have) // 5
        for i in range(0, size * 5, size):
            g = have[i:i + size]
            rate = sum(1 for r in g if r["y"] >= 20) / len(g)
            buckets.append({"n": len(g),
                            "mean_p20": sum(r["p_20_plus"] for r in g) / len(g),
                            "realized_rate": rate,
                            "realized_se": math.sqrt(max(rate * (1 - rate), 1e-9) / len(g))})
    out["p20_calibration"] = buckets
    return out


def show(p: dict) -> None:
    print(f"\n=== {p['label']}")
    print(f"    {p['n_rows']} projected rows on slate {p['slate']}: {p['n_dst']} DST excluded "
          f"(no team-defence rows in weekly_stats); {p['n_degenerate']} zero-variance "
          f"stand-ins excluded {p['degenerate_by_pos']}; {p['n_skill']} scored, of which "
          f"{p['n_no_stat_line']} recorded no stat line and score 0")
    print(f"    zero-variance stand-ins that did score: {p['degenerate_nonzero_realized']}, "
          f"largest {p['degenerate_max_realized']:.1f} DK points")
    hdr = (f"    {'group':<14}{'n':>5}{'proj':>8}{'real':>8}{'bias':>8}{'+-':>6}{'RMSE':>8}"
           f"{'medAE':>8}{'CRPS':>8}{'<p10':>7}{'<p50':>7}{'<p90':>7}{'pin90':>8}")
    print(hdr)
    rows = [("all skill", p["all"]), *((k, v) for k, v in p["by_position"].items()),
            ("played only", p["played_only"])]
    for name, b in rows:
        if not b:
            continue
        print(f"    {name:<14}{b['n']:>5}{b['mean_proj']:>8.2f}{b['mean_realized']:>8.2f}"
              f"{b['mean_bias']:>8.2f}{b['bias_se']:>6.2f}{b['rmse']:>8.2f}{b['median_abs_err']:>8.2f}"
              f"{b['crps']:>8.2f}{b['cov_p10']:>7.1%}{b['cov_p50']:>7.1%}"
              f"{b['cov_p90']:>7.1%}{b['pinball_p90']:>8.2f}")
    if p.get("p20_calibration_note"):
        print(f"    P(>=20) calibration not computed: {p['p20_calibration_note']}")
    if p["p20_calibration"]:
        print("    P(>=20) calibration, quintiles of the published probability:")
        for b in p["p20_calibration"]:
            print(f"      n={b['n']:>4}  stated {b['mean_p20']:>6.1%}   "
                  f"realized {b['realized_rate']:>6.1%} +- {b['realized_se']:>4.1%}")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--slate", type=int)
    ap.add_argument("--batch", action="append", default=[],
                    help="generated_at of a batch to score; repeatable")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args(argv)

    client = bigquery.Client(project=PROJECT)
    if not args.batch:
        print(f"batches for {args.season} week {args.week} "
              f"(pass one or more with --batch to score):")
        list_batches(client, args.season, args.week)
        return 0
    if args.slate is None:
        ap.error("--slate is required when --batch is given")

    panels = []
    for ts in args.batch:
        rows = fetch(client, args.season, args.week, args.slate, ts)
        if not rows:
            print(f"\n=== {ts}: no rows on slate {args.slate}; nothing scored")
            continue
        p = panel(rows, ts)
        p["generated_at"] = ts
        p["season"], p["week"], p["slate"] = args.season, args.week, args.slate
        panels.append(p)
        show(p)
    if not panels:
        print("no batch produced rows", flush=True)
        return 1
    if args.out:
        args.out.write_text(
            json.dumps(panels, indent=2, sort_keys=True, default=str) + "\n")
        print(f"\nwrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
