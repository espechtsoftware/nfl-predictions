"""Read-only, outcome-blind census of timestamped practice-trajectory support."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
from google.cloud import bigquery

PROJECT='nfl-predictions-503414'
RAW=f'{PROJECT}.nfl_raw'
TABLES=['injuries','injury_snapshots','schedules','depth_charts','depth_charts_snapshots']

def main():
    out=Path(sys.argv[1]);assert not out.exists()
    client=bigquery.Client(project=PROJECT)
    cutoff=datetime.now(timezone.utc)
    metadata=[]
    for name in TABLES:
        t=client.get_table(f'{RAW}.{name}')
        metadata.append({'table':f'{RAW}.{name}','rows':t.num_rows,'bytes':t.num_bytes,
                         'modified':t.modified.isoformat(),'etag':t.etag,
                         'schema':[(f.name,f.field_type) for f in t.schema]})
    queries={
      'historical_source':f'''
WITH keys AS (
 SELECT CAST(season AS INT64) season, CAST(week AS INT64) week, gsis_id,
   COUNT(*) n, COUNTIF(date_modified IS NOT NULL) timestamped,
   COUNT(DISTINCT DATE(date_modified, 'America/New_York')) source_days,
   COUNT(DISTINCT practice_status) practice_states
 FROM `{RAW}.injuries` FOR SYSTEM_TIME AS OF @cutoff
 WHERE game_type='REG' AND gsis_id IS NOT NULL
 GROUP BY 1,2,3
)
SELECT season, SUM(n) row_count, COUNT(*) player_weeks,
 SUM(timestamped) timestamped_rows, COUNTIF(n>1) multirow_player_weeks,
 COUNTIF(source_days>1) multiday_player_weeks,
 COUNTIF(practice_states>1) changing_practice_player_weeks
FROM keys GROUP BY season ORDER BY season''',
      'captured_trajectory':f'''
WITH locks AS (
 SELECT season,week,MIN(TIMESTAMP(DATETIME(PARSE_DATE('%Y-%m-%d',gameday),
   SAFE.PARSE_TIME('%H:%M',gametime)),'America/New_York')) lock_at
 FROM `{RAW}.schedules` FOR SYSTEM_TIME AS OF @cutoff
 WHERE game_type='REG' AND weekday='Sunday'
 AND SAFE.PARSE_TIME('%H:%M',gametime)>=TIME '13:00:00'
 AND SAFE.PARSE_TIME('%H:%M',gametime)<TIME '19:00:00'
 GROUP BY season,week
), keys AS (
 SELECT i.season,i.week,i.gsis_id,COUNT(*) n,
 COUNT(DISTINCT capture_id) captures,
 COUNT(DISTINCT DATE(pulled_at,'America/New_York')) capture_days,
 COUNT(DISTINCT practice_status) practice_states,
 MIN(pulled_at) first_capture, MAX(pulled_at) last_capture
 FROM `{RAW}.injury_snapshots` AS i FOR SYSTEM_TIME AS OF @cutoff
 JOIN locks l USING(season,week)
 WHERE i.game_type='REG' AND i.gsis_id IS NOT NULL AND i.pulled_at<=l.lock_at
 AND i.pulled_at<=@cutoff AND (i.date_modified IS NULL OR i.date_modified<=i.pulled_at)
 GROUP BY i.season,i.week,i.gsis_id
)
SELECT season,week,SUM(n) row_count,COUNT(*) player_weeks,
 COUNTIF(capture_days>1) multiday_player_weeks,
 COUNTIF(practice_states>1) changing_practice_player_weeks,
 MAX(captures) maximum_captures,MIN(first_capture) first_capture,MAX(last_capture) last_capture
FROM keys GROUP BY season,week ORDER BY season,week''',
      'capture_timeline':f'''
SELECT season,week,pulled_at,COUNT(*) row_count,COUNT(DISTINCT gsis_id) players,
 COUNTIF(date_modified IS NOT NULL) source_timestamped,
 COUNTIF(date_modified>pulled_at) malformed_source_time
FROM `{RAW}.injury_snapshots` FOR SYSTEM_TIME AS OF @cutoff
WHERE game_type='REG' AND pulled_at<=@cutoff
GROUP BY season,week,pulled_at ORDER BY season,week,pulled_at''',
      'current_feature_freshness':f'''
SELECT season,week,injury_source_kind,COUNT(*) row_count,
 MIN(injury_information_at) earliest_information,MAX(injury_information_at) latest_information
FROM `{PROJECT}.nfl_features.player_week_injury` FOR SYSTEM_TIME AS OF @cutoff
WHERE season=2026 GROUP BY season,week,injury_source_kind ORDER BY season,week,injury_source_kind'''
    }
    result={'scope':'Input support only; no actuals, availability outcomes, or model fitting',
            'cutoff':cutoff.isoformat(),'metadata':metadata,'queries':{},'source_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    parameters=[bigquery.ScalarQueryParameter('cutoff','TIMESTAMP',cutoff)]
    for sql in queries.values():
        dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False,query_parameters=parameters))
        assert dry.total_bytes_processed<=100_000_000
    for name,sql in queries.items():
        job=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=100_000_000,query_parameters=parameters))
        rows=[dict(r) for r in job.result()]
        result['queries'][name]={'sql':sql,'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,'rows':rows}
        print(name,json.dumps(rows,default=str),flush=True)
    out.write_text(json.dumps(result,indent=2,default=str,allow_nan=False))

if __name__=='__main__': main()
