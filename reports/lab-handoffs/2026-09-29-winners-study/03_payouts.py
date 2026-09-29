"""Assign each entry its prize from the contest's payout ladder (ties split the prizes of the positions they occupy)."""
import json, numpy as np, pandas as pd
det = {}
for f in ("contest-details-2026-w01.json", "contest-details-2026-w02.json", "contest-details-2026-w03.json"):
    det.update({str(k): v for k, v in json.load(open(f)).items()})
e = pd.read_parquet("entries_all.parquet")
rows, meta = [], []
for cid, g in e.groupby("contest_id"):
    d = det.get(cid)
    if d is None: print("no ladder for", cid); continue
    n = len(g); prize = np.zeros(n + 1)
    for t in d.get("payoutSummary") or []:
        v = sum(float(p.get("value") or 0) * float(p.get("quantity") or 1) for p in t.get("payoutDescriptions", []))
        lo, hi = int(t["minPosition"]), min(int(t["maxPosition"]), n)
        if lo <= n: prize[lo:hi + 1] = v
    g = g.sort_values(["rank", "entry_id"]).reset_index(drop=True)
    pos = np.arange(1, n + 1)                                   # positions in sorted order
    # tie groups share the mean prize of the positions they occupy
    grp = g["rank"].to_numpy(); p = prize[pos]
    s = pd.Series(p).groupby(grp).transform("mean").to_numpy()
    g["prize"] = s; g["fee"] = float(d["fee"]); g["pct"] = (pos - 0.5) / n; g["n_field"] = n
    rows.append(g)
    meta.append({"contest_id": cid, "week": int(g.week.iloc[0]), "name": d["name"], "fee": float(d["fee"]), "entries": n, "entries_dk": d.get("entries"),
                 "pool_stated": d.get("payout"), "pool_computed": float(s.sum()), "paid_positions": int((prize > 0).sum()), "max_per_user": d.get("maxPerUser") or d.get("maximumEntriesPerUser")})
E = pd.concat(rows, ignore_index=True); E.to_parquet("entries_paid.parquet")
M = pd.DataFrame(meta); M.to_csv("contest_meta_all.csv", index=False)
pd.set_option("display.width", 250)
M["rake %"] = 100 * (1 - M.pool_stated / (M.fee * M.entries_dk)); M["check"] = M.pool_computed / M.pool_stated
print(M.sort_values(["week", "entries"], ascending=[True, False]).assign(name=M.name.str[:46]).groupby(["week", "name", "fee", "entries_dk"]).agg(n=("contest_id", "size"), paid=("paid_positions", "first"), pool=("pool_stated", "first"), check=("check", "mean"), rake=("rake %", "mean")).round(3).to_string())
