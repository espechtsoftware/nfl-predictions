"""Frozen same-membership block-allocation diagnostic; no outcome-column access."""
import hashlib,io,json,os,platform,subprocess,time
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from google.cloud import storage
R=Path('reports/reviews/evidence');O=R/'2026-09-19-contest-allocation.json';assert not O.exists()
m=json.loads((R/'2026-09-18-week2-archive-preflight.json').read_text())
prior=json.loads((R/'2026-09-18-week2-current-selector-diagnostic.json').read_text());assert prior['baseline_reproduced']
selected=prior['selected'];assert len(selected)==len(set(selected))==97
b=storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab');prefix=m['prefix'].split(b.name+'/',1)[1];verified={}
def get(name):
 rec=next(x for x in m['objects'] if x['name']==name);raw=b.blob(prefix+name).download_as_bytes(if_generation_match=int(rec['generation']))
 assert hashlib.sha256(raw).hexdigest()==rec['sha256'];verified[name]=dict(sha256=rec['sha256'],generation=rec['generation']);return raw
fr=pq.read_table(io.BytesIO(get('frame.parquet')),columns=['id']).to_pydict()
c=pq.read_table(io.BytesIO(get('candidates.parquet')),columns=['players']).to_pydict();index={str(p):i for i,p in enumerate(fr['id'])}
rosters=[[index[p] for p in c['players'][i].split(',')] for i in selected]
T=np.empty((97,20000),dtype=np.float64)
for part,name in enumerate(('incumbent_player_scores.npy','corrected_hsim_player_scores.npy')):
 P=np.load(io.BytesIO(get(name)),allow_pickle=False);assert P.shape==(435,10000) and P.dtype==np.float32
 for i,ids in enumerate(rosters):T[i,part*10000:(part+1)*10000]=P[ids].sum(axis=0,dtype=np.float32)
 del P
raw=subprocess.check_output(['git','-C','/home/erich/projects/.nfl2-worktrees/prereg101-review-reply','show',
 'e7255e98bf87297452befb61fb508ad4b368b59f:results/contest/milly_winners.json'])
registry_sha=hashlib.sha256(raw).hexdigest();assert registry_sha=='4e0d57c2f100cfbed37a026c3273b233f8b09c6a6779a60060564a8b56d6ce3f'
w=np.array(sorted(json.loads(raw).values()));assert len(w)==48
START=time.monotonic();U=np.empty_like(T)
for i in range(97):U[i]=(1/(1+np.exp(-(T[i,:,None]-w)/8))).mean(axis=1)
spans=[(0,1),(1,24),(24,25),(25,30),(30,31),(31,33),(33,43),(43,53),(53,63),(63,79),(79,95),(95,97)]
blockof=np.empty(97,dtype=int)
for block,(a,z) in enumerate(spans):blockof[a:z]=block

def metrics(raw_max,utility_max):
 return np.array([float(x) for sl in (slice(0,10000),slice(10000,20000)) for x in
   (raw_max[sl].mean(),utility_max[sl].mean(),(raw_max[sl]>=220).mean())])

def block_state(order):
 states=[]
 for a,z in spans:
  members=order[a:z];raw=T[members];util=U[members]
  base=raw.max(axis=0);baseu=util.max(axis=0)
  states.append(dict(members=members,base=base,baseu=baseu,metrics=metrics(base,baseu)))
 return states

def without(order,row):
 a,z=spans[blockof[row]];members=[int(x) for j,x in enumerate(order[a:z],a) if j!=row]
 if not members:return np.full(20000,-np.inf),np.full(20000,-np.inf)
 return T[members].max(axis=0),U[members].max(axis=0)

# Direct-fixture removal/addition parity, including a singleton block.
fixture=np.array([[5.,1.,2.],[4.,7.,2.],[3.,2.,9.]])
for old,incoming in (([0,1],2),([0],2)):
 for remove in old:
  remaining=[x for x in old if x!=remove]
  base=fixture[remaining].max(axis=0) if remaining else np.full(3,-np.inf)
  assert np.array_equal(np.maximum(base,fixture[incoming]),fixture[remaining+[incoming]].max(axis=0))
