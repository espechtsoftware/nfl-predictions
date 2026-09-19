"""Publish exact small quote-integrity inputs/outputs for independent review."""
import hashlib,json
from pathlib import Path
from google.cloud import bigquery,storage
ROOT=Path('/home/erich/projects/review-evidence/overnight-20260918')
E=Path(__file__).parent
PREFIX='research/week2-input-release-20260919/prop-snapshot-impact-v1/'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    p=ROOT/'prop-snapshot-impact-v2';r=json.loads((p/'result.json').read_text())
    files={n:p/n for n in r['artifacts']}
    assert all(sha(files[n])==h for n,h in r['artifacts'].items())
    for n in ['props.parquet','schedules.parquet','census.json']:files[n]=ROOT/'prop-snapshot-census'/n
    files.update({'result.json':p/'result.json','analysis.py':E/'2026-09-19-prop-snapshot-impact-v2.py',
                  'consumer.py':E.parents[2]/'src/nfl_dfs/models/prop_market.py'})
    assert sha(files['analysis.py'])==r['script_sha256'] and sha(files['consumer.py'])==r['production_source_sha256']
    proof=json.loads((ROOT/'authorized-release-v2/live-cli-host-proof.json').read_text())
    files['proof-frame.parquet']=Path(proof['run'])/'frame.parquet'
    stamp=proof['receipt']['config']['production_generated_at'];c=bigquery.Client(project='nfl-predictions-503414')
    sql='SELECT gsis_id,position FROM `nfl-predictions-503414.nfl_predictions.player_projections` WHERE season=2026 AND week=2 AND generated_at=@stamp'
    j=c.query(sql,job_config=bigquery.QueryJobConfig(maximum_bytes_billed=1000000000,query_parameters=[bigquery.ScalarQueryParameter('stamp','TIMESTAMP',stamp)]))
    d=j.result(timeout=300).to_dataframe();assert len(d)==504 and d[d.position.ne('DST')].gsis_id.nunique()==472
    dest=p/'projection-identities.parquet';assert not dest.exists();d.to_parquet(dest,index=False);files[dest.name]=dest
    b=storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab');objects={}
    for name,f in files.items():
        h=sha(f);blob=b.blob(PREFIX+name);blob.upload_from_filename(str(f),if_generation_match=0,checksum='crc32c');blob.reload()
        raw=b.blob(blob.name,generation=int(blob.generation)).download_as_bytes();assert hashlib.sha256(raw).hexdigest()==h
        objects[name]=dict(uri='gs://'+b.name+'/'+blob.name,generation=str(blob.generation),sha256=h,bytes=len(raw))
        print('VERIFIED',name,flush=True)
    result=dict(objects=objects,projection_identity_query=dict(sql=sql,job_id=j.job_id,stamp=stamp),scope='Read-only quote-integrity engineering comparison; no live change or efficacy claim')
    raw=json.dumps(result,indent=2).encode();blob=b.blob(PREFIX+'manifest.json');blob.upload_from_string(raw,if_generation_match=0,content_type='application/json');blob.reload()
    assert b.blob(blob.name,generation=int(blob.generation)).download_as_bytes()==raw
    result['manifest']=dict(uri='gs://'+b.name+'/'+blob.name,generation=str(blob.generation),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
    with (ROOT/'prop-snapshot-publication.json').open('x') as f:json.dump(result,f,indent=2)
    print('PUBLICATION_COMPLETE',json.dumps(result['manifest']),flush=True)
if __name__=='__main__':main()
