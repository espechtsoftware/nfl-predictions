"""C4: chalk-core shape (<=2 players under 5% REALIZED Millionaire ownership, >=1 at 20%+; all nine slots, and a
skill-only variant) in our 2026 pools and entered books, with realized mean and cash-line share vs the rest.
Pools: W3 = the Sunday D12800 pool (cands_scored.pkl, 12,559 rows, realized 'actual'); W1 = the 800-candidate
K90 scoring subset (the only archived W1 pool on this host); W2 = the THURSDAY rehearsal D6400 pool (proxy; the
Sunday pool is not on this host -- cite the winner-anatomy 7.2%). Books: W3 our_book.pkl (144 rows), W1 the 57
Millionaire entries, W2 the single Millionaire entry (from contest_entries)."""
import re, pickle, numpy as np, pandas as pd
S="/tmp/claude-1000/-home-erich-projects-nfl-predictions/72305fd0-5efb-4d88-a744-a668e10ec3e9/scratchpad/q/C"
CASH={1:166.4, 2:138.0, 3:149.3}; TOP1={1:209.0, 2:179.8, 3:188.2}
def norm(s):
    s=str(s).lower(); s=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?","",s); s=re.sub(r"[^a-z ]","",s); return " ".join(s.split())
om = pd.read_csv(f"{S}/own_2026_milly.csv"); om["key"]=om.display_name.map(norm)
act = pd.read_csv(f"{S}/actuals_2026.csv")
def own_maps(w):
    o = om[om.week==w]; return dict(zip(o.key, o.own)), dict(zip(o.key, o.fpts))
SK={"QB","RB","WR","TE"}
def shape(names, omap, posmap=None):
    owns=[omap.get(norm(n), 0.0) for n in names]
    u5=sum(o<5 for o in owns); c20=sum(o>=20 for o in owns)
    if posmap is not None:
        sk=[o for n,o in zip(names,owns) if posmap.get(norm(n)) in SK]; u5s=sum(o<5 for o in sk)
    else: u5s=np.nan
    return u5, c20, u5s, sum(owns)
def report(w, df, label):
    df=df.copy(); df["core"]=(df.u5<=2)&(df.c20>=1); df["core_sk"]=(df.u5s<=2)&(df.c20>=1); df["strict"]=(df.u5<=1)&(df.c20>=2)
    n=len(df)
    for col in ("core","core_sk","strict"):
        a=df[df[col]]; b=df[~df[col]]
        if len(a)==0: print(f"  W{w} {label}: {col} 0/{n}"); continue
        print(f"  W{w} {label} [{col}]: {len(a)}/{n} = {len(a)/n:.1%} | realized mean {a.actual.mean():.1f} vs rest {b.actual.mean():.1f} (diff {a.actual.mean()-b.actual.mean():+.1f}) | cash share {(a.actual>=CASH[w]).mean():.1%} vs {(b.actual>=CASH[w]).mean():.1%} | top-1% line share {(a.actual>=TOP1[w]).mean():.2%} vs {(b.actual>=TOP1[w]).mean():.2%} | proj mean {a.proj.mean():.1f} vs {b.proj.mean():.1f}" if "proj" in df else "")
    return df
