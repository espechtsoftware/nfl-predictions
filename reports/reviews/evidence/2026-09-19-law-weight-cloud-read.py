"""Cloud scoring adapter for the frozen reader; validate the complete forecast cohort first."""
import concurrent.futures
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import time
import pandas as pd
from google.cloud import storage

PREFIX='research/law-weight-20260919/forecast-v1/forecast/'
READER_SHA='2f9f41b1c5bc30e4930f1cdd5981a3df5d30384928e44fb81fd9f6a5d6eb0cd5'
def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    start=time.monotonic();root=Path('/workspace')
    bound=json.loads((root/'context.json').read_text())
    for name,digest in bound['files'].items(): assert sha(root/name)==digest
    reader=root/'reader.py';assert sha(reader)==READER_SHA
    support=json.loads((root/'support-cloud.json').read_text())
    client=storage.Client(project='nfl-2-506823');bucket=client.bucket('nfl-2-506823-lab')
    pubblob=bucket.blob(PREFIX+'publication.json');pubblob.reload()
    pub=json.loads(pubblob.download_as_bytes(if_generation_match=int(pubblob.generation)))
    assert pub['mode']=='forecast' and pub['research_commit']=='645ff1ef124890db439af5c655905d02a130f6b7'
    assert pub['context_sha256']=='8f920a5310e9afaa4453dd9e752408b44f714012b1c9838f50c1b7b5c2937a89'
    assert pub['build_id']=='2eb37a28-4779-4ec2-97a7-4d3c918f5390'
    objects=pub['objects'];assert len(objects)==446
    names=[Path(x['uri']).name for x in objects];assert len(names)==len(set(names))
    dest=root/'forecast';dest.mkdir(exist_ok=False)
    def download(rec):
        name=rec['uri'].split('gs://nfl-2-506823-lab/',1)[1]
        assert name.startswith(PREFIX) and '/' not in name[len(PREFIX):]
        blob=bucket.blob(name,generation=int(rec['generation']))
        p=dest/Path(name).name
        blob.download_to_filename(str(p),if_generation_match=int(rec['generation']),checksum='crc32c')
        assert p.stat().st_size==rec['bytes'] and sha(p)==rec['sha256']
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(download,objects))
    receipt=json.loads((dest/'receipt.json').read_text())
    assert not receipt['smoke'] and receipt['current_season_outcomes_accessible'] is False
    assert len(receipt['records'])==178
    assert receipt['support_sha256']==sha(root/'support-cloud.json')
    print('ALL_FORECAST_IDENTITIES_VERIFIED_BEFORE_ACTUAL_READ',flush=True)
    spec=importlib.util.spec_from_file_location('frozen_law_weight_reader',reader)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    # This is the only outcome read, after authenticating the complete frozen forecast cohort.
    rec=next(r for r in support['files'] if '/snap_pitclean_k1/' in r['uri'])
    assert sha(rec['path'])==rec['sha256']
    actuals=pd.read_parquet(rec['path'],columns=['season','week','id','actual'])
    report,rows=module.evaluate(dest,support,actuals)
    report.update({'reader_sha256':READER_SHA,'forecast_receipt_sha256':sha(dest/'receipt.json'),
       'forecast_publication_generation':str(pubblob.generation),'build_id':os.environ.get('BUILD_ID'),
       'elapsed_seconds':time.monotonic()-start,'complete_forecast_identity_before_actuals':True})
    out=root/'score-result.json';out.write_text(json.dumps(report,indent=2,allow_nan=False))
    rowfile=root/'score-rows.parquet';rows.to_parquet(rowfile,index=False)
    published=[]
    for p in (out,rowfile):
        b=bucket.blob('research/law-weight-20260919/read-v1/'+p.name)
        b.metadata={'sha256':sha(p),'reader_sha256':READER_SHA}
        b.upload_from_filename(str(p),if_generation_match=0,checksum='crc32c');b.reload()
        published.append({'uri':f'gs://{bucket.name}/{b.name}','generation':str(b.generation),
                          'bytes':int(b.size),'crc32c':b.crc32c,'sha256':sha(p)})
    result={'objects':published,'reader_sha256':READER_SHA,'build_id':os.environ.get('BUILD_ID')}
    bucket.blob('research/law-weight-20260919/read-v1/publication.json').upload_from_string(
        json.dumps(result,indent=2),content_type='application/json',if_generation_match=0)
    print('READ_PUBLISHED',json.dumps({k:report[k] for k in ['primary_delta','primary_95_interval',
        'by_season','by_bank','advance_to_separate_lineup_study']}),flush=True)

if __name__=='__main__': main()
