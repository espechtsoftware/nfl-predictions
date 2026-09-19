"""Reconstruct one archived hsim bank using exact source and authenticated inputs."""
import base64
import hashlib
import io
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

import google_crc32c
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from google.cloud import storage

R = Path('reports/reviews/evidence')
OUT = R / '2026-09-19-hsim-replay-preflight.json'
LOCAL = Path('/home/erich/projects/review-evidence/overnight-20260918/hsim-replay')
LAB = Path('/home/erich/projects/.nfl2-worktrees/audit-capture-review')
SHA = 'e7255e98bf87297452befb61fb508ad4b368b59f'
assert not OUT.exists() and not (LOCAL / 'replayed.npy').exists()
LOCAL.mkdir(parents=True, exist_ok=True)
source_hashes = {}
for path in sorted((LAB/'src/nfl2/hsim').glob('*.py')) + [LAB/'src/nfl2/data.py']:
    name = path.relative_to(LAB).as_posix()
    raw = subprocess.check_output(['git','-C',str(LAB),'show',SHA+':'+name])
    assert path.read_bytes() == raw, name
    source_hashes[name] = hashlib.sha256(raw).hexdigest()
manifest_bytes = (LAB/'benchmark/MANIFEST-v1.json').read_bytes()
assert manifest_bytes == subprocess.check_output(['git','-C',str(LAB),'show',SHA+':benchmark/MANIFEST-v1.json'])
manifest = json.loads(manifest_bytes)
names = ('player_week_training','raw_weekly_stats','raw_schedules')
files = {}
benchmark = []
for rec in manifest['objects']:
    if not any('/warehouse/'+name+'/' in rec['uri'] for name in names):
        continue
    rel = rec['uri'].split('/benchmark/v0/',1)[1]
    path = Path('/home/erich/.cache/nfl2/v0')/rel
    raw = path.read_bytes()
    assert len(raw) == int(rec['bytes'])
    assert base64.b64encode(google_crc32c.Checksum(raw).digest()).decode() == rec['crc32c']
    benchmark.append(dict(**rec,sha256=hashlib.sha256(raw).hexdigest()))
    files[rel] = path
assert len(files) == 6
sys.path.insert(0,str(LAB/'src'))
import nfl2.data as data

def allowed_list(prefix):
    assert prefix in {'warehouse/'+name+'/' for name in names}, prefix
    return sorted(key for key in files if key.startswith(prefix))

def allowed_fetch(path):
    assert path in files, path
    return files[path]

data._list = allowed_list
data._fetch = allowed_fetch
from nfl2.hsim.world import simulate_hsim
archive = json.loads((R/'2026-09-18-week2-archive-preflight.json').read_text())
bucket = storage.Client(project='nfl-2-506823').bucket('nfl-2-506823-lab')
prefix = archive['prefix'].split(bucket.name+'/',1)[1]
verified = {}

def get(name):
    rec = next(x for x in archive['objects'] if x['name'] == name)
    path = LOCAL/name
    if path.exists():
        raw = path.read_bytes()
    else:
        raw = bucket.blob(prefix+name).download_as_bytes(if_generation_match=int(rec['generation']))
        assert hashlib.sha256(raw).hexdigest() == rec['sha256']
        with path.open('xb') as f: f.write(raw)
    assert hashlib.sha256(raw).hexdigest() == rec['sha256']
    verified[name] = dict(sha256=rec['sha256'],generation=rec['generation'])
    return raw

columns = ['id','display_name','pos','team','proj','mean_projection','depth_rank','snap_share_l4',
           'is_cold_start','games_played_prior','target_share_l4','carry_share_l4',
           'rz20_target_share_l4','gl3_carry_share_l4','neutral_pass_rate_l6',
           'yards_per_target_l8','yards_per_carry_l8']
raw_frame = get('frame.parquet')
assert set(columns) <= set(pq.read_schema(io.BytesIO(raw_frame)).names)
fr = pq.read_table(io.BytesIO(raw_frame),columns=columns).to_pandas()
archived = np.load(io.BytesIO(get('corrected_hsim_player_scores.npy')),allow_pickle=False)
assert len(fr)==fr.id.nunique()==435 and archived.shape==(435,10000) and archived.dtype==np.float32
start = time.monotonic()
with data.outcome_firewall(2026):
    replay = simulate_hsim(fr,2026,2,10000,seed=2326).astype(np.float32)
assert replay.shape==archived.shape and np.isfinite(replay).all()
with (LOCAL/'replayed.npy').open('xb') as f: np.save(f,replay,allow_pickle=False)
diff = replay.astype(np.float64)-archived.astype(np.float64)
result = dict(exact_equal=bool(np.array_equal(replay,archived)),differing_elements=int(np.count_nonzero(diff)),
              max_absolute_difference=float(np.abs(diff).max()),mean_absolute_difference=float(np.abs(diff).mean()),
              max_player_mean_difference=float(np.abs(diff.mean(axis=1)).max()),
              replay_sha256=hashlib.sha256((LOCAL/'replayed.npy').read_bytes()).hexdigest(),
              elapsed_seconds=time.monotonic()-start,shape=list(replay.shape),source_hashes=source_hashes,
              benchmark_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),benchmark=benchmark,
              verified_inputs=verified,frame_columns=columns,
              provenance=dict(python=platform.python_version(),numpy=np.__version__,pandas=pd.__version__,
                  source_sha=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
                  source_status=subprocess.check_output(['git','status','--porcelain'],text=True),
                  script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()),
              scope='Mechanical archived-bank replay; no repaired inputs, efficacy verdict or live changes.')
with OUT.open('x') as f: json.dump(result,f,indent=2,allow_nan=False)
print(json.dumps({k:result[k] for k in ('exact_equal','differing_elements','max_absolute_difference',
    'mean_absolute_difference','max_player_mean_difference','elapsed_seconds','replay_sha256')},indent=2),flush=True)
