# Mechanical serialization amendment only: optional missing name/position fields become JSON null.
# Original completed calculations and partial JSON remain in prop-snapshot-impact.
"""Current quote-coherence engineering contrast; no production writes or outcomes."""
import hashlib,json,sys
from datetime import time
from pathlib import Path
import numpy as np
import pandas as pd
from google.cloud import bigquery
REPO=Path(__file__).resolve().parents[3]
ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918')
INPUT=ROOT/'prop-snapshot-census';OUT=ROOT/'prop-snapshot-impact-v2'

def coherent(props,schedules):
    p=props.copy();p['_snapshot']=pd.to_datetime(p.snapshot_ts,utc=True,errors='coerce')
    s=schedules[schedules.game_type.eq('REG')&schedules.weekday.eq('Sunday')].copy()
    tm=pd.to_datetime(s.gametime.astype(str),format='%H:%M',errors='coerce').dt.time
    s=s[tm.map(lambda t:pd.notna(t) and time(13)<=t<time(19))].copy()
    s['_lock']=pd.to_datetime(s.gameday.astype(str)+' '+s.gametime.astype(str),errors='coerce').dt.tz_localize('America/New_York',ambiguous='NaT',nonexistent='shift_forward').dt.tz_convert('UTC')
    locks=s.dropna(subset=['_lock']).groupby(['season','week'],observed=True)._lock.min().reset_index()
    q=p.merge(locks,on=['season','week'],how='inner',validate='many_to_one')
    q=q[q._snapshot.notna()&q._snapshot.lt(q._lock)].copy()
    group=['season','week','event_id','bookmaker','market','player']
    assert q[group].notna().all().all(),'coherent event/market identity required'
    q=q[q._snapshot.eq(q.groupby(group,dropna=False)._snapshot.transform('max'))].copy()
    key=group+['point','outcome_name','_snapshot']
    assert not q.groupby(key,dropna=False).price.nunique(dropna=False).gt(1).any(),'conflicting same-snapshot price'
    q=q.drop_duplicates(key,keep='first')
    return q.drop(columns=['_snapshot','_lock']),dict(input_rows=len(p),main_slate_weeks=len(locks),prelock_rows=len(q),postlock_rows_excluded=int((p._snapshot>=s._lock.min()).sum()))

def smoke():
    s=pd.DataFrame([dict(season=2026,week=2,gameday='2026-09-20',gametime='13:00',game_type='REG',weekday='Sunday')])
    def row(point,ts,side,price=-110):return dict(season=2026,week=2,event_id='e',bookmaker='b',market='player_reception_yds',player='Synthetic',price=price,point=point,outcome_name=side,snapshot_ts=ts)
    early='2026-09-20T09:00:00Z';late='2026-09-20T16:00:00Z';post='2026-09-20T18:00:00Z'
    base=[row(pt,ts,side) for pt,ts in [(49.5,early),(59.5,late),(69.5,post)] for side in ['Over','Under']]
    d,_=coherent(pd.DataFrame(base),s);assert len(d)==2 and set(d.point)=={59.5}
    d,_=coherent(pd.DataFrame([row(49.5,early,'Over'),row(49.5,early,'Under'),row(49.5,late,'Over')]),s)
    assert len(d)==1 and set(d.outcome_name)=={'Over'},'older Under must not be backfilled'
    alternate=[row(pt,late,side) for pt in [49.5,59.5] for side in ['Over','Under']]
    d,_=coherent(pd.DataFrame(alternate),s);assert len(d)==4 and d.point.nunique()==2
    d,_=coherent(pd.DataFrame(alternate+[alternate[0].copy()]),s);assert len(d)==4
    try:coherent(pd.DataFrame(alternate+[row(49.5,late,'Over',-120)]),s)
    except AssertionError as e:assert 'conflicting' in str(e)
    else:raise AssertionError('conflicting same-snapshot prices accepted')
    print('SYNTHETIC_BOUNDARIES_PASS',flush=True)

