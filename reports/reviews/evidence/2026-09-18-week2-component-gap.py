"""Frozen descriptive same-book component decomposition. No actual-score reads."""
import hashlib,io,json,os,platform,subprocess,time
from pathlib import Path
import numpy as np
import pyarrow.parquet as pq
from google.cloud import storage
ROOT=Path('reports/reviews/evidence');OUT=ROOT/'2026-09-18-week2-component-gap.json';assert not OUT.exists()
manifest=json.loads((ROOT/'2026-09-18-week2-archive-preflight.json').read_text())
bucket=storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab');prefix=manifest['prefix'].split(bucket.name+'/',1)[1]
verified={}
def get(name):
 rec=next(r for r in manifest['objects'] if r['name']==name)
 raw=bucket.blob(prefix+name).download_as_bytes(if_generation_match=int(rec['generation']))
 sha=hashlib.sha256(raw).hexdigest();assert sha==rec['sha256']
 verified[name]=dict(sha256=sha,generation=rec['generation']);return raw
fr=pq.read_table(io.BytesIO(get('frame.parquet')),columns=['id','position','mean_projection','proj']).to_pydict()
c=pq.read_table(io.BytesIO(get('candidates.parquet')),columns=['players','book_rank']).to_pydict()
json.loads(get('receipt.json'))
ids=[str(v) for v in fr['id']];idx={p:i for i,p in enumerate(ids)};assert len(ids)==len(idx)==435
selected=sorted((int(rank),i) for i,rank in enumerate(c['book_rank']) if rank is not None and np.isfinite(rank))
assert [rank for rank,i in selected]==list(range(1,91))
rosters=[[idx[p] for p in c['players'][i].split(',')] for rank,i in selected]
assert all(len(x)==len(set(x))==9 for x in rosters)
I=np.load(io.BytesIO(get('incumbent_player_scores.npy')),allow_pickle=False).astype(np.float64)
H=np.load(io.BytesIO(get('corrected_hsim_player_scores.npy')),allow_pickle=False).astype(np.float64)
assert I.shape==H.shape==(435,10000) and np.isfinite(I).all() and np.isfinite(H).all()
START=time.monotonic();mi=I.mean(axis=1);mh=H.mean(axis=1);delta=mh-mi
TI=np.array([I[rows].astype(np.float32).sum(axis=0,dtype=np.float32) for rows in rosters]).astype(np.float64)
TH=np.array([H[rows].astype(np.float32).sum(axis=0,dtype=np.float32) for rows in rosters]).astype(np.float64)
line_delta=np.array([delta[rows].sum() for rows in rosters])
def measures(T):
 maxima=T.max(axis=0)
 return dict(mean_book_max=float(maxima.mean()),p220=float((maxima>=220).mean()),hits220=int((maxima>=220).sum()),
             highest_lineup_mean=float(T.mean(axis=1).max()),mean_lineup_mean=float(T.mean(axis=1).mean()),
             bookmax_lift_above_highest_lineup_mean=float(maxima.mean()-T.mean(axis=1).max()))
values={'Imean_Iresidual':measures(TI),'Hmean_Hresidual':measures(TH),
        'Hmean_Iresidual':measures(TI+line_delta[:,None]),'Imean_Hresidual':measures(TH-line_delta[:,None])}
assert abs((values['Imean_Iresidual']['mean_book_max']+values['Hmean_Hresidual']['mean_book_max'])/2-200.2197586074829)<1e-4
assert abs(values['Imean_Iresidual']['p220']-.0729)<=.0001+1e-12
assert abs(values['Hmean_Hresidual']['p220']-.3029)<=.0001+1e-12
attribution={}
for metric in ('mean_book_max','p220'):
 a=values['Imean_Iresidual'][metric];b=values['Hmean_Hresidual'][metric]
 c1=values['Hmean_Iresidual'][metric];d=values['Imean_Hresidual'][metric]
 means=.5*((c1-a)+(b-d));residuals=.5*((d-a)+(b-c1))
 assert abs(means+residuals-(b-a))<1e-10
 attribution[metric]=dict(total=b-a,mean_contribution=means,residual_contribution=residuals)
def describe(x):
 a=np.asarray(x);a=a[np.isfinite(a)]
 return dict(n=len(a),mean=float(a.mean()),median=float(np.median(a)),maxabs=float(abs(a).max())) if len(a) else dict(n=0)
positions=np.array(fr['position']);members=np.unique(np.array(rosters).ravel());groups=[]
for population,eligible in [('all',np.arange(435)),('selected_players',members)]:
 for pos in sorted(set(positions)):
  rows=eligible[positions[eligible]==pos]
  if not len(rows):continue
  record=dict(population=population,position=str(pos),hsim_minus_incumbent=describe(delta[rows]))
  for column in ('mean_projection','proj'):
   target=np.asarray(fr[column],dtype=np.float64)
   record['incumbent_minus_'+column]=describe(mi[rows]-target[rows])
   record['hsim_minus_'+column]=describe(mh[rows]-target[rows])
  groups.append(record)
variance={}
for name,P,T in [('incumbent',I,TI),('hsim',H,TH)]:
 player_var=P.var(axis=1);marginal=np.array([player_var[rows].sum() for rows in rosters]);total=T.var(axis=1)
 covariance=total-marginal
 assert np.allclose(total,marginal+covariance,atol=1e-10)
 variance[name]=dict(total_lineup_variance=describe(total),sum_player_variances=describe(marginal),
                     twice_within_lineup_covariance=describe(covariance))
assert time.monotonic()-START<60
result=dict(values=values,attribution=attribution,position_mean_differences=groups,variance=variance,
 negative_scores_after_cross_centering=dict(hsim_to_incumbent=int((H-delta[:,None]<0).sum()),incumbent_to_hsim=int((I+delta[:,None]<0).sum())),
 verified_inputs=verified,elapsed_seconds=time.monotonic()-START,
 caveat='Additive crossings are diagnostics, not valid new distributions. Attribution is descriptive and noncausal; reused selection banks, same fixed K90 book.',
 provenance=dict(git_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
 git_status=subprocess.check_output(['git','status','--porcelain'],text=True),script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
 python=platform.python_version(),numpy=np.__version__,threads={k:os.environ.get(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}))
with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:result[k] for k in ('values','attribution','variance','negative_scores_after_cross_centering','elapsed_seconds')},indent=2))
