"""Read-only feature release checks; aggregate identities/support, no label values."""
import hashlib
import json
from pathlib import Path
from google.cloud import bigquery

ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
BASE=ROOT.parent/'authorized-release-v1'
client=bigquery.Client(project='nfl-predictions-503414')
assert (ROOT/'build-features-result.json').exists()
out=ROOT/'feature-validation.json';assert not out.exists()
before=json.loads((BASE/'before-tables-private.json').read_text())
plan=json.loads((Path(__file__).parent/'2026-09-19-release-plan.json').read_text())
parts=[]
for r in plan['tables']:
    a=r['source'];b=r['snapshot'];meta=before[a]
    if '.nfl_features.' not in a or a.endswith('.tabpfn_projections'):continue
    columns=[f['name'] for f in meta['schema']]
    current=client.get_table(a)
    assert [f.to_api_repr() for f in current.schema]==meta['schema'],a
    if 'season' not in columns:continue
    parts.append(f"""SELECT '{a}' AS source,
      (SELECT COUNT(*) FROM `{a}` WHERE season<2026) AS current_rows,
      (SELECT COUNT(*) FROM `{b}` WHERE season<2026) AS previous_rows,
      (SELECT COUNT(*) FROM (SELECT TO_JSON_STRING(t) AS row_json FROM `{a}` t WHERE season<2026
        EXCEPT DISTINCT SELECT TO_JSON_STRING(t) FROM `{b}` t WHERE season<2026)) AS current_only,
      (SELECT COUNT(*) FROM (SELECT TO_JSON_STRING(t) AS row_json FROM `{b}` t WHERE season<2026
        EXCEPT DISTINCT SELECT TO_JSON_STRING(t) FROM `{a}` t WHERE season<2026)) AS previous_only""")
sql='\nUNION ALL\n'.join(parts)
def query(sql,limit=5_000_000_000):
    assert sql.lstrip().startswith(('SELECT','WITH')) and ';' not in sql
    dry=client.query(sql,job_config=bigquery.QueryJobConfig(dry_run=True,maximum_bytes_billed=limit))
    assert dry.total_bytes_processed<=limit
    j=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=limit))
    rows=[dict(r) for r in j.result(timeout=900)]
    return dict(query=sql,sha256=hashlib.sha256(sql.encode()).hexdigest(),job_id=j.job_id,
                bytes_processed=j.total_bytes_processed,rows=rows)
history=query(sql)
with (ROOT/'feature-history-check.json').open('x') as f:json.dump(history,f,indent=2)
support=query("""SELECT
 (SELECT COUNT(*) FROM `nfl-predictions-503414.nfl_features.dk_salary_week` WHERE season=2026 AND week=1) salary_w1,
 (SELECT COUNT(*) FROM `nfl-predictions-503414.nfl_features.dk_salary_week` WHERE season=2026 AND week=2) salary_w2,
 (SELECT COUNT(*) FROM (SELECT gsis_id,season,week FROM `nfl-predictions-503414.nfl_features.dk_salary_week` GROUP BY 1,2,3 HAVING COUNT(*)>1)) salary_duplicate_keys,
 (SELECT COUNT(*) FROM (SELECT gsis_id,season,week FROM `nfl-predictions-503414.nfl_features.player_week_inference` GROUP BY 1,2,3 HAVING COUNT(*)>1)) inference_duplicate_keys,
 (SELECT COUNT(*) FROM (SELECT gsis_id,season,week FROM `nfl-predictions-503414.nfl_features.player_week_training` GROUP BY 1,2,3 HAVING COUNT(*)>1)) training_duplicate_keys,
 (SELECT COUNT(*) FROM `nfl-predictions-503414.nfl_features.player_week_inference` WHERE season=2026 AND week=2) inference_w2,
 (SELECT COUNTIF(games_played_prior>0) FROM `nfl-predictions-503414.nfl_features.player_week_inference` WHERE season=2026 AND week=2) inference_w2_prior_games,
 (SELECT COUNTIF(snap_share_l4 IS NOT NULL) FROM `nfl-predictions-503414.nfl_features.player_week_inference` WHERE season=2026 AND week=2) inference_w2_snap,
 (SELECT MAX(games_played_prior) FROM `nfl-predictions-503414.nfl_features.player_week_inference` WHERE season=2026 AND week=2) inference_w2_max_prior_games,
 (SELECT COUNTIF(games_played_prior>0) FROM `nfl-predictions-503414.nfl_features.player_week_usage` WHERE season=2026 AND week=1) usage_w1_future_support
""")
result=dict(history=history,support=support,scope='engineering aggregate parity/support only; no label values returned')
with out.open('x') as f:json.dump(result,f,indent=2)
print(json.dumps({'history_differences':[r for r in history['rows'] if r['current_rows']!=r['previous_rows'] or r['current_only'] or r['previous_only']], 'support':support['rows']},indent=2),flush=True)
r=support['rows'][0]
assert r['salary_w1']>0 and r['salary_w2']>0 and r['inference_w2_prior_games']>0 and r['inference_w2_snap']>0
assert r['inference_w2_max_prior_games']==1 and r['usage_w1_future_support']==0
assert not any(r[k] for k in ('salary_duplicate_keys','inference_duplicate_keys','training_duplicate_keys'))
assert all(r['current_rows']==r['previous_rows'] and r['current_only']==r['previous_only']==0 for r in history['rows']), 'historical differences need review, not automatic acceptance'
print('FEATURE_PARITY_AND_SUPPORT_PASS',flush=True)
