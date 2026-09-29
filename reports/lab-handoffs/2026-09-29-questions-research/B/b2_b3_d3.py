"""B2 predictable duds in the entered book; B3 p90 punt valuation vs plain mean; D3 residual availability loss."""
from common import *
out=[]
def P(*a):
    s=" ".join(str(x) for x in a); print(s); out.append(s)
FLEX_OK={"RB","WR","TE"}
def replacement(f, row, j, used_ids, by_pos):
    """Best PROJ-ranked (pre-lock) active same-slot player affordable within the row's salary slack, not already in the row."""
    p=f.pos.iat[j]; slack=50000-f.salary.to_numpy(float)[row].sum(); budget=f.salary.iat[j]+slack
    cands=by_pos[p]
    for k in cands:
        if k in used_ids or f.salary.iat[k]>budget: continue
        return k
    return None
for wk in (1,2,3):
    R=RUNS[wk]; cash=R["cash"]
    src=R["final"] if wk==1 else R["sat"]
    fe=attach_realized(load_frame(src),wk); er=entered_rows(wk,fe)
    ft=attach_realized(load_frame(R["t70"]),wk)
    t70s=dict(zip(ft.id,ft.status.astype(str))); t70p=dict(zip(ft.id,ft.proj.astype(float)))
    fe["status_t70"]=fe.id.map(t70s).fillna("absent"); fe["proj_t70"]=fe.id.map(t70p)
    st=fe.status.astype(str).str.upper()
    fe["cls_out_build"]=st.isin(["O","OUT","IR","D"])|fe.injury_status.astype(str).isin(["Out","Doubtful"])
    fe["cls_out_t70"]=fe.status_t70.str.upper().isin(["O","OUT","IR","D","ABSENT"])|(fe.proj_t70.fillna(0)<=0.01)&(fe.proj>3)
    fe["cls_backup_qb"]=(fe.pos=="QB")&(fe.depth_rank.fillna(1)>=2)
    fe["cls_deep"]=fe.pos.isin(["RB","WR","TE"])&(fe.depth_rank.fillna(1)>=3)
    fe["cls_sub1"]=fe.proj<1
    fe["cls_punt_p90"]=fe.pos.isin(SKILL)&(fe.salary<=4000)&(fe.proj_tourney>fe.proj+0.5)
    active_ok=~fe.cls_out_build&(fe.proj>=1)
    by_pos={p:list(fe.index[active_ok&(fe.pos==p)].to_numpy()[np.argsort(-fe.proj.to_numpy()[active_ok&(fe.pos==p)])]) for p in ("QB","RB","WR","TE","DST")}
    se=lineup_stats(er,fe)
    P(f"\n=== WEEK {wk} entered book ({len(er)} rows, valued on {os.path.basename(src)}; T-70 statuses from {os.path.basename(R['t70'])}) ===")
    classes=[("OUT/D/IR at build",fe.cls_out_build),("OUT/D/IR/absent by T-70 frame",fe.cls_out_t70),("backup QB (depth>=2)",fe.cls_backup_qb),("depth>=3 RB/WR/TE",fe.cls_deep),("sub-1 projection",fe.cls_sub1),("p90-valued punt (<=$4k skill)",fe.cls_punt_p90)]
    real=fe.realized.to_numpy(float); proj=fe.proj.to_numpy(float); pt=fe.proj_tourney.to_numpy(float)
    P(f"{'class':<32}{'rows':>6}{'slots':>6}{'dud slots(<5)':>14}{'val-real/row':>13}{'repl gain/row':>14}{'mean real':>10}")
    anyd=np.zeros(len(er),bool); anygain=np.zeros(len(er))
    for name,m in classes:
        mv=m.to_numpy()
        rows=0; slots=0; duds=0; lost=0.0; gain=0.0
        for i,row in enumerate(er):
            hit=[j for j in row if mv[j]]
            if hit: rows+=1; slots+=len(hit)
            d=[j for j in hit if real[j]<5]
            if d:
                duds+=len(d); anyd[i]=True
                used=set(row)
                for j in d:
                    val=pt[j] if name.startswith("p90") else proj[j]
                    lost+=val-real[j]
                    k=replacement(fe,row,j,used,by_pos)
                    if k is not None: g=real[k]-real[j]; gain+=g; anygain[i]+=g; used.add(k)
        P(f"{name:<32}{rows:>6}{slots:>6}{duds:>14}{(lost/max(rows,1)):>13.1f}{(gain/max(rows,1)):>14.1f}{(se.realized[[bool(x) for x in (np.array([any(mv[j] and real[j]<5 for j in row) for row in er]))]].mean() if duds else float('nan')):>10.1f}")
    P(f"rows with ANY predictable dud (scored <5): {anyd.sum()} of {len(er)} ({100*anyd.mean():.0f}%); their realized mean {se.realized[anyd].mean():.1f} vs clean rows {se.realized[~anyd].mean():.1f}; replacement gain summed over those rows {anygain[anyd].sum():.0f} pts = {anygain[anyd].sum()/len(er):.1f} per entered row (all rows) / {anygain[anyd].mean():.1f} per affected row")
    # punt count per entered row
    punt=(fe.pos.isin(SKILL)&(fe.salary<=4000)).to_numpy()
    npunt=np.array([int(punt[row].sum()) for row in er])
    g=pd.DataFrame(dict(n=npunt,real=se.realized.values,proj=se.proj.values)).groupby("n").agg(rows=("real","size"),proj=("proj","mean"),real=("real","mean"),cash=("real",lambda s:100*(s>=cash).mean()))
    P("entered rows by number of <=$4k skill players: "+" | ".join(f"{k}: rows {int(r.rows)} proj {r.proj:.1f} real {r.real:.1f} cash {r.cash:.0f}%" for k,r in g.iterrows()))

    # ---------- B3 on the Saturday pool ----------
    fs=attach_realized(load_frame(R["sat"]),wk); cs,rs=load_cands(R["sat"],fs); ss=lineup_stats(rs,fs); ss["fam"]=cs.fam.values
    punt=(fs.pos.isin(SKILL)&(fs.salary<=4000)).to_numpy(); real=fs.realized.to_numpy(float); proj=fs.proj.to_numpy(float); pt=fs.proj_tourney.to_numpy(float)
    npunt=np.array([int(punt[row].sum()) for row in rs]); ss["npunt"]=npunt
    P(f"\n--- B3 week {wk}: Saturday pool, lev rows (built on proj_tourney = p90 valuation for <=$4k skill) and boom rows, by number of punts ---")
    for fam in ("lev","boom"):
        m=ss.fam.values==fam
        g=ss[m].groupby("npunt").agg(rows=("realized","size"),proj=("proj","mean"),proj_t=("proj_t","mean"),real=("realized","mean"),cash=("realized",lambda s:100*(s>=cash).mean()),best=("realized","max"))
        P(f"  {fam}: "+" | ".join(f"{k} punts: n {int(r.rows)} proj {r.proj:.1f} (tourney {r.proj_t:.1f}) real {r.real:.1f} cash {r.cash:.0f}% best {r.best:.0f}" for k,r in g.iterrows()))
    # top-K mean book from lev rows by punt count (mean track uses proj, not proj_tourney)
    K={1:80,2:97,3:144}[wk]
    for lab,m in (("lev all",ss.fam.values=="lev"),("lev <=2 punts",(ss.fam.values=="lev")&(npunt<=2)),("lev >=4 punts",(ss.fam.values=="lev")&(npunt>=4)),("boom all",ss.fam.values=="boom")):
        idx=np.where(m)[0]
        if len(idx)<K: P(f"  top-{K}-mean from {lab}: only {len(idx)} rows"); continue
        s=idx[topk_by_mean(rs[idx],ss.proj.values[idx],K)]
        P(f"  top-{K}-mean book from {lab:<14}: proj {ss.proj.values[s].mean():6.1f} real {ss.realized.values[s].mean():6.1f} cash {100*(ss.realized.values[s]>=cash).mean():3.0f}% punts/row {npunt[s].mean():.1f}")
    # punt players by valuation bucket (pre-lock valuation -> realized)
    lev_usage=np.bincount(rs[ss.fam.values=="lev"].ravel(),minlength=len(fs))/max((ss.fam.values=="lev").sum(),1)
    boom_usage=np.bincount(rs[ss.fam.values=="boom"].ravel(),minlength=len(fs))/max((ss.fam.values=="boom").sum(),1)
    pp=fs[punt].copy(); pp["lev_usage"]=lev_usage[punt]; pp["boom_usage"]=boom_usage[punt]
    pp["vbucket"]=pd.cut(pp.proj_tourney,[-1,8,12,15,18,40],labels=["<8","8-12","12-15","15-18","18+"])
    g=pp.groupby("vbucket",observed=True).agg(n=("proj","size"),proj=("proj","mean"),val=("proj_tourney","mean"),real=("realized","mean"),p10=("realized",lambda s:100*(s>=10).mean()),played=("realized",lambda s:100*(s>0).mean()),lev_slots=("lev_usage","sum"),boom_slots=("boom_usage","sum"))
    P("  punt players (<=$4k skill) by p90 valuation bucket: "+" | ".join(f"{k}: n {int(r.n)} mean proj {r.proj:.1f} val {r.val:.1f} real {r.real:.1f} P(10+) {r.p10:.0f}% played {r.played:.0f}% lev slots/row {r.lev_slots:.2f} boom {r.boom_slots:.2f}" for k,r in g.iterrows()))
    pp["pbucket"]=pd.cut(pp.proj,[-1,1,3,5,8,40],labels=["<1","1-3","3-5","5-8","8+"])
    g=pp.groupby("pbucket",observed=True).agg(n=("proj","size"),proj=("proj","mean"),val=("proj_tourney","mean"),real=("realized","mean"),p10=("realized",lambda s:100*(s>=10).mean()),lev_slots=("lev_usage","sum"),boom_slots=("boom_usage","sum"))
    P("  punt players by MEAN projection bucket: "+" | ".join(f"{k}: n {int(r.n)} proj {r.proj:.1f} val {r.val:.1f} real {r.real:.1f} P(10+) {r.p10:.0f}% lev slots/row {r.lev_slots:.2f} boom {r.boom_slots:.2f}" for k,r in g.iterrows()))
    w=pp.lev_usage; 
    P(f"  lev-exposure-weighted punt slot: valuation {np.average(pp.proj_tourney,weights=w) if w.sum() else float('nan'):.1f}, mean proj {np.average(pp.proj,weights=w) if w.sum() else float('nan'):.1f}, realized {np.average(pp.realized,weights=w) if w.sum() else float('nan'):.1f}; punt slots per lev row {w.sum():.2f} -> valuation-minus-realized per lev row {(w*(pp.proj_tourney-pp.realized)).sum():.1f}, proj-minus-realized {(w*(pp.proj-pp.realized)).sum():.1f}")
    # rank quality: does the p90 valuation or the mean rank punts better?
    from scipy.stats import spearmanr
    pl=pp[pp.proj>=1]
    P(f"  among punts with proj>=1 (n={len(pl)}): spearman(valuation, realized) {spearmanr(pl.proj_tourney,pl.realized).statistic:+.3f}; spearman(mean proj, realized) {spearmanr(pl.proj,pl.realized).statistic:+.3f}; spearman(market, realized) {spearmanr(pl.market_points.fillna(pl.proj),pl.realized).statistic:+.3f}")
    # counterfactual: replace every punt in lev rows with best mean-proj same-pos player affordable
    active_ok=(~fs.status.astype(str).str.upper().isin(["O","OUT","IR","D"]))&(fs.proj>=1)
    by_pos={p:list(fs.index[active_ok&(fs.pos==p)].to_numpy()[np.argsort(-fs.proj.to_numpy()[active_ok&(fs.pos==p)])]) for p in ("QB","RB","WR","TE","DST")}
    lev_idx=np.where(ss.fam.values=="lev")[0]; gains=[]
    for i in lev_idx:
        row=rs[i]; used=set(row); g_=0.0
        for j in row:
            if punt[j] and proj[j]<5:
                k=replacement(fs,row,j,used,by_pos)
                if k is not None: g_+=real[k]-real[j]; used.add(k)
        gains.append(g_)
    gains=np.array(gains)
    P(f"  counterfactual (lev rows): swap each punt with mean proj<5 for the best mean-projected same-position player affordable in that row: mean realized change {gains.mean():+.1f}/row (share of rows improved {100*(gains>0).mean():.0f}%); note: same-slot swap, not a re-solve")

    # ---------- D3 residual availability loss ----------
    P(f"\n--- D3 week {wk}: players scoring 0 with projection > 3 ---")
    for lab,f,rx in (("entered book",fe,er),("Saturday pool",fs,rs)):
        usage=np.bincount(rx.ravel(),minlength=len(f))/len(rx)
        z=f[(f.realized<=0)&(f.proj>3)&(usage>0)].copy(); z["usage"]=usage[z.index]
        z["st"]=z.status.astype(str).replace({"None":"-","nan":"-"})+"/"+z.injury_status.astype(str).replace({"None":"-","nan":"-"})+"/"+z.roster_status.astype(str)
        z["cls"]=np.where(z.pos=="QB",np.where(z.depth_rank.fillna(1)>=2,"backup QB","starting QB"),np.where(z.depth_rank.fillna(1)>=2,"depth>=2 skill/DST","depth-1"))
        z["lost"]=z.usage*z.proj
        g=z.groupby("cls").agg(players=("proj","size"),proj_sum=("proj","sum"),lost_per_row=("lost","sum"),slots_per_row=("usage","sum"))
        P(f"  {lab}: {len(z)} zero-scorers with proj>3 used; projected points lost per row {z.lost.sum():.2f}; rows affected {100*np.mean([any((f.realized.to_numpy()[j]<=0)&(f.proj.to_numpy()[j]>3) for j in row) for row in rx]):.0f}%")
        for k,r in g.iterrows(): P(f"     {k:<20} players {int(r.players):>3}  slots/row {r.slots_per_row:.3f}  proj pts lost/row {r.lost_per_row:.2f}")
        top=z.sort_values("lost",ascending=False).head(8)
        P("     largest: "+"; ".join(f"{r.display_name} ({r.pos} ${int(r.salary)} proj {r.proj:.1f} st {r.st} depth {r.depth_rank} usage {100*r.usage:.1f}%)" for _,r in top.iterrows()))
open(os.path.join(HERE,"b2_b3_d3.out"),"w").write("\n".join(out))
