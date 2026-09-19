"""Before/after census using existing factorial banks; no new worlds or outcome reads."""
import hashlib
import json
import sys
from pathlib import Path
import numpy as np
import pandas as pd

R=Path(__file__).parent
OUT=R/'2026-09-19-opportunity-support-transitions.json'
assert not OUT.exists()
factor=json.loads((R/'2026-09-19-usage-schedule-factorial.json').read_text())
cache=Path('/home/erich/projects/review-evidence/overnight-20260918/hsim-replay')
p=cache/'frame.parquet'
assert hashlib.sha256(p.read_bytes()).hexdigest()==factor['verified_archive']['frame.parquet']['sha256']
old=pd.read_parquet(p);new=old.copy(deep=True)
raw=(R/'2026-09-19-salaryfix-usage-input.json').read_bytes()
assert hashlib.sha256(raw).hexdigest()==factor['usage_input_sha256']
usage=pd.DataFrame(json.loads(raw)['rows']).set_index('gsis_id')
for col in ['snap_share_l4','target_share_l4','carry_share_l4','games_played_prior','rz20_target_share_l4','gl3_carry_share_l4']:
    new[col]=old[col].where(~old.id.isin(usage.index),pd.to_numeric(old.id.map(usage[col]),errors='raise'))
sys.path.insert(0,'/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs/src')
from nfl2.hsim.shares import active_mask
old_active,new_active=active_mask(old),active_mask(new)
banks={}
for case in ('A','B','C','D'):
    rec=factor['array_identities'][case+'_audit'];p=Path(rec['path'])
    assert hashlib.sha256(p.read_bytes()).hexdigest()==rec['sha256']
    banks[case]=np.load(p,allow_pickle=False)
rows=[]
for i,r in new.iterrows():
    if r.pos not in ('RB','WR','TE'):continue
    row=dict(id=str(r.id),name=r['name'],position=r.pos,old_active=bool(old_active[i]),new_active=bool(new_active[i]),
        snap_share=None if pd.isna(r.snap_share_l4) else float(r.snap_share_l4),
        observed_target_share=None if pd.isna(r.target_share_l4) else float(r.target_share_l4),
        observed_carry_share=None if pd.isna(r.carry_share_l4) else float(r.carry_share_l4))
    for case in banks:
        row[case+'_zero_score']=bool((banks[case][i]==0).all())
        row[case+'_target_weight']=factor['calibration'][case]['target_weights'][i]
        row[case+'_carry_weight']=factor['calibration'][case]['carry_weights'][i]
    rows.append(row)
df=pd.DataFrame(rows);counts={}
for before,after in [('A','B'),('C','D')]:
    counts[before+'-to-'+after]={}
    for pos in ('RB','WR','TE'):
        d=df[df.position.eq(pos)];a,b=d[before+'_zero_score'],d[after+'_zero_score']
        lost=(~a)&b;recovered=a&(~b)
        counts[before+'-to-'+after][pos]=dict(players=len(d),old_zero=int(a.sum()),new_zero=int(b.sum()),
            newly_zero=int(lost.sum()),recovered=int(recovered.sum()),
            newly_zero_with_snap_at_least_30pct=int((lost&d.snap_share.ge(.3)).sum()),
            old_inactive_to_new_active=int(((~d.old_active)&d.new_active).sum()),
            positive_target_weight_to_zero=int((d[before+'_target_weight'].gt(0)&d[after+'_target_weight'].eq(0)).sum()))
result=dict(counts=counts,players=json.loads(df.to_json(orient='records',double_precision=15)),
            source_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            scope='435-player archived slate with repaired usage. Not the full 877-row inference table; zero target weight is distinct from zero total score.')
with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps(counts,indent=2))
