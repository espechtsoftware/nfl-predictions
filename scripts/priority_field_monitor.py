#!/usr/bin/env python3
"""Weekly real-field pattern monitor for the operator's PRIORITY contests (the outside reviewer, 10-07; descriptive, no rule).

The operator, 10-07: "I'd consider the $20 milly satellites a lower priority, the 4444, 555, 333, WWFC are top
priorities"; then "I forgot about the midseason warm ups. Those are big prizes. Can we move that up to under the 4444
and before 555" -- so the Midseason Warm Up sats are priority too. This is a separate script from field_pattern_monitor.py on purpose: the frozen field-pattern reading
(4ceada3f / ce13626d) is pinned to that monitor's Millionaire output, and nothing here writes to it.

For each week with a T-70 run (or --weeks), on the week's contests whose type (from the private type CSVs, read at
runtime: the shark-share table and the weekly mapping) contains a priority key ($4,444 / Warm Up / $555 / $333 / FFWC):
- the Mantel-Haenszel odds ratio of finishing in the top 2% / 5% / 10% of the lineup's own contest, stratified by
  CONTEST (controls the field) and by USER-WEEK (controls the user; users with 3+ priority lineups that week);
- features: 2+ sub-$4k non-DST players vs 0-1 (the primary line: the W5-W8 cheap tracking), DST < $3,000 vs >= $3,500,
  bring-back 1+ vs none, QB + 1 vs QB + 2, projection / chalk above the contest median;
- groups: all priority contests, the FFWC $14M qualifiers, the other priority satellites.
W1-4 (10-07, priority_fields.py): 2+ sub-$4k top 5% by contest 2.03, within user 1.93; per week 1.65 / 2.94 / 1.96 / 1.19.

User names are fingerprinted server-side and never downloaded; the type CSVs' other columns are not read. Aggregates only.
Usage: python priority_field_monitor.py [--weeks 5] [--types CSV ...] [--out CSV]
"""
import argparse
import csv
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd

PRIORITY_KEYS = ("$4,444", "Warm Up", "$555", "$333", "FFWC")
DEPTHS = (0.02, 0.05, 0.10)
CHEAP_MAX_SALARY = 4000
MIN_USER_LINEUPS = 3
DEFAULT_TYPES = ("private/regulars-share/shark_share_by_contest.csv", "private/regulars-share/week5_type_mapping.csv")

_spec = importlib.util.spec_from_file_location("field_pattern_monitor", Path(__file__).resolve().parent / "field_pattern_monitor.py")
FPM = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(FPM)


def load_types(paths) -> dict:
    """contest id -> type from one or more CSVs; the id column is the one named *contest_id; later files win."""
    out = {}
    for p in paths:
        p = Path(p)
        if not p.exists():
            continue
        with p.open(newline="") as fh:
            r = csv.DictReader(fh)
            idc = next((c for c in (r.fieldnames or []) if c.endswith("contest_id")), None)
            if idc is None or "type" not in (r.fieldnames or []):
                continue
            for row in r:
                if row.get(idc):
                    out[str(row[idc]).strip()] = row["type"]
    return out


def is_priority(contest_type: str, keys=PRIORITY_KEYS) -> bool:
    return any(k in str(contest_type) for k in keys)


def top_flags(rank, n, share: float) -> np.ndarray:
    """rank <= max(1, floor(share * field size)): a one-seat contest of 11 pays rank 1 at any depth below 1/11."""
    rank = np.asarray(rank, dtype=float); n = np.asarray(n, dtype=float)
    return rank <= np.maximum(1.0, np.floor(share * n))


def feature_cells(df: pd.DataFrame, stratum: str, exposed: pd.Series, reference: pd.Series, outcome: str) -> pd.DataFrame:
    """Cells for FPM.mh_odds_ratio: week, u (= the stratum key), k (1 exposed / 0 reference), n lineups, t events."""
    m = (exposed | reference).values
    x = pd.DataFrame({"week": df.week.values[m], "u": df[stratum].astype(str).values[m], "k": exposed.values[m].astype(int),
                      "o": df[outcome].values[m].astype(int)})
    return x.groupby(["week", "u", "k"]).o.agg(n="size", t="sum").reset_index()


def odds_ratio(df: pd.DataFrame, stratum: str, exposed: pd.Series, reference: pd.Series, outcome: str) -> tuple:
    cells = feature_cells(df, stratum, exposed, reference, outcome)
    est, num, den = FPM.mh_odds_ratio(cells, lambda k: k == 1)
    lo, hi = FPM.bootstrap_ci(num, den) if len(num) else (float("nan"), float("nan"))
    return est, lo, hi, int(cells.t.sum())


