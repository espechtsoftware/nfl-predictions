"""Outcome-blind historical injury-type support on the frozen training universe."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import pandas as pd
from google.cloud import bigquery

E=Path(__file__).resolve().parent
SAFE_COLUMNS=['gsis_id','season','week','team','game_id','position','injury_status','practice_level',
              'practice_participation_trend','snap_share_l4','target_share_l4','targets_l4',
              'depth_rank','games_played_prior','salary']
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    out=Path(sys.argv[1]);assert not out.exists()
    meta=json.loads((E/'2026-09-19-zero-target-prior-current-support.json').read_text())
    assert sha(meta['path'])==meta['input']['sha256']
    features=E.parents[2]/'src/nfl_dfs/models/featureset.py'
    spec=importlib.util.spec_from_file_location('pinned_featureset',features)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    numeric=list(dict.fromkeys([*module.NUMERIC_FEATURES,'targets_l4','practice_level',
        'practice_participation_trend','games_missed_l4','target_share_last','snap_share_last']))
    columns=list(dict.fromkeys([*SAFE_COLUMNS,*numeric]))
    assert not any(c=='was_active' or c=='actual' or c.startswith('y_') for c in columns)
    frame=pd.read_parquet(meta['path'],columns=columns,filters=[('season','<',2025)])
    assert not frame.duplicated(['gsis_id','season','week']).any()
    cutoff=datetime.now(timezone.utc);client=bigquery.Client(project='nfl-predictions-503414')
    sql='''WITH locks AS (
 SELECT season,week,MIN(TIMESTAMP(DATETIME(PARSE_DATE('%Y-%m-%d',gameday),
 SAFE.PARSE_TIME('%H:%M',gametime)),'America/New_York')) lock_at
 FROM `nfl-predictions-503414.nfl_raw.schedules` FOR SYSTEM_TIME AS OF @cutoff
 WHERE game_type='REG' AND weekday='Sunday'
 AND SAFE.PARSE_TIME('%H:%M',gametime)>=TIME '13:00:00'
 AND SAFE.PARSE_TIME('%H:%M',gametime)<TIME '19:00:00'
 GROUP BY season,week
)
SELECT i.gsis_id,CAST(i.season AS INT64) season,CAST(i.week AS INT64) week,
i.report_status,i.practice_status,i.report_primary_injury,i.report_secondary_injury,
i.practice_primary_injury,i.practice_secondary_injury,i.date_modified,l.lock_at
FROM `nfl-predictions-503414.nfl_raw.injuries` AS i FOR SYSTEM_TIME AS OF @cutoff
JOIN locks l ON l.season=CAST(i.season AS INT64) AND l.week=CAST(i.week AS INT64)
WHERE i.game_type='REG' AND i.season BETWEEN 2014 AND 2024
AND i.gsis_id IS NOT NULL AND i.date_modified<=l.lock_at
QUALIFY ROW_NUMBER() OVER(PARTITION BY i.gsis_id,CAST(i.season AS INT64),CAST(i.week AS INT64)
 ORDER BY i.date_modified DESC,i.team DESC,i.practice_status DESC)=1'''
    params=[bigquery.ScalarQueryParameter('cutoff','TIMESTAMP',cutoff)]
    dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False,query_parameters=params))
    assert dry.total_bytes_processed<100_000_000
    job=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100_000_000,query_parameters=params))
    injury=pd.DataFrame([dict(x) for x in job.result()])
    assert not injury.duplicated(['gsis_id','season','week']).any()
    assert (injury.date_modified<=injury.lock_at).all()
    data=frame.merge(injury,on=['gsis_id','season','week'],how='left',validate='one_to_one')
    calendar_sql='''SELECT game_id,season,week FROM `nfl-predictions-503414.nfl_raw.schedules`
FOR SYSTEM_TIME AS OF @cutoff WHERE game_type='REG' AND season BETWEEN 2014 AND 2024
AND weekday='Sunday' AND SAFE.PARSE_TIME('%H:%M',gametime)>=TIME '13:00:00'
AND SAFE.PARSE_TIME('%H:%M',gametime)<TIME '19:00:00' '''
    dry=client.query(calendar_sql,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False,query_parameters=params))
    assert dry.total_bytes_processed<100_000_000
    calendar_job=client.query(calendar_sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100_000_000,query_parameters=params))
    calendar=pd.DataFrame([dict(x) for x in calendar_job.result()])
    assert calendar.game_id.is_unique
    allowed=set(zip(calendar.season,calendar.week,calendar.game_id))
    data['sunday_main']=[(s,w,g) in allowed for s,w,g in zip(data.season,data.week,data.game_id)]
    data['receiving_role']=data.position.isin(['RB','WR','TE'])&data.snap_share_l4.ge(.2)&data.games_played_prior.ge(1)
    data['has_report']=data.date_modified.notna()
    data['type']=data.report_primary_injury.astype('string').str.strip().replace('',pd.NA).fillna(
        data.practice_primary_injury.astype('string').str.strip().replace('',pd.NA))
    data['has_type']=data.type.notna()
    data['q']=data.injury_status.eq('Questionable').fillna(False)
    data['status_mismatch']=data.has_report&data.injury_status.astype('string').fillna('NONE').ne(data.report_status.astype('string').fillna('NONE'))
    safe=out.with_suffix('.parquet');assert not safe.exists();data.to_parquet(safe,index=False)
    rows=[]
    for (year,pos),g in data[data.receiving_role&data.sunday_main].groupby(['season','position']):
        rows.append({'season':int(year),'position':pos,'rows':len(g),'reports':int(g.has_report.sum()),
                     'with_type':int(g.has_type.sum()),'questionable':int(g.q.sum()),
                     'questionable_with_type':int((g.q&g.has_type).sum()),
                     'report_status_mismatches':int(g.status_mismatch.sum())})
    types=data[data.receiving_role&data.sunday_main&data.has_type].groupby('type').size().sort_values(ascending=False).to_dict()
    result={'outcomes_read':False,'cutoff':cutoff.isoformat(),'query':sql,'query_job':job.job_id,
            'bytes_processed':job.total_bytes_processed,'frame_sha256':meta['input']['sha256'],
            'safe_frame_columns':columns,'baseline_numeric_features':numeric,'featureset_sha256':sha(features),
            'source_sha256':sha(__file__),'calendar_sql':calendar_sql,'calendar_query_job':calendar_job.job_id,
            'calendar_bytes_processed':calendar_job.total_bytes_processed,
            'safe_extract_path':str(safe),'safe_extract_sha256':sha(safe),
            'historical_frame_rows':len(frame),'raw_pit_reports':len(injury),'support':rows,
            'types':{str(k):int(v) for k,v in types.items()}}
    out.write_text(json.dumps(result,indent=2,allow_nan=False))
    print(json.dumps({'rows':len(data),'receiving_role_sunday_rows':int((data.receiving_role&data.sunday_main).sum()),
        'support':rows,'top_types':dict(list(result['types'].items())[:20])},indent=2))

if __name__=='__main__':main()
