"""Run the unchanged frozen reader locally; normalize NumPy scalars for JSON only."""
import hashlib
import importlib.util
import json
from pathlib import Path
import time
import numpy as np
from google.cloud import storage

E=Path(__file__).parent
BASE=Path('/home/erich/projects/review-evidence/overnight-20260918')
OUT=BASE/'injury-type-read-v2-local'
STUDY_SHA='6914d7f3a4b6f0d06defa128cc20380d165b88004fde1f5ea8aa641e96d32274'
LABEL=BASE/'complete-chain-cli/queries/d60f9597695e6877c4aec85b7b3bc52e05ad979762d088978201c7e425e51df7.parquet'
PREFIX='research/injury-type-opportunity-20260919/v2/'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def plain(v):
    if isinstance(v,np.generic):return v.item()
    if isinstance(v,dict):return {plain(k):plain(x) for k,x in v.items()}
    if isinstance(v,(list,tuple)):return [plain(x) for x in v]
    if isinstance(v,np.ndarray):return plain(v.tolist())
    return v

def main():
    assert json.loads(json.dumps(plain({np.int64(2021):{'x':np.float64(.25)}}),allow_nan=False))=={'2021':{'x':.25}}
    study=E/'2026-09-19-injury-type-opportunity.py';assert sha(study)==STUDY_SHA
    spec=importlib.util.spec_from_file_location('frozen_injury_reader',study)
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    assert sha(LABEL)==m.LABEL_SHA
    OUT.mkdir(exist_ok=False);forecast=OUT/'forecast';forecast.mkdir()
    context=json.loads((BASE/'injury-type-context-receipt-v4.json').read_text())
    bucket=storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab')
    blob=bucket.blob(PREFIX+'forecast/publication.json');blob.reload()
    raw=blob.download_as_bytes(if_generation_match=int(blob.generation));p=json.loads(raw)
    assert p['context_sha256']==context['context_sha256'] and p['study_sha256']==STUDY_SHA
    assert p['build_id']=='32334063-4581-4aa1-b428-b771f3332072' and p['mode']=='forecast' and len(p['objects'])==6
    (OUT/'forecast-publication.json').write_bytes(raw)
    seen=set()
    for r in p['objects']:
        key=r['uri'].removeprefix('gs://nfl-2-506823-lab/')
        assert key.startswith(PREFIX+'forecast/') and '/' not in key.removeprefix(PREFIX+'forecast/')
        dest=forecast/Path(key).name;assert dest.name not in seen;seen.add(dest.name)
        bucket.blob(key,generation=int(r['generation'])).download_to_filename(str(dest),if_generation_match=int(r['generation']),checksum='crc32c')
        assert sha(dest)==r['sha256'] and dest.stat().st_size==r['bytes']
    print('ALL_FORECAST_FILES_AUTHENTICATED_BEFORE_EVALUATION_LABELS',flush=True)
    start=time.monotonic();result,rows=m.read(forecast,LABEL)
    result.update(reader_sha256=STUDY_SHA,context_sha256=context['context_sha256'],
      forecast_publication_generation=str(blob.generation),forecast_build_id=p['build_id'],
      execution='local exact frozen reader after cloud JSON-key serialization failure',elapsed_seconds=time.monotonic()-start)
    result=plain(result)
    (OUT/'score-result.json').write_text(json.dumps(result,indent=2,allow_nan=False))
    rows.to_parquet(OUT/'score-rows.parquet',index=False)
    records=[]
    for path in [OUT/'score-result.json',OUT/'score-rows.parquet']:
        b=bucket.blob(PREFIX+'read/'+path.name);b.metadata={'sha256':sha(path),'study_sha256':STUDY_SHA}
        b.upload_from_filename(str(path),if_generation_match=0,checksum='crc32c');b.reload()
        records.append(dict(uri=f'gs://{bucket.name}/{b.name}',generation=str(b.generation),bytes=int(b.size),crc32c=b.crc32c,sha256=sha(path)))
    publication=dict(mode='read',study_sha256=STUDY_SHA,context_sha256=context['context_sha256'],
       adapter_sha256=sha(__file__),forecast_build_id=p['build_id'],objects=records)
    (OUT/'publication.json').write_text(json.dumps(publication,indent=2))
    bucket.blob(PREFIX+'read/publication.json').upload_from_filename(str(OUT/'publication.json'),if_generation_match=0)
    print(json.dumps(result,indent=2),flush=True)

if __name__=='__main__':main()
