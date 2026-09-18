"""Allowlisted archive census: no actuals, ranks, prediction metrics, or score matrices."""
import hashlib
import io
import json
from pathlib import Path
from collections import Counter
from google.cloud import storage
import pyarrow.parquet as pq

root=Path('reports/reviews/evidence')
previous=json.loads((root/'2026-09-18-e0-archive-schema.json').read_text())
client=storage.Client(project='nfl-predictions-503414')
bucket=client.bucket('nfl-predictions-503414-raw')
prefix=previous['prefix'].split(bucket.name+'/',1)[1]
columns={'candidates.parquet':['cand','players','salary'],
         'frame.parquet':['id','position','salary','team','opp']}
tables={}
for name, cols in columns.items():
    record=next(r for r in previous['objects'] if r['name']==name)
    data=bucket.blob(prefix+name).download_as_bytes(if_generation_match=int(record['generation']))
    assert hashlib.sha256(data).hexdigest()==record['sha256']
    tables[name]=pq.read_table(io.BytesIO(data),columns=cols).to_pydict()
frame=tables['frame.parquet']; candidates=tables['candidates.parquet']
ids=[str(i) for i in frame['id']]
assert len(set(ids))==len(ids)
index={v:i for i,v in enumerate(ids)}
violations=Counter(); rosters=[]
for roster, salary in zip(candidates['players'],candidates['salary']):
    players=roster.split(','); rosters.append(tuple(sorted(players)))
    if len(players)!=9 or len(set(players))!=9: violations['roster_size_or_duplicate']+=1
    if any(p not in index for p in players):
        violations['missing_frame_player']+=1
        continue
    rows=[index[p] for p in players]
    counts=Counter(str(frame['position'][i]) for i in rows)
    if not(counts['QB']==1 and counts['DST']==1 and 2<=counts['RB']<=3 and
           3<=counts['WR']<=4 and 1<=counts['TE']<=2 and
           counts['RB']+counts['WR']+counts['TE']==7):
        violations['classic_position_counts']+=1
    total=sum(float(frame['salary'][i]) for i in rows)
    if abs(total-float(salary))>1e-8: violations['salary_identity']+=1
    if total>50000 or total<0: violations['salary_cap']+=1
blob=bucket.blob(prefix+'receipt.json'); blob.reload()
receipt=json.loads(blob.download_as_bytes(if_generation_match=int(blob.generation)))
identity=receipt.get('identity',{})
config=receipt.get('config',{})
allowed_config=('lev','boom','k','operational_k','sims','seed','selector','hsim_seed','hsim_worlds','centering')
result=dict(method='Explicit column projection; no actual, ranks, metric columns or score matrix values decoded.',
    allowed_columns=columns, candidates=len(rosters),unique_rosters=len(set(rosters)),
    unique_candidate_ids=len(set(candidates['cand'])),frame_rows=len(ids),
    frame_order_sha256=hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest(),
    roster_order_sha256=hashlib.sha256(json.dumps(rosters,separators=(',',':')).encode()).hexdigest(),
    basic_contract_violations=dict(violations),
    receipt_generation=blob.generation, receipt_identity_keys=list(identity),
    identity={k:identity[k] for k in ('sha','git_sha','dirty','branch','code_sha') if k in identity},
    season=receipt.get('season'),week=receipt.get('week'),lock_utc=receipt.get('lock_utc'),
    built_utc=receipt.get('built_utc'),salary_pull=receipt.get('salary_pull'),
    config={k:config[k] for k in allowed_config if k in config},banks=receipt.get('banks'),
    sidecar_identity=receipt.get('a5_sidecars'))
with (root/'2026-09-18-e0-archive-identity.json').open('x') as f:
    json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps(result,indent=2))