def main():
    smoke();OUT.mkdir(exist_ok=False);sys.path.insert(0,str(REPO/'src'))
    from nfl_dfs.models import prop_market as pm
    props=pd.read_parquet(INPUT/'props.parquet');sched=pd.read_parquet(INPUT/'schedules.parquet')
    census=json.loads((INPUT/'census.json').read_text())
    assert all(hashlib.sha256((INPUT/(name+'.parquet')).read_bytes()).hexdigest()==q['sha256'] for name,q in zip(['props','schedules'],census['queries']))
    client=bigquery.Client(project='nfl-predictions-503414');queries=[];cached={}
    def query(sql):
        if '.nfl_raw.prop_lines' in sql:return props.copy(deep=True)
        if '.nfl_raw.schedules' in sql:return sched.copy(deep=True)
        assert sql.lstrip().startswith('SELECT DISTINCT gsis_id, display_name') and ';' not in sql
        if sql not in cached:
            j=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1000000000));d=j.result(timeout=300).to_dataframe()
            cached[sql]=d;d.to_parquet(OUT/'names.parquet',index=False)
            queries.append(dict(sql=sql,job_id=j.job_id,bytes_processed=j.total_bytes_processed,rows=len(d)))
        return cached[sql].copy(deep=True)
    pm.query_df=query;original=pm.latest_pre_main_lock
    old=pm.market_points((2026,),minimum_markets=2);old.to_parquet(OUT/'control-market.parquet',index=False)
    pm.latest_pre_main_lock=coherent
    new=pm.market_points((2026,),minimum_markets=2);new.to_parquet(OUT/'coherent-market.parquet',index=False)
    pm.latest_pre_main_lock=original
    key=['season','week','gsis_id'];assert not old.duplicated(key).any() and not new.duplicated(key).any()
    assert set(old.week)==set(new.week)=={2}
    pair=old.merge(new,on=key,how='outer',suffixes=('_control','_coherent'),indicator=True,validate='one_to_one')
    pair['delta']=pair.market_points_coherent-pair.market_points_control
    assert np.isfinite(pair.loc[pair._merge.eq('both'),['market_points_control','market_points_coherent']].to_numpy()).all()
    proof=json.loads((ROOT/'authorized-release-v2/live-cli-host-proof.json').read_text())
    frame=pd.read_parquet(Path(proof['run'])/'frame.parquet',columns=['gsis_id','name','pos'])
    pair=pair.merge(frame.drop_duplicates('gsis_id'),on='gsis_id',how='left',validate='one_to_one')
    pair.to_parquet(OUT/'paired-market.parquet',index=False)
    stamp=proof['receipt']['config']['production_generated_at']
    sql='SELECT gsis_id,position FROM `nfl-predictions-503414.nfl_predictions.player_projections` WHERE season=2026 AND week=2 AND generated_at=@stamp'
    j=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1000000000,query_parameters=[bigquery.ScalarQueryParameter('stamp','TIMESTAMP',stamp)]))
    pr=j.result(timeout=300).to_dataframe();assert len(pr)==504
    ids=set(pr[pr.position.ne('DST')].gsis_id);assert len(ids)==472
    control_matches=len(set(old.gsis_id)&ids);new_matches=len(set(new.gsis_id)&ids);assert control_matches==185
    summaries={}
    for label,mask in [('all_priced',pair._merge.eq('both')),('actual_proof_frame',pair._merge.eq('both')&pair.name.notna()),('projection_consumer',pair._merge.eq('both')&pair.gsis_id.isin(ids))]:
        d=pair[mask];delta=d.delta
        summaries[label]=dict(paired=len(d),changed_above_1e_8=int(delta.abs().gt(1e-8).sum()),mean_signed=float(delta.mean()),
          mean_absolute=float(delta.abs().mean()),max_absolute=float(delta.abs().max()),
          largest=d.loc[delta.abs().sort_values(ascending=False).index].head(20).drop(columns='_merge').astype(object).where(lambda x:x.notna(),None).to_dict('records'))
    result=dict(scope='Prelock quote-integrity numerical effect only; no efficacy or live adoption',control_rows=len(old),coherent_rows=len(new),
      control_only=pair[pair._merge.eq('left_only')].gsis_id.tolist(),coherent_only=pair[pair._merge.eq('right_only')].gsis_id.tolist(),
      exact_projection_skill_rows=472,control_real_prop_matches=control_matches,coherent_real_prop_matches=new_matches,
      crosses_thirty_percent_gate=(control_matches/472>=.3)!=(new_matches/472>=.3),summaries=summaries,
      queries=queries+[dict(sql=sql,job_id=j.job_id,rows=len(pr),projection_stamp=stamp)],
      artifacts={f.name:hashlib.sha256(f.read_bytes()).hexdigest() for f in OUT.glob('*.parquet')},
      script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),production_source_sha256=hashlib.sha256((REPO/'src/nfl_dfs/models/prop_market.py').read_bytes()).hexdigest())
    with (OUT/'result.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False,default=str)
    print(json.dumps(result,indent=2,default=str),flush=True)
if __name__=='__main__':main()
