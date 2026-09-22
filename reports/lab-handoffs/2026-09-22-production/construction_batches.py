"""Verify the laptop's lev/boom finding on W2 and replicate on W1; add salary-left bins."""
import sys, numpy as np, pandas as pd
from scipy.stats import hypergeom
sys.path.insert(0,"/home/erich/projects/.nfl-predictions-worktrees/week3-qbgate-minimal/src")
from nfl_dfs.bq import query_df
from nfl_dfs.config import settings
for tag,wk,rf in [("item3",2,"roster_idx.npy"),("w1",1,"rix.npy")]:
    fr=pd.read_parquet(f"{tag}/frame.parquet").reset_index(drop=True); cd=pd.read_parquet(f"{tag}/cands.parquet"); rix=np.load(f"{tag}/{rf}")
    own=query_df(f"SELECT display_name, MAX(fpts) fpts FROM `{settings.raw}.contest_ownership` WHERE season=2026 AND week={wk} GROUP BY 1")
    lut=dict(zip(own.display_name.astype(str),own.fpts.astype(float)))
    pa=np.array([lut.get(str(n),np.nan) for n in fr.display_name],float); dead=np.isnan(pa)|(np.nan_to_num(pa)==0)
    real=np.nan_to_num(pa)[rix].sum(axis=1); sal=fr.salary.to_numpy(float)[rix].sum(axis=1)
    top=real>=np.quantile(real,0.99); clean=~dead[rix].any(axis=1)
    fam=cd.tag.astype(str).str.extract(r"^([a-z_]+)")[0].fillna(cd.tag.astype(str))
    print(f"\n=== WEEK {wk}: pool {len(real):,}, top-1% line {np.quantile(real,0.99):.2f} ({top.sum()} lineups), book {int(cd.book_rank.notna().sum())} ===")
    print(f"tag families: {fam.value_counts().to_dict()}")
    for lab,m in (("ALL",np.ones(len(real),bool)),("CLEAN (no zero-point player)",clean)):
        print(f"  {lab}:")
        T=top[m].sum(); N=m.sum()
        for f in fam[m].value_counts().index:
            mm=m&(fam==f).to_numpy(); k=int((top&mm).sum()); n=int(mm.sum()); e=n*T/N
            p=hypergeom.cdf(k,N,T,n) if k<e else hypergeom.sf(k-1,N,T,n)
            inbook=int((cd.book_rank.notna().to_numpy()&(fam==f).to_numpy()).sum())
            print(f"    {f:<10} share {100*n/N:5.1f}%  best {real[mm].max():6.1f}  top-1% {k:>4} (exp {e:5.1f}, lift {k/e if e else 0:4.2f}, p {p:.4f})  in book {inbook}")
    b=clean&(fam=="boom").to_numpy()
    left=50000-sal
    for lo,hi,l in ((0,0,"$0 left"),(100,300,"$100-300"),(400,1000,"$400-1000"),(1100,99999,">$1000")):
        mm=b&(left>=lo)&(left<=hi); k=int((top&mm).sum()); e=mm.sum()*top[b].sum()/b.sum()
        print(f"    clean boom {l:<10} n {int(mm.sum()):>5}  top-1% {k:>3} exp {e:5.1f} lift {k/e if e else 0:4.2f}")
