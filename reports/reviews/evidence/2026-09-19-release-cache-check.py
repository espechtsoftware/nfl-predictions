"""Validate actual cache publication and its logged strict pre-week receipt."""
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
import pandas as pd
from google.cloud import bigquery

P=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
PROJECT='nfl-predictions-503414'
def main():
    execution=json.loads((P/'tabpfn-gen-result.json').read_text())['execution'].split('/')[-1]
    filt=f'resource.type="cloud_run_job" AND resource.labels.job_name="tabpfn-gen" AND labels."run.googleapis.com/execution_name"="{execution}"'
    raw=subprocess.check_output(['gcloud','logging','read',filt,'--project='+PROJECT,'--freshness=3h','--limit=1000','--format=json'])
    logs=json.loads(raw);(P/'tabpfn-gen-logs.json').write_bytes(raw)
    reports=[json.loads(x['textPayload'].split('TABPFN_GEN_JSON=',1)[1]) for x in logs if 'TABPFN_GEN_JSON=' in x.get('textPayload','')]
    assert len(reports)==1,'missing or duplicate cache receipt; reconcile, do not infer from rows alone'
    r=reports[0]
    assert r['context_law']=='strictly-prior-season-week-nonnull-labels'
    assert r['training_target_exclusive']==r['upcoming_target']==[2026,2]
    assert r['upcoming_only'] is False and r['target_seasons']==[2019,2021,2022,2023,2024,2025]
    assert r['output_table']==PROJECT+'.nfl_features.tabpfn_projections'
    client=bigquery.Client(project=PROJECT);queries=[]
    def read(sql):
        assert sql.lstrip().startswith(('SELECT','WITH')) and ';' not in sql
        j=client.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000))
        result=j.result(timeout=300).to_dataframe()
        queries.append(dict(sql=sql,job_id=j.job_id,bytes_processed=j.total_bytes_processed,rows=len(result)))
        return result
    keys=['gsis_id','season','week'];qs=['q01','q05','q10','q20','q30','q40','q50','q60','q70','q80','q90','q95','q99']
    cache=read(f'SELECT * FROM `{PROJECT}.nfl_features.tabpfn_projections` ORDER BY season,week,gsis_id')
    assert len(cache)==r['output_rows']==r['unique_keys'] and not cache.duplicated(keys).any()
    assert np.isfinite(cache[['mean',*qs]].to_numpy(float)).all()
    assert (np.diff(cache[qs].to_numpy(float),axis=1)>=-1e-8).all()
    expected=read(f"SELECT gsis_id,season,week FROM `{PROJECT}.nfl_features.player_week_inference` WHERE season=2026 AND week=2 AND position IN ('QB','RB','WR','TE')")
    target=cache[cache.season.eq(2026)&cache.week.eq(2)]
    assert set(map(tuple,target[keys].to_numpy()))==set(map(tuple,expected[keys].to_numpy()))
    missing=read(f"""SELECT COUNT(*) AS n FROM (SELECT gsis_id,season,week FROM `{PROJECT}.nfl_release_20260919_input_repair.nfl_features__tabpfn_projections` WHERE season<2026
       EXCEPT DISTINCT SELECT gsis_id,season,week FROM `{PROJECT}.nfl_features.tabpfn_projections` WHERE season<2026)""")
    assert int(missing.n.iloc[0])==0
    expected_training=read(f"SELECT COUNT(*) AS n FROM `{PROJECT}.nfl_features.player_week_training` WHERE (season<2026 OR (season=2026 AND week<2)) AND position IN ('QB','RB','WR','TE')")
    assert r['training_source']['rows']==int(expected_training.n.iloc[0])
    path=P/'refreshed-cache.parquet';assert not path.exists();cache.to_parquet(path,index=False)
    result=dict(execution=execution,receipt=r,rows=len(cache),upcoming_rows=len(target),expected_upcoming_rows=len(expected),
       no_missing_historical_keys=True,unique_keys=True,finite_quantiles=True,ordered_quantiles=True,
       cache_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),queries=queries,
       scope='actual live cache, source receipt and support verification; no efficacy inference or current labels opened')
    with (P/'cache-validation.json').open('x') as f:json.dump(result,f,indent=2)
    print('LIVE_CACHE_VALIDATION_PASS',len(cache),len(target),flush=True)

if __name__=='__main__':main()