def features(d: pd.DataFrame) -> dict:
    return {"2+ sub-$4k vs 0-1": (d.cheap >= 2, d.cheap <= 1), "DST < $3,000 vs >= $3,500": (d.dsts < 3000, d.dsts >= 3500),
            "bring-back 1+ vs none": (d.bring_n >= 1, d.bring_n == 0), "QB + 1 vs QB + 2": (d.stack_n == 1, d.stack_n == 2),
            "projection above contest median": (d.proj_hi, ~d.proj_hi), "chalkier (own sum above contest median)": (d.own_hi, ~d.own_hi)}


def main() -> None:
    from google.cloud import bigquery
    ap = argparse.ArgumentParser(); ap.add_argument("--weeks", default=None); ap.add_argument("--out", default=None)
    ap.add_argument("--types", nargs="*", default=None); ap.add_argument("--season", type=int, default=2026)
    a = ap.parse_args()
    cfg = json.loads((Path.home() / "moneygate/weeks.json").read_text())
    weeks = [int(x) for x in a.weeks.split(",")] if a.weeks else sorted(int(k) for k, v in cfg["weeks"].items() if v.get("t70_run"))
    types = load_types(a.types if a.types else [Path.home() / p for p in DEFAULT_TYPES])
    bq = bigquery.Client(); frames = []
    for w in weeks:
        fr = pd.read_parquet(Path(cfg["weeks"][str(w)]["t70_run"]) / "frame.parquet")
        cs = bq.query(f"SELECT contest_id, COUNT(DISTINCT entry_id) n FROM `nfl_raw.contest_entries` WHERE season = {a.season} AND week = {w} GROUP BY 1").to_dataframe()
        cs["type"] = cs.contest_id.astype(str).map(types); untyped = int(cs.type.isna().sum())
        pri = cs[cs.type.map(lambda t: isinstance(t, str) and is_priority(t))]
        if pri.empty:
            print(f"W{w}: no typed priority contest among {len(cs)} loaded ({untyped} untyped) -- add the week's types to the type CSV", flush=True); continue
        fn = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].drop_duplicates("display_name")
        big = cs.sort_values("n", ascending=False).contest_id.iloc[0]
        own = bq.query(f"SELECT display_name, ANY_VALUE(pct_drafted) own FROM `nfl_raw.contest_ownership` WHERE contest_id = '{big}' GROUP BY 1").to_dataframe()
        om = dict(zip(own.display_name, pd.to_numeric(own.own, errors="coerce").fillna(0.0)))
        q = """WITH m AS (SELECT n, s, p, t, o, pr, ow FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@sal) s WITH OFFSET j ON i = j
                    JOIN UNNEST(@pos) p WITH OFFSET k ON i = k JOIN UNNEST(@team) t WITH OFFSET a ON i = a JOIN UNNEST(@opp) o WITH OFFSET b ON i = b
                    JOIN UNNEST(@proj) pr WITH OFFSET c ON i = c JOIN UNNEST(@own) ow WITH OFFSET d ON i = d),
          e AS (SELECT DISTINCT contest_id, entry_id, rank, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key
                FROM `nfl_raw.contest_entries` WHERE season = @season AND week = @w AND contest_id IN UNNEST(@cids)),
          x AS (SELECT e.contest_id, e.u, e.entry_id, ANY_VALUE(e.rank) rank, ARRAY_AGG(STRUCT(m.s, m.p, m.t, m.o, m.pr, m.ow)) pl, COUNT(m.n) matched
                FROM e, UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.contest_id, e.u, e.entry_id),
          y AS (SELECT contest_id, u, rank, pl, (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') qbt,
                       (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p = 'QB') qbo, (SELECT ANY_VALUE(z.s) FROM UNNEST(pl) z WHERE z.p = 'DST') dsts
                FROM x WHERE matched = 9)
          SELECT contest_id, u, rank, (SELECT SUM(z.pr) FROM UNNEST(pl) z) proj, (SELECT SUM(z.ow) FROM UNNEST(pl) z) own_sum,
                 (SELECT COUNTIF(z.s < @cheap AND z.p != 'DST') FROM UNNEST(pl) z) cheap, dsts,
                 (SELECT COUNTIF(z.t = qbt AND z.p NOT IN ('QB', 'DST')) FROM UNNEST(pl) z) stack_n,
                 (SELECT COUNTIF(z.t = qbo AND z.p != 'DST') FROM UNNEST(pl) z) bring_n FROM y"""
        jc = bigquery.QueryJobConfig(query_parameters=[
            bigquery.ArrayQueryParameter("cids", "STRING", pri.contest_id.astype(str).tolist()), bigquery.ScalarQueryParameter("w", "INT64", w),
            bigquery.ScalarQueryParameter("season", "INT64", a.season), bigquery.ScalarQueryParameter("cheap", "INT64", CHEAP_MAX_SALARY),
            bigquery.ArrayQueryParameter("names", "STRING", fn.display_name.astype(str).tolist()),
            bigquery.ArrayQueryParameter("sal", "INT64", [int(x) for x in pd.to_numeric(fn.salary)]),
            bigquery.ArrayQueryParameter("pos", "STRING", fn.pos.astype(str).tolist()), bigquery.ArrayQueryParameter("team", "STRING", fn.team.astype(str).tolist()),
            bigquery.ArrayQueryParameter("opp", "STRING", fn.opp.astype(str).tolist()),
            bigquery.ArrayQueryParameter("proj", "FLOAT64", [float(x) for x in pd.to_numeric(fn.mean_projection, errors="coerce").fillna(0.0)]),
            bigquery.ArrayQueryParameter("own", "FLOAT64", [float(om.get(n, 0.0)) for n in fn.display_name])])
        d = bq.query(q, job_config=jc).to_dataframe(); d["week"] = w
        d = d.merge(pri[["contest_id", "n", "type"]], on="contest_id", how="left"); frames.append(d)
        print(f"W{w}: priority contests {len(pri)} of {len(cs)} loaded ({untyped} untyped); lineups with 9 matched {len(d):,} of {int(pri.n.sum()):,}", flush=True)
    if not frames:
        print("no week has a typed priority contest"); raise SystemExit(3)
    D = pd.concat(frames, ignore_index=True)
    for s in DEPTHS:
        D[f"top{int(round(100 * s))}"] = top_flags(D["rank"], D.n, s)
    D["proj_hi"] = D.proj > D.groupby("contest_id").proj.transform("median"); D["own_hi"] = D.own_sum > D.groupby("contest_id").own_sum.transform("median")
    D["uw"] = D.week.astype(str) + "|" + D.u.astype(str); D["uw_n"] = D.groupby("uw").u.transform("size")
    D["group"] = np.where(D.type.str.contains("14M"), "FFWC $14M qualifiers", "other priority sats")
    rows = []
    for grp, G in [("all priority", D)] + list(D.groupby("group")):
        print(f"\n=== {grp}: lineups {len(G):,} in {G.contest_id.nunique()} contests; user-weeks with {MIN_USER_LINEUPS}+ lineups {G[G.uw_n >= MIN_USER_LINEUPS].uw.nunique():,}")
        for name, (ex, ref) in features(G).items():
            line = []
            for out in ("top2", "top5", "top10"):
                est, lo, hi, ev = odds_ratio(G, "contest_id", ex, ref, out)
                rows.append({"week": "pooled", "group": grp, "feature": name, "depth": out, "strata": "contest", "value": round(est, 3), "lo": round(lo, 3), "hi": round(hi, 3), "events": ev})
                line.append(f"{out} {est:.2f} [{lo:.2f}, {hi:.2f}] ({ev})")
            U = G[G.uw_n >= MIN_USER_LINEUPS]; ex_u, ref_u = features(U)[name]
            est, lo, hi, ev = odds_ratio(U, "uw", ex_u, ref_u, "top5")
            rows.append({"week": "pooled", "group": grp, "feature": name, "depth": "top5", "strata": "user-week", "value": round(est, 3), "lo": round(lo, 3), "hi": round(hi, 3), "events": ev})
            line.append(f"top5 within user {est:.2f} [{lo:.2f}, {hi:.2f}] ({ev})")
            per = []
            for w, Gw in G.groupby("week"):
                exw, refw = features(Gw)[name]; e_w, l_w, h_w, ev_w = odds_ratio(Gw, "contest_id", exw, refw, "top10")
                rows.append({"week": int(w), "group": grp, "feature": name, "depth": "top10", "strata": "contest", "value": round(e_w, 3), "lo": round(l_w, 3), "hi": round(h_w, 3), "events": ev_w})
                per.append(f"W{w} {e_w:.2f}")
            print(f"  {name:42s} " + "; ".join(line) + "; top10 by contest per week " + " ".join(per))
    if a.out:
        pd.DataFrame(rows).to_csv(a.out, index=False); print(f"\nwrote {a.out}")


if __name__ == "__main__":
    main()
