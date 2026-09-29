"""C1: field top-10 most-owned skill players vs our top-10 projected, realized points, 72 historical Millionaire
slates (2022-25; ownership REALIZED post-settlement; projection = point-in-time replay snapshot, panel
20260811-pitclean-e80-k1-a12ab31) plus 2026 W1-3 (projection = the build frame; ownership REALIZED Millionaire).
Also a light C2 supplement: MAE of an ownership-implied projection vs ours vs a blend (fit 2022-24, test 2025)."""
import re, sys, numpy as np, pandas as pd
S = "/tmp/claude-1000/-home-erich-projects-nfl-predictions/72305fd0-5efb-4d88-a744-a668e10ec3e9/scratchpad/q/C"
SKILL = ["QB","RB","WR","TE"]; TOPN = {"QB":3,"RB":5,"WR":5,"TE":3}
def norm(s):
    s=str(s).lower(); s=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?","",s); s=re.sub(r"[^a-z ]","",s); return " ".join(s.split())
def spearman(a,b):
    return float(pd.Series(a).rank().corr(pd.Series(b).rank()))

def slate_read(d, own_col="own", proj_col="proj", act_col="actual"):
    """d = one slate's skill players with own (0 if unlisted), proj, actual."""
    d = d.dropna(subset=[proj_col, act_col])
    top_own = d.nlargest(10, own_col); top_proj = d.nlargest(10, proj_col)
    r = {"n": len(d), "own_top10_pts": top_own[act_col].mean(), "proj_top10_pts": top_proj[act_col].mean(),
         "overlap": len(set(top_own.index) & set(top_proj.index)),
         "rho_own": spearman(d[own_col], d[act_col]), "rho_proj": spearman(d[proj_col], d[act_col])}
    lst = d[d[own_col] > 0]
    r["n_listed"] = len(lst); r["rho_own_listed"] = spearman(lst[own_col], lst[act_col]); r["rho_proj_listed"] = spearman(lst[proj_col], lst[act_col])
    for p, k in TOPN.items():
        dp = d[d.pos == p]
        if len(dp) >= k:
            r[f"{p}_own"] = dp.nlargest(k, own_col)[act_col].mean(); r[f"{p}_proj"] = dp.nlargest(k, proj_col)[act_col].mean()
    return r

# ---------- historical ----------
snap = pd.read_csv(f"{S}/snap_2022_2025.csv"); own = pd.read_csv(f"{S}/own_raw.csv"); hm = pd.read_csv(f"{S}/hist_milly_contests.csv")
hm = hm.sort_values(["season","week","sumpct"], ascending=[True,True,False]).drop_duplicates(["season","week"])
o = own[own.contest_id.isin(hm.contest_id)].assign(key=lambda x: x.display_name.map(norm), pos=lambda x: x.roster_position)
o = o.groupby(["season","week","key","pos"], as_index=False).pct_drafted.sum()
snap = snap.assign(key=snap.name.map(norm))
j = snap.merge(o, on=["season","week","key","pos"], how="left").rename(columns={"pct_drafted":"own"})
j["own"] = j.own.fillna(0.0)
sk = j[j.pos.isin(SKILL)]
rows = []
for (s,w), d in sk.groupby(["season","week"]):
    r = slate_read(d.reset_index(drop=True)); r.update(season=s, week=w); rows.append(r)
H = pd.DataFrame(rows)
H["field_wins"] = H.own_top10_pts > H.proj_top10_pts
H.to_csv(f"{S}/c1_historical_per_slate.csv", index=False)
print("=== C1 historical: 72 Millionaire slates 2022-25, skill players (QB/RB/WR/TE), snapshot universe (unlisted own=0) ===")
print(f"slates {len(H)}; snapshot skill players per slate {H.n.mean():.0f}; listed in the Millionaire file {H.n_listed.mean():.0f}")
def summ(g):
    return pd.Series({"slates": len(g), "field_top10_pts": g.own_top10_pts.mean(), "our_top10_pts": g.proj_top10_pts.mean(),
        "diff": (g.own_top10_pts-g.proj_top10_pts).mean(), "field_wins": int(g.field_wins.sum()), "ties": int((g.own_top10_pts==g.proj_top10_pts).sum()),
        "overlap_of_10": g.overlap.mean(), "rho_own_all": g.rho_own.mean(), "rho_proj_all": g.rho_proj.mean(),
        "rho_own_listed": g.rho_own_listed.mean(), "rho_proj_listed": g.rho_proj_listed.mean()})
print(H.groupby("season").apply(summ).round(3).to_string()); print(summ(H).round(3).to_string())
d = H.own_top10_pts - H.proj_top10_pts
print(f"paired diff field-ours: mean {d.mean():+.2f}, sd {d.std():.2f}, se {d.std()/np.sqrt(len(d)):.2f}, t {d.mean()/(d.std()/np.sqrt(len(d))):.2f}; field wins {int((d>0).sum())}/{len(d)}")
print("-- per position (top-k by own vs top-k by proj, realized pts mean; k: QB3 RB5 WR5 TE3)")
for p in SKILL:
    a, b = H[f"{p}_own"], H[f"{p}_proj"]; m = a.notna() & b.notna()
    print(f"  {p}: field {a[m].mean():.2f} vs ours {b[m].mean():.2f}  diff {(a-b)[m].mean():+.2f}  field wins {int(((a-b)[m]>0).sum())}/{int(m.sum())} ties {int(((a-b)[m]==0).sum())}")
