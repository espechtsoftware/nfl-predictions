"""Read object identities and structural headers only; never decode NFL outcome rows."""
import ast
import hashlib
import io
import json
from pathlib import Path
import struct

from google.cloud import storage
import pyarrow.parquet as pq

prefix = 'week1/prelock/2026-w01/a5-books/20260910t2315z-fa5d035/sources/D800_DEMAX/'
client = storage.Client(project='nfl-predictions-503414')
bucket = client.bucket('nfl-predictions-503414-raw')
records = []
for name in ('candidates.parquet', 'frame.parquet', 'incumbent_player_scores.npy', 'corrected_hsim_player_scores.npy'):
    blob = bucket.blob(prefix+name)
    blob.reload()
    record = dict(name=name, generation=blob.generation, size=blob.size, crc32c=blob.crc32c,
                  md5=blob.md5_hash, updated=blob.updated.isoformat())
    if name.endswith('.parquet'):
        data = blob.download_as_bytes(if_generation_match=int(blob.generation))
        meta = pq.ParquetFile(io.BytesIO(data))
        record.update(sha256=hashlib.sha256(data).hexdigest(), rows=meta.metadata.num_rows,
                      row_groups=meta.metadata.num_row_groups,
                      schema=[dict(name=f.name, type=str(f.type)) for f in meta.schema_arrow])
    else:
        data = blob.download_as_bytes(start=0, end=511, if_generation_match=int(blob.generation))
        assert data[:6] == b'\x93NUMPY'
        version = tuple(data[6:8])
        offset = 10 if version[0] == 1 else 12
        length = struct.unpack('<H' if offset == 10 else '<I', data[8:offset])[0]
        assert offset+length <= len(data), 'header exceeds read bound'
        header = ast.literal_eval(data[offset:offset+length].decode('latin1').strip())
        record.update(npy_version=version, header=header)
    records.append(record)
out = Path('reports/reviews/evidence/2026-09-18-e0-archive-schema.json')
with out.open('x') as f:
    json.dump(dict(prefix='gs://'+bucket.name+'/'+prefix,
                   method='Parquet structural metadata only; NPY header only. No row values or book/receipt payloads inspected.',
                   objects=records), f, indent=2)
for r in records:
    print(r['name'], 'rows',r.get('rows'), 'header',r.get('header'), 'columns', [f['name'] for f in r.get('schema',[])])
