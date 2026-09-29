import json, numpy as np
r=json.load(open('out/hist.json'))
books=['market','dk_l4','served','served_house']
print('| slate | rows | market rows | ' + ' | '.join(f'{b} mean / best / >=150 / >=194' for b in books)+' |')
print('|---|---:|---:|'+'---|'*len(books))
agg={b:[] for b in books}
for k,v in r.items():
    cells=[]
    for b in books:
        s=v.get(b,{})
        if s.get('n'):
            cells.append(f"{s['mean']:.1f} / {s['best']:.1f} / {s['share_150']:.2f} / {s['share_194']:.2f}"); agg[b].append(s['scores'])
        else: cells.append('n/a (no trailing window in week 1)')
    print(f"| {k} | {v['rows']} | {v['market_rows']} | "+' | '.join(cells)+' |')
for b in books:
    sc=np.concatenate(agg[b]); n=len(agg[b])
    print(b, 'slates',n,'pooled mean %.1f'%sc.mean(),'mean of best %.1f'%np.mean([max(x) for x in agg[b]]),'>=150 %.3f'%(sc>=150).mean(),'>=194 %.3f'%(sc>=194).mean())
m=[np.mean(x) for x in agg['market']]; s=[np.mean(x) for x in agg['served']]; h=[np.mean(x) for x in agg['served_house']]
print('market - served per slate', np.round(np.array(m)-np.array(s),1), 'market wins', sum(a>b for a,b in zip(m,s)), 'of', len(m), 'mean diff %.1f'%np.mean(np.array(m)-np.array(s)))
print('house - served per slate', np.round(np.array(h)-np.array(s),1), 'house wins', sum(a>b for a,b in zip(h,s)), 'mean diff %.1f'%np.mean(np.array(h)-np.array(s)))
keys=list(r.keys()); l4=[(k,np.mean(r[k]['dk_l4']['scores'])) for k in keys if r[k]['dk_l4'].get('n')]
sv={k:np.mean(r[k]['served']['scores']) for k in keys}
print('served - dk_l4 on the 10 slates with a window', np.round([sv[k]-v for k,v in l4],1), 'served wins', sum(sv[k]>v for k,v in l4))
