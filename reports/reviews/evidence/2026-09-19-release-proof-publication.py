"""Publish non-entry-key engineering proof artifacts once, then verify bytes."""
import hashlib
import json
from pathlib import Path
from google.cloud import storage

ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918/authorized-release-v2')
PREFIX='research/week2-input-release-20260919/live-cli-host-proof-v1/'
BUCKET='nfl-2-506823-lab'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    proof=json.loads((ROOT/'live-cli-host-proof.json').read_text());run=Path(proof['run'])
    assert sha(run/'receipt.json')==proof['receipt_sha256']
    assert proof['historical_cache_mode']=='host' and proof['receipt']['written']==97
    files={name:run/name for name in ['receipt.json','frame.parquet','candidates.parquet','book.csv','book.json',
       'incumbent_player_scores.npy','corrected_hsim_player_scores.npy','exposure_ledger.json','universe_ledger.parquet']}
    files['proof.json']=ROOT/'live-cli-host-proof.json'
    files['adapter.py']=Path(__file__).with_name('2026-09-19-release-live-cli-proof.py')
    for name in ['feature-accepted.json','cache-validation.json','projection-validation.json']:
        files[name]=ROOT/name
    assert sha(files['adapter.py'])==proof['adapter_sha256']
    # Roster-only DK file; no entry IDs, contests or operator entries export.
    import csv
    with files['book.csv'].open() as f:
        rows=list(csv.reader(f))
    assert rows[0]==['QB','RB','RB','WR','WR','WR','TE','FLEX','DST'] and len(rows)==98
    c=storage.Client(project='nfl-2-506823');b=c.bucket(BUCKET);objects={}
    for name,p in files.items():
        h=sha(p);n=p.stat().st_size;blob=b.blob(PREFIX+name)
        blob.upload_from_filename(str(p),if_generation_match=0,checksum='crc32c');blob.reload()
        remote=b.blob(blob.name,generation=int(blob.generation)).download_as_bytes()
        assert len(remote)==n and hashlib.sha256(remote).hexdigest()==h
        objects[name]=dict(uri='gs://'+BUCKET+'/'+blob.name,generation=str(blob.generation),sha256=h,bytes=n)
        print('VERIFIED',name,n,flush=True)
    result=dict(scope='D160 research engineering proof, not entered or uploaded to DraftKings',
      source_sha=proof['source_sha'],objects=objects,publisher_sha256=sha(Path(__file__)))
    raw=json.dumps(result,indent=2).encode();blob=b.blob(PREFIX+'manifest.json')
    blob.upload_from_string(raw,content_type='application/json',if_generation_match=0,checksum='crc32c');blob.reload()
    manifest=dict(uri='gs://'+BUCKET+'/'+blob.name,generation=str(blob.generation),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    assert b.blob(blob.name,generation=int(blob.generation)).download_as_bytes()==raw
    with (ROOT/'proof-publication.json').open('x') as f:json.dump(dict(manifest=manifest,**result),f,indent=2)
    print('PROOF_PUBLICATION_VERIFIED',json.dumps(manifest),flush=True)

if __name__=='__main__':main()
