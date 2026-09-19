"""Fixed participation-map selection transfer; no fitting, outcomes or cloud calls."""
import contextlib
import csv
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import subprocess
import sys
import time
from types import SimpleNamespace

import numpy as np
import pandas as pd
from google.cloud import bigquery

HERE=Path(__file__).parent
REPO=Path(__file__).resolve().parents[3]
BASE=Path('/home/erich/projects/review-evidence/overnight-20260918')
INPUT=BASE/'participation-transfer-inputs'
SUPPORT=BASE/'participation-transfer-support'
LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')
OUT=BASE/'participation-transfer'
SAFE=['id','dk_player_id','dk_draftable_id','draft_group_id','display_name','position','pos','team','salary','gsis_id','status']
SELECTION_SEED=20260919054
AUDIT_SEED=20260920054


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def opened(r):
    p=Path(r['path']);assert sha(p)==r['sha256'],p;return p
def write(p,v):
    with Path(p).open('x') as f:json.dump(v,f,indent=2,allow_nan=False,default=str)
def ahash(a):return hashlib.sha256(np.ascontiguousarray(a).tobytes()).hexdigest()
def status(x):
    x='' if pd.isna(x) else str(x).strip().upper()
    d={'':None,'NONE':None,'Q':'Questionable','QUESTIONABLE':'Questionable',
       'D':'Doubtful','DOUBTFUL':'Doubtful','O':'Out','OUT':'Out','IR':'Out',
       'PUP':'Out','NFI':'Out','SUS':'Out','SUSPENDED':'Out'}
    assert x in d,('unknown status',x);return d[x]
def practice(x):
    if pd.isna(x):return None
    d={'Did Not Participate In Practice':0,'Limited Participation in Practice':1,'Full Participation in Practice':2}
    assert x in d,('unknown practice',x);return d[x]


def inputs():
    capture=json.loads((INPUT/'capture.json').read_text())
    for r in capture['captures']:opened(r)
    dkrec=json.loads((INPUT/'dk-capture-repair.json').read_text());d=pd.read_parquet(opened(dkrec))
    inj=pd.read_parquet(INPUT/'injury_snapshots.parquet');assert inj.gsis_id.is_unique
    assert (pd.Timestamp(capture['cutoff'])-inj.pulled_at.max()).total_seconds()<86400
    assert (pd.Timestamp(capture['cutoff'])-d.pulled_at.max()).total_seconds()<3600
    r=json.loads((BASE/'complete-chain-d1600/salaryfix/receipt.json').read_text())
    original=Path(r['original_run'])
    prior=json.loads((HERE/'2026-09-19-repaired-chain-d1600-read.json').read_text())
    for name,h in prior['provenance']['salaryfix']['artifacts'].items():assert sha(original/name)==h
    fr=pd.read_parquet(original/'frame.parquet',columns=SAFE)
    orders=json.loads(opened(r['candidate_player_orders']).read_text())
    cands=pd.read_parquet(original/'candidates.parquet',columns=['cand','players'])
    assert cands.cand.tolist()==list(range(1600)) and fr.id.is_unique
    assert all(len(o)==len(set(o))==9 and ','.join(sorted(o))==s for o,s in zip(orders,cands.players))
    d=d.set_index('dk_player_id');inj=inj.set_index('gsis_id')
    assert set(fr.dk_player_id)<=set(d.index)
    fr['status']=fr.dk_player_id.map(d.status)
    mp=SUPPORT/'participation-map.json';assert sha(mp)=='fc5a22bb9c3cab895e8260ef00caca4c389888f4110ceff0b21a59b97b005cbb'
    from nfl_dfs.inference.week1_participation_mixture import validate_participation_map_v1
    m=validate_participation_map_v1(json.loads(mp.read_text()))
    probs=np.ones(len(fr));out=set();records=[];severity={None:0,'Questionable':1,'Doubtful':2,'Out':3}
    for n,row in enumerate(fr.itertuples()):
        raw=inj.loc[row.gsis_id] if row.gsis_id in inj.index else None
        ds=status(row.status);rs=status(raw.report_status) if raw is not None else None
        st=max((ds,rs),key=lambda x:severity[x]);pr=practice(raw.practice_status) if raw is not None else None
        if st=='Out':out.add(row.id)
        elif st is not None:probs[n]=m['p_active'][st+'|'+('none' if pr is None else str(pr))]
        if st is not None:
            records.append(dict(id=row.id,name=row.display_name,dk_status=row.status,injury_status=rs,
                source_disagreement=ds!=rs,practice_raw=None if raw is None else raw.practice_status,
                practice=pr,selected_status=st,p_active=None if st=='Out' else float(probs[n]),
                provider_modified_at=None if raw is None or pd.isna(raw.date_modified) else str(raw.date_modified)))
    keep=[n for n,o in enumerate(orders) if not(set(o)&out)]
    assert len(keep)>=97
    index={x:i for i,x in enumerate(fr.id)}
    roster=np.asarray([[index[x] for x in o] for o in orders],int)
    return dict(fr=fr,orders=orders,roster=roster,keep=keep,probs=probs,records=records,
                receipt=r,prior=prior,original=original,cutoff=capture['cutoff'],out=sorted(out))


