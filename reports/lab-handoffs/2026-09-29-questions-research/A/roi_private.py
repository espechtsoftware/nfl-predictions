"""Operator entry-history ROI by class / fee tier / field size. PRIVATE input; prints only %, counts, multiples."""
import pandas as pd, numpy as np, re
b=pd.read_csv('/home/erich/week2-sunday/ENTERED/draftkings-contest-entry-history-week2.csv')
def money(s): return pd.to_numeric(s.astype(str).str.replace(r'[\$,]','',regex=True),errors='coerce').fillna(0)
b['fee']=money(b.Entry_Fee); b['won']=money(b.Winnings_Non_Ticket)+money(b.Winnings_Ticket)
b['tix']=money(b.Winnings_Ticket)>0
b['cash']=b.won>0
b['date']=pd.to_datetime(b.Contest_Date_EST); b['season']=np.where(b.date.dt.month>=8,b.date.dt.year,b.date.dt.year-1)
b['name']=b.Entry.str.replace(r'\s*\(\d+/\d+\)','',regex=True).str.strip()
b['n_user']=b.Entry.str.extract(r'\((\d+)/(\d+)\)')[1].astype(float).fillna(1)
n=b.Contest_Entries; pp=b.Places_Paid
def cls(r):
    nm=r['name'].lower(); n=r.Contest_Entries; pp=r.Places_Paid
    if r.Game_Type!='Classic' or r.Sport!='NFL': return 'z_other(showdown/other sport)'
    if n>=100000: return 'A_Millionaire-size (100k+)'
    if 'satellite to' in nm and n<=11: return 'E_11-entry satellite'
    if 'supersat' in nm: return 'D_supersat (multi-ticket)'
    if n<1000 and ('satellite' in nm or 'qualifier' in nm or 'wildcat' in nm): return 'C_sub-1000 satellite/qualifier-sat'
    if 1000<=n<=40000 and ('qualifier' in nm or 'satellite' in nm): return 'B_5k-40k qualifier'
    if n<1000: return 'C2_sub-1000 other GPP'
    if n<100000: return 'B2_1k-100k GPP (Flea/Play-Action/Huddle/Pylon/Nickel)'
    return 'x_unclassified'
b['cls']=b.apply(cls,axis=1)
b['tier']=pd.cut(b.fee,[0,1.5,3.5,6,12,25,60,1e9],labels=['<=1','2-3','4-6','7-12','13-25','26-60','60+']).astype(str)
b['fsize']=pd.cut(b.Contest_Entries,[0,11,100,1000,5000,40000,200000,1e9],labels=['<=11','12-100','101-1k','1k-5k','5k-40k','40k-200k','200k+']).astype(str)
b['paid_share']=pp/n
b['shape']=pd.cut(b.paid_share,[0,0.02,0.1,0.25,1.01],labels=['<2% paid','2-10%','10-25%','>25%']).astype(str)
def tab(g,key):
    out=g.groupby(key).agg(entries=('fee','size'),contests=('Contest_Key','nunique'),cash_rate=('cash','mean'),ticket_rate=('tix','mean'),fees=('fee','sum'),won=('won','sum'))
    out['ROI_pct']=(100*(out.won/out.fees-1)).round(1); out['cash_rate']=(100*out.cash_rate).round(1); out['ticket_rate']=(100*out.ticket_rate).round(1)
    out['best_multiple']=g.groupby(key).apply(lambda d:(d.won/d.fee).max()).round(1)
    return out.drop(columns=['fees','won'])
pd.set_option('display.width',200)
for label,g in [('LIFETIME (2020-2026 W2)',b),('2026 (W1+W2)',b[b.season==2026]),('PRE-2026',b[b.season<2026])]:
    print('\n=====',label,'| entries',len(g),'| overall ROI %.1f%%'%(100*(g.won.sum()/g.fee.sum()-1)),'| cash %.1f%%'%(100*g.cash.mean()))
    for key in ['cls','tier','fsize','shape']:
        print('--',key); print(tab(g,key).to_string())
print('\n== by season'); print(tab(b,'season').to_string())
# 2026 per contest: our points vs field; keep names, counts, ROI only
g=b[b.season==2026].copy()
per=g.groupby(['date','name','Contest_Key']).agg(n=('fee','size'),field=('Contest_Entries','first'),paid=('Places_Paid','first'),mean_pts=('Points','mean'),best=('Points','max'),best_place=('Place','min'),cash=('cash','sum'),tix=('tix','sum'),fees=('fee','sum'),won=('won','sum'))
per['ROI_pct']=(100*(per.won/per.fees-1)).round(1); per['pool_ratio']=None
print('\n== 2026 per contest (no dollars)'); print(per.drop(columns=['fees','won']).to_string())
per.drop(columns=['fees','won']).to_csv('our_2026_w1w2_per_contest.csv')
g[['date','name','Contest_Key','Contest_Entries','Places_Paid','Place','Points','cash','tix']].to_csv('our_2026_w1w2_entries_nodollars.csv',index=False)
