#!/usr/bin/env python3
"""Weekly "picks vs the rest of the field": do our player choices, and the max-entry regulars', beat the field's at the
same price? (The operator, 10-06: "do we feel that our ability to choose players - both stacks as well as boom players -
is at a level comparable to the winners?"; the reviewer's request; descriptive monitoring, no rule.)

The measure (reports/2026-10-05-regulars-player-choices.md §1): for a group's lineups, the sum over players of
(the group's share of lineups holding him - the rest of the Millionaire field's share) x his realized DK points. That is
the group's average lineup score minus the rest of the field's, in points per lineup.
The null (the reviewer's, 2026-10-05): realized points shuffled among players of the same position and $1,000 salary band
within the week, 1,000 draws. It separates "picks better at the same price" from "price and position tilts paid".

Groups:
- REGULARS: the FIXED cohort chosen by entry volume, never results (100+ entries in each of the 2026 W1-W4
  Millionaires; 117 users; a private file -- usernames never enter tracked files);
- OURS: every entry of our book that week, in every contest (the operator's private DK entry history).
The rest of the field is the Millionaire's entries outside the cohort and outside ours.

    GCP_PROJECT=... python scripts/weekly_picks_vs_field.py week --season 2026 --week 5 --contest <Milly id>
        --frame <T-70 frame.parquet> --cohort ~/private/regulars/cohort-2026w1-4.txt
        --entry-history <private DK entry history csv> --out-dir ~/private/picks-vs-field
    python scripts/weekly_picks_vs_field.py pool --out-dir ~/private/picks-vs-field

`week` prints the week's edges with their null and appends them (private jsonl); `pool` prints the running mean from
Week 5 on beside the before-FP baseline (2026 W1-4: ours -3.8, regulars +6.1 per lineup). Aggregates only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

B, SEED_BASE = 1000, 20261005
BASELINE = {"ours": -3.8, "regulars": 6.1}             # 2026 W1-4, points per lineup (the 10-05 report; before FP)
FIRST_WEEK = 5
GROUPS = {"regulars": "reg_share", "ours": "our_share"}


def edge(d: pd.DataFrame, col: str) -> float:
    """Points per lineup: sum over players of (group share - rest share) x realized points."""
    return float(((d[col] - d.rest_share) * d.dk).sum())


def null_draws(d: pd.DataFrame, col: str, b: int = B, seed: int = SEED_BASE) -> np.ndarray:
    """The edge with realized points shuffled within position x $1k salary band (players with known points and salary)."""
    d = d[d.dk.notna() & d.salary.notna()]
    diff = (d[col] - d.rest_share).to_numpy(float); dk = d.dk.to_numpy(float)
    idx = list(d.assign(band=(d.salary // 1000).astype(int)).groupby(["pos", "band"]).indices.values())
    rng = np.random.default_rng(seed); out = np.empty(b)
    for k in range(b):
        p = dk.copy()
        for ix in idx:
            p[ix] = dk[rng.permutation(ix)]
        out[k] = diff @ p
    return out


def panel(counts: pd.DataFrame, n: dict, frame: pd.DataFrame, dk: pd.Series) -> pd.DataFrame:
    """counts: player, grp ('reg' / 'ours' / 'rest'), k; n: lineups per grp; frame: display_name, pos, salary (T-70);
    dk: realized points by player. One row per player in the frame or picked by anyone."""
    sh = counts.pivot_table(index="player", columns="grp", values="k", aggfunc="sum").fillna(0.0)
    for g in ("reg", "ours", "rest"):
        sh[g] = sh[g] / n[g] if g in sh else 0.0
    f = frame.drop_duplicates("display_name").set_index("display_name")
    d = pd.DataFrame({"player": sh.index, "reg_share": sh["reg"].to_numpy(), "our_share": sh["ours"].to_numpy(),
                      "rest_share": sh["rest"].to_numpy()})
    d["pos"] = d.player.map(f.pos); d["salary"] = pd.to_numeric(d.player.map(f.salary), errors="coerce")
    d["dk"] = d.player.map(dk)
    return d


def load_week(a) -> tuple[pd.DataFrame, dict]:
    from google.cloud import bigquery
    proj = os.environ.get("GCP_PROJECT", "").strip()
    if not proj:
        raise SystemExit("GCP_PROJECT is not set (this reads the contest tables)")
    c = bigquery.Client(project=proj); P = proj
    cohort = [u.strip() for u in Path(a.cohort).read_text().splitlines() if u.strip()]
    keys = pd.read_csv(a.entry_history, dtype=str)["Entry_Key"].dropna().astype(str).tolist()
    job = bigquery.QueryJobConfig(query_parameters=[
        bigquery.ScalarQueryParameter("s", "INT64", a.season), bigquery.ScalarQueryParameter("w", "INT64", a.week),
        bigquery.ScalarQueryParameter("c", "STRING", str(a.contest)),
        bigquery.ArrayQueryParameter("cohort", "STRING", cohort), bigquery.ArrayQueryParameter("ours", "STRING", keys)])
    milly = f"""SELECT IF(TRIM(SPLIT(entry_name,' (')[OFFSET(0)]) IN UNNEST(@cohort), 'reg', 'rest') grp, entry_id, lineup_slots_json j
      FROM `{P}.nfl_raw.contest_entries` WHERE season=@s AND contest_id=@c AND points IS NOT NULL AND entry_id NOT IN UNNEST(@ours)"""
    ours = f"""SELECT 'ours' grp, entry_id, lineup_slots_json j FROM `{P}.nfl_raw.contest_entries`
      WHERE season=@s AND week=@w AND entry_id IN UNNEST(@ours)"""
    q = f"""WITH e AS ({milly} UNION ALL {ours})
      SELECT grp, JSON_VALUE(s,'$.player') player, COUNT(*) k FROM e, UNNEST(JSON_QUERY_ARRAY(j)) s GROUP BY 1, 2"""
    counts = c.query(q, job_config=job).to_dataframe()
    n = c.query(f"WITH e AS ({milly} UNION ALL {ours}) SELECT grp, COUNT(*) n FROM e GROUP BY 1", job_config=job).to_dataframe()
    n = dict(zip(n.grp, n.n.astype(int)))
    if not all(n.get(g) for g in ("reg", "rest", "ours")):
        raise SystemExit(f"a group has no lineups this week: {n}")
    own = c.query(f"""SELECT display_name player, MAX(CAST(fpts AS FLOAT64)) dk FROM `{P}.nfl_raw.contest_ownership`
      WHERE season=@s AND contest_id=@c GROUP BY 1""", job_config=job).to_dataframe()
    d = panel(counts, n, pd.read_parquet(a.frame), own.set_index("player").dk)
    return d, {"lineups": n, "players": int(len(d)), "unpriced_share": {g: float(d.loc[d.salary.isna() | d.dk.isna(), c2].sum() / max(d[c2].sum(), 1e-9))
                                                                       for g, c2 in GROUPS.items()}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0]); sub = ap.add_subparsers(dest="cmd", required=True)
    w = sub.add_parser("week")
    for k in ("--season", "--week"):
        w.add_argument(k, type=int, required=True)
    for k in ("--contest", "--frame", "--cohort", "--entry-history", "--out-dir"):
        w.add_argument(k, required=True)
    w.add_argument("--no-append", action="store_true", help="print only (the W1-4 parity check)")
    p = sub.add_parser("pool"); p.add_argument("--out-dir", required=True)
    a = ap.parse_args(argv)
    out = Path(a.out_dir); out.mkdir(parents=True, exist_ok=True); log = out / "picks-vs-field.jsonl"
    if a.cmd == "week":
        d, meta = load_week(a)
        recs = []
        for g, col in GROUPS.items():
            obs = edge(d[d.dk.notna()], col); nul = null_draws(d, col, seed=SEED_BASE + a.week)
            rec = {"season": a.season, "week": a.week, "group": g, "edge": round(obs, 3), "null_mean": round(float(nul.mean()), 3),
                   "null_sd": round(float(nul.std()), 3), "p_better": float((nul >= obs).mean()), "p_worse": float((nul <= obs).mean()),
                   "lineups": meta["lineups"]["reg" if g == "regulars" else "ours"], "unpriced_share": round(meta["unpriced_share"][g], 4)}
            recs.append(rec)
            print(f"W{a.week} {g:<9} picks vs the rest of the field {obs:+.1f} pts/lineup | null {rec['null_mean']:+.1f} "
                  f"(sd {rec['null_sd']:.1f}) | p(better) {rec['p_better']:.3f}, p(worse) {rec['p_worse']:.3f} | {rec['lineups']} lineups")
        if not a.no_append:
            prev = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
            if any(r["season"] == a.season and r["week"] == a.week for r in prev):
                raise SystemExit(f"{a.season} W{a.week} is already in {log}")
            with log.open("a") as h:
                for r in recs:
                    h.write(json.dumps(r) + "\n")
        return 0
    rows = [json.loads(x) for x in log.read_text().splitlines()] if log.exists() else []
    rows = [r for r in rows if r["week"] >= FIRST_WEEK]
    for g in GROUPS:
        e = [r["edge"] for r in rows if r["group"] == g]
        mean = f"{np.mean(e):+.1f}" if e else "n/a"
        print(f"{g:<9} weeks >= {FIRST_WEEK}: {len(e)} | mean {mean} pts/lineup | before FP (2026 W1-4): {BASELINE[g]:+.1f}"
              f" | by week {[round(x, 1) for x in e]}")
    print("Descriptive monitoring (no rule); after 3 weeks it shows whether the switch to FP closed the gap to the regulars.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
