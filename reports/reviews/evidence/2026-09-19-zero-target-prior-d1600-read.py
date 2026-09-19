"""Expanded fixed-pool selection with the unchanged, already-simulated prior banks."""
import hashlib
import json
import runpy
import subprocess
import sys
import time
from pathlib import Path
import numpy as np
import pandas as pd

R=Path(__file__).parent
OUT=R/'2026-09-19-zero-target-prior-d1600-read.json'
CHAIN=Path('/home/erich/projects/review-evidence/overnight-20260918/complete-chain-d1600')
LAB=Path('/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs')


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    assert not OUT.exists();started=time.monotonic()
    chain=json.loads((R/'2026-09-19-repaired-chain-d1600-read.json').read_text())
    prior=json.loads((R/'2026-09-19-zero-target-prior-simulator.json').read_text())
    assert prior['baseline_exact_replay'] and prior['baseline_books_exact']
    r=json.loads((CHAIN/'salaryfix'/'receipt.json').read_text());out=Path(r['original_run'])
    for name,digest in chain['provenance']['salaryfix']['artifacts'].items():assert sha(out/name)==digest
    frame=pd.read_parquet(out/'frame.parquet');cands=pd.read_parquet(out/'candidates.parquet')
    assert cands.index.tolist()==cands.cand.tolist()==list(range(len(cands)))
    rec=r['candidate_player_orders'];assert sha(rec['path'])==rec['sha256']
    orders=json.loads(Path(rec['path']).read_text());index={str(x):i for i,x in enumerate(frame.id)}
    assert len(orders)==len(cands)>=97
    assert all(len(x)==len(set(x))==9 and ','.join(sorted(x))==s for x,s in zip(orders,cands.players))
    roster=np.asarray([[index[x] for x in order] for order in orders])
    assert [str(x) for x in frame.id]==[x['id'] for x in prior['players']]
    banks={}
    for key in ('I_selection','I_audit','H_selection','H_audit'):
        rec=r['arrays'][key];assert sha(rec['path'])==rec['sha256']
        banks[key]=np.load(rec['path'],allow_pickle=False)
    selection={};audits={'I':banks['I_audit']}
    for arm in ('baseline','one_prior_game','past_empirical'):
        for kind in ('selection','audit'):
            rec=prior['array_identities'][arm+'_'+kind];assert sha(rec['path'])==rec['sha256']
            arr=np.load(rec['path'],allow_pickle=False)
            assert arr.shape==(len(frame),10000) and arr.dtype==np.float32 and np.isfinite(arr).all()
            if arm=='baseline':assert np.array_equal(arr,banks['H_'+kind])
            (selection if kind=='selection' else audits)[arm]=arr
    sys.path.insert(0,str(LAB/'src'))
    for name in ('src/nfl2/selectors.py','src/nfl2/live_a5.py'):
        assert (LAB/name).read_bytes()==subprocess.check_output(['git','-C',str(LAB),'show','2dc116c:'+name])
    from nfl2.selectors import select_expected_max
    from nfl2.live_a5 import select_same_pool_wemax
    def totals(bank):return np.stack([bank[row].sum(axis=0,dtype=np.float32) for row in roster])
    itotals=totals(banks['I_selection']);books={}
    for arm,bank in selection.items():
        assert time.monotonic()-started<580
        both=np.concatenate([itotals,totals(bank)],axis=1)
        for kind,fn in [('emax',select_expected_max),('wemax',select_same_pool_wemax)]:
            b=list(map(int,fn(both,97)));assert len(b)==len(set(b))==97
            if arm=='baseline':assert b==chain['books']['salaryfix_'+kind]['candidate_indices']
            books[arm+'_'+kind]=b
        print('EXPANDED_PRIOR_SELECTED',arm,flush=True)
    del selection,both,itotals
    helpers=runpy.run_path(str(R/'2026-09-19-repaired-chain-read.py'))
    metric,uncertainty,regions=(helpers[k] for k in ('metrics','uncertainty','REGIONS'))
    raw=subprocess.check_output(['git','-C',str(LAB),'show','e7255e9:results/contest/milly_winners.json'])
    assert hashlib.sha256(raw).hexdigest()=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
    winners=np.asarray(sorted(json.loads(raw).values()),float);samples={};metrics={}
    for law,bank in audits.items():
        t=totals(bank);samples[law]={};metrics[law]={}
        for name,b in books.items():
            samples[law][name]={};metrics[law][name]={}
            for region,sl in regions.items():
                m=metric(t[np.asarray(b)[sl]].max(axis=0).astype(float),winners)
                samples[law][name][region]=m;metrics[law][name][region]={k:float(x.mean()) for k,x in m.items()}
    laws={k:[k] for k in audits}
    laws.update({k+'_equal_mixture':['I',k] for k in ('baseline','one_prior_game','past_empirical')})
    for law,parts in laws.items():
        if len(parts)==1:continue
        metrics[law]={b:{region:{m:float(np.mean([metrics[p][b][region][m] for p in parts]))
            for m in ('emax','p220','global_proxy')} for region in regions} for b in books}
    pairs=[(a+'_'+k,'baseline_'+k) for a in ('one_prior_game','past_empirical') for k in ('emax','wemax')]
    pairs += [(a+'_wemax',a+'_emax') for a in ('baseline','one_prior_game','past_empirical')]
    contrasts={after+'-minus-'+before:{law:{region:{m:uncertainty([
        samples[p][after][region][m]-samples[p][before][region][m] for p in parts])
        for m in ('emax','p220','global_proxy')} for region in regions} for law,parts in laws.items()} for after,before in pairs}
    overlap={a:{b:dict(shared_members=len(set(x)&set(y)),same_ranks=sum(i==j for i,j in zip(x,y)),same_first=x[0]==y[0])
                for b,y in books.items()} for a,x in books.items()}
    result=dict(source_sha256=sha(__file__),chain_result_sha256=sha(R/'2026-09-19-repaired-chain-d1600-read.json'),
        prior_trace_sha256=sha(R/'2026-09-19-zero-target-prior-simulator.json'),baseline_bank_and_book_parity=True,
        pool_size=len(cands),requested_budget=dict(lev=320,boom=1280),books=books,book_overlap=overlap,
        first_rosters={k:orders[v[0]] for k,v in books.items()},metrics=metrics,contrasts=contrasts,
        global_proxy_bandwidth=8,elapsed_seconds=time.monotonic()-started,
        scope='Expanded fixed-pool prior selection; same saved player banks/calibration; no new worlds, fitting, current outcomes or live adoption.')
    with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    print(json.dumps(dict(pool_size=len(cands),book_overlap=overlap,elapsed_seconds=result['elapsed_seconds'],
        whole_book={law:{b:m['prefix97'] for b,m in bs.items()} for law,bs in metrics.items()}),indent=2))


if __name__=='__main__':main()
