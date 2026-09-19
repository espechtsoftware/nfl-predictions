"""Aggregate column-level diagnosis of historical feature differences; no row values."""
import json
from pathlib import Path
from google.cloud import bigquery

P=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
old=json.loads((P.parent/'authorized-release-v1/before-tables-private.json').read_text())
history=json.loads((P/'feature-history-check.json').read_text())
client=bigquery.Client(project='nfl-predictions-503414');results=[]
for rec in history['rows']:
    if not rec['current_only'] and not rec['previous_only']:continue
    source=rec['source'];name=source.rsplit('.',1)[1]
    keys=['season','week','gsis_id' if name.startswith('player_') else 'team']
    fields=old[source]['schema'];assert set(keys)<={c['name'] for c in fields}
    structs=[]
    for col in fields:
        c=col['name'];a=f'a.`{c}`';b=f'b.`{c}`'
        numeric=col['type'] in ['FLOAT','FLOAT64','INTEGER','INT64','NUMERIC','BIGNUMERIC']
        delta=f'MAX(ABS(CAST({a} AS FLOAT64)-CAST({b} AS FLOAT64)))' if numeric else 'CAST(NULL AS FLOAT64)'
        relative=f'MAX(SAFE_DIVIDE(ABS(CAST({a} AS FLOAT64)-CAST({b} AS FLOAT64)),GREATEST(1.,ABS(CAST({a} AS FLOAT64)),ABS(CAST({b} AS FLOAT64)))))' if numeric else 'CAST(NULL AS FLOAT64)'
        structs.append(f"STRUCT('{c}' AS column_name,'{col['type']}' AS type,COUNTIF({a} IS DISTINCT FROM {b}) AS different,COUNTIF(({a} IS NULL)!=({b} IS NULL)) AS null_mismatch,{delta} AS max_abs_delta,{relative} AS max_scaled_delta)")
    backup='nfl-predictions-503414.nfl_release_20260919_input_repair.nfl_features__'+name
    join=' AND '.join(f'a.`{k}`=b.`{k}`' for k in keys)
    q=f"""WITH a AS (SELECT * FROM `{source}` WHERE season<2026),b AS (SELECT * FROM `{backup}` WHERE season<2026)
      SELECT COUNT(*) AS joined_rows,COUNTIF(a.season IS NULL) AS missing_current,COUNTIF(b.season IS NULL) AS missing_previous,
      [{','.join(structs)}] AS columns FROM a FULL OUTER JOIN b ON {join}"""
    dry=client.query(q,job_config=bigquery.QueryJobConfig(dry_run=True,maximum_bytes_billed=1_000_000_000));assert dry.total_bytes_processed<=1_000_000_000
    job=client.query(q,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
    value=dict(next(iter(job.result(timeout=600))));value['columns']=[dict(c) for c in value['columns']]
    result=dict(source=source,query=q,job_id=job.job_id,bytes_processed=job.total_bytes_processed,**value);results.append(result)
    with (P/(name+'-differences.json')).open('x') as f:json.dump(result,f,indent=2,allow_nan=False)
    assert value['joined_rows']==rec['current_rows']==rec['previous_rows'] and not value['missing_current'] and not value['missing_previous']
    print(json.dumps(dict(source=name,**{k:v for k,v in value.items() if k!='columns'},changed_columns=[c for c in value['columns'] if c['different']]),indent=2),flush=True)
with (P/'feature-differences.json').open('x') as f:json.dump(results,f,indent=2,allow_nan=False)
