"""B4: points-per-dollar calibration by position x salary tier, 2026 W1-3 served projections (last pre-lock batch and the Saturday batch)."""
from common import *
out=[]
def P(*a):
    s=" ".join(str(x) for x in a); print(s); out.append(s)
pp=pd.read_csv(os.path.join(DATA,"player_projections_2026.csv")); pp["generated_at"]=pd.to_datetime(pp.generated_at)
by_name,by_gsis,own=realized_tables()
def tier(pos,s):
    if pos=="QB": return "a<5.5k" if s<5500 else "b5.5-6.5k" if s<6500 else "c6.5-7.5k" if s<7500 else "d7.5k+"
    if pos=="TE": return "a<=4k" if s<=4000 else "b4-5.5k" if s<5500 else "c5.5k+"
    if pos=="DST": return "a<3k" if s<3000 else "b3-3.6k" if s<3600 else "c3.6k+"
    return "a<=4k" if s<=4000 else "b4-5.5k" if s<5500 else "c5.5-6.5k" if s<6500 else "d6.5-7.5k" if s<7500 else "e7.5k+"
batches={1:("2026-09-13 16:03:49","2026-09-08 14:33:26"),2:("2026-09-20 16:02:22","2026-09-19 15:09:52"),3:("2026-09-27 16:03:50","2026-09-26 14:57:13")}
allrows=[]
for wk,(last,sat) in batches.items():
    for lab,ts in (("last pre-lock (T-70 batch)",last),("Saturday batch",sat)):
        b=pp[(pp.week==wk)&(pp.generated_at==pd.Timestamp(ts))].copy()
        if wk==1 and lab.startswith("Sat"): b=b  # Week 1: 09-08 batch is the last Saturday-ish batch before the Sunday hourly runs
        # main slate only: keep rows whose display_name has a DK ownership record in the Millionaire OR appears in our frame of that week
        fs=load_frame(RUNS[wk]["sat"]); names=set(fs.display_name.astype(str))
        b=b[b.display_name.isin(names)]
        r1=np.array([by_name.get((wk,str(n)),np.nan) for n in b.display_name]); r2=np.array([by_gsis.get((wk,str(g)),np.nan) for g in b.gsis_id.astype(str)])
        b["realized"]=np.where(~np.isnan(r1),r1,np.where(~np.isnan(r2),r2,0.0)); b["played"]=b.realized>0
        b["tier"]=[tier(p,s) for p,s in zip(b.position,b.salary)]; b["week"]=wk; b["batch"]=lab
        allrows.append(b)
A=pd.concat(allrows)
for lab in ("last pre-lock (T-70 batch)","Saturday batch"):
    B=A[A.batch==lab]
    P(f"\n=== 2026 W1-3 pooled, served projections, {lab}; realized = DK fpts (0 if no record) ===")
    P(f"{'pos':<4}{'tier':<11}{'n':>5}{'played%':>8}{'sal':>6}{'proj':>7}{'real':>7}{'bias':>7}{'proj/1k':>8}{'real/1k':>8} | played only: {'n':>4}{'bias':>7}{'real/1k':>8}")
    for (pos,t),g in B.groupby(["position","tier"]):
        gp=g[g.played]
        P(f"{pos:<4}{t:<11}{len(g):>5}{100*g.played.mean():>8.0f}{g.salary.mean():>6.0f}{g.proj_points.mean():>7.2f}{g.realized.mean():>7.2f}{g.realized.mean()-g.proj_points.mean():>+7.2f}{1000*g.proj_points.mean()/g.salary.mean():>8.2f}{1000*g.realized.mean()/g.salary.mean():>8.2f} | {len(gp):>4}{(gp.realized-gp.proj_points).mean():>+7.2f}{1000*gp.realized.mean()/gp.salary.mean():>8.2f}")
    # per-week bias for the priced tiers (proj>=5), to show stability
    P("  per-week bias (realized - proj), players projected >=5, by position: " + " | ".join(f"W{w}: "+", ".join(f"{p} {v:+.1f}" for p,v in B[(B.week==w)&(B.proj_points>=5)].groupby('position').apply(lambda g:(g.realized-g.proj_points).mean()).items()) for w in (1,2,3)))
    # top-of-board: top 10 by projection per position per week -> realized
    P("  top-8 projected per position per week: proj -> realized")
    for w in (1,2,3):
        s=[]
        for pos,g in B[B.week==w].groupby("position"):
            t8=g.nlargest(8,"proj_points"); s.append(f"{pos} {t8.proj_points.mean():.1f}->{t8.realized.mean():.1f}")
        P(f"    W{w}: "+", ".join(s))
# stud RB/WR vs expensive QB/TE, priced players (proj>=5)
B=A[A.batch=="last pre-lock (T-70 batch)"]
for w in (1,2,3):
    b=B[(B.week==w)&(B.proj_points>=5)]
    P(f"  W{w} priced players (proj>=5): "+" | ".join(f"{k}: n {len(g)} proj/1k {1000*g.proj_points.mean()/g.salary.mean():.2f} real/1k {1000*g.realized.mean()/g.salary.mean():.2f}" for k,g in (("QB>=6.5k",b[(b.position=='QB')&(b.salary>=6500)]),("QB<5.5k",b[(b.position=='QB')&(b.salary<5500)]),("TE>=5k",b[(b.position=='TE')&(b.salary>=5000)]),("TE<=4k",b[(b.position=='TE')&(b.salary<=4000)]),("RB>=7k",b[(b.position=='RB')&(b.salary>=7000)]),("WR>=7k",b[(b.position=='WR')&(b.salary>=7000)]),("RB 5-7k",b[(b.position=='RB')&(b.salary>=5000)&(b.salary<7000)]),("WR 5-7k",b[(b.position=='WR')&(b.salary>=5000)&(b.salary<7000)]))))
open(os.path.join(HERE,"b4_calibration.out"),"w").write("\n".join(out))
