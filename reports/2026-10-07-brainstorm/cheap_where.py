"""Where do the winning sub-$4k players sit? Per real-field lineup: the QB's team; each sub-$4k non-DST player is a STACK
piece (QB's team), a BRING-BACK (QB's opponent) or ELSEWHERE. Whole-field top-1% rate by category, and the within-user-week
Mantel-Haenszel OR (users with 20+ entries) for lineups whose cheap players include a stack piece vs lineups whose cheap
players are all elsewhere (both with >= 1 cheap player). Server-side; names fingerprinted. Aggregates only."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text()); Fw, Uw = [], []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("display_name")
    opp = dict(zip(fr.team.astype(str), fr.opp.astype(str)))
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    q = """WITH m AS (SELECT n, s, p, t, o FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@sal) s WITH OFFSET j ON i = j JOIN UNNEST(@pos) p WITH OFFSET k ON i = k
                       JOIN UNNEST(@team) t WITH OFFSET a ON i = a JOIN UNNEST(@opp) o WITH OFFSET b ON i = b),
      e AS (SELECT DISTINCT entry_id, rank, expected_entries ne, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = 2026 AND week = @w),
      x AS (SELECT e.u, e.entry_id, ANY_VALUE(e.rank) <= 0.01 * ANY_VALUE(e.ne) top1, ARRAY_AGG(STRUCT(m.s, m.p, m.t, m.o)) pl FROM e, UNNEST(SPLIT(e.players_key, '|')) nm JOIN m ON m.n = nm GROUP BY e.u, e.entry_id),
      y AS (SELECT u, top1, (SELECT ANY_VALUE(z.t) FROM UNNEST(pl) z WHERE z.p = 'QB') qbt, (SELECT ANY_VALUE(z.o) FROM UNNEST(pl) z WHERE z.p = 'QB') qbo, pl FROM x),
      c AS (SELECT u, top1, (SELECT COUNTIF(z.s < 4000 AND z.p != 'DST' AND z.t = qbt) FROM UNNEST(pl) z) c_stack,
                 (SELECT COUNTIF(z.s < 4000 AND z.p != 'DST' AND z.t = qbo) FROM UNNEST(pl) z) c_bring,
                 (SELECT COUNTIF(z.s < 4000 AND z.p != 'DST' AND z.t != qbt AND z.t != qbo) FROM UNNEST(pl) z) c_else FROM y),
      d AS (SELECT u, top1, CASE WHEN c_stack + c_bring + c_else = 0 THEN '0 none' WHEN c_stack > 0 THEN '1 has stack piece' WHEN c_bring > 0 THEN '2 bring-back only'
                 ELSE '3 elsewhere only' END cat FROM c)"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", cid), bigquery.ScalarQueryParameter("w", "INT64", w),
        bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()), bigquery.ArrayQueryParameter("sal", "INT64", [int(x) for x in fr.salary]),
        bigquery.ArrayQueryParameter("pos", "STRING", fr.pos.astype(str).tolist()), bigquery.ArrayQueryParameter("team", "STRING", fr.team.astype(str).tolist()),
        bigquery.ArrayQueryParameter("opp", "STRING", fr.opp.astype(str).tolist())])
    f = BQ.query(q + " SELECT cat, COUNT(*) n, COUNTIF(top1) t FROM d GROUP BY cat", job_config=cfg).to_dataframe(); f["week"] = w; Fw.append(f)
    u = BQ.query(q + ", big AS (SELECT u FROM d GROUP BY u HAVING COUNT(*) >= 20) SELECT u, cat, COUNT(*) n, COUNTIF(top1) t FROM d JOIN big USING (u) GROUP BY u, cat", job_config=cfg).to_dataframe(); u["week"] = w; Uw.append(u)
    print(f"W{w}: lineups {int(f.n.sum()):,}", flush=True)
F = pd.concat(Fw); U = pd.concat(Uw)
F["rate"] = 100 * F.t / F.n
print("\nwhole field: top-1% rate % by where the lineup's sub-$4k players sit"); print(F.pivot(index="cat", columns="week", values="rate").round(2).to_string())
print("share of lineups %"); print((100 * F.pivot(index="cat", columns="week", values="n") / F.groupby("week").n.sum()).round(1).to_string())
def mh(df, a_cat, b_cat):
    s = df[df.cat.isin([a_cat, b_cat])].assign(E=lambda d: d.cat == a_cat).groupby(["week", "u", "E"])[["n", "t"]].sum().unstack("E", fill_value=0)
    if ("t", True) not in s.columns or ("t", False) not in s.columns: return np.nan, None, None
    a = s[("t", True)]; b = s[("n", True)] - a; c = s[("t", False)]; d = s[("n", False)] - c; n = a + b + c + d
    num = (a * d / n).fillna(0); den = (b * c / n).fillna(0); return num.sum() / den.sum(), num, den
rng = np.random.default_rng(3)
print("\nwithin user-week MH odds ratio of a top-1% finish (users 20+ entries); 95% by bootstrap over user-weeks:")
for a_cat, b_cat in (("1 has stack piece", "3 elsewhere only"), ("2 bring-back only", "3 elsewhere only"), ("1 has stack piece", "0 none"), ("3 elsewhere only", "0 none")):
    est, num, den = mh(U, a_cat, b_cat)
    bs = [num.values[i].sum() / den.values[i].sum() for i in (rng.integers(0, len(num), len(num)) for _ in range(1000))]
    wk = {int(w): round(num[num.index.get_level_values(0) == w].sum() / max(den[den.index.get_level_values(0) == w].sum(), 1e-9), 2) for w in sorted(U.week.unique())}
    print(f"  {a_cat} vs {b_cat}: OR {est:.2f} [{np.percentile(bs, 2.5):.2f}, {np.percentile(bs, 97.5):.2f}] by week {wk}")
