"""G4 bootstrap, numpy-only (same rule and comparisons as bootstrap_verdicts.py, faster)."""
import glob, json, sys
from pathlib import Path
import numpy as np, pandas as pd
RES=Path(sys.argv[1]); REL=0.05; DRAWS=2000; rng=np.random.default_rng(0)
def load(d):
    rows=[json.loads(l)["result"] for f in sorted(glob.glob(str(RES/d/"results_bank*.jsonl"))) for l in open(f) if "result" in json.loads(l)]
    return pd.DataFrame(rows).drop_duplicates(["bank","season","week"],keep="last").reset_index(drop=True)
def verdict_arr(a,b,s):
    ta,tb=a.sum(),b.sum(); ok_up=True; ok_dn=True
    for y in np.unique(s):
        m=s==y; x,z=a[m].sum(),b[m].sum(); ok_up&=x>=z; ok_dn&=x<=z
    d=a-b; w,l=(d>0).sum(),(d<0).sum()
    if ta>=(1+REL)*tb and ok_up and w>l: return "SUPPORTED"
    if ta<=(1-REL)*tb and ok_dn and l>w: return "HARMFUL"
    return "NEUTRAL"
from comparisons import COMPARISONS
frames={}; out=[]
for panel,label,ca,cb in COMPARISONS:
    df=frames.setdefault(panel,load(panel)); a=df[ca].to_numpy(float); b=df[cb].to_numpy(float); s=df.season.to_numpy()
    v0=verdict_arr(a,b,s); n=len(a)
    seas={int(y):(int(a[s==y].sum()),int(b[s==y].sum())) for y in np.unique(s)}
    d=a-b; w,l,t=int((d>0).sum()),int((d<0).sum()),int((d==0).sum())
    agree=len({np.sign(x-z) for x,z in seas.values()})==1
    banks={int(bk):int(a[df.bank.to_numpy()==bk].sum()-b[df.bank.to_numpy()==bk].sum()) for bk in sorted(df.bank.unique())}
    # (i) slate-bank bootstrap
    c_sb={"SUPPORTED":0,"HARMFUL":0,"NEUTRAL":0}; rel_sb=[]
    for _ in range(DRAWS):
        i=rng.integers(0,n,n); c_sb[verdict_arr(a[i],b[i],s[i])]+=1; rel_sb.append(a[i].sum()/max(b[i].sum(),1)-1)
    # (ii) slate-cluster bootstrap: both banks of a slate together
    key=(df.season*100+df.week).to_numpy(); uk=np.unique(key); idx_by={k:np.where(key==k)[0] for k in uk}; m=len(uk)
    c_sl={"SUPPORTED":0,"HARMFUL":0,"NEUTRAL":0}; rel_sl=[]
    for _ in range(DRAWS):
        ks=uk[rng.integers(0,m,m)]; i=np.concatenate([idx_by[k] for k in ks]); c_sl[verdict_arr(a[i],b[i],s[i])]+=1; rel_sl.append(a[i].sum()/max(b[i].sum(),1)-1)
    rel_sb=np.array(rel_sb); rel_sl=np.array(rel_sl)
    out.append({"comparison":label,"verdict":v0,"a":int(a.sum()),"b":int(b.sum()),"rel":round(a.sum()/max(b.sum(),1)-1,3),
        "2023":f"{seas.get(2023,('-','-'))[0]} vs {seas.get(2023,('-','-'))[1]}","2024":f"{seas.get(2024,('-','-'))[0]} vs {seas.get(2024,('-','-'))[1]}",
        "seasons_agree":agree,"paired_W-L-T":f"{w}-{l}-{t}","bank_diffs":banks,
        "sb_same":round(c_sb[v0]/DRAWS,3),"sb_SUPP":round(c_sb["SUPPORTED"]/DRAWS,3),"sb_HARM":round(c_sb["HARMFUL"]/DRAWS,3),"sb_NEUT":round(c_sb["NEUTRAL"]/DRAWS,3),
        "sb_rel90":f"[{np.percentile(rel_sb,5):+.3f},{np.percentile(rel_sb,95):+.3f}]",
        "sl_same":round(c_sl[v0]/DRAWS,3),"sl_SUPP":round(c_sl["SUPPORTED"]/DRAWS,3),"sl_HARM":round(c_sl["HARMFUL"]/DRAWS,3),"sl_NEUT":round(c_sl["NEUTRAL"]/DRAWS,3),
        "sl_rel90":f"[{np.percentile(rel_sl,5):+.3f},{np.percentile(rel_sl,95):+.3f}]","sl_P(rel>0)":round(float((rel_sl>0).mean()),3)})
o=pd.DataFrame(out); pd.set_option("display.width",300); pd.set_option("display.max_columns",40); pd.set_option("display.max_colwidth",60)
print(o.to_string(index=False)); o.to_csv("bootstrap_verdicts_fast.csv",index=False)
l17,l18=frames["l17"],frames["l18"]
print("\nX50 K36 control per bank t89: L17",{int(bk):int(l17.loc[l17.bank==bk,'X50_tickets89'].sum()) for bk in sorted(l17.bank.unique())},"L18",{int(bk):int(l18.loc[l18.bank==bk,'X50_tickets89'].sum()) for bk in sorted(l18.bank.unique())})
a2=l17.groupby(["season","week"])["X50_tickets89"].sum(); b2=l18.groupby(["season","week"])["X50_tickets89"].sum()
print("X50 per-slate L17 vs L18: corr",round(float(np.corrcoef(a2.values,b2.values)[0,1]),3),"mean|diff|",round(float(np.abs(a2.values-b2.values).mean()),2),"identical",int((a2.values==b2.values).sum()),"of",len(a2))
x=l17["X50_tickets89"]; print("X50 per-slate-bank t89 mean",round(float(x.mean()),2),"sd",round(float(x.std()),2),"zeros L17",int((x==0).sum()),"L18",int((l18["X50_tickets89"]==0).sum()),"max",int(x.max()))
for panel,ca,cb in [("l17","X67_tickets89","X50_tickets89"),("l18","X40_tickets89","X50_tickets89"),("l13","PMO_X50_tickets89","MEAN_tickets89"),("l13","PMO_X50_tickets99","MEAN_tickets99")]:
    d=frames[panel][ca]-frames[panel][cb]; print(panel,ca,"-",cb,"diff/slate-bank mean",round(float(d.mean()),3),"sd",round(float(d.std()),3),"se(sum72)",round(float(d.std()*np.sqrt(len(d))),1),"sum",int(d.sum()))
