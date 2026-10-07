"""The cheap-player finding on the WHOLE real field: every user with >= 20 Millionaire entries in a week (not just the
117-regular cohort). Server-side in BigQuery (user names are fingerprinted, never downloaded). Per lineup: the number of
sub-$4,000 non-DST players, salary used, the most expensive player's salary; top-1% flag. Within each user-week, the
top-1% lineups vs the same user's other lineups (standardized difference), as in within_portfolio.py. Aggregates only."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from google.cloud import bigquery
BQ = bigquery.Client(); CFG = json.loads((Path.home() / "moneygate/weeks.json").read_text())
WEEKS = sorted(int(k) for k, v in CFG["weeks"].items() if v.get("t70_run")); rows = []
for w in WEEKS:
    fr = pd.read_parquet(Path(CFG["weeks"][str(w)]["t70_run"]) / "frame.parquet").drop_duplicates("display_name")
    names = fr.display_name.astype(str).tolist(); sal = [int(x) for x in fr.salary]; pos = fr.pos.astype(str).tolist()
    cid = BQ.query(f"SELECT contest_id FROM `nfl_raw.contest_entries` WHERE season = 2026 AND week = {w} GROUP BY 1 ORDER BY MAX(expected_entries) DESC LIMIT 1").to_dataframe().contest_id.iloc[0]
    q = """WITH m AS (SELECT n, s, p FROM UNNEST(@names) n WITH OFFSET i JOIN UNNEST(@sal) s WITH OFFSET j ON i = j JOIN UNNEST(@pos) p WITH OFFSET k ON i = k),
      e AS (SELECT DISTINCT entry_id, rank, expected_entries ne, FARM_FINGERPRINT(TRIM(SPLIT(entry_name, ' (')[OFFSET(0)])) u, players_key FROM `nfl_raw.contest_entries` WHERE contest_id = @c AND season = 2026 AND week = @w),
      big AS (SELECT u FROM e GROUP BY u HAVING COUNT(*) >= 20),
      x AS (SELECT e.u, e.entry_id, ANY_VALUE(e.rank) rank, ANY_VALUE(e.ne) ne, COUNTIF(m.s < 4000 AND m.p != 'DST') cheap, SUM(m.s) sal, MAX(m.s) max_sal, COUNTIF(m.n IS NULL) unmatched
            FROM e JOIN big USING (u), UNNEST(SPLIT(e.players_key, '|')) nm LEFT JOIN m ON m.n = nm GROUP BY e.u, e.entry_id)
      SELECT u, rank <= 0.01 * ne AS top1, cheap, sal, max_sal, unmatched FROM x"""
    cfg = bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter("c", "STRING", cid), bigquery.ScalarQueryParameter("w", "INT64", w),
        bigquery.ArrayQueryParameter("names", "STRING", names), bigquery.ArrayQueryParameter("sal", "INT64", sal), bigquery.ArrayQueryParameter("pos", "STRING", pos)])
    d = BQ.query(q, job_config=cfg).to_dataframe(); d["week"] = w; rows.append(d)
    print(f"W{w}: {d.u.nunique():,} users with >= 20 entries, {len(d):,} lineups, {int(d.top1.sum()):,} top-1%; unmatched slots {d.unmatched.mean():.3f}/lineup", flush=True)
D = pd.concat(rows, ignore_index=True); D["uw"] = D.week.astype(str) + "|" + D.u.astype(str)
D = D[D.groupby("uw").top1.transform("any")]
rng = np.random.default_rng(11)
for f in ("cheap", "sal", "max_sal"):
    sd = D.groupby("uw")[f].transform("std"); z = (D[f] - D.groupby("uw")[f].transform("mean")) / (sd + 1e-9)
    t = D.assign(z=z)[D.top1 & (sd > 0)]; per = t.groupby("uw").z.mean()
    bs = [per.iloc[rng.integers(0, len(per), len(per))].mean() for _ in range(1000)]
    print(f"  {f:8s} within-portfolio top-1% vs other lineups: {per.mean():+.3f} sd [{np.percentile(bs, 2.5):+.3f}, {np.percentile(bs, 97.5):+.3f}]; by week " +
          str(t.groupby("week").z.mean().round(2).to_dict()) + f"; user-weeks {len(per):,}")
g = D.assign(k=D.cheap.clip(upper=3)).groupby(["week", "k"]).top1.agg(["mean", "size"]); g["mean"] = (100 * g["mean"]).round(2)
print("\nmulti-entry users' lineups: top-1% rate (%) by sub-$4k count"); print(g["mean"].unstack(0).to_string()); print(g["size"].unstack(0).to_string())
