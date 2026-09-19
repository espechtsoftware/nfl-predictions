"""Create-once engineering artifacts for independent cache-decomposition review."""
import hashlib,json
from pathlib import Path
from google.cloud import storage
ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
EVIDENCE=Path(__file__).parent
PREFIX='research/week2-input-release-20260919/cache-order-decomposition-v1/'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=ROOT/'cache-order-decomposition';r=json.loads((p/'result-repaired.json').read_text())
    files={n+'-'+suffix:p/(n+'-'+suffix) for n in r['artifacts'] for suffix in ['components.parquet','bank.npy']}
    for n,parts in r['artifacts'].items():
        for suffix,h in parts.items():assert sha(files[n+'-'+suffix])==h
    proof=json.loads((ROOT/'live-cli-host-proof.json').read_text())
    files.update({'result.json':p/'result-repaired.json','producer.py':EVIDENCE/'2026-09-19-cache-order-decomposition.py',
       'reader.py':EVIDENCE/'2026-09-19-cache-order-decomposition-read.py',
       'fresh-training.parquet':ROOT/'live-cli-fresh-cache/training_through_2025.parquet',
       'tabpfn-cache.parquet':ROOT/'refreshed-cache.parquet','frame.parquet':Path(proof['run'])/'frame.parquet'})
    assert sha(files['producer.py'])==r['producer_sha256'] and sha(files['reader.py'])==r['reader_sha256']
    b=storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab');objects={}
    for name,f in files.items():
        h=sha(f);blob=b.blob(PREFIX+name);blob.upload_from_filename(str(f),if_generation_match=0,checksum='crc32c');blob.reload()
        raw=b.blob(blob.name,generation=int(blob.generation)).download_as_bytes()
        assert hashlib.sha256(raw).hexdigest()==h and len(raw)==f.stat().st_size
        objects[name]=dict(uri='gs://'+b.name+'/'+blob.name,generation=str(blob.generation),sha256=h,bytes=len(raw))
        print('VERIFIED',name,len(raw),flush=True)
    result=dict(objects=objects,scope='Engineering only; no outcome or efficacy claim',
      host_training=dict(uri='gs://nfl-2-506823-lab/research/week2-input-release-20260919/host-training-cache/training_through_2025.parquet',
      generation='1789798352721560',sha256='8aaa5daf5a3ebd12bdb471466dabefdc55f774988ff9437710a4e54467b072b7',bytes=13918400))
    raw=json.dumps(result,indent=2).encode();blob=b.blob(PREFIX+'manifest.json')
    blob.upload_from_string(raw,content_type='application/json',if_generation_match=0);blob.reload()
    assert b.blob(blob.name,generation=int(blob.generation)).download_as_bytes()==raw
    result['manifest']=dict(uri='gs://'+b.name+'/'+blob.name,generation=str(blob.generation),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    with (ROOT/'cache-order-publication.json').open('x') as f:json.dump(result,f,indent=2)
    print('PUBLICATION_COMPLETE',json.dumps(result['manifest']),flush=True)
if __name__=='__main__':main()
