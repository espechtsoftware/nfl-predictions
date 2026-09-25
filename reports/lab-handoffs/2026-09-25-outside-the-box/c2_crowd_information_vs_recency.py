import json, re, pandas as pd, numpy as np
from scipy import stats
df=pd.read_parquet("ls_main.parquet")
pmap={int(k):tuple(v) for k,v in json.load(open("linestar/pmap.json")).items()}
# all-slate PID -> (pp, ps) per (season, week) for recency
rec=[]
for pid,(season,week) in pmap.items():
    d=json.load(open(f"linestar/p{pid}.json")); sc=json.loads(d["SalaryContainerJson"])
    seen=set()
    for r in sc["Salaries"]:
        if r["PID"] in seen: continue
        seen.add(r["PID"]); rec.append((season,week,r["PID"],r.get("PP"),r.get("PS")))
rec=pd.DataFrame(rec,columns=["season","week","pid","pp_all","ps_all"])
prev=rec.rename(columns={"pp_all":"prev_pp","ps_all":"prev_ps"}); prev["week"]=prev.week+1
df=df.merge(prev,on=["season","week","pid"],how="left")
df["prev_surprise"]=df.prev_ps-df.prev_pp

# played flag from nflverse box scores
def norm(s):
    s=str(s).lower(); s=re.sub(r"[\.\'’]","",s); s=re.sub(r"-"," ",s)
    s=re.sub(r"\b(jr|sr|ii|iii|iv|v)\b","",s); return re.sub(r"\s+"," ",s).strip()
a=pd.read_parquet("ps_all.parquet"); a=a[a.season_type=="REG"][["season","week","player_display_name"]]
b=pd.concat([pd.read_parquet(f"ps_{y}.parquet") for y in (2025,2026)]); b=b[b.season_type=="REG"][["season","week","player_display_name"]]
nv=pd.concat([a,b]); nv["nm"]=nv.player_display_name.map(norm); nv=nv.drop_duplicates(["season","week","nm"]); nv["played"]=True
df["nm"]=df.name.map(norm)
df=df.merge(nv[["season","week","nm","played"]],on=["season","week","nm"],how="left"); df["played"]=df.played.fillna(False).astype(bool)

# game window from LineStar's display string (Pacific time): 10:00 AM PT = 1 pm ET early, 1:05/1:25 PM PT = late
def _win(gi):
    m=re.search(r"(\d{1,2}):(\d{2}) (AM|PM)",str(gi))
    if not m: return "other"
    mins=(int(m.group(1))%12+(12 if m.group(3)=="PM" else 0))*60+int(m.group(2))
    return "early" if 9*60<=mins<11*60 else ("late" if 12*60<=mins<14*60 else "other")
df["window"]=df.gi.map(_win)
sk=df[df.pos.isin(["QB","RB","WR","TE"])&(df.pp>=4)].copy()
print("skill rows",len(sk),"played share",sk.played.mean().round(3),"slates",sk.groupby(["season","week"]).ngroups)
print("window counts",sk.window.value_counts().to_dict())
sk["resid"]=sk.ps-sk.pp
sk["lo_act"]=np.log(sk.own_act+0.1); sk["lo_proj"]=np.log(sk.own_proj+0.1)
sk["lpp"]=np.log(sk.pp); sk["lsal"]=np.log(sk.sal); sk["val"]=sk.pp/sk.sal*1000

def resid_within(g, y, X):
    Xm=np.column_stack([np.ones(len(g))]+[g[c].values for c in X]+[ (g.pos==p).astype(float).values for p in ["RB","WR","TE"]])
    beta,*_=np.linalg.lstsq(Xm,g[y].values,rcond=None); return g[y].values-Xm@beta

parts=[]
for (s,w),g in sk.groupby(["season","week"]):
    g=g.copy()
    g["e_act"]=resid_within(g,"lo_act",["lpp","lsal","val"])
    g["e_proj"]=resid_within(g,"lo_proj",["lpp","lsal","val"])
    g["drift"]=resid_within(g,"lo_act",["lo_proj"])     # what the crowd did beyond LineStar's pre-lock ownership projection
    parts.append(g)
sk=pd.concat(parts)

def slate_corr(d, x, y, min_n=25):
    out=[]
    for k,g in d.groupby(["season","week"]):
        g=g[[x,y]].dropna()
        if len(g)>=min_n: out.append(stats.spearmanr(g[x],g[y])[0])
    out=np.array(out); t=out.mean()/(out.std(ddof=1)/np.sqrt(len(out)))
    return f"mean rho {out.mean():+.3f}  t {t:+.1f}  positive {int((out>0).sum())}/{len(out)}"

pl=sk[sk.played]
print("\nSanity: corr(PP, PS) among played =", round(np.corrcoef(pl.pp,pl.ps)[0,1],3), " MAE", round((pl.ps-pl.pp).abs().mean(),2), " mean resid", round(pl.resid.mean(),2))
print("\n[T1] excess ACTUAL ownership (beyond LineStar proj, salary, value) -> residual, played:", slate_corr(pl,"e_act","resid"))
print("[T2] excess PROJECTED ownership (LineStar's ownership model beyond its own projection) -> residual:", slate_corr(pl,"e_proj","resid"))
print("[T3] drift = actual own beyond LineStar projected own -> residual:", slate_corr(pl,"drift","resid"))
for wnd in ["early","late"]:
    x=pl[pl.window==wnd]
    print(f"     {wnd}: T1 {slate_corr(x,'e_act','resid',12)} | T3 drift {slate_corr(x,'drift','resid',12)}")
print("\n[AVAIL] all rows incl. non-players: drift -> played:", slate_corr(sk,"drift","played"), "| e_proj -> played:", slate_corr(sk,"e_proj","played"))
# recency
r=pl.dropna(subset=["prev_surprise"])
print("\n[T4] last-week surprise -> excess ACTUAL ownership (does the crowd chase?):", slate_corr(r,"prev_surprise","e_act"))
print("[T4b] last-week surprise -> excess PROJECTED ownership:", slate_corr(r,"prev_surprise","e_proj"))
print("[T5] last-week surprise -> this week's residual vs LineStar projection:", slate_corr(r,"prev_surprise","resid"))
# decomposition of excess actual ownership into recency-explained vs rest
parts=[]
for k,g in r.groupby(["season","week"]):
    if len(g)<25: continue
    g=g.copy(); X=np.column_stack([np.ones(len(g)),g.prev_surprise.values]); b,*_=np.linalg.lstsq(X,g.e_act.values,rcond=None)
    g["own_recency"]=X@b; g["own_other"]=g.e_act-g.own_recency; parts.append(g)
r2=pd.concat(parts)
print("[T6] recency-driven part of excess ownership -> residual:", slate_corr(r2,"own_recency","resid"))
print("[T6] non-recency part of excess ownership -> residual:", slate_corr(r2,"own_other","resid"))
# magnitude: top vs bottom quintile of e_act, residual in DK points
pl=pl.copy(); pl["q"]=pl.groupby(["season","week"]).e_act.transform(lambda s: pd.qcut(s.rank(method="first"),5,labels=False))
print("\nResidual (PS-PP) by within-slate quintile of excess actual ownership (played):")
print(pl.groupby("q").resid.agg(["mean","count"]).round(2).T.to_string())
pl["qd"]=pl.groupby(["season","week"]).drift.transform(lambda s: pd.qcut(s.rank(method="first"),5,labels=False))
print("Residual by quintile of DRIFT (actual beyond projected ownership):")
print(pl.groupby(["window","qd"]).resid.mean().unstack().round(2).to_string())
sk.to_parquet("ls_skill_analysis.parquet")
