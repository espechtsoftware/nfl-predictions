"""Second pass: class fix, A3 restricted to the Millionaires, winners-study ratio curve with field-strength adjustment,
ticket-line entry-count lifts, 2026 total ROI (percent only)."""
import json, numpy as np, pandas as pd
exec(open('analyze.py').read().split("# ---- Table A1a")[0])   # reuse loaders/helpers (lad, fl, lr, br, tiers, payout, places, ticket_places, md, P/out)
out.clear()
def cls(cid):
    c=lad[cid]; n=c['maximumEntries']
    if n>=160000: return '1 Millionaire (162k-832k)'
    if 80000<=n<160000: return '2 Large GPP 20/150-max (83k-159k)'
    if 9000<=n<=25000: return '3 Mid GPP single/5-max (9.5k-24k)'
    if n==5000: return '4 FFWC qualifier 5,000 (260 paid, 1 ticket)'
    if n==2378: return '5 Supersat 2,378 / 25 tickets (20-max)'
    if n==594: return '6 Supersat 594 / 25 tickets (17-max)'
    if n==190: return '7 Supersat 190 / 2 tickets (5-max)'
    if n==402: return '8 Satellite 402 / 1 ticket (12-max)'
    if n in (148,79,72,85,68): return '9 Satellite 59-148 / 1-4 tickets (2-4-max)'
    if n==11: return '10 Satellite 11 / 1 ticket (single)'
    return 'other'
cmap={cid:cls(cid) for cid in lad}; week={cid:int(fl.loc[cid,'week']) for cid in lad}
MILLY={'193028206','195648007','195905122'}
LINES={(r.contest_id,int(r.k)):float(r.line) for r in lr.itertuples()}
mp=pd.read_csv('milly_pct.csv',dtype={'cid':str})
MSH={(r.cid,r.kind):r.milly_share_pct/100 for r in mp.itertuples()}

# ratio curve (share of book rows over a field line / field base rate) by Millionaire-field percentile
CURVES={'PMO_X50 as armed (winners study §3.2 + laptop 16:54)':{0.50:1.07,0.77:1.12,0.89:1.20,0.95:1.33,0.99:1.78,0.998:2.22},
        'PMO_X50 + blended ownership λ0.20 (winners study §4.1)':{0.50:1.15,0.77:1.41,0.89:1.48,0.95:1.53,0.99:2.16,0.998:2.22},
        'MEAN (laptop 16:54)':{0.89:0.95,0.99:1.02,0.998:1.30},'EMAX, Weeks 1-3 form (laptop 16:54)':{0.89:0.82,0.99:1.02,0.998:1.30}}
def ratio(curve,p):
    ks=sorted(curve); vs=[curve[k] for k in ks]
    if p<=ks[0]: return vs[0]
    if p>=ks[-1]: return vs[-1]
    return float(np.interp(p,ks,vs))

# ---- T4b: transfer with field strength: P(row >= line) = ratio(p_M) * (1-p_M), where 1-p_M = share of the same-week
# Millionaire field at or above the contest's line (so the satellite's stronger field is priced in)
recs=[]
for cid in lad:
    n=int(fl.loc[cid,'n']); ts=tiers(cid); pl=places(cid); tp=ticket_places(cid)
    s_cash=MSH[(cid,'cash')]; s_tick=MSH[(cid,'ticket')]
    for name,curve in CURVES.items():
        pc=min(1,ratio(curve,1-s_cash)*s_cash); pt=min(1,ratio(curve,1-s_tick)*s_tick)
        # EV: single-tier -> pt*mult; multi-tier -> use in-contest tiers, base share of Milly field at each tier line
        if len(ts)==1: ev=pt*ts[0][2]; ev_ex=ev
        else:
            cum=[]; 
            for lo,hi,m in ts:
                ln=LINES.get((cid,hi),np.nan)
                # share of the Milly field >= this tier's line: approximate by in-contest share hi/n scaled by field strength at cash line
                base=(hi/n)*(s_cash/(pl/n))
                cum.append(min(1,ratio(curve,1-base)*base))
            cum=np.maximum.accumulate(cum); prev=0; ev=0; ev_ex=0
            for i,((lo,hi,m),c) in enumerate(zip(ts,cum)):
                ev+=(c-prev)*m
                if hi>10: ev_ex+=(c-prev)*m
                prev=c
        recs.append(dict(cls=cmap[cid],form=name,cid=cid,field_rate=100*pl/n,break_even=100/ts[-1][2] if len(ts)==1 else np.nan,P_cash=100*pc,P_ticket=100*pt,ROI_pct=100*(ev-1),ROI_ex_top10_pct=100*(ev_ex-1)))
