"""Read-only input capture and unchanged installed-helper replay on saved research books.

This is a fresh-timestamp delivery trace, not an archived Week-2 delivery or efficacy test.
No outcomes, score banks, live files, uploads, or policies are touched.
"""
import contextlib
import csv
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import runpy
import shutil
import sys
import pandas as pd
from google.cloud import bigquery

ROOT=Path(__file__).resolve().parents[3]
HELPER=ROOT/'scripts/week1_vet_book.py'
HELPER_SHA='aa7d35f808d2a5db4faea6471b95c0c89b765ad1bc3c1e0c310ff5a428d6e89e'
LOCAL=Path('/home/erich/projects/review-evidence/overnight-20260918/complete-chain-d1600')
COLS=['id','dk_player_id','dk_draftable_id','draft_group_id','display_name','position','team','salary','gsis_id','status']
TABLES=['nfl-predictions-503414.nfl_raw.injuries','nfl-predictions-503414.nfl_features.player_week_inference',
        'nfl-predictions-503414.nfl_raw.prop_lines']
SPANS=[(0,1),(1,24),(24,25),(25,30),(30,31),(31,33),(33,43),(43,53),(53,63),(63,79),(79,95),(95,97)]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def book(p):
    with Path(p).open(newline='') as f:return list(csv.reader(f))
def main():
    output=Path(sys.argv[1]);output.mkdir(exist_ok=False,parents=True)
    assert sha(HELPER)==HELPER_SHA
    cutoff=datetime.now(timezone.utc)
    real=bigquery.Client(project='nfl-predictions-503414')
    cache={};captures=[];calls=[]
    class FrozenResult:
        def __init__(self,frame):self.frame=frame
        def result(self):return self
        def to_dataframe(self):return self.frame.copy(deep=True)
    class CapturedClient:
        def __init__(self,project):assert project=='nfl-predictions-503414'
        def query(self,sql,job_config):
            assert sql.strip().startswith('SELECT')
            matches=[t for t in TABLES if '`'+t+'`' in sql];assert len(matches)==1
            table=matches[0];assert sql.count('`'+table+'`')==1
            assert all(x not in sql.lower() for x in ['y_targets','y_dk_points','was_active'])
            params=list(job_config.query_parameters)
            assert next(p.value for p in params if p.name=='s')==2026
            assert next(p.value for p in params if p.name=='w')==2
            contract={'sql':sql,'parameters':[p.to_api_repr() for p in params]}
            key=hashlib.sha256(json.dumps(contract,sort_keys=True).encode()).hexdigest()
            calls.append({'table':table,'key':key})
            if key not in cache:
                sql2=sql.replace('`'+table+'`','`'+table+'` FOR SYSTEM_TIME AS OF @capture_at')
                params.append(bigquery.ScalarQueryParameter('capture_at','TIMESTAMP',cutoff))
                dry=real.query(sql2,job_config=bigquery.QueryJobConfig(dry_run=True,use_query_cache=False,query_parameters=params))
                assert dry.total_bytes_processed<=1_000_000_000
                job=real.query(sql2,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1_000_000_000,query_parameters=params))
                frame=job.result().to_dataframe();p=output/(key+'.parquet');frame.to_parquet(p,index=False)
                captures.append({**contract,'captured_sql':sql2,'cutoff':cutoff.isoformat(),'job_id':job.job_id,
                    'bytes_processed':job.total_bytes_processed,'path':str(p),'sha256':sha(p),'rows':len(frame)})
                (output/'query-captures.json').write_text(json.dumps(captures,indent=2))
                cache[key]=frame
            return FrozenResult(cache[key])
    sys.path.insert(0,str(ROOT/'src'))
    original_client=bigquery.Client;original_args=sys.argv.copy();summaries={}
    try:
        bigquery.Client=CapturedClient
        helper=runpy.run_path(str(HELPER))
        for arm in ['control','salaryfix']:
            rec=json.loads((LOCAL/arm/'receipt.json').read_text());run=Path(rec['original_run'])
            assert sha(run/'receipt.json')==rec['original_receipt_sha256']
            before=book(run/'book.csv');assert len(before)==98
            source=output/arm/'source';source.mkdir(parents=True)
            # Only the helper's identity/status fields plus emitter identifiers enter this rehearsal.
            fr=pd.read_parquet(run/'frame.parquet',columns=COLS)
            assert fr.dk_player_id.astype(str).is_unique and len(fr)==fr.id.nunique()
            assert not any(c=='actual' or c.startswith('y_') for c in fr)
            fr.to_parquet(source/'frame.parquet',index=False)
            shutil.copyfile(run/'book.csv',source/'book.csv');shutil.copyfile(run/'receipt.json',source/'receipt.json')
            dest=output/arm/'vetted'
            sys.argv=[str(HELPER),str(source),'--k','30','--season','2026','--week','2','--output-dir',str(dest)]
            count=len(calls)
            with (output/arm/'helper.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):helper['main']()
            assert len(calls)-count==3
            v=json.loads((dest/'vetting.json').read_text());order=v['order_source_ranks']
            assert sorted(order)==list(range(1,98))
            after=book(dest/'book.csv');assert after[0]==before[0] and after[1:]==[before[r] for r in order]
            names=dict(zip(fr.dk_player_id.astype(str),fr.display_name.astype(str)))
            summaries[arm]={'original_run':str(run),'source_receipt_sha256':rec['original_receipt_sha256'],
                'original_book_sha256':sha(run/'book.csv'),'safe_frame_sha256':sha(source/'frame.parquet'),
                'vetted_book_sha256':sha(dest/'book.csv'),'vetting_sha256':sha(dest/'vetting.json'),
                'order_source_ranks':order,'first_original_rank':order[0],
                'original_first':v['lineups'][0],'delivered_first':v['lineups'][order[0]-1],
                'first_player_names':[names[d] for d in after[1]],
                'hard_lineups':sum(x['hard'] for x in v['lineups']),
                'material_lineups':sum(x['material'] for x in v['lineups']),
                'top30_demoted':v['demoted_out_of_top_k'],'top30_promoted':v['promoted_into_top_k'],
                'prop_fetch_days':v['prop_fetch_days'],'signals':v['signals'],
                'contest_source_ranks':[order[a:b] for a,b in SPANS]}
    finally:bigquery.Client=original_client;sys.argv=original_args
    report={'scope':'Fresh-timestamp read-only vetting identity trace on saved D1600 research books; not actual entry files',
        'capture_at':cutoff.isoformat(),'helper_sha256':HELPER_SHA,'source_sha256':sha(__file__),
        'safe_frame_columns':COLS,'all_queries_read_only':True,'football_outcomes_read':False,
        'queries':captures,'arms':summaries,
        'limits':'Both arms use the same fresh live vetting tables, not a refreshed repaired warehouse. Future Sunday inputs can change order.'}
    (output/'result.json').write_text(json.dumps(report,indent=2,allow_nan=False))
    print(json.dumps({a:{k:r[k] for k in ['first_original_rank','hard_lineups','material_lineups','top30_demoted','top30_promoted']} for a,r in summaries.items()},indent=2))

if __name__=='__main__':main()
