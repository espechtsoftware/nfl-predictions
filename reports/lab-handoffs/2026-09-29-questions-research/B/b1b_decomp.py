"""B1b: who explains the entered-vs-top-mean gap (exact exposure decomposition), plus ownership/punt profile of each book."""
from common import *
out=[]
def P(*a):
    s=" ".join(str(x) for x in a); print(s); out.append(s)
for wk in (1,2,3):
    R=RUNS[wk]; K={1:80,2:97,3:144}[wk]; cash=R["cash"]
    src=R["final"] if wk==1 else R["sat"]
    fs=attach_realized(load_frame(R["sat"]),wk); cs,rs=load_cands(R["sat"],fs); st=lineup_stats(rs,fs)
    fe=attach_realized(load_frame(src),wk); er=entered_rows(wk,fe)
    sel=topk_by_mean(rs,st.proj.values,K)
    ue=np.bincount(er.ravel(),minlength=len(fe))/len(er)
    um=np.bincount(rs[sel].ravel(),minlength=len(fs))/len(sel)
    # align by player id
    E=pd.DataFrame(dict(id=fe.id,name=fe.display_name,pos=fe.pos,salary=fe.salary,proj=fe.proj,real=fe.realized,own=fe.field_own,u_ent=ue))
    M=pd.DataFrame(dict(id=fs.id,u_mean=um))
    d=E.merge(M,on="id",how="outer").fillna({"u_ent":0,"u_mean":0})
    d["contrib"]=(d.u_ent-d.u_mean)*d.real
    P(f"\n=== WEEK {wk}: entered book vs top-{K}-mean book, exact player decomposition (sum = realized gap {d.contrib.sum():+.1f}) ===")
    punt=(fe.pos.isin(SKILL)&(fe.salary<=4000)).to_numpy()
    for lab,rx,f in (("entered",er,fe),("top-K-mean",rs[sel],fs)):
        own=f.field_own.to_numpy(float)[rx].sum(1); pn=(f.pos.isin(SKILL)&(f.salary<=4000)).to_numpy()[rx].sum(1)
        pj=f.proj.to_numpy(float)[rx].sum(1); rl=f.realized.to_numpy(float)[rx].sum(1)
        sal=f.salary.to_numpy(float)[rx].sum(1); qbs=f.salary.to_numpy(float)[rx][:,0] if False else None
        P(f"  {lab:<12} proj {pj.mean():6.1f} real {rl.mean():6.1f} resid {rl.mean()-pj.mean():+6.1f} | Milly ownership sum {own.mean():5.1f} | punts/row {pn.mean():.2f} | salary {sal.mean():.0f} | distinct players {len(np.unique(rx))}")
    w=d.reindex(d.contrib.abs().sort_values(ascending=False).index).head(12)
    P("  largest contributors (exposure entered vs top-mean, realized, contribution):")
    for _,r in w.iterrows(): P(f"     {r['name']:<24}{r.pos:<4}${int(r.salary):<6}ent {100*r.u_ent:5.1f}% mean {100*r.u_mean:5.1f}%  proj {r.proj:5.1f} real {r.real:5.1f}  own {r.own:5.1f}%  contrib {r.contrib:+6.2f}")
    ov=d[d.u_ent>d.u_mean]; un=d[d.u_ent<d.u_mean]
    P(f"  over-exposed (vs top-mean) total {ov.contrib.sum():+.1f}; under-exposed total {un.contrib.sum():+.1f}")
    # residual by ownership tercile within the pool: do chalky rows out-realize their projection?
    own_pool=fs.field_own.to_numpy(float)[rs].sum(1); resid=st.realized.values-st.proj.values
    q=pd.qcut(own_pool,3,labels=["low own","mid","high own"])
    g=pd.DataFrame(dict(q=q,resid=resid,real=st.realized.values,proj=st.proj.values)).groupby("q",observed=True).agg(n=("resid","size"),proj=("proj","mean"),real=("real","mean"),resid=("resid","mean"))
    P("  pool residual (realized - projected) by Millionaire-ownership tercile of the row: "+" | ".join(f"{k}: proj {r.proj:.1f} real {r.real:.1f} resid {r.resid:+.1f}" for k,r in g.iterrows()))
    pn=(fs.pos.isin(SKILL)&(fs.salary<=4000)).to_numpy()[rs].sum(1)
    g=pd.DataFrame(dict(q=pn,resid=resid,proj=st.proj.values)).groupby("q").agg(n=("resid","size"),proj=("proj","mean"),resid=("resid","mean"))
    P("  pool residual by punts per row: "+" | ".join(f"{k}: n {int(r.n)} proj {r.proj:.1f} resid {r.resid:+.1f}" for k,r in g.iterrows()))
open(os.path.join(HERE,"b1b_decomp.out"),"w").write("\n".join(out))
