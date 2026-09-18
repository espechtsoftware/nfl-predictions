"""Verify transferred Week2 archive bytes and schemas; no score/actual/rank values decoded."""
import hashlib
import io
import json
from pathlib import Path
import ast
import struct
from google.cloud import storage
import pyarrow.parquet as pq

PREFIX='research/week2-diagnostic-population/20260917T150719330879Z-e7255e9/'
EXPECTED={
'candidates.parquet':'dd547b99189d3adb8fb2b5f7aa680dd0419944be3c5957688c66ad894df7fb3e',
'frame.parquet':'90a762654111126aefad1950217044443291251918ab70edb925ff341d226635',
'incumbent_player_scores.npy':'4774e37cf0416b28c93c0467e33382589562832aceb23594809f76bd5f0e2568',
'corrected_hsim_player_scores.npy':'1d5b6372c9ba4a1d86ddac7c29652f432377486966a5be4bc08f338eb01e7a06',
'receipt.json':'4f00d70b4ae5a907431485f4327ebc30afecefb4ff7f33b4053e93c6491df3d5'}
bucket=storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab')
records=[]
for name,sha in EXPECTED.items():
    blob=bucket.blob(PREFIX+name);blob.reload()
    raw=blob.download_as_bytes(if_generation_match=int(blob.generation))
    observed=hashlib.sha256(raw).hexdigest()
    assert observed==sha,(name,observed)
    row=dict(name=name,sha256=observed,generation=blob.generation,bytes=len(raw),updated=blob.updated.isoformat())
    if name.endswith('.parquet'):
        p=pq.ParquetFile(io.BytesIO(raw))
        row.update(rows=p.metadata.num_rows,schema=[dict(name=f.name,type=str(f.type)) for f in p.schema_arrow])
    elif name.endswith('.npy'):
        assert raw[:6]==b'\x93NUMPY'
        offset=10 if raw[6]==1 else 12
        length=struct.unpack('<H' if offset==10 else '<I',raw[8:offset])[0]
        row['header']=ast.literal_eval(raw[offset:offset+length].decode('latin1'))
    else:
        receipt=json.loads(raw)
        row['identity']=receipt['identity']
        row['config']={k:receipt['config'].get(k) for k in ('lev','boom','sims','operational_k','selector','seed','hsim_seed','centering')}
        row['built_utc']=receipt['built_utc'];row['lock_utc']=receipt['lock_utc']
    records.append(row)
    print(name,'hash verified','rows',row.get('rows'),'shape',row.get('header',{}).get('shape'))
out=Path('reports/reviews/evidence/2026-09-18-week2-archive-preflight.json')
with out.open('x') as f:
    json.dump(dict(prefix='gs://'+bucket.name+'/'+PREFIX,objects=records,
                   scope='Full-byte hashes verified; parquet schemas and npy headers only, plus allowlisted receipt metadata. No outcomes, prediction values or ranks decoded.'),f,indent=2)
