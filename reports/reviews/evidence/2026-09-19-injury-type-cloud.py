"""Authenticated Cloud Build adapter; distinct smoke, forecast and outcome-read phases."""
import hashlib
import importlib.util
import importlib.metadata
import json
import os
from pathlib import Path
import sys
import time
import numpy as np
import pandas as pd
from google.cloud import storage

PREFIX='research/injury-type-opportunity-20260919/v1/'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    mode=sys.argv[1];assert mode in ['smoke','forecast','read']
    root=Path('/workspace');context=json.loads((root/'context.json').read_text())
    for name,digest in context['files'].items():assert sha(root/name)==digest,name
    wheels=json.loads((root/'wheels.json').read_text())
    for name,version in wheels['pins'].items():assert importlib.metadata.version(name)==version
    spec=importlib.util.spec_from_file_location('frozen_injury_type',root/'study.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    bucket=storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab')
    out=root/'output';start=time.monotonic()
    if mode=='smoke':
        module.synthetic()
        safe=pd.read_parquet(root/'safe.parquet')
        support=json.loads((root/'support.json').read_text())
        assert sha(root/'safe.parquet')==module.SAFE_SHA
        assert len(safe)==90082 and safe.season.max()==2024
        for extra in [False,True]:
            x=module.design(safe,support['baseline_numeric_features'],extra)
            assert len(x)==len(safe) and not np.isinf(x).any()
        assert int(module.eligible(safe).sum())==33802
        out.mkdir(exist_ok=False)
        (out/'smoke.json').write_text(json.dumps({'synthetic':'PASS','safe_rows':len(safe),
             'eligible_rows':int(module.eligible(safe).sum()),'historical_labels_opened':False,
             'elapsed_seconds':time.monotonic()-start},indent=2))
    elif mode=='forecast':
        module.construct(root/'safe.parquet',root/'labels.parquet',root/'support.json',out)
    else:
        b=bucket.blob(PREFIX+'forecast/publication.json');b.reload()
        publication=json.loads(b.download_as_bytes(if_generation_match=int(b.generation)))
        assert publication['context_sha256']==sha(root/'context.json')
        assert publication['study_sha256']==sha(root/'study.py')
        assert publication['build_id']==os.environ['FORECAST_BUILD_ID']
        assert publication['mode']=='forecast' and len(publication['objects'])==6
        forecast=root/'forecast';forecast.mkdir(exist_ok=False)
        seen=set()
        for rec in publication['objects']:
            name=rec['uri'].split('gs://nfl-2-506823-lab/',1)[1]
            assert name.startswith(PREFIX+'forecast/') and '/' not in name.removeprefix(PREFIX+'forecast/')
            p=forecast/Path(name).name;assert p.name not in seen;seen.add(p.name)
            bucket.blob(name,generation=int(rec['generation'])).download_to_filename(str(p),
                 if_generation_match=int(rec['generation']),checksum='crc32c')
            assert p.stat().st_size==rec['bytes'] and sha(p)==rec['sha256']
        print('ALL_FORECAST_FILES_AUTHENTICATED_BEFORE_EVALUATION_LABELS',flush=True)
        result,rows=module.read(forecast,root/'labels.parquet')
        result.update({'reader_sha256':sha(root/'study.py'),'context_sha256':sha(root/'context.json'),
             'forecast_publication_generation':str(b.generation),'build_id':os.environ.get('BUILD_ID'),
             'elapsed_seconds':time.monotonic()-start})
        out.mkdir(exist_ok=False)
        (out/'score-result.json').write_text(json.dumps(result,indent=2,allow_nan=False))
        rows.to_parquet(out/'score-rows.parquet',index=False)
    objects=[]
    for p in sorted(out.iterdir()):
        blob=bucket.blob(PREFIX+mode+'/'+p.name)
        blob.metadata={'sha256':sha(p),'study_sha256':sha(root/'study.py')}
        blob.upload_from_filename(str(p),if_generation_match=0,checksum='crc32c');blob.reload()
        objects.append({'uri':f'gs://{bucket.name}/{blob.name}','generation':str(blob.generation),
                        'bytes':int(blob.size),'crc32c':blob.crc32c,'sha256':sha(p)})
    record={'mode':mode,'study_sha256':sha(root/'study.py'),'context_sha256':sha(root/'context.json'),
            'research_commit':context['research_commit'],'build_id':os.environ.get('BUILD_ID'),'objects':objects}
    bucket.blob(PREFIX+mode+'/publication.json').upload_from_string(json.dumps(record,indent=2),
        content_type='application/json',if_generation_match=0)
    print('PUBLISHED',mode,json.dumps(record),flush=True)
    if mode=='read':
        print('RESULT',json.dumps({k:result[k] for k in ['primary_delta','primary_95_interval',
                 'by_season','all_active_delta','nominate_for_separate_followup']}),flush=True)

if __name__=='__main__':main()