def mixed_pair(banks,p,seed):
    rng=np.random.default_rng(seed);mixed={k:v.copy() for k,v in banks.items()};receipts=[]
    for i in np.flatnonzero(p<1):
        for name,bank in mixed.items():
            mask=rng.random(bank.shape[1])>=p[i];bank[i,mask]=0
            receipts.append(dict(player_index=int(i),bank=name,inactive=int(mask.sum()),sha256=ahash(mask)))
    return mixed,receipts
def totals(bank,roster):return np.stack([bank[row].sum(axis=0,dtype=np.float32) for row in roster])


def vet(s,books,dest):
    helper=REPO/'scripts/week1_vet_book.py'
    assert sha(helper)=='aa7d35f808d2a5db4faea6471b95c0c89b765ad1bc3c1e0c310ff5a428d6e89e'
    captures=json.loads((INPUT/'vetting/query-captures.json').read_text());cache={}
    for r in captures:
        key=hashlib.sha256(json.dumps({'sql':r['sql'],'parameters':r['parameters']},sort_keys=True).encode()).hexdigest()
        cache[key]=pd.read_parquet(opened(r))
    calls=[]
    class Result:
        def __init__(self,f):self.f=f
        def result(self):return self
        def to_dataframe(self):return self.f.copy(deep=True)
    class OfflineClient:
        def __init__(self,project):assert project=='nfl-predictions-503414'
        def query(self,sql,job_config):
            key=hashlib.sha256(json.dumps({'sql':sql,'parameters':[x.to_api_repr() for x in job_config.query_parameters]},sort_keys=True).encode()).hexdigest()
            assert key in cache,'uncaptured query';calls.append(key);return Result(cache[key])
    from nfl2.live import dk_csv
    oldclient=bigquery.Client;oldargs=sys.argv;result={}
    try:
        bigquery.Client=OfflineClient
        fn=runpy.run_path(str(helper))['main']
        for name,b in books.items():
            source=dest/name/'source';source.mkdir(parents=True)
            s['fr'].to_parquet(source/'frame.parquet',index=False)
            lu=[SimpleNamespace(players=[{'id':x} for x in s['orders'][i]]) for i in b]
            assert dk_csv(lu,s['fr'],source/'book.csv')==97
            write(source/'receipt.json',dict(research_only=True,candidate_indices=b))
            target=dest/name/'vetted';count=len(calls)
            sys.argv=[str(helper),str(source),'--k','30','--season','2026','--week','2','--output-dir',str(target)]
            with (dest/name/'vetting.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):fn()
            assert len(calls)-count==3
            v=json.loads((target/'vetting.json').read_text());order=v['order_source_ranks']
            assert sorted(order)==list(range(1,98))
            before=list(csv.reader((source/'book.csv').open()));after=list(csv.reader((target/'book.csv').open()))
            assert after[1:]==[before[i] for i in order]
            result[name]=dict(indices=[b[i-1] for i in order],first_source_rank=order[0],
                hard=sum(x['hard'] for x in v['lineups']),material=sum(x['material'] for x in v['lineups']),
                order_source_ranks=order,receipt_sha256=sha(target/'vetting.json'))
    finally:bigquery.Client=oldclient;sys.argv=oldargs
    return result


def select(s,banks):
    from nfl2.selectors import select_expected_max
    t=np.concatenate([totals(b,s['roster'][s['keep']]) for b in banks.values()],axis=1)
    chosen=[s['keep'][i] for i in select_expected_max(t,97)]
    assert len(chosen)==len(set(chosen))==97
    return chosen


def smoke(s):
    rng=np.random.default_rng(54)
    banks={k:rng.gamma(2,5,(len(s['fr']),400)).astype(np.float32) for k in ('I','H')}
    allactive,rec=mixed_pair(banks,np.ones(len(s['fr'])),SELECTION_SEED)
    assert not rec and all(np.array_equal(banks[k],allactive[k]) for k in banks)
    a,ar=mixed_pair(banks,s['probs'],SELECTION_SEED);b,br=mixed_pair(banks,s['probs'],SELECTION_SEED)
    assert ar==br and all(np.array_equal(a[k],b[k]) for k in a)
    books=dict(control=select(s,banks),pmix=select(s,a))
    dest=BASE/'participation-transfer-smoke';assert not dest.exists();v=vet(s,books,dest)
    write(dest/'smoke.json',dict(passed=True,books=books,vet=v,source_sha256=sha(__file__),
        designated=s['records'],eligible_candidates=len(s['keep']),no_football_outcomes=True))
    print('SYNTHETIC_FULL_PATH_AND_REAL_INPUT_SUPPORT_PASS',flush=True)


def main(s):
    start=time.monotonic();OUT.mkdir(exist_ok=False)
    banks={k:np.load(opened(s['receipt']['arrays'][k+'_selection']),allow_pickle=False) for k in ('I','H')}
    assert all(a.shape==(len(s['fr']),10000) and a.dtype==np.float32 and np.isfinite(a).all() for a in banks.values())
    mix,selection_masks=mixed_pair(banks,s['probs'],SELECTION_SEED)
    books=dict(control=select(s,banks),pmix=select(s,mix))
    if len(s['keep'])==1600:assert books['control']==s['prior']['books']['salaryfix_emax']['candidate_indices']
    write(OUT/'frozen-books.json',books)
    del banks,mix
    v=vet(s,books,OUT/'delivery')
    books.update({k+'_vetted':x['indices'] for k,x in v.items()})
    helper=runpy.run_path(str(HERE/'2026-09-19-repaired-chain-read.py'));regions=helper['REGIONS']
    raw=subprocess.check_output(['git','-C',str(LAB),'show','e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest()=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners=np.asarray(sorted(json.loads(raw).values()),float)
    banks={k:np.load(opened(s['receipt']['arrays'][k+'_audit']),allow_pickle=False) for k in ('I','H')}
    mix,audit_masks=mixed_pair(banks,s['probs'],AUDIT_SEED)
    assert {r['sha256'] for r in selection_masks}.isdisjoint(r['sha256'] for r in audit_masks)
    samples={};metrics={}
    for kind,bb in [('all_active',banks),('participation',mix)]:
        for comp,bank in bb.items():
            law=kind+'_'+comp;samples[law]={};metrics[law]={}
            for name,b in books.items():
                t=totals(bank,s['roster'][b]);samples[law][name]={};metrics[law][name]={}
                for reg,sl in regions.items():
                    m=helper['metrics'](t[sl].max(axis=0).astype(float),winners)
                    m['mean_lineup']=t[sl].mean(axis=0,dtype=float)
                    samples[law][name][reg]=m;metrics[law][name][reg]={k:float(a.mean()) for k,a in m.items()}
    laws={k:[k] for k in samples}
    for kind in ('all_active','participation'):
        parts=[kind+'_I',kind+'_H'];law=kind+'_mixture';laws[law]=parts
        metrics[law]={b:{reg:{m:float(np.mean([metrics[p][b][reg][m] for p in parts])) for m in metrics[parts[0]][b][reg]} for reg in regions} for b in books}
    comparisons=[('pmix','control'),('pmix_vetted','control_vetted'),('control_vetted','control'),('pmix_vetted','pmix')]
    contrasts={a+'-minus-'+b:{law:{reg:{m:helper['uncertainty']([samples[p][a][reg][m]-samples[p][b][reg][m] for p in parts]) for m in samples[parts[0]][a][reg]} for reg in regions} for law,parts in laws.items()} for a,b in comparisons}
    risk=1-np.prod(s['probs'][s['roster']],axis=1)
    exposures={name:{r['name']:sum(r['id'] in s['orders'][i] for i in b) for r in s['records']} for name,b in books.items()}
    result=dict(source_sha256=sha(__file__),protocol_sha256=sha(REPO/'reports/2026-09-19-participation-transfer-protocol.md'),
        cutoff=s['cutoff'],candidate_count=len(s['keep']),excluded_players=s['out'],map_records=s['records'],
        input_arrays=s['receipt']['arrays'],selection_seed=SELECTION_SEED,audit_seed=AUDIT_SEED,
        masks=dict(selection=selection_masks,audit=audit_masks),books=books,vetting=v,
        shared_members=len(set(books['control'])&set(books['pmix'])),exposures=exposures,
        expected_inactive_contamination={b:{reg:float(risk[np.asarray(ids)[sl]].mean()) for reg,sl in regions.items()} for b,ids in books.items()},
        first_rosters={b:s['fr'].set_index('id').loc[s['orders'][ids[0]],'display_name'].tolist() for b,ids in books.items()},
        metrics=metrics,contrasts=contrasts,elapsed_seconds=time.monotonic()-start,
        scope='Conditional current-pool selection and delivery transfer; no football outcomes or live adoption.')
    write(OUT/'result.json',result)
    print(json.dumps({k:{b:v['prefix97'] for b,v in m.items()} for k,m in metrics.items() if k.endswith('mixture')},indent=2),flush=True)


if __name__=='__main__':
    sys.path.insert(0,str(REPO/'src'));sys.path.insert(0,str(LAB/'src'))
    state=inputs()
    if '--smoke' in sys.argv:smoke(state)
    else:main(state)
