"""What clears each line depth? Week 5's installed plan enters contests paying from the top 0.2% to the top 23% (most at 1-4%). On the W1-4 real Millionaire fields,
within user-week (users with 20+ entries), the Mantel-Haenszel odds ratio of finishing inside the top 1% / 4% / 10% / 20%
for pre-lock lineup features: projected points (the T-70 frame's mean projection, above the user-week's own median),
field ownership sum (above own median; realized ownership as the chalk measure), and the structures from the 10-07
screen. Server-side join; user names fingerprinted. Aggregates only."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); Uw = []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet")
    fr = fr[pd.to_numeric(fr.salary, errors="coerce").notna()].drop_duplicates("display_name")
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    own = BQ.query(f"SELECT display_name, ANY_VALUE(pct_drafted) own FROM `nfl_raw.contest_ownership` WHERE contest_id = '{cid}' GROUP BY 1").to_dataframe()
    om = dict(zip(own.display_name, pd.to_numeric(own.own, errors="coerce").fillna(0.0)))
    q = """WITH m AS (SELECT n, s, p, t, o, pr, ow FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@sal) s WITH OFFSET j ON i = j JOIN UNNEST(@pos) p WITH OFFSET k ON i = k
                       JOIN UNNEST(@team) t WITH OFFSET a ON i = a JOIN UNNEST(@opp) o WITH OFFSET b ON i = b JOIN UNNEST(@proj) pr WITH OFFSET c ON i = c
                       JOIN UNNEST(@own) ow WITH OFFSET d ON i = d),
      e AS (SELECT DISTINCT entry_id, rank, expected_entries ne, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = 2026 AND week = @w),
      big AS (SELECT u FROM e GROUP BY u HAVING COUNT(*) >= 20),
      x AS (SELECT e.u, e.entry_id, ANY_VALUE(e.rank) / ANY_VALUE(e.ne) rk, ARRAY_AGG(STRUCT(m.s, m.p, m.t, m.o, m.pr, m.ow)) pl, COUNT(m.n) matched
            FROM e JOIN big USING (u), UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.u, e.entry_id),
      y AS (SELECT u, rk, pl, (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') qbt, (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p = 'QB') qbo,
                   (SELECT ANY_VALUE(z.s) FROM UNNEST(pl) z WHERE z.p = 'DST') dsts FROM x WHERE matched = 9)
      SELECT u, rk, (SELECT SUM(z.pr) FROM UNNEST(pl) z) proj, (SELECT SUM(z.ow) FROM UNNEST(pl) z) own_sum,
             (SELECT COUNTIF(z.s < 4000 AND z.p != 'DST') FROM UNNEST(pl) z) cheap, dsts,
             (SELECT COUNTIF(z.t = qbt AND z.p NOT IN ('QB', 'DST')) FROM UNNEST(pl) z) stack_n, (SELECT COUNTIF(z.t = qbo AND z.p != 'DST') FROM UNNEST(pl) z) bring_n,
             (SELECT MAX(z.ow) FROM UNNEST(pl) z WHERE z.p != 'DST') max_own FROM y"""
    proj = pd.to_numeric(fr.mean_projection, errors="coerce").fillna(0.0)
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", cid), bigquery.ScalarQueryParameter("w", "INT64", w),
        bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()), bigquery.ArrayQueryParameter("sal", "INT64", [int(x) for x in pd.to_numeric(fr.salary)]),
        bigquery.ArrayQueryParameter("pos", "STRING", fr.pos.astype(str).tolist()), bigquery.ArrayQueryParameter("team", "STRING", fr.team.astype(str).tolist()),
        bigquery.ArrayQueryParameter("opp", "STRING", fr.opp.astype(str).tolist()), bigquery.ArrayQueryParameter("proj", "FLOAT64", [float(x) for x in proj]),
        bigquery.ArrayQueryParameter("own", "FLOAT64", [float(om.get(n, 0.0)) for n in fr.display_name])])
    d = BQ.query(q, job_config=cfg).to_dataframe(); d["week"] = w; Uw.append(d); print(f"W{w}: multi-entry lineups {len(d):,}", flush=True)
D = pd.concat(Uw, ignore_index=True); D["uw"] = D.week.astype(str) + "|" + D.u.astype(str)
D["proj_hi"] = D.proj > D.groupby("uw").proj.transform("median"); D["own_hi"] = D.own_sum > D.groupby("uw").own_sum.transform("median")
for k in (1, 4, 10, 20):
    D[f"top{k}"] = D.rk <= k / 100.0
EXPO = {"projection above own median": (D.proj_hi, ~D.proj_hi), "ownership sum above own median (chalkier)": (D.own_hi, ~D.own_hi),
        "2+ sub-$4k vs 0-1": (D.cheap >= 2, D.cheap <= 1), "DST < $3,000 vs >= $3,500": (D.dsts < 3000, D.dsts >= 3500),
        "QB + 1 vs QB + 2": (D.stack_n == 1, D.stack_n == 2), "QB + 3+ vs QB + 2": (D.stack_n >= 3, D.stack_n == 2),
        "bring-back 1+ vs none": (D.bring_n >= 1, D.bring_n == 0)}
def mh(ex, ref, out):
    X = D[ex | ref].assign(E=ex[ex | ref].astype(int), o=D[out].astype(int))
    g = X.groupby(["week", "uw", "E"]).o.agg(["size", "sum"]).reset_index()
    s = g.pivot_table(index=["week", "uw"], columns="E", values=["size", "sum"], fill_value=0)
    for col in (("size", 0), ("size", 1), ("sum", 0), ("sum", 1)):
        if col not in s.columns: s[col] = 0
    a = s[("sum", 1)]; b = s[("size", 1)] - a; c = s[("sum", 0)]; d = s[("size", 0)] - c; n = a + b + c + d
    num, den = a * d / n, b * c / n
    wk = [num[num.index.get_level_values(0) == w].sum() / max(den[den.index.get_level_values(0) == w].sum(), 1e-12) for w in (1, 2, 3, 4)]
    return num.sum() / den.sum(), wk
rows = []
for name, (ex, ref) in EXPO.items():
    r = {"feature (vs reference)": name}
    for k in (1, 4, 10, 20):
        est, wk = mh(ex, ref, f"top{k}"); r[f"top{k}% OR"] = round(est, 2); r[f"top{k}% weeks"] = "/".join(f"{v:.2f}" for v in wk)
    rows.append(r)
pd.set_option("display.width", 260); pd.set_option("display.max_colwidth", 40)
print("\nwithin user-week Mantel-Haenszel odds ratios by line depth (W1-4 real Millionaire fields, users with 20+ entries)")
print(pd.DataFrame(rows).to_string(index=False))
print("\nmean percentile finish (share of field beaten) by projection quintile WITHIN user-week:")
D["pq"] = D.groupby("uw").proj.rank(pct=True).mul(5).clip(upper=4.999).astype(int) + 1
print(D.assign(beat=1 - D.rk).groupby(["pq", "week"]).beat.mean().unstack().round(3).to_string())
