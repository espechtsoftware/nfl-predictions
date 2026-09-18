"""Outcome-free metadata and synthetic checks; no training, vendor pulls or mutations."""
import hashlib, json, subprocess
from datetime import datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
from google.cloud import bigquery, storage
from nfl_dfs.models import prop_market
from nfl_dfs.inference.run_projections import _props_first_market_with_dk_fallback

ROOT=Path(__file__).resolve().parents[3]
OUT=Path(__file__).with_suffix('.json')
result={'started_at_utc':datetime.now(timezone.utc).isoformat(),'code_sha':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),'checks':{}}
def save(): OUT.write_text(json.dumps(result,indent=2,default=str)+'\n')
def stage(name,fn):
 try: result['checks'][name]=fn()
 except Exception as e: result['checks'][name]={'error_type':type(e).__name__,'message':str(e)[:600]}
 save();print(name, 'recorded',flush=True)

def synthetic():
 schedule=pd.DataFrame([dict(season=2026,week=2,gameday='2026-09-20',gametime='13:00',game_type='REG',weekday='Sunday')])
 def quote(point,ts,side='Over',market='player_reception_yds'):
  return dict(season=2026,week=2,bookmaker='synthetic',market=market,player='Synthetic Receiver',outcome_name=side,price=-110,point=point,snapshot_ts=ts)
 rows=[quote(pt,ts,side) for pt,ts in [(49.5,'2026-09-20T09:00:00Z'),(59.5,'2026-09-20T16:00:00Z'),(69.5,'2026-09-20T18:00:00Z')] for side in ['Over','Under']]
 moved,audit=prop_market.latest_pre_main_lock(pd.DataFrame(rows),schedule)
 mixed,_=prop_market.latest_pre_main_lock(pd.DataFrame([quote(59.5,'2026-09-20T09:00:00Z','Under'),quote(59.5,'2026-09-20T16:00:00Z')]),schedule)
 fallback=np.full(10,20.0);two=np.array([10.,10.]+[np.nan]*8);three=two.copy();three[2]=10.
 before,mask0=_props_first_market_with_dk_fallback(fallback,two);after,mask1=_props_first_market_with_dk_fallback(fallback,three)
 original=prop_market.query_df
 partial=pd.DataFrame([quote(pt,'2026-09-20T16:00:00Z',side,m) for m,pt in [('player_reception_yds',59.5),('player_receptions',4.5)] for side in ['Over','Under']])
 def fake(sql,*args,**kwargs):
  if '.prop_lines`' in sql:return partial.copy()
  if '.schedules`' in sql:return schedule.copy()
  return pd.DataFrame([{'gsis_id':'00-0000001','display_name':'Synthetic Receiver'}])
 try:
  prop_market.query_df=fake
  partial_result=prop_market.market_points((2026,),minimum_markets=2)
 finally:prop_market.query_df=original
 return {'source_sha256':hashlib.sha256((ROOT/'src/nfl_dfs/models/prop_market.py').read_bytes()).hexdigest(),
 'moved_main_line':{'observed_points':sorted(moved.point.unique().tolist()),'desired_latest_only':[59.5],'old_point_survives':bool((moved.point==49.5).any()),'cutoff_audit':audit},
 'mixed_sides':{'distinct_timestamps':sorted(mixed.snapshot_ts.unique().tolist()),'both_sides_retained':set(mixed.outcome_name)=={'Over','Under'}},
 'coverage_gate':{'true_prop_rows_before':int(mask0.sum()),'true_prop_rows_after':int(mask1.sum()),'previously_covered_player_market_before':float(before[0]),'after':float(after[0])},
 'two_markets_without_td':{'accepted_player_rows':len(partial_result),'markets':['player_reception_yds','player_receptions'],'note':'Accepted proxy lacks TD component; this is a completeness limitation, not an asserted requirement to invent a TD quote.'}}

def registry():
 client=storage.Client(project='nfl-predictions-503414');bucket=client.bucket('nfl-predictions-503414-raw')
 metas=[b for b in client.list_blobs(bucket,prefix='models/pooled/') if b.name.endswith('/meta.json') and any(f'__{v}/' in b.name for v in ['tail_k1','tail_k1_role','tail_k1_route'])]
 latest={}
 for b in metas:
  label,week=b.name.split('/')[-3:-1]
  if label not in latest or week>latest[label][0]:latest[label]=(week,b)
 rows=[]
 for label,(week,b) in sorted(latest.items()):
  payload=b.download_as_bytes(if_generation_match=int(b.generation));meta=json.loads(payload)
  base=b.name.rsplit('/',1)[0];model=bucket.blob(base+'/model.txt');model.reload()
  raw=model.download_as_bytes(if_generation_match=int(model.generation));features=[]
  for line in raw.decode().splitlines():
   if line.startswith('feature_names='):features=line.split('=',1)[1].split();break
  rows.append({'label':label,'week':week,'metadata_uri':f'gs://{bucket.name}/{b.name}','metadata_generation':b.generation,'metadata_sha256':hashlib.sha256(payload).hexdigest(),'model_generation':model.generation,'model_sha256':hashlib.sha256(raw).hexdigest(),'features':features,'metadata_matches_serialized_features':features==meta.get('features'),'vendor_features':[x for x in features if x.startswith(('fp_','sis_'))]})
 return {'models':rows,'note':'Features only; validation metrics and model predictions not exposed. Latest registry objects are not proof a specific past book loaded them.'}

def warehouse():
 c=bigquery.Client(project='nfl-predictions-503414')
 q="""SELECT table_name,column_name,data_type FROM `nfl-predictions-503414.nfl_raw.INFORMATION_SCHEMA.COLUMNS` WHERE STARTS_WITH(table_name,'fantasy_points_') OR STARTS_WITH(table_name,'sis_') ORDER BY table_name,ordinal_position"""
 job=c.query(q,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100_000_000));rows=[dict(r) for r in job.result()]
 tables={}
 for r in rows:tables.setdefault(r['table_name'],[]).append({'name':r['column_name'],'type':r['data_type']})
 return {'query':q,'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,'tables':tables}

def operations():
 rows=[]
 for job in ['shadow-sis-pass-tail-paired','shadow-k1-route-roleunion']:
  cmd=['gcloud','run','jobs','executions','list',f'--job={job}','--project=nfl-predictions-503414','--region=us-central1','--limit=3','--format=json(metadata.name,status.startTime,status.completionTime,status.succeededCount,status.failedCount)']
  p=subprocess.run(cmd,capture_output=True,text=True)
  rows.append({'job':job,'executions':json.loads(p.stdout) if p.returncode==0 else [],'error':p.stderr[-350:] if p.returncode else None})
 cmd=['gcloud','scheduler','jobs','list','--project=nfl-predictions-503414','--location=us-central1','--format=json(name,state,schedule,timeZone,lastAttemptTime)']
 p=subprocess.run(cmd,capture_output=True,text=True)
 sched=[x for x in json.loads(p.stdout) if 'sis' in x.get('name','') or 'route' in x.get('name','')] if p.returncode==0 else []
 return {'execution_metadata':rows,'schedulers':sched,'scheduler_error':p.stderr[-350:] if p.returncode else None,'note':'Execution success can represent a pre-Week-5 eligibility skip, not a delivered treatment book.'}

stage('synthetic_odds',synthetic)
stage('registered_features',registry)
stage('warehouse_schema',warehouse)
stage('shadow_operations',operations)
result['finished_at_utc']=datetime.now(timezone.utc).isoformat();save()
