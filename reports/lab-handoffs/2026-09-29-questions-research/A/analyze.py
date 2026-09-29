"""A-theme analysis. Inputs: ladders_2026_w1w3.json (DK public API), field_lines.csv, lines_at_ranks.csv, book_ranks.csv,
book_scores.csv, entry_buckets.csv, our_w3_entries.csv. Output: tables (markdown) to analysis_out.md. No dollar output."""
import json, numpy as np, pandas as pd
pd.set_option('display.width',250); pd.set_option('display.max_columns',40)
lad=json.load(open('ladders_2026_w1w3.json'))
fl=pd.read_csv('field_lines.csv',dtype={'contest_id':str}).set_index('contest_id')
lr=pd.read_csv('lines_at_ranks.csv',dtype={'contest_id':str})
br=pd.read_csv('book_ranks.csv',dtype={'contest_id':str})
bk=pd.read_csv('entry_buckets.csv',dtype={'contest_id':str})
out=[]

def md(df,index=False):
    df=df.copy()
    if index: df=df.reset_index()
    cols=list(df.columns); lines=["| "+" | ".join(str(c) for c in cols)+" |","|"+"|".join("---" for _ in cols)+"|"]
    for _,r in df.iterrows(): lines.append("| "+" | ".join(("%g"%v if isinstance(v,float) else str(v)) for v in r.values)+" |")
    return "\n".join(lines)
def P(*a): out.append(" ".join(str(x) for x in a))

# ---- per-contest ladder as (maxPosition -> multiple of fee), tie-aware payout
def tiers(cid):
    c=lad[cid]; fee=c['entryFee']; ps=c['payoutSummary'] or []
    return [(t['minPosition'],t['maxPosition'],t['payoutDescriptions'][0]['value']/fee) for t in ps]
def mult_at(cid,pos):
    for lo,hi,m in tiers(cid):
        if lo<=pos<=hi: return m
    return 0.0
def payout(cid,rank,ties):
    # our hypothetical entry joins a tie group of size ties+1 occupying rank..rank+ties; DK splits equally
    g=ties+1; return sum(mult_at(cid,p) for p in range(rank,rank+g))/g
def places(cid): return sum(hi-lo+1 for lo,hi,m in tiers(cid))
def pool_ratio(cid): c=lad[cid]; return c['totalPayouts']/(c['entryFee']*c['maximumEntries'])
def ticket_places(cid):
    # single-tier contests: all places are tickets; FFWC qualifier: place 1 only (ticket value >> rest)
    ts=tiers(cid); return ts[0][1] if len(ts)>1 and ts[0][2]>100 else places(cid)

# ---- class map (2026 actual contests)
def cls(cid):
    c=lad[cid]; n=c['maximumEntries']; nm=c['name']; pl=places(cid)
    if n>=150000: return '1 Millionaire (160k-830k, 150-max)'
    if 80000<=n<150000: return '2 Large GPP 20/150-max (83k-158k)'
    if 9000<=n<=25000: return '3 Mid GPP single/5-max (9.5k-24k)'
    if n==5000: return '4 FFWC qualifier 5,000 (260 paid, 1 ticket)'
    if n==2378: return '5 Supersat 2,378 / 25 tickets (20-max)'
    if n==594: return '6 Supersat 594 / 25 tickets (17-max)'
    if n==190: return '7 Supersat 190 / 2 tickets (5-max)'
    if n==402: return '8 Satellite 402 / 1 ticket (12-max)'
    if n in (148,79,72,85,68): return '9 Satellite 59-148 / 1-4 tickets (2-4-max)'
    if n==11: return '10 Satellite 11 / 1 ticket (single)'
    return 'other'
cmap={cid:cls(cid) for cid in lad}
week={cid:int(fl.loc[cid,'week']) for cid in lad}

# ---- Table A1a: per contest class per week, field stats and lines as multiples of field mean
LINES={(r.contest_id,int(r.k)):float(r.line) for r in lr.itertuples()}
def line(cid,k): return LINES.get((cid,k),np.nan)
recs=[]
for cid in lad:
    n=int(fl.loc[cid,'n']); mean=fl.loc[cid,'mean']; pl=places(cid); tp=ticket_places(cid)
    recs.append(dict(week=week[cid],cls=cmap[cid],cid=cid,n=n,field_mean=mean,sd=fl.loc[cid,'sd'],paid_pct=100*pl/n,cash_line=line(cid,pl),ticket_line=line(cid,tp),ticket_pct=100*tp/n,
                     pool_ratio=pool_ratio(cid),top_mult=tiers(cid)[0][2],winner=fl.loc[cid,'top1']))
