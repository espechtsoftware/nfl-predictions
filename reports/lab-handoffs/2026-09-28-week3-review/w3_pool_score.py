import pandas as pd, numpy as np, json
f = pd.read_parquet("frame.parquet"); c = pd.read_parquet("candidates.parquet")
pts = pd.read_csv("../pts_w3.csv").set_index("display_name").fpts
f["actual_dk"] = f.display_name.map(pts).fillna(0.0)
own = pd.read_parquet("../own_w3.parquet"); meta = pd.read_csv("../contest_meta.csv"); milly = int(meta.loc[meta.entries_dk.idxmax(), "contest_id"])
f["field_own"] = f.display_name.map(own[own.contest_id.astype(int) == milly].groupby("display_name").pct_drafted.sum()).fillna(0)
idx = {i: n for n, i in enumerate(f.id)}
rows = [[idx[p] for p in s.split(",")] for s in c.players]
R = np.zeros((len(c), len(f)), dtype=np.float32)
for i, r in enumerate(rows): R[i, r] = 1
inc = np.load("incumbent_player_scores.npy").astype(np.float32); hs = np.load("corrected_hsim_player_scores.npy").astype(np.float32)
T = np.concatenate([R @ inc, R @ hs], axis=1)                      # candidates x 20,000 selection worlds
act = R @ f.actual_dk.to_numpy(np.float32); mean_proj = R @ f.mean_projection.to_numpy(np.float32); tourney = R @ f.proj_tourney.to_numpy(np.float32)
npunt = R @ ((f.salary <= 4000) & (f.pos != "DST")).to_numpy(np.float32); ownsum = R @ f.field_own.to_numpy(np.float32)
c["act"], c["mean_proj"], c["tourney"], c["npunt"], c["ownsum"] = act, mean_proj, tourney, npunt, ownsum
c["simmean"] = T.mean(axis=1)
print("sel_mean vs simmean corr", round(np.corrcoef(c.sel_mean, c.simmean)[0, 1], 4), "| sel_mean vs mean_proj corr", round(np.corrcoef(c.sel_mean, c.mean_proj)[0, 1], 4))
print("pool: n", len(c), "| by tag realized mean:", c.groupby("tag").act.mean().round(1).to_dict(), "| projected mean by tag:", c.groupby("tag").mean_proj.mean().round(1).to_dict(), "| punts by tag:", c.groupby("tag").npunt.mean().round(2).to_dict())
lines = {"$2 sat (p91)": 169.4, "594 supersat (p96)": 173.8, "FFWC qual (p95)": 176.6, "wildcat (p99)": 189.5, "190 supersat (p99)": 190.5, "2378 supersat (p99)": 193.0, "$4444 sat (p99.8)": 205.5, "Milly top100": 208.0}
rosters = [frozenset(r) for r in rows]
def top_by(score, k=144, max_shared=7, cap=None):
    chosen, taken, cnt = [], [], {}
    for i in np.argsort(-score, kind="stable"):
        r = rosters[i]
        if any(len(r & t) > max_shared for t in taken): continue
        if cap is not None and any(cnt.get(p, 0) + 1 > cap * k for p in r): continue
        chosen.append(i); taken.append(r)
        for p in r: cnt[p] = cnt.get(p, 0) + 1
        if len(chosen) == k: break
    return np.array(chosen)
books = {"EMAX (entered)": np.array(c.index[c.book_rank.notna()])[np.argsort(c.book_rank.dropna().to_numpy())],
         "top mean (cap7)": top_by(c.simmean.to_numpy()), "top mean, exposure<=50%": top_by(c.simmean.to_numpy(), cap=0.5), "top mean, exposure<=35%": top_by(c.simmean.to_numpy(), cap=0.35),
         "top mean, no punts (<=1)": top_by(np.where(npunt <= 1, c.simmean.to_numpy(), -1e9)),
         "top mean, lev only": top_by(np.where(c.tag == "lev", c.simmean.to_numpy(), -1e9))}
for L in (175, 190, 205):
    p = (T >= L).mean(axis=1); books[f"top P(>={L})"] = top_by(p)
out = []
for name, b in books.items():
    r = act[b]; row = {"book": name, "realized mean": r.mean(), "best": r.max(), "proj mean": mean_proj[b].mean(), "punts/row": npunt[b].mean(), "own sum": ownsum[b].mean(),
                       "distinct": len(set(p for i in b for p in rosters[i])), "max exposure %": 100 * max(pd.Series([p for i in b for p in rosters[i]]).value_counts()) / len(b)}
    for k, L in lines.items(): row[k] = 100 * (r >= L).mean()
    out.append(row)
D = pd.DataFrame(out).set_index("book")
pd.set_option("display.width", 300)
print("\nWeek-3 pool (in-sample): 144-row books; columns after 'max exposure' = % of rows at or above each contest's real ticket line")
print(D.round(1).to_string())
c.to_parquet("cands_scored.parquet")
# what a lineup at each mean-projection percentile of the POOL actually scored (optimizer's-curse check inside our own pool)
c["mp_pct"] = c.simmean.rank(pct=True)
print("\nrealized by pool percentile of simulated mean:"); print(c.groupby(pd.cut(c.mp_pct, [0, .5, .8, .9, .95, .98, .99, 1.0]), observed=True).agg(n=("act", "size"), proj=("simmean", "mean"), realized=("act", "mean"), ge175=("act", lambda x: 100 * (x >= 175).mean()), ge190=("act", lambda x: 100 * (x >= 190).mean())).round(1).to_string())
