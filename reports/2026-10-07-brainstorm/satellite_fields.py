"""What wins in the SATELLITES (the contests Week 5 mostly enters), W1-4 2026 real standings in nfl_raw.contest_entries:
every contest whose name marks a satellite / qualifier (supersat, sat, wildcat, ffwc, SUPERSat, Qualifier), not the
Millionaires or the big open GPPs. Outcome: finishing in the top 2% / top 10% of the lineup's own contest. Mantel-Haenszel
odds ratios two ways: stratified by CONTEST (controls the field; compares users) and by USER-WEEK (controls the user;
users with 3+ satellite lineups that week, possibly across contests). Same pre-lock features as line_depth.py.
Server-side; user names fingerprinted; aggregates only."""
import json, re
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); Uw = []
SAT = r"(?i)(supersat|^sat|wildcat|ffwc|SUPERSat|Qualifier|satellite)"
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    fr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].drop_duplicates("display_name")
    cs = BQ.query(f"SELECT contest_id, ANY_VALUE(contest_name) nm, COUNT(DISTINCT entry_id) n FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1").to_dataframe()
    cs = cs[cs.nm.str.contains(SAT, regex=True) & ~cs.nm.str.contains("(?i)millionaire \\[|showdown", regex=True)]
    big = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    own = BQ.query(f"SELECT display_name, ANY_VALUE(pct_drafted) own FROM `nfl_raw.contest_ownership` WHERE contest_id = '{big}' GROUP BY 1").to_dataframe()
    om = dict(zip(own.display_name, pd.to_numeric(own.own, errors="coerce").fillna(0.0)))
    if cs.empty: continue
    q = """WITH m AS (SELECT n, s, p, t, o, pr, ow FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@sal) s WITH OFFSET j ON i = j JOIN UNNEST(@pos) p WITH OFFSET k ON i = k
                       JOIN UNNEST(@team) t WITH OFFSET a ON i = a JOIN UNNEST(@opp) o WITH OFFSET b ON i = b JOIN UNNEST(@proj) pr WITH OFFSET c ON i = c
                       JOIN UNNEST(@own) ow WITH OFFSET d ON i = d),
      e AS (SELECT DISTINCT contest_id, entry_id, rank, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key FROM `nfl_raw.contest_entries`
            WHERE season = 2026 AND week = @w AND contest_id IN UNNEST(@cids)),
      x AS (SELECT e.contest_id, e.u, e.entry_id, ANY_VALUE(e.rank) rank, ARRAY_AGG(STRUCT(m.s, m.p, m.t, m.o, m.pr, m.ow)) pl, COUNT(m.n) matched
            FROM e, UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.contest_id, e.u, e.entry_id),
      y AS (SELECT contest_id, u, rank, pl, (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') qbt, (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p = 'QB') qbo,
                   (SELECT ANY_VALUE(z.s) FROM UNNEST(pl) z WHERE z.p = 'DST') dsts FROM x WHERE matched = 9)
      SELECT contest_id, u, rank, (SELECT SUM(z.pr) FROM UNNEST(pl) z) proj, (SELECT SUM(z.ow) FROM UNNEST(pl) z) own_sum,
             (SELECT COUNTIF(z.s < 4000 AND z.p != 'DST') FROM UNNEST(pl) z) cheap, dsts,
             (SELECT COUNTIF(z.t = qbt AND z.p NOT IN ('QB', 'DST')) FROM UNNEST(pl) z) stack_n, (SELECT COUNTIF(z.t = qbo AND z.p != 'DST') FROM UNNEST(pl) z) bring_n FROM y"""
    proj = pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0.0)
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ArrayQueryParameter("cids", "STRING", cs.contest_id.astype(str).tolist()), bigquery.ScalarQueryParameter("w", "INT64", w),
        bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()), bigquery.ArrayQueryParameter("sal", "INT64", [int(x) for x in pd.to_numeric(fr.salary)]),
        bigquery.ArrayQueryParameter("pos", "STRING", fr.pos.astype(str).tolist()), bigquery.ArrayQueryParameter("team", "STRING", fr.team.astype(str).tolist()),
        bigquery.ArrayQueryParameter("opp", "STRING", fr.opp.astype(str).tolist()), bigquery.ArrayQueryParameter("proj", "FLOAT64", [float(x) for x in proj]),
        bigquery.ArrayQueryParameter("own", "FLOAT64", [float(om.get(n, 0.0)) for n in fr.display_name])])
    d = BQ.query(q, job_config=cfg).to_dataframe(); d["week"] = w; d = d.merge(cs[["contest_id", "n"]], on="contest_id", how="left"); Uw.append(d)
    print(f"W{w}: satellite contests {len(cs)}, lineups with 9 matched {len(d):,} of {int(cs.n.sum()):,}", flush=True)