A=pd.DataFrame(recs)
A['cash_x']=A.cash_line/A.field_mean; A['ticket_x']=A.ticket_line/A.field_mean; A['winner_x']=A.winner/A.field_mean
milly_mean={w:A[(A.week==w)&(A.cls.str.startswith('1 '))].field_mean.iloc[0] for w in (1,2,3)}
A['field_vs_milly']=A.apply(lambda r:r.field_mean/milly_mean[r.week],axis=1)
g=A.groupby(['week','cls']).agg(contests=('cid','size'),n=('n','first'),field_mean=('field_mean','mean'),sd=('sd','mean'),field_vs_milly=('field_vs_milly','mean'),paid_pct=('paid_pct','first'),cash_x=('cash_x','mean'),ticket_pct=('ticket_pct','first'),ticket_x=('ticket_x','mean'),winner_x=('winner_x','mean'),pool_ratio=('pool_ratio','first'),top_mult=('top_mult','first')).reset_index()
P('## T1. Field lines per class per week (realized standings; lines as multiples of that contest field mean)\n'); P(g.round(3).pipe(md)); P()

# ---- our books placed: per class x week x book
rows=[]
for _,r in br.iterrows():
    cid=r.contest_id; m=payout(cid,int(r['rank']),int(r.ties)); pl=places(cid); tp=ticket_places(cid)
    rows.append(dict(week=r.week,book=r.book,i=r.i,score=r.score,cid=cid,cls=cmap[cid],n=r.n,rank=r['rank'],mult=m,cash=r['rank']<=pl,ticket=r['rank']<=tp,top1000=r['rank']<=1000,top100=r['rank']<=100,top10=r['rank']<=10,
                     field_mean=fl.loc[cid,'mean']))
B=pd.DataFrame(rows); B['x_mean']=B.score/B.field_mean
# base rates
base=A.set_index('cid')
def summ(d):
    cid=d.name[3]
    return pd.Series(dict(rows=len(d),book_mean_x=d.x_mean.mean(),P_cash=100*d.cash.mean(),base_cash=base.loc[cid,'paid_pct'],cash_ratio=d.cash.mean()/(base.loc[cid,'paid_pct']/100),
                          P_ticket=100*d.ticket.mean(),base_ticket=base.loc[cid,'ticket_pct'],ticket_ratio=d.ticket.mean()/(base.loc[cid,'ticket_pct']/100),ROI_pct=100*(d.mult.mean()-1)))
S=B.groupby(["week","book","cls","cid"]).apply(summ, include_groups=False).reset_index()
S2=S.groupby(['week','book','cls']).agg(contests=('cid','size'),rows=('rows','first'),book_mean_x=('book_mean_x','mean'),P_cash=('P_cash','mean'),base_cash=('base_cash','mean'),cash_ratio=('cash_ratio','mean'),P_ticket=('P_ticket','mean'),base_ticket=('base_ticket','mean'),ticket_ratio=('ticket_ratio','mean'),ROI_pct=('ROI_pct','mean')).reset_index()
P('## T2. Our books placed in every same-week contest (hypothetical entry of every book row into each contest of the class; realized fields; averaged over the class contests)\n'); P(S2.round(2).pipe(md)); P()

# ---- break-even shift: delta such that mean multiple == 1, using tier boundary lines (ignores ties)
TIERARR={}
for cid in lad:
    ts=tiers(cid); ln=np.array([line(cid,hi) for lo,hi,m in ts]); mm=np.array([m for lo,hi,m in ts])
    order=np.argsort(ln); TIERARR[cid]=(ln[order],mm[order])   # ascending lines; higher line = better tier
def ev_shift(cid,scores,delta):
    ln,mm=TIERARR[cid]; s=scores+delta
    idx=np.searchsorted(ln,s,side='right')-1   # highest line <= s  -> best tier reached
    out=np.where(idx>=0,mm[np.clip(idx,0,len(mm)-1)],0.0)
    return out.mean()
def solve(cid,scores):
    lo,hi=-60.0,150.0
    if ev_shift(cid,scores,hi)<1: return np.nan
    for _ in range(40):
        mid=(lo+hi)/2
        if ev_shift(cid,scores,mid)>=1: hi=mid
        else: lo=mid
    return hi
