"""Descriptive support census on already-opened factorial outputs; no resimulation/outcomes."""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT=Path(__file__).parent
OUT=ROOT/'2026-09-19-recovered-usage-zero-support.json'
assert not OUT.exists()
factor=json.loads((ROOT/'2026-09-19-usage-schedule-factorial.json').read_text())
usage_raw=(ROOT/'2026-09-19-salaryfix-usage-input.json').read_bytes()
assert hashlib.sha256(usage_raw).hexdigest()==factor['usage_input_sha256']
usage=pd.DataFrame(json.loads(usage_raw)['rows']).set_index('gsis_id')
cache=Path('/home/erich/projects/review-evidence/overnight-20260918/hsim-replay')
frpath=cache/'frame.parquet'
assert hashlib.sha256(frpath.read_bytes()).hexdigest()==factor['verified_archive']['frame.parquet']['sha256']
columns=['id','name','pos','team','depth_rank','is_cold_start','games_played_prior',
         'snap_share_l4','target_share_l4','carry_share_l4','mean_projection']
fr=pd.read_parquet(frpath,columns=columns)
for col in ['snap_share_l4','target_share_l4','carry_share_l4','games_played_prior']:
    fr[col]=fr[col].where(~fr.id.isin(usage.index),pd.to_numeric(fr.id.map(usage[col]),errors='raise'))
hrec=factor['array_identities']['D_audit'];hp=Path(hrec['path'])
assert hashlib.sha256(hp.read_bytes()).hexdigest()==hrec['sha256']
H=np.load(hp,allow_pickle=False);assert H.shape==(len(fr),10000)
ip=cache/'incumbent_player_scores.npy'
assert hashlib.sha256(ip.read_bytes()).hexdigest()==factor['verified_archive']['incumbent_player_scores.npy']['sha256']
I=np.load(ip,allow_pickle=False)
cands=pd.read_parquet(cache/'candidates.parquet',columns=['players'])
counts={}
for k in factor['books']['D']:
    for player in cands.players.iloc[k].split(','):counts[player]=counts.get(player,0)+1
sys.path.insert(0,'/home/erich/projects/.nfl2-worktrees/live-hsim-game-inputs/src')
from nfl2.hsim.shares import active_mask
fr['active']=active_mask(fr)
fr['final_target_weight']=factor['calibration']['D']['target_weights']
fr['final_carry_weight']=factor['calibration']['D']['carry_weights']
fr['H_all_zero']=(H==0).all(axis=1)
fr['H_mean']=H.mean(axis=1,dtype=np.float64)
fr['I_mean']=I.mean(axis=1,dtype=np.float64)
fr['selected_count']=fr.id.map(counts).fillna(0).astype(int)
routes=json.loads((ROOT/'2026-09-19-route-role-support.json').read_text())
assert not routes['invalid_rows']
lookup={r['gsis_id']:r for r in routes['source_records']};assert len(lookup)==len(routes['source_records'])
fr['fp_prior_route_share']=fr.id.map({k:v['route_share'] for k,v in lookup.items()})
skill=fr.pos.isin(['RB','WR','TE'])
zero=skill&fr.H_all_zero
active_zero=zero&fr.active
observed=active_zero&pd.to_numeric(fr.snap_share_l4).gt(0)
groups=[]
for pos in ['RB','WR','TE']:
    take=fr.pos.eq(pos)
    groups.append(dict(position=pos,players=int(take.sum()),all_zero_hsim=int((take&zero).sum()),
        active_zero_hsim=int((take&active_zero).sum()),active_zero_with_positive_snaps=int((take&observed).sum()),
        active_zero_with_positive_routes=int((take&active_zero&fr.fp_prior_route_share.gt(0)).sum()),
        selected_zero_players=int((take&zero&fr.selected_count.gt(0)).sum())))
details=json.loads(fr[active_zero].to_json(orient='records',double_precision=15))
result=dict(groups=groups,active_zero_players=details,source='existing canonical D factorial audit; no new worlds',
    meaning='Exact zero scores in saved simulator draws; positive prior activity is not proof of high-scoring potential.',
    source_route_job=routes['job_id'],current_outcome_reads=0,cloud_queries=0)
with OUT.open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps(result,indent=2),flush=True)
