"""Actual projection receipt plus exact props consumer inputs; read-only."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import numpy as np
from google.cloud import bigquery

REPO=Path(__file__).resolve().parents[3]
P=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
PROJECT='nfl-predictions-503414'

def main():
    r=json.loads((P/'project-slate-result.json').read_text())
    e=r['execution_receipt'];start=e['startTime'];end=e['completionTime'];name=e['name'].split('/')[-1]
    filt=f'resource.type="cloud_run_job" AND resource.labels.job_name="project-slate" AND labels."run.googleapis.com/execution_name"="{name}"'
    logs=json.loads(subprocess.check_output(['gcloud','logging','read',filt,'--project='+PROJECT,'--freshness=3h','--limit=1000','--format=json']))
    (P/'project-slate-logs.json').write_text(json.dumps(logs,indent=2))
    client=bigquery.Client(project=PROJECT);queries=[]
    def query(sql):
        assert sql.lstrip().startswith(('SELECT','WITH')) and ';' not in sql
        cfg=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000,query_parameters=[
          bigquery.ScalarQueryParameter('start','TIMESTAMP',start),bigquery.ScalarQueryParameter('end','TIMESTAMP',end)])
        j=client.query(sql,job_config=cfg);df=j.result(timeout=300).to_dataframe()
        queries.append(dict(sql=sql,job_id=j.job_id,rows=len(df),bytes_processed=j.total_bytes_processed));return df
    proj=query(f"SELECT * FROM `{PROJECT}.nfl_predictions.player_projections` WHERE generated_at BETWEEN @start AND @end AND season=2026 AND week=2")
    assert len(proj)>0 and proj.generated_at.nunique()==1
    # DST is intentionally written with null gsis_id (dst_projections.py), and
    # is keyed by DraftKings team ID. Skill rows retain unique non-null GSIS.
    assert proj.dk_player_id.notna().all() and not proj.dk_player_id.duplicated().any()
    ps=proj[proj.position.isin(['QB','RB','WR','TE'])]
    assert ps.gsis_id.notna().all() and not ps.gsis_id.duplicated().any()
    assert proj[proj.position.eq('DST')].gsis_id.isna().all()
    assert len(ps)+int(proj.position.eq('DST').sum())==len(proj)
    vals=['proj_points','proj_p10','proj_p50','proj_p90','proj_std']
    assert np.isfinite(proj[vals].to_numpy(float)).all() and (proj.proj_std>=0).all()
    assert ((proj.proj_p10<=proj.proj_p50)&(proj.proj_p50<=proj.proj_p90)).all()
    old=query(f"SELECT DISTINCT model_version FROM `{PROJECT}.nfl_release_20260919_input_repair.nfl_predictions__player_projections` WHERE season=2026 AND week=2")
    assert set(proj.model_version)<=set(old.model_version),'model registry changed unexpectedly'
    div=query(f"SELECT generated_at,gsis_id,season,week FROM `{PROJECT}.nfl_predictions.div_shadow` WHERE generated_at BETWEEN @start AND @end AND season=2026 AND week=2")
    log_prop=[x.get('textPayload','') for x in logs if 'market blend source: props' in x.get('textPayload','')]
    assert log_prop or len(div)>0,'no direct props-branch witness from the exact new execution window'
    # The exact production reader and market matching functions, no model fitting.
    sys.path.insert(0,str(REPO/'src'))
    from nfl_dfs.config import settings
    assert settings.project==PROJECT and settings.features==PROJECT+'.nfl_features' and settings.predictions==PROJECT+'.nfl_predictions'
    from nfl_dfs.inference.run_projections import upcoming_slate_features,_props_first_market_with_dk_fallback
    from nfl_dfs.models.prop_market import market_points
    feats=upcoming_slate_features(2026,2)
    skill=feats[feats.dk_position.isin(['QB','RB','WR','TE'])].reset_index(drop=True)
    pm=market_points((2026,),minimum_markets=2);pm=pm[pm.week.eq(2)]
    merged=skill[['gsis_id']].merge(pm[['gsis_id','market_points']],on='gsis_id',how='left')
    assert len(merged)==len(skill)
    _,mask=_props_first_market_with_dk_fallback(np.zeros(len(skill)),merged.market_points)
    assert mask.any() and np.isfinite(merged.market_points.to_numpy(float)).sum()>=.3*len(skill)
    assert set(proj[proj.position.isin(['QB','RB','WR','TE'])].gsis_id)==set(skill.gsis_id)
    result=dict(execution=name,start=start,end=end,projection_rows=len(proj),generated_at=str(proj.generated_at.iloc[0]),
      model_versions=sorted(proj.model_version.unique()),position_counts=proj.position.value_counts().to_dict(),
      finite_ordered_projections=True,unique_nonnull_dk_ids=True,unique_nonnull_skill_gsis=True,dst_gsis_null_by_contract=True,
      direct_props_log=log_prop,fresh_div_shadow_rows=len(div),
      exact_skill_frame_rows=len(skill),exact_finite_prop_rows=int(mask.sum()),exact_prop_coverage=float(mask.mean()),
      source_hashes={n:hashlib.sha256((REPO/n).read_bytes()).hexdigest() for n in ['src/nfl_dfs/inference/run_projections.py','src/nfl_dfs/models/prop_market.py']},
      queries=queries,scope='actual new projection batch and direct branch witnesses; read-only consumer replay')
    with (P/'projection-validation.json').open('x') as f:json.dump(result,f,indent=2,default=str)
    print(json.dumps(result,indent=2,default=str),flush=True)

if __name__=='__main__':main()