recs=[]
for (w,bkname),d in B.groupby(['week','book']):
    scores=d.drop_duplicates('i').score.values
    for cid in [c for c in lad if week[c]==w]:
        dl=solve(cid,scores); fm=fl.loc[cid,'mean']
        recs.append(dict(week=w,book=bkname,cls=cmap[cid],cid=cid,book_mean=scores.mean(),book_x=scores.mean()/fm,shift_needed=dl,needed_book_x=(scores.mean()+dl)/fm))
E=pd.DataFrame(recs).groupby(['week','book','cls']).agg(book_mean=('book_mean','first'),book_x=('book_x','mean'),shift_needed=('shift_needed','mean'),needed_book_x=('needed_book_x','mean')).reset_index()
P('## T3. Break-even: points to add to every row of the book (keeping its spread) for mean payout = 1x fee, and the book mean as a multiple of the field mean that implies\n'); P(E.round(2).pipe(md)); P()

# ---- Week-4 form transfer (panel ratios at p89/p99/p99.8 -> P(rank<=k) = ratio(p_k) * k/n)
ratios={'PMO_X50 (Week-4 main)':{0.89:1.22,0.99:1.77,0.998:2.22},'MEAN':{0.89:0.95,0.99:1.02,0.998:1.30},'EMAX (W1-3 form)':{0.89:0.82,0.99:1.02,0.998:1.30}}
def ratio(form,p):
    ks=sorted(ratios[form]); vs=[ratios[form][k] for k in ks]
    if p<=ks[0]: return vs[0]
    if p>=ks[-1]: return vs[-1]
    return float(np.interp(p,ks,vs))
recs=[]
for cid in lad:
    n=int(fl.loc[cid,'n']); ts=tiers(cid)
    for form in ratios:
        # cumulative P(rank<=hi) per tier, clipped monotone
        cum=[]; 
        for lo,hi,m in ts:
            p=1-hi/n; cum.append(min(1.0,ratio(form,p)*hi/n))
        cum=np.maximum.accumulate(cum)
        ev=0; prev=0
        for (lo,hi,m),c in zip(ts,cum):
            ev+=(c-prev)*m; prev=c
        ev_ex_top=ev-sum((c-p)*m for (lo,hi,m),c,p in list(zip(ts,cum,[0]+list(cum[:-1])))[:3])
        pl=places(cid); tp=ticket_places(cid)
        recs.append(dict(week=week[cid],cls=cmap[cid],cid=cid,form=form,line_pct=100*(1-pl/n),P_cash=100*min(1,ratio(form,1-pl/n)*pl/n),P_ticket=100*min(1,ratio(form,1-tp/n)*tp/n),ROI_pct=100*(ev-1),ROI_ex_top3_pct=100*(ev_ex_top-1),extrap=('yes' if (1-tp/n)>0.998 or (1-pl/n)<0.89 else 'no')))
T=pd.DataFrame(recs).groupby(['cls','form']).agg(contests=('cid','size'),line_pct=('line_pct','mean'),P_cash=('P_cash','mean'),P_ticket=('P_ticket','mean'),ROI_pct=('ROI_pct','mean'),ROI_ex_top3_pct=('ROI_ex_top3_pct','mean'),extrap=('extrap','first')).reset_index()
P('## T4. If the 36-slate panel ratios transfer (share of rows over a field line / field base rate: PMO_X50 1.22x@p89, 1.77x@p99, 2.22x@p99.8; MEAN 0.95/1.02/1.30; EMAX 0.82/1.02/1.30), expected P(cash), P(ticket) and ROI by class. extrap=yes means the line sits outside the measured p89-p99.8 grid (ratio held flat there).\n'); P(T.round(2).pipe(md)); P()

# ---- A3 Millionaire seat distribution
M=B[B.cls.str.startswith('1 ')]
def a3(d):
    return pd.Series(dict(rows=len(d),book_mean=d.score.mean(),P_cash=100*d.cash.mean(),P_top1000=100*d.top1000.mean(),P_top100=100*d.top100.mean(),P_top10=100*d.top10.mean(),E_mult=d.mult.mean(),best_rank=int(d['rank'].min()),median_rank_pct=100*np.median(d['rank'])/d.n.iloc[0],
                          P_mult_ge2=100*(d.mult>=2).mean(),P_mult_ge5=100*(d.mult>=5).mean(),max_mult=d.mult.max()))
