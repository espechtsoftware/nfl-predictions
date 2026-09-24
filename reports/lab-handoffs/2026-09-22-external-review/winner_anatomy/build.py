"""Build per-lineup feature tables for every pulled contest and cache them."""
import numpy as np, pandas as pd
from feat import *
e = pd.read_parquet(HERE / "entries.parquet")
acct = open(HERE / "acct.txt").read().strip()
out = []
for w in (1, 2):
    pl = players(w); pl.to_parquet(HERE / f"players_w{w}.parquet")
    for cid, ew in e[e.week == w].groupby("contest_id"):
        L, flex = parse(ew, pl)
        ok = (L >= 0).all(axis=1)
        f = features(L[ok], pl, ownership(cid), flex[ok])
        f["week"] = w; f["contest_id"] = cid; f["contest"] = ew.contest_name.iloc[0][:28]
        f["points"] = ew.points.astype(float).to_numpy()[ok]; f["rank"] = ew["rank"].astype(int).to_numpy()[ok]
        nm = ew.entry_name.astype(str).str.replace(r" \(.*\)$", "", regex=True).to_numpy()[ok]
        f["user"] = pd.factorize(nm)[0]            # anonymised within contest
        f["ours"] = nm == acct
        cnt = ew.entry_name.astype(str).str.extract(r"\((\d+)/(\d+)\)$")[1].astype(float).to_numpy()[ok]
        f["user_entries"] = np.nan_to_num(cnt, nan=1.0)
        np.save(HERE / f"L_{cid}.npy", L[ok])
        n = len(f); f["pct"] = f["rank"] / n       # finish percentile, 0 = best
        out.append(f)
        print(w, cid, f.contest.iloc[0], n, "ours", int(f.ours.sum()))
pd.concat(out).to_parquet(HERE / "lineups.parquet")
