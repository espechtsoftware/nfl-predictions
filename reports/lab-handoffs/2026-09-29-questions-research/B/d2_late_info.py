"""D2: what arrives after T-70 - DK status changes by pull time, line moves, wind. Information times named."""
from common import *
out=[]
def P(*a):
    s=" ".join(str(x) for x in a); print(s); out.append(s)
d=pd.read_csv(os.path.join(DATA,"dk_status_pulls.csv"),dtype={"status":str})
d["pulled_at"]=pd.to_datetime(d.pulled_at); d["game_start"]=pd.to_datetime(d.game_start)
d["status"]=d.status.fillna("None").replace({"nan":"None"})
for wk in (1,2,3):
    R=RUNS[wk]; dg=R["dg"]; x=d[d.draft_group_id==dg].sort_values("pulled_at")
    lock=x.game_start.min(); t70=lock-pd.Timedelta(minutes=70)
    fs=attach_realized(load_frame(R["sat"]),wk); cs,rs=load_cands(R["sat"],fs)
    used=set(fs.dk_player_id.astype(int).values[np.unique(rs)])
    ft=load_frame(R["t70"])
    src=R["final"] if wk==1 else R["sat"]; fe=load_frame(src); er=entered_rows(wk,fe); ent=set(fe.dk_player_id.astype(int).values[np.unique(er)])
    usage=np.bincount(er.ravel(),minlength=len(fe))/len(er); umap=dict(zip(fe.dk_player_id.astype(int),usage))
    pulls=sorted(x.pulled_at.unique())
    P(f"\n=== WEEK {wk} dg {dg}: lock {lock} UTC, T-70 {t70}; {len(pulls)} DK pulls from {pulls[0]} to {pulls[-1]}; Saturday frame pulled {fs.pulled_at.iloc[0]}, T-70 frame pulled {ft.pulled_at.iloc[0]} ===")
    sun=[p for p in pulls if p.date()==lock.date()]
    P("  Sunday pulls (UTC): "+", ".join(p.strftime('%H:%M') for p in sun))
    # status transitions per player
    ch=[]
    for pid,g in x.groupby("dk_player_id"):
        g=g.sort_values("pulled_at"); prev=None
        for _,r in g.iterrows():
            if prev is not None and r.status!=prev: ch.append(dict(pid=pid,pname=r.display_name,pos=r.position,team=r.team_abbr,salary=r.salary,t=r.pulled_at,frm=prev,to=r.status,game=r.game_start))
            prev=r.status
    C=pd.DataFrame(ch)
    win=lambda a,b: C[(C.t>=a)&(C.t<b)] if len(C) else C
    satpull=fs.pulled_at.iloc[0].tz_convert(None) if fs.pulled_at.iloc[0].tzinfo else fs.pulled_at.iloc[0]
    t70pull=ft.pulled_at.iloc[0].tz_convert(None) if ft.pulled_at.iloc[0].tzinfo else ft.pulled_at.iloc[0]
    for lab,a,b in (("after Saturday frame pull, before T-70 frame pull",satpull,t70pull),("after T-70 frame pull, before lock",t70pull,lock),("after lock (late games)",lock,lock+pd.Timedelta(hours=6))):
        w=win(a,b)
        P(f"  status changes {lab}: {len(w)} (to O/OUT/IR/D: {int(w.to.isin(['O','OUT','IR','D']).sum())}; Q cleared: {int(((w.frm=='Q')&(w.to=='None')).sum())})")
        for _,r in w[w.to.isin(['O','OUT','IR','D'])|((w.frm=='Q')&(w.to=='None'))].iterrows():
            P(f"     {r.t.strftime('%H:%M')}Z {r.pname:<24}{r.pos:<4}{r.team:<4}${int(r.salary):<6}{r.frm}->{r.to}  game {r.game.strftime('%H:%M')}Z  in pool: {int(r.pid) in used}  entered rows: {100*umap.get(int(r.pid),0):.1f}%")
    # line moves and wind: Saturday frame vs T-70 frame
    gs=fs.groupby("game_id").agg(tot_sat=("total_line","first"),spr_sat=("spread_line","first"),wind=("wind_mph","first"),temp=("temp_f","first"),dome=("is_dome","first"))
    gt=ft.groupby("game_id").agg(tot_t70=("total_line","first"),spr_t70=("spread_line","first"))
    gg=gs.join(gt); gg["dtot"]=gg.tot_t70-gg.tot_sat
    P(f"  totals moved Sat->T-70: max |move| {gg.dtot.abs().max():.1f}; games moved >=1.0: {int((gg.dtot.abs()>=1).sum())} of {len(gg)}; wind>=12mph games: {list(gg.index[gg.wind>=12])} (wind {gg.wind.max():.0f} max)")
open(os.path.join(HERE,"d2_late_info.out"),"w").write("\n".join(out))