P('## T5. A3: one Millionaire seat drawn at random from each book, placed in that week Millionaire field (realized)\n'); P(M.groupby(['week','book']).apply(a3, include_groups=False).round(2).pipe(md,index=True)); P()
# pooled over weeks (entered books)
d=M[M.book=='entered']; P('Pooled W1-3 entered rows (n=%d): P_cash %.1f%%, P_top1000 %.2f%%, P_top100 %.2f%%, P_top10 %.2f%%, E[mult] %.3f (ROI %.1f%%)'%(len(d),100*d.cash.mean(),100*d.top1000.mean(),100*d.top100.mean(),100*d.top10.mean(),d.mult.mean(),100*(d.mult.mean()-1))); P()
# Milly ladder shape: share of pool by rank band (W3 ladder)
cid='195905122'; ts=tiers(cid); tot=sum((hi-lo+1)*m for lo,hi,m in ts)
bands=[(1,1),(2,10),(11,100),(101,1000),(1001,10000),(10001,places(cid))]
P('W3 Millionaire ladder: share of the prize pool by finishing band and multiple of fee at the band floor:')
for a,b in bands:
    sh=sum(m for lo,hi,m in ts for p in range(max(lo,a),min(hi,b)+1))/tot
    P(f'- places {a}-{b}: {100*sh:.1f}% of pool; multiple at place {b}: {mult_at(cid,b):.1f}x')
P()

# ---- W3 realized ROI (fees from ladders, internal only; output % only)
w3=pd.read_csv('our_w3_entries.csv')
fee_by_cls={'milly20':lad['195905122']['entryFee'],'ffwc18':lad['195923609']['entryFee'],'supersat25lo':lad['195920743']['entryFee'],'supersat25hi':lad['195920744']['entryFee'],'sat13mega':lad['195920605']['entryFee'],'supersat2':lad['195920727']['entryFee'],'ffwc':lad['195920781']['entryFee'],'wildcat':lad['195920803']['entryFee'],'sat20':lad['195920630']['entryFee']}
w3['fee']=w3.cls.map(fee_by_cls); w3['won']=np.where((w3.cls=='sat20')&(w3['rank']==1),w3.fee*10,0.0)
P('## T6. Week 3 realized (204 entries, one 11-entry satellite won; fees taken from the public ladders, reported as ROI only)\n')
P('Overall W3 ROI: %.1f%%; share of stake by class: '%(100*(w3.won.sum()/w3.fee.sum()-1)) + ', '.join(f'{k} {100*v:.0f}%' for k,v in (w3.groupby('cls').fee.sum()/w3.fee.sum()).sort_values(ascending=False).items()))
P(w3.groupby('cls').apply(include_groups=False, func=lambda d:pd.Series(dict(entries=len(d),mean_pts=d.score.mean(),best_rank=d['rank'].min(),ROI_pct=100*(d.won.sum()/d.fee.sum()-1)))).round(1).pipe(md,index=True)); P()

# ---- F4 / A5: entry-count buckets by class
bk['cls']=bk.contest_id.map(cmap); bk['t1']=np.maximum(1,np.round(0.01*bk.n)); bk['t10']=np.maximum(1,np.round(0.10*bk.n)); bk['t20']=np.maximum(1,np.round(0.20*bk.n))
bk['top1_rows']=bk.share_top1/100*bk.t1; bk['top10_rows']=bk.share_top10/100*bk.t10; bk['top20_rows']=bk.share_top20/100*bk.t20
F=bk.groupby(['cls','bucket']).agg(rows=('n_rows','sum'),users=('users','sum'),top1_rows=('top1_rows','sum'),top10_rows=('top10_rows','sum'),top20_rows=('top20_rows','sum'),wins=('wins','sum'),mean_pts=('mean_pts','mean')).reset_index()
tot=F.groupby('cls').agg(rows=('rows','sum'),top1=('top1_rows','sum'),top10=('top10_rows','sum'),top20=('top20_rows','sum'),wins=('wins','sum'))
F=F.join(tot,on='cls',rsuffix='_all')
F['share_field']=100*F.rows/F.rows_all; F['lift_top1']=(F.top1_rows/F.top1)/(F.rows/F.rows_all); F['lift_top10']=(F.top10_rows/F.top10)/(F.rows/F.rows_all); F['lift_top20']=(F.top20_rows/F.top20)/(F.rows/F.rows_all); F['lift_win']=(F.wins/F.wins_all)/(F.rows/F.rows_all)
P('## T7. F4/A5: per-entry lift by entry-count bucket and class (lift = share of top-x% rows / share of field rows; 1.0 = flat). 2026 W1-3, all 60 contests.\n')
P(F[['cls','bucket','rows','users','share_field','lift_top1','lift_top10','lift_top20','lift_win','wins','mean_pts']].round(2).pipe(md)); P()
open('analysis_out2.md','w').write("\n".join(out)); print("\n".join(out))