order=np.arange(97);original=block_state(order);steps=[]
for iteration in range(5):
 states=block_state(order);cache=[without(order,row) for row in range(97)]
 best=None;eligible=0
 for i in range(1,97):
  assert time.monotonic()-START<120,'compute cap exceeded'
  bi=blockof[i]
  for j in range(i+1,97):
   bj=blockof[j]
   if bi==bj:continue
   ri,ui=cache[i];rj,uj=cache[j]
   mi=metrics(np.maximum(ri,T[order[j]]),np.maximum(ui,U[order[j]]))
   if np.any(mi<states[bi]['metrics']-1e-12):continue
   mj=metrics(np.maximum(rj,T[order[i]]),np.maximum(uj,U[order[i]]))
   if np.any(mj<states[bj]['metrics']-1e-12):continue
   gain=float((mi[[0,3]]-states[bi]['metrics'][[0,3]]).sum()/2+(mj[[0,3]]-states[bj]['metrics'][[0,3]]).sum()/2)
   if gain<=1e-6:continue
   eligible+=1
   if best is None or gain>best['gain']+1e-12:best=dict(i=i,j=j,gain=gain,mi=mi,mj=mj)
 if best is None:
  steps.append(dict(iteration=iteration,eligible_pairs=eligible,stopped=True));break
 i,j=best['i'],best['j'];oldi,oldj=int(order[i]),int(order[j]);order[i],order[j]=order[j],order[i]
 newstates=block_state(order)
 assert np.allclose(newstates[blockof[i]]['metrics'],best['mi'],atol=1e-12,rtol=0)
 assert np.allclose(newstates[blockof[j]]['metrics'],best['mj'],atol=1e-12,rtol=0)
 steps.append(dict(iteration=iteration,eligible_pairs=eligible,row_a=i+1,row_b=j+1,
  original_lineup_a=oldi,original_lineup_b=oldj,sum_mixed_expected_max_gain=best['gain']))
 print('accepted',iteration,i+1,j+1,'gain',best['gain'],flush=True)
final=block_state(order)
assert order[0]==0 and set(order)==set(range(97))
assert all(np.all(f['metrics']>=o['metrics']-1e-12) for o,f in zip(original,final))
assert np.array_equal(T[order].max(axis=0),T.max(axis=0))
output_blocks=[]
for block,((a,z),old,new) in enumerate(zip(spans,original,final)):
 output_blocks.append(dict(first=a+1,last=z,before=old['metrics'].tolist(),after=new['metrics'].tolist(),delta=(new['metrics']-old['metrics']).tolist()))
prefixes=[]
for k in (1,10,20,30,80,90,97):
 x=metrics(T[:k].max(axis=0),U[:k].max(axis=0));y=metrics(T[order[:k]].max(axis=0),U[order[:k]].max(axis=0))
 prefixes.append(dict(k=k,before=x.tolist(),after=y.tolist(),delta=(y-x).tolist()))
result=dict(steps=steps,final_order_original_rows=(order+1).tolist(),final_candidate_ids=[selected[int(x)] for x in order],
 metric_order=['incumbent_Emax','incumbent_GLOBALproxy','incumbent_P220','hsim_Emax','hsim_GLOBALproxy','hsim_P220'],
 blocks=output_blocks,prefixes=prefixes,whole_book_unchanged=True,milly_unchanged=True,all_component_block_no_harm=True,
 verified_inputs=verified,registry_sha256=registry_sha,elapsed_seconds=time.monotonic()-START,
 provenance=dict(git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 git_status=subprocess.check_output(['git','status','--porcelain'],text=True),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 python=platform.python_version(),numpy=np.__version__))
with O.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({'steps':steps,'elapsed_seconds':result['elapsed_seconds']},indent=2))
