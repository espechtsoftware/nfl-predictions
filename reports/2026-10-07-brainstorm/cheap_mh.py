"""The cheap-player effect as a Mantel-Haenszel odds ratio within user-weeks (users with >= 20 Millionaire entries; strata
without both outcomes contribute nothing), plus the unconditional top-1% rate by sub-$4k count over the WHOLE field
(single-entry users included). Server-side aggregation; user names fingerprinted and never downloaded."""
import json
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
U, Fd = [], []
for w in sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")):
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("display_name")
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    base = """WITH m AS (SELECT n, s, p FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@sal) s WITH OFFSET j ON i = j JOIN UNNEST(@pos) p WITH OFFSET k ON i = k),
      e AS (SELECT DISTINCT entry_id, rank, expected_entries ne, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = 2026 AND week = @w),
      x AS (SELECT e.u, e.entry_id, ANY_VALUE(e.rank) <= 0.01 * ANY_VALUE(e.ne) top1, LEAST(COUNTIF(m.s < 4000 AND m.p != 'DST'), 3) k
            FROM e, UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.u, e.entry_id)"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", cid), bigquery.ScalarQueryParameter("w", "INT64", w),
        bigquery.ArrayQueryParameter("names", "STRING", fr.display_name.astype(str).tolist()), bigquery.ArrayQueryParameter("sal", "INT64", [int(x) for x in fr.salary]),
        bigquery.ArrayQueryParameter("pos", "STRING", fr.pos.astype(str).tolist())])
    u = BQ.query(base + """, big AS (SELECT u FROM x GROUP BY u HAVING COUNT(*) >= 20)
      SELECT u, k, COUNT(*) n, COUNTIF(top1) t FROM x JOIN big USING (u) GROUP BY u, k""", job_config=cfg).to_dataframe(); u["week"] = w; U.append(u)
    f = BQ.query(base + " SELECT k, COUNT(*) n, COUNTIF(top1) t FROM x GROUP BY k", job_config=cfg).to_dataframe(); f["week"] = w; Fd.append(f)
    print(f"W{w}: multi-entry user-week-k cells {len(u):,}; whole field {int(f.n.sum()):,} lineups", flush=True)
U = pd.concat(U, ignore_index=True); F = pd.concat(Fd, ignore_index=True)
def mh(df, expo):
    s = df.assign(E=expo(df.k)).groupby(["week", "u", "E"])[["n", "t"]].sum().unstack("E", fill_value=0)
    a = s[("t", True)]; b = s[("n", True)] - a; c = s[("t", False)]; d = s[("n", False)] - c; n = a + b + c + d
    keep = (n > 0); num = (a * d / n)[keep]; den = (b * c / n)[keep]; return num, den
rng = np.random.default_rng(5)
print("\nMantel-Haenszel odds ratio of a top-1% finish, within user-week (users with 20+ entries); 95% by bootstrap over user-weeks")
for label, expo in (("1+ sub-$4k vs none", lambda k: k >= 1), ("2+ vs 0-1", lambda k: k >= 2), ("2 vs 0 (only those)", None)):
    df = U if expo else U[U.k.isin([0, 2])]; ex = expo or (lambda k: k == 2)
    num, den = mh(df, ex); est = num.sum() / den.sum()
    idx = np.arange(len(num)); bs = []
    for _ in range(1000):
        i = rng.integers(0, len(idx), len(idx)); bs.append(num.values[i].sum() / den.values[i].sum())
    wk = {w: round(num[num.index.get_level_values(0) == w].sum() / den[den.index.get_level_values(0) == w].sum(), 2) for w in sorted(U.week.unique())}
    print(f"  {label:22s} OR {est:.2f} [{np.percentile(bs, 2.5):.2f}, {np.percentile(bs, 97.5):.2f}]  by week {wk}")
F["rate"] = 100 * F.t / F.n
print("\nWHOLE field (all entrants), top-1% rate % by sub-$4k count (3 = 3+), and share of lineups %:")
print(F.pivot(index="k", columns="week", values="rate").round(2).to_string())
print((100 * F.pivot(index="k", columns="week", values="n") / F.groupby("week").n.sum()).round(1).to_string())
