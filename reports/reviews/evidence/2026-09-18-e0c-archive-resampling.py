"""E0c conditional empirical-law pilot. Excludes all 2026 actual-score columns."""
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
OUT=ROOT/'2026-09-18-e0c-archive-resampling-results.json'
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
reference=greedy(utility,weights,80)
assert reference[0]==int(np.argmax(utility @ weights))

def evaluate(book, columns, sample_weights):
    previous=-np.inf; output=[]
    for k in PREFIXES:
        maximum=raw_totals[book[:k]].max(axis=0)
        umax=utility[book[:k]].max(axis=0)
        full=float(umax.mean())
        assert full+1e-12>=previous; previous=full
        direct=sum(float(v) for v in umax)/len(umax)
        assert abs(direct-full)<1e-12
        train=float(umax[columns] @ sample_weights)
        refset=set(reference[:k]); selected=set(book[:k])
        output.append(dict(k=k,full_proxy=full,decision_proxy=train,optimism=train-full,
                           full_raw_max=float(maximum.mean()),full_p220=float((maximum>=220).mean()),
                           decision_raw_max=float(maximum[columns] @ sample_weights),
                           decision_p220=float((maximum[columns]>=220) @ sample_weights),
                           jaccard_reference=len(refset&selected)/len(refset|selected)))
    return output

ref_values=evaluate(reference,np.arange(20000),weights)
ref_map={r['k']:r for r in ref_values}
runs=[]
for replicate in range(5):
    draws=[]
    for component in (0,1):
        rng=np.random.Generator(np.random.PCG64(np.random.SeedSequence([20260918,3,replicate,component])))
        draws.append(rng.integers(0,10000,size=10000)+component*10000)
    for count in (1000,5000,20000):
        deadline()
        sample=np.concatenate([part[:count//2] for part in draws])
        columns,frequencies=np.unique(sample,return_counts=True)
        sample_weights=frequencies/count
        assert np.isclose(sample_weights[columns<10000].sum(),.5)
        selected_matrix=utility[:,columns]
        book=greedy(selected_matrix,sample_weights,80)
        assert book[0]==int(np.argmax(selected_matrix @ sample_weights))
        del selected_matrix
        measures=evaluate(book,columns,sample_weights)
        for measure in measures:
            measure['proxy_minus_reference']=measure['full_proxy']-ref_map[measure['k']]['full_proxy']
            measure['raw_minus_reference']=measure['full_raw_max']-ref_map[measure['k']]['full_raw_max']
            measure['p220_minus_reference']=measure['full_p220']-ref_map[measure['k']]['full_p220']
        runs.append(dict(replicate=replicate,worlds=count,unique_sample_columns=len(columns),
                         book=book,measures=measures))
        print('Completed',replicate,count,'seconds',round(time.monotonic()-START,2),flush=True)

def stats(values):
    a=np.array(values)
    return dict(n=len(a),mean=float(a.mean()),min=float(a.min()),max=float(a.max()),
                mcse=float(a.std(ddof=1)/np.sqrt(len(a))))
summary=[]
for count in (1000,5000,20000):
    for k in PREFIXES:
        rows=[m for run in runs if run['worlds']==count for m in run['measures'] if m['k']==k]
        summary.append(dict(worlds=count,k=k,metrics={key:stats([r[key] for r in rows]) for key in
            ('proxy_minus_reference','optimism','raw_minus_reference','p220_minus_reference','jaccard_reference')}))
paired=[]
for k in PREFIXES:
    diffs=[]
    for rep in range(5):
        low=next(m for run in runs if (run['worlds'],run['replicate'])==(1000,rep) for m in run['measures'] if m['k']==k)
        high=next(m for run in runs if (run['worlds'],run['replicate'])==(20000,rep) for m in run['measures'] if m['k']==k)
        diffs.append(high['full_proxy']-low['full_proxy'])
    paired.append(dict(k=k,proxy_20000_minus_1000=stats(diffs)))
assert len(runs)==15
result=dict(reference_book=reference,reference_values=ref_values,runs=runs,summary=summary,paired=paired,
    verified_inputs=verified,registry_sha256=registry_sha,elapsed_seconds=time.monotonic()-START,
    checks='hashes, ordering, shape, finite, frequency-weight parity, K1 agreement, unique books, scalar full-law evaluation, monotonic prefix utility',
    provenance=dict(git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        git_status=subprocess.check_output(['git','status','--porcelain'],text=True),
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        python=platform.python_version(),numpy=np.__version__,
        threads={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}))
with OUT.open('x') as f: json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({'elapsed_seconds':result['elapsed_seconds'],'paired':paired},indent=2))