T=pd.DataFrame(recs).groupby(['cls','form']).agg(contests=('cid','size'),field_rate=('field_rate','mean'),break_even_rate=('break_even','mean'),P_cash=('P_cash','mean'),P_ticket=('P_ticket','mean'),ROI_pct=('ROI_pct','mean'),ROI_ex_top10_pct=('ROI_ex_top10_pct','mean')).reset_index()
P('## T4b. Panel-ratio transfer, field-strength adjusted (each contest line placed in the same-week Millionaire field; ratio curve in Millionaire-field percentile). Break-even rate = fee / ticket value (single-tier contests).\n'); P(T.round(2).pipe(md)); P()

# ---- A3 restricted to the three Millionaires
rows=[]
for r in br[br.contest_id.isin(MILLY)].itertuples():
    cid=r.contest_id; m=payout(cid,int(r.rank),int(r.ties))
    rows.append(dict(week=r.week,book=r.book,score=r.score,rank=r.rank,n=r.n,mult=m,cash=r.rank<=places(cid),top1000=r.rank<=1000,top100=r.rank<=100,top10=r.rank<=10,top10000=r.rank<=10000))
M=pd.DataFrame(rows)
def a3(d): return pd.Series(dict(rows=len(d),book_mean=d.score.mean(),P_cash=100*d.cash.mean(),P_top10000=100*d.top10000.mean(),P_top1000=100*d.top1000.mean(),P_top100=100*d.top100.mean(),P_top10=100*d.top10.mean(),E_mult=d.mult.mean(),ROI_pct=100*(d.mult.mean()-1),best_rank=int(d['rank'].min()),median_rank_pct=100*np.median(d['rank'])/d.n.iloc[0],P_mult_ge2=100*(d.mult>=2).mean(),max_mult=d.mult.max()))
P('## T5b. A3: one Millionaire seat drawn at random from each book, placed in that week Millionaire (realized field; ties split per DK rule)\n'); P(M.groupby(['week','book']).apply(a3,include_groups=False).round(2).pipe(md,index=True))
d=M[M.book=='entered']; P(f'Pooled entered rows W1-3 (n={len(d)}): P_cash {100*d.cash.mean():.1f}%, P_top10000 {100*d.top10000.mean():.2f}%, P_top1000 {100*d.top1000.mean():.2f}%, P_top100 0, P_top10 0, E[mult] {d.mult.mean():.3f} (ROI {100*(d.mult.mean()-1):.1f}%)'); P()
# Week-4 form projection for a Milly seat: P(rank<=k) = ratio(p) * k/n with p in Milly percentile, W3 ladder
cid='195905122'; n=int(fl.loc[cid,'n']); ts=tiers(cid)
P('Week-4 form, if the panel curve transfers (W3 Millionaire ladder and field size):')
for name,curve in CURVES.items():
    cum=np.maximum.accumulate([min(1,ratio(curve,1-hi/n)*hi/n) for lo,hi,m in ts]); prev=0; ev=0; ev_ex=0
    for (lo,hi,m),c in zip(ts,cum):
        ev+=(c-prev)*m; ev_ex+= (c-prev)*m if hi>10 else 0; prev=c
    pk=lambda k: min(1,ratio(curve,1-k/n)*k/n)
    P(f'- {name}: P_cash {100*pk(places(cid)):.1f}%, P_top10000 {100*pk(10000):.2f}%, P_top1000 {100*pk(1000):.2f}%, P_top100 {100*pk(100):.3f}%, P_top10 {100*pk(10):.4f}%; E[mult] {ev:.2f} (ex top-10 {ev_ex:.2f}); note ratios beyond p99.8 are held flat at the last measured value')
