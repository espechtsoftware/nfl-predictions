"""Score pre-lock ownership predictions against the real field's ownership for one week (operator 2026-10-02: "try a
quick test to see how [the Fantasy Points ownership] data performs").

Real ownership needs no game outcome: it is known at lock. So this runs Sunday afternoon, once the Millionaire's
ownership is imported to nfl_raw.contest_ownership (the operator's post-lock export).

Sources (each optional; a missing one is reported, not invented):
  fp       nfl_raw.fantasy_points_projected_ownership, DraftKings rows, the newest capture retrieved BEFORE lock
  lag      the Saturday lag file (pred_own, %)            --lag
  blend    an ownership_blend-*.csv (pred_own, %)          --blend
  tabpfn   an ownership_tabpfn-*.csv (pred_own, %)         --tabpfn
Matched on the player's display name (normalised). Real ownership = the sum of pct_drafted over the player's roster
slots (an RB has an RB row and a FLEX row).

Per source, over the players every source covers (and over each source's own coverage):
  mean absolute error (points of ownership %), correlation, Spearman, and how many of the real top-20 the source's
  top-20 named. Prints only player-level public data; no entry ids, no user names.

Usage: score_ownership_sources.py --season 2026 --week 4 --contest <Millionaire id> --lock-utc 2026-10-04T17:00:00Z \
           [--lag f.csv] [--blend f.csv] [--tabpfn f.csv]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT = "nfl-predictions-503414"


def norm(s: object) -> str:
    return " ".join(str(s).replace(".", "").replace("'", "").split()).lower()


def real_ownership(client, season: int, week: int, contest: str) -> pd.Series:
    q = f"""SELECT display_name, SUM(pct_drafted) AS own FROM `{PROJECT}.nfl_raw.contest_ownership`
            WHERE season = {season} AND week = {week} AND contest_id = '{contest}' GROUP BY display_name"""
    d = client.query(q).to_dataframe()
    if d.empty:
        raise SystemExit(f"no real ownership for contest {contest} in {season} week {week} (import the post-lock export first)")
    return pd.Series(d.own.to_numpy(float), index=d.display_name.map(norm))


def fp_ownership(client, season: int, week: int, lock_utc: str) -> tuple[pd.Series, str]:
    q = f"""SELECT name, projected_ownership_pct, retrieved_at FROM `{PROJECT}.nfl_raw.fantasy_points_projected_ownership`
            WHERE season = {season} AND week = {week} AND operator = 'DraftKings' AND retrieved_at < TIMESTAMP('{lock_utc}')"""
    d = client.query(q).to_dataframe()
    if d.empty:
        return pd.Series(dtype=float), "no capture before lock"
    last = d[d.retrieved_at == d.retrieved_at.max()]
    return pd.Series(last.projected_ownership_pct.to_numpy(float), index=last.name.map(norm)), f"captured {last.retrieved_at.max()}"


def file_ownership(path: str | None) -> tuple[pd.Series, str]:
    if not path:
        return pd.Series(dtype=float), "not given"
    if not Path(path).is_file():
        return pd.Series(dtype=float), f"missing: {path}"
    d = pd.read_csv(path)
    name = next(c for c in ("display_name", "name") if c in d.columns)
    s = pd.Series(pd.to_numeric(d.pred_own, errors="coerce").clip(lower=0).to_numpy(float), index=d[name].map(norm))
    return s[~s.index.duplicated()], Path(path).name


def score(pred: pd.Series, real: pd.Series, players: list[str]) -> dict:
    p = pred.reindex(players).astype(float); r = real.reindex(players).astype(float)
    ok = p.notna() & r.notna(); p, r = p[ok], r[ok]
    top_r = set(r.sort_values(ascending=False).index[:20]); top_p = set(p.sort_values(ascending=False).index[:20])
    return {"players": int(ok.sum()), "MAE": round(float((p - r).abs().mean()), 2), "corr": round(float(p.corr(r)), 3),
            "spearman": round(float(p.rank().corr(r.rank())), 3), "top20 named": len(top_r & top_p)}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True); ap.add_argument("--week", type=int, required=True)
    ap.add_argument("--contest", required=True); ap.add_argument("--lock-utc", required=True)
    ap.add_argument("--lag"); ap.add_argument("--blend"); ap.add_argument("--tabpfn")
    a = ap.parse_args(argv)
    from google.cloud import bigquery
    client = bigquery.Client(project=PROJECT)
    real = real_ownership(client, a.season, a.week, a.contest)
    srcs = {"fp": fp_ownership(client, a.season, a.week, a.lock_utc), "lag": file_ownership(a.lag),
            "blend": file_ownership(a.blend), "tabpfn": file_ownership(a.tabpfn)}
    have = {k: s for k, (s, _) in srcs.items() if len(s)}
    for k, (s, why) in srcs.items():
        print(f"{k:7s} {len(s):4d} players  ({why})")
    print(f"real   {len(real):4d} players drafted in contest {a.contest}")
    common = sorted(set(real.index).intersection(*[set(s.index) for s in have.values()])) if have else []
    rows = []
    for k, s in have.items():
        rows.append({"source": k, "over": "common", **score(s, real, common)})
        rows.append({"source": k, "over": "own coverage", **score(s, real, sorted(set(real.index) & set(s.index)))})
    print(pd.DataFrame(rows).to_string(index=False))
    print("lower MAE / higher corr / more of the real top 20 = better; 'common' compares like with like")
    return 0


if __name__ == "__main__":
    sys.exit(main())
