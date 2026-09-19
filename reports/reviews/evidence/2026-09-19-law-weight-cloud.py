"""Cloud Build compute entry: authenticated inputs, forecast-only construction, create-once export."""
import base64
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import google_crc32c
from google.cloud import storage

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    mode=sys.argv[1]
    assert mode in ('smoke','forecast')
    root=Path('/workspace')
    bound=json.loads((root/'context.json').read_text())
    # Context is staged from committed source; verify every payload before imports or simulations.
    for name,digest in bound['files'].items(): assert sha(root/name)==digest,name
    assert bound['lab_commit']=='2dc116ce95647a776ba9c36cf194f44d022d03a4'
    out=root/'output'
    cmd=[sys.executable,'-X','cpu_count=1',str(root/'forecast.py'),'--out',str(out),
         '--lab-root',str(root/'lab'),'--source-contract',str(root/'source-contract.json'),
         '--support',str(root/'support-cloud.json')]
    if mode=='smoke': cmd.append('--smoke')
    subprocess.run(cmd,check=True)
    receipt=json.loads((out/'receipt.json').read_text())
    assert receipt['current_season_outcomes_accessible'] is False
    assert receipt['smoke']==(mode=='smoke')
    client=storage.Client(project='nfl-2-506823')
    prefix=f'research/law-weight-20260919/forecast-v1/{mode}/'
    bucket=client.bucket('nfl-2-506823-lab')
    transfers=[]
    paths=sorted(p for p in out.iterdir() if p.name!='receipt.json')+[out/'receipt.json']
    for p in paths:
        assert p.suffix in ('.npy','.parquet','.json')
        blob=bucket.blob(prefix+p.name)
        blob.metadata={'sha256':sha(p),'research_commit':bound['research_commit']}
        blob.upload_from_filename(str(p),if_generation_match=0,checksum='crc32c')
        blob.reload()
        crc=base64.b64encode(google_crc32c.value(p.read_bytes()).to_bytes(4,'big')).decode()
        assert int(blob.size)==p.stat().st_size and blob.crc32c==crc
        transfers.append({'uri':f'gs://{bucket.name}/{blob.name}','generation':str(blob.generation),
                          'bytes':int(blob.size),'crc32c':blob.crc32c,'sha256':sha(p)})
    publication={'mode':mode,'research_commit':bound['research_commit'],'context_sha256':sha(root/'context.json'),
                 'build_id':os.environ.get('BUILD_ID'),'objects':transfers,
                 'elapsed_forecast_seconds':receipt['elapsed_seconds'],'runtime':receipt['runtime']}
    text=json.dumps(publication,indent=2,allow_nan=False)
    bucket.blob(prefix+'publication.json').upload_from_string(text,content_type='application/json',if_generation_match=0)
    print('FORECAST_PUBLICATION',json.dumps({'uri':f'gs://{bucket.name}/{prefix}publication.json',
            'objects':len(transfers),'elapsed_seconds':receipt['elapsed_seconds'],'runtime':receipt['runtime']}),flush=True)

if __name__=='__main__': main()
