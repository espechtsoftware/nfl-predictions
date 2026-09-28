from google.cloud import bigquery
import pandas as pd, numpy as np, json
P = "nfl-predictions-503414"; c = bigquery.Client(project=P)
det = json.load(open("contest-details-20260927.json"))
paid = {cid: max((t["maxPosition"] for t in x.get("payoutSummary", [])), default=0) for cid, x in det.items()}
meta = pd.DataFrame([{"contest_id": int(cid), "name": x["name"], "entries_dk": x["entries"], "fee": x["fee"], "paid": paid[cid],
                      "ticket_value": (x["payoutSummary"][0]["payoutDescriptions"][0].get("value") if x.get("payoutSummary") else None)} for cid, x in det.items()])
meta.to_csv("contest_meta.csv", index=False)
e = c.query(f"""SELECT contest_id, entry_name, rank, points, lineup FROM `{P}.nfl_raw.contest_entries` WHERE season = 2026 AND week = 3""").to_dataframe()
e["contest_id"] = e.contest_id.astype(int)
e.to_parquet("entries_w3.parquet")
own = c.query(f"""SELECT contest_id, display_name, roster_position, pct_drafted, fpts FROM `{P}.nfl_raw.contest_ownership` WHERE season = 2026 AND week = 3""").to_dataframe()
own.to_parquet("own_w3.parquet")
milly = meta.loc[meta.entries_dk.idxmax(), "contest_id"]
pts = own[own.contest_id.astype(int) == milly].groupby("display_name").fpts.max()
pts.to_csv("pts_w3.csv")
rows = []
for cid, g in e.groupby("contest_id"):
    m = meta[meta.contest_id == cid].iloc[0]; g = g.sort_values("rank")
    k = int(m.paid); line = g.points.iloc[k - 1] if k and k <= len(g) else np.nan
    per_user = g.groupby("entry_name").size()
    heavy = per_user[per_user >= 20].index
    rows.append({"contest": m["name"][:48], "fee": m.fee, "entries": len(g), "paid": k, "line": line, "p50": g.points.median(),
                 "line_pct": (g.points < line).mean() * 100, "users": g.entry_name.nunique(),
                 "share_from_20plus_users": g.entry_name.isin(heavy).mean() * 100,
                 "heavy_mean": g[g.entry_name.isin(heavy)].points.mean(), "light_mean": g[~g.entry_name.isin(heavy)].points.mean()})
R = pd.DataFrame(rows)
pd.set_option("display.width", 250)
summary = R.groupby(["contest", "fee", "entries", "paid"]).agg(n_contests=("line", "size"), line=("line", "mean"), p50=("p50", "mean"), line_pct=("line_pct", "mean"),
      users=("users", "mean"), share_20plus=("share_from_20plus_users", "mean"), heavy_mean=("heavy_mean", "mean"), light_mean=("light_mean", "mean")).reset_index()
print(summary.round(1).to_string())
R.to_csv("contest_lines.csv", index=False)
