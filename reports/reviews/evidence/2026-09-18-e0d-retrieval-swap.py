"""E0d bounded empirical-law replacement search. Excludes all 2026 actual-score columns."""
import hashlib
import io
import json
import os
import platform
import subprocess
import time
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from google.cloud import storage

ROOT=Path('reports/reviews/evidence')
OUT=ROOT/'2026-09-18-e0d-retrieval-swap-results.json'
assert not OUT.exists()
SCHEMA=json.loads((ROOT/'2026-09-18-e0-archive-schema.json').read_text())
IDENT=json.loads((ROOT/'2026-09-18-e0-archive-identity.json').read_text())
PREFIXES=(1,10,20,40,80)
SOURCE='fa5d035ba99928f71736cbb77222515e9cdd94a8'
LAB='/home/erich/projects/.nfl2-worktrees/prereg101-review-reply'
START=None

def deadline():
    if START is not None and time.monotonic()-START>300:
        raise TimeoutError('Five-minute compute cap exceeded')

def greedy(matrix, weights, k):
    weights=np.asarray(weights,dtype=np.float64)
    assert np.isclose(weights.sum(),1)
    current=np.full(matrix.shape[1],-np.inf)
    chosen=[]
    for _ in range(k):
        deadline()
        values=np.empty(matrix.shape[0])
        for start in range(0,len(values),64):
            stop=min(start+64,len(values))
            values[start:stop]=np.maximum(matrix[start:stop],current) @ weights
        values[chosen]=-np.inf
        i=int(np.argmax(values)); chosen.append(i)
        current=np.maximum(current,matrix[i])
    assert len(set(chosen))==k
    return chosen

# A duplicated-world fixture verifies frequency weighting and marginal selection.
fixture=np.array([[10.,0.],[9.,0.],[0.,8.]])
assert greedy(fixture,np.array([.5,.5]),2)==[0,2]
assert greedy(fixture,np.array([.75,.25]),2)==greedy(fixture[:,[0,0,0,1]],np.full(4,.25),2)

bucket=storage.Client(project='nfl-predictions-503414').bucket('nfl-predictions-503414-raw')
prefix=SCHEMA['prefix'].split(bucket.name+'/',1)[1]
verified={}
def download(name, expected_sha):
    rec=next(r for r in SCHEMA['objects'] if r['name']==name)
    raw=bucket.blob(prefix+name).download_as_bytes(if_generation_match=int(rec['generation']))
    sha=hashlib.sha256(raw).hexdigest()
    assert sha==expected_sha,(name,sha,expected_sha)
    verified[name]=dict(generation=rec['generation'],sha256=sha,bytes=len(raw))
    return raw

frames={}
for name,cols in [('frame.parquet',['id']),('candidates.parquet',['cand','players','salary'])]:
    rec=next(r for r in SCHEMA['objects'] if r['name']==name)
    raw=download(name,rec['sha256'])
    frames[name]=pq.read_table(io.BytesIO(raw),columns=cols).to_pydict()
ids=[str(v) for v in frames['frame.parquet']['id']]
rosters=[tuple(sorted(s.split(','))) for s in frames['candidates.parquet']['players']]
assert hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()==IDENT['frame_order_sha256']
assert hashlib.sha256(json.dumps(rosters,separators=(',',':')).encode()).hexdigest()==IDENT['roster_order_sha256']
assert len(ids)==len(set(ids))==397 and len(rosters)==len(set(rosters))==800
idx={v:i for i,v in enumerate(ids)}
indices=[[idx[v] for v in roster] for roster in rosters]
assert all(len(r)==len(set(r))==9 for r in indices)
raw_totals=np.empty((800,20000),dtype=np.float64)
for component,name in enumerate(('incumbent_player_scores','corrected_hsim_player_scores')):
    raw=download(name+'.npy',IDENT['sidecar_identity'][name]['sha256'])
    matrix=np.load(io.BytesIO(raw),allow_pickle=False)
    assert matrix.shape==(397,10000) and matrix.dtype==np.float32 and np.isfinite(matrix).all()
    for i,players in enumerate(indices):
        raw_totals[i,component*10000:(component+1)*10000]=matrix[players].sum(axis=0,dtype=np.float64)
    del matrix,raw
registry=subprocess.check_output(['git','-C',LAB,'show',SOURCE+':results/contest/milly_winners.json'])
registry_sha=hashlib.sha256(registry).hexdigest()
assert registry_sha=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
winners=np.array(sorted(json.loads(registry).values()),dtype=np.float64)
assert winners.shape==(48,) and np.isfinite(winners).all()
START=time.monotonic()
utility=np.empty_like(raw_totals)
flat=raw_totals.ravel(); out=utility.ravel()
for start in range(0,len(flat),50000):
    deadline()
    stop=min(start+50000,len(flat))
    out[start:stop]=(1/(1+np.exp(-(flat[start:stop,None]-winners)/8))).mean(axis=1)