# projection-rank vs own-rank, players in both top-10 vs only one
both, own_only, proj_only = [], [], []
for (s,w), d in sk.groupby(["season","week"]):
    d = d.dropna(subset=["proj","actual"]); to = set(d.nlargest(10,"own").index); tp = set(d.nlargest(10,"proj").index)
    both += list(d.loc[list(to&tp),"actual"]); own_only += list(d.loc[list(to-tp),"actual"]); proj_only += list(d.loc[list(tp-to),"actual"])
print(f"players in BOTH top-10s: n {len(both)} mean {np.mean(both):.2f}; field-only: n {len(own_only)} mean {np.mean(own_only):.2f}; ours-only: n {len(proj_only)} mean {np.mean(proj_only):.2f}")

# ---------- 2026 ----------
print("\n=== C1 2026 W1-3: build-frame projection (pre-lock) vs REALIZED Millionaire ownership (sum of slots) ===")
frames = {1:("/home/erich/week1-sunday/composite-20260913t1550z-t70-e7255e9/frame.parquet","2026-09-13 15:50Z (T-70 build)"),
          2:("/home/erich/week2-sunday/vetted-20260920t1410z-d3200-2dc116c/frame.parquet","2026-09-20 14:10Z (Sunday build)"),
          3:("/home/erich/week3-sunday/composite-20260927t1550z-d800-65305f5/frame.parquet","2026-09-27 15:50Z (T-70 build)")}
om = pd.read_csv(f"{S}/own_2026_milly.csv").assign(key=lambda x: x.display_name.map(norm))
served = pd.read_csv(f"{S}/proj_2026_last.csv").assign(key=lambda x: x.display_name.map(norm))
R26 = []
for w,(p,t) in frames.items():
    f = pd.read_parquet(p)[["name","pos","salary","proj","mean_projection"]].assign(key=lambda x: x.name.map(norm))
    ow = om[om.week==w][["key","own","fpts"]]
    d = f.merge(ow, on="key", how="left"); d["own"] = d.own.fillna(0.0); d = d.rename(columns={"fpts":"actual"})
    d = d[d.pos.isin(SKILL)]
    r = slate_read(d.reset_index(drop=True)); r.update(week=w, proj_source=f"frame {t}")
    R26.append(r)
    sv = served[served.week==w].rename(columns={"position":"pos","proj_points":"proj"}).merge(ow, on="key", how="left")
    sv["own"] = sv.own.fillna(0.0); sv = sv.rename(columns={"fpts":"actual"}); sv = sv[sv.pos.isin(SKILL)]
    r2 = slate_read(sv.reset_index(drop=True)); r2.update(week=w, proj_source=f"served table {served[served.week==w].generated_at.iloc[0]}Z")
    R26.append(r2)
    print(f"W{w} frame: top-10 owned {d.nlargest(10,'own')[['name','own','proj','actual']].to_string(index=False)}")
    print(f"W{w} frame: top-10 proj  {d.nlargest(10,'proj')[['name','own','proj','actual']].to_string(index=False)}")
R26 = pd.DataFrame(R26)
cols = ["week","proj_source","n","own_top10_pts","proj_top10_pts","overlap","rho_own","rho_proj","rho_own_listed","rho_proj_listed"]+[f"{p}_{k}" for p in SKILL for k in ("own","proj")]
print(R26[cols].round(3).to_string(index=False))
R26.to_csv(f"{S}/c1_2026.csv", index=False)

# ---------- C2 light supplement ----------
print("\n=== C2 supplement (realized-ownership-implied projection; the live version needs a pre-lock forecast) ===")
t = sk.dropna(subset=["proj","actual","salary"]).copy(); t["lo"] = np.log(t.own + 0.1)
X = pd.get_dummies(t.pos, drop_first=True).astype(float); X["lo"] = t.lo; X["sal"] = t.salary/1000; X["c"] = 1.0
for pos in ["RB","WR","TE"]:
    if pos in X: X[f"lo_{pos}"] = X[pos]*t.lo
tr = t.season <= 2024; te = t.season == 2025
def fit(Xa, ya): return np.linalg.lstsq(Xa, ya, rcond=None)[0]
b = fit(X[tr].to_numpy(), t.actual[tr].to_numpy()); t["own_impl"] = X.to_numpy() @ b
Xb = X.copy(); Xb["proj"] = t.proj; b2 = fit(Xb[tr].to_numpy(), t.actual[tr].to_numpy()); t["proj_plus_own"] = Xb.to_numpy() @ b2
Xc = pd.DataFrame({"proj": t.proj, "c": 1.0}); b3 = fit(Xc[tr].to_numpy(), t.actual[tr].to_numpy()); t["proj_recal"] = Xc.to_numpy() @ b3
for lab, m in [("all snapshot skill players (unlisted own=0)", te), ("listed in the Millionaire file", te & (t.own>0)), ("our top-60 projected per slate", te & (t.groupby(["season","week"]).proj.rank(ascending=False)<=60))]:
    d = t[m]
    print(f"2025 test, {lab}: n {len(d)}; MAE ours {np.abs(d.actual-d.proj).mean():.3f} | ours recalibrated {np.abs(d.actual-d.proj_recal).mean():.3f} | own-implied {np.abs(d.actual-d.own_impl).mean():.3f} | ours+own {np.abs(d.actual-d.proj_plus_own).mean():.3f} | 50/50 blend {np.abs(d.actual-(d.proj+d.own_impl)/2).mean():.3f}")
print("coef on log-own in ours+own model:", dict(zip(Xb.columns, np.round(b2,3))))
