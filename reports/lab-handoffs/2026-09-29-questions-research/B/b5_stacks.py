"""B5: the stack mandate on the MEAN track - our pools and the field, by stack depth / bring-back / distinct games."""
from common import *
out=[]
def P(*a):
    s=" ".join(str(x) for x in a); print(s); out.append(s)
for wk in (1,2,3):
    R=RUNS[wk]; cash=R["cash"]; K={1:80,2:97,3:144}[wk]
    fs=attach_realized(load_frame(R["sat"]),wk); cs,rs=load_cands(R["sat"],fs); st=lineup_stats(rs,fs); st["fam"]=cs.fam.values
    P(f"\n=== WEEK {wk} our Saturday pool ({len(st)}) : realized by construction feature (cash line {cash}) ===")
    for col in ("depth","depth_rb","bringback","games"):
        g=st.groupby(col).agg(n=("realized","size"),proj=("proj","mean"),real=("realized","mean"),cash=("realized",lambda s:100*(s>=cash).mean()),top=("realized",lambda s:s.max()))
        P(f"  by {col}: "+" | ".join(f"{k}: n {int(r.n)} proj {r.proj:.1f} real {r.real:.1f} cash {r.cash:.0f}% best {r.top:.0f}" for k,r in g.iterrows()))
    # control for projected mean: within top projected quintile
    q5=st.proj>=st.proj.quantile(0.8)
    g=st[q5].groupby("depth").agg(n=("realized","size"),proj=("proj","mean"),real=("realized","mean"),cash=("realized",lambda s:100*(s>=cash).mean()))
    P("  top projected quintile only, by depth: "+" | ".join(f"{k}: n {int(r.n)} proj {r.proj:.1f} real {r.real:.1f} cash {r.cash:.0f}%" for k,r in g.iterrows()))
    g=st[q5].groupby("games").agg(n=("realized","size"),proj=("proj","mean"),real=("realized","mean"),cash=("realized",lambda s:100*(s>=cash).mean()))
    P("  top projected quintile only, by games: "+" | ".join(f"{k}: n {int(r.n)} proj {r.proj:.1f} real {r.real:.1f} cash {r.cash:.0f}%" for k,r in g.iterrows()))
    # mean-track book restricted by construction
    for lab,m in (("all",np.ones(len(st),bool)),("depth==2",st.depth.values==2),("depth>=3",st.depth.values>=3),("games>=5",st.games.values>=5),("games<=4",st.games.values<=4)):
        idx=np.where(m)[0]
        if len(idx)<K: P(f"  top-{K} mean book from {lab}: only {len(idx)} rows"); continue
        s=idx[topk_by_mean(rs[idx],st.proj.values[idx],K)]
        P(f"  top-{K} mean book from {lab:<9}: proj {st.proj.values[s].mean():6.1f} real {st.realized.values[s].mean():6.1f} cash {100*(st.realized.values[s]>=cash).mean():4.0f}% best {st.realized.values[s].max():5.1f}")
    # field
    fd=field_sample(wk)
    pos=dict(zip(fs.display_name.astype(str),fs.pos)); team=dict(zip(fs.display_name.astype(str),fs.team)); game=dict(zip(fs.display_name.astype(str),fs.game_id)); proj=dict(zip(fs.display_name.astype(str),fs.proj.astype(float)))
    rows=[]
    for _,r in fd.iterrows():
        n=r.names
        if any(x not in pos for x in n): continue
        p=[pos[x] for x in n]; t=[team[x] for x in n]; g=[game[x] for x in n]
        qi=[i for i in range(len(n)) if p[i]=="QB"]
        if not qi: continue
        qt=t[qi[0]]; qg=g[qi[0]]
        d=sum(1 for i in range(len(n)) if t[i]==qt and p[i] in ("WR","TE"))
        bb=sum(1 for i in range(len(n)) if g[i]==qg and t[i]!=qt and p[i] in SKILL)
        rows.append(dict(points=r.points,top1=bool(r.top1),depth=d,bringback=min(bb,1),bb_n=bb,games=len(set(g)),proj=sum(proj[x] for x in n)))
    F=pd.DataFrame(rows); rnd=F[~F.top1]; top=F[F.top1]
    P(f"  FIELD (2% random sample n={len(rnd)}; top-1% n={len(top)}): realized mean / share>=cash / top-1% lift by feature")
    for col in ("depth","bringback","games"):
        g=rnd.groupby(col).agg(n=("points","size"),proj=("proj","mean"),real=("points","mean"),cash=("points",lambda s:100*(s>=cash).mean()))
        share=rnd[col].value_counts(normalize=True); tshare=top[col].value_counts(normalize=True)
        P(f"   by {col}: "+" | ".join(f"{k}: field share {100*share.get(k,0):.0f}% proj {r.proj:.1f} real {r.real:.1f} cash {r.cash:.0f}% top1-lift {tshare.get(k,0)/share.get(k,1e-9):.2f}" for k,r in g.iterrows()))
    m2=(rnd.depth>=2)&(rnd.bringback==1)
    P(f"   field rows with our mandate (depth>=2 AND bring-back): {100*m2.mean():.1f}% of field, real {rnd[m2].points.mean():.1f} vs others {rnd[~m2].points.mean():.1f}; cash {100*(rnd[m2].points>=cash).mean():.0f}% vs {100*(rnd[~m2].points>=cash).mean():.0f}%; top-1% share {100*((top.depth>=2)&(top.bringback==1)).mean():.1f}%")
    # field: within a projected-sum band (control for projection), by depth
    hi=rnd[rnd.proj>=rnd.proj.quantile(0.8)]
    g=hi.groupby("depth").agg(n=("points","size"),real=("points","mean"),cash=("points",lambda s:100*(s>=cash).mean()))
    P("   field top projected quintile, by depth: "+" | ".join(f"{k}: n {int(r.n)} real {r.real:.1f} cash {r.cash:.0f}%" for k,r in g.iterrows()))
    g=hi.groupby("games").agg(n=("points","size"),real=("points","mean"),cash=("points",lambda s:100*(s>=cash).mean()))
    P("   field top projected quintile, by games: "+" | ".join(f"{k}: n {int(r.n)} real {r.real:.1f} cash {r.cash:.0f}%" for k,r in g.iterrows()))
open(os.path.join(HERE,"b5_stacks.out"),"w").write("\n".join(out))