# ---- Week 3 ----
omap, fmap = own_maps(3)
fr3 = pd.read_parquet("/home/erich/week3-sunday/composite-20260927t1550z-d800-65305f5/frame.parquet"); pos3=dict(zip(fr3.name.map(norm), fr3.pos))
cs = pickle.load(open("/home/erich/week3-sunday/postmortem/cands_scored.pkl","rb"))
sh = cs.names.str.split("|").map(lambda ns: shape(ns, omap, pos3)); cs[["u5","c20","u5s","own_sum2"]] = pd.DataFrame(sh.tolist(), index=cs.index)
cs["proj"]=cs.sel_mean
print("=== Week 3 (ownership REALIZED Millionaire, post-settlement; cash line 149.3, top-1% 188.2) ===")
print(f"  own_sum check vs post-mortem own_sum: corr {cs.own_sum.corr(cs.own_sum2):.3f}")
report(3, cs, "Sunday D12800 pool (12,559)")
for tag,g in cs.groupby("tag"): report(3, g, f"pool batch {tag} ({len(g)})")
report(3, cs[cs.book_rank.notna()], "entered book (144)")
# ---- Week 1 ----
omap, fmap = own_maps(1)
fr1 = pd.read_parquet("/home/erich/week1-sunday/composite-20260913t1550z-t70-e7255e9/frame.parquet")
idcol = "id" if "id" in fr1.columns else "gsis_id"
id2name = dict(zip(fr1[idcol].astype(str), fr1.name)); pos1=dict(zip(fr1.name.map(norm), fr1.pos))
for _,r in fr1[fr1.pos=="DST"].iterrows(): id2name[f"{r.team}_DST"]=r["name"]
c1 = pd.read_csv("/home/erich/week1-sunday/learned-K90-20260913T160405364118Z/candidate_scores.csv")
c1["names"]=c1.players.str.split(",").map(lambda ids: [id2name.get(i, i) for i in ids])
miss = c1.names.map(lambda ns: sum(1 for n in ns if "-" in n and n[:3]=="00-")).sum(); print(f"\n=== Week 1 (cash 166.4, top-1% 209.0) === unmapped ids in 800-candidate file: {miss}")
c1["actual"]=c1.names.map(lambda ns: sum(fmap.get(norm(n), 0.0) for n in ns)); c1["proj"]=c1.sel_mean
sh = c1.names.map(lambda ns: shape(ns, omap, pos1)); c1[["u5","c20","u5s","own_sum"]] = pd.DataFrame(sh.tolist(), index=c1.index)
report(1, c1, "K90 scoring subset of the pool (800 of 3,200)")
for tag,g in c1.groupby("tag"): report(1, g, f"subset batch {tag} ({len(g)})")
b1 = pd.read_csv(f"{S}/milly_lineups_2026.csv"); b1 = b1[(b1.week==1)&(b1.ours)]
b1 = b1.rename(columns={"points":"actual","n_under5":"u5","n_20plus":"c20"}); b1["u5s"]=b1.duplicate_key.str.split("|").map(lambda ns: sum(1 for n in ns if pos1.get(norm(n)) in SK and omap.get(norm(n),0)<5))
print(f"  (W1 entered rows present in the truncated export: {len(b1)} of 57; full-field numbers for all 57 are in the BigQuery E_ours row)")
if len(b1): report(1, b1, f"entered Millionaire rows in export ({len(b1)})")
# ---- Week 2 proxy ----
omap, fmap = own_maps(2)
fr2 = pd.read_parquet("/home/erich/week2-sunday/vetted-20260920t1410z-d3200-2dc116c/frame.parquet"); pos2=dict(zip(fr2.name.map(norm), fr2.pos))
c2 = pd.read_parquet("/home/erich/week2-rehearsal-k97/20260917T150719330879Z-e7255e9/candidates.parquet")
c2["actual"]=c2.names.str.split("|").map(lambda ns: sum(fmap.get(norm(n), 0.0) for n in ns)); c2["proj"]=c2.sel_mean
sh = c2.names.str.split("|").map(lambda ns: shape(ns, omap, pos2)); c2[["u5","c20","u5s","own_sum"]] = pd.DataFrame(sh.tolist(), index=c2.index)
print("\n=== Week 2 PROXY: Thursday 09-17 rehearsal D6400 pool (the Sunday 12,555 pool is not on this host; its chalk-core share was 7.2% per the winner-anatomy report); cash 138.0, top-1% 179.8 ===")
report(2, c2, "Thursday rehearsal pool (6,400)")
for tag,g in c2.groupby("tag"): report(2, g, f"proxy batch {tag} ({len(g)})")
