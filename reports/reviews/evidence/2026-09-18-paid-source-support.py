"""Follow-up to preflight: support counts and metadata order, no outcomes."""
import hashlib,json
from datetime import datetime,timezone
from pathlib import Path
from google.cloud import bigquery,storage
ROOT=Path(__file__).parent
prior=json.loads((ROOT/'2026-09-18-paid-source-preflight.json').read_text())
r={'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'source_support':[],'model_metadata_order':[]}
c=bigquery.Client(project='nfl-predictions-503414')
for table,week,field in [('fantasy_points_route_share','week','route_share'),('fantasy_points_advanced_receiving_windows','target_week','fp_adv_rec_first_read_rate'),('fantasy_points_alignment_player_l4','target_week','player_wide_share'),('sis_team_context_game','week','pdef_boom_rate')]:
 sql=f'''SELECT season, COUNT(*) AS n_rows, MIN({week}) AS first_week, MAX({week}) AS last_week,
 COUNTIF({field} IS NOT NULL) AS supported_rows, MAX(ingested_at) AS latest_import
 FROM `nfl-predictions-503414.nfl_raw.{table}` GROUP BY season ORDER BY season'''
 job=c.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100_000_000))
 r['source_support'].append({'table':table,'support_field':field,'query':sql,'job_id':job.job_id,'rows':[dict(x) for x in job.result()],'bytes_processed':job.total_bytes_processed})
s=storage.Client(project='nfl-predictions-503414')
for m in prior['checks']['registered_features']['models']:
 if m['metadata_matches_serialized_features']:continue
 uri=m['metadata_uri'];bucket,name=uri.removeprefix('gs://').split('/',1)
 b=s.bucket(bucket).blob(name,generation=int(m['metadata_generation']))
 meta=json.loads(b.download_as_bytes(if_generation_match=int(m['metadata_generation'])))
 names=meta.get('features',[]);actual=m['features']
 r['model_metadata_order'].append({'label':m['label'],'set_equal':set(names)==set(actual),'metadata_only':sorted(set(names)-set(actual)),'model_only':sorted(set(actual)-set(names)),'metadata_count':len(names),'serialized_count':len(actual),'metadata_names':names})
(ROOT/'2026-09-18-paid-source-support.json').write_text(json.dumps(r,indent=2,default=str)+'\n')
print(json.dumps({'support':[{k:v for k,v in x.items() if k in ['table','rows']} for x in r['source_support']],'metadata_order':[{k:v for k,v in x.items() if k!='metadata_names'} for x in r['model_metadata_order']]},indent=2,default=str))
