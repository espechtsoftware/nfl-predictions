"""Replay unchanged usage SQL with old salary spine and current raw inputs in a job TEMP table."""
import json
import hashlib
from pathlib import Path
from google.cloud import bigquery

P=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
R=Path('/home/erich/projects/.nfl-predictions-worktrees/salary-week-resolution')
source=R/'sql/features/014_player_week_usage.sql';sql=source.read_text()
header='CREATE OR REPLACE TABLE `${features}.player_week_usage` AS'
assert sql.count(header)==1;sql=sql.replace(header,'CREATE TEMP TABLE replay_usage AS')
old_salary='`nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__dk_salary_week`'
assert sql.count('`${features}.dk_salary_week`')==1
sql=sql.replace('`${features}.dk_salary_week`',old_salary)
for a,b in [('${features}','nfl-predictions-503414.nfl_features'),('${raw}','nfl-predictions-503414.nfl_raw'),('${prior_k}','4')]:
    assert a in sql;sql=sql.replace(a,b)
assert '${' not in sql
metadata=json.loads((P.parent/'authorized-release-v1/before-tables-private.json').read_text())
fields=metadata['nfl-predictions-503414.nfl_features.player_week_usage']['schema'];parts=[]
for f in fields:
    c=f['name'];a=f'a.`{c}`';b=f'b.`{c}`';numeric=f['type'] in ['FLOAT','FLOAT64','INTEGER','INT64','NUMERIC']
    delta=f'MAX(ABS(CAST({a} AS FLOAT64)-CAST({b} AS FLOAT64)))' if numeric else 'CAST(NULL AS FLOAT64)'
    parts.append(f"STRUCT('{c}' AS column_name,'{f['type']}' AS type,COUNTIF({a} IS DISTINCT FROM {b}) AS different,COUNTIF(({a} IS NULL)!=({b} IS NULL)) AS null_mismatch,{delta} AS max_abs_delta)")
sql+=f"""\nWITH a AS (SELECT * FROM `nfl-predictions-503414.nfl_features.player_week_usage` WHERE season<2026),
b AS (SELECT * FROM replay_usage WHERE season<2026)
SELECT COUNT(*) AS joined_rows,COUNTIF(a.season IS NULL) AS missing_current,COUNTIF(b.season IS NULL) AS missing_replay,
[{','.join(parts)}] AS columns FROM a FULL OUTER JOIN b USING(gsis_id,season,week)"""
client=bigquery.Client(project='nfl-predictions-503414')
job=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=2_000_000_000))
result=dict(next(iter(job.result(timeout=600))));result['columns']=[dict(x) for x in result['columns']]
result.update(job_id=job.job_id,bytes_processed=job.total_bytes_processed,query=sql,
              unchanged_usage_sql_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),
              scope='old salary table; current other inputs; original usage SQL; job-local TEMP only')
with (P/'usage-drift-replay.json').open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:v for k,v in result.items() if k!='query'},indent=2),flush=True)
assert result['joined_rows']==102927 and result['missing_current']==result['missing_replay']==0
assert all(c['different']==0 or (c['type']=='FLOAT' and not c['null_mismatch'] and c['max_abs_delta']<1e-12) for c in result['columns'])
print('UNCHANGED_USAGE_OLD_SALARY_CURRENT_RAW_REPRODUCES_HISTORY_PASS',flush=True)
