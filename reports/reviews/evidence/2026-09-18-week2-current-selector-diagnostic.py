"""Current raw-DEMAX mechanics/coverage diagnostic. No actual-score column access."""
import hashlib,io,json,os,platform,subprocess,time
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from google.cloud import storage
ROOT=Path('reports/reviews/evidence');OUT=ROOT/'2026-09-18-week2-current-selector-diagnostic.json'
assert not OUT.exists()
manifest=json.loads((ROOT/'2026-09-18-week2-archive-preflight.json').read_text())
bucket=storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab')
prefix=manifest['prefix'].split(bucket.name+'/',1)[1]; verified={}
def data(name):
 r=next(x for x in manifest['objects'] if x['name']==name)
 raw=bucket.blob(prefix+name).download_as_bytes(if_generation_match=int(r['generation']))
 sha=hashlib.sha256(raw).hexdigest();assert sha==r['sha256']
 verified[name]=dict(sha256=sha,generation=r['generation'])
 return raw
fr=pq.read_table(io.BytesIO(data('frame.parquet')),columns=['id']).to_pydict()
c=pq.read_table(io.BytesIO(data('candidates.parquet')),columns=['cand','players','salary','book_rank']).to_pydict()
receipt=json.loads(data('receipt.json'))
ids=[str(x) for x in fr['id']];index={p:i for i,p in enumerate(ids)}
rosters=[s.split(',') for s in c['players']]
assert len(ids)==len(index)==435 and len(rosters)==len(set(tuple(x) for x in rosters))==6400
assert all(len(x)==len(set(x))==9 for x in rosters)
indices=[[index[p] for p in ps] for ps in rosters]
reference=sorted([(int(rank),i) for i,rank in enumerate(c['book_rank']) if rank is not None and np.isfinite(rank)])
assert [r for r,i in reference]==list(range(1,91))
reference=[i for rank,i in reference]
T=np.empty((6400,20000),dtype=np.float32)
for component,name in enumerate(('incumbent_player_scores.npy','corrected_hsim_player_scores.npy')):
 p=np.load(io.BytesIO(data(name)),allow_pickle=False)
 assert p.shape==(435,10000) and p.dtype==np.float32 and np.isfinite(p).all()
 for i,idx in enumerate(indices):T[i,component*10000:(component+1)*10000]=p[idx].sum(axis=0,dtype=np.float32)
 del p
START=time.monotonic();cur=np.full(20000,-np.inf);book=[]
for rank in range(97):
 assert time.monotonic()-START<300,'compute cap exceeded'
 values=np.empty(6400)
 for start in range(0,6400,64):
  values[start:start+64]=np.maximum(T[start:start+64].astype(np.float64),cur).mean(axis=1)
 values[book]=-np.inf;i=int(np.argmax(values));book.append(i);cur=np.maximum(cur,T[i])
assert len(set(book))==97
mismatches=[dict(rank=j+1,stored=reference[j],reproduced=book[j]) for j in range(90) if reference[j]!=book[j]]
result=dict(baseline_reproduced=not mismatches,mismatches=mismatches,selected=book,verified_inputs=verified,
 code_identity=receipt['identity'],note='Older D6400 population, diagnostic K97 extension only; selection-world estimates, no independent audit or actuals.')
if not mismatches:
 def metrics(which):
  maximum=T[which].max(axis=0).astype(np.float64);hits=maximum>=220
  return dict(n=len(which),mean_max=float(maximum.mean()),p220=float(hits.mean()),hits=int(hits.sum()),
              incumbent_p220=float(hits[:10000].mean()),hsim_p220=float(hits[10000:].mean()))
 prefixes=[];last_mean=-np.inf;last_p=-np.inf
 for k in (1,10,20,30,80,90,97):
  m=metrics(book[:k]);assert m['mean_max']>=last_mean-1e-12 and m['p220']>=last_p
  last_mean,last_p=m['mean_max'],m['p220'];prefixes.append(dict(k=k,**m))
 blocks=[(1,1),(2,24),(25,25),(26,30),(31,31),(32,33),(34,43),(44,53),(54,63),(64,79),(80,95),(96,97)]
 assert [r for a,b in blocks for r in range(a,b+1)]==list(range(1,98))
 block_metrics=[dict(first=a,last=b,**metrics(book[a-1:b])) for a,b in blocks]
 pool_hits=T.max(axis=0)>=220;book_hits=T[book].max(axis=0)>=220
 all_p=(T>=220).mean(axis=1);best=int(np.argmax(all_p));extra=np.empty(6400)
 for start in range(0,6400,64):extra[start:start+64]=((T[start:start+64]>=220)&~book_hits).mean(axis=1)
 extra[book]=-1;add=int(np.argmax(extra))
 result.update(prefixes=prefixes,blocks=block_metrics,pool_p220=float(pool_hits.mean()),pool_hit_worlds=int(pool_hits.sum()),
  book_fraction_pool_hits=float(book_hits.sum()/pool_hits.sum()) if pool_hits.any() else None,
  standalone_first_p220=float(all_p[book[0]]),standalone_best_p220=float(all_p[best]),standalone_best_candidate=best,
  standalone_best_book_rank=book.index(best)+1 if best in book else None,
  max_extra_220_coverage=float(extra[add]),extra_coverage_candidate=add,
  extra_coverage_scope='Hypothetical98th addition; not a tested97-slot replacement')
result.update(elapsed_seconds=time.monotonic()-START,provenance=dict(
 git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 git_status=subprocess.check_output(['git','status','--porcelain'],text=True),
 script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),python=platform.python_version(),numpy=np.__version__,
 threads={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}))
with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in result.items() if k not in ('selected','verified_inputs')},indent=2))