D = pd.concat(Uw, ignore_index=True)
D["top2"] = D["rank"] <= np.maximum(1, np.floor(0.02 * D.n)); D["top10"] = D["rank"] <= np.maximum(1, np.floor(0.10 * D.n))
D["proj_hi"] = D.proj > D.groupby("contest_id").proj.transform("median"); D["own_hi"] = D.own_sum > D.groupby("contest_id").own_sum.transform("median")
D["uw"] = D.week.astype(str) + "|" + D.u.astype(str); D["uw_n"] = D.groupby("uw").u.transform("size")
EXPO = {"2+ sub-$4k vs 0-1": (D.cheap >= 2, D.cheap <= 1), "DST < $3,000 vs >= $3,500": (D.dsts < 3000, D.dsts >= 3500),
        "QB + 3+ vs QB + 2": (D.stack_n >= 3, D.stack_n == 2), "QB + 1 vs QB + 2": (D.stack_n == 1, D.stack_n == 2),
        "bring-back 1+ vs none": (D.bring_n >= 1, D.bring_n == 0), "projection above contest median": (D.proj_hi, ~D.proj_hi),
        "chalkier (own sum above contest median)": (D.own_hi, ~D.own_hi)}
def mh(sub, ex, ref, out, strat):
    X = sub[ex[sub.index] | ref[sub.index]].copy(); X["E"] = ex[X.index].astype(int); X["o"] = X[out].astype(int)
    s = X.groupby([strat, "E"]).o.agg(["size", "sum"]).reset_index().pivot_table(index=strat, columns="E", values=["size", "sum"], fill_value=0)
    for col in (("size", 0), ("size", 1), ("sum", 0), ("sum", 1)):
        if col not in s.columns: s[col] = 0
    a = s[("sum", 1)]; b = s[("size", 1)] - a; c = s[("sum", 0)]; d = s[("size", 0)] - c; n = a + b + c + d
    num, den = (a * d / n).fillna(0), (b * c / n).fillna(0)
    rng = np.random.default_rng(3); nv, dv = num.values, den.values
    bs = [nv[i].sum() / dv[i].sum() for i in (rng.integers(0, len(nv), len(nv)) for _ in range(500)) if dv[i].sum() > 0]
    return (num.sum() / den.sum() if den.sum() > 0 else np.nan), (np.percentile(bs, 2.5) if bs else np.nan), (np.percentile(bs, 97.5) if bs else np.nan), int(X.o.sum())
rows = []
for name, (ex, ref) in EXPO.items():
    r = {"feature (vs reference)": name}
    for out in ("top2", "top10"):
        est, lo, hi, ev = mh(D, ex, ref, out, "contest_id"); r[f"{out} by contest"] = f"{est:.2f} [{lo:.2f}, {hi:.2f}] ({ev})"
    for out in ("top10",):
        est, lo, hi, ev = mh(D[D.uw_n >= 3], ex, ref, out, "uw"); r[f"{out} within user"] = f"{est:.2f} [{lo:.2f}, {hi:.2f}] ({ev})"
    wk = []
    for w in sorted(D.week.unique()):
        est, _, _, _ = mh(D[D.week == w], ex, ref, "top10", "contest_id"); wk.append(f"{est:.2f}")
    r["top10 by contest, per week"] = "/".join(wk); rows.append(r)
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 60)
print(f"\nsatellite lineups {len(D):,} in {D.contest_id.nunique()} contests; users with 3+ satellite lineups in a week: {D[D.uw_n >= 3].uw.nunique():,} user-weeks")
print("odds ratio [95% bootstrap over strata] (events in the compared lineups):"); print(pd.DataFrame(rows).to_string(index=False))
print("\nshare of satellite lineups: 2+ cheap %.2f, DST < $3k %.2f, QB+3+ %.2f, QB+1 %.2f" % ((D.cheap >= 2).mean(), (D.dsts < 3000).mean(), (D.stack_n >= 3).mean(), (D.stack_n == 1).mean()))
