"""C3 addendum: within-position Spearman and top-k hits of the production fade input naive_ownership(frame) computed
on the BUILD frame (T-70 / Sunday) vs the Thursday own_shadow naive, against REALIZED Millionaire ownership."""
import sys, re, numpy as np, pandas as pd
sys.path.insert(0,"/home/erich/projects/nfl-predictions/src")
from nfl_dfs.backtest.field import naive_ownership
S="/tmp/claude-1000/-home-erich-projects-nfl-predictions/72305fd0-5efb-4d88-a744-a668e10ec3e9/scratchpad/q/C"
def norm(s):
    s=str(s).lower(); s=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b\.?","",s); s=re.sub(r"[^a-z ]","",s); return " ".join(s.split())
om = pd.read_csv(f"{S}/own_2026_milly.csv"); om["key"]=om.display_name.map(norm)
os_ = pd.read_csv(f"{S}/own_shadow_2026w1.csv"); os_ = os_[os_.generated_at==os_.generated_at.max()].copy(); os_["key"]=os_.name.map(norm)
frames = {1:"/home/erich/week1-sunday/composite-20260913t1550z-t70-e7255e9/frame.parquet", 2:"/home/erich/week2-sunday/vetted-20260920t1410z-d3200-2dc116c/frame.parquet", 3:"/home/erich/week3-sunday/composite-20260927t1550z-d800-65305f5/frame.parquet"}
POSK={"QB":3,"RB":5,"WR":5,"TE":3,"DST":3}
for w,p in frames.items():
    f = pd.read_parquet(p); f["key"]=f.name.map(norm); f["naive_frame"]=np.asarray(naive_ownership(f)); f["value"]=f.proj/(f.salary/1000)
    d = f.merge(om[om.week==w][["key","own"]], on="key", how="left"); d["own"]=d.own.fillna(0)
    if w==1: d = d.merge(os_[["key","pred_own","booster_own"]], on="key", how="left")
    srcs = ["proj","value","naive_frame"] + (["pred_own","booster_own"] if w==1 else [])
    print(f"W{w} frame rows {len(f)} (matched to realized {d.own.gt(0).sum()}): within-position Spearman with realized ownership / top-k hits (k QB3 RB5 WR5 TE3 DST3)")
    for pos,k in POSK.items():
        dp = d[d.pos==pos]; top=set(dp.nlargest(k,"own").index)
        print(f"   {pos:3s} n{len(dp):4d}  " + "  ".join(f"{s}: rho {dp.own.rank().corr(dp[s].rank()):+.2f} hits {len(top & set(dp.dropna(subset=[s]).nlargest(k,s).index))}/{k}" for s in srcs))
    # realized top-15 skill by the frame's projection rank and salary
    sk = d[d.pos.isin(["QB","RB","WR","TE"])]; t = sk.nlargest(15,"own")
    print(f"   realized top-15 skill: mean salary {t.salary.mean():.0f} (frame skill mean {sk.salary.mean():.0f}); their projection rank within slate: median {sk.proj.rank(ascending=False).loc[t.index].median():.0f}, in our top-15 proj {int((sk.proj.rank(ascending=False).loc[t.index]<=15).sum())}; their value rank median {sk.value.rank(ascending=False).loc[t.index].median():.0f}")