assert np.isfinite(utility).all()
weights=np.full(20000,1/20000)

def replacement_values(matrix,book,slot,world_weights):
    selected=matrix[book]
    best=selected.max(axis=0)
    where=selected.argmax(axis=0)
    second=np.partition(selected,-2,axis=0)[-2]
    baseline=np.where(where==slot,second,best)
    scores=np.empty(len(matrix))
    for start in range(0,len(matrix),64):
        scores[start:start+64]=np.maximum(matrix[start:start+64],baseline) @ world_weights
    scores[book]=-np.inf
    return scores

fixture=np.array([[5.,5.,1.],[5.,2.,6.],[7.,3.,4.],[1.,9.,2.]])
fw=np.array([.2,.3,.5]);fb=[0,1]
for slot in range(2):
    optimized=replacement_values(fixture,fb,slot,fw)
    for candidate in (2,3):
        trial=fb.copy();trial[slot]=candidate
        assert abs(optimized[candidate]-float(fixture[trial].max(axis=0) @ fw))<1e-12

baseline=greedy(utility,weights,80)
old=json.loads((ROOT/'2026-09-18-e0c-archive-resampling-results.json').read_text())
assert baseline==old['reference_book']
current_value=float(utility[baseline].max(axis=0).mean())
assert abs(current_value-old['reference_values'][-1]['full_proxy'])<1e-12
book=baseline.copy();steps=[];local_optimal=False
for iteration in range(3):
    selected=utility[book]
    best=selected.max(axis=0);where=selected.argmax(axis=0)
    second=np.partition(selected,-2,axis=0)[-2]
    best_value=current_value;best_pair=None
    for slot in range(80):
        deadline()
        without=np.where(where==slot,second,best)
        # Only columns where this slot uniquely supplies the maximum can change upon removal;
        # evaluate every incoming candidate on all columns to retain exact objective semantics.
        values=np.empty(800)
        for start in range(0,800,64):
            values[start:start+64]=np.maximum(utility[start:start+64],without) @ weights
        values[book]=-np.inf
        idx=int(np.flatnonzero(values>=values.max()-1e-12)[0])
        value=float(values[idx])
        if value>best_value+1e-12:
            best_value=value;best_pair=(slot,idx)
    if best_pair is None:
        local_optimal=True
        break
    slot,idx=best_pair;removed=book[slot];book[slot]=idx
    direct=float(utility[book].max(axis=0).mean())
    assert abs(direct-best_value)<1e-12 and direct>current_value+1e-12
    assert len(set(book))==80
    steps.append(dict(iteration=iteration,removed=removed,added=idx,slot=slot,
                      previous=current_value,new=direct,gain=direct-current_value))
    current_value=direct
    print('Accepted swap',iteration,'gain',steps[-1]['gain'],'seconds',round(time.monotonic()-START,2),flush=True)
reordered=[book[i] for i in greedy(utility[book],weights,80)]

def metrics(order):
    out=[]
    for k in PREFIXES:
        raw=raw_totals[order[:k]].max(axis=0)
        proxy=float(utility[order[:k]].max(axis=0).mean())
        out.append(dict(k=k,proxy=proxy,raw_max=float(raw.mean()),p220=float((raw>=220).mean())))
    return out

base_metrics=metrics(baseline);final_metrics=metrics(book);ordered_metrics=metrics(reordered)
assert abs(final_metrics[-1]['proxy']-ordered_metrics[-1]['proxy'])<1e-12
no_harm=all(t['proxy']>=c['proxy']-1e-12 for c,t in zip(base_metrics,ordered_metrics))
result=dict(baseline_book=baseline,final_book=book,reordered_book=reordered,steps=steps,
    stopped_one_swap_optimal=local_optimal,prefix_no_harm=no_harm,
    baseline=base_metrics,final_unreordered=final_metrics,final_reordered=ordered_metrics,
    turnover=len(set(book)-set(baseline))/80,elapsed_seconds=time.monotonic()-START,
    verified_inputs=verified,registry_sha256=registry_sha,
    checks='input hashes/order; exact E0c reference reproduction; tied-world replacement fixture; direct accepted-swap evaluation; unique books; monotonic K80 utility; final permutation equality',
    provenance=dict(git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        git_status=subprocess.check_output(['git','status','--porcelain'],text=True),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        python=platform.python_version(),numpy=np.__version__,
        threads={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}))
with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:result[k] for k in ('steps','stopped_one_swap_optimal','prefix_no_harm','baseline','final_reordered','elapsed_seconds')},indent=2))