P()

# ---- F4 at the ticket line and cash line per class
tb=pd.read_csv('ticket_buckets.csv',dtype={'contest_id':str}); tb['cls']=tb.contest_id.map(cmap)
F=tb.groupby(['cls','bucket']).agg(rows=('n_rows','sum'),cash_rows=('cash_rows','sum'),ticket_rows=('ticket_rows','sum')).reset_index()
tot=F.groupby('cls').agg(rows_all=('rows','sum'),cash_all=('cash_rows','sum'),ticket_all=('ticket_rows','sum'))
F=F.join(tot,on='cls'); F['share_field_pct']=100*F.rows/F.rows_all; F['cash_rate_pct']=100*F.cash_rows/F.rows; F['ticket_rate_pct']=100*F.ticket_rows/F.rows
F['cash_lift']=(F.cash_rows/F.cash_all)/(F.rows/F.rows_all); F['ticket_lift']=(F.ticket_rows/F.ticket_all)/(F.rows/F.rows_all)
P('## T7b. F4/A5: per-entry cash and ticket rate by entry-count bucket and class (lift = bucket rate / class rate; 1.0 = flat). Ticket = first place in single-ticket satellites and the FFWC qualifier, all paid places in multi-ticket supersats, cash in the GPPs.\n')
P(F[['cls','bucket','rows','share_field_pct','cash_rate_pct','cash_lift','ticket_rows','ticket_rate_pct','ticket_lift']].round(2).pipe(md)); P()

# ---- 2026 total ROI (W1+W2 private CSV + W3 from ladders); percent only
b=pd.read_csv('/home/erich/week2-sunday/ENTERED/draftkings-contest-entry-history-week2.csv')
def money(s): return pd.to_numeric(s.astype(str).str.replace(r'[\$,]','',regex=True),errors='coerce').fillna(0)
b['fee']=money(b.Entry_Fee); b['won']=money(b.Winnings_Non_Ticket)+money(b.Winnings_Ticket); b['date']=pd.to_datetime(b.Contest_Date_EST)
g=b[b.date>='2026-09-01']
w3=pd.read_csv('our_w3_entries.csv'); fee_by={'milly20':'195905122','ffwc18':'195923609','supersat25lo':'195920743','supersat25hi':'195920744','sat13mega':'195920605','supersat2':'195920727','ffwc':'195920781','wildcat':'195920803','sat20':'195920630'}
w3['fee']=w3.cls.map(lambda c: lad[fee_by[c]]['entryFee']); w3['won']=np.where((w3.cls=='sat20')&(w3['rank']==1),w3.fee*10,0.0)
fees=g.fee.sum()+w3.fee.sum(); won=g.won.sum()+w3.won.sum()
P(f'## 2026 to date (W1-3, 381 entries): ROI {100*(won/fees-1):.1f}%; W1 {100*(g[g.date<"2026-09-15"].won.sum()/g[g.date<"2026-09-15"].fee.sum()-1):.1f}%, W2 {100*(g[g.date>="2026-09-15"].won.sum()/g[g.date>="2026-09-15"].fee.sum()-1):.1f}%, W3 {100*(w3.won.sum()/w3.fee.sum()-1):.1f}%; share of the three-week stake by week: W1 {100*g[g.date<"2026-09-15"].fee.sum()/fees:.0f}%, W2 {100*g[g.date>="2026-09-15"].fee.sum()/fees:.0f}%, W3 {100*w3.fee.sum()/fees:.0f}%')
open('analysis_out3.md','w').write("\n".join(out)); print("\n".join(out))
